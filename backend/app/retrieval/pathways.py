from typing import List, Optional, Set
from collections import Counter
from itertools import combinations
import math

from backend.app.retrieval.models import TraversalContext, QueryType, Chunk, RankedSeed, ScoredNode, SyntheticPassage, Edge
from backend.app.retrieval.context import assemble_context, embed
from backend.app.db.queries import qdrant_search, neo4j_neighbors, pg_facts
from backend.app.db.connection import neo4j_driver, pg_pool

# --- Vector Pathway ---
async def vector_pathway(query: str) -> List[Chunk]:
    query_embedding = await embed(query)
    results = await qdrant_search(query_embedding, top_k=20)
    chunks = []
    for r in results:
        chunks.append(Chunk(
            chunk_id=r["chunk_id"],
            text=r["text"],
            score=0.8, # Mock score
            source="vector",
            payload=r["payload"]
        ))
    return chunks

# --- Lexical Pathway ---
async def lexical_pathway(query: str) -> List[Chunk]:
    # Real Lexical search (Postgres FTS)
    sql = """
        SELECT chunk_id, text, payload 
        FROM chunks 
        WHERE fts @@ plainto_tsquery('english', %s)
        LIMIT 20
    """
    try:
        async with pg_pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(sql, (query,))
                rows = await cur.fetchall()
                chunks = []
                for row in rows:
                    chunks.append(Chunk(
                        chunk_id=row[0],
                        text=row[1],
                        score=0.8, # Fallback BM25/FTS score, usually need rank_cd
                        source="lexical",
                        payload=row[2] or {}
                    ))
                return chunks
    except Exception:
        return []

# --- Graph Pathway Components ---
async def embedding_expand(query_embedding: List[float]) -> List[str]:
    # Strategy B - Embedding-Nearest Nodes
    chunks = await qdrant_search(query_embedding, top_k=10)
    doc_ids = [c["payload"].get("doc_id") for c in chunks if "doc_id" in c.get("payload", {})]
    
    # Fetch distinct subject_tags from facts table for these doc_ids
    facts = await pg_facts(doc_ids)
    tags = list(set([f["subject_tag"] for f in facts if "subject_tag" in f]))
    return tags

async def type_based_expand(tag: str) -> List[str]:
    # Strategy C - Type-Based Expansion (mock)
    # Would query Neo4j for nodes with the same type
    return []

async def expand_seeds(ctx: TraversalContext) -> List[RankedSeed]:
    seeds: dict[str, float] = {}
    
    # Strategy A: Direct Seeds
    for tag in ctx.explicit_tags:
        seeds[tag] = seeds.get(tag, 0.0) + 1.0 # High weight
    for tag in ctx.implicit_tags:
        seeds[tag] = seeds.get(tag, 0.0) + 0.8 # Medium weight
        
    # Strategy B: Embedding-Nearest
    embed_tags = await embedding_expand(ctx.query_embedding)
    for tag in embed_tags:
        seeds[tag] = seeds.get(tag, 0.0) + 0.5
        
    # Strategy C: Type-Based (for diagnostic)
    if ctx.query_type == QueryType.DIAGNOSTIC and ctx.explicit_tags:
        for tag in ctx.explicit_tags:
            type_tags = await type_based_expand(tag)
            for t_tag in type_tags:
                seeds[t_tag] = seeds.get(t_tag, 0.0) + 0.6
                
    ranked = [RankedSeed(tag=k, score=v) for k, v in seeds.items()]
    ranked.sort(key=lambda x: -x.score)
    return ranked[:15] # Top 15

# Helper for cosine similarity
def cosine_similarity(v1: List[float], v2: List[float]) -> float:
    # Mock: return a constant or simple check
    if not v1 or not v2: return 0.0
    return 0.8

async def adaptive_traverse(
    seeds: List[RankedSeed], query_embedding: List[float],
    max_depth: int = 5, relevance_threshold: float = 0.3, max_nodes: int = 50
) -> List[ScoredNode]:
    visited = {}
    frontier = [(s.tag, 0, s.score) for s in seeds]
    
    while frontier and len(visited) < max_nodes:
        frontier.sort(key=lambda x: -x[2])
        tag, depth, parent_score = frontier.pop(0)
        
        if tag in visited or depth > max_depth:
            continue
            
        # Mock node text/embedding
        node_embedding = await embed(tag) 
        semantic_sim = cosine_similarity(query_embedding, node_embedding)
        
        node_score = 0.5 * parent_score * 0.7 + 0.5 * semantic_sim # DECAY_FACTOR = 0.7
        
        if node_score < relevance_threshold and depth > 1:
            continue # Prune this branch
            
        visited[tag] = ScoredNode(tag=tag, score=node_score, depth=depth)
        
        neighbors = await neo4j_neighbors(tag)
        for neighbor_tag, rel_type, confidence in neighbors:
            if neighbor_tag not in visited:
                frontier.append((neighbor_tag, depth + 1, node_score * confidence))
                
    return sorted(visited.values(), key=lambda n: -n.score)

async def find_bridge_nodes(explicit_tags: List[str], already_found: Set[str]) -> List[ScoredNode]:
    bridges = Counter()
    query = """
    MATCH path = shortestPath((a {tag: $tag_a})-[*..6]-(b {tag: $tag_b}))
    RETURN [n IN nodes(path) | n.tag] AS path_tags
    """
    async with neo4j_driver.session() as session:
        for tag_a, tag_b in combinations(explicit_tags, 2):
            result = await session.run(query, tag_a=tag_a, tag_b=tag_b)
            record = await result.single()
            if record and record["path_tags"]:
                path_tags = record["path_tags"]
                for tag in path_tags[1:-1]: # exclude endpoints
                    bridges[tag] += 1
                    
    return [ScoredNode(tag=t, score=0.6, depth=3) for t, _ in bridges.most_common(10) if t not in already_found]

async def detect_hubs(explicit_tags: List[str]) -> List[ScoredNode]:
    query = """
    UNWIND $tags AS seed_tag
    MATCH (seed {tag: seed_tag})-[*1..3]-(member)
    WITH member, count(*) AS connections
    WHERE connections >= 3
    RETURN member.tag AS tag, labels(member)[0] AS entity_type, connections
    ORDER BY connections DESC LIMIT 5
    """
    async with neo4j_driver.session() as session:
        result = await session.run(query, tags=explicit_tags)
        records = await result.data()
        return [ScoredNode(tag=rec["tag"], score=0.7, depth=2, entity_type=rec["entity_type"] or "Unknown") for rec in records]

async def get_node_edges(tag: str) -> List[Edge]:
    # Mock
    return []

def node_to_passage(node: ScoredNode, edges: List[Edge]) -> SyntheticPassage:
    lines = [f"{node.tag} ({node.entity_type}):"]
    for edge in edges:
         lines.append(
             f"- {edge.rel_type} -> {edge.target_tag} "
             f"[confidence: {edge.confidence:.2f}, source: {edge.source_doc_id}]"
         )
    return SyntheticPassage(
        chunk_id=f"graph-{node.tag}", text="\n".join(lines), score=node.score,
        source="graph_traversal", fact_ids=[e.fact_id for e in edges], payload={}
    )

async def graph_pathway(
    query: str, query_type: QueryType, session_id: str, focused_tag: Optional[str] = None, depth_mode: str = "deep"
) -> List[Chunk]:
    ctx = await assemble_context(query, session_id, focused_tag)
    seeds = await expand_seeds(ctx)
    
    if depth_mode == "shallow":
        # Retained fast path
        traversed = await adaptive_traverse(seeds, ctx.query_embedding, max_depth=2, max_nodes=20)
    else:
        # Full adaptive pipeline
        traversed = await adaptive_traverse(seeds, ctx.query_embedding)
        
        if query_type in (QueryType.DIAGNOSTIC, QueryType.OPEN):
            bridges = await find_bridge_nodes(ctx.explicit_tags, {n.tag for n in traversed})
            hubs = await detect_hubs(ctx.explicit_tags)
            traversed.extend(bridges + hubs)
            
    passages = []
    for node in traversed[:20]:
        edges = await get_node_edges(node.tag)
        passages.append(node_to_passage(node, edges))
        
    return passages

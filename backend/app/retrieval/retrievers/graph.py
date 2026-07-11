from typing import List, Set, Dict, Any
from collections import Counter
from itertools import combinations
import structlog

from backend.app.retrieval.interfaces import BaseRetriever, SearchQuery
from backend.app.retrieval.models import TraversalContext, QueryType, Chunk, RankedSeed, ScoredNode, SyntheticPassage, Edge
from backend.app.db.queries import qdrant_search, neo4j_neighbors, pg_facts
from backend.shared.neo4j_client import get_neo4j_async

logger = structlog.get_logger(__name__)

class GraphRetriever(BaseRetriever):
    @property
    def name(self) -> str:
        return "graph"

    async def _embedding_expand(self, query_embedding: List[float]) -> List[str]:
        chunks = await qdrant_search(query_embedding, top_k=10)
        doc_ids = [c["payload"].get("doc_id") for c in chunks if "doc_id" in c.get("payload", {})]
        facts = await pg_facts(doc_ids)
        tags = list(set([f["subject_tag"] for f in facts if "subject_tag" in f]))
        return tags

    async def _type_based_expand(self, tag: str) -> List[str]:
        query = """
        MATCH (n {tag: $tag})
        WITH labels(n) AS lbls
        MATCH (m)
        WHERE any(lbl IN lbls WHERE lbl IN labels(m)) AND m.tag <> $tag
        RETURN m.tag as tag LIMIT 10
        """
        try:
            driver = get_neo4j_async()
            async with driver.session() as session:
                result = await session.run(query, tag=tag)
                records = await result.data()
                return [r["tag"] for r in records if "tag" in r]
        except Exception as e:
            logger.warning(
                "type expansion failed",
                tag=tag,
                exception_type=type(e).__name__,
                exc_info=True
            )
            return []

    async def _expand_seeds(self, ctx: TraversalContext) -> List[RankedSeed]:
        seeds: Dict[str, float] = {}
        
        for tag in ctx.explicit_tags:
            seeds[tag] = seeds.get(tag, 0.0) + 1.0
        for tag in ctx.implicit_tags:
            seeds[tag] = seeds.get(tag, 0.0) + 0.8
            
        embed_tags = await self._embedding_expand(ctx.query_embedding)
        for tag in embed_tags:
            seeds[tag] = seeds.get(tag, 0.0) + 0.5
            
        if ctx.query_type == QueryType.DIAGNOSTIC and ctx.explicit_tags:
            for tag in ctx.explicit_tags:
                type_tags = await self._type_based_expand(tag)
                for t_tag in type_tags:
                    seeds[t_tag] = seeds.get(t_tag, 0.0) + 0.6
                    
        ranked = [RankedSeed(tag=k, score=v) for k, v in seeds.items()]
        ranked.sort(key=lambda x: -x.score)
        return ranked[:15]

    async def _adaptive_traverse(
        self, seeds: List[RankedSeed], max_depth: int = 5, relevance_threshold: float = 0.3, max_nodes: int = 50
    ) -> List[ScoredNode]:
        visited = {}
        frontier = [(s.tag, 0, s.score) for s in seeds]
        
        while frontier and len(visited) < max_nodes:
            frontier.sort(key=lambda x: -x[2])
            tag, depth, parent_score = frontier.pop(0)
            
            if tag in visited or depth > max_depth:
                continue
                
            node_score = parent_score * 0.85
            
            if node_score < relevance_threshold and depth > 1:
                continue
                
            visited[tag] = ScoredNode(tag=tag, score=node_score, depth=depth)
            
            neighbors = await neo4j_neighbors(tag)
            for neighbor_tag, rel_type, confidence in neighbors:
                if neighbor_tag not in visited:
                    frontier.append((neighbor_tag, depth + 1, node_score * confidence))
                    
        return sorted(visited.values(), key=lambda n: -n.score)

    async def _find_bridge_nodes(self, explicit_tags: List[str], already_found: Set[str]) -> List[ScoredNode]:
        bridges = Counter()
        query = """
        MATCH path = shortestPath((a {tag: $tag_a})-[*..6]-(b {tag: $tag_b}))
        RETURN [n IN nodes(path) | n.tag] AS path_tags
        """
        driver = get_neo4j_async()
        async with driver.session() as session:
            for tag_a, tag_b in combinations(explicit_tags, 2):
                result = await session.run(query, tag_a=tag_a, tag_b=tag_b)
                record = await result.single()
                if record and record["path_tags"]:
                    path_tags = record["path_tags"]
                    for tag in path_tags[1:-1]:
                        bridges[tag] += 1
                        
        return [ScoredNode(tag=t, score=0.6, depth=3) for t, _ in bridges.most_common(10) if t not in already_found]

    async def _detect_hubs(self, explicit_tags: List[str]) -> List[ScoredNode]:
        query = """
        UNWIND $tags AS seed_tag
        MATCH (seed {tag: seed_tag})-[*1..3]-(member)
        WITH member, count(*) AS connections
        WHERE connections >= 3
        RETURN member.tag AS tag, labels(member)[0] AS entity_type, connections
        ORDER BY connections DESC LIMIT 5
        """
        driver = get_neo4j_async()
        async with driver.session() as session:
            result = await session.run(query, tags=explicit_tags)
            records = await result.data()
            return [ScoredNode(tag=rec["tag"], score=0.7, depth=2, entity_type=rec["entity_type"] or "Unknown") for rec in records]

    async def _get_node_edges(self, tag: str) -> List[Edge]:
        query = """
        MATCH (n {tag: $tag})-[r]->(m)
        RETURN m.tag as target_tag, type(r) as rel_type, r.confidence as confidence, r.source_doc_id as source_doc_id
        LIMIT 20
        """
        try:
            driver = get_neo4j_async()
            async with driver.session() as session:
                result = await session.run(query, tag=tag)
                records = await result.data()
                edges = []
                for r in records:
                    edges.append(Edge(
                        source_tag=tag,
                        target_tag=r["target_tag"],
                        rel_type=r["rel_type"],
                        confidence=r.get("confidence", 1.0),
                        fact_id=r.get("fact_id", "unknown"),
                        source_doc_id=r.get("source_doc_id", "unknown")
                    ))
                return edges
        except Exception as e:
            logger.warning(
                "node edges retrieval failed",
                tag=tag,
                exception_type=type(e).__name__,
                exc_info=True
            )
            return []

    def _node_to_passage(self, node: ScoredNode, edges: List[Edge]) -> SyntheticPassage:
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

    async def _retrieve_impl(self, query: SearchQuery, context: TraversalContext) -> List[Chunk]:
        depth_mode = "deep" if query.query_type in (QueryType.DIAGNOSTIC, QueryType.OPEN) else "shallow"
        
        seeds = await self._expand_seeds(context)
        
        if depth_mode == "shallow":
            traversed = await self._adaptive_traverse(seeds, max_depth=2, max_nodes=20)
        else:
            traversed = await self._adaptive_traverse(seeds)
            
            if context.query_type in (QueryType.DIAGNOSTIC, QueryType.OPEN):
                bridges = await self._find_bridge_nodes(context.explicit_tags, {n.tag for n in traversed})
                hubs = await self._detect_hubs(context.explicit_tags)
                traversed.extend(bridges + hubs)
                
        passages = []
        for node in traversed[:20]:
            edges = await self._get_node_edges(node.tag)
            passages.append(self._node_to_passage(node, edges))
            
        return passages

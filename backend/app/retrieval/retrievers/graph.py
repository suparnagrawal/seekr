from typing import List, Set, Dict, Tuple
from collections import Counter
from dataclasses import dataclass
import structlog

from backend.app.retrieval.interfaces import BaseRetriever, SearchQuery
from backend.app.retrieval.models import (
    TraversalContext,
    QueryType,
    Chunk,
    RankedSeed,
    ScoredNode,
    SyntheticPassage,
    Edge,
)
from backend.app.db.queries import neo4j_bulk_neighbors
from backend.shared.neo4j_client import get_neo4j_async
from backend.shared.config import settings

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class TraversalConfig:
    """Tunable traversal parameters, sourced from settings rather than hardcoded
    magic numbers inside the algorithm."""

    max_nodes: int
    max_depth: int
    decay: float
    relevance_threshold: float
    offtarget_multiplier: float

    @classmethod
    def deep(cls) -> "TraversalConfig":
        return cls(
            max_nodes=settings.GRAPH_TRAVERSAL_MAX_NODES,
            max_depth=settings.GRAPH_TRAVERSAL_MAX_DEPTH,
            decay=settings.GRAPH_TRAVERSAL_DECAY,
            relevance_threshold=settings.GRAPH_TRAVERSAL_RELEVANCE_THRESHOLD,
            offtarget_multiplier=settings.GRAPH_TRAVERSAL_OFFTARGET_MULTIPLIER,
        )

    @classmethod
    def shallow(cls) -> "TraversalConfig":
        return cls(
            max_nodes=settings.GRAPH_TRAVERSAL_SHALLOW_MAX_NODES,
            max_depth=settings.GRAPH_TRAVERSAL_SHALLOW_MAX_DEPTH,
            decay=settings.GRAPH_TRAVERSAL_DECAY,
            relevance_threshold=settings.GRAPH_TRAVERSAL_RELEVANCE_THRESHOLD,
            offtarget_multiplier=settings.GRAPH_TRAVERSAL_OFFTARGET_MULTIPLIER,
        )


class GraphRetriever(BaseRetriever):
    @property
    def name(self) -> str:
        return "graph"

    async def _type_based_expand(self, tag: str) -> List[str]:
        query = """
        MATCH (n:Entity {tag: $tag})
        MATCH (m:Entity {type: n.type})
        WHERE m.tag <> $tag
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
                exc_info=True,
            )
            return []

    async def _expand_seeds(self, ctx: TraversalContext) -> List[RankedSeed]:
        seeds: Dict[str, float] = {}

        for tag in ctx.explicit_tags:
            seeds[tag] = seeds.get(tag, 0.0) + 1.0
        for tag in ctx.implicit_tags:
            seeds[tag] = seeds.get(tag, 0.0) + 0.8

        if ctx.query_type == QueryType.DIAGNOSTIC and ctx.explicit_tags:
            for tag in ctx.explicit_tags:
                type_tags = await self._type_based_expand(tag)
                for t_tag in type_tags:
                    seeds[t_tag] = seeds.get(t_tag, 0.0) + 0.6

        ranked = [RankedSeed(tag=k, score=v) for k, v in seeds.items()]
        ranked.sort(key=lambda x: -x.score)
        return ranked[: settings.GRAPH_TRAVERSAL_MAX_SEEDS]

    async def _adaptive_traverse(
        self, seeds: List[RankedSeed], context: TraversalContext, config: TraversalConfig
    ) -> List[ScoredNode]:
        """Best-first, *level-synchronous* graph expansion.

        Unlike the previous implementation — which issued one Neo4j round-trip
        per visited node (an N+1 pattern, up to `max_nodes` sequential queries)
        — this expands the graph one depth level at a time, fetching neighbors
        for the entire wave in a single batched query. Round-trips are therefore
        bounded by traversal depth, not by node count.

        Scoring: a node's score is inherited from the best parent that reached
        it, decayed per hop and scaled by edge confidence; edges whose type is
        outside the query's target relationship set are down-weighted.
        """
        target_types = set(context.target_relationship_types or [])

        visited: Dict[str, ScoredNode] = {}
        # tag -> (depth, score) for the current expansion wave. Seeds start
        # undecayed at depth 0; decay is applied as we generate their children.
        current: Dict[str, Tuple[int, float]] = {}
        for s in seeds:
            prev = current.get(s.tag)
            if prev is None or s.score > prev[1]:
                current[s.tag] = (0, s.score)

        while current and len(visited) < config.max_nodes:
            # Record this wave's nodes as visited (best-scoring first, capped).
            wave = sorted(current.items(), key=lambda kv: -kv[1][1])
            to_expand: List[Tuple[str, int, float]] = []
            for tag, (depth, score) in wave:
                if tag in visited:
                    continue
                if len(visited) >= config.max_nodes:
                    break
                visited[tag] = ScoredNode(tag=tag, score=score, depth=depth)
                if depth < config.max_depth:
                    to_expand.append((tag, depth, score))

            if not to_expand:
                break

            neighbor_map = await neo4j_bulk_neighbors([t for t, _, _ in to_expand])

            next_wave: Dict[str, Tuple[int, float]] = {}
            for tag, depth, node_score in to_expand:
                for neighbor_tag, rel_type, confidence in neighbor_map.get(tag, []):
                    if neighbor_tag in visited:
                        continue
                    rel_multiplier = (
                        1.0
                        if (not target_types or rel_type in target_types)
                        else config.offtarget_multiplier
                    )
                    child_depth = depth + 1
                    child_score = node_score * config.decay * float(confidence) * rel_multiplier
                    # Prune weak nodes past the first hop from further expansion.
                    if child_score < config.relevance_threshold and child_depth > 1:
                        continue
                    prev = next_wave.get(neighbor_tag)
                    if prev is None or child_score > prev[1]:
                        next_wave[neighbor_tag] = (child_depth, child_score)

            current = next_wave

        return sorted(visited.values(), key=lambda n: -n.score)

    async def _find_bridge_nodes(
        self, explicit_tags: List[str], already_found: Set[str]
    ) -> List[ScoredNode]:
        if not explicit_tags or len(explicit_tags) < 2:
            return []

        bridges: Counter = Counter()
        query = """
        UNWIND $tags as tag_a
        UNWIND $tags as tag_b
        WITH tag_a, tag_b WHERE tag_a < tag_b
        MATCH path = shortestPath((a:Entity {tag: tag_a})-[*..6]-(b:Entity {tag: tag_b}))
        RETURN [n IN nodes(path) | n.tag] AS path_tags
        """
        driver = get_neo4j_async()
        async with driver.session() as session:
            result = await session.run(query, tags=explicit_tags)
            records = await result.data()
            for record in records:
                if record and record.get("path_tags"):
                    path_tags = record["path_tags"]
                    for tag in path_tags[1:-1]:
                        bridges[tag] += 1

        return [
            ScoredNode(tag=t, score=0.6, depth=3)
            for t, _ in bridges.most_common(10)
            if t not in already_found
        ]

    async def _detect_hubs(self, explicit_tags: List[str]) -> List[ScoredNode]:
        """Find highly-connected entities near the seeds using true node degree.

        The previous query counted *variable-length paths* through each member
        (`count(*)` over `[*1..3]`), which both over-counts (paths, not distinct
        neighbors) and is expensive. This scopes to `:Entity`, collapses to
        distinct members within 2 hops, and ranks by distinct-relationship
        degree — the correct notion of a hub.
        """
        if not explicit_tags:
            return []
        query = """
        UNWIND $tags AS seed_tag
        MATCH (seed:Entity {tag: seed_tag})-[*1..2]-(member:Entity)
        WITH DISTINCT member
        MATCH (member)-[r]-(:Entity)
        WITH member, count(DISTINCT r) AS degree
        WHERE degree >= $min_degree
        RETURN member.tag AS tag, member.type AS entity_type, degree
        ORDER BY degree DESC LIMIT $limit
        """
        driver = get_neo4j_async()
        async with driver.session() as session:
            result = await session.run(query, tags=explicit_tags, min_degree=3, limit=5)
            records = await result.data()
            return [
                ScoredNode(
                    tag=rec["tag"],
                    score=0.7,
                    depth=2,
                    entity_type=rec.get("entity_type") or "Unknown",
                )
                for rec in records
            ]

    async def _get_bulk_node_data(
        self, tags: List[str]
    ) -> Tuple[Dict[str, str], Dict[str, List[Edge]]]:
        if not tags:
            return {}, {}

        query = """
        UNWIND $tags AS tag
        MATCH (n:Entity {tag: tag})
        OPTIONAL MATCH (n)-[r]->(m:Entity)
        RETURN n.tag as source_tag, n.description as source_desc,
               m.tag as target_tag, m.description as target_desc,
               type(r) as rel_type, r.description as rel_desc,
               r.confidence as confidence, r.fact_id as fact_id, r.source_doc_id as source_doc_id
        """
        edges_by_node: Dict[str, List[Edge]] = {tag: [] for tag in tags}
        desc_by_node: Dict[str, str] = {}
        try:
            driver = get_neo4j_async()
            async with driver.session() as session:
                result = await session.run(query, tags=tags)
                records = await result.data()

                for r in records:
                    source_tag = r["source_tag"]
                    desc_by_node[source_tag] = r.get("source_desc") or ""

                    if r.get("target_tag") and r.get("rel_type"):
                        edges_by_node.setdefault(source_tag, []).append(
                            Edge(
                                source_tag=source_tag,
                                target_tag=r["target_tag"],
                                rel_type=r["rel_type"],
                                # `or` (not dict default) so a present-but-null
                                # property is treated as the fallback, avoiding a
                                # None that would crash downstream float/str fmt.
                                confidence=r.get("confidence") or 1.0,
                                fact_id=r.get("fact_id") or "unknown",
                                source_doc_id=r.get("source_doc_id") or "unknown",
                                description=r.get("rel_desc") or "",
                            )
                        )
                return desc_by_node, edges_by_node
        except Exception as e:
            logger.warning(
                "bulk node edges retrieval failed",
                exception_type=type(e).__name__,
                exc_info=True,
            )
            return desc_by_node, edges_by_node

    def _node_to_passage(
        self, node: ScoredNode, edges: List[Edge], description: str
    ) -> SyntheticPassage:
        lines = [f"[Entity] {node.tag} ({node.entity_type})"]
        if description:
            lines.append(f"Description: {description}")

        if edges:
            lines.append("Relationships:")
            for edge in edges:
                rel_text = f" - [{edge.rel_type}] -> {edge.target_tag}"
                if edge.description:
                    rel_text += f": {edge.description}"
                rel_text += f" (Confidence: {edge.confidence:.2f}, Source: {edge.source_doc_id})"
                lines.append(rel_text)

        return SyntheticPassage(
            chunk_id=f"graph-{node.tag}",
            text="\n".join(lines),
            score=node.score,
            source="graph",
            fact_ids=[e.fact_id for e in edges],
            payload={},
        )

    async def _retrieve_impl(self, query: SearchQuery, context: TraversalContext) -> List[Chunk]:
        deep = query.query_type in (QueryType.DIAGNOSTIC, QueryType.OPEN)
        config = TraversalConfig.deep() if deep else TraversalConfig.shallow()

        seeds = await self._expand_seeds(context)
        if not seeds:
            return []

        traversed = await self._adaptive_traverse(seeds, context, config)

        if context.query_type in (QueryType.DIAGNOSTIC, QueryType.OPEN):
            bridges = await self._find_bridge_nodes(
                context.explicit_tags, {n.tag for n in traversed}
            )
            hubs = await self._detect_hubs(context.explicit_tags)
            traversed.extend(bridges + hubs)

        passages: List[Chunk] = []
        top_nodes = traversed[: settings.GRAPH_TRAVERSAL_MAX_PASSAGES]
        node_tags = [n.tag for n in top_nodes]
        desc_by_node, edges_by_node = await self._get_bulk_node_data(node_tags)

        for node in top_nodes:
            edges = edges_by_node.get(node.tag, [])
            desc = desc_by_node.get(node.tag, "")
            passages.append(self._node_to_passage(node, edges, desc))

        return passages

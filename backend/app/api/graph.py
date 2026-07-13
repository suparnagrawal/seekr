"""
Structured knowledge-graph read API.

Exposes the Neo4j knowledge graph as structured nodes/edges for the frontend
graph explorer. This is a read-only projection of the graph that ingestion
builds; it does not invoke the LLM or the agent layer.
"""

from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, Query

from backend.shared.neo4j_client import neo4j_driver
from backend.app.schemas.graph import GraphNode, GraphEdge, GraphResponse
from backend.app.agents.shared.logging import get_logger, log_error

router = APIRouter()
logger = get_logger("api.graph")

# Traversal depth is interpolated into the Cypher query (Neo4j cannot
# parameterize variable-length bounds), so it is clamped to a small, validated
# integer range to keep the query text safe and the traversal bounded.
_MIN_DEPTH = 1
_MAX_DEPTH = 3

_GENERIC_LABELS = {"Entity", "Node", "Resource"}


def _derive_type(labels: List[str], props: Dict[str, Any]) -> str:
    """Pick a display type: the `type` property (written by extraction) wins,
    then the first non-generic label, else a generic default."""
    prop_type = props.get("type")
    if prop_type:
        return str(prop_type).lower()
    for label in labels:
        if label not in _GENERIC_LABELS:
            return label.lower()
    return labels[0].lower() if labels else "entity"


def _derive_label(props: Dict[str, Any], tag: str) -> str:
    """Pick a human-readable name for a node."""
    for key in ("name", "label", "title", "display_name"):
        value = props.get(key)
        if value:
            return str(value)
    return tag


@router.get("/graph", response_model=GraphResponse)
async def get_graph(
    tag: str = Query(..., description="Tag of the entity to centre the graph on."),
    depth: int = Query(2, ge=_MIN_DEPTH, le=_MAX_DEPTH, description="Traversal hops from the centre."),
) -> GraphResponse:
    """
    Return the neighbourhood of `tag` up to `depth` hops as structured
    nodes and edges. Returns an empty graph (not an error) if the tag is
    unknown, so the frontend can render an explicit empty state.
    """
    safe_depth = max(_MIN_DEPTH, min(_MAX_DEPTH, int(depth)))

    nodes_query = f"""
    MATCH (c {{tag: $tag}})
    OPTIONAL MATCH (c)-[*1..{safe_depth}]-(m)
    WITH collect(DISTINCT c) + collect(DISTINCT m) AS all_nodes
    UNWIND all_nodes AS node
    WITH DISTINCT node
    WHERE node IS NOT NULL AND node.tag IS NOT NULL
    RETURN node.tag AS tag, labels(node) AS labels, properties(node) AS props
    """

    edges_query = """
    MATCH (a)-[r]-(b)
    WHERE a.tag IN $tags AND b.tag IN $tags
    RETURN a.tag AS source, b.tag AS target, type(r) AS rel,
           COALESCE(r.confidence, 1.0) AS confidence, properties(r) AS props
    """

    try:
        async with neo4j_driver.session() as session:
            node_result = await session.run(nodes_query, tag=tag)
            node_records = await node_result.data()

            nodes: List[GraphNode] = []
            tags: List[str] = []
            for rec in node_records:
                node_tag = rec["tag"]
                props = rec.get("props") or {}
                labels = rec.get("labels") or []
                tags.append(node_tag)
                nodes.append(
                    GraphNode(
                        id=node_tag,
                        tag=node_tag,
                        label=_derive_label(props, node_tag),
                        type=_derive_type(labels, props),
                        properties=props,
                        confidence=props.get("confidence"),
                    )
                )

            edges: List[GraphEdge] = []
            if tags:
                edge_result = await session.run(edges_query, tags=tags)
                edge_records = await edge_result.data()

                seen: set[tuple[str, str, str]] = set()
                for rec in edge_records:
                    source = rec["source"]
                    target = rec["target"]
                    rel = rec["rel"]
                    # The undirected match returns each edge twice; dedupe on
                    # the unordered pair plus relationship type.
                    pair = tuple(sorted((source, target)))
                    key = (pair[0], pair[1], rel)
                    if key in seen:
                        continue
                    seen.add(key)
                    edges.append(
                        GraphEdge(
                            id=f"{source}-{rel}-{target}",
                            source=source,
                            target=target,
                            relationship=rel,
                            confidence=float(rec.get("confidence") or 1.0),
                            properties=rec.get("props") or {},
                        )
                    )

        return GraphResponse(center=tag, nodes=nodes, edges=edges)

    except Exception as exc:
        log_error(logger, str(exc), session_id=f"graph:{tag}", exc_info=True)
        # Fail soft: an unreachable graph store should not 500 the explorer.
        return GraphResponse(center=tag, nodes=[], edges=[])

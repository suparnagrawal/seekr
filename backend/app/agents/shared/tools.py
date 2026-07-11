"""
Thin abstraction layer over the P2 retrieval interfaces.

All P3 components (Copilot, Supervisor, Workers) must import retrieval
functions from this module rather than importing directly from
app.retrieval.* or app.kg.*.

This module re-exports the frozen public interfaces without duplicating
any retrieval logic.
"""

from __future__ import annotations

from typing import Optional, Dict, Any, List

from backend.app.retrieval.models import (
    GraphContext,
    QueryType,
    RetrievalContext,
)
from backend.app.retrieval.orchestrator import retrieve as _p2_retrieve
from backend.app.kg.shared_tools import context_graph_query as _p2_context_graph_query


async def retrieve(
    query: str,
    query_type: QueryType,
    session_id: str,
    focused_tag: Optional[str] = None,
) -> RetrievalContext:
    """
    Public retrieval interface consumed by P3.

    Delegates to the P2 retrieve() function. Runs graph, vector, and lexical
    pathways in parallel, fuses the results, and returns a structured
    RetrievalContext.
    """
    return await _p2_retrieve(
        query=query,
        query_type=query_type,
        session_id=session_id,
        focused_tag=focused_tag,
    )


async def context_graph_query(
    tag: str,
    query: str,
    depth: str = "auto",
    include_analogues: bool = False,
) -> GraphContext:
    """
    Knowledge graph retrieval tool exposed to P3.

    Delegates to the P2 context_graph_query() function. Dynamically runs the
    full context-aware graph pipeline and returns a GraphContext.
    """
    return await _p2_context_graph_query(
        tag=tag,
        query=query,
        depth=depth,
        include_analogues=include_analogues,
    )


def serialize_retrieval_context(ctx: RetrievalContext) -> Dict[str, Any]:
    """Serialize P2 RetrievalContext into a standard dictionary for P3 state."""
    return {
        "chunks": [
            {"chunk_id": c.chunk_id, "text": c.text, "score": c.score, "source": c.source}
            for c in ctx.chunks
        ],
        "metadata": ctx.metadata,
    }


def serialize_citations(ctx: RetrievalContext) -> List[Dict[str, Any]]:
    """Serialize P2 Citations into a standard list of dictionaries for P3 state."""
    return [
        {"doc_id": c.doc_id, "passage_id": c.passage_id, "page": c.page}
        for c in ctx.citations
    ]

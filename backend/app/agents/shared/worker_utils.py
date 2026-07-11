"""
Shared utility helpers for specialist workers.
"""

from __future__ import annotations

from typing import AsyncIterator, List, Tuple
import structlog

from backend.app.agents.shared.state import AgentState
from backend.app.agents.shared.tools import context_graph_query
from backend.app.agents.shared.streaming import (
    emit_tool_call,
    emit_tool_result,
    emit_token,
    emit_citation,
)
from backend.app.agents.shared.llm import generate_streaming
from backend.app.agents.shared.logging import log_tool_execution


async def execute_graph_query_tool(
    state: AgentState,
    depth: str,
    logger: structlog.stdlib.BoundLogger,
) -> AsyncIterator[Tuple[str, str]]:
    """
    Execute the context_graph_query tool and yield streaming events.
    Yields tuples of (event_string, context_text) where the last yield
    contains the actual result string.
    """
    tag = state.focused_tag or "unknown"
    graph_context_text = ""

    yield emit_tool_call(
        tool_name="context_graph_query",
        tool_args={"tag": tag, "depth": depth},
    ), graph_context_text

    try:
        graph_context = await context_graph_query(
            tag=tag,
            query=state.query,
            depth=depth,
        )
        log_tool_execution(
            logger,
            tool_name="context_graph_query",
            session_id=state.session_id,
            success=True,
        )
        yield emit_tool_result("context_graph_query", "Retrieved graph context."), graph_context_text
        
        graph_texts = [p.text for p in graph_context.passages]
        graph_context_text = "\n\n".join(graph_texts)
        
    except Exception as tool_exc:
        log_tool_execution(
            logger,
            tool_name="context_graph_query",
            session_id=state.session_id,
            success=False,
            error=str(tool_exc),
        )
        yield emit_tool_result("context_graph_query", f"Error: {tool_exc}"), graph_context_text

    # Final yield to pass the computed text
    yield "", graph_context_text


def extract_context_texts(state: AgentState) -> List[str]:
    """Extract context chunk texts from the AgentState."""
    chunks = state.retrieval_context.get("chunks", [])
    return [c.get("text", "") for c in chunks]


async def stream_generation_and_citations(
    messages: List[dict],
    state: AgentState,
) -> AsyncIterator[str]:
    """Stream LLM generation and append the state's citations."""
    async for token_text in generate_streaming(messages):
        yield emit_token(token_text)

    for citation in state.citations:
        yield emit_citation(
            doc_id=citation.get("doc_id", ""),
            passage_id=citation.get("passage_id", ""),
            page=citation.get("page"),
        )

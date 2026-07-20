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

    # Check if retrieval_context already has graph chunks from the Copilot pipeline
    if state.retrieval_context.get("chunks"):
        graph_chunks = [c for c in state.retrieval_context["chunks"] if c.get("source") == "graph"]
        if graph_chunks:
            graph_context_text = "\n\n".join([c.get("text", "") for c in graph_chunks])
            yield "", graph_context_text
            return

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
    """Stream LLM generation, validate citations, regenerate once if hallucinated, and append citations."""
    draft_parts = []
    async for token_text in generate_streaming(messages):
        draft_parts.append(token_text)
        yield emit_token(token_text)

    draft_answer = "".join(draft_parts)

    import re
    def extract_citations(text: str) -> set[tuple[str, int]]:
        extracted = set()
        for bracket_content in re.findall(r"\[(.*?)\]", text):
            chunk_match = re.search(r"chunk\s*(\d+)", bracket_content, re.IGNORECASE)
            if not chunk_match:
                continue
            chunk_idx = int(chunk_match.group(1))
            
            parts = [p.strip() for p in bracket_content.split(",")]
            filename = ""
            for p in parts:
                if "." in p and len(p.split(".")[-1]) in (2, 3, 4):
                    filename = p
                    break
            if not filename and parts:
                filename = parts[0]
                
            if filename:
                extracted.add((filename, chunk_idx))
        return extracted

    referenced_citations = extract_citations(draft_answer)
    
    # Valid citations from state context
    valid_context_keys = set()
    for chunk in state.retrieval_context.get("chunks", []):
        fname = chunk.get("payload", {}).get("filename", "")
        idx = chunk.get("payload", {}).get("chunk_index")
        if fname and idx is not None:
            valid_context_keys.add((fname, int(idx)))
            
    invalid_citations = [f"[{f}, Chunk {i}]" for (f, i) in referenced_citations if (f, i) not in valid_context_keys]
    
    if invalid_citations:
        yield emit_token("\n\n*(Self-Correction: I noticed I generated citations that were not present in the retrieved context. Let me correct that.)*\n\n")
        
        correction_messages = messages + [
            {"role": "assistant", "content": draft_answer},
            {"role": "user", "content": f"You included these invalid citations: {', '.join(invalid_citations)}. They are NOT in the context. Please regenerate your answer using ONLY the facts and citations explicitly provided in the context."}
        ]
        
        async for token_text in generate_streaming(correction_messages):
            yield emit_token(token_text)

    for citation in state.citations:
        yield emit_citation(
            doc_id=citation.get("doc_id", ""),
            filename=citation.get("filename", ""),
            passage_id=citation.get("passage_id", ""),
            chunk_index=citation.get("chunk_index", 0),
            page_numbers=citation.get("page_numbers", []),
            headings=citation.get("headings", []),
            page=citation.get("page"),
        )

"""
Copilot orchestrator — the main entry point for general query processing.

Implements the runtime flow:
    retrieve() → LLM Generation → Trigger Evaluation → stream or escalate

The Copilot never performs specialist reasoning. If escalation is required,
it constructs an EscalationContext and invokes the LangGraph workflow.
"""

from __future__ import annotations

import uuid
from typing import AsyncIterator, Optional

from backend.app.retrieval.models import QueryType
from backend.app.agents.shared.tools import retrieve, serialize_retrieval_context, serialize_citations
from backend.app.agents.shared.llm import generate_streaming
from backend.app.agents.shared.streaming import (
    emit_token,
    emit_citation,
    emit_done,
    emit_error,
)
from backend.app.agents.shared.state import EscalationContext
from backend.app.agents.shared.logging import get_logger, log_error
from backend.app.agents.copilot.prompts import build_copilot_messages
from backend.app.agents.copilot.classifier import evaluate_trigger
from backend.app.agents.graph.workflow import run_escalation_graph

logger = get_logger("copilot")


async def run_query(
    query: str,
    session_id: str,
    focused_tag: Optional[str] = None,
) -> AsyncIterator[str]:
    """
    Execute the full Copilot query lifecycle as an SSE event stream.

    This is the primary entry point that the API layer will call.
    It yields SSE-formatted strings suitable for a StreamingResponse.
    """
    answer_id = f"a-{uuid.uuid4().hex[:8]}"

    try:
        # --- Step 1: Retrieve context via P2 ---
        query_type = _classify_query_heuristic(query)
        retrieval_ctx = await retrieve(
            query=query,
            query_type=query_type,
            session_id=session_id,
            focused_tag=focused_tag,
        )

        # Group chunks by document, preserving the order of the highest-ranked chunk per document
        doc_groups = {}
        for chunk in retrieval_ctx.chunks:
            filename = chunk.payload.get("filename", "Unknown")
            if filename not in doc_groups:
                doc_groups[filename] = []
            doc_groups[filename].append(chunk)

        context_texts = []
        for filename, chunks in doc_groups.items():
            for chunk in chunks:
                page_numbers = chunk.payload.get("page_numbers", [])
                headings = chunk.payload.get("headings", [])
                chunk_idx = chunk.payload.get("chunk_index")
                
                header = f"Source: {filename}\n"
                if page_numbers:
                    header += f"Page: {page_numbers[0]}\n"
                if headings:
                    header += f"Section: {headings[-1]}\n"
                if chunk_idx is not None:
                    header += f"Chunk: {chunk_idx}\n"
                
                context_texts.append(f"{header}\n{chunk.text}")

        # --- Step 2: LLM Generation — stream tokens immediately ---
        messages = build_copilot_messages(query, context_texts)
        draft_parts: list[str] = []

        async for token_text in generate_streaming(messages):
            draft_parts.append(token_text)
            yield emit_token(token_text)

        draft_answer = "".join(draft_parts)

        # Persist the current exchange to session history for continuity
        await _persist_session_history(session_id, query, draft_answer)

        # --- Step 3: Extract referenced citations ---
        import re
        referenced_citations = set()
        # Parse [Filename, ..., Chunk Y] format in a robust way
        for bracket_content in re.findall(r"\[(.*?)\]", draft_answer):
            chunk_match = re.search(r"chunk\s*(\d+)", bracket_content, re.IGNORECASE)
            if not chunk_match:
                continue
            chunk_idx = int(chunk_match.group(1))
            
            parts = [p.strip() for p in bracket_content.split(",")]
            filename = ""
            # Try to find a part with a file extension, otherwise use the first part
            for p in parts:
                if "." in p and len(p.split(".")[-1]) in (2, 3, 4):
                    filename = p
                    break
            if not filename and parts:
                filename = parts[0]
                
            if filename:
                referenced_citations.add((filename, chunk_idx))

        MAX_FALLBACK_CITATIONS = 4
        if not referenced_citations:
            logger.info(
                "citation_filter_fallback",
                reason="no_referenced_citations_found",
                retrieved=len(retrieval_ctx.citations),
                emitted=min(MAX_FALLBACK_CITATIONS, len(retrieval_ctx.citations)),
            )

        # --- Step 4: Emit citations from retrieval context ---
        emitted_count = 0
        for citation in retrieval_ctx.citations:
            if referenced_citations:
                if (citation.filename, citation.chunk_index) not in referenced_citations:
                    continue
            else:
                if emitted_count >= MAX_FALLBACK_CITATIONS:
                    continue
            
            emitted_count += 1
            yield emit_citation(
                doc_id=citation.doc_id,
                filename=citation.filename,
                passage_id=citation.passage_id,
                chunk_index=citation.chunk_index,
                page_numbers=citation.page_numbers,
                headings=citation.headings,
                page=citation.page,
            )

        # --- Step 4: Trigger Evaluation ---
        should_escalate, reason, confidence = await evaluate_trigger(
            query, draft_answer, session_id=session_id,
        )

        if not should_escalate:
            # Normal flow — done
            yield emit_done(answer_id)
            return

        # --- Step 5: Escalation via LangGraph ---
        escalation = EscalationContext(
            query=query,
            session_id=session_id,
            focused_tag=focused_tag,
            retrieval_context=serialize_retrieval_context(retrieval_ctx),
            citations=serialize_citations(retrieval_ctx),
            trigger_reason=reason,
            trigger_confidence=confidence,
            copilot_answer=draft_answer,
        )

        # LangGraph workflow: Supervisor → Worker
        async for event in run_escalation_graph(escalation):
            yield event

        yield emit_done(answer_id)

    except Exception as exc:
        log_error(logger, str(exc), session_id=session_id, exc_info=True)
        yield emit_error(str(exc))
        yield emit_done(answer_id)


from backend.shared.query_classification import classify_query_heuristic

def _classify_query_heuristic(query: str) -> QueryType:
    """
    Fast heuristic query classification used before retrieval.
    """
    return classify_query_heuristic(query) or QueryType.OPEN


async def _persist_session_history(session_id: str, query: str, answer: str) -> None:
    """Persist the current query/answer pair to Redis session history.

    Best-effort: a failure to write history should never break the response
    stream.  The history list is capped at 20 entries to bound memory.
    """
    from backend.shared.redis_client import redis_conn
    import asyncio

    key = f"session:{session_id}:history"
    try:
        await asyncio.to_thread(redis_conn.rpush, key, query)
        await asyncio.to_thread(redis_conn.rpush, key, answer)
        # Keep the list bounded so long sessions don't leak memory
        await asyncio.to_thread(redis_conn.ltrim, key, -20, -1)
        # Set a 24-hour TTL so stale sessions expire
        await asyncio.to_thread(redis_conn.expire, key, 86400)
    except Exception:
        logger.warning("session_history_persist_failed", session_id=session_id, exc_info=True)

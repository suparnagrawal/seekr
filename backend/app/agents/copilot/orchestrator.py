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

        context_texts = [chunk.text for chunk in retrieval_ctx.chunks]

        # --- Step 2: LLM Generation — stream tokens immediately ---
        messages = build_copilot_messages(query, context_texts)
        draft_parts: list[str] = []

        async for token_text in generate_streaming(messages):
            draft_parts.append(token_text)
            yield emit_token(token_text)

        draft_answer = "".join(draft_parts)

        # --- Step 3: Emit citations from retrieval context ---
        for citation in retrieval_ctx.citations:
            yield emit_citation(
                doc_id=citation.doc_id,
                passage_id=citation.passage_id,
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


def _classify_query_heuristic(query: str) -> QueryType:
    """
    Fast heuristic query classification used before retrieval.

    This mirrors the logic in backend/app/retrieval/context.py but is
    duplicated here intentionally: the Copilot needs a QueryType to call
    retrieve(), and importing classify_query from P2's context module
    would violate the P2→P3 boundary (it is internal to P2).
    """
    q = query.lower()
    if any(kw in q for kw in ("why", "keeps failing", "root cause")):
        return QueryType.DIAGNOSTIC
    if any(kw in q for kw in ("how do i", "steps to")):
        return QueryType.PROCEDURAL
    if any(kw in q for kw in ("which", "compatible", "compare")):
        return QueryType.OPEN
    if any(kw in q for kw in ("what", "when")):
        return QueryType.FACTUAL
    return QueryType.OPEN

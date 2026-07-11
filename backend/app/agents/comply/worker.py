"""
Compliance worker implementation.
"""

from __future__ import annotations

from typing import AsyncIterator

from backend.app.agents.shared.state import AgentState
from backend.app.agents.shared.streaming import emit_reasoning, emit_error
from backend.app.agents.shared.logging import get_logger, log_error
from backend.app.agents.shared.worker_utils import (
    execute_graph_query_tool,
    extract_context_texts,
    stream_generation_and_citations,
)
from backend.app.agents.comply.prompts import build_comply_messages

logger = get_logger("comply.worker")


async def run(state: AgentState) -> AsyncIterator[str]:
    """
    Execute the Compliance worker logic.
    """
    try:
        yield emit_reasoning("Compliance worker verifying regulations and standards...")

        graph_context_text = ""

        # Tool call: context_graph_query
        # Compliance uses 'shallow' depth by default
        async for event, text in execute_graph_query_tool(state, "shallow", logger):
            if event:
                yield event
            graph_context_text = text

        yield emit_reasoning("Synthesizing information and generating response...")

        context_texts = extract_context_texts(state)
        messages = build_comply_messages(state.query, context_texts, graph_context_text)

        async for event in stream_generation_and_citations(messages, state):
            yield event

    except Exception as exc:
        log_error(logger, str(exc), session_id=state.session_id, exc_info=True)
        yield emit_error(str(exc))

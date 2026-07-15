"""
LangGraph workflow definition for the P3 Agent layer.

Architecture contract:
- Exactly one graph exists.
- The graph begins only after the Copilot determines escalation is required.
- Normal Copilot responses do NOT execute this graph.
- The graph supports Supervisor → {Asset, Diagnose, Compliance}.
- Workers yield SSE events that continue the existing stream IMMEDIATELY (no buffering).

The graph uses a simple two-node topology:
    supervisor_node → worker_node

The supervisor_node performs routing (no retrieval, no LLM generation).
The worker_node dispatches to the appropriate specialist.
"""

from __future__ import annotations

import asyncio
import contextvars
import uuid
from typing import Any, AsyncIterator, Dict, Optional, TypedDict

from langgraph.graph import StateGraph, END

from backend.app.agents.shared.state import (
    AgentState,
    EscalationContext,
    WorkerType,
)
from backend.app.agents.shared.streaming import emit_agent_trigger
from backend.app.agents.shared.logging import get_logger, log_worker_lifecycle
from backend.app.agents.supervisor.router import route
from backend.app.agents.asset.worker import run as run_asset
from backend.app.agents.diagnose.worker import run as run_diagnose
from backend.app.agents.comply.worker import run as run_comply

logger = get_logger("graph.workflow")

# Use a ContextVar to pass the queue directly to nodes without state deepcopy issues
_event_queue_var: contextvars.ContextVar[asyncio.Queue] = contextvars.ContextVar("event_queue")

class GraphState(TypedDict):
    """LangGraph state schema for escalation workflows."""
    escalation_context: EscalationContext
    agent_state: Optional[AgentState]
    worker_type: Optional[WorkerType]


_WORKER_DISPATCH = {
    WorkerType.ASSET: run_asset,
    WorkerType.DIAGNOSE: run_diagnose,
    WorkerType.COMPLIANCE: run_comply,
}


async def _supervisor_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Supervisor node — performs routing only.

    Reads the EscalationContext from state, determines the worker,
    emits agent_trigger, and sets the worker on the AgentState.
    """
    escalation = state["escalation_context"]
    worker_type = await route(escalation)
    queue = _event_queue_var.get()

    job_id = f"j-{uuid.uuid4().hex[:8]}"
    await queue.put(emit_agent_trigger(worker=worker_type.value, job_id=job_id))

    # Build AgentState for the worker
    agent_state = AgentState(
        query=escalation.query,
        session_id=escalation.session_id,
        thread_id=escalation.thread_id,
        focused_tag=escalation.focused_tag,
        worker=worker_type,
        retrieval_context=escalation.retrieval_context,
        citations=escalation.citations,
        conversation=escalation.conversation,
    )
    state["agent_state"] = agent_state
    state["worker_type"] = worker_type
    return state


async def _worker_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Worker node — dispatches to the selected specialist worker.

    Streams all SSE events from the worker directly into the queue.
    """
    agent_state: AgentState = state["agent_state"]
    worker_type: WorkerType = state["worker_type"]
    session_id = agent_state.session_id
    queue = _event_queue_var.get()

    log_worker_lifecycle(logger, "started", worker=worker_type.value, session_id=session_id)

    worker_fn = _WORKER_DISPATCH[worker_type]
    async for event in worker_fn(agent_state):
        await queue.put(event)

    log_worker_lifecycle(logger, "completed", worker=worker_type.value, session_id=session_id)
    return state


def _build_graph() -> StateGraph:
    """
    Build the single LangGraph workflow.

    Topology:
        supervisor → worker → END
    """
    graph = StateGraph(GraphState)
    graph.add_node("supervisor", _supervisor_node)
    graph.add_node("worker", _worker_node)

    graph.set_entry_point("supervisor")
    graph.add_edge("supervisor", "worker")
    graph.add_edge("worker", END)

    return graph


# Compile once at module level
_compiled_graph = _build_graph().compile()


async def run_escalation_graph(escalation: EscalationContext) -> AsyncIterator[str]:
    """
    Execute the LangGraph workflow for an escalated query.

    This is the primary entry point called by the Copilot when escalation
    is required. It yields SSE events that continue the existing stream.

    The graph is invoked asynchronously and events are yielded exactly
    as they are emitted by the workers to preserve true streaming.
    """
    queue: asyncio.Queue = asyncio.Queue()
    _event_queue_var.set(queue)

    initial_state: Dict[str, Any] = {
        "escalation_context": escalation,
        "agent_state": None,
        "worker_type": None,
    }

    async def _execute_graph():
        try:
            await _compiled_graph.ainvoke(initial_state)
        finally:
            await queue.put(None)  # Sentinel value to mark completion

    # Start the graph in the background
    graph_task = asyncio.create_task(_execute_graph())

    # Consume events from the queue and yield them
    while True:
        get_task = asyncio.create_task(queue.get())
        done, pending = await asyncio.wait(
            [get_task, graph_task],
            return_when=asyncio.FIRST_COMPLETED
        )
        
        if get_task in done:
            event = get_task.result()
            if event is None:
                break
            yield event
        else:
            # graph_task finished early (either crashed or exited without putting None)
            get_task.cancel()
            break

    # Ensure any exceptions from the graph execution are surfaced as SSE errors
    # rather than silently breaking the response stream.
    try:
        await graph_task
    except Exception as exc:
        from backend.app.agents.shared.streaming import emit_error as _emit_error
        yield _emit_error(f"Escalation workflow failed: {exc}")

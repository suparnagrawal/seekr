"""
Supervisor — dispatches to specialist workers.

route_escalation: owned by the LangGraph workflow (graph/workflow.py).
run_worker_direct: used by explicit endpoints (POST /asset, /diagnose, /comply)
                   which bypass the Copilot and Supervisor routing.

The Supervisor itself performs no retrieval, prompt construction, or LLM generation.
"""

from __future__ import annotations

from typing import AsyncIterator

from backend.app.agents.shared.state import AgentState, WorkerType
from backend.app.agents.shared.logging import get_logger, log_worker_lifecycle
from backend.app.agents.asset.worker import run as run_asset
from backend.app.agents.diagnose.worker import run as run_diagnose
from backend.app.agents.comply.worker import run as run_comply

logger = get_logger("supervisor")

_WORKER_DISPATCH = {
    WorkerType.ASSET: run_asset,
    WorkerType.DIAGNOSE: run_diagnose,
    WorkerType.COMPLIANCE: run_comply,
}


async def run_worker_direct(state: AgentState) -> AsyncIterator[str]:
    """
    Execute a worker directly from an AgentState.

    Used by POST /asset, POST /diagnose, POST /comply which bypass the
    Copilot and Supervisor and construct AgentState directly from AgentRequest.
    The worker is already identified — no routing is performed here.
    """
    if state.worker is None:
        raise ValueError("AgentState.worker must be set for direct worker execution")

    worker_fn = _WORKER_DISPATCH[state.worker]

    log_worker_lifecycle(
        logger, "started_direct",
        worker=state.worker.value,
        session_id=state.session_id,
    )

    async for event in worker_fn(state):
        yield event

    log_worker_lifecycle(
        logger, "completed_direct",
        worker=state.worker.value,
        session_id=state.session_id,
    )


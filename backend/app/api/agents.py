import uuid

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from backend.app.schemas.agent import AgentRequest
from backend.app.agents.shared.state import AgentState, WorkerType
from backend.app.agents.shared.streaming import emit_done, emit_error
from backend.app.agents.shared.logging import get_logger, log_error
from backend.app.agents.supervisor.supervisor import run_worker_direct

router = APIRouter()
logger = get_logger("api.agents")


async def _run_explicit_worker(worker_type: WorkerType, request: AgentRequest):
    """
    Execute a specialist worker directly for an explicit agent endpoint.

    Bypasses Copilot and Supervisor. Constructs AgentState directly from
    the AgentRequest as specified in the frozen architecture.
    """
    answer_id = f"a-{uuid.uuid4().hex[:8]}"

    try:
        state = AgentState(
            query=request.query,
            session_id=request.session_id,
            thread_id=request.thread_id,
            focused_tag=request.focused_tag,
            worker=worker_type,
        )

        async for event in run_worker_direct(state):
            yield event

        yield emit_done(answer_id)

    except Exception as exc:
        log_error(logger, str(exc), session_id=request.session_id, exc_info=True)
        yield emit_error(str(exc))
        yield emit_done(answer_id)


@router.post("/asset")
async def agent_asset(request: AgentRequest):
    """
    Handle Asset Agent queries via SSE streaming.

    Bypasses Copilot and Supervisor — constructs AgentState directly.
    """
    return StreamingResponse(
        _run_explicit_worker(WorkerType.ASSET, request),
        media_type="text/event-stream",
    )


@router.post("/diagnose")
async def agent_diagnose(request: AgentRequest):
    """
    Handle Diagnose Agent queries via SSE streaming.

    Bypasses Copilot and Supervisor — constructs AgentState directly.
    """
    return StreamingResponse(
        _run_explicit_worker(WorkerType.DIAGNOSE, request),
        media_type="text/event-stream",
    )


@router.post("/comply")
async def agent_comply(request: AgentRequest):
    """
    Handle Comply Agent queries via SSE streaming.

    Bypasses Copilot and Supervisor — constructs AgentState directly.
    """
    return StreamingResponse(
        _run_explicit_worker(WorkerType.COMPLIANCE, request),
        media_type="text/event-stream",
    )


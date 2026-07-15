from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from backend.app.schemas.query import QueryRequest
from backend.app.agents.copilot.orchestrator import run_query

router = APIRouter()


from backend.app.agents.shared.streaming import emit_error, emit_done

async def _safe_sse_wrapper(gen):
    try:
        async for event in gen:
            yield event
    except Exception as exc:
        import uuid
        err_id = f"err-{uuid.uuid4().hex[:8]}"
        yield emit_error(str(exc))
        yield emit_done(err_id)

@router.post("/query")
async def process_query(request: QueryRequest):
    """
    Handle Copilot queries via one-directional SSE streaming.

    Delegates to the P3 Copilot orchestrator which owns retrieval,
    initial reasoning, trigger evaluation, and escalation.
    """
    gen = run_query(
        query=request.query,
        session_id=request.session_id,
        focused_tag=request.focused_tag,
    )
    return StreamingResponse(
        _safe_sse_wrapper(gen),
        media_type="text/event-stream",
    )


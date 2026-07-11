from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from backend.app.schemas.query import QueryRequest
from backend.app.agents.copilot.orchestrator import run_query

router = APIRouter()


@router.post("/query")
async def process_query(request: QueryRequest):
    """
    Handle Copilot queries via one-directional SSE streaming.

    Delegates to the P3 Copilot orchestrator which owns retrieval,
    initial reasoning, trigger evaluation, and escalation.
    """
    return StreamingResponse(
        run_query(
            query=request.query,
            session_id=request.session_id,
            focused_tag=request.focused_tag,
        ),
        media_type="text/event-stream",
    )


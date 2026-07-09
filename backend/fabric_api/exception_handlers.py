import structlog
from fastapi import Request
from fastapi.responses import JSONResponse

from backend.shared.exceptions import (
    SeekrError,
)

logger = structlog.get_logger(__name__)

async def seekr_error_handler(request: Request, exc: SeekrError) -> JSONResponse:
    """
    Catch-all for domain-specific Seekr errors.
    Translates the specific status_code and message to a JSON response.
    """
    logger.warning("Seekr error handled", status_code=exc.status_code, error=exc.message, path=request.url.path)
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.message}
    )

async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Catch-all for unhandled exceptions. Returns 500 without leaking stack traces.
    """
    logger.error("Unhandled exception occurred", error=str(exc), exception_type=type(exc).__name__, path=request.url.path, exc_info=exc)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal Server Error"}
    )

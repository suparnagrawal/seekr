import time
import uuid
import structlog
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

logger = structlog.get_logger(__name__)

class StructlogRequestMiddleware(BaseHTTPMiddleware):
    """
    Middleware to bind a unique request ID to the structlog context and track request timing.
    """
    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        
        # Clear context and bind new variables for this request
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            client_ip=request.client.host if request.client else None
        )
        
        start_time = time.perf_counter()
        
        try:
            response = await call_next(request)
            process_time = time.perf_counter() - start_time
            
            # Attach timing and request_id to response headers
            response.headers["X-Process-Time"] = str(process_time)
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Correlation-ID"] = request_id
            
            structlog.contextvars.bind_contextvars(status_code=response.status_code)
            logger.info("Request processed", duration_sec=round(process_time, 4))
            return response
        except Exception as e:
            process_time = time.perf_counter() - start_time
            structlog.contextvars.bind_contextvars(status_code=500)
            logger.exception("Request failed", duration_sec=round(process_time, 4), error=str(e))
            raise

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
import os
import structlog

from backend.shared.config import settings
from backend.shared.exceptions import SeekrError
from backend.fabric_api.lifespan import lifespan
from backend.fabric_api.middleware import StructlogRequestMiddleware
from backend.fabric_api.exception_handlers import seekr_error_handler, generic_exception_handler
from backend.fabric_api.routes import health, upload, metrics
from backend.shared.constants import API_V1_PREFIX
from backend.shared.security import verify_jwt

logger = structlog.get_logger(__name__)

def create_app() -> FastAPI:
    """
    Application factory for the SEEKR Fabric API.
    """
    app = FastAPI(
        title=settings.PROJECT_NAME,
        version=settings.VERSION,
        lifespan=lifespan,
    )

    # Register Middleware
    app.add_middleware(StructlogRequestMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in settings.CORS_ORIGINS.split(",")],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register Exception Handlers
    app.add_exception_handler(SeekrError, seekr_error_handler)
    app.add_exception_handler(Exception, generic_exception_handler)

    # Health is usually public
    app.include_router(health.router, prefix=API_V1_PREFIX)
    
    # Authentication is now configurable for demos.
    enable_auth = os.getenv("ENABLE_AUTH", "false").lower() == "true"
    auth_deps = [Depends(verify_jwt)] if enable_auth else []
    
    app.include_router(upload.router, prefix=API_V1_PREFIX, dependencies=auth_deps)
    app.include_router(metrics.router, prefix=API_V1_PREFIX, dependencies=auth_deps)
    
    # Include P2/P3 application routers
    from backend.app.api import query, agents, graph
    app.include_router(query.router, prefix=API_V1_PREFIX, tags=["query"], dependencies=auth_deps)
    app.include_router(agents.router, prefix=f"{API_V1_PREFIX}/agents", tags=["agents"], dependencies=auth_deps)
    app.include_router(graph.router, prefix=API_V1_PREFIX, tags=["graph"], dependencies=auth_deps)

    return app

# The ASGI application instance
app = create_app()

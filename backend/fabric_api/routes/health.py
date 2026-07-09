from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import text
from neo4j import Driver
from qdrant_client import QdrantClient
from redis import Redis

import structlog

from backend.shared.database import get_db
from backend.shared.neo4j_client import get_neo4j
from backend.shared.qdrant_client import get_qdrant
from backend.shared.redis_client import get_redis
from backend.shared.config import settings

logger = structlog.get_logger(__name__)
router = APIRouter(tags=["Health"])

class LivenessResponse(BaseModel):
    status: str

class HealthResponse(BaseModel):
    project: str
    version: str
    status: str

class ReadinessServices(BaseModel):
    postgres: str | None = None
    neo4j: str | None = None
    qdrant: str | None = None
    redis: str | None = None

class ReadinessResponse(BaseModel):
    ready: bool
    services: ReadinessServices

@router.get("/live", status_code=200, response_model=LivenessResponse)
async def liveness_probe():
    """
    Liveness probe. Returns 200 OK immediately if the FastAPI process is running.
    """
    return LivenessResponse(status="alive")

@router.get("/health", status_code=200, response_model=HealthResponse)
async def health_check():
    """
    General health check endpoint.
    """
    return HealthResponse(
        project=settings.PROJECT_NAME,
        version=settings.VERSION,
        status="healthy"
    )

@router.get("/ready", response_model=ReadinessResponse)
async def readiness_probe(
    response: Response,
    db: Session = Depends(get_db),
    neo4j: Driver = Depends(get_neo4j),
    qdrant: QdrantClient = Depends(get_qdrant),
    redis: Redis = Depends(get_redis)
):
    """
    Readiness probe. Checks lightweight connectivity to all backing infrastructure.
    """
    services = ReadinessServices()
    ready = True
    
    # Check Postgres
    try:
        db.execute(text("SELECT 1"))
        services.postgres = "ok"
    except Exception as e:
        services.postgres = "error"
        ready = False
        logger.error("Postgres readiness check failed", error=str(e))
        
    # Check Neo4j
    try:
        neo4j.verify_connectivity()
        services.neo4j = "ok"
    except Exception as e:
        services.neo4j = "error"
        ready = False
        logger.error("Neo4j readiness check failed", error=str(e))
        
    # Check Qdrant
    try:
        qdrant.get_collections()
        services.qdrant = "ok"
    except Exception as e:
        services.qdrant = "error"
        ready = False
        logger.error("Qdrant readiness check failed", error=str(e))
        
    # Check Redis
    try:
        redis.ping()
        services.redis = "ok"
    except Exception as e:
        services.redis = "error"
        ready = False
        logger.error("Redis readiness check failed", error=str(e))

    if not ready:
        response.status_code = 503
        
    return ReadinessResponse(ready=ready, services=services)

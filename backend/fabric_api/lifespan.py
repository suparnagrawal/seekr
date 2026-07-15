import structlog
from contextlib import asynccontextmanager
import asyncio
from fastapi import FastAPI

from backend.shared.config import settings
from backend.shared.logging import setup_logging
from backend.shared.database import engine, init_db_pools, close_db_pools
from backend.shared.neo4j_client import neo4j_driver, close_neo4j_async
from backend.shared.qdrant_client import qdrant_client, close_qdrant_async
from backend.shared.redis_client import redis_conn
from backend.fabric_api.dlq_recovery import dlq_recovery_loop

logger = structlog.get_logger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI lifespan context manager for graceful startup and shutdown.
    Replaces deprecated @app.on_event("startup") and @app.on_event("shutdown").
    """
    from backend.shared.http_clients import init_http_client, close_http_client
    
    # Startup Sequence
    await init_http_client()
    setup_logging()
    logger.info("Application starting up...", version=settings.VERSION)
    
    # Ensure UPLOAD_DIR exists
    try:
        settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        logger.info("Upload directory verified", path=str(settings.UPLOAD_DIR))
    except Exception as e:
        logger.error("Failed to create upload directory", error=str(e))
        raise

    async def wait_for_dependency(dependency_func, name: str, max_retries: int = 5, initial_wait: int = 2):
        for attempt in range(1, max_retries + 1):
            try:
                await asyncio.to_thread(dependency_func)
                logger.info(f"{name} is ready.")
                return
            except Exception as e:
                if attempt == max_retries:
                    logger.error(f"Failed to connect to {name}", attempt=attempt, error=type(e).__name__, exc_info=True)
                    raise
                wait_time = initial_wait * (2 ** (attempt - 1))
                logger.warning(f"Waiting for {name}...", attempt=attempt, sleep=f"{wait_time}s", error=type(e).__name__)
                await asyncio.sleep(wait_time)

    from backend.shared.services.qdrant_service import get_qdrant_service
    
    # Verification check with independent retries
    await wait_for_dependency(redis_conn.ping, "Redis")
    await wait_for_dependency(neo4j_driver.verify_connectivity, "Neo4j")
    await wait_for_dependency(get_qdrant_service().bootstrap_collections, "Qdrant")
    
    logger.info("Infrastructure clients verified and ready.")

    await init_db_pools()
    logger.info("Async database pools initialized.")

    # Start DLQ Recovery Daemon
    dlq_task = asyncio.create_task(dlq_recovery_loop())
    
    yield # Yield control to the FastAPI application

    # Shutdown Sequence
    logger.info("Application shutting down. Cancelling background tasks...")
    dlq_task.cancel()
    try:
        await dlq_task
    except asyncio.CancelledError:
        pass
    logger.info("Application shutting down. Closing infrastructure connections...")
    
    try:
        await close_db_pools()
        logger.info("Async database pools closed.")
    except Exception as e:
        logger.error("Error closing async database pools", error=str(e))
        
    try:
        await asyncio.to_thread(neo4j_driver.close)
        logger.info("Neo4j driver closed.")
    except Exception as e:
        logger.error("Error closing Neo4j driver", error=str(e))
        
    try:
        await close_neo4j_async()
        logger.info("Neo4j async driver closed.")
    except Exception as e:
        logger.error("Error closing Neo4j async driver", error=str(e))
        
    try:
        await asyncio.to_thread(redis_conn.close)
        logger.info("Redis connection closed.")
    except Exception as e:
        logger.error("Error closing Redis connection", error=str(e))
        
    try:
        engine.dispose()
        logger.info("PostgreSQL engine disposed.")
    except Exception as e:
        logger.error("Error disposing PostgreSQL engine", error=str(e))
        
    try:
        qdrant_client.close()
        logger.info("Qdrant client closed.")
    except Exception as e:
        logger.error("Error closing Qdrant client", error=str(e))
        
    try:
        await close_qdrant_async()
        logger.info("Qdrant async client closed.")
    except Exception as e:
        logger.error("Error closing Qdrant async client", error=str(e))

    try:
        await close_http_client()
        logger.info("HTTP client closed.")
    except Exception as e:
        logger.error("Error closing HTTP client", error=str(e))

    logger.info("Shutdown sequence complete.")

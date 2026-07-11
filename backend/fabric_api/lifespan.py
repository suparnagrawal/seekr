import structlog
from contextlib import asynccontextmanager
import time
from fastapi import FastAPI

from backend.shared.config import settings
from backend.shared.logging import setup_logging
from backend.shared.database import engine, init_db_pools, close_db_pools
from backend.shared.neo4j_client import neo4j_driver, get_neo4j_async, close_neo4j_async
from backend.shared.qdrant_client import qdrant_client, get_qdrant_async, close_qdrant_async
from backend.shared.redis_client import redis_conn

logger = structlog.get_logger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI lifespan context manager for graceful startup and shutdown.
    Replaces deprecated @app.on_event("startup") and @app.on_event("shutdown").
    """
    # Startup Sequence
    setup_logging()
    logger.info("Application starting up...", version=settings.VERSION)
    
    # Ensure UPLOAD_DIR exists
    try:
        settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        logger.info("Upload directory verified", path=str(settings.UPLOAD_DIR))
    except Exception as e:
        logger.error("Failed to create upload directory", error=str(e))
        raise

    def wait_for_dependency(dependency_func, name: str, max_retries: int = 5, initial_wait: int = 2):
        for attempt in range(1, max_retries + 1):
            try:
                dependency_func()
                logger.info(f"{name} is ready.")
                return
            except Exception as e:
                if attempt == max_retries:
                    logger.error(f"Failed to connect to {name}", attempt=attempt, error=type(e).__name__, exc_info=True)
                    raise
                wait_time = initial_wait * (2 ** (attempt - 1))
                logger.warning(f"Waiting for {name}...", attempt=attempt, sleep=f"{wait_time}s", error=type(e).__name__)
                time.sleep(wait_time)

    from backend.shared.services.qdrant_service import get_qdrant_service
    from backend.shared.services.graph_indexer import get_graph_indexer
    
    # Verification check with independent retries
    wait_for_dependency(redis_conn.ping, "Redis")
    wait_for_dependency(neo4j_driver.verify_connectivity, "Neo4j")
    wait_for_dependency(get_qdrant_service().bootstrap_collections, "Qdrant")
    wait_for_dependency(get_graph_indexer().bootstrap, "Graph Indexer")
    
    logger.info("Infrastructure clients verified and ready.")

    await init_db_pools()
    logger.info("Async database pools initialized.")

    yield # Yield control to the FastAPI application

    # Shutdown Sequence
    logger.info("Application shutting down. Closing infrastructure connections...")
    
    try:
        await close_db_pools()
        logger.info("Async database pools closed.")
    except Exception as e:
        logger.error("Error closing async database pools", error=str(e))
        
    try:
        neo4j_driver.close()
        logger.info("Neo4j driver closed.")
    except Exception as e:
        logger.error("Error closing Neo4j driver", error=str(e))
        
    try:
        await close_neo4j_async()
        logger.info("Neo4j async driver closed.")
    except Exception as e:
        logger.error("Error closing Neo4j async driver", error=str(e))
        
    try:
        redis_conn.close()
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

    logger.info("Shutdown sequence complete.")

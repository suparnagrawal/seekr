from neo4j import GraphDatabase, AsyncGraphDatabase, Driver, AsyncDriver
import structlog
from typing import Generator

from backend.shared.config import settings

logger = structlog.get_logger(__name__)

# --- Sync Neo4j (for RQ) ---
neo4j_driver: Driver = GraphDatabase.driver(
    settings.NEO4J_URI,
    auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
)

def get_neo4j() -> Generator[Driver, None, None]:
    yield neo4j_driver

# --- Async Neo4j (for FastAPI / P2) ---
_neo4j_driver_async: AsyncDriver | None = None

def get_neo4j_async() -> AsyncDriver:
    global _neo4j_driver_async
    if _neo4j_driver_async is None:
        _neo4j_driver_async = AsyncGraphDatabase.driver(
            settings.NEO4J_URI,
            auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
        )
    return _neo4j_driver_async

async def close_neo4j_async():
    global _neo4j_driver_async
    if _neo4j_driver_async is not None:
        await _neo4j_driver_async.close()
        _neo4j_driver_async = None

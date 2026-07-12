from neo4j import GraphDatabase, Driver
import structlog
from typing import Generator

from backend.shared.config import settings

logger = structlog.get_logger(__name__)

neo4j_driver: Driver = GraphDatabase.driver(
    settings.NEO4J_URI,
    auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
)

def get_neo4j() -> Generator[Driver, None, None]:
    """
    Dependency to get the Neo4j driver.
    """
    yield neo4j_driver

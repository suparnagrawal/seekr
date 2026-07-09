from qdrant_client import QdrantClient
import structlog
from typing import Generator

from backend.shared.config import settings

logger = structlog.get_logger(__name__)

qdrant_client = QdrantClient(
    host=settings.QDRANT_HOST,
    port=settings.QDRANT_PORT
)

def get_qdrant() -> Generator[QdrantClient, None, None]:
    """
    Dependency to get the Qdrant client.
    """
    yield qdrant_client

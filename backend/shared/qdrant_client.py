from qdrant_client import QdrantClient, AsyncQdrantClient
import structlog
from typing import Generator

from backend.shared.config import settings

logger = structlog.get_logger(__name__)

# --- Sync Qdrant (for RQ) ---
qdrant_client = QdrantClient(
    host=settings.QDRANT_HOST,
    port=settings.QDRANT_PORT
)

def get_qdrant() -> Generator[QdrantClient, None, None]:
    yield qdrant_client

# --- Async Qdrant (for FastAPI / P2) ---
_qdrant_client_async: AsyncQdrantClient | None = None

def get_qdrant_async() -> AsyncQdrantClient:
    global _qdrant_client_async
    if _qdrant_client_async is None:
        _qdrant_client_async = AsyncQdrantClient(
            url=settings.QDRANT_URL
        )
    return _qdrant_client_async

async def close_qdrant_async():
    global _qdrant_client_async
    if _qdrant_client_async is not None:
        await _qdrant_client_async.close()
        _qdrant_client_async = None

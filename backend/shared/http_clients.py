"""
Shared async HTTP client pool for the SEEKR backend.

Provides a single httpx.AsyncClient instance with connection pooling
for health checks, DLQ recovery, and any other internal HTTP calls.
Lifecycle is managed by the FastAPI lifespan handler.
"""

import httpx
from typing import Optional

_shared_client: Optional[httpx.AsyncClient] = None

async def init_http_client() -> None:
    global _shared_client
    if _shared_client is None:
        _shared_client = httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=10.0))

async def close_http_client() -> None:
    global _shared_client
    if _shared_client is not None:
        await _shared_client.aclose()
        _shared_client = None

def get_http_client() -> httpx.AsyncClient:
    if _shared_client is None:
        raise RuntimeError("HTTP client not initialized. Call init_http_client() first.")
    return _shared_client

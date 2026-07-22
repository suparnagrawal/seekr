"""
Shared async LLM client pool for the SEEKR backend.
Consolidates P2 and P3 client instantiation to manage connection limits.
"""

from typing import Optional, Dict, Tuple
from openai import AsyncOpenAI
import httpx

from backend.shared.config import settings
from backend.shared.constants import NGROK_HEADERS

_client_cache: Dict[Tuple[str, Optional[str]], AsyncOpenAI] = {}

def get_llm_client(api_key: str, base_url: Optional[str] = None) -> AsyncOpenAI:
    """Get or create an AsyncOpenAI client for the given credentials and endpoint."""
    key = (api_key, base_url)
    if key not in _client_cache:
        _client_cache[key] = AsyncOpenAI(
            api_key=api_key or "dummy",
            max_retries=settings.LLM_MAX_RETRIES,
            timeout=httpx.Timeout(settings.LLM_TIMEOUT, connect=60.0),
            default_headers=NGROK_HEADERS,
            **({"base_url": base_url} if base_url else {}),
        )
    return _client_cache[key]

def reset_llm_clients() -> None:
    """Clear cached clients (useful for tests or config reloads)."""
    _client_cache.clear()

async def aclose_llm_clients() -> None:
    """Close every cached client's connection pool and evict it.

    The cache is a process-lifetime singleton, but each cached AsyncOpenAI's
    httpx connection pool binds to whatever asyncio event loop is running the
    first time it's used. Callers that drive a client from a short-lived loop
    (e.g. `asyncio.run(...)` per RQ job) must call this before that loop
    closes, or the pool is left wired to a dead loop: the next job's fresh
    loop reuses the same cached client, httpx can't service it, and calls
    stall through their retry/backoff instead of failing fast - degrading
    every subsequent job on the process instead of just the one that hit it.
    """
    clients = list(_client_cache.values())
    _client_cache.clear()
    for client in clients:
        try:
            await client.close()
        except Exception:
            pass

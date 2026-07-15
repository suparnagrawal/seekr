"""
Shared async LLM client pool for the SEEKR backend.
Consolidates P2 and P3 client instantiation to manage connection limits.
"""

from typing import Optional, Dict, Tuple
from openai import AsyncOpenAI
import httpx

from backend.shared.config import settings

_client_cache: Dict[Tuple[str, Optional[str]], AsyncOpenAI] = {}

def get_llm_client(api_key: str, base_url: Optional[str] = None) -> AsyncOpenAI:
    """Get or create an AsyncOpenAI client for the given credentials and endpoint."""
    key = (api_key, base_url)
    if key not in _client_cache:
        _client_cache[key] = AsyncOpenAI(
            api_key=api_key or "dummy",
            max_retries=settings.LLM_MAX_RETRIES,
            timeout=httpx.Timeout(settings.LLM_TIMEOUT, connect=60.0),
            default_headers={"ngrok-skip-browser-warning": "1"},
            **({"base_url": base_url} if base_url else {}),
        )
    return _client_cache[key]

def reset_llm_clients() -> None:
    """Clear cached clients (useful for tests or config reloads)."""
    _client_cache.clear()

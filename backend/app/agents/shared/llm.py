"""
Shared LLM invocation layer for the P3 Agent layer.

All P3 components call LLMs through this module. It wraps the AsyncOpenAI
client with a streaming-aware interface suitable for the SSE contract.

All LLM configuration (key, base URL, model, timeouts) is sourced from the
single central `settings` object in backend/shared/config.py.
"""

from __future__ import annotations

from typing import AsyncIterator, Dict, List, Optional

import openai
from openai import AsyncOpenAI
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from backend.shared.config import settings


from backend.shared.llm_clients import get_llm_client

def get_client(base_url_override: str | None = None) -> AsyncOpenAI:
    """Return a shared client to maintain connection pools and Keep-Alive."""
    return get_llm_client(
        api_key=settings.llm_api_key,
        base_url=base_url_override or settings.LLM_BASE_URL
    )


async def generate_streaming(
    messages: List[Dict[str, str]],
    *,
    model: Optional[str] = None,
    temperature: float = settings.LLM_TEMPERATURE,
    max_tokens: int = settings.LLM_MAX_TOKENS,
) -> AsyncIterator[str]:
    """
    Stream LLM token chunks as an async iterator of strings.

    Each yielded string is a text delta from the model. The caller is
    responsible for wrapping these into SSE events via shared/streaming.py.

    The initial connection is retried (up to 3 attempts with exponential
    backoff) to survive transient tunnel/network failures. Once the stream
    is established, iteration proceeds without retries.
    """
    client = get_client()

    # Retry the initial connection with exponential backoff
    last_exc: Optional[Exception] = None
    for attempt in range(3):
        try:
            response = await client.chat.completions.create(
                model=model or settings.LLM_MODEL,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
            )
            break
        except (openai.APIConnectionError, openai.APIError, openai.APITimeoutError) as exc:
            last_exc = exc
            if attempt < 2:
                import asyncio
                await asyncio.sleep(2 ** (attempt + 1))
    else:
        raise last_exc  # type: ignore[misc]

    async for chunk in response:
        if not chunk.choices:
            continue
        delta = chunk.choices[0].delta
        
        # Note: Some models (e.g., Fireworks gpt-oss-120b) generate reasoning_content 
        # and do not support disabling it via API parameters (like thinking=false).
        # We explicitly filter it out here by only yielding delta.content to prevent 
        # leaking internal model reasoning to the frontend.
        if delta and delta.content:
            yield delta.content


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=4, max=10),
    retry=retry_if_exception_type((openai.APIConnectionError, openai.RateLimitError, openai.APIError, openai.APITimeoutError)),
    reraise=True
)
async def generate(
    messages: List[Dict[str, str]],
    *,
    model: Optional[str] = None,
    temperature: float = settings.LLM_TEMPERATURE,
    max_tokens: int = 1024,
    response_format: Optional[Dict[str, str]] = None,
    base_url_override: str | None = None,
) -> str:
    """
    Non-streaming LLM call. Returns the complete response text.

    Used by the Supervisor for routing classification and by the Copilot
    for trigger evaluation where streaming is not needed.
    """
    kwargs = {}
    if response_format:
        kwargs["response_format"] = response_format
        
    client = get_client(base_url_override=base_url_override)
    response = await client.chat.completions.create(
        model=model or settings.LLM_MODEL,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        stream=False,
        **kwargs
    )
    
    # Explicitly return only message.content, ignoring message.reasoning_content
    # to maintain strict control over the exposed API surface.
    return response.choices[0].message.content or ""

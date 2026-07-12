"""
Shared LLM invocation layer for the P3 Agent layer.

All P3 components call LLMs through this module. It wraps the AsyncOpenAI
client (already used in P2 for classification) with a streaming-aware
interface suitable for the SSE contract.

Configuration follows the same env-var pattern established in
backend/app/retrieval/context.py.
"""

from __future__ import annotations

import os
from typing import Any, AsyncIterator, Dict, List, Optional

from openai import AsyncOpenAI

LLM_API_KEY = os.getenv("LLM_API_KEY", os.getenv("FAST_MODEL_API_KEY", ""))
LLM_BASE_URL = os.getenv("LLM_BASE_URL", None)
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")

_client = AsyncOpenAI(
    api_key=LLM_API_KEY or "dummy",
    max_retries=3,
    timeout=60.0,
    **({"base_url": LLM_BASE_URL} if LLM_BASE_URL else {}),
)


async def generate_streaming(
    messages: List[Dict[str, str]],
    *,
    model: Optional[str] = None,
    temperature: float = 0.3,
    max_tokens: int = 2048,
) -> AsyncIterator[str]:
    """
    Stream LLM token chunks as an async iterator of strings.

    Each yielded string is a text delta from the model. The caller is
    responsible for wrapping these into SSE events via shared/streaming.py.
    """
    response = await _client.chat.completions.create(
        model=model or LLM_MODEL,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        stream=True,
    )
    async for chunk in response:
        delta = chunk.choices[0].delta if chunk.choices else None
        if delta and delta.content:
            yield delta.content


async def generate(
    messages: List[Dict[str, str]],
    *,
    model: Optional[str] = None,
    temperature: float = 0.3,
    max_tokens: int = 1024,
) -> str:
    """
    Non-streaming LLM call. Returns the complete response text.

    Used by the Supervisor for routing classification and by the Copilot
    for trigger evaluation where streaming is not needed.
    """
    response = await _client.chat.completions.create(
        model=model or LLM_MODEL,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        stream=False,
    )
    return response.choices[0].message.content or ""

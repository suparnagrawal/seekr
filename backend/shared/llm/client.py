import os
from typing import Optional, Dict, Any

from openai import AsyncOpenAI

from backend.shared.config import settings

LLM_API_KEY = os.getenv("LLM_API_KEY", os.getenv("FAST_MODEL_API_KEY", ""))
LLM_BASE_URL = os.getenv("LLM_BASE_URL", None)
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")

_client = AsyncOpenAI(
    api_key=LLM_API_KEY or "dummy",
    max_retries=3,
    timeout=60.0,
    **({"base_url": LLM_BASE_URL} if LLM_BASE_URL else {}),
)

def get_llm_client() -> AsyncOpenAI:
    return _client

def get_default_model() -> str:
    return LLM_MODEL

async def generate_json(
    messages: list[dict[str, str]],
    *,
    model: Optional[str] = None,
    temperature: float = 0.0,
    max_tokens: int = 2048,
) -> str:
    """
    Non-streaming LLM call enforcing JSON output.
    Used by the ingestion pipeline for graph extraction.
    """
    active_model = model or LLM_MODEL
    
    kwargs = {}
    if settings.LLM_SUPPORTS_JSON_MODE:
        kwargs["response_format"] = {"type": "json_object"}
        
    response = await _client.chat.completions.create(
        model=active_model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        stream=False,
        **kwargs
    )
    return response.choices[0].message.content or "{}"

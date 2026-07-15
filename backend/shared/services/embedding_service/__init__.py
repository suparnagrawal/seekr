from functools import lru_cache
from backend.shared.services.embedding_service.provider import EmbeddingProvider
from backend.shared.services.embedding_service.fastembed_provider import FastEmbedProvider
from backend.shared.services.embedding_service.openai_provider import OpenAIEmbeddingProvider
from backend.shared.config import settings
import structlog

logger = structlog.get_logger(__name__)

# Remove lru_cache since we need dynamic instantiation based on endpoint_override
def get_embedding_service(endpoint_override: str | None = None) -> EmbeddingProvider:
    """
    Dependency provider for the embedding service.
    Returns OpenAIEmbeddingProvider if a remote API endpoint is configured,
    otherwise falls back to the local FastEmbed provider.
    """
    target_endpoint = endpoint_override or settings.EMBEDDING_MODEL_ENDPOINT
    
    # 1. Custom Endpoint (Ngrok, vLLM, DeepInfra)
    if target_endpoint and target_endpoint != "http://localhost:11434/v1":
        logger.info("Using remote API for embeddings", endpoint=target_endpoint)
        return OpenAIEmbeddingProvider(
            endpoint=target_endpoint,
            model_name=settings.EMBEDDING_MODEL
        )
        
    # 2. Official OpenAI Fallback (Triggered if the user clears FAST_MODEL to use Official OpenAI natively)
    import os
    api_key = os.getenv("FAST_MODEL_API_KEY", "")
    if not settings.FAST_MODEL and api_key and api_key != "<replace_with_your_api_key>":
        logger.info("Using Official OpenAI for embeddings")
        return OpenAIEmbeddingProvider(
            endpoint="https://api.openai.com/v1",
            model_name="text-embedding-3-small"
        )
        
    # 3. Default Local CPU Fallback
    logger.info("Using local FastEmbed for embeddings", model=settings.EMBEDDING_MODEL)
    return FastEmbedProvider(model_name=settings.EMBEDDING_MODEL)

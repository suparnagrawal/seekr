from functools import lru_cache
from backend.shared.services.embedding_service.provider import EmbeddingProvider
from backend.shared.services.embedding_service.fastembed_provider import FastEmbedProvider
from backend.shared.services.embedding_service.openai_provider import OpenAIEmbeddingProvider
from backend.shared.config import settings
import structlog

logger = structlog.get_logger(__name__)

class FallbackEmbeddingProvider(EmbeddingProvider):
    """Wraps a primary remote provider with a fallback local CPU provider for resilience."""
    def __init__(self, primary: EmbeddingProvider, fallback: EmbeddingProvider):
        self.primary = primary
        self.fallback = fallback
        
    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        try:
            return self.primary.embed_batch(texts)
        except Exception as e:
            logger.warning("primary_embedding_failed_falling_back", error=str(e), batch_size=len(texts))
            return self.fallback.embed_batch(texts)

# Remove lru_cache since we need dynamic instantiation based on endpoint_override
def get_embedding_service(endpoint_override: str | None = None) -> EmbeddingProvider:
    """
    Dependency provider for the embedding service.
    Returns OpenAIEmbeddingProvider if a remote API endpoint is configured,
    and falls back to the local FastEmbed provider for resilience.
    """
    target_endpoint = endpoint_override or settings.EMBEDDING_MODEL_ENDPOINT
    
    local_fallback = FastEmbedProvider(model_name=settings.EMBEDDING_MODEL)
    
    # 1. Custom Endpoint (Ngrok, vLLM, DeepInfra)
    if target_endpoint and target_endpoint != "http://localhost:11434/v1":
        logger.info("Using remote API for embeddings", endpoint=target_endpoint)
        primary = OpenAIEmbeddingProvider(
            endpoint=target_endpoint,
            model_name=settings.EMBEDDING_MODEL
        )
        return FallbackEmbeddingProvider(primary, local_fallback)
        
    # 2. Official OpenAI Fallback (Triggered if the user clears FAST_MODEL to use Official OpenAI natively)
    import os
    api_key = os.getenv("FAST_MODEL_API_KEY", "")
    if not settings.FAST_MODEL and api_key and api_key != "<replace_with_your_api_key>":
        logger.info("Using Official OpenAI for embeddings")
        primary = OpenAIEmbeddingProvider(
            endpoint="https://api.openai.com/v1",
            model_name="text-embedding-3-small"
        )
        return FallbackEmbeddingProvider(primary, local_fallback)
        
    # 3. Default Local CPU Fallback
    logger.info("Using local FastEmbed for embeddings", model=settings.EMBEDDING_MODEL)
    return local_fallback

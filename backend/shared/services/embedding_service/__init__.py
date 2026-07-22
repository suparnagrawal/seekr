from functools import lru_cache
from backend.shared.services.embedding_service.provider import EmbeddingProvider
from backend.shared.services.embedding_service.fastembed_provider import FastEmbedProvider
from backend.shared.services.embedding_service.openai_provider import OpenAIEmbeddingProvider
from backend.shared.config import settings
import structlog

logger = structlog.get_logger(__name__)


class FallbackEmbeddingProvider(EmbeddingProvider):
    """Wraps a primary (remote) embedding provider with a local CPU fallback.

    Any exception raised by the primary provider is caught, logged with a
    structured warning, and the same batch is transparently re-embedded via
    the fallback. This centralises resilience at the provider-factory level
    rather than requiring inline try/excepts in every caller.
    """

    def __init__(self, primary: EmbeddingProvider, fallback: EmbeddingProvider):
        self.primary = primary
        self.fallback = fallback

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        try:
            return self.primary.embed_batch(texts)
        except Exception as e:
            logger.warning(
                "primary_embedding_failed_falling_back",
                error=str(e),
                batch_size=len(texts),
                primary=type(self.primary).__name__,
                fallback=type(self.fallback).__name__,
            )
            return self.fallback.embed_batch(texts)


# Remove lru_cache since we need dynamic instantiation based on endpoint_override
def get_embedding_service(endpoint_override: str | None = None) -> EmbeddingProvider:
    """
    Dependency provider for the embedding service.
    Returns OpenAIEmbeddingProvider if a remote API endpoint is configured,
    otherwise falls back to the local FastEmbed provider.

    Remote providers are automatically wrapped with FallbackEmbeddingProvider
    so that any primary-provider failure transparently falls back to a local
    FastEmbed instance.
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


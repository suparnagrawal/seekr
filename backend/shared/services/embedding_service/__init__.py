from functools import lru_cache
from backend.shared.services.embedding_service.provider import EmbeddingProvider
from backend.shared.services.embedding_service.fastembed_provider import FastEmbedProvider
from backend.shared.config import settings

@lru_cache(maxsize=1)
def get_embedding_service() -> EmbeddingProvider:
    """
    Dependency provider for the embedding service.
    Currently hardcoded to use FastEmbedProvider, but trivially extensible based on config.
    """
    return FastEmbedProvider(model_name=settings.EMBEDDING_MODEL)

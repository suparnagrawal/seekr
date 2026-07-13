import structlog
from backend.shared.services.embedding_service.provider import EmbeddingProvider
from backend.shared.exceptions import InfrastructureError

logger = structlog.get_logger(__name__)

class FastEmbedProvider(EmbeddingProvider):
    """
    Implements EmbeddingProvider using FastEmbed (ONNX-optimized).
    """
    
    def __init__(self, model_name: str = "BAAI/bge-base-en-v1.5"):
        self.model_name = model_name
        self._model = None
        
    def _get_model(self):
        """Lazy load the embedding model to avoid startup penalties for non-embedding workers."""
        if self._model is None:
            try:
                from fastembed import TextEmbedding  # type: ignore
                from backend.shared.config import settings
                logger.info("Initializing FastEmbed model", model_name=self.model_name)
                self._model = TextEmbedding(model_name=self.model_name, cache_dir=settings.FASTEMBED_CACHE_DIR, threads=1)
                logger.info("FastEmbed model initialized successfully")
            except ImportError:
                raise InfrastructureError("fastembed package is not installed.", service="Embedding")
            except Exception as e:
                logger.error("Failed to initialize FastEmbed model", error=str(e), exc_info=True)
                raise InfrastructureError(f"FastEmbed initialization failed: {str(e)}", service="Embedding")
        return self._model
        
    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """
        Embeds a batch of texts using FastEmbed.
        """
        if not texts:
            return []
            
        try:
            model = self._get_model()
            # FastEmbed's embed returns a generator of numpy arrays
            embeddings_generator = model.embed(texts)
            # Convert to standard python floats for JSON/Qdrant compatibility
            return [vec.tolist() for vec in embeddings_generator]
        except Exception as e:
            logger.error("FastEmbed embedding failed", batch_size=len(texts), error=str(e), exc_info=True)
            raise InfrastructureError(f"Embedding generation failed: {str(e)}", service="Embedding")

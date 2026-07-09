from abc import ABC, abstractmethod

class EmbeddingProvider(ABC):
    """
    Abstract base class for all embedding model providers.
    Ensures that Seekr can swap out local models (FastEmbed, SentenceTransformers)
    or managed APIs (OpenAI, Vertex) seamlessly.
    """
    
    @abstractmethod
    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """
        Embeds a batch of texts.
        
        Args:
            texts: List of text strings to embed.
            
        Returns:
            List of dense vectors (list of floats).
        """
        pass

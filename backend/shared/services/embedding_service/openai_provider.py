import structlog
from typing import List
from openai import OpenAI

from backend.shared.services.embedding_service.provider import EmbeddingProvider
from backend.shared.exceptions import InfrastructureError

logger = structlog.get_logger(__name__)

class OpenAIEmbeddingProvider(EmbeddingProvider):
    """
    Implements EmbeddingProvider using the OpenAI API standard.
    This allows Seekr to use vLLM, standard OpenAI, or Ollama for embeddings
    instead of relying on local CPU FastEmbed.
    """
    
    def __init__(self, endpoint: str, model_name: str = "BAAI/bge-base-en-v1.5"):
        self.endpoint = endpoint
        self.model_name = model_name
        
        # Initialize synchronous OpenAI client
        # We use a dummy API key if none is provided, which works for vLLM/Ollama
        import os
        api_key = os.getenv("FAST_MODEL_API_KEY", "dummy")
        
        try:
            self.client = OpenAI(
                base_url=self.endpoint if self.endpoint != "https://api.openai.com/v1" else None,
                api_key=api_key,
                default_headers={"ngrok-skip-browser-warning": "1"}
            )
            logger.info("Initialized OpenAIEmbeddingProvider", endpoint=endpoint, model=model_name)
        except Exception as e:
            logger.error("Failed to initialize OpenAI client for embeddings", error=str(e), exc_info=True)
            raise InfrastructureError(f"OpenAI embedding client initialization failed: {str(e)}", service="Embedding")

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Embeds a batch of texts using the OpenAI-compatible API endpoint.
        """
        if not texts:
            return []
            
        try:
            response = self.client.embeddings.create(
                model=self.model_name,
                input=texts
            )
            
            # The API returns results in order, extract just the float lists
            return [data.embedding for data in response.data]
            
        except Exception as e:
            logger.error("OpenAI API embedding failed", batch_size=len(texts), endpoint=self.endpoint, error=str(e), exc_info=True)
            raise InfrastructureError(f"Remote embedding generation failed: {str(e)}", service="Embedding")

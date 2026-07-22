import structlog
from typing import List

from backend.shared.services.embedding_service.provider import EmbeddingProvider
from backend.shared.exceptions import InfrastructureError
from backend.shared.constants import NGROK_HEADERS
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

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
        import os
        self.api_key = os.getenv("FAST_MODEL_API_KEY", "dummy")
        logger.info("Initialized Remote EmbeddingProvider", endpoint=endpoint, model=model_name)

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
            
        import httpx
        try:
            # Send POST directly, bypassing the OpenAI python client's hidden connection pooling
            # Ensure we append /embeddings if it's the v1 base url
            url = self.endpoint
            if url.endswith("/v1"):
                url = url + "/embeddings"
            elif not url.endswith("/embeddings"):
                url = url.rstrip("/") + "/embeddings"
                
            @retry(
                stop=stop_after_attempt(3),
                wait=wait_exponential(multiplier=2, min=4, max=10),
                retry=retry_if_exception_type((httpx.RequestError, httpx.TimeoutException)),
                reraise=True
            )
            def _do_post():
                resp = httpx.post(
                    url,
                    json={
                        "model": self.model_name,
                        "input": texts
                    },
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                        **NGROK_HEADERS
                    },
                    timeout=120.0 # High timeout per batch
                )
                resp.raise_for_status()
                return resp
                
            response = _do_post()
            data = response.json()
            
            # Extract floats
            return [item["embedding"] for item in data["data"]]
            
        except Exception as e:
            logger.error("Remote API embedding failed", batch_size=len(texts), endpoint=self.endpoint, error=str(e), exc_info=True)
            raise InfrastructureError(f"Remote embedding generation failed: {str(e)}", service="Embedding")

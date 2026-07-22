import uuid
import structlog
from rq import Queue
from backend.shared.rq_policy import get_default_retry
from backend.shared.config import settings

logger = structlog.get_logger(__name__)

class PipelineOrchestrator:
    """
    Mediates job chaining across Seekr pipelines.
    Keeps worker logic decoupled by centralizing enqueue decisions.
    """
    
    def __init__(self, queue: Queue | None = None):
        self._queue = queue
        
    @property
    def queue(self) -> Queue:
        if self._queue is None:
            from backend.shared.redis_client import ingestion_queue
            self._queue = ingestion_queue
        return self._queue
        
    def _enqueue_worker_job(self, function_path: str, job_prefix: str, timeout: int, document_id: str, ml_gateway_url: str | None) -> str:
        job = self.queue.enqueue(
            function_path,
            kwargs={"document_id": document_id, "ml_gateway_url": ml_gateway_url},
            job_id=f"{job_prefix}_{document_id}",
            job_timeout=timeout,
            retry=get_default_retry(),
            result_ttl=86400
        )
        return job.id

    def enqueue_embedding(self, document_id: str | uuid.UUID, ml_gateway_url: str | None = None) -> str:
        """
        Enqueues the embedding generation job.
        
        Args:
            document_id: UUID of the document
            ml_gateway_url: Optional override endpoint
            
        Returns:
            job_id
        """
        document_id = str(document_id)
        
        job_id = self._enqueue_worker_job(
            "backend.ingestion_worker.embedding_jobs.process_embedding_job",
            "embed",
            settings.RQ_EMBED_TIMEOUT,
            document_id,
            ml_gateway_url
        )
        logger.info("Enqueued embedding job via orchestrator", document_id=document_id, job_id=job_id)
        return job_id

    def enqueue_graph(self, document_id: str | uuid.UUID, ml_gateway_url: str | None = None) -> str | None:
        """
        Enqueues the graph extraction job if enabled.
        
        Args:
            document_id: UUID of the document
            ml_gateway_url: Optional override endpoint
            
        Returns:
            job_id if enqueued, None otherwise
        """
        if not settings.GRAPH_EXTRACTION_ENABLED:
            logger.info("Graph extraction is disabled, skipping enqueue", document_id=str(document_id))
            return None
            
        document_id = str(document_id)
        
        try:
            job_id = self._enqueue_worker_job(
                "backend.ingestion_worker.graph_jobs.process_graph_job",
                "graph",
                settings.RQ_GRAPH_TIMEOUT,
                document_id,
                ml_gateway_url
            )
            logger.info("Enqueued graph extraction job via orchestrator", document_id=document_id, job_id=job_id)
            return job_id
        except Exception as e:
            logger.error("Failed to enqueue graph job", document_id=document_id, error=str(e), exc_info=True)
            return None

pipeline_orchestrator = PipelineOrchestrator()

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
        
        job = self.queue.enqueue(
            "backend.fabric_api.dlq_recovery.enqueue_with_retry",
            args=("backend.ingestion_worker.embedding_jobs.generate_embeddings_job",),
            kwargs={"document_id": document_id, "ml_gateway_url": ml_gateway_url},
            job_id=f"embed_{document_id}",
            job_timeout=settings.RQ_EMBED_TIMEOUT,
            retry=get_default_retry(),
            result_ttl=86400
        )
        logger.info("Enqueued embedding job via orchestrator", document_id=document_id, job_id=job.id)
        return job.id

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
            job = self.queue.enqueue(
                "backend.fabric_api.dlq_recovery.enqueue_with_retry",
                args=("backend.ingestion_worker.graph_jobs.process_graph_job",),
                kwargs={"document_id": document_id, "ml_gateway_url": ml_gateway_url},
                job_id=f"graph_{document_id}",
                job_timeout=settings.RQ_GRAPH_TIMEOUT,
                retry=get_default_retry(),
                result_ttl=86400
            )
            logger.info("Enqueued graph extraction job via orchestrator", document_id=document_id, job_id=job.id)
            return job.id
        except Exception as e:
            logger.error("Failed to enqueue graph job", document_id=document_id, error=str(e), exc_info=True)
            return None

pipeline_orchestrator = PipelineOrchestrator()

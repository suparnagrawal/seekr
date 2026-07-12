import structlog
from rq import Queue
from backend.shared.redis_client import get_queue
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
        
    def enqueue_embedding(self, document_id: str) -> str:
        """
        Enqueues the next pipeline stage (P1.5/P1.6: Embedding & Indexing).
        """
        try:
            job = self.queue.enqueue(
                "backend.ingestion_worker.embedding_jobs.process_embedding_job",
                kwargs={"document_id": str(document_id)},
                job_id=f"embed_{document_id}",
                job_timeout=settings.RQ_EMBED_TIMEOUT,
                retry=get_default_retry(),
                result_ttl=86400
            )
            logger.info("Enqueued embedding job via orchestrator", document_id=document_id, job_id=job.id)
            return job.id
        except Exception as e:
            logger.error("Failed to enqueue embedding job", document_id=document_id, error=str(e), exc_info=True)
            raise

pipeline_orchestrator = PipelineOrchestrator()

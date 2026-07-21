import uuid
from fastapi import UploadFile, Depends
from pathlib import Path
from rq import Queue
from rq.job import Job
from rq.exceptions import NoSuchJobError
from rq.command import send_stop_job_command
import structlog

from backend.shared.storage import StorageManager, storage_manager
from backend.shared.repositories.document_repository import DocumentRepository, get_document_repository
from backend.shared.services.cleanup_service import CleanupService, get_cleanup_service
from backend.shared.redis_client import get_queue
from backend.shared.rq_policy import get_default_retry
from backend.shared.config import settings
from backend.shared.exceptions import (
    ValidationFailedError,
    UnsupportedMediaTypeError,
    PayloadTooLargeError,
    DuplicateResourceError,
    InfrastructureError
)

logger = structlog.get_logger(__name__)

# Constants
ALLOWED_MIME_TYPES = ["application/pdf"]
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB

class UploadService:
    """
    Orchestrates the document upload lifecycle: validation, storage, DB insertion, and enqueueing.
    """
    
    def __init__(self, repo: DocumentRepository, storage: StorageManager, queue: Queue, cleanup: CleanupService):
        self.repo = repo
        self.storage = storage
        self.queue = queue
        self.cleanup = cleanup

    def process_upload(self, file: UploadFile, ml_gateway_url: str | None = None) -> tuple[uuid.UUID, str, str]:
        """
        Handles the end-to-end document upload flow:
        1. Persists file to storage
        2. Computes hashes
        3. Creates Postgres record
        4. Enqueues background ingestion job
        
        Returns:
            Tuple of (document_id, job_id, status)
        """
        # 1. Validate MIME type
        if file.content_type not in ALLOWED_MIME_TYPES:
            raise UnsupportedMediaTypeError("Unsupported media type. Only PDF is allowed.")
            
        # 2. Validate File Size
        # Note: UploadFile.size is populated by Starlette but may not be accurate depending 
        # on the proxy/client headers. For production, it's safer to check size during streaming.
        # For MVP, this is acceptable.
        size_bytes = file.size
        
        if size_bytes is None or size_bytes == 0:
            raise ValidationFailedError("Empty file uploaded.")
            
        if size_bytes > MAX_FILE_SIZE:
            raise PayloadTooLargeError(f"Payload too large. Max size is {MAX_FILE_SIZE} bytes.")
            
        # 3. Generate UUID
        document_id = uuid.uuid4()
        
        # 4. Save and hash file simultaneously
        stored_path, sha256 = self.storage.save_and_hash_file(file, document_id)
        
        # 5. Check for duplicates
        existing_doc = self.repo.get_by_sha256(sha256)
        if existing_doc:
            self.storage.delete_document_dir(document_id)
            raise DuplicateResourceError(f"Document with SHA256 {sha256} already exists.")
            
        # 6. Database Insert (Commit as UPLOADED)
        from backend.shared.models.document import DocumentStatus
        from sqlalchemy.exc import IntegrityError
        
        document = self.repo.create(
            id=document_id,
            filename=file.filename or "unknown.pdf",
            stored_filename=f"original{Path(file.filename or '').suffix or '.pdf'}",
            mime_type=file.content_type,
            size_bytes=size_bytes,
            sha256=sha256,
            status=DocumentStatus.UPLOADED.value
        )
        
        try:
            self.repo.db.commit() # Initial create commit is fine in service orchestration
            logger.info("Document saved to Postgres", document_id=str(document_id), status="UPLOADED", sha256=sha256)
        except IntegrityError as e:
            self.repo.db.rollback()
            
            # Check specifically for the sha256 unique constraint
            constraint_name = getattr(getattr(e, 'orig', None), 'diag', None) and getattr(e.orig.diag, 'constraint_name', None)
            pgcode = getattr(getattr(e, 'orig', None), 'pgcode', None)
            
            is_sha256_duplicate = False
            if constraint_name and 'sha256' in constraint_name:
                is_sha256_duplicate = True
            elif pgcode == '23505' and 'sha256' in str(e.orig).lower(): # Fallback if constraint_name isn't available
                is_sha256_duplicate = True
                
            if is_sha256_duplicate:
                logger.warning("Duplicate upload race condition caught", sha256=sha256)
                self.cleanup.cleanup_failed_upload(document_id, "Duplicate SHA256 constraint violation")
                raise DuplicateResourceError(f"Document with SHA256 {sha256} already exists.")
            else:
                logger.error("Database constraint violated during upload", error=str(e), exc_info=True)
                self.cleanup.cleanup_failed_upload(document_id, "Database constraint violation")
                raise InfrastructureError("Database constraint violation.", service="Postgres")
        except Exception as e:
            self.repo.db.rollback()
            logger.error("Failed to commit document to DB, rolled back and delegating to cleanup", error=str(e), exc_info=True)
            self.cleanup.cleanup_failed_upload(document_id, str(e))
            raise InfrastructureError("Database failure during document upload.", service="Postgres")
        
        # 7. Redis Enqueue (Update to QUEUED on success)
        try:
            job_id = self._enqueue_document_job(document_id, stored_path, ml_gateway_url)
            
            self.repo.update_status(document_id, DocumentStatus.QUEUED.value)
            self.repo.db.commit()
            
            import time
            logger.info(
                "Document upload sequence completed successfully", 
                document_id=str(document_id), 
                job_id=job_id, 
                status="QUEUED",
                upload_duration_ms=int(time.time() * 1000), # placeholder for actual duration calculation
                queue_wait_ms=0
            )
            return document.id, job_id, document.status
            
        except Exception as e:
            logger.error(
                "Failed to enqueue background job", 
                document_id=str(document_id), 
                exception_type=type(e).__name__,
                error=str(e),
                exc_info=True
            )
            
            self.cleanup.cleanup_failed_upload(document_id, error_message=str(e))
            raise InfrastructureError(message="Failed to enqueue background job.", service="Redis")

    def retry_upload(self, document_id: str, ml_gateway_url: str | None = None) -> tuple[uuid.UUID, str, str]:
        """
        Retries a failed upload by resetting its state and re-enqueueing the processing job.
        """
        from backend.shared.models.document import DocumentStatus, GraphJobStatus
        
        doc = self.repo.get_by_id(document_id)
        if not doc:
            raise ValidationFailedError("Document not found.")
            
        # Optional: You can choose to allow retry only if the document is in a FAILED state,
        # but for robustness we allow retrying any document that hasn't successfully completed.
        if doc.status == DocumentStatus.COMPLETED.value:
            raise ValidationFailedError("Cannot retry a successfully completed document.")
            
        # Reconstruct the URI properly depending on local vs S3 storage
        stored_path = self.storage.get_artifact_uri(document_id, doc.stored_filename)
        
        try:
            job_id = self._enqueue_document_job(document_id, stored_path, ml_gateway_url)
            
            # Reset document state back to QUEUED
            doc.status = DocumentStatus.QUEUED.value
            doc.graph_job_status = None
            doc.error_message = None
            self.repo.db.commit()
            
            logger.info("Document retry sequence initiated", document_id=str(document_id), job_id=job_id)
            return doc.id, job_id, doc.status
            
        except Exception as e:
            logger.error("Failed to enqueue retry job", document_id=str(document_id), error=str(e), exc_info=True)
            raise InfrastructureError("Failed to enqueue retry job.", service="Redis")

    def cancel_upload(self, document_id: str) -> None:
        """
        Cancels any running or queued jobs for a document and marks it as FAILED.
        """
        from backend.shared.models.document import DocumentStatus
        
        doc = self.repo.get_by_id(document_id)
        if not doc:
            raise ValidationFailedError("Document not found.")
            
        # We allow cancelling if it's not already terminal
        if doc.status in [DocumentStatus.COMPLETED.value, DocumentStatus.FAILED.value]:
            raise ValidationFailedError(f"Cannot cancel document in {doc.status} state.")
            
        job_ids = [
            f"ingest_{document_id}", 
            f"embed_{document_id}", 
            f"graph_{document_id}"
        ]
        
        for jid in job_ids:
            try:
                # 1. Cancel in RQ (prevents it from starting if queued)
                job = Job.fetch(jid, connection=self.queue.connection)
                job.cancel()
                # 2. Stop running job (kills the worker process if it's active)
                try:
                    send_stop_job_command(self.queue.connection, jid)
                except Exception as e:
                    logger.debug("Failed to send stop command", job_id=jid, error=str(e))
            except NoSuchJobError:
                pass
                
        # Update status to FAILED
        self.repo.update_failure(document_id, "Cancelled by user", DocumentStatus.FAILED.value)
        self.repo.db.commit()
        
        logger.info("Document cancellation sequence completed", document_id=str(document_id))

    def _enqueue_document_job(self, document_id: uuid.UUID | str, stored_path: str, ml_gateway_url: str | None = None) -> str:
        """Helper to enqueue the document processing job with uniform retry and timeout policies."""
        job = self.queue.enqueue(
            "backend.ingestion_worker.jobs.process_document_job",
            kwargs={
                "document_id": str(document_id),
                "stored_path": stored_path,
                "ml_gateway_url": ml_gateway_url
            },
            job_id=f"ingest_{document_id}",
            job_timeout=settings.RQ_DOC_PARSE_TIMEOUT,
            retry=get_default_retry(),
            result_ttl=86400
        )
        return job.id

def get_upload_service(
    repo: DocumentRepository = Depends(get_document_repository),
    queue: Queue = Depends(get_queue),
    cleanup: CleanupService = Depends(get_cleanup_service)
) -> UploadService:
    """
    Dependency provider for UploadService.
    StorageManager is used as a singleton module.
    """
    return UploadService(repo, storage_manager, queue, cleanup)

import uuid
from fastapi import UploadFile, Depends
from pathlib import Path
from rq import Queue
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

    def process_upload(self, file: UploadFile) -> tuple[uuid.UUID, str, str]:
        """
        Processes an uploaded file synchronously.
        Returns a tuple of (document_id, job_id, status).
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
            job = self.queue.enqueue(
                "backend.ingestion_worker.jobs.process_document_job",
                kwargs={
                    "document_id": str(document_id),
                    "stored_path": stored_path
                },
                job_id=f"ingest_{document_id}",
                job_timeout=settings.RQ_DOC_PARSE_TIMEOUT,
                retry=get_default_retry(),
                result_ttl=86400 # Keep result for 24h
            )
            
            self.repo.update_status(document_id, DocumentStatus.QUEUED.value)
            self.repo.db.commit()
            
            import time
            logger.info(
                "Document upload sequence completed successfully", 
                document_id=str(document_id), 
                job_id=job.id, 
                status="QUEUED",
                upload_duration_ms=int(time.time() * 1000), # placeholder for actual duration calculation
                queue_wait_ms=0
            )
            return document.id, job.id, document.status
            
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

    def retry_upload(self, document_id: str) -> tuple[uuid.UUID, str, str]:
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
            
        # Reconstruct the S3 URI
        stored_path = f"s3://{self.storage.bucket}/{self.storage.get_object_key(document_id, doc.stored_filename)}"
        
        try:
            job = self.queue.enqueue(
                "backend.ingestion_worker.jobs.process_document_job",
                kwargs={
                    "document_id": str(document_id),
                    "stored_path": stored_path
                },
                job_id=f"ingest_{document_id}",
                job_timeout=settings.RQ_DOC_PARSE_TIMEOUT,
                retry=get_default_retry(),
                result_ttl=86400
            )
            
            # Reset document state back to QUEUED
            doc.status = DocumentStatus.QUEUED.value
            doc.graph_job_status = None
            doc.error_message = None
            self.repo.db.commit()
            
            logger.info("Document retry sequence initiated", document_id=str(document_id), job_id=job.id)
            return doc.id, job.id, doc.status
            
        except Exception as e:
            logger.error("Failed to enqueue retry job", document_id=str(document_id), error=str(e), exc_info=True)
            raise InfrastructureError("Failed to enqueue retry job.", service="Redis")

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

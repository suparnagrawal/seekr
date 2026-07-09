import uuid
import structlog
from fastapi import Depends

from backend.shared.storage import StorageManager, storage_manager
from backend.shared.repositories.document_repository import DocumentRepository, get_document_repository

logger = structlog.get_logger(__name__)

class CleanupService:
    """
    Dedicated service for compensating transactions and cleaning up orphaned infrastructure state.
    Keeps error recovery logic encapsulated away from primary workflow orchestrators.
    """
    def __init__(self, repo: DocumentRepository, storage: StorageManager):
        self.repo = repo
        self.storage = storage

    def cleanup_failed_upload(self, document_id: uuid.UUID | str, error_message: str):
        """
        Cleans up artifacts and database rows for an upload that failed to complete
        its transaction boundaries (e.g. failed to enqueue).
        """
        logger.warning(
            "Executing cleanup for failed upload", 
            document_id=str(document_id), 
            error_message=error_message
        )
        try:
            self.storage.delete_document_dir(document_id)
            self.repo.delete(document_id)
            self.repo.db.commit()
            logger.info("Successfully cleaned up orphaned state", document_id=str(document_id))
        except Exception as e:
            logger.error("Failed to clean up orphaned state", document_id=str(document_id), error=str(e), exc_info=True)
            self.repo.db.rollback()
            
    def cleanup_failed_parse(self, document_id: uuid.UUID | str, error_message: str):
        """Stub: Recovery workflow for parsing failures."""
        pass
        
    def cleanup_failed_embedding(self, document_id: uuid.UUID | str, error_message: str):
        """Stub: Recovery workflow for embedding failures."""
        pass
        
    def cleanup_orphan_artifacts(self):
        """Stub: Cron-like workflow for orphan garbage collection."""
        pass

def get_cleanup_service(
    repo: DocumentRepository = Depends(get_document_repository)
) -> CleanupService:
    return CleanupService(repo, storage_manager)

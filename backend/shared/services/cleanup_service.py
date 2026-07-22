import uuid
import structlog
from fastapi import Depends

from backend.shared.storage import StorageManager, storage_manager
from backend.shared.repositories.document_repository import DocumentRepository, get_document_repository
from backend.shared.neo4j_client import neo4j_driver
from backend.shared.services.qdrant_service import get_qdrant_service

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
        """Future work: Recovery workflow for parsing failures."""
        raise NotImplementedError("Parse failure cleanup is deferred to future milestones.")
        
    def cleanup_failed_embedding(self, document_id: uuid.UUID | str, error_message: str):
        """Future work: Recovery workflow for embedding failures."""
        raise NotImplementedError("Embedding failure cleanup is deferred to future milestones.")
        
    def cleanup_orphan_artifacts(self):
        """Future work: Cron-like workflow for orphan garbage collection."""
        raise NotImplementedError("Global artifact garbage collection is deferred to future milestones.")

    def delete_document(self, document_id: uuid.UUID | str):
        """
        Deletes a document and all its associated data:
        - Postgres metadata row
        - S3/local storage artifacts
        - Qdrant vectors
        - Neo4j graph nodes and edges
        """
        document_id = str(document_id)
        doc = self.repo.get_by_id(document_id)
        if not doc:
            raise ValueError(f"Document {document_id} not found")

        # 1. Update Postgres row to DELETING status first to prevent race conditions
        try:
            self.repo.update_status(document_id, "DELETING")
            self.repo.db.commit()
        except Exception as e:
            logger.error("Failed to mark document as DELETING", document_id=document_id, error=str(e))
            raise Exception("Failed to initiate document deletion")

        # 2. Extract tags for scoped orphan cleanup before deleting relationships
        tags_to_check = []
        try:
            with neo4j_driver.session() as session:
                result = session.run("MATCH (a)-[r {source_doc_id: $doc_id}]-(b) RETURN DISTINCT a.tag AS tag UNION MATCH (a)-[r {source_doc_id: $doc_id}]-(b) RETURN DISTINCT b.tag AS tag", doc_id=document_id)
                tags_to_check = [record["tag"] for record in result]
                
                # Delete relationships created from this document
                session.run("MATCH ()-[r {source_doc_id: $doc_id}]->() DELETE r", doc_id=document_id)
                
                # Cleanup orphan nodes scoped to just the ones that might have been orphaned
                if tags_to_check:
                    session.run("MATCH (n:Entity) WHERE n.tag IN $tags AND NOT (n)--() DELETE n", tags=tags_to_check)
        except Exception as e:
            logger.warning("Failed to delete Neo4j facts", document_id=document_id, error=str(e))

        # 3. Delete Qdrant vectors
        try:
            get_qdrant_service().delete_by_document_id(document_id)
        except Exception as e:
            logger.warning("Failed to delete Qdrant vectors", document_id=document_id, error=str(e))

        # 4. Delete S3/local artifacts
        try:
            self.storage.delete_document_dir(document_id)
        except Exception as e:
            logger.warning("Failed to delete storage artifacts", document_id=document_id, error=str(e))

        # 5. Finally, hard-delete the Postgres row
        try:
            self.repo.delete(document_id)
            self.repo.db.commit()
        except Exception as e:
            self.repo.db.rollback()
            logger.error("Failed to delete document from Postgres", document_id=document_id, error=str(e))
            raise Exception("Failed to delete document metadata")

def get_cleanup_service(
    repo: DocumentRepository = Depends(get_document_repository)
) -> CleanupService:
    return CleanupService(repo, storage_manager)

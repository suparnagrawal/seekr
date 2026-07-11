from fastapi import Depends
from sqlalchemy.orm import Session
import uuid
import structlog

from backend.shared.database import get_db
from backend.shared.models.document import Document

logger = structlog.get_logger(__name__)

class DocumentRepository:
    """
    Handles database operations for the Document model.
    """
    
    def __init__(self, db: Session):
        self.db = db

    def get_by_sha256(self, sha256: str) -> Document | None:
        """
        Retrieves a document by its SHA256 hash.
        """
        return self.db.query(Document).filter(Document.sha256 == sha256).first()

    def create(
        self, 
        id: uuid.UUID,
        filename: str, 
        stored_filename: str, 
        mime_type: str, 
        size_bytes: int, 
        sha256: str, 
        status: str
    ) -> Document:
        """
        Creates a new document record.
        """
        document = Document(
            id=id,
            filename=filename,
            stored_filename=stored_filename,
            mime_type=mime_type,
            size_bytes=size_bytes,
            sha256=sha256,
            status=status
        )
        self.db.add(document)
        # NOTE: We do not commit here. The Service layer is responsible for the transaction boundary.
        return document

    def get_by_id(self, document_id: str | uuid.UUID) -> Document | None:
        if isinstance(document_id, str):
            document_id = uuid.UUID(document_id)
        return self.db.query(Document).filter(Document.id == document_id).first()

    def update_status(self, document_id: str | uuid.UUID, status: str) -> None:
        """Updates just the status of a document."""
        doc = self.get_by_id(document_id)
        if doc:
            doc.status = status

    def update_parsing_results(self, document_id: str | uuid.UUID, parsed_text_path: str, page_count: int, chunk_count: int, status: str) -> None:
        """Updates the parsed text path, page count, chunk count, and status."""
        doc = self.get_by_id(document_id)
        if doc:
            doc.parsed_text_path = parsed_text_path
            doc.page_count = page_count
            doc.chunk_count = chunk_count
            doc.status = status

    def mark_embedding_started(self, document_id: str | uuid.UUID) -> None:
        doc = self.get_by_id(document_id)
        if doc:
            doc.status = "EMBEDDING"
            
    def mark_embedded(self, document_id: str | uuid.UUID, model_name: str, embedded_at) -> None:
        doc = self.get_by_id(document_id)
        if doc:
            doc.embedding_model = model_name
            doc.embedded_at = embedded_at
            if doc.status not in ["COMPLETED", "FAILED"]:
                doc.status = "EMBEDDED"
            if doc.embedded_at is not None and doc.graph_built_at is not None:
                doc.status = "COMPLETED"
            
    def mark_graph_built(self, document_id: str | uuid.UUID, graph_built_at) -> None:
        doc = self.get_by_id(document_id)
        if doc:
            doc.graph_built_at = graph_built_at
            if doc.status not in ["COMPLETED", "FAILED"]:
                doc.status = "GRAPH_BUILT"
            if doc.embedded_at is not None and doc.graph_built_at is not None:
                doc.status = "COMPLETED"
            
    def mark_indexing(self, document_id: str | uuid.UUID) -> None:
        doc = self.get_by_id(document_id)
        if doc:
            doc.status = "INDEXING"
            
    def mark_completed(self, document_id: str | uuid.UUID, embedding_time_ms: int = None, graph_time_ms: int = None) -> None:
        doc = self.get_by_id(document_id)
        if doc:
            doc.status = "COMPLETED"
            if embedding_time_ms is not None:
                doc.embedding_time_ms = embedding_time_ms
            if graph_time_ms is not None:
                doc.graph_time_ms = graph_time_ms

    def update_failure(self, document_id: str | uuid.UUID, error_message: str, status: str = "FAILED") -> None:
        """Records a failure."""
        doc = self.get_by_id(document_id)
        if doc:
            doc.status = status
            doc.error_message = error_message

    def delete(self, document_id: str | uuid.UUID) -> None:
        """Deletes a document from the database."""
        doc = self.get_by_id(document_id)
        if doc:
            self.db.delete(doc)

def get_document_repository(db: Session = Depends(get_db)) -> DocumentRepository:
    """
    Dependency provider for DocumentRepository.
    """
    return DocumentRepository(db)

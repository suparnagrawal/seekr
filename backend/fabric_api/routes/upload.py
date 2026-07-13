from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
import structlog
import uuid
from typing import List
from sqlalchemy.orm import Session

from backend.fabric_api.schemas.upload import UploadResponse, DocumentStatusResponse
from backend.shared.services.upload_service import UploadService, get_upload_service
from backend.shared.database import get_db
from backend.shared.repositories.document_repository import DocumentRepository

logger = structlog.get_logger(__name__)
router = APIRouter(tags=["Ingestion"])

@router.post("/upload", response_model=UploadResponse, status_code=202)
def upload_document(
    file: UploadFile = File(...),
    upload_service: UploadService = Depends(get_upload_service)
):
    """
    Uploads a document, persists it to disk, stores metadata in Postgres,
    and enqueues a background job for ingestion.
    """
    logger.info("Upload request received", filename=file.filename)
    
    document_id, job_id, status = upload_service.process_upload(file)
    
    return UploadResponse(
        document_id=document_id,
        job_id=job_id,
        status=status
    )

@router.post("/retry/{document_id}", response_model=UploadResponse, status_code=202)
def retry_document(
    document_id: str,
    upload_service: UploadService = Depends(get_upload_service)
):
    """
    Retries the ingestion process for a failed document.
    """
    logger.info("Retry request received", document_id=document_id)
    
    doc_id, job_id, status = upload_service.retry_upload(document_id)
    
    return UploadResponse(
        document_id=doc_id,
        job_id=job_id,
        status=status
    )

@router.get("/documents", response_model=List[DocumentStatusResponse])
def list_documents(db: Session = Depends(get_db)):
    """
    Returns a list of all uploaded documents.
    """
    repo = DocumentRepository(db)
    docs = repo.list_all()
    
    return [
        DocumentStatusResponse(
            document_id=doc.id,
            filename=doc.filename,
            overall_status=doc.status,
            graph_job_status=doc.graph_job_status.value if doc.graph_job_status else None,
            error_message=doc.error_message,
            page_count=doc.page_count,
            chunk_count=doc.chunk_count,
            uploaded_at=doc.uploaded_at.isoformat(),
            updated_at=doc.updated_at.isoformat()
        )
        for doc in docs
    ]

@router.get("/status/{document_id}", response_model=DocumentStatusResponse)
def get_document_status(
    document_id: uuid.UUID,
    db: Session = Depends(get_db)
):
    """
    Returns the full lifecycle status of an uploaded document, including
    sub-job statuses for parsing, embedding, and graph extraction.
    """
    repo = DocumentRepository(db)
    doc = repo.get_by_id(str(document_id))
    
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
        
    return DocumentStatusResponse(
        document_id=doc.id,
        filename=doc.filename,
        overall_status=doc.status,
        graph_job_status=doc.graph_job_status.value if doc.graph_job_status else None,
        error_message=doc.error_message,
        page_count=doc.page_count,
        chunk_count=doc.chunk_count,
        uploaded_at=doc.uploaded_at.isoformat(),
        updated_at=doc.updated_at.isoformat()
    )

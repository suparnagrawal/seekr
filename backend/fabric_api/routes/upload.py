from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, Form, Query
import structlog
import uuid
from typing import List
from sqlalchemy.orm import Session
from backend.shared.security import require_role, verify_jwt
from backend.shared.config import settings

from backend.fabric_api.schemas.upload import UploadResponse, DocumentStatusResponse
from backend.shared.services.upload_service import UploadService, get_upload_service
from backend.shared.services.cleanup_service import CleanupService, get_cleanup_service
from backend.shared.database import get_db
from backend.shared.repositories.document_repository import DocumentRepository

logger = structlog.get_logger(__name__)
router = APIRouter(tags=["Ingestion"])

def _to_status_response(doc) -> DocumentStatusResponse:
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

@router.post("/upload", response_model=UploadResponse, status_code=202)
def upload_document(
    file: UploadFile = File(...),
    ml_gateway_url: str | None = Form(None),
    upload_service: UploadService = Depends(get_upload_service)
):
    """
    Uploads a document, persists it to disk, stores metadata in Postgres,
    and enqueues a background job for ingestion.
    """
    logger.info("Upload request received", filename=file.filename, custom_ml_gateway=ml_gateway_url)
    
    document_id, job_id, status = upload_service.process_upload(file, ml_gateway_url=ml_gateway_url)
    
    return UploadResponse(
        document_id=document_id,
        job_id=job_id,
        status=status
    )

@router.post("/retry/{document_id}", response_model=UploadResponse, status_code=202)
def retry_document(
    document_id: str,
    ml_gateway_url: str | None = Query(None),
    claims: dict = Depends(verify_jwt),
    upload_service: UploadService = Depends(get_upload_service)
):
    """
    Retries the ingestion process for a failed document.
    When auth is disabled, the dev fallback user is allowed to retry documents.
    """
    if not settings.auth_enabled:
        user_role = claims.get("role") or claims.get("roles") or claims.get("user_role", "viewer")
        if isinstance(user_role, list):
            if "admin" not in user_role and settings.DEV_FALLBACK_ROLE != "admin":
                raise HTTPException(status_code=403, detail="Forbidden")
        elif user_role != "admin" and settings.DEV_FALLBACK_ROLE != "admin":
            raise HTTPException(status_code=403, detail="Forbidden")

    logger.info("Retry request received", document_id=document_id, custom_ml_gateway=ml_gateway_url)
    
    doc_id, job_id, status = upload_service.retry_upload(document_id, ml_gateway_url=ml_gateway_url)
    
    return UploadResponse(
        document_id=doc_id,
        job_id=job_id,
        status=status
    )

@router.post("/cancel/{document_id}", status_code=204, dependencies=[require_role("admin")])
def cancel_document(
    document_id: str,
    upload_service: UploadService = Depends(get_upload_service)
):
    """
    Cancels any running ingestion jobs for a document and marks it as FAILED.
    """
    logger.info("Cancel request received", document_id=document_id)
    upload_service.cancel_upload(document_id)

@router.get("/documents", response_model=List[DocumentStatusResponse])
def list_documents(db: Session = Depends(get_db)):
    """
    Returns a list of all uploaded documents.
    """
    repo = DocumentRepository(db)
    docs = repo.list_all()
    
    return [_to_status_response(doc) for doc in docs]

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
        
    return _to_status_response(doc)

@router.delete("/documents/{document_id}", status_code=204)
def delete_document(
    document_id: uuid.UUID,
    claims: dict = Depends(verify_jwt),
    cleanup_service: CleanupService = Depends(get_cleanup_service),
):
    """
    Deletes a document and all its associated data.
    When auth is disabled, the dev fallback user is allowed to delete documents.
    """
    if not settings.auth_enabled:
        user_role = claims.get("role") or claims.get("roles") or claims.get("user_role", "viewer")
        if isinstance(user_role, list):
            if "admin" not in user_role and settings.DEV_FALLBACK_ROLE != "admin":
                raise HTTPException(status_code=403, detail="Forbidden")
        elif user_role != "admin" and settings.DEV_FALLBACK_ROLE != "admin":
            raise HTTPException(status_code=403, detail="Forbidden")

    try:
        cleanup_service.delete_document(document_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Document not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

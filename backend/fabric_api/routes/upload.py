from fastapi import APIRouter, UploadFile, File, Depends
import structlog

from backend.fabric_api.schemas.upload import UploadResponse
from backend.shared.services.upload_service import UploadService, get_upload_service

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

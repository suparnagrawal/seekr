from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, Form, Query
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
    upload_service: UploadService = Depends(get_upload_service)
):
    """
    Retries the ingestion process for a failed document.
    """
    logger.info("Retry request received", document_id=document_id, custom_ml_gateway=ml_gateway_url)
    
    doc_id, job_id, status = upload_service.retry_upload(document_id, ml_gateway_url=ml_gateway_url)
    
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

@router.delete("/documents/{document_id}", status_code=204)
def delete_document(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    """
    Deletes a document and all its associated data:
    - Postgres metadata row
    - S3/local storage artifacts
    - Qdrant vectors
    - Neo4j graph nodes and edges
    """
    repo = DocumentRepository(db)
    doc = repo.get_by_id(str(document_id))
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # 1. Update Postgres row to DELETING status first to prevent race conditions
    try:
        repo.update_status(str(document_id), "DELETING")
        db.commit()
    except Exception as e:
        logger.error("Failed to mark document as DELETING", document_id=str(document_id), error=str(e))
        raise HTTPException(status_code=500, detail="Failed to initiate document deletion")

    # 2. Extract tags for scoped orphan cleanup before deleting relationships
    tags_to_check = []
    from backend.shared.neo4j_client import neo4j_driver
    try:
        with neo4j_driver.session() as session:
            result = session.run("MATCH (a)-[r {source_doc_id: $doc_id}]-(b) RETURN DISTINCT a.tag AS tag UNION MATCH (a)-[r {source_doc_id: $doc_id}]-(b) RETURN DISTINCT b.tag AS tag", doc_id=str(document_id))
            tags_to_check = [record["tag"] for record in result]
            
            # Delete relationships created from this document
            session.run("MATCH ()-[r {source_doc_id: $doc_id}]->() DELETE r", doc_id=str(document_id))
            
            # Cleanup orphan nodes scoped to just the ones that might have been orphaned
            if tags_to_check:
                session.run("MATCH (n:Entity) WHERE n.tag IN $tags AND NOT (n)--() DELETE n", tags=tags_to_check)
    except Exception as e:
        logger.warning("Failed to delete Neo4j facts", document_id=str(document_id), error=str(e))

    # 3. Delete Qdrant vectors
    from backend.shared.services.qdrant_service import get_qdrant_service
    try:
        get_qdrant_service().delete_by_document_id(str(document_id))
    except Exception as e:
        logger.warning("Failed to delete Qdrant vectors", document_id=str(document_id), error=str(e))

    # 4. Delete S3/local artifacts
    from backend.shared.storage import storage_manager
    try:
        storage_manager.delete_document_dir(document_id)
    except Exception as e:
        logger.warning("Failed to delete storage artifacts", document_id=str(document_id), error=str(e))

    # 5. Finally, hard-delete the Postgres row
    try:
        repo.delete(str(document_id))
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error("Failed to delete document from Postgres", document_id=str(document_id), error=str(e))
        raise HTTPException(status_code=500, detail="Failed to delete document metadata")

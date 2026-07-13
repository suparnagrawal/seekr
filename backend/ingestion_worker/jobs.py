import structlog
from typing import Any
import json

from backend.shared.database import SessionLocal
from backend.shared.repositories.document_repository import DocumentRepository
from backend.shared.models.document import DocumentStatus
from backend.shared.services.parsing_service import get_parsing_service
from backend.shared.services.chunking_service import get_chunking_service
from backend.shared.storage import storage_manager
from backend.shared.exceptions import IngestionPipelineError

logger = structlog.get_logger(__name__)

def process_document_job(document_id: str, stored_path: str) -> dict[str, Any]:
    """
    Entrypoint for RQ worker.
    Executes the Docling parsing pipeline, runs layout-aware chunking, and persists all artifacts.
    """
    logger.info("Starting document ingestion job", document_id=document_id, stored_path=stored_path)
    
    with SessionLocal() as db:
        repo = DocumentRepository(db)
        parsing_service = get_parsing_service()
        chunking_service = get_chunking_service()
        
        # 1. Fetch document and update to PROCESSING
        doc = repo.get_by_id(document_id)
        if not doc:
            logger.error("Document not found in DB", document_id=document_id)
            raise ValueError(f"Document {document_id} not found")
            
        repo.update_status(document_id, DocumentStatus.PROCESSING.value)
        repo.db.commit()
        logger.info("Document status updated to PROCESSING", document_id=document_id)
        
        try:
            # 2. Execute parsing
            parsed_doc = parsing_service.parse_document(stored_path)
            
            # 3. Save Parsing Artifacts to Disk
            parsed_md_path = storage_manager.save_artifact(document_id, "parsed.md", parsed_doc.markdown)
            storage_manager.save_artifact(document_id, "metadata.json", json.dumps(parsed_doc.metadata, indent=2))
            
            # 4. Execute chunking
            chunks = chunking_service.chunk_document(document_id, parsed_doc)
            
            # Free the massive Docling object early now that chunking is done
            parsed_doc.docling_document = None
            
            # 5. Save Chunking Artifacts to Storage (NDJSON string)
            chunks_str = "".join(json.dumps(chunk) + "\n" for chunk in chunks)
            chunks_uri = storage_manager.save_artifact(document_id, "chunks.jsonl", chunks_str)
            logger.info("Artifact saved to storage", stored_path=chunks_uri)
            
            # 6. Update DB to PARSED (End of ingestion pipeline)
            repo.update_parsing_results(
                document_id=document_id,
                parsed_text_path=parsed_md_path,
                page_count=parsed_doc.page_count,
                chunk_count=len(chunks),
                status=DocumentStatus.PARSED.value
            )
            repo.db.commit()
            
            # 7. Hand off to Orchestrator — fan out embedding + graph extraction
            from backend.ingestion_worker.orchestrator import pipeline_orchestrator
            pipeline_orchestrator.enqueue_embedding(document_id)
            pipeline_orchestrator.enqueue_graph(document_id)
            
            logger.info("Document ingestion pipeline finished successfully, enqueued parallel downstream jobs", document_id=document_id, page_count=parsed_doc.page_count, chunk_count=len(chunks))
            return {
                "status": "success", 
                "document_id": document_id, 
                "page_count": parsed_doc.page_count,
                "chunk_count": len(chunks)
            }
            
        except IngestionPipelineError as e:
            logger.error(
                "Document parsing failed (Domain Error)", 
                document_id=document_id, 
                error=str(e),
                exc_info=True
            )
            repo.update_failure(document_id, error_message=str(e), status=DocumentStatus.FAILED.value)
            repo.db.commit()
            raise e
        except Exception as e:
            logger.error(
                "Document ingestion failed (Unexpected)", 
                document_id=document_id, 
                exception_type=type(e).__name__,
                error=str(e),
                exc_info=True
            )
            repo.update_failure(document_id, error_message=str(e), status=DocumentStatus.FAILED.value)
            repo.db.commit()
            raise IngestionPipelineError(message=f"Unexpected error: {str(e)}", stage="Worker Execution") from e

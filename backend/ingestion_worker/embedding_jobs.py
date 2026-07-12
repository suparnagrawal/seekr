import structlog
import json
import time
from typing import Any
from pathlib import Path
from datetime import datetime, timezone

from backend.shared.database import SessionLocal
from backend.shared.repositories.document_repository import DocumentRepository
from backend.shared.models.document import DocumentStatus
from backend.shared.storage import storage_manager
from backend.shared.exceptions import IngestionPipelineError, InfrastructureError
from backend.shared.services.embedding_service import get_embedding_service
from backend.shared.config import settings
from backend.shared.services.qdrant_service import get_qdrant_service

logger = structlog.get_logger(__name__)

def process_embedding_job(document_id: str) -> dict[str, Any]:
    """
    Entrypoint for P1.5 and P1.6.
    Reads chunks, generates embeddings in-memory via FastEmbed, and directly upserts to Qdrant.
    No intermediate JSON file is created for vectors to optimize I/O and storage.
    """
    logger.info("Starting document embedding & indexing job", document_id=document_id)
    start_time = time.time()
    
    with SessionLocal() as db:
        repo = DocumentRepository(db)
        embedding_service = get_embedding_service()
        qdrant_service = get_qdrant_service()
        
        # 1. Fetch document and mark as EMBEDDING
        doc = repo.get_by_id(document_id)
        if not doc:
            logger.error("Document not found in DB", document_id=document_id)
            raise ValueError(f"Document {document_id} not found")
            
        repo.mark_embedding_started(document_id)
        repo.db.commit()
        
        try:
            # 2. Read chunks.json
            chunks_path = Path(storage_manager.get_document_dir(document_id)) / "chunks.json"
            if not chunks_path.exists():
                raise IngestionPipelineError("chunks.json artifact not found", stage="Embedding")
                
            with chunks_path.open("r", encoding="utf-8") as f:
                chunks = json.load(f)
                
            if not chunks:
                logger.warning("No chunks found in chunks.json", document_id=document_id)
                repo.update_status(document_id, DocumentStatus.COMPLETED.value)
                repo.db.commit()
                return {"status": "success", "message": "No chunks to embed"}
                
            # Populate chunk filename if not present
            for c in chunks:
                if "filename" not in c:
                    c["filename"] = doc.filename
                    
            # 3. Generate Embeddings in Batches
            texts = [chunk["text"] for chunk in chunks]
            embeddings = []
            batch_size = 32
            
            for i in range(0, len(texts), batch_size):
                batch_texts = texts[i:i+batch_size]
                batch_embeddings = embedding_service.embed_batch(batch_texts)
                embeddings.extend(batch_embeddings)
            
            # Transition to EMBEDDED
            repo.mark_embedded(document_id, settings.EMBEDDING_MODEL, datetime.now(timezone.utc))
            repo.db.commit()
            
            # 4. Upsert to Qdrant (INDEXING)
            repo.mark_indexing(document_id)
            repo.db.commit()
            
            qdrant_service.upsert_chunks(
                document_id=document_id,
                chunks=chunks,
                embeddings=embeddings,
                embedding_model=settings.EMBEDDING_MODEL
            )
            
            # Transition to COMPLETED
            time_ms = int((time.time() - start_time) * 1000)
            repo.mark_completed(document_id, time_ms)
            repo.db.commit()
            
            logger.info("Embedding and Indexing completed successfully", document_id=document_id, time_ms=time_ms, count=len(chunks))
            return {
                "status": "success",
                "document_id": document_id,
                "chunk_count": len(chunks),
                "time_ms": time_ms
            }
            
        except InfrastructureError as e:
            repo.update_failure(document_id, error_message=str(e), status=DocumentStatus.FAILED.value)
            repo.db.commit()
            raise e
        except Exception as e:
            logger.error("Embedding job failed", document_id=document_id, error=str(e), exc_info=True)
            repo.update_failure(document_id, error_message=str(e), status=DocumentStatus.FAILED.value)
            repo.db.commit()
            raise IngestionPipelineError(f"Embedding/Indexing failed: {str(e)}", stage="Embedding & Indexing") from e

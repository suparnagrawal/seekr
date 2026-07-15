import structlog
import json
import time
from typing import Any
from pathlib import Path
import os
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

def process_embedding_job(document_id: str, ml_gateway_url: str | None = None) -> dict[str, Any]:
    """
    Entrypoint for P1.5 and P1.6.
    Reads chunks, generates embeddings in-memory via FastEmbed, and directly upserts to Qdrant.
    No intermediate JSON file is created for vectors to optimize I/O and storage.
    """
    logger.info("Starting document embedding & indexing job", document_id=document_id)
    start_time = time.time()
    
    with SessionLocal() as db:
        repo = DocumentRepository(db)
        
        target_embedding_url = settings.EMBEDDING_MODEL_ENDPOINT
        if ml_gateway_url:
            target_embedding_url = ml_gateway_url.rstrip('/') + '/v1'
            
        embedding_service = get_embedding_service(endpoint_override=target_embedding_url)
        qdrant_service = get_qdrant_service()
        
        # 1. Fetch document and mark as EMBEDDING
        doc = repo.get_by_id(document_id)
        if not doc:
            logger.error("Document not found in DB", document_id=document_id)
            raise ValueError(f"Document {document_id} not found")
            
        repo.mark_embedding_started(document_id)
        repo.db.commit()
        
        try:
            # 2. Read chunks.jsonl iteratively from Storage
            artifact_uri = storage_manager.get_artifact_uri(document_id, "chunks.jsonl")
            try:
                temp_chunks_path = storage_manager.download_to_tempfile(artifact_uri)
            except Exception as e:
                raise IngestionPipelineError(
                    f"chunks.jsonl artifact not found or failed to download: {e}",
                    stage="Embedding",
                )

            chunks_path = Path(temp_chunks_path)
            try:
                # 3. Resume / Idempotency Check
                existing_chunk_ids = qdrant_service.get_existing_chunk_ids(document_id)
                if existing_chunk_ids:
                    logger.info("Found existing chunks in Qdrant, resuming job", document_id=document_id, existing_count=len(existing_chunk_ids))
                
                # Resolve docling version once for the entire job
                import importlib.metadata
                try:
                    docling_version = f"docling=={importlib.metadata.version('docling')}"
                except importlib.metadata.PackageNotFoundError:
                    docling_version = "docling==unknown"
                    
                # Mark as indexing immediately since we interleave it
                repo.mark_indexing(document_id)
                repo.db.commit()
                
                total_processed = 0
                total_chunks = 0
                batch_size = 32
                
                with chunks_path.open("r", encoding="utf-8") as f:
                    batch_chunks = []
                    batch_texts = []
                    
                    for line in f:
                        if not line.strip():
                            continue
                        
                        total_chunks += 1
                        c = json.loads(line)
                        
                        # Skip chunks that are already in Qdrant
                        if c["id"] in existing_chunk_ids:
                            continue
                            
                        # Populate chunk filename if not present
                        if "filename" not in c:
                            c["filename"] = doc.filename

                        # Prepend section headings to anchor the paragraph in its
                        # document context.  Without this, orphaned body text like
                        # "This standard is issued under the fixed designation
                        # A106/A106M..." loses its semantic link to "ASTM A106".
                        headings = c.get("headings", [])
                        if headings:
                            heading_prefix = "Section: " + " > ".join(headings)
                            text_to_embed = f"{heading_prefix}\n\n{c['text']}"
                        else:
                            text_to_embed = c["text"]
                            
                        batch_chunks.append(c)
                        batch_texts.append(text_to_embed)
                        
                        # Generate Embeddings and Upsert in Batches
                        if len(batch_chunks) >= batch_size:
                            logger.info("Processing embedding batch", document_id=document_id, batch_size=len(batch_texts))
                            batch_embeddings = embedding_service.embed_batch(batch_texts)
                            
                            # Upsert immediately to save state in Qdrant
                            qdrant_service.upsert_chunks(
                                document_id=document_id,
                                chunks=batch_chunks,
                                embeddings=batch_embeddings,
                                embedding_model=settings.EMBEDDING_MODEL,
                                parser_version=docling_version,
                            )
                            
                            total_processed += len(batch_embeddings)
                            logger.info("Finished embedding and indexing batch", document_id=document_id, current_total=total_processed)
                            
                            # Clear batch memory
                            batch_chunks = []
                            batch_texts = []
                    
                    # 4. Process any remaining chunks in the final batch
                    if batch_chunks:
                        logger.info("Processing final embedding batch", document_id=document_id, batch_size=len(batch_texts))
                        batch_embeddings = embedding_service.embed_batch(batch_texts)
                        
                        qdrant_service.upsert_chunks(
                            document_id=document_id,
                            chunks=batch_chunks,
                            embeddings=batch_embeddings,
                            embedding_model=settings.EMBEDDING_MODEL,
                            parser_version=docling_version,
                        )
                        total_processed += len(batch_embeddings)
                        logger.info("Finished final embedding and indexing batch", document_id=document_id, current_total=total_processed)
                
                if total_processed == 0 and total_chunks == 0:
                    logger.warning("No chunks found in chunks.jsonl", document_id=document_id)
                    repo.update_status(document_id, DocumentStatus.COMPLETED.value)
                    repo.db.commit()
                    return {"status": "success", "message": "No chunks to embed"}
                
                # 5. Transition to EMBEDDED and check state convergence
                time_ms = int((time.time() - start_time) * 1000)
                repo.mark_embedded(document_id, settings.EMBEDDING_MODEL, datetime.now(timezone.utc))
                
                # Save embedding time
                doc = repo.get_by_id(document_id)
                if doc:
                    doc.embedding_time_ms = time_ms
                    
                repo.db.commit()
                
                logger.info("Embedding and Indexing completed successfully", document_id=document_id, time_ms=time_ms, count=total_chunks)
                
                return {
                    "status": "success",
                    "document_id": document_id,
                    "chunk_count": total_chunks,
                    "time_ms": time_ms
                }
            finally:
                if chunks_path.exists():
                    os.remove(chunks_path)
            
        except InfrastructureError as e:
            repo.update_failure(document_id, error_message=str(e), status=DocumentStatus.FAILED.value)
            repo.db.commit()
            raise e
        except Exception as e:
            logger.error("Embedding job failed", document_id=document_id, error=str(e), exc_info=True)
            repo.update_failure(document_id, error_message=str(e), status=DocumentStatus.FAILED.value)
            repo.db.commit()
            raise IngestionPipelineError(f"Embedding/Indexing failed: {str(e)}", stage="Embedding & Indexing") from e

import structlog
import json
import time
import asyncio
from pathlib import Path
from typing import Any
from datetime import datetime, timezone
from pydantic import ValidationError

from backend.shared.database import SessionLocal
from backend.shared.repositories.document_repository import DocumentRepository
from backend.shared.models.document import DocumentStatus
from backend.shared.models.graph import GraphExtractionResult
from backend.shared.storage import storage_manager
from backend.shared.exceptions import IngestionPipelineError, InfrastructureError
from backend.shared.services.graph_indexer import get_graph_indexer
from backend.ingestion_worker.graph_prompts import GRAPH_EXTRACTION_SYSTEM_PROMPT, build_extraction_prompt
from backend.shared.llm.client import generate_json

logger = structlog.get_logger(__name__)

async def _extract_graph_async(chunks: list[dict]) -> dict[str, Any]:
    """
    Asynchronously extracts entities and relationships from chunks using the shared LLM abstraction.
    Groups chunks to fit into the context window.
    """
    # Group all chunk text (in a real scenario, you'd batch this to avoid context limit)
    combined_text = "\n\n".join([c.get("text", "") for c in chunks[:10]]) # Just taking first 10 for safety
    
    prompt = build_extraction_prompt(combined_text)
    messages = [
        {"role": "system", "content": GRAPH_EXTRACTION_SYSTEM_PROMPT},
        {"role": "user", "content": prompt}
    ]
    
    try:
        # Use the shared provider with JSON mode natively
        result_content = await generate_json(messages, temperature=0.0, max_tokens=2048)
        
        if not result_content:
            return {"nodes": [], "edges": []}
            
        # Clean up JSON if LLM wraps in markdown code blocks
        if result_content.startswith("```json"):
            result_content = result_content.strip("`").replace("json\n", "", 1)
            
        graph_data_raw = json.loads(result_content)
        
        # Pydantic Validation
        validated_data = GraphExtractionResult(**graph_data_raw)
        return validated_data.model_dump()
        
    except Exception as e:
        logger.error("LLM Graph Extraction failed validation or generation", error=str(e), exc_info=True)
        raise IngestionPipelineError(f"LLM Graph Extraction failed: {str(e)}", stage="Graph Extraction") from e

def process_graph_job(document_id: str) -> dict[str, Any]:
    """
    Entrypoint for P1: Parallel Graph Extraction.
    Reads chunks.json, extracts entities via the configured LLM, and indexes them into Neo4j.
    """
    logger.info("Starting graph extraction job", document_id=document_id)
    start_time = time.time()
    
    with SessionLocal() as db:
        repo = DocumentRepository(db)
        indexer = get_graph_indexer()
        
        # 1. Fetch document
        doc = repo.get_by_id(document_id)
        if not doc:
            logger.error("Document not found in DB", document_id=document_id)
            raise ValueError(f"Document {document_id} not found")
            
        try:
            # 2. Read chunks.json
            chunks_path = Path(storage_manager.get_document_dir(document_id)) / "chunks.json"
            if not chunks_path.exists():
                raise IngestionPipelineError("chunks.json artifact not found", stage="Graph Extraction")
                
            with chunks_path.open("r", encoding="utf-8") as f:
                chunks = json.load(f)
                
            if not chunks:
                logger.warning("No chunks found for graph extraction", document_id=document_id)
                repo.mark_graph_built(document_id, datetime.now(timezone.utc))
                repo.db.commit()
                return {"status": "success", "message": "No chunks to extract"}
                
            # 3. LLM Extraction
            # We run the async extraction synchronously since RQ jobs are synchronous
            loop = asyncio.get_event_loop()
            graph_data = loop.run_until_complete(_extract_graph_async(chunks))
            
            # 4. Neo4j Indexing
            indexer.index_graph_data(document_id, graph_data)
            
            # 5. Transition to GRAPH_BUILT and try to converge state
            time_ms = int((time.time() - start_time) * 1000)
            repo.mark_graph_built(document_id, datetime.now(timezone.utc))
            
            # Save graph time
            doc = repo.get_by_id(document_id)
            if doc:
                doc.graph_time_ms = time_ms
                
            repo.db.commit()
            
            logger.info("Graph Extraction and Indexing completed successfully", document_id=document_id, time_ms=time_ms)
            return {
                "status": "success",
                "document_id": document_id,
                "time_ms": time_ms
            }
            
        except InfrastructureError as e:
            repo.update_failure(document_id, error_message=str(e), status=DocumentStatus.FAILED.value)
            repo.db.commit()
            raise e
        except Exception as e:
            logger.error("Graph extraction job failed", document_id=document_id, error=str(e), exc_info=True)
            repo.update_failure(document_id, error_message=str(e), status=DocumentStatus.FAILED.value)
            repo.db.commit()
            raise IngestionPipelineError(f"Graph Extraction/Indexing failed: {str(e)}", stage="Graph Extraction & Indexing") from e

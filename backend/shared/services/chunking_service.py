import structlog
import hashlib
from typing import Any
from functools import lru_cache
from docling.chunking import HierarchicalChunker
from backend.shared.services.parsing_service import ParsedDocument
from backend.shared.exceptions import IngestionPipelineError

logger = structlog.get_logger(__name__)

class ChunkingService:
    """
    Consumes a ParsedDocument and segments it using Docling's layout-aware HierarchicalChunker.
    Generates deterministic chunk IDs based on content and hierarchy.
    """
    
    def __init__(self):
        # We can cache or lazily instantiate chunker models here if we switch to 
        # ML-based chunking later. HierarchicalChunker is currently deterministic and light.
        self._chunker = HierarchicalChunker()
        
    def chunk_document(self, document_id: str, parsed_doc: ParsedDocument) -> list[dict[str, Any]]:
        """
        Takes a ParsedDocument, consumes its in-memory DoclingDocument,
        and chunks it hierarchically.
        
        Returns:
            A list of dictionary chunks ready for JSON serialization and later embedding.
        """
        logger.info("Starting hierarchical chunking", document_id=document_id)
        
        docling_doc = parsed_doc.docling_document
        if not docling_doc:
            raise IngestionPipelineError(
                message="Cannot chunk document: missing 'docling_document' in ParsedDocument.",
                stage="Chunking"
            )
            
        try:
            # Execute chunking directly on the in-memory object
            chunks_iter = self._chunker.chunk(docling_doc)
            
            # Map into our artifact schema with deterministic IDs
            artifact_chunks = []
            for index, chunk in enumerate(chunks_iter):
                chunk_text = chunk.text
                chunk_meta = chunk.meta.export_json_dict() if chunk.meta else {}
                
                # Extract structural info for stable hashing
                headings = chunk_meta.get("headings", [])
                heading_path = "/".join(headings) if headings else "root"
                
                # Extract page numbers from doc_items if possible (default to 0)
                page_numbers = []
                for item in chunk_meta.get("doc_items", []):
                    for prov in item.get("prov", []):
                        if "page_no" in prov:
                            page_numbers.append(str(prov["page_no"]))
                page_str = ",".join(sorted(set(page_numbers))) if page_numbers else "0"
                
                # Normalize chunk text for hashing
                import unicodedata
                import re
                normalized_text = unicodedata.normalize("NFKC", chunk_text.strip())
                normalized_text = re.sub(r'\s+', ' ', normalized_text)
                
                # Deterministic ID based on document UUID, heading path, page, and text content
                chunk_hash_input = f"{document_id}_{heading_path}_{page_str}_{normalized_text}".encode("utf-8")
                chunk_id = hashlib.sha256(chunk_hash_input).hexdigest()
                
                # Note: bbox and token_count are placeholders for now, to be filled out later or populated natively if available
                artifact_chunks.append({
                    "id": chunk_id,
                    "text": chunk_text,
                    "headings": headings,
                    "page_numbers": [int(p) for p in page_numbers] if page_numbers else [],
                    "bbox": None,
                    "chunk_index": index,
                    "token_count": len(chunk_text.split()), # Naive token count for now
                    "source_document": document_id
                })
                
            logger.info("Hierarchical chunking completed", document_id=document_id, chunk_count=len(artifact_chunks))
            return artifact_chunks
            
        except Exception as e:
            logger.error(
                "Chunking failed", 
                document_id=document_id, 
                exception_type=type(e).__name__,
                error=str(e),
                exc_info=True
            )
            raise IngestionPipelineError(message=f"Chunking error: {str(e)}", stage="Chunking") from e

# Using an lru_cache-like dependency provider to ensure we don't recreate 
# heavy chunkers for every job in the worker process.

@lru_cache(maxsize=1)
def get_chunking_service() -> ChunkingService:
    """Dependency provider for ChunkingService."""
    return ChunkingService()

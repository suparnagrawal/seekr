import uuid
import structlog
from typing import Any
from functools import lru_cache
from backend.shared.exceptions import InfrastructureError
from backend.shared.config import settings

logger = structlog.get_logger(__name__)

class QdrantService:
    """
    Handles all interactions with Qdrant, abstracting away client specifics,
    payload mappings, and UUID conversions.
    """
    
    def __init__(self, client, collection_name: str = settings.QDRANT_COLLECTION):
        self._client = client
        self.collection_name = collection_name
        
    def _get_client(self):
        """
        Returns the encapsulated Qdrant client.
        """
        if self._client is None:
            raise InfrastructureError("Qdrant client not provided to service.", service="Qdrant")
        return self._client
        
    def bootstrap_collections(self):
        """
        Ensures the collection exists and validates its configuration.
        Should only be called once during application startup.
        """
        client = self._get_client()
        from qdrant_client.http import models
        
        if not client.collection_exists(collection_name=self.collection_name):
            logger.info("Creating Qdrant collection", collection=self.collection_name, dimension=settings.EMBEDDING_DIMENSION)
            client.create_collection(
                collection_name=self.collection_name,
                vectors_config=models.VectorParams(
                    size=settings.EMBEDDING_DIMENSION, 
                    distance=models.Distance.COSINE
                )
            )
        else:
            collection_info = client.get_collection(collection_name=self.collection_name)
            if hasattr(collection_info.config.params, "vectors") and collection_info.config.params.vectors.size != settings.EMBEDDING_DIMENSION:
                raise ValueError(f"Collection {self.collection_name} dimension mismatch. Expected {settings.EMBEDDING_DIMENSION}")
        
    def _convert_id_to_uuid(self, chunk_id: str) -> str:
        """
        Qdrant allows UUID or unsigned integers as point IDs.
        Since Seekr uses SHA256 deterministic hashes, we convert them to UUIDv5
        internally to satisfy Qdrant's schema without polluting our domain model.
        """
        # Using a fixed namespace to ensure stability
        namespace = uuid.UUID(settings.QDRANT_NAMESPACE_UUID)
        return str(uuid.uuid5(namespace, chunk_id))
        
    def get_existing_chunk_ids(self, document_id: str) -> set[str]:
        """
        Retrieves all original chunk_ids that have already been embedded and stored
        in Qdrant for a given document. Used for idempotent job resumption.
        """
        client = self._get_client()
        from qdrant_client.http import models
        
        chunk_ids = set()
        offset = None
        
        try:
            while True:
                records, next_page_offset = client.scroll(
                    collection_name=self.collection_name,
                    scroll_filter=models.Filter(
                        must=[
                            models.FieldCondition(
                                key="document_id",
                                match=models.MatchValue(value=document_id)
                            )
                        ]
                    ),
                    with_payload=["chunk_id"],
                    with_vectors=False,
                    limit=100,
                    offset=offset
                )
                
                for record in records:
                    if record.payload and "chunk_id" in record.payload:
                        chunk_ids.add(record.payload["chunk_id"])
                        
                if next_page_offset is None:
                    break
                offset = next_page_offset
                
            return chunk_ids
        except Exception as e:
            logger.warning("Failed to retrieve existing chunk IDs, assuming none exist", document_id=document_id, error=str(e))
            return set()

    def upsert_chunks(self, document_id: str, chunks: list[dict[str, Any]], embeddings: list[list[float]], embedding_model: str):
        """
        Upserts a batch of chunks and their corresponding embeddings into Qdrant.
        """
        if not chunks or not embeddings:
            return
            
        if len(chunks) != len(embeddings):
            raise ValueError(f"Mismatch: {len(chunks)} chunks vs {len(embeddings)} embeddings")
            
        client = self._get_client()
        from qdrant_client.http import models
        
        points = []
        for chunk, vector in zip(chunks, embeddings):
            qdrant_id = self._convert_id_to_uuid(chunk["id"])
            
            import importlib.metadata
            try:
                docling_version = f"docling=={importlib.metadata.version('docling')}"
            except importlib.metadata.PackageNotFoundError:
                docling_version = "docling==unknown"
                
            payload = {
                "document_id": chunk.get("source_document", document_id),
                "source_document": chunk.get("source_document", document_id),
                "chunk_id": chunk["id"], # Store the canonical SHA256 inside the payload too
                "filename": chunk.get("filename", "unknown"),
                "chunk_index": chunk.get("chunk_index", 0),
                "headings": chunk.get("headings", []),
                "page_numbers": chunk.get("page_numbers", []),
                "token_count": chunk.get("token_count", 0),
                "bbox": chunk.get("bbox", None),
                "parser_version": chunk.get("parser_version", docling_version),
                "embedding_model": embedding_model,
                "content_type": chunk.get("content_type", "text"),
                "text": chunk.get("text", ""), # Crucial for retrieval
                "created_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()
            }
            
            points.append(
                models.PointStruct(
                    id=qdrant_id,
                    vector=vector,
                    payload=payload
                )
            )
            
        try:
            logger.info("Upserting batch to Qdrant", document_id=document_id, count=len(points))
            client.upsert(
                collection_name=self.collection_name,
                points=points
            )
        except Exception as e:
            logger.error("Qdrant upsert failed", document_id=document_id, error=str(e), exc_info=True)
            raise InfrastructureError(f"Failed to upsert to Qdrant: {str(e)}", service="Qdrant")

@lru_cache(maxsize=1)
def get_qdrant_service() -> QdrantService:
    from backend.shared.qdrant_client import qdrant_client
    return QdrantService(client=qdrant_client)

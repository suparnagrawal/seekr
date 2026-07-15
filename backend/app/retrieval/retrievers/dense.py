from typing import List
from backend.app.retrieval.interfaces import BaseRetriever, SearchQuery
from backend.app.retrieval.models import TraversalContext, Chunk
from backend.app.db.queries import qdrant_search

class DenseRetriever(BaseRetriever):
    @property
    def name(self) -> str:
        return "dense"
        
    async def _retrieve_impl(self, query: SearchQuery, context: TraversalContext) -> List[Chunk]:
        # Pure semantic search — no text-match filters. Entity relevance is
        # handled by the graph pathway and the metadata reranker.
        results = await qdrant_search(
            context.query_embedding, 
            top_k=20,
        )
        chunks = []
        for r in results:
            chunks.append(Chunk(
                chunk_id=r["chunk_id"],
                text=r["text"],
                score=r.get("score", 0.8),
                source="vector",
                payload=r["payload"]
            ))
        return chunks

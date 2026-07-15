from typing import List
from backend.app.retrieval.interfaces import BaseRetriever, SearchQuery
from backend.app.retrieval.models import TraversalContext, Chunk
from backend.app.db.queries import qdrant_keyword_search

class LexicalRetriever(BaseRetriever):
    """Retriever backed by Qdrant's full-text index (scroll + MatchText).
    
    Provides exact keyword recall for tags, part numbers, and error codes
    that dense (semantic) retrieval underperforms on. Results are unranked
    by Qdrant's scroll API, so a uniform score is assigned — RRF handles
    rank-based fusion from the position order.
    """
    @property
    def name(self) -> str:
        return "lexical"
        
    async def _retrieve_impl(self, query: SearchQuery, context: TraversalContext) -> List[Chunk]:
        results = await qdrant_keyword_search(query.text, top_k=12)
        chunks = []
        for r in results:
            # Uniform score — Qdrant scroll returns unranked results.
            # RRF fuses by position, so ordering matters but magnitude doesn't.
            chunks.append(Chunk(
                chunk_id=r["chunk_id"],
                text=r["text"],
                score=0.5,
                source="lexical",
                payload=r["payload"]
            ))
        return chunks

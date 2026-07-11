from typing import List
from backend.app.retrieval.interfaces import BaseRetriever, SearchQuery
from backend.app.retrieval.models import TraversalContext, Chunk
from backend.shared.database import pg_pool

class KeywordRetriever(BaseRetriever):
    @property
    def name(self) -> str:
        return "keyword"
        
    async def _retrieve_impl(self, query: SearchQuery, context: TraversalContext) -> List[Chunk]:
        sql = """
            SELECT chunk_id, text, payload 
            FROM chunks 
            WHERE fts @@ plainto_tsquery('english', %s)
            LIMIT 20
        """
        async with pg_pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(sql, (query.text,))
                rows = await cur.fetchall()
                chunks = []
                for row in rows:
                    chunks.append(Chunk(
                        chunk_id=row[0],
                        text=row[1],
                        score=0.8,
                        source="lexical",
                        payload=row[2] or {}
                    ))
                return chunks

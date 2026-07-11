from typing import Any, Dict, List, Tuple
from backend.shared.database import pg_pool
from backend.shared.neo4j_client import get_neo4j_async
from backend.shared.qdrant_client import get_qdrant_async

async def qdrant_search(query_embedding: List[float], top_k: int = 10) -> List[Dict[str, Any]]:
    # Assuming collection name is 'chunks'
    client = get_qdrant_async()
    response = await client.query_points(
        collection_name="seekr_chunks",
        query=query_embedding,
        limit=top_k
    )
    return [
        {
            "chunk_id": str(hit.id),
            "text": hit.payload.get("text", "") if hit.payload else "",
            "payload": hit.payload,
            "score": hit.score
        }
        for hit in response.points
    ]

async def neo4j_neighbors(tag: str) -> List[Tuple[str, str, float]]:
    query = """
    MATCH (start {tag: $tag})-[r]-(neighbor)
    RETURN neighbor.tag AS tag, type(r) AS rel_type, COALESCE(r.confidence, 1.0) AS confidence
    LIMIT 100
    """
    driver = get_neo4j_async()
    async with driver.session() as session:
        result = await session.run(query, tag=tag)
        records = await result.data()
        return [(rec["tag"], rec["rel_type"], rec["confidence"]) for rec in records]

async def pg_facts(doc_ids: List[str]) -> List[Dict[str, Any]]:
    if not doc_ids:
        return []
    query = "SELECT subject_tag, predicate, object_tag FROM facts WHERE source_doc_id = ANY(%s) AND status = 'active'"
    async with pg_pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(query, (doc_ids,))
            rows = await cur.fetchall()
            return [
                {
                    "subject_tag": row[0],
                    "predicate": row[1],
                    "object_tag": row[2]
                }
                for row in rows
            ]

from typing import Any, Dict, List, Tuple
from backend.shared.database import pg_pool
from backend.shared.neo4j_client import get_neo4j_async
from backend.shared.qdrant_client import get_qdrant_async
from backend.shared.config import settings

async def qdrant_search(query_embedding: List[float], top_k: int = 10, filters: List[str] = None) -> List[Dict[str, Any]]:
    # Assuming collection name is 'chunks'
    client = get_qdrant_async()
    from qdrant_client.http import models
    
    query_filter = None
    if filters:
        query_filter = models.Filter(
            should=[
                models.FieldCondition(
                    key="text",
                    match=models.MatchText(text=tag)
                ) for tag in filters
            ]
        )
        
    response = await client.query_points(
        collection_name=settings.QDRANT_COLLECTION,
        query=query_embedding,
        query_filter=query_filter,
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

async def qdrant_keyword_search(query_text: str, top_k: int = 12) -> List[Dict[str, Any]]:
    client = get_qdrant_async()
    from qdrant_client.http import models
    
    records, _ = await client.scroll(
        collection_name=settings.QDRANT_COLLECTION,
        scroll_filter=models.Filter(
            must=[
                models.FieldCondition(
                    key="text",
                    match=models.MatchText(text=query_text)
                )
            ]
        ),
        limit=top_k,
        with_payload=True,
        with_vectors=False
    )
    
    return [
        {
            "chunk_id": str(record.id),
            "text": record.payload.get("text", "") if record.payload else "",
            "payload": record.payload,
            "score": 0.8  # Default score since scroll doesn't rank
        }
        for record in records
    ]

async def neo4j_neighbors(tag: str) -> List[Tuple[str, str, float]]:
    query = """
    MATCH (start:Entity {tag: $tag})-[r]-(neighbor:Entity)
    RETURN neighbor.tag AS tag, type(r) AS rel_type, COALESCE(r.confidence, 1.0) AS confidence
    LIMIT 100
    """
    driver = get_neo4j_async()
    async with driver.session() as session:
        result = await session.run(query, tag=tag)
        records = await result.data()
        return [(rec["tag"], rec["rel_type"], rec["confidence"]) for rec in records]


async def neo4j_bulk_neighbors(
    tags: List[str], per_node_limit: int = 100
) -> Dict[str, List[Tuple[str, str, float]]]:
    """Fetch neighbors for many entities in a single round-trip.

    Replaces the per-node ``neo4j_neighbors`` calls the graph traversal used to
    issue inside its BFS loop (an N+1 pattern: one Neo4j round-trip per visited
    node). Returns a mapping of source tag -> list of (neighbor_tag, rel_type,
    confidence), scoped to ``:Entity`` on both ends.

    Each source tag gets up to ``per_node_limit`` neighbors so that high-degree
    nodes don't starve lower-degree ones.
    """
    if not tags:
        return {}
    query = """
    UNWIND $tags AS t
    MATCH (start:Entity {tag: t})-[r]-(neighbor:Entity)
    WITH t, neighbor.tag AS tag, type(r) AS rel_type,
         COALESCE(r.confidence, 1.0) AS confidence
    RETURN t AS source, tag, rel_type, confidence
    """
    out: Dict[str, List[Tuple[str, str, float]]] = {t: [] for t in tags}
    driver = get_neo4j_async()
    async with driver.session() as session:
        result = await session.run(query, tags=tags)
        records = await result.data()
        for rec in records:
            src = rec["source"]
            bucket = out.setdefault(src, [])
            if len(bucket) < per_node_limit:
                bucket.append((rec["tag"], rec["rel_type"], rec["confidence"]))
    return out

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

async def neo4j_resolve_entities(text: str) -> List[str]:
    """Resolve entities in text by searching Neo4j for tag or name matches."""
    if not text:
        return []
        
    query = """
    MATCH (n:Entity) 
    WHERE toLower($text) CONTAINS toLower(n.tag) OR toLower($text) CONTAINS toLower(n.name) 
    RETURN n.tag LIMIT 10
    """
    
    try:
        driver = get_neo4j_async()
        async with driver.session() as session:
            result = await session.run(query, text=text)
            records = await result.data()
            return [rec["n.tag"] for rec in records if "n.tag" in rec]
    except Exception as e:
        import structlog
        logger = structlog.get_logger(__name__)
        logger.warning("Entity resolution query failed", error=str(e))
        return []

async def neo4j_resolve_entities_batch(texts: List[str]) -> List[str]:
    """Resolve entities for multiple texts in a single Neo4j round-trip."""
    if not texts:
        return []
        
    query = """
    UNWIND $texts AS text
    MATCH (n:Entity) 
    WHERE toLower(text) CONTAINS toLower(n.tag) OR toLower(text) CONTAINS toLower(n.name) 
    RETURN collect(DISTINCT n.tag) AS tags LIMIT 50
    """
    
    try:
        driver = get_neo4j_async()
        async with driver.session() as session:
            result = await session.run(query, texts=texts)
            record = await result.single()
            if record and record["tags"]:
                return record["tags"]
            return []
    except Exception as e:
        import structlog
        logger = structlog.get_logger(__name__)
        logger.warning("Batch entity resolution query failed", error=str(e))
        return []

async def get_redis_session_history(session_id: str, limit: int = 5) -> List[str]:
    """Fetch recent message history from Redis."""
    from backend.shared.redis_client import redis_conn
    import asyncio
    key = f"session:{session_id}:history"
    try:
        messages = await asyncio.to_thread(redis_conn.lrange, key, -limit, -1)
        return [msg.decode('utf-8') for msg in messages if msg]
    except Exception:
        import structlog
        logger = structlog.get_logger(__name__)
        logger.warning(
            "Failed to fetch Redis session history",
            session_id=session_id,
            exc_info=True,
        )
        return []

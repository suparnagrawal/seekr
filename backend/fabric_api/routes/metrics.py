from fastapi import APIRouter
from fastapi.responses import PlainTextResponse
from backend.shared.database import SessionLocal, pg_pool
from backend.shared.neo4j_client import get_neo4j_async
from backend.shared.services.qdrant_service import get_qdrant_service
from backend.shared.config import settings
import asyncio
from prometheus_client import Gauge, generate_latest, CONTENT_TYPE_LATEST

router = APIRouter(tags=["Metrics"])

# Custom Prometheus Metrics
NEO4J_NODES = Gauge("seekr_neo4j_nodes_total", "Total nodes in Neo4j")
NEO4J_EDGES = Gauge("seekr_neo4j_edges_total", "Total edges in Neo4j")
QDRANT_POINTS = Gauge("seekr_qdrant_points_total", "Total points in Qdrant")
POSTGRES_DOCUMENTS = Gauge("seekr_postgres_documents_total", "Total documents in Postgres")
POSTGRES_FACTS = Gauge("seekr_postgres_facts_total", "Total facts in Postgres")

@router.get("/metrics")
async def get_metrics():
    """
    Returns system metrics in Prometheus format for the knowledge graph, vector store, and relational database.
    Required for PS8 operational visibility.
    """
    # Neo4j Metrics
    try:
        neo4j_async = get_neo4j_async()
        async with neo4j_async.session() as session:
            node_result = await session.run("MATCH (n) RETURN count(n) AS cnt")
            node_record = await node_result.single()
            if node_record: NEO4J_NODES.set(node_record["cnt"])
            
            edge_result = await session.run("MATCH ()-[r]->() RETURN count(r) AS cnt")
            edge_record = await edge_result.single()
            if edge_record: NEO4J_EDGES.set(edge_record["cnt"])
    except Exception:
        pass
        
    # Qdrant Metrics
    try:
        def get_qdrant_metrics():
            qdrant = get_qdrant_service()
            return qdrant.client.get_collection(settings.QDRANT_COLLECTION).points_count
            
        points = await asyncio.to_thread(get_qdrant_metrics)
        QDRANT_POINTS.set(points)
    except Exception:
        pass
        
    # Postgres Metrics
    try:
        async with pg_pool.connection() as conn:
            doc_res = await conn.execute("SELECT count(*) FROM documents")
            doc_count = await doc_res.fetchone()
            if doc_count: POSTGRES_DOCUMENTS.set(doc_count[0])
            
            fact_res = await conn.execute("SELECT count(*) FROM facts")
            fact_count = await fact_res.fetchone()
            if fact_count: POSTGRES_FACTS.set(fact_count[0])
    except Exception:
        pass
        
    return PlainTextResponse(generate_latest(), media_type=CONTENT_TYPE_LATEST)

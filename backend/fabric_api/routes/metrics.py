from fastapi import APIRouter
from backend.shared.database import SessionLocal
from backend.shared.neo4j_client import neo4j_driver
from backend.shared.services.qdrant_service import get_qdrant_service
from backend.shared.config import settings

router = APIRouter(tags=["Metrics"])

@router.get("/metrics")
async def get_metrics():
    """
    Returns system metrics for the knowledge graph, vector store, and relational database.
    Required for PS8 operational visibility.
    """
    metrics = {
        "status": "ok",
        "neo4j": {"nodes": 0, "edges": 0},
        "qdrant": {"points": 0},
        "postgres": {"documents": 0, "facts": 0}
    }
    
    # Neo4j Metrics
    try:
        with neo4j_driver.session() as session:
            node_result = session.run("MATCH (n) RETURN count(n) AS cnt")
            metrics["neo4j"]["nodes"] = node_result.single()["cnt"]
            
            edge_result = session.run("MATCH ()-[r]->() RETURN count(r) AS cnt")
            metrics["neo4j"]["edges"] = edge_result.single()["cnt"]
    except Exception:
        metrics["neo4j"] = "unreachable"
        
    # Qdrant Metrics
    try:
        qdrant = get_qdrant_service()
        col_info = qdrant.client.get_collection(settings.QDRANT_COLLECTION)
        metrics["qdrant"]["points"] = col_info.points_count
    except Exception:
        metrics["qdrant"] = "unreachable"
        
    # Postgres Metrics
    try:
        with SessionLocal() as db:
            from sqlalchemy import text
            doc_res = db.execute(text("SELECT count(*) FROM documents"))
            metrics["postgres"]["documents"] = doc_res.scalar()
            
            fact_res = db.execute(text("SELECT count(*) FROM facts"))
            metrics["postgres"]["facts"] = fact_res.scalar()
    except Exception:
        metrics["postgres"] = "unreachable"
        
    return metrics

import asyncio
import os
import sys

# Ensure backend can be imported
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.shared.config import settings
from backend.shared.database import engine, Base
from backend.shared.redis_client import redis_conn
from backend.shared.neo4j_client import neo4j_driver
from backend.shared.qdrant_client import qdrant_client
from qdrant_client.http.models import Distance, VectorParams
from backend.shared.models.document import Document
from backend.shared.models.fact import Fact
from backend.shared.models.entity import EntityRegistry, EntityAlias
from sqlalchemy import text

def reset_postgres():
    print("Resetting PostgreSQL database...")
    # Drop all tables and recreate them
    Base.metadata.drop_all(bind=engine)
    print("Dropped PostgreSQL tables.")
    Base.metadata.create_all(bind=engine)
    print("Recreated PostgreSQL tables.")

def reset_redis():
    print("Flushing Redis...")
    redis_conn.flushall()
    print("Redis flushed successfully.")

def reset_neo4j():
    print("Resetting Neo4j graph...")
    def _delete_all(tx):
        tx.run("MATCH (n) DETACH DELETE n")
    
    with neo4j_driver.session() as session:
        session.execute_write(_delete_all)
    print("Neo4j graph cleared.")

def reset_qdrant():
    print("Resetting Qdrant collection...")
    try:
        qdrant_client.delete_collection(collection_name=settings.QDRANT_COLLECTION)
        print(f"Deleted Qdrant collection: {settings.QDRANT_COLLECTION}")
    except Exception as e:
        print(f"Collection {settings.QDRANT_COLLECTION} may not exist: {e}")
        
    print(f"Creating Qdrant collection: {settings.QDRANT_COLLECTION}...")
    qdrant_client.create_collection(
        collection_name=settings.QDRANT_COLLECTION,
        vectors_config=VectorParams(size=settings.EMBEDDING_DIMENSION, distance=Distance.COSINE),
    )
    print("Qdrant collection created.")

if __name__ == "__main__":
    print("Starting full database reset...")
    reset_redis()
    reset_neo4j()
    reset_qdrant()
    # Postgres is reset last
    reset_postgres()
    print("All databases have been successfully cleared and initialized!")

import os
from qdrant_client import AsyncQdrantClient
from neo4j import AsyncGraphDatabase
from psycopg_pool import AsyncConnectionPool

QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://seekr:seekr@localhost:5432/seekr")

qdrant_client = AsyncQdrantClient(url=QDRANT_URL)
neo4j_driver = AsyncGraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
pg_pool = AsyncConnectionPool(DATABASE_URL, open=False)

async def init_db_pools():
    await pg_pool.open()

async def close_db_pools():
    await pg_pool.close()
    await neo4j_driver.close()
    await qdrant_client.close()

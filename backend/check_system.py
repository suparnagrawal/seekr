import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from backend.shared.qdrant_client import qdrant_client
from backend.shared.neo4j_client import neo4j_driver
from backend.shared.config import settings
from backend.shared.redis_client import redis_conn
from rq import Queue


print("--- QDRANT ---")
try:
    count = qdrant_client.count(settings.QDRANT_COLLECTION)
    print(f"Chunks in Qdrant: {count.count}")
except Exception as e:
    print(f"Qdrant error: {e}")

print("--- NEO4J ---")
try:
    with neo4j_driver.session() as session:
        result = session.run("MATCH (n) RETURN count(n) as c")
        print(f"Nodes in Neo4j: {result.single()['c']}")
except Exception as e:
    print(f"Neo4j error: {e}")

print("--- REDIS / RQ ---")
try:
    from backend.shared.constants import INGESTION_QUEUE_NAME
    queue = Queue(INGESTION_QUEUE_NAME, connection=redis_conn)
    failed_queue = Queue("failed", connection=redis_conn)
    print(f"Jobs in ingestion queue: {len(queue)}")
    print(f"Jobs in failed queue: {len(failed_queue)}")
    
    if len(failed_queue) > 0:
        job = failed_queue.jobs[0]
        print(f"\nFailed Job {job.id} ({job.func_name}):")
        print(job.exc_info)
except Exception as e:
    print(f"Redis error: {e}")

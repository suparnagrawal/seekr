
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
from rq import Queue
from backend.shared.models.document import Document  # noqa: F401


def reset_postgres():
    print("Resetting PostgreSQL database...")
    import subprocess
    import os
    
    backend_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Downgrade all migrations to drop tables cleanly
    print("Downgrading all Alembic migrations...")
    subprocess.run(["alembic", "downgrade", "base"], cwd=backend_dir, check=True)
    print("Dropped PostgreSQL tables.")
    
    # Recreate using Alembic migrations
    # This ensures the alembic_version table is correctly initialized
    print("Recreating PostgreSQL tables via Alembic...")
    
    # Run alembic upgrade head in the backend directory
    subprocess.run(["alembic", "upgrade", "head"], cwd=backend_dir, check=True)
    print("Recreated PostgreSQL tables.")


def reset_redis():
    print("Flushing Redis and clearing queues...")
    try:
        # Explicitly empty the queue so workers stop grabbing jobs
        q = Queue('ingestion_queue', connection=redis_conn)
        q.empty()
        
        # Clear RQ registries (failed, started, etc)
        from rq.registry import FailedJobRegistry, StartedJobRegistry
        FailedJobRegistry(queue=q).cleanup()
        StartedJobRegistry(queue=q).cleanup()
    except Exception as e:
        print(f"Queue cleanup error: {e}")
        
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

def reset_storage():
    print("Resetting remote S3 artifact storage...")
    try:
        from backend.shared.storage import storage_manager
        
        paginator = storage_manager.s3_client.get_paginator('list_objects_v2')
        for page in paginator.paginate(Bucket=storage_manager.bucket):
            if 'Contents' in page:
                for obj in page['Contents']:
                    storage_manager.s3_client.delete_object(
                        Bucket=storage_manager.bucket,
                        Key=obj['Key']
                    )
        print("S3 artifact storage cleared.")
    except Exception as e:
        print(f"Failed to clear S3 storage: {e}")

def _guard() -> None:
    """Refuse to run destructively unless the caller has clearly opted in.

    This script drops all Postgres tables, deletes every Neo4j node, deletes the
    Qdrant collection, flushes Redis, and wipes local artifact storage. That is
    unrecoverable against a shared or production-adjacent database. Require an
    explicit opt-in (``--force`` / ``SEEKR_RESET_CONFIRM=YES``) and, when the
    target looks production-like, an interactive typed confirmation.
    """
    import argparse

    parser = argparse.ArgumentParser(description="Destructively reset all SEEKR datastores.")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Proceed without the interactive confirmation prompt.",
    )
    args = parser.parse_args()

    target = settings.postgres_dsn
    
    from urllib.parse import urlparse
    parsed = urlparse(target)
    safe_target = f"{parsed.hostname}{':' + str(parsed.port) if parsed.port else ''}{parsed.path}"
    
    print("!!! DESTRUCTIVE OPERATION !!!")
    print("This will PERMANENTLY delete ALL data in:")
    print(f"  Postgres : {safe_target}")
    print(f"  Neo4j    : {settings.NEO4J_URI}")
    print(f"  Qdrant   : {settings.QDRANT_URL}/{settings.QDRANT_COLLECTION}")
    
    redis_parsed = urlparse(settings.redis_url)
    safe_redis = f"{redis_parsed.hostname}{':' + str(redis_parsed.port) if redis_parsed.port else ''}"
    print(f"  Redis    : {safe_redis}")
    
    print(f"  Storage  : s3://{settings.S3_BUCKET_NAME}")

    # Heuristic production guard: refuse outright on obviously non-local targets
    # unless explicitly forced AND confirmed.
    lowered = target.lower()
    looks_remote = not any(h in lowered for h in ("localhost", "127.0.0.1", "::1"))
    if looks_remote:
        print("\nWARNING: the Postgres target does not look local (possible shared/production DB).")

    forced = args.force or os.getenv("SEEKR_RESET_CONFIRM") == "YES"
    if not forced:
        print("\nRefusing to run without confirmation.")
        print("Re-run with --force, or set SEEKR_RESET_CONFIRM=YES, to proceed.")
        sys.exit(1)

    # If the user explicitly passed SEEKR_RESET_CONFIRM=YES, completely bypass the prompt.
    # Otherwise, even with --force, a remote target on a TTY requires typed confirmation.
    if looks_remote and sys.stdin.isatty() and os.getenv("SEEKR_RESET_CONFIRM") != "YES":
        answer = input('\nType "RESET" to confirm destruction of the target above: ').strip()
        if answer != "RESET":
            print("Confirmation not received. Aborting.")
            sys.exit(1)


if __name__ == "__main__":
    _guard()
    print("Starting full database reset...")
    reset_redis()
    reset_neo4j()
    reset_qdrant()
    reset_storage()
    # Postgres is reset last
    reset_postgres()
    print("All databases and storage have been successfully cleared and initialized!")

import signal
import sys
import time
import structlog
from rq import SimpleWorker
from rq.worker_registration import clean_worker_registry

from backend.shared.config import settings
from backend.shared.logging import setup_logging
from backend.shared.redis_client import redis_conn, ingestion_queue
from backend.shared.constants import INGESTION_QUEUE_NAME

# Stable, deterministic worker identity. A fixed name means the RQ registry
# holds at most ONE entry for this consumer instead of a fresh pid-named entry
# per restart, and RQ itself refuses to register a second live worker under it.
# This is the guard against duplicate concurrent consumers (e.g. deploy overlap)
# that would over-subscribe a free-tier Render instance.
WORKER_NAME = "seekr-ingestion-worker"
# How long to wait for a pre-existing live worker (deploy overlap) to exit
# before retrying, rather than running a second consumer or crash-stranding.
_DUP_RETRY_SECONDS = 15
from backend.shared.database import engine
from backend.shared.neo4j_client import neo4j_driver
from backend.shared.qdrant_client import qdrant_client

logger = structlog.get_logger(__name__)

def cleanup():
    """
    Close all infrastructure connections gracefully.
    """
    try:
        neo4j_driver.close()
        redis_conn.close()
        engine.dispose()
        qdrant_client.close()
        logger.info("Infrastructure connections closed successfully.")
    except Exception as e:
        logger.error("Error during shutdown cleanup", error=str(e))

def shutdown_handler(signum, frame):
    """
    Handle graceful shutdown on SIGINT/SIGTERM.
    """
    logger.info("Shutdown signal received. Initiating graceful shutdown...", signal=signum)
    cleanup()
    sys.exit(0)

def main():
    """
    Bootstrap the ingestion worker.
    """
    setup_logging()
    logger.info("Starting SEEKR Ingestion Worker...", version=settings.VERSION)
    
    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)
    
    try:
        # Verify redis connection is active before starting
        redis_conn.ping()
        logger.info("Connected to Redis successfully.")
        
        # Removed dummy HTTP server: In a unified Render Web Service, FastAPI 
        # already binds to $PORT. Binding here again causes Address Already In Use.

        # Prune worker registrations whose heartbeat has expired (crashed /
        # OOM-killed / previous deploy). Without this, dead workers linger in
        # Redis and show up as phantom concurrent consumers.
        try:
            clean_worker_registry(ingestion_queue)
        except Exception as e:
            logger.warning("Worker registry cleanup skipped", error=str(e))

        # Initialize and run the RQ Worker under a fixed name so only ONE live
        # consumer can exist. If another live worker already holds the name
        # (deploy overlap), RQ raises on registration — wait for it to exit and
        # retry rather than starting a duplicate or dying and stranding the queue.
        while True:
            worker = SimpleWorker(
                [INGESTION_QUEUE_NAME],
                connection=redis_conn,
                name=WORKER_NAME,
                log_job_description=False  # Handled by structlog
            )
            try:
                logger.info("Worker is ready and listening for jobs.", queue=INGESTION_QUEUE_NAME, name=WORKER_NAME)
                worker.work(with_scheduler=False)  # Scheduler not needed for P1
                break
            except ValueError as e:
                # RQ signals a name collision with a still-live worker this way.
                if "already" in str(e).lower():
                    logger.warning(
                        "Another live worker holds this name; not starting a duplicate. Retrying after it exits.",
                        name=WORKER_NAME, sleep=f"{_DUP_RETRY_SECONDS}s"
                    )
                    time.sleep(_DUP_RETRY_SECONDS)
                    try:
                        clean_worker_registry(ingestion_queue)
                    except Exception:
                        pass
                    continue
                raise
        
    except Exception as e:
        logger.error("Worker failed to start or crashed", error=str(e))
        sys.exit(1)

if __name__ == "__main__":
    main()

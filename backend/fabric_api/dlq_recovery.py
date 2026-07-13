import asyncio
import httpx
import structlog
from rq.registry import FailedJobRegistry

from backend.shared.config import settings
from backend.shared.redis_client import ingestion_queue

logger = structlog.get_logger(__name__)

async def dlq_recovery_loop():
    """
    Background daemon that periodically checks if the external ML Gateway is healthy.
    If it is, it pulls all failed jobs from the RQ Dead Letter Queue (FailedJobRegistry)
    and requeues them automatically.
    """
    if not settings.LLM_BASE_URL:
        logger.info("DLQ Recovery Daemon disabled: LLM_BASE_URL is not set.")
        return

    logger.info("DLQ Auto-Recovery Daemon started", check_interval_sec=60)
    
    registry = FailedJobRegistry(queue=ingestion_queue)
    
    while True:
        try:
            # 1. Ping the external gateway
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.get(
                    f"{settings.LLM_BASE_URL}/models",
                    headers={"ngrok-skip-browser-warning": "1"}
                )
                resp.raise_for_status()
                
            # 2. Gateway is healthy! Check for failed jobs.
            failed_job_ids = registry.get_job_ids()
            if failed_job_ids:
                logger.info("ML Gateway is healthy and failed jobs detected. Initiating auto-recovery.", failed_count=len(failed_job_ids))
                for job_id in failed_job_ids:
                    try:
                        # Requeue the job
                        ingestion_queue.requeue_job(job_id)
                        logger.info("Successfully requeued job", job_id=job_id)
                    except Exception as e:
                        logger.error("Failed to requeue job", job_id=job_id, error=str(e))
                        
        except httpx.HTTPError:
            # Expected if gateway is down, silently ignore and wait
            pass
        except asyncio.CancelledError:
            logger.info("DLQ Auto-Recovery Daemon shutting down.")
            break
        except Exception as e:
            logger.error("Unexpected error in DLQ recovery loop", error=str(e), exc_info=True)
            
        await asyncio.sleep(60)

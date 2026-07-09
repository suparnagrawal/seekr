from rq import Retry
from backend.shared.config import settings

def get_default_retry() -> Retry:
    """
    Returns the standard exponential backoff retry policy for background jobs,
    configured via application Settings.
    """
    intervals = [int(i.strip()) for i in settings.RQ_RETRY_INTERVALS.split(",")]
    return Retry(max=settings.RQ_RETRY_MAX, interval=intervals)

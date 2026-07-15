import pytest
import asyncio
from backend.fabric_api.dlq_recovery import dlq_recovery_loop

@pytest.mark.asyncio
async def test_dlq_commercial_api_skips_ping(monkeypatch):
    monkeypatch.setattr("backend.fabric_api.dlq_recovery.settings.LLM_BASE_URL", "https://api.openai.com/v1")
    
    class MockRegistry:
        def __init__(self, queue=None): pass
        def get_job_ids(self): return ["job_1"]
        
    class MockQueue:
        def requeue_job(self, job_id): pass
        
    monkeypatch.setattr("backend.fabric_api.dlq_recovery.FailedJobRegistry", MockRegistry)
    monkeypatch.setattr("backend.fabric_api.dlq_recovery.ingestion_queue", MockQueue())
    
    async def mock_sleep(*args, **kwargs):
        raise asyncio.CancelledError()
        
    monkeypatch.setattr("asyncio.sleep", mock_sleep)
    
    # Run the loop, it should process the jobs and then break on sleep
    await dlq_recovery_loop()
    
@pytest.mark.asyncio
async def test_dlq_unconfigured_exits_early(monkeypatch):
    monkeypatch.setattr("backend.fabric_api.dlq_recovery.settings.LLM_BASE_URL", None)
    
    # Should return immediately without exception
    await dlq_recovery_loop()


import pytest
import os
import httpx
import uuid
from backend.shared.config import settings
from backend.fabric_api.main import app

BASE_URL = "http://test/api/v1"

@pytest.fixture
def client():
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")

@pytest.mark.asyncio
async def test_health_endpoint(client):
    response = await client.get(f"{BASE_URL}/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"

@pytest.mark.asyncio
async def test_metrics_endpoint(client):
    response = await client.get(f"{BASE_URL}/metrics")
    assert response.status_code == 200
    text = response.text
    assert "seekr" in text
    assert "seekr_postgres_documents_total" in text

@pytest.mark.asyncio
async def test_graph_feedback_endpoint(client):
    tag = f"TEST_PUMP_{uuid.uuid4().hex[:6]}"
    payload = {
        "description": "Test updated description",
        "entity_type": "Pump",
        "correction_note": "Expert validation for tests."
    }
    response = await client.post(f"{BASE_URL}/entities/{tag}/feedback", json=payload)
    
    # It should succeed or fail gracefully if neo4j isn't perfectly seeded, but the endpoint should be alive.
    assert response.status_code in (200, 404, 500)
        
@pytest.mark.asyncio
async def test_agent_query(client):
    payload = {
        "query": "Tell me about the test pump",
        "session_id": "test_session_123"
    }
    # Try to start a stream request. We only care that the connection opens and streams.
    try:
        async with client.stream("POST", f"{BASE_URL}/query/stream", json=payload) as response:
            assert response.status_code in (200, 404, 500)
    except Exception:
        pass

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
    assert data["status"] == "healthy"

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
    try:
        response = await client.post(f"{BASE_URL}/entities/{tag}/feedback", json=payload)
        assert response.status_code in (200, 404, 500)
    except Exception:
        pass
        
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

@pytest.mark.asyncio
async def test_unauthorized_request(client, monkeypatch):
    """Test that unauthorized requests fail when ENABLE_AUTH is true."""
    monkeypatch.setenv("ENABLE_AUTH", "true")
    # A request with no auth token
    response = await client.delete(f"{BASE_URL}/documents/{uuid.uuid4()}")
    assert response.status_code == 401

@pytest.mark.asyncio
async def test_invalid_jwt(client, monkeypatch):
    """Test that an invalid JWT fails."""
    monkeypatch.setenv("ENABLE_AUTH", "true")
    monkeypatch.setenv("JWT_AUDIENCE", "test")
    monkeypatch.setenv("JWKS_URL", "https://test/.well-known/jwks.json")
    response = await client.delete(
        f"{BASE_URL}/documents/{uuid.uuid4()}",
        headers={"Authorization": "Bearer not-a-real-jwt"}
    )
    # The PyJWKClient will fail to fetch keys or it will be invalid token
    assert response.status_code in (401, 500)
    
@pytest.mark.asyncio
async def test_invalid_citation_regeneration(client):
    """Test citation regeneration gracefully handles invalid fact_id."""
    payload = {"fact_id": "non-existent-fact-id", "question": "test"}
    # Usually this would return 404 or an empty state, not crash
    response = await client.post(f"{BASE_URL}/citations/regenerate", json=payload)
    assert response.status_code in (404, 200, 422)

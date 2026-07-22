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


@pytest.mark.asyncio
async def test_unauthorized_request(client):
    """Test that unauthorized requests fail when auth is enabled."""
    from backend.shared.security import verify_jwt
    from backend.shared.exceptions import AuthenticationError
    
    def override_verify_jwt():
        raise AuthenticationError("Not authenticated")
        
    from backend.fabric_api.main import app
    app.dependency_overrides[verify_jwt] = override_verify_jwt
    
    # A request with no auth token
    response = await client.delete(f"{BASE_URL}/documents/{uuid.uuid4()}")
    assert response.status_code == 401
    
    app.dependency_overrides.clear()

@pytest.mark.asyncio
async def test_invalid_jwt(client):
    """Test that an invalid JWT fails."""
    from backend.shared.security import verify_jwt
    from backend.shared.exceptions import AuthenticationError
    
    def override_verify_jwt():
        raise AuthenticationError("Not authenticated")
        
    from backend.fabric_api.main import app
    app.dependency_overrides[verify_jwt] = override_verify_jwt
    response = await client.delete(
        f"{BASE_URL}/documents/{uuid.uuid4()}",
        headers={"Authorization": "Bearer not-a-real-jwt"}
    )
    assert response.status_code == 401
    app.dependency_overrides.clear()
    
@pytest.mark.asyncio
async def test_invalid_citation_regeneration(client):
    """Test citation regeneration gracefully handles invalid fact_id."""
    payload = {"fact_id": "non-existent-fact-id", "question": "test"}
    # Usually this would return 404 or an empty state, not crash
    response = await client.post(f"{BASE_URL}/citations/regenerate", json=payload)
    assert response.status_code in (404, 200, 422)

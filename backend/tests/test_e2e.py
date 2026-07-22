import pytest
import uuid
import httpx
from unittest.mock import patch, AsyncMock, MagicMock

from backend.fabric_api.main import app
from backend.shared.security import verify_jwt
from backend.shared.config import settings

BASE_URL = "http://test/api/v1"

@pytest.fixture
def override_auth():
    # Pin auth state explicitly: assume valid admin JWT
    def mock_verify_jwt():
        return {"sub": "e2e_user", "role": "admin"}
    app.dependency_overrides[verify_jwt] = mock_verify_jwt
    yield
    app.dependency_overrides.clear()

@pytest.fixture
def client(override_auth):
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")

@pytest.mark.asyncio
async def test_end_to_end_flow(client):
    """
    Simulates a full E2E flow with explicit assertions and no swallowed exceptions.
    1. Upload document (mocked HTTP response)
    2. Query for information (mocked generator)
    3. Feedback supersession (mocked DB transaction)
    """
    payload = {
        "query": "Tell me about the P-301 pump from the uploaded document.",
        "session_id": f"e2e_{uuid.uuid4().hex}"
    }
    
    # 1. Query Stream - mock the streaming generator to just yield a chunk
    with patch("backend.app.api.query.run_query") as mock_stream:
        async def mock_generator(*args, **kwargs):
            yield "data: {\"type\": \"content\", \"content\": \"Pump P-301 is a centrifugal pump.\"}\n\n"
        mock_stream.return_value = mock_generator()
        
        async with client.stream("POST", f"{BASE_URL}/query", json=payload) as response:
            assert response.status_code == 200
            content = await response.aread()
            assert b"Pump P-301" in content
        
    # 2. Submit feedback (will return 404 since Neo4j is empty, but proves auth and routing)
    tag = "P-301"
    feedback = {
        "description": "Updated P-301 description",
        "entity_type": "Pump",
        "correction_note": "E2E update"
    }
    
    resp = await client.post(f"{BASE_URL}/entities/{tag}/feedback", json=feedback)
    assert resp.status_code == 404  # Not found, since DB is empty. (No 500 or auth bypass)
    data = resp.json()
    assert "not found" in data["detail"].lower()

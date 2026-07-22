import pytest
import uuid
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

with patch("backend.shared.config.settings.S3_ACCESS_KEY_ID", "mock"):
    from backend.fabric_api.main import app

def test():
    from backend.shared.config import settings
    # temporarily mock settings
    with patch.object(settings.__class__, "auth_enabled", False):
        with patch.object(settings, "DEV_FALLBACK_ROLE", "admin"):
            client = TestClient(app)
            response = client.delete(f"/api/v1/documents/{uuid.uuid4()}")
            print("Status:", response.status_code)

test()

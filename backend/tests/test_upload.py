import pytest
from fastapi.testclient import TestClient
import uuid

from backend.fabric_api.main import app
from backend.shared.database import SessionLocal
from backend.shared.models.document import Document
from backend.shared.redis_client import get_queue
from backend.shared.security import verify_jwt
from unittest.mock import MagicMock

@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c

@pytest.fixture(scope="module", autouse=True)
def setup_database():
    """
    Ensure the test database is clean.
    DISABLED: We no longer blanket-delete the database.
    Tests must clean up their own inserted rows.
    """
    pass
@pytest.fixture(scope="function")
def mock_redis_queue():
    """
    Mock the Redis queue dependency so tests don't require a running Redis instance.
    Cleans up automatically after the test.
    """
    mock_queue = MagicMock()
    mock_job = MagicMock()
    mock_job.id = "mock_job_id"
    mock_queue.enqueue.return_value = mock_job
    app.dependency_overrides[get_queue] = lambda: mock_queue
    app.dependency_overrides[verify_jwt] = lambda: {"sub": "test_user"}
    yield mock_queue
    app.dependency_overrides.pop(get_queue, None)
    app.dependency_overrides.pop(verify_jwt, None)

def test_upload_pdf(client, tmp_path, mock_redis_queue):
    """
    Test uploading a valid PDF document.
    """
    # Create a dummy PDF file
    dummy_pdf = tmp_path / "test.pdf"
    dummy_pdf.write_bytes(b"%PDF-1.4\n%Dummy PDF content\n%%EOF")
    
    with open(dummy_pdf, "rb") as f:
        response = client.post(
            "/api/v1/upload",
            files={"file": ("test.pdf", f, "application/pdf")}
        )
        
    assert response.status_code == 202
    data = response.json()
    
    assert "document_id" in data
    assert "job_id" in data
    assert data["status"] == "QUEUED"
    
    # Verify DB insertion
    with SessionLocal() as db:
        doc = db.query(Document).filter(Document.id == uuid.UUID(data["document_id"])).first()
        assert doc is not None
        assert doc.filename == "test.pdf"
        assert doc.mime_type == "application/pdf"
        assert doc.status == "QUEUED"
        
        # Safe cleanup: Delete ONLY the document created by this test
        db.delete(doc)
        db.commit()
def test_upload_invalid_mime(client, tmp_path, mock_redis_queue):
    """
    Test uploading a non-PDF file.
    """
    dummy_txt = tmp_path / "test.txt"
    dummy_txt.write_text("This is not a PDF")
    
    with open(dummy_txt, "rb") as f:
        response = client.post(
            "/api/v1/upload",
            files={"file": ("test.txt", f, "text/plain")}
        )
        
    assert response.status_code == 415
    assert "Unsupported media type" in response.json()["detail"]

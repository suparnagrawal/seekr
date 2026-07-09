import pytest
from fastapi.testclient import TestClient
import uuid

from backend.fabric_api.main import app
from backend.shared.database import Base, engine, SessionLocal
from backend.shared.models.document import Document

client = TestClient(app)

@pytest.fixture(scope="module", autouse=True)
def setup_database():
    """
    Ensure the test database is clean.
    Since we are using the main DB for this hackathon test, we'll just clear the documents table before and after.
    """
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        db.query(Document).delete()
        db.commit()
        
    yield
    
    with SessionLocal() as db:
        db.query(Document).delete()
        db.commit()

def test_upload_pdf(tmp_path):
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

def test_upload_invalid_mime(tmp_path):
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

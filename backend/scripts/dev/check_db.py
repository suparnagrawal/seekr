import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from backend.shared.database import SessionLocal
from backend.shared.models.document import Document

db = SessionLocal()
doc = db.query(Document).order_by(Document.uploaded_at.desc()).first()
if doc:
    print(f"Status: {doc.status}")
    print(f"Graph Status: {doc.graph_job_status}")
    print(f"Error: {doc.error_message}")
else:
    print("No documents found.")
db.close()

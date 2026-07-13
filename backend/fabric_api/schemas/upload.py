import uuid
from pydantic import BaseModel

class UploadResponse(BaseModel):
    document_id: uuid.UUID
    job_id: str
    status: str

class DocumentStatusResponse(BaseModel):
    document_id: uuid.UUID
    filename: str
    overall_status: str
    graph_job_status: str | None
    error_message: str | None
    page_count: int | None
    chunk_count: int | None
    uploaded_at: str
    updated_at: str

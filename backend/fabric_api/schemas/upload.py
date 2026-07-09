import uuid
from pydantic import BaseModel

class UploadResponse(BaseModel):
    document_id: uuid.UUID
    job_id: str
    status: str

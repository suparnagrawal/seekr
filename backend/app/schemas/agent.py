from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
import re

class AgentRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000, description="The user's question")
    session_id: str = Field(..., min_length=1, max_length=128)
    thread_id: Optional[str] = Field(None, max_length=128)
    focused_tag: Optional[str] = Field(None, max_length=256)

    @field_validator("focused_tag")
    @classmethod
    def validate_tag_format(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not re.match(r"^[\w\s\-./()]+$", v):
            raise ValueError("focused_tag contains invalid characters")
        return v

class AgentResponse(BaseModel):
    answer: str
    citations: List[str] = []
    error: Optional[str] = None

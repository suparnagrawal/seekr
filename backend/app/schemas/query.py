from pydantic import BaseModel, Field, field_validator
from typing import Optional, Any, Dict, List
import re

class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000, description="The user's question")
    session_id: str = Field(..., min_length=1, max_length=128)
    focused_tag: Optional[str] = Field(None, max_length=256)

    @field_validator("focused_tag")
    @classmethod
    def validate_tag_format(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not re.match(r"^[\w\s\-./()]+$", v):
            raise ValueError("focused_tag contains invalid characters")
        return v

class TokenEventData(BaseModel):
    text: str

class CitationEventData(BaseModel):
    doc_id: str
    filename: str
    passage_id: str
    chunk_index: int
    page_numbers: List[int] = []
    headings: List[str] = []
    page: Optional[int] = None

class AgentTriggerEventData(BaseModel):
    worker: str
    job_id: str

class DoneEventData(BaseModel):
    answer_id: str

class ReasoningEventData(BaseModel):
    content: str

class ToolCallEventData(BaseModel):
    tool_name: str
    tool_args: Dict[str, Any]

class ToolResultEventData(BaseModel):
    tool_name: str
    result: Any

class ErrorEventData(BaseModel):
    message: str
    code: Optional[str] = None

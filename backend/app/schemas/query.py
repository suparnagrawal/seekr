from pydantic import BaseModel
from typing import Optional, Any, Dict

class QueryRequest(BaseModel):
    query: str
    session_id: str
    focused_tag: Optional[str] = None

class TokenEventData(BaseModel):
    text: str

class CitationEventData(BaseModel):
    doc_id: str
    passage_id: str
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

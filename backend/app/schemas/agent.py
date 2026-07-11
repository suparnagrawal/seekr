from pydantic import BaseModel
from typing import Optional, List

class AgentRequest(BaseModel):
    query: str
    session_id: str
    thread_id: Optional[str] = None
    focused_tag: Optional[str] = None

class AgentResponse(BaseModel):
    answer: str
    citations: List[str] = []
    error: Optional[str] = None

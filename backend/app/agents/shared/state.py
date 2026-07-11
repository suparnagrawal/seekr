"""
Shared state models for the P3 Agent layer.

These Pydantic models represent the internal state passed between P3 components
(Copilot, Supervisor, Workers). They are not API schemas — they carry runtime
context within a single request lifecycle.

P2-owned models (RetrievalContext, GraphContext, Citation, AgentRequest,
AgentResponse) are imported but never modified here.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class WorkerType(str, Enum):
    """Specialist worker identifiers used by the Supervisor for routing."""

    ASSET = "asset"
    DIAGNOSE = "diagnose"
    COMPLIANCE = "comply"


class MessageRole(str, Enum):
    """Role of a message within the conversation history."""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class Message(BaseModel):
    """A single message in the conversation history."""

    role: MessageRole
    content: str


class ConversationContext(BaseModel):
    """
    Represents the ongoing conversation history and user session data.

    Maintained across turns within a session to provide continuity for the
    Copilot and any escalated workers.
    """

    session_id: str
    messages: List[Message] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class EscalationContext(BaseModel):
    """
    Passed between the Copilot and the Supervisor when specialized reasoning
    is required.

    This is only constructed during the general query flow (POST /query) when
    the Copilot determines that escalation is needed after its initial LLM
    generation and trigger evaluation.

    Explicit agent endpoints (POST /asset, /diagnose, /comply) never create
    an EscalationContext — they construct AgentState directly.
    """

    query: str
    session_id: str
    thread_id: Optional[str] = None
    focused_tag: Optional[str] = None
    retrieval_context: Dict[str, Any] = Field(default_factory=dict)
    citations: List[Dict[str, Any]] = Field(default_factory=list)
    trigger_reason: str = ""
    trigger_confidence: float = 0.0
    copilot_answer: Optional[str] = None
    conversation: Optional[ConversationContext] = None


class AgentState(BaseModel):
    """
    The internal state within a LangGraph execution.

    For escalated queries: constructed by the Supervisor from an
    EscalationContext.

    For explicit agent endpoints: constructed directly from the AgentRequest
    before entering the worker workflow.
    """

    query: str
    session_id: str
    thread_id: Optional[str] = None
    focused_tag: Optional[str] = None
    worker: Optional[WorkerType] = None
    retrieval_context: Dict[str, Any] = Field(default_factory=dict)
    citations: List[Dict[str, Any]] = Field(default_factory=list)
    reasoning_steps: List[str] = Field(default_factory=list)
    tool_calls: List[Dict[str, Any]] = Field(default_factory=list)
    answer: Optional[str] = None
    error: Optional[str] = None
    conversation: Optional[ConversationContext] = None

from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional


class GraphNode(BaseModel):
    id: str
    tag: str
    label: str
    type: str
    properties: Dict[str, Any] = Field(default_factory=dict)
    confidence: Optional[float] = None


class GraphEdge(BaseModel):
    id: str
    source: str
    target: str
    relationship: str
    confidence: float = 1.0
    properties: Dict[str, Any] = Field(default_factory=dict)


class GraphResponse(BaseModel):
    center: str
    nodes: List[GraphNode] = Field(default_factory=list)
    edges: List[GraphEdge] = Field(default_factory=list)


class EntityFeedbackRequest(BaseModel):
    """Request body for entity correction/feedback."""
    description: Optional[str] = Field(None, max_length=2000, description="Updated entity description")
    entity_type: Optional[str] = Field(None, max_length=128, description="Updated entity type")
    correction_note: Optional[str] = Field(None, max_length=500, description="Reason for the correction")


class EntityFeedbackResponse(BaseModel):
    tag: str
    status: str = "updated"
    previous_description: Optional[str] = None
    previous_type: Optional[str] = None


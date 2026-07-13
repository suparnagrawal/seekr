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

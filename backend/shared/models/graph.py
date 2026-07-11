from typing import Any, List, Dict, Optional
from pydantic import BaseModel, Field

class Node(BaseModel):
    tag: str
    label: str
    properties: Dict[str, Any] = Field(default_factory=dict)

class Edge(BaseModel):
    source: str
    target: str
    type: str
    confidence: Optional[float] = None

class GraphExtractionResult(BaseModel):
    nodes: List[Node] = Field(default_factory=list)
    edges: List[Edge] = Field(default_factory=list)

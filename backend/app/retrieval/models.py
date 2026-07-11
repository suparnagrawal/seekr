from enum import Enum
from dataclasses import dataclass, field
from typing import List, Optional, Any, Dict

class QueryType(str, Enum):
    FACTUAL = "factual"
    DIAGNOSTIC = "diagnostic"
    PROCEDURAL = "procedural"
    OPEN = "open"

@dataclass
class TraversalContext:
    explicit_tags: List[str]
    implicit_tags: List[str]
    query_type: QueryType
    query_embedding: List[float]

@dataclass
class RankedSeed:
    tag: str
    score: float

@dataclass
class ScoredNode:
    tag: str
    score: float
    depth: int
    entity_type: str = "Unknown"

@dataclass
class Edge:
    source_tag: str
    target_tag: str
    rel_type: str
    confidence: float
    fact_id: str
    source_doc_id: str

@dataclass
class Chunk:
    chunk_id: str
    text: str
    score: float
    source: str
    payload: Dict[str, Any] = field(default_factory=dict)
    fact_ids: List[str] = field(default_factory=list)

@dataclass
class SyntheticPassage(Chunk):
    pass

@dataclass
class Citation:
    doc_id: str
    passage_id: str
    page: Optional[int] = None
    text_snippet: Optional[str] = None

@dataclass
class GraphContext:
    passages: List[Chunk]
    entities: List[str] = field(default_factory=list)
    relationships: List[str] = field(default_factory=list)

@dataclass
class RetrievalContext:
    chunks: List[Chunk]
    graph_context: Optional[GraphContext] = None
    citations: List[Citation] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

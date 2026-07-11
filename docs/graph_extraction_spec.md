# Seekr Graph Extraction Specification

This document defines the formal ingestion rules for the Phase 1 Knowledge Graph extraction pipeline. 
It establishes the operational parameters used to parse `chunks.json` into the Neo4j ontology defined in `docs/graph_schema.md`.

## 1. Prompt & Generation Parameters
- **Prompt Version**: v1.0
- **Ontology Version**: v1
- **Prompt Source**: `backend/ingestion_worker/graph_prompts.py`
- **Output Format**: JSON is strictly enforced either natively via the LLM API (`response_format={"type": "json_object"}`) or through standard prompt-engineering fallbacks for non-OpenAI compliant models.
- **Max Context Batch**: Currently batches 10 chunks per LLM extraction call to prevent context window exhaustion. (This will be expanded based on the context size of `LLM_MODEL`).
- **Temperature**: `0.0` to maximize determinism.

## 2. Pydantic Output Schema
The LLM response is structurally validated at runtime via Pydantic in `graph_jobs.py` before any Neo4j Cypher queries are executed.

```python
class Node(BaseModel):
    tag: str
    label: str
    properties: Dict[str, Any] = Field(default_factory=dict)

class Edge(BaseModel):
    source: str
    target: str
    type: str
    confidence: float = 1.0

class GraphExtractionResult(BaseModel):
    nodes: List[Node] = Field(default_factory=list)
    edges: List[Edge] = Field(default_factory=list)
```

## 3. Retries & Error Handling
- **RQ Retry Policy**: If the extraction or Neo4j insertion fails (due to network timeout, malformed JSON, or database locks), the job is retried based on `RQ_RETRY_MAX` (default: 3) with exponential backoff defined in `RQ_RETRY_INTERVALS` (default: `10,30,60`).
- **Validation Failures**: If the Pydantic validation fails, an `IngestionPipelineError` is raised, triggering the retry loop. The document is marked as `FAILED` if all retries are exhausted.

## 4. Canonicalization & Edge Confidence
- **Deduplication (Nodes)**: Nodes are merged idempotently in Neo4j using the `tag` property (`MERGE (n:Entity {tag: node.tag})`). This naturally deduplicates exact matches (e.g., `tag: "Pump P-101A"`), but string canonicalization (e.g., standardizing casing or spacing) is currently handled implicitly by the LLM instructions.
- **Edge Confidence**: The LLM outputs a `confidence` float (`0.0 - 1.0`). In Cypher, `MERGE` handles edge uniqueness, and `SET r.confidence = COALESCE(edge.confidence, 1.0)` records the strength of the relationship for P2 adaptive traversal.

"""
Mock fixture data for Day 0 development before P1 connects real databases.
"""

from typing import Any, Dict, List, Tuple

# Mock facts table (Postgres)
MOCK_FACTS = [
    {"subject_tag": "P-101A", "predicate": "experiencedFailure", "object_tag": "FailureMode-1", "confidence": 0.9, "source_doc_id": "d-91"},
    {"subject_tag": "P-101B", "predicate": "experiencedFailure", "object_tag": "FailureMode-1", "confidence": 0.8, "source_doc_id": "d-91"},
]

# Mock Neo4j Graph
MOCK_GRAPH = {
    "P-101A": {
        "entity_type": "Equipment",
        "neighbors": [
            ("P-101B", "CONNECTED_TO", 0.55),
            ("FailureMode-1", "EXPERIENCED_FAILURE", 0.9)
        ]
    }
}

# Mock Qdrant Vector DB
MOCK_VECTORS = {
    "doc-1-chunk-1": {
        "text": "Pump P-101A has experienced a bearing failure.",
        "payload": {"doc_id": "d-91", "passage_id": "p-4", "page": 3}
    }
}

async def mock_qdrant_search(query_embedding: List[float], top_k: int = 10) -> List[Dict[str, Any]]:
    # Simply return mock vectors regardless of embedding for Day 0
    return [{"chunk_id": k, **v} for k, v in MOCK_VECTORS.items()][:top_k]

async def mock_neo4j_neighbors(tag: str) -> List[Tuple[str, str, float]]:
    return MOCK_GRAPH.get(tag, {}).get("neighbors", [])

async def mock_pg_facts(doc_ids: List[str]) -> List[Dict[str, Any]]:
    return [f for f in MOCK_FACTS if f["source_doc_id"] in doc_ids]

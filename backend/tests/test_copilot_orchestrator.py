import pytest
from backend.app.agents.copilot.orchestrator import _classify_query_heuristic
from backend.app.retrieval.models import QueryType

def test_classify_query_heuristic():
    assert _classify_query_heuristic("Why is this failing?") == QueryType.DIAGNOSTIC
    assert _classify_query_heuristic("What is the root cause of the error?") == QueryType.DIAGNOSTIC
    assert _classify_query_heuristic("How do I fix this?") == QueryType.PROCEDURAL
    assert _classify_query_heuristic("What are the steps to deploy?") == QueryType.PROCEDURAL
    assert _classify_query_heuristic("Which one is better?") == QueryType.OPEN
    assert _classify_query_heuristic("When was this created?") == QueryType.FACTUAL
    assert _classify_query_heuristic("Tell me a story.") == QueryType.OPEN

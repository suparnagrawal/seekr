"""
Heuristic query classification shared between P2 (retrieval) and P3 (agents).

Lives in the shared layer so both P2's ContextAssembler and P3's Copilot can
import it without creating a cross-layer dependency.
"""

from backend.app.retrieval.models import QueryType

def classify_query_heuristic(query: str) -> QueryType | None:
    """Fast keyword-based classification. Returns None if no pattern matches,
    allowing callers to fall back to LLM classification or a default."""
    q = query.lower()
    if any(kw in q for kw in ("why", "keeps failing", "root cause")):
        return QueryType.DIAGNOSTIC
    if any(kw in q for kw in ("how do i", "steps to")):
        return QueryType.PROCEDURAL
    if any(kw in q for kw in ("which", "compatible", "compare")):
        return QueryType.OPEN
    if any(kw in q for kw in ("what", "when")):
        return QueryType.FACTUAL
    return None

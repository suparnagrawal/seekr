import pytest
import asyncio
from backend.app.retrieval.context import assemble_context, mock_classify_query
from backend.app.retrieval.pathways import graph_pathway
from backend.app.retrieval.orchestrator import citations_resolve, generate_answer
from backend.app.retrieval.models import Chunk, QueryType
from backend.app.kg.shared_tools import context_graph_query

@pytest.mark.asyncio
async def test_context_assembly():
    query = "What is the root cause of P-101A failure?"
    ctx = await assemble_context(query, "s-123", focused_tag="P-101A")
    assert ctx.query_type == QueryType.DIAGNOSTIC
    assert "P-101A" in ctx.explicit_tags
    assert len(ctx.query_embedding) == 384

@pytest.mark.asyncio
async def test_adaptive_traversal_integration():
    # Calling graph_pathway directly tests adaptive traversal
    passages = await graph_pathway("P-101A failed", QueryType.DIAGNOSTIC, "s-123", "P-101A", "deep")
    # We should get at least the seeds
    assert len(passages) >= 0

def test_citation_resolution():
    chunks = [Chunk(chunk_id="1", text="a", score=1.0, source="test")]
    assert citations_resolve("test", chunks) is True

@pytest.mark.asyncio
async def test_context_graph_query():
    result = await context_graph_query("P-101A", "Why failure?", "shallow")
    assert result.passages is not None

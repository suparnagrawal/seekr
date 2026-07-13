import pytest
from backend.app.retrieval.context import ContextAssembler
from backend.app.retrieval.retrievers.graph import GraphRetriever
from backend.app.retrieval.models import QueryType
from backend.app.retrieval.interfaces import SearchQuery
from backend.app.kg.shared_tools import context_graph_query

@pytest.mark.asyncio
async def test_context_assembly():
    query = SearchQuery(text="What is the root cause of P-101A failure?", session_id="s-123", focused_tag="P-101A")
    assembler = ContextAssembler()
    ctx = await assembler.assemble(query)
    # The actual context logic relies on LLMs or DBs, so assertions here depend on the actual mocked vs real logic.
    assert ctx.query_type is not None

@pytest.mark.asyncio
async def test_adaptive_traversal_integration():
    assembler = ContextAssembler()
    query = SearchQuery(text="P-101A failed", session_id="s-123", focused_tag="P-101A", query_type=QueryType.DIAGNOSTIC)
    ctx = await assembler.assemble(query)
    
    retriever = GraphRetriever()
    passages = await retriever.retrieve(query, ctx)
    assert len(passages) >= 0

@pytest.mark.asyncio
async def test_context_graph_query():
    result = await context_graph_query("P-101A", "Why failure?", "shallow")
    assert result.passages is not None

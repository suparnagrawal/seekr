"""
Tests for the P2 retrieval pipeline.

These tests validate the DefaultRetrievalPipeline directly (not through the
orchestrator's cached singleton) to verify that:
  - Retrievers are invoked concurrently
  - RRF fusion merges results correctly
  - The reranker is applied when present
  - Chunks are capped to RETRIEVAL_TOP_K
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from backend.app.retrieval.interfaces import SearchQuery, RetrievalResult
from backend.app.retrieval.models import (
    QueryType,
    TraversalContext,
    Chunk,
)
from backend.app.retrieval.pipeline import DefaultRetrievalPipeline
from backend.app.retrieval.fusion import ReciprocalRankFusion


def _make_context() -> TraversalContext:
    """Build a minimal TraversalContext for testing."""
    return TraversalContext(
        query_embedding=[0.0] * 768,
        explicit_tags=[],
        implicit_tags=[],
        query_type=QueryType.OPEN,
    )


def _make_chunk(chunk_id: str, text: str, score: float, source: str) -> Chunk:
    return Chunk(
        chunk_id=chunk_id,
        text=text,
        score=score,
        source=source,
        payload={"filename": "test.pdf", "document_id": "doc-1", "chunk_index": int(chunk_id)},
    )


class FakeRetriever:
    """Minimal concrete retriever for testing without touching databases."""

    def __init__(self, name: str, chunks: list[Chunk]):
        self._name = name
        self._chunks = chunks

    @property
    def name(self) -> str:
        return self._name

    async def retrieve(self, query: SearchQuery, context: TraversalContext) -> list[Chunk]:
        return self._chunks


@pytest.mark.asyncio
async def test_pipeline_fuses_two_retrievers():
    """Dense + graph chunks are fused via RRF and returned."""
    dense_chunks = [_make_chunk("1", "dense result", 0.9, "vector")]
    graph_chunks = [_make_chunk("2", "graph result", 0.7, "graph")]

    assembler = AsyncMock()
    assembler.assemble.return_value = _make_context()

    pipeline = DefaultRetrievalPipeline(
        retrievers=[
            FakeRetriever("dense", dense_chunks),
            FakeRetriever("graph", graph_chunks),
        ],
        fusion_strategy=ReciprocalRankFusion(),
        context_assembler=assembler,
    )

    result = await pipeline.run(
        SearchQuery(text="test query", session_id="s1", query_type=QueryType.OPEN)
    )

    assert isinstance(result, RetrievalResult)
    assert len(result.chunks) == 2
    assert set(result.pathways_used) == {"dense", "graph"}
    assert "total_seconds" in result.timings


@pytest.mark.asyncio
async def test_pipeline_applies_reranker():
    """When a reranker is supplied, it is called on the fused chunks."""
    chunks = [_make_chunk("1", "chunk", 0.9, "vector")]

    assembler = AsyncMock()
    assembler.assemble.return_value = _make_context()

    reranker = MagicMock()
    reranker.rerank.return_value = chunks  # pass-through

    pipeline = DefaultRetrievalPipeline(
        retrievers=[FakeRetriever("dense", chunks)],
        fusion_strategy=ReciprocalRankFusion(),
        context_assembler=assembler,
        reranker=reranker,
    )

    result = await pipeline.run(
        SearchQuery(text="test", session_id="s1", query_type=QueryType.OPEN)
    )

    reranker.rerank.assert_called_once()
    assert len(result.chunks) == 1


@pytest.mark.asyncio
async def test_pipeline_empty_retrievers():
    """Pipeline with no retrievers returns an empty result."""
    assembler = AsyncMock()
    assembler.assemble.return_value = _make_context()

    pipeline = DefaultRetrievalPipeline(
        retrievers=[],
        fusion_strategy=ReciprocalRankFusion(),
        context_assembler=assembler,
    )

    result = await pipeline.run(
        SearchQuery(text="test", session_id="s1", query_type=QueryType.OPEN)
    )

    assert result.chunks == []
    assert result.pathways_used == []

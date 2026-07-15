import pytest
from backend.app.retrieval.models import Chunk, TraversalContext, QueryType
from backend.app.retrieval.interfaces import SearchQuery
from backend.app.retrieval.reranking import MetadataReranker

def test_reranker_bonuses():
    reranker = MetadataReranker()
    
    c1 = Chunk(chunk_id="1", text="text1", score=0.1, source="dense", payload={"filename": "doc1.pdf", "headings": ["Intro"]})
    c2 = Chunk(chunk_id="2", text="text2", score=0.1, source="dense", payload={"filename": "doc2.pdf"})
    c3 = Chunk(chunk_id="3", text="text3", score=0.1, source="dense", payload={"headings": ["Summary"]})
    
    query = SearchQuery(text="test", session_id="s1")
    context = TraversalContext(explicit_tags=["doc1", "Intro"], implicit_tags=[], query_type=QueryType.OPEN, query_embedding=[])
    
    reranked = reranker.rerank([c1, c2, c3], query, context)
    
    # c1 gets bonus for filename match "doc1" and heading match "Intro"
    # c2 gets no bonus
    # c3 gets no bonus
    assert reranked[0].chunk_id == "1"
    assert reranked[0].score > 0.1
    assert reranked[1].score == 0.1
    assert reranked[2].score == 0.1

def test_reranker_no_entities_fallback():
    reranker = MetadataReranker()
    
    c1 = Chunk(chunk_id="1", text="text1", score=0.1, source="dense", payload={"filename": "pump.pdf"})
    c2 = Chunk(chunk_id="2", text="text2", score=0.1, source="dense", payload={"filename": "doc2.pdf"})
    
    query = SearchQuery(text="pump failure", session_id="s1")
    context = TraversalContext(explicit_tags=[], implicit_tags=[], query_type=QueryType.OPEN, query_embedding=[])
    
    reranked = reranker.rerank([c1, c2], query, context)
    
    # c1 gets bonus for filename match "pump" from query fallback
    assert reranked[0].chunk_id == "1"
    assert reranked[0].score > 0.1
    assert reranked[1].score == 0.1

def test_reranker_max_bonus():
    reranker = MetadataReranker()
    
    # Lots of matches
    c1 = Chunk(chunk_id="1", text="text1", score=0.1, source="dense", payload={"filename": "pump doc.pdf", "headings": ["pump", "doc"]})
    
    query = SearchQuery(text="pump doc", session_id="s1")
    context = TraversalContext(explicit_tags=["pump", "doc"], implicit_tags=[], query_type=QueryType.OPEN, query_embedding=[])
    
    reranked = reranker.rerank([c1], query, context)
    
    # Bonus is capped
    assert reranked[0].score <= 0.1 + reranker.MAX_METADATA_BONUS + 0.01  # small float tolerance

import pytest
from backend.app.retrieval.models import Chunk
from backend.app.retrieval.fusion import ReciprocalRankFusion

def test_rrf_empty_groups():
    fusion = ReciprocalRankFusion(k=60)
    assert fusion.fuse([]) == []
    assert fusion.fuse([[], []]) == []

def test_rrf_single_group():
    fusion = ReciprocalRankFusion(k=60)
    c1 = Chunk(chunk_id="1", text="text1", score=1.0, source="dense")
    c2 = Chunk(chunk_id="2", text="text2", score=0.9, source="dense")
    
    fused = fusion.fuse([[c1, c2]])
    assert len(fused) == 2
    assert fused[0].chunk_id == "1"
    assert fused[1].chunk_id == "2"
    assert fused[0].score > fused[1].score

def test_rrf_multiple_groups():
    fusion = ReciprocalRankFusion(k=60)
    
    # c2 appears in both, c1 in first, c3 in second
    c1 = Chunk(chunk_id="1", text="text1", score=1.0, source="dense")
    c2 = Chunk(chunk_id="2", text="text2", score=0.9, source="dense")
    
    c2_alt = Chunk(chunk_id="2", text="text2", score=0.8, source="keyword")
    c3 = Chunk(chunk_id="3", text="text3", score=0.7, source="keyword")
    
    fused = fusion.fuse([[c1, c2], [c2_alt, c3]])
    
    assert len(fused) == 3
    # c2 should have the highest score because it's ranked 2nd and 1st
    assert fused[0].chunk_id == "2"
    assert fused[1].chunk_id == "1"
    assert fused[2].chunk_id == "3"

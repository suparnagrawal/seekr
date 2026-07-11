from typing import List, Dict
from backend.app.retrieval.models import Chunk
from backend.app.retrieval.interfaces import FusionStrategy
from backend.shared.config import settings
import structlog

logger = structlog.get_logger(__name__)

class ReciprocalRankFusion(FusionStrategy):
    """
    Reciprocal Rank Fusion (RRF) algorithm.
    RRF_score = sum(1 / (k + rank_in_list))
    """
    def __init__(self, k: int | None = None):
        self.k = k if k is not None else settings.RRF_K

    def fuse(self, results_groups: List[List[Chunk]]) -> List[Chunk]:
        rrf_scores: Dict[str, float] = {}
        chunk_map: Dict[str, Chunk] = {}
        
        for hits in results_groups:
            if not hits:
                continue
            # Results are expected to be sorted by their native score already
            for rank, hit in enumerate(hits):
                score = 1.0 / (self.k + rank + 1)
                
                if hit.chunk_id not in rrf_scores:
                    rrf_scores[hit.chunk_id] = 0.0
                    chunk_map[hit.chunk_id] = hit
                    
                rrf_scores[hit.chunk_id] += score
                
        for chunk_id, rrf_score in rrf_scores.items():
            chunk_map[chunk_id].score = rrf_score
            
        combined = list(chunk_map.values())
        combined.sort(key=lambda x: -x.score)
        
        return combined

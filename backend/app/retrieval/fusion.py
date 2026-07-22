from typing import Dict, List

import structlog

from backend.app.retrieval.interfaces import FusionStrategy
from backend.app.retrieval.models import Chunk, TraversalContext, QueryType
from backend.shared.config import settings

logger = structlog.get_logger(__name__)


class ReciprocalRankFusion(FusionStrategy):
    """
    Reciprocal Rank Fusion (RRF) algorithm.
    RRF_score = sum(1 / (k + rank_in_list))
    """

    def __init__(self, k: int | None = None):
        self.k = k if k is not None else settings.RRF_K

    def fuse(self, results_groups: List[List[Chunk]], context: TraversalContext = None) -> List[Chunk]:
        rrf_scores: Dict[str, float] = {}
        chunk_map: Dict[str, Chunk] = {}

        # Default weights
        weights = {"dense": 1.0, "keyword": 1.0, "graph": 1.0}
        
        # Apply Query-Type Weighting if context is available
        if context:
            if context.query_type == QueryType.DIAGNOSTIC:
                weights = {"dense": 0.8, "keyword": 0.5, "graph": 1.5}
            elif context.query_type == QueryType.FACTUAL:
                weights = {"dense": 1.0, "keyword": 1.2, "graph": 0.8}
            elif context.query_type == QueryType.OPEN:
                weights = {"dense": 1.2, "keyword": 0.8, "graph": 1.0}

        for hits in results_groups:
            if not hits:
                continue
            for rank, hit in enumerate(hits):
                weight = weights.get(hit.source, 1.0)
                score = (1.0 / (self.k + rank + 1)) * weight

                if hit.chunk_id not in rrf_scores:
                    rrf_scores[hit.chunk_id] = 0.0
                    chunk_map[hit.chunk_id] = hit

                rrf_scores[hit.chunk_id] += score

        for chunk_id, rrf_score in rrf_scores.items():
            chunk_map[chunk_id].score = rrf_score

        combined = list(chunk_map.values())
        combined.sort(key=lambda x: -x.score)

        return combined

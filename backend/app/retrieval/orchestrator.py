from typing import Optional

from backend.app.retrieval.models import QueryType, RetrievalContext
from backend.app.retrieval.interfaces import SearchQuery
from backend.app.retrieval.context import ContextAssembler
from backend.app.retrieval.pipeline import DefaultRetrievalPipeline
from backend.app.retrieval.fusion import ReciprocalRankFusion
from backend.app.retrieval.retrievers.dense import DenseRetriever
# from backend.app.retrieval.retrievers.keyword import KeywordRetriever
from backend.app.retrieval.retrievers.graph import GraphRetriever
from backend.shared.services.embedding_service import get_embedding_service
import structlog

logger = structlog.get_logger(__name__)

# Dependency Injection / Wiring Factories
def get_context_assembler() -> ContextAssembler:
    # Injecting the embedding service via DI
    return ContextAssembler(embedding_service=get_embedding_service())

def get_fusion_strategy() -> ReciprocalRankFusion:
    return ReciprocalRankFusion()

def get_retrieval_pipeline() -> DefaultRetrievalPipeline:
    return DefaultRetrievalPipeline(
        retrievers=[DenseRetriever(), GraphRetriever()],
        fusion_strategy=get_fusion_strategy(),
        context_assembler=get_context_assembler()
    )

# Public retrieval interface consumed by P3.
async def retrieve(
    query: str, query_type: QueryType, session_id: str, focused_tag: Optional[str] = None
) -> RetrievalContext:
    
    search_query = SearchQuery(
        text=query,
        session_id=session_id,
        focused_tag=focused_tag,
        query_type=query_type
    )
    
    pipeline = get_retrieval_pipeline()
    result = await pipeline.run(search_query)
    
    # Bridging the new RetrievalResult to the older RetrievalContext structure used by callers
    return RetrievalContext(
        chunks=result.chunks,
        metadata={
            "query_type": result.diagnostics.get("query_type"),
            "timings": result.timings,
            "pathways_used": result.pathways_used
        }
    )

# DEPRECATED/INTERNAL functions have been removed to enforce the P2->P3 contract.

from typing import Optional

from backend.app.retrieval.models import QueryType, RetrievalContext
from backend.app.retrieval.interfaces import SearchQuery
from backend.app.retrieval.context import ContextAssembler
from backend.app.retrieval.pipeline import DefaultRetrievalPipeline
from backend.app.retrieval.fusion import ReciprocalRankFusion
from backend.app.retrieval.reranking import MetadataReranker
from backend.app.retrieval.retrievers.dense import DenseRetriever
from backend.app.retrieval.retrievers.keyword import LexicalRetriever
from backend.app.retrieval.retrievers.graph import GraphRetriever
from backend.shared.services.embedding_service import get_embedding_service
from backend.shared.config import settings
import structlog

logger = structlog.get_logger(__name__)

# Dependency Injection / Wiring Factories
def get_context_assembler() -> ContextAssembler:
    # Injecting the embedding service via DI
    return ContextAssembler(embedding_service=get_embedding_service())

def get_fusion_strategy() -> ReciprocalRankFusion:
    return ReciprocalRankFusion()

_pipeline: Optional[DefaultRetrievalPipeline] = None

def get_retrieval_pipeline() -> DefaultRetrievalPipeline:
    global _pipeline
    if _pipeline is not None:
        return _pipeline
        
    # Three-pathway fusion: dense (Qdrant vector), graph (Neo4j traversal),
    # and lexical (Qdrant text-match). The lexical pathway restores exact-match
    # recall for tags, part numbers, and error codes that dense retrieval
    # underperforms on. It is fail-soft (BaseRetriever wraps it), so an error
    # yields an empty contribution rather than a pipeline failure.
    retrievers: list = [DenseRetriever(), GraphRetriever()]
    if settings.RETRIEVAL_ENABLE_KEYWORD:
        retrievers.append(LexicalRetriever())

    _pipeline = DefaultRetrievalPipeline(
        retrievers=retrievers,
        fusion_strategy=get_fusion_strategy(),
        context_assembler=get_context_assembler(),
        reranker=MetadataReranker()
    )
    return _pipeline

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
    
    from backend.app.retrieval.models import Citation

    # Bridging the new RetrievalResult to the older RetrievalContext structure used by callers
    return RetrievalContext(
        chunks=result.chunks,
        citations=[
            Citation(
                doc_id=chunk.payload.get("document_id", "unknown"),
                filename=chunk.payload.get("filename", "unknown"),
                passage_id=chunk.chunk_id,
                chunk_index=chunk.payload.get("chunk_index", 0),
                page_numbers=chunk.payload.get("page_numbers", []),
                headings=chunk.payload.get("headings", [])
            )
            for chunk in result.chunks
        ],
        metadata={
            "query_type": result.diagnostics.get("query_type"),
            "timings": result.timings,
            "pathways_used": result.pathways_used
        }
    )

# DEPRECATED/INTERNAL functions have been removed to enforce the P2->P3 contract.

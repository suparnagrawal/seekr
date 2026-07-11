from typing import Optional

from backend.app.retrieval.models import QueryType, RetrievalContext
from backend.app.retrieval.interfaces import SearchQuery, RetrievalResult
from backend.app.retrieval.context import ContextAssembler
from backend.app.retrieval.pipeline import DefaultRetrievalPipeline
from backend.app.retrieval.fusion import ReciprocalRankFusion
from backend.app.retrieval.prompt_builder import PromptBuilder, CitedAnswer
from backend.app.retrieval.retrievers.dense import DenseRetriever
from backend.app.retrieval.retrievers.keyword import KeywordRetriever
from backend.app.retrieval.retrievers.graph import GraphRetriever
from backend.shared.services.embedding_service import get_embedding_service

# Dependency Injection / Wiring Factories
def get_context_assembler() -> ContextAssembler:
    # Injecting the embedding service via DI
    return ContextAssembler(embedding_service=get_embedding_service())

def get_fusion_strategy() -> ReciprocalRankFusion:
    return ReciprocalRankFusion()

def get_retrieval_pipeline() -> DefaultRetrievalPipeline:
    return DefaultRetrievalPipeline(
        retrievers=[DenseRetriever(), KeywordRetriever(), GraphRetriever()],
        fusion_strategy=get_fusion_strategy(),
        context_assembler=get_context_assembler()
    )

def get_prompt_builder() -> PromptBuilder:
    return PromptBuilder()

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

# DEPRECATED/INTERNAL
# This function is NOT part of the frozen P2->P3 public contract.
# P3 should consume retrieve() instead.
async def retrieve_and_generate(query: str, session_id: str, focused_tag: Optional[str] = None) -> CitedAnswer:
    search_query = SearchQuery(
        text=query,
        session_id=session_id,
        focused_tag=focused_tag,
        query_type=QueryType.OPEN
    )
    
    pipeline = get_retrieval_pipeline()
    result = await pipeline.run(search_query)
    
    prompt_builder = get_prompt_builder()
    return await prompt_builder.generate_answer(query, result.chunks)

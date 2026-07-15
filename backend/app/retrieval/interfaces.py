from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

from backend.app.retrieval.models import QueryType, TraversalContext, Chunk

class SearchQuery(BaseModel):
    text: str
    session_id: str
    focused_tag: Optional[str] = None
    query_type: QueryType = QueryType.OPEN

class RetrievalResult(BaseModel):
    chunks: List[Chunk]
    diagnostics: Dict[str, Any] = Field(default_factory=dict)
    timings: Dict[str, float] = Field(default_factory=dict)
    pathways_used: List[str] = Field(default_factory=list)

class BaseRetriever(ABC):
    """
    Abstract base class for all retrieval pathways.
    Enforces a standard error boundary and logging signature.
    """
    @property
    @abstractmethod
    def name(self) -> str:
        """The name of the retriever (e.g. 'dense', 'keyword', 'graph')."""
        pass

    @abstractmethod
    async def _retrieve_impl(self, query: SearchQuery, context: TraversalContext) -> List[Chunk]:
        """Internal retrieval implementation to be overridden by subclasses."""
        pass

    async def retrieve(self, query: SearchQuery, context: TraversalContext) -> List[Chunk]:
        """
        Public execution entrypoint. Provides fault tolerance and standard logging.
        """
        import structlog
        import time
        logger = structlog.get_logger(__name__)
        
        start_time = time.perf_counter()
        try:
            results = await self._retrieve_impl(query, context)
            elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
            logger.info("retrieval pathway succeeded", pathway=self.name, result_count=len(results), duration_ms=elapsed_ms)
            return results
        except Exception as e:
            elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
            logger.warning(
                "retrieval pathway failed",
                pathway=self.name,
                query=query.text,
                duration_ms=elapsed_ms,
                exception_type=type(e).__name__,
                exc_info=True
            )
            return []

class FusionStrategy(ABC):
    @abstractmethod
    def fuse(self, results_groups: List[List[Chunk]]) -> List[Chunk]:
        pass

class RetrievalPipeline(ABC):
    @abstractmethod
    async def run(self, query: SearchQuery) -> RetrievalResult:
        pass

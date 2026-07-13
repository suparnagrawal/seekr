import asyncio
import time
from typing import List
import structlog

from backend.app.retrieval.interfaces import RetrievalPipeline, BaseRetriever, FusionStrategy, SearchQuery, RetrievalResult
from backend.app.retrieval.context import ContextAssembler
from backend.shared.config import settings

logger = structlog.get_logger(__name__)

class DefaultRetrievalPipeline(RetrievalPipeline):
    def __init__(self, retrievers: List[BaseRetriever], fusion_strategy: FusionStrategy, context_assembler: ContextAssembler):
        self.retrievers = retrievers
        self.fusion_strategy = fusion_strategy
        self.context_assembler = context_assembler

    async def run(self, query: SearchQuery) -> RetrievalResult:
        """
        Builds the traversal context, executes all configured retrievers concurrently, 
        and fuses the results.
        """
        start_time = time.time()
        logger.info("Starting retrieval pipeline", retrievers=[r.name for r in self.retrievers])
        
        context = await self.context_assembler.assemble(query)
        
        tasks = [r.retrieve(query, context) for r in self.retrievers]
        results_groups = await asyncio.gather(*tasks)
        
        # results_groups is a list of lists of Chunks
        fused_chunks = self.fusion_strategy.fuse(list(results_groups))
        
        logger.info("Pipeline fusion complete", total_chunks=len(fused_chunks))
        
        return RetrievalResult(
            chunks=fused_chunks[: settings.RETRIEVAL_TOP_K],
            diagnostics={"query_type": context.query_type.value},
            timings={"total_seconds": time.time() - start_time},
            pathways_used=[r.name for r in self.retrievers]
        )

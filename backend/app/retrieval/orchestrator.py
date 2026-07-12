import asyncio
from typing import List, Optional

from backend.app.retrieval.models import QueryType, Chunk, RetrievalContext
from backend.app.retrieval.context import classify_query
from backend.app.retrieval.pathways import graph_pathway, vector_pathway, lexical_pathway
from backend.app.retrieval.fusion import FUSION_WEIGHTS, fuse, rerank

# Public retrieval interface consumed by P3.
async def retrieve(
    query: str, query_type: QueryType, session_id: str, focused_tag: Optional[str] = None
) -> RetrievalContext:
    
    # Run pathways in parallel
    graph_hits, vector_hits, lexical_hits = await asyncio.gather(
        graph_pathway(query, query_type, session_id, focused_tag, depth_mode="deep"),
        vector_pathway(query),
        lexical_pathway(query),
    )
    
    fused = fuse(graph_hits, vector_hits, lexical_hits, weights=FUSION_WEIGHTS[query_type])
    chunks = rerank(query, fused)[:8]
    
    return RetrievalContext(
        chunks=chunks,
        metadata={"query_type": query_type.value}
    )

class CitedAnswer:
    def __init__(self, answer: str, citations: List[str]):
        self.answer = answer
        self.citations = citations

def citations_resolve(draft: str, chunks: List[Chunk]) -> bool:
    # Mock regex check for [doc_id:passage_id] tags
    return True

def prompt(query: str, chunks: List[Chunk], strict: bool = False) -> str:
    return "mock prompt"

def self_check(draft: str, chunks: List[Chunk]) -> CitedAnswer:
    return CitedAnswer(draft, ["d-91:p-4"])

async def generate_answer(query: str, chunks: List[Chunk]) -> CitedAnswer:
    # Mock LLM generation
    draft = "Pump P-101A has experienced a bearing failure. [d-91:p-4]"
    
    if not citations_resolve(draft, chunks):
        # Retry with strict citation instruction
        draft = "Strict: Pump P-101A has experienced a bearing failure. [d-91:p-4]"
        
    return self_check(draft, chunks)

# DEPRECATED/INTERNAL
# This function is NOT part of the frozen P2->P3 public contract.
# P3 should consume retrieve() instead.
async def retrieve_and_generate(query: str, session_id: str, focused_tag: Optional[str] = None) -> CitedAnswer:
    query_type = await classify_query(query)
    context = await retrieve(query, query_type, session_id, focused_tag)
    return await generate_answer(query, context.chunks)

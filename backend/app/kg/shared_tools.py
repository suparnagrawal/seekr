from backend.app.retrieval.models import QueryType, GraphContext
from backend.app.retrieval.interfaces import SearchQuery
from backend.app.retrieval.retrievers.graph import GraphRetriever
from backend.app.retrieval.orchestrator import get_context_assembler

# Knowledge graph retrieval tool exposed to P3.
async def context_graph_query(
    tag: str, query: str, depth: str = "auto", include_analogues: bool = False
) -> GraphContext:
    """
    Enhanced graph query tool for agents.
    
    'shallow': fixed-depth traversal only, max_depth=2 (fast, ~100ms)
    'deep': full five-phase context-aware pipeline, max_depth=5 (~300-500ms)
    'auto': shallow for Asset (history mode)/Comply, deep for Diagnose.
    """
    
    assembler = get_context_assembler()
    q_type = await assembler.classify_query(query)
    
    if depth == "auto":
        depth = "deep" if q_type == QueryType.DIAGNOSTIC else "shallow"
        
    search_query = SearchQuery(
        text=query, 
        session_id="agent_session", 
        focused_tag=tag, 
        query_type=q_type
    )
    
    assembler = get_context_assembler()
    traversal_context = await assembler.assemble(search_query)
    
    retriever = GraphRetriever()
    passages = await retriever.retrieve(search_query, traversal_context)
    
    return GraphContext(passages=passages)

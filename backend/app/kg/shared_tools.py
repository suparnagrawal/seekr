from typing import Optional, List, Any
from backend.app.retrieval.models import QueryType, Chunk, GraphContext
from backend.app.retrieval.pathways import graph_pathway

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
    
    # We resolve "auto" based on context, here we mock the choice
    if depth == "auto":
        depth = "shallow"
        
    # The agent provides the tag. We treat the agent's question as the query.
    # We'll pass the agent's explicit tag as the focused_tag for traversal context
    
    # query_type for Agent calls usually maps to OPEN or DIAGNOSTIC. 
    # Let's mock it to DIAGNOSTIC for now if not provided
    q_type = QueryType.DIAGNOSTIC
    
    passages = await graph_pathway(
        query=query, 
        query_type=q_type, 
        session_id="agent_session", 
        focused_tag=tag, 
        depth_mode=depth
    )
    
    return GraphContext(passages=passages)

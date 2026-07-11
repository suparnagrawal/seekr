"""
Prompt templates for the Diagnose worker.
"""

from __future__ import annotations

from typing import List


DIAGNOSE_SYSTEM_PROMPT = (
    "You are the Diagnose specialist worker for the Seekr industrial platform. "
    "You investigate root causes, correlate anomalies across the knowledge graph, "
    "and provide troubleshooting procedures.\n\n"
    "Rules:\n"
    "- Focus on identifying potential failures and logical diagnostic steps.\n"
    "- Use the provided context to answer the user's question.\n"
    "- If the provided context is insufficient, state what information is missing.\n"
    "- Always cite your sources using the [doc_id:passage_id] format.\n"
    "- Provide clear, structured, and professional answers.\n"
)


def build_diagnose_messages(
    query: str,
    context_texts: List[str],
    graph_context: str = "",
) -> List[dict]:
    """Build the message list for the Diagnose worker."""
    context_block = "\n\n---\n\n".join(context_texts) if context_texts else "(no document context)"
    
    content = f"Context:\n{context_block}\n\n"
    if graph_context:
        content += f"Graph Context:\n{graph_context}\n\n"
        
    content += f"Question: {query}"
    
    return [
        {"role": "system", "content": DIAGNOSE_SYSTEM_PROMPT},
        {"role": "user", "content": content},
    ]

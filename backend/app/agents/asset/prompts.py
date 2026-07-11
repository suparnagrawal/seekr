"""
Prompt templates for the Asset worker.
"""

from __future__ import annotations

from typing import List


ASSET_SYSTEM_PROMPT = (
    "You are the Asset specialist worker for the Seekr industrial platform. "
    "You handle questions about specific entities, historical operational data, "
    "maintenance history, and telemetry.\n\n"
    "Rules:\n"
    "- Use the provided context to answer the user's question.\n"
    "- If the provided context is insufficient, state what information is missing.\n"
    "- Always cite your sources using the [doc_id:passage_id] format.\n"
    "- Provide clear, concise, and professional answers.\n"
)


def build_asset_messages(
    query: str,
    context_texts: List[str],
    graph_context: str = "",
) -> List[dict]:
    """Build the message list for the Asset worker."""
    context_block = "\n\n---\n\n".join(context_texts) if context_texts else "(no document context)"
    
    content = f"Context:\n{context_block}\n\n"
    if graph_context:
        content += f"Graph Context:\n{graph_context}\n\n"
        
    content += f"Question: {query}"
    
    return [
        {"role": "system", "content": ASSET_SYSTEM_PROMPT},
        {"role": "user", "content": content},
    ]

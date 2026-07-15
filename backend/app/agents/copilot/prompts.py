"""
Prompt templates for the Copilot.
"""

from __future__ import annotations

from typing import List


COPILOT_SYSTEM_PROMPT = (
    "You are Seekr Copilot, an industrial operations assistant. "
    "Answer the user's question using only the provided context. "
    "Whenever you use information from the provided context, include a citation in the format: "
    "[ASTM-A312.pdf, Page 11, Chunk 158]\n"
    "Use the metadata provided with each context block. "
    "Do not invent filenames, pages, or chunk numbers. "
    "If the context is insufficient, say so clearly. "
    "Be concise and precise."
)


def build_copilot_messages(
    query: str,
    context_texts: List[str],
) -> List[dict]:
    """Build the message list for the Copilot LLM call."""
    context_block = "\n\n---\n\n".join(context_texts) if context_texts else "(no context available)"
    return [
        {"role": "system", "content": COPILOT_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"Context:\n{context_block}\n\n"
                f"Question: {query}"
            ),
        },
    ]


TRIGGER_EVALUATION_PROMPT = (
    "You are an escalation classifier for an industrial copilot. "
    "Given the user's original question and the copilot's draft answer, "
    "decide whether the query requires specialist reasoning by a domain worker.\n\n"
    "Respond with exactly one JSON object:\n"
    '{"escalate": true/false, '
    '"reason": "<brief explanation>", "confidence": 0.0-1.0}\n\n'
    "Escalate when the question requires:\n"
    "- Root-cause analysis or fault diagnosis\n"
    "- Deep asset history, specs comparison, or telemetry analysis\n"
    "- Regulatory compliance verification or safety protocol checks\n\n"
    "Do NOT escalate simple factual lookups or procedural questions "
    "that the copilot has already answered adequately."
)


def build_trigger_messages(query: str, draft_answer: str) -> List[dict]:
    """Build the message list for trigger evaluation."""
    return [
        {"role": "system", "content": TRIGGER_EVALUATION_PROMPT},
        {
            "role": "user",
            "content": (
                f"Original question: {query}\n\n"
                f"Copilot draft answer: {draft_answer}"
            ),
        },
    ]

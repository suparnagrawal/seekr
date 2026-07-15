"""
Reusable SSE streaming utilities for the P3 Agent layer.

These helpers emit the frozen SSE event types defined in the streaming
contract (see docs/p3_architecture.md § 6). They produce correctly formatted
Server-Sent Event strings that can be yielded from any async generator
backing a FastAPI StreamingResponse.

Supported event types:
    token, citation, agent_trigger, reasoning,
    tool_call, tool_result, error, done
"""

from __future__ import annotations

import json
from typing import Any, Dict, Optional, List

__all__ = [
    "emit_token",
    "emit_citation",
    "emit_agent_trigger",
    "emit_reasoning",
    "emit_tool_call",
    "emit_tool_result",
    "emit_error",
    "emit_done",
]

def _format_sse(event: str, data: Dict[str, Any]) -> str:
    """Format a single SSE frame with the given event name and JSON payload."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"

def emit_token(text: str) -> str:
    """Emit a token event containing a chunk of generated text."""
    return _format_sse("token", {"text": text})

def emit_citation(
    doc_id: str,
    filename: str,
    passage_id: str,
    chunk_index: int,
    page_numbers: List[int],
    headings: List[str],
    page: Optional[int] = None,
) -> str:
    """Emit a citation event referencing a source passage."""
    payload: Dict[str, Any] = {
        "doc_id": doc_id,
        "filename": filename,
        "passage_id": passage_id,
        "chunk_index": chunk_index,
        "page_numbers": page_numbers,
        "headings": headings,
    }
    if page is not None:
        payload["page"] = page
    return _format_sse("citation", payload)


def emit_agent_trigger(worker: str, job_id: str) -> str:
    """Emit an agent_trigger event indicating escalation to a specialist worker."""
    return _format_sse("agent_trigger", {"worker": worker, "job_id": job_id})


def emit_reasoning(content: str) -> str:
    """Emit a reasoning event containing a step of worker reasoning."""
    return _format_sse("reasoning", {"content": content})


def emit_tool_call(tool_name: str, tool_args: Dict[str, Any]) -> str:
    """Emit a tool_call event when a worker invokes a retrieval tool."""
    return _format_sse("tool_call", {"tool_name": tool_name, "tool_args": tool_args})


def emit_tool_result(tool_name: str, result: Any) -> str:
    """Emit a tool_result event containing the output of a tool invocation."""
    return _format_sse("tool_result", {"tool_name": tool_name, "result": result})


def emit_error(message: str, code: Optional[str] = None) -> str:
    """Emit an error event. This may precede done in exceptional cases."""
    payload: Dict[str, Any] = {"message": message}
    if code is not None:
        payload["code"] = code
    return _format_sse("error", payload)


def emit_done(answer_id: str) -> str:
    """
    Emit the done event. This is always the final event in a stream.

    Contract rules:
    - done is emitted exactly once per request lifecycle.
    - No event may follow done.
    """
    return _format_sse("done", {"answer_id": answer_id})

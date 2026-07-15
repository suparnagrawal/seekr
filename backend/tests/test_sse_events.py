"""
Tests for the SSE streaming helpers in backend.app.agents.shared.streaming.

Assertions are aligned to the ACTUAL contract defined in streaming.py:
- Each helper emits a NAMED event (e.g. "token", "citation", "error", "done").
- Payloads are function-specific dicts; there is no generic "type" wrapper.
"""

import json
from backend.app.agents.shared.streaming import (
    emit_token,
    emit_error,
    emit_done,
    emit_citation,
    emit_tool_call,
    emit_tool_result,
    emit_agent_trigger,
    emit_reasoning,
)


def _parse_sse(raw: str):
    """Extract (event_name, parsed_data) from a raw SSE frame."""
    lines = raw.strip().split("\n")
    event_name = lines[0].split("event: ", 1)[1]
    data_str = lines[1].split("data: ", 1)[1]
    return event_name, json.loads(data_str)


def test_emit_token():
    event_name, data = _parse_sse(emit_token("hello"))
    assert event_name == "token"
    assert data == {"text": "hello"}


def test_emit_token_empty():
    event_name, data = _parse_sse(emit_token(""))
    assert event_name == "token"
    assert data["text"] == ""


def test_emit_error():
    event_name, data = _parse_sse(emit_error("bad error"))
    assert event_name == "error"
    assert data["message"] == "bad error"
    assert "code" not in data  # code is optional, not included when None


def test_emit_error_with_code():
    event_name, data = _parse_sse(emit_error("rate limited", code="429"))
    assert event_name == "error"
    assert data["message"] == "rate limited"
    assert data["code"] == "429"


def test_emit_done():
    event_name, data = _parse_sse(emit_done("answer_123"))
    assert event_name == "done"
    assert data == {"answer_id": "answer_123"}


def test_emit_citation():
    event_name, data = _parse_sse(
        emit_citation(
            doc_id="doc1",
            filename="report.pdf",
            passage_id="chunk1",
            chunk_index=3,
            page_numbers=[1, 2],
            headings=["Introduction"],
            page=42,
        )
    )
    assert event_name == "citation"
    assert data["doc_id"] == "doc1"
    assert data["filename"] == "report.pdf"
    assert data["passage_id"] == "chunk1"
    assert data["chunk_index"] == 3
    assert data["page_numbers"] == [1, 2]
    assert data["headings"] == ["Introduction"]
    assert data["page"] == 42


def test_emit_citation_no_page():
    """When page is None it should be omitted from the payload entirely."""
    event_name, data = _parse_sse(
        emit_citation(
            doc_id="doc2",
            filename="spec.pdf",
            passage_id="chunk5",
            chunk_index=0,
            page_numbers=[],
            headings=[],
        )
    )
    assert event_name == "citation"
    assert "page" not in data


def test_emit_tool_call():
    event_name, data = _parse_sse(emit_tool_call("search", {"q": "test"}))
    assert event_name == "tool_call"
    assert data["tool_name"] == "search"
    assert data["tool_args"] == {"q": "test"}


def test_emit_tool_result():
    event_name, data = _parse_sse(emit_tool_result("search", "found it"))
    assert event_name == "tool_result"
    assert data["tool_name"] == "search"
    assert data["result"] == "found it"


def test_emit_agent_trigger():
    event_name, data = _parse_sse(emit_agent_trigger("diagnose", "j-abc123"))
    assert event_name == "agent_trigger"
    assert data["worker"] == "diagnose"
    assert data["job_id"] == "j-abc123"


def test_emit_reasoning():
    event_name, data = _parse_sse(emit_reasoning("Analyzing pump P-101"))
    assert event_name == "reasoning"
    assert data["content"] == "Analyzing pump P-101"


def test_sse_frame_format():
    """All SSE frames must end with a double newline for proper streaming."""
    for frame in [
        emit_token("x"),
        emit_error("e"),
        emit_done("id"),
        emit_tool_call("t", {}),
        emit_tool_result("t", "r"),
        emit_agent_trigger("w", "j"),
        emit_reasoning("r"),
    ]:
        assert frame.endswith("\n\n"), f"Frame does not end with \\n\\n: {frame!r}"

import pytest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock

from backend.app.agents.shared.worker_utils import stream_generation_and_citations
from backend.app.agents.shared.state import AgentState

@pytest.mark.asyncio
async def test_citation_hallucination_regeneration():
    # We want to test that if the LLM hallucinates a citation that doesn't exist in the context,
    # the function intercepts it and triggers a regeneration.
    
    state = AgentState(
        session_id="test",
        query="test query",
        retrieval_context={"chunks": [{"payload": {"filename": "real.txt", "chunk_index": 0}}]}
    )

    # First attempt: hallucinates "fake-fact"
    # Second attempt: uses "real-fact"
    
    call_count = 0
    async def mock_generate_streaming(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            yield 'Here is a fact [fake.txt, chunk 0].'
        else:
            yield 'Here is a fact [real.txt, chunk 0].'
            
    with patch("backend.app.agents.shared.worker_utils.generate_streaming", new=mock_generate_streaming):
        events = []
        async for event in stream_generation_and_citations([{"role": "user", "content": "hi"}], state):
            events.append(event)
            
    # Should see the correction event
    assert any("Self-Correction" in str(e) for e in events)
    # The final output should have the real citation
    assert call_count == 2

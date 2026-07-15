import pytest
from backend.app.agents.supervisor.router import route
from backend.app.agents.shared.state import EscalationContext, WorkerType
import backend.app.agents.supervisor.router as router_module

@pytest.mark.asyncio
async def test_supervisor_llm_route(monkeypatch):
    async def mock_generate(*args, **kwargs):
        return '{"worker": "diagnose"}'
        
    monkeypatch.setattr(router_module, "generate", mock_generate)
    
    escalation = EscalationContext(query="Why did the pump fail?", session_id="s1", trigger_reason="", thread_id="", retrieval_context={}, conversation={"messages": [], "session_id": "s1"})
    worker = await route(escalation)
    
    assert worker == WorkerType.DIAGNOSE

@pytest.mark.asyncio
async def test_supervisor_fallback_diagnose(monkeypatch):
    async def mock_generate_raise(*args, **kwargs):
        raise Exception("LLM down")
        
    monkeypatch.setattr(router_module, "generate", mock_generate_raise)
    
    escalation = EscalationContext(query="What is the root cause?", session_id="s1", trigger_reason="", thread_id="", retrieval_context={}, conversation={"messages": [], "session_id": "s1"})
    worker = await route(escalation)
    
    assert worker == WorkerType.DIAGNOSE

@pytest.mark.asyncio
async def test_supervisor_fallback_comply(monkeypatch):
    async def mock_generate_raise(*args, **kwargs):
        raise Exception("LLM down")
        
    monkeypatch.setattr(router_module, "generate", mock_generate_raise)
    
    escalation = EscalationContext(query="What is the compliance regulation?", session_id="s1", trigger_reason="", thread_id="", retrieval_context={}, conversation={"messages": [], "session_id": "s1"})
    worker = await route(escalation)
    
    assert worker == WorkerType.COMPLIANCE

@pytest.mark.asyncio
async def test_supervisor_fallback_default(monkeypatch):
    async def mock_generate_raise(*args, **kwargs):
        raise Exception("LLM down")
        
    monkeypatch.setattr(router_module, "generate", mock_generate_raise)
    
    escalation = EscalationContext(query="Tell me about the pump.", session_id="s1", trigger_reason="", thread_id="", retrieval_context={}, conversation={"messages": [], "session_id": "s1"})
    worker = await route(escalation)
    
    assert worker == WorkerType.ASSET

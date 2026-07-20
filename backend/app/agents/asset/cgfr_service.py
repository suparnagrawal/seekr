from __future__ import annotations

import json
from typing import AsyncIterator, Tuple
from backend.app.agents.shared.state import AgentState
from backend.app.agents.shared.streaming import emit_reasoning, emit_tool_call, emit_tool_result
from backend.app.agents.shared.llm import generate
from backend.app.agents.shared.cgfr_tools import find_by_type, compare_specs

async def classify_intent(query: str) -> str:
    """Determine if query is simple asset history or comparative spec matching (CGFR)."""
    messages = [
        {"role": "system", "content": "Classify the user's intent as either 'history' (asking about a specific asset's past, telemetry, or maintenance) or 'cgfr' (asking to compare specifications, find components by constraints, or evaluate compatibility). Reply with exactly one word: 'history' or 'cgfr'."},
        {"role": "user", "content": query}
    ]
    result = await generate(messages, temperature=0.0)
    return "cgfr" if "cgfr" in result.lower() else "history"

async def extract_cgfr_constraints(query: str) -> dict:
    """Extract entity type and constraints for finding candidates."""
    messages = [
        {"role": "system", "content": 'Extract the primary entity type and any constraints. Return strict JSON: {"entity_type": "Pump", "constraints": ["must be high pressure"]}'},
        {"role": "user", "content": query}
    ]
    try:
        raw = await generate(messages, temperature=0.0, response_format={"type": "json_object"})
        return json.loads(raw)
    except Exception:
        return {"entity_type": "Component", "constraints": []}

async def run_cgfr_pipeline(state: AgentState) -> AsyncIterator[Tuple[str, str]]:
    """Execute the CGFR constraint -> gather -> compare pipeline. Yields (event, graph_context_text)."""
    yield emit_reasoning("Asset worker detected Comparative Reasoning intent (CGFR)."), ""
    
    constraints = await extract_cgfr_constraints(state.query)
    entity_type = constraints.get("entity_type", "Component")
    yield emit_reasoning(f"Extracted search constraints for type '{entity_type}'."), ""
    
    yield emit_tool_call("find_by_type", {"entity_type": entity_type}), ""
    candidates = await find_by_type(entity_type)
    yield emit_tool_result("find_by_type", f"Found {len(candidates)} candidates."), ""
    
    if candidates:
        tags = [c["tag"] for c in candidates[:5]]
        yield emit_tool_call("compare_specs", {"tags": tags}), ""
        comparison_data = await compare_specs(tags)
        yield emit_tool_result("compare_specs", {"message": f"Retrieved specs for {len(tags)} entities.", "data": comparison_data}), ""
        graph_context_text = f"Comparative Spec Data:\n{json.dumps(comparison_data, indent=2)}"
    else:
        graph_context_text = f"No entities of type {entity_type} found in the graph."
        
    yield "", graph_context_text

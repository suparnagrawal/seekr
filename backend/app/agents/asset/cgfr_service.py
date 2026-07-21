from __future__ import annotations

import json
from typing import AsyncIterator, Tuple
from backend.app.agents.shared.state import AgentState
from backend.app.agents.shared.streaming import emit_reasoning, emit_tool_call, emit_tool_result
from backend.app.agents.shared.llm import generate
from backend.app.agents.shared.cgfr_tools import find_by_type, compare_specs
from backend.shared.config import settings

async def classify_intent(query: str) -> str:
    """Determine if query is simple asset history or comparative spec matching (CGFR)."""
    messages = [
        {"role": "system", "content": "Classify the user's intent as either 'history' (asking about a specific asset's past, telemetry, or maintenance) or 'cgfr' (asking to compare specifications, find components by constraints, or evaluate compatibility). Reply with exactly one word: 'history' or 'cgfr'."},
        {"role": "user", "content": query}
    ]
    result = await generate(messages, temperature=0.0, model=settings.FAST_MODEL)
    return "cgfr" if "cgfr" in result.lower() else "history"

async def extract_cgfr_constraints(query: str, focused_tag: str | None) -> dict:
    """Extract target entity tag, type and constraints for finding candidates."""
    messages = [
        {"role": "system", "content": 'Extract the primary target entity tag (if any), the entity type, and any explicitly stated constraints from the query. If the user mentions replacing or comparing to a specific component like "P-101", that is the target_tag. Return strict JSON: {"target_tag": "P-101", "entity_type": "Pump", "constraints": ["must be high pressure"]}'},
        {"role": "user", "content": f"Focused tag: {focused_tag}. Query: {query}"}
    ]
    try:
        raw = await generate(messages, temperature=0.0, response_format={"type": "json_object"}, model=settings.FAST_MODEL)
        return json.loads(raw)
    except Exception:
        return {"target_tag": focused_tag, "entity_type": "Component", "constraints": []}

async def evaluate_candidates(target_specs: dict, candidates_specs: dict, constraints: list) -> dict:
    """Programmatic/LLM Pass/Fail compatibility filtering table generation."""
    messages = [
        {"role": "system", "content": "You are a constraint evaluation engine. Given a target entity's specifications, a list of explicit constraints, and a set of candidate entities with their specifications, evaluate each candidate against the constraints and target specs to determine compatibility. Return strict JSON containing an evaluation table: {\"evaluations\": [{\"tag\": \"Candidate-Tag\", \"pass\": true, \"reasoning\": \"Meets all constraints\"}]}"},
        {"role": "user", "content": f"Target Specs: {json.dumps(target_specs)}\nConstraints: {json.dumps(constraints)}\nCandidates: {json.dumps(candidates_specs)}"}
    ]
    try:
        raw = await generate(messages, temperature=0.0, response_format={"type": "json_object"}, model=settings.FAST_MODEL)
        return json.loads(raw)
    except Exception:
        return {"evaluations": []}

async def run_cgfr_pipeline(state: AgentState) -> AsyncIterator[Tuple[str, str]]:
    """Execute the Deep CGFR pipeline: Retrieve target -> specs -> constraints -> candidates -> filter -> Pass/Fail table -> LLM synthesis."""
    yield emit_reasoning("Asset worker detected Comparative Reasoning intent (CGFR)."), ""
    
    constraints_data = await extract_cgfr_constraints(state.query, state.focused_tag)
    target_tag = constraints_data.get("target_tag") or state.focused_tag
    entity_type = constraints_data.get("entity_type", "Component")
    constraints = constraints_data.get("constraints", [])
    yield emit_reasoning(f"Extracted target '{target_tag}', type '{entity_type}', and {len(constraints)} constraints."), ""
    
    target_specs = {}
    if target_tag:
        yield emit_tool_call("compare_specs", {"tags": [target_tag]}), ""
        target_data = await compare_specs([target_tag])
        target_specs = target_data.get(target_tag, {})
        yield emit_tool_result("compare_specs", {"message": f"Retrieved specs for target {target_tag}."}), ""
    
    yield emit_tool_call("find_by_type", {"entity_type": entity_type}), ""
    candidates = await find_by_type(entity_type)
    yield emit_tool_result("find_by_type", f"Found {len(candidates)} candidates of type {entity_type}."), ""
    
    if candidates:
        tags = [c["tag"] for c in candidates[:5] if c["tag"] != target_tag]
        if not tags:
            graph_context_text = f"No other entities of type {entity_type} found to compare against."
            yield "", graph_context_text
            return
            
        yield emit_tool_call("compare_specs", {"tags": tags}), ""
        candidates_data = await compare_specs(tags)
        yield emit_tool_result("compare_specs", {"message": f"Retrieved specs for {len(tags)} candidate entities."}), ""
        
        yield emit_reasoning("Evaluating candidates against constraints and target specifications to generate Pass/Fail table..."), ""
        eval_table = await evaluate_candidates(target_specs, candidates_data, constraints)
        
        # Combine everything for the final LLM synthesis
        synthesis_context = {
            "target": target_specs,
            "candidates": candidates_data,
            "constraints_evaluated": constraints,
            "evaluation_table": eval_table.get("evaluations", [])
        }
        
        graph_context_text = f"Deep CGFR Evaluation Results (Use this pre-computed reasoning table to synthesize your final answer):\n{json.dumps(synthesis_context, indent=2)}"
    else:
        graph_context_text = f"No candidates of type {entity_type} found in the graph."
        
    yield "", graph_context_text

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
    """Extract target entity tag, type and structured constraints."""
    messages = [
        {"role": "system", "content": 'Extract the primary target entity tag (if any), the entity type, and any explicitly stated constraints from the query. If the user mentions replacing or comparing to a specific component like "P-101", that is the target_tag. For numeric/logical constraints, extract them as rules: {"field": "pressure", "operator": ">", "value": 100}. Return strict JSON: {"target_tag": "P-101", "entity_type": "Pump", "rules": [{"field": "pressure", "operator": ">=", "value": 150}], "narrative_constraints": ["must be durable"]}'},
        {"role": "user", "content": f"Focused tag: {focused_tag}. Query: {query}"}
    ]
    try:
        raw = await generate(messages, temperature=0.0, response_format={"type": "json_object"}, model=settings.FAST_MODEL)
        return json.loads(raw)
    except Exception:
        return {"target_tag": focused_tag, "entity_type": "Component", "rules": [], "narrative_constraints": []}

import re
import operator

def _parse_numeric(val) -> float | None:
    if isinstance(val, (int, float)): return float(val)
    if isinstance(val, str):
        matches = re.findall(r'[-+]?\d*\.\d+|\d+', val)
        if matches: return float(matches[0])
    return None

def _evaluate_rule(rule: dict, spec: dict) -> bool:
    field = rule.get("field")
    op_str = rule.get("operator", "==")
    target_val = rule.get("value")
    
    # We search the spec dictionary keys loosely matching the field
    spec_val = None
    if field in spec:
        spec_val = spec[field]
    else:
        for k, v in spec.items():
            if field.lower() in k.lower():
                spec_val = v
                break
                
    if spec_val is None:
        return False
        
    v1 = _parse_numeric(spec_val)
    v2 = _parse_numeric(target_val)
    
    if v1 is not None and v2 is not None:
        ops = {">": operator.gt, ">=": operator.ge, "<": operator.lt, "<=": operator.le, "==": operator.eq, "=": operator.eq, "!=": operator.ne}
        op_func = ops.get(op_str, operator.eq)
        try:
            return op_func(v1, v2)
        except Exception:
            return False
            
    if op_str in ("==", "="):
        return str(spec_val).lower() == str(target_val).lower()
    return False

def programmatic_filter(candidates_specs: dict, rules: list) -> list:
    evals = []
    for tag, spec in candidates_specs.items():
        passed = True
        failed_rules = []
        for r in rules:
            if not _evaluate_rule(r, spec):
                passed = False
                failed_rules.append(r)
        evals.append({"tag": tag, "pass_programmatic": passed, "failed_rules": failed_rules})
    return evals

async def evaluate_candidates(target_specs: dict, candidates_specs: dict, rules: list, narrative: list) -> dict:
    """Programmatic rule evaluation + LLM narrative explanation."""
    prog_evals = programmatic_filter(candidates_specs, rules)
    
    messages = [
        {"role": "system", "content": "You are a constraint evaluation engine. Review the programmatic Pass/Fail evaluation results and the narrative constraints. Output a final evaluation table with explanations. Return strict JSON: {\"evaluations\": [{\"tag\": \"Candidate-Tag\", \"pass\": true, \"reasoning\": \"Passed programmatic rules and meets narrative ...\"}]}"},
        {"role": "user", "content": f"Programmatic Eval: {json.dumps(prog_evals)}\nNarrative Constraints: {json.dumps(narrative)}\nCandidates: {json.dumps(candidates_specs)}"}
    ]
    try:
        raw = await generate(messages, temperature=0.0, response_format={"type": "json_object"}, model=settings.FAST_MODEL)
        return json.loads(raw)
    except Exception:
        return {"evaluations": prog_evals}

async def run_cgfr_pipeline(state: AgentState) -> AsyncIterator[Tuple[str, str]]:
    """Execute the Deep CGFR pipeline: Retrieve target -> specs -> constraints -> candidates -> filter -> Pass/Fail table -> LLM synthesis."""
    yield emit_reasoning("Asset worker detected Comparative Reasoning intent (CGFR)."), ""
    
    constraints_data = await extract_cgfr_constraints(state.query, state.focused_tag)
    target_tag = constraints_data.get("target_tag") or state.focused_tag
    entity_type = constraints_data.get("entity_type", "Component")
    rules = constraints_data.get("rules", [])
    narrative = constraints_data.get("narrative_constraints", [])
    yield emit_reasoning(f"Extracted target '{target_tag}', type '{entity_type}', with {len(rules)} programmatic rules and {len(narrative)} narrative constraints."), ""
    
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
        
        yield emit_reasoning("Evaluating candidates programmatically against numeric rules, and synthesizing narrative context..."), ""
        eval_table = await evaluate_candidates(target_specs, candidates_data, rules, narrative)
        
        # Combine everything for the final LLM synthesis
        synthesis_context = {
            "target": target_specs,
            "candidates": candidates_data,
            "rules_evaluated": rules,
            "narrative_evaluated": narrative,
            "evaluation_table": eval_table.get("evaluations", [])
        }
        
        graph_context_text = f"Deep CGFR Evaluation Results (Use this pre-computed reasoning table to synthesize your final answer):\n{json.dumps(synthesis_context, indent=2)}"
    else:
        graph_context_text = f"No candidates of type {entity_type} found in the graph."
        
    yield "", graph_context_text

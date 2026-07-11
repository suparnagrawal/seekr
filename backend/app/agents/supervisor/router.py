"""
Supervisor routing logic.

The Supervisor is responsible ONLY for routing. It receives an
EscalationContext and determines which specialist worker should handle it.

The Supervisor NEVER:
- performs retrieval
- invokes an LLM for generation
- builds prompts for answer generation
- performs reasoning
- accesses databases
"""

import json
import re
from typing import Optional

from backend.app.agents.shared.state import EscalationContext, WorkerType
from backend.app.agents.shared.logging import get_logger, log_routing
from backend.app.agents.shared.llm import generate

logger = get_logger("supervisor.router")

ROUTING_PROMPT = (
    "You are the routing Supervisor for an industrial AI agent platform. "
    "Given the user's original query, the Copilot's reason for escalation, and the available "
    "retrieval context, determine which specialist worker should handle the request.\n\n"
    "Respond with exactly one JSON object:\n"
    '{"worker": "asset" | "diagnose" | "comply"}\n\n'
    "- diagnose: Root-cause analysis, failure investigation, or troubleshooting.\n"
    "- asset: Deep asset history, specs comparison, telemetry data, or maintenance records.\n"
    "- comply: Regulatory compliance, safety protocol verification, or audit standards."
)

# Keyword patterns for deterministic routing fallback
_ROUTING_PATTERNS = {
    WorkerType.DIAGNOSE: [
        "root cause", "failure", "fault", "malfunction", "diagnos",
        "troubleshoot", "why", "keeps failing", "anomal",
    ],
    WorkerType.COMPLIANCE: [
        "compliance", "regulation", "safety", "standard", "iso",
        "osha", "api 610", "protocol", "audit", "certif",
    ],
    WorkerType.ASSET: [
        "asset", "history", "maintenance", "spec", "telemetry",
        "operational data", "compare", "model", "serial",
    ],
}


async def route(escalation: EscalationContext) -> WorkerType:
    """
    Determine which specialist worker should handle the escalated query.

    Routing strategy:
    1. LLM-based routing using query and trigger reason.
    2. Fall back to keyword-based routing on query + reason if LLM fails.
    3. If nothing matches, default to the Asset worker and log the fallback.

    The Supervisor must always resolve to exactly one worker. It must
    never silently terminate or leave the request unresolved.
    """
    # Strategy 1: LLM-based routing
    messages = [
        {"role": "system", "content": ROUTING_PROMPT},
        {"role": "user", "content": f"Query: {escalation.query}\nTrigger Reason: {escalation.trigger_reason}"}
    ]
    
    try:
        raw = await generate(messages, temperature=0.1, max_tokens=128)
        
        match = re.search(r'\{.*\}', raw.strip(), re.DOTALL)
        json_str = match.group(0) if match else raw.strip()
            
        result = json.loads(json_str)
        worker_raw = result.get("worker")

        worker_map = {
            "asset": WorkerType.ASSET,
            "diagnose": WorkerType.DIAGNOSE,
            "comply": WorkerType.COMPLIANCE,
        }
        worker = worker_map.get(worker_raw)
        
        if worker is not None:
            log_routing(
                logger,
                session_id=escalation.session_id,
                selected_worker=worker.value,
                confidence=0.9,
                reason=f"llm_routing_decision",
            )
            return worker
            
        logger.warning(
            "unknown_worker_in_router",
            session_id=escalation.session_id,
            worker_raw=worker_raw,
        )

    except Exception as exc:
        logger.warning(
            "llm_routing_failed",
            session_id=escalation.session_id,
            error=str(exc),
        )

    # Strategy 2: Keyword-based routing fallback
    search_text = (escalation.query + " " + escalation.trigger_reason).lower()
    for worker_type, patterns in _ROUTING_PATTERNS.items():
        if any(pattern in search_text for pattern in patterns):
            log_routing(
                logger,
                session_id=escalation.session_id,
                selected_worker=worker_type.value,
                confidence=0.7,
                reason=f"keyword_fallback: {worker_type.value}",
            )
            return worker_type

    # Strategy 3: Logged fallback — always resolves
    logger.warning(
        "routing_fallback_default",
        session_id=escalation.session_id,
        query=escalation.query,
    )
    log_routing(
        logger,
        session_id=escalation.session_id,
        selected_worker=WorkerType.ASSET.value,
        confidence=0.3,
        reason="fallback_default",
    )
    return WorkerType.ASSET

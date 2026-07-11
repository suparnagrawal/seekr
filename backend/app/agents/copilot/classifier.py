"""
Trigger evaluation — determines whether the Copilot should escalate
to a specialist worker after generating its initial answer.
"""

from __future__ import annotations

import json
import re
from typing import Tuple

from backend.app.agents.shared.llm import generate
from backend.app.agents.shared.logging import get_logger
from backend.app.agents.copilot.prompts import build_trigger_messages

logger = get_logger("copilot.classifier")

ESCALATION_CONFIDENCE_THRESHOLD = 0.6


async def evaluate_trigger(
    query: str,
    draft_answer: str,
    *,
    session_id: str,
) -> Tuple[bool, str, float]:
    """
    Evaluate whether a query requires escalation to a specialist worker.

    Returns:
        (should_escalate, reason, confidence)
    """
    messages = build_trigger_messages(query, draft_answer)

    try:
        raw = await generate(messages, temperature=0.1, max_tokens=256)
        
        # Robust JSON extraction
        match = re.search(r'\{.*\}', raw.strip(), re.DOTALL)
        if match:
            json_str = match.group(0)
        else:
            json_str = raw.strip()
            
        result = json.loads(json_str)

        should_escalate = bool(result.get("escalate", False))
        confidence = float(result.get("confidence", 0.0))
        reason = str(result.get("reason", ""))

        if not should_escalate or confidence < ESCALATION_CONFIDENCE_THRESHOLD:
            return False, reason, confidence

        return True, reason, confidence

    except (json.JSONDecodeError, KeyError, ValueError) as exc:
        logger.warning(
            "trigger_evaluation_parse_error",
            session_id=session_id,
            error=str(exc),
            raw_response=raw if 'raw' in locals() else None,
        )
        return False, f"parse error: {exc}", 0.0
    except Exception as exc:
        logger.error(
            "trigger_evaluation_failed",
            session_id=session_id,
            error=str(exc),
            exc_info=True,
        )
        return False, f"evaluation error: {exc}", 0.0

"""
Shared logging helpers for the P3 Agent layer.

Uses structlog (already a project dependency) to provide structured,
JSON-friendly logging throughout the agent components.

All P3 modules should use the helpers in this file rather than calling
the stdlib logging module directly or constructing ad-hoc log lines.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

import structlog


def get_logger(component: str) -> structlog.stdlib.BoundLogger:
    """
    Return a structlog logger bound with the given component name.

    Usage:
        logger = get_logger("copilot")
        logger.info("starting query", session_id="s-123")
    """
    return structlog.get_logger(component=component)


def log_reasoning(
    logger: structlog.stdlib.BoundLogger,
    step: str,
    *,
    session_id: str,
    detail: Optional[str] = None,
) -> None:
    """Log a reasoning step within a worker or Copilot."""
    logger.info("reasoning_step", step=step, session_id=session_id, detail=detail)


def log_tool_execution(
    logger: structlog.stdlib.BoundLogger,
    tool_name: str,
    *,
    session_id: str,
    tool_args: Optional[Dict[str, Any]] = None,
    success: bool = True,
    error: Optional[str] = None,
) -> None:
    """Log the invocation of a retrieval tool by a worker."""
    logger.info(
        "tool_execution",
        tool_name=tool_name,
        session_id=session_id,
        tool_args=tool_args,
        success=success,
        error=error,
    )


def log_routing(
    logger: structlog.stdlib.BoundLogger,
    *,
    session_id: str,
    selected_worker: str,
    confidence: float,
    reason: str,
) -> None:
    """Log the Supervisor's routing decision."""
    logger.info(
        "routing_decision",
        session_id=session_id,
        selected_worker=selected_worker,
        confidence=confidence,
        reason=reason,
    )


def log_error(
    logger: structlog.stdlib.BoundLogger,
    message: str,
    *,
    session_id: str,
    error_code: Optional[str] = None,
    exc_info: bool = False,
) -> None:
    """Log an error encountered during agent execution."""
    logger.error(
        "agent_error",
        message=message,
        session_id=session_id,
        error_code=error_code,
        exc_info=exc_info,
    )


def log_worker_lifecycle(
    logger: structlog.stdlib.BoundLogger,
    event: str,
    *,
    worker: str,
    session_id: str,
    detail: Optional[str] = None,
) -> None:
    """
    Log a worker lifecycle event (e.g. started, completed, failed).

    Usage:
        log_worker_lifecycle(logger, "started", worker="diagnose", session_id="s-1")
        log_worker_lifecycle(logger, "completed", worker="diagnose", session_id="s-1")
    """
    logger.info(
        "worker_lifecycle",
        lifecycle_event=event,
        worker=worker,
        session_id=session_id,
        detail=detail,
    )

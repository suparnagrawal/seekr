"""
Lightweight audit-logging service.

Usage::

    from backend.shared.audit import audit_log
    await audit_log("query", "copilot", session_id=sid, detail={"query": q})
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, Optional

import structlog

logger = structlog.get_logger(__name__)


async def audit_log(
    action: str,
    resource_type: str,
    *,
    resource_id: Optional[str] = None,
    actor: str = "system",
    session_id: Optional[str] = None,
    detail: Optional[Dict[str, Any]] = None,
) -> None:
    """Write an audit entry.  Best-effort: failures are logged but never
    propagate to the caller — audit logging must not break the happy path."""
    from backend.shared.database import pg_pool
    import json
    import datetime

    try:
        async with pg_pool.connection() as conn:
            # We use an async cursor to execute the INSERT
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    INSERT INTO audit_log (id, timestamp, actor, action, resource_type, resource_id, detail, session_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        str(uuid.uuid4()),
                        datetime.datetime.utcnow(),
                        actor,
                        action,
                        resource_type,
                        resource_id,
                        json.dumps(detail) if detail else None,
                        session_id
                    )
                )
    except Exception:
        logger.warning("audit_log_write_failed", action=action, exc_info=True)

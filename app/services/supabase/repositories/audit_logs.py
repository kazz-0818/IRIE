from __future__ import annotations

import logging
from typing import Any

from supabase import Client

log = logging.getLogger(__name__)


def save_audit_log(
    client: Client,
    *,
    agent_id: str | None = None,
    source: str,
    event_type: str,
    detail: dict[str, Any],
    conversation_id: str | None = None,
) -> str | None:
    """
    `veliora.agent_audit_logs` へ挿入（best-effort）。
    既存 `lira.lira_audit_log` / `log_audit` は変更しない。
    """
    try:
        payload: dict[str, Any] = {
            "source": source,
            "event_type": event_type,
            "detail": detail,
        }
        if agent_id:
            payload["agent_id"] = agent_id
        if conversation_id:
            payload["conversation_id"] = conversation_id
        r = client.schema("veriora").table("agent_audit_logs").insert(payload).execute()
        rows = r.data or []
        row_id = rows[0].get("id") if rows else None
        return str(row_id) if row_id else None
    except Exception:
        log.exception("save_audit_log failed source=%s", source)
        return None

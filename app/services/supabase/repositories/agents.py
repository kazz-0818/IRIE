from __future__ import annotations

import logging
from typing import Any

from supabase import Client

log = logging.getLogger(__name__)


def get_agent_by_key(client: Client, agent_key: str) -> dict[str, Any] | None:
    """`veriora.ai_agents` から agent_key で1件取得。"""
    try:
        r = (
            client.schema("veriora")
            .table("ai_agents")
            .select("id, agent_key, display_name, department")
            .eq("agent_key", agent_key.strip().lower())
            .limit(1)
            .execute()
        )
        rows = r.data or []
        return rows[0] if rows else None
    except Exception:
        log.exception("get_agent_by_key failed agent_key=%s", agent_key)
        return None

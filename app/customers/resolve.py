"""Veliora 共通顧客マスター（IRIE / ベガパンク）— Supabase 経由の薄い接続。

接続: `app/line_routes.py` の LINE webhook（1:1 / グループ応答前）。
`app/services.py` とパッケージ名が衝突するため `app/customers/` に配置。
"""

from __future__ import annotations

import logging
import os
from typing import Any

from supabase import Client

log = logging.getLogger(__name__)

CHANNEL_KEY = "irie_line"
AGENT_KEY = "irie"


def is_customer_master_enabled() -> bool:
    v = (os.environ.get("VERIORA_CUSTOMER_MASTER_ENABLED") or "true").strip().lower()
    return v not in ("false", "0")


def resolve_customer_from_line(
    client: Client,
    line_user_id: str,
    display_name: str | None = None,
) -> str | None:
    if not is_customer_master_enabled() or not line_user_id.strip():
        return None
    try:
        schema = client.schema("veriora")
        existing = (
            schema.table("customer_identities")
            .select("customer_id")
            .eq("provider", "line")
            .eq("channel_key", CHANNEL_KEY)
            .eq("external_user_id", line_user_id.strip())
            .limit(1)
            .execute()
        )
        rows = existing.data or []
        if rows:
            return str(rows[0]["customer_id"])

        cust = (
            schema.table("customers")
            .insert({"status": "active", "metadata": {"source": "irie_resolve"}})
            .execute()
        )
        cust_rows = cust.data or []
        if not cust_rows:
            return None
        customer_id = str(cust_rows[0]["id"])

        identity: dict[str, Any] = {
            "customer_id": customer_id,
            "provider": "line",
            "channel_key": CHANNEL_KEY,
            "agent_key": AGENT_KEY,
            "external_user_id": line_user_id.strip(),
            "linked_by": "auto",
        }
        if display_name:
            identity["external_display_name"] = display_name
        schema.table("customer_identities").upsert(identity).execute()

        if display_name:
            schema.table("customers").update({"display_name": display_name}).eq("id", customer_id).execute()

        return customer_id
    except Exception:
        log.exception("resolve_customer_from_line failed")
        return None


def build_customer_context_prompt(
    client: Client,
    customer_id: str,
    agent_key: str = AGENT_KEY,
) -> str:
    if not is_customer_master_enabled():
        return ""
    try:
        schema = client.schema("veriora")
        parts: list[str] = ["【Veliora 共通顧客情報（IRIE）】"]

        cust = schema.table("customers").select("display_name,preferred_name,nickname").eq("id", customer_id).limit(1).execute()
        if cust.data:
            row = cust.data[0]
            if row.get("preferred_name"):
                parts.append(f"呼び名: {row['preferred_name']}")
            elif row.get("nickname"):
                parts.append(f"あだ名: {row['nickname']}")
            elif row.get("display_name"):
                parts.append(f"表示名: {row['display_name']}")

        notes = (
            schema.table("customer_memory_notes")
            .select("note,category")
            .eq("customer_id", customer_id)
            .eq("confirmed", True)
            .order("created_at", desc=True)
            .limit(8)
            .execute()
        )
        for row in notes.data or []:
            cat = f"[{row.get('category')}] " if row.get("category") else ""
            parts.append(f"・{cat}{row.get('note')}")

        prof = (
            schema.table("customer_profiles")
            .select("profile_key,profile_value")
            .eq("customer_id", customer_id)
            .eq("confirmed", True)
            .eq("is_sensitive", False)
            .limit(10)
            .execute()
        )
        for row in prof.data or []:
            parts.append(f"・{row.get('profile_key')}: {row.get('profile_value')}")

        if len(parts) <= 1:
            return ""
        parts.append("※ 未確認情報は断定しない。")
        return "\n".join(parts)
    except Exception:
        log.exception("build_customer_context_prompt failed")
        return ""

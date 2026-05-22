"""非LINE /ask 経路の顧客紐づけ（外部IDがある場合のみ）。"""

from __future__ import annotations

import logging
import re
from typing import Any

from supabase import Client

from app.customers.resolve import build_customer_context_prompt, resolve_customer_from_line

log = logging.getLogger(__name__)

_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.I,
)


def resolve_customer_for_ask(
    client: Client | None,
    *,
    manual_customer_id: str | None = None,
    line_user_id: str | None = None,
    email: str | None = None,
    display_name: str | None = None,
) -> tuple[str | None, str]:
    """
    customer_id とプロンプト用 context を返す。
    外部IDが無い場合は (None, "") — 新規 customer は作らない。
    """
    if client is None:
        return None, ""

    manual = (manual_customer_id or "").strip()
    if manual and _UUID_RE.match(manual):
        block = build_customer_context_prompt(client, manual)
        return manual, block

    line_uid = (line_user_id or "").strip()
    if line_uid:
        cid = resolve_customer_from_line(client, line_uid, display_name)
        if cid:
            return cid, build_customer_context_prompt(client, cid)

    mail = (email or "").strip().lower()
    if mail:
        try:
            schema = client.schema("veriora")
            row = (
                schema.table("customers")
                .select("id")
                .eq("email", mail)
                .eq("status", "active")
                .limit(1)
                .execute()
            )
            rows = row.data or []
            if rows:
                cid = str(rows[0]["id"])
                return cid, build_customer_context_prompt(client, cid)
        except Exception:
            log.debug("resolve_customer_for_ask email lookup failed", exc_info=True)

    return None, ""


def prepend_context_to_answer(answer: str, context_block: str) -> str:
    if not context_block.strip():
        return answer
    return answer

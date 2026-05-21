from __future__ import annotations

import logging
from typing import Any

from supabase import Client, create_client

from app.config import get_settings

log = logging.getLogger(__name__)


def _supabase_client() -> Client | None:
    s = get_settings()
    key = s.supabase_service_role_key
    if not s.supabase_url or not key:
        return None
    return create_client(s.supabase_url, key)


def log_audit(source: str, detail: dict[str, Any]) -> None:
    """監査ログを Supabase に挿入（失敗しても API は落とさない）。秘密は detail に含めないこと。"""
    client = _supabase_client()
    if not client:
        return
    s = get_settings()
    try:
        client.table(s.supabase_audit_table).insert({"source": source, "detail": detail}).execute()
    except Exception:
        log.exception("Supabase 監査ログの挿入に失敗しました (source=%s)", source)

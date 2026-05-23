"""LINE グループ／ルーム ID の観測ログ（Supabase irie.line_group_registry）。"""

from __future__ import annotations

import logging
from typing import Any

from app.audit_supabase import _supabase_client
from app.config import get_settings

log = logging.getLogger(__name__)

_PREVIEW_LEN = 200


def _preview(text: str | None) -> str | None:
    if not text or not str(text).strip():
        return None
    t = str(text).strip()
    return t if len(t) <= _PREVIEW_LEN else t[:_PREVIEW_LEN] + "…"


def record_line_chat_seen(
    source: dict[str, Any],
    *,
    text: str | None = None,
    respond_reason: str | None = None,
) -> str | None:
    """
    グループ／ルームの ID を Supabase に upsert（失敗しても Webhook は継続）。
    戻り値: group_id または room_id（1:1 のときは None）。
    """
    st = source.get("type")
    chat_id: str | None = None
    chat_kind: str | None = None
    if st == "group":
        gid = source.get("groupId")
        if isinstance(gid, str) and gid.strip():
            chat_id = gid.strip()
            chat_kind = "group"
    elif st == "room":
        rid = source.get("roomId")
        if isinstance(rid, str) and rid.strip():
            chat_id = rid.strip()
            chat_kind = "room"
    if not chat_id or not chat_kind:
        return None

    preview = _preview(text)
    client = _supabase_client()
    if client is None:
        log.info(
            "LINE chat observed (no supabase): kind=%s id=%s preview=%s",
            chat_kind,
            chat_id,
            (preview or "")[:80],
        )
        return chat_id

    try:
        client.rpc(
            "upsert_irie_line_group_registry",
            {
                "p_chat_id": chat_id,
                "p_chat_kind": chat_kind,
                "p_last_text_preview": preview,
                "p_last_respond_reason": respond_reason,
            },
        ).execute()
    except Exception:
        log.debug("line_group_registry upsert failed", exc_info=True)
        log.info(
            "LINE chat observed: kind=%s id=%s preview=%s",
            chat_kind,
            chat_id,
            (preview or "")[:80],
        )
    return chat_id


def is_main_line_group(source: dict[str, Any]) -> bool:
    """LINE_MAIN_GROUP_ID が設定されていれば、そのグループ／ルームのみ True。"""
    main_id = (get_settings().line_main_group_id or "").strip()
    if not main_id:
        return False
    st = source.get("type")
    if st == "group":
        return source.get("groupId") == main_id
    if st == "room":
        return source.get("roomId") == main_id
    return False

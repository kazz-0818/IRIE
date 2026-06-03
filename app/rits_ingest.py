"""RITS POST /admin/logs — 会話ログ転送（env 未設定時は no-op）。"""

from __future__ import annotations

import json
import logging
import os
import time
import urllib.error
import urllib.request
from typing import Any

log = logging.getLogger(__name__)

AGENT_NAME = "IRIE"
_MAX = 4000


def _clip(text: str | None, max_len: int = _MAX) -> str | None:
    if not text or not str(text).strip():
        return None
    t = str(text).strip()
    return t if len(t) <= max_len else t[:max_len] + "…"


def _group_observe_enabled() -> bool:
    v = (os.environ.get("VERIORA_RITS_GROUP_OBSERVE") or "").strip().lower()
    return v not in ("0", "false", "off", "no")


def _line_context_metadata(
    *,
    group_id: str | None = None,
    room_id: str | None = None,
    line_source_type: str | None = None,
    actor_user_id: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    meta: dict[str, Any] = dict(extra or {})
    if group_id:
        meta["group_id"] = group_id
    if room_id:
        meta["room_id"] = room_id
    if line_source_type:
        meta["line_source_type"] = line_source_type
    if actor_user_id:
        meta["actor_user_id"] = actor_user_id
    return meta


def send_agent_log_to_rits(
    *,
    user_message: str | None = None,
    agent_reply: str | None = None,
    intent: str | None = None,
    source: str = "line",
    metadata: dict[str, Any] | None = None,
) -> None:
    base = (os.environ.get("VERIORA_RITS_BASE_URL") or "").strip().rstrip("/")
    key = (os.environ.get("VERIORA_RITS_ADMIN_API_KEY") or "").strip()
    if not base or len(key) < 12:
        return

    body = {
        "agent_name": AGENT_NAME,
        "user_message": _clip(user_message),
        "agent_reply": _clip(agent_reply),
        "intent": intent,
        "source": source,
        "metadata": metadata or {},
    }
    url = f"{base}/admin/logs"
    retryable = {429, 502, 503, 504}
    for attempt in range(4):
        if attempt > 0:
            time.sleep(0.5 * attempt)
        else:
            try:
                urllib.request.urlopen(f"{base}/health", timeout=12)
            except Exception:
                pass
        req = urllib.request.Request(
            url,
            data=json.dumps(body).encode("utf-8"),
            method="POST",
            headers={
                "Content-Type": "application/json",
                "x-admin-api-key": key,
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=12) as res:
                if res.status < 400:
                    return
                if res.status not in retryable or attempt >= 3:
                    log.warning("LIRA send_agent_log_to_rits HTTP %s", res.status)
                    return
        except urllib.error.HTTPError as e:
            if e.code not in retryable or attempt >= 3:
                log.warning("LIRA send_agent_log_to_rits HTTP %s", e.code)
                return
        except Exception:
            if attempt >= 3:
                log.debug("send_agent_log_to_rits failed", exc_info=True)
                return


def record_line_exchange_to_rits(
    *,
    user_text: str,
    agent_reply: str,
    group_id: str | None = None,
    room_id: str | None = None,
    line_source_type: str | None = None,
    actor_user_id: str | None = None,
) -> None:
    send_agent_log_to_rits(
        user_message=user_text,
        agent_reply=agent_reply,
        intent="line",
        source="line",
        metadata=_line_context_metadata(
            group_id=group_id,
            room_id=room_id,
            line_source_type=line_source_type,
            actor_user_id=actor_user_id,
        ),
    )


def record_group_observe_to_rits(
    *,
    user_text: str,
    skip_reason: str,
    group_id: str | None = None,
    room_id: str | None = None,
    line_source_type: str | None = None,
    actor_user_id: str | None = None,
) -> None:
    if not _group_observe_enabled():
        return
    clipped = _clip(user_text)
    if not clipped:
        return
    send_agent_log_to_rits(
        user_message=clipped,
        agent_reply=None,
        intent="group_observe",
        source="line",
        metadata=_line_context_metadata(
            group_id=group_id,
            room_id=room_id,
            line_source_type=line_source_type,
            actor_user_id=actor_user_id,
            extra={"observe_only": True, "skip_reason": skip_reason},
        ),
    )

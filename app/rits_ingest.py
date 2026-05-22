"""RITS POST /admin/logs — 会話ログ転送（env 未設定時は no-op）。"""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request
from typing import Any

log = logging.getLogger(__name__)

AGENT_NAME = "LIRA"
_MAX = 4000


def _clip(text: str | None, max_len: int = _MAX) -> str | None:
    if not text or not str(text).strip():
        return None
    t = str(text).strip()
    return t if len(t) <= max_len else t[:max_len] + "…"


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
        with urllib.request.urlopen(req, timeout=8) as res:
            if res.status >= 400:
                log.warning("LIRA send_agent_log_to_rits HTTP %s", res.status)
    except urllib.error.HTTPError as e:
        log.warning("LIRA send_agent_log_to_rits HTTP %s", e.code)
    except Exception:
        log.debug("send_agent_log_to_rits failed", exc_info=True)


def record_line_exchange_to_rits(
    *,
    user_text: str,
    agent_reply: str,
    group_id: str | None = None,
) -> None:
    send_agent_log_to_rits(
        user_message=user_text,
        agent_reply=agent_reply,
        intent="line",
        source="line",
        metadata={"group_id": group_id},
    )

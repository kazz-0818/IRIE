"""LLM usage 記録（RITS POST /admin/usage 準備。API 未実装の間はログのみ）。"""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

log = logging.getLogger(__name__)

AGENT_NAME = "IRIE"


@dataclass(frozen=True)
class LlmUsagePayload:
    agent_name: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    source: str
    total_tokens: int | None = None
    metadata: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "agent_name": self.agent_name,
            "model": self.model,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "source": self.source,
        }
        if self.total_tokens is not None:
            d["total_tokens"] = self.total_tokens
        if self.metadata:
            d["metadata"] = self.metadata
        return d


def usage_from_chat_completion(
    completion: Any,
    *,
    source: str,
    model: str | None = None,
) -> LlmUsagePayload | None:
    u = getattr(completion, "usage", None)
    if u is None:
        return None
    prompt = int(getattr(u, "prompt_tokens", None) or 0)
    comp = int(getattr(u, "completion_tokens", None) or 0)
    if prompt == 0 and comp == 0:
        return None
    total = getattr(u, "total_tokens", None)
    return LlmUsagePayload(
        agent_name=AGENT_NAME,
        model=model or getattr(completion, "model", None) or "unknown",
        prompt_tokens=prompt,
        completion_tokens=comp,
        total_tokens=int(total) if total is not None else prompt + comp,
        source=source,
    )


def record_llm_usage(payload: LlmUsagePayload) -> None:
    log.debug(
        "llm_usage_recorded agent=%s model=%s prompt=%s completion=%s source=%s",
        payload.agent_name,
        payload.model,
        payload.prompt_tokens,
        payload.completion_tokens,
        payload.source,
    )
    try:
        send_llm_usage_to_rits(payload)
    except Exception:
        log.debug("send_llm_usage_to_rits skipped or failed", exc_info=True)


def send_llm_usage_to_rits(payload: LlmUsagePayload) -> None:
    base = (os.environ.get("VERIORA_RITS_BASE_URL") or "").strip().rstrip("/")
    key = (os.environ.get("VERIORA_RITS_ADMIN_API_KEY") or "").strip()
    if not base or len(key) < 12:
        return

    url = f"{base}/admin/usage"
    body = json.dumps(payload.to_dict()).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "x-admin-api-key": key,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=8) as res:
            if res.status >= 400:
                log.warning("send_llm_usage_to_rits status=%s", res.status)
    except urllib.error.HTTPError as e:
        log.warning("send_llm_usage_to_rits http_error=%s", e.code)
    except OSError as e:
        log.warning("send_llm_usage_to_rits failed: %s", e)

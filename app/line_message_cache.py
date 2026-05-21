"""LINE チャット内の messageId → 本文キャッシュ（リプライ引用の解決用）。"""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from typing import Any, Literal

_MAX_ENTRIES = 800

Direction = Literal["inbound", "outbound"]


@dataclass(frozen=True)
class CachedLineMessage:
    text: str
    direction: Direction


def _cache_key(chat_key: str, message_id: str) -> str:
    return f"{chat_key}:{message_id}"


class LineMessageCache:
    def __init__(self, max_entries: int = _MAX_ENTRIES) -> None:
        self._max = max_entries
        self._data: OrderedDict[str, CachedLineMessage] = OrderedDict()

    def put(self, chat_key: str, message_id: str, text: str, direction: Direction) -> None:
        if not message_id or not text.strip():
            return
        key = _cache_key(chat_key, message_id)
        self._data[key] = CachedLineMessage(text=text.strip()[:4000], direction=direction)
        self._data.move_to_end(key)
        while len(self._data) > self._max:
            self._data.popitem(last=False)

    def get(self, chat_key: str, message_id: str) -> CachedLineMessage | None:
        return self._data.get(_cache_key(chat_key, message_id))


# プロセス内共有（Render 1 インスタンス想定）
_default_cache = LineMessageCache()


def get_line_message_cache() -> LineMessageCache:
    return _default_cache


def line_chat_key(source: dict[str, Any]) -> str:
    st = source.get("type") or ""
    if st == "group" and source.get("groupId"):
        return f"g:{source['groupId']}"
    if st == "room" and source.get("roomId"):
        return f"r:{source['roomId']}"
    return f"u:{source.get('userId', 'unknown')}"

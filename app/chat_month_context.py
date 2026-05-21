"""LINE チャット単位の直近対象月（「経費は？」などのフォローアップ用）。"""

from __future__ import annotations

from collections import OrderedDict

_MAX_CHATS = 400


class ChatMonthContextStore:
    def __init__(self, max_chats: int = _MAX_CHATS) -> None:
        self._max = max_chats
        self._last_month: OrderedDict[str, str] = OrderedDict()

    def get(self, chat_key: str) -> str | None:
        return self._last_month.get(chat_key)

    def set(self, chat_key: str, month: str) -> None:
        if not chat_key or not month:
            return
        self._last_month[chat_key] = month
        self._last_month.move_to_end(chat_key)
        while len(self._last_month) > self._max:
            self._last_month.popitem(last=False)


_store = ChatMonthContextStore()


def get_last_target_month(chat_key: str | None) -> str | None:
    if not chat_key:
        return None
    return _store.get(chat_key)


def remember_target_month(chat_key: str | None, month: str) -> None:
    if chat_key:
        _store.set(chat_key, month)

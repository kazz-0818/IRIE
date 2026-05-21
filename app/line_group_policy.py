"""LINE グループ／ルームでの応答条件（Veriora エージェント共通方針）。

- 1:1（source.type=user）… 常に応答
- グループ／ルーム … **メンション** または **ボット名呼び** があるときのみ応答
- リプライ（返信）でも同じ。引用だけでは応答しない
"""

from __future__ import annotations

import re
from typing import Any

# デフォルトの名前呼び（LINE_BOT_NAME_ALIASES で上書き可）
_DEFAULT_NAME_ALIASES: tuple[str, ...] = (
    "りら",
    "リラ",
    "LIRA",
    "lira",
)


def parse_name_aliases(raw: str | None) -> tuple[str, ...]:
    if not raw or not raw.strip():
        return _DEFAULT_NAME_ALIASES
    parts = [p.strip() for p in raw.split(",")]
    return tuple(p for p in parts if p) or _DEFAULT_NAME_ALIASES


def strip_line_mentions(text: str, mention: dict[str, Any] | None) -> str:
    """メンション区間を除いた本文（@表示名 プレースホルダを除去）。"""
    if not text or not mention:
        return (text or "").strip()
    mentionees = mention.get("mentionees") or []
    if not mentionees:
        return text.strip()
    chars = list(text)
    for m in sorted(mentionees, key=lambda x: int(x.get("index") or 0), reverse=True):
        i = int(m.get("index") or 0)
        ln = int(m.get("length") or 0)
        if i < 0 or ln <= 0 or i >= len(chars):
            continue
        del chars[i : i + ln]
    return "".join(chars).strip()


def bot_mentioned_in_message(message: dict[str, Any]) -> bool:
    """LINE の mentionees[].isSelf または bot userId 一致でボット宛メンションを判定。"""
    mention = message.get("mention")
    if not mention:
        return False
    for m in mention.get("mentionees") or []:
        if m.get("isSelf") is True:
            return True
    return False


def text_calls_bot_name(text: str, aliases: tuple[str, ...]) -> bool:
    """メンション除去後の本文にボット名が含まれるか。"""
    t = (text or "").strip()
    if not t:
        return False
    lower = t.casefold()
    for alias in aliases:
        a = alias.strip()
        if not a:
            continue
        if a.isascii():
            pat = rf"(?<![A-Za-z0-9]){re.escape(a)}(?![A-Za-z0-9])"
            if re.search(pat, t, flags=re.IGNORECASE):
                return True
        elif a in t or a.casefold() in lower:
            return True
    return False


def normalize_group_question(
    text: str,
    mention: dict[str, Any] | None,
    aliases: tuple[str, ...],
) -> str:
    """グループ用: メンションと名前呼びを除いた質問文。"""
    body = strip_line_mentions(text, mention)
    for alias in aliases:
        a = alias.strip()
        if not a:
            continue
        if a.isascii():
            body = re.sub(
                rf"(?<![A-Za-z0-9]){re.escape(a)}(?![A-Za-z0-9])",
                " ",
                body,
                flags=re.IGNORECASE,
            )
        else:
            body = body.replace(a, " ")
    return " ".join(body.split()).strip()


def should_respond_line_event(
    event: dict[str, Any],
    *,
    aliases: tuple[str, ...],
    bot_user_id: str | None = None,
) -> tuple[bool, str]:
    """
    応答すべきかと理由を返す。
    reason: direct_chat | mention | name_call | group_silent | unsupported_source
    """
    source = event.get("source") or {}
    st = source.get("type")

    if st == "user":
        return True, "direct_chat"

    if st not in ("group", "room"):
        return False, "unsupported_source"

    msg = event.get("message") or {}
    if msg.get("type") != "text":
        return False, "group_silent"

    text = (msg.get("text") or "").strip()
    mention = msg.get("mention")

    if bot_mentioned_in_message(msg):
        return True, "mention"

    if bot_user_id:
        for m in (mention or {}).get("mentionees") or []:
            if m.get("userId") == bot_user_id and m.get("type") == "user":
                return True, "mention"

    body = strip_line_mentions(text, mention)
    if text_calls_bot_name(body, aliases):
        return True, "name_call"

    return False, "group_silent"

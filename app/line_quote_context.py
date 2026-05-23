"""LINE リプライ（引用返信）の文脈を質問文に載せる。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.line_message_cache import CachedLineMessage, LineMessageCache, get_line_message_cache


@dataclass(frozen=True)
class LineQuoteContext:
    quoted_message_id: str | None
    quoted_text: str | None
    quoted_from_bot: bool
    raw_quoted_content: dict[str, Any] | None = None

    def has_quote(self) -> bool:
        return bool(self.quoted_message_id or self.quoted_text or self.raw_quoted_content)


def _text_from_quoted_content(content: dict[str, Any]) -> str | None:
    """Webhook の quotedMessageContent（将来・一部クライアント）。"""
    if not content:
        return None
    t = content.get("type")
    if t == "text":
        s = (content.get("text") or "").strip()
        return s or None
    if t == "flex":
        alt = content.get("altText")
        if alt:
            return str(alt).strip()
    return None


def resolve_line_quote(
    message: dict[str, Any],
    chat_key: str,
    cache: LineMessageCache | None = None,
) -> LineQuoteContext | None:
    msg_id = message.get("quotedMessageId") or message.get("quoted_message_id")
    if not msg_id:
        return None

    cache = cache or get_line_message_cache()
    raw = message.get("quotedMessageContent") or message.get("quoted_message_content")
    if isinstance(raw, dict):
        text = _text_from_quoted_content(raw)
        if text:
            return LineQuoteContext(
                quoted_message_id=str(msg_id),
                quoted_text=text,
                quoted_from_bot=False,
                raw_quoted_content=raw,
            )

    cached: CachedLineMessage | None = cache.get(chat_key, str(msg_id))
    if cached:
        return LineQuoteContext(
            quoted_message_id=str(msg_id),
            quoted_text=cached.text,
            quoted_from_bot=cached.direction == "outbound",
        )

    return LineQuoteContext(
        quoted_message_id=str(msg_id),
        quoted_text=None,
        quoted_from_bot=False,
    )


def enrich_question_with_quote(user_question: str, quote: LineQuoteContext | None) -> str:
    q = (user_question or "").strip()
    if not quote or not quote.has_quote():
        return q

    lines: list[str] = []
    if quote.quoted_text:
        header = "【リプライ先のメッセージ】"
        if quote.quoted_from_bot:
            header = "【リプライ先（IRIE の直前の発言）】"
        lines.append(f"{header}\n{quote.quoted_text}")
    elif quote.quoted_message_id:
        lines.append(
            "【リプライ】ユーザーが過去メッセージに返信していますが、"
            f"引用元本文は取得できませんでした（ID: {quote.quoted_message_id}）。"
            "「これ」「それ」はその直前の会話を指している可能性があります。"
        )

    lines.append(f"【ユーザーの質問】\n{q or '（本文なし）'}")
    hint = (
        "上記のリプライ先を踏まえ、「これ」「それ」「この数字」などは引用先を指すと解釈し、"
        "経理シートのデータと照らして答えてください。"
    )
    lines.append(hint)
    return "\n\n".join(lines)

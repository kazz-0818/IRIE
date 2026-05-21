from __future__ import annotations

from app.line_group_policy import parse_name_aliases, should_respond_line_event
from app.line_message_cache import LineMessageCache
from app.line_quote_context import (
    enrich_question_with_quote,
    resolve_line_quote,
)


def test_enrich_question_with_quote() -> None:
    from app.line_quote_context import LineQuoteContext

    quote = LineQuoteContext(
        quoted_message_id="m1",
        quoted_text="4月売上合計 1013542円",
        quoted_from_bot=True,
    )
    out = enrich_question_with_quote("これの利益は？", quote)
    assert "【リプライ先" in out
    assert "1013542" in out
    assert "これの利益" in out


def test_quote_reply_to_bot_without_name() -> None:
    cache = LineMessageCache()
    cache.put("g:G1", "bot-msg-1", "4月の売上は101万です", "outbound")
    msg = {
        "type": "text",
        "text": "これの利益は？",
        "quotedMessageId": "bot-msg-1",
    }
    quote = resolve_line_quote(msg, "g:G1", cache)
    assert quote is not None
    assert quote.quoted_from_bot is True
    ev = {
        "source": {"type": "group", "groupId": "G1"},
        "message": msg,
    }
    ok, reason = should_respond_line_event(
        ev, aliases=parse_name_aliases(None), quote=quote
    )
    assert ok is True
    assert reason == "quote_reply_to_bot"


def test_embedded_name_rira_kore() -> None:
    ev = {
        "source": {"type": "group", "groupId": "G1"},
        "message": {"type": "text", "text": "りらこれの利益は？"},
    }
    ok, reason = should_respond_line_event(ev, aliases=parse_name_aliases(None))
    assert ok and reason == "name_call"

from __future__ import annotations

from app.line_group_policy import (
    bot_mentioned_in_message,
    normalize_group_question,
    parse_name_aliases,
    should_respond_line_event,
    strip_line_mentions,
    text_calls_bot_name,
)


def test_direct_chat_always_responds() -> None:
    ev = {
        "source": {"type": "user", "userId": "U1"},
        "message": {"type": "text", "text": "こんにちは"},
    }
    ok, reason = should_respond_line_event(ev, aliases=parse_name_aliases(None))
    assert ok is True
    assert reason == "direct_chat"


def test_group_silent_without_mention_or_name() -> None:
    ev = {
        "source": {"type": "group", "groupId": "G1"},
        "message": {"type": "text", "text": "こんにちは"},
    }
    ok, reason = should_respond_line_event(ev, aliases=parse_name_aliases(None))
    assert ok is False
    assert reason == "group_silent"


def test_group_responds_on_name_call() -> None:
    ev = {
        "source": {"type": "group", "groupId": "G1"},
        "message": {"type": "text", "text": "りら 売上をみて"},
    }
    ok, reason = should_respond_line_event(ev, aliases=parse_name_aliases(None))
    assert ok is True
    assert reason == "name_call"
    aliases = parse_name_aliases(None)
    assert normalize_group_question("りら 売上をみて", None, aliases) == "売上をみて"


def test_group_responds_on_bot_mention_is_self() -> None:
    ev = {
        "source": {"type": "group", "groupId": "G1"},
        "message": {
            "type": "text",
            "text": "@LIRA 売上",
            "mention": {
                "mentionees": [
                    {
                        "index": 0,
                        "length": 5,
                        "userId": "B1",
                        "type": "user",
                        "isSelf": True,
                    }
                ]
            },
        },
    }
    ok, reason = should_respond_line_event(ev, aliases=parse_name_aliases(None))
    assert ok is True
    assert reason == "mention"
    assert bot_mentioned_in_message(ev["message"]) is True
    assert strip_line_mentions("@LIRA 売上", ev["message"]["mention"]) == "売上"


def test_group_reply_without_mention_stays_silent() -> None:
    """リプライでもメンション・名前呼びが無ければ無反応。"""
    ev = {
        "source": {"type": "group", "groupId": "G1"},
        "message": {
            "type": "text",
            "text": "了解です",
            "quotedMessageId": "q1234567890",
        },
    }
    ok, reason = should_respond_line_event(ev, aliases=parse_name_aliases(None))
    assert ok is False
    assert reason == "group_silent"


def test_text_calls_bot_ascii_word_boundary() -> None:
    aliases = ("LIRA",)
    assert text_calls_bot_name("LIRA お疲れ", aliases) is True
    assert text_calls_bot_name("こんにちは", aliases) is False

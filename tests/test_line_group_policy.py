from __future__ import annotations

from app.line_group_policy import (
    bot_mentioned_in_message,
    normalize_group_question,
    parse_name_aliases,
    should_respond_line_event,
    strip_line_mentions,
    text_calls_bot_name,
)
from app.line_routes import _question_from_event


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
            "text": "@IRIE 売上",
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
    assert strip_line_mentions("@IRIE 売上", ev["message"]["mention"]) == "売上"


def test_group_reply_without_mention_stays_silent() -> None:
    """他人へのリプライで名前・メンション・LIRA引用が無ければ無反応。"""
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


def test_name_only_becomes_placeholder_question() -> None:
    ev = {
        "source": {"type": "group", "groupId": "G1"},
        "message": {"type": "text", "text": "りら"},
    }
    aliases = parse_name_aliases(None)
    ok, reason = should_respond_line_event(ev, aliases=aliases)
    assert ok and reason == "name_call"
    q = _question_from_event(ev, aliases=aliases, respond_reason=reason)
    assert q == "（名前呼び）"


def test_mention_only_becomes_placeholder_question() -> None:
    ev = {
        "source": {"type": "group", "groupId": "G1"},
        "message": {
            "type": "text",
            "text": "@IRIE",
            "mention": {
                "mentionees": [
                    {"index": 0, "length": 5, "userId": "B1", "type": "user", "isSelf": True},
                ]
            },
        },
    }
    aliases = parse_name_aliases(None)
    ok, reason = should_respond_line_event(ev, aliases=aliases)
    assert ok and reason == "mention"
    q = _question_from_event(ev, aliases=aliases, respond_reason=reason)
    assert q == "（メンション）"

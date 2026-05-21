from __future__ import annotations

from unittest.mock import MagicMock

from app.nl_router import has_accounting_intent, is_casual_chat, route_question


def test_kongetsu_dou_summary_intent() -> None:
    repo = MagicMock()
    repo.load_receivables.return_value = []
    r = route_question("今月どう？", repo)
    assert r["intent"] == "summary"


def test_kyou_nyukin_receivables_intent() -> None:
    repo = MagicMock()
    repo.load_receivables.return_value = []
    r = route_question("今日入金ある？", repo)
    assert r["intent"] == "receivables"


def test_kongetsu_harau_payables_intent() -> None:
    repo = MagicMock()
    repo.load_receivables.return_value = []
    r = route_question("今月払うものある？", repo)
    assert r["intent"] == "payables"


def test_greeting_without_accounting_keywords() -> None:
    repo = MagicMock()
    repo.load_receivables.return_value = []
    r = route_question("こんにちは", repo)
    assert r["intent"] == "greeting"


def test_casual_chat_otsukare() -> None:
    repo = MagicMock()
    repo.load_receivables.return_value = []
    r = route_question("お疲れ様です", repo)
    assert r["intent"] == "casual_chat"


def test_casual_not_when_accounting_hint() -> None:
    assert not is_casual_chat("お疲れ様、今月の売上は？")
    assert has_accounting_intent("今月の売上")

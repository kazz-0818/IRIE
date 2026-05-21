from __future__ import annotations

from unittest.mock import MagicMock

from app.mapping import MonthlySummaryRow
from app.month_resolve import resolve_target_month
from app.nl_router import has_accounting_intent, route_question
from app.text_normalize import normalize_user_question


def test_typo_uriage() -> None:
    assert normalize_user_question("3月の売り上げ") == "3月の売上"
    assert has_accounting_intent("3月の売り上げ") is True


def test_route_suriage_to_summary() -> None:
    repo = MagicMock()
    repo.load_receivables.return_value = []
    r = route_question("3月の売り上げ", repo)
    assert r["intent"] == "summary"


def test_sensatsu_zentai_dashite() -> None:
    repo = MagicMock()
    repo.load_receivables.return_value = []
    r = route_question("りら先月の全体だして", repo)
    assert r["intent"] == "summary"
    assert r.get("focus") == "overview"


def test_sensatsu_suchi_dashite() -> None:
    repo = MagicMock()
    repo.load_receivables.return_value = []
    assert route_question("先月の数値出して", repo)["intent"] == "summary"


def test_conversation_month_for_keihi_followup() -> None:
    repo = MagicMock()
    repo.resolved_sheets = {"summary": "事業実績表"}
    repo.load_summary_rows.return_value = [
        MonthlySummaryRow("2026-03", 100, 50, 50, None),
        MonthlySummaryRow("2026-05", 0, 300000, None, None),
    ]
    repo._fetch_raw.return_value = []
    repo._header_idx.return_value = 0
    repo.warnings = []

    resolve_target_month("3月の売上", repo, chat_key="g:G1")
    res = resolve_target_month("経費は？", repo, chat_key="g:G1")
    assert res.month == "2026-03"
    assert res.source == "conversation_context"

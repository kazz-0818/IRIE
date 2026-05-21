from __future__ import annotations

from datetime import date

from app.parse_util import extract_month_from_question


def test_japanese_month_without_year() -> None:
    ref = date(2026, 5, 21)
    assert extract_month_from_question("4月の売上", ref) == "2026-04"
    assert extract_month_from_question("12月", ref) == "2025-12"


def test_japanese_month_with_year() -> None:
    assert extract_month_from_question("2026年4月の売上") == "2026-04"


def test_relative_month_phrases() -> None:
    ref = date(2026, 5, 21)
    assert extract_month_from_question("先月の売上", ref) == "2026-04"
    assert extract_month_from_question("先月はどうだった？", ref) == "2026-04"
    assert extract_month_from_question("今月の売上", ref) == "2026-05"
    assert extract_month_from_question("来月の見込み", ref) == "2026-06"
    assert extract_month_from_question("先々月", ref) == "2026-03"

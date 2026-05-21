from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.mapping import MonthlySummaryRow
from app.month_resolve import (
    resolve_default_api_month,
    resolve_target_month,
)


def _repo_with_months(rows: list[MonthlySummaryRow]) -> MagicMock:
    repo = MagicMock()
    repo.resolved_sheets = {"summary": "事業実績表"}
    repo.load_summary_rows.return_value = rows
    repo._fetch_raw.return_value = [
        ["項目", "2026/3", "2026/4", "2026/5"],
        ["売上合計", "100", "200", ""],
    ]
    repo._header_idx.return_value = 0
    return repo


def test_no_month_uses_latest_with_data() -> None:
    repo = _repo_with_months(
        [
            MonthlySummaryRow("2026-03", 100, 10, 90, None),
            MonthlySummaryRow("2026-04", 200, 20, 180, None),
            MonthlySummaryRow("2026-05", None, None, None, None),
        ]
    )
    res = resolve_target_month("売上をみて", repo)
    assert res.month == "2026-04"
    assert res.source == "latest_sheet_data"


@patch("app.month_resolve._calendar_month_str", return_value="2026-05")
def test_kongetsu_prefers_calendar_then_fallback(_cal: MagicMock) -> None:
    repo = _repo_with_months(
        [
            MonthlySummaryRow("2026-04", 200, 20, 180, None),
            MonthlySummaryRow("2026-05", None, None, None, None),
        ]
    )
    res = resolve_target_month("今月の売上は？", repo)
    assert res.month == "2026-04"
    assert res.source == "latest_sheet_data_fallback"


def test_explicit_month() -> None:
    repo = _repo_with_months(
        [MonthlySummaryRow("2026-03", 100, 10, 90, None)],
    )
    res = resolve_target_month("2026年3月の売上", repo)
    assert res.month == "2026-03"
    assert res.source == "explicit"


def test_resolve_default_api_month() -> None:
    repo = _repo_with_months(
        [
            MonthlySummaryRow("2026-03", 100, 10, 90, None),
            MonthlySummaryRow("2026-04", 200, 20, 180, None),
        ]
    )
    assert resolve_default_api_month(repo) == "2026-04"

"""質問・API から対象月 (YYYY-MM) を決める（シート実績優先）。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Literal

from app.nl_router import extract_month
from app.parse_util import parse_month_key_from_cell
from app.services import SheetRepository

MonthSource = Literal[
    "explicit",
    "calendar_current",
    "latest_sheet_data",
    "calendar_fallback",
    "latest_sheet_data_fallback",
]


@dataclass(frozen=True)
class TargetMonthResolution:
    month: str
    source: MonthSource
    calendar_month: str
    available_months: tuple[str, ...]
    month_column_label: str | None = None

    def as_context(self) -> dict[str, Any]:
        return {
            "target_month": self.month,
            "target_month_source": self.source,
            "calendar_month": self.calendar_month,
            "available_summary_months": list(self.available_months),
            "month_column_label": self.month_column_label,
            "month_selection_note": _selection_note(self),
        }


def _selection_note(res: TargetMonthResolution) -> str:
    if res.source == "explicit":
        return "質問に含まれる年月を対象月にしました。"
    if res.source == "calendar_current":
        return "「今月」「当月」の指定があるため、カレンダー上の当月を対象にしました。"
    if res.source == "latest_sheet_data":
        return (
            "月の指定がないため、事業実績（サマリー）シートで"
            "数値がある最新の月を対象にしました。"
        )
    if res.source == "latest_sheet_data_fallback":
        return (
            "指定・当月に相当する列に実績が無かったため、"
            "シート上で数値がある最新の月に切り替えました。"
        )
    return "シートから月次を読めなかったため、カレンダー上の当月を対象にしました。"


def _calendar_month_str() -> str:
    today = date.today()
    return f"{today.year:04d}-{today.month:02d}"


def _prefers_calendar_current_month(question: str) -> bool:
    q = question.strip()
    return any(k in q for k in ("今月", "当月", "こんげつ", "こんゲツ"))


def _month_has_data(row: Any) -> bool:
    if row is None:
        return False
    for attr in ("sales", "expenses", "profit"):
        v = getattr(row, attr, None)
        if v is not None and v != 0:
            return True
    return False


def _available_months_from_repo(repo: SheetRepository) -> tuple[str, ...]:
    rows = repo.load_summary_rows()
    months = sorted({r.month for r in rows if r.month})
    return tuple(months)


def _latest_month_with_data(repo: SheetRepository) -> str | None:
    rows = repo.load_summary_rows()
    with_data = [r for r in rows if _month_has_data(r)]
    if not with_data:
        return None
    return max(r.month for r in with_data)


def _month_column_label(repo: SheetRepository, month: str) -> str | None:
    sheet = repo.resolved_sheets.get("summary")
    if not sheet:
        return None
    values = repo._fetch_raw(sheet)
    if not values:
        return None
    header_idx = repo._header_idx(sheet, values)
    if header_idx >= len(values):
        return None
    for cell in values[header_idx]:
        if parse_month_key_from_cell(cell) == month:
            s = str(cell).strip() if cell is not None else ""
            return s or None
    return None


def resolve_target_month(question: str, repo: SheetRepository) -> TargetMonthResolution:
    """
    対象月の決定順:
    1. 質問内の明示 YYYY-MM
    2. 「今月」「当月」→ カレンダー当月（シートに実績が無ければ最新実績月へフォールバック）
    3. 月指定なし → サマリーシートで数値がある最新月
    4. 上記が無い → カレンダー当月
    """
    calendar = _calendar_month_str()
    available = _available_months_from_repo(repo)
    latest = _latest_month_with_data(repo)
    explicit = extract_month(question)

    if explicit:
        month = explicit
        source: MonthSource = "explicit"
    elif _prefers_calendar_current_month(question):
        month = calendar
        source = "calendar_current"
    elif latest:
        month = latest
        source = "latest_sheet_data"
    else:
        month = calendar
        source = "calendar_fallback"

    rows_by_month = {r.month: r for r in repo.load_summary_rows()}
    chosen_row = rows_by_month.get(month)
    if rows_by_month and not _month_has_data(chosen_row) and latest and latest != month:
        month = latest
        source = "latest_sheet_data_fallback"

    label = _month_column_label(repo, month)
    return TargetMonthResolution(
        month=month,
        source=source,
        calendar_month=calendar,
        available_months=available,
        month_column_label=label,
    )


def resolve_target_month_str(question: str, repo: SheetRepository) -> str:
    return resolve_target_month(question, repo).month


def resolve_default_api_month(repo: SheetRepository) -> str:
    """GET /summary など、質問文が無い API 用（最新実績月 → カレンダー当月）。"""
    return _latest_month_with_data(repo) or _calendar_month_str()

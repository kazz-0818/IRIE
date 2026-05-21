"""質問・API から対象月 (YYYY-MM) を決める（シート実績優先）。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Literal

from app.chat_month_context import get_last_target_month, remember_target_month
from app.parse_util import extract_month_from_question, parse_month_key_from_cell
from app.services import SheetRepository
from app.text_normalize import normalize_user_question

MonthSource = Literal[
    "explicit",
    "conversation_context",
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
    user_calendar_month: str | None = None

    def as_context(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "target_month": self.month,
            "target_month_source": self.source,
            "calendar_month": self.calendar_month,
            "available_summary_months": list(self.available_months),
            "month_column_label": self.month_column_label,
            "month_selection_note": _selection_note(self),
        }
        if self.user_calendar_month and self.user_calendar_month != self.month:
            out["user_calendar_month"] = self.user_calendar_month
        return out


def _selection_note(res: TargetMonthResolution) -> str:
    if res.source == "explicit":
        return (
            "質問に含まれる年月（4月・先月・来月 など）を対象月にしました。"
        )
    if res.source == "conversation_context":
        return (
            f"直前の会話で扱った対象月（{res.month}）を引き継ぎました。"
            "（「経費は？」など月が省略された質問）"
        )
    if res.source == "calendar_current":
        return "「今月」「当月」の指定があるため、カレンダー上の当月を対象にしました。"
    if res.source == "latest_sheet_data":
        return (
            "月の指定がないため、事業実績（サマリー）シートで"
            "数値がある最新の月を対象にしました。"
        )
    if res.source == "latest_sheet_data_fallback":
        if res.user_calendar_month:
            return (
                f"「今月」({res.user_calendar_month}) の売上・利益はシート上未確定のため、"
                f"直近の確定実績 {res.month} で回答します。"
            )
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
    with_sales = [r for r in rows if r.sales is not None and r.sales != 0]
    if with_sales:
        return max(r.month for r in with_sales)
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


def _followup_without_month(question: str) -> bool:
    from app.nl_router import has_accounting_intent

    q = normalize_user_question(question)
    if not has_accounting_intent(q):
        return False
    if extract_month_from_question(q):
        return False
    if _prefers_calendar_current_month(q):
        return False
    return True


def resolve_target_month(
    question: str,
    repo: SheetRepository,
    *,
    chat_key: str | None = None,
) -> TargetMonthResolution:
    """
    対象月の決定順:
    1. 質問内の明示 YYYY-MM
    2. 「今月」「当月」→ カレンダー当月（シートに実績が無ければ最新実績月へフォールバック）
    3. 月指定なし → サマリーシートで数値がある最新月
    4. 上記が無い → カレンダー当月
    """
    q = normalize_user_question(question)
    calendar = _calendar_month_str()
    available = _available_months_from_repo(repo)
    latest = _latest_month_with_data(repo)
    explicit = extract_month_from_question(q)
    user_calendar: str | None = None

    if explicit:
        month = explicit
        source: MonthSource = "explicit"
    elif chat_key and _followup_without_month(q):
        last = get_last_target_month(chat_key)
        if last:
            month = last
            source = "conversation_context"
        elif latest:
            month = latest
            source = "latest_sheet_data"
        else:
            month = calendar
            source = "calendar_fallback"
    elif _prefers_calendar_current_month(q):
        month = calendar
        source = "calendar_current"
        user_calendar = calendar
    elif latest:
        month = latest
        source = "latest_sheet_data"
    else:
        month = calendar
        source = "calendar_fallback"

    rows_by_month = {r.month: r for r in repo.load_summary_rows()}
    chosen_row = rows_by_month.get(month)
    chosen_has_sales = chosen_row is not None and chosen_row.sales not in (None, 0)
    if (
        rows_by_month
        and not chosen_has_sales
        and latest
        and latest != month
    ):
        month = latest
        source = "latest_sheet_data_fallback"
        if user_calendar is None and _prefers_calendar_current_month(q):
            user_calendar = calendar

    label = _month_column_label(repo, month)
    if chat_key:
        remember_target_month(chat_key, month)
    return TargetMonthResolution(
        month=month,
        source=source,
        calendar_month=calendar,
        available_months=available,
        month_column_label=label,
        user_calendar_month=user_calendar if user_calendar != month else None,
    )


def resolve_target_month_str(
    question: str,
    repo: SheetRepository,
    *,
    chat_key: str | None = None,
) -> str:
    return resolve_target_month(question, repo, chat_key=chat_key).month


def resolve_default_api_month(repo: SheetRepository) -> str:
    """GET /summary など、質問文が無い API 用（最新実績月 → カレンダー当月）。"""
    return _latest_month_with_data(repo) or _calendar_month_str()

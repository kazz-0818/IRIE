from __future__ import annotations

from dataclasses import asdict
from datetime import date
from typing import Any, Literal

from app.config import Settings, get_settings
from app.header_detect import detect_header_row_index
from app.horizontal_summary import (
    extract_horizontal_month_snapshot,
    extract_horizontal_monthly,
    looks_like_horizontal_month_header,
)
from app.mapping import (
    MonthlySummaryRow,
    PayableRow,
    ReceivableRow,
    row_to_monthly_summary,
    row_to_payable,
    row_to_receivable,
    rows_to_dicts,
)
from app.parse_util import parse_month_key_from_cell
from app.sheet_resolve import SheetResolution, resolve_effective_sheet_names_best_effort
from app.sheets_client import build_sheets_service, fetch_range, list_sheet_titles


def _escape_sheet(name: str) -> str:
    return "'" + name.replace("'", "''") + "'"


def _full_grid_range(sheet: str, last_row: int) -> str:
    # 横持ち月次は列が Z を超えることがある
    return f"{_escape_sheet(sheet)}!A1:ZZ{last_row}"


def _is_blank_row(row: dict[str, Any]) -> bool:
    return not any(str(v).strip() for v in row.values())


class SheetRepository:
    def __init__(
        self,
        settings: Settings | None = None,
        *,
        _service: Any | None = None,
        _titles: list[str] | None = None,
        _resolution: SheetResolution | None = None,
    ):
        self.settings = settings or get_settings()
        self._service = _service or build_sheets_service()
        self._titles = _titles if _titles is not None else list_sheet_titles(
            self._service,
            self.settings.spreadsheet_id,
        )
        self._resolution = _resolution or resolve_effective_sheet_names_best_effort(
            self.settings,
            self._titles,
        )
        rs = self._resolution["resolved_sheets"]
        self.resolved_sheets: dict[str, str | None] = dict(rs)
        self.warnings: list[str] = list(self._resolution["warnings"])
        self._sheet_summary = rs.get("summary")
        self._sheet_receivables = rs.get("receivables")
        self._sheet_payables = rs.get("payables")

    def _fetch_raw(self, sheet: str | None) -> list[list[Any]]:
        if not sheet:
            return []
        s = self.settings
        rng = _full_grid_range(sheet, s.max_data_rows)
        return fetch_range(self._service, s.spreadsheet_id, rng)

    def _header_idx(self, sheet: str, values: list[list[Any]]) -> int:
        fb = self.settings.header_row - 1
        if not self.settings.header_row_auto:
            return max(0, min(fb, max(0, len(values) - 1)))
        idx, _sc = detect_header_row_index(values, max_scan=20, min_score=4, fallback_index=fb)
        return max(0, min(idx, max(0, len(values) - 1)))

    def _read_sheet_with_row_numbers(self, sheet: str | None) -> list[tuple[int, dict[str, Any]]]:
        if not sheet:
            return []
        values = self._fetch_raw(sheet)
        if not values:
            return []
        header_idx = self._header_idx(sheet, values)
        _, dict_rows = rows_to_dicts(values, header_idx)
        pairs: list[tuple[int, dict[str, Any]]] = []
        for i, row in enumerate(dict_rows):
            if _is_blank_row(row):
                continue
            sheet_row = header_idx + 1 + i + 1
            pairs.append((sheet_row, row))
        return pairs

    def _load_summary_rows_horizontal(self, values: list[list[Any]]) -> list[MonthlySummaryRow]:
        out: list[MonthlySummaryRow] = []
        for h in range(min(20, len(values))):
            if not looks_like_horizontal_month_header(values, h):
                continue
            header = values[h]
            months: list[str] = []
            for cell in header:
                mk = parse_month_key_from_cell(cell)
                if mk and mk not in months:
                    months.append(mk)
            for mk in months:
                m = extract_horizontal_monthly(values, h, mk)
                if m:
                    out.append(m)
            if out:
                return out
        return out

    def load_summary_rows(self) -> list[MonthlySummaryRow]:
        if not self._sheet_summary:
            return []
        values = self._fetch_raw(self._sheet_summary)
        if not values:
            return []
        horiz = self._load_summary_rows_horizontal(values)
        if horiz:
            return horiz
        header_idx = self._header_idx(self._sheet_summary, values)
        _, dict_rows = rows_to_dicts(values, header_idx)
        out: list[MonthlySummaryRow] = []
        for row in dict_rows:
            if _is_blank_row(row):
                continue
            m = row_to_monthly_summary(row)
            if m:
                out.append(m)
        return out

    def summary_for_month(self, month: str) -> MonthlySummaryRow | None:
        for m in self.load_summary_rows():
            if m.month == month:
                return m
        return None

    def month_sales_snapshot(self, month: str) -> dict[str, Any] | None:
        """横持ち事業実績表の指定月列（売上行）を構造化。"""
        if not self._sheet_summary:
            return None
        values = self._fetch_raw(self._sheet_summary)
        if not values:
            return None
        for h in range(min(20, len(values))):
            if not looks_like_horizontal_month_header(values, h):
                continue
            snap = extract_horizontal_month_snapshot(values, h, month)
            if snap:
                return snap
        return None

    def load_receivables(self) -> list[ReceivableRow]:
        sheet = self._sheet_receivables
        return [
            row_to_receivable(num, row) for num, row in self._read_sheet_with_row_numbers(sheet)
        ]

    def load_payables(self) -> list[PayableRow]:
        sheet = self._sheet_payables
        return [row_to_payable(num, row) for num, row in self._read_sheet_with_row_numbers(sheet)]


Audience = Literal["internal", "client"]


def _fmt_money(n: int | None) -> str:
    if n is None:
        return "（未設定）"
    return f"¥{n:,}"


def monthly_report_text(
    month: str,
    summary: MonthlySummaryRow | None,
    audience: Audience,
) -> str:
    if summary is None:
        body = f"{month} の月次サマリー行が見つかりませんでした。"
    else:
        rate = summary.margin_rate
        rate_s = f"{rate * 100:.1f}%" if rate is not None else "（算出不可）"
        body = (
            f"対象月: {summary.month}\n"
            f"売上合計: {_fmt_money(summary.sales)}\n"
            f"経費合計: {_fmt_money(summary.expenses)}\n"
            f"利益: {_fmt_money(summary.profit)}\n"
            f"利益率: {rate_s}\n"
        )
    if audience == "internal":
        return (
            f"[LIRA 内部メモ]\n"
            f"{body}\n"
            f"※数値はスプレッドシートの月次・実績系タブの値に基づきます。"
            f"差異があれば原票を確認してください。"
        )
    return (
        f"株式会社BRANDVOX\n"
        f"各位\n\n"
        f"{month} 分の月次概況を共有いたします。\n\n"
        f"{body}\n"
        f"ご不明点がございましたら担当までお問い合わせください。\n"
        f"BRANDVOX 経理チーム（LIRA）"
    )


def payment_received_text(rows: list[ReceivableRow], audience: Audience) -> str:
    lines = []
    for r in rows:
        who = r.client or "（取引先名未設定）"
        tit = f" / {r.title}" if r.title else ""
        lines.append(f"- {who}{tit}: {_fmt_money(r.amount)}（予定日: {r.due_date or '—'}）")
    block = "\n".join(lines) if lines else "（対象行なし）"
    if audience == "internal":
        return (
            "[LIRA 入金確認・内部]\n"
            f"以下について入金を確認しました。\n{block}\n"
            f"入金確認チェックと実入金日の更新をお願いします。"
        )
    return (
        "お世話になっております。BRANDVOXでございます。\n"
        f"下記につきまして、ご入金を確認いたしました。\n\n{block}\n\n"
        f"お忙しいところ恐れ入りますが、ご査収くださいますようお願い申し上げます。"
    )


def overdue_reminder_text(rows: list[ReceivableRow], audience: Audience) -> str:
    lines = []
    today = date.today()
    for r in rows:
        due = r.due_date or date.min
        overdue_days = (today - due).days if r.due_date else None
        od = f"（{overdue_days} 日超過）" if overdue_days is not None and overdue_days > 0 else ""
        who = r.client or "（取引先名未設定）"
        tit = f" / {r.title}" if r.title else ""
        last = f" 最終通知: {r.last_notice}" if r.last_notice else ""
        lines.append(f"- {who}{tit}: {_fmt_money(r.amount)} 予定日 {r.due_date or '—'}{od}{last}")
    block = "\n".join(lines) if lines else "（対象行なし）"
    if audience == "internal":
        return (
            "[LIRA 督促・内部]\n"
            f"未入金候補:\n{block}\n"
            f"送付チャネル・文面トーンの最終確認後、対外送付をお願いします。"
        )
    return (
        "お世話になっております。BRANDVOXでございます。\n"
        f"下記請求につきまして、入金期日を経過しておりますため、お手続き状況のご確認をお願い申し上げます。\n\n"
        f"{block}\n\n"
        f"既にお振込済みの場合は行き違いとなります旨、何卒ご容赦ください。"
    )


def serialize_receivable(r: ReceivableRow) -> dict[str, Any]:
    d = asdict(r)
    d["due_date"] = r.due_date.isoformat() if r.due_date else None
    d["payment_date"] = r.payment_date.isoformat() if r.payment_date else None
    d["last_notice"] = r.last_notice.isoformat() if r.last_notice else None
    d["is_unpaid"] = r.is_unpaid()
    if r.unpaid_flag is not None and not isinstance(r.unpaid_flag, str | int | float | bool):
        d["unpaid_flag"] = str(r.unpaid_flag)
    return d


def serialize_payable(p: PayableRow) -> dict[str, Any]:
    d = asdict(p)
    d["due_date"] = p.due_date.isoformat() if p.due_date else None
    d["is_open"] = p.is_open()
    return d

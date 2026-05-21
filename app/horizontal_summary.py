"""横持ち（月が列方向）の月次サマリー表を読む。"""

from __future__ import annotations

import re
from typing import Any

from app.mapping import MonthlySummaryRow
from app.parse_util import parse_jpy_amount, parse_month_key_from_cell

# 行ラベル（第1列想定）から売上・経費・利益を推定
_SALES_LABELS = re.compile(
    r"(売上|売上合計|売上高|収入|売上実績|売上計)",
)
_EXPENSE_LABELS = re.compile(
    r"(経費|経費合計|支出|費用|原価|広告費|外注費|費用合計|人件費|役員報酬|税理士|弁護士)",
)
_EXPENSE_TOTAL_LABEL = re.compile(r"(経費合計|支出合計|費用合計)")
_PROFIT_LABELS = re.compile(
    r"(利益|営業利益|粗利|純利益|差引|収支)",
)
_SALES_TOTAL_LABEL = re.compile(r"(売上合計|売上計|合計売上|売上高合計)")


def looks_like_horizontal_month_header(values: list[list[Any]], header_row_index: int) -> bool:
    """見出し行に複数の「月」列が並んでいれば横持ち月次とみなす。"""
    if header_row_index >= len(values):
        return False
    row = values[header_row_index]
    months: list[str] = []
    for cell in row[1:]:  # 左端は「項目」列のことが多い
        mk = parse_month_key_from_cell(cell)
        if mk and mk not in months:
            months.append(mk)
    return len(months) >= 2


def _row_label(values: list[list[Any]], r: int) -> str:
    if r >= len(values) or not values[r]:
        return ""
    row = values[r]
    for c in range(min(3, len(row))):
        t = str(row[c]).strip() if row[c] is not None else ""
        if t:
            return t
    return ""


def extract_horizontal_monthly(
    values: list[list[Any]],
    header_row_index: int,
    month: str,
) -> MonthlySummaryRow | None:
    """
    形式B: 1行目が月列、左列が項目名の表から指定月の MonthlySummaryRow を構築。
    """
    if header_row_index >= len(values):
        return None
    header = values[header_row_index]
    col_idx: int | None = None
    for j, cell in enumerate(header):
        mk = parse_month_key_from_cell(cell)
        if mk == month:
            col_idx = j
            break
    if col_idx is None:
        return None

    sales = expenses = profit = None
    for r in range(header_row_index + 1, len(values)):
        label = _row_label(values, r)
        if not label:
            continue
        row = values[r]
        raw = row[col_idx] if col_idx < len(row) else None
        val = parse_jpy_amount(raw)
        if val is None:
            continue
        if _SALES_LABELS.search(label):
            sales = val
        elif _EXPENSE_LABELS.search(label):
            expenses = val
        elif _PROFIT_LABELS.search(label):
            profit = val

    if sales is None and expenses is None and profit is None:
        return None

    if profit is None and sales is not None and expenses is not None:
        profit = sales - expenses

    margin_rate = None
    if profit is not None and sales not in (None, 0):
        margin_rate = profit / sales if sales else None

    return MonthlySummaryRow(
        month=month,
        sales=sales,
        expenses=expenses,
        profit=profit,
        margin_rate=margin_rate,
    )


def _find_month_column(
    values: list[list[Any]],
    header_row_index: int,
    month: str,
) -> tuple[int | None, str | None]:
    if header_row_index >= len(values):
        return None, None
    header = values[header_row_index]
    for j, cell in enumerate(header):
        mk = parse_month_key_from_cell(cell)
        if mk == month:
            label = str(cell).strip() if cell is not None else None
            return j, label or None
    return None, None


def extract_horizontal_month_breakdown(
    values: list[list[Any]],
    header_row_index: int,
    month: str,
    *,
    max_items_per_kind: int = 30,
) -> dict[str, Any] | None:
    """横持ち事業実績表: 指定月列の売上・経費・利益を分類して返す。"""
    col_idx, column_label = _find_month_column(values, header_row_index, month)
    if col_idx is None:
        return None

    sales_lines: list[dict[str, Any]] = []
    expense_lines: list[dict[str, Any]] = []
    sales_total: int | None = None
    expenses_total: int | None = None
    profit: int | None = None

    for r in range(header_row_index + 1, len(values)):
        label = _row_label(values, r)
        if not label:
            continue
        row = values[r]
        raw = row[col_idx] if col_idx < len(row) else None
        val = parse_jpy_amount(raw)
        if val is None:
            continue

        if _SALES_TOTAL_LABEL.search(label):
            sales_total = val
            continue
        if _EXPENSE_TOTAL_LABEL.search(label):
            expenses_total = val
            continue
        if _PROFIT_LABELS.search(label):
            profit = val
            continue
        if _EXPENSE_LABELS.search(label):
            expense_lines.append({"label": label, "amount_jpy": val})
            continue
        if _SALES_LABELS.search(label):
            sales_lines.append({"label": label, "amount_jpy": val})
            continue
        # 販売・契約金など売上内訳行（ラベルに売上語が無い行）
        if not _EXPENSE_LABELS.search(label):
            sales_lines.append({"label": label, "amount_jpy": val})

    if not any([sales_total, expenses_total, profit, sales_lines, expense_lines]):
        return None

    return {
        "month": month,
        "column_label": column_label,
        "sales_total_jpy": sales_total,
        "sales_line_items": sales_lines[:max_items_per_kind],
        "expenses_total_jpy": expenses_total,
        "expense_line_items": expense_lines[:max_items_per_kind],
        "profit_jpy": profit,
    }


def extract_horizontal_month_snapshot(
    values: list[list[Any]],
    header_row_index: int,
    month: str,
    *,
    max_line_items: int = 35,
) -> dict[str, Any] | None:
    """後方互換: 売上側スナップショット。"""
    full = extract_horizontal_month_breakdown(
        values, header_row_index, month, max_items_per_kind=max_line_items
    )
    if not full:
        return None
    return {
        "month": full["month"],
        "column_label": full.get("column_label"),
        "sales_total_jpy": full.get("sales_total_jpy"),
        "line_items": full.get("sales_line_items") or [],
    }

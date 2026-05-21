from __future__ import annotations

from datetime import date
from typing import Any

from app.services import SheetRepository, serialize_payable, serialize_receivable
from app.sheet_preview import build_raw_previews_for_llm, structured_data_is_sparse


def build_accounting_context(repo: SheetRepository, month: str) -> dict[str, Any]:
    """OpenAI 用 JSON: ルール抽出 + 各タブの生グリッド（BRANDVOX 実シート向け）。"""
    today = date.today()
    summary = None
    if repo.resolved_sheets.get("summary"):
        summary = repo.summary_for_month(month)
    summ_dict: dict[str, Any] | None = None
    if summary:
        summ_dict = {
            "month": summary.month,
            "sales_jpy": summary.sales,
            "expenses_jpy": summary.expenses,
            "profit_jpy": summary.profit,
            "margin_rate": summary.margin_rate,
        }

    rec_all = repo.load_receivables() if repo.resolved_sheets.get("receivables") else []
    unpaid = [serialize_receivable(r) for r in rec_all if r.is_unpaid()][:40]
    due_today = [serialize_receivable(r) for r in rec_all if r.due_date == today][:25]
    overdue = [
        serialize_receivable(r)
        for r in rec_all
        if r.is_unpaid() and r.due_date is not None and r.due_date < today
    ][:25]

    pay_all = repo.load_payables() if repo.resolved_sheets.get("payables") else []
    pay_open = [serialize_payable(p) for p in pay_all if p.is_open()][:40]
    pay_due_today = [serialize_payable(p) for p in pay_all if p.is_open() and p.due_date == today][
        :25
    ]

    rules_block: dict[str, Any] = {
        "monthly_summary_row": summ_dict,
        "unpaid_receivables": unpaid,
        "receivables_due_today": due_today,
        "overdue_unpaid_receivables": overdue,
        "open_payables": pay_open,
        "payables_due_today": pay_due_today,
    }
    raw_previews = build_raw_previews_for_llm(repo)
    sparse = structured_data_is_sparse(rules_block)

    return {
        "as_of": today.isoformat(),
        "target_month": month,
        "resolved_sheets": dict(repo.resolved_sheets),
        "sheet_warnings": list(repo.warnings),
        "interpretation_hint": (
            "BRANDVOX 経理ファイルは LIRA 専用列名と一致しないことがあります。"
            "rules_extracted が空でも raw_sheet_previews の grid から"
            "数値・日付を読んで回答してください。"
            if sparse
            else (
                "rules_extracted は列名マッチ時の構造化データです。"
                "不足があれば raw_sheet_previews を参照してください。"
            )
        ),
        "rules_extracted": rules_block,
        "raw_sheet_previews": raw_previews,
        # 後方互換: トップレベルにも同じキーを残す
        **rules_block,
    }

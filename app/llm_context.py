from __future__ import annotations

from datetime import date
from typing import Any

from app.month_resolve import resolve_target_month
from app.services import SheetRepository, serialize_payable, serialize_receivable
from app.sheet_preview import build_raw_previews_for_llm, structured_data_is_sparse

_CONVERSATION_CAPABILITIES: tuple[str, ...] = (
    "今月の売上・経費・利益（「今月どう？」「売上は？」）",
    "入金予定・未入金（「入金予定」「未入金ある？」）",
    "支払・経費（「支払い予定」「経費いくら？」）",
    "月次のざっくり相談（「まとめて」「今月の状況」）",
)


def build_conversation_context(
    repo: SheetRepository,
    question: str,
    intent: str,
) -> dict[str, Any]:
    """挨拶・雑談・曖昧な質問向け（生グリッドは送らずトークン節約）。"""
    month_res = resolve_target_month(question, repo)
    month = month_res.month
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
        }

    ctx: dict[str, Any] = {
        "response_mode": "conversation",
        "intent": intent,
        "as_of": today.isoformat(),
        "target_month": month,
        "resolved_sheets": dict(repo.resolved_sheets),
        "sheet_warnings": list(repo.warnings)[:4],
        "monthly_summary_teaser": summ_dict,
        "lira_capabilities": list(_CONVERSATION_CAPABILITIES),
        "persona_note": (
            "株式会社BRANDVOXの経理担当AI「LIRA」。"
            "丁寧だが堅苦しくなりすぎない口調で、短い雑談にも自然に返答する。"
            "経理の質問には喜んで答える。"
        ),
    }
    ctx.update(month_res.as_context())
    return ctx


def build_accounting_context(repo: SheetRepository, question: str) -> dict[str, Any]:
    """OpenAI 用 JSON: ルール抽出 + 各タブの生グリッド（BRANDVOX 実シート向け）。"""
    month_res = resolve_target_month(question, repo)
    month = month_res.month
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

    month_hint = (
        "回答の対象月は target_month の列のみ使用すること。"
        "month_column_label があればその列見出しと数値を対応づけること。"
        "target_month と列見出しが食い違う場合は数値の列を優先し、"
        "対象月を正直に述べること（例: 5月列が空で4月列を読んだ場合は4月の実績と明記）。"
    )
    ctx: dict[str, Any] = {
        "response_mode": "accounting",
        "as_of": today.isoformat(),
        "target_month": month,
        "resolved_sheets": dict(repo.resolved_sheets),
        "sheet_warnings": list(repo.warnings),
        "interpretation_hint": (
            "BRANDVOX 経理ファイルは LIRA 専用列名と一致しないことがあります。"
            "rules_extracted が空でも raw_sheet_previews の grid から"
            "数値・日付を読んで回答してください。"
            f" {month_hint}"
            if sparse
            else (
                "rules_extracted は列名マッチ時の構造化データです。"
                "不足があれば raw_sheet_previews を参照してください。"
                f" {month_hint}"
            )
        ),
        "rules_extracted": rules_block,
        "raw_sheet_previews": raw_previews,
        # 後方互換: トップレベルにも同じキーを残す
        **rules_block,
    }
    ctx.update(month_res.as_context())
    return ctx

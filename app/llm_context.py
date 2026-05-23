from __future__ import annotations

from datetime import date
from typing import Any

from app.month_resolve import resolve_target_month
from app.nl_router import detect_accounting_focus
from app.services import SheetRepository, serialize_payable, serialize_receivable
from app.sheet_preview import build_raw_previews_for_llm, structured_data_is_sparse
from app.text_normalize import normalize_user_question

_CONVERSATION_CAPABILITIES: tuple[str, ...] = (
    "今月の売上・経費・利益の説明（例: 今月どう？）",
    "入金予定・未入金の確認",
    "支払い・経費の金額や一覧",
    "経理用の表の数字を読んで答える",
    "雑談や軽い相談",
)


def build_conversation_context(
    repo: SheetRepository,
    question: str,
    intent: str,
) -> dict[str, Any]:
    """挨拶・雑談・曖昧な質問向け（生グリッドは送らずトークン節約）。"""
    q = normalize_user_question(question)
    month_res = resolve_target_month(q, repo)
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
        "irie_capabilities": list(_CONVERSATION_CAPABILITIES),
        "persona_note": (
            "株式会社BRANDVOXの経理担当AI「IRIE」。"
            "丁寧だが堅苦しくなりすぎない口調で、短い雑談にも自然に返答する。"
            "経理の質問には喜んで答える。"
        ),
    }
    ctx.update(month_res.as_context())
    return ctx


def build_accounting_context(
    repo: SheetRepository,
    question: str,
    *,
    chat_key: str | None = None,
) -> dict[str, Any]:
    """OpenAI 用 JSON: ルール抽出 + 各タブの生グリッド（BRANDVOX 実シート向け）。"""
    q = normalize_user_question(question)
    month_res = resolve_target_month(q, repo, chat_key=chat_key)
    month = month_res.month
    focus = detect_accounting_focus(q)
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

    breakdown = (
        repo.month_breakdown_snapshot(month) if repo.resolved_sheets.get("summary") else None
    )

    rules_block: dict[str, Any] = {
        "monthly_summary_row": summ_dict,
        "authoritative_month_breakdown": breakdown,
        "authoritative_month_sales": breakdown,
        "unpaid_receivables": unpaid,
        "receivables_due_today": due_today,
        "overdue_unpaid_receivables": overdue,
        "open_payables": pay_open,
        "payables_due_today": pay_due_today,
    }
    raw_previews = build_raw_previews_for_llm(repo)
    sparse = structured_data_is_sparse(rules_block)

    month_hint = (
        "authoritative_month_breakdown がある場合は raw グリッドより最優先。"
        "数値がある項目は「シート上では確認できません」と言わない。"
        "回答の対象月は必ず target_month（例: 2026-04 → 2026年4月）。"
        "month_selection_note を冒頭1文で反映。"
        "accounting_focus=overview なら売上合計・経費合計・利益と主要内訳を簡潔に。"
        "expenses なら経費、sales なら売上を中心に。"
    )
    ctx: dict[str, Any] = {
        "response_mode": "accounting",
        "as_of": today.isoformat(),
        "target_month": month,
        "accounting_focus": focus,
        "resolved_sheets": dict(repo.resolved_sheets),
        "sheet_warnings": list(repo.warnings),
        "interpretation_hint": (
            "BRANDVOX 経理ファイルは IRIE 専用列名と一致しないことがあります。"
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

from __future__ import annotations

from datetime import date
from typing import Any

from app.month_resolve import resolve_target_month_str
from app.nl_router import route_question
from app.services import SheetRepository, serialize_payable, serialize_receivable


def month_from_question(question: str, repo: SheetRepository | None = None) -> str:
    """後方互換。repo があればシート実績を考慮した対象月。"""
    if repo is not None:
        return resolve_target_month_str(question, repo)
    today = date.today()
    return f"{today.year:04d}-{today.month:02d}"


def _sheet_meta(repo: SheetRepository) -> dict[str, Any]:
    return {
        "resolved_sheets": dict(repo.resolved_sheets),
        "warnings": list(repo.warnings),
    }


def run_rules_ask(question: str, repo: SheetRepository, month: str) -> dict[str, Any]:
    """キーワードルーティング + スプレッドシート由来の構造化データ（従来の /ask 相当）。"""
    meta = _sheet_meta(repo)
    route = route_question(question, repo)
    intent = route["intent"]

    if intent in ("greeting", "casual_chat"):
        return {"intent": intent, **meta}

    if intent == "summary":
        s = repo.summary_for_month(month) if repo.resolved_sheets.get("summary") else None
        return {
            "intent": intent,
            "month": month,
            "data": {
                "found": s is not None,
                "sales_jpy": s.sales if s else None,
                "expenses_jpy": s.expenses if s else None,
                "profit_jpy": s.profit if s else None,
            },
            **meta,
        }
    if intent == "receivables":
        rows = repo.load_receivables() if repo.resolved_sheets.get("receivables") else []
        sample = [serialize_receivable(r) for r in rows[:5]]
        return {"intent": intent, "count": len(rows), "sample": sample, **meta}
    if intent == "payables":
        rows = repo.load_payables() if repo.resolved_sheets.get("payables") else []
        sample = [serialize_payable(p) for p in rows[:5]]
        return {"intent": intent, "count": len(rows), "sample": sample, **meta}
    if intent == "unpaid":
        rows = (
            [r for r in repo.load_receivables() if r.is_unpaid()]
            if repo.resolved_sheets.get("receivables")
            else []
        )
        sample = [serialize_receivable(r) for r in rows[:5]]
        return {"intent": intent, "count": len(rows), "sample": sample, **meta}
    if intent == "payment_received":
        rows = (
            [r for r in repo.load_receivables() if r.payment_date]
            if repo.resolved_sheets.get("receivables")
            else []
        )
        return {"intent": intent, "count": len(rows), **meta}
    if intent == "overdue_reminder":
        rows = (
            [r for r in repo.load_receivables() if r.is_unpaid()]
            if repo.resolved_sheets.get("receivables")
            else []
        )
        return {"intent": intent, "count": len(rows), **meta}

    return {"intent": "unknown", "route": route, **meta}

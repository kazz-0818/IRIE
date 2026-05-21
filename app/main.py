from __future__ import annotations

import logging
from datetime import date
from typing import Annotated, Any, Literal

from fastapi import Depends, FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from app.ask_service import run_rules_ask
from app.audit_supabase import log_audit
from app.config import get_settings
from app.deployment_info import deployment_revision
from app.line_routes import handle_line_webhook
from app.line_routes import router as line_router
from app.llm_ask import answer_with_openai
from app.llm_context import build_accounting_context, build_conversation_context
from app.month_resolve import resolve_default_api_month, resolve_target_month
from app.parse_util import is_paid_status
from app.services import (
    SheetRepository,
    monthly_report_text,
    overdue_reminder_text,
    payment_received_text,
    serialize_payable,
    serialize_receivable,
)
from app.sheet_debug import build_sheets_debug
from app.sheet_resolve import resolve_effective_sheet_names_best_effort
from app.sheets_client import build_sheets_service, list_sheet_titles
from app.sheets_errors import format_sheets_user_message

Audience = Literal["internal", "client"]
_CONVERSATION_INTENTS = frozenset({"greeting", "casual_chat", "unknown"})


def get_repo() -> SheetRepository:
    return SheetRepository()


RepoDep = Annotated[SheetRepository, Depends(get_repo)]


def _reading_scope_notice(repo: SheetRepository) -> str:
    if not repo.warnings:
        return ""
    lines = "\n".join(f"・{w}" for w in repo.warnings[:6])
    return f"読める範囲で回答します。\n{lines}\n\n"


def _fastapi_kwargs() -> dict:
    s = get_settings()
    kwargs: dict = {
        "title": "LIRA",
        "version": "0.1.0",
        "description": "BRANDVOX 経理 AI MVP（Sheets バックエンド）",
    }
    if s.public_app_url:
        kwargs["servers"] = [{"url": s.public_app_url.rstrip("/")}]
    return kwargs


app = FastAPI(**_fastapi_kwargs())
app.include_router(line_router)
# LINE Webhook よくあるパス揺れ（404 防止）
app.add_api_route("/webhook", handle_line_webhook, methods=["POST"], tags=["line"])
app.add_api_route("/webhook/line", handle_line_webhook, methods=["POST"], tags=["line"])

log = logging.getLogger(__name__)


@app.get("/health")
def health() -> dict[str, Any]:
    """Render 上で Sheets 接続・タブ解決まで含めた状態を返す。"""
    s = get_settings()
    out: dict[str, Any] = {
        "status": "ok",
        "service": "lira",
        "google_credentials_configured": bool((s.google_service_account_json or "").strip())
        or bool((s.google_application_credentials or "").strip()),
        "spreadsheet_id_configured": bool((s.spreadsheet_id or "").strip()),
        "spreadsheet_access_ok": False,
        "sheet_titles": [],
        "resolved_sheets": {},
        "sheet_resolution_warnings": [],
        "openai_configured": bool(s.openai_api_key),
        "supabase_configured": bool(
            s.supabase_url and s.supabase_service_role_key,
        ),
        "line_configured": bool(s.line_channel_secret and s.line_channel_access_token),
    }
    out.update(deployment_revision())
    try:
        svc = build_sheets_service()
        titles = list_sheet_titles(svc, s.spreadsheet_id)
        out["spreadsheet_access_ok"] = True
        out["sheet_titles"] = titles
        res = resolve_effective_sheet_names_best_effort(s, titles)
        out["resolved_sheets"] = res["resolved_sheets"]
        out["sheet_resolution_warnings"] = res["warnings"]
    except Exception as e:
        out["spreadsheet_access_error"] = f"{type(e).__name__}: {e!s}"[:500]
    return out


@app.get("/debug/sheets")
def debug_sheets(debug: bool = Query(False, description="true で spreadsheet_id をマスクせず返す")):
    """タブ一覧・先頭行プレビュー・ヘッダー候補・ロールスコア・解決結果の診断。"""
    s = get_settings()
    try:
        svc = build_sheets_service()
        titles = list_sheet_titles(svc, s.spreadsheet_id)
        return build_sheets_debug(s, titles, svc, s.spreadsheet_id, debug=debug)
    except Exception as e:
        return {
            "error": format_sheets_user_message(e),
            "spreadsheet_id": s.spreadsheet_id if debug else "***",
        }


def _month_or_default(month: str | None, repo: SheetRepository) -> str:
    if month:
        return month
    return resolve_default_api_month(repo)


def _parse_iso(d: str | None) -> date | None:
    if not d:
        return None
    try:
        y, m, day = d.split("-")
        return date(int(y), int(m), int(day))
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail="日付は YYYY-MM-DD 形式で指定してください。",
        ) from e


@app.get("/summary")
def get_summary(
    repo: RepoDep,
    month: str | None = Query(None, description="YYYY-MM（省略時は最新実績月）"),
):
    m = _month_or_default(month, repo)
    s = repo.summary_for_month(m)
    if not s:
        return {
            "month": m,
            "found": False,
            "sales": None,
            "expenses": None,
            "profit": None,
            "margin_rate": None,
        }
    rate = s.margin_rate
    return {
        "month": m,
        "found": True,
        "sales_jpy": s.sales,
        "expenses_jpy": s.expenses,
        "profit_jpy": s.profit,
        "margin_rate": rate,
        "margin_percent": round(rate * 100, 2) if rate is not None else None,
    }


@app.get("/receivables")
def get_receivables(
    repo: RepoDep,
    month: str | None = Query(None, description="入金予定日がこの月に含まれる行に絞る YYYY-MM"),
    due_from: str | None = Query(None),
    due_to: str | None = Query(None),
):
    df = _parse_iso(due_from)
    dt = _parse_iso(due_to)
    rows = repo.load_receivables()
    out = []
    for r in rows:
        if month and r.due_date:
            key = f"{r.due_date.year:04d}-{r.due_date.month:02d}"
            if key != month:
                continue
        elif month and not r.due_date:
            continue
        if df and r.due_date and r.due_date < df:
            continue
        if dt and r.due_date and r.due_date > dt:
            continue
        out.append(serialize_receivable(r))
    return {"items": out, "count": len(out)}


@app.get("/payables")
def get_payables(
    repo: RepoDep,
    month: str | None = Query(None),
    due_from: str | None = Query(None),
    due_to: str | None = Query(None),
    open_only: bool = Query(True, description="未払いのみ"),
):
    df = _parse_iso(due_from)
    dt = _parse_iso(due_to)
    rows = repo.load_payables()
    out = []
    for p in rows:
        if open_only and not p.is_open():
            continue
        if month and p.due_date:
            key = f"{p.due_date.year:04d}-{p.due_date.month:02d}"
            if key != month:
                continue
        elif month and not p.due_date:
            continue
        if df and p.due_date and p.due_date < df:
            continue
        if dt and p.due_date and p.due_date > dt:
            continue
        out.append(serialize_payable(p))
    return {"items": out, "count": len(out)}


@app.get("/unpaid")
def get_unpaid(repo: RepoDep):
    rows = [r for r in repo.load_receivables() if r.is_unpaid()]
    return {"items": [serialize_receivable(r) for r in rows], "count": len(rows)}


@app.get("/integrations/status")
def integrations_status() -> dict[str, bool | str]:
    s = get_settings()
    google = bool((s.google_service_account_json or "").strip()) or bool(
        (s.google_application_credentials or "").strip()
    )
    out: dict[str, bool | str] = {
        "openai_configured": bool(s.openai_api_key),
        "supabase_configured": bool(
            s.supabase_url and s.supabase_service_role_key
        ),
        "line_webhook_configured": bool(s.line_channel_secret and s.line_channel_access_token),
        "public_app_url_configured": bool(s.public_app_url),
        "google_credentials_configured": google,
    }
    out.update(deployment_revision())
    return out


class MonthlyReportBody(BaseModel):
    month: str | None = Field(None, description="YYYY-MM（省略時は最新実績月）")
    audience: Audience = "internal"


@app.post("/reports/monthly")
def post_monthly_report(body: MonthlyReportBody, repo: RepoDep):
    m = _month_or_default(body.month, repo)
    summary = repo.summary_for_month(m)
    text = monthly_report_text(m, summary, body.audience)
    return {"month": m, "audience": body.audience, "text": text}


class RowSelection(BaseModel):
    sheet_row_indices: list[int] = Field(default_factory=list)
    audience: Audience = "internal"


@app.post("/messages/payment-received")
def post_payment_received(body: RowSelection, repo: RepoDep):
    all_rows = repo.load_receivables()
    if body.sheet_row_indices:
        idx = set(body.sheet_row_indices)
        chosen = [r for r in all_rows if r.sheet_row_index in idx]
        if not chosen:
            raise HTTPException(404, "指定した行番号に一致する入金予定がありません。")
    else:
        chosen = [r for r in all_rows if r.payment_date and is_paid_status(r.status)]
        if not chosen:
            chosen = [r for r in all_rows if r.payment_date]
    text = payment_received_text(chosen, body.audience)
    return {"audience": body.audience, "row_count": len(chosen), "text": text}


@app.post("/messages/overdue-reminder")
def post_overdue_reminder(body: RowSelection, repo: RepoDep):
    all_rows = repo.load_receivables()
    today = date.today()
    if body.sheet_row_indices:
        idx = set(body.sheet_row_indices)
        chosen = [r for r in all_rows if r.sheet_row_index in idx]
        if not chosen:
            raise HTTPException(404, "指定した行番号に一致する入金予定がありません。")
    else:
        chosen = [
            r for r in all_rows if r.is_unpaid() and r.due_date is not None and r.due_date < today
        ]
        if not chosen:
            chosen = [r for r in all_rows if r.is_unpaid()]
    text = overdue_reminder_text(chosen, body.audience)
    return {"audience": body.audience, "row_count": len(chosen), "text": text}


class AskBody(BaseModel):
    question: str = Field(..., min_length=1)


@app.post("/ask")
def post_ask(body: AskBody, repo: RepoDep):
    month_res = resolve_target_month(body.question, repo, chat_key=None)
    month = month_res.month
    try:
        structured = run_rules_ask(body.question, repo, month)
    except Exception as e:
        log.exception("POST /ask: Sheets 読み取り失敗")
        return {"mode": "error", "message": format_sheets_user_message(e)}
    log_audit(
        "ask",
        {
            "intent": structured.get("intent"),
            "month": month,
            "target_month_source": month_res.source,
        },
    )
    intent = structured.get("intent", "unknown")
    s = get_settings()
    if s.openai_api_key:
        try:
            if intent in _CONVERSATION_INTENTS:
                ctx = build_conversation_context(repo, body.question, intent)
                answer = answer_with_openai(
                    body.question, ctx, mode="conversation"
                )
            else:
                ctx = build_accounting_context(repo, body.question, chat_key=None)
                answer = answer_with_openai(
                    body.question, ctx, mode="accounting"
                )
            return {
                "mode": "openai",
                "response_kind": (
                    "conversation" if intent in _CONVERSATION_INTENTS else "accounting"
                ),
                "target_month": month,
                "target_month_source": month_res.source,
                "answer": _reading_scope_notice(repo) + answer,
                "structured": structured,
            }
        except Exception:
            log.exception("OpenAI /ask が失敗したためルール結果を返します")
    notice = _reading_scope_notice(repo)
    out: dict[str, Any] = {"mode": "rules", **structured}
    if notice.strip():
        out["reading_scope_notice"] = notice.strip()
    return out


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)

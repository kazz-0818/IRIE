from __future__ import annotations

import logging

from app.ask_service import run_rules_ask
from app.config import get_settings
from app.llm_ask import answer_with_openai
from app.llm_context import build_accounting_context, build_conversation_context
from app.month_resolve import resolve_target_month_str
from app.services import SheetRepository
from app.sheets_errors import format_sheets_user_message_with_retry_hint
from app.capabilities_help import format_irie_capabilities_reply, is_capabilities_help_question
from app.text_normalize import normalize_user_question

log = logging.getLogger(__name__)

_CONVERSATION_INTENTS = frozenset({"greeting", "casual_chat", "unknown"})


def _partial_notice(repo: SheetRepository) -> str:
    if not repo.warnings:
        return ""
    lines = "\n".join(f"・{w}" for w in repo.warnings[:6])
    return f"読める範囲で回答します。\n{lines}\n\n"


def _fallback_text(structured: dict) -> str:
    intent = structured.get("intent", "unknown")
    if intent == "greeting":
        return (
            "IRIE 経理部です。こんにちは。\n"
            "「今月の売上」「入金予定」「未入金」「支払い予定」など、気軽に聞いてください。"
        )
    if intent == "casual_chat":
        return (
            "IRIE です。お気軽にどうぞ。\n"
            "雑談も大丈夫です。経理の数字が知りたくなったら、"
            "「今月どう？」「入金予定」などと送ってください。"
        )
    if intent == "summary":
        d = structured.get("data") or {}
        if not d.get("found"):
            rs = structured.get("resolved_sheets") or {}
            tab_hint = (
                f"\n割当タブ: summary={rs.get('summary')!s}, "
                f"receivables={rs.get('receivables')!s}, payables={rs.get('payables')!s}"
            )
            return (
                "今月の売上・経費・利益を、シート上の縦持ち行または横持ち月次列からはまだ読み取れませんでした。"
                "事業実績表のレイアウト確認、または GET /debug/sheets を参照してください。"
                f"{tab_hint}"
            )
        return (
            f"（ルール応答）売上: {d.get('sales_jpy')} 円、経費: {d.get('expenses_jpy')} 円、"
            f"利益: {d.get('profit_jpy')} 円です。"
        )
    if intent == "receivables":
        rs = structured.get("resolved_sheets") or {}
        if not rs.get("receivables"):
            return (
                "入金・売掛用のタブを特定できないか、列構造が合わず一覧を読めませんでした。"
                "GET /debug/sheets で確認するか、SHEET_RECEIVABLES を指定してください。"
            )
        return f"（ルール応答）入金予定は {structured.get('count', 0)} 件です。"
    if intent == "payables":
        rs = structured.get("resolved_sheets") or {}
        if not rs.get("payables"):
            return (
                "支払・経費用のタブを特定できないか、列構造が合わず一覧を読めませんでした。"
                "GET /debug/sheets で確認するか、SHEET_PAYABLES を指定してください。"
            )
        return f"（ルール応答）支払予定は {structured.get('count', 0)} 件です。"
    if intent == "unpaid":
        rs = structured.get("resolved_sheets") or {}
        if not rs.get("receivables"):
            return (
                "未入金一覧を読むには入金・売掛用タブが必要です。"
                "GET /debug/sheets を確認するか、SHEET_RECEIVABLES を指定してください。"
            )
        return f"（ルール応答）未入金候補は {structured.get('count', 0)} 件です。"
    if intent in ("payment_received", "overdue_reminder"):
        n = structured.get("count", 0)
        return (
            f"（ルール応答）{intent} 関連データ {n} 件です。\n"
            "詳細は /docs の API を参照ください。"
        )
    return "（ルール応答）売上・入金・支払・未入金・月次 などのキーワードで質問してください。"


def answer_for_user(
    question: str,
    repo: SheetRepository | None = None,
    *,
    chat_key: str | None = None,
) -> str:
    """人が読む自然文。OpenAI が使えなければルールベースの短文。"""
    if is_capabilities_help_question(question):
        return format_irie_capabilities_reply()
    try:
        if repo is None:
            repo = SheetRepository()
        q = normalize_user_question(question)
        month = resolve_target_month_str(q, repo, chat_key=chat_key)
        structured = run_rules_ask(q, repo, month)
        intent = structured.get("intent", "unknown")
        s = get_settings()
        if not s.openai_api_key:
            return (
                _partial_notice(repo)
                + "（ルールのみ）経理シートの列レイアウトが IRIE 既定と異なるため、"
                "数値の自動読み取りができていません。\n"
                "Render の Environment に OPENAI_API_KEY を設定すると、"
                "スプレッドシートの生データを LLM が読んで回答します。\n\n"
                + _fallback_text(structured)
            )
        try:
            if intent in _CONVERSATION_INTENTS:
                ctx = build_conversation_context(repo, q, intent)
                ans = answer_with_openai(q, ctx, mode="conversation")
            else:
                ctx = build_accounting_context(repo, q, chat_key=chat_key)
                ans = answer_with_openai(q, ctx, mode="accounting")
            return _partial_notice(repo) + ans
        except Exception:
            log.exception("OpenAI 応答失敗、フォールバックします")
        return _partial_notice(repo) + _fallback_text(structured)
    except Exception as e:
        log.exception("LINE / answer_for_user: Sheets または処理エラー")
        return format_sheets_user_message_with_retry_hint(e)

from __future__ import annotations

import re
from datetime import date
from typing import Any

from app.parse_util import extract_month_from_question
from app.services import SheetRepository
from app.text_normalize import normalize_user_question

_GREETING_RE = re.compile(
    r"^(こんにちは|こんちゃ|こんばんは|おはよう|おはよ|はろー|やあ|よう|hello|hi)\s*[!！。、,]*\s*$",
    re.IGNORECASE,
)

_ACCOUNTING_HINTS: tuple[str, ...] = (
    "売上",
    "経費",
    "利益",
    "収支",
    "入金",
    "支払",
    "未入金",
    "未払",
    "請求",
    "黒字",
    "赤字",
    "月次",
    "レポート",
    "サマリー",
    "損益",
    "スポンサー",
    "事業実績",
    "経費詳細",
    "シート",
    "スプレッド",
    "今月どう",
    "今月の状況",
    "今月の売上",
    "督促",
    "振込",
    "payable",
    "receivable",
    "summary",
    "pl",
)

_CASUAL_HINTS: tuple[str, ...] = (
    "ありがと",
    "有難う",
    "お疲れ",
    "おつかれ",
    "よろしく",
    "承知",
    "了解",
    "なるほど",
    "そうなんだ",
    "そうなん",
    "へー",
    "へえ",
    "笑",
    "www",
    "w ",
    "雑談",
    "暇",
    "元気",
    "調子",
    "LIRAって",
    "LIRAとは",
    "リラって",
    "あなたは誰",
    "君は誰",
    "何ができる",
    "できること",
    "使い方",
    "ヘルプ",
    "助けて",
    "話そう",
    "話して",
    "ちょっと相談",
    "おはよう",
    "こんにちは",
    "こんばんは",
)


def extract_month(question: str) -> str | None:
    return extract_month_from_question(normalize_user_question(question))


def _has(q: str, *keys: str) -> bool:
    return any(k in q for k in keys)


def _has_month_scoped_request(q: str) -> bool:
    """「先月の全体出して」「3月の数値」など月＋取得依頼。"""
    nq = normalize_user_question(q)
    if not extract_month_from_question(nq):
        return False
    return _has(
        nq,
        "全体",
        "数値",
        "数字",
        "実績",
        "状況",
        "まとめ",
        "サマリー",
        "出して",
        "見せて",
        "教えて",
        "表示",
        "売上",
        "経費",
        "利益",
        "収支",
        "損益",
    )


def has_accounting_intent(q: str) -> bool:
    nq = normalize_user_question(q)
    return _has(nq, *_ACCOUNTING_HINTS) or _has_month_scoped_request(nq)


def is_casual_chat(q: str) -> bool:
    """経理以外の挨拶・雑談・自己紹介系（短いメッセージ向け）。"""
    nq = normalize_user_question(q)
    if has_accounting_intent(nq):
        return False
    if _GREETING_RE.match(nq):
        return True
    if _has(nq, *_CASUAL_HINTS):
        return True
    if len(nq) <= 48 and _has(
        nq,
        "こんにちは",
        "こんばんは",
        "おはよう",
        "はじめまして",
        "初めまして",
    ):
        return True
    return False


def _is_monthly_pl_query(q: str) -> bool:
    """事業実績表の月次（売上・経費・利益）。支払予定タブとは別。"""
    nq = normalize_user_question(q)
    if _has_month_scoped_request(nq):
        return True
    if extract_month_from_question(nq):
        if _has(nq, "売上", "経費", "利益", "収支", "損益", "黒字", "赤字", "粗利"):
            return True
    if _has(
        nq,
        "売上は",
        "売上いくら",
        "今月の売上",
        "今月どう",
        "今月のBRANDVOX",
        "今月の状況",
        "収支は",
        "収支",
        "黒字",
        "赤字",
        "利益出てる",
        "粗利",
        "経費いくら",
        "経費は",
        "経費？",
        "経費 ",
        "利益は",
        "利益？",
        "損益",
        "PL",
    ):
        return True
    if _has(nq, "売上", "summary") and not _has(nq, "入金予定", "支払い予定", "未入金"):
        return True
    return False


def detect_accounting_focus(q: str) -> str | None:
    nq = normalize_user_question(q)
    if _has(nq, "経費") and not _has(nq, "売上", "利益", "全体", "数値", "数字"):
        return "expenses"
    if _has(nq, "売上") and not _has(nq, "全体", "数値", "数字", "経費"):
        return "sales"
    if _has(nq, "利益", "粗利", "黒字", "赤字") and not _has(nq, "全体", "数値"):
        return "profit"
    if _has(nq, "全体", "数値", "数字", "まとめ", "状況", "サマリー", "出して"):
        return "overview"
    return None


def route_question(question: str, repo: SheetRepository) -> dict[str, Any]:
    """意図のざっくり分類。"""
    q = normalize_user_question(question.strip())
    month = extract_month(q) or f"{date.today().year:04d}-{date.today().month:02d}"
    focus = detect_accounting_focus(q)

    if not has_accounting_intent(q):
        if _GREETING_RE.match(q):
            return {"intent": "greeting", "month": month}
        if is_casual_chat(q):
            return {"intent": "casual_chat", "month": month}

    if _has(
        q,
        "まとめて",
        "レポート出して",
        "月次まとめ",
        "状況まとめ",
        "今月の状況まとめ",
        "サマリー出して",
        "全体出して",
        "全体見せて",
        "数値出して",
        "数字出して",
        "実績出して",
    ):
        return {"intent": "summary", "month": month, "focus": focus or "overview"}

    if _is_monthly_pl_query(q):
        return {
            "intent": "summary",
            "month": month,
            "focus": focus or ("overview" if _has_month_scoped_request(q) else None),
        }

    if _has(
        q,
        "今日入金",
        "今週入金",
        "入金予定",
        "入金予定は",
        "入金済み",
        "入金済",
        "未入金",
        "回収できてる",
        "スポンサーの入金",
        "入金ある",
        "入金は",
        "入金って",
    ):
        rows = [r for r in repo.load_receivables() if r.is_unpaid()]
        if "未入金" in q or "回収" in q:
            return {"intent": "unpaid", "count": len(rows)}
        return {"intent": "receivables", "count": len(repo.load_receivables())}

    if any(k in q for k in ("督促", "遅延", "延滞", "overdue")):
        rows = [r for r in repo.load_receivables() if r.is_unpaid()]
        return {"intent": "overdue_reminder", "month": month, "unpaid_count": len(rows)}

    if any(k in q for k in ("入金確認", "支払いました", "振込済")) and "未入金" not in q:
        rows = [r for r in repo.load_receivables() if r.payment_date]
        return {"intent": "payment_received", "rows_with_payment_date": len(rows)}

    if any(k in q for k in ("入金済",)) and "未入金" not in q:
        rows = [r for r in repo.load_receivables() if r.payment_date]
        return {"intent": "payment_received", "rows_with_payment_date": len(rows)}

    if _has(q, "未払い", "未入金一覧", "未収"):
        rows = [r for r in repo.load_receivables() if r.is_unpaid()]
        return {"intent": "unpaid", "count": len(rows)}

    if _has(
        q,
        "今日払う",
        "今月払う",
        "今月払うもの",
        "支払い予定",
        "支払予定",
        "経費一覧",
        "経費詳細",
        "未払",
        "買掛",
        "payable",
    ):
        return {"intent": "payables", "count": len(repo.load_payables())}

    if any(k in q for k in ("支払",)) and not _has(q, "入金", "振込済"):
        return {"intent": "payables", "count": len(repo.load_payables())}

    if any(k in q for k in ("入金予定", "売掛", "レシーバブル", "receivable")) or (
        "入金" in q
        and "未入金" not in q
        and not any(k in q for k in ("入金確認", "入金済", "振込済", "支払いました"))
    ):
        return {"intent": "receivables", "count": len(repo.load_receivables())}

    if is_casual_chat(q):
        return {"intent": "casual_chat", "month": month}

    return {
        "intent": "unknown",
        "hint": "売上・入金・支払・未入金・月次 などのキーワードで試してください。",
    }

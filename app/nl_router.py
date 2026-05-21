from __future__ import annotations

import re
from datetime import date
from typing import Any

from app.services import SheetRepository

_MONTH_RE = re.compile(r"(20\d{2})[-年/](\d{1,2})")
_GREETING_RE = re.compile(
    r"^(こんにちは|こんちゃ|こんばんは|おはよう|おはよ|はろー|やあ|よう|hello|hi)\s*[!！。、,]*\s*$",
    re.IGNORECASE,
)

# 経理キーワードが無いときだけ雑談扱い（あれば先に summary / receivables 等へ）
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
    "損益",
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
    m = _MONTH_RE.search(question)
    if not m:
        return None
    y, mo = int(m.group(1)), int(m.group(2))
    return f"{y:04d}-{mo:02d}"


def _has(q: str, *keys: str) -> bool:
    return any(k in q for k in keys)


def has_accounting_intent(q: str) -> bool:
    return _has(q, *_ACCOUNTING_HINTS)


def is_casual_chat(q: str) -> bool:
    """経理以外の挨拶・雑談・自己紹介系（短いメッセージ向け）。"""
    if has_accounting_intent(q):
        return False
    if _GREETING_RE.match(q):
        return True
    if _has(q, *_CASUAL_HINTS):
        return True
    # 短い挨拶混じり（「こんにちは、よろしく」等）
    if len(q) <= 48 and _has(
        q,
        "こんにちは",
        "こんばんは",
        "おはよう",
        "はじめまして",
        "初めまして",
    ):
        return True
    return False


def route_question(question: str, repo: SheetRepository) -> dict[str, Any]:
    """意図のざっくり分類。summary の月次行取得だけは run_rules_ask に任せ、ここでは呼ばない。"""
    q = question.strip()
    month = extract_month(q) or f"{date.today().year:04d}-{date.today().month:02d}"

    # 経理キーワードが無ければ雑談優先（Sheets 読み取りを避ける）
    if not has_accounting_intent(q):
        if _GREETING_RE.match(q):
            return {"intent": "greeting", "month": month}
        if is_casual_chat(q):
            return {"intent": "casual_chat", "month": month}

    # --- レポート系（先に判定） ---
    if _has(
        q,
        "まとめて",
        "レポート出して",
        "月次まとめ",
        "状況まとめ",
        "今月の状況まとめ",
        "サマリー出して",
    ):
        return {"intent": "summary", "month": month}

    # --- 売上・収支系 ---
    if _has(
        q,
        "今月どう",
        "今月のBRANDVOX",
        "今月の状況",
        "売上は",
        "売上いくら",
        "今月の売上",
        "収支は",
        "収支",
        "黒字",
        "赤字",
        "利益出てる",
        "粗利",
        "経費いくら",
        "経費は",
        "経費 ",
        "利益は",
        "PL",
        "損益",
    ):
        return {"intent": "summary", "month": month}

    # --- 入金系 ---
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

    # --- 支払・経費系 ---
    if _has(
        q,
        "今日払う",
        "今月払う",
        "今月払うもの",
        "支払い予定",
        "支払予定",
        "経費一覧",
        "未払",
        "買掛",
        "payable",
        "経費",
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

    if any(
        k in q
        for k in (
            "月次",
            "レポート",
            "サマリー",
            "売上",
            "summary",
        )
    ):
        return {"intent": "summary", "month": month}

    if is_casual_chat(q):
        return {"intent": "casual_chat", "month": month}

    return {
        "intent": "unknown",
        "hint": "売上・入金・支払・未入金・月次 などのキーワードで試してください。",
    }

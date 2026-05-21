"""ユーザー質問の表記ゆれを正規化（ルーティング・月抽出の前に適用）。"""

from __future__ import annotations

# (誤表記, 正規形) — 長い語句を先に置換する想定で順序固定
_QUESTION_TYPOS: tuple[tuple[str, str], ...] = (
    ("売り上げ", "売上"),
    ("売上げ", "売上"),
    ("うりあげ", "売上"),
    ("ウリアゲ", "売上"),
    ("けいひ", "経費"),
    ("だして", "出して"),
    ("だして。", "出して。"),
    ("みせて", "見せて"),
    ("おしえて", "教えて"),
)


def normalize_user_question(question: str) -> str:
    q = (question or "").strip()
    if not q:
        return q
    for old, new in _QUESTION_TYPOS:
        q = q.replace(old, new)
    return q

"""「何ができますか？」系 — 専門用語なしの箇条書き（LINE / ask 向け）"""

from __future__ import annotations

import re

_IRIE_BULLETS: tuple[str, ...] = (
    "今月の売上・経費・利益の説明",
    "入金予定・未入金の確認",
    "支払い・経費の金額や一覧",
    "会社の経理用の表の数字を読んで答える（設定されている表）",
    "雑談や軽い相談",
    "数字の確定や請求書の発行そのものは人の確認が必要なことがあります",
)

_HELP_RE = re.compile(
    r"何ができ|なにができ|できること|何ができます|何をしてくれ|何を手伝|"
    r"何が使え|使い方|ヘルプ|help|機能一覧|機能は何|できる？|できますか|"
    r"お願いできる|仕事は何|役割は|IRIEって|イリって|あなたは誰",
    re.IGNORECASE,
)


def is_capabilities_help_question(text: str) -> bool:
    n = text.strip().replace(" ", "").replace("　", "")
    if not n or len(n) > 80:
        return False
    return bool(_HELP_RE.search(n))


def format_irie_capabilities_reply() -> str:
    lines = ["IRIE（経理）で、いまお手伝いできることはだいたい次のとおりです。", ""]
    lines.extend(f"・{b}" for b in _IRIE_BULLETS)
    lines.append("")
    lines.append("例:「今月どう？」「入金予定」「未入金ある？」など、気軽に聞いてください。")
    return "\n".join(lines)

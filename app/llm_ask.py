from __future__ import annotations

import json
from typing import Any, Literal

from openai import OpenAI

from app.config import get_settings
from app.llm_usage import record_llm_usage, usage_from_chat_completion

ResponseMode = Literal["accounting", "conversation"]

_SYSTEM_ACCOUNTING = (
    "あなたは株式会社BRANDVOXの経理担当AI「LIRA」です。\n"
    "次の JSON には (1) rules_extracted … 列名が合ったときの構造化データ、"
    "(2) raw_sheet_previews … 各タブの先頭グリッド（実シートの生データ）が含まれます。\n"
    "BRANDVOX の事業実績表・経費詳細・スポンサー管理FILE などは、"
    "固定の「月次サマリー」列とは限りません。rules_extracted が空でも、"
    "raw_sheet_previews の grid から売上・経費・利益・入金・支払を読み取って答えてください。\n"
    "authoritative_month_breakdown がある場合は最優先（sales / expense_line_items 等）。\n"
    "breakdown にある数値について「シート上では確認できません」とは言わない。\n"
    "質問に【リプライ先のメッセージ】があれば「これ」「それ」は引用先を指す。\n"
    "target_month のみを対象月として明記。month_selection_note を冒頭に反映。\n"
    "accounting_focus=overview なら売上・経費・利益の合計と要点。expenses/sales も同様に focus に従う。\n"
    "根拠のない数値は出さない。雑談や天気の話はしない。\n"
    "ユーザーの質問に、簡潔な日本語で答えてください。箇条書き可。"
)

_SYSTEM_CONVERSATION = (
    "あなたは株式会社BRANDVOXの経理担当AI「LIRA」です。\n"
    "経理のプロだが、人間らしい会話も大切にします。\n"
    "挨拶・お礼・雑談・自己紹介・「何ができる？」には、温かく自然な日本語で返してください。"
    "2〜5文程度。絵文字は使わない。\n"
    "毎回いきなり経理データを羅列しない。雑談のあと、さりげなく経理で手伝えることを1文添えてもよい"
    "（lira_capabilities を参照）。\n"
    "JSON に monthly_summary_teaser があれば、雑談の流れで軽く触れてもよいが、"
    "無理に数字を出さない。\n"
    "秘密や社外秘の推測はしない。"
)


def _resolve_mode(context: dict[str, Any], mode: ResponseMode | None) -> ResponseMode:
    if mode:
        return mode
    if context.get("response_mode") == "conversation":
        return "conversation"
    return "accounting"


def answer_with_openai(
    question: str,
    context: dict[str, Any],
    *,
    mode: ResponseMode | None = None,
) -> str:
    s = get_settings()
    if not s.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY が未設定です。")

    resolved = _resolve_mode(context, mode)
    system = _SYSTEM_CONVERSATION if resolved == "conversation" else _SYSTEM_ACCOUNTING
    temperature = 0.65 if resolved == "conversation" else 0.3
    max_tokens = 700 if resolved == "conversation" else 1800

    client = OpenAI(api_key=s.openai_api_key)
    payload = json.dumps(context, ensure_ascii=False, default=str)
    user = f"質問:\n{question}\n\n参照データ (JSON):\n{payload}"
    cust = (context.get("veriora_customer_context") or "").strip()
    if cust:
        user = f"{cust}\n\n---\n\n{user}"

    resp = client.chat.completions.create(
        model=s.openai_model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=temperature,
        max_tokens=max_tokens,
    )
    usage = usage_from_chat_completion(
        resp,
        source=f"llm_ask:{resolved}",
        model=s.openai_model,
    )
    if usage:
        record_llm_usage(usage)
    choice = resp.choices[0].message.content
    if not choice:
        raise RuntimeError("OpenAI から空の応答でした。")
    return choice.strip()

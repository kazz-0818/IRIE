from __future__ import annotations

import json
from typing import Any

from openai import OpenAI

from app.config import get_settings


def answer_with_openai(question: str, context: dict[str, Any]) -> str:
    s = get_settings()
    if not s.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY が未設定です。")

    client = OpenAI(api_key=s.openai_api_key)
    payload = json.dumps(context, ensure_ascii=False, default=str)

    system = (
        "あなたは株式会社BRANDVOXの経理担当AI「LIRA」です。\n"
        "次の JSON には (1) rules_extracted … 列名が合ったときの構造化データ、"
        "(2) raw_sheet_previews … 各タブの先頭グリッド（実シートの生データ）が含まれます。\n"
        "BRANDVOX の事業実績表・経費詳細・スポンサー管理FILE などは、"
        "固定の「月次サマリー」列とは限りません。rules_extracted が空でも、"
        "raw_sheet_previews の grid から売上・経費・利益・入金・支払を読み取って答えてください。\n"
        "横持ち（月が列方向）の表は、対象月の列と「売上」「経費」「利益」などの行ラベルを対応づけてください。\n"
        "JSON に根拠のない数値はでっち上げず、「シート上では確認できません」と述べてください。\n"
        "ユーザーの質問に、簡潔な日本語で答えてください。箇条書き可。"
    )
    user = f"質問:\n{question}\n\n参照データ (JSON):\n{payload}"

    resp = client.chat.completions.create(
        model=s.openai_model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.3,
        max_tokens=1800,
    )
    choice = resp.choices[0].message.content
    if not choice:
        raise RuntimeError("OpenAI から空の応答でした。")
    return choice.strip()

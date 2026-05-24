# LINE グループ／ルームの応答方針（IRIE）

Veriora 組織内の LINE エージェント（NEAR / SERA / IRIE 等）で共通する想定です。

## ルール

| 会話種別 | 応答 |
|----------|------|
| **1:1**（`source.type = user`） | 常に応答 |
| **グループ／ルーム** | **メンション** または **ボット名呼び** があるときのみ応答 |
| **返信（リプライ）** | 上記と同じ。引用メッセージだけでは応答しない |

## 名前呼び

環境変数 `LINE_BOT_NAME_ALIASES`（カンマ区切り）で指定。未設定時の既定:

`いり`, `イリ`, `IRIE`, `irie`

## 実装

- `app/line_group_policy.py` … 判定ロジック
- `app/line_routes.py` … Webhook で `should_respond_line_event` を通過したイベントのみ処理

## 呼びかけへの返信

- グループで **メンション** または **名前呼び** で応答するとき、LINE Profile API から取得した **発言者の表示名** で呼びかけます（例: 「田中さん、…」）。
- 表示名が取れない場合は従来どおり名前なしで返します。

## メイングループ（`LINE_MAIN_GROUP_ID`）

BRANDVOX 経理の本番トークなど、**運用上の正本グループ**の LINE `groupId`（`C` で始まる 33 文字）を Render の環境変数に設定します。

| 変数 | 説明 |
|------|------|
| `LINE_MAIN_GROUP_ID` | メイングループの groupId（エイリアス: `IRIE_LINE_MAIN_GROUP_ID`） |
| `VERIORA_RITS_GROUP_OBSERVE` | `1` のとき、応答しなかったグループ発言も RITS / `agent_logs` に `metadata.group_id` 付きで記録 |

GID の調べ方:

1. 対象グループで何か一言送る（メンション不要）。Webhook 経由で `irie.line_group_registry` に記録される。
2. `GET /debug/line/groups` または Supabase の `public.irie_line_group_registry` を参照。
3. 確定した ID を `LINE_MAIN_GROUP_ID` に設定して再デプロイ。

## 運用メモ

- グループで無言にしたい雑談は、メンション・名前なしにすれば IRIE は返信しません。
- **メンションのみ**・**名前だけ**（`いり` / `イリ` 等）でも返信します（本文は会話モードの短い挨拶として扱います）。
- `こんにちは` だけなど、メンション・名前が無いメッセージは返信しません。
- **IRIE の発言へのリプライ**（「これの利益は？」など）… 名前がなくても返信します（引用元をキャッシュから解決）。

## リプライ（引用返信）

- Webhook の `quotedMessageId` と、同一チャットで受信・送信したメッセージのキャッシュから引用文を復元します。
- LLM には `【リプライ先のメッセージ】` と `【ユーザーの質問】` を分けて渡し、「これ」「それ」を臨機応変に解釈します。

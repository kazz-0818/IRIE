# LIRA → IRIE 移行ガイド

**LIRA-リラ-『経理部』** は **IRIE-イリ-『経理部』** にリネームされました。

## GitHub

| 旧 | 新 |
|----|-----|
| `kazz-0818/LIRA` | [`kazz-0818/IRIE`](https://github.com/kazz-0818/IRIE) |

リポジトリ名は **rename** 済みです（別リポの Archive ではありません）。  
`https://github.com/kazz-0818/LIRA` は **IRIE へリダイレクト** されます。

## 環境変数（Render / ローカル）

**canonical 名**（アプリが直接読むキー）を正とします。`IRIE_*` は互換 alias として読み取りのみサポートします。

| canonical（推奨） | 互換 alias（非推奨・削除可） |
|-------------------|------------------------------|
| `LINE_CHANNEL_SECRET` | `IRIE_LINE_CHANNEL_SECRET` |
| `LINE_CHANNEL_ACCESS_TOKEN` | `IRIE_LINE_CHANNEL_ACCESS_TOKEN` |
| `SUPABASE_URL` | `IRIE_SUPABASE_URL`, `VERIORA_SUPABASE_URL` |
| `SUPABASE_SERVICE_ROLE_KEY` | `IRIE_SUPABASE_SERVICE_ROLE_KEY` |
| `OPENAI_API_KEY` | `IRIE_OPENAI_API_KEY` |
| `LINE_MAIN_GROUP_ID` | `IRIE_LINE_MAIN_GROUP_ID` |
| `SUPABASE_AUDIT_TABLE` | 既定 `irie_audit_log`（旧 `lira_audit_log`） |

**削除済み**（コード側 alias なし）: `LIRA_*`, `りら` / `リラ` / `LIRA` / `lira` の LINE 名前呼び。

## DB

- Postgres schema: `lira` → `irie`
- 監査: `irie_audit_log`（旧 `lira_audit_log`）
- LINE グループ観測: `public.irie_line_group_registry`

migration: `docs/supabase/migrations/017_rename_lira_agent_to_irie.sql`, `018_irie_line_group_registry.sql`  
共有 Supabase では NEAR `069` / `070` でも適用済み。

## Render

- サービス名: **IRIE**（`srv-d829fi3eo5us7386o5cg`）
- URL（slug 旧名）: `https://lira-ofkv.onrender.com` — slug 変更は Dashboard から別途可能

## ローカル checkout

```bash
# 旧パス
~/Downloads/System/LIRA   # → IRIE に rename 推奨

git clone https://github.com/kazz-0818/IRIE.git
```

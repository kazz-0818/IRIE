# IRIE（BRANDVOX 経理 AI MVP）

> **旧 LIRA から移行しました。** 詳細: [`docs/MIGRATION_FROM_LIRA.md`](docs/MIGRATION_FROM_LIRA.md)  
> GitHub: `kazz-0818/LIRA` → **[`kazz-0818/IRIE`](https://github.com/kazz-0818/IRIE)**（rename 済み・旧 URL はリダイレクト）

## Veriora 組織OS

このリポジトリは **Veriora** の経理部エージェント（**IRIE-イリ-『経理部』**）です。組織共通の規約・registry・手順は [`AGENTS.md`](AGENTS.md) と [`docs/veriora-architecture.md`](docs/veriora-architecture.md) を参照してください。

Google スプレッドシートを正とした会計サマリー・入金／支払スケジュール取得、定型文面生成、**OpenAI による自然文回答**、**LINE Webhook 返信**、**Supabase 監査ログ**（任意）を行う REST API です。バックエンドは **Python 3.12+** / **FastAPI**、データ取得は **Google Sheets API v4（サービスアカウント・読み取り専用スコープ）** です。

## 前提

- Google Cloud プロジェクトで **Google Sheets API** を有効化する。
- **サービスアカウント**を作成し、JSON キーをダウンロードする（リポジトリにコミットしない）。
- 対象スプレッドシートを、サービスアカウントのメール（`...@...iam.gserviceaccount.com`）に **編集者** 以上で共有する。

## 手動で必要な作業（チェックリスト）

コードだけでは動きません。次を人の手で済ませてください。

1. **Google Cloud**  
   - プロジェクトを選び、**Google Sheets API** をオンにする。  
   - **サービスアカウント**を作成し、JSON キーを取得する（Git に入れない）。

2. **スプレッドシート共有**  
   - 経理用シートを、上記 SA のメールアドレスに **編集者** で共有する。  
   - タブ名・ヘッダーは `docs/sheet-structure.md` に合わせるか、`.env` の `SHEET_*` を実シート名に合わせる。

3. **ローカル `.env`**  
   - `cp .env.example .env` または `cp env/local.env.example .env`  
   - `GOOGLE_APPLICATION_CREDENTIALS`（ファイルパス）**または** `GOOGLE_SERVICE_ACCOUNT_JSON`（JSON 全文）のどちらかを必ず設定。  
   - `SPREADSHEET_ID` を URL の `/d/` と `/edit` の間の ID にする。

4. **Render でデプロイする場合**  
   - リポジトリの **`render.yaml` は `runtime: docker`** です。**`Dockerfile`** で `pip install` と起動を同じイメージ内に固定しているため、Native Python で起きていた **`python` が無い** / **`No module named uvicorn`** を避けられます。  
   - **既存の Web Service を Native Python のまま直すのは非推奨**。ダッシュボードで **Environment を Docker** に切り替え、**Dockerfile Path** を `./Dockerfile`（リポジトリ直下）にするか、Blueprint から作り直してください。  
   - 秘密は **Environment** にのみ設定（`env/render.env.example` 参照）。**`GOOGLE_SERVICE_ACCOUNT_JSON`** 推奨。  
   - **LINE**: Webhook URL の例（いずれも POST。末尾スラッシュなし推奨）  
     - `https://（ホスト）/line/webhook`（正式）  
     - `https://（ホスト）/webhook`  
     - `https://（ホスト）/webhook/line`（語順違いでも受け付け）  
   - **LINE で「LIRA でエラーが発生しました…」のような旧定型文だけ出るとき** … 現行コードにその文言は**存在しません**（履歴上は `6f50f42` で削除）。`GET /health` の `git_commit` が GitHub `main` の最新コミットと一致するか確認し、**別の Render サービス・別 URL・別ブランチ**に Webhook が向いていないかを疑ってください。**LINE 公式アカウントマネージャー**の応答メッセージ／チャットの自動応答に同文面が入っていないかも確認してください。  
   - デプロイ後の URL を **`PUBLIC_APP_URL`** にも設定。  

   **Native Python のままにする場合（非推奨）** … ビルド用 Python と **`/usr/bin/python3`** が別になり、`No module named uvicorn` が再発しやすいです。トラブルが続くなら **Docker 運用に移行**してください。

   **ビルドログに `cargo build` が出る場合** … ランタイムが Rust になっています。**Docker** または **Language: Python** に変更。

5. **Supabase（任意）**  
   - **NEAR と同じ共有プロジェクト**の場合: SQL エディタで **`docs/supabase/migrations/001_irie_schema_init.sql`** を実行（`irie` スキーマ + `irie.irie_audit_log` + `public.irie_audit_log` 互換 VIEW）。  
   - 単体で最小構成だけ欲しい場合: `docs/supabase.sql`（`public` 実テーブルのみ）。  
   - `.env` に `SUPABASE_URL` と **`SUPABASE_SERVICE_ROLE_KEY`**（挿入用。リポジトリに書かない）を設定。  
   - `/ask` や LINE Webhook 成功時に `source` と `detail`（秘密なし）が `irie_audit_log` に追記される。  
   - Table Editor で `irie` スキーマを見るには、Supabase Dashboard → **Project Settings → API → Exposed schemas** に `irie` を追加。

6. **OpenAI（任意）**  
   - `OPENAI_API_KEY` を設定すると `POST /ask` が `mode: "openai"` で自然文 `answer` を返す。失敗時は従来どおり `mode: "rules"`。

7. **LINE（任意）**
   - `LINE_CHANNEL_SECRET` と `LINE_CHANNEL_ACCESS_TOKEN` を設定。Webhook を本番 URL に向ける。
   - **グループ／ルーム**では **メンション** または **名前呼び**（既定: `いり` / `イリ` / `IRIE`）があるときだけ返信します。1:1 は常に返信。詳細は [`docs/line-group-policy.md`](docs/line-group-policy.md)。

## 環境変数テンプレート

| ファイル | 用途 |
|----------|------|
| `.env.example` | 汎用テンプレート |
| `env/local.env.example` | ローカル用（ルートに `.env` としてコピー） |
| `env/render.env.example` | Render 用の変数名の例 |

## 環境変数

| 変数 | 必須 | 説明 |
|------|------|------|
| `GOOGLE_APPLICATION_CREDENTIALS` | ローカルでは**推奨** | サービスアカウント JSON の**絶対パス**（`GOOGLE_SERVICE_ACCOUNT_JSON` 未使用時は実質必須） |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | Render 等では**推奨** | JSON 全文を 1 変数に格納。設定時はファイルパス不要 |
| `SPREADSHEET_ID` | はい | スプレッドシート URL の `/d/` と `/edit` の間の ID |
| `PUBLIC_APP_URL` | いいえ | 本番 URL（OpenAPI `/docs` の servers。LINE Webhook のベースにも使用） |
| `SUPABASE_URL` | いいえ | 監査ログ用 |
| `SUPABASE_SERVICE_ROLE_KEY` | いいえ | サーバーからの `irie_audit_log` 挿入に推奨（`anon` の代わり） |
| `SUPABASE_ANON_KEY` | いいえ | `service_role` が無い場合のみ（RLS で insert 要設定） |
| `SUPABASE_AUDIT_TABLE` | いいえ | 既定 `irie_audit_log` |
| `OPENAI_API_KEY` | いいえ | 設定時 `/ask` と LINE が自然文優先 |
| `OPENAI_MODEL` | いいえ | 既定 `gpt-4o-mini` |
| `LINE_CHANNEL_SECRET` | いいえ | LINE Webhook 署名検証 |
| `LINE_CHANNEL_ACCESS_TOKEN` | いいえ | 返信 API 用 |
| `LINE_BOT_NAME_ALIASES` | いいえ | グループでの名前呼び（カンマ区切り。省略時 `いり,イリ,IRIE,irie`） |
| `LINE_BOT_USER_ID` | いいえ | Bot の LINE userId（`isSelf` メンションが使えない場合の補助） |
| `SHEET_SUMMARY` | いいえ | 月次サマリー用タブ名（既定: `月次サマリー`）。実名と違ってもタブ一覧＋キーワードで自動推測可 |
| `SHEET_RECEIVABLES` | いいえ | 入金予定タブ名（既定: `入金予定`）。同上 |
| `SHEET_PAYABLES` | いいえ | 支払予定タブ名（既定: `支払予定`）。同上 |
| `HEADER_ROW` | いいえ | ヘッダー行（1 始まり、既定: `1`）。`HEADER_ROW_AUTO=true` のときは自動検出に失敗した場合のフォールバック行として使う |
| `HEADER_ROW_AUTO` | いいえ | `true`（既定）で 1〜20 行からヘッダー行を推定。`false` で常に `HEADER_ROW` 行をヘッダーとする |
| `DATA_START_ROW` | いいえ | 将来拡張用（現在は `HEADER_ROW` 直下をデータとみなす） |
| `MAX_DATA_ROWS` | いいえ | 取得末尾行（既定: `5000`） |

`.env.example` をコピーして `.env` を作成してください。

```bash
cp .env.example .env
# .env を編集
```

**テンプレにキーが増えたとき**（pull 後など）、既存の値はそのままに **足りないキーだけ追記**するには:

```bash
python scripts/merge_env.py
```

（実行前に `.env` を `.env.bak` にバックアップします。）

**GCP の JSON を 1 行にしたいとき**（Render の Environment に貼りやすくする）:

```bash
jq -c . /path/to/service-account.json
```

**direnv** を使う場合は `.envrc` に `dotenv` と書けば、ディレクトリに入ったとき自動で `.env` を読み込めます（別途 direnv のインストールが必要）。

## セットアップ

```bash
cd /path/to/IRIE
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## 起動

```bash
export GOOGLE_APPLICATION_CREDENTIALS=/absolute/path/to/sa.json
export SPREADSHEET_ID=your_spreadsheet_id
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

ブラウザで `http://127.0.0.1:8000/docs`（OpenAPI UI）を開けます。

## BRANDVOX 実シート（暫定推奨設定）

IRIE 専用タブ（`月次サマリー` / `入金予定` / `支払予定`）が無くても、タブ名のキーワードと優先ルールで **事業実績表・スポンサー管理FILE・経費詳細** などを自動割当します。明示したい場合の例です。

| 変数 | 推奨値（例: 2026.3 期のブック） |
|------|----------------------------------|
| `SHEET_SUMMARY` | `事業実績表(26.3-27.8)` |
| `SHEET_RECEIVABLES` | `スポンサー管理FILE` |
| `SHEET_PAYABLES` | `経費詳細` |

**Render で動かないときの確認（優先順）**

1. `GET /health` の `git_commit` / `git_commit_short` が GitHub の `main` 最新と一致するか（別ブランチ・別サービスに Webhook が向いていないか）。  
2. `spreadsheet_access_ok` が `true` か、`sheet_titles` に想定タブが出ているか。  
3. `resolved_sheets` が期待どおりか。ずれている場合は Environment の **`SHEET_*` が古い値のまま**（例: `月次サマリー`）になっていないか。不要なら削除するか上表のとおり更新。  
4. `GET /debug/sheets?debug=true` でヘッダー行候補・列不足ヒントを確認（本番では `debug=false` 推奨）。  
5. Supabase / OpenAI は **タブ解決の主因ではありません**（監査ログ・自然文用）。Sheets 認証・`SPREADSHEET_ID`・タブ割当を先に切り分けてください。

## API 概要

| メソッド | パス | 説明 |
|----------|------|------|
| GET | `/health` | 生存確認 + `git_commit`、Google 認証有無、`spreadsheet_access_ok`、`sheet_titles`、`resolved_sheets`、OpenAI/Supabase/LINE 設定有無など |
| GET | `/debug/sheets` | タブ一覧・先頭行プレビュー・ヘッダー候補・ロールスコア・解決結果・推奨 `SHEET_*`（`debug=true` で spreadsheet_id 表示） |
| GET | `/summary?month=YYYY-MM` | 当月の売上・経費・利益・利益率（事業実績表など summary 割当タブの行または横持ち列） |
| GET | `/receivables` | 入金予定一覧（`month` / `due_from` / `due_to` で絞り込み可） |
| GET | `/payables` | 支払予定一覧（`open_only` 既定 true） |
| GET | `/unpaid` | 未入金候補 |
| POST | `/reports/monthly` | 月次レポート文（`audience`: `internal` / `client`） |
| POST | `/messages/payment-received` | 入金確認文（任意で `sheet_row_indices`） |
| POST | `/messages/overdue-reminder` | 督促文（任意で `sheet_row_indices`） |
| GET | `/integrations/status` | OpenAI / Supabase / LINE / Google 認証の有無（値は返さない） |
| POST | `/line/webhook` / `/webhook` / `/webhook/line` | LINE（同一処理） |
| POST | `/ask` | OpenAI があれば自然文 `answer` + `structured`、なければ従来のルール結果のみ |

シートの列名・構成は `docs/sheet-structure.md` を参照してください。

## Lint（任意）

```bash
pip install ruff==0.8.6
ruff check app
ruff format app
```

## ターゲットシート（設計用 ID）

開発時の想定例: `https://docs.google.com/spreadsheets/d/1DGEgDH0205d9pjV-ujvk28nmzH34Djh1JtIPELNW4jg/edit`  
実運用では自社の `SPREADSHEET_ID` に差し替えてください。

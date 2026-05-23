from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.config_env_alias import apply_irie_env_aliases

apply_irie_env_aliases()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # 本番（Render 等）で Try 用のベース URL を OpenAPI に載せる
    # （ゲートウェイ・共用ドメインと揃える）
    public_app_url: str | None = Field(default=None, alias="PUBLIC_APP_URL")

    spreadsheet_id: str = Field(..., alias="SPREADSHEET_ID")
    sheet_summary: str = Field(default="月次サマリー", alias="SHEET_SUMMARY")
    sheet_receivables: str = Field(default="入金予定", alias="SHEET_RECEIVABLES")
    sheet_payables: str = Field(default="支払予定", alias="SHEET_PAYABLES")
    header_row: int = Field(default=1, ge=1, alias="HEADER_ROW")
    header_row_auto: bool = Field(default=True, alias="HEADER_ROW_AUTO")
    data_start_row: int = Field(default=2, ge=1, alias="DATA_START_ROW")
    max_data_rows: int = Field(default=5000, ge=1, alias="MAX_DATA_ROWS")

    # ローカル: SA JSON ファイルの絶対パス。Render 等では空でも可（下の JSON 文字列を使う）
    google_application_credentials: str | None = Field(
        default=None,
        alias="GOOGLE_APPLICATION_CREDENTIALS",
    )
    # クラウド向け: サービスアカウント JSON を 1 行の文字列として格納（Render の Environment 推奨）
    google_service_account_json: str | None = Field(
        default=None,
        alias="GOOGLE_SERVICE_ACCOUNT_JSON",
    )

    # Supabase（監査ログ）。挿入には service_role 推奨
    supabase_url: str | None = Field(default=None, alias="SUPABASE_URL")
    supabase_service_role_key: str | None = Field(
        default=None,
        alias="SUPABASE_SERVICE_ROLE_KEY",
    )
    supabase_anon_key: str | None = Field(default=None, alias="SUPABASE_ANON_KEY")
    supabase_audit_table: str = Field(default="irie_audit_log", alias="SUPABASE_AUDIT_TABLE")

    # OpenAI（/ask の自然文回答）
    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4o-mini", alias="OPENAI_MODEL")

    # LINE Messaging API（Webhook 受信・返信）
    line_channel_secret: str | None = Field(default=None, alias="LINE_CHANNEL_SECRET")
    line_channel_access_token: str | None = Field(
        default=None,
        alias="LINE_CHANNEL_ACCESS_TOKEN",
    )
    # グループ／ルーム: メンションまたは名前呼びがあるときのみ返信
    line_bot_name_aliases: str | None = Field(
        default=None,
        alias="LINE_BOT_NAME_ALIASES",
    )
    line_bot_user_id: str | None = Field(
        default=None,
        alias="LINE_BOT_USER_ID",
    )
    # 運用メイングループ（LINE groupId / roomId）。未設定時は全グループを同等に扱う
    line_main_group_id: str | None = Field(
        default=None,
        alias="LINE_MAIN_GROUP_ID",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()

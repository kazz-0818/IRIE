-- IRIE 専用スキーマ（NEAR の near.* / SERA の sera.* と同様の整理）
-- 共有 Supabase で実行。冪等（IF NOT EXISTS / 条件分岐）。
--
-- 実行後:
--   - 実体: irie.irie_audit_log
--   - アプリ既定: public.irie_audit_log（互換 VIEW + INSERT トリガ）
--   - Veliora: veliora.ai_agents に irie 行を追加（既にあればスキップ）

CREATE SCHEMA IF NOT EXISTS irie;

COMMENT ON SCHEMA irie IS 'IRIE 経理エージェント専用（Veriora 共有 Supabase）';

-- ---------------------------------------------------------------------------
-- 監査ログ（/ask, line_webhook 等。API キー・生 PII は detail に入れない）
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS irie.irie_audit_log (
  id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  source     TEXT NOT NULL,
  detail     JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS irie_audit_log_created_at_idx
  ON irie.irie_audit_log (created_at DESC);

CREATE INDEX IF NOT EXISTS irie_audit_log_source_created_idx
  ON irie.irie_audit_log (source, created_at DESC);

ALTER TABLE irie.irie_audit_log ENABLE ROW LEVEL SECURITY;

COMMENT ON TABLE irie.irie_audit_log IS
  'IRIE API / LINE からの監査ログ（秘密は入れない）。実体は irie スキーマ。';

-- ---------------------------------------------------------------------------
-- シートタブ解決の診断スナップショット（任意・将来 /health から記録する場合）
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS irie.irie_sheet_resolution_log (
  id              BIGSERIAL PRIMARY KEY,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  spreadsheet_id  TEXT,
  resolved_sheets JSONB NOT NULL DEFAULT '{}'::jsonb,
  warnings        JSONB NOT NULL DEFAULT '[]'::jsonb,
  sheet_titles    JSONB NOT NULL DEFAULT '[]'::jsonb
);

CREATE INDEX IF NOT EXISTS irie_sheet_resolution_log_created_idx
  ON irie.irie_sheet_resolution_log (created_at DESC);

ALTER TABLE irie.irie_sheet_resolution_log ENABLE ROW LEVEL SECURITY;

COMMENT ON TABLE irie.irie_sheet_resolution_log IS
  'GET /health や /debug/sheets 相当のタブ解決結果の履歴（任意）。';

-- ---------------------------------------------------------------------------
-- public に残っている実テーブルがあれば irie スキーマへ移す
-- ---------------------------------------------------------------------------
DO $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = 'public'
      AND c.relname = 'irie_audit_log'
      AND c.relkind = 'r'
  ) THEN
    ALTER TABLE public.irie_audit_log SET SCHEMA irie;
    RAISE NOTICE 'irie_init: moved public.irie_audit_log → irie.irie_audit_log';
  END IF;
END $$;

-- ---------------------------------------------------------------------------
-- public 互換 VIEW（Supabase クライアントの .table("irie_audit_log") 用）
-- ---------------------------------------------------------------------------
DROP VIEW IF EXISTS public.irie_audit_log CASCADE;

CREATE VIEW public.irie_audit_log AS
  SELECT id, created_at, source, detail
  FROM irie.irie_audit_log;

COMMENT ON VIEW public.irie_audit_log IS
  '互換VIEW → irie.irie_audit_log。INSERT は下記トリガ経由。';

CREATE OR REPLACE FUNCTION irie.public_irie_audit_log_insert()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = irie, public
AS $$
BEGIN
  INSERT INTO irie.irie_audit_log (id, created_at, source, detail)
  VALUES (
    COALESCE(NEW.id, gen_random_uuid()),
    COALESCE(NEW.created_at, now()),
    NEW.source,
    COALESCE(NEW.detail, '{}'::jsonb)
  );
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_public_irie_audit_log_insert ON public.irie_audit_log;

CREATE TRIGGER trg_public_irie_audit_log_insert
  INSTEAD OF INSERT ON public.irie_audit_log
  FOR EACH ROW
  EXECUTE FUNCTION irie.public_irie_audit_log_insert();

-- ---------------------------------------------------------------------------
-- Veliora OS マスタ（NEAR migration 046 と同じ。共有 DB で未登録なら追加）
-- ---------------------------------------------------------------------------
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM pg_namespace WHERE nspname = 'veliora'
  ) AND EXISTS (
    SELECT 1
    FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = 'veliora' AND c.relname = 'ai_agents'
  ) THEN
    INSERT INTO veliora.ai_agents (agent_code, display_name, parent_brand)
    VALUES ('irie', 'IRIE', 'Veliora OS')
    ON CONFLICT (agent_code) DO NOTHING;
  END IF;
END $$;

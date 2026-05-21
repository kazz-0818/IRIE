-- LIRA — Supabase 初期セットアップ（エントリポイント）
--
-- 【推奨】NEAR と同様の lira スキーマ + public 互換 VIEW は次を実行:
--   docs/supabase/migrations/001_lira_schema_init.sql
--
-- 下記は最小版（public 実テーブルのみ）。共有 DB で NEAR 方式に揃えるなら上記 migration を使う。

-- === 最小版（レガシー・単体プロジェクト向け） ===
create table if not exists public.lira_audit_log (
  id uuid primary key default gen_random_uuid(),
  created_at timestamptz not null default now(),
  source text not null,
  detail jsonb not null default '{}'::jsonb
);

create index if not exists lira_audit_log_created_at_idx on public.lira_audit_log (created_at desc);

alter table public.lira_audit_log enable row level security;

comment on table public.lira_audit_log is 'LIRA API / LINE からの監査ログ（秘密は入れない）';

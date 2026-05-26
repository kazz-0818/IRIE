"""Veliora canonical Supabase repositories (optional; 既存 audit は維持)."""

from app.services.supabase.repositories.audit_logs import save_audit_log

__all__ = ["save_audit_log"]

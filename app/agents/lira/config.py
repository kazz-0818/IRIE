"""LIRA agent folder — 参照用。実行は既存 app 経路のまま。"""
from __future__ import annotations

AGENT_KEY = "lira"

VERIORA_TABLES_USED = (
    "veriora.ai_agents",
    "veriora.agent_audit_logs",
)

IMPLEMENTATION_NOTE = "See app/ (existing LIRA handlers); registry in app/agents/registry.py"

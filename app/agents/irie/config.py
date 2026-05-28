"""IRIE agent folder — 参照用。実行は既存 app 経路のまま。"""
from __future__ import annotations

AGENT_KEY = "irie"

VERIORA_TABLES_USED = (
    "veliora.ai_agents",
    "veliora.agent_audit_logs",
)

IMPLEMENTATION_NOTE = "See app/ (existing IRIE handlers); registry in app/agents/registry.py"

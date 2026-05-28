"""Veliora canonical Postgres schema (migration 073 後は veliora)."""

VELIORA_SCHEMA = "veliora"

# deprecated alias
VERIORA_SCHEMA = VELIORA_SCHEMA

VELIORA_TABLES = {
    "ai_agents": f"{VELIORA_SCHEMA}.ai_agents",
    "conversations": f"{VELIORA_SCHEMA}.conversations",
    "messages": f"{VELIORA_SCHEMA}.messages",
    "agent_audit_logs": f"{VELIORA_SCHEMA}.agent_audit_logs",
}

VERIORA_TABLES = VELIORA_TABLES

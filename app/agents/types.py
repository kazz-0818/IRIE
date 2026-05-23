"""Veriora agent registry — 共通データ型（IRIE）。"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class AgentDefinition:
    """`id` は小文字。`code` は表示用（大文字推奨）。"""

    id: str
    code: str
    kana: str
    department: str
    display_name: str
    role: str
    description: str
    primary_responsibilities: tuple[str, ...]
    out_of_scope: tuple[str, ...]
    handoff_rules: tuple[str, ...]
    allowed_actions: tuple[str, ...]
    requires_approval_actions: tuple[str, ...]
    enabled: bool
    icon_key: str | None = None
    line_account_name: str | None = None
    system_prompt_key: str | None = None
    tags: tuple[str, ...] = field(default_factory=tuple)
    created_at: str | None = None
    updated_at: str | None = None

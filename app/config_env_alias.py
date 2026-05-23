"""Phase 3: 読み取り時 env alias（canonical ← legacy）。"""

from __future__ import annotations

import os
from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(frozen=True)
class EnvAliasRule:
    canonical: str
    legacy: tuple[str, ...]
    deprecated_legacy: bool = False


def _pick_first(keys: Iterable[str]) -> str | None:
    for k in keys:
        v = (os.environ.get(k) or "").strip()
        if v:
            return v
    return None


def apply_env_aliases(rules: tuple[EnvAliasRule, ...], *, service: str = "irie") -> None:
    for rule in rules:
        if _pick_first((rule.canonical,)):
            continue
        for leg in rule.legacy:
            v = _pick_first((leg,))
            if not v:
                continue
            os.environ[rule.canonical] = v
            if rule.deprecated_legacy:
                print(
                    f"[veriora-env:{service}] deprecated env {leg!r} → use {rule.canonical!r}",
                    flush=True,
                )
            break


IRIE_ENV_ALIASES: tuple[EnvAliasRule, ...] = (
    EnvAliasRule(
        "LINE_CHANNEL_SECRET",
        ("IRIE_LINE_CHANNEL_SECRET",),
        deprecated_legacy=True,
    ),
    EnvAliasRule(
        "LINE_CHANNEL_ACCESS_TOKEN",
        ("IRIE_LINE_CHANNEL_ACCESS_TOKEN",),
        deprecated_legacy=True,
    ),
    EnvAliasRule(
        "SUPABASE_URL",
        ("IRIE_SUPABASE_URL", "VERIORA_SUPABASE_URL"),
        deprecated_legacy=True,
    ),
    EnvAliasRule(
        "SUPABASE_SERVICE_ROLE_KEY",
        ("IRIE_SUPABASE_SERVICE_ROLE_KEY", "VERIORA_SUPABASE_SERVICE_ROLE_KEY"),
        deprecated_legacy=True,
    ),
    EnvAliasRule(
        "OPENAI_API_KEY",
        ("IRIE_OPENAI_API_KEY", "VERIORA_OPENAI_API_KEY"),
        deprecated_legacy=True,
    ),
    EnvAliasRule(
        "PUBLIC_APP_URL",
        ("VERIORA_PUBLIC_BASE_URL", "IRIE_PUBLIC_APP_URL"),
        deprecated_legacy=True,
    ),
    EnvAliasRule(
        "VERIORA_RITS_BASE_URL",
        ("RITS_BASE_URL", "RITS_URL", "IRIE_RITS_BASE_URL"),
        deprecated_legacy=True,
    ),
    EnvAliasRule(
        "VERIORA_RITS_ADMIN_API_KEY",
        ("RITS_ADMIN_API_KEY", "IRIE_RITS_ADMIN_API_KEY"),
        deprecated_legacy=True,
    ),
    EnvAliasRule(
        "LINE_MAIN_GROUP_ID",
        ("IRIE_LINE_MAIN_GROUP_ID", "LIRA_LINE_MAIN_GROUP_ID"),
        deprecated_legacy=True,
    ),
)


def apply_irie_env_aliases() -> None:
    apply_env_aliases(IRIE_ENV_ALIASES, service="irie")

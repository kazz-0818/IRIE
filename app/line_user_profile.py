from __future__ import annotations

import logging

import httpx

from app.config import get_settings

log = logging.getLogger(__name__)


async def fetch_line_caller_display_name(
    user_id: str,
    *,
    group_id: str | None = None,
    room_id: str | None = None,
) -> str | None:
    s = get_settings()
    token = (s.line_channel_access_token or "").strip()
    if not token:
        return None
    if group_id:
        url = (
            f"https://api.line.me/v2/bot/group/{group_id}/member/{user_id}"
        )
    elif room_id:
        url = (
            f"https://api.line.me/v2/bot/room/{room_id}/member/{user_id}"
        )
    else:
        url = f"https://api.line.me/v2/bot/profile/{user_id}"
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(
                url,
                headers={"Authorization": f"Bearer {token}"},
                timeout=12.0,
            )
        if r.status_code >= 400:
            log.warning(
                "LIRA LINE profile API: %s user=%s",
                r.status_code,
                user_id[:8],
            )
            return None
        data = r.json()
        name = (data.get("displayName") or "").strip()
        return name or None
    except Exception:
        log.exception("fetch_line_caller_display_name failed")
        return None

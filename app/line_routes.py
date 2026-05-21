from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
from functools import partial
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException, Request
from starlette.concurrency import run_in_threadpool

from app.audit_supabase import log_audit
from app.combined_ask import answer_for_user
from app.config import get_settings
from app.line_group_policy import (
    normalize_group_question,
    parse_name_aliases,
    should_respond_line_event,
)
from app.sheets_errors import format_sheets_user_message_with_retry_hint

log = logging.getLogger(__name__)

router = APIRouter(prefix="/line", tags=["line"])


def _verify_signature(channel_secret: str, body: bytes, signature: str | None) -> bool:
    if not signature:
        return False
    mac = hmac.new(channel_secret.encode("utf-8"), body, hashlib.sha256).digest()
    expected = base64.b64encode(mac).decode()
    return hmac.compare_digest(expected, signature)


async def _reply_line(reply_token: str, text: str) -> bool:
    """返信 API を叩く。失敗しても例外は出さない（Webhook 本体は 200 を返すため）。"""
    s = get_settings()
    token = s.line_channel_access_token
    if not token:
        log.warning("LINE_CHANNEL_ACCESS_TOKEN 未設定のため返信できません")
        return False
    payload: dict[str, Any] = {
        "replyToken": reply_token,
        "messages": [{"type": "text", "text": text[:4800]}],
    }
    try:
        async with httpx.AsyncClient() as client:
            r = await client.post(
                "https://api.line.me/v2/bot/message/reply",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=45.0,
            )
        if r.status_code >= 400:
            log.warning("LINE reply API: %s %s", r.status_code, r.text[:500])
            return False
    except Exception:
        log.exception("LINE reply API 通信エラー")
        return False
    return True


def _question_from_event(
    ev: dict[str, Any],
    *,
    aliases: tuple[str, ...],
    respond_reason: str,
) -> str:
    msg = ev.get("message") or {}
    text = (msg.get("text") or "").strip()
    mention = msg.get("mention")
    source_type = (ev.get("source") or {}).get("type") or ""

    if source_type in ("group", "room"):
        q = normalize_group_question(text, mention, aliases)
    else:
        q = text

    if not q and respond_reason == "mention":
        return "（メンション）"
    return q


async def handle_line_webhook(request: Request) -> dict[str, str]:
    s = get_settings()
    if not s.line_channel_secret:
        raise HTTPException(503, "LINE_CHANNEL_SECRET が未設定です。")

    body = await request.body()
    sig = request.headers.get("X-Line-Signature")
    if not _verify_signature(s.line_channel_secret, body, sig):
        raise HTTPException(400, "Invalid signature")

    if not body.strip():
        return {}

    try:
        data = json.loads(body.decode("utf-8"))
    except json.JSONDecodeError as e:
        raise HTTPException(400, "Invalid JSON") from e

    aliases = parse_name_aliases(s.line_bot_name_aliases)
    bot_user_id = (s.line_bot_user_id or "").strip() or None

    for ev in data.get("events", []):
        if ev.get("type") != "message":
            continue
        msg = ev.get("message") or {}
        if msg.get("type") != "text":
            continue

        should, reason = should_respond_line_event(
            ev,
            aliases=aliases,
            bot_user_id=bot_user_id,
        )
        if not should:
            log.debug(
                "LINE skip: reason=%s source=%s",
                reason,
                (ev.get("source") or {}).get("type"),
            )
            continue

        reply_token = ev.get("replyToken")
        if not reply_token:
            continue

        source_type = (ev.get("source") or {}).get("type") or ""
        q = _question_from_event(ev, aliases=aliases, respond_reason=reason)
        if not q:
            continue

        try:
            text_out = await run_in_threadpool(partial(answer_for_user, q))
            if not (text_out or "").strip():
                text_out = "（応答を生成できませんでした。もう一度お試しください。）"
            await _reply_line(reply_token, text_out)
        except Exception as e:
            log.exception("LINE webhook 処理エラー")
            log.error(
                "LINE webhook 例外の要約: type=%s repr=%s",
                type(e).__name__,
                repr(e)[:500],
            )
            err_reply = format_sheets_user_message_with_retry_hint(e, line_time_hint=True)
            try:
                await _reply_line(reply_token, err_reply)
            except Exception:
                log.exception("LINE エラー返信も失敗")
        else:
            try:
                log_audit(
                    "line_webhook",
                    {
                        "question_len": len(q),
                        "line_source": source_type,
                        "respond_reason": reason,
                    },
                )
            except Exception:
                log.exception("監査ログ（Supabase）の記録に失敗しました（返信は済み）")

    return {}


@router.post("/webhook")
async def line_webhook(request: Request) -> dict[str, str]:
    return await handle_line_webhook(request)

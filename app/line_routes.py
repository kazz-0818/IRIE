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

from app.audit_supabase import log_audit, _supabase_client
from app.customers.resolve import (
    build_customer_context_prompt,
    resolve_customer_from_line,
)
from app.combined_ask import answer_for_user
from app.config import get_settings
from app.line_caller_address import prefix_reply_with_caller
from app.rits_ingest import record_line_exchange_to_rits
from app.line_group_policy import (
    normalize_group_question,
    parse_name_aliases,
    should_respond_line_event,
)
from app.line_message_cache import get_line_message_cache, line_chat_key
from app.line_quote_context import enrich_question_with_quote, resolve_line_quote
from app.line_user_profile import fetch_line_caller_display_name
from app.sheets_errors import format_sheets_user_message_with_retry_hint
from app.text_normalize import normalize_user_question

log = logging.getLogger(__name__)

router = APIRouter(prefix="/line", tags=["line"])


def _verify_signature(channel_secret: str, body: bytes, signature: str | None) -> bool:
    if not signature:
        return False
    mac = hmac.new(channel_secret.encode("utf-8"), body, hashlib.sha256).digest()
    expected = base64.b64encode(mac).decode()
    return hmac.compare_digest(expected, signature)


def _remember_inbound_message(ev: dict[str, Any], chat_key: str) -> None:
    msg = ev.get("message") or {}
    mid = msg.get("id")
    text = (msg.get("text") or "").strip()
    if mid and text:
        get_line_message_cache().put(chat_key, str(mid), text, "inbound")


async def _reply_line(
    reply_token: str,
    text: str,
    *,
    chat_key: str | None = None,
) -> bool:
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
        if chat_key and r.status_code < 300:
            try:
                body = r.json()
                for sm in body.get("sentMessages") or []:
                    mid = sm.get("id")
                    if mid:
                        get_line_message_cache().put(
                            chat_key, str(mid), text[:4800], "outbound"
                        )
            except Exception:
                log.debug("LINE 返信 messageId のキャッシュに失敗", exc_info=True)
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

    if not q:
        if respond_reason == "mention":
            return "（メンション）"
        if respond_reason == "name_call":
            return "（名前呼び）"
        if respond_reason == "quote_reply_to_bot":
            return "（リプライ）"
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
    cache = get_line_message_cache()

    for ev in data.get("events", []):
        if ev.get("type") != "message":
            continue
        msg = ev.get("message") or {}
        if msg.get("type") != "text":
            continue

        source = ev.get("source") or {}
        chat_key = line_chat_key(source)
        _remember_inbound_message(ev, chat_key)

        quote = resolve_line_quote(msg, chat_key, cache)

        should, reason = should_respond_line_event(
            ev,
            aliases=aliases,
            bot_user_id=bot_user_id,
            quote=quote,
        )
        if not should:
            log.debug(
                "LINE skip: reason=%s source=%s",
                reason,
                source.get("type"),
            )
            continue

        reply_token = ev.get("replyToken")
        if not reply_token:
            continue

        source_type = source.get("type") or ""
        q = _question_from_event(ev, aliases=aliases, respond_reason=reason)
        if not q:
            continue

        q = enrich_question_with_quote(q, quote)

        line_user_id = source.get("userId")
        if isinstance(line_user_id, str) and line_user_id.strip():
            sb = _supabase_client()
            if sb is not None:
                try:
                    cid = resolve_customer_from_line(
                        sb,
                        line_user_id.strip(),
                        None,
                    )
                    if cid:
                        block = build_customer_context_prompt(sb, cid)
                        if block:
                            q = f"{block}\n\n---\n\n{q}"
                except Exception:
                    log.debug("customer context resolve skipped", exc_info=True)

        caller_display_name: str | None = None
        if reason in ("mention", "name_call"):
            uid = source.get("userId")
            if isinstance(uid, str) and uid.strip():
                caller_display_name = await fetch_line_caller_display_name(
                    uid.strip(),
                    group_id=source.get("groupId") if source_type == "group" else None,
                    room_id=source.get("roomId") if source_type == "room" else None,
                )

        try:
            text_out = await run_in_threadpool(
                partial(answer_for_user, normalize_user_question(q), chat_key=chat_key)
            )
            if not (text_out or "").strip():
                text_out = "（応答を生成できませんでした。もう一度お試しください。）"
            if reason in ("mention", "name_call"):
                text_out = prefix_reply_with_caller(text_out, caller_display_name)
            await _reply_line(reply_token, text_out, chat_key=chat_key)
            group_id = source.get("groupId") if source_type == "group" else None
            record_line_exchange_to_rits(
                user_text=q,
                agent_reply=text_out,
                group_id=group_id if isinstance(group_id, str) else None,
            )
        except Exception as e:
            log.exception("LINE webhook 処理エラー")
            log.error(
                "LINE webhook 例外の要約: type=%s repr=%s",
                type(e).__name__,
                repr(e)[:500],
            )
            err_reply = format_sheets_user_message_with_retry_hint(e, line_time_hint=True)
            try:
                await _reply_line(reply_token, err_reply, chat_key=chat_key)
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
                        "has_quote": bool(quote and quote.has_quote()),
                    },
                )
            except Exception:
                log.exception("監査ログ（Supabase）の記録に失敗しました（返信は済み）")

    return {}


@router.post("/webhook")
async def line_webhook(request: Request) -> dict[str, str]:
    return await handle_line_webhook(request)

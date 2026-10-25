from __future__ import annotations

import logging
from typing import Literal

from fastapi import APIRouter, Body, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator

from app.core.observability import safe_exception
from app.core.rate_limit import ApiUidRateLimitExceeded, api_uid_limiter, limiter
from app.core.security import (
    db_firestore,
    extract_id_token,
    verify_user_token,
    AuthenticationUnavailable,
    auth_unavailable_error,
)
from app.services.chat_store import (
    CHAT_PAGE_SIZE,
    CHAT_PAGE_SIZE_MAX,
    MAX_TASK_ITEMS,
    ChatCursorUnavailable,
    ChatIdempotencyConflict,
    ChatNotFound,
    ChatQuotaExceeded,
    ChatStore,
    ChatStoreError,
    InvalidChatCursor,
    TurnStatusConflict,
    normalize_task_checks,
    normalize_title,
)


router = APIRouter()

# Every endpoint below is deliberately a sync `def`, so FastAPI runs it in the
# threadpool. The Firestore client is blocking; declaring these `async def`
# would execute those blocking reads and transactions directly ON the event
# loop and stall every concurrent request for their whole duration.
#
# Since 2026-10-25 the browser runs no Consensus chat: the routes that created
# Consensus turns and built their follow-up memory are gone. The Agent writes
# its turns through /agent; a saved Consensus chat is read from its bookmark.


class ChatCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = None
    execution_mode: Literal["consensus", "agent"] = "consensus"

    @field_validator("title")
    @classmethod
    def validate_title(cls, value):
        if value is None:
            return None
        return normalize_title(value) or None


class TaskChecksRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Positions of the ticked checklist boxes in the turn's answer.
    checked: list[StrictInt] = Field(max_length=MAX_TASK_ITEMS)

    @field_validator("checked")
    @classmethod
    def validate_checked(cls, value):
        return normalize_task_checks(value)


# Schreibende Chat-Operationen zusaetzlich pro KONTO begrenzen. Der
# slowapi-Limiter am Endpoint zaehlt pro IP; das ist hier die falsche Achse:
# ueber IPv6 (ein /64 liefert praktisch beliebig viele Adressen) laesst sich ein
# IP-Limit umgehen, waehrend sich hinter einem Firmen-NAT fremde Nutzer
# gegenseitig aussperren. Chat- und Turn-Anlage kosten keinen Usage-Slot, also
# ist das Konto die einzige Achse, die den Missbrauch wirklich deckelt.
CHAT_UID_RATE_LIMITS = {
    "create_chat": 20,
    "delete_chat": 30,
    "task_checks": 60,
}


def _chat_uid(request: Request, operation: str = "") -> str:
    token = extract_id_token(request, {})
    if not token:
        raise HTTPException(status_code=401, detail="Authentication failed")
    try:
        uid = verify_user_token(token)
    except AuthenticationUnavailable:
        raise auth_unavailable_error() from None
    except Exception as exc:
        logging.warning("chat history authentication failed")
        raise HTTPException(status_code=401, detail="Authentication failed") from exc

    limit = CHAT_UID_RATE_LIMITS.get(operation)
    if limit is not None:
        try:
            api_uid_limiter.check(uid, f"chat:{operation}", limit)
        except ApiUidRateLimitExceeded as exc:
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "Too many chat requests. Please slow down.",
                    "error_code": "chat_rate_limited",
                },
                headers=exc.headers,
            ) from exc
    return uid


def _store() -> ChatStore:
    return ChatStore(db_firestore)


def _raise_store_error(exc: Exception, *, operation: str, uid: str) -> None:
    if isinstance(exc, ChatNotFound):
        raise HTTPException(status_code=404, detail="Chat not found") from exc
    if isinstance(exc, ChatQuotaExceeded):
        # Kein 500: das Limit ist erreicht, nicht kaputt. Der error_code sagt
        # dem Frontend, ob eine alte Unterhaltung geloescht oder eine neue
        # begonnen werden muss.
        raise HTTPException(
            status_code=403,
            detail={"error": str(exc), "error_code": exc.error_code},
        ) from exc
    if isinstance(exc, InvalidChatCursor):
        raise HTTPException(status_code=400, detail="Invalid or expired chat cursor") from exc
    if isinstance(exc, ChatCursorUnavailable):
        logging.error("%s failed: chat cursor signing is not configured", operation)
        raise HTTPException(status_code=503, detail="Chat pagination unavailable") from exc
    if isinstance(exc, ChatIdempotencyConflict):
        raise HTTPException(status_code=409, detail="Idempotency conflict") from exc
    if isinstance(exc, TurnStatusConflict):
        raise HTTPException(status_code=409, detail="Turn state conflict") from exc
    if isinstance(exc, ChatStoreError):
        logging.error(
            "%s failed category=%s", operation, safe_exception(exc)
        )
        raise HTTPException(status_code=500, detail="Chat storage error") from exc
    logging.error("%s failed category=%s", operation, safe_exception(exc))
    raise HTTPException(status_code=500, detail="Chat storage error") from exc


@router.post("/chats", status_code=201)
@limiter.limit("20/minute")
def create_chat(
    request: Request,
    payload: ChatCreateRequest | None = Body(default=None),
):
    uid = _chat_uid(request, "create_chat")
    execution_mode = payload.execution_mode if payload else "consensus"
    if execution_mode == "agent":
        from app.api.routers.agent import require_agent_access
        require_agent_access(uid)
    try:
        chat = _store().create_chat(uid, title=(payload.title if payload else "") or "", execution_mode=execution_mode)
        return {"status": "success", "chat": chat}
    except Exception as exc:
        _raise_store_error(exc, operation="create chat", uid=uid)


@router.get("/chats")
@limiter.limit("30/minute")
def list_chats(
    request: Request,
    cursor: str = Query(default="", max_length=512),
    limit: int = Query(default=CHAT_PAGE_SIZE, ge=1, le=CHAT_PAGE_SIZE_MAX),
):
    uid = _chat_uid(request)
    try:
        result = _store().list_chats(uid, cursor=cursor, limit=limit)
        return {"status": "success", **result}
    except Exception as exc:
        _raise_store_error(exc, operation="list chats", uid=uid)


@router.get("/chats/{chat_id}")
@limiter.limit("60/minute")
def get_chat(request: Request, chat_id: str):
    uid = _chat_uid(request)
    try:
        return {"status": "success", "chat": _store().get_chat(uid, chat_id)}
    except Exception as exc:
        _raise_store_error(exc, operation="get chat", uid=uid)


@router.delete("/chats/{chat_id}")
@limiter.limit("20/minute")
def delete_chat(request: Request, chat_id: str):
    """Delete one owner-bound chat and everything nested beneath it.

    Without this the only handle on a chat is its bookmark, so deleting the
    bookmark stranded the whole transcript with no way to ever reach or remove
    it. Repeating the call on an already deleted chat returns 404, matching
    every other unknown or foreign chat id.
    """
    uid = _chat_uid(request, "delete_chat")
    try:
        _store().delete_chat(uid, chat_id)
        return {"status": "success"}
    except Exception as exc:
        _raise_store_error(exc, operation="delete chat", uid=uid)


@router.put("/chats/{chat_id}/turns/{turn_id}/task-checks")
@limiter.limit("60/minute")
def set_task_checks(
    request: Request,
    chat_id: str,
    turn_id: str,
    payload: TaskChecksRequest,
):
    """Which checklist boxes of the turn's answer are ticked (task-checks.js)."""
    uid = _chat_uid(request, "task_checks")
    try:
        checked = _store().set_task_checks(uid, chat_id, turn_id, payload.checked)
        return {"status": "success", "checked": checked}
    except Exception as exc:
        _raise_store_error(exc, operation="set task checks", uid=uid)

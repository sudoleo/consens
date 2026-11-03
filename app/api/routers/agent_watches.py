"""Watches that run the Agent (agent_watches.py, since 2026-11-03).

POST /agent/watches starts a Watch: the one the agent prepared under an
answer (``turn_id``: task and goal from that saved turn), the user's own task
in a chat (``chat_id`` + ``task``, the Watch pill's sheet) or in a chat of its
own (``task`` alone, "New Watch" on the Watches page). GET lists the
account's Watches (one chat's with ``chat_id``); the others act on one:
stop, pause, resume, seen (its finding was looked at) and PATCH (its
channels). /agent-watch/unsubscribe is the mail's "Stop emails" link: GET
asks, POST acts (also the mail clients' one-click POST).
"""
from __future__ import annotations

import logging
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import Field

from app.api.routers.agent import require_agent_access
from app.api.routers.chat_history import _chat_uid
from app.core.notice_page import WATCHES_LINK, notice_page
from app.core.observability import safe_exception
from app.core.rate_limit import limiter
from app.core.security import db_firestore, get_user_tier
from app.services import agent_watches
from app.services.agent_documents import Strict

router = APIRouter()

_NO_STORE = {"Cache-Control": "private, no-store"}
_UNAVAILABLE = "Watches are unavailable right now. Try again."


class StartWatch(Strict):
    chat_id: str = Field(default="", pattern=r"^(?:[0-9a-f]{32})?$")
    turn_id: str = Field(default="", pattern=r"^[A-Za-z0-9_-]{0,128}$")
    task: str | None = Field(default=None, max_length=agent_watches.TASK_MAX_CHARS + 200)
    goal: str | None = Field(default=None, max_length=agent_watches.GOAL_MAX_CHARS + 100)
    interval: str | None = Field(default=None, max_length=20)
    run_time: str | None = Field(default=None, max_length=5)
    run_weekday: str | None = Field(default=None, max_length=10)
    timezone: str = Field(default="", max_length=64)


class Channels(Strict):
    email_enabled: bool | None = None
    telegram_enabled: bool | None = None


def _refusal(exc: agent_watches.AgentWatchError) -> JSONResponse:
    return JSONResponse({"error": str(exc), "code": exc.code}, status_code=exc.status, headers=_NO_STORE)


def _act(action):
    """``action()``'s Watch as ``{watch}``, a refusal as ``{error, code}``."""
    try:
        watch = action()
    except agent_watches.AgentWatchError as exc:
        return _refusal(exc)
    except Exception as exc:
        logging.warning("Agent watch action failed category=%s", safe_exception(exc))
        raise HTTPException(status_code=503, detail=_UNAVAILABLE) from None
    return JSONResponse({"watch": watch}, headers=_NO_STORE)


def _watch_id(value: str) -> str:
    if not value.isalnum() or len(value) > 64:
        raise HTTPException(status_code=404, detail="This Watch no longer exists.")
    return value


@router.post("/agent/watches")
@limiter.limit("20/minute")
def start_watch(request: Request, payload: StartWatch):
    uid = _chat_uid(request)
    require_agent_access(uid)
    try:
        watch = agent_watches.create(
            uid, chat_id=payload.chat_id, turn_id=payload.turn_id, task=payload.task, goal=payload.goal,
            tier=get_user_tier(uid), timezone_name=payload.timezone, interval=payload.interval,
            run_time=payload.run_time, weekday=payload.run_weekday, db=db_firestore)
    except agent_watches.AgentWatchError as exc:
        return _refusal(exc)
    except Exception as exc:
        logging.warning("Agent watch start failed category=%s", safe_exception(exc))
        raise HTTPException(status_code=503, detail=_UNAVAILABLE) from None
    return JSONResponse({"watch": watch}, status_code=201, headers=_NO_STORE)


@router.get("/agent/watches")
@limiter.limit("60/minute")
def list_watches(request: Request, chat_id: str = Query("", pattern=r"^(?:[0-9a-f]{32})?$")):
    uid = _chat_uid(request)
    require_agent_access(uid)
    try:
        watches = agent_watches.list_for(uid, db=db_firestore)
        tier = get_user_tier(uid)
    except Exception as exc:
        logging.warning("Agent watch list failed category=%s", safe_exception(exc))
        raise HTTPException(status_code=503, detail=_UNAVAILABLE) from None
    active = sum(1 for watch in watches if watch["status"] == "active")
    if chat_id:
        watches = [watch for watch in watches if watch["chat_id"] == chat_id]
    return JSONResponse({"watches": watches, "active_count": active,
                         "active_limit": agent_watches.active_limit(tier),
                         "intervals": agent_watches.allowed_intervals(tier)}, headers=_NO_STORE)


@router.post("/agent/watches/{watch_id}/stop")
@limiter.limit("20/minute")
def stop_watch(request: Request, watch_id: str):
    uid = _chat_uid(request)
    require_agent_access(uid)
    watch_id = _watch_id(watch_id)
    return _act(lambda: agent_watches.stop(uid, watch_id, db=db_firestore))


@router.post("/agent/watches/{watch_id}/pause")
@limiter.limit("20/minute")
def pause_watch(request: Request, watch_id: str):
    uid = _chat_uid(request)
    require_agent_access(uid)
    watch_id = _watch_id(watch_id)
    return _act(lambda: agent_watches.pause(uid, watch_id, db=db_firestore))


@router.post("/agent/watches/{watch_id}/resume")
@limiter.limit("20/minute")
def resume_watch(request: Request, watch_id: str):
    uid = _chat_uid(request)
    require_agent_access(uid)
    watch_id = _watch_id(watch_id)
    return _act(lambda: agent_watches.resume(uid, watch_id, tier=get_user_tier(uid), db=db_firestore))


@router.post("/agent/watches/{watch_id}/seen")
@limiter.limit("60/minute")
def watch_seen(request: Request, watch_id: str):
    uid = _chat_uid(request)
    require_agent_access(uid)
    watch_id = _watch_id(watch_id)
    return _act(lambda: agent_watches.seen(uid, watch_id, db=db_firestore))


@router.patch("/agent/watches/{watch_id}")
@limiter.limit("30/minute")
def watch_channels(request: Request, watch_id: str, payload: Channels):
    uid = _chat_uid(request)
    require_agent_access(uid)
    watch_id = _watch_id(watch_id)
    return _act(lambda: agent_watches.set_channels(
        uid, watch_id, email=payload.email_enabled, telegram=payload.telegram_enabled, db=db_firestore))


# --- the mail's "Stop emails" link -------------------------------------------

_EYEBROW = "Watch"


def _link_problem(request: Request):
    return notice_page(request, status_code=400, eyebrow=_EYEBROW, heading="This link no longer works",
                       message="It may have expired. Switch the emails off on the Watches page.",
                       links=[WATCHES_LINK])


def _gone(request: Request):
    return notice_page(request, status_code=404, eyebrow=_EYEBROW, heading="This Watch no longer exists",
                       message="It was deleted with its chat. Nothing more is sent.", links=[WATCHES_LINK])


@router.get("/agent-watch/unsubscribe", response_class=HTMLResponse)
@limiter.limit("20/minute")
def unsubscribe_page(request: Request, token: str = ""):
    try:
        watch = agent_watches.watch_of(agent_watches.parse_unsubscribe_token(token), db=db_firestore)
    except agent_watches.AgentWatchError:
        return _link_problem(request)
    if watch is None:
        return _gone(request)
    if not watch["email_enabled"]:
        return notice_page(request, eyebrow=_EYEBROW, heading="Emails are off for this Watch",
                           message="It keeps running. Its findings appear in its chat.",
                           subject_label="Watch", subject=watch["task"], links=[WATCHES_LINK])
    return notice_page(request, eyebrow=_EYEBROW, heading="Stop emails from this Watch?",
                       message="It keeps running and its findings appear in its chat. "
                               "You can switch emails on again on the Watches page.",
                       subject_label="Watch", subject=watch["task"],
                       action=f"/agent-watch/unsubscribe?token={quote(token, safe='')}",
                       button="Stop emails", links=[WATCHES_LINK])


@router.post("/agent-watch/unsubscribe", response_class=HTMLResponse)
@limiter.limit("20/minute")
def unsubscribe(request: Request, token: str = ""):
    try:
        watch = agent_watches.stop_emails(agent_watches.parse_unsubscribe_token(token), db=db_firestore)
    except agent_watches.AgentWatchError:
        return _link_problem(request)
    if watch is None:
        return _gone(request)
    return notice_page(request, eyebrow=_EYEBROW, heading="Emails stopped",
                       message="This Watch keeps running. Its findings appear in its chat.",
                       subject_label="Watch", subject=watch["task"], links=[WATCHES_LINK])

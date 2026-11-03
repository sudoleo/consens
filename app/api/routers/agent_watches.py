"""Watches that run the Agent (agent_watches.py, since 2026-11-03).

POST /agent/watches starts the Watch the agent prepared under an answer
(its card, static/js/agent-watch.js): the task and the goal come from that
saved turn, the schedule and the timezone from the card. GET lists the
account's Watches (one chat's with ``chat_id``); POST .../stop ends one.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pydantic import Field

from app.api.routers.agent import require_agent_access
from app.api.routers.chat_history import _chat_uid
from app.core.observability import safe_exception
from app.core.rate_limit import limiter
from app.core.security import db_firestore, get_user_tier
from app.services import agent_watches
from app.services.agent_documents import Strict

router = APIRouter()

_NO_STORE = {"Cache-Control": "private, no-store"}


class StartWatch(Strict):
    chat_id: str = Field(pattern=r"^[0-9a-f]{32}$")
    turn_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,128}$")
    interval: str | None = Field(default=None, max_length=20)
    run_time: str | None = Field(default=None, max_length=5)
    run_weekday: str | None = Field(default=None, max_length=10)
    timezone: str = Field(default="", max_length=64)


def _refusal(exc: agent_watches.AgentWatchError) -> JSONResponse:
    return JSONResponse({"error": str(exc), "code": exc.code}, status_code=exc.status, headers=_NO_STORE)


@router.post("/agent/watches")
@limiter.limit("20/minute")
def start_watch(request: Request, payload: StartWatch):
    uid = _chat_uid(request)
    require_agent_access(uid)
    try:
        watch = agent_watches.create(
            uid, chat_id=payload.chat_id, turn_id=payload.turn_id, tier=get_user_tier(uid),
            timezone_name=payload.timezone, interval=payload.interval, run_time=payload.run_time,
            weekday=payload.run_weekday, db=db_firestore)
    except agent_watches.AgentWatchError as exc:
        return _refusal(exc)
    except Exception as exc:
        logging.warning("Agent watch start failed category=%s", safe_exception(exc))
        raise HTTPException(status_code=503, detail="Watches are unavailable right now. Try again.") from None
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
        raise HTTPException(status_code=503, detail="Watches are unavailable right now. Try again.") from None
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
    if not watch_id.isalnum() or len(watch_id) > 64:
        raise HTTPException(status_code=404, detail="This Watch no longer exists.")
    try:
        watch = agent_watches.stop(uid, watch_id, db=db_firestore)
    except agent_watches.AgentWatchError as exc:
        return _refusal(exc)
    except Exception as exc:
        logging.warning("Agent watch stop failed category=%s", safe_exception(exc))
        raise HTTPException(status_code=503, detail="Watches are unavailable right now. Try again.") from None
    return JSONResponse({"watch": watch}, headers=_NO_STORE)

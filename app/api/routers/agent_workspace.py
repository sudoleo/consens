"""The account's workspace from the browser (agent_workspace.py,
workspace-view.js, docs/agent-mode.md "Arbeitsplatz"): the live view of its
Chrome, the user's takeover and resetting the browser.

The view is a WebSocket the server carries through to the VM's gateway
(workspace_vm/gateway.py) over the VM's private address, which only the
provider's token opens; the token never leaves the server. The browser
signs in with its first message ({"id_token"}), never in the URL. After the
gateway's text states (setup, starting, ready) both ways carry VNC bytes. A
view ends after VIEW_SECONDS: an open view keeps the VM awake.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time

from fastapi import APIRouter, HTTPException, Request, WebSocket
from fastapi.responses import JSONResponse
from pydantic import Field

from app.api.routers.agent import require_agent_access, vm_allowed
from app.api.routers.chat_history import _chat_uid
from app.core.observability import safe_exception
from app.core.rate_limit import limiter
from app.core.security import db_firestore, verify_user_token
from app.services import agent_vm, agent_workspace
from app.services.agent_documents import Strict

router = APIRouter()
VIEW_SECONDS = 60 * 60
SIGN_IN_SECONDS = 15
UPSTREAM_OPEN_SECONDS = 30
NO_STORE = {"Cache-Control": "private, no-store"}


class Control(Strict):
    holder: str = Field(pattern=r"^(user|agent)$")


def allowed(uid):
    """The workspace comes with the VM (routers/agent.py vm_allowed) and a
    provider."""
    return vm_allowed(uid) and agent_vm.configured()


def owner(request):
    uid = _chat_uid(request)
    require_agent_access(uid)
    if not allowed(uid):
        raise HTTPException(status_code=403, detail="The workspace is not available on your account.")
    return uid


def _store():
    from app.services.agent_runs import AgentRunStore
    return AgentRunStore(db_firestore)


def _backend():
    vm = agent_vm.backend()
    if vm is None:
        raise agent_vm.VMUnavailable("no provider configured")
    return vm


@router.get("/agent/workspace")
@limiter.limit("60/minute")
def workspace_status(request: Request):
    """Whether this account has the workspace, and whether a chat's message
    uses it right now (the view says so; the user may still look)."""
    uid = _chat_uid(request)
    require_agent_access(uid)
    if not allowed(uid):
        return JSONResponse({"available": False}, headers=NO_STORE)
    return JSONResponse({"available": True, "in_use": bool(agent_workspace.held_by(db_firestore, uid))},
                        headers=NO_STORE)


@router.post("/agent/workspace/control")
@limiter.limit("30/minute")
def workspace_control(request: Request, payload: Control):
    """The user takes the browser over (refreshed by the open view every
    CONTROL_REFRESH_SECONDS, else it expires) or hands it back. Meanwhile
    the agent pauses completely (agent_workspace.set_control)."""
    from app.services.llm.provider_runtime import ProviderCancellation
    uid = owner(request)
    if not agent_workspace.record(db_firestore, uid).get("name"):
        raise HTTPException(status_code=404, detail="Open the workspace first.")
    try:
        vm = _backend()
        try:
            agent_workspace.set_control(db_firestore, uid, vm, agent_vm.workspace_name(uid), payload.holder,
                                        ProviderCancellation())
        finally:
            vm.close()
    except agent_vm.VMUnavailable as exc:
        logging.warning("Agent workspace control unavailable category=%s", safe_exception(exc))
        raise HTTPException(status_code=503, detail="The workspace is not reachable right now. Try again.") from None
    return JSONResponse({"holder": payload.holder, "seconds": agent_workspace.CONTROL_SECONDS}, headers=NO_STORE)


@router.post("/agent/workspace/reset-browser")
@limiter.limit("5/minute")
def reset_workspace_browser(request: Request):
    """Signs the workspace's browser out of everything: its profile goes,
    never while a chat's message uses the workspace."""
    from app.services.llm.provider_runtime import ProviderCancellation
    uid = owner(request)
    if not agent_workspace.record(db_firestore, uid).get("name"):
        return JSONResponse({"status": "reset"}, headers=NO_STORE)
    if agent_workspace.held_by(db_firestore, uid):
        return JSONResponse({"error": "The agent is working in the workspace. Try again when its response is done.",
                             "code": "running"}, status_code=409)
    try:
        vm = _backend()
        try:
            agent_workspace.reset_browser(vm, agent_vm.workspace_name(uid), ProviderCancellation())
        finally:
            vm.close()
    except agent_vm.VMUnavailable as exc:
        logging.warning("Agent workspace reset unavailable category=%s", safe_exception(exc))
        return JSONResponse({"error": "The workspace is not reachable right now. Try again.",
                             "code": "vm_unavailable"}, status_code=503)
    return JSONResponse({"status": "reset"}, headers=NO_STORE)


def _sign_in(token):
    """The account behind the view's first message, or None."""
    if not isinstance(token, str) or not token.strip():
        return None
    try:
        uid = verify_user_token(token)
        require_agent_access(uid)
    except Exception:
        return None
    return uid if allowed(uid) else None


def _open(uid):
    """The workspace for the view (created if no chat used it yet, its tools
    up to date): its private address."""
    agent_workspace.record_for_view(_store(), uid, provider="sprites")
    vm = _backend()
    try:
        name = agent_vm.workspace_name(uid)
        vm.ensure(name)
        agent_workspace.prepare(vm, name)
        return vm.url(name)
    finally:
        vm.close()


async def connect_upstream(url):
    """The VM gateway's WebSocket with the provider's token (tests replace it)."""
    from websockets.asyncio.client import connect
    return await connect(url, additional_headers={"Authorization": f"Bearer {os.getenv('SPRITES_TOKEN', '').strip()}"},
                         open_timeout=UPSTREAM_OPEN_SECONDS, max_size=8 * 1024 * 1024, ping_interval=20,
                         ping_timeout=40, close_timeout=2)


async def _state(websocket, state):
    await websocket.send_text(json.dumps({"state": state}))


@router.websocket("/agent/workspace/view")
async def workspace_view(websocket: WebSocket):
    await websocket.accept()
    try:
        first = await asyncio.wait_for(websocket.receive_text(), SIGN_IN_SECONDS)
        token = (json.loads(first) or {}).get("id_token") if first.startswith("{") else None
    except Exception:
        token = None
    uid = await asyncio.to_thread(_sign_in, token)
    if uid is None:
        await websocket.close(code=4403)
        return
    await _state(websocket, "connecting")
    started = time.monotonic()
    try:
        url = await asyncio.to_thread(_open, uid)
        upstream = await connect_upstream("wss://" + url.split("://", 1)[1].rstrip("/") + "/vnc")
    except Exception as exc:
        logging.warning("Agent workspace view unavailable category=%s", safe_exception(exc))
        await _state(websocket, "error")
        await websocket.close(code=1011)
        return

    async def to_vm():
        while True:
            message = await websocket.receive()
            if message["type"] == "websocket.disconnect":
                return
            if message.get("bytes") is not None:
                await upstream.send(message["bytes"])

    async def to_browser():
        async for message in upstream:
            if isinstance(message, bytes):
                await websocket.send_bytes(message)
            else:
                await websocket.send_text(message)

    tasks = [asyncio.ensure_future(to_vm()), asyncio.ensure_future(to_browser())]
    done, _ = await asyncio.wait(tasks, timeout=VIEW_SECONDS, return_when=asyncio.FIRST_COMPLETED)
    for task in tasks:
        task.cancel()
    try:
        await upstream.close()
    except Exception:
        pass
    try:
        if not done:
            await _state(websocket, "ended")
        await websocket.close()
    except Exception:
        pass
    # Open views keep the VM awake: their length, to watch what they cost.
    logging.info("Agent workspace view closed seconds=%d", int(time.monotonic() - started))

"""The account's workspace from the browser (agent_workspace.py,
workspace-view.js, docs/agent-mode.md "Arbeitsplatz"): the live view of its
Chrome, the user's takeover and resetting the browser.

The view is a WebSocket the server carries through to the browser VM
(agent_vm.browser_name): since the security audit of 2026-10-27 over a
command on the provider's exec API, workspace_vm/browser/relay.py, whose
stdin and stdout carry the VNC bytes. The provider's token goes only to
api.sprites.dev, never to an address of the VM (before, it went to the VM's
own address, where a service answered that the agent could change). The
browser signs in with its first message ({"id_token"}), never in the URL.
The relay's states (setup, starting, ready, error) come as JSON lines on its
stderr and go on as text; after "ready" both ways carry VNC bytes. A view
ends after VIEW_SECONDS: an open view keeps the VM awake. An account has one
view at a time (the newest wins, agent_workspace.claim_view), its time
counts against the day's VM time (agent_vm_time.py) and never runs past it,
and opening is rate limited.

The terminal (since 2026-10-28) is the user's own shell on the workbench,
the same way: a WebSocket carried to an exec with a TTY on the provider's
API (agent_vm.terminal_argv), with the agent's rights and nothing more, one
per account, its time VM time. The first message also names the terminal's
size ({"id_token", "cols", "rows"}); then the browser's binary frames are
keystrokes and {"type": "resize", "cols", "rows"} resizes it; the server's
binary frames are the terminal's output. The reviewers never see it: it is
the user's work, not the agent's.
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
from app.core.rate_limit import ApiUidRateLimitExceeded, api_uid_limiter, limiter
from app.core.security import db_firestore, verify_user_token
from app.services import agent_tunnel, agent_vm, agent_vm_time, agent_workspace
from app.services.agent_documents import Strict

router = APIRouter()
VIEW_SECONDS = 60 * 60
# Views an account may open per minute (a reload or a second window, not a loop).
VIEWS_PER_MINUTE = 6
SIGN_IN_SECONDS = 15
UPSTREAM_OPEN_SECONDS = 30
# The relay's own limit lies this far past the view's.
RELAY_GRACE_SECONDS = 60
# The relay's first bytes on stderr: its states, one JSON line each.
STATE_LINE_BYTES = 4096
# The terminal's size, as xterm.js reports it (workspace-view.js), within reason.
TERMINAL_COLS, TERMINAL_ROWS = (2, 500), (2, 200)
RESIZE_BYTES = 200
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
    the agent waits (agent_workspace.set_control). While the user has the
    browser, the localhost tunnel neither ends as idle nor stays ended: they
    may be trying the agent's app (agent_tunnel.py)."""
    uid = owner(request)
    record = agent_workspace.record(db_firestore, uid)
    if not record.get("name"):
        raise HTTPException(status_code=404, detail="Open the workspace first.")
    if payload.holder == "user":
        agent_tunnel.seed(uid, agent_workspace.listed(record, "tunnel_ports", int))
        agent_tunnel.touch(uid)
        agent_tunnel.resume(uid, backend_factory=_backend, db=db_firestore)
    try:
        vm = _backend()
        try:
            agent_workspace.set_control(db_firestore, uid, vm, payload.holder)
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
    # No checkpoint from before brings the sign-ins back (restorable): set
    # first, so a failure here leaves the browser as it is.
    agent_workspace.raise_restore_floor(_store(), uid)
    try:
        vm = _backend()
        try:
            agent_workspace.reset_browser(vm, uid, ProviderCancellation())
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


def _open(uid, seconds):
    """The browser VM for the view (created if nothing used it yet, its
    tools up to date): the exec address of its relay on the provider's API,
    for at most ``seconds`` (the VM ends the relay by itself then)."""
    store = _store()
    record = agent_workspace.record_for_view(store, uid, provider="sprites")
    vm = _backend()
    try:
        name = agent_workspace.open_browser(vm, uid)
        # The agent's app on localhost goes on working in the view after
        # its run and a restart of the server, with the servers it started
        # since (agent_tunnel.py).
        agent_tunnel.seed(uid, agent_workspace.listed(record, "tunnel_ports", int))
        agent_tunnel.resume(uid, backend_factory=_backend, db=store.db, find=True)
        argv = agent_vm.wrapped_command(f"exec python3 {agent_workspace.BROWSER_RELAY}", seconds + RELAY_GRACE_SECONDS,
                                        False)
        return vm.exec_url(name, argv, cwd=agent_vm.SERVER_HOME, stdin=True)
    finally:
        vm.close()


def _open_terminal(uid, seconds, size):
    """The workbench for the terminal (created if nothing used it yet, its
    tools up to date): the exec address of a login shell with a TTY of
    ``size`` (cols, rows) as the agent's user, for at most ``seconds``."""
    agent_workspace.record_for_view(_store(), uid, provider="sprites")
    vm = _backend()
    try:
        name = agent_workspace.open_workbench(vm, uid)
        return vm.exec_url(name, agent_vm.terminal_argv(seconds + RELAY_GRACE_SECONDS), cwd=agent_vm.SERVER_HOME,
                           stdin=True, tty=size)
    finally:
        vm.close()


def _size(cols, rows):
    """The terminal's (cols, rows) from the browser, or None when either is no whole number in range."""
    if type(cols) is not int or type(rows) is not int:
        return None
    if not (TERMINAL_COLS[0] <= cols <= TERMINAL_COLS[1] and TERMINAL_ROWS[0] <= rows <= TERMINAL_ROWS[1]):
        return None
    return cols, rows


async def connect_upstream(url):
    """The relay's exec WebSocket with the provider's token, which goes
    to the provider's API only (tests replace it)."""
    from websockets.asyncio.client import connect
    if not url.startswith("wss://" + agent_vm.SPRITES_API.split("://", 1)[1] + "/"):
        raise ValueError("The view connects to the provider's API only.")
    return await connect(url, additional_headers={"Authorization": f"Bearer {os.getenv('SPRITES_TOKEN', '').strip()}"},
                         open_timeout=UPSTREAM_OPEN_SECONDS, max_size=8 * 1024 * 1024, ping_interval=20,
                         ping_timeout=40, close_timeout=2)


async def _state(websocket, state):
    await websocket.send_text(json.dumps({"state": state}))


def _view_seconds(uid):
    """How long this view may stay open: VIEW_SECONDS, at most what is left
    of today's VM time (agent_vm_time.py); a failed read leaves the hour."""
    try:
        limit = agent_vm_time.daily_limit(uid)
        if limit is None:
            return VIEW_SECONDS
        return min(VIEW_SECONDS, int(limit - agent_vm_time.used(db_firestore, uid)))
    except Exception as exc:
        logging.warning("Agent workspace view time unavailable category=%s", safe_exception(exc))
        return VIEW_SECONDS


def _charge(uid, seconds):
    agent_vm_time.charge(_store(), uid, seconds)


# Why the server closed a view (workspace-view.js CLOSED): once noVNC has the
# socket, text states would reach it as VNC bytes, so the reason is the code.
CLOSE_ENDED, CLOSE_REPLACED, CLOSE_NO_TIME, CLOSE_TOO_MANY = 4410, 4409, 4402, 4429


async def _end(websocket, code):
    try:
        await websocket.close(code=code)
    except Exception:
        pass


async def _admit(websocket, kind):
    """A view's or terminal's start: the account behind its first message
    (signed in, allowed the VM), the rate limit and what is left of today's
    VM time. ``(uid, seconds, first message)``, or None once it is closed."""
    await websocket.accept()
    try:
        first = await asyncio.wait_for(websocket.receive_text(), SIGN_IN_SECONDS)
        hello = json.loads(first) if first.startswith("{") else {}
    except Exception:
        hello = {}
    hello = hello if isinstance(hello, dict) else {}
    uid = await asyncio.to_thread(_sign_in, hello.get("id_token"))
    if uid is None:
        await websocket.close(code=4403)
        return None
    try:
        api_uid_limiter.check(uid, f"agent:workspace_{kind}", VIEWS_PER_MINUTE)
    except ApiUidRateLimitExceeded:
        await _end(websocket, CLOSE_TOO_MANY)
        return None
    seconds = await asyncio.to_thread(_view_seconds, uid)
    if seconds < 1:
        await _end(websocket, CLOSE_NO_TIME)
        return None
    return uid, seconds, hello


async def _carry(websocket, upstream, uid, kind, view_id, seconds, started, to_vm, to_browser):
    """Carries both ways until one side ends, the time is up or a newer
    one of this kind took over; then counts the open time as VM time and
    closes with the reason (CLOSE_*)."""
    async def replaced():
        # A newer view (or terminal) of the account took over: this one ends.
        while True:
            await asyncio.sleep(agent_workspace.VIEW_CHECK_SECONDS)
            try:
                if not await asyncio.to_thread(agent_workspace.holds_view, db_firestore, uid, view_id, kind):
                    return
            except Exception as exc:
                logging.info("Agent workspace %s check failed category=%s", kind, safe_exception(exc))

    watcher = asyncio.ensure_future(replaced())
    tasks = [asyncio.ensure_future(to_vm()), asyncio.ensure_future(to_browser()), watcher]
    done, _ = await asyncio.wait(tasks, timeout=seconds, return_when=asyncio.FIRST_COMPLETED)
    for task in tasks:
        task.cancel()
    try:
        # Stdin ends (0x04, the relay's; a terminal ends with its socket).
        if kind == "view":
            await upstream.send(b"\x04")
    except Exception:
        pass
    try:
        await upstream.close()
    except Exception:
        pass
    # Open views keep the VM awake: their time counts as VM time.
    elapsed = time.monotonic() - started
    await asyncio.to_thread(_charge, uid, elapsed)
    logging.info("Agent workspace %s closed seconds=%d", kind, int(elapsed))
    # Its hour, or today's VM time, is over; or a newer one took over.
    code = (CLOSE_ENDED if seconds >= VIEW_SECONDS else CLOSE_NO_TIME) if not done \
        else CLOSE_REPLACED if watcher in done else 1000
    await _end(websocket, code)


@router.websocket("/agent/workspace/view")
async def workspace_view(websocket: WebSocket):
    admitted = await _admit(websocket, "view")
    if admitted is None:
        return
    uid, seconds, _ = admitted
    await _state(websocket, "connecting")
    started = time.monotonic()
    try:
        url = await asyncio.to_thread(_open, uid, seconds)
        view_id = await asyncio.to_thread(agent_workspace.claim_view, _store(), uid, seconds)
        upstream = await connect_upstream(url)
    except Exception as exc:
        logging.warning("Agent workspace view unavailable category=%s", safe_exception(exc))
        await _state(websocket, "error")
        await websocket.close(code=1011)
        return

    async def to_vm():
        # The view's bytes go to the relay's stdin (exec frames 0x00).
        while True:
            message = await websocket.receive()
            if message["type"] == "websocket.disconnect":
                return
            if message.get("bytes") is not None:
                await upstream.send(b"\x00" + message["bytes"])

    async def to_browser():
        # stdout (0x01) is VNC once the relay said "ready"; its states come
        # as JSON lines on stderr (0x02) before; the exit (0x03) ends it.
        pending = b""
        async for message in upstream:
            if not isinstance(message, bytes) or not message:
                continue
            stream, payload = message[0], message[1:]
            if stream == 1 and payload:
                await websocket.send_bytes(payload)
            elif stream == 2 and len(pending) < STATE_LINE_BYTES:
                pending += payload
                while b"\n" in pending:
                    line, pending = pending.split(b"\n", 1)
                    try:
                        state = (json.loads(line) or {}).get("state")
                    except ValueError:
                        continue
                    if state in {"setup", "starting", "ready", "error"}:
                        await _state(websocket, state)
            elif stream == 3:
                return

    await _carry(websocket, upstream, uid, "view", view_id, seconds, started, to_vm, to_browser)


@router.websocket("/agent/workspace/terminal")
async def workspace_terminal(websocket: WebSocket):
    admitted = await _admit(websocket, "terminal")
    if admitted is None:
        return
    uid, seconds, hello = admitted
    size = _size(hello.get("cols"), hello.get("rows")) or (80, 24)
    await _state(websocket, "connecting")
    started = time.monotonic()
    try:
        url = await asyncio.to_thread(_open_terminal, uid, seconds, size)
        terminal_id = await asyncio.to_thread(agent_workspace.claim_view, _store(), uid, seconds, "terminal")
        upstream = await connect_upstream(url)
    except Exception as exc:
        logging.warning("Agent workspace terminal unavailable category=%s", safe_exception(exc))
        await _state(websocket, "error")
        await websocket.close(code=1011)
        return
    await _state(websocket, "ready")

    async def to_vm():
        # Keystrokes go to the TTY as they are; a resize as the provider's
        # own message, rebuilt from two checked numbers.
        while True:
            message = await websocket.receive()
            if message["type"] == "websocket.disconnect":
                return
            if message.get("bytes") is not None:
                await upstream.send(message["bytes"])
            elif message.get("text") and len(message["text"]) <= RESIZE_BYTES:
                try:
                    data = json.loads(message["text"])
                except ValueError:
                    continue
                if isinstance(data, dict) and data.get("type") == "resize":
                    resized = _size(data.get("cols"), data.get("rows"))
                    if resized:
                        await upstream.send(json.dumps({"type": "resize", "cols": resized[0], "rows": resized[1]}))

    async def to_browser():
        # A TTY's output comes as raw binary frames; the shell's end as
        # {"type": "exit"} (or the socket's close) ends the terminal.
        async for message in upstream:
            if isinstance(message, bytes):
                if message:
                    await websocket.send_bytes(message)
                continue
            try:
                data = json.loads(message)
            except ValueError:
                continue
            if isinstance(data, dict) and data.get("type") == "exit":
                return

    await _carry(websocket, upstream, uid, "terminal", terminal_id, seconds, started, to_vm, to_browser)

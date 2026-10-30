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
and opening is rate limited. Its first state ("connecting") names what is
left of the day's VM time (``left_seconds``, absent without a cap) for the
panel's head (since 2026-10-30, runtime audit V4).

How a view or terminal ended goes to the log with its close code, who ended
it (the browser, the relay, the provider's socket) and the numbers they gave,
never an account; the relay's "error" state and a failed carry too. Per UTC
day ``ops_metrics/workspace-view-{day}`` counts them anonymously: opened,
refused or failed by reason, how they ended, their open seconds and a bucket
of their length (runtime audit I8; written off the event loop, never raised).

The terminal (since 2026-10-28) is the user's own shell on the workbench,
the same way: a WebSocket carried to an exec with a TTY on the provider's
API (agent_vm.terminal_argv), with the agent's rights and nothing more, one
per account, its time VM time. The first message also names the terminal's
size ({"id_token", "cols", "rows"}); then the browser's binary frames are
keystrokes and {"type": "resize", "cols", "rows"} resizes it; the server's
binary frames are the terminal's output. The reviewers never see it: it is
the user's work, not the agent's.

The server's safety rules (workspace_guard.py, since 2026-10-30) see both:
the relay's stderr also names the host of every page a tab shows
({"visit"}), the VM's network counters ({"net"}) and its Chrome policy
({"policy"}), each page with who steered then (_steering: the user from
their takeover on, else the agent they watch); the view's bytes count, the
terminal's do not; a workspace the rules closed refuses a new view,
terminal or takeover (CLOSE_GUARDED, CLOSE_LOCKED) and ends an open one
within workspace_guard.CHECK_SECONDS.
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
from app.services import agent_tunnel, agent_vm, agent_vm_time, agent_workspace, workspace_guard
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
    body = {"available": True, "in_use": bool(agent_workspace.held_by(db_firestore, uid))}
    guard = workspace_guard.status(uid)
    if guard.closed:
        # Closed by the server's safety rules: until when (None: until consens.io looked at it).
        body["guard"] = {"state": guard.state, "until": guard.until.isoformat() if guard.until else None}
    return JSONResponse(body, headers=NO_STORE)


@router.post("/agent/workspace/control")
@limiter.limit("30/minute")
def workspace_control(request: Request, payload: Control):
    """The user takes the browser over (refreshed by the open view every
    CONTROL_REFRESH_SECONDS, else it expires) or hands it back. Meanwhile
    the agent waits (agent_workspace.set_control). While the user has the
    browser, the localhost tunnel neither ends as idle nor stays ended: they
    may be trying the agent's app (agent_tunnel.py)."""
    uid = owner(request)
    guard = workspace_guard.status(uid)
    if payload.holder == "user" and guard.closed:
        raise HTTPException(status_code=403, detail=workspace_guard.user_text(guard))
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
    _note_takeover(uid, payload.holder)
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


async def _state(websocket, state, **fields):
    await websocket.send_text(json.dumps({"state": state, **fields}))


def _time_left(uid):
    """``(seconds, day_left)``: how long this view may stay open, VIEW_SECONDS
    at most what is left of today's VM time (agent_vm_time.py), and what is
    left of the day (None without a cap). A failed read leaves the hour and
    says nothing about the day."""
    try:
        limit = agent_vm_time.daily_limit(uid)
        if limit is None:
            return VIEW_SECONDS, None
        left = int(limit - agent_vm_time.used(db_firestore, uid))
        return min(VIEW_SECONDS, left), max(0, left)
    except Exception as exc:
        logging.warning("Agent workspace view time unavailable category=%s", safe_exception(exc))
        return VIEW_SECONDS, None


# Anonymous daily counters of views and terminals (I8), beside the audit's
# (agent_audit_metrics.py): one document per UTC day, labels and numbers only.
METRICS_COLLECTION = "ops_metrics"
# Upper bounds of a view's open time in seconds; the last bucket is "over3600".
OPEN_BOUNDS = (10, 30, 120, 600, 1800, 3600)


def _metrics_on():
    # Test and mock profiles share the real Firestore locally: no counters.
    return not any(os.getenv(key) == "1" for key in ("UNIT_TEST_MODE", "E2E_TEST_MODE", "MOCK_LLM"))


def _open_bucket(seconds):
    for bound in OPEN_BOUNDS:
        if seconds <= bound:
            return f"le{bound}"
    return f"over{OPEN_BOUNDS[-1]}"


def _count(kind, outcome, seconds=None):
    """Adds one ``outcome`` of a view or terminal to today's counters (and its
    open seconds with their bucket): one merge of Firestore increments. Never
    an account, a chat or any text; failures are logged, never raised."""
    if not _metrics_on():
        return
    try:
        from google.cloud import firestore
        day = agent_vm_time.day_key()
        counts = {outcome: firestore.Increment(1)}
        if seconds is not None:
            counts["seconds"] = firestore.Increment(int(seconds))
            counts["open_" + _open_bucket(seconds)] = firestore.Increment(1)
        db_firestore.collection(METRICS_COLLECTION).document(f"workspace-view-{day}").set(
            {kind: counts, "day": day, "updated_at": firestore.SERVER_TIMESTAMP}, merge=True)
    except Exception as exc:
        logging.warning("Agent workspace %s metrics not saved category=%s", kind, safe_exception(exc))


def _charge(uid, seconds):
    agent_vm_time.charge(_store(), uid, seconds)


# Why the server closed a view (workspace-view.js CLOSED, FINAL): once noVNC
# has the socket, text states would reach it as VNC bytes, so the reason is
# the code. The view tries again by itself only after a close without one.
CLOSE_ENDED, CLOSE_REPLACED, CLOSE_NO_TIME, CLOSE_TOO_MANY = 4410, 4409, 4402, 4429
CLOSE_FORBIDDEN = 4403
# The server's safety rules closed the workspace: until the next UTC day, or until consens.io looked at it.
CLOSE_GUARDED, CLOSE_LOCKED = 4423, 4424
CLOSE_REASONS = {CLOSE_ENDED: "ended", CLOSE_REPLACED: "replaced", CLOSE_NO_TIME: "no_time",
                 CLOSE_TOO_MANY: "too_many", CLOSE_FORBIDDEN: "forbidden", CLOSE_GUARDED: "guarded",
                 CLOSE_LOCKED: "locked"}


def _guard_code(guard):
    return CLOSE_LOCKED if guard.state == "locked" else CLOSE_GUARDED


async def _end(websocket, code):
    try:
        await websocket.close(code=code)
    except Exception:
        pass


async def _refuse(websocket, kind, code):
    """Closes a view or terminal before it opened, with its reason, logged and counted."""
    logging.info("Agent workspace %s refused code=%d", kind, code)
    await _end(websocket, code)
    await asyncio.to_thread(_count, kind, "refused_" + CLOSE_REASONS[code])


async def _admit(websocket, kind):
    """A view's or terminal's start: the account behind its first message
    (signed in, allowed the VM), the rate limit and what is left of today's
    VM time. ``(uid, seconds, first message, day_left)``, or None once it is
    closed."""
    await websocket.accept()
    try:
        first = await asyncio.wait_for(websocket.receive_text(), SIGN_IN_SECONDS)
        hello = json.loads(first) if first.startswith("{") else {}
    except Exception:
        hello = {}
    hello = hello if isinstance(hello, dict) else {}
    uid = await asyncio.to_thread(_sign_in, hello.get("id_token"))
    if uid is None:
        await _refuse(websocket, kind, CLOSE_FORBIDDEN)
        return None
    try:
        api_uid_limiter.check(uid, f"agent:workspace_{kind}", VIEWS_PER_MINUTE)
    except ApiUidRateLimitExceeded:
        await _refuse(websocket, kind, CLOSE_TOO_MANY)
        return None
    guard = await asyncio.to_thread(workspace_guard.status, uid)
    if guard.closed:
        await _refuse(websocket, kind, _guard_code(guard))
        return None
    seconds, day_left = await asyncio.to_thread(_time_left, uid)
    if seconds < 1:
        await _refuse(websocket, kind, CLOSE_NO_TIME)
        return None
    return uid, seconds, hello, day_left


class Meter:
    """The bytes a view or terminal carried (both ways) since the guard last took them."""

    def __init__(self):
        self.bytes = 0

    def add(self, data):
        self.bytes += len(data)

    def take(self):
        taken, self.bytes = self.bytes, 0
        return taken


async def _carry(websocket, upstream, uid, kind, view_id, seconds, started, to_vm, to_browser, ending=None,
                 meter=None):
    """Carries both ways until one side ends, the time is up, a newer one
    of this kind took over or the server's safety rules closed the
    workspace; then counts the open time as VM time and closes with the
    reason (CLOSE_*). ``ending`` is what the two ways noted about their end
    (who, and the numbers they got), for the log; ``meter`` what they
    carried, which the safety rules count (the view's, not the terminal's)."""
    ending = ending if ending is not None else {}
    async def replaced():
        # A newer view (or terminal) of the account took over: this one ends.
        while True:
            await asyncio.sleep(agent_workspace.VIEW_CHECK_SECONDS)
            try:
                if not await asyncio.to_thread(agent_workspace.holds_view, db_firestore, uid, view_id, kind):
                    return
            except Exception as exc:
                logging.info("Agent workspace %s check failed category=%s", kind, safe_exception(exc))

    async def guarded():
        # The bytes so far go to the safety rules now and then (each hand-over
        # is a count in Firestore); a workspace they closed (also by another
        # way, the agent's calls) ends this one.
        handed = time.monotonic()
        while True:
            await asyncio.sleep(workspace_guard.CHECK_SECONDS)
            if meter is not None and time.monotonic() - handed >= workspace_guard.VIEW_BYTES_SECONDS:
                handed = time.monotonic()
                workspace_guard.note_view_bytes(uid, meter.take())
            try:
                found = await asyncio.to_thread(workspace_guard.status, uid)
            except Exception as exc:
                logging.info("Agent workspace %s guard check failed category=%s", kind, safe_exception(exc))
                continue
            if found.closed:
                return found

    watcher = asyncio.ensure_future(replaced())
    guard = asyncio.ensure_future(guarded())
    tasks = [asyncio.ensure_future(to_vm()), asyncio.ensure_future(to_browser()), watcher, guard]
    done, _ = await asyncio.wait(tasks, timeout=seconds, return_when=asyncio.FIRST_COMPLETED)
    for task in tasks:
        task.cancel()
    if meter is not None:
        workspace_guard.note_view_bytes(uid, meter.take())
    # A way that broke (the provider's socket dropped, a send into a closed
    # socket): its kind of error, never its words.
    for task in done:
        if task not in {watcher, guard} and not task.cancelled() and task.exception() is not None:
            ending.setdefault("by", "error")
            logging.warning("Agent workspace %s carry failed category=%s", kind, safe_exception(task.exception()))
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
    # Its hour, or today's VM time, is over; a newer one took over; or the
    # safety rules closed the workspace.
    closed = guard.result() if guard in done and not guard.cancelled() and guard.exception() is None else None
    code = (CLOSE_ENDED if seconds >= VIEW_SECONDS else CLOSE_NO_TIME) if not done \
        else _guard_code(closed) if closed is not None else CLOSE_REPLACED if watcher in done else 1000
    by = CLOSE_REASONS.get(code) or ending.get("by") or "unknown"
    details = "".join(f" {key}={ending[key]}" for key in ("browser_code", "upstream_code", "exit")
                      if isinstance(ending.get(key), int))
    logging.info("Agent workspace %s closed seconds=%d code=%d by=%s%s", kind, int(elapsed), code, by, details)
    await _end(websocket, code)
    await asyncio.to_thread(_count, kind, "end_" + by, elapsed)


@router.websocket("/agent/workspace/view")
async def workspace_view(websocket: WebSocket):
    admitted = await _admit(websocket, "view")
    if admitted is None:
        return
    uid, seconds, _, day_left = admitted
    await _state(websocket, "connecting", **({} if day_left is None else {"left_seconds": day_left}))
    started = time.monotonic()
    try:
        url = await asyncio.to_thread(_open, uid, seconds)
        view_id = await asyncio.to_thread(agent_workspace.claim_view, _store(), uid, seconds)
        upstream = await connect_upstream(url)
    except Exception as exc:
        logging.warning("Agent workspace view unavailable category=%s", safe_exception(exc))
        await _state(websocket, "error")
        await websocket.close(code=1011)
        await asyncio.to_thread(_count, "view", "failed")
        return
    await asyncio.to_thread(_count, "view", "opened")
    ending = {}
    meter = Meter()

    async def to_vm():
        # The view's bytes go to the relay's stdin (exec frames 0x00).
        while True:
            message = await websocket.receive()
            if message["type"] == "websocket.disconnect":
                ending.setdefault("by", "browser")
                ending.setdefault("browser_code", message.get("code"))
                return
            if message.get("bytes") is not None:
                meter.add(message["bytes"])
                await upstream.send(b"\x00" + message["bytes"])

    async def to_browser():
        # stdout (0x01) is VNC once the relay said "ready"; its states come
        # as JSON lines on stderr (0x02) before, and the whole time what the
        # safety rules count (relay_line); the exit (0x03) ends it.
        pending = b""
        async for message in upstream:
            if not isinstance(message, bytes) or not message:
                continue
            stream, payload = message[0], message[1:]
            if stream == 1 and payload:
                meter.add(payload)
                await websocket.send_bytes(payload)
            elif stream == 2:
                pending += payload
                while b"\n" in pending:
                    line, pending = pending.split(b"\n", 1)
                    state = relay_line(uid, line)
                    if state == "error":
                        logging.warning("Agent workspace view relay error")
                    if state in {"setup", "starting", "ready", "error"}:
                        await _state(websocket, state)
                # A line longer than any the relay writes is dropped, never kept growing.
                if len(pending) > STATE_LINE_BYTES:
                    pending = b""
            elif stream == 3:
                ending.setdefault("by", "relay")
                ending.setdefault("exit", payload[0] if payload else None)
                return
        ending.setdefault("by", "upstream")
        ending.setdefault("upstream_code", getattr(upstream, "close_code", None))

    await _carry(websocket, upstream, uid, "view", view_id, seconds, started, to_vm, to_browser, ending, meter)


# Who steers the browser, for the safety rules: until when each account's
# user holds it, as its takeover said here (workspace_control; the open view
# renews it every CONTROL_REFRESH_SECONDS). In this process, no Firestore
# read per page.
_takeovers: dict[str, float] = {}


def _note_takeover(uid, holder):
    if holder == "user":
        _takeovers[uid] = time.monotonic() + agent_workspace.CONTROL_SECONDS
    else:
        _takeovers.pop(uid, None)


def _steering(uid):
    """"user" while the account's user holds the browser, else "view"."""
    return "user" if _takeovers.get(uid, 0) > time.monotonic() else "view"


def relay_line(uid, line):
    """One JSON line of the relay's stderr: its state, which the caller
    passes on, or what the safety rules count (a page's host with who
    steered then, the VM's network counters, its Chrome policy). Anything
    else is dropped: the browser VM is not trusted."""
    try:
        data = json.loads(line) if len(line) <= STATE_LINE_BYTES else None
    except ValueError:
        return None
    if not isinstance(data, dict):
        return None
    if isinstance(data.get("visit"), str):
        workspace_guard.note_visit(uid, data["visit"], _steering(uid))
    elif isinstance(data.get("net"), dict):
        workspace_guard.note_net(uid, data["net"])
    elif isinstance(data.get("policy"), str):
        workspace_guard.note_policy(uid, data["policy"])
    state = data.get("state")
    return state if isinstance(state, str) else None


@router.websocket("/agent/workspace/terminal")
async def workspace_terminal(websocket: WebSocket):
    admitted = await _admit(websocket, "terminal")
    if admitted is None:
        return
    uid, seconds, hello, _ = admitted
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
        await asyncio.to_thread(_count, "terminal", "failed")
        return
    await _state(websocket, "ready")
    await asyncio.to_thread(_count, "terminal", "opened")
    ending = {}

    async def to_vm():
        # Keystrokes go to the TTY as they are; a resize as the provider's
        # own message, rebuilt from two checked numbers.
        while True:
            message = await websocket.receive()
            if message["type"] == "websocket.disconnect":
                ending.setdefault("by", "browser")
                ending.setdefault("browser_code", message.get("code"))
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
                ending.setdefault("by", "relay")
                ending.setdefault("exit", data.get("exit_code"))
                return
        ending.setdefault("by", "upstream")
        ending.setdefault("upstream_code", getattr(upstream, "close_code", None))

    # The terminal's bytes do not count: its output is the user's own work (a runaway
    # loop prints gigabytes), and its machine reaches only package registries.
    await _carry(websocket, upstream, uid, "terminal", terminal_id, seconds, started, to_vm, to_browser, ending)

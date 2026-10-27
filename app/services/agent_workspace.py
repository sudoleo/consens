"""The account's workspace (since 2026-10-27, docs/agent-mode.md "Workspace"):
one Linux VM for all of an account's chats and its user, like a colleague's
computer. The agent works there (agent_vm_tools.py), and the user watches
and steers its browser live (routers/agent_workspace.py, workspace-view.js).

Record and lease: ``users/{uid}/chat_state/agent_workspace`` names the VM
before the provider creates it, so the account's deletion always finds it,
and leases it to one chat's message at a time (``lease``: chat, turn,
until). A lease ends with its message (release) or by itself LEASE_SECONDS
after its last VM call, so a run that died never blocks the workspace. The
user's live view takes no lease: it is their computer.

Tools in the VM (workspace_vm/): ``browser``, the agent's way to use the
workspace's Chrome; the browser's setup and start; the live view's gateway,
a VM service on GATEWAY_PORT that the VM's private address leads to. They are
written again whenever their VERSION changed (prepare), at the first VM call
of a message or when the view opens.

Folders and notes (like Claude Code's memory): each chat's folder names its
chat in CHAT_MARKER (title, start, id), so a chat finds another's files; and
NOTES_PATH is the agent's own notebook of the workspace across chats (what is
where, what is in progress, a project's conventions). Its beginning comes with
the first VM result of every message (read_notes), as data; the user's memory
(agent_memory.py) stays what the user said about themselves.

Takeover: ``control.json`` in the VM says the user has the browser until a
time the open view keeps moving on (CONTROL_SECONDS), and the account's
record says the same (``control``). While it holds, the agent pauses
completely, so nothing of it sees what the user types there: the server holds
its VM calls (user_has_browser, VMSession.wait_for_user), ``browser`` refuses
to act, and pause.py freezes whatever of the agent already runs in the VM
(agent_vm.AGENT_MARK) until the user hands back or the takeover expires. The
reviewers follow what the agent does, never what the user does.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
import logging
from pathlib import Path
import time

from app.core.observability import safe_exception
from app.services import agent_vm

HOME = agent_vm.HOME
WORKSPACE_DOC = "agent_workspace"
LEASE_SECONDS = 600
# A lease is moved on when a VM call finds less than this left.
LEASE_RENEW_SECONDS = LEASE_SECONDS - 120
WORKSPACE_DIR = HOME + "/.consens/workspace"
VERSION_PATH = WORKSPACE_DIR + "/version"
CONTROL_PATH = WORKSPACE_DIR + "/control.json"
BROWSER_COMMAND = HOME + "/.local/bin/browser"
BROWSER_PROFILE = HOME + "/.consens/browser/profile"
NOTES_PATH = HOME + "/NOTES.md"
# What of the notes comes with a message's first VM result; the rest the agent
# reads itself.
NOTES_CHARS = 6000
GATEWAY_PORT = 6080
GATEWAY_SERVICE = "view"
# How long a takeover holds without the view refreshing it (it does every
# CONTROL_REFRESH_SECONDS while the user has the browser).
CONTROL_SECONDS = 90
CONTROL_REFRESH_SECONDS = 30
TOOL_FILES = ("browser.py", "display.sh", "gateway.py", "pause.py", "setup.sh")
# Started at every takeover, without the agent's mark (a second one ends at once).
PAUSE_COMMAND = (f"env -u {agent_vm.AGENT_MARK.split('=')[0]} setsid nohup python3 {WORKSPACE_DIR}/pause.py "
                 ">/dev/null 2>&1 </dev/null &")
PAUSE_START_SECONDS = 30
_FILES = Path(__file__).with_name("workspace_vm")
WRAPPER = b'#!/bin/sh\nexec python3 "$HOME/.consens/workspace/browser.py" "$@"\n'

# What the agent reads when another chat has the workspace; the activity
# says it calmly (agent-activity.js, outcome "busy").
VM_BUSY = ("Your workspace is in use by another chat of this account right now (one chat at a time). Continue "
           "without it for this message and tell the user it is free again once the other chat's response is done.")
RESTORED_NOTE = ("The user restored the workspace to how it was before an earlier message since this chat last used "
                 "it: whatever later commands changed there is gone, in every chat's folder and the browser. Check "
                 "the files before you rely on them.")


class WorkspaceBusy(Exception):
    """Another chat's message holds the workspace."""


@dataclass(frozen=True)
class Claim:
    restored: bool
    title: str = ""
    started: str = ""


def tool_files():
    """The VM's tools as written there (LF line ends whatever the checkout)."""
    return {name: (_FILES / name).read_bytes().replace(b"\r\n", b"\n") for name in TOOL_FILES}


def _version():
    digest = hashlib.sha256()
    for name, data in sorted(tool_files().items()):
        digest.update(name.encode() + b"\0" + data + b"\0")
    digest.update(WRAPPER + str(GATEWAY_PORT).encode())
    return digest.hexdigest()[:16]


VERSION = _version()


def ref(db, uid):
    return db.collection("users").document(uid).collection("chat_state").document(WORKSPACE_DOC)


def _now():
    return datetime.now(timezone.utc)


def _held_by_other(lease, chat_id, now):
    """The chat of a live lease that is not ``chat_id``'s, else None. One
    chat runs one message at a time, so its own lease is never a conflict."""
    if not isinstance(lease, dict):
        return None
    until = lease.get("until")
    if not isinstance(until, datetime) or until <= now or lease.get("chat_id") == chat_id:
        return None
    return lease.get("chat_id")


def claim(store, uid, chat_id, turn_id, *, provider):
    """In one transaction: the account may write, the chat is still active,
    the account's workspace is recorded on the account and the chat (before
    the provider creates it) and leased to this message. Raises WorkspaceBusy
    when another chat's message holds it. Returns a Claim: whether the
    workspace was restored since this chat last used it, and the chat's title
    and start for its folder (make_chat_dir)."""
    from app.services import persistence_guard
    from app.services.chat_store import ChatNotFound
    name = agent_vm.workspace_name(uid)
    workspace, chat = ref(store.db, uid), store._chat_ref(uid, chat_id)
    outcome = {}

    def operation(tx):
        persistence_guard.ensure_account_write_allowed(uid=uid, db=store.db, transaction=tx)
        chat_data = chat.get(transaction=tx).to_dict() or {}
        if chat_data.get("status") != "active":
            raise ChatNotFound("Chat not found")
        record = workspace.get(transaction=tx).to_dict() or {}
        now = _now()
        if _held_by_other(record.get("lease"), chat_id, now):
            raise WorkspaceBusy()
        used = (chat_data.get("agent_vm") or {}) if isinstance(chat_data.get("agent_vm"), dict) else {}
        # Restores of the workspace so far, and how many this chat was told of.
        restores = int(record.get("restores") or 0)
        outcome["restored"] = bool(used.get("workspace")) and restores > int(used.get("restores_seen") or 0)
        started = chat_data.get("created_at")
        outcome["title"] = str(chat_data.get("title") or "")
        outcome["started"] = started.date().isoformat() if isinstance(started, datetime) else ""
        tx.set(workspace, {**{key: value for key, value in record.items() if key != "lease"},
                           "provider": provider, "name": name,
                           "created_at": record.get("created_at") or now.isoformat(),
                           "lease": {"chat_id": chat_id, "turn_id": turn_id, "until": now + timedelta(
                               seconds=LEASE_SECONDS)}})
        tx.update(chat, {"agent_vm": {**{key: value for key, value in used.items()
                                         if key in {"restored", "created_at"}},
                                      "provider": provider, "name": name, "workspace": True,
                                      "created_at": used.get("created_at") or now.isoformat(), "used_at": now,
                                      "restores_seen": restores}})
    store._transaction(operation)
    return Claim(restored=outcome.get("restored", False), title=outcome.get("title", ""),
                 started=outcome.get("started", ""))


def renew(store, uid, turn_id):
    """Moves this message's lease on; False when it is not this message's
    any more (it expired and another chat took the workspace)."""
    workspace = ref(store.db, uid)
    held = {}

    def operation(tx):
        record = workspace.get(transaction=tx).to_dict() or {}
        lease = record.get("lease") or {}
        held["ours"] = lease.get("turn_id") == turn_id
        if held["ours"]:
            tx.update(workspace, {"lease": {**lease, "until": _now() + timedelta(seconds=LEASE_SECONDS)}})
    store._transaction(operation)
    return held["ours"]


def release(store, uid, turn_id):
    """Ends this message's lease; failures only cost the wait for its expiry."""
    workspace = ref(store.db, uid)

    def operation(tx):
        record = workspace.get(transaction=tx).to_dict() or {}
        if (record.get("lease") or {}).get("turn_id") == turn_id:
            tx.update(workspace, {"lease": None})
    try:
        store._transaction(operation)
    except Exception as exc:
        logging.warning("Agent workspace release failed category=%s", safe_exception(exc))


def record(db, uid):
    return ref(db, uid).get().to_dict() or {}


def held_by(db, uid, now=None):
    """The chat whose message holds the workspace now, or None."""
    return _held_by_other(record(db, uid).get("lease"), None, now or _now())


def mark_restored(store, uid):
    """The workspace went back to a checkpoint: every chat's next message
    that uses it is told (claim)."""
    workspace = ref(store.db, uid)

    def operation(tx):
        snapshot = workspace.get(transaction=tx)
        if snapshot.exists:
            tx.update(workspace, {"restores": int((snapshot.to_dict() or {}).get("restores") or 0) + 1,
                                  "restored_at": _now()})
    store._transaction(operation)


def record_for_view(store, uid, *, provider):
    """The view may open the workspace before any chat used it: recorded on
    the account (no lease) before the provider creates it."""
    from app.services import persistence_guard
    workspace = ref(store.db, uid)

    def operation(tx):
        persistence_guard.ensure_account_write_allowed(uid=uid, db=store.db, transaction=tx)
        current = workspace.get(transaction=tx).to_dict() or {}
        if current.get("name") != agent_vm.workspace_name(uid):
            tx.set(workspace, {**current, "provider": provider, "name": agent_vm.workspace_name(uid),
                               "created_at": current.get("created_at") or _now().isoformat()})
    store._transaction(operation)


def _quiet(stream, chunk):
    pass


def prepare(vm, name):
    """The VM's tools at this VERSION: written, the ``browser`` command made
    executable and the gateway service (re)created, only when the version in
    the VM differs. Returns whether it wrote them."""
    try:
        raw, _ = vm.read_file(name, VERSION_PATH, limit=64)
    except agent_vm.VMFileMissing:
        raw = b""
    if raw.decode("utf-8", "replace").strip() == VERSION:
        return False
    for file, data in tool_files().items():
        vm.write_file(name, f"{WORKSPACE_DIR}/{file}", data)
    vm.write_file(name, BROWSER_COMMAND, WRAPPER)
    vm.chmod(name, BROWSER_COMMAND, "755")
    vm.put_service(name, GATEWAY_SERVICE, {"cmd": "python3", "args": [f"{WORKSPACE_DIR}/gateway.py"],
                                           "http_port": GATEWAY_PORT})
    vm.write_file(name, VERSION_PATH, VERSION.encode())
    return True


# Makes the chat's folder (the file API creates the folders a file needs),
# where commands start, and names its chat there: the folders themselves are
# ids, so `cat ~/chats/*/.consens-chat` tells the agent which is which.
CHAT_MARKER = ".consens-chat"
TITLE_CHARS = 200


def chat_marker(chat_id, title="", started=""):
    title = " ".join(str(title or "").split())[:TITLE_CHARS] or "(untitled)"
    return (f"chat: {title}\nstarted: {started or 'unknown'}\nid: {chat_id}\n"
            "This folder holds the files of that chat; it is deleted with the chat.\n").encode("utf-8")


def make_chat_dir(vm, name, chat_id, title="", started=""):
    """Written at every message's first VM call: the title follows a rename."""
    vm.write_file(name, f"{agent_vm.chat_dir(chat_id)}/{CHAT_MARKER}", chat_marker(chat_id, title, started))


def read_notes(vm, name):
    """The beginning of the workspace's notes for the agent, or that there
    are none yet: ``{"path", "text", "more"}``. Data, never instructions
    (AGENT_VM_PROMPT)."""
    try:
        raw, complete = vm.read_file(name, NOTES_PATH, limit=NOTES_CHARS * 4)
    except agent_vm.VMFileMissing:
        return {"path": NOTES_PATH, "text": "", "note": "No notes yet: start them when something lasting comes up."}
    text = raw.decode("utf-8", "replace")
    notes = {"path": NOTES_PATH, "text": text[:NOTES_CHARS]}
    if len(text) > NOTES_CHARS or not complete:
        notes["more"] = f"The notes go on: read the rest with vm_read_file {NOTES_PATH}, and keep them shorter."
    return notes


def control_payload(holder, *, now=None):
    """control.json: the user's takeover with its expiry, or the agent's turn."""
    until = (now or time.time()) + CONTROL_SECONDS if holder == "user" else 0
    return json.dumps({"holder": holder, "until": until}).encode()


def set_control(db, uid, vm, name, holder, cancellation):
    """The user takes the browser over (again at every refresh of the view)
    or hands it back. Taking over closes the server's way first (the record),
    then the browser's (control.json), then freezes what already runs
    (pause.py); handing back opens them in the other order."""
    now = time.time()
    control = {"holder": holder, "until": now + CONTROL_SECONDS if holder == "user" else 0}
    if holder == "user":
        ref(db, uid).update({"control": control})
        vm.write_file(name, CONTROL_PATH, control_payload(holder, now=now))
        vm.exec(name, PAUSE_COMMAND, cwd=HOME, timeout=PAUSE_START_SECONDS, on_output=_quiet,
                cancellation=cancellation, agent=False)
        return
    vm.write_file(name, CONTROL_PATH, control_payload(holder, now=now))
    ref(db, uid).update({"control": control})


def user_has_browser(db, uid, now=None):
    """Whether the user has the workspace's browser now (the record's
    ``control``, which only the server writes)."""
    control = record(db, uid).get("control")
    if not isinstance(control, dict) or control.get("holder") != "user":
        return False
    try:
        return float(control.get("until") or 0) > (now or time.time())
    except (TypeError, ValueError):
        return False


def reset_browser(vm, name, cancellation):
    """Ends the browser and deletes its profile: every sign-in, cookie and
    open tab. The next use starts a fresh one."""
    vm.exec(name, f"pkill -f '[u]ser-data-dir={BROWSER_PROFILE}'; sleep 1; rm -rf {BROWSER_PROFILE}", cwd=HOME,
            timeout=60, on_output=_quiet, cancellation=cancellation, agent=False)


def delete_for_account(db, uid, *, factory=None):
    """With the account (account_deletion.py): the workspace VM, then its
    record. Nothing to do for an account that never had one."""
    workspace = ref(db, uid)
    if not workspace.get().exists:
        return
    agent_vm.delete_workspace(uid, factory=factory)
    workspace.delete()

"""The account's workspace (since 2026-10-27, docs/agent-mode.md "Workspace"):
two Linux VMs for all of an account's chats and its user, like a
colleague's computer and its browser. The agent works on the workbench
(agent_vm.workspace_name, agent_vm_tools.py) as a user of its own; the
browser (agent_vm.browser_name) holds Chrome, which the user watches and
steers live (routers/agent_workspace.py, workspace-view.js) and the agent
uses through the ``browser`` tool (agent_browser.py). No code of the agent
runs on the browser, and the workbench reaches only package registries and
what the user allowed for the chat (agent_domains.py): security audit
2026-10-27, Max's option A.

Record and lease: ``users/{uid}/chat_state/agent_workspace`` names both VMs
before the provider creates either, so the account's deletion always finds
them, and leases the workspace to one chat's message at a time (``lease``:
chat, turn, until). A lease ends with its message (release) or by itself
LEASE_SECONDS after its last VM call, so a run that died never blocks the
workspace. The user's live view takes no lease: it is their computer.

Tools in the VMs (workspace_vm/): on the workbench ``agent-run``, which every
command and file operation of the agent goes through, its setup (the
agent's user, the move from the layout before) and the pause; on the browser
``browser.py``, the one program the browser tool calls, the browser's setup
and start, and the live view's relay. They are written again whenever their
VERSION changed (prepare, prepare_browser), at a message's first call of
either or when the view opens.

Folders and notes (like Claude Code's memory): each chat's folder names its
chat in CHAT_MARKER (title, start, id), so a chat finds another's files; and
NOTES_PATH is the agent's own notebook of the workspace across chats (what is
where, what is in progress, a project's conventions). Its beginning comes with
the first VM result of every message (read_notes), as data; the user's memory
(agent_memory.py) stays what the user said about themselves.

Takeover: the account's record says the user has the browser until a time
the open view keeps moving on (CONTROL_SECONDS, ``control``), and so do
``control.json`` on the browser and on the workbench. While it holds, the
agent pauses completely: the server holds its calls (user_has_browser,
VMSession.wait_for_user), browser.py refuses to act, and the workbench's
pause.py freezes whatever of the agent already runs there, by its user. The
reviewers follow what the agent does, never what the user does.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
import logging
from pathlib import Path
import secrets
import time

from app.core.observability import safe_exception
from app.services import agent_vm

HOME = agent_vm.HOME
WORKSPACE_DOC = "agent_workspace"
LEASE_SECONDS = 600
# A lease is moved on when a VM call finds less than this left.
LEASE_RENEW_SECONDS = LEASE_SECONDS - 120
# The server's own files, in the provider's home on each VM; on the
# workbench the agent's user cannot open it.
WORKSPACE_DIR = agent_vm.TOOLS_DIR
VERSION_PATH = WORKSPACE_DIR + "/version"
CONTROL_PATH = WORKSPACE_DIR + "/control.json"
BROWSER_STATE = agent_vm.SERVER_HOME + "/.consens/browser"
BROWSER_CONTROL = BROWSER_STATE + "/control.json"
BROWSER_PROFILE = BROWSER_STATE + "/profile"
BROWSER_UPLOADS = BROWSER_STATE + "/uploads"
BROWSER_HELPER = WORKSPACE_DIR + "/browser.py"
BROWSER_RELAY = WORKSPACE_DIR + "/relay.py"
NOTES_PATH = HOME + "/NOTES.md"
# What of the notes comes with a message's first VM result; the rest the agent
# reads itself.
NOTES_CHARS = 6000
# The live view's gateway service before 2026-10-27, removed by prepare.
OLD_GATEWAY_SERVICE = "view"
# How long a takeover holds without the view refreshing it (it does every
# CONTROL_REFRESH_SECONDS while the user has the browser).
CONTROL_SECONDS = 90
CONTROL_REFRESH_SECONDS = 30
WORKBENCH_FILES = ("agent-run", "pause.py", "setup.sh")
BROWSER_FILES = ("browser.py", "display.sh", "relay.py", "setup.sh")
SETUP_SECONDS = 180
# Started as root at every takeover (a second one ends at once).
PAUSE_COMMAND = (f"sudo -n setsid nohup \"$(command -v python3)\" {WORKSPACE_DIR}/pause.py "
                 ">/dev/null 2>&1 </dev/null &")
PAUSE_START_SECONDS = 30
_FILES = Path(__file__).with_name("workspace_vm")

# What the agent reads when another chat has the workspace; the activity
# says it calmly (agent-activity.js, outcome "busy").
VM_BUSY = ("Your workspace is in use by another chat of this account right now (one chat at a time). Continue "
           "without it for this message and tell the user it is free again once the other chat's response is done.")
RESTORED_NOTE = ("The user restored the workspace to how it was before an earlier message since this chat last used "
                 "it: whatever later commands changed there is gone, in every chat's folder. Check the files before "
                 "you rely on them.")


class WorkspaceBusy(Exception):
    """Another chat's message holds the workspace."""


@dataclass(frozen=True)
class Claim:
    restored: bool
    title: str = ""
    started: str = ""
    # The domains the user allowed for this chat (agent_domains.py).
    domains: tuple = ()


def tool_files(kind="workbench"):
    """A VM's tools as written there (LF line ends whatever the checkout)."""
    names = WORKBENCH_FILES if kind == "workbench" else BROWSER_FILES
    return {name: (_FILES / kind / name).read_bytes().replace(b"\r\n", b"\n") for name in names}


def _version(kind):
    digest = hashlib.sha256(kind.encode() + b"\0" + agent_vm.AGENT_USER.encode() + b"\0")
    for name, data in sorted(tool_files(kind).items()):
        digest.update(name.encode() + b"\0" + data + b"\0")
    return digest.hexdigest()[:16]


VERSION = _version("workbench")
BROWSER_VERSION = _version("browser")


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
    the account's workspace (both VMs) is recorded on the account and the
    chat (before the provider creates either) and leased to this message.
    Raises WorkspaceBusy when another chat's message holds it. Returns a
    Claim: whether the workspace was restored since this chat last used it,
    the chat's title and start for its folder (make_chat_dir) and the
    domains its user allowed (agent_domains.py)."""
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
        from app.services import agent_domains
        outcome["domains"] = agent_domains.granted(chat_data)
        tx.set(workspace, {**{key: value for key, value in record.items() if key != "lease"},
                           "provider": provider, "name": name, "browser": agent_vm.browser_name(uid),
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
                 started=outcome.get("started", ""), domains=tuple(outcome.get("domains") or ()))


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
    """The view may open the workspace before any chat used it: both VMs
    recorded on the account (no lease) before the provider creates one."""
    from app.services import persistence_guard
    workspace = ref(store.db, uid)

    def operation(tx):
        persistence_guard.ensure_account_write_allowed(uid=uid, db=store.db, transaction=tx)
        current = workspace.get(transaction=tx).to_dict() or {}
        if (current.get("name") != agent_vm.workspace_name(uid)
                or current.get("browser") != agent_vm.browser_name(uid)):
            tx.set(workspace, {**current, "provider": provider, "name": agent_vm.workspace_name(uid),
                               "browser": agent_vm.browser_name(uid),
                               "created_at": current.get("created_at") or _now().isoformat()})
    store._transaction(operation)


# The live view (routers/agent_workspace.py): one per account, the newest
# wins, and an older one ends within VIEW_CHECK_SECONDS once it sees that
# (security audit 2026-10-27; before, any number stayed open for an hour
# each). An open view keeps the VM awake: its time counts as VM time.
VIEW_CHECK_SECONDS = 30


def claim_view(store, uid, seconds):
    """This view is the account's one from now on (record_for_view made the
    record): its id, which the view checks (holds_view)."""
    view_id = secrets.token_hex(8)
    workspace = ref(store.db, uid)

    def operation(tx):
        if workspace.get(transaction=tx).exists:
            tx.update(workspace, {"view": {"id": view_id, "until": _now() + timedelta(seconds=seconds)}})
    store._transaction(operation)
    return view_id


def holds_view(db, uid, view_id):
    """Whether ``view_id`` is still the account's view (no newer one took over)."""
    return (record(db, uid).get("view") or {}).get("id") == view_id


def _quiet(stream, chunk):
    pass


def _current(vm, name, version):
    try:
        raw, _ = vm.read_file(name, VERSION_PATH, limit=64, agent=False)
    except agent_vm.VMFileMissing:
        raw = b""
    return raw.decode("utf-8", "replace").strip() == version


def prepare(vm, name, cancellation=None):
    """The workbench at this VERSION, only when the version there differs
    (else one read): its tools written to the provider's home, the live
    view's gateway service of the layout before removed, and setup.sh run
    as root (the agent's user; once, the move of its files out of the
    provider's home). Returns whether it wrote them; raises VMUnavailable
    when the setup failed, so no command runs with the provider's rights."""
    from app.services.llm.provider_runtime import ProviderCancellation
    if _current(vm, name, VERSION):
        return False
    for file, data in tool_files("workbench").items():
        vm.write_file(name, f"{WORKSPACE_DIR}/{file}", data, agent=False)
    vm.delete_service(name, OLD_GATEWAY_SERVICE)
    said = []
    outcome = vm.exec(name, f"sudo -n bash {WORKSPACE_DIR}/setup.sh", cwd=agent_vm.SERVER_HOME,
                      timeout=SETUP_SECONDS, on_output=lambda stream, chunk: said.append(chunk),
                      cancellation=cancellation or ProviderCancellation(), agent=False)
    if outcome.exit_code != 0:
        logging.warning("Agent workbench setup failed exit=%s", outcome.exit_code)
        raise agent_vm.VMUnavailable("setup")
    vm.write_file(name, VERSION_PATH, VERSION.encode(), agent=False)
    return True


def prepare_browser(vm, name):
    """The browser VM's tools at BROWSER_VERSION (browser.py installs and
    starts the browser itself when called). Returns whether it wrote them."""
    if _current(vm, name, BROWSER_VERSION):
        return False
    for file, data in tool_files("browser").items():
        vm.write_file(name, f"{WORKSPACE_DIR}/{file}", data, agent=False)
    vm.write_file(name, VERSION_PATH, BROWSER_VERSION.encode(), agent=False)
    return True


def open_browser(vm, uid):
    """The account's browser VM, created if needed with its network rules
    and tools up to date; its name."""
    name = agent_vm.browser_name(uid)
    vm.ensure(name, agent_vm.BROWSER_RULES)
    prepare_browser(vm, name)
    return name


# Makes the chat's folder (as the agent's user, with the folders the file
# needs), where commands start, and names its chat there: the folders
# themselves are ids, so `cat ~/chats/*/.consens-chat` tells the agent which
# is which.
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


def set_control(db, uid, vm, holder, cancellation):
    """The user takes the browser over (again at every refresh of the view)
    or hands it back. Taking over closes the server's way first (the record),
    then the browser's (control.json there), then freezes what of the agent
    already runs on the workbench (pause.py, by its user); handing back opens
    them in the other order. A workbench that no chat made yet has nothing
    to freeze."""
    now = time.time()
    control = {"holder": holder, "until": now + CONTROL_SECONDS if holder == "user" else 0}
    payload = control_payload(holder, now=now)
    browser, workbench = agent_vm.browser_name(uid), agent_vm.workspace_name(uid)
    if holder == "user":
        ref(db, uid).update({"control": control})
        vm.write_file(browser, BROWSER_CONTROL, payload, agent=False)
        if vm.exists(workbench):
            vm.write_file(workbench, CONTROL_PATH, payload, agent=False)
            vm.exec(workbench, PAUSE_COMMAND, cwd=agent_vm.SERVER_HOME, timeout=PAUSE_START_SECONDS,
                    on_output=_quiet, cancellation=cancellation, agent=False)
        return
    if vm.exists(workbench):
        vm.write_file(workbench, CONTROL_PATH, payload, agent=False)
    vm.write_file(browser, BROWSER_CONTROL, payload, agent=False)
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


def reset_browser(vm, uid, cancellation):
    """Ends the browser and deletes its profile on the browser VM: every
    sign-in, cookie and open tab. The next use starts a fresh one. A browser
    VM that was never made has nothing to sign out of."""
    name = agent_vm.browser_name(uid)
    if not vm.exists(name):
        return
    vm.exec(name, f"pkill -f '[u]ser-data-dir={BROWSER_PROFILE}'; sleep 1; rm -rf {BROWSER_PROFILE} "
                  f"{BROWSER_UPLOADS}", cwd=agent_vm.SERVER_HOME, timeout=60, on_output=_quiet,
            cancellation=cancellation, agent=False)


def delete_for_account(db, uid, *, factory=None):
    """With the account (account_deletion.py): both VMs of the workspace by
    the names that follow from the account, then its record. Before 2026-10-27 a
    missing record ended this, and a later area of the deletion removed the
    record after one failed provider call: the VM stayed for good. Only a
    server without a provider skips an account without a record (it never
    made one there)."""
    workspace = ref(db, uid)
    if agent_vm.configured() or factory is not None or workspace.get().exists:
        agent_vm.delete_workspace(uid, factory=factory)
    workspace.delete()


# A message's checkpoint of the workbench (VMSession.ready; the browser VM has
# none) may bring the workspace back for
# this long, and only after the last time something left it for good
# (``restore_floor``): signing the browser out everywhere or deleting a
# chat. An older checkpoint would bring the sign-ins or the chat's folder
# back (security audit 2026-10-27). The provider keeps the checkpoints; only
# their use ends here.
RESTORE_DAYS = 14


def restorable(record, turn_vm, now=None):
    """Whether ``turn_vm`` (a turn's ``agent_vm``) names a checkpoint of this
    account's workspace that may still bring it back: taken in the workspace
    (its name), within RESTORE_DAYS and after the record's restore_floor."""
    now = now or _now()
    if not isinstance(turn_vm, dict) or not turn_vm.get("checkpoint"):
        return False
    if not record.get("name") or turn_vm.get("name") != record.get("name"):
        return False
    try:
        taken = datetime.fromisoformat(str(turn_vm.get("checkpoint_at") or ""))
    except ValueError:
        return False
    if taken.tzinfo is None or taken < now - timedelta(days=RESTORE_DAYS):
        return False
    floor = record.get("restore_floor")
    return not (isinstance(floor, datetime) and taken <= floor)


def raise_restore_floor(store, uid):
    """Something left the workspace for good (a sign-out everywhere, a
    chat's folder): no checkpoint from before may bring it back
    (restorable). An account without a record (deleted meanwhile) is left
    alone."""
    workspace = ref(store.db, uid)

    def operation(tx):
        if workspace.get(transaction=tx).exists:
            tx.update(workspace, {"restore_floor": _now()})
    store._transaction(operation)

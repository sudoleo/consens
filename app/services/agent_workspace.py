"""The account's workspace (docs/agent-mode.md "Arbeitsplatz"):
one Linux VM for all of an account's chats and its user, like a colleague's
computer with its browser (agent_vm.workspace_name). The agent works there
as a user of its own (agent_vm_tools.py); Chrome runs there as the
provider's user, which the user watches and steers live
(routers/agent_workspace.py, workspace-view.js) and the agent uses through
the ``browser`` tool (agent_browser.py). localhost in that browser is the
agent's own servers, no tunnel between them.

One VM, and what the agent must not reach it cannot reach by the
computer's own means: Unix users and file modes, not bridges between two VMs
(a localhost tunnel, uploads and downloads copied from VM to VM), each a
rule of its own (Max: "Sudo ist um einiges sicherer als eine von uns
implementierte Sicherheitslayer"). Chrome's protocol is a
socket in the provider's home (workspace_vm/browser/cdp.py, no TCP port),
its screen asks for a cookie from there and starts only on its own socket
(display.sh), and the agent's commands have a /tmp of their own
(agent-run). The network is open for the whole VM (agent_vm.RULES, Max's
decision). What a key the user gave the agent
can do, the agent can do with it: that holds on any computer.

Record and lease: ``users/{uid}/chat_state/agent_workspace`` names the VM
before the provider creates it, so the account's deletion always finds it,
and leases the workspace to one chat's message at a time (``lease``: chat,
turn, until). A lease ends with its message (release) or by itself
LEASE_SECONDS after its last VM call, so a run that died never blocks the
workspace. The user's live view takes no lease: it is their computer. A
record that still names an older browser VM of its own (``browser``) has it
deleted at the workspace's next start (retire_old_browser): the sign-ins are
made again once.

Tools in the VM (workspace_vm/): ``agent-run``, which every command and file
operation of the agent goes through, and setup.sh (the agent's user, its
/tmp, the moves from the layouts before); ``browser.py``, the one program
the browser tool calls, with cdp.py, the browser's installation, start and
rules and the live view's relay. They are written again whenever their
VERSION changed (prepare), at a message's first call or when the view or
terminal opens.

Folders and notes (like Claude Code's memory): each chat's folder names its
chat in CHAT_MARKER (title, start, id), so a chat finds another's files; and
NOTES_PATH is the agent's own notebook of the workspace across chats (what is
where, what is in progress, a project's conventions). Its beginning comes with
the first VM result of every message (open_chat), as data; the user's memory
(agent_memory.py) stays what the user said about themselves.

Takeover: the account's record says the user has the browser until a time
the open view keeps moving on (CONTROL_SECONDS, ``control``), and so does
``control.json`` next to the browser. While it holds, the agent waits: the
server holds its calls (user_has_browser, VMSession.wait_for_user) and
browser.py refuses to act. What already runs of the agent goes on: its
processes reach neither the screen nor Chrome, and the agent's server must
answer the browser while the user tries the agent's app. The reviewers
follow what the agent does, never what the user does.

A new account's workspace (provision): its first setup
installs Chrome, its screen and the rest (about a minute). A colleague of
Max's waited for it on her first try ("every normal user is gone then"),
two minutes after her first message to the agent. So the account's first
message to the agent makes the VM in the background, while the user still
talks to the agent; the first call that needs it waits only for what is
left (setup_lock, the browser's own installation lock). The time a start
still takes (START_SECONDS, start_until) is what the chat and the live view
count down.

The warm-up (warm_later): the app asks for the workspace before the user
opens it, so the live view finds the VM awake with its Chrome running, and a
VM the provider does not start is restored (heal) before anyone waits for it.
One that no restore brings back gets a new VM in its place, on the user's
word only (replace): its files and sign-ins do not come along.

The kit (KIT_APT, KIT_PYTHON): what the agent kept installing before it
could work is on every workspace, installed in the background where it is
missing (kit_later), after the account's provisioning and after a message
that used the workbench. No start waits for it.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
import logging
from pathlib import Path
import secrets
import shlex
import threading
import time

from app.core.observability import safe_exception
from app.services import agent_vm

HOME = agent_vm.HOME
WORKSPACE_DOC = "agent_workspace"
LEASE_SECONDS = 600
# A lease is moved on when a VM call finds less than this left.
LEASE_RENEW_SECONDS = LEASE_SECONDS - 120
# The server's own files, in the provider's home, which the agent's user
# cannot open.
WORKSPACE_DIR = agent_vm.TOOLS_DIR
VERSION_PATH = WORKSPACE_DIR + "/version"
BROWSER_STATE = agent_vm.SERVER_HOME + "/.consens/browser"
BROWSER_CONTROL = BROWSER_STATE + "/control.json"
BROWSER_PROFILE = BROWSER_STATE + "/profile"
BROWSER_UPLOADS = BROWSER_STATE + "/uploads"
# What the browser downloaded, until agent_browser copies it into the chat's
# folder (workspace_vm/browser/browser.py DOWNLOADS).
BROWSER_DOWNLOADS = BROWSER_STATE + "/downloads"
BROWSER_HELPER = WORKSPACE_DIR + "/browser.py"
BROWSER_RELAY = WORKSPACE_DIR + "/relay.py"
NOTES_PATH = HOME + "/NOTES.md"
# What of the notes comes with a message's first VM result; the rest the agent
# reads itself.
NOTES_CHARS = 6000
# The live view's former gateway service, removed by prepare.
OLD_GATEWAY_SERVICE = "view"
# How long a takeover holds without the view refreshing it (it does every
# CONTROL_REFRESH_SECONDS while the user has the browser).
CONTROL_SECONDS = 90
CONTROL_REFRESH_SECONDS = 30
# The tools of the VM, by their folder in workspace_vm/: the agent's side
# (agent-run, setup.sh) and the browser's (browser.py and cdp.py, its
# installation, start and rules: harden.sh with policy.json and openbox's two
# files hold whoever steers Chrome, workspace_guard.py; the live view's
# relay).
TOOL_FILES = {"workbench": ("agent-run", "nouserns.py", "setup.sh"),
              "browser": ("browser.py", "cdp.py", "display.sh", "harden.sh", "install.sh", "openbox-menu.xml",
                          "openbox-rc.xml", "policy.json", "relay.py", "xsocket.py")}
SETUP_SECONDS = 180
_FILES = Path(__file__).with_name("workspace_vm")

# What the agent reads when another chat has the workspace; the activity
# says it calmly (agent-activity.js, outcome "busy").
VM_BUSY = ("Your workspace is in use by another chat of this account right now (one chat at a time). Continue "
           "without it for this message and tell the user it is free again once the other chat's response is done.")
RESTORED_NOTE = ("The user restored the workspace to how it was before an earlier message since this chat last used "
                 "it: whatever later commands changed there is gone, in every chat's folder. Check the files before "
                 "you rely on them.")
HEALED_NOTE = ("The workspace's provider could not start it, so consens.io restored it to how it was before an "
               "earlier message since this chat last used it: whatever later commands changed there is gone, in "
               "every chat's folder. Check the files before you rely on them.")
REPLACED_NOTE = ("The workspace's provider could not start its computer any more, so the user started a new one since "
                 "this chat last used it. It is empty: every file from before is gone, in every chat's folder, with "
                 "the notes, the keys the user gave you, installed packages, background processes and the browser's "
                 "sign-ins. Files you shared in a chat are still in that chat. Say so where the user counts on "
                 "something from before, and make again what this message needs.")


class WorkspaceBusy(Exception):
    """Another chat's message holds the workspace."""


@dataclass(frozen=True)
class Claim:
    restored: bool
    title: str = ""
    started: str = ""
    # The name of the chat's folder as the chat records it (open_chat),
    # empty before its first message.
    folder: str = ""
    # The names of the keys the user gave the agent (agent_secrets.py),
    # kept on the account's record across restarts.
    secrets: tuple = ()
    # The newest of those restores was the workspace's own (heal).
    healed: bool = False
    # The workspace got a new computer since this chat last used it (replace).
    replaced: bool = False


def tool_files():
    """The VM's tools as written there (LF line ends whatever the checkout)."""
    return {name: (_FILES / folder / name).read_bytes().replace(b"\r\n", b"\n")
            for folder, names in TOOL_FILES.items() for name in names}


def _version():
    digest = hashlib.sha256(b"workspace\0" + agent_vm.AGENT_USER.encode() + b"\0")
    for name, data in sorted(tool_files().items()):
        digest.update(name.encode() + b"\0" + data + b"\0")
    # Its network rules come with a new version (prepare).
    digest.update(json.dumps(agent_vm.RULES, sort_keys=True).encode())
    return digest.hexdigest()[:16]


VERSION = _version()


# How long a start of a VM takes until its first call can run, by what it
# has to do (seconds): a new VM's setup with Chrome's package (setup.sh,
# 55-56 s on two test Sprites 2026-11-10), the browser's own installation
# at its first start with Chrome's start (install.sh and display.sh, about
# 40 s: a new account's provisioning took 95-109 s in all, Prod 2026-11-07
# to 11-09), the tools after a new version (7 s), a VM waking from cold with
# Chrome starting (median 15 s after a pause) or from warm (5 s), Chrome's
# start in the live view. Only what the user is told: the chat's step and
# the live view count the time left down (start_until); no start waits for
# them.
START_SECONDS = {"setup": 65, "install": 45, "update": 10, "cold": 15, "warm": 5, "chrome": 8}
# The phases only the browser goes through: the workbench is ready before them.
BROWSER_PHASES = frozenset({"install", "chrome"})
# A start whose end nobody said is forgotten this long after its estimate.
START_FORGET_SECONDS = 600
_starts: dict[tuple, dict] = {}
_starts_lock = threading.Lock()


class Start:
    """One running start of an account's VM (``kind`` "browser" or
    "workbench"): ``phase`` says what it does now, ``end`` that it is over.
    Several may run for one VM (a message and the account's provisioning);
    start_until says the latest. Both kinds start the same VM and wait for
    one setup (setup_lock): whoever waits asks for both (START_KINDS)."""

    def __init__(self, uid, kind):
        self.key = (uid, kind)

    def phase(self, phase, then=None):
        """Runs until about START_SECONDS[phase] from now, never earlier
        than it said before. ``then``: the phase the browser still goes
        through after this one (a new VM's setup is followed by the
        browser's installation), which whoever waits for the browser is
        told from the beginning (start_until) and ``next`` begins."""
        until = _now() + timedelta(seconds=START_SECONDS[phase])
        whole = until + timedelta(seconds=START_SECONDS[then] if then else 0)
        with _starts_lock:
            starts = _starts.setdefault(self.key, {})
            before = starts.get(self) or {}
            starts[self] = {
                "bench": None if phase in BROWSER_PHASES else max(until, before.get("bench") or until),
                "browser": max(whole, before.get("browser") or whole), "then": then}
        return self

    def next(self):
        """The phase this one named as following begins; nothing where it named none."""
        with _starts_lock:
            then = ((_starts.get(self.key) or {}).get(self) or {}).get("then")
        return self.phase(then) if then else self

    def end(self):
        with _starts_lock:
            starts = _starts.get(self.key)
            if starts is not None:
                starts.pop(self, None)
                if not starts:
                    _starts.pop(self.key, None)


START_KINDS = ("browser", "workbench")


def start_until(uid, kinds=START_KINDS, besides=None, *, bench=False):
    """About when the starts of the account's ``kinds`` still running end
    (the latest), or None when none runs; ``besides``: a Start left out.
    ``bench``: for a call that waits for the workbench alone, which the
    browser's own phases (BROWSER_PHASES) do not hold up."""
    now = _now()
    latest = None
    with _starts_lock:
        for kind in kinds:
            starts = _starts.get((uid, kind)) or {}
            for start, said in list(starts.items()):
                if said["browser"] + timedelta(seconds=START_FORGET_SECONDS) < now:
                    starts.pop(start, None)
                    continue
                until = said["bench" if bench else "browser"]
                if start is not besides and until is not None and (latest is None or until > latest):
                    latest = until
    return latest


# One setup of a workspace at a time in this process (one server instance):
# the account's provisioning, a message's start (VMSession._bench), the
# browser's warm-up and the view never run setup.sh side by side; the second
# waits and finds the version there. The browser's installation holds a lock
# of its own on the VM (workspace_vm/browser/install.sh).
_setup_locks: dict[str, threading.Lock] = {}
_setup_locks_lock = threading.Lock()


def setup_lock(name):
    with _setup_locks_lock:
        return _setup_locks.setdefault(name, threading.Lock())


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
    the provider creates it) and leased to this message. Raises
    WorkspaceBusy when another chat's message holds it. Returns a Claim:
    whether the workspace was restored since this chat last used it, the
    chat's title and start for its folder (open_chat) and the names of the
    account's keys."""
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
        outcome["healed"] = outcome["restored"] and record.get("restored_by") == "heal"
        # By the times, not by the newest restore's kind: a restore after
        # the new computer must not turn "every file is gone" into "check
        # the files" for a chat that has not been there since.
        replaced_at, last = record.get("replaced_at"), used.get("used_at")
        outcome["replaced"] = (bool(used.get("workspace")) and isinstance(replaced_at, datetime)
                               and not (isinstance(last, datetime) and last >= replaced_at))
        started = chat_data.get("created_at")
        outcome["title"] = str(chat_data.get("title") or "")
        outcome["started"] = started.date().isoformat() if isinstance(started, datetime) else ""
        folder = used.get("folder")
        outcome["folder"] = folder if isinstance(folder, str) else ""
        outcome["secrets"] = listed(record, "secret_names", str)
        tx.set(workspace, {**{key: value for key, value in record.items() if key != "lease"},
                           "provider": provider, "name": name,
                           "created_at": record.get("created_at") or now.isoformat(),
                           "lease": {"chat_id": chat_id, "turn_id": turn_id, "until": now + timedelta(
                               seconds=LEASE_SECONDS)}})
        tx.update(chat, {"agent_vm": {**{key: value for key, value in used.items()
                                         if key in {"restored", "created_at", "folder"}},
                                      "provider": provider, "name": name, "workspace": True,
                                      "created_at": used.get("created_at") or now.isoformat(), "used_at": now,
                                      "restores_seen": restores}})
    store._transaction(operation)
    return Claim(restored=outcome.get("restored", False), title=outcome.get("title", ""),
                 started=outcome.get("started", ""), folder=outcome.get("folder", ""),
                 secrets=outcome.get("secrets", ()), healed=outcome.get("healed", False),
                 replaced=outcome.get("replaced", False))


def listed(record, field, kind):
    """A list field of the record, its entries of ``kind`` only."""
    values = record.get(field)
    return tuple(value for value in values if type(value) is kind) if isinstance(values, list) else ()


def _merge(db, uid, change):
    """Merges into the account's record what ``change`` makes of the record
    as it stands (the fields to write, or None for nothing) and returns the
    record after. None once the account's deletion began, with nothing
    written: the deletion sweeps users/{uid}/chat_state once, and a write
    after it would leave a record of an account that is gone."""
    from app.services import persistence_guard
    doc = ref(db, uid)

    def operation(tx):
        persistence_guard.ensure_account_write_allowed(uid=uid, db=db, transaction=tx)
        current = persistence_guard._get(doc, tx).to_dict() or {}
        fields = change(current)
        if fields:
            persistence_guard._set(tx, doc, fields, merge=True)
        return {**current, **(fields or {})}
    try:
        return persistence_guard._run_transaction(db, operation)
    except persistence_guard.AccountDeletionInProgress:
        return None


def remember_values(db, uid, field, values, *, keep):
    """Adds ``values`` to the list ``field`` of the account's record, the
    newest last and at most ``keep`` (agent_secrets' names): the record
    outlives a restart of the server, the process's memory does not."""
    def change(record):
        kept = [value for value in (record.get(field) or []) if value not in values]
        return {field: [*kept, *values][-keep:]}
    _merge(db, uid, change)


# The sites the browser is logged in to, as the agent noted them
# (note_sign_in, agent_browser.py): ``sign_ins`` on the
# record, each {site, name, since}. Cookies cannot say it (consent and
# bot-protection cookies are cookies too, browser.py saved_sign_in), the
# agent sees it on the page. The list comes with
# every message (sign_ins_note) and the user sees it in Settings →
# Connections, where an entry can go; logging out of everything empties it.
SIGN_INS_KEPT = 20
SIGN_IN_NAME_CHARS = 40
SIGN_INS_NOTE = ("The workspace's browser was logged in to these sites when the agent last noted it (note_sign_in); "
                 "a session can run out, the page shows whether it still holds: {sites}.")


def sign_ins(record):
    """The record's sign-ins, oldest first, valid entries only."""
    values = record.get("sign_ins")
    entries = []
    for entry in values if isinstance(values, list) else ():
        if not isinstance(entry, dict) or not isinstance(entry.get("site"), str) or not entry["site"]:
            continue
        name, since = entry.get("name"), entry.get("since")
        entries.append({"site": entry["site"], "name": name if isinstance(name, str) and name else entry["site"],
                        "since": since if isinstance(since, str) else ""})
    return entries


def note_sign_in(db, uid, site, name, signed_in, *, today=None):
    """Puts ``site`` on the account's list of sign-ins (``signed_in``) or
    takes it off, and returns the list after. A site noted again keeps the
    day it was first noted and takes the new name; the newest
    SIGN_INS_KEPT stay."""
    def change(record):
        current = sign_ins(record)
        before = next((entry for entry in current if entry["site"] == site), None)
        entries = [entry for entry in current if entry["site"] != site]
        if signed_in:
            since = (before or {}).get("since") or (today or _now().date()).isoformat()
            entries.append({"site": site, "name": name or (before or {}).get("name") or site, "since": since})
        entries = entries[-SIGN_INS_KEPT:]
        return {"sign_ins": entries} if entries != current else None
    return sign_ins(_merge(db, uid, change) or {})


def clear_sign_ins(db, uid):
    """After the browser logged out of everything (reset_browser). A record
    without sign-ins stays as it is, and none is made."""
    _merge(db, uid, lambda record: {"sign_ins": []} if record.get("sign_ins") else None)


def sign_ins_note(entries):
    """What a message's context says of ``entries`` (sign_ins), or ""."""
    sites = "; ".join(f"{entry['name']} ({entry['site']}" + (f", since {entry['since']})" if entry["since"] else ")")
                      for entry in entries)
    return SIGN_INS_NOTE.format(sites=sites) if sites else ""


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


def holds_lease(store, uid, turn_id):
    """Whether the workspace's lease is still this message's: False once
    another message holds it, None when the record cannot be read."""
    try:
        lease = record(store.db, uid).get("lease")
    except Exception as exc:
        logging.warning("Agent workspace lease unreadable category=%s", safe_exception(exc))
        return None
    return isinstance(lease, dict) and lease.get("turn_id") == turn_id


def held_by(db, uid, now=None):
    """The chat whose message holds the workspace now, or None."""
    return _held_by_other(record(db, uid).get("lease"), None, now or _now())


def in_use(store, uid, now=None):
    """Whether a chat's message may be using the workspace now: its lease
    holds, or the chat named by the lease, also one past its time, still
    runs a response (its run lock, ``agent_lock_until``, which the running
    response keeps moving on). A restore never goes under a running agent,
    also when its lease ran out."""
    now = now or _now()
    lease = record(store.db, uid).get("lease")
    if _held_by_other(lease, None, now):
        return True
    if not isinstance(lease, dict) or not lease.get("chat_id"):
        return False
    try:
        chat = store._chat_ref(uid, lease["chat_id"]).get().to_dict() or {}
    except Exception as exc:
        logging.warning("Agent workspace lease chat unreadable category=%s", safe_exception(exc))
        return True
    lock = chat.get("agent_lock_until")
    return isinstance(lock, datetime) and lock > now


def mark_restored(store, uid, by="user"):
    """The workspace went back to a checkpoint: every chat's next message
    that uses it is told (claim), who did it too (``by``: "user", "heal"
    when it was stuck, or "replace" when it got a new computer instead,
    whose time ``replaced_at`` keeps)."""
    # The checkpoint may be from before the kit, or from the middle of its
    # installation, and from before this version's tools; also when the note
    # below cannot be written.
    forget_kit(uid)
    _ready.discard(agent_vm.workspace_name(uid))
    workspace = ref(store.db, uid)

    def operation(tx):
        snapshot = workspace.get(transaction=tx)
        if snapshot.exists:
            now = _now()
            tx.update(workspace, {"restores": int((snapshot.to_dict() or {}).get("restores") or 0) + 1,
                                  "restored_at": now, "restored_by": by,
                                  **({"replaced_at": now} if by == "replace" else {})})
    store._transaction(operation)


def record_for_view(store, uid, *, provider):
    """The view may open the workspace before any chat used it: the VM
    recorded on the account (no lease) before the provider creates it.
    Returns the record as it was."""
    from app.services import persistence_guard
    workspace = ref(store.db, uid)
    seen = {}

    def operation(tx):
        persistence_guard.ensure_account_write_allowed(uid=uid, db=store.db, transaction=tx)
        current = workspace.get(transaction=tx).to_dict() or {}
        seen["record"] = current
        if current.get("name") != agent_vm.workspace_name(uid):
            tx.set(workspace, {**current, "provider": provider, "name": agent_vm.workspace_name(uid),
                               "created_at": current.get("created_at") or _now().isoformat()})
    store._transaction(operation)
    return seen.get("record") or {}


# The live view (routers/agent_workspace.py): one per account, the newest
# wins, and an older one ends within VIEW_CHECK_SECONDS once it sees that.
# An open view keeps the VM awake: its time counts as VM time.
VIEW_CHECK_SECONDS = 30


def claim_view(store, uid, seconds, kind="view"):
    """This view is the account's one from now on (record_for_view made the
    record): its id, which the view checks (holds_view). ``kind``: "view"
    for the browser's live view, "terminal" for the user's terminal; each
    kind has one at a time."""
    view_id = secrets.token_hex(8)
    workspace = ref(store.db, uid)

    def operation(tx):
        if workspace.get(transaction=tx).exists:
            tx.update(workspace, {kind: {"id": view_id, "until": _now() + timedelta(seconds=seconds)}})
    store._transaction(operation)
    return view_id


def holds_view(db, uid, view_id, kind="view"):
    """Whether ``view_id`` is still the account's view of that kind (no newer
    one took over). The open view asks every VIEW_CHECK_SECONDS."""
    return (record(db, uid).get(kind) or {}).get("id") == view_id


def open_workspace(vm, uid, cancellation=None, *, start=None, db=None, timeout=None):
    """The account's VM for whatever needs it (a message's start, the
    browser's warm-up, the view, the terminal, the provisioning): created
    with the network rules where nothing made it yet, its tools and the
    agent's user up to date (prepare), under the setup lock; its name.
    ``start`` (a Start) learns what the start has to do: the setup of a VM
    made just now, which the browser's own installation follows (the
    browser's caller says when that begins, Start.next), else how it wakes
    (the provider's status, a hint only: a
    VM that just ran may say "cold" too). ``db``: an older browser VM of its
    own goes once the workspace is ready (retire_old_browser). ``timeout``: at
    most this long for a setup (prepare). A VM the gateway called
    unresponsive before raises at once, or once its probe did not reach it
    (reachable); one that does so now is asked again right after, and
    restores itself when it is stuck (heal_later, with ``db``). One whose
    probe finds it deleted is made anew like any that is not there (_gone).
    A VM this process brought up to date and reached a moment ago is asked
    nothing (_ready): its next request wakes it."""
    name = agent_vm.workspace_name(uid)
    if name in _ready and agent_vm.reached_within(name, agent_vm.WAKE_AFTER_SECONDS):
        return name
    stuck = None if db is None else (lambda: heal_later(db, uid))

    def gone():
        _gone(uid)
    lock = setup_lock(name)
    while not lock.acquire(timeout=.2):
        if cancellation is not None:
            cancellation.raise_if_cancelled()
    try:
        reachable(name, cancellation, timeout, on_unresponsive=stuck, on_gone=gone)
        try:
            # A VM made just now has no version yet: prepare sets its rules.
            created = vm.ensure(name)
            if created:
                # A VM made anew (after one deleted by hand) has no kit.
                forget_kit(uid)

            def setting_up():
                if created:
                    start.phase("setup", then="install")
                else:
                    start.phase("update")
            if start is not None:
                phase = {"cold": "cold", "warm": "warm"}.get(getattr(vm, "statuses", {}).get(name))
                if created:
                    setting_up()
                elif phase:
                    start.phase(phase)
            prepare(vm, name, cancellation, timeout=timeout, on_setup=None if start is None else setting_up)
            _ready.add(name)
        except agent_vm.VMUnavailable as exc:
            _ready.discard(name)
            if stuck is not None and agent_vm.unresponsive(exc):
                agent_vm.watch(name, stuck, on_gone=gone)
            raise
    finally:
        lock.release()
    if db is not None:
        retire_old_browser(db, uid, vm)
    return name


# The VMs this process found at its VERSION (open_workspace). Opening one
# costs two requests before the first that does anything (the provider's
# record of it, the version on its disk), each a round trip the user waits
# for when the live view opens right after the warm-up or a message. While
# the VM was reached within agent_vm.WAKE_AFTER_SECONDS both are known. A
# restore brings back an older disk (mark_restored forgets it); a VM deleted
# by hand in that time fails its next request, which opens it anew.
_ready: set[str] = set()


def _gone(uid):
    """The account's VM is gone (deleted, here or outside this process):
    what this process knew of it holds for none made after it, neither that
    its tools are up to date nor that it has its kit."""
    _ready.discard(agent_vm.workspace_name(uid))
    forget_kit(uid)


def reachable(name, cancellation=None, timeout=None, on_unresponsive=None, on_gone=None):
    """Raises VMUnavailable with the gateway's status while ``name`` is
    marked unresponsive (agent_vm.mark_unresponsive): the browser's warm-up
    and the workbench of one message, and every message after, would each
    wait about 48 s for the same 502 (prod 2026-11-06). Waits
    only for the VM's probe, at most PROBE_WAIT_SECONDS (and ``timeout``),
    so a VM that woke again is used again by the start that asked, and one
    that was deleted meanwhile is made anew by it.
    ``on_unresponsive``: what the probe calls when the VM answers so again;
    ``on_gone``: when the provider has none under the name any more."""
    if agent_vm.unresponsive_status(name) is None:
        return
    probe = agent_vm.probe(name, on_unresponsive=on_unresponsive, on_gone=on_gone)
    if probe is not None:
        limit = agent_vm.PROBE_WAIT_SECONDS if timeout is None else min(agent_vm.PROBE_WAIT_SECONDS, timeout)
        deadline = time.monotonic() + max(0.0, limit)
        while probe.is_alive() and time.monotonic() < deadline:
            if cancellation is not None:
                cancellation.raise_if_cancelled()
            probe.join(.2)
    status = agent_vm.unresponsive_status(name)
    if status is not None:
        raise agent_vm.VMUnavailable(f"unresponsive: HTTP {status}", status)


# Accounts whose older browser VM is gone (or never was), in this process.
_retired: set[str] = set()


def retire_old_browser(db, uid, vm):
    """An older browser VM of its own goes once the account's
    workspace runs (Max: the sign-ins are made again once): deleted by its
    name, then the record forgets it, and the list of sign-ins with it
    (sign_ins), since none of them holds on the new browser. Only where the
    record still names it; a failure leaves it for the next start (the
    account's deletion takes it in any case, agent_vm.delete_workspace)."""
    if uid in _retired:
        return
    try:
        if record(db, uid).get("browser"):
            delete_old_browser(db, uid, vm)
            clear_sign_ins(db, uid)
            logging.info("Agent workspace old browser VM deleted")
        _retired.add(uid)
    except Exception as exc:
        logging.warning("Agent workspace old browser VM not deleted category=%s", safe_exception(exc))


def delete_old_browser(db, uid, vm):
    """The older browser VM, with the profile and every
    sign-in it kept, by its name whatever the record says (a VM that is gone
    counts as deleted), then the record forgets it. Also "Log out
    everywhere" (routers/agent_workspace.py): an account that has not opened
    its workspace may still have that VM, and then no record to change."""
    vm.delete(agent_vm.old_browser_name(uid))
    _merge(db, uid, lambda record: {"browser": None} if record.get("browser") else None)


# The account's provisioning (module docstring): once per process and account.
_provisioned: set[str] = set()


def provisioning():
    """AGENT_WORKSPACE_PROVISION=off: no workspace before it is needed (the
    test suite's default, whose fake VMs count their calls)."""
    import os
    return os.getenv("AGENT_WORKSPACE_PROVISION", "").strip().lower() != "off"


def provision(store, uid, *, factory=None):
    """A new account's workspace before it is needed (the module's
    docstring): the VM made and set up in the background, the
    browser's Chrome started once and then told to rest (the helper's warm
    and rest, as after a message), unless a message uses it by then
    (_provision). Only a VM that is not there: where the
    account's record names none yet nothing ever opened one, else it may be
    gone (deleted by hand). And only while the server's safety rules leave
    the workspace open. Called with the account's messages to the agent that
    may use the workspace (routers/agent.py); asks the record once per
    process and account, on a thread of its own, so the message never waits
    for it. Returns the thread, or None."""
    if not provisioning() or uid in _provisioned:
        return None
    _provisioned.add(uid)
    thread = threading.Thread(target=_provision_new, args=(store, uid, factory or agent_vm.backend),
                              name="agent-workspace-provision", daemon=True)
    thread.start()
    return thread


def _provision_new(store, uid, factory):
    try:
        from app.services import workspace_guard
        if workspace_guard.status(uid).closed:
            return
        vm = factory()
        if vm is None:
            return
        try:
            new = _record_new(store, uid, vm.provider)
            needed = new or not vm.exists(agent_vm.workspace_name(uid))
        finally:
            vm.close()
        if not needed:
            return
    except Exception as exc:
        logging.warning("Agent workspace provision not started category=%s", safe_exception(exc))
        return
    _provision(store, uid, factory)


def _record_new(store, uid, provider):
    """Names the VM on the account's record where it names none yet (the
    account's deletion finds it from then on, as record_for_view); whether
    it did."""
    from app.services import persistence_guard
    workspace = ref(store.db, uid)
    made = {}

    def operation(tx):
        persistence_guard.ensure_account_write_allowed(uid=uid, db=store.db, transaction=tx)
        current = workspace.get(transaction=tx).to_dict() or {}
        made["new"] = not current.get("name")
        if made["new"]:
            tx.set(workspace, {**current, "provider": provider, "name": agent_vm.workspace_name(uid),
                               "created_at": current.get("created_at") or _now().isoformat()})
    store._transaction(operation)
    return made["new"]


def _provision(store, uid, factory):
    """The VM set up and its browser started once, then told to rest;
    failures are only logged: the first call that needs it sets up what is
    missing. A message that uses the workspace by then keeps the hold of its
    browser calls (the rest would shorten it to two minutes, and a longer
    pause of the agent would let the VM sleep under it); the message rests
    at its own end (agent_browser._rest), and the kit comes after it too
    (kit_later), so its installation never runs beside the agent's own."""
    from app.services import agent_browser
    from app.services.llm.provider_runtime import ProviderCancellation
    start, vm, began = Start(uid, "browser").phase("setup", then="install"), None, time.monotonic()
    try:
        vm = factory()
        name = open_workspace(vm, uid, db=store.db)
        start.next()
        agent_browser.helper(vm, name, {"action": "warm"}, agent_browser.CALL_SECONDS, ProviderCancellation())
        idle = not in_use(store, uid)
        if idle:
            agent_browser.helper(vm, name, {"action": "rest"}, agent_browser.REST_SECONDS, ProviderCancellation())
        logging.info("Agent workspace provisioned seconds=%.1f", time.monotonic() - began)
        if idle:
            kit_later(uid, factory=factory)
    except Exception as exc:
        logging.warning("Agent workspace provision failed category=%s", safe_exception(exc))
    finally:
        start.end()
        if vm is not None:
            vm.close()


# The warm-up before the user opens the workspace
# (routers/agent_workspace.py warm_workspace). A VM that slept takes its
# wake and Chrome's start before the live view shows a picture (15 to 30 s
# from cold), and one the provider does not start at all is found only then
# (prod 2026-11-20: 49 s of a progress bar, then "not reachable"). So the
# app asks for the VM while the user is still elsewhere in it: when it
# loads, while they use it, and when they reach for the workspace's button
# (``intent``). The VM is woken, its tools brought up to date, its Chrome
# started and held awake until past the app's next asking (the helper's
# warm and rest, browser.py WARM_FOR): a VM that paused in between took
# 6.6 s to take the view's connection, a running one 0.3 s (test Sprite
# 2026-11-20). A VM that does not start is restored before the user asks for it
# (open_workspace, heal_later). Never a VM that is not there (a warm-up
# makes none), never past the day's VM time or the safety rules, and
# without the user's hand on the button only for an account that opened
# the view or the terminal before: most accounts with a VM never do, and
# every wake is paid for. WARM_EVERY_SECONDS and WARMS_PER_DAY bound what
# an open tab can cost.
WARM_EVERY_SECONDS = 240
WARMS_PER_DAY = 150
WARM_SECONDS = 120
# Per account in this process: when its last warm-up began (time.monotonic),
# the UTC day and how many began on it, and whether one runs.
_warms: dict[str, dict] = {}
_warms_lock = threading.Lock()


def warming_on():
    """AGENT_WORKSPACE_WARM=off: no warm-up before the workspace is opened."""
    import os
    return os.getenv("AGENT_WORKSPACE_WARM", "").strip().lower() != "off"


def warm_later(store, uid, *, intent=False, factory=None):
    """The account's warm-up on a thread of its own, unless one runs, the
    last began within WARM_EVERY_SECONDS or the day's WARMS_PER_DAY are
    used. ``intent``: the user reaches for the workspace now. Returns the
    thread, or None."""
    if not warming_on():
        return None
    now, day = time.monotonic(), _now().date().isoformat()
    with _warms_lock:
        seen = _warms.get(uid) or {}
        count = seen.get("count", 0) if seen.get("day") == day else 0
        if seen.get("running") or count >= WARMS_PER_DAY:
            return None
        if seen.get("at") is not None and now - seen["at"] < WARM_EVERY_SECONDS:
            return None
        _warms[uid] = {"at": now, "day": day, "count": count + 1, "running": True}
    thread = threading.Thread(target=_warm, args=(store, uid, intent, factory or agent_vm.backend),
                              name="agent-workspace-warm", daemon=True)
    thread.start()
    return thread


def _warm(store, uid, intent, factory):
    from app.services import agent_browser, agent_vm_time, workspace_guard
    from app.services.llm.provider_runtime import ProviderCancellation
    vm, began, passed = None, time.monotonic(), False
    try:
        # A new computer on its way (replace) starts its browser itself.
        if replacing(uid) or workspace_guard.status(uid).closed:
            return
        current = record(store.db, uid)
        if current.get("name") != agent_vm.workspace_name(uid):
            return
        if not intent and not (current.get("view") or current.get("terminal")):
            # Not this account's turn yet: its first reach for the button is not held up by this.
            passed = True
            return
        # A message has it: awake already, and its own calls hold it. Nor
        # while the user has the browser: the start looks at Chrome and
        # would restart one that is slow to answer, under their hands.
        if _held_by_other(current.get("lease"), None, _now()) or control_of(current)[0]:
            return
        limit = agent_vm_time.daily_limit(uid)
        if limit is not None and agent_vm_time.used(store.db, uid) >= limit:
            return
        vm = factory()
        if vm is None:
            return
        name = open_workspace(vm, uid, db=store.db)
        agent_browser.helper(vm, name, {"action": "warm"}, WARM_SECONDS, ProviderCancellation())
        # As in _provision: a message that began meanwhile keeps its hold.
        # "for": "view" leaves the VM awake past the app's next asking
        # (browser.py WARM_FOR, longer than WARM_EVERY_SECONDS).
        if not in_use(store, uid):
            agent_browser.helper(vm, name, {"action": "rest", "for": "view"}, agent_browser.REST_SECONDS,
                                 ProviderCancellation())
        logging.info("Agent workspace warmed seconds=%.1f intent=%s", time.monotonic() - began, bool(intent))
    except Exception as exc:
        logging.info("Agent workspace warm-up failed category=%s", safe_exception(exc))
    finally:
        with _warms_lock:
            if uid in _warms:
                _warms[uid]["running"] = False
                if passed:
                    _warms[uid]["at"] = None
        if vm is not None:
            vm.close()


def _quiet(stream, chunk):
    pass


def _current(vm, name, version):
    try:
        raw, _ = vm.read_file(name, VERSION_PATH, limit=64, agent=False)
    except agent_vm.VMFileMissing:
        raw = b""
    return raw.decode("utf-8", "replace").strip() == version


class SetupFailed(agent_vm.VMUnavailable):
    """setup.sh did not succeed: no command of the agent may run there
    (a refusal of the workbench, not a broken connection)."""


def prepare(vm, name, cancellation=None, timeout=None, on_setup=None):
    """The VM at this VERSION, only when the version there differs (else
    one read): its network rules (agent_vm.RULES, the open web), its tools
    written to the provider's home, the live view's former gateway service
    removed, and setup.sh run as root
    (the agent's user and its /tmp, the tools every workspace has; once, the
    moves from the layouts before). Returns whether it wrote them; raises
    SetupFailed when the setup failed, so no command runs with the
    provider's rights. ``timeout``: at most this long for the setup (the
    time the message has left before its answer). ``on_setup``: called when
    the setup is about to run (the start's phase)."""
    from app.services.llm.provider_runtime import ProviderCancellation
    if _current(vm, name, VERSION):
        return False
    if on_setup is not None:
        on_setup()
    vm.set_policy(name, agent_vm.RULES)
    for file, data in tool_files().items():
        vm.write_file(name, f"{WORKSPACE_DIR}/{file}", data, agent=False)
    vm.delete_service(name, OLD_GATEWAY_SERVICE)
    said = []
    seconds = SETUP_SECONDS if timeout is None else max(1, min(SETUP_SECONDS, int(timeout)))
    outcome = vm.exec(name, f"sudo -n bash {WORKSPACE_DIR}/setup.sh", cwd=agent_vm.SERVER_HOME,
                      timeout=seconds, on_output=lambda stream, chunk: said.append(chunk),
                      cancellation=cancellation or ProviderCancellation(), agent=False)
    if outcome.exit_code != 0:
        logging.warning("Agent workspace setup failed exit=%s", outcome.exit_code)
        raise SetupFailed("setup")
    vm.write_file(name, VERSION_PATH, VERSION.encode(), agent=False)
    return True


# The kit: what the agent kept installing before it could work. 14 of 46
# messages with the workspace began with an installation (Prod 2026-10-20
# to 11-10), and `apt install ffmpeg` took 39 s of one: to Max the
# workspace seemed to start for a minute each time. So ffmpeg and the
# Python packages for charts, pictures, tables, PDFs, Office files and a
# page's check are on every workspace (AGENT_VM_PROMPT names them). Small
# on purpose: a VM's disk is paid for each account for good (the kit is
# 668 MB and installs in 49 s, test Sprite 2026-11-10), so what only a few
# need stays the agent's own installation. The Python packages go where the
# agent's own pip puts them, its site folder: that outlasts a new Python
# patch release of the provider's image (/.sprite/languages is a layer of
# its own), no root runs a package's code, and the agent updates them like
# its own.
KIT_APT = ("ffmpeg",)
KIT_PYTHON = ("pillow", "numpy", "pandas", "matplotlib", "pypdf", "python-docx", "openpyxl", "python-pptx",
              "playwright")
# What of the kit is missing, as the agent's user sees it, one "apt <name>"
# or "python <name>" a line: a package by dpkg's status, a Python package by
# its metadata, which a wheel unpacks last, so a folder half written (a
# checkpoint taken during the installation, then restored) counts as missing.
_KIT_PYTHON_CHECK = ("import sys\nfrom importlib import metadata\nfor name in sys.argv[1:]:\n    try:\n"
                     "        metadata.version(name)\n    except Exception:\n        print('python', name)\n")
KIT_CHECK = ("for name in " + " ".join(KIT_APT) + "; do [ \"$(dpkg-query -W -f='${Status}' \"$name\" 2>/dev/null)\" "
             "= 'install ok installed' ] || echo \"apt $name\"; done; python3 -c "
             + shlex.quote(_KIT_PYTHON_CHECK) + " " + " ".join(KIT_PYTHON))
# No cache: the wheels would lie in the agent's home a second time.
KIT_PIP = "python3 -m pip install --user --quiet --no-input --no-cache-dir --disable-pip-version-check {packages}"
KIT_CHECK_SECONDS = 60
KIT_SECONDS = 300
# An account's kit is looked at once per process (kit_later); one that
# failed, again with a later message, this often at most. _kits: "done" or
# the failures so far; _kits_running: whether the VM changed under a look
# still running (forget_kit), whose outcome then says nothing.
KIT_TRIES = 3
_kits: dict[str, object] = {}
_kits_running: dict[str, bool] = {}
_kits_lock = threading.Lock()


def kit_on():
    """AGENT_WORKSPACE_KIT=off: no kit (the test suite's default, whose fake
    VMs count their calls, and the switch should an installation ever harm
    a workspace)."""
    import os
    return os.getenv("AGENT_WORKSPACE_KIT", "").strip().lower() != "off"


def kit_missing(vm, name, cancellation=None):
    """``(apt, python)``: the kit's packages the VM lacks (KIT_CHECK)."""
    from app.services.llm.provider_runtime import ProviderCancellation
    out = bytearray()

    def keep(stream, chunk):
        if stream == "stdout" and len(out) < 4096:
            out.extend(chunk)
    outcome = vm.exec(name, KIT_CHECK, cwd=HOME, timeout=KIT_CHECK_SECONDS, on_output=keep,
                      cancellation=cancellation or ProviderCancellation())
    if outcome.exit_code != 0:
        raise agent_vm.VMUnavailable(f"kit check: exit {outcome.exit_code}")
    said = [line.split() for line in out.decode("ascii", "replace").splitlines()]
    return (tuple(name for name in KIT_APT if ["apt", name] in said),
            tuple(name for name in KIT_PYTHON if ["python", name] in said))


def install_kit(vm, name, cancellation=None):
    """Installs what of the kit the VM lacks: the apt packages as root, the
    way vm_install_packages does (its command never removes a package, so
    the browser's Chrome stays), the Python packages as the agent's user.
    Returns ``(apt, python)``, the names it installed; raises VMUnavailable
    when a step failed, after it tried the other."""
    from app.services.agent_vm_tools import INSTALL_COMMAND, INSTALL_TIMEOUT
    from app.services.llm.provider_runtime import ProviderCancellation
    cancellation = cancellation or ProviderCancellation()
    apt, python = kit_missing(vm, name, cancellation)
    failed = []
    if apt:
        outcome = vm.exec(name, INSTALL_COMMAND.format(packages=" ".join(apt)), cwd=agent_vm.SERVER_HOME,
                          timeout=INSTALL_TIMEOUT, on_output=_quiet, cancellation=cancellation, agent=False)
        if outcome.exit_code != 0:
            failed.append(f"apt exit {outcome.exit_code}")
    if python:
        outcome = vm.exec(name, KIT_PIP.format(packages=" ".join(python)), cwd=HOME, timeout=KIT_SECONDS,
                          on_output=_quiet, cancellation=cancellation)
        if outcome.exit_code != 0:
            failed.append(f"pip exit {outcome.exit_code}")
    if failed:
        raise agent_vm.VMUnavailable("kit: " + ", ".join(failed))
    return apt, python


def kit_later(uid, *, factory=None):
    """The account's kit on a thread of its own, where this process has not
    seen it complete yet: after the account's provisioning and after a
    message that used the workbench (VMSession._finish), so the
    installation runs beside no command of the agent's and no start waits
    for it. Never while the server's safety rules have closed the
    workspace. Returns the thread, or None."""
    if not kit_on():
        return None
    with _kits_lock:
        state = _kits.get(uid, 0)
        if uid in _kits_running or state == "done" or state >= KIT_TRIES:
            return None
        _kits_running[uid] = False
    thread = threading.Thread(target=_kit, args=(uid, factory or agent_vm.backend, state),
                              name="agent-workspace-kit", daemon=True)
    thread.start()
    return thread


def _kit(uid, factory, failures):
    vm, done, began = None, False, time.monotonic()
    try:
        from app.services import workspace_guard
        if workspace_guard.status(uid).closed:
            return
        vm = factory()
        if vm is None:
            return
        apt, python = install_kit(vm, agent_vm.workspace_name(uid))
        done = True
        if apt or python:
            logging.info("Agent workspace kit installed seconds=%.1f apt=%d python=%d", time.monotonic() - began,
                         len(apt), len(python))
    except Exception as exc:
        logging.warning("Agent workspace kit failed category=%s", safe_exception(exc))
    finally:
        with _kits_lock:
            if not _kits_running.pop(uid, False):
                _kits[uid] = "done" if done else failures + 1
        if vm is not None:
            vm.close()


def forget_kit(uid):
    """The VM may lack its kit again (restored to a checkpoint, made anew):
    the next message's end looks."""
    with _kits_lock:
        _kits.pop(uid, None)
        if uid in _kits_running:
            _kits_running[uid] = True


# Makes the chat's folder (as the agent's user, with the folders the file
# needs), where commands start, and names its chat there. The folder is
# named after the chat's title (agent_vm.chat_folder), so
# `ls ~/chats` already says which is which; .consens-chat adds title, start
# and id.
CHAT_MARKER = ".consens-chat"
TITLE_CHARS = 200


# A temporary chat's folder and marker name no title:
# the workspace is every chat's, and its title is the user's question.
TEMPORARY_FOLDER_TITLE = "temporary"
TEMPORARY_MARKER = ("This folder holds the files of a temporary chat; it is deleted when the user leaves that "
                    "chat, and other chats leave it alone.")


def chat_marker(chat_id, title="", started="", *, temporary=False):
    title = "(temporary chat)" if temporary else " ".join(str(title or "").split())[:TITLE_CHARS] or "(untitled)"
    note = TEMPORARY_MARKER if temporary else "This folder holds the files of that chat; it is deleted with the chat."
    return f"chat: {title}\nstarted: {started or 'unknown'}\nid: {chat_id}\n{note}\n".encode("utf-8")


def wanted_folder(chat_id, title="", *, temporary=False):
    """The folder's name that the chat's title asks for (agent_vm.chat_folder)."""
    return agent_vm.chat_folder(TEMPORARY_FOLDER_TITLE if temporary else title, chat_id)


def record_folder(store, uid, chat_id, folder):
    """The chat names its folder (chat field ``agent_vm.folder``): its
    deletion finds it there (agent_vm.delete_chat_vm), the next message
    renames from there. Written after the move, so a failed move never
    leaves the chat pointing at a folder that does not exist; a failed
    write only means the next message moves nothing and writes it again."""
    chat = store._chat_ref(uid, chat_id)

    def operation(tx):
        data = chat.get(transaction=tx).to_dict() or {}
        used = data.get("agent_vm") if isinstance(data.get("agent_vm"), dict) else None
        if data.get("status") == "active" and used is not None:
            tx.update(chat, {"agent_vm": {**used, "folder": folder}})
    try:
        store._transaction(operation)
    except Exception as exc:
        logging.warning("Agent chat folder not recorded category=%s", safe_exception(exc))


# The keys in ~/.secrets as the agent's user ("key" name NUL value NUL):
# the record's names first ("$@"), then every other file of a key's name, at
# most $most (the record keeps only the newest names, and an older key would
# go unmasked).
KEYS_PART = (
    'if cd "$HOME/.secrets" 2>/dev/null; then count=0; named=$#; seen=" "; for name in "$@" *; do '
    'if [ "$named" -gt 0 ]; then named=$((named - 1)); seen="$seen$name "; '
    'else case $seen in *" $name "*) continue;; esac; fi; '
    '[[ $name =~ ^[A-Z][A-Z0-9_]{1,63}$ ]] && [ -f "$name" ] && [ -r "$name" ] || continue; '
    '[ "$count" -lt "$most" ] || break; count=$((count + 1)); '
    'printf "key %s\\0" "$name"; head -c 16384 -- "$name"; printf "\\0"; done; fi; ')
# A message's chat on the workbench in one command (the move, the marker,
# the notes and the keys, not one round trip each), as the agent's user: the
# chat's folder follows its title ($1 the folder now, $2 the one its title wants;
# "taken" keeps it where it is), its marker comes on stdin, then the keys
# (KEYS_PART, at most $5, the record's names from $6), and last the notes'
# beginning ($3, at most $4 bytes, to the end).
CHAT_SCRIPT = (
    'old=$1; new=$2; notes=$3; limit=$4; most=$5; shift 5; dir=$old; state=same; '
    'if [ "$new" != "$old" ]; then '
    'if [ ! -e "$old" ] && [ ! -L "$old" ]; then dir=$new; state=missing; '
    'elif [ -e "$new" ] || [ -L "$new" ]; then state=taken; '
    'elif mkdir -p -- "$(dirname -- "$new")" && mv -T -- "$old" "$new"; then dir=$new; state=moved; '
    'else state=failed; fi; fi; '
    'mkdir -p -- "$dir" 2>/dev/null && cat > "$dir/' + CHAT_MARKER + '" 2>/dev/null || exit 46; '
    'printf "folder %s\\n" "$state"; ' + KEYS_PART +
    'if [ -f "$notes" ] && [ -r "$notes" ]; then printf "notes +\\n"; exec head -c "$limit" -- "$notes"; fi; '
    'printf "notes -\\n"')
CHAT_SECONDS = 60
# The keys alone (read_keys): at most $1, the record's names from $2.
KEYS_SCRIPT = 'most=$1; shift 1; ' + KEYS_PART + 'exit 0'
KEYS_SECONDS = 30


@dataclass(frozen=True)
class ChatOpened:
    folder: str
    notes: dict
    keys: tuple
    seconds: float


def parse_chat(raw):
    """``(state, keys, notes)`` of CHAT_SCRIPT's output: the folder's
    state, ``(name, value)`` pairs and the notes' bytes (None: no notes).
    A value loses its surrounding whitespace, as agent_secrets.save takes
    it: a key file edited since (an editor's line break at its end) would
    be masked only together with that line break."""
    head, _, rest = raw.partition(b"\n")
    if not head.startswith(b"folder "):
        raise agent_vm.VMUnavailable("chat: unreadable")
    state = head[7:].decode("ascii", "replace")
    keys, rest = _parse_keys(rest)
    if rest.startswith(b"notes +\n"):
        return state, keys, rest[8:]
    if rest.startswith(b"notes -"):
        return state, keys, None
    raise agent_vm.VMUnavailable("chat: unreadable")


def _parse_keys(raw):
    """KEYS_PART's ``(name, value)`` pairs at the start of ``raw``, and the rest."""
    keys = []
    while raw.startswith(b"key "):
        name, _, raw = raw[4:].partition(b"\0")
        value, _, raw = raw.partition(b"\0")
        keys.append((name.decode("ascii", "replace"), value.decode("utf-8", "replace").strip()))
    return keys, raw


# A temporary chat reads the notes and leaves them as they are: they
# outlast it (agent_vm_tools.VMTools._notes_kept).
NOTES_TEMPORARY = "This temporary chat leaves the notes as they are: they outlast it."
NOTES_NONE_TEMPORARY = "No notes yet, and this temporary chat starts none: they would outlast it."


def notes_for_agent(raw, *, temporary=False):
    """The beginning of the workspace's notes for the agent (``raw``, None:
    there are none), or that there are none yet: ``{"path", "text", "more"}``.
    Data, never instructions (AGENT_VM_PROMPT). ``temporary``: for a
    temporary chat, which only reads them."""
    if raw is None:
        return {"path": NOTES_PATH, "text": "",
                "note": NOTES_NONE_TEMPORARY if temporary else "No notes yet: start them when something lasting comes up."}
    text = raw.decode("utf-8", "replace")
    notes = {"path": NOTES_PATH, "text": text[:NOTES_CHARS]}
    if len(raw) >= NOTES_CHARS * 4 or len(text) > NOTES_CHARS:
        notes["more"] = (f"The notes go on: read the rest with vm_read_file {NOTES_PATH}"
                         + ("." if temporary else ", and keep them shorter."))
    if temporary:
        notes["note"] = NOTES_TEMPORARY
    return notes


def open_chat(vm, name, chat_id, *, title="", started="", folder="", keys=(), cancellation=None, temporary=False):
    """At a message's first workbench call: the chat's folder follows its
    title (``folder``: the name the chat recorded, empty for an older
    chat's folder named by its id, which moves too) with its marker
    rewritten, the account's keys read again for masking (every key file in
    ~/.secrets, ``keys``: the record's names, first; CHAT_SCRIPT) and the
    notes' beginning (notes_for_agent), in one command. Returns ChatOpened:
    the folder's name now, the old one when the new name is taken or the
    move failed."""
    from app.services import agent_secrets
    from app.services.llm.provider_runtime import ProviderCancellation
    wanted = wanted_folder(chat_id, title, temporary=temporary)
    old = agent_vm.chat_dir(chat_id, folder or None)
    names = [key for key in dict.fromkeys(keys) if agent_secrets.NAME.fullmatch(str(key))][:agent_secrets.KEEP_NAMES]
    out = bytearray()
    limit = NOTES_CHARS * 4
    most = agent_secrets.READ_KEYS
    cap = limit + most * (agent_secrets.VALUE_CHARS + 80) + 256

    def keep(stream, chunk):
        if stream == "stdout" and len(out) <= cap:
            out.extend(chunk)
    outcome = vm.run(name, agent_vm.agent_argv(["bash", "-c", CHAT_SCRIPT, "chat", old,
                                                agent_vm.chat_dir(chat_id, wanted), NOTES_PATH, str(limit), str(most),
                                                *names], CHAT_SECONDS, HOME),
                     cwd="/", timeout=CHAT_SECONDS, on_output=keep, cancellation=cancellation or ProviderCancellation(),
                     input=chat_marker(chat_id, title, started, temporary=temporary))
    if outcome.exit_code != 0:
        raise agent_vm.VMUnavailable(f"chat: exit {outcome.exit_code}")
    state, found, notes = parse_chat(bytes(out))
    # The script's own check of a name is the shell's, in the VM's locale.
    found = [(key, value) for key, value in found if agent_secrets.NAME.fullmatch(key)][:most]
    return ChatOpened(folder=wanted if state in {"moved", "missing", "same"} else folder,
                      notes=notes_for_agent(notes, temporary=temporary),
                      keys=tuple(found), seconds=outcome.seconds)


def read_keys(vm, name, keys=(), *, cancellation=None, timeout=KEYS_SECONDS):
    """The account's keys for masking (agent_secrets.scrub) where no start
    of the workbench reads them (open_chat): every key file in ~/.secrets,
    ``keys`` (the record's names) first, as ``(name, value)`` pairs."""
    from app.services import agent_secrets
    from app.services.llm.provider_runtime import ProviderCancellation
    names = [key for key in dict.fromkeys(keys) if agent_secrets.NAME.fullmatch(str(key))][:agent_secrets.KEEP_NAMES]
    most = agent_secrets.READ_KEYS
    cap = most * (agent_secrets.VALUE_CHARS + 80) + 256
    out = bytearray()

    def keep(stream, chunk):
        if stream == "stdout" and len(out) <= cap:
            out.extend(chunk)
    seconds = max(1, int(timeout))
    outcome = vm.run(name, agent_vm.agent_argv(["bash", "-c", KEYS_SCRIPT, "keys", str(most), *names], seconds, HOME),
                     cwd="/", timeout=seconds, on_output=keep, cancellation=cancellation or ProviderCancellation())
    if outcome.exit_code != 0:
        raise agent_vm.VMUnavailable(f"keys: exit {outcome.exit_code}")
    found, rest = _parse_keys(bytes(out))
    if rest:
        raise agent_vm.VMUnavailable("keys: unreadable")
    # The script's own check of a name is the shell's, in the VM's locale.
    return tuple((key, value) for key, value in found if agent_secrets.NAME.fullmatch(key))[:most]


def control_payload(holder, *, now=None):
    """control.json: the user's takeover with its expiry, or the agent's turn."""
    until = (now or time.time()) + CONTROL_SECONDS if holder == "user" else 0
    return json.dumps({"holder": holder, "until": until}).encode()


def set_control(db, uid, vm, holder):
    """The user takes the browser over (again at every refresh of the view)
    or hands it back. Taking over closes the server's way first (the record),
    then the browser's (control.json there); handing back opens them in the
    other order. Handing back notes when (``returned_at``): a run waiting for
    it sees a hand-back even between two of its looks (control_state)."""
    now = time.time()
    control = {"holder": holder, "until": now + CONTROL_SECONDS if holder == "user" else 0,
               **({"returned_at": now} if holder == "agent" else {})}
    payload = control_payload(holder, now=now)
    browser = agent_vm.workspace_name(uid)
    if holder == "user":
        ref(db, uid).update({"control": control})
        _forget_control(uid)
        vm.write_file(browser, BROWSER_CONTROL, payload, agent=False)
        return
    vm.write_file(browser, BROWSER_CONTROL, payload, agent=False)
    ref(db, uid).update({"control": control})
    _forget_control(uid)


def control_state(db, uid, now=None):
    """(whether the user has the workspace's browser now, when they last
    handed it back as a time.time() or 0): the record's ``control``, which
    only the server writes. A takeover the open view stopped refreshing has
    simply run out, without a hand-back."""
    return control_of(record(db, uid), now)


def control_of(workspace, now=None):
    """control_state of a record already read (routers/agent.py reads it
    once at a message's start, for the sign-ins too)."""
    control = workspace.get("control")
    if not isinstance(control, dict):
        return False, 0.0

    def number(key):
        try:
            return float(control.get(key) or 0)
        except (TypeError, ValueError):
            return 0.0
    return control.get("holder") == "user" and number("until") > (now or time.time()), number("returned_at")


# user_has_browser's answer for a moment: a call into the workspace asks
# twice right after another (the run's takeover check, then the session's
# wait), one read of the account's record each. A takeover in this process
# (set_control) forgets it at once; on the VM itself browser.py refuses to
# act while the user has it.
CONTROL_CACHE_SECONDS = 1.0
_control_seen: dict = {}
_control_lock = threading.Lock()


def _forget_control(uid):
    with _control_lock:
        for key in [key for key in _control_seen if key[1] == uid]:
            del _control_seen[key]


def user_has_browser(db, uid, now=None, fresh=False):
    """Whether the user has the workspace's browser now (control_state);
    ``fresh``: read now, as a wait for their hand-back does."""
    if now is not None or fresh:
        return control_state(db, uid, now)[0]
    key, moment = (id(db), uid), time.monotonic()
    with _control_lock:
        seen = _control_seen.get(key)
    if seen is not None and seen[0] is db and moment - seen[1] < CONTROL_CACHE_SECONDS:
        return seen[2]
    holding = control_state(db, uid)[0]
    with _control_lock:
        if len(_control_seen) > 1000:
            _control_seen.clear()
        _control_seen[key] = (db, moment, holding)
    return holding


def reset_browser(vm, uid, cancellation):
    """Ends the browser and deletes its profile: every sign-in, cookie and
    open tab. The next use starts a fresh one. A workspace that was never
    made has nothing to sign out of. As the provider's user, whose
    processes alone it ends (cdp.py names the profile too, and goes with
    Chrome)."""
    name = agent_vm.workspace_name(uid)
    if not vm.exists(name):
        return
    vm.exec(name, f"pkill -u \"$(id -u)\" -f '[u]ser-data-dir={BROWSER_PROFILE}'; sleep 1; rm -rf {BROWSER_PROFILE} "
                  f"{BROWSER_UPLOADS}", cwd=agent_vm.SERVER_HOME, timeout=60, on_output=_quiet,
            cancellation=cancellation, agent=False)


def delete_for_account(db, uid, *, factory=None):
    """With the account (account_deletion.py): the workspace's VM (and an
    older browser VM) by the names that follow from the account, so a
    record already gone never leaves the VM behind, then its record. Only a
    server without a provider skips an account
    without a record (it never made one there). The safety rules' guard
    and trail go with it (workspace_guard.py)."""
    from app.services import workspace_guard
    workspace = ref(db, uid)
    if agent_vm.configured() or factory is not None or workspace.get().exists:
        agent_vm.delete_workspace(uid, factory=factory)
    workspace.delete()
    workspace_guard.delete_for_account(db, uid)


# A message's checkpoint of the workspace (VMSession.ready; it holds the
# browser's profile too) may bring the workspace back for
# this long, and only after the last time something left it for good
# (``restore_floor``): signing the browser out everywhere or deleting a
# chat. An older checkpoint would bring the sign-ins or the chat's folder
# back. The provider keeps the checkpoints; only
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
    if isinstance(floor, datetime) and taken <= floor:
        return False
    return not any(isinstance(gap, dict) and isinstance(gap.get("from"), datetime)
                   and isinstance(gap.get("to"), datetime) and gap["from"] <= taken <= gap["to"]
                   for gap in record.get("restore_gaps") or ())


# A temporary chat's messages take no checkpoint (VMSession.ready), but
# other chats' messages may while it lives, its folder in them: only those
# may not bring it back (restore_gaps). A floor at each
# deletion would end restore for the account's whole past, and temporary
# chats are deleted whenever the user leaves one. A gap ends this much
# after the deletion, for a checkpoint still being taken then.
RESTORE_GAPS = 100
GAP_GRACE = timedelta(seconds=agent_vm.CHECKPOINT_SECONDS + 10)


def close_restore_gap(store, uid, since):
    """A temporary chat's folder left the workspace: no checkpoint taken
    from ``since`` (when the chat first claimed the workspace, its record's
    ``created_at``) to now may bring it back (restorable). Gaps past
    RESTORE_DAYS go; beyond RESTORE_GAPS, or without a readable ``since``,
    the floor rises instead (raise_restore_floor)."""
    try:
        start = datetime.fromisoformat(str(since or ""))
    except ValueError:
        start = None
    if start is None or start.tzinfo is None:
        raise_restore_floor(store, uid)
        return
    workspace = ref(store.db, uid)

    def operation(tx):
        snapshot = workspace.get(transaction=tx)
        if not snapshot.exists:
            return
        now = _now()
        kept = [gap for gap in (snapshot.to_dict() or {}).get("restore_gaps") or ()
                if isinstance(gap, dict) and isinstance(gap.get("to"), datetime)
                and gap["to"] > now - timedelta(days=RESTORE_DAYS)]
        if len(kept) >= RESTORE_GAPS:
            tx.update(workspace, {"restore_floor": now, "restore_gaps": []})
        else:
            tx.update(workspace, {"restore_gaps": [*kept, {"from": start, "to": now + GAP_GRACE}]})
    store._transaction(operation)


def record_checkpoint(db, uid, checkpoint, taken):
    """The workspace's newest checkpoint on the account's record (a
    message's, VMSession._take_checkpoint): what a stuck workspace goes back
    to (heal). ``taken``: when it began, ISO 8601 as the turn's
    ``checkpoint_at``. Best effort: without it the workspace only cannot heal."""
    at = taken.isoformat() if isinstance(taken, datetime) else str(taken)
    try:
        ref(db, uid).update({"checkpoint": {"id": str(checkpoint), "at": at}})
    except Exception as exc:
        logging.warning("Agent workspace checkpoint not recorded category=%s", safe_exception(exc))


# A stuck workspace (the gateway answered 502, 503 or 504 twice in a row,
# agent_vm.watch) goes back to its newest checkpoint
# by itself instead of staying so until a restore by hand. It loses what changed
# after that checkpoint, which a message takes before its own commands, so
# at most that message's changes; the files it shared stay in the chat.
# Only a checkpoint that may still bring the workspace back (restorable),
# never under a message (in_use: waited for, at most HEAL_WAIT_SECONDS),
# and after one that restored it not again for HEAL_SECONDS in this process.
# The restore is the stuck VM's own request and may meet the same gateway
# answer (prod 2026-11-20: 502 after 48 s): it is tried HEAL_TRIES times, and
# a heal that restored nothing may begin again after HEAL_AGAIN_SECONDS
# instead of leaving the workspace dead for the hour.
HEAL_SECONDS = 3600
HEAL_AGAIN_SECONDS = 300
HEAL_TRIES = 3
HEAL_RETRY_SECONDS = 10
HEAL_WAIT_SECONDS = 600
HEAL_POLL_SECONDS = 5
# Per account: before when (time.monotonic) no heal begins, and the one running.
_heals: dict[str, float] = {}
_healing: dict[str, threading.Thread] = {}
_heals_lock = threading.Lock()


def heal_later(db, uid, *, factory=None):
    """heal on a thread of its own, unless one runs or the last one's pause
    (HEAL_SECONDS after a restore, HEAL_AGAIN_SECONDS after none) still
    holds. Returns the thread, or None."""
    def run():
        restored = False
        try:
            restored = heal(db, uid, factory=factory) is True
        finally:
            with _heals_lock:
                _healing.pop(uid, None)
                _heals[uid] = time.monotonic() + (HEAL_SECONDS if restored else HEAL_AGAIN_SECONDS)
    with _heals_lock:
        if uid in _healing or time.monotonic() < _heals.get(uid, 0.0):
            return None
        thread = _healing[uid] = threading.Thread(target=run, name="agent-workspace-heal", daemon=True)
    thread.start()
    return thread


def healing(uid):
    """Whether a heal of the account's workspace runs now (the live view
    waits for it, routers/agent_workspace.py)."""
    with _heals_lock:
        return uid in _healing


def heal(db, uid, *, factory=None, sleep=time.sleep, clock=time.monotonic):
    """Restores the account's stuck workspace to its newest checkpoint
    (record_checkpoint) once no message uses it; every chat's next message
    is told (mark_restored, HEALED_NOTE). Returns whether it restored."""
    from app.services.agent_runs import AgentRunStore
    store = AgentRunStore(db)
    try:
        deadline = clock() + HEAL_WAIT_SECONDS
        while in_use(store, uid):
            if clock() >= deadline:
                logging.warning("Agent workspace stuck, still in use")
                return False
            sleep(HEAL_POLL_SECONDS)
        current = record(db, uid)
        latest = current.get("checkpoint") if isinstance(current.get("checkpoint"), dict) else None
        if latest is None:
            latest = _newest_turn_checkpoint(db, uid, current.get("name")) or {}
        point = {"checkpoint": latest.get("id"), "checkpoint_at": latest.get("at"), "name": current.get("name")}
        if not restorable(current, point):
            logging.warning("Agent workspace stuck without a checkpoint it may go back to")
            return False
        for attempt in range(1, HEAL_TRIES + 1):
            try:
                agent_vm.restore_workspace(uid, point["checkpoint"], factory=factory)
                break
            except agent_vm.VMUnavailable as exc:
                logging.warning("Agent workspace stuck, restore failed attempt=%d category=%s", attempt,
                                safe_exception(exc))
                if attempt == HEAL_TRIES:
                    return False
                sleep(HEAL_RETRY_SECONDS)
        mark_restored(store, uid, by="heal")
    except Exception as exc:
        logging.warning("Agent workspace stuck, restore failed category=%s", safe_exception(exc))
        return False
    logging.warning("Agent workspace was stuck and went back to its newest checkpoint")
    return True


HEAL_CHATS = 20
HEAL_TURNS = 5


def _newest_turn_checkpoint(db, uid, name):
    """The newest checkpoint a message took in the workspace ``name``, for a
    record from before record_checkpoint (2026-11-06; a stuck workspace
    takes none): of the HEAL_CHATS chats that used it last (the newest are
    those that met the stuck VM and took none: prod 2026-11-06, three of
    them), each one's newest within its newest HEAL_TURNS turns, only their
    ``agent_vm``; of those the one taken last. Not the first chat's: the
    chat that met the stuck VM may hold an old one of its own while another
    chat took a newer one since, whose work would go. None without one."""
    from google.cloud import firestore
    from google.cloud.firestore_v1.base_query import FieldFilter
    if not name:
        return None
    chats = db.collection("users").document(uid).collection("chats")
    used = []
    # Only the chats that used it (a field's own index): reads, not the whole chat list.
    for snapshot in chats.where(filter=FieldFilter("agent_vm.name", "==", name)).select(["agent_vm"]).stream():
        vm = (snapshot.to_dict() or {}).get("agent_vm")
        if isinstance(vm, dict) and vm.get("name") == name and isinstance(vm.get("used_at"), datetime):
            used.append((vm["used_at"], snapshot.id))
    found = []
    for _, chat_id in sorted(used, reverse=True)[:HEAL_CHATS]:
        turns = (chats.document(chat_id).collection("turns").order_by("position", direction=firestore.Query.DESCENDING)
                 .limit(HEAL_TURNS).select(["agent_vm"]))
        for snapshot in turns.stream():
            vm = (snapshot.to_dict() or {}).get("agent_vm")
            if isinstance(vm, dict) and vm.get("checkpoint") and vm.get("name") == name:
                at = str(vm.get("checkpoint_at") or "")
                try:
                    taken = datetime.fromisoformat(at)
                except ValueError:
                    taken = None
                # One without a readable time comes last (restorable refuses it anyway).
                if taken is None or taken.tzinfo is None:
                    taken = datetime.min.replace(tzinfo=timezone.utc)
                found.append((taken, {"id": str(vm["checkpoint"]), "at": at}))
                break
    return max(found, key=lambda pair: pair[0])[1] if found else None


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


# A stuck workspace whose restore the provider refuses as well has one way
# left: a new VM under its name (prod 2026-11-20 and 11-21: "restore: HTTP
# 502" on every try of four heals, then set up anew by hand). That costs
# every file on it, the keys the user gave the agent and the browser's
# sign-ins, so it never happens by itself: only on the user's word
# (routers/agent_workspace.py replace_workspace, which the live view offers
# once it says "stuck"), only for a VM this process knows as stuck with
# nothing left working on it (replace_refusal), never under a message, and
# once per REPLACE_SECONDS and account by the record's ``replaced_at``, which
# a restart of the server does not forget.
REPLACE_SECONDS = 3600
# How long the provider may still list the deleted VM before the new one is
# made under its name.
REPLACE_GONE_SECONDS = 60
REPLACE_GONE_POLL_SECONDS = 2
# Per account: the replacement running.
_replacing: dict[str, threading.Thread] = {}
_replacing_lock = threading.Lock()


def replace_refusal(store, uid, now=None):
    """Why the account's workspace gets no new computer now, or None:
    "unneeded" while this process does not know its VM as stuck or
    something still works on it (a probe, its watch, a heal: the view waits
    for those, routers/agent_workspace.py _repairing), "recent" within
    REPLACE_SECONDS of the last one, "running" under a chat's message."""
    name = agent_vm.workspace_name(uid)
    if agent_vm.unresponsive_status(name) is None or agent_vm.checking(name) or healing(uid):
        return "unneeded"
    now = now or _now()
    current = record(store.db, uid)
    if current.get("name") != name:
        return "unneeded"
    replaced = current.get("replaced_at")
    if isinstance(replaced, datetime) and replaced > now - timedelta(seconds=REPLACE_SECONDS):
        return "recent"
    return "running" if in_use(store, uid, now) else None


def replace_later(db, uid, *, factory=None):
    """replace on a thread of its own, unless one runs. Its Start begins
    here, so whoever asks right after is told about how long it takes
    (start_until). Returns the thread, or None."""
    def run():
        try:
            replace(db, uid, factory=factory, start=start)
        finally:
            with _replacing_lock:
                _replacing.pop(uid, None)
    with _replacing_lock:
        if uid in _replacing:
            return None
        start = Start(uid, "browser").phase("setup", then="install")
        thread = _replacing[uid] = threading.Thread(target=run, name="agent-workspace-replace", daemon=True)
    thread.start()
    return thread


def replacing(uid):
    """Whether the account's workspace gets its new computer right now (the
    live view and the terminal wait for it, routers/agent_workspace.py)."""
    with _replacing_lock:
        return uid in _replacing


def replace(db, uid, *, factory=None, start=None, sleep=time.sleep, clock=time.monotonic):
    """A new VM for the account's workspace in place of its stuck one, once
    nothing else works on it: the old one deleted with everything on it,
    the new one set up and its browser started and told to rest, its kit
    after that in the background, as for a new account (_provision). Every
    chat's next message that uses the workspace is told (REPLACED_NOTE).
    ``start``: the Start that counts it down for whoever waits, ended here.
    Returns whether the new one stands with its browser."""
    from app.services import agent_browser
    from app.services.agent_runs import AgentRunStore
    from app.services.llm.provider_runtime import ProviderCancellation
    store, name, vm, began = AgentRunStore(db), agent_vm.workspace_name(uid), None, clock()
    start = start or Start(uid, "browser").phase("setup", then="install")
    try:
        if healing(uid) or in_use(store, uid):
            logging.warning("Agent workspace not replaced, in use")
            return False
        vm = (factory or agent_vm.backend)()
        if vm is None:
            return False
        # Before the VM goes, so nothing below can fail and leave one of its
        # checkpoints in reach: the new VM numbers its own from the start
        # again, and an old id would name another disk's state there.
        raise_restore_floor(store, uid)
        vm.delete(name)
        deadline = clock() + REPLACE_GONE_SECONDS
        while vm.exists(name):
            if clock() >= deadline:
                logging.warning("Agent workspace not replaced, its VM is still there")
                return False
            sleep(REPLACE_GONE_POLL_SECONDS)
        agent_vm.forget_vm(name)
        # The old files are gone whatever happens below: the chats are told
        # from here on, not only once the new VM stands.
        mark_restored(store, uid, by="replace")
        _forget_old_vm(db, uid)
        name = open_workspace(vm, uid, db=db, start=start)
        start.next()
        agent_browser.helper(vm, name, {"action": "warm"}, agent_browser.CALL_SECONDS, ProviderCancellation())
        # As in _provision: a message that began meanwhile keeps its hold,
        # and the kit comes at its end.
        if not in_use(store, uid):
            agent_browser.helper(vm, name, {"action": "rest", "for": "view"}, agent_browser.REST_SECONDS,
                                 ProviderCancellation())
            kit_later(uid, factory=factory)
    except Exception as exc:
        logging.warning("Agent workspace replace failed category=%s", safe_exception(exc))
        return False
    finally:
        start.end()
        if vm is not None:
            vm.close()
    logging.warning("Agent workspace was stuck and got a new VM seconds=%.1f", clock() - began)
    return True


def _forget_old_vm(db, uid):
    """What the record lists of a VM that is gone: the sites its browser was
    logged in to and the names of the keys the user gave the agent, whose
    files lay there. A record without either stays as it is."""
    _merge(db, uid, lambda record: {field: [] for field in ("sign_ins", "secret_names") if record.get(field)} or None)

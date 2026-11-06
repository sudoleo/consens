"""The account's workspace (since 2026-10-27, docs/agent-mode.md "Workspace"):
one Linux VM for all of an account's chats and its user, like a colleague's
computer with its browser (agent_vm.workspace_name). The agent works there
as a user of its own (agent_vm_tools.py); Chrome runs there as the
provider's user, which the user watches and steers live
(routers/agent_workspace.py, workspace-view.js) and the agent uses through
the ``browser`` tool (agent_browser.py). localhost in that browser is the
agent's own servers, no tunnel between them.

From 2026-10-27 to 2026-11-04 the browser had a VM of its own and the
workbench reached only the package registries (security audit 2026-10-27,
Max's option A). Every feature between them needed a bridge (a localhost
tunnel, uploads and downloads copied from VM to VM, warm-ups of two VMs),
each bridge a rule of its own, and the agent still sent a key of
~/.secrets through the browser's upload (Max, 2026-11-04: "Sudo ist um
einiges sicherer als eine von uns implementierte Sicherheitslayer"). Since
then one VM, and what the agent must not reach it cannot reach by the
computer's own means: Unix users and file modes. Chrome's protocol is a
socket in the provider's home (workspace_vm/browser/cdp.py, no TCP port),
its screen asks for a cookie from there and starts only on its own socket
(display.sh), and the agent's commands have a /tmp of their own
(agent-run). The network is open for the whole VM, as it was for the
browser (agent_vm.RULES, Max's decision). What a key the user gave the agent
can do, the agent can do with it: that holds on any computer.

Record and lease: ``users/{uid}/chat_state/agent_workspace`` names the VM
before the provider creates it, so the account's deletion always finds it,
and leases the workspace to one chat's message at a time (``lease``: chat,
turn, until). A lease ends with its message (release) or by itself
LEASE_SECONDS after its last VM call, so a run that died never blocks the
workspace. The user's live view takes no lease: it is their computer. A
record that still names the browser VM of before (``browser``) has it
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
browser.py refuses to act. What already runs of the agent goes on: from
2026-10-27 to 2026-10-29 pause.py froze it, from the time the browser lived
on the workbench without users of its own, where the agent's processes could
have watched the user type. Now they reach neither the screen nor Chrome,
and the agent's server must answer the browser while the user tries the
agent's app. The reviewers follow what the agent does, never what the user
does.

A new account's workspace (provision, since 2026-11-02): its first setup
installs Chrome, its screen and the rest (about a minute). A colleague of
Max's waited for it on her first try ("every normal user is gone then"),
two minutes after her first message to the agent. So the account's first
message to the agent makes the VM in the background, while the user still
talks to the agent; the first call that needs it waits only for what is
left (setup_lock, the browser's own installation lock). The time a start
still takes (START_SECONDS, start_until) is what the chat and the live view
count down.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
import logging
from pathlib import Path
import secrets
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
# The live view's gateway service before 2026-10-27, removed by prepare.
OLD_GATEWAY_SERVICE = "view"
# How long a takeover holds without the view refreshing it (it does every
# CONTROL_REFRESH_SECONDS while the user has the browser).
CONTROL_SECONDS = 90
CONTROL_REFRESH_SECONDS = 30
# The tools of the VM, by their folder in workspace_vm/: the agent's side
# (agent-run, setup.sh) and the browser's (browser.py and cdp.py, its
# installation, start and rules: harden.sh with policy.json and openbox's two
# files hold whoever steers Chrome, since 2026-10-30, workspace_guard.py; the
# live view's relay). One folder on the VM since 2026-11-04: the browser's
# setup.sh is install.sh since then.
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


class WorkspaceBusy(Exception):
    """Another chat's message holds the workspace."""


@dataclass(frozen=True)
class Claim:
    restored: bool
    title: str = ""
    started: str = ""
    # The name of the chat's folder as the chat records it (open_chat),
    # empty before its first message since 2026-10-28.
    folder: str = ""
    # Since 2026-10-29: the names of the keys the user gave the agent
    # (agent_secrets.py), kept on the account's record across restarts.
    secrets: tuple = ()
    # Since 2026-11-06: the newest of those restores was the workspace's own (heal).
    healed: bool = False


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
# has to do (seconds, Prod 2026-10-29 to 11-02): a new VM's setup with
# Chrome (browser 61-63 s, workbench 57 s), the tools after a new version
# (7 s), a VM waking from cold with Chrome starting (median 15 s after a
# pause) or from warm (5 s), Chrome's start in the live view. Only what the
# user is told: the chat's step and the live view count the time left down
# (start_until); no start waits for them.
START_SECONDS = {"setup": 65, "update": 10, "cold": 15, "warm": 5, "chrome": 8}
# A start whose end nobody said is forgotten this long after its estimate.
START_FORGET_SECONDS = 600
_starts: dict[tuple, dict] = {}
_starts_lock = threading.Lock()


class Start:
    """One running start of an account's VM (``kind`` "browser" or
    "workbench"): ``phase`` says what it does now, ``end`` that it is over.
    Several may run for one VM (a message and the account's provisioning);
    start_until says the latest. Since the one computer (2026-11-04) both
    kinds start the same VM and wait for one setup (setup_lock): whoever
    waits asks for both (START_KINDS)."""

    def __init__(self, uid, kind):
        self.key = (uid, kind)

    def phase(self, phase):
        """Runs until about START_SECONDS[phase] from now, never earlier than it said before."""
        until = _now() + timedelta(seconds=START_SECONDS[phase])
        with _starts_lock:
            starts = _starts.setdefault(self.key, {})
            starts[self] = max(until, starts.get(self, until))
        return self

    def end(self):
        with _starts_lock:
            starts = _starts.get(self.key)
            if starts is not None:
                starts.pop(self, None)
                if not starts:
                    _starts.pop(self.key, None)


START_KINDS = ("browser", "workbench")


def start_until(uid, kinds=START_KINDS, besides=None):
    """About when the starts of the account's ``kinds`` still running end
    (the latest), or None when none runs; ``besides``: a Start left out."""
    now = _now()
    latest = None
    with _starts_lock:
        for kind in kinds:
            starts = _starts.get((uid, kind)) or {}
            for start, until in list(starts.items()):
                if until + timedelta(seconds=START_FORGET_SECONDS) < now:
                    starts.pop(start, None)
                elif start is not besides and (latest is None or until > latest):
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
                 secrets=outcome.get("secrets", ()), healed=outcome.get("healed", False))


def listed(record, field, kind):
    """A list field of the record, its entries of ``kind`` only."""
    values = record.get(field)
    return tuple(value for value in values if type(value) is kind) if isinstance(values, list) else ()


def remember_values(db, uid, field, values, *, keep):
    """Adds ``values`` to the list ``field`` of the account's record, the
    newest last and at most ``keep`` (agent_secrets' names): the record
    outlives a restart of the server, the process's memory does not."""
    doc = ref(db, uid)
    current = [value for value in ((doc.get().to_dict() or {}).get(field) or []) if value not in values]
    doc.set({field: [*current, *values][-keep:]}, merge=True)


# The sites the browser is logged in to, as the agent noted them
# (note_sign_in, agent_browser.py; since 2026-11-02): ``sign_ins`` on the
# record, each {site, name, since}. Cookies cannot say it (consent and
# bot-protection cookies are cookies too, browser.py saved_sign_in), the
# agent sees it on the page. Before, Max told the agent "remember you are
# logged in to WhatsApp", which went into his memory. The list comes with
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
    doc = ref(db, uid)
    current = sign_ins(doc.get().to_dict() or {})
    before = next((entry for entry in current if entry["site"] == site), None)
    entries = [entry for entry in current if entry["site"] != site]
    if signed_in:
        since = (before or {}).get("since") or (today or _now().date()).isoformat()
        entries.append({"site": site, "name": name or (before or {}).get("name") or site, "since": since})
    entries = entries[-SIGN_INS_KEPT:]
    if entries != current:
        doc.set({"sign_ins": entries}, merge=True)
    return entries


def clear_sign_ins(db, uid):
    """After the browser logged out of everything (reset_browser)."""
    ref(db, uid).set({"sign_ins": []}, merge=True)


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
    also when its lease ran out (runtime audit 2026-10-30, A2)."""
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
    that uses it is told (claim), who did it too (``by``: "user", or "heal"
    when it was stuck)."""
    workspace = ref(store.db, uid)

    def operation(tx):
        snapshot = workspace.get(transaction=tx)
        if snapshot.exists:
            tx.update(workspace, {"restores": int((snapshot.to_dict() or {}).get("restores") or 0) + 1,
                                  "restored_at": _now(), "restored_by": by})
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
# wins, and an older one ends within VIEW_CHECK_SECONDS once it sees that
# (security audit 2026-10-27; before, any number stayed open for an hour
# each). An open view keeps the VM awake: its time counts as VM time.
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
    made just now, else how it wakes (the provider's status, a hint only: a
    VM that just ran may say "cold" too). ``db``: the browser VM of before
    goes once the workspace is ready (retire_old_browser). ``timeout``: at
    most this long for a setup (prepare). A VM the gateway called
    unresponsive before raises at once, or once its probe did not reach it
    (reachable); one that does so now is asked again a minute later, and
    restores itself when it is stuck (heal_later, with ``db``)."""
    name = agent_vm.workspace_name(uid)
    stuck = None if db is None else (lambda: heal_later(db, uid))
    lock = setup_lock(name)
    while not lock.acquire(timeout=.2):
        if cancellation is not None:
            cancellation.raise_if_cancelled()
    try:
        reachable(name, cancellation, timeout, on_unresponsive=stuck)
        try:
            # A VM made just now has no version yet: prepare sets its rules.
            created = vm.ensure(name)
            if start is not None:
                phase = "setup" if created else {"cold": "cold", "warm": "warm"}.get(
                    getattr(vm, "statuses", {}).get(name))
                if phase:
                    start.phase(phase)
            prepare(vm, name, cancellation, timeout=timeout,
                    on_setup=None if start is None else (lambda: start.phase("setup" if created else "update")))
        except agent_vm.VMUnavailable as exc:
            if stuck is not None and agent_vm.unresponsive(exc):
                agent_vm.watch(name, stuck)
            raise
    finally:
        lock.release()
    if db is not None:
        retire_old_browser(db, uid, vm)
    return name


def reachable(name, cancellation=None, timeout=None, on_unresponsive=None):
    """Raises VMUnavailable with the gateway's status while ``name`` is
    marked unresponsive (agent_vm.mark_unresponsive): the browser's warm-up
    and the workbench of one message, and every message after, each waited
    about 48 s for the same 502 before (prod 2026-11-06, turn bb633b). Waits
    only for the VM's probe, at most PROBE_WAIT_SECONDS (and ``timeout``),
    so a VM that woke again is used again by the start that asked.
    ``on_unresponsive``: what the probe calls when the VM answers so again."""
    if agent_vm.unresponsive_status(name) is None:
        return
    probe = agent_vm.probe(name, on_unresponsive=on_unresponsive)
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


# Accounts whose browser VM of before is gone (or never was), in this process.
_retired: set[str] = set()


def retire_old_browser(db, uid, vm):
    """The browser VM of 2026-10-27 to 2026-11-04 goes once the account's
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
            ref(db, uid).set({"sign_ins": []}, merge=True)
            logging.info("Agent workspace old browser VM deleted")
        _retired.add(uid)
    except Exception as exc:
        logging.warning("Agent workspace old browser VM not deleted category=%s", safe_exception(exc))


def delete_old_browser(db, uid, vm):
    """The browser VM of 2026-10-27 to 2026-11-04, with the profile and every
    sign-in it kept, by its name whatever the record says (a VM that is gone
    counts as deleted), then the record forgets it. Also "Log out
    everywhere" (routers/agent_workspace.py): an account that did not open
    its workspace since the move still had that VM (review 2026-11-04)."""
    vm.delete(agent_vm.old_browser_name(uid))
    ref(db, uid).set({"browser": None}, merge=True)


# The account's provisioning (module docstring): once per process and account.
_provisioned: set[str] = set()


def provisioning():
    """AGENT_WORKSPACE_PROVISION=off: no workspace before it is needed (the
    test suite's default, whose fake VMs count their calls)."""
    import os
    return os.getenv("AGENT_WORKSPACE_PROVISION", "").strip().lower() != "off"


def provision(store, uid, *, factory=None):
    """A new account's workspace before it is needed (since 2026-11-02, the
    module's docstring): the VM made and set up in the background, the
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
    browser calls (bug hunt P60, 2026-11-05: the rest shortened it to two
    minutes, and a longer pause of the agent let the VM sleep under it); the
    message rests at its own end (agent_browser._rest)."""
    from app.services import agent_browser
    from app.services.llm.provider_runtime import ProviderCancellation
    start, vm, began = Start(uid, "browser").phase("setup"), None, time.monotonic()
    try:
        vm = factory()
        name = open_workspace(vm, uid, db=store.db)
        agent_browser.helper(vm, name, {"action": "warm"}, agent_browser.CALL_SECONDS, ProviderCancellation())
        if not in_use(store, uid):
            agent_browser.helper(vm, name, {"action": "rest"}, agent_browser.REST_SECONDS, ProviderCancellation())
        logging.info("Agent workspace provisioned seconds=%.1f", time.monotonic() - began)
    except Exception as exc:
        logging.warning("Agent workspace provision failed category=%s", safe_exception(exc))
    finally:
        start.end()
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
    one read): its network rules (agent_vm.RULES, the open web since
    2026-11-04), its tools written to the provider's home, the live view's
    gateway service of the layout before removed, and setup.sh run as root
    (the agent's user and its /tmp, the tools every workspace has; once, the
    moves from the layouts before). Returns whether it wrote them; raises
    SetupFailed when the setup failed, so no command runs with the
    provider's rights. ``timeout``: at most this long for the setup (the
    time the message has left before its answer, runtime audit 2026-10-30,
    A5). ``on_setup``: called when the setup is about to run (the start's
    phase)."""
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


# Makes the chat's folder (as the agent's user, with the folders the file
# needs), where commands start, and names its chat there. Since 2026-10-28
# the folder is named after the chat's title (agent_vm.chat_folder), so
# `ls ~/chats` already says which is which; .consens-chat adds title, start
# and id.
CHAT_MARKER = ".consens-chat"
TITLE_CHARS = 200


# A temporary chat's folder and marker name no title (since 2026-11-01):
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


# A message's chat on the workbench in one command (since 2026-10-30, runtime
# audit T6; before, four: the move, the marker, the notes and the keys, one
# round trip each), as the agent's user like each of them was: the chat's
# folder follows its title ($1 the folder now, $2 the one its title wants;
# "taken" keeps it where it is), its marker comes on stdin, then the keys
# the account gave ($5...: name NUL value NUL, as agent_secrets.LOAD_SCRIPT)
# and last the notes' beginning ($3, at most $4 bytes, to the end).
CHAT_SCRIPT = (
    'old=$1; new=$2; notes=$3; limit=$4; shift 4; dir=$old; state=same; '
    'if [ "$new" != "$old" ]; then '
    'if [ ! -e "$old" ] && [ ! -L "$old" ]; then dir=$new; state=missing; '
    'elif [ -e "$new" ] || [ -L "$new" ]; then state=taken; '
    'elif mkdir -p -- "$(dirname -- "$new")" && mv -T -- "$old" "$new"; then dir=$new; state=moved; '
    'else state=failed; fi; fi; '
    'mkdir -p -- "$dir" 2>/dev/null && cat > "$dir/' + CHAT_MARKER + '" 2>/dev/null || exit 46; '
    'printf "folder %s\\n" "$state"; '
    'if cd "$HOME/.secrets" 2>/dev/null; then for name in "$@"; do [ -f "$name" ] || continue; '
    'printf "key %s\\0" "$name"; head -c 16384 -- "$name"; printf "\\0"; done; fi; '
    'if [ -f "$notes" ] && [ -r "$notes" ]; then printf "notes +\\n"; exec head -c "$limit" -- "$notes"; fi; '
    'printf "notes -\\n"')
CHAT_SECONDS = 60


@dataclass(frozen=True)
class ChatOpened:
    folder: str
    notes: dict
    keys: tuple
    seconds: float


def parse_chat(raw):
    """``(state, keys, notes)`` of CHAT_SCRIPT's output: the folder's
    state, ``(name, value)`` pairs and the notes' bytes (None: no notes).
    A value loses its surrounding whitespace, as agent_secrets.save and load
    take it: a key file edited since (an editor's line break at its end)
    was masked only together with that line break (bug hunt 2026-11-06)."""
    head, _, rest = raw.partition(b"\n")
    if not head.startswith(b"folder "):
        raise agent_vm.VMUnavailable("chat: unreadable")
    state, keys = head[7:].decode("ascii", "replace"), []
    while rest.startswith(b"key "):
        name, _, rest = rest[4:].partition(b"\0")
        value, _, rest = rest.partition(b"\0")
        keys.append((name.decode("ascii", "replace"), value.decode("utf-8", "replace").strip()))
    if rest.startswith(b"notes +\n"):
        return state, keys, rest[8:]
    if rest.startswith(b"notes -"):
        return state, keys, None
    raise agent_vm.VMUnavailable("chat: unreadable")


# A temporary chat reads the notes and leaves them as they are (since
# 2026-11-01 evening): they outlast it (agent_vm_tools.VMTools._notes_kept).
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
    title (``folder``: the name the chat recorded, empty for a folder named
    by its id from before 2026-10-28, which moves too) with its marker
    rewritten, the account's keys read again for masking (as
    agent_secrets.load) and the notes' beginning (notes_for_agent), in one
    command. Returns ChatOpened: the folder's name now, the old one when the
    new name is taken or the move failed."""
    from app.services import agent_secrets
    from app.services.llm.provider_runtime import ProviderCancellation
    wanted = wanted_folder(chat_id, title, temporary=temporary)
    old = agent_vm.chat_dir(chat_id, folder or None)
    names = [key for key in dict.fromkeys(keys) if agent_secrets.NAME.fullmatch(str(key))][:agent_secrets.KEEP_NAMES]
    out = bytearray()
    limit = NOTES_CHARS * 4
    cap = limit + len(names) * (agent_secrets.VALUE_CHARS + 80) + 256

    def keep(stream, chunk):
        if stream == "stdout" and len(out) <= cap:
            out.extend(chunk)
    outcome = vm.run(name, agent_vm.agent_argv(["bash", "-c", CHAT_SCRIPT, "chat", old,
                                                agent_vm.chat_dir(chat_id, wanted), NOTES_PATH, str(limit), *names],
                                               CHAT_SECONDS, HOME),
                     cwd="/", timeout=CHAT_SECONDS, on_output=keep, cancellation=cancellation or ProviderCancellation(),
                     input=chat_marker(chat_id, title, started, temporary=temporary))
    if outcome.exit_code != 0:
        raise agent_vm.VMUnavailable(f"chat: exit {outcome.exit_code}")
    state, found, notes = parse_chat(bytes(out))
    return ChatOpened(folder=wanted if state in {"moved", "missing", "same"} else folder,
                      notes=notes_for_agent(notes, temporary=temporary),
                      keys=tuple(found), seconds=outcome.seconds)


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
# wait), one read of the account's record each (runtime audit 2026-10-30,
# T6). A takeover in this process (set_control) forgets it at once; on the
# browser VM itself browser.py refuses to act while the user has it.
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
    """With the account (account_deletion.py): the workspace's VM (and the
    browser VM of before) by the names that follow from the account, then
    its record. Before 2026-10-27 a missing record ended this, and a later
    area of the deletion removed the record after one failed provider call:
    the VM stayed for good. Only a server without a provider skips an
    account without a record (it never made one there). The safety rules'
    guard and trail go with it (workspace_guard.py, since 2026-10-30)."""
    from app.services import workspace_guard
    workspace = ref(db, uid)
    if agent_vm.configured() or factory is not None or workspace.get().exists:
        agent_vm.delete_workspace(uid, factory=factory)
    workspace.delete()
    workspace_guard.delete_for_account(db, uid)


# A message's checkpoint of the workspace (VMSession.ready; since 2026-11-04
# it holds the browser's profile too) may bring the workspace back for
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
    if isinstance(floor, datetime) and taken <= floor:
        return False
    return not any(isinstance(gap, dict) and isinstance(gap.get("from"), datetime)
                   and isinstance(gap.get("to"), datetime) and gap["from"] <= taken <= gap["to"]
                   for gap in record.get("restore_gaps") or ())


# A temporary chat's messages take no checkpoint (VMSession.ready), but
# other chats' messages may while it lives, its folder in them: only those
# may not bring it back (restore_gaps, since 2026-11-01). A floor at each
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


# A stuck workspace (agent_vm.PROBE_SECONDS: the gateway answered 502, 503
# or 504 twice, a minute or more apart) goes back to its newest checkpoint
# by itself (since 2026-11-06): before, it stayed so until Max asked for a
# restore by hand, several times since 2026-10-29. It loses what changed
# after that checkpoint, which a message takes before its own commands, so
# at most that message's changes; the files it shared stay in the chat.
# Only a checkpoint that may still bring the workspace back (restorable),
# never under a message (in_use: waited for, at most HEAL_WAIT_SECONDS),
# at most once per HEAL_SECONDS and account in this process.
HEAL_SECONDS = 3600
HEAL_WAIT_SECONDS = 600
HEAL_POLL_SECONDS = 5
_heals: dict[str, float] = {}
_heals_lock = threading.Lock()


def heal_later(db, uid, *, factory=None):
    """heal on a thread of its own, unless one began within HEAL_SECONDS.
    Returns the thread, or None."""
    now = time.monotonic()
    with _heals_lock:
        began = _heals.get(uid)
        if began is not None and now - began < HEAL_SECONDS:
            return None
        _heals[uid] = now
    thread = threading.Thread(target=heal, args=(db, uid), kwargs={"factory": factory}, name="agent-workspace-heal",
                              daemon=True)
    thread.start()
    return thread


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
        agent_vm.restore_workspace(uid, point["checkpoint"], factory=factory)
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
    takes none): from the chats that used it, newest first, the first whose
    newest HEAL_TURNS turns name one, at most HEAL_CHATS chats (the newest
    are those that met the stuck VM and took none: prod 2026-11-06, three
    of them), only their ``agent_vm``. None without one."""
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
    for _, chat_id in sorted(used, reverse=True)[:HEAL_CHATS]:
        turns = (chats.document(chat_id).collection("turns").order_by("position", direction=firestore.Query.DESCENDING)
                 .limit(HEAL_TURNS).select(["agent_vm"]))
        for snapshot in turns.stream():
            vm = (snapshot.to_dict() or {}).get("agent_vm")
            if isinstance(vm, dict) and vm.get("checkpoint") and vm.get("name") == name:
                return {"id": str(vm["checkpoint"]), "at": str(vm.get("checkpoint_at") or "")}
    return None


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

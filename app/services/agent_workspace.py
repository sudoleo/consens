"""The account's workspace (since 2026-10-27, docs/agent-mode.md "Workspace"):
two Linux VMs for all of an account's chats and its user, like a
colleague's computer and its browser. The agent works on the workbench
(agent_vm.workspace_name, agent_vm_tools.py) as a user of its own; the
browser (agent_vm.browser_name) holds Chrome, which the user watches and
steers live (routers/agent_workspace.py, workspace-view.js) and the agent
uses through the ``browser`` tool (agent_browser.py). No code of the agent
runs on the browser, and the workbench reaches only package registries and
what the user allowed for the chat (agent_domains.py): security audit
2026-10-27, Max's option A. localhost in the browser is the workbench's
(agent_tunnel.py, since 2026-10-29), one direction only.

Record and lease: ``users/{uid}/chat_state/agent_workspace`` names both VMs
before the provider creates either, so the account's deletion always finds
them, and leases the workspace to one chat's message at a time (``lease``:
chat, turn, until). A lease ends with its message (release) or by itself
LEASE_SECONDS after its last VM call, so a run that died never blocks the
workspace. The user's live view takes no lease: it is their computer.

Tools in the VMs (workspace_vm/): on the workbench ``agent-run``, which every
command and file operation of the agent goes through, and its setup (the
agent's user, the move from the layout before); on the browser
``browser.py``, the one program the browser tool calls, the browser's setup
and start, the live view's relay and the tunnel to the workbench. They are written again whenever their
VERSION changed (prepare, prepare_browser), at a message's first call of
either or when the view opens.

Folders and notes (like Claude Code's memory): each chat's folder names its
chat in CHAT_MARKER (title, start, id), so a chat finds another's files; and
NOTES_PATH is the agent's own notebook of the workspace across chats (what is
where, what is in progress, a project's conventions). Its beginning comes with
the first VM result of every message (open_chat), as data; the user's memory
(agent_memory.py) stays what the user said about themselves.

Takeover: the account's record says the user has the browser until a time
the open view keeps moving on (CONTROL_SECONDS, ``control``), and so does
``control.json`` on the browser. While it holds, the agent waits: the server
holds its calls (user_has_browser, VMSession.wait_for_user) and browser.py
refuses to act. What already runs on the workbench goes on: from 2026-10-27
to 2026-10-29 pause.py froze it, from the time the browser lived on the
workbench, where the agent's processes could have watched the user type.
On a VM of its own nothing of the workbench sees the browser, and the
agent's server must answer it while the user tries the agent's app
(agent_tunnel.py). The reviewers follow what the agent does, never what the
user does.

A new account's workspace (provision, since 2026-11-02): each VM's first
setup installs Chrome and the rest (about a minute each). A colleague of
Max's waited for both on her first try ("every normal user is gone then"),
two minutes after her first message to the agent. So the account's first
message to the agent makes both VMs in the background, while the user
still talks to the agent; the first call that needs one waits only for
what is left (setup_lock, the browser's own setup lock). The time a start
still takes (START_SECONDS, start_until) is what the chat and the live view
count down.
"""
from __future__ import annotations

from contextlib import contextmanager
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
# The server's own files, in the provider's home on each VM; on the
# workbench the agent's user cannot open it.
WORKSPACE_DIR = agent_vm.TOOLS_DIR
VERSION_PATH = WORKSPACE_DIR + "/version"
BROWSER_STATE = agent_vm.SERVER_HOME + "/.consens/browser"
BROWSER_CONTROL = BROWSER_STATE + "/control.json"
BROWSER_PROFILE = BROWSER_STATE + "/profile"
BROWSER_UPLOADS = BROWSER_STATE + "/uploads"
# What the browser downloaded, until agent_browser copies it to the workbench
# (workspace_vm/browser/browser.py DOWNLOADS).
BROWSER_DOWNLOADS = BROWSER_STATE + "/downloads"
BROWSER_HELPER = WORKSPACE_DIR + "/browser.py"
BROWSER_RELAY = WORKSPACE_DIR + "/relay.py"
BROWSER_TUNNEL = WORKSPACE_DIR + "/tunnel.py"
# tunnel.py on the workbench, where the agent's user reads it (setup.sh
# installs it there, root's, 0644): its connect runs as that user.
WORKBENCH_TUNNEL = "/usr/local/lib/consens/tunnel.py"
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
WORKBENCH_FILES = ("agent-run", "setup.sh", "tunnel.py")
# harden.sh with policy.json and openbox's two files: the rules that hold
# whoever steers Chrome (since 2026-10-30, workspace_guard.py).
BROWSER_FILES = ("browser.py", "display.sh", "harden.sh", "openbox-menu.xml", "openbox-rc.xml", "policy.json",
                 "relay.py", "setup.sh", "tunnel.py")
SETUP_SECONDS = 180
# setup.sh installs headless Chrome from Google's own server, which the
# workbench's policy closes (agent_vm.WORKBENCH_RULES): prepare opens it
# around the setup alone (_open_for_setup).
CHROME_DOMAIN = "dl.google.com"
CHROME_RULE = {"domain": CHROME_DOMAIN, "action": "allow"}
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
    # The name of the chat's folder as the chat records it (open_chat),
    # empty before its first message since 2026-10-28.
    folder: str = ""
    # Since 2026-10-29: the ports the browser reached on the workbench
    # (agent_tunnel.py) and the names of the keys the user gave the agent
    # (agent_secrets.py), both kept on the account's record across restarts.
    tunnel_ports: tuple = ()
    secrets: tuple = ()
    # The workbench's network rules as the last message confirmed them at
    # its end (policy_key), or None when nobody knows them for sure. The
    # claim leaves the record's key unknown until this message's release
    # says it again (release), so a run that died never leaves a key behind
    # that the workbench does not have (runtime audit 2026-10-30, T6).
    policy: str | None = None


def policy_key(rules):
    """A short fingerprint of network rules, to see whether they changed."""
    return hashlib.sha256(json.dumps(list(rules), sort_keys=True).encode()).hexdigest()[:16]


# Workbenches whose rules this process changed and could not confirm back
# (_open_for_setup's restore failed): their next start sets the rules
# whatever the record says.
_policy_unsure: set[str] = set()


def policy_unsure(name):
    return name in _policy_unsure


def tool_files(kind="workbench"):
    """A VM's tools as written there (LF line ends whatever the checkout):
    its own folder's, else the ones both VMs run (workspace_vm/tunnel.py)."""
    names = WORKBENCH_FILES if kind == "workbench" else BROWSER_FILES
    return {name: (_FILES / kind / name if (_FILES / kind / name).exists() else _FILES / name)
            .read_bytes().replace(b"\r\n", b"\n") for name in names}


def _version(kind):
    digest = hashlib.sha256(kind.encode() + b"\0" + agent_vm.AGENT_USER.encode() + b"\0")
    for name, data in sorted(tool_files(kind).items()):
        digest.update(name.encode() + b"\0" + data + b"\0")
    if kind == "browser":
        # Its network rules come with a new version (prepare_browser).
        digest.update(json.dumps(agent_vm.BROWSER_RULES, sort_keys=True).encode())
    return digest.hexdigest()[:16]


VERSION = _version("workbench")
BROWSER_VERSION = _version("browser")


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
    start_until says the latest."""

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


def start_until(uid, kinds=("browser", "workbench"), besides=None):
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


# One setup of a workbench at a time in this process (one server instance):
# the account's provisioning and a message's start (VMSession._bench) never
# run setup.sh side by side, whose rules for its download the other would
# undo; the second waits and finds the version there. The browser VM's
# setup holds a lock of its own on the VM (workspace_vm/browser/setup.sh).
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
    the account's workspace (both VMs) is recorded on the account and the
    chat (before the provider creates either) and leased to this message.
    Raises WorkspaceBusy when another chat's message holds it. Returns a
    Claim: whether the workspace was restored since this chat last used it,
    the chat's title and start for its folder (open_chat) and the
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
        folder = used.get("folder")
        outcome["folder"] = folder if isinstance(folder, str) else ""
        from app.services import agent_domains
        outcome["domains"] = agent_domains.granted(chat_data)
        outcome["tunnel_ports"] = listed(record, "tunnel_ports", int)
        outcome["secrets"] = listed(record, "secret_names", str)
        policy = record.get("policy")
        outcome["policy"] = policy if isinstance(policy, str) else None
        tx.set(workspace, {**{key: value for key, value in record.items() if key != "lease"},
                           "provider": provider, "name": name, "browser": agent_vm.browser_name(uid),
                           "created_at": record.get("created_at") or now.isoformat(),
                           # Unknown while this message may change the rules (Claim.policy).
                           "policy": None,
                           "lease": {"chat_id": chat_id, "turn_id": turn_id, "until": now + timedelta(
                               seconds=LEASE_SECONDS)}})
        tx.update(chat, {"agent_vm": {**{key: value for key, value in used.items()
                                         if key in {"restored", "created_at", "folder"}},
                                      "provider": provider, "name": name, "workspace": True,
                                      "created_at": used.get("created_at") or now.isoformat(), "used_at": now,
                                      "restores_seen": restores}})
    store._transaction(operation)
    return Claim(restored=outcome.get("restored", False), title=outcome.get("title", ""),
                 started=outcome.get("started", ""), domains=tuple(outcome.get("domains") or ()),
                 folder=outcome.get("folder", ""), tunnel_ports=outcome.get("tunnel_ports", ()),
                 secrets=outcome.get("secrets", ()), policy=outcome.get("policy"))


def listed(record, field, kind):
    """A list field of the record, its entries of ``kind`` only."""
    values = record.get(field)
    return tuple(value for value in values if type(value) is kind) if isinstance(values, list) else ()


def remember_values(db, uid, field, values, *, keep):
    """Adds ``values`` to the list ``field`` of the account's record, the
    newest last and at most ``keep`` (agent_tunnel's ports, agent_secrets'
    names): the record outlives a restart of the server, the process's
    memory does not."""
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


def release(store, uid, turn_id, policy=None):
    """Ends this message's lease; failures only cost the wait for its expiry.
    ``policy``: the workbench's rules as this message leaves them, confirmed
    (policy_key), or None when it does not know them for sure; the next
    message sets its rules unless they are confirmed the same (Claim.policy)."""
    workspace = ref(store.db, uid)

    def operation(tx):
        record = workspace.get(transaction=tx).to_dict() or {}
        if (record.get("lease") or {}).get("turn_id") == turn_id:
            tx.update(workspace, {"lease": None, "policy": policy})
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
    recorded on the account (no lease) before the provider creates one.
    Returns the record as it was."""
    from app.services import agent_tunnel, persistence_guard
    # The view opening may start the localhost tunnel: it is wanted from now
    # on, before claim_view names the view (agent_tunnel.viewing).
    agent_tunnel.viewing(uid)
    workspace = ref(store.db, uid)
    seen = {}

    def operation(tx):
        persistence_guard.ensure_account_write_allowed(uid=uid, db=store.db, transaction=tx)
        current = workspace.get(transaction=tx).to_dict() or {}
        seen["record"] = current
        if (current.get("name") != agent_vm.workspace_name(uid)
                or current.get("browser") != agent_vm.browser_name(uid)):
            tx.set(workspace, {**current, "provider": provider, "name": agent_vm.workspace_name(uid),
                               "browser": agent_vm.browser_name(uid),
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
    for the browser's live view, "terminal" for the user's terminal on the
    workbench; each kind has one at a time."""
    view_id = secrets.token_hex(8)
    workspace = ref(store.db, uid)

    def operation(tx):
        if workspace.get(transaction=tx).exists:
            tx.update(workspace, {kind: {"id": view_id, "until": _now() + timedelta(seconds=seconds)}})
    store._transaction(operation)
    if kind == "view":
        _viewing(uid)
    return view_id


def holds_view(db, uid, view_id, kind="view"):
    """Whether ``view_id`` is still the account's view of that kind (no newer
    one took over). The open view asks every VIEW_CHECK_SECONDS: for the
    browser's view that is its heartbeat, which keeps the localhost tunnel
    wanted while the user may look at the agent's app (agent_tunnel.viewing)."""
    held = (record(db, uid).get(kind) or {}).get("id") == view_id
    if held and kind == "view":
        _viewing(uid)
    return held


def _viewing(uid):
    from app.services import agent_tunnel
    agent_tunnel.viewing(uid)


def open_workbench(vm, uid, cancellation=None):
    """The account's workbench for the user's terminal and the account's
    provisioning: created with the base network rules where nothing made it
    yet (on an existing one a running chat's message keeps the rules it
    set), its tools and the agent's user up to date (prepare); its name."""
    name = agent_vm.workspace_name(uid)
    with setup_lock(name):
        if not vm.exists(name):
            vm.ensure(name, agent_vm.WORKBENCH_RULES)
        prepare(vm, name, cancellation)
    return name


# The account's provisioning (module docstring): once per process and account.
_provisioned: set[str] = set()


def provisioning():
    """AGENT_WORKSPACE_PROVISION=off: no workspace before it is needed (the
    test suite's default, whose fake VMs count their calls)."""
    import os
    return os.getenv("AGENT_WORKSPACE_PROVISION", "").strip().lower() != "off"


def provision(store, uid, *, factory=None):
    """A new account's workspace before it is needed (since 2026-11-02, the
    module's docstring): both VMs made and set up in the background, the
    browser's Chrome started once and then told to rest (the helper's warm
    and rest, as after a message). Only a VM that is not there: where the
    account's record names none yet nothing ever opened one, else the live
    view or the terminal may have made only its own (until 2026-11-04 that
    left the other to its first call). And only while the server's safety
    rules leave the workspace open. Called with the account's messages to the agent
    that may use the workspace (routers/agent.py); asks the record once per
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
            kinds = {kind for kind, name in (("browser", agent_vm.browser_name(uid)),
                                             ("workbench", agent_vm.workspace_name(uid)))
                     if new or not vm.exists(name)}
        finally:
            vm.close()
        if not kinds:
            return
    except Exception as exc:
        logging.warning("Agent workspace provision not started category=%s", safe_exception(exc))
        return
    _provision(uid, factory, kinds)


def _record_new(store, uid, provider):
    """Names both VMs on the account's record where it names none yet (the
    account's deletion finds them from then on, as record_for_view); whether
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
                               "browser": agent_vm.browser_name(uid),
                               "created_at": current.get("created_at") or _now().isoformat()})
    store._transaction(operation)
    return made["new"]


def _provision(uid, factory, kinds=("browser", "workbench")):
    """The VMs of ``kinds`` side by side, each on a backend of its own;
    failures are only logged: the first call that needs a VM sets up what is
    missing."""
    from app.services import agent_browser
    from app.services.llm.provider_runtime import ProviderCancellation
    seconds = {}

    def browser():
        start, vm, began = Start(uid, "browser").phase("setup"), None, time.monotonic()
        try:
            vm = factory()
            name = open_browser(vm, uid)
            for action, timeout in (("warm", agent_browser.CALL_SECONDS), ("rest", agent_browser.REST_SECONDS)):
                agent_browser.helper(vm, name, {"action": action}, timeout, ProviderCancellation())
            seconds["browser"] = time.monotonic() - began
        except Exception as exc:
            logging.warning("Agent workspace provision failed vm=browser category=%s", safe_exception(exc))
        finally:
            start.end()
            if vm is not None:
                vm.close()

    def workbench():
        start, vm, began = Start(uid, "workbench").phase("setup"), None, time.monotonic()
        try:
            vm = factory()
            open_workbench(vm, uid)
            seconds["workbench"] = time.monotonic() - began
        except Exception as exc:
            logging.warning("Agent workspace provision failed vm=workbench category=%s", safe_exception(exc))
        finally:
            start.end()
            if vm is not None:
                vm.close()
    threads = [threading.Thread(target=target, name=f"agent-workspace-provision-{target.__name__}", daemon=True)
               for target in (browser, workbench) if target.__name__ in kinds]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    logging.info("Agent workspace provisioned %s", " ".join(f"{kind}={value:.1f}" for kind, value in seconds.items())
                 or "nothing")


def _quiet(stream, chunk):
    pass


def _current(vm, name, version):
    try:
        raw, _ = vm.read_file(name, VERSION_PATH, limit=64, agent=False)
    except agent_vm.VMFileMissing:
        raw = b""
    return raw.decode("utf-8", "replace").strip() == version


@contextmanager
def _open_for_setup(vm, name):
    """CHROME_RULE for setup.sh alone: the rules read before come back
    exactly as they were, also when the setup fails or is stopped. A
    running chat's message may have added its domains (agent_domains.py),
    so they never go back to the base list. A policy that lets it through
    already, or none at all (open), stays untouched."""
    before = vm.get_policy(name)
    widen = bool(before) and not any(rule.get("action") == "allow" and rule.get("domain") in {CHROME_DOMAIN, "*"}
                                     for rule in before)
    if widen:
        # Until the rules are back for sure, the next start sets them anew
        # (policy_unsure), whatever the account's record says.
        _policy_unsure.add(name)
        vm.set_policy(name, [*before, CHROME_RULE])
    try:
        yield
    finally:
        if widen:
            vm.set_policy(name, before)
            _policy_unsure.discard(name)


class SetupFailed(agent_vm.VMUnavailable):
    """setup.sh did not succeed: no command of the agent may run there
    (a refusal of the workbench, not a broken connection)."""


def prepare(vm, name, cancellation=None, timeout=None, on_setup=None):
    """The workbench at this VERSION, only when the version there differs
    (else one read): its tools written to the provider's home, the live
    view's gateway service of the layout before removed, and setup.sh run
    as root (the agent's user, the tools every workbench has; once, the
    move of its files out of the provider's home) while the policy lets it
    reach CHROME_DOMAIN. Returns whether it wrote them; raises SetupFailed
    when the setup failed, so no command runs with the provider's rights.
    ``timeout``: at most this long for the setup (the time the message has
    left before its answer, runtime audit 2026-10-30, A5). ``on_setup``:
    called when the setup is about to run (the start's phase)."""
    from app.services.llm.provider_runtime import ProviderCancellation
    if _current(vm, name, VERSION):
        return False
    if on_setup is not None:
        on_setup()
    for file, data in tool_files("workbench").items():
        vm.write_file(name, f"{WORKSPACE_DIR}/{file}", data, agent=False)
    vm.delete_service(name, OLD_GATEWAY_SERVICE)
    said = []
    seconds = SETUP_SECONDS if timeout is None else max(1, min(SETUP_SECONDS, int(timeout)))
    with _open_for_setup(vm, name):
        outcome = vm.exec(name, f"sudo -n bash {WORKSPACE_DIR}/setup.sh", cwd=agent_vm.SERVER_HOME,
                          timeout=seconds, on_output=lambda stream, chunk: said.append(chunk),
                          cancellation=cancellation or ProviderCancellation(), agent=False)
    if outcome.exit_code != 0:
        logging.warning("Agent workbench setup failed exit=%s", outcome.exit_code)
        raise SetupFailed("setup")
    vm.write_file(name, VERSION_PATH, VERSION.encode(), agent=False)
    return True


def prepare_browser(vm, name):
    """The browser VM's tools and network rules at BROWSER_VERSION
    (browser.py installs and starts the browser itself when called).
    Returns whether it wrote them."""
    if _current(vm, name, BROWSER_VERSION):
        return False
    vm.set_policy(name, agent_vm.BROWSER_RULES)
    for file, data in tool_files("browser").items():
        vm.write_file(name, f"{WORKSPACE_DIR}/{file}", data, agent=False)
    vm.write_file(name, VERSION_PATH, BROWSER_VERSION.encode(), agent=False)
    return True


def open_browser(vm, uid, start=None):
    """The account's browser VM, created if needed, with its tools and
    network rules up to date; its name. Until 2026-10-29 every opening set
    its rules anew, a request that waits while the VM wakes: in Prod it once
    ran into its time limit, and the browser was off for the message. The
    rules only change with a new version, which sets them. ``start`` (a
    Start) learns what the browser's start has to do: its setup on a VM made
    just now, else how it wakes (the provider's status, a hint only: a VM
    that just ran may say "cold" too)."""
    name = agent_vm.browser_name(uid)
    created = vm.ensure(name)
    if start is not None:
        phase = "setup" if created else {"cold": "cold", "warm": "warm"}.get(getattr(vm, "statuses", {}).get(name))
        if phase:
            start.phase(phase)
    prepare_browser(vm, name)
    return name


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
    state, ``(name, value)`` pairs and the notes' bytes (None: no notes)."""
    head, _, rest = raw.partition(b"\n")
    if not head.startswith(b"folder "):
        raise agent_vm.VMUnavailable("chat: unreadable")
    state, keys = head[7:].decode("ascii", "replace"), []
    while rest.startswith(b"key "):
        name, _, rest = rest[4:].partition(b"\0")
        value, _, rest = rest.partition(b"\0")
        keys.append((name.decode("ascii", "replace"), value.decode("utf-8", "replace")))
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
    browser = agent_vm.browser_name(uid)
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
    made one there). The safety rules' guard and trail go with it
    (workspace_guard.py, since 2026-10-30)."""
    from app.services import agent_tunnel, workspace_guard
    workspace = ref(db, uid)
    agent_tunnel.close(uid)
    if agent_vm.configured() or factory is not None or workspace.get().exists:
        agent_vm.delete_workspace(uid, factory=factory)
    workspace.delete()
    workspace_guard.delete_for_account(db, uid)


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

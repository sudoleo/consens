"""The account's workspace (docs/agent-mode.md "Workspace"): one Linux VM for all of an account's
chats and its user, like a colleague's computer with its browser.

The agent works there as a user of its own (agent_vm_tools.py). Chrome runs there as the provider's
user; the user watches and steers it live and the agent uses it through the ``browser`` tool.
localhost in that browser is the agent's own servers. What the agent must not reach it cannot reach
by the computer's own means, Unix users and file modes, rather than bridges between machines, each
of which needed rules of its own: Chrome's protocol is a socket in the provider's home
(workspace_vm/browser/cdp.py, no TCP port), its screen asks for a cookie from there, and the agent's
commands have a /tmp of their own (agent-run). The network is open for the whole VM
(agent_vm.RULES). What a key the user gave the agent can do, the agent can do with it: that holds on
any computer.

``users/{uid}/chat_state/agent_workspace`` names the VM before the provider creates it, so the
account's deletion always finds it, and leases the workspace to one chat's message at a time. A
lease ends with its message, LEASE_SECONDS after its last VM call, or once its chat's run lock ran
out, so a run that died never blocks the workspace for long. The user's live view takes no lease: it
is their computer. A record that still names a browser VM of the two-VM layout has it deleted at the
next start (retire_old_browser).

Each chat's folder names its chat in CHAT_MARKER, so a chat finds another's files; NOTES_PATH is the
agent's own notebook across chats, whose beginning comes with each message's first VM result as
data.

Takeover: while the user has the browser (``control``, refreshed by the open view) the server holds
the agent's calls and browser.py refuses to act. What runs of the agent goes on: it reaches neither
the screen nor Chrome, and the agent's server must answer the browser while the user tries the
agent's app.

A new account's first message to the agent provisions the VM in the background (about a minute), so
the first call that needs it waits only for what is left."""
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
LEASE_RENEW_SECONDS = LEASE_SECONDS - 120
# The server's own files, in the provider's home, which the agent's user cannot open.
WORKSPACE_DIR = agent_vm.TOOLS_DIR
VERSION_PATH = WORKSPACE_DIR + "/version"
BROWSER_STATE = agent_vm.SERVER_HOME + "/.consens/browser"
BROWSER_CONTROL = BROWSER_STATE + "/control.json"
BROWSER_PROFILE = BROWSER_STATE + "/profile"
BROWSER_UPLOADS = BROWSER_STATE + "/uploads"
# What the browser downloaded, until agent_browser copies it into the chat's folder.
BROWSER_DOWNLOADS = BROWSER_STATE + "/downloads"
BROWSER_HELPER = WORKSPACE_DIR + "/browser.py"
BROWSER_RELAY = WORKSPACE_DIR + "/relay.py"
NOTES_PATH = HOME + "/NOTES.md"
# What of the notes comes with a message's first VM result; the rest the agent reads itself.
NOTES_CHARS = 6000
# The live view's former gateway service, removed by prepare.
OLD_GATEWAY_SERVICE = "view"
# How long a takeover holds without the view refreshing it.
CONTROL_SECONDS = 90
CONTROL_REFRESH_SECONDS = 30
# The VM's tools by their folder in workspace_vm/: the agent's side and the browser's (harden.sh
# with policy.json and openbox's two files hold whoever steers Chrome, workspace_guard.py).
TOOL_FILES = {"workbench": ("agent-run", "setup.sh"),
              "browser": ("browser.py", "cdp.py", "display.sh", "harden.sh", "install.sh", "openbox-menu.xml",
                          "openbox-rc.xml", "policy.json", "relay.py")}
SETUP_SECONDS = 180
_FILES = Path(__file__).with_name("workspace_vm")

# The activity says it calmly.
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
    # The chat's folder as the chat records it, empty before its first message.
    folder: str = ""
    # The names of the keys the user gave the agent, kept on the record across restarts.
    secrets: tuple = ()


def tool_files():
    """The VM's tools as written there (LF line ends whatever the checkout)."""
    return {name: (_FILES / folder / name).read_bytes().replace(b"\r\n", b"\n")
            for folder, names in TOOL_FILES.items() for name in names}


def _version():
    digest = hashlib.sha256(b"workspace\0" + agent_vm.AGENT_USER.encode() + b"\0")
    for name, data in sorted(tool_files().items()):
        digest.update(name.encode() + b"\0" + data + b"\0")
    # Its network rules come with a new version.
    digest.update(json.dumps(agent_vm.RULES, sort_keys=True).encode())
    return digest.hexdigest()[:16]


VERSION = _version()


# Seconds until a VM start's first call can run, by what it has to do (measured): a new VM's setup
# with Chrome, the tools after a new version, waking cold or warm, Chrome's start. Only what the
# user is told to count down; no start waits for them.
START_SECONDS = {"setup": 65, "update": 10, "cold": 15, "warm": 5, "chrome": 8}
# A start whose end nobody said is forgotten this long after its estimate.
START_FORGET_SECONDS = 600
_starts: dict[tuple, dict] = {}
_starts_lock = threading.Lock()


class Start:
    """One running start of an account's VM (``kind`` "browser" or "workbench"). Several may run for
    one VM; start_until says the latest."""

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
    """About when the starts of ``kinds`` still running end, or None; ``besides``: a Start left out."""
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


# One setup at a time in this process: the provisioning, a message's start, the browser's warm-up
# and the view never run setup.sh side by side; the second finds the version there. The browser's
# installation locks on the VM.
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
    """The chat of a live lease that is not ``chat_id``'s, else None: one chat runs one message at a
    time."""
    if not isinstance(lease, dict):
        return None
    until = lease.get("until")
    if not isinstance(until, datetime) or until <= now or lease.get("chat_id") == chat_id:
        return None
    return lease.get("chat_id")


def _runs(store, uid, chat_id, now, transaction=None):
    """Whether ``chat_id`` still runs a response: its run lock, which runs out within minutes of a
    server that died with it."""
    chat = store._chat_ref(uid, chat_id).get(transaction=transaction).to_dict() or {}
    lock = chat.get("agent_lock_until")
    return isinstance(lock, datetime) and lock > now


def claim(store, uid, chat_id, turn_id, *, provider):
    """In one transaction: the account may write, the chat is active, the VM is recorded on the
    account and the chat before the provider creates it, and the workspace is leased to this
    message. Raises WorkspaceBusy while another chat's message holds it and still runs. Returns a
    Claim."""
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
        holder = _held_by_other(record.get("lease"), chat_id, now)
        if holder and _runs(store, uid, holder, now, transaction=tx):
            raise WorkspaceBusy()
        used = (chat_data.get("agent_vm") or {}) if isinstance(chat_data.get("agent_vm"), dict) else {}
        # Restores so far, and how many this chat was told of.
        restores = int(record.get("restores") or 0)
        outcome["restored"] = bool(used.get("workspace")) and restores > int(used.get("restores_seen") or 0)
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
                 secrets=outcome.get("secrets", ()))


def listed(record, field, kind):
    values = record.get(field)
    return tuple(value for value in values if type(value) is kind) if isinstance(values, list) else ()


def remember_values(db, uid, field, values, *, keep):
    """Adds ``values`` to the list ``field`` of the account's record, newest last, at most ``keep``:
    the record outlives a server restart, the process's memory does not."""
    doc = ref(db, uid)
    current = [value for value in ((doc.get().to_dict() or {}).get(field) or []) if value not in values]
    doc.set({field: [*current, *values][-keep:]}, merge=True)


# The sites the browser is logged in to as the agent noted them, each {site, name, since}. Cookies
# cannot say it (consent and bot-protection cookies are cookies too), the agent sees it on the page.
# The list comes with every message, and the user sees and edits it in Settings.
SIGN_INS_KEPT = 20
SIGN_IN_NAME_CHARS = 40
SIGN_INS_NOTE = ("The workspace's browser was logged in to these sites when the agent last noted it (note_sign_in); "
                 "a session can run out, the page shows whether it still holds: {sites}.")


def sign_ins(record):
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
    """Puts ``site`` on the account's sign-ins or takes it off; returns the list. A site noted again
    keeps its first day and takes the new name."""
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
    """What a message's context says of ``entries``, or ""."""
    sites = "; ".join(f"{entry['name']} ({entry['site']}" + (f", since {entry['since']})" if entry["since"] else ")")
                      for entry in entries)
    return SIGN_INS_NOTE.format(sites=sites) if sites else ""


def renew(store, uid, turn_id):
    """Moves this message's lease on; False when another chat took the workspace."""
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
    """Whether the lease is still this message's; None when the record cannot be read."""
    try:
        lease = record(store.db, uid).get("lease")
    except Exception as exc:
        logging.warning("Agent workspace lease unreadable category=%s", safe_exception(exc))
        return None
    return isinstance(lease, dict) and lease.get("turn_id") == turn_id


def held_by(db, uid, now=None):
    return _held_by_other(record(db, uid).get("lease"), None, now or _now())


def in_use(store, uid, now=None):
    """Whether a chat's message may be using the workspace now: its lease holds, or the lease's
    chat, also one past its time, still runs a response. A restore never goes under a running agent."""
    now = now or _now()
    lease = record(store.db, uid).get("lease")
    if _held_by_other(lease, None, now):
        return True
    if not isinstance(lease, dict) or not lease.get("chat_id"):
        return False
    try:
        return _runs(store, uid, lease["chat_id"], now)
    except Exception as exc:
        logging.warning("Agent workspace lease chat unreadable category=%s", safe_exception(exc))
        return True


def mark_restored(store, uid):
    """The workspace went back to a checkpoint: every chat's next message that uses it is told."""
    workspace = ref(store.db, uid)

    def operation(tx):
        snapshot = workspace.get(transaction=tx)
        if snapshot.exists:
            tx.update(workspace, {"restores": int((snapshot.to_dict() or {}).get("restores") or 0) + 1,
                                  "restored_at": _now()})
    store._transaction(operation)


def record_for_view(store, uid, *, provider):
    """The VM recorded on the account (no lease) before the view makes one; returns the record as it
    was."""
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


# One live view per account: the newest wins and an older one ends within VIEW_CHECK_SECONDS. An
# open view keeps the VM awake, so its time counts.
VIEW_CHECK_SECONDS = 30


def claim_view(store, uid, seconds, kind="view"):
    """This view is the account's one of its ``kind`` ("view" or "terminal") from now on; returns
    its id."""
    view_id = secrets.token_hex(8)
    workspace = ref(store.db, uid)

    def operation(tx):
        if workspace.get(transaction=tx).exists:
            tx.update(workspace, {kind: {"id": view_id, "until": _now() + timedelta(seconds=seconds)}})
    store._transaction(operation)
    return view_id


def holds_view(db, uid, view_id, kind="view"):
    """Whether ``view_id`` is still the account's view of that kind; the open view asks every
    VIEW_CHECK_SECONDS."""
    return (record(db, uid).get(kind) or {}).get("id") == view_id


def open_workspace(vm, uid, cancellation=None, *, start=None, db=None, timeout=None):
    """The account's VM for whatever needs it, created with the network rules where nothing made it
    yet, tools and the agent's user up to date (prepare), under the setup lock; its name. ``start``
    learns what the start has to do (the provider's status is a hint only). ``db``: an old browser
    VM goes once the workspace is ready. ``timeout``: at most this long for a setup."""
    name = agent_vm.workspace_name(uid)
    lock = setup_lock(name)
    while not lock.acquire(timeout=.2):
        if cancellation is not None:
            cancellation.raise_if_cancelled()
    try:
        # A VM made just now has no version yet: prepare sets its rules.
        created = vm.ensure(name)
        if start is not None:
            phase = "setup" if created else {"cold": "cold", "warm": "warm"}.get(getattr(vm, "statuses", {}).get(name))
            if phase:
                start.phase(phase)
        prepare(vm, name, cancellation, timeout=timeout,
                on_setup=None if start is None else (lambda: start.phase("setup" if created else "update")))
    finally:
        lock.release()
    if db is not None:
        retire_old_browser(db, uid, vm)
    return name


# Accounts whose old browser VM is gone (or never was), in this process.
_retired: set[str] = set()


def retire_old_browser(db, uid, vm):
    """A browser VM of the two-VM layout goes once the account's workspace runs: deleted by name,
    then the record forgets it and the sign-ins with it, since none holds on the new browser. Only
    where the record still names it; a failure leaves it for the next start."""
    if uid in _retired:
        return
    try:
        if record(db, uid).get("browser"):
            vm.delete(agent_vm.old_browser_name(uid))
            ref(db, uid).set({"browser": None, "sign_ins": []}, merge=True)
            logging.info("Agent workspace old browser VM deleted")
        _retired.add(uid)
    except Exception as exc:
        logging.warning("Agent workspace old browser VM not deleted category=%s", safe_exception(exc))


# Once per process and account.
_provisioned: set[str] = set()


def provisioning():
    """AGENT_WORKSPACE_PROVISION=off: no workspace before it is needed (the test suite's default)."""
    import os
    return os.getenv("AGENT_WORKSPACE_PROVISION", "").strip().lower() != "off"


def provision(store, uid, *, factory=None):
    """A new account's workspace before it is needed: the VM made and set up in the background,
    Chrome started once and told to rest. Only where none is there, and only while workspace_guard
    leaves the workspace open; asks the record once per process and account, on a thread, so the
    message never waits. Returns the thread, or None."""
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
    _provision(uid, factory, store.db)


def _record_new(store, uid, provider):
    """Names the VM on the record where it names none yet; whether it did."""
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


def _provision(uid, factory, db=None):
    """The VM set up and its browser started once, then told to rest; failures are only logged, the
    first call that needs it sets up what is missing."""
    from app.services import agent_browser
    from app.services.llm.provider_runtime import ProviderCancellation
    start, vm, began = Start(uid, "browser").phase("setup"), None, time.monotonic()
    try:
        vm = factory()
        name = open_workspace(vm, uid, db=db)
        for action, timeout in (("warm", agent_browser.CALL_SECONDS), ("rest", agent_browser.REST_SECONDS)):
            agent_browser.helper(vm, name, {"action": action}, timeout, ProviderCancellation())
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
    """setup.sh did not succeed: no command of the agent may run there."""


def prepare(vm, name, cancellation=None, timeout=None, on_setup=None):
    """The VM at this VERSION, only when the version there differs: network rules, tools, the old
    gateway service removed, setup.sh run as root. Returns whether it wrote them; raises SetupFailed
    so no command runs with the provider's rights. ``timeout``: the message's time left before its
    answer. ``on_setup``: called when the setup is about to run."""
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


# The chat's folder is named after its title, so `ls ~/chats` says which is which; .consens-chat
# adds title, start and id.
CHAT_MARKER = ".consens-chat"
TITLE_CHARS = 200


# A temporary chat's folder and marker name no title: the workspace is every chat's, and its title
# is the user's question.
TEMPORARY_FOLDER_TITLE = "temporary"
TEMPORARY_MARKER = ("This folder holds the files of a temporary chat; it is deleted when the user leaves that "
                    "chat, and other chats leave it alone.")


def chat_marker(chat_id, title="", started="", *, temporary=False):
    title = "(temporary chat)" if temporary else " ".join(str(title or "").split())[:TITLE_CHARS] or "(untitled)"
    note = TEMPORARY_MARKER if temporary else "This folder holds the files of that chat; it is deleted with the chat."
    return f"chat: {title}\nstarted: {started or 'unknown'}\nid: {chat_id}\n{note}\n".encode("utf-8")


def wanted_folder(chat_id, title="", *, temporary=False):
    return agent_vm.chat_folder(TEMPORARY_FOLDER_TITLE if temporary else title, chat_id)


def record_folder(store, uid, chat_id, folder):
    """The chat names its folder (``agent_vm.folder``), where its deletion finds it. Written after
    the move, so a failed move never leaves the chat pointing at a missing folder."""
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


# A message's chat in the workspace in one command as the agent's user: the folder follows its title
# ($1 now, $2 wanted; "taken" keeps it), its marker comes on stdin, then the account's keys ($5...:
# "key " name NUL value NUL) and the notes' beginning ($3, at most $4 bytes).
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
    """``(state, keys, notes)`` of CHAT_SCRIPT's output (notes None: none)."""
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


# A temporary chat only reads the notes: they outlast it.
NOTES_TEMPORARY = "This temporary chat leaves the notes as they are: they outlast it."
NOTES_NONE_TEMPORARY = "No notes yet, and this temporary chat starts none: they would outlast it."


def notes_for_agent(raw, *, temporary=False):
    """The beginning of the workspace's notes for the agent, or that there are none yet: ``{"path",
    "text", "more"}``. Data, never instructions."""
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
    """At a message's first call of the agent's side, in one command: the chat's folder follows its
    title with its marker rewritten, the account's keys read again for masking, and the notes'
    beginning. Returns ChatOpened (the old name when the new one is taken or the move failed)."""
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
    until = (now or time.time()) + CONTROL_SECONDS if holder == "user" else 0
    return json.dumps({"holder": holder, "until": until}).encode()


def set_control(db, uid, vm, holder):
    """The user takes the browser over (again at every refresh of the view) or hands it back. Taking
    over closes the server's way first, then the browser's; handing back opens them in the other
    order and notes ``returned_at``, so a waiting run sees it even between two looks."""
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
    """(whether the user has the browser now, when they last handed it back or 0), from the record's
    ``control``, which only the server writes. A takeover the view stopped refreshing has run out
    without a hand-back."""
    return control_of(record(db, uid), now)


def control_of(workspace, now=None):
    """control_state of a record already read."""
    control = workspace.get("control")
    if not isinstance(control, dict):
        return False, 0.0

    def number(key):
        try:
            return float(control.get(key) or 0)
        except (TypeError, ValueError):
            return 0.0
    return control.get("holder") == "user" and number("until") > (now or time.time()), number("returned_at")


# A workspace call asks twice right after another (the run's check, then the session's wait), one
# record read each. A takeover in this process forgets it at once; on the VM browser.py refuses to
# act anyway.
CONTROL_CACHE_SECONDS = 1.0
_control_seen: dict = {}
_control_lock = threading.Lock()


def _forget_control(uid):
    with _control_lock:
        for key in [key for key in _control_seen if key[1] == uid]:
            del _control_seen[key]


def user_has_browser(db, uid, now=None, fresh=False):
    """Whether the user has the browser now; ``fresh``: read now."""
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
    """Ends the browser and deletes its profile: every sign-in, cookie and open tab. As the
    provider's user, whose processes alone it ends. A workspace never made has nothing to sign out
    of."""
    name = agent_vm.workspace_name(uid)
    if not vm.exists(name):
        return
    vm.exec(name, f"pkill -u \"$(id -u)\" -f '[u]ser-data-dir={BROWSER_PROFILE}'; sleep 1; rm -rf {BROWSER_PROFILE} "
                  f"{BROWSER_UPLOADS}", cwd=agent_vm.SERVER_HOME, timeout=60, on_output=_quiet,
            cancellation=cancellation, agent=False)


def delete_for_account(db, uid, *, factory=None):
    """With the account: the VM (and an old browser VM) by the names that follow from the account,
    then its record and the guard's trail. Only a server without a provider skips an account without
    a record: a missing record must never leave a VM behind."""
    from app.services import workspace_guard
    workspace = ref(db, uid)
    if agent_vm.configured() or factory is not None or workspace.get().exists:
        agent_vm.delete_workspace(uid, factory=factory)
    workspace.delete()
    workspace_guard.delete_for_account(db, uid)


# A checkpoint (holding the browser's profile too) may bring the workspace back for this long, and
# only after the last time something left it for good (``restore_floor``: a sign-out everywhere, a
# deleted chat), or it would bring those back. The provider keeps the checkpoints; only their use
# ends here.
RESTORE_DAYS = 14


def restorable(record, turn_vm, now=None):
    """Whether ``turn_vm`` names a checkpoint of this account's workspace that may still bring it
    back."""
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


# A temporary chat takes no checkpoint, but other chats' messages may while it lives, its folder in
# them: only those may not bring it back. A floor at each deletion would end restore for the
# account's whole past. A gap ends this much after the deletion, for a checkpoint still being taken.
RESTORE_GAPS = 100
GAP_GRACE = timedelta(seconds=agent_vm.CHECKPOINT_SECONDS + 10)


def close_restore_gap(store, uid, since):
    """A temporary chat's folder left the workspace: no checkpoint from ``since`` to now may bring
    it back. Old gaps go; beyond RESTORE_GAPS or without ``since`` the floor rises instead."""
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
    """Something left the workspace for good: no checkpoint from before may bring it back. An
    account without a record is left alone."""
    workspace = ref(store.db, uid)

    def operation(tx):
        if workspace.get(transaction=tx).exists:
            tx.update(workspace, {"restore_floor": _now()})
    store._transaction(operation)

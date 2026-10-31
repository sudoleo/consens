"""The agent's work log, written live by the app (docs/agent-work-log.md).

Since 2026-10-25 in audit mode, since 2026-10-31 the Agent's one mode: every
turn of every account (routers/agent.py lets the turn's owner read it). While
the agent works, the app records what it sees and does, never the agent
itself: the context each model step receives (``context``: the chat's
history and question, then everything the run adds to the conversation,
such as the app's hints and workers' messages), the step's readable
reasoning, text, tool calls and search hits (``step``), every tool result
(``tool``), the app's own interventions (``app``: a retracted text, the
memory lock, the fixed answer), and the run's ``start`` and ``end``.
Delegated workers write into the same log under their own id. The reviewers
(comparison models), the judges and the app's page fetches are not part of
it (DelegationLoop._log_actor).

The log only grows: an entry is never changed, a retraction is a new entry.
One writer thread saves the entries in order, up to BATCH_LIMIT per
Firestore transaction of their own (AgentSessionStore.save_work_log), under
``users/{uid}/chats/{chat}/turns/{turn}/work_log/{seq:06d}``. Content above
INLINE_CHARS goes to the private object store (agent_files.PrivateObjects);
without one it is kept shortened. Recording never raises and never holds the
agent up: an entry that cannot be saved is lost, and the turn then carries
``work_log_incomplete``.

Retention: the turn carries ``work_log_expires_at`` (RETENTION_DAYS after
the run started); the hourly retention maintenance removes expired logs
(cleanup_expired_work_logs), and chat and account deletion remove them with
the turn (chat_store._delete_chat_tree -> delete_turn_log).
"""
from __future__ import annotations

from collections import deque
from datetime import datetime, timedelta, timezone
import hashlib
import json
import logging
import os
import threading
import time

from app.core.observability import safe_exception

RETENTION_DAYS = 30
# Content up to this many characters stays in the entry; longer content goes
# to the object store and the entry keeps PREVIEW_CHARS of it.
INLINE_CHARS = 16_000
PREVIEW_CHARS = 2_000
# Entries per Firestore transaction (each one write).
BATCH_LIMIT = 50
WRITE_ATTEMPTS = 3
# Seconds the run's end waits for the writer; what it has not saved by then
# is lost (the log then has no ``end`` entry, which readers take as a gap).
CLOSE_SECONDS = 20
OBJECT_PREFIX = "work-log"
KINDS = ("start", "context", "step", "tool", "app", "end")
# Where an entry's content comes from. Content from outside the user and the
# app (web, file, google, agent: model output, vm: what the agent's own VM
# returned) is data for every later reader, never instructions.
DATA_CLASSES = ("user", "web", "file", "google", "memory", "agent", "vm", "app")
UNTRUSTED_DATA = frozenset({"web", "file", "google", "agent", "vm"})
TOOL_DATA = {
    "read_source": "web",
    "read_file": "file", "read_document": "file", "create_document": "file", "revise_document": "file",
    "gmail_read": "google", "calendar_read": "google", "import_gmail_attachment": "google",
    "prepare_gmail_draft": "google", "prepare_calendar_event": "google",
    "update_memory": "memory",
    "start_agent": "agent", "send_agent": "agent", "wait_agents": "agent", "review_agent": "agent",
    "stop_agent": "agent", "report_to_orchestrator": "agent",
    "vm_exec": "vm", "vm_read_file": "vm", "vm_write_file": "vm", "vm_edit_file": "vm", "vm_share_file": "vm",
    "vm_start_process": "vm", "vm_process_output": "vm", "vm_stop_process": "vm", "vm_view_image": "vm",
    "vm_install_packages": "vm", "github_import": "vm", "prepare_pull_request": "vm", "update_plan": "agent",
    # Pages of the open web, in the user's signed-in browser; ask_user brings
    # the page back with it once the user handed the browser back (agent_ask.py).
    "browser": "web", "ask_user": "web",
    # Pictures of the web the server fetched (agent_web_images.py).
    "find_pictures": "web", "show_image": "web",
    # The answers of the user's chosen models with their pages (audit mode,
    # since 2026-10-31): model output.
    "compare_models": "agent",
}
# Measurements an entry may carry beside its content (since 2026-10-30): a
# tool result's start and duration (``tool``, audit I4), a gate's wait on its
# ``checked`` or ``paused`` entry (I9). Numbers and times only, never text.
ENTRY_FIELDS = ("started_at", "duration_ms", "gate_ms")


def _now():
    return datetime.now(timezone.utc)


def _json(value):
    return json.dumps(value, ensure_ascii=False, default=str)


def _measure(value):
    """A value ENTRY_FIELDS may hold: a non-negative number or a short time text."""
    if isinstance(value, bool):
        return False
    if isinstance(value, (int, float)):
        return value >= 0
    return isinstance(value, str) and 0 < len(value) <= 40


def readable_reasoning(value):
    """The step's reasoning a person can read: its text and summary blocks,
    never encrypted ones (agent_client: those are not stored anywhere)."""
    parts = []
    for detail in getattr(value, "_reasoning_parts", None) or []:
        if not isinstance(detail, dict):
            continue
        kind = detail.get("type")
        text = detail.get("summary" if kind == "reasoning.summary" else "text")
        if kind in {"reasoning.text", "reasoning.summary"} and isinstance(text, str) and text:
            parts.append(text)
    text = getattr(value, "_reasoning_text", "")
    if not parts and isinstance(text, str) and text:
        parts.append(text)
    return "\n\n".join(parts)


def message_text(message):
    """A context message as text; images and files as a placeholder (their
    bytes never enter the log)."""
    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        blocks = []
        for block in content:
            kind = block.get("type") if isinstance(block, dict) else None
            if kind == "text":
                blocks.append(str(block.get("text") or ""))
            elif kind == "file":
                blocks.append(f"[file: {(block.get('file') or {}).get('filename') or 'attachment'}]")
            elif kind == "image_url":
                blocks.append("[image]")
            else:
                blocks.append(f"[{kind or 'content'}]")
        return "\n\n".join(blocks)
    return _json(content)


def context_data(actor, index, own_from, message, text):
    """The data class of the conversation message at ``index`` (DATA_CLASSES).

    Messages before ``own_from`` are the chat as the run received it: the
    user's questions (with the app's context block) and the agent's earlier
    answers, and after an answer of a VM turn its work record (the app's,
    from VM output: ``vm``). Later user-role messages are never the user's
    words: the app adds its hints, and workers report to the agent. A
    worker's user-role messages are the agent's (its assignment and later
    messages)."""
    from app.services.agent_compaction import PICTURE_OPEN, is_work_record
    role = message.get("role")
    if role in {"system", "tool"}:
        return "app"
    if role == "assistant" or actor != "agent":
        return "agent"
    if is_work_record(text) or text.startswith(PICTURE_OPEN):
        # The app's record of VM output, a picture of the VM; a picture of
        # the browser or one find_pictures fetched is the web's.
        from app.services.agent_browser import SCREENSHOT_INTRO
        from app.services.agent_web_images import INTRO
        return "web" if text.startswith((SCREENSHOT_INTRO.split("{")[0], INTRO.split("{")[0])) else "vm"
    from app.services.agent_delegation import USER_NOTE_OPEN
    if text.startswith(USER_NOTE_OPEN):
        # A message the user sent into the running response.
        return "user"
    if index < own_from:
        return "user"
    return "agent" if text.startswith("Worker messages") else "app"


def object_key(uid, chat_id, turn_id, seq):
    return f"{OBJECT_PREFIX}/{uid}/{chat_id}/{turn_id}/{seq:06d}"


_OBJECT_STORES = {}
_OBJECT_STORES_LOCK = threading.Lock()


def _objects():
    """The private object store, one client per configuration, or None where
    none is configured."""
    from app.services.agent_files import PrivateObjects, StorageNotConfigured, _local_dir
    key = (os.getenv("AGENT_FILES_BUCKET", ""), _local_dir())
    with _OBJECT_STORES_LOCK:
        if key not in _OBJECT_STORES:
            try:
                _OBJECT_STORES[key] = PrivateObjects()
            except StorageNotConfigured:
                _OBJECT_STORES[key] = None
        return _OBJECT_STORES[key]


class WorkLog:
    """The work log of one turn. Every recording method is thread-safe and
    never raises; one writer thread saves the entries (``close`` waits for it
    at the run's end, at most CLOSE_SECONDS)."""

    def __init__(self, store, uid, chat_id, turn_id, *, ready=lambda: True, objects=None, clock=_now,
                 sleep=time.sleep):
        self.store, self.uid, self.chat_id, self.turn_id = store, uid, chat_id, turn_id
        # Entries are saved once the run has started its first model step;
        # a run that never did keeps no log.
        self._ready = ready
        self._clock, self._sleep = clock, sleep
        self._objects = objects
        self.expires_at = (clock() + timedelta(days=RETENTION_DAYS)).isoformat()
        self._condition = threading.Condition()
        self._seq = 0
        self._pending = deque()
        # Per actor: how much of its conversation is in the log, the tool
        # results logged when they returned, the request additions logged.
        self._cursors, self._logged, self._extras = {}, {}, {}
        # Every entry in order with its whole content, for the reviewers who
        # follow the log while the agent works (agent_audit.ReviewerSession).
        self._entries = []
        self._thread = None
        self._closing = False
        # Set when an entry could not be saved; the writer says so on the turn.
        self.incomplete = False

    # --- Recording ------------------------------------------------------------

    def add(self, kind, *, actor="app", name="", data="app", step=None, content="", fields=None):
        """Append one entry; returns its sequence number (None if refused).
        ``fields``: measurements of ENTRY_FIELDS beside the content."""
        try:
            text = content if isinstance(content, str) else _json(content)
            with self._condition:
                if self._closing:
                    return None
                self._seq += 1
                entry = {"seq": self._seq, "at": self._clock().isoformat(), "actor": actor, "kind": kind,
                         "name": str(name or "")[:200], "data": data if data in DATA_CLASSES else "app",
                         "format": "text" if isinstance(content, str) else "json", "chars": len(text)}
                if step:
                    entry["step"] = str(step)[:80]
                for key, value in (fields or {}).items():
                    if key in ENTRY_FIELDS and _measure(value):
                        entry[key] = value
                self._pending.append((entry, text))
                self._entries.append((entry, text))
                self._start()
                self._condition.notify_all()
                return self._seq
        except Exception as exc:
            logging.warning("Agent work log entry dropped category=%s", safe_exception(exc))
            self.incomplete = True
            return None

    def context(self, actor, conversation, request, *, step=None, own_from=0):
        """What a model step receives, as far as not yet in the log.

        ``conversation``: the actor's own message list, which only grows
        (DelegationLoop.messages, Worker.messages). Every message past this
        actor's cursor is logged, except the model's own messages from
        ``own_from`` on (they are its step entries; earlier ones are the
        chat's history) and the tool results logged when they returned.
        ``request``: what this step sends, the conversation plus what the app
        adds for the step only (the file block, a step note, a changed system
        prompt); each such addition is logged once per distinct text."""
        try:
            with self._condition:
                cursor = self._cursors.get(actor, 0)
                self._cursors[actor] = len(conversation)
                logged = self._logged.setdefault(actor, set())
                fresh = []
                for index in range(cursor, len(conversation)):
                    message = conversation[index]
                    if id(message) in logged:
                        logged.discard(id(message))
                    elif not (message.get("role") == "assistant" and index >= own_from):
                        fresh.append((index, message))
            for index, message in fresh:
                text = message_text(message)
                self.add("context", actor=actor, name=message.get("role") or "",
                         data=context_data(actor, index, own_from, message, text), step=step, content=text)
            own = {id(message) for message in conversation}
            for message in request:
                if id(message) in own:
                    continue
                text = message_text(message)
                digest = hashlib.sha256(f"{message.get('role')}\n{text}".encode("utf-8")).hexdigest()
                with self._condition:
                    extras = self._extras.setdefault(actor, set())
                    if digest in extras:
                        continue
                    extras.add(digest)
                self.add("context", actor=actor, name=message.get("role") or "", step=step, content=text,
                         data="file" if text.startswith("File evidence (untrusted)") else "app")
        except Exception as exc:
            logging.warning("Agent work log context dropped category=%s", safe_exception(exc))
            self.incomplete = True

    def step(self, actor, step, model, value, status):
        """A finished (or failed, or stopped) model step: what it thought,
        wrote and called. Returns its entry's number (None if not written)."""
        try:
            citations = {}
            for citation in getattr(value, "citations", None) or []:
                if isinstance(citation, dict) and citation.get("url") and citation.get("content"):
                    citations.setdefault(citation["url"], citation["content"])
            content = {
                "model": getattr(model, "model", ""), "status": status,
                "finish_reason": getattr(value, "finish_reason", ""),
                "reasoning": readable_reasoning(value), "text": getattr(value, "text", ""),
                "tool_calls": [{"id": call.get("id"), "name": (call.get("function") or {}).get("name"),
                                "arguments": (call.get("function") or {}).get("arguments")}
                               for call in getattr(value, "tool_calls", None) or []],
                "sources": list(getattr(value, "sources", None) or []),
                "search_excerpts": [{"url": url, "content": text} for url, text in citations.items()],
                "usage": getattr(value, "usage", None) or {},
            }
            if getattr(value, "published", ""):
                content["shown"] = True
            # Model output, the agent's or a worker's: data for every later
            # reader, never instructions.
            return self.add("step", actor=actor, name=getattr(model, "model", ""), data="agent", step=step,
                            content=content)
        except Exception as exc:
            logging.warning("Agent work log step dropped category=%s", safe_exception(exc))
            self.incomplete = True
            return None

    def tool(self, actor, step, call, message, *, started_at=None, duration_ms=None):
        """A tool result as it goes into the actor's conversation (where the
        next ``context`` then skips it), with when the call started (UTC,
        ISO) and how long it ran: a slow browser or VM call shows in the log
        itself, not only as the gap to the next entry (audit I4)."""
        try:
            name = (call.get("function") or {}).get("name") or ""
            with self._condition:
                self._logged.setdefault(actor, set()).add(id(message))
            self.add("tool", actor=actor, name=name, data=TOOL_DATA.get(name, "app"), step=step,
                     content=message_text(message), fields={"started_at": started_at, "duration_ms": duration_ms})
        except Exception as exc:
            logging.warning("Agent work log tool result dropped category=%s", safe_exception(exc))
            self.incomplete = True

    def app(self, name, content="", *, step=None, **fields):
        """An intervention of the app itself; ``fields`` as in ``add``."""
        return self.add("app", name=name, step=step, content=content, fields=fields)

    # --- Reading while it grows (the reviewers) -------------------------------

    @property
    def last(self):
        """The number of the newest entry (0 before the first)."""
        with self._condition:
            return self._seq

    def entries_after(self, seq):
        """``[(entry, whole content)]`` of every entry after number ``seq``."""
        with self._condition:
            return list(self._entries[seq:])

    def wait_for(self, seq, timeout):
        """Until an entry after number ``seq`` exists, ``wake`` is called or
        ``timeout`` passes (also once closed: a reader never spins)."""
        with self._condition:
            if self._seq <= seq:
                self._condition.wait(timeout)

    def wake(self):
        """Everyone waiting in ``wait_for`` looks again."""
        with self._condition:
            self._condition.notify_all()

    def close(self, timeout=CLOSE_SECONDS):
        """No more entries; wait (at most ``timeout``) for the writer."""
        with self._condition:
            self._closing = True
            self._condition.notify_all()
            thread = self._thread
        if thread is not None:
            thread.join(timeout)
            if thread.is_alive():
                logging.warning("Agent work log still saving at the run's end thread=%s", thread.name)

    # --- Saving ---------------------------------------------------------------

    def _start(self):
        if self._thread is None:
            self._thread = threading.Thread(target=self._run, name="agent-work-log", daemon=True)
            self._thread.start()

    def _run(self):
        while True:
            with self._condition:
                while not self._closing and not (self._pending and self._is_ready()):
                    self._condition.wait(.5)
                ready = self._is_ready()
                if self._closing and not ready:
                    # The run never started a model step: no log.
                    self._pending.clear()
                    return
                batch = [self._pending.popleft() for _ in range(min(BATCH_LIMIT, len(self._pending)))]
            if batch:
                self._write(batch)
                continue
            # Closing, all written: a lost entry is said on the turn.
            if self.incomplete:
                self._save([], incomplete=True)
            return

    def _is_ready(self):
        try:
            return bool(self._ready())
        except Exception:
            return False

    def _write(self, batch):
        entries = [self._stored(entry, text) for entry, text in batch]
        if not self._save(entries):
            self.incomplete = True
            # Content stored for entries that were never saved has no record
            # that would ever delete it.
            for entry in entries:
                if entry.get("ref") and self._objects is not None:
                    try:
                        self._objects.delete(entry["ref"])
                    except Exception as exc:
                        logging.warning("Agent work log content left behind category=%s", safe_exception(exc))

    def _save(self, entries, *, incomplete=False):
        from app.services.chat_store import ChatNotFound, TurnStatusConflict
        from app.services.persistence_guard import AccountDeletionInProgress
        for attempt in range(WRITE_ATTEMPTS):
            try:
                self.store.save_work_log(self.uid, self.chat_id, self.turn_id, entries, expires_at=self.expires_at,
                                         incomplete=incomplete)
                return True
            except (TurnStatusConflict, ChatNotFound, AccountDeletionInProgress) as exc:
                # The turn finished, or the chat or account is gone.
                logging.info("Agent work log closed category=%s", safe_exception(exc))
                return False
            except Exception as exc:
                logging.warning("Agent work log write failed attempt=%s category=%s", attempt + 1,
                                safe_exception(exc))
                if attempt + 1 < WRITE_ATTEMPTS:
                    self._sleep(.5 * 2 ** attempt)
        return False

    def _stored(self, entry, text):
        """The entry as saved: its content inline, or in the object store."""
        entry = dict(entry)
        if len(text) <= INLINE_CHARS:
            entry["content"] = text
            return entry
        key = object_key(self.uid, self.chat_id, self.turn_id, entry["seq"])
        try:
            if self._objects is None:
                self._objects = _objects()
            if self._objects is None:
                raise LookupError("no object store")
            _put(self._objects, key, text)
            entry.update(content=text[:PREVIEW_CHARS], ref=key)
        except Exception as exc:
            if not isinstance(exc, LookupError):
                logging.warning("Agent work log content kept shortened category=%s", safe_exception(exc))
            entry.update(content=text[:INLINE_CHARS], truncated=True)
        return entry


def _put(objects, key, text):
    """Store ``text`` once; a retried write finds its own first copy."""
    from google.api_core.exceptions import PreconditionFailed
    try:
        objects.put(key, text.encode("utf-8"), "text/plain; charset=utf-8")
    except (FileExistsError, PreconditionFailed):
        pass


# --- Reading, deleting, retention ---------------------------------------------

def entry_content(entry, objects=None):
    """An entry's whole content (from the object store when it is there)."""
    if not entry.get("ref"):
        return entry.get("content", "")
    objects = objects if objects is not None else _objects()
    if objects is None:
        from app.services.agent_files import FileUnavailable
        raise FileUnavailable("No object store holds this content.")
    return objects.get(entry["ref"]).decode("utf-8")


def delete_turn_log(turn_ref, objects=None):
    """Delete one turn's log: the stored content its entries name, then the
    entries. A turn without a log costs one empty query, never a call to the
    object store. Returns the number of entries deleted."""
    snapshots = list(turn_ref.collection("work_log").select(["ref"]).stream())
    keys = [data["ref"] for data in (snapshot.to_dict() or {} for snapshot in snapshots) if data.get("ref")]
    if keys:
        objects = objects if objects is not None else _objects()
        for key in keys if objects is not None else ():
            objects.delete(key)
    for snapshot in snapshots:
        snapshot.reference.delete()
    return len(snapshots)


CLEANUP_PAGE_SIZE = 50
CLEANUP_TIME_BUDGET_SECONDS = 240


def cleanup_expired_work_logs(db=None, *, page_size=CLEANUP_PAGE_SIZE, time_budget=CLEANUP_TIME_BUDGET_SECONDS,
                              clock=None, objects=None):
    """Hourly retention: remove every work log past ``work_log_expires_at``."""
    from firebase_admin import firestore
    from google.cloud.firestore_v1.base_query import FieldFilter
    clock = clock or time.monotonic
    if db is None:
        from app.core.security import db_firestore
        db = db_firestore
    deadline = clock() + time_budget
    threshold = _now().isoformat()
    count = 0
    query = (db.collection_group("turns").where(filter=FieldFilter("work_log_expires_at", "<=", threshold))
             .order_by("work_log_expires_at").limit(page_size))
    while clock() < deadline:
        batch = list(query.stream())
        for snapshot in batch:
            if clock() >= deadline:
                return count
            # The collection-group name is reused elsewhere: validate the full path.
            path = snapshot.reference.path
            pieces = path.split("/") if isinstance(path, str) else list(path)
            if not (len(pieces) == 6 and pieces[0] == "users" and pieces[2] == "chats"):
                continue
            try:
                delete_turn_log(snapshot.reference, objects=objects)
                snapshot.reference.update({"work_log_expires_at": firestore.DELETE_FIELD,
                                           "work_log_incomplete": firestore.DELETE_FIELD})
                count += 1
            except Exception as exc:
                # One stuck log must not stall retention for everyone.
                logging.warning("agent_work_log_retention_failed category=%s", safe_exception(exc))
        if len(batch) < page_size:
            break
        query = query.start_after(batch[-1])
    return count

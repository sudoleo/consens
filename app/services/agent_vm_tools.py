"""The agent's VM tools: vm_exec, vm_read_file, vm_write_file and
vm_share_file (agent_vm.py).

Admins only (AgentPreferences.vm, routers/agent.py effective_preferences),
never in chats with Google data, in turns with comparison or audit tools on
the account's token ledger (DelegationLoop). One VMSession per message: on
the first VM call it records the VM on the chat (before the provider creates
it, so the chat's deletion always finds it), wakes or creates it, takes the
message's checkpoint (the state before this message changed anything) and
copies the message's attachments into INPUT_DIR. Messages that never call a
VM tool neither wake the VM nor take a checkpoint.

Each call is one activity event of its tool (agent-activity.js): what ran,
its output's end while it runs (``report``, at most every REPORT_SECONDS),
then exit code and duration. The model gets each stream's end
(MODEL_STREAM_CHARS) with the cut said in the text; in audit mode the same
result is the call's ``tool`` entry in the work log, which the reviewers
follow live. The turn keeps the summary (``agent_vm``: checkpoint, commands,
seconds). A failing VM costs its tools, never the answer: the agent gets one
short message and works on without the VM for the rest of the message.

vm_share_file gives the user a file of the VM (since 2026-10-26): it is
copied into the chat's private file store (AgentFiles, kind ``vm_file``, the
turn's id) and shown under the answer, a picture as a picture, anything else
as a download (agent-workspace.js). The VM has no public address; nothing of
it is ever a link.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import logging
import mimetypes
import posixpath
import re
import threading
import time

from pydantic import BaseModel, ConfigDict, Field

from app.core.observability import safe_exception
from app.services import agent_vm
from app.services.agent_tools import ReadOnlyTool
from app.services.error_alerts import report_server_exception
from app.services.llm.provider_runtime import ProviderCancelled

HOME = agent_vm.HOME
INPUT_DIR = HOME + "/input"
EXEC_TIMEOUT_DEFAULT = 60
EXEC_TIMEOUT_MAX = 300
# A command needs at least this long before the answer must start
# (DelegationLoop.answer_time_left); with less left it is not started.
MIN_COMMAND_SECONDS = 15
# Per stream: the end the model reads, and the end kept while it runs.
MODEL_STREAM_CHARS = 12_000
CAPTURE_BYTES = 64 * 1024
# The activity's view: both streams in arrival order, its end only.
VIEW_CHARS = 2_000
VIEW_BYTES = 12 * 1024
COMMAND_VIEW_CHARS = 2_000
REPORT_SECONDS = 1.0
READ_BYTES = 2 * 1024 * 1024
READ_CHARS = 16_000
# A shared file goes into the chat's file store, which takes up to 5 MB a file
# (AgentFiles.save).
SHARE_BYTES = 5 * 1024 * 1024
# Pictures the chat shows as pictures, known by their bytes only: a name
# never makes a file an image (agent-workspace.js shows these inline).
_IMAGE_MAGIC = ((b"\x89PNG\r\n\x1a\n", "image/png"), (b"\xff\xd8\xff", "image/jpeg"),
                (b"GIF87a", "image/gif"), (b"GIF89a", "image/gif"))
WRITE_CHARS = 100_000
TOOL_ARGUMENT_CHARS = WRITE_CHARS + 4_000

# What the agent reads when the VM fails or has no time; the activity says
# the same calmly (agent-activity.js, ``outcome``).
VM_UNAVAILABLE = ("The VM is not available right now. Continue without it for this message and do not call VM "
                  "tools again; say so if the answer needed it.")
VM_NO_TIME = ("Not enough time is left in this message for a command. Write the answer from what you have.")

_ANSI = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]|\x1b\][^\x07]*\x07")


class VmExecArgs(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    command: str = Field(min_length=1, max_length=20_000, description="Shell command, run by bash with your login environment.")
    cwd: str = Field(default="", max_length=1024, description=f"Working directory; default {HOME}.")
    timeout_seconds: int = Field(default=EXEC_TIMEOUT_DEFAULT, ge=1, le=EXEC_TIMEOUT_MAX)


class VmReadFileArgs(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    path: str = Field(min_length=1, max_length=1024)
    offset: int = Field(default=1, ge=1, description="First line to read (1-based).")
    limit: int = Field(default=400, ge=1, le=4000, description="Number of lines.")


class VmWriteFileArgs(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    path: str = Field(min_length=1, max_length=1024)
    content: str = Field(max_length=WRITE_CHARS)


class VmShareFileArgs(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    path: str = Field(min_length=1, max_length=1024)
    name: str = Field(default="", max_length=120, description="File name the user sees; default the file's own name.")


class _VMOff(ValueError):
    """The VM failed or was never reachable in this message."""


def _now():
    return datetime.now(timezone.utc).isoformat()


def _unexpected(exc, operation):
    """A failure that is not the provider's: a bug or a broken install (a
    package missing). It still costs only the VM, and is reported."""
    if not isinstance(exc, agent_vm.VMUnavailable):
        logging.warning("Agent VM %s failed unexpectedly category=%s", operation, safe_exception(exc))
        report_server_exception(exc, where=f"agent_vm.{operation}", phase="tool")


def vm_path(path):
    """An absolute, normalized path in the VM; relative paths start at HOME."""
    if "\x00" in path:
        raise ValueError("The path contains a NUL character.")
    if path == "~" or path.startswith("~/"):
        path = HOME + path[1:]
    if not path.startswith("/"):
        path = HOME + "/" + path
    return posixpath.normpath(path)


def clean(text):
    """Terminal output as text: no color codes, and of a line rewritten with
    carriage returns (a progress bar) only its last state."""
    text = _ANSI.sub("", text.replace("\r\n", "\n"))
    return "\n".join(line.rsplit("\r", 1)[-1] for line in text.split("\n"))


def tail(raw, total, limit):
    """``(text, omitted)``: the end of ``raw`` as at most ``limit`` cleaned
    characters, and how many earlier bytes of the ``total`` are left out."""
    text = clean(raw.decode("utf-8", "replace")).lstrip("�")
    omitted = max(0, total - len(raw))
    if len(text) > limit:
        cut = len(text) - limit
        omitted += len(text[:cut].encode("utf-8"))
        text = text[cut:]
    return text, omitted


def model_text(raw, total, stream):
    text, omitted = tail(raw, total, MODEL_STREAM_CHARS)
    return f"[… {omitted:,} earlier bytes of {stream} omitted …]\n{text}" if omitted else text


def file_mime(raw, name):
    """The type a shared file is stored with: pictures and PDFs by their
    bytes, other files by their name, never an image by its name alone."""
    for magic, mime in _IMAGE_MAGIC:
        if raw.startswith(magic):
            return mime
    if raw[:4] == b"RIFF" and raw[8:12] == b"WEBP":
        return "image/webp"
    if raw.startswith(b"%PDF-"):
        return "application/pdf"
    guessed = mimetypes.guess_type(name)[0]
    return guessed if guessed and not guessed.startswith("image/") else "application/octet-stream"


def _safe_name(name, used):
    base = re.sub(r"[^\w.\- ]", "_", posixpath.basename(str(name or "")).strip()).strip(". ")[:120] or "file"
    candidate, number = base, 2
    while candidate in used:
        stem, dot, extension = base.rpartition(".")
        candidate = f"{stem} ({number}).{extension}" if dot and stem else f"{base} ({number})"
        number += 1
    used.add(candidate)
    return candidate


class _Output:
    """One command's output while it runs: each stream's end for the model,
    both in arrival order for the view."""

    def __init__(self):
        self.streams = {"stdout": bytearray(), "stderr": bytearray()}
        self.sizes = {"stdout": 0, "stderr": 0}
        self.view, self.view_size = bytearray(), 0

    def add(self, stream, chunk):
        buffer = self.streams[stream]
        buffer.extend(chunk)
        del buffer[:-CAPTURE_BYTES]
        self.sizes[stream] += len(chunk)
        self.view.extend(chunk)
        del self.view[:-VIEW_BYTES]
        self.view_size += len(chunk)

    def shown(self):
        text, omitted = tail(bytes(self.view), self.view_size, VIEW_CHARS)
        return {"output": text, "output_truncated": bool(omitted)}

    def for_model(self, stream):
        return model_text(bytes(self.streams[stream]), self.sizes[stream], stream)


class VMSession:
    """The VM of one message (thread-safe). ``factory`` returns a backend or
    None without a configured provider (tests pass a fake)."""

    def __init__(self, loop, factory=None, clock=time.monotonic):
        self.loop = loop
        self._factory = factory or agent_vm.backend
        self.clock = clock
        self.name = agent_vm.vm_name(loop.uid, loop.chat_id)
        self._lock = threading.Lock()
        self.backend = None
        self.state = "idle"
        self.checkpoint = None
        self.inputs, self.skipped = [], []
        self.calls = self.commands = 0
        self.seconds = 0.0
        # The first result after the VM became ready tells the agent which
        # attachments are in INPUT_DIR.
        self._announced = False

    def ready(self, cancellation):
        with self._lock:
            if self.state == "unavailable":
                raise _VMOff(VM_UNAVAILABLE)
            if self.state == "ready":
                return
            try:
                self.backend = self._factory()
                if self.backend is None:
                    raise agent_vm.VMUnavailable("no provider configured")
                self._record()
                cancellation.raise_if_cancelled()
                self.backend.ensure(self.name)
                self._still_active()
                try:
                    self.checkpoint = self.backend.checkpoint(self.name, f"consens.io message {self.loop.turn_id}")
                except agent_vm.VMUnavailable:
                    # Works on without it: the checkpoint only marks a state to return to.
                    logging.warning("Agent VM checkpoint unavailable")
                self._copy_inputs(cancellation)
                self.state = "ready"
            except ProviderCancelled:
                raise
            except Exception as exc:
                _unexpected(exc, "start")
                self.state = "unavailable"
                raise _VMOff(VM_UNAVAILABLE) from None

    def failed(self):
        """The VM failed during a call: off for the rest of the message."""
        with self._lock:
            self.state = "unavailable"

    def _record(self):
        """The chat names its VM before the provider creates it."""
        from app.services import persistence_guard
        from app.services.chat_store import ChatNotFound
        store, uid, chat_id = self.loop.store, self.loop.uid, self.loop.chat_id
        ref = store._chat_ref(uid, chat_id)
        record = {"provider": self.backend.provider, "name": self.name}

        def operation(tx):
            persistence_guard.ensure_account_write_allowed(uid=uid, db=store.db, transaction=tx)
            data = ref.get(transaction=tx).to_dict() or {}
            if data.get("status") != "active":
                raise ChatNotFound("Chat not found")
            current = data.get("agent_vm") or {}
            if {key: current.get(key) for key in record} != record:
                tx.update(ref, {"agent_vm": {**record, "created_at": _now()}})
        try:
            store._transaction(operation)
        except Exception as exc:
            logging.warning("Agent VM record failed category=%s", safe_exception(exc))
            raise agent_vm.VMUnavailable("record") from None

    def _still_active(self):
        """A chat deleted while its VM was being created already looked for
        the VM (chat_store._purge_chat): this run deletes it instead."""
        try:
            data = self.loop.store._chat_ref(self.loop.uid, self.loop.chat_id).get().to_dict() or {}
        except Exception as exc:
            logging.warning("Agent VM chat check failed category=%s", safe_exception(exc))
            raise agent_vm.VMUnavailable("chat check") from None
        if data.get("status") != "active":
            self.backend.delete(self.name)
            raise agent_vm.VMUnavailable("chat deleted")

    def _copy_inputs(self, cancellation):
        context = self.loop.file_context
        used = set()
        for file_id in (context.file_ids if context else []):
            cancellation.raise_if_cancelled()
            try:
                data, raw = context.attachment(file_id)
            except ValueError as exc:
                logging.info("Agent VM input unavailable category=%s", safe_exception(exc))
                self.skipped.append(file_id)
                continue
            path = f"{INPUT_DIR}/{_safe_name(data.get('name'), used)}"
            self.backend.write_file(self.name, path, raw)
            self.inputs.append(path)

    def announce(self, result):
        """``result`` with the inputs, once per message."""
        with self._lock:
            if self._announced:
                return result
            self._announced = True
        extra = {"input_dir": INPUT_DIR, "inputs": list(self.inputs)} if self.inputs else {}
        if self.skipped:
            extra["inputs_unavailable"] = len(self.skipped)
        return {**result, **extra}

    def summary(self):
        """The turn's ``agent_vm``, or None when no VM tool ran."""
        if self.state == "idle":
            return None
        data = {"provider": self.backend.provider if self.backend else "", "checkpoint": self.checkpoint,
                "calls": self.calls, "commands": self.commands, "seconds": round(self.seconds, 1)}
        if self.state == "unavailable":
            data["unavailable"] = True
        return data

    def close(self):
        if self.backend is not None:
            try:
                self.backend.close()
            except Exception as exc:
                logging.info("Agent VM backend close failed category=%s", safe_exception(exc))


class VMTools:
    """The four VM tools of one message, around its VMSession."""

    def __init__(self, loop, factory=None, files=None):
        self.loop = loop
        self.session = VMSession(loop, factory)
        self._files = files
        # Shared in this message: (path, sha256) -> file, so sharing the same
        # file again gives the same download.
        self.shared = {}

    def tools(self):
        return [
            ReadOnlyTool("vm_exec", "Run a shell command in your Linux VM (bash, your home folder by default). "
                         "Returns stdout, stderr (their ends when long), exit code and duration.",
                         VmExecArgs, self.exec, activity=self._exec_activity, reports=True),
            ReadOnlyTool("vm_read_file", "Read a text file in your VM by lines.", VmReadFileArgs, self.read,
                         activity=self._path_activity, reports=True),
            ReadOnlyTool("vm_write_file", "Write a text file in your VM (creates folders, replaces the file).",
                         VmWriteFileArgs, self.write, argument_limit=TOOL_ARGUMENT_CHARS,
                         activity=self._path_activity, reports=True),
            ReadOnlyTool("vm_share_file", "Give the user a file from your VM (up to 5 MB): it appears under your "
                         "answer, a picture as a picture, any other file as a download.",
                         VmShareFileArgs, self.share, activity=self._path_activity, reports=True),
        ]

    @property
    def files(self):
        """The chat's file store, the one its uploads and documents use."""
        if self._files is None:
            context = self.loop.file_context
            if context is not None:
                self._files = context.files
            else:
                from app.services.agent_files import AgentFiles
                self._files = AgentFiles(self.loop.store.db)
        return self._files

    def _start(self, cancellation):
        with self.session._lock:
            self.session.calls += 1
        self.session.ready(cancellation)

    def _provider(self, operation, call):
        """One call to the provider: any failure turns the VM off for the rest
        of the message and becomes the agent's short message, never a failed
        answer. A missing file and Stop pass through."""
        try:
            return call()
        except (ProviderCancelled, agent_vm.VMFileMissing):
            raise
        except Exception as exc:
            _unexpected(exc, operation)
            self.session.failed()
            raise _VMOff(VM_UNAVAILABLE) from None

    def _timeout(self, requested):
        timeout = min(requested, EXEC_TIMEOUT_MAX)
        left = self.loop.answer_time_left()
        if left is not None:
            if left < MIN_COMMAND_SECONDS:
                raise ValueError(VM_NO_TIME)
            timeout = min(timeout, int(left))
        return timeout

    def exec(self, args, *, cancellation, report=None):
        report = report or (lambda fields: None)
        self._start(cancellation)
        timeout = self._timeout(args.timeout_seconds)
        cwd = vm_path(args.cwd) if args.cwd.strip() else HOME
        output = _Output()
        reported = [self.session.clock()]

        def on_output(stream, chunk):
            output.add(stream, chunk)
            now = self.session.clock()
            if now - reported[0] >= REPORT_SECONDS:
                reported[0] = now
                report(output.shown())
        report({"started_at": _now()})
        try:
            outcome = self._provider("exec", lambda: self.session.backend.exec(
                self.session.name, args.command, cwd=cwd, timeout=timeout, on_output=on_output,
                cancellation=cancellation))
        except _VMOff:
            report(output.shown())
            raise
        with self.session._lock:
            self.session.commands += 1
            self.session.seconds += outcome.seconds
        result = {"exit_code": outcome.exit_code, "timed_out": outcome.timed_out,
                  "duration_ms": int(outcome.seconds * 1000), "cwd": cwd,
                  "stdout": output.for_model("stdout"), "stderr": output.for_model("stderr")}
        if outcome.timed_out:
            result["note"] = f"The command was stopped after its time limit of {timeout} seconds."
        report({**output.shown(), "exit_code": outcome.exit_code, "timed_out": outcome.timed_out,
                "duration_ms": result["duration_ms"]})
        return self.session.announce(result)

    def read(self, args, *, cancellation, report=None):
        report = report or (lambda fields: None)
        path = vm_path(args.path)
        self._start(cancellation)
        try:
            raw, complete = self._provider("read", lambda: self.session.backend.read_file(
                self.session.name, path, limit=READ_BYTES))
        except agent_vm.VMFileMissing:
            raise ValueError(f"No file at {path}.") from None
        report({"bytes": len(raw)})
        if b"\x00" in raw[:8192]:
            return self.session.announce({"path": path, "binary": True, "bytes": len(raw),
                                          "note": "Binary file: inspect it with vm_exec (file, xxd, python)."})
        lines = raw.decode("utf-8", "replace").splitlines()
        if not complete:
            # The last line may be cut; it is read with the rest.
            lines = lines[:-1]
        chosen = lines[args.offset - 1:args.offset - 1 + args.limit]
        text, shown = "", 0
        for line in chosen:
            if len(text) + len(line) + 1 > READ_CHARS:
                break
            text += line + "\n"
            shown += 1
        last = args.offset - 1 + shown
        result = {"path": path, "first_line": args.offset, "last_line": last, "content": text}
        if complete:
            result["total_lines"] = len(lines)
        if last < len(lines):
            result["more"] = f"More lines follow: read on with offset={last + 1}."
        elif not complete:
            result["more"] = (f"The file is larger than {READ_BYTES // (1024 * 1024)} MB: read its further lines "
                              "with vm_exec (sed -n, tail).")
        return self.session.announce(result)

    def write(self, args, *, cancellation, report=None):
        report = report or (lambda fields: None)
        path = vm_path(args.path)
        self._start(cancellation)
        size = self._provider("write", lambda: self.session.backend.write_file(
            self.session.name, path, args.content.encode("utf-8")))
        report({"bytes": size})
        return self.session.announce({"path": path, "bytes": size})

    def share(self, args, *, cancellation, report=None):
        report = report or (lambda fields: None)
        path = vm_path(args.path)
        self._start(cancellation)
        try:
            raw, complete = self._provider("share", lambda: self.session.backend.read_file(
                self.session.name, path, limit=SHARE_BYTES + 1))
        except agent_vm.VMFileMissing:
            raise ValueError(f"No file at {path}.") from None
        report({"bytes": len(raw)})
        if not raw:
            raise ValueError(f"{path} is empty.")
        if not complete or len(raw) > SHARE_BYTES:
            raise ValueError(f"{path} is larger than {SHARE_BYTES // (1024 * 1024)} MB. Share a smaller file "
                             "(compress, split or shrink it).")
        key = (path, hashlib.sha256(raw).hexdigest())
        if key not in self.shared:
            name = posixpath.basename(args.name.strip() or path) or "file"
            mime = file_mime(raw, name)
            # The agent made it: nothing for the store to read out. The bytes
            # are served as a download only (routers/agent_files.py).
            meta = self.files.save(self.loop.uid, self.loop.chat_id, raw=raw, name=name, mime=mime,
                                   extraction={"status": "ready", "parts": [], "warnings": []},
                                   cancellation=cancellation,
                                   extra={"kind": "vm_file", "turn_id": self.loop.turn_id,
                                          "origin": {"source": "vm", "path": path}})
            self.shared[key] = {field: meta[field] for field in ("id", "name", "mime", "size")}
            outgoing = getattr(self.loop, "outgoing", None)
            if outgoing is not None:
                outgoing.put_nowait({"type": "resources", "files": [meta]})
        file = self.shared[key]
        return self.session.announce({"path": path, "file": file,
                                      "shown_as": "picture" if file["mime"].startswith("image/") else "download",
                                      "note": "The app shows it with your answer by itself. Do not embed it as an "
                                              "image, link it or say where it appears."})

    # --- Activity fields (DelegationLoop._execute) -----------------------------

    @staticmethod
    def _outcome(result):
        error = (result or {}).get("error") if isinstance(result, dict) else None
        return {"outcome": "unavailable"} if error == VM_UNAVAILABLE else {"outcome": "no_time"} \
            if error == VM_NO_TIME else {}

    def _exec_activity(self, args, result):
        command = args.command if len(args.command) <= COMMAND_VIEW_CHARS else \
            args.command[:COMMAND_VIEW_CHARS - 1] + "…"
        return {"command": command, "cwd": vm_path(args.cwd) if args.cwd.strip() else HOME,
                **self._outcome(result)}

    def _path_activity(self, args, result):
        try:
            path = vm_path(args.path)
        except ValueError:
            path = ""
        return {"path": path, **self._outcome(result)}

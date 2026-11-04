"""The agent's own Linux VM, one per account: the workspace (agent_workspace.py, docs/agent-mode.md
"Agent VM").

It holds the agent's commands and files, shared by the account's chats one at a time, each in its
own folder (chat_dir), and the Chrome its user watches and steers live. A browser VM of the two-VM
layout (old_browser_name) is deleted when the workspace first starts again; chats that still record
a VM of their own (vm_name) keep it until they are deleted.

Everything that knows the provider (Fly.io Sprites) lives in ``SpritesBackend`` and ``backend()``;
another provider replaces those, nothing else.

The agent has no access to what it must not have by the VM's own means, Unix users and file modes,
rather than rules on its commands: every command and file operation runs as its own user without
sudo (AGENT_USER), in a mount namespace without the provider's management socket and checkpoints and
with a /tmp of its own (agent_argv). The provider's exec and file APIs run as ``sprite``, which may
sudo: only the server's own steps use them, in SERVER_HOME, which the agent's user cannot open. So
does the browser: Chrome, its screen and its profile run as ``sprite``, its protocol on a socket in
that home. The VM never holds a secret: SPRITES_TOKEN goes only into this module's requests to
SPRITES_API, and no command gets an environment variable from the backend.

Commands use the exec WebSocket (binary frames: stdin 0x00, its end 0x04; stdout 0x01, stderr 0x02,
exit code 0x03): the plain HTTP exec relies on chunk boundaries surviving every proxy, which
Sprites' own SDK warns about."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import logging
import os
import re
import threading
import time
from typing import Callable, Optional
import unicodedata
from urllib.parse import quote, urlencode

import httpx

from app.core.observability import safe_exception

SPRITES_API = "https://api.sprites.dev"
# The policy is DNS-based, per sprite, and applies at once; nothing inside can change it, and raw
# IPs are closed under an allowlist. One policy holds for the whole VM, the agent's commands and the
# browser: the open web, without Fly.io's private network.
RULES = [{"domain": "*.internal", "action": "deny"}, {"domain": "*.flycast", "action": "deny"},
         {"domain": "*", "action": "allow"}]
# The agent's Unix user and its home, where chats' folders, notes and repositories are.
AGENT_USER = "agent"
AGENT_UID = 1500
HOME = "/home/agent"
# The provider's own user, with sudo; the agent cannot open its home.
SERVER_HOME = "/home/sprite"
TOOLS_DIR = SERVER_HOME + "/.consens/workspace"
AGENT_RUN = TOOLS_DIR + "/agent-run"
# Seconds between the command's own time limit and its forced end, and how much longer the backend
# waits for the exit frame before it kills the session itself.
KILL_GRACE_SECONDS = 5
EXIT_WAIT_SECONDS = 15
REQUEST_SECONDS = 30
# A sleeping VM's first call answers once it is up: a first browser call took up to 99 s, and a
# policy request ran into REQUEST_SECONDS.
WAKE_SECONDS = 90
# A sprite pauses within seconds of its last work and goes cold later. After this long without
# contact a command first wakes it with a REST request that waits WAKE_SECONDS, instead of meeting
# the sleep in the exec handshake (WS_OPEN_SECONDS).
WAKE_AFTER_SECONDS = 5 * 60
CHECKPOINT_SECONDS = 120
WS_OPEN_SECONDS = 20
WS_MAX_FRAME = 10 * 1024 * 1024
HANDSHAKE_RETRY_SECONDS = 1.0
STDIN_CHUNK = 256 * 1024
# How long the user's terminal goes on once its socket is gone: a reload finds a new shell.
TERMINAL_AFTER_DISCONNECT = "5s"
# Exit codes of ``timeout``: the limit passed (TERM), or KILL after the grace.
TIMEOUT_EXIT_CODES = frozenset({124, 137})
# Per stream, what a command sends through the server as it comes; the VM keeps only the last 64 KiB
# of the rest, which is what the server keeps anyway.
OUTPUT_BYTES = 8 * 1024 * 1024
# What agent-run says on stderr when it ended processes a command left in the background.
BACKGROUND_ENDED = re.compile(r"\[consens\.io\] Ended with the command: (\d+) process(?:es)? it left running in "
                              r"the background\.")
# Ending a session on Stop or a deploy's interrupt: the VM-side limit ends the command anyway, so
# this never holds the message's end long.
KILL_SECONDS = 5


class VMUnavailable(Exception):
    """The provider cannot be reached or refused the request. The message names the operation and
    the kind of failure, never data; the agent and the user get agent_vm_tools' own words."""


def _unavailable(reason):
    """VMUnavailable for ``reason``, logged where it arises."""
    logging.warning("Agent VM unavailable reason=%s", reason)
    return VMUnavailable(reason)


# When the server last reached each VM, across all messages in this process: the exec handshake is
# no place to wait for a wake.
_contact: dict[str, float] = {}
_contact_lock = threading.Lock()


def _touch(name):
    with _contact_lock:
        _contact[name] = time.monotonic()


def _asleep(name):
    """Whether ``name`` was reached before, but not within WAKE_AFTER_SECONDS. Never reached in this
    process: the session's start makes a REST request first anyway."""
    with _contact_lock:
        last = _contact.get(name)
    return last is not None and time.monotonic() - last > WAKE_AFTER_SECONDS


class VMFileMissing(FileNotFoundError):
    """No file at the path the agent named."""


class VMFileRefused(PermissionError):
    """The agent's user may not read or write there, or it is a folder; the message is for the
    agent."""


@dataclass(frozen=True)
class ExecOutcome:
    """How a command ended; ``exit_code`` is None when it never reported one (killed after its
    limit)."""
    exit_code: Optional[int]
    timed_out: bool
    seconds: float


def vm_name(uid, chat_id):
    """The name of a chat's own VM from the per-chat layout: only to delete it with its chat."""
    return "consens-" + hashlib.sha256(f"{uid}:{chat_id}".encode("utf-8")).hexdigest()[:32]


def workspace_name(uid):
    """The account's workspace VM: stable, so every chat and the account's deletion find it, and
    free of the account id."""
    return "consens-w-" + hashlib.sha256(f"workspace:{uid}".encode("utf-8")).hexdigest()[:32]


def old_browser_name(uid):
    """A browser VM of the two-VM layout: only to delete it."""
    return "consens-b-" + hashlib.sha256(f"browser:{uid}".encode("utf-8")).hexdigest()[:32]


CHATS_DIR = HOME + "/chats"

FOLDER_TITLE_CHARS = 40
FOLDER_ID_CHARS = 6
_GERMAN_LETTERS = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"})


def chat_folder(title, chat_id):
    """A chat's folder name: its title as words and the start of its id
    (``promotion-neben-dem-beruf-3f9a1c``, ``chat-…`` without a title). The id part keeps two chats
    of one title apart."""
    chat_dir(chat_id)
    text = unicodedata.normalize("NFKD", str(title or "").lower().translate(_GERMAN_LETTERS))
    words = re.sub(r"[^a-z0-9]+", "-", text.encode("ascii", "ignore").decode()).strip("-")
    if len(words) > FOLDER_TITLE_CHARS:
        # At a word's end where there is one in reach.
        cut = words[:FOLDER_TITLE_CHARS + 1]
        words = cut.rsplit("-", 1)[0] if "-" in cut else words[:FOLDER_TITLE_CHARS]
    return f"{words or 'chat'}-{str(chat_id)[:FOLDER_ID_CHARS].lower()}"


def chat_dir(chat_id, folder=None):
    """A chat's own folder: where its commands start and its attachments land, deleted with the
    chat. Without ``folder`` the id-named folder of an older chat."""
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", str(chat_id or "")):
        raise ValueError("chat id")
    if folder is not None:
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", str(folder)):
            raise ValueError("chat folder")
        return f"{CHATS_DIR}/{folder}"
    return f"{CHATS_DIR}/{chat_id}"


class VMBackend:
    """What the agent's VM tools need from a provider. Every method raises VMUnavailable when the
    provider fails; one backend per message. ``agent`` (exec and file methods): as the agent's user
    (the default); only the server's own steps pass False."""

    provider = ""

    def exists(self, name):
        raise NotImplementedError

    def ensure(self, name, rules=None):
        """Create the VM if it does not exist yet and apply the network ``rules`` (None leaves them
        as they are). True when it was created."""
        raise NotImplementedError

    def set_policy(self, name, rules):
        raise NotImplementedError

    def get_policy(self, name):
        """The VM's network rules as set_policy takes them; empty where none were ever set (open)."""
        raise NotImplementedError

    def run(self, name, argv, *, cwd, timeout, on_output: Callable[[str, bytes], None], cancellation, input=None):
        """Run ``argv`` without a shell, waiting at most ``timeout`` plus the grace; ``input`` goes
        to stdin. Raises ProviderCancelled on Stop, ending the command too."""
        raise NotImplementedError

    def exec(self, name, command, *, cwd, timeout, on_output: Callable[[str, bytes], None], cancellation,
             agent=True):
        """Run ``command`` with bash in ``cwd`` for at most ``timeout`` seconds; ``on_output(stream,
        chunk)`` gets output as it arrives."""
        return self.run(name, wrapped_command(command, timeout, agent, cwd=cwd, output=OUTPUT_BYTES),
                        cwd="/" if agent else cwd, timeout=timeout, on_output=on_output, cancellation=cancellation)

    def exec_url(self, name, argv, *, cwd, stdin, tty=None):
        """The exec WebSocket's address for ``argv`` (``tty`` = (cols, rows) for a terminal)."""
        raise NotImplementedError

    def open_stream(self, name, argv, *, cwd):
        """A command that keeps running with its stdin open: ``send(bytes)``, ``recv(timeout)`` (b""
        when nothing came, None once it ended) and ``close()``."""
        raise NotImplementedError

    def read_file(self, name, path, *, limit, agent=True):
        """``(bytes, complete)``: at most ``limit`` bytes. VMFileMissing if absent, VMFileRefused
        where the agent's user may not read."""
        raise NotImplementedError

    def write_file(self, name, path, data, *, agent=True):
        raise NotImplementedError

    def checkpoint(self, name, comment):
        raise NotImplementedError

    def restore(self, name, checkpoint):
        """Return the VM's disk to ``checkpoint``; what ran in it stops."""
        raise NotImplementedError

    def delete(self, name):
        """Delete the VM and its disk; already gone is fine."""
        raise NotImplementedError

    def delete_path(self, name, path, *, agent=True):
        """Delete a file or folder with everything in it; gone is fine."""
        raise NotImplementedError

    def move_path(self, name, source, target):
        """Rename as the agent's user: "moved", "missing" or "taken" (``target`` exists and stays
        untouched)."""
        raise NotImplementedError

    def delete_service(self, name, service):
        """Remove a service of the VM; gone is fine."""
        raise NotImplementedError

    def close(self):
        pass


# A login shell's environment without its startup noise (the Sprites .bashrc warns about ``bind`` in
# every non-interactive shell), then the command as written, without positional parameters.
SHELL_PRELUDE = ('for __profile in /etc/profile "$HOME/.profile"; do [ -r "$__profile" ] && . "$__profile"; '
                 'done >/dev/null 2>&1; __command=$1; set --; eval "$__command"')


def agent_argv(argv, timeout, cwd=HOME, *, output=None):
    """``argv`` as the agent: AGENT_RUN starts as root, hides the management socket and checkpoints
    in its own mount namespace with a /tmp of its own, becomes the agent's user with no way back
    (no-new-privs) and runs ``argv`` in ``cwd`` under ``timeout``, also when the backend's
    connection is gone.

    ``output`` (bytes, 0 for no limit): a command of the agent's own, in a cgroup of its own, so
    what it leaves in the background ends with it (background services belong to vm_start_process);
    each stream passes its first ``output`` bytes, then only its end. None: the server's own fixed
    steps."""
    options = [] if output is None else ["--output", str(int(output))]
    return ["sudo", "-n", "/bin/bash", AGENT_RUN, *options, str(int(timeout)), cwd, *argv]


def terminal_argv(timeout):
    """The user's own terminal in the workspace: a login shell through AGENT_RUN --terminal with the
    agent's rights, in its home, under ``timeout``."""
    return ["sudo", "-n", "/bin/bash", AGENT_RUN, "--terminal", str(int(timeout)), HOME, "bash", "-l"]


def wrapped_command(command, timeout, agent=True, *, cwd=HOME, output=0):
    """The argv for a shell command: bash with the login environment, the agent's through
    agent_argv, the server's own as the provider's user under ``timeout``."""
    shell = ["bash", "-c", SHELL_PRELUDE, "bash", command]
    if agent:
        return agent_argv(shell, timeout, cwd, output=output)
    return ["timeout", f"--kill-after={KILL_GRACE_SECONDS}", str(int(timeout)), *shell]


# The agent's file operations run as its user with the path as an argument, never in the command's
# text (44 missing, 45 a folder, 46 not allowed): the provider's file API may sudo, so it never
# touches a path the agent named.
READ_SCRIPT = ('[ -e "$1" ] || exit 44; [ -d "$1" ] && exit 45; [ -r "$1" ] || exit 46; '
               'exec head -c "$2" -- "$1"')
WRITE_SCRIPT = ('[ -d "$1" ] && exit 45; mkdir -p -- "$(dirname -- "$1")" 2>/dev/null || exit 46; '
                'cat > "$1" 2>/dev/null || exit 46; stat -c %s -- "$1"')
# A folder the agent made read-only gets its bits back first, or rm failed and a chat's deletion
# retried for ever; chmod -R sets a folder's bits before it goes in.
DELETE_SCRIPT = 'rm -rf -- "$1" 2>/dev/null || { chmod -R u+rwX -- "$1" 2>/dev/null; rm -rf -- "$1"; }'
# Never over something that exists (mv -T -n would still merge into an empty folder).
MOVE_SCRIPT = ('[ -e "$1" ] || [ -L "$1" ] || exit 44; { [ -e "$2" ] || [ -L "$2" ]; } && exit 47; '
               'mkdir -p -- "$(dirname -- "$2")" && mv -T -- "$1" "$2"')
FILE_SECONDS = 120


def _file_error(code, path):
    if code == 44:
        return VMFileMissing(path)
    if code == 45:
        return VMFileRefused(f"{path} is a folder, not a file.")
    if code == 46:
        return VMFileRefused(f"Permission denied: {path} (your user may not read or write there).")
    return None


# Closing without waiting for the close frame makes the library log "unexpected internal error" for
# a socket that ended as intended; this module logs the failures that matter itself.
_SOCKET_LOG = logging.getLogger("app.agent_vm.exec_socket")
_SOCKET_LOG.setLevel(logging.CRITICAL)


class SpritesBackend(VMBackend):
    provider = "sprites"

    def __init__(self, token, *, base_url=SPRITES_API, transport=None, connect=None, clock=time.monotonic):
        self._token = token
        self._base = base_url.rstrip("/")
        self._http = httpx.Client(base_url=self._base, headers={"Authorization": f"Bearer {token}"},
                                  timeout=REQUEST_SECONDS, transport=transport)
        self._connect = connect
        self._clock = clock
        # Each VM's runtime status as the last GET said ("cold", "warm", "running"): whether a
        # message met it cold.
        self.statuses = {}


    def _request(self, operation, method, path, *, missing_ok=False, **kwargs):
        """One REST call; any 2xx is success (200, 201 or 204 by operation)."""
        try:
            response = self._http.request(method, path, **kwargs)
        except httpx.HTTPError as exc:
            logging.warning("Agent VM request failed operation=%s category=%s", operation, safe_exception(exc))
            raise VMUnavailable(f"{operation}: no connection") from None
        if response.is_success or (missing_ok and response.status_code == 404):
            return response
        logging.warning("Agent VM request refused operation=%s status=%s", operation, response.status_code)
        raise VMUnavailable(f"{operation}: HTTP {response.status_code}")

    def _sprite(self, name):
        return f"/v1/sprites/{quote(name, safe='')}"

    def exists(self, name):
        return self._request("get", "GET", self._sprite(name), missing_ok=True).status_code != 404

    def _seen(self, name, response):
        try:
            status = response.json().get("status")
        except (ValueError, AttributeError):
            status = None
        if isinstance(status, str) and status:
            self.statuses[name] = status[:20]

    def ensure(self, name, rules=None):
        created = False
        response = self._request("get", "GET", self._sprite(name), missing_ok=True)
        if response.status_code != 404:
            self._seen(name, response)
        else:
            try:
                self._request("create", "POST", "/v1/sprites", json={"name": name})
                created = True
            except VMUnavailable:
                # Another message of the chat may have created it just now.
                if self._request("get", "GET", self._sprite(name), missing_ok=True).status_code == 404:
                    raise
        if rules is not None:
            self.set_policy(name, rules)
        return created

    def set_policy(self, name, rules):
        self._request("policy", "POST", self._sprite(name) + "/policy/network", json={"rules": list(rules)},
                      timeout=WAKE_SECONDS)
        _touch(name)

    def get_policy(self, name):
        # [] on a sprite whose policy was never set.
        response = self._request("policy", "GET", self._sprite(name) + "/policy/network")
        try:
            rules = response.json().get("rules")
        except (ValueError, AttributeError):
            rules = None
        if not isinstance(rules, list) or not all(isinstance(rule, dict) for rule in rules):
            logging.warning("Agent VM policy unreadable")
            raise VMUnavailable("policy: unreadable")
        return rules

    def _collect(self, name, argv, *, limit, input=None, timeout=FILE_SECONDS):
        from app.services.llm.provider_runtime import ProviderCancellation
        out = bytearray()

        def keep(stream, chunk):
            if stream == "stdout" and len(out) <= limit:
                out.extend(chunk[:limit + 1 - len(out)])
        outcome = self.run(name, argv, cwd="/", timeout=timeout, on_output=keep, cancellation=ProviderCancellation(),
                           input=input)
        return outcome.exit_code, bytes(out)

    def read_file(self, name, path, *, limit, agent=True):
        if agent:
            code, data = self._collect(name, agent_argv(["bash", "-c", READ_SCRIPT, "read", path, str(limit + 1)],
                                                        FILE_SECONDS), limit=limit + 1)
            error = _file_error(code, path)
            if error is not None:
                raise error
            if code != 0:
                raise _unavailable(f"read: exit {code}")
            return data[:limit], len(data) <= limit
        params = {"path": path, "workingDir": SERVER_HOME}
        try:
            with self._http.stream("GET", self._sprite(name) + "/fs/read", params=params,
                                   timeout=WAKE_SECONDS) as response:
                if response.status_code == 404:
                    raise VMFileMissing(path)
                if not response.is_success:
                    logging.warning("Agent VM request refused operation=read status=%s", response.status_code)
                    raise VMUnavailable(f"read: HTTP {response.status_code}")
                _touch(name)
                data = bytearray()
                for chunk in response.iter_bytes():
                    data.extend(chunk)
                    if len(data) > limit:
                        return bytes(data[:limit]), False
                return bytes(data), True
        except httpx.HTTPError as exc:
            logging.warning("Agent VM request failed operation=read category=%s", safe_exception(exc))
            raise VMUnavailable("read: no connection") from None

    def write_file(self, name, path, data, *, agent=True):
        if agent:
            code, out = self._collect(name, agent_argv(["bash", "-c", WRITE_SCRIPT, "write", path], FILE_SECONDS),
                                      limit=64, input=bytes(data))
            error = _file_error(code, path)
            if error is not None:
                raise error
            if code != 0:
                raise _unavailable(f"write: exit {code}")
            try:
                return int(out.decode().strip())
            except ValueError:
                return len(data)
        response = self._request("write", "PUT", self._sprite(name) + "/fs/write", content=data,
                                 params={"path": path, "workingDir": SERVER_HOME, "mkdir": "true"},
                                 headers={"Content-Type": "application/octet-stream"})
        _touch(name)
        try:
            return int(response.json().get("size", len(data)))
        except (ValueError, AttributeError):
            return len(data)

    def checkpoint(self, name, comment):
        # Creation streams NDJSON; its last line is "complete" or "error". The id comes from the
        # list, found by this comment.
        try:
            with self._http.stream("POST", self._sprite(name) + "/checkpoint", json={"comment": comment},
                                   timeout=CHECKPOINT_SECONDS) as response:
                if not response.is_success:
                    logging.warning("Agent VM request refused operation=checkpoint status=%s", response.status_code)
                    raise VMUnavailable(f"checkpoint: HTTP {response.status_code}")
                done = False
                for line in response.iter_lines():
                    try:
                        event = json.loads(line) if line.strip() else {}
                    except ValueError:
                        continue
                    if event.get("type") == "error":
                        logging.warning("Agent VM checkpoint failed code=%s", str(event.get("code") or "")[:40])
                        raise VMUnavailable("checkpoint: error event")
                    done |= event.get("type") == "complete"
        except httpx.HTTPError as exc:
            logging.warning("Agent VM request failed operation=checkpoint category=%s", safe_exception(exc))
            raise VMUnavailable("checkpoint: no connection") from None
        if not done:
            raise _unavailable("checkpoint: no completion")
        # The completion names the id only in its text, so the list says it.
        listed = self._request("checkpoints", "GET", self._sprite(name) + "/checkpoints").json()
        found = [item for item in listed if isinstance(item, dict) and item.get("comment") == comment]
        if not found:
            raise _unavailable("checkpoint: not listed")
        return str(max(found, key=lambda item: str(item.get("create_time") or ""))["id"])

    def restore(self, name, checkpoint):
        # Streams NDJSON like a checkpoint; "complete" or "error" ends it.
        path = f"{self._sprite(name)}/checkpoints/{quote(str(checkpoint), safe='')}/restore"
        try:
            with self._http.stream("POST", path, timeout=CHECKPOINT_SECONDS) as response:
                if not response.is_success:
                    logging.warning("Agent VM request refused operation=restore status=%s", response.status_code)
                    raise VMUnavailable(f"restore: HTTP {response.status_code}")
                done = False
                for line in response.iter_lines():
                    try:
                        event = json.loads(line) if line.strip() else {}
                    except ValueError:
                        continue
                    if event.get("type") == "error":
                        logging.warning("Agent VM restore failed code=%s", str(event.get("code") or "")[:40])
                        raise VMUnavailable("restore: error event")
                    done |= event.get("type") == "complete"
        except httpx.HTTPError as exc:
            logging.warning("Agent VM request failed operation=restore category=%s", safe_exception(exc))
            raise VMUnavailable("restore: no connection") from None
        if not done:
            raise _unavailable("restore: no completion")

    def delete(self, name):
        self._request("delete", "DELETE", self._sprite(name), missing_ok=True)

    def delete_path(self, name, path, *, agent=True):
        if agent:
            code, _ = self._collect(name, agent_argv(["bash", "-c", DELETE_SCRIPT, "delete", path], FILE_SECONDS),
                                    limit=0)
            if code != 0:
                raise _unavailable(f"delete path: exit {code}")
            return
        self._request("delete path", "DELETE", self._sprite(name) + "/fs/delete", missing_ok=True,
                      json={"path": path, "workingDir": SERVER_HOME, "recursive": True, "asRoot": False})

    def move_path(self, name, source, target):
        code, _ = self._collect(name, agent_argv(["bash", "-c", MOVE_SCRIPT, "move", source, target], FILE_SECONDS),
                                limit=0)
        outcome = {0: "moved", 44: "missing", 47: "taken"}.get(code)
        if outcome is None:
            raise _unavailable(f"move path: exit {code}")
        return outcome

    def delete_service(self, name, service):
        self._request("service", "DELETE", f"{self._sprite(name)}/services/{quote(service, safe='')}", missing_ok=True)

    def close(self):
        self._http.close()


    def _open(self, url):
        if self._connect is not None:
            return self._connect(url, self._token)
        import socket
        from websockets.sync.client import connect
        ws = connect(url, additional_headers={"Authorization": f"Bearer {self._token}"},
                     # The server keeps the socket open for seconds after the exit frame; waiting
                     # for its close frame would add that to every command.
                     open_timeout=WS_OPEN_SECONDS, ping_interval=15, ping_timeout=45, close_timeout=0,
                     max_size=WS_MAX_FRAME, logger=_SOCKET_LOG)
        try:
            # Small frames (a key press) go at once, not after the last one's acknowledgement.
            ws.socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        except (AttributeError, OSError):
            pass
        return ws

    def exec_url(self, name, argv, *, cwd, stdin, tty=None):
        """The exec WebSocket's address on SPRITES_API, the only place the token goes. ``tty``:
        (cols, rows) for a terminal, raw bytes both ways, ending TERMINAL_AFTER_DISCONNECT after its
        socket is gone."""
        params = [*(("cmd", arg) for arg in argv), ("path", argv[0]), ("dir", cwd),
                  ("stdin", "true" if stdin else "false")]
        if tty is not None:
            cols, rows = tty
            params += [("tty", "true"), ("cols", str(int(cols))), ("rows", str(int(rows))),
                       ("max_run_after_disconnect", TERMINAL_AFTER_DISCONNECT)]
        return "wss://" + self._base.split("://", 1)[-1] + self._sprite(name) + "/exec?" + urlencode(params)

    def _connect_exec(self, url, operation="exec"):
        """The exec socket; a handshake that broke off (a sprite waking) is tried once more. One
        that ran out of time is not: the command is in the request, and a second try might run it
        twice. _wake keeps that case rare."""
        from websockets.exceptions import InvalidHandshake, InvalidStatus
        for attempt in (1, 2):
            try:
                return self._open(url)
            except InvalidStatus as exc:
                status = exc.response.status_code
                logging.warning("Agent VM request refused operation=%s status=%s", operation, status)
                raise VMUnavailable(f"{operation}: HTTP {status}") from None
            except TimeoutError as exc:
                logging.warning("Agent VM request failed operation=%s attempt=%s category=%s", operation, attempt,
                                safe_exception(exc))
                raise VMUnavailable(f"{operation}: handshake timed out") from None
            except (OSError, InvalidHandshake) as exc:
                logging.warning("Agent VM request failed operation=%s attempt=%s category=%s", operation, attempt,
                                safe_exception(exc))
                if attempt == 2:
                    raise VMUnavailable(f"{operation}: no connection") from None
                time.sleep(HANDSHAKE_RETRY_SECONDS)

    def _wake(self, name):
        """A VM not reached for WAKE_AFTER_SECONDS is woken by a REST request that waits
        WAKE_SECONDS before a command's handshake meets its sleep. Best effort."""
        if not _asleep(name):
            return
        try:
            self._http.request("GET", self._sprite(name) + "/fs/list", params={"path": "/"}, timeout=WAKE_SECONDS)
            _touch(name)
        except httpx.HTTPError as exc:
            logging.info("Agent VM wake failed category=%s", safe_exception(exc))

    def run(self, name, argv, *, cwd, timeout, on_output, cancellation, input=None):
        from websockets.exceptions import ConnectionClosed
        url = self.exec_url(name, argv, cwd=cwd, stdin=input is not None)
        cancellation.raise_if_cancelled()
        self._wake(name)
        cancellation.raise_if_cancelled()
        ws = self._connect_exec(url)
        # From the open socket: a handshake that waited for the VM never eats the limit.
        started = self._clock()
        _touch(name)
        # Stop closes the socket at once; the loop below then ends the command.
        unregister = cancellation.register(ws)
        session, exit_code, killed = None, None, False
        deadline = started + timeout + KILL_GRACE_SECONDS + EXIT_WAIT_SECONDS
        try:
            if input is not None:
                try:
                    for start in range(0, len(input), STDIN_CHUNK):
                        ws.send(b"\x00" + input[start:start + STDIN_CHUNK])
                    ws.send(b"\x04")
                except (ConnectionClosed, OSError) as exc:
                    logging.warning("Agent VM request failed operation=stdin category=%s", safe_exception(exc))
                    raise VMUnavailable("exec: stdin not sent") from None
            while True:
                left = deadline - self._clock()
                if left <= 0:
                    killed = True
                    break
                try:
                    message = ws.recv(timeout=min(left, 1.0))
                except TimeoutError:
                    if cancellation.cancelled:
                        break
                    continue
                except ConnectionClosed:
                    break
                if isinstance(message, str):
                    try:
                        info = json.loads(message)
                    except ValueError:
                        continue
                    if info.get("type") == "session_info":
                        session = str(info.get("session_id") or "") or None
                    elif info.get("type") == "exit" and isinstance(info.get("exit_code"), int):
                        exit_code = info["exit_code"]
                        break
                    continue
                if not message:
                    continue
                stream, payload = message[0], bytes(message[1:])
                if stream == 1 and payload:
                    on_output("stdout", payload)
                elif stream == 2 and payload:
                    on_output("stderr", payload)
                elif stream == 3:
                    exit_code = payload[0] if payload else 0
                    break
        finally:
            unregister()
            try:
                ws.close()
            except Exception:
                pass
        if exit_code is None and session and (killed or cancellation.cancelled):
            # The VM-side limit ends it too; this only ends it sooner.
            self._kill(name, session)
        cancellation.raise_if_cancelled()
        seconds = self._clock() - started
        _touch(name)
        if exit_code is None and not killed:
            raise _unavailable("exec: connection closed before the exit code")
        timed_out = killed or (exit_code in TIMEOUT_EXIT_CODES and seconds >= timeout)
        return ExecOutcome(exit_code=None if killed else exit_code, timed_out=timed_out, seconds=seconds)

    def open_stream(self, name, argv, *, cwd):
        return _ExecStream(self._connect_exec(self.exec_url(name, argv, cwd=cwd, stdin=True)))

    def _kill(self, name, session):
        try:
            with self._http.stream("POST", f"{self._sprite(name)}/exec/{quote(session, safe='')}/kill",
                                   params={"signal": "SIGKILL"}, timeout=KILL_SECONDS) as response:
                for _ in response.iter_lines():
                    pass
        except httpx.HTTPError as exc:
            logging.info("Agent VM session kill failed category=%s", safe_exception(exc))


class _ExecStream:
    """A running command's stdin and stdout over the exec WebSocket."""

    def __init__(self, ws):
        self.ws = ws
        self._send_lock = threading.Lock()

    def send(self, data):
        with self._send_lock:
            for start in range(0, len(data), STDIN_CHUNK):
                self.ws.send(b"\x00" + data[start:start + STDIN_CHUNK])

    def recv(self, timeout):
        from websockets.exceptions import ConnectionClosed
        try:
            message = self.ws.recv(timeout=timeout)
        except TimeoutError:
            return b""
        except ConnectionClosed:
            return None
        if isinstance(message, str):
            try:
                ended = json.loads(message).get("type") == "exit"
            except (ValueError, AttributeError):
                ended = False
            return None if ended else b""
        if not message or message[0] == 2:
            return b""
        return bytes(message[1:]) if message[0] == 1 else None

    def close(self):
        """Never waits for a send that hangs: its socket goes under it instead."""
        if self._send_lock.acquire(blocking=False):
            try:
                self.ws.send(b"\x04")
            except Exception:
                pass
            finally:
                self._send_lock.release()
        else:
            _shutdown(self.ws)
        try:
            self.ws.close()
        except Exception:
            pass


def _shutdown(ws):
    import socket
    try:
        ws.socket.shutdown(socket.SHUT_RDWR)
    except (AttributeError, OSError):
        pass


def configured():
    return bool(os.getenv("SPRITES_TOKEN", "").strip())


def open_to_all():
    """AGENT_VM_ACCESS=all ("pro" means the same): the VM and its browser for every account, held in
    check by the token account and the day's VM time. Otherwise only admins get it."""
    return os.getenv("AGENT_VM_ACCESS", "").strip().lower() in {"all", "pro"}


def on_demand():
    """The workspace on demand: a message starts without its tools until the agent opens it.
    AGENT_WORKSPACE_ON_DEMAND=off gives them from the start."""
    return os.getenv("AGENT_WORKSPACE_ON_DEMAND", "").strip().lower() != "off"


def backend():
    """The configured provider for one message, or None without one."""
    token = os.getenv("SPRITES_TOKEN", "").strip()
    return SpritesBackend(token) if token else None


VM_RESTORED_NOTE = ("Before this message the user restored your VM to how it was before an earlier message: "
                    "whatever later commands changed there is gone, background processes included. Check the files "
                    "before you rely on them.")
# The workspace's page is the user's, not what the agent last saw.
HANDED_BACK_NOTE = ("The user worked in the workspace's browser themselves and handed it back to you {minutes} min "
                    "ago: what it shows may have changed since you last looked.")


def restore_workspace(uid, checkpoint, *, factory=None):
    """Return the account's workspace to ``checkpoint`` (agent_workspace.restorable decides which
    may). Raises VMUnavailable without or on failure of the provider."""
    vm = (factory or backend)()
    if vm is None:
        raise _unavailable("restore: no provider configured")
    try:
        vm.restore(workspace_name(uid), checkpoint)
    finally:
        vm.close()


def delete_chat_vm(uid, chat_id, record, *, factory=None, store=None):
    """What a chat recorded goes with it: its folder in the workspace with the background processes
    it started, and its own VM from the per-chat layout. That VM's name comes from the chat, never
    from the record, which a chat that moved to the workspace lost. Raises when the provider fails,
    so the deletion job retries and none of the chat's files outlives it."""
    if not isinstance(record, dict) or not record.get("name"):
        return
    name = record["name"]
    if name not in {workspace_name(uid), vm_name(uid, chat_id)}:
        # Written by this app only; anything else is not ours to delete.
        logging.warning("Agent VM record does not match its chat")
        return
    vm = (factory or backend)()
    if vm is None:
        raise VMUnavailable("delete: no provider configured")
    try:
        if name == workspace_name(uid) and vm.exists(name):
            from app.services import agent_vm_processes, agent_workspace
            agent_workspace.prepare(vm, name)
            # Its processes first: they run in its folder. ``store``: the VM time they did not use
            # comes back.
            refund = None
            if store is not None:
                from app.services import agent_vm_time
                refund = lambda seconds, day: agent_vm_time.refund(store, uid, seconds, day)  # noqa: E731
            agent_vm_processes.delete_for_chat(vm, name, chat_id, refund=refund)
            # By the name the chat recorded, and by its id while a rename has not happened yet.
            folder = record.get("folder")
            if isinstance(folder, str) and re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", folder):
                vm.delete_path(name, chat_dir(chat_id, folder))
            vm.delete_path(name, chat_dir(chat_id))
        vm.delete(vm_name(uid, chat_id))
    finally:
        vm.close()


def delete_workspace(uid, *, factory=None):
    """Delete the account's workspace with its account, and an old browser VM where it is still
    there, by the names that follow from the account, so a record already gone never hides them."""
    vm = (factory or backend)()
    if vm is None:
        raise VMUnavailable("delete: no provider configured")
    try:
        vm.delete(workspace_name(uid))
        vm.delete(old_browser_name(uid))
    finally:
        vm.close()

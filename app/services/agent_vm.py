"""The agent's own Linux VMs (docs/agent-mode.md, "Agent VM", "Arbeitsplatz").

Since 2026-10-27 two per account, the workspace (agent_workspace.py): the
workbench (workspace_name), where the agent's commands and files are, shared
by the account's chats one at a time, each in its own folder (chat_dir); and
the browser (browser_name), the Chrome its user watches and steers live and
the agent uses through the ``browser`` tool (agent_browser.py). Before, each
chat had a VM of its own (vm_name); chats that still record one keep it
until they are deleted.

A small interface (``VMBackend``) with one implementation on Fly.io Sprites
(``SpritesBackend``). Everything that knows the provider lives in this file:
moving to another one (E2B) replaces ``SpritesBackend`` and ``backend()``,
nothing else. The tools the agent calls, the per-message session and the
activity events are in agent_vm_tools.py.

The agent has no access to what it must not have, by the VM's own means
rather than rules on its commands (security audit 2026-10-27). On the
workbench every command of the agent, and every file its tools read or
write, runs as its own Unix user without sudo (AGENT_USER), in a mount
namespace without the provider's management socket and checkpoints
(workspace_vm/workbench/agent-run, started as root by ``agent_argv``). The
provider's exec and file APIs run as ``sprite``, which may sudo: only the
server's own steps use them directly, in SERVER_HOME, which the agent's user
cannot open. The workbench reaches only package registries (WORKBENCH_RULES)
and what the user allowed for the chat (agent_domains.py); the browser the
open web (BROWSER_RULES), with no code of the agent in it.

The VMs never hold a secret: the provider token (SPRITES_TOKEN) goes only
into the headers of this module's requests to SPRITES_API, never to a VM's
own address, and no command gets an environment variable from the backend.

Sprites API (https://docs.fly.io/sprites/api): REST over HTTPS for the
sprite, its files, network policy and checkpoints; commands over the exec
WebSocket, whose binary frames carry stdin (0x00, its end 0x04) to the VM and
stdout (0x01), stderr (0x02) and the exit code (0x03) back. The plain HTTP
exec streams the same frames without lengths and relies on HTTP chunk
boundaries surviving every proxy (Sprites' own JS SDK warns about it), so
commands use the WebSocket.
"""
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
# The policy is DNS-based, per sprite, and applies at once (measured on a
# Sprite 2026-10-27: a closed domain gets REFUSED, raw IPs are closed under an
# allowlist, nothing inside can change it). The workbench reaches the package
# registries its tools install from and nothing else (since 2026-10-27; from
# 2026-10-26 it had the open web): what the agent wrote there leaves only
# through tools the reviewers see and the user decides on. npm's registry
# also takes uploads (PUT), a known rest risk Max accepted. GitHub stays
# closed: github_import brings repositories in through the backend.
WORKBENCH_DOMAINS = ("archive.ubuntu.com", "*.archive.ubuntu.com", "security.ubuntu.com", "ports.ubuntu.com",
                     "pypi.org", "files.pythonhosted.org", "registry.npmjs.org")
WORKBENCH_RULES = [{"domain": domain, "action": "allow"} for domain in WORKBENCH_DOMAINS]
# The browser reaches the open web like any browser, Fly.io's private network
# (*.internal, *.flycast) not.
BROWSER_RULES = [{"domain": "*.internal", "action": "deny"}, {"domain": "*.flycast", "action": "deny"},
                 {"domain": "*", "action": "allow"}]
# The agent's Unix user on the workbench (created by workspace_vm/workbench/
# setup.sh) and its home, where its chats' folders, notes and repositories are.
AGENT_USER = "agent"
AGENT_UID = 1500
HOME = "/home/agent"
# The provider's own user (exec and file API), with sudo; the agent cannot open its home.
SERVER_HOME = "/home/sprite"
TOOLS_DIR = SERVER_HOME + "/.consens/workspace"
AGENT_RUN = TOOLS_DIR + "/agent-run"
# Seconds between the command's own time limit (the VM-side ``timeout``)
# and its forced end, and how much longer the backend waits for the exit
# frame before it kills the session itself.
KILL_GRACE_SECONDS = 5
EXIT_WAIT_SECONDS = 15
REQUEST_SECONDS = 30
# What may wake a sleeping VM (its network rules, a file of the provider's
# user): its first call after a while answers once the VM is up. Measured in
# Prod 2026-10-28/29: a first browser call of a message took up to 99 s, and
# a policy request ran into REQUEST_SECONDS (the browser was off for the
# message, the live view did not open).
WAKE_SECONDS = 90
CHECKPOINT_SECONDS = 120
WS_OPEN_SECONDS = 20
WS_MAX_FRAME = 10 * 1024 * 1024
HANDSHAKE_RETRY_SECONDS = 1.0
# Bytes per stdin frame (0x00 + data); the stdin's end is 0x04.
STDIN_CHUNK = 256 * 1024
# How long the user's terminal goes on once its socket is gone (the
# provider's max_run_after_disconnect): a reload finds a new shell.
TERMINAL_AFTER_DISCONNECT = "5s"
# Exit codes of ``timeout``: the limit passed (TERM), or KILL after the grace.
TIMEOUT_EXIT_CODES = frozenset({124, 137})


class VMUnavailable(Exception):
    """The provider cannot be reached or refused the request. The message is
    for logs only; the agent and the user get agent_vm_tools' own words."""


class VMFileMissing(FileNotFoundError):
    """No file at the path the agent named."""


class VMFileRefused(PermissionError):
    """The agent's user may not read or write there, or it is a folder; the
    message names the path and is for the agent."""


@dataclass(frozen=True)
class ExecOutcome:
    """How a command ended. ``exit_code`` is None when it never reported one
    (killed after its time limit); its output went to ``on_output``."""
    exit_code: Optional[int]
    timed_out: bool
    seconds: float


def vm_name(uid, chat_id):
    """The name of a chat's own VM (before 2026-10-27): only to delete it
    with its chat."""
    return "consens-" + hashlib.sha256(f"{uid}:{chat_id}".encode("utf-8")).hexdigest()[:32]


def workspace_name(uid):
    """The account's workbench VM: stable, so every chat and the account's
    deletion find the same VM, and free of the account id."""
    return "consens-w-" + hashlib.sha256(f"workspace:{uid}".encode("utf-8")).hexdigest()[:32]


def browser_name(uid):
    """The account's browser VM, next to its workbench (since 2026-10-27)."""
    return "consens-b-" + hashlib.sha256(f"browser:{uid}".encode("utf-8")).hexdigest()[:32]


CHATS_DIR = HOME + "/chats"
# Where the chats' folders were before the agent had a user of its own
# (moved by workspace_vm/workbench/setup.sh).
LEGACY_CHATS_DIR = SERVER_HOME + "/chats"


FOLDER_TITLE_CHARS = 40
FOLDER_ID_CHARS = 6
_GERMAN_LETTERS = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"})


def chat_folder(title, chat_id):
    """The name of a chat's folder since 2026-10-28: its title as words and
    the start of its id, ``promotion-neben-dem-beruf-3f9a1c`` (``chat-…``
    while it has no title yet). The id part keeps two chats of one title
    apart; the folder follows a new title (agent_workspace.make_chat_dir)."""
    chat_dir(chat_id)
    text = unicodedata.normalize("NFKD", str(title or "").lower().translate(_GERMAN_LETTERS))
    words = re.sub(r"[^a-z0-9]+", "-", text.encode("ascii", "ignore").decode()).strip("-")
    if len(words) > FOLDER_TITLE_CHARS:
        # At a word's end where there is one in reach.
        cut = words[:FOLDER_TITLE_CHARS + 1]
        words = cut.rsplit("-", 1)[0] if "-" in cut else words[:FOLDER_TITLE_CHARS]
    return f"{words or 'chat'}-{str(chat_id)[:FOLDER_ID_CHARS].lower()}"


def chat_dir(chat_id, folder=None):
    """A chat's own folder in the workspace: where its commands start and its
    attachments land, deleted with the chat. ``folder``: its name as the
    chat records it (chat_folder); without one the folder of a chat from
    before 2026-10-28, named by its id."""
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", str(chat_id or "")):
        raise ValueError("chat id")
    if folder is not None:
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", str(folder)):
            raise ValueError("chat folder")
        return f"{CHATS_DIR}/{folder}"
    return f"{CHATS_DIR}/{chat_id}"


class VMBackend:
    """What the agent's VM tools need from a provider. Every method raises
    VMUnavailable when the provider fails; ``close`` ends the backend's
    connections (one backend per message). ``agent`` (exec and the file
    methods): as the agent's user on the workbench (agent_argv), the
    default; only the server's own steps pass False, in SERVER_HOME or on
    the browser VM."""

    provider = ""

    def exists(self, name):
        """Whether the VM exists (a deletion never creates one)."""
        raise NotImplementedError

    def ensure(self, name, rules=None):
        """Create the VM if it does not exist yet and apply the network
        ``rules`` (WORKBENCH_RULES, agent_domains.rules); None leaves them as
        they are (the browser VM sets its rules with a new version of its
        tools, agent_workspace.prepare_browser). True when it was created."""
        raise NotImplementedError

    def set_policy(self, name, rules):
        """Replace the VM's network rules; they apply at once."""
        raise NotImplementedError

    def get_policy(self, name):
        """The VM's network rules now, as set_policy takes them (a list of
        ``{"domain", "action"}``); empty where none were ever set (open)."""
        raise NotImplementedError

    def run(self, name, argv, *, cwd, timeout, on_output: Callable[[str, bytes], None], cancellation, input=None):
        """Run ``argv`` as given (no shell around it), wait at most
        ``timeout`` seconds plus the grace for its end. ``input``: bytes for
        its stdin, which then ends. Returns ExecOutcome; raises
        ProviderCancelled on Stop (the command is then ended as well)."""
        raise NotImplementedError

    def exec(self, name, command, *, cwd, timeout, on_output: Callable[[str, bytes], None], cancellation,
             agent=True):
        """Run ``command`` with bash in ``cwd`` for at most ``timeout`` seconds
        (wrapped_command). ``on_output(stream, chunk)`` gets stdout/stderr as
        they arrive."""
        return self.run(name, wrapped_command(command, timeout, agent, cwd=cwd), cwd="/" if agent else cwd,
                        timeout=timeout, on_output=on_output, cancellation=cancellation)

    def exec_url(self, name, argv, *, cwd, stdin, tty=None):
        """The exec WebSocket's address for ``argv`` (the live view's relay,
        the user's terminal with ``tty`` = (cols, rows))."""
        raise NotImplementedError

    def open_stream(self, name, argv, *, cwd):
        """A command that keeps running with its stdin open (tunnel.py on
        both VMs, agent_tunnel): an object with ``send(bytes)`` for stdin,
        ``recv(timeout)`` for stdout's next bytes (b"" when nothing came, None
        once it ended) and ``close()``."""
        raise NotImplementedError

    def read_file(self, name, path, *, limit, agent=True):
        """``(bytes, complete)``: at most ``limit`` bytes of the file;
        ``complete`` is False when it is longer. VMFileMissing if absent,
        VMFileRefused where the agent's user may not read."""
        raise NotImplementedError

    def write_file(self, name, path, data, *, agent=True):
        """Write ``data`` (creating parent folders); returns its size."""
        raise NotImplementedError

    def checkpoint(self, name, comment):
        """Snapshot the VM's disk; returns the checkpoint's id."""
        raise NotImplementedError

    def restore(self, name, checkpoint):
        """Return the VM's disk to ``checkpoint``; what ran in it stops."""
        raise NotImplementedError

    def delete(self, name):
        """Delete the VM and its disk; a VM that is already gone is fine."""
        raise NotImplementedError

    def delete_path(self, name, path, *, agent=True):
        """Delete a file or folder with everything in it; gone is fine."""
        raise NotImplementedError

    def move_path(self, name, source, target):
        """Rename a file or folder as the agent's user (a chat's folder after
        a new title): "moved", "missing" (no ``source``, nothing to do) or
        "taken" (``target`` exists and stays untouched)."""
        raise NotImplementedError

    def delete_service(self, name, service):
        """Remove a service of the VM (the live view's gateway before
        2026-10-27); gone is fine."""
        raise NotImplementedError

    def close(self):
        pass


# A login shell's environment (PATH with the image's and the user's tools,
# language settings) without its startup noise: the profile files run
# silently (the Sprites .bashrc warns about ``bind`` in every non-interactive
# shell), then the command runs as written, without positional parameters.
SHELL_PRELUDE = ('for __profile in /etc/profile "$HOME/.profile"; do [ -r "$__profile" ] && . "$__profile"; '
                 'done >/dev/null 2>&1; __command=$1; set --; eval "$__command"')


def agent_argv(argv, timeout, cwd=HOME):
    """``argv`` as the agent on the workbench: the provider's user starts
    AGENT_RUN as root (sudo), which hides the management socket and the
    checkpoints in a mount namespace of its own, becomes the agent's user
    with no way back (setpriv --no-new-privs), goes to ``cwd`` and runs
    ``argv`` under coreutils ``timeout`` (workspace_vm/workbench/agent-run).
    So a command never outlives its limit, also when the backend's
    connection is gone, and nothing of it, nor anything it starts, has more
    rights than that user."""
    return ["sudo", "-n", "/bin/bash", AGENT_RUN, str(int(timeout)), cwd, *argv]


def terminal_argv(timeout):
    """The user's own terminal on the workbench (routers/agent_workspace.py,
    since 2026-10-28): a login shell through AGENT_RUN --terminal, with the
    agent's rights and nothing more, in the agent's home, under ``timeout``."""
    return ["sudo", "-n", "/bin/bash", AGENT_RUN, "--terminal", str(int(timeout)), HOME, "bash", "-l"]


def wrapped_command(command, timeout, agent=True, *, cwd=HOME):
    """The argv the VM runs for a shell command: bash with the login
    environment (SHELL_PRELUDE), the agent's through agent_argv, the
    server's own as the provider's user under ``timeout``."""
    shell = ["bash", "-c", SHELL_PRELUDE, "bash", command]
    if agent:
        return agent_argv(shell, timeout, cwd)
    return ["timeout", f"--kill-after={KILL_GRACE_SECONDS}", str(int(timeout)), *shell]


# The agent's file operations, as its user (agent_argv) with the path as an
# argument, never in the command's text: 44 no such file, 45 a folder, 46
# not allowed. The provider's file API runs as its own user, which may sudo,
# so it never touches a path the agent named.
READ_SCRIPT = ('[ -e "$1" ] || exit 44; [ -d "$1" ] && exit 45; [ -r "$1" ] || exit 46; '
               'exec head -c "$2" -- "$1"')
WRITE_SCRIPT = ('[ -d "$1" ] && exit 45; mkdir -p -- "$(dirname -- "$1")" 2>/dev/null || exit 46; '
                'cat > "$1" 2>/dev/null || exit 46; stat -c %s -- "$1"')
DELETE_SCRIPT = 'rm -rf -- "$1"'
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


# Closing without waiting for the server's close frame (above) makes the
# library's reader log "unexpected internal error" with a trace for a socket
# that ended as intended (seen on a Sprite 2026-10-27); this module logs the
# failures that matter itself.
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

    # --- REST -----------------------------------------------------------------

    def _request(self, operation, method, path, *, missing_ok=False, **kwargs):
        """One REST call; any 2xx is success (the API answers 200, 201 or
        204 depending on the operation, the policy for instance with 204)."""
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

    def ensure(self, name, rules=None):
        created = False
        if self._request("get", "GET", self._sprite(name), missing_ok=True).status_code == 404:
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

    def get_policy(self, name):
        # {"rules": [...]}, [] on a sprite whose policy was never set (measured 2026-10-28).
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
        """``(exit_code, stdout)`` of a short command, at most ``limit`` bytes kept."""
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
                raise VMUnavailable(f"read: exit {code}")
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
                raise VMUnavailable(f"write: exit {code}")
            try:
                return int(out.decode().strip())
            except ValueError:
                return len(data)
        response = self._request("write", "PUT", self._sprite(name) + "/fs/write", content=data,
                                 params={"path": path, "workingDir": SERVER_HOME, "mkdir": "true"},
                                 headers={"Content-Type": "application/octet-stream"})
        try:
            return int(response.json().get("size", len(data)))
        except (ValueError, AttributeError):
            return len(data)

    def checkpoint(self, name, comment):
        # Creation streams its progress as NDJSON; its last line is "complete"
        # or "error". The id comes from the list, found by this comment.
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
            raise VMUnavailable("checkpoint: no completion")
        listed = self._request("checkpoints", "GET", self._sprite(name) + "/checkpoints").json()
        found = [item for item in listed if isinstance(item, dict) and item.get("comment") == comment]
        if not found:
            raise VMUnavailable("checkpoint: not listed")
        return str(max(found, key=lambda item: str(item.get("create_time") or ""))["id"])

    def restore(self, name, checkpoint):
        # Streams its progress as NDJSON like a checkpoint; "complete" or "error" ends it.
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
            raise VMUnavailable("restore: no completion")

    def delete(self, name):
        self._request("delete", "DELETE", self._sprite(name), missing_ok=True)

    def delete_path(self, name, path, *, agent=True):
        if agent:
            code, _ = self._collect(name, agent_argv(["bash", "-c", DELETE_SCRIPT, "delete", path], FILE_SECONDS),
                                    limit=0)
            if code != 0:
                raise VMUnavailable(f"delete path: exit {code}")
            return
        self._request("delete path", "DELETE", self._sprite(name) + "/fs/delete", missing_ok=True,
                      json={"path": path, "workingDir": SERVER_HOME, "recursive": True, "asRoot": False})

    def move_path(self, name, source, target):
        code, _ = self._collect(name, agent_argv(["bash", "-c", MOVE_SCRIPT, "move", source, target], FILE_SECONDS),
                                limit=0)
        outcome = {0: "moved", 44: "missing", 47: "taken"}.get(code)
        if outcome is None:
            raise VMUnavailable(f"move path: exit {code}")
        return outcome

    def delete_service(self, name, service):
        self._request("service", "DELETE", f"{self._sprite(name)}/services/{quote(service, safe='')}", missing_ok=True)

    def close(self):
        self._http.close()

    # --- Commands -------------------------------------------------------------

    def _open(self, url):
        if self._connect is not None:
            return self._connect(url, self._token)
        import socket
        from websockets.sync.client import connect
        ws = connect(url, additional_headers={"Authorization": f"Bearer {self._token}"},
                     # The server keeps the socket open for seconds after the
                     # exit frame; waiting for its close frame would add that
                     # to every command (the Sprites SDKs do not wait either).
                     open_timeout=WS_OPEN_SECONDS, ping_interval=15, ping_timeout=45, close_timeout=0,
                     max_size=WS_MAX_FRAME, logger=_SOCKET_LOG)
        try:
            # Small frames go at once (a request through the tunnel, a key
            # press), not after the last one's acknowledgement (Nagle).
            ws.socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        except (AttributeError, OSError):
            pass
        return ws

    def exec_url(self, name, argv, *, cwd, stdin, tty=None):
        """The exec WebSocket's address on SPRITES_API, the only place the
        token goes (the live view and the terminal use it too,
        routers/agent_workspace.py). ``tty``: (cols, rows) for a terminal,
        whose frames are raw bytes both ways and which ends
        TERMINAL_AFTER_DISCONNECT after its socket is gone."""
        params = [*(("cmd", arg) for arg in argv), ("path", argv[0]), ("dir", cwd),
                  ("stdin", "true" if stdin else "false")]
        if tty is not None:
            cols, rows = tty
            params += [("tty", "true"), ("cols", str(int(cols))), ("rows", str(int(rows))),
                       ("max_run_after_disconnect", TERMINAL_AFTER_DISCONNECT)]
        return "wss://" + self._base.split("://", 1)[-1] + self._sprite(name) + "/exec?" + urlencode(params)

    def _connect_exec(self, url, operation="exec"):
        """The exec socket; a handshake that broke off (a sprite waking from
        its sleep, seen 2026-10-27) is tried once more: no command started."""
        from websockets.exceptions import InvalidHandshake, InvalidStatus
        for attempt in (1, 2):
            try:
                return self._open(url)
            except InvalidStatus as exc:
                status = exc.response.status_code
                logging.warning("Agent VM request refused operation=%s status=%s", operation, status)
                raise VMUnavailable(f"{operation}: HTTP {status}") from None
            except (OSError, TimeoutError, InvalidHandshake) as exc:
                logging.warning("Agent VM request failed operation=%s attempt=%s category=%s", operation, attempt,
                                safe_exception(exc))
                if attempt == 2:
                    raise VMUnavailable(f"{operation}: no connection") from None
                time.sleep(HANDSHAKE_RETRY_SECONDS)

    def run(self, name, argv, *, cwd, timeout, on_output, cancellation, input=None):
        from websockets.exceptions import ConnectionClosed
        url = self.exec_url(name, argv, cwd=cwd, stdin=input is not None)
        cancellation.raise_if_cancelled()
        started = self._clock()
        ws = self._connect_exec(url)
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
        if exit_code is None and not killed:
            raise VMUnavailable("exec: connection closed before the exit code")
        timed_out = killed or (exit_code in TIMEOUT_EXIT_CODES and seconds >= timeout)
        return ExecOutcome(exit_code=None if killed else exit_code, timed_out=timed_out, seconds=seconds)

    def open_stream(self, name, argv, *, cwd):
        return _ExecStream(self._connect_exec(self.exec_url(name, argv, cwd=cwd, stdin=True)))

    def _kill(self, name, session):
        try:
            with self._http.stream("POST", f"{self._sprite(name)}/exec/{quote(session, safe='')}/kill",
                                   params={"signal": "SIGKILL"}) as response:
                for _ in response.iter_lines():
                    pass
        except httpx.HTTPError as exc:
            logging.info("Agent VM session kill failed category=%s", safe_exception(exc))


class _ExecStream:
    """A running command's stdin and stdout over the exec WebSocket
    (open_stream): frames 0x00 in, 0x01 out; the exit ends it."""

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
        """Never waits for a send that hangs (a stalled connection): its
        socket goes under it instead."""
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


def open_to_pro():
    """AGENT_VM_ACCESS=pro: the VM comes with every account's audit (Pro and
    admins). Otherwise, the default since the workspace's security audit of
    2026-10-27, only admins get it; Pro's audit runs without a VM."""
    return os.getenv("AGENT_VM_ACCESS", "").strip().lower() == "pro"


def on_demand():
    """The workspace on demand (docs/agent-mode.md "Arbeitsplatz auf Abruf"),
    since 2026-10-29 for every account with the VM (Pro and admins): a message
    starts without the workspace's tools until the agent opens it
    (DelegationLoop._open_workspace). AGENT_WORKSPACE_ON_DEMAND=off, the
    emergency off, gives them from the start again."""
    return os.getenv("AGENT_WORKSPACE_ON_DEMAND", "").strip().lower() != "off"


def backend():
    """The configured provider for one message, or None without one."""
    token = os.getenv("SPRITES_TOKEN", "").strip()
    return SpritesBackend(token) if token else None


# What the next message is told after the user restored the VM (the turn's
# app context, routers/agent.py run_agent).
VM_RESTORED_NOTE = ("Before this message the user restored your VM to how it was before an earlier message: "
                    "whatever later commands changed there is gone, background processes included. Check the files "
                    "before you rely on them.")
# The user handed the workspace's browser back shortly before this message
# (routers/agent.py browser_turn): its page is theirs, not what you last saw.
HANDED_BACK_NOTE = ("The user worked in the workspace's browser themselves and handed it back to you {minutes} min "
                    "ago: what it shows may have changed since you last looked.")


def restore_workspace(uid, checkpoint, *, factory=None):
    """Return the account's workspace to ``checkpoint``, one of its own
    (agent_workspace.restorable decides which may go back). Raises
    VMUnavailable when there is no provider or it fails."""
    vm = (factory or backend)()
    if vm is None:
        raise VMUnavailable("restore: no provider configured")
    try:
        vm.restore(workspace_name(uid), checkpoint)
    finally:
        vm.close()


def delete_chat_vm(uid, chat_id, record, *, factory=None):
    """What a chat recorded (chat field ``agent_vm``) goes with the chat: its
    folder in the account's workbench, and the chat's own VM from before
    2026-10-27. That one's name comes from the chat (vm_name), never from
    the record: a chat that moved to the workspace lost it there, and its VM
    stayed (security audit 2026-10-27). The folder goes as the agent's user
    (its tools brought up to date first, agent_workspace.prepare) and from
    where it was before the agent had a user of its own (LEGACY_CHATS_DIR).
    Gone already is fine. Raises when the provider fails or is not
    configured: the chat's deletion job then retries
    (chat_store.run_chat_deletion), so none of the chat's files outlives it."""
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
            from app.services import agent_workspace
            agent_workspace.prepare(vm, name)
            # The folder by the name the chat recorded (since 2026-10-28), and
            # by its id, as before and while a rename has not happened yet.
            folder = record.get("folder")
            if isinstance(folder, str) and re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", folder):
                vm.delete_path(name, chat_dir(chat_id, folder))
            vm.delete_path(name, chat_dir(chat_id))
            vm.delete_path(name, f"{LEGACY_CHATS_DIR}/{chat_dir(chat_id).rsplit('/', 1)[1]}", agent=False)
        vm.delete(vm_name(uid, chat_id))
    finally:
        vm.close()


def delete_workspace(uid, *, factory=None):
    """Delete the account's workspace with its account (agent_workspace.py):
    the workbench with every chat's folder, and the browser with its
    sign-ins. By the names that follow from the account, so a record
    already gone never hides them; gone already is fine."""
    vm = (factory or backend)()
    if vm is None:
        raise VMUnavailable("delete: no provider configured")
    try:
        vm.delete(workspace_name(uid))
        vm.delete(browser_name(uid))
    finally:
        vm.close()

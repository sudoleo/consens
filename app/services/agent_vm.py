"""The agent's own Linux VM, one per chat (docs/agent-mode.md, "Agent VM").

A small interface (``VMBackend``) with one implementation on Fly.io Sprites
(``SpritesBackend``). Everything that knows the provider lives in this file:
moving to another one (E2B) replaces ``SpritesBackend`` and ``backend()``,
nothing else. The tools the agent calls, the per-message session and the
activity events are in agent_vm_tools.py.

The VM never holds a secret: the provider token (SPRITES_TOKEN) goes only
into the headers of this module's own requests, no command gets an
environment variable from the backend, and the VM reaches only the package
registries and developer services of the provider's default network policy
(EGRESS_RULES), applied whenever a message first uses the VM.

Sprites API (https://docs.fly.io/sprites/api): REST over HTTPS for the
sprite, its files, network policy and checkpoints; commands over the exec
WebSocket, whose binary frames carry stdout (0x01), stderr (0x02) and the
exit code (0x03). The plain HTTP exec streams the same frames without
lengths and relies on HTTP chunk boundaries surviving every proxy (Sprites'
own JS SDK warns about it), so commands use the WebSocket.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import logging
import os
import time
from typing import Callable, Optional
from urllib.parse import quote, urlencode

import httpx

from app.core.observability import safe_exception

SPRITES_API = "https://api.sprites.dev"
# The provider's default allowlist: GitHub, npm, PyPI, Docker Hub and the
# major AI APIs. Everything else is refused by DNS, so a page the agent read
# cannot have it send the chat's files to a server of its choosing.
EGRESS_RULES = [{"include": "defaults"}]
HOME = "/home/sprite"
# Seconds between the command's own time limit (the VM-side ``timeout``)
# and its forced end, and how much longer the backend waits for the exit
# frame before it kills the session itself.
KILL_GRACE_SECONDS = 5
EXIT_WAIT_SECONDS = 15
REQUEST_SECONDS = 30
CHECKPOINT_SECONDS = 120
WS_OPEN_SECONDS = 20
WS_MAX_FRAME = 10 * 1024 * 1024
# Exit codes of ``timeout``: the limit passed (TERM), or KILL after the grace.
TIMEOUT_EXIT_CODES = frozenset({124, 137})


class VMUnavailable(Exception):
    """The provider cannot be reached or refused the request. The message is
    for logs only; the agent and the user get agent_vm_tools' own words."""


class VMFileMissing(FileNotFoundError):
    """No file at the path the agent named."""


@dataclass(frozen=True)
class ExecOutcome:
    """How a command ended. ``exit_code`` is None when it never reported one
    (killed after its time limit); its output went to ``on_output``."""
    exit_code: Optional[int]
    timed_out: bool
    seconds: float


def vm_name(uid, chat_id):
    """The chat's VM name: stable, so every message (and the chat's
    deletion) finds the same VM, and free of the account id."""
    return "consens-" + hashlib.sha256(f"{uid}:{chat_id}".encode("utf-8")).hexdigest()[:32]


class VMBackend:
    """What the agent's VM tools need from a provider. Every method raises
    VMUnavailable when the provider fails; ``close`` ends the backend's
    connections (one backend per message)."""

    provider = ""

    def ensure(self, name):
        """Create the VM if it does not exist yet and apply EGRESS_RULES."""
        raise NotImplementedError

    def exec(self, name, command, *, cwd, timeout, on_output: Callable[[str, bytes], None], cancellation):
        """Run ``command`` with bash in ``cwd`` for at most ``timeout`` seconds.
        ``on_output(stream, chunk)`` gets stdout/stderr as they arrive.
        Returns ExecOutcome; raises ProviderCancelled on Stop (the command
        is then ended in the VM as well)."""
        raise NotImplementedError

    def read_file(self, name, path, *, limit):
        """``(bytes, complete)``: at most ``limit`` bytes of the file;
        ``complete`` is False when it is longer. VMFileMissing if absent."""
        raise NotImplementedError

    def write_file(self, name, path, data):
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

    def close(self):
        pass


# A login shell's environment (PATH with the image's and the user's tools,
# language settings) without its startup noise: the profile files run
# silently (the Sprites .bashrc warns about ``bind`` in every non-interactive
# shell), then the command runs as written, without positional parameters.
SHELL_PRELUDE = ('for __profile in /etc/profile "$HOME/.profile"; do [ -r "$__profile" ] && . "$__profile"; '
                 'done >/dev/null 2>&1; __command=$1; set --; eval "$__command"')


def wrapped_command(command, timeout):
    """The argv the VM runs: bash with the login environment (SHELL_PRELUDE)
    under coreutils ``timeout``, so a command never outlives its limit, also
    when the backend's connection is gone."""
    return ["timeout", f"--kill-after={KILL_GRACE_SECONDS}", str(int(timeout)), "bash", "-c", SHELL_PRELUDE,
            "bash", command]


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

    def ensure(self, name):
        if self._request("get", "GET", self._sprite(name), missing_ok=True).status_code == 404:
            try:
                self._request("create", "POST", "/v1/sprites", json={"name": name})
            except VMUnavailable:
                # Another message of the chat may have created it just now.
                if self._request("get", "GET", self._sprite(name), missing_ok=True).status_code == 404:
                    raise
        self._request("policy", "POST", self._sprite(name) + "/policy/network", json={"rules": EGRESS_RULES})

    def read_file(self, name, path, *, limit):
        params = {"path": path, "workingDir": HOME}
        try:
            with self._http.stream("GET", self._sprite(name) + "/fs/read", params=params) as response:
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

    def write_file(self, name, path, data):
        response = self._request("write", "PUT", self._sprite(name) + "/fs/write", content=data,
                                 params={"path": path, "workingDir": HOME, "mkdir": "true"},
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

    def close(self):
        self._http.close()

    # --- Commands -------------------------------------------------------------

    def _open(self, url):
        if self._connect is not None:
            return self._connect(url, self._token)
        from websockets.sync.client import connect
        return connect(url, additional_headers={"Authorization": f"Bearer {self._token}"},
                       # The server keeps the socket open for seconds after the
                       # exit frame; waiting for its close frame would add that
                       # to every command (the Sprites SDKs do not wait either).
                       open_timeout=WS_OPEN_SECONDS, ping_interval=15, ping_timeout=45, close_timeout=0,
                       max_size=WS_MAX_FRAME)

    def exec(self, name, command, *, cwd, timeout, on_output, cancellation):
        from websockets.exceptions import ConnectionClosed, InvalidStatus
        argv = wrapped_command(command, timeout)
        query = urlencode([*(("cmd", arg) for arg in argv), ("path", argv[0]), ("dir", cwd), ("stdin", "false")])
        url = "wss://" + self._base.split("://", 1)[-1] + self._sprite(name) + "/exec?" + query
        cancellation.raise_if_cancelled()
        started = self._clock()
        try:
            ws = self._open(url)
        except InvalidStatus as exc:
            status = exc.response.status_code
            logging.warning("Agent VM request refused operation=exec status=%s", status)
            raise VMUnavailable(f"exec: HTTP {status}") from None
        except (OSError, TimeoutError) as exc:
            logging.warning("Agent VM request failed operation=exec category=%s", safe_exception(exc))
            raise VMUnavailable("exec: no connection") from None
        # Stop closes the socket at once; the loop below then ends the command.
        unregister = cancellation.register(ws)
        session, exit_code, killed = None, None, False
        deadline = started + timeout + KILL_GRACE_SECONDS + EXIT_WAIT_SECONDS
        try:
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

    def _kill(self, name, session):
        try:
            with self._http.stream("POST", f"{self._sprite(name)}/exec/{quote(session, safe='')}/kill",
                                   params={"signal": "SIGKILL"}) as response:
                for _ in response.iter_lines():
                    pass
        except httpx.HTTPError as exc:
            logging.info("Agent VM session kill failed category=%s", safe_exception(exc))


def configured():
    return bool(os.getenv("SPRITES_TOKEN", "").strip())


def backend():
    """The configured provider for one message, or None without one."""
    token = os.getenv("SPRITES_TOKEN", "").strip()
    return SpritesBackend(token) if token else None


# What the next message is told after the user restored the VM (the turn's
# app context, routers/agent.py run_agent).
VM_RESTORED_NOTE = ("Before this message the user restored your VM to how it was before an earlier message: "
                    "whatever later commands changed there is gone, background processes included. Check the files "
                    "before you rely on them.")


def restore_chat_vm(uid, chat_id, record, checkpoint, *, factory=None):
    """Return the chat's VM (chat field ``agent_vm``) to ``checkpoint``.
    Raises VMUnavailable when there is none or the provider fails."""
    if not isinstance(record, dict) or record.get("name") != vm_name(uid, chat_id):
        raise VMUnavailable("restore: no VM of this chat")
    vm = (factory or backend)()
    if vm is None:
        raise VMUnavailable("restore: no provider configured")
    try:
        vm.restore(record["name"], checkpoint)
    finally:
        vm.close()


def delete_chat_vm(uid, chat_id, record, *, factory=None):
    """Delete the VM a chat recorded (chat field ``agent_vm``) with the chat.
    Raises when the provider fails or is not configured: the chat's deletion
    job then retries (chat_store.run_chat_deletion), so no VM with the
    user's files outlives their chat."""
    if not isinstance(record, dict) or not record.get("name"):
        return
    if record["name"] != vm_name(uid, chat_id):
        # Written by this app only; anything else is not ours to delete.
        logging.warning("Agent VM record does not match its chat")
        return
    vm = (factory or backend)()
    if vm is None:
        raise VMUnavailable("delete: no provider configured")
    try:
        vm.delete(record["name"])
    finally:
        vm.close()

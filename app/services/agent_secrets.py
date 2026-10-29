"""A key the agent needs from the user (ask_user with ``secret``, since
2026-10-29, docs/agent-mode.md "Arbeitsplatz").

An app the agent builds often needs an API key or a token of the user's.
Typed into the chat, it would sit in the chat's history, go to every model
of the run and into the work record. Now the agent asks for it by name
(OPENAI_API_KEY), the user pastes it into a field on the card, and the
server writes it straight to the workbench, as the agent's user, into
``~/.secrets/<name>`` (only that user reads it, like a .env of the user's
computer): never into Firestore, a log or a model's context. The agent hears
the path and uses the file in its commands.

What a command or a page then shows of a saved key is masked in what the
run keeps and the models read (scrub: tool results, activity, work record),
as ``[secret ~/.secrets/<name>, hidden from you]``: an `echo $KEY` by
mistake never reaches a chat, and the mask says where the key is and that
the file is fine (agents took a bare mask for a placeholder in the file). The names stay on the account's
record (``secret_names``, never the values), so every message's VM start
reads the keys again (load, VMSession.ready) and a restart of the server
masks them as well; the agent hears their names with its first VM result.
A key stays on the workbench until the user deletes it (their terminal).
"""
from __future__ import annotations

import re
import threading
import time

from app.services import agent_vm

NAME = re.compile(r"^[A-Z][A-Z0-9_]{1,63}$")
DIR = agent_vm.HOME + "/.secrets"
VALUE_CHARS = 16_384
SAVE_SECONDS = 60
SCRUB_SECONDS = 24 * 3600
# Shorter values would mask ordinary words of a page or an output.
SCRUB_MIN_CHARS = 8
MASK = "[secret ~/.secrets/{name}, hidden from you]"
KEEP_NAMES = 32
# With the first VM result of a message whose account holds keys.
KEYS_NOTE = ("Keys the user gave you through ask_user, one file each: read the file in the same command line "
             "that needs it, never print it, and ask again only for a key not here.")
LOAD_SECONDS = 30
# Every key the record names, as name NUL value NUL, read as the agent's
# user; a deleted one is left out.
LOAD_SCRIPT = ('cd "$HOME/.secrets" 2>/dev/null || exit 0; for name in "$@"; do [ -f "$name" ] || continue; '
               'printf "%s\\0" "$name"; head -c 16384 -- "$name"; printf "\\0"; done')
# As the agent's user, readable by it alone, written whole (a half-written
# key is never read): the name comes as an argument, never in the text.
SAVE_SCRIPT = ('umask 077 && mkdir -p -- "$HOME/.secrets" && chmod 700 -- "$HOME/.secrets" && '
               'cat > "$HOME/.secrets/.$1.part" && mv -f -- "$HOME/.secrets/.$1.part" "$HOME/.secrets/$1"')


def path(name):
    return f"{DIR}/{name}"


def save(vm, uid, name, value, cancellation, db=None):
    """Writes the key to the account's workbench; VMUnavailable when it
    could not. ``value`` loses only its surrounding whitespace. Its name
    goes on the account's record (never the value)."""
    from app.services import agent_workspace
    if not NAME.fullmatch(name):
        raise ValueError("No such key name.")
    value = value.strip()
    if not value or len(value) > VALUE_CHARS:
        raise ValueError("The key is empty or too long.")
    workbench = agent_workspace.open_workbench(vm, uid, cancellation)
    outcome = vm.run(workbench, agent_vm.agent_argv(["bash", "-c", SAVE_SCRIPT, "bash", name], SAVE_SECONDS,
                                                    agent_vm.HOME),
                     cwd="/", timeout=SAVE_SECONDS, on_output=lambda stream, chunk: None,
                     cancellation=cancellation, input=value.encode("utf-8"))
    if outcome.exit_code != 0:
        raise agent_vm.VMUnavailable(f"secret: exit {outcome.exit_code}")
    remember(uid, value, name)
    if db is not None:
        from app.services import agent_workspace
        agent_workspace.remember_values(db, uid, "secret_names", [name], keep=KEEP_NAMES)
    return path(name)


def load(vm, workbench, uid, names, cancellation):
    """Reads the keys ``names`` on the workbench again, for scrub only:
    their values go nowhere else. Returns the seconds it took."""
    names = [name for name in dict.fromkeys(names) if NAME.fullmatch(str(name))][:KEEP_NAMES]
    if not names:
        return 0.0
    out = bytearray()

    def keep(stream, chunk):
        if stream == "stdout" and len(out) <= KEEP_NAMES * (VALUE_CHARS + 80):
            out.extend(chunk)
    outcome = vm.run(workbench, agent_vm.agent_argv(["bash", "-c", LOAD_SCRIPT, "bash", *names], LOAD_SECONDS,
                                                    agent_vm.HOME),
                     cwd="/", timeout=LOAD_SECONDS, on_output=keep, cancellation=cancellation)
    parts = bytes(out).split(b"\0")
    for name, value in zip(parts[0::2], parts[1::2]):
        text = value.decode("utf-8", "replace").strip()
        if text and NAME.fullmatch(name.decode("ascii", "replace")):
            remember(uid, text, name.decode("ascii"))
    return outcome.seconds


_seen: dict[str, dict[str, tuple[float, str]]] = {}
_lock = threading.Lock()


def remember(uid, value, name, now=None):
    if len(value) < SCRUB_MIN_CHARS:
        return
    with _lock:
        _seen.setdefault(uid, {})[value] = ((now or time.time()) + SCRUB_SECONDS, name)


def _values(uid, now=None):
    """``(value, mask)`` of the account's keys, the longest first: one key may hold another."""
    now = now or time.time()
    with _lock:
        seen = _seen.get(uid)
        if not seen:
            return []
        for value in [value for value, (until, _) in seen.items() if until <= now]:
            del seen[value]
        return [(value, MASK.format(name=name)) for value, (_, name) in
                sorted(seen.items(), key=lambda item: len(item[0]), reverse=True)]


def scrub(uid, data, now=None):
    """``data`` (str, dict, list) with every saved key of the account masked."""
    values = _values(uid, now)
    return _masked(data, values) if values else data


def _masked(data, values):
    if isinstance(data, str):
        for value, mask in values:
            if value in data:
                data = data.replace(value, mask)
        return data
    if isinstance(data, dict):
        return {key: _masked(item, values) for key, item in data.items()}
    if isinstance(data, (list, tuple)):
        return type(data)(_masked(item, values) for item in data)
    return data

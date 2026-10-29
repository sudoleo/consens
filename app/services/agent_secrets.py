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
for SCRUB_SECONDS in this process: an `echo $KEY` by mistake never reaches a
chat. It stays on the workbench until the user deletes it (their terminal).
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
MASK = "[secret]"
# As the agent's user, readable by it alone, written whole (a half-written
# key is never read): the name comes as an argument, never in the text.
SAVE_SCRIPT = ('umask 077 && mkdir -p -- "$HOME/.secrets" && chmod 700 -- "$HOME/.secrets" && '
               'cat > "$HOME/.secrets/.$1.part" && mv -f -- "$HOME/.secrets/.$1.part" "$HOME/.secrets/$1"')


def path(name):
    return f"{DIR}/{name}"


def save(vm, uid, name, value, cancellation):
    """Writes the key to the account's workbench; VMUnavailable when it
    could not. ``value`` loses only its surrounding whitespace."""
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
    remember(uid, value)
    return path(name)


_seen: dict[str, dict[str, float]] = {}
_lock = threading.Lock()


def remember(uid, value, now=None):
    if len(value) < SCRUB_MIN_CHARS:
        return
    with _lock:
        _seen.setdefault(uid, {})[value] = (now or time.time()) + SCRUB_SECONDS


def _values(uid, now=None):
    now = now or time.time()
    with _lock:
        seen = _seen.get(uid)
        if not seen:
            return []
        for value in [value for value, until in seen.items() if until <= now]:
            del seen[value]
        # The longest first: one key may hold another.
        return sorted(seen, key=len, reverse=True)


def scrub(uid, data, now=None):
    """``data`` (str, dict, list) with every saved key of the account masked."""
    values = _values(uid, now)
    return _masked(data, values) if values else data


def _masked(data, values):
    if isinstance(data, str):
        for value in values:
            if value in data:
                data = data.replace(value, MASK)
        return data
    if isinstance(data, dict):
        return {key: _masked(item, values) for key, item in data.items()}
    if isinstance(data, (list, tuple)):
        return type(data)(_masked(item, values) for item in data)
    return data

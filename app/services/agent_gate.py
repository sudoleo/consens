"""Which of the agent's calls act outside its workspace (since 2026-10-27).

In audit mode such a call runs only once the reviewers let it
(agent_audit.AnswerAudit.gate, docs/agent-work-log.md "Vor dem Aufruf"): a
reviewer's halt came only after the call before, because the app logs a step
and runs it at once while a round takes seconds.

The app decides by the tool and its typed arguments, never by reading text:
the browser's actions that send something or go somewhere (open, click,
Enter, Space, upload) and a request for a domain (request_domain, which the user
decides after the reviewers, DelegationLoop._domain_wait). Shell commands
are not on it since the workbench's network is closed (security audit
2026-10-27, agent_domains.py): until the user allowed a domain, a command
reaches nothing but the package registries, whatever it says. Before, a
list of patterns guessed which commands talked to the network.

A memory change (update_memory) joins them once outside content is in view
(since 2026-10-28): it acts on later chats, and a page could have suggested
it. Before, memory simply locked for the rest of the message.
"""
from __future__ import annotations

import json

# browser actions that act outside: always, or with one argument set.
BROWSER_OUTWARD = frozenset({"open", "click", "upload", "download"})
# Keys that send: Enter submits, Space presses the focused button like a click.
BROWSER_OUTWARD_KEYS = frozenset({"Enter", "Space"})


def _arguments(call):
    arguments = ((call or {}).get("function") or {}).get("arguments")
    try:
        args = json.loads(arguments) if isinstance(arguments, str) else arguments
    except ValueError:
        return {}
    return args if isinstance(args, dict) else {}


def outward(call, *, memory_exposed=False):
    """Why ``call`` waits for the reviewers ("browser", "domain", "memory"),
    or None for a call that stays inside the workspace. ``memory_exposed``:
    outside content is in view (DelegationLoop.outside_in_view), so a memory
    change may come from a page rather than the user (since 2026-10-28 it
    waits for the reviewers instead of being refused)."""
    name = ((call or {}).get("function") or {}).get("name")
    if name == "request_domain":
        return "domain"
    if name == "update_memory":
        return "memory" if memory_exposed else None
    if name != "browser":
        return None
    args = _arguments(call)
    action = args.get("action")
    if action in BROWSER_OUTWARD or (action == "key" and args.get("key") in BROWSER_OUTWARD_KEYS) \
            or (action == "type" and args.get("enter") is True):
        return "browser"
    return None

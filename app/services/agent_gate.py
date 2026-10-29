"""Which of the agent's calls wait for the reviewers before they run (since 2026-10-27).

In audit mode such a call runs only once the reviewers let it
(agent_audit.AnswerAudit.gate, docs/agent-work-log.md "Vor dem Aufruf"): a
reviewer's halt came only after the call before, because the app logs a step
and runs it at once while a round takes seconds.

The app decides by the tool and its typed arguments, never by reading text:
a request for a domain (request_domain, which the user decides after the
reviewers, DelegationLoop._domain_wait) and a memory change (update_memory)
once outside content is in view: it acts on later chats, and a page could
have suggested it (since 2026-10-28; before, memory simply locked for the
rest of the message). Shell commands are not on it since the workbench's
network is closed (security audit 2026-10-27, agent_domains.py): until the
user allowed a domain, a command reaches nothing but the package registries,
whatever it says.

Browser actions that send something or go somewhere (open, click, Enter,
upload) and pages the server fetched for the agent (read_source, show_image)
waited here from 2026-10-27/28 until 2026-10-29. In three days of Prod 30 such
rounds cost a median 3.9 s per click (up to 13 s, one turn almost a minute),
and each of their 4 halts was a false alarm the user let run (a link from a
search hit, a picture, a move in an online game). The one real prompt
injection so far was halted in an ordinary live round, while the agent read
the file. So the reviewers follow those steps live like any other (Max,
2026-10-29), and a step that acts in the user's name goes to the user
instead: the agent asks before it (agent_ask.py).
"""
from __future__ import annotations


def outward(call, *, memory_exposed=False):
    """Why ``call`` waits for the reviewers ("domain", "memory"), or None.
    ``memory_exposed``: outside content is in view
    (DelegationLoop.outside_in_view), so a memory change may come from a page
    rather than the user (since 2026-10-28 it waits for the reviewers instead
    of being refused)."""
    name = ((call or {}).get("function") or {}).get("name")
    if name == "request_domain":
        return "domain"
    if name == "update_memory":
        return "memory" if memory_exposed else None
    return None

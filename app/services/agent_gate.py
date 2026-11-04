"""Which of the agent's calls wait for the reviewers before they run (2026-10-27
to 2026-11-04; since then none).

Such a call runs only once the reviewers let it
(agent_audit.AnswerAudit.gate, docs/agent-work-log.md "Vor dem Aufruf"): a
reviewer's halt came only after the call before, because the app logs a step
and runs it at once while a round takes seconds.

The app decides by the tool and its typed arguments, never by reading text.
The last call on it was a request for a domain (request_domain, which the
user decided after the reviewers): it went with the closed network of the
workbench when the browser moved onto it (2026-11-04, agent_vm.RULES). A
memory change (update_memory) with outside content in view was on it from
2026-10-28 to 2026-11-02: the agent decides what to keep, and the user sees
and can undo every change (Max). Shell commands were never on it. The gate
itself (agent_audit.AnswerAudit.open_gate, DelegationLoop._gate_wait) stays
for a call that may need it again.

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


def outward(call):
    """Why ``call`` waits for the reviewers, or None: none does now."""
    return None

"""Which of the agent's calls wait for the reviewers before they run: none at present.

Such a call runs only once the reviewers let it
(agent_audit.AnswerAudit.open_gate, DelegationLoop._gate_wait,
docs/agent-work-log.md "Vor dem Aufruf"): otherwise a reviewer's halt comes
only after the call, because the app logs a step and runs it at once while a
round takes seconds. The gate stays for a call that may need it again. The
app decides by the tool and its typed arguments, never by reading text.

A memory change (update_memory) does not wait: the agent decides what to
keep, and the user sees and can undo every change (Max). Browser actions that
send something or go somewhere (open, click, Enter, upload) and pages the
server fetched for the agent (read_source, show_image) do not wait either.
When they did, 30 such rounds in three days of Prod cost a median 3.9 s per
click (up to 13 s, one turn almost a minute), and each of their 4 halts was a
false alarm the user let run (a link from a search hit, a picture, a move in
an online game). The one real prompt injection so far was halted in an
ordinary live round, while the agent read the file. So the reviewers follow
those steps live like any other (Max), and a step that acts in the user's
name goes to the user instead: the agent asks before it (agent_ask.py).
"""
from __future__ import annotations


def outward(call):
    """Why ``call`` waits for the reviewers, or None: none does now."""
    return None

"""Where the Agent writes its answer: in a step of its own or as its last step.

Separate (the default): the orchestrator ends its steering with ``answer`` and
the app starts a fresh, tool-free answer step of the same model with its own
prompt and an evidence message (``DelegationLoop._write_synthesis``). That step
reads the whole conversation and every comparison answer a second time,
without prompt cache, and knows only what the app puts into its evidence.

Merged (``AGENT_MERGED_ANSWER=1``, 2026-10-14): the agent writes the answer
itself, as plain text in a step without tool calls. After a comparison the
same call that reads the answers writes the answer; a direct answer is one
call instead of two. The agent keeps everything it did in this message in its
context (tool results, pages read, its own decisions), so the answer needs no
separate facts about the app or the turn. docs/agent-mode.md, "Antwort im
selben Aufruf", describes the flow; scripts/evaluate_agent_answer_mode.py
compares both paths live.

Off by default until that live comparison has confirmed quality, time and
cost. A turn reads the switch once (DelegationLoop) and keeps its mode.
"""
from __future__ import annotations

import os

ENABLED_ENV = "AGENT_MERGED_ANSWER"

# A merged step's text streams only once it is this long and no tool call has
# started: a short preamble before a tool call ("I'll compare this.") never
# shows. Greetings and other short answers appear at once when the step ends.
ANSWER_HOLD_CHARS = 300

# Text a step streamed and then took back (a tool call followed) stays visible
# as one progress line of at most this many characters.
NOTE_CHARS = 400

# Text replies a merged turn holds back because a rule requires a tool first
# (own research without a comparison). After that many the reply stands: the
# turn ends with an answer instead of failing.
TOOL_REMINDERS = 1

# Tools that change nothing an answer rests on. A step that shows its answer
# and calls only these keeps the text as the answer (DelegationLoop.
# _answered_with_tools); any other tool call makes the text a preamble.
SIDE_TOOLS = frozenset({"update_memory", "prepare_watch"})


def enabled() -> bool:
    """On only with AGENT_MERGED_ANSWER=1."""
    return os.environ.get(ENABLED_ENV, "0").strip() == "1"

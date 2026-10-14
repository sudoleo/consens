"""How the Agent writes its answer: as the last message of its own tool loop.

The agent writes the answer itself, as plain text in a step without tool
calls. After a comparison the same call that reads the answers writes the
answer; a direct answer is one call. The agent keeps everything it did in
this message in its context (tool results, pages read, its own decisions), so
the answer needs no separate facts about the app or the turn.
docs/agent-mode.md, "Die Antwort schreibt der Agent selbst", describes the
flow; scripts/evaluate_agent_answers.py measures it live.

Until 2026-10-14 the orchestrator ended its steering with an ``answer`` tool
and a fresh, tool-free answer step of the same model wrote the answer from an
evidence message, reading the conversation and every comparison answer a
second time without prompt cache (git tag agent-separate-answer-last).
"""
from __future__ import annotations

# A step's text streams only once it is this long and no tool call has
# started: a short preamble before a tool call ("I'll compare this.") never
# shows. Greetings and other short answers appear at once when the step ends.
ANSWER_HOLD_CHARS = 300

# Text a step streamed and then took back (a tool call followed) stays visible
# as one progress line of at most this many characters.
NOTE_CHARS = 400

# Text replies a turn holds back because a rule requires a tool first (own
# research without a comparison). After that many the reply stands: the turn
# ends with an answer instead of failing.
TOOL_REMINDERS = 1

# Tools that change nothing an answer rests on. A step that shows its answer
# and calls only these keeps the text as the answer (DelegationLoop.
# _answered_with_tools); any other tool call makes the text a preamble.
SIDE_TOOLS = frozenset({"update_memory", "prepare_watch"})

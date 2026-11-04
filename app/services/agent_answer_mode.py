"""Constants of the agent writing its own answer: plain text in a step without tool calls (docs/agent-mode.md,
"Die Antwort schreibt der Agent selbst")."""
from __future__ import annotations

# A step's text streams once it is this long and no tool call has started, so a short preamble before a call
# never shows.
ANSWER_HOLD_CHARS = 300

# Text written alongside a tool call stays in the timeline as a progress note of at most this many characters.
NOTE_CHARS = 8000

# A step that shows its answer and calls only these keeps its text as the answer
# (AgentLoop._answered_with_tools).
SIDE_TOOLS = frozenset({"update_memory", "prepare_watch", "prepare_settings_change", "update_plan",
                        "prepare_pull_request", "report_finding", "finish_watch"})

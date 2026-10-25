"""Read-only catalog of the system prompts, built from code at call time.

Prompts are maintained in code and ship with a deploy; the admin only
displays this catalog. Add a prompt by appending one entry to ``_ENTRIES``.
Imports are lazy so this module never takes part in an import cycle.
"""
from __future__ import annotations

import re

# Clock line of ``llm.base.get_date_context``; replaced so the catalog shows
# the template instead of the second at which the admin opened it.
_DATE_CONTEXT = re.compile(r"Current date: .*?local timezone are unknown unless provided\.", re.S)
DATE_PLACEHOLDER = "[Current date, reference time and timezone: added at request time]"


def _defaults(key):
    from app.services.prompt_defaults import DEFAULT_PROMPTS
    return DEFAULT_PROMPTS[key]


def _comparison():
    from app.services.agent_comparison import SEARCH_ROUNDS, comparison_system_prompt
    return _DATE_CONTEXT.sub(DATE_PLACEHOLDER, comparison_system_prompt("full", SEARCH_ROUNDS["full"]), count=1)


def _reviewer():
    from app.services.agent_audit import review_system_prompt
    from app.services.prompt_config import DEFAULT_TIMEZONE
    return _DATE_CONTEXT.sub(DATE_PLACEHOLDER, review_system_prompt(DEFAULT_TIMEZONE), count=1)


def _vm():
    from app.services.prompt_defaults import AGENT_VM_PROMPT
    return AGENT_VM_PROMPT


def _delegation(name):
    from app.services import agent_delegation_config
    return agent_delegation_config.PROMPTS[name]


# (key, label, used_for, source, text factory) in display order.
_ENTRIES = (
    ("agent", "Agent: instructions",
     "System prompt of the user's selected Agent model: it steers the run (comparisons, depth, memory, tools) "
     "and writes the answer itself as its last message (WRITING THE ANSWER, AGENT_ANSWER_SECTION). At runtime "
     "the comparison settings, the per-message comparison limit and the source reading "
     "(AGENT_READ_SOURCE_PROMPT), file, document, Google, Watch (agent_watch.py), settings (agent_settings.py; reading and Watch not in chats "
     "with Google data) and memory instructions are appended (in chats with Google data also a no-web-search "
     "note); date, reference time and selected model travel with the latest user message. After each "
     "comparison that returned answers the app adds AGENT_WRITE_NOTE as its own message (the answer is the "
     "next message: complete, from all answers; depth only steered the comparison models).",
     "prompt_defaults.py:AGENT_SYSTEM_PROMPT", lambda: _defaults("agent")),
    ("comparison", "Agent: comparison models",
     "System prompt of each independent comparison model, shown for depth \"full\" (3 search rounds). "
     "Quick depth allows one search round and adds brief-answer guidance instead. The date line is "
     "filled in per request; in chats with Google data a no-web-search note is appended.",
     "agent_comparison.py:comparison_system_prompt()", _comparison),
    ("agent_audit", "Agent: audit mode instructions",
     "System prompt of the Agent model instead of \"Agent: instructions\" when an admin switched on Audit instead "
     "of comparison (agent_audit.py): no comparison tools, the agent researches with its own web search in every "
     "step and writes the answer itself (AGENT_AUDIT_ANSWER_SECTION). At runtime the source reading "
     "(AGENT_AUDIT_READ_SOURCE_PROMPT), file, document, Google, Watch, settings and memory instructions are "
     "appended as for the agent; the memory rules without comparisons (agent_memory.without_comparisons).",
     "prompt_defaults.py:AGENT_AUDIT_SYSTEM_PROMPT", lambda: _defaults("agent_audit")),
    ("audit_reviewer", "Agent audit: reviewers",
     "System prompt of each comparison model in audit mode: it follows the agent's work log in rounds (each user "
     "message holds the new entries as JSON, up to two search rounds each) and reviews the fixed answer in a final "
     "round (the rest of the log and the answer, up to three search rounds); the message's files go along. The "
     "date line is filled in per request.",
     "agent_audit.py:review_system_prompt()", _reviewer),
    ("agent_vm", "Agent: Linux VM",
     "Appended to \"Agent: instructions\" or \"Agent: audit mode instructions\" before the memory instructions when "
     "an admin switched on Agent VM (agent_vm_tools.py) and the chat has no Google data: the agent's own VM with "
     "vm_exec, vm_read_file and vm_write_file.",
     "prompt_defaults.py:AGENT_VM_PROMPT", _vm),
    ("answers", "Consensus mode: individual answers",
     "Default instructions for each answering model in Consensus mode, after the date context. A user's "
     "personal instructions replace it.",
     "prompt_defaults.py:ANSWER_SYSTEM_PROMPT", lambda: _defaults("answers")),
    ("consensus", "Consensus mode: final answer",
     "Instructions for combining the model responses into the Consensus answer; question, answers, "
     "sources and date context are added at request time.",
     "prompt_defaults.py:CONSENSUS_SYSTEM_PROMPT", lambda: _defaults("consensus")),
    ("delegation_orchestrator", "Delegation: orchestrator",
     "Appended to the Agent instructions only when delegation is enabled in the settings AND the selected "
     "model supports it (off by default).",
     "agent_delegation_config.py:ORCHESTRATOR_PROMPT", lambda: _delegation("orchestrator_prompt")),
    ("delegation_worker", "Delegation: worker",
     "System prompt of a delegated worker session; only used when delegation is enabled AND the model "
     "supports it (off by default).",
     "agent_delegation_config.py:WORKER_PROMPT", lambda: _delegation("worker_prompt")),
)


def prompt_catalog():
    """Current prompt texts as read-only entries for the admin."""
    return [{"key": key, "label": label, "used_for": used_for, "source": source, "text": text()}
            for key, label, used_for, source, text in _ENTRIES]

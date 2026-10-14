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


def _agent_answer():
    from app.services.prompt_defaults import AGENT_ANSWER_PROMPT
    return AGENT_ANSWER_PROMPT


def _agent_direct_answer():
    from app.services.prompt_defaults import AGENT_DIRECT_ANSWER_PROMPT
    return AGENT_DIRECT_ANSWER_PROMPT


def _agent_merged():
    from app.services.prompt_defaults import AGENT_MERGED_SYSTEM_PROMPT
    return AGENT_MERGED_SYSTEM_PROMPT


def _comparison():
    from app.services.agent_comparison import SEARCH_ROUNDS, comparison_system_prompt
    return _DATE_CONTEXT.sub(DATE_PLACEHOLDER, comparison_system_prompt("full", SEARCH_ROUNDS["full"]), count=1)


def _delegation(name):
    from app.services import agent_delegation_config
    return agent_delegation_config.PROMPTS[name]


# (key, label, used_for, source, text factory) in display order.
_ENTRIES = (
    ("agent", "Agent: steering instructions",
     "System prompt of the user's selected Agent model while it steers the run (comparisons, depth, memory, "
     "tools). At runtime the comparison settings, the per-message comparison limit and the source reading "
     "(AGENT_READ_SOURCE_PROMPT), file, document, Google, Watch (agent_watch.py; reading and Watch not in chats "
     "with Google data) and memory instructions are appended (in "
     "chats with Google data also a no-web-search note); date, "
     "reference time and selected model travel with the latest user message.",
     "prompt_defaults.py:AGENT_SYSTEM_PROMPT", lambda: _defaults("agent")),
    ("agent_answer", "Agent: answer step",
     "System prompt of the step that writes the answer the user reads (same model, no tools, fresh context). "
     "At runtime the app facts (AGENT_ANSWER_APP_FACTS, with the read and Watch sentences where the turn "
     "can do that), what the agent did in this message (AGENT_ANSWER_TURN_PROMPT: comparisons, own web "
     "search, pages opened) with one sentence per further evidence field sent (AGENT_ANSWER_EVIDENCE_FIELDS), "
     "the date context, selected model, memory block (if enabled) and, after a prepared Watch, "
     "the Watch card note are appended; the "
     "conversation and the evidence message (comparison answers with sources) follow.",
     "prompt_defaults.py:AGENT_ANSWER_PROMPT", _agent_answer),
    ("agent_direct_answer", "Agent: answer step without comparison",
     "Replaces the answer-step prompt when the Agent answered without a comparison (tool answer, no model "
     "answers, no check), e.g. for questions about the chat, rewrites or a page the user asked to read. The "
     "same app facts, message summary, date, model, memory and Watch additions follow; the evidence holds "
     "only pages read, a prepared Watch and, where present, documents, Google items or helper results.",
     "prompt_defaults.py:AGENT_DIRECT_ANSWER_PROMPT", _agent_direct_answer),
    ("agent_merged", "Agent: steering and answer in one step",
     "Replaces the steering instructions when AGENT_MERGED_ANSWER=1 (agent_answer_mode, off by default): the "
     "Agent writes the answer itself as its last step, with no separate answer step. It is the steering prompt "
     "with the sentences of AGENT_MERGED_REPLACEMENTS changed, followed by the writing rules "
     "(AGENT_MERGED_ANSWER_SECTION). The same runtime additions follow, source reading and Watch in their "
     "merged wording and the memory decision on compare_models and check_text. After each comparison that "
     "returned answers, the app adds AGENT_MERGED_WRITE_NOTE as its own message (the answer is the next "
     "message: complete, from all answers; depth only steered the comparison models).",
     "prompt_defaults.py:AGENT_MERGED_SYSTEM_PROMPT", _agent_merged),
    ("comparison", "Agent: comparison models",
     "System prompt of each independent comparison model, shown for depth \"full\" (3 search rounds). "
     "Quick depth allows one search round and adds brief-answer guidance instead. The date line is "
     "filled in per request; in chats with Google data a no-web-search note is appended.",
     "agent_comparison.py:comparison_system_prompt()", _comparison),
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

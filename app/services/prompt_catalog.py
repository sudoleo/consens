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


def _agent_protocol():
    from app.services.agent_comparison import PROMPT
    return PROMPT


def _agent_answer():
    from app.services.agent_comparison import SYNTHESIS_PROMPT
    return _defaults("consensus") + "\n\n" + SYNTHESIS_PROMPT


def _comparison():
    from app.services.agent_comparison import SEARCH_ROUNDS, comparison_system_prompt
    return _DATE_CONTEXT.sub(DATE_PLACEHOLDER, comparison_system_prompt("full", SEARCH_ROUNDS["full"]), count=1)


def _delegation(name):
    from app.services import agent_delegation_config
    return agent_delegation_config.PROMPTS[name]


# (key, label, used_for, source, text factory) in display order.
_ENTRIES = (
    ("agent", "Agent: steering instructions",
     "System prompt of the user's selected Agent model (orchestrator). Date, reference time and selected "
     "model travel with each user message as app context, not in this prompt.",
     "prompt_defaults.py:AGENT_SYSTEM_PROMPT", lambda: _defaults("agent")),
    ("agent_protocol", "Agent: pipeline protocol (appended)",
     "Appended to the Agent steering instructions whenever comparison tools are available. At runtime the "
     "comparison preferences, the Check contradictions ON/OFF block and the per-message comparison limit "
     "follow it.",
     "agent_comparison.py:PROMPT", _agent_protocol),
    ("agent_answer", "Agent: answer step",
     "System prompt of the final, checked Agent answer: the Consensus final-answer prompt followed by the "
     "synthesis instructions. At runtime the date context, selected model, memory block (if enabled) and "
     "the evidence message are appended.",
     "prompt_defaults.py:CONSENSUS_SYSTEM_PROMPT + agent_comparison.py:SYNTHESIS_PROMPT", _agent_answer),
    ("comparison", "Agent: comparison models",
     "System prompt of each independent comparison model, shown for depth \"full\" (3 search rounds). "
     "Quick depth allows one search round and adds brief-answer guidance instead. The date line is "
     "filled in per request.",
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

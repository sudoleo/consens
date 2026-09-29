"""Typed completion state of one generated text (review R06).

A provider stream that simply stops, or stops at the output-token limit, is
not a finished answer. Every model answer and every synthesis carries one of
these states from the transport up to storage and UI:

- ``complete``     the provider confirmed a normal end (``finish_reason=stop``
                   or the terminal ``[DONE]`` marker without a contrary reason)
- ``token_limit``  the provider stopped at the output-token limit
- ``interrupted``  the stream ended without any confirmation (EOF)
- ``error``        the provider reported an error / content filter stop
- ``cancelled``    the request was cancelled deliberately

Explicit input rule for the Consensus: ``complete`` answers are used as they
are; ``token_limit`` answers are used as clearly marked truncated answers (the
model finished a long answer and hit the output budget, which is common for
reasoning models); ``interrupted``/``error``/``cancelled`` answers are never
used. A synthesis is only a completed result when it is ``complete`` itself.
Partial text may stay visible, but it is always labelled with its state.
"""

from __future__ import annotations

from typing import Any, Optional

COMPLETE = "complete"
TOKEN_LIMIT = "token_limit"
INTERRUPTED = "interrupted"
ERROR = "error"
CANCELLED = "cancelled"
STATES = frozenset({COMPLETE, TOKEN_LIMIT, INTERRUPTED, ERROR, CANCELLED})
INCOMPLETE_STATES = frozenset({TOKEN_LIMIT, INTERRUPTED})

_COMPLETE_REASONS = frozenset({"stop", "end_turn", "stop_sequence", "eos"})
_TOKEN_LIMIT_REASONS = frozenset({"length", "max_tokens", "max_output_tokens"})
_ERROR_REASONS = frozenset({"error", "content_filter"})


INPUT_STATES = frozenset({COMPLETE, TOKEN_LIMIT})
TRUNCATION_NOTE = "\n\n[Note: this answer was cut off at the model's output limit; its end is missing.]"


def usable_as_input(state: Optional[str]) -> bool:
    """Whether a model answer in this state may feed a Consensus synthesis."""
    return (state or COMPLETE) in INPUT_STATES


def consensus_input_text(text: str, state: Optional[str]) -> str:
    """Answer text as the synthesis sees it: truncated answers say so."""
    return str(text or "") + (TRUNCATION_NOTE if state == TOKEN_LIMIT else "")


def completion_state(finish_reason: Any, *, terminated: bool) -> str:
    """Map the provider's finish signal to a completion state.

    ``terminated`` is True when the transport itself confirmed the end (the
    SSE ``[DONE]`` marker or a complete non-streaming JSON body). A plain EOF
    is not a confirmation.
    """
    reason = str(finish_reason or "").strip().lower()
    if reason in _TOKEN_LIMIT_REASONS:
        return TOKEN_LIMIT
    if reason in _ERROR_REASONS:
        return ERROR
    if reason in _COMPLETE_REASONS:
        return COMPLETE
    return COMPLETE if terminated else INTERRUPTED


def result_completion(result: Any) -> str:
    """Completion state of an engine result dict (``complete`` by default for
    successful results produced before this field existed, e.g. fixtures)."""
    if isinstance(result, dict):
        state = result.get("completion")
        if state in STATES:
            return state
        if result.get("error"):
            return ERROR
    return COMPLETE


def incomplete_message(state: Optional[str], subject: str = "The answer") -> str:
    if state == TOKEN_LIMIT:
        return f"{subject} stopped at the output limit and is incomplete."
    if state == INTERRUPTED:
        return f"{subject} was interrupted before it finished and is incomplete."
    if state == CANCELLED:
        return f"{subject} was cancelled."
    return f"{subject} could not be completed."

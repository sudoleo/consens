"""Provider reasoning continuation across tool steps, in real stream shapes.

OpenRouter streams ``reasoning_details`` as fragments. Gemini 3.x sends readable
``reasoning.text`` first and then its thought signature as a separate
``reasoning.encrypted`` block, both at ``index: 0``. Joining fragments by
``index`` alone either crashed the step ("identity changed") or glued opaque
signatures together, which Google rejects with HTTP 400 on the next step.
"""
import json

import pytest

from app.services.llm import agent_client
from app.services.llm.agent_client import AgentCompletion

GEMINI = "google-gemini-v1"
SIGNATURE = "CiQBjz1rX2ZvbGxvd3VwLXNpZ25hdHVyZS1ieXRlcw=="


def _run(monkeypatch, deltas, *, finish="tool_calls", allow_tool_calls=True):
    def lines(url, **kwargs):
        for index, delta in enumerate(deltas):
            choice = {"index": 0, "delta": delta}
            if index == len(deltas) - 1:
                choice["finish_reason"] = finish
            yield "data: " + json.dumps({"id": "gen-1", "choices": [choice]})
            yield ""
        yield "data: [DONE]"
        yield ""
    monkeypatch.setattr(agent_client, "cancellable_sse_lines", lines)
    completion = AgentCompletion()
    model = agent_client.resolve_agent_model("gpt-5.6-luna", "low")
    events = list(completion.stream(model=model, messages=[], api_key="test", allow_tool_calls=allow_tool_calls))
    return completion, events


def _tool_call(name="web_search", call_id="tool_web_search_1"):
    return [{"index": 0, "id": call_id, "type": "function",
             "function": {"name": name, "arguments": '{"query":"news"}'}}]


def test_gemini_text_then_signature_at_same_index_continues_the_tool_loop(monkeypatch):
    signature = {"type": "reasoning.encrypted", "data": SIGNATURE, "id": "tool_web_search_1",
                 "format": GEMINI, "index": 0}
    completion, events = _run(monkeypatch, [
        {"reasoning": "Checking ", "reasoning_details": [
            {"type": "reasoning.text", "text": "Checking ", "format": GEMINI, "index": 0}]},
        {"reasoning": "the news.", "reasoning_details": [
            {"type": "reasoning.text", "text": "the news.", "format": GEMINI, "index": 0}]},
        {"tool_calls": _tool_call(), "reasoning_details": [signature]},
    ])

    message = completion.assistant_message()
    # The signature goes back byte for byte; Gemini's unsigned thought text does
    # not (Google rejects replayed thought text it cannot verify).
    assert message["reasoning_details"] == [signature]
    assert "reasoning" not in message
    assert message["tool_calls"][0]["id"] == "tool_web_search_1"
    # The readable thought is still shown live and never exposes the signature.
    visible = json.dumps(events)
    assert "Checking the news." in json.dumps(completion.activity)
    assert SIGNATURE not in visible


def test_consecutive_encrypted_blocks_are_never_glued_together(monkeypatch):
    first = {"type": "reasoning.encrypted", "data": "c2lnLWE=", "format": GEMINI, "index": 0}
    second = {"type": "reasoning.encrypted", "data": "c2lnLWI=", "format": GEMINI, "index": 0}
    completion, _ = _run(monkeypatch, [
        {"reasoning_details": [first]},
        {"reasoning_details": [second], "tool_calls": _tool_call()},
    ])
    assert completion.assistant_message()["reasoning_details"] == [first, second]


def test_type_change_at_same_index_starts_a_new_block_instead_of_failing(monkeypatch):
    completion, _ = _run(monkeypatch, [
        {"reasoning_details": [{"type": "reasoning.summary", "summary": "Plan ", "index": 0,
                                "format": "openai-responses-v1"}]},
        {"reasoning_details": [{"type": "reasoning.summary", "summary": "first.", "index": 0,
                                "format": "openai-responses-v1"}]},
        {"reasoning_details": [{"type": "reasoning.encrypted", "data": "b3BhcXVl", "index": 0, "id": "rs_1",
                                "format": "openai-responses-v1"}],
         "tool_calls": _tool_call()},
    ])
    assert completion.assistant_message()["reasoning_details"] == [
        {"type": "reasoning.summary", "summary": "Plan first.", "index": 0, "format": "openai-responses-v1"},
        {"type": "reasoning.encrypted", "data": "b3BhcXVl", "index": 0, "id": "rs_1", "format": "openai-responses-v1"},
    ]


def test_signed_anthropic_thinking_is_merged_and_replayed_with_one_signature(monkeypatch):
    fmt = "anthropic-claude-v1"
    completion, _ = _run(monkeypatch, [
        {"reasoning_details": [{"type": "reasoning.text", "text": "Need a ", "format": fmt, "index": 0}]},
        {"reasoning_details": [{"type": "reasoning.text", "text": "search.", "format": fmt, "index": 0}]},
        {"reasoning_details": [{"type": "reasoning.text", "text": "", "signature": "EqQBsig", "format": fmt, "index": 0}],
         "tool_calls": _tool_call()},
    ])
    assert completion.assistant_message()["reasoning_details"] == [
        {"type": "reasoning.text", "text": "Need a search.", "signature": "EqQBsig", "format": fmt, "index": 0}]


def test_unsigned_anthropic_thinking_is_not_replayed(monkeypatch):
    fmt = "anthropic-claude-v1"
    completion, _ = _run(monkeypatch, [
        {"reasoning_details": [{"type": "reasoning.text", "text": "Draft", "format": fmt, "index": 0}],
         "tool_calls": _tool_call()},
    ])
    assert "reasoning_details" not in completion.assistant_message()


def test_distinct_indices_and_ids_stay_separate_blocks(monkeypatch):
    completion, _ = _run(monkeypatch, [
        {"reasoning_details": [{"type": "reasoning.summary", "summary": "A", "index": 0}]},
        {"reasoning_details": [{"type": "reasoning.summary", "summary": "B", "index": 1}]},
        {"reasoning_details": [{"type": "reasoning.text", "text": "x", "id": "one"},
                               {"type": "reasoning.text", "text": "y", "id": "two"}],
         "tool_calls": _tool_call()},
    ])
    details = completion.assistant_message()["reasoning_details"]
    assert [d.get("summary") or d.get("text") for d in details] == ["A", "B", "x", "y"]


def test_malformed_reasoning_fragments_do_not_end_the_run(monkeypatch):
    completion, _ = _run(monkeypatch, [
        {"reasoning_details": ["noise", {"text": "no type"}, {"type": "reasoning.text", "text": "ok", "index": 0}]},
        {"tool_calls": _tool_call()},
    ])
    assert completion.assistant_message()["reasoning_details"] == [
        {"type": "reasoning.text", "text": "ok", "index": 0}]


def test_oversized_reasoning_continuation_is_still_bounded(monkeypatch):
    with pytest.raises(ValueError, match="exceeds context limit"):
        _run(monkeypatch, [
            {"reasoning_details": [{"type": "reasoning.encrypted", "data": "x" * 70_000, "index": 0}]},
            {"reasoning_details": [{"type": "reasoning.encrypted", "data": "y" * 70_000, "index": 0}],
             "tool_calls": _tool_call()},
        ])

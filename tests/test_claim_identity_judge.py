"""The real identity parser rejects ambiguous indices and invented identities."""
import json
import logging
from unittest.mock import Mock
import pytest
from app.services.llm import consensus_engine as engine

KNOWN = [{"key": "k1", "label": "First"}, {"key": "k2", "label": "Second"}]
KEYS = {"OpenRouter": "dummy"}


def run(monkeypatch, payload, known=KNOWN, new=("A", "B")):
    call = Mock(return_value=json.dumps(payload))
    monkeypatch.setattr(engine, "_call_engine_text", call)
    result = engine.query_claim_identity(known, new, KEYS, "OpenAI")
    return result, call


def test_known_unique_bindings_only(monkeypatch):
    result, call = run(
        monkeypatch,
        {
            "matches": [
                {"index": 0, "key": "invented"},
                {"index": 0, "key": "k1"},
                {"index": 1, "key": "k1"},
                {"index": 0, "key": "k2"},
                {"index": 1, "key": "k2"},
                None,
            ]
        },
    )
    assert result == {0: "k1", 1: "k2"}
    assert call.call_count == 1


@pytest.mark.parametrize("index", [True, False, 0.0, 0.5, "0", None, -1, 2, {}, []])
def test_only_json_integer_indices_are_accepted(monkeypatch, index):
    assert run(monkeypatch, {"matches": [{"index": index, "key": "k1"}]})[0] == {}


def test_bounded_prompt_and_unmapped_outside_window(monkeypatch):
    result, call = run(
        monkeypatch,
        {
            "matches": [
                {"index": 11, "key": "k23"},
                {"index": 12, "key": "k1"},
                {"index": 0, "key": "k24"},
            ]
        },
        known=[{"key": "k" + str(i), "label": "x" * 1000} for i in range(40)],
        new=["y" * 1000] * 30,
    )
    assert result == {11: "k23"}
    prompt = call.call_args.kwargs["prompt"]
    known = json.loads(
        prompt.split("<KNOWN_CLAIMS>\n")[1].split("\n</KNOWN_CLAIMS>")[0]
    )
    new = json.loads(prompt.split("<NEW_CLAIMS>\n")[1].split("\n</NEW_CLAIMS>")[0])
    assert len(known) == 24 and len(new) == 12
    assert all(len(item["claim"]) == 300 for item in known + new)
    assert call.call_args.kwargs["max_tokens"] == 512


def test_retry_fallback_is_bounded_and_logs_no_provider_content(monkeypatch, caplog):
    call = Mock(
        side_effect=[
            RuntimeError("SECRET provider body"),
            "malformed JSON",
            '{"matches":[{"index":0,"key":"k1"}]}',
        ]
    )
    monkeypatch.setattr(engine, "_call_engine_text", call)
    # Multiple provider credentials let the real planner select a fallback.
    keys = {
        "OpenRouter": "dummy",
        "openai": "dummy",
        "google": "dummy",
        "deepseek": "dummy",
        "anthropic": "dummy",
    }
    with caplog.at_level(logging.WARNING):
        result = engine.query_claim_identity(KNOWN, ["A"], keys, "OpenAI")
    assert result == {0: "k1"}
    assert call.call_count == 3
    assert "SECRET" not in caplog.text
    call.side_effect = RuntimeError("SECRET")
    assert engine.query_claim_identity(KNOWN, ["A"], keys, "OpenAI") == {}
    assert call.call_count <= 7


def test_empty_or_invalid_engine_returns_unmapped_without_transport(monkeypatch):
    call = Mock(side_effect=AssertionError("Transport must not run"))
    monkeypatch.setattr(engine, "_call_engine_text", call)
    assert engine.query_claim_identity([], ["A"], KEYS, "OpenAI") == {}
    assert engine.query_claim_identity(KNOWN, [], KEYS, "OpenAI") == {}
    assert engine.query_claim_identity(KNOWN, ["A"], KEYS, "not-a-model") == {}
    call.assert_not_called()

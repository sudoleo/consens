"""Review R06: typed completion of model answers and syntheses.

R09 (answers bound to the server as receipts for the browser's /consensus)
ended on 2026-10-25 with that endpoint; the server pipeline (Watches, API,
Topics) collects its answers itself.
"""

from __future__ import annotations

from unittest import mock

from app.services.llm import completion
from app.services.llm.consensus_engine import (
    CONSENSUS_INCOMPLETE_TEXT,
    query_consensus,
)


def test_query_consensus_rejects_a_token_limited_synthesis():
    response = {"choices": [{"message": {"content": "Half"}, "finish_reason": "length"}]}
    with mock.patch("app.services.llm.consensus_engine.cancellable_post_json", return_value=response), \
         mock.patch("app.services.llm.consensus_engine.claim_analysis_call"):
        result = query_consensus("Q?", {"openai": "a", "mistral": "b"}, [], "OpenAI", {"OpenRouter": "k"})
    assert result == CONSENSUS_INCOMPLETE_TEXT


def test_non_streaming_query_model_reports_token_limit():
    from app.services.llm import engines

    class Response:
        status_code = 200

        def json(self):
            return {"choices": [{"message": {"content": "Half"}, "finish_reason": "length"}]}

        def close(self):
            pass

    with mock.patch.object(engines.requests, "post", return_value=Response()):
        result = engines.query_model("openai", "Q?", "key")
    assert result["completion"] == completion.TOKEN_LIMIT


def test_provider_fan_out_drops_interrupted_and_marks_truncated_answers():
    from app.services.llm.completion import TRUNCATION_NOTE
    from app.services.llm.provider_transport import fan_out_provider_answers
    states = {"openai": "interrupted", "mistral": "complete", "grok": "token_limit"}

    def call(provider, *args):
        return {"text": f"{provider} text", "sources": [], "completion": states[provider]}

    answers = fan_out_provider_answers(question="Q", provider_models={p: "m" for p in states},
                                       keys={}, tier="free", deep_think=False, provider_call=call)
    assert sorted(answers) == ["grok", "mistral"]
    assert answers["grok"].response == "grok text" + TRUNCATION_NOTE
    assert answers["mistral"].response == "mistral text"


def test_browser_flow_carries_completion_state():
    """Compare, the browser's own run besides Agent, keeps typed answer
    states. It runs no Consensus since 2026-10-25, so it binds no answer
    receipts to a run either."""
    from pathlib import Path
    root = Path(__file__).resolve().parents[1] / "static" / "js"
    query_send = (root / "query-send.js").read_text(encoding="utf-8")
    assert "run_id:" not in query_send
    assert 'const usable = completion === "complete" || completion === "token_limit";' in query_send
    assert 'result.status = usable ? "complete" : "incomplete";' in query_send
    assert "answer_receipt" not in query_send
    assert not (root / "consensus-run.js").exists()

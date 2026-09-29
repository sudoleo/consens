"""Review R06 (typed completion) and R09 (server-bound answer provenance)."""

from __future__ import annotations

import json
import re
from datetime import timedelta
from unittest import mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.core.config as cfg
from app.api.routers import chat as chat_router
from app.core.rate_limit import limiter
from app.services import answer_receipts
from app.services.llm import completion
from app.services.llm.consensus_engine import (
    CONSENSUS_INCOMPLETE_TEXT,
    query_consensus,
    stream_consensus,
)
import receipt_helpers

UID = "integrity-owner"
OTHER_UID = "integrity-other"
CHAT_ID = "a" * 32
TURN_ID = "b" * 32
AUTH = {"Authorization": "Bearer token"}
QUESTION = "What changed?"


class Store:
    def __init__(self):
        self.completions, self.failures = [], []

    def validate_turn_for_completion(self, uid, chat_id, turn_id, *, question):
        return {"id": turn_id, "status": "pending", "question": question}

    def complete_turn(self, uid, chat_id, turn_id, **payload):
        self.completions.append(payload)
        return {"status": "completed"}

    def fail_turn(self, uid, chat_id, turn_id, *, error_code):
        self.failures.append(error_code)
        return {"status": "failed"}


@pytest.fixture
def api(monkeypatch):
    limiter.reset()
    store = Store()
    seen = {"pending": [], "stats": [], "synthesized": []}
    monkeypatch.setattr(chat_router, "chat_store", store)
    monkeypatch.setattr(chat_router, "verify_user_token", lambda token: UID)
    monkeypatch.setattr(chat_router, "get_user_tier", lambda uid: "free")

    def synthesize(question, answers, *args, **kwargs):
        seen["synthesized"].append({k: v for k, v in dict(answers).items() if v})
        return "Consensus"

    monkeypatch.setattr(chat_router, "query_consensus", synthesize)
    monkeypatch.setattr(chat_router, "query_differences",
                        lambda *a, **k: ("Differences", {"agreement": {"score": 80}, "best_model": "OpenAI"}))
    monkeypatch.setattr(chat_router, "persist_pending_result",
                        lambda **kwargs: seen["pending"].append(kwargs) or "R" * 16)
    monkeypatch.setattr(chat_router, "record_differences_stats",
                        lambda *a, **k: seen["stats"].append(k))
    receipts = receipt_helpers.install(monkeypatch, chat_router)
    app = FastAPI()
    app.state.limiter = limiter
    app.include_router(chat_router.router)
    return TestClient(app), receipts, store, seen


def _payload(receipts, **updates):
    payload = {
        "question": QUESTION,
        "consensus_model": "Gemini",
        "useOwnKeys": True,
        "openrouter_key": "own-key",
        "run_id": receipt_helpers.RUN_ID,
        "answer_receipts": receipts,
    }
    payload.update(updates)
    return payload


def _issue(store, provider, text, **kwargs):
    kwargs.setdefault("provenance", "byok")
    return receipt_helpers.issue(store, uid=kwargs.pop("uid", UID), question=kwargs.pop("question", QUESTION),
                                 provider=provider, text=text, **kwargs)


# --------------------------------------------------------------------- R09 --

def test_consensus_uses_exactly_the_stored_answers(api):
    client, receipts, _, seen = api
    ids = {"openai": _issue(receipts, "OpenAI", "Stored one"),
           "mistral": _issue(receipts, "Mistral", "Stored two")}
    response = client.post("/consensus", headers=AUTH, json=_payload(ids))
    assert response.status_code == 200, response.text
    assert seen["synthesized"] == [{"openai": "Stored one", "mistral": "Stored two"}]


def test_client_answer_text_is_never_a_model_answer(api):
    client, _, _, seen = api
    response = client.post("/consensus", headers=AUTH, json={
        "question": QUESTION, "consensus_model": "Gemini", "useOwnKeys": True,
        "openrouter_key": "k", "answers": {"openai": "Invented", "mistral": "Invented too"},
    })
    assert response.status_code == 400
    assert response.json()["detail"]["error_code"] == "answer_receipts_required"
    assert seen["synthesized"] == []


@pytest.mark.parametrize("tamper", ["foreign_owner", "other_run", "other_question", "other_provider",
                                    "modified_text", "expired", "unknown"])
def test_forged_or_foreign_receipts_are_rejected(api, tamper):
    client, receipts, _, seen = api
    good = _issue(receipts, "Mistral", "Stored two")
    kwargs = {}
    if tamper == "foreign_owner":
        kwargs["uid"] = OTHER_UID
    elif tamper == "other_run":
        kwargs["run_id"] = "another_run"
    elif tamper == "other_question":
        kwargs["question"] = "Something else?"
    bad = _issue(receipts, "Grok" if tamper == "other_provider" else "OpenAI", "Stored one", **kwargs)
    doc = receipts.db.docs[("answer_receipts", bad)]
    if tamper == "modified_text":
        doc["text"] = "Stored one, but edited"
    elif tamper == "expired":
        doc["expires_at"] = doc["created_at"] - timedelta(seconds=1)
    elif tamper == "unknown":
        bad = "f" * 40
    response = client.post("/consensus", headers=AUTH,
                           json=_payload({"openai": bad, "mistral": good}))
    assert response.status_code == 409
    assert response.json()["detail"]["error_code"] in {
        "unknown_answer_receipt", "answer_receipt_mismatch"}
    assert seen["synthesized"] == []


def test_model_names_come_from_the_receipt_not_the_client(api):
    client, receipts, store, _ = api
    ids = {"openai": _issue(receipts, "OpenAI", "One", model=cfg.PROVIDERS["openai"].base_model),
           "mistral": _issue(receipts, "Mistral", "Two")}
    response = client.post("/consensus", headers=AUTH, json=_payload(
        ids, chat_id=CHAT_ID, turn_id=TURN_ID,
        model_labels={"OpenAI": "Totally Different Model", "Mistral": "X"}))
    assert response.status_code == 200
    stored = store.completions[0]["model_answers"]["OpenAI"]["model_label"]
    assert stored == cfg.get_model_label(cfg.PROVIDERS["openai"].base_model)


def test_byok_results_are_flagged_and_excluded_from_rankings(api):
    client, receipts, _, seen = api
    ids = {"openai": _issue(receipts, "OpenAI", "One", provenance="byok"),
           "mistral": _issue(receipts, "Mistral", "Two", provenance="developer")}
    assert client.post("/consensus", headers=AUTH, json=_payload(ids)).status_code == 200
    assert seen["pending"][-1]["answer_provenance"] == "byok"
    assert seen["stats"] == []


def test_own_key_synthesis_of_developer_answers_is_flagged(api):
    client, receipts, _, seen = api
    ids = {"openai": _issue(receipts, "OpenAI", "One", provenance="developer"),
           "mistral": _issue(receipts, "Mistral", "Two", provenance="developer")}
    assert client.post("/consensus", headers=AUTH, json=_payload(ids)).status_code == 200
    assert seen["pending"][-1]["answer_provenance"] == "byok"
    assert seen["stats"] == []


def test_developer_results_keep_rankings(api, monkeypatch):
    client, receipts, _, seen = api
    ids = {"openai": _issue(receipts, "OpenAI", "One", provenance="developer"),
           "mistral": _issue(receipts, "Mistral", "Two", provenance="developer")}
    monkeypatch.setattr(chat_router, "authorize_usage_operation", lambda *a, **k: None)
    monkeypatch.setattr(chat_router, "build_engine_api_keys", lambda *a: {"OpenRouter": "server-key"})
    response = client.post("/consensus", headers=AUTH, json=_payload(
        ids, useOwnKeys=False, openrouter_key=""))
    assert response.status_code == 200, response.text
    assert seen["pending"][-1]["answer_provenance"] == "developer"
    assert len(seen["stats"]) == 1


def test_browser_retry_of_the_same_receipts_is_accepted(api):
    client, receipts, _, seen = api
    ids = {"openai": _issue(receipts, "OpenAI", "One"), "mistral": _issue(receipts, "Mistral", "Two")}
    assert client.post("/consensus", headers=AUTH, json=_payload(ids)).status_code == 200
    limiter.reset()
    assert client.post("/consensus", headers=AUTH, json=_payload(ids)).status_code == 200
    assert len(seen["synthesized"]) == 2


def test_ask_issues_a_receipt_bound_to_owner_run_question_and_model(monkeypatch):
    limiter.reset()
    receipts = receipt_helpers.install(monkeypatch, chat_router)
    monkeypatch.setattr(chat_router, "verify_user_token", lambda token: UID)
    monkeypatch.setattr(chat_router, "get_user_tier", lambda uid: "free")
    model = cfg.FREE_DEFAULT_MODEL_BY_PROVIDER["openai"]
    with mock.patch.object(chat_router, "query_model", return_value={
        "text": "Delivered answer", "sources": [], "completion": "complete"}):
        app = FastAPI()
        app.state.limiter = limiter
        app.include_router(chat_router.router)
        response = TestClient(app).post("/ask_openai", headers=AUTH, json={
            "question": QUESTION, "model": model, "useOwnKeys": True,
            "openrouter_key": "sk-user", "run_id": "run_abc"})
    assert response.status_code == 200, response.text
    receipt_id = response.json()["answer_receipt"]
    stored = receipts.db.docs[("answer_receipts", receipt_id)]
    assert stored["owner_uid"] == UID
    assert stored["model"] == model
    assert stored["provenance"] == "byok"
    assert stored["content_sha256"] == answer_receipts.content_digest("Delivered answer")
    assert stored["run"] == answer_receipts.run_binding(UID, None, "run_abc")


# --------------------------------------------------------------------- R06 --

def test_interrupted_answers_never_enter_the_synthesis(api):
    client, receipts, _, seen = api
    ids = {"openai": _issue(receipts, "OpenAI", "Cut off", state="interrupted"),
           "mistral": _issue(receipts, "Mistral", "Two"),
           "grok": _issue(receipts, "Grok", "Three")}
    assert client.post("/consensus", headers=AUTH, json=_payload(ids)).status_code == 200
    assert seen["synthesized"] == [{"mistral": "Two", "grok": "Three"}]


def test_token_limit_answers_enter_the_synthesis_marked_as_truncated(api):
    from app.services.llm.completion import TRUNCATION_NOTE
    client, receipts, _, seen = api
    ids = {"openai": _issue(receipts, "OpenAI", "Long answer", state="token_limit"),
           "mistral": _issue(receipts, "Mistral", "Two")}
    assert client.post("/consensus", headers=AUTH, json=_payload(ids)).status_code == 200
    assert seen["synthesized"] == [{"openai": "Long answer" + TRUNCATION_NOTE, "mistral": "Two"}]


def _final(response):
    matches = re.findall(r"event: final\r?\ndata: (.+?)\r?\n\r?\n", response.text)
    return json.loads(matches[-1])


@pytest.mark.parametrize("state", ["token_limit", "interrupted"])
def test_truncated_streaming_synthesis_is_never_a_completed_result(api, monkeypatch, state):
    client, receipts, store, seen = api
    monkeypatch.setattr(chat_router, "stream_consensus", lambda *a, **k: iter([
        {"type": "delta", "text": "Partial synthesis"},
        {"type": "final", "text": "Partial synthesis", "error": True, "completion": state},
    ]))
    monkeypatch.setattr(chat_router, "stream_differences",
                        lambda *a, **k: pytest.fail("no judge on an incomplete synthesis"))
    ids = {"openai": _issue(receipts, "OpenAI", "One"), "mistral": _issue(receipts, "Mistral", "Two")}
    response = client.post("/consensus", headers=AUTH, json=_payload(
        ids, stream=True, chat_id=CHAT_ID, turn_id=TURN_ID))
    final = _final(response)
    assert final["consensus_completion"] == state
    assert final["consensus_response"] == ""
    assert final["error_code"] == "consensus_incomplete"
    assert final["chat_turn_state"] == "failed"
    assert "result_id" not in final
    assert store.completions == [] and store.failures == ["consensus_incomplete"]
    assert seen["pending"] == []


def test_complete_streaming_synthesis_reports_complete(api, monkeypatch):
    client, receipts, store, _ = api
    monkeypatch.setattr(chat_router, "stream_consensus", lambda *a, **k: iter([
        {"type": "final", "text": "Consensus"}]))
    monkeypatch.setattr(chat_router, "stream_differences", lambda *a, **k: iter([
        {"type": "final", "text": "D", "data": {"agreement": {"score": 1}}}]))
    ids = {"openai": _issue(receipts, "OpenAI", "One"), "mistral": _issue(receipts, "Mistral", "Two")}
    final = _final(client.post("/consensus", headers=AUTH, json=_payload(
        ids, stream=True, chat_id=CHAT_ID, turn_id=TURN_ID, check_sources=False)))
    assert final["consensus_completion"] == "complete"
    assert final["chat_turn_state"] == "completed"


def test_stream_consensus_marks_truncation_and_does_not_mix_retries():
    def engine(*args):
        yield {"type": "delta", "text": "Half of the "}
        yield {"type": "completion", "state": "token_limit"}

    with mock.patch("app.services.llm.consensus_engine._stream_consensus_engine", side_effect=engine) as call:
        events = list(stream_consensus("Q?", {"openai": "a", "mistral": "b"}, [], "OpenAI",
                                       {"OpenRouter": "k"}))
    assert call.call_count == 1  # no silent retry replacing visible text
    assert events[-1]["error"] is True and events[-1]["completion"] == "token_limit"

    attempts = []

    def flaky(*args):
        attempts.append(1)
        yield {"type": "delta", "text": "broken "}
        if len(attempts) == 1:
            raise RuntimeError("503")
        yield {"type": "completion", "state": "complete"}

    with mock.patch("app.services.llm.consensus_engine._stream_consensus_engine", side_effect=flaky):
        events = list(stream_consensus("Q?", {"openai": "a", "mistral": "b"}, [], "OpenAI",
                                       {"OpenRouter": "k"}))
    types = [event["type"] for event in events]
    assert types == ["delta", "reset", "delta", "final"]
    assert events[-1] == {"type": "final", "text": "broken"}


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


def test_browser_flow_carries_receipts_and_completion_state():
    """The /ask -> /consensus browser path uses receipts and typed states."""
    from pathlib import Path
    root = Path(__file__).resolve().parents[1] / "static" / "js"
    query_send = (root / "query-send.js").read_text(encoding="utf-8")
    consensus = (root / "consensus-run.js").read_text(encoding="utf-8")
    assert "run_id: context.runId" in query_send
    assert "result.receipt = typeof data.answer_receipt" in query_send
    assert 'const usable = completion === "complete" || completion === "token_limit";' in query_send
    assert 'result.status = usable ? "complete" : "incomplete";' in query_send
    run_path = consensus.split("window.App.executeConsensusRun =", 1)[1].split("window.getConsensus =", 1)[0]
    assert "answer_receipts: runReceipts(context)" in run_path
    assert "answers: Object.fromEntries" not in run_path


@pytest.mark.parametrize("body", ["tampered", "legacy_text"])
def test_rejected_answer_sets_fail_the_pending_turn(api, body):
    client, receipts, store, seen = api
    good = _issue(receipts, "Mistral", "Two")
    if body == "tampered":
        payload = _payload({"openai": "f" * 40, "mistral": good}, chat_id=CHAT_ID, turn_id=TURN_ID)
        expected = 409
    else:
        payload = _payload({}, chat_id=CHAT_ID, turn_id=TURN_ID, answers={"OpenAI": "free text", "Mistral": "x"})
        payload.pop("answer_receipts")
        expected = 400
    response = client.post("/consensus", headers=AUTH, json=payload)
    assert response.status_code == expected
    detail = response.json()["detail"]
    assert detail["chat_turn_state"] == "failed" and detail["turn_id"] == TURN_ID
    assert store.failures == [detail["error_code"]]
    assert seen["synthesized"] == []

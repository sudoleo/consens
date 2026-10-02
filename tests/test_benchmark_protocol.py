"""Provider protocol failures remain failures through persistence and resume."""

import json

import pytest

from benchmark import results, transport
from benchmark.runner import BenchmarkRunner, cell_key, compute_skip_keys, index_existing


class Response:
    status_code = 200

    def __init__(self, body):
        self.body = body
        self.closed = False

    def json(self):
        return self.body

    def close(self):
        self.closed = True


def record(outcome):
    return BenchmarkRunner()._make_cell_record(
        run_id="protocol", qrecord={"question_id": 1, "answer": "B",
                                    "options": ["Paris", "Berlin"], "category": "test"},
        role="model", provider="openai", internal_model="test", api_model="test",
        user_prompt="question", payload={}, outcome=outcome, fallback_cost=0.1,
    )


@pytest.mark.parametrize("body,code", [
    ({"error": {"code": 429, "message": "private-secret-provider-text"}}, "provider_response_error"),
    ({"error": {}, "choices": [{"message": {"content": "FINAL_ANSWER: B"}}]}, "provider_response_error"),
    (None, "response_parse_failed"),
    ([], "response_parse_failed"),
    ({}, "response_parse_failed"),
    ({"choices": []}, "response_parse_failed"),
    ({"choices": "invalid"}, "response_parse_failed"),
    ({"choices": [None]}, "response_parse_failed"),
    ({"choices": [{"message": {}}]}, "response_parse_failed"),
    ({"choices": [{"message": {"content": {"private-secret-provider-text": 1}}}]}, "response_parse_failed"),
])
def test_protocol_failures_are_not_successful_abstentions(body, code):
    response = Response(body)
    outcome = transport.execute({"payload": {}}, "private-secret-key", http_post=lambda *a, **k: response)
    assert response.closed
    assert outcome["error_code"] == code
    assert outcome["error"]
    assert outcome["raw"] is None
    row = record(outcome)
    assert row["abstain"] is False
    assert row["extracted_letter"] is None
    assert "private-secret" not in json.dumps(row)
    index = index_existing([row])
    key = cell_key(1, "model", "openai")
    assert index[key]["success"] is None
    assert compute_skip_keys(index, retry_failed=True) == set()
    assert compute_skip_keys(index, retry_failed=False) == {key}
    summary = results.aggregate([row])["systems"]["model:openai"]
    assert summary["error"] == 1
    assert summary["abstain"] == 0


@pytest.mark.parametrize("text,abstain,letter", [
    ("I cannot determine the answer.", True, None),
    ("FINAL_ANSWER: B", False, "B"),
])
def test_valid_text_preserves_selection_and_abstention(text, abstain, letter):
    response = Response({"choices": [{"message": {"content": text}}],
                         "usage": {"prompt_tokens": 3, "completion_tokens": 4}})
    outcome = transport.execute({"payload": {}}, "unused", http_post=lambda *a, **k: response)
    row = record(outcome)
    assert response.closed
    assert row["error"] is None
    assert row["abstain"] is abstain
    assert row["extracted_letter"] == letter
    assert row["usage"]["total"] == 7
    assert compute_skip_keys(index_existing([row]), retry_failed=True) == {cell_key(1, "model", "openai")}


def test_exception_messages_cannot_leak_credentials_into_records():
    def fail(*a, **k):
        raise RuntimeError("Authorization: private-secret-key; private prompt")
    outcome = transport.execute({"payload": {}}, "unused", http_post=fail)
    assert outcome["error_code"] == "transport_request_failed"
    assert "private" not in json.dumps(record(outcome))


@pytest.mark.parametrize('raises', [True, False])
def test_consensus_error_projection_never_persists_private_provider_details(raises):
    def consensus(**kwargs):
        if raises:
            raise RuntimeError('private-secret-key')
        return 'Consensus error: private-secret-response'
    outcome = BenchmarkRunner()._call_consensus(consensus, {'question':'question', 'options':['One','Two']}, {})
    assert outcome['error_code'] == 'consensus_failed'
    assert 'private' not in json.dumps(record(outcome))

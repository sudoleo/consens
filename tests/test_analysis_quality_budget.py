"""Regression cases for evidence coverage, shared inputs and paid-call bounds."""
import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor
from unittest import mock

import httpx
import pytest

from app.services.llm import consensus_engine as engine
from app.services.llm import provider_runtime as runtime
from app.services.llm.consensus_scoring import compute_agreement_score
from app.services.share_snapshots import sanitize_differences_data
from app.services.chat_store import normalize_turn_differences_data


def claim(agree=("OpenAI", "Gemini")):
    return {"anchor": "A sufficiently concrete statement.", "agree": list(agree), "dissent": []}


def score(claims, **extra):
    return compute_agreement_score({
        "claims": claims, "models_compared": ["OpenAI", "Gemini", "Grok", "Mistral"],
        "differences": [], **extra,
    })


def test_empty_or_sparse_evidence_does_not_create_a_numeric_score():
    for claims in ([], [claim()] + [claim(("OpenAI",)) for _ in range(19)]):
        result = score(claims)
        assert result["score"] is None
        assert result["level"] == "insufficient"
        assert result["coverage_status"] == "insufficient"
    assert score([claim()] + [claim(()) for _ in range(19)])["coverage_percent"] == 5


def test_limited_coverage_caps_the_verdict_without_hiding_disagreement():
    result = score([claim(), claim(())])
    assert result["score"] == 64
    assert result["coverage_percent"] == 50
    disputed = score([claim(), claim(())], differences=[{"type": "contradiction", "severity": "major"}] * 2)
    assert disputed["score"] <= 39
    assert disputed["major_contradictions"] == 2


def test_judges_and_synthesis_share_the_full_answer_including_late_caveats():
    late = "However, this conclusion is invalid after 2030."
    text = "An introductory paragraph. " * 400 + late
    answers = {"openai": text, "gemini": "The conclusion remains valid after 2030."}
    prompt = engine._build_consensus_prompt("When?", answers, [], shuffle=False)
    context = engine._build_judge_context(answers, "This conclusion is valid after 2030.")
    assert text in prompt
    assert context.answers_by_model["OpenAI"] == text
    assert late in engine._build_differences_prompt_from(context)
    assert context.truncated_answers == 0


def test_sentence_cap_is_reported_and_limits_overall_score():
    answer = "\n".join(f"The numbered item {index} has a checkable property." for index in range(100))
    context = engine._build_judge_context({"openai": answer, "gemini": answer}, answer)
    assert len(context.sentences) == 80
    assert context.unindexed_sentences == 20
    result = score([claim()] * 80, evidence_coverage={"unindexed_sentences": 20})
    assert result["coverage_percent"] == 80
    assert result["evidence_incomplete"] is True
    assert result["score"] == 64


def test_snapshot_preserves_all_claims_null_score_coverage_and_runtime():
    data = {
        "claims": [claim()] * 80, "differences": [],
        "agreement": score([]),
        "judges": {"coverage": {"provider": "Gemini", "attempts": 2, "duration_ms": 240}},
        "analysis_runtime": {"attempts": 5, "duration_ms": 1600},
        "evidence_coverage": {"unindexed_sentences": 20, "truncated_answers": 0},
    }
    saved = sanitize_differences_data(data)
    assert len(saved["claims"]) == 80
    assert saved["agreement"]["score"] is None
    assert saved["agreement"]["coverage_status"] == "insufficient"
    assert saved["judges"]["coverage"]["attempts"] == 2
    assert saved["analysis_runtime"] == data["analysis_runtime"]
    assert saved["evidence_coverage"] == data["evidence_coverage"]
    turn = normalize_turn_differences_data(data)
    assert "score" in turn["agreement"]
    assert turn["agreement"]["score"] is None


def test_parallel_roles_share_one_atomic_call_budget():
    budget = runtime.AnalysisBudget(seconds=10, max_calls=3)
    def attempt(_):
        with runtime.bind_analysis_budget(budget):
            try:
                runtime.claim_analysis_call()
                return True
            except runtime.AnalysisBudgetExceeded:
                return False
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sum(pool.map(attempt, range(10))) == 3
    assert budget.calls == 3


def test_nested_synthesis_and_judges_do_not_reset_budget():
    @runtime.analysis_budgeted
    def stage():
        runtime.claim_analysis_call()
        return runtime.current_analysis_budget()
    with runtime.analysis_budget_scope() as budget:
        assert stage() is budget
        assert stage() is budget
        assert budget.calls == 2
    assert runtime.current_analysis_budget() is None


@pytest.mark.parametrize("stop", ["disconnect", "deadline"])
def test_nonstream_request_is_cancelled_while_waiting_for_headers(stop):
    started = threading.Event()
    stopped = threading.Event()
    cancellation = runtime.ProviderCancellation()
    budget = runtime.AnalysisBudget(seconds=0.15 if stop == "deadline" else 5)

    async def waiting_transport(request):
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            stopped.set()

    client_type = httpx.AsyncClient
    def client(**kwargs):
        return client_type(transport=httpx.MockTransport(waiting_transport), **kwargs)
    def cancel():
        assert started.wait(2)
        cancellation.cancel()
    worker = threading.Thread(target=cancel) if stop == "disconnect" else None
    if worker:
        worker.start()
    try:
        with mock.patch.object(runtime.httpx, "AsyncClient", side_effect=client):
            with runtime.bind_provider_cancellation(cancellation), runtime.bind_analysis_budget(budget):
                with pytest.raises((runtime.ProviderCancelled, runtime.AnalysisBudgetExceeded)):
                    runtime.cancellable_post_json("https://example.invalid/chat", json={}, headers={})
        assert stopped.is_set(), "the HTTP task itself must be cancelled, not abandoned"
    finally:
        if worker:
            worker.join(2)


def test_paid_transport_is_not_called_after_budget_exhaustion():
    with runtime.bind_analysis_budget(runtime.AnalysisBudget(seconds=10, max_calls=0)):
        with mock.patch.object(engine, "cancellable_post_json") as post:
            with pytest.raises(runtime.AnalysisBudgetExceeded):
                engine._call_engine_text("gemini", "test", "test", {}, system="", prompt="", max_tokens=10)
            post.assert_not_called()


@pytest.mark.parametrize("stop", ["disconnect", "deadline"])
def test_stream_body_read_is_cancelled_and_connection_closed(stop):
    closed = threading.Event()
    interrupted = threading.Event()
    cancellation = runtime.ProviderCancellation()
    budget = runtime.AnalysisBudget(seconds=0.15 if stop == "deadline" else 5)

    class Body(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield b'data: {"choices": []}\n\n'
            try:
                await asyncio.Event().wait()
            finally:
                interrupted.set()
        async def aclose(self):
            closed.set()

    client_type = httpx.AsyncClient
    def client(**kwargs):
        return client_type(transport=httpx.MockTransport(lambda _: httpx.Response(200, stream=Body())), **kwargs)
    with mock.patch.object(runtime.httpx, "AsyncClient", side_effect=client):
        with runtime.bind_provider_cancellation(cancellation), runtime.bind_analysis_budget(budget):
            lines = runtime.cancellable_sse_lines("https://example.invalid/chat", json={}, headers={})
            assert next(lines) == 'data: {"choices": []}'
            assert next(lines) == ""
            timer = threading.Timer(0.03, cancellation.cancel) if stop == "disconnect" else None
            if timer:
                timer.start()
            try:
                with pytest.raises((runtime.ProviderCancelled, runtime.AnalysisBudgetExceeded)):
                    next(lines)
            finally:
                lines.close()
                if timer:
                    timer.cancel()
    assert interrupted.is_set()
    assert closed.is_set()


def test_coverage_worker_inherits_budget_and_disconnect_signal():
    context = engine._build_judge_context({"openai": "one", "gemini": "two"}, "A claim with enough words.")
    with runtime.analysis_budget_scope() as budget:
        cancellation = runtime.current_provider_cancellation()
        def judge(*args):
            assert runtime.current_analysis_budget() is budget
            assert runtime.current_provider_cancellation() is cancellation
            runtime.claim_analysis_call()
            return {}, {}
        with mock.patch.object(engine, "_run_coverage_judge", side_effect=judge):
            pool, future = engine._coverage_in_background(context, {}, "OpenAI")
            assert engine._collect_coverage(pool, future) == ({}, {})
        assert budget.calls == 1

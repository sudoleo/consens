"""Regression cases for evidence coverage, shared inputs and paid-call bounds."""
import asyncio
import threading
import time
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


def test_a_run_gives_each_phase_its_own_budget_and_totals_them():
    """Audit C3: synthesis and judges no longer share one deadline and count."""
    @runtime.analysis_budgeted(seconds=30, max_calls=1)
    def phase():
        runtime.claim_analysis_call()
        return runtime.current_analysis_budget()

    with runtime.analysis_run_scope() as run:
        synthesis, judges = phase(), phase()
        assert synthesis is not judges and synthesis.run is run and judges.run is run
        assert synthesis.max_calls == 1 and judges.calls == 1
        assert judges.snapshot()["attempts"] == 2
    assert runtime.current_analysis_budget() is None
    # An Agent's budget still governs every phase it calls.
    agent = runtime.AnalysisBudget(seconds=10, max_calls=5)
    with runtime.bind_analysis_budget(agent), runtime.analysis_run_scope():
        assert phase() is agent and phase() is agent


def test_a_pro_runs_judges_keep_their_whole_plan_after_a_synthesis_fallback():
    """Audit C3: synthesis (2 failures + fallback) plus the pro judge plan need
    more than the former shared 8 calls; the judges lost their fallbacks."""
    from app.services.consensus_pipeline import analyze_provider_answers
    keys = {"OpenRouter": "sk-or"}
    seen, lock = [], threading.Lock()

    def fake_engine(provider, api_model, model_ref, api_keys, *, system, **kwargs):
        runtime.claim_analysis_call()
        role = "judge" if system else "synthesis"
        with lock:
            seen.append((role, runtime.current_analysis_budget()))
            synthesis_calls = sum(1 for name, _ in seen if name == "synthesis")
        if role == "synthesis" and synthesis_calls == 3:
            return "The fallback engine wrote this synthesis sentence."
        raise RuntimeError("503 - UNAVAILABLE")

    with mock.patch.object(engine, "_call_engine_text", side_effect=fake_engine):
        analysis = analyze_provider_answers(
            question="Q?", answers={"openai": "One answer here.", "gemini": "Another answer here."},
            consensus_model="Gemini-Pro", keys=keys, require_differences_data=False,
        )
    assert analysis.consensus == "The fallback engine wrote this synthesis sentence."
    synthesis = [budget for role, budget in seen if role == "synthesis"]
    judges = [budget for role, budget in seen if role == "judge"]
    plan = len(engine._differences_attempts("Gemini-Pro", keys)) + len(engine._coverage_attempts("Gemini-Pro", keys))
    assert len(synthesis) == 3 and len(judges) == plan
    assert {id(budget) for budget in synthesis} != {id(budget) for budget in judges}


def test_phase_call_limits_cover_the_longest_attempt_plans():
    """The phase limits follow the retry plans (audit C3); a longer plan must
    raise its limit instead of losing its last attempts."""
    import app.core.config as cfg
    keys = {"OpenRouter": "sk-or"}
    for model in cfg.ALLOWED_CONSENSUS_MODELS:
        resolved = engine._resolve_engine(model)
        if resolved is None:
            continue
        synthesis = engine.CONSENSUS_MAX_ATTEMPTS + bool(engine._fallback_judge_engine(resolved[0], keys))
        # Coverage's worst case: its last attempt succeeds and needs the repair.
        judges = len(engine._differences_attempts(model, keys)) + len(engine._coverage_attempts(model, keys)) + 1
        assert synthesis <= engine.SYNTHESIS_MAX_CALLS, model
        assert judges <= engine.JUDGE_PHASE_MAX_CALLS, model


@pytest.mark.parametrize("stop", ["disconnect", "deadline"])
def test_nonstream_request_is_cancelled_while_waiting_for_headers(stop):
    started = threading.Event()
    stopped = threading.Event()
    cancellation = runtime.ProviderCancellation()
    budget = runtime.AnalysisBudget(seconds=5)

    async def waiting_transport(request):
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            stopped.set()

    client_type = httpx.AsyncClient
    def client(**kwargs):
        return client_type(transport=httpx.MockTransport(waiting_transport), **kwargs)
    def stop_while_waiting():
        assert started.wait(2)
        if stop == "disconnect":
            cancellation.cancel()
        else:
            # The deadline passes while the request waits for headers. A fixed
            # 0.15 s budget could run out on a slow runner before the request
            # even started, leaving no HTTP task to cancel (CI 2026-10-29).
            budget.deadline = time.monotonic()
    worker = threading.Thread(target=stop_while_waiting)
    worker.start()
    try:
        with mock.patch.object(runtime.httpx, "AsyncClient", side_effect=client):
            with runtime.bind_provider_cancellation(cancellation), runtime.bind_analysis_budget(budget):
                with pytest.raises((runtime.ProviderCancelled, runtime.AnalysisBudgetExceeded)):
                    runtime.cancellable_post_json("https://example.invalid/chat", json={}, headers={})
        assert stopped.is_set(), "the HTTP task itself must be cancelled, not abandoned"
    finally:
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
        def judge(*args, **kwargs):
            assert runtime.current_analysis_budget() is budget
            # Its own stop, linked: a disconnect of the caller still reaches it.
            own = runtime.current_provider_cancellation()
            assert own is not cancellation and not own.cancelled
            cancellation.cancel()
            assert own.cancelled
            return {}, {}
        with mock.patch.object(engine, "_run_coverage_judge", side_effect=judge):
            pool, future, stop = engine._coverage_in_background(context, {}, "OpenAI")
            assert engine._collect_coverage(pool, future, stop) == ({}, {})


def test_coverage_worker_counts_against_the_shared_budget():
    context = engine._build_judge_context({"openai": "one", "gemini": "two"}, "A claim with enough words.")
    with runtime.analysis_budget_scope() as budget:
        def judge(*args, **kwargs):
            runtime.claim_analysis_call()
            return {}, {}
        with mock.patch.object(engine, "_run_coverage_judge", side_effect=judge):
            pool, future, stop = engine._coverage_in_background(context, {}, "OpenAI")
            assert engine._collect_coverage(pool, future, stop) == ({}, {})
        assert budget.calls == 1


def test_a_coverage_result_past_the_deadline_is_stopped_not_awaited():
    """Agent judges run through a task transport, whose calls are not bound
    by the analysis deadline, and the collector waits for the thread. A
    result the run no longer uses must be stopped, not awaited (prod
    2026-10-15: 64 s of waiting for a Coverage result that was then dropped)."""
    from app.services.llm.task_transport import bind_task_transport
    context = engine._build_judge_context({"openai": "one", "gemini": "two"}, "A claim with enough words.")
    stopped = threading.Event()

    def judge(*args, **kwargs):
        own = runtime.current_provider_cancellation()
        # A stall: only its stop ends it (the test fails after 5 s otherwise).
        for _ in range(500):
            if own.cancelled:
                stopped.set()
                raise runtime.ProviderCancelled("stopped")
            threading.Event().wait(0.01)
        return {"s1": {}}, {"provider": "OpenAI"}

    with runtime.bind_analysis_budget(runtime.AnalysisBudget(seconds=0.05)), bind_task_transport(lambda: None):
        with mock.patch.object(engine, "_run_coverage_judge", side_effect=judge):
            pool, future, stop = engine._coverage_in_background(context, {}, "OpenAI")
            started = engine.time.monotonic()
            assert engine._collect_coverage(pool, future, stop) == (None, None)
            assert engine.time.monotonic() - started < 2
    assert stopped.is_set()


def test_unlimited_agent_budget_waits_for_pending_coverage_without_overflow():
    from app.services.llm.task_transport import bind_task_transport
    gate = threading.Event()
    result = ({"sentences": []}, {"provider": "Gemini"})
    pool = ThreadPoolExecutor(max_workers=1)
    future = pool.submit(lambda: (gate.wait(3), result)[1])
    timer = threading.Timer(.05, gate.set)
    timer.start()
    try:
        with runtime.bind_analysis_budget(runtime.AnalysisBudget(unlimited=True)), bind_task_transport(lambda: None):
            assert engine._collect_coverage(pool, future) == result
    finally:
        gate.set(); timer.cancel(); pool.shutdown()

"""A judge call that hangs gets an identical second request (_hedged_judge_call).

Chat review 2026-10-18: Luna judge attempts ran into their 90 s limit in prod.
A stall now costs JUDGE_HEDGE_SECONDS: the duplicate answers, the first one is
stopped. Fast calls never pay for a duplicate.
"""
import json
import threading
import time
import unittest
from unittest import mock

from app.services.llm import consensus_engine as engine
from app.services.llm import provider_runtime as runtime


def stall_until_stopped(stopped=None):
    stop = runtime.current_provider_cancellation()
    for _ in range(500):
        if stop is not None and stop.cancelled:
            if stopped is not None:
                stopped.set()
            raise runtime.ProviderCancelled("stopped")
        time.sleep(0.01)
    raise AssertionError("the stalled request was never stopped")


class HedgedJudgeCallTests(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.object(engine, "JUDGE_HEDGE_SECONDS", 0.05)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_a_stalled_request_is_answered_by_its_duplicate_and_stopped(self):
        calls, stopped, lock = [], threading.Event(), threading.Lock()

        def call():
            with lock:
                calls.append(1)
                first = len(calls) == 1
            if first:
                stall_until_stopped(stopped)
            return "second"

        started = time.monotonic()
        self.assertEqual(engine._hedged_judge_call(call), "second")
        self.assertLess(time.monotonic() - started, 2.0)
        self.assertEqual(len(calls), 2)
        self.assertTrue(stopped.wait(2.0))

    def test_a_fast_request_never_gets_a_duplicate(self):
        calls = []
        self.assertEqual(engine._hedged_judge_call(lambda: calls.append(1) or "ok"), "ok")
        self.assertEqual(calls, [1])

    def test_the_duplicate_waits_for_a_spare_call_in_the_budget(self):
        calls = []
        budget = runtime.AnalysisBudget(seconds=30, max_calls=2)
        budget.calls = 1

        def call():
            calls.append(1)
            time.sleep(0.15)
            return "slow"

        with runtime.bind_analysis_budget(budget):
            self.assertEqual(engine._hedged_judge_call(call), "slow")
        self.assertEqual(calls, [1])

    def test_a_failed_request_waits_for_the_other(self):
        calls, lock = [], threading.Lock()

        def call():
            with lock:
                calls.append(1)
                first = len(calls) == 1
            if first:
                time.sleep(0.1)
                raise RuntimeError("provider error")
            time.sleep(0.2)
            return "late but fine"

        self.assertEqual(engine._hedged_judge_call(call), "late but fine")

    def test_when_both_fail_the_first_error_propagates(self):
        calls, lock = [], threading.Lock()

        def call():
            with lock:
                calls.append(1)
                number = len(calls)
            time.sleep(0.1)
            raise RuntimeError(f"failure {number}")

        with self.assertRaisesRegex(RuntimeError, "failure 1"):
            engine._hedged_judge_call(call)

    def test_a_user_stop_reaches_both_requests(self):
        parent = runtime.ProviderCancellation()
        stops = [threading.Event(), threading.Event()]
        calls, lock = [], threading.Lock()

        def call():
            with lock:
                index = len(calls)
                calls.append(1)
            if index == 1:
                parent.cancel()
            stall_until_stopped(stops[index])

        with runtime.bind_provider_cancellation(parent), self.assertRaises(runtime.ProviderCancelled):
            engine._hedged_judge_call(call)
        self.assertTrue(all(stop.wait(2.0) for stop in stops))

    def test_a_stalled_coverage_window_is_covered_by_the_same_judge(self):
        """End to end: no fallback family, no 90 s wait, Luna's duplicate covers."""
        context = engine._build_judge_context({"openai": "Paris is the capital.", "gemini": "Paris, yes."},
                                              "Paris is the capital of France. It lies on the Seine.")
        ids = engine.coverage.sentence_ids(context.sentences)
        labels = engine._coverage_labels(context)
        payload = json.dumps({"sentences": [{"id": sid, "classification": "claim", "counter_quotes": [],
                                             "models": {label: "supports" for label in labels}} for sid in ids]})
        providers, lock = [], threading.Lock()

        def fake(provider, api_model, model_ref, api_keys, **kwargs):
            with lock:
                providers.append(provider)
                first = len(providers) == 1
            if first:
                stall_until_stopped()
            return payload

        with mock.patch.object(engine, "_call_engine_text", side_effect=fake):
            started = time.monotonic()
            result, meta = engine._run_coverage_judge(context, {"OpenRouter": "sk-or"}, "OpenAI", chat_mode=True)
        self.assertLess(time.monotonic() - started, 3.0)
        self.assertEqual(providers, ["openai", "openai"])
        self.assertEqual(meta["provider"], "OpenAI")
        self.assertEqual(sorted(result or {}), sorted(ids))


if __name__ == "__main__":
    unittest.main()

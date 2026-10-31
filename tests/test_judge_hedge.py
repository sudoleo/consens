"""A judge call that hangs gets an identical second request (_hedged_judge_call),
and later the next family's judge alongside.

Chat review 2026-10-18: Luna judge attempts ran into their 90 s limit in prod.
A stall now costs JUDGE_HEDGE_SECONDS: the duplicate answers, the first one is
stopped. Fast calls never pay for a duplicate. Since 2026-10-21 a judge that
hangs for every request (Luna via Azure on 2026-10-17) costs
JUDGE_FALLBACK_SECONDS instead of the attempt's 90 s: the next family's judge
checks alongside and the first answer wins. A Differences attempt that stalls
stops after JUDGE_ATTEMPT_SECONDS and the next family answers, like Coverage
(prod 2026-10-15: a 243 s judge call).
"""
import json
import threading
import time
import unittest
from unittest import mock

from app.services.llm import consensus_engine as engine
from app.services.llm import provider_runtime as runtime


ANSWER = ("Paris is the capital of France. Some say the capital is Lyon. "
          "It rains every second day. Others say rain is rare there.")
KEYS = {"OpenRouter": "sk-or"}


def difference(claim, *quotes):
    return {"type": "contradiction", "severity": "minor", "claim": claim, "consensus_anchor": "",
            "positions": [{"stance": quote, "models": [label], "quote": quote}
                          for quote, label in zip(quotes, ("Model A", "Model B"))]}


def differences_payload(*items):
    return json.dumps({"differences": list(items), "best_model": "Model A"})


CAPITAL = difference("Capital", "Paris is the capital", "the capital is Lyon")


def query(fake, **patches):
    """query_differences as the Consensus pipeline calls it, with ``fake`` as
    every judge request and ``patches`` (timeouts) on the engine."""
    with mock.patch.object(engine, "_call_engine_text", side_effect=fake), mock.patch.multiple(engine, **patches):
        return engine.query_differences({"openai": ANSWER, "gemini": ANSWER, "grok": ANSWER},
                                        "Paris is the capital.", KEYS, differences_model="OpenAI")


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
        labels = context.labels
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
            result, meta = engine._run_coverage_judge(context, KEYS, "OpenAI")
        self.assertLess(time.monotonic() - started, 3.0)
        self.assertEqual(providers, ["openai", "openai"])
        self.assertEqual(meta["provider"], "OpenAI")
        self.assertEqual(sorted(result or {}), sorted(ids))


class FallbackFamilyTests(unittest.TestCase):
    """The plan's next family joins a judge call that hangs for every request."""

    def setUp(self):
        for name, value in (("JUDGE_HEDGE_SECONDS", 0.05), ("JUDGE_FALLBACK_SECONDS", 0.15)):
            patcher = mock.patch.object(engine, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_the_fallback_answers_when_the_duplicate_hangs_too(self):
        stopped = [threading.Event(), threading.Event()]
        calls, lock = [], threading.Lock()

        def call():
            with lock:
                index = len(calls)
                calls.append(1)
            stall_until_stopped(stopped[index])

        won = {}
        started = time.monotonic()
        self.assertEqual(engine._hedged_judge_call(call, fallback=lambda: "next family", won=won), "next family")
        self.assertLess(time.monotonic() - started, 2.0)
        self.assertEqual(won, {"fallback": True})
        # Luna's first request and its duplicate both stop.
        self.assertTrue(all(stop.wait(2.0) for stop in stopped))

    def test_a_judge_answering_before_the_fallback_wait_never_asks_it(self):
        fallback = mock.Mock(return_value="next family")

        def call():
            time.sleep(0.08)
            return "luna"

        won = {}
        self.assertEqual(engine._hedged_judge_call(call, fallback=fallback, won=won), "luna")
        time.sleep(0.2)
        fallback.assert_not_called()
        self.assertEqual(won, {})

    def test_the_fallback_waits_for_a_spare_call_in_the_budget_too(self):
        budget = runtime.AnalysisBudget(seconds=30, max_calls=2)
        budget.calls = 1
        fallback = mock.Mock(return_value="next family")

        def call():
            time.sleep(0.3)
            return "slow"

        with runtime.bind_analysis_budget(budget):
            self.assertEqual(engine._hedged_judge_call(call, fallback=fallback), "slow")
        fallback.assert_not_called()

    def test_a_hanging_coverage_judge_is_covered_by_the_next_family(self):
        """End to end: Luna hangs for every request; Gemini checks the window
        alongside after JUDGE_FALLBACK_SECONDS, not after the 90 s attempt."""
        context = engine._build_judge_context({"openai": "Paris is the capital.", "gemini": "Paris, yes."},
                                              "Paris is the capital of France. It lies on the Seine.")
        ids = engine.coverage.sentence_ids(context.sentences)
        labels = context.labels
        payload = json.dumps({"sentences": [{"id": sid, "classification": "claim", "counter_quotes": [],
                                             "models": {label: "supports" for label in labels}} for sid in ids]})
        providers, lock = [], threading.Lock()

        def fake(provider, api_model, model_ref, api_keys, **kwargs):
            with lock:
                providers.append(provider)
            if provider == "openai":
                stall_until_stopped()
            return payload

        with mock.patch.object(engine, "_call_engine_text", side_effect=fake):
            started = time.monotonic()
            result, meta = engine._run_coverage_judge(context, KEYS, "OpenAI")
        self.assertLess(time.monotonic() - started, 3.0)
        self.assertEqual(providers, ["openai", "openai", "gemini"])
        # The record names the judge that answered.
        self.assertEqual(meta["provider"], "Gemini")
        self.assertEqual(sorted(result or {}), sorted(ids))

    def test_a_hanging_differences_judge_is_covered_by_the_next_family(self):
        calls, lock = [], threading.Lock()

        def fake(provider, api_model, model_ref, api_keys, **kwargs):
            if kwargs.get("json_schema") is not engine.DIFFERENCES_JSON_SCHEMA:
                return "{}"  # coverage judge: unusable output is tolerated
            with lock:
                calls.append(provider)
            if provider == "openai":
                stall_until_stopped()
            return differences_payload(CAPITAL)

        started = time.monotonic()
        _, data = query(fake, JUDGE_ATTEMPT_SECONDS=1.0)
        self.assertLess(time.monotonic() - started, 3.0)
        # Luna, its duplicate, then the next family alongside: it answers.
        self.assertEqual(calls, ["openai", "openai", "gemini"])
        self.assertEqual(data["judges"]["differences"]["provider"], "Gemini")
        self.assertEqual([item["claim"] for item in data["differences"]], ["Capital"])


class StalledDifferencesJudgeTests(unittest.TestCase):
    """A stalled Differences attempt stops after JUDGE_ATTEMPT_SECONDS; its
    retry is skipped and the plan's next family answers."""

    def test_a_stalled_primary_hands_over_to_the_next_family(self):
        calls, lock = [], threading.Lock()

        def fake(provider, api_model, model_ref, api_keys, **kwargs):
            if kwargs.get("json_schema") is not engine.DIFFERENCES_JSON_SCHEMA:
                return "{}"
            with lock:
                calls.append(provider)
            if provider == "openai":
                stall_until_stopped()
            return differences_payload(CAPITAL)

        started = time.monotonic()
        _, data = query(fake, JUDGE_ATTEMPT_SECONDS=0.05)
        self.assertLess(time.monotonic() - started, 3.0)
        self.assertEqual(calls, ["openai", "gemini"])
        self.assertEqual(data["judges"]["differences"]["provider"], "Gemini")
        self.assertEqual([item["claim"] for item in data["differences"]], ["Capital"])

    def test_a_user_stop_is_no_timeout(self):
        calls = []
        parent = engine.ProviderCancellation()

        def fake(provider, api_model, model_ref, api_keys, **kwargs):
            if kwargs.get("json_schema") is not engine.DIFFERENCES_JSON_SCHEMA:
                return "{}"
            calls.append(provider)
            parent.cancel()
            stall_until_stopped()

        with engine.bind_provider_cancellation(parent):
            _, data = query(fake, JUDGE_ATTEMPT_SECONDS=30)
        self.assertEqual(calls, ["openai"])
        self.assertIsNone(data)


if __name__ == "__main__":
    unittest.main()

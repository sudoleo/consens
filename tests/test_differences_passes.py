"""Two parallel differences passes (Agent) and their merge.

Judge audit 2026-10-07: one GPT-6 Luna pass found about two thirds of the real
disagreements, two passes together about four fifths. The second pass runs in
parallel and only adds what the first did not report.
"""
import json
import time
import threading
import unittest
from unittest import mock

from app.services.llm import consensus_engine as engine
from app.services.llm.consensus_engine import merge_difference_passes, query_differences


def difference(claim, *quotes, anchor="", models=(("OpenAI",), ("Gemini",))):
    return {"type": "contradiction", "severity": "minor", "claim": claim, "consensus_anchor": anchor,
            "positions": [{"stance": quote, "models": list(group), "quote": quote}
                          for quote, group in zip(quotes, models)]}


class MergeDifferencePassesTests(unittest.TestCase):
    def test_keeps_the_first_pass_and_adds_only_new_disagreements(self):
        first = {"differences": [difference("Capital", "Paris is the capital", "the capital is Lyon")]}
        second = {"differences": [
            # Same passage, reworded claim and a slightly longer quote: a duplicate.
            difference("Which city is the capital", "Paris is the capital of France", "the capital is Lyon"),
            difference("Rainfall", "it rains every second day", "rain is rare there"),
        ]}
        self.assertEqual(merge_difference_passes(first, second), 1)
        self.assertEqual([item["claim"] for item in first["differences"]], ["Capital", "Rainfall"])

    def test_same_sentence_counts_once_only_with_the_same_models(self):
        same = difference("A", "short", "quote", anchor="Prices rose in 2026.")
        first = {"differences": [same]}
        duplicate = difference("B", "other words", "elsewhere", anchor="Prices rose in 2026.")
        other_sides = difference("C", "other words", "elsewhere", anchor="Prices rose in 2026.",
                                 models=(("Grok",), ("Mistral",)))
        self.assertEqual(merge_difference_passes(first, {"differences": [duplicate, other_sides]}), 1)
        self.assertEqual([item["claim"] for item in first["differences"]], ["A", "C"])


class ParallelPassTests(unittest.TestCase):
    ANSWER = ("Paris is the capital of France. Some say the capital is Lyon. "
              "It rains every second day. Others say rain is rare there.")

    def run_query(self, passes, payloads):
        calls, lock = [], threading.Lock()

        def fake(provider, api_model, model_ref, api_keys, **kwargs):
            if kwargs.get("json_schema") is not engine.DIFFERENCES_JSON_SCHEMA:
                return "{}"  # coverage judge: unusable output is tolerated
            with lock:
                calls.append(provider)
                return json.dumps(payloads[min(len(calls), len(payloads)) - 1])

        with mock.patch.object(engine, "_call_engine_text", side_effect=fake):
            _, data = query_differences({"openai": self.ANSWER, "gemini": self.ANSWER, "grok": self.ANSWER},
                                        "Paris is the capital.", {"OpenRouter": "sk-or"},
                                        differences_model="OpenAI", chat_mode=True, passes=passes)
        return calls, data

    @staticmethod
    def payload(*items):
        return {"differences": [dict(item, positions=[dict(p, models=["Model A"] if i == 0 else ["Model B"])
                                                      for i, p in enumerate(item["positions"])])
                                for item in items], "best_model": "Model A"}

    def test_two_passes_run_and_merge(self):
        capital = difference("Capital", "Paris is the capital", "the capital is Lyon")
        rain = difference("Rain", "It rains every second day", "rain is rare there")
        # Disjoint findings: whichever pass finishes first, the other adds one.
        calls, data = self.run_query(2, [self.payload(capital), self.payload(rain)])
        self.assertEqual(len(calls), 2)
        self.assertEqual(sorted(item["claim"] for item in data["differences"]), ["Capital", "Rain"])
        self.assertEqual(data["judges"]["differences"]["passes"], 2)
        self.assertEqual(data["judges"]["differences"]["second_pass_added"], 1)
        # The score counts the merged list: two minor contradictions.
        self.assertEqual(data["agreement"]["minor_contradictions"], 2)

    def test_default_stays_a_single_pass(self):
        capital = difference("Capital", "Paris is the capital", "the capital is Lyon")
        calls, data = self.run_query(1, [self.payload(capital)])
        self.assertEqual(len(calls), 1)
        self.assertNotIn("passes", data["judges"]["differences"])

    def test_a_failed_pass_is_covered_by_the_other(self):
        capital = difference("Capital", "Paris is the capital", "the capital is Lyon")
        calls, lock = [], threading.Lock()

        def fake(provider, api_model, model_ref, api_keys, **kwargs):
            if kwargs.get("json_schema") is not engine.DIFFERENCES_JSON_SCHEMA:
                return "{}"
            with lock:
                calls.append(provider)
                first = len(calls) == 1
            if first:
                raise RuntimeError("OpenRouter: 401 - invalid API key")
            return json.dumps(self.payload(capital))

        with mock.patch.object(engine, "_call_engine_text", side_effect=fake):
            _, data = query_differences({"openai": self.ANSWER, "gemini": self.ANSWER, "grok": self.ANSWER},
                                        "Paris is the capital.", {"OpenRouter": "sk-or"},
                                        differences_model="OpenAI", chat_mode=True, passes=2)
        self.assertIsNotNone(data)
        self.assertEqual([item["claim"] for item in data["differences"]], ["Capital"])


class PrimaryOutageTests(unittest.TestCase):
    def test_only_the_first_pass_falls_back_when_the_primary_judge_is_down(self):
        capital = difference("Capital", "Paris is the capital", "the capital is Lyon")
        calls, lock = [], threading.Lock()

        def fake(provider, api_model, model_ref, api_keys, **kwargs):
            if kwargs.get("json_schema") is not engine.DIFFERENCES_JSON_SCHEMA:
                return "{}"
            with lock:
                calls.append(provider)
            if provider == "openai":
                raise RuntimeError("503 service unavailable")
            return json.dumps(ParallelPassTests.payload(capital))

        answer = ParallelPassTests.ANSWER
        with mock.patch.object(engine, "_call_engine_text", side_effect=fake):
            _, data = query_differences({"openai": answer, "gemini": answer, "grok": answer},
                                        "Paris is the capital.", {"OpenRouter": "sk-or"},
                                        differences_model="OpenAI", chat_mode=True, passes=2)
        # Both passes try Luna (failed calls are not billed); only one falls back.
        self.assertEqual(calls.count("gemini"), 1)
        self.assertEqual(data["judges"]["differences"]["provider"], "Gemini")


class LanguageRuleTests(unittest.TestCase):
    def test_judge_writes_in_the_language_of_the_consensus_answer(self):
        context = engine._build_judge_context({"openai": "Uno.", "gemini": "Eins."}, "One.")
        prompt = engine._build_differences_prompt_from(context)
        self.assertIn("in the language of the consensus answer", prompt)
        self.assertIn("language of the consensus answer", engine._differences_system_prompt())


if __name__ == "__main__":
    unittest.main()


class SecondPassEdgeCaseTests(unittest.TestCase):
    """The second pass may add findings; it must never hold, break or outlive
    the check (grace time, user stop, errors, missing quotes)."""
    ANSWER = ParallelPassTests.ANSWER
    CAPITAL = difference("Capital", "Paris is the capital", "the capital is Lyon")

    def setUp(self):
        patcher = mock.patch.multiple(engine, SECOND_PASS_GRACE_MIN_SECONDS=0.2, SECOND_PASS_GRACE_MAX_SECONDS=0.3)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.second_saw_cancel = threading.Event()

    def fake(self, *, primary_error=None):
        payload = json.dumps(ParallelPassTests.payload(self.CAPITAL))

        def call(provider, api_model, model_ref, api_keys, **kwargs):
            if kwargs.get("json_schema") is not engine.DIFFERENCES_JSON_SCHEMA:
                return "{}"
            if threading.current_thread().name.startswith("differences-pass"):
                cancellation = engine.current_provider_cancellation()
                for _ in range(200):  # a stuck provider: up to 10 s
                    if cancellation is not None and cancellation.cancelled:
                        self.second_saw_cancel.set()
                        raise engine.ProviderCancelled("stopped")
                    time.sleep(0.05)
                return payload
            if primary_error:
                raise primary_error
            return payload
        return call

    def query(self, **kwargs):
        return query_differences({"openai": self.ANSWER, "gemini": self.ANSWER, "grok": self.ANSWER},
                                 "Paris is the capital.", {"OpenRouter": "sk-or"},
                                 differences_model="OpenAI", chat_mode=True, passes=2, **kwargs)

    def test_a_stuck_second_pass_is_stopped_after_its_grace_time(self):
        started = time.monotonic()
        with mock.patch.object(engine, "_call_engine_text", side_effect=self.fake()):
            _, data = self.query()
        self.assertLess(time.monotonic() - started, 3.0)
        self.assertTrue(self.second_saw_cancel.wait(2.0))
        self.assertEqual([item["claim"] for item in data["differences"]], ["Capital"])
        meta = data["judges"]["differences"]
        self.assertEqual((meta["passes"], meta["second_pass_failed"]), (1, True))

    def test_a_user_stop_ends_the_second_pass_too(self):
        parent = engine.ProviderCancellation()
        threading.Timer(0.2, parent.cancel).start()
        with mock.patch.multiple(engine, SECOND_PASS_GRACE_MIN_SECONDS=30, SECOND_PASS_GRACE_MAX_SECONDS=30), \
                mock.patch.object(engine, "_call_engine_text", side_effect=self.fake()), \
                engine.bind_provider_cancellation(parent):
            started = time.monotonic()
            self.query()
        self.assertLess(time.monotonic() - started, 3.0)
        self.assertTrue(self.second_saw_cancel.is_set())

    def test_an_error_in_the_first_pass_stops_the_second(self):
        with mock.patch.object(engine, "parse_differences_payload", side_effect=RuntimeError("bug")), \
                mock.patch.object(engine, "_call_engine_text", side_effect=self.fake()):
            with self.assertRaises(RuntimeError):
                self.query()
        self.assertTrue(self.second_saw_cancel.wait(2.0))

    def test_first_pass_failure_is_recorded_when_the_second_answers(self):
        def call(provider, api_model, model_ref, api_keys, **kwargs):
            if kwargs.get("json_schema") is not engine.DIFFERENCES_JSON_SCHEMA:
                return "{}"
            if threading.current_thread().name.startswith("differences-pass"):
                return json.dumps(ParallelPassTests.payload(self.CAPITAL))
            raise RuntimeError("OpenRouter: 401 - invalid API key")

        with mock.patch.object(engine, "_call_engine_text", side_effect=call):
            _, data = self.query()
        meta = data["judges"]["differences"]
        self.assertTrue(meta["first_pass_failed"])
        self.assertEqual(meta["passes"], 2)

    def test_findings_without_quotes_merge_by_their_claim(self):
        bare = lambda claim: {"type": "contradiction", "claim": claim, "positions": [{"models": ["OpenAI"], "quote": ""}]}
        first = {"differences": [bare("Whether the bonus still exists.")]}
        self.assertEqual(merge_difference_passes(first, {"differences": [bare("Whether the bonus still exists"),
                                                                         bare("Which year the RFC was published")]}), 1)


class SecondPassSurfacesTests(unittest.TestCase):
    def test_stats_keep_how_much_the_second_pass_added(self):
        from app.services.differences_stats import build_differences_stats_doc
        doc = build_differences_stats_doc({"differences": [], "claims": [], "agreement": {},
                                           "judges": {"differences": {"provider": "OpenAI", "model": "m", "tier": "standard",
                                                                      "passes": 2, "second_pass_added": 3}}})
        self.assertEqual((doc["judges"]["differences"]["passes"], doc["judges"]["differences"]["second_pass_added"]), (2, 3))

    def test_streamed_judge_also_gets_the_answer_language_by_name(self):
        systems = []
        payload = json.dumps({"differences": [], "best_model": ""})

        def fake_stream(provider, *args, **kwargs):
            systems.append(kwargs.get("system"))
            yield {"type": "delta", "text": payload}

        english = ("The evidence does not show that the drug is safe for the heart, and the risk of a stroke is "
                   "higher for people who take it with other drugs or have kidney problems.")
        with mock.patch.object(engine, "_stream_engine_text", side_effect=fake_stream):
            list(engine.stream_differences({"openai": english, "mistral": english}, english,
                                           {"OpenRouter": "sk-or"}, differences_model="OpenAI"))
        self.assertIn("English", systems[0])


class BoundedBudgetTests(unittest.TestCase):
    def test_a_nearly_spent_call_budget_keeps_one_pass(self):
        from app.services.llm.provider_runtime import AnalysisBudget, bind_analysis_budget
        capital = difference("Capital", "Paris is the capital", "the capital is Lyon")
        calls, lock = [], threading.Lock()

        def fake(provider, api_model, model_ref, api_keys, **kwargs):
            if kwargs.get("json_schema") is not engine.DIFFERENCES_JSON_SCHEMA:
                return "{}"
            with lock:
                calls.append(provider)
            return json.dumps(ParallelPassTests.payload(capital))

        budget = AnalysisBudget(seconds=60, max_calls=5)
        budget.calls = 2
        answer = ParallelPassTests.ANSWER
        with mock.patch.object(engine, "_call_engine_text", side_effect=fake), bind_analysis_budget(budget):
            _, data = query_differences({"openai": answer, "gemini": answer, "grok": answer},
                                        "Paris is the capital.", {"OpenRouter": "sk-or"},
                                        differences_model="OpenAI", chat_mode=True, passes=2)
        self.assertEqual(len(calls), 1)
        self.assertNotIn("passes", data["judges"]["differences"])

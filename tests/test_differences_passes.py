"""Two parallel differences passes (Agent) and their merge.

Judge audit 2026-10-07: one GPT-6 Luna pass found about two thirds of the real
disagreements, two passes together about four fifths. The second pass runs in
parallel and only adds what the first did not report.
"""
import json
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

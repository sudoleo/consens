"""Old answers keep the name of the model that wrote them.

The family constants in app/core/config.py move on with each model
generation. Stored answers, share pages and benchmark runs still carry the
old IDs and engine keys; they must not take on the successor's name.
"""
import unittest
from unittest import mock

import app.core.config as cfg
from app.services import share_snapshots as snapshots
from benchmark import config as benchmark_config


RETIRED_LABELS = {
    "claude-haiku-4-5": "Claude Haiku 4.5",
    "claude-opus-4-8": "Claude Opus 4.8",
    "gpt-5.4-mini": "GPT-5.4 mini",
    "gpt-5.5": "GPT-5.5",
    "gpt-5.6-luna": "GPT-5.6 Luna",
    "gpt-5.6-sol": "GPT-5.6 Sol",
    "gemini-3.5-flash": "Gemini 3.5 Flash",
    "gemini-3.6-flash": "Gemini 3.6 Flash",
    "gemini-3.1-pro-preview": "Gemini 3.1",
}


class RetiredModelLabelTests(unittest.TestCase):
    def test_retired_ids_keep_their_label_and_are_not_migrated(self):
        current = set(cfg.DEFAULT_MODEL_BY_PROVIDER.values()) | {
            provider.pro_model for provider in cfg.PROVIDERS.values()
        }
        for model_id, label in RETIRED_LABELS.items():
            with self.subTest(model_id=model_id):
                self.assertNotIn(model_id, current)
                self.assertEqual(cfg.canonical_model_id(model_id), model_id)
                self.assertEqual(cfg.get_model_label(model_id), label)

    def test_share_pages_name_the_engine_model_of_their_time(self):
        expected = {
            "OpenAI": "GPT-5.4 mini",
            "OpenAI-Pro": "GPT-5.5",
            "Anthropic": "Claude Haiku 4.5",
            "Anthropic-Pro": "Claude Opus 4.8",
            "Gemini-Pro": "Gemini 3.1",
        }
        for engine, label in expected.items():
            with self.subTest(engine=engine):
                self.assertEqual(snapshots.consensus_model_view(engine)["model"], label)
                self.assertNotEqual(cfg.get_consensus_model_label(engine), label)

    def test_direct_consensus_models_that_left_the_lists_keep_name_and_logo(self):
        # Old Open Models shares store "gpt-5.6-luna"; the admin lists no
        # longer hold it, so MODEL_CONFIGS cannot name it any more.
        with mock.patch.dict(cfg.MODEL_CONFIGS, {}, clear=True):
            for raw, family, label in (
                ("gpt-5.6-luna", "OpenAI", "GPT-5.6 Luna"),
                ("gemini-3.5-flash", "Gemini", "Gemini 3.5 Flash"),
                ("claude-sonnet-5", "Anthropic", "Claude Sonnet 5"),
            ):
                with self.subTest(raw=raw):
                    view = snapshots.consensus_model_view(raw)
                    self.assertEqual((view["provider"], view["model"]), (family, label))
                    self.assertTrue(view["icon"])
            self.assertEqual(snapshots.consensus_model_view("Foo-Pro")["provider"], "")

    def test_consulted_models_on_old_share_pages_keep_their_names(self):
        view = snapshots.consulted_models_view([
            "Anthropic Claude: claude-haiku-4-5",
            "OpenAI: gpt-5.6-luna",
        ])
        self.assertEqual([entry["model"] for entry in view], ["Claude Haiku 4.5", "GPT-5.6 Luna"])

    def test_family_aliases_run_the_current_models(self):
        self.assertEqual(cfg.CONSENSUS_ENGINE_ALIASES["Anthropic"], ("anthropic", "claude-haiku-5.5"))
        self.assertEqual(cfg.CONSENSUS_ENGINE_ALIASES["Anthropic-Pro"], ("anthropic", "claude-opus-5.5"))
        self.assertEqual(cfg.CONSENSUS_ENGINE_ALIASES["OpenAI"], ("openai", "gpt-6-luna"))
        self.assertEqual(cfg.CONSENSUS_ENGINE_ALIASES["OpenAI-Pro"], ("openai", "gpt-6.1-sol"))
        self.assertEqual(cfg.CONSENSUS_ENGINE_ALIASES["Gemini-Pro"], ("gemini", "gemini-4-carbon"))

    def test_memory_edit_model_is_not_the_family_default(self):
        # Prod stores gpt-5.6-luna; the admin save accepts it only while it
        # equals the code default, so the family default must not drag it.
        self.assertEqual(cfg.DEFAULT_MEMORY_EDIT_CONFIG["memory_edit_model"], "gpt-5.6-luna")

    def test_benchmark_pins_stay_frozen(self):
        pins = {model.provider: (model.internal_id, model.api_model) for model in benchmark_config.MODELS}
        self.assertEqual(pins["anthropic"], ("claude-opus-4-8", "anthropic/claude-opus-4.8"))
        self.assertEqual(pins["gemini"], ("gemini-3.5-flash", "google/gemini-3.5-flash"))
        self.assertEqual(benchmark_config.CONSENSUS_MODEL, "gemini-3.5-flash")
        benchmark_config.assert_pins_match_config()


if __name__ == "__main__":
    unittest.main()

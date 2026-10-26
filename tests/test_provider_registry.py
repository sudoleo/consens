"""Die Provider-Registry ist die einzige Quelle fuer Modellfamilien.

Eine neue Familie soll ein Eintrag in cfg.PROVIDERS plus ihre Modelle in der
Admin-DB sein -- kein weiteres paralleles Dict, keine weitere Sechser-Liste und
keine weitere Stelle im Prompt-Bau. Diese Tests halten genau das fest: alle
abgeleiteten Strukturen decken die Registry vollstaendig ab, und die
Consensus-/Differences-Pipeline haengt an keiner festen Anzahl von Familien.
"""

import unittest
from pathlib import Path

import app.core.config as cfg
from app.services import chat_store, opinion_map, share_snapshots, topics, watch_scheduler
from app.services.llm import engines, provider_transport
from app.services.llm.consensus_engine import (
    _build_consensus_prompt,
    _build_differences_prompt,
    _model_answer_items,
)


class RegistryCoverageTests(unittest.TestCase):
    """Jede abgeleitete Struktur kennt genau die Familien der Registry."""

    def test_derived_model_maps_cover_every_family(self):
        families = set(cfg.PROVIDERS)
        for name, mapping in (
            ("DEFAULT_MODEL_BY_PROVIDER", cfg.DEFAULT_MODEL_BY_PROVIDER),
            ("FREE_DEFAULT_MODEL_BY_PROVIDER", cfg.FREE_DEFAULT_MODEL_BY_PROVIDER),
            ("PROVIDER_LABEL_BY_ID", cfg.PROVIDER_LABEL_BY_ID),
            ("OPENROUTER_MODEL_PREFIXES", cfg.OPENROUTER_MODEL_PREFIXES),
            ("DIFFERENCES_JUDGE_MODEL_BY_PROVIDER", cfg.DIFFERENCES_JUDGE_MODEL_BY_PROVIDER),
            ("PRO_JUDGE_MODEL_BY_PROVIDER", cfg.PRO_JUDGE_MODEL_BY_PROVIDER),
            ("CHAT_MEMORY_MODEL_BY_PROVIDER", cfg.CHAT_MEMORY_MODEL_BY_PROVIDER),
            ("MODEL_ORDER_BY_PROVIDER", cfg.MODEL_ORDER_BY_PROVIDER),
            ("_provider_allowed_sets()", cfg._provider_allowed_sets()),
        ):
            with self.subTest(mapping=name):
                self.assertEqual(set(mapping), families)

    def test_dead_config_aliases_stay_gone(self):
        """Audit C16: the registry set (PROVIDERS[key].models) is the one name
        for a family's models, LIMITS the one source for limits, and a model
        ID literal stands in config.py once."""
        for name in (
            "MAX_WORDS", "REASONING_MAX_TOKENS", "GEMINI_MAX_TOKENS",
            *(f"ALLOWED_{key.upper()}_MODELS" for key in cfg.PROVIDERS),
        ):
            with self.subTest(name=name):
                self.assertFalse(hasattr(cfg, name))
        source = Path(cfg.__file__).read_text(encoding="utf-8")
        self.assertEqual(source.count('"gpt-5.6-luna"'), 1)

    def test_every_family_has_both_consensus_aliases(self):
        for provider in cfg.PROVIDERS.values():
            with self.subTest(provider=provider.key):
                self.assertEqual(
                    cfg.CONSENSUS_ENGINE_ALIASES.get(provider.label),
                    (provider.key, provider.base_model),
                )
                self.assertEqual(
                    cfg.CONSENSUS_ENGINE_ALIASES.get(f"{provider.label}-Pro"),
                    (provider.key, provider.pro_model),
                )
                self.assertIn(provider.label, cfg.VALID_LEADERBOARD_MODELS)
                self.assertIn(f"{provider.label}-Pro", cfg.VALID_LEADERBOARD_MODELS)

    def test_base_model_is_free_and_pro_model_is_premium(self):
        for provider in cfg.PROVIDERS.values():
            with self.subTest(provider=provider.key):
                self.assertIn(provider.base_model, provider.models)
                self.assertNotIn(provider.base_model, cfg.PREMIUM_MODELS)
                if provider.pro_model in cfg.ZDR_UNAVAILABLE_MODEL_IDS:
                    # Ohne ZDR-Endpunkt (Meta: Muse Spark) gibt es kein
                    # waehlbares Pro-Modell und keinen "<Familie>-Pro"-Alias.
                    self.assertNotIn(provider.pro_model, provider.models)
                    self.assertNotIn(provider.pro_model, cfg.PREMIUM_MODELS)
                    self.assertNotIn(f"{provider.label}-Pro", cfg.ALLOWED_CONSENSUS_MODELS)
                    self.assertEqual(
                        cfg.PRO_JUDGE_MODEL_BY_PROVIDER[provider.key], provider.base_model
                    )
                    continue
                self.assertIn(provider.pro_model, provider.models)
                self.assertIn(provider.pro_model, cfg.PREMIUM_MODELS)

    def test_model_configs_resolve_every_allowed_model(self):
        for model_id in cfg.ALL_ALLOWED_MODELS:
            with self.subTest(model=model_id):
                config = cfg.MODEL_CONFIGS[model_id]
                self.assertIn(config.provider, cfg.PROVIDERS)
                self.assertTrue(config.api_model.startswith(
                    cfg.PROVIDERS[config.provider].openrouter_prefix
                ))

    def test_kimi_and_glm_request_and_attachment_policies_are_data(self):
        self.assertEqual(
            cfg.MODEL_CONFIGS[cfg.KIMI_BASE_MODEL].request_config,
            {
                "provider": {"only": ["moonshotai"], "allow_fallbacks": False},
                "reasoning": {"enabled": False},
            },
        )
        self.assertEqual(
            cfg.MODEL_CONFIGS[cfg.GLM_PRO_MODEL].request_config,
            {"reasoning": {"effort": "low"}},
        )
        self.assertTrue(cfg.MODEL_CONFIGS[cfg.GLM_BASE_MODEL].accepts_attachments)
        self.assertFalse(cfg.MODEL_CONFIGS[cfg.GLM_PRO_MODEL].accepts_attachments)
        self.assertFalse(cfg.MODEL_CONFIGS[cfg.DEEPSEEK_FLASH_MODEL].accepts_attachments)

    def test_meta_is_the_ninth_family_with_muse_as_its_product_name(self):
        meta = cfg.PROVIDERS["meta"]
        self.assertEqual(meta.openrouter_prefix, "meta/")
        self.assertEqual(meta.base_model, cfg.MUSE_BASE_MODEL)
        self.assertEqual(meta.pro_model, cfg.MUSE_PRO_MODEL)
        # Wie bei Anthropic/Claude traegt die Familie zwei Namen: "Meta" ist
        # der Consensus-Alias, "Muse" das Produkt im DOM.
        self.assertEqual(meta.ask_endpoint, "/ask_muse")
        self.assertEqual(meta.response_id, "museResponse")
        self.assertEqual(meta.checkbox_id, "selectMuse")
        # Der billige Contributor-Tarif darf nie erlaubt sein: dort fliessen
        # Prompts in Metas Produkte, was der ZDR-Zusage widerspricht.
        self.assertNotIn("muse-spark-1.3-contributor", meta.models)
        # Muse Spark hat bei OpenRouter keinen ZDR-Endpunkt (nur "Meta") und
        # ist deshalb nicht waehlbar; die Policy bleibt fuer spaeter stehen.
        self.assertIn(cfg.MUSE_PRO_MODEL, cfg.ZDR_UNAVAILABLE_MODEL_IDS)
        self.assertNotIn(cfg.MUSE_PRO_MODEL, meta.models)
        self.assertEqual(
            cfg.MODEL_REQUEST_CONFIG[cfg.MUSE_PRO_MODEL],
            {"reasoning": {"effort": "low"}},
        )
        self.assertTrue(cfg.MODEL_CONFIGS[cfg.MUSE_BASE_MODEL].accepts_attachments)

    def test_qwen_is_the_tenth_family_and_thinks_low(self):
        qwen = cfg.PROVIDERS["qwen"]
        self.assertEqual(list(cfg.PROVIDERS)[9], "qwen")
        self.assertEqual(qwen.openrouter_prefix, "qwen/")
        self.assertEqual((qwen.base_model, qwen.pro_model), (cfg.QWEN_BASE_MODEL, cfg.QWEN_PRO_MODEL))
        self.assertEqual((qwen.ask_endpoint, qwen.response_id, qwen.checkbox_id),
                         ("/ask_qwen", "qwenResponse", "selectQwen"))
        self.assertEqual(cfg.get_model_label(cfg.QWEN_BASE_MODEL), "Qwen3.8 27B")
        self.assertEqual(cfg.get_model_label(cfg.QWEN_PRO_MODEL), "Qwen3.8 Max Prime")
        # Without reasoning Qwen often skipped the search; "low" searched every time.
        for model in (cfg.QWEN_BASE_MODEL, cfg.QWEN_PRO_MODEL):
            self.assertEqual(cfg.MODEL_CONFIGS[model].request_config, {"reasoning": {"effort": "low"}})
            self.assertTrue(cfg.MODEL_CONFIGS[model].accepts_attachments)
        self.assertEqual(cfg.CONSENSUS_ENGINE_ALIASES["Qwen"], ("qwen", cfg.QWEN_BASE_MODEL))
        self.assertIn(cfg.QWEN_BASE_MODEL, cfg.CONSENSUS_PRESET_MODELS["balanced"]["answers"].values())

    def test_xiaomi_is_the_eleventh_family_and_answers_without_thinking(self):
        mimo = cfg.PROVIDERS["xiaomi"]
        self.assertEqual(list(cfg.PROVIDERS)[-1], "xiaomi")
        self.assertEqual(mimo.openrouter_prefix, "xiaomi/")
        self.assertEqual((mimo.base_model, mimo.pro_model), (cfg.MIMO_BASE_MODEL, cfg.MIMO_PRO_MODEL))
        self.assertEqual((mimo.ask_endpoint, mimo.response_id, mimo.checkbox_id),
                         ("/ask_mimo", "mimoResponse", "selectMiMo"))
        self.assertEqual(cfg.get_model_label(cfg.MIMO_BASE_MODEL), "MiMo V2.6 Flash")
        self.assertEqual(cfg.get_model_label(cfg.MIMO_PRO_MODEL), "MiMo V2.6 Pro")
        self.assertEqual(cfg.MODEL_CONFIGS[cfg.MIMO_BASE_MODEL].api_model, "xiaomi/mimo-v2.6-flash")
        # Both searched without thinking; with it, Flash emptied an answer at the limit.
        for model in (cfg.MIMO_BASE_MODEL, cfg.MIMO_PRO_MODEL):
            self.assertEqual(cfg.MODEL_CONFIGS[model].request_config, {"reasoning": {"enabled": False}})
            self.assertTrue(cfg.MODEL_CONFIGS[model].accepts_attachments)
        self.assertIn(cfg.MIMO_PRO_MODEL, cfg.PREMIUM_MODELS)
        self.assertNotIn(cfg.MIMO_BASE_MODEL, cfg.PREMIUM_MODELS)
        self.assertEqual(cfg.CONSENSUS_ENGINE_ALIASES["Xiaomi"], ("xiaomi", cfg.MIMO_BASE_MODEL))
        self.assertEqual(cfg.CONSENSUS_ENGINE_ALIASES["Xiaomi-Pro"], ("xiaomi", cfg.MIMO_PRO_MODEL))
        # Added on top: no preset changes with the family.
        for preset in cfg.CONSENSUS_PRESET_MODELS.values():
            self.assertNotIn("xiaomi", preset["answers"])

    def test_open_models_have_labels_and_gpt_oss_reads_text_only(self):
        # gpt-oss-120b is the one text-only model of an attachment-capable
        # family; every other OpenAI model keeps taking files.
        self.assertFalse(cfg.MODEL_CONFIGS[cfg.OPENAI_OSS_MODEL].accepts_attachments)
        self.assertTrue(cfg.MODEL_CONFIGS[cfg.OPENAI_LUNA_MODEL].accepts_attachments)
        self.assertTrue(cfg.PROVIDERS["openai"].model_accepts_attachments("gpt-new-admin-model"))
        self.assertTrue(cfg.MODEL_CONFIGS[cfg.GEMMA_MODEL].accepts_attachments)
        self.assertEqual(
            cfg.MODEL_CONFIGS[cfg.OPENAI_OSS_MODEL].request_config,
            {"reasoning": {"effort": "low"}},
        )
        self.assertEqual(cfg.get_model_label(cfg.OPENAI_OSS_MODEL), "gpt-oss-120b")
        self.assertEqual(cfg.get_model_label(cfg.GEMMA_MODEL), "Gemma 4 31B")


class ConsumerCoverageTests(unittest.TestCase):
    """Die Module rund um den Lauf ziehen ihre Familien aus der Registry."""

    def test_transport_order_and_labels_come_from_the_registry(self):
        self.assertEqual(provider_transport.PROVIDER_ORDER, tuple(cfg.PROVIDERS))
        self.assertEqual(provider_transport.PROVIDER_LABELS, cfg.PROVIDER_LABEL_BY_ID)

    def test_engine_model_maps_cover_every_family(self):
        self.assertEqual(set(engines._DEFAULT_MODEL_BY_PROVIDER), set(cfg.PROVIDERS))
        # The Reasoning switch no longer has its own model map (no Pro swap).
        self.assertFalse(hasattr(engines, "_DEEP_SEARCH_MODEL_BY_PROVIDER"))

    def test_product_surfaces_cover_every_family(self):
        labels = set(cfg.PROVIDER_LABEL_BY_ID.values())
        self.assertEqual(set(share_snapshots.PROVIDER_ORDER), labels)
        self.assertEqual(set(share_snapshots.PROVIDER_CITATION_LABELS), labels)
        self.assertEqual(set(chat_store.PROVIDER_DOCUMENT_IDS), labels)
        self.assertEqual(set(opinion_map.PROVIDERS), labels)
        self.assertEqual(set(topics.PROVIDER_ORDER), set(cfg.PROVIDERS))
        self.assertEqual(set(topics.PROVIDER_LABELS), set(cfg.PROVIDERS))

    def test_ask_endpoints_and_judge_vocabulary_cover_every_family(self):
        from app.api.routers.chat import ASK_PROVIDERS, router
        from app.services.llm.consensus_engine import (
            CANONICAL_MODEL_NAMES,
            normalize_model_name,
        )

        self.assertEqual(set(ASK_PROVIDERS), set(cfg.PROVIDERS))
        post_paths = {
            route.path
            for route in router.routes
            if "POST" in getattr(route, "methods", set())
        }
        self.assertLessEqual(
            {provider.ask_endpoint for provider in cfg.PROVIDERS.values()},
            post_paths,
        )
        for provider, label in cfg.PROVIDER_LABEL_BY_ID.items():
            with self.subTest(provider=provider):
                self.assertIs(ASK_PROVIDERS[provider].allowed_models,
                              cfg.PROVIDERS[provider].models)
                # Der Judge darf die Familie als Label, klein oder als
                # "<Label>-Pro" benennen; alles landet auf demselben Namen.
                self.assertEqual(CANONICAL_MODEL_NAMES[provider], label)
                self.assertEqual(normalize_model_name(label), label)
                self.assertEqual(normalize_model_name(f"{label}-Pro"), label)

    def test_preference_orders_stay_inside_the_registry(self):
        """Bewusst abweichende Reihenfolgen sind erlaubt, duerfen aber keine
        Familie verlieren -- sonst faellt eine neue Familie still hinten weg."""
        self.assertEqual(set(watch_scheduler.PROVIDER_ORDER), set(cfg.PROVIDERS))
        self.assertEqual(
            {provider.key for provider in cfg._consensus_alias_providers()},
            set(cfg.PROVIDERS),
        )


class PipelineIsFamilyCountAgnosticTests(unittest.TestCase):
    """Prompt-Bau und Judge haengen an der uebergebenen Menge, nicht an sechs."""

    def test_consensus_prompt_grows_and_shrinks_with_the_answers(self):
        for count in (2, 3, 6, 8):
            answers = {f"family{i}": f"answer {i}" for i in range(count)}
            with self.subTest(count=count):
                prompt = _build_consensus_prompt("Q?", answers, [], shuffle=False)
                for i in range(count):
                    self.assertIn(f"answer {i}", prompt)
                self.assertEqual(prompt.count("Expert opinion from"), count)

    def test_differences_prompt_anonymizes_any_number_of_families(self):
        answers = {f"family{i}": f"answer {i}" for i in range(8)}
        built = _build_differences_prompt(answers, "consensus text", excluded_models=[])
        self.assertIsNotNone(built)
        _prompt, anon_map, answers_by_model, _sentences = built
        self.assertEqual(len(anon_map), 8)
        self.assertEqual(len(answers_by_model), 8)
        self.assertEqual(sorted(anon_map), [f"Model {chr(65 + i)}" for i in range(8)])

    def test_answers_may_be_keyed_by_family_id_or_display_name(self):
        by_id = _model_answer_items({"openai": "a", "deepseek": "b"}, [])
        by_label = _model_answer_items({"OpenAI": "a", "DeepSeek": "b"}, [])
        self.assertEqual(by_id, [("OpenAI", "a"), ("DeepSeek", "b")])
        self.assertEqual(by_id, by_label)

    def test_empty_and_excluded_answers_drop_out(self):
        items = _model_answer_items(
            {"openai": "a", "mistral": "", "gemini": None, "grok": "d"},
            ["Grok"],
        )
        self.assertEqual(items, [("OpenAI", "a")])


if __name__ == "__main__":
    unittest.main()

import unittest
from pathlib import Path
from unittest import mock

from fastapi import HTTPException

import app.core.config as cfg
from app.api.routers import admin as admin_router
from app.api.routers.admin import (
    get_models,
    _model_dependencies,
    _server_enforced_models,
    normalize_models_document,
)
from app.api.routers.chat import (
    parse_boolean_flag,
    validate_question_word_limit,
)
from app.services.llm.base import validate_model
from app.services.llm.citations import source_response
from app.services.llm.engines import build_provider_payload


ROOT = Path(__file__).resolve().parents[1]


class _Snapshot:
    def __init__(self, data):
        self._data = None if data is None else dict(data)
        self.exists = data is not None

    def to_dict(self):
        return dict(self._data or {})


class _MemoryModelsDocument:
    """One in-memory ``app_config/models`` document with sequential transactions."""

    def __init__(self, data):
        self.data = None if data is None else dict(data)
        self.writes = []

    def get(self, transaction=None, **_kwargs):
        return _Snapshot(self.data)

    def set(self, data, merge=False, **_kwargs):
        self.writes.append(dict(data))
        self.data = {**(self.data or {}), **data} if merge else dict(data)

    def delete(self):
        self.writes.append(None)
        self.data = None

    def database(self):
        document = self

        class Transaction:
            def set(self, ref, data, merge=False):
                ref.set(data, merge=merge)

            def delete(self, ref):
                ref.delete()

        class Database:
            def collection(self, _name):
                return self

            def document(self, _name):
                return document

            def run_transaction(self, operation):
                return operation(Transaction())

        return Database()


class ModelConfigurationTests(unittest.TestCase):
    def _valid_admin_payload(self):
        return {
            **{
                provider.key: list(provider.models)
                for provider in cfg.PROVIDERS.values()
            },
            "premium": list(cfg.PREMIUM_MODELS),
            "consensus": list(cfg.ALLOWED_CONSENSUS_MODELS),
            "preset_models": cfg.get_consensus_preset_models(),
            "defaults": dict(cfg.FREE_DEFAULT_MODEL_BY_PROVIDER),
            "watch_models": {
                tier: dict(models) for tier, models in cfg.WATCH_MODELS_BY_TIER.items()
            },
            "watch_consensus_models": dict(cfg.WATCH_CONSENSUS_MODELS_BY_TIER),
            "judge_models": cfg.get_judge_models(),
            "judge_models_pro": cfg.get_pro_judge_models(),
            "judge_families": cfg.get_judge_families(),
            "chat_memory_models": cfg.get_chat_memory_models(),
            "limits": cfg.get_limits_config(),
        }

    def test_rejected_admin_document_cannot_mutate_runtime_limits(self):
        payload = self._valid_admin_payload()
        payload["limits"] = {**payload["limits"], "free_consensus_run_limit": 999}
        payload["preset_models"] = {}
        before = cfg.get_limits_config()
        fake_document = mock.Mock()
        fake_db = mock.Mock()
        fake_db.collection.return_value.document.return_value = fake_document

        with (
            mock.patch.object(admin_router, "_require_admin"),
            mock.patch.object(admin_router, "db_firestore", fake_db),
            self.assertRaises(HTTPException) as exc_info,
        ):
            admin_router.update_models(mock.Mock(), payload)

        self.assertEqual(exc_info.exception.status_code, 400)
        self.assertEqual(cfg.get_limits_config(), before)
        fake_document.set.assert_not_called()

    def test_runtime_reload_rolls_back_all_mutations_on_activation_error(self):
        payload = self._valid_admin_payload()

        class Snapshot:
            exists = True

            def to_dict(self):
                return payload

        document = mock.Mock()
        document.get.return_value = Snapshot()
        database = mock.Mock()
        database.collection.return_value.document.return_value = document
        before_limits = cfg.get_limits_config()
        before_openai = set(cfg.PROVIDERS["openai"].models)

        with (
            mock.patch("app.core.security.db_firestore", database),
            mock.patch.object(cfg, "apply_watch_models", side_effect=RuntimeError("boom")),
            self.assertRaises(RuntimeError),
        ):
            cfg.load_models_from_db(strict=True)

        self.assertEqual(cfg.get_limits_config(), before_limits)
        self.assertEqual(set(cfg.PROVIDERS["openai"].models), before_openai)

    def test_admin_update_restores_persisted_document_on_activation_error(self):
        payload = self._valid_admin_payload()
        previous = {"schema_version": 7, "openai": ["previous-model"], "revision": 4}
        doc_ref = _MemoryModelsDocument(previous)

        with (
            mock.patch.object(admin_router, "_require_admin"),
            mock.patch.object(admin_router, "db_firestore", doc_ref.database()),
            mock.patch.object(
                admin_router,
                "load_models_from_db",
                side_effect=RuntimeError("activation failed"),
            ),
            self.assertRaises(HTTPException) as exc_info,
        ):
            admin_router.update_models(mock.Mock(), payload)

        self.assertEqual(exc_info.exception.status_code, 500)
        self.assertEqual(len(doc_ref.writes), 2)
        restored = dict(doc_ref.data)
        # The previous content comes back under a new revision number, so every
        # process that already activated the failed revision reloads it.
        self.assertEqual(restored.pop("revision"), 6)
        self.assertEqual(restored, {k: v for k, v in previous.items() if k != "revision"})

    def test_failed_activation_never_rolls_back_a_newer_foreign_revision(self):
        """R25: A writes, B writes, A's activation fails -> B stays."""
        doc_ref = _MemoryModelsDocument({"marker": "X", "revision": 1})

        def foreign_write_then_fail(**_kwargs):
            doc_ref.data = {"marker": "B", "revision": 3}
            raise RuntimeError("activation in A failed")

        with mock.patch.object(admin_router, "db_firestore", doc_ref.database()), \
                mock.patch.object(admin_router, "load_models_from_db",
                                  side_effect=foreign_write_then_fail):
            with self.assertRaises(RuntimeError):
                admin_router._persist_and_activate_models(
                    doc_ref, {"marker": "A"}, expected_revision=1,
                )
        self.assertEqual(doc_ref.data, {"marker": "B", "revision": 3})

    def test_stale_admin_save_is_refused_with_409_and_nothing_is_written(self):
        payload = {**self._valid_admin_payload(), "revision": 2}
        doc_ref = _MemoryModelsDocument({"openai": ["x"], "revision": 5})
        with (
            mock.patch.object(admin_router, "_require_admin"),
            mock.patch.object(admin_router, "db_firestore", doc_ref.database()),
            mock.patch.object(admin_router, "load_models_from_db") as load,
            self.assertRaises(HTTPException) as exc_info,
        ):
            admin_router.update_models(mock.Mock(), payload)
        self.assertEqual(exc_info.exception.status_code, 409)
        self.assertEqual(doc_ref.writes, [])
        load.assert_not_called()

    def test_successful_save_increments_revision_and_get_exposes_it(self):
        payload = {**self._valid_admin_payload(), "revision": 5}
        doc_ref = _MemoryModelsDocument({"openai": ["x"], "revision": 5})
        with (
            mock.patch.object(admin_router, "_require_admin"),
            mock.patch.object(admin_router, "db_firestore", doc_ref.database()),
            mock.patch.object(admin_router, "load_models_from_db"),
        ):
            result = admin_router.update_models(mock.Mock(), payload)
            self.assertEqual(result["revision"], 6)
            self.assertEqual(doc_ref.data["revision"], 6)
            self.assertEqual(get_models(mock.Mock())["revision"], 6)

    def test_every_process_adopts_a_newer_published_revision(self):
        doc_ref = _MemoryModelsDocument({"revision": 7})
        original = cfg.ACTIVE_MODEL_CONFIG_REVISION
        try:
            with mock.patch("app.core.security.db_firestore", doc_ref.database()), \
                    mock.patch.object(cfg, "load_models_from_db", return_value=True) as load:
                cfg.ACTIVE_MODEL_CONFIG_REVISION = 7
                self.assertFalse(cfg.refresh_models_if_changed())
                load.assert_not_called()
                doc_ref.data = {"revision": 8}
                self.assertTrue(cfg.refresh_models_if_changed())
                load.assert_called_once_with(strict=True, persist_backfill=False)
        finally:
            cfg.ACTIVE_MODEL_CONFIG_REVISION = original

    def test_readiness_config_load_never_creates_missing_document(self):
        snapshot = mock.Mock(exists=False)
        document = mock.Mock()
        document.get.return_value = snapshot
        database = mock.Mock()
        database.collection.return_value.document.return_value = document

        with mock.patch("app.core.security.db_firestore", database):
            loaded = cfg.load_models_from_db(strict=True, persist_backfill=False)

        self.assertTrue(loaded)
        document.get.assert_called_once_with(timeout=5.0, retry=None)
        document.set.assert_not_called()

    def test_admin_models_get_is_read_only_and_preserves_judge_family(self):
        raw = {
            "openai": [cfg.DEFAULT_OPENAI_MODEL],
            "mistral": [cfg.DEFAULT_MISTRAL_MODEL],
            "anthropic": [cfg.DEFAULT_ANTHROPIC_MODEL],
            "gemini": [cfg.DEFAULT_GEMINI_MODEL],
            "deepseek": [cfg.DEEPSEEK_FLASH_MODEL],
            "grok": [cfg.DEFAULT_GROK_MODEL],
            "premium": [],
            "consensus": ["Gemini"],
            "judge_families": {"openai": "gemini"},
        }

        class FakeSnapshot:
            exists = True

            def to_dict(self):
                return dict(raw)

        class FakeDocument:
            def __init__(self):
                self.set_calls = []

            def get(self):
                return FakeSnapshot()

            def set(self, *args, **kwargs):
                self.set_calls.append((args, kwargs))

        class FakeCollection:
            def __init__(self, document):
                self._document = document

            def document(self, name):
                self.name = name
                return self._document

        class FakeDB:
            def __init__(self, document):
                self._document = document

            def collection(self, name):
                self.name = name
                return FakeCollection(self._document)

        document = FakeDocument()
        with (
            mock.patch.object(admin_router, "db_firestore", FakeDB(document)),
            mock.patch.object(admin_router, "_require_admin"),
        ):
            response = get_models(mock.Mock())

        self.assertEqual(response["judge_families"], {"openai": "gemini"})
        self.assertEqual(document.set_calls, [])

    def test_removed_low_reasoning_aliases_are_not_runtime_models(self):
        self.assertFalse(hasattr(cfg, "EARLY_DEFAULT_MODEL_BY_PROVIDER"))
        self.assertFalse(hasattr(cfg, "EARLY_MODELS"))
        self.assertFalse(hasattr(cfg, "FRONTIER_LOW_MODELS"))
        for model_id in cfg.REMOVED_MODEL_IDS:
            with self.subTest(model=model_id):
                self.assertNotIn(model_id, cfg.ALL_ALLOWED_MODELS)
                self.assertNotIn(model_id, cfg.ALLOWED_CONSENSUS_MODELS)
                self.assertNotIn(model_id, cfg.PREMIUM_MODELS)

    def test_missing_openrouter_legacy_ids_stay_removed(self):
        legacy_ids = {
            "gpt-5-chat-latest",
            "gpt-5.3",
            "gpt-5.3-chat-latest",
            "mistral-large-latest",
            "mistral-medium-latest",
            "ministral-3b-latest",
            "ministral-8b-latest",
            "claude-sonnet-4-20250514",
            "claude-3-7-sonnet-20250219",
            "claude-3-5-haiku-20241022",
            "claude-sonnet-4-5",
            "claude-opus-4-5",
            "claude-sonnet-4-6",
            "claude-opus-4-6",
            "claude-opus-4-7",
            "gemini-2.0-flash",
        }
        self.assertLessEqual(legacy_ids, cfg.REMOVED_MODEL_IDS)
        self.assertTrue(legacy_ids.isdisjoint(cfg.ALL_ALLOWED_MODELS))
        self.assertTrue(legacy_ids.isdisjoint(cfg.PREMIUM_MODELS))

        for provider, model_id in (
            ("openai", "gpt-5.3"),
            ("mistral", "mistral-large-latest"),
            ("anthropic", "claude-sonnet-4-6"),
            ("gemini", "gemini-2.0-flash"),
        ):
            normalized = normalize_models_document({provider: [model_id]})
            self.assertNotIn(model_id, normalized[provider])

    def test_admin_drops_removed_aliases_everywhere(self):
        removed = next(iter(cfg.REMOVED_MODEL_IDS))
        normalized = normalize_models_document({
            "openai": [removed, cfg.DEFAULT_OPENAI_MODEL],
            "mistral": [cfg.DEFAULT_MISTRAL_MODEL],
            "anthropic": [cfg.DEFAULT_ANTHROPIC_MODEL],
            "gemini": [cfg.DEFAULT_GEMINI_MODEL],
            "deepseek": [cfg.DEEPSEEK_FLASH_MODEL],
            "grok": [cfg.DEFAULT_GROK_MODEL],
            "premium": [removed],
            "consensus": [removed, "Gemini"],
            "defaults": {"openai": removed},
        })
        self.assertNotIn(removed, normalized["openai"])
        self.assertNotIn(removed, normalized["premium"])
        self.assertNotIn(removed, normalized["consensus"])
        self.assertNotEqual(normalized["defaults"].get("openai"), removed)

    def test_new_gemini_models_are_direct_and_temperature_free(self):
        for model_id in (cfg.DEFAULT_GEMINI_MODEL, cfg.GEMINI_35_FLASH_MODEL, cfg.GEMINI_36_FLASH_MODEL):
            with self.subTest(model=model_id):
                request = build_provider_payload(
                    "gemini",
                    question="payload dry run",
                    system_prompt="system",
                    model_override=model_id,
                    max_output_tokens=123,
                )
                self.assertEqual(request["internal_model"], model_id)
                self.assertEqual(request["api_model"], cfg.openrouter_model_id(model_id, "gemini"))
                payload = request["payload"]
                self.assertEqual(payload["max_tokens"], 123)
                self.assertNotIn("temperature", payload)
                self.assertEqual(payload["provider"], {"sort": "throughput", "data_collection": "deny"})
                self.assertEqual(payload["tools"][0]["type"], "openrouter:web_search")

    def test_web_search_budget_and_engine_per_family(self):
        """Grok braucht `exa`, sonst greift keiner der Suchparameter.

        Mit "auto" landet Grok auf xAIs nativer Live-Suche, die `max_uses`
        ignoriert: gemessen 6-11 Quellen und ~66.000 Prompt-Tokens statt 5
        Quellen und ~4.800. Die anderen Familien bleiben auf "auto" -- ein
        erzwungenes "native" schaltet Geminis Grounding-Suche ganz ab.
        """
        for provider, expected_engine in [
            ("openai", "auto"),
            ("mistral", "auto"),
            ("anthropic", "auto"),
            ("gemini", "auto"),
            ("deepseek", "auto"),
            ("grok", "exa"),
        ]:
            with self.subTest(provider=provider):
                payload = build_provider_payload(
                    provider, question="dry run", system_prompt="system"
                )["payload"]
                tool = payload["tools"][0]
                self.assertEqual(tool["type"], "openrouter:web_search")
                self.assertEqual(tool["parameters"]["engine"], expected_engine)
                # Eine Suchrunde im Normallauf; jede weitere kostet eine
                # komplette Modellrunde extra.
                self.assertEqual(tool["parameters"]["max_uses"], 1)
                self.assertEqual(payload["max_tool_calls"], 2)

    def test_reasoning_switch_keeps_model_prompt_and_single_search_round(self):
        """Reasoning (wire name deep_search) only thinks longer: no Pro-model
        swap, no extra prompt, still one search round."""
        for provider in cfg.PROVIDERS:
            with self.subTest(provider=provider):
                base = cfg.PROVIDERS[provider].base_model
                plain = build_provider_payload(
                    provider, question="dry run", system_prompt="system",
                    model_override=base,
                )
                reasoning = build_provider_payload(
                    provider, question="dry run", system_prompt="system",
                    model_override=base, deep_search=True,
                )
                self.assertEqual(reasoning["internal_model"], base)
                self.assertEqual(reasoning["api_model"], plain["api_model"])
                self.assertEqual(
                    reasoning["payload"]["messages"], plain["payload"]["messages"]
                )
                self.assertEqual(reasoning["payload"]["tools"][0]["parameters"]["max_uses"], 1)
                self.assertEqual(reasoning["payload"]["max_tool_calls"], 2)

    def test_reasoning_output_limit_is_the_larger_of_tier_and_reasoning_cap(self):
        original = cfg.get_limits_config()
        try:
            cfg.apply_limits({**original, "free_max_tokens": 4096,
                              "pro_max_tokens": 16384, "reasoning_max_tokens": 8192})
            self.assertEqual(cfg.get_output_token_limit("free"), 4096)
            self.assertEqual(cfg.get_output_token_limit("free", True), 8192)
            self.assertEqual(cfg.get_output_token_limit("plus", True), 8192)
            # A tier limit above the reasoning cap is never lowered.
            self.assertEqual(cfg.get_output_token_limit("pro", True), 16384)
            # The word limit no longer depends on the switch.
            self.assertEqual(cfg.get_word_limit("free", True), cfg.get_word_limit("free"))
        finally:
            cfg.apply_limits(original)

    def test_old_deep_think_limit_keys_are_ignored_or_mapped_once(self):
        legacy = {
            "free_deep_search_max_words": 0,
            "pro_deep_search_max_words": 1000,
            "free_deep_search_max_tokens": 0,
            "pro_deep_search_max_tokens": 12000,
        }
        normalized = cfg.normalize_limits_config(legacy)
        self.assertEqual(normalized["reasoning_max_tokens"], 12000)
        for key in legacy:
            self.assertNotIn(key, normalized)
        # Once the new key exists it wins over the legacy value.
        normalized = cfg.normalize_limits_config({**legacy, "reasoning_max_tokens": 9000})
        self.assertEqual(normalized["reasoning_max_tokens"], 9000)
        self.assertEqual(
            cfg.normalize_limits_config({})["reasoning_max_tokens"], 8192
        )

    def test_limits_below_their_minimum_fall_back_to_the_default(self):
        """Audit C16: an admin typo of 0 (or 8 for 8192) no longer silences
        every synthesis; counters keep 0 as a real setting."""
        normalized = cfg.normalize_limits_config({
            "consensus_max_tokens": 0,
            "differences_max_tokens": 8,
            "free_max_words": 0,
            "consensus_max_answer_chars": 5,
            "watch_probe_max_per_day": 0,
            "share_min_sources": 0,
        })
        defaults = cfg.DEFAULT_LIMITS
        self.assertEqual(normalized["consensus_max_tokens"], defaults["consensus_max_tokens"])
        self.assertEqual(normalized["differences_max_tokens"], defaults["differences_max_tokens"])
        self.assertEqual(normalized["free_max_words"], defaults["free_max_words"])
        self.assertEqual(normalized["consensus_max_answer_chars"], defaults["consensus_max_answer_chars"])
        self.assertEqual(normalized["watch_probe_max_per_day"], 0)
        self.assertEqual(normalized["share_min_sources"], 0)
        # A real, smaller setting above the floor is kept.
        self.assertEqual(cfg.normalize_limits_config({"consensus_max_tokens": 2048})["consensus_max_tokens"], 2048)

    def test_admin_save_never_stores_a_zero_token_limit(self):
        payload = {**self._valid_admin_payload(), "revision": 4}
        payload["limits"] = {**payload["limits"], "consensus_max_tokens": 0}
        doc_ref = _MemoryModelsDocument({"openai": ["x"], "revision": 4})
        with (
            mock.patch.object(admin_router, "_require_admin"),
            mock.patch.object(admin_router, "db_firestore", doc_ref.database()),
            mock.patch.object(admin_router, "load_models_from_db", return_value=True),
        ):
            admin_router.update_models(mock.Mock(), payload)
        self.assertEqual(
            doc_ref.data["limits"]["consensus_max_tokens"],
            cfg.DEFAULT_LIMITS["consensus_max_tokens"],
        )

    def test_reload_never_shows_lock_free_readers_an_empty_or_free_premium_state(self):
        """Audit C8: requests read the model sets, LIMITS and the Consensus
        list without the config lock while a reload runs. Every state a reader
        can see in between keeps what stays, and a new Pro model is never
        allowed while still Free."""
        views = []
        recorded = {}

        def reader(base, methods):
            def wrap(name):
                def method(self, *args):
                    result = getattr(base, name)(self, *args)
                    views.append({key: type(obj).__mro__[1](obj) for key, obj in recorded.items()})
                    return result
                return method
            return type(f"Reader{base.__name__}", (base,), {name: wrap(name) for name in methods})

        ReaderSet = reader(set, ("add", "discard", "remove", "clear", "update", "difference_update",
                                 "intersection_update", "__ior__", "__iand__", "__isub__"))
        ReaderDict = reader(dict, ("clear", "update", "pop", "setdefault", "__setitem__", "__delitem__"))
        ReaderList = reader(list, ("clear", "extend", "append", "insert", "remove", "__setitem__", "__delitem__"))

        openai = cfg.PROVIDERS["openai"]
        leaving = next(model for model in sorted(cfg.PREMIUM_MODELS & openai.models)
                       if model != openai.pro_model)
        arriving = "gpt-reader-probe"
        payload = self._valid_admin_payload()
        payload["openai"] = [*payload["openai"], arriving]
        payload["premium"] = [model for model in payload["premium"] if model != leaving] + [arriving]
        before = {"premium": set(cfg.PREMIUM_MODELS), "openai": set(openai.models),
                  "consensus": set(cfg.ALLOWED_CONSENSUS_MODELS)}

        class Snapshot:
            exists = True

            def to_dict(self):
                return payload

        database = mock.Mock()
        database.collection.return_value.document.return_value.get.return_value = Snapshot()
        state = cfg._capture_runtime_config()
        revision = cfg.ACTIVE_MODEL_CONFIG_REVISION
        original_models = openai.models
        recorded.update(premium=ReaderSet(cfg.PREMIUM_MODELS), openai=ReaderSet(openai.models),
                        limits=ReaderDict(cfg.LIMITS), consensus=ReaderList(cfg.ALLOWED_CONSENSUS_MODELS))
        try:
            object.__setattr__(openai, "models", recorded["openai"])
            with (
                mock.patch("app.core.security.db_firestore", database),
                mock.patch.object(cfg, "PREMIUM_MODELS", recorded["premium"]),
                mock.patch.object(cfg, "LIMITS", recorded["limits"]),
                mock.patch.object(cfg, "ALLOWED_CONSENSUS_MODELS", recorded["consensus"]),
            ):
                self.assertTrue(cfg.load_models_from_db(strict=True, persist_backfill=False))
                after = {"premium": set(cfg.PREMIUM_MODELS), "openai": set(openai.models),
                         "consensus": set(cfg.ALLOWED_CONSENSUS_MODELS)}
        finally:
            object.__setattr__(openai, "models", original_models)
            cfg._restore_runtime_config(state)
            cfg.ACTIVE_MODEL_CONFIG_REVISION = revision

        self.assertIn(arriving, after["premium"])
        self.assertNotIn(leaving, after["premium"])
        self.assertTrue(views)
        for view in views:
            for key in ("premium", "openai", "consensus"):
                self.assertLessEqual(before[key] & after[key], set(view[key]), key)
            self.assertLessEqual(set(cfg.DEFAULT_LIMITS), set(view["limits"]))
            # Allowed means runnable: a new Pro model is Pro from its first moment.
            if arriving in view["openai"]:
                self.assertIn(arriving, view["premium"])

    def test_gemini_models_are_available_to_admin(self):
        enforced = _server_enforced_models()["gemini"]
        self.assertEqual(enforced, [])
        self.assertIn(cfg.DEFAULT_GEMINI_MODEL, cfg.PROVIDERS["gemini"].models)
        self.assertIn(cfg.GEMINI_36_FLASH_MODEL, cfg.PROVIDERS["gemini"].models)

    def test_admin_premium_is_limited_to_configured_provider_models(self):
        normalized = normalize_models_document({
            "openai": [cfg.DEFAULT_OPENAI_MODEL],
            "mistral": [cfg.DEFAULT_MISTRAL_MODEL],
            "anthropic": [cfg.DEFAULT_ANTHROPIC_MODEL],
            "gemini": [cfg.DEFAULT_GEMINI_MODEL],
            "deepseek": [cfg.DEEPSEEK_FLASH_MODEL],
            "grok": [cfg.DEFAULT_GROK_MODEL],
            "premium": ["gpt-5.5", cfg.DEFAULT_GEMINI_MODEL],
        })
        self.assertEqual(
            normalized["premium"],
            sorted({
                cfg.DEFAULT_GEMINI_MODEL,
                cfg.KIMI_PRO_MODEL,
                cfg.GLM_PRO_MODEL,
                cfg.QWEN_PRO_MODEL,
            }),
        )

    def test_admin_dependencies_are_informative_not_server_enforced(self):
        normalized = normalize_models_document({
            "openai": [cfg.DEFAULT_OPENAI_MODEL],
            "mistral": [cfg.DEFAULT_MISTRAL_MODEL],
            "anthropic": [cfg.DEFAULT_ANTHROPIC_MODEL],
            "gemini": [cfg.DEFAULT_GEMINI_MODEL],
            "deepseek": [cfg.DEEPSEEK_FLASH_MODEL],
            "grok": [cfg.DEFAULT_GROK_MODEL],
            "premium": [],
            "defaults": {"openai": cfg.DEFAULT_OPENAI_MODEL},
        })
        dependencies = _model_dependencies(normalized)
        self.assertIn("Free default", dependencies["openai"][cfg.DEFAULT_OPENAI_MODEL])
        self.assertEqual(_server_enforced_models()["openai"], [])

    def test_retired_grok_aliases_are_canonicalized(self):
        normalized = normalize_models_document({
            "grok": ["grok-4-fast-reasoning-latest", "grok-4-1-fast-non-reasoning-latest"],
            "premium": ["grok-4-fast-reasoning-latest"],
        })
        self.assertEqual(normalized["grok"], ["grok-4.3"])
        self.assertNotIn("grok-4-fast-reasoning-latest", normalized["grok"])
        # The former reasoning variants of 4.3 and 4.20 (2026-10-11) as well.
        normalized = normalize_models_document({
            "grok": [cfg.GROK_NO_REASONING_MODEL, "grok-4.20-non-reasoning", "grok-4.20", "grok-4.3"],
            "premium": ["grok-4.20"],
        })
        self.assertEqual(normalized["grok"], ["grok-4.3"])

    def test_grok_reasoning_follows_the_reasoning_switch(self):
        default = build_provider_payload(
            "grok", question="q", system_prompt="s",
            model_override=cfg.GROK_NO_REASONING_MODEL, max_output_tokens=123,
        )
        self.assertEqual(default["api_model"], "x-ai/grok-4.3")
        self.assertNotIn("reasoning", default["payload"])

        high = build_provider_payload(
            "grok", question="q", system_prompt="s",
            model_override="grok-4.3", deep_search=True, max_output_tokens=123,
        )
        self.assertEqual(high["payload"]["reasoning"], {"effort": "high"})

    def test_muse_reasoning_is_pinned_low_because_it_cannot_be_disabled(self):
        base = build_provider_payload(
            "meta", question="q", system_prompt="s",
            model_override=cfg.MUSE_BASE_MODEL, max_output_tokens=123,
        )
        self.assertEqual(base["api_model"], "meta/muse-glimmer-30b")
        self.assertEqual(base["payload"]["reasoning"], {"effort": "low"})
        # Muse Spark ist unter ZDR nicht bedienbar und damit nicht waehlbar;
        # seine Request-Policy bleibt fuer eine spaetere Wiederaufnahme stehen.
        self.assertNotIn(cfg.MUSE_PRO_MODEL, cfg.MODEL_CONFIGS)
        self.assertEqual(
            cfg.MODEL_REQUEST_CONFIG[cfg.MUSE_PRO_MODEL], {"reasoning": {"effort": "low"}},
        )

    def test_kimi_search_keeps_moonshot_route_and_model_reasoning(self):
        for model, deep, reasoning in (
            (cfg.KIMI_BASE_MODEL, False, {"enabled": False}),
            (cfg.KIMI_PRO_MODEL, False, {"effort": "low"}),
            # Reasoning keeps Kimi's explicit model policy (no model swap).
            (cfg.KIMI_BASE_MODEL, True, {"enabled": False}),
            (cfg.KIMI_PRO_MODEL, True, {"effort": "low"}),
        ):
            with self.subTest(model=model, deep=deep):
                payload = build_provider_payload(
                    "kimi", question="current events", model_override=model,
                    deep_search=deep, max_output_tokens=4096,
                )["payload"]
                self.assertEqual(payload["provider"], {
                    "sort": "throughput", "data_collection": "deny",
                    "only": ["moonshotai"], "allow_fallbacks": False,
                })
                self.assertEqual(payload["reasoning"], reasoning)
                self.assertEqual(payload["max_tokens"], 4096)
                self.assertEqual(payload["tools"][0]["type"], "openrouter:web_search")
                self.assertEqual(payload["tools"][0]["parameters"]["max_uses"], 1)

    def test_kimi_and_glm_payload_policies_are_applied(self):
        kimi = build_provider_payload(
            "kimi", question="q", system_prompt="s",
            model_override=cfg.KIMI_BASE_MODEL, max_output_tokens=123,
        )
        glm = build_provider_payload(
            "glm", question="q", system_prompt="s",
            model_override=cfg.GLM_PRO_MODEL, max_output_tokens=123,
        )

        self.assertEqual(kimi["api_model"], "moonshotai/kimi-k2.6")
        self.assertEqual(kimi["payload"]["reasoning"], {"enabled": False})
        self.assertEqual(glm["api_model"], "z-ai/glm-5.3")
        self.assertEqual(glm["payload"]["reasoning"], {"effort": "low"})

    def test_effective_reasoning_policy_matches_answer_payload_precedence(self):
        self.assertEqual(
            cfg.effective_model_reasoning("grok", "grok-4.3"),
            (None, "provider default"),
        )
        self.assertEqual(
            cfg.effective_model_reasoning("grok", "grok-4.3", reasoning=True),
            ({"effort": "high"}, "REASONING_EFFORT_ON"),
        )
        self.assertEqual(
            cfg.effective_model_reasoning("mistral", cfg.MISTRAL_PRO_MODEL),
            ({"effort": "high"}, "MISTRAL_REASONING_MODELS"),
        )
        existing = {"profile": "existing", "models": {}}
        self.assertEqual(cfg.REASONING_EFFORT_ON, "high")
        # Reasoning on fills a still-unset policy with "high" ...
        self.assertEqual(
            cfg.effective_model_reasoning(
                "openai", cfg.OPENAI_PRO_MODEL, reasoning=True, policy=existing
            ),
            ({"effort": "high"}, "REASONING_EFFORT_ON"),
        )
        self.assertEqual(
            cfg.effective_model_reasoning(
                "anthropic", cfg.DEFAULT_ANTHROPIC_MODEL, reasoning=True, policy=existing
            ),
            ({"effort": "high"}, "REASONING_EFFORT_ON"),
        )
        # ... while explicit model policies and Mistral defaults keep winning.
        self.assertEqual(
            cfg.effective_model_reasoning(
                "kimi", cfg.KIMI_BASE_MODEL, reasoning=True, policy=existing
            ),
            ({"enabled": False}, "MODEL_REQUEST_CONFIG"),
        )
        self.assertEqual(
            cfg.effective_model_reasoning(
                "mistral", cfg.MISTRAL_PRO_MODEL, reasoning=True, policy=existing
            ),
            ({"effort": "high"}, "MISTRAL_REASONING_MODELS"),
        )
        self.assertEqual(
            cfg.effective_model_reasoning("anthropic", cfg.DEFAULT_ANTHROPIC_MODEL),
            (None, "provider default"),
        )

    def test_access_control_only_has_free_and_pro_models(self):
        validate_model(
            cfg.DEFAULT_OPENAI_MODEL, cfg.PROVIDERS["openai"].models, "OpenAI", is_pro=False
        )
        with self.assertRaises(HTTPException) as denied:
            validate_model("gpt-5.5", cfg.PROVIDERS["openai"].models, "OpenAI", is_pro=False)
        self.assertEqual(denied.exception.status_code, 403)
        validate_model("gpt-5.5", cfg.PROVIDERS["openai"].models, "OpenAI", is_pro=True)

        # Nach Entfernen des Early-Gates darf DeepSeek Pro nicht ueber das
        # fruehere is_free-Override am Backend-Gate vorbeikommen.
        with self.assertRaises(HTTPException) as deepseek_denied:
            validate_model(
                cfg.DEEPSEEK_PRO_MODEL,
                cfg.PROVIDERS["deepseek"].models,
                "DeepSeek",
                is_pro=False,
            )
        self.assertEqual(deepseek_denied.exception.status_code, 403)

    def test_presets_are_complete_and_free_presets_stay_free(self):
        presets = {preset["id"]: preset for preset in cfg.get_consensus_presets()}
        self.assertEqual(set(presets), {"fast", "balanced", "thorough"})
        for preset in presets.values():
            self.assertEqual(len(preset["models"]), cfg.MAX_RUN_FAMILIES)
            self.assertLessEqual(set(preset["models"]), set(cfg.DEFAULT_MODEL_BY_PROVIDER))
        self.assertFalse(presets["fast"]["pro_only"])
        self.assertTrue(presets["thorough"]["pro_only"])

        normalized = normalize_models_document({
            "openai": [cfg.OPENAI_LUNA_MODEL, "gpt-5.5"],
            "mistral": [cfg.DEFAULT_MISTRAL_MODEL],
            "anthropic": [cfg.DEFAULT_ANTHROPIC_MODEL],
            "gemini": [cfg.DEFAULT_GEMINI_MODEL],
            "deepseek": [cfg.DEEPSEEK_FLASH_MODEL],
            "grok": [cfg.DEFAULT_GROK_MODEL, cfg.GROK_FAST_MODEL],
            "premium": ["gpt-5.5"],
            "preset_models": {
                "balanced": {
                    **cfg._BASE_CONSENSUS_PRESET_MODELS["balanced"],
                    "answers": {
                        **cfg._BASE_CONSENSUS_PRESET_MODELS["balanced"]["answers"],
                        "qwen": cfg.QWEN_PRO_MODEL,
                    },
                    "consensus": "OpenAI-Pro",
                },
            },
        })
        self.assertEqual(
            normalized["preset_models"]["balanced"]["answers"]["qwen"],
            cfg.QWEN_BASE_MODEL,
        )
        self.assertEqual(
            normalized["preset_models"]["balanced"]["consensus"], cfg.OPENAI_LUNA_MODEL
        )

    def test_admin_and_picker_have_no_early_contract(self):
        admin = (ROOT / "templates" / "admin.html").read_text(encoding="utf-8")
        admin_js = (ROOT / "static" / "js" / "admin.js").read_text(encoding="utf-8")
        index = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")
        picker = (ROOT / "static" / "js" / "model-picker.js").read_text(encoding="utf-8")
        tier = (ROOT / "static" / "js" / "user-tier.js").read_text(encoding="utf-8")
        combined = "\n".join((admin, admin_js, index, picker, tier))
        self.assertNotIn("EARLY_DEFAULT_MODELS", combined)
        self.assertNotIn("early-option", combined)
        self.assertNotIn("isUserEarly", combined)
        self.assertIn("'In use'", admin_js)
        self.assertNotIn("re-added automatically", combined)
        self.assertNotIn("Server-enforced Pro model", combined)

    def test_provider_errors_are_structured_without_fallback_response(self):
        response = source_response({
            "text": "",
            "sources": [],
            "error": "OpenAI could not complete this request. Please try again later.",
            "error_code": "provider_request_failed",
        })
        self.assertEqual(response["response"], "")
        self.assertEqual(response["error_code"], "provider_request_failed")
        self.assertNotIn("error_detail", response)

    def test_input_helpers(self):
        for question in (None, "", "   "):
            with self.assertRaises(HTTPException) as exc:
                validate_question_word_limit(question, tier="free", deep_search=False)
            self.assertEqual(exc.exception.status_code, 400)
        self.assertTrue(parse_boolean_flag(" true "))
        self.assertFalse(parse_boolean_flag("false"))
        self.assertFalse(parse_boolean_flag(None))


if __name__ == "__main__":
    unittest.main()

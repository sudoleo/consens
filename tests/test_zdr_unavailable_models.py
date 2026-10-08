"""Modelle ohne ZDR-Endpunkt bei OpenRouter sind nirgends waehlbar.

Die Produktion fuehrt ihre Modelllisten in Firestore (``app_config/models``);
dort stehen solche IDs teils noch. Der Load muss sie als Tombstones entfernen,
und jede gespeicherte Auswahl, die auf sie zeigt (Free-Default, Preset,
Judge, Chat-Memory, Watch, Consensus-Engine), faellt auf das Familien-Default
zurueck, statt bei OpenRouter mit 404 "No endpoints found matching your data
policy" zu scheitern.
"""
from unittest import mock

import pytest

import app.core.config as cfg
from app.services.llm import agent_client

DEAD = sorted(cfg.ZDR_UNAVAILABLE_MODEL_IDS)


class _Snapshot:
    exists = True

    def __init__(self, data):
        self._data = data

    def to_dict(self):
        return dict(self._data)


def _prod_like_document():
    """Ausschnitt des Prod-Dokuments vom 2026-10-08 plus tote Referenzen."""
    providers = {key: sorted(provider.models) for key, provider in cfg.PROVIDERS.items()}
    providers["openai"] += ["gpt-3.5-turbo", "chat-latest"]
    providers["gemini"] += ["gemini-3.1-flash-lite-preview"]
    providers["meta"] = [cfg.MUSE_BASE_MODEL, cfg.MUSE_PRO_MODEL]
    return {
        **providers,
        "premium": sorted(cfg.PREMIUM_MODELS | {"chat-latest", cfg.MUSE_PRO_MODEL}),
        "consensus": ["Gemini", "OpenAI", "Meta", "Meta-Pro", "chat-latest",
                      cfg.MUSE_PRO_MODEL],
        "defaults": {"openai": "gpt-3.5-turbo", "gemini": "gemini-3.1-flash-lite-preview"},
        "preset_models": {
            "balanced": {
                "answers": {
                    "openai": "gpt-3.5-turbo",
                    "gemini": "gemini-3.1-flash-lite-preview",
                    "meta": cfg.MUSE_BASE_MODEL,
                    "deepseek": cfg.DEEPSEEK_FLASH_MODEL,
                    "glm": cfg.GLM_BASE_MODEL,
                    "kimi": cfg.KIMI_BASE_MODEL,
                },
                "consensus": "Gemini",
            },
            "thorough": {
                "answers": {
                    "openai": "chat-latest",
                    "meta": cfg.MUSE_PRO_MODEL,
                    "gemini": cfg.GEMINI_PRO_MODEL,
                    "deepseek": cfg.DEEPSEEK_PRO_MODEL,
                    "glm": cfg.GLM_PRO_MODEL,
                    "kimi": cfg.KIMI_PRO_MODEL,
                },
                "consensus": "Meta-Pro",
            },
        },
        "judge_models": {"gemini": "gemini-3.1-flash-lite-preview", "openai": "gpt-3.5-turbo"},
        "judge_models_pro": {"meta": cfg.MUSE_PRO_MODEL, "openai": "chat-latest"},
        "chat_memory_models": {"openai": "gpt-3.5-turbo"},
        "watch_models": {
            "free": {"gemini": "gemini-3.1-flash-lite-preview", "openai": "gpt-3.5-turbo",
                     "deepseek": cfg.DEEPSEEK_FLASH_MODEL},
            "pro": {"meta": cfg.MUSE_PRO_MODEL, "openai": "chat-latest",
                    "deepseek": cfg.DEEPSEEK_FLASH_MODEL},
        },
        "revision": 7,
    }


@pytest.fixture
def loaded_prod_document():
    state = cfg._capture_runtime_config()
    revision = cfg.ACTIVE_MODEL_CONFIG_REVISION
    document = mock.Mock()
    document.get.return_value = _Snapshot(_prod_like_document())
    database = mock.Mock()
    database.collection.return_value.document.return_value = document
    try:
        with mock.patch("app.core.security.db_firestore", database):
            assert cfg.load_models_from_db(strict=True, persist_backfill=False)
        document.set.assert_not_called()
        yield
    finally:
        cfg._restore_runtime_config(state)
        cfg.ACTIVE_MODEL_CONFIG_REVISION = revision


def test_code_fallback_offers_no_zdr_unavailable_model():
    assert cfg.ZDR_UNAVAILABLE_MODEL_IDS <= cfg.REMOVED_MODEL_IDS
    assert not cfg.ALL_ALLOWED_MODELS & cfg.ZDR_UNAVAILABLE_MODEL_IDS
    assert not cfg.PREMIUM_MODELS & cfg.ZDR_UNAVAILABLE_MODEL_IDS
    assert not set(cfg.MODEL_CONFIGS) & cfg.ZDR_UNAVAILABLE_MODEL_IDS
    assert "Meta-Pro" not in cfg.DEFAULT_CONSENSUS_MODELS
    assert "Meta-Pro" not in cfg.ALLOWED_CONSENSUS_MODELS
    assert cfg.PRO_JUDGE_MODEL_BY_PROVIDER["meta"] == cfg.MUSE_BASE_MODEL


def test_prod_document_with_dead_ids_loads_without_offering_them(loaded_prod_document):
    for provider in cfg.PROVIDERS.values():
        assert not provider.models & cfg.ZDR_UNAVAILABLE_MODEL_IDS, provider.key
        assert not set(cfg.get_ordered_models(provider.key)) & cfg.ZDR_UNAVAILABLE_MODEL_IDS
    assert not cfg.PREMIUM_MODELS & cfg.ZDR_UNAVAILABLE_MODEL_IDS
    assert not set(cfg.ALLOWED_CONSENSUS_MODELS) & ({"Meta-Pro"} | cfg.ZDR_UNAVAILABLE_MODEL_IDS)
    assert {"Gemini", "OpenAI", "Meta"} <= set(cfg.ALLOWED_CONSENSUS_MODELS)


def test_saved_selections_of_dead_ids_fall_back_to_the_family_default(loaded_prod_document):
    defaults = cfg.FREE_DEFAULT_MODEL_BY_PROVIDER
    assert defaults["openai"] == cfg.DEFAULT_OPENAI_MODEL
    assert defaults["gemini"] == cfg.DEFAULT_GEMINI_MODEL

    # Presets fallen auf ihre eigene Produktbelegung fuer die Familie zurueck.
    balanced = cfg.CONSENSUS_PRESET_MODELS["balanced"]["answers"]
    base = cfg._BASE_CONSENSUS_PRESET_MODELS["balanced"]["answers"]
    assert balanced["openai"] == base["openai"]
    assert balanced["gemini"] == base.get("gemini", defaults["gemini"])
    thorough = cfg.CONSENSUS_PRESET_MODELS["thorough"]
    assert not set(thorough["answers"].values()) & cfg.ZDR_UNAVAILABLE_MODEL_IDS
    assert thorough["answers"]["meta"] == cfg.MUSE_BASE_MODEL
    assert thorough["consensus"] != "Meta-Pro"
    assert cfg._consensus_engine_available(thorough["consensus"])

    assert cfg.DIFFERENCES_JUDGE_MODEL_BY_PROVIDER["gemini"] == cfg.DEFAULT_GEMINI_MODEL
    assert cfg.DIFFERENCES_JUDGE_MODEL_BY_PROVIDER["openai"] == cfg.OPENAI_LUNA_MODEL
    assert cfg.PRO_JUDGE_MODEL_BY_PROVIDER["meta"] == cfg.MUSE_BASE_MODEL
    assert cfg.PRO_JUDGE_MODEL_BY_PROVIDER["openai"] not in cfg.ZDR_UNAVAILABLE_MODEL_IDS
    assert cfg.CHAT_MEMORY_MODEL_BY_PROVIDER["openai"] == defaults["openai"]
    for tier in ("free", "pro"):
        assert not set(cfg.WATCH_MODELS_BY_TIER[tier].values()) & cfg.ZDR_UNAVAILABLE_MODEL_IDS


def test_agent_catalog_and_resolution_skip_dead_ids(loaded_prod_document):
    options = agent_client.agent_model_options()["models"]
    assert not {item["id"] for item in options} & cfg.ZDR_UNAVAILABLE_MODEL_IDS
    for model_id in DEAD:
        # Nicht mehr im Katalog: abgelehnt, bevor ein Lauf beginnt. Der
        # Browser waehlt dann das Default-Chatmodell (agent-chat.js selection()).
        with pytest.raises(ValueError, match="not available"):
            agent_client.resolve_agent_model(model_id)

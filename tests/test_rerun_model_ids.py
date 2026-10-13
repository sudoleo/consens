"""Wiederholte Läufe fahren gespeicherte Modell-IDs so, wie sie heute laufen.

Ein Topic speichert beim Anlegen seinen Modellplan (run_config.provider_models).
Wird ein Modell danach aus den Providerlisten entfernt, ging die gespeicherte
ID unverändert an OpenRouter und fiel dort bei jedem Lauf aus; der Lauf
überlebte nur, solange noch zwei Familien antworteten. Seitdem hebt
cfg.runnable_model_id eine migrierte ID auf ihre aktuelle Form und ersetzt ein
entferntes Modell durch das Standardmodell seiner Familie, ohne das Topic oder
frühere Läufe umzuschreiben. Watches speichern keinen Modellplan.

Keine echten Modell-Calls: MOCK_LLM plus ein Transport, der wie OpenRouter nur
Modelle des aktuellen Katalogs bedient.
"""
import asyncio
import copy
from unittest.mock import patch

import pytest

import app.core.config as cfg
from app.core.entitlements import TIER_FREE, TIER_PRO
from app.services import topic_pipeline, topic_runner, topics, watch_scheduler, watch_service
from app.services.llm import provider_transport
from test_topics_feature import NOW, FakeFirestore, topic_payload


REMOVED_ANTHROPIC = "claude-sonnet-4-5"
REMOVED_GEMINI = "gemini-2.0-flash"
MIGRATED_GROK = cfg.GROK_NO_REASONING_MODEL


def _in_catalog(provider: str, model: str) -> bool:
    return model in cfg.get_ordered_models(provider)


def _claimed_topic(db, provider_models: dict) -> dict:
    """A Topic saved while ``provider_models`` were still selectable."""
    topic = topics.create_topic(topic_payload(evidence=[]), actor_uid="admin", db=db, now=NOW)
    stored = db.documents[("topics", topic["id"])]
    stored["run_config"] = {**stored["run_config"], "provider_models": dict(provider_models)}
    stored.update({"current_run_id": "rerun", "claimed_until": NOW, "last_run_status": "running"})
    return {**copy.deepcopy(stored), "id": topic["id"]}


def _result(**overrides) -> dict:
    return {
        "consensus": "## Current consensus\n\nUnchanged.",
        "agreement_score": 80,
        "changed": False,
        "severity": "minor",
        "change_summary": "No material shift.",
        "opinion_map": {},
        "differences_data": {"agreement": {"score": 80}},
        "sources": [],
        "included_models": [],
        **overrides,
    }


def test_the_fixture_ids_are_really_retired():
    assert REMOVED_ANTHROPIC in cfg.REMOVED_MODEL_IDS
    assert REMOVED_GEMINI in cfg.REMOVED_MODEL_IDS
    assert not _in_catalog("anthropic", REMOVED_ANTHROPIC)
    assert not _in_catalog("gemini", REMOVED_GEMINI)
    assert not _in_catalog("grok", MIGRATED_GROK)
    assert cfg.canonical_model_id(MIGRATED_GROK, "grok") == cfg.GROK_BASE_MODEL


def test_topic_rerun_with_removed_models_still_runs_every_family(monkeypatch):
    """Ohne Normalisierung antwortete hier nur OpenAI, und der Lauf scheiterte."""
    monkeypatch.setenv("MOCK_LLM", "1")
    # In production a MOCK_LLM instance must not touch the shared Firestore;
    # this run writes into the in-memory fake only.
    monkeypatch.setattr(topic_runner, "_guard_mock_mode", lambda: None)
    called = []

    def openrouter(provider, model, *args):
        called.append((provider, model))
        if not _in_catalog(provider, cfg.canonical_model_id(model, provider)):
            raise RuntimeError("404 No endpoints found")
        return provider_transport.query_provider(provider, model, *args)

    pipeline = topic_pipeline.run_consensus_pipeline
    monkeypatch.setattr(
        topic_pipeline, "run_consensus_pipeline",
        lambda **kwargs: pipeline(**kwargs, provider_call=openrouter),
    )
    db = FakeFirestore()
    claimed = _claimed_topic(db, {
        "openai": cfg.DEFAULT_OPENAI_MODEL,
        "anthropic": REMOVED_ANTHROPIC,
        "gemini": REMOVED_GEMINI,
    })
    before = copy.deepcopy(db.documents[("topics", claimed["id"])])

    run = topic_runner.execute_claimed_topic(claimed, actor_uid="admin", db=db, now=NOW)

    assert sorted(provider for provider, _model in called) == ["anthropic", "gemini", "openai"]
    assert all(_in_catalog(provider, model) for provider, model in called)
    assert len(run["models"]) == 3
    after = db.documents[("topics", claimed["id"])]
    assert after["last_run_status"] == "success"
    # The Topic keeps the plan and labels it was saved with.
    assert after["run_config"] == before["run_config"]
    assert after["models"] == before["models"]


def test_topic_rerun_maps_migrated_and_removed_ids_to_todays_models():
    db = FakeFirestore()
    claimed = _claimed_topic(db, {
        "openai": cfg.DEFAULT_OPENAI_MODEL,
        "anthropic": REMOVED_ANTHROPIC,
        "grok": MIGRATED_GROK,
    })
    stored_plan = copy.deepcopy(claimed["run_config"]["provider_models"])
    planned = {}

    def execute(question, previous_consensus, **kwargs):
        planned.update(kwargs["model_overrides"])
        return _result()

    run = topic_runner.execute_claimed_topic(
        claimed, actor_uid="admin", db=db, now=NOW, executor=execute,
    )

    expected = {
        "openai": cfg.DEFAULT_OPENAI_MODEL,
        "anthropic": cfg.FREE_DEFAULT_MODEL_BY_PROVIDER["anthropic"],
        "grok": cfg.GROK_BASE_MODEL,
    }
    assert planned == expected
    # Without included models the run is labelled with what it really ran.
    assert run["models"] == topics.topic_model_labels(expected)
    assert db.documents[("topics", claimed["id"])]["run_config"]["provider_models"] == stored_plan


def test_runnable_model_id_follows_the_watch_tier_defaults(monkeypatch):
    free = {**cfg.WATCH_MODELS_BY_TIER["free"], "anthropic": cfg.ANTHROPIC_PRO_MODEL}
    pro = {**cfg.WATCH_MODELS_BY_TIER["pro"], "anthropic": cfg.ANTHROPIC_PRO_MODEL}
    monkeypatch.setitem(cfg.WATCH_MODELS_BY_TIER, "free", free)
    monkeypatch.setitem(cfg.WATCH_MODELS_BY_TIER, "pro", pro)
    assert cfg.ANTHROPIC_PRO_MODEL in cfg.PREMIUM_MODELS

    # Pro takes the tier's Watch model; Free never gets a Premium substitute.
    assert cfg.runnable_model_id(REMOVED_ANTHROPIC, "anthropic", TIER_PRO) == cfg.ANTHROPIC_PRO_MODEL
    assert (
        cfg.runnable_model_id(REMOVED_ANTHROPIC, "anthropic", TIER_FREE)
        == cfg.FREE_DEFAULT_MODEL_BY_PROVIDER["anthropic"]
    )
    # A model that is still offered stays, Premium or not: nothing is downgraded.
    assert cfg.runnable_model_id(cfg.ANTHROPIC_PRO_MODEL, "anthropic") == cfg.ANTHROPIC_PRO_MODEL
    assert cfg.runnable_model_id(MIGRATED_GROK, "grok") == cfg.GROK_BASE_MODEL


def test_a_family_without_any_model_drops_out_of_the_plan(monkeypatch):
    allowed = cfg._provider_allowed_sets()
    monkeypatch.setattr(cfg, "_provider_allowed_sets", lambda: {**allowed, "anthropic": set()})

    assert cfg.runnable_model_id(REMOVED_ANTHROPIC, "anthropic") == ""
    assert cfg.runnable_provider_models({
        "openai": cfg.DEFAULT_OPENAI_MODEL,
        "anthropic": REMOVED_ANTHROPIC,
        "unknown": "model",
        "gemini": "",
    }) == {"openai": cfg.DEFAULT_OPENAI_MODEL}
    assert cfg.runnable_provider_models(None) == {}


def test_scheduled_watch_rerun_runs_the_tiers_current_models():
    """Watches speichern keinen Modellplan: jeder Lauf nimmt die aktuelle
    Watch-Konfiguration der Stufe, die beim Laden gegen den Katalog geprüft
    wird. Auch Modellfelder in einem Altdokument ändern daran nichts."""
    claimed = {
        "owner_uid": "u1", "share_id": "A" * 16, "interval": "weekly",
        "email_mode": "changes_only",
        "provider_models": {"anthropic": REMOVED_ANTHROPIC, "gemini": REMOVED_GEMINI},
        "models": [REMOVED_ANTHROPIC, REMOVED_GEMINI],
    }
    share = {
        "status": "active", "slug": "q", "question": "Q", "consensus_md": "Old",
        "included_models": ["Anthropic: Claude Sonnet 4.5", "Google Gemini: Gemini 2.0 Flash"],
    }
    planned = {}

    def pipeline(**kwargs):
        planned.update(kwargs["provider_models"])
        raise RuntimeError("stop after the plan")

    with (
        patch.object(watch_service, "acquire_worker_lease", return_value=True),
        patch.object(watch_service, "release_worker_lease"),
        patch.object(watch_service, "list_due_watch_ids", return_value=["w1"]),
        patch.object(watch_scheduler.watch_probe, "list_due_probe_ids", return_value=[]),
        patch.object(watch_service, "claim_watch", return_value=(claimed, "claimed")),
        patch.object(watch_scheduler.security, "get_user_tier", return_value=TIER_FREE),
        patch.object(watch_scheduler.share_snapshots, "get_share", return_value=share),
        patch.object(watch_scheduler.share_snapshots, "list_watch_history", return_value=[]),
        patch.object(watch_scheduler.provider_transport, "provider_available", return_value=True),
        patch.object(watch_scheduler, "run_consensus_pipeline", side_effect=pipeline),
        patch.object(watch_service, "fail_watch_run", return_value=None) as failed,
    ):
        assert asyncio.run(watch_scheduler.run_watch_tick()) == 0

    failed.assert_called_once()
    assert planned == cfg.get_watch_models(TIER_FREE)
    assert all(_in_catalog(provider, model) for provider, model in planned.items())

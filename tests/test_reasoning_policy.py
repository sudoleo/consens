from unittest import mock

import pytest
from fastapi import HTTPException

from app.core import config as cfg
from app.api.routers import admin
from app.services.llm import consensus_engine as engine
from app.services.llm.engines import build_provider_payload


@pytest.fixture(autouse=True)
def restore_policy():
    state = cfg._capture_runtime_config()
    cfg.apply_reasoning_policy()
    yield
    cfg._restore_runtime_config(state)


def model_document():
    return {
        **{key: list(provider.models) for key, provider in cfg.PROVIDERS.items()},
        "premium": list(cfg.PREMIUM_MODELS),
        "consensus": list(cfg.ALLOWED_CONSENSUS_MODELS),
        "preset_models": cfg.get_consensus_preset_models(),
        "defaults": dict(cfg.FREE_DEFAULT_MODEL_BY_PROVIDER),
        "watch_models": {key: dict(value) for key, value in cfg.WATCH_MODELS_BY_TIER.items()},
        "watch_consensus_models": dict(cfg.WATCH_CONSENSUS_MODELS_BY_TIER),
        "deep_think_model": cfg.get_deep_think_consensus_model(),
        "judge_models": cfg.get_judge_models(),
        "judge_models_pro": cfg.get_pro_judge_models(),
        "judge_families": cfg.get_judge_families(),
        "chat_memory_models": cfg.get_chat_memory_models(),
    }


@pytest.mark.parametrize("provider,model,expected", [
    ("mistral", cfg.MISTRAL_PRO_MODEL, {"effort": "none"}),
    ("openai", cfg.OPENAI_PRO_MODEL, {"effort": "low"}),
    ("grok", cfg.GROK_PRO_MODEL, {"effort": "low"}),
    ("meta", cfg.MUSE_PRO_MODEL, {"effort": "low"}),
    ("kimi", cfg.KIMI_PRO_MODEL, {"enabled": True}),
    ("kimi", cfg.KIMI_BASE_MODEL, {"enabled": False}),
    ("grok", cfg.GROK_NO_REASONING_MODEL, {"effort": "none"}),
])
def test_savings_reaches_answers_and_engine_aliases_without_breaking_protection(provider, model, expected):
    cfg.apply_reasoning_policy({"profile": "economy", "models": {}})
    for deep in (False, True):
        assert cfg.effective_model_reasoning(provider, model, deep_think=deep)[0] == expected
    built = build_provider_payload(provider, question="question", model_override=model, deep_search=False)
    assert built["payload"]["reasoning"] == expected
    model_config = cfg.get_model_config(model, provider)
    assert engine._engine_request_config(provider, model_config.api_model, model)["reasoning"] == expected
    if model == cfg.PROVIDERS[provider].pro_model:
        assert engine._engine_request_config(provider, model_config.api_model, f"{cfg.PROVIDERS[provider].label}-Pro")["reasoning"] == expected
    if provider == "kimi":
        assert built["payload"]["provider"]["zdr"] is True
        assert built["payload"]["provider"]["only"] == ["moonshotai"]


def test_disabled_helpers_stay_disabled_and_exception_restores_flow_specific_behavior():
    cfg.apply_reasoning_policy({"profile": "economy", "models": {cfg.MISTRAL_PRO_MODEL: "existing"}})
    assert cfg.effective_model_reasoning("mistral", cfg.MISTRAL_PRO_MODEL)[0] == {"effort": "high"}
    assert cfg.effective_engine_reasoning("mistral", cfg.MISTRAL_PRO_MODEL, effort="none")[0] == {"effort": "none"}
    assert cfg.effective_engine_reasoning("mistral", cfg.MISTRAL_PRO_MODEL)[0] is None
    cfg.apply_reasoning_policy({"profile": "economy", "models": {}})
    assert cfg.effective_engine_reasoning("mistral", cfg.MISTRAL_PRO_MODEL, effort="none")[0] == {"effort": "none"}
    assert cfg.effective_model_reasoning("openai", "unverified-future-model")[0] is None


def test_saved_preview_matches_runtime_for_every_model_and_flow():
    document = model_document()
    document["reasoning_policy"] = {"profile": "economy", "models": {}}
    before = cfg.get_reasoning_policy()
    meta = admin._reasoning_admin_meta(document)
    assert cfg.get_reasoning_policy() == before  # Preview never activates a policy.
    cfg.apply_reasoning_policy(document["reasoning_policy"])
    for row in meta["controls"]:
        provider, model = row["provider"], row["model"]
        preview = row["previews"]["economy"]
        assert preview["answers"] == cfg.effective_model_reasoning(provider, model)[0]
        assert preview["deep"] == cfg.effective_model_reasoning(provider, model, deep_think=True)[0]
        assert preview["synthesis"] == cfg.effective_engine_reasoning(provider, model)[0]
        assert preview["helpers"] == cfg.effective_engine_reasoning(provider, model, effort=cfg.judge_reasoning_effort(provider))[0]


@pytest.mark.parametrize("invalid", [None, [], {}, {"profile": "high", "models": {}},
    {"profile": "economy", "models": {cfg.KIMI_PRO_MODEL: "economy"}},
    {"profile": "economy", "models": {cfg.GROK_PRO_MODEL: {"effort": "high"}}},
])
def test_invalid_admin_policy_fails_before_persistence(invalid):
    payload = {**model_document(), "reasoning_policy": invalid}
    with mock.patch.object(admin, "_require_admin"), mock.patch.object(admin, "_persist_and_activate_models") as persist:
        with pytest.raises(HTTPException) as error:
            admin.update_models(mock.Mock(), payload)
        assert error.value.status_code == 400
        persist.assert_not_called()
    assert cfg.get_reasoning_policy()["profile"] == "existing"


def test_save_roundtrip_and_old_client_preserve_active_policy():
    policy = {"profile": "economy", "models": {cfg.GROK_PRO_MODEL: "existing"}}
    cfg.apply_reasoning_policy(policy)
    for payload in (model_document(), {**model_document(), "reasoning_policy": policy}):
        with mock.patch.object(admin, "_require_admin"), mock.patch.object(admin, "_persist_and_activate_models") as persist:
            assert admin.update_models(mock.Mock(), payload)["status"] == "success"
            assert persist.call_args.args[1]["reasoning_policy"] == policy


def test_reload_and_activation_rollback_include_reasoning_policy():
    db = mock.Mock()
    document = db.collection.return_value.document.return_value
    document.get.return_value.exists = True
    document.get.return_value.to_dict.return_value = {**model_document(), "reasoning_policy": {"profile": "economy", "models": {}}}
    with mock.patch("app.core.security.db_firestore", db):
        with mock.patch.object(cfg, "apply_watch_models", side_effect=RuntimeError("activation failed")):
            with pytest.raises(RuntimeError):
                cfg.load_models_from_db(strict=True, persist_backfill=False)
        assert cfg.get_reasoning_policy()["profile"] == "existing"
        assert cfg.load_models_from_db(strict=True, persist_backfill=False)
        assert cfg.get_reasoning_policy()["profile"] == "economy"


def test_stream_and_json_engine_send_same_capped_policy():
    cfg.apply_reasoning_policy({"profile": "economy", "models": {}})
    response = mock.Mock(status_code=200)
    response.json.return_value = {"choices": [{"message": {"content": "ok"}}]}
    args = ("grok", "x-ai/grok-4.3", "Grok-Pro", {"openrouter": "test-key"})
    kwargs = {"system": "system", "prompt": "prompt", "max_tokens": 100, "effort": "low"}
    with mock.patch.object(engine, "mock_llm_enabled", return_value=False), mock.patch.object(engine, "openrouter_api_key", return_value="test-key"):
        with mock.patch.object(engine.requests, "post", return_value=response) as post:
            assert engine._call_engine_text(*args, **kwargs) == "ok"
            assert post.call_args.kwargs["json"]["reasoning"] == {"effort": "low"}
        with mock.patch("app.services.llm.streaming.stream_chat_completion_text", return_value=iter([])) as stream:
            list(engine._stream_engine_text(*args, **kwargs))
            assert stream.call_args.kwargs["request_config"]["reasoning"] == {"effort": "low"}

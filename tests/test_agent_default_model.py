"""The Agent's default chat model: Claude Sonnet 5.5 since 2026-10-07 (blind
writer test), open to every tier as "Early access" and resolvable from the
built-in catalogue even when OpenRouter's live catalogue is unreachable."""
from app.services.llm import agent_model_metadata as metadata
from app.services.llm.agent_client import AgentModel, agent_model, agent_model_label, agent_model_options, agent_models, resolve_agent_model


def baseline():
    return {key: {**value, "_version": metadata.BASELINE["version"]} for key, value in metadata.BASELINE["models"].items()}


def test_default_is_sonnet_and_works_from_the_builtin_catalogue(monkeypatch):
    monkeypatch.delenv("AGENT_MODEL", raising=False)
    assert AgentModel().model == "anthropic/claude-sonnet-5.5"
    model = agent_model(_metadata=baseline())
    assert model.model == "anthropic/claude-sonnet-5.5" and model.label == "Claude Sonnet 5.5"
    # The landing page's composer mock shows this name.
    assert agent_model_label() == "Claude Sonnet 5.5"


def test_default_is_listed_once_and_resolves_by_registry_or_openrouter_id(monkeypatch):
    monkeypatch.delenv("AGENT_MODEL", raising=False)
    monkeypatch.setattr(metadata, "snapshot", baseline)
    models = [model for model, _ in agent_models()]
    ids = [model.selection_id for model in models]
    assert len(ids) == len(set(ids)) and sum(model.model == "anthropic/claude-sonnet-5.5" for model in models) == 1
    default = models[0]
    assert resolve_agent_model(None).model == "anthropic/claude-sonnet-5.5"
    # Older clients may still send the default by its OpenRouter ID.
    assert resolve_agent_model(default.model).selection_id == default.selection_id


def test_default_is_offered_as_early_access_not_pro(monkeypatch):
    monkeypatch.delenv("AGENT_MODEL", raising=False)
    monkeypatch.setattr(metadata, "snapshot", baseline)
    import app.core.config as cfg
    # In production the registry lists Sonnet 5.5 as premium; the ID is the
    # registry ID there and the OpenRouter ID in this bare test registry.
    default_id = agent_model().selection_id
    monkeypatch.setattr(cfg, "PREMIUM_MODELS", [*cfg.PREMIUM_MODELS, default_id])
    options = agent_model_options()
    default = options["models"][0]
    assert options["default_model_id"] == default["id"] == default_id
    assert default["premium"] is False and default["early_access"] is True
    assert all(item.get("early_access") is not True for item in options["models"][1:])


def test_free_accounts_may_chat_with_the_default_but_not_compare_against_it(monkeypatch):
    from fastapi import HTTPException
    import app.core.config as cfg
    from app.api.routers import agent as agent_router
    monkeypatch.delenv("AGENT_MODEL", raising=False)
    monkeypatch.setattr(metadata, "snapshot", baseline)
    default_id = agent_model().selection_id
    monkeypatch.setattr(cfg, "PREMIUM_MODELS", [*cfg.PREMIUM_MODELS, default_id])
    monkeypatch.setattr(agent_router, "_premium_allowed", lambda uid: False)
    assert agent_router.default_agent_model_id() == default_id
    agent_router.require_model_access("free-user", ["gpt-6-luna"])
    try:
        agent_router.require_model_access("free-user", [default_id])
    except HTTPException as exc:
        assert exc.status_code == 403
    else:
        raise AssertionError("Sonnet as a comparison model must stay Pro")


def test_a_migrated_id_does_not_open_its_premium_successor(monkeypatch):
    # kimi-k3 became Kimi K3.1 Pro (2026-10-25): the old ID is no longer in
    # the premium list itself, but comparison_selection runs its Pro successor.
    import pytest
    from fastapi import HTTPException
    import app.core.config as cfg
    from app.api.routers import agent as agent_router
    monkeypatch.setattr(agent_router, "_premium_allowed", lambda uid: False)
    successor = cfg.canonical_model_id(cfg.KIMI_K3_MODEL, "kimi")
    assert successor != cfg.KIMI_K3_MODEL and successor in cfg.PREMIUM_MODELS
    with pytest.raises(HTTPException) as refused:
        agent_router.require_model_access("free-user", [cfg.KIMI_K3_MODEL])
    assert refused.value.status_code == 403


def test_catalog_maps_migrated_ids_to_listed_successors(monkeypatch):
    # The browser maps a saved, migrated chat model (grok-4.3-no-reasoning)
    # like resolve_agent_model instead of resetting it to the default.
    monkeypatch.delenv("AGENT_MODEL", raising=False)
    monkeypatch.setattr(metadata, "snapshot", baseline)
    import app.core.config as cfg
    options = agent_model_options()
    ids = {item["id"] for item in options["models"]}
    target = options["models"][0]["id"]
    monkeypatch.setitem(cfg.PROVIDER_MODEL_MIGRATIONS, "test-family", {"legacy-id": target, "gone-id": "not-listed"})
    aliases = agent_model_options()["aliases"]
    assert aliases["legacy-id"] == target
    assert "gone-id" not in aliases
    assert all(value in ids and key not in ids for key, value in aliases.items())

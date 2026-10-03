"""The Agent's default chat model: GPT-6 Luna since 2026-10-04 (the cheap base
model), resolvable from the built-in catalogue even when OpenRouter's live
catalogue is unreachable at start."""
from app.services.llm import agent_model_metadata as metadata
from app.services.llm.agent_client import AgentModel, agent_model, agent_model_label, agent_models, resolve_agent_model


def baseline():
    return {key: {**value, "_version": metadata.BASELINE["version"]} for key, value in metadata.BASELINE["models"].items()}


def test_default_is_gpt6_luna_and_works_from_the_builtin_catalogue(monkeypatch):
    monkeypatch.delenv("AGENT_MODEL", raising=False)
    assert AgentModel().model == "openai/gpt-6-luna"
    model = agent_model(_metadata=baseline())
    assert model.model == "openai/gpt-6-luna" and model.label == "GPT-6 Luna"
    # The landing page's composer mock shows this name.
    assert agent_model_label() == "GPT-6 Luna"


def test_default_is_listed_once_and_resolves_by_registry_or_openrouter_id(monkeypatch):
    monkeypatch.delenv("AGENT_MODEL", raising=False)
    monkeypatch.setattr(metadata, "snapshot", baseline)
    models = [model for model, _ in agent_models()]
    ids = [model.selection_id for model in models]
    assert len(ids) == len(set(ids)) and sum(model.model == "openai/gpt-6-luna" for model in models) == 1
    default = models[0]
    assert resolve_agent_model(None).model == "openai/gpt-6-luna"
    # Older clients may still send the default by its OpenRouter ID.
    assert resolve_agent_model(default.model).selection_id == default.selection_id

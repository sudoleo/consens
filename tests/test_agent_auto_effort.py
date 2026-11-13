"""The picker's "Auto" names the level the turn really sends, per model and tier."""
from __future__ import annotations

import pytest

import app.core.config as cfg
from app.services import agent_comparison
from app.services.llm import agent_client
from app.services.llm.agent_client import auto_efforts, resolve_agent_model, running_effort


def options():
    return {model["id"]: model for model in agent_client.agent_model_options()["models"]}


@pytest.mark.parametrize("model_id, pro, free", [
    # Ember reasons at its own default as the chat model; Free sends Medium.
    (cfg.MUSE_BASE_MODEL, "max", "medium"),
    # Pinned by probes: the pin is what Auto sends on every tier.
    (cfg.KIMI_BASE_MODEL, "none", "none"),
    (cfg.KIMI_PRO_MODEL, "low", "low"),
    (cfg.GLM_BASE_MODEL, "low", "low"),
    (cfg.MUSE_GLIMMER_MODEL, "low", "low"),
    # Unpinned: the catalog's default, Medium without Pro where offered.
    ("gpt-6.1-sol", "medium", "medium"),
    ("claude-sonnet-5.5", "high", "medium"),
    # No Medium to fall back on: Free runs the model's own default too.
    ("deepseek-v4.1-flash", "high", "high"),
])
def test_auto_names_the_level_the_request_sends(model_id, pro, free):
    assert options()[model_id]["auto_effort"] == {"pro": pro, "free": free}


def test_auto_effort_is_resolved_from_the_request_the_turn_builds():
    """The same resolution as the route: Pro sends "default", Free its
    free_default_effort; the level is what that model would reason at."""
    for model, metadata in agent_client.agent_models():
        levels = auto_efforts(model, metadata)
        assert levels["pro"] == running_effort(resolve_agent_model(model.selection_id, "default"), metadata)
        free = agent_client.free_default_effort(model.selection_id) or "default"
        assert levels["free"] == running_effort(resolve_agent_model(model.selection_id, free), metadata)


def test_an_unknown_default_is_not_guessed():
    model = agent_client.AgentModel(model="x/plain", request_config={})
    assert running_effort(model, {"reasoning": {"mandatory": True}}) is None
    assert auto_efforts(model, {"reasoning": {"mandatory": True}}) == {"pro": None, "free": None}
    # Without reasoning in the catalog the model does not reason at all.
    assert running_effort(model, {}) == "none"


def test_ember_sends_no_level_as_chat_model_and_low_everywhere_else():
    chat = resolve_agent_model(cfg.MUSE_BASE_MODEL, "default")
    assert "effort" not in chat.request_config["reasoning"]
    # Reviewers and compare_models (metered_model) and the Consensus Engine
    # (MODEL_REQUEST_CONFIG) keep "low": the review after the answer has a
    # 90 s cap.
    reviewer = agent_comparison.comparison_selection({"meta": cfg.MUSE_BASE_MODEL})["meta"]
    assert reviewer.request_config["reasoning"] == {"effort": "low"}
    assert cfg.effective_engine_reasoning("meta", cfg.MUSE_BASE_MODEL)[0] == {"effort": "low"}
    assert cfg.effective_model_reasoning("meta", cfg.MUSE_BASE_MODEL)[0] == {"effort": "low"}
    # Glimmer and Spark keep their pin as chat models too.
    assert resolve_agent_model(cfg.MUSE_GLIMMER_MODEL, "default").request_config["reasoning"]["effort"] == "low"

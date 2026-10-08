"""Auto reasoning without Pro runs as Medium (Max, 2026-10-08)."""
from __future__ import annotations

import pytest

from app.api.routers import agent
from app.services.llm import agent_client
from app.services.llm.agent_client import AgentModel, _free_default_effort
from test_agent_runs import AUTH, UID, api, store  # noqa: F401 (fixtures)

pytestmark = pytest.mark.usefixtures("deepseek_default_agent")


def test_auto_stands_for_medium_only_where_the_model_offers_it_unpinned():
    offers = {"reasoning": {"supported_efforts": ["low", "medium", "high", "max"]}}
    assert _free_default_effort(AgentModel(model="anthropic/claude-sonnet-5.5", request_config={}), offers) == "medium"
    no_medium = {"reasoning": {"supported_efforts": ["low", "high", "max"]}}
    assert _free_default_effort(AgentModel(model="deepseek/x", request_config={}), no_medium) is None
    # A registry entry that pins its reasoning (Kimi off, GLM low) keeps it.
    pinned = AgentModel(model="z-ai/glm", request_config={"reasoning": {"effort": "low"}})
    assert _free_default_effort(pinned, offers) is None
    off = AgentModel(model="moonshotai/kimi", request_config={"reasoning": {"enabled": False}})
    assert _free_default_effort(off, offers) is None
    # A pinned Pro level is not a free default either.
    high = AgentModel(model="x-ai/grok-4.3", request_config={"reasoning": {"effort": "high"}})
    assert _free_default_effort(high, offers) == "medium"
    assert _free_default_effort(AgentModel(model="x/plain", request_config={}), {}) is None


def test_the_catalog_says_what_auto_becomes_without_pro(api):
    client, _store, _ = api
    models = client.get("/agent/models", headers=AUTH).json()["models"]
    assert all("free_default_effort" in model for model in models if model.get("available"))


@pytest.mark.parametrize("pro", [False, True])
def test_auto_without_pro_runs_at_medium(api, monkeypatch, pro):
    client, store, calls = api
    monkeypatch.setattr(agent, "is_user_pro", lambda uid: pro)
    monkeypatch.setattr(agent, "free_default_effort", lambda model_id=None: "medium")
    seen, original = [], agent.resolve_agent_model

    def resolve(model_id=None, reasoning_effort="default"):
        seen.append(reasoning_effort)
        # The test catalog's default model has no Medium; resolve it as Auto.
        return original(model_id, "default")

    monkeypatch.setattr(agent, "resolve_agent_model", resolve)
    chat_id = client.post("/chats", json={"execution_mode": "agent"}, headers=AUTH).json()["chat"]["id"]
    payload = {"chat_id": chat_id, "question": "Hi", "client_request_id": f"auto-{pro}", "bookmark_id": "bm1"}
    assert "event: final" in client.post("/agent", json=payload, headers=AUTH).text
    assert seen == ["default" if pro else "medium"]
    # The request identity keeps what the browser sent: a replay still matches.
    turn = store.list_turns(UID, chat_id)["turns"][0]
    assert store.get_turn(UID, chat_id, turn["id"])["agent_settings"]["selection"]["reasoning_effort"] == "default"
    assert client.post("/agent", json={**payload, "recover_only": True}, headers=AUTH).status_code == 200
    # An explicit level is never changed.
    seen.clear()
    payload = {**payload, "client_request_id": f"low-{pro}", "reasoning_effort": "low"}
    client.post("/agent", json=payload, headers=AUTH)
    assert seen == ["low"]

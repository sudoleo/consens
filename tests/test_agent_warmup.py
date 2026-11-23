"""The Agent's warm-up at server start (app/services/agent_warmup.py)."""
import logging

from app.services import agent_vm, agent_warmup
from app.services.llm import provider_runtime


def test_the_warm_up_builds_a_message_run_without_a_database_or_a_model_call(monkeypatch):
    # Its store has no database (AgentRunStore(None)) and its model no key:
    # a read or a request anywhere in the build would fail it.
    from app.services.agent_delegation import DelegationLoop
    built = []
    init = DelegationLoop.__init__

    def record(self, **kwargs):
        init(self, **kwargs)
        built.append(self)
    monkeypatch.setattr(DelegationLoop, "__init__", record)
    monkeypatch.setattr(provider_runtime, "_provider_http", provider_runtime.ProviderHTTP())
    assert agent_warmup.warm() is True
    loop, = built
    assert loop.store.db is None and loop.api_key == "" and not loop.claimed
    # The tools of a new chat's first message, as the Agent route registers them.
    assert {"compare_models", "read_settings", "search_chats"} <= set(loop.registry.tools)
    # The provider's HTTP client stands: the first request opens a connection, not a client.
    assert provider_runtime._provider_http._session is not None


def test_the_warm_up_builds_the_workspace_tools_but_wakes_no_workspace(monkeypatch):
    monkeypatch.setattr(agent_vm, "configured", lambda: True)
    woken = []
    from app.services.agent_vm_tools import VMTools
    monkeypatch.setattr(VMTools, "prewarm", lambda self, **kwargs: woken.append(kwargs))
    monkeypatch.setattr(agent_vm, "backend", lambda: woken.append("backend"))
    loop = agent_warmup.message_run()
    assert loop.workspace_closed and "open_workspace" in loop.registry.tools
    # Built for the message that starts with the workspace open, registered on none.
    assert {"vm_exec", "browser"} <= loop.workspace_names and "vm_exec" not in loop.registry.tools
    assert woken == []


def test_a_failed_warm_up_is_logged_and_fails_nothing(monkeypatch, caplog):
    def broken():
        raise RuntimeError("catalog unavailable")
    monkeypatch.setattr(agent_warmup, "message_run", broken)
    with caplog.at_level(logging.WARNING):
        assert agent_warmup.warm() is False
    assert "Agent warm-up failed category=RuntimeError" in caplog.text


def test_the_warm_up_runs_on_a_thread_of_its_own(monkeypatch):
    ran = []
    monkeypatch.setattr(agent_warmup, "warm", lambda: ran.append(1))
    thread = agent_warmup.warm_later()
    thread.join(5)
    assert ran == [1] and thread.daemon and thread.name == "agent-warm-up"

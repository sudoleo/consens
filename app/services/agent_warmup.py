"""A server's first Agent message, prepared when the server starts.

What a message's run builds on first use (the modules of its tools, the
tokenizer, every tool's schema, OpenRouter's model catalog, the provider's
HTTP client) made the first message after every server start wait for it
between its turn's creation and its first model request: 0.5-0.9 s in prod
after each deploy and each nightly restart, never for a later message.
warm() does that work once, off any request: it builds what the Agent route
builds for a message (routers/agent.py start_agent_turn), with no account,
no database and no model call, and starts nothing of it.
"""
from concurrent.futures import Future
import logging
import threading
import time

from app.core.observability import safe_exception


def message_run():
    """The run of a new chat's first message as the Agent route builds it,
    never started."""
    from app.services import prompt_config
    from app.services.agent_comparison import AgentPreferences, comparison_selection
    from app.services.agent_delegation import DelegationLoop
    from app.services.agent_files import FileContext
    from app.services.agent_memory import MemorySnapshot
    from app.services.agent_policy import AgentPolicy
    from app.services.agent_provider_limits import provider_cooldowns
    from app.services.agent_runs import AgentRunStore, get_agent_turn_context
    from app.services.agent_tools import configured_model
    from app.services.llm.agent_client import AgentCompletion, resolve_agent_model
    from app.services.llm.provider_runtime import ProviderCancellation

    # The code's own settings, not the saved ones: nothing here reads the database.
    config = {**prompt_config.defaults(), "revision": 0}
    # The process's first look at the model catalog waits for its download.
    model = configured_model(resolve_agent_model(None, "default"))
    store, chat_id, turn_id = AgentRunStore(None), "0" * 32, "0" * 32
    # With the history page handed in, messages reads none itself.
    messages = store.messages("", chat_id, {"id": turn_id, "position": 1, "question": "Hello"}, model=model,
                              config=config, sources=[], context=get_agent_turn_context(model, config),
                              first_page={"snapshots": [], "has_more": False, "next_cursor": None}, summary={})
    catalog = Future()
    catalog.set_result([])
    file_context = FileContext(None, "", chat_id, [])
    file_context.preload(catalog)
    loop = DelegationLoop(
        store=store, uid="", chat_id=chat_id, turn_id=turn_id, model=model, messages=messages, api_key="",
        cancellation=ProviderCancellation(), completion_factory=AgentCompletion,
        policy=AgentPolicy.for_chat(config["delegation"]), file_context=file_context,
        delegation_config=config["delegation"], cooldowns=provider_cooldowns,
        comparison_models=comparison_selection(None), agent_preferences=AgentPreferences(vm="on"),
        memory=MemorySnapshot(), reviewers="always", findings_to_agent=True,
        # Closed: a run that starts with the workspace open wakes its browser
        # (VMTools.prewarm). Its tools are built below instead.
        workspace_closed=True)
    if loop.vm_tools is not None:
        loop._workspace_tool_list()
    return loop


def warm():
    """True when everything was built. A failure is only logged: the first
    message then waits as it did without the warm-up."""
    began = time.monotonic()
    try:
        message_run()
        # What the route itself loads on a message's way to its run.
        from app.services import agent_review_feedback, agent_workspace, memory_review  # noqa: F401
        # The provider's HTTP client and its loop thread start on first use.
        from app.services.llm.provider_runtime import _provider_http
        _provider_http.session()
    except Exception as exc:
        logging.warning("Agent warm-up failed category=%s", safe_exception(exc))
        return False
    logging.info("Agent warmed seconds=%.1f", time.monotonic() - began)
    return True


def warm_later():
    """warm() on a thread of its own: the server takes requests meanwhile."""
    thread = threading.Thread(target=warm, name="agent-warm-up", daemon=True)
    thread.start()
    return thread

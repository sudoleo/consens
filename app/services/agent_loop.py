"""Model/tool orchestration, independent of HTTP and provider transport."""
import threading
from uuid import uuid4

from app.core.openrouter_contract import provider_session_id
from app.services import agent_secrets
from app.services.agent_costs import RunCosts
from app.services.agent_progress import ReasoningProgress
from app.services.agent_policy import AgentPolicy
from app.services.agent_tools import ToolRegistry
from app.services.llm.agent_client import AgentCompletion


class AgentLoop:
    def __init__(self, *, store, uid, chat_id, turn_id, model, messages, api_key,
                 cancellation, policy=None, registry=None, completion_factory=AgentCompletion, mock_answer=None):
        self.store, self.uid, self.chat_id, self.turn_id = store, uid, chat_id, turn_id
        self.model, self.messages, self.api_key = model, list(messages), api_key
        self.cancellation = cancellation
        self.policy = policy or AgentPolicy()
        self.registry = registry or ToolRegistry()
        self.factory, self.mock_answer = completion_factory, mock_answer
        self.completion = AgentCompletion()
        self.completion.step_id = "run"
        self.run_token = uuid4().hex
        # The chat model's steps stay on one endpoint, where their prefix is
        # cached. Comparison answers keep the fastest endpoint: they share
        # no prefix with each other.
        self.provider_session = provider_session_id(uid, chat_id)
        # The chat's last earlier message (system prompt, history, then this
        # message's question): the chat model's steps mark it as a cache point,
        # so the next message reads the history (agent_client.with_cache_points).
        self.history_end = len(self.messages) - 2
        self.claimed = False
        self.costs = RunCosts()
        self.seen_calls = set()
        self.progress = {}
        # Calls of one step and the reviewers send activity from threads of
        # their own: the trace and its step_id change together.
        self.activity_lock = threading.RLock()

    def activity(self, event):
        """One bounded trace, with identities stable across all model steps.
        A key the user saved for the agent is masked (agent_secrets.scrub)."""
        if not event:
            return None
        event = dict(agent_secrets.scrub(self.uid, event))
        step = event.pop("step_id", "run")
        event_id, kind = event.pop("id"), event.pop("kind")
        for key in ("version", "type"):
            event.pop(key, None)
        with self.activity_lock:
            if kind == "reasoning":
                progress = self.progress.setdefault(step, ReasoningProgress())
                compact = progress.update({"kind": kind, "id": event_id, **event})
                if not compact:
                    return None
                event = compact
                event_id = "reasoning-summary"
            self.completion.step_id = step
            return self.completion.event(kind, f"{step}/{event_id}", **event)

    def status(self, step, event_id, **data):
        return self.activity({"step_id": step, "id": event_id, "kind": "status", **data})

    def tool_event(self, step, name, status, **data):
        if "sources" in data:
            data["sources"] = data["sources"][:self.policy.result_sources]
        return self.activity({"step_id": step, "id": "tool", "kind": "tool", "name": name, "status": status, **data})


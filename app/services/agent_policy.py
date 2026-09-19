"""Server-owned capabilities and shared limits, frozen once per Agent turn."""
from dataclasses import asdict, dataclass, replace


@dataclass(frozen=True)
class AgentPolicy:
    version: str = "agent-search-2026-09-15-v2"
    max_calls: int = 3
    max_tools: int = 2
    seconds: int = 180
    max_tokens: int = 4_000_000
    max_cost_nano_usd: int = 1_000_000_000  # simulated $1, not a provider invoice cap
    result_chars: int = 8_000
    result_sources: int = 5
    delegation: bool = False
    max_agents: int = 4
    max_parallel: int = 2
    max_messages: int = 64
    context_chars: int = 48_000
    message_chars: int = 4000
    worker_calls: int = 8
    max_searches: int = 2
    account_budget_only: bool = False

    @classmethod
    def for_chat(cls, config):
        # Chat has one spending limit: the atomic, account-wide token ledger.
        # Keep the bounded policy for legacy callers and the Consensus pipeline.
        return replace(cls.from_config({**config, "enabled": True}),
                       account_budget_only=True, context_chars=120_000,
                       version="agent-account-budget-2026-09-19-v2")

    @classmethod
    def from_config(cls, config):
        return cls(**{key: value for key, value in config.items() if key in cls.__dataclass_fields__},
                   delegation=config["enabled"], version="agent-delegation-2026-09-16-v1")

    def snapshot(self):
        data = asdict(self)
        if self.account_budget_only:
            for key in ("seconds", "max_calls", "max_tools", "max_tokens", "max_cost_nano_usd",
                        "worker_calls", "max_searches", "max_messages", "context_chars"):
                data[key] = None
        return data


def tools_for_model(model):
    # Model admission follows the DB-backed admin lists via agent_models.
    # OpenRouter handles both native search and the Exa fallback, including
    # the provider's internal reasoning/tool-continuation protocol.
    return ("web_search",)


def supports_client_tools(model):
    # Replaying signed/complete reasoning is a separate provider capability.
    # Never strip it and then silently continue a thinking model's tool call.
    reasoning = model.request_config.get("reasoning", {})
    return (model.model == "anthropic/claude-haiku-4.5"
            and not reasoning.get("enabled") and not reasoning.get("max_tokens")
            and reasoning.get("effort", "none") == "none")


def supports_delegation(model):
    from app.services.llm.agent_client import _CATALOG
    capability = _CATALOG["models"].get(model.model, {}).get("delegation", {})
    return (capability.get("protocol") == "openrouter-reasoning-v1"
            and model.reasoning_effort in capability.get("tested_efforts", []))

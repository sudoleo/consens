"""Server-owned capabilities and shared limits, frozen once per Agent turn."""
from dataclasses import asdict, dataclass


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

    def snapshot(self):
        return asdict(self)


def tools_for_model(model):
    # Model admission is owned by agent_models (Daily + configured default).
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

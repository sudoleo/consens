"""Server-owned capabilities and shared limits, frozen once per Agent turn."""
from dataclasses import asdict, dataclass
from app.services.agent_costs import NATIVE_SEARCH_NANO_USD


@dataclass(frozen=True)
class AgentPolicy:
    version: str = "agent-tools-2026-09-15"
    max_calls: int = 3
    max_tools: int = 2
    seconds: int = 180
    max_tokens: int = 800_000
    max_cost_nano_usd: int = 1_000_000_000  # simulated $1, not a provider invoice cap
    result_chars: int = 8_000
    result_sources: int = 5
    native_search_nano_usd: int = NATIVE_SEARCH_NANO_USD

    def snapshot(self):
        return asdict(self)


# Native execution stays inside the chosen model's API request. Extend this
# exact-model allowlist only after checking routing, limits, usage and pricing.
def tools_for_model(model):
    if model.model == "anthropic/claude-haiku-4.5":
        return ("web_search",)
    return ()


def supports_client_tools(model):
    # Replaying signed/complete reasoning is a separate provider capability.
    # Never strip it and then silently continue a thinking model's tool call.
    reasoning = model.request_config.get("reasoning", {})
    return (model.model == "anthropic/claude-haiku-4.5"
            and not reasoning.get("enabled") and not reasoning.get("max_tokens")
            and reasoning.get("effort", "none") == "none")

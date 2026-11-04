"""Server-owned limits of an Agent turn, frozen once per turn."""
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class AgentPolicy:
    version: str = "agent-account-budget-2026-11-04-v5"
    # A run with agent sessions (comparison answers, reviewers): the run's
    # root receipt, its reaper and the browser's session panel look for it.
    delegation: bool = True
    result_chars: int = 8_000
    result_sources: int = 5
    message_chars: int = 4000
    # The daily token ledger is the spending limit. These only stop a turn
    # that loops without progress before it burns the whole allowance.
    turn_comparisons: int = 4
    turn_steps: int = 24
    turn_seconds: int = 900
    turn_identical_calls: int = 2
    # A turn that works in the agent's VM (agent_vm_tools.py) is a long run
    # from its first VM call on: these replace turn_steps and turn_seconds.
    # The ledger and the model's context window end it earlier
    # (DelegationLoop._long_run_limit).
    vm_turn_steps: int = 200
    vm_turn_seconds: int = 7200

    def snapshot(self):
        return asdict(self)


def tools_for_model(model):
    # Model admission follows the DB-backed admin lists via agent_models.
    # OpenRouter handles both native search and the Exa fallback, including
    # the provider's internal reasoning/tool-continuation protocol.
    return ("web_search",)

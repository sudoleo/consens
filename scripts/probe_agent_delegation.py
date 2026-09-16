"""Explicit, bounded live tool-continuation probes; never modifies admission."""
import argparse
from dataclasses import replace
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.agent_costs import RunCosts, aggregate_usage
from app.services.agent_policy import AgentPolicy
from app.services.llm.agent_client import AgentCompletion, agent_models, resolve_agent_model
from app.services.llm.provider_runtime import AnalysisBudget, ProviderCancellation, bind_analysis_budget, bind_provider_cancellation


def probe(model, key):
    model = replace(model, max_output_tokens=2048)
    schema = {"type": "function", "function": {"name": "double", "description": "Multiply an integer by two.",
        "parameters": {"type": "object", "properties": {"value": {"type": "integer"}}, "required": ["value"], "additionalProperties": False}}}
    messages = [{"role": "system", "content": "You are testing tool protocol. Call double with value 21 exactly once. After the tool result, reply with only that numeric result."},
                {"role": "user", "content": "What is double(21)? Use the provided tool."}]
    costs = RunCosts(AgentPolicy(max_calls=2, seconds=90, max_cost_nano_usd=100_000_000))
    started = time.monotonic()
    result = {"model_id": model.selection_id, "model": model.model, "effort": model.reasoning_effort, "passed": False}
    try:
        with bind_analysis_budget(AnalysisBudget(seconds=90, max_calls=2)), bind_provider_cancellation(ProviderCancellation()):
            for index in range(2):
                value = AgentCompletion()
                reservation = costs.reserve(model, messages, [schema])
                try:
                    list(value.stream(model=model, messages=messages, api_key=key, tools=[schema], allow_tool_calls=True))
                finally:
                    costs.reconcile(reservation, value.usage)
                if index == 0:
                    if len(value.tool_calls) != 1 or value.tool_calls[0]["function"]["name"] != "double":
                        raise ValueError("Expected tool call missing")
                    call = value.tool_calls[0]
                    if json.loads(call["function"]["arguments"]) != {"value": 21}:
                        raise ValueError("Wrong tool arguments")
                    messages.extend([value.assistant_message(), {"role": "tool", "tool_call_id": call["id"], "content": '{"result":42}'}])
                    result["reasoning_blocks_replayed"] = len(value._reasoning_parts)
                else:
                    if value.tool_calls or value.text.strip().strip(". ") != "42":
                        raise ValueError("Continuation did not return the tool result")
                    result["passed"] = True
    except Exception as exc:
        # Error category only: never record credentials or raw provider bodies.
        result["error"] = type(exc).__name__
    result.update(usage=costs.total(), elapsed_ms=int((time.monotonic() - started) * 1000))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", required=True, help="Authorize at most two paid requests per selected model")
    parser.add_argument("--model", action="append")
    parser.add_argument("--effort", default="default")
    parser.add_argument("--output", default="artifacts/agent-delegation-protocol.json")
    args = parser.parse_args()
    from dotenv import load_dotenv
    load_dotenv()
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        parser.error("OPENROUTER_API_KEY is required")
    ids = args.model or [m.selection_id for m, _ in agent_models()]
    results = []
    for identity in ids:
        result = probe(resolve_agent_model(identity, args.effort), key)
        results.append(result)
        print(json.dumps(result), flush=True)
        report = {"date": datetime.now(timezone.utc).isoformat(), "kind": "live_protocol_probe",
                  "quality_gate": "Not a task-quality or savings evaluation", "results": results}
        Path(args.output).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

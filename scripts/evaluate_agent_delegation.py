"""Paired, reproducible quality/total-cost comparison. Live mode is opt-in.

No database writes. All provider steps (including failures and rework) are
recorded by the same production loops. Admission never follows price alone.
"""
import argparse
from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import threading
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.agent_costs import aggregate_usage
from app.services.agent_delegation import DelegationLoop
from app.services.agent_delegation_config import defaults
from app.services.agent_loop import AgentLoop
from app.services.agent_policy import AgentPolicy
from app.services.llm.agent_client import resolve_agent_model
from app.services.llm.provider_runtime import ProviderCancellation
from app.services.prompt_defaults import AGENT_SYSTEM_PROMPT


def task_set():
    tables = {name: [{"id": i, "amount": (i * multiplier) % 97 + 1, "status": "cancelled" if i % 7 == 0 else "paid"}
                     for i in range(1, 31)] for name, multiplier in (("north", 13), ("south", 19))}
    totals = {name: sum(row["amount"] for row in rows if row["status"] == "paid") for name, rows in tables.items()}
    return [
        {"id": "simple_arithmetic", "category": "direct", "question": 'What is 17 * 23? Return JSON {"result": integer}.', "expected": {"result": 391}},
        {"id": "extraction", "category": "extraction", "question": 'Extract the facts below, preserving dates literally. Return only JSON with keys project (name only, without the word Project), owner (full name), start (date string), budget (integer amount without currency), archived (boolean). Memo: Project Alder; owner Nia Hart; start 2031-04-09; budget EUR 72000; not archived. The earlier draft (Project Birch, owner Sol Beck, budget EUR 69000) is superseded.',
         "expected": {"project": "Alder", "owner": "Nia Hart", "start": "2031-04-09", "budget": 72000, "archived": False}},
        {"id": "parallel_ledgers", "category": "calculation", "question": 'Independently audit both ledgers. If agent tools are available, assign each ledger to a separate worker and verify their totals yourself; otherwise audit both yourself. Exclude cancelled rows. Return only JSON with the paid amount totals under north and south.\n' + json.dumps(tables), "expected": totals},
        {"id": "dependencies", "category": "planning", "question": 'Unlimited parallel resources. Tasks: A takes 3h; B takes 5h; both start at time 0. C takes 4h after A. D takes 2h after A and B. E takes 1h after C and D. Return only JSON with earliest finish times A,B,C,D,E and total (integers, hours).',
         "expected": {"A": 3, "B": 5, "C": 7, "D": 7, "E": 8, "total": 8}},
        {"id": "rule_cases", "category": "reasoning", "question": 'Rule: allow access exactly when (admin OR paid) AND NOT suspended. Missing flags count as false. Cases: a={admin:true, suspended:true}; b={paid:true}; c={}; d={admin:true, paid:false}; e={paid:true, suspended:true}; f={admin:false,paid:false,suspended:false}. Return only JSON mapping each case a..f to boolean.',
         "expected": {"a": False, "b": True, "c": False, "d": True, "e": False, "f": False}},
        {"id": "code_analysis", "category": "code", "question": 'Without executing tools, inspect this Python function: def f(xs):\n s=0\n for i,x in enumerate(xs):\n  if i%2==0: s+=x\n  else: s-=x\n return s\nReturn only JSON with results for a=f([]), b=f([2,7,4,1]), c=f([-3,2,-5]), d=f([10]). Also include empty_safe:boolean for whether f([]) succeeds.',
         "expected": {"a": 0, "b": -2, "c": -10, "d": 10, "empty_safe": True}},
    ]


class EvaluationStore:
    """In-memory receipt sink, deliberately isolated from user persistence."""
    def __init__(self):
        self.lock = threading.RLock()
        self.receipts, self.agents, self.events = {}, {}, []

    def claim(self, *args, step="completion:0", **kwargs):
        with self.lock:
            if step in self.receipts:
                return False
            self.receipts[step] = {"step": step, "status": "running", "model": args[3].model}
            return True

    def settle(self, *args, completion, status, step="completion:0", **kwargs):
        with self.lock:
            self.receipts[step].update(status=status, usage=completion.usage, generation_id=completion.generation_id)

    def finish_run(self, *args, **kwargs):
        pass

    def release_unclaimed(self, *args):
        pass

    def check_delegation(self, *args):
        pass

    def publish_agent(self, *args, agent_id, patch=None, message=None, **kwargs):
        with self.lock:
            seq = len(self.events) + 1
            self.agents[agent_id] = {**self.agents.get(agent_id, {}), **(patch or {}), "id": agent_id, "seq": seq}
            event = {"type": "delegation", "version": 1, "id": str(seq), "seq": seq, "agent": dict(self.agents[agent_id])}
            self.events.append({**event, **({"message": message} if message else {})})
            return event


def parsed(text):
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    try:
        return json.loads(text)
    except ValueError:
        return None


def gate(rows):
    """Fail closed on missing pairs, unknown costs, failed checks or regression."""
    baseline = {(r["task"], r["repeat"]): r for r in rows if r["mode"] == "direct"}
    candidates = [r for r in rows if r["mode"] == "delegation"]
    paired = (bool(baseline) and len(candidates) == len(baseline)
              and len(rows) == 2 * len(baseline)
              and len({(r["task"], r["repeat"]) for r in candidates}) == len(candidates)
              and all((r["task"], r["repeat"]) in baseline for r in candidates))
    quality = paired and all(r["passed"] and baseline[(r["task"], r["repeat"])]["passed"] for r in candidates)
    complete = paired and all(r.get("usage") and r["usage"].get("cost_complete", r["usage"].get("complete"))
                              and r["usage"].get("cost_source") == "provider" for r in rows)
    direct_cost = sum((r.get("usage") or {}).get("estimated_cost_nano_usd") or 0 for r in baseline.values())
    delegated_cost = sum((r.get("usage") or {}).get("estimated_cost_nano_usd") or 0 for r in candidates)
    # Three paired repetitions, >=5% aggregate savings and no cost regression
    # in any repeat prevent promotion from a single lucky/cache-warm sample.
    repeats = sorted({r["repeat"] for r in candidates})
    required = {task["id"] for task in task_set()}
    coverage = all({r["task"] for r in candidates if r["repeat"] == i} == required for i in repeats)
    per_repeat = all(sum((r.get("usage") or {}).get("estimated_cost_nano_usd") or 0 for r in candidates if r["repeat"] == i)
        < sum((r.get("usage") or {}).get("estimated_cost_nano_usd") or 0 for r in baseline.values() if r["repeat"] == i) for i in repeats)
    exercised = any(r.get("agents", 0) >= 2 for r in candidates)
    approved = quality and complete and exercised and coverage and len(repeats) >= 3 and delegated_cost <= direct_cost * .95 and per_repeat
    return {"approved": approved, "quality_passed": quality, "costs_complete": complete,
            "direct_cost_nano_usd": direct_cost, "delegated_cost_nano_usd": delegated_cost,
            "savings_fraction": 1 - delegated_cost / direct_cost if direct_cost and complete else None,
            "paired_repetitions": len(repeats), "minimum_repetitions": 3, "delegation_exercised": exercised, "full_dataset": coverage,
            "decision": "Prefer evaluated worker candidate" if approved else "Keep model choice unrestricted; no proven saving at equal quality"}


def run_task(task, mode, orchestrator, worker, key, repeat):
    store = EvaluationStore()
    config = defaults()
    config.update(enabled=True, max_searches=0, seconds=120, max_calls=24)
    common = dict(store=store, uid="evaluation", chat_id="evaluation", turn_id=task["id"],
                  model=resolve_agent_model(orchestrator), messages=[{"role": "system", "content": AGENT_SYSTEM_PROMPT},
                  {"role": "user", "content": task["question"]}], api_key=key, cancellation=ProviderCancellation())
    if mode == "delegation":
        loop = DelegationLoop(**common, policy=AgentPolicy.from_config(config), delegation_config=config,
                              worker_model_ids=[worker] if worker else None)
    else:
        loop = AgentLoop(**common, policy=AgentPolicy(max_tools=0, seconds=120))
    started = time.monotonic()
    error = detail = None
    try:
        for _ in loop.run():
            pass
    except (Exception, KeyboardInterrupt) as exc:
        error = type(exc).__name__
        detail = str(exc) if isinstance(exc, ValueError) else None
    result = loop.completion.text
    usage = aggregate_usage([r.get("usage") for r in store.receipts.values()])
    return {"task": task["id"], "category": task["category"], "repeat": repeat, "mode": mode,
            "passed": error is None and json.dumps(parsed(result), sort_keys=True) == json.dumps(task["expected"], sort_keys=True), "response": result,
            "error": error, "error_detail": detail, "usage": usage, "elapsed_ms": int((time.monotonic() - started) * 1000),
            "agents": len(store.agents), "steps": list(store.receipts.values()), "events": store.events}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", required=True, action="store_true")
    parser.add_argument("--orchestrator", default="deepseek/deepseek-v4.1-flash")
    parser.add_argument("--worker", default="mistral-small-latest")
    parser.add_argument("--repeats", type=int, choices=range(1, 6), default=3)
    parser.add_argument("--task", action="append")
    parser.add_argument("--output", default="artifacts/agent-delegation-evaluation.json")
    args = parser.parse_args()
    from dotenv import load_dotenv
    load_dotenv()
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        parser.error("OPENROUTER_API_KEY is required")
    tasks = [t for t in task_set() if not args.task or t["id"] in args.task]
    if not tasks:
        parser.error("No selected tasks")
    digest = hashlib.sha256(json.dumps(tasks, sort_keys=True).encode()).hexdigest()
    rows = []
    report = {"schema_version": 1, "kind": "live_paired_evaluation", "date": datetime.now(timezone.utc).isoformat(),
              "dataset_sha256": digest, "tasks": tasks, "orchestrator": args.orchestrator, "worker": args.worker,
              "scope": "Six synthetic objective tasks; no subjective or current-web claims. No universal quality guarantee.", "runs": rows}
    for repeat in range(args.repeats):
        for task in tasks:
            # Alternate order to reduce systematic cache/time effects.
            for mode in (["direct", "delegation"] if repeat % 2 == 0 else ["delegation", "direct"]):
                row = run_task(task, mode, args.orchestrator, args.worker, key, repeat)
                rows.append(row)
                report["gate"] = gate(rows)
                Path(args.output).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
                print(json.dumps({k: row[k] for k in ("task", "repeat", "mode", "passed", "error", "usage", "elapsed_ms", "agents")}), flush=True)
                if row["error"] == "KeyboardInterrupt":
                    return
    print(json.dumps(report["gate"]), flush=True)


if __name__ == "__main__":
    main()

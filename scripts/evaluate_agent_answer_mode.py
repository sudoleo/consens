"""Live A/B: where the Agent writes its answer (agent_answer_mode).

separate: the agent ends its steering with ``answer`` and a fresh answer step
of the same model writes the answer (the default until this comparison).
merged:   the agent writes the answer itself as its last step
          (AGENT_MERGED_ANSWER=1, docs/agent-mode.md "Antwort im selben Aufruf").

Per question one full turn in each mode: same chat model, the same six
comparison families, real judges, on an in-memory store (nothing is written to
Firestore). Paid: every turn asks the comparison models and the judges, so a
question costs about twice a normal message. The comparison answers differ
between the two runs; read the quality numbers as a trend, not a verdict.

    venv/Scripts/python.exe scripts/evaluate_agent_answer_mode.py --live --model gpt-6-luna
    venv/Scripts/python.exe scripts/evaluate_agent_answer_mode.py --live --model claude-opus-5.5 --only 0 --only 3

Per turn one JSON line (answer text included), then a summary per mode.
--pairwise MODEL lets a blind judge pick the better answer per question.
--out FILE also writes everything as JSON lines.

Measured per turn:
- seconds: whole turn; to the first visible answer text; from the last
  comparison to the finished answer (decide + write, the part that changes)
- chat_cost_usd / chat_input_tokens: the chat model's own steps (completion:N
  receipts); after_comparison_cost_usd: those after the last comparison
- total_cost_usd: everything, comparison models and judges included
- steps: chat model steps; retractions: text taken back from view
- leaks: tool or protocol words in the answer
- agreement / major_contradictions: the judges' verdict per comparison
"""
import argparse
import json
import os
from pathlib import Path
import random
import re
import statistics
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

PASTED = ("Stimmt das? ChatGPT hat mir geschrieben: \"Wärmepumpen funktionieren in Altbauten nur mit "
          "Fußbodenheizung. Der Staat übernimmt bis zu 70 Prozent der Kosten. Unter 55 Grad Vorlauftemperatur "
          "arbeiten sie effizient.\"")

# (kind, question). compare: a fact, advice or analysis the agent should
# compare; direct: no outside fact at stake; check: a pasted text to check.
CASES = [
    ("compare", "Wie hoch ist der aktuelle Leitzins der EZB und wann ist die nächste Zinssitzung?"),
    ("compare", "Soll ich als Anfänger eher ETFs oder Einzelaktien kaufen?"),
    ("compare", "Wie viel Protein brauche ich als Vegetarier bei dreimal Krafttraining pro Woche, 80 kg?"),
    ("compare", "Lohnt sich eine Wärmepumpe in einem unsanierten Einfamilienhaus von 1965?"),
    ("compare", "PostgreSQL oder MySQL für ein kleines SaaS-Projekt mit einem Entwickler: was spricht wofür?"),
    ("compare", "Wie hoch ist der Eiffelturm aktuell genau? Ich lese überall andere Zahlen."),
    ("compare", "Welche Laufschuhe eignen sich für einen ersten Marathon bei 85 kg Körpergewicht?"),
    ("compare", "Was hat sich 2026 bei der Grundsteuer in Deutschland geändert?"),
    ("direct", "Übersetze ins Englische: Die Sitzung wurde auf Dienstag verschoben, weil zwei Teilnehmer krank sind."),
    ("check", PASTED),
]

# Tool and protocol words that do not belong in an answer.
LEAKS = re.compile(r"\b(compare_models|check_text|read_source|prepare_watch|update_memory|status_update|"
                   r"judge_answer|tool calls?|tool results?|comparison results?|untrusted|Model [A-F])\b", re.I)
STEP = re.compile(r"^completion:(\d+)/started$")
TOOL_STEP = re.compile(r"^completion:(\d+):")

PAIRWISE_PROMPT = """You compare two answers to the same user question for a blind quality test.
Judge which answer serves the user better: correct and current facts, faithfulness to what is known,
clear recommendation where one is possible, useful structure, no filler, no process talk about tools
or models. Length alone is no merit. Reply with JSON only:
{"better": "1" | "2" | "tie", "reason": "<one sentence>"}"""


def usd(nanos):
    return round((nanos or 0) / 1e9, 5)


def receipts(store, uid, chat_id, turn_id):
    """Usage of the chat model's own steps (completion:N), in order."""
    steps, index = [], 0
    while True:
        snapshot = store.receipt_ref(uid, chat_id, turn_id, f"completion:{index}").get()
        if not snapshot.exists:
            return steps
        usage = (snapshot.to_dict() or {}).get("usage") or {}
        steps.append({"step": index, "cost_nano": usage.get("estimated_cost_nano_usd") or 0,
                      "input_tokens": usage.get("input_tokens") or 0,
                      "cached_input_tokens": usage.get("cached_input_tokens") or 0,
                      "output_tokens": usage.get("output_tokens") or 0})
        index += 1


def run_turn(case, question, *, merged, model, families, config, key, check_sources):
    from app.services.agent_comparison import comparison_selection
    from app.services.agent_delegation import DelegationLoop
    from app.services.agent_policy import AgentPolicy
    from app.services.agent_runs import get_agent_turn_context, with_app_context
    from app.services.llm.agent_client import AgentCompletion
    from app.services.llm.provider_runtime import ProviderCancellation
    from test_agent_runs import AgentRunStore, Database, UID, pending

    store = AgentRunStore(Database())
    chat, turn = pending(store, question=question)
    delegation_config = {**config["delegation"], "enabled": False}
    messages = [{"role": "system", "content": config["prompts"]["agent"]},
                {"role": "user", "content": with_app_context(question, get_agent_turn_context(model, config))}]
    loop = DelegationLoop(store=store, uid=UID, chat_id=chat, turn_id=turn["id"], model=model, messages=messages,
                          api_key=key, cancellation=ProviderCancellation(),
                          policy=AgentPolicy.for_chat(delegation_config), delegation_config=delegation_config,
                          completion_factory=AgentCompletion, comparison_models=comparison_selection(families),
                          check_sources=check_sources, merged_answer=merged)
    started = time.monotonic()
    events, error = [], None
    try:
        for event in loop.run():
            events.append((time.monotonic() - started, event))
    except Exception as exc:  # A failed turn is a result; provider bodies are never printed.
        error = f"{type(exc).__name__}: {str(exc)[:160]}"
    total = time.monotonic() - started
    saved = store.get_turn(UID, chat, turn["id"]) or {}
    text = saved.get("assistant_response") or saved.get("consensus") or ""

    first_delta = next((t for t, e in events if e.get("type") == "delta"), None)
    judge = next((t for t, e in events if e.get("kind") == "tool" and e.get("name") == "judge_answer"), None)
    compares = [(t, e) for t, e in events if e.get("kind") == "tool" and e.get("name") in {"compare_models", "check_text"}
                and e.get("status") == "succeeded"]
    answer_done = judge if judge is not None else (total if text else None)
    last_compare = compares[-1][0] if compares else None
    compare_step = None
    if compares:
        match = TOOL_STEP.match(str(compares[-1][1].get("id") or ""))
        compare_step = int(match.group(1)) if match else None
    steps = receipts(store, UID, chat, turn["id"])
    after = [s for s in steps if compare_step is not None and s["step"] > compare_step]
    review = saved.get("agent_review") or {}
    checks = [((c.get("differences_data") or {}).get("agreement") or {}) for c in review.get("checks") or []]
    usage = loop.completion.usage or {}
    return {
        "case": case, "mode": "merged" if merged else "separate", "model": model.selection_id,
        "question": question[:120], "status": saved.get("status"), "error": error,
        "failure": (saved.get("agent_failure") or {}).get("code"),
        "seconds": round(total, 1),
        "seconds_to_answer_text": None if first_delta is None else round(first_delta, 1),
        "seconds_after_comparison": (round(answer_done - last_compare, 1)
                                     if answer_done is not None and last_compare is not None else None),
        "steps": len(steps), "comparisons": len(review.get("comparisons") or []),
        "chat_cost_usd": usd(sum(s["cost_nano"] for s in steps)),
        "after_comparison_cost_usd": usd(sum(s["cost_nano"] for s in after)) if compare_step is not None else None,
        "chat_input_tokens": sum(s["input_tokens"] for s in steps),
        "chat_cached_input_tokens": sum(s["cached_input_tokens"] for s in steps),
        "chat_output_tokens": sum(s["output_tokens"] for s in steps),
        "total_cost_usd": usd(usage.get("estimated_cost_nano_usd")),
        "retractions": sum(1 for _, e in events if e.get("kind") == "status" and e.get("clear_response")),
        "leaks": sorted({m.group(0) for m in LEAKS.finditer(text)}),
        "review": review.get("status"),
        "agreement": [c.get("score") for c in checks],
        "major_contradictions": sum(c.get("major_contradictions") or 0 for c in checks),
        "answer": text,
    }


def pairwise(question, first, second, *, judge_model, key, seed):
    """Blind pick between two answers, in random order. Returns the mode or "tie"."""
    from app.services.llm.agent_client import AgentCompletion
    from app.services.llm.provider_runtime import (AnalysisBudget, ProviderCancellation, bind_analysis_budget,
                                                   bind_provider_cancellation)
    pair = [first, second]
    random.Random(seed).shuffle(pair)
    prompt = (f"Question:\n{question}\n\nAnswer 1:\n{pair[0]['answer']}\n\nAnswer 2:\n{pair[1]['answer']}")
    value = AgentCompletion()
    with bind_analysis_budget(AnalysisBudget(seconds=180, max_calls=1)), \
            bind_provider_cancellation(ProviderCancellation()):
        list(value.stream(model=judge_model, messages=[{"role": "system", "content": PAIRWISE_PROMPT},
                                                       {"role": "user", "content": prompt}], api_key=key))
    match = re.search(r"\{.*\}", value.text, re.S)
    verdict = json.loads(match.group(0)) if match else {}
    better = str(verdict.get("better", "")).strip()
    winner = pair[0]["mode"] if better == "1" else pair[1]["mode"] if better == "2" else "tie"
    return {"winner": winner, "reason": str(verdict.get("reason") or "")[:300],
            "cost_usd": usd((value.usage or {}).get("estimated_cost_nano_usd"))}


def summary(rows, mode):
    mine = [r for r in rows if r["mode"] == mode]

    def mean(key):
        values = [r[key] for r in mine if isinstance(r.get(key), (int, float))]
        return round(statistics.mean(values), 3) if values else None
    scores = [s for r in mine for s in r["agreement"] if isinstance(s, (int, float))]
    return {"mode": mode, "turns": len(mine), "completed": sum(r["status"] == "completed" for r in mine),
            "seconds": mean("seconds"), "seconds_to_answer_text": mean("seconds_to_answer_text"),
            "seconds_after_comparison": mean("seconds_after_comparison"), "steps": mean("steps"),
            "chat_cost_usd": mean("chat_cost_usd"), "after_comparison_cost_usd": mean("after_comparison_cost_usd"),
            "chat_input_tokens": mean("chat_input_tokens"), "total_cost_usd": mean("total_cost_usd"),
            "retractions": sum(r["retractions"] for r in mine), "turns_with_leaks": sum(bool(r["leaks"]) for r in mine),
            "agreement": round(statistics.mean(scores), 1) if scores else None,
            "major_contradictions": sum(r["major_contradictions"] for r in mine)}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--live", action="store_true", required=True, help="Authorize the paid turns")
    parser.add_argument("--model", default="gpt-6-luna", help="Chat model (selection id)")
    parser.add_argument("--effort", default="default", help="Reasoning effort of the chat model")
    parser.add_argument("--only", type=int, action="append", help="Case index (repeatable)")
    parser.add_argument("--modes", default="separate,merged", help="Comma-separated: separate, merged")
    parser.add_argument("--check-sources", action="store_true", help="Also run the source check of contradictions")
    parser.add_argument("--pairwise", help="Model id of a blind judge that picks the better answer per question")
    parser.add_argument("--out", help="Write every line to this JSON lines file as well")
    parser.add_argument("--tier", default="pro", choices=("free", "plus", "pro"),
                        help="Token allowance of the test account (default pro)")
    args = parser.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
    os.chdir(ROOT)
    from app.services import agent_quota
    # The test account exists only in memory; looked up in Firestore it is
    # Free, and the Free allowance queues the parallel comparison answers and
    # judges behind each other and shrinks searches (2026-10-14: 518 s for a
    # turn that takes 1-2 min on a Pro account).
    agent_quota._stored_tier = lambda uid: args.tier
    agent_quota._admin_role = lambda uid: False
    from app.core import config as cfg
    cfg.load_models_from_db(persist_backfill=False)
    from app.services import prompt_config
    from app.services.llm.agent_client import resolve_agent_model

    config = prompt_config.get_config()
    model = resolve_agent_model(args.model, args.effort)
    judge_model = resolve_agent_model(args.pairwise) if args.pairwise else None
    key = os.environ["OPENROUTER_API_KEY"]
    families = {p: cfg.FREE_DEFAULT_MODEL_BY_PROVIDER[p]
                for p in ("openai", "anthropic", "gemini", "deepseek", "grok", "glm")
                if p in cfg.FREE_DEFAULT_MODEL_BY_PROVIDER}
    modes = [mode.strip() for mode in args.modes.split(",") if mode.strip() in {"separate", "merged"}]
    out = open(args.out, "a", encoding="utf-8") if args.out else None

    def emit(line):
        text = json.dumps(line, ensure_ascii=False)
        # The file first: a console that cannot print a character ("→" on a
        # Windows code page) must not lose a paid turn's line.
        if out:
            out.write(text + "\n")
            out.flush()
        print(text, flush=True)

    rows, wins = [], {"separate": 0, "merged": 0, "tie": 0}
    for index, (kind, question) in enumerate(CASES):
        if args.only and index not in args.only:
            continue
        pair = {}
        # Alternate the order so neither mode always runs first (provider caches).
        for mode in (modes if index % 2 == 0 else list(reversed(modes))):
            row = run_turn(index, question, merged=mode == "merged", model=model, families=families,
                           config=config, key=key, check_sources=args.check_sources)
            row["kind"] = kind
            rows.append(row)
            pair[mode] = row
            emit(row)
        if judge_model and len(pair) == 2 and all(r["status"] == "completed" and r["answer"] for r in pair.values()):
            verdict = pairwise(question, pair["separate"], pair["merged"], judge_model=judge_model, key=key, seed=index)
            wins[verdict["winner"]] += 1
            emit({"case": index, "pairwise": verdict})
    for mode in modes:
        emit({"summary": summary(rows, mode)})
    if judge_model:
        emit({"pairwise_wins": wins, "judge": judge_model.selection_id})
    if out:
        out.close()


if __name__ == "__main__":
    main()

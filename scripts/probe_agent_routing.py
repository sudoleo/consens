"""Live probe: which tool does the orchestrator choose in its first step?

One paid routing step per case (no comparison, no answer step), with the real
steering prompt, the turn's tools and the web search tool, on an in-memory
store: nothing is written to Firestore. Checks the decision rule "compare or
answer directly" (docs/agent-mode.md) against messages from real tests.

    venv/Scripts/python.exe scripts/probe_agent_routing.py --live --model gpt-6-luna

--memory runs the same cases with memory switched on (the required `memory`
field on answer, update_memory) plus a memory request, as for an opted-in user.
"""
import argparse
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

LIVE = "https://www.tri247.com/triathlon-news/elite/ironman-world-championship-kona-2026-live-updates"
EARLIER = [
    {"role": "user", "content": "Wer hat die Ironman-WM 2026 in Kona gewonnen?"},
    {"role": "assistant", "content": "In Kona gewannen 2026 **Vincent Luis** das Männerrennen (7:47:27) und **Taylor "
                                     f"Knibb** das Frauenrennen (8:36:29). ([Livebericht]({LIVE}))"},
]
WATCHED = [
    {"role": "user", "content": "Sag mir Bescheid, wenn die EZB die Zinsen das nächste Mal senkt."},
    {"role": "assistant", "content": "Die EZB hat zuletzt am 10. September 2026 erhöht; die nächste Sitzung ist am "
                                     "29. Oktober. Die Beobachtung ist vorbereitet: starte sie über die Karte unter "
                                     "dieser Antwort."},
]
PASTED = ("Stimmt das? ChatGPT hat mir geschrieben: \"Wärmepumpen funktionieren in Altbauten nur mit "
          "Fußbodenheizung. Der Staat übernimmt bis zu 70 Prozent der Kosten. Unter 55 Grad Vorlauftemperatur "
          "arbeiten sie effizient.\"")

# (expected decision, history, message). compare: compare_models; check:
# check_text; direct: no comparison (answer, plain text, read_source or
# prepare_watch without compare_models); read/watch: that tool, no comparison.
CASES = [
    ("compare", [], "Wer hat die Ironman-WM 2026 in Kona gewonnen?"),
    ("compare", [], "Wie hoch ist der Eiffelturm aktuell genau? Ich lese überall andere Zahlen."),
    ("compare", [], "Soll ich als Anfänger eher ETFs oder Einzelaktien kaufen?"),
    ("compare", EARLIER, "Vergleiche das bitte nochmal mit den anderen Modellen."),
    ("watch", [], "Sag mir Bescheid, wenn die EZB die Zinsen das nächste Mal senkt."),
    ("watch", WATCHED, "kannst du den watch bitte für mich starten"),
    ("read", EARLIER, "Lies die erste Quelle aus deiner Antwort nach und sag mir die genaue Siegerzeit."),
    ("direct", EARLIER, "Kannst du die Quellen lesen, die dir die Modelle vom Vergleich gegeben haben?"),
    ("direct", EARLIER, "Übersetze deine letzte Antwort ins Englische."),
    ("direct", [], "Danke dir!"),
    ("direct", [], "Was kann consens.io eigentlich?"),
    ("check", [], PASTED),
]
# Only with --memory: a memory request is answered with update_memory and text.
MEMORY_CASES = [
    ("direct", [], "Merk dir bitte, dass ich Vegetarier bin."),
]


def decision(names):
    names = set(names)
    if "check_text" in names:
        return "check"
    if "compare_models" in names:
        return "compare" if "prepare_watch" not in names else "watch+compare"
    if "prepare_watch" in names:
        return "watch"
    if "read_source" in names:
        return "read"
    return "direct"


def passes(expected, got):
    if expected == "watch":
        return got in {"watch", "watch+compare"}
    if expected == "direct":
        return got in {"direct", "read"}
    return got == expected


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", required=True, help="Authorize one paid step per case")
    parser.add_argument("--model", default="gpt-6-luna")
    parser.add_argument("--only", type=int, action="append", help="Case index (repeatable)")
    parser.add_argument("--memory", action="store_true", help="Memory on and writable (opted-in user)")
    args = parser.parse_args()
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
    os.chdir(ROOT)
    from app.core import config as cfg
    cfg.load_models_from_db(persist_backfill=False)
    from app.services import prompt_config
    from app.services.agent_comparison import comparison_selection
    from app.services.agent_delegation import ORCHESTRATOR_SEARCH_ROUNDS, DelegationLoop
    from app.services.agent_memory import MemorySnapshot
    from app.services import user_memory
    from app.services.agent_policy import AgentPolicy
    from app.services.agent_runs import get_agent_turn_context, with_app_context
    from app.services.agent_tools import search_tools
    from app.services.llm.agent_client import AgentCompletion, resolve_agent_model
    from app.services.llm.provider_runtime import (AnalysisBudget, ProviderCancellation, bind_analysis_budget,
                                                   bind_provider_cancellation)
    from test_agent_runs import AgentRunStore, Database, UID, pending

    config = prompt_config.get_config()
    delegation_config = {**config["delegation"], "enabled": False}
    model = resolve_agent_model(args.model)
    key = os.environ["OPENROUTER_API_KEY"]
    families = {p: cfg.FREE_DEFAULT_MODEL_BY_PROVIDER[p] for p in ("openai", "anthropic", "gemini", "deepseek", "grok", "glm")}
    total, passed = 0.0, 0
    cases = [*CASES, *(MEMORY_CASES if args.memory else [])]
    selected = [(i, case) for i, case in enumerate(cases) if not args.only or i in args.only]
    for index, (expected, history, message) in selected:
        store = AgentRunStore(Database())
        chat, turn = pending(store, question=message)
        messages = [{"role": "system", "content": config["prompts"]["agent"]}, *history,
                    {"role": "user", "content": with_app_context(message, get_agent_turn_context(model, config))}]
        sources = [{"url": LIVE, "title": "Livebericht"}] if history is EARLIER else []
        loop = DelegationLoop(store=store, uid=UID, chat_id=chat, turn_id=turn["id"], model=model, messages=messages,
                              api_key=key, cancellation=ProviderCancellation(),
                              policy=AgentPolicy.for_chat(delegation_config), delegation_config=delegation_config,
                              completion_factory=AgentCompletion, comparison_models=comparison_selection(families),
                              check_sources=True, chat_sources=sources,
                              memory=MemorySnapshot(available=True, enabled=True, auto=True,
                                                    profile=user_memory.empty_profile()) if args.memory else None)
        value = AgentCompletion()
        value.tool_call_limit, value.tool_argument_limit = 4, loop.registry.argument_limit
        # As the first routing step in prod: research before a comparison.
        rounds = ORCHESTRATOR_SEARCH_ROUNDS
        started = time.monotonic()
        error = None
        try:
            with bind_analysis_budget(AnalysisBudget(seconds=180, max_calls=1)), \
                    bind_provider_cancellation(ProviderCancellation()):
                list(value.stream(model=model, messages=loop.messages, api_key=key,
                                  tools=[*loop.registry.schemas, *search_tools(model, rounds)], native_searches=rounds,
                                  allow_tool_calls=True))
        except Exception as exc:  # A probe records the category, never provider bodies.
            error = type(exc).__name__
        names = [call["function"]["name"] for call in value.tool_calls]
        got = decision(names)
        ok = error is None and passes(expected, got)
        # With memory on, answer must carry its required memory decision.
        memory_missing = args.memory and any(
            call["function"]["name"] == "answer" and "memory" not in json.loads(call["function"]["arguments"] or "{}")
            for call in value.tool_calls)
        ok = ok and not memory_missing
        memory_ops = []
        for call in value.tool_calls if args.memory else []:
            if call["function"]["name"] not in {"answer", "update_memory"}:
                continue
            arguments = json.loads(call["function"]["arguments"] or "{}")
            changes = arguments.get("memory", arguments.get("changes"))
            memory_ops.append([change.get("op") for change in changes if isinstance(change, dict)]
                              if isinstance(changes, list) else repr(changes)[:200])
        passed += ok
        cost = ((value.usage or {}).get("estimated_cost_nano_usd") or 0) / 1e9
        total += cost
        print(json.dumps({"case": index, "ok": ok, "expected": expected, "got": got, "tools": names,
                          "searches": (value.usage or {}).get("web_search_requests"), "error": error,
                          **({"memory_missing": True} if memory_missing else {}),
                          **({"memory_ops": memory_ops} if args.memory else {}),
                          "text": value.text[:120], "seconds": round(time.monotonic() - started, 1),
                          "cost_usd": round(cost, 5)}, ensure_ascii=False))
    print(json.dumps({"model": model.selection_id, "memory": args.memory, "passed": passed, "cases": len(selected),
                      "cost_usd": round(total, 4)}))


if __name__ == "__main__":
    main()

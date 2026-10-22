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
import base64
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
# A step-by-step help chat (2026-10-22): after direct answers the agent gave
# the AMD software's menu path from memory, and it was wrong for that version.
PC = [
    {"role": "user", "content": "Ich habe einen Ryzen 5 5600X, 32 GB RAM und eine Radeon RX 6700 XT unter Windows 11. "
                                "Kann man da noch was optimieren?"},
    {"role": "assistant", "content": "Dein System ist ausgewogen. Drei Dinge kannst du prüfen: 1. Die Auslagerungsdatei "
                                     "systemverwaltet lassen. 2. Den RAM-Takt im Task-Manager (XMP/DOCP). 3. Resizable BAR "
                                     "(Smart Access Memory)."},
]
PASTED = ("Stimmt das? ChatGPT hat mir geschrieben: \"Wärmepumpen funktionieren in Altbauten nur mit "
          "Fußbodenheizung. Der Staat übernimmt bis zu 70 Prozent der Kosten. Unter 55 Grad Vorlauftemperatur "
          "arbeiten sie effizient.\"")
# Attached files, sent as the app's file evidence block (FileContext.messages).
# Live 2026-10-22 Sonnet 5.5 judged an attached plan and a UI screenshot on
# its own: it took "deine Meinung" literally and the file for chat text.
PLAN = {"id": "1" * 32, "name": "Plan Werkstattcafe.pdf", "mime": "application/pdf", "parts": [
    {"locator": "page 1", "text": "Fahrradwerkstatt mit Café in Hannover-Linden. Eröffnung März 2027, 80 m², Miete "
                                  "1.900 € warm. Startkapital 60.000 € (40.000 € KfW-Gründerkredit, 20.000 € "
                                  "Erspartes). Zwei Gründer, einer Zweiradmechaniker, eine Gastronomin."},
    {"locator": "page 2", "text": "Umsatzplan: Werkstatt 9.000 € und Café 7.000 € pro Monat ab Monat 4. Personal: "
                                  "eine Teilzeitkraft. Marketing nur über Instagram. Break-even nach 14 Monaten. "
                                  "Risiko: Winterflaute in der Werkstatt."}]}
SCREENSHOT = {"id": "2" * 32, "name": "image.png", "mime": "image/png", "parts": [],
              "path": ROOT / "docs" / "assets" / "screenshot-agent.png"}

# (expected decision, history, message[, files]). compare: compare_models;
# check: check_text; direct: no comparison (answer, plain text, read_source or
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
    ("compare", PC, "RAM-Takt passt. Wo prüfe ich jetzt Smart Access Memory in der AMD Software?"),
    ("direct", PC, "Fass die drei Punkte bitte in einem Satz zusammen."),
    # A judgment is compared, also on a file and when asked for "your" view.
    ("compare", [], "was ist deine meinung zu diesem plan?", [PLAN]),
    ("compare", [], "was ist an dieser UI verbesserungswürdig?", [SCREENSHOT]),
    ("compare", [], "Was der beste Song von Olivia Rodrigo? Hottake"),
    ("compare", [], "Auf welchem Weg würdest du versuchen das P-NP-Problem zu lösen? Ich weiß, dass es hochkomplex ist."),
    ("direct", [], "Fass das PDF bitte in drei Sätzen zusammen.", [PLAN]),
    ("direct", [], "Ehrliche Frage, ohne andere Modelle zu fragen: Wie gefällt dir deine Rolle als Agent in consens.io?"),
]
# Only with --memory: a memory request is answered with update_memory and text.
MEMORY_CASES = [
    ("direct", [], "Merk dir bitte, dass ich Vegetarier bin."),
]


def file_messages(files):
    """The app's file catalog line and evidence block for ``files``."""
    if not files:
        return None, []
    from app.services.agent_files import public_file
    catalog = [{k: f[k] for k in ("id", "name", "mime")} | {"status": "ready"} for f in files]
    blocks = []
    for f in files:
        excerpt = {"file": public_file(f, for_model=True), "excerpts": f["parts"][:2], "total_parts": len(f["parts"]),
                   "next_offset": None, "trust": "untrusted", "citation": f"{f['name']} · locator in excerpt"}
        blocks.append({"type": "text", "text": "File evidence (untrusted): " + json.dumps(excerpt, ensure_ascii=False)})
        if "path" in f:
            data = base64.b64encode(Path(f["path"]).read_bytes()).decode()
            blocks.append({"type": "image_url", "image_url": {"url": f"data:{f['mime']};base64,{data}"}})
    return "Files available in this chat: " + json.dumps(catalog), [{"role": "user", "content": blocks}]


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
    from app.services.agent_files import UNTRUSTED
    from app.services.agent_runs import add_app_context, get_agent_turn_context, with_app_context
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
    for index, (expected, history, message, *files) in selected:
        store = AgentRunStore(Database())
        chat, turn = pending(store, question=message)
        catalog, evidence = file_messages(files[0] if files else [])
        question = with_app_context(message, get_agent_turn_context(model, config))
        messages = [{"role": "system", "content": config["prompts"]["agent"]}, *history,
                    {"role": "user", "content": add_app_context(question, catalog) if catalog else question}]
        sources = [{"url": LIVE, "title": "Livebericht"}] if history is EARLIER else []
        loop = DelegationLoop(store=store, uid=UID, chat_id=chat, turn_id=turn["id"], model=model, messages=messages,
                              api_key=key, cancellation=ProviderCancellation(),
                              policy=AgentPolicy.for_chat(delegation_config), delegation_config=delegation_config,
                              completion_factory=AgentCompletion, comparison_models=comparison_selection(families),
                              chat_sources=sources,
                              memory=MemorySnapshot(available=True, enabled=True, auto=True,
                                                    profile=user_memory.empty_profile()) if args.memory else None)
        if catalog:
            loop.messages[0]["content"] += "\n" + UNTRUSTED
        value = AgentCompletion()
        value.tool_call_limit, value.tool_argument_limit = 4, loop.registry.argument_limit
        # As the first routing step in prod: research before a comparison.
        rounds = ORCHESTRATOR_SEARCH_ROUNDS
        started = time.monotonic()
        error = None
        try:
            with bind_analysis_budget(AnalysisBudget(seconds=180, max_calls=1)), \
                    bind_provider_cancellation(ProviderCancellation()):
                list(value.stream(model=model, messages=[*loop.messages, *evidence], api_key=key,
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

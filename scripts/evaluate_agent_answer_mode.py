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

Where the time goes (seconds since the turn started, see Timing):
- phases: comparison start/end, first answer text, judges start/end
- timeline: one entry per provider call, chat steps (completion:N) and
  workers (comparison answers, judges, page reads): start, claimed, request,
  first_progress, first_text, end, settled, wait (admission), ttft,
  max_silence (longest stretch without a token, the 180 s stall watchdog's
  measure), tokens, error (HTTP status or exception class) and stalled
- after_comparison: seconds_after_comparison split into chat steps, page
  reads and the rest (app work, retry pauses)
- rate_limits, stalls, retries, allowance_refusals, longest_silence
"""
import argparse
from contextlib import contextmanager
import json
import os
from pathlib import Path
import random
import re
import statistics
import sys
import threading
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
# Also OpenAI's citation marks (agent_client.CITE_MARK), should one get past.
LEAKS = re.compile(r"\b(compare_models|check_text|read_source|prepare_watch|update_memory|status_update|"
                   r"judge_answer|tool calls?|tool results?|comparison results?|untrusted|Model [A-F]|"
                   r"cite\W?turn\d+\w*|turn\d+search\d+)\b|[-]", re.I)
STEP = re.compile(r"^completion:(\d+)/started$")
TOOL_STEP = re.compile(r"^completion:(\d+):")

PAIRWISE_PROMPT = """You compare two answers to the same user question for a blind quality test.
Judge which answer serves the user better: correct and current facts, faithfulness to what is known,
clear recommendation where one is possible, useful structure, no filler, no process talk about tools
or models. Length alone is no merit. Reply with JSON only:
{"better": "1" | "2" | "tie", "reason": "<one sentence>"}"""


def usd(nanos):
    return round((nanos or 0) / 1e9, 5)


# The provider call a stream is opening on this thread, for the stall
# watchdog it creates (Timing.installed).
_ACTIVE = threading.local()


class Timing:
    """Where a turn's time goes, read from what the run does anyway.

    One record per provider call: chat-model steps (completion:N) and
    workers (agent:<id>:N: comparison answers, judges, page reads). Times are
    seconds since the turn started: ``start`` (the step began, before its
    admission), ``claimed`` (admitted, receipt written), ``request`` (sent),
    ``first_progress`` (first token, reasoning or tool call: what the stall
    watchdog counts as progress), ``first_text``, ``end`` (stream closed) and
    ``settled`` (receipt settled). ``max_silence`` is the longest stretch
    without progress, the wait for the first token included; the watchdog
    ends a call at AGENT_PROVIDER_STALL_SECONDS (180 s). ``error`` is the HTTP
    status or the exception class of a failed call, never a provider body;
    ``stalled`` marks a call the watchdog ended. Prompts and answers are not
    recorded."""

    def __init__(self):
        # perf_counter: Windows' monotonic clock ticks in 15.6 ms steps.
        self.started = time.perf_counter()
        self.lock = threading.Lock()
        self.calls = {}
        # Worker kind and title by agent id, from the session events.
        self.agents = {}
        # Claims the daily allowance refused: the step waited for other calls
        # to settle, or tried again with less search or output.
        self.refused_claims = 0

    def clock(self):
        return time.perf_counter() - self.started

    def call(self, step):
        with self.lock:
            return self.calls.setdefault(step, {})

    def first(self, record, key, at=None):
        if record.get(key) is None:
            record[key] = self.clock() if at is None else at

    def progress(self, record):
        at = self.clock()
        last = record.get("_last", record.get("request"))
        if last is not None:
            record["max_silence"] = max(record.get("max_silence", 0), at - last)
        record["_last"] = at
        self.first(record, "first_progress", at)

    def end(self, record):
        record["end"] = at = self.clock()
        last = record.get("_last", record.get("request"))
        if last is not None:
            record["max_silence"] = max(record.get("max_silence", 0), at - last)

    @staticmethod
    def error(record, error):
        status = getattr(error, "status_code", None)
        record["error"] = str(status) if status else type(error).__name__
        if isinstance(error, TimeoutError) and "no progress" in str(error):
            record["stalled"] = True

    def watch_store(self, store):
        """Claims, settlements and worker sessions of this turn's store."""
        from app.services.agent_quota import AgentTokenBudgetExceeded
        claim, settle, publish = store.claim, store.settle, store.publish_agent

        def timed_claim(*args, **kwargs):
            try:
                claimed = claim(*args, **kwargs)
            except AgentTokenBudgetExceeded:
                record = self.call(kwargs.get("step", "completion:0"))
                with self.lock:
                    self.refused_claims += 1
                    record["refused"] = record.get("refused", 0) + 1
                raise
            if claimed:
                record = self.call(kwargs.get("step", "completion:0"))
                self.first(record, "claimed")
                model = kwargs.get("model", args[3] if len(args) > 3 else None)
                record["model"] = getattr(model, "model", None)
            return claimed

        def timed_settle(*args, **kwargs):
            settled = settle(*args, **kwargs)
            record = self.call(kwargs.get("step", "completion:0"))
            self.first(record, "settled")
            completion = kwargs.get("completion")
            usage = getattr(completion, "usage", None) or {}
            record.update(status=kwargs.get("status"), finish_reason=getattr(completion, "finish_reason", None) or None,
                          input_tokens=usage.get("input_tokens"), output_tokens=usage.get("output_tokens"),
                          reasoning_tokens=usage.get("reasoning_tokens"))
            return settled

        def timed_publish(*args, agent_id=None, patch=None, **kwargs):
            if patch:
                with self.lock:
                    known = self.agents.setdefault(agent_id, {"created": self.clock()})
                    for key in ("kind", "title"):
                        if patch.get(key):
                            known.setdefault(key, patch[key])
            return publish(*args, agent_id=agent_id, patch=patch, **kwargs)

        store.claim, store.settle, store.publish_agent = timed_claim, timed_settle, timed_publish

    def completion(self, base):
        """``base`` with its stream timed (first progress, first text, end)
        and its failures recorded."""
        timing = self

        class Timed(base):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self._timing_start = timing.clock()

            def stream(self, *args, **kwargs):
                record = self._timing = timing.call(self.step_id)
                timing.first(record, "start", self._timing_start)
                record["request"] = timing.clock()
                # The watchdog is created on the first next(), on this thread.
                _ACTIVE.record = record
                source = super().stream(*args, **kwargs)
                try:
                    for event in source:
                        _ACTIVE.record = None
                        if event.get("type") == "delta":
                            timing.first(record, "first_text")
                            timing.progress(record)
                        elif event.get("kind") == "reasoning":
                            timing.progress(record)
                        yield event
                finally:
                    _ACTIVE.record = None
                    source.close()
                    timing.end(record)

            def _tool_delta(self, raw):
                if getattr(self, "_timing", None) is not None:
                    timing.progress(self._timing)
                return super()._tool_delta(raw)

            def record_rejection(self, error, model):
                timing.error(timing.call(self.step_id), error)
                return super().record_rejection(error, model)

        Timed.__name__ = base.__name__
        return Timed

    @contextmanager
    def installed(self):
        """Time the progress of real provider streams: the stall watchdog
        sees every token, reasoning delta and tool-call fragment."""
        from app.services.llm import provider_runtime
        base = provider_runtime.ProviderProgressWatchdog
        timing = self

        class TimedWatchdog(base):
            def __init__(self, seconds):
                self.record = None
                super().__init__(seconds)
                self.record = getattr(_ACTIVE, "record", None)

            def touch(self):
                super().touch()
                if self.record is not None:
                    timing.progress(self.record)

            def check(self):
                try:
                    super().check()
                except TimeoutError:
                    if self.record is not None:
                        self.record["stalled"] = True
                    raise

        provider_runtime.ProviderProgressWatchdog = TimedWatchdog
        try:
            yield self
        finally:
            provider_runtime.ProviderProgressWatchdog = base

    def timeline(self, digits=1):
        """The calls in order of their start, internal fields dropped, times
        rounded to ``digits`` (None: exact, for comparing them)."""
        rows = []
        with self.lock:
            calls, agents = dict(self.calls), dict(self.agents)
        for step, record in calls.items():
            agent = agents.get(step.split(":")[1], {}) if step.startswith("agent:") else {}
            kind = "chat" if step.startswith("completion:") else agent.get("kind", "worker")
            # A worker starts when it is created: waiting for a judge slot
            # or for admission is part of its time.
            start = record.get("start") if kind == "chat" else agent.get("created", record.get("start"))
            start = record.get("claimed") if start is None else start
            row = {"call": step if kind == "chat" else f"{kind}:{step.split(':')[1][:8]}", "kind": kind,
                   "title": agent.get("title"), "model": record.get("model"), "start": start,
                   **{key: record.get(key) for key in ("claimed", "request", "first_progress", "first_text", "end",
                                                       "settled", "max_silence")}}
            if start is not None and row["claimed"] is not None:
                row["wait"] = row["claimed"] - start
            if row["request"] is not None and row["first_progress"] is not None:
                row["ttft"] = row["first_progress"] - row["request"]
            done = row["settled"] if row["settled"] is not None else row["end"]
            if start is not None and done is not None:
                row["seconds"] = done - start
            row.update({key: record.get(key) for key in ("refused", "status", "finish_reason", "error", "stalled",
                                                         "input_tokens", "output_tokens", "reasoning_tokens")})
            rows.append({key: round(value, digits) if isinstance(value, float) and digits is not None else value
                         for key, value in row.items() if value is not None})
        return sorted(rows, key=lambda row: (row.get("start", float("inf")), row["call"]))


def after_comparison(timeline, begin, end):
    """seconds_after_comparison split: chat steps, page reads and the rest
    (app work between them, the page-excerpt wait, retry pauses). Both run on
    the loop's thread one after another, so their spans add up."""
    if begin is None or end is None:
        return None
    inside = [row for row in timeline if row["kind"] in {"chat", "source"} and row.get("start") is not None
              and begin <= row["start"] <= end]
    chat = sum(row.get("seconds", 0) for row in inside if row["kind"] == "chat")
    reads = sum(row.get("seconds", 0) for row in inside if row["kind"] == "source")
    return {"chat_seconds": round(chat, 1), "read_seconds": round(reads, 1),
            "other_seconds": round(max(0.0, end - begin - chat - reads), 1),
            "calls": [row["call"] for row in inside]}


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
    timing = Timing()
    timing.watch_store(store)
    delegation_config = {**config["delegation"], "enabled": False}
    messages = [{"role": "system", "content": config["prompts"]["agent"]},
                {"role": "user", "content": with_app_context(question, get_agent_turn_context(model, config))}]
    loop = DelegationLoop(store=store, uid=UID, chat_id=chat, turn_id=turn["id"], model=model, messages=messages,
                          api_key=key, cancellation=ProviderCancellation(),
                          policy=AgentPolicy.for_chat(delegation_config), delegation_config=delegation_config,
                          completion_factory=timing.completion(AgentCompletion),
                          comparison_models=comparison_selection(families),
                          check_sources=check_sources, merged_answer=merged)
    timing.started = time.perf_counter()
    events, error = [], None
    try:
        with timing.installed():
            for event in loop.run():
                events.append((timing.clock(), event))
    except Exception as exc:  # A failed turn is a result; provider bodies are never printed.
        error = f"{type(exc).__name__}: {str(exc)[:160]}"
    total = timing.clock()
    saved = store.get_turn(UID, chat, turn["id"]) or {}
    text = saved.get("assistant_response") or saved.get("consensus") or ""

    first_delta = next((t for t, e in events if e.get("type") == "delta"), None)
    judges = [(t, e) for t, e in events if e.get("kind") == "tool" and e.get("name") == "judge_answer"]
    judge = judges[0][0] if judges else None
    judge_done = next((t for t, e in reversed(judges) if e.get("status") in {"succeeded", "failed"}), None)
    compares = [(t, e) for t, e in events if e.get("kind") == "tool" and e.get("name") in {"compare_models", "check_text"}
                and e.get("status") == "succeeded"]
    answer_done = judge if judge is not None else (total if text else None)
    last_compare = compares[-1][0] if compares else None
    compare_step = compare_started = None
    if compares:
        match = TOOL_STEP.match(str(compares[-1][1].get("id") or ""))
        compare_step = int(match.group(1)) if match else None
        compare_started = next(t for t, e in events if e.get("id") == compares[-1][1].get("id"))
    steps = receipts(store, UID, chat, turn["id"])
    after = [s for s in steps if compare_step is not None and s["step"] > compare_step]
    review = saved.get("agent_review") or {}
    checks = [((c.get("differences_data") or {}).get("agreement") or {}) for c in review.get("checks") or []]
    usage = loop.completion.usage or {}
    timeline = timing.timeline()
    silent = max(timeline, key=lambda row: row.get("max_silence", 0), default=None)

    def at(value):
        return None if value is None else round(value, 1)
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
        "phases": {"comparison_started": at(compare_started), "comparison_done": at(last_compare),
                   "answer_text": at(first_delta), "judges_started": at(judge), "judges_done": at(judge_done),
                   "end": at(total)},
        "after_comparison": after_comparison(timing.timeline(digits=None), last_compare, answer_done),
        "rate_limits": sum(row.get("error") == "429" for row in timeline),
        "stalls": sum(bool(row.get("stalled")) for row in timeline),
        # Thought-only steps written again lighter, 429 or cooldown waits.
        "retries": sum(1 for _, e in events if e.get("kind") == "progress"
                       and str(e.get("id", "")).endswith(("/retry", "/rate_limit"))),
        "allowance_refusals": timing.refused_claims,
        "longest_silence": ({"call": silent["call"], "seconds": silent["max_silence"]}
                            if silent and "max_silence" in silent else None),
        "timeline": timeline,
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
            "major_contradictions": sum(r["major_contradictions"] for r in mine),
            "rate_limits": sum(r["rate_limits"] for r in mine), "stalls": sum(r["stalls"] for r in mine),
            "retries": sum(r["retries"] for r in mine),
            "longest_silence": max((r["longest_silence"]["seconds"] for r in mine if r["longest_silence"]),
                                   default=None)}


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
    # The test account exists only in memory; looked up in Firestore it would
    # be Free. Every turn gets a fresh in-memory account, where Free does not
    # wait either (replayed offline 2026-10-14: the 434-518 s of the first
    # Free run did not come from the allowance; Pro runs took up to 672 s).
    # Pinned anyway, so no turn depends on a Firestore lookup.
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

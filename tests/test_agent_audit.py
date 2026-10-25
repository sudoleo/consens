"""Audit instead of comparison (AgentPreferences.audit, admin accounts only):
the agent answers itself with its own search and gets no comparison tools;
the comparison models follow its work log in rounds and review the fixed
answer in a final round, marking passages and log entries with a note; the
app places their quotes on the answer's sentences. Without the setting
everything runs as before (test_agent_comparison, test_agent_answer_mode).
"""
import json
import threading
import time

import pytest

from app.services import agent_audit, agent_memory, prompt_defaults
from app.services.agent_audit import (AGENT_SEARCH_ROUNDS, LIVE_SEARCH_ROUNDS, REVIEW_SEARCH_ROUNDS, locate_quote,
                                      parse_review, place_marks, review_entry, round_message, work_goes_on)
from app.services.agent_comparison import (AUDIT_OFF_PROMPT, AgentPreferences, JudgeArgs, comparison_selection,
                                           preference_prompt)
from app.services.agent_tools import ReadOnlyTool, ToolRegistry
from app.services.agent_delegation import DelegationLoop
from app.services.agent_delegation_config import defaults
from app.services.agent_policy import AgentPolicy
from app.services.llm.agent_client import AgentCompletion, measured_usage, resolve_agent_model
from app.services.llm.provider_runtime import ProviderCancellation, ProviderCancelled, current_provider_cancellation
from test_agent_runs import AUTH, UID, api, pending, store  # noqa: F401  (fixtures)


@pytest.fixture(autouse=True)
def _admin_allowance(monkeypatch):
    """Audit mode is for admins, whose daily account (5M tokens) holds the
    agent's five search rounds; the suites' 250k (conftest) would not."""
    from app.services import agent_budget_config
    monkeypatch.setitem(agent_budget_config.DEFAULT_TIER_LIMITS, "pro", 5_000_000)


ANSWER = ("The Eiffel Tower is 330 metres tall. It was built in 1889 for the World's Fair. "
          "**Gustave Eiffel** did not design it alone: the engineers Maurice Koechlin and Emile Nouguier drew "
          "the first plans. About seven million people visit it every year, according to the "
          "[official site](https://www.toureiffel.paris/en). Tickets to the top cost 14 euros.")
RATES = "https://www.toureiffel.paris/en/rates-opening-times"
REVIEWS = {
    "anthropic": json.dumps({"marks": [
        {"quote": "Tickets to the top cost 14 euros", "kind": "wrong", "note": "The top costs 36.10 euros.",
         "source": RATES},
        {"quote": "according to the official site", "kind": "doubtful", "note": "The site counts about 6 million."},
    ]}),
    # In a code fence, with a synonym, a source that is no URL and a quote the answer does not hold.
    "openai": "```json\n" + json.dumps({"marks": [
        {"quote": "tickets to the TOP cost 14 euros.", "kind": "incorrect", "note": "Too low.", "source": "the website"},
        {"quote": "Gustave Eiffel did not design it alone", "kind": "missing", "note": "Stephen Sauvestre is missing."},
        {"quote": "The Eiffel Tower is 400 metres tall", "kind": "wrong", "note": "Not in the answer.",
         "source": "https://example.org/height"},
    ]}) + "\n```",
}


class Audit:
    """A scripted audit-mode turn: the agent's first ``tool_steps`` steps
    (completion:N) call the tool ``lookup``, the next one answers, each after
    its own search. Every other call is a reviewer: its final round replies
    with ``reviews[family]``, a live round with ``live[family]`` (a text, an
    exception or "wait": until it is stopped)."""

    def __init__(self, reviews=None, *, answer=ANSWER, search=True, tool_steps=0, live=None, on_lookup=None):
        self.reviews = dict(REVIEWS if reviews is None else reviews)
        self.on_lookup = on_lookup
        self.live = dict(live or {})
        self.answer = answer
        self.search = search
        self.tool_steps = tool_steps
        self.calls, self.offered, self.searches, self.prompts, self.rounds = [], [], {}, {}, {}
        self.loop = None

    def factory(self):
        script = self

        class Completion(AgentCompletion):
            def stream(self, *, model, messages, **kwargs):
                script.calls.append((self.step_id, model.model))
                self.usage = measured_usage({"prompt_tokens": 50, "completion_tokens": 20, "cost": .0001}, model)
                names = [tool["function"]["name"] for tool in kwargs.get("tools") or [] if tool.get("type") == "function"]
                if self.step_id.startswith("completion:"):
                    script.offered.append(names)
                    script.searches[self.step_id] = kwargs.get("native_searches")
                    # The agent's own search found a page, then it writes.
                    if script.search:
                        self.sources = [{"url": "https://www.toureiffel.paris/en", "title": "Official site"}]
                        self._results_at = 0
                    index = int(self.step_id.split(":")[1])
                    if index < script.tool_steps:
                        self.tool_calls = [{"id": f"call_{index}", "type": "function",
                                            "function": {"name": "lookup", "arguments": "{}"}}]
                        self.finish_reason = "tool_calls"
                        return
                    for start in range(0, len(script.answer), 60):
                        chunk = script.answer[start:start + 60]
                        self.text += chunk
                        yield {"type": "delta", "text": chunk}
                    self.finish_reason = "stop"
                    return
                family = model.model.split("/")[0]
                final = messages[-1]["content"].startswith("Final round.")
                script.rounds.setdefault(family, []).append("final" if final else "live")
                script.prompts[family] = list(messages)
                script.searches[family] = kwargs.get("native_searches")
                reply = (script.reviews if final else script.live).get(family, json.dumps({"marks": []}))
                if reply == "wait":
                    stop = current_provider_cancellation()
                    while not stop.cancelled:
                        time.sleep(.01)
                    raise ProviderCancelled("stopped")
                if isinstance(reply, BaseException):
                    raise reply
                if callable(reply):
                    reply = reply(messages)
                self.text, self.finish_reason = reply, "stop"
                yield {"type": "delta", "text": self.text}
        return Completion()


def lookup(script):
    """The agent's tool in a scripted turn: its n-th call returns once both
    reviewers started n live rounds, so each step has its round."""
    calls = []

    def run(args, *, cancellation):
        calls.append(args)
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and not all(
                script.rounds.get(f, []).count("live") >= len(calls) for f in ("anthropic", "openai")):
            time.sleep(.01)
        if script.on_lookup:
            script.on_lookup(len(calls))
        return {"text": "The tower is 330 metres tall."}
    return ReadOnlyTool("lookup", "Look something up.", JudgeArgs, run)


def audit_loop(store, script, *, judges="on", audit="on", messages=None, memory=None):
    chat, turn = pending(store)
    config = {**defaults(), "enabled": False, "max_searches": 0}
    loop = DelegationLoop(store=store, uid=UID, chat_id=chat, turn_id=turn["id"],
        model=resolve_agent_model("claude-haiku-4-5"),
        messages=messages or [{"role": "system", "content": "Answer."},
                              {"role": "user", "content": "Tell me about the Eiffel Tower."}],
        api_key="test", cancellation=ProviderCancellation(), policy=AgentPolicy.for_chat(config),
        delegation_config=config, completion_factory=script.factory,
        comparison_models=comparison_selection({"anthropic": "claude-haiku-4-5", "openai": "gpt-5.4-mini"}),
        agent_preferences=AgentPreferences(audit=audit, judges=judges), memory=memory)
    if script.tool_steps:
        loop.registry = ToolRegistry([*loop.registry.tools.values(), lookup(script)],
                                     argument_limit=loop.registry.argument_limit)
    script.loop = loop
    return loop


def saved(store, loop):
    return store.get_turn(UID, loop.chat_id, loop.turn_id)


def round_entries(message):
    """The log entries of a round's user message, and the fixed answer of the final round."""
    text = message["content"]
    log, _, answer = text.partition("\n\nThe fixed answer:\n")
    entries = json.loads(log[log.index("\n") + 1:])["entries"]
    return entries, (json.loads(answer)["answer"] if answer else None)


def entry_of(messages, kind, name=None):
    """The number of the newest entry of ``kind`` the reviewer has read."""
    entries = [e for m in messages if m["role"] == "user" for e in round_entries(m)[0]]
    return [e["seq"] for e in entries if e["kind"] == kind and name in (None, e.get("name"))][-1]


def by_anchor(review):
    return {claim["anchor"]: claim for claim in review["audit"]["claims"]}


# --- The turn -------------------------------------------------------------------

def test_the_agent_answers_itself_and_the_comparison_models_review_its_answer(store):
    script = Audit()
    loop = audit_loop(store, script)
    events = list(loop.run())
    turn = saved(store, loop)
    review = turn["agent_review"]
    assert turn["status"] == "completed" and turn["consensus"] == ANSWER
    # No comparison: the agent is offered neither tool, and searches in every step.
    assert script.offered and all("compare_models" not in names and "check_text" not in names
                                  for names in script.offered)
    assert {step: rounds for step, rounds in script.searches.items() if step.startswith("completion:")} == {
        "completion:0": AGENT_SEARCH_ROUNDS}
    assert [step for step, _ in script.calls if step.startswith("completion:")] == ["completion:0"]
    # The answer streamed as it was written, then the app announced its check.
    assert "".join(e["text"] for e in events if e.get("type") == "delta") == ANSWER
    first_review = next(i for i, e in enumerate(events) if e.get("type") == "review")
    assert any(e.get("type") == "answer_check" for e in events[:first_review])
    # Both comparison models reviewed it with their own search; no judge ran.
    assert script.searches["anthropic"] == script.searches["openai"] == REVIEW_SEARCH_ROUNDS
    assert loop.comparison.judge_calls == 0
    assert not any(e.get("kind") == "tool" and e.get("name") == "judge_answer" for e in events)
    assert [e["status"] for e in events if e.get("kind") == "tool" and e.get("name") == "audit_answer"] == [
        "running", "succeeded"]
    # The review: bound to the answer, every reviewer done, marks with notes.
    assert review["mode"] == "audit" and review["status"] == "succeeded" and review["comparisons"] == []
    assert review["versions"][-1]["text"] == ANSWER and review["versions"][-1]["hash"] == review["answer_hash"]
    assert [(r["provider"], r["status"], r["marks"]) for r in review["audit"]["reviewers"]] == [
        ("anthropic", "completed", 2), ("openai", "completed", 3)]
    claims = by_anchor(review)
    tickets = claims["Tickets to the top cost 14 euros."]
    # Two reviewers on one sentence: one mark, both notes, the most severe kind.
    assert tickets["kind"] == "wrong" and tickets["agree"] == [] and tickets["audit"] is True
    assert [(d["model"], d["kind"], d["note"], d.get("source"), d["mark"]) for d in tickets["dissent"]] == [
        ("Anthropic", "wrong", "The top costs 36.10 euros.", RATES, 1), ("OpenAI", "doubtful", "Too low.", None, 3)]
    assert [d["target"] for d in tickets["dissent"]] == ["Tickets to the top cost 14 euros."] * 2
    # A link is quoted by its words; Markdown emphasis does not count.
    visitors = next(c for anchor, c in claims.items() if anchor.startswith("About seven million"))
    # The quoted words as the page shows them: a link by its label.
    assert visitors["kind"] == "doubtful" and visitors["dissent"][0]["target"] == "according to the official site."
    eiffel = next(c for anchor, c in claims.items() if anchor.startswith("**Gustave Eiffel**"))
    assert eiffel["kind"] == "incomplete" and eiffel["dissent"][0]["note"] == "Stephen Sauvestre is missing."
    # Unmarked sentences carry nothing: no objection, not "confirmed".
    assert "The Eiffel Tower is 330 metres tall." not in claims
    assert review["audit"]["unplaced"] == [{"model": "OpenAI", "kind": "wrong", "note": "Not in the answer.",
                                            "source": "https://example.org/height", "mark": 5,
                                            "quote": "The Eiffel Tower is 400 metres tall"}]
    assert review["audit"]["process"] == []
    # An answer written in one step: only the final round, no live round.
    assert script.rounds == {"anthropic": ["final"], "openai": ["final"]}
    # The agent's own search put pages in view: memory is locked for the turn.
    assert loop.memory_locked is True
    # A reviewer's session saves what it reads, not a copy of it.
    sessions = [a for a in store.delegation_view(UID, loop.chat_id, loop.turn_id)["agents"] if a.get("kind") == "audit"]
    assert len(sessions) == 2
    for session in sessions:
        agent = store.delegation_view(UID, loop.chat_id, loop.turn_id, agent_id=session["id"])["agent"]
        assert agent["assignment"]["context"] == agent_audit.REVIEW_ASSIGNMENT


def test_the_reviewers_read_the_work_log_and_the_whole_answer(store):
    script = Audit()
    loop = audit_loop(store, script, messages=[
        {"role": "system", "content": "Answer."}, {"role": "user", "content": "Paris trip?"},
        {"role": "assistant", "content": "Yes, go in spring."}, {"role": "user", "content": "And the tower?"}])
    list(loop.run())
    system, user = script.prompts["openai"]
    assert system["content"].startswith("You are an independent reviewer") and "Current date:" in system["content"]
    assert user["content"].startswith("Final round.")
    entries, answer = round_entries(user)
    assert answer == ANSWER
    # What the agent received, by origin, its step and what the app did.
    context = [(e["name"], e["data"], e["content"]) for e in entries if e["kind"] == "context"][:4]
    assert [(name, data) for name, data, _ in context] == [
        ("system", "app"), ("user", "user"), ("assistant", "agent"), ("user", "user")]
    assert [content for _, _, content in context[1:]] == ["Paris trip?", "Yes, go in spring.", "And the tower?"]
    assert context[0][2].startswith("Answer.")
    [step] = [e for e in entries if e["kind"] == "step"]
    assert step["actor"] == "agent" and step["content"]["text"] == ANSWER and "usage" not in step["content"]
    assert [e["seq"] for e in entries] == list(range(1, len(entries) + 1))
    assert [e["name"] for e in entries if e["kind"] == "app"][-1] == "answer_fixed"


def test_the_reviewers_follow_the_work_in_rounds_and_mark_its_entries(store):
    def live_mark(note):
        return lambda messages: json.dumps({"marks": [
            {"entry": entry_of(messages, "step"), "kind": "wrong", "note": note},
            # Unknown entries and quotes while the agent works name nothing.
            {"entry": 999, "kind": "doubtful", "note": "Unknown."},
            {"quote": "The Eiffel Tower", "kind": "doubtful", "note": "No answer yet."}]})

    def final_marks(messages):
        marks = json.loads(REVIEWS["anthropic"])["marks"]
        return json.dumps({"marks": [*marks, {"entry": f"#{entry_of(messages, 'tool', 'lookup')}", "kind": "missing",
                                               "note": "The lookup names no source."}]})
    script = Audit({"anthropic": final_marks, "openai": RuntimeError("provider down")}, tool_steps=1,
                   live={"anthropic": live_mark("Not checked."), "openai": live_mark("Unchecked lookup.")})
    loop = audit_loop(store, script)
    list(loop.run())
    turn = saved(store, loop)
    review = turn["agent_review"]
    assert turn["status"] == "completed" and turn["consensus"] == ANSWER
    assert script.rounds == {"anthropic": ["live", "final"], "openai": ["live", "final"]}
    # One conversation per reviewer: the live round, its reply, the final round.
    system, live, reply, final = script.prompts["anthropic"]
    assert [m["role"] for m in (system, live, reply, final)] == ["system", "user", "assistant", "user"]
    assert live["content"].startswith("Round 1.") and final["content"].startswith("Final round.")
    live_entries, _ = round_entries(live)
    final_entries, answer = round_entries(final)
    assert answer == ANSWER and final_entries[0]["seq"] == live_entries[-1]["seq"] + 1
    assert any(e["kind"] == "step" and e["content"]["tool_calls"] for e in live_entries)
    # Search per round: two while the agent works, three in the final round.
    assert script.searches["anthropic"] == REVIEW_SEARCH_ROUNDS
    # Anthropic's final list counts; OpenAI's final round failed, its live marks stand.
    assert review["status"] == "partial"
    assert [(r["provider"], r["status"], r.get("marks"), r.get("live_marks"), r["rounds"])
            for r in review["audit"]["reviewers"]] == [("anthropic", "completed", 3, None, 1),
                                                     ("openai", "failed", None, 1, 1)]
    step = entry_of(script.prompts["openai"][:2], "step")
    tool = entry_of(script.prompts["anthropic"], "tool", "lookup")
    assert [(p["model"], p["entry"], p["entry_kind"], p["entry_name"], p["kind"], p["mark"], p.get("live"))
            for p in review["audit"]["process"]] == [
        ("Anthropic", tool, "tool", "lookup", "incomplete", 3, None),
        ("OpenAI", step, "step", loop.model.model, "doubtful", 4, True)]
    assert len(review["audit"]["claims"]) == 2 and review["audit"]["unplaced"] == []
    # The panel shows each round: the live round's marks, then the final list.
    sessions = [a for a in store.delegation_view(UID, loop.chat_id, loop.turn_id)["agents"] if a.get("kind") == "audit"]
    assert len(sessions) == 2
    kinds = {}
    for session in sessions:
        messages = store.delegation_view(UID, loop.chat_id, loop.turn_id, agent_id=session["id"])["messages"]
        kinds[session["title"]] = [m["kind"] for m in messages if m["kind"] in {"round", "result"}]
    assert sorted(kinds.values()) == [["round"], ["round", "result"]]


def test_a_failed_live_round_opens_a_new_session_and_its_entries_come_again(store):
    seen = []

    def live(messages):
        seen.append(messages[-1]["content"])
        if len(seen) == 1:
            raise RuntimeError("provider down")
        return json.dumps({"marks": []})
    script = Audit(tool_steps=2, live={"anthropic": live})
    loop = audit_loop(store, script)
    list(loop.run())
    review = saved(store, loop)["agent_review"]
    assert review["status"] == "succeeded"
    # No retry of the same entries at once: the next round waits for new
    # work, and the failed round's entries go into it, in a new session.
    assert script.rounds["anthropic"] == ["live", "live", "final"]
    assert [m.split(".")[0] for m in seen] == ["Round 1", "Round 1"]
    first, again = (round_entries({"content": m})[0] for m in seen)
    assert again[0]["seq"] == first[0]["seq"] == 1 and len(again) > len(first)
    views = store.delegation_view(UID, loop.chat_id, loop.turn_id)["agents"]
    statuses = sorted(a["status"] for a in views if a.get("kind") == "audit")
    assert statuses == ["completed", "completed", "failed"]
    failed = next(a for a in views if a.get("kind") == "audit" and a["status"] == "failed")
    notes = store.delegation_view(UID, loop.chat_id, loop.turn_id, agent_id=failed["id"])["messages"]
    assert [m["text"] for m in notes if m["kind"] == "failure"] == [
        "This round failed. The reviewer goes on in a new session."]


def test_a_live_mark_may_name_any_entry_read_so_far(store):
    marks = []

    def live(messages):
        # Each round marks the agent's first step, read in round 1.
        first = entry_of(messages[:2], "step")
        marks.append(first)
        return json.dumps({"marks": [{"entry": first, "kind": "doubtful", "note": f"Round {len(marks)}."}]})
    script = Audit({"openai": RuntimeError("provider down")}, tool_steps=2, live={"openai": live})
    loop = audit_loop(store, script)
    list(loop.run())
    review = saved(store, loop)["agent_review"]
    assert len(marks) == 2 and marks[0] == marks[1]
    assert [(p["model"], p["entry"], p["note"], p.get("live")) for p in review["audit"]["process"]] == [
        ("OpenAI", marks[0], "Round 1.", True), ("OpenAI", marks[0], "Round 2.", True)]


class RateLimited(RuntimeError):
    status_code = 429
    retry_after = 60


def test_a_reviewers_rate_limit_never_blocks_the_agent_on_the_same_model(store):
    # The agent and the Anthropic reviewer run the same model.
    script = Audit(tool_steps=1, live={"anthropic": RateLimited("busy")})
    loop = audit_loop(store, script)
    list(loop.run())
    turn = saved(store, loop)
    assert turn["status"] == "completed" and turn["consensus"] == ANSWER
    assert [step for step, _ in script.calls if step.startswith("completion:")] == ["completion:0", "completion:1"]
    loop.cooldowns.check(loop.model, loop.api_key)


def test_a_session_between_rounds_ends_with_the_run(store):
    def stop(_):
        auditor = script.loop.comparison.auditor
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and not all(
                s.live_rounds and s.worker and s.worker.state == "waiting" for s in auditor.sessions.values()):
            time.sleep(.01)
        script.loop.cancellation.cancel()
    script = Audit(tool_steps=1, on_lookup=stop)
    loop = audit_loop(store, script)
    with pytest.raises(ProviderCancelled):
        list(loop.run())
    views = store.delegation_view(UID, loop.chat_id, loop.turn_id)["agents"]
    sessions = [a for a in views if a.get("kind") == "audit"]
    assert len(sessions) == 2 and {a["status"] for a in sessions} == {"stopped"}


def test_a_long_step_reads_within_its_limit_and_a_full_session_starts_over(store, monkeypatch):
    step = {"seq": 4, "actor": "agent", "kind": "step", "name": "m", "data": "agent", "format": "json"}
    excerpts = [{"url": f"https://example.org/{i}", "content": "e" * 4000} for i in range(40)]
    item = review_entry(step, json.dumps({"text": "t", "search_excerpts": excerpts}))
    assert len(json.dumps(item["content"])) <= agent_audit.ENTRY_CHARS
    assert item["content"]["search_excerpts"][-1] == "… [20 more items]"
    # A 128k model holds about 200k characters of review; the cap is for cost.
    model = type("Model", (), {"context_length": 128_000, "max_output_tokens": 16_000})
    assert agent_audit.session_budget(model) == 201_600
    model.context_length = 2_000_000
    assert agent_audit.session_budget(model) == agent_audit.SESSION_CHARS
    # A conversation too full for the final round: it starts over with the
    # whole log, read shorter, in a new session.
    monkeypatch.setattr(agent_audit, "session_budget", lambda model: 60_000)
    script = Audit(tool_steps=1, live={"anthropic": json.dumps({"marks": []}), "openai": json.dumps({"marks": []})})
    loop = audit_loop(store, script)
    sessions = {}

    def fill(_):
        for provider, session in loop.comparison.auditor.sessions.items():
            sessions[provider] = session
    script.on_lookup = fill
    original = agent_audit.ReviewerSession._final

    def full(self, answer):
        self.chars = self.budget - 100
        return original(self, answer)
    monkeypatch.setattr(agent_audit.ReviewerSession, "_final", full)
    list(loop.run())
    review = saved(store, loop)["agent_review"]
    assert review["status"] == "succeeded"
    system, final = script.prompts["anthropic"]
    entries, answer = round_entries(final)
    assert answer == ANSWER and entries[0]["seq"] == 1
    views = store.delegation_view(UID, loop.chat_id, loop.turn_id)["agents"]
    assert sorted(a["status"] for a in views if a.get("kind") == "audit") == ["completed"] * 4


def test_a_failed_or_unreadable_review_costs_only_its_marks(store):
    script = Audit({"anthropic": RuntimeError("provider down"), "openai": "Looks fine to me."})
    loop = audit_loop(store, script)
    list(loop.run())
    turn = saved(store, loop)
    review = turn["agent_review"]
    assert turn["status"] == "completed" and turn["consensus"] == ANSWER
    assert review["status"] == "failed" and review["audit"]["claims"] == []
    assert [(r["status"], r["failure"]["code"]) for r in review["audit"]["reviewers"]] == [
        ("failed", "provider_error"), ("failed", "review_unreadable")]
    assert {"code": "reviewers_unavailable", "count": 2} in review["audit"]["issues"]


def test_one_reviewer_left_keeps_its_marks_as_a_partial_review(store):
    script = Audit({"anthropic": RuntimeError("provider down"), "openai": REVIEWS["openai"]})
    loop = audit_loop(store, script)
    list(loop.run())
    review = saved(store, loop)["agent_review"]
    assert review["status"] == "partial"
    assert {d["model"] for c in review["audit"]["claims"] for d in c["dissent"]} == {"OpenAI"}


def test_an_empty_review_means_no_objection(store):
    script = Audit({"anthropic": '{"marks": []}', "openai": "[]"})
    loop = audit_loop(store, script)
    list(loop.run())
    review = saved(store, loop)["agent_review"]
    assert review["status"] == "succeeded" and review["audit"]["claims"] == [] and review["audit"]["unplaced"] == []


def test_reviewers_still_working_at_the_deadline_lose_their_marks_not_the_answer(store, monkeypatch):
    monkeypatch.setattr(agent_audit, "REVIEW_TIME_MARGIN", 0)
    monkeypatch.setattr(agent_audit, "REVIEW_MIN_SECONDS", 0)
    script = Audit({"anthropic": "wait", "openai": REVIEWS["openai"]})
    loop = audit_loop(store, script)
    # Plenty of time while the agent writes; .3 s once the answer is fixed.
    monkeypatch.setattr(loop, "_hard_stop_left", lambda: .3 if loop.comparison.text else 1000)
    list(loop.run())
    turn = saved(store, loop)
    review = turn["agent_review"]
    assert turn["status"] == "completed" and turn["consensus"] == ANSWER
    assert review["status"] == "partial"
    assert [(r["status"], (r.get("failure") or {}).get("code")) for r in review["audit"]["reviewers"]] == [
        ("failed", "no_time"), ("completed", None)]
    assert {"code": "no_time"} in review["audit"]["issues"]


def test_without_time_left_no_reviewer_starts(store, monkeypatch):
    script = Audit()
    loop = audit_loop(store, script)
    monkeypatch.setattr(loop, "_hard_stop_left", lambda: 5 if loop.comparison.text else 1000)
    list(loop.run())
    turn = saved(store, loop)
    assert turn["status"] == "completed" and turn["agent_review"]["status"] == "failed"
    assert turn["agent_review"]["audit"]["issues"] == [{"code": "no_time"}]
    assert "anthropic" not in script.prompts and "openai" not in script.prompts


def test_a_stop_during_the_review_stops_the_reviewers_not_the_answer(store):
    script = Audit({"anthropic": "wait", "openai": "wait"})
    loop = audit_loop(store, script)

    def stop_when_reviewing():
        while len(script.prompts) < 2:
            time.sleep(.01)
        loop.cancellation.cancel()
    threading.Thread(target=stop_when_reviewing, daemon=True).start()
    list(loop.run())
    turn = saved(store, loop)
    # The answer was complete and fixed: the turn ends with it.
    assert turn["status"] == "completed" and turn["consensus"] == ANSWER
    assert turn["agent_review"]["status"] == "cancelled"
    assert {r["status"] for r in turn["agent_review"]["audit"]["reviewers"]} == {"stopped"}


def test_a_stop_before_the_review_starts_still_completes_the_answer(store, monkeypatch):
    script = Audit()
    loop = audit_loop(store, script)
    capture = loop.comparison.capture

    def stop_once_fixed(text):
        capture(text)
        loop.cancellation.cancel()
    monkeypatch.setattr(loop.comparison, "capture", stop_once_fixed)
    list(loop.run())
    turn = saved(store, loop)
    assert turn["status"] == "completed" and turn["consensus"] == ANSWER
    assert turn["agent_review"]["status"] == "cancelled" and not script.prompts


def test_a_failed_save_of_the_marks_is_saved_again_at_the_end(store, monkeypatch):
    script = Audit()
    loop = audit_loop(store, script)
    save, failed = store.save_review, []

    def flaky(uid, chat_id, turn_id, token, review, text):
        if (review.get("audit") or {}).get("claims") and not failed:
            failed.append(review["status"])
            raise RuntimeError("database briefly unavailable")
        return save(uid, chat_id, turn_id, token, review, text)
    monkeypatch.setattr(store, "save_review", flaky)
    list(loop.run())
    review = saved(store, loop)["agent_review"]
    assert failed == ["succeeded"]
    assert review["status"] == "succeeded" and len(review["audit"]["claims"]) == 3


def test_a_completed_answer_never_keeps_a_review_that_says_reviewing(store, monkeypatch):
    script = Audit()
    loop = audit_loop(store, script)
    save = store.save_review

    def down_after_start(uid, chat_id, turn_id, token, review, text):
        if any(r["status"] != "waiting" for r in (review.get("audit") or {}).get("reviewers", [])):
            raise RuntimeError("database unavailable")
        return save(uid, chat_id, turn_id, token, review, text)
    monkeypatch.setattr(store, "save_review", down_after_start)
    list(loop.run())
    turn = saved(store, loop)
    assert turn["status"] == "completed" and turn["consensus"] == ANSWER
    assert turn["agent_review"]["status"] == "failed"


def test_memory_stays_open_while_the_agent_has_not_searched(store):
    script = Audit(search=False)
    loop = audit_loop(store, script)
    list(loop.run())
    assert loop.memory_locked is False


def test_with_the_answer_check_off_the_agent_answers_alone(store):
    script = Audit()
    loop = audit_loop(store, script, judges="off")
    list(loop.run())
    turn = saved(store, loop)
    assert turn["status"] == "completed" and turn["consensus"] == ANSWER
    assert [step for step, _ in script.calls] == ["completion:0"]
    assert "compare_models" not in loop.registry.tools and loop.comparison.auditor is None
    assert not (turn.get("agent_review") or {}).get("audit")
    assert AUDIT_OFF_PROMPT in loop.messages[0]["content"]


def test_without_the_setting_the_agent_keeps_its_comparison_tools(store):
    loop = audit_loop(store, Audit(), audit="off")
    assert {"compare_models", "check_text"} <= set(loop.registry.tools)
    assert loop.comparison.auditor is None and not loop.comparison.audit_mode
    assert prompt_defaults.AGENT_ANSWER_SECTION in loop.messages[0]["content"]
    assert prompt_defaults.AGENT_AUDIT_ANSWER_SECTION not in loop.messages[0]["content"]


# --- Prompts ----------------------------------------------------------------------

def test_the_audit_prompt_has_its_writing_reading_and_memory_rules(store, monkeypatch):
    from test_agent_memory import repo, set_profile
    monkeypatch.delenv("AGENT_READ_SOURCES", raising=False)
    set_profile(store.db, auto_memory=True)
    loop = audit_loop(store, Audit(), memory=repo(store).snapshot(UID), messages=[
        {"role": "system", "content": prompt_defaults.AGENT_AUDIT_SYSTEM_PROMPT}, {"role": "user", "content": "Hi"}])
    system = loop.messages[0]["content"]
    assert system.startswith(prompt_defaults.AGENT_AUDIT_SYSTEM_PROMPT)
    assert system.count("WRITING THE ANSWER") == 1 and "READING SOURCES" in system
    assert prompt_defaults.AGENT_AUDIT_READ_SOURCE_PROMPT.split("\n\n")[1][:60] in system
    # No comparison limit, no comparison memory field, no free-mode text.
    assert "comparisons per message" not in system and "compare_models and check_text carry" not in system
    assert "call update_memory first" in system and "FREE" not in system
    names = set(loop.registry.tools)
    assert {"read_source", "update_memory"} <= names and not {"compare_models", "check_text"} & names
    assert "Call it first" in loop.registry.tools["update_memory"].description
    assert "comparison answer" not in loop.registry.tools["read_source"].description


def test_every_memory_rule_without_comparisons_replaces_a_sentence_that_exists():
    texts = (agent_memory.MEMORY_USE_PROMPT, agent_memory.MEMORY_WRITE_PROMPT, agent_memory.MEMORY_READ_ONLY_PROMPT,
             agent_memory.MEMORY_PAUSED_PROMPT, agent_memory.MEMORY_UNAVAILABLE_PROMPT)
    # A changed memory prompt fails here, not silently in audit mode.
    for old, _ in agent_memory.NO_COMPARISON_REPLACEMENTS:
        assert any(old in text for text in texts), old
    for text in texts:
        adapted = agent_memory.without_comparisons(text)
        # Only the user's own comparisons (an example) may remain.
        assert "compar" not in adapted.replace("a comparison they asked for", "").lower(), adapted[:80]


def test_the_comparison_settings_say_nothing_in_audit_mode():
    assert preference_prompt(AgentPreferences(audit="on", depth="quick", autonomy="free")) == ""
    assert preference_prompt(AgentPreferences(audit="on", judges="off")) == AUDIT_OFF_PROMPT


# --- Reading reviews and placing quotes -------------------------------------------

def test_a_review_is_read_tolerantly_and_a_wrong_needs_a_source():
    text = "Here is my review:\n" + json.dumps({"marks": [
        {"quote": "A", "kind": "wrong", "note": "No source."},
        {"quote": "B", "kind": "FALSE", "note": "With one.", "source": ["ftp://x", "https://example.org/b"]},
        {"quote": "C", "kind": "unclear", "note": "Unknown kind."},
        {"quote": "", "kind": "doubtful", "note": "No quote."},
        {"quote": "D", "kind": "doubtful", "note": "Credentials.", "source": "https://user:pw@example.org"},
        {"quote": "D", "kind": "doubtful", "note": "Credentials.", "source": "https://user:pw@example.org"},
    ]}) + "\nThanks."
    assert parse_review(text) == [
        {"quote": "A", "kind": "doubtful", "note": "No source."},
        {"quote": "B", "kind": "wrong", "note": "With one.", "source": "https://example.org/b"},
        {"quote": "D", "kind": "doubtful", "note": "Credentials."}]
    for unreadable in ("No problems found.", '{"verdict": "fine"}', ""):
        with pytest.raises(agent_audit.ReviewUnreadable):
            parse_review(unreadable)
    marks = [{"quote": f"q{i}", "kind": "doubtful", "note": "n"} for i in range(50)]
    assert len(parse_review(json.dumps({"marks": marks}))) == agent_audit.MAX_MARKS


def test_a_mark_on_the_work_needs_an_entry_the_reviewer_has_read():
    text = json.dumps({"marks": [
        {"entry": 12, "kind": "doubtful", "note": "Known."},
        {"entry": "#13", "quote": "Q", "kind": "doubtful", "note": "Written with a hash."},
        {"entry": 99, "kind": "doubtful", "note": "Never read."},
        {"entry": True, "kind": "doubtful", "note": "Not a number."},
        {"entry": "12a", "kind": "doubtful", "note": "Not a number either."}]})
    assert parse_review(text, known={12, 13}) == [
        {"entry": 12, "kind": "doubtful", "note": "Known."},
        {"quote": "Q", "entry": 13, "kind": "doubtful", "note": "Written with a hash."}]
    # While the agent works there is no answer to quote.
    assert parse_review(text, known={12, 13}, final=False) == [
        {"entry": 12, "kind": "doubtful", "note": "Known."},
        {"entry": 13, "kind": "doubtful", "note": "Written with a hash."}]
    assert parse_review(json.dumps({"marks": [{"quote": "Q", "kind": "doubtful", "note": "n"}]}), final=False) == []


@pytest.mark.parametrize("quote,expected", [
    ("tickets to the top cost 14 euros", "Tickets to the top cost 14 euros."),
    ("“Gustave Eiffel did not design it alone”", "**Gustave Eiffel** did not design it alone"),
    ("according to the official site", "according to the [official site](https://www.toureiffel.paris/en)."),
    ("It was built ... World's Fair", "It was built in 1889 for the World's Fair."),
    ("Eiffel Tow", "Eiffel Tower"),
])
def test_a_quote_is_found_like_a_checked_passage(quote, expected):
    start, stop = locate_quote(ANSWER, quote)
    assert ANSWER[start:stop] == expected


def test_quotes_the_answer_does_not_hold_or_holds_twice_stay_unplaced():
    assert locate_quote(ANSWER, "The tower is made of glass") is None
    assert locate_quote(ANSWER, "is") is None
    # "Eiffel" stands twice: which one the reviewer meant is unknown.
    assert locate_quote(ANSWER, "Eiffel") is None
    claims, unplaced, process = place_marks("# Heading words here\n\nOne plain sentence stands here.", [
        ("OpenAI", [{"quote": "Heading words here", "kind": "doubtful", "note": "A heading."}], False)])
    assert claims == [] and process == [] and unplaced[0]["quote"] == "Heading words here"


def test_a_mark_on_the_work_names_its_entry_also_with_an_unplaced_quote():
    claims, unplaced, process = place_marks("One plain sentence stands here.", [
        ("OpenAI", [{"entry": 4, "kind": "doubtful", "note": "The step skipped the file."},
                    {"entry": 6, "quote": "Not in the answer", "kind": "incomplete", "note": "Missing."},
                    {"entry": 6, "quote": "One plain sentence", "kind": "doubtful", "note": "On the answer."}], True)],
        {4: ("step", "gpt-5.4-mini"), 6: ("tool", "read_source")})
    assert unplaced == []
    assert process == [
        {"model": "OpenAI", "kind": "doubtful", "note": "The step skipped the file.", "entry": 4, "mark": 1,
         "entry_kind": "step", "entry_name": "gpt-5.4-mini", "live": True},
        {"model": "OpenAI", "kind": "incomplete", "note": "Missing.", "entry": 6, "mark": 2,
         "quote": "Not in the answer", "entry_kind": "tool", "entry_name": "read_source", "live": True}]
    # A quote the answer holds marks its sentence, with the entry it came from.
    [claim] = claims
    assert claim["anchor"] == "One plain sentence stands here." and claim["dissent"][0]["entry"] == 6


def test_a_mark_over_up_to_three_sentences_is_one_mark_and_longer_quotes_stay_unplaced():
    text = " ".join(f"Sentence number {n} says something." for n in range(1, 7))
    two = "Sentence number 2 says something. Sentence number 3"
    claims, unplaced, _ = place_marks(text, [("OpenAI", [
        {"quote": two, "kind": "doubtful", "note": "Two sentences."},
        {"quote": text, "kind": "doubtful", "note": "All of it."},
        {"quote": "Sentence number 1 ... number 5 says something.", "kind": "wrong", "note": "Five."}], False)])
    assert [(c["anchor"], [d["mark"] for d in c["dissent"]]) for c in claims] == [
        ("Sentence number 2 says something.", [1]), ("Sentence number 3 says something.", [1])]
    assert [(item["mark"], item["note"]) for item in unplaced] == [(2, "All of it."), (3, "Five.")]


@pytest.mark.parametrize("value,expected", [
    ("https://en.wikipedia.org/wiki/Mercury_(planet)", "https://en.wikipedia.org/wiki/Mercury_(planet)"),
    ("(https://en.wikipedia.org/wiki/Mercury_(planet))", "https://en.wikipedia.org/wiki/Mercury_(planet)"),
    ("[Wikipedia](https://en.wikipedia.org/wiki/Mercury_(planet))", "https://en.wikipedia.org/wiki/Mercury_(planet)"),
    ("<https://example.org/a>", "https://example.org/a"),
    ("\"https://example.org/a\"", "https://example.org/a"),
    ("https://example.org/a)", "https://example.org/a"),
    ("see https://example.org/a", None),
    ("ftp://example.org/a", None),
])
def test_a_source_is_read_with_its_own_parentheses(value, expected):
    assert agent_audit.source_url(value) == expected


def test_over_the_storage_budget_marks_keep_their_sentences_with_shorter_notes():
    audit = {"claims": [{"anchor": "A.", "dissent": [{"model": "OpenAI", "kind": "doubtful", "note": "n" * 600,
                                                      "target": "A", "mark": 1}]}],
             "unplaced": [{"model": "OpenAI", "kind": "doubtful", "note": "x", "quote": "q" * 400, "mark": 2}],
             "process": [{"model": "OpenAI", "kind": "doubtful", "note": "p" * 600, "entry": 3, "mark": 3}]}
    agent_audit.trim_marks(audit)
    [item] = audit["claims"][0]["dissent"]
    assert "target" not in item and len(item["note"]) == agent_audit.TRIMMED_NOTE_CHARS and item["mark"] == 1
    assert len(audit["unplaced"][0]["quote"]) == 200
    assert len(audit["process"][0]["note"]) == agent_audit.TRIMMED_NOTE_CHARS and audit["process"][0]["entry"] == 3


# --- What a reviewer reads ----------------------------------------------------------

def test_a_log_entry_is_read_structured_and_shortened():
    step = {"seq": 4, "actor": "agent", "kind": "step", "name": "m", "data": "agent", "format": "json"}
    content = json.dumps({"text": "t" * 500, "tool_calls": [], "usage": {"cost": 1}})
    assert review_entry(step, content, 300) == {
        "seq": 4, "actor": "agent", "kind": "step", "name": "m", "data": "agent",
        "content": {"text": "t" * 150 + "\n… [shortened: 500 characters in total]", "tool_calls": []}}
    # The agent's instructions (with the user's memory at their end) are read whole up to their own limit.
    system = {"seq": 2, "actor": "agent", "kind": "context", "name": "system", "data": "app", "format": "text"}
    assert review_entry(system, "s" * 20_000)["content"] == "s" * 20_000
    assert review_entry({**system, "name": "user"}, "s" * 20_000)["content"].endswith("[shortened: 20000 characters in total]")
    broken = {**step, "format": "json"}
    assert review_entry(broken, "{not json")["content"] == "{not json"


def test_a_round_message_carries_new_entries_and_in_the_end_the_answer():
    entries = [({"seq": 1, "actor": "app", "kind": "start", "data": "app", "format": "text"}, "x" * 3000)]
    live = round_message(2, entries)
    assert live.startswith("Round 2.") and "The fixed answer" not in live
    assert round_entries({"content": live}) == ([{"seq": 1, "actor": "app", "kind": "start", "data": "app",
                                                  "content": "x" * 3000}], None)
    # A round without room reads its entries shorter, or not at all.
    tight, _ = round_entries({"content": agent_audit.fitted_round(3, entries, 2500)})
    assert tight[0]["content"].startswith("x" * agent_audit.TIGHT_ENTRY_CHARS + "\n… [shortened")
    assert agent_audit.fitted_round(3, entries, 200) is None
    final = round_message(3, [], answer="The answer.")
    assert final.startswith("Final round.") and round_entries({"content": final}) == ([], "The answer.")


def test_only_a_step_that_calls_a_tool_starts_a_live_round():
    def step(content, kind="step"):
        return ({"kind": kind}, content)
    assert work_goes_on([step(json.dumps({"tool_calls": [{"name": "read_source"}]}))])
    assert not work_goes_on([step(json.dumps({"tool_calls": [], "text": "The answer."}))])
    assert not work_goes_on([step(json.dumps({"tool_calls": [{"name": "x"}]}), kind="tool"), step("not json")])
    assert not work_goes_on([])


# --- The route ---------------------------------------------------------------------

@pytest.mark.parametrize("admin", [True, False])
def test_only_an_admins_message_runs_in_audit_mode(api, monkeypatch, admin):
    from app.api.routers import agent
    client, store, calls = api
    monkeypatch.setattr(agent, "is_user_admin", lambda uid: admin)
    chat_id = store.create_chat(UID, execution_mode="agent")["id"]
    payload = {"chat_id": chat_id, "question": "Hi", "client_request_id": "r1", "bookmark_id": "bm1",
               "agent_preferences": {"audit": "on"}}
    response = client.post("/agent", json=payload, headers=AUTH)
    assert response.status_code == 200, response.text
    turn = next(t for t in store.list_turns(UID, chat_id)["turns"] if t["question"] == "Hi")
    settings = store.get_turn(UID, chat_id, turn["id"])["agent_settings"]
    assert settings["agent_preferences"]["audit"] == ("on" if admin else "off")
    first = calls[0]
    names = {tool["function"]["name"] for tool in first.get("tools") or [] if tool.get("type") == "function"}
    system = first["messages"][0]["content"]
    if admin:
        assert system.startswith(prompt_defaults.AGENT_AUDIT_SYSTEM_PROMPT) and "compare_models" not in names
        # The fake model's reply is no review: the reviewers lose their marks, the answer stands.
        assert store.get_turn(UID, chat_id, turn["id"])["status"] == "completed"
    else:
        assert "COMPARE OR ANSWER DIRECTLY" in system and "compare_models" in names
    # The same request again is the same message, with the same effective settings.
    assert client.post("/agent", json=payload, headers=AUTH).status_code == 200

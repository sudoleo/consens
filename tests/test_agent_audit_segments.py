"""A reviewer's conversation grows by appending only, up to its cap, then
goes on in a new one that carries what it needs of the old
(agent_audit.ReviewerSession._carry): every request stays bounded and a
run's reviews cost linearly in its length. Played without a model or a run:
a work log, one reviewer session and a scripted provider."""
import json
import threading
from types import SimpleNamespace

import pytest

from app.services import agent_audit
from app.services.agent_work_log import WorkLog
from test_agent_runs import store  # noqa: F401  (fixture)
from test_agent_work_log import LogStore

MODEL = SimpleNamespace(model="anthropic/claude-haiku-5.5", label="Claude Haiku 5.5", context_length=200_000,
                        max_output_tokens=16_000, settings=lambda: {})
OUTPUT = "x" * 5_000


class Provider:
    """The reviewer's requests: what each sent, its round, its OpenRouter
    session; ``replies``: a reply (text, exception or callable) per request
    number, else no marks."""

    def __init__(self, replies=None):
        self.replies = dict(replies or {})
        self.sent, self.lock = [], threading.Lock()

    def worker_request(self, worker, model, messages, *, cancellation, slots, review_round=None, **kwargs):
        with self.lock:
            number = len(self.sent)
            self.sent.append({"chars": sum(len(m["content"]) for m in messages), "round": review_round,
                              "session": worker.session_key or worker.id, "messages": list(messages)})
        reply = self.replies.get(number, json.dumps({"marks": []}))
        if callable(reply):
            reply = reply(messages)
        if isinstance(reply, BaseException):
            raise reply
        return SimpleNamespace(text=reply, sources=[], finish_reason="stop",
                               assistant_message=lambda: {"role": "assistant", "content": reply,
                                                          "reasoning_details": [{"type": "reasoning.text",
                                                                                 "text": "t" * 4_000}]})


def reviewer(provider, *, brief=None):
    """One reviewer session on a work log of its own, its halts recorded."""
    log = WorkLog(LogStore(), "u", "c", "t", ready=lambda: False, sleep=lambda seconds: None)
    loop = SimpleNamespace(_publish=lambda *a, **k: None, _state=lambda worker, state, **k: setattr(worker, "state", state),
                           _terminal=lambda worker, state, *a: setattr(worker, "state", state),
                           _hard_stop_left=lambda: None, policy=SimpleNamespace(result_chars=1000),
                           cancellation=SimpleNamespace(cancelled=False))
    tools = SimpleNamespace(loop=loop, lock=threading.RLock(), worker_request=provider.worker_request)
    halts = []
    audit = SimpleNamespace(tools=tools, work_log=log, brief=lambda: brief, final_answer=None,
                            slots=threading.BoundedSemaphore(3), file_ids=[], reviewers={"anthropic": {}},
                            halt=lambda session, halt: halts.append(halt))
    session = agent_audit.ReviewerSession(audit, "anthropic", MODEL)
    session.halted = halts
    return session, log


def opening(log, question="Build the site and keep me posted."):
    log.add("start", content={"question": question})
    log.add("context", actor="agent", name="system", content="The app's instructions. " * 50)
    log.add("context", actor="agent", name="user", data="user", content=question)


def work(log, step):
    """One step of the agent: a command, and its output."""
    log.add("step", actor="agent", name="m", data="agent", step=f"completion:{step}", content={
        "text": f"Step {step}.", "tool_calls": [{"id": f"c{step}", "name": "vm_exec",
                                                 "arguments": json.dumps({"command": f"make step-{step}"})}]})
    log.add("tool", actor="agent", name="vm_exec", data="vm", step=f"completion:{step}",
            content=json.dumps({"exit_code": 0, "stdout": OUTPUT}))


def follow(session, log, steps, *, start=0, each=None):
    for step in range(start, start + steps):
        work(log, step)
        if each:
            each(step)
        session._round(log.entries_after(session.cursor))


def test_two_hundred_steps_keep_every_request_under_its_cap_and_the_cost_linear():
    provider = Provider()
    session, log = reviewer(provider)
    opening(log)
    follow(session, log, 100)
    first_half = sum(request["chars"] for request in provider.sent)
    follow(session, log, 100, start=100)
    sizes = [request["chars"] for request in provider.sent]
    assert len(sizes) == 200 and session.live_rounds == 200
    # Bounded: no request ever sends more than the conversation's cap,
    # whatever the run's length (before, ~100k tokens and quadratic).
    assert max(sizes) <= session.segment_cap == agent_audit.SEGMENT_CHARS
    assert max(sizes[150:]) <= session.segment_cap
    # Linear: the second hundred steps cost about what the first did.
    second_half = sum(sizes) - first_half
    assert .8 < second_half / first_half < 1.25
    assert session.fresh >= 10
    # Each new conversation started small: its carry, then only new entries.
    starts = [request for request in provider.sent if len(request["messages"]) == 2]
    assert len(starts) == session.fresh + 1
    assert all(request["chars"] < session.segment_cap * .7 for request in starts)
    log.close(0)


def test_the_final_round_after_a_long_run_stays_bounded_with_the_answers_sources():
    provider = Provider()
    session, log = reviewer(provider)
    opening(log)
    url = "https://example.org/rules"

    def search(step):
        if step == 3:
            # A search hit early in the run: long gone from the conversation by its end.
            log.add("step", actor="agent", name="m", data="agent", step="completion:x", content={
                "text": "", "tool_calls": [], "search_excerpts": [{"url": url, "content": "Rule 7 allows it."}]})
    follow(session, log, 120, each=search)
    answer = f"Done. See [the rules]({url}) and https://unknown.example/page."
    log.app("answer_fixed", {"chars": len(answer)})
    session.audit.final_answer = answer
    session._final(answer)
    final = provider.sent[-1]
    assert final["round"] == "final"
    assert final["chars"] <= session.segment_cap + agent_audit.FINAL_REST_CHARS + len(answer) + 1_000
    message = final["messages"][-1]["content"]
    sections = dict(part.split("\n", 1) for part in message.split("\n\n"))
    [cited] = json.loads(sections[agent_audit.SOURCES_HEAD])["sources"]
    assert cited["url"] == url and "Rule 7 allows it." in cited["evidence"] and cited["entries"]
    assert json.loads(sections["The fixed answer:"]) == {"answer": answer}
    log.close(0)


def test_a_new_conversation_carries_what_the_reviewer_needs_of_the_old_one():
    marks = {7: json.dumps({"marks": [{"entry": 9, "kind": "doubtful", "note": "Step 3 skipped the tests."}]})}
    provider = Provider(marks)
    brief = {"seq": 2, "content": {"instructions": "The app's instructions, summed up.", "tools": {}, "memory": ""}}
    session, log = reviewer(provider, brief=brief)
    opening(log, "Translate the README.")
    session.halts.append({"entry": 6, "kind": "safety", "reason": "Deletes the backups."})

    def events(step):
        if step == 2:
            log.add("context", actor="agent", name="user", data="user",
                    content="[The user wrote this while you were working; it comes from the user:]\nOnly German.")
            log.app("paused", "The work was paused for the user's decision.")
            log.app("decision", "The user let the work go on.")
    follow(session, log, 12, each=events)
    session.chars = session.segment_cap
    follow(session, log, 1, start=12)
    carried = provider.sent[-1]["messages"]
    assert len(carried) == 2
    sections = dict(part.split("\n", 1) for part in carried[1]["content"].split("\n\n"))
    head = next(key for key in sections if key.startswith("Round 13."))
    assert agent_audit.CARRY_HEAD in head and "beginning of the work log" in head
    beginning = json.loads(sections[head])["entries"]
    assert [e["kind"] for e in beginning] == ["start", "context", "context"]
    assert beginning[1]["content"] == brief["content"] and beginning[2]["content"] == "Translate the README."
    notes = json.loads(sections["The user's messages into the run, since its beginning:"])["entries"]
    assert [note["content"].endswith("Only German.") for note in notes] == [True]
    decisions = json.loads(sections["The app's entries of the user's decisions and the run's limits:"])["entries"]
    assert [entry["name"] for entry in decisions] == ["paused", "decision"]
    lines = json.loads(sections["The work log you read since its beginning, one line per entry:"])["lines"]
    assert len(lines) == session.cursor - 3 - 2
    assert any(line.endswith("vm_exec: make step-4 · “Step 4.”") for line in lines)
    assert json.loads(sections["Your marks from the earlier rounds:"])["marks"] == [
        {"entry": 9, "kind": "doubtful", "note": "Step 3 skipped the tests."}]
    assert json.loads(sections["Your halts from the earlier rounds:"])["halts"] == session.halts
    new = json.loads(sections[agent_audit.NEW_LIVE])["entries"]
    assert [e["seq"] for e in new] == list(range(session.segment_from, session.cursor + 1))
    log.close(0)


def test_the_carried_lines_stay_within_their_room_however_long_the_run():
    entries = [({"seq": seq, "actor": "agent", "kind": "tool", "name": "vm_exec", "data": "vm"},
                json.dumps({"stdout": "line " * 100})) for seq in range(1, 2001)]
    lines = agent_audit.carried_lines(entries, 16_000)
    assert len(agent_audit._dumps(lines)) <= 16_000
    assert lines[0].startswith("#1 to #") and "tool results" in lines[0]
    assert lines[-1].startswith("#2000 agent tool vm_exec (vm): line line")
    assert any(line == "#1800 agent tool vm_exec" for line in lines)


def test_a_new_conversation_is_priced_without_the_old_ones_cache():
    """Its requests go on on the same OpenRouter session, but the first
    finds only the instructions in the cache: the admission's estimate
    forgets the cached prefix of the conversation before (RunCosts.rewritten)."""
    from app.services.agent_costs import RunCosts
    provider = Provider()
    session, log = reviewer(provider)
    costs = session.loop.costs = RunCosts(SimpleNamespace(account_budget_only=True))
    forgotten = []
    costs.rewritten = lambda key: (forgotten.append(key), RunCosts.rewritten(costs, key))
    opening(log)
    follow(session, log, 60)
    keys = {request["session"] for request in provider.sent}
    assert session.fresh >= 2 and len(keys) == 1
    assert forgotten == [session.conversation_key] * session.fresh
    log.close(0)


def test_a_failed_round_keeps_the_conversation_and_its_endpoint_and_replays_no_reasoning():
    provider = Provider({1: RuntimeError("provider down")})
    session, log = reviewer(provider)
    opening(log)
    follow(session, log, 1)
    key, kept = session.conversation_key, list(session.messages)
    follow(session, log, 1, start=1)
    # The failed round cost only itself: the conversation as it was, on the
    # same OpenRouter session, so the next round reads it from the cache.
    assert session.messages == kept and session.conversation_key == key and session.tried > session.cursor
    follow(session, log, 1, start=2)
    assert [request["session"] for request in provider.sent] == [key] * 3
    assert provider.sent[2]["messages"][:3] == kept
    # A reply goes on as its text: the reasoning that came with it is not sent again.
    assert all(set(message) == {"role", "content"} for message in session.messages)
    # Two failures in a row leave that endpoint.
    provider.replies.update({3: RuntimeError("down"), 4: RuntimeError("down")})
    follow(session, log, 2, start=3)
    assert session.failures == 2 and session.conversation_key is None
    log.close(0)


@pytest.mark.parametrize("quote,stops", [
    ("make step-0", True), ("MAKE   step-0", True), ("rm -rf ~", False), ("", False)])
def test_a_halt_stops_the_work_only_with_its_evidence(quote, stops):
    """All 13 halts in Prod ended with the user's Continue. A halt counts
    only where its entry holds the words it quotes; else it is a mark."""
    step = {"seq": 4, "kind": "step"}
    content = json.dumps({"tool_calls": [{"name": "vm_exec", "arguments": json.dumps({"command": "make step-0"})}]})
    assert agent_audit.quote_found(quote, step, content) is stops


def test_an_escaped_quote_is_found_as_the_reviewer_read_it():
    entry = {"seq": 5, "kind": "tool"}
    content = json.dumps({"stdout": 'Say "yes"\nthen run it'})
    assert agent_audit.quote_found('Say \\"yes\\"\\nthen run it', entry, content)


def test_a_reviewer_reads_no_other_reviewers_finding_in_the_log(store):
    from test_agent_audit import Audit, audit_loop, halting_live, decide_when_held
    script = Audit(tool_steps=2, live={"anthropic": halting_live})
    loop = audit_loop(store, script)
    waiter = decide_when_held(loop, store, "continue")
    list(loop.run())
    waiter.join(5)
    from test_agent_audit import HALT_REASON
    said = json.dumps(script.prompts["openai"][1:])
    assert "The work was paused for the user's decision." in said and "The user let the work go on." in said
    assert HALT_REASON not in said and "paused the work for the user" not in said


def test_the_reviewers_charge_per_step_follows_its_recent_steps(store):
    from test_agent_audit import Audit, audit_loop
    from app.services import agent_delegation
    loop = audit_loop(store, Audit())
    for step, charge in enumerate([10, 10, 10, 10, 80, 20, 20]):
        loop.routing_steps = step
        loop.reviewer_charges[step] = charge
    assert loop._reviewer_step_charge() == 80
    loop.routing_steps = 4 + agent_delegation.REVIEWER_CHARGE_STEPS + 1
    assert loop._reviewer_step_charge() == 20

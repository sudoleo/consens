"""The reviewers' findings back to the agent (agent_review_feedback.py), the
account's ``findings_to_agent``: off, the review is what it always was; on,
hard findings reach the agent while it works, the reviewed answer gets one
correction pass, and what stays open goes with the next message."""
import json
import time

import pytest

from app.services import agent_audit_metrics, agent_review_feedback as fb, prompt_defaults, user_settings
from app.services.agent_comparison import AgentPreferences, comparison_selection
from app.services.agent_delegation import DelegationLoop
from app.services.agent_delegation_config import defaults
from app.services.agent_policy import AgentPolicy
from app.services.agent_tools import ToolRegistry
from app.services.llm.agent_client import resolve_agent_model
from app.services.llm.provider_runtime import ProviderCancellation
from test_agent_audit import ANSWER, RATES, Audit, lookup, round_entries, saved
from test_agent_runs import AUTH, UID, api, pending, store  # noqa: F401  (fixtures)

TICKETS = "Tickets to the top cost 14 euros."
FIXED = "Tickets to the top cost 36.10 euros."


@pytest.fixture(autouse=True)
def _admin_allowance(monkeypatch):
    from app.services import agent_budget_config
    monkeypatch.setitem(agent_budget_config.DEFAULT_TIER_LIMITS, "pro", 5_000_000)


def feedback_loop(store, script, *, findings=True, reviewers="always"):
    """test_agent_audit.audit_loop with the account's findings_to_agent."""
    chat, turn = pending(store)
    config = {**defaults(), "enabled": False, "max_searches": 0}
    loop = DelegationLoop(store=store, uid=UID, chat_id=chat, turn_id=turn["id"],
        model=resolve_agent_model("claude-haiku-4-5"),
        messages=[{"role": "system", "content": "Answer."},
                  {"role": "user", "content": "Tell me about the Eiffel Tower."}],
        api_key="test", cancellation=ProviderCancellation(), policy=AgentPolicy.for_chat(config),
        delegation_config=config, completion_factory=script.factory,
        comparison_models=comparison_selection({"anthropic": "claude-haiku-4-5", "openai": "gpt-6-luna"}),
        agent_preferences=AgentPreferences(), reviewers=reviewers, findings_to_agent=findings)
    if script.tool_steps:
        loop.registry = ToolRegistry([*loop.registry.tools.values(), lookup(script)],
                                     argument_limit=loop.registry.argument_limit)
    script.loop = loop
    return loop


def correction_request(messages):
    last = messages[-1]["content"] if messages and isinstance(messages[-1].get("content"), str) else ""
    if not last.startswith("[consens.io, written by the app: the reviewers' findings on your answer"):
        return None
    body = last.split("\n", 1)[1].split("\n\nFor each finding", 1)[0]
    return json.loads(body)["findings"]


def agent_side(reply):
    """The agent model's helper replies (the agent is on Anthropic, like
    one reviewer): ``reply(findings)`` for the correction request, no marks
    for the reviewer's own live rounds."""
    def answer(messages):
        asked = correction_request(messages)
        return json.dumps({"marks": []}) if asked is None else reply(asked)
    return answer


def log_entries(store, loop, name):
    """The app's entries ``name`` of the run's work log, their content read."""
    found = []
    for entry in store.read_work_log(UID, loop.chat_id, loop.turn_id, limit=500)["entries"]:
        if entry.get("kind") == "app" and entry.get("name") == name:
            content = entry.get("content")
            found.append({**entry, "content": json.loads(content) if isinstance(content, str) else content})
    return found


# --- Off: the review as it always was -----------------------------------------

def test_off_is_the_review_as_it_was(store):
    script = Audit()
    loop = feedback_loop(store, script, findings=False)
    list(loop.run())
    turn = saved(store, loop)
    review = turn["agent_review"]
    dumped = json.dumps(review)
    # No register, no finding on any mark, no way back to the agent.
    assert "feedback" not in review["audit"] and '"finding"' not in dumped
    assert set(loop.app_registry.tools) == {"audit_answer"}
    assert turn["assistant_response"] == ANSWER and len(review["versions"]) == 1
    system = loop.messages[0]["content"]
    assert prompt_defaults.AGENT_REVIEW_FACTS["always"] in system and fb.MARKS_SHARED not in system
    assert not any(fb.FINDINGS_OPEN in str(m.get("content")) for m in loop.messages)
    assert not log_entries(store, loop, "findings_delivered") and not log_entries(store, loop, "answer_corrected")
    chat = store._chat_ref(UID, loop.chat_id).get().to_dict()
    assert "agent_open_findings" not in chat and "agent_correcting" not in turn
    assert "findings" not in agent_audit_metrics.capture(loop)
    # No correction request went to the agent's model.
    assert not any(correction_request(m) for m in [script.prompts.get("anthropic") or []])


def test_on_changes_only_the_reviewers_sentence_about_their_marks():
    assert fb.review_facts(prompt_defaults.AGENT_REVIEW_FACTS, "off", prompt_defaults._REVIEW_MARKS) \
        == prompt_defaults.AGENT_REVIEW_FACTS["off"]
    for setting in ("always", "workspace"):
        fact = fb.review_facts(prompt_defaults.AGENT_REVIEW_FACTS, setting, prompt_defaults._REVIEW_MARKS)
        assert fb.MARKS_SHARED in fact and prompt_defaults._REVIEW_MARKS not in fact
        assert fact.replace(fb.MARKS_SHARED, prompt_defaults._REVIEW_MARKS) == prompt_defaults.AGENT_REVIEW_FACTS[setting]


def test_the_setting_is_a_switch_and_off_by_default():
    assert user_settings.validate_changes({"findings_to_agent": True}) == ({"findings_to_agent": True}, [])
    assert user_settings.validate_changes({"findings_to_agent": None}) == ({"findings_to_agent": None}, [])
    assert user_settings.validate_changes({"findings_to_agent": "yes"}) == ({}, ["findings_to_agent"])
    assert user_settings.UserSettings().findings_to_agent is None


def test_without_reviewers_nothing_reaches_the_agent(store):
    loop = feedback_loop(store, Audit(), findings=True, reviewers="off")
    assert loop.findings_to_agent is False and loop.comparison.auditor.feedback is None


# --- The register -------------------------------------------------------------

def test_a_finding_is_hard_when_called_wrong_or_marked_twice():
    register = fb.Findings()
    register.live("Claude", [{"entry": 3, "kind": "doubtful", "note": "Maybe outdated."}])
    assert register.take_live() == []
    # The same reviewer again is no second voice.
    register.live("Claude", [{"entry": 3, "kind": "incomplete", "note": "Something is missing."}])
    assert register.take_live() == []
    register.live("GPT", [{"entry": 3, "kind": "doubtful", "note": "Unsupported."}])
    [found] = register.take_live()
    assert found["id"] == "e3" and found["reviewers"] == 2 and found["kind"] == "doubtful"
    register.live("GPT", [{"entry": 5, "kind": "wrong", "note": "False.", "source": RATES}])
    [wrong] = register.take_live()
    assert wrong["id"] == "e5" and wrong["notes"][0]["source"] == RATES
    # Each finding once.
    register.live("Claude", [{"entry": 5, "kind": "wrong", "note": "Still false.", "source": RATES}])
    assert register.take_live() == []


def test_live_findings_stop_at_the_limit_and_count_the_rest():
    register = fb.Findings()
    for entry in range(1, fb.LIVE_FINDINGS + 3):
        register.live("GPT", [{"entry": entry, "kind": "wrong", "note": "False.", "source": RATES}])
    assert len(register.take_live()) == fb.LIVE_FINDINGS
    assert register.take_live() == []
    assert register.counts == {"delivered": fb.LIVE_FINDINGS, "corrected": 0, "disputed": 0, "cut": 2}


def test_marks_on_one_sentence_are_one_finding_with_their_voices():
    from app.services.agent_audit import place_marks
    reviews = [("Claude", [{"quote": "Tickets to the top cost 14 euros", "kind": "wrong", "note": "36.10.",
                            "source": RATES}], False),
               ("GPT", [{"quote": "cost 14 euros", "kind": "doubtful", "note": "Too low."},
                        {"quote": "built in 1889", "kind": "doubtful", "note": "Check the year."}], False)]
    claims, unplaced, process = place_marks(ANSWER, reviews)
    register = fb.Findings()
    register.placed(claims, process)
    register.annotate(claims, unplaced, process)
    findings = {f["id"]: f for f in register.snapshot()["findings"]}
    tickets = next(f for f in findings.values() if f["voices"] == 2)
    assert tickets["kind"] == "wrong" and tickets["hard"] and tickets["on"] == "answer"
    year = next(f for f in findings.values() if f["voices"] == 1)
    assert not year["hard"]
    assert all(item.get("finding") for claim in claims for item in claim["dissent"])


def test_the_correction_replaces_only_its_sentences():
    finding = {"id": "s1", "sentences": None}
    spans = fb.sentence_spans(ANSWER)
    number = next(i for i, (start, end) in enumerate(spans, 1) if "Tickets" in ANSWER[start:end])
    finding["sentences"] = [number]
    items = fb.correction_items(ANSWER, [finding])
    assert items["s1"][2].startswith("Tickets to the top cost 14 euros")
    results = fb.read_corrections(json.dumps({"findings": [{"id": "s1", "sentence": FIXED}]}), items)
    text = fb.corrected_answer(ANSWER, items, results)
    assert text == ANSWER.replace(items["s1"][2], FIXED)
    # A reply that is no sentence any more, or an unknown id, changes nothing.
    assert fb.read_corrections(json.dumps({"findings": [{"id": "s1", "sentence": "a\n\nb"}]}), items) == {}
    assert fb.read_corrections(json.dumps({"findings": [{"id": "s9", "sentence": FIXED}]}), items) == {}
    assert fb.read_corrections("not json", items) == {}
    assert fb.read_corrections(json.dumps({"findings": [{"id": "s1", "stands": "The site says 14."}]}), items) \
        == {"s1": ("disputed", "The site says 14.")}


def test_the_next_message_carries_the_most_severe_open_findings_as_data():
    saved_findings = {"turn_id": "t1", "total": 7, "findings": [
        {"on": "answer", "kind": "wrong", "reviewers": 2, "quote": "q", "note": "n", "source": RATES}] * 5}
    text = fb.open_findings_context(saved_findings)
    assert text.startswith(fb.CONTEXT_OPEN) and "2 further open findings" in text
    assert json.loads(text.split("\n")[1])[0]["source"] == RATES
    assert fb.open_findings_context({"findings": []}) == "" and fb.open_findings_context(None) == ""


# --- While the agent works ---------------------------------------------------

def test_a_hard_finding_reaches_the_agent_before_its_next_step_once(store):
    def flag(messages):
        if correction_request(messages) is not None:
            return json.dumps({"findings": []})
        user = [m for m in messages if m["role"] == "user"]
        entries, _ = round_entries(user[-1])
        steps = [e["seq"] for e in entries or [] if e["kind"] == "step"]
        marks = [{"entry": steps[-1], "kind": "doubtful", "note": "The lookup asked the wrong thing."}] if steps else []
        return json.dumps({"marks": marks})

    def both_marked(_):
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            register = script.loop.comparison.auditor.feedback
            if any(f["hard"] for f in register.findings.values()):
                return
            time.sleep(.01)

    script = Audit(tool_steps=2, live={"anthropic": flag, "openai": flag}, on_lookup=both_marked)
    loop = feedback_loop(store, script)
    events = list(loop.run())
    delivered = [m for m in loop.messages if m["role"] == "user" and str(m["content"]).startswith(fb.FINDINGS_OPEN)]
    assert len(delivered) >= 1
    sent = json.loads(delivered[0]["content"].split("\n", 1)[1])
    assert sent[0]["reviewers"] == 2 and sent[0]["kind"] == "doubtful" and "id" not in sent[0]
    # Each finding once, at most LIVE_FINDINGS in the run.
    total = sum(len(json.loads(m["content"].split("\n", 1)[1])) for m in delivered)
    assert total <= fb.LIVE_FINDINGS
    logged = log_entries(store, loop, "findings_delivered")
    assert logged and logged[0]["content"]["phase"] == "work"
    assert any(e.get("text") in fb.FINDINGS_PASSED.values() for e in events if e.get("kind") == "progress")
    review = saved(store, loop)["agent_review"]
    assert any(f.get("delivered") == "live" for f in review["audit"]["feedback"]["findings"])


# --- After the answer -------------------------------------------------------

def test_the_agent_corrects_a_hard_finding_once_and_the_first_version_stays(store):
    asked = []

    def correct(findings):
        asked.append(findings)
        return json.dumps({"findings": [{"id": item["id"], "sentence": FIXED} for item in findings
                                        if "Tickets" in item["sentence"]]})

    script = Audit(live={"anthropic": agent_side(correct)})
    loop = feedback_loop(store, script)
    events = list(loop.run())
    turn = saved(store, loop)
    review = turn["agent_review"]
    # One pass with every finding on the answer, the hard one (wrong with a source, two voices) first.
    assert len(asked) == 1 and asked[0][0]["kind"] == "wrong"
    assert asked[0][0]["sentence"].startswith("Tickets to the top cost 14 euros")
    corrected = ANSWER.replace("Tickets to the top cost 14 euros.", FIXED)
    assert turn["assistant_response"] == corrected and loop.completion.text == corrected
    assert [v["text"] for v in review["versions"]] == [ANSWER, corrected]
    assert review["answer_version"] == 2 and review["versions"][1]["corrects"] == 1
    feedback = review["audit"]["feedback"]
    fixed = next(f for f in feedback["findings"] if f["state"] == "corrected" and "Tickets" in f["before"])
    assert fixed["after"] == FIXED and fixed["before"].startswith("Tickets to the top cost 14 euros")
    assert feedback["status"] == "done"
    # The improved sentence carries no mark.
    assert not any(i.get("finding") == fixed["id"] for c in review["audit"]["claims"] for i in c["dissent"])
    # The reviewers did not review the correction.
    assert script.rounds["openai"].count("final") == 1
    # The log and the activity say so; the next message gets the open ones.
    assert log_entries(store, loop, "findings_delivered")[0]["content"]["phase"] == "answer"
    assert log_entries(store, loop, "answer_corrected")[0]["content"]["findings"][0]["state"] == "corrected"
    assert any(e.get("tool") == "correct_answer" or "correct_answer" in json.dumps(e) for e in events)
    chat = store._chat_ref(UID, loop.chat_id).get().to_dict()
    assert chat["agent_open_findings"]["turn_id"] == loop.turn_id
    assert all(item["kind"] != "wrong" for item in chat["agent_open_findings"]["findings"])
    assert "agent_correcting" not in turn
    counted = agent_audit_metrics.turn_counters(turn, agent_audit_metrics.capture(loop))
    assert counted["findings_to_agent"]["corrected"] == 1
    assert counted["findings_to_agent"]["delivered"] == len(asked[0])


def test_the_agent_may_say_why_a_sentence_stands(store):
    def dispute(findings):
        return json.dumps({"findings": [{"id": item["id"], "stands": "The official site lists 14 euros."}
                                        for item in findings]})

    script = Audit(live={"anthropic": agent_side(dispute)})
    loop = feedback_loop(store, script)
    list(loop.run())
    turn = saved(store, loop)
    review = turn["agent_review"]
    assert turn["assistant_response"] == ANSWER and len(review["versions"]) == 1
    disputed = next(f for f in review["audit"]["feedback"]["findings"] if f["state"] == "disputed")
    assert disputed["reason"] == "The official site lists 14 euros."
    states = {f["state"] for f in review["audit"]["feedback"]["findings"] if f["on"] == "answer"}
    assert states == {"disputed"}
    # A disputed finding keeps its mark: real disagreement the reader sees.
    marked = {item["finding"] for claim in review["audit"]["claims"] for item in claim["dissent"]}
    assert disputed["id"] in marked


def test_without_findings_no_correction_runs(store):
    reviews = {"anthropic": json.dumps({"marks": []}), "openai": json.dumps({"marks": []})}
    asked = []
    script = Audit(reviews, live={"anthropic": agent_side(lambda f: asked.append(f) or "{}")})
    loop = feedback_loop(store, script)
    events = list(loop.run())
    assert asked == [] and not any("correct_answer" in json.dumps(e) for e in events)
    turn = saved(store, loop)
    assert turn["assistant_response"] == ANSWER and turn["agent_review"]["audit"]["feedback"]["status"] == "done"
    assert "agent_open_findings" not in store._chat_ref(UID, loop.chat_id).get().to_dict()


def test_every_finding_on_the_answer_goes_to_the_one_pass_and_only_what_stays_open_keeps_a_mark(store):
    """No mark shows what the agent corrected; a finding it disputes keeps its
    mark with its reason, one it did not settle keeps its mark as before."""
    def settle(findings):
        replies = []
        for item in findings:
            if "Tickets" in item["sentence"]:
                replies.append({"id": item["id"], "sentence": FIXED})
            elif "Gustave" in item["sentence"]:
                replies.append({"id": item["id"], "stands": "Sauvestre shaped the design, not the plans."})
        return json.dumps({"findings": replies})

    asked = []
    script = Audit(live={"anthropic": agent_side(lambda f: asked.append(f) or settle(f))})
    loop = feedback_loop(store, script)
    list(loop.run())
    review = saved(store, loop)["agent_review"]
    # The soft findings went too, the most severe first.
    assert len(asked) == 1 and len(asked[0]) == 3 and asked[0][0]["kind"] == "wrong"
    assert all("model" not in note for item in asked[0] for note in item["notes"])
    feedback = {f["state"]: f for f in review["audit"]["feedback"]["findings"]}
    assert set(feedback) == {"corrected", "disputed", "open"}
    marked = {item["finding"] for claim in review["audit"]["claims"] for item in claim["dissent"]}
    assert feedback["corrected"]["id"] not in marked
    assert {feedback["disputed"]["id"], feedback["open"]["id"]} <= marked
    assert not any("36.10" in claim["anchor"] for claim in review["audit"]["claims"])
    # The trace keeps every note, with its reviewer.
    assert feedback["corrected"]["notes"] and all(note["model"] for note in feedback["corrected"]["notes"])


def test_a_newer_message_keeps_the_first_version(store, monkeypatch):
    """The next message may start while the reviewers still work: it read
    the first version, so a correction finished after its start is not kept."""
    begin = type(store).begin_correction

    def newer_meanwhile(self, uid, chat_id, turn_id, **kwargs):
        started = begin(self, uid, chat_id, turn_id, **kwargs)
        self._chat_ref(uid, chat_id).update({"agent_turn_id": "newer"})
        return started

    monkeypatch.setattr(type(store), "begin_correction", newer_meanwhile)
    script = Audit(live={"anthropic": agent_side(
        lambda findings: json.dumps({"findings": [{"id": f["id"], "sentence": FIXED} for f in findings]}))})
    loop = feedback_loop(store, script)
    list(loop.run())
    turn = saved(store, loop)
    review = turn["agent_review"]
    assert turn["assistant_response"] == ANSWER and len(review["versions"]) == 1
    feedback = review["audit"]["feedback"]
    assert feedback["skipped"] == "newer_message"
    assert all(f["state"] == "open" for f in feedback["findings"])
    # The chat's newest message is another: nothing is saved for it.
    assert "agent_open_findings" not in store._chat_ref(UID, loop.chat_id).get().to_dict()


def test_no_correction_starts_once_a_newer_message_runs(store, monkeypatch):
    monkeypatch.setattr(type(store), "begin_correction", lambda self, *a, **k: False)
    asked = []
    script = Audit(live={"anthropic": agent_side(lambda f: asked.append(f) or "{}")})
    loop = feedback_loop(store, script)
    list(loop.run())
    assert asked == []
    assert saved(store, loop)["agent_review"]["audit"]["feedback"]["skipped"] == "newer_message"


def test_an_unusable_correction_leaves_the_answer_and_the_findings_open(store):
    script = Audit(live={"anthropic": agent_side(lambda findings: "I would rather not.")})
    loop = feedback_loop(store, script)
    list(loop.run())
    turn = saved(store, loop)
    assert turn["status"] == "completed" and turn["assistant_response"] == ANSWER
    feedback = turn["agent_review"]["audit"]["feedback"]
    assert feedback["skipped"] == "unreadable" and not any(f["state"] == "checking" for f in feedback["findings"])


def test_the_history_reads_a_correcting_turn_again():
    from app.services.agent_runs import AgentRunStore

    class Snap:
        def __init__(self, data):
            self.data = data

        def to_dict(self):
            return self.data
    page = {"snapshots": [Snap({"position": 1, "status": "pending", "agent_answer_fixed_at": 1})]}
    assert AgentRunStore.history_current(page, {"position": 2})
    page["snapshots"][0].data["agent_correcting"] = True
    assert not AgentRunStore.history_current(page, {"position": 2})


def asked(calls, question):
    """The agent's first request for ``question``: its last user message."""
    for call in calls:
        users = [m for m in call["messages"] if m["role"] == "user" and isinstance(m.get("content"), str)]
        if users and users[-1]["content"].endswith(question):
            return users[-1]["content"]
    raise AssertionError(f"No request asked {question!r}")


def test_the_route_reads_the_setting_and_passes_the_open_findings_on(api, monkeypatch):
    from app.api.routers import agent
    client, store, calls = api
    chat_id = client.post("/chats", json={"execution_mode": "agent"}, headers=AUTH).json()["chat"]["id"]
    first = {"chat_id": chat_id, "question": "Hi", "client_request_id": "f-1", "bookmark_id": "bm_f"}
    assert client.post("/agent", json=first, headers=AUTH).status_code == 200
    chat = store._chat_ref(UID, chat_id).get().to_dict()
    open_findings = {"turn_id": chat["agent_turn_id"], "total": 1, "findings": [
        {"on": "answer", "kind": "wrong", "reviewers": 2, "quote": "A helpful answer", "note": "Not helpful.",
         "source": RATES}]}
    store._chat_ref(UID, chat_id).update({"agent_open_findings": open_findings})
    # Off: the next message does not hear of them.
    monkeypatch.setattr(agent, "_findings_to_agent", lambda uid: False)
    assert client.post("/agent", json={**first, "client_request_id": "f-2", "question": "Two"},
                       headers=AUTH).status_code == 200
    assert fb.CONTEXT_OPEN not in asked(calls, "Two")
    # On, the message after the one that left them reads them as data.
    store._chat_ref(UID, chat_id).update({"agent_open_findings": {
        **open_findings, "turn_id": store._chat_ref(UID, chat_id).get().to_dict()["agent_turn_id"]}})
    monkeypatch.setattr(agent, "_findings_to_agent", lambda uid: True)
    assert client.post("/agent", json={**first, "client_request_id": "f-3", "question": "Three"},
                       headers=AUTH).status_code == 200
    question = asked(calls, "Three")
    assert fb.CONTEXT_OPEN in question and "Not helpful." in question
    turn = next(t for t in store.list_turns(UID, chat_id)["turns"] if t["question"] == "Three")
    assert store.get_turn(UID, chat_id, turn["id"])["agent_settings"]["findings_to_agent"] is True


# --- Robustness: a failure costs at most the correction --------------------------

def _marks_kept(review):
    marked = {item.get("finding") for claim in review["audit"]["claims"] for item in claim["dissent"]}
    answer = {f["id"] for f in review["audit"]["feedback"]["findings"] if f["on"] == "answer"}
    return answer and answer <= marked


@pytest.mark.parametrize("failure, skipped", [("allowance", "allowance"), ("time", "no_time"), ("error", "failed")])
def test_a_pass_that_cannot_finish_ends_quietly_with_the_marks_as_before(store, monkeypatch, failure, skipped):
    from app.services.agent_audit import AnswerAudit
    from app.services.agent_quota import AgentTokenBudgetExceeded
    from app.services.llm.provider_runtime import ProviderCancelled

    def refuse(self, message, cancellation, seconds):
        raise {"allowance": lambda: AgentTokenBudgetExceeded(0, 100), "time": lambda: ProviderCancelled("overtime"),
               "error": lambda: RuntimeError("provider broke")}[failure]()
    monkeypatch.setattr(AnswerAudit, "_correction_request", refuse)
    loop = feedback_loop(store, Audit())
    list(loop.run())
    turn = saved(store, loop)
    review = turn["agent_review"]
    assert turn["status"] == "completed" and turn["assistant_response"] == ANSWER
    assert review["status"] == "succeeded" and len(review["versions"]) == 1
    feedback = review["audit"]["feedback"]
    assert feedback["status"] == "done" and feedback["skipped"] == skipped
    assert all(f["state"] == "open" for f in feedback["findings"])
    assert _marks_kept(review)


def test_the_users_stop_during_the_pass_keeps_the_answer_and_its_marks(store):
    from app.services.llm.provider_runtime import ProviderCancelled

    def stop(findings):
        script.loop.cancellation.cancel()
        raise ProviderCancelled("stopped")
    script = Audit(live={"anthropic": agent_side(stop)})
    loop = feedback_loop(store, script)
    try:
        list(loop.run())
    except ProviderCancelled:
        pass
    turn = saved(store, loop)
    assert turn["assistant_response"] == ANSWER
    review = turn["agent_review"]
    assert review["audit"]["feedback"]["status"] == "done" and _marks_kept(review)


def test_a_reviewer_that_fails_leaves_the_others_findings_to_the_pass(store):
    asked = []
    script = Audit({"anthropic": json.dumps({"marks": [{"quote": "Tickets to the top cost 14 euros", "kind": "wrong",
                                                         "note": "36.10.", "source": RATES}]}),
                    "openai": RuntimeError("provider down")},
                   live={"anthropic": agent_side(lambda f: asked.append(f) or json.dumps(
                       {"findings": [{"id": f[0]["id"], "sentence": FIXED}]}))})
    loop = feedback_loop(store, script)
    list(loop.run())
    turn = saved(store, loop)
    assert turn["agent_review"]["status"] == "partial" and len(asked) == 1
    assert turn["assistant_response"] == ANSWER.replace("Tickets to the top cost 14 euros.", FIXED)


def test_a_run_that_breaks_off_mid_pass_leaves_its_findings_open():
    review = {"status": "succeeded", "audit": {"feedback": {"status": "checking", "findings": [
        {"id": "s1", "state": "checking"}, {"id": "s2", "state": "disputed"}]}}}
    closed = fb.closed_feedback(review)
    feedback = closed["audit"]["feedback"]
    assert feedback["status"] == "done" and feedback["skipped"] == "run_interrupted"
    assert [f["state"] for f in feedback["findings"]] == ["open", "disputed"]
    done = {"audit": {"feedback": {"status": "done", "findings": []}}}
    assert fb.closed_feedback(done) is done and fb.closed_feedback({"status": "off"}) == {"status": "off"}


def test_a_failed_review_ends_the_register_without_a_pass(store, monkeypatch):
    """A review that failed as a whole leaves nothing to correct; the page
    must not wait for a pass that never comes."""
    from app.services.agent_audit import AnswerAudit
    asked = []
    script = Audit(live={"anthropic": agent_side(lambda f: asked.append(f) or "{}")})
    loop = feedback_loop(store, script)
    original = AnswerAudit._register

    def fail_review(self, reviews):
        original(self, reviews)
        self.claims = None
    monkeypatch.setattr(AnswerAudit, "_register", fail_review)
    list(loop.run())
    assert asked == []
    assert saved(store, loop)["agent_review"]["audit"]["feedback"]["status"] == "done"

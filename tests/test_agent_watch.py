"""The Agent's Watch tools (agent_watch.py): it prepares a Watch the user
starts from a card, and in a scheduled run it reports a finding with
evidence or ends the Watch (since 2026-11-03, a Watch runs the Agent)."""
import json

import pytest

from app.services import agent_watch, agent_watches
from app.services.agent_comparison import comparison_selection
from app.services.agent_delegation import HOLD_TIMEOUT_SECONDS, DelegationLoop
from app.services.agent_policy import AgentPolicy
from app.services.chat_store import turn_detail
from app.services.llm.agent_client import measured_usage, resolve_agent_model
from app.services.llm.provider_runtime import ProviderCancellation
from agent_reviewers import without_reviewers
from test_agent_comparison import Script
from test_agent_runs import UID, pending, store  # noqa: F401  (fixture)


pytestmark = pytest.mark.usefixtures("deepseek_default_agent")

TASK = "Check on ironman.com whether registration for IRONMAN Hamburg 2027 is open."
WATCH = {"task": TASK, "goal": "Registration is open", "interval": "daily"}
PROPOSAL = {"task": TASK, "goal": "Registration is open", "interval": "daily", "run_time": "", "run_weekday": ""}


def outlook(**fields):
    base = {"already_watched": False, "active_count": 0, "active_limit": 2,
            "limit_reached": False, "intervals": ["hourly", "every_6_hours", "daily", "weekly"]}
    return lambda uid, chat_id: {**base, **fields}


class WatchScript(Script):
    """prepare_watch first, then a comparison and the answer the agent
    writes from it; or a watch-only message that it answers directly.
    ``requests`` keeps the messages of each orchestrator step: the last one
    wrote the answer."""

    def __init__(self, *, watch=WATCH, direct_reply=None, **kwargs):
        super().__init__(compares=2, **kwargs)
        self.watch, self.direct_reply = watch, direct_reply
        self.tools, self.system, self.requests = [], "", {}

    def factory(self):
        script = self
        base = type(Script.factory(self))

        class Completion(base):
            def stream(self, *, model, messages, **kwargs):
                tools = kwargs.get("tools") or []
                if self.step_id.startswith("completion:"):
                    script.requests[self.step_id] = json.loads(json.dumps(messages))
                if self.step_id == "completion:0":
                    script.system = messages[0]["content"]
                    script.tools = [tool["function"]["name"] for tool in tools if tool.get("type") == "function"]
                if self.step_id.startswith("completion:") and (
                        self.step_id == "completion:0" or script.direct_reply is not None):
                    script.calls.append((self.step_id, model.model))
                    self.usage = measured_usage({"prompt_tokens": 50, "completion_tokens": 20, "cost": .0001}, model)
                    if self.step_id == "completion:0":
                        self.tool_calls = [{"id": "call_watch", "type": "function", "function": {
                            "name": "prepare_watch", "arguments": json.dumps(script.watch)}}]
                        self.finish_reason = "tool_calls"
                        return
                    self.text, self.finish_reason = script.direct_reply, "stop"
                    yield {"type": "delta", "text": self.text}
                    return
                yield from super().stream(model=model, messages=messages, **kwargs)
        return Completion()

    def writer(self):
        """The messages of the step that wrote the answer."""
        return self.requests[max(self.requests, key=lambda step: int(step.split(":")[-1]))]


def watch_loop(store, script, *, watch_outlook=None, question="Tell me when IRONMAN Hamburg registration opens.",
               preferences=None, google_data=False, reviewers=False, watch_run=None, temporary=False):
    """A chat turn of the agent; its reviewers never start (agent_reviewers.py)
    unless ``reviewers``, whose rounds Script answers without marks.
    ``watch_run``: a Watch's scheduled run."""
    chat, turn = pending(store, question=question)
    loop = DelegationLoop(store=store, uid=UID, chat_id=chat, turn_id=turn["id"],
        model=resolve_agent_model("claude-haiku-4-5"),
        messages=[{"role": "system", "content": "Answer."}, {"role": "user", "content": question}],
        api_key="test", cancellation=ProviderCancellation(), policy=AgentPolicy(),
        completion_factory=script.factory,
        comparison_models=comparison_selection({"anthropic": "claude-haiku-4-5", "openai": "gpt-5.4-mini"}),
        agent_preferences=preferences, google_data=google_data, watch_run=watch_run, temporary=temporary)
    if loop.watch_tools:
        loop.watch_tools.outlook = watch_outlook or outlook()
    if not reviewers:
        without_reviewers(loop)
    script.loop = loop
    return loop


@pytest.fixture
def no_watch_writes(monkeypatch):
    """prepare_watch must never start a Watch: only the card does."""
    def refuse(*args, **kwargs):
        raise AssertionError("prepare_watch started a Watch")
    monkeypatch.setattr(agent_watches, "create", refuse)


def tool_results(loop, name="call_watch"):
    return [json.loads(m["content"]) for m in loop.messages if m.get("role") == "tool" and m.get("tool_call_id") == name]


def seen_watch(messages):
    """The prepare_watch result as the step that wrote the answer read it."""
    return json.loads(next(m["content"] for m in messages
                           if m.get("role") == "tool" and m.get("tool_call_id") == "call_watch"))


@pytest.mark.usefixtures("no_watch_writes")
def test_a_requested_watch_is_prepared_saved_and_handed_to_the_answer(store):
    script = WatchScript()
    loop = watch_loop(store, script, reviewers=True)
    list(loop.run())
    saved = store.get_turn(UID, loop.chat_id, loop.turn_id)
    assert saved["status"] == "completed"
    # The card reads the proposal from the completed turn; nothing else carries it.
    assert saved["agent_watch"] == PROPOSAL
    result = tool_results(loop)[0]
    assert result["status"] == "prepared" and "nothing runs yet" in result["instruction"]
    assert "prepare_watch" in script.tools and "compare_models" in script.tools and "answer" not in script.tools
    assert "report_finding" not in script.tools and "finish_watch" not in script.tools
    assert agent_watch.AUDIT_PROMPT in script.system and agent_watch.RUN_PROMPT not in script.system
    writer = script.writer()
    assert agent_watch.AUDIT_PROMPT in writer[0]["content"]
    assert seen_watch(writer)["status"] == "prepared" and seen_watch(writer)["task"] == TASK
    assert "never claim the Watch is active" in seen_watch(writer)["instruction"]
    assert saved["consensus"] == "The first option costs 100."
    assert saved["agent_review"]["mode"] == "audit" and saved["agent_review"]["status"] == "succeeded"
    steps = [event for event in saved["agent_activity"] if event.get("name") == "prepare_watch"]
    assert steps and steps[-1]["status"] == "succeeded"
    # An ordinary turn waits for the user on a card as before.
    assert loop.hold_timeout == HOLD_TIMEOUT_SECONDS


@pytest.mark.usefixtures("no_watch_writes")
def test_a_weekly_watch_keeps_its_time_and_day_and_a_shorter_one_none(store):
    script = WatchScript(watch={**WATCH, "interval": "weekly", "run_time": "07:30", "run_weekday": "monday"})
    loop = watch_loop(store, script)
    list(loop.run())
    proposal = store.get_turn(UID, loop.chat_id, loop.turn_id)["agent_watch"]
    assert (proposal["interval"], proposal["run_time"], proposal["run_weekday"]) == ("weekly", "07:30", "monday")
    script = WatchScript(watch={**WATCH, "interval": "hourly", "run_time": "07:30", "run_weekday": "monday"})
    loop = watch_loop(store, script)
    list(loop.run())
    proposal = store.get_turn(UID, loop.chat_id, loop.turn_id)["agent_watch"]
    assert (proposal["interval"], proposal["run_time"], proposal["run_weekday"]) == ("hourly", "", "")


@pytest.mark.usefixtures("no_watch_writes")
def test_an_interval_the_account_lacks_becomes_its_shortest(store):
    script = WatchScript(watch={**WATCH, "interval": "hourly"})
    loop = watch_loop(store, script, watch_outlook=outlook(intervals=["daily", "weekly"]))
    list(loop.run())
    assert store.get_turn(UID, loop.chat_id, loop.turn_id)["agent_watch"]["interval"] == "daily"
    result = tool_results(loop)[0]
    assert result["interval"] == "daily" and "not available on this account" in result["note"]


@pytest.mark.usefixtures("no_watch_writes")
@pytest.mark.parametrize("fields,status", [({"already_watched": True}, "already_watched"),
                                           ({"limit_reached": True, "active_count": 2, "active_limit": 2},
                                            "limit_reached")])
def test_an_existing_watch_or_a_full_account_is_said_not_offered(store, fields, status):
    script = WatchScript()
    loop = watch_loop(store, script, watch_outlook=outlook(**fields))
    list(loop.run())
    assert tool_results(loop)[0]["status"] == status
    writer = script.writer()
    assert seen_watch(writer)["status"] == status
    assert seen_watch(writer)["instruction"] == agent_watch.INSTRUCTIONS[status]
    # The card still shows the task; it reads the chat's Watches itself.
    assert store.get_turn(UID, loop.chat_id, loop.turn_id)["agent_watch"]["task"] == TASK


@pytest.mark.usefixtures("no_watch_writes")
def test_a_watch_only_message_ends_with_an_acknowledgement(store):
    script = WatchScript(direct_reply="I prepared a Watch for this below.")
    loop = watch_loop(store, script, question="Can you keep an eye on that for me?")
    list(loop.run())
    saved = store.get_turn(UID, loop.chat_id, loop.turn_id)
    assert saved["status"] == "completed"
    assert saved["consensus"] == "I prepared a Watch for this below."
    assert saved["agent_watch"]["task"] == TASK
    assert not (saved.get("agent_review") or {}).get("comparisons")
    reminders = [m for m in loop.messages if "App rule" in str(m.get("content"))]
    assert reminders == []


class WatchWithReply(WatchScript):
    """The acknowledgement and prepare_watch in one step: the text is the
    answer, with no comparison and no further step (2026-10-11, "kannst du
    den Watch für mich starten?" ran six models)."""

    REPLY = "Here is the Watch again: start it from the card below."

    def factory(self):
        script = self
        base = type(super().factory())

        class Completion(base):
            def stream(self, *, model, messages, **kwargs):
                if self.step_id == "completion:0":
                    script.system = messages[0]["content"]
                    script.calls.append((self.step_id, model.model))
                    self.usage = measured_usage({"prompt_tokens": 50, "completion_tokens": 20, "cost": .0001}, model)
                    self.text = script.REPLY
                    yield {"type": "delta", "text": self.text}
                    calls = [{"id": "call_watch", "type": "function", "function": {
                        "name": "prepare_watch", "arguments": json.dumps(script.watch)}}]
                    self._tool_parts = dict(enumerate(calls))
                    self.tool_calls, self.finish_reason = calls, "tool_calls"
                    return
                yield from super().stream(model=model, messages=messages, **kwargs)
        return Completion()


@pytest.mark.usefixtures("no_watch_writes")
def test_starting_an_earlier_watch_prepares_it_again_and_answers_without_a_comparison(store):
    script = WatchWithReply()
    loop = watch_loop(store, script, question="Kannst du den Watch bitte für mich starten?")
    events = list(loop.run())
    saved = store.get_turn(UID, loop.chat_id, loop.turn_id)
    assert saved["status"] == "completed" and saved["agent_watch"]["task"] == TASK
    assert not loop.comparison.comparisons
    assert saved["consensus"] == WatchWithReply.REPLY
    assert "".join(e["text"] for e in events if e.get("type") == "delta") == WatchWithReply.REPLY
    assert not any(e.get("clear_response") for e in events)
    assert [step for step, _ in script.calls if step.startswith("completion:")] == ["completion:0"]


def watch_outage(uid, chat_id):
    raise RuntimeError("firestore down")


@pytest.mark.usefixtures("no_watch_writes")
@pytest.mark.parametrize("watch_outlook,reply", [
    (outlook(already_watched=True), "This chat already has a Watch."),
    (watch_outage, "Watches cannot be prepared right now, sorry."),
], ids=["already_watched", "outage"])
def test_a_reply_next_to_a_watch_that_was_not_prepared_is_written_again(store, watch_outlook, reply):
    """The reply pointed to a card that offers no new Watch: it goes back and
    the next step writes the answer with the result in view
    (DelegationLoop._side_results_accepted, review 2026-10-14)."""
    script = WatchWithReply(direct_reply=reply)
    loop = watch_loop(store, script, question="Kannst du den Watch bitte für mich starten?",
                      watch_outlook=watch_outlook)
    events = list(loop.run())
    saved = store.get_turn(UID, loop.chat_id, loop.turn_id)
    assert [step for step, _ in script.calls if step.startswith("completion:")] == ["completion:0", "completion:1"]
    assert saved["status"] == "completed" and saved["consensus"] == reply
    assert "".join(e["text"] for e in events if e.get("type") == "delta") == reply
    assert seen_watch(script.writer()) == tool_results(loop)[0]
    assert tool_results(loop)[0].get("status") != "prepared"


def test_the_watch_block_says_what_a_watch_does_as_facts():
    """Since 2026-11-03 a Watch runs the agent again; the block still says it
    is the one way to reach the user later (2026-10-11: GPT-6 Luna answered
    "kannst du mich erinnern …" with "consens.io cannot notify you")."""
    prompt = agent_watch.AUDIT_PROMPT
    assert "is consens.io's only way to reach the user later" in prompt
    assert "runs you again on a schedule in this chat" in prompt
    assert "prepare_watch prepares one as a card below your answer, which only the user starts" in prompt
    assert "in the user's name" in prompt
    assert "never claim the Watch is active" in agent_watch.INSTRUCTIONS["prepared"]
    assert "call answer" not in prompt and "compare" not in prompt


def test_no_watch_tool_with_google_data_or_in_a_temporary_chat(store):
    google = watch_loop(store, WatchScript(), google_data=True)
    assert google.watch_tools is None and "prepare_watch" not in google.registry.tools
    assert agent_watch.AUDIT_PROMPT not in google.messages[0]["content"]
    temporary = watch_loop(store, WatchScript(), temporary=True)
    assert temporary.watch_tools is None and "prepare_watch" not in temporary.registry.tools


@pytest.mark.parametrize("arguments,problem", [
    ({"task": "Check"}, "task"),
    ({"task": "Check " + "x" * 500}, "task"),
    ({"task": TASK, "goal": "x" * 201}, "goal"),
    ({"task": TASK, "interval": "monthly"}, "interval"),
    ({"task": TASK, "run_time": "8 am"}, "run_time"),
    ({"task": TASK, "visibility": "public"}, "visibility"),
])
def test_the_schema_bounds_what_the_model_may_propose(store, arguments, problem):
    loop = watch_loop(store, WatchScript())
    call = {"id": "c", "type": "function", "function": {"name": "prepare_watch", "arguments": json.dumps(arguments)}}
    with pytest.raises(ValueError) as error:
        loop.registry.validate(call)
    assert problem in str(error.value)


@pytest.mark.usefixtures("no_watch_writes")
def test_a_finished_turn_takes_no_proposal_and_outages_are_readable_refusals(store):
    loop = watch_loop(store, WatchScript())
    args = agent_watch.PrepareWatch(task=TASK)
    loop.watch_tools.outlook = watch_outage
    with pytest.raises(ValueError, match="cannot be prepared right now"):
        loop.watch_tools.prepare(args)
    loop.watch_tools.outlook = outlook()
    store.db.turns(UID, loop.chat_id)[loop.turn_id]["status"] = "completed"
    with pytest.raises(ValueError, match="already finished"):
        loop.watch_tools.prepare(args)
    assert loop.watch_proposal is None
    assert "agent_watch" not in store.get_turn(UID, loop.chat_id, loop.turn_id)


@pytest.mark.usefixtures("no_watch_writes")
def test_the_mock_run_prepares_a_watch_for_browser_tests(store):
    loop = watch_loop(store, WatchScript(), question="Watch: Check whether the next iPhone ships.")
    loop.watch_tools.mock_turn("Watch: Check whether the next iPhone ships.")
    assert store.get_turn(UID, loop.chat_id, loop.turn_id)["agent_watch"] == {
        "task": "Check whether the next iPhone ships.", "goal": "It is officially announced",
        "interval": "daily", "run_time": "", "run_weekday": ""}


def test_saved_turns_keep_the_proposal_and_a_runs_outcome():
    run = {"finding": {"summary": "Registration is open.", "evidence_url": "https://www.ironman.com/hamburg"}}
    detail = turn_detail("t1", {"execution_mode": "agent", "assistant_response": "Answer.",
                                "agent_watch": PROPOSAL, "agent_watch_run": run}, {})
    assert detail["agent_watch"] == PROPOSAL and detail["agent_watch_run"] == run


# --- A scheduled run ---------------------------------------------------------

RUN = {"watch_id": "w" * 32, "scheduled_at": "2026-11-04T07:00:00+00:00", "request_id": "watch.w.1", "goal": ""}
PAGE = "https://www.ironman.com/im-hamburg"


def test_a_scheduled_run_reports_and_ends_and_nobody_waits_for_a_card(store):
    loop = watch_loop(store, WatchScript(), watch_run=RUN)
    names = set(loop.registry.tools)
    assert {"report_finding", "finish_watch"} <= names and "prepare_watch" not in names
    system = loop.messages[0]["content"]
    assert agent_watch.RUN_PROMPT in system and agent_watch.AUDIT_PROMPT not in system
    # The user is away: a card (ask_user, a reviewer's halt) ends at once.
    assert loop.hold_timeout == 0
    assert "the user is not here" in agent_watch.RUN_PROMPT and "with a page you opened in this run" in agent_watch.RUN_PROMPT


def test_a_finding_needs_a_page_this_run_saw(store):
    loop = watch_loop(store, WatchScript(), watch_run=RUN)
    tools = agent_watch.WatchRunTools(loop)
    args = agent_watch.ReportFinding(summary="Registration is open.", evidence_url=PAGE)
    # Only in the chat or the model's own text: refused.
    with pytest.raises(ValueError, match="page you opened or found in this run"):
        tools.report(args)
    # A tool result of this message names it.
    loop.messages.append({"role": "tool", "tool_call_id": "r1", "content": json.dumps({"url": PAGE + "/", "text": "Open"})})
    assert tools.report(args)["status"] == "reported"
    saved = store.get_turn(UID, loop.chat_id, loop.turn_id)["agent_watch_run"]
    assert saved == {"finding": {"summary": "Registration is open.", "evidence_url": PAGE, "evidence_title": "",
                                 "needs_user": False}}


def test_a_search_result_counts_as_seen_with_its_title_and_finish_ends_the_watch(store):
    loop = watch_loop(store, WatchScript(), watch_run=RUN)
    loop.search_sources.append({"url": PAGE, "title": "IRONMAN Hamburg"})
    tools = agent_watch.WatchRunTools(loop)
    tools.report(agent_watch.ReportFinding(summary="Registration is open.", evidence_url=PAGE + "#dates", needs_user=True))
    tools.finish(agent_watch.FinishWatch(reason="Registration opened on November 4."))
    saved = store.get_turn(UID, loop.chat_id, loop.turn_id)["agent_watch_run"]
    assert saved["finding"]["evidence_title"] == "IRONMAN Hamburg" and saved["finding"]["needs_user"] is True
    assert saved["done"] == {"reason": "Registration opened on November 4."}
    # Once the turn ended, nothing more is saved on it.
    store.db.turns(UID, loop.chat_id)[loop.turn_id]["status"] = "completed"
    with pytest.raises(ValueError, match="already finished"):
        tools.finish(agent_watch.FinishWatch(reason="Again."))


def test_the_run_tools_add_no_outside_content_and_ride_along_an_answer():
    from app.services.agent_answer_mode import SIDE_TOOLS
    from app.services.agent_delegation import OWN_CONTENT_TOOLS
    assert {"report_finding", "finish_watch"} <= SIDE_TOOLS & OWN_CONTENT_TOOLS

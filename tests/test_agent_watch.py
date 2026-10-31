"""Agent prepares a Consensus Watch the user asked for; the user starts it from a card."""
import json

import pytest

from app.services import agent_watch, watch_service
from app.services.agent_comparison import comparison_selection
from app.services.agent_delegation import DelegationLoop
from app.services.agent_delegation_config import defaults
from app.services.agent_policy import AgentPolicy
from app.services.chat_store import turn_detail
from app.services.llm.agent_client import measured_usage, resolve_agent_model
from app.services.llm.provider_runtime import ProviderCancellation
from agent_reviewers import without_reviewers
from test_agent_comparison import Script
from test_agent_runs import UID, pending, store  # noqa: F401  (fixture)


pytestmark = pytest.mark.usefixtures("deepseek_default_agent")

QUESTION = "When will OpenAI release GPT-6 to the public?"
WATCH = {"question": QUESTION, "goals": ["GPT-6 is officially released", "OpenAI announces a release date"]}


def outlook(**fields):
    base = {"already_watched": False, "active_count": 0, "active_limit": 3,
            "limit_reached": False, "daily_allowed": True}
    return lambda uid, question: {**base, **fields}


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


def watch_loop(store, script, *, watch_outlook=None, question="Tell me when GPT-6 comes out.",
               preferences=None, google_data=False, comparisons=True, reviewers=False):
    """A chat turn of the agent; its reviewers never start (agent_reviewers.py)
    unless ``reviewers``, whose rounds Script answers without marks.
    ``comparisons=False``: a delegation-only run, without the agent's tools."""
    chat, turn = pending(store, question=question)
    config = {**defaults(), "enabled": False, "max_searches": 0, "context_chars": 120_000}
    loop = DelegationLoop(store=store, uid=UID, chat_id=chat, turn_id=turn["id"],
        model=resolve_agent_model("claude-haiku-4-5"),
        messages=[{"role": "system", "content": "Answer."}, {"role": "user", "content": question}],
        api_key="test", cancellation=ProviderCancellation(), policy=AgentPolicy.for_chat(config),
        delegation_config=config, completion_factory=script.factory,
        comparison_models=comparison_selection({"anthropic": "claude-haiku-4-5", "openai": "gpt-5.4-mini"})
        if comparisons else None,
        agent_preferences=preferences, google_data=google_data)
    if loop.watch_tools:
        loop.watch_tools.outlook = watch_outlook or outlook()
    if comparisons and not reviewers:
        without_reviewers(loop)
    script.loop = loop
    return loop


@pytest.fixture
def no_watch_writes(monkeypatch):
    """prepare_watch must never create a Watch: only the card does."""
    def refuse(*args, **kwargs):
        raise AssertionError("prepare_watch created a Watch")
    monkeypatch.setattr(watch_service, "create_watch", refuse)


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
    proposal = {"question": QUESTION, "goals": WATCH["goals"], "interval": "weekly"}
    # The card reads the proposal from the completed turn; nothing else carries it.
    assert saved["agent_watch"] == proposal
    result = tool_results(loop)[0]
    assert result["status"] == "prepared" and "nothing is watched yet" in result["instruction"]
    # The agent learns what a Watch is once; the tool is offered with compare_models.
    assert "prepare_watch" in script.tools and "compare_models" in script.tools and "answer" not in script.tools
    assert agent_watch.AUDIT_PROMPT in script.system
    # The step that writes the answer knows what the Watch is, and the tool's
    # result says what to tell the user: it must not claim more.
    writer = script.writer()
    assert agent_watch.AUDIT_PROMPT in writer[0]["content"]
    assert seen_watch(writer)["status"] == "prepared" and seen_watch(writer)["question"] == QUESTION
    assert "never claim the Watch is active" in seen_watch(writer)["instruction"]
    assert saved["consensus"] == "The first option costs 100."
    assert saved["agent_review"]["comparisons"], "the current state is still compared, then reviewed"
    assert saved["agent_review"]["mode"] == "audit" and saved["agent_review"]["status"] == "succeeded"
    steps = [event for event in saved["agent_activity"] if event.get("name") == "prepare_watch"]
    assert steps and steps[-1]["status"] == "succeeded"


@pytest.mark.usefixtures("no_watch_writes")
def test_daily_falls_back_to_weekly_when_the_account_cannot_check_daily(store):
    script = WatchScript(watch={**WATCH, "interval": "daily"})
    loop = watch_loop(store, script, watch_outlook=outlook(daily_allowed=False))
    list(loop.run())
    assert store.get_turn(UID, loop.chat_id, loop.turn_id)["agent_watch"]["interval"] == "weekly"
    result = tool_results(loop)[0]
    assert result["interval"] == "weekly" and "Daily checks are not available" in result["note"]


@pytest.mark.usefixtures("no_watch_writes")
@pytest.mark.parametrize("fields,status", [({"already_watched": True}, "already_watched"),
                                           ({"limit_reached": True, "active_count": 1, "active_limit": 1},
                                            "limit_reached")])
def test_an_existing_watch_or_a_full_account_is_said_not_offered(store, fields, status):
    script = WatchScript()
    loop = watch_loop(store, script, watch_outlook=outlook(**fields))
    list(loop.run())
    assert tool_results(loop)[0]["status"] == status
    writer = script.writer()
    # What to tell the user comes with the result the answer is written from.
    assert seen_watch(writer)["status"] == status
    assert seen_watch(writer)["instruction"] == agent_watch.INSTRUCTIONS[status]
    # The card still shows the question; it reads the live state itself.
    assert store.get_turn(UID, loop.chat_id, loop.turn_id)["agent_watch"]["question"] == QUESTION


@pytest.mark.usefixtures("no_watch_writes")
def test_a_watch_only_message_ends_with_an_acknowledgement(store):
    script = WatchScript(direct_reply="I prepared a Watch for this question below.")
    loop = watch_loop(store, script, question="Can you watch that for me?")
    list(loop.run())
    saved = store.get_turn(UID, loop.chat_id, loop.turn_id)
    assert saved["status"] == "completed"
    assert saved["consensus"] == "I prepared a Watch for this question below."
    assert saved["agent_watch"]["question"] == QUESTION
    assert not (saved.get("agent_review") or {}).get("comparisons")
    # A short acknowledgement is plain text (no reminder).
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
    assert saved["status"] == "completed" and saved["agent_watch"]["question"] == QUESTION
    assert not loop.comparison.comparisons
    # The text of that step stands as the answer: shown, never retracted.
    assert saved["consensus"] == WatchWithReply.REPLY
    assert "".join(e["text"] for e in events if e.get("type") == "delta") == WatchWithReply.REPLY
    assert not any(e.get("clear_response") for e in events)
    assert [step for step, _ in script.calls if step.startswith("completion:")] == ["completion:0"]
    assert agent_watch.AUDIT_PROMPT in script.system


def watch_outage(uid, question):
    raise RuntimeError("firestore down")


@pytest.mark.usefixtures("no_watch_writes")
@pytest.mark.parametrize("watch_outlook,reply", [
    (outlook(already_watched=True), "You already watch this question."),
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


def test_the_watch_block_says_it_is_the_only_way_to_reach_the_user_later():
    """2026-10-11: GPT-6 Luna read "kannst du mich erinnern, wann der Sieger
    feststeht?" after a search as a question about the date, prepared nothing,
    and the answer said consens.io could not notify anyone. Since 2026-10-28
    the block says what a Watch is, as facts; the tool's result says what to
    tell the user."""
    prompt = agent_watch.AUDIT_PROMPT
    assert "it is consens.io's only way to reach the user later" in prompt
    assert "emails the user when a source changes the answer" in prompt
    assert "prepare_watch prepares one as a card below your answer, which only the user starts" in prompt
    assert "never claim the Watch is active" in agent_watch.INSTRUCTIONS["prepared"]
    # No recipe and nothing about removed tools or steps.
    assert "call answer" not in prompt and "answer step" not in prompt and "evidence" not in prompt
    assert "compare" not in prompt


def test_no_watch_tool_with_google_data_or_without_comparisons(store):
    script = WatchScript()
    google = watch_loop(store, script, google_data=True)
    assert google.watch_tools is None and "prepare_watch" not in google.registry.tools
    assert agent_watch.AUDIT_PROMPT not in google.messages[0]["content"]
    bounded = watch_loop(store, WatchScript(), comparisons=False)
    assert bounded.watch_tools is None and "prepare_watch" not in bounded.registry.tools


@pytest.mark.parametrize("arguments,problem", [
    ({"question": "GPT-6?"}, "question"),
    ({"question": "When " + "x" * 200 + "?"}, "question"),
    ({"question": QUESTION, "goals": ["a", "b", "c", "d"]}, "goals"),
    ({"question": QUESTION, "goals": ["x" * 121]}, "goals"),
    ({"question": QUESTION, "interval": "hourly"}, "interval"),
    ({"question": QUESTION, "visibility": "public"}, "visibility"),
])
def test_the_schema_bounds_what_the_model_may_propose(store, arguments, problem):
    loop = watch_loop(store, WatchScript())
    call = {"id": "c", "type": "function", "function": {"name": "prepare_watch", "arguments": json.dumps(arguments)}}
    with pytest.raises(ValueError) as error:
        loop.registry.validate(call)
    assert problem in str(error.value)


def test_goals_are_clean_distinct_lines():
    assert agent_watch.normalize_goals([" GPT-6 is  released. ", "gpt-6 is released", "ok", "A date is set"]) == [
        "GPT-6 is released", "A date is set"]


@pytest.mark.usefixtures("no_watch_writes")
def test_a_finished_turn_takes_no_proposal_and_outages_are_readable_refusals(store):
    loop = watch_loop(store, WatchScript())
    args = agent_watch.PrepareWatch(question=QUESTION)
    loop.watch_tools.outlook = lambda uid, question: (_ for _ in ()).throw(RuntimeError("firestore down"))
    with pytest.raises(ValueError, match="cannot be prepared right now"):
        loop.watch_tools.prepare(args)
    loop.watch_tools.outlook = outlook()
    original = loop.watch_tools._save
    loop.watch_tools._save = lambda proposal: (_ for _ in ()).throw(RuntimeError("contention"))
    with pytest.raises(ValueError, match="could not be prepared right now"):
        loop.watch_tools.prepare(args)
    loop.watch_tools._save = original
    store.db.turns(UID, loop.chat_id)[loop.turn_id]["status"] = "completed"
    with pytest.raises(ValueError, match="already finished"):
        loop.watch_tools.prepare(args)
    assert loop.watch_proposal is None
    assert "agent_watch" not in store.get_turn(UID, loop.chat_id, loop.turn_id)


@pytest.mark.usefixtures("no_watch_writes")
def test_the_mock_run_prepares_a_watch_for_browser_tests(store):
    loop = watch_loop(store, WatchScript(), question="Watch: When will the next iPhone ship?")
    loop.watch_tools.mock_turn("Watch: When will the next iPhone ship?")
    assert store.get_turn(UID, loop.chat_id, loop.turn_id)["agent_watch"] == {
        "question": "When will the next iPhone ship?", "goals": ["It is officially announced"], "interval": "weekly"}


def test_saved_turns_keep_the_proposal():
    proposal = {"question": QUESTION, "goals": [], "interval": "weekly"}
    detail = turn_detail("t1", {"execution_mode": "agent", "assistant_response": "Answer.",
                                "agent_watch": proposal}, {})
    assert detail["agent_watch"] == proposal

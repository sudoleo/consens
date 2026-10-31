"""compare_models in audit mode (since 2026-10-31, package 1 of one mode for
comparison and audit; routers/agent.py audit_compare_allowed): the agent may
ask the user's chosen models its question. They answer as advisers, each in a
fresh conversation of its own, never the reviewers' sessions; no judge runs;
the reviewers read every answer in the work log; and the run goes on after
the answers, it does not end with them. Without the switch audit mode offers
no comparison (test_agent_audit).
"""
import json

import pytest

from app.api.routers import agent as agent_router
from app.services import agent_audit, prompt_defaults
from app.services.agent_audit import COMPARISON_ENTRY_CHARS, ENTRY_CHARS, review_entry
from app.services.agent_comparison import AgentPreferences, JudgeArgs, comparison_selection, review_is_bound
from app.services.agent_delegation import DelegationLoop
from app.services.agent_delegation_config import defaults
from app.services.agent_policy import AgentPolicy
from app.services.agent_tools import ReadOnlyTool, ToolRegistry
from app.services.llm.agent_client import measured_usage, resolve_agent_model
from app.services.llm.provider_runtime import ProviderCancellation
from test_agent_audit import ANSWER, Audit, round_entries, saved
from test_agent_runs import UID, pending, store  # noqa: F401  (fixtures)


@pytest.fixture(autouse=True)
def _admin_allowance(monkeypatch):
    """Audit mode is for admins (5M tokens a day, test_agent_audit)."""
    from app.services import agent_budget_config
    monkeypatch.setitem(agent_budget_config.DEFAULT_TIER_LIMITS, "pro", 5_000_000)


QUESTION = "How tall is the Eiffel Tower today, antennas included?"
# Longer together than one log entry (ENTRY_CHARS): cut as one text, the
# reviewers saw the first answer only.
ADVICE = {"anthropic": "Claude says 330 metres since the 2022 antenna. " + "C" * 7_000 + " END-CLAUDE",
          "openai": "GPT says 324 metres; the antenna is not counted. " + "G" * 7_000 + " END-GPT"}


class Advised(Audit):
    """A scripted audit turn whose agent asks the models (compare_models) in
    its first step: their answers come from ``advice`` by family. Then, by
    ``then``, it calls the tool ``note`` before it answers."""

    def __init__(self, *, advice=None, then=False, **kwargs):
        steps = {0: "compare_models", **({1: "note"} if then else {})}
        args = {0: {"question": QUESTION}, **({1: {"step": 1}} if then else {})}
        super().__init__(tool_steps=len(steps), step_tools=steps, step_args=args, **kwargs)
        self.advice = dict(ADVICE if advice is None else advice)
        # (family, messages, OpenRouter session) of every adviser's request.
        self.asked = []

    def factory(self):
        completion = super().factory()
        script, stream = self, completion.stream

        def advise(*, model, messages, **kwargs):
            if not messages[0]["content"].startswith("You are an independent answer model"):
                return (yield from stream(model=model, messages=messages, **kwargs))
            family = model.model.split("/")[0]
            script.asked.append((family, messages, completion.session_id))
            completion.usage = measured_usage({"prompt_tokens": 50, "completion_tokens": 20, "cost": .0001}, model)
            if isinstance(script.advice[family], BaseException):
                raise script.advice[family]
            completion.text, completion.finish_reason = script.advice[family], "stop"
            yield {"type": "delta", "text": completion.text}
        completion.stream = advise
        return completion


def advised_loop(store, script, *, judges="on", audit_compare=True):
    chat, turn = pending(store)
    config = {**defaults(), "enabled": False, "max_searches": 0}
    loop = DelegationLoop(store=store, uid=UID, chat_id=chat, turn_id=turn["id"],
        model=resolve_agent_model("claude-haiku-4-5"),
        messages=[{"role": "system", "content": "Answer."}, {"role": "user", "content": "Tell me about the Eiffel Tower."}],
        api_key="test", cancellation=ProviderCancellation(), policy=AgentPolicy.for_chat(config),
        delegation_config=config, completion_factory=script.factory,
        comparison_models=comparison_selection({"anthropic": "claude-haiku-4-5", "openai": "gpt-5.4-mini"}, audit=True),
        agent_preferences=AgentPreferences(audit="on", judges=judges), audit_compare=audit_compare)
    notes = []

    def note(args, *, cancellation):
        notes.append(args)
        return {"text": "Noted."}
    loop.registry = ToolRegistry([*loop.registry.tools.values(), ReadOnlyTool("note", "Take a note.", JudgeArgs, note)],
                                 argument_limit=loop.registry.argument_limit)
    script.loop = loop
    return loop


def tool_results(loop, name):
    """The results the agent got from ``name``, in order."""
    ids = {call["id"] for message in loop.messages if message.get("role") == "assistant"
           for call in message.get("tool_calls") or [] if call["function"]["name"] == name}
    return [json.loads(message["content"]) for message in loop.messages
            if message.get("role") == "tool" and message.get("tool_call_id") in ids]


def test_the_agent_asks_the_models_works_on_and_the_reviewers_read_their_answers(store):
    script = Advised(then=True)
    loop = advised_loop(store, script)
    events = list(loop.run())
    turn = saved(store, loop)
    review = turn["agent_review"]
    assert turn["status"] == "completed" and turn["consensus"] == ANSWER

    # Offered in every step of the agent, without the progress paragraph and
    # memory of comparison mode, and never check_text.
    assert script.offered and all("compare_models" in names and "check_text" not in names for names in script.offered)
    schema = loop.registry.tools["compare_models"].schema()["function"]
    assert set(schema["parameters"]["properties"]) == {"question", "context", "file_ids", "depth"}
    assert schema["description"].startswith("Ask the models the user chose for this chat the same question.")
    assert "At most 4 times per message." in schema["description"]

    # Every chosen model answered the question alone, with its own search,
    # in a conversation of its own: never one of the reviewers' sessions.
    assert sorted(family for family, _, _ in script.asked) == ["anthropic", "openai"]
    for _, messages, _ in script.asked:
        assert json.loads(messages[-1]["content"]) == {"question": QUESTION, "context": ""}
    reviewer_sessions = {session for sessions in script.session_ids.values() for session in sessions}
    assert not {session for _, _, session in script.asked} & reviewer_sessions

    # The run went on after the answers: a further tool, then the answer.
    assert [step for step, _ in script.calls if step.startswith("completion:")] == [
        "completion:0", "completion:1", "completion:2"]
    [result] = tool_results(loop, "compare_models")
    assert sorted(answer["text"] for answer in result["answers"]) == sorted(ADVICE.values())
    assert "still yours to do" in result["instruction"] and "write the answer" not in result["instruction"]
    assert "the app checks it" not in result["instruction"]
    assert not any(message.get("content") == prompt_defaults.AGENT_WRITE_NOTE for message in loop.messages)

    # No judge: the reviewers reviewed the answer, bound to it as a whole.
    assert loop.comparison.judge_calls == 0
    assert not any(e.get("kind") == "tool" and e.get("name") == "judge_answer" for e in events)
    assert review["mode"] == "audit" and review["status"] == "succeeded" and review["checks"] == []
    assert review_is_bound(review, ANSWER) and not review_is_bound(review, ANSWER + " changed")
    [comparison] = review["comparisons"]
    assert comparison["status"] == "succeeded" and len(comparison["answers"]) == 2
    assert review["versions"][-1]["comparison_ids"] == [comparison["id"]]
    assert {row["status"] for row in review["audit"]["reviewers"]} == {"completed"}

    # The reviewers read every answer in full in the log (in a live round:
    # the agent's next step called a tool), as model output, and were told
    # what compare_models is.
    rounds = [round_entries(message) for message in script.prompts["openai"] if message["role"] == "user"]
    entries = [entry for found, _ in rounds for entry in found or []]
    assert rounds[-1][1] == ANSWER and script.rounds["openai"][-1] == "final" and "live" in script.rounds["openai"]
    [compared] = [entry for entry in entries if entry["kind"] == "tool" and entry["name"] == "compare_models"]
    assert compared["data"] == "agent"
    assert sorted(item["text"] for item in compared["content"]["answers"]) == sorted(ADVICE.values())
    brief = next(entry for entry in entries if entry["kind"] == "context" and entry["name"] == "system")["content"]
    assert "compare_models asks the models the user chose" in brief["instructions"]


def test_without_the_switch_audit_mode_offers_no_comparison(store):
    script = Audit()
    loop = advised_loop(store, script, audit_compare=False)
    list(loop.run())
    assert script.offered and all("compare_models" not in names for names in script.offered)
    assert saved(store, loop)["status"] == "completed"


def test_with_the_answer_check_off_the_comparison_still_advises_and_the_turn_completes(store):
    script = Advised()
    loop = advised_loop(store, script, judges="off")
    list(loop.run())
    turn = saved(store, loop)
    review = turn["agent_review"]
    # Nobody reviews: the comparison stands as "off", bound to the answer.
    assert turn["status"] == "completed" and turn["consensus"] == ANSWER
    assert loop.comparison.auditor is None and loop.comparison.judge_calls == 0
    assert review["status"] == "off" and review_is_bound(review, ANSWER)
    assert script.rounds == {}


def test_one_answer_is_said_and_the_work_goes_on(store):
    script = Advised(advice={"anthropic": "330 metres.", "openai": RuntimeError("provider down")})
    loop = advised_loop(store, script)
    list(loop.run())
    [result] = tool_results(loop, "compare_models")
    assert result["instruction"].startswith("Only one model answered.")
    assert saved(store, loop)["status"] == "completed"


def test_the_agent_may_still_compare_after_it_read_a_page(store):
    """In comparison mode a read page ends comparing (the models must stay
    independent); in audit mode the agent searches and reads in every step,
    and the models see only its question."""
    script = Advised()
    loop = advised_loop(store, script)

    class Reader:
        reads = [{"status": "completed"}]

        @staticmethod
        def cited():
            return True

        @staticmethod
        def snapshot():
            return []
    loop.comparison.reader = Reader()
    list(loop.run())
    [result] = tool_results(loop, "compare_models")
    assert "error" not in result and len(result["answers"]) == 2
    assert "read_source" not in result["instruction"]


def test_a_comparison_entry_shows_every_answer_to_the_reviewers():
    """One log entry of the agent's compare_models result: its JSON text was
    cut at ENTRY_CHARS, so the second and third answers never reached the
    reviewers. It is read as structure now, each answer shortened alike."""
    answers = [{"text": f"Answer {n}: " + "x" * 9_000 + f" END-{n}", "sources": []} for n in range(3)]
    text = json.dumps({"comparison": 1, "question": QUESTION, "answers": answers, "missing_answers": [],
                       "sources": [], "instruction": "..."})
    assert len(text) > ENTRY_CHARS
    entry = {"seq": 7, "actor": "agent", "kind": "tool", "name": "compare_models", "data": "agent", "format": "text"}
    read = review_entry(entry, text)
    assert [item["text"] for item in read["content"]["answers"]] == [answer["text"] for answer in answers]
    # Beyond COMPARISON_ENTRY_CHARS each answer is shortened, none dropped.
    long = [{"text": f"Answer {n}: " + "y" * 30_000, "sources": []} for n in range(3)]
    read = review_entry(entry, json.dumps({"answers": long}))
    assert len(json.dumps(read["content"])) <= COMPARISON_ENTRY_CHARS
    assert [item["text"][:9] for item in read["content"]["answers"]] == ["Answer 0:", "Answer 1:", "Answer 2:"]
    # A round that must read its entries short still lists every answer.
    read = review_entry(entry, text, agent_audit.TIGHT_ENTRY_CHARS)
    assert len(read["content"]["answers"]) == 3
    # Other tool results stay one text, as before.
    other = review_entry({**entry, "name": "vm_exec"}, text)
    assert isinstance(other["content"], str) and len(other["content"]) < len(text)


@pytest.mark.parametrize("env, admin, allowed", [("", True, True), ("", False, False), ("all", False, True),
                                                 ("ALL ", False, True), ("admins", False, False)])
def test_compare_in_audit_is_for_admins_until_the_switch_opens_it(monkeypatch, env, admin, allowed):
    monkeypatch.setenv("AGENT_AUDIT_COMPARE", env)
    monkeypatch.setattr(agent_router, "is_user_admin", lambda uid: admin)
    assert agent_router.audit_compare_allowed("u1") is allowed


def test_an_unknown_tier_keeps_compare_in_audit_closed(monkeypatch):
    from app.core.security import TierStatusUnavailable
    monkeypatch.delenv("AGENT_AUDIT_COMPARE", raising=False)

    def unavailable(uid):
        raise TierStatusUnavailable("down")
    monkeypatch.setattr(agent_router, "is_user_admin", unavailable)
    assert agent_router.audit_compare_allowed("u1") is False

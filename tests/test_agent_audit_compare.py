"""compare_models (since 2026-10-31, in every chat run of the agent's one
mode): the agent may ask the user's chosen models its question. They answer
as advisers, each in a fresh conversation of its own, never the reviewers'
sessions; no judge runs; the reviewers read every answer in the work log;
and the run goes on after the answers, it does not end with them.
"""
import json
import time

import pytest

from app.api.routers import agent as agent_router
from app.services import agent_audit
from app.services.agent_audit import COMPARISON_ENTRY_CHARS, ENTRY_CHARS, review_entry
from app.services.agent_comparison import AgentPreferences, answer_hash, comparison_selection
from app.services.agent_delegation import DelegationLoop
from app.services.agent_delegation_config import defaults
from app.services.agent_policy import AgentPolicy
from app.services.agent_tools import ReadOnlyTool, ToolRegistry
from app.services.llm.agent_client import measured_usage, resolve_agent_model
from app.services.llm.provider_runtime import ProviderCancellation, ProviderCancelled, current_provider_cancellation
from test_agent_audit import ANSWER, Audit, LookupArgs, round_entries, saved
from test_agent_runs import UID, pending, store  # noqa: F401  (fixtures)


@pytest.fixture(autouse=True)
def _admin_allowance(monkeypatch):
    """The agent's five search rounds need an admin's 5M tokens a day (test_agent_audit)."""
    from app.services import agent_budget_config
    monkeypatch.setitem(agent_budget_config.DEFAULT_TIER_LIMITS, "pro", 5_000_000)


QUESTION = "How tall is the Eiffel Tower today, antennas included?"
# Longer together than one log entry (ENTRY_CHARS): cut as one text, the
# reviewers saw the first answer only.
ADVICE = {"anthropic": "Claude says 330 metres since the 2022 antenna. " + "C" * 7_000 + " END-CLAUDE",
          "openai": "GPT says 324 metres; the antenna is not counted. " + "G" * 7_000 + " END-GPT"}


class Advised(Audit):
    """A scripted turn whose agent asks the models (compare_models) in
    its first step: their answers come from ``advice`` by family. Then, by
    ``then``, it calls the tool ``note`` before it answers."""

    def __init__(self, *, advice=None, then=False, **kwargs):
        steps = {0: "compare_models", **({1: "note"} if then else {})}
        args = {0: {"question": QUESTION}, **({1: {"step": 1}} if then else {})}
        super().__init__(tool_steps=len(steps), step_tools=steps, step_args=args, **kwargs)
        self.advice = dict(ADVICE if advice is None else advice)
        # (family, messages, OpenRouter session) of every adviser's request.
        self.asked = []
        # Called when an adviser starts to wait ("wait" in ``advice``).
        self.on_wait = None

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
            if script.advice[family] == "wait":
                # Still answering: until it is stopped, at most a few seconds.
                if script.on_wait:
                    script.on_wait()
                stop, deadline = current_provider_cancellation(), time.monotonic() + 5
                while not stop.cancelled and time.monotonic() < deadline:
                    time.sleep(.01)
                if stop.cancelled:
                    raise ProviderCancelled("stopped")
                script.advice[family] = "A late answer."
            completion.text, completion.finish_reason = script.advice[family], "stop"
            yield {"type": "delta", "text": completion.text}
        completion.stream = advise
        return completion


def advised_loop(store, script, *, on_note=None):
    chat, turn = pending(store)
    config = {**defaults(), "enabled": False, "max_searches": 0}
    loop = DelegationLoop(store=store, uid=UID, chat_id=chat, turn_id=turn["id"],
        model=resolve_agent_model("claude-haiku-4-5"),
        messages=[{"role": "system", "content": "Answer."}, {"role": "user", "content": "Tell me about the Eiffel Tower."}],
        api_key="test", cancellation=ProviderCancellation(), policy=AgentPolicy.for_chat(config),
        delegation_config=config, completion_factory=script.factory,
        comparison_models=comparison_selection({"anthropic": "claude-haiku-4-5", "openai": "gpt-5.4-mini"}),
        agent_preferences=AgentPreferences())
    notes = []

    def note(args, *, cancellation):
        notes.append(args)
        if on_note:
            on_note()
        return {"text": "Noted."}
    loop.registry = ToolRegistry([*loop.registry.tools.values(), ReadOnlyTool("note", "Take a note.", LookupArgs, note)],
                                 argument_limit=loop.registry.argument_limit)
    script.loop, script.notes = loop, notes
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

    # Offered in every step of the agent, without a progress paragraph or a
    # memory field (comparison mode's, until 2026-10-31), and no check_text.
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
    assert len(script.notes) == 1 and "error" not in tool_results(loop, "note")[0]
    [result] = tool_results(loop, "compare_models")
    assert sorted(answer["text"] for answer in result["answers"]) == sorted(ADVICE.values())
    assert "still yours to do" in result["instruction"] and "write the answer" not in result["instruction"]
    assert "the app checks it" not in result["instruction"]
    # No note of the app after the answers: the next step is the agent's own.
    position = next(i for i, m in enumerate(loop.messages) if m.get("role") == "tool")
    assert loop.messages[position + 1]["role"] == "assistant"

    # No judge: the reviewers reviewed the answer, bound to it as a whole.
    assert not any(e.get("kind") == "tool" and e.get("name") == "judge_answer" for e in events)
    assert [e["status"] for e in events if e.get("kind") == "tool" and e.get("name") == "audit_answer"] == [
        "running", "succeeded"]
    assert review["mode"] == "audit" and review["status"] == "succeeded" and review["checks"] == []
    assert review["answer_hash"] == answer_hash(ANSWER) != answer_hash(ANSWER + " changed")
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


def test_a_comparison_past_the_answers_time_stops_waiting_even_for_one_model(store):
    """Until 2026-10-31 comparison mode waited at its deadline until two
    models answered (its check needed two); now nothing needs them, and one
    model may be all the user chose: it stops waiting at once, and the turn
    still ends with its answer instead of running into its hard stop."""
    script = Advised(advice={"anthropic": "wait", "openai": "wait"})
    loop = advised_loop(store, script)
    left = {"seconds": 10_000.0}
    loop.answer_time_left = lambda: left["seconds"]
    script.on_wait = lambda: left.update(seconds=0.0)
    started = time.monotonic()
    list(loop.run())
    assert time.monotonic() - started < 4
    [result] = tool_results(loop, "compare_models")
    assert result["instruction"].startswith("No model answered.")
    assert "under your answer" not in result["instruction"]
    turn = saved(store, loop)
    assert turn["status"] == "completed" and turn["consensus"] == ANSWER
    # The answer stopped them: their failures say so.
    [comparison] = turn["agent_review"]["comparisons"]
    assert {m["failure"]["code"] for m in comparison["failed_models"]} == {"late_cutoff"}


def test_a_stop_after_the_comparison_ends_the_reviewers_as_stopped(store):
    """Stopped before the answer, without live marks: the comparison saved
    the review with its reviewers at work; they end "stopped", not "failed,
    run_interrupted" (review 2026-10-31)."""
    script = Advised(then=True)
    loop = advised_loop(store, script, on_note=lambda: script.loop.cancellation.cancel())
    with pytest.raises(ProviderCancelled):
        list(loop.run())
    turn = saved(store, loop)
    assert turn["status"] == "failed" and turn["error_code"] == "cancelled"
    review = turn["agent_review"]
    assert review["mode"] == "audit" and review["status"] == "cancelled" and len(review["comparisons"]) == 1
    assert {row["status"] for row in review["audit"]["reviewers"]} == {"stopped"}


def test_one_answer_is_said_and_the_work_goes_on(store):
    script = Advised(advice={"anthropic": "330 metres.", "openai": RuntimeError("provider down")})
    loop = advised_loop(store, script)
    list(loop.run())
    [result] = tool_results(loop, "compare_models")
    assert result["instruction"].startswith("Only one model answered.")
    assert saved(store, loop)["status"] == "completed"


def test_the_agent_may_still_compare_after_it_read_a_page(store):
    """Until 2026-10-31 comparison mode ended comparing after a read page
    (the models had to stay independent); the agent searches and reads in
    every step, and the models see only its question."""
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


def test_a_failed_save_while_stopping_stragglers_costs_neither_the_review_nor_the_answer(store, monkeypatch):
    script = Advised()
    loop = advised_loop(store, script)

    def broken():
        raise RuntimeError("storage down")
    monkeypatch.setattr(loop.comparison, "finish_comparisons", broken)
    list(loop.run())
    turn = saved(store, loop)
    assert turn["status"] == "completed" and turn["consensus"] == ANSWER
    assert turn["agent_review"]["status"] == "succeeded"


def test_the_share_of_a_turn_with_comparisons_shows_no_comparison():
    """The models the agent asked answered its own question, not the user's:
    a share keeps saying only who answered (share_snapshots, review 2026-10-31)."""
    from app.services import share_snapshots
    review = {"mode": "audit", "answer_hash": "h", "checks": [], "comparisons": [
        {"id": "c1", "answers": [{"provider": "openai", "text": "330 metres."},
                                 {"provider": "anthropic", "text": "324 metres."}]}]}
    assert share_snapshots._agent_share_basis(review, ANSWER) == (None, None)


def answer_shape(n):
    """A compare_models result as _merged_result writes it: answers with the
    addresses they cite and the cited pages with excerpts."""
    return {"comparison": 1, "question": QUESTION, "context": "", "status": "succeeded",
            "answers": [{"text": f"Answer {i}: " + "z" * 9_000, "sources": [f"https://example.org/{i}/{j}" for j in range(8)]}
                        for i in range(n)],
            "missing_answers": [],
            "sources": [{"url": f"https://example.org/page/{j}", "title": f"Page {j}", "cited_by": 2,
                         "supports": ["The tower is 330 metres tall."], "excerpt": "e" * 700} for j in range(26)],
            "instruction": "..."}


def test_a_round_too_long_for_its_conversation_shortens_the_other_entries_before_the_answers():
    """Review 2026-10-31: one tier for every entry cut a 60,000-character
    comparison to 1,500 characters, and with its pages to the start of its
    first answer. Now the other entries give way first, then the pages'
    excerpts; every answer stays in the round."""
    from app.services.agent_audit import fitted_round
    compare = ({"seq": 4, "actor": "agent", "kind": "tool", "name": "compare_models", "data": "agent",
                "format": "text"}, json.dumps(answer_shape(5)))
    step = ({"seq": 5, "actor": "agent", "kind": "step", "name": "m", "data": "agent", "format": "json"},
            json.dumps({"reasoning": "r" * 5_000, "text": "", "tool_calls": [{"name": "note"}]}))
    full = fitted_round(2, [compare, step], 10**6)
    for room in (50_000, 20_000):
        message = fitted_round(2, [compare, step], room)
        assert message is not None and len(message) <= room < len(full)
        entries = json.loads(message.split("\n", 1)[1])["entries"]
        answers = entries[0]["content"]["answers"]
        assert [answer["text"][:9] for answer in answers] == [f"Answer {i}:" for i in range(5)]
        # The other entry gave way first.
        assert len(json.dumps(entries[1]["content"])) < 5_000


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

"""Summaries (agent_compaction.py "Summaries", since 2026-11-03), as Claude
Code and Codex compact a session whose context fills up: the chat model
summarizes a long chat's older history in the first step of the next
message, and a long run's earlier steps before its next one. The summary is
saved with the turn and starts every later message, byte for byte.
No test calls a provider.
"""
import json

from app.services import agent_compaction
from app.services.agent_compaction import (HISTORY_SUMMARY_OPEN, HISTORY_SUMMARY_PARTIAL, HISTORY_SUMMARY_REQUEST,
                                           RUN_SUMMARY_OPEN, RUN_SUMMARY_REQUEST, SUMMARY_CLOSE, history_keep,
                                           is_summary, run_summary_due, run_tail, summary_message, summary_text)
from app.services.agent_delegation import LONG_RUN_CONTEXT_SHARE, SUMMARY_TEXTS, DelegationLoop
from app.services.agent_runs import strip_app_context
from app.services.agent_work_log import context_data
from app.services.llm.agent_client import AgentCompletion, AgentModel, measured_usage
from test_agent_runs import UID, _answered, pending, receipt, store  # noqa: F401  (fixture)
from test_agent_vm import ANSWER, _admin_allowance, fake_vm, vm_loop  # noqa: F401  (fixtures)

SUMMARY = "The user builds a parser in /home/sprite/parser; tests pass except test_unicode. " * 5


class Summarizer:
    """A scripted agent like test_agent_vm.Agent: step N of the agent makes
    the tool calls ``steps[N]``, then it answers ANSWER. A summary request
    gets ``summary`` (or ``reply``, a function of the completion, for an
    unusable one); every request is kept in ``seen``."""

    def __init__(self, steps=(), summary=SUMMARY, reply=None):
        self.steps, self.summary, self.reply = list(steps), summary, reply
        self.seen, self.kwargs = [], []

    def factory(self):
        script = self

        class Completion(AgentCompletion):
            def stream(self, *, model, messages, **kwargs):
                self.usage = measured_usage({"prompt_tokens": 50, "completion_tokens": 20, "cost": .0001}, model)
                script.seen.append([dict(message) for message in messages])
                script.kwargs.append(kwargs)
                if messages[-1]["content"] in {HISTORY_SUMMARY_REQUEST, RUN_SUMMARY_REQUEST}:
                    if script.reply is not None:
                        script.reply(self)
                        return
                    self.text, self.finish_reason = script.summary, "stop"
                    yield {"type": "delta", "text": self.text}
                    return
                done = sum(1 for request in script.seen[:-1]
                           if request[-1]["content"] not in {HISTORY_SUMMARY_REQUEST, RUN_SUMMARY_REQUEST})
                if done < len(script.steps):
                    self.tool_calls = [{"id": f"call_{done}_{n}", "type": "function",
                                        "function": {"name": name, "arguments": json.dumps(arguments)}}
                                       for n, (name, arguments) in enumerate(script.steps[done])]
                    self.finish_reason = "tool_calls"
                    return
                self.text, self.finish_reason = ANSWER, "stop"
                yield {"type": "delta", "text": self.text}
        return Completion()

    def summary_requests(self):
        return [request for request in self.seen
                if request[-1]["content"] in {HISTORY_SUMMARY_REQUEST, RUN_SUMMARY_REQUEST}]


def stored(store, loop):
    return store._turn_ref(UID, loop.chat_id, loop.turn_id).get().to_dict()


# --- The pieces -------------------------------------------------------------------

def test_a_summary_is_never_the_users_words_and_is_bounded():
    message = summary_message("  notes  ")
    assert message["role"] == "user" and is_summary(message["content"])
    assert message["content"] == f"{HISTORY_SUMMARY_OPEN}\nnotes\n{SUMMARY_CLOSE}"
    assert summary_message("notes", run=True)["content"].startswith(RUN_SUMMARY_OPEN)
    assert HISTORY_SUMMARY_PARTIAL in summary_message("notes", partial=True)["content"]
    long = summary_message("x" * (agent_compaction.SUMMARY_MAX_CHARS + 500))["content"]
    assert len(long) < agent_compaction.SUMMARY_MAX_CHARS + 600 and "…" in long
    assert not is_summary("The user said: " + HISTORY_SUMMARY_OPEN) and not is_summary(None)
    # The work log files it as the agent's text, also in the chat's history.
    assert context_data("agent", 1, 5, message, message["content"]) == "agent"
    assert context_data("agent", 1, 5, {"role": "user", "content": "Hi"}, "Hi") == "user"


def test_only_a_complete_text_counts_as_summary():
    value = AgentCompletion()
    value.text, value.finish_reason = SUMMARY, "stop"
    assert summary_text(value) == SUMMARY.strip()
    for change in ({"finish_reason": "length"}, {"text": "Too short."},
                   {"tool_calls": [{"id": "c", "function": {"name": "vm_exec", "arguments": "{}"}}]},
                   {"output_limited": True}):
        other = AgentCompletion()
        other.text, other.finish_reason = SUMMARY, "stop"
        for key, item in change.items():
            setattr(other, key, item)
        assert summary_text(other) is None, change


def test_the_newest_history_stays_word_for_word_at_least_one_message():
    keep = agent_compaction.HISTORY_KEEP_CHARS
    assert history_keep([5_000] * 10) == keep // 5_000
    assert history_keep([keep * 3, 100]) == 1
    assert history_keep([100, keep * 3]) == 1
    assert history_keep([]) == 0


def run_messages(steps, size):
    messages = [{"role": "system", "content": "Answer."}, {"role": "user", "content": "Build it."}]
    for n in range(steps):
        messages.append({"role": "assistant", "content": "", "tool_calls": [
            {"id": f"c{n}", "type": "function", "function": {"name": "vm_exec", "arguments": "{}"}}]})
        messages.append({"role": "tool", "tool_call_id": f"c{n}", "content": "x" * size})
    return messages


def test_a_run_is_summarized_above_its_mark_while_most_of_it_is_its_own():
    messages = run_messages(10, 1_000)
    above = agent_compaction.RUN_SUMMARY_ABOVE_TOKENS
    assert not run_summary_due(above, 1_000_000, messages, 2)
    assert run_summary_due(above + 1, 1_000_000, messages, 2)
    # A smaller window brings the mark down to its share.
    assert run_summary_due(70_000, 100_000, messages, 2)
    # Mostly the chat's history (right after a summary of the run): not yet.
    assert not run_summary_due(above + 1, 1_000_000, [messages[0], {"role": "user", "content": "h" * 50_000},
                                                      *messages[1:4]], 2)
    # No step of the run yet: nothing of its own to summarize.
    assert not run_summary_due(above + 1, 1_000_000, messages[:2], 2)


def test_the_runs_latest_step_stays_when_it_is_small():
    messages = run_messages(4, 1_000)
    assert run_tail(messages, 2, len(messages)) == len(messages) - 2
    big = run_messages(4, agent_compaction.RUN_KEEP_CHARS + 1)
    assert run_tail(big, 2, len(big)) == len(big)
    assert run_tail(messages[:2], 2, 2) == 2


# --- The chat's history -----------------------------------------------------------

def _summarized(store, chat_id, request_id, through, content=None):
    """An earlier turn that wrote a summary covering positions up to ``through``."""
    _answered(store, chat_id, request_id, f"Answer {request_id}")
    turn = [t for t in store.history_page(UID, chat_id)["snapshots"]
            if (t.to_dict() or {}).get("question") == f"Question {request_id}"][0]
    content = content or summary_message(f"Summary through {through}")["content"]
    turn.reference.update({"agent_history_summary": {"content": content, "through": through, "turns": through}})
    return content


def test_later_messages_start_with_the_saved_summary_byte_for_byte(store):
    chat_id = store.create_chat(UID, execution_mode="agent")["id"]
    for index in range(3):
        _answered(store, chat_id, f"r{index}", f"Answer r{index}")
    first = _summarized(store, chat_id, "r3", 2)
    _answered(store, chat_id, "r4", "Answer r4")
    # A newer summary wins over an older one.
    newer = _summarized(store, chat_id, "r5", 4, summary_message("Summary through 4")["content"])
    _, target = pending(store, chat_id=chat_id, request_id="new", question="Continue")
    sources = []
    messages = store.messages(UID, chat_id, target, sources=sources)
    assert messages[1] == {"role": "user", "content": newer} and first != newer
    questions = [m["content"] for m in messages[2:-1] if m["role"] == "user"]
    # Positions 5 and 6 (r4 is position 5, r5 position 6) follow it.
    assert questions == ["Question r4", "Question r5"]
    assert strip_app_context(messages[-1]["content"]) == "Continue"


def test_the_plan_names_what_the_summary_replaces_and_what_stays(store, monkeypatch):
    monkeypatch.setattr(agent_compaction, "HISTORY_SUMMARY_ABOVE_CHARS", 30_000)
    monkeypatch.setattr(agent_compaction, "HISTORY_KEEP_CHARS", 10_000)
    chat_id = store.create_chat(UID, execution_mode="agent")["id"]
    for index in range(5):
        _answered(store, chat_id, f"r{index}", "x" * 8_000)
    _, target = pending(store, chat_id=chat_id, request_id="new", question="Continue")
    plan = {}
    messages = store.messages(UID, chat_id, target, summary=plan)
    # 40,000 characters held: the newest message (8,000) stays, four go.
    assert 40_000 <= plan.pop("held") < 41_000
    assert plan == {"end": 9, "through": 4, "turns": 4, "partial": False}
    assert messages[plan["end"]]["content"].endswith("Question r4")
    # A short chat plans nothing, and a Watch's run neither reads nor plans one.
    short = store.create_chat(UID, execution_mode="agent")["id"]
    _answered(store, short, "s0", "Short")
    _, target = pending(store, chat_id=short, request_id="s1", question="Continue")
    plan = {}
    store.messages(UID, short, target, summary=plan)
    assert plan == {}
    watched = store.create_chat(UID, execution_mode="agent")["id"]
    for index in range(5):
        _answered(store, watched, f"w{index}", "x" * 8_000)
    _summarized(store, watched, "w5", 3)
    _, target = pending(store, chat_id=watched, request_id="watch", question="Look again")
    plan = {}
    messages = store.messages(UID, watched, target, summary=plan, history_chars=100_000)
    assert plan == {} and not any(is_summary(m["content"]) for m in messages)


def test_the_summarized_turns_keep_their_sources_openable(store):
    chat_id = store.create_chat(UID, execution_mode="agent")["id"]
    _, turn = pending(store, chat_id=chat_id, request_id="r0", question="Question r0")
    value = receipt()
    store.claim(UID, chat_id, turn["id"], AgentModel())
    store.settle(UID, chat_id, turn["id"], completion=value, status="succeeded")
    store._turn_ref(UID, chat_id, turn["id"]).update(
        {"sources": [{"url": "https://example.com/old", "title": "Old"}]})
    _summarized(store, chat_id, "r1", 1)
    _, target = pending(store, chat_id=chat_id, request_id="new", question="Continue")
    sources = []
    messages = store.messages(UID, chat_id, target, sources=sources)
    assert "Question r0" not in json.dumps(messages)
    assert any(source.get("url") == "https://example.com/old" for source in sources)


def history_loop(store, script, *, partial=False):
    """A turn whose chat holds three earlier messages, the first two to be
    summarized (positions 1 and 2), the third kept."""
    loop = vm_loop(store, script, vm="off")
    loop.messages[1:] = [
        {"role": "user", "content": "Question one"}, {"role": "assistant", "content": "Answer one"},
        {"role": "user", "content": "Question two"}, {"role": "assistant", "content": "Answer two"},
        {"role": "user", "content": "Question three"}, {"role": "assistant", "content": "Answer three"},
        {"role": "user", "content": "Analyse my data."}]
    loop.turn_start = len(loop.messages)
    loop.history_end = loop.turn_start - 2
    loop.history_summary = {"end": 5, "through": 2, "turns": 2, "partial": partial}
    return loop


def test_the_first_step_summarizes_the_history_and_the_turn_keeps_it(store):
    script = Summarizer()
    loop = history_loop(store, script)
    events = list(loop.run())
    request, answer = script.seen
    # The summary request: only what it replaces, with the tools, the search
    # and the tool choice of the agent's steps (their cached prefix); a call
    # in it would not run.
    assert [m["content"] for m in request[1:]] == ["Question one", "Answer one", "Question two", "Answer two",
                                                     HISTORY_SUMMARY_REQUEST]
    assert script.kwargs[0]["allow_tool_calls"] is False
    for key in ("tools", "native_searches", "tool_choice"):
        assert script.kwargs[0][key] == script.kwargs[1][key]
    assert script.kwargs[0]["tool_choice"] == "auto" and script.kwargs[0]["native_searches"] > 0
    summary = summary_message(SUMMARY)["content"]
    # The agent's step: the summary, the kept message, the question.
    assert [m["content"] for m in answer[1:4]] == [summary, "Question three", "Answer three"]
    assert answer[4]["content"].endswith("Analyse my data.")
    turn = stored(store, loop)
    assert turn["agent_history_summary"] == {"content": summary, "through": 2, "turns": 2}
    assert turn["status"] == "completed" and turn["assistant_response"] == ANSWER
    assert any(e.get("type") == "activity" and e.get("text") == SUMMARY_TEXTS["history"] for e in events)
    # Claimed and billed like any step: the summary is step 0, the answer step 1.
    for step in ("completion:0", "completion:1"):
        assert store.receipt_ref(UID, loop.chat_id, loop.turn_id, step).get().to_dict()["status"] == "succeeded"
    assert loop.turn_start == 5 and loop.history_end == 3


def test_a_history_summary_that_does_not_work_out_changes_nothing(store):
    def too_short(completion):
        completion.text, completion.finish_reason = "Short.", "stop"
    script = Summarizer(reply=too_short)
    loop = history_loop(store, script)
    list(loop.run())
    request, answer = script.seen
    assert [m["content"] for m in answer[1:7]] == ["Question one", "Answer one", "Question two", "Answer two",
                                                   "Question three", "Answer three"]
    turn = stored(store, loop)
    assert "agent_history_summary" not in turn and turn["status"] == "completed"
    # The turn keeps the mark: the next message waits for the history to grow.
    assert turn["agent_history_summary_failed"] == {"held": 0}


def _failed_summary(store, chat_id, request_id, held, answer="Done."):
    """An earlier turn whose history summary did not work out at ``held``."""
    _answered(store, chat_id, request_id, answer)
    turn = [t for t in store.history_page(UID, chat_id)["snapshots"]
            if (t.to_dict() or {}).get("question") == f"Question {request_id}"][0]
    turn.reference.update({"agent_history_summary_failed": {"held": held}})


def test_after_a_history_summary_that_did_not_work_out_the_next_waits_for_growth(store, monkeypatch):
    monkeypatch.setattr(agent_compaction, "HISTORY_SUMMARY_ABOVE_CHARS", 30_000)
    monkeypatch.setattr(agent_compaction, "HISTORY_KEEP_CHARS", 10_000)
    monkeypatch.setattr(agent_compaction, "HISTORY_SUMMARY_RETRY_CHARS", 10_000)
    chat_id = store.create_chat(UID, execution_mode="agent")["id"]
    for index in range(5):
        _answered(store, chat_id, f"r{index}", "x" * 8_000)
    _failed_summary(store, chat_id, "f0", 40_000)

    def plan(position):
        planned = {}
        store.messages(UID, chat_id, {"position": position, "question": "Continue"}, summary=planned)
        return planned
    assert plan(7) == {}
    # Grown by the retry margin since: planned again.
    _answered(store, chat_id, "r5", "y" * 10_000)
    assert plan(8)["held"] >= 50_000


def test_a_partial_history_says_so_in_its_summary(store):
    script = Summarizer()
    loop = history_loop(store, script, partial=True)
    list(loop.run())
    assert HISTORY_SUMMARY_PARTIAL in stored(store, loop)["agent_history_summary"]["content"]


def test_memory_evidence_never_takes_a_summary_for_the_users_words(store):
    loop = vm_loop(store, Summarizer(), vm="off")
    summary = summary_message(SUMMARY)
    fresh = DelegationLoop(store=store, uid=UID, chat_id=loop.chat_id, turn_id=loop.turn_id, model=loop.model,
                           messages=[loop.messages[0], summary, {"role": "user", "content": "Go on."}],
                           api_key="test", cancellation=loop.cancellation, policy=loop.policy,
                           delegation_config=loop.config, completion_factory=Summarizer().factory,
                           comparison_models=None)
    assert [m["content"] for m in fresh.answer_conversation] == ["Go on."]


# --- A long run -------------------------------------------------------------------

def test_a_long_run_summarizes_its_steps_and_goes_on(store, fake_vm, monkeypatch):
    calls = [[("vm_exec", {"command": f"make step{n}"})] for n in range(6)]
    script = Summarizer(calls)
    loop = vm_loop(store, script)
    seen = []

    def due(inputs, context_length, messages, start):
        # After the third command, once.
        commands = sum(1 for m in messages[start:] if m.get("role") == "tool")
        seen.append(commands)
        return commands >= 3 and not loop.run_summaries
    monkeypatch.setattr(agent_compaction, "run_summary_due", due)
    events = list(loop.run())
    requests = script.summary_requests()
    assert len(requests) == 1
    # The summary request is the next step's request with the request at its end.
    index = script.seen.index(requests[0])
    after = script.seen[index + 1]
    assert requests[0][-1]["content"] == RUN_SUMMARY_REQUEST
    # It may only write, in the request of the steps around it.
    assert script.kwargs[index]["allow_tool_calls"] is False
    for key in ("tools", "native_searches", "tool_choice"):
        assert script.kwargs[index][key] == script.kwargs[index - 1][key] == script.kwargs[index + 1][key]
    # The next step: the question, the summary, then the latest step whole.
    start = next(n for n, m in enumerate(after) if strip_app_context(str(m.get("content"))).endswith("Analyse my data."))
    assert after[start + 1]["content"] == summary_message(SUMMARY, run=True)["content"]
    assert after[start + 2]["role"] == "assistant"
    kept_calls = [call["function"]["arguments"] for m in after[start + 2:] if m.get("role") == "assistant"
                  for call in m.get("tool_calls") or []]
    assert json.loads(kept_calls[0])["command"] == "make step2"
    turn = stored(store, loop)
    assert turn["status"] == "completed" and turn["assistant_response"] == ANSWER
    # The work record still lists every command, the summarized ones too.
    record = turn["agent_work_record"]
    assert all(f"make step{n}" in record for n in range(6))
    assert any(e.get("type") == "activity" and e.get("text") == SUMMARY_TEXTS["run"] for e in events)
    assert "agent_history_summary" not in turn


def test_a_run_summary_that_does_not_work_out_waits_for_the_run_to_grow(store, fake_vm, monkeypatch):
    def tool_call_instead(completion):
        completion.tool_calls = [{"id": "x", "type": "function",
                                  "function": {"name": "vm_exec", "arguments": json.dumps({"command": "echo never-run"})}}]
        completion.finish_reason = "tool_calls"
    calls = [[("vm_exec", {"command": f"make step{n}"})] for n in range(4)]
    script = Summarizer(calls, reply=tool_call_instead)
    loop = vm_loop(store, script)
    monkeypatch.setattr(agent_compaction, "run_summary_due",
                        lambda inputs, context_length, messages, start: any(m.get("role") == "tool"
                                                                            for m in messages[start:]))
    list(loop.run())
    # The run's next requests stay far below RUN_SUMMARY_RETRY_TOKENS more.
    assert len(script.summary_requests()) == 1 and loop.run_summary_retry_at is not None
    turn = stored(store, loop)
    assert turn["status"] == "completed" and turn["assistant_response"] == ANSWER
    # Its call never ran.
    assert "never-run" not in json.dumps(fake_vm.calls, default=str)
    assert all(not is_summary(str(m.get("content"))) for m in script.seen[-1])


def test_a_failed_run_summary_is_tried_again_once_the_run_has_grown(store, fake_vm, monkeypatch):
    attempts = []

    def first_fails(completion):
        attempts.append(1)
        if len(attempts) == 1:
            completion.text, completion.finish_reason = "Short.", "stop"
        else:
            completion.text, completion.finish_reason = SUMMARY, "stop"
    calls = [[("vm_exec", {"command": f"make step{n}"})] for n in range(5)]
    script = Summarizer(calls, reply=first_fails)
    loop = vm_loop(store, script)
    monkeypatch.setattr(agent_compaction, "RUN_SUMMARY_RETRY_TOKENS", 1)
    monkeypatch.setattr(agent_compaction, "run_summary_due",
                        lambda inputs, context_length, messages, start: not loop.run_summaries and sum(
                            1 for m in messages[start:] if m.get("role") == "tool") >= 2)
    list(loop.run())
    assert len(script.summary_requests()) == 2 and loop.run_summaries == 1
    assert stored(store, loop)["assistant_response"] == ANSWER


def test_a_run_is_summarized_before_it_would_end_at_the_window():
    """Before summaries a long run at LONG_RUN_CONTEXT_SHARE of the window
    wrote its answer (TURN_CONTEXT_LIMIT); the summary comes first."""
    assert agent_compaction.RUN_SUMMARY_WINDOW_SHARE < LONG_RUN_CONTEXT_SHARE


# --- As Claude Code and Codex keep it (2026-11-03) --------------------------------

def test_the_app_adds_the_plan_and_the_processes_to_a_run_summary():
    state = agent_compaction.run_state([{"content": "Write the parser", "status": "completed"},
                                        {"content": "Fix test_unicode", "status": "in_progress"},
                                        {"content": "Answer", "status": "pending"}], {"p2", "p1"})
    assert state.splitlines() == [
        agent_compaction.RUN_STATE_OPEN, "Your plan (update_plan):", "- [x] Write the parser",
        "- [in progress] Fix test_unicode", "- [ ] Answer",
        "Background processes started in this message: p1, p2 (vm_process_output without id lists them and "
        "whether they still run)."]
    assert agent_compaction.run_state() == ""
    content = summary_message("notes", run=True, state=state)["content"]
    assert content.endswith(f"notes\n\n{state}\n{SUMMARY_CLOSE}") and is_summary(content)
    # The agent goes on from it instead of starting over (Claude Code, Codex).
    assert "goes on from here" in agent_compaction.RUN_SUMMARY_OPEN
    assert "instead of repeating it" in agent_compaction.RUN_SUMMARY_OPEN


def test_a_history_summary_moves_what_the_run_appended_after_its_question(store):
    """Whatever stands after the question before the first step (the run's
    own) moves up with it: the run's start is not the end of the list."""
    script = Summarizer()
    loop = history_loop(store, script)
    loop.messages.append({"role": "user", "content": "[consens.io: an app note of this run]"})
    list(loop.run())
    answer = script.seen[1]
    assert strip_app_context(answer[4]["content"]).endswith("Analyse my data.")
    assert answer[5]["content"] == "[consens.io: an app note of this run]"
    assert (loop.turn_start, loop.history_end) == (5, 3)


def test_a_run_summary_keeps_the_users_messages_and_the_apps_state(store, fake_vm, monkeypatch):
    from app.services.agent_delegation import USER_NOTE_OPEN
    note = {"role": "user", "content": USER_NOTE_OPEN + "\nPlease also add a test for emoji."}
    plan = [{"content": "Build the parser", "status": "completed"}, {"content": "Test it", "status": "in_progress"}]
    calls = [[("update_plan", {"items": plan})], *[[("vm_exec", {"command": f"make step{n}"})] for n in range(5)]]
    script = Summarizer(calls)
    loop = vm_loop(store, script)

    def due(inputs, context_length, messages, start):
        commands = sum(1 for m in messages[start:] if m.get("role") == "tool")
        if commands >= 4 and not loop.run_summaries:
            # The user wrote into the run after its first steps.
            messages.insert(start + 2, note)
            loop.vm_tools.processes.started.add("dev-server-1")
            return True
        return False
    monkeypatch.setattr(agent_compaction, "run_summary_due", due)
    list(loop.run())
    request = script.summary_requests()[0]
    after = script.seen[script.seen.index(request) + 1]
    start = next(n for n, m in enumerate(after) if strip_app_context(str(m.get("content"))).endswith("Analyse my data."))
    # The user's message word for word, then the summary with the app's state.
    assert after[start + 1] == note
    summary = after[start + 2]["content"]
    assert summary.startswith(agent_compaction.RUN_SUMMARY_OPEN)
    assert "- [x] Build the parser" in summary and "- [in progress] Test it" in summary
    assert "dev-server-1" in summary
    assert stored(store, loop)["assistant_response"] == ANSWER

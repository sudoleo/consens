"""Summaries (agent_compaction.py "Summaries"), as Claude
Code and Codex compact a session whose context fills up: the chat model
summarizes a long chat's older history in the first step of the next
message, and a long run's earlier steps before its next one. The summary is
saved with the turn and starts every later message, byte for byte.
No test calls a provider.
"""
import json

import pytest

from app.services import agent_compaction, agent_delegation
from app.services.agent_compaction import (HISTORY_SUMMARY_OPEN, HISTORY_SUMMARY_PARTIAL, HISTORY_SUMMARY_REQUEST,
                                           RUN_SUMMARY_OPEN, RUN_SUMMARY_REQUEST, SUMMARY_CLOSE, history_keep,
                                           is_summary, run_summary_due, run_tail, summary_message, summary_text)
from app.services.agent_delegation import LONG_RUN_CONTEXT_SHARE, SUMMARY_TEXTS, DelegationLoop
from app.services.agent_provider_limits import ModelDeclined
from app.services.agent_runs import strip_app_context
from app.services.agent_work_log import context_data
from app.services.llm.agent_client import (AgentCompletion, AgentModel, AgentStreamIncomplete, answer_output_limit,
                                           measured_usage, resolve_agent_model)
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

def test_the_run_summary_request_leaves_out_the_sentence_azure_declines():
    """Azure's filter declined every run summary of GPT-6.1 Terra, at 0
    tokens, for the sentence asking for "a summary of your work on it so
    far, everything after the user's question" (probes 2026-11-12)."""
    assert "everything after the user's question" not in RUN_SUMMARY_REQUEST
    assert "summary of your work" not in RUN_SUMMARY_REQUEST


def test_the_history_summary_request_asks_as_the_run_summary_request_does():
    """Azure's filter declined Terra's history summaries too, asked for as
    "a summary of the conversation above that will replace it"."""
    assert "Write a summary" not in HISTORY_SUMMARY_REQUEST
    assert "will be replaced by notes you write now" in HISTORY_SUMMARY_REQUEST
    assert "will be replaced by notes you write now" in " ".join(RUN_SUMMARY_REQUEST.split())


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
    # The summary request: only what it replaces, no tools to call.
    assert [m["content"] for m in request[1:]] == ["Question one", "Answer one", "Question two", "Answer two",
                                                     HISTORY_SUMMARY_REQUEST]
    assert script.kwargs[0]["allow_tool_calls"] is False
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

    def due(inputs, context_length, messages, start, end_at=None):
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
    assert script.kwargs[index].get("allow_tool_calls") is not False
    assert script.kwargs[index]["tools"] == script.kwargs[index - 1]["tools"]
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


def test_a_run_summary_that_does_not_work_out_is_not_tried_again(store, fake_vm, monkeypatch):
    def tool_call_instead(completion):
        completion.tool_calls = [{"id": "x", "type": "function",
                                  "function": {"name": "vm_exec", "arguments": json.dumps({"command": "echo never-run"})}}]
        completion.finish_reason = "tool_calls"
    calls = [[("vm_exec", {"command": f"make step{n}"})] for n in range(4)]
    script = Summarizer(calls, reply=tool_call_instead)
    loop = vm_loop(store, script)
    monkeypatch.setattr(agent_compaction, "run_summary_due",
                        lambda inputs, context_length, messages, start, end_at=None: any(
                            m.get("role") == "tool" for m in messages[start:]))
    list(loop.run())
    assert len(script.summary_requests()) == 1
    turn = stored(store, loop)
    assert turn["status"] == "completed" and turn["assistant_response"] == ANSWER
    # Its call never ran.
    assert "never-run" not in json.dumps(fake_vm.calls, default=str)
    assert all(not is_summary(str(m.get("content"))) for m in script.seen[-1])


def refused(completion):
    """The provider's filter ends the summary request with its refusal line,
    as GPT-6.1 Terra on Azure did with each of its run summaries while every
    step around them passed; the client reads a stop with text as a stream
    that broke off."""
    completion.text, completion.finish_reason = "I'm sorry, but I cannot assist with that request.", "content_filter"
    completion.endpoint = "Azure"
    raise AgentStreamIncomplete("finish=content-filter native=content-filter text=49 tool_parts=0 output_tokens=0")


def declined_on_azure(completion):
    completion.endpoint = "Azure"
    raise ModelDeclined()


def broke_off(completion):
    completion.endpoint = "Azure"
    raise AgentStreamIncomplete("finish=stop native=stop text=0 tool_parts=0 output_tokens=0")


def declined(completion):
    raise ModelDeclined()


def every_step_after_a_command(monkeypatch):
    monkeypatch.setattr(agent_compaction, "run_summary_due",
                        lambda inputs, context_length, messages, start, end_at=None: any(
                            m.get("role") == "tool" for m in messages[start:]))


def summarized_run(store, monkeypatch, reply):
    """A run of three commands whose every step after one is due for a
    summary, and the summary request gets ``reply``. Returns the script, the
    loop and the run's events."""
    monkeypatch.setattr(agent_delegation, "PASSING_RETRY_SECONDS", 0)
    every_step_after_a_command(monkeypatch)
    script = Summarizer([[("vm_exec", {"command": f"make step{n}"})] for n in range(3)], reply=reply)
    loop = vm_loop(store, script)
    return script, loop, list(loop.run())


def assert_the_run_went_on_whole(store, fake_vm, script, loop):
    turn = stored(store, loop)
    assert turn["status"] == "completed" and turn["assistant_response"] == ANSWER and "agent_failure" not in turn
    assert all(f"make step{n}" in json.dumps(fake_vm.calls, default=str) for n in range(3))
    assert all(not is_summary(str(m.get("content"))) for m in script.seen[-1])
    # Every step settled, so each next one could claim its index; none was skipped.
    receipts = [store.receipt_ref(UID, loop.chat_id, loop.turn_id, f"completion:{n}").get()
                for n in range(len(script.seen))]
    assert all(r.exists and r.to_dict()["status"] == "succeeded" for r in receipts)


def test_a_run_summary_that_broke_off_tries_once_more_and_the_run_goes_on(store, fake_vm, monkeypatch):
    script, loop, events = summarized_run(store, monkeypatch, broke_off)
    assert len(script.summary_requests()) == 2
    assert any(e.get("type") == "activity" and e.get("text") == agent_delegation.PASSING_RETRY_TEXT for e in events)
    assert_the_run_went_on_whole(store, fake_vm, script, loop)


@pytest.mark.parametrize("reply", [refused, declined_on_azure])
def test_a_run_summary_the_filter_stops_is_left_out_at_once(store, fake_vm, monkeypatch, reply):
    """Asked once more, it met the same filter on the same endpoint and an
    HTTP 400 on another; the user waited for it and read that the model's
    reply broke off."""
    script, loop, events = summarized_run(store, monkeypatch, reply)
    assert len(script.summary_requests()) == 1
    assert not any(e.get("text") == agent_delegation.PASSING_RETRY_TEXT for e in events)
    assert_the_run_went_on_whole(store, fake_vm, script, loop)


def test_a_declined_history_summary_leaves_the_history_whole(store):
    script = Summarizer(reply=declined)
    loop = history_loop(store, script)
    list(loop.run())
    request, answer = script.seen
    assert [m["content"] for m in answer[1:7]] == ["Question one", "Answer one", "Question two", "Answer two",
                                                   "Question three", "Answer three"]
    turn = stored(store, loop)
    assert "agent_history_summary" not in turn and turn["status"] == "completed"
    assert store.receipt_ref(UID, loop.chat_id, loop.turn_id, "completion:0").get().to_dict()["status"] == "succeeded"


def test_a_run_is_summarized_before_it_would_end_at_the_window():
    """A long run at LONG_RUN_CONTEXT_SHARE of the window writes its answer
    (TURN_CONTEXT_LIMIT); the summary comes before that."""
    assert agent_compaction.RUN_SUMMARY_WINDOW_SHARE < LONG_RUN_CONTEXT_SHARE
    # Also where the answer's allowance is large: a long run of Haiku 4.5
    # ends at 0.8 x 200k less its answer, before 100k.
    model = resolve_agent_model("claude-haiku-4-5")
    end_at = model.context_length * LONG_RUN_CONTEXT_SHARE - answer_output_limit(model)
    assert end_at < agent_compaction.RUN_SUMMARY_ABOVE_TOKENS
    messages = run_messages(4, 40_000)
    assert not run_summary_due(int(end_at) - 1, model.context_length, messages, 2)
    assert run_summary_due(int(end_at) + 1, model.context_length, messages, 2, end_at=end_at)
    assert not run_summary_due(int(end_at), model.context_length, messages, 2, end_at=end_at)


def test_a_long_run_tells_its_summary_where_it_would_end(store, fake_vm, monkeypatch):
    seen = []

    def due(inputs, context_length, messages, start, end_at=None):
        seen.append(end_at)
        return False
    monkeypatch.setattr(agent_compaction, "run_summary_due", due)
    loop = vm_loop(store, Summarizer([[("vm_exec", {"command": "make"})]]))
    list(loop.run())
    model = loop.routing_lighter or loop.model
    # Before the VM started the run is no long run yet.
    assert seen[0] is None
    assert seen[-1] == model.context_length * LONG_RUN_CONTEXT_SHARE - answer_output_limit(model)


def test_a_run_ending_at_its_step_limit_answers_without_a_summary_first(store, fake_vm, monkeypatch):
    """A summary of a run that ends anyway would cost time and money, and
    the answer would come from the shorter version."""
    calls = [[("vm_exec", {"command": f"make step{n}"})] for n in range(3)]
    script = Summarizer(calls)
    loop = vm_loop(store, script)
    monkeypatch.setattr(agent_compaction, "run_summary_due",
                        lambda inputs, context_length, messages, start, end_at=None: sum(
                            1 for m in messages[start:] if m.get("role") == "tool") >= 3)
    loop._turn_limit = lambda: agent_delegation.TURN_STEP_LIMIT if loop.routing_steps >= 3 else None
    list(loop.run())
    assert script.summary_requests() == []
    turn = stored(store, loop)
    assert turn["status"] == "completed" and turn["assistant_response"] == ANSWER
    # A context that no longer holds the answer is still summarized first.
    script = Summarizer(calls)
    loop = vm_loop(store, script, request_id="two")
    loop._turn_limit = lambda: agent_delegation.TURN_STEP_LIMIT if loop.routing_steps >= 3 else None
    # It does not fit until the run is summarized.
    loop._answer_fits = lambda: bool(loop.run_summaries)
    list(loop.run())
    assert len(script.summary_requests()) == 1


# --- As Claude Code and Codex keep it ---------------------------------------------

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

    def due(inputs, context_length, messages, start, end_at=None):
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

"""The Agent writes its answer itself (agent_answer_mode): its plain-text
message without tool calls is the answer; after a comparison the step that
reads the answers writes it, a direct answer is one call.

Until 2026-10-14 this was the merged path behind AGENT_MERGED_ANSWER next to
a separate, tool-free answer step (git tag agent-separate-answer-last); now
it is the only path. test_agent_comparison covers the checks and accounting
with the shared Script; these tests cover streaming, holding back and
retracting the answer text, the write note, memory and Watch replies, limits
and the live evaluation script.
"""
from dataclasses import replace
import json
import re
import sys

import pytest

from app.services import agent_answer_mode, agent_budget_config, agent_delegation, agent_memory, agent_quota, prompt_defaults
from app.services.agent_comparison import comparison_selection, review_is_bound
from app.services.agent_delegation import DelegationLoop
from app.services.agent_delegation_config import defaults
from app.services.agent_policy import AgentPolicy
from app.services.llm.agent_client import measured_usage, resolve_agent_model
from app.services.agent_provider_limits import ModelOutputLimit, ProviderCooldowns
from app.services.llm.engines import _ProviderHTTPStatusError
from app.services.llm.provider_runtime import AnalysisBudgetExceeded, ProviderCancellation
from test_agent_comparison import Script
from test_agent_memory import repo, set_profile
from test_agent_runs import UID, api, pending, store  # noqa: F401  (fixtures)


ANSWER = ("The first option costs 100 euros a month and includes the support plan. "
          "The second option is cheaper at first but adds fees once the team grows, "
          "so over two years the first option ends up cheaper for a team of ten. ") * 3
# A long comparison answer: the agent reads it whole (no routing gist).
MODEL_ANSWER = "The first option costs 100. The constraint matters. " + "Details on pricing. " * 500
COMPARE = ("compare_models", {"question": "Which option is cheaper over two years?", "context": "Team of ten.",
                              "status_update": "Comparing the options."})


def tool_call(index, n, name, args):
    return {"id": f"call_{index}_{n}", "type": "function", "function": {"name": name, "arguments": json.dumps(args)}}


class Merged(Script):
    """A scripted Agent turn. ``plan[i]`` is what step completion:i does:
    ``text`` (streamed in chunks of 50), then ``tools`` [(name, args)];
    ``sources`` arrive before the text (the step's own search found them)."""

    def __init__(self, plan, *, memory=None, cited=(), **kwargs):
        super().__init__(**kwargs)
        self.plan = plan
        self.memory = memory
        self.cited = cited
        self.requests, self.kwargs = {}, {}
        # Output limit of each orchestrator step's request.
        self.limits = {}

    def factory(self):
        base = type(super().factory())
        script = self

        class Completion(base):
            def stream(self, *, model, messages, **kwargs):
                if not self.step_id.startswith("completion:"):
                    schema = (model.request_config.get("response_format") or {}).get("json_schema")
                    if schema:
                        yield from super().stream(model=model, messages=messages, **kwargs)
                        return
                    # A comparison answer.
                    script.calls.append((self.step_id, model.model))
                    self.usage = measured_usage({"prompt_tokens": 50, "completion_tokens": 20, "cost": .0001}, model)
                    self.text, self.finish_reason = MODEL_ANSWER, "stop"
                    self.sources = [{"url": url, "title": "Report"} for url in script.cited]
                    yield {"type": "delta", "text": self.text}
                    return
                index = int(self.step_id.split(":")[-1])
                script.calls.append((self.step_id, model.model))
                script.requests[index] = json.loads(json.dumps(messages))
                script.kwargs[index] = {key: value for key, value in kwargs.items() if key != "api_key"}
                script.limits[index] = model.max_output_tokens
                script.tools = [tool["function"] for tool in kwargs.get("tools") or [] if tool.get("type") == "function"]
                step = script.plan[min(index, len(script.plan) - 1)]
                if step.get("rate_limited"):
                    # Refused before any output: free (record_rejection).
                    raise _ProviderHTTPStatusError(429, retry_after=1)
                self.usage = measured_usage({"prompt_tokens": 50, "completion_tokens": 20, "cost": .0001}, model)
                if step.get("sources"):
                    self.sources = list(step["sources"])
                    self._results_at = 0
                text = step.get("text", "")
                for start in range(0, len(text), 50):
                    chunk = text[start:start + 50]
                    self.text += chunk
                    yield {"type": "delta", "text": chunk}
                if step.get("cut"):
                    # A tool call cut in half at the output limit: the client
                    # marks it and raises (AgentCompletion._output_limited).
                    self.finish_reason, self.output_limited = "length", True
                    raise ModelOutputLimit()
                calls = []
                for n, (name, args) in enumerate(step.get("tools", ())):
                    if script.memory is not None and name in {"compare_models", "check_text"} and "memory" not in args:
                        args = {**args, "memory": script.memory if n == 0 and index == 0 else []}
                    calls.append(tool_call(index, n, name, args))
                if calls:
                    self._tool_parts = dict(enumerate(calls))
                    self.tool_calls, self.finish_reason = calls, "tool_calls"
                else:
                    self.finish_reason = step.get("finish", "stop")
        return Completion()


def merged_loop(store, script, *, messages=None, memory=None, check_sources=False):
    chat, turn = pending(store)
    config = {**defaults(), "enabled": False, "max_searches": 0}
    loop = DelegationLoop(store=store, uid=UID, chat_id=chat, turn_id=turn["id"],
        model=resolve_agent_model("claude-haiku-4-5"),
        messages=messages or [{"role": "system", "content": "Answer."},
                              {"role": "user", "content": "Which option is cheaper?"}],
        api_key="test", cancellation=ProviderCancellation(), policy=AgentPolicy.for_chat(config),
        delegation_config=config, completion_factory=script.factory, check_sources=check_sources,
        comparison_models=comparison_selection({"anthropic": "claude-haiku-4-5", "openai": "gpt-5.4-mini"}),
        memory=memory)
    script.loop = loop
    return loop


def deltas(events):
    return "".join(event["text"] for event in events if event.get("type") == "delta")


def retractions(events):
    return [event for event in events if event.get("kind") == "status" and event.get("clear_response")]


def shown(events):
    """What the browser shows at the end (agent-chat.js): a delta appends, a
    retraction clears."""
    clears = [i for i, event in enumerate(events) if event.get("kind") == "status" and event.get("clear_response")]
    return deltas(events[clears[-1] + 1:] if clears else events)


def orchestrator_steps(script):
    return [step for step, _ in script.calls if step.startswith("completion:")]


def tool_result(loop, call_id):
    return json.loads(next(m["content"] for m in loop.messages
                           if m.get("role") == "tool" and m.get("tool_call_id") == call_id))


# --- Prompts and tools -----------------------------------------------------------

def test_every_turn_with_comparison_tools_writes_its_own_answer(store):
    """No switch any more: chat turns and bounded runs alike have no answer
    tool and get the writing rules."""
    from test_agent_comparison import make_loop
    for loop in (merged_loop(store, Merged([{}])), make_loop(store, Script())):
        assert loop.merged and "answer" not in loop.registry.tools
        assert prompt_defaults.AGENT_ANSWER_SECTION in loop.messages[0]["content"]


def test_no_prompt_points_to_the_removed_answer_step():
    from app.services import agent_read_source, agent_watch
    assert prompt_defaults.AGENT_SYSTEM_PROMPT == (prompt_defaults._AGENT_STEERING + "\n\n"
                                                   + prompt_defaults.AGENT_ANSWER_SECTION)
    reading = prompt_defaults.AGENT_SYSTEM_PROMPT
    for old, new in prompt_defaults.AGENT_READ_SOURCE_REPLACEMENTS:
        assert reading.count(old) == 1, old
        reading = reading.replace(old, new)
    for text in (prompt_defaults.AGENT_SYSTEM_PROMPT, reading, prompt_defaults.AGENT_READ_SOURCE_PROMPT,
                 prompt_defaults.AGENT_WRITE_NOTE, agent_memory.MEMORY_WRITE_PROMPT, agent_watch.ORCHESTRATOR_PROMPT,
                 agent_read_source.UNTRUSTED_NOTE):
        assert "call answer" not in text and "answer step" not in text and "answer call" not in text, text[:80]


def test_the_steering_prompt_has_the_writing_reading_and_memory_rules(store, monkeypatch):
    monkeypatch.delenv("AGENT_READ_SOURCES", raising=False)
    set_profile(store.db, auto_memory=True)
    loop = merged_loop(store, Merged([{}]), memory=repo(store).snapshot(UID), messages=[
        {"role": "system", "content": prompt_defaults.AGENT_SYSTEM_PROMPT}, {"role": "user", "content": "Hi"}])
    system = loop.messages[0]["content"]
    assert system.startswith(prompt_defaults.AGENT_SYSTEM_PROMPT.split("COMPARE OR ANSWER DIRECTLY")[0])
    # The code prompt already carries the writing rules: not appended twice.
    assert system.count("WRITING THE ANSWER") == 1 and "READING SOURCES" in system
    assert "Include status_update in every compare_models, check_text and read_source call" in system
    assert "call answer" not in system
    assert "compare_models and check_text carry a required" in system
    names = list(loop.registry.tools)
    assert "answer" not in names and {"compare_models", "check_text", "read_source", "update_memory"} <= set(names)
    # The required memory decision rides on the calls that start the work.
    for name in ("compare_models", "check_text"):
        schema = loop.registry.tools[name].schema()["function"]["parameters"]
        assert "memory" in schema["properties"] and "memory" in schema["required"]
    assert "answer without a comparison" in loop.registry.tools["update_memory"].description


def test_a_custom_steering_prompt_still_gets_the_writing_rules(store):
    loop = merged_loop(store, Merged([{}]))
    system = loop.messages[0]["content"]
    assert system.startswith("Answer.") and prompt_defaults.AGENT_ANSWER_SECTION in system


# --- Comparison and answer in one call -------------------------------------------

def test_the_step_that_reads_the_answers_writes_the_checked_answer(store):
    script = Merged([{"tools": [COMPARE]}, {"text": ANSWER}])
    loop = merged_loop(store, script)
    events = list(loop.run())
    saved = store.get_turn(UID, loop.chat_id, loop.turn_id)
    review = saved["agent_review"]
    assert saved["status"] == "completed" and saved["consensus"] == ANSWER
    assert review["status"] == "succeeded" and review_is_bound(review, ANSWER)
    # Steering, then the answer from the same context: no separate answer step.
    assert orchestrator_steps(script) == ["completion:0", "completion:1"]
    assert "tools" in script.kwargs[1] and script.kwargs[1]["allow_tool_calls"] is True
    assert script.kwargs[1].get("prompt_cache", True) is True
    # Full answers and the source list are in the tool result the agent reads.
    result = tool_result(loop, "call_0_0")
    assert [a["text"] for a in result["answers"]] == [MODEL_ANSWER.strip()] * 2
    assert "sources" in result and "write the answer;" in result["instruction"]
    assert not any("text_shortened_for_routing" in a for a in result["answers"])
    # The deliverable is named right after the evidence, like Claude Code's
    # reminders; the depth that steered the comparison models is not shown.
    assert "depth" not in result
    request = script.requests[1]
    assert request[-1] == {"role": "user", "content": prompt_defaults.AGENT_WRITE_NOTE}
    assert request[-2]["role"] == "tool" and request[-2]["tool_call_id"] == "call_0_0"
    # The answer streamed and was complete before the check started.
    assert deltas(events) == ANSWER
    first_judge = next(i for i, e in enumerate(events) if e.get("kind") == "tool" and e.get("name") == "judge_answer")
    assert max(i for i, e in enumerate(events) if e.get("type") == "delta") < first_judge
    assert not retractions(events)
    assert all(c.get("synthesis_providers") == ["anthropic", "openai"] for c in review["comparisons"])
    assert loop.completion.text == ANSWER


def test_the_write_note_follows_only_usable_comparisons(store):
    # A refused comparison (invalid task) gives nothing to write from.
    refused = ("compare_models", {"question": "", "status_update": "Comparing."})
    script = Merged([{"tools": [refused]}, {"text": "Hello! How can I help?"}])
    list(merged_loop(store, script).run())
    assert prompt_defaults.AGENT_WRITE_NOTE not in json.dumps(script.requests[1])


def test_a_direct_answer_is_one_call_and_unchecked(store):
    script = Merged([{"text": ANSWER}])
    loop = merged_loop(store, script)
    events = list(loop.run())
    saved = store.get_turn(UID, loop.chat_id, loop.turn_id)
    assert saved["status"] == "completed" and saved["assistant_response"] == ANSWER
    assert orchestrator_steps(script) == ["completion:0"]
    assert "agent_review" not in saved
    assert not any(e.get("kind") == "tool" and e.get("name") == "judge_answer" for e in events)
    assert deltas(events) == ANSWER and loop.comparison.direct


def test_a_greeting_shows_at_once_when_the_step_ends(store):
    loop = merged_loop(store, Merged([{"text": "Hello! How can I help?"}]))
    events = list(loop.run())
    assert [e["text"] for e in events if e.get("type") == "delta"] == ["Hello! How can I help?"]
    assert loop.completion.text == "Hello! How can I help?"


def test_a_short_preamble_before_a_tool_call_never_shows(store):
    script = Merged([{"text": "I'll compare the options.", "tools": [COMPARE]}, {"text": ANSWER}])
    loop = merged_loop(store, script)
    events = list(loop.run())
    assert deltas(events) == ANSWER and not retractions(events)


def test_a_long_text_before_a_tool_call_is_taken_back_and_kept_as_a_note(store):
    preamble = "Let me first think about what matters here. " * 12
    script = Merged([{"text": preamble, "tools": [COMPARE]}, {"text": ANSWER}])
    loop = merged_loop(store, script)
    events = list(loop.run())
    assert len(retractions(events)) == 1
    clear = events.index(retractions(events)[0])
    # What streamed before the clear was the preamble; after it only the answer.
    assert deltas(events[:clear]) == preamble and deltas(events[clear:]) == ANSWER
    note = next(e for e in events if e.get("kind") == "progress" and e.get("id", "").endswith("/note"))
    assert note["text"].startswith("Let me first think") and len(note["text"]) <= agent_answer_mode.NOTE_CHARS
    saved = store.get_turn(UID, loop.chat_id, loop.turn_id)
    assert saved["consensus"] == ANSWER


def test_research_is_held_back_and_goes_through_a_comparison(store):
    research = "From my search: the first option is cheaper. " * 20
    found = [{"url": "https://example.org/found", "title": "Found"}]
    script = Merged([{"text": research, "sources": found}, {"text": research}, {"tools": [COMPARE]},
                     {"text": ANSWER}])
    loop = merged_loop(store, script)
    events = list(loop.run())
    # Never shown: the step's own search results arrived before its text,
    # and the next reply was held back while research stood unchecked.
    assert research not in deltas(events) and deltas(events) == ANSWER
    users = [m["content"] for m in loop.messages if m["role"] == "user"]
    assert any(m.startswith("The web-search phase has finished.") and "write the answer" in m for m in users)
    assert sum(m.startswith("App rule: your reply above is not sent.") for m in users) == 1
    saved = store.get_turn(UID, loop.chat_id, loop.turn_id)
    assert saved["status"] == "completed" and saved["agent_review"]["status"] == "succeeded"


def test_after_one_reminder_a_reply_without_comparison_stands(store):
    research = "From my search: the first option is cheaper. " * 20
    found = [{"url": "https://example.org/found", "title": "Found"}]
    script = Merged([{"text": research, "sources": found}, {"text": research}, {"text": ANSWER}])
    loop = merged_loop(store, script)
    events = list(loop.run())
    assert deltas(events) == ANSWER and loop.completion.text == ANSWER
    assert orchestrator_steps(script) == ["completion:0", "completion:1", "completion:2"]


def test_a_free_429_after_paid_comparisons_is_retried_once(store, monkeypatch):
    monkeypatch.setattr(agent_delegation.DelegationLoop, "_pause", lambda self, seconds: iter(()))
    script = Merged([{"tools": [COMPARE]}, {"rate_limited": True}, {"text": ANSWER}])
    loop = merged_loop(store, script)
    loop.cooldowns = ProviderCooldowns()  # never the process-wide gate in tests
    events = list(loop.run())
    saved = store.get_turn(UID, loop.chat_id, loop.turn_id)
    assert saved["status"] == "completed" and saved["consensus"] == ANSWER
    assert orchestrator_steps(script) == ["completion:0", "completion:1", "completion:2"]
    assert any(e.get("kind") == "progress" and e["id"].endswith("/rate_limit") for e in events)


def test_a_short_reply_after_research_stands_like_a_clarification_question(store):
    found = [{"url": "https://example.org/found", "title": "Found"}]
    script = Merged([{"text": "Research findings", "sources": found}, {"text": "Which team size do you mean?"}])
    loop = merged_loop(store, script)
    events = list(loop.run())
    assert orchestrator_steps(script) == ["completion:0", "completion:1"]
    assert deltas(events) == loop.completion.text == "Which team size do you mean?"


# A short one was held back for its length and never streamed: it is shown
# whole and saved too (DelegationLoop._keep_cut_answer, review 2026-10-14).
@pytest.mark.parametrize("text", [ANSWER, "The first option is cheaper over two years."])
def test_an_answer_cut_at_its_limit_is_kept_unchecked(store, text):
    script = Merged([{"tools": [COMPARE]}, {"text": text, "finish": "length"}])
    loop = merged_loop(store, script)
    events = []
    with pytest.raises(AnalysisBudgetExceeded, match="output token limit"):
        for event in loop.run():
            events.append(event)
    saved = store.get_turn(UID, loop.chat_id, loop.turn_id)
    assert saved["status"] == "failed" and saved["assistant_response"] == text
    assert saved["agent_review"]["versions"][-1]["text"] == text
    assert deltas(events) == text
    assert not any(e.get("kind") == "tool" and e.get("name") == "judge_answer" for e in events)


def test_every_step_may_write_a_whole_answer_but_is_admitted_like_a_routing_step(store):
    from app.services.llm.agent_client import answer_output_limit, routing_output_limit
    script = Merged([{"tools": [COMPARE]}, {"text": ANSWER}])
    loop = merged_loop(store, script)
    list(loop.run())
    # Every request may write the answer...
    assert script.limits == {0: answer_output_limit(loop.model), 1: answer_output_limit(loop.model)}
    # ...but admission and further search segments use the routing allowance.
    assert loop._routing_model().max_output_tokens == routing_output_limit(loop.model)
    assert loop._answer_output() == answer_output_limit(loop.model)


def free_account(store, monkeypatch, remaining):
    monkeypatch.setattr(agent_quota, "_stored_tier", lambda uid: "free")
    limit = agent_budget_config.DEFAULT_TIER_LIMITS["free"]
    ref = agent_quota.quota_ref(store.db, UID, agent_quota.day_key())
    ref.set({"used": limit - remaining})
    return ref


def test_a_free_account_keeps_its_research_after_a_first_message(store, monkeypatch):
    """Until 2026-10-14 a first step that may write the answer reserved the
    answer allowance for every search round (~460k tokens here): a Free
    account (660k a day) got one research round instead of three once ~190k
    were used. It is admitted like a routing step now."""
    from app.services.agent_delegation import ORCHESTRATOR_SEARCH_ROUNDS
    ref = free_account(store, monkeypatch, 350_000)
    script = Merged([{"tools": [COMPARE]}, {"text": ANSWER}])
    loop = merged_loop(store, script)
    list(loop.run())
    saved = store.get_turn(UID, loop.chat_id, loop.turn_id)
    assert saved["status"] == "completed" and saved["consensus"] == ANSWER
    assert script.kwargs[0]["native_searches"] == ORCHESTRATOR_SEARCH_ROUNDS
    assert ref.get().to_dict()["reserved"] == 0


def test_near_the_limit_a_direct_answer_keeps_its_whole_allowance(store, monkeypatch):
    """Admitted like a routing step, the answer on top may overdraw; the
    search still yields."""
    from app.services.llm.agent_client import answer_output_limit
    ref = free_account(store, monkeypatch, 30_000)
    used = ref.get().to_dict()["used"]
    script = Merged([{"text": ANSWER}])
    loop = merged_loop(store, script)
    events = list(loop.run())
    saved = store.get_turn(UID, loop.chat_id, loop.turn_id)
    assert saved["status"] == "completed" and saved["assistant_response"] == ANSWER
    assert script.kwargs[0]["native_searches"] == 0
    assert any(e.get("name") == "web_search" and e.get("status") == "blocked" for e in events)
    assert script.limits[0] == answer_output_limit(loop.model) > 30_000
    ledger = ref.get().to_dict()
    assert ledger["reserved"] == 0 and ledger["used"] == used + 70


def test_a_turn_limit_lets_the_agent_write_without_tools(store, monkeypatch):
    script = Merged([{"tools": [COMPARE]}, {"tools": [COMPARE]}, {"text": ANSWER}])
    loop = merged_loop(store, script)
    # The step cap stops further steering after the second comparison.
    loop.policy = replace(loop.policy, turn_steps=2)
    events = list(loop.run())
    saved = store.get_turn(UID, loop.chat_id, loop.turn_id)
    assert saved["status"] == "completed" and saved["consensus"] == ANSWER
    last = max(script.kwargs)
    # Same tools listed (prompt cache), none callable, no search.
    assert script.kwargs[last]["allow_tool_calls"] is False and script.kwargs[last]["tools"]
    assert script.kwargs[last]["native_searches"] == 0
    assert script.requests[last][-1]["content"].startswith("App rule: this message has reached its limit.")
    assert review_is_bound(saved["agent_review"], ANSWER) and deltas(events) == ANSWER


def test_the_memory_decision_rides_on_the_comparison(store):
    set_profile(store.db, auto_memory=True)
    snapshot = repo(store).snapshot(UID)
    memory = [{"op": "add", "text": "Leads a team of ten.", "evidence": "Which option is cheaper?"}]
    script = Merged([{"tools": [COMPARE]}, {"text": ANSWER}], memory=memory)
    loop = merged_loop(store, script, memory=snapshot)
    list(loop.run())
    assert [item["text"] for item in repo(store).get(UID)[0]] == ["Leads a team of ten."]
    assert tool_result(loop, "call_0_0")["memory"]["changes"][0]["op"] == "add"


def test_an_answer_followed_only_by_a_memory_save_stands(store):
    """Claude may write the answer and then save a memory: retracting it would
    leave only "Saved." for the next step."""
    set_profile(store.db, auto_memory=True)
    save = ("update_memory", {"changes": [{"op": "add", "text": "Leads a team of ten.",
                                           "evidence": "Which option is cheaper?"}]})
    script = Merged([{"text": ANSWER, "tools": [save]}, {"text": "Saved."}])
    loop = merged_loop(store, script, memory=repo(store).snapshot(UID))
    events = list(loop.run())
    assert orchestrator_steps(script) == ["completion:0"]
    assert loop.completion.text == ANSWER and deltas(events) == ANSWER and not retractions(events)
    assert [item["text"] for item in repo(store).get(UID)[0]] == ["Leads a team of ten."]


def test_a_short_reply_with_a_memory_save_is_the_whole_answer(store):
    """The usual memory request: a short confirmation, held only for its
    length, plus update_memory. Not a preamble: no second step writes "Saved."
    (review 2026-10-14)."""
    set_profile(store.db, auto_memory=True)
    save = ("update_memory", {"changes": [{"op": "add", "text": "Leads a team of ten.",
                                           "evidence": "Which option is cheaper?"}]})
    short = "Got it, I will keep in mind that you lead a team of ten."
    script = Merged([{"text": short, "tools": [save]}, {"text": "Saved."}])
    loop = merged_loop(store, script, memory=repo(store).snapshot(UID))
    events = list(loop.run())
    assert orchestrator_steps(script) == ["completion:0"]
    assert loop.completion.text == short and deltas(events) == short and not retractions(events)
    assert [item["text"] for item in repo(store).get(UID)[0]] == ["Leads a team of ten."]


def test_a_short_text_held_during_research_is_no_answer_with_a_memory_save(store):
    """Text after the step's own search results never counted as shown: a
    memory save next to it does not turn research into the answer."""
    set_profile(store.db, auto_memory=True)
    save = ("update_memory", {"changes": [{"op": "add", "text": "Leads a team of ten.",
                                           "evidence": "Which option is cheaper?"}]})
    script = Merged([{"sources": [{"url": "https://example.com/a", "title": "A"}], "text": "Found prices.",
                      "tools": [save]}, {"tools": [COMPARE]}, {"text": ANSWER}])
    loop = merged_loop(store, script, memory=repo(store).snapshot(UID))
    events = list(loop.run())
    assert orchestrator_steps(script)[:2] == ["completion:0", "completion:1"]
    assert "Found prices." not in deltas(events) and loop.completion.text != "Found prices."


# Evidence paraphrased, not the user's words: update_memory refuses the change.
REFUSED_SAVE = ("update_memory", {"changes": [{"op": "add", "text": "Leads a team of ten.",
                                               "evidence": "I lead a team of ten people at work"}]})


@pytest.mark.parametrize("reply", ["Got it, I will keep in mind that you lead a team of ten.", ANSWER],
                         ids=["held", "shown"])
def test_a_reply_next_to_a_refused_memory_save_is_written_again(store, reply):
    """The reply may confirm a change that was refused: it goes back (a shown
    one stays as a note) and the next step writes the answer with the
    refusal in view (_side_results_accepted, review 2026-10-14)."""
    set_profile(store.db, auto_memory=True)
    retry = "I could not save that: a memory needs your own words."
    script = Merged([{"text": reply, "tools": [REFUSED_SAVE]}, {"text": retry}])
    loop = merged_loop(store, script, memory=repo(store).snapshot(UID))
    events = list(loop.run())
    assert "error" in tool_result(loop, "call_0_0") and repo(store).get(UID)[0] == []
    assert orchestrator_steps(script) == ["completion:0", "completion:1"]
    assert any(m.get("role") == "tool" and "error" in m["content"] for m in script.requests[1])
    saved = store.get_turn(UID, loop.chat_id, loop.turn_id)
    assert saved["status"] == "completed" and saved["assistant_response"] == retry
    assert shown(events) == retry
    # Only a reply that was on screen leaves a note.
    notes = [e for e in events if e.get("kind") == "progress" and e.get("id", "").endswith("/note")]
    assert len(notes) == (reply == ANSWER)


@pytest.mark.parametrize("accepted", [False, True], ids=["refused", "accepted"])
def test_a_reply_with_a_side_tool_at_the_invalid_round_limit_leaves_one_answer_on_screen(store, monkeypatch,
                                                                                         accepted):
    """A comparison, two invalid rounds, then the answer with a side tool.
    Refused (a memory save), the wrap-up wrote a second answer under the
    first, which stayed on screen (review 2026-10-14); accepted (a prepared
    Watch), the answer stands without another step. Either way the browser
    shows exactly the saved answer."""
    from app.services import watch_service
    from test_agent_watch import WATCH, outlook
    monkeypatch.setattr(watch_service, "create_watch", lambda *args, **kwargs: pytest.fail("Watch created"))
    set_profile(store.db, auto_memory=True)
    invalid = ("compare_models", {"question": "", "context": "", "status_update": "Comparing."})
    side = ("prepare_watch", WATCH) if accepted else REFUSED_SAVE
    wrap_up = "From the comparisons: the first option is cheaper over two years for a team of ten. " * 4
    script = Merged([{"tools": [COMPARE]}, {"tools": [invalid]}, {"tools": [invalid]},
                     {"text": ANSWER, "tools": [side]}, {"text": wrap_up}], memory=[])
    loop = merged_loop(store, script, memory=repo(store).snapshot(UID))
    loop.watch_tools.outlook = outlook()
    events = list(loop.run())
    answer = ANSWER if accepted else wrap_up
    saved = store.get_turn(UID, loop.chat_id, loop.turn_id)
    assert saved["status"] == "completed" and saved["consensus"] == answer
    assert review_is_bound(saved["agent_review"], answer)
    assert shown(events) == answer
    assert len(orchestrator_steps(script)) == (4 if accepted else 5)


def test_text_before_a_cut_tool_call_is_taken_back_before_the_retry(store, monkeypatch):
    monkeypatch.setattr(agent_delegation, "lighter_reasoning",
                        lambda model: replace(model, reasoning_effort="low"))
    preamble = "Let me first think about what matters here. " * 12
    script = Merged([{"text": preamble, "cut": True}, {"text": ANSWER}])
    loop = merged_loop(store, script)
    events = list(loop.run())
    assert len(retractions(events)) == 1
    clear = events.index(retractions(events)[0])
    assert deltas(events[:clear]) == preamble and deltas(events[clear:]) == ANSWER
    assert loop.completion.text == ANSWER


class RealStep(Merged):
    """Merged, but step completion:``real`` streams through the real client
    (AgentCompletion.stream over test_agent_loop.transport)."""

    def __init__(self, plan, *, real, **kwargs):
        super().__init__(plan, **kwargs)
        self.real = real

    def factory(self):
        from test_agent_loop import REAL_STREAM
        base = type(super().factory())
        script = self

        class Completion(base):
            def stream(self, **kwargs):
                if self.step_id != f"completion:{script.real}":
                    yield from super().stream(**kwargs)
                    return
                script.calls.append((self.step_id, kwargs["model"].model))
                yield from REAL_STREAM(self, **kwargs)
        return Completion()


def searched_midway(before, after, end):
    """Provider packets: ``before``, the step's own search results (0/0
    offsets, as Anthropic's search sends them), ``after``, then ``end``."""
    from test_agent_loop import packet
    from test_agent_source_evidence import search_result
    text = lambda value: [packet({"content": value[i:i + 50]}) for i in range(0, len(value), 50)]
    return [*text(before), packet({"content": "", "annotations": [search_result("https://example.org/fees")]}),
            *text(after), end]


def test_an_answer_that_searches_midway_keeps_its_shown_opening(store, monkeypatch):
    """After a comparison the agent writes, settles a point with its own
    search and writes on. The client's pre-search cut took the opening the
    user had seen off the screen and out of the saved answer
    (AgentCompletion._drop_presearch_text, review 2026-10-14)."""
    from test_agent_loop import packet, transport, usage
    opening = "Summary: the first option is cheaper over two years for a team of ten. " * 6
    rest = "After checking the fee table: the second option adds 20 euros per seat. " * 10
    transport(monkeypatch, [searched_midway(opening, rest, packet(finish="stop", usage=usage(1)))])
    script = RealStep([{"tools": [COMPARE]}, {}], real=1)
    loop = merged_loop(store, script)
    events = list(loop.run())
    saved = store.get_turn(UID, loop.chat_id, loop.turn_id)
    assert saved["status"] == "completed" and saved["consensus"] == opening + rest
    assert review_is_bound(saved["agent_review"], opening + rest)
    assert deltas(events) == opening + rest and not retractions(events)


def test_a_research_step_that_breaks_off_saves_only_what_was_shown(store, monkeypatch):
    """A first step shows its opening, gets its own search results, writes on
    unseen (research the app does not send) and its stream breaks: the
    partial answer saved is what the user saw (DelegationLoop._step,
    review 2026-10-14)."""
    from test_agent_loop import transport
    opening = "Let me look into the current prices of both options carefully. " * 6
    research = "From the results: the first option costs 100 and the second 80 a month. " * 12
    transport(monkeypatch, [searched_midway(opening, research, RuntimeError("connection reset"))])
    loop = merged_loop(store, RealStep([{}], real=0))
    loop.cooldowns = ProviderCooldowns()  # never the process-wide gate in tests
    events = []
    with pytest.raises(RuntimeError, match="connection reset"):
        for event in loop.run():
            events.append(event)
    saved = store.get_turn(UID, loop.chat_id, loop.turn_id)
    assert deltas(events) == opening
    assert saved["status"] == "failed" and saved["assistant_response"] == opening


def test_a_page_read_after_the_comparison_is_in_context_and_checked(store, monkeypatch):
    from test_agent_web_fetch import CITED, PAGE, fake_fetch, read_call
    monkeypatch.setenv("AGENT_READ_SOURCES", "1")
    fake_fetch(monkeypatch)
    script = Merged([{"tools": [COMPARE]}, {"tools": [read_call()]}, {"text": ANSWER}], cited=(CITED,))
    loop = merged_loop(store, script)
    events = list(loop.run())
    saved = store.get_turn(UID, loop.chat_id, loop.turn_id)
    assert saved["status"] == "completed" and saved["consensus"] == ANSWER
    assert review_is_bound(saved["agent_review"], ANSWER)
    assert [r["status"] for r in saved["agent_review"]["read_sources"]] == ["completed"]
    # The cited source is listed once in the comparison result.
    assert [entry["url"] for entry in tool_result(loop, "call_0_0")["sources"]] == [CITED]
    # The agent writes the answer with the page text it read in its own context.
    read = tool_result(loop, "call_1_0")
    assert read["untrusted_page_text"] == PAGE and "write the answer" in read["note"]
    assert any(m.get("role") == "tool" and PAGE in m["content"] for m in script.requests[2])
    assert deltas(events) == ANSWER


@pytest.mark.parametrize("compare", [True, False])
def test_a_watch_is_prepared_and_the_agent_points_to_its_card(store, monkeypatch, compare):
    from app.services import agent_watch, watch_service
    from test_agent_watch import QUESTION, WATCH, outlook

    def refuse(*args, **kwargs):
        raise AssertionError("prepare_watch created a Watch")
    monkeypatch.setattr(watch_service, "create_watch", refuse)
    first = [("prepare_watch", WATCH), *([COMPARE] if compare else [])]
    script = Merged([{"tools": first}, {"text": ANSWER}])
    loop = merged_loop(store, script)
    loop.watch_tools.outlook = outlook()
    list(loop.run())
    saved = store.get_turn(UID, loop.chat_id, loop.turn_id)
    assert saved["status"] == "completed" and saved["assistant_response"] == ANSWER
    assert saved["agent_watch"]["question"] == QUESTION
    system = script.requests[0][0]["content"]
    assert agent_watch.ORCHESTRATOR_PROMPT in system and "points to the card" in system
    assert ("agent_review" in saved) == compare


def test_over_http_a_direct_answer_is_one_streamed_request(api, monkeypatch):
    """The whole path: POST /agent, the real stream client, the saved turn
    and the recovered answer."""
    from test_agent_loop import REAL_STREAM, packet, transport, usage
    from test_agent_runs import AUTH
    from app.services.llm.agent_client import AgentCompletion
    client, store, _ = api
    monkeypatch.setattr(AgentCompletion, "stream", REAL_STREAM)
    chunks = [ANSWER[i:i + 100] for i in range(0, len(ANSWER), 100)]
    requests, _, _ = transport(monkeypatch, [[*(packet({"content": chunk}) for chunk in chunks),
                                              packet(finish="stop", usage=usage(0))]])
    chat = client.post("/chats", json={"execution_mode": "agent"}, headers=AUTH).json()["chat"]
    payload = {"chat_id": chat["id"], "question": "Translate this, please.", "client_request_id": "merged",
               "bookmark_id": "merged", "model_id": "claude-haiku-4-5"}
    body = client.post("/agent", json=payload, headers=AUTH).text
    assert "event: final" in body
    assert len(requests) == 1
    names = [tool.get("function", {}).get("name") for tool in requests[0]["tools"] if tool.get("type") == "function"]
    assert "compare_models" in names and "answer" not in names
    assert requests[0]["tool_choice"] == "auto"
    assert requests[0]["messages"][0]["content"].startswith(
        prompt_defaults.AGENT_SYSTEM_PROMPT.split("COMPARE OR ANSWER DIRECTLY")[0])
    replay = client.post("/agent", json={**payload, "recover_only": True}, headers=AUTH)
    assert replay.status_code == 200 and replay.json()["response"] == ANSWER
    assert replay.json()["turn"]["agent_settings"]["answer_mode"] == "merged"


# --- scripts/evaluate_agent_answers.py, offline ----------------------------------

def evaluation_script():
    """The live evaluation script as a module (scripts/ is no package)."""
    import importlib.util
    from pathlib import Path
    path = Path(__file__).resolve().parents[1] / "scripts" / "evaluate_agent_answers.py"
    spec = importlib.util.spec_from_file_location("evaluate_agent_answers", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_live_script_measures_a_turn(store, monkeypatch):
    """One scripted turn: steps, cost, review and where the time goes."""
    from app.services import prompt_config
    from app.services.llm import agent_client
    module = evaluation_script()
    script = Merged([{"tools": [COMPARE]}, {"text": ANSWER}])
    monkeypatch.setattr(agent_client, "AgentCompletion", type(script.factory()))
    row = module.run_turn(0, "Which option is cheaper?", model=resolve_agent_model("claude-haiku-4-5"),
                          families={"anthropic": "claude-haiku-4-5", "openai": "gpt-5.4-mini"},
                          config=prompt_config.get_config(), key="test", check_sources=False)
    assert row["mode"] == "agent" and row["status"] == "completed" and not row["error"]
    # Steering and the answer in one step after the comparison.
    assert row["steps"] == 2 and 0 < row["after_comparison_cost_usd"] < row["chat_cost_usd"]
    assert row["answer"] == ANSWER and not row["leaks"] and row["retractions"] == 0
    assert row["review"] == "succeeded" and row["seconds_after_comparison"] is not None
    summary = module.summary([row])
    assert summary["turns"] == summary["completed"] == 1 and summary["steps"] == 2

    # Where the time goes: every provider call with claim, request, first
    # token and settlement; the time after the comparison split by step.
    calls = row["timeline"]
    assert [c["call"] for c in calls if c["kind"] == "chat"] == ["completion:0", "completion:1"]
    assert sum(c["kind"] == "comparison" for c in calls) == 2 and any(c["kind"] == "judge" for c in calls)
    for c in calls:
        assert c["status"] == "succeeded" and "error" not in c
        assert c["start"] <= c["claimed"] <= c["request"] <= c["end"] <= c["settled"]
        assert c["request"] <= c.get("first_progress", c["request"]) <= c["end"]
        assert c["seconds"] >= 0 and c["max_silence"] >= 0 and c["output_tokens"] == 20
    # The step that writes the answer streams text.
    assert "first_text" in next(c for c in calls if c["call"] == "completion:1")
    assert all(c["title"].startswith("Comparison 1") for c in calls if c["kind"] == "comparison")
    phases = row["phases"]
    assert (phases["comparison_started"] <= phases["comparison_done"] <= phases["judges_started"]
            <= phases["judges_done"] <= phases["end"])
    assert row["rate_limits"] == row["stalls"] == row["retries"] == 0
    # The test account's allowance does not hold the first step's three
    # search rounds: one refused claim, then it searches less.
    assert row["allowance_refusals"] == 1 and next(c for c in calls if c["call"] == "completion:0")["refused"] == 1
    split = row["after_comparison"]
    assert split["calls"] == ["completion:1"]
    assert split["read_seconds"] == 0 and split["chat_seconds"] + split["other_seconds"] >= 0
    assert row["phases"]["answer_text"] is not None and row["longest_silence"]["seconds"] >= 0


def test_the_live_script_shows_429s_and_stalls(store, monkeypatch):
    """A free 429 of the step that writes the answer and a comparison answer
    the stall watchdog ended show up in the script's timeline and counters."""
    from app.services import prompt_config
    from app.services.llm import agent_client
    module = evaluation_script()
    monkeypatch.setattr(agent_delegation.DelegationLoop, "_pause", lambda self, seconds: iter(()))
    monkeypatch.setattr(agent_delegation, "provider_cooldowns", ProviderCooldowns())
    base = type(Merged([{"tools": [COMPARE]}, {"rate_limited": True}, {"text": ANSWER}]).factory())

    class Stalling(base):
        def stream(self, *, model, messages, **kwargs):
            schema = (model.request_config.get("response_format") or {}).get("json_schema")
            if not self.step_id.startswith("completion:") and not schema and model.model.startswith("google/"):
                raise TimeoutError("Provider stream made no progress")
            yield from super().stream(model=model, messages=messages, **kwargs)

    monkeypatch.setattr(agent_client, "AgentCompletion", Stalling)
    row = module.run_turn(0, "Which option is cheaper?", model=resolve_agent_model("claude-haiku-4-5"),
                          families={"anthropic": "claude-haiku-4-5", "openai": "gpt-5.4-mini",
                                    "gemini": "gemini-3.5-flash-lite"},
                          config=prompt_config.get_config(), key="test", check_sources=False)
    assert row["status"] == "completed" and row["answer"] == ANSWER
    assert (row["rate_limits"], row["stalls"], row["retries"]) == (1, 1, 1)
    calls = {c["call"]: c for c in row["timeline"]}
    assert calls["completion:1"]["error"] == "429" and "first_progress" not in calls["completion:1"]
    assert "error" not in calls["completion:2"] and calls["completion:2"]["first_text"] >= calls["completion:2"]["request"]
    stalled = [c for c in row["timeline"] if c.get("stalled")]
    assert [(c["kind"], c["error"], c["status"]) for c in stalled] == [("comparison", "TimeoutError", "failed")]
    assert row["after_comparison"]["calls"] == ["completion:1", "completion:2"]
    summary = module.summary([row])
    assert (summary["rate_limits"], summary["stalls"], summary["retries"]) == (1, 1, 1)


def test_the_live_script_times_real_provider_streams(monkeypatch):
    """The real stream path: the stall watchdog's progress gives the first
    token and the longest silence (keepalive comments are none), and a
    stream the watchdog ends is marked stalled."""
    import time
    from app.services.llm import agent_client, provider_runtime
    module = evaluation_script()

    def packet(delta, finish=None):
        return "data: " + json.dumps({"id": "gen", "choices": [{"index": 0, "delta": delta, "finish_reason": finish}]})

    def answering(url, **kwargs):
        yield ": OPENROUTER PROCESSING"
        time.sleep(.15)
        yield packet({"content": "Hello"})
        yield ""
        yield packet({"content": " world"}, "stop")
        yield ""
        yield "data: [DONE]"
        yield ""

    def stalling(url, *, progress, **kwargs):
        yield ": OPENROUTER PROCESSING"
        progress.deadline = 0  # 180 s without a token, as the socket guard sees it
        progress.check()

    timing = module.Timing()
    timed = timing.completion(agent_client.AgentCompletion)
    model = resolve_agent_model("claude-haiku-4-5")
    original = provider_runtime.ProviderProgressWatchdog
    with timing.installed():
        for step, lines in (("completion:0", answering), ("completion:1", stalling)):
            monkeypatch.setattr(agent_client, "cancellable_sse_lines", lines)
            value = timed()
            value.step_id = step
            try:
                list(value.stream(model=model, messages=[{"role": "user", "content": "Hi"}], api_key="test"))
            except TimeoutError:
                assert step == "completion:1"
    assert provider_runtime.ProviderProgressWatchdog is original
    answered, stalled = timing.timeline()
    assert answered["call"] == "completion:0" and answered["ttft"] >= .1 and answered["max_silence"] >= .1
    assert answered["first_text"] == answered["first_progress"] and "stalled" not in answered
    assert stalled["call"] == "completion:1" and stalled["stalled"] and "first_progress" not in stalled


def test_the_live_script_judges_each_answer_against_its_saved_baseline(monkeypatch, tmp_path):
    """--baseline FILE --pairwise MODEL: one turn per question, then a blind
    pick against the saved answer of the same case, taken only from completed
    rows of --baseline-mode. Winners are "agent" or "baseline", whatever mode
    the saved rows had."""
    import os
    import dotenv
    from app.core import config as cfg
    from app.services.llm import agent_client
    module = evaluation_script()
    # Nothing live: no .env, no Firestore, no model call. main() pins the
    # account lookups and the working directory; both are restored afterwards.
    monkeypatch.setattr(dotenv, "load_dotenv", lambda *args, **kwargs: None)
    monkeypatch.setattr(cfg, "load_models_from_db", lambda **kwargs: None)
    monkeypatch.setattr(agent_quota, "_stored_tier", agent_quota._stored_tier)
    monkeypatch.setattr(agent_quota, "_admin_role", agent_quota._admin_role)
    monkeypatch.chdir(os.getcwd())
    monkeypatch.setenv("OPENROUTER_API_KEY", "test")
    turns = []

    def run_turn(case, question, *, model, families, config, key, check_sources):
        turns.append(case)
        return {"case": case, "mode": "agent", "model": model.selection_id, "status": "completed",
                "answer": f"Agent answer {case}.", "steps": 2, "agreement": [80], "retractions": 0, "leaks": [],
                "major_contradictions": 0, "rate_limits": 0, "stalls": 0, "retries": 0, "longest_silence": None}

    # The judge prefers the agent's answer on case 0, the saved one on case 1
    # and ties on case 2, wherever the shuffle put them.
    prefer = {0: "agent", 1: "baseline", 2: "tie"}

    class Judge:
        def __init__(self):
            self.text, self.usage = "", {"estimated_cost_nano_usd": 1000}

        def stream(self, *, model, messages, api_key):
            prompt = messages[-1]["content"]
            case = int(re.search(r"Agent answer (\d+)\.", prompt).group(1))
            agent_first = "Agent answer" in prompt.split("Answer 2:")[0]
            want = prefer[case]
            better = "tie" if want == "tie" else "1" if (want == "agent") == agent_first else "2"
            self.text = json.dumps({"better": better, "reason": "Clearer."})
            return iter(())

    monkeypatch.setattr(module, "run_turn", run_turn)
    monkeypatch.setattr(agent_client, "AgentCompletion", Judge)
    baseline, out = tmp_path / "baseline.jsonl", tmp_path / "out.jsonl"
    saved = [{"case": case, "mode": "separate", "status": "completed", "answer": f"Saved answer {case}."}
             for case in (0, 1, 2)]
    # Neither a failed row nor a row of another mode is a baseline.
    saved += [{"case": 3, "mode": "separate", "status": "failed", "answer": "Partial."},
              {"case": 3, "mode": "merged", "status": "completed", "answer": "Other mode."}]
    baseline.write_text("".join(json.dumps(row) + "\n" for row in saved), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["evaluate_agent_answers.py", "--live", "--model", "claude-haiku-4-5",
                                      *(arg for case in range(4) for arg in ("--only", str(case))),
                                      "--baseline", str(baseline), "--pairwise", "claude-haiku-4-5",
                                      "--out", str(out)])
    module.main()
    lines = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]
    # A single run per question.
    assert turns == [0, 1, 2, 3]
    assert [line["case"] for line in lines if "answer" in line] == [0, 1, 2, 3]
    verdicts = {line["case"]: line["pairwise"]["winner"] for line in lines if "pairwise" in line}
    assert verdicts == prefer
    assert lines[-2]["summary"]["turns"] == lines[-2]["summary"]["completed"] == 4
    assert lines[-1] == {"pairwise_wins": {"agent": 1, "baseline": 1, "tie": 1}, "judge": "claude-haiku-4-5"}

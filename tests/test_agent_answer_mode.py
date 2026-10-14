"""Merged answer (agent_answer_mode, AGENT_MERGED_ANSWER=1): the agent writes
the answer itself as its last step, no separate answer step.

The separate path keeps its own tests (test_agent_comparison and others);
these cover what changes when the switch is on.
"""
from dataclasses import replace
import json

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
# Longer than the routing gist of the separate path (result_chars 8000).
MODEL_ANSWER = "The first option costs 100. The constraint matters. " + "Details on pricing. " * 500
COMPARE = ("compare_models", {"question": "Which option is cheaper over two years?", "context": "Team of ten.",
                              "status_update": "Comparing the options."})


def tool_call(index, n, name, args):
    return {"id": f"call_{index}_{n}", "type": "function", "function": {"name": name, "arguments": json.dumps(args)}}


class Merged(Script):
    """A scripted merged turn. ``plan[i]`` is what step completion:i does:
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
                    # A comparison answer, longer than the routing gist.
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


def merged_loop(store, script, *, merged=True, messages=None, memory=None, check_sources=False):
    chat, turn = pending(store)
    config = {**defaults(), "enabled": False, "max_searches": 0}
    loop = DelegationLoop(store=store, uid=UID, chat_id=chat, turn_id=turn["id"],
        model=resolve_agent_model("claude-haiku-4-5"),
        messages=messages or [{"role": "system", "content": "Answer."},
                              {"role": "user", "content": "Which option is cheaper?"}],
        api_key="test", cancellation=ProviderCancellation(), policy=AgentPolicy.for_chat(config),
        delegation_config=config, completion_factory=script.factory, check_sources=check_sources,
        comparison_models=comparison_selection({"anthropic": "claude-haiku-4-5", "openai": "gpt-5.4-mini"}),
        memory=memory, merged_answer=merged)
    script.loop = loop
    return loop


def deltas(events):
    return "".join(event["text"] for event in events if event.get("type") == "delta")


def retractions(events):
    return [event for event in events if event.get("kind") == "status" and event.get("clear_response")]


def orchestrator_steps(script):
    return [step for step, _ in script.calls if step.startswith("completion:")]


def tool_result(loop, call_id):
    return json.loads(next(m["content"] for m in loop.messages
                           if m.get("role") == "tool" and m.get("tool_call_id") == call_id))


# --- Switch and prompts ----------------------------------------------------------

def test_the_switch_is_off_by_default_and_needs_a_chat_turn(store, monkeypatch):
    monkeypatch.delenv(agent_answer_mode.ENABLED_ENV, raising=False)
    assert not agent_answer_mode.enabled()
    assert not merged_loop(store, Merged([{}]), merged=None).merged
    monkeypatch.setenv(agent_answer_mode.ENABLED_ENV, "1")
    assert agent_answer_mode.enabled() and merged_loop(store, Merged([{}]), merged=None).merged
    # An explicit choice wins over the environment (live comparison script).
    assert not merged_loop(store, Merged([{}]), merged=False).merged
    # Bounded legacy runs keep the separate answer step.
    from test_agent_comparison import make_loop
    assert not make_loop(store, Script()).merged


def test_every_changed_sentence_exists_once():
    for old, _ in prompt_defaults.AGENT_MERGED_REPLACEMENTS:
        assert prompt_defaults.AGENT_SYSTEM_PROMPT.count(old) == 1, old
    for old, _ in prompt_defaults.AGENT_MERGED_READ_SOURCE_REPLACEMENTS:
        assert prompt_defaults.AGENT_MERGED_SYSTEM_PROMPT.count(old) == 1, old
    for old, _ in agent_memory.MERGED_MEMORY_DECISION:
        assert agent_memory.MEMORY_WRITE_PROMPT.count(old) == 1, old
    from app.services.agent_watch import MERGED_ORCHESTRATOR_PROMPT, ORCHESTRATOR_PROMPT
    assert ORCHESTRATOR_PROMPT.count("then call answer.") == 1
    for text in (prompt_defaults.AGENT_MERGED_SYSTEM_PROMPT, prompt_defaults.AGENT_MERGED_READ_SOURCE_PROMPT,
                 agent_memory._merged_write_prompt(), MERGED_ORCHESTRATOR_PROMPT):
        assert "call answer" not in text and "answer step" not in text


def test_the_steering_prompt_becomes_the_merged_one_with_reading_and_memory(store, monkeypatch):
    monkeypatch.delenv("AGENT_READ_SOURCES", raising=False)
    set_profile(store.db, auto_memory=True)
    loop = merged_loop(store, Merged([{}]), memory=repo(store).snapshot(UID), messages=[
        {"role": "system", "content": prompt_defaults.AGENT_SYSTEM_PROMPT}, {"role": "user", "content": "Hi"}])
    system = loop.messages[0]["content"]
    assert system.startswith(prompt_defaults.AGENT_MERGED_SYSTEM_PROMPT.split("COMPARE OR ANSWER DIRECTLY")[0])
    assert "WRITING THE ANSWER" in system and "READING SOURCES" in system
    assert "Include status_update in every compare_models, check_text and read_source call" in system
    assert "call answer" not in system
    assert agent_memory.MERGED_MEMORY_DECISION[0][1] in system
    names = list(loop.registry.tools)
    assert "answer" not in names and {"compare_models", "check_text", "read_source", "update_memory"} <= set(names)
    # The required memory decision moved to the calls that start the work.
    for name in ("compare_models", "check_text"):
        schema = loop.registry.tools[name].schema()["function"]["parameters"]
        assert "memory" in schema["properties"] and "memory" in schema["required"]
    assert "answer without a comparison" in loop.registry.tools["update_memory"].description


def test_a_custom_steering_prompt_still_gets_the_writing_rules(store):
    loop = merged_loop(store, Merged([{}]))
    system = loop.messages[0]["content"]
    assert system.startswith("Answer.") and prompt_defaults.AGENT_MERGED_ANSWER_SECTION in system


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
    assert "sources" in result and "write the answer now" in result["instruction"]
    assert not any("text_shortened_for_routing" in a for a in result["answers"])
    # The answer streamed and was complete before the check started.
    assert deltas(events) == ANSWER
    first_judge = next(i for i, e in enumerate(events) if e.get("kind") == "tool" and e.get("name") == "judge_answer")
    assert max(i for i, e in enumerate(events) if e.get("type") == "delta") < first_judge
    assert not retractions(events)
    assert all(c.get("synthesis_providers") == ["anthropic", "openai"] for c in review["comparisons"])
    assert loop.completion.text == ANSWER


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


def test_an_answer_cut_at_its_limit_is_kept_unchecked(store):
    script = Merged([{"tools": [COMPARE]}, {"text": ANSWER, "finish": "length"}])
    loop = merged_loop(store, script)
    events = []
    with pytest.raises(AnalysisBudgetExceeded, match="output token limit"):
        for event in loop.run():
            events.append(event)
    saved = store.get_turn(UID, loop.chat_id, loop.turn_id)
    assert saved["status"] == "failed" and saved["assistant_response"] == ANSWER
    assert saved["agent_review"]["versions"][-1]["text"] == ANSWER
    assert deltas(events) == ANSWER
    assert not any(e.get("kind") == "tool" and e.get("name") == "judge_answer" for e in events)


def test_every_merged_step_may_write_a_whole_answer_but_is_admitted_like_a_routing_step(store):
    from app.services.llm.agent_client import answer_output_limit, routing_output_limit
    script = Merged([{"tools": [COMPARE]}, {"text": ANSWER}])
    loop = merged_loop(store, script)
    list(loop.run())
    # Every request may write the answer...
    assert script.limits == {0: answer_output_limit(loop.model), 1: answer_output_limit(loop.model)}
    # ...but admission and further search segments use the routing allowance.
    assert loop._routing_model().max_output_tokens == routing_output_limit(loop.model)
    assert loop._answer_output() == answer_output_limit(loop.model)
    separate = merged_loop(store, Merged([{}]), merged=False)
    assert separate._routing_model().max_output_tokens == routing_output_limit(separate.model)


def free_account(store, monkeypatch, remaining):
    monkeypatch.setattr(agent_quota, "_stored_tier", lambda uid: "free")
    limit = agent_budget_config.DEFAULT_TIER_LIMITS["free"]
    ref = agent_quota.quota_ref(store.db, UID, agent_quota.day_key())
    ref.set({"used": limit - remaining})
    return ref


@pytest.mark.parametrize("merged", [False, True])
def test_a_free_account_keeps_its_research_after_a_first_message(store, monkeypatch, merged):
    """Until 2026-10-14 a merged first step reserved the answer allowance for
    every search round (~460k tokens here): a Free account (660k a day) got one
    research round instead of three once ~190k were used, the separate path
    only near the end of the allowance. Both now admit research alike."""
    from app.services.agent_delegation import ORCHESTRATOR_SEARCH_ROUNDS
    ref = free_account(store, monkeypatch, 350_000)
    answer = ("answer", {"status_update": "Writing the answer."})
    script = Merged([{"tools": [COMPARE]}, {"text": ANSWER}] if merged else
                    [{"tools": [COMPARE]}, {"tools": [answer]}, {"text": ANSWER}])
    loop = merged_loop(store, script, merged=merged)
    list(loop.run())
    saved = store.get_turn(UID, loop.chat_id, loop.turn_id)
    assert saved["status"] == "completed" and saved["consensus"] == ANSWER
    assert script.kwargs[0]["native_searches"] == ORCHESTRATOR_SEARCH_ROUNDS
    assert ref.get().to_dict()["reserved"] == 0


def test_near_the_limit_a_merged_direct_answer_keeps_its_whole_allowance(store, monkeypatch):
    """Admitted like a routing step, the answer on top may overdraw, as the
    separate answer step may after a direct answer; the search still yields."""
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
    assert agent_watch.MERGED_ORCHESTRATOR_PROMPT in system and "points to the card" in system
    assert ("agent_review" in saved) == compare


def test_the_separate_path_is_unchanged_when_the_switch_is_off(store):
    script = Script()
    loop = merged_loop(store, script, merged=False)
    list(loop.run())
    assert "answer" in loop.registry.tools
    # Steering, answer call, dedicated answer step without tools.
    assert len(orchestrator_steps(script)) == 3


def test_over_http_a_direct_answer_is_one_streamed_request(api, monkeypatch):
    """The whole path: POST /agent with the switch on, the real stream client,
    the saved turn and the recovered answer."""
    from test_agent_loop import REAL_STREAM, packet, transport, usage
    from test_agent_runs import AUTH
    from app.services.llm.agent_client import AgentCompletion
    client, store, _ = api
    monkeypatch.setenv(agent_answer_mode.ENABLED_ENV, "1")
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
        prompt_defaults.AGENT_MERGED_SYSTEM_PROMPT.split("COMPARE OR ANSWER DIRECTLY")[0])
    replay = client.post("/agent", json={**payload, "recover_only": True}, headers=AUTH)
    assert replay.status_code == 200 and replay.json()["response"] == ANSWER
    assert replay.json()["turn"]["agent_settings"]["answer_mode"] == "merged"


def test_the_live_comparison_script_measures_both_modes(store, monkeypatch):
    """scripts/evaluate_agent_answer_mode.py, offline: one scripted turn per mode."""
    import importlib.util
    from pathlib import Path
    from app.services import prompt_config
    from app.services.llm import agent_client
    path = Path(__file__).resolve().parents[1] / "scripts" / "evaluate_agent_answer_mode.py"
    spec = importlib.util.spec_from_file_location("evaluate_agent_answer_mode", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    rows = {}
    for merged in (False, True):
        script = Merged([{"tools": [COMPARE]}, {"text": ANSWER}]) if merged else Script()
        monkeypatch.setattr(agent_client, "AgentCompletion", type(script.factory()))
        rows[merged] = module.run_turn(0, "Which option is cheaper?", merged=merged,
                                       model=resolve_agent_model("claude-haiku-4-5"),
                                       families={"anthropic": "claude-haiku-4-5", "openai": "gpt-5.4-mini"},
                                       config=prompt_config.get_config(), key="test", check_sources=False)
    separate, one = rows[False], rows[True]
    assert separate["mode"] == "separate" and one["mode"] == "merged"
    assert separate["status"] == one["status"] == "completed" and not separate["error"] and not one["error"]
    # Steering, answer call, answer step against steering and answer in one.
    assert (separate["steps"], one["steps"]) == (3, 2)
    assert one["after_comparison_cost_usd"] < separate["after_comparison_cost_usd"]
    assert one["answer"] == ANSWER and not one["leaks"] and one["retractions"] == 0
    assert one["review"] == "succeeded" and one["seconds_after_comparison"] is not None
    summary = module.summary([separate, one], "merged")
    assert summary["turns"] == summary["completed"] == 1 and summary["steps"] == 2

    # Where the time goes: every provider call with claim, request, first
    # token and settlement; the time after the comparison split by step.
    for row, chat in ((separate, ["completion:0", "completion:1", "completion:2"]), (one, ["completion:0", "completion:1"])):
        calls = row["timeline"]
        assert [c["call"] for c in calls if c["kind"] == "chat"] == chat
        assert sum(c["kind"] == "comparison" for c in calls) == 2 and any(c["kind"] == "judge" for c in calls)
        for c in calls:
            assert c["status"] == "succeeded" and "error" not in c
            assert c["start"] <= c["claimed"] <= c["request"] <= c["end"] <= c["settled"]
            assert c["request"] <= c.get("first_progress", c["request"]) <= c["end"]
            assert c["seconds"] >= 0 and c["max_silence"] >= 0 and c["output_tokens"] == 20
        # The step that writes the answer streams text.
        assert "first_text" in next(c for c in calls if c["call"] == chat[-1])
        assert all(c["title"].startswith("Comparison 1") for c in calls if c["kind"] == "comparison")
        phases = row["phases"]
        assert (phases["comparison_started"] <= phases["comparison_done"] <= phases["judges_started"]
                <= phases["judges_done"] <= phases["end"])
        assert row["rate_limits"] == row["stalls"] == row["retries"] == 0
        # The test account's allowance does not hold the first step's three
        # search rounds: one refused claim, then it searches less.
        assert row["allowance_refusals"] == 1 and next(c for c in calls if c["call"] == "completion:0")["refused"] == 1
    assert separate["after_comparison"]["calls"] == ["completion:1", "completion:2"]
    assert one["after_comparison"]["calls"] == ["completion:1"]
    split = one["after_comparison"]
    assert split["read_seconds"] == 0 and split["chat_seconds"] + split["other_seconds"] >= 0
    assert one["phases"]["answer_text"] is not None and one["longest_silence"]["seconds"] >= 0


def test_the_live_comparison_script_shows_429s_and_stalls(store, monkeypatch):
    """A free 429 of the answer step and a comparison answer the stall
    watchdog ended show up in the script's timeline and counters."""
    import importlib.util
    from pathlib import Path
    from app.services import prompt_config
    from app.services.llm import agent_client
    path = Path(__file__).resolve().parents[1] / "scripts" / "evaluate_agent_answer_mode.py"
    spec = importlib.util.spec_from_file_location("evaluate_agent_answer_mode", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
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
    row = module.run_turn(0, "Which option is cheaper?", merged=True, model=resolve_agent_model("claude-haiku-4-5"),
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
    summary = module.summary([row], "merged")
    assert (summary["rate_limits"], summary["stalls"], summary["retries"]) == (1, 1, 1)


def test_the_live_comparison_script_times_real_provider_streams(monkeypatch):
    """The real stream path: the stall watchdog's progress gives the first
    token and the longest silence (keepalive comments are none), and a
    stream the watchdog ends is marked stalled."""
    import importlib.util
    from pathlib import Path
    import time
    from app.services.llm import agent_client, provider_runtime
    path = Path(__file__).resolve().parents[1] / "scripts" / "evaluate_agent_answer_mode.py"
    spec = importlib.util.spec_from_file_location("evaluate_agent_answer_mode", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

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

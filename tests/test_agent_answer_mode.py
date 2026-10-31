"""The Agent writes its answer itself (agent_answer_mode): its plain-text
message without tool calls is the answer; after a comparison the step that
reads the answers may write it, a direct answer is one call. The user's
chosen models review it (agent_audit.py, test_agent_audit.py).

Until 2026-10-14 this was the merged path behind AGENT_MERGED_ANSWER next to
a separate, tool-free answer step (git tag agent-separate-answer-last); now
it is the only path. test_agent_comparison covers compare_models and its
accounting with the shared Script; these tests cover streaming, holding back
and retracting the answer text, memory and Watch replies, and limits. Their
reviewers never start (agent_reviewers.py) unless a test asks for them.
"""
from dataclasses import replace
import json
from types import SimpleNamespace

import pytest

from app.services import agent_budget_config, agent_delegation, agent_memory, agent_quota, prompt_defaults, user_memory
from app.services.agent_memory import FirestoreAgentMemoryRepository
from app.services.agent_comparison import answer_hash, comparison_selection
from app.services.agent_delegation import DelegationLoop
from app.services.agent_delegation_config import defaults
from app.services.agent_policy import AgentPolicy
from app.services.llm.agent_client import measured_usage, resolve_agent_model
from app.services.agent_provider_limits import ModelOutputLimit, ProviderCooldowns
from app.services.llm.engines import _ProviderHTTPStatusError
from app.services.llm.provider_runtime import AnalysisBudgetExceeded, ProviderCancellation
from agent_reviewers import inert_reviewers, without_reviewers  # noqa: F401  (fixture)
from test_agent_comparison import REVIEWER, Script
from test_agent_runs import UID, api, pending, store  # noqa: F401  (fixtures)


ANSWER = ("The first option costs 100 euros a month and includes the support plan. "
          "The second option is cheaper at first but adds fees once the team grows, "
          "so over two years the first option ends up cheaper for a team of ten. ") * 3
# A long comparison answer: the agent reads it whole (no routing gist).
MODEL_ANSWER = "The first option costs 100. The constraint matters. " + "Details on pricing. " * 500
COMPARE = ("compare_models", {"question": "Which option is cheaper over two years?", "context": "Team of ten."})


def set_profile(db, **fields):
    db.collection("users").document(UID).collection("memory").document("profile").set(
        {**user_memory.empty_profile(), **fields})


def repo(store):
    return FirestoreAgentMemoryRepository(store.db)


def tool_call(index, n, name, args):
    return {"id": f"call_{index}_{n}", "type": "function", "function": {"name": name, "arguments": json.dumps(args)}}


class Merged(Script):
    """A scripted Agent turn. ``plan[i]`` is what step completion:i does:
    ``text`` (streamed in chunks of 50), then ``tools`` [(name, args)];
    ``sources`` arrive before the text (the step's own search found them).
    A reviewer's round replies with no marks (Script)."""

    def __init__(self, plan, *, cited=(), **kwargs):
        super().__init__(**kwargs)
        self.plan = plan
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
                    if messages[0]["content"].startswith(REVIEWER):
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
                    calls.append(tool_call(index, n, name, args))
                if calls:
                    self._tool_parts = dict(enumerate(calls))
                    # As AgentCompletion.stream says it when a call begins;
                    # what the user sees once the loop has taken it in.
                    yield self.event("status", "tool_call", status="working")
                    loop = getattr(script, "loop", None)
                    script.shown_at_call = loop.completion.text if loop is not None else None
                    self.tool_calls, self.finish_reason = calls, "tool_calls"
                else:
                    self.finish_reason = step.get("finish", "stop")
        return Completion()


def merged_loop(store, script, *, messages=None, memory=None, reviewers=False):
    """A chat turn with ``script``'s steps; its reviewers never start
    (agent_reviewers.InertAnswerAudit) unless ``reviewers``."""
    chat, turn = pending(store)
    config = {**defaults(), "enabled": False, "max_searches": 0}
    loop = DelegationLoop(store=store, uid=UID, chat_id=chat, turn_id=turn["id"],
        model=resolve_agent_model("claude-haiku-4-5"),
        messages=messages or [{"role": "system", "content": "Answer."},
                              {"role": "user", "content": "Which option is cheaper?"}],
        api_key="test", cancellation=ProviderCancellation(), policy=AgentPolicy.for_chat(config),
        delegation_config=config, completion_factory=script.factory,
        comparison_models=comparison_selection({"anthropic": "claude-haiku-4-5", "openai": "gpt-5.4-mini"}),
        memory=memory)
    if not reviewers:
        without_reviewers(loop)
    script.loop = loop
    return loop


def reviewed(review, text):
    """The saved review is the reviewers' review of exactly ``text``."""
    return review.get("mode") == "audit" and review.get("answer_hash") == answer_hash(text)


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
    tool and get the facts of the app (AGENT_AUDIT_ANSWER_SECTION)."""
    from test_agent_comparison import make_loop
    for loop in (merged_loop(store, Merged([{}])), make_loop(store, Script())):
        assert loop.merged and "answer" not in loop.registry.tools
        assert prompt_defaults.AGENT_AUDIT_ANSWER_SECTION in loop.messages[0]["content"]


def test_no_prompt_points_to_the_removed_answer_step():
    from app.services import agent_read_source, agent_watch
    assert prompt_defaults.AGENT_AUDIT_SYSTEM_PROMPT == (prompt_defaults._AGENT_AUDIT_STEERING + "\n\n"
                                                         + prompt_defaults.AGENT_AUDIT_ANSWER_SECTION)
    assert prompt_defaults.DEFAULT_PROMPTS["agent"] == prompt_defaults.AGENT_AUDIT_SYSTEM_PROMPT
    for text in (prompt_defaults.AGENT_AUDIT_SYSTEM_PROMPT, agent_memory.AUDIT_MEMORY_WRITE_PROMPT,
                 agent_watch.AUDIT_PROMPT, agent_read_source.UNTRUSTED_NOTE):
        assert "call answer" not in text and "answer step" not in text and "answer call" not in text, text[:80]


def test_the_agent_prompt_and_its_tools_in_every_chat(store, monkeypatch):
    """One mode since 2026-10-31: the facts of the app once, compare_models
    with only what the models are asked, no check_text, and memory changes
    through update_memory alone."""
    monkeypatch.delenv("AGENT_READ_SOURCES", raising=False)
    set_profile(store.db, auto_memory=True)
    loop = merged_loop(store, Merged([{}]), memory=repo(store).snapshot(UID), messages=[
        {"role": "system", "content": prompt_defaults.AGENT_AUDIT_SYSTEM_PROMPT}, {"role": "user", "content": "Hi"}])
    system = loop.messages[0]["content"]
    assert system.startswith(prompt_defaults.AGENT_AUDIT_SYSTEM_PROMPT)
    # The code prompt already carries the app's facts: not appended twice.
    assert system.count("HOW CONSENS.IO WORKS") == 1
    assert "call answer" not in system and "status_update" not in system and "check_text" not in system
    names = list(loop.registry.tools)
    assert "answer" not in names and "check_text" not in names
    assert {"compare_models", "read_source", "update_memory"} <= set(names)
    # What the models are asked, and nothing that rides along.
    schema = loop.registry.tools["compare_models"].schema()["function"]["parameters"]
    assert set(schema["properties"]) == {"question", "context", "file_ids", "depth"}
    assert "evidence" not in json.dumps(loop.registry.tools["update_memory"].schema())


def test_a_custom_steering_prompt_still_gets_the_facts_of_the_app(store):
    loop = merged_loop(store, Merged([{}]))
    system = loop.messages[0]["content"]
    assert system.startswith("Answer.") and prompt_defaults.AGENT_AUDIT_ANSWER_SECTION in system


# --- Comparison and answer in one call -------------------------------------------

def test_the_step_that_reads_the_answers_writes_the_reviewed_answer(store):
    script = Merged([{"tools": [COMPARE]}, {"text": ANSWER}])
    loop = merged_loop(store, script, reviewers=True)
    events = list(loop.run())
    saved = store.get_turn(UID, loop.chat_id, loop.turn_id)
    review = saved["agent_review"]
    assert saved["status"] == "completed" and saved["consensus"] == ANSWER
    assert review["status"] == "succeeded" and reviewed(review, ANSWER)
    # Steering, then the answer from the same context: no separate answer step.
    assert orchestrator_steps(script) == ["completion:0", "completion:1"]
    assert "tools" in script.kwargs[1] and script.kwargs[1]["allow_tool_calls"] is True
    assert script.kwargs[1].get("prompt_cache", True) is True
    # Full answers and the source list are in the tool result the agent reads.
    result = tool_result(loop, "call_0_0")
    assert [a["text"] for a in result["answers"]] == [MODEL_ANSWER.strip()] * 2
    assert "sources" in result and "still yours to do" in result["instruction"]
    assert not any("text_shortened_for_routing" in a for a in result["answers"])
    # The depth that steered the comparison models is not shown.
    assert "depth" not in result
    # No app note follows the evidence (until 2026-10-31 AGENT_WRITE_NOTE):
    # the answers advise, and the work goes on.
    request = script.requests[1]
    assert request[-1]["role"] == "tool" and request[-1]["tool_call_id"] == "call_0_0"
    # The answer streamed and was complete before the review started.
    assert deltas(events) == ANSWER
    review_call = next(i for i, e in enumerate(events) if e.get("kind") == "tool" and e.get("name") == "audit_answer")
    assert max(i for i, e in enumerate(events) if e.get("type") == "delta") < review_call
    assert not retractions(events)
    assert all(c.get("synthesis_providers") == ["anthropic", "openai"] for c in review["comparisons"])
    assert loop.completion.text == ANSWER


def test_a_direct_answer_is_one_call_and_reviewed(store):
    """Without a comparison too: until 2026-10-31 a direct answer went
    unchecked in comparison mode."""
    script = Merged([{"text": ANSWER}])
    loop = merged_loop(store, script, reviewers=True)
    events = list(loop.run())
    saved = store.get_turn(UID, loop.chat_id, loop.turn_id)
    assert saved["status"] == "completed" and saved["assistant_response"] == ANSWER
    assert orchestrator_steps(script) == ["completion:0"]
    review = saved["agent_review"]
    assert review["status"] == "succeeded" and reviewed(review, ANSWER) and review["comparisons"] == []
    # One final round per reviewer: the agent called no tool to follow.
    assert sorted(model for _, model in script.reviews) == ["anthropic/claude-haiku-4.5", "openai/gpt-5.4-mini"]
    assert [e["status"] for e in events if e.get("kind") == "tool" and e.get("name") == "audit_answer"] == [
        "running", "succeeded"]
    assert deltas(events) == ANSWER


def test_a_greeting_shows_at_once_when_the_step_ends(store):
    loop = merged_loop(store, Merged([{"text": "Hello! How can I help?"}]))
    events = list(loop.run())
    assert [e["text"] for e in events if e.get("type") == "delta"] == ["Hello! How can I help?"]
    assert loop.completion.text == "Hello! How can I help?"


def notes(events):
    return [e["text"] for e in events if e.get("kind") == "progress" and e.get("id", "").endswith("/note")]


def test_a_short_preamble_never_shows_as_the_answer_but_stands_as_a_note(store):
    script = Merged([{"text": "I'll compare the options.", "tools": [COMPARE]}, {"text": ANSWER}])
    loop = merged_loop(store, script)
    events = list(loop.run())
    assert deltas(events) == ANSWER and not retractions(events)
    # Since 2026-10-28 also a text too short to have streamed (Max: in the trace).
    assert notes(events) == ["I'll compare the options."]


def test_a_long_text_before_a_tool_call_moves_whole_into_the_timeline_once_the_call_begins(store):
    preamble = "Let me first think about what matters here. " * 12
    second = "\n\n\n- First the fees.\n- Then   the terms."
    script = Merged([{"text": preamble + second, "tools": [COMPARE]}, {"text": ANSWER}])
    loop = merged_loop(store, script)
    events = list(loop.run())
    assert len(retractions(events)) == 1
    clear = events.index(retractions(events)[0])
    # What streamed before the clear was the preamble; after it only the answer.
    assert deltas(events[:clear]) == preamble + second and deltas(events[clear:]) == ANSWER
    # Moved when the call began, not when its arguments had streamed.
    assert script.shown_at_call == ""
    # Whole, not cut to 400 characters; its lines kept, spaces tidied.
    assert notes(events)[-1] == preamble.strip() + "\n\n- First the fees.\n- Then the terms."
    assert len(notes(events)[-1]) > 400
    saved = store.get_turn(UID, loop.chat_id, loop.turn_id)
    assert saved["consensus"] == ANSWER


@pytest.mark.parametrize("names,moves", [(["update_memory"], False), (["prepare_watch", "update_plan"], False),
                                         (["update_memory", "vm_exec"], True), (["vm_exec"], True), ([""], False)])
def test_only_a_call_that_needs_results_moves_the_shown_text_when_it_begins(store, names, moves):
    """A side tool leaves a written answer standing (_answered_with_tools),
    and a call without a name yet may still turn out to be one."""
    loop = merged_loop(store, Merged([{"text": ANSWER}]))
    value = SimpleNamespace(step_id="completion:0", text="The answer so far.", published="The answer so far.",
                            _tool_parts={n: {"function": {"name": name}} for n, name in enumerate(names)})
    moved = list(loop._move_preamble(value))
    assert bool(moved) is moves and (value.published == "") is moves


def test_a_reply_after_the_agents_own_search_is_the_answer(store):
    """The agent researches the answer itself: what it writes after its own
    search streams and stands. Until 2026-10-31 comparison mode held such a
    reply back once and sent the question through a comparison."""
    research = "From my search: the first option is cheaper. " * 20
    found = [{"url": "https://example.org/found", "title": "Found"}]
    script = Merged([{"text": research, "sources": found}])
    loop = merged_loop(store, script)
    events = list(loop.run())
    assert orchestrator_steps(script) == ["completion:0"]
    assert deltas(events) == research and loop.completion.text == research and not retractions(events)
    assert not any(m["content"].startswith(("App rule", "The web-search phase")) for m in loop.messages
                   if m["role"] == "user" and isinstance(m["content"], str))
    saved = store.get_turn(UID, loop.chat_id, loop.turn_id)
    assert saved["status"] == "completed" and saved["assistant_response"] == research
    assert reviewed(saved["agent_review"], research)


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


# A short one was held back for its length and never streamed: it is shown
# whole and saved too (DelegationLoop._keep_cut_answer, review 2026-10-14).
# The turn keeps it (agent_runs.finish_run), not a version for the reviewers.
@pytest.mark.parametrize("text", [ANSWER, "The first option is cheaper over two years."])
def test_an_answer_cut_at_its_limit_is_kept_unreviewed(store, text):
    script = Merged([{"tools": [COMPARE]}, {"text": text, "finish": "length"}])
    loop = merged_loop(store, script)
    events = []
    with pytest.raises(AnalysisBudgetExceeded, match="output token limit"):
        for event in loop.run():
            events.append(event)
    saved = store.get_turn(UID, loop.chat_id, loop.turn_id)
    assert saved["status"] == "failed" and saved["assistant_response"] == text
    assert saved["agent_review"]["versions"] == [] and saved["agent_review"]["comparisons"]
    assert deltas(events) == text
    assert not any(e.get("kind") == "tool" and e.get("name") == "audit_answer" for e in events)


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
    ref = agent_quota.quota_ref(store.db, UID, agent_quota.day_key() + agent_quota.LEDGER_UNIT)
    ref.set({"used": limit - remaining})
    return ref


def test_a_free_account_keeps_its_research_after_a_first_message(store, monkeypatch):
    """Until 2026-10-14 a first step that may write the answer reserved the
    answer allowance for every search round (~460k tokens here): a Free
    account (660k a day) got one research round instead of three once ~190k
    were used. It is admitted like a routing step now, with every search
    round the agent has in a step (here with 60 % of the day left)."""
    from app.services.agent_audit import AGENT_SEARCH_ROUNDS
    ref = free_account(store, monkeypatch, 600_000)
    script = Merged([{"tools": [COMPARE]}, {"text": ANSWER}])
    loop = merged_loop(store, script)
    list(loop.run())
    saved = store.get_turn(UID, loop.chat_id, loop.turn_id)
    assert saved["status"] == "completed" and saved["consensus"] == ANSWER
    assert script.kwargs[0]["native_searches"] == AGENT_SEARCH_ROUNDS
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
    # The answer's provider cost, $0.0001, is 87 micro-euros (rounded up).
    assert ledger["reserved"] == 0 and ledger["used"] == used + 87


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
    assert reviewed(saved["agent_review"], ANSWER) and deltas(events) == ANSWER


def test_after_paid_comparisons_a_refused_routing_step_closes_the_turn(store, monkeypatch):
    """Audit 2026-10-28: after the first paid comparison every further
    routing step overdrew the daily allowance and was never refused before
    turn_steps. Now only the closing answer (no tools) and the reviewers'
    final rounds may: a routing step the allowance refuses leaves its step to
    that answer."""
    ref = free_account(store, monkeypatch, 400_000)
    script = Merged([{"tools": [COMPARE]}, {"text": ANSWER}])
    loop = merged_loop(store, script)
    execute = loop._execute_stream

    def spend(value, call, *args):
        result = yield from execute(value, call, *args)
        if call["function"]["name"] == "compare_models":
            # Another tab used up the rest of the day meanwhile.
            ref.set({**ref.get().to_dict(), "used": agent_budget_config.DEFAULT_TIER_LIMITS["free"]})
        return result

    monkeypatch.setattr(loop, "_execute_stream", spend)
    events = list(loop.run())
    saved = store.get_turn(UID, loop.chat_id, loop.turn_id)
    assert saved["status"] == "completed" and saved["consensus"] == ANSWER
    # Step 1 was refused before its claim and written as the closing answer:
    # tools listed, none callable.
    assert orchestrator_steps(script) == ["completion:0", "completion:1"]
    assert script.kwargs[1]["allow_tool_calls"] is False
    assert script.requests[1][-1]["content"].startswith("App rule: this message has reached its limit.")
    assert reviewed(saved["agent_review"], ANSWER) and deltas(events) == ANSWER


def test_without_paid_comparisons_a_refused_routing_step_ends_the_turn(store, monkeypatch):
    free_account(store, monkeypatch, 0)
    script = Merged([{"text": ANSWER}])
    loop = merged_loop(store, script)
    with pytest.raises(agent_quota.AgentTokenBudgetExceeded):
        list(loop.run())
    assert orchestrator_steps(script) == []


def test_an_answer_followed_only_by_a_memory_save_stands(store):
    """Claude may write the answer and then save a memory: retracting it would
    leave only "Saved." for the next step."""
    set_profile(store.db, auto_memory=True)
    save = ("update_memory", {"changes": [{"op": "add", "text": "Leads a team of ten."}]})
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
    save = ("update_memory", {"changes": [{"op": "add", "text": "Leads a team of ten."}]})
    short = "Got it, I will keep in mind that you lead a team of ten."
    script = Merged([{"text": short, "tools": [save]}, {"text": "Saved."}])
    loop = merged_loop(store, script, memory=repo(store).snapshot(UID))
    events = list(loop.run())
    assert orchestrator_steps(script) == ["completion:0"]
    assert loop.completion.text == short and deltas(events) == short and not retractions(events)
    assert [item["text"] for item in repo(store).get(UID)[0]] == ["Leads a team of ten."]


# An id on an added memory: update_memory refuses the change (normalize_change).
REFUSED_SAVE = ("update_memory", {"changes": [{"op": "add", "id": "m1a2b3c", "text": "Leads a team of ten."}]})


@pytest.mark.parametrize("reply", ["Got it, I will keep in mind that you lead a team of ten.", ANSWER],
                         ids=["held", "shown"])
def test_a_reply_next_to_a_refused_memory_save_is_written_again(store, reply):
    """The reply may confirm a change that was refused: it goes back (a shown
    one stays as a note) and the next step writes the answer with the
    refusal in view (_side_results_accepted, review 2026-10-14)."""
    set_profile(store.db, auto_memory=True)
    retry = "I could not save that memory."
    script = Merged([{"text": reply, "tools": [REFUSED_SAVE]}, {"text": retry}])
    loop = merged_loop(store, script, memory=repo(store).snapshot(UID))
    events = list(loop.run())
    assert "error" in tool_result(loop, "call_0_0") and repo(store).get(UID)[0] == []
    assert orchestrator_steps(script) == ["completion:0", "completion:1"]
    assert any(m.get("role") == "tool" and "error" in m["content"] for m in script.requests[1])
    saved = store.get_turn(UID, loop.chat_id, loop.turn_id)
    assert saved["status"] == "completed" and saved["assistant_response"] == retry
    assert shown(events) == retry
    # Since 2026-10-28 also a reply too short to have been on screen leaves
    # its note: the agent's words stay in the timeline.
    notes = [e for e in events if e.get("kind") == "progress" and e.get("id", "").endswith("/note")]
    assert len(notes) == 1 and notes[0]["text"] == reply.strip()


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
    invalid = ("compare_models", {"question": "", "context": ""})
    side = ("prepare_watch", WATCH) if accepted else REFUSED_SAVE
    wrap_up = "From the comparisons: the first option is cheaper over two years for a team of ten. " * 4
    script = Merged([{"tools": [COMPARE]}, {"tools": [invalid]}, {"tools": [invalid]},
                     {"text": ANSWER, "tools": [side]}, {"text": wrap_up}])
    loop = merged_loop(store, script, memory=repo(store).snapshot(UID))
    loop.watch_tools.outlook = outlook()
    events = list(loop.run())
    answer = ANSWER if accepted else wrap_up
    saved = store.get_turn(UID, loop.chat_id, loop.turn_id)
    assert saved["status"] == "completed" and saved["consensus"] == answer
    assert reviewed(saved["agent_review"], answer)
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
    assert reviewed(saved["agent_review"], opening + rest)
    assert deltas(events) == opening + rest and not retractions(events)


def test_a_step_that_breaks_off_after_its_own_search_saves_what_was_shown(store, monkeypatch):
    """A first step shows its opening, gets its own search results, writes on
    and its stream breaks: the partial answer saved is what the user saw
    (DelegationLoop._step, review 2026-10-14). Since 2026-10-31 the text after
    the search shows too: the agent researches the answer itself (until then
    comparison mode held it back as research)."""
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
    assert deltas(events) == opening + research
    assert saved["status"] == "failed" and saved["assistant_response"] == opening + research


def test_a_page_read_after_the_comparison_is_in_context_and_reviewed(store, monkeypatch):
    from test_agent_web_fetch import CITED, PAGE, fake_fetch
    monkeypatch.setenv("AGENT_READ_SOURCES", "1")
    fake_fetch(monkeypatch)
    script = Merged([{"tools": [COMPARE]}, {"tools": [("read_source", {"url": CITED})]}, {"text": ANSWER}],
                    cited=(CITED,))
    loop = merged_loop(store, script)
    events = list(loop.run())
    saved = store.get_turn(UID, loop.chat_id, loop.turn_id)
    assert saved["status"] == "completed" and saved["consensus"] == ANSWER
    assert reviewed(saved["agent_review"], ANSWER)
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
    assert agent_watch.AUDIT_PROMPT in system
    # Reviewed either way; the comparison only where the agent asked for one.
    assert reviewed(saved["agent_review"], ANSWER)
    assert len(saved["agent_review"]["comparisons"]) == (1 if compare else 0)


def test_over_http_a_direct_answer_is_one_streamed_request(api, monkeypatch, inert_reviewers):
    """The whole path: POST /agent, the real stream client, the saved turn
    and the recovered answer. The reviewers never start (agent_reviewers.py):
    the one request is the agent's."""
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
    # Claude's system prompt goes out as one block with a cache point of its
    # own (agent_client.with_cache_points).
    [system] = requests[0]["messages"][0]["content"]
    assert system["cache_control"] == {"type": "ephemeral"}
    assert system["text"].startswith(prompt_defaults.AGENT_AUDIT_SYSTEM_PROMPT)
    replay = client.post("/agent", json={**payload, "recover_only": True}, headers=AUTH)
    assert replay.status_code == 200 and replay.json()["response"] == ANSWER
    assert replay.json()["turn"]["agent_settings"]["answer_mode"] == "merged"

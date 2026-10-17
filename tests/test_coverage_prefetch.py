"""The answer check starts while the Agent writes (since 2026-10-17).

Coverage windows of settled sentences run during the stream; the check of the
finished answer collects them and asks only the rest. These tests hold the
three promises that makes: a sentence is numbered the same before and after
the answer is finished, an early verdict is used only for the exact same
sentence, and nothing is asked twice. Since 2026-10-18 the windows that are
done also reach the page as provisional marks while Differences still runs:
only answered sentences, only for the exact fixed answer, never saved.
"""
import json
import threading
import time

import pytest

from app.services.llm import coverage_judge as coverage
from app.services.llm.consensus_engine import (
    AGENT_COVERAGE_WINDOW, CHAT_MAX_CONSENSUS_SENTENCES, _build_judge_context, _CoverageProgress,
    _enumerate_consensus_sentences, _run_coverage_judge, prefetch_coverage_window, settled_sentence_count,
)
from app.services.llm.provider_runtime import ProviderCancelled, current_provider_cancellation
from app.services.llm.task_transport import bind_task_transport
from test_agent_runs import store  # noqa: F401 (fixture)

ANSWERS = {"OpenAI": "Paris is the capital. It has two million people.",
           "Anthropic": "Paris is the capital of France.", "Gemini": "France's capital is Lyon."}

MARKDOWN = """# Heading stays context

Paris is the capital of France. It is home to about 2.1 million people, ca. 12 million in the region.

| City | Note |
|------|------|
| Paris | The largest city of the country |
| Lyon | A city with a long silk history |

- First item says something concrete.
- Second item says something else again.

```
code is never numbered at all
```

The last paragraph closes the answer here. It has a second sentence too.
"""


def entries(ids, labels, stance=lambda label: "supports"):
    return json.dumps({"sentences": [{"id": key, "classification": "claim",
                                      "models": {label: stance(label) for label in labels},
                                      "counter_quotes": []} for key in ids]})


def schema_ids(kwargs):
    return list(kwargs["json_schema"]["properties"]["sentences"]["items"]["properties"]["id"]["enum"])


def schema_labels(kwargs):
    return list(kwargs["json_schema"]["properties"]["sentences"]["items"]["properties"]["models"]["properties"])


def test_settled_sentences_keep_their_number_and_wording_while_the_answer_grows():
    _, final = _enumerate_consensus_sentences(MARKDOWN, limit=CHAT_MAX_CONSENSUS_SENTENCES)
    assert len(final) >= 8
    seen = 0
    for cut in range(len(MARKDOWN) + 1):
        part = MARKDOWN[:cut]
        settled = settled_sentence_count(part)
        _, sentences = _enumerate_consensus_sentences(part, limit=CHAT_MAX_CONSENSUS_SENTENCES)
        assert sentences[:settled] == final[:settled], cut
        assert settled >= seen  # never goes back
        seen = settled
    # Only lines followed by another complete line count: the table header
    # line is decided by the line after it.
    assert settled_sentence_count("Intro sentence is here.\n| A | B |\n") == 1
    assert settled_sentence_count("A first sentence here.") == 0


def test_early_verdicts_are_used_only_for_the_same_sentence_and_the_rest_runs_once():
    answer = "".join(f"Fact number {n} holds true.\n" for n in range(1, 41))
    early_text = "".join(f"Fact number {n} holds true.\n" for n in range(1, 21))
    asked, lock = [], threading.Lock()

    def transport(provider, api_model, model_ref, **kwargs):
        with lock:
            asked.append(schema_ids(kwargs))
        # Anthropic contradicts every sentence: the label mapping must survive
        # two different anonymizations (early window and final check).
        return entries(schema_ids(kwargs), schema_labels(kwargs))

    with bind_task_transport(transport):
        early = prefetch_coverage_window(ANSWERS, early_text, coverage.sentence_ids(range(16)), {"OpenRouter": "k"},
                                         "OpenAI", resolved_question="Capital?")
    assert asked == [coverage.sentence_ids(range(16))]
    assert set(early["entries"]["s1"]["models"]) == set(ANSWERS)  # keyed by model, not by label
    early["entries"]["s3"]["models"]["Anthropic"] = "contradicts"
    # Sentence 2 changed after the window started: it is asked again.
    launched = {sid: text for sid, text in early["sentences"].items()}
    launched["s2"] = "Fact number 2 was something else."
    early["sentences"]["s2"] = launched["s2"]

    class Prefetch:
        def launched(self):
            return launched

        def results(self):
            yield early

    asked.clear()
    context = _build_judge_context(ANSWERS, answer, None, "Capital?", sentence_limit=CHAT_MAX_CONSENSUS_SENTENCES)
    with bind_task_transport(transport):
        result, meta = _run_coverage_judge(context, {"OpenRouter": "k"}, "OpenAI", chat_mode=True,
                                           window=AGENT_COVERAGE_WINDOW, prefetch=Prefetch())
    asked_ids = sorted(sum(asked, []), key=lambda key: int(key[1:]))
    assert asked_ids == ["s2"] + [f"s{n}" for n in range(17, 41)]
    assert all(len(ids) <= AGENT_COVERAGE_WINDOW for ids in asked)
    assert len(result) == 40 and meta["missing"] == 0 and meta["prefetched"] == 15
    anthropic = next(label for label, name in context.anon_map.items() if name == "Anthropic")
    assert result["s3"]["models"][anthropic] == "contradicts"
    assert all(stance == "supports" for label, stance in result["s4"]["models"].items())


def test_each_finished_window_reaches_the_page_with_its_sentences_only():
    answer = "".join(f"Fact number {n} holds true.\n" for n in range(1, 41))
    early_text = "".join(f"Fact number {n} holds true.\n" for n in range(1, 21))
    reports, answered, lock = [], set(), threading.Lock()
    first_report = threading.Event()

    def receiver(preview):
        with lock:
            reports.append(({claim["sentence_id"] for claim in preview["claims"]}, set(answered), preview))
        first_report.set()

    def transport(provider, api_model, model_ref, **kwargs):
        ids = schema_ids(kwargs)
        if "s33" in ids:
            # The last window is still out when the page gets its first marks.
            assert first_report.wait(5)
        reply = entries(ids, schema_labels(kwargs))
        with lock:
            answered.update(coverage.sentence_id_number(sid) for sid in ids)
        return reply

    with bind_task_transport(transport):
        early = prefetch_coverage_window(ANSWERS, early_text, coverage.sentence_ids(range(16)), {"OpenRouter": "k"},
                                         "OpenAI", resolved_question="Capital?")
    early["entries"]["s3"]["models"]["Anthropic"] = "contradicts"
    early["sentences"]["s2"] = "Fact number 2 was something else."
    answered.clear()

    class Prefetch:
        def launched(self):
            return dict(early["sentences"])

        def results(self):
            yield early

    context = _build_judge_context(ANSWERS, answer, None, "Capital?", sentence_limit=CHAT_MAX_CONSENSUS_SENTENCES)
    with bind_task_transport(transport):
        result, _ = _run_coverage_judge(context, {"OpenRouter": "k"}, "OpenAI", chat_mode=True,
                                        window=AGENT_COVERAGE_WINDOW, prefetch=Prefetch(),
                                        progress=_CoverageProgress(context, answer, receiver))
    assert len(result) == 40
    adopted = {1, *range(3, 17)}
    seen = set()
    for claimed, known, _ in reports:
        # Never a mark for a sentence no window has answered yet: it would
        # read as checked (grey "thin") while it is still being checked.
        assert claimed <= known | adopted
        # Every report holds every mark so far: a late reader needs only the newest.
        assert claimed >= seen
        seen = claimed
    assert seen == set(range(1, 41))
    assert any(33 not in claimed for claimed, _, _ in reports)
    last = reports[-1][2]
    assert last["models_compared"] == sorted(ANSWERS) and last["checked"] == last["sentences"] == 40
    claims = {claim["sentence_id"]: claim for claim in last["claims"]}
    assert claims[1]["anchor"] == "Fact number 1 holds true." and claims[1]["coverage"] == "supported"
    # Real model names, not the labels of either anonymization.
    assert [item["model"] for item in claims[3]["dissent"]] == ["Anthropic"] and claims[3]["coverage"] == "split"


def test_provisional_marks_go_out_only_while_the_exact_answer_is_checked():
    import queue
    from types import SimpleNamespace
    from app.services.agent_comparison import ComparisonTools, answer_hash

    tools = SimpleNamespace(lock=threading.RLock(), review={"status": "running", "checks": []}, text="Fixed answer.",
                            loop=SimpleNamespace(outgoing=queue.Queue(maxsize=1)))
    preview = {"claims": [{"anchor": "Fixed answer.", "agree": ["OpenAI"], "dissent": []}],
               "models_compared": ["OpenAI"], "checked": 1, "sentences": 1}
    digest = answer_hash("Fixed answer.")

    def send(value):
        ComparisonTools.preview_coverage(tools, "c1", value, preview)

    send(answer_hash("A text that was taken back."))
    assert tools.loop.outgoing.empty()
    send(digest)
    assert tools.loop.outgoing.get_nowait() == {"type": "coverage_preview", "answer_hash": digest,
                                                "comparison_id": "c1", **preview}
    # A full event queue drops the preview, never the check.
    send(digest)
    send(digest)
    tools.loop.outgoing.get_nowait()
    for review in ({"status": "succeeded", "checks": []}, {"status": "cancelled", "checks": []}, None):
        tools.review = review
        send(digest)
        assert tools.loop.outgoing.empty()


class FakeLoop:
    def __init__(self):
        from app.services.llm.provider_runtime import ProviderCancellation
        from types import SimpleNamespace
        self.cancellation, self.api_key = ProviderCancellation(), "k"
        self.policy = SimpleNamespace(account_budget_only=True)


class FakeTools:
    def __init__(self, transport):
        from app.services.agent_comparison import AgentPreferences
        self.comparisons = [{"id": "c1", "question": "Capital?", "answers": [
            {"provider": "openai", "text": ANSWERS["OpenAI"]}, {"provider": "anthropic", "text": ANSWERS["Anthropic"]}]}]
        self.text, self.passage, self.reader = "", None, None
        self.preferences, self.lock, self.loop = AgentPreferences(), threading.RLock(), FakeLoop()
        self.judge_transport = transport

    def _judge_reference(self):
        return "OpenAI"


def test_windows_start_as_sentences_settle_and_stop_when_the_text_is_taken_back():
    from app.services.agent_coverage_prefetch import CoveragePrefetch
    started, release = [], threading.Event()

    def transport(provider, api_model, model_ref, **kwargs):
        started.append(schema_ids(kwargs))
        cancellation = current_provider_cancellation()
        while not release.wait(.01):
            if cancellation is not None and cancellation.cancelled:
                raise ProviderCancelled("stopped")
        return entries(schema_ids(kwargs), schema_labels(kwargs))

    tools = FakeTools(transport)
    prefetch = CoveragePrefetch(tools)
    text = ""
    for n in range(1, 40):
        text += f"Fact number {n} holds true.\n"
        prefetch.update(text)
    # 38 settled sentences: two full windows, the rest waits for the end.
    deadline = time.time() + 5
    while len(started) < 2 and time.time() < deadline:
        time.sleep(.01)
    assert sorted(started) == sorted([coverage.sentence_ids(range(16)),
                                      [coverage.sentence_id(n) for n in range(17, 33)]])
    futures = [future for _, future in prefetch.windows["c1"][1]]
    prefetch.discard()
    assert prefetch.windows == {} and prefetch.started == 0
    # Stopped windows end without a verdict instead of running to the end.
    assert [future.result(timeout=5) for future in futures] == [None, None]
    assert not release.is_set()
    prefetch.close()


def test_no_windows_when_the_check_is_off_or_the_answer_is_fixed():
    from app.services.agent_comparison import AgentPreferences
    from app.services.agent_coverage_prefetch import CoveragePrefetch
    calls = []
    tools = FakeTools(lambda *args, **kwargs: calls.append(1))
    text = "".join(f"Fact number {n} holds true.\n" for n in range(1, 40))
    tools.preferences = AgentPreferences(judges="off")
    CoveragePrefetch(tools).update(text)
    tools.preferences, tools.text = AgentPreferences(), "fixed"
    CoveragePrefetch(tools).update(text)
    assert calls == []


ANSWER = "".join(f"Fact number {n} holds true for this option.\n" for n in range(1, 41))


def streaming_turn(store, *, chat=True, fail_after=None, judge_delay=0.0, events=None):
    """A scripted Agent turn whose answer streams line by line. Returns
    (loop, coverage calls as (ids, prompt), raised exception or None);
    ``events`` collects what the turn sent to the page."""
    from dataclasses import replace
    from test_agent_comparison import Script, make_loop
    from app.services.llm.agent_client import measured_usage
    calls, lock = [], threading.Lock()

    class StreamingScript(Script):
        def factory(self):
            completion = super().factory()
            base, script = completion.stream, self

            def stream(*, model, messages, **kwargs):
                step = completion.step_id
                if step.startswith("completion:") and int(step.split(":")[-1]) >= script.compares:
                    script.calls.append((step, model.model))
                    completion.usage = measured_usage({"prompt_tokens": 50, "completion_tokens": 20, "cost": .0001}, model)
                    completion.text, completion.finish_reason = "", "stop"
                    for index, line in enumerate(ANSWER.splitlines(keepends=True), 1):
                        if fail_after is not None and index > fail_after:
                            raise RuntimeError("The provider stopped mid-answer")
                        completion.text += line
                        yield {"type": "delta", "text": line}
                    return
                schema = (model.request_config.get("response_format") or {}).get("json_schema", {}).get("schema")
                if schema and "sentences" in schema["properties"]:
                    ids = schema["properties"]["sentences"]["items"]["properties"]["id"]["enum"]
                    with lock:
                        calls.append((list(ids), messages[-1]["content"]))
                    time.sleep(judge_delay)
                yield from base(model=model, messages=messages, **kwargs)

            completion.stream = stream
            return completion

    loop = make_loop(store, StreamingScript())
    loop.policy = replace(loop.policy, account_budget_only=chat)
    try:
        for event in loop.run():
            if events is not None and event:
                events.append(event)
    except Exception as exc:
        return loop, calls, exc
    return loop, calls, None


def test_agent_turn_checks_settled_windows_while_writing_and_asks_nothing_twice(store):
    from test_agent_runs import UID
    loop, coverage_calls, error = streaming_turn(store)
    assert error is None
    review = store.get_turn(UID, loop.chat_id, loop.turn_id)["agent_review"]
    assert review["status"] == "succeeded"
    asked = [ids for ids, _ in coverage_calls]
    assert sorted(sum(asked, []), key=lambda key: int(key[1:])) == [f"s{n}" for n in range(1, 41)]
    early = next(prompt for ids, prompt in coverage_calls if ids[0] == "s1")
    assert "Fact number 17" in early and "Fact number 40" not in early  # written so far, not more
    data = review["checks"][0]["differences_data"]
    assert data["judges"]["coverage"]["prefetched"] == 32
    assert len(data["claims"]) == 40
    # Two early windows, the rest, and the differences pass (tests pin one pass).
    assert loop.comparison.judge_calls == 4


def test_bounded_runs_keep_their_judge_calls_for_the_finished_answer(store):
    loop, coverage_calls, error = streaming_turn(store, chat=False)
    assert error is None
    assert coverage_calls and all("Fact number 40" in prompt for _, prompt in coverage_calls)
    assert sorted(sum((ids for ids, _ in coverage_calls), []), key=lambda key: int(key[1:])) == [
        f"s{n}" for n in range(1, 41)]


def test_a_turn_that_fails_mid_answer_settles_its_early_windows_before_it_ends(store):
    from test_agent_runs import UID
    loop, coverage_calls, error = streaming_turn(store, fail_after=36, judge_delay=.3)
    # Two windows started while writing; the run end stopped what had not finished.
    windows = [window for _, launched in loop.comparison.prefetch.windows.values() for window in launched]
    assert len(windows) == 2 and all(future.done() for _, future in windows)
    assert coverage_calls and coverage_calls[0][0][0] == "s1"
    root = loop.store.receipt_ref(UID, loop.chat_id, loop.turn_id).get().to_dict()
    assert root["run_status"] != "running"
    assert "running" not in (root.get("step_states") or {}).values()
    assert store.get_turn(UID, loop.chat_id, loop.turn_id)["status"] != "pending"


def test_agent_turn_sends_provisional_marks_before_the_final_review_and_saves_none(store):
    from test_agent_runs import UID

    events = []
    loop, _, error = streaming_turn(store, events=events)
    assert error is None
    turn = store.get_turn(UID, loop.chat_id, loop.turn_id)
    review = turn["agent_review"]
    data = review["checks"][0]["differences_data"]
    previews = [i for i, event in enumerate(events) if event["type"] == "coverage_preview"]
    final = max(i for i, event in enumerate(events) if event["type"] == "review" and event["review"]["status"] == "succeeded")
    # Two windows ran while the answer was written, the third after it: each
    # reaches the page on its own, all before the final review.
    assert len(previews) == 3 and max(previews) < final
    sent = [events[i] for i in previews]
    assert all(event["answer_hash"] == review["answer_hash"] == review["versions"][-1]["hash"]
               and event["comparison_id"] == review["checks"][0]["comparison_id"] for event in sent)
    counts = [len(event["claims"]) for event in sent]
    assert counts == sorted(counts) and counts[-1] == 40
    assert [claim["anchor"] for claim in sent[-1]["claims"]] == [claim["anchor"] for claim in data["claims"]]
    # Coverage only: no score, no differences, and nothing of it is saved.
    assert all(set(event) == {"type", "answer_hash", "comparison_id", "claims", "models_compared", "checked",
                              "sentences"} for event in sent)
    for event in events:
        if event["type"] == "review" and event["review"]["status"] == "running":
            assert all(check["differences_data"] is None for check in event["review"]["checks"])
    assert "coverage_preview" not in json.dumps(turn, default=str)

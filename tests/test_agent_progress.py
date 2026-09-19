from app.services.agent_progress import ReasoningProgress, StreamProgress
from test_agent_runs import store
from test_agent_comparison import Script, make_loop


def event(text, format="text"):
    return {"kind": "reasoning", "format": format, "text": text, "append": True}


def test_short_highlights_update_at_boundaries_and_remain_bounded():
    progress = ReasoningProgress()
    assert progress.update(event("Checking the ")) is None
    first = progress.update(event("available evidence."))
    assert first["text"] == "Checking the available evidence."
    assert first["summary_source"] == "excerpt" and first["append"] is False
    assert progress.update(event(" Next")) is None
    for i in range(20):
        value = progress.update(event(f"\n\nChecking source {i} against the constraints. " + "detail " * 80))
        if value:
            assert len(value["text"]) <= 542
            assert len(value["text"].splitlines()) <= 3
    assert progress.updates <= 8 and len(progress.text) <= 8000


def test_provider_summary_replaces_excerpts_and_ignores_raw_reasoning():
    progress = ReasoningProgress()
    progress.update(event("A preliminary assumption needs checking."))
    value = progress.update(event("Checking the primary sources.", "summary"))
    assert value["summary_source"] == "provider_summary"
    assert "preliminary" not in value["text"]
    assert progress.update(event("Private additional detail. " * 100)) is None
    assert progress.update({"kind": "reasoning", "format": "encrypted", "text": "ciphertext"}) is None


def test_late_provider_summary_without_punctuation_replaces_excerpts_at_limit():
    progress = ReasoningProgress()
    for i in range(12):
        progress.update(event(f"\n\nChecking alternative {i}. " + "detail " * 80))
    assert progress.updates == 7
    value = progress.update(event("Checking sources and conflicting claims", "summary"))
    assert value["text"] == "Checking sources and conflicting claims"
    assert value["summary_source"] == "provider_summary" and progress.updates == 8


def test_live_and_saved_activity_never_contain_full_reasoning(store):
    script = Script()
    original = script.factory
    trace = "Checking the evidence before choosing. " + "Long internal detail. " * 500
    def factory():
        value = original()
        stream = value.stream
        def compact_stream(**kwargs):
            yield {"type": "activity", "version": 1, "step_id": value.step_id, "id": "r", **event(trace)}
            yield from stream(**kwargs)
        value.stream = compact_stream
        return value
    script.factory = factory
    loop = make_loop(store, script)
    events = list(loop.run())
    saved = store.get_turn(loop.uid, loop.chat_id, loop.turn_id)
    highlights = [e for e in saved["agent_activity"] if e["kind"] == "reasoning"]
    assert highlights and all(len(e["text"]) <= 542 and e["format"] == "summary" for e in highlights)
    assert all(len(e["text"]) <= 542 for e in events if e.get("kind") == "reasoning")
    sessions = store.delegation_view(loop.uid, loop.chat_id, loop.turn_id)["agents"]
    assert sessions and all(len(s["progress_text"]) <= 542 for s in sessions)
    assert all(s["progress_kind"] == "excerpt" for s in sessions)


def test_stream_progress_counts_received_unicode_and_throttles_without_guessing_tokens(monkeypatch):
    now = [10.0]
    monkeypatch.setattr("app.services.agent_progress.time.monotonic", lambda: now[0])
    progress = StreamProgress()
    assert progress.snapshot(None) == {"chars": 0, "usage": None, "streaming": True}
    progress.update({"type": "delta", "text": "Hi 🐳"})
    progress.update({"id": "r", **event("Think.")})
    progress.update({"id": "r", "kind": "reasoning", "format": "text", "text": "Think.", "append": False})
    progress.update({"kind": "reasoning", "format": "encrypted", "text": "private"})
    assert progress.snapshot(None) is None
    now[0] += .5
    assert progress.snapshot(None)["chars"] == 10
    assert progress.snapshot(None) is None
    now[0] += .5
    usage = {"input_tokens": 100, "output_tokens": 20, "reasoning_tokens": 5, "cached_input_tokens": 50}
    assert progress.snapshot(usage)["usage"] == {"input_tokens": 100, "output_tokens": 20, "complete": None}
    assert progress.snapshot(usage, streaming=False, force=True)["streaming"] is False
    assert progress.snapshot({"input_tokens": True, "output_tokens": 2}, force=True)["usage"] is None


def test_live_usage_replaces_step_snapshots_without_extra_receipts_or_transcript(store, monkeypatch):
    original_snapshot = StreamProgress.snapshot
    monkeypatch.setattr(StreamProgress, "snapshot", lambda self, usage, **kwargs:
        original_snapshot(self, usage, streaming=kwargs.get("streaming", True), force=True))
    script = Script()
    original = script.factory
    def factory():
        value = original()
        stream = value.stream
        def with_usage(**kwargs):
            if value.step_id.startswith("agent:"):
                value.usage = {"input_tokens": 50, "output_tokens": 5, "complete": True}
                yield {"type": "activity", "kind": "usage", "usage": value.usage}
            yield from stream(**kwargs)
        value.stream = with_usage
        return value
    script.factory = factory
    loop = make_loop(store, script)
    events = list(loop.run())
    progress = [e for e in events if e["type"] == "delegation_progress"]
    assert progress and all("text" not in e and "progress_text" not in e for e in progress)
    agents = store.delegation_view(loop.uid, loop.chat_id, loop.turn_id)["agents"]
    for agent in agents:
        updates = [e for e in progress if e["agent_id"] == agent["id"]]
        assert [e["seq"] for e in updates] == sorted({e["seq"] for e in updates})
        assert updates[-1]["streaming"] is False and updates[-1]["chars"] > 0
        assert updates[-1]["usage"]["input_tokens"] == agent["usage"]["input_tokens"] == 50
        assert updates[-1]["usage"]["output_tokens"] == agent["usage"]["output_tokens"] == 20
        assert "stream_chars" not in agent
    stored = [snap.to_dict() for snap in store._turn_ref(loop.uid, loop.chat_id, loop.turn_id).collection("agent_events").stream()]
    assert all(e["type"] == "delegation" for e in stored)
    assert loop.completion.usage["input_tokens"] + loop.completion.usage["output_tokens"] == 70 * len(script.calls)


def test_worker_rework_adds_settled_usage_once_and_coalesces_without_filling_event_queue(store):
    import queue
    from app.services.agent_delegation import Worker
    loop = make_loop(store, Script())
    worker = Worker("a" * 32, loop.model, [], session_seq=1, stream_chars=120,
                    usages=[{"input_tokens": 50, "output_tokens": 20}, None])
    progress = StreamProgress(worker.stream_chars)
    progress.update({"type": "delta", "text": "Next"})
    for output in (10, 15):
        loop._stream_progress(worker, progress, {"input_tokens": 100, "output_tokens": output}, force=True)
        event = list(loop._events())[0]
        assert event["chars"] == 124
        assert event["usage"] == {"input_tokens": 150, "output_tokens": 20 + output, "complete": False}
    loop.outgoing = queue.Queue(maxsize=1)
    loop.outgoing.put_nowait({"type": "delegation"})
    loop._stream_progress(worker, progress, None, force=True)
    loop._stream_progress(worker, progress, None, streaming=False, force=True)
    events = list(loop._events())
    assert len(events) == 2 and events[0] == {"type": "delegation"}
    assert events[1]["streaming"] is False and not loop.live_progress
    assert len(worker.usages) == 2 and loop.costs.calls == 0

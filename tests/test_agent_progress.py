from app.services.agent_progress import ReasoningProgress
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

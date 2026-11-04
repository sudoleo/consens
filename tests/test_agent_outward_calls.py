"""Every call of the agent runs at once: the reviewers follow it live and
halt the work before the next step where it needs the user (agent_audit.py).
What is the user's to allow goes to them: a step in their name through
ask_user (agent_ask.py). A memory change runs at once too; the user sees and can undo
every change.
"""
import json

import pytest

from app.services.agent_tools import ReadOnlyTool, ToolRegistry
from test_agent_audit import Audit, LookupArgs, after_live_rounds, audit_loop, decide_when_held, saved
from agent_reviewers import without_reviewers
from test_agent_runs import UID, store  # noqa: F401  (fixture)

HALT_REASON = "The fact comes from a page, not from the user."


def replies(script, family, live):
    """A reviewer's live replies: ``live(messages)``; it records what each round read."""
    script.read = getattr(script, "read", {})

    def reply(messages):
        script.read.setdefault(family, []).append(messages[-1]["content"])
        return live(messages)
    return reply


def calm(messages):
    return json.dumps({"marks": []})


def halt_on(quote):
    """A live reply that halts on the newest step it read, quoting ``quote``."""
    from test_agent_audit import entry_of

    def reply(messages):
        return json.dumps({"marks": [], "halt": {"entry": entry_of(messages, "step"), "kind": "injection",
                                                 "reason": HALT_REASON, "quote": quote}})
    return reply


class BrowserArgs(LookupArgs):
    action: str = ""
    ref: str = ""


def test_a_browser_click_runs_at_once_while_the_reviewers_follow_it_live(store):
    ran = []
    script = Audit(tool_steps=1, step_tools={0: "browser"}, step_args={0: {"action": "click", "ref": "e4"}},
                   live={})
    script.live.update(anthropic=replies(script, "anthropic", calm), openai=replies(script, "openai", calm))
    script.on_answer = after_live_rounds(script, "anthropic", "openai")
    loop = audit_loop(store, script)

    def run(args, *, cancellation):
        ran.append(args.action)
        return {"action": args.action, "page": "done"}
    loop.registry = ToolRegistry([*loop.registry.tools.values(),
                                  ReadOnlyTool("browser", "Use the browser.", BrowserArgs, run)],
                                 argument_limit=loop.registry.argument_limit)
    events = list(loop.run())
    assert ran == ["click"] and not [e for e in events if e.get("type") == "hold"]
    # The click and the page it brought back, in the reviewers' live rounds.
    assert any('"name": "browser"' in text for text in script.read["openai"])
    names = [entry["name"] for entry, _ in loop.work_log.entries_after(0) if entry["kind"] == "app"]
    assert "paused" not in names and "checked" not in names


def read_args(url):
    return {"url": url}


def test_a_page_of_its_own_choice_is_read_at_once(store, monkeypatch):
    """GPT-6.1 Terra's provider sends no search hits to the app, so
    read_source refused what it found: while reviewers follow the work it
    reads any public page."""
    from test_agent_web_fetch import PAGE, fake_fetch
    from app.services.agent_read_source import LABEL_CHOSEN, LABEL_SEARCH
    monkeypatch.delenv("AGENT_READ_SOURCES", raising=False)
    fetched = fake_fetch(monkeypatch)
    found, chosen = "https://www.toureiffel.paris/en", "https://de.wikipedia.org/wiki/Eiffelturm"
    script = Audit(tool_steps=2, step_tools={0: "read_source", 1: "read_source"},
                   step_args={0: read_args(found), 1: read_args(chosen)}, live={})
    script.live.update(anthropic=replies(script, "anthropic", calm), openai=replies(script, "openai", calm))
    loop = audit_loop(store, script)
    events = list(loop.run())
    results = [json.loads(m["content"]) for m in loop.messages if m.get("role") == "tool"]
    assert [r["status"] for r in results] == ["completed", "completed"]
    assert results[0]["cited_by"] == [LABEL_SEARCH] and results[1]["cited_by"] == [LABEL_CHOSEN]
    assert results[1]["untrusted_page_text"] == PAGE and len(fetched) == 2
    assert not [e for e in events if e.get("type") == "hold"]


# --- A request for a domain (gone with the open network) -------------------------------


def test_a_request_for_a_domain_gets_its_refusal_at_once(store):
    """A model that still calls request_domain gets "unknown tool", never a
    card."""
    script = Audit(tool_steps=1, step_tools={0: "request_domain"},
                   step_args={0: {"domain": "api.example.com", "reason": "Docs"}})
    loop = audit_loop(store, script)
    assert "request_domain" not in loop.registry.tools
    events = list(loop.run())
    assert not [e for e in events if e.get("type") == "hold"]
    [result] = [json.loads(m["content"]) for m in loop.messages if m.get("role") == "tool"]
    assert "unknown tool" in result["error"]
    assert saved(store, loop)["status"] == "completed"


# --- A memory change runs at once --------------------------------------------------

MEMORY_TEXT = "Is planning a trip to the Eiffel Tower."
MEMORY_CHANGE = {"op": "add", "text": MEMORY_TEXT}


def remembering(store, *, live, reviewers=True):
    """A turn whose first step searched (every scripted step does) and saves
    a memory with it, with a page in view too (as after read_source).
    ``reviewers=False``: they never start (agent_reviewers.InertAnswerAudit)."""
    from test_agent_memory import repo, set_profile
    set_profile(store.db, auto_memory=True)
    script = Audit(tool_steps=1, step_tools={0: "update_memory"}, step_args={0: {"changes": [MEMORY_CHANGE]}},
                   live=live)
    loop = audit_loop(store, script, memory=repo(store).snapshot(UID))
    loop.outside_in_view = True
    if not reviewers:
        without_reviewers(loop)
    return script, loop, lambda: [item["text"] for item in repo(store).get(UID)[0]]


@pytest.mark.parametrize("reviewers", [True, False])
def test_a_memory_change_with_outside_content_in_view_runs_at_once(store, reviewers):
    """The agent searches in nearly every first step, and a lock after it
    kept an opted-in account's memory empty."""
    script, loop, memories = remembering(store, live={}, reviewers=reviewers)
    if reviewers:
        script.live.update(anthropic=replies(script, "anthropic", calm), openai=replies(script, "openai", calm))
    events = list(loop.run())
    assert memories() == [MEMORY_TEXT]
    assert not [e for e in events if e.get("type") == "hold"]
    assert saved(store, loop)["status"] == "completed"


def test_a_halt_on_a_memory_change_stops_the_work_after_it_with_its_words(store):
    """The change ran at once; a reviewer that finds the page made the agent
    write it halts the work before its next step, and the card says the
    change in words, never its JSON."""
    script, loop, memories = remembering(store, live={})
    script.live.update(anthropic=replies(script, "anthropic", calm),
                       openai=replies(script, "openai", halt_on(MEMORY_TEXT)))
    script.on_answer = after_live_rounds(script, "openai", until=lambda: loop.hold is not None)
    waiter = decide_when_held(loop, store, "continue")
    events = list(loop.run())
    waiter.join(5)
    [hold] = [e["hold"] for e in events if e.get("type") == "hold" and e.get("hold")]
    assert hold["kind"] == "injection" and hold["reason"] == HALT_REASON and hold["reviewer"] == "GPT-5.4 mini"
    assert [(c["tool"], c["text"]) for c in hold["step_calls"]] == [("update_memory", MEMORY_TEXT)]
    assert "{" not in hold["step"] and memories() == [MEMORY_TEXT]
    assert HALT_REASON not in json.dumps(loop.messages)


def test_a_memory_needs_no_quote(store):
    """The model decides what is worth remembering, also a preference the
    user never put into words; the user sees and can undo every change."""
    from test_agent_memory import repo, set_profile
    set_profile(store.db, auto_memory=True)
    preference = {"op": "add", "text": "Prefers short answers."}
    script = Audit(search=False, tool_steps=1, step_tools={0: "update_memory"},
                   step_args={0: {"changes": [preference]}}, live={})
    loop = audit_loop(store, script, memory=repo(store).snapshot(UID))
    list(loop.run())
    assert [item["text"] for item in repo(store).get(UID)[0]] == ["Prefers short answers."]
    tool = next(t for t in loop.registry.tools.values() if t.name == "update_memory")
    assert "evidence" not in json.dumps(tool.schema()) and "can undo it" in tool.description

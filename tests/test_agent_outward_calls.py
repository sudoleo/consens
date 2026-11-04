"""Every call of the agent runs at once: the reviewers follow it live and
halt the work before the next step where it needs the user (agent_audit.py).
What is the user's to allow goes to them: a request for a domain always
(DelegationLoop._domain_wait), a step in their name through ask_user
(agent_ask.py). A memory change runs at once too; the user sees and can undo
every change.
"""
import json
import threading
import time

import pytest

from app.services import agent_delegation, agent_domains
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


# --- A domain for the workbench (agent_domains.py) ------------------------------------

DOMAIN_REASON = "The script calls the weather API."


def asking(store, *, live, domain="api.weather.example"):
    """An audit turn whose first step asks for ``domain``; the fake tool
    records whether it ran and what the loop allowed then."""
    ran = []
    script = Audit(tool_steps=1, step_tools={0: "request_domain"},
                   step_args={0: {"domain": domain, "reason": DOMAIN_REASON}}, live=live)
    loop = audit_loop(store, script)

    def run(args, *, cancellation):
        ran.append((args.domain, set(loop.allowed_domains)))
        return {"domain": args.domain, "status": "allowed"}
    loop.registry = ToolRegistry([*loop.registry.tools.values(),
                                  ReadOnlyTool("request_domain", "Ask for a domain.", agent_domains.RequestDomainArgs,
                                               run)],
                                 argument_limit=loop.registry.argument_limit)
    return script, loop, ran


def test_a_domain_goes_to_the_user_and_runs_only_on_their_yes(store):
    """Never allowed by itself, also not by the reviewers: the user decides
    every domain, and the call waits for nothing else."""
    script, loop, ran = asking(store, live={})
    script.live.update(anthropic=replies(script, "anthropic", calm), openai=replies(script, "openai", calm))
    waiter = decide_when_held(loop, store, "continue")
    events = list(loop.run())
    waiter.join(5)
    holds = [e["hold"] for e in events if e.get("type") == "hold" and e.get("hold")]
    assert len(holds) == 1
    hold = holds[0]
    assert hold["domain"] == "api.weather.example" and hold["domain_reason"] == DOMAIN_REASON
    assert hold["kind"] == "domain" and hold["reviewer"] == "" and "review" not in hold and "gate" not in hold
    step = next(entry["seq"] for entry, _ in loop.work_log.entries_after(0) if entry["kind"] == "step")
    assert hold["entry"] == step
    # It ran only after the user's yes, with the domain allowed then.
    assert ran == [("api.weather.example", {"api.weather.example"})]
    activity = [e for e in events if e.get("type") == "activity" and e.get("kind") == "hold"]
    assert activity[0]["domain"] == "api.weather.example" and activity[0]["halt"] == "domain"
    assert activity[-1]["state"] == "continue"
    said = [content for entry, content in loop.work_log.entries_after(0) if entry["kind"] == "app"]
    assert f"The agent asks to reach api.weather.example (entry {step}): the user decides." in said
    assert "The user allowed api.weather.example for this chat." in said


def test_without_reviewers_the_domain_card_says_only_the_user_decides(store):
    script, loop, ran = asking(store, live={})
    without_reviewers(loop)
    waiter = decide_when_held(loop, store, "continue")
    events = list(loop.run())
    waiter.join(5)
    [hold] = [e["hold"] for e in events if e.get("type") == "hold" and e.get("hold")]
    assert hold["review"] == "off" and ran


def test_a_domain_the_user_does_not_allow_never_runs(store):
    script, loop, ran = asking(store, live={})
    script.live.update(anthropic=replies(script, "anthropic", calm), openai=replies(script, "openai", calm))
    waiter = decide_when_held(loop, store, "deny")
    list(loop.run())
    waiter.join(5)
    assert ran == [] and loop.allowed_domains == set()
    results = [json.loads(m["content"]) for m in loop.messages if m.get("role") == "tool"]
    assert results == [{"error": agent_domains.DOMAIN_DENIED.format(domain="api.weather.example")}]
    names = [entry["name"] for entry, _ in loop.work_log.entries_after(0) if entry["kind"] == "app"]
    assert "paused" in names and "decision" in names
    assert saved(store, loop)["status"] == "completed"


def test_a_domain_card_nobody_answers_stays_closed_and_the_work_goes_on(store, monkeypatch):
    """After 30 minutes without a decision the domain is not allowed, as
    with "Don't allow", and the work goes on."""
    from test_agent_audit import open_hold
    script, loop, ran = asking(store, live={})
    script.live.update(anthropic=replies(script, "anthropic", calm), openai=replies(script, "openai", calm))
    clock = {"skew": 0.0}
    loop.clock = lambda: time.monotonic() + clock["skew"]

    def later():
        open_hold(loop)
        clock.update(skew=agent_delegation.HOLD_TIMEOUT_SECONDS + 1)
    thread = threading.Thread(target=later, daemon=True)
    thread.start()
    events = list(loop.run())
    thread.join(5)
    assert [e.get("decision") for e in events if e.get("type") == "hold" and not e.get("hold")] == ["timeout"]
    assert ran == [] and loop.allowed_domains == set() and not loop.cancellation.cancelled
    results = [json.loads(m["content"]) for m in loop.messages if m.get("role") == "tool"]
    assert results == [{"error": agent_domains.DOMAIN_DENIED.format(domain="api.weather.example")}]
    said = [content for entry, content in loop.work_log.entries_after(0) if entry["kind"] == "app"]
    assert "No decision in 30 minutes: not allowed, the work goes on." in said
    assert saved(store, loop)["status"] == "completed"


def test_a_reviewers_halt_during_a_domain_card_joins_it(store):
    """A live halt that comes while the user reads the card stands on it."""
    from test_agent_audit import join_when_held
    script, loop, ran = asking(store, live={})
    script.live.update(anthropic=replies(script, "anthropic", calm), openai=replies(script, "openai", calm))
    thread, seen = join_when_held(loop, store, "deny", provider="openai", entry=1)
    list(loop.run())
    thread.join(5)
    [card] = seen
    assert card["kind"] == "domain" and card["review"] == "halt" and card["reviewer"] == "GPT-5.4 mini"
    assert card["reason"] == "Deletes the user's files." and card["revision"] == 1
    assert ran == [] and loop.allowed_domains == set()


def test_a_domain_the_chat_already_has_needs_no_card(store):
    script, loop, ran = asking(store, live={})
    script.live.update(anthropic=replies(script, "anthropic", calm), openai=replies(script, "openai", calm))
    store._chat_ref(UID, loop.chat_id).update({agent_domains.CHAT_FIELD: [{"domain": "api.weather.example"}]})
    events = list(loop.run())
    assert not [e for e in events if e.get("type") == "hold"]
    assert ran == [("api.weather.example", {"api.weather.example"})]


def test_a_request_the_tool_refuses_needs_no_card(store):
    script, loop, ran = asking(store, live={}, domain="api.sprites.dev")
    script.live.update(anthropic=replies(script, "anthropic", calm), openai=replies(script, "openai", calm))
    events = list(loop.run())
    assert not [e for e in events if e.get("type") == "hold"]


def test_a_request_for_a_domain_without_the_tool_gets_its_refusal_at_once(store):
    """An account without request_domain (Free) whose model calls it anyway
    gets "unknown tool", never a card whose yes ends there."""
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

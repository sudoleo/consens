"""Audit instead of comparison (AgentPreferences.audit, admin accounts only):
the agent answers itself with its own search and gets no comparison tools;
the comparison models then review the finished answer, mark passages with a
note, and the app places their quotes on the answer's sentences. Without the
setting everything runs as before (test_agent_comparison, test_agent_answer_mode).
"""
import json
import threading
import time

import pytest

from app.services import agent_audit, agent_memory, prompt_defaults
from app.services.agent_audit import (AGENT_SEARCH_ROUNDS, REVIEW_SEARCH_ROUNDS, locate_quote, parse_review,
                                      place_marks, review_input)
from app.services.agent_comparison import AUDIT_OFF_PROMPT, AgentPreferences, comparison_selection, preference_prompt
from app.services.agent_delegation import DelegationLoop
from app.services.agent_delegation_config import defaults
from app.services.agent_policy import AgentPolicy
from app.services.llm.agent_client import AgentCompletion, measured_usage, resolve_agent_model
from app.services.llm.provider_runtime import ProviderCancellation, ProviderCancelled, current_provider_cancellation
from test_agent_runs import AUTH, UID, api, pending, store  # noqa: F401  (fixtures)


@pytest.fixture(autouse=True)
def _admin_allowance(monkeypatch):
    """Audit mode is for admins, whose daily account (5M tokens) holds the
    agent's five search rounds; the suites' 250k (conftest) would not."""
    from app.services import agent_budget_config
    monkeypatch.setitem(agent_budget_config.DEFAULT_TIER_LIMITS, "pro", 5_000_000)


ANSWER = ("The Eiffel Tower is 330 metres tall. It was built in 1889 for the World's Fair. "
          "**Gustave Eiffel** did not design it alone: the engineers Maurice Koechlin and Emile Nouguier drew "
          "the first plans. About seven million people visit it every year, according to the "
          "[official site](https://www.toureiffel.paris/en). Tickets to the top cost 14 euros.")
RATES = "https://www.toureiffel.paris/en/rates-opening-times"
REVIEWS = {
    "anthropic": json.dumps({"marks": [
        {"quote": "Tickets to the top cost 14 euros", "kind": "wrong", "note": "The top costs 36.10 euros.",
         "source": RATES},
        {"quote": "according to the official site", "kind": "doubtful", "note": "The site counts about 6 million."},
    ]}),
    # In a code fence, with a synonym, a source that is no URL and a quote the answer does not hold.
    "openai": "```json\n" + json.dumps({"marks": [
        {"quote": "tickets to the TOP cost 14 euros.", "kind": "incorrect", "note": "Too low.", "source": "the website"},
        {"quote": "Gustave Eiffel did not design it alone", "kind": "missing", "note": "Stephen Sauvestre is missing."},
        {"quote": "The Eiffel Tower is 400 metres tall", "kind": "wrong", "note": "Not in the answer.",
         "source": "https://example.org/height"},
    ]}) + "\n```",
}


class Audit:
    """A scripted audit-mode turn: every agent step (completion:N) answers at
    once, after its own search; every other call is a reviewer, replying with
    ``reviews[family]`` (a text, an exception or "wait": until it is stopped)."""

    def __init__(self, reviews=None, *, answer=ANSWER, search=True):
        self.reviews = dict(REVIEWS if reviews is None else reviews)
        self.answer = answer
        self.search = search
        self.calls, self.offered, self.searches, self.prompts = [], [], {}, {}
        self.loop = None

    def factory(self):
        script = self

        class Completion(AgentCompletion):
            def stream(self, *, model, messages, **kwargs):
                script.calls.append((self.step_id, model.model))
                self.usage = measured_usage({"prompt_tokens": 50, "completion_tokens": 20, "cost": .0001}, model)
                names = [tool["function"]["name"] for tool in kwargs.get("tools") or [] if tool.get("type") == "function"]
                if self.step_id.startswith("completion:"):
                    script.offered.append(names)
                    script.searches[self.step_id] = kwargs.get("native_searches")
                    # The agent's own search found a page, then it writes.
                    if script.search:
                        self.sources = [{"url": "https://www.toureiffel.paris/en", "title": "Official site"}]
                        self._results_at = 0
                    for start in range(0, len(script.answer), 60):
                        chunk = script.answer[start:start + 60]
                        self.text += chunk
                        yield {"type": "delta", "text": chunk}
                    self.finish_reason = "stop"
                    return
                family = model.model.split("/")[0]
                script.prompts[family] = messages
                script.searches[family] = kwargs.get("native_searches")
                reply = script.reviews.get(family, json.dumps({"marks": []}))
                if reply == "wait":
                    stop = current_provider_cancellation()
                    while not stop.cancelled:
                        time.sleep(.01)
                    raise ProviderCancelled("stopped")
                if isinstance(reply, BaseException):
                    raise reply
                self.text, self.finish_reason = reply, "stop"
                yield {"type": "delta", "text": self.text}
        return Completion()


def audit_loop(store, script, *, judges="on", audit="on", messages=None, memory=None):
    chat, turn = pending(store)
    config = {**defaults(), "enabled": False, "max_searches": 0}
    loop = DelegationLoop(store=store, uid=UID, chat_id=chat, turn_id=turn["id"],
        model=resolve_agent_model("claude-haiku-4-5"),
        messages=messages or [{"role": "system", "content": "Answer."},
                              {"role": "user", "content": "Tell me about the Eiffel Tower."}],
        api_key="test", cancellation=ProviderCancellation(), policy=AgentPolicy.for_chat(config),
        delegation_config=config, completion_factory=script.factory,
        comparison_models=comparison_selection({"anthropic": "claude-haiku-4-5", "openai": "gpt-5.4-mini"}),
        agent_preferences=AgentPreferences(audit=audit, judges=judges), memory=memory)
    script.loop = loop
    return loop


def saved(store, loop):
    return store.get_turn(UID, loop.chat_id, loop.turn_id)


def by_anchor(review):
    return {claim["anchor"]: claim for claim in review["audit"]["claims"]}


# --- The turn -------------------------------------------------------------------

def test_the_agent_answers_itself_and_the_comparison_models_review_its_answer(store):
    script = Audit()
    loop = audit_loop(store, script)
    events = list(loop.run())
    turn = saved(store, loop)
    review = turn["agent_review"]
    assert turn["status"] == "completed" and turn["consensus"] == ANSWER
    # No comparison: the agent is offered neither tool, and searches in every step.
    assert script.offered and all("compare_models" not in names and "check_text" not in names
                                  for names in script.offered)
    assert {step: rounds for step, rounds in script.searches.items() if step.startswith("completion:")} == {
        "completion:0": AGENT_SEARCH_ROUNDS}
    assert [step for step, _ in script.calls if step.startswith("completion:")] == ["completion:0"]
    # The answer streamed as it was written, then the app announced its check.
    assert "".join(e["text"] for e in events if e.get("type") == "delta") == ANSWER
    first_review = next(i for i, e in enumerate(events) if e.get("type") == "review")
    assert any(e.get("type") == "answer_check" for e in events[:first_review])
    # Both comparison models reviewed it with their own search; no judge ran.
    assert script.searches["anthropic"] == script.searches["openai"] == REVIEW_SEARCH_ROUNDS
    assert loop.comparison.judge_calls == 0
    assert not any(e.get("kind") == "tool" and e.get("name") == "judge_answer" for e in events)
    assert [e["status"] for e in events if e.get("kind") == "tool" and e.get("name") == "audit_answer"] == [
        "running", "succeeded"]
    # The review: bound to the answer, every reviewer done, marks with notes.
    assert review["mode"] == "audit" and review["status"] == "succeeded" and review["comparisons"] == []
    assert review["versions"][-1]["text"] == ANSWER and review["versions"][-1]["hash"] == review["answer_hash"]
    assert [(r["provider"], r["status"], r["marks"]) for r in review["audit"]["reviewers"]] == [
        ("anthropic", "completed", 2), ("openai", "completed", 3)]
    claims = by_anchor(review)
    tickets = claims["Tickets to the top cost 14 euros."]
    # Two reviewers on one sentence: one mark, both notes, the most severe kind.
    assert tickets["kind"] == "wrong" and tickets["agree"] == [] and tickets["audit"] is True
    assert [(d["model"], d["kind"], d["note"], d.get("source"), d["mark"]) for d in tickets["dissent"]] == [
        ("Anthropic", "wrong", "The top costs 36.10 euros.", RATES, 1), ("OpenAI", "doubtful", "Too low.", None, 3)]
    assert [d["target"] for d in tickets["dissent"]] == ["Tickets to the top cost 14 euros."] * 2
    # A link is quoted by its words; Markdown emphasis does not count.
    visitors = next(c for anchor, c in claims.items() if anchor.startswith("About seven million"))
    # The quoted words as the page shows them: a link by its label.
    assert visitors["kind"] == "doubtful" and visitors["dissent"][0]["target"] == "according to the official site."
    eiffel = next(c for anchor, c in claims.items() if anchor.startswith("**Gustave Eiffel**"))
    assert eiffel["kind"] == "incomplete" and eiffel["dissent"][0]["note"] == "Stephen Sauvestre is missing."
    # Unmarked sentences carry nothing: no objection, not "confirmed".
    assert "The Eiffel Tower is 330 metres tall." not in claims
    assert review["audit"]["unplaced"] == [{"model": "OpenAI", "kind": "wrong", "note": "Not in the answer.",
                                            "source": "https://example.org/height", "mark": 5,
                                            "quote": "The Eiffel Tower is 400 metres tall"}]
    # The agent's own search put pages in view: memory is locked for the turn.
    assert loop.memory_locked is True
    # A reviewer's session saves what it reads, not a copy of it.
    sessions = [a for a in store.delegation_view(UID, loop.chat_id, loop.turn_id)["agents"] if a.get("kind") == "audit"]
    assert len(sessions) == 2
    for session in sessions:
        agent = store.delegation_view(UID, loop.chat_id, loop.turn_id, agent_id=session["id"])["agent"]
        assert agent["assignment"]["context"] == agent_audit.REVIEW_ASSIGNMENT


def test_the_reviewers_read_the_conversation_the_latest_message_and_the_whole_answer(store):
    script = Audit()
    loop = audit_loop(store, script, messages=[
        {"role": "system", "content": "Answer."}, {"role": "user", "content": "Paris trip?"},
        {"role": "assistant", "content": "Yes, go in spring."}, {"role": "user", "content": "And the tower?"}])
    list(loop.run())
    system, user = script.prompts["openai"]
    assert system["content"].startswith("You are an independent reviewer") and "Current date:" in system["content"]
    task = json.loads(user["content"])
    assert task == {"conversation": [{"role": "user", "content": "Paris trip?"},
                                     {"role": "assistant", "content": "Yes, go in spring."}],
                    "latest_message": "And the tower?", "answer": ANSWER}


def test_a_failed_or_unreadable_review_costs_only_its_marks(store):
    script = Audit({"anthropic": RuntimeError("provider down"), "openai": "Looks fine to me."})
    loop = audit_loop(store, script)
    list(loop.run())
    turn = saved(store, loop)
    review = turn["agent_review"]
    assert turn["status"] == "completed" and turn["consensus"] == ANSWER
    assert review["status"] == "failed" and review["audit"]["claims"] == []
    assert [(r["status"], r["failure"]["code"]) for r in review["audit"]["reviewers"]] == [
        ("failed", "provider_error"), ("failed", "review_unreadable")]
    assert {"code": "reviewers_unavailable", "count": 2} in review["audit"]["issues"]


def test_one_reviewer_left_keeps_its_marks_as_a_partial_review(store):
    script = Audit({"anthropic": RuntimeError("provider down"), "openai": REVIEWS["openai"]})
    loop = audit_loop(store, script)
    list(loop.run())
    review = saved(store, loop)["agent_review"]
    assert review["status"] == "partial"
    assert {d["model"] for c in review["audit"]["claims"] for d in c["dissent"]} == {"OpenAI"}


def test_an_empty_review_means_no_objection(store):
    script = Audit({"anthropic": '{"marks": []}', "openai": "[]"})
    loop = audit_loop(store, script)
    list(loop.run())
    review = saved(store, loop)["agent_review"]
    assert review["status"] == "succeeded" and review["audit"]["claims"] == [] and review["audit"]["unplaced"] == []


def test_reviewers_still_working_at_the_deadline_lose_their_marks_not_the_answer(store, monkeypatch):
    monkeypatch.setattr(agent_audit, "REVIEW_TIME_MARGIN", 0)
    monkeypatch.setattr(agent_audit, "REVIEW_MIN_SECONDS", 0)
    script = Audit({"anthropic": "wait", "openai": REVIEWS["openai"]})
    loop = audit_loop(store, script)
    # Plenty of time while the agent writes; .3 s once the answer is fixed.
    monkeypatch.setattr(loop, "_hard_stop_left", lambda: .3 if loop.comparison.text else 1000)
    list(loop.run())
    turn = saved(store, loop)
    review = turn["agent_review"]
    assert turn["status"] == "completed" and turn["consensus"] == ANSWER
    assert review["status"] == "partial"
    assert [(r["status"], (r.get("failure") or {}).get("code")) for r in review["audit"]["reviewers"]] == [
        ("failed", "no_time"), ("completed", None)]
    assert {"code": "no_time"} in review["audit"]["issues"]


def test_without_time_left_no_reviewer_starts(store, monkeypatch):
    script = Audit()
    loop = audit_loop(store, script)
    monkeypatch.setattr(loop, "_hard_stop_left", lambda: 5 if loop.comparison.text else 1000)
    list(loop.run())
    turn = saved(store, loop)
    assert turn["status"] == "completed" and turn["agent_review"]["status"] == "failed"
    assert turn["agent_review"]["audit"]["issues"] == [{"code": "no_time"}]
    assert "anthropic" not in script.prompts and "openai" not in script.prompts


def test_a_stop_during_the_review_stops_the_reviewers_not_the_answer(store):
    script = Audit({"anthropic": "wait", "openai": "wait"})
    loop = audit_loop(store, script)

    def stop_when_reviewing():
        while len(script.prompts) < 2:
            time.sleep(.01)
        loop.cancellation.cancel()
    threading.Thread(target=stop_when_reviewing, daemon=True).start()
    list(loop.run())
    turn = saved(store, loop)
    # The answer was complete and fixed: the turn ends with it.
    assert turn["status"] == "completed" and turn["consensus"] == ANSWER
    assert turn["agent_review"]["status"] == "cancelled"
    assert {r["status"] for r in turn["agent_review"]["audit"]["reviewers"]} == {"stopped"}


def test_a_stop_before_the_review_starts_still_completes_the_answer(store, monkeypatch):
    script = Audit()
    loop = audit_loop(store, script)
    capture = loop.comparison.capture

    def stop_once_fixed(text):
        capture(text)
        loop.cancellation.cancel()
    monkeypatch.setattr(loop.comparison, "capture", stop_once_fixed)
    list(loop.run())
    turn = saved(store, loop)
    assert turn["status"] == "completed" and turn["consensus"] == ANSWER
    assert turn["agent_review"]["status"] == "cancelled" and not script.prompts


def test_a_failed_save_of_the_marks_is_saved_again_at_the_end(store, monkeypatch):
    script = Audit()
    loop = audit_loop(store, script)
    save, failed = store.save_review, []

    def flaky(uid, chat_id, turn_id, token, review, text):
        if (review.get("audit") or {}).get("claims") and not failed:
            failed.append(review["status"])
            raise RuntimeError("database briefly unavailable")
        return save(uid, chat_id, turn_id, token, review, text)
    monkeypatch.setattr(store, "save_review", flaky)
    list(loop.run())
    review = saved(store, loop)["agent_review"]
    assert failed == ["succeeded"]
    assert review["status"] == "succeeded" and len(review["audit"]["claims"]) == 3


def test_a_completed_answer_never_keeps_a_review_that_says_reviewing(store, monkeypatch):
    script = Audit()
    loop = audit_loop(store, script)
    save = store.save_review

    def down_after_start(uid, chat_id, turn_id, token, review, text):
        if any(r["status"] != "waiting" for r in (review.get("audit") or {}).get("reviewers", [])):
            raise RuntimeError("database unavailable")
        return save(uid, chat_id, turn_id, token, review, text)
    monkeypatch.setattr(store, "save_review", down_after_start)
    list(loop.run())
    turn = saved(store, loop)
    assert turn["status"] == "completed" and turn["consensus"] == ANSWER
    assert turn["agent_review"]["status"] == "failed"


def test_memory_stays_open_while_the_agent_has_not_searched(store):
    script = Audit(search=False)
    loop = audit_loop(store, script)
    list(loop.run())
    assert loop.memory_locked is False


def test_with_the_answer_check_off_the_agent_answers_alone(store):
    script = Audit()
    loop = audit_loop(store, script, judges="off")
    list(loop.run())
    turn = saved(store, loop)
    assert turn["status"] == "completed" and turn["consensus"] == ANSWER
    assert [step for step, _ in script.calls] == ["completion:0"]
    assert "compare_models" not in loop.registry.tools and loop.comparison.auditor is None
    assert not (turn.get("agent_review") or {}).get("audit")
    assert AUDIT_OFF_PROMPT in loop.messages[0]["content"]


def test_without_the_setting_the_agent_keeps_its_comparison_tools(store):
    loop = audit_loop(store, Audit(), audit="off")
    assert {"compare_models", "check_text"} <= set(loop.registry.tools)
    assert loop.comparison.auditor is None and not loop.comparison.audit_mode
    assert prompt_defaults.AGENT_ANSWER_SECTION in loop.messages[0]["content"]
    assert prompt_defaults.AGENT_AUDIT_ANSWER_SECTION not in loop.messages[0]["content"]


# --- Prompts ----------------------------------------------------------------------

def test_the_audit_prompt_has_its_writing_reading_and_memory_rules(store, monkeypatch):
    from test_agent_memory import repo, set_profile
    monkeypatch.delenv("AGENT_READ_SOURCES", raising=False)
    set_profile(store.db, auto_memory=True)
    loop = audit_loop(store, Audit(), memory=repo(store).snapshot(UID), messages=[
        {"role": "system", "content": prompt_defaults.AGENT_AUDIT_SYSTEM_PROMPT}, {"role": "user", "content": "Hi"}])
    system = loop.messages[0]["content"]
    assert system.startswith(prompt_defaults.AGENT_AUDIT_SYSTEM_PROMPT)
    assert system.count("WRITING THE ANSWER") == 1 and "READING SOURCES" in system
    assert prompt_defaults.AGENT_AUDIT_READ_SOURCE_PROMPT.split("\n\n")[1][:60] in system
    # No comparison limit, no comparison memory field, no free-mode text.
    assert "comparisons per message" not in system and "compare_models and check_text carry" not in system
    assert "call update_memory first" in system and "FREE" not in system
    names = set(loop.registry.tools)
    assert {"read_source", "update_memory"} <= names and not {"compare_models", "check_text"} & names
    assert "Call it first" in loop.registry.tools["update_memory"].description
    assert "comparison answer" not in loop.registry.tools["read_source"].description


def test_every_memory_rule_without_comparisons_replaces_a_sentence_that_exists():
    texts = (agent_memory.MEMORY_USE_PROMPT, agent_memory.MEMORY_WRITE_PROMPT, agent_memory.MEMORY_READ_ONLY_PROMPT,
             agent_memory.MEMORY_PAUSED_PROMPT, agent_memory.MEMORY_UNAVAILABLE_PROMPT)
    # A changed memory prompt fails here, not silently in audit mode.
    for old, _ in agent_memory.NO_COMPARISON_REPLACEMENTS:
        assert any(old in text for text in texts), old
    for text in texts:
        adapted = agent_memory.without_comparisons(text)
        # Only the user's own comparisons (an example) may remain.
        assert "compar" not in adapted.replace("a comparison they asked for", "").lower(), adapted[:80]


def test_the_comparison_settings_say_nothing_in_audit_mode():
    assert preference_prompt(AgentPreferences(audit="on", depth="quick", autonomy="free")) == ""
    assert preference_prompt(AgentPreferences(audit="on", judges="off")) == AUDIT_OFF_PROMPT


# --- Reading reviews and placing quotes -------------------------------------------

def test_a_review_is_read_tolerantly_and_a_wrong_needs_a_source():
    text = "Here is my review:\n" + json.dumps({"marks": [
        {"quote": "A", "kind": "wrong", "note": "No source."},
        {"quote": "B", "kind": "FALSE", "note": "With one.", "source": ["ftp://x", "https://example.org/b"]},
        {"quote": "C", "kind": "unclear", "note": "Unknown kind."},
        {"quote": "", "kind": "doubtful", "note": "No quote."},
        {"quote": "D", "kind": "doubtful", "note": "Credentials.", "source": "https://user:pw@example.org"},
        {"quote": "D", "kind": "doubtful", "note": "Credentials.", "source": "https://user:pw@example.org"},
    ]}) + "\nThanks."
    assert parse_review(text) == [
        {"quote": "A", "kind": "doubtful", "note": "No source."},
        {"quote": "B", "kind": "wrong", "note": "With one.", "source": "https://example.org/b"},
        {"quote": "D", "kind": "doubtful", "note": "Credentials."}]
    for unreadable in ("No problems found.", '{"verdict": "fine"}', ""):
        with pytest.raises(agent_audit.ReviewUnreadable):
            parse_review(unreadable)
    marks = [{"quote": f"q{i}", "kind": "doubtful", "note": "n"} for i in range(50)]
    assert len(parse_review(json.dumps({"marks": marks}))) == agent_audit.MAX_MARKS


@pytest.mark.parametrize("quote,expected", [
    ("tickets to the top cost 14 euros", "Tickets to the top cost 14 euros."),
    ("“Gustave Eiffel did not design it alone”", "**Gustave Eiffel** did not design it alone"),
    ("according to the official site", "according to the [official site](https://www.toureiffel.paris/en)."),
    ("It was built ... World's Fair", "It was built in 1889 for the World's Fair."),
    ("Eiffel Tow", "Eiffel Tower"),
])
def test_a_quote_is_found_like_a_checked_passage(quote, expected):
    start, stop = locate_quote(ANSWER, quote)
    assert ANSWER[start:stop] == expected


def test_quotes_the_answer_does_not_hold_or_holds_twice_stay_unplaced():
    assert locate_quote(ANSWER, "The tower is made of glass") is None
    assert locate_quote(ANSWER, "is") is None
    # "Eiffel" stands twice: which one the reviewer meant is unknown.
    assert locate_quote(ANSWER, "Eiffel") is None
    claims, unplaced = place_marks("# Heading words here\n\nOne plain sentence stands here.", [
        ("OpenAI", [{"quote": "Heading words here", "kind": "doubtful", "note": "A heading."}])])
    assert claims == [] and unplaced[0]["quote"] == "Heading words here"


def test_a_mark_over_up_to_three_sentences_is_one_mark_and_longer_quotes_stay_unplaced():
    text = " ".join(f"Sentence number {n} says something." for n in range(1, 7))
    two = "Sentence number 2 says something. Sentence number 3"
    claims, unplaced = place_marks(text, [("OpenAI", [
        {"quote": two, "kind": "doubtful", "note": "Two sentences."},
        {"quote": text, "kind": "doubtful", "note": "All of it."},
        {"quote": "Sentence number 1 ... number 5 says something.", "kind": "wrong", "note": "Five."}])])
    assert [(c["anchor"], [d["mark"] for d in c["dissent"]]) for c in claims] == [
        ("Sentence number 2 says something.", [1]), ("Sentence number 3 says something.", [1])]
    assert [(item["mark"], item["note"]) for item in unplaced] == [(2, "All of it."), (3, "Five.")]


@pytest.mark.parametrize("value,expected", [
    ("https://en.wikipedia.org/wiki/Mercury_(planet)", "https://en.wikipedia.org/wiki/Mercury_(planet)"),
    ("(https://en.wikipedia.org/wiki/Mercury_(planet))", "https://en.wikipedia.org/wiki/Mercury_(planet)"),
    ("[Wikipedia](https://en.wikipedia.org/wiki/Mercury_(planet))", "https://en.wikipedia.org/wiki/Mercury_(planet)"),
    ("<https://example.org/a>", "https://example.org/a"),
    ("\"https://example.org/a\"", "https://example.org/a"),
    ("https://example.org/a)", "https://example.org/a"),
    ("see https://example.org/a", None),
    ("ftp://example.org/a", None),
])
def test_a_source_is_read_with_its_own_parentheses(value, expected):
    assert agent_audit.source_url(value) == expected


def test_over_the_storage_budget_marks_keep_their_sentences_with_shorter_notes():
    audit = {"claims": [{"anchor": "A.", "dissent": [{"model": "OpenAI", "kind": "doubtful", "note": "n" * 600,
                                                      "target": "A", "mark": 1}]}],
             "unplaced": [{"model": "OpenAI", "kind": "doubtful", "note": "x", "quote": "q" * 400, "mark": 2}]}
    agent_audit.trim_marks(audit)
    [item] = audit["claims"][0]["dissent"]
    assert "target" not in item and len(item["note"]) == agent_audit.TRIMMED_NOTE_CHARS and item["mark"] == 1
    assert len(audit["unplaced"][0]["quote"]) == 200


def test_the_review_input_keeps_the_newest_history_within_its_budget(monkeypatch):
    monkeypatch.setattr(agent_audit, "REVIEW_HISTORY_CHARS", 10)
    task = json.loads(review_input([{"role": "user", "content": "x" * 20}, {"role": "assistant", "content": "short"},
                                    {"role": "user", "content": "Latest?"}], "The answer."))
    assert task == {"conversation": [{"role": "assistant", "content": "short"}], "earlier_messages_omitted": True,
                    "latest_message": "Latest?", "answer": "The answer."}


# --- The route ---------------------------------------------------------------------

@pytest.mark.parametrize("admin", [True, False])
def test_only_an_admins_message_runs_in_audit_mode(api, monkeypatch, admin):
    from app.api.routers import agent
    client, store, calls = api
    monkeypatch.setattr(agent, "is_user_admin", lambda uid: admin)
    chat_id = store.create_chat(UID, execution_mode="agent")["id"]
    payload = {"chat_id": chat_id, "question": "Hi", "client_request_id": "r1", "bookmark_id": "bm1",
               "agent_preferences": {"audit": "on"}}
    response = client.post("/agent", json=payload, headers=AUTH)
    assert response.status_code == 200, response.text
    turn = next(t for t in store.list_turns(UID, chat_id)["turns"] if t["question"] == "Hi")
    settings = store.get_turn(UID, chat_id, turn["id"])["agent_settings"]
    assert settings["agent_preferences"]["audit"] == ("on" if admin else "off")
    first = calls[0]
    names = {tool["function"]["name"] for tool in first.get("tools") or [] if tool.get("type") == "function"}
    system = first["messages"][0]["content"]
    if admin:
        assert system.startswith(prompt_defaults.AGENT_AUDIT_SYSTEM_PROMPT) and "compare_models" not in names
        # The fake model's reply is no review: the reviewers lose their marks, the answer stands.
        assert store.get_turn(UID, chat_id, turn["id"])["status"] == "completed"
    else:
        assert "COMPARE OR ANSWER DIRECTLY" in system and "compare_models" in names
    # The same request again is the same message, with the same effective settings.
    assert client.post("/agent", json=payload, headers=AUTH).status_code == 200

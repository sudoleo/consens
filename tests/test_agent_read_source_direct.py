"""read_source straight from Exa (SourceReader.direct): where Exa is
available the server asks it for the page's text itself, without a model
call; a long page is read on from ``start``, and ``fresh`` has the page
fetched now. tests/test_agent_web_fetch.py has the helper's fetch, which
stays for runs without Exa and for a read Exa itself did not answer."""
import json

import pytest

from app.services import agent_quota, agent_read_source, exa
from app.services.agent_read_source import (CUT_NOTE, DIRECT_MIN_SECONDS, PAGE_LENGTH_CHARS, READ_TEXT_CHARS,
                                            READS_PER_MESSAGE, STORED_NOTE, UNTRUSTED_NOTE, ReadSourceArgs)
from app.services.llm.provider_runtime import ProviderCancellation
from test_agent_runs import UID, store  # noqa: F401  (fixture)
from test_agent_web_fetch import ANSWER, CITED, PAGE, Plan, chat_loop, compare, fake_fetch, results, run, tool_events


@pytest.fixture
def pages(monkeypatch):
    """Exa with a key; exa.page answers from ``pages.found`` (url -> text,
    a failure reason in a dict, or an exception) and records every call."""
    class Pages:
        found, calls = {}, []

    def page(url, *, characters, fresh=False):
        Pages.calls.append({"url": url, "characters": characters, "fresh": fresh})
        outcome = Pages.found.get(url, PAGE)
        if isinstance(outcome, Exception):
            raise outcome
        if isinstance(outcome, dict):
            return {"status": "failed", "cost_nanos": 0, **outcome}
        return {"status": "completed", "url": url, "title": "Report", "text": outcome[:characters],
                "published": "2026-10-01", "stored": not fresh, "cost_nanos": 1_000_000}

    Pages.found, Pages.calls = {}, []
    monkeypatch.setenv(exa.KEY_ENV, "key")
    monkeypatch.setenv("AGENT_READ_SOURCES", "1")
    monkeypatch.setattr(exa, "page", page)
    exa.reset()
    yield Pages
    exa.reset()


def read_call(url=CITED, **more):
    return "read_source", {"url": url, **more}


def service_receipts(store):
    return [r.to_dict() for r in store.db.collection("users").document(UID).collection("llm_calls").stream()
            if str(r.to_dict().get("step")).startswith("service:")]


def test_a_read_asks_exa_itself_without_a_model_call(store, monkeypatch, pages):
    helper = fake_fetch(monkeypatch)
    plan = Plan([[read_call()]])
    loop, events, saved = run(store, plan)
    assert saved["status"] == "completed" and saved["assistant_response"] == ANSWER
    assert pages.calls == [{"url": CITED, "characters": PAGE_LENGTH_CHARS, "fresh": False}]
    # No helper model, no session of its own.
    assert helper == []
    assert not [a for a in store.delegation_view(UID, loop.chat_id, loop.turn_id)["agents"] if a.get("kind") == "source"]
    [result] = results(loop)
    assert result == {"status": "completed", "note": f"{UNTRUSTED_NOTE} {STORED_NOTE}", "url": CITED,
                      "title": "Report", "published": "2026-10-01", "text_cut": False, "copy": "stored",
                      "cited_by": ["a page you chose"], "untrusted_page_text": PAGE}
    # The warning stands before the page's text.
    assert list(result)[:2] == ["status", "note"]
    # The timeline and the saved review, as with the helper's fetch.
    running, done = tool_events(events)
    assert running["host"] == "example.org" and done["read"] == "completed"
    assert done["sources"] == [{"url": CITED, "title": "Report"}]
    [read] = saved["agent_review"]["read_sources"]
    assert read["status"] == "completed" and read["text"] == PAGE and read["retrieved_at"]
    # Charged at Exa's price, with a receipt of its own.
    [receipt] = service_receipts(store)
    assert receipt["operation"] == "page" and receipt["usage"]["estimated_cost_nano_usd"] == 1_000_000
    assert receipt["usage"]["web_search_requests"] == 0
    assert receipt["quota_charged"] == agent_quota.measured_charge(receipt["usage"]) > 0


def test_a_long_page_is_read_on_from_where_the_last_read_ended(store, monkeypatch, pages):
    fake_fetch(monkeypatch)
    long_page = "".join(f"{number:07d} " for number in range(7000))  # 56,000 characters
    pages.found = {CITED: long_page}
    plan = Plan([[read_call()], [read_call(start=READ_TEXT_CHARS)], [read_call(start=2 * READ_TEXT_CHARS)],
                 [read_call(start=len(long_page) + 5)], [read_call(start=READ_TEXT_CHARS)]])
    loop, events, saved = run(store, plan)
    first, second, third, beyond, again = results(loop)
    assert first["text_cut"] and first["next_start"] == READ_TEXT_CHARS
    # How long the page is, so the agent can go straight to a later part.
    assert CUT_NOTE.format(length="55,999", next=READ_TEXT_CHARS) in first["note"]
    assert first["untrusted_page_text"] == long_page[:READ_TEXT_CHARS]
    assert second["untrusted_page_text"] == long_page[READ_TEXT_CHARS:2 * READ_TEXT_CHARS]
    assert second["next_start"] == 2 * READ_TEXT_CHARS
    # The last part: nothing goes on.
    assert third["untrusted_page_text"] == long_page.strip()[2 * READ_TEXT_CHARS:]
    assert third["text_cut"] is False and "next_start" not in third and "goes on" not in third["note"]
    # Every read asks for enough of the page to say how long it is.
    assert [call["characters"] for call in pages.calls[:3]] == [PAGE_LENGTH_CHARS] * 3
    assert beyond["status"] == "failed" and "ends before position" in beyond["reason"]
    # The same part again is in hand already.
    assert again["status"] == "already_read"
    assert len(pages.calls) == 4


def test_a_page_can_be_fetched_anew_after_its_stored_copy(store, monkeypatch, pages):
    fake_fetch(monkeypatch)
    plan = Plan([[read_call()], [read_call(fresh=True)], [read_call(fresh=True)], [read_call()]])
    loop, events, saved = run(store, plan)
    stored, fresh, again, stored_again = results(loop)
    assert stored["copy"] == "stored" and STORED_NOTE in stored["note"]
    assert fresh["status"] == "completed" and fresh["copy"] == "fetched now" and STORED_NOTE not in fresh["note"]
    # Once fetched now, neither a second fetch nor the stored copy adds anything.
    assert again["status"] == "already_read" and stored_again["status"] == "already_read"
    assert [call["fresh"] for call in pages.calls] == [False, True]


def test_a_page_exa_cannot_give_fails_with_its_reason_and_costs_nothing(store, monkeypatch, pages):
    helper = fake_fetch(monkeypatch)
    pages.found = {CITED: {"error": "the site does not let a reader in"}}
    loop, events, saved = run(store, Plan([[read_call()], [read_call()]]))
    failed, again = results(loop)
    assert failed["status"] == "failed" and "the site does not let a reader in" in failed["reason"]
    assert "do not try it again" in failed["note"].lower()
    # Exa answered: no second way is tried, the page is not asked for again.
    assert helper == [] and len(pages.calls) == 1 and again["status"] == "refused"
    assert service_receipts(store) == []
    assert tool_events(events)[1]["read"] == "failed"


def test_a_read_exa_itself_does_not_answer_goes_through_the_helpers_fetch(store, monkeypatch, pages):
    helper = fake_fetch(monkeypatch)
    pages.found = {CITED: exa.ExaError("server", "HTTP 503")}
    loop, events, saved = run(store, Plan([[read_call()], [read_call(start=READ_TEXT_CHARS)]]))
    read, later = results(loop)
    assert len(helper) == 1 and read["status"] == "completed" and read["untrusted_page_text"] == PAGE
    assert "copy" not in read
    # The helper's fetch reads a page from its beginning only.
    assert later["status"] == "failed" and "the reader did not answer" in later["reason"] and len(helper) == 1


def test_the_tool_names_its_three_fields_and_its_bounds(store, pages):
    loop = chat_loop(store, Plan())
    reader = loop.comparison.reader
    assert reader.direct
    schema = reader.tool.schema()["function"]
    assert list(schema["parameters"]["properties"]) == ["url", "start", "fresh"]
    assert schema["parameters"]["required"] == ["url"]
    assert f"{READ_TEXT_CHARS:,} characters" in schema["description"] and "start" in schema["description"]
    assert f"At most {READS_PER_MESSAGE} reads per message" in schema["description"]
    assert ReadSourceArgs(url=CITED).start == 0 and ReadSourceArgs(url=CITED).fresh is False


def test_without_exa_the_tool_is_the_helpers_fetch_with_the_address_alone(store, monkeypatch):
    exa.reset()
    monkeypatch.delenv(exa.KEY_ENV, raising=False)
    monkeypatch.setenv("AGENT_READ_SOURCES", "1")
    reader = chat_loop(store, Plan()).comparison.reader
    assert not reader.direct
    assert list(reader.tool.schema()["function"]["parameters"]["properties"]) == ["url"]


def test_a_direct_read_may_start_closer_to_the_answer_than_the_helpers(store, monkeypatch, pages):
    loop = chat_loop(store, Plan())
    reader = loop.comparison.reader
    monkeypatch.setattr(loop, "answer_time_left", lambda: DIRECT_MIN_SECONDS + 1)
    result = reader.read(ReadSourceArgs(url=CITED), cancellation=ProviderCancellation())
    assert result["status"] == "completed"
    monkeypatch.setattr(loop, "answer_time_left", lambda: DIRECT_MIN_SECONDS - 1)
    refused = reader.read(ReadSourceArgs(url="https://example.org/other"), cancellation=ProviderCancellation())
    assert refused["status"] == "refused" and "no time left" in refused["reason"]


def test_a_search_and_reads_of_its_hits_in_one_run(store, monkeypatch, pages):
    """The agent's own search and reads, both on Exa: found by this message,
    read without a helper, two receipts."""
    def search(query, **options):
        return {"hits": [{"url": CITED, "title": "Report", "excerpts": ["The first option costs 100."]}],
                "cost_nanos": 7_000_000, "notes": []}
    monkeypatch.setattr(exa, "search", search)
    helper = fake_fetch(monkeypatch)
    plan = Plan([[("web_search", {"queries": ["price option one"]})], [read_call()]])
    loop, events, saved = run(store, plan)
    assert helper == [] and saved["status"] == "completed"
    [read] = results(loop)
    assert read["cited_by"] == [agent_read_source.LABEL_SEARCH]
    assert sorted(receipt["operation"] for receipt in service_receipts(store)) == ["page", "search"]
    assert saved["agent_usage"]["web_search_requests"] == 1 and saved["agent_usage"]["complete"]


def test_a_page_longer_than_asked_for_says_so_and_parts_of_one_page_read_beside_each_other(store, monkeypatch, pages):
    fake_fetch(monkeypatch)
    pages.found = {CITED: "x" * (PAGE_LENGTH_CHARS + 10)}
    plan = Plan([[read_call(), read_call(start=READ_TEXT_CHARS), read_call(start=READ_TEXT_CHARS)]])
    loop, events, saved = run(store, plan)
    first, second, same = results(loop)
    assert CUT_NOTE.format(length=f"more than {PAGE_LENGTH_CHARS:,}", next=READ_TEXT_CHARS) in first["note"]
    assert second["status"] == "completed" and second["next_start"] == 2 * READ_TEXT_CHARS
    # The same part twice in one step: read once.
    assert same["status"] == "already_read" and len(pages.calls) == 2


def test_a_read_saves_the_review_once_not_before_and_after(store, monkeypatch, pages):
    """A direct read is over before a write of the turn's document would be:
    the saved review gets it once, with its text."""
    fake_fetch(monkeypatch)
    loop = chat_loop(store, Plan())
    saves = []
    monkeypatch.setattr(loop.comparison, "checkpoint", lambda status=None: saves.append(
        [read["status"] for read in loop.comparison.reader.reads]))
    loop.comparison.reader.read(ReadSourceArgs(url=CITED), cancellation=ProviderCancellation())
    assert saves == [["completed"]]


def test_a_read_that_never_reached_the_page_may_be_tried_again(store, monkeypatch, pages):
    helper = fake_fetch(monkeypatch, fail_models=("openai", "google"))
    pages.found = {CITED: exa.ExaError("unreachable", "ConnectTimeout")}
    plan = Plan([[read_call()], [read_call()]])
    loop, events, saved = run(store, plan)
    first, second = results(loop)
    # Exa did not answer and neither helper did: nothing about the page.
    assert first["status"] == "failed" and "a later try may work" in first["note"]
    assert "try it again" not in first["note"]
    # The second try runs (and fails the same way), it is not refused.
    assert second["status"] == "failed" and len(pages.calls) == 2


def test_after_a_summary_of_the_run_a_page_read_before_comes_back_with_its_text(store, monkeypatch, pages):
    fake_fetch(monkeypatch)
    loop = chat_loop(store, Plan())
    reader = loop.comparison.reader
    first = reader.read(ReadSourceArgs(url=CITED), cancellation=ProviderCancellation())
    again = reader.read(ReadSourceArgs(url=CITED), cancellation=ProviderCancellation())
    assert first["status"] == "completed" and again["status"] == "already_read"
    # The run's steps were summarised: the earlier result is no longer in the conversation.
    loop.run_summaries += 1
    back = reader.read(ReadSourceArgs(url=CITED), cancellation=ProviderCancellation())
    assert back["status"] == "completed" and back["untrusted_page_text"] == PAGE
    assert "summary" in back["note"] and len(pages.calls) == 1
    assert reader.read(ReadSourceArgs(url=CITED), cancellation=ProviderCancellation())["status"] == "already_read"

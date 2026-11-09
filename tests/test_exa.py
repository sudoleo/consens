"""Exa's client (app/services/exa.py): what a search and a page read send and
return, how failures are retried, and when the agent does without Exa for a
while. The network is an httpx.MockTransport."""
import json
import time
from types import SimpleNamespace

import httpx
import pytest

from app.services import exa


@pytest.fixture
def service(monkeypatch):
    """Exa with a key, answering from ``service.answers`` (a list of
    (status, body[, headers]) taken in order, the last one repeating);
    ``service.sent`` holds every request's (url, body, key)."""
    state = SimpleNamespace(answers=[(200, {"results": []})], sent=[], slept=[])

    def handler(request):
        state.sent.append((str(request.url), json.loads(request.content), request.headers.get("x-api-key")))
        status, body, *headers = state.answers[min(len(state.sent), len(state.answers)) - 1]
        return httpx.Response(status, json=body, headers=headers[0] if headers else None)

    monkeypatch.setenv(exa.KEY_ENV, "key")
    monkeypatch.setattr(exa, "_client_instance", httpx.Client(transport=httpx.MockTransport(handler)))
    monkeypatch.setattr(exa, "time", SimpleNamespace(monotonic=time.monotonic, sleep=state.slept.append))
    exa.reset()
    yield state
    exa.reset()


HIT = {"url": "https://example.org/report", "title": "  Annual\nreport ", "publishedDate": "2026-11-03T08:00:00.000Z",
       "highlights": [" The first option costs 100. ", ""], "id": "x", "author": None}


def test_a_search_sends_the_query_and_returns_pages_with_excerpts_and_its_price(service):
    service.answers = [(200, {"results": [HIT, {**HIT}, {"url": "ftp://example.org/x", "title": "no page"},
                                          {"url": "https://user:pw@example.org/", "title": "credentials"},
                                          {"url": "https://example.net/undated", "title": "", "highlights": ["b"]}],
                              "costDollars": {"total": 0.007}, "notices": ["Query was shortened.", 5]})]
    found = exa.search("what does option one cost", results=5, characters=2000, domains=("example.org",),
                       since="2026-01-01")
    url, body, key = service.sent[0]
    assert url == exa.SEARCH_URL and key == "key"
    assert body == {"query": "what does option one cost", "type": "auto", "numResults": 5,
                    "contents": {"highlights": {"maxCharacters": 2000}}, "includeDomains": ["example.org"],
                    "startPublishedDate": "2026-01-01T00:00:00.000Z"}
    # Each page once, only public http(s) addresses, the title on one line.
    assert found["hits"] == [
        {"url": "https://example.org/report", "title": "Annual report", "published": "2026-11-03",
         "excerpts": ["The first option costs 100."]},
        {"url": "https://example.net/undated", "title": "", "excerpts": ["b"]}]
    assert found["cost_nanos"] == 7_000_000 and found["notes"] == ["Query was shortened."]


def test_a_search_without_a_reported_price_costs_the_list_price(service):
    service.answers = [(200, {"results": []})]
    assert exa.search("q", results=5, characters=2000) == {"hits": [], "cost_nanos": exa.SEARCH_COST_NANOS, "notes": []}
    assert "includeDomains" not in service.sent[0][1] and "startPublishedDate" not in service.sent[0][1]


def test_a_rate_limit_and_a_server_error_are_tried_again_a_refused_request_is_not(service):
    service.answers = [(429, {"error": "slow down", "tag": "RATE_LIMIT"}, {"retry-after": "2"}),
                       (503, {"error": "over capacity"}), (200, {"results": [HIT]})]
    assert exa.search("q", results=5, characters=100)["hits"]
    assert len(service.sent) == 3
    # The wait Exa asked for (and a little apart from the others), then the short one.
    assert 2 <= service.slept[0] <= 2.3 and service.slept[1] == exa.RETRY_SECONDS
    service.sent.clear()
    service.answers = [(400, {"error": "bad", "tag": "INVALID_REQUEST_BODY"})]
    with pytest.raises(exa.ExaError) as refused:
        exa.search("q", results=5, characters=100)
    assert refused.value.code == "rejected" and refused.value.detail == "HTTP 400 INVALID_REQUEST_BODY"
    assert len(service.sent) == 1
    # A request Exa refused says nothing about the service.
    assert exa.available()


def test_after_three_failed_calls_in_a_row_the_agent_does_without_exa_for_a_while(service, monkeypatch):
    service.answers = [(500, {"error": "down"})]
    for _ in range(exa.BREAK_FAILURES - 1):
        with pytest.raises(exa.ExaError):
            exa.search("q", results=5, characters=100)
        assert exa.available()
    with pytest.raises(exa.ExaError) as failed:
        exa.search("q", results=5, characters=100)
    assert failed.value.code == "server" and not exa.available()
    # Every call tried ATTEMPTS times before it counted.
    assert len(service.sent) == exa.BREAK_FAILURES * exa.ATTEMPTS
    # The break ends by itself, and a call that works clears the count.
    clock = time.monotonic() + exa.BREAK_SECONDS + 1
    monkeypatch.setattr(exa, "time", SimpleNamespace(monotonic=lambda: clock, sleep=lambda seconds: None))
    assert exa.available()
    service.answers = [(200, {"results": []})]
    exa.search("q", results=5, characters=100)
    service.answers = [(500, {"error": "down"})]
    with pytest.raises(exa.ExaError):
        exa.search("q", results=5, characters=100)
    assert exa.available()


@pytest.mark.parametrize("status", [401, 402, 403])
def test_a_refused_key_or_used_up_credit_sets_exa_aside_at_once(service, status, caplog, monkeypatch):
    monkeypatch.setenv(exa.KEY_ENV, "secret-value")
    service.answers = [(status, {"error": "no", "tag": "NO_MORE_CREDITS"})]
    with pytest.raises(exa.ExaError) as failed:
        exa.search("q", results=5, characters=100)
    assert failed.value.code == "account" and len(service.sent) == 1 and not exa.available()
    # Only the operator heals it: logged as an error (the alert), without the key.
    assert [record.levelname for record in caplog.records if "Exa set aside" in record.getMessage()] == ["ERROR"]
    assert "secret-value" not in caplog.text


def test_no_answer_in_time_counts_as_unreachable(service, monkeypatch):
    def broken(request):
        raise httpx.ConnectTimeout("no answer")
    monkeypatch.setattr(exa, "_client_instance", httpx.Client(transport=httpx.MockTransport(broken)))
    with pytest.raises(exa.ExaError) as failed:
        exa.search("q", results=5, characters=100)
    assert failed.value.code == "unreachable" and failed.value.detail == "ConnectTimeout"


def test_configured_only_with_a_key_and_not_when_switched_off(monkeypatch):
    exa.reset()
    monkeypatch.delenv(exa.KEY_ENV, raising=False)
    assert not exa.configured() and not exa.available()
    monkeypatch.setenv(exa.KEY_ENV, "key")
    assert exa.configured() and exa.available()
    monkeypatch.setenv(exa.ENABLED_ENV, "0")
    assert not exa.configured() and not exa.available()


def test_the_pace_lets_a_burst_through_and_then_the_steady_rate():
    pace = exa._Pace(rate=5, burst=5)
    started = time.monotonic()
    for _ in range(5):
        pace.wait(started + 5)
    assert time.monotonic() - started < .15
    pace.wait(started + 5)
    assert .15 <= time.monotonic() - started < 1
    # No slot before the deadline: said, not waited out.
    with pytest.raises(exa.ExaError) as busy:
        exa._Pace(rate=.1, burst=0).wait(time.monotonic() + .2)
    assert busy.value.code == "busy"


def test_the_search_pace_follows_the_teams_limit(monkeypatch):
    monkeypatch.setenv(exa.SEARCH_QPS_ENV, "40")
    pace = exa._search_pace()
    assert (pace.rate, pace.burst) == (20, 20)
    monkeypatch.setenv(exa.SEARCH_QPS_ENV, "many")
    assert exa._search_pace().rate == exa.SEARCH_QPS / 2


def test_a_page_returns_its_text_and_whether_it_is_the_stored_copy(service):
    service.answers = [(200, {"results": [{"url": "https://example.org/report", "title": "Report", "text": "Page text.",
                                           "publishedDate": "2026-10-01T00:00:00.000Z"}],
                              "statuses": [{"id": "https://example.org/report", "status": "success", "source": "cached"}],
                              "costDollars": {"total": 0.001}})]
    read = exa.page("https://example.org/report", characters=24_000)
    assert service.sent[0][0] == exa.CONTENTS_URL
    assert service.sent[0][1] == {"urls": ["https://example.org/report"], "text": {"maxCharacters": 24_000}}
    assert read == {"status": "completed", "url": "https://example.org/report", "title": "Report", "text": "Page text.",
                    "published": "2026-10-01", "stored": True, "cost_nanos": 1_000_000}
    # Fetched now: no stored copy however fresh.
    service.answers = [(200, {"results": [{"url": "https://example.org/report", "title": "Report", "text": "New."}],
                              "statuses": [{"id": "x", "status": "success", "source": "crawled"}]})]
    read = exa.page("https://example.org/report", characters=100, fresh=True)
    assert service.sent[1][1]["maxAgeHours"] == 0
    assert read["stored"] is False and read["cost_nanos"] == exa.PAGE_COST_NANOS and read["published"] == ""


@pytest.mark.parametrize("error, reason", [
    ({"tag": "CRAWL_NOT_FOUND", "httpStatusCode": 404}, "the page does not exist (HTTP 404)"),
    ({"tag": "CRAWL_LIVECRAWL_TIMEOUT", "httpStatusCode": 504}, "the page did not answer in time"),
    ({"tag": "SOURCE_NOT_AVAILABLE", "httpStatusCode": 403}, "the site does not let a reader in"),
    ({"tag": "CRAWL_SOMETHING_NEW", "httpStatusCode": 500}, "HTTP 500"),
    ({}, "the page gave no text"),
])
def test_a_page_exa_could_not_give_is_a_result_with_its_reason(service, error, reason):
    service.answers = [(200, {"results": [], "statuses": [{"id": "x", "status": "error", "error": error}],
                              "costDollars": {"total": 0}})]
    assert exa.page("https://example.org/gone", characters=100) == {"status": "failed", "error": reason, "cost_nanos": 0}
    # No failure of the service: Exa answered.
    assert exa.available()


def test_a_page_without_text_is_no_page(service):
    service.answers = [(200, {"results": [{"url": "https://example.org/empty", "title": "Empty", "text": "  "}],
                              "statuses": [{"id": "x", "status": "success", "source": "cached"}]})]
    assert exa.page("https://example.org/empty", characters=100)["status"] == "failed"

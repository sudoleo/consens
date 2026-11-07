"""The fixed answer's links that lead nowhere (agent_answer_links)."""
import asyncio
import socket

import httpx
import pytest

from app.services import agent_answer_links
from app.services.agent_answer_links import LINKS_MAX, LinkCheck, answer_links, link_gone
from test_agent_runs import UID, store  # noqa: F401  (fixture)
from test_agent_web_fetch import CITED, Plan, chat_loop, compare, run


def test_finds_markdown_and_bare_links_once_and_none_in_code():
    text = ("Laut [Bericht](https://example.org/a_(b)) und https://example.org/c.\n"
            "Siehe auch <https://example.org/d>, (https://example.org/e) und "
            "https://EXAMPLE.org/c/ noch einmal.\n\n"
            "`https://example.org/inline` steht in Code.\n"
            "```svg\n<svg xmlns=\"http://www.w3.org/2000/svg\"/>\n```\n"
            "ftp://example.org/f und mailto:someone@example.org zählen nicht.")
    assert answer_links(text) == ["https://example.org/a_(b)", "https://example.org/c",
                                  "https://example.org/d", "https://example.org/e"]


def test_takes_at_most_the_first_links():
    links = answer_links(" ".join(f"https://example.org/{n}" for n in range(LINKS_MAX + 5)))
    assert links == [f"https://example.org/{n}" for n in range(LINKS_MAX)]


def pinned(monkeypatch, failure=None):
    async def target(url):
        if failure is not None:
            raise failure
        parts = httpx.URL(url)
        return f"{parts.scheme}://203.0.113.7{parts.raw_path.decode()}", parts.host, parts.host
    monkeypatch.setattr(agent_answer_links, "pinned_target", target)


def gone(url, routes):
    def handler(request):
        status, location = routes[request.url.path]
        return httpx.Response(status, headers={"location": location} if location else {})
    return asyncio.run(link_gone(url, transport=httpx.MockTransport(handler)))


@pytest.mark.parametrize("status, expected", [(404, 404), (410, 410), (200, None), (403, None), (401, None),
                                              (429, None), (500, None)])
def test_only_the_sites_own_no_such_page_counts(monkeypatch, status, expected):
    pinned(monkeypatch)
    assert gone("https://example.org/page", {"/page": (status, None)}) == expected


def test_follows_redirects_to_where_the_page_ends(monkeypatch):
    pinned(monkeypatch)
    routes = {"/old": (301, "/new"), "/new": (302, "https://example.org/gone"), "/gone": (410, None)}
    assert gone("https://example.org/old", routes) == 410
    loop = {"/a": (302, "/b"), "/b": (302, "/a")}
    assert gone("https://example.org/a", loop) is None


@pytest.mark.parametrize("errno, expected", [(socket.EAI_NONAME, "no_host"), (socket.EAI_AGAIN, None)])
def test_a_host_that_does_not_exist_counts_a_lookup_that_failed_does_not(monkeypatch, errno, expected):
    pinned(monkeypatch, socket.gaierror(errno, "lookup"))
    assert gone("https://no-such-host.example/page", {}) == expected


def test_never_opens_a_private_address():
    """pinned_target refuses before any request: the check finds nothing."""
    check = LinkCheck("http://127.0.0.1:8765/t.html und http://169.254.169.254/latest", gone=link_gone).start()
    assert check.result() == {"checked": 2, "missing": []}


def test_keeps_what_is_missing_in_the_answers_order_with_where_it_came_from():
    async def fake(url):
        return {"https://example.org/x": 404, "https://example.org/z": "no_host"}.get(url)
    check = LinkCheck("https://example.org/x https://example.org/y https://example.org/z",
                      retrieved=lambda url: url.endswith("/z"), gone=fake).start()
    assert check.result() == {"checked": 3, "missing": [
        {"url": "https://example.org/x", "status": 404, "retrieved": False},
        {"url": "https://example.org/z", "status": "no_host", "retrieved": True}]}


def test_a_slow_link_is_no_finding_and_the_rest_stand(monkeypatch):
    monkeypatch.setattr(agent_answer_links, "CHECK_SECONDS", 0.3)
    monkeypatch.setattr(agent_answer_links, "LINK_SECONDS", 0.2)

    async def fake(url):
        if url.endswith("/slow"):
            await asyncio.sleep(5)
        return 404
    check = LinkCheck("https://example.org/slow https://example.org/gone", gone=fake).start()
    assert check.result() == {"checked": 2, "missing": [
        {"url": "https://example.org/gone", "status": 404, "retrieved": False}]}


def test_without_links_nothing_runs():
    check = LinkCheck("Keine Adresse hier.").start()
    assert check.thread is None and check.result() is None


def test_the_review_keeps_the_links_that_lead_nowhere(store, monkeypatch):
    monkeypatch.setenv("AGENT_READ_SOURCES", "1")
    opened = []

    async def fake(url, **kwargs):
        opened.append(url)
        return 404 if url != "https://example.org/fine" else None
    monkeypatch.setattr(agent_answer_links, "link_gone", fake)
    answer = (f"Laut [Bericht]({CITED}) kostet es 100 Euro, [mehr](https://example.org/invented) "
              "und https://example.org/fine.")
    loop, events, saved = run(store, Plan(steps=[[compare()]], answer=answer))
    assert saved["status"] == "completed" and saved["assistant_response"] == answer
    assert sorted(opened) == sorted([CITED, "https://example.org/invented", "https://example.org/fine"])
    # The cited page the comparison answers named counts as retrieved.
    assert saved["agent_review"]["links"] == {"checked": 3, "missing": [
        {"url": CITED, "status": 404, "retrieved": True},
        {"url": "https://example.org/invented", "status": 404, "retrieved": False}]}
    assert any(e.get("type") == "review" and e["review"].get("links") for e in loop_frames(loop, events))


def loop_frames(loop, events):
    """The review frames the browser got (ComparisonTools.checkpoint)."""
    frames = list(events)
    while not loop.outgoing.empty():
        frames.append(loop.outgoing.get_nowait())
    return frames


def test_nothing_is_saved_when_every_link_works(store):
    loop, events, saved = run(store, Plan(steps=[[compare()]], answer=f"Siehe {CITED}."))
    assert saved["status"] == "completed" and "links" not in saved["agent_review"]


def test_no_check_in_a_chat_with_google_data(store, monkeypatch):
    opened = []

    async def fake(url, **kwargs):
        opened.append(url)
    monkeypatch.setattr(agent_answer_links, "link_gone", fake)
    loop = chat_loop(store, Plan(), google_data=True)
    assert loop._check_links("Siehe https://example.org/mail?text=geheim") is None and opened == []

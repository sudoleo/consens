"""The German page costs the server little (audit 2026-10-28).

Until then ``I18nMiddleware._page`` translated on the event loop, every word of
a shared answer was parsed into a tree first, and a long share page held all
other requests, SSE streams included, for 0.5-2 s.
"""

import asyncio
import threading

import pytest
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.testclient import TestClient

from app.api.routers import firebase_auth_proxy, topics as topics_router
from app.core import i18n, i18n_middleware
from app.core.i18n_middleware import I18nMiddleware
from app.core.rate_limit import limiter


@pytest.fixture
def catalog(monkeypatch):
    current = i18n.Catalog({"New chat": "Neuer Chat", "Settings": "Einstellungen", "A page": "Eine Seite"})
    monkeypatch.setitem(i18n._catalogs, "de", ((), current))
    monkeypatch.setitem(i18n._checked, "de", float("inf"))
    i18n._translated_cache.clear()
    yield current
    i18n._translated_cache.clear()


def share_page(answer):
    return ('<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><title>A page</title></head><body>'
            '<header><a href="/app">New chat</a></header>'
            f'<main><div class="share-md" data-i18n-skip lang="en">{answer}</div></main>'
            "<footer><p>Settings</p></footer></body></html>")


ANSWER = ('<p>Start a <strong>New chat</strong> first.</p><div>nested <div>Settings</div></div>'
          '<p><a href="https://example.org" title="a </div> b">link</a></p>'
          "<script>var end = '</div>';</script><!-- </div> --><ul><li>New chat</li></ul>")


def test_the_readers_words_are_not_parsed_and_stay_as_they_are(catalog):
    root = i18n.parse(share_page(ANSWER))
    marked = next(i18n._find(root, lambda element: "data-i18n-skip" in element.start))
    # One raw block instead of a tree of the answer's elements.
    assert [type(child).__name__ for child in marked.children] == ["_Raw"]
    assert marked.children[0].raw == ANSWER and marked.end == "</div>"
    out = i18n.translate_html(share_page(ANSWER), "de")
    assert ANSWER in out
    assert '<a href="/app">Neuer Chat</a>' in out and "<p>Einstellungen</p>" in out


@pytest.mark.parametrize("content", [
    "<p>unclosed <div>inner</p>",            # the inner div never closes
    "<p>New chat",                           # no end tag at all
])
def test_marked_content_without_a_matching_end_is_parsed_as_before(catalog, content):
    page = ('<html><body><section data-i18n-skip>' + content + "</body></html>")
    i18n.parse(page)  # no exception, nothing swallowed
    out = i18n.translate_html(page, "de")
    assert out.endswith("</body></html>")


def test_implicitly_closed_marked_tags_keep_the_old_parsing(catalog):
    page = "<ul><li data-i18n-skip>New chat<li>Settings</ul>"
    assert i18n.translate_html(page, "de") == "<ul><li data-i18n-skip>New chat<li>Einstellungen</ul>"


@pytest.fixture
def client(catalog):
    app = FastAPI()

    @app.get("/s/answer", response_class=HTMLResponse)
    def page():
        return share_page(ANSWER)

    @app.get("/s/huge", response_class=HTMLResponse)
    def huge():
        return share_page("<p>x</p>" * (i18n_middleware.MAX_TRANSLATED_PAGE_CHARS // 8))

    app.add_middleware(I18nMiddleware)
    return TestClient(app)


def test_the_page_is_translated_off_the_event_loop(client, monkeypatch):
    test_client = client
    threads = []
    original = I18nMiddleware._page

    def recording(self, *args):
        threads.append(threading.current_thread())
        return original(self, *args)

    monkeypatch.setattr(I18nMiddleware, "_page", recording)
    loop_threads = []
    real_run = asyncio.BaseEventLoop.run_forever

    def run_forever(self):
        loop_threads.append(threading.current_thread())
        return real_run(self)

    monkeypatch.setattr(asyncio.BaseEventLoop, "run_forever", run_forever)
    response = test_client.get("/s/answer", headers={"Accept-Language": "de"})
    assert response.status_code == 200 and "Neuer Chat" in response.text
    assert threads and loop_threads and threads[0] not in loop_threads


def test_a_page_beyond_the_cap_goes_out_untranslated_with_the_dictionary(client, monkeypatch):
    test_client = client
    calls = []
    monkeypatch.setattr(i18n, "translate_html", lambda *args, **kwargs: calls.append(args) or args[0])
    response = test_client.get("/s/huge", headers={"Accept-Language": "de"})
    assert response.status_code == 200 and calls == []
    assert '<a href="/app">New chat</a>' in response.text
    assert "/i18n/de." in response.text  # the browser translates it as it arrives
    test_client.get("/s/answer", headers={"Accept-Language": "de"})
    assert len(calls) == 1


@pytest.mark.parametrize("endpoint,rate", [
    (topics_router.topics_hub, "60 per 1 minute"),
    (topics_router.topic_page, "60 per 1 minute"),
    (firebase_auth_proxy.firebase_auth_helper, "60 per 1 minute"),
    (firebase_auth_proxy.firebase_init_json, "60 per 1 minute"),
])
def test_translated_public_pages_and_the_auth_proxy_are_throttled(endpoint, rate):
    limits = limiter._route_limits.get(f"{endpoint.__module__}.{endpoint.__name__}", [])
    assert [str(item.limit) for item in limits] == [rate]

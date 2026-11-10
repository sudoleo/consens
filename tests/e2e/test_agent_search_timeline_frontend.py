"""The agent's own web search in the timeline (agent-activity.js): what it
searched for in its own words under the step, and the pages found as the
answer's pills. Built /app with isolated HTTP fixtures; no paid calls.
"""
import json

import pytest
from playwright.sync_api import expect
from test_agent_chat_frontend import CATALOG, _choose_mode, _snapshot
from test_phase4_frontend import phase4_server, _real_firebase_page, _json  # noqa: F401  (fixture)

CHAT = "b" * 32
QUERIES = ["Hannover 96 Cheftrainer aktuell", "Hannover 96 Trainer seit wann"]
SOURCES = [{"url": "https://www.hannover96.de/newscenter/news/details/trainer.html", "title": "Neuer Cheftrainer"},
           {"url": "https://www.ndr.de/sport/fussball/hannover-1268.html", "title": "Zweite Bundesliga"},
           {"url": "https://www.kicker.de/hannover-96/team-trainer", "title": "Trainer"}]
ANSWER = "Cheftrainer von Hannover 96 ist Sandro Wagner, seit dem 21. September 2026."


def _routes(page, turns, bookmark):
    page.route("**/user_status", lambda r: _json(r, {"tier": "pro", "is_pro": True, "agent_access": True}))
    page.route("**/usage", lambda r: _json(r, {"tier": "pro", "is_pro": True, "remaining": 500, "total_limit": 500}))
    page.route("**/agent/models", lambda r: _json(r, CATALOG))
    page.route("**/agent/budget", lambda r: _json(r, {"token_budget": {"limit": 250000, "used": 1000, "remaining": 249000}}))
    page.route("**/api/my/memory", lambda r: _json(r, {"memory": {"content": "", "revision": 0}}))
    page.route("**/chats", lambda r: _json(r, {"chat": {"id": CHAT, "execution_mode": "agent"}}))
    page.route("**/bookmarks/*/conversation*", lambda r: _json(r, {"chat_id": CHAT, "turns": turns, "next_cursor": None,
                                                                    "has_more": False}))
    page.route("**/bookmarks/*", lambda r: _json(r, {"bookmark": bookmark}))

    def answer(route):
        body = route.request.post_data_json
        turn_id = "1" * 32
        search = {"id": "completion:0:call_1/tool", "step_id": "completion:0:call_1", "kind": "tool", "name": "web_search",
                  "status": "succeeded", "queries": QUERIES, "count": 2, "sources": SOURCES, "took_ms": 1812}
        turn = {"id": turn_id, "turn_id": turn_id, "question": body["question"], "status": "completed", "position": 1,
                "mode": "Agent", "execution_mode": "agent", "consensus": ANSWER, "differences": "", "model_answers": {},
                "sources": SOURCES, "agent_settings": {"model_id": body["model_id"], "label": "GPT-6.1 Terra"},
                "agent_activity": [search], "created_at": "2026-11-10T01:00:00Z", "completed_at": "2026-11-10T01:00:10Z"}
        turns.append(turn)
        bookmark.update(id=body["bookmark_id"], query=body["question"], title=body["question"], mode="Agent",
                        execution_mode="agent", chat_id=CHAT, turn_id=turn_id,
                        responses={"consensus": ANSWER, "differences": ""}, sources=SOURCES)
        meta = {"id": body["bookmark_id"], "title": body["question"], "query": body["question"], "mode": "Agent",
                "has_consensus": True}
        final = {"chat_id": CHAT, "turn_id": turn_id, "response": ANSWER, "turn": turn, "bookmark_meta": meta}
        running = {"type": "activity", **{**search, "status": "running", "sources": [], "count": None}}
        route.fulfill(content_type="text/event-stream", body=(
            "event: activity\ndata: " + json.dumps(running) + "\n\n"
            + "event: delta\ndata: " + json.dumps({"text": ANSWER}) + "\n\n"
            + "event: final\ndata: " + json.dumps(final) + "\n\n"))

    page.route("**/agent", answer)


@pytest.mark.parametrize("width,dark", [(1280, False), (390, True)])
def test_a_search_shows_its_words_and_the_pages_it_found(browser, phase4_server, width, dark):
    context, page = _real_firebase_page(browser, phase4_server, has_touch=width < 700)
    errors, turns, bookmark = [], [], {}
    page.on("pageerror", lambda error: errors.append(str(error)))
    try:
        page.set_viewport_size({"width": width, "height": 900})
        _routes(page, turns, bookmark)
        page.evaluate("async () => { await window.__switchE2EUser('account-a'); }")
        page.evaluate("dark => { document.documentElement.classList.toggle('dark-mode', dark); document.body.classList.toggle('dark-mode', dark); }", dark)
        _choose_mode(page, "agent")
        page.locator("#questionInput").fill("Wer trainiert Hannover 96?")
        page.locator("#sendButton").click()
        page.wait_for_function("() => App.runRegistry.visible()?.status === 'succeeded'")
        activity = page.locator("#agentAnswerActivity .agent-activity")
        expect(activity).to_be_visible()
        # The timeline opens only on the reader's click.
        activity.locator("summary").first.click()
        step = activity.locator(".agent-activity-tool").first
        expect(step).to_be_visible()
        expect(step.locator("strong")).to_have_text("Searched the web")
        # The agent's own search words, kept as written.
        expect(step.locator("p[data-i18n-skip]")).to_have_text(" · ".join(QUERIES))
        expect(step.locator(".agent-activity-sources a")).to_have_count(3)
        step.scroll_into_view_if_needed()
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")
        _snapshot(page, f"agent-search-timeline-{width}")
        assert errors == []
    finally:
        context.close()

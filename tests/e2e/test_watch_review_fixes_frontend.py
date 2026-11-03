"""The Watches page and the Watch pill in the built /app, since 2026-11-03.

A Watch runs the Agent on a schedule in its chat (agent_watches.py). Writer-
free like the other Phase-4 browser tests: every API answer comes from the
route handlers below. The page lists the Agent's Watches by what they want
from the reader and opens a row's chat; "…" pauses and ends one; the page
opened directly loads once; the newest answer's pill opens the sheet that
starts a Watch in its chat.
"""
import json
from datetime import datetime, timedelta, timezone

from playwright.sync_api import expect
from test_agent_chat_frontend import CATALOG, _choose_mode
from test_phase4_frontend import phase4_server, _real_firebase_page, _json  # noqa: F401 (fixture)

LATER = (datetime.now(timezone.utc) + timedelta(hours=20)).isoformat()
EARLIER = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()


def _watch(watch_id, task, **extra):
    watch = {"id": watch_id, "chat_id": "c" * 32, "turn_id": "", "bookmark_id": f"agent_{watch_id}", "task": task,
             "goal": "", "status": "active", "interval": "daily", "run_time": "08:00", "run_weekday": "",
             "timezone": "", "next_run_at": LATER, "created_at": EARLIER, "runs": 2,
             "last_run": {"at": EARLIER, "outcome": "quiet", "summary": ""}, "ended": "", "unread": False,
             "email_enabled": True, "telegram_enabled": True, "image": None}
    watch.update(extra)
    return watch


def _watch_routes(page, state):
    def agent_watches(route):
        request = route.request
        path = request.url.split("?")[0]
        if path.endswith("/agent/watches"):
            if request.method == "POST":
                body = request.post_data_json
                created = _watch("new1", body["task"], chat_id=body.get("chat_id") or "n" * 32, last_run=None, runs=0)
                state["watches"].insert(0, created)
                state["calls"].append(("POST", "create", body))
                return _json(route, {"watch": created}, status=201)
            return _json(route, {"watches": state["watches"], "intervals": ["daily", "weekly"],
                                 "active_count": sum(1 for w in state["watches"] if w["status"] == "active"),
                                 "active_limit": 5})
        rest = path.rsplit("/agent/watches/", 1)[1].split("/")
        watch_id, action = rest[0], rest[1] if len(rest) > 1 else ""
        target = next(item for item in state["watches"] if item["id"] == watch_id)
        state["calls"].append((request.method, action or "patch", watch_id))
        if action == "pause":
            target.update(status="paused", next_run_at=None)
        elif action == "stop":
            target.update(status="done", ended="user", next_run_at=None)
        elif action == "seen":
            target.update(unread=False)
        return _json(route, {"watch": target})

    page.route("**/agent/watches", agent_watches)
    page.route("**/agent/watches?*", agent_watches)
    page.route("**/agent/watches/**", agent_watches)
    page.route("**/api/my/watches", lambda route: _json(route, {"status": "success", "watches": state.get("archive", []),
                                                                "limits": {"plan": "pro"}, "archived": True}))
    page.route("**/api/my/telegram", lambda route: _json(route, {"telegram": {"configured": False}}))


def test_the_page_lists_watches_by_what_they_need_and_opens_a_chat(browser, phase4_server):
    state = {"calls": [], "watches": [
        _watch("run", "Check the Garmin 965 price on bike-discount.de."),
        _watch("found", "Tell me when IRONMAN Hamburg 2027 registration opens.", unread=True,
               last_run={"at": EARLIER, "outcome": "finding", "summary": "Registration opened this morning."}),
        _watch("ask", "Renew the parking permit when the portal opens.", unread=True,
               last_run={"at": EARLIER, "outcome": "needs_you", "summary": "The portal asks for a new login."}),
    ], "archive": [{"id": "old", "question": "When does GPT-6 ship?", "share_path": "/s/old",
                    "last_run_at": "2026-10-30T08:00:00+00:00"}]}
    context, page = _real_firebase_page(browser, phase4_server, path="/app/watches",
                                        before_goto=lambda page: _watch_routes(page, state))
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    try:
        expect(page.locator(".aw-row")).to_have_count(3)
        titles = page.locator(".aw-section-title").all_text_contents()
        assert titles[:3] == ["Needs you", "New", "Running"], titles
        expect(page.locator(".aw-row.is-needs .aw-line")).to_have_text("The portal asks for a new login.")
        expect(page.locator(".aw-archive-link")).to_have_text("When does GPT-6 ship?")
        page.evaluate("() => { window.__opened = []; window.openBookmark = id => window.__opened.push(id); }")
        page.locator('.aw-row[data-watch-id="found"] .aw-open').click()
        page.wait_for_function("() => window.__opened.length === 1")
        assert page.evaluate("() => window.__opened") == ["agent_found"]
        assert ("POST", "seen", "found") in state["calls"]
        assert not errors, errors
    finally:
        context.close()


def test_a_watch_is_paused_and_ended_from_its_menu(browser, phase4_server):
    state = {"calls": [], "watches": [_watch("w1", "Check the Garmin 965 price on bike-discount.de.")]}
    context, page = _real_firebase_page(browser, phase4_server, path="/app/watches",
                                        before_goto=lambda page: _watch_routes(page, state))
    try:
        row = page.locator('.aw-row[data-watch-id="w1"]')
        expect(row).to_be_visible()
        row.locator(".aw-more").click()
        menu = page.locator(".aw-menu")
        expect(menu).to_be_visible()
        menu.get_by_role("menuitem", name="Pause").click()
        expect(page.locator(".aw-section.is-paused")).to_be_visible()
        row.locator(".aw-more").click()
        page.locator(".aw-menu").get_by_role("menuitem", name="End Watch").click()
        page.locator("#appConfirmDialog .confirm-accept").click()
        expect(page.locator(".aw-disclosure")).to_have_text("Show ended Watches (1)")
        assert [call[:2] for call in state["calls"]] == [("POST", "pause"), ("POST", "stop")]
    finally:
        context.close()


def test_the_watch_page_opened_directly_loads_once(browser, phase4_server):
    # Review 2: the route's wait and the auth state both rendered the page.
    state = {"calls": [], "watches": [_watch("w1", "Check the Garmin 965 price on bike-discount.de.")]}
    counts = {}

    def count(request):
        path = request.url.split("?")[0]
        for name in ("/agent/watches", "/api/my/watches", "/api/my/telegram"):
            if path.endswith(name):
                counts[name] = counts.get(name, 0) + 1

    def before_goto(page):
        page.on("request", count)
        _watch_routes(page, state)

    context, page = _real_firebase_page(browser, phase4_server, path="/app/watches", before_goto=before_goto)
    try:
        expect(page.locator('.aw-row[data-watch-id="w1"]')).to_be_visible()
        page.wait_for_timeout(1500)
        assert counts == {"/agent/watches": 1, "/api/my/watches": 1, "/api/my/telegram": 1}, counts
        expect(page.locator("#watchDashLimit")).to_have_text("1 of 5 Watches running")
    finally:
        context.close()


def test_the_newest_answer_has_the_pill_and_it_starts_a_watch_in_this_chat(browser, phase4_server):
    context, page = _real_firebase_page(browser, phase4_server)
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    chat_id = "a" * 32
    turns = []
    state = {"calls": [], "watches": []}
    questions = ["When will OpenAI release GPT-6 to the public?", "And what will it cost per month?"]
    try:
        page.route("**/user_status", lambda route: _json(route, {"tier": "pro", "is_pro": True,
            "agent_access": True, "limit": 500, "deep_limit": 50}))
        page.route("**/usage", lambda route: _json(route, {"tier": "pro", "is_pro": True,
            "remaining": 10, "deep_remaining": 1, "total_limit": 500, "deep_total_limit": 50}))
        page.route("**/chats", lambda route: _json(route, {"chat": {"id": chat_id, "execution_mode": "agent"}}))
        page.route("**/agent/models", lambda route: _json(route, CATALOG))
        _watch_routes(page, state)

        def answer(route):
            body = route.request.post_data_json
            turn_id = f"{len(turns) + 1:032x}"
            text = f"Here is what is known: {body['question']}"
            turn = {"id": turn_id, "turn_id": turn_id, "question": body["question"], "status": "completed",
                    "position": len(turns) + 1, "mode": "Agent", "execution_mode": "agent", "consensus": text,
                    "differences": "", "differences_data": None, "model_answers": {}, "sources": [],
                    "agent_settings": {"model_id": CATALOG["default_model_id"], "label": "DeepSeek V4.1 Flash"}}
            turns.append(turn)
            meta = {"id": body["bookmark_id"], "title": questions[0], "query": body["question"],
                    "mode": "Agent", "has_consensus": True}
            stream = "event: delta\ndata: " + json.dumps({"text": text}) + "\n\n"
            stream += "event: final\ndata: " + json.dumps({"chat_id": chat_id, "turn_id": turn_id, "response": text,
                                                           "turn": turn, "bookmark_meta": meta}) + "\n\n"
            route.fulfill(content_type="text/event-stream", body=stream)

        page.route("**/agent", answer)
        page.evaluate("async () => { await window.__switchE2EUser('account-a'); }")
        page.wait_for_function("() => document.getElementById('runModeControl').hidden === false")
        _choose_mode(page, "agent")
        page.locator("#questionInput").fill(questions[0])
        page.locator("#sendButton").click()
        page.wait_for_function("() => App.runRegistry.visible()?.status === 'succeeded'")
        expect(page.locator("#agentAnswer #agentAnswerWatchButton")).to_be_visible()
        page.locator("#questionInput").fill(questions[1])
        page.wait_for_function("() => !document.body.classList.contains('composer-gliding')")
        page.wait_for_timeout(500)
        page.locator("#sendButton").click()
        page.wait_for_function("q => App.runRegistry.visible()?.status === 'succeeded'"
                               " && App.runRegistry.visible().question === q", arg=questions[1])
        # A Watch belongs to the chat: one pill, under the newest answer.
        expect(page.locator("#threadHistory .agent-watch-pill")).to_have_count(0)
        live = page.locator("#agentAnswer #agentAnswerWatchButton")
        expect(live).to_be_visible()
        live.click()
        sheet = page.locator(".watch-sheet")
        expect(sheet).to_be_visible()
        expect(sheet.locator(".watch-sheet-task")).to_have_value(questions[1])
        sheet.locator(".watch-sheet-start").click()
        expect(sheet).to_be_hidden()
        created = next(call[2] for call in state["calls"] if call[1] == "create")
        assert created["chat_id"] == chat_id and created["task"] == questions[1]
        expect(live).to_have_text("Watching")
        assert not errors, errors
    finally:
        context.close()

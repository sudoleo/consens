"""Watches after the second review of the Apple audit, in the built /app.

Writer-free like the other Phase-4 browser tests: every API answer comes from
the route handlers below. Measured per frame where the finding was a jump:
a card that is deleted folds away without first growing by its padding, and
a quick Undo brings it back for good. The new watch shows on the page however
the success step is closed, and every Agent answer has its Watch pill with the
question of its own turn, also in the history and in a reopened chat (J20).
"""
import json
from datetime import datetime, timedelta, timezone

from playwright.sync_api import expect
from test_agent_chat_frontend import CATALOG, _choose_mode
from test_phase4_frontend import phase4_server, _real_firebase_page, _json  # noqa: F401 (fixture)

FUTURE = (datetime.now(timezone.utc) + timedelta(hours=26)).isoformat()


def _watch(watch_id, question, **extra):
    watch = {"id": watch_id, "status": "active", "question": question, "condition": "",
             "goal_state": "not_met", "interval": "weekly", "run_weekday": "monday", "run_time": "08:00",
             "timezone": "", "next_run_at": FUTURE, "share_path": f"/s/{watch_id}", "share_id": f"sh-{watch_id}",
             "visibility": "private", "email_enabled": True, "telegram_enabled": False, "email_mode": "changes_only",
             "history": [{"ts": "2026-10-19T08:00:00+00:00", "signal": "stable", "trigger": "stable"}]}
    watch.update(extra)
    return watch


def _watch_routes(page, state):
    def watches(route):
        _json(route, {"status": "success", "watches": state["watches"],
                      "limits": {"plan": "pro", "active_count": len(state["watches"]), "active_limit": 10,
                                 "daily_available": True}})

    def create(route):
        body = route.request.post_data_json
        created = _watch("created", body["question"], condition=body["condition"], interval=body["interval"],
                         run_weekday=body["run_weekday"], run_time=body["run_time"], history=[],
                         awaiting_first_run=True)
        state["watches"] = [created, *state["watches"]]
        _json(route, {"status": "success", "watch": created})

    def change(route):
        method = route.request.method
        path = route.request.url.split("?")[0]
        if path.endswith("/goal-suggestions"):
            _json(route, {"goals": []})
            return
        watch_id = path.rsplit("/", 1)[-1]
        state["calls"].append((method, watch_id))
        target = next(item for item in state["watches"] if item["id"] == watch_id)
        if method == "DELETE":
            state["watches"] = [item for item in state["watches"] if item["id"] != watch_id]
            _json(route, {"status": "success"})
            return
        target.update(route.request.post_data_json or {})
        _json(route, {"status": "success", "watch": {k: v for k, v in target.items() if k != "history"}})

    page.route("**/api/my/watches", watches)
    page.route("**/api/my/watch-brief", lambda route: _json(route, {"brief": {}}))
    page.route("**/api/my/telegram", lambda route: _json(route, {"telegram": {"configured": False}}))
    page.route("**/api/watch", create)
    page.route("**/api/watch/*", change)


# Card heights, one per painted frame, while `action` runs.
FRAMES = """async ({ selector, action, ms }) => {
  const card = document.querySelector(selector);
  const heights = [];
  let running = true;
  const sample = () => { if (!running) return; heights.push(card.getBoundingClientRect().height); requestAnimationFrame(sample); };
  const before = card.getBoundingClientRect().height;
  eval(action);
  requestAnimationFrame(sample);
  await new Promise(resolve => setTimeout(resolve, ms));
  running = false;
  return { before, heights };
}"""


def test_deleted_card_folds_without_growing_and_quick_undo_keeps_it(browser, phase4_server):
    context, page = _real_firebase_page(browser, phase4_server)
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    state = {"watches": [_watch("w1", "When will OpenAI release GPT-6?"),
                         _watch("w2", "Will the EU pass the AI liability rules?")], "calls": []}
    try:
        _watch_routes(page, state)
        page.click("#viewSwitchWatches")
        card = page.locator('.wd-item[data-watch-id="w1"]')
        expect(card).to_be_visible()
        card.locator(".wd-action-toggle").click()
        page.wait_for_function("() => document.querySelector('.wd-item[data-watch-id=\"w1\"]').classList.contains('is-open')")
        page.wait_for_timeout(400)

        folded = page.evaluate(FRAMES, {"selector": '.wd-item[data-watch-id="w1"]', "ms": 500,
                                        "action": "card.querySelector('.wd-settings-footer [data-action=\"delete\"]').click()"})
        assert folded["heights"], folded
        # Never taller than before its first frame (a content-box card grew by
        # its padding, 34 px, and pushed the cards below down).
        assert max(folded["heights"]) <= folded["before"] + 0.5, folded
        assert folded["heights"][-1] < 1, folded
        expect(card).to_be_hidden()
        expect(page.locator("#appToasts .toast.is-shown")).to_contain_text("Watch deleted")
        page.locator("#appToasts .toast.is-shown .toast-action").click()
        expect(card).to_be_visible()
        page.wait_for_timeout(600)
        restored = card.bounding_box()["height"]
        assert abs(restored - folded["before"]) < 1, (restored, folded["before"])

        # Undo while the card is still on its way out: back for good.
        page.evaluate("() => document.querySelector('.wd-item[data-watch-id=\"w1\"] .wd-settings-footer [data-action=\"delete\"]').click()")
        page.wait_for_timeout(80)
        page.locator("#appToasts .toast.is-shown .toast-action").click()
        page.wait_for_timeout(900)
        expect(card).to_be_visible()
        assert abs(card.bounding_box()["height"] - folded["before"]) < 1
        assert ("DELETE", "w1") not in state["calls"]
        assert not errors, errors
    finally:
        context.close()


def test_new_watch_shows_on_the_page_when_its_success_step_is_left_with_escape(browser, phase4_server):
    context, page = _real_firebase_page(browser, phase4_server)
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    state = {"watches": [_watch("w1", "When will OpenAI release GPT-6?")], "calls": []}
    try:
        _watch_routes(page, state)
        page.click("#viewSwitchWatches")
        expect(page.locator('.wd-item[data-watch-id="w1"]')).to_be_visible()
        page.click("#watchDashCreate")
        page.fill("#watchQuestion", "Will the EU pass the AI liability rules in 2027?")
        page.click("#watchQuestionNext")
        page.click("#watchAdvancedSettings summary")
        page.fill("#watchRunTime", "07:30")
        page.select_option("#watchVisibility", "public")
        # "Edit" changes only the question.
        page.click("#watchQuestionEdit")
        page.fill("#watchQuestion", "Will the EU pass the AI liability rules before 2028?")
        page.click("#watchQuestionNext")
        expect(page.locator("#watchRunTime")).to_have_value("07:30")
        expect(page.locator("#watchVisibility")).to_have_value("public")
        page.click("#watchConfirmBtn")
        expect(page.locator("#watchDoneBtn")).to_be_visible()
        page.keyboard.press("Escape")
        expect(page.locator("#shareModal")).to_be_hidden()
        first = page.locator('.wd-section[data-section="active"] .wd-item').first
        expect(first).to_have_attribute("data-watch-id", "created")
        assert not errors, errors
    finally:
        context.close()


def test_the_watch_page_opened_directly_loads_once(browser, phase4_server):
    # Review 2: /app/watches opened directly loaded the list three times and
    # brief and Telegram twice: the route's wait and the auth state both
    # rendered the page, and the sign-in loaded the list beside them.
    state = {"watches": [_watch("w1", "When will OpenAI release GPT-6?")], "calls": []}
    counts = {}

    def count(request):
        path = request.url.split("?")[0]
        if "/api/my/" in path:
            name = path.rsplit("/api/my/", 1)[1]
            counts[name] = counts.get(name, 0) + 1

    def before_goto(page):
        page.on("request", count)
        _watch_routes(page, state)

    context, page = _real_firebase_page(browser, phase4_server, path="/app/watches", before_goto=before_goto)
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    try:
        expect(page.locator('.wd-item[data-watch-id="w1"]')).to_be_visible()
        # The route polls every 250 ms; whatever else would load has had its turn.
        page.wait_for_timeout(1500)
        assert counts.get("watches") == 1, counts
        assert counts.get("watch-brief") == 1, counts
        assert counts.get("telegram") == 1, counts
        expect(page.locator("#watchDashLimit")).to_contain_text("1 of 10 active")
        assert not errors, errors
    finally:
        context.close()


def test_the_full_dialog_turns_into_the_form_once_a_deletion_frees_the_slot(browser, phase4_server):
    # Review 2: "all slots are in use" stood after the watch was deleted.
    context, page = _real_firebase_page(browser, phase4_server)
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    state = {"watches": [_watch("w1", "When will OpenAI release GPT-6?")], "calls": []}
    try:
        _watch_routes(page, state)
        page.route("**/api/my/watches", lambda route: _json(route, {"status": "success", "watches": state["watches"],
            "limits": {"plan": "pro", "active_count": len(state["watches"]), "active_limit": 1}}))
        page.click("#viewSwitchWatches")
        card = page.locator('.wd-item[data-watch-id="w1"]')
        expect(card).to_be_visible()
        card.locator(".wd-action-toggle").click()
        card.locator('.wd-settings-footer [data-action="delete"]').click()
        expect(page.locator("#appToasts .toast.is-shown")).to_contain_text("Watch deleted")
        # While its Undo stands the slot is still taken.
        page.click("#watchDashCreate")
        expect(page.locator("#watchDialogLimit")).to_contain_text("Your watch slot is in use")
        expect(page.locator("#watchShowList")).to_be_focused()
        # The Undo passes, the watch is deleted, and the dialog follows.
        question = page.locator("#watchQuestion")
        expect(question).to_be_visible(timeout=12000)
        assert ("DELETE", "w1") in state["calls"]
        expect(page.locator("#watchShowList")).to_have_count(0)
        expect(page.locator("#shareModal")).to_be_visible()
        question.fill("Will the EU pass the AI liability rules in 2027?")
        expect(page.locator("#watchQuestionNext")).to_be_enabled()
        assert not errors, errors
    finally:
        context.close()


def test_every_agent_answer_has_a_watch_pill_with_its_own_question(browser, phase4_server):
    context, page = _real_firebase_page(browser, phase4_server)
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    chat_id = "a" * 32
    turns, bookmark = [], {}
    questions = ["When will OpenAI release GPT-6 to the public?", "And what will it cost per month?"]
    try:
        page.route("**/user_status", lambda route: _json(route, {"tier": "pro", "is_pro": True,
            "agent_access": True, "limit": 500, "deep_limit": 50}))
        page.route("**/usage", lambda route: _json(route, {"tier": "pro", "is_pro": True,
            "remaining": 10, "deep_remaining": 1, "total_limit": 500, "deep_total_limit": 50}))
        page.route("**/chats", lambda route: _json(route, {"chat": {"id": chat_id, "execution_mode": "agent"}}))
        page.route("**/agent/models", lambda route: _json(route, CATALOG))
        page.route("**/api/my/watches", lambda route: _json(route, {"status": "success", "watches": [],
            "limits": {"plan": "pro", "active_count": 0, "active_limit": 10}}))
        page.route("**/api/watch/goal-suggestions", lambda route: _json(route, {"goals": []}))
        page.route("**/api/my/telegram", lambda route: _json(route, {"telegram": {"configured": False}}))

        def answer(route):
            body = route.request.post_data_json
            turn_id = f"{len(turns) + 1:032x}"
            text = f"Here is what is known: {body['question']}"
            turn = {"id": turn_id, "turn_id": turn_id, "question": body["question"], "status": "completed",
                    "position": len(turns) + 1, "mode": "Agent", "execution_mode": "agent", "consensus": text,
                    "differences": "", "differences_data": None, "model_answers": {}, "sources": [],
                    "agent_settings": {"model_id": CATALOG["default_model_id"], "label": "DeepSeek V4.1 Flash"}}
            turns.append(turn)
            bookmark.update(id=body["bookmark_id"], query=body["question"], title=questions[0], mode="Agent",
                            execution_mode="agent", chat_id=chat_id, turn_id=turn_id,
                            responses={"consensus": text, "differences": ""}, sources=[])
            meta = {"id": body["bookmark_id"], "title": questions[0], "query": body["question"],
                    "mode": "Agent", "has_consensus": True}
            stream = "event: delta\ndata: " + json.dumps({"text": text}) + "\n\n"
            stream += "event: final\ndata: " + json.dumps({"chat_id": chat_id, "turn_id": turn_id, "response": text,
                                                           "turn": turn, "bookmark_meta": meta}) + "\n\n"
            route.fulfill(content_type="text/event-stream", body=stream)

        page.route("**/agent", answer)
        page.route("**/bookmarks/*/conversation*", lambda route: _json(route, {"chat_id": chat_id, "turns": turns,
                                                                              "next_cursor": None, "has_more": False}))
        page.route("**/bookmarks/*", lambda route: _json(route, {"bookmark": bookmark}))
        page.evaluate("async () => { await window.__switchE2EUser('account-a'); }")
        page.wait_for_function("() => document.getElementById('runModeControl').hidden === false")
        _choose_mode(page, "agent")

        page.locator("#questionInput").fill(questions[0])
        page.locator("#sendButton").click()
        page.wait_for_function("() => App.runRegistry.visible()?.status === 'succeeded'")
        expect(page.locator("#agentAnswer #agentAnswerWatchButton")).to_be_visible()
        page.locator("#questionInput").fill(questions[1])
        # The mocked answer lands at once; a second start within 450 ms is
        # dropped as a double click (run-registry.js claimStartAction).
        page.wait_for_function("() => !document.body.classList.contains('composer-gliding')")
        page.wait_for_timeout(500)
        page.locator("#sendButton").click()
        page.wait_for_function("q => App.runRegistry.visible()?.status === 'succeeded'"
                               " && App.runRegistry.visible().question === q", arg=questions[1])

        history_pill = page.locator("#threadHistory .agent-watch-pill")
        expect(history_pill).to_have_count(1)
        expect(page.locator("#agentAnswerWatchButton")).to_have_count(1)
        history_pill.click()
        expect(page.locator(".watch-question-preview strong")).to_have_text(questions[0])
        page.locator("#watchCancelBtn").click()

        # The chat reopened from the sidebar: its history and its answer
        # each have the pill of their own turn.
        page.evaluate("() => App.runRegistry.clearAll('test-reload')")
        page.locator(f'.bookmark[data-id="{bookmark["id"]}"]').click()
        expect(page.locator("#agentAnswerBody")).to_contain_text(questions[1])
        expect(page.locator("#threadHistory .agent-watch-pill")).to_have_count(1)
        live = page.locator("#agentAnswer #agentAnswerWatchButton")
        expect(live).to_be_visible()
        live.click()
        # A follow-up opens at the question, so it can stand alone.
        expect(page.locator("#watchQuestion")).to_have_value(questions[1])
        page.locator("#watchCancelBtn").click()
        page.locator("#threadHistory .agent-watch-pill").click()
        expect(page.locator(".watch-question-preview strong")).to_have_text(questions[0])
        assert not errors, errors
    finally:
        context.close()

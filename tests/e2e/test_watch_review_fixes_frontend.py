"""Watches after the second review of the Apple audit, in the built /app.

Writer-free like the other Phase-4 browser tests: every API answer comes from
the route handlers below. Measured per frame where the finding was a jump:
a card that is deleted folds away without first growing by its padding, and
a quick Undo brings it back for good. The new watch shows on the page however
the success step is closed.
"""
from datetime import datetime, timedelta, timezone

from playwright.sync_api import expect
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

"""A Watch the Agent prepared, in the built /app: card under the answer, Change, Start, End.

Since 2026-11-03 a Watch runs the Agent again in its chat (agent_watches.py).
Writer-free like the other Phase-4 browser tests: every API response comes
from the route handlers below. The server's rules (the task from the saved
turn, limits, intervals, runs) are covered in tests/test_agent_watch.py and
tests/test_agent_watches.py.
"""
import json
import os
from pathlib import Path

import pytest
from playwright.sync_api import expect
from test_agent_chat_frontend import CATALOG, _choose_mode
from test_phase4_frontend import phase4_server, _real_firebase_page, _json  # noqa: F401 (fixture)

TASK = "Check on ironman.com whether registration for IRONMAN Hamburg 2027 is open."
GOAL = "Registration is open"


def _shot(page, name):
    target = os.environ.get("AGENT_SCREENSHOTS")
    if target:
        Path(target).mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(Path(target) / f"{name}.png"))


@pytest.mark.parametrize("width,dark", [(1280, False), (390, True)])
def test_agent_watch_card_starts_the_prepared_watch_and_ends_it(browser, phase4_server, width, dark):
    context, page = _real_firebase_page(browser, phase4_server, has_touch=width < 700)
    errors, creates, stops = [], [], []
    page.on("pageerror", lambda error: errors.append(str(error)))
    chat_id, turn_id = "c" * 32, "1".rjust(32, "0")
    state = {"watches": []}
    proposal = {"task": TASK, "goal": GOAL, "interval": "daily", "run_time": "", "run_weekday": ""}

    def watches(route):
        request = route.request
        if request.method == "POST":
            body = request.post_data_json
            creates.append(body)
            watch = {"id": "w1", "chat_id": chat_id, "turn_id": body["turn_id"], "task": TASK, "goal": GOAL,
                     "status": "active", "interval": body["interval"], "run_time": body["run_time"],
                     "run_weekday": body["run_weekday"], "timezone": body["timezone"],
                     "next_run_at": "2030-01-02T07:00:00+00:00", "runs": 0, "last_run": None, "ended": ""}
            state["watches"] = [watch]
            return _json(route, {"watch": watch}, status=201)
        _json(route, {"watches": state["watches"], "intervals": ["daily", "weekly"],
                      "active_count": sum(1 for w in state["watches"] if w["status"] == "active"), "active_limit": 2})

    def stop(route):
        stops.append(route.request.url)
        state["watches"] = [{**watch, "status": "done", "ended": "user", "next_run_at": None} for watch in state["watches"]]
        _json(route, {"watch": state["watches"][0]})

    def answer(route):
        body = route.request.post_data_json
        text = "Registration for IRONMAN Hamburg 2027 is not open yet. Start the Watch below and I check every morning."
        turn = {"id": turn_id, "turn_id": turn_id, "question": body["question"], "status": "completed", "position": 1,
                "mode": "Agent", "execution_mode": "agent", "consensus": text, "differences": "",
                "differences_data": None, "model_answers": {}, "sources": [], "agent_watch": proposal,
                "agent_activity": [{"id": "s1:call_watch", "kind": "tool", "name": "prepare_watch", "status": "succeeded"}],
                "agent_settings": {"model_id": CATALOG["default_model_id"], "label": "DeepSeek V4.1 Flash"}}
        meta = {"id": body["bookmark_id"], "title": "IRONMAN Hamburg", "query": body["question"], "mode": "Agent",
                "has_consensus": True}
        stream = "event: delta\ndata: " + json.dumps({"text": text}) + "\n\n"
        stream += "event: final\ndata: " + json.dumps({"chat_id": chat_id, "turn_id": turn_id, "response": text,
                                                       "turn": turn, "bookmark_meta": meta}) + "\n\n"
        route.fulfill(content_type="text/event-stream", body=stream)

    try:
        page.set_viewport_size({"width": width, "height": 900})
        page.route("**/user_status", lambda route: _json(route, {"tier": "free", "is_pro": False, "agent_access": True,
                                                                 "limit": 500, "deep_limit": 50}))
        page.route("**/usage", lambda route: _json(route, {"tier": "free", "is_pro": False, "remaining": 10,
                                                           "deep_remaining": 1, "total_limit": 500, "deep_total_limit": 50}))
        page.route("**/api/my/watches", lambda route: _json(route, {"status": "success", "watches": [],
                                                                    "limits": {"plan": "free", "active_count": 0, "active_limit": 1}}))
        page.route("**/api/my/telegram", lambda route: _json(route, {"telegram": {"configured": False}}))
        page.route("**/agent/watches?*", watches)
        page.route("**/agent/watches", watches)
        page.route("**/agent/watches/w1/stop", stop)
        page.route("**/chats", lambda route: _json(route, {"chat": {"id": chat_id, "execution_mode": "agent"}}))
        page.route("**/agent/models", lambda route: _json(route, CATALOG))
        page.route("**/agent", answer)
        page.evaluate("async () => { await window.__switchE2EUser('account-a'); }")
        page.wait_for_function("() => document.getElementById('runModeControl').hidden === false")
        page.evaluate("dark => { document.documentElement.classList.toggle('dark-mode', dark); "
                      "document.body.classList.toggle('dark-mode', dark); }", dark)

        _choose_mode(page, "agent")
        page.locator("#questionInput").fill("Tell me when IRONMAN Hamburg registration opens.")
        page.locator("#sendButton").click()
        page.wait_for_function("() => App.runRegistry.visible()?.status === 'succeeded'")

        card = page.locator("#agentAnswer .agent-watch-card")
        expect(card).to_be_visible()
        expect(card).to_have_attribute("data-state", "proposal")
        expect(card.locator(".agent-watch-question")).to_have_text(TASK)
        expect(card.locator(".agent-watch-goal")).to_have_text("Done when: " + GOAL)
        expect(card.locator(".agent-watch-settings")).to_have_text("Daily at 08:00")
        # The card sits under the answer it is introduced by.
        answer_box = page.locator("#agentAnswerBody").bounding_box()
        card_box = card.bounding_box()
        assert answer_box and card_box and card_box["y"] >= answer_box["y"] + answer_box["height"] - 1
        assert card_box["x"] + card_box["width"] <= width + .5
        # Its own card replaces the generic "Watch this question" hint.
        expect(page.locator("#watchFeatureNudge")).to_have_count(0)
        _shot(page, f"agent-watch-card-{width}-{'dark' if dark else 'light'}")

        # Change: the account's intervals and a time.
        card.get_by_role("button", name="Change").click()
        expect(card.locator(".agent-watch-interval option")).to_have_count(2)
        card.locator(".agent-watch-time").fill("07:30")
        card.locator(".agent-watch-time").dispatch_event("change")
        _shot(page, f"agent-watch-change-{width}-{'dark' if dark else 'light'}")

        card.get_by_role("button", name="Start Watch").click()
        expect(card).to_have_attribute("data-state", "watching")
        expect(card.locator(".agent-watch-title")).to_have_text("Watch running")
        expect(card.locator(".agent-watch-settings")).to_contain_text("next run")
        assert len(creates) == 1
        created = creates[0]
        assert (created["chat_id"], created["turn_id"]) == (chat_id, turn_id)
        assert (created["interval"], created["run_time"]) == ("daily", "07:30") and "task" not in created
        _shot(page, f"agent-watch-started-{width}-{'dark' if dark else 'light'}")

        card.get_by_role("button", name="End Watch").click()
        expect(card).to_have_attribute("data-state", "ended")
        expect(card.locator(".agent-watch-title")).to_have_text("Watch ended")
        assert len(stops) == 1
        assert not errors, errors
    finally:
        context.close()

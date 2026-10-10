"""A Watch the Agent prepared, in the built /app: card under the answer, one-click start, Adjust.

Writer-free like the other Phase-4 browser tests: every API response comes
from the route handlers below. The tool's server rules (proposal only, no
Google data, status, schema) are covered in tests/test_agent_watch.py.
"""
import json
import os
from pathlib import Path

import pytest
from playwright.sync_api import expect
from test_agent_chat_frontend import CATALOG, _choose_mode
from test_phase4_frontend import phase4_server, _real_firebase_page, _json  # noqa: F401 (fixture)

QUESTION = "When will OpenAI release GPT-6 to the public?"
GOALS = ["GPT-6 is officially released", "OpenAI announces a release date"]


def _shot(page, name):
    target = os.environ.get("AGENT_SCREENSHOTS")
    if target:
        Path(target).mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(Path(target) / f"{name}.png"))


@pytest.mark.parametrize("width,dark", [(1280, False), (390, True)])
def test_agent_watch_card_starts_the_prepared_watch_and_adjust_opens_the_dialog(browser, phase4_server, width, dark):
    context, page = _real_firebase_page(browser, phase4_server, has_touch=width < 700)
    errors, creates, suggestions = [], [], []
    page.on("pageerror", lambda error: errors.append(str(error)))
    chat_id, turn_id = "c" * 32, "1".rjust(32, "0")
    state = {"watches": [], "limits": {"plan": "free", "active_count": 0, "active_limit": 3}}
    proposal = {"question": QUESTION, "goals": GOALS, "interval": "weekly"}

    def watches(route):
        _json(route, {"status": "success", "watches": state["watches"], "limits": state["limits"]})

    def create(route):
        body = route.request.post_data_json
        creates.append(body)
        watch = {"id": "w1", "status": "active", "question": body["question"], "condition": body["condition"],
                 "interval": body["interval"], "run_weekday": body["run_weekday"], "run_time": body["run_time"],
                 "timezone": body["timezone"], "share_path": "/s/watch1", "query_first": True}
        state["watches"] = [watch]
        state["limits"] = {**state["limits"], "active_count": 1}
        _json(route, {"status": "success", "watch": watch})

    def answer(route):
        body = route.request.post_data_json
        text = "GPT-6 has no announced release date yet. Start the Watch below to hear when it ships."
        turn = {"id": turn_id, "turn_id": turn_id, "question": body["question"], "status": "completed", "position": 1,
                "mode": "Agent", "execution_mode": "agent", "consensus": text, "differences": "",
                "differences_data": None, "model_answers": {}, "sources": [], "agent_watch": proposal,
                "agent_activity": [{"id": "s1:call_watch", "kind": "tool", "name": "prepare_watch", "status": "succeeded"}],
                "agent_settings": {"model_id": CATALOG["default_model_id"], "label": "DeepSeek V4.1 Flash"}}
        meta = {"id": body["bookmark_id"], "title": "GPT-6", "query": body["question"], "mode": "Agent", "has_consensus": True}
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
        page.route("**/api/my/watches", watches)
        page.route("**/api/watch", create)
        page.route("**/api/watch/goal-suggestions", lambda route: (suggestions.append(1), _json(route, {"goals": []})))
        page.route("**/api/my/telegram", lambda route: _json(route, {"telegram": {"configured": False}}))
        page.route("**/chats", lambda route: _json(route, {"chat": {"id": chat_id, "execution_mode": "agent"}}))
        page.route("**/agent/models", lambda route: _json(route, CATALOG))
        page.route("**/agent", answer)
        page.evaluate("async () => { await window.__switchE2EUser('account-a'); }")
        page.wait_for_function("() => document.getElementById('runModeControl').hidden === false")
        page.evaluate("dark => { document.documentElement.classList.toggle('dark-mode', dark); "
                      "document.body.classList.toggle('dark-mode', dark); }", dark)

        _choose_mode(page, "agent")
        page.locator("#questionInput").fill("Tell me when GPT-6 comes out.")
        page.locator("#sendButton").click()
        page.wait_for_function("() => App.runRegistry.visible()?.status === 'succeeded'")

        card = page.locator("#agentAnswer .agent-watch-card")
        expect(card).to_be_visible()
        expect(card).to_have_attribute("data-state", "proposal")
        expect(card.locator(".agent-watch-question")).to_have_text(QUESTION)
        expect(card.locator(".agent-watch-goal")).to_have_text("Waiting for: " + GOALS[0])
        expect(card.locator(".agent-watch-settings")).to_contain_text("09:00 · E-mail · Private")
        # The card sits under the answer it is introduced by.
        answer_box = page.locator("#agentAnswerBody").bounding_box()
        card_box = card.bounding_box()
        assert answer_box and card_box and card_box["y"] >= answer_box["y"] + answer_box["height"] - 1
        assert card_box["x"] + card_box["width"] <= width + .5
        # Its own card replaces the generic "Watch this question" hint.
        expect(page.locator("#watchFeatureNudge")).to_have_count(0)
        _shot(page, f"agent-watch-card-{width}-{'dark' if dark else 'light'}")

        # Adjust: the create dialog, prefilled with the Agent's goals, the
        # first one chosen, and no second goal suggestion call.
        card.get_by_role("button", name="Adjust").click()
        expect(page.locator(".watch-question-preview strong")).to_have_text(QUESTION)
        expect(page.locator("#watchGoalSuggestions label")).to_have_count(2)
        expect(page.locator("#watchGoalSuggestions input[type=radio]").first).to_be_checked()
        assert not suggestions
        _shot(page, f"agent-watch-adjust-{width}-{'dark' if dark else 'light'}")
        page.locator("#watchCancelBtn").click()

        card.get_by_role("button", name="Start watching").click()
        expect(card).to_have_attribute("data-state", "watching")
        expect(card.locator(".agent-watch-title")).to_have_text("Watching")
        expect(card.locator(".agent-watch-status")).to_contain_text("Checks weekly on")
        assert len(creates) == 1
        created = creates[0]
        assert created["question"] == QUESTION and created["condition"] == GOALS[0]
        assert created["visibility"] == "private" and created["interval"] == "weekly" and created["run_time"] == "09:00"
        _shot(page, f"agent-watch-started-{width}-{'dark' if dark else 'light'}")
        assert not errors, errors
    finally:
        context.close()

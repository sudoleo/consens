"""An answer written at a limit of its message says which limit, in the
app's words, and offers to go on (agent-review.js wrapUpNote, agent-chat.js
wrapUpNotice). Built /app with isolated HTTP fixtures; no paid calls.
"""
import json

import pytest
from playwright.sync_api import expect
from test_agent_chat_frontend import CATALOG, _choose_mode, _snapshot
from test_phase4_frontend import phase4_server, _real_firebase_page, _json  # noqa: F401  (fixture)

CHAT = "a" * 32
STEP_LIMIT = "This response reached its step limit."


def _routes(page, turns, bookmark, calls):
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
        calls.append(body)
        turn_id = str(len(calls)) * 32
        first = len(calls) == 1
        text = "Half of the importer is built: the parser reads the files." if first else "The importer is finished."
        turn = {"id": turn_id, "turn_id": turn_id, "question": body["question"], "status": "completed", "position": len(calls),
                "mode": "Agent", "execution_mode": "agent", "consensus": text, "differences": "", "model_answers": {},
                "sources": [], "agent_settings": {"model_id": body["model_id"], "label": "DeepSeek V4.1 Flash"},
                "agent_activity": [], "completed_at": "2026-11-09T20:00:00Z",
                **({"agent_wrap_up": {"reason": "steps", "steps": 24, "seconds": 310.2}} if first else {})}
        turns.append(turn)
        bookmark.update(id=body["bookmark_id"], query=body["question"], title=body["question"], mode="Agent",
                        execution_mode="agent", chat_id=CHAT, turn_id=turn_id,
                        responses={"consensus": text, "differences": ""}, sources=[])
        meta = {"id": body["bookmark_id"], "title": body["question"], "query": body["question"], "mode": "Agent",
                "has_consensus": True}
        final = {"chat_id": CHAT, "turn_id": turn_id, "response": text, "turn": turn, "bookmark_meta": meta}
        route.fulfill(content_type="text/event-stream", body="event: delta\ndata: " + json.dumps({"text": text}) + "\n\n"
                      + "event: final\ndata: " + json.dumps(final) + "\n\n")

    page.route("**/agent", answer)


@pytest.mark.parametrize("width,dark", [(1280, False), (390, True)])
def test_an_answer_at_its_step_limit_says_so_and_continues(browser, phase4_server, width, dark):
    context, page = _real_firebase_page(browser, phase4_server, has_touch=width < 700)
    errors, calls, turns, bookmark = [], [], [], {}
    page.on("pageerror", lambda error: errors.append(str(error)))
    try:
        page.set_viewport_size({"width": width, "height": 900})
        _routes(page, turns, bookmark, calls)
        page.evaluate("async () => { await window.__switchE2EUser('account-a'); }")
        page.evaluate("dark => { document.documentElement.classList.toggle('dark-mode', dark); document.body.classList.toggle('dark-mode', dark); }", dark)
        _choose_mode(page, "agent")
        page.locator("#questionInput").fill("Build the importer")
        page.locator("#sendButton").click()
        page.wait_for_function("() => App.runRegistry.visible()?.status === 'succeeded'")
        note = page.locator("#agentAnswerError")
        expect(note).to_be_visible()
        expect(note).to_have_text(STEP_LIMIT)
        # Said, not announced: a limit is no failure.
        expect(note).to_have_attribute("role", "status")
        resume = page.locator("#agentAnswerErrorActions button[data-action='continue']")
        expect(resume).to_be_visible()
        expect(resume).to_have_text("Continue")
        note.scroll_into_view_if_needed()
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")
        _snapshot(page, f"agent-limit-notice-{width}")
        # Two sends within 450 ms count as one gesture (run-registry.js claimStartAction).
        page.wait_for_timeout(500)
        resume.click()
        page.wait_for_function("() => App.runRegistry.visible()?.question === 'Continue.'")
        page.wait_for_function("() => App.runRegistry.visible()?.status === 'succeeded'")
        assert [call["question"] for call in calls] == ["Build the importer", "Continue."]
        assert calls[1]["chat_id"] == calls[0]["chat_id"] and not calls[1]["recover_only"]
        # The first turn keeps its sentence in the history, without the button;
        # the answer that finished by itself has neither.
        history = page.locator("#threadHistory")
        expect(history).to_contain_text(STEP_LIMIT)
        expect(history.locator("button[data-action='continue']")).to_have_count(0)
        expect(page.locator("#agentAnswerError")).not_to_be_visible()
        expect(page.locator("#agentAnswerErrorActions button")).to_have_count(0)
        _snapshot(page, f"agent-limit-notice-continued-{width}")
        assert not errors
    finally:
        context.close()

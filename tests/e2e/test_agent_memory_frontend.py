"""Agent-managed memory in the built /app: opt-in, note under the answer, Undo, Settings list.

Writer-free like the other Phase-4 browser tests: every API response comes
from the route handlers below. Server rules (evidence, opt-in fence, secrets)
are covered in tests/test_agent_memory.py.
"""
import json
import os
from pathlib import Path

import pytest
from playwright.sync_api import expect
from test_agent_chat_frontend import CATALOG, _choose_mode
from test_phase4_frontend import phase4_server, _real_firebase_page, _json  # noqa: F401 (fixture)

CHANGE_ID = "0123456789abcdef"


def _shot(page, name):
    target = os.environ.get("AGENT_SCREENSHOTS")
    if target:
        Path(target).mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(Path(target) / f"{name}.png"))


@pytest.mark.parametrize("width,dark", [(1280, False), (390, True)])
def test_agent_memory_opt_in_note_undo_and_settings_list(browser, phase4_server, width, dark):
    context, page = _real_firebase_page(browser, phase4_server, has_touch=width < 700)
    errors, puts, undos, item_posts = [], [], [], []
    page.on("pageerror", lambda error: errors.append(str(error)))
    chat_id, turn_id = "b" * 32, "1".rjust(32, "0")
    state = {"profile": {"schema_version": 2, "enabled": True, "auto_memory": False, "role": "", "focus": "",
                         "style": "", "constraints": "", "notes": ""},
             "revision": 2, "items": [], "items_revision": 4}

    def listing():
        return {"items": state["items"], "items_revision": state["items_revision"],
                "limits": {"items": 100, "item_chars": 300, "notes_chars": 12000}}

    def memory(route):
        if route.request.method == "PUT":
            body = route.request.post_data_json
            puts.append(body)
            state["profile"] = {"schema_version": 2, **{k: v for k, v in body.items() if k != "expected_revision"}}
            state["revision"] += 1
        _json(route, {"status": "success", "memory": state["profile"], "revision": state["revision"], **listing()})

    def items(route):
        body = route.request.post_data_json
        item_posts.append(body)
        for change in body["changes"]:
            if change["op"] == "add":
                state["items"].append({"id": "m9f8e7d", "text": change["text"], "origin": "user",
                                       "created_at": "2026-10-04T10:00:00+00:00", "updated_at": "2026-10-04T10:00:00+00:00"})
        state["items_revision"] += 1
        _json(route, {"status": "success", **listing()})

    def undo(route):
        undos.append(route.request.url)
        state["items"] = []
        state["items_revision"] += 1
        _json(route, {"status": "success", "result": "undone", **listing()})

    def answer(route):
        body = route.request.post_data_json
        fact = body["question"].split(":", 1)[1].strip()
        state["items"].append({"id": "m1a2b3c", "text": fact, "origin": "agent",
                               "created_at": "2026-10-04T10:00:00+00:00", "updated_at": "2026-10-04T10:00:00+00:00"})
        state["items_revision"] += 1
        change = {"change_id": CHANGE_ID, "op": "add", "item_id": "m1a2b3c", "text": fact, "undone": False}
        text = "Got it, I'll keep that in mind."
        turn = {"id": turn_id, "turn_id": turn_id, "question": body["question"], "status": "completed", "position": 1,
                "mode": "Agent", "execution_mode": "agent", "consensus": text, "differences": "",
                "differences_data": None, "model_answers": {}, "sources": [], "agent_memory": [change],
                "agent_settings": {"model_id": CATALOG["default_model_id"], "label": "DeepSeek V4.1 Flash"}}
        meta = {"id": body["bookmark_id"], "title": "Memory", "query": body["question"], "mode": "Agent", "has_consensus": True}
        stream = "event: memory\ndata: " + json.dumps({"changes": [change]}) + "\n\n"
        stream += "event: delta\ndata: " + json.dumps({"text": text}) + "\n\n"
        stream += "event: final\ndata: " + json.dumps({"chat_id": chat_id, "turn_id": turn_id, "response": text,
                                                       "turn": turn, "bookmark_meta": meta}) + "\n\n"
        route.fulfill(content_type="text/event-stream", body=stream)

    try:
        page.set_viewport_size({"width": width, "height": 900})
        page.route("**/user_status", lambda route: _json(route, {"tier": "pro", "is_pro": True, "agent_access": True,
                                                                 "limit": 500, "deep_limit": 50}))
        page.route("**/usage", lambda route: _json(route, {"tier": "pro", "is_pro": True, "remaining": 10,
                                                           "deep_remaining": 1, "total_limit": 500, "deep_total_limit": 50}))
        page.route("**/api/my/memory", memory)
        page.route("**/api/my/memory/items", items)
        page.route(f"**/api/my/memory/changes/{CHANGE_ID}/undo", undo)
        page.route("**/chats", lambda route: _json(route, {"chat": {"id": chat_id, "execution_mode": "agent"}}))
        page.route("**/agent/models", lambda route: _json(route, CATALOG))
        page.route("**/agent", answer)
        page.evaluate("async () => { await window.__switchE2EUser('account-a'); }")
        page.wait_for_function("() => document.getElementById('runModeControl').hidden === false")
        page.evaluate("dark => { document.documentElement.classList.toggle('dark-mode', dark); "
                      "document.body.classList.toggle('dark-mode', dark); }", dark)

        # Opt in: the switch saves only itself.
        page.evaluate("() => document.getElementById('editSystemPromptBtn').click()")
        auto = page.locator("#memoryAutoSwitch")
        expect(auto).not_to_be_checked()
        expect(page.locator("#memoryItemsEmpty")).to_be_visible()
        page.locator("label[for='memoryAutoSwitch']").click()
        expect(page.locator("#memoryStatus")).to_contain_text("Agent can now update your memory")
        assert puts[-1]["auto_memory"] is True and puts[-1]["expected_revision"] == 2
        _shot(page, f"memory-settings-{width}-{'dark' if dark else 'light'}")
        page.click("#closeSystemPromptModal")

        _choose_mode(page, "agent")
        expect(page.locator("#agentModelDropdown")).to_be_enabled()
        page.locator("#questionInput").fill("Remember: I prefer metric units.")
        page.locator("#sendButton").click()
        page.wait_for_function("() => App.runRegistry.visible()?.status === 'succeeded'")
        # The note is a working-phase hint; the final answer carries none.
        expect(page.locator("#agentAnswer .agent-memory-note")).to_have_count(0)

        page.evaluate("() => document.getElementById('editSystemPromptBtn').click()")
        expect(page.locator("#systemPromptModal")).to_be_visible()
        expect(page.locator("#memoryItemsList")).to_contain_text("I prefer metric units.")
        page.locator("#memoryItemInput").fill("Works night shifts.")
        page.locator("#memoryItemAddBtn").click()
        expect(page.locator("#memoryItemsList")).to_contain_text("Works night shifts.")
        expect(page.locator("#memoryItemsList")).to_contain_text("Added by you")
        assert item_posts[-1] == {"changes": [{"op": "add", "text": "Works night shifts."}],
                                  "expected_revision": state["items_revision"] - 1}
        _shot(page, f"memory-list-{width}-{'dark' if dark else 'light'}")
        assert not errors
    finally:
        context.close()

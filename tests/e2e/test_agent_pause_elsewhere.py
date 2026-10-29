"""A second tab opens a chat whose newest turn runs, paused for the user
(A-B2, docs/agent-audit-readiness-2026-10-29.md): it follows the turn by its
request identity and shows the pause card, without a provider and without
sending anything.
"""
from playwright.sync_api import expect
from test_phase4_frontend import phase4_server, _real_firebase_page, _json  # noqa: F401  (fixture)
from test_agent_chat_frontend import CATALOG

CHAT, DONE, RUNNING = "c" * 32, "d" * 32, "e" * 32


def test_a_second_tab_follows_a_paused_turn_and_shows_its_card(browser, phase4_server):
    context, page = _real_firebase_page(browser, phase4_server)
    errors, asked, sent, live = [], [], [], []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.on("request", lambda request: live.append(request.url) if "/live?" in request.url else None)
    try:
        page.route("**/user_status", lambda r: _json(r, {"tier": "pro", "is_pro": True, "agent_access": True,
                                                         "audit_access": True, "limit": 500}))
        page.route("**/agent/models", lambda r: _json(r, {**CATALOG, "token_budget": {"remaining": 188878, "limit": 250000}}))
        page.route("**/agent/budget", lambda r: _json(r, {"token_budget": {"limit": 250000, "used": 1000, "remaining": 249000}}))
        done = {"id": DONE, "question": "Find the cheapest train to Munich.", "status": "completed", "position": 1,
                "execution_mode": "agent", "mode": "Agent", "consensus": "The 7:12 train costs 29 euros.",
                "agent_settings": {"model_id": CATALOG["default_model_id"], "label": "DeepSeek V4.1 Flash"}}
        running = {"id": RUNNING, "question": "Book it for Friday.", "client_request_id": "req-other-tab", "position": 2,
                   "attachments": [], "agent_settings": {
                       "selection": {"model_id": CATALOG["default_model_id"], "reasoning_effort": "default"},
                       "comparison_selection": {"openai": "gpt-5.4-mini"},
                       "agent_preferences": {"depth": "auto", "quorum": "all", "autonomy": "guided", "judges": "on",
                                             "audit": "on", "vm": "off"},
                       "file_ids": [], "google_selection": None, "google_data_consent": False}}
        bookmark = {"id": "b_elsewhere", "chat_id": CHAT, "turn_id": DONE, "mode": "Agent", "execution_mode": "agent",
                    "title": done["question"], "query": done["question"], "responses": {"consensus": done["consensus"]}}
        page.route("**/bookmarks/b_elsewhere/conversation*", lambda r: _json(r, {
            "chat_id": CHAT, "turns": [done], "running": running, "has_more": False}))
        page.route("**/bookmarks/b_elsewhere", lambda r: _json(r, {"bookmark": bookmark}))

        def agent(route):
            body = route.request.post_data_json
            (asked if body.get("recover_only") else sent).append(body)
            _json(route, {"error": "This request is still running.", "code": "request_running",
                          "recoverable": True, "recovery_state": "running"}, status=409)
        page.route("**/agent", agent)
        hold = {"id": "a1b2c3d4e5f6", "reviewer": "GPT-6 Luna", "kind": "safety", "entry": 6,
                "reason": "The booking would charge the saved card without asking.",
                "step": "browser click: Pay now", "step_kind": "step", "timeout_seconds": 1800,
                "at": "2099-01-01T00:00:00+00:00"}
        page.route("**/agent/chats/*/live*", lambda r: _json(r, {"known": True, "done": False, "more": False, "last_seq": 2,
                                                                "events": [
            {"seq": 1, "type": "accepted", "data": {"chat_id": CHAT, "turn_id": RUNNING}},
            {"seq": 2, "type": "hold", "data": {"hold": hold}}]}))
        page.evaluate("async () => { await window.__switchE2EUser('account-a'); }")
        page.evaluate("async () => { await window.openBookmark('b_elsewhere'); }")
        card = page.locator("#agentHold .agent-hold-card")
        expect(card).to_be_visible()
        expect(card.locator(".agent-hold-title")).to_have_text("A reviewer paused the work")
        expect(card.locator(".agent-hold-reason")).to_have_text(hold["reason"])
        # Followed by its own identity: polled, never sent again.
        assert live and "request_id=req-other-tab" in live[0]
        assert asked and asked[0]["client_request_id"] == "req-other-tab" and not sent
        assert asked[0]["comparison_models"] == {"openai": "gpt-5.4-mini"}
        # The chat's earlier turn stays above the running one.
        expect(page.locator("#threadHistory")).to_contain_text(done["question"])
        assert not errors
    finally:
        context.close()

"""A settings change the Agent prepared, in the built /app: card, one-click Apply, the next message.

Writer-free like the other Phase-4 browser tests: every API response comes
from the route handlers below. The tool's server rules (tier, reasoning
levels, schema, proposal only) are covered in tests/test_agent_settings.py.
"""
import json
import os
from pathlib import Path

import pytest
from playwright.sync_api import expect
from test_agent_chat_frontend import CATALOG, _choose_mode
from test_phase4_frontend import phase4_server, _real_firebase_page, _json, _route_account_settings  # noqa: F401 (fixture)

NOTE = "DeepSeek V4.1 Flash offers Low (High, Max on Pro); Low is the closest."
PROPOSAL = {"settings": {"agent_model": {"model_id": CATALOG["default_model_id"], "reasoning_effort": "low"},
                         "agent_preferences": {"depth": "quick", "judges": "off"}, "consensus_preset": "balanced",
                         "claim_counts": True},
            "notes": {"agent_model": NOTE}}


def _shot(page, name):
    target = os.environ.get("AGENT_SCREENSHOTS")
    if target:
        Path(target).mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(Path(target) / f"{name}.png"))


@pytest.mark.parametrize("width,dark", [(1280, False), (390, True)])
def test_agent_settings_card_applies_the_change_and_the_next_message_carries_it(browser, phase4_server, width, dark):
    context, page = _real_firebase_page(browser, phase4_server, has_touch=width < 700)
    account = _route_account_settings(page)
    errors, requests = [], []
    page.on("pageerror", lambda error: errors.append(str(error)))
    chat_id = "c" * 32

    def answer(route):
        body = route.request.post_data_json
        requests.append(body)
        turn_id = str(len(requests)).rjust(32, "0")
        first = len(requests) == 1
        text = ("Low is the closest level for your account; apply it with the card below."
                if first else "A brief answer.")
        # The second message ran with the answer check off: its comparison is
        # bound to the answer, nothing judged (agent_comparison.skip_review).
        review = None if first else {
            "version": 1, "status": "off", "answer_hash": "h", "answer_version": 1,
            "versions": [{"id": 1, "text": text, "hash": "h", "status": "off"}],
            "comparisons": [{"id": "c1", "basis_hash": "b1", "question": "What does it cost?", "status": "succeeded",
                             "answers": [{"provider": p, "provider_label": label, "model": {"label": label},
                                          "text": "It costs 100.", "sources": []}
                                         for p, label in (("openai", "GPT"), ("anthropic", "Claude"))]}],
            "checks": [{"comparison_id": "c1", "basis_hash": "b1", "answer_hash": "h", "status": "off",
                        "differences_data": None}]}
        turn = {"id": turn_id, "turn_id": turn_id, "question": body["question"], "status": "completed",
                "position": len(requests), "mode": "Agent", "execution_mode": "agent", "consensus": text,
                "differences": "", "differences_data": None, "model_answers": {}, "sources": [],
                "agent_activity": [{"id": "s1:call_settings", "kind": "tool", "name": "prepare_settings_change",
                                    "status": "succeeded"}] if first else [],
                "agent_settings": {"model_id": body["model_id"], "reasoning_effort": body["reasoning_effort"],
                                   "label": "DeepSeek V4.1 Flash"},
                **({"agent_settings_proposal": PROPOSAL} if first else {"agent_review": review})}
        meta = {"id": body["bookmark_id"], "title": "Settings", "query": body["question"], "mode": "Agent",
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
                                                                    "limits": {"plan": "free", "active_count": 0, "active_limit": 3}}))
        page.route("**/chats", lambda route: _json(route, {"chat": {"id": chat_id, "execution_mode": "agent"}}))
        page.route("**/agent/models", lambda route: _json(route, CATALOG))
        page.route("**/agent", answer)
        page.evaluate("async () => { await window.__switchE2EUser('account-a'); }")
        page.wait_for_function("() => document.getElementById('runModeControl').hidden === false")
        page.evaluate("dark => { document.documentElement.classList.toggle('dark-mode', dark); "
                      "document.body.classList.toggle('dark-mode', dark); }", dark)

        _choose_mode(page, "agent")
        page.locator("#questionInput").fill("Denk ab jetzt etwas weniger und antworte kurz, mit Zählern.")
        page.locator("#sendButton").click()
        page.wait_for_function("() => App.runRegistry.visible()?.status === 'succeeded'")

        card = page.locator("#agentAnswer .agent-settings-card")
        expect(card).to_be_visible()
        expect(card).to_have_attribute("data-state", "proposal")
        expect(card.locator("dt")).to_have_text(["Reasoning", "Answer depth", "Answer check", "Comparison models",
                                                 "Inline claim counts"])
        expect(card.locator("dd")).to_have_text(["Auto → Low", "Automatic → Always brief", "On → Off",
                                                 "Daily → Open Models", "Off → On"])
        expect(card.locator(".agent-settings-note")).to_have_text(NOTE)
        # The card sits under the answer it is introduced by and fits the screen.
        answer_box = page.locator("#agentAnswerBody").bounding_box()
        card_box = card.bounding_box()
        assert answer_box and card_box and card_box["y"] >= answer_box["y"] + answer_box["height"] - 1
        assert card_box["x"] + card_box["width"] <= width + .5
        _shot(page, f"agent-settings-card-{width}-{'dark' if dark else 'light'}")

        card.get_by_role("button", name="Apply").click()
        expect(card).to_have_attribute("data-state", "applied")
        expect(card.locator(".agent-settings-status")).to_have_text("Applied. These settings apply from your next message.")
        # Every owner shows it at once: the picker, Settings and the answer display.
        assert page.evaluate("() => App.agentChat.pick()") == {"model_id": CATALOG["default_model_id"],
                                                               "reasoning_effort": "low"}
        expect(page.locator("#agentDepthSelect")).to_have_value("quick")
        expect(page.locator("#agentJudgesSelect")).to_have_value("off")
        expect(page.locator("#claimCountsSwitch")).to_be_checked()
        page.wait_for_function("() => document.body.classList.contains('claim-counts-visible')")
        # Saved to the account, in the form the real route takes.
        page.evaluate("async () => { await App.userSettings.flush(); }")
        assert account["rejected"] == []
        assert account["settings"]["agent_model"] == {"model_id": CATALOG["default_model_id"], "reasoning_effort": "low"}
        assert account["settings"]["agent_preferences"] == {"depth": "quick", "judges": "off"}
        assert account["settings"]["claim_counts"] is True
        assert account["settings"]["consensus_preset"] == "balanced"
        # The model picker took the lineup at once, as from the account.
        assert page.evaluate("() => App.activeConsensusPresetId()") == "balanced"
        open_models = page.evaluate("() => window.CONSENSUS_PRESETS.find(preset => preset.id === 'balanced').models")
        _shot(page, f"agent-settings-applied-{width}-{'dark' if dark else 'light'}")

        # The next message of this chat runs with what the card applied.
        page.locator("#questionInput").fill("Und was kostet das?")
        page.locator("#sendButton").click()
        page.wait_for_function("() => App.runRegistry.visible()?.status === 'succeeded' && "
                               "document.querySelector('#agentAnswerBody')?.textContent.includes('A brief answer')")
        assert len(requests) == 2
        assert requests[1]["reasoning_effort"] == "low"
        assert requests[1]["agent_preferences"]["depth"] == "quick"
        assert requests[0]["agent_preferences"]["judges"] == "on" and requests[1]["agent_preferences"]["judges"] == "off"
        # No line under the answer (the reader switched the check off), no
        # review link, and no "Sources 0": only the model answers.
        status = page.locator("#agentAnswer .agent-review-status")
        expect(status).to_have_attribute("data-state", "off")
        expect(status).to_be_hidden()
        expect(page.locator("#agentAnswer .agent-review [data-section]")).to_have_count(1)
        expect(page.locator('#agentAnswer .agent-review [data-section="answers"]')).to_be_visible()
        expect(page.locator("#agentAnswer .agent-agreement")).to_have_count(0)
        _shot(page, f"agent-answer-check-off-{width}-{'dark' if dark else 'light'}")
        assert requests[1]["comparison_models"] == open_models != requests[0]["comparison_models"]
        # A turn without a proposal has no card.
        expect(page.locator("#agentAnswer .agent-settings-card")).to_have_count(0)
        assert not errors, errors
    finally:
        context.close()

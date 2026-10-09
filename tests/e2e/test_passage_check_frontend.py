"""A pasted AI answer the Agent checked: marks on the user's message, built frontend, no providers."""
import hashlib
import json

import pytest
from playwright.sync_api import expect
from test_phase4_frontend import phase4_server, _real_firebase_page, _json  # noqa: F401  (fixture)
from test_agent_chat_frontend import CATALOG, _choose_mode, _snapshot


CHAT, TURN = "a" * 32, "b" * 32
PASTED = ("Heat pumps work in old buildings when the flow temperature stays below 55 degrees.\n\n"
          "- You always need **underfloor heating** for that.\n"
          "- The state pays up to 70 percent of the costs.")
QUESTION = "Is this right?\n\n" + PASTED
ANSWER = "Mostly, but not the underfloor heating: larger radiators are often enough."
MODELS = [("openai", "OpenAI", "openai/gpt-5.4-mini", "GPT-5.4 Mini"),
          ("deepseek", "DeepSeek", "deepseek/deepseek-v4-flash", "DeepSeek V4 Flash"),
          ("gemini", "Gemini", "google/gemini-3.5-flash-lite", "Gemini 3.5 Flash-Lite")]


def _claim(sentence, agree, dissent=()):
    start = PASTED.index(sentence)
    return {"anchor": sentence, "start": start, "end": start + len(sentence), "agree": list(agree),
            "dissent": [{"model": m, "quote": "Larger radiators are often enough."} for m in dissent],
            "coverage": "split" if dissent else "supported" if len(agree) >= 2 else "thin"}


def _review(status="succeeded"):
    digest = hashlib.sha256(ANSWER.encode()).hexdigest()
    answers = [{"provider": p, "provider_label": label, "model": {"model": model, "label": name},
                "text": "Heat pumps work with low flow temperatures. Larger radiators are often enough.", "sources": []}
               for p, label, model, name in MODELS]
    passage = {"version": 1, "status": status, "comparison_id": "c1", "text": PASTED, "hash": "h",
               "answer_to": "Do heat pumps make sense in old buildings?"}
    if status == "succeeded":
        passage.update(models_compared=[m[1] for m in MODELS], issues=[], claims=[
            _claim("Heat pumps work in old buildings when the flow temperature stays below 55 degrees.",
                   ["OpenAI", "DeepSeek", "Gemini"]),
            _claim("You always need **underfloor heating** for that.", ["Gemini"], ["OpenAI", "DeepSeek"]),
            _claim("The state pays up to 70 percent of the costs.", ["OpenAI"])])
    review = {"status": "succeeded" if status == "succeeded" else "required", "answer_version": 1 if status == "succeeded" else 0,
              "answer_hash": digest, "passage_check": passage,
              "versions": [{"id": 1, "text": ANSWER, "hash": digest, "status": "succeeded"}] if status == "succeeded" else [],
              "comparisons": [{"id": "c1", "basis_hash": "basis", "question": "Do heat pumps make sense in old buildings?",
                               "reason": "Check the pasted answer", "context": "", "status": "succeeded", "answers": answers}]}
    if status == "succeeded":
        review["checks"] = [{"comparison_id": "c1", "basis_hash": "basis", "answer_hash": digest, "status": "succeeded",
                             "differences_data": {"claims": [], "differences": [], "models_compared": [m[1] for m in MODELS]}}]
    return review


SAVED = {"id": TURN, "turn_id": TURN, "question": QUESTION, "status": "completed", "execution_mode": "agent", "mode": "Agent",
         "consensus": ANSWER, "sources": [], "model_answers": {}, "agent_review": _review(),
         "agent_settings": {"model_id": "claude-haiku-4-5", "label": "Claude Haiku 4.5"}}


def _setup(page, requests):
    page.route("**/user_status", lambda r: _json(r, {"tier": "pro", "is_pro": True, "agent_access": True, "limit": 500}))
    page.route("**/usage", lambda r: _json(r, {"tier": "pro", "is_pro": True, "remaining": 0, "total_limit": 500}))
    page.route("**/api/my/memory", lambda r: _json(r, {"memory": {"content": "", "revision": 0}}))
    page.route("**/chats", lambda r: _json(r, {"chat": {"id": CHAT, "execution_mode": "agent"}}))
    page.route("**/agent/models", lambda r: _json(r, CATALOG))

    def respond(route):
        body = route.request.post_data_json
        requests.append(body)
        final = {"chat_id": CHAT, "turn_id": TURN, "response": ANSWER, "turn": SAVED,
                 "bookmark_meta": {"id": body["bookmark_id"], "title": "Heat pumps", "query": QUESTION, "mode": "Agent",
                                   "has_consensus": True}}
        events = [("started", {"chat_id": CHAT, "turn_id": TURN}), ("review", {"review": _review("waiting")}),
                  ("delta", {"text": ANSWER}), ("review", {"review": SAVED["agent_review"]}), ("final", final)]
        route.fulfill(content_type="text/event-stream",
                      body="".join(f"event: {name}\ndata: {json.dumps(data)}\n\n" for name, data in events))
    page.route("**/agent", respond)


@pytest.mark.parametrize("width,dark", [(1280, False), (390, True)])
def test_pasted_answer_is_marked_on_the_message(browser, phase4_server, width, dark):
    context, page = _real_firebase_page(browser, phase4_server, has_touch=width < 700)
    requests, errors = [], []
    page.on("pageerror", lambda error: errors.append(str(error)))
    try:
        page.set_viewport_size({"width": width, "height": 960})
        _setup(page, requests)
        page.evaluate("async () => { await window.__switchE2EUser('account-a'); }")
        _choose_mode(page, "agent")
        page.evaluate("dark => { document.documentElement.classList.toggle('dark-mode', dark); document.body.classList.toggle('dark-mode', dark); }", dark)
        # The only hint at the feature: the placeholder of a new chat.
        expected = "Ask, or paste an AI answer to check" if width <= 640 else "Ask anything, or paste an AI answer to check it"
        expect(page.locator("#questionInput")).to_have_attribute("placeholder", expected)

        page.locator("#questionInput").fill(QUESTION)
        page.locator("#sendButton").click()
        page.wait_for_function("() => App.runRegistry.visible()?.status === 'succeeded'")
        assert requests[0]["question"] == QUESTION

        ask = page.locator("#threadAsk")
        marks = ask.locator(".pc-claim")
        expect(marks).to_have_count(3)
        assert marks.evaluate_all("els => els.map(el => el.dataset.verdict)") == ["holds", "disputed", "unconfirmed"]
        expect(marks.nth(1)).to_have_text("You always need underfloor heating for that.")
        # The pasted list keeps its lines; the bubble does not collapse them.
        assert ask.locator("#threadAskText").evaluate("el => getComputedStyle(el).whiteSpace") == "pre-line"
        assert marks.nth(1).evaluate("el => getComputedStyle(el).backgroundColor") != "rgba(0, 0, 0, 0)"
        summary = ask.locator(".passage-check")
        expect(summary).to_contain_text("Checked against 3 models as an answer to “Do heat pumps make sense in old buildings?”")
        expect(summary).to_contain_text("The models answered without seeing your text.")
        # On a phone the counts wrap as whole units, never as a lone dot.
        units = summary.locator(".passage-check-unit")
        assert units.evaluate_all("els => els.every(el => el.getClientRects().length === 1)")
        expect(summary.locator("button.passage-check-count")).to_have_count(3)
        _snapshot(page, f"passage-check-{width}")

        # A count jumps to its first sentence and opens the same card as a
        # checked answer sentence, with a way to the model's own answer.
        summary.locator('[data-verdict="disputed"]').click()
        popover = page.locator("#claimPopover")
        expect(popover).to_be_visible()
        expect(popover).to_contain_text("Deviate")
        expect(popover).to_contain_text("Larger radiators are often enough.")
        _snapshot(page, f"passage-check-popover-{width}")
        page.keyboard.press("Escape")
        expect(popover).to_be_hidden()
        marks.nth(1).click()
        expect(popover).to_be_visible()
        popover.get_by_role("button", name="View answer").first.click()
        expect(page.locator(".answer-reader-dialog, .answer-reader")).to_be_visible()
        page.keyboard.press("Escape")

        # Restoring the saved chat (bookmark path) keeps the marks, even when
        # the thread question is set again afterwards.
        page.evaluate("""turn => {
            App.runRegistry.showSavedView({type: 'bookmark'}, {chatId: 'a'.repeat(32), turnId: turn.id, executionMode: 'agent',
                question: turn.question, consensus: turn.consensus, currentTurn: turn});
            App.setThreadQuestion(turn.question);
        }""", SAVED)
        expect(ask.locator(".pc-claim")).to_have_count(3)
        # As an earlier turn of the chat, the message keeps its marks too.
        page.evaluate("turn => App.followup.renderStoredTurns([turn])", SAVED)
        history = page.locator("#threadHistory .thread-history-question")
        expect(history.locator(".pc-claim")).to_have_count(3)
        expect(history.locator(".passage-check")).to_contain_text("1 disputed")
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        assert errors == []
    finally:
        context.close()


def test_overlong_agent_message_is_stopped_with_a_clear_reason(browser, phase4_server):
    context, page = _real_firebase_page(browser, phase4_server)
    requests, dialogs = [], []
    try:
        _setup(page, requests)
        page.on("dialog", lambda dialog: (dialogs.append(dialog.message), dialog.dismiss()))
        page.evaluate("async () => { await window.__switchE2EUser('account-a'); }")
        _choose_mode(page, "agent")
        # 600 words pass in Agent (it counts characters, like its server) ...
        page.locator("#questionInput").fill("word " * 600)
        assert page.evaluate("validateInputText()") is True
        # ... 8,001 characters do not.
        page.locator("#questionInput").fill("x" * 8001)
        page.locator("#sendButton").click()
        page.wait_for_timeout(300)
        # Exactly one notice: the click and the send path no longer both check.
        assert len(dialogs) == 1 and "longer than 8,000 characters (it has 8,001)" in dialogs[0]
        assert requests == []
        expect(page.locator("#questionInput")).to_have_value("x" * 8001)
    finally:
        context.close()

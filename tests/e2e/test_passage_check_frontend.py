"""A pasted AI answer the Agent checked: a result card above the answer, built frontend, no providers."""
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
                             # The answer's own statement, judged like any answer's.
                             "differences_data": {"claims": [{"anchor": ANSWER, "agree": ["OpenAI"], "coverage": "split",
                                                              "dissent": [{"model": "Gemini", "quote": "Underfloor heating is needed."}]}],
                                                  "differences": [], "models_compared": [m[1] for m in MODELS]}}]
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


# A colour-mix comes back as color(srgb 0..1), a plain colour as rgb(0..255).
# The ink itself is a slightly cool grey (34/36/40); the agree green is 20+ apart.
GREY = r"""el => { const value = getComputedStyle(el).backgroundColor;
    const scale = value.startsWith('color(') ? 255 : 1;
    const [r, g, b] = value.match(/[\d.]+/g).slice(0, 3).map(n => Number(n) * scale);
    return Math.max(r, g, b) - Math.min(r, g, b) <= 10; }"""


@pytest.mark.parametrize("width,dark", [(1280, False), (390, True)])
def test_pasted_answer_check_is_a_card_above_the_answer(browser, phase4_server, width, dark):
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

        # The message stays as it was sent: plain text with its paragraphs, no marks.
        ask = page.locator("#threadAsk")
        expect(ask.locator(".pc-claim")).to_have_count(0)
        expect(ask.locator(".passage-check")).to_have_count(0)
        assert ask.locator("#threadAskText").evaluate("el => getComputedStyle(el).whiteSpace") == "pre-wrap"
        expect(ask.locator("#threadAskMore")).to_have_text("Show more")

        # The result is one card right above the answer.
        card = page.locator("#agentAnswer > .passage-check")
        expect(card).to_be_visible()
        assert card.evaluate("el => el.nextElementSibling.id") == "agentAnswerBody"
        # The result as one sentence, its number in the verdict colour; no label above it.
        headline = card.locator(".passage-check-headline")
        expect(headline).to_have_text("Models disagree with 1 of 3 statements in your text")
        figure = headline.locator(".passage-check-figure")
        assert figure.evaluate("el => getComputedStyle(el).color") != headline.evaluate("el => getComputedStyle(el).color")
        expect(card.locator(".passage-check-strip i")).to_have_count(3)
        # No box around it: no surface, no border; the text sits on a rail.
        assert card.evaluate("el => getComputedStyle(el).backgroundColor") == "rgba(0, 0, 0, 0)"
        assert card.evaluate("el => getComputedStyle(el).borderTopWidth") == "0px"
        assert card.locator(".passage-check-body").evaluate("el => getComputedStyle(el).borderLeftWidth") == "3px"
        expect(card.locator("button.passage-check-count")).to_have_count(3)
        quotes = card.locator(".passage-check-quote .pc-claim")
        expect(quotes).to_have_count(1)
        expect(quotes).to_have_text("You always need underfloor heating for that.")
        assert quotes.evaluate("el => getComputedStyle(el).backgroundColor") != "rgba(0, 0, 0, 0)"
        # Under the sentence: who disagrees and what one of them says instead,
        # in the reading colour; no grey rows between the quotes.
        verdict = card.locator(".passage-check-verdict")
        expect(verdict).to_have_text("2 of 3 models disagree – OpenAI: “Larger radiators are often enough.”")
        assert verdict.evaluate("el => getComputedStyle(el).color") != card.locator(".passage-check-note").evaluate(
            "el => getComputedStyle(el).color")
        expect(card.locator(".passage-check-quotes > *")).to_have_count(1)
        expect(card).to_contain_text("Checked against 3 models that answered “Do heat pumps make sense in old buildings?” "
                                     "without seeing your text.")
        # On a phone the counts wrap as whole units, never as a lone dot.
        assert card.locator(".passage-check-count").evaluate_all("els => els.every(el => el.getClientRects().length === 1)")
        # The answer's own statements are checked and marked like any answer's.
        expect(page.locator("#agentAnswerBody .cx-claim")).to_have_count(1)
        _snapshot(page, f"passage-check-{width}")

        # A count opens the same card as a checked answer sentence, with a
        # way to the model's own answer.
        card.locator('.passage-check-count[data-verdict="disputed"]').click()
        popover = page.locator("#claimPopover")
        expect(popover).to_be_visible()
        expect(popover).to_contain_text("Deviate")
        expect(popover).to_contain_text("Larger radiators are often enough.")
        _snapshot(page, f"passage-check-popover-{width}")
        page.keyboard.press("Escape")
        expect(popover).to_be_hidden()
        quotes.click()
        expect(popover).to_be_visible()
        popover.get_by_role("button", name="View answer").first.click()
        expect(page.locator(".answer-reader-dialog, .answer-reader")).to_be_visible()
        page.keyboard.press("Escape")
        expect(page.locator(".answer-reader-dialog, .answer-reader")).to_be_hidden()

        # The full text marks every sentence; what the Highlights setting does
        # not paint stays uncoloured, also under the pointer (no green).
        card.locator(".passage-check-toggle").click()
        marks = card.locator(".passage-check-text .pc-claim")
        expect(marks).to_have_count(3)
        assert marks.evaluate_all("els => els.map(el => el.dataset.verdict)") == ["holds", "disputed", "unconfirmed"]
        assert card.locator(".passage-check-text").evaluate("el => getComputedStyle(el).whiteSpace") == "pre-line"
        assert marks.nth(0).evaluate("el => el.classList.contains('is-quiet')")
        assert marks.nth(0).evaluate("el => getComputedStyle(el).backgroundColor") == "rgba(0, 0, 0, 0)"
        if width >= 700:
            marks.nth(0).hover()
            page.wait_for_timeout(250)
            hovered = marks.nth(0).evaluate("el => getComputedStyle(el).backgroundColor")
            assert marks.nth(0).evaluate(GREY), hovered
            assert hovered != "rgba(0, 0, 0, 0)"
        _snapshot(page, f"passage-check-full-{width}")
        expect(card.locator(".passage-check-toggle")).to_have_text("Show less")

        # Restoring the saved chat (bookmark path) keeps the card, even when
        # the thread question is set again afterwards.
        page.evaluate("""turn => {
            App.runRegistry.showSavedView({type: 'bookmark'}, {chatId: 'a'.repeat(32), turnId: turn.id, executionMode: 'agent',
                question: turn.question, consensus: turn.consensus, currentTurn: turn});
            App.setThreadQuestion(turn.question);
        }""", SAVED)
        expect(page.locator("#agentAnswer > .passage-check")).to_have_count(1)
        expect(page.locator("#agentAnswerBody .cx-claim")).to_have_count(1)
        # As an earlier turn of the chat, the card stays with its answer.
        page.evaluate("turn => App.followup.renderStoredTurns([turn])", SAVED)
        history = page.locator("#threadHistory .thread-history-turn").first
        expect(history.locator(".thread-history-question .pc-claim")).to_have_count(0)
        history_card = history.locator(".thread-history-answer > .passage-check")
        expect(history_card).to_contain_text("Models disagree with 1 of 3 statements in your text")
        assert history_card.evaluate("el => el.nextElementSibling.classList.contains('thread-history-answer-body')")
        expect(history.locator(".thread-history-answer-body .cx-claim")).to_have_count(1)
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

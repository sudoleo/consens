"""Before an account's first question goes to the AI providers, the app asks
once (static/js/ai-consent.js, app/services/ai_consent.py). Real bundles
against a stubbed Firebase SDK; the server's routes are stood in for."""
from playwright.sync_api import expect

from tests.e2e.test_phase4_frontend import _json, _real_firebase_page, phase4_server  # noqa: F401 (fixture)

QUESTION = "Is creatine safe for teenagers?"


def test_the_first_question_names_the_providers_and_goes_out_after_the_yes(browser, phase4_server):
    context, page = _real_firebase_page(browser, phase4_server)
    prepared, agreed = [], []
    try:
        page.route("**/user_status", lambda route: _json(route, {
            "is_pro": False, "limit": 3, "deep_limit": 0, "ai_consent": False}))
        page.route("**/api/my/ai-consent", lambda route: (
            agreed.append(route.request.method), _json(route, {"ai_consent": True})))
        page.route("**/prepare", lambda route: (
            prepared.append(route.request.post_data_json), _json(route, {"system_prompt": "Prepared prompt"})))
        page.route("**/ask_*", lambda route: _json(route, {"response": "An answer", "sources": []}))
        page.reload(wait_until="domcontentloaded")
        page.wait_for_function("() => window.App.aiConsent?.needed() === true")

        page.fill("#questionInput", QUESTION)
        page.click("#sendButton")
        dialog = page.locator("#appConfirmDialog")
        expect(dialog).to_be_visible()
        expect(dialog).to_contain_text("through OpenRouter")
        # The companies come from the registry (window.MODEL_FAMILIES).
        expect(dialog).to_contain_text("Anthropic Claude")
        expect(dialog.locator("#appConfirmLink a")).to_have_attribute("href", "/privacy#providers")

        # Not now: nothing leaves, the question stays in the field.
        dialog.locator(".confirm-cancel").click()
        expect(dialog).to_be_hidden()
        expect(page.locator("#questionInput")).to_have_value(QUESTION)
        assert prepared == [] and agreed == []

        page.wait_for_timeout(500)
        page.click("#sendButton")
        dialog.locator(".confirm-accept").click()
        page.wait_for_function(f"() => window.App.runRegistry.visible()?.question === {QUESTION!r}")
        assert agreed == ["POST"] and len(prepared) == 1
        # Asked once: the yes holds for the next question.
        assert page.evaluate("() => window.App.aiConsent.needed()") is False
    finally:
        context.close()

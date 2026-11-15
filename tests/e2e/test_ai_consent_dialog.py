"""Before an account's first question goes to the AI providers, the app asks
once, as the last step of the first-run dialog (static/js/first-run.js,
static/js/ai-consent.js, app/services/ai_consent.py). Real bundles
against a stubbed Firebase SDK; the server's routes are stood in for."""
from playwright.sync_api import expect

from tests.e2e.test_phase4_frontend import _json, _real_firebase_page, phase4_server  # noqa: F401 (fixture)

QUESTION = "Is creatine safe for teenagers?"


def test_the_first_question_sets_the_account_up_names_the_providers_and_goes_out_after_the_yes(browser, phase4_server):
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
        dialog = page.locator("#firstRunDialog")
        expect(dialog).to_be_visible()
        # Step one: how much of the reviewers' work to show. The agreement is not in sight yet.
        expect(dialog.locator('input[name="firstRunView"][value="doubts"]')).to_be_checked()
        expect(dialog.locator(".confirm-accept")).to_be_hidden()
        dialog.locator(".first-run-view", has=page.locator('input[value="answer"]')).click()
        expect(dialog).to_have_attribute("data-view", "answer")
        dialog.locator(".first-run-next").click()

        # Step two: the providers come from the registry (window.MODEL_FAMILIES), each with its logo.
        expect(dialog).to_contain_text("only goes to the models working on it")
        families = page.evaluate("() => window.MODEL_FAMILIES.length")
        expect(dialog.locator(".first-run-logos img")).to_have_count(families)
        dialog.locator(".first-run-providers summary").click()
        expect(dialog.locator(".first-run-providers li")).to_have_count(families)
        expect(dialog.locator(".first-run-providers ul")).to_contain_text("Anthropic Claude")
        expect(dialog.locator(".confirm-modal-note a")).to_have_attribute("href", "/privacy#providers")

        # Closed without a yes: nothing leaves, nothing is set, the question stays in the field.
        dialog.locator(".close-button").click()
        expect(dialog).to_be_hidden()
        expect(page.locator("#questionInput")).to_have_value(QUESTION)
        assert prepared == [] and agreed == []
        assert page.evaluate("() => window.App.userSettings.get('findings_to_agent')") is None

        page.wait_for_timeout(500)
        page.click("#sendButton")
        # Asked again from the start, with the default view.
        expect(dialog.locator('input[name="firstRunView"][value="doubts"]')).to_be_checked()
        dialog.locator(".first-run-view", has=page.locator('input[value="answer"]')).click()
        dialog.locator(".first-run-next").click()
        dialog.locator(".confirm-accept").click()
        page.wait_for_function(f"() => window.App.runRegistry.visible()?.question === {QUESTION!r}")
        assert agreed == ["POST"] and len(prepared) == 1
        # The chosen view and the correction pass are the account's settings now.
        assert page.evaluate("() => window.App.userSettings.get('consensus_highlights')") == "critical"
        assert page.evaluate("() => window.App.userSettings.get('findings_to_agent')") is True
        # Asked once: the yes holds for the next question.
        assert page.evaluate("() => window.App.aiConsent.needed()") is False
    finally:
        context.close()

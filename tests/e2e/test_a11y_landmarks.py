"""Landmarks, Sprungmarke und Fertig-Ansage in /app
(docs/a11y-audit-2026-10-23.md, B2, B3 und B4).

Vor der Eingabe lagen bei voller Chatliste rund 80 Tab-Stopps; die
Sprungmarke ist deshalb der erste und landet in der Frage. Das Ende eines
Laufs sagte bisher nur der Tab-Titel einer verborgenen Seite.
"""

from playwright.sync_api import expect

TABBABLE = "a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select, [tabindex]:not([tabindex='-1'])"


def test_the_first_tab_stop_skips_to_the_question(app_page):
    assert app_page.evaluate(
        "(selector) => document.querySelector(selector)?.classList.contains('skip-link')", TABBABLE
    ), "the skip link is the first tab stop of the page"
    skip = app_page.locator(".skip-link")
    skip.focus()
    box = skip.bounding_box()
    assert box and box["y"] >= 0, "a focused skip link is on screen"

    app_page.keyboard.press("Enter")

    expect(app_page.locator("#questionInput")).to_be_focused()
    assert "#" not in app_page.url, "the skip link does not leave a fragment in the address"


def test_the_app_has_one_main_a_named_sidebar_and_a_heading(app_page):
    structure = app_page.evaluate(
        """() => ({
          mains: [...document.querySelectorAll('main')].filter(el => el.checkVisibility()).map(el => el.id),
          sidebar: [document.getElementById('appSidebar').localName, document.getElementById('appSidebar').getAttribute('aria-label')],
          headings: [...document.querySelectorAll('h1')].filter(el => el.checkVisibility()).map(el => el.id),
          composer: document.getElementById('questionInput').getAttribute('aria-label'),
        })"""
    )
    assert structure == {
        "mains": ["appMain"],
        "sidebar": ["nav", "Chats"],
        "headings": ["appHeading"],
        "composer": "Your question",
    }


def test_a_finished_run_is_announced(app_page):
    status = app_page.locator("#answerStatus")
    expect(status).to_have_attribute("role", "status")
    expect(status).to_have_text("")
    # Like test_smoke._send_question: own dummy keys keep the run independent
    # of the free allowance; MOCK_LLM answers.
    app_page.evaluate(
        """() => {
          localStorage.setItem('openrouterKey', 'e2e-dummy-key');
          const ownKeys = document.getElementById('useOwnKeysSwitch');
          if (ownKeys) ownKeys.checked = true;
        }"""
    )
    app_page.fill("#questionInput", "When was the Eiffel Tower completed?")
    app_page.click("#sendButton")

    expect(status).to_have_text("Answer ready", timeout=45000)
    expect(app_page.locator("#appHeading")).to_have_text("When was the Eiffel Tower completed?")
    # Under the chat's h1 each message has its own heading (B3).
    expect(app_page.locator("#threadAsk > h2")).to_have_text("Your message")

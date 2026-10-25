"""axe-core gegen die öffentlichen Seiten und /app
(docs/a11y-audit-2026-10-23.md, Abschnitt 7).

axe findet die Grundlagen: Kontrast, Namen, erlaubte ARIA-Attribute. Damit
sie nicht wieder verrutschen, prüft es jede Seite in Hell und Dunkel, die
Landing und /app auch in Handybreite, /app als Vergleich und als Agent. Nur
`serious` und `critical` lassen den Test scheitern: `moderate` (Landmarks,
Überschriftenfolge) wiegt zu leicht für eine rote Nacht.

Gemessen wird erst, wenn alles steht: Bewegung ist reduziert, und der Scan
wartet, bis jede endliche Animation und jeder Übergang fertig ist. Sonst
misst axe die Zwischenfarbe eines Werts, der gerade einblendet, oder eines
Knopfs mitten im Wechsel auf Dunkel.

Was axe nicht sieht (Fokus, Ansagen, Sprache), prüfen eigene Tests wie
test_a11y_landmarks.py.
"""

import json
from pathlib import Path

import pytest
from playwright.sync_api import expect

from test_agent_chat_frontend import CATALOG, _choose_mode

AXE = Path(__file__).resolve().parents[2] / "node_modules" / "axe-core" / "axe.min.js"

PUBLIC_PAGES = (
    "/", "/de/", "/about", "/benchmark", "/consensus-engine", "/ai-model-comparison",
    "/model-pulse", "/questions", "/topics", "/privacy", "/terms", "/imprint",
    "/no-such-page",
)

# Waits for fonts and every finite animation and transition, then reports
# each serious rule as "rule (impact): first nodes", so a failure names what
# to fix.
SCAN = """async () => {
  await document.fonts.ready;
  for (let round = 0; round < 5; round += 1) {
    const moving = document.getAnimations().filter(animation => animation.playState === 'running'
      && Number.isFinite(animation.effect?.getComputedTiming().endTime));
    if (!moving.length) break;
    await Promise.race([Promise.all(moving.map(animation => animation.finished.catch(() => null))),
      new Promise(resolve => setTimeout(resolve, 4000))]);
  }
  const result = await axe.run(document, { resultTypes: ['violations'] });
  return result.violations
    .filter(rule => rule.impact === 'serious' || rule.impact === 'critical')
    .map(rule => `${rule.id} (${rule.impact}): ${rule.nodes.slice(0, 8).map(node => node.target.join(' ')).join(' | ')}`);
}"""


def _report(found):
    if found:
        pytest.fail("\n".join(f"{variant}: {line}" for variant, lines in found.items() for line in lines),
                    pytrace=False)


def _public_context(browser, width, dark):
    context = browser.new_context(
        viewport={"width": width, "height": 900}, reduced_motion="reduce",
        color_scheme="dark" if dark else "light",
    )
    # An init script is not held to the page's CSP, which forbids inline scripts.
    context.add_init_script(path=str(AXE))
    context.add_init_script("localStorage.setItem('theme', '" + ("dark" if dark else "light") + "')")
    context.route("https://cloud.umami.is/**", lambda route: route.fulfill(body=""))
    return context


@pytest.mark.parametrize("path", PUBLIC_PAGES)
def test_public_page_has_no_serious_axe_violations(browser, app_server, path):
    variants = [(1280, False), (1280, True)] + ([(390, False), (390, True)] if path in ("/", "/de/") else [])
    found = {}
    for width, dark in variants:
        context = _public_context(browser, width, dark)
        try:
            page = context.new_page()
            page.goto(app_server + path, wait_until="networkidle")
            violations = page.evaluate(SCAN)
            if violations:
                found[f"{width}px {'dark' if dark else 'light'}"] = violations
        finally:
            context.close()
    _report(found)


@pytest.mark.parametrize("width", [1440, 390])
def test_app_has_no_serious_axe_violations(app_server, context, width):
    context.add_init_script(path=str(AXE))
    page = context.new_page()
    page.set_viewport_size({"width": width, "height": 900})
    page.emulate_media(reduced_motion="reduce")
    # Agent access, so the scan also sees the Agent's own controls.
    page.route("**/user_status", lambda route: route.fulfill(
        content_type="application/json", body='{"tier": "pro", "is_pro": true, "agent_access": true}'))
    page.route("**/agent/models", lambda route: route.fulfill(
        content_type="application/json", body=json.dumps(CATALOG)))
    page.goto(f"{app_server}/app", wait_until="domcontentloaded")
    page.wait_for_function("() => window.App && window.App.authState && window.App.authState.known", timeout=30000)
    found = {}
    for mode in ("consensus", "agent"):
        if mode == "agent":
            _choose_mode(page, "agent")
            expect(page.locator("#agentModelDropdown")).to_be_enabled()
            page.keyboard.press("Escape")
        for dark in (False, True):
            page.evaluate("dark => { for (const el of [document.documentElement, document.body])"
                          " el.classList.toggle('dark-mode', dark); }", dark)
            violations = page.evaluate(SCAN)
            if violations:
                found[f"{mode} {'dark' if dark else 'light'}"] = violations
    _report(found)

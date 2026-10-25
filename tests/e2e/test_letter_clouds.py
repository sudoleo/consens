"""Buchstabenwolken (letter-clouds.js): nur auf dem leeren Startbildschirm.

Sie laufen im Hero, eine freie Stelle löst eine Welle aus, mit der ersten
Frage blenden sie aus und die Schleife hält an; „New comparison“ holt sie zurück.
"""

FREE_POINT = """() => {
  const skip = "a,button,input,textarea,select,label,summary,[role='button'],"
    + ".input-section,.sidebar,.app-nav-float,.view-switch,.app-mobile-header,dialog,.modal";
  const spots = [[0.62, 0.14], [0.85, 0.2], [0.4, 0.82], [0.88, 0.85]];
  for (const [fx, fy] of spots) {
    const x = Math.round(innerWidth * fx), y = Math.round(innerHeight * fy);
    const el = document.elementFromPoint(x, y);
    if (el && !el.closest(skip)) return {x, y};
  }
  return null;
}"""


def clouds(page):
    return page.evaluate("() => window.App.letterClouds.state()")


def test_letter_clouds_live_only_on_the_empty_start_screen(app_page, get_console_errors):
    page = app_page
    # The clouds belong to the hero, Agent's start screen (every account has
    # Agent; the suite starts in Compare, whose start is the answer grid).
    page.evaluate("() => window.App.runMode.set('agent')")
    page.wait_for_function("() => document.body.classList.contains('is-hero')")
    page.wait_for_function("() => window.App.letterClouds && window.App.letterClouds.state().active")
    state = clouds(page)
    assert state["supported"] and state["running"]

    spot = page.evaluate(FREE_POINT)
    assert spot, "no free spot on the start screen"
    page.mouse.click(spot["x"], spot["y"])
    assert clouds(page)["ripples"] > 0

    page.click("#questionInput")
    assert clouds(page)["ripples"] > 0  # Klick ins Feld startet keine neue Welle, stört die laufende nicht

    # Agent sends once its model list is there (agent-chat.js sendBlocker).
    page.wait_for_function("() => document.getElementById('agentModelDropdown')?.dataset.catalog === 'ready'")
    page.fill("#questionInput", "Wie sicher ist die Prognose?")
    page.keyboard.press("Enter")
    page.wait_for_function("() => !document.body.classList.contains('is-hero')")
    page.wait_for_function("() => !window.App.letterClouds.state().active")
    state = clouds(page)
    assert not state["running"] and state["ripples"] == 0
    assert page.locator(".letter-clouds").evaluate("el => el.classList.contains('is-off')")

    page.click("#newRunButton")
    page.wait_for_function("() => window.App.letterClouds.state().active")
    assert get_console_errors() == []

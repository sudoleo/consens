"""The material contract (Apple-Audit G5, G7, G13, G15): measured, not guessed.

The surface and text steps are checked with real colour math (OKLab distance
x100, WCAG contrast) so a later tweak cannot quietly bring back a bluish app
surface, a light step that does not lift, two greys that read as one, or a
sentence mark in a different red than the dots beside it.
"""

import math
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSS = ROOT / "static" / "css"


def read(name: str) -> str:
    return (CSS / name).read_text(encoding="utf-8")


def strip_comments(text: str) -> str:
    return re.sub(r"/\*.*?\*/", "", text, flags=re.S)


def block(text: str, selector: str) -> dict:
    """Custom properties of the first rule whose selector list is exactly `selector`."""
    text = strip_comments(text)
    for match in re.finditer(r"([^{}]+)\{([^{}]*)\}", text):
        if " ".join(match.group(1).split(";")[-1].split()) == selector:
            return dict(re.findall(r"(--[\w-]+)\s*:\s*([^;]+);", match.group(2)))
    raise AssertionError(f"no rule for {selector!r}")


# --- colour math ------------------------------------------------------------

def rgb(value: str):
    value = value.strip()
    if value.startswith("rgba("):
        r, g, b, _a = (float(x) for x in value[5:-1].split(","))
        return r / 255, g / 255, b / 255
    value = value.lstrip("#")
    if len(value) == 3:
        value = "".join(c * 2 for c in value)
    return tuple(int(value[i:i + 2], 16) / 255 for i in (0, 2, 4))


def _lin(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def luminance(value):
    r, g, b = (_lin(c) for c in rgb(value))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a, b):
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def oklab(value):
    r, g, b = (_lin(c) for c in rgb(value))
    l = (0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b) ** (1 / 3)
    m = (0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b) ** (1 / 3)
    s = (0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b) ** (1 / 3)
    return (0.2104542553 * l + 0.7936177850 * m - 0.0040720468 * s,
            1.9779984951 * l - 2.4285922050 * m + 0.4505937099 * s,
            0.0259040371 * l + 0.7827717662 * m - 0.8086757660 * s)


def distance(a, b):
    return 100 * math.dist(oklab(a), oklab(b))


def hue(value):
    _l, a, b = oklab(value)
    return math.degrees(math.atan2(b, a)) % 360


def mix(fg, amount, bg):
    """color-mix(in srgb, fg amount, bg) / fg at alpha `amount` over bg."""
    return "#" + "".join(
        "%02x" % round((x * amount + y * (1 - amount)) * 255) for x, y in zip(rgb(fg), rgb(bg))
    )


def oklch_hex(lightness, chroma, hue_deg):
    a = chroma * math.cos(math.radians(hue_deg))
    b = chroma * math.sin(math.radians(hue_deg))
    l_ = (lightness + 0.3963377774 * a + 0.2158037573 * b) ** 3
    m_ = (lightness - 0.1055613458 * a - 0.0638541728 * b) ** 3
    s_ = (lightness - 0.0894841775 * a - 1.2914855480 * b) ** 3
    lin = (4.0767416621 * l_ - 3.3077115913 * m_ + 0.2309699292 * s_,
           -1.2684380046 * l_ + 2.6097574011 * m_ - 0.3413193965 * s_,
           -0.0041960863 * l_ - 0.7034186147 * m_ + 1.7076147010 * s_)
    enc = [12.92 * x if x <= 0.0031308 else 1.055 * x ** (1 / 2.4) - 0.055 for x in lin]
    return "#" + "".join("%02x" % round(min(1, max(0, v)) * 255) for v in enc)


def percent(value: str) -> float:
    return float(value.strip().rstrip("%")) / 100


APP = read("variables.css")
LIGHT = block(APP, ":root")
DARK = block(APP, ".dark-mode")
THEMES = {"light": LIGHT, "dark": DARK}


def test_app_and_public_pages_are_made_of_the_same_material():
    public = read("public-tokens.css")
    public_light = block(public, ":root")
    public_dark = block(public, ":root.dark-mode, .dark-mode")
    for name in ("--ground", "--raise", "--well", "--ink", "--ink-2", "--ink-3", "--line", "--line-soft",
                 "--agree", "--agree-bg", "--partial", "--partial-bg", "--dispute", "--dispute-bg",
                 "--hover-mix", "--selected-mix", "--field", "--field-line", "--field-lift", "--field-lift-active"):
        assert public_light[name] == LIGHT[name], name
        assert public_dark[name] == DARK[name], name


def test_the_app_shell_no_longer_paints_its_own_surface():
    """shell.css used to rebind --raise to #303338 in dark: a bluish surface
    with ten times the step of the website (OKLab 10.3 against 3.7)."""
    shell = strip_comments(read("shell.css"))
    assert not re.search(r"--(raise|app-surface)\s*:\s*#", shell)
    assert not re.search(r"--(raise|app-surface)\s*:\s*rgba?\(", shell)
    head = block(read("shell.css"), "body, body.dark-mode")
    assert head["--app-surface"] == "var(--raise)"
    assert head["--app-surface-hover"] == "var(--raise-hover)"


def test_a_raised_surface_lifts_the_same_in_light_and_dark():
    light = distance(LIGHT["--ground"], LIGHT["--raise"])
    dark = distance(DARK["--ground"], DARK["--raise"])
    assert light >= 3.0 and dark >= 3.0, (light, dark)
    assert abs(light - dark) <= 0.5, (light, dark)


def test_the_grey_ladder_has_three_distinct_rungs_and_stays_readable():
    for theme, tokens in THEMES.items():
        ink, ink2, ink3 = tokens["--ink"], tokens["--ink-2"], tokens["--ink-3"]
        assert distance(ink2, ink3) >= 7, (theme, distance(ink2, ink3))
        assert distance(ink, ink2) >= 12, (theme, distance(ink, ink2))
        hover = mix(ink, percent(tokens["--hover-mix"]), tokens["--raise"])
        for surface in (tokens["--ground"], tokens["--raise"], tokens["--well"], hover):
            assert contrast(ink3, surface) >= 4.5, (theme, ink3, surface, contrast(ink3, surface))


def test_hover_is_one_tone_step_in_both_themes():
    steps = {}
    for theme, tokens in THEMES.items():
        hover = mix(tokens["--ink"], percent(tokens["--hover-mix"]), tokens["--ground"])
        selected = mix(tokens["--ink"], percent(tokens["--selected-mix"]), tokens["--ground"])
        steps[theme] = distance(tokens["--ground"], hover)
        assert distance(hover, selected) >= 2, theme
    assert all(3 <= step <= 5 for step in steps.values()), steps
    assert abs(steps["light"] - steps["dark"]) <= 0.6, steps
    foundation = block(read("foundation.css"), ":root, .dark-mode")
    assert "var(--hover-mix" in foundation["--hover"]
    assert "var(--ink)" in foundation["--hover"]


def test_traffic_light_is_text_safe_and_dispute_is_not_the_amber():
    for theme, tokens in THEMES.items():
        for name in ("--agree", "--partial", "--dispute"):
            for surface in (tokens["--ground"], tokens["--raise"]):
                assert contrast(tokens[name], surface) >= 4.5, (theme, name, surface)
        assert abs(hue(tokens["--dispute"]) - hue(tokens["--partial"])) >= 45, theme
    # The tints stand on the hue of their colour.
    for name in ("agree", "partial", "dispute"):
        assert abs(hue(LIGHT[f"--{name}-bg"]) - hue(LIGHT[f"--{name}"])) <= 3, name


MARKS = {
    # mark: (token, lightness, chroma, alpha in dark or None)
    "--cx-mark-agree": ("--agree", 0.962, 0.017),
    "--cx-mark-agree-strong": ("--agree", 0.941, 0.031),
    "--cx-mark-split": ("--partial", 0.931, 0.051),
    "--cx-mark-split-strong": ("--partial", 0.907, 0.077),
    "--cx-mark-major": ("--dispute", 0.916, 0.029),
    "--cx-mark-major-strong": ("--dispute", 0.871, 0.05),
}


def test_sentence_marks_take_their_hue_from_the_traffic_light():
    """One meaning, one colour: the marked passage once had its own red and
    amber, next to dots and labels in another (OKLab 9.9)."""
    visuals = read("components-consensus-visuals.css")
    supports = strip_comments(visuals).split("@supports (color: oklch(from red l c h))", 1)[1]
    derived_light = block(supports, ":root")
    derived_dark = block(supports, ".dark-mode")
    fallback_light = block(visuals, ":root")
    fallback_dark = block(visuals, ".dark-mode")
    for mark, (token, lightness, chroma) in MARKS.items():
        assert derived_light[mark] == f"oklch(from var({token}) {lightness:g} {chroma:g} h)", mark
        assert derived_dark[mark].startswith(f"oklch(from var({token}) "), mark
        # The fixed fallback is the same computation, so older browsers see
        # the same colour.
        expected = oklch_hex(lightness, chroma, hue(LIGHT[token]))
        assert distance(fallback_light[mark], expected) <= 0.6, (mark, fallback_light[mark], expected)
        dark_fallback = re.match(r"rgba\((\d+), (\d+), (\d+), [\d.]+\)", fallback_dark[mark])
        assert dark_fallback, mark
        vivid = "#" + "".join("%02x" % int(v) for v in dark_fallback.groups())
        assert abs(hue(vivid) - hue(DARK[token])) <= 2, (mark, vivid)
    assert fallback_light["--cx-major-line"] == "var(--partial)"


def test_no_text_takes_its_tone_from_transparency():
    layout = strip_comments(read("layout.css"))
    footer = re.search(r"\.sidebar-footer-meta \{([^}]*)\}", layout).group(1)
    assert "opacity" not in footer
    modals = strip_comments(read("components-modals.css"))
    guest = re.search(r"\.settings-guest-note p \{([^}]*)\}", modals).group(1)
    assert "opacity" not in guest


# --- the parts, built once (Apple-Audit G2, G4, G5, G6, G8-G12, G17, C3, C9) --

ROOT_TEMPLATES = ROOT / "templates"
SKIP_SHEETS = {"admin.css", "admin-benchmark.css"}


def sheets():
    for path in sorted(CSS.glob("*.css")):
        if path.name not in SKIP_SHEETS:
            yield path.name, strip_comments(path.read_text(encoding="utf-8"))


def rules(text):
    """(selector, body) of every plain rule; @media wrappers are looked through."""
    for match in re.finditer(r"([^{}]+)\{([^{}]*)\}", text):
        selector = " ".join(match.group(1).split(";")[-1].split())
        if not selector.startswith("@"):
            yield selector, match.group(2)


def rule_body(text, selector):
    for found, body in rules(text):
        if found == selector:
            return body
    raise AssertionError(f"no rule for {selector!r}")


def test_hover_is_a_tone_step_not_transparency():
    """The global button:hover faded every button to 0.9 and needed some forty
    `opacity: 1` exceptions; hover backgrounds came in 67 different values."""
    hover_values = set()
    counters = []
    for name, text in sheets():
        for selector, body in rules(text):
            if ":hover" not in selector:
                continue
            assert not re.fullmatch(r"button:hover", selector), name
            if re.search(r"(?<![-\w])opacity\s*:\s*0?\.9\d*\s*;", body):
                counters.append(f"{name}: {selector} fades")
            for value in re.findall(r"background(?:-color)?\s*:\s*([^;]+);", body):
                hover_values.add(value.replace("!important", "").strip())
    assert not counters, counters
    assert "var(--hover)" in hover_values
    assert len(hover_values) <= 36, sorted(hover_values)


def test_the_filled_button_is_one_component():
    inputs = strip_comments(read("components-input.css"))
    primaries = (".share-primary-btn", ".btn-pro", ".auth-primary-action", ".memory-edit-submit",
                 ".watch-nudge-btn", ".post-demo-login-action", ".agent-google-btn.is-primary",
                 ".wd-button.is-primary", ".wd-action.is-strong", ".run-blocked-btn.is-primary",
                 ".verify-banner-btn", ".feedback-login-button", "#feedbackForm .feedback-submit")
    head, material = next((s, b) for s, b in rules(inputs) if s.startswith(".button, .btn, .share-primary-btn"))
    for primary in primaries:
        assert primary in head, primary
    for declaration in ("min-height: 36px", "border-radius: var(--radius-sm)", "background: var(--button-bg)",
                        "box-shadow: none"):
        assert declaration in material
    assert "var(--button-bg-hover)" in inputs and "min-height: 44px" in inputs
    # No variant paints its own gloss, shadow or lift any more.
    for name, text in sheets():
        for selector, body in rules(text):
            if not any(p in selector for p in primaries) or ":disabled" in selector:
                continue
            assert "linear-gradient" not in body, (name, selector)
            assert "translateY(-" not in body, (name, selector)
            assert not re.search(r"box-shadow:\s*(?!none)[^;]*var\(--button-bg\)", body), (name, selector)



def test_the_filled_button_hover_lends_no_id_weight():
    """Inside :is() the one ID selector (#feedbackForm .feedback-submit) gave
    every filled button's hover the weight of an ID. In a narrow desktop window
    it outranked the phone header's Sign up, whose surface is a 32 px ::before
    in a 44 px target, and the hover filled the whole target."""
    inputs = strip_comments(read("components-input.css"))
    hover = next(s for s, _ in rules(inputs) if ":hover" in s and ".auth-top-signup" in s)
    groups = re.findall(r":is\(([^)]*\([^)]*\)[^)]*|[^)]*)\)", hover)
    assert groups and not any("#" in group for group in groups), hover
    assert "#feedbackForm .feedback-submit:hover:not(:disabled)" in hover

def test_the_chosen_option_reads_in_full_ink():
    shell = strip_comments(read("shell.css"))
    chosen = rule_body(shell, "body .model-picker-option.is-selected, body.dark-mode .model-picker-option.is-selected")
    assert "color: var(--ink)" in chosen
    toggle = rule_body(shell, "body .theme-toggle, body .theme-toggle.is-dark")
    assert "is-selected" not in toggle


def test_composer_and_landing_field_are_one_material():
    shell = strip_comments(read("shell.css"))
    composer = rule_body(shell, ":root, body.dark-mode")
    assert "--composer-surface: var(--field)" in composer
    assert "--composer-shadow: var(--field-lift)" in composer
    landing = rule_body(strip_comments(read("landing.css")), ":root, .dark-mode")
    assert "--lp-field: var(--field)" in landing


def test_sources_are_one_component_in_the_app_and_on_public_pages():
    assert "@import url('./css/source-pill.css');" in (ROOT / "static" / "style.css").read_text(encoding="utf-8")
    assert "@import url('./source-pill.css');" in read("public-pages.css")
    pill = strip_comments(read("source-pill.css"))
    assert '.src-ref, .source-link, .share-md a[href^="#src-"]' in [s for s, _ in rules(pill)]
    # No other sheet sizes or shapes a site icon or tints a citation pill.
    for name, text in sheets():
        if name == "source-pill.css":
            continue
        for selector, body in rules(text):
            if re.search(r"\.(src-ref|source-link|src-ref-favicon|source-favicon|cite-favicon|wp-link-icon|share-source-favicon|wd-source-icon)\b(?![-\w])", selector) \
                    or 'a[href^="#src-"]' in selector:
                assert not re.search(r"(?<![-\w])(width|height|border-radius)\s*:", body), (name, selector)
                assert "--accent" not in body, (name, selector)


def test_no_text_is_smaller_than_the_12px_floor():
    """typography.css: 12px is the floor. Anything below was an 8-px "PDF"
    plaque, a 10-px file size and 9-px fallback letters (Apple-Audit G10)."""
    offenders = []
    for name, text in sheets():
        for selector, body in rules(text):
            for value in re.findall(r"(?<![-\w])font-size\s*:\s*([^;]+);", body):
                value = value.replace("!important", "").strip()
                size = None
                if m := re.fullmatch(r"([\d.]+)px", value):
                    size = float(m.group(1))
                elif m := re.fullmatch(r"([\d.]+)rem", value):
                    size = float(m.group(1)) * 16
                elif m := re.fullmatch(r"([\d.]+)em", value):
                    size = float(m.group(1)) * 16
                if size is not None and 0 < size < 12:
                    offenders.append(f"{name}: {selector} -> {value}")
            for value in re.findall(r"(?<![-\w])font\s*:\s*([^;]+);", body):
                if m := re.match(r"(?:[\w-]+\s+)*?([\d.]+)px", value):
                    if float(m.group(1)) < 12:
                        offenders.append(f"{name}: {selector} -> font: {value}")
    tokens = strip_comments(read("typography.css"))
    for name, rem in re.findall(r"(--font-size-[\w-]+)\s*:\s*([\d.]+)rem", tokens):
        assert float(rem) * 16 >= 12, name
    assert not offenders, offenders


def test_every_chevron_is_the_one_drawn_symbol():
    """52 rotated CSS borders, a unicode "›", a "▸/▾" from a fallback font and
    a CSS triangle used to draw the same arrow (Apple-Audit G11). Left are the
    check marks, which are not chevrons."""
    checks = ("custom-checkbox-label input", "model-picker-option.is-selected::after", "model-picker-row-check")
    for name, text in sheets():
        for selector, body in rules(text):
            rotated = re.search(r"rotate\(-?(45|135|225|315)deg\)", body)
            bordered = re.search(r"border-(right|bottom|top|left|width)\s*:", body)
            if rotated and bordered:
                assert any(c in selector for c in checks), (name, selector)
            assert not re.search(r'content:\s*"[›‹▸▾]"', body), (name, selector)
            assert "border-top: 5px solid" not in body, (name, selector)
    foundation = strip_comments(read("foundation.css"))
    assert "--chevron-mask:" in foundation and ".chevron" in [s for s, _ in rules(foundation)]
    for template in ("index.html", "landing.html", "benchmark.html"):
        markup = (ROOT_TEMPLATES / template).read_text(encoding="utf-8")
        assert "&#8250;" not in markup and '<span aria-hidden="true">›</span>' not in markup, template


def test_every_text_field_focuses_the_same_way():
    expected = {
        "components-input.css": ['input[type="text"]:focus, textarea:focus'],
        "auth-modal.css": ["#loginModal .auth-form input:focus"],
        "components-modals.css": ['#feedbackForm textarea:focus, #feedbackForm input[type="email"]:focus',
                                  '.settings-body input[type="text"]:focus, .settings-body textarea:focus',
                                  ".share-url-row input:focus", ".watch-condition-input:focus"],
        "components-memory-edit.css": [".memory-edit-dialog textarea:focus"],
        "public-pages.css": [".hub-toolbar input:focus, .hub-toolbar select:focus"],
        "public-shell.css": [".share-follow-form input:focus, .share-report-form input:focus, .share-report-form textarea:focus"],
        "shell.css": [".sidebar-search-box input:focus"],
    }
    for name, selectors in expected.items():
        text = strip_comments(read(name))
        for selector in selectors:
            body = rule_body(text, selector)
            assert "var(--field-focus-border)" in body, (name, selector)
            assert "var(--field-focus-ring)" in body, (name, selector)
            assert "--liquid-focus-ring" not in body and "--accent" not in body, (name, selector)


def test_switches_show_the_choice_without_a_bolder_label():
    """A bolder label grew 1-3 px and pushed its neighbours (Apple-Audit C9)."""
    for name, selector in (("components-watch.css", ".view-switch-btn.is-active"),
                           ("auth-modal.css", '#loginModal .auth-tab[aria-selected="true"]'),
                           ("model-answer-reader.css", '.answer-reader-sections button[aria-pressed="true"]'),
                           ("components-modals.css", ".settings-nav-item.is-active")):
        assert "font-weight" not in rule_body(strip_comments(read(name)), selector), selector
    auth = strip_comments(read("auth-modal.css"))
    assert "transform: translateX(100%)" in rule_body(
        auth, '#loginModal .auth-tabs:has(#authTabRegister[aria-selected="true"])::before')
    firebase = (ROOT / "static" / "firebase.js").read_text(encoding="utf-8")
    assert "window.App?.watchUi?.smoothHeight" in firebase


def test_sidebar_rows_are_one_component():
    shell = strip_comments(read("shell.css"))
    for selector in (".sidebar-new-run", ".sidebar-model-entry", ".sidebar-bookmarks-head .sidebar-toggle-btn"):
        body = rule_body(shell, selector)
        assert "grid-template-columns: 18px minmax(0, 1fr)" in body, selector
        assert "min-height: 36px" in body and "padding: 6px 8px" in body, selector
        assert "column-gap: 9px" in body, selector
    for selector in (".sidebar-new-run", ".sidebar-model-copy strong", ".sidebar-bookmarks-head .sidebar-toggle-btn"):
        body = rule_body(shell, selector)
        assert "font-size: var(--font-size-sm)" in body and "font-weight: var(--font-weight-medium)" in body, selector
    assert "color: var(--ink-3)" in rule_body(shell, ".sidebar-model-copy span")


def test_logo_toggle_and_switch_move_with_the_sidebar():
    """Opening the sidebar the switch jumped 130 px in one frame and the logo
    vanished; closing it two logos and two toggles stood side by side
    (Apple-Audit C3)."""
    watch = strip_comments(read("components-watch.css"))
    switch = rule_body(watch, ".view-switch")
    assert "left: 50vw" in switch
    media = watch.split("@media (min-width: 1100px)", 1)[1]
    placed = rule_body(media, ".view-switch")
    assert "left: calc(50vw + var(--app-sidebar-offset) / 2)" in placed
    assert "left var(--dur-layer) var(--ease-standard)" in placed
    layout = strip_comments(read("layout.css"))
    desktop = layout.split("@media (min-width: 1100px)", 1)[1]
    assert "left var(--dur-layer) var(--ease-standard)" in rule_body(desktop, ".container")
    assert "transition: opacity var(--dur-state) var(--ease-out) calc(var(--dur-layer) / 2)" in layout
    shell = strip_comments(read("shell.css"))
    handover = [b for s, b in rules(shell) if s == "body:not(:has(.sidebar.collapsed)) .app-nav-float .sidebar-toggle"]
    assert any("visibility 0s var(--ease-linear) var(--dur-layer)" in body for body in handover)


def test_the_phone_menu_mark_is_bare():
    """Max: rahmenlos wie am Desktop (Apple-Audit G17)."""
    shell = strip_comments(read("shell.css"))
    toggle = rule_body(shell, ".app-mobile-header .sidebar-toggle")
    assert "background: transparent" in toggle and "box-shadow: none" in toggle
    group = rule_body(shell, ".mobile-conversation-actions")
    assert "background: transparent" in group and "box-shadow: none" in group

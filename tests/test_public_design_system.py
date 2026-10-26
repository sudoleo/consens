import importlib.util
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PUBLIC_TEMPLATES = (
    "landing.html",
    "about.html",
    "ai-model-comparison.html",
    "consensus-engine.html",
    "benchmark.html",
    "model-pulse.html",
    "privacy.html",
    "terms.html",
    "imprint.html",
    "share.html",
    "share_unavailable.html",
    "topics.html",
    "topic.html",
)


def read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_public_pages_share_navigation_and_footer_partials():
    for template_name in PUBLIC_TEMPLATES:
        template = read(f"templates/{template_name}")
        assert '{% include "partials/public_nav.html" %}' in template
        assert '{% include "partials/public_footer.html" %}' in template


def test_public_styles_share_the_app_aligned_token_layer():
    # Nested imports are unversioned; the entry URL's content hash covers them.
    token_import = re.compile(r"@import url\('\./public-tokens\.css'\);")
    assert token_import.search(read("static/css/landing.css"))
    assert token_import.search(read("static/css/public-pages.css"))

    app_tokens = read("static/css/variables.css")
    public_tokens = read("static/css/public-tokens.css")

    # The surface scale is the contract between /app and the public pages:
    # the marketing mockups are supposed to be made of the same material as
    # the product, so these five values have to be identical in both files —
    # in light AND dark. Everything else is derived from them.
    for contract in (
        "--radius-lg: 16px;",
        "--ground: #ffffff;",
        "--raise: #f3f3f3;",
        "--well: #fff;",
        "--side: #f8f8f8;",
        "--ink: #0a0a0a;",
        "--ink-2: var(--ink-3);",
        "--ink-3: #5e5e5e;",
        "--agree: #217863;",
        "--agree-bg: #e0efea;",
        "--partial: #896512;",
        "--partial-bg: #fbebcf;",
        "--dispute: #ad4b57;",
        "--dispute-bg: #fbe7e8;",
        "--ground: #050505;",
        "--raise: #151515;",
        "--side: #101010;",
        "--ink-3: #a1a1a1;",
        "--dispute: #f07f76;",
        "--hover-mix: 5%;",
        "--hover-mix: 7%;",
        "--field: var(--well);",
        "--accent-secondary: var(--agree);",
        "--glass-blur: 0px;",
    ):
        assert contract in app_tokens, f"missing in variables.css: {contract}"
        assert contract in public_tokens, f"missing in public-tokens.css: {contract}"

    for contract in ("--page-bg: var(--ground);",):
        assert contract in public_tokens


def test_typography_is_self_hosted_and_shared_by_every_surface():
    typography = read("static/css/typography.css")
    app_tokens = read("static/css/variables.css")
    public_tokens = read("static/css/public-tokens.css")

    # Three Inter parts per style plus two metric-matched local fallbacks (no
    # download): regular/medium against Arial, semibold/bold against Arial
    # Bold. The full source files are no longer referenced.
    assert typography.count('@font-face {') == 8
    assert typography.count("url(") == 6
    assert typography.count('font-family: "Inter Fallback";') == 2 and "size-adjust:" in typography
    assert 'local("Arial Bold")' in typography and "font-weight: 550 900;" in typography
    assert "InterVariable.woff2" not in typography and "InterVariable-Italic.woff2" not in typography
    for contract in (
        '--font-sans: "Inter Variable"',
        "--font-weight-regular: 400;",
        "--font-weight-medium: 500;",
        "--font-weight-semibold: 600;",
        "--font-weight-bold: 700;",
        "--font-size-display-lg:",
    ):
        assert contract in typography

    typography_import = re.compile(r"@import url\('\./typography\.css'\);")
    assert typography_import.search(app_tokens)
    assert typography_import.search(public_tokens)

    font_dir = ROOT / "static" / "fonts" / "inter"
    assert "SIL OPEN FONT LICENSE" in (font_dir / "OFL.txt").read_text(encoding="utf-8")

    for template_path in (ROOT / "templates").rglob("*.html"):
        assert "fonts.googleapis.com" not in template_path.read_text(encoding="utf-8")
    # Every page fetches Inter with the HTML, at the exact URL @font-face
    # resolves to (B3): /app and each public template include the partial.
    assert '{% include "partials/font_preload.html" %}' in read("templates/index.html")
    for template_name in PUBLIC_TEMPLATES + ("not_found.html", "questions.html", "watch_share.html", "notice.html"):
        template = read(f"templates/{template_name}")
        head = template.split("</head>", 1)[0]
        assert '{% include "partials/font_preload.html" %}' in head, template_name
        assert head.index("font_preload.html") < head.index('rel="stylesheet"'), template_name

    security = read("app/core/security.py")
    assert "fonts.googleapis.com" not in security
    assert "fonts.gstatic.com" not in security


def _inter_subsets():
    path = ROOT / "scripts" / "subset_inter_font.py"
    spec = importlib.util.spec_from_file_location("subset_inter_font", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_inter_parts_have_disjoint_ranges_and_a_small_latin_file():
    subsets = _inter_subsets()
    declared = subsets.declared_ranges(read("static/css/typography.css"))
    font_dir = ROOT / "static" / "fonts" / "inter"

    assert set(declared) == {f"{style}-{part}.woff2" for style in subsets.STYLES for part in subsets.PARTS}
    for style in subsets.STYLES:
        ranges = {part: subsets.parse_css_ranges(declared[f"{style}-{part}.woff2"]) for part in subsets.PARTS}
        # The Latin face is declared exactly as the script cuts it; the other
        # two hold only characters outside it and never overlap each other.
        assert declared[f"{style}-latin.woff2"] == subsets.css_ranges(subsets.LATIN_RANGES)
        assert all(subsets.part_of(codepoint) == "latin-ext" for codepoint in ranges["latin-ext"])
        assert all(subsets.part_of(codepoint) == "rest" for codepoint in ranges["rest"])
        # The part every page loads stays far below the 344/379 KB source.
        files = subsets.declared_files(read("static/css/typography.css"))
        assert 60_000 < (font_dir / files[f"{style}-latin.woff2"]).stat().st_size < 160_000
        for part in ("latin-ext", "rest"):
            assert (font_dir / files[f"{style}-{part}.woff2"]).stat().st_size > 60_000


def test_font_files_are_named_by_their_content_and_cached_for_good():
    """B3: the font used to be revalidated (no-cache, a 304) on every visit,
    arrived after the first paint and swapped every headline. Its name now
    carries its hash, so it can be immutable -- and a stale name is caught
    here, without fonttools."""
    import hashlib

    from app.core import static_delivery
    from app.core.assets import font_preload_urls

    subsets = _inter_subsets()
    typography = read("static/css/typography.css")
    font_dir = ROOT / "static" / "fonts" / "inter"
    for part, name in subsets.declared_files(typography).items():
        data = (font_dir / name).read_bytes()
        assert name == f"{part.removesuffix('.woff2')}.{hashlib.sha256(data).hexdigest()[:12]}.woff2"
        assert static_delivery.static_cache_control(f"/static/fonts/inter/{name}") == static_delivery.IMMUTABLE_CACHE_CONTROL
    # Unhashed files (the full sources) are still revalidated.
    assert static_delivery.static_cache_control("/static/fonts/inter/InterVariable.woff2") == "no-cache"
    latin = subsets.declared_files(typography)["InterVariable-latin.woff2"]
    assert font_preload_urls() == [f"/static/fonts/inter/{latin}"]
    # Upright Latin is drawn in Inter or in the fallback, never both: no swap
    # after the first paint. The rarer parts may still swap in.
    latin_face = typography.split(latin, 1)[1].split("}", 1)[0]
    assert "font-display: optional;" in latin_face
    assert typography.count("font-display: optional;") == 1


def test_interface_text_never_needs_more_than_the_latin_font_file():
    """A character outside the Latin part in a template, script or stylesheet
    would make every page showing it download a second Inter file. Add the
    character's block to LATIN_RANGES in scripts/subset_inter_font.py and
    re-run it, or write the character differently."""
    subsets = _inter_subsets()
    declared = subsets.declared_ranges(read("static/css/typography.css"))
    # Only characters Inter has outside its Latin part fetch another file;
    # one Inter lacks entirely (a fullwidth plus) falls back to the system font.
    fetches = set()
    for name, ranges in declared.items():
        if not name.endswith("-latin.woff2"):
            fetches |= subsets.parse_css_ranges(ranges)
    offenders = []
    for folder in (ROOT / "templates", ROOT / "static" / "js", ROOT / "static" / "css"):
        for path in folder.rglob("*"):
            if path.suffix not in {".html", ".js", ".css"} or "vendor" in path.parts:
                continue
            for character in set(path.read_text(encoding="utf-8")):
                if ord(character) in fetches:
                    offenders.append((path.relative_to(ROOT).as_posix(), f"U+{ord(character):04X} {character}"))
    # Only in source comments, never rendered.
    comments_only = {("static/js/letter-clouds.js", "U+03B8 θ")}
    assert sorted(set(offenders) - comments_only) == []

    security = read("app/core/security.py")
    assert "fonts.googleapis.com" not in security
    assert "fonts.gstatic.com" not in security


def test_product_result_mockup_is_reused():
    # The landing hero is demo-first (input field CTA) since 2026-07-17 and no
    # longer embeds the result mockup; the consensus-engine page still does.
    include = '{% include "partials/product_result_mockup.html" %}'
    assert include in read("templates/consensus-engine.html")


def test_share_page_loads_the_common_math_renderer():
    template = read("templates/share.html")
    assert '{% include "partials/katex.html" %}' in template
    partial = read("templates/partials/katex.html")
    assert "asset_url('/static/vendor/katex/0.19.0/dist/katex.min.js')" in partial
    assert "asset_url('/static/js/math-render.js')" in partial
    # Die Klassenliste des Shells waechst (share-shell, topic-detail-shell);
    # gepruefft wird, dass der Renderer am Shell haengt, nicht ihre Reihenfolge.
    assert re.search(r'<main id="main" class="page-shell[^"]*" data-math-render>', template)


def test_watch_page_leads_with_one_state_line_and_keeps_the_curve_off_phones():
    template = read("templates/watch_share.html")
    public_css = read("static/css/public-pages.css")
    phone_rules = public_css.split(".wp-shell { padding-top: 26px; }", 1)[1].split("}\n}", 1)[0]

    parts = read("templates/partials/check_page.html")
    assert 'class="wp-state is-{{ page_state.tone }}"' in parts
    assert template.index("check.state(") < template.index("check.answer(") < template.index("check.history(")
    # No scoreboard, model chips or differences toggle above the answer.
    assert "share-scoreboard" not in template
    assert "toggleDifferencesView" not in template
    assert ".wp-chart { display: none; }" in phone_rules
    # A long, non-wrapping source title once pushed the whole phone page
    # sideways: the list item has to be capped, not only the link.
    assert ".wp-evidence li { min-width: 0; max-width: 100%; }" in public_css


def test_landing_explains_consensus_watch_as_fourth_product_step():
    landing = read("templates/landing.html")
    navigation = read("templates/partials/public_nav.html")

    assert 'id="watch"' in landing
    assert "04 · Monitor" in landing
    assert "Know when the answer changes." in landing
    assert 'href="/app/watches"' in landing
    assert 'href="/#watch">Watches</a>' in navigation


def test_landing_watch_example_uses_the_live_watch_wording_and_no_scores():
    """The example once showed "72/100 model agreement" and "34/100 movement"
    long after watches dropped scores for goals and evidence. Every label it
    shows has to exist in the dashboard, the watch page, the alert options,
    the watch mail or the Telegram message, so a rename there flags the
    landing too."""
    landing = read("templates/landing.html")
    section = landing.split('<section id="watch"', 1)[1].split("</section>", 1)[0]

    assert "/100" not in section
    assert "materially" not in section
    dashboard = read("static/js/watch-dashboard.js")
    alert_options = read("static/js/watch-fields.js")
    mail = read("app/services/mailer.py")
    watch_page = read("templates/partials/check_page.html")
    telegram = read("app/services/telegram_watch.py")
    for label, source in (
        ("Moved", dashboard),
        ("Waiting for", dashboard),
        ("Not yet", mail),
        ("The answer changed", watch_page),
        ("When it moves or is reached", alert_options),
        ("The answer moved", telegram),
        ("What changed", telegram),
        ("New evidence the earlier answer did not have.", telegram),
    ):
        assert label in section, label
        assert label in source, f"{label!r} is no longer live wording"


def test_landing_heights_in_the_page_flow_ignore_the_browser_bar():
    """F1: dvh follows Safari's bar, so every band grew on the first swipe and
    the text slid away under the finger. In-flow heights use svh."""
    landing = read("static/css/landing.css")
    assert "dvh" not in re.sub(r"/\*.*?\*/", "", landing, flags=re.S)
    assert "min-height: calc(100svh - 54px);" in landing


def test_smooth_scrolling_starts_only_after_the_page_has_arrived():
    """L1: html { scroll-behavior: smooth } also animated the jump to /#watch
    after loading a page: 8,000 px through every scene. The glide is switched
    on by public-nav.js once the page has loaded; anchors land under the bar."""
    nav = read("templates/partials/public_nav.html")
    assert "asset_url('/static/js/public-nav.js')" in nav
    assert "asset_url('/static/favicon.png')" in nav
    for sheet in ("static/css/landing.css", "static/css/public-pages.css"):
        css = re.sub(r"/\*.*?\*/", "", read(sheet), flags=re.S)
        assert not re.search(r"(?m)^html\s*\{[^}]*scroll-behavior:\s*smooth", css), sheet
        assert re.search(r"html\.is-scroll-smooth\s*\{\s*scroll-behavior:\s*smooth", css), sheet
        assert re.search(r"html\s*\{\s*scroll-padding-top:\s*54px", css), sheet
    script = read("static/js/public-nav.js")
    assert 'classList.add("is-scroll-smooth")' in script
    assert 'addEventListener("load", enableSmoothScroll)' in script


def test_every_bar_link_keeps_the_width_of_its_semibold_self():
    """The current section is semibold, which is wider: the landing bar
    twitched sideways while scrolling into Watches. Each bar link carries its
    own text as data-label; an invisible semibold line reserves the width."""
    nav = read("templates/partials/public_nav.html")
    bar = nav.split('<div class="nav-links', 1)[1].split("<details", 1)[0]
    links = re.findall(r"<a ([^>]*)>([^<]+)</a>", bar)
    assert len(links) == 5
    for attributes, text in links:
        assert f'data-label="{text}"' in attributes, text
    tokens = re.sub(r"/\*.*?\*/", "", read("static/css/public-tokens.css"), flags=re.S)
    rule = tokens.split(".nav-links > a[data-label]::after {", 1)[1].split("}", 1)[0]
    assert "content: attr(data-label)" in rule
    assert "visibility: hidden" in rule and "height: 0" in rule
    assert "font-weight: var(--font-weight-semibold)" in rule


def test_public_pages_keep_the_page_grid_and_the_bar_on_a_phone():
    """I14: one grid and one bar. The phone block of public-pages.css set its
    own 12 px column, a 50 px bar with 14 px padding and a smaller mark."""
    css = re.sub(r"/\*.*?\*/", "", read("static/css/public-pages.css"), flags=re.S)
    assert "100% - 24px" not in css
    assert "min-height: 50px" not in css and "width: 21px" not in css
    assert "100vw - 40px" not in css

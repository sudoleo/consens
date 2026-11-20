"""The landing page is one chat.

templates/landing.html is a claim, a thread of chapters with the field docked
under it and the model families; landing-chat.css lays it out and
landing-chat.js plays it along the scroll. These hold what a later edit must
not lose without anyone looking at the page: the order of the chapters, the
one way into the app, that the page is whole without script, and that every
photo is sized, light and credited.
"""
import re
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
LANDING = (ROOT / "templates" / "landing.html").read_text(encoding="utf-8")
STYLES = (ROOT / "static" / "css" / "landing-chat.css").read_text(encoding="utf-8")
SCRIPT = (ROOT / "static" / "js" / "landing-chat.js").read_text(encoding="utf-8")
PHOTOS = ROOT / "static" / "landing"


def test_the_page_is_a_claim_and_one_thread_of_chapters():
    assert LANDING.count("<h1") == 1
    chapters = re.findall(r'<section class="lc-part[^"]*" id="([a-z]+)">', LANDING)
    assert chapters == ["workspace", "review", "files", "browser", "watch", "models"]
    # One heading a chapter and the last line of the page.
    assert LANDING.count('<h2 class="lc-h2">') == len(chapters) + 1
    # Nothing stands beside the thread: the page has no second column and
    # none of the sections it had before it became a chat.
    for gone in ("lp-shell", "lp-scroll-scene", "lp-steps", 'id="benchmark"', "data-scene"):
        assert gone not in LANDING, gone


def test_the_docked_field_is_the_one_way_into_the_app():
    # The bar's own button comes from the shared partial.
    assert LANDING.count('href="/app') == 1
    assert '<a id="landingField" class="lp-composer lc-composer" href="/app?focus=1"' in LANDING
    assert LANDING.index('class="lc-dock"') > LANDING.index("lc-beat--end")
    assert ".lc-dock {\n  position: sticky;\n  bottom: 0;" in STYLES
    # With the mark set the app does not send the visitor back here.
    assert '["landingField", "navCtaButton"]' in SCRIPT and '"skipLandingRedirect", "1"' in SCRIPT


def test_the_docked_field_is_one_row_until_it_rests():
    # One row is what the style sheet draws by itself; the two rows stand
    # under the class the script sets once the dock rests.
    assert ".lc-composer .lp-composer-row { display: contents; }" in STYLES
    assert ".lc-dock.is-end .lc-composer { flex-wrap: wrap;" in STYLES
    # The mark that says the dock rests stands right under it.
    assert '</a>\n    </div>\n    <span class="lc-dock-rest" aria-hidden="true"></span>' in LANDING
    # The room the two rows take is kept above the one-row field and lets
    # clicks through to the thread.
    assert "padding: calc(10px + var(--lc-rise, 0px)) 0 max(16px, env(safe-area-inset-bottom));" in STYLES
    assert "pointer-events: none;" in STYLES.split(".lc-dock {", 1)[1].split("}", 1)[0]
    # A reader who asked for less motion still gets both forms: the field
    # is set up before the script stops for them.
    assert SCRIPT.index("observe(rest)") < SCRIPT.index("if (reduced) return;")


def test_the_page_stands_whole_without_the_script():
    # Nothing in the markup is hidden or waiting for a state.
    assert " hidden" not in LANDING
    assert "data-phase" not in LANDING
    assert 'data-watch data-state="watching"' in LANDING
    # Every state before the last frame belongs to the script: it stands
    # under .lc-js, in each selector of the rule.
    for line in STYLES.splitlines():
        if "{" not in line:
            continue
        selector = line.split("{", 1)[0]
        if "[data-reveal]" in selector or ':not([data-phase="found"])' in selector:
            assert all(part.strip().startswith(".lc-js ") for part in selector.split(",")), line
    # And the script sets that class only for a reader who did not ask for
    # less motion.
    assert SCRIPT.index("prefers-reduced-motion: reduce") < SCRIPT.index('root.classList.add("lc-js")')


def test_the_reviewed_plan_is_the_plan_the_agent_wrote():
    rows = re.findall(r"<tr[^>]*><td>(Day \d)</td><td>(.*?)</td></tr>", LANDING)
    words = [(day, re.sub(r"<[^>]+>", "", text)) for day, text in rows]
    assert len(words) == 11
    assert words[:5] == words[5:10]
    # The review marks one place, the day the correction replaces.
    assert LANDING.count("cx-claim is-audit is-major") == 1
    assert words[10][0] == "Day 3" and words[10][1] != words[2][1]


def test_every_photo_is_sized_light_and_credited():
    tags = re.findall(r"<img[^>]*/static/landing/[^>]*>", LANDING)
    names = [re.search(r"/static/landing/([a-z-]+\.jpg)", tag).group(1) for tag in tags]
    assert sorted(names) == sorted(path.name for path in PHOTOS.glob("*.jpg"))
    for tag, name in zip(tags, names):
        assert f"asset_url('/static/landing/{name}')" in tag, name
        assert (PHOTOS / name).stat().st_size <= 400_000, name
        with Image.open(PHOTOS / name) as image:
            # The page reserves the picture's room before it has loaded.
            assert f'width="{image.width}" height="{image.height}"' in tag, name
        assert re.search(r'alt="[^"]{12,}"', tag), name
        assert 'loading="lazy"' in tag, name
    # Who took a picture and under which licence, each with its link.
    assert LANDING.count("https://commons.wikimedia.org/wiki/File:") == len(names)
    assert LANDING.count("https://creativecommons.org/licenses/") == LANDING.count('class="lc-credit"')

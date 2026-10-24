"""The skip link of the public pages (a11y audit P3).

The bar of the public pages put 7-8 tab stops before the content of every
page. Its partial now opens with a skip link to #main, which only works if
every page that includes the bar names its <main> that way.
"""

import re
from pathlib import Path

TEMPLATES = Path(__file__).resolve().parents[1] / "templates"


def test_the_bar_opens_with_a_skip_link():
    partial = (TEMPLATES / "partials" / "public_nav.html").read_text(encoding="utf-8")
    markup = re.sub(r"\{#.*?#\}", "", partial, flags=re.S)
    first_tag = re.search(r"<(?!script)[a-z]+[^>]*>", markup.split("{% set", 1)[-1].split("%}", 1)[-1])
    assert first_tag.group(0) == '<a class="skip-link" href="#main">'


def test_every_page_with_the_bar_has_one_main_named_main():
    pages = [path for path in sorted(TEMPLATES.glob("*.html"))
             if "partials/public_nav.html" in path.read_text(encoding="utf-8")]
    assert len(pages) >= 15
    for path in pages:
        mains = re.findall(r"<main(?=[\s>])[^>]*>", path.read_text(encoding="utf-8"))
        assert len(mains) == 1 and 'id="main"' in mains[0], (path.name, mains)

"""page_has_math decides whether a public page loads KaTeX.

A miss would show raw LaTeX until math-render.js loads KaTeX itself, so the
check has to cover every form math-render.js typesets.
"""

import pytest
from jinja2 import Environment

from app.core.math_assets import contains_math, register_math_globals


@pytest.mark.parametrize("text", [
    r"The map \(F:\mathbb C^3\to\mathbb C^3\)",
    r"\[ \det(DF)=-2 \]",
    "$$x^2$$",
    r"\begin{align} a &= b \end{align}",
    r"costs $5 and $x^2$ more",
    r"inline $\alpha$",
    r"escaped dollar inside $a\$b_1$",
])
def test_formulas_are_found(text):
    assert contains_math(text)


@pytest.mark.parametrize("text", [
    "Photosynthese wandelt Licht in Energie um.",
    "6,7 Mrd. $ in Q1 gegenueber 6,7 Mrd. $ in Q2",
    "Price: $5 to $10",
    "a_b and c^d without dollars",
    "$x\ny_1$",
])
def test_plain_text_and_currency_are_not_math(text):
    assert not contains_math(text)


def test_nested_context_values_are_scanned():
    assert contains_math({"differences": [{"claim": r"we get \(x\)"}]})
    assert not contains_math({"count": 3, "items": ("a", None), "flag": True})


def test_jinja_global_sees_route_context_and_includes():
    env = Environment()

    class Templates:
        pass

    templates = Templates()
    templates.env = env
    register_math_globals(templates)
    env.globals["organization_jsonld"] = '{"name": "consens.io"}'
    page = env.from_string("{% if page_has_math() %}katex{% else %}none{% endif %}")
    assert page.render(answer_html="<p>plain</p>") == "none"
    assert page.render(answer_html=r"<p>\(x^2\)</p>") == "katex"
    local = env.from_string(r"{% set lead = '$$a$$' %}{{ 'katex' if page_has_math() else 'none' }}")
    assert local.render() == "katex"


def test_json_ld_escapes_do_not_count_as_latex():
    env = Environment()

    class Templates:
        pass

    templates = Templates()
    templates.env = env
    register_math_globals(templates)
    page = env.from_string("{{ 'katex' if page_has_math() else 'none' }}")
    escaped = r'{"text":"Kostet $5 f\u00fcr Kinder.\nSonst $10"}'
    assert contains_math(escaped)  # what the unfiltered scan would have said
    assert page.render(jsonld=escaped, answer_html="<p>Kostet $5 für Kinder.</p>") == "none"
    assert page.render(jsonld=escaped, answer_html=r"<p>\(x\)</p>") == "katex"

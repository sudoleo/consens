"""Load KaTeX on public pages only when the page has a formula.

KaTeX is a render-blocking stylesheet plus ~270 KB of deferred JavaScript.
Share, Topic and Watch pages are where new visitors land, and almost none of
them contain math, so the templates include ``partials/katex.html``, which
emits the KaTeX tags only when ``page_has_math()`` finds a formula in the
template context.

The check is a deliberate superset of what ``static/js/math-render.js``
renders: a false positive only loads KaTeX as before. A miss is not fatal
either -- the partial always names the asset URLs, and math-render.js loads
KaTeX itself when it finds a formula on a page without it.
"""

from __future__ import annotations

import re

from jinja2 import pass_context

# Delimiters KaTeX's auto-render knows (see ``delimiters`` in math-render.js).
_DELIMITER = re.compile(r"\$\$|\\\(|\\\[|\\begin\{")
# "$...$" on one line, at most 200 characters, with a LaTeX signal inside --
# the form math-render.js converts to "\(...\)". The lookahead finds
# overlapping pairs, so "$5 and $x^2$" is still seen.
_DOLLAR_PAIR = re.compile(r"(?=\$((?:[^$\n\\]|\\[^\n]){1,200}?)\$)")
_LATEX_SIGNAL = re.compile(r"\\[A-Za-z]|[\^_{}]")

_MAX_DEPTH = 8


def contains_math(value, _depth: int = 0) -> bool:
    """True when a string anywhere in ``value`` may hold a formula."""

    if isinstance(value, str):
        if "$" not in value and "\\" not in value:
            return False
        if _DELIMITER.search(value):
            return True
        return any(
            _LATEX_SIGNAL.search(match.group(1))
            for match in _DOLLAR_PAIR.finditer(value)
        )
    if _depth >= _MAX_DEPTH:
        return False
    if isinstance(value, dict):
        return any(contains_math(item, _depth + 1) for item in value.values())
    if isinstance(value, (list, tuple, set, frozenset)):
        return any(contains_math(item, _depth + 1) for item in value)
    return False


@pass_context
def page_has_math(context) -> bool:
    """Jinja global: scan the variables the route passed to the template."""

    # ``context.vars`` holds template-local {% set %}s, ``parent`` the route
    # context plus the env globals (functions and site-wide JSON-LD).
    return contains_math(_page_values(context.parent)) or contains_math(_page_values(context.vars))


def _page_values(variables) -> dict:
    # JSON-LD repeats page text JSON-escaped: "für" and a literal "\n"
    # look like LaTeX commands, so "$5 für $10" would count as a
    # formula. The same text is in the HTML fields, which are scanned.
    return {key: value for key, value in variables.items() if not key.endswith("jsonld")}


def register_math_globals(templates) -> None:
    templates.env.globals["page_has_math"] = page_has_math

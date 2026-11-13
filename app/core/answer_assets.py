"""Load the scripts for an answer's blocks on public pages only when needed.

A shared answer shows a ```mermaid block as its diagram, a code block
with its syntax tones and its tables and numbered lists in their shapes,
like the app (static/js/diagram-render.js, code-highlight.js,
answer-shapes.js). Most pages need few of them, so the templates include
``partials/answer_blocks.html``, which emits each script only when the
rendered answer carries the mark ``public_markdown`` leaves on such a block
(for the shapes: a table or a numbered list at all).
"""

from __future__ import annotations

import re

from jinja2 import pass_context

# What public_markdown.render_public_markdown writes for a diagram block
# and for a code block in a language it lets through.
DIAGRAM_MARK = 'class="language-mermaid"'
_CODE_MARK = re.compile(r'class="language-(?!mermaid")')

_MAX_DEPTH = 8


def _contains(value, found, depth: int = 0) -> bool:
    """True when ``found`` holds for a string anywhere in ``value``."""

    if isinstance(value, str):
        return found(value)
    if depth >= _MAX_DEPTH:
        return False
    if isinstance(value, dict):
        return any(_contains(item, found, depth + 1) for item in value.values())
    if isinstance(value, (list, tuple, set, frozenset)):
        return any(_contains(item, found, depth + 1) for item in value)
    return False


def contains_diagram(value) -> bool:
    return _contains(value, lambda text: DIAGRAM_MARK in text)


def contains_code(value) -> bool:
    return _contains(value, lambda text: bool(_CODE_MARK.search(text)))


def contains_shapes(value) -> bool:
    """A table or a numbered list: what static/js/answer-shapes.js may draw."""

    return _contains(value, lambda text: "<table" in text or "<ol" in text)


@pass_context
def page_has_diagram(context) -> bool:
    """Jinja global: scan the variables the route passed to the template."""

    return contains_diagram(dict(context.parent)) or contains_diagram(dict(context.vars))


@pass_context
def page_has_code(context) -> bool:
    """Jinja global: a code block in a language the page can highlight."""

    return contains_code(dict(context.parent)) or contains_code(dict(context.vars))


@pass_context
def page_has_shapes(context) -> bool:
    """Jinja global: a table or a numbered list in the rendered answer."""

    return contains_shapes(dict(context.parent)) or contains_shapes(dict(context.vars))


def register_answer_globals(templates) -> None:
    templates.env.globals["page_has_diagram"] = page_has_diagram
    templates.env.globals["page_has_code"] = page_has_code
    templates.env.globals["page_has_shapes"] = page_has_shapes

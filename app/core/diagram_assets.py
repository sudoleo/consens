"""Load the diagram script on public pages only when the page has a diagram.

A shared answer shows a ```mermaid block as its diagram, like the app
(static/js/diagram-render.js). Almost no page has one, so the templates
include ``partials/diagrams.html``, which emits the script only when the
rendered answer carries the mark ``public_markdown`` leaves on such a block.
"""

from __future__ import annotations

from jinja2 import pass_context

# What public_markdown.render_public_markdown writes for a diagram block.
DIAGRAM_MARK = 'class="language-mermaid"'

_MAX_DEPTH = 8


def contains_diagram(value, _depth: int = 0) -> bool:
    """True when a string anywhere in ``value`` holds a diagram block."""

    if isinstance(value, str):
        return DIAGRAM_MARK in value
    if _depth >= _MAX_DEPTH:
        return False
    if isinstance(value, dict):
        return any(contains_diagram(item, _depth + 1) for item in value.values())
    if isinstance(value, (list, tuple, set, frozenset)):
        return any(contains_diagram(item, _depth + 1) for item in value)
    return False


@pass_context
def page_has_diagram(context) -> bool:
    """Jinja global: scan the variables the route passed to the template."""

    return contains_diagram(dict(context.parent)) or contains_diagram(dict(context.vars))


def register_diagram_globals(templates) -> None:
    templates.env.globals["page_has_diagram"] = page_has_diagram

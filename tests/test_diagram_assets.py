"""page_has_diagram decides whether a public page loads diagram-render.js,
and public_markdown marks the blocks it draws."""

from jinja2 import Environment

from app.core.diagram_assets import contains_diagram, register_diagram_globals
from app.services.public_markdown import render_public_markdown

FENCE = "```"


def _block(source, language="mermaid", fence=FENCE):
    return f"{fence}{language}\n{source}\n{fence}"


def test_only_a_closed_mermaid_block_keeps_its_mark():
    html = render_public_markdown(f"Text\n\n{_block('flowchart LR\n  A --> B')}\n\nEnd")
    assert '<pre><code class="language-mermaid">flowchart LR\n  A --&gt; B\n</code></pre>' in html
    assert contains_diagram(html)
    # As in the app (markdown-stream.js fenceClosed): half a diagram is code.
    cut_off = render_public_markdown(f"Text\n\n{FENCE}mermaid\nflowchart LR\n  A --> B")
    assert "language-mermaid" not in cut_off and "<pre><code>flowchart LR" in cut_off
    # No other code block carries a class: nothing on the page reads one.
    for other in (_block("print(1)", "python"), _block("pie", "mermaidjs"), "    indented code"):
        assert "class=" not in render_public_markdown(other)


def test_a_diagram_is_found_whatever_the_fence_and_wherever_it_stands():
    for text in (_block("pie", "Mermaid"), _block("pie", "mermaid title", fence="~~~~"),
                 "> " + _block("pie").replace("\n", "\n> "),
                 "- item\n\n  " + _block("pie").replace("\n", "\n  ")):
        assert 'class="language-mermaid"' in render_public_markdown(text), text


def test_a_model_cannot_write_the_mark_itself():
    # html=False: markup in the answer is text, and nh3 keeps no other class.
    html = render_public_markdown('<pre><code class="language-mermaid">pie</code></pre>\n\n`x`{.language-mermaid}')
    assert "<code class=" not in html


def test_nested_context_values_are_scanned():
    mark = '<pre><code class="language-mermaid">pie\n</code></pre>'
    assert contains_diagram({"turns": [{"answer_html": mark}]})
    assert not contains_diagram({"count": 3, "items": ("<pre><code>pie</code></pre>", None), "flag": True})


def test_jinja_global_sees_route_context_and_includes():
    env = Environment()

    class Templates:
        pass

    templates = Templates()
    templates.env = env
    register_diagram_globals(templates)
    page = env.from_string("{% if page_has_diagram() %}diagrams{% else %}none{% endif %}")
    assert page.render(answer_html="<p>plain</p>") == "none"
    assert page.render(answer_html='<pre><code class="language-mermaid">pie\n</code></pre>') == "diagrams"

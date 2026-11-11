"""page_has_diagram and page_has_code decide whether a public page loads
diagram-render.js and code-highlight.js, and public_markdown marks the blocks
they read."""

from jinja2 import Environment

from app.core.answer_assets import contains_code, contains_diagram, register_answer_globals
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
    # A language nothing on the page reads carries no class.
    for other in (_block("+[>+<-]", "brainfuck"), _block("pie", "mermaidjs"), "    indented code", _block("plain", "")):
        assert "class=" not in render_public_markdown(other)


def test_a_closed_block_in_a_known_language_keeps_it_for_its_syntax_tones():
    html = render_public_markdown(f"Text\n\n{_block('print(1)', 'Python title')}")
    assert '<pre><code class="language-python">print(1)\n</code></pre>' in html
    assert contains_code(html) and not contains_diagram(html)
    assert 'class="language-c++"' in render_public_markdown(_block("int x;", "c++"))
    # Cut off inside the block: plain, as in the app.
    cut_off = render_public_markdown(f"{FENCE}python\nprint(1)")
    assert "class=" not in cut_off and not contains_code(cut_off)
    # A diagram is no code to highlight: a page of only diagrams loads no highlighter.
    assert not contains_code(render_public_markdown(_block("pie")))


def test_a_diagram_is_found_whatever_the_fence_and_wherever_it_stands():
    for text in (_block("pie", "Mermaid"), _block("pie", "mermaid title", fence="~~~~"),
                 "> " + _block("pie").replace("\n", "\n> "),
                 "- item\n\n  " + _block("pie").replace("\n", "\n  ")):
        assert 'class="language-mermaid"' in render_public_markdown(text), text


def test_a_model_cannot_write_the_mark_itself():
    # html=False: markup in the answer is text, and nh3 keeps no other class.
    html = render_public_markdown('<pre><code class="language-mermaid">pie</code></pre>\n\n`x`{.language-python}')
    assert "<code class=" not in html


def test_nested_context_values_are_scanned():
    mark = '<pre><code class="language-mermaid">pie\n</code></pre>'
    assert contains_diagram({"turns": [{"answer_html": mark}]})
    assert not contains_diagram({"count": 3, "items": ("<pre><code>pie</code></pre>", None), "flag": True})
    assert contains_code({"turns": [{"answer_html": '<pre><code class="language-sql">select 1\n</code></pre>'}]})
    assert not contains_code({"turns": [{"answer_html": mark}], "count": 3})


def test_jinja_globals_see_route_context_and_includes():
    env = Environment()

    class Templates:
        pass

    templates = Templates()
    templates.env = env
    register_answer_globals(templates)
    page = env.from_string("{{ 'diagrams' if page_has_diagram() else '' }}{{ 'code' if page_has_code() else '' }}")
    assert page.render(answer_html="<p>plain</p><pre><code>x</code></pre>") == ""
    assert page.render(answer_html='<pre><code class="language-mermaid">pie\n</code></pre>') == "diagrams"
    assert page.render(answer_html='<pre><code class="language-ts">let a;\n</code></pre>') == "code"

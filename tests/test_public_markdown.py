

def test_citations_to_excluded_sources_are_dropped_not_shown_raw():
    from app.services.public_markdown import render_public_markdown
    sources = [{"id": "S1", "url": "https://agency.example/report", "title": "Agency"}]
    excluded = [{"id": "S3", "url": "https://news.example/story", "title": "News"}]
    html = render_public_markdown("Prices rose [S1, S3]. Also reported [S3].", sources, excluded_sources=excluded)
    assert "S3" not in html and "[3]" not in html
    assert "#src-1" in html


def test_latex_in_bare_brackets_becomes_display_math_but_links_stay():
    from app.services.public_markdown import render_public_markdown
    html = render_public_markdown(
        "So, [\n" r"P(\text{a}\mid b) =\frac12." "\n] Rest [S1] and " r"[a \LaTeX guide](https://e.example)."
    )
    assert r"\[" "\n" r"P(\text{a}\mid b) =\frac12." "\n" r"\]" in html
    assert '<a href="https://e.example"' in html
    assert "[S1]" in html

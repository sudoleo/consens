from app.services.public_markdown import render_public_markdown, markdown_to_plaintext
from app.services.share_snapshots import build_citation


SOURCES = [
    {"id": "S1", "url": "https://github.com/example/project", "title": "GitHub"},
    {"id": "S2", "url": "https://glitchwire.com/article", "title": "An article"},
]


def test_legacy_citations_are_numbered_without_removing_actual_words():
    html = render_public_markdown(
        "GitHub and Glitchwire are mentioned in this sentence. [S1][S2] "
        "[githubgithub](https://github.com/example/project) "
        "[glitchwire](https://glitchwire.com/article)", SOURCES,
    )
    assert "GitHub and Glitchwire are mentioned in this sentence." in html
    assert "githubgithub" not in html
    assert ">glitchwire<" not in html
    assert html.count('href="#src-1"') == 2
    assert html.count('href="#src-2"') == 2
    assert ">[1]<" in html and ">[2]<" in html


def test_duplicate_reference_ids_are_collapsed_but_distinct_sources_survive():
    html = render_public_markdown("Claim. [S1, S1, S2]", SOURCES)
    assert html.count('href="#src-1"') == 1
    assert html.count('href="#src-2"') == 1


def test_descriptive_links_unknown_references_and_code_are_preserved():
    text = ("[Read the project documentation](https://github.com/example/project) "
            "[S1](https://unknown.example/page) [S99] `githubgithub [S1]`\n\n"
            "```\n[S2]\n```")
    html = render_public_markdown(text, SOURCES)
    assert ">Read the project documentation<" in html
    assert 'href="https://unknown.example/page"' in html
    assert "[S99]" in html and "<code>githubgithub [S1]</code>" in html
    assert "<code>[S2]" in html
    assert "#src-" not in html


def test_copied_citation_points_to_exact_version_without_redirect_tokens():
    url = "https://www.consens.io/s/example-id?version=run-123"
    citation = build_citation({
        "included_models": ["OpenAI", "Gemini"],
        "answered_at": "2026-09-11", "question": "Example?",
        "sources": [{"id": "S1", "url": "https://vertexaisearch.cloud.google.com/grounding-api-redirect/long-token"}],
    }, url)
    assert url + "#shareSources" in citation
    assert "vertexaisearch" not in citation
    assert "long-token" not in citation


def test_search_snippet_omits_known_citation_labels_but_keeps_real_mentions():
    text = markdown_to_plaintext(
        "GitHub is mentioned. [githubgithub](https://github.com/example/project) "
        "Another claim. [glitchwire](https://glitchwire.com/article)", sources=SOURCES,
    )
    assert text == "GitHub is mentioned. Another claim."



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


def test_chat_framing_around_a_published_answer_is_dropped_but_the_answer_stays():
    from app.services.public_markdown import lead_sentences, strip_chat_framing

    # The real opening of /topics/gemini-4-release-date on 2026-10-14.
    md = (
        "Here’s the current evidence-based picture of Google Gemini 4 as of 2026-10-14:\n\n"
        "## Short answer\nGoogle has **officially announced Gemini 4**. Argon is the only variant.\n\n"
        "## Pricing\n\n$2 per 1M input tokens.\n\n"
        "If you want, I can also turn this into a one-table fact sheet."
    )
    clean = strip_chat_framing(md)
    assert clean.startswith("Google has **officially announced Gemini 4**.")
    assert "## Pricing" in clean
    assert "If you want" not in clean and "Here’s" not in clean
    assert lead_sentences(md) == "Google has officially announced Gemini 4. Argon is the only variant. $2 per 1M input tokens."

    # Only pure framing goes: an answer that merely starts with "Here" or
    # ends with an ordinary sentence keeps every word.
    assert strip_chat_framing("Here the models disagree.\n\nThey do.") == "Here the models disagree.\n\nThey do."
    assert strip_chat_framing("Yes.\n\nThat is all.") == "Yes.\n\nThat is all."
    # A lone framing paragraph is never turned into an empty answer.
    assert strip_chat_framing("If you want, I can help.") == "If you want, I can help."
    # "If you want ..." as advice is the answer, not an offer.
    advice = "Both work.\n\nIf you want the cheapest option, use X.\n\nIf you want the strongest, use Y."
    assert strip_chat_framing(advice) == advice
    assert strip_chat_framing("Both work.\n\nIf you'd like, want me to compare prices?") == "Both work."
    assert strip_chat_framing("## Short answer\n\nYes.") == "Yes."
    # Right after a one-paragraph lead-in it is framing too.
    assert strip_chat_framing("Views split three ways:\n\n## Short answer\n\n- Labs: 2027") == (
        "Views split three ways:\n\n- Labs: 2027"
    )
    # Further down it is the answer's own structure and stays.
    assert "## Short answer" in strip_chat_framing("A.\n\nB.\n\n## Short answer\n\nC.")


def test_lead_sentences_cut_at_a_sentence_end_and_skip_headings():
    from app.services.public_markdown import lead_sentences

    assert lead_sentences("## Current consensus\n\nNo confirmed release date exists.") == (
        "No confirmed release date exists."
    )
    long = "First sentence is here. " + "word " * 60
    assert lead_sentences(long, limit=60) == "First sentence is here."
    assert lead_sentences("word " * 60, limit=40).endswith("…")


def test_plain_text_is_text_not_html():
    # Templates escape it once more: "AT&amp;T" stood on the Topic hub cards
    # and in every meta and og:description ("AT&amp;amp;T" in the markup).
    from app.services.public_markdown import lead_sentences, markdown_to_plaintext

    assert markdown_to_plaintext("**AT&T** and R&D: 5 < 7 > 3, \"quoted\" `<b>`") == (
        'AT&T and R&D: 5 < 7 > 3, "quoted" <b>'
    )
    assert lead_sentences("AT&T cut prices. More follows here.", limit=20, min_sentence=5) == "AT&T cut prices."

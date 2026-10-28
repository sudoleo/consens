

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


def test_checklist_items_show_a_box_instead_of_their_brackets():
    from app.services.public_markdown import render_public_markdown
    html = render_public_markdown(
        "- [ ] Renew the passport\n- [x] Book **the train**\n- Bring snacks\n\n1. [ ] Numbered step\n\n"
        "- [ ]\n\n```\n- [ ] code stays\n```\n"
    )
    assert '<ul class="md-task-list">' in html
    assert ('<li class="md-task-item"><span class="md-task-box" role="img" aria-label="Open" '
            'data-checked="false"></span>Renew the passport</li>') in html
    assert 'aria-label="Done" data-checked="true"></span>Book <strong>the train</strong>' in html
    assert "<li>Bring snacks</li>" in html
    # A numbered list keeps its numbers; the box leads the words.
    assert '<ol>\n<li class="md-task-item"><span class="md-task-box"' in html
    # No words after the box: not an item. Code stays code.
    assert "<li>[ ]</li>" in html
    assert "- [ ] code stays" in html


def test_notifications_draw_a_checklist_box_as_a_character():
    from app.services.mailer import MAIL_PALETTE
    from app.services.notification_markdown import answer_mail_html, answer_plain
    md = "- [ ] Renew the passport\n- [x] Book the train\n"
    mail = answer_mail_html(md, palette=MAIL_PALETTE)
    assert "☐ Renew the passport" in mail and "☑ Book the train" in mail
    plain = answer_plain(md)
    assert "☐ Renew the passport" in plain and "☑ Book the train" in plain


def test_plain_text_is_text_not_html():
    # Templates escape it once more: "AT&amp;T" stood on the Topic hub cards
    # and in every meta and og:description ("AT&amp;amp;T" in the markup).
    from app.services.public_markdown import lead_sentences, markdown_to_plaintext

    assert markdown_to_plaintext("**AT&T** and R&D: 5 < 7 > 3, \"quoted\" `<b>`") == (
        'AT&T and R&D: 5 < 7 > 3, "quoted" <b>'
    )
    assert lead_sentences("AT&T cut prices. More follows here.", limit=20, min_sentence=5) == "AT&T cut prices."


def test_a_shared_agent_answer_cites_its_sources_as_pills_like_the_app():
    # sources.js linkifyAgentSources, on the server: the words stay, the source
    # follows as a pill; a link that only names its domain becomes the pill.
    from app.services.public_markdown import render_public_markdown
    sources = [{"id": "S1", "url": "https://www.uni-hannover.de/news/hoi", "title": "Founding"},
               {"id": "S2", "url": "https://njaped.no/", "title": "njaped"},
               {"id": "S3", "url": "https://example.org/a", "title": "A"},
               {"id": "S4", "url": "https://example.com/b", "title": "B"}]
    md = ("Founded 2018 ([founding note](https://www.uni-hannover.de/news/hoi)). "
          "Read [njaped.no](https://njaped.no/). "
          "See [example.org](https://example.org/a), [example.com](https://example.com/b). "
          "Elsewhere: [here](https://other.example/x). Last [report](https://example.org/a).")
    html = render_public_markdown(md, sources, source_pills=True)

    pill = '<a class="src-ref" href="https://www.uni-hannover.de/news/hoi" target="_blank"'
    assert "(founding note" + pill in html
    assert '<span class="src-ref-label">uni-hannover.de</span></a>).' in html
    assert "Read " + '<a class="src-ref" href="https://njaped.no/"' in html
    assert '>njaped.no</span></a>.' in html and ">njaped.no</a>" not in html
    # Side by side: one pill, "+1".
    assert '<span class="src-ref-label">example.org</span><span class="src-ref-more">+1</span></a>.' in html
    assert 'href="https://example.com/b"' not in html
    # The point before the pill that ends a sentence; other links stay links.
    assert "Last report.<a class=\"src-ref\"" in html
    assert '<a href="https://other.example/x" rel="nofollow noopener noreferrer">here</a>' in html
    assert 'src="/api/topics/favicon?d=example.org"' in html

    # Without the flag (Consensus and Watch pages) nothing changes.
    assert "src-ref" not in render_public_markdown(md, sources)


# A long group of markers without a point was tried again from each marker
# and each blank before it: 4,000 markers took 5.7 s on a share page, which
# renders without a cache (2026-10-22). The point is optional now, the
# matches are those of the old pattern.
_OLD_TERMINAL_SOURCE_ORDER = (
    r"[ \t]*((?:\[(?:S?\d+)(?:\s*,\s*S?\d+)*\][ \t]*)*\[(?:S?\d+)(?:\s*,\s*S?\d+)*\])"
    r"([.!?]+(?:[\"'”’)\]}]+)?)(?=\s|$)"
)


def test_markers_before_the_sentence_end_move_as_before_in_linear_time():
    import random
    import re
    import time
    from app.services.public_markdown import _TERMINAL_SOURCE_ORDER_RE, render_public_markdown

    old = re.compile(_OLD_TERMINAL_SOURCE_ORDER, re.IGNORECASE)

    def move(pattern, text):
        return pattern.sub(lambda m: m[2] + m[1] if m[2] else m[0], text)

    rng = random.Random(20261028)
    pieces = ["[1]", "[S2]", "[3, S4]", "[x]", "[Text]", " ", "\t", "  ", ".", "!", "?", "”", ")", "]",
              "[", "a", "Claim", "\n", ",", "(", "[1](u)"]
    for _ in range(20_000):
        text = "".join(rng.choice(pieces) for _ in range(rng.randint(1, 14)))
        assert move(_TERMINAL_SOURCE_ORDER_RE, text) == move(old, text), text
    assert move(_TERMINAL_SOURCE_ORDER_RE, "See [Text][1]. Claim [S1] [S2].") == "See [Text].[1] Claim.[S1] [S2]"

    sources = [{"id": "S1", "url": "https://agency.example/report", "title": "Agency"}]
    started = time.perf_counter()
    html = render_public_markdown("Claim " + "[S1]" * 8_000 + " " * 8_000 + "end", sources)
    assert time.perf_counter() - started < 2
    assert "#src-1" in html

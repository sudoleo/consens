"""Decode real cards and assert content, without platform-specific raster hashes."""
from datetime import datetime, timezone
from io import BytesIO
from unittest.mock import Mock
import pytest
from PIL import Image, ImageDraw, ImageChops
from app.services import og_image

pytestmark = pytest.mark.skipif(not og_image.is_available(), reason="Pillow/Font fehlt")

BASE = dict(
    question="Is this the distinctive test question?",
    score=71,
    model_count=3,
    contradiction_count=2,
    checked_label="",
)
QUESTION_BOX = (og_image.MARGIN, 40, 1200 - og_image.MARGIN, og_image.QUESTION_BOTTOM)
FOOTER_BOX = (0, 505, 1200, 590)


@pytest.fixture(autouse=True)
def clear_cache():
    og_image._cache.clear()
    yield
    og_image._cache.clear()


@pytest.fixture
def drawn(monkeypatch):
    texts = []
    original = ImageDraw.ImageDraw.text

    def record(self, xy, text, *args, **kwargs):
        texts.append(str(text))
        return original(self, xy, text, *args, **kwargs)

    monkeypatch.setattr(ImageDraw.ImageDraw, "text", record)
    return texts


def decoded(png):
    image = Image.open(BytesIO(png))
    assert image.format == "PNG" and image.size == (1200, 630)
    return image.convert("RGB")


def has_color(image, color):
    return any(pixel == color for _, pixel in image.getcolors(1_000_000))


def test_card_draws_question_brand_score_and_facts(drawn):
    image = decoded(og_image.render_share_card(**{**BASE, "checked_label": "Answered Oct 12, 2026"}))
    assert "Is this the distinctive test question?" in " ".join(drawn)
    assert "consens.io" in drawn
    assert "71" in drawn and "/100 agreement" in drawn
    assert {"3 AI models", "2 contradictions", "Answered Oct 12, 2026"} <= set(drawn)
    # The light ground of the brand card, not the old dark scoreboard.
    assert image.getpixel((5, 5)) == og_image.BG
    for box in (QUESTION_BOX, FOOTER_BOX):
        assert len(image.crop(box).getcolors(1_000_000)) > 20
    changed = decoded(og_image.render_share_card(**{**BASE, "question": "A completely different question?"}))
    assert ImageChops.difference(image.crop(QUESTION_BOX), changed.crop(QUESTION_BOX)).getbbox()


@pytest.mark.parametrize("score, color", [
    (71, og_image.AGREE), (65, og_image.AGREE), (64, og_image.PARTIAL),
    (40, og_image.PARTIAL), (39, og_image.DISPUTE), (12, og_image.DISPUTE),
])
def test_the_score_glyph_carries_the_app_traffic_light(score, color):
    footer = decoded(og_image.render_share_card(**{**BASE, "score": score})).crop(FOOTER_BOX)
    assert has_color(footer, color)
    assert not any(has_color(footer, other) for other in
                   {og_image.AGREE, og_image.PARTIAL, og_image.DISPUTE} - {color})


def test_unscored_card_keeps_conflicts_without_inventing_agreement(drawn):
    decoded(og_image.render_share_card(**{**BASE, "score": None}))
    assert not any("/100" in text or text == "0" for text in drawn)
    assert {"3 AI models", "2 contradictions"} <= set(drawn)


def test_long_questions_shrink_before_they_are_cut(drawn):
    long = ("What is the current state of the evidence on whether creatine supplementation "
            "improves cognitive performance in healthy adults, and does it differ for vegetarians?")
    image = decoded(og_image.render_card(question=long, facts=["6 AI models"]))
    assert "…" not in "".join(drawn)
    assert " ".join(long.split()) == " ".join(
        text for text in drawn if text not in {"consens.io", "6 AI models"})
    # The question never runs into the footer.
    gap = image.crop((0, og_image.QUESTION_BOTTOM + 8, 1200, 515))
    assert gap.getcolors(1)[0][1] == og_image.BG

    drawn.clear()
    endless = decoded(og_image.render_card(question="word " * 400, facts=[]))
    assert any(text.endswith("…") for text in drawn)
    gap = endless.crop((0, og_image.QUESTION_BOTTOM + 8, 1200, 515))
    assert gap.getcolors(1)[0][1] == og_image.BG


def test_facts_give_way_from_the_end_but_the_score_stays(drawn):
    decoded(og_image.render_card(
        question="Q?", score=55,
        facts=["6 AI models", "12 contradictions", "Answered September 30, 2026 " * 3],
    ))
    assert "55" in drawn and "/100 agreement" in drawn
    assert not any(text.startswith("Answered") for text in drawn)


def test_cache_tracks_all_rendered_content(monkeypatch):
    render = Mock(wraps=og_image.render_card)
    monkeypatch.setattr(og_image, "render_card", render)
    initial = og_image.share_card_png("share", **BASE)
    assert og_image.share_card_png("share", **BASE) == initial
    assert render.call_count == 1
    for changes in (
        {"question": "Updated question"},
        {"score": 40},
        {"model_count": 4},
        {"contradiction_count": 0},
        {"checked_label": "Answered Oct 1, 2026"},
    ):
        og_image.share_card_png("share", **{**BASE, **changes})
    assert render.call_count == 6
    # Another page with the same text is another card.
    og_image.share_card_png("other", **BASE)
    assert render.call_count == 7


def test_render_failure_is_safe_and_not_cached(monkeypatch, caplog):
    render = Mock(side_effect=[RuntimeError("PRIVATE answer"), b"retry succeeded"])
    monkeypatch.setattr(og_image, "render_card", render)
    assert og_image.share_card_png("share", **BASE) is None
    assert og_image.share_card_png("share", **BASE) == b"retry succeeded"
    assert "PRIVATE" not in caplog.text


def test_date_label_reads_iso_strings_and_datetimes():
    assert og_image.date_label("2026-10-12T08:30:00Z") == "Oct 12, 2026"
    assert og_image.date_label(datetime(2026, 7, 4, tzinfo=timezone.utc)) == "Jul 4, 2026"
    assert og_image.date_label("") == og_image.date_label("not a date") == og_image.date_label(None) == ""


def test_a_word_wider_than_the_card_breaks_instead_of_running_off_it():
    url = "https://example.com/" + "very-long-path-segment-" * 12
    image = decoded(og_image.render_card(question=f"Is {url} trustworthy?", facts=[]))
    # Nothing but ground in the right margin.
    margin = image.crop((1200 - og_image.MARGIN + 4, 0, 1200, og_image.QUESTION_BOTTOM))
    assert margin.getcolors(1)[0][1] == og_image.BG


# WhatsApp shows the card in its composer cut to about 1.6:1, roughly 90 px
# off each side (2026-10-18, the old brand card lost the "T" of its title).
# Everything drawn keeps at least 40 px of air inside that crop.
SAFE_LEFT, SAFE_RIGHT = 130, 1200 - 130


def content_box(image):
    ground = Image.new("RGB", image.size, og_image.BG)
    return ImageChops.difference(image, ground).getbbox()


@pytest.mark.parametrize("card", [
    lambda: og_image.render_brand_card(),
    lambda: og_image.render_share_card(**{**BASE, "checked_label": "Answered Sep 30, 2026"}),
    lambda: og_image.render_card(question="When will GPT-6 be released?", facts=["6 AI models"],
                                 dateline="Checked Oct 15, 2026"),
    lambda: og_image.render_card(question="word " * 400, score=55,
                                 facts=["6 AI models", "12 contradictions"]),
])
def test_every_card_stays_inside_whatsapps_crop(card):
    left, _top, right, _bottom = content_box(decoded(card()))
    assert left >= SAFE_LEFT and right <= SAFE_RIGHT


def test_brand_card_says_the_landing_claim_over_six_marks(drawn):
    image = decoded(og_image.render_brand_card())
    assert drawn == ["consens.io", *og_image.BRAND_HEADLINE]
    assert has_color(image, og_image.INK) and has_color(image, og_image.MUTED)
    # Six marks in one grey row under the claim, centred.
    row = image.crop((0, 470, 1200, 530))
    left, _top, right, _bottom = content_box(row)
    assert has_color(row, og_image.LOGO_GREY)
    assert abs((left + right) / 2 - 600) <= 4
    columns = [x for x in range(left, right) if content_box(row.crop((x, 0, x + 1, 60)))]
    groups = 1 + sum(1 for a, b in zip(columns, columns[1:]) if b - a > 20)
    assert groups == len(og_image.BRAND_LOGOS) == 6

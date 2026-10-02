"""Decode real cards and assert content, without platform-specific raster hashes."""
from io import BytesIO
from unittest.mock import Mock
import pytest
from PIL import Image, ImageDraw, ImageChops
from app.services import og_image

BASE = dict(
    question="Is this the distinctive test question?",
    score=71,
    model_count=3,
    contradiction_count=2,
    history_scores=[],
    checked_label="",
)


@pytest.fixture(autouse=True)
def clear_cache():
    og_image._cache.clear()
    yield
    og_image._cache.clear()


def decoded(png):
    image = Image.open(BytesIO(png))
    assert image.format == "PNG" and image.size == (1200, 630)
    return image.convert("RGB")


def test_renderer_draws_question_score_and_model_facts(monkeypatch):
    texts = []
    original = ImageDraw.ImageDraw.text

    def record(self, xy, text, *args, **kwargs):
        texts.append(str(text))
        return original(self, xy, text, *args, **kwargs)

    monkeypatch.setattr(ImageDraw.ImageDraw, "text", record)
    image = decoded(og_image.render_share_card(**BASE))
    assert "Is this the distinctive test question?" in " ".join(texts)
    assert "71" in texts and "/100 agreement" in texts
    assert any("3 AI models" in text for text in texts)
    assert any("2 contradictions" in text for text in texts)
    # Blank PNG and background-only mutations fail on independent image regions.
    for box in ((72, 150, 1128, 430), (72, 445, 1128, 600)):
        assert len(image.crop(box).getcolors(1_000_000)) > 20
    changed = decoded(
        og_image.render_share_card(
            **{**BASE, "question": "A completely different question?"}
        )
    )
    assert ImageChops.difference(
        image.crop((72, 150, 1128, 430)), changed.crop((72, 150, 1128, 430))
    ).getbbox()


def test_unscored_card_keeps_conflicts_without_inventing_agreement(monkeypatch):
    texts = []
    original = ImageDraw.ImageDraw.text

    def record(self, xy, text, *args, **kwargs):
        texts.append(str(text))
        return original(self, xy, text, *args, **kwargs)

    monkeypatch.setattr(ImageDraw.ImageDraw, "text", record)
    decoded(og_image.render_share_card(**{**BASE, "score": None}))
    assert not any("/100" in text or text == "0" for text in texts)
    assert any("3 AI models" in text and "2 contradictions" in text for text in texts)


def test_cache_tracks_all_rendered_content(monkeypatch):
    render = Mock(wraps=og_image.render_share_card)
    monkeypatch.setattr(og_image, "render_share_card", render)
    initial = og_image.share_card_png("share", **BASE)
    assert og_image.share_card_png("share", **BASE) == initial
    assert render.call_count == 1
    for changes in (
        {"question": "Updated question"},
        {"model_count": 4},
        {"contradiction_count": 0},
        {"history_scores": [20, 50]},
        {"history_scores": [90, 50]},
    ):
        og_image.share_card_png("share", **{**BASE, **changes})
    assert render.call_count == 6


def test_render_failure_is_safe_and_not_cached(monkeypatch, caplog):
    render = Mock(side_effect=[RuntimeError("PRIVATE answer"), b"retry succeeded"])
    monkeypatch.setattr(og_image, "render_share_card", render)
    assert og_image.share_card_png("share", **BASE) is None
    assert og_image.share_card_png("share", **BASE) == b"retry succeeded"
    assert "PRIVATE" not in caplog.text

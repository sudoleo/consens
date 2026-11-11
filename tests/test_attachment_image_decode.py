"""How much of the one server process a picture may take while it is decoded.

A few KB of zeros can claim the pixels of a poster. A JPEG decodes already
reduced; every other format decodes whole, so it gets fewer pixels and, above
the size of a 4K screenshot, one decode at a time.
"""

import io
import threading
import time

import pytest
from PIL import Image, JpegImagePlugin

from app.services.llm import attachments
from app.services.llm.attachments import (IMAGE_FREE_DECODE_PIXELS, IMAGE_MAX_EDGE, IMAGE_MAX_PIXELS_DECODED,
                                          ImagePixelLimitExceeded, shrink_image)


def encoded(size, fmt, mode="L"):
    buffer = io.BytesIO()
    Image.new(mode, size).save(buffer, format=fmt)
    return buffer.getvalue()


def test_a_jpeg_decodes_already_reduced(monkeypatch):
    raw = encoded((6000, 4200), "JPEG")
    loaded = []
    real_load = JpegImagePlugin.JpegImageFile.load

    def load(self):
        result = real_load(self)
        loaded.append(self.size)
        return result

    monkeypatch.setattr(JpegImagePlugin.JpegImageFile, "load", load)
    shrunk, mime = shrink_image(raw, "image/jpeg")
    # 25 MP on disk; in memory the smallest step that still holds the
    # provider's edge, here a quarter of the pixels.
    assert loaded and loaded[0] == (3000, 2100)
    assert mime == "image/jpeg"
    assert max(Image.open(io.BytesIO(shrunk)).size) == IMAGE_MAX_EDGE


def test_the_picture_as_sent_decides_whether_it_is_shrunk():
    # Twice the provider's edge: its reduced decode is exactly that edge and
    # few bytes. It is a large picture all the same and goes out at 1568 px.
    noisy = Image.effect_noise((IMAGE_MAX_EDGE * 2, IMAGE_MAX_EDGE * 2), 60).convert("RGB")
    buffer = io.BytesIO()
    noisy.save(buffer, format="JPEG", quality=95)
    raw = buffer.getvalue()
    shrunk, mime = shrink_image(raw, "image/jpeg")
    assert shrunk != raw
    assert Image.open(io.BytesIO(shrunk)).size == (IMAGE_MAX_EDGE, IMAGE_MAX_EDGE)


def test_a_format_that_decodes_whole_gets_fewer_pixels():
    side = int(IMAGE_MAX_PIXELS_DECODED ** 0.5) + 30
    raw = encoded((side, side), "PNG", "1")
    assert len(raw) < 200_000
    with pytest.raises(ImagePixelLimitExceeded):
        shrink_image(raw, "image/png")
    # The same pixels as a JPEG are within its budget.
    shrunk, _mime = shrink_image(encoded((side, side), "JPEG"), "image/jpeg")
    assert max(Image.open(io.BytesIO(shrunk)).size) == IMAGE_MAX_EDGE


def test_large_whole_decodes_run_one_at_a_time_and_a_screenshot_never_waits():
    side = int(IMAGE_FREE_DECODE_PIXELS ** 0.5) + 200
    large = encoded((side, side), "PNG", "1")
    screenshot = encoded((3840, 2160), "PNG", "1")
    done = []
    with attachments._whole_decodes:
        waiting = threading.Thread(target=lambda: done.append(shrink_image(large, "image/png")[1]))
        waiting.start()
        # The screenshot goes through while the place is taken.
        assert shrink_image(screenshot, "image/png")[1] in {"image/png", "image/jpeg"}
        time.sleep(0.3)
        assert done == []
    waiting.join(timeout=30)
    assert done and not waiting.is_alive()

"""A JPEG decodes no larger than it is needed, whatever its shape or extras.

Two kinds of phone picture missed that. An HDR or depth photo carries further
pictures (MPF); Pillow names it MPO, also where only JPEG was asked for, and
it ran as a format that decodes whole: refused above a few megapixels. A
panorama stayed whole because Pillow's draft reduces only while both sides
keep the size asked for.
"""

import io

import pytest
from PIL import Image, JpegImagePlugin

from app.services import agent_vm_tools, agent_web_images, image_decode, watch_images
from app.services.llm.attachments import IMAGE_MAX_EDGE, shrink_image


def hdr_photo(size=(6000, 4000)):
    """A JPEG with a second picture behind it, as a phone writes its gain map."""
    buffer = io.BytesIO()
    Image.effect_noise(size, 40).convert("RGB").save(
        buffer, format="MPO", save_all=True, quality=30, append_images=[Image.new("RGB", (640, 480))])
    raw = buffer.getvalue()
    with Image.open(io.BytesIO(raw)) as picture:
        assert picture.format == "MPO"
    return raw


def panorama(size=(13000, 3000)):
    buffer = io.BytesIO()
    Image.new("L", size).save(buffer, format="JPEG")
    return buffer.getvalue()


@pytest.fixture
def decoded(monkeypatch):
    """The sizes at which JPEGs were actually decoded."""
    sizes = []
    real_load = JpegImagePlugin.JpegImageFile.load

    def load(self):
        result = real_load(self)
        sizes.append(self.size)
        return result

    monkeypatch.setattr(JpegImagePlugin.JpegImageFile, "load", load)
    return sizes


def test_draft_keeps_the_shape_of_the_picture():
    with Image.open(io.BytesIO(panorama())) as source:
        image_decode.draft(source, (IMAGE_MAX_EDGE, IMAGE_MAX_EDGE))
        assert source.size == (1625, 375)
    # Within the box nothing is reduced.
    with Image.open(io.BytesIO(panorama((1200, 300)))) as source:
        image_decode.draft(source, (IMAGE_MAX_EDGE, IMAGE_MAX_EDGE))
        assert source.size == (1200, 300)


def test_an_attached_hdr_photo_is_a_jpeg(decoded):
    # 24 MP: above what a format that decodes whole may have.
    shrunk, mime = shrink_image(hdr_photo(), "image/jpeg")
    assert decoded[0] == (3000, 2000)
    assert mime == "image/jpeg"
    with Image.open(io.BytesIO(shrunk)) as picture:
        assert picture.format == "JPEG" and max(picture.size) == IMAGE_MAX_EDGE


def test_an_attached_panorama_decodes_reduced(decoded):
    shrunk, _mime = shrink_image(panorama(), "image/jpeg")
    assert decoded[0] == (1625, 375)
    with Image.open(io.BytesIO(shrunk)) as picture:
        assert picture.size == (IMAGE_MAX_EDGE, 362)


def test_the_agent_sees_an_hdr_photo_from_its_computer_smaller(decoded):
    raw = hdr_photo()
    mime, sent = agent_vm_tools.model_picture("image/jpeg", raw)
    assert mime == "image/webp" and len(sent) < len(raw)
    assert decoded[0] == (3000, 2000)


def test_the_agent_sees_a_panorama_decoded_reduced(decoded):
    mime, _sent = agent_vm_tools.model_picture("image/jpeg", panorama())
    assert mime == "image/webp"
    assert decoded[0] == (1625, 375)


def test_an_hdr_photo_from_the_web_is_a_picture(decoded):
    _data, mime, width, height = agent_web_images.encode(hdr_photo())
    assert mime == "image/webp" and (width, height) == (agent_web_images.MAX_SIDE, 1067)
    assert decoded[0] == (3000, 2000)


def test_a_panorama_from_the_web_decodes_reduced(decoded):
    assert agent_web_images.encode(panorama())[2] == agent_web_images.MAX_SIDE
    assert decoded[0] == (1625, 375)


def test_an_hdr_photo_gives_a_thumbnail(decoded):
    data, _size = watch_images.make_thumbnail(hdr_photo())
    with Image.open(io.BytesIO(data)) as picture:
        assert picture.format == "WEBP"
    assert decoded[0][0] < 6000

"""Decoding a JPEG no larger than it is needed."""

# Pillow names a JPEG that carries further pictures (MPF: the gain map of an
# HDR phone photo, a depth map) MPO, also where only JPEG was asked for. Its
# first frame is the photo and decodes like any JPEG.
JPEG_FORMATS = frozenset({"JPEG", "MPO"})


def is_jpeg(source):
    return source.format in JPEG_FORMATS


def draft(source, box):
    """Have the JPEG ``source`` decode at the smallest of its steps (1/2, 1/4,
    1/8) that still fills what fitting it into ``box`` leaves of it.

    Pillow reduces only while BOTH sides keep the size asked for, so asking
    for the box itself leaves a panorama whole.
    """
    width, height = source.size
    ratio = min(box[0] / width, box[1] / height)
    if ratio < 1:
        # Rounded down: rounded up, the shorter side could ask for one step less.
        source.draft("RGB", (max(1, int(width * ratio)), max(1, int(height * ratio))))

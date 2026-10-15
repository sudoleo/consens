"""Set the picture of a Topic by hand: a real picture from one of its sources.

The automatic search (services/topic_images.py) takes what the source pages
offer; when that is a clickbait thumbnail or nothing at all, an editor picks a
real picture from a credible source instead -- never a generated image or a
stock photo. The picture is served by consens.io and links to its page, like
a found one.

Default is a dry run: it fetches the page's preview image (or ``--image``),
crops it (``--crop x0,y0,x1,y1`` in source pixels) and saves the thumbnail to
``--out`` for a look. ``--apply`` stores it on the Topic (Prod write).

    venv\\Scripts\\python.exe scripts\\set_topic_image.py --slug unsolved-math-problems-solved-by-ai \\
        --page https://www.nature.com/articles/d41586-025-02343-x --out _preview\\math.webp
    venv\\Scripts\\python.exe scripts\\set_topic_image.py ... --apply
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from urllib.parse import urljoin

import httpx

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services import topic_images, topics  # noqa: E402

_META_RE = re.compile(
    r'<meta[^>]+(?:property|name)=["\'](?:og:image|twitter:image)(?::src)?["\'][^>]*content=["\']([^"\']+)["\']'
    r'|<meta[^>]+content=["\']([^"\']+)["\'][^>]*(?:property|name)=["\'](?:og:image|twitter:image)["\']',
    re.IGNORECASE,
)
# A plain client: pages that block it are not fetched around.
_HEADERS = {"User-Agent": "consensio-topic-image/1.0 (+https://www.consens.io)"}


def preview_image_url(client, page: str) -> str:
    response = client.get(page)
    response.raise_for_status()
    match = _META_RE.search(response.text)
    if not match:
        raise SystemExit(f"{page} offers no preview image; pass --image")
    return urljoin(page, (match.group(1) or match.group(2)).replace("&amp;", "&"))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--slug", required=True)
    parser.add_argument("--page", required=True, help="the source page the picture belongs to")
    parser.add_argument("--image", default="", help="picture URL (default: the page's preview image)")
    parser.add_argument("--crop", default="", help="x0,y0,x1,y1 in source pixels")
    parser.add_argument("--out", default="", help="dry run: save the thumbnail here")
    parser.add_argument("--apply", action="store_true", help="store it on the Topic (Prod write)")
    args = parser.parse_args(argv)
    crop = [int(value) for value in args.crop.split(",")] if args.crop else None
    if crop is not None and len(crop) != 4:
        raise SystemExit("--crop needs four numbers: x0,y0,x1,y1")

    with httpx.Client(follow_redirects=True, timeout=30, headers=_HEADERS) as client:
        image_url = args.image or preview_image_url(client, args.page)
        response = client.get(image_url)
        response.raise_for_status()
        content = response.content
    data, size = topic_images.editorial_thumbnail(content, crop)
    print(f"{image_url}\n    thumbnail {size[0]}x{size[1]}, {len(data)} bytes")
    if args.out:
        with open(args.out, "wb") as handle:
            handle.write(data)
        print(f"    saved {args.out}")
    if not args.apply:
        return 0

    from app.core.security import db_firestore as db

    topic = topics.get_topic_by_slug(args.slug, db=db)
    if not topic:
        raise SystemExit(f"no Topic {args.slug}")
    state = topic_images.set_editorial_image(topic["id"], content, source_url=args.page, crop=crop, db=db)
    print(f"    stored on {args.slug}: {state['width']}x{state['height']} from {state['source_host']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

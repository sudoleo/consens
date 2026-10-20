"""Privacy-preserving favicon proxy for public source embeds.

Public Topic pages render self-hosted source cards. To give each card a real
site favicon *without* the visitor's browser ever talking to a third party, we
fetch the icon server-side once and cache it in memory (a daily Render restart
is an acceptable cache lifetime, consistent with the rest of the app). The
browser only ever requests ``/api/topics/favicon`` from consens.io.

We resolve icons through Google's public S2 favicon service. That call happens
server-to-server, so no visitor data is exposed; unknown domains still yield a
neutral globe glyph, which the card layer treats as "no icon" and falls back to
a self-hosted monogram.

An icon smaller than ``MIN_ICON_PX`` counts as no icon: shown at 20 CSS
pixels on a 3x display it would be visibly soft next to sharp ones, and the
crisp globe reads better than a blurred logo (Audit I13).
"""

from __future__ import annotations

import io
import re
import threading
import time
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor

import requests
from PIL import Image

_HOST_RE = re.compile(
    r"^(?=.{1,253}$)([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$"
)
_SERVICE = "https://www.google.com/s2/favicons"
_TIMEOUT = 2
_MAX_BYTES = 100_000
_OK_TTL = 60 * 60 * 24 * 7      # 7 days for a resolved icon
_MISS_TTL = 60 * 60 * 24       # negative cache prevents retry amplification
_MAX_ENTRIES = 2000
# The largest place an icon is drawn is 20 CSS px; DPR 3 needs 60 device px.
MIN_ICON_PX = 64
# Ask for more than needed: Google returns the largest icon it has up to this.
_REQUEST_PX = 128

_CACHE: OrderedDict[str, tuple[float, bytes | None, str]] = OrderedDict()
_INFLIGHT: dict[str, threading.Event] = {}
_LOCK = threading.Lock()
EXECUTOR = ThreadPoolExecutor(max_workers=4, thread_name_prefix="favicon-proxy")


def normalize_host(value) -> str:
    """Reduce arbitrary input to a bare, validated registrable host or ""."""
    host = str(value or "").strip().lower()
    host = re.sub(r"^https?://", "", host).split("/")[0].split("?")[0]
    host = host.split(":")[0].strip(".")
    host = re.sub(r"^www\.", "", host)
    return host if _HOST_RE.match(host) else ""


def _sharp_enough(content: bytes, content_type: str) -> bool:
    """True for a vector icon or a raster at least MIN_ICON_PX wide and high."""
    if content_type == "image/svg+xml":
        return True
    try:
        with Image.open(io.BytesIO(content)) as image:
            width, height = image.size
    except Exception:
        return False
    return min(width, height) >= MIN_ICON_PX


def _fetch(host: str) -> tuple[bytes | None, str]:
    try:
        resp = requests.get(
            _SERVICE,
            params={"domain": host, "sz": str(_REQUEST_PX)},
            timeout=_TIMEOUT,
            headers={"User-Agent": "consens.io-favicon/1.0"},
        )
    except requests.RequestException:
        return None, ""
    if resp.status_code != 200:
        return None, ""
    content_type = resp.headers.get("Content-Type", "").split(";")[0].strip().lower()
    content = resp.content or b""
    if not content_type.startswith("image/") or not content or len(content) > _MAX_BYTES:
        return None, ""
    if not _sharp_enough(content, content_type):
        return None, ""
    return content, content_type


def cached_favicon(value) -> tuple[bytes | None, str] | None:
    """The cached answer for a host without any outbound call, or None when
    only a lookup can tell. An invalid host is answered: it has no icon."""
    host = normalize_host(value)
    if not host:
        return None, ""
    with _LOCK:
        cached = _CACHE.get(host)
        if cached and cached[0] > time.time():
            _CACHE.move_to_end(host)
            return cached[1], cached[2]
    return None


def get_favicon(value) -> tuple[bytes | None, str]:
    """Return (bytes, content_type) for a host, cached; (None, "") if unknown."""
    host = normalize_host(value)
    if not host:
        return None, ""
    now = time.time()
    with _LOCK:
        cached = _CACHE.get(host)
        if cached and cached[0] > now:
            _CACHE.move_to_end(host)
            return cached[1], cached[2]
        if cached:
            _CACHE.pop(host, None)
        pending = _INFLIGHT.get(host)
        if pending is None:
            pending = threading.Event()
            _INFLIGHT[host] = pending
            leader = True
        else:
            leader = False
    if not leader:
        pending.wait(timeout=_TIMEOUT + 0.5)
        with _LOCK:
            cached = _CACHE.get(host)
            if cached and cached[0] > time.time():
                _CACHE.move_to_end(host)
                return cached[1], cached[2]
        return None, ""
    try:
        data, content_type = _fetch(host)
        ttl = _OK_TTL if data else _MISS_TTL
        with _LOCK:
            _CACHE[host] = (now + ttl, data, content_type)
            _CACHE.move_to_end(host)
            while len(_CACHE) > _MAX_ENTRIES:
                _CACHE.popitem(last=False)
        return data, content_type
    finally:
        # An unexpected decoder/client exception must never strand a host in
        # the single-flight map. Followers are released and a later request may
        # retry normally instead of timing out until process restart.
        with _LOCK:
            if _INFLIGHT.get(host) is pending:
                _INFLIGHT.pop(host, None)
            pending.set()

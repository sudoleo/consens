"""Ein echtes Bild pro Watch -- oder keins (Produktentscheidung 2026-10-10).

Nach einer erfolgreichen Prüfung (und beim Anlegen aus einer fertigen Antwort)
sucht dieses Modul unter den Quellen, auf die sich die Modelle gestützt haben,
eine Seite, die sich selbst als konkreten Gegenstand ausweist -- schema.org
Product, Vehicle, Book, Event oder Unterkunft per JSON-LD/Microdata, sonst
``og:type`` product -- und deren Name zur Frage passt. Das Bild dieses
Gegenstands wird einmal serverseitig geholt (SSRF-sicher über
``source_documents.pinned_target``), auf ein kleines WebP verkleinert und unter
``watch_images/{watch_id}`` gespeichert. Der Browser lädt es nur von
consens.io; der Shop sieht keine Besucher-IP.

Bewusst nicht: KI-generierte Bilder, Stockfotos, Artikel-Aufmacher, Logos.
Abstrakte Watches bekommen kein Bild. Das Bild landet nie in der OG-Karte
oder im JSON-LD der Watch-Seite -- es ist eine Vorschau, keine Werbung.
"""

from __future__ import annotations

import asyncio
import hashlib
import io
import json
import logging
import os
import re
import threading
import time
import zlib
from collections import OrderedDict
from datetime import datetime, timezone
from urllib.parse import urljoin, urlsplit

import httpx
from bs4 import BeautifulSoup
from PIL import Image, ImageOps

from app.core.observability import record_metric, safe_exception
from app.services import persistence_guard
from app.services.source_documents import pinned_target


WATCH_IMAGES_COLLECTION = "watch_images"
STATUS_READY = "ready"
STATUS_NONE = "none"
STATUS_DISMISSED = "dismissed"
# Drei Prüfungen ohne passenden Gegenstand: die Watch ist abstrakt, weitere
# Seitenabrufe wären nur Last für fremde Server.
MAX_ATTEMPTS = 3
MAX_PAGES = 5
FETCH_SECONDS = 6.0
ATTEMPT_SECONDS = 25.0
PAGE_MAX_BYTES = 2_000_000
IMAGE_MAX_BYTES = 5_000_000
MIN_SIDE = 160
MAX_PIXELS = 40_000_000
THUMB_SIDE = 320
STORED_MAX_BYTES = 120_000
USER_AGENT = "Mozilla/5.0 (compatible; consens.io-preview/1.0; +https://consens.io)"

TOKEN_RE = re.compile(r"^[0-9a-f]{20}$")
WATCH_ID_RE = re.compile(r"^[A-Za-z0-9]{8,32}$")

_PAGE_KINDS = frozenset({"text/html", "application/xhtml+xml"})
_IMAGE_KINDS = frozenset({"image/jpeg", "image/png", "image/webp", "image/gif"})
_IMAGE_FORMATS = frozenset({"JPEG", "PNG", "WEBP", "GIF"})
_REDIRECTS = frozenset({301, 302, 303, 307, 308})

# schema.org-Typen, deren Bild den Gegenstand selbst zeigt. Artikel, Blogposts,
# Organisationen und Webseiten fehlen absichtlich: deren Bilder sind Aufmacher
# oder Logos. Alle *Event-Untertypen zählen über die Endung.
_ITEM_TYPES = frozenset({
    "product", "productgroup", "productmodel", "individualproduct", "someproducts",
    "vehicle", "car", "motorcycle", "motorizedbicycle", "busorcoach",
    "book", "festival",
    "accommodation", "apartment", "house", "singlefamilyresidence", "room",
    "hotelroom", "suite", "lodgingbusiness", "hotel", "hostel", "motel", "resort",
    "bedandbreakfast", "campground", "vacationrental",
    "touristattraction", "landmarksorhistoricalbuildings",
})
# Seiten, die nie eine Produktseite sind: ihr Abruf wäre verschwendet.
_SKIP_HOSTS = (
    "reddit.com", "youtube.com", "youtu.be", "wikipedia.org", "wikimedia.org",
    "x.com", "twitter.com", "facebook.com", "instagram.com", "tiktok.com",
    "linkedin.com", "google.com", "github.com", "medium.com", "quora.com",
    "stackoverflow.com", "stackexchange.com", "news.ycombinator.com",
)
_LOGO_TOKENS = frozenset({
    "logo", "logos", "favicon", "placeholder", "noimage", "dummy", "sprite",
    "icon", "icons", "avatar", "banner",
})
_STOPWORDS = frozenset("""
in im an am to of on at is it be or by as de en vs
the and for with from that this what when where which will would should into
over under about price prices cost buy cheap best new sale shop online store
size sizes men women mens womens unisex kids pair available
der die das den dem des ein eine einer eines einem und oder mit von vom zum zur
für fur bei auf aus nach unter über uber ist sind wird werden wann wie was wer
ich will möchte moechte kaufen kauf günstig guenstig preis preise euro eur
größe groesse grosse gr neu herren damen kinder erhältlich erhaeltlich verfügbar
verfuegbar paar
shoe shoes sneaker sneakers schuh schuhe laufschuh laufschuhe running
""".split())
_YEAR_RE = re.compile(r"^(19[89]\d|20[0-4]\d)$")

_CACHE: OrderedDict[str, tuple[str, bytes, str]] = OrderedDict()
_MISSES: OrderedDict[tuple[str, str], float] = OrderedDict()
_CACHE_LOCK = threading.Lock()
_CACHE_ENTRIES = 256
_MISS_SECONDS = 300

# Daemon-Threads statt Executor: ein halber Versuch beim Herunterfahren ist
# egal (nichts committet, der nächste Check versucht es erneut), ein Warten auf
# fremde Server im Render-Drain nicht.
_WORKERS = threading.BoundedSemaphore(2)
_PENDING: set[str] = set()
_PENDING_LOCK = threading.Lock()
_PENDING_MAX = 8


# ----------------------------------------------------------------------
# Passt der Gegenstand zur Frage?
# ----------------------------------------------------------------------

def _tokens(text) -> set[str]:
    words = re.findall(r"[^\W_]+", str(text or "").lower())
    return {
        word for word in words
        if word not in _STOPWORDS and (len(word) >= 2 or word.isdigit())
    }


def match_score(name, context: set[str]) -> int:
    """Gemeinsame Wörter zwischen Gegenstand und Frage; 0 heißt: passt nicht.

    Eine Zahl im Namen, die in der Frage fehlt, ist ein anderes Modell
    (Adios Pro 3 statt 4) und schließt aus. Jahreszahlen zählen nur, wenn die
    Frage selbst ein Jahr nennt.
    """
    tokens = _tokens(name)
    if not tokens:
        return 0
    context_has_year = any(_YEAR_RE.match(word) for word in context)
    numbers = {
        word for word in tokens
        if word.isdigit() and (context_has_year or not _YEAR_RE.match(word))
    }
    if numbers - context:
        return 0
    shared = tokens & context
    if not any(len(word) >= 4 and not word.isdigit() for word in shared):
        return 0
    if len(shared) >= 3 or (len(shared) >= 2 and len(shared) * 2 >= len(tokens)):
        return len(shared)
    return 0


# ----------------------------------------------------------------------
# Was zeigt eine Seite? (JSON-LD, Microdata, og:type product)
# ----------------------------------------------------------------------

def _type_names(value) -> list[str]:
    values = value if isinstance(value, list) else [value]
    names = []
    for item in values:
        if isinstance(item, str):
            names.append(item.rsplit("/", 1)[-1].rsplit(":", 1)[-1].strip().lower())
    return names


def _is_item_type(value) -> bool:
    return any(name in _ITEM_TYPES or name.endswith("event") for name in _type_names(value))


def _image_urls(value, base_url: str) -> list[str]:
    queue = value if isinstance(value, list) else [value]
    urls = []
    for item in queue[:6]:
        if isinstance(item, dict):
            item = item.get("contentUrl") or item.get("url") or ""
        if isinstance(item, list):
            item = item[0] if item else ""
        url = str(item or "").strip()
        if not url or url.startswith("data:"):
            continue
        absolute = urljoin(base_url, url)
        if absolute.startswith(("https://", "http://")) and absolute not in urls:
            urls.append(absolute[:2000])
    return urls


def _json_ld_items(soup, base_url: str) -> list[tuple[str, list[str]]]:
    items = []
    for node in soup.find_all("script", type="application/ld+json")[:12]:
        raw = node.string or node.get_text() or ""
        raw = raw.strip().removeprefix("<!--").removesuffix("-->").strip()
        try:
            data = json.loads(raw)
        except (ValueError, RecursionError):
            continue
        queue, seen = [data], 0
        while queue and seen < 400:
            entry = queue.pop(0)
            seen += 1
            if isinstance(entry, list):
                queue.extend(entry[:50])
                continue
            if not isinstance(entry, dict):
                continue
            if _is_item_type(entry.get("@type")):
                name = entry.get("name")
                if isinstance(name, list):
                    name = name[0] if name else ""
                if isinstance(name, str) and name.strip():
                    items.append((name.strip()[:300], _image_urls(entry.get("image"), base_url)))
            queue.extend(value for value in entry.values() if isinstance(value, (dict, list)))
    return items


def _microdata_items(soup, base_url: str) -> list[tuple[str, list[str]]]:
    items = []
    for node in soup.find_all(attrs={"itemtype": True}, limit=40):
        if not _is_item_type(str(node.get("itemtype") or "").split()):
            continue
        name_node = node.find(attrs={"itemprop": "name"})
        if name_node is None:
            continue
        name = name_node.get("content") or name_node.get_text(" ", strip=True)
        images = []
        for image_node in node.find_all(attrs={"itemprop": "image"}, limit=4):
            images.append(
                image_node.get("content") or image_node.get("src")
                or image_node.get("href") or image_node.get("data-src") or ""
            )
        if str(name or "").strip():
            items.append((str(name).strip()[:300], _image_urls(images, base_url)))
        if len(items) >= 10:
            break
    return items


def _meta(soup, *names) -> str:
    for name in names:
        node = soup.find("meta", attrs={"property": name}) or soup.find("meta", attrs={"name": name})
        if node and str(node.get("content") or "").strip():
            return str(node["content"]).strip()
    return ""


def page_items(html: str, base_url: str) -> list[tuple[str, list[str]]]:
    """(Name, Bild-URLs) jedes Gegenstands, den die Seite ausweist.

    Fehlt dem Gegenstand ein eigenes Bild, gilt das Vorschaubild der Seite --
    aber nur, weil die Seite sich als dieser Gegenstand ausweist.
    """
    soup = BeautifulSoup(html, "html.parser")
    items = _json_ld_items(soup, base_url) + _microdata_items(soup, base_url)
    og_type = _meta(soup, "og:type").lower()
    if re.search(r"(^|[:.])(product|item)($|[:.])", og_type):
        title = _meta(soup, "og:title") or (soup.title.get_text(" ", strip=True) if soup.title else "")
        if title:
            items.append((title[:300], []))
    page_image = _image_urls(
        [_meta(soup, "og:image:secure_url", "og:image", "twitter:image")], base_url,
    )
    return [(name, images or page_image) for name, images in items]


def _looks_like_logo(url: str) -> bool:
    path = urlsplit(url).path.lower()
    if any(marker in path for marker in ("no-image", "no_image", "default-image", "default_image")):
        return True
    return bool(set(re.findall(r"[a-z]+", path)) & _LOGO_TOKENS)


# ----------------------------------------------------------------------
# Bild prüfen und verkleinern
# ----------------------------------------------------------------------

def _looks_flat(image) -> bool:
    """Platzhalter und Logos bestehen aus wenigen Flächen, Fotos nicht."""
    rgb = image
    if image.mode == "RGBA":
        rgb = Image.new("RGB", image.size, (255, 255, 255))
        rgb.paste(image, mask=image.getchannel("A"))
    sample = rgb.convert("RGB").resize((32, 32), Image.Resampling.NEAREST)
    colors = sample.getcolors(maxcolors=64)
    return colors is not None and len(colors) <= 8


def make_thumbnail(content: bytes):
    """Kleines WebP (Kante <= THUMB_SIDE) oder None, wenn es kein Foto ist."""
    try:
        with Image.open(io.BytesIO(content)) as source:
            if source.format not in _IMAGE_FORMATS:
                return None
            width, height = source.size
            if min(width, height) < MIN_SIDE or width * height > MAX_PIXELS:
                return None
            if not (1 / 3 <= width / height <= 3):
                return None
            image = ImageOps.exif_transpose(source)
            has_alpha = image.mode in ("RGBA", "LA", "PA") or (
                image.mode == "P" and "transparency" in image.info
            )
            image = image.convert("RGBA" if has_alpha else "RGB")
        if _looks_flat(image):
            return None
        image.thumbnail((THUMB_SIDE, THUMB_SIDE), Image.Resampling.LANCZOS)
        for quality in (82, 70, 55):
            buffer = io.BytesIO()
            image.save(buffer, "WEBP", quality=quality, method=4)
            data = buffer.getvalue()
            if len(data) <= STORED_MAX_BYTES:
                return data, image.size
    except (OSError, ValueError, SyntaxError, Image.DecompressionBombError):
        return None
    return None


# ----------------------------------------------------------------------
# Kandidaten und Abruf
# ----------------------------------------------------------------------

def _skip_host(host: str) -> bool:
    host = host.lower().strip(".")
    return any(host == domain or host.endswith("." + domain) for domain in _SKIP_HOSTS)


def candidate_urls(sources, limit: int = MAX_PAGES) -> list[str]:
    """Quellen-URLs, von mehreren Modellen zitierte zuerst, ein Host pro Runde."""
    order, counts, hosts = [], {}, {}
    for item in sources or []:
        if not isinstance(item, dict):
            continue
        url = str(item.get("url") or "").strip()
        if not url.startswith(("https://", "http://")) or len(url) > 2000:
            continue
        parts = urlsplit(url)
        host = (parts.hostname or "").lower()
        if not host or _skip_host(host) or parts.path.lower().endswith(".pdf"):
            continue
        key = url.split("#", 1)[0]
        if key not in counts:
            order.append(key)
            hosts[key] = host.removeprefix("www.")
        counts[key] = counts.get(key, 0) + 1
    ranked = sorted(order, key=lambda key: (-counts[key], order.index(key)))
    picked, seen_hosts = [], set()
    for key in ranked:
        if hosts[key] not in seen_hosts:
            picked.append(key)
            seen_hosts.add(hosts[key])
    picked += [key for key in ranked if key not in picked]
    return picked[:limit]


async def _fetch(client, url: str, kinds, max_bytes: int, accept: str):
    """(endgültige URL, Bytes, Typ, abgeschnitten) über die gepinnte Adresse."""
    for _ in range(4):
        target, host, hostname = await pinned_target(url)
        async with client.stream(
            "GET", target,
            headers={
                "Host": host, "Accept": accept, "Accept-Encoding": "gzip, deflate",
                "User-Agent": USER_AGENT,
            },
            extensions={"sni_hostname": hostname},
        ) as response:
            if response.status_code in _REDIRECTS:
                location = response.headers.get("location", "")
                if not location:
                    raise ValueError("redirect_without_location")
                url = urljoin(url, location)
                continue
            if response.status_code != 200:
                raise ValueError(f"status_{response.status_code}")
            kind = response.headers.get("content-type", "").split(";")[0].strip().lower()
            if kind not in kinds:
                raise ValueError("unsupported_type")
            encoding = response.headers.get("content-encoding", "identity").strip().lower()
            if encoding not in ("identity", "gzip", "deflate"):
                raise ValueError("unsupported_encoding")
            decoder = (
                zlib.decompressobj(16 + zlib.MAX_WBITS if encoding == "gzip" else zlib.MAX_WBITS)
                if encoding != "identity" else None
            )
            content = bytearray()
            wire_bytes = 0
            truncated = False
            async for chunk in response.aiter_raw(chunk_size=16384):
                wire_bytes += len(chunk)
                remaining = max_bytes - len(content)
                content.extend(decoder.decompress(chunk, remaining) if decoder else chunk[:remaining])
                if wire_bytes >= max_bytes or len(content) >= max_bytes:
                    truncated = True
                    break
            return url, bytes(content), kind, truncated
    raise ValueError("redirect_limit")


async def _http_fetch(url: str, purpose: str):
    async with httpx.AsyncClient(trust_env=False, follow_redirects=False,
                                 timeout=FETCH_SECONDS) as client:
        if purpose == "page":
            return await _fetch(client, url, _PAGE_KINDS, PAGE_MAX_BYTES,
                                "text/html,application/xhtml+xml;q=0.9,*/*;q=0.1")
        return await _fetch(client, url, _IMAGE_KINDS, IMAGE_MAX_BYTES,
                            "image/webp,image/png,image/jpeg,image/gif;q=0.9")


async def _find(urls, context: set[str], fetch):
    tried_images = set()
    for page_url in urls:
        try:
            final_url, content, _kind, _truncated = await asyncio.wait_for(
                fetch(page_url, "page"), FETCH_SECONDS + 1,
            )
            items = page_items(content.decode("utf-8", errors="replace"), final_url)
        except Exception as exc:
            logging.info("Watch image page skipped category=%s", safe_exception(exc))
            continue
        scored = sorted(
            ((match_score(name, context), index, images)
             for index, (name, images) in enumerate(items)),
            key=lambda row: (-row[0], row[1]),
        )
        for score, _index, images in scored[:2]:
            if score <= 0:
                break
            for image_url in images[:2]:
                if image_url in tried_images or _looks_like_logo(image_url):
                    continue
                tried_images.add(image_url)
                try:
                    _url, data, _kind, truncated = await asyncio.wait_for(
                        fetch(image_url, "image"), FETCH_SECONDS + 1,
                    )
                except Exception as exc:
                    logging.info("Watch image fetch skipped category=%s", safe_exception(exc))
                    continue
                if truncated:
                    continue
                thumbnail = await asyncio.to_thread(make_thumbnail, data)
                if thumbnail:
                    stored, (width, height) = thumbnail
                    host = (urlsplit(page_url).hostname or "").lower().removeprefix("www.")
                    return {
                        "content": stored,
                        "content_type": "image/webp",
                        "width": int(width),
                        "height": int(height),
                        "source_url": page_url,
                        "source_host": host,
                    }
    return None


def find_image(sources, question: str, condition: str = "", *, fetch=None) -> dict | None:
    """Bild des Gegenstands, um den es geht, oder None. Blockiert (Thread)."""
    context = _tokens(question) | _tokens(condition)
    urls = candidate_urls(sources)
    if not urls or not context:
        return None

    async def run():
        return await asyncio.wait_for(_find(urls, context, fetch or _http_fetch), ATTEMPT_SECONDS)

    try:
        return asyncio.run(run())
    except (asyncio.TimeoutError, TimeoutError):
        return None


# ----------------------------------------------------------------------
# Speichern, Ausliefern, Entfernen
# ----------------------------------------------------------------------

def needs_image(watch: dict) -> bool:
    image = watch.get("image") if isinstance(watch, dict) else None
    image = image if isinstance(image, dict) else {}
    if image.get("status") in (STATUS_READY, STATUS_DISMISSED):
        return False
    attempts = image.get("attempts")
    return not (isinstance(attempts, int) and attempts >= MAX_ATTEMPTS)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def store_result(watch_id: str, found: dict | None, *, db) -> str:
    """Ergebnis eines Versuchs festhalten, solange die Watch noch eins braucht.

    Bild und Watch-Feld entstehen in einer Transaktion, die die Watch liest:
    eine gelöschte Watch bekommt kein Bild-Dokument mehr, ein inzwischen
    entferntes Bild kommt nicht zurück.
    """
    from app.services import watch_service

    watch_ref = db.collection(watch_service.WATCHES_COLLECTION).document(watch_id)
    image_ref = db.collection(WATCH_IMAGES_COLLECTION).document(watch_id)

    def write(transaction):
        snapshot = watch_ref.get(transaction=transaction)
        current = snapshot.to_dict() if snapshot.exists else None
        if not current or not current.get("owner_uid"):
            return "gone"
        persistence_guard.ensure_account_write_allowed(
            uid=current["owner_uid"], db=db, transaction=transaction,
        )
        if not needs_image(current):
            return "kept"
        previous = current.get("image") if isinstance(current.get("image"), dict) else {}
        attempts = previous.get("attempts") if isinstance(previous.get("attempts"), int) else 0
        now = _now()
        if not found:
            transaction.update(watch_ref, {"image": {
                "status": STATUS_NONE, "attempts": attempts + 1, "last_attempt_at": now,
            }})
            return STATUS_NONE
        token = hashlib.sha256(found["content"]).hexdigest()[:20]
        transaction.set(image_ref, {
            "owner_uid": current["owner_uid"],
            "token": token,
            "content": found["content"],
            "content_type": found["content_type"],
            "width": found["width"],
            "height": found["height"],
            "created_at": now,
        })
        transaction.update(watch_ref, {"image": {
            "status": STATUS_READY,
            "token": token,
            "width": found["width"],
            "height": found["height"],
            "source_url": found["source_url"][:2000],
            "source_host": found["source_host"][:120],
            "attempts": attempts + 1,
            "picked_at": now,
        }})
        return STATUS_READY

    return watch_service._run_transaction(db, write)


def refresh_for_watch(watch_id: str, watch: dict, sources, question: str,
                      condition: str = "", *, db=None, fetch=None) -> str:
    """Ein Versuch für eine Watch; Quellen ohne Kandidaten zählen nicht."""
    if not needs_image(watch) or not candidate_urls(sources):
        return "skipped"
    if db is None:
        from app.core.security import db_firestore as db
    started = time.monotonic()
    found = find_image(sources, question, condition, fetch=fetch)
    outcome = store_result(watch_id, found, db=db)
    record_metric(
        "watch_images", "pick",
        duration_ms=(time.monotonic() - started) * 1000,
        outcome="success" if outcome == STATUS_READY else "skipped",
        processed=int(outcome == STATUS_READY),
    )
    return outcome


def background_enabled() -> bool:
    from app.services.llm.mock_llm import mock_llm_enabled

    if mock_llm_enabled():
        return False
    return not any(os.getenv(key) == "1" for key in ("UNIT_TEST_MODE", "E2E_TEST_MODE"))


def _submit(watch_id: str, job) -> bool:
    with _PENDING_LOCK:
        if watch_id in _PENDING or len(_PENDING) >= _PENDING_MAX:
            return False
        _PENDING.add(watch_id)

    def run():
        try:
            with _WORKERS:
                job()
        except Exception as exc:
            logging.warning("Watch image pick failed category=%s", safe_exception(exc))
        finally:
            with _PENDING_LOCK:
                _PENDING.discard(watch_id)

    threading.Thread(target=run, name="watch-image", daemon=True).start()
    return True


def schedule_after_run(watch_id: str, watch: dict, sources, question: str,
                       condition: str = "") -> bool:
    """Nach einer Prüfung im Hintergrund versuchen; hält den Tick nie auf."""
    if not background_enabled() or not needs_image(watch) or not candidate_urls(sources):
        return False
    sources = list(sources or [])
    return _submit(watch_id, lambda: refresh_for_watch(
        watch_id, watch, sources, question, condition,
    ))


def schedule_for_new_watch(watch_id: str) -> bool:
    """Watch aus einer fertigen Antwort: deren Quellen tragen schon ein Bild."""
    if not background_enabled() or not WATCH_ID_RE.match(str(watch_id or "")):
        return False

    def job():
        from app.core.security import db_firestore
        from app.services import share_snapshots, watch_service

        snapshot = db_firestore.collection(watch_service.WATCHES_COLLECTION).document(watch_id).get()
        watch = snapshot.to_dict() if snapshot.exists else None
        if not watch or watch.get("query_first") is True:
            return
        share = share_snapshots.get_share(str(watch.get("share_id") or "")) or {}
        refresh_for_watch(
            watch_id, watch, share.get("sources") or [], str(share.get("question") or ""),
            str(watch.get("condition") or ""), db=db_firestore,
        )

    return _submit(watch_id, job)


def image_view(watch_id: str, watch: dict) -> dict | None:
    """Was Dashboard und Watch-Seite vom Bild wissen dürfen (ohne Bytes)."""
    image = watch.get("image") if isinstance(watch, dict) else None
    if not isinstance(image, dict) or image.get("status") != STATUS_READY:
        return None
    token = str(image.get("token") or "")
    if not TOKEN_RE.match(token) or not WATCH_ID_RE.match(str(watch_id or "")):
        return None
    source_url = str(image.get("source_url") or "")[:2000]
    if not source_url.startswith(("https://", "http://")):
        source_url = ""

    def side(value):
        return value if isinstance(value, int) and 0 < value <= THUMB_SIDE else THUMB_SIDE

    return {
        "url": f"/api/watch/{watch_id}/image/{token}",
        "width": side(image.get("width")),
        "height": side(image.get("height")),
        "source_url": source_url,
        "source_host": str(image.get("source_host") or "")[:120],
    }


def load_image(watch_id: str, token: str, *, db=None) -> tuple[bytes, str] | None:
    """Bytes zum Token; ein Prozess-Cache spart Firestore-Reads."""
    if not WATCH_ID_RE.match(str(watch_id or "")) or not TOKEN_RE.match(str(token or "")):
        return None
    now = time.monotonic()
    with _CACHE_LOCK:
        cached = _CACHE.get(watch_id)
        if cached and cached[0] == token:
            _CACHE.move_to_end(watch_id)
            return cached[1], cached[2]
        missed = _MISSES.get((watch_id, token))
        if missed and now - missed < _MISS_SECONDS:
            return None
    if db is None:
        from app.core.security import db_firestore as db
    snapshot = db.collection(WATCH_IMAGES_COLLECTION).document(watch_id).get()
    data = snapshot.to_dict() if snapshot.exists else None
    content = (data or {}).get("content")
    content_type = str((data or {}).get("content_type") or "")
    if (not data or data.get("token") != token or not isinstance(content, (bytes, bytearray))
            or content_type not in _IMAGE_KINDS):
        with _CACHE_LOCK:
            _MISSES[(watch_id, token)] = now
            while len(_MISSES) > _CACHE_ENTRIES * 4:
                _MISSES.popitem(last=False)
        return None
    with _CACHE_LOCK:
        _CACHE[watch_id] = (token, bytes(content), content_type)
        _CACHE.move_to_end(watch_id)
        while len(_CACHE) > _CACHE_ENTRIES:
            _CACHE.popitem(last=False)
    return bytes(content), content_type


def forget(watch_id: str) -> None:
    with _CACHE_LOCK:
        _CACHE.pop(str(watch_id or ""), None)

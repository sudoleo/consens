"""Ein echtes Bild pro Watch -- oder keins (Produktentscheidung 2026-10-10/11).

Nach einer erfolgreichen Prüfung (und beim Anlegen aus einer fertigen Antwort)
sucht dieses Modul unter den Quellen, auf die sich die Modelle gestützt haben:

1. den Gegenstand selbst: eine Seite, die sich als schema.org Product,
   Vehicle, Book, Event oder Unterkunft ausweist (JSON-LD/Microdata, sonst
   ``og:type`` product) und deren Name zur Frage passt (``kind="item"``);
2. sonst das Thema: einen Artikel (schema.org Article/NewsArticle/BlogPosting,
   sonst ``og:type`` article), dessen Überschrift zur Frage passt, mit dem
   Vorschaubild, das der Verlag selbst fürs Teilen festlegt (``og:image``,
   ``kind="article"``).

Das Bild wird einmal serverseitig geholt (SSRF-sicher über
``source_documents.pinned_target``), als kleines WebP neu kodiert und unter
``watch_images/{watch_id}`` gespeichert. Der Browser lädt es nur von
consens.io; die Quelle sieht keine Besucher-IP.

Bewusst nicht: KI-generierte Bilder, Stockfotos, Logos, Platzhalter,
Seiten-Standardbilder. Passt nichts, gibt es kein Bild. Das Bild landet nie in
der OG-Karte oder im JSON-LD der Watch-Seite -- es ist eine Vorschau, keine
Werbung.
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
from PIL import Image

from app.core.observability import record_metric, safe_exception
from app.services import persistence_guard
from app.services.source_documents import pinned_target


WATCH_IMAGES_COLLECTION = "watch_images"
STATUS_READY = "ready"
STATUS_NONE = "none"
STATUS_DISMISSED = "dismissed"
# Drei Prüfungen, in denen Seiten gelesen, aber kein passender Gegenstand
# gefunden wurde: die Watch ist abstrakt. Versuche, in denen keine einzige
# Seite lesbar war (Bot-Sperre, Zeitüberschreitung), zählen dort nicht, sind
# aber auf MAX_TRIES begrenzt -- sonst klopfen wir ewig bei gesperrten Shops.
MAX_ATTEMPTS = 3
MAX_TRIES = 8
MAX_PAGES = 5
FETCH_SECONDS = 6.0
ATTEMPT_SECONDS = 25.0
PAGE_MAX_BYTES = 2_000_000
IMAGE_MAX_BYTES = 5_000_000
MIN_SIDE = 160
# JPEG wird verkleinert dekodiert (draft), alles andere in voller Größe:
# 8 MP sind ~32 MB je Puffer, genug für jedes Produktfoto.
MAX_PIXELS = 40_000_000
MAX_PIXELS_DECODED = 8_000_000
THUMB_SIDE = 320
STORED_MAX_BYTES = 120_000
USER_AGENT = "Mozilla/5.0 (compatible; consens.io-preview/1.0; +https://consens.io)"

TOKEN_RE = re.compile(r"^[0-9a-f]{20}$")
WATCH_ID_RE = re.compile(r"^[A-Za-z0-9]{8,32}$")

_PAGE_KINDS = frozenset({"text/html", "application/xhtml+xml"})
_IMAGE_KINDS = frozenset({"image/jpeg", "image/png", "image/webp", "image/gif"})
_IMAGE_FORMATS = ("JPEG", "PNG", "WEBP", "GIF")
_REDIRECTS = frozenset({301, 302, 303, 307, 308})

# schema.org-Typen, deren Bild den Gegenstand selbst zeigt. Organisationen und
# Webseiten fehlen absichtlich (Logos); Artikel sind die zweite Stufe
# (_ARTICLE_TYPES). Events nur als echte Veranstaltungen -- BroadcastEvent &
# Co. hängen an Videos und tragen deren Thumbnail.
_ITEM_TYPES = frozenset({
    "product", "productgroup", "productmodel", "individualproduct", "someproducts",
    "vehicle", "car", "motorcycle", "motorizedbicycle", "busorcoach",
    "book", "festival", "event", "musicevent", "sportsevent", "theaterevent",
    "comedyevent", "danceevent", "exhibitionevent", "screeningevent", "foodevent",
    "literaryevent", "visualartsevent", "childrensevent", "educationevent",
    "accommodation", "apartment", "house", "singlefamilyresidence", "room",
    "hotelroom", "suite", "lodgingbusiness", "hotel", "hostel", "motel", "resort",
    "bedandbreakfast", "campground", "vacationrental",
    "touristattraction", "landmarksorhistoricalbuildings",
})
_ARTICLE_TYPES = frozenset({
    "article", "newsarticle", "blogposting", "liveblogposting", "techarticle",
    "report", "scholarlyarticle", "reportagenewsarticle", "analysisnewsarticle",
    "opinionnewsarticle", "backgroundnewsarticle", "reviewnewsarticle", "review",
})
# Seiten, deren Vorschaubild nie das Thema zeigt (Plattform-Logos, Login-Wände,
# Video-Thumbnails mit Gesichtern): ihr Abruf wäre verschwendet.
_SKIP_HOSTS = (
    "reddit.com", "youtube.com", "youtu.be",
    "x.com", "twitter.com", "facebook.com", "instagram.com", "tiktok.com",
    "linkedin.com", "github.com", "medium.com", "quora.com",
    "stackoverflow.com", "stackexchange.com", "news.ycombinator.com",
)
# Google nur Suche/News, nicht etwa store.google.com.
_SKIP_EXACT_HOSTS = frozenset({"google.com", "www.google.com", "news.google.com"})
_LOGO_TOKENS = frozenset({
    "logo", "logos", "favicon", "placeholder", "noimage", "dummy", "sprite",
    "icon", "icons", "avatar", "banner",
})
# Zusätzlich für Artikel: das Standardbild, das eine Seite jedem Artikel gibt.
_DEFAULT_TOKENS = frozenset({"default", "fallback", "generic"})
_STOPWORDS = frozenset("""
in im an am to of on at is it be or by as de en vs
the and for with from that this what when where which will would should into
has have had does did can could than there their how why who whether still yet
now today really actually more most much many any some get got
over under about price prices cost buy cheap best new sale shop online store
size sizes men women mens womens unisex kids pair available
der die das den dem des ein eine einer eines einem und oder mit von vom zum zur
für fur bei auf aus nach unter über uber ist sind wird werden wann wie was wer
ich will möchte moechte kaufen kauf günstig guenstig preis preise euro eur
es gibt hat haben kann können koennen noch schon jetzt heute bis wurde sein
ob welche welcher welches wieder mehr
größe groesse grosse gr neu herren damen kinder erhältlich erhaeltlich verfügbar
verfuegbar paar
shoe shoes sneaker sneakers schuh schuhe laufschuh laufschuhe running
""".split())
# Zubehör und Merch: steht so ein Wort im Namen, aber nicht in der Frage, ist
# es nicht der Gegenstand (Socken zum Laufschuh, Hülle zum iPhone).
_ACCESSORY_TOKENS = frozenset("""
hülle huelle schutzhülle case etui tasche cover sleeve schutzfolie folie panzerglas
displayschutz protector ladegerät ladegeraet charger ladekabel netzteil kabel cable
adapter halterung mount holder ständer staender stand armband strap band ersatz
ersatzteil ersatzteile replacement ohrpolster earpads socken socks schnürsenkel
schnuersenkel laces einlegesohlen einlegesohle insoles fußmatten fussmatten matten
mats aufkleber sticker decal skin poster zubehör zubehoer accessory accessories
kompatibel compatible passend refill kartusche cartridge toner shirt tshirt hoodie
shorts cap mütze muetze kappe tasse mug keychain schlüsselanhänger lanyard
""".split())

_CACHE: OrderedDict[str, tuple[str, bytes, str]] = OrderedDict()
_MISSES: OrderedDict[tuple[str, str], float] = OrderedDict()
_CACHE_LOCK = threading.Lock()
_CACHE_ENTRIES = 256
_MISS_SECONDS = 300

_GENERATIONS: dict[str, int] = {}

# Daemon-Threads statt Executor: ein halber Versuch beim Herunterfahren ist
# egal (nichts committet, der nächste Check versucht es erneut), ein Warten auf
# fremde Server im Render-Drain nicht. Ein Versuch zur Zeit hält den Speicher
# im einen Prod-Prozess klein.
_WORKERS = threading.BoundedSemaphore(1)
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


def _sequence(text) -> list[str]:
    words = re.findall(r"[^\W_]+", str(text or "").lower())
    return [word for word in words if word not in _STOPWORDS and (len(word) >= 2 or word.isdigit())]


def _number_slots(text) -> dict[str, set[str]]:
    """Welche Zahl hinter welchem Wort steht: "pro 4", "iphone 17", "air 13"."""
    words = re.findall(r"[^\W_]+", str(text or "").lower())
    slots: dict[str, set[str]] = {}
    for previous, word in zip(words, words[1:]):
        if word.isdigit() and not previous.isdigit():
            slots.setdefault(previous, set()).add(word)
    return slots


def _longest_run(left: list[str], right: list[str]) -> int:
    best = 0
    lengths = [0] * (len(right) + 1)
    for word in left[:60]:
        previous = 0
        for index, other in enumerate(right[:60], start=1):
            current = lengths[index]
            lengths[index] = previous + 1 if word == other else 0
            best = max(best, lengths[index])
            previous = current
    return best


class Question:
    """Was die Frage (plus Ziel) über den gesuchten Gegenstand verrät."""

    def __init__(self, question: str, condition: str = ""):
        self.tokens = _tokens(question) | _tokens(condition)
        self.entities = entity_tokens(question) | entity_tokens(condition)
        self.named = {word for word in self.entities if not word.isdigit()}
        self.slots: dict[str, set[str]] = {}
        for text in (question, condition):
            for word, numbers in _number_slots(text).items():
                self.slots.setdefault(word, set()).update(numbers)
        self.sequences = [_sequence(question), _sequence(condition)]


def match_score(name, question: Question) -> int:
    """Gemeinsame Wörter zwischen Gegenstand und Frage; 0 heißt: passt nicht.

    Ausgeschlossen: Zubehör/Merch, das die Frage nicht nennt, und eine andere
    Zahl am selben Platz ("Pro 3" statt "Pro 4"; Größen und Speicher an
    anderer Stelle stören nicht). Sonst muss der Name die Namen der Frage
    weitgehend abdecken oder drei Wörter der Frage am Stück enthalten -- das
    trennt "Adizero Adios Pro 4" vom Schwestermodell "Adizero Evo SL".
    """
    tokens = _tokens(name)
    if not tokens or (tokens & _ACCESSORY_TOKENS) - question.tokens:
        return 0
    for word, numbers in _number_slots(name).items():
        expected = question.slots.get(word)
        if expected and not numbers & expected:
            return 0
    shared = tokens & question.tokens
    if len(shared) < 2 or not any(len(word) >= 4 and not word.isdigit() for word in shared):
        return 0
    covered = len(shared & question.named) / len(question.named) if question.named else 0.0
    run = max((_longest_run(_sequence(name), sequence) for sequence in question.sequences), default=0)
    return len(shared) if covered >= 0.75 or run >= 3 else 0


def entity_tokens(text) -> set[str]:
    """Wörter, die in der Frage wie Namen aussehen: mit Großbuchstabe (außer
    am Satzanfang) oder Ziffer -- "GPT-6", "Opus", "EU", "iPhone", "17"."""
    entities = set()
    for sentence in re.split(r"(?<=[.!?:])\s+", str(text or "")):
        for index, match in enumerate(re.finditer(r"[^\W_]+", sentence)):
            word = match.group(0)
            lowered = word.lower()
            if lowered in _STOPWORDS:
                continue
            if any(ch.isdigit() for ch in word) or (index > 0 and any(ch.isupper() for ch in word)):
                entities.add(lowered)
    return entities


def article_score(headline, context: set[str], entities: set[str]) -> int:
    """Wie match_score, aber für Überschriften: Zahlen schließen nicht aus
    (Artikel nennen Ergebnisse). Dafür muss ein gemeinsames Wort ein Name aus
    der Frage sein -- allgemeine Wörter wie "better" oder "coding" passen zu
    jeder zweiten Überschrift."""
    tokens = _tokens(headline)
    shared = tokens & context
    named = shared & entities
    if not named or not any(len(word) >= 3 and not word.isdigit() for word in shared):
        return 0
    if len(shared) >= 3 or (len(shared) == 2 and len(named) == 2 and len(tokens) <= 6):
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
    return any(name in _ITEM_TYPES for name in _type_names(value))


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


def _json_ld_items(soup, base_url: str) -> list[tuple[str, list[str], bool]]:
    """(Name, eigene Bilder, eigenständig) je Gegenstand im JSON-LD.

    Eigenständig ist ein Gegenstand auf oberster Ebene, im @graph oder als
    mainEntity -- nicht einer, der in einer Rezension, Liste, einem Artikel
    oder Video steckt. Nur eigenständige dürfen das Seitenbild erben.
    """
    items = []
    for node in soup.find_all("script", type="application/ld+json")[:12]:
        raw = node.string or node.get_text() or ""
        raw = raw.strip().removeprefix("<!--").removesuffix("-->").strip()
        try:
            data = json.loads(raw)
        except (ValueError, RecursionError):
            continue
        queue, seen = [(data, True)], 0
        while queue and seen < 400:
            entry, top = queue.pop(0)
            seen += 1
            if isinstance(entry, list):
                queue.extend((value, top) for value in entry[:50])
                continue
            if not isinstance(entry, dict):
                continue
            if _is_item_type(entry.get("@type")):
                name = entry.get("name")
                if isinstance(name, list):
                    name = name[0] if name else ""
                if isinstance(name, str) and name.strip():
                    items.append((name.strip()[:300], _image_urls(entry.get("image"), base_url), top))
            for key, value in entry.items():
                if isinstance(value, (dict, list)):
                    queue.append((value, top and key in ("@graph", "mainEntity")))
    return items


def _own(node, prop: str, limit: int):
    """Eigenschaften dieses Microdata-Gegenstands, nicht eines verschachtelten
    (der Name der Marke oder eines Angebots darunter)."""
    found = []
    for child in node.find_all(attrs={"itemprop": prop}):
        owner = child.find_parent(attrs={"itemscope": True})
        if owner is node or (owner is None and child is not node):
            found.append(child)
            if len(found) >= limit:
                break
    return found


def _microdata_items(soup, base_url: str) -> list[tuple[str, list[str], bool]]:
    items = []
    for node in soup.find_all(attrs={"itemtype": True}, limit=40):
        if not _is_item_type(str(node.get("itemtype") or "").split()):
            continue
        names = _own(node, "name", 1)
        if not names:
            continue
        name = names[0].get("content") or names[0].get_text(" ", strip=True)
        images = [
            image_node.get("content") or image_node.get("src")
            or image_node.get("href") or image_node.get("data-src") or ""
            for image_node in _own(node, "image", 4)
        ]
        top = node.find_parent(attrs={"itemscope": True}) is None
        if str(name or "").strip():
            items.append((str(name).strip()[:300], _image_urls(images, base_url), top))
        if len(items) >= 10:
            break
    return items


def _meta(soup, *names) -> str:
    for name in names:
        node = soup.find("meta", attrs={"property": name}) or soup.find("meta", attrs={"name": name})
        if node and str(node.get("content") or "").strip():
            return str(node["content"]).strip()
    return ""


def _json_ld_article(soup, base_url: str):
    """(Überschrift, Bild-URLs) des ersten Artikels im JSON-LD, sonst None."""
    for node in soup.find_all("script", type="application/ld+json")[:12]:
        raw = (node.string or node.get_text() or "").strip()
        raw = raw.removeprefix("<!--").removesuffix("-->").strip()
        try:
            data = json.loads(raw)
        except (ValueError, RecursionError):
            continue
        queue, seen = [data], 0
        while queue and seen < 200:
            entry = queue.pop(0)
            seen += 1
            if isinstance(entry, list):
                queue.extend(entry[:50])
                continue
            if not isinstance(entry, dict):
                continue
            if any(name in _ARTICLE_TYPES for name in _type_names(entry.get("@type"))):
                headline = entry.get("headline") or entry.get("name") or ""
                if isinstance(headline, list):
                    headline = headline[0] if headline else ""
                if isinstance(headline, str) and headline.strip():
                    return headline.strip()[:300], _image_urls(entry.get("image"), base_url)
            graph = entry.get("@graph")
            if isinstance(graph, list):
                queue.extend(graph[:50])
    return None


def _parse(html: str, base_url: str):
    """Gegenstände der Seite und -- falls sie ein Artikel ist -- der Artikel."""
    soup = BeautifulSoup(html, "html.parser")
    items = _json_ld_items(soup, base_url) + _microdata_items(soup, base_url)
    og_type = _meta(soup, "og:type").lower()
    title = _meta(soup, "og:title") or (soup.title.get_text(" ", strip=True) if soup.title else "")
    if re.search(r"(^|[:.])(product|item)($|[:.])", og_type) and title:
        items.append((title[:300], [], True))
    page_image = _image_urls(
        [_meta(soup, "og:image:secure_url", "og:image", "twitter:image")], base_url,
    )
    # Das Seitenbild gehört nur einem eigenständigen Gegenstand einer Seite, die
    # kein Artikel ist -- sonst wäre es der Aufmacher einer Rezension.
    inherit = og_type != "article"
    items = [
        (name, images or (page_image if top and inherit else []))
        for name, images, top in items
    ]
    article = _json_ld_article(soup, base_url)
    if article is None and og_type == "article" and title:
        article = (title[:300], [])
    if article is not None:
        # Das Vorschaubild, das der Verlag fürs Teilen festlegt, zuerst.
        headline, images = article
        article = (headline, list(dict.fromkeys(page_image + images)))
    return items, article


def page_items(html: str, base_url: str) -> list[tuple[str, list[str]]]:
    """(Name, Bild-URLs) jedes Gegenstands, den die Seite ausweist.

    Fehlt dem Gegenstand ein eigenes Bild, gilt das Vorschaubild der Seite --
    aber nur, weil die Seite sich als dieser Gegenstand ausweist.
    """
    return _parse(html, base_url)[0]


def page_article(html: str, base_url: str):
    """(Überschrift, Bild-URLs) wenn die Seite ein Artikel ist, sonst None."""
    return _parse(html, base_url)[1]


def _looks_like_logo(url: str, *, article: bool = False) -> bool:
    path = urlsplit(url).path.lower()
    if any(marker in path for marker in ("no-image", "no_image", "default-image", "default_image")):
        return True
    words = set(re.findall(r"[a-z]+", path))
    return bool(words & _LOGO_TOKENS or (article and words & _DEFAULT_TOKENS))


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


_ORIENTATION = {
    2: Image.Transpose.FLIP_LEFT_RIGHT, 3: Image.Transpose.ROTATE_180,
    4: Image.Transpose.FLIP_TOP_BOTTOM, 5: Image.Transpose.TRANSPOSE,
    6: Image.Transpose.ROTATE_270, 7: Image.Transpose.TRANSVERSE,
    8: Image.Transpose.ROTATE_90,
}


def make_thumbnail(content: bytes):
    """Kleines WebP (Kante <= THUMB_SIDE) oder None, wenn es kein Foto ist.

    Nur vier Decoder; JPEG wird per draft() gleich verkleinert dekodiert,
    andere Formate nur bis MAX_PIXELS_DECODED -- ein 6000er-Original darf den
    einen Prod-Prozess nicht um Hunderte MB aufblähen.
    """
    try:
        with Image.open(io.BytesIO(content), formats=_IMAGE_FORMATS) as source:
            width, height = source.size
            limit = MAX_PIXELS if source.format == "JPEG" else MAX_PIXELS_DECODED
            if min(width, height) < MIN_SIDE or width * height > limit:
                return None
            if not (1 / 3 <= width / height <= 3):
                return None
            orientation = None
            if source.format == "JPEG":
                # Nur JPEG-Fotos tragen eine Kamera-Ausrichtung; PNG würde für
                # getexif() schon voll dekodiert.
                try:
                    orientation = source.getexif().get(0x0112)
                except Exception:
                    orientation = None
                source.draft("RGB", (THUMB_SIDE * 2, THUMB_SIDE * 2))
            box = (THUMB_SIDE, THUMB_SIDE)
            if source.mode in ("RGB", "RGBA"):
                # Erst verkleinern, dann kopieren: nur ein großer Puffer lebt.
                source.thumbnail(box, Image.Resampling.LANCZOS)
                image = source.convert(source.mode)
            else:
                has_alpha = source.mode in ("LA", "PA") or (
                    source.mode == "P" and "transparency" in source.info
                )
                image = source.convert("RGBA" if has_alpha else "RGB")
                image.thumbnail(box, Image.Resampling.LANCZOS)
        if orientation in _ORIENTATION:
            image = image.transpose(_ORIENTATION[orientation])
        if _looks_flat(image):
            return None
        for quality in (82, 70, 55):
            buffer = io.BytesIO()
            image.save(buffer, "WEBP", quality=quality, method=4)
            data = buffer.getvalue()
            if len(data) <= STORED_MAX_BYTES:
                return data, image.size
    except Exception:
        # Beliebig kaputte Dateien (EXIF, Modi, Header) sind schlicht kein Bild;
        # sie dürfen nie den ganzen Versuch abbrechen.
        return None
    return None


# ----------------------------------------------------------------------
# Kandidaten und Abruf
# ----------------------------------------------------------------------

def _skip_host(host: str) -> bool:
    host = host.lower().strip(".")
    if host in _SKIP_EXACT_HOSTS:
        return True
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


async def _find(urls, question: Question, fetch, progress: dict):
    """Erst der Gegenstand auf irgendeiner Quelle, dann der beste Artikel."""
    tried_images = set()

    async def first_photo(page_url, images, kind):
        for image_url in images[:2]:
            if image_url in tried_images or _looks_like_logo(image_url, article=kind == "article"):
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
                    "kind": kind,
                    "width": int(width),
                    "height": int(height),
                    "source_url": page_url,
                    "source_host": host,
                }
        return None

    articles = []
    for rank, page_url in enumerate(urls):
        try:
            final_url, content, _kind, _truncated = await asyncio.wait_for(
                fetch(page_url, "page"), FETCH_SECONDS + 1,
            )
            items, article = _parse(content.decode("utf-8", errors="replace"), final_url)
        except Exception as exc:
            logging.info("Watch image page skipped category=%s", safe_exception(exc))
            continue
        progress["looked"] = True
        scored = sorted(
            ((match_score(name, question), index, images)
             for index, (name, images) in enumerate(items)),
            key=lambda row: (-row[0], row[1]),
        )
        for score, _index, images in scored[:2]:
            if score <= 0:
                break
            found = await first_photo(page_url, images, "item")
            if found:
                return found
        if article is not None:
            score = article_score(article[0], question.tokens, question.entities)
            if score:
                articles.append((score, rank, page_url, article[1]))
    for _score, _rank, page_url, images in sorted(articles, key=lambda row: (-row[0], row[1]))[:3]:
        found = await first_photo(page_url, images, "article")
        if found:
            return found
    return None


def search(sources, question: str, condition: str = "", *, fetch=None) -> tuple[dict | None, bool]:
    """(Bild oder None, ob mindestens eine Seite gelesen wurde). Blockiert (Thread)."""
    asked = Question(question, condition)
    urls = candidate_urls(sources)
    if not urls or not asked.tokens:
        return None, False
    progress = {"looked": False}

    async def run():
        return await asyncio.wait_for(
            _find(urls, asked, fetch or _http_fetch, progress), ATTEMPT_SECONDS,
        )

    try:
        return asyncio.run(run()), progress["looked"]
    except (asyncio.TimeoutError, TimeoutError):
        return None, progress["looked"]


def find_image(sources, question: str, condition: str = "", *, fetch=None) -> dict | None:
    """Bild des Gegenstands, um den es geht, oder None. Blockiert (Thread)."""
    return search(sources, question, condition, fetch=fetch)[0]


# ----------------------------------------------------------------------
# Speichern, Ausliefern, Entfernen
# ----------------------------------------------------------------------

def needs_image(watch: dict) -> bool:
    image = watch.get("image") if isinstance(watch, dict) else None
    image = image if isinstance(image, dict) else {}
    if image.get("status") in (STATUS_READY, STATUS_DISMISSED):
        return False
    attempts, tries = image.get("attempts"), image.get("tries")
    return not (
        (isinstance(attempts, int) and attempts >= MAX_ATTEMPTS)
        or (isinstance(tries, int) and tries >= MAX_TRIES)
    )


def _now() -> datetime:
    return datetime.now(timezone.utc)


def store_result(watch_id: str, found: dict | None, *, db, looked: bool = True) -> str:
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
        tries = previous.get("tries") if isinstance(previous.get("tries"), int) else 0
        now = _now()
        if not found:
            transaction.update(watch_ref, {"image": {
                "status": STATUS_NONE, "attempts": attempts + int(bool(looked)),
                "tries": tries + 1, "last_attempt_at": now,
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
            "kind": "article" if found.get("kind") == "article" else "item",
            "token": token,
            "width": found["width"],
            "height": found["height"],
            "source_url": found["source_url"][:2000],
            "source_host": found["source_host"][:120],
            "attempts": attempts + 1,
            "tries": tries + 1,
            "picked_at": now,
        }})
        return STATUS_READY

    outcome = watch_service._run_transaction(db, write)
    if outcome == STATUS_READY:
        forget(watch_id)
    return outcome


def refresh_for_watch(watch_id: str, watch: dict, sources, question: str,
                      condition: str = "", *, db=None, fetch=None) -> str:
    """Ein Versuch für eine Watch; Quellen ohne Kandidaten zählen nicht."""
    if not needs_image(watch) or not candidate_urls(sources):
        return "skipped"
    if db is None:
        from app.core.security import db_firestore as db
    started = time.monotonic()
    try:
        found, looked = search(sources, question, condition, fetch=fetch)
    except Exception as exc:
        # Ein unerwarteter Fehler soll nicht jede Prüfung wiederholen: er zählt
        # als Versuch ohne gelesene Seite (MAX_TRIES deckelt das).
        logging.warning("Watch image search failed category=%s", safe_exception(exc))
        found, looked = None, False
    outcome = store_result(watch_id, found, db=db, looked=looked)
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

    try:
        threading.Thread(target=run, name="watch-image", daemon=True).start()
    except Exception as exc:
        logging.warning("Watch image thread start failed category=%s", safe_exception(exc))
        with _PENDING_LOCK:
            _PENDING.discard(watch_id)
        return False
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
        # item: Produktfoto (meist weißer Grund, ganz zeigen); article: Foto
        # eines Artikels (darf die Kachel füllen).
        "kind": "article" if image.get("kind") == "article" else "item",
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
        generation = _GENERATIONS.get(watch_id, 0)
        cached = _CACHE.get(watch_id)
        if cached:
            # Ein fertiges Bild wird nie ersetzt, nur entfernt (dann forget());
            # ein anderes Token ist also falsch und kostet keinen Read.
            if cached[0] != token:
                return None
            _CACHE.move_to_end(watch_id)
            return cached[1], cached[2]
        missed = _MISSES.get((watch_id, token)) or _MISSES.get((watch_id, ""))
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
            # Ohne Dokument ist jedes Token falsch: eine Watch-ID kostet dann
            # nur einen Read, egal wie viele Tokens jemand probiert.
            _MISSES[(watch_id, token if data else "")] = now
            while len(_MISSES) > _CACHE_ENTRIES * 4:
                _MISSES.popitem(last=False)
        return None
    with _CACHE_LOCK:
        if _GENERATIONS.get(watch_id, 0) != generation:
            # Inzwischen entfernt oder gelöscht: ausliefern ja, merken nein.
            return bytes(content), content_type
        _CACHE[watch_id] = (token, bytes(content), content_type)
        _CACHE.move_to_end(watch_id)
        while len(_CACHE) > _CACHE_ENTRIES:
            _CACHE.popitem(last=False)
    return bytes(content), content_type


def forget(watch_id: str) -> None:
    watch_id = str(watch_id or "")
    with _CACHE_LOCK:
        _CACHE.pop(watch_id, None)
        _MISSES.pop((watch_id, ""), None)
        _GENERATIONS[watch_id] = _GENERATIONS.get(watch_id, 0) + 1
        if len(_GENERATIONS) > _CACHE_ENTRIES * 8:
            _GENERATIONS.clear()

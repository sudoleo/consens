"""Ein echtes Bild pro Watch -- oder keins (Produktentscheidung 2026-10-10/11).

Nach einer erfolgreichen Prüfung (und beim Anlegen aus einer fertigen Antwort)
sucht dieses Modul unter den Quellen, auf die sich die Modelle gestützt haben:

1. den Gegenstand selbst: eine Seite, die sich als schema.org Product,
   Vehicle, Book, Event oder Unterkunft ausweist (JSON-LD/Microdata, sonst
   ``og:type`` product) und deren Name zur Frage passt (``kind="item"``);
2. sonst das Thema: einen Artikel (schema.org Article/NewsArticle/BlogPosting,
   sonst ``og:type`` article), dessen Überschrift zur Frage passt, mit dem
   Vorschaubild, das der Verlag selbst fürs Teilen festlegt (``og:image``,
   ``kind="article"``);
3. sonst das Logo derer, um die es geht (seit 2026-10-12, damit man eine Watch
   auf einen Blick wiedererkennt): eine Quelle, deren Domainname ein Name aus
   der Frage ist ("Cursor oder Claude Code?" -> cursor.com, claude.com), mit
   dem App-Icon, das die Seite selbst festlegt -- höchstens zwei nebeneinander
   (``kind="logo"``).

Das Bild wird einmal serverseitig geholt (SSRF-sicher über
``source_documents.pinned_target``), als kleines WebP neu kodiert und unter
``watch_images/{watch_id}`` gespeichert. Der Browser lädt es nur von
consens.io; die Quelle sieht keine Besucher-IP.

Bewusst nicht: KI-generierte Bilder, Stockfotos, Platzhalter,
Seiten-Standardbilder, Logos von Shops oder Verlagen. Passt nichts, gibt es
kein Bild (das Dashboard zeigt dann ein Symbol, ``watch_symbols``). Das Bild
landet nie in der OG-Karte oder im JSON-LD der Watch-Seite -- es ist eine
Vorschau, keine Werbung.
"""

from __future__ import annotations

import asyncio
import hashlib
import io
import ipaddress
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
from PIL import Image, ImageDraw, ImageStat

from app.core.observability import record_metric, safe_exception
from app.services import persistence_guard, watch_symbols
from app.services.source_documents import pinned_target


WATCH_IMAGES_COLLECTION = "watch_images"
STATUS_READY = "ready"
STATUS_NONE = "none"
STATUS_DISMISSED = "dismissed"
# Stand der Suche. Erfolglose Versuche einer älteren Suche zählen nicht mehr,
# sobald eine neue Stufe dazukommt (2 = Logos, 2026-10-12).
SEARCH_VERSION = 2
# Drei Prüfungen, in denen Seiten gelesen, aber kein passender Gegenstand
# gefunden wurde: die Watch ist abstrakt. Versuche, in denen keine einzige
# Seite lesbar war (Bot-Sperre, Zeitüberschreitung), zählen dort nicht, sind
# aber auf MAX_TRIES begrenzt -- sonst klopfen wir ewig bei gesperrten Shops.
MAX_ATTEMPTS = 3
MAX_TRIES = 8
# Fehlgeschlagene Judge-Aufrufe je Watch; danach wird er nicht mehr gefragt.
MAX_JUDGE_TRIES = 3
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

# Logos: höchstens zwei App-Icons als abgerundete Kacheln nebeneinander
# (2 x 144 + 16 = 304 px, also innerhalb von THUMB_SIDE). Kleiner als 64 px
# ist ein Favicon, das in der Kachel nur verschwimmt.
MAX_LOGOS = 2
LOGO_SIDE = 144
LOGO_GAP = 16
LOGO_MIN_SIDE = 64
# Ein App-Icon ist selten größer als 512 px; mehr dekodieren wir nicht.
LOGO_MAX_SOURCE_SIDE = 1024
LOGO_SECONDS = 15.0
ARTICLE_SECONDS = 15.0
LOGO_MAX_BYTES = 1_000_000
MAX_ICON_TRIES = 3
MAX_SITES = 20

TOKEN_RE = re.compile(r"^[0-9a-f]{20}$")
WATCH_ID_RE = re.compile(r"^[A-Za-z0-9]{8,32}$")

_PAGE_KINDS = frozenset({"text/html", "application/xhtml+xml"})
_IMAGE_KINDS = frozenset({"image/jpeg", "image/png", "image/webp", "image/gif"})
_IMAGE_FORMATS = ("JPEG", "PNG", "WEBP", "GIF")
_ICON_KINDS = _IMAGE_KINDS | {"image/x-icon", "image/vnd.microsoft.icon", "image/ico"}
_ICON_FORMATS = _IMAGE_FORMATS + ("ICO",)
_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_REDIRECTS = frozenset({301, 302, 303, 307, 308})
# Endungen, unter denen die eigentliche Domain eine Stufe tiefer liegt (bbc.co.uk).
_SECOND_LEVEL = frozenset({"co", "com", "org", "net", "ac", "gov", "edu", "or", "ne"})
# Weiterleitungen der Google-Suche sind kein Ort, an dem ein Thema zu Hause ist.
_NOT_A_SITE = frozenset({"vertexaisearch.cloud.google.com"})

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
    # Die eigene Seite: ihr Vorschaubild ist unsere OG-Karte, kein Thema.
    "consens.io",
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
# Logos: das App-Icon einer Seite als Kachel
# ----------------------------------------------------------------------

def _icon_size(value) -> int:
    sizes = re.findall(r"(\d+)\s*x\s*(\d+)", str(value or "").lower())
    return max((min(int(width), int(height)) for width, height in sizes), default=0)


def page_icons(html: str, base_url: str) -> list[str]:
    """Icon-URLs, die die Seite selbst festlegt, beste zuerst.

    Erst das App-Icon (apple-touch-icon, fluid-icon), dann große PNG-Icons,
    dann /apple-touch-icon.png, zuletzt Icons ohne Größe und /favicon.ico (ein
    .ico trägt manchmal 96 px). SVG und Masken-Icons fallen weg: SVG dekodieren
    wir nicht, eine Maske ist einfarbig.
    """
    soup = BeautifulSoup(html, "html.parser")
    ranked = []
    for node in soup.find_all("link", href=True, limit=80):
        rel = node.get("rel")
        rel = " ".join(rel) if isinstance(rel, list) else str(rel or "")
        rel = rel.lower()
        href = str(node.get("href") or "").strip()
        if not href or href.startswith("data:") or "mask-icon" in rel:
            continue
        if "svg" in str(node.get("type") or "").lower() or urlsplit(href).path.lower().endswith(".svg"):
            continue
        size = _icon_size(node.get("sizes"))
        if size and size < LOGO_MIN_SIDE:
            continue
        if "apple-touch-icon" in rel or "fluid-icon" in rel:
            rank, size = 0, size or 180
        elif "icon" in rel.split():
            rank = 1 if size else 3
        else:
            continue
        url = urljoin(base_url, href)
        if url.startswith(("https://", "http://")):
            ranked.append((rank, -size, len(ranked), url[:2000]))
    ranked.append((2, 0, len(ranked), urljoin(base_url, "/apple-touch-icon.png")))
    ranked.append((4, 0, len(ranked), urljoin(base_url, "/favicon.ico")))
    return list(dict.fromkeys(url for *_, url in sorted(ranked)))


def _ico_fits(content: bytes) -> bool:
    """Darf diese Datei überhaupt geöffnet werden?

    Bei .ico dekodiert Pillow das größte Bild schon in ``Image.open`` -- vor
    jeder Größenprüfung, und das Verzeichnis darf lügen (256 px im Kopf,
    12000 px im eingebetteten PNG: ~580 MB aus einer 580-kB-Datei). Deshalb
    die echten Maße jedes Eintrags vorher aus PNG-IHDR bzw. BMP-Kopf lesen.
    Andere Formate liest Pillow faul; ihre Maße prüft ``make_logo``.
    """
    if content[:4] != b"\x00\x00\x01\x00":
        return True
    count = int.from_bytes(content[4:6], "little")
    if not 0 < count <= 64 or len(content) < 6 + 16 * count:
        return False
    for index in range(count):
        entry = content[6 + 16 * index:22 + 16 * index]
        offset = int.from_bytes(entry[12:16], "little")
        head = content[offset:offset + 24]
        if head[:8] == _PNG_SIGNATURE:
            if len(head) < 24 or head[12:16] != b"IHDR":
                return False
            width, height = int.from_bytes(head[16:20], "big"), int.from_bytes(head[20:24], "big")
        else:
            if len(head) < 12:
                return False
            width = abs(int.from_bytes(head[4:8], "little", signed=True))
            height = abs(int.from_bytes(head[8:12], "little", signed=True)) // 2  # mit AND-Maske
        if width > LOGO_MAX_SOURCE_SIDE or height > LOGO_MAX_SOURCE_SIDE:
            return False
    return True


def make_logo(content: bytes):
    """Quadratische Kachel (LOGO_SIDE, RGB) aus einem Icon oder None.

    Ein Icon, das die Fläche füllt, füllt die Kachel. Ein Zeichen auf
    Durchsicht steht verkleinert auf der Fläche, für die es gemacht ist:
    helle Zeichen (für dunkle Tab-Leisten) auf Dunkel, sonst auf Weiß.
    """
    try:
        if not _ico_fits(content):
            return None
        with Image.open(io.BytesIO(content), formats=_ICON_FORMATS) as source:
            width, height = source.size
            if min(width, height) < LOGO_MIN_SIDE or width * height > MAX_PIXELS_DECODED:
                return None
            if not (1 / 2 <= width / height <= 2):
                return None
            image = source.convert("RGBA")
        image.thumbnail((LOGO_SIDE, LOGO_SIDE), Image.Resampling.LANCZOS)
        alpha = image.getchannel("A")
        solid = alpha.point(lambda value: 255 if value > 128 else 0)
        coverage = ImageStat.Stat(solid).mean[0] / 255
        if coverage < 0.75:
            light = ImageStat.Stat(image.convert("L"), mask=solid).mean[0] > 200
            background = (32, 33, 36) if light else (255, 255, 255)
            target = round(LOGO_SIDE * 0.72)
        else:
            corner = image.getpixel((0, 0))
            background = corner[:3] if corner[3] > 250 else (255, 255, 255)
            target = LOGO_SIDE
        scale = target / max(image.size)
        glyph = image.resize(
            (max(1, round(image.width * scale)), max(1, round(image.height * scale))),
            Image.Resampling.LANCZOS,
        )
        tile = Image.new("RGB", (LOGO_SIDE, LOGO_SIDE), background)
        tile.paste(glyph, ((LOGO_SIDE - glyph.width) // 2, (LOGO_SIDE - glyph.height) // 2), glyph)
        if tile.getcolors(maxcolors=2) is not None:
            return None  # eine leere Fläche ist kein Logo
        return tile
    except Exception:
        return None


def _rounded_mask(side: int):
    big = Image.new("L", (side * 4, side * 4), 0)
    ImageDraw.Draw(big).rounded_rectangle(
        (0, 0, side * 4 - 1, side * 4 - 1), radius=round(side * 4 * 0.22), fill=255,
    )
    return big.resize((side, side), Image.Resampling.LANCZOS)


def compose_logos(tiles) -> tuple[bytes, tuple[int, int]]:
    """Kacheln mit abgerundeten Ecken nebeneinander, als ein WebP mit Durchsicht."""
    tiles = list(tiles)[:MAX_LOGOS]
    width = len(tiles) * LOGO_SIDE + (len(tiles) - 1) * LOGO_GAP
    canvas = Image.new("RGBA", (width, LOGO_SIDE), (0, 0, 0, 0))
    mask = _rounded_mask(LOGO_SIDE)
    for index, tile in enumerate(tiles):
        canvas.paste(tile, (index * (LOGO_SIDE + LOGO_GAP), 0), mask)
    for options in ({"lossless": True, "method": 4}, {"quality": 85, "method": 4}):
        buffer = io.BytesIO()
        canvas.save(buffer, "WEBP", **options)
        if buffer.tell() <= STORED_MAX_BYTES:
            break
    return buffer.getvalue(), canvas.size


# ----------------------------------------------------------------------
# Kandidaten und Abruf
# ----------------------------------------------------------------------

def site_domain(host) -> str:
    """Die registrierbare Domain: docs.github.com -> github.com, www.bbc.co.uk -> bbc.co.uk.

    Eine IP-Adresse hat keine (aus 192.168.1.1 würde sonst "1.1")."""
    try:
        ipaddress.ip_address(str(host or "").strip("[]"))
        return ""
    except ValueError:
        pass
    labels = [label for label in str(host or "").lower().strip(".").split(".") if label]
    if len(labels) < 2:
        return ""
    keep = 3 if len(labels) >= 3 and labels[-2] in _SECOND_LEVEL and len(labels[-1]) == 2 else 2
    return ".".join(labels[-keep:])


def source_sites(sources, limit: int = MAX_SITES) -> list[tuple[str, list[str]]]:
    """(Domain, Quell-URLs) je Domain der Quellen, häufiger zitierte zuerst."""
    order, counts, urls = [], {}, {}
    for item in sources or []:
        if not isinstance(item, dict):
            continue
        url = str(item.get("url") or "").strip()
        if not url.startswith(("https://", "http://")) or len(url) > 2000:
            continue
        host = (urlsplit(url).hostname or "").lower()
        domain = site_domain(host)
        if not domain or host in _NOT_A_SITE or domain == "consens.io":
            continue
        if domain not in counts:
            order.append(domain)
            urls[domain] = []
        counts[domain] = counts.get(domain, 0) + 1
        if url not in urls[domain]:
            urls[domain].append(url)
    ranked = sorted(order, key=lambda domain: (-counts[domain], order.index(domain)))
    return [(domain, urls[domain][:3]) for domain in ranked[:limit]]


def named_sites(sites, question: "Question") -> list[str]:
    """Ohne Judge: Domains, deren Name ein Name aus der Frage ist.

    "Cursor oder Claude Code?" -> cursor.com, claude.com; "Stelle an der
    Hochschule Hannover" -> hs-hannover.de. Eine Seite, die nur berichtet
    (heise.de), heißt nicht wie das Thema und fällt so von selbst weg.
    Reihenfolge wie in der Frage.
    """
    names = {word for word in question.entities if len(word) >= 3 and not word.isdigit()}
    names |= {word for word in question.tokens if len(word) >= 5 and not word.isdigit()}
    positions: dict[str, int] = {}
    for index, word in enumerate(question.sequences[0] + question.sequences[1]):
        positions.setdefault(word, index)
    ranked = []
    for rank, (domain, _urls) in enumerate(sites):
        label = domain.split(".")[0]
        hits = [positions.get(part, 10_000) for part in {label, *label.split("-")} if part in names]
        if hits:
            ranked.append((min(hits), rank, domain))
    return [domain for *_, domain in sorted(ranked)][:MAX_LOGOS]

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


async def _fetch(client, url: str, kinds, max_bytes: int, accept: str, headers=None):
    """(endgültige URL, Bytes, Typ, abgeschnitten) über die gepinnte Adresse.
    ``headers`` ergänzt die eigenen (agent_web_images: Referer)."""
    for _ in range(4):
        target, host, hostname = await pinned_target(url)
        async with client.stream(
            "GET", target,
            headers={
                **(headers or {}),
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
        if purpose == "icon":
            return await _fetch(client, url, _ICON_KINDS, LOGO_MAX_BYTES,
                                "image/png,image/webp,image/x-icon,image/*;q=0.8")
        return await _fetch(client, url, _IMAGE_KINDS, IMAGE_MAX_BYTES,
                            "image/webp,image/png,image/jpeg,image/gif;q=0.9")


async def _first_photo(page_url, images, kind, fetch, tried: set):
    for image_url in images[:2]:
        if image_url in tried or _looks_like_logo(image_url, article=kind == "article"):
            continue
        tried.add(image_url)
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


async def _scan(urls, question: Question, fetch, progress: dict, articles: list, tried: set):
    """Der Gegenstand auf irgendeiner Quelle; passende Artikel sammelt er in
    ``articles`` (bleiben auch bei einer Zeitüberschreitung erhalten)."""
    for rank, page_url in enumerate(urls):
        try:
            final_url, content, _kind, _truncated = await asyncio.wait_for(
                fetch(page_url, "page"), FETCH_SECONDS + 1,
            )
            # Eine Weiterleitung (etwa die der Google-Suche) zählt als die
            # Seite, auf der sie endet.
            if _skip_host(urlsplit(final_url).hostname or ""):
                continue
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
            found = await _first_photo(final_url, images, "item", fetch, tried)
            if found:
                return found
        if article is not None:
            score = article_score(article[0], question.tokens, question.entities)
            if score:
                articles.append((score, rank, final_url, article[1]))
    return None


async def _article_photo(articles, fetch, tried: set):
    for _score, _rank, page_url, images in sorted(articles, key=lambda row: (-row[0], row[1]))[:3]:
        found = await _first_photo(page_url, images, "article", fetch, tried)
        if found:
            return found
    return None


async def _site_logo(domain: str, urls, fetch, progress: dict):
    """Kachel aus dem App-Icon der Startseite (sonst einer Quellseite) der Domain."""
    icons = []
    for page_url in [f"https://{domain}/", *list(urls or [])[:1]]:
        try:
            final_url, content, _kind, _truncated = await asyncio.wait_for(
                fetch(page_url, "page"), FETCH_SECONDS + 1,
            )
            icons = page_icons(content.decode("utf-8", errors="replace"), final_url)
        except Exception as exc:
            logging.info("Watch logo page skipped category=%s", safe_exception(exc))
            continue
        progress["looked"] = True
        break
    for icon_url in icons[:MAX_ICON_TRIES]:
        try:
            _url, data, _kind, truncated = await asyncio.wait_for(
                fetch(icon_url, "icon"), FETCH_SECONDS + 1,
            )
        except Exception as exc:
            logging.info("Watch logo fetch skipped category=%s", safe_exception(exc))
            continue
        if truncated:
            continue
        tile = await asyncio.to_thread(make_logo, data)
        if tile is not None:
            return tile
    return None


async def _find_logos(sites, fetch, progress: dict):
    tiles, domains = [], []
    for domain, urls in list(sites)[:MAX_LOGOS]:
        tile = await _site_logo(domain, urls, fetch, progress)
        if tile is not None:
            tiles.append(tile)
            domains.append(domain)
    if not tiles:
        return None
    content, (width, height) = await asyncio.to_thread(compose_logos, tiles)
    return {
        "content": content,
        "content_type": "image/webp",
        "kind": "logo",
        "width": int(width),
        "height": int(height),
        "source_url": f"https://{domains[0]}/",
        "source_host": ", ".join(domains),
    }


def logo_sites(sources, question: "Question", sites=None) -> list[tuple[str, list[str]]]:
    """Die Domains, deren Logo infrage kommt, mit ihren Quell-URLs.

    ``sites`` ist die Auswahl des Judges (auch aus einer früheren Prüfung,
    deren Quellen heute fehlen dürfen); ohne sie gilt die Namensregel.
    """
    known = source_sites(sources)
    urls = dict(known)
    chosen = named_sites(known, question) if sites is None else list(sites)
    return [(domain, urls.get(domain, [])) for domain in chosen[:MAX_LOGOS] if domain]


def search(sources, question: str, condition: str = "", *, fetch=None,
           sites=None) -> tuple[dict | None, bool]:
    """(Bild oder None, ob mindestens eine Seite gelesen wurde). Blockiert (Thread).

    Gegenstand, dann Logos, dann Artikel -- jede Stufe mit eigenem
    Zeitbudget, damit langsame Quellen die späteren nicht verdrängen; die
    Seiten liest nur die erste.

    Logos vor Artikeln: Ein Artikelbild wählt der Verlag, oft ist es eine
    allgemeine Teilen-Grafik; das Logo dessen, um den es geht, erkennt man
    sicherer wieder.
    """
    asked = Question(question, condition)
    urls = candidate_urls(sources)
    logos = logo_sites(sources, asked, sites)
    if not (urls or logos) or not asked.tokens:
        return None, False
    progress = {"looked": False}
    fetch = fetch or _http_fetch
    articles, tried = [], set()

    async def stage(work, seconds):
        try:
            return await asyncio.wait_for(work, seconds)
        except (asyncio.TimeoutError, TimeoutError):
            return None

    async def run():
        found = await stage(_scan(urls, asked, fetch, progress, articles, tried), ATTEMPT_SECONDS) if urls else None
        if found is None and logos:
            found = await stage(_find_logos(logos, fetch, progress), LOGO_SECONDS)
        if found is None and articles:
            found = await stage(_article_photo(list(articles), fetch, tried), ARTICLE_SECONDS)
        return found

    return asyncio.run(run()), progress["looked"]


def find_image(sources, question: str, condition: str = "", *, fetch=None,
               sites=None) -> dict | None:
    """Bild des Gegenstands, um den es geht, oder None. Blockiert (Thread)."""
    return search(sources, question, condition, fetch=fetch, sites=sites)[0]


# ----------------------------------------------------------------------
# Speichern, Ausliefern, Entfernen
# ----------------------------------------------------------------------

_KINDS = ("item", "article", "logo")


def _image_state(watch) -> dict:
    image = watch.get("image") if isinstance(watch, dict) else None
    return image if isinstance(image, dict) else {}


def _counts(image: dict) -> tuple[int, int]:
    """(attempts, tries) der aktuellen Suche; die einer älteren zählen nicht."""
    if image.get("version") != SEARCH_VERSION:
        return 0, 0
    attempts, tries = image.get("attempts"), image.get("tries")
    return (attempts if isinstance(attempts, int) else 0, tries if isinstance(tries, int) else 0)


def _stored_sites(image: dict):
    """Die Auswahl des Judges aus einer früheren Prüfung, sonst None."""
    sites = image.get("sites")
    if not isinstance(sites, list):
        return None
    return [str(site) for site in sites if isinstance(site, str) and site][:MAX_LOGOS]


def needs_image(watch: dict) -> bool:
    image = _image_state(watch)
    if image.get("status") in (STATUS_READY, STATUS_DISMISSED):
        return False
    attempts, tries = _counts(image)
    return attempts < MAX_ATTEMPTS and tries < MAX_TRIES


def has_symbol(watch: dict) -> bool:
    return isinstance(watch, dict) and watch.get("symbol") in watch_symbols.SYMBOLS


def _judge_failures(watch: dict) -> int:
    tries = watch.get("visual_tries") if isinstance(watch, dict) else None
    return tries if isinstance(tries, int) else 0


def _has_candidates(watch: dict, sources) -> bool:
    return bool(candidate_urls(sources) or source_sites(sources) or _stored_sites(_image_state(watch)))


def wants_work(watch: dict, sources) -> bool:
    """Fehlt der Watch ein Symbol oder (bei brauchbaren Quellen) ein Bild?"""
    return not has_symbol(watch) or (needs_image(watch) and _has_candidates(watch, sources))


def _now() -> datetime:
    return datetime.now(timezone.utc)


def store_result(watch_id: str, found: dict | None, *, db, looked: bool = True,
                 symbol: str | None = None, sites=None, attempted: bool = True,
                 judge_failed: bool = False) -> str:
    """Ergebnis eines Versuchs festhalten, solange die Watch noch eins braucht.

    Bild und Watch-Feld entstehen in einer Transaktion, die die Watch liest:
    eine gelöschte Watch bekommt kein Bild-Dokument mehr, ein inzwischen
    entferntes Bild kommt nicht zurück. Ein Symbol wird nur einmal gesetzt;
    die Domain-Auswahl des Judges (``sites``) reist mit dem Bildstand, damit
    spätere Versuche ihn nicht erneut fragen. Scheitert der Judge
    ``MAX_JUDGE_TRIES``-mal (``visual_tries``), wird er nicht mehr gefragt:
    es gilt das Standardsymbol und für Logos die Namensregel -- sonst fragte
    ihn jede Prüfung neu.
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
        updates = {}
        if symbol in watch_symbols.SYMBOLS and not has_symbol(current):
            updates["symbol"] = symbol
        if judge_failed:
            failures = _judge_failures(current) + 1
            updates["visual_tries"] = failures
            if failures >= MAX_JUDGE_TRIES and not has_symbol(current):
                updates["symbol"] = watch_symbols.DEFAULT_SYMBOL
        outcome = "kept"
        if not attempted and sites is not None and needs_image(current):
            # Der Judge hat gewählt, aber es gab nichts zu holen: die Wahl
            # trotzdem merken, sonst fragt ihn jede Prüfung neu.
            previous = _image_state(current)
            if _stored_sites(previous) is None:
                updates["image"] = {**previous, "sites": list(sites)[:MAX_LOGOS]}
        if attempted and needs_image(current):
            previous = _image_state(current)
            attempts, tries = _counts(previous)
            kept_sites = list(sites)[:MAX_LOGOS] if sites is not None else _stored_sites(previous)
            now = _now()
            if not found:
                state = {
                    "status": STATUS_NONE, "attempts": attempts + int(bool(looked)),
                    "tries": tries + 1, "last_attempt_at": now, "version": SEARCH_VERSION,
                }
                outcome = STATUS_NONE
            else:
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
                state = {
                    "status": STATUS_READY,
                    "kind": found.get("kind") if found.get("kind") in _KINDS else "item",
                    "token": token,
                    "width": found["width"],
                    "height": found["height"],
                    "source_url": found["source_url"][:2000],
                    "source_host": found["source_host"][:120],
                    "attempts": attempts + 1,
                    "tries": tries + 1,
                    "picked_at": now,
                    "version": SEARCH_VERSION,
                }
                outcome = STATUS_READY
            if kept_sites is not None:
                state["sites"] = kept_sites
            updates["image"] = state
        if updates:
            transaction.update(watch_ref, updates)
        return outcome

    outcome = watch_service._run_transaction(db, write)
    if outcome == STATUS_READY:
        forget(watch_id)
    return outcome


def _default_pick():
    """Der Judge wählt Symbol und Seiten -- nie in Unit-/E2E-/Mock-Läufen."""
    if not background_enabled():
        return None
    from app.services import watch_scheduler

    return watch_scheduler.pick_visual


def _pick_visual(pick, question: str, condition: str, sources) -> dict | None:
    """{symbol, sites} vom Judge oder None; Seiten nur aus den Quell-Domains.

    Ohne eine einzige Quell-Domain ist ``sites`` None statt []: Der Judge
    hatte nichts zu wählen, eine spätere Prüfung mit Quellen fragt erneut.
    """
    if pick is None:
        return None
    domains = [domain for domain, _urls in source_sites(sources)]
    try:
        verdict = pick(question, condition, domains)
    except Exception as exc:
        logging.warning("Watch visual pick failed category=%s", safe_exception(exc))
        return None
    if not isinstance(verdict, dict) or verdict.get("symbol") not in watch_symbols.SYMBOLS:
        return None
    sites = verdict.get("sites") if isinstance(verdict.get("sites"), list) else []
    return {
        "symbol": verdict["symbol"],
        "sites": [site for site in dict.fromkeys(sites) if site in domains][:MAX_LOGOS] if domains else None,
    }


def refresh_for_watch(watch_id: str, watch: dict, sources, question: str,
                      condition: str = "", *, db=None, fetch=None, pick=None) -> str:
    """Ein Versuch für eine Watch: Symbol (einmal) und Bild.

    Der Judge (``pick``) läuft, solange das Symbol oder seine Domain-Auswahl
    fehlt -- in der Regel also genau einmal pro Watch. Fällt er aus, gilt für
    Logos die Namensregel und das Dashboard zeigt das Standardsymbol.
    Quellen ohne Kandidaten zählen nicht als Bildversuch.
    """
    wants_symbol = not has_symbol(watch)
    wants_image = needs_image(watch) and _has_candidates(watch, sources)
    if not (wants_symbol or wants_image):
        return "skipped"
    if db is None:
        from app.core.security import db_firestore as db
    started = time.monotonic()
    sites = _stored_sites(_image_state(watch))
    symbol, verdict, judge_failed = None, None, False
    if (wants_symbol or (wants_image and sites is None)) and _judge_failures(watch) < MAX_JUDGE_TRIES:
        chooser = pick if pick is not None else _default_pick()
        verdict = _pick_visual(chooser, question, condition, sources)
        judge_failed = chooser is not None and verdict is None
        if verdict:
            symbol = verdict["symbol"]
            if verdict["sites"] is not None:
                sites = verdict["sites"]
    if wants_image and not (
        candidate_urls(sources) or logo_sites(sources, Question(question, condition), sites)
    ):
        wants_image = False
    found, looked = None, False
    if wants_image:
        try:
            found, looked = search(sources, question, condition, fetch=fetch, sites=sites)
        except Exception as exc:
            # Ein unerwarteter Fehler soll nicht jede Prüfung wiederholen: er
            # zählt als Versuch ohne gelesene Seite (MAX_TRIES deckelt das).
            logging.warning("Watch image search failed category=%s", safe_exception(exc))
            found, looked = None, False
    if not wants_image and not verdict and not judge_failed:
        return "skipped"
    outcome = store_result(
        watch_id, found, db=db, looked=looked, symbol=symbol, sites=sites, attempted=wants_image,
        judge_failed=judge_failed,
    )
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
    if not background_enabled() or not wants_work(watch, sources):
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
        # eines Artikels (darf die Kachel füllen); logo: abgerundete
        # App-Icon-Kacheln auf Durchsicht (ohne Rahmen zeigen).
        "kind": image.get("kind") if image.get("kind") in _KINDS else "item",
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

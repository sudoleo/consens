"""Ein Bild pro Topic aus den Quellen seiner Checks (seit 2026-10-15).

Dieselbe Suche wie bei Watches (``watch_images.search``): Produktfoto, sonst
die Logos der Seiten, um die es geht, sonst ein Artikelbild -- nie ein
KI-Bild, nie ein Stockfoto. Zweck wie dort: Wiedererkennen. Topics sind
öffentlich und redaktionell; es gibt keinen Besitzer, kein Symbol und kein
Entfernen durch Nutzer. Das Bild wird von consens.io ausgeliefert, verlinkt
auf seine Quelle und steht nie in og:image/JSON-LD.

Gespeichert wie bei Watches: die Bytes in ``topic_images/{topic_id}``, der
Stand (``status``, ``token``, Maße, Quelle, Versuche, gewählte Seiten) im
Feld ``image`` des Topics. Ein fertiges Bild wird nicht ersetzt.

Ohne gutes Bild zeigt die Seite ein Symbol (``symbol``, aus derselben festen
Liste wie bei Watches, ``watch_symbols``), das der Judge bei seiner einen
Wahl mitliefert. ``status: dismissed`` beendet die Suche für ein Topic, dessen
gefundenes Bild nicht taugt (z. B. eine reißerische Thumbnail-Grafik).
"""

from __future__ import annotations

import hashlib
import logging
import re
import threading
from collections import OrderedDict
from datetime import datetime, timezone

from app.core.observability import safe_exception
from app.services import topics, watch_images, watch_symbols

TOPIC_IMAGES_COLLECTION = "topic_images"
TOPIC_ID_RE = re.compile(r"^[A-Za-z0-9]{8,40}$")
STATUS_READY = watch_images.STATUS_READY
STATUS_NONE = watch_images.STATUS_NONE
STATUS_DISMISSED = watch_images.STATUS_DISMISSED
MAX_ATTEMPTS = watch_images.MAX_ATTEMPTS
MAX_TRIES = watch_images.MAX_TRIES

_CACHE: OrderedDict[str, tuple[str, bytes, str]] = OrderedDict()
_CACHE_LOCK = threading.Lock()
_CACHE_ENTRIES = 32


def _state(topic: dict) -> dict:
    image = topic.get("image") if isinstance(topic, dict) else None
    return image if isinstance(image, dict) else {}


def _counts(state: dict) -> tuple[int, int]:
    attempts = state.get("attempts")
    tries = state.get("tries")
    return (attempts if isinstance(attempts, int) else 0,
            tries if isinstance(tries, int) else 0)


def needs_image(topic: dict) -> bool:
    state = _state(topic)
    if state.get("status") in (STATUS_READY, STATUS_DISMISSED):
        return False
    attempts, tries = _counts(state)
    return attempts < MAX_ATTEMPTS and tries < MAX_TRIES


def _stored_sites(state: dict):
    sites = state.get("sites")
    return [site for site in sites if isinstance(site, str)] if isinstance(sites, list) else None


def _default_pick():
    """Der Judge wählt die offiziellen Seiten -- nie in Unit-/E2E-/Mock-Läufen."""
    if not watch_images.background_enabled():
        return None
    from app.services import watch_scheduler

    return watch_scheduler.pick_visual


def _pick_visual(pick, question: str, sources):
    """(offizielle Seiten unter den Quell-Domains, Symbol) wie bei Watches;
    (None, None), wenn der Judge nichts wählen konnte."""
    domains = [domain for domain, _urls in watch_images.source_sites(sources)]
    if pick is None or not domains:
        return None, None
    try:
        verdict = pick(question, "", domains)
    except Exception as exc:
        logging.warning("Topic visual pick failed category=%s", safe_exception(exc))
        return None, None
    verdict = verdict if isinstance(verdict, dict) else {}
    symbol = verdict.get("symbol") if verdict.get("symbol") in watch_symbols.SYMBOLS else None
    sites = verdict.get("sites")
    if not isinstance(sites, list):
        return None, symbol
    return [site for site in dict.fromkeys(sites) if site in domains][:watch_images.MAX_LOGOS], symbol


def store_result(topic_id: str, found: dict | None, *, db, looked: bool, sites=None,
                 symbol=None) -> str:
    """Ergebnis eines Versuchs festhalten; ein fertiges Bild bleibt."""
    topic_ref = db.collection(topics.TOPICS_COLLECTION).document(topic_id)
    image_ref = db.collection(TOPIC_IMAGES_COLLECTION).document(topic_id)

    def write(transaction):
        snapshot = topic_ref.get(transaction=transaction)
        current = snapshot.to_dict() if snapshot.exists else None
        if not current or not needs_image(current):
            return "kept"
        previous = _state(current)
        attempts, tries = _counts(previous)
        kept_sites = list(sites)[:watch_images.MAX_LOGOS] if sites is not None else _stored_sites(previous)
        now = datetime.now(timezone.utc)
        if not found:
            state = {"status": STATUS_NONE, "attempts": attempts + int(bool(looked)),
                     "tries": tries + 1, "last_attempt_at": now}
            outcome = STATUS_NONE
        else:
            token = hashlib.sha256(found["content"]).hexdigest()[:20]
            transaction.set(image_ref, {
                "token": token,
                "content": found["content"],
                "content_type": found["content_type"],
                "width": found["width"],
                "height": found["height"],
                "created_at": now,
            })
            state = {
                "status": STATUS_READY,
                "kind": found.get("kind") if found.get("kind") in ("item", "article", "logo") else "item",
                "token": token,
                "width": found["width"],
                "height": found["height"],
                "source_url": str(found.get("source_url") or "")[:2000],
                "source_host": str(found.get("source_host") or "")[:120],
                "attempts": attempts + 1,
                "tries": tries + 1,
                "picked_at": now,
            }
            outcome = STATUS_READY
        if kept_sites is not None:
            state["sites"] = kept_sites
        updates = {"image": state}
        if symbol in watch_symbols.SYMBOLS and not current.get("symbol"):
            updates["symbol"] = symbol
        transaction.update(topic_ref, updates)
        return outcome

    return topics._run_transaction(db, write)


def refresh_for_topic(topic_id: str, topic: dict, sources, *, db=None, fetch=None,
                      pick=None) -> str:
    """Ein Versuch für ein Topic. Der Judge läuft, solange seine Seitenwahl
    fehlt -- in der Regel also genau einmal pro Topic."""
    if not needs_image(topic) or not TOPIC_ID_RE.match(str(topic_id or "")):
        return "skipped"
    sources = [item for item in sources or [] if isinstance(item, dict)]
    question = str(topic.get("lead_question") or topic.get("title") or "")
    if not (watch_images.candidate_urls(sources) or watch_images.source_sites(sources)):
        return "skipped"
    if db is None:
        from app.core.security import db_firestore as db
    sites, symbol = _stored_sites(_state(topic)), None
    if sites is None:
        sites, symbol = _pick_visual(pick if pick is not None else _default_pick(), question, sources)
    try:
        found, looked = watch_images.search(sources, question, "", fetch=fetch, sites=sites)
    except Exception as exc:
        logging.warning("Topic image search failed category=%s", safe_exception(exc))
        found, looked = None, False
    return store_result(topic_id, found, db=db, looked=looked, sites=sites, symbol=symbol)


def schedule_after_run(topic_id: str, topic: dict, sources) -> bool:
    """Nach einem Check im Hintergrund versuchen; hält den Lauf nie auf."""
    if not watch_images.background_enabled() or not needs_image(topic):
        return False
    sources = list(sources or [])
    return watch_images._submit(
        "topic:" + str(topic_id), lambda: refresh_for_topic(topic_id, topic, sources),
    )


def image_view(topic_id: str, topic: dict) -> dict | None:
    """Was die Seiten vom Bild wissen dürfen (ohne Bytes)."""
    state = _state(topic)
    token = str(state.get("token") or "")
    if state.get("status") != STATUS_READY or not watch_images.TOKEN_RE.match(token):
        return None
    if not TOPIC_ID_RE.match(str(topic_id or "")):
        return None
    source_url = str(state.get("source_url") or "")[:2000]
    if not source_url.startswith(("https://", "http://")):
        source_url = ""

    def side(value):
        side_max = watch_images.THUMB_SIDE
        return value if isinstance(value, int) and 0 < value <= side_max else side_max

    return {
        "url": f"/api/topics/{topic_id}/image/{token}",
        "kind": state.get("kind") if state.get("kind") in ("item", "article", "logo") else "item",
        "width": side(state.get("width")),
        "height": side(state.get("height")),
        "source_url": source_url,
        "source_host": str(state.get("source_host") or "")[:120],
    }


def symbol_view(topic: dict) -> dict | None:
    """The drawn symbol a page shows when there is no picture."""
    name = topic.get("symbol") if isinstance(topic, dict) else None
    if name not in watch_symbols.SYMBOL_PATHS:
        return None
    return {"kind": "symbol", "name": name, "paths": watch_symbols.SYMBOL_PATHS[name]}


def visual_view(topic_id: str, topic: dict) -> dict | None:
    """The picture if there is one, else the symbol, else nothing."""
    return image_view(topic_id, topic) or symbol_view(topic)


def load_image(topic_id: str, token: str, *, db=None) -> tuple[bytes, str] | None:
    """Bytes zum Token; ein kleiner Prozess-Cache spart Firestore-Reads."""
    if not TOPIC_ID_RE.match(str(topic_id or "")) or not watch_images.TOKEN_RE.match(str(token or "")):
        return None
    with _CACHE_LOCK:
        cached = _CACHE.get(topic_id)
        if cached and cached[0] == token:
            _CACHE.move_to_end(topic_id)
            return cached[1], cached[2]
    if db is None:
        from app.core.security import db_firestore as db
    snapshot = db.collection(TOPIC_IMAGES_COLLECTION).document(topic_id).get()
    data = snapshot.to_dict() if snapshot.exists else None
    content = (data or {}).get("content")
    content_type = str((data or {}).get("content_type") or "")
    if (not data or data.get("token") != token or not isinstance(content, (bytes, bytearray))
            or content_type not in watch_images._IMAGE_KINDS):
        return None
    with _CACHE_LOCK:
        _CACHE[topic_id] = (token, bytes(content), content_type)
        while len(_CACHE) > _CACHE_ENTRIES:
            _CACHE.popitem(last=False)
    return bytes(content), content_type


"""Pictures from the pages a Topic's answer cites, for its Direct-links cards.

Every Direct-links card on a Topic page leads to a page the standing answer
rests on: the announcement, the model card, the paper. Such a page names its
own preview picture (``og:image``); on the card it puts a real picture on the
Topic page that nobody had to choose and no model was asked for. Which pages
qualify is a rule about the source, never a judgement of the picture:

* only primary sources, documentation and research, plus reporting from the
  Topic's preferred domains. Other reporting, community and rumor pages are
  left out: content farms illustrate with generated or stock pictures.
* a page that refuses the plain client has no picture; nothing is fetched
  around a bot wall.
* a picture two pages of one site share is that site's share card, not a
  picture of either page. Logo-like and flat images fall as they do for
  Watches (``watch_images``).

Stored next to the Topic's own picture: the bytes in ``topic_images`` (one
document per picture, ``{topic_id}_{token}``, the token is the content hash),
the list in the Topic's field ``pictures``. Served by consens.io and never
part of og:image or JSON-LD.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import threading
from collections import OrderedDict
from datetime import datetime, timezone
from urllib.parse import urlsplit

from app.core.observability import safe_exception
from app.services import source_links, topic_images, topics, watch_images
from app.services.public_markdown import strip_chat_framing
from app.services.source_catalog import canonical_source_url

MAX_PICTURES = 4
# Candidates one pass considers, stored pictures included.
MAX_PAGES = 8
# Passes in which a page gave no picture; after that it is left alone.
MAX_MISSES = 3
ATTEMPT_SECONDS = 60.0
# A card is at most ~430 px wide; 640 keeps it sharp on a dense screen.
PICTURE_BOX = (640, 480)
MIN_WIDTH = 300
# Landscape only: a square preview is an app icon or an avatar, a strip a banner.
PICTURE_ASPECT = (1.2, 2.4)
ELIGIBLE_ROLES = frozenset({"primary", "documentation", "research"})

_CACHE: OrderedDict[tuple[str, str], tuple[bytes, str]] = OrderedDict()
_CACHE_LOCK = threading.Lock()
_CACHE_ENTRIES = 24


def picture_key(url) -> str:
    """What makes two links the same page (scheme, host, path, query)."""
    return canonical_source_url(topics.canonical_evidence_url(url))


def _miss_key(key: str) -> str:
    # A map key in Firestore: a URL's dots and slashes would read as a path.
    return hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]


def _state(topic) -> dict:
    state = topic.get("pictures") if isinstance(topic, dict) else None
    return state if isinstance(state, dict) else {}


def stored_items(topic) -> list[dict]:
    """The stored list, structurally checked; anything unreadable is dropped."""
    items = []
    for item in _state(topic).get("items") or []:
        if not isinstance(item, dict):
            continue
        token = str(item.get("token") or "")
        source_url = str(item.get("source_url") or "")
        width, height = item.get("width"), item.get("height")
        if (not watch_images.TOKEN_RE.match(token) or not picture_key(source_url)
                or not all(isinstance(side, int) and not isinstance(side, bool) and 0 < side <= 2000
                           for side in (width, height))):
            continue
        items.append({
            "token": token, "width": width, "height": height,
            "source_url": source_url[:2000],
            "source_host": str(item.get("source_host") or "")[:120],
            "title": str(item.get("title") or "")[:200],
            "image_url": str(item.get("image_url") or "")[:2000],
        })
    return items[:MAX_PICTURES]


def _misses(topic) -> dict[str, int]:
    misses = _state(topic).get("misses")
    if not isinstance(misses, dict):
        return {}
    return {
        str(key): count for key, count in misses.items()
        if isinstance(count, int) and not isinstance(count, bool) and count > 0
    }


def candidate_pages(evidence, answer_md: str, preferred_domains) -> list[dict]:
    """The pages a picture may come from, the Direct links first.

    The order is the page's: its source list (best role first), from which
    ``source_links.key_links`` picks the cards. A picture is matched to its
    card by URL, so a different order here would only cost coverage.
    """
    ranked = []
    for position, item in enumerate(evidence or []):
        if not isinstance(item, dict):
            continue
        verdict = topics.classify_evidence(
            item.get("url"), item.get("type"), preferred_domains,
            title=str(item.get("title") or ""), publisher=str(item.get("publisher") or ""),
        )
        if verdict["is_indirect"] or source_links.is_own_page(verdict["url"]):
            continue
        entry = source_links.source_entries([{**item, "url": verdict["url"]}])[0]
        entry["eligible"] = verdict["role"] in ELIGIBLE_ROLES or (
            verdict["role"] == "reporting" and verdict["is_preferred"]
        )
        ranked.append(((verdict["rank"], not verdict["is_preferred"], position), entry))
    ranked.sort(key=lambda row: row[0])
    entries = [row[1] for row in ranked]
    links = source_links.key_links(entries, answer_md)
    linked = {link["url"] for link in links}
    pages, seen = [], set()
    for entry in links + [entry for entry in entries if entry["url"] not in linked]:
        url = str(entry.get("url") or "")
        key = picture_key(url)
        parts = urlsplit(url)
        host = (parts.hostname or "").lower()
        if (not entry.get("eligible") or not key or key in seen or len(url) > 2000
                or not host or watch_images._skip_host(host)
                or parts.path.lower().endswith(".pdf")):
            continue
        seen.add(key)
        pages.append({
            "url": url, "key": key,
            "site": watch_images.site_domain(host) or host,
            "host": host.removeprefix("www."),
            "title": (entry["title"] if entry["url"] in linked else source_links.display_title(entry))[:200],
        })
    return pages


def _fetch_failure(exc: BaseException) -> str:
    # watch_images._fetch raises its own short codes ("status_403",
    # "unsupported_type"); anything else is named by its class only.
    if isinstance(exc, ValueError) and str(exc).replace("_", "").isalnum():
        return str(exc)[:40]
    return safe_exception(exc)


async def _page_picture(page: dict, fetch):
    """(the page's own preview picture as a card thumbnail or None, why not)."""
    try:
        final_url, content, _kind, _truncated = await asyncio.wait_for(
            fetch(page["url"], "page"), watch_images.FETCH_SECONDS + 1,
        )
    except Exception as exc:
        logging.info("Topic picture page skipped category=%s", safe_exception(exc))
        return None, "page not readable (" + _fetch_failure(exc) + ")"
    final_host = (urlsplit(final_url).hostname or "").lower()
    # A page that sends the client elsewhere (login, consent, another site)
    # shows that place's picture, not its own.
    if watch_images._skip_host(final_host) or (watch_images.site_domain(final_host) or final_host) != page["site"]:
        return None, "leads to another site"
    images = watch_images.page_preview(content.decode("utf-8", errors="replace"), final_url)
    reason = "no preview picture"
    for image_url in images[:2]:
        if watch_images._looks_like_logo(image_url, article=True):
            reason = "preview is a logo or a default image"
            continue
        try:
            _url, data, _kind, truncated = await asyncio.wait_for(
                fetch(image_url, "image"), watch_images.FETCH_SECONDS + 1,
            )
        except Exception as exc:
            logging.info("Topic picture fetch skipped category=%s", safe_exception(exc))
            reason = "preview not readable (" + _fetch_failure(exc) + ")"
            continue
        if truncated:
            reason = "preview too large"
            continue
        thumbnail = await asyncio.to_thread(
            watch_images.make_thumbnail, data, box=PICTURE_BOX, aspect=PICTURE_ASPECT,
        )
        if not thumbnail or thumbnail[1][0] < MIN_WIDTH:
            reason = "preview is flat, too small or not landscape"
            continue
        stored, (width, height) = thumbnail
        return {
            "content": stored, "content_type": "image/webp",
            "token": hashlib.sha256(stored).hexdigest()[:20],
            "width": int(width), "height": int(height),
            "source_url": page["url"], "source_host": page["host"],
            "title": page["title"], "image_url": image_url[:2000],
        }, ""
    return None, reason


def _same_picture(left: dict, right: dict) -> bool:
    return left["token"] == right["token"] or (
        bool(left.get("image_url")) and left.get("image_url") == right.get("image_url")
    )


async def _gather(pages, stored: dict, misses: dict, fetch, picked: dict, missed: dict,
                  generic: set, notes: dict):
    """Walk the candidates in order until four have a picture.

    ``picked`` (page key -> picture), ``missed`` and ``generic`` fill as it
    goes, so a pass that runs out of time keeps what it has. ``notes`` says
    per page what happened, for the backfill's report.
    """
    by_site: dict[str, list[tuple[str, dict]]] = {}
    for page in pages[:MAX_PAGES]:
        if len(picked) >= MAX_PICTURES:
            break
        key = page["key"]
        found = stored.get(key)
        if found is not None:
            notes[key] = "stored"
        else:
            if misses.get(_miss_key(key), 0) >= MAX_MISSES:
                notes[key] = "given up"
                continue
            found, reason = await _page_picture(page, fetch)
            if found is None:
                missed[key] = misses.get(_miss_key(key), 0) + 1
                notes[key] = reason
                continue
            notes[key] = "picture"
        twins = [other for other, picture in by_site.get(page["site"], []) if _same_picture(picture, found)]
        if twins:
            # One picture on two pages of a site is the site's share card.
            for other in twins + [key]:
                picked.pop(other, None)
                generic.add(other)
                notes[other] = "share card of the site"
            continue
        by_site.setdefault(page["site"], []).append((key, found))
        picked[key] = found


def find_pictures(pages, topic: dict, *, fetch=None, notes=None) -> tuple[list[dict], dict[str, int]]:
    """(pictures in card order, miss counts for the pages looked at). Blocks.

    A page with a stored picture is not fetched again; a page whose misses
    reached the limit is not asked again.
    """
    stored = {picture_key(item["source_url"]): item for item in stored_items(topic)}
    misses = _misses(topic)
    picked: dict[str, dict] = {}
    missed: dict[str, int] = {}
    generic: set[str] = set()
    notes = notes if notes is not None else {}

    async def run():
        try:
            await asyncio.wait_for(
                _gather(pages, stored, misses, fetch or watch_images._http_fetch,
                        picked, missed, generic, notes),
                ATTEMPT_SECONDS,
            )
        except (asyncio.TimeoutError, TimeoutError):
            pass

    asyncio.run(run())
    # Only the pages still cited keep a count, so the memo cannot grow.
    counts = {}
    for page in pages[:MAX_PAGES]:
        key = page["key"]
        count = MAX_MISSES if key in generic else missed.get(key, misses.get(_miss_key(key), 0))
        if count and key not in picked:
            counts[_miss_key(key)] = min(int(count), MAX_MISSES)
    order = [page["key"] for page in pages]
    pictures = sorted(picked.items(), key=lambda row: order.index(row[0]))
    return [picture for _key, picture in pictures][:MAX_PICTURES], counts


def _doc_id(topic_id: str, token: str) -> str:
    return f"{topic_id}_{token}"


def store(topic_id: str, pictures, misses, *, db) -> str:
    """Write the list, the bytes of new pictures, and drop bytes no card uses."""
    topic_ref = db.collection(topics.TOPICS_COLLECTION).document(topic_id)
    images = db.collection(topic_images.TOPIC_IMAGES_COLLECTION)

    def write(transaction):
        snapshot = topic_ref.get(transaction=transaction)
        current = snapshot.to_dict() if snapshot.exists else None
        if not current:
            return "skipped"
        now = datetime.now(timezone.utc)
        before = {item["token"] for item in stored_items(current)}
        items = []
        for picture in pictures:
            if isinstance(picture.get("content"), (bytes, bytearray)) and picture["token"] not in before:
                transaction.set(images.document(_doc_id(topic_id, picture["token"])), {
                    "token": picture["token"], "topic_id": topic_id,
                    "content": bytes(picture["content"]), "content_type": picture["content_type"],
                    "width": picture["width"], "height": picture["height"], "created_at": now,
                })
            items.append({name: picture[name] for name in (
                "token", "width", "height", "source_url", "source_host", "title", "image_url",
            )})
        for token in before - {item["token"] for item in items}:
            transaction.delete(images.document(_doc_id(topic_id, token)))
        transaction.update(topic_ref, {"pictures": {
            "items": items, "misses": dict(misses), "updated_at": now,
        }})
        return "ready" if items else "none"

    return topics._run_transaction(db, write)


def standing_pages(topic: dict, *, db=None) -> list[dict]:
    """The candidate pages of the answer the Topic page shows."""
    run_id = str(topic.get("accepted_run_id") or topic.get("latest_run_id") or "")
    run = topics.get_run(topic["id"], run_id, db=db) if run_id else None
    if not run:
        return []
    return candidate_pages(
        run.get("evidence"), strip_chat_framing(run.get("consensus_md") or ""),
        (topic.get("source_rules") or {}).get("preferred_domains") or [],
    )


def refresh_for_topic(topic_id: str, *, db=None, fetch=None) -> str:
    """One pass for a Topic, from the answer its page shows.

    The pass reads the Topic and its standing run itself: the newest check is
    not always the one the page shows (a check whose search missed the
    evidence does not replace the answer), and the cards belong to the page.
    """
    if not topic_images.TOPIC_ID_RE.match(str(topic_id or "")):
        return "skipped"
    if db is None:
        db = topics.db_firestore
    topic = topics.get_topic(topic_id, db=db)
    if not topic or topic.get("status") not in {"active", "paused"}:
        return "skipped"
    pages = standing_pages(topic, db=db)
    if not pages and not _state(topic):
        return "skipped"
    try:
        pictures, misses = find_pictures(pages, topic, fetch=fetch)
    except Exception as exc:
        logging.warning("Topic picture search failed category=%s", safe_exception(exc))
        return "skipped"
    before = [(item["token"], picture_key(item["source_url"])) for item in stored_items(topic)]
    after = [(item["token"], picture_key(item["source_url"])) for item in pictures]
    if before == after and misses == _misses(topic):
        return "kept"
    return store(topic_id, pictures, misses, db=db)


def schedule_after_run(topic_id: str) -> bool:
    """After a check, in the background; never holds the check up."""
    if not watch_images.background_enabled() or not topic_images.TOPIC_ID_RE.match(str(topic_id or "")):
        return False
    return watch_images._submit(
        "topic-pictures:" + str(topic_id), lambda: refresh_for_topic(topic_id),
    )


def with_pictures(topic_id: str, topic: dict, links) -> list[dict]:
    """The Direct links, each with its stored picture where there is one."""
    links = list(links or [])
    if not topic_images.TOPIC_ID_RE.match(str(topic_id or "")):
        return links
    by_key = {picture_key(item["source_url"]): item for item in stored_items(topic)}
    if not by_key:
        return links
    shown = []
    for link in links:
        item = by_key.get(picture_key(link.get("url")))
        shown.append({**link, "picture": {
            "url": f"/api/topics/{topic_id}/picture/{item['token']}",
            "width": item["width"], "height": item["height"],
        }} if item else link)
    return shown


def load_picture(topic_id: str, token: str, *, db=None) -> tuple[bytes, str] | None:
    """Bytes for a token; a small process cache saves Firestore reads."""
    if (not topic_images.TOPIC_ID_RE.match(str(topic_id or ""))
            or not watch_images.TOKEN_RE.match(str(token or ""))):
        return None
    cache_key = (topic_id, token)
    with _CACHE_LOCK:
        cached = _CACHE.get(cache_key)
        if cached:
            _CACHE.move_to_end(cache_key)
            return cached
    if db is None:
        db = topics.db_firestore
    snapshot = db.collection(topic_images.TOPIC_IMAGES_COLLECTION).document(_doc_id(topic_id, token)).get()
    data = snapshot.to_dict() if snapshot.exists else None
    content = (data or {}).get("content")
    content_type = str((data or {}).get("content_type") or "")
    if (not data or data.get("token") != token or not isinstance(content, (bytes, bytearray))
            or content_type not in watch_images._IMAGE_KINDS):
        return None
    with _CACHE_LOCK:
        _CACHE[cache_key] = (bytes(content), content_type)
        while len(_CACHE) > _CACHE_ENTRIES:
            _CACHE.popitem(last=False)
    return bytes(content), content_type

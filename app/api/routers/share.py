import json
import logging
import re
from datetime import datetime, timezone
from urllib.parse import quote
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Request, Body, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from app.core.assets import register_asset_globals
from app.core.rate_limit import limiter
from app.core.observability import safe_exception
from app.core.security import verify_user_token, extract_id_token, is_user_admin
from app.core import seo_entity
from app.core.site import SITE_URL
from app.services import check_page, og_image, source_links
from app.services import share_snapshots as snapshots
from app.services.history_view import PAGE_CHART_WIDTH, build_history_view, day_label
from app.services import watch_service
from app.services.share_snapshots import ShareError
from app.services.public_markdown import (
    render_public_markdown,
    markdown_to_plaintext,
    source_host,
    source_site_name,
)

# Widerrufbare öffentliche Inhalte (Share-Seiten, historische Watch-Versionen,
# OG-Karten) werden nie langlebig oder `immutable` ausgeliefert: Browser und
# Proxies dürfen sie höchstens kurz halten. Zusammen mit dem In-Process-Cache
# (snapshots.SHARE_CACHE_TTL_SECONDS) bleibt die Verzögerung eines Widerrufs
# unter snapshots.PUBLIC_REVOCATION_MAX_DELAY_SECONDS (Review R18).
SHARE_CACHE_CONTROL = "public, max-age=60, s-maxage=60, stale-while-revalidate=60"

templates = Jinja2Templates(directory="templates")
register_asset_globals(templates)


def clip_words(text, limit: int) -> str:
    """Cut at the last word boundary within ``limit`` and end with "…".

    Tab titles, search results and link previews ended mid-word ("…actually
    includ | consens.io") with ``question[:70]`` (Apple-Audit L8).
    """
    text = " ".join(str(text or "").split())
    if len(text) <= limit:
        return text
    cut = text[: limit - 1]
    space = cut.rfind(" ")
    if space >= limit // 2:
        cut = cut[:space]
    return cut.rstrip(" ,;:-–—") + "…"


templates.env.filters["clip_words"] = clip_words

router = APIRouter()

_SHARE_ERROR_STATUS = {
    "not_found": 404,
    "forbidden": 403,
    "quota_exceeded": 429,
}

# "BestModel: Grok" (ggf. mit Markdown-Sternchen) im Differences-Freitext.
_BEST_MODEL_RE = re.compile(
    r"^\s*\**\s*Best\s*Model\s*\**\s*[:\-]\s*(.+?)\s*$",
    re.IGNORECASE | re.MULTILINE,
)


# Shared with the curated Topic pages (app/services/check_page.py).
_build_watch_history_view = build_history_view
_build_watch_drift_view = check_page.drift_view
_watch_state_view = check_page.state_view


def _watch_datetime_view(value, timezone_name=""):
    if not isinstance(value, datetime):
        return {"iso": "", "display": "", "day": ""}
    display_zone = "UTC"
    normalized = value.astimezone(timezone.utc)
    if timezone_name:
        try:
            normalized = value.astimezone(ZoneInfo(timezone_name))
            display_zone = timezone_name
        except (ZoneInfoNotFoundError, ValueError):
            pass
    return {
        "iso": value.astimezone(timezone.utc).isoformat(),
        "display": normalized.strftime("%Y-%m-%d %H:%M ") + display_zone,
        "day": day_label(normalized),
    }


def _build_watch_page_meta(meta, history_points):
    if not meta and not history_points:
        return None
    meta = meta or {}
    status = meta.get("status") or "history"
    labels = {
        "active": "Active",
        "paused": "Paused",
        "paused_error": "Paused after errors",
        "resolved": "Resolved",
        "history": "Archived history",
    }
    last_run = meta.get("last_run_at")
    if not isinstance(last_run, datetime) and history_points:
        last_run = history_points[-1].get("ts")
    timezone_name = str(meta.get("timezone") or "")
    run_time = str(meta.get("run_time") or "")
    run_weekday = str(meta.get("run_weekday") or "")
    interval = str(meta.get("interval") or "")
    schedule_label = interval.capitalize()
    if interval == "weekly" and run_weekday:
        schedule_label += f" on {run_weekday.capitalize()}"
    if run_time and timezone_name:
        schedule_label += f" at {run_time} ({timezone_name})"
    return {
        "status": status,
        "status_label": labels.get(status, "Paused"),
        "is_active": status == "active",
        "interval": interval,
        "interval_label": interval.capitalize(),
        "schedule_label": schedule_label,
        "last_run": _watch_datetime_view(last_run, timezone_name),
        "next_run": _watch_datetime_view(meta.get("next_run_at"), timezone_name),
        "created": _watch_datetime_view(meta.get("created_at"), timezone_name),
        "goal": str(meta.get("condition") or ""),
        "resolution": _resolution_view(meta.get("resolution"), timezone_name),
        "image": meta.get("image") if isinstance(meta.get("image"), dict) else None,
    }


def _resolution_view(resolution, timezone_name=""):
    if not isinstance(resolution, dict) or not resolution.get("run_id"):
        return None
    return {
        "run_id": str(resolution.get("run_id") or ""),
        "at": _watch_datetime_view(resolution.get("at"), timezone_name),
        "goal": str(resolution.get("condition") or ""),
        "reason": str(resolution.get("reason") or ""),
        "sources": [
            item for item in resolution.get("sources") or []
            if isinstance(item, dict) and str(item.get("url") or "").startswith(("http://", "https://"))
        ][:4],
    }


def _score_stats(data):
    """(agreement-dict, model_count, contradiction_count) aus einem Share-Doc."""
    differences_data = data.get("differences_data")
    differences_data = differences_data if isinstance(differences_data, dict) else {}
    agreement = differences_data.get("agreement")
    agreement = agreement if isinstance(agreement, dict) else {}
    model_count = (
        len(differences_data.get("models_compared") or [])
        or len(data.get("included_models") or [])
    )
    contradiction_count = sum(
        1 for d in (differences_data.get("differences") or [])
        if isinstance(d, dict) and d.get("type") == "contradiction"
    )
    return agreement, model_count, contradiction_count


def _standing_run_id(meta, data) -> str:
    """The Watch version a page shows by default: the one whose answer stands."""
    meta = meta or {}
    return str(
        meta.get("accepted_run_id") or meta.get("last_successful_run_id")
        or data.get("latest_watch_run_id") or ""
    )


def _resolve_display_version(data, watch_page, requested_version, latest_run_id, share_id):
    """Resolve the only snapshot allowed to supply visible answer content."""
    original = {
        "id": "original",
        "kind": "original",
        "data": data,
        "snapshot": None,
        "fallback_notice": "",
    }
    if not watch_page or requested_version == "original":
        return original
    if requested_version:
        snapshot = snapshots.get_watch_version(share_id, requested_version)
        if snapshot is None:
            return None
        return {
            "id": requested_version,
            "kind": "historical",
            "data": {**data, **snapshot},
            "snapshot": snapshot,
            "fallback_notice": "",
        }
    if not latest_run_id:
        return original
    snapshot = snapshots.get_watch_version(share_id, latest_run_id)
    if snapshot is None:
        original["kind"] = "fallback"
        original["fallback_notice"] = (
            "The latest Watch check has no complete saved version. "
            "Showing the original consensus and all of its original metadata instead."
        )
        return original
    return {
        "id": latest_run_id,
        "kind": "current",
        "data": {**data, **snapshot},
        "snapshot": snapshot,
        "fallback_notice": "",
    }


def _require_uid(request, data):
    id_token = extract_id_token(request, data)
    if not id_token:
        raise HTTPException(status_code=401, detail="Authentication required")
    try:
        return verify_user_token(id_token)
    except Exception:
        raise HTTPException(status_code=401, detail="Authentication failed")


def _raise_share_error(exc):
    raise HTTPException(status_code=_SHARE_ERROR_STATUS.get(exc.code, 400), detail=exc.message)


@router.post("/api/share")
@limiter.limit("5/minute")
def create_share(request: Request, data: dict = Body(...)):
    uid = _require_uid(request, data)
    result_id = str(data.get("result_id") or "").strip()
    if not result_id:
        raise HTTPException(status_code=400, detail="Missing required field: result_id")

    try:
        result = snapshots.create_share_from_pending(uid, result_id, visibility="public")
    except ShareError as exc:
        _raise_share_error(exc)
    except Exception as exc:
        logging.error("create_share failed category=%s", safe_exception(exc))
        raise HTTPException(status_code=500, detail="Error creating share link")

    path = snapshots.share_path(result["slug"], result["share_id"])
    return {
        "status": "success",
        "share_id": result["share_id"],
        "path": path,
        "url": SITE_URL + path,
        "created": result["created"],
    }


@router.delete("/api/share/{share_id}")
@limiter.limit("10/minute")
def delete_share(request: Request, share_id: str, data: dict = Body(default={})):
    uid = _require_uid(request, data)
    try:
        snapshots.revoke_share(share_id, uid, is_admin=is_user_admin(uid))
    except ShareError as exc:
        _raise_share_error(exc)
    except Exception as exc:
        logging.error("delete_share failed category=%s", safe_exception(exc))
        raise HTTPException(status_code=500, detail="Error revoking share link")
    return {"status": "success", "message": "Share link revoked."}


@router.get("/api/my/shares")
@limiter.limit("20/minute")
def my_shares(request: Request):
    uid = _require_uid(request, {})
    cursor = str(request.query_params.get("cursor") or "")[:64]
    try:
        page = snapshots.list_shares_for_owner_page(uid, cursor=cursor)
    except Exception as exc:
        logging.error("my_shares failed category=%s", safe_exception(exc))
        raise HTTPException(status_code=500, detail="Error loading shares")
    return {
        "status": "success",
        "shares": page["items"],
        "has_more": page["has_more"],
        "next_cursor": page["next_cursor"],
        "site_url": SITE_URL,
    }


@router.post("/api/share/{share_id}/indexing-request")
@limiter.limit("10/minute")
def request_indexing(request: Request, share_id: str, data: dict = Body(default={})):
    """Owner nominiert die eigene öffentliche Seite für den Google-Index.

    Setzt nur ``index_requested`` – die eigentliche Freigabe (``indexed``)
    bleibt eine Admin-Entscheidung in der Moderations-UI.
    """
    uid = _require_uid(request, data)
    want = data.get("want", True)
    if not isinstance(want, bool):
        raise HTTPException(status_code=400, detail="want must be a boolean")
    try:
        state = snapshots.request_share_indexing(share_id, uid, want=want)
    except ShareError as exc:
        _raise_share_error(exc)
    except Exception as exc:
        logging.error("request_indexing failed category=%s", safe_exception(exc))
        raise HTTPException(status_code=500, detail="Error updating listing request")
    return {"status": "success", **state}


@router.post("/api/share/{share_id}/report")
@limiter.limit("3/minute")
def report_share(request: Request, share_id: str, data: dict = Body(default={})):
    # Bewusst ohne Auth (Besucher sollen melden können) und ohne IP/UA-
    # Speicherung; Missbrauchsschutz nur über das Rate-Limit.
    reason = str(data.get("reason") or "other")
    try:
        snapshots.report_share(share_id, reason)
    except ShareError as exc:
        _raise_share_error(exc)
    except Exception as exc:
        logging.error("report_share failed category=%s", safe_exception(exc))
        raise HTTPException(status_code=500, detail="Error reporting page")
    return {"status": "success", "message": "Thanks, this page has been reported for review."}


def _unavailable_response(request, status_code, heading, message, *, sign_in_href=""):
    response = templates.TemplateResponse(
        request=request,
        name="share_unavailable.html",
        context={"heading": heading, "message": message, "sign_in_href": sign_in_href},
        status_code=status_code,
    )
    response.headers["X-Robots-Tag"] = "noindex, noarchive"
    return response


@router.get("/sitemap-shares.xml")
@limiter.limit("30/minute")
def sitemap_shares(request: Request):
    """Nur vom Admin indexierte UND aktive Shares – alles andere ist noindex
    und hat in der Sitemap nichts verloren."""
    try:
        urls = snapshots.list_indexed_share_urls()
    except Exception as exc:
        logging.error("sitemap_shares failed category=%s", safe_exception(exc))
        raise HTTPException(status_code=500, detail="Error building sitemap")

    entries = "\n".join(
        "  <url>\n"
        f"    <loc>{SITE_URL}{item['path']}</loc>\n"
        + (f"    <lastmod>{item['lastmod']}</lastmod>\n" if item["lastmod"] else "")
        + "    <changefreq>monthly</changefreq>\n"
        "  </url>"
        for item in urls
    )
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{entries}\n"
        "</urlset>\n"
    )
    return Response(
        content=xml,
        media_type="application/xml",
        headers={"Cache-Control": "public, max-age=3600"},
    )


@router.get("/questions", response_class=HTMLResponse)
@limiter.limit("30/minute")
def questions_hub(request: Request):
    """Öffentliche Hub-Seite: verlinkt alle indexierten Share-Seiten intern.

    SEO-Zweck: indexierte Shares hingen bisher nur in der Sitemap ("verwaiste
    Seiten") – der Hub gibt ihnen einen Crawl-Pfad aus der Hauptnavigation.
    """
    try:
        entries = snapshots.list_hub_shares()
    except Exception as exc:
        logging.error("list_hub_shares failed category=%s", safe_exception(exc))
        entries = []

    # "tracked over time" counts the Watches that are still checked; a paused
    # one is not tracked any more (Apple-Audit L2).
    watch_count = sum(1 for e in entries if (e.get("watch") or {}).get("active"))
    jsonld = {
        "@context": "https://schema.org",
        "@type": "CollectionPage",
        "@id": SITE_URL + "/questions",
        "url": SITE_URL + "/questions",
        "name": "AI Consensus Library",
        "description": (
            "Questions answered by multiple AI models independently, "
            "cross-checked and scored for agreement."
        ),
        "isPartOf": seo_entity.SITE_REF,
        "publisher": seo_entity.ORG_REF,
        "mainEntity": {
            "@type": "ItemList",
            "numberOfItems": len(entries),
            "itemListElement": [
                {
                    "@type": "ListItem",
                    "position": index + 1,
                    "name": entry["question"][:110],
                    "url": SITE_URL + entry["path"],
                }
                for index, entry in enumerate(entries[:50])
            ],
        },
    }
    jsonld_html = seo_entity.dumps(seo_entity.page_graph(jsonld))

    response = templates.TemplateResponse(request=request, name="questions.html", context={
        "entries": entries,
        "total_count": len(entries),
        "watch_count": watch_count,
        "jsonld": jsonld_html,
    })
    response.headers["Cache-Control"] = "public, max-age=300"
    return response


@router.get("/s/{slug_id}/og.png")
@limiter.limit("60/minute")
def share_og_card(request: Request, slug_id: str):
    """Generierte Open-Graph-Karte (PNG) einer öffentlichen Share-Seite."""
    _slug, share_id = snapshots.split_slug_id(slug_id)
    if not snapshots.is_valid_share_id(share_id) or not og_image.is_available():
        raise HTTPException(status_code=404, detail="Not found")
    try:
        data = snapshots.get_share_cached(share_id)
    except Exception as exc:
        logging.error(
            "share_og_card lookup failed category=%s", safe_exception(exc)
        )
        raise HTTPException(status_code=500, detail="Error loading share")
    if (data is None or data.get("status") != "active"
            or str(data.get("visibility") or "public") == "private"):
        raise HTTPException(status_code=404, detail="Not found")

    try:
        history_points = snapshots.list_watch_history(share_id)
    except Exception as exc:
        logging.error(
            "share_og_card history failed category=%s", safe_exception(exc)
        )
        history_points = []
    try:
        watch_meta = watch_service.get_public_watch_meta(share_id)
    except Exception:
        watch_meta = None
    watch_page = _build_watch_page_meta(watch_meta, history_points)
    latest_run_id = _standing_run_id(watch_meta, data)
    try:
        display_version = _resolve_display_version(data, watch_page, "", latest_run_id, share_id)
    except Exception:
        display_version = None
    display_data = display_version["data"] if display_version else data
    agreement, model_count, contradiction_count = _score_stats(display_data)
    score = agreement.get("score")
    if not isinstance(score, (int, float)):
        score = display_data.get("agreement_score")
    display_payload = snapshots.public_share_payload(display_data)
    answered_on = og_image.date_label(display_payload["answered_at"])
    checked_label = f"Answered {answered_on}" if answered_on else ""
    if watch_page:
        # A Watch's card tells what its page leads with, like a Topic card:
        # that it is watched and whether the answer moved -- not a score the
        # page no longer shows (Apple-Audit L13).
        watch_state = _watch_state_view(
            watch_page,
            _build_watch_history_view(history_points, width=PAGE_CHART_WIDTH),
            _build_watch_drift_view(
                history_points, display_version["id"] if display_version else "",
                query_first=bool(data.get("watch_query_only")),
            ),
            awaiting=bool(data.get("awaiting_first_watch_run")) and not (display_version or {}).get("snapshot"),
            version_kind=(display_version or {}).get("kind", "fallback"),
            selected_run_id=(display_version or {}).get("id", ""),
            fallback_notice=(display_version or {}).get("fallback_notice", ""),
        )
        png = og_image.watch_card_png(
            share_id,
            question=str(data.get("question") or ""),
            state_line=watch_state.get("headline") or "",
            model_count=model_count,
        )
    else:
        png = og_image.share_card_png(
            share_id,
            question=str(data.get("question") or ""),
            score=score if isinstance(score, (int, float)) else None,
            model_count=model_count,
            contradiction_count=contradiction_count,
            checked_label=checked_label,
        )
    if png is None:
        raise HTTPException(status_code=404, detail="Not found")
    return Response(
        content=png,
        media_type="image/png",
        headers={
            # The card shows the question: it is revoked with its page.
            "Cache-Control": SHARE_CACHE_CONTROL,
            "X-Robots-Tag": "noindex",
        },
    )


@router.get("/s/{slug_id}", response_class=HTMLResponse)
@limiter.limit("30/minute")
def share_page(request: Request, slug_id: str):
    slug, share_id = snapshots.split_slug_id(slug_id)
    if not snapshots.is_valid_share_id(share_id):
        return _unavailable_response(
            request, 404, "Page not found",
            "This shared consensus does not exist.",
        )

    try:
        data = snapshots.get_share_cached(share_id)
    except Exception as exc:
        logging.error("share_page lookup failed category=%s", safe_exception(exc))
        raise HTTPException(status_code=500, detail="Error loading shared page")

    if data is None:
        return _unavailable_response(
            request, 404, "Page not found",
            "This shared consensus does not exist.",
        )
    if data.get("status") != "active":
        # Widerrufen oder gesperrt: dauerhaft weg (410 Gone).
        return _unavailable_response(
            request, 410, "This page is gone",
            "This shared consensus has been removed by its creator or by consens.io.",
        )

    is_private = str(data.get("visibility") or "public") == "private"
    if is_private:
        token = extract_id_token(request, {})
        try:
            viewer_uid = verify_user_token(token) if token else ""
        except Exception:
            viewer_uid = ""
        if not viewer_uid:
            # Usually the owner from a mail link, in a browser without the
            # session cookie: the app signs in (or finds the session it
            # already has) and comes straight back (static/firebase.js).
            return _unavailable_response(
                request, 403, "Private watch page",
                "This page is private. Log in with the account that created it to view it.",
                # The canonical path, not the requested one: it always
                # matches what the app accepts as a return target.
                sign_in_href="/app?next=" + quote(snapshots.share_path("", share_id), safe="/"),
            )
        if viewer_uid != data.get("owner_uid"):
            return _unavailable_response(
                request, 403, "Private watch page",
                "This page is private and belongs to another account. Log in with the account that created it to view it.",
            )

    canonical_slug = data.get("slug") or ""
    if not is_private and slug != canonical_slug:
        return RedirectResponse(
            url=snapshots.share_path(canonical_slug, share_id), status_code=301
        )

    page_path = snapshots.share_path("" if is_private else canonical_slug, share_id)
    page_url = SITE_URL + page_path

    # Shared Pages stay immutable. Only a page with Watch metadata overlays an
    # immutable version snapshot at render time; the underlying Share document
    # remains the original baseline and keeps its existing API semantics.
    try:
        history_points = snapshots.list_watch_history(share_id)
    except Exception as exc:
        logging.error(
            "list_watch_history failed category=%s", safe_exception(exc)
        )
        history_points = []
    try:
        current_watch_meta = watch_service.get_public_watch_meta(share_id)
    except Exception as exc:
        logging.error(
            "get_public_watch_meta failed category=%s", safe_exception(exc)
        )
        current_watch_meta = None
    watch_page = _build_watch_page_meta(current_watch_meta, history_points)

    requested_version = str(request.query_params.get("version") or "").strip()
    latest_run_id = _standing_run_id(current_watch_meta, data)
    if watch_page and requested_version and requested_version != "original":
        if not re.fullmatch(r"[A-Za-z0-9]{8,64}", requested_version):
            return _unavailable_response(
                request, 404, "Version not found",
                "This Watch version does not exist.",
            )
    try:
        display_version = _resolve_display_version(
            data, watch_page, requested_version, latest_run_id, share_id,
        )
    except Exception as exc:
        logging.error(
            "resolve Watch display version failed category=%s", safe_exception(exc)
        )
        display_version = None
    if display_version is None:
        if requested_version:
            return _unavailable_response(
                request, 404, "Version not found",
                "This Watch version does not exist.",
            )
        display_version = {
            "id": "original", "kind": "fallback", "data": data, "snapshot": None,
            "fallback_notice": (
                "The latest Watch version could not be loaded. "
                "Showing the original consensus and all of its original metadata instead."
            ),
        }

    selected_run_id = display_version["id"]
    selected_version = display_version["snapshot"]
    display_data = display_version["data"]
    payload = snapshots.public_share_payload(display_data)
    watch_awaiting_first_run = bool(
        watch_page and data.get("awaiting_first_watch_run") and not selected_version
    )

    # Indexierung: nur wenn der Admin "indexed" gesetzt hat (nie automatisch).
    is_indexed = bool(data.get("indexed")) and not is_private
    robots_meta = "index, follow" if is_indexed else "noindex, nofollow" if is_private else "noindex, follow"

    # Canonical-Dedup über question_hash: Nicht indexierte Duplikate zeigen
    # auf den ältesten aktiven UND indexierten Share derselben Frage. Ein
    # Canonical zeigt nie auf eine noindex-Seite; ohne Ziel: selbst-kanonisch.
    canonical_url = page_url
    if not is_indexed and data.get("question_hash"):
        try:
            canonical_target = snapshots.find_canonical_share(data["question_hash"])
        except Exception as exc:
            logging.error(
                "find_canonical_share failed category=%s", safe_exception(exc)
            )
            canonical_target = None
        if canonical_target and canonical_target["share_id"] != share_id:
            canonical_url = SITE_URL + snapshots.share_path(
                canonical_target["slug"], canonical_target["share_id"]
            )

    sources_view = []
    # A link back to consens.io (often this very page) is no source: it
    # leaves the list, the direct links and the inline names, and its [S#]
    # markers drop like those of an expired redirect (Apple-Audit L4).
    own_sources = [
        {"id": source.get("id")} for source in payload["sources"]
        if source_links.is_own_page(source.get("url")) and source.get("id")
    ]
    for source in payload["sources"]:
        if source_links.is_own_page(source.get("url")):
            continue
        match = re.match(r"^S(\d+)$", str(source.get("id") or ""))
        url = source.get("url") or ""
        # Grounding-Redirects zeigen sonst alle denselben Google-Host statt der
        # Seite, die die Aussage wirklich stützt.
        domain = source_host(url, source.get("title"))
        # Nichtssagende Titel (leer, nur eine Zahl oder die nackte URL)
        # fallen auf die Domain zurück, damit Quellen zuordenbar bleiben.
        title = str(source.get("title") or "").strip()
        if not title or title == url or re.fullmatch(r"\d+", title):
            title = domain or url
        site_label = source_site_name(url, source.get("title"))
        sources_view.append({
            "num": match.group(1) if match else "",
            "id": source.get("id") or "",
            "title": title,
            "url": url,
            "domain": domain,
            "site": site_label,
            # False = die URL ist ein Redirect, die Domain kam aus dem Titel.
            "is_direct": bool(domain) and domain == source_host(url),
        })

    # Watch-Seiten führen direkt zu den Quellen: Direktlinks über der Antwort
    # und die Namen der Quellen im Text als Links (source_links.py).
    watch_key_links = []
    site_links = None
    if watch_page:
        watch_key_links = source_links.key_links(sources_view, payload["consensus_md"])
        site_links = source_links.site_mentions(sources_view, payload["consensus_md"])
    consensus_html = render_public_markdown(
        payload["consensus_md"], source_links.without_own_pages(payload["sources"]),
        # Abgelaufene Weiterleitungen sind entfernt; ihre [S3]-Verweise fallen weg.
        excluded_sources=payload["expired_sources"] + own_sources, site_links=site_links,
    )

    # Differences: strukturierte Karten, sonst Freitext-Fallback (markdown-
    # gerendert). Beides read-only aus dem Snapshot – keine LLM-Calls.
    differences_data = payload["differences_data"] if isinstance(payload["differences_data"], dict) else {}
    differences = differences_data.get("differences") or []
    has_structured_differences = isinstance(differences_data.get("differences"), list)
    best_model_display = str(differences_data.get("best_model") or "").strip()
    differences_fallback_html = ""
    if payload["differences_text"]:
        # Die technische "BestModel: X"-Zeile auch aus Legacy-/Uebergangs-
        # Snapshots ziehen, aber den restlichen Freitext nur dann anzeigen,
        # wenn keine autoritative strukturierte Differences-Liste existiert.
        # Eine vorhandene leere Liste ist ein echter "keine Unterschiede"-
        # Befund und darf nicht auf den alten Credibility-Text zurueckfallen.
        fallback_text = str(payload["differences_text"])
        match = _BEST_MODEL_RE.search(fallback_text)
        if match:
            if not best_model_display:
                best_model_display = match.group(1).strip()
            fallback_text = _BEST_MODEL_RE.sub("", fallback_text).strip()
        if not has_structured_differences:
            differences_fallback_html = render_public_markdown(
                fallback_text, payload["sources"]
            )
    model_count = (
        len(differences_data.get("models_compared") or [])
        or len(payload["included_models"])
    )
    contradiction_count = sum(1 for d in differences if d.get("type") == "contradiction")

    # "Verwandte Fragen": nur indexierte, aktive Shares (read-only, gecacht).
    related_shares = []
    if not is_private:
        try:
            related_shares = snapshots.list_related_shares(share_id, payload["question"])
        except Exception as exc:
            logging.error(
                "list_related_shares failed category=%s", safe_exception(exc)
            )

    watch_history = _build_watch_history_view(history_points, width=PAGE_CHART_WIDTH)
    watch_drift = _build_watch_drift_view(
        history_points,
        selected_run_id,
        query_first=bool(data.get("watch_query_only")),
    ) if watch_page else None

    # A Watch page has its own, much quieter template: the state line, the
    # answer, the changes over time. The one-off share page keeps its
    # scoreboard, model chips and differences toggle.
    watch_state = _watch_state_view(
        watch_page, watch_history, watch_drift,
        awaiting=watch_awaiting_first_run,
        version_kind=(
            "original" if requested_version == "original"
            else "historical" if requested_version else display_version["kind"]
        ),
        selected_run_id=selected_run_id,
        requested=bool(requested_version),
        fallback_notice=display_version["fallback_notice"],
    ) if watch_page else None

    date_iso = payload["answered_at"] or payload["created_at"]
    published_iso = date_iso
    # Auch strukturierte Zeitangaben bleiben an die autoritative Anzeigeversion
    # gebunden; kompakte History-Metadaten dürfen hier nicht einsickern.
    modified_iso = date_iso

    # Die laufende Watch-Seite ist EIN Dokument, das seit ihrer Anlage gepflegt
    # wird: der letzte Check ist ihre Aenderung, nicht ihre Geburt. Ohne diese
    # Trennung sieht sie nach jedem Lauf wie ein brandneuer Artikel aus und
    # verliert genau das, was sie auszeichnet. Historische Versionen bleiben
    # bewusst vollstaendig bei ihrem eigenen Datum.
    tracking_start = history_points[0]["ts"] if history_points else None
    if watch_page and not requested_version:
        origin = snapshots.public_share_payload(data)
        published_iso = origin["answered_at"] or origin["created_at"] or date_iso

    # Verdict-Scoreboard: der datendichte Einstieg über der Konsens-Antwort.
    agreement_data = differences_data.get("agreement")
    agreement_data = agreement_data if isinstance(agreement_data, dict) else {}
    base_score = agreement_data.get("score")
    if not isinstance(base_score, (int, float)):
        base_score = display_data.get("agreement_score")
    latest_score = base_score if isinstance(base_score, (int, float)) else None
    if agreement_data.get("coverage_status") == "insufficient":
        latest_score = None
    scoreboard = {
        "score": int(latest_score) if isinstance(latest_score, (int, float)) else None,
        "level": str(agreement_data.get("level") or ""),
        "coverage_status": agreement_data.get("coverage_status"),
        "coverage_percent": agreement_data.get("coverage_percent"),
        "scored_claims": agreement_data.get("scored_claims"),
        "total_claims": agreement_data.get("total_claims"),
        "evidence_incomplete": agreement_data.get("evidence_incomplete", False),
        "model_count": model_count,
        "contradiction_count": contradiction_count,
        "source_count": len(sources_view),
        # Nur auf der laufenden Seite: eine historische Version zeigt den Stand
        # ihres eigenen Checks, nicht die Bilanz aller späteren.
        "checks": len(history_points) if watch_page and not requested_version else 0,
        "tracked_since": (
            tracking_start.strftime("%d %b %Y")
            if watch_page and not requested_version and isinstance(tracking_start, datetime)
            else ""
        ),
        "last_checked": date_iso[:10] if date_iso else "",
        "spark": None,
    }

    # Meta-Description datengeführt statt AI-Textanfang: liest sich im SERP
    # wie ein Datenprodukt, der Konsens-Auszug folgt dahinter.
    # A Watch page leads with its state ("Paused · last checked Oct 1"), not
    # a score or a count of contradictions it no longer shows (Apple-Audit
    # L2/L13, Zweitprüfung 16) -- the search line says what the page says.
    description_bits = []
    if watch_state and watch_state.get("headline") and not watch_awaiting_first_run:
        description_bits.append(watch_state["headline"])
    if model_count:
        description_bits.append(f"{model_count} AI models answered independently")
    if scoreboard["score"] is not None and not watch_page:
        description_bits.append(f"agreement {scoreboard['score']}/100")
    if contradiction_count and not watch_page:
        description_bits.append(
            f"{contradiction_count} contradiction{'s' if contradiction_count != 1 else ''}"
        )
    if scoreboard["tracked_since"]:
        # Der eigentliche Unterschied zu einer einmaligen Antwort: die Seite
        # wird seit Monaten nachgeprüft. Das gehört in die Suchergebnis-Zeile.
        description_bits.append(
            f"{scoreboard['checks']} checks since {scoreboard['tracked_since']}"
            if scoreboard["checks"] > 1
            else f"tracked since {scoreboard['tracked_since']}"
        )
    if description_bits:
        prefix = " · ".join(description_bits) + ". "
        excerpt = markdown_to_plaintext(
            payload["consensus_md"], limit=max(40, 160 - len(prefix)), sources=payload["sources"]
        )
        meta_description = prefix + excerpt
    else:
        meta_description = (
            f"A Watch on: {payload['question']}"[:160]
            if watch_awaiting_first_run
            else markdown_to_plaintext(payload["consensus_md"], limit=160, sources=payload["sources"])
        )

    # Generierte OG-Karte mit der Frage, sonst die Markenkarte der Landing.
    og_is_card = og_image.is_available() and not is_private
    og_image_url = page_url + "/og.png" if og_is_card else og_image.brand_card_url()

    jsonld = {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": payload["question"][:110],
        "description": meta_description,
        "datePublished": published_iso or date_iso,
        "dateModified": modified_iso,
        "mainEntityOfPage": {"@type": "WebPage", "@id": page_url},
        "author": seo_entity.ORG_REF,
        "publisher": seo_entity.ORG_REF,
        "isPartOf": seo_entity.SITE_REF,
        # Nur Quellen, deren URL wirklich auf die zitierte Seite zeigt. Ein
        # signierter Grounding-Redirect ist als Zitat wertlos und verdraengt
        # sonst die echten Belege aus den ersten zehn.
        "citation": [
            source["url"] for source in sources_view if source["url"] and source["is_direct"]
        ][:10],
        "isAccessibleForFree": True,
    }
    if og_is_card:
        jsonld["image"] = og_image_url
    # "</" escapen, damit Snapshot-Inhalte das <script>-Element nie schließen können.
    jsonld_html = seo_entity.dumps(seo_entity.page_graph(jsonld))

    response = templates.TemplateResponse(request=request, name="watch_share.html" if watch_page else "share.html", context={
        "watch_state": watch_state,
        "share_id": share_id,
        "is_private": is_private,
        "question": payload["question"],
        "consensus_html": consensus_html,
        # Old judge texts say "Model C"; the page names the families (L15).
        "differences": check_page.named_differences(differences),
        "differences_data": differences_data,
        "differences_fallback_html": differences_fallback_html,
        "best_model_display": best_model_display,
        "has_differences_view": bool(differences or differences_fallback_html or differences_data),
        "model_count": model_count,
        "contradiction_count": contradiction_count,
        "scoreboard": scoreboard,
        "can_follow": bool(
            not is_private and watch_page and watch_page["is_active"]
            and not watch_awaiting_first_run
        ),
        "sources": sources_view,
        "watch_key_links": watch_key_links,
        "related_shares": related_shares,
        "watch_history": watch_history,
        "watch_page": watch_page,
        "watch_awaiting_first_run": watch_awaiting_first_run,
        "watch_selected_version": {
            "id": selected_run_id,
            "kind": display_version["kind"],
            "is_original": display_version["kind"] in {"original", "fallback"},
            "is_current": display_version["kind"] == "current",
            "is_historical": bool(requested_version),
            "fallback_notice": display_version["fallback_notice"],
            "current_url": page_path,
            "original_url": page_path + "?version=original",
        } if watch_page else None,
        "included_models": payload["included_models"],
        "consulted_models": snapshots.consulted_models_view(payload["included_models"]),
        "consensus_model": payload["consensus_model"],
        "consensus_model_view": snapshots.consensus_model_view(payload["consensus_model"]),
        "date_display": date_iso[:10] if date_iso else "",
        "canonical_url": canonical_url,
        "page_url": page_url,
        "robots_meta": robots_meta,
        "meta_description": meta_description,
        "og_image": og_image_url,
        "og_is_card": og_is_card,
        "jsonld": jsonld_html,
        # Zitation immer mit der eigenen URL der Seite (nicht dem Dedup-Canonical).
        "citation_text": snapshots.build_citation(
            payload,
            page_url + (f"?version={selected_run_id}" if requested_version else ""),
        ),
    })
    response.headers["X-Robots-Tag"] = robots_meta
    if is_private:
        response.headers["Cache-Control"] = "private, no-store"
    else:
        # A historical Watch version never changes, but its publication can be
        # revoked, so it gets the same short lifetime as the current page.
        response.headers["Cache-Control"] = SHARE_CACHE_CONTROL
    return response

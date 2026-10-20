"""Public and admin routes for the independent curated Topics area."""

import asyncio
import functools
import html
import json
import logging
import re
from datetime import datetime
from typing import Optional
from urllib.parse import quote, urlsplit

from fastapi import APIRouter, BackgroundTasks, Body, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from app.core.assets import register_asset_globals
from app.core import not_found
from app.core import seo_entity
from app.core.site import SITE_URL
from app.core.observability import safe_exception
from app.core.rate_limit import limiter
from app.core.security import TierStatusUnavailable, extract_id_token, is_user_admin, verify_user_token
from app.services import (
    check_page, drift_signal, favicons, mailer, og_image, source_links,
    topic_figures, topic_images, topic_runner, topics,
)
from app.services.history_view import PAGE_CHART_WIDTH, build_history_view, day_label
from app.services.public_markdown import (
    lead_sentences,
    render_public_markdown,
    strip_chat_framing,
)


router = APIRouter()
_FAVICON_CONCURRENCY: Optional[asyncio.Semaphore] = None
_FAVICON_CONCURRENCY_LOOP = None
_FAVICON_ACQUIRE_TIMEOUT_SECONDS = 1.0
# A public Topic page reads a bounded window of its record: the newest runs
# for the timeline, and for an older version the runs ending at it.
TOPIC_PAGE_RUNS = 100
HUB_DESCRIPTION = (
    "Questions about AI that several AI models answer again every week: the "
    "current answer, direct links to the sources, and every time it changed."
)
templates = Jinja2Templates(directory="templates")
register_asset_globals(templates)


def _favicon_concurrency() -> asyncio.Semaphore:
    """Return a limiter bound to the currently serving event loop."""
    global _FAVICON_CONCURRENCY, _FAVICON_CONCURRENCY_LOOP
    loop = asyncio.get_running_loop()
    if _FAVICON_CONCURRENCY is None or _FAVICON_CONCURRENCY_LOOP is not loop:
        _FAVICON_CONCURRENCY = asyncio.Semaphore(8)
        _FAVICON_CONCURRENCY_LOOP = loop
    return _FAVICON_CONCURRENCY

_STATUS_BY_CODE = {
    "not_found": 404,
    "bad_request": 400,
    "conflict": 409,
    "invalid_email": 400,
    "invalid_token": 400,
    "expired_token": 410,
    "limit_reached": 429,
}


def _direct_sources(items) -> list[dict]:
    """The sources behind a change, without Google redirects: those expire
    within weeks and never name the page they stand for."""
    return [
        item for item in topics.normalize_evidence_sources(items)
        if not topics.classify_evidence(item["url"])["is_indirect"]
    ]


def _history_points(runs_raw) -> list[dict]:
    """Topic runs as points for the parts Topic and Watch pages share
    (check_page, history_view). Movement follows the Topic's own rule -- the
    Judge grade and its cause, never the score (drift_signal.topic_point)."""
    points = []
    for run in runs_raw:
        observed_at = run.get("observed_at")
        if not isinstance(observed_at, datetime):
            continue
        score = run.get("agreement_score")
        points.append({
            **drift_signal.topic_point(run),
            "ts": observed_at,
            "agreement_score": (
                int(score) if isinstance(score, (int, float)) and not isinstance(score, bool)
                else None
            ),
            "change_summary": str(run.get("change_summary") or ""),
            "evidence_sources": _direct_sources(run.get("evidence_sources")),
            "run_id": run["id"],
            "has_snapshot": True,
        })
    return points


def _sources_view(evidence, preferred_domains):
    """The run's evidence as the shared source list, direct sources first.

    Returns ``(sources, entries, hidden)``: the stored sources and their list
    entries in display order, and the Google redirects, which are left out of
    the list, the direct links and the inline names (their [S#] markers drop).
    """
    ranked, hidden = [], []
    for position, item in enumerate(evidence or []):
        if not isinstance(item, dict):
            continue
        classification = topics.classify_evidence(
            item.get("url"), item.get("type"), preferred_domains,
            title=str(item.get("title") or ""),
            publisher=str(item.get("publisher") or ""),
        )
        if classification["is_indirect"]:
            hidden.append(item)
            continue
        source = {**item, "url": classification["url"]}
        entry = source_links.source_entries([source])[0]
        match = re.match(r"^S(\d+)$", str(item.get("id") or ""))
        entry.update({"id": str(item.get("id") or ""), "num": match.group(1) if match else ""})
        rank = (classification["rank"], not classification["is_preferred"], position)
        ranked.append((rank, source, entry))
    ranked.sort(key=lambda row: row[0])
    return [row[1] for row in ranked], [row[2] for row in ranked], hidden


def _consulted_models(labels) -> list[dict]:
    """"OpenAI: gpt-6-luna" as the label/model pair the shared part prints."""
    models = []
    for label in labels or []:
        provider, _, model = str(label or "").partition(":")
        models.append({"label": provider.strip(), "model": model.strip()})
    return models


def _raise_topic(exc: topics.TopicError):
    raise HTTPException(
        status_code=_STATUS_BY_CODE.get(exc.code, 400), detail=exc.message
    )


def _require_admin(request: Request, data: Optional[dict] = None) -> str:
    token = extract_id_token(request, data or {})
    if not token:
        raise HTTPException(status_code=401, detail="Authentication required")
    try:
        uid = verify_user_token(token, check_revoked=True)
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Authentication failed") from exc
    try:
        is_admin = is_user_admin(uid)
    except TierStatusUnavailable:
        raise HTTPException(
            status_code=503,
            detail="Account role is temporarily unavailable. Please retry.",
        ) from None
    if not is_admin:
        raise HTTPException(status_code=403, detail="Admin privileges required")
    return uid


def _date_label(value: str) -> str:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).strftime("%b %d, %Y")
    except (TypeError, ValueError):
        return str(value or "")[:10]


def _admin_topic_view(topic: dict) -> dict:
    result = dict(topic)
    for key in (
        "created_at", "updated_at", "latest_run_at", "next_run_at",
        "claimed_until",
    ):
        value = result.get(key)
        if isinstance(value, datetime):
            result[key] = value.isoformat()
    return result


def _message_page(
    heading: str, message: str, status_code: int, *, href: str = "/topics",
    action: str = "", button: str = "",
) -> HTMLResponse:
    # With ``action`` the page is a confirmation step: its button posts there
    # and is the only thing on the page that changes anything.
    form = (
        f"<form method='post' action='{html.escape(action)}'>"
        "<button type='submit' style='font:inherit;padding:10px 18px;cursor:pointer'>"
        f"{html.escape(button)}</button></form>"
        if action else ""
    )
    content = (
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<meta name='robots' content='noindex'><title>Topics | consens.io</title>"
        "<style>body{font-family:Inter,system-ui,sans-serif;max-width:680px;margin:12vh auto;"
        "padding:24px;color:#172033}a{color:#335cff}</style></head><body>"
        f"<p style='color:#335cff;font-weight:700'>consens.io Topics</p>"
        f"<h1>{html.escape(heading)}</h1><p>{html.escape(message)}</p>{form}"
        f"<p><a href='{html.escape(href)}'>Open Topics</a></p></body></html>"
    )
    return HTMLResponse(
        content,
        status_code=status_code,
        headers={"X-Robots-Tag": "noindex, noarchive"},
    )


@router.get("/topics", response_class=HTMLResponse)
async def topics_hub(request: Request):
    try:
        entries = await asyncio.to_thread(topics.list_public_topics)
    except Exception as exc:
        logging.error("topics_hub failed category=%s", safe_exception(exc))
        entries = []
    for entry in entries:
        # A card says what a reader of the page would see first: the picture,
        # the opening of the answer, and whether the latest check moved it.
        entry["image"] = topic_images.visual_view(
            entry["id"], {"image": entry["image_state"], "symbol": entry["symbol"]}
        )
        try:
            day = day_label(datetime.fromisoformat(entry["accepted_run_at"]))
        except (TypeError, ValueError):
            day = ""
        if entry["standing_moved"]:
            entry["state_line"] = f"Changed {day}" if day else "Changed in the latest check"
        else:
            entry["state_line"] = f"Checked {day}" if day else "No change in the latest check"
        # One short whole sentence reads better on a card than three cut ones.
        entry["lead"] = lead_sentences(entry["lead"], limit=150, min_sentence=30) if entry["lead"] else ""
    jsonld = {
        "@context": "https://schema.org",
        "@type": "CollectionPage",
        "@id": SITE_URL + "/topics",
        "url": SITE_URL + "/topics",
        "name": "AI Consensus Topics",
        "description": HUB_DESCRIPTION,
        "mainEntity": {
            "@type": "ItemList",
            "numberOfItems": len(entries),
            "itemListElement": [{
                "@type": "ListItem",
                "position": index,
                "url": f"{SITE_URL}/topics/{entry['slug']}",
                "name": entry["title"],
            } for index, entry in enumerate(entries, start=1)],
        },
    }
    response = templates.TemplateResponse(request=request, name="topics.html", context={
        "entries": entries,
        "description": HUB_DESCRIPTION,
        "jsonld": seo_entity.dumps(seo_entity.page_graph(jsonld)),
    })
    response.headers["Cache-Control"] = "public, max-age=60, s-maxage=300"
    return response


@router.get("/sitemap-topics.xml")
async def sitemap_topics():
    try:
        urls = await asyncio.to_thread(topics.list_indexed_topic_urls)
    except Exception as exc:
        logging.error("sitemap_topics failed category=%s", safe_exception(exc))
        raise HTTPException(status_code=500, detail="Error building topic sitemap")
    items = []
    for item in urls:
        lastmod = (
            f"\n    <lastmod>{html.escape(item['lastmod'])}</lastmod>"
            if item.get("lastmod") else ""
        )
        items.append(
            "  <url>\n"
            f"    <loc>{SITE_URL}{html.escape(item['path'])}</loc>{lastmod}\n"
            "    <changefreq>weekly</changefreq>\n"
            "    <priority>0.8</priority>\n"
            "  </url>"
        )
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "\n".join(items)
        + "\n</urlset>\n"
    )
    return Response(content=xml, media_type="application/xml")


def _topic_not_found(request: Request):
    # A visitor following an old link sees the site's 404 page, a script
    # still gets the JSON error it always got.
    if not_found.wants_html_page(request):
        return not_found.not_found_page(request)
    raise HTTPException(status_code=404, detail="Topic not found")


@router.get("/topics/{slug}", response_class=HTMLResponse)
async def topic_page(
    request: Request, slug: str, version: str = Query(default="", max_length=40)
):
    try:
        topic, retired_slug = await asyncio.to_thread(
            topics.resolve_topic_by_slug, slug
        )
    except topics.TopicError:
        return _topic_not_found(request)
    except Exception as exc:
        logging.error(
            "topic_page lookup failed category=%s", safe_exception(exc)
        )
        raise HTTPException(status_code=500, detail="Error loading topic")
    if (
        not topic
        or topic.get("status") not in {"active", "paused"}
        or not topic.get("latest_run_id")
    ):
        return _topic_not_found(request)
    if retired_slug:
        # The topic was renamed. Everything the old URL earned moves to the new
        # one instead of dying in a 404.
        target = "/topics/" + quote(str(topic["slug"]))
        if version:
            target += "?version=" + quote(version)
        redirect = RedirectResponse(url=target, status_code=301)
        redirect.headers["Cache-Control"] = "public, max-age=3600"
        return redirect

    # The history is the newest page of the record; it is navigation, not
    # the lookup for an explicit version link.
    recent_raw = await asyncio.to_thread(
        topics.list_runs, topic["id"], max_items=TOPIC_PAGE_RUNS
    )
    # Without an explicit version the page shows the answer that stands, not
    # the newest run: a run whose search missed the evidence does not replace
    # it (docs/watch-evidence-model.md).
    standing_id = str(topic.get("accepted_run_id") or topic["latest_run_id"])
    wanted = version or standing_id
    selected_raw = next((run for run in recent_raw if run["id"] == wanted), None)
    if selected_raw is None and re.fullmatch(r"[A-Za-z0-9]{1,40}", wanted):
        # An older, still stored version is loaded directly under the topic
        # that was already resolved above, so a link never dies of old age.
        selected_raw = await asyncio.to_thread(topics.get_run, topic["id"], wanted)
    if not selected_raw:
        raise HTTPException(status_code=404, detail="Topic version not found")
    current = selected_raw["id"] == standing_id
    selected = topics.run_public_view(selected_raw)

    # The page is built from the parts it shares with Watch pages
    # (partials/check_page.html): state line, direct links, answer, history.
    points = _history_points(recent_raw)
    if not any(point["run_id"] == selected_raw["id"] for point in points):
        points = sorted(
            points + _history_points([selected_raw]), key=lambda point: point["ts"]
        )
    history = build_history_view(points, width=PAGE_CHART_WIDTH)
    public_topic = topics.topic_public_view(topic)
    next_run = topic.get("next_run_at")
    page = {
        "is_active": public_topic["status"] == "active",
        "next_run": {
            "day": day_label(next_run) if isinstance(next_run, datetime) and current else ""
        },
        "status_label": "Paused" if public_topic["status"] == "paused" else "Active",
        "resolution": None,
    }
    page_state = check_page.state_view(
        page, history, check_page.drift_view(points, selected_raw["id"]),
        awaiting=False,
        version_kind="historical" if version and not current else "current",
        selected_run_id=selected_raw["id"],
        requested=bool(version) and not current,
    )

    # The head keeps the state to one line; "What changed" leads to the
    # history entry that says it.
    interval = public_topic.get("update_interval") or ""
    state_detail = (
        "" if page_state.get("back")
        else "paused" if public_topic["status"] == "paused"
        else f"checked {interval}" if interval and interval != "manual" else ""
    )
    shown_point = next(
        (point for point in (history or {}).get("points") or [] if point["run_id"] == selected_raw["id"]),
        None,
    )
    state_more_href = (
        f"#watch-run-{shown_point['anchor_id']}"
        if page_state.get("tone") == "moved" and shown_point else ""
    )

    preferred_domains = (topic.get("source_rules") or {}).get("preferred_domains") or []
    answer_md = strip_chat_framing(selected["consensus_md"])
    sources, source_list, hidden = _sources_view(selected["evidence"], preferred_domains)
    # Figures drawn from this answer sit under the heading they belong to.
    figure_md, figures = topic_figures.place(answer_md, selected["figures"])
    answered = selected_raw.get("observed_at")
    answer_html = topic_figures.fill(
        render_public_markdown(
            figure_md, sources,
            excluded_sources=list(selected_raw.get("excluded_evidence") or []) + hidden,
            site_links=source_links.site_mentions(source_list, answer_md),
        ),
        figures,
        answered_on=(
            f"{answered:%b} {answered.day}, {answered.year}" if isinstance(answered, datetime) else ""
        ),
    )
    differences_data = selected_raw.get("differences_data")
    differences_data = differences_data if isinstance(differences_data, dict) else {}
    differences = [
        item for item in differences_data.get("differences") or [] if isinstance(item, dict)
    ]

    canonical_url = f"{SITE_URL}/topics/{public_topic['slug']}"
    page_url = canonical_url + (f"?version={selected['id']}" if version else "")
    seo = public_topic.get("seo") or {}
    title = seo.get("title") or public_topic["title"]
    # The snippet answers the query: the opening of the answer, then what
    # separates this page from asking one model once. A hand-set description
    # only fills in for an answer without a usable opening.
    model_count = len(selected["models"]) or len(public_topic["models"])
    checks = max(int(public_topic.get("run_count") or 0), len(points))
    record = f" Checked by {model_count or 'several'} AI models"
    if len(points) > 1:
        # Count and date come from the same window, so the sentence holds
        # even when older checks lie beyond it.
        first = points[0]["ts"]
        record += f", {len(points)} times since {first:%b} {first.day}, {first.year}"
    record += "."
    lead = lead_sentences(answer_md, limit=max(80, 300 - len(record)))
    meta_description = (lead + record) if lead else (
        seo.get("description") or public_topic["lead_question"]
    )
    robots = "noindex, follow" if seo.get("noindex") or version else "index, follow"
    # Only when the window reaches back to the first check does its date say
    # when the page was first published.
    window_complete = bool(recent_raw) and len(recent_raw) >= checks
    jsonld = {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": title[:110],
        "description": meta_description[:300],
        "datePublished": (
            topics._public_datetime(recent_raw[0].get("observed_at")) if window_complete
            else public_topic.get("created_at") or selected["observed_at"]
        ),
        "dateModified": (
            topics._public_datetime(recent_raw[-1].get("observed_at")) if recent_raw
            else selected["observed_at"]
        ),
        "mainEntityOfPage": {"@type": "WebPage", "@id": canonical_url},
        "author": seo_entity.ORG_REF,
        "publisher": seo_entity.ORG_REF,
        "isPartOf": seo_entity.SITE_REF,
        "citation": list(dict.fromkeys(
            entry["url"] for entry in source_list if entry["is_direct"]
        ))[:30],
        "isAccessibleForFree": True,
    }
    if lead:
        jsonld["abstract"] = lead[:300]
    # The link preview shows the Topic's question, like a shared answer does.
    og_card = f"{canonical_url}/og.png" if og_image.is_available() else ""
    if og_card:
        jsonld["image"] = og_card
    response = templates.TemplateResponse(request=request, name="topic.html", context={
        "topic": public_topic,
        "topic_image": topic_images.visual_view(topic["id"], topic),
        "page_state": page_state,
        "state_detail": state_detail,
        "state_more_href": state_more_href,
        "key_links": source_links.key_links(source_list, answer_md),
        "answer_html": answer_html,
        "sources": source_list,
        "page_history": history,
        "selected_version": {
            "id": selected_raw["id"],
            "current_url": f"/topics/{public_topic['slug']}",
            "original_url": "",
            "is_original": True,
        },
        "model_count": model_count,
        "contradiction_count": sum(
            1 for item in differences if item.get("type") == "contradiction"
        ),
        "consulted_models": _consulted_models(selected["models"]),
        "differences": differences,
        "is_current": current,
        "canonical_url": canonical_url,
        "page_url": page_url,
        "page_title": title,
        "og_card_image": og_card,
        "og_card_alt": title,
        "meta_description": meta_description,
        "robots_meta": robots,
        "jsonld": seo_entity.dumps(seo_entity.page_graph(jsonld)),
    })
    response.headers["X-Robots-Tag"] = robots
    # A stored version never changes, but the Topic can be archived and then
    # has to disappear everywhere, so no version is cached long or immutable.
    response.headers["Cache-Control"] = (
        "public, max-age=60, s-maxage=300, stale-while-revalidate=300"
    )
    return response


@router.get("/topics/{slug}/og.png")
@limiter.limit("60/minute")
async def topic_og_card(request: Request, slug: str):
    """Open-Graph card of a public Topic: its title and how it is checked."""
    if not og_image.is_available():
        raise HTTPException(status_code=404, detail="Not found")
    try:
        topic, _retired = await asyncio.to_thread(topics.resolve_topic_by_slug, slug)
    except topics.TopicError:
        raise HTTPException(status_code=404, detail="Not found")
    except Exception as exc:
        logging.error("topic_og_card lookup failed category=%s", safe_exception(exc))
        raise HTTPException(status_code=500, detail="Error loading topic")
    if (
        not topic
        or topic.get("status") not in {"active", "paused"}
        or not topic.get("latest_run_id")
    ):
        raise HTTPException(status_code=404, detail="Not found")
    public_topic = topics.topic_public_view(topic)
    title = (public_topic.get("seo") or {}).get("title") or public_topic["title"]
    model_count = len(public_topic["models"])
    checked = og_image.date_label(public_topic.get("latest_run_at") or "")
    png = await asyncio.to_thread(
        functools.partial(
            og_image.card_png, f"topic:{public_topic['id']}", question=title,
            facts=[f"{model_count} AI models" if model_count else "Several AI models"],
            dateline=f"Checked {checked}" if checked else "",
        )
    )
    if png is None:
        raise HTTPException(status_code=404, detail="Not found")
    return Response(
        content=png,
        media_type="image/png",
        headers={
            # The card shows only the public title; an archived Topic's card
            # may outlive its page by an hour.
            "Cache-Control": "public, max-age=3600",
            "X-Robots-Tag": "noindex",
        },
    )


@router.get("/api/topics/{topic_id}/image/{token}")
@limiter.limit("60/minute")
def topic_image(request: Request, topic_id: str, token: str):
    """The Topic's picture, served by consens.io (no request to the source).

    Topics are public and the token changes with the picture, so it may be
    cached long.
    """
    try:
        found = topic_images.load_image(topic_id, token)
    except Exception as exc:
        logging.warning("topic_image failed category=%s", safe_exception(exc))
        raise HTTPException(status_code=503, detail="Image unavailable")
    if not found:
        raise HTTPException(status_code=404, detail="Not found")
    content, content_type = found
    return Response(
        content=content,
        media_type=content_type,
        headers={"Cache-Control": "public, max-age=2592000, immutable"},
    )


_GLOBE_SVG = (
    b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
    b'stroke="currentColor" stroke-width="1.6" stroke-linecap="round" '
    b'stroke-linejoin="round"><circle cx="12" cy="12" r="9"/>'
    b'<path d="M3 12h18M12 3c2.5 2.5 3.5 6 3.5 9s-1 6.5-3.5 9c-2.5-2.5-3.5-6-3.5-9'
    b'S9.5 5.5 12 3z"/></svg>'
)


@router.get("/api/topics/favicon")
@limiter.limit("30/minute")
async def topic_favicon(request: Request, d: str = Query(default="", max_length=253)):
    acquired = False
    overloaded = False
    concurrency = _favicon_concurrency()
    try:
        await asyncio.wait_for(
            concurrency.acquire(), timeout=_FAVICON_ACQUIRE_TIMEOUT_SECONDS
        )
        acquired = True
        data, content_type = await asyncio.get_running_loop().run_in_executor(
            favicons.EXECUTOR, favicons.get_favicon, d
        )
    except asyncio.TimeoutError:
        overloaded = True
        data, content_type = None, ""
    except Exception as exc:
        # Favicons are optional decoration. An unexpected decoder/client
        # failure must not turn an otherwise healthy Topic page into a 500.
        overloaded = True
        data, content_type = None, ""
        logging.warning(
            "Topic favicon lookup failed category=%s", safe_exception(exc)
        )
    finally:
        if acquired:
            concurrency.release()
    if not data:
        return Response(
            content=_GLOBE_SVG,
            media_type="image/svg+xml",
            # A capacity fallback is transient and must not be cached by a
            # browser/CDN for a day.  Genuine negative favicon lookups remain
            # safely cached to prevent retry amplification.
            headers={
                "Cache-Control": (
                    "no-store" if overloaded else "public, max-age=86400"
                )
            },
        )
    return Response(
        content=data,
        media_type=content_type or "image/png",
        headers={"Cache-Control": "public, max-age=604800, immutable"},
    )


@router.post("/api/topics/{slug}/follow")
@limiter.limit("3/minute")
async def follow_topic(request: Request, slug: str, data: dict = Body(default={})):
    try:
        topic, _retired = await asyncio.to_thread(topics.resolve_topic_by_slug, slug)
        if not topic:
            raise topics.TopicError("not_found", "This topic cannot be followed.")
        pending = await asyncio.to_thread(
            topics.request_follow, topic["id"], data.get("email")
        )
    except topics.TopicError as exc:
        _raise_topic(exc)
    except Exception as exc:
        logging.error("follow_topic failed category=%s", safe_exception(exc))
        raise HTTPException(status_code=500, detail="Error processing follow request")
    if pending["token"]:
        if not mailer.is_configured():
            raise HTTPException(status_code=503, detail="E-mail delivery is not configured.")
        topic_url = f"{SITE_URL}/topics/{pending['slug']}"
        confirm_url = SITE_URL + "/topic-follow/confirm?token=" + pending["token"]
        sent = await mailer.send_message(mailer.build_topic_follow_confirm_message(
            recipient=pending["email"],
            title=pending["title"],
            confirm_url=confirm_url,
            topic_url=topic_url,
        ))
        if not sent:
            raise HTTPException(
                status_code=502,
                detail="Confirmation e-mail could not be sent. Please try again later.",
            )
    return {
        "status": "success",
        "message": "Check your inbox and confirm to start following.",
    }


def _follow_link_step(path: str, token: str, *, unsubscribe: bool, heading: str,
                      message: str, button: str, error_heading: str) -> HTMLResponse:
    """GET of a link from a follow mail: checks the token and asks for the
    click that acts. Mail scanners and link previews open every link in a
    message; only the POST changes anything (it is also the one-click
    unsubscribe a mail client sends for the List-Unsubscribe header)."""
    try:
        topics.parse_follow_token(token, unsubscribe=unsubscribe)
    except Exception as exc:
        error = getattr(exc, "message", "This link is invalid or expired.")
        code = _STATUS_BY_CODE.get(getattr(exc, "code", ""), 400)
        return _message_page(error_heading, error, code)
    return _message_page(heading, message, 200,
                         action=f"{path}?token={quote(token, safe='')}", button=button)


@router.get("/topic-follow/confirm", response_class=HTMLResponse)
@limiter.limit("20/minute")
def topic_follow_confirm_page(request: Request, token: str = ""):
    return _follow_link_step(
        "/topic-follow/confirm", token, unsubscribe=False,
        heading="Confirm your follow",
        message="Confirm to get an e-mail when the curated consensus on this topic changes materially.",
        button="Confirm and follow", error_heading="Unable to confirm",
    )


@router.post("/topic-follow/confirm", response_class=HTMLResponse)
@limiter.limit("20/minute")
async def topic_follow_confirm(request: Request, token: str = ""):
    try:
        result = await asyncio.to_thread(topics.confirm_follow, token)
        return _message_page(
            "You're following this topic",
            f"We will e-mail you when the curated consensus on “{result['title']}” changes materially.",
            200,
            href=f"/topics/{result['slug']}",
        )
    except Exception as exc:
        message = getattr(exc, "message", "This confirmation link is invalid or expired.")
        code = _STATUS_BY_CODE.get(getattr(exc, "code", ""), 400)
        return _message_page("Unable to confirm", message, code)


@router.get("/topic-follow/unsubscribe", response_class=HTMLResponse)
@limiter.limit("20/minute")
def topic_follow_unsubscribe_page(request: Request, token: str = ""):
    return _follow_link_step(
        "/topic-follow/unsubscribe", token, unsubscribe=True,
        heading="Unfollow this topic?",
        message="You will no longer receive curated consensus updates for this topic.",
        button="Unfollow", error_heading="Unable to unfollow",
    )


@router.post("/topic-follow/unsubscribe", response_class=HTMLResponse)
@limiter.limit("20/minute")
async def topic_follow_unsubscribe(request: Request, token: str = ""):
    try:
        await asyncio.to_thread(topics.unsubscribe_follow, token)
        return _message_page(
            "Topic unfollowed",
            "You will no longer receive curated consensus updates for this topic.",
            200,
        )
    except Exception as exc:
        message = getattr(exc, "message", "This unsubscribe link is invalid or expired.")
        code = _STATUS_BY_CODE.get(getattr(exc, "code", ""), 400)
        return _message_page("Unable to unfollow", message, code)


async def _deliver_topic_notifications(item_ids) -> None:
    try:
        await topic_runner.deliver_topic_notifications(item_ids)
    except Exception as exc:
        logging.error(
            "Topic follower notification failed category=%s", safe_exception(exc)
        )


@router.get("/api/admin/topics")
@limiter.limit("30/minute")
async def admin_list_topics(request: Request):
    await asyncio.to_thread(_require_admin, request)
    try:
        items = await asyncio.to_thread(topics.list_admin_topics)
        return {"status": "success", "topics": items}
    except Exception as exc:
        logging.error("admin_list_topics failed category=%s", safe_exception(exc))
        raise HTTPException(status_code=500, detail="Failed to load topics")


@router.post("/api/admin/topics")
@limiter.limit("20/minute")
async def admin_create_topic(request: Request, data: dict = Body(...)):
    actor_uid = await asyncio.to_thread(_require_admin, request, data)
    payload = {key: value for key, value in data.items() if key != "id_token"}
    try:
        topic = await asyncio.to_thread(
            topics.create_topic, payload, actor_uid=actor_uid
        )
        return {"status": "success", "topic": _admin_topic_view(topic)}
    except topics.TopicError as exc:
        _raise_topic(exc)
    except Exception as exc:
        logging.error("admin_create_topic failed category=%s", safe_exception(exc))
        raise HTTPException(status_code=500, detail="Failed to create topic")


@router.get("/api/admin/topics/{topic_id}")
@limiter.limit("30/minute")
async def admin_get_topic(request: Request, topic_id: str):
    await asyncio.to_thread(_require_admin, request)
    topic = await asyncio.to_thread(topics.get_topic, topic_id)
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")
    runs = await asyncio.to_thread(topics.list_runs, topic_id)
    return {
        "status": "success",
        "topic": _admin_topic_view(topic),
        "runs": [topics.run_public_view(run) for run in reversed(runs)],
        "follower_count": len(await asyncio.to_thread(topics.list_followers, topic_id)),
    }


@router.put("/api/admin/topics/{topic_id}")
@limiter.limit("20/minute")
async def admin_update_topic(
    request: Request, topic_id: str, data: dict = Body(...)
):
    actor_uid = await asyncio.to_thread(_require_admin, request, data)
    payload = {key: value for key, value in data.items() if key != "id_token"}
    try:
        topic = await asyncio.to_thread(
            topics.update_topic, topic_id, payload, actor_uid=actor_uid
        )
        return {"status": "success", "topic": _admin_topic_view(topic)}
    except topics.TopicError as exc:
        _raise_topic(exc)
    except Exception as exc:
        logging.error("admin_update_topic failed category=%s", safe_exception(exc))
        raise HTTPException(status_code=500, detail="Failed to update topic")


@router.post("/api/admin/topics/{topic_id}/runs")
@limiter.limit("10/minute")
async def admin_create_topic_run(
    request: Request,
    background_tasks: BackgroundTasks,
    topic_id: str,
    data: dict = Body(...),
):
    actor_uid = await asyncio.to_thread(_require_admin, request, data)
    payload = {key: value for key, value in data.items() if key != "id_token"}
    try:
        topic_before = await asyncio.to_thread(topics.get_topic, topic_id)
        if not topic_before:
            raise topics.TopicError("not_found", "Topic not found.")
        # Same bar as the Watch pages: only what moved on evidence reaches a
        # follower (docs/watch-evidence-model.md). Items commit with the run (R17).
        staged = await asyncio.to_thread(
            topic_runner.topic_notification_builder, topic_id,
        )
        if str(payload.get("consensus_md") or "").strip():
            # Explicit legacy/editorial import. Normal admin runs send an empty
            # body and execute the configured models plus source collection.
            run = await asyncio.to_thread(
                functools.partial(
                    topics.create_run, topic_id, payload, actor_uid=actor_uid,
                    notifications=staged,
                )
            )
        else:
            run = await asyncio.to_thread(
                functools.partial(
                    topic_runner.run_topic_now, topic_id, actor_uid=actor_uid,
                    notifications=staged,
                )
            )
        is_material = (run.get("outcome") or {}).get("signal") == drift_signal.SIGNAL_MOVED
        should_notify = is_material and mailer.is_configured()
        if staged.ids:
            background_tasks.add_task(_deliver_topic_notifications, list(staged.ids))
        return {
            "status": "success",
            "run": topics.run_public_view(run),
            "notifications_queued": should_notify,
            "notification_warning": (
                "Run saved, but SMTP is not configured; follower e-mails were not queued."
                if is_material and not should_notify
                else ""
            ),
        }
    except topics.TopicError as exc:
        _raise_topic(exc)
    except Exception as exc:
        logging.error(
            "admin_create_topic_run failed category=%s", safe_exception(exc)
        )
        raise HTTPException(status_code=500, detail="Topic run failed")

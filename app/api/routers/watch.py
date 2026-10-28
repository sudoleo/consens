import asyncio
import logging
from urllib.parse import quote

from fastapi import APIRouter, Body, HTTPException, Request
from fastapi.responses import HTMLResponse, Response

from app.core import config as cfg
from app.core.notice_page import WATCHES_LINK, notice_page
from app.core.i18n_middleware import request_language
from app.core.observability import safe_exception
from app.core.rate_limit import ApiUidRateLimitExceeded, api_uid_limiter, limiter
from app.core.entitlements import entitlements_for
from app.core.security import (
    extract_id_token, get_user_tier, verify_user_token,
    AuthenticationUnavailable, auth_unavailable_error,
)
from app.core.site import SITE_URL
from app.services import (
    mailer, share_snapshots, telegram_watch, watch_brief, watch_followers, watch_images,
    watch_scheduler, watch_service,
)


router = APIRouter()
_STATUS_BY_CODE = {
    "not_found": 404, "forbidden": 403, "pro_required": 403,
    "limit_reached": 429, "already_exists": 409, "already_watched": 409,
    "invalid_token": 400,
    "expired_token": 410, "invalid_email": 400, "not_watched": 404,
    "telegram_not_configured": 503, "telegram_not_linked": 409,
    "telegram_already_linked": 409, "telegram_delivery_failed": 502,
    "goal_reached": 409,
}


def _uid(request: Request, data: dict) -> str:
    token = extract_id_token(request, data)
    if not token:
        raise HTTPException(status_code=401, detail="Authentication required")
    try:
        return verify_user_token(token)
    except AuthenticationUnavailable:
        raise auth_unavailable_error() from None
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Authentication failed") from exc


def _raise(exc: watch_service.WatchError):
    """The JSON error carries the reason as ``code`` (and its details, e.g.
    the ``watch_id`` of ``already_watched``) next to the sentence: the app
    opens the watch instead of showing an error, and only ``limit_reached``
    offers more watches -- never a ``rate_limited`` (main.py)."""
    error = HTTPException(status_code=_STATUS_BY_CODE.get(exc.code, 400), detail=exc.message)
    error.error_fields = {"code": exc.code, **exc.details}
    raise error


@router.post("/api/watch")
@limiter.limit("5/minute")
def create_watch(request: Request, data: dict = Body(...)):
    uid = _uid(request, data)
    if "visibility" not in data:
        raise HTTPException(status_code=400, detail="Choose whether the watch page is private or public.")
    if data.get("telegram_enabled") is True and not telegram_watch.get_connection(uid).get("connected"):
        raise HTTPException(status_code=409, detail="Connect Telegram before enabling it for a watch.")
    try:
        watch = watch_service.create_watch(
            uid,
            interval=data.get("interval"),
            email_mode=data.get("email_mode", "changes_only"),
            email_enabled=data.get("email_enabled", True),
            telegram_enabled=data.get("telegram_enabled", False),
            condition=data.get("condition", ""),
            visibility=data.get("visibility", "public"),
            run_weekday=data.get("run_weekday", ""),
            run_time=data.get("run_time", ""),
            timezone_name=data.get("timezone", ""),
            tier=get_user_tier(uid),
            result_id=data.get("result_id"),
            share_id=data.get("share_id"),
            question=data.get("question"),
        )
    except watch_service.WatchError as exc:
        _raise(exc)
    except Exception as exc:
        logging.error("create_watch failed category=%s", safe_exception(exc))
        raise HTTPException(status_code=500, detail="Error creating watch")
    if not watch.get("query_first"):
        # Aus einer fertigen Antwort: deren Quellen können das Bild schon jetzt
        # liefern. Läuft im Hintergrund und kann die Antwort nie verzögern.
        try:
            watch_images.schedule_for_new_watch(watch["id"])
        except Exception as exc:
            logging.warning("watch image scheduling failed category=%s", safe_exception(exc))
    return {"status": "success", "watch": watch}


# Normal ist ein Aufruf pro angelegter Watch (watch.js cacht pro Frage).
GOAL_SUGGESTIONS_PER_HOUR = 20


@router.post("/api/watch/goal-suggestions")
@limiter.limit("6/minute")
def goal_suggestions(request: Request, data: dict = Body(...)):
    """Concrete goals for "What are you waiting for?" in the create flow."""
    uid = _uid(request, data)
    question = " ".join(str(data.get("question") or "").split())
    if len(question) < watch_service.WATCH_QUESTION_MIN_CHARS:
        raise HTTPException(status_code=400, detail="Enter a complete question first.")
    try:
        # Läuft auf dem Projekt-Key ohne Tokenbuchung; die Kontogrenze hält
        # die Kosten pro Konto fest, egal von wie vielen IPs es kommt.
        api_uid_limiter.check(
            uid, "watch:goal-suggestions", GOAL_SUGGESTIONS_PER_HOUR, window_seconds=3600
        )
    except ApiUidRateLimitExceeded:
        return {"status": "limited", "goals": []}
    try:
        goals = watch_scheduler.suggest_goals(question[:1_000], get_user_tier(uid))
    except Exception as exc:
        # Suggestions are a convenience: the field stays usable without them.
        logging.warning("goal_suggestions failed category=%s", safe_exception(exc))
        goals = []
    return {"status": "success", "goals": goals}


@router.get("/api/my/watches")
@limiter.limit("20/minute")
def my_watches(request: Request):
    uid = _uid(request, {})
    try:
        watches = watch_service.list_watches(uid, include_history=True)
        tier = get_user_tier(uid)
        active_count = sum(1 for watch in watches if watch.get("status") == "active")
        resolved_count = sum(
            1 for watch in watches if watch.get("status") == watch_service.WATCH_STATUS_RESOLVED
        )
        active_limit = cfg.get_watch_active_limit(tier)
        return {
            "status": "success",
            "watches": watches,
            "limits": {
                # "plan" traegt jetzt die volle Stufe (free/plus/pro). Aeltere
                # Clients vergleichen nur gegen "pro" und behandeln plus damit
                # wie free - richtig herum, aber siehe watch.js.
                "plan": entitlements_for(tier).tier,
                "active_count": active_count,
                "active_limit": active_limit,
                "remaining": max(0, active_limit - active_count),
                "paused_count": len(watches) - active_count - resolved_count,
                "resolved_count": resolved_count,
                "daily_available": cfg.is_watch_daily_allowed(tier),
            },
        }
    except Exception as exc:
        logging.error("my_watches failed category=%s", safe_exception(exc))
        raise HTTPException(status_code=500, detail="Error loading watches")


@router.patch("/api/watch/{watch_id}")
@limiter.limit("10/minute")
def patch_watch(request: Request, watch_id: str, data: dict = Body(...)):
    uid = _uid(request, data)
    changes = {key: value for key, value in data.items() if key != "id_token"}
    if changes.get("telegram_enabled") is True and not telegram_watch.get_connection(uid).get("connected"):
        raise HTTPException(status_code=409, detail="Connect Telegram before enabling it for a watch.")
    try:
        watch = watch_service.update_watch(uid, watch_id, changes, get_user_tier(uid))
    except watch_service.WatchError as exc:
        _raise(exc)
    except Exception as exc:
        logging.error("patch_watch failed category=%s", safe_exception(exc))
        raise HTTPException(status_code=500, detail="Error updating watch")
    return {"status": "success", "watch": watch}


@router.get("/api/my/telegram")
@limiter.limit("20/minute")
def my_telegram(request: Request):
    uid = _uid(request, {})
    try:
        return {"status": "success", "telegram": telegram_watch.get_connection(uid)}
    except Exception as exc:
        logging.error("my_telegram failed category=%s", safe_exception(exc))
        raise HTTPException(status_code=500, detail="Error loading Telegram connection")


@router.post("/api/my/telegram/link")
@limiter.limit("5/minute")
def create_telegram_link(request: Request, data: dict = Body(default={})):
    uid = _uid(request, data)
    try:
        link = telegram_watch.create_link(uid)
    except watch_service.WatchError as exc:
        _raise(exc)
    except Exception as exc:
        logging.error(
            "create_telegram_link failed category=%s", safe_exception(exc)
        )
        raise HTTPException(status_code=500, detail="Error creating Telegram link")
    return {"status": "success", **link}


@router.post("/api/my/telegram/test")
@limiter.limit("3/minute")
async def test_telegram(request: Request, data: dict = Body(default={})):
    uid = await asyncio.to_thread(_uid, request, data)
    try:
        result = await asyncio.to_thread(telegram_watch.send_test, uid)
    except watch_service.WatchError as exc:
        _raise(exc)
    except Exception as exc:
        logging.error("test_telegram failed category=%s", safe_exception(exc))
        raise HTTPException(status_code=500, detail="Error testing Telegram connection")
    return {"status": "success", "delivery": result}


@router.delete("/api/my/telegram")
@limiter.limit("5/minute")
def disconnect_telegram(request: Request, data: dict = Body(default={})):
    uid = _uid(request, data)
    try:
        state = telegram_watch.disconnect(uid)
    except Exception as exc:
        logging.error(
            "disconnect_telegram failed category=%s", safe_exception(exc)
        )
        raise HTTPException(status_code=500, detail="Error disconnecting Telegram")
    return {"status": "success", "telegram": state}


@router.post("/api/telegram/webhook")
async def telegram_webhook(request: Request):
    # The secret first, the body after: until 2026-10-28 FastAPI parsed the
    # JSON of anyone's request before this check (audit). The body itself is
    # capped before (request_limits.PATH_MAX_REQUEST_BODY_BYTES).
    if not telegram_watch.verify_webhook_secret(
        request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    ):
        raise HTTPException(status_code=403, detail="Invalid Telegram webhook secret")
    try:
        data = await request.json()
    except ValueError:
        data = None
    if not isinstance(data, dict):
        # Acknowledged like a failed update: Telegram would only resend it.
        logging.warning("telegram_webhook update was not a JSON object")
        return {"ok": True}
    try:
        await asyncio.to_thread(telegram_watch.handle_update, data)
    except Exception as exc:
        # Return 200 so one malformed update cannot create an endless Telegram
        # retry loop; action-level errors are acknowledged inside the handler.
        logging.error(
            "telegram_webhook update failed category=%s", safe_exception(exc)
        )
    return {"ok": True}


@router.delete("/api/watch/{watch_id}")
@limiter.limit("10/minute")
def remove_watch(request: Request, watch_id: str, data: dict = Body(default={})):
    uid = _uid(request, data)
    try:
        watch_service.delete_watch(uid, watch_id)
    except watch_service.WatchError as exc:
        _raise(exc)
    except Exception as exc:
        logging.error("delete_watch failed category=%s", safe_exception(exc))
        raise HTTPException(status_code=500, detail="Error deleting watch")
    try:
        watch_brief.disable_if_no_watches(uid)
    except Exception as exc:
        # Die Watch ist bereits gelöscht; Brief-Cleanup darf dem Client keinen
        # falschen Delete-Fehler melden. Das Aktivierungs-Gate bleibt intakt.
        logging.error(
            "Morning Brief cleanup after final watch failed category=%s",
            safe_exception(exc),
        )
    return {"status": "success"}


@router.get("/api/watch/{watch_id}/image/{token}")
@limiter.limit("60/minute")
def watch_image(request: Request, watch_id: str, token: str):
    """Die gespeicherte Vorschau, nur von consens.io (kein Abruf beim Shop).

    Ohne Login, weil <img> keinen Token mitschicken kann; die URL trägt die
    zufällige Watch-ID plus Inhalts-Token und steht nur dort, wo die Watch
    ohnehin sichtbar ist. Zwischenspeicher nur im Browser (private).
    """
    try:
        found = watch_images.load_image(watch_id, token)
    except Exception as exc:
        logging.warning("watch_image failed category=%s", safe_exception(exc))
        raise HTTPException(status_code=503, detail="Image unavailable")
    if not found:
        raise HTTPException(status_code=404, detail="Not found")
    content, content_type = found
    return Response(
        content=content,
        media_type=content_type,
        # nosniff und CSP setzt die Security-Middleware für jede Antwort.
        headers={"Cache-Control": "private, max-age=2592000, immutable"},
    )


@router.delete("/api/watch/{watch_id}/image")
@limiter.limit("10/minute")
def dismiss_watch_image(request: Request, watch_id: str, data: dict = Body(default={})):
    uid = _uid(request, data)
    try:
        watch_service.dismiss_watch_image(uid, watch_id)
    except watch_service.WatchError as exc:
        _raise(exc)
    except Exception as exc:
        logging.error("dismiss_watch_image failed category=%s", safe_exception(exc))
        raise HTTPException(status_code=500, detail="Error removing image")
    return {"status": "success"}


@router.get("/api/my/watch-brief")
@limiter.limit("20/minute")
def my_watch_brief(request: Request):
    uid = _uid(request, {})
    try:
        return {
            "status": "success",
            "brief": watch_brief.get_brief(uid),
            "has_watches": watch_brief.has_watches(uid),
        }
    except Exception as exc:
        logging.error("my_watch_brief failed category=%s", safe_exception(exc))
        raise HTTPException(status_code=500, detail="Error loading brief settings")


@router.patch("/api/my/watch-brief")
@limiter.limit("10/minute")
def patch_watch_brief(request: Request, data: dict = Body(...)):
    uid = _uid(request, data)
    changes = {key: value for key, value in data.items() if key != "id_token"}
    try:
        brief = watch_brief.update_brief(uid, changes)
    except watch_service.WatchError as exc:
        _raise(exc)
    except Exception as exc:
        logging.error(
            "patch_watch_brief failed category=%s", safe_exception(exc)
        )
        raise HTTPException(status_code=500, detail="Error updating brief settings")
    return {"status": "success", "brief": brief}


# A link in a mail only asks; the button on the page it opens acts. Mail
# scanners, link previews and prefetchers open every link in a message, so a
# GET that paused a watch or confirmed a follow did so without the reader.
# The POST is also what a mail client sends for the List-Unsubscribe header
# (RFC 8058), with the token in the same query string. Every page names what
# the link is about and offers the way back (app/core/notice_page.py).
_LINK_ERROR_MESSAGES = {
    "expired_token": "This link has expired. Open Watches to change the watch there.",
    "invalid_token": "This link is incomplete or was changed. Open Watches to change the watch there.",
}


# What the mail-link pages are about: the thing is a Watch (Apple-Audit H3).
_WATCH_EYEBROW = "Watch"


def _token_url(path: str, token: str) -> str:
    return f"{path}?token={quote(token, safe='')}"


def _link_error(request: Request, exc: watch_service.WatchError, *,
                eyebrow: str = _WATCH_EYEBROW, links=(WATCHES_LINK,)):
    gone = exc.code == "not_found"
    return notice_page(
        request, status_code=_STATUS_BY_CODE.get(exc.code, 400), eyebrow=eyebrow,
        heading="This watch no longer exists" if gone and eyebrow == _WATCH_EYEBROW
        else "This link no longer works",
        message=_LINK_ERROR_MESSAGES.get(exc.code, exc.message), links=links,
    )


def _watch_state_page(request: Request, view: dict, *, paused_now: bool = False,
                      resumed_now: bool = False):
    """The page for a watch reached by a mail link, by its current state."""
    watch_id = view["watch_id"]
    common = {
        "eyebrow": _WATCH_EYEBROW, "subject_label": "Watch", "subject": view["question"],
    }
    if view["status"] == watch_service.WATCH_STATUS_RESOLVED:
        return notice_page(
            request, heading="This watch reached its goal",
            message="It stopped checking and freed its slot. Open it to watch for something new.",
            links=[WATCHES_LINK], **common,
        )
    if view["status"] == "active":
        return notice_page(
            request, heading="Watch resumed" if resumed_now else "This watch is active",
            message="It checks again on its usual schedule and writes when something moves."
            if resumed_now else "It checks on its usual schedule and writes when something moves.",
            links=[WATCHES_LINK], **common,
        )
    return notice_page(
        request, heading="Watch paused" if paused_now else "This watch is paused",
        message="It no longer checks or writes. Resume it whenever you like."
        if paused_now else "It does not check or write until you resume it.",
        action=_token_url("/watch/resume", watch_service.make_resume_token(watch_id)),
        button="Resume watch", links=[WATCHES_LINK], **common,
    )


def _share_question(share_id: str) -> tuple[str, str]:
    """(question, page path) of a public page, ("", "") when unavailable."""
    try:
        share = share_snapshots.get_share(share_id) or {}
    except Exception as exc:
        logging.warning("follow page lookup failed category=%s", safe_exception(exc))
        return "", ""
    if share.get("status") != "active" or str(share.get("visibility") or "public") != "public":
        return "", ""
    return (
        " ".join(str(share.get("question") or "").split()),
        share_snapshots.share_path(share.get("slug") or "", share_id),
    )


def _view_or_error(request: Request, watch_id: str):
    try:
        view = watch_service.watch_link_view(watch_id)
    except Exception as exc:
        logging.error("watch link lookup failed category=%s", safe_exception(exc))
        return None, notice_page(
            request, status_code=503, eyebrow=_WATCH_EYEBROW,
            heading="This page could not load",
            message="Your watch is unchanged. Please try the link again in a moment.",
            links=[WATCHES_LINK],
        )
    if not view:
        return None, _link_error(request, watch_service.WatchError("not_found", "This watch no longer exists."))
    return view, None


@router.post("/api/share/{share_id}/follow")
@limiter.limit("3/minute")
async def follow_share(request: Request, share_id: str, data: dict = Body(default={})):
    """Besucher-Follow (Double-Opt-in): sendet nur eine Bestätigungs-Mail.

    Bewusst ohne Auth (Besucher!) und ohne IP/UA-Speicherung; persistiert
    wird erst beim Klick auf den Bestätigungslink. Die Antwort ist immer
    generisch, damit Adressen nicht enumeriert werden können.
    """
    try:
        pending = await asyncio.to_thread(
            watch_followers.request_follow, share_id, data.get("email")
        )
    except watch_service.WatchError as exc:
        _raise(exc)
    except Exception as exc:
        logging.error("follow_share failed category=%s", safe_exception(exc))
        raise HTTPException(status_code=500, detail="Error processing follow request")
    if pending["token"]:
        if not mailer.is_configured():
            raise HTTPException(status_code=503, detail="Email delivery is not configured.")
        share_url = SITE_URL + "/s/" + share_id
        confirm_url = SITE_URL + "/watch/follow/confirm?token=" + pending["token"]
        sent = await mailer.send_message(mailer.build_follow_confirm_message(
            recipient=pending["email"], question=pending["question"],
            confirm_url=confirm_url, share_url=share_url,
            language=request_language(request),
        ))
        if not sent:
            raise HTTPException(status_code=502, detail="Confirmation email could not be sent. Please try again later.")
    return {"status": "success", "message": "Check your inbox and confirm to start following."}


_FOLLOW_EYEBROW = "Question you follow"


@router.get("/watch/follow/confirm", response_class=HTMLResponse)
@limiter.limit("20/minute")
def follow_confirm_page(request: Request, token: str = ""):
    try:
        share_id, _email = watch_followers.parse_follow_confirm_token(token)
    except watch_service.WatchError as exc:
        return _link_error(request, exc, eyebrow=_FOLLOW_EYEBROW, links=[{"href": "/", "label": "Open consens.io"}])
    question, path = _share_question(share_id)
    return notice_page(
        request, eyebrow=_FOLLOW_EYEBROW, heading="Follow this question?",
        message="You get one email whenever this answer changes materially. No account needed.",
        subject_label="Question", subject=question,
        action=_token_url("/watch/follow/confirm", token), button="Confirm and follow",
        links=[{"href": path, "label": "Open the page"}] if path else [],
    )


@router.post("/watch/follow/confirm", response_class=HTMLResponse)
@limiter.limit("20/minute")
def follow_confirm(request: Request, token: str = ""):
    try:
        result = watch_followers.confirm_follow(token, language=request_language(request))
    except watch_service.WatchError as exc:
        return _link_error(request, exc, eyebrow=_FOLLOW_EYEBROW, links=[{"href": "/", "label": "Open consens.io"}])
    return notice_page(
        request, eyebrow=_FOLLOW_EYEBROW, heading="You're following this question",
        message="We email you when this answer changes materially.",
        subject_label="Question", subject=result.get("question") or "",
        links=[{"href": result.get("share_path") or "/", "label": "Open the page"}],
    )


@router.get("/watch/follow/unsubscribe", response_class=HTMLResponse)
@limiter.limit("20/minute")
def follow_unsubscribe_page(request: Request, token: str = ""):
    try:
        share_id, _email = watch_followers.parse_follow_unsubscribe_token(token)
    except watch_service.WatchError as exc:
        return _link_error(request, exc, eyebrow=_FOLLOW_EYEBROW, links=[{"href": "/", "label": "Open consens.io"}])
    question, path = _share_question(share_id)
    return notice_page(
        request, eyebrow=_FOLLOW_EYEBROW, heading="Unfollow this question?",
        message="You will no longer get emails when this answer changes.",
        subject_label="Question", subject=question,
        action=_token_url("/watch/follow/unsubscribe", token), button="Unfollow",
        links=[{"href": path, "label": "Open the page"}] if path else [],
    )


@router.post("/watch/follow/unsubscribe", response_class=HTMLResponse)
@limiter.limit("20/minute")
def follow_unsubscribe(request: Request, token: str = ""):
    try:
        result = watch_followers.unsubscribe_follow(token)
    except watch_service.WatchError as exc:
        return _link_error(request, exc, eyebrow=_FOLLOW_EYEBROW, links=[{"href": "/", "label": "Open consens.io"}])
    question, path = _share_question(result.get("share_id") or "")
    return notice_page(
        request, eyebrow=_FOLLOW_EYEBROW, heading="Unfollowed",
        message="You will no longer get emails about this question. You can follow it again on its page.",
        subject_label="Question", subject=question,
        links=[{"href": path or "/", "label": "Open the page" if path else "Open consens.io"}],
    )


@router.get("/watch/unsubscribe", response_class=HTMLResponse)
@limiter.limit("20/minute")
def unsubscribe_page(request: Request, token: str = ""):
    try:
        watch_id = watch_service.parse_unsubscribe_token(token)
    except watch_service.WatchError as exc:
        return _link_error(request, exc)
    view, error = _view_or_error(request, watch_id)
    if error:
        return error
    if view["status"] != "active":
        return _watch_state_page(request, view)
    return notice_page(
        request, eyebrow=_WATCH_EYEBROW, heading="Pause this watch?",
        message="Pausing stops its checks and its emails. You can resume it any time.",
        subject_label="Watch", subject=view["question"],
        action=_token_url("/watch/unsubscribe", token), button="Pause watch",
        links=[WATCHES_LINK],
    )


@router.post("/watch/unsubscribe", response_class=HTMLResponse)
@limiter.limit("20/minute")
def unsubscribe(request: Request, token: str = ""):
    try:
        result = watch_service.unsubscribe(token)
    except watch_service.WatchError as exc:
        return _link_error(request, exc)
    view, error = _view_or_error(request, result["watch_id"])
    return error or _watch_state_page(request, view, paused_now=True)


@router.get("/watch/resume", response_class=HTMLResponse)
@limiter.limit("20/minute")
def resume_page(request: Request, token: str = ""):
    try:
        watch_id = watch_service.parse_resume_token(token)
    except watch_service.WatchError as exc:
        return _link_error(request, exc)
    view, error = _view_or_error(request, watch_id)
    if error:
        return error
    if view["status"] not in {"paused", "paused_error"}:
        return _watch_state_page(request, view)
    return notice_page(
        request, eyebrow=_WATCH_EYEBROW, heading="Resume this watch?",
        message="It checks again on its usual schedule and writes when something moves.",
        subject_label="Watch", subject=view["question"],
        action=_token_url("/watch/resume", token), button="Resume watch",
        links=[WATCHES_LINK],
    )


@router.post("/watch/resume", response_class=HTMLResponse)
@limiter.limit("20/minute")
def resume(request: Request, token: str = ""):
    try:
        result = watch_service.resume_from_token(token, get_user_tier)
    except watch_service.WatchError as exc:
        if exc.code == "limit_reached":
            return notice_page(
                request, status_code=409, eyebrow=_WATCH_EYEBROW,
                heading="No free watch slot",
                message="All your active watch slots are in use. Pause or delete another watch, then resume this one.",
                links=[WATCHES_LINK],
            )
        return _link_error(request, exc)
    except Exception as exc:
        logging.error("resume watch failed category=%s", safe_exception(exc))
        return notice_page(
            request, status_code=500, eyebrow=_WATCH_EYEBROW,
            heading="The watch could not be resumed",
            message="Nothing changed. Please try again, or resume it on your Watches page.",
            links=[WATCHES_LINK],
        )
    view, error = _view_or_error(request, result["watch_id"])
    return error or _watch_state_page(request, view, resumed_now=True)


_BRIEF_EYEBROW = "Morning brief"


@router.get("/watch/brief/unsubscribe", response_class=HTMLResponse)
@limiter.limit("20/minute")
def unsubscribe_brief_page(request: Request, token: str = ""):
    try:
        watch_brief.parse_brief_unsubscribe_token(token)
    except watch_service.WatchError as exc:
        return _link_error(request, exc, eyebrow=_BRIEF_EYEBROW)
    return notice_page(
        request, eyebrow=_BRIEF_EYEBROW, heading="Turn off the morning brief?",
        message="You will no longer get the daily digest of your watches. Watch alerts are unaffected.",
        action=_token_url("/watch/brief/unsubscribe", token), button="Turn off the brief",
        links=[WATCHES_LINK],
    )


@router.post("/watch/brief/unsubscribe", response_class=HTMLResponse)
@limiter.limit("20/minute")
def unsubscribe_brief(request: Request, token: str = ""):
    try:
        watch_brief.unsubscribe_brief(token)
    except watch_service.WatchError as exc:
        return _link_error(request, exc, eyebrow=_BRIEF_EYEBROW)
    return notice_page(
        request, eyebrow=_BRIEF_EYEBROW, heading="Morning brief turned off",
        message="You will no longer get the daily digest. Watch alerts are unaffected; "
                "you can turn the brief back on under Delivery on your Watches page.",
        links=[WATCHES_LINK],
    )

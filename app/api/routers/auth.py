import asyncio
import hashlib
import logging
import re
import time
from typing import Optional

from firebase_admin import auth
from fastapi import APIRouter, BackgroundTasks, Request, Body, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.i18n_middleware import request_language
from app.core.observability import safe_exception
from app.core.rate_limit import ApiUidRateLimitExceeded, api_uid_limiter, limiter
from app.core.security import verify_user_token, AuthenticationUnavailable, auth_unavailable_error
from app.services import sign_in_links
from app.services.registration import (
    deliver_password_setup_email,
    deliver_sign_in_email,
    find_or_provision_user,
    is_password_setup_configured,
    needs_password_setup,
)
from app.services.telegram_notifier import send_new_user_registration_notification

router = APIRouter()
_NEW_USER_WINDOW_MS = 10 * 60 * 1000
_REGISTER_RESPONSE_FLOOR_SECONDS = 0.35
# Setup-Mails pro Adresse und Stunde. Das IP-Limit allein hält niemanden mit
# vielen Adressen (Proxys, Botnetz) davon ab, ein fremdes Postfach zu fluten.
_SETUP_MAILS_PER_ADDRESS = 5
_SETUP_MAIL_WINDOW_SECONDS = 3600
# The page shows this one sentence for every refused link: unknown, expired,
# used or for an account that changed.
_LINK_REFUSED = {"error": "This link has expired or was already used.", "code": "link_invalid"}


class RegisterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str = Field(min_length=3, max_length=254)
    # Accepted temporarily for cached pre-migration clients, but deliberately
    # ignored. An anonymous caller must never choose an immediately usable
    # Firebase credential before proving mailbox ownership.
    password: Optional[str] = Field(default=None, max_length=256)
    # The mail sets a password instead of carrying a sign-in link: for an app
    # saved to the iPhone home screen, whose own storage a link from the mail
    # (it opens Safari) never reaches.
    password_setup: bool = False

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        normalized = str(value or "").strip().lower()
        if any(ord(char) < 32 or ord(char) == 127 for char in normalized):
            raise ValueError("Invalid email address")
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]{2,}", normalized):
            raise ValueError("Invalid email address")
        return normalized


class EmailLinkRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Any string up to this size reaches sign_in_links.redeem, which refuses
    # a malformed code with the same answer as an unknown one.
    code: str = Field(default="", max_length=128)


async def _neutral_registration_response(started_at: float) -> dict:
    remaining = _REGISTER_RESPONSE_FLOOR_SECONDS - (time.monotonic() - started_at)
    if remaining > 0:
        await asyncio.sleep(remaining)
    return {"status": "check_inbox"}


def _recent_registration_method(user) -> str:
    """Return the provider only while Firebase still identifies a new account."""
    metadata = getattr(user, "user_metadata", None)
    created_ms = getattr(metadata, "creation_timestamp", None)
    try:
        age_ms = (time.time() * 1000) - float(created_ms)
    except (TypeError, ValueError):
        return ""
    if age_ms < -60_000 or age_ms > _NEW_USER_WINDOW_MS:
        return ""

    provider_ids = {
        str(getattr(item, "provider_id", "") or "").strip()
        for item in (getattr(user, "provider_data", None) or [])
    }
    if "google.com" in provider_ids:
        return "google"
    if "password" in provider_ids:
        return "email/password"
    return "firebase"


@router.post("/register")
@limiter.limit("3/minute")
async def register_user(
    request: Request,
    background_tasks: BackgroundTasks,
    data: RegisterRequest,
):
    started_at = time.monotonic()
    email = data.email

    try:
        if not is_password_setup_configured():
            raise RuntimeError("Password setup is not configured")
        try:
            # Gehasht, damit der Prozess-Zähler keine Adressen im Klartext hält.
            address_key = hashlib.sha256(email.encode("utf-8")).hexdigest()
            api_uid_limiter.check(
                address_key,
                "register:setup-mail",
                _SETUP_MAILS_PER_ADDRESS,
                window_seconds=_SETUP_MAIL_WINDOW_SECONDS,
            )
        except ApiUidRateLimitExceeded:
            # Gleiche Antwort wie immer: ein 429 würde verraten, dass für
            # diese Adresse gerade Mails rausgehen.
            logging.warning("/register: setup mail cap reached for one address")
            return await _neutral_registration_response(started_at)
        # New users receive an unguessable temporary credential. Existing and
        # new addresses then take the exact same mailbox-only path, so an
        # anonymous caller cannot distinguish them with a follow-up login.
        user, created = await asyncio.to_thread(find_or_provision_user, email)
        first = created or needs_password_setup(user)
        if data.password_setup:
            background_tasks.add_task(
                deliver_password_setup_email, email, setup=first, language=request_language(request),
            )
        else:
            background_tasks.add_task(
                deliver_sign_in_email, email, uid=user.uid, first=first, language=request_language(request),
            )
        if created:
            background_tasks.add_task(
                send_new_user_registration_notification,
                "email/password",
                user.uid,
            )
        return await _neutral_registration_response(started_at)

    except HTTPException:
        # bereits bewusst gesetzte Meldungen durchreichen
        raise
    except Exception as exc:
        logging.error("/register failed: %s", safe_exception(exc))
        raise HTTPException(status_code=503, detail="Registration is temporarily unavailable.")


@router.post("/auth/email-link")
# A code has 256 bits; the limit only keeps floods off Firestore and Firebase.
@limiter.limit("10/minute")
def sign_in_with_email_link(request: Request, data: EmailLinkRequest):
    """Trade the code from a sign-in mail for a Firebase custom token, once.

    The browser signs in with the token; the usual session path
    (/confirm-registration) follows from there."""
    try:
        sign_in = sign_in_links.redeem(data.code)
    except sign_in_links.LinkInvalid:
        raise HTTPException(status_code=400, detail=_LINK_REFUSED) from None
    except Exception as exc:
        logging.error("/auth/email-link failed: %s", safe_exception(exc))
        raise HTTPException(
            status_code=503,
            detail="Logging in is temporarily unavailable.",
            headers={"Retry-After": "5"},
        ) from None
    response = JSONResponse({"token": sign_in.token, "first": sign_in.first})
    response.headers["Cache-Control"] = "no-store"
    return response


@router.post("/auth/email-link/account")
@limiter.limit("10/minute")
def email_link_account(request: Request, data: EmailLinkRequest):
    """The address a sign-in link would log in; spends nothing, changes nothing.

    A browser that did not ask for the link shows it and logs in only after
    a click, so a page load alone (a mail scanner's) leaves the link usable."""
    try:
        email = sign_in_links.account_address(data.code)
    except sign_in_links.LinkInvalid:
        raise HTTPException(status_code=400, detail=_LINK_REFUSED) from None
    except Exception as exc:
        logging.error("/auth/email-link/account failed: %s", safe_exception(exc))
        raise HTTPException(
            status_code=503,
            detail="Logging in is temporarily unavailable.",
            headers={"Retry-After": "5"},
        ) from None
    response = JSONResponse({"email": email})
    response.headers["Cache-Control"] = "no-store"
    return response


@router.post("/confirm-registration")
# Runs on every sign-in and page load (firebase.js), so the limit only stops
# a flood: each call costs a revocation lookup at Firebase.
@limiter.limit("30/minute")
def confirm_registration(
    request: Request,
    background_tasks: BackgroundTasks,
    data: dict = Body(...),
):
    token = data.get("id_token")
    if not token:
        raise HTTPException(status_code=400, detail="Authentication failed")

    try:
        uid = verify_user_token(
            token,
            allow_unverified=True,
            check_revoked=True,
        )
        user = auth.get_user(uid)
    except AuthenticationUnavailable:
        raise auth_unavailable_error() from None
    except Exception as exc:
        logging.error(
            "/confirm-registration token error: %s", safe_exception(exc)
        )
        raise HTTPException(status_code=401, detail="Authentication failed")

    if not user.email_verified:
        # Diese Info ist okay, weil sie nichts über Passwort / Existenz aussagt
        raise HTTPException(status_code=400, detail="Email address not yet verified.")

    registration_method = _recent_registration_method(user)
    if registration_method:
        background_tasks.add_task(
            send_new_user_registration_notification,
            registration_method,
            uid,
        )

    response = JSONResponse({"status": "registered"})
    response.headers["Cache-Control"] = "no-store"
    forwarded_proto = request.headers.get("x-forwarded-proto", "").split(",", 1)[0].strip()
    response.set_cookie(
        "session",
        token,
        max_age=60 * 60,
        httponly=True,
        secure=request.url.scheme == "https" or forwarded_proto == "https",
        samesite="lax",
        path="/",
    )
    return response


@router.delete("/auth/session")
def clear_session():
    response = JSONResponse({"status": "signed_out"})
    response.headers["Cache-Control"] = "no-store"
    response.delete_cookie("session", path="/", httponly=True, samesite="lax")
    return response

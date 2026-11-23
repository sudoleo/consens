"""Authenticated private file operations for Agent chats.

A picture under an answer loads as a preview (``?preview=1``): at most
agent_web_images.MAX_SIDE pixels on a
side, as WebP, when the stored file is larger; a GIF keeps its frames. The
original stays the download and what the file viewer opens.

The same ``?preview=1`` is what the app's document preview shows
(static/js/file-viewer.js): an Office file the agent shared from
its workspace answers with its PDF from the converter all accounts share
(agent_office.py, agent_vm_tools._office_preview), a Word file the user sent
with the text read from it (its paragraphs, plain text), a PDF with itself.

An HTML file the agent shared runs in the chat as a page (app/core/html_page.py):
the browser asks for its address, signed in, and a frame loads it from
``show_page``, the only route that answers a file of a chat as a document.
Every other answer here is bytes to save or one of the fixed preview types.
"""
import io
import logging
from typing import Optional

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import Response, JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from urllib.parse import quote

from app.api.routers.agent import require_agent_access
from app.api.routers.chat_history import _chat_uid, _raise_store_error
from app.core import html_page
from app.core.entitlements import entitlements_for, normalize_tier
from app.core.observability import safe_exception
from app.core.security import TierStatusUnavailable, db_firestore, get_user_tier, is_user_admin
from app.core.rate_limit import ApiUidRateLimitExceeded, api_uid_limiter, limiter
from app.services import agent_pages
from app.services.agent_files import UPLOAD_QUOTAS, AgentFiles, FileUnavailable, StorageNotConfigured
from app.services.chat_store import ChatNotFound

router = APIRouter()


class Upload(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    name: str = Field(min_length=1, max_length=200)
    data: str = Field(min_length=1, max_length=7_000_000)
    # Set when the browser fetched the file from Google's picker. The file is
    # then Google data: the chat it is sent in follows the Google rules.
    drive_file_id: Optional[str] = Field(default=None, pattern=r"^[A-Za-z0-9_-]{10,200}$")


def service(request):
    uid = _chat_uid(request)
    require_agent_access(uid)
    return uid, AgentFiles(db_firestore)


# Uploads per account, on top of the per-IP limit: a burst of files is
# extraction work and storage, whoever sends it.
UPLOADS_PER_WINDOW = 30
UPLOAD_WINDOW_SECONDS = 600


def require_uploads(uid):
    """Uploading follows the attachment rule of every mode (every tier) and
    returns the account's storage quota (files, bytes).
    Listing, downloading and deleting stay open: Agent writes documents into
    the same store for every account."""
    try:
        tier = normalize_tier(get_user_tier(uid))
        admin = is_user_admin(uid)
    except TierStatusUnavailable:
        raise HTTPException(503, "Account tier is temporarily unavailable. Please retry.") from None
    if not (entitlements_for(tier).attachments or admin):
        raise HTTPException(403, "Attachments are not available for this account.")
    try:
        api_uid_limiter.check(uid, "agent:upload", UPLOADS_PER_WINDOW, window_seconds=UPLOAD_WINDOW_SECONDS)
    except ApiUidRateLimitExceeded as exc:
        raise HTTPException(429, "Too many uploads in a short time. Please wait a few minutes.",
                            headers=exc.headers) from None
    return UPLOAD_QUOTAS["pro"] if admin else UPLOAD_QUOTAS.get(tier, UPLOAD_QUOTAS["free"])


def invoke(operation, uid):
    try:
        return operation()
    except HTTPException:
        raise
    except StorageNotConfigured:
        raise HTTPException(503, "Private file storage is not available right now.") from None
    except FileUnavailable as exc:
        raise HTTPException(422, str(exc)) from None
    except Exception as exc:
        _raise_store_error(exc, operation="access private files", uid=uid)


@router.post("/agent/chats/{chat_id}/files")
@limiter.limit("10/minute")
def upload_file(request: Request, chat_id: str, payload: Upload):
    uid, files = service(request)
    quota = require_uploads(uid)
    extra = None
    if payload.drive_file_id:
        from app.services.google_connections import drive_picker, user_allowed
        if not drive_picker() or not user_allowed(uid):
            raise HTTPException(403, "Google Drive is not available for this account.")
        extra = {"kind": "drive_file", "origin": {"source": "google_drive", "file_id": payload.drive_file_id}}
    def operation():
        files.expire(uid, chat_id)
        return files.upload(uid, chat_id, payload.model_dump(exclude={"drive_file_id"}), limits=quota, extra=extra)
    return JSONResponse({"file": invoke(operation, uid)}, headers={"Cache-Control": "private, no-store"})


@router.get("/agent/chats/{chat_id}/files")
@limiter.limit("60/minute")
def list_files(request: Request, chat_id: str):
    uid, files = service(request)
    return JSONResponse({"files": invoke(lambda: files.list(uid, chat_id), uid)}, headers={"Cache-Control": "private, no-store"})


# Pictures a preview can stand for; a GIF would lose its frames.
PREVIEW_MIMES = frozenset({"image/png", "image/jpeg", "image/webp"})


def _preview(mime, raw):
    """The picture at most MAX_SIDE pixels on a side as WebP (the encoding of
    the pictures from the web, agent_web_images.encode), or None when the
    stored one is no larger or no picture to shrink."""
    if mime not in PREVIEW_MIMES:
        return None
    from PIL import Image
    from app.services import agent_web_images
    try:
        with Image.open(io.BytesIO(raw)) as image:
            if max(image.size) <= agent_web_images.MAX_SIDE and len(raw) <= agent_web_images.STORED_BYTES:
                return None
    except Exception:
        return None
    shrunk = agent_web_images.encode(raw)
    return shrunk[0] if shrunk and len(shrunk[0]) < len(raw) else None


DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
# Types a browser opens as a document and runs. A stored file of one goes
# out as bytes to save, whatever asks for its address.
DOCUMENT_MIMES = frozenset({"text/html", "application/xhtml+xml", "image/svg+xml", "text/xml", "application/xml"})
INLINE = {"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff", "Content-Disposition": "inline"}


def _word_text(meta):
    """A Word file's text as read on upload (agent_file_extract), paragraph
    by paragraph, or None when nothing was read."""
    if meta.get("mime") != DOCX_MIME:
        return None
    texts = [str(part.get("text") or "").strip() for part in meta.get("parts") or [] if isinstance(part, dict)]
    text = "\n\n".join(text for text in texts if text)
    return text or None


@router.get("/agent/chats/{chat_id}/files/{file_id}")
@limiter.limit("60/minute")
def download_file(request: Request, chat_id: str, file_id: str, preview: bool = False):
    uid, files = service(request)
    # The metadata once (a picture under every answer asks here): the
    # preview's branch and the bytes both come from it.
    known = None
    if preview:
        known = invoke(lambda: files.get(uid, chat_id, file_id), uid)
        if isinstance(known.get("preview"), dict):
            _, pdf = invoke(lambda: files.download_preview(uid, chat_id, file_id, data=known), uid)
            return Response(pdf, media_type="application/pdf", headers=INLINE)
        text = _word_text(known)
        if text is not None:
            return Response(text.encode("utf-8"), media_type="text/plain; charset=utf-8", headers=INLINE)
    meta, raw = invoke(lambda: files.download(uid, chat_id, file_id, data=known), uid)
    smaller = _preview(meta["mime"], raw) if preview else None
    if smaller is not None:
        return Response(smaller, media_type="image/webp", headers=INLINE)
    return Response(raw, media_type=download_type(meta["mime"]), headers={"Cache-Control": "private, no-store",
        "X-Content-Type-Options": "nosniff", "Content-Disposition": "attachment; filename*=UTF-8''" + quote(meta["name"], safe="")})


def download_type(mime):
    """The type a stored file is downloaded as: its own, unless a browser
    would open that as a document."""
    kind = str(mime or "").split(";", 1)[0].strip().lower()
    return "application/octet-stream" if kind in DOCUMENT_MIMES or kind.endswith("+xml") else mime


@router.post("/agent/chats/{chat_id}/files/{file_id}/page")
@limiter.limit("60/minute")
def open_page(request: Request, chat_id: str, file_id: str):
    """The address a frame in the chat loads a shared page from, for the
    account that owns the chat (agent_pages.py)."""
    uid, files = service(request)
    known = invoke(lambda: files.get(uid, chat_id, file_id), uid)
    if known.get("page") != "html":
        raise HTTPException(404, "This file is not shown as a page.")
    return JSONResponse({"url": html_page.PATH_PREFIX + agent_pages.issue(uid, chat_id, file_id),
                         "expires_in": agent_pages.TOKEN_SECONDS}, headers={"Cache-Control": "private, no-store"})


def _no_page(status):
    return Response(b"", status_code=status, media_type="text/plain; charset=utf-8", headers=html_page.HEADERS)


@router.get(html_page.PATH_PREFIX + "{token}")
@limiter.limit("120/minute")
def show_page(request: Request, token: str):
    """A shared page as the document a frame runs (html_page.document). The
    address is the whole permission, so every answer, a refusal too, carries
    html_page.HEADERS; the security middleware sets them for this path again,
    over whatever answers in the route's place."""
    try:
        uid, chat_id, file_id = agent_pages.read(token)
        meta, raw = AgentFiles(db_firestore).download(uid, chat_id, file_id)
        source = html_page.text(raw) if meta.get("page") == "html" and len(raw) <= html_page.MAX_BYTES else None
    except (agent_pages.InvalidToken, FileUnavailable, ChatNotFound):
        return _no_page(404)
    except Exception as exc:
        logging.error("agent page failed category=%s", safe_exception(exc))
        return _no_page(503)
    if source is None:
        return _no_page(404)
    return Response(html_page.document(source, meta.get("name")), media_type=html_page.CONTENT_TYPE,
                    headers=html_page.HEADERS)


@router.delete("/agent/chats/{chat_id}/files/{file_id}")
@limiter.limit("30/minute")
def delete_file(request: Request, chat_id: str, file_id: str):
    uid, files = service(request)
    invoke(lambda: files.delete(uid, chat_id, file_id), uid)
    return JSONResponse({"status": "deleted"}, headers={"Cache-Control": "private, no-store"})

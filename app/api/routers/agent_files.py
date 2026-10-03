"""Authenticated private file operations for Agent chats."""
from typing import Optional

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import Response, JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from urllib.parse import quote

from app.api.routers.agent import require_agent_access
from app.api.routers.chat_history import _chat_uid, _raise_store_error
from app.core.entitlements import entitlements_for, normalize_tier
from app.core.security import TierStatusUnavailable, db_firestore, get_user_tier, is_user_admin
from app.core.rate_limit import ApiUidRateLimitExceeded, api_uid_limiter, limiter
from app.services.agent_files import UPLOAD_QUOTAS, AgentFiles, FileUnavailable, StorageNotConfigured

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
    """Uploading follows the attachment rule of every mode (every tier since
    2026-10-02) and returns the account's storage quota (files, bytes).
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
    except ApiUidRateLimitExceeded:
        raise HTTPException(429, "Too many uploads in a short time. Please wait a few minutes.") from None
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


@router.get("/agent/chats/{chat_id}/files/{file_id}")
@limiter.limit("60/minute")
def download_file(request: Request, chat_id: str, file_id: str):
    uid, files = service(request)
    meta, raw = invoke(lambda: files.download(uid, chat_id, file_id), uid)
    return Response(raw, media_type=meta["mime"], headers={"Cache-Control": "private, no-store",
        "X-Content-Type-Options": "nosniff", "Content-Disposition": "attachment; filename*=UTF-8''" + quote(meta["name"], safe="")})


@router.delete("/agent/chats/{chat_id}/files/{file_id}")
@limiter.limit("30/minute")
def delete_file(request: Request, chat_id: str, file_id: str):
    uid, files = service(request)
    invoke(lambda: files.delete(uid, chat_id, file_id), uid)
    return JSONResponse({"status": "deleted"}, headers={"Cache-Control": "private, no-store"})

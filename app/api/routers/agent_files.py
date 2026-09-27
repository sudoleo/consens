"""Authenticated private file operations for Agent chats."""
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import Response, JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from urllib.parse import quote

from app.api.routers.agent import require_agent_access
from app.api.routers.chat_history import _chat_uid, _raise_store_error
from app.core.security import db_firestore
from app.core.rate_limit import limiter
from app.services.agent_files import AgentFiles, FileUnavailable

router = APIRouter()


class Upload(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    name: str = Field(min_length=1, max_length=200)
    data: str = Field(min_length=1, max_length=7_000_000)


def service(request):
    uid = _chat_uid(request)
    require_agent_access(uid)
    return uid, AgentFiles(db_firestore)


def invoke(operation, uid):
    try:
        return operation()
    except HTTPException:
        raise
    except FileUnavailable as exc:
        raise HTTPException(422, str(exc)) from None
    except Exception as exc:
        _raise_store_error(exc, operation="access private files", uid=uid)


@router.post("/agent/chats/{chat_id}/files")
@limiter.limit("10/minute")
def upload_file(request: Request, chat_id: str, payload: Upload):
    uid, files = service(request)
    def operation():
        files.expire(uid, chat_id)
        return files.upload(uid, chat_id, payload.model_dump())
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

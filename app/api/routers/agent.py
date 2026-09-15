"""Admin/Pro-only bounded Agent turns in the existing chat storage."""
from __future__ import annotations

import logging
from typing import Literal
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator
from firebase_admin import firestore

from app.core.observability import safe_exception
from app.core.rate_limit import limiter, api_uid_limiter, ApiUidRateLimitExceeded
from app.core.security import db_firestore, is_user_admin, is_user_pro
from app.api.routers.chat_history import _chat_uid, _raise_store_error
from app.api.routers.bookmarks import _bookmark_meta
from app.services import persistence_guard
from app.services.agent_runs import AgentRunStore
from app.services.agent_loop import AgentLoop
from app.services.agent_policy import AgentPolicy
from app.services.agent_provider_limits import AgentProviderCooldown, provider_cooldowns, provider_failure
from app.services.agent_tools import configured_model
from app.services.agent_runtime import AgentCapacityExceeded, AgentStreamingResponse, agent_capacity
from app.services.chat_store import normalize_question, ChatNotFound, TurnStatusConflict, _idempotent_turn_id
from app.services.llm.agent_client import AgentCompletion, agent_model, agent_model_options, resolve_agent_model
from app.services.llm.credentials import resolve_developer_api_keys, openrouter_api_key
from app.services.llm.provider_runtime import AnalysisBudgetExceeded, ProviderCancellation, ProviderCancelled
from app.services.llm.streaming import iter_sse_with_keepalive, sse_pack, SSE_HEADERS
from app.services.llm.mock_llm import mock_llm_enabled

router = APIRouter()


def require_agent_access(uid):
    if not (is_user_pro(uid) or is_user_admin(uid)):
        raise HTTPException(status_code=403, detail="Agent Beta is available to Pro users and admins.")


class AgentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    chat_id: str = Field(pattern=r"^[0-9a-f]{32}$")
    client_request_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
    bookmark_id: str = Field(pattern=r"^[A-Za-z0-9_]{1,100}$")
    question: str
    stream: Literal[True] = True
    recover_only: bool = False
    model_id: str | None = Field(default=None, min_length=1, max_length=160)
    reasoning_effort: str = Field(default="default", pattern=r"^(default|none|minimal|low|medium|high|xhigh|max)$")

    @field_validator("question")
    @classmethod
    def valid_question(cls, value):
        return normalize_question(value)


def _save_bookmark(uid, payload, store, turn):
    chat = store.get_chat(uid, payload.chat_id)
    if chat["status"] != "active":
        raise ChatNotFound("Chat not found")
    ref = db_firestore.collection("users").document(uid).collection("bookmarks").document(payload.bookmark_id)
    existing = ref.get()
    if existing.exists and (existing.to_dict() or {}).get("chat_id") != payload.chat_id:
        raise TurnStatusConflict("Bookmark belongs to another conversation")
    if existing.exists and (existing.to_dict() or {}).get("agent_turn_position", 0) > turn["position"]:
        return _bookmark_meta(payload.bookmark_id, existing.to_dict())
    def chat_guard(tx):
        snapshot = store._chat_ref(uid, payload.chat_id).get(transaction=tx)
        if not snapshot.exists or (snapshot.to_dict() or {}).get("status") != "active":
            raise ChatNotFound("Chat not found")
    bookmark = persistence_guard.write_bookmark(
        uid=uid, db=db_firestore, doc_ref=ref, transaction_guard=chat_guard,
        current_guard=lambda current: not current or (
            current.get("chat_id") == payload.chat_id and current.get("agent_turn_position", 0) <= turn["position"]), patch={
        "query": turn["question"], "title": chat["title"], "mode": "Agent",
        "execution_mode": "agent", "chat_id": payload.chat_id, "turn_id": turn["id"],
        "agent_turn_position": turn["position"],
        "timestamp": firestore.SERVER_TIMESTAMP, "sources": [], "attachments": [],
        "previous_question": "", "previous_turn": {}, "share_result_id": "",
        "consensus_model": turn["consensus_model"], "included_providers": [], "model_labels": {},
        "responses": {"consensus": turn.get("consensus", ""), "differences": "", "differences_data": None},
    })
    return _bookmark_meta(payload.bookmark_id, bookmark)


def _final(uid, payload, store, turn):
    bookmark_meta = _save_bookmark(uid, payload, store, turn)
    return {"chat_id": payload.chat_id, "turn_id": turn["id"], "turn": turn,
            "response": turn["consensus"], "execution_mode": "agent", "bookmark_meta": bookmark_meta}


@router.get("/agent/models")
@limiter.limit("60/minute")
def available_agent_models(request: Request):
    from fastapi.responses import JSONResponse
    uid = _chat_uid(request)
    require_agent_access(uid)
    return JSONResponse(agent_model_options(), headers={"Cache-Control": "private, no-store"})


@router.post("/agent")
@limiter.limit("30/minute")
def run_agent(request: Request, payload: AgentRequest):
    uid = _chat_uid(request)
    require_agent_access(uid)
    try:
        api_uid_limiter.check(uid, "agent:turn", 20)
    except ApiUidRateLimitExceeded:
        raise HTTPException(status_code=429, detail="Too many agent requests. Please wait.") from None
    store = AgentRunStore(db_firestore)
    turn = None
    lease = None
    try:
        # Read before applying today's configuration: old requests remain
        # replayable after a model/price/key change without another paid call.
        try:
            existing = store.get_turn(uid, payload.chat_id, _idempotent_turn_id(payload.chat_id, payload.client_request_id))
        except ChatNotFound:
            existing = None
        if existing:
            if existing["question"] != payload.question or existing.get("execution_mode") != "agent":
                raise TurnStatusConflict("Request identity conflicts with another turn")
            selection = {"model_id": payload.model_id, "reasoning_effort": payload.reasoning_effort}
            prior_selection = existing.get("agent_settings", {}).get("selection", {"model_id": None, "reasoning_effort": "default"})
            if prior_selection != selection:
                raise TurnStatusConflict("Request identity conflicts with different agent settings")
            if existing["status"] == "completed":
                return _final(uid, payload, store, existing)
            raise HTTPException(status_code=409, detail="This request has already started. Reopen the saved conversation or send a new message after it finishes.")
        if payload.recover_only:
            raise HTTPException(status_code=404, detail="No saved answer is available for this request yet.")
        try:
            model = configured_model(resolve_agent_model(payload.model_id, payload.reasoning_effort))
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from None
        key = openrouter_api_key(resolve_developer_api_keys())
        if not key and not mock_llm_enabled():
            raise HTTPException(status_code=503, detail="Agent model is not configured.")
        provider_cooldowns.check(model, key or "")
        bookmark = db_firestore.collection("users").document(uid).collection("bookmarks").document(payload.bookmark_id).get()
        if bookmark.exists and (bookmark.to_dict() or {}).get("chat_id") != payload.chat_id:
            raise TurnStatusConflict("Bookmark belongs to another conversation")
        lease = agent_capacity.acquire()
        turn = store.create_turn(
            uid, payload.chat_id, question=payload.question, mode="Agent", deep_search=False,
            selected_models=[model.model], consensus_model=model.model,
            client_request_id=payload.client_request_id, execution_mode="agent",
            agent_settings={**model.settings(), "policy": AgentPolicy().snapshot(),
                            "selection": {"model_id": payload.model_id, "reasoning_effort": payload.reasoning_effort}},
        )
        if turn["status"] == "completed":
            lease.release()
            return _final(uid, payload, store, store.get_turn(uid, payload.chat_id, turn["id"]))
        messages = store.messages(uid, payload.chat_id, turn, model=model)
    except Exception as exc:
        try:
            if turn:
                store.release_unclaimed(uid, payload.chat_id, turn["id"])
        finally:
            if lease:
                lease.release()
        if isinstance(exc, HTTPException):
            raise
        if isinstance(exc, AgentProviderCooldown):
            raise HTTPException(status_code=429, detail=str(exc), headers={"Retry-After": str(exc.retry_after)}) from None
        if isinstance(exc, AgentCapacityExceeded):
            raise HTTPException(status_code=503, detail=str(exc), headers={"Retry-After": "5"}) from None
        if isinstance(exc, ValueError):
            raise HTTPException(status_code=422, detail=str(exc)) from None
        _raise_store_error(exc, operation="prepare agent turn", uid=uid)

    cancellation = ProviderCancellation()

    def events():
        loop = AgentLoop(store=store, uid=uid, chat_id=payload.chat_id, turn_id=turn["id"],
                         model=model, messages=messages, api_key=key or "", cancellation=cancellation,
                         completion_factory=AgentCompletion,
                         mock_answer="Agent test answer: " + payload.question if mock_llm_enabled() else None)
        completion = loop.completion
        status = "failed"
        error = "The agent response could not be completed. Please try a new message."
        failure = {}
        try:
            source = loop.run()
            try:
                for event in source:
                    if event:
                        yield sse_pack(event["type"], event)
            finally:
                source.close()
            status = "succeeded"
        except (ProviderCancelled, GeneratorExit):
            status = "cancelled"
            raise
        except (AgentCapacityExceeded, TurnStatusConflict, AnalysisBudgetExceeded) as exc:
            error = str(exc)
        except AgentProviderCooldown as exc:
            error = str(exc)
            failure = {"code": "provider_rate_limited", "retry_after": exc.retry_after}
        except Exception as exc:
            provider_cooldowns.record(model, key or "", exc)
            failure = provider_failure(exc)
            error = failure.pop("error")
            logging.warning("Agent completion failed category=%s model=%s code=%s retry_after=%s",
                            safe_exception(exc), model.model, failure["code"], failure.get("retry_after"))
        if status != "succeeded":
            yield sse_pack("activity", {"version": 1, "step_id": "run", "id": "run/usage", "kind": "usage", "usage": completion.usage})
            yield sse_pack("error", {"error": error, **failure})
            return
        try:
            completed = store.get_turn(uid, payload.chat_id, turn["id"])
            yield sse_pack("final", _final(uid, payload, store, completed))
        except Exception as exc:
            logging.warning("Agent bookmark failed category=%s", safe_exception(exc))
            yield sse_pack("error", {"error": "The answer was saved to chat history, but its bookmark could not be saved. Retry this request to recover it."})

    def stream_events():
        if not lease.start():
            return
        try:
            yield from events()
        finally:
            lease.release()

    return AgentStreamingResponse(
        iter_sse_with_keepalive(stream_events(), cancellation=cancellation), cancellation=cancellation,
        lease=lease, cleanup=lambda: store.release_unclaimed(uid, payload.chat_id, turn["id"]),
        media_type="text/event-stream", headers={**SSE_HEADERS, "Cache-Control": "private, no-store"},
    )

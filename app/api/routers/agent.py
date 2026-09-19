"""Admin/Pro-only bounded Agent turns in the existing chat storage."""
from __future__ import annotations

import logging
from dataclasses import asdict, replace
from typing import Literal
from fastapi import APIRouter, HTTPException, Request, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator
from firebase_admin import firestore

from app.core.observability import safe_exception
from app.core.rate_limit import limiter, api_uid_limiter, ApiUidRateLimitExceeded
from app.core.security import db_firestore, is_user_admin, is_user_pro
from app.api.routers.chat_history import _chat_uid, _raise_store_error
from app.api.routers.bookmarks import _bookmark_meta
from app.services import persistence_guard, prompt_config
from app.services import agent_quota
from app.services.agent_comparison import comparison_selection
from app.services.source_verification import Limits as SourceCheckLimits
from app.services.agent_runs import AgentRunStore
from app.services.agent_policy import AgentPolicy, supports_delegation
from app.services.agent_delegation import DelegationLoop
from app.services.agent_provider_limits import AgentProviderCooldown, agent_failure, provider_cooldowns
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
    comparison_models: dict[str, str] | None = Field(default=None, max_length=9)
    check_sources: bool = False

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
            "response": turn["consensus"], "execution_mode": "agent", "bookmark_meta": bookmark_meta,
            "token_budget": agent_quota.snapshot(store.db, uid)}


def _save_interrupted(uid, payload, store, turn_id):
    try:
        turn = store.get_turn(uid, payload.chat_id, turn_id)
    except Exception as exc:
        logging.warning("Interrupted Agent snapshot unavailable category=%s", safe_exception(exc))
        return None
    if turn.get("consensus") and turn["status"] == "failed":
        try:
            turn["bookmark_meta"] = _save_bookmark(uid, payload, store, turn)
        except Exception as exc:
            logging.warning("Interrupted Agent bookmark unavailable category=%s", safe_exception(exc))
    return turn


@router.get("/agent/models")
@limiter.limit("60/minute")
def available_agent_models(request: Request):
    from fastapi.responses import JSONResponse
    uid = _chat_uid(request)
    require_agent_access(uid)
    return JSONResponse({**agent_model_options(), "token_budget": agent_quota.snapshot(db_firestore, uid)},
                        headers={"Cache-Control": "private, no-store"})


@router.get("/agent/budget")
@limiter.limit("60/minute")
def available_agent_budget(request: Request):
    uid = _chat_uid(request)
    require_agent_access(uid)
    return JSONResponse({"token_budget": agent_quota.snapshot(db_firestore, uid)},
                        headers={"Cache-Control": "private, no-store"})


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
            if existing.get("agent_settings", {}).get("comparison_selection") != payload.comparison_models:
                raise TurnStatusConflict("Request identity conflicts with different comparison models")
            if existing.get("agent_settings", {}).get("check_sources", False) != payload.check_sources:
                raise TurnStatusConflict("Request identity conflicts with different contradiction settings")
            if payload.recover_only and existing["status"] == "pending":
                # A lost producer has no live SSE/poller to close its lease.
                # Reap only expired runs; this never starts a paid step.
                store.reap_delegation(uid, payload.chat_id, existing["id"])
                existing = store.get_turn(uid, payload.chat_id, existing["id"])
            if existing["status"] == "completed":
                return _final(uid, payload, store, existing)
            if payload.recover_only and existing["status"] == "failed" and existing.get("consensus"):
                return _final(uid, payload, store, existing)
            failed = existing["status"] == "failed"
            return JSONResponse({"error": "This run ended without a saved answer. Send a new message to try again." if failed
                else "This request is still running. You can check its saved answer after it finishes.",
                "code": "answer_unavailable" if failed else "request_running", "recoverable": not failed,
                "recovery_state": "unavailable" if failed else "running"}, status_code=409)
        if payload.recover_only:
            return JSONResponse({"error": "No saved answer is available for this request.",
                "code": "answer_unavailable", "recoverable": False}, status_code=404)
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
        config = prompt_config.get_config()
        delegation_config = config["delegation"]
        # Comparisons always use the shared bounded loop; worker delegation
        # retains its separately configured model/protocol feature gate.
        delegation_config = {**delegation_config, "enabled": delegation_config["enabled"] and supports_delegation(model)}
        policy = AgentPolicy.for_chat(delegation_config)
        comparisons = comparison_selection(payload.comparison_models)
        source_limits = SourceCheckLimits.configured() if payload.check_sources else None
        model = replace(model, request_config={**model.request_config, "_agent_bounded_search": True})
        turn = store.create_turn(
            uid, payload.chat_id, question=payload.question, mode="Agent", deep_search=False,
            selected_models=[model.model], consensus_model=model.model,
            client_request_id=payload.client_request_id, execution_mode="agent",
            agent_settings={**model.settings(), "policy": policy.snapshot(), "config_revision": config["revision"],
                            "delegation_config": delegation_config,
                            "comparison_selection": payload.comparison_models,
                            "check_sources": payload.check_sources,
                            "source_check_limits": asdict(source_limits) if source_limits else None,
                            "comparison_models": {p: m.snapshot() for p, m in comparisons.items()},
                            "selection": {"model_id": payload.model_id, "reasoning_effort": payload.reasoning_effort}},
        )
        if turn["status"] == "completed":
            lease.release()
            return _final(uid, payload, store, store.get_turn(uid, payload.chat_id, turn["id"]))
        messages = store.messages(uid, payload.chat_id, turn, model=model, config=config)
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
        loop = DelegationLoop(store=store, uid=uid, chat_id=payload.chat_id, turn_id=turn["id"],
                         model=model, messages=messages, api_key=key or "", cancellation=cancellation,
                         completion_factory=AgentCompletion, policy=policy,
                         delegation_config=delegation_config, cooldowns=provider_cooldowns,
                         comparison_models=comparisons,
                         check_sources=payload.check_sources,
                         source_limits=source_limits,
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
                        if event["type"] == "started" or (event["type"] == "activity" and event.get("kind") == "usage"):
                            try:
                                yield sse_pack("quota", {"token_budget": agent_quota.snapshot(store.db, uid)})
                            except Exception as exc:
                                logging.warning("Agent allowance unavailable category=%s", safe_exception(exc))
            finally:
                source.close()
            status = "succeeded"
        except (ProviderCancelled, GeneratorExit):
            status = "cancelled"
            _save_interrupted(uid, payload, store, turn["id"])
            raise
        except (AgentCapacityExceeded, TurnStatusConflict, AnalysisBudgetExceeded) as exc:
            failure = agent_failure(exc)
            error = failure.pop("error")
            logging.warning("Agent admission stopped category=%s model=%s reason=%s", safe_exception(exc), model.model, error)
        except AgentProviderCooldown as exc:
            error = str(exc)
            failure = {"code": "provider_rate_limited", "retry_after": exc.retry_after}
        except Exception as exc:
            provider_cooldowns.record(model, key or "", exc)
            failure = agent_failure(exc)
            error = failure.pop("error")
            logging.warning("Agent completion failed category=%s model=%s code=%s retry_after=%s",
                            safe_exception(exc), model.model, failure["code"], failure.get("retry_after"))
        if status != "succeeded":
            for event in loop._events():
                yield sse_pack(event["type"], event)
            interrupted = _save_interrupted(uid, payload, store, turn["id"])
            if interrupted is not None:
                pending = interrupted["status"] == "pending"
                failure["recoverable"] = pending or bool(interrupted.get("consensus"))
                failure["recovery_state"] = "running" if pending else "saved" if interrupted.get("consensus") else "unavailable"
                if interrupted.get("bookmark_meta"):
                    saved = dict(interrupted)
                    bookmark_meta = saved.pop("bookmark_meta")
                    failure["saved_answer"] = {"chat_id": payload.chat_id, "turn_id": saved["id"],
                        "turn": saved, "response": saved["consensus"], "bookmark_meta": bookmark_meta}
            if interrupted and interrupted.get("agent_review"):
                yield sse_pack("review", {"review": interrupted["agent_review"]})
            yield sse_pack("activity", {"version": 1, "step_id": "run", "id": "run/usage", "kind": "usage", "usage": completion.usage})
            try:
                failure["token_budget"] = agent_quota.snapshot(store.db, uid)
            except Exception as exc:
                logging.warning("Agent allowance unavailable category=%s", safe_exception(exc))
            yield sse_pack("error", {"error": error, **failure})
            return
        try:
            completed = store.get_turn(uid, payload.chat_id, turn["id"])
            yield sse_pack("final", _final(uid, payload, store, completed))
        except Exception as exc:
            logging.warning("Agent bookmark failed category=%s", safe_exception(exc))
            yield sse_pack("error", {"error": "The answer was saved to chat history, but its bookmark could not be saved. Recover the saved answer to reopen it.", "recoverable": True, "recovery_state": "saved"})

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


@router.get("/agent/chats/{chat_id}/turns/{turn_id}/agents")
@limiter.limit("120/minute")
def list_agents(request: Request, chat_id: str, turn_id: str):
    return _agent_details(request, chat_id, turn_id)


@router.get("/agent/chats/{chat_id}/turns/{turn_id}/agents/{agent_id}")
@limiter.limit("120/minute")
def agent_details(request: Request, chat_id: str, turn_id: str, agent_id: str,
                  after: int = Query(0, ge=0), limit: int = Query(25, ge=1, le=50)):
    return _agent_details(request, chat_id, turn_id, agent_id=agent_id, after=after, limit=limit)


def _agent_details(request, chat_id, turn_id, **kwargs):
    from fastapi.responses import JSONResponse
    uid = _chat_uid(request)
    require_agent_access(uid)
    try:
        data = AgentRunStore(db_firestore).delegation_view(uid, chat_id, turn_id, **kwargs)
        if not kwargs:
            data["token_budget"] = agent_quota.snapshot(db_firestore, uid)
        return JSONResponse(data, headers={"Cache-Control": "private, no-store"})
    except Exception as exc:
        _raise_store_error(exc, operation="read agent sessions", uid=uid)


@router.post("/agent/chats/{chat_id}/turns/{turn_id}/stop")
@limiter.limit("30/minute")
def stop_agent_run(request: Request, chat_id: str, turn_id: str):
    uid = _chat_uid(request)
    require_agent_access(uid)
    try:
        AgentRunStore(db_firestore).stop_delegation(uid, chat_id, turn_id)
        return {"status": "stopping"}
    except Exception as exc:
        _raise_store_error(exc, operation="stop agent sessions", uid=uid)

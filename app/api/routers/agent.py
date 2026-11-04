"""Agent turns in the existing chat storage (every signed-in account)."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import dataclasses
from datetime import datetime, timezone
import logging
import re
from typing import Literal, Optional
from fastapi import APIRouter, HTTPException, Request, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator
from firebase_admin import firestore

from app.core.observability import provider_diagnostic, safe_exception, safe_traceback
from app.services.error_alerts import report_server_exception
from app.core import config as cfg
from app.core.rate_limit import limiter, api_uid_limiter, ApiUidRateLimitExceeded
from app.core.security import TierStatusUnavailable, db_firestore, get_user_tier, is_user_admin, is_user_pro
from app.api.routers.chat_history import _chat_uid, _raise_store_error
from app.api.routers.bookmarks import _bookmark_meta, prepare_agent_share_result
from app.services import persistence_guard, prompt_config
from app.services import agent_quota, agent_secrets, agent_vm
from app.services.agent_memory import FirestoreAgentMemoryRepository, MemorySnapshot
from app.services.agent_comparison import AgentPreferences, comparison_selection
from app.services.agent_runs import AgentRunStore, get_agent_turn_context
from app.services.agent_sessions import HoldActionRefused, NotesFull
from app.services.agent_policy import AgentPolicy
from app.services.agent_loop import AgentLoop
from app.services.agent_provider_limits import AgentProviderCooldown, agent_failure, provider_cooldowns
from app.services.agent_tools import configured_model
from app.services.agent_runtime import AgentCapacityExceeded, AgentStreamingResponse, agent_capacity
from app.services.agent_background import AgentRunDuplicate, AgentRunStopped, AgentShuttingDown, agent_background
from app.services.chat_store import normalize_question, ChatNotFound, TurnStatusConflict, _idempotent_turn_id
from app.services.llm.agent_client import (PRO_REASONING_EFFORTS, REASONING_EFFORT_PATTERN, AgentCompletion, agent_model,
                                           agent_model_options, default_agent_model_id, free_default_effort,
                                           resolve_agent_model)
from app.services.llm.credentials import resolve_developer_api_keys, openrouter_api_key
from app.services.llm.provider_runtime import AnalysisBudgetExceeded, ProviderCancellation, ProviderCancelled
from app.services.llm.streaming import SSE_HEADERS, SSE_PADDING
from app.services.agent_live import agent_live
from app.services.llm.mock_llm import mock_llm_enabled
from app.services.agent_calendar import GoogleSelection

router = APIRouter()
# Past this a position is no number a stream gives: JavaScript counts exactly up to 2**53.
MAX_AFTER = 2 ** 53


def require_agent_access(uid):
    """Agent is open to every signed-in account; the daily token account limits it per tier. The
    tier is read here although it no longer decides access, so an unavailable tier service answers
    503 up front, before any write."""
    if not uid:
        raise HTTPException(status_code=401, detail="Log in to use Agent.")
    try:
        get_user_tier(uid)
    except TierStatusUnavailable:
        raise HTTPException(
            status_code=503, detail="Account tier is temporarily unavailable. Please retry."
        ) from None


def _premium_allowed(uid):
    try:
        return is_user_pro(uid) or is_user_admin(uid)
    except TierStatusUnavailable:
        raise HTTPException(
            status_code=503, detail="Account tier is temporarily unavailable. Please retry."
        ) from None


def require_model_access(uid, model_ids):
    """Premium models stay Pro in Agent as in Compare and Consensus, checked on the model the run
    uses (a migrated ID's current form)."""
    model_ids = [cfg.canonical_model_id(model_id) for model_id in model_ids if model_id]
    premium = [model_id for model_id in model_ids if model_id and model_id in cfg.PREMIUM_MODELS]
    if premium and not _premium_allowed(uid):
        labels = ", ".join(cfg.get_model_label(model_id) for model_id in premium)
        raise HTTPException(status_code=403, detail=f"{labels} is available on Pro. Choose another model.")


# The expensive reasoning levels are Pro: they multiply the chat model's thinking tokens. Without
# Pro, Auto runs as Medium (free_default_effort).


def require_reasoning_access(uid, reasoning_effort):
    if reasoning_effort in PRO_REASONING_EFFORTS and not _premium_allowed(uid):
        raise HTTPException(status_code=403, detail="High reasoning levels are available on Pro. Choose Auto or a lower level.")


# The account's Linux VM (workspace, live view, restore) only for admins unless AGENT_VM_ACCESS=all
# (agent_vm.open_to_all).
def vm_allowed(uid):
    if agent_vm.open_to_all():
        return True
    try:
        return is_user_admin(uid)
    except TierStatusUnavailable:
        raise HTTPException(
            status_code=503, detail="Account tier is temporarily unavailable. Please retry."
        ) from None


# The user handed the browser back this recently: they just worked in it.
RECENT_HANDBACK_SECONDS = 600


def browser_turn(record):
    """0 while the user has the workspace's browser, the seconds since they handed it back within
    RECENT_HANDBACK_SECONDS, else None."""
    import time
    from app.services import agent_workspace
    has, returned = agent_workspace.control_of(record)
    if has:
        return 0
    ago = time.time() - returned if returned else None
    return ago if ago is not None and 0 <= ago < RECENT_HANDBACK_SECONDS else None


def workspace_turn(uid):
    """(browser_turn, the browser's noted sign-ins) from one read of the record; (None, []) when it
    cannot be read."""
    from app.services import agent_workspace
    try:
        record = agent_workspace.record(db_firestore, uid)
    except Exception as exc:
        logging.warning("Agent workspace browser state unavailable category=%s", safe_exception(exc))
        return None, []
    return browser_turn(record), agent_workspace.sign_ins(record)


def workspace_closed(chat_data, browser):
    """Whether this message starts with only open_workspace. It starts with the tools where the
    chat's last message used the workspace or the user has or just handed back the browser; with the
    browser's state unknown it starts closed."""
    return agent_vm.on_demand() and not chat_data.get("agent_workspace_used") and browser is None


def _memory_snapshot(uid):
    """The user's memory for one turn, fail-open. Never cached across requests: a memory deleted a
    moment ago must not reach the next prompt."""
    try:
        tier = get_user_tier(uid)
    except TierStatusUnavailable:
        tier = None
    return FirestoreAgentMemoryRepository(db_firestore).snapshot(
        uid, max_notes_chars=cfg.get_memory_char_limit(tier))


class AgentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    chat_id: str = Field(pattern=r"^[0-9a-f]{32}$")
    client_request_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
    bookmark_id: str = Field(pattern=r"^[A-Za-z0-9_]{1,100}$")
    question: str
    stream: Literal[True] = True
    recover_only: bool = False
    model_id: str | None = Field(default=None, min_length=1, max_length=160)
    reasoning_effort: str = Field(default="default", pattern=REASONING_EFFORT_PATTERN)
    comparison_models: dict[str, str] | None = Field(default=None, max_length=9)
    # Ignored: pages still open from before the source check's removal keep sending it.
    check_sources: bool = False
    file_ids: list[str] = Field(default_factory=list, max_length=5)
    google_selection: GoogleSelection | None = None
    google_data_consent: bool = False
    # Ignored: the route sets what a message runs with. Older pages keep sending it.
    agent_preferences: dict | None = None
    # The composer's value of the account setting ``reviewers``, kept with the turn but no part of
    # the request's identity, so a turn recovers after the setting changed.
    reviewers: Literal["always", "workspace", "off"] = "always"
    # The browser's IANA zone for the message's date; an unknown name counts as none.
    timezone: str | None = Field(default=None, max_length=64)

    @field_validator("timezone")
    @classmethod
    def known_timezone(cls, value):
        from zoneinfo import ZoneInfo
        try:
            return value if value and ZoneInfo(value) else None
        except Exception:
            return None

    @field_validator("file_ids")
    @classmethod
    def valid_files(cls, value):
        import re
        if len(set(value)) != len(value) or any(not re.fullmatch(r"[a-f0-9]{32}", item) for item in value):
            raise ValueError("Invalid file IDs")
        return value

    @field_validator("question")
    @classmethod
    def valid_question(cls, value):
        return normalize_question(value)


def _save_bookmark(uid, payload, store, turn, *, quiet=False):
    """The chat's sidebar entry after ``turn``. ``quiet``: a Watch's run that found nothing keeps
    the entry where it is."""
    chat = store.get_chat(uid, payload.chat_id)
    if chat["status"] != "active":
        raise ChatNotFound("Chat not found")
    ref = db_firestore.collection("users").document(uid).collection("bookmarks").document(payload.bookmark_id)
    existing = ref.get()
    if existing.exists and (existing.to_dict() or {}).get("chat_id") != payload.chat_id:
        raise TurnStatusConflict("Bookmark belongs to another conversation")
    if quiet and existing.exists:
        return _bookmark_meta(payload.bookmark_id, existing.to_dict())
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
        "timestamp": firestore.SERVER_TIMESTAMP, "sources": [], "attachments": turn.get("attachments", []),
        "previous_question": "", "previous_turn": {}, "share_result_id": "",
        "consensus_model": turn["consensus_model"], "included_providers": [], "model_labels": {},
        "responses": {"consensus": turn.get("consensus", ""), "differences": "", "differences_data": None},
    })
    return _bookmark_meta(payload.bookmark_id, bookmark)


def _temporary(turn):
    """A temporary chat's turn: no sidebar entry is written for it."""
    return (turn.get("agent_settings") or {}).get("temporary") is True


def _quiet_watch_run(turn):
    """A Watch's scheduled run that found nothing: its chat keeps its place in the sidebar."""
    settings = turn.get("agent_settings") or {}
    run = turn.get("agent_watch_run") if isinstance(turn.get("agent_watch_run"), dict) else {}
    return bool(settings.get("watch_run")) and not run.get("finding") and not run.get("done")


def _watch_history_chars():
    from app.services import agent_watches
    return agent_watches.HISTORY_CHARS


def _final(uid, payload, store, turn):
    bookmark_meta = None if _temporary(turn) else _save_bookmark(uid, payload, store, turn,
                                                                quiet=_quiet_watch_run(turn))
    # Whether the next message needs Google consent; a tool may set the chat's marker during this
    # turn.
    settings = turn.get("agent_settings") or {}
    google_data = bool(settings.get("google_data"))
    google_consent = google_data and settings.get("google_data_consent") is True
    if not google_data:
        try:
            chat = store._chat_ref(uid, payload.chat_id).get().to_dict() or {}
            google_data = bool(chat.get("google_data"))
            google_consent = google_data and chat.get("google_consent") is True
        except Exception as exc:
            # A hint for the composer only; the server rule still enforces consent.
            logging.warning("Agent chat Google marker unavailable category=%s", safe_exception(exc))
    final = {"chat_id": payload.chat_id, "turn_id": turn["id"], "turn": turn,
             "response": turn.get("consensus", ""), "execution_mode": "agent", "bookmark_meta": bookmark_meta,
             "google_data": google_data, "google_consent": google_consent, "temporary": _temporary(turn)}
    try:
        final["token_budget"] = agent_quota.snapshot(store.db, uid)
    except Exception as exc:
        # Without it the browser asks for the allowance itself.
        logging.warning("Agent allowance unavailable category=%s", safe_exception(exc))
    return final


def _handover_frame(uid, payload, store, event):
    """The ``handover`` frame: the answer fixed, its review still running, the chat entry saved.
    None when that fails; the final frame follows anyway."""
    try:
        return _final(uid, payload, store, store.get_turn(uid, payload.chat_id, event["turn_id"]))
    except Exception as exc:
        logging.warning("Agent hand-over frame unavailable category=%s", safe_exception(exc))
        return None


def _bookmark_limit_failure(exc):
    """The answer is saved, but the sidebar entry hit a storage cap; freeing space and recovering
    adds it, unless the answer is too large for any entry."""
    if exc.code == "bookmark_too_large":
        return {"error": "This answer is too large to keep in your chats.", "code": exc.code, "recoverable": False}
    return {"error": "Your saved chats are full. Delete an old chat, then recover this answer.",
            "code": exc.code, "recoverable": True, "recovery_state": "saved"}


def _save_interrupted(uid, payload, store, turn_id):
    try:
        turn = store.get_turn(uid, payload.chat_id, turn_id)
    except Exception as exc:
        logging.warning("Interrupted Agent snapshot unavailable category=%s", safe_exception(exc))
        return None
    if turn["status"] == "failed" and not _temporary(turn):
        try:
            # A Watch's failed run moves nothing in the sidebar either.
            turn["bookmark_meta"] = _save_bookmark(uid, payload, store, turn,
                                                   quiet=bool((turn.get("agent_settings") or {}).get("watch_run")))
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


# Reads a new message needs before its turn exists, side by side: one after another, about 25
# Firestore round trips cost 2-3 s before a model saw the question.
_TURN_READS = ThreadPoolExecutor(max_workers=24, thread_name_prefix="agent-turn-read")


def _turn_reads(uid, payload, store):
    """Futures of what run_agent reads for a new message, all started at once and each taken where
    its read belongs, so a failing read fails the request at the same point. The sweep of abandoned
    turns, which may fail a turn, waits for the checks (sweep_after)."""
    from app.services.agent_files import AgentFiles, public_file
    files = AgentFiles(db_firestore)
    chat_id = payload.chat_id
    bookmark = db_firestore.collection("users").document(uid).collection("bookmarks").document(payload.bookmark_id)
    jobs = {
        "turn": lambda: store.chat_and_turn(uid, chat_id, _idempotent_turn_id(chat_id, payload.client_request_id)),
        "recover": lambda: store.recover_allowance(uid),
        "bookmark": bookmark.get,
        "files": lambda: [public_file(files.get(uid, chat_id, fid)) for fid in payload.file_ids],
        "memory": lambda: _memory_snapshot(uid),
        "workspace": lambda: workspace_turn(uid) if vm_allowed(uid) else (None, []),
        # Used only after the turn's creation found the chat live.
        "history": lambda: store.history_page(uid, chat_id, checked=True),
        "catalog": lambda: files.list(uid, chat_id, checked=True),
    }
    return {name: _TURN_READS.submit(job) for name, job in jobs.items()}


def sweep_after(store, uid, chat_id, recover):
    """The sweep of abandoned turns for a message that passed every check, after the reaper and
    beside the route's work."""
    def sweep():
        try:
            recover.result()
        except Exception:
            # The route takes the reaper's failure itself.
            pass
        store.sweep_abandoned_turns(uid, chat_id)
    return _TURN_READS.submit(sweep)


def _first_history_page(read):
    """The history page read beside the turn's creation, None when that failed."""
    try:
        return read.result()
    except Exception as exc:
        logging.warning("Agent history read ahead unavailable category=%s", safe_exception(exc))
        return None


# The allowance for the browser's quota frames, read beside the run so no step's request waits for
# it.
_ALLOWANCE_READS = ThreadPoolExecutor(max_workers=4, thread_name_prefix="agent-allowance")


def quota_frames(allowances, *, wait=False):
    """The quota frames of the reads that are done (all with ``wait``), oldest first; unreadable
    ones left out."""
    while allowances and (wait or allowances[0].done()):
        try:
            yield {"token_budget": allowances.pop(0).result()}
        except Exception as exc:
            logging.warning("Agent allowance unavailable category=%s", safe_exception(exc))


@router.post("/agent")
@limiter.limit("30/minute")
def run_agent(request: Request, payload: AgentRequest):
    return start_agent_turn(_chat_uid(request), payload)


def start_agent_turn(uid, payload: AgentRequest, *, watch_run=None):
    """A message as POST /agent runs it: the turn on its own thread, the response only a tail of its
    frames. ``watch_run``: a Watch's scheduled run with nobody following, noted on the Watch at its
    end."""
    require_agent_access(uid)
    store = AgentRunStore(db_firestore)
    turn = None
    lease = None
    try:
        # A request that only recovers a saved answer reads its turn alone.
        reads = None if payload.recover_only else _turn_reads(uid, payload, store)
        # Read before applying today's configuration: old requests stay replayable after a model,
        # price or key change without another paid call.
        chat_data, existing = (reads["turn"].result() if reads else store.chat_and_turn(
            uid, payload.chat_id, _idempotent_turn_id(payload.chat_id, payload.client_request_id)))
        if existing:
            if existing["question"] != payload.question or existing.get("execution_mode") != "agent":
                raise TurnStatusConflict("Request identity conflicts with another turn")
            selection = {"model_id": payload.model_id, "reasoning_effort": payload.reasoning_effort}
            prior_selection = existing.get("agent_settings", {}).get("selection", {"model_id": None, "reasoning_effort": "default"})
            if existing.get("agent_settings", {}).get("file_ids", []) != payload.file_ids:
                raise TurnStatusConflict("Request identity conflicts with different files")
            previous_google = existing.get("agent_settings", {}).get("google_selection")
            if (GoogleSelection.model_validate(previous_google).model_dump() if previous_google else None) != (payload.google_selection.model_dump() if payload.google_selection else None):
                raise TurnStatusConflict("Request identity conflicts with different Google permissions")
            if existing.get("agent_settings", {}).get("google_data_consent", False) != payload.google_data_consent:
                raise TurnStatusConflict("Request identity conflicts with different Google data consent")
            if prior_selection != selection:
                raise TurnStatusConflict("Request identity conflicts with different agent settings")
            if existing.get("agent_settings", {}).get("comparison_selection") != payload.comparison_models:
                raise TurnStatusConflict("Request identity conflicts with different comparison models")
            # The turn's agent_preferences are the server's, no part of its identity, so an older
            # turn still recovers.
            if payload.recover_only and existing["status"] == "pending":
                # A lost producer has no live stream to close its lease; only expired runs are
                # reaped, never a paid step started.
                store.reap_delegation(uid, payload.chat_id, existing["id"])
                existing = store.get_turn(uid, payload.chat_id, existing["id"])
            if existing["status"] == "completed":
                return _final(uid, payload, store, existing)
            if payload.recover_only and existing["status"] == "failed":
                return _final(uid, payload, store, existing)
            failed = existing["status"] == "failed"
            return JSONResponse({"error": "This run ended without a saved answer. Send a new message to try again." if failed
                else "This request is still running. You can check its saved answer after it finishes.",
                "code": "answer_unavailable" if failed else "request_running", "recoverable": not failed,
                "recovery_state": "unavailable" if failed else "running"}, status_code=409)
        if payload.recover_only:
            return JSONResponse({"error": "No saved answer is available for this request.",
                "code": "answer_unavailable", "recoverable": False}, status_code=404)
        # Only a new turn counts: a browser following a running turn must not use up the send limit.
        # Watches are bounded by their schedule.
        try:
            if watch_run is None:
                api_uid_limiter.check(uid, "agent:turn", 20)
        except ApiUidRateLimitExceeded as exc:
            raise HTTPException(status_code=429, detail="Too many agent requests. Please wait.",
                                headers=exc.headers) from None
        if agent_background.shutting_down:
            raise AgentShuttingDown("The server is restarting. Please send your message again in a moment.")
        if agent_background.running(uid, payload.chat_id, payload.client_request_id):
            return JSONResponse({"error": "This request is still running.", "code": "request_running",
                                 "recoverable": True, "recovery_state": "running"}, status_code=409)
        try:
            effort = payload.reasoning_effort
            if effort == "default" and not _premium_allowed(uid):
                # The request identity and the saved selection keep what the browser sent.
                effort = free_default_effort(payload.model_id) or effort
            model = configured_model(resolve_agent_model(payload.model_id, effort))
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from None
        # None means the preset default, open to every tier; the same model as a comparison model
        # still needs Pro.
        chat_model = [] if model.selection_id == default_agent_model_id() else [model.selection_id]
        require_model_access(uid, [*chat_model, *(payload.comparison_models or {}).values()])
        require_reasoning_access(uid, payload.reasoning_effort)
        # A temporary chat keeps nothing beyond itself: no sidebar entry, memory read but never
        # written, no share; its workspace folder and processes go with it.
        temporary = chat_data.get("temporary") is True
        preferences = AgentPreferences(vm="on" if vm_allowed(uid) else "off")
        key = openrouter_api_key(resolve_developer_api_keys())
        if not key and not mock_llm_enabled():
            raise HTTPException(status_code=503, detail="Agent model is not configured.")
        provider_cooldowns.check(model, key or "")
        reads["recover"].result()
        sweep = sweep_after(store, uid, payload.chat_id, reads["recover"])
        bookmark = reads["bookmark"].result()
        # A temporary chat has no bookmark: its id is the page's and unused.
        if not temporary and bookmark.exists and (bookmark.to_dict() or {}).get("chat_id") != payload.chat_id:
            raise TurnStatusConflict("Bookmark belongs to another conversation")
        from app.services.agent_files import AgentFiles, FileContext
        files = AgentFiles(db_firestore)
        file_meta = reads["files"].result()
        file_context = FileContext(files, uid, payload.chat_id, payload.file_ids)
        file_context.preload(reads["catalog"])
        if payload.google_selection:
            from app.services.google_connections import user_allowed
            if not user_allowed(uid):
                raise HTTPException(403, "Google is not available for this account yet.")
        # Google data enters through a Gmail or Calendar selection or a Drive file; once there, the
        # chat keeps the Google rules.
        drive_files = any(meta.get("kind") == "drive_file" for meta in file_meta)
        google_data = bool(payload.google_selection or drive_files or chat_data.get("google_data"))
        if google_data:
            from app.services.google_connections import restricted_model
            if not payload.google_data_consent:
                raise HTTPException(422, "This chat contains Google information. Review and enable Google model-sharing consent before sending.")
            model = restricted_model(model)
            def mark_google(tx):
                files.guard(uid, payload.chat_id, tx)
                # The consent covers this chat from now on; every request still has to carry it.
                tx.update(store._chat_ref(uid, payload.chat_id), {"google_data": True, "google_consent": True})
            store._transaction(mark_google)
        if payload.google_selection:
            from app.services.google_connections import GoogleConnections, configuration
            configuration()
            connections = GoogleConnections(db_firestore)
            connections.get(uid, payload.google_selection.connection_id, "calendar_read" if payload.google_selection.calendar else None)
            if payload.google_selection.gmail and not {"gmail_read", "gmail_send"} & set(connections.get(uid, payload.google_selection.connection_id)["capabilities"]):
                raise HTTPException(403, "Authorize Gmail for the selected account first.")
        lease = agent_capacity.acquire()
        config = prompt_config.get_config()
        policy = AgentPolicy()
        comparisons = comparison_selection(payload.comparison_models)
        # A temporary chat reads it and writes nothing.
        memory = reads["memory"].result()
        if temporary:
            memory = dataclasses.replace(memory, temporary=True)
        # The turn keeps it, so the next message repeats this question byte for byte (prompt cache).
        app_context = get_agent_turn_context(model, config, payload.timezone)
        # The user restored the VM since the last message: this message's context says so, once.
        restored = (chat_data.get("agent_vm") or {}).get("restored") if preferences.vm == "on" else None
        if isinstance(restored, dict) and not restored.get("told"):
            app_context += "\n" + agent_vm.VM_RESTORED_NOTE
        browser, signed_in = reads["workspace"].result() if preferences.vm == "on" else (None, [])
        if browser:
            app_context += "\n" + agent_vm.HANDED_BACK_NOTE.format(minutes=max(1, round(browser / 60)))
        if signed_in:
            from app.services import agent_workspace
            app_context += "\n" + agent_workspace.sign_ins_note(signed_in)
        if watch_run:
            from app.services import agent_watches
            app_context += "\n" + agent_watches.run_context(watch_run)
        sweep.result()
        turn = store.create_turn(
            uid, payload.chat_id, question=payload.question, mode="Agent", deep_search=False,
            selected_models=[model.model], consensus_model=model.model,
            client_request_id=payload.client_request_id, execution_mode="agent", attachments=file_meta,
            agent_settings={**model.settings(), "policy": policy.snapshot(), "config_revision": config["revision"],
                            "file_ids": payload.file_ids,
                            "google_selection": payload.google_selection.model_dump() if payload.google_selection else None,
                            "google_data_consent": payload.google_data_consent,
                            "google_data": google_data,
                            "comparison_selection": payload.comparison_models,
                            "agent_preferences": preferences.model_dump(),
                            "reviewers": payload.reviewers,
                            **({"temporary": True} if temporary else {}),
                            **({"watch_run": watch_run} if watch_run else {}),
                            "comparison_models": {p: m.snapshot() for p, m in comparisons.items()},
                            "memory": memory.settings(),
                            "answer_mode": "merged",
                            "selection": {"model_id": payload.model_id, "reasoning_effort": payload.reasoning_effort}},
            app_context=app_context, sweep=False, read_back=False,
        )
        if turn["status"] == "completed":
            lease.release()
            return _final(uid, payload, store, store.get_turn(uid, payload.chat_id, turn["id"]))
        if turn.get("chat_google_data") and not google_data:
            # The chat gained Google data after the route first read it (another tab's turn imported
            # mail): its rules hold here too.
            if not payload.google_data_consent:
                raise HTTPException(422, "This chat contains Google information. Review and enable Google model-sharing consent before sending.")
            from app.services.google_connections import restricted_model
            google_data, model = True, restricted_model(model)
        if isinstance(restored, dict) and not restored.get("told"):
            _vm_restore_told(store, uid, payload.chat_id)
        chat_sources = []
        # A long history is summarized in the run's first step.
        history_summary = {}
        messages = store.messages(uid, payload.chat_id, turn, model=model, config=config, sources=chat_sources,
                                  context=app_context, first_page=_first_history_page(reads["history"]),
                                  history_chars=_watch_history_chars() if watch_run else None,
                                  summary=history_summary)
        cancellation = ProviderCancellation()
        loop = AgentLoop(store=store, uid=uid, chat_id=payload.chat_id, turn_id=turn["id"],
                         model=model, messages=messages, api_key=key or "", cancellation=cancellation,
                         completion_factory=AgentCompletion, policy=policy, file_context=file_context,
                         google_selection=payload.google_selection,
                         google_data_consent=payload.google_data_consent, google_data=google_data,
                         cooldowns=provider_cooldowns,
                         comparison_models=comparisons, agent_preferences=preferences, memory=memory,
                         chat_sources=chat_sources, reviewers=payload.reviewers, temporary=temporary,
                         watch_run=watch_run, history_summary=history_summary or None,
                         workspace_closed=preferences.vm == "on" and workspace_closed(chat_data, browser),
                         mock_answer="Agent test answer: " + payload.question if mock_llm_enabled() else None)
        if loop.vm_tools is not None:
            # A new account's workspace is made while it talks to the agent.
            from app.services import agent_workspace
            agent_workspace.provision(store, uid)
        # Every view follows the run through this buffer.
        live, live_owned = agent_live.acquire(uid, payload.chat_id, payload.client_request_id)
    except Exception as exc:
        try:
            if turn:
                store.release_unclaimed(uid, payload.chat_id, turn["id"], failure=agent_failure(exc))
                _save_interrupted(uid, payload, store, turn["id"])
        finally:
            if lease:
                lease.release()
        if isinstance(exc, HTTPException):
            raise
        if isinstance(exc, AgentProviderCooldown):
            raise HTTPException(status_code=429, detail=str(exc), headers={"Retry-After": str(exc.retry_after)}) from None
        if isinstance(exc, (AgentCapacityExceeded, AgentShuttingDown)):
            raise HTTPException(status_code=503, detail=str(exc), headers={"Retry-After": "5"}) from None
        if isinstance(exc, ValueError):
            raise HTTPException(status_code=422, detail=str(exc)) from None
        if isinstance(exc, persistence_guard.PersistenceLimitError):
            # Recovering a finished answer whose bookmark does not fit.
            return JSONResponse(_bookmark_limit_failure(exc), status_code=409)
        _raise_store_error(exc, operation="prepare agent turn", uid=uid)

    def pack(event_type, data):
        # One sequence per run for the SSE id and the live replay, so the browser drops frames it
        # already applied from a poll.
        seq, text = agent_live.record(live, event_type, data)
        return f"id: {seq}\nevent: {event_type}\ndata: {text}\n\n"

    def events():
        completion = loop.completion
        status = "failed"
        error = "The agent response could not be completed. Please try a new message."
        failure = {}
        # The allowance after a step, sent with the next frame once read.
        allowances = []
        try:
            # A durable identity while admission is still waiting, so Stop and status do not depend
            # on a paid call starting.
            yield pack("accepted", {"chat_id": payload.chat_id, "turn_id": turn["id"]})
            source = loop.run()
            closing = False
            try:
                for event in source:
                    if event and event["type"] == "handover":
                        # The answer stands and the chat is free: the browser takes it like a final
                        # answer, its review follows.
                        handed = _handover_frame(uid, payload, store, event)
                        if handed:
                            yield pack("handover", handed)
                    elif event:
                        yield pack(event["type"], event)
                        if event["type"] == "started" or (event["type"] == "activity" and event.get("kind") == "usage"):
                            allowances.append(_ALLOWANCE_READS.submit(agent_quota.snapshot, store.db, uid))
                    for frame in quota_frames(allowances):
                        yield pack("quota", frame)
                for frame in quota_frames(allowances, wait=True):
                    yield pack("quota", frame)
            except GeneratorExit:
                closing = True
                raise
            finally:
                try:
                    source.close()
                except Exception as exc:
                    if not closing:
                        raise
                    # An account tombstone can refuse settlement during close. Preserve
                    # GeneratorExit: an error frame now would violate the generator protocol and
                    # strand the producer.
                    logging.warning("Agent stream cleanup unavailable category=%s", safe_exception(exc))
            status = "succeeded"
        except GeneratorExit:
            # The producer itself closed the stream (the run is not tied to a connection). No frame
            # may follow.
            status = "cancelled"
            if not loop.claimed:
                store.release_unclaimed(uid, payload.chat_id, turn["id"], failure={
                    "code": "cancelled", "error": "Response stopped before a model call started."})
            _save_interrupted(uid, payload, store, turn["id"])
            raise
        except ProviderCancelled:
            # Stop: the loop has settled and saved; tell every view still following the run.
            status = "cancelled"
            error = "This response was stopped."
            failure = {"code": "cancelled"}
            if (getattr(completion, "failure", None) or {}).get("code") == "hold_timeout":
                # A pause nobody decided: said so.
                error, failure = completion.failure["error"], {"code": "hold_timeout"}
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
            logging.warning("Agent completion failed category=%s model=%s code=%s retry_after=%s detail=%s where=%s",
                            safe_exception(exc), model.model, failure["code"], failure.get("retry_after"),
                            provider_diagnostic(exc), safe_traceback(exc))
            # Provider errors land here routinely; only a programming error is reported.
            report_server_exception(exc, where="agent.turn_stream")
        if status != "succeeded":
            for event in loop._events():
                yield pack(event["type"], event)
            interrupted = _save_interrupted(uid, payload, store, turn["id"])
            if interrupted is not None:
                pending = interrupted["status"] == "pending"
                failure["recoverable"] = True
                failure["recovery_state"] = "running" if pending else "saved"
                # A temporary chat's answer has no sidebar entry but is saved with its turn.
                if interrupted.get("bookmark_meta") or _temporary(interrupted):
                    saved = dict(interrupted)
                    bookmark_meta = saved.pop("bookmark_meta", None)
                    failure["saved_answer"] = {"chat_id": payload.chat_id, "turn_id": saved["id"],
                        "turn": saved, "response": saved.get("consensus", ""), "bookmark_meta": bookmark_meta,
                        "temporary": _temporary(saved)}
            if interrupted and interrupted.get("agent_review"):
                yield pack("review", {"review": interrupted["agent_review"]})
            yield pack("activity", {"version": 1, "step_id": "run", "id": "run/usage", "kind": "usage", "usage": completion.usage})
            try:
                failure["token_budget"] = agent_quota.snapshot(store.db, uid)
            except Exception as exc:
                logging.warning("Agent allowance unavailable category=%s", safe_exception(exc))
            yield pack("error", {"error": error, **failure})
            return
        try:
            completed = store.get_turn(uid, payload.chat_id, turn["id"])
            yield pack("final", _final(uid, payload, store, completed))
        except persistence_guard.PersistenceLimitError as exc:
            refused = _bookmark_limit_failure(exc)
            logging.warning("Agent bookmark refused code=%s", refused["code"])
            yield pack("error", refused)
        except Exception as exc:
            logging.warning("Agent bookmark failed category=%s", safe_exception(exc))
            yield pack("error", {"error": "The answer was saved, but it couldn’t be added to your chats. Recover the saved answer to reopen it.",
                                 "code": "bookmark_unavailable", "recoverable": True, "recovery_state": "saved"})

    def produce():
        # The whole run on its own thread: every frame goes into the live buffer, nothing waits for
        # a reader.
        try:
            if not lease.start():
                return
            for _frame in events():
                pass
        finally:
            # Capacity first: whoever sees the run end may start the next.
            lease.release()
            agent_live.finish(live)
            if watch_run:
                from app.services import agent_watches
                agent_watches.turn_ended(uid, payload.chat_id, turn["id"], watch_run)

    if not live_owned:
        # Another request of this identity made the buffer and starts this turn's run. Never this
        # one: its start could come first, and the maker's duplicate refusal would discard the
        # buffer it fed.
        lease.release()
        return JSONResponse({"error": "This request is still running.", "code": "request_running",
                             "recoverable": True, "recovery_state": "running"}, status_code=409)

    def interrupt(reason):
        # Shutdown: the saved turn says why it is incomplete instead of a plain Stop.
        loop.watch_error = reason
        cancellation.cancel()

    try:
        agent_background.start(uid=uid, chat_id=payload.chat_id, request_id=payload.client_request_id,
                               turn_id=turn["id"], target=produce, cancel=cancellation.cancel, interrupt=interrupt,
                               loop=loop)
    except AgentRunDuplicate as exc:
        # Two identical requests at once: the first one runs this turn.
        lease.release()
        agent_live.discard(live)
        return JSONResponse({"error": str(exc), "code": "request_running", "recoverable": True,
                             "recovery_state": "running"}, status_code=409)
    except Exception as exc:
        try:
            agent_live.finish(live)
            failure = ({"code": "cancelled", "error": str(exc)} if isinstance(exc, AgentRunStopped)
                       else {"code": "run_interrupted", "error": str(exc)} if isinstance(exc, AgentShuttingDown)
                       else agent_failure(exc))
            store.release_unclaimed(uid, payload.chat_id, turn["id"], failure=failure)
            _save_interrupted(uid, payload, store, turn["id"])
        finally:
            lease.release()
        if isinstance(exc, AgentRunStopped):
            return JSONResponse({"error": str(exc), "code": "cancelled", "recoverable": False}, status_code=409)
        if isinstance(exc, AgentShuttingDown):
            raise HTTPException(status_code=503, detail=str(exc), headers={"Retry-After": "5"}) from None
        raise

    return AgentStreamingResponse(
        agent_live.tail_sse(live, lead=SSE_PADDING), lease=lease,
        media_type="text/event-stream", headers={**SSE_HEADERS, "Cache-Control": "private, no-store, no-transform"},
    )


@router.get("/agent/chats/{chat_id}/turns/{turn_id}/agents")
@limiter.limit("120/minute")
def list_agents(request: Request, chat_id: str, turn_id: str):
    return _agent_details(request, chat_id, turn_id)


@router.get("/agent/chats/{chat_id}/turns/{turn_id}/agents/{agent_id}")
@limiter.limit("120/minute")
def agent_details(request: Request, chat_id: str, turn_id: str, agent_id: str,
                  after: int = Query(0, ge=0, le=MAX_AFTER), limit: int = Query(25, ge=1, le=50)):
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


@router.get("/agent/chats/{chat_id}/turns/{turn_id}/work-log")
@limiter.limit("120/minute")
def agent_work_log(request: Request, chat_id: str, turn_id: str,
                   after: int = Query(0, ge=0, le=MAX_AFTER), limit: int = Query(100, ge=1, le=200)):
    """The turn's work log after entry ``after``, only for its owner. Long contents come shortened
    (``ref``); the entry endpoint returns one whole."""
    uid = _chat_uid(request)
    require_agent_access(uid)
    try:
        data = AgentRunStore(db_firestore).read_work_log(uid, chat_id, turn_id, after=after, limit=limit)
        return JSONResponse(data, headers={"Cache-Control": "private, no-store"})
    except Exception as exc:
        _raise_store_error(exc, operation="read agent work log", uid=uid)


@router.get("/agent/chats/{chat_id}/turns/{turn_id}/work-log/{seq}")
@limiter.limit("120/minute")
def agent_work_log_entry(request: Request, chat_id: str, turn_id: str, seq: int):
    uid = _chat_uid(request)
    require_agent_access(uid)
    if not 1 <= seq <= 999_999:
        raise HTTPException(status_code=404, detail="Not found")
    try:
        data = AgentRunStore(db_firestore).work_log_entry(uid, chat_id, turn_id, seq)
        return JSONResponse(data, headers={"Cache-Control": "private, no-store"})
    except Exception as exc:
        _raise_store_error(exc, operation="read agent work log entry", uid=uid)


@router.get("/agent/chats/{chat_id}/live")
@limiter.limit("120/minute")
def agent_live_events(request: Request, chat_id: str,
                      request_id: str = Query(..., min_length=1, max_length=128, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$"),
                      after: int = Query(0, ge=0, le=MAX_AFTER)):
    """The running stream's frames after ``after``, for networks that buffer SSE. Process memory
    only: ``known: false`` means this process holds no such stream. Keyed by the caller's uid, so
    another account can never address it."""
    uid = _chat_uid(request)
    require_agent_access(uid)
    if not re.fullmatch(r"[0-9a-f]{32}", chat_id):
        raise HTTPException(status_code=404, detail="Chat not found")
    return JSONResponse(agent_live.read(uid, chat_id, request_id, after),
                        headers={"Cache-Control": "private, no-store"})


@router.post("/agent/chats/{chat_id}/turns/{turn_id}/stop")
@limiter.limit("30/minute")
def stop_agent_run(request: Request, chat_id: str, turn_id: str):
    uid = _chat_uid(request)
    require_agent_access(uid)
    try:
        # This process runs it: cancel at once. The saved flag stops it wherever it runs.
        agent_background.stop(uid, chat_id, turn_id=turn_id)
        AgentRunStore(db_firestore).stop_delegation(uid, chat_id, turn_id)
        return JSONResponse({"status": "stopping"}, headers={"Cache-Control": "private, no-store"})
    except Exception as exc:
        _raise_store_error(exc, operation="stop agent sessions", uid=uid)


@router.post("/agent/chats/{chat_id}/turns/{turn_id}/share-result")
@limiter.limit("10/minute")
def prepare_agent_share(request: Request, chat_id: str, turn_id: str):
    """The pending share result of one finished Agent answer (any of the chat's); POST /api/share
    publishes it. Sharing needs no Agent quota."""
    uid = _chat_uid(request)
    if not re.fullmatch(r"[0-9a-f]{32}", chat_id) or not re.fullmatch(r"[0-9a-f]{32}", turn_id):
        raise HTTPException(status_code=404, detail="This chat no longer exists.")
    return JSONResponse(prepare_agent_share_result(uid, chat_id, turn_id),
                        headers={"Cache-Control": "private, no-store"})


def _vm_restore_told(store, uid, chat_id):
    """The next message carries the restore in its context: told once."""
    ref = store._chat_ref(uid, chat_id)

    def operation(tx):
        record = dict((ref.get(transaction=tx).to_dict() or {}).get("agent_vm") or {})
        if isinstance(record.get("restored"), dict):
            tx.update(ref, {"agent_vm": {**record, "restored": {**record["restored"], "told": True}}})
    try:
        store._transaction(operation)
    except Exception as exc:
        logging.warning("Agent VM restore note not marked category=%s", safe_exception(exc))


def _refuse_closed_workspace(uid):
    """403 while workspace_guard has closed the account's workspace: nothing wakes or writes its VMs
    then."""
    from app.services import workspace_guard
    guard = workspace_guard.status(uid)
    if guard.closed:
        raise HTTPException(status_code=403, detail=workspace_guard.user_text(guard))


@router.post("/agent/chats/{chat_id}/turns/{turn_id}/vm-restore")
@limiter.limit("10/minute")
def restore_agent_vm(request: Request, chat_id: str, turn_id: str):
    """Return the workspace to the checkpoint taken before this message. Never while a response runs
    in the chat; the next message is told."""
    uid = _chat_uid(request)
    require_agent_access(uid)
    if not vm_allowed(uid):
        raise HTTPException(status_code=403, detail="The workspace is not available on your account.")
    _refuse_closed_workspace(uid)
    if not re.fullmatch(r"[0-9a-f]{32}", chat_id) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", turn_id):
        raise HTTPException(status_code=404, detail="Message not found")
    store = AgentRunStore(db_firestore)
    try:
        turn = store.get_turn(uid, chat_id, turn_id)
        chat = store._chat_ref(uid, chat_id).get().to_dict() or {}
    except ChatNotFound:
        raise HTTPException(status_code=404, detail="Message not found") from None
    except Exception as exc:
        _raise_store_error(exc, operation="read agent vm restore", uid=uid)
    checkpoint = (turn.get("agent_vm") or {}).get("checkpoint")
    if not checkpoint:
        return JSONResponse({"error": "This message has no saved workspace to go back to.", "code": "no_checkpoint"},
                            status_code=409)
    lock = chat.get("agent_lock_until")
    from app.services import agent_workspace
    workspace = agent_workspace.record(db_firestore, uid)
    # Only a recent checkpoint of this account's workspace taken after the last sign-out everywhere
    # or chat deletion.
    if not agent_workspace.restorable(workspace, turn.get("agent_vm")):
        return JSONResponse({"error": "The workspace can no longer go back to before this message.", "code": "expired"},
                            status_code=409)
    # No chat's message may be using the workspace, also not one whose lease ran out while its
    # response runs.
    if turn.get("status") == "pending" or (isinstance(lock, datetime) and lock > datetime.now(timezone.utc)) or \
            agent_workspace.in_use(store, uid):
        return JSONResponse({"error": "Wait until the response is done, then restore the workspace.", "code": "running"},
                            status_code=409)
    try:
        agent_vm.restore_workspace(uid, checkpoint)
    except agent_vm.VMUnavailable as exc:
        logging.warning("Agent VM restore unavailable category=%s", safe_exception(exc))
        return JSONResponse({"error": "The workspace could not be restored right now. Try again later.",
                             "code": "vm_unavailable"}, status_code=503)
    ref = store._chat_ref(uid, chat_id)

    def record(tx):
        current = dict((ref.get(transaction=tx).to_dict() or {}).get("agent_vm") or {})
        tx.update(ref, {"agent_vm": {**current, "restored": {"checkpoint": checkpoint, "turn_id": turn_id,
                                                             "at": datetime.now(timezone.utc).isoformat()}}})
    try:
        store._transaction(record)
        # The other chats' next messages in the workspace are told too.
        if (chat.get("agent_vm") or {}).get("workspace"):
            agent_workspace.mark_restored(store, uid)
    except Exception as exc:
        # Restored all the same; only the next message's note is missing.
        logging.warning("Agent VM restore not recorded category=%s", safe_exception(exc))
    return JSONResponse({"status": "restored", "checkpoint": checkpoint}, headers={"Cache-Control": "private, no-store"})


class AgentNoteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    text: str = Field(min_length=1, max_length=4000)


@router.post("/agent/chats/{chat_id}/requests/{request_id}/notes")
@limiter.limit("30/minute")
def add_agent_note(request: Request, chat_id: str, request_id: str, payload: AgentNoteRequest):
    """A message into the running response by the browser's request identity; the run takes it
    before its next step."""
    uid = _chat_uid(request)
    require_agent_access(uid)
    if not re.fullmatch(r"[0-9a-f]{32}", chat_id) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}", request_id):
        raise HTTPException(status_code=404, detail="Request not found")
    text = payload.text.strip()
    if not text:
        raise HTTPException(status_code=422, detail="Write a message first.")
    try:
        store = AgentRunStore(db_firestore)
        turn_id = _idempotent_turn_id(chat_id, request_id)
        try:
            turn = store.get_turn(uid, chat_id, turn_id)
        except ChatNotFound:
            turn = None
        if not turn or turn.get("status") != "pending":
            return JSONResponse({"error": "This response is no longer running. Send your message as a new one.",
                                 "code": "not_running"}, status_code=409)
        if ((turn.get("agent_settings") or {}).get("agent_preferences") or {}).get("vm") != "on":
            return JSONResponse({"error": "Messages during a response need the workspace.", "code": "notes_unavailable"},
                                status_code=409)
        note = store.add_user_note(uid, chat_id, turn_id, text)
        loop = agent_background.run_loop(uid, chat_id, request_id)
        if loop is not None:
            # This process runs it: the run has it at once.
            loop.receive({"user_notes": [note]})
        return JSONResponse({"status": "added", "id": note["id"]}, headers={"Cache-Control": "private, no-store"})
    except TurnStatusConflict as exc:
        return JSONResponse({"error": str(exc), "code": "not_running"}, status_code=409)
    except Exception as exc:
        _raise_store_error(exc, operation="add agent note", uid=uid)


def _decide_hold(store, uid, chat_id, request_id, turn_id, hold_id, action, text="", choice=None):
    """The user's decision on the open hold, saved on the run's root and handed at once to a run in
    this process. A hold whose save failed is known only to its run, which takes the decision
    itself. Raises as decide_hold when neither knows it open."""
    loop = agent_background.run_loop(uid, chat_id, request_id)
    try:
        saved = store.decide_hold(uid, chat_id, turn_id, hold_id, action, text, choice)
    except NotesFull:
        raise
    except TurnStatusConflict:
        if loop is None or not loop.decide_unsaved(hold_id, action, text, choice):
            raise
        return
    if loop is not None:
        loop.receive(saved)


class AgentHoldDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    id: str = Field(pattern=r"^[0-9a-f]{12}$")
    # "deny": for the agent's own question, 422 elsewhere. "choose": an answer of the agent's
    # choice card by its index in ``choice``.
    action: Literal["continue", "stop", "steer", "deny", "choose"]
    text: str = Field(default="", max_length=4000)
    choice: Optional[int] = Field(default=None, ge=0, le=9)


@router.post("/agent/chats/{chat_id}/requests/{request_id}/hold")
@limiter.limit("30/minute")
def decide_agent_hold(request: Request, chat_id: str, request_id: str, payload: AgentHoldDecision):
    """The user's decision on a paused response: go on, stop, or go on with a message to the agent,
    which learns only of the message. On the agent's own question "continue" allows its step and
    "deny" does not."""
    uid = _chat_uid(request)
    require_agent_access(uid)
    if not re.fullmatch(r"[0-9a-f]{32}", chat_id) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}", request_id):
        raise HTTPException(status_code=404, detail="Request not found")
    text = payload.text.strip()
    if payload.action == "steer" and not text:
        raise HTTPException(status_code=422, detail="Write what the agent should do instead.")
    try:
        store = AgentRunStore(db_firestore)
        turn_id = _idempotent_turn_id(chat_id, request_id)
        try:
            turn = store.get_turn(uid, chat_id, turn_id)
        except ChatNotFound:
            turn = None
        if not turn or turn.get("status") != "pending":
            return JSONResponse({"error": "This response is no longer running.", "code": "not_running"}, status_code=409)
        try:
            _decide_hold(store, uid, chat_id, request_id, turn_id, payload.id, payload.action, text, payload.choice)
        except NotesFull as exc:
            # Nothing decided: the card stays for another answer.
            return JSONResponse({"error": str(exc), "code": "notes_full"}, status_code=409)
        except HoldActionRefused as exc:
            # "deny" on a pause it is no answer to.
            return JSONResponse({"error": str(exc), "code": "invalid_action"}, status_code=422)
        except TurnStatusConflict as exc:
            return JSONResponse({"error": str(exc), "code": "hold_over"}, status_code=409)
        if payload.action == "stop" and not agent_background.stop(uid, chat_id, request_id=request_id):
            store.stop_delegation(uid, chat_id, turn_id)
        return JSONResponse({"status": "decided"}, headers={"Cache-Control": "private, no-store"})
    except HTTPException:
        raise
    except Exception as exc:
        _raise_store_error(exc, operation="decide agent hold", uid=uid)


class AgentSecret(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    id: str = Field(pattern=r"^[0-9a-f]{12}$")
    value: str = Field(min_length=1, max_length=agent_secrets.VALUE_CHARS)


@router.post("/agent/chats/{chat_id}/requests/{request_id}/secret")
@limiter.limit("10/minute")
def save_agent_secret(request: Request, chat_id: str, request_id: str, payload: AgentSecret):
    """The key the agent asked for, written into the workspace as the agent's user before the card is
    answered. It goes into no turn, log or model context: the agent hears the file's path."""
    uid = _chat_uid(request)
    require_agent_access(uid)
    if not re.fullmatch(r"[0-9a-f]{32}", chat_id) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}", request_id):
        raise HTTPException(status_code=404, detail="Request not found")
    if not payload.value.strip():
        raise HTTPException(status_code=422, detail="Paste the key first.")
    _refuse_closed_workspace(uid)
    try:
        store = AgentRunStore(db_firestore)
        turn_id = _idempotent_turn_id(chat_id, request_id)
        try:
            turn = store.get_turn(uid, chat_id, turn_id)
        except ChatNotFound:
            turn = None
        if not turn or turn.get("status") != "pending":
            return JSONResponse({"error": "This response is no longer running.", "code": "not_running"}, status_code=409)
        hold = store.open_hold(uid, chat_id, turn_id)
        if not hold:
            # Its save failed: only this process's run knows it.
            loop = agent_background.run_loop(uid, chat_id, request_id)
            hold = loop.unsaved_hold() if loop is not None else None
        name = str((hold or {}).get("secret") or "")
        if not hold or hold.get("id") != payload.id or hold.get("ask") != "secret" or not agent_secrets.NAME.fullmatch(name):
            return JSONResponse({"error": "This question is already over.", "code": "hold_over"}, status_code=409)
        vm = agent_vm.backend()
        if vm is None:
            return JSONResponse({"error": "Your workspace is not reachable right now. Try again.",
                                 "code": "vm_unavailable"}, status_code=503)
        try:
            agent_secrets.save(vm, uid, name, payload.value, ProviderCancellation(), db=db_firestore)
        except agent_vm.VMUnavailable as exc:
            logging.warning("Agent secret not saved category=%s", safe_exception(exc))
            return JSONResponse({"error": "Your workspace is not reachable right now. Try again.",
                                 "code": "vm_unavailable"}, status_code=503)
        finally:
            vm.close()
        try:
            _decide_hold(store, uid, chat_id, request_id, turn_id, payload.id, "continue")
        except TurnStatusConflict as exc:
            return JSONResponse({"error": str(exc), "code": "hold_over"}, status_code=409)
        return JSONResponse({"status": "saved", "path": agent_secrets.path(name)},
                            headers={"Cache-Control": "private, no-store"})
    except HTTPException:
        raise
    except Exception as exc:
        _raise_store_error(exc, operation="save agent secret", uid=uid)


@router.post("/agent/chats/{chat_id}/requests/{request_id}/stop")
@limiter.limit("30/minute")
def stop_agent_request(request: Request, chat_id: str, request_id: str):
    """Stop a message by the browser's request identity. Works before the browser knows the turn id,
    and a Stop that overtakes its own POST keeps it from starting."""
    uid = _chat_uid(request)
    require_agent_access(uid)
    if not re.fullmatch(r"[0-9a-f]{32}", chat_id) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}", request_id):
        raise HTTPException(status_code=404, detail="Request not found")
    if agent_background.stop(uid, chat_id, request_id=request_id):
        return JSONResponse({"status": "stopping"}, headers={"Cache-Control": "private, no-store"})
    try:
        store = AgentRunStore(db_firestore)
        turn_id = _idempotent_turn_id(chat_id, request_id)
        try:
            turn = store.get_turn(uid, chat_id, turn_id)
        except ChatNotFound:
            turn = None
        if turn and turn.get("status") == "pending":
            store.stop_delegation(uid, chat_id, turn_id)
        return JSONResponse({"status": "stopping" if turn and turn.get("status") == "pending" else "not_running"},
                            headers={"Cache-Control": "private, no-store"})
    except Exception as exc:
        _raise_store_error(exc, operation="stop agent request", uid=uid)

import os
import contextlib
import time
import logging
import re
import hashlib
import hmac
from copy import deepcopy
from dataclasses import dataclass
from typing import Optional

from fastapi import APIRouter, Request, Body, HTTPException
from fastapi.responses import StreamingResponse
from google.api_core.exceptions import Aborted as FirestoreAborted

from app.core.rate_limit import limiter
from app.core.observability import record_metric, safe_exception, safe_traceback
from app.core.entitlements import TIER_FREE, entitlements_for
from app.core.security import (
    TierStatusUnavailable,
    db_firestore,
    extract_id_token,
    get_user_tier,
    verify_user_token,
)
import app.core.config as cfg
from app.services.llm.attachments import parse_attachments
from app.services.llm.base import (
    build_followup_system_prompt,
    count_words,
    get_system_prompt,
    validate_model,
)
from app.services.llm.engines import query_model
from app.services.llm.citations import coerce_text, source_response
from app.services.llm.credentials import openrouter_api_key, resolve_developer_api_keys
from app.services.llm.mock_llm import mock_ask_result, mock_ask_stream, mock_llm_enabled
from app.services.llm.provider_runtime import ProviderCancelled
from app.services.llm.streaming import (
    SSE_HEADERS,
    keepalive_streaming_response,
    sse_pack,
    streaming_model_response,
    stream_model_query,
)
from app.services.llm.consensus_engine import (
    CONSENSUS_INCOMPLETE_TEXT,
    DIFFERENCES_SKIPPED_TEXT,
    is_consensus_error_text,
    normalize_model_name,
    query_consensus,
    query_differences,
    stream_consensus,
    stream_differences,
)
from app.services.llm.resolve_engine import (
    InvalidResolvePayload,
    normalize_resolve_positions,
    run_resolve_round,
)
from app.services.share_snapshots import (
    persist_pending_result,
    sanitize_differences_data,
    sanitize_model_labels,
    sanitize_sources,
)
from app.services.chat_store import (
    ChatNotFound,
    ChatStore,
    ChatStoreError,
    TurnQuestionConflict,
    TurnStatusConflict,
)
from app.services.chat_context import (
    ChatContextConflict,
    ChatContextError,
    ChatContextNotFound,
    ChatContextService,
    FirestoreChatContextRepository,
    ResolvedContextCache,
    build_chat_context_system_prompt,
    resolved_context_cache_key,
)
from app.services import answer_receipts, persistence_guard, user_memory
from app.services.llm import completion
from app.services.user_memory import FirestoreUserMemoryRepository
from app.services.differences_stats import record_differences_stats
from app.services import agent_quota
from app.services.run_metering import OperationBooking, metered_events
from app.services.usage_repository import (
    FirestoreUsageRepository,
    RunKind,
    RunStatus,
    TokenAdmission,
    UsageCapacityExceeded,
    UsageLimitExceeded,
    UsageRunExpired,
    UsageRunConflict,
    UsageOperationConflict,
    UsageRunReleased,
    UsageTransitionError,
    canonical_request_fingerprint,
)
from app.services.consensus_pipeline import analyze_provider_answers
from app.services.llm.provider_runtime import analysis_budgeted

router = APIRouter()

OWN_KEYS_LOGIN_REQUIRED = "Please log in to use your own API keys."
MAX_QUESTION_CHARS = 8_000
MAX_QUESTION_BYTES = 16_000
MAX_SYSTEM_PROMPT_CHARS = 12_000
MAX_SYSTEM_PROMPT_BYTES = 32_000
run_usage_repository = FirestoreUsageRepository(db_firestore)
chat_store = ChatStore(db_firestore)
answer_receipt_store = answer_receipts.ReceiptStore(db_firestore)
chat_context_service = ChatContextService(FirestoreChatContextRepository(db_firestore))
resolved_context_cache = ResolvedContextCache()
user_memory_repository = FirestoreUserMemoryRepository(db_firestore)
_CHAT_DOCUMENT_ID_RE = re.compile(r"[0-9a-f]{32}")


def ledger_tier(uid: str, tier) -> str:
    """Tier key of the shared token account (admin role first)."""
    try:
        return agent_quota.account_tier(uid, tier)
    except TierStatusUnavailable:
        raise HTTPException(
            status_code=503,
            detail="Account tier is temporarily unavailable. Please retry.",
        ) from None


def token_admission_for(uid: str, tier, *, deep_think: bool, mode=None) -> TokenAdmission:
    try:
        return run_usage_repository.admission(ledger_tier(uid, tier), mode=mode, deep_think=deep_think)
    except HTTPException:
        raise
    except Exception as exc:
        logging.error("Token budget configuration unavailable category=%s", safe_exception(exc))
        raise HTTPException(status_code=503, detail={
            "error": "Usage accounting is temporarily unavailable. Please retry this run.",
            "error_code": "usage_storage_busy",
        }) from None


def get_usage_run_key(data: dict) -> str:
    value = data.get("usage_run_key")
    if not isinstance(value, str) or not value.strip():
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Missing usage_run_key. Start the run via /prepare.",
                "error_code": "usage_run_key_required",
            },
        )
    return value.strip()


def usage_run_fingerprint(
    data: dict,
    *,
    question: str,
    deep_think: bool,
    purpose: Optional[str] = None,
) -> str:
    """Bind a usage run to the logical fields known before the fan-out."""
    fingerprint_input = {
        "schema": 1,
        "question": question,
        "deep_think": bool(deep_think),
    }
    if purpose is not None:
        fingerprint_input["purpose"] = str(purpose)
    return canonical_request_fingerprint(fingerprint_input)


def usage_response_fields(token_budget, tier) -> dict:
    entitlements = entitlements_for(tier)
    fields = {
        # is_pro_user bleibt das Modell-/Deep-Think-Flag (Plus -> False);
        # "tier" ist die vollstaendige Stufe fuer die UI.
        "is_pro_user": entitlements.is_pro,
        "tier": entitlements.tier,
    }
    if token_budget:
        fields["token_budget"] = token_budget
    return fields


def own_key_usage_fields(tier) -> dict:
    """Own keys are paid by the user: no account, no token_budget."""
    entitlements = entitlements_for(tier)
    return {"is_pro_user": entitlements.is_pro, "tier": entitlements.tier, "usage": "own_keys"}


def _token_limit_detail(exc: UsageLimitExceeded, tier) -> dict:
    detail = usage_response_fields(exc.token_budget, tier)
    detail.update({
        "error": (
            "Today's token allowance does not cover another run. "
            "It resets at 00:00 UTC."
        ),
        "error_code": "token_budget_exhausted",
        "required_tokens": exc.required,
    })
    return detail


def _usage_storage_busy(message="Usage accounting is temporarily busy. Please retry this run."):
    return HTTPException(status_code=503, detail={
        "error": message, "error_code": "usage_storage_busy",
    })


def reserve_usage_run(
    uid: str,
    data: dict,
    *,
    tier,
    deep_think: bool,
    purpose: Optional[str] = None,
    mode=None,
):
    key = get_usage_run_key(data)
    kind = RunKind.DEEP_THINK if deep_think else RunKind.REGULAR
    admission = token_admission_for(uid, tier, deep_think=deep_think, mode=mode)
    try:
        result = run_usage_repository.reserve(
            uid,
            key,
            kind,
            admission,
            request_fingerprint=usage_run_fingerprint(
                data,
                question=str(data.get("question") or "").strip(),
                deep_think=deep_think,
                purpose=purpose,
            ),
        )
    except UsageLimitExceeded as exc:
        raise HTTPException(status_code=403, detail=_token_limit_detail(exc, tier)) from None
    except UsageCapacityExceeded:
        raise HTTPException(status_code=429, detail={
            "error": "Too many runs are starting at once. Please wait for one to finish.",
            "error_code": "usage_run_capacity",
        }) from None
    except UsageRunConflict as exc:
        raise HTTPException(
            status_code=409,
            detail={"error": str(exc), "error_code": "usage_run_conflict"},
        ) from None
    except UsageRunExpired as exc:
        raise HTTPException(
            status_code=409,
            detail={"error": str(exc), "error_code": "usage_run_expired"},
        ) from None
    except FirestoreAborted:
        raise _usage_storage_busy() from None
    if result.status is RunStatus.RELEASED:
        raise HTTPException(
            status_code=409,
            detail={
                "error": "This usage run was already released. Start a new run.",
                "error_code": "usage_run_released",
            },
        )
    return key, result, admission


def consume_usage_run(uid: str, key: str):
    try:
        return run_usage_repository.consume(uid, key)
    except UsageTransitionError as exc:
        raise HTTPException(
            status_code=409,
            detail={"error": str(exc), "error_code": "usage_run_transition"},
        ) from None
    except FirestoreAborted:
        raise _usage_storage_busy() from None


def current_token_budget(uid: str, result, admission) -> Optional[dict]:
    """The account after an authorization: from the transaction if it admitted
    a run, else one plain read. A failed read only omits the field."""
    if result is not None and result.token_budget:
        return result.token_budget
    try:
        return run_usage_repository.token_budget(uid, admission)
    except Exception as exc:
        logging.warning("Token budget read failed category=%s", safe_exception(exc))
        return None


def authorize_usage_operation(
    uid: str, data: dict, operation: str, request_payload: dict,
    *, tier, deep_think: bool, purpose: Optional[str] = None, mode=None,
):
    """Keep admission, run binding and execution claim in one transaction.

    Returns ``(result, admission)``; a run that skipped /prepare is admitted
    here like any other.
    """
    key = get_usage_run_key(data)
    admission = token_admission_for(uid, tier, deep_think=deep_think, mode=mode)
    try:
        result, claim = run_usage_repository.authorize_operation(
            uid, key, RunKind.DEEP_THINK if deep_think else RunKind.REGULAR,
            admission, operation,
            canonical_request_fingerprint(request_payload),
            request_fingerprint=usage_run_fingerprint(
                data, question=str(data.get("question") or "").strip(),
                deep_think=deep_think, purpose=purpose,
            ),
        )
    except UsageLimitExceeded as exc:
        raise HTTPException(status_code=403, detail=_token_limit_detail(exc, tier)) from None
    except UsageCapacityExceeded:
        raise HTTPException(status_code=429, detail={
            "error": "Too many runs are starting at once. Please wait for one to finish.",
            "error_code": "usage_run_capacity",
        }) from None
    except (UsageRunConflict, UsageRunExpired, UsageRunReleased, UsageTransitionError) as exc:
        code = (
            "usage_operation_conflict" if isinstance(exc, UsageOperationConflict) else
            "usage_run_conflict" if isinstance(exc, UsageRunConflict) else
            "usage_run_expired" if isinstance(exc, UsageRunExpired) else
            "usage_run_released" if isinstance(exc, UsageRunReleased) else
            "usage_run_transition"
        )
        raise HTTPException(
            status_code=409, detail={"error": str(exc), "error_code": code},
        ) from None
    except FirestoreAborted:
        raise _usage_storage_busy("Usage authorization is temporarily busy. Please retry.") from None
    if claim.idempotent:
        raise HTTPException(status_code=409, detail={
            "error": "This logical operation was already started.",
            "error_code": "usage_operation_already_claimed",
        })
    return result, admission


def operation_booking(uid: str, data: dict, operation: str, *, final: bool = False) -> OperationBooking:
    """Meter one authorized operation; its tokens are booked when it ends."""
    return OperationBooking(run_usage_repository, uid, get_usage_run_key(data), operation, final=final)


def parse_boolean_flag(value) -> bool:
    return str(value).strip().lower() == "true"


ENGINE_KEY_FIELDS = {"OpenRouter": "openrouter_key"}


def build_engine_api_keys(data: dict, use_own_keys: bool) -> dict:
    """Keys fuer Consensus-/Differences-/Resolve-Engines: bei useOwnKeys nur
    die vom Nutzer uebermittelten Keys, sonst die zentral aufgeloesten
    Developer-Keys. Leere/Whitespace-Werte werden einheitlich zu None."""
    if not use_own_keys:
        # Eine gemeinsame Quelle fuer App, API und Benchmark verhindert, dass
        # ein Provider im Answer-Fan-out verfuegbar ist, im Judge-Plan aber
        # wegen abweichender Env-Namen oder Leerwert-Behandlung fehlt.
        return resolve_developer_api_keys()

    # Im Own-Key-Modus Developer-Keys strikt ignorieren. Sonst koennte der
    # Differences-Fallback unbemerkt einen Server-Key verwenden.
    return {
        label: str(data.get(field) or "").strip() or None
        for label, field in ENGINE_KEY_FIELDS.items()
    }


def cap_engine_text(value, limit: int):
    """Kappt clientseitig gelieferte Texte (Frage/Modellantworten), bevor sie
    in Consensus-/Differences-Prompts fliessen. Stilles Truncate statt 400:
    legitime Antworten liegen weit unter dem Limit, nur Abuse-Payloads nicht."""
    if not isinstance(value, str) or len(value) <= limit:
        return value
    # Keep the exact cap length so downstream judges can conservatively flag
    # the shared evidence boundary, including cuts landing on whitespace.
    return value[:limit]


# Historische Feldnamen der /consensus-Antworten. Neue Familien kommen ohne
# Sonderfall aus: answer_<familie>.
LEGACY_ANSWER_FIELDS = {"anthropic": "answer_claude"}


def _incoming_answers(data: dict, limit: int) -> dict:
    """Antworten je Familie, gekappt, in Registry-Reihenfolge, Schluessel ist
    der Anzeigename.

    Bevorzugt wird das Feld `answers` ({"openai": "..."} oder {"OpenAI": ...});
    ohne dieses greifen die historischen answer_<familie>-Felder, die aeltere
    Clients senden."""
    supplied = data.get("answers")
    supplied = supplied if isinstance(supplied, dict) else None
    answers = {}
    for provider, label in cfg.PROVIDER_LABEL_BY_ID.items():
        if supplied is not None:
            raw = supplied.get(provider, supplied.get(label))
        else:
            raw = data.get(LEGACY_ANSWER_FIELDS.get(provider, f"answer_{provider}"))
        answers[label] = cap_engine_text(raw, limit)
    return answers


def _receipt_ids(data: dict) -> Optional[dict]:
    """``answer_receipts`` as ``{label: receipt_id}`` or None when absent."""
    supplied = data.get("answer_receipts")
    if supplied is None:
        return None
    if not isinstance(supplied, dict):
        raise HTTPException(status_code=400, detail="answer_receipts must be an object.")
    receipts = {}
    for provider, label in cfg.PROVIDER_LABEL_BY_ID.items():
        value = supplied.get(provider, supplied.get(label))
        if value in (None, ""):
            continue
        if not answer_receipts.is_receipt_id(value):
            raise HTTPException(status_code=400, detail="Invalid answer receipt.")
        receipts[label] = value
    return receipts


def validate_text_size(
    value,
    *,
    label: str,
    max_chars: int,
    max_bytes: int,
    required: bool = False,
) -> str:
    if not isinstance(value, str):
        if required:
            raise HTTPException(status_code=400, detail=f"{label} must be text.")
        return ""
    normalized = value.strip()
    if required and not normalized:
        raise HTTPException(status_code=400, detail=f"{label} must not be empty.")
    if len(normalized) > max_chars or len(normalized.encode("utf-8")) > max_bytes:
        raise HTTPException(
            status_code=400,
            detail=(
                f"{label} exceeds the limit of {max_chars} characters "
                f"or {max_bytes} UTF-8 bytes."
            ),
        )
    return normalized


def validate_client_system_prompt(value) -> str:
    if value is None or value == "":
        return ""
    return validate_text_size(
        value,
        label="System prompt",
        max_chars=MAX_SYSTEM_PROMPT_CHARS,
        max_bytes=MAX_SYSTEM_PROMPT_BYTES,
    )


def _incomplete_consensus_fields(state: str) -> dict:
    """Final-payload fields of a synthesis that stopped early (R06).

    The partial text already reached the browser as deltas and may stay
    visible there, labelled as incomplete. It is never returned or stored as
    the consensus of the run.
    """
    return {
        "consensus_response": "",
        "consensus_completion": state,
        "error": completion.incomplete_message(state, "The consensus"),
        "error_code": "consensus_incomplete",
    }


def _chat_turn_ids(data: dict) -> Optional[tuple[str, str]]:
    chat_id = data.get("chat_id")
    turn_id = data.get("turn_id")
    if (chat_id is None) != (turn_id is None):
        raise HTTPException(
            status_code=400,
            detail="chat_id and turn_id must be provided together.",
        )
    if chat_id is None:
        return None
    if (
        not isinstance(chat_id, str)
        or not isinstance(turn_id, str)
        or not _CHAT_DOCUMENT_ID_RE.fullmatch(chat_id)
        or not _CHAT_DOCUMENT_ID_RE.fullmatch(turn_id)
    ):
        raise HTTPException(status_code=400, detail="Invalid chat or turn identifier.")
    return chat_id, turn_id


def _context_version_id(
    data: dict, chat_turn_ids: Optional[tuple[str, str]]
) -> Optional[str]:
    version_id = data.get("context_version_id")
    if version_id is None:
        return None
    if chat_turn_ids is None:
        raise HTTPException(
            status_code=400,
            detail="context_version_id requires chat_id and turn_id.",
        )
    if not isinstance(version_id, str) or not _CHAT_DOCUMENT_ID_RE.fullmatch(version_id):
        raise HTTPException(status_code=400, detail="Invalid context version identifier.")
    return version_id


def _chat_turn_disposition(
    ids: tuple[str, str],
    state: str,
    *,
    persisted: Optional[bool] = None,
) -> dict:
    chat_id, turn_id = ids
    result = {
        "chat_id": chat_id,
        "turn_id": turn_id,
        "chat_turn_state": state,
    }
    if persisted is not None:
        result["chat_persisted"] = persisted
    return result


def _chat_turn_error_detail(
    message: str,
    ids: tuple[str, str],
    state: str,
    *,
    persisted: Optional[bool] = None,
) -> dict:
    return {
        "error": message,
        **_chat_turn_disposition(ids, state, persisted=persisted),
    }


def _validate_chat_turn(uid: str, ids: tuple[str, str], question: str) -> dict:
    chat_id, turn_id = ids
    try:
        return chat_store.validate_turn_for_completion(
            uid,
            chat_id,
            turn_id,
            question=question,
        )
    except ChatNotFound as exc:
        raise HTTPException(
            status_code=404,
            detail=_chat_turn_error_detail(
                "Chat turn not found.", ids, "failed", persisted=False
            ),
        ) from exc
    except TurnQuestionConflict as exc:
        raise HTTPException(
            status_code=409,
            detail=_chat_turn_error_detail(
                "Consensus question does not match the pending turn.",
                ids,
                "failed",
                persisted=False,
            ),
        ) from exc
    except TurnStatusConflict as exc:
        raise HTTPException(
            status_code=409,
            detail=_chat_turn_error_detail(
                "Chat turn is not completable.", ids, "failed", persisted=False
            ),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=_chat_turn_error_detail(
                "Invalid chat turn payload.", ids, "pending", persisted=False
            ),
        ) from exc
    except ChatStoreError as exc:
        logging.error(
            "chat turn preflight failed chat_id=%s turn_id=%s category=%s",
            chat_id,
            turn_id,
            safe_exception(exc),
        )
        raise HTTPException(
            status_code=503,
            detail=_chat_turn_error_detail(
                "Chat persistence unavailable.", ids, "pending", persisted=False
            ),
        ) from exc
    except Exception as exc:
        logging.error(
            "chat turn preflight failed chat_id=%s turn_id=%s category=%s",
            chat_id,
            turn_id,
            safe_exception(exc),
        )
        raise HTTPException(
            status_code=503,
            detail=_chat_turn_error_detail(
                "Chat persistence unavailable.", ids, "pending", persisted=False
            ),
        ) from exc


def _fail_chat_turn_best_effort(
    uid: str,
    ids: Optional[tuple[str, str]],
    *,
    error_code: str,
) -> bool:
    if ids is None:
        return False
    chat_id, turn_id = ids
    try:
        failed_turn = chat_store.fail_turn(uid, chat_id, turn_id, error_code=error_code)
        return isinstance(failed_turn, dict) and failed_turn.get("status") == "failed"
    except Exception as exc:
        logging.warning(
            "chat turn failure marker failed chat_id=%s turn_id=%s code=%s category=%s",
            chat_id,
            turn_id,
            error_code,
            safe_exception(exc),
        )
        return False


def _replay_completed_chat_turn(
    uid: str,
    ids: tuple[str, str],
    *,
    stream_requested: bool,
):
    chat_id, turn_id = ids
    try:
        turn = chat_store.get_turn(uid, chat_id, turn_id)
    except ChatNotFound as exc:
        raise HTTPException(
            status_code=404,
            detail=_chat_turn_error_detail(
                "Chat turn not found.", ids, "failed", persisted=False
            ),
        ) from exc
    except Exception as exc:
        logging.error(
            "completed chat turn replay read failed chat_id=%s turn_id=%s category=%s",
            chat_id,
            turn_id,
            safe_exception(exc),
        )
        raise HTTPException(
            status_code=503,
            detail=_chat_turn_error_detail(
                "Chat persistence unavailable.", ids, "pending", persisted=False
            ),
        ) from exc

    consensus_text = turn.get("consensus")
    if not isinstance(consensus_text, str) or not consensus_text.strip():
        raise HTTPException(
            status_code=409,
            detail=_chat_turn_error_detail(
                "Completed chat turn has no replayable consensus.",
                ids,
                "failed",
                persisted=False,
            ),
        )

    payload = {
        "consensus_response": consensus_text,
        "consensus_completion": completion.COMPLETE,
        "differences": turn.get("differences")
        if isinstance(turn.get("differences"), str)
        else "",
        "differences_data": turn.get("differences_data"),
        "sources": turn.get("sources") if isinstance(turn.get("sources"), list) else [],
        "model_answers": (
            turn.get("model_answers")
            if isinstance(turn.get("model_answers"), dict)
            else {}
        ),
        **_chat_turn_disposition(ids, "completed", persisted=True),
        "chat_replayed": True,
    }
    result_id = turn.get("result_id")
    if turn.get("source_verification") is not None:
        payload["source_verification"] = turn["source_verification"]
    if isinstance(result_id, str) and result_id:
        payload["result_id"] = result_id

    if not stream_requested:
        return payload

    def replay_event_source():
        yield sse_pack("consensus.final", {"text": consensus_text})
        yield sse_pack("differences.final", {
            "differences": payload["differences"], "differences_data": payload["differences_data"],
        })
        if payload.get("source_verification"):
            yield sse_pack("sources.final", {"source_verification": payload["source_verification"]})
        yield sse_pack("final", payload)

    return StreamingResponse(
        replay_event_source(),
        media_type="text/event-stream",
        headers=dict(SSE_HEADERS),
    )


def normalize_followup_context(raw):
    """Validiert das optionale context-Feld einer Follow-up-Frage
    ({previous_question, previous_consensus}) und kappt beide Texte
    serverseitig, analog zu cap_engine_text bei /consensus. Genau eine
    Kontext-Ebene: ein einzelnes Frage/Konsens-Paar, kein Verlauf.
    Unbrauchbare Payloads werden still ignoriert (kein 400: das Feld ist
    optional und ein kaputter Kontext soll die Frage nicht blockieren)."""
    if not isinstance(raw, dict):
        return None
    previous_question = raw.get("previous_question")
    previous_consensus = raw.get("previous_consensus")
    if not isinstance(previous_question, str) or not previous_question.strip():
        return None
    if not isinstance(previous_consensus, str) or not previous_consensus.strip():
        return None
    previous_question = validate_text_size(
        previous_question,
        label="Previous question",
        max_chars=cfg.get_followup_question_char_limit(),
        max_bytes=cfg.get_followup_question_char_limit() * 4,
        required=True,
    )
    previous_consensus = validate_text_size(
        previous_consensus,
        label="Previous consensus",
        max_chars=cfg.get_followup_consensus_char_limit(),
        max_bytes=cfg.get_followup_consensus_char_limit() * 4,
        required=True,
    )
    return {
        "previous_question": previous_question,
        "previous_consensus": previous_consensus,
    }


def _resolve_authoritative_chat_context(
    uid: Optional[str],
    data: dict,
    question: str,
    provider: str = "",
) -> Optional[str]:
    fields = (
        data.get("chat_id"),
        data.get("turn_id"),
        data.get("context_version_id"),
    )
    if not any(value is not None for value in fields):
        return None
    if uid is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    if data.get("context") is not None:
        raise HTTPException(
            status_code=400,
            detail="Legacy context and context_version_id cannot be combined.",
        )
    if not all(
        isinstance(value, str) and _CHAT_DOCUMENT_ID_RE.fullmatch(value)
        for value in fields
    ):
        raise HTTPException(status_code=400, detail="Invalid chat context identifier.")
    chat_id, turn_id, version_id = fields
    try:
        # All six /ask_* calls of one run resolve the same owner-bound tuple,
        # differing only in the caller's own previous answer. Resolving stays
        # server-side (the context must never travel through the client); the
        # cache still collapses the reads and renders of one provider, including
        # its retries.
        return resolved_context_cache.get_or_resolve(
            resolved_context_cache_key(
                uid, chat_id, turn_id, version_id, question, provider
            ),
            lambda: chat_context_service.resolve_for_ask(
                uid,
                chat_id,
                turn_id,
                version_id,
                question=question,
                provider=provider,
            ),
        )
    except ChatContextNotFound as exc:
        raise HTTPException(status_code=404, detail="Chat context not found") from exc
    except ChatContextConflict as exc:
        raise HTTPException(status_code=409, detail="Chat context conflict") from exc
    except ChatContextError as exc:
        logging.error(
            "chat context resolution failed category=%s", safe_exception(exc)
        )
        raise HTTPException(status_code=503, detail="Chat context unavailable") from exc
    except Exception as exc:
        logging.error(
            "chat context resolution failed category=%s", safe_exception(exc)
        )
        raise HTTPException(status_code=503, detail="Chat context unavailable") from exc


def validate_question_word_limit(question: str, tier, deep_search: bool):
    question = validate_text_size(
        question,
        label="Question",
        max_chars=MAX_QUESTION_CHARS,
        max_bytes=MAX_QUESTION_BYTES,
        required=True,
    )

    max_words_limit = cfg.get_word_limit(tier, deep_search)
    if count_words(question) > max_words_limit:
        raise HTTPException(status_code=400, detail=f"Input exceeds word limit of {max_words_limit}.")
    return question


def _attachment_claim_payload(attachments: list[dict]) -> list[dict]:
    return [
        {
            "name": str(item.get("name") or ""),
            "mime": str(item.get("mime") or ""),
            "sha256": hashlib.sha256(item.get("raw") or b"").hexdigest(),
        }
        for item in attachments
    ]

# ---------------------------------------------------------------------------
# /ask_*-Endpoints: ein gemeinsamer Ablauf fuer alle Registry-Familien; alle
# Requests verwenden denselben OpenRouter-Transport und dasselbe Credential.
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class AskProvider:
    key: str
    label: str

    @property
    def allowed_models(self) -> set:
        """Immer die aktuelle Admin-Liste der Familie (in-place mutiertes Set)."""
        return cfg.PROVIDERS[self.key].models


# Eine /ask-Familie je Registry-Eintrag. Die Routen darunter sind der
# Client-Vertrag und bleiben ausgeschrieben.
ASK_PROVIDERS = {
    provider.key: AskProvider(key=provider.key, label=provider.label)
    for provider in cfg.PROVIDERS.values()
}


def _with_receipt(result, receipt):
    """Attach the server receipt of a delivered answer (R09) to its result."""
    if receipt is None or not isinstance(result, dict) or result.get("error"):
        return result
    receipt_id = receipt(result)
    if receipt_id:
        return {**result, "answer_receipt": receipt_id}
    return result


def _receipt_stream(source, receipt):
    for event in source:
        if receipt is not None and isinstance(event, dict) and event.get("type") == "final":
            event = {**event, "result": _with_receipt(event.get("result"), receipt)}
        yield event


def _run_ask(provider: AskProvider, *, stream_requested, question, key,
             system_prompt, deep_search, model, max_tokens, attachments, extras,
             receipt=None, booking: Optional[OperationBooking] = None):
    """Fuehrt den Provider-Call aus (streamend oder nicht) und verpackt das
    Ergebnis im bisherigen Response-Format.

    ``receipt(result) -> receipt_id`` stores the delivered answer server-side
    so /consensus can use exactly this text (R09)."""
    if mock_llm_enabled():
        # E2E-Suite: deterministischer Fixture-Stream statt Provider-Call.
        # Auth/Limits/Validierung sind zu diesem Zeitpunkt bereits gelaufen.
        if stream_requested:
            source = _receipt_stream(mock_ask_stream(provider.label, question), receipt)
            return streaming_model_response(
                metered_events(source, booking) if booking else source,
                provider.label, extras,
            )
        if booking is None:
            return source_response(_with_receipt(mock_ask_result(provider.label, question), receipt), **extras)
        with booking.metering():
            result = _with_receipt(mock_ask_result(provider.label, question), receipt)
        return source_response(result, **extras, **booking.extras())

    kwargs = {
        "system_prompt": system_prompt,
        "deep_search": deep_search,
        "model_override": model,
        "max_output_tokens": max_tokens,
        "attachments": attachments,
    }
    if stream_requested:
        source = _receipt_stream(
            stream_model_query(provider.key, question, key, **kwargs), receipt
        )

        def observed_stream():
            started = time.monotonic()
            outcome = "success"
            saw_final = False
            try:
                for event in source:
                    result = event.get("result") if isinstance(event, dict) else None
                    if isinstance(result, dict) and result.get("error"):
                        outcome = (
                            "timeout"
                            if result.get("error_code") == "provider_timeout"
                            else "failure"
                        )
                    if isinstance(event, dict) and event.get("type") == "final":
                        saw_final = True
                    yield event
                if not saw_final:
                    outcome = "failure"
            except ProviderCancelled:
                outcome = "cancelled"
                raise
            except GeneratorExit:
                if not saw_final:
                    outcome = "cancelled"
                raise
            except TimeoutError:
                outcome = "timeout"
                raise
            except Exception:
                outcome = "failure"
                raise
            finally:
                record_metric(
                    "provider",
                    provider.label,
                    duration_ms=(time.monotonic() - started) * 1000,
                    outcome=outcome,
                )

        events = observed_stream()
        return streaming_model_response(
            metered_events(events, booking) if booking else events, provider.label, extras
        )
    started = time.monotonic()
    outcome = "success"
    try:
        if booking is None:
            result = _with_receipt(
                query_model(provider.key, question, key, **kwargs), receipt
            )
        else:
            try:
                with booking.metering():
                    result = _with_receipt(
                        query_model(provider.key, question, key, **kwargs), receipt
                    )
            finally:
                extras = {**extras, **booking.extras()}
        if isinstance(result, dict) and result.get("error"):
            outcome = (
                "timeout"
                if result.get("error_code") == "provider_timeout"
                else "failure"
            )
        return source_response(result, **extras)
    except TimeoutError:
        outcome = "timeout"
        raise
    except Exception:
        outcome = "failure"
        raise
    finally:
        record_metric(
            "provider",
            provider.label,
            duration_ms=(time.monotonic() - started) * 1000,
            outcome=outcome,
        )


def handle_ask(provider: AskProvider, request: Request, data: dict):
    question = data.get("question")
    deep_search = parse_boolean_flag(data.get("deep_search", False))
    stream_requested = parse_boolean_flag(data.get("stream", False))
    system_prompt = validate_client_system_prompt(data.get("system_prompt"))
    id_token = extract_id_token(request, data)
    api_key = str(data.get("openrouter_key") or "").strip()
    model = data.get("model")

    tier = TIER_FREE
    entitlements = entitlements_for(tier)
    uid = None

    if id_token:
        try:
            uid = verify_user_token(id_token)
        except Exception as exc:
            raise HTTPException(status_code=401, detail="Authentication failed")
        try:
            tier = get_user_tier(uid)
        except TierStatusUnavailable:
            raise HTTPException(
                status_code=503,
                detail="Account tier is temporarily unavailable. Please retry.",
            ) from None
        entitlements = entitlements_for(tier)

    # is_pro_user heisst weiterhin "darf Frontier-Modelle und Deep Think".
    # Plus ist hier False und faehrt damit exakt die Free-Modellauswahl.
    is_pro_user = entitlements.is_pro

    # Deep Think ist strikt Pro-only.
    if deep_search and not entitlements.deep_think:
        raise HTTPException(status_code=403, detail="Deep Think is exclusively available for Pro users.")

    question = validate_question_word_limit(question, tier, deep_search)
    validate_model(
        model,
        provider.allowed_models,
        provider.label,
        is_pro=is_pro_user,
    )
    attachments = parse_attachments(data, attachments_allowed=entitlements.attachments)
    effective_model = cfg.PROVIDERS[provider.key].pro_model if deep_search else model
    model_config = cfg.get_model_config(effective_model, provider.key)
    if attachments and model_config and not model_config.accepts_attachments:
        raise HTTPException(
            status_code=400,
            detail=f"{model_config.label} cannot read attachments.",
        )
    max_tokens = cfg.get_output_token_limit(tier, deep_search)

    # Das nutzereigene Gedaechtnis. Es haengt an der Basisanweisung, NICHT im
    # Datenteil: es ist eine stehende Praeferenz des Nutzers, kein
    # Gespraechsinhalt. Deshalb steht es vor der Chat-Kontext-Umhuellung -- die
    # legt den Kontext davor und laesst die Anweisung samt Profil zuletzt.
    #
    # Ausschliesslich hier, wie beim Follow-up-Kontext: Watch-Reruns, Publisher-
    # und Topic-Laeufe rufen engines.py direkt und duerfen kein Profil sehen,
    # sonst driftet eine Watch-Baseline mit dem Profil statt mit der Welt.
    if uid and parse_boolean_flag(data.get("use_memory", True)):
        memory_text = user_memory.load_profile_text(
            user_memory_repository,
            uid,
            max_notes_chars=cfg.get_memory_char_limit(tier),
            run_key=data.get("usage_run_key"),
        )
        if memory_text:
            system_prompt = user_memory.build_user_memory_system_prompt(
                system_prompt.strip()
                if isinstance(system_prompt, str) and system_prompt.strip()
                else get_system_prompt(),
                memory_text,
            )

    # Antwortmodelle sehen Memory nur lesend. Die Schreibberechtigung bleibt
    # beim expliziten /api/my/memory/edit-Flow; dadurch kann eine normale Frage
    # nie mit einem falschen "ich merke mir das"-Versprechen beantwortet werden.
    # Nur interaktive, eingeloggte Ask-Laeufe erhalten diese Grenze. Watch,
    # Publisher und Topics umgehen diesen Router weiterhin vollstaendig.
    if uid:
        system_prompt = user_memory.build_interactive_memory_boundary_prompt(
            system_prompt.strip()
            if isinstance(system_prompt, str) and system_prompt.strip()
            else get_system_prompt()
        )

    authoritative_context = _resolve_authoritative_chat_context(
        uid, data, question, provider.label
    )
    if authoritative_context:
        base_prompt = (
            system_prompt.strip()
            if isinstance(system_prompt, str) and system_prompt.strip()
            else get_system_prompt()
        )
        system_prompt = build_chat_context_system_prompt(
            base_prompt,
            authoritative_context,
        )

    # Legacy-Follow-up-Kontext: genau eine vorherige Frage/Konsens-Ebene,
    # serverseitig hart begrenzt und hier in den System-Prompt injiziert — nicht in
    # /prepare, damit der Kontext auch dann ankommt, wenn das Frontend nach
    # einem /prepare-Fehler mit dem Basis-Prompt weitermacht. Kein Tier-Gate:
    # ein Follow-up ist ein normaler Lauf und zaehlt gegen das Tagesbudget.
    followup_context = normalize_followup_context(data.get("context"))
    if followup_context:
        base_prompt = (
            system_prompt.strip()
            if isinstance(system_prompt, str) and system_prompt.strip()
            else get_system_prompt()
        )
        system_prompt = build_followup_system_prompt(
            base_prompt,
            followup_context["previous_question"],
            followup_context["previous_consensus"],
        )

    own_keys_requested = parse_boolean_flag(data.get("useOwnKeys", False))

    def answer_receipt(provenance):
        # R09: the server keeps the exact delivered answer. /consensus only
        # accepts answers through these receipts, never as browser text.
        run = answer_receipts.run_binding(uid, data.get("usage_run_key"), data.get("run_id"))
        if not uid or not run:
            return None
        concrete_model = cfg.PROVIDERS[provider.key].pro_model if deep_search else (
            model or cfg.PROVIDERS[provider.key].base_model
        )

        def store(result):
            text = coerce_text(result.get("text") or result.get("response")) if isinstance(result, dict) else ""
            return answer_receipt_store.store(
                uid=uid,
                run=run,
                question=question,
                provider=provider.label,
                model=concrete_model,
                text=text,
                sources=result.get("sources") if isinstance(result, dict) else [],
                state=completion.result_completion(result),
                provenance=provenance,
            )

        return store

    # --- Eigener API-Key: eingeloggtes Feature, umgeht die Usage-Zaehlung ---
    if own_keys_requested and uid:
        if not api_key:
            raise HTTPException(status_code=400, detail="Missing user OpenRouter API key.")
        return _run_ask(
            provider,
            stream_requested=stream_requested,
            question=question,
            key=api_key,
            system_prompt=system_prompt,
            deep_search=deep_search,
            model=model,
            max_tokens=max_tokens,
            attachments=attachments,
            extras={
                **own_key_usage_fields(tier),
                "key_used": "User API Key",
            },
            receipt=answer_receipt(answer_receipts.PROVENANCE_BYOK),
        )

    # --- Developer-Key: genau ein persistenter Slot pro Run ---
    if uid:
        developer_key = openrouter_api_key(resolve_developer_api_keys())
        if not developer_key:
            raise HTTPException(status_code=500, detail="Server error: API key missing")

        operation = f"ask:{provider.label.lower()}"
        usage_result, admission = authorize_usage_operation(
            uid,
            data,
            operation,
            {
                "schema": 1,
                "provider": provider.label,
                "question": question,
                "system_prompt": system_prompt or "",
                "deep_search": deep_search,
                "model": model,
                "stream": stream_requested,
                "attachments": _attachment_claim_payload(attachments),
                "chat_id": data.get("chat_id"),
                "turn_id": data.get("turn_id"),
                "context_version_id": data.get("context_version_id"),
            },
            tier=tier, deep_think=deep_search, mode=data.get("run_mode"),
        )

        # The answer's tokens are measured in the transport and booked on the
        # account when it ends; the final event carries the booked snapshot.
        return _run_ask(
            provider,
            stream_requested=stream_requested,
            question=question,
            key=developer_key,
            system_prompt=system_prompt,
            deep_search=deep_search,
            model=model,
            max_tokens=max_tokens,
            attachments=attachments,
            extras={
                **usage_response_fields(None, tier),
                "usage_run_status": usage_result.status.value,
                "key_used": "Developer API Key",
            },
            receipt=answer_receipt(answer_receipts.PROVENANCE_DEVELOPER),
            booking=operation_booking(uid, data, operation),
        )

    # --- Kein Login: eigener Key erfordert Login, sonst Provider-No-Auth-Fehler ---
    if own_keys_requested:
        raise HTTPException(status_code=401, detail=OWN_KEYS_LOGIN_REQUIRED)
    raise HTTPException(status_code=400, detail="No auth provided.")


def _make_ask_endpoint(provider_key: str):
    provider_config = cfg.PROVIDERS[provider_key]

    def ask_provider_post(request: Request, data: dict = Body(...)):
        return handle_ask(ASK_PROVIDERS[provider_key], request, data)

    ask_provider_post.__name__ = f"ask_{provider_config.dom_key}_post"
    ask_provider_post.__qualname__ = ask_provider_post.__name__
    rate = "5/minute" if provider_key in {"openai", "mistral"} else "3/minute"
    return limiter.limit(rate)(ask_provider_post)


# Route, Handlername und Client-Endpoint kommen aus derselben Registry. Damit
# braucht eine neue Familie keinen zusaetzlichen Copy-Paste-Wrapper mehr.
for _provider_key, _provider_config in cfg.PROVIDERS.items():
    _handler = _make_ask_endpoint(_provider_key)
    globals()[_handler.__name__] = _handler
    router.add_api_route(
        _provider_config.ask_endpoint,
        _handler,
        methods=["POST"],
    )


@router.post("/prepare")
def prepare(request: Request, data: dict = Body(...)):
    question = validate_text_size(
        data.get("question"),
        label="Question",
        max_chars=MAX_QUESTION_CHARS,
        max_bytes=MAX_QUESTION_BYTES,
        required=True,
    )

    use_own_keys = parse_boolean_flag(data.get("useOwnKeys", False))
    deep_think = parse_boolean_flag(data.get("deep_search", False))
    id_token = extract_id_token(request, data)
    if not id_token:
        raise HTTPException(status_code=401, detail="Authentication required to analyze intent.")

    try:
        uid = verify_user_token(id_token)
        try:
            tier = get_user_tier(uid)
        except TierStatusUnavailable:
            raise HTTPException(
                status_code=503,
                detail="Account tier is temporarily unavailable. Please retry.",
            ) from None
        entitlements = entitlements_for(tier)
        if deep_think and not entitlements.deep_think:
            raise HTTPException(
                status_code=403,
                detail={
                    "error": "Deep Think is exclusively available for Pro users.",
                    "error_code": "pro_required",
                },
            )
    except HTTPException as he:
        raise he
    except Exception as exc:
        logging.error("Auth failed in /prepare category=%s", safe_exception(exc))
        raise HTTPException(status_code=401, detail="Authentication failed.")

    # Der Follow-up-Kontext wird hier bewusst NICHT verarbeitet: injiziert wird
    # er erst in den /ask_*-Endpoints (handle_ask), sonst stuende er doppelt im
    # System-Prompt. Ein Tier-Gate gibt es nicht mehr.

    validate_question_word_limit(question, tier, deep_think)
    raw_system_prompt = validate_client_system_prompt(data.get("system_prompt"))
    if not raw_system_prompt or not str(raw_system_prompt).strip():
        base_system_prompt = get_system_prompt()
    else:
        base_system_prompt = str(raw_system_prompt).strip()

    # Echtzeitdaten holen sich die Modelle ueber das gemeinsame OpenRouter-Web-Tool,
    # das in jedem Modell-Call aktiv ist (siehe engines.py). Ein vorgeschalteter
    # Intent-Router mit Realtime-Injektion waere nur redundante, serielle Latenz.
    response = {
        "system_prompt": base_system_prompt,
        "sources": []
    }
    if not use_own_keys:
        # Admission: the run starts only if the account covers the expected
        # cost of a typical run of this mode (compare/consensus/deep think).
        usage_key, reserved, admission = reserve_usage_run(
            uid, data, tier=tier, deep_think=deep_think, mode=data.get("run_mode")
        )
        # Consume once before fan-out so later authorization only reads the
        # run and writes the operation claim. The combined authorize path also
        # consumes a leftover reservation if prepare was interrupted.
        usage_result = consume_usage_run(uid, usage_key)
        response.update(usage_response_fields(
            current_token_budget(uid, reserved, admission), tier))
        response["usage_run_status"] = usage_result.status.value
        response["run_estimate"] = admission.estimate
    return response


@router.post("/consensus")
@limiter.limit("5/minute")
def consensus(request: Request, data: dict = Body(...)):
    id_token = extract_id_token(request, data)
    chat_turn_ids = _chat_turn_ids(data)
    context_version_id = _context_version_id(data, chat_turn_ids)
    use_own_keys = str(data.get("useOwnKeys", "false")).lower() == "true"
    deep_think = parse_boolean_flag(data.get("deep_search", False))
    consensus_model = data.get("consensus_model")
    stream_requested = parse_boolean_flag(data.get("stream", False))
    uid = None
    tier = TIER_FREE
    entitlements = entitlements_for(tier)
    is_pro = False

    # 1. Auth & Usage Check
    if not id_token:
        raise HTTPException(
            status_code=401,
            detail=OWN_KEYS_LOGIN_REQUIRED if use_own_keys else "Authentication required",
        )

    try:
        uid = verify_user_token(id_token)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")
    try:
        tier = get_user_tier(uid)  # WICHTIG: Kontostufe prüfen
    except TierStatusUnavailable:
        raise HTTPException(
            status_code=503,
            detail="Account tier is temporarily unavailable. Please retry.",
        ) from None
    entitlements = entitlements_for(tier)
    # is_pro bleibt das Modell-/Deep-Think-Flag; Plus ist hier False.
    is_pro = entitlements.is_pro

    # A completed turn is owner-bound stored history, not a new engine run.
    # Resolve it before current model/tier/credential checks so a later plan or
    # allowlist change cannot make an already completed answer unreadable.
    question = validate_text_size(
        data.get("question"),
        label="Question",
        max_chars=min(MAX_QUESTION_CHARS, cfg.get_consensus_question_char_limit()),
        max_bytes=MAX_QUESTION_BYTES,
    )
    validated_chat_turn_ids = None
    # Dieselbe aufgeloeste Lesart, die auch die sechs Modelle bekommen haben.
    # Sie steht am Turn, nicht im Request: der Client darf den Prompt der
    # Synthese so wenig bestimmen wie den Kontext der Modelle. Ohne sie schrieb
    # der Synthesizer die sichtbare Antwort auf eine Frage, die er selbst nicht
    # aufloesen konnte ("1-10?"), und der Judge verglich sechs Antworten auf
    # sechs verschiedene Lesarten als inhaltlichen Widerspruch.
    resolved_question = ""
    if question and chat_turn_ids is not None:
        validated_turn = _validate_chat_turn(uid, chat_turn_ids, question)
        validated_chat_turn_ids = chat_turn_ids
        resolved_question = str(validated_turn.get("resolved_question") or "")
        linked_context_version_id = validated_turn.get("context_version_id")
        if linked_context_version_id != context_version_id:
            raise HTTPException(
                status_code=409,
                detail=_chat_turn_error_detail(
                    "Consensus context version does not match the pending turn.",
                    chat_turn_ids,
                    "pending",
                    persisted=False,
                ),
            )
        if validated_turn.get("status") == "completed":
            return _replay_completed_chat_turn(
                uid,
                validated_chat_turn_ids,
                stream_requested=stream_requested,
            )

    # Parameter extrahieren. Frage und Antworten kommen als freier Text vom
    # Client und werden serverseitig hart begrenzt: der Consensus-Prompt enthaelt
    # sonst unbegrenzte Eingaben gegen den Developer-Key (Kostenleck).
    answer_char_limit = cfg.get_consensus_answer_char_limit()
    excluded_models = data.get("excluded_models", [])
    check_sources = data.get("check_sources", True) is not False
    if not isinstance(excluded_models, list):
        excluded_models = []
    excluded_models = list({normalize_model_name(model) for model in excluded_models if model})

    # R09: model answers are authoritative only as server-stored /ask results.
    # The browser names them by receipt id; text, sources, model and
    # provenance come from the receipt. Client-supplied answer text is never
    # accepted as a model answer.
    def receipt_failure(status_code: int, message: str, error_code: str) -> HTTPException:
        # A rejected answer set can never complete this turn: fail it so the
        # browser does not keep the conversation locked on a pending turn.
        disposable_ids = validated_chat_turn_ids or chat_turn_ids
        failed = _fail_chat_turn_best_effort(uid, disposable_ids, error_code=error_code)
        detail = {"error": message, "error_code": error_code}
        if disposable_ids is not None:
            detail = {**_chat_turn_error_detail(message, disposable_ids, "failed" if failed else "pending",
                                                persisted=False), "error_code": error_code}
        return HTTPException(status_code=status_code, detail=detail)

    receipt_ids = _receipt_ids(data)
    if receipt_ids is None and (
        isinstance(data.get("answers"), dict) and any(data["answers"].values())
        or any(data.get(LEGACY_ANSWER_FIELDS.get(provider, f"answer_{provider}"))
               for provider in cfg.PROVIDER_LABEL_BY_ID)
    ):
        raise receipt_failure(
            400,
            "Model answers must be submitted as answer receipts. Reload the page and run the comparison again.",
            "answer_receipts_required",
        )
    receipt_ids = {
        label: receipt_id for label, receipt_id in (receipt_ids or {}).items()
        if normalize_model_name(label) not in excluded_models
    }
    if len(receipt_ids) > cfg.MAX_RUN_FAMILIES:
        raise HTTPException(
            status_code=400,
            detail=f"A run compares at most {cfg.MAX_RUN_FAMILIES} model answers.",
        )
    try:
        verified_receipts = answer_receipt_store.load(
            uid=uid,
            run=answer_receipts.run_binding(uid, data.get("usage_run_key"), data.get("run_id")),
            question=question,
            receipt_ids=receipt_ids,
        ) if receipt_ids and question else {}
    except answer_receipts.ReceiptError as exc:
        raise receipt_failure(409, exc.message, exc.code) from None
    except Exception as exc:
        logging.error("answer receipt read failed category=%s", safe_exception(exc))
        raise receipt_failure(
            503, "Model answers are temporarily unavailable. Run the question again.",
            "answer_receipts_unavailable",
        ) from exc
    # Incomplete answers (token limit, interrupted) stay visible in the
    # browser but never enter a synthesis (R06).
    usable_receipts = {
        label: receipt for label, receipt in verified_receipts.items()
        if completion.usable_as_input(receipt["completion"]) and receipt["text"].strip()
    }
    answers_by_model = {
        label: completion.consensus_input_text(
            cap_engine_text(usable_receipts[label]["text"], answer_char_limit),
            usable_receipts[label]["completion"],
        )
        if label in usable_receipts else None
        for label in cfg.PROVIDER_LABEL_BY_ID.values()
    }
    model_sources = {
        label: receipt["sources"] for label, receipt in usable_receipts.items()
    }
    # The judge (best model, agreement) also runs on the request's key, so an
    # own-key synthesis is flagged even when every answer came from the
    # service credential.
    result_provenance = (
        answer_receipts.PROVENANCE_BYOK if use_own_keys
        else answer_receipts.result_provenance(usable_receipts.values())
    )
    receipt_model_labels = {
        label: cfg.get_model_label(receipt["model"]) or label
        for label, receipt in usable_receipts.items()
    }

    # Validierung der erforderlichen Parameter (nur für Modelle, die nicht ausgeschlossen wurden)
    missing = []
    if not question:
        missing.append("question")
    if not consensus_model:
        missing.append("consensus_model")

    included_answers = {
        model: answer
        for model, answer in answers_by_model.items()
        if (
            model not in excluded_models
            and isinstance(answer, str)
            and answer.strip()
        )
    }
    # Ein Lauf vergleicht hoechstens MAX_RUN_FAMILIES Modelle. Mehr Familien
    # duerfen konfiguriert sein; der Lauf bleibt ein Sechs-Modell-Vergleich
    # (Prompt-Laenge, Kosten, Lesbarkeit). Der Picker haelt dieselbe Grenze.
    if len(included_answers) > cfg.MAX_RUN_FAMILIES:
        raise HTTPException(
            status_code=400,
            detail=f"A run compares at most {cfg.MAX_RUN_FAMILIES} model answers.",
        )

    from app.services.source_catalog import normalize_source_catalog
    included_answers, model_sources, canonical_sources = normalize_source_catalog(
        included_answers, model_sources=model_sources,
        turn_sources=data.get('turn_sources') if isinstance(data.get('turn_sources'), list) else None,
    )
    # Familien-Sicht derselben Antworten: die Engines und die Domaenen-
    # Pipeline sprechen Familien-IDs, Persistenz und Anzeige die Labels.
    included_by_provider = {
        provider: included_answers[label]
        for provider, label in cfg.PROVIDER_LABEL_BY_ID.items()
        if label in included_answers
    }

    # Ein einzelner ausgefallener Provider (Timeout, 503, leere Reasoning-
    # Antwort) darf den Konsens NICHT blockieren. Fehlt die Antwort eines
    # aktiven Modells, wird es einfach ausgelassen, solange noch mindestens
    # zwei Modelle geantwortet haben – der Consensus-/Differences-Prompt
    # filtert leere Antworten ohnehin heraus. Deshalb hier bewusst KEINE
    # Per-Modell-Pflichtprüfung mehr (die früher den ganzen Lauf mit 400
    # abbrach, sobald ein einzelnes Modell nicht lieferte).
    # Without a question the receipts cannot be verified; the disposition of a
    # pending turn then only distinguishes how many answers were submitted.
    answer_count = len(included_answers) if question else len(receipt_ids)
    if answer_count < 2:
        missing.append("at least two selected model answers")

    if missing:
        # An empty question skips the preflight above, so validated_chat_turn_ids
        # stays None — but the pending turn still exists and would otherwise stay
        # pending forever. fail_turn is owner-scoped and only moves pending ->
        # failed, so disposing an unvalidated turn is safe and never leaks state.
        disposable_ids = validated_chat_turn_ids or chat_turn_ids
        failed = _fail_chat_turn_best_effort(
            uid,
            disposable_ids,
            error_code=(
                "insufficient_answers"
                if answer_count < 2
                else "consensus_failed"
            ),
        )
        message = "Missing parameters: " + ", ".join(missing)
        if disposable_ids is not None:
            raise HTTPException(
                status_code=400,
                detail=_chat_turn_error_detail(
                    message,
                    disposable_ids,
                    "failed" if failed else "pending",
                    persisted=False,
                ),
            )
        raise HTTPException(status_code=400, detail=message)

    if consensus_model not in cfg.ALLOWED_CONSENSUS_MODELS:
        raise HTTPException(status_code=400, detail="Invalid consensus model selected.")

    if deep_think and not is_pro:
        raise HTTPException(status_code=403, detail="Deep Think is exclusively available for Pro users.")

    # Premium-Engines bleiben Pro-exklusiv, AUCH im Own-Key-Modus: eigene Keys
    # bezahlen zwar den Call, heben aber das Tier-Gate nicht auf. Bewusst
    # unbedingt (nicht nur unter `not use_own_keys`) — genau diese zweite,
    # unbedingte Pruefung stand vor der Chat-Umsortierung weiter unten.
    if cfg.is_premium_consensus_model(consensus_model) and not is_pro:
        raise HTTPException(status_code=403, detail="Premium consensus engines are reserved for Pro users.")

    # API Keys setzen: Own-Key-Modus nutzt ausschliesslich Nutzer-Keys,
    # andernfalls kommt das vollstaendige Developer-Key-Set aus der gemeinsamen
    # Credential-Quelle. Bei unvollstaendigen Antworten ist der Turn bereits
    # autoritativ disponiert, bevor diese aktuelle Konfiguration relevant wird.
    api_keys = build_engine_api_keys(data, use_own_keys)
    
    if not openrouter_api_key(api_keys):
        raise HTTPException(status_code=400, detail="Missing OpenRouter API key.")

    usage_result = None
    booking = None
    if not use_own_keys:
        usage_result, _admission = authorize_usage_operation(
            uid,
            data,
            "consensus",
            {
                "schema": 1,
                "question": question,
                "consensus_model": consensus_model,
                "deep_think": deep_think,
                "stream": stream_requested,
                "answers": included_answers,
                "excluded_models": sorted(excluded_models),
                "model_sources": model_sources,
                "chat_id": data.get("chat_id"),
                "turn_id": data.get("turn_id"),
                "context_version_id": context_version_id,
            },
            tier=tier, deep_think=deep_think, mode="consensus",
        )
        # Synthesis, Differences and Coverage judges (and their repairs) are
        # measured in the transport; the final operation of a run also drops
        # what is left of its admission hold.
        booking = operation_booking(uid, data, "consensus", final=True)

    # Share-Feature: Ergebnis nur für verifizierte Nutzer persistieren.
    share_uid = uid
    # The concrete model comes from the /ask receipt, never from the client.
    model_labels = receipt_model_labels

    allowed_model_labels = sanitize_model_labels(
        model_labels,
        list(included_answers.keys()),
    )
    chat_model_answers = {
        provider: {
            "provider": provider,
            "answer": answer,
            "model_label": allowed_model_labels.get(provider, provider),
            "sources": model_sources.get(provider, []),
        }
        for provider, answer in included_answers.items()
    }
    if "turn_sources" in data:
        raw_turn_sources = data.get("turn_sources")
    else:
        raw_turn_sources = [
            source
            for provider in included_answers
            for source in (
                model_sources.get(provider, [])
                if isinstance(model_sources.get(provider, []), list)
                else []
            )
        ]
    raw_turn_sources = canonical_sources
    sanitized_turn_sources = sanitize_sources(raw_turn_sources)
    from app.services.source_verification import source_records
    verification_sources = source_records(raw_turn_sources)
    source_verification = None

    def enqueue_verification(**options):
        from app.services.source_check_jobs import submit_advisory
        references = []
        if validated_chat_turn_ids:
            references.append(f"users/{uid}/chats/{validated_chat_turn_ids[0]}")
        bookmark_id = str(data.get('bookmarkId') or '')
        if re.fullmatch(r'[A-Za-z0-9_-]{1,160}', bookmark_id):
            references.append(f'users/{uid}/bookmarks/{bookmark_id}')
        context = dict(uid=uid, run_key=str(data.get('usage_run_key') or
            (':'.join(validated_chat_turn_ids) if validated_chat_turn_ids else hashlib.sha256(
                (question + options['consensus'] + str(time.time_ns())).encode()).hexdigest())),
            own_keys=use_own_keys, references=references, origin='interactive')
        return submit_advisory(**options, context=context)

    def record_run_stats(differences_data):
        # Anonyme Differences-Telemetrie (keine Texte, keine UID — siehe
        # app/services/differences_stats.py). Mock-Läufe (E2E) schreiben nicht.
        if differences_data is None or mock_llm_enabled():
            return
        if result_provenance != answer_receipts.PROVENANCE_DEVELOPER:
            # BYOK answers are real calls, but on a key the service does not
            # control: they never feed model statistics or rankings (R09).
            return
        record_differences_stats(
            differences_data,
            consensus_model=consensus_model,
            model_labels=model_labels,
            excluded_count=len(excluded_models),
            is_pro_user=bool(is_pro),
            used_own_keys=bool(use_own_keys),
            question_word_count=count_words(question),
        )

    def persist_share_result(consensus_text, differences_data, differences_text):
        # Mock-Modus (E2E-Tests) darf keine pending_results in das echte
        # Firestore schreiben.
        if not share_uid or mock_llm_enabled():
            return None
        return persist_pending_result(
            uid=share_uid,
            question=question,
            consensus_md=consensus_text,
            differences_data=differences_data,
            differences_text=differences_text,
            model_sources=model_sources,
            included_providers=list(included_answers.keys()),
            model_labels=model_labels,
            consensus_model=consensus_model,
            model_responses=included_answers,
            source_verification=source_verification,
            answer_provenance=result_provenance,
        )

    def persist_chat_completion(
        consensus_text,
        differences_text,
        differences_data,
        result_id,
    ) -> bool:
        if validated_chat_turn_ids is None:
            return False
        chat_id, turn_id = validated_chat_turn_ids
        try:
            chat_store.complete_turn(
                uid,
                chat_id,
                turn_id,
                question=question,
                model_answers=chat_model_answers,
                consensus=consensus_text,
                differences=differences_text,
                differences_data=differences_data,
                sources=sanitized_turn_sources,
                result_id=result_id,
                source_verification=source_verification,
            )
            return True
        except Exception as exc:
            # The LLM result is authoritative for the UI. Keep the pending turn
            # retryable and report only identifiers/state, never content/keys.
            logging.error(
                "chat turn completion failed chat_id=%s turn_id=%s category=%s",
                chat_id,
                turn_id,
                safe_exception(exc),
            )
            return False

    def persist_consensus_bookmark(
        consensus_text,
        differences_text,
        differences_data,
        result_id,
        *,
        chat_persisted: bool,
    ) -> Optional[dict]:
        """Write the sidebar bookmark before the successful result is sent.

        Bookmarking used to start only after the browser received the final
        consensus event. A closed tab, lost connection, or a rejected legacy
        copy could therefore leave a completed run without its bookmark. The
        consensus handler already owns every trusted field, so it is the
        reliable primary writer; ``/bookmark/consensus`` remains the retry and
        cached-client compatibility path.
        """
        bookmark_id = str(data.get("bookmarkId") or "").strip()
        if not bookmark_id:
            return None
        bookmark_data = {
            "question": question,
            "bookmarkId": bookmark_id,
            "resultId": result_id,
            "previousQuestion": data.get("previousQuestion") or "",
            "previousTurn": data.get("previousTurn"),
        }
        if chat_persisted and validated_chat_turn_ids is not None:
            bookmark_data.update({
                "chatId": validated_chat_turn_ids[0],
                "turnId": validated_chat_turn_ids[1],
            })
        authoritative = {
            "question": question,
            "consensus": consensus_text,
            "differences": differences_text,
            "differences_data": differences_data,
            "sources": sanitized_turn_sources,
            "source_verification": source_verification,
            "included_models": [
                f"{provider}: {allowed_model_labels.get(provider, provider)}"
                for provider in included_answers
            ],
            "model_labels": allowed_model_labels,
            "consensus_model": consensus_model,
            "model_responses": included_answers,
            "vote_subject_id": result_id or "bookmark:" + bookmark_id,
            "result_id": result_id or "",
        }
        try:
            # Local import avoids coupling router import order while keeping the
            # shared mutation contract in the bookmark module.
            from app.api.routers.bookmarks import (
                _bookmark_meta,
                persist_authoritative_consensus_bookmark,
            )

            bookmark = persist_authoritative_consensus_bookmark(
                uid, bookmark_data, authoritative
            )
            return _bookmark_meta(bookmark["id"], bookmark)
        except Exception as exc:
            logging.error(
                "consensus bookmark primary write failed category=%s",
                safe_exception(exc),
            )
            return None

    def add_bookmark_result_fields(
        payload: dict,
        consensus_text,
        differences_text,
        differences_data,
        result_id,
        *,
        chat_persisted: bool,
    ) -> None:
        if not str(data.get("bookmarkId") or "").strip():
            return
        bookmark_meta = persist_consensus_bookmark(
            consensus_text,
            differences_text,
            differences_data,
            result_id,
            chat_persisted=chat_persisted,
        )
        payload["bookmark_persisted"] = bookmark_meta is not None
        if bookmark_meta is not None:
            payload["bookmark_meta"] = bookmark_meta

    def add_chat_result_fields(
        payload: dict,
        *,
        persisted: bool,
        state: str,
    ) -> None:
        if validated_chat_turn_ids is None:
            return
        payload.update(
            _chat_turn_disposition(
                validated_chat_turn_ids,
                state,
                persisted=persisted,
            )
        )

    if stream_requested:
        extra_fields = {}
        if usage_result is not None:
            extra_fields = usage_response_fields(None, tier)
            extra_fields["usage_run_status"] = usage_result.status.value
        elif use_own_keys:
            extra_fields = own_key_usage_fields(tier)

        @analysis_budgeted
        def consensus_event_source():
            nonlocal source_verification
            consensus_text = ""
            consensus_failed = False
            consensus_state = completion.COMPLETE
            differences_text = ""
            differences_data = None
            stream_failed = False
            # Reasoning-Marker der Engines gedrosselt weiterleiten (max. alle
            # 2 s, wie im /ask_*-Streaming): hält die Verbindung aktiv und
            # lässt das Frontend "Reasoning" statt eines stummen Spinners zeigen.
            last_reasoning_at = None

            def _reasoning_event(event_name):
                nonlocal last_reasoning_at
                now = time.monotonic()
                if last_reasoning_at is not None and now - last_reasoning_at < 2.0:
                    return None
                last_reasoning_at = now
                return sse_pack(event_name, {"reasoning": True})

            try:
                for item in stream_consensus(
                    question,
                    included_by_provider,
                    excluded_models,
                    consensus_model,
                    api_keys,
                    model_sources=model_sources,
                    resolved_question=resolved_question,
                ):
                    if item.get("type") == "delta":
                        text = coerce_text(item.get("text"))
                        if text:
                            yield sse_pack("consensus.delta", {"text": text})
                    elif item.get("type") == "reasoning":
                        event = _reasoning_event("consensus.delta")
                        if event:
                            yield event
                    elif item.get("type") == "reset":
                        # A failed attempt's visible deltas are discarded
                        # before a retry; attempts never mix in one text.
                        yield sse_pack("consensus.reset", {"reset": True})
                    else:
                        consensus_text = coerce_text(item.get("text"))
                        consensus_failed = bool(item.get("error")) or is_consensus_error_text(consensus_text)
                        consensus_state = (
                            item["completion"] if item.get("completion") in completion.STATES
                            else completion.ERROR if consensus_failed else completion.COMPLETE
                        )

                if consensus_failed:
                    # Ohne Konsensantwort ist der Vergleich sinnlos: der Judge
                    # würde sonst den Fehlertext "analysieren" und das Ergebnis
                    # würde als Share-Snapshot persistiert.
                    differences_text = DIFFERENCES_SKIPPED_TEXT
                    differences_data = None
                else:
                    # Consensus completion is its own successful phase. Send
                    # the authoritative text before the slower Differences
                    # judge so a later mobile/network interruption cannot
                    # erase an answer the user already received.
                    yield sse_pack("consensus.final", {"text": consensus_text})
                    if not check_sources:
                        from app.services.source_check_jobs import disabled_snapshot
                        source_verification = disabled_snapshot(consensus_text)
                    last_reasoning_at = None
                    # Die Analyse hat ihren EIGENEN Fehlerrahmen. Sie laeuft
                    # erst, nachdem die Antwort den Nutzer erreicht hat -- ein
                    # Fehler hier darf den Lauf deshalb nicht mehr als
                    # gescheitert markieren und die Antwort nicht mehr aus der
                    # Persistenz halten. Der Lauf verliert dann seine Marken
                    # und Widerspruchskarten, aber nicht die Antwort.
                    differences_complete = False
                    try:
                        differences_stream = stream_differences(
                            included_by_provider,
                            consensus_text,
                            api_keys,
                            differences_model=consensus_model,
                            excluded_models=excluded_models,
                            resolved_question=resolved_question,
                        )
                        for item in differences_stream:
                            if item.get("type") == "source_verification":
                                source_verification = item["data"]
                                yield sse_pack("sources.final", {"source_verification": source_verification})
                            elif item.get("type") == "delta":
                                # Das Frontend rendert diese Deltas nicht mehr (die Engine
                                # liefert JSON); sie halten nur die SSE-Verbindung aktiv.
                                text = coerce_text(item.get("text"))
                                if text:
                                    yield sse_pack("differences.delta", {"text": text})
                            elif item.get("type") == "reasoning":
                                event = _reasoning_event("differences.delta")
                                if event:
                                    yield event
                            else:
                                differences_text = coerce_text(item.get("text"))
                                differences_data = item.get("data")
                                differences_complete = not item.get("error", False)
                                yield sse_pack("differences.final", {
                                    "differences": differences_text,
                                    "differences_data": differences_data,
                                })
                        # The accepted plan is based on the successful structured
                        # Differences result. Fetches and the evidence judge run
                        # in durable workers, after the answer was delivered.
                        if check_sources:
                            if differences_complete and isinstance(differences_data, dict):
                                source_verification = enqueue_verification(
                                    question=question, consensus=consensus_text,
                                    sources=verification_sources, keys=api_keys,
                                    resolved_question=resolved_question,
                                    differences_data=differences_data,
                                    model_answers=included_by_provider, model_sources=model_sources,
                                )
                            else:
                                from app.services.consensus_pipeline import _differences_check_failed
                                source_verification = _differences_check_failed(consensus_text)
                            yield sse_pack("sources.final", {"source_verification": source_verification})
                    except GeneratorExit:
                        raise
                    except Exception as exc:
                        logging.error(
                            "Differences analysis failed category=%s at=%s",
                            safe_exception(exc), safe_traceback(exc),
                        )
                        if not differences_complete:
                            differences_text = ""
                            differences_data = None
                            yield sse_pack("differences.final", {
                                "differences": "", "differences_data": None, "error": True,
                            })
                        if check_sources:
                            from app.services.consensus_pipeline import _differences_check_failed
                            source_verification = _differences_check_failed(consensus_text)
                            yield sse_pack("sources.final", {"source_verification": source_verification})
            except GeneratorExit:
                consensus_state = completion.CANCELLED
                _fail_chat_turn_best_effort(
                    uid,
                    validated_chat_turn_ids,
                    error_code="cancelled",
                )
                raise
            except Exception as exc:
                # Frames statt Message: die Kategorie allein liess einen
                # unerwarteten internen Fehler hier bisher nicht auffindbar
                # werden (siehe observability.safe_traceback).
                logging.error(
                    "Consensus streaming failed category=%s at=%s",
                    safe_exception(exc), safe_traceback(exc),
                )
                stream_failed = True
                if not consensus_text:
                    consensus_text = (
                        "Consensus could not complete this request. "
                        "Please try again later."
                    )
                if not differences_text:
                    differences_text = ""

            payload = {
                "consensus_response": consensus_text,
                "consensus_completion": consensus_state,
                "differences": differences_text,
                "differences_data": differences_data,
                "source_verification": source_verification,
            }
            if stream_failed and consensus_state == completion.COMPLETE:
                payload["consensus_completion"] = completion.ERROR
            incomplete = consensus_failed and consensus_state in completion.INCOMPLETE_STATES
            if incomplete:
                payload.update(_incomplete_consensus_fields(consensus_state))
            result_id = None
            chat_persisted = False
            chat_turn_state = "pending"
            if not stream_failed and not consensus_failed:
                record_run_stats(differences_data)
                result_id = persist_share_result(consensus_text, differences_data, differences_text)
                if result_id:
                    payload["result_id"] = result_id
                chat_persisted = persist_chat_completion(
                    consensus_text,
                    differences_text,
                    differences_data,
                    result_id,
                )
                if chat_persisted:
                    chat_turn_state = "completed"
            else:
                failed = _fail_chat_turn_best_effort(
                    uid,
                    validated_chat_turn_ids,
                    error_code="consensus_incomplete" if incomplete else "consensus_failed",
                )
                if failed:
                    chat_turn_state = "failed"
            add_chat_result_fields(
                payload,
                persisted=chat_persisted,
                state=chat_turn_state,
            )
            if not stream_failed and not consensus_failed:
                add_bookmark_result_fields(
                    payload,
                    consensus_text,
                    differences_text,
                    differences_data,
                    result_id,
                    chat_persisted=chat_persisted,
                )
            payload.update(extra_fields)
            if booking is not None:
                payload.update(booking.extras())
            yield sse_pack("final", payload)

        # Keepalive-Wrapper: schiebt SSE-Kommentare ein, wenn die Engines
        # (z. B. ein denkender Reasoning-Judge) länger keine Bytes liefern —
        # sonst trennt Cloudflare idle Verbindungen und das final-Event geht
        # verloren (Spinner bliebe für immer stehen). metered_events bindet den
        # Token-Zaehler im Pump-Thread und bucht auch bei Abbruch.
        events = consensus_event_source()
        return keepalive_streaming_response(
            metered_events(events, booking) if booking is not None else events
        )

    try:
        with (booking.metering() if booking is not None else contextlib.nullcontext()):
            analysis = analyze_provider_answers(
                question=question,
                answers=included_by_provider,
                consensus_model=consensus_model,
                keys=api_keys,
                model_sources=model_sources,
                resolved_question=resolved_question,
                synthesize=query_consensus,
                judge=query_differences,
                allow_consensus_error=True,
                skipped_differences_text=DIFFERENCES_SKIPPED_TEXT,
                require_differences_data=False,
                verification_sources=verification_sources,
                check_sources=check_sources,
                verification_submit=enqueue_verification,
            )
        consensus_answer = analysis.consensus
        consensus_failed = is_consensus_error_text(consensus_answer)
        differences = analysis.differences_text
        differences_data = analysis.differences_data
        source_verification = analysis.source_verification
    except Exception as exc:
        if booking is not None:
            # Calls that already ran are spent even though the analysis failed.
            booking.finish()
        failed = _fail_chat_turn_best_effort(
            uid,
            validated_chat_turn_ids,
            error_code="consensus_failed",
        )
        if validated_chat_turn_ids is not None:
            raise HTTPException(
                status_code=500,
                detail=_chat_turn_error_detail(
                    "Consensus generation failed.",
                    validated_chat_turn_ids,
                    "failed" if failed else "pending",
                    persisted=False,
                ),
            ) from exc
        raise

    incomplete = consensus_answer == CONSENSUS_INCOMPLETE_TEXT
    response = {
        "consensus_response": consensus_answer,
        "consensus_completion": (
            completion.TOKEN_LIMIT if incomplete
            else completion.ERROR if consensus_failed else completion.COMPLETE
        ),
        "differences": differences,
        "differences_data": differences_data,
        "source_verification": source_verification,
    }
    if incomplete:
        response.update(_incomplete_consensus_fields(completion.TOKEN_LIMIT))
    chat_persisted = False
    chat_turn_state = "pending"
    result_id = None
    if not consensus_failed:
        record_run_stats(differences_data)
        result_id = persist_share_result(consensus_answer, differences_data, differences)
        if result_id:
            response["result_id"] = result_id
        chat_persisted = persist_chat_completion(
            consensus_answer,
            differences,
            differences_data,
            result_id,
        )
        if chat_persisted:
            chat_turn_state = "completed"
    else:
        failed = _fail_chat_turn_best_effort(
            uid,
            validated_chat_turn_ids,
            error_code="consensus_incomplete" if incomplete else "consensus_failed",
        )
        if failed:
            chat_turn_state = "failed"
    add_chat_result_fields(
        response,
        persisted=chat_persisted,
        state=chat_turn_state,
    )
    if not consensus_failed:
        add_bookmark_result_fields(
            response,
            consensus_answer,
            differences,
            differences_data,
            result_id,
            chat_persisted=chat_persisted,
        )
    if usage_result is not None:
        response.update(usage_response_fields(None, tier))
        response["usage_run_status"] = usage_result.status.value
        response.update(booking.extras())
    elif use_own_keys:
        response.update(own_key_usage_fields(tier))
    return response


def _persist_resolve_bookmark(uid: str, data: dict, claim: str, positions: list, result: dict) -> bool:
    """Attach a server-produced resolution to the exact bookmark revision."""
    bookmark_id = str(data.get("bookmarkId") or "").strip()
    expected_version = str(data.get("expectedBookmarkVersion") or "").strip().lower()
    if not re.fullmatch(r"[A-Za-z0-9_]{1,100}", bookmark_id):
        return False
    if not re.fullmatch(r"[0-9a-f]{64}", expected_version):
        return False

    # One revision algorithm serves Share and Resolve. The local import avoids
    # coupling router import order.
    from app.api.routers.bookmarks import _bookmark_share_version

    doc_ref = (
        db_firestore.collection("users").document(uid)
        .collection("bookmarks").document(bookmark_id)
    )
    snapshot = doc_ref.get()
    if not snapshot.exists:
        return False
    bookmark = snapshot.to_dict() or {}
    if not hmac.compare_digest(expected_version, _bookmark_share_version(bookmark)):
        return False
    responses = bookmark.get("responses")
    responses = deepcopy(responses) if isinstance(responses, dict) else {}
    differences_data = responses.get("differences_data")
    if not isinstance(differences_data, dict):
        return False
    differences = differences_data.get("differences")
    if not isinstance(differences, list):
        return False

    match = None
    for difference in differences:
        if not isinstance(difference, dict):
            continue
        try:
            stored_claim, stored_positions = normalize_resolve_positions(
                difference.get("claim"), difference.get("positions")
            )
        except InvalidResolvePayload:
            continue
        if stored_claim == claim and stored_positions == positions:
            if match is not None:
                return False
            match = difference
    if match is None:
        return False

    match["resolution"] = {
        "outcome": str(result.get("outcome") or "error"),
        "results": [
            {
                "model": str(item.get("model") or ""),
                "decision": str(item.get("decision") or "error"),
                "position": str(item.get("position") or ""),
                "reason": str(item.get("reason") or ""),
            }
            for item in result.get("results", []) if isinstance(item, dict)
        ],
    }
    sanitized = sanitize_differences_data(differences_data)
    if sanitized is None:
        return False
    responses["differences_data"] = sanitized

    try:
        persistence_guard.write_bookmark(
            uid=uid,
            doc_ref=doc_ref,
            patch={"responses": responses, "share_result_id": ""},
            db=db_firestore,
            # Recheck inside the same quota transaction that applies the patch.
            current_guard=lambda current: hmac.compare_digest(
                expected_version, _bookmark_share_version(current)
            ),
        )
    except (persistence_guard.PersistenceConflictError, persistence_guard.PersistenceLimitError):
        return False
    except Exception as exc:
        logging.error("Resolve bookmark persistence failed category=%s", safe_exception(exc))
        return False
    return True


@router.post("/resolve")
@limiter.limit("3/minute")
def resolve(request: Request, data: dict = Body(...)):
    """Resolve-Runde: konfrontiert die dissentierenden Modelle eines
    Widerspruchs (aus differences_data) gezielt mit der Gegenposition.
    Bucht ihre gemessenen Tokens auf das Tageskonto; bei exakter Bookmark-Bindung wird das
    serverseitige Ergebnis versionsgeschuetzt persistiert."""
    id_token = extract_id_token(request, data)
    use_own_keys = parse_boolean_flag(data.get("useOwnKeys", False))

    if not id_token:
        raise HTTPException(
            status_code=401,
            detail=OWN_KEYS_LOGIN_REQUIRED if use_own_keys else "Authentication required",
        )
    try:
        uid = verify_user_token(id_token)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")
    try:
        tier = get_user_tier(uid)
    except TierStatusUnavailable:
        raise HTTPException(
            status_code=503,
            detail="Account tier is temporarily unavailable. Please retry.",
        ) from None
    entitlements = entitlements_for(tier)

    # Resolve ist ab Plus freigeschaltet; Free-Nutzer sehen den Button nur als
    # Teaser. Die Runde laeuft auf dem Standard-Judge, kostet also keinen
    # Frontier-Preis -- deshalb darf Plus sie testen. Serverseitig gilt das Gate
    # auch mit eigenen Keys (wie bei Deep Think).
    if not entitlements.resolve:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "Resolve rounds need Plus or Pro.",
                "error_code": "plus_required",
            },
        )

    question = validate_text_size(
        data.get("question"),
        label="Question",
        max_chars=min(MAX_QUESTION_CHARS, cfg.get_consensus_question_char_limit()),
        max_bytes=MAX_QUESTION_BYTES,
        required=True,
    )
    if not isinstance(question, str) or not question.strip():
        raise HTTPException(status_code=400, detail="Missing 'question' in request body.")

    try:
        claim, positions = normalize_resolve_positions(data.get("claim"), data.get("positions"))
    except InvalidResolvePayload as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    usage_result = None
    booking = None
    if not use_own_keys:
        # A Resolve round is a few judge calls: it is admitted against the
        # smaller Compare estimate and booked with its measured tokens.
        usage_result, _admission = authorize_usage_operation(
            uid,
            data,
            "resolve",
            {
                "schema": 1,
                "question": question,
                "claim": claim,
                "positions": positions,
            },
            tier=tier, deep_think=False, purpose="resolve", mode="compare",
        )
        booking = operation_booking(uid, data, "resolve", final=True)

    api_keys = build_engine_api_keys(data, use_own_keys)

    try:
        with (booking.metering() if booking is not None else contextlib.nullcontext()):
            result = run_resolve_round(question, claim, positions, api_keys)
    finally:
        if booking is not None:
            booking.finish()
    result["bookmark_persisted"] = _persist_resolve_bookmark(
        uid, data, claim, positions, result
    )
    if usage_result is not None:
        result.update(usage_response_fields(booking.token_budget, tier))
        result["usage_run_status"] = usage_result.status.value
    else:
        result.update(own_key_usage_fields(tier))
    return result

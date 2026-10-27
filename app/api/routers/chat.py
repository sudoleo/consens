import time
import logging
import hashlib
from dataclasses import dataclass
from typing import Optional

from fastapi import APIRouter, Request, Body, HTTPException
from google.api_core.exceptions import Aborted as FirestoreAborted

from app.core.rate_limit import limiter
from app.core.observability import record_metric, safe_exception
from app.core.entitlements import TIER_FREE, entitlements_for
from app.core.security import (
    TierStatusUnavailable,
    db_firestore,
    extract_id_token,
    get_user_tier,
    verify_user_token,
    AuthenticationUnavailable,
    auth_unavailable_error,
)
import app.core.config as cfg
from app.services.llm.attachments import parse_attachments
from app.services.llm.base import (
    count_words,
    get_system_prompt,
    validate_model,
)
from app.services.llm.engines import query_model
from app.services.llm.citations import source_response
from app.services.llm.credentials import openrouter_api_key, resolve_developer_api_keys
from app.services.llm.mock_llm import mock_ask_result, mock_ask_stream, mock_llm_enabled
from app.services.llm.provider_runtime import ProviderCancelled
from app.services.llm.streaming import (
    streaming_model_response,
    stream_model_query,
)
from app.services import user_memory
from app.services.user_memory import FirestoreUserMemoryRepository
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
from app.services import user_settings

router = APIRouter()

OWN_KEYS_LOGIN_REQUIRED = "Please log in to use your own API keys."
MAX_QUESTION_CHARS = 8_000
MAX_QUESTION_BYTES = 16_000
# A run carries the account's saved system prompt behind the app's date line
# (query-send.js), so every prompt the account can keep is one a run accepts.
MAX_SYSTEM_PROMPT_CHARS = user_settings.MAX_SYSTEM_PROMPT_CHARS + user_settings.SYSTEM_PROMPT_DATE_LINE_RESERVE
MAX_SYSTEM_PROMPT_BYTES = user_settings.MAX_SYSTEM_PROMPT_BYTES + user_settings.SYSTEM_PROMPT_DATE_LINE_RESERVE
run_usage_repository = FirestoreUsageRepository(db_firestore)
user_memory_repository = FirestoreUserMemoryRepository(db_firestore)


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
        # is_pro_user bleibt das Modell-Flag (Plus -> False);
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
            "Today’s allowance doesn’t cover another run. "
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
    planned_operations: Optional[int] = None,
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
            planned_operations=planned_operations,
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


def validate_question_word_limit(question: str, tier, deep_search: bool = False):
    """Word limit of a question. Since 2026-10-02 it no longer depends on the
    Reasoning switch (``deep_search``); the argument stays for callers."""
    question = validate_text_size(
        question,
        label="Question",
        max_chars=MAX_QUESTION_CHARS,
        max_bytes=MAX_QUESTION_BYTES,
        required=True,
    )

    max_words_limit = cfg.get_word_limit(tier)
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


def _run_ask(provider: AskProvider, *, stream_requested, question, key,
             system_prompt, deep_search, model, max_tokens, attachments, extras,
             booking: Optional[OperationBooking] = None):
    """Fuehrt den Provider-Call aus (streamend oder nicht) und verpackt das
    Ergebnis im bisherigen Response-Format."""
    if mock_llm_enabled():
        # E2E-Suite: deterministischer Fixture-Stream statt Provider-Call.
        # Auth/Limits/Validierung sind zu diesem Zeitpunkt bereits gelaufen.
        if stream_requested:
            source = mock_ask_stream(provider.label, question)
            return streaming_model_response(
                metered_events(source, booking) if booking else source,
                provider.label, extras,
            )
        if booking is None:
            return source_response(mock_ask_result(provider.label, question), **extras)
        with booking.metering():
            result = mock_ask_result(provider.label, question)
        return source_response(result, **extras, **booking.extras())

    kwargs = {
        "system_prompt": system_prompt,
        "deep_search": deep_search,
        "model_override": model,
        "max_output_tokens": max_tokens,
        "attachments": attachments,
    }
    if stream_requested:
        source = stream_model_query(provider.key, question, key, **kwargs)

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
            result = query_model(provider.key, question, key, **kwargs)
        else:
            try:
                with booking.metering():
                    result = query_model(provider.key, question, key, **kwargs)
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
    # ``deep_search`` is the kept wire name of the Reasoning switch (formerly
    # Deep Think): same model, more reasoning, larger output cap. No tier gate.
    deep_search = parse_boolean_flag(data.get("deep_search", False))
    stream_requested = parse_boolean_flag(data.get("stream", False))
    system_prompt = validate_client_system_prompt(data.get("system_prompt"))
    id_token = extract_id_token(request, data)
    api_key = str(data.get("openrouter_key") or "").strip()
    model = data.get("model")
    if isinstance(model, str) and model:
        # A request may still carry a migrated ID (grok-4.3-no-reasoning,
        # 2026-10-11); it would otherwise fail the allowlist below.
        model = cfg.canonical_model_id(model, provider.key)

    tier = TIER_FREE
    entitlements = entitlements_for(tier)
    uid = None

    if id_token:
        try:
            uid = verify_user_token(id_token)
        except AuthenticationUnavailable:
            raise auth_unavailable_error() from None
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

    # is_pro_user heisst weiterhin "darf Frontier-Modelle".
    # Plus ist hier False und faehrt damit exakt die Free-Modellauswahl.
    is_pro_user = entitlements.is_pro

    question = validate_question_word_limit(question, tier)
    validate_model(
        model,
        provider.allowed_models,
        provider.label,
        is_pro=is_pro_user,
    )
    # Files need an account: their tokens are booked to it.
    attachments = parse_attachments(data, attachments_allowed=entitlements.attachments and uid is not None)
    model_config = cfg.get_model_config(model, provider.key)
    if attachments and model_config and not model_config.accepts_attachments:
        raise HTTPException(
            status_code=400,
            detail=f"{model_config.label} cannot read attachments.",
        )
    max_tokens = cfg.get_output_token_limit(tier, deep_search)

    # Das nutzereigene Gedaechtnis. Es haengt an der Basisanweisung, NICHT im
    # Datenteil: es ist eine stehende Praeferenz des Nutzers, kein
    # Gespraechsinhalt.
    #
    # Ausschliesslich hier: Watch-Reruns, Publisher- und Topic-Laeufe rufen
    # engines.py direkt und duerfen kein Profil sehen, sonst driftet eine
    # Watch-Baseline mit dem Profil statt mit der Welt.
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

    # A question continues no chat here: since 2026-10-25 the browser asks
    # /ask_* only for Compare (side by side, a chat of its own). Follow-ups
    # run in Agent (/agent), whose context the server keeps.
    own_keys_requested = parse_boolean_flag(data.get("useOwnKeys", False))

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


def _planned_answers(value) -> Optional[int]:
    """How many /ask_* answers the run will book (``operations`` of /prepare).

    With it the last answer's booking drops the run's leftover admission hold;
    without (older browsers, nonsense) the hold expires as before.
    """
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value if 1 <= value <= cfg.MAX_RUN_FAMILIES else None


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
    except AuthenticationUnavailable:
        raise auth_unavailable_error() from None
    except HTTPException as he:
        raise he
    except Exception as exc:
        logging.error("Auth failed in /prepare category=%s", safe_exception(exc))
        raise HTTPException(status_code=401, detail="Authentication failed.")

    validate_question_word_limit(question, tier)
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
        # cost of a typical run of this mode (Compare, with or without
        # Reasoning).
        usage_key, reserved, admission = reserve_usage_run(
            uid, data, tier=tier, deep_think=deep_think, mode=data.get("run_mode"),
            planned_operations=_planned_answers(data.get("operations")),
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

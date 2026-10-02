"""Persistente Run-Belege der Consensus-Pipeline auf dem gemeinsamen Tokenkonto.

Ein logischer Lauf (``usage_run_key``) ist weiterhin genau ein Beleg: er bindet
Idempotenz, Request-Fingerprint, Operations-Claims und Chat-Kontext. Gezaehlt
werden aber keine Runs mehr, sondern Tokens auf demselben Tageskonto wie Agent
(``agent_quota``; Limit nach Kontostufe aus ``agent_budget_config``):

* **Admission:** ein neuer Lauf startet nur, wenn das freie Budget die
  erwarteten Kosten eines typischen Laufs dieses Modus deckt (Compare,
  Consensus, Deep Think). Der Lauf haelt diese Schaetzung kurz gegen parallele
  Admissions (``pipeline_holds`` im Kontodokument), reserviert aber nichts pro
  Call.
* **Buchung:** jede abgeschlossene Operation (``ask:<familie>``, ``consensus``,
  ``resolve``, API ``pipeline``) bucht ihre gemessenen Tokens genau einmal
  (``booked_operations``). Fehlt die Messung, bucht sie dieselbe begrenzte
  Schaetzung wie Agent. Ein Lauf darf das Konto dabei leicht ueberziehen.

Firestore-Datenmodell (unter ``users/{uid}``):

* ``usage_runs/{sha256(idempotency_key)}`` enthaelt Run-Typ, UTC-Tag, Ablauf,
  kanonischen Request-Fingerprint, Status, Operations-Claims, die Konto-Periode
  der Admission (``quota_day``), Stufe/Modus/Schaetzung und die gebuchten
  Operationen. ``utc_date`` ist der Admissionstag; ``expires_at`` die davon
  getrennte Ausfuehrungs-/Retry-Gueltigkeit (mindestens bis Tagesende und
  ``MIN_EXECUTION_WINDOW``).
* ``chat_state/agent_tokens_{periode}`` ist das gemeinsame Kontodokument.

Statusuebergaenge bleiben ``reserved -> consumed`` oder ``reserved ->
released``; beide terminal. Kostenpflichtige Arbeit darf erst nach ``consume``
und einem erfolgreichen Operations-Claim beginnen; Provider-Aufrufe gehoeren
niemals in eine Firestore-Transaktion.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta, timezone
from enum import Enum
from typing import Callable, Protocol, TypeVar

from firebase_admin import firestore

from app.services import agent_budget_config, agent_quota, persistence_guard


USAGE_RUNS_COLLECTION = "usage_runs"
USAGE_SCHEMA_VERSION = 3
MAX_IDEMPOTENCY_KEY_BYTES = 256
MAX_OPERATION_NAME_BYTES = 80
FINGERPRINT_HEX_LENGTH = 64
MAX_BOOKED_OPERATIONS = 32
# Execution validity of an already admitted run, independent of its billing day.
MIN_EXECUTION_WINDOW = timedelta(hours=2)


def execution_expiry(now: datetime) -> datetime:
    """Bounded execution/retry validity of a run reserved at ``now`` (UTC)."""
    end_of_billing_day = datetime.combine(
        now.date() + timedelta(days=1), time.min, tzinfo=timezone.utc
    )
    return max(end_of_billing_day, now + MIN_EXECUTION_WINDOW)


class RunKind(str, Enum):
    REGULAR = "regular"
    DEEP_THINK = "deep_think"


class RunStatus(str, Enum):
    RESERVED = "reserved"
    CONSUMED = "consumed"
    RELEASED = "released"


@dataclass(frozen=True)
class TokenAdmission:
    """What a new run must find on the account before it may start."""

    tier: str
    mode: str
    limit: int
    estimate: int
    period: str
    config: dict = field(compare=False, repr=False)

    def __post_init__(self) -> None:
        for label, value in (("limit", self.limit), ("estimate", self.estimate)):
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ValueError(f"{label} must be a positive integer")
        if self.mode not in agent_budget_config.RUN_MODES:
            raise ValueError("Unsupported run mode")


def token_admission(db, tier: str, *, mode: str | None = None, deep_think: bool = False) -> TokenAdmission:
    """Admission parameters for one run of ``tier`` (a ledger tier incl. admin)."""
    config = agent_budget_config.get_config(db)
    tier = agent_budget_config.tier_key(tier)
    run_mode = agent_budget_config.run_mode(mode, deep_think=deep_think)
    return TokenAdmission(
        tier=tier, mode=run_mode,
        limit=agent_budget_config.limit_for(config, tier),
        estimate=agent_budget_config.run_estimates_for(config, tier)[run_mode],
        period=agent_quota.period_key(config), config=config,
    )


@dataclass(frozen=True)
class UsageRunResult:
    uid: str
    idempotency_hash: str
    kind: RunKind
    status: RunStatus
    utc_date: str
    token_budget: dict | None
    idempotent: bool


@dataclass(frozen=True)
class UsageOperationClaim:
    uid: str
    idempotency_hash: str
    operation: str
    request_fingerprint: str
    claimed_at: datetime
    expires_at: datetime
    idempotent: bool


class UsageRepositoryError(Exception):
    """Basisklasse fuer erwartbare Usage-Repository-Fehler."""


class UsageLimitExceeded(UsageRepositoryError):
    """The remaining tokens do not cover the expected cost of this run."""

    limiting_bucket = "tokens"

    def __init__(self, *, uid: str, kind: RunKind, utc_date: str, token_budget: dict, required: int):
        super().__init__("daily token allowance does not cover this run")
        self.uid = uid
        self.kind = kind
        self.utc_date = utc_date
        self.token_budget = token_budget
        self.required = required


class UsageCapacityExceeded(UsageRepositoryError):
    """Too many young runs on one account at once."""


class UsageRunNotFound(UsageRepositoryError):
    pass


class UsageRunConflict(UsageRepositoryError):
    pass


class UsageOperationConflict(UsageRunConflict):
    """An operation payload conflicts, rather than the logical run."""


class UsageRunReleased(UsageRepositoryError):
    pass


class UsageTransitionError(UsageRepositoryError):
    pass


class UsageRunExpired(UsageRepositoryError):
    pass


class UsageOperationAlreadyClaimed(UsageRepositoryError):
    pass


class UsageDataError(UsageRepositoryError):
    pass


class UsageRepository(Protocol):
    def authorize_operation(
        self, uid: str, idempotency_key: str, kind: RunKind,
        admission: TokenAdmission, operation: str, operation_fingerprint: str,
        *, request_fingerprint: str, now: datetime | None = None,
    ) -> tuple[UsageRunResult, UsageOperationClaim]: ...

    def reserve(
        self, uid: str, idempotency_key: str, kind: RunKind, admission: TokenAdmission,
        *, request_fingerprint: str | None = None, now: datetime | None = None,
    ) -> UsageRunResult: ...

    def consume(self, uid: str, idempotency_key: str) -> UsageRunResult: ...

    def release(self, uid: str, idempotency_key: str) -> UsageRunResult: ...

    def book_operation(
        self, uid: str, idempotency_key: str, operation: str, *,
        measured: int, estimated: int, final: bool = False, now: datetime | None = None,
    ) -> dict: ...

    def get_run(self, uid: str, idempotency_key: str, *, now: datetime | None = None) -> UsageRunResult: ...

    def bind_context_target(
        self, uid: str, idempotency_key: str, target_scope: str, *, now: datetime | None = None,
    ) -> None: ...

    def claim_operation(
        self, uid: str, idempotency_key: str, operation: str, request_fingerprint: str,
        *, now: datetime | None = None,
    ) -> UsageOperationClaim: ...

    def token_budget(self, uid: str, admission: TokenAdmission, *, now: datetime | None = None) -> dict: ...


T = TypeVar("T")
TransactionRunner = Callable[[Callable[[object], T]], T]


class FirestoreUsageRepository:
    """Firestore-Implementierung mit atomarer Admission und Buchung.

    ``transaction_runner`` ist ein Test-Seam. In Produktion wird immer der
    Retry-faehige ``firebase_admin.firestore.transactional``-Wrapper benutzt.
    """

    def __init__(self, db, *, transaction_runner: TransactionRunner | None = None):
        self._db = db
        self._transaction_runner = transaction_runner

    # --- Admission -----------------------------------------------------------

    def admission(self, tier: str, *, mode: str | None = None, deep_think: bool = False) -> TokenAdmission:
        """Admission parameters from the same database as the account."""
        return token_admission(self._db, tier, mode=mode, deep_think=deep_think)

    def account_snapshot(self, uid: str, tier: str) -> dict:
        """The account as Agent reports it (with Agent's allowance repairs)."""
        return agent_quota.snapshot(self._db, _validate_uid(uid), tier=tier)

    def _admit(self, tx, uid, key_hash, kind, admission, now):
        """Read the account and admit one new run (no writes yet)."""
        ledger_ref = agent_quota.quota_ref(self._db, uid, admission.period)
        ledger = ledger_ref.get(transaction=tx).to_dict() or {}
        epoch = now.timestamp()
        try:
            admitted = agent_quota.admit_run(ledger, key_hash, admission.estimate,
                                             limit=admission.limit, now=epoch)
        except agent_quota.AgentTokenBudgetExceeded:
            raise UsageLimitExceeded(
                uid=uid, kind=kind, utc_date=now.date().isoformat(), required=admission.estimate,
                token_budget=self._public(ledger, admission.period, admission.config, admission.tier, epoch,
                                          limit=admission.limit),
            ) from None
        except agent_quota.PipelineCapacityExceeded as exc:
            raise UsageCapacityExceeded(str(exc)) from None
        return ledger_ref, admitted

    def _new_run(self, kind, admission, request_fingerprint, now):
        return {
            "schema_version": USAGE_SCHEMA_VERSION,
            "kind": kind.value,
            "utc_date": now.date().isoformat(),
            "quota_day": admission.period,
            "token_tier": admission.tier,
            "admission_mode": admission.mode,
            "admission_estimate": admission.estimate,
            "token_limit_at_admission": admission.limit,
            "request_fingerprint": request_fingerprint,
            "expires_at": execution_expiry(now),
            "operation_claims": {},
            "booked_operations": {},
            "created_at": now,
        }

    def authorize_operation(
        self, uid: str, idempotency_key: str, kind: RunKind,
        admission: TokenAdmission, operation: str, operation_fingerprint: str,
        *, request_fingerprint: str, now: datetime | None = None,
    ) -> tuple[UsageRunResult, UsageOperationClaim]:
        """Admit (if new)/consume/claim atomically, reading each document once.

        Prepared runs only need the deletion fence and the run (two reads); the
        account is read only to admit a legacy run that skipped /prepare.
        No cached state may authorize external work.
        """
        uid = _validate_uid(uid)
        key_hash = _idempotency_hash(idempotency_key)
        kind = _coerce_kind(kind)
        operation = _validate_operation(operation)
        request_fingerprint = _validate_fingerprint(request_fingerprint)
        operation_fingerprint = _validate_fingerprint(operation_fingerprint)
        now = _as_utc(now)
        run_ref = self._run_ref(uid, key_hash)

        def authorize(tx):
            persistence_guard.ensure_account_write_allowed(
                uid=uid, db=self._db, transaction=tx
            )
            run_snap = run_ref.get(transaction=tx)
            ledger_ref = admitted = None
            if run_snap.exists:
                run_data = run_snap.to_dict() or {}
                if _stored_kind(run_data) is not kind:
                    raise UsageRunConflict(
                        "Idempotency key is already bound to a different run kind"
                    )
                if not hmac.compare_digest(
                    _stored_request_fingerprint(run_data), request_fingerprint
                ):
                    raise UsageRunConflict(
                        "Idempotency key is already bound to a different request"
                    )
                utc_date = _stored_utc_date(run_data)
                expires_at = _stored_expires_at(run_data)
                if now >= expires_at:
                    raise UsageRunExpired("Usage run has expired")
                status = _stored_status(run_data)
                if status is RunStatus.RELEASED:
                    raise UsageRunReleased("This usage run was already released. Start a new run.")
            else:
                ledger_ref, admitted = self._admit(tx, uid, key_hash, kind, admission, now)
                run_data = self._new_run(kind, admission, request_fingerprint, now)
                utc_date = run_data["utc_date"]
                expires_at = run_data["expires_at"]
                status = None

            claims = run_data.get("operation_claims")
            if claims is None:
                claims = {}
            if not isinstance(claims, dict):
                raise UsageDataError("Invalid operation claims in Firestore")
            existing = claims.get(operation)
            if existing is not None:
                if not isinstance(existing, dict):
                    raise UsageDataError("Invalid operation claim in Firestore")
                stored_fingerprint = _validate_fingerprint(
                    existing.get("request_fingerprint"), error_type=UsageDataError
                )
                if not hmac.compare_digest(stored_fingerprint, operation_fingerprint):
                    raise UsageOperationConflict("Operation is already bound to a different request")
                claimed_at = _stored_datetime(existing.get("claimed_at"), "claim time")
            else:
                claimed_at = now

            # All reads and validations precede every write, as Firestore requires.
            if admitted is not None:
                tx.set(ledger_ref, admitted)
            if existing is None or status is not RunStatus.CONSUMED:
                updated_claims = dict(claims)
                updated_claims[operation] = {
                    "request_fingerprint": operation_fingerprint,
                    "claimed_at": claimed_at,
                }
                updates = {
                    "status": RunStatus.CONSUMED.value,
                    "operation_claims": updated_claims, "updated_at": now,
                }
                if status is not RunStatus.CONSUMED:
                    updates["consumed_at"] = now
                if run_snap.exists:
                    tx.update(run_ref, updates)
                else:
                    tx.set(run_ref, {**run_data, **updates})
            budget = (self._public(admitted, admission.period, admission.config, admission.tier,
                                   now.timestamp(), limit=admission.limit)
                      if admitted is not None else None)
            return (
                UsageRunResult(uid=uid, idempotency_hash=key_hash, kind=kind,
                               status=RunStatus.CONSUMED, utc_date=utc_date,
                               token_budget=budget, idempotent=status is RunStatus.CONSUMED),
                UsageOperationClaim(
                    uid=uid, idempotency_hash=key_hash, operation=operation,
                    request_fingerprint=operation_fingerprint, claimed_at=claimed_at,
                    expires_at=expires_at, idempotent=existing is not None,
                ),
            )

        return self._transaction(uid, authorize)

    def reserve(
        self,
        uid: str,
        idempotency_key: str,
        kind: RunKind,
        admission: TokenAdmission,
        *,
        request_fingerprint: str | None = None,
        now: datetime | None = None,
    ) -> UsageRunResult:
        uid = _validate_uid(uid)
        key_hash = _idempotency_hash(idempotency_key)
        kind = _coerce_kind(kind)
        request_fingerprint = _validate_fingerprint(
            request_fingerprint
            or canonical_request_fingerprint({"internal_idempotency_hash": key_hash})
        )
        now = _as_utc(now)
        run_ref = self._run_ref(uid, key_hash)

        def operation(tx):
            persistence_guard.ensure_account_write_allowed(
                uid=uid, db=self._db, transaction=tx
            )
            run_snap = run_ref.get(transaction=tx)
            if run_snap.exists:
                run_data = run_snap.to_dict() or {}
                existing_kind = _stored_kind(run_data)
                if existing_kind is not kind:
                    raise UsageRunConflict(
                        "Idempotency key is already bound to a different run kind"
                    )
                stored_fingerprint = _stored_request_fingerprint(run_data)
                if not hmac.compare_digest(stored_fingerprint, request_fingerprint):
                    raise UsageRunConflict(
                        "Idempotency key is already bound to a different request"
                    )
                if now >= _stored_expires_at(run_data):
                    raise UsageRunExpired("Usage run has expired")
                return UsageRunResult(
                    uid=uid, idempotency_hash=key_hash, kind=existing_kind,
                    status=_stored_status(run_data), utc_date=_stored_utc_date(run_data),
                    token_budget=None, idempotent=True,
                )

            ledger_ref, admitted = self._admit(tx, uid, key_hash, kind, admission, now)
            run_data = self._new_run(kind, admission, request_fingerprint, now)
            tx.set(ledger_ref, admitted)
            tx.set(run_ref, {**run_data, "status": RunStatus.RESERVED.value, "updated_at": now})
            return UsageRunResult(
                uid=uid, idempotency_hash=key_hash, kind=kind, status=RunStatus.RESERVED,
                utc_date=run_data["utc_date"],
                token_budget=self._public(admitted, admission.period, admission.config,
                                          admission.tier, now.timestamp(), limit=admission.limit),
                idempotent=False,
            )

        return self._transaction(uid, operation)

    # --- Booking -------------------------------------------------------------

    def book_operation(
        self,
        uid: str,
        idempotency_key: str,
        operation: str,
        *,
        measured: int,
        estimated: int,
        final: bool = False,
        now: datetime | None = None,
    ) -> dict:
        """Debit one finished operation's tokens exactly once.

        ``final`` marks the last operation of a run (Consensus, API pipeline,
        Resolve): its remaining admission hold is dropped instead of waiting
        for expiry. Returns the account's public snapshot after the booking.
        """
        uid = _validate_uid(uid)
        key_hash = _idempotency_hash(idempotency_key)
        operation = _validate_operation(operation)
        for label, value in (("measured", measured), ("estimated", estimated)):
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{label} must be a non-negative integer")
        now = _as_utc(now)
        epoch = now.timestamp()
        config = agent_budget_config.get_config(self._db)
        run_ref = self._run_ref(uid, key_hash)

        def book(tx):
            persistence_guard.ensure_account_write_allowed(
                uid=uid, db=self._db, transaction=tx
            )
            run_snap = run_ref.get(transaction=tx)
            if not run_snap.exists:
                raise UsageRunNotFound("Usage reservation does not exist")
            run_data = run_snap.to_dict() or {}
            if _stored_status(run_data) is not RunStatus.CONSUMED:
                raise UsageTransitionError("Only a consumed usage run can be booked")
            booked = run_data.get("booked_operations") or {}
            if not isinstance(booked, dict):
                raise UsageDataError("Invalid booked operations in Firestore")
            period = run_data.get("quota_day")
            if not isinstance(period, str) or not period:
                # Runs admitted before the shared account book into today's period.
                period = agent_quota.period_key(config)
            tier = agent_budget_config.tier_key(run_data.get("token_tier"))
            ledger_ref = agent_quota.quota_ref(self._db, uid, period)
            ledger = ledger_ref.get(transaction=tx).to_dict() or {}
            if operation in booked:
                return self._public(ledger, period, config, tier, epoch)
            if len(booked) >= MAX_BOOKED_OPERATIONS:
                raise UsageDataError("Too many booked operations for one run")
            ledger = agent_quota.book_run(ledger, key_hash, measured=measured, estimated=estimated, now=epoch)
            if final:
                ledger = agent_quota.release_run(ledger, key_hash, now=epoch)
            tx.set(ledger_ref, ledger)
            tx.update(run_ref, {
                "booked_operations": {**booked, operation: {
                    "measured": measured, "estimated": estimated, "booked_at": now}},
                "updated_at": now,
            })
            return self._public(ledger, period, config, tier, epoch)

        return self._transaction(uid, book)

    def token_budget(self, uid: str, admission: TokenAdmission, *, now: datetime | None = None) -> dict:
        """Plain read of the account for responses (no repairs, no writes)."""
        uid = _validate_uid(uid)
        epoch = _as_utc(now).timestamp()
        ledger = agent_quota.quota_ref(self._db, uid, admission.period).get().to_dict() or {}
        return self._public(ledger, admission.period, admission.config, admission.tier, epoch,
                            limit=admission.limit)

    @staticmethod
    def _public(ledger, period, config, tier, epoch, limit=None):
        return agent_quota.public_snapshot(ledger or {}, period, config, tier, now=epoch, limit=limit)

    # --- Claims, lifecycle -----------------------------------------------------

    def claim_operation(
        self,
        uid: str,
        idempotency_key: str,
        operation: str,
        request_fingerprint: str,
        *,
        now: datetime | None = None,
    ) -> UsageOperationClaim:
        """Atomically authorize one billable logical operation once.

        Accounting idempotency and execution authorization are deliberately
        separate. Repeating a consumed run may read its state, but it may
        never acquire the same operation slot twice.
        """
        uid = _validate_uid(uid)
        key_hash = _idempotency_hash(idempotency_key)
        operation = _validate_operation(operation)
        request_fingerprint = _validate_fingerprint(request_fingerprint)
        now = _as_utc(now)
        run_ref = self._run_ref(uid, key_hash)

        def claim(tx):
            persistence_guard.ensure_account_write_allowed(
                uid=uid, db=self._db, transaction=tx
            )
            run_snap = run_ref.get(transaction=tx)
            if not run_snap.exists:
                raise UsageRunNotFound("Usage reservation does not exist")
            run_data = run_snap.to_dict() or {}
            if _stored_status(run_data) is not RunStatus.CONSUMED:
                raise UsageTransitionError(
                    "Only a consumed usage run can authorize provider work"
                )
            expires_at = _stored_expires_at(run_data)
            if now >= expires_at:
                raise UsageRunExpired("Usage run has expired")

            claims = run_data.get("operation_claims")
            if claims is None:
                claims = {}
            if not isinstance(claims, dict):
                raise UsageDataError("Invalid operation claims in Firestore")
            existing = claims.get(operation)
            if existing is not None:
                if not isinstance(existing, dict):
                    raise UsageDataError("Invalid operation claim in Firestore")
                stored_fingerprint = _validate_fingerprint(
                    existing.get("request_fingerprint"),
                    error_type=UsageDataError,
                )
                if not hmac.compare_digest(stored_fingerprint, request_fingerprint):
                    raise UsageRunConflict(
                        "Operation is already bound to a different request"
                    )
                claimed_at = _stored_datetime(existing.get("claimed_at"), "claim time")
                return UsageOperationClaim(
                    uid=uid,
                    idempotency_hash=key_hash,
                    operation=operation,
                    request_fingerprint=stored_fingerprint,
                    claimed_at=claimed_at,
                    expires_at=expires_at,
                    idempotent=True,
                )

            updated_claims = dict(claims)
            updated_claims[operation] = {
                "request_fingerprint": request_fingerprint,
                "claimed_at": now,
            }
            tx.update(
                run_ref,
                {
                    "operation_claims": updated_claims,
                    "updated_at": now,
                },
            )
            return UsageOperationClaim(
                uid=uid,
                idempotency_hash=key_hash,
                operation=operation,
                request_fingerprint=request_fingerprint,
                claimed_at=now,
                expires_at=expires_at,
                idempotent=False,
            )

        return self._transaction(uid, claim)

    def consume(self, uid: str, idempotency_key: str) -> UsageRunResult:
        return self._finish(uid, idempotency_key, RunStatus.CONSUMED)

    def release(self, uid: str, idempotency_key: str) -> UsageRunResult:
        return self._finish(uid, idempotency_key, RunStatus.RELEASED)

    def get_run(
        self,
        uid: str,
        idempotency_key: str,
        *,
        now: datetime | None = None,
    ) -> UsageRunResult:
        """Read a logical run without changing its lifecycle or the account."""
        uid = _validate_uid(uid)
        key_hash = _idempotency_hash(idempotency_key)
        now = _as_utc(now)
        snap = self._run_ref(uid, key_hash).get()
        if not snap.exists:
            raise UsageRunNotFound("Usage reservation does not exist")
        run_data = snap.to_dict() or {}
        if now >= _stored_expires_at(run_data):
            raise UsageRunExpired("Usage run has expired")
        return UsageRunResult(
            uid=uid, idempotency_hash=key_hash, kind=_stored_kind(run_data),
            status=_stored_status(run_data), utc_date=_stored_utc_date(run_data),
            token_budget=None, idempotent=True,
        )

    def bind_context_target(
        self,
        uid: str,
        idempotency_key: str,
        target_scope: str,
        *,
        now: datetime | None = None,
    ) -> None:
        """Bind one consumed logical run to one chat-context target.

        Only a hash of the target scope is stored. This admits nothing new; it
        prevents one historical consumed key from financing context builds for
        multiple turns.
        """
        uid = _validate_uid(uid)
        key_hash = _idempotency_hash(idempotency_key)
        now = _as_utc(now)
        if not isinstance(target_scope, str) or not target_scope.strip():
            raise ValueError("target_scope must not be empty")
        encoded_scope = target_scope.encode("utf-8")
        if len(encoded_scope) > 512:
            raise ValueError("target_scope is too long")
        target_hash = hashlib.sha256(encoded_scope).hexdigest()
        run_ref = self._run_ref(uid, key_hash)

        def operation(tx):
            persistence_guard.ensure_account_write_allowed(
                uid=uid, db=self._db, transaction=tx
            )
            run_snap = run_ref.get(transaction=tx)
            if not run_snap.exists:
                raise UsageRunNotFound("Usage reservation does not exist")
            run_data = run_snap.to_dict() or {}
            if now >= _stored_expires_at(run_data):
                raise UsageRunExpired("Usage run has expired")
            status = _stored_status(run_data)
            if status is not RunStatus.CONSUMED:
                raise UsageTransitionError(
                    "Only a consumed usage run can fund chat context"
                )
            existing = run_data.get("context_target_hash")
            if isinstance(existing, str) and existing:
                if not hmac.compare_digest(existing, target_hash):
                    raise UsageRunConflict(
                        "Usage run is already bound to a different context target"
                    )
                return
            tx.update(
                run_ref,
                {
                    "context_target_hash": target_hash,
                    "context_bound_at": now,
                    "updated_at": now,
                },
            )

        self._transaction(uid, operation)

    def _finish(
        self, uid: str, idempotency_key: str, target: RunStatus
    ) -> UsageRunResult:
        uid = _validate_uid(uid)
        key_hash = _idempotency_hash(idempotency_key)
        run_ref = self._run_ref(uid, key_hash)

        def operation(tx):
            persistence_guard.ensure_account_write_allowed(
                uid=uid, db=self._db, transaction=tx
            )
            run_snap = run_ref.get(transaction=tx)
            if not run_snap.exists:
                raise UsageRunNotFound("Usage reservation does not exist")
            run_data = run_snap.to_dict() or {}
            kind = _stored_kind(run_data)
            status = _stored_status(run_data)
            utc_date = _stored_utc_date(run_data)
            period = run_data.get("quota_day")
            release_hold = (target is RunStatus.RELEASED and status is RunStatus.RESERVED
                            and isinstance(period, str) and bool(period))
            ledger_ref = agent_quota.quota_ref(self._db, uid, period) if release_hold else None
            ledger = (ledger_ref.get(transaction=tx).to_dict() or {}) if ledger_ref else None

            if status is target:
                return UsageRunResult(uid=uid, idempotency_hash=key_hash, kind=kind, status=status,
                                      utc_date=utc_date, token_budget=None, idempotent=True)
            if status is not RunStatus.RESERVED:
                raise UsageTransitionError(
                    f"Cannot transition usage run from {status.value} to {target.value}"
                )

            updated_at = datetime.now(timezone.utc)
            if ledger_ref is not None:
                # Released before any provider work: its admission hold goes.
                tx.set(ledger_ref, agent_quota.release_run(ledger, key_hash, now=updated_at.timestamp()))
            tx.update(
                run_ref,
                {
                    "status": target.value,
                    "updated_at": updated_at,
                    f"{target.value}_at": updated_at,
                },
            )
            return UsageRunResult(uid=uid, idempotency_hash=key_hash, kind=kind, status=target,
                                  utc_date=utc_date, token_budget=None, idempotent=False)

        return self._transaction(uid, operation)

    def _transaction(self, uid: str, operation: Callable[[object], T]) -> T:
        # Agent and pipeline write the same account document; serialize the
        # short bookkeeping transactions of one account inside this process.
        with agent_quota.account_lock(uid):
            if self._transaction_runner is not None:
                return self._transaction_runner(operation)
            # Parallel provider claims share one run document. Keep the retry
            # budget for that contention, including legacy reserve/consume callers;
            # transaction retries must never authorize an operation twice.
            transaction = self._db.transaction(max_attempts=12)

            @firestore.transactional
            def run(tx):
                return operation(tx)

            return run(transaction)

    def _user_ref(self, uid: str):
        return self._db.collection("users").document(uid)

    def _run_ref(self, uid: str, key_hash: str):
        return self._user_ref(uid).collection(USAGE_RUNS_COLLECTION).document(key_hash)


def _validate_uid(uid: str) -> str:
    value = str(uid or "").strip()
    if not value:
        raise ValueError("uid must not be empty")
    return value


def _idempotency_hash(key: str) -> str:
    if not isinstance(key, str) or not key.strip():
        raise ValueError("idempotency_key must not be empty")
    encoded = key.encode("utf-8")
    if len(encoded) > MAX_IDEMPOTENCY_KEY_BYTES:
        raise ValueError(
            f"idempotency_key must not exceed {MAX_IDEMPOTENCY_KEY_BYTES} bytes"
        )
    return hashlib.sha256(encoded).hexdigest()


def canonical_request_fingerprint(value) -> str:
    """Return a stable SHA-256 fingerprint for a JSON-compatible request."""
    try:
        encoded = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ValueError("Request fingerprint input must be canonical JSON") from exc
    return hashlib.sha256(encoded).hexdigest()


def _validate_fingerprint(value, *, error_type=ValueError) -> str:
    if not isinstance(value, str) or len(value) != FINGERPRINT_HEX_LENGTH:
        raise error_type("Invalid request fingerprint")
    try:
        int(value, 16)
    except ValueError:
        raise error_type("Invalid request fingerprint") from None
    return value.lower()


def _validate_operation(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("operation must not be empty")
    normalized = value.strip().lower()
    if len(normalized.encode("utf-8")) > MAX_OPERATION_NAME_BYTES:
        raise ValueError("operation is too long")
    if not all(char.isalnum() or char in {":", "_", "-"} for char in normalized):
        raise ValueError("operation contains invalid characters")
    return normalized


def _coerce_kind(kind: RunKind) -> RunKind:
    try:
        return RunKind(kind)
    except (TypeError, ValueError):
        raise ValueError("Unsupported usage run kind") from None


def _as_utc(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    if value.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    return value.astimezone(timezone.utc)


def _stored_kind(data: dict) -> RunKind:
    try:
        return RunKind(data.get("kind"))
    except (TypeError, ValueError):
        raise UsageDataError("Invalid usage run kind in Firestore") from None


def _stored_status(data: dict) -> RunStatus:
    try:
        return RunStatus(data.get("status"))
    except (TypeError, ValueError):
        raise UsageDataError("Invalid usage run status in Firestore") from None


def _stored_utc_date(data: dict) -> str:
    value = data.get("utc_date")
    if not isinstance(value, str):
        raise UsageDataError("Invalid usage run UTC date in Firestore")
    try:
        parsed = datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        raise UsageDataError("Invalid usage run UTC date in Firestore") from None
    if parsed.isoformat() != value:
        raise UsageDataError("Invalid usage run UTC date in Firestore")
    return value


def _stored_request_fingerprint(data: dict) -> str:
    return _validate_fingerprint(
        data.get("request_fingerprint"), error_type=UsageDataError
    )


def _stored_datetime(value, label: str) -> datetime:
    if not isinstance(value, datetime):
        raise UsageDataError(f"Invalid usage run {label} in Firestore")
    if value.tzinfo is None:
        raise UsageDataError(f"Invalid usage run {label} in Firestore")
    return value.astimezone(timezone.utc)


def _stored_expires_at(data: dict) -> datetime:
    return _stored_datetime(data.get("expires_at"), "expiry")

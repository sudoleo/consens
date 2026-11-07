"""The account's consent to sending its questions to the AI providers.

Before a question of an account first goes to a model, the app says where it
goes (OpenRouter and the model families of the registry) and asks once
(App Store guideline 5.1.2(i); the web asks the same). The
answer is kept on ``users/{uid}`` as ``ai_consent = {version, at}``; the
check reads it with the account's tier (``security.has_ai_consent``) and the
entry points refuse with ``ai_consent_required`` (``security.require_ai_consent``).
Scheduled Watch runs and API v1 runs are not asked: a Watch comes from a chat
or a request that needed the consent, and API keys are issued by the operator.
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.core import security
from app.services import persistence_guard


def record(uid: str, *, db, now: datetime | None = None) -> None:
    """Note the consent in the current version. Raises
    AccountDeletionInProgress for an account that is being deleted."""
    now = now or datetime.now(timezone.utc)

    def operation(transaction):
        # A deleted account must not regain a user document through this field.
        persistence_guard.ensure_account_write_allowed(uid=uid, db=db, transaction=transaction)
        transaction.set(db.collection("users").document(uid), {
            security.AI_CONSENT_FIELD: {"version": security.AI_CONSENT_VERSION, "at": now},
        }, merge=True)

    persistence_guard._run_transaction(db, operation)
    # The tier cache holds the flag: the next check of this process sees it now.
    security.invalidate_tier_cache(uid)

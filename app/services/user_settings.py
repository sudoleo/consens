"""Account settings: the choices that follow an account to every device.

The browser keeps a copy of each value (static/js/user-settings.js) so the
first paint already matches; this document is the account's own record. It
holds only what the user chose: a setting that was never touched has no
field, so a later change of its default reaches everyone who never chose.

What stays in the browser on purpose (theme, sidebar width, the question
draft, the own OpenRouter key, analytics opt-out, seen hints) is not listed
here; docs/codebase-map.md names the reasons.

Writes go only through ``FirestoreUserSettingsRepository.update`` behind the
PATCH route. ``users/{uid}`` itself stays closed to the browser: tier and
role live there (see docs/codebase-map.md, "Datenhaltung").
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Literal, Optional

from firebase_admin import firestore
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from app.services import persistence_guard
from app.services.agent_comparison import AgentAutonomy, AgentDepth, AgentQuorum
from app.services.llm.agent_client import REASONING_EFFORT_PATTERN


SETTINGS_COLLECTION = "settings"
SETTINGS_DOCUMENT_ID = "app"
READ_TIMEOUT_SECONDS = 5.0

# A system prompt the account can keep is one every run accepts
# (chat.validate_client_system_prompt uses the same limits).
MAX_SYSTEM_PROMPT_CHARS = 12_000
MAX_SYSTEM_PROMPT_BYTES = 32_000

# Model IDs and family labels are checked by form, not against today's
# catalog: a model that leaves the catalog must not make the whole settings
# record unreadable. The browser falls back to an available model itself.
MODEL_ID_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._:/@+-]{0,159}$"
FAMILY_LABEL_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9 ._-]{0,31}$"
PRESET_ID_PATTERN = r"^[a-z0-9][a-z0-9_-]{0,31}$"
MAX_COMPARE_FAMILIES = 16

ModelId = Annotated[str, Field(pattern=MODEL_ID_PATTERN)]
FamilyLabel = Annotated[str, Field(pattern=FAMILY_LABEL_PATTERN)]
PresetId = Annotated[str, Field(pattern=PRESET_ID_PATTERN)]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class AgentModelSetting(_Strict):
    """The Agent chat model and its reasoning level the account picked last."""

    model_id: ModelId
    reasoning_effort: str = Field(default="default", pattern=REASONING_EFFORT_PATTERN)


class AgentPreferencesSetting(_Strict):
    """Agent depth, answer start and model choice; only the fields chosen."""

    depth: Optional[AgentDepth] = None
    quorum: Optional[AgentQuorum] = None
    autonomy: Optional[AgentAutonomy] = None


class CompareModelSetting(_Strict):
    """One model family in Compare/Consensus: included or not, which model."""

    enabled: Optional[bool] = None
    model: Optional[ModelId] = None


class UserSettings(_Strict):
    """Every account setting. ``None`` means "not chosen": the app default."""

    # Compare / Consensus / Agent for the next message (run-mode.js).
    run_mode: Optional[Literal["compare", "consensus", "agent"]] = None
    agent_model: Optional[AgentModelSetting] = None
    agent_preferences: Optional[AgentPreferencesSetting] = None
    # "Check sources" for Consensus and Agent; on unless switched off.
    check_sources: Optional[bool] = None
    # Keyed by the family label the app shows (OpenAI, Gemini, ...).
    compare_models: Optional[dict[FamilyLabel, CompareModelSetting]] = Field(
        default=None, max_length=MAX_COMPARE_FAMILIES
    )
    consensus_model: Optional[ModelId] = None
    # A preset id (fast, balanced, thorough) or "custom".
    consensus_preset: Optional[PresetId] = None
    system_prompt: Optional[str] = Field(default=None, max_length=MAX_SYSTEM_PROMPT_CHARS)
    agreement_display: Optional[Literal["full", "summary", "off"]] = None
    consensus_highlights: Optional[
        Literal["none", "all", "contradictions", "concerns", "critical"]
    ] = None
    claim_counts: Optional[bool] = None

    @field_validator("system_prompt")
    @classmethod
    def _system_prompt(cls, value):
        if value is None:
            return None
        if len(value.encode("utf-8")) > MAX_SYSTEM_PROMPT_BYTES:
            raise ValueError(f"System prompt exceeds {MAX_SYSTEM_PROMPT_BYTES} UTF-8 bytes.")
        # Empty is the app default, the same as never having written one.
        return value.strip() or None


SETTING_NAMES = tuple(UserSettings.model_fields)


def _compact(name: str, value):
    """A chosen value without its unchosen parts; ``None`` when nothing is left."""
    if name == "compare_models":
        value = {label: family for label, family in value.items() if family}
    return value if value not in (None, {}, "") else None


def _dump(settings: UserSettings, names) -> dict:
    dumped = settings.model_dump(include=set(names), exclude_none=True)
    return {name: _compact(name, dumped.get(name)) for name in names}


def changes_from(settings: UserSettings) -> dict:
    """The fields a PATCH named; ``None`` resets a setting to the default."""
    return _dump(settings, [name for name in SETTING_NAMES if name in settings.model_fields_set])


def sanitize_settings(raw) -> dict:
    """Stored values, field by field: one that no longer validates is dropped
    alone (an older schema), never the whole record."""
    if not isinstance(raw, dict):
        return {}
    clean = {}
    for name in SETTING_NAMES:
        if raw.get(name) is None:
            continue
        try:
            settings = UserSettings.model_validate({name: raw[name]})
        except ValidationError:
            continue
        value = _dump(settings, [name])[name]
        if value is not None:
            clean[name] = value
    return clean


class FirestoreUserSettingsRepository:
    """``users/{uid}/settings/app``: ``values``, ``revision``, ``updated_at``.

    ``revision`` 0 (no document) tells the browser that this account never
    saved settings; it then uploads what it chose before the sync existed.
    """

    def __init__(self, db):
        self.db = db

    def get(self, uid: str) -> tuple[dict, int]:
        snapshot = self._ref(uid).get(timeout=READ_TIMEOUT_SECONDS, retry=None)
        if not snapshot.exists:
            return {}, 0
        raw = snapshot.to_dict() or {}
        return sanitize_settings(raw.get("values")), max(0, int(raw.get("revision") or 0))

    def update(self, uid: str, changes: dict, *, now: datetime | None = None) -> tuple[dict, int]:
        """Apply named changes; every other setting keeps its stored value."""
        written = datetime.now(timezone.utc) if now is None else now
        ref = self._ref(uid)
        saved: dict = {}

        def operation(transaction):
            # Settings must not reappear after an acknowledged account deletion.
            persistence_guard.ensure_account_write_allowed(uid=uid, db=self.db, transaction=transaction)
            snapshot = ref.get(transaction=transaction)
            previous = (snapshot.to_dict() or {}) if snapshot.exists else {}
            values = sanitize_settings(previous.get("values"))
            for name, value in changes.items():
                if name not in SETTING_NAMES:
                    raise ValueError(f"Unknown setting: {name}")
                if value is None:
                    values.pop(name, None)
                else:
                    values[name] = value
            revision = max(0, int(previous.get("revision") or 0)) + 1
            transaction.set(ref, {"values": values, "revision": revision, "updated_at": written})
            saved["values"], saved["revision"] = values, revision

        _run_transaction(self.db, operation)
        return saved["values"], saved["revision"]

    def _ref(self, uid: str):
        uid = str(uid or "").strip()
        if not uid:
            raise ValueError("uid must not be empty")
        return (
            self.db.collection("users")
            .document(uid)
            .collection(SETTINGS_COLLECTION)
            .document(SETTINGS_DOCUMENT_ID)
        )


def _run_transaction(db, operation):
    """One Firestore transaction, with the lightweight test seam."""
    fake_runner = getattr(db, "run_transaction", None)
    if callable(fake_runner):
        return fake_runner(operation)
    transaction = db.transaction(max_attempts=6)

    @firestore.transactional
    def run(tx):
        return operation(tx)

    return run(transaction)

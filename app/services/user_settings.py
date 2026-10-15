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
from typing import Annotated, Any, Literal, Optional

from firebase_admin import firestore
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from app.services import persistence_guard
from app.services.agent_comparison import AgentAutonomy, AgentDepth, AgentQuorum
from app.services.llm.agent_client import REASONING_EFFORT_PATTERN


SETTINGS_COLLECTION = "settings"
SETTINGS_DOCUMENT_ID = "app"
READ_TIMEOUT_SECONDS = 5.0

# The longest system prompt an account keeps. A run sends it behind the date
# line the app puts in front ("Today is Wednesday, 2026-10-12. ",
# query-send.js), so a run accepts that much more (chat.py).
MAX_SYSTEM_PROMPT_CHARS = 12_000
MAX_SYSTEM_PROMPT_BYTES = 32_000
SYSTEM_PROMPT_DATE_LINE_RESERVE = 64

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
# A PATCH names each setting at most once; more keys are not a settings change.
MAX_PATCH_FIELDS = len(SETTING_NAMES)


def _compact(name: str, value):
    """A chosen value without its unchosen parts; ``None`` when nothing is left."""
    if name == "compare_models":
        value = {label: family for label, family in value.items() if family}
    return value if value not in (None, {}, "") else None


def _dump(settings: UserSettings, names) -> dict:
    dumped = settings.model_dump(include=set(names), exclude_none=True)
    return {name: _compact(name, dumped.get(name)) for name in names}


def _setting(name: str, value):
    """One setting's stored form; ``None`` is the default. Raises ValidationError."""
    if value is None:
        return None
    return _dump(UserSettings.model_validate({name: value}), [name])[name]


def validate_changes(raw: dict) -> tuple[dict, list[str]]:
    """The changes a PATCH asks for, setting by setting.

    A setting the server does not take (an unknown name, a value outside its
    rules, e.g. from a browser running an older or newer version) is
    returned in ``rejected``; the others are still saved. ``None`` resets a
    setting to the default.
    """
    changes, rejected = {}, []
    for name, value in raw.items():
        if name not in SETTING_NAMES:
            rejected.append(name)
            continue
        try:
            changes[name] = _setting(name, value)
        except ValidationError:
            rejected.append(name)
    return changes, rejected


def _revision(value) -> int:
    """A stored revision; anything that is not a count is taken as 1 (the
    document exists, so the account has settings)."""
    return value if isinstance(value, int) and not isinstance(value, bool) and value > 0 else 1


def sanitize_field_revisions(raw) -> dict:
    if not isinstance(raw, dict):
        return {}
    return {name: value for name, value in raw.items()
            if name in SETTING_NAMES and isinstance(value, int) and not isinstance(value, bool) and value > 0}


def sanitize_settings(raw) -> dict:
    """Stored values, setting by setting: one that no longer validates (an
    older schema) is dropped alone, never the whole record. A setting is one
    unit; ``compare_models`` is dropped as a whole."""
    if not isinstance(raw, dict):
        return {}
    clean = {}
    for name in SETTING_NAMES:
        try:
            value = _setting(name, raw.get(name))
        except ValidationError:
            continue
        if value is not None:
            clean[name] = value
    return clean


class AccountSettings(tuple):
    """``(values, revision, field_revisions)`` of one account."""

    __slots__ = ()

    def __new__(cls, values: dict, revision: int, field_revisions: dict):
        return super().__new__(cls, (values, revision, field_revisions))


class FirestoreUserSettingsRepository:
    """``users/{uid}/settings/app``: ``values``, ``revision``,
    ``field_revisions`` (the revision at which each setting last changed) and
    ``updated_at``.

    ``revision`` 0 (no document) tells the browser that this account never
    saved settings; it then uploads what it chose before the sync existed.
    ``field_revisions`` lets a browser tell whether a change it kept from an
    earlier visit is older than the account's value.
    """

    def __init__(self, db):
        self.db = db

    def get(self, uid: str) -> AccountSettings:
        snapshot = self._ref(uid).get(timeout=READ_TIMEOUT_SECONDS, retry=None)
        if not snapshot.exists:
            return AccountSettings({}, 0, {})
        return self._state(snapshot.to_dict() or {})

    def update(self, uid: str, changes: dict, *, now: datetime | None = None) -> AccountSettings:
        """Apply named changes; every other setting keeps its stored value."""
        written = datetime.now(timezone.utc) if now is None else now
        ref = self._ref(uid)
        saved: dict = {}

        def operation(transaction):
            # Settings must not reappear after an acknowledged account deletion.
            persistence_guard.ensure_account_write_allowed(uid=uid, db=self.db, transaction=transaction)
            snapshot = ref.get(transaction=transaction)
            previous = self._state(snapshot.to_dict() or {}) if snapshot.exists else AccountSettings({}, 0, {})
            values, field_revisions = dict(previous[0]), dict(previous[2])
            revision = previous[1] + 1
            for name, value in changes.items():
                if name not in SETTING_NAMES:
                    raise ValueError(f"Unknown setting: {name}")
                if value is None:
                    values.pop(name, None)
                else:
                    values[name] = value
                field_revisions[name] = revision
            transaction.set(ref, {"values": values, "revision": revision,
                                  "field_revisions": field_revisions, "updated_at": written})
            saved["state"] = AccountSettings(values, revision, field_revisions)

        _run_transaction(self.db, operation)
        return saved["state"]

    @staticmethod
    def _state(raw: dict) -> AccountSettings:
        return AccountSettings(sanitize_settings(raw.get("values")), _revision(raw.get("revision")),
                               sanitize_field_revisions(raw.get("field_revisions")))

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

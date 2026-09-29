from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.core.config as cfg
from app.api.routers import users as users_router
from app.core.rate_limit import limiter
from app.services import memory_edit, user_memory


UID = "memory-edit-owner"
NOW = datetime(2026, 8, 17, 12, 0, tzinfo=timezone.utc)


class Snapshot:
    def __init__(self, doc):
        self._doc = doc
        self.exists = doc.data is not None

    def to_dict(self):
        return dict(self._doc.data or {})


class Document:
    def __init__(self):
        self.data = None
        self.children = {}

    def get(self, transaction=None):
        return Snapshot(self)

    def set(self, value, merge=False):
        self.data = ({**(self.data or {}), **value} if merge else dict(value))

    def delete(self):
        self.data = None

    def collection(self, name):
        return Collection(self.children.setdefault(name, {}))


class Collection:
    def __init__(self, docs):
        self.docs = docs

    def document(self, name):
        return self.docs.setdefault(name, Document())


class Transaction:
    def set(self, ref, value, merge=False):
        ref.set(value, merge=merge)


class Database:
    def __init__(self):
        self.roots = {}

    def collection(self, name):
        return Collection(self.roots.setdefault(name, {}))

    def run_transaction(self, operation):
        return operation(Transaction())

    def collection_group(self, name):
        return GroupQuery(self, name)

    def walk(self):
        """Yield (path, document) for every stored document."""
        stack = [((root,), docs) for root, docs in self.roots.items()]
        while stack:
            prefix, docs = stack.pop()
            for doc_id, doc in docs.items():
                path = (*prefix, doc_id)
                yield path, doc
                for child, child_docs in doc.children.items():
                    stack.append(((*path, child), child_docs))


class GroupRef:
    def __init__(self, path, doc):
        self.path = "/".join(path)
        self._doc = doc

    def set(self, value, merge=False):
        self._doc.set(value, merge=merge)


class GroupSnapshot:
    def __init__(self, path, doc):
        self.reference = GroupRef(path, doc)
        self._doc = doc

    def to_dict(self):
        return dict(self._doc.data or {})


class GroupQuery:
    def __init__(self, db, name):
        self.db, self.name, self.filters, self.max = db, name, [], None

    def where(self, filter=None):
        self.filters.append(filter)
        return self

    def limit(self, value):
        self.max = value
        return self

    def stream(self):
        found = []
        for path, doc in self.db.walk():
            if len(path) < 2 or path[-2] != self.name or doc.data is None:
                continue
            matches = True
            for condition in self.filters:
                assert condition.op_string == "<="
                value = (doc.data or {}).get(condition.field_path)
                if value is None or value > condition.value:
                    matches = False
            if matches:
                found.append(GroupSnapshot(path, doc))
        return found[: self.max] if self.max is not None else found


def config(**updates):
    return {**cfg.DEFAULT_MEMORY_EDIT_CONFIG, **updates}


@pytest.fixture
def repository(monkeypatch):
    monkeypatch.setattr(
        memory_edit.persistence_guard,
        "ensure_account_write_allowed",
        lambda **kwargs: None,
    )
    db = Database()
    profile = (
        db.collection("users").document(UID)
        .collection(user_memory.MEMORY_COLLECTION)
        .document(user_memory.PROFILE_DOCUMENT_ID)
    )
    profile.set({
        **user_memory.empty_profile(),
        "role": "Works at Firma X.",
        "notes": "Prefers short answers.",
        "revision": 4,
    })
    return memory_edit.FirestoreMemoryEditRepository(db)


def test_model_patch_schema_is_strict_and_passage_bounded():
    assert memory_edit.parse_and_validate_patch({
        "operation": "replace",
        "target": "Works at Firma X.",
        "replacement": "Works at Firma Y.",
    })["operation"] == "replace"
    with pytest.raises(memory_edit.MemoryEditError):
        memory_edit.parse_and_validate_patch({
            "operation": "replace",
            "target": "x",
            "replacement": "y",
            "explanation": "trust me",
        })
    with pytest.raises(memory_edit.MemoryEditError):
        memory_edit.parse_and_validate_patch({
            "operation": "rewrite",
            "target": "",
            "replacement": "all memory",
        })


def test_replace_is_revision_checked_and_undo_restores_exact_content(repository):
    request_id = "request-00000001"
    fingerprint = "f" * 64
    reserved = repository.reserve(
        UID,
        client_request_id=request_id,
        fingerprint=fingerprint,
        tier="free",
        config=config(),
        now=NOW,
    )
    assert reserved["baseline_revision"] == 4

    result = repository.apply_patch(
        UID,
        client_request_id=request_id,
        fingerprint=fingerprint,
        lease_nonce=reserved["lease_nonce"],
        patch={
            "operation": "replace",
            "target": "Works at Firma X.",
            "replacement": "Works at Firma Y.",
        },
        memory_limit=12_000,
        now=NOW + timedelta(seconds=1),
    )
    assert result["status"] == "applied"
    profile, revision = user_memory.FirestoreUserMemoryRepository(
        repository.db
    ).get_with_revision(UID)
    assert profile["role"] == "Works at Firma Y."
    assert revision == 5

    undone = repository.undo(
        UID,
        result["revision_id"],
        memory_limit=12_000,
        now=NOW + timedelta(seconds=2),
    )
    restored, restored_revision = user_memory.FirestoreUserMemoryRepository(
        repository.db
    ).get_with_revision(UID)
    assert undone["status"] == "undone"
    assert restored["role"] == "Works at Firma X."
    assert restored["notes"] == "Prefers short answers."
    assert restored_revision == 6


def test_non_unique_target_is_never_overwritten(repository):
    profile_ref = repository._profile_ref(UID)
    profile_ref.data["notes"] = "Firma X. then Firma X."
    reservation = repository.reserve(
        UID,
        client_request_id="request-00000002",
        fingerprint="a" * 64,
        tier="free",
        config=config(),
        now=NOW,
    )
    with pytest.raises(memory_edit.MemoryEditError, match="unambiguous"):
        repository.apply_patch(
            UID,
            client_request_id="request-00000002",
            fingerprint="a" * 64,
            lease_nonce=reservation["lease_nonce"],
            patch={"operation": "delete", "target": "Firma X.", "replacement": ""},
            memory_limit=12_000,
            now=NOW + timedelta(seconds=1),
        )
    assert reservation["memory"]["notes"] == "Firma X. then Firma X."
    assert profile_ref.data["notes"] == "Firma X. then Firma X."


def test_same_client_request_never_calls_provider_twice(repository):
    calls = []

    def provider(**kwargs):
        calls.append(kwargs)
        return {
            "operation": "replace",
            "target": "Works at Firma X.",
            "replacement": "Works at Firma Y.",
        }

    service = memory_edit.MemoryEditService(repository, provider=provider)
    payload = dict(
        tier="free",
        client_request_id="request-00000003",
        source_kind="consensus",
        selected_text="You work at Firma X.",
        correction="I work at Firma Y.",
        config=config(),
    )
    first = service.edit(UID, **payload)
    second = service.edit(UID, **payload)
    assert first["revision_id"] == second["revision_id"]
    assert len(calls) == 1


def test_remember_intent_appends_when_no_related_entry_exists(repository):
    calls = []

    def provider(**kwargs):
        calls.append(kwargs)
        return {
            "operation": "append",
            "target": "",
            "replacement": "Lives in Berlin.",
        }

    service = memory_edit.MemoryEditService(repository, provider=provider)
    result = service.edit(
        UID,
        tier="free",
        client_request_id="request-add-0001",
        source_kind="model_answer",
        selected_text="You live in Berlin.",
        correction="I live in Berlin.",
        intent="add",
        config=config(),
    )
    profile, _ = user_memory.FirestoreUserMemoryRepository(
        repository.db
    ).get_with_revision(UID)
    assert result["status"] == "applied"
    assert result["operation"] == "append"
    assert profile["notes"] == "Prefers short answers.\nLives in Berlin."
    assert calls[0]["intent"] == "add"


def test_remember_intent_replaces_one_unique_conflicting_passage(repository):
    service = memory_edit.MemoryEditService(
        repository,
        provider=lambda **kwargs: {
            "operation": "replace",
            "target": "Works at Firma X.",
            "replacement": "Works at Firma Y.",
        },
    )
    result = service.edit(
        UID,
        tier="free",
        client_request_id="request-add-0002",
        source_kind="consensus",
        selected_text="You work at Firma Y.",
        correction="I work at Firma Y.",
        intent="add",
        config=config(),
    )
    profile, _ = user_memory.FirestoreUserMemoryRepository(
        repository.db
    ).get_with_revision(UID)
    assert result["operation"] == "replace"
    assert profile["role"] == "Works at Firma Y."
    assert profile["notes"] == "Prefers short answers."


def test_remember_intent_rejects_delete_patch(repository):
    service = memory_edit.MemoryEditService(
        repository,
        provider=lambda **kwargs: {
            "operation": "delete",
            "target": "Works at Firma X.",
            "replacement": "",
        },
    )
    with pytest.raises(memory_edit.MemoryEditError) as exc:
        service.edit(
            UID,
            tier="free",
            client_request_id="request-add-0003",
            source_kind="consensus",
            selected_text="You work at Firma Y.",
            correction="I work at Firma Y.",
            intent="add",
            config=config(),
        )
    assert exc.value.code == "invalid_model_patch"


def test_smallest_replace_preserves_unrelated_details(repository):
    profile_ref = repository._profile_ref(UID)
    profile_ref.data["role"] = "Works at Continental and lives in Hanover."
    reservation = repository.reserve(
        UID,
        client_request_id="request-merge-0001",
        fingerprint="7" * 64,
        tier="free",
        config=config(),
        now=NOW,
    )
    repository.apply_patch(
        UID,
        client_request_id="request-merge-0001",
        fingerprint="7" * 64,
        lease_nonce=reservation["lease_nonce"],
        patch={
            "operation": "replace",
            "target": "Works at Continental",
            "replacement": "Works at VHV",
        },
        memory_limit=12_000,
        now=NOW + timedelta(seconds=1),
    )
    profile, _ = user_memory.FirestoreUserMemoryRepository(
        repository.db
    ).get_with_revision(UID)
    assert profile["role"] == "Works at VHV and lives in Hanover."
    assert profile["notes"] == "Prefers short answers."


def test_persistent_daily_budget_is_shared_by_repository_instances(repository):
    other_process = memory_edit.FirestoreMemoryEditRepository(repository.db)
    limited = config(memory_free_ai_edits_daily=1)
    repository.reserve(
        UID,
        client_request_id="request-00000004",
        fingerprint="b" * 64,
        tier="free",
        config=limited,
        now=NOW,
    )
    with pytest.raises(memory_edit.MemoryEditError) as exc:
        other_process.reserve(
            UID,
            client_request_id="request-00000005",
            fingerprint="c" * 64,
            tier="free",
            config=limited,
            now=NOW + timedelta(seconds=46),
        )
    assert exc.value.code == "daily_limit"


def test_over_plan_memory_is_not_truncated_or_charged_by_ai_edit(repository):
    profile_ref = repository._profile_ref(UID)
    profile_ref.data["notes"] = "x" * 12_001
    with pytest.raises(memory_edit.MemoryEditError) as exc:
        repository.reserve(
            UID,
            client_request_id="request-over-plan",
            fingerprint="9" * 64,
            tier="free",
            config=config(),
            now=NOW,
        )
    assert exc.value.code == "memory_limit"
    assert profile_ref.data["notes"] == "x" * 12_001
    usage = repository.db.collection(memory_edit.USAGE_COLLECTION).document(
        memory_edit._hash(UID)
    )
    assert not usage.get().exists


def test_invalid_admin_values_fall_back_to_safe_defaults():
    normalized = cfg.normalize_memory_edit_config({
        "memory_edit_enabled": "yes",
        "memory_edit_model": "unknown-model",
        "memory_free_chars": 999_999,
        "memory_pro_chars": -1,
        "memory_global_calls_daily": "not-a-number",
    })
    assert normalized == cfg.DEFAULT_MEMORY_EDIT_CONFIG


def test_provider_call_is_schema_bound_no_reasoning_and_output_capped(monkeypatch):
    captured = {}

    client_config = {}

    class Completions:
        def create(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(
                content='{"operation":"append","target":"","replacement":"Works at Firma Y."}'
            ))])

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr(
        memory_edit,
        "openai_client",
        lambda **kwargs: (
            client_config.update(kwargs)
            or SimpleNamespace(chat=SimpleNamespace(completions=Completions()))
        ),
    )
    patch = memory_edit.request_memory_patch(
        model="gpt-5.6-luna",
        memory=user_memory.empty_profile(),
        source_kind="consensus",
        selected_text="Works at Firma X.",
        correction="Works at Firma Y.",
        max_output_tokens=150,
        timeout_seconds=10,
        intent="add",
    )
    assert patch["operation"] == "append"
    assert client_config["base_url"] == "https://openrouter.ai/api/v1"
    assert captured["model"] == "openai/gpt-5.6-luna"
    assert captured["reasoning_effort"] == "none"
    assert captured["max_tokens"] == 150
    assert captured["response_format"]["json_schema"]["strict"] is True
    assert captured["extra_body"] == {"provider": {"zdr": True}}
    assert '"intent":"add"' in captured["messages"][1]["content"]
    assert "smallest exact, uniquely occurring substring" in captured["messages"][0]["content"]
    assert "preserve every detail" in captured["messages"][0]["content"]


def test_one_in_flight_edit_and_global_budget_are_persistent(repository):
    repository.reserve(
        UID,
        client_request_id="request-00000006",
        fingerprint="d" * 64,
        tier="free",
        config=config(),
        now=NOW,
    )
    with pytest.raises(memory_edit.MemoryEditError) as in_flight:
        memory_edit.FirestoreMemoryEditRepository(repository.db).reserve(
            UID,
            client_request_id="request-00000007",
            fingerprint="e" * 64,
            tier="free",
            config=config(),
            now=NOW + timedelta(seconds=1),
        )
    assert in_flight.value.code == "edit_in_progress"

    other_uid = "second-owner"
    with pytest.raises(memory_edit.MemoryEditError) as global_limit:
        repository.reserve(
            other_uid,
            client_request_id="request-00000008",
            fingerprint="f" * 64,
            tier="free",
            config=config(memory_global_calls_daily=1),
            now=NOW + timedelta(seconds=1),
        )
    assert global_limit.value.code == "global_limit"


def test_edit_endpoint_applies_explicit_feedback_without_confirmation(monkeypatch):
    calls = []

    class StubService:
        def edit(self, uid, **kwargs):
            calls.append((uid, kwargs))
            return {
                "status": "applied",
                "revision_id": "a" * 32,
                "revision": 2,
                "undo_expires_at": NOW.isoformat(),
            }

    limiter.reset()
    monkeypatch.setattr(users_router, "verify_user_token", lambda token: UID)
    monkeypatch.setattr(users_router, "get_user_tier", lambda uid: "free")
    monkeypatch.setattr(users_router, "memory_edit_service", StubService())
    app = FastAPI()
    app.state.limiter = limiter
    app.include_router(users_router.router)
    client = TestClient(app)
    response = client.post(
        "/api/my/memory/edit",
        headers={"Authorization": "Bearer verified-token"},
        json={
            "client_request_id": "request-00000009",
            "source_kind": "model_answer",
            "selected_text": "You work at Firma X.",
            "correction": "I work at Firma Y.",
            "intent": "add",
        },
    )
    assert response.status_code == 200
    assert response.json()["status"] == "applied"
    assert calls[0][0] == UID
    assert calls[0][1]["correction"] == "I work at Firma Y."
    assert calls[0][1]["intent"] == "add"


# ---------------------------------------------------------------------------
# R13: Ein reservierter Edit erreicht nach einem Absturz einen Terminalzustand
# oder wird unter neuer Lease/Nonce genau einmal fortgesetzt; ein spaeter
# Altworker kann nichts mehr schreiben.
# ---------------------------------------------------------------------------


def _reserve(repository, request_id, fingerprint, now=NOW, **overrides):
    return repository.reserve(
        UID,
        client_request_id=request_id,
        fingerprint=fingerprint,
        tier="free",
        config=config(**overrides),
        now=now,
    )


def _usage(repository):
    return repository.db.collection(memory_edit.USAGE_COLLECTION).document(
        memory_edit._hash(UID)
    ).data


def _global_count(repository, now=NOW):
    return repository.db.collection(memory_edit.GLOBAL_USAGE_COLLECTION).document(
        f"memory-edit-{now.date().isoformat()}"
    ).data["count"]


PATCH_Y = {"operation": "replace", "target": "Works at Firma X.", "replacement": "Works at Firma Y."}


def test_same_request_is_recovered_under_a_new_lease_after_a_crash(repository):
    first = _reserve(repository, "request-crash-0001", "1" * 64)
    # Same id while the first worker may still be alive: stays processing.
    assert _reserve(repository, "request-crash-0001", "1" * 64, now=NOW + timedelta(seconds=5))["existing"]

    later = NOW + timedelta(days=1)
    recovered = _reserve(repository, "request-crash-0001", "1" * 64, now=later)

    assert recovered["existing"] is False
    assert recovered["lease_nonce"] != first["lease_nonce"]
    # The user's quota is charged once; only the real extra provider call
    # counts against the global provider budget.
    assert _usage(repository)["day_count"] == 1
    assert _global_count(repository) == 1
    assert _global_count(repository, later) == 1

    # The superseded worker finally answers: fenced, Memory untouched.
    with pytest.raises(memory_edit.MemoryEditError) as lost:
        repository.apply_patch(
            UID, client_request_id="request-crash-0001", fingerprint="1" * 64,
            patch=PATCH_Y, memory_limit=12_000, lease_nonce=first["lease_nonce"], now=later,
        )
    assert lost.value.code == "lease_lost"
    repository.fail(
        UID, "request-crash-0001", fingerprint="1" * 64, error_code="provider_failed",
        lease_nonce=first["lease_nonce"], now=later,
    )
    assert repository._profile_ref(UID).data["role"] == "Works at Firma X."
    assert repository._request_ref(UID, "request-crash-0001").data["status"] == "reserved"

    applied = repository.apply_patch(
        UID, client_request_id="request-crash-0001", fingerprint="1" * 64,
        patch=PATCH_Y, memory_limit=12_000, lease_nonce=recovered["lease_nonce"], now=later,
    )
    assert applied["status"] == "applied"
    assert repository._profile_ref(UID).data["revision"] == 5
    # Exactly one apply: a replay returns the same result without writing.
    again = repository.apply_patch(
        UID, client_request_id="request-crash-0001", fingerprint="1" * 64,
        patch=PATCH_Y, memory_limit=12_000, lease_nonce=first["lease_nonce"], now=later,
    )
    assert again["revision_id"] == applied["revision_id"]
    assert repository._profile_ref(UID).data["revision"] == 5
    assert _usage(repository)["in_flight_request"] is None


def test_a_second_crash_ends_the_request_as_interrupted(repository):
    _reserve(repository, "request-crash-0002", "2" * 64)
    _reserve(repository, "request-crash-0002", "2" * 64, now=NOW + timedelta(minutes=5))

    terminal = _reserve(repository, "request-crash-0002", "2" * 64, now=NOW + timedelta(minutes=10))

    assert terminal["existing"] is True
    assert terminal["record"] == {"status": "failed", "error_code": "interrupted"}
    assert _usage(repository)["in_flight_request"] is None


def test_crash_after_provider_answer_is_recovered_through_the_service(repository):
    calls = []

    def provider(**kwargs):
        calls.append(kwargs)
        return PATCH_Y

    payload = dict(
        tier="free",
        client_request_id="request-crash-0003",
        source_kind="consensus",
        selected_text="You work at Firma X.",
        correction="I work at Firma Y.",
        config=config(),
    )
    fingerprint = memory_edit.request_fingerprint(
        client_request_id="request-crash-0003", source_kind="consensus",
        selected_text="You work at Firma X.", correction="I work at Firma Y.",
    )
    # A reservation whose worker died after the provider answered but before
    # apply, reserved long enough ago that its lease has expired.
    _reserve(
        repository, "request-crash-0003", fingerprint,
        now=datetime.now(timezone.utc) - timedelta(hours=1),
    )

    result = memory_edit.MemoryEditService(repository, provider=provider).edit(UID, **payload)

    assert result["status"] == "applied"
    assert len(calls) == 1
    assert repository._profile_ref(UID).data["role"] == "Works at Firma Y."


def test_retention_moves_abandoned_reservations_to_a_terminal_state(repository):
    _reserve(repository, "request-crash-0004", "4" * 64)
    live = _reserve(repository, "request-crash-0005", "5" * 64, now=NOW + timedelta(minutes=5))
    assert live["existing"] is False  # the first lease expired, so a new edit may start

    summary = memory_edit.cleanup_memory_edit_records(
        repository.db, now=NOW + timedelta(minutes=5, seconds=1)
    )

    assert summary["edits_recovered"] == 1
    record = repository._request_ref(UID, "request-crash-0004").data
    assert record["status"] == "failed" and record["error_code"] == "interrupted"
    # The live reservation is untouched and still owns the in-flight lease.
    assert repository._request_ref(UID, "request-crash-0005").data["status"] == "reserved"
    assert _usage(repository)["in_flight_request"] == "request-crash-0005"
    # Repeatable: nothing left to recover.
    assert memory_edit.cleanup_memory_edit_records(
        repository.db, now=NOW + timedelta(minutes=5, seconds=2)
    )["edits_recovered"] == 0


def test_interrupted_edit_endpoint_answers_with_a_retryable_409(monkeypatch):
    class StubService:
        def edit(self, uid, **kwargs):
            raise memory_edit.MemoryEditError("interrupted", "This Memory action was interrupted.")

    limiter.reset()
    monkeypatch.setattr(users_router, "verify_user_token", lambda token: UID)
    monkeypatch.setattr(users_router, "get_user_tier", lambda uid: "free")
    monkeypatch.setattr(users_router, "memory_edit_service", StubService())
    app = FastAPI()
    app.state.limiter = limiter
    app.include_router(users_router.router)
    response = TestClient(app).post(
        "/api/my/memory/edit",
        headers={"Authorization": "Bearer verified-token"},
        json={
            "client_request_id": "request-00000010",
            "source_kind": "consensus",
            "selected_text": "x",
            "correction": "y",
        },
    )
    assert response.status_code == 409
    assert response.json()["detail"]["error_code"] == "interrupted"


# ---------------------------------------------------------------------------
# R28: Vollstaendige Undo-Vorzustaende verfallen nach 30 Tagen; die
# inhaltsfreien Idempotenz-/Revisionsdaten bleiben.
# ---------------------------------------------------------------------------


def test_undo_snapshots_expire_after_thirty_days_but_idempotency_remains(repository):
    calls = []

    def provider(**kwargs):
        calls.append(kwargs)
        return PATCH_Y

    applied_at = datetime.now(timezone.utc)
    service = memory_edit.MemoryEditService(repository, provider=provider)
    payload = dict(
        tier="free",
        client_request_id="request-retain-0001",
        source_kind="consensus",
        selected_text="You work at Firma X.",
        correction="I work at Firma Y.",
        config=config(),
    )
    result = service.edit(UID, **payload)
    revision_ref = repository._revision_ref(UID, result["revision_id"])
    assert revision_ref.data["before"]["role"] == "Works at Firma X."

    # Before the retention deadline nothing is removed.
    early = memory_edit.cleanup_memory_edit_records(repository.db, now=applied_at + timedelta(days=29))
    assert early["snapshots_purged"] == 0
    assert revision_ref.data["before"]["role"] == "Works at Firma X."

    later = applied_at + timedelta(days=31)
    summary = memory_edit.cleanup_memory_edit_records(repository.db, now=later)

    assert summary["snapshots_purged"] == 1
    assert "before" not in revision_ref.data
    assert "Works at Firma X." not in repr(revision_ref.data)
    assert revision_ref.data["after_revision"] == result["revision"]
    # Repeatable, and the request record left the query too.
    assert memory_edit.cleanup_memory_edit_records(repository.db, now=later)["snapshots_purged"] == 0
    # A late retry of the same request is still recognized, no second call.
    replay = service.edit(UID, **payload)
    assert replay["revision_id"] == result["revision_id"]
    assert replay["undo_expires_at"] == result["undo_expires_at"]
    assert len(calls) == 1
    with pytest.raises(memory_edit.MemoryEditError) as expired:
        repository.undo(UID, result["revision_id"], memory_limit=12_000, now=later)
    assert expired.value.code == "undo_expired"

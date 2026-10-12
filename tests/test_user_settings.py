"""Account settings: stored per account, written only through the PATCH route.

The browser half (static/js/user-settings.js) has its own tests in
tests/js/user-settings.test.mjs.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routers import chat as chat_router
from app.api.routers import users as users_router
from app.core.rate_limit import api_uid_limiter, limiter
from app.services import persistence_guard, user_settings
from app.services.account_deletion import FirestoreAccountDeletion
from app.services.user_settings import AccountSettings, FirestoreUserSettingsRepository, UserSettings
from test_chat_history import FakeChatDatabase


UID = "settings-user"
AUTH = {"Authorization": "Bearer token"}
SETTINGS_PATH = ("users", UID, "settings", "app")


# --- Schema -------------------------------------------------------------------


def test_sanitize_keeps_valid_fields_and_drops_each_invalid_one_alone():
    stored = {
        "run_mode": "bogus",
        "check_sources": "true",
        "agent_model": {"model_id": "openai/gpt-6-luna", "reasoning_effort": "low"},
        "agent_preferences": {"depth": "quick", "quorum": None},
        "compare_models": {"OpenAI": {"enabled": False}, "Gemini": {}, "<script>": {"enabled": True}},
        "system_prompt": "  Answer in German.  ",
        "claim_counts": True,
        "unknown": 1,
    }
    assert user_settings.sanitize_settings(stored) == {
        "agent_model": {"model_id": "openai/gpt-6-luna", "reasoning_effort": "low"},
        "agent_preferences": {"depth": "quick"},
        "system_prompt": "Answer in German.",
        "claim_counts": True,
    }
    assert user_settings.sanitize_settings(None) == {}
    assert user_settings.sanitize_settings(["run_mode"]) == {}


def test_sanitize_drops_settings_that_hold_only_unchosen_parts():
    assert user_settings.sanitize_settings({
        "agent_preferences": {},
        "compare_models": {"OpenAI": {}},
        "system_prompt": "   ",
    }) == {}


def test_changes_are_checked_setting_by_setting():
    changes, rejected = user_settings.validate_changes({
        "run_mode": None,
        "check_sources": False,
        # An empty prompt is the app default, the same as no prompt at all.
        "system_prompt": " ",
        "claim_counts": "yes",
        "theme": "dark",
        "agent_model": {"model_id": "gpt-6-luna"},
    })
    assert changes == {
        "run_mode": None,
        "check_sources": False,
        "system_prompt": None,
        "agent_model": {"model_id": "gpt-6-luna", "reasoning_effort": "default"},
    }
    assert rejected == ["claim_counts", "theme"]


def test_every_saved_prompt_fits_a_run_behind_the_date_line():
    longest_date_line = "Today is Wednesday, 2026-10-12. "
    assert len(longest_date_line) <= user_settings.SYSTEM_PROMPT_DATE_LINE_RESERVE
    saved = "\u20ac" * (user_settings.MAX_SYSTEM_PROMPT_BYTES // 3)  # 3 UTF-8 bytes each
    assert user_settings.validate_changes({"system_prompt": saved})[0] == {"system_prompt": saved}
    assert chat_router.validate_client_system_prompt(longest_date_line + saved)
    saved = "x" * user_settings.MAX_SYSTEM_PROMPT_CHARS
    assert chat_router.validate_client_system_prompt(longest_date_line + saved)


# --- Repository ---------------------------------------------------------------


@pytest.fixture
def database():
    return FakeChatDatabase()


@pytest.fixture
def repository(database):
    return FirestoreUserSettingsRepository(database)


def test_an_account_without_settings_reads_empty_with_revision_zero(repository):
    assert repository.get(UID) == ({}, 0, {})


def test_update_changes_only_the_named_settings_and_notes_when(repository, database):
    now = datetime(2026, 10, 12, tzinfo=timezone.utc)
    assert repository.update(UID, {"run_mode": "compare", "claim_counts": True}, now=now) == (
        {"run_mode": "compare", "claim_counts": True}, 1, {"run_mode": 1, "claim_counts": 1})
    assert repository.update(UID, {"run_mode": None, "check_sources": False}) == (
        {"claim_counts": True, "check_sources": False}, 2, {"run_mode": 2, "claim_counts": 1, "check_sources": 2})
    assert repository.get(UID) == (
        {"claim_counts": True, "check_sources": False}, 2, {"run_mode": 2, "claim_counts": 1, "check_sources": 2})
    stored = database.documents[SETTINGS_PATH]
    assert set(stored) == {"values", "revision", "field_revisions", "updated_at"}


def test_update_drops_a_stored_value_that_no_longer_validates(repository, database):
    database.documents[SETTINGS_PATH] = {"values": {"run_mode": "legacy", "claim_counts": True}, "revision": 4}
    assert repository.get(UID) == ({"claim_counts": True}, 4, {})
    assert repository.update(UID, {"check_sources": True}) == (
        {"claim_counts": True, "check_sources": True}, 5, {"check_sources": 5})


@pytest.mark.parametrize("stored", ["7", -3, None, True, 2.5])
def test_a_damaged_revision_still_reads_as_an_account_with_settings(repository, database, stored):
    database.documents[SETTINGS_PATH] = {"values": {"claim_counts": True}, "revision": stored,
                                         "field_revisions": {"claim_counts": "x", "theme": 3}}
    assert repository.get(UID) == ({"claim_counts": True}, 1, {})
    assert repository.update(UID, {"run_mode": "agent"})[1] == 2


def test_update_refuses_unknown_settings(repository, database):
    with pytest.raises(ValueError):
        repository.update(UID, {"theme": "dark"})
    assert SETTINGS_PATH not in database.documents


def test_settings_cannot_be_written_while_the_account_is_deleted(repository, database):
    database.collection(persistence_guard.ACCOUNT_DELETION_JOBS_COLLECTION).document(UID).set({"status": "pending"})
    with pytest.raises(persistence_guard.AccountDeletionInProgress):
        repository.update(UID, {"run_mode": "agent"})
    assert SETTINGS_PATH not in database.documents


def test_account_deletion_removes_the_settings(repository, database):
    repository.update(UID, {"run_mode": "agent"})
    FirestoreAccountDeletion(database)._delete_user_subcollections(UID)
    assert SETTINGS_PATH not in database.documents


# --- HTTP ---------------------------------------------------------------------


class StubRepository:
    def __init__(self):
        self.values, self.revision, self.field_revisions = {}, 0, {}
        self.updates = []
        self.error = None

    def get(self, uid):
        if self.error:
            raise self.error
        return AccountSettings(dict(self.values), self.revision, dict(self.field_revisions))

    def update(self, uid, changes):
        if self.error:
            raise self.error
        self.updates.append((uid, changes))
        self.revision += 1
        for name, value in changes.items():
            if value is None:
                self.values.pop(name, None)
            else:
                self.values[name] = value
            self.field_revisions[name] = self.revision
        return self.get(uid)


@pytest.fixture
def settings_api(monkeypatch):
    limiter.reset()
    api_uid_limiter.reset()
    stub = StubRepository()
    monkeypatch.setattr(users_router, "user_settings_repository", stub)
    monkeypatch.setattr(users_router, "verify_user_token", lambda token, **kw: UID)
    app = FastAPI()
    app.state.limiter = limiter
    app.include_router(users_router.router)
    return TestClient(app), stub


def test_settings_require_authentication(settings_api):
    client, stub = settings_api
    assert client.get("/api/my/settings").status_code == 401
    assert client.patch("/api/my/settings", json={"settings": {"run_mode": "agent"}}).status_code == 401
    assert stub.updates == []


def test_get_returns_the_stored_settings_and_revision(settings_api):
    client, stub = settings_api
    assert client.get("/api/my/settings", headers=AUTH).json() == {
        "settings": {}, "revision": 0, "field_revisions": {}}
    stub.values, stub.revision, stub.field_revisions = {"run_mode": "compare"}, 3, {"run_mode": 2}
    assert client.get("/api/my/settings", headers=AUTH).json() == {
        "settings": {"run_mode": "compare"}, "revision": 3, "field_revisions": {"run_mode": 2}}


def test_patch_changes_named_settings_and_null_resets(settings_api):
    client, stub = settings_api
    response = client.patch("/api/my/settings", headers=AUTH, json={"settings": {
        "run_mode": "compare",
        "agent_model": {"model_id": "anthropic/claude-sonnet-5.5", "reasoning_effort": "medium"},
        "compare_models": {"OpenAI": {"enabled": False, "model": "gpt-5.6-luna"}, "Meta": {"enabled": True}},
        "consensus_preset": "custom",
        "consensus_highlights": "none",
    }})
    assert response.status_code == 200
    assert response.json()["revision"] == 1
    assert response.json()["rejected"] == []
    assert stub.updates[-1] == (UID, {
        "run_mode": "compare",
        "agent_model": {"model_id": "anthropic/claude-sonnet-5.5", "reasoning_effort": "medium"},
        "compare_models": {"OpenAI": {"enabled": False, "model": "gpt-5.6-luna"}, "Meta": {"enabled": True}},
        "consensus_preset": "custom",
        "consensus_highlights": "none",
    })
    response = client.patch("/api/my/settings", headers=AUTH, json={"settings": {"run_mode": None}})
    assert response.status_code == 200
    assert "run_mode" not in response.json()["settings"]
    assert stub.updates[-1] == (UID, {"run_mode": None})


@pytest.mark.parametrize("settings", [
    {"theme": "dark"},
    {"run_mode": "fast"},
    {"check_sources": "false"},
    {"agent_model": {"model_id": "x", "reasoning_effort": "turbo"}},
    {"agent_model": {"reasoning_effort": "low"}},
    {"agent_preferences": {"depth": "deep"}},
    {"compare_models": {"Open<AI>": {"enabled": True}}},
    {"compare_models": {"OpenAI": {"enabled": True, "colour": "red"}}},
    {"compare_models": {f"Family{index}": {"enabled": True} for index in range(user_settings.MAX_COMPARE_FAMILIES + 1)}},
    {"consensus_model": "gpt 5"},
    {"consensus_preset": "High Quality"},
    {"system_prompt": "x" * (user_settings.MAX_SYSTEM_PROMPT_CHARS + 1)},
    {"system_prompt": "ä" * (user_settings.MAX_SYSTEM_PROMPT_BYTES // 2 + 1)},
])
def test_patch_refuses_a_value_outside_the_rules_and_keeps_the_others(settings_api, settings):
    client, stub = settings_api
    response = client.patch("/api/my/settings", headers=AUTH,
                            json={"settings": {**settings, "claim_counts": True}})
    assert response.status_code == 200
    assert response.json()["rejected"] == list(settings)
    assert stub.updates == [(UID, {"claim_counts": True})]


def test_patch_with_only_refused_values_writes_nothing(settings_api):
    client, stub = settings_api
    response = client.patch("/api/my/settings", headers=AUTH, json={"settings": {"run_mode": "fast"}})
    assert response.status_code == 200
    assert response.json() == {"settings": {}, "revision": 0, "field_revisions": {}, "rejected": ["run_mode"]}
    assert stub.updates == []


@pytest.mark.parametrize("body", [
    {"settings": {}},
    {"settings": None},
    {"settings": ["run_mode"]},
    {"settings": {f"name{index}": 1 for index in range(user_settings.MAX_PATCH_FIELDS + 1)}},
    {"settings": {"run_mode": "agent"}, "revision": 1},
])
def test_patch_refuses_a_malformed_request(settings_api, body):
    client, stub = settings_api
    response = client.patch("/api/my/settings", headers=AUTH, json=body)
    assert response.status_code == 422
    assert stub.updates == []


def test_patch_is_limited_per_account(settings_api, monkeypatch):
    client, stub = settings_api
    monkeypatch.setattr(api_uid_limiter, "_enabled", True)
    for _ in range(60):
        assert client.patch("/api/my/settings", headers=AUTH, json={"settings": {"claim_counts": True}}).status_code == 200
    assert client.patch("/api/my/settings", headers=AUTH, json={"settings": {"claim_counts": True}}).status_code == 429


def test_patch_is_refused_while_the_account_is_deleted(settings_api):
    client, stub = settings_api
    stub.error = persistence_guard.AccountDeletionInProgress("deleting")
    response = client.patch("/api/my/settings", headers=AUTH, json={"settings": {"run_mode": "agent"}})
    assert response.status_code == 403


def test_storage_failures_answer_503_without_details(settings_api):
    client, stub = settings_api
    stub.error = RuntimeError("firestore says no: secret-detail")
    for response in (
        client.get("/api/my/settings", headers=AUTH),
        client.patch("/api/my/settings", headers=AUTH, json={"settings": {"run_mode": "agent"}}),
    ):
        assert response.status_code == 503
        assert "secret-detail" not in response.text


# --- Browser and server agree -------------------------------------------------


def test_the_browser_keeps_and_checks_the_settings_the_server_stores():
    """A value the browser accepts must be one the server stores; a refused
    PATCH drops the change (static/js/user-settings.js)."""
    import json
    import re
    from pathlib import Path
    from typing import get_args

    from app.services.llm.agent_client import REASONING_EFFORT_PATTERN

    source = (Path(__file__).resolve().parents[1] / "static/js/user-settings.js").read_text(encoding="utf-8")

    def const(name):
        match = re.search(rf"^  const {name} = (.+?);$", source, re.MULTILINE | re.DOTALL)
        assert match, name
        return match.group(1)

    def choices(annotation):
        return sorted(value for arg in get_args(annotation) for value in (get_args(arg) or [arg]) if value is not type(None))

    fields = UserSettings.model_fields
    assert const("MODEL_ID") == f"/{user_settings.MODEL_ID_PATTERN}/"
    assert const("FAMILY_LABEL") == f"/{user_settings.FAMILY_LABEL_PATTERN}/"
    assert const("PRESET_ID") == f"/{user_settings.PRESET_ID_PATTERN}/"
    assert const("REASONING_EFFORT") == f"/{REASONING_EFFORT_PATTERN}/"
    assert int(const("MAX_COMPARE_FAMILIES")) == user_settings.MAX_COMPARE_FAMILIES
    assert int(const("MAX_SYSTEM_PROMPT_CHARS")) == user_settings.MAX_SYSTEM_PROMPT_CHARS
    assert int(const("MAX_SYSTEM_PROMPT_BYTES")) == user_settings.MAX_SYSTEM_PROMPT_BYTES
    assert sorted(json.loads(const("RUN_MODES"))) == choices(fields["run_mode"].annotation)
    assert sorted(json.loads(const("AGREEMENT_DISPLAY_MODES"))) == choices(fields["agreement_display"].annotation)
    assert sorted(json.loads(const("HIGHLIGHT_FILTERS")) + ["none"]) == choices(fields["consensus_highlights"].annotation)
    agent_choices = json.loads(re.sub(r"(\w+):", r'"\1":', const("AGENT_CHOICES")).replace(",\n  }", "\n  }"))
    for field, values in agent_choices.items():
        assert sorted(values) == choices(user_settings.AgentPreferencesSetting.model_fields[field].annotation)
    definitions = re.search(r"const DEFINITIONS = Object\.freeze\(\{(.+?)\}\);", source, re.DOTALL).group(1)
    assert re.findall(r"^    (\w+):", definitions, re.MULTILINE) == list(user_settings.SETTING_NAMES)

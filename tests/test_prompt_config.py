from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timezone
import threading
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from app.api.routers import admin
from app.core.rate_limit import limiter
from app.services import agent_delegation_config, prompt_catalog, prompt_config, agent_runs
from app.services.llm import base, consensus_engine
from app.services.llm.agent_client import resolve_agent_model
from app.services.prompt_defaults import (AGENT_SYSTEM_PROMPT, ANSWER_SYSTEM_PROMPT, CONSENSUS_SYSTEM_PROMPT,
                                          DEFAULT_PROMPTS)


class Document:
    def __init__(self, db, path):
        self.db, self.path = db, path

    def collection(self, name):
        return Collection(self.db, (*self.path, name))

    def get(self, transaction=None, **kwargs):
        self.db.reads += 1
        if self.db.fail_read:
            raise RuntimeError("Database unavailable")
        data = (transaction.documents if transaction else self.db.documents).get(self.path)
        return SimpleNamespace(exists=data is not None, to_dict=lambda: deepcopy(data))


class Collection:
    def __init__(self, db, path):
        self.db, self.path = db, path

    def document(self, name):
        return Document(self.db, (*self.path, name))


class Database:
    def __init__(self):
        self.documents = {}
        self.lock = threading.Lock()
        self.reads = 0
        self.fail_read = self.fail_write = False

    def collection(self, name):
        return Collection(self, (name,))

    def run_transaction(self, operation):
        with self.lock:
            tx = SimpleNamespace(documents=deepcopy(self.documents))
            tx.set = lambda ref, data, **kwargs: tx.documents.update({ref.path: deepcopy(data)})
            result = operation(tx)
            if self.fail_write:
                raise RuntimeError("Write failed")
            self.documents = tx.documents
            return result


@pytest.fixture
def config_store(monkeypatch):
    store = prompt_config.PromptConfigStore(Database())
    monkeypatch.setattr(prompt_config, "_runtime_store", store)
    return store


@pytest.fixture
def client(config_store, monkeypatch):
    def verify(token, **kwargs):
        assert kwargs.get("check_revoked") is True
        if token == "invalid":
            raise ValueError("Bad token")
        return token
    monkeypatch.setattr(admin, "verify_user_token", verify)
    monkeypatch.setattr(admin, "is_user_admin", lambda uid: uid == "admin")
    monkeypatch.setattr(limiter, "enabled", False)
    app = FastAPI()
    app.include_router(admin.router)
    return TestClient(app)


AUTH = {"Authorization": "Bearer admin"}
LEGACY_PROMPTS = {"agent": "Outdated admin agent prompt.", "answers": "Old answers.", "consensus": "Old consensus."}


def changed():
    config = {"reference_timezone": "America/New_York", "delegation": agent_delegation_config.settings_defaults()}
    config["delegation"].update(enabled=True, max_agents=3)
    return config


def legacy_document(revision=4):
    """An old Firestore document that still stores admin-edited prompt texts."""
    delegation = {**agent_delegation_config.settings_defaults(), "max_agents": 3,
                  "orchestrator_prompt": "Outdated orchestrator.", "worker_prompt": "Outdated worker."}
    return {"reference_timezone": "UTC", "prompts": dict(LEGACY_PROMPTS), "delegation": delegation,
            "revision": revision, "updated_at": None, "updated_by": "someone"}


def assert_code_prompts(config):
    assert config["prompts"] == DEFAULT_PROMPTS
    assert config["delegation"]["orchestrator_prompt"] == agent_delegation_config.ORCHESTRATOR_PROMPT
    assert config["delegation"]["worker_prompt"] == agent_delegation_config.WORKER_PROMPT


def assert_prompt_free(document):
    assert "prompts" not in document
    assert not set(agent_delegation_config.PROMPTS) & set(document["delegation"])


def test_admin_read_is_write_free_and_save_is_versioned_and_audited(client, config_store):
    response = client.get("/api/admin/prompt-config", headers=AUTH)
    assert response.status_code == 200
    assert response.json()["config"]["revision"] == 0
    assert_prompt_free(response.json()["config"])
    assert config_store.db.documents == {}
    response = client.put("/api/admin/prompt-config", headers=AUTH, json={"revision": 0, "config": changed()})
    assert response.status_code == 200
    saved = response.json()["config"]
    assert saved["revision"] == 1 and saved["updated_by"] == "admin"
    assert saved["reference_timezone"] == "America/New_York" and saved["delegation"] == changed()["delegation"]
    stored = config_store.db.documents[("app_config", "prompts")]
    assert stored == config_store.db.documents[("app_config", "prompts", "revisions", "000000000001")]
    assert_prompt_free(stored)
    assert client.get("/api/admin/prompt-config", headers=AUTH).json()["config"] == saved
    conflict = client.put("/api/admin/prompt-config", headers=AUTH,
                          json={"revision": 0, "config": {"reference_timezone": "UTC"}})
    assert conflict.status_code == 409
    assert config_store.read()["revision"] == 1
    restored = client.put("/api/admin/prompt-config", headers=AUTH,
                          json={"revision": 1, "config": {"reference_timezone": "UTC"}})
    assert restored.status_code == 200 and restored.json()["config"]["revision"] == 2
    # A timezone-only (legacy) save keeps the saved delegation settings.
    assert restored.json()["config"]["delegation"] == changed()["delegation"]
    first = config_store.db.documents[("app_config", "prompts", "revisions", "000000000001")]
    assert first["reference_timezone"] == "America/New_York"


def test_stored_prompt_texts_are_ignored_on_read(config_store):
    config_store.db.documents[("app_config", "prompts")] = legacy_document()
    config = prompt_config.get_config()
    assert config["revision"] == 4 and config["reference_timezone"] == "UTC"
    assert config["delegation"]["max_agents"] == 3
    assert_code_prompts(config)


def test_legacy_clients_cannot_store_prompts_and_saving_cleans_old_documents(client, config_store):
    config_store.db.documents[("app_config", "prompts")] = legacy_document()
    payload = {"reference_timezone": "UTC", "prompts": {"agent": "Injected"},
               "delegation": {**legacy_document()["delegation"], "orchestrator_prompt": "Injected"}}
    response = client.put("/api/admin/prompt-config", headers=AUTH, json={"revision": 4, "config": payload})
    assert response.status_code == 200
    # Settings are unchanged, but the save still drops the stored prompt texts.
    assert response.json()["config"]["revision"] == 5
    assert_prompt_free(response.json()["config"])
    stored = config_store.db.documents[("app_config", "prompts")]
    assert_prompt_free(stored)
    assert stored["delegation"]["max_agents"] == 3
    assert_code_prompts(config_store.read(force=True))
    again = client.put("/api/admin/prompt-config", headers=AUTH, json={"revision": 5, "config": payload})
    assert again.status_code == 200 and again.json()["config"]["revision"] == 5  # Clean documents stay put.


def test_admin_get_lists_the_code_prompts_read_only(client):
    from app.services import agent_comparison
    from app.services.prompt_defaults import AGENT_ANSWER_PROMPT
    entries = client.get("/api/admin/prompt-config", headers=AUTH).json()["prompts_readonly"]
    assert [entry["key"] for entry in entries] == [
        "agent", "agent_answer", "comparison", "answers", "consensus",
        "delegation_orchestrator", "delegation_worker"]
    assert all(set(entry) == {"key", "label", "used_for", "source", "text"} for entry in entries)
    assert all(entry["label"] and entry["used_for"] and entry["source"] and entry["text"].strip() for entry in entries)
    texts = {entry["key"]: entry["text"] for entry in entries}
    assert texts["agent"] == AGENT_SYSTEM_PROMPT
    assert texts["agent_answer"] == AGENT_ANSWER_PROMPT
    assert texts["answers"] == ANSWER_SYSTEM_PROMPT and texts["consensus"] == CONSENSUS_SYSTEM_PROMPT
    assert texts["delegation_orchestrator"] == agent_delegation_config.ORCHESTRATOR_PROMPT
    assert texts["delegation_worker"] == agent_delegation_config.WORKER_PROMPT
    comparison = texts["comparison"]
    assert comparison.startswith("You are an independent answer model")
    assert prompt_catalog.DATE_PLACEHOLDER in comparison and "Current date:" not in comparison
    assert "up to 3 search rounds" in comparison
    assert comparison.endswith(agent_comparison.DEPTH_GUIDANCE["full"])


def test_code_prompts_fit_the_prepare_round_trip():
    for text in DEFAULT_PROMPTS.values():
        assert len(text) <= prompt_config.MAX_PROMPT_CHARS
        assert len(text.encode("utf-8")) <= prompt_config.MAX_PROMPT_BYTES


@pytest.mark.parametrize("token,status", [(None, 401), ("invalid", 401), ("member", 403)])
@pytest.mark.parametrize("method", ["GET", "PUT"])
def test_admin_access_is_checked_before_config_reads_or_writes(client, config_store, token, status, method):
    kwargs = {"headers": {"Authorization": f"Bearer {token}"}} if token else {}
    if method == "PUT":
        kwargs["json"] = {"revision": 0, "config": changed()}
    response = client.request(method, "/api/admin/prompt-config", **kwargs)
    assert response.status_code == status
    assert config_store.db.reads == 0 and not config_store.db.documents


@pytest.mark.parametrize("mutation", [
    lambda c: c.update(reference_timezone="not/a/timezone"),
    lambda c: c.update(extra="unsupported"),
    lambda c: c.pop("reference_timezone"),
    lambda c: c["delegation"].update(max_agents=99),
    lambda c: c["delegation"].update(enabled="yes"),
    lambda c: c["delegation"].pop("max_parallel"),
    lambda c: c["delegation"].update(unknown=1),
])
def test_invalid_config_is_rejected_without_writes(client, config_store, mutation):
    config = changed()
    mutation(config)
    assert client.put("/api/admin/prompt-config", headers=AUTH, json={"revision": 0, "config": config}).status_code == 422
    assert not config_store.db.documents


def test_runtime_uses_code_prompts_and_saved_timezone(config_store, monkeypatch):
    config_store.db.documents[("app_config", "prompts")] = {**legacy_document(), "reference_timezone": "America/New_York"}

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 9, 16, 1, 0, tzinfo=timezone.utc).astimezone(tz)
    monkeypatch.setattr(base, "datetime", Clock)
    agent = agent_runs.get_agent_system_prompt(resolve_agent_model("claude-haiku-4-5"))
    assert agent.startswith(AGENT_SYSTEM_PROMPT)
    assert "Tuesday, 2026-09-15" in agent and "21:00:00" in agent
    assert "America/New_York (UTC-04:00)" in agent and "Claude Haiku 4.5" in agent
    answer = base.get_system_prompt()
    assert answer.endswith(ANSWER_SYSTEM_PROMPT)
    synthesis = consensus_engine._build_consensus_prompt("Question?", {"openai": "Actual answer"}, [])
    assert "Question?" in synthesis and "Actual answer" in synthesis
    assert synthesis.endswith(CONSENSUS_SYSTEM_PROMPT)
    assert "America/New_York" in synthesis
    assert not any(text in agent + answer + synthesis for text in LEGACY_PROMPTS.values())


def test_two_workers_cannot_overwrite_the_same_revision(config_store):
    another = prompt_config.PromptConfigStore(config_store.db)
    gate = threading.Barrier(2)

    def save(store):
        gate.wait(timeout=5)
        try:
            return store.save(changed(), expected_revision=0, updated_by="admin")["revision"]
        except prompt_config.PromptConfigConflict:
            return "conflict"
    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(save, [config_store, another]))
    assert sorted(map(str, outcomes)) == ["1", "conflict"]
    assert len(config_store.db.documents) == 2


def test_cache_refreshes_other_workers_and_failed_writes_never_activate(config_store):
    now = [100.0]
    other = prompt_config.PromptConfigStore(config_store.db, clock=lambda: now[0])
    assert other.read()["revision"] == 0
    config_store.save(changed(), expected_revision=0, updated_by="admin")
    assert other.read()["revision"] == 0
    now[0] += prompt_config.CACHE_SECONDS + 1
    assert other.read()["reference_timezone"] == "America/New_York"
    config_store.db.fail_write = True
    with pytest.raises(RuntimeError):
        config_store.save({"reference_timezone": "UTC"}, expected_revision=1, updated_by="admin")
    assert config_store.read()["reference_timezone"] == "America/New_York"
    assert len(config_store.db.documents) == 2
    config_store.db.fail_read = True
    now[0] += prompt_config.CACHE_SECONDS + 1
    assert other.read()["reference_timezone"] == "America/New_York"
    with pytest.raises(RuntimeError):
        other.read(force=True)


def test_delegation_limits_are_validated_and_legacy_saves_preserve_them(config_store):
    assert prompt_config.defaults()["delegation"]["enabled"] is False
    config = changed()
    config["delegation"].update(enabled=True, max_agents=2, max_parallel=3)
    with pytest.raises(prompt_config.PromptConfigError):
        config_store.save(config, expected_revision=0, updated_by="admin")
    config["delegation"]["max_parallel"] = 2
    saved = config_store.save(config, expected_revision=0, updated_by="admin")
    saved = config_store.save({"reference_timezone": "UTC"}, expected_revision=saved["revision"], updated_by="admin")
    assert agent_delegation_config.settings_only(saved["delegation"]) == config["delegation"]
    assert_code_prompts(saved)

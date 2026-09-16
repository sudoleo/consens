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
from app.services import prompt_config, agent_runs
from app.services.llm import base, consensus_engine
from app.services.llm.agent_client import resolve_agent_model


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


def changed():
    return {"reference_timezone": "America/New_York", "prompts": {
        "agent": "Answer directly. Literal {braces} are text.",
        "answers": "Use short paragraphs.", "consensus": "Combine evidence and explain remaining uncertainty.",
    }}


def test_admin_read_is_write_free_and_save_is_versioned_and_audited(client, config_store):
    response = client.get("/api/admin/prompt-config", headers=AUTH)
    assert response.status_code == 200
    assert response.json()["config"]["revision"] == 0
    assert response.json()["defaults"] == prompt_config.defaults()
    assert config_store.db.documents == {}
    response = client.put("/api/admin/prompt-config", headers=AUTH, json={"revision": 0, "config": changed()})
    assert response.status_code == 200
    saved = response.json()["config"]
    assert saved["revision"] == 1 and saved["updated_by"] == "admin"
    assert saved["prompts"] == changed()["prompts"]
    assert config_store.db.documents[("app_config", "prompts")] == config_store.db.documents[("app_config", "prompts", "revisions", "000000000001")]
    assert client.get("/api/admin/prompt-config", headers=AUTH).json()["config"] == saved
    conflict = client.put("/api/admin/prompt-config", headers=AUTH, json={"revision": 0, "config": prompt_config.defaults()})
    assert conflict.status_code == 409
    assert config_store.read()["revision"] == 1
    restored = client.put("/api/admin/prompt-config", headers=AUTH, json={"revision": 1, "config": prompt_config.defaults()})
    assert restored.status_code == 200 and restored.json()["config"]["revision"] == 2
    assert config_store.db.documents[("app_config", "prompts", "revisions", "000000000001")]["prompts"] == changed()["prompts"]


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
    lambda c: c["prompts"].update(agent=" "),
    lambda c: c["prompts"].update(agent=123),
    lambda c: c["prompts"].update(agent="x" * (prompt_config.MAX_PROMPT_CHARS + 1)),
    lambda c: c["prompts"].update(agent="😀" * 7500),
    lambda c: c["prompts"].update(agent="Bad\x00text"),
    lambda c: c["prompts"].pop("consensus"),
])
def test_invalid_config_is_rejected_without_writes(client, config_store, mutation):
    config = changed()
    mutation(config)
    assert client.put("/api/admin/prompt-config", headers=AUTH, json={"revision": 0, "config": config}).status_code == 422
    assert not config_store.db.documents


def test_runtime_uses_saved_prompts_and_keeps_dynamic_context(config_store, monkeypatch):
    config_store.save(changed(), expected_revision=0, updated_by="admin")
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 9, 16, 1, 0, tzinfo=timezone.utc).astimezone(tz)
    monkeypatch.setattr(base, "datetime", Clock)
    agent = agent_runs.get_agent_system_prompt(resolve_agent_model("claude-haiku-4-5"))
    assert agent.startswith(changed()["prompts"]["agent"])
    assert "Tuesday, 2026-09-15" in agent and "21:00:00" in agent
    assert "America/New_York (UTC-04:00)" in agent and "Claude Haiku 4.5" in agent
    answer = base.get_system_prompt()
    assert answer.endswith(changed()["prompts"]["answers"])
    synthesis = consensus_engine._build_consensus_prompt("Question?", {"openai": "Actual answer"}, [])
    assert "Question?" in synthesis and "Actual answer" in synthesis
    assert synthesis.endswith(changed()["prompts"]["consensus"])
    assert "America/New_York" in synthesis


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
    assert other.read()["prompts"] == changed()["prompts"]
    config_store.db.fail_write = True
    with pytest.raises(RuntimeError):
        config_store.save(prompt_config.defaults(), expected_revision=1, updated_by="admin")
    assert config_store.read()["prompts"] == changed()["prompts"]
    assert len(config_store.db.documents) == 2
    config_store.db.fail_read = True
    now[0] += prompt_config.CACHE_SECONDS + 1
    assert other.read()["prompts"] == changed()["prompts"]
    with pytest.raises(RuntimeError):
        other.read(force=True)


def test_delegation_limits_are_validated_and_legacy_saves_preserve_them(config_store):
    config = prompt_config.defaults()
    assert config["delegation"]["enabled"] is False
    config["delegation"].update(enabled=True, max_agents=2, max_parallel=3)
    with pytest.raises(prompt_config.PromptConfigError):
        config_store.save(config, expected_revision=0, updated_by="admin")
    config["delegation"]["max_parallel"] = 2
    saved = config_store.save(config, expected_revision=0, updated_by="admin")
    legacy = changed()
    saved = config_store.save(legacy, expected_revision=saved["revision"], updated_by="admin")
    assert saved["delegation"] == config["delegation"]

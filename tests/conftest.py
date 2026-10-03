import os

import pytest

# Die Playwright-E2E-Suite (tests/e2e/) braucht einen Chromium-Browser und
# startet einen eigenen uvicorn-Server; sie darf die schnelle Backend-Baseline
# ("python -m pytest tests") nicht mit einsammeln. Lauf nur mit RUN_E2E=1
# (siehe tests/e2e/README.md).
if os.environ.get("RUN_E2E") != "1":
    # The regular suite uses in-memory repository fakes and must be collectable
    # on a clean CI checkout without the gitignored production credential.
    os.environ.setdefault("UNIT_TEST_MODE", "1")
    collect_ignore = ["e2e"]


@pytest.fixture(autouse=True)
def _no_real_telegram_alerts(monkeypatch):
    """main.py laedt die lokale .env; mit einem echten Bot-Token darf ein Test,
    der einen Fehlerpfad uebt, nie eine echte Telegram-Nachricht ausloesen.
    Tests, die den Versand pruefen, setzen den Token selbst (und mocken HTTP)."""
    from app.services import telegram_notifier

    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    telegram_notifier.reset_critical_state()


@pytest.fixture
def deepseek_default_agent(monkeypatch):
    """Agent mechanics tests (costs, replay, ordering) were written against
    DeepSeek V4.1 Flash as the chat model and keep it pinned; the real default
    (GPT-6 Luna since 2026-10-04) has its own test in test_agent_runs.py."""
    monkeypatch.setenv("AGENT_MODEL", "deepseek/deepseek-v4.1-flash")


@pytest.fixture(autouse=True)
def _no_local_google_configuration(monkeypatch):
    """A local .env may switch Google on for manual testing; the suite starts
    without it, and Google tests configure exactly what they exercise."""
    for key in ("GOOGLE_INTEGRATIONS_ENABLED", "GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "GOOGLE_REDIRECT_URI",
                "GOOGLE_TOKEN_KEYS", "GOOGLE_PICKER_API_KEY", "GOOGLE_PROJECT_NUMBER", "GOOGLE_WRITES_ENABLED",
                "GOOGLE_TEST_USERS", "GOOGLE_ALLOWED_MODEL_IDS", "GOOGLE_ALLOWED_PROVIDERS"):
        monkeypatch.delenv(key, raising=False)


@pytest.fixture(autouse=True)
def _default_prompt_configuration(monkeypatch):
    """Default prompt reads must not contact Firestore in the unit suite."""
    from types import SimpleNamespace
    from app.services import prompt_config

    class EmptyConfigDb:
        def collection(self, _name):
            return self

        def document(self, _name):
            return self

        def get(self, **_kwargs):
            return SimpleNamespace(exists=False)

    monkeypatch.setattr(prompt_config, "_runtime_store", prompt_config.PromptConfigStore(EmptyConfigDb()))


@pytest.fixture(autouse=True)
def _default_token_account_tier(monkeypatch):
    """The shared token account reads tier and admin role per account.

    Unit fakes have no users/{uid} document; without this seam every ledger
    read would wait for the closed loopback endpoint. Agent tests run as Pro
    (Agent is Pro/Admin only); tier-specific tests patch these themselves.
    Routes pass their already resolved tier, so only the role is read there.
    """
    from app.services import agent_budget_config, agent_quota

    monkeypatch.setattr(agent_quota, "_stored_tier", lambda uid: "pro")
    monkeypatch.setattr(agent_quota, "_admin_role", lambda uid: False)
    # The Agent suites were calibrated against the historic 250,000-token
    # Agent allowance; the shared account's production defaults are larger
    # (agent_budget_config.DEFAULT_TIER_LIMITS). Tests that care about the
    # real defaults read them from the module, not from this value.
    for tier in ("pro", "admin"):
        monkeypatch.setitem(agent_budget_config.DEFAULT_TIER_LIMITS, tier, 250_000)


@pytest.fixture(autouse=True)
def _fresh_token_account_read_throttles():
    """agent_quota remembers per process which extra reads found nothing.
    Keyed by id(db), a later test's fake could inherit an earlier one's."""
    from app.services import agent_quota

    agent_quota._quiet_until.clear()
    yield
    agent_quota._quiet_until.clear()


@pytest.fixture(autouse=True)
def _neutral_user_memory_profile():
    """Jeder authentifizierte /ask_* liest jetzt das User-Memory-Profil.

    Ohne diesen Ersatz liefe der Read gegen den geschlossenen Loopback-Endpunkt
    aus UNIT_TEST_MODE und jeder /ask_*-Test wartete das Firestore-Budget ab.
    Der Default ist ein leeres Profil -- also exakt das Verhalten vor dem
    Feature. tests/test_user_memory.py setzt bewusst eigene Stubs darueber."""
    from app.api.routers import chat as chat_router
    from app.services.user_memory import empty_profile

    class _EmptyProfileRepository:
        def get(self, uid):
            return empty_profile()

    original = chat_router.user_memory_repository
    chat_router.user_memory_repository = _EmptyProfileRepository()
    yield
    chat_router.user_memory_repository = original


@pytest.fixture(autouse=True)
def _clear_resolved_chat_context_cache():
    """Der /ask_*-Kontext-Cache ist prozessweit und lebt 120 s — ohne Reset
    koennte ein Test den aufgeloesten Kontext des naechsten beantworten."""
    from app.api.routers import chat as chat_router

    chat_router.resolved_context_cache.clear()
    yield
    chat_router.resolved_context_cache.clear()

import os
import sys
from pathlib import Path

import pytest


def _isolate_from_local_configuration():
    """The unit suite must pass identically with and without a local .env.

    load_dotenv() searches upward from the calling file, so even a worktree
    under .claude/worktrees/ silently picked up the main checkout's .env. No
    test may read it (also not through a script that loads it on import), and
    every key documented in .env.example starts unset, whatever the shell or
    CI exports. Tests that need a value set it themselves via monkeypatch."""
    if "app.core.config" in sys.modules or "main" in sys.modules:
        raise RuntimeError("tests/conftest.py must isolate the environment before the app is imported")
    import dotenv

    dotenv.load_dotenv = lambda *args, **kwargs: False
    example = Path(__file__).resolve().parent.parent / ".env.example"
    for line in example.read_text(encoding="utf-8").splitlines():
        key, separator, _ = line.strip().partition("=")
        if separator and not key.startswith("#") and key != "UNIT_TEST_MODE":
            os.environ.pop(key, None)


# Die Playwright-E2E-Suite (tests/e2e/) braucht einen Chromium-Browser und
# startet einen eigenen uvicorn-Server; sie darf die schnelle Backend-Baseline
# ("python -m pytest tests") nicht mit einsammeln. Lauf nur mit RUN_E2E=1
# (siehe tests/e2e/README.md).
if os.environ.get("RUN_E2E") != "1":
    # The regular suite uses in-memory repository fakes and must be collectable
    # on a clean CI checkout without the gitignored production credential.
    os.environ.setdefault("UNIT_TEST_MODE", "1")
    collect_ignore = ["e2e"]
    _isolate_from_local_configuration()


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
    (Claude Sonnet 5.5 since 2026-10-07) has its own test in test_agent_default_model.py."""
    monkeypatch.setenv("AGENT_MODEL", "deepseek/deepseek-v4.1-flash")


# $1.15 per million tokens is one micro-euro per token
# (agent_budget_config.NANO_USD_PER_MICRO_EUR); a search costs $0.000001.
FLAT_PRICE = "0.00000115"


@pytest.fixture(autouse=True)
def flat_agent_prices(request, monkeypatch):
    """Since 2026-10-31 the daily account counts micro-euros. Agent tests run
    whole loops against the suite's allowance (250,000, see below) and were
    written in tokens: reservations shrinking to fit, waiting siblings,
    overdrafts, long runs. At one flat price for input, cached input, cache
    writes and output every catalog model costs one micro-euro per token, so
    their arithmetic holds and no catalog price update moves them. Tests of
    real prices carry ``@pytest.mark.real_prices`` (and explicit models:
    test_agent_euro_account.py, test_usage_meter.py)."""
    if request.node.get_closest_marker("real_prices"):
        return
    from app.services.llm import agent_model_metadata
    real = agent_model_metadata.snapshot

    def flat():
        catalog = real()
        for entry in catalog.values():
            entry["pricing"] = {**entry.get("pricing", {}), "prompt": FLAT_PRICE, "completion": FLAT_PRICE,
                                "input_cache_read": FLAT_PRICE, "input_cache_write": FLAT_PRICE,
                                "web_search": "0.000001"}
        return catalog

    monkeypatch.setattr(agent_model_metadata, "snapshot", flat)
    # Models without a search price of their own reserve Exa's ($0.007): next
    # to nothing here too, as searches cost no tokens in those tests.
    from app.services import agent_costs
    from app.services.llm import agent_client
    for module in (agent_costs, agent_client):
        monkeypatch.setattr(module, "search_cost_nanos", lambda model: 1_000)


@pytest.fixture(autouse=True)
def _fresh_agent_background(monkeypatch):
    """Each test gets its own Agent run registry: a lifespan test drains the
    process-wide one (shutdown refuses new turns), which must not leak."""
    import sys
    from app.services import agent_background as module
    runs = module.AgentBackgroundRuns()
    monkeypatch.setattr(module, "agent_background", runs)
    for name in ("app.api.routers.agent", "main"):
        if name in sys.modules and hasattr(sys.modules[name], "agent_background"):
            monkeypatch.setattr(sys.modules[name], "agent_background", runs)
    return runs


@pytest.fixture(autouse=True)
def _single_differences_pass(monkeypatch):
    """Agent judge tests pin exact call sequences (fallback order, cooldowns,
    call counts) written for one differences pass. Production runs two in
    parallel (agent_comparison.DIFFERENCES_PASSES); tests that cover the second
    pass set it back to 2 themselves."""
    from app.services import agent_comparison
    monkeypatch.setattr(agent_comparison, "DIFFERENCES_PASSES", 1)


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
def _clear_rendered_topic_pages():
    """Gerenderte Topic-Seiten und der Hub leben 120 s im Prozess (Audit I12)
    -- ohne Reset saehe ein Test die Seite aus dem Speicher des vorigen."""
    from app.api.routers import topics as topics_router

    topics_router.invalidate_topic_pages()
    yield
    topics_router.invalidate_topic_pages()

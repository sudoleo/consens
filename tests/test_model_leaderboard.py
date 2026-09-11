from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from google.api_core.exceptions import FailedPrecondition, ServiceUnavailable

from app.api.routers import pages as pages_router
from app.core.rate_limit import limiter


@pytest.fixture(autouse=True)
def isolated_leaderboard_cache(monkeypatch):
    pages_router._leaderboard_cache.clear()
    monkeypatch.setattr(pages_router.firestore, "transactional", lambda fn: fn)
    yield
    pages_router._leaderboard_cache.clear()


class LeaderboardSnapshot:
    def __init__(self, document_id, selections):
        self.id = document_id
        self._selections = selections

    def to_dict(self):
        return {"BestModel": self._selections}


class LeaderboardCollection:
    def __init__(self, db):
        self.db = db

    def stream(self, transaction=None, **kwargs):
        self.db.catalog_reads += 1
        return transaction.catalog if transaction else self.db.catalog


@pytest.mark.parametrize("period,total", [("all", 24), ("since-2026-08-31", 3)])
def test_pulse_renders_cached_ranking_without_javascript(monkeypatch, period, total):
    db = LeaderboardDb()
    monkeypatch.setattr(pages_router, "db_firestore", db)
    app = FastAPI()
    app.include_router(pages_router.router)
    client = TestClient(app)
    page = client.get("/model-pulse", params={"period": period})
    assert page.status_code == 200
    assert f"{total} judge selections" in page.text
    assert page.text.count('role="listitem"') == 9
    assert '2026-09-02</time>' in page.text
    assert 'action="/model-pulse" method="get"' in page.text
    assert "Loading real-run" not in page.text
    api = client.get("/api/model-leaderboard", params={"period": period})
    assert api.json()["total_selections"] == total
    assert db.catalog_reads == 1


def test_pulse_failure_is_retryable_not_a_fake_zero_ranking(monkeypatch):
    def fail(period):
        raise ServiceUnavailable("offline")
    monkeypatch.setattr(pages_router, "_read_leaderboard_totals", fail)
    app = FastAPI()
    app.include_router(pages_router.router)
    client = TestClient(app)
    page = client.get("/model-pulse")
    assert page.status_code == 503
    assert page.headers["cache-control"] == "no-store"
    assert page.headers["retry-after"] == "60"
    assert "temporarily unavailable" in page.text
    assert 'role="listitem"' not in page.text
    assert "0 judge selections" not in page.text
    assert client.get("/model-pulse?period=invalid").status_code == 400


def initial_catalog():
    return [
            LeaderboardSnapshot("Anthropic", 8),
            LeaderboardSnapshot("Claude", 5),
            LeaderboardSnapshot("OpenAI-Pro", 11),
            LeaderboardSnapshot("Mistral", 0),
        ]


class VoteSnapshot:
    def __init__(self, model, *, vote_type="BestModel", created_at=None):
        self._data = {
            "model": model,
            "vote_type": vote_type,
            "created_at": created_at or datetime(2026, 8, 31, 12, tzinfo=timezone.utc),
        }

    def to_dict(self):
        return dict(self._data)


class VoteCollection:
    def __init__(self, db, filters=()):
        self.db = db
        self.filters = filters

    def where(self, *, filter):
        return VoteCollection(self.db, self.filters + (filter,))

    def _matches(self, snapshot):
        for field_filter in self.filters:
            value = snapshot.to_dict().get(field_filter.field_path)
            target = field_filter.value
            if field_filter.op_string == "==" and value != target:
                return False
            if field_filter.op_string == ">=" and (value is None or value < target):
                return False
            if field_filter.op_string == "in" and value not in target:
                return False
        return True

    def stream(self):
        self.db.vote_streams += 1
        return [vote for vote in self.db.vote_docs if self._matches(vote)]

    def count(self, *, alias):
        assert alias == "selections"
        return self

    def get(self, *, transaction, retry, timeout):
        assert transaction.read_only is True
        assert retry is None
        assert timeout == 10
        self.db.count_queries.append(self.filters)
        if self.db.count_error:
            raise self.db.count_error
        if self.db.on_count:
            self.db.on_count()
        value = sum(self._matches(vote) for vote in transaction.votes)
        # Match the SDK's integer_value-or-double_value decoding for zero.
        return [[SimpleNamespace(value=value or 0.0)]]


class LeaderboardDb:
    def __init__(self):
        self.catalog = initial_catalog()
        self.vote_docs = [
            VoteSnapshot("OpenAI"),
            VoteSnapshot("Kimi-Pro"),
            VoteSnapshot("GLM"),
            VoteSnapshot("Grok", vote_type="WorstModel"),
        ]
        self.votes = VoteCollection(self)
        self.catalog_reads = 0
        self.vote_streams = 0
        self.count_queries = []
        self.count_error = None
        self.on_count = None
        self.transactions = 0

    def transaction(self, *, read_only):
        self.transactions += 1
        return SimpleNamespace(read_only=read_only, votes=list(self.vote_docs), catalog=list(self.catalog))

    def collection(self, name):
        if name == "leaderboard":
            return LeaderboardCollection(self)
        assert name == "model_votes"
        return self.votes


def test_public_model_leaderboard_aggregates_aliases_and_sets_cache(monkeypatch):
    monkeypatch.setattr(pages_router, "db_firestore", LeaderboardDb())
    app = FastAPI()
    app.state.limiter = limiter
    app.include_router(pages_router.router)

    response = TestClient(app).get("/api/model-leaderboard")

    assert response.status_code == 200
    data = response.json()
    assert data["period"] == "all"
    assert data["period_start"] is None
    assert data["total_selections"] == 24
    assert [(row["family"], row["selections"]) for row in data["rows"]] == [
        ("Anthropic / Claude", 13),
        ("OpenAI / ChatGPT", 11),
        ("Mistral", 0),
        ("Google / Gemini", 0),
        ("DeepSeek", 0),
        ("xAI / Grok", 0),
        ("Moonshot AI / Kimi", 0),
        ("Z.ai / GLM", 0),
        ("Meta / Muse", 0),
    ]
    kimi = next(row for row in data["rows"] if row["family"] == "Moonshot AI / Kimi")
    glm = next(row for row in data["rows"] if row["family"] == "Z.ai / GLM")
    meta = next(row for row in data["rows"] if row["family"] == "Meta / Muse")
    assert kimi["icon"].endswith("/kimi.svg")
    assert glm["icon"].endswith("/zai.svg")
    assert meta["icon"].endswith("/meta.svg")
    assert kimi["available_since"] == glm["available_since"] == "2026-08-31"
    # Jede spaeter ergaenzte Familie traegt ihr eigenes Startdatum, sonst
    # liest sich ein niedriger Stand wie ein Ergebnis.
    assert meta["available_since"] == "2026-09-02"
    assert response.headers["cache-control"] == "public, max-age=60, stale-while-revalidate=300"


def test_public_model_leaderboard_supports_shared_window(monkeypatch):
    db = LeaderboardDb()
    monkeypatch.setattr(pages_router, "db_firestore", db)
    app = FastAPI()
    app.state.limiter = limiter
    app.include_router(pages_router.router)

    response = TestClient(app).get("/api/model-leaderboard?period=since-2026-08-31")

    assert response.status_code == 200
    data = response.json()
    assert data["period"] == "since-2026-08-31"
    assert data["period_start"] == "2026-08-31"
    assert data["total_selections"] == 3
    assert [(row["family"], row["selections"]) for row in data["rows"][:3]] == [
        ("OpenAI / ChatGPT", 1),
        ("Moonshot AI / Kimi", 1),
        ("Z.ai / GLM", 1),
    ]


def test_public_model_leaderboard_rejects_unknown_period(monkeypatch):
    monkeypatch.setattr(pages_router, "db_firestore", LeaderboardDb())
    app = FastAPI()
    app.state.limiter = limiter
    app.include_router(pages_router.router)

    response = TestClient(app).get("/api/model-leaderboard?period=yesterday")

    assert response.status_code == 400


def test_period_counts_preserve_historical_aliases_other_dates_and_deleted_votes(monkeypatch):
    db = LeaderboardDb()
    db.catalog.extend([
        LeaderboardSnapshot("Google Legacy", 2),
        LeaderboardSnapshot("Retired vendor", 1),
    ])
    db.vote_docs.extend([
        VoteSnapshot("Google Legacy"),
        VoteSnapshot("Retired vendor"),
        VoteSnapshot("Claude"),
        VoteSnapshot("OpenAI", created_at=datetime(2026, 8, 30, 23, 59, tzinfo=timezone.utc)),
        VoteSnapshot("GLM", created_at=datetime(2026, 8, 31, tzinfo=timezone.utc)),
    ])
    now = [100.0]
    monkeypatch.setattr(pages_router, "db_firestore", db)
    monkeypatch.setattr(pages_router.time, "monotonic", lambda: now[0])

    totals = pages_router._read_leaderboard_totals(pages_router._MODEL_PULSE_PERIOD)
    assert totals == {
        "OpenAI / ChatGPT": 1, "Moonshot AI / Kimi": 1, "Z.ai / GLM": 2,
        "Google / Gemini": 1, "Other": 1, "Anthropic / Claude": 1,
    }
    assert db.vote_streams == 0
    assert db.transactions == 1
    assert len(db.count_queries) == 10
    # Deletion changes live period totals after expiry; lifetime counters keep
    # their existing semantics. No stale decrement/backfill state is involved.
    db.vote_docs = [vote for vote in db.vote_docs if vote.to_dict()["model"] != "Claude"]
    now[0] += 60
    assert "Anthropic / Claude" not in pages_router._read_leaderboard_totals(pages_router._MODEL_PULSE_PERIOD)
    assert pages_router._read_leaderboard_totals("all")["Anthropic / Claude"] == 13


def test_period_alias_counts_chunk_above_firestore_in_limit(monkeypatch):
    db = LeaderboardDb()
    for index in range(64):
        model = f"OpenAI historical {index}"
        db.catalog.append(LeaderboardSnapshot(model, 1))
        db.vote_docs.append(VoteSnapshot(model))
    monkeypatch.setattr(pages_router, "db_firestore", db)

    totals = pages_router._read_leaderboard_totals(pages_router._MODEL_PULSE_PERIOD)

    assert totals["OpenAI / ChatGPT"] == 65
    chunks = [field.value for query in db.count_queries for field in query if field.field_path == "model"]
    assert all(1 <= len(chunk) <= 30 for chunk in chunks)
    assert sum("OpenAI historical 0" in chunk for chunk in chunks) == 1
    assert db.vote_streams == 0


@pytest.mark.parametrize("period", ["all", pages_router._MODEL_PULSE_PERIOD])
def test_server_cache_reuses_empty_totals_and_refreshes_at_expiry(monkeypatch, period):
    db = LeaderboardDb()
    db.catalog = []
    db.vote_docs = []
    now = [100.0]
    monkeypatch.setattr(pages_router, "db_firestore", db)
    monkeypatch.setattr(pages_router.time, "monotonic", lambda: now[0])

    assert pages_router._read_leaderboard_totals(period) == {}
    assert pages_router._read_leaderboard_totals(period) == {}
    now[0] = 159.99
    assert pages_router._read_leaderboard_totals(period) == {}
    assert db.catalog_reads == 1
    now[0] = 160.0
    assert pages_router._read_leaderboard_totals(period) == {}
    assert db.catalog_reads == 2


def test_cache_entries_separate_periods_and_database_clients(monkeypatch):
    db = LeaderboardDb()
    monkeypatch.setattr(pages_router, "db_firestore", db)
    first = pages_router._read_leaderboard_totals("all")
    first.clear()  # Callers cannot mutate the stored totals.
    assert pages_router._read_leaderboard_totals("all")["Anthropic / Claude"] == 13
    assert pages_router._read_leaderboard_totals(pages_router._MODEL_PULSE_PERIOD)["OpenAI / ChatGPT"] == 1
    replacement = LeaderboardDb()
    replacement.catalog = []
    monkeypatch.setattr(pages_router, "db_firestore", replacement)
    assert pages_router._read_leaderboard_totals("all") == {}
    assert replacement.catalog_reads == 1


def test_concurrent_period_misses_share_one_refresh(monkeypatch):
    db = LeaderboardDb()
    entered = Event()
    release = Event()

    def hold_first_count():
        entered.set()
        assert release.wait(5)

    db.on_count = hold_first_count
    monkeypatch.setattr(pages_router, "db_firestore", db)
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(pages_router._read_leaderboard_totals, pages_router._MODEL_PULSE_PERIOD) for _ in range(8)]
        assert entered.wait(5)
        release.set()
        results = [future.result(timeout=5) for future in futures]
    assert all(result == results[0] for result in results)
    assert db.transactions == 1
    assert db.catalog_reads == 1
    assert db.vote_streams == 0


def test_counts_use_one_snapshot_despite_concurrent_vote_deletion(monkeypatch):
    db = LeaderboardDb()
    db.on_count = lambda: db.vote_docs.clear()
    monkeypatch.setattr(pages_router, "db_firestore", db)

    totals = pages_router._read_leaderboard_totals(pages_router._MODEL_PULSE_PERIOD)

    assert sum(totals.values()) == 3
    assert db.vote_docs == []
    assert db.transactions == 1


@pytest.mark.parametrize("message", [
    "The query requires an index. You can create it here: ...",
    "The query requires an index. That index is currently building and cannot be used yet.",
])
def test_missing_index_falls_back_once_then_upgrades_after_expiry(monkeypatch, message):
    db = LeaderboardDb()
    db.count_error = FailedPrecondition(message)
    now = [100.0]
    monkeypatch.setattr(pages_router, "db_firestore", db)
    monkeypatch.setattr(pages_router.time, "monotonic", lambda: now[0])

    totals = pages_router._read_leaderboard_totals(pages_router._MODEL_PULSE_PERIOD)
    assert sum(totals.values()) == 3
    assert pages_router._read_leaderboard_totals(pages_router._MODEL_PULSE_PERIOD) == totals
    assert db.vote_streams == 1
    assert db.transactions == 1
    db.count_error = None
    now[0] += 60
    assert pages_router._read_leaderboard_totals(pages_router._MODEL_PULSE_PERIOD) == totals
    assert db.vote_streams == 1
    assert db.transactions == 2


@pytest.mark.parametrize("error", [ServiceUnavailable("offline"), FailedPrecondition("unrelated precondition")])
def test_failed_aggregation_is_not_cached_or_replaced_with_scan(monkeypatch, error):
    db = LeaderboardDb()
    db.count_error = error
    monkeypatch.setattr(pages_router, "db_firestore", db)
    app = FastAPI()
    app.state.limiter = limiter
    app.include_router(pages_router.router)

    response = TestClient(app).get("/api/model-leaderboard?period=since-2026-08-31")

    assert response.status_code == 503
    assert db.vote_streams == 0
    assert pages_router._MODEL_PULSE_PERIOD not in pages_router._leaderboard_cache
    db.count_error = None
    assert sum(pages_router._read_leaderboard_totals(pages_router._MODEL_PULSE_PERIOD).values()) == 3


def test_partial_refresh_does_not_publish_or_extend_expired_cache(monkeypatch):
    db = LeaderboardDb()
    now = [100.0]
    monkeypatch.setattr(pages_router, "db_firestore", db)
    monkeypatch.setattr(pages_router.time, "monotonic", lambda: now[0])
    period = pages_router._MODEL_PULSE_PERIOD
    pages_router._read_leaderboard_totals(period)
    original_entry = pages_router._leaderboard_cache[period]
    now[0] += 60
    first_refresh_queries = len(db.count_queries)

    def fail_second_count():
        if len(db.count_queries) > first_refresh_queries + 1:
            raise ServiceUnavailable("interrupted count refresh")

    db.on_count = fail_second_count
    with pytest.raises(ServiceUnavailable):
        pages_router._read_leaderboard_totals(period)
    assert pages_router._leaderboard_cache[period] is original_entry
    assert original_entry[1] <= now[0]
    assert db.vote_streams == 0
    db.on_count = None
    assert sum(pages_router._read_leaderboard_totals(period).values()) == 3
    assert pages_router._leaderboard_cache[period][1] > now[0]

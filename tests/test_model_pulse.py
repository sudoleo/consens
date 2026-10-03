"""Model Pulse as a rate: picks per run a family was in (since 2026-10-03)."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routers import pages as pages_router
from app.services import model_pulse, persistence_guard

NOW = datetime(2026, 10, 3, 12, tzinfo=timezone.utc)


def entry(days_ago, field, picked, source="consensus"):
    return (NOW - timedelta(days=days_ago), source, tuple(field), picked)


def test_family_keys_fold_labels_aliases_pro_and_citations():
    assert model_pulse.family_key("Anthropic-Pro") == "anthropic"
    assert model_pulse.family_key("Claude") == "anthropic"
    assert model_pulse.family_key("Google Gemini: gemini-3.5-flash") == "gemini"
    assert model_pulse.family_key("meta") == "meta"
    assert model_pulse.family_key("Muse") == "meta"
    assert model_pulse.family_key("Not a model") is None


def test_participation_refuses_runs_that_would_distort_the_rate():
    assert model_pulse.participation(["OpenAI", "Claude", "OpenAI-Pro"], "Anthropic") == {
        "participants": ["openai", "anthropic"], "picked": "anthropic", "pulse_version": 1,
    }
    # One family is no comparison, and a pick outside the run is no data.
    assert model_pulse.participation(["OpenAI"], "OpenAI") is None
    assert model_pulse.participation(["OpenAI", "Grok"], "Gemini") is None


def test_rate_divides_by_runs_and_compares_with_chance():
    runs = [entry(1, ["openai", "anthropic"], "openai") for _ in range(6)]
    runs += [entry(1, ["openai", "anthropic", "grok", "gemini"], "anthropic") for _ in range(6)]
    view = model_pulse.build_view(runs, now=NOW)
    rows = {row["key"]: row for row in view["rows"] + view["sparse"]}
    assert view["runs"] == 12
    assert rows["openai"]["rate"] == 50.0 and rows["anthropic"]["rate"] == 50.0
    # Fair share: 6 runs at 1/2 and 6 runs at 1/4 -> 37.5 %.
    assert rows["openai"]["fair_share"] == 37.5
    assert rows["openai"]["lift"] == pytest.approx(6 / 4.5, abs=0.01)
    # Six runs are too few to rank; they stay visible as sparse.
    assert rows["grok"]["enough"] is False and rows["grok"] in view["sparse"]
    assert rows["mistral"]["runs"] == 0


def test_ranking_needs_min_runs_and_leader_names_the_others():
    runs = [entry(1, ["openai", "anthropic", "grok"], "openai") for _ in range(7)]
    runs += [entry(1, ["openai", "anthropic", "grok"], "anthropic") for _ in range(3)]
    view = model_pulse.build_view(runs, now=NOW)
    assert [row["key"] for row in view["rows"]] == ["openai", "anthropic", "grok"]
    assert [row["rank"] for row in view["rows"]] == [1, 2, 3]
    assert view["leader"]["key"] == "openai"
    assert view["leader"]["rate"] == 70.0 and view["leader"]["others_rate"] == 30.0
    low, high = view["rows"][0]["interval"]
    assert low < 70.0 < high
    assert view["scale"] >= high


def test_filters_period_mode_and_rival_with_head_to_head():
    runs = [entry(2, ["openai", "anthropic", "grok"], "anthropic", "agent")] * 4
    runs += [entry(2, ["openai", "anthropic", "grok"], "openai", "consensus")] * 3
    runs += [entry(2, ["openai", "grok"], "grok", "consensus")] * 5
    runs += [entry(40, ["openai", "anthropic"], "openai", "consensus")] * 9
    assert model_pulse.build_view(runs, period="30d", now=NOW)["runs"] == 12
    assert model_pulse.build_view(runs, mode="agent", now=NOW)["runs"] == 4
    view = model_pulse.build_view(runs, period="30d", rival="anthropic", now=NOW)
    assert view["runs"] == 7
    rows = {row["key"]: row for row in view["rows"] + view["sparse"]}
    assert rows["anthropic"]["is_rival"] and "h2h" not in rows["anthropic"]
    assert rows["openai"]["h2h"] == {"wins": 3, "losses": 4}
    assert rows["grok"]["h2h"] == {"wins": 0, "losses": 4}


def test_unknown_filters_are_errors():
    for bad in ({"period": "1y"}, {"mode": "byok"}, {"sort": "name"}):
        with pytest.raises(ValueError):
            model_pulse.normalize(**bad)
    assert model_pulse.normalize(rival="Claude")["rival"] == "anthropic"


# ------------------------------------------------------------------ ledger


class Snap:
    def __init__(self, doc_id, data):
        self.id, self._data = doc_id, data

    def to_dict(self):
        return dict(self._data)


class LedgerDb:
    def __init__(self, docs):
        self.docs, self.queries = docs, []

    def collection(self, name):
        assert name == "model_votes"
        return self

    def where(self, *, filter):
        self.queries.append((filter.field_path, filter.op_string, filter.value))
        return self

    def stream(self, **_kwargs):
        field, op, value = self.queries[-1]
        if op == "==":
            return [Snap(k, v) for k, v in self.docs.items() if v.get(field) == value]
        return [Snap(k, v) for k, v in self.docs.items() if v["created_at"] >= value]


def vote(minutes, picked="openai", **extra):
    return {"vote_type": "BestModel", "created_at": NOW + timedelta(minutes=minutes),
            "participants": ["openai", "grok"], "picked": picked, "pulse_version": 1,
            "owner_hash": "never-kept", **extra}


def test_ledger_loads_once_then_reads_only_new_votes(monkeypatch):
    clock = SimpleNamespace(now=1000.0)
    monkeypatch.setattr(model_pulse.time, "monotonic", lambda: clock.now)
    db = LedgerDb({"a": vote(0), "legacy": {"vote_type": "BestModel", "created_at": NOW, "model": "OpenAI"}})
    ledger = model_pulse.PulseLedger()
    first = ledger.entries(db)
    assert len(first) == 1 and db.queries[-1] == ("pulse_version", "==", 1)
    # The slim fact carries no owner.
    assert "never-kept" not in repr(first)
    db.docs["b"] = vote(3, picked="grok", source="agent")
    assert len(ledger.entries(db)) == 1  # inside the refresh window
    clock.now += 61
    entries = ledger.entries(db)
    assert len(entries) == 2
    field, op, value = db.queries[-1]
    assert (field, op) == ("created_at", ">=") and value == NOW - model_pulse.PulseLedger.OVERLAP
    # A deleted vote leaves on the next full reload.
    del db.docs["a"]
    clock.now += model_pulse.PulseLedger.FULL_RELOAD_SECONDS + 1
    assert [e[3] for e in ledger.entries(db)] == ["grok"]


# ------------------------------------------------------------------ writes


def test_consensus_vote_stores_who_was_in_the_run():
    from test_phase5_operations import Database

    db = Database()
    result_id = "P" * 16
    db.data[("pending_results", result_id)] = {
        "owner_uid": "u1", "expires_at": NOW + timedelta(hours=1),
        "differences_data": {"best_model": "Anthropic"}, "answer_provenance": "developer",
        "included_models": ["OpenAI: gpt-6-luna", "Anthropic Claude: claude-sonnet-5.5", "Grok: grok-4.7"],
    }
    assert persistence_guard.record_model_vote(
        uid="u1", result_id=result_id, model="Anthropic", vote_type="BestModel", db=db, now=NOW)
    stored = next(v for (kind, _), v in db.data.items() if kind == "model_votes")
    assert stored["participants"] == ["openai", "anthropic", "grok"]
    assert stored["picked"] == "anthropic" and stored["source"] == "consensus"


def test_agent_choice_names_the_widest_compared_field():
    review = {"status": "succeeded",
              "comparisons": [{"id": "a", "answers": [{"provider_label": "OpenAI"}, {"provider_label": "Grok"}]},
                              {"id": "b", "answers": [{"provider_label": "Gemini"}, {"provider_label": "Kimi"},
                                                      {"provider_label": "Anthropic"}]}],
              "checks": [{"comparison_id": "a", "status": "succeeded", "differences_data": {"best_model": "OpenAI"}},
                         {"comparison_id": "b", "status": "succeeded", "differences_data": {"best_model": "Claude"}}]}
    assert persistence_guard.agent_best_model_choice(review) == ("Anthropic", ["Gemini", "Kimi", "Anthropic"])


# ------------------------------------------------------------------ pages


@pytest.fixture
def client(monkeypatch):
    runs = [entry(1, ["openai", "anthropic", "grok", "gemini"], "openai") for _ in range(8)]
    runs += [entry(1, ["openai", "anthropic", "grok", "gemini"], "anthropic") for _ in range(4)]
    state = SimpleNamespace(entries=runs, fail=False)

    def entries(db):
        if state.fail:
            raise RuntimeError("offline")
        return state.entries

    monkeypatch.setattr(model_pulse.LEDGER, "entries", entries)
    monkeypatch.setattr(model_pulse, "datetime", SimpleNamespace(now=lambda tz=None: NOW))
    app = FastAPI()
    app.include_router(pages_router.router)
    return TestClient(app), state


def test_pulse_page_renders_rates_filters_and_headline(client):
    http, _ = client
    page = http.get("/model-pulse")
    assert page.status_code == 200
    assert page.text.count('class="pulse-row') == 4
    assert 'id="modelPulseHeadline"' in page.text
    assert "67%" in page.text  # 8 of 12
    assert 'action="/model-pulse" method="get"' in page.text
    assert "8 of 12 runs" in page.text
    rival = http.get("/model-pulse", params={"with": "anthropic", "sort": "lift"})
    assert "vs Claude" in rival.text and "pulse-row is-rival" in rival.text
    assert http.get("/model-pulse", params={"period": "year"}).status_code == 400


def test_pulse_api_and_failure_are_honest(client):
    http, state = client
    data = http.get("/api/model-pulse", params={"mode": "consensus"}).json()
    assert data["runs"] == 12 and data["rows"][0]["key"] == "openai"
    assert http.get("/api/model-pulse", params={"mode": "x"}).status_code == 400
    state.fail = True
    page = http.get("/model-pulse")
    assert page.status_code == 503 and page.headers["cache-control"] == "no-store"
    assert 'class="pulse-row' not in page.text
    assert http.get("/api/model-pulse").status_code == 503


def test_landing_shows_benchmark_before_watch_and_the_live_strip(client, monkeypatch):
    http, state = client
    import app.services.llm.agent_client as agent_client
    monkeypatch.setattr(agent_client, "agent_model_label", lambda: "Agent")
    page = http.get("/").text
    assert page.index('id="benchmark"') < page.index('id="watch"')
    assert 'class="lp-live-pulse lp-reveal"' in page
    assert "No model wins every time." in page
    assert 'class="lp-hero-pulse"' not in page
    # Too few runs to say anything: the strip stays out, the page renders.
    state.entries = state.entries[:3]
    assert 'class="lp-live-pulse' not in http.get("/").text
    state.fail = True
    assert http.get("/").status_code == 200

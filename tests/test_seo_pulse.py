from datetime import date, datetime, timedelta, timezone

from fastapi.testclient import TestClient

import main
from app.api.routers import admin as admin_router
from app.services import seo_pulse


NOW = datetime(2026, 10, 5, 7, 0, tzinfo=timezone.utc)  # Monday 09:00 Berlin


class Snap:
    def __init__(self, data):
        self._data = data

    @property
    def exists(self):
        return self._data is not None

    def to_dict(self):
        return dict(self._data) if self._data is not None else None


class DocRef:
    def __init__(self):
        self.data = None

    def get(self, transaction=None):
        return Snap(self.data)

    def set(self, values, merge=False):
        self.data = {**(self.data or {}), **values} if merge else dict(values)


class Db:
    def __init__(self):
        self.doc = DocRef()

    def collection(self, name):
        assert name == seo_pulse.CONFIG_COLLECTION
        return self

    def document(self, name):
        assert name == seo_pulse.CONFIG_DOCUMENT
        return self.doc


def row(keys, impressions, clicks=0, position=8.0):
    return {"keys": keys, "impressions": impressions, "clicks": clicks, "position": position}


SITE = "https://www.consens.io"


class Client:
    """Search Console double keyed by the dimensions the pulse asks for."""

    def __init__(self, window):
        self.window = window
        self.calls = []

    def search(self, start, end, dimensions):
        self.calls.append((start, end, tuple(dimensions)))
        w = self.window
        if dimensions == ["date"]:
            return [row([w["prev_end"].isoformat()], 40, 1), row([w["end"].isoformat()], 160, 2)]
        if dimensions == ["page"] and start == w["start"]:
            return [row([SITE + "/"], 120, 1), row([SITE + "/s/glm-vs-deepseek-AAAAAAAAAAAAAAAA"], 40)]
        if dimensions == ["page"] and start == w["prev_start"]:
            return [row([SITE + "/"], 10), row([SITE + "/topics/gpt-6"], 30)]
        if dimensions == ["page", "query"]:
            return [row([SITE + "/", "consens"], 100), row([SITE + "/", "consensus ai"], 5)]
        if dimensions == ["page"] and start == w["dormant_start"]:
            return [row([SITE + "/s/old-but-alive-BBBBBBBBBBBBBBBB"], 25)]
        raise AssertionError(dimensions)


def service_with(db, client, shares, notes, monkeypatch, moderated):
    monkeypatch.setattr(
        seo_pulse.share_snapshots, "moderate_share",
        lambda share_id, **kwargs: moderated.append((share_id, kwargs["indexed"])),
    )
    service = seo_pulse.SeoPulseService(
        db, client_factory=lambda: client, clock=lambda: NOW, notify=notes.append,
    )
    service._indexed_shares = lambda: shares
    return service


def test_next_run_is_the_coming_monday_morning_in_berlin():
    sunday = datetime(2026, 10, 4, 12, 0, tzinfo=timezone.utc)
    assert seo_pulse.next_run_after(sunday) == NOW
    assert seo_pulse.next_run_after(NOW) == NOW + timedelta(days=7)


def test_movers_name_the_page_and_the_query_behind_the_change():
    moved = seo_pulse.movers(
        [row([SITE + "/"], 120), row([SITE + "/s/a-AAAAAAAAAAAAAAAA"], 40)],
        [row([SITE + "/"], 10), row([SITE + "/topics/gpt-6"], 30)],
        [row([SITE + "/", "consens"], 100)],
    )
    assert [(m["path"], m["delta"], m["top_query"]) for m in moved["up"]] == [
        ("/", 110, "consens"), ("/s/a-AAAAAAAAAAAAAAAA", 40, ""),
    ]
    assert [(m["path"], m["delta"]) for m in moved["down"]] == [("/topics/gpt-6", -30)]


def test_dormant_shares_are_old_clickless_and_nearly_invisible():
    old = NOW - timedelta(days=120)
    shares = [
        {"share_id": "AAAAAAAAAAAAAAAA", "slug": "dead", "created_at": old},
        {"share_id": "BBBBBBBBBBBBBBBB", "slug": "alive", "created_at": old},
        {"share_id": "CCCCCCCCCCCCCCCC", "slug": "young", "created_at": NOW - timedelta(days=30)},
        {"share_id": "DDDDDDDDDDDDDDDD", "slug": "kept", "created_at": old},
        {"share_id": "EEEEEEEEEEEEEEEE", "slug": "clicked", "created_at": old},
    ]
    window = [
        # A renamed slug still belongs to the same share id.
        row([SITE + "/s/old-title-AAAAAAAAAAAAAAAA"], 3),
        row([SITE + "/s/alive-BBBBBBBBBBBBBBBB"], 10),
        row([SITE + "/s/clicked-EEEEEEEEEEEEEEEE"], 2, clicks=1),
    ]
    dormant = seo_pulse.dormant_shares(shares, window, now=NOW, keep_ids={"DDDDDDDDDDDDDDDD"})
    assert dormant == [{
        "share_id": "AAAAAAAAAAAAAAAA", "path": "/s/dead-AAAAAAAAAAAAAAAA", "impressions_90d": 3,
    }]


def test_first_tick_only_schedules_and_later_ticks_wait_until_due(monkeypatch):
    db, notes, moderated = Db(), [], []
    service = service_with(db, None, [], notes, monkeypatch, moderated)
    early = NOW - timedelta(days=1)
    service.clock = lambda: early
    assert service.run() == {"status": "scheduled"}
    assert db.doc.data["next_run_at"] == NOW
    assert service.run() == {"status": "not_due"}
    db.doc.data["enabled"] = False
    assert service.run() == {"status": "disabled"}
    assert notes == [] and moderated == []


def test_run_reports_moves_noindexes_dormant_pages_and_releases_the_lease(monkeypatch):
    db, notes, moderated = Db(), [], []
    window = seo_pulse.report_window(NOW.date())
    client = Client(window)
    old = NOW - timedelta(days=200)
    shares = [
        {"share_id": "ZZZZZZZZZZZZZZZZ", "slug": "nobody-reads-this", "created_at": old},
        {"share_id": "BBBBBBBBBBBBBBBB", "slug": "old-but-alive", "created_at": old},
    ]
    service = service_with(db, client, shares, notes, monkeypatch, moderated)
    db.doc.set({"next_run_at": NOW - timedelta(minutes=1)})

    assert service.run() == {"status": "completed"}

    saved = db.doc.data
    report = saved["report"]
    assert report["week"] == {"impressions": 160, "clicks": 2, "position": 8.0}
    assert report["prev_week"]["impressions"] == 40
    assert report["movers"]["up"][0]["top_query"] == "consens"
    assert moderated == [("ZZZZZZZZZZZZZZZZ", False)]
    assert [item["share_id"] for item in saved["noindexed"]] == ["ZZZZZZZZZZZZZZZZ"]
    assert saved["history"] == [{"end": window["end"].isoformat(), "impressions": 160, "clicks": 2}]
    assert saved["lease_until"] is None and saved["lease_run_id"] == ""
    assert saved["next_run_at"] == NOW + timedelta(days=7)
    assert len(notes) == 1
    note = notes[0]
    assert "Impressions 160 (prev 40, +300%)" in note
    assert '↑ / +110 · "consens"' in note
    assert "↓ /topics/gpt-6 -30" in note
    assert "Set to noindex: 1 page(s)" in note
    assert len(note.splitlines()) <= 12


def test_rerunning_the_same_week_replaces_its_history_entry(monkeypatch):
    db, notes, moderated = Db(), [], []
    client = Client(seo_pulse.report_window(NOW.date()))
    service = service_with(db, client, [], notes, monkeypatch, moderated)
    service.run(force=True)
    service.run(force=True)
    assert len(db.doc.data["history"]) == 1


def test_keep_indexed_reindexes_and_exempts_the_page(monkeypatch):
    db, notes, moderated = Db(), [], []
    service = service_with(db, None, [], notes, monkeypatch, moderated)
    db.doc.set({"noindexed": [{"share_id": "ZZZZZZZZZZZZZZZZ", "path": "/s/x-ZZZZZZZZZZZZZZZZ"}]})
    status = service.keep_indexed("ZZZZZZZZZZZZZZZZ", admin_uid="admin-1")
    assert moderated == [("ZZZZZZZZZZZZZZZZ", True)]
    assert status["noindexed"] == []
    assert status["keep_share_ids"] == ["ZZZZZZZZZZZZZZZZ"]


def test_failure_note_is_one_line_plus_link():
    text = seo_pulse.format_message({"error": "Not configured: GSC_SITE_URL."}, "https://x/admin#seo")
    assert text == "SEO pulse failed: Not configured: GSC_SITE_URL.\nhttps://x/admin#seo"


def test_admin_endpoints_expose_status_run_and_keep(monkeypatch):
    calls = []

    class Service:
        def status(self):
            return {"enabled": True, "report": None}

        def run(self, *, force):
            calls.append(("run", force))
            return {"status": "completed"}

        def set_enabled(self, enabled):
            calls.append(("enabled", enabled))
            return {"enabled": enabled}

        def keep_indexed(self, share_id, *, admin_uid):
            calls.append(("keep", share_id, admin_uid))
            return {"keep_share_ids": [share_id]}

    monkeypatch.setattr(admin_router, "_require_admin", lambda request, data: "admin-1")
    monkeypatch.setattr(seo_pulse, "default_service", Service())
    client = TestClient(main.app)

    assert client.get("/api/admin/seo").json() == {"enabled": True, "report": None}
    assert client.post("/api/admin/seo/run", json={}).status_code == 200
    assert client.put("/api/admin/seo/config", json={"enabled": False}).json() == {"enabled": False}
    kept = client.post("/api/admin/seo/shares/ZZZZZZZZZZZZZZZZ/keep", json={})
    assert kept.json() == {"keep_share_ids": ["ZZZZZZZZZZZZZZZZ"]}
    assert calls == [("run", True), ("enabled", False), ("keep", "ZZZZZZZZZZZZZZZZ", "admin-1")]


def test_report_window_ends_two_days_back_and_compares_full_weeks():
    window = seo_pulse.report_window(date(2026, 10, 5))
    assert window["end"] == date(2026, 10, 3)
    assert window["start"] == date(2026, 9, 27)
    assert window["prev_end"] == date(2026, 9, 26)
    assert window["prev_start"] == date(2026, 9, 20)

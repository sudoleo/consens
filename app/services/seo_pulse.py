"""Weekly SEO pulse: a short, deterministic Search Console note for the admin.

Replaces the Scheduled Publisher and the LLM portfolio review (2026-10-04).
Sixteen auto-published pages earned two clicks in eleven weeks, and the
weekly review texts went unread. The pulse reads Search Console live (no
stored per-page metrics, no LLM), says in a few lines what moved and why, and
does exactly one thing on its own: an indexed share page that stayed
invisible for 90 days goes to noindex. "Keep indexed" in the admin undoes
that and exempts the page from later sweeps.
"""

from __future__ import annotations

import asyncio
import logging
import os
import uuid
from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from firebase_admin import firestore

from app.core.background_tasks import task_succeeded
from app.core.observability import safe_exception
from app.core.security import db_firestore
from app.services import share_snapshots, telegram_notifier
from app.services.google_search_console import (
    GoogleSearchConsoleClient,
    SearchConsoleError,
)


CONFIG_COLLECTION = "app_config"
CONFIG_DOCUMENT = "seo_pulse"
RUN_WEEKDAY = 0  # Monday
RUN_TIME = time(9, 0)
TIMEZONE = "Europe/Berlin"
SCHEDULER_TICK_SECONDS = 15 * 60
LEASE_MINUTES = 15
# Search Console needs about two days before a day is complete.
DATA_LAG_DAYS = 2
WEEK_DAYS = 7
HISTORY_WEEKS = 12
MOVERS_UP = 3
MOVERS_DOWN = 2
DORMANT_AFTER_DAYS = 90
DORMANT_MAX_IMPRESSIONS = 10
MAX_NOINDEX_PER_RUN = 25
NOINDEX_LOG_LIMIT = 50
DEFAULT_ADMIN_URL = "https://www.consens.io/admin#seo"


class PulseAlreadyRunning(Exception):
    pass


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value) -> datetime | None:
    if not isinstance(value, datetime):
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def next_run_after(now: datetime) -> datetime:
    """The next Monday 09:00 Europe/Berlin strictly after ``now``."""
    zone = ZoneInfo(TIMEZONE)
    local = now.astimezone(zone)
    candidate = datetime.combine(
        local.date() + timedelta(days=(RUN_WEEKDAY - local.weekday()) % 7),
        RUN_TIME, tzinfo=zone,
    )
    if candidate <= local:
        candidate += timedelta(days=7)
    return candidate.astimezone(timezone.utc)


def page_path(url: str) -> str:
    return urlsplit(str(url or "")).path or "/"


def share_id_from_path(path: str) -> str:
    if not path.startswith("/s/"):
        return ""
    return share_snapshots.split_slug_id(path[3:])[1]


def report_window(today: date) -> dict:
    end = today - timedelta(days=DATA_LAG_DAYS)
    start = end - timedelta(days=WEEK_DAYS - 1)
    prev_end = start - timedelta(days=1)
    return {
        "start": start,
        "end": end,
        "prev_start": prev_end - timedelta(days=WEEK_DAYS - 1),
        "prev_end": prev_end,
        "dormant_start": end - timedelta(days=DORMANT_AFTER_DAYS - 1),
    }


def _totals(daily_rows: list[dict], start: date, end: date) -> dict:
    impressions = clicks = weighted_position = 0.0
    for row in daily_rows:
        day = str((row.get("keys") or [""])[0])
        if start.isoformat() <= day <= end.isoformat():
            row_impressions = float(row.get("impressions") or 0)
            impressions += row_impressions
            clicks += float(row.get("clicks") or 0)
            weighted_position += float(row.get("position") or 0) * row_impressions
    return {
        "impressions": int(impressions),
        "clicks": int(clicks),
        "position": round(weighted_position / impressions, 1) if impressions else None,
    }


def _by_path(rows: list[dict]) -> dict[str, dict]:
    pages: dict[str, dict] = defaultdict(lambda: {"impressions": 0, "clicks": 0})
    for row in rows:
        path = page_path((row.get("keys") or [""])[0])
        pages[path]["impressions"] += int(row.get("impressions") or 0)
        pages[path]["clicks"] += int(row.get("clicks") or 0)
    return pages


def _top_queries(rows: list[dict]) -> dict[str, str]:
    best: dict[str, tuple[int, str]] = {}
    for row in rows:
        keys = row.get("keys") or []
        if len(keys) < 2:
            continue
        path, query = page_path(keys[0]), str(keys[1])
        impressions = int(row.get("impressions") or 0)
        if impressions > best.get(path, (0, ""))[0]:
            best[path] = (impressions, query)
    return {path: query for path, (_, query) in best.items()}


def movers(page_week: list[dict], page_prev: list[dict], page_query_week: list[dict]) -> dict:
    week, prev = _by_path(page_week), _by_path(page_prev)
    queries = _top_queries(page_query_week)
    changes = []
    for path in set(week) | set(prev):
        now_imp = week.get(path, {}).get("impressions", 0)
        before = prev.get(path, {}).get("impressions", 0)
        if now_imp == before:
            continue
        changes.append({
            "path": path,
            "impressions": now_imp,
            "prev_impressions": before,
            "delta": now_imp - before,
            "clicks": week.get(path, {}).get("clicks", 0),
            "top_query": queries.get(path, ""),
        })
    up = sorted((c for c in changes if c["delta"] > 0), key=lambda c: (-c["delta"], c["path"]))
    down = sorted((c for c in changes if c["delta"] < 0), key=lambda c: (c["delta"], c["path"]))
    return {"up": up[:MOVERS_UP], "down": down[:MOVERS_DOWN]}


def dormant_shares(shares: list[dict], page_window: list[dict], *, now: datetime,
                   keep_ids: set[str]) -> list[dict]:
    """Indexed shares older than the window with no click and <10 impressions in it."""
    seen: dict[str, dict] = defaultdict(lambda: {"impressions": 0, "clicks": 0})
    for path, metrics in _by_path(page_window).items():
        share_id = share_id_from_path(path)
        if share_id:
            seen[share_id]["impressions"] += metrics["impressions"]
            seen[share_id]["clicks"] += metrics["clicks"]
    cutoff = now - timedelta(days=DORMANT_AFTER_DAYS)
    dormant = []
    for share in shares:
        share_id = share["share_id"]
        created = _as_utc(share.get("created_at"))
        if share_id in keep_ids or not created or created > cutoff:
            continue
        metrics = seen.get(share_id, {"impressions": 0, "clicks": 0})
        if metrics["clicks"] == 0 and metrics["impressions"] < DORMANT_MAX_IMPRESSIONS:
            dormant.append({
                "share_id": share_id,
                "path": share_snapshots.share_path(share.get("slug") or "", share_id),
                "impressions_90d": metrics["impressions"],
            })
    dormant.sort(key=lambda item: (item["impressions_90d"], item["path"]))
    return dormant[:MAX_NOINDEX_PER_RUN]


def _date_label(day: date) -> str:
    return f"{day.day} {day.strftime('%b')}"


def _change(now: int, before: int) -> str:
    if not before:
        return f"prev {before}"
    return f"prev {before}, {round((now - before) * 100 / before):+d}%"


def format_message(report: dict, admin_url: str = DEFAULT_ADMIN_URL) -> str:
    if report.get("error"):
        return f"SEO pulse failed: {report['error']}\n{admin_url}"
    week, prev = report["week"], report["prev_week"]
    start = date.fromisoformat(report["window"]["start"])
    end = date.fromisoformat(report["window"]["end"])
    position = f" · avg pos {week['position']}" if week.get("position") else ""
    lines = [
        f"SEO week {_date_label(start)} – {_date_label(end)}",
        f"Impressions {week['impressions']} ({_change(week['impressions'], prev['impressions'])})"
        f" · clicks {week['clicks']} (prev {prev['clicks']}){position}",
        "",
    ]
    moved = [("↑", item) for item in report["movers"]["up"]]
    moved += [("↓", item) for item in report["movers"]["down"]]
    if moved:
        for arrow, item in moved:
            path = item["path"] if len(item["path"]) <= 48 else item["path"][:47] + "…"
            query = f' · "{item["top_query"]}"' if item.get("top_query") else ""
            lines.append(f"{arrow} {path} {item['delta']:+d}{query}")
    else:
        lines.append("Nothing moved.")
    noindexed = report.get("noindexed") or []
    if noindexed:
        lines += ["", f"Set to noindex: {len(noindexed)} page(s) without a click and "
                      f"<{DORMANT_MAX_IMPRESSIONS} impressions in {DORMANT_AFTER_DAYS} days "
                      "(undo in admin)"]
    lines += ["", admin_url]
    return "\n".join(lines)


class SeoPulseService:
    def __init__(self, db, *, client_factory=GoogleSearchConsoleClient.from_env,
                 clock=utcnow, notify=None):
        self.db = db
        self.client_factory = client_factory
        self.clock = clock
        self.notify = notify or telegram_notifier.send_admin_note

    @property
    def config_ref(self):
        return self.db.collection(CONFIG_COLLECTION).document(CONFIG_DOCUMENT)

    def _config(self) -> dict:
        snapshot = self.config_ref.get()
        data = (snapshot.to_dict() if snapshot.exists else None) or {}
        data.setdefault("enabled", True)
        return data

    def status(self) -> dict:
        config = self._config()
        now = self.clock()
        lease = _as_utc(config.get("lease_until"))
        next_run = _as_utc(config.get("next_run_at")) or next_run_after(now)
        return {
            "enabled": bool(config["enabled"]),
            "running": bool(lease and lease > now),
            "last_run_at": _iso(config.get("last_run_at")),
            "next_run_at": next_run.isoformat() if config["enabled"] else None,
            "report": config.get("report"),
            "history": list(config.get("history") or []),
            "noindexed": list(config.get("noindexed") or []),
            "keep_share_ids": list(config.get("keep_share_ids") or []),
        }

    def set_enabled(self, enabled: bool) -> dict:
        self.config_ref.set({"enabled": bool(enabled), "updated_at": self.clock()}, merge=True)
        return self.status()

    def keep_indexed(self, share_id: str, *, admin_uid: str) -> dict:
        """Undo an automatic noindex and keep the page out of later sweeps."""
        share_snapshots.moderate_share(
            share_id, indexed=True, db=self.db, actor_uid=admin_uid, source="seo_pulse_keep",
        )
        config = self._config()
        keep = sorted(set(config.get("keep_share_ids") or []) | {share_id})
        noindexed = [
            item for item in (config.get("noindexed") or [])
            if item.get("share_id") != share_id
        ]
        self.config_ref.set({
            "keep_share_ids": keep, "noindexed": noindexed, "updated_at": self.clock(),
        }, merge=True)
        return self.status()

    def _acquire(self, run_id: str, now: datetime) -> bool:
        lease_until = now + timedelta(minutes=LEASE_MINUTES)

        def claim(transaction=None):
            # A Transaction without writes has len() == 0 and is falsy, so
            # test for None: a truthiness check silently skipped the
            # transactional read and let two workers take the same lease.
            in_transaction = transaction is not None
            snapshot = (self.config_ref.get(transaction=transaction) if in_transaction
                        else self.config_ref.get())
            current = _as_utc(((snapshot.to_dict() if snapshot.exists else None) or {}).get("lease_until"))
            if current and current > now:
                return False
            values = {"lease_until": lease_until, "lease_run_id": run_id}
            if in_transaction:
                transaction.set(self.config_ref, values, merge=True)
            else:
                self.config_ref.set(values, merge=True)
            return True

        if hasattr(self.db, "transaction"):
            return bool(firestore.transactional(claim)(self.db.transaction()))
        return claim()

    def _indexed_shares(self) -> list[dict]:
        query = self.db.collection(share_snapshots.SHARES_COLLECTION).where(
            filter=firestore.FieldFilter("indexed", "==", True)
        )
        shares = []
        for doc in query.stream():
            data = doc.to_dict() or {}
            if data.get("status") == "active":
                shares.append({
                    "share_id": doc.id,
                    "slug": data.get("slug") or "",
                    "created_at": data.get("created_at"),
                })
        return shares

    def _build(self, now: datetime, keep_ids: set[str]) -> dict:
        client = self.client_factory()
        window = report_window(now.date())
        daily = client.search(window["prev_start"], window["end"], ["date"])
        page_week = client.search(window["start"], window["end"], ["page"])
        page_prev = client.search(window["prev_start"], window["prev_end"], ["page"])
        page_query_week = client.search(window["start"], window["end"], ["page", "query"])
        page_window = client.search(window["dormant_start"], window["end"], ["page"])
        dormant = dormant_shares(self._indexed_shares(), page_window, now=now, keep_ids=keep_ids)
        noindexed = []
        for item in dormant:
            try:
                share_snapshots.moderate_share(
                    item["share_id"], indexed=False, db=self.db, source="seo_pulse_dormant",
                )
            except Exception as exc:
                logging.warning("SEO pulse noindex failed share=%s category=%s",
                                item["share_id"], safe_exception(exc))
                continue
            noindexed.append({**item, "at": now.isoformat()})
        return {
            "window": {key: value.isoformat() for key, value in window.items()},
            "week": _totals(daily, window["start"], window["end"]),
            "prev_week": _totals(daily, window["prev_start"], window["prev_end"]),
            "movers": movers(page_week, page_prev, page_query_week),
            "noindexed": noindexed,
        }

    def run(self, *, force: bool = False) -> dict:
        now = self.clock()
        config = self._config()
        if not force:
            if not config["enabled"]:
                return {"status": "disabled"}
            due = _as_utc(config.get("next_run_at"))
            if due is None:
                # First tick after deploy: schedule, do not fire immediately.
                self.config_ref.set({"next_run_at": next_run_after(now)}, merge=True)
                return {"status": "scheduled"}
            if due > now:
                return {"status": "not_due"}
        run_id = uuid.uuid4().hex
        if not self._acquire(run_id, now):
            raise PulseAlreadyRunning()
        keep_ids = set(config.get("keep_share_ids") or [])
        try:
            report = self._build(now, keep_ids)
        except SearchConsoleError as exc:
            report = {"error": exc.safe_message}
        except Exception as exc:
            logging.error("SEO pulse failed category=%s", safe_exception(exc))
            report = {"error": "The weekly report failed; see server logs."}
        report["generated_at"] = now.isoformat()
        updates = {
            "report": report,
            "last_run_at": now,
            "next_run_at": next_run_after(now),
            "lease_until": None,
            "lease_run_id": "",
        }
        if not report.get("error"):
            history = [
                entry for entry in (config.get("history") or [])
                if entry.get("end") != report["window"]["end"]
            ]
            history.append({
                "end": report["window"]["end"],
                "impressions": report["week"]["impressions"],
                "clicks": report["week"]["clicks"],
            })
            updates["history"] = history[-HISTORY_WEEKS:]
            updates["noindexed"] = (
                report["noindexed"] + list(config.get("noindexed") or [])
            )[:NOINDEX_LOG_LIMIT]
        self.config_ref.set(updates, merge=True)
        admin_url = str(os.environ.get("SEO_ADMIN_URL") or DEFAULT_ADMIN_URL).strip()
        try:
            self.notify(format_message(report, admin_url))
        except Exception as exc:
            logging.warning("SEO pulse note failed category=%s", safe_exception(exc))
        return {"status": "failed" if report.get("error") else "completed"}


def _iso(value) -> str | None:
    value = _as_utc(value)
    return value.isoformat() if value else None


default_service = SeoPulseService(db_firestore)


async def seo_pulse_scheduler_loop():
    while True:
        try:
            result = await asyncio.to_thread(default_service.run)
        except PulseAlreadyRunning:
            result = {"status": "already_running"}
        task_succeeded("seo-pulse-scheduler", result=str(result.get("status") or "completed"))
        await asyncio.sleep(SCHEDULER_TICK_SECONDS)

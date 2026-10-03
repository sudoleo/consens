"""Model Pulse: how often a family's answer is the judge's pick, out of the
judged runs it took part in.

An absolute pick count mostly measures how often a family was selected into
runs. The rate per appearance answers the visitor's question ("when this
model is in the run, how often does it give the best answer?"), and the fair
share (1/n per run of n answers) says what pure chance would give, so a
family in many small runs does not look better than one in large runs.

Every BestModel vote since this module stores ``participants`` (provider
keys of the answers the judge compared) and ``picked``. Older votes without
them stay in the all-time pick counter on ``leaderboard`` but cannot enter a
rate. ``scripts/backfill_model_pulse.py`` reconstructs them where the run is
still stored.

Reading: one process-wide ledger of the slim vote facts (time, source,
participants, pick; no owner, no prompt). A refresh reads only votes newer
than the last one seen, at most once a minute; a full reload every six hours
also drops votes removed by account deletion.
"""

from __future__ import annotations

import math
import threading
import time
from datetime import datetime, timedelta, timezone

from google.cloud.firestore_v1.base_query import FieldFilter

from app.core import config as cfg

VOTES_COLLECTION = "model_votes"
PULSE_VERSION = 1
MIN_RUNS = 10
PERIODS = {"7d": 7, "30d": 30, "90d": 90, "all": None}
DEFAULT_PERIOD = "all"
MODES = ("all", "consensus", "agent")
SORTS = ("rate", "lift", "runs")

FAMILY_NAMES = {
    "openai": "OpenAI / ChatGPT",
    "mistral": "Mistral",
    "anthropic": "Anthropic / Claude",
    "gemini": "Google / Gemini",
    "deepseek": "DeepSeek",
    "grok": "xAI / Grok",
    "kimi": "Moonshot AI / Kimi",
    "glm": "Z.ai / GLM",
    "meta": "Meta / Muse",
}
# The short name the landing page and sentences use.
FAMILY_SHORT = {key: provider.title for key, provider in cfg.PROVIDERS.items()}
FAMILY_ORDER = {key: index for index, key in enumerate(cfg.PROVIDERS)}

_KEY_BY_NAME = {}
for _key, _provider in cfg.PROVIDERS.items():
    for _name in (_key, _provider.label, _provider.title, _provider.citation_label):
        _KEY_BY_NAME[str(_name).strip().lower()] = _key
for _alias, _target in cfg.LEADERBOARD_MODEL_ALIASES.items():
    _KEY_BY_NAME[_alias.lower()] = _KEY_BY_NAME[_target.lower()]


def family_key(value) -> str | None:
    """Provider key for a vote label ("Anthropic-Pro", "Claude"), a provider
    key, or a citation string ("Anthropic Claude: claude-opus-5.5")."""
    text = str(value or "").strip()
    if not text:
        return None
    text = text.partition(":")[0].strip().lower()
    if text.endswith("-pro"):
        text = text[:-4]
    return _KEY_BY_NAME.get(text)


def participation(participants, picked) -> dict | None:
    """The fields a vote stores for the rate, or None when they would lie:
    fewer than two compared families, or a pick outside the run."""
    families = sorted(
        {key for key in (family_key(item) for item in participants or []) if key},
        key=FAMILY_ORDER.get,
    )
    pick = family_key(picked)
    if len(families) < 2 or pick not in families:
        return None
    return {"participants": families, "picked": pick, "pulse_version": PULSE_VERSION}


def consensus_participants(pending: dict) -> list[str]:
    """The families a Consensus judge compared, from the pending result."""
    included = pending.get("included_models") or []
    if not included:
        included = (pending.get("differences_data") or {}).get("models_compared") or []
    return [str(item) for item in included]


# ---------------------------------------------------------------- the ledger


def _utc(value):
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    return None


def _entry(data: dict):
    """The slim, anonymous fact of one vote, or None when it has no rate."""
    created = _utc(data.get("created_at"))
    shape = participation(data.get("participants"), data.get("picked"))
    if not created or not shape or data.get("vote_type", "BestModel") != "BestModel":
        return None
    return (created, "agent" if data.get("source") == "agent" else "consensus",
            tuple(shape["participants"]), shape["picked"])


class PulseLedger:
    REFRESH_SECONDS = 60
    FULL_RELOAD_SECONDS = 6 * 3600
    # A vote is stamped inside its transaction; one committed a moment after
    # a later-stamped one must still be found by the next delta read.
    OVERLAP = timedelta(minutes=5)

    def __init__(self):
        self._lock = threading.Lock()
        self._reset(None)

    def _reset(self, db):
        self._db = db
        self._entries: dict[str, tuple] = {}
        self._high_water = None
        self._checked_at = 0.0
        self._loaded_at = 0.0

    def entries(self, db) -> list[tuple]:
        with self._lock:
            now = time.monotonic()
            if db is not self._db or now - self._loaded_at > self.FULL_RELOAD_SECONDS:
                fresh = {}
                query = db.collection(VOTES_COLLECTION).where(
                    filter=FieldFilter("pulse_version", "==", PULSE_VERSION))
                for snapshot in query.stream(retry=None, timeout=20):
                    entry = _entry(snapshot.to_dict() or {})
                    if entry:
                        fresh[snapshot.id] = entry
                self._reset(db)
                self._entries, self._loaded_at = fresh, now
                self._checked_at = now
                self._high_water = max((e[0] for e in fresh.values()), default=None)
            elif now - self._checked_at > self.REFRESH_SECONDS:
                since = (self._high_water - self.OVERLAP) if self._high_water else \
                    datetime.now(timezone.utc) - timedelta(days=1)
                query = db.collection(VOTES_COLLECTION).where(
                    filter=FieldFilter("created_at", ">=", since))
                for snapshot in query.stream(retry=None, timeout=10):
                    entry = _entry(snapshot.to_dict() or {})
                    if entry:
                        self._entries[snapshot.id] = entry
                        if not self._high_water or entry[0] > self._high_water:
                            self._high_water = entry[0]
                self._checked_at = now
            return list(self._entries.values())


LEDGER = PulseLedger()


# ---------------------------------------------------------------- the view


def _icon(key):
    provider = cfg.PROVIDERS.get(key)
    return f"/static/icons/chat_icons/{provider.icon}" if provider else "/static/favicon.png"


def normalize(period=None, mode=None, rival=None, sort=None) -> dict:
    period = str(period or DEFAULT_PERIOD).strip().lower()
    mode = str(mode or "all").strip().lower()
    sort = str(sort or "rate").strip().lower()
    rival = family_key(rival) if rival else None
    if period not in PERIODS or mode not in MODES or sort not in SORTS:
        raise ValueError("Unsupported model pulse filter")
    return {"period": period, "mode": mode, "rival": rival, "sort": sort}


def build_view(entries, *, period=DEFAULT_PERIOD, mode="all", rival=None, sort="rate",
               now: datetime | None = None) -> dict:
    """Rates for one filter. Pure: tests and the landing preview call it
    with any list of ledger entries."""
    now = now or datetime.now(timezone.utc)
    days = PERIODS[period]
    cutoff = now - timedelta(days=days) if days else None
    runs = [
        entry for entry in entries
        if (cutoff is None or entry[0] >= cutoff)
        and (mode == "all" or entry[1] == mode)
        and (rival is None or rival in entry[2])
    ]
    stats = {key: {"runs": 0, "picks": 0, "expected": 0.0, "h2h_wins": 0, "h2h_losses": 0}
             for key in cfg.PROVIDERS}
    for _created, _source, participants, picked in runs:
        share = 1 / len(participants)
        for key in participants:
            row = stats.setdefault(key, {"runs": 0, "picks": 0, "expected": 0.0,
                                         "h2h_wins": 0, "h2h_losses": 0})
            row["runs"] += 1
            row["expected"] += share
            if key == picked:
                row["picks"] += 1
            if rival and key != rival:
                if picked == key:
                    row["h2h_wins"] += 1
                elif picked == rival:
                    row["h2h_losses"] += 1

    rows = []
    for key, row in stats.items():
        count = row["runs"]
        rate = row["picks"] / count if count else None
        fair = row["expected"] / count if count else None
        rows.append({
            "key": key,
            "family": FAMILY_NAMES.get(key, key),
            "short": FAMILY_SHORT.get(key, key),
            "icon": _icon(key),
            "runs": count,
            "picks": row["picks"],
            "rate": round(rate * 100, 1) if rate is not None else None,
            "fair_share": round(fair * 100, 1) if fair is not None else None,
            "lift": round(row["picks"] / row["expected"], 2) if row["expected"] else None,
            "interval": wilson_interval(row["picks"], count),
            "enough": count >= MIN_RUNS,
            "is_rival": key == rival,
            **({"h2h": {"wins": row["h2h_wins"], "losses": row["h2h_losses"]}}
               if rival and key != rival else {}),
        })

    sort_key = {
        "rate": lambda r: (r["rate"] or 0, r["runs"]),
        "lift": lambda r: (r["lift"] or 0, r["runs"]),
        "runs": lambda r: (r["runs"], r["rate"] or 0),
    }[sort]
    ranked = sorted((r for r in rows if r["enough"]), key=sort_key, reverse=True)
    sparse = sorted((r for r in rows if not r["enough"]),
                    key=lambda r: (-r["runs"], FAMILY_ORDER.get(r["key"], 99)))
    for index, row in enumerate(ranked, start=1):
        row["rank"] = index

    # The bars share one 0..scale axis in real percent; the scale only
    # stretches so the widest plausible range still fits.
    top = max([(r["interval"] or (0, 0))[1] for r in ranked] + [r["rate"] or 0 for r in ranked] + [0])
    scale = min(100, max(40, math.ceil(top / 10) * 10))
    leader = max(ranked, key=lambda r: (r["rate"] or 0, r["runs"]), default=None)
    sizes = [len(entry[2]) for entry in runs]
    return {
        "period": period,
        "mode": mode,
        "rival": rival,
        "sort": sort,
        "min_runs": MIN_RUNS,
        "scale": scale,
        "runs": len(runs),
        "average_field": round(sum(sizes) / len(sizes), 1) if sizes else None,
        "since": min((entry[0] for entry in runs), default=None),
        "leader": {
            "key": leader["key"], "short": leader["short"], "rate": leader["rate"],
            "icon": leader["icon"], "runs": leader["runs"],
            # How often the best answer came from someone else: the reason to
            # ask more than one model.
            "others_rate": round(100 - leader["rate"], 1),
        } if leader else None,
        "rows": ranked,
        "sparse": sparse,
    }


def public_view(db, **filters) -> dict:
    view = build_view(LEDGER.entries(db), **normalize(**filters))
    since = view["since"]
    view["since"] = since.date().isoformat() if since else None
    return view


def wilson_interval(picks: int, runs: int, z: float = 1.96):
    """95 % interval for a rate; used by the page's uncertainty band."""
    if not runs:
        return None
    p = picks / runs
    denominator = 1 + z * z / runs
    centre = (p + z * z / (2 * runs)) / denominator
    margin = z * math.sqrt(p * (1 - p) / runs + z * z / (4 * runs * runs)) / denominator
    return round(max(0.0, centre - margin) * 100, 1), round(min(1.0, centre + margin) * 100, 1)

"""A benchmark chart for Topics about a model family (since 2026-10-31).

A Topic about a model family ("Gemini 4") names that family in its
``benchmark.models`` setting. After each check the runner reads the
Artificial Analysis Intelligence Index once (free data API, key in
``ARTIFICIAL_ANALYSIS_API_KEY``) and stores a snapshot on the run: the
family's models next to the best model of each other lab. The page draws it
like the answer's figures (HTML/CSS bars, no copied image) with the
attribution the API requires.

Unlike ``topic_figures``, these numbers do not come from the answer: they
are third-party measurements, labelled and dated as such, and they show up
even when the models' searches missed a new release. A failure here only
costs the chart, never the check.
"""

from __future__ import annotations

import logging
import os
import re
import threading
import time
from datetime import date

import requests
from markupsafe import Markup, escape

from app.core.observability import safe_exception

API_URL = "https://artificialanalysis.ai/api/v2/data/llms/models"
API_KEY_ENV = "ARTIFICIAL_ANALYSIS_API_KEY"
# Attribution is a condition of the free API.
SOURCE_URL = "https://artificialanalysis.ai/"
METRIC = "artificial_analysis_intelligence_index"
METRIC_LABEL = "Artificial Analysis Intelligence Index"
MAX_PATTERNS = 4
MAX_OWN = 3
MAX_OTHERS = 5
MIN_ITEMS = 2
TIMEOUT_SECONDS = 15
# One read serves every Topic of a scheduler tick; the API allows 1,000 a day.
CACHE_SECONDS = 6 * 60 * 60

_CACHE: dict = {"at": 0.0, "rows": None}
_LOCK = threading.Lock()
# "Gemini 4 Carbon (High)" and "Gemini 4 Carbon (Low)" are one model at two
# settings; the chart keeps the better one.
_VARIANT_RE = re.compile(r"\s*\([^)]*\)\s*$")


class BenchmarkUnavailable(Exception):
    pass


def _norm(text) -> str:
    return " ".join(str(text or "").lower().replace("-", " ").replace("_", " ").split())


def normalize_config(value) -> dict:
    """The model names a Topic's chart is about, as the editor wrote them.

    Accepts a list or one string with a name per line (the admin form)."""
    models = value.get("models") if isinstance(value, dict) else value
    if isinstance(models, str):
        models = re.split(r"[\n,]", models)
    names, seen = [], set()
    for item in models if isinstance(models, list) else []:
        name = " ".join(str(item or "").split())[:60]
        if name and _norm(name) not in seen:
            seen.add(_norm(name))
            names.append(name)
    return {"models": names[:MAX_PATTERNS]}


def _matches(name: str, patterns) -> bool:
    """"Gemini 4" matches "Gemini 4 Carbon (High)", never "Gemini 4.5 Pro"."""
    text = _norm(name)
    return any(
        text == pattern or text.startswith(pattern + " ") or text.startswith(pattern + "(")
        for pattern in (_norm(item) for item in patterns) if pattern
    )


def _score(row):
    value = (row.get("evaluations") or {}).get(METRIC) if isinstance(row, dict) else None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
        return None
    return float(value)


def select(rows, patterns, *, fetched_on: str) -> dict | None:
    """The chart for one Topic: its family's models and the best of each other lab."""
    best: dict[str, dict] = {}
    for row in rows or []:
        score = _score(row)
        name = " ".join(str((row or {}).get("name") or "").split()) if score else ""
        if not name:
            continue
        creator = row.get("model_creator") if isinstance(row.get("model_creator"), dict) else {}
        item = {
            "name": name[:80],
            "creator": " ".join(str(creator.get("name") or "").split())[:60],
            "creator_id": str(creator.get("id") or creator.get("name") or ""),
            "score": round(score, 1),
            "own": _matches(name, patterns),
        }
        key = _norm(_VARIANT_RE.sub("", name))
        if key not in best or item["score"] > best[key]["score"]:
            best[key] = item
    ranked = sorted(best.values(), key=lambda item: -item["score"])
    own = [item for item in ranked if item["own"]][:MAX_OWN]
    if not own:
        return None
    own_labs = {item["creator_id"] for item in own}
    others, labs = [], set()
    for item in ranked:
        if item["own"] or item["creator_id"] in own_labs or item["creator_id"] in labs:
            continue
        labs.add(item["creator_id"])
        others.append(item)
        if len(others) == MAX_OTHERS:
            break
    items = sorted(own + others, key=lambda item: -item["score"])
    if len(items) < MIN_ITEMS:
        return None
    return {
        "source": "artificial_analysis",
        "metric": METRIC,
        "fetched_on": fetched_on,
        "items": [{key: item[key] for key in ("name", "creator", "score", "own")} for item in items],
    }


def configured() -> bool:
    return bool(str(os.environ.get(API_KEY_ENV) or "").strip())


def fetch_models(*, get=requests.get) -> list[dict]:
    """All LLM rows from the data API, cached for a few hours."""
    key = str(os.environ.get(API_KEY_ENV) or "").strip()
    if not key:
        raise BenchmarkUnavailable("not configured")
    with _LOCK:
        if _CACHE["rows"] is not None and time.monotonic() - _CACHE["at"] < CACHE_SECONDS:
            return _CACHE["rows"]
    response = get(
        API_URL, headers={"x-api-key": key, "Accept": "application/json"},
        timeout=TIMEOUT_SECONDS,
    )
    if getattr(response, "status_code", 0) != 200:
        raise BenchmarkUnavailable(f"HTTP {getattr(response, 'status_code', 'error')}")
    body = response.json()
    rows = body.get("data") if isinstance(body, dict) else None
    if not isinstance(rows, list):
        raise BenchmarkUnavailable("unexpected response")
    rows = [row for row in rows if isinstance(row, dict)]
    with _LOCK:
        _CACHE.update(at=time.monotonic(), rows=rows)
    return rows


def build(config, *, today: date, fetch=None) -> dict | None:
    """The snapshot a check stores, or ``None`` (no setting, no key, no data)."""
    patterns = normalize_config(config)["models"]
    if not patterns:
        return None
    if fetch is None:
        from app.services import watch_images

        # Tests, E2E and mock runs never call out; without a key there is nothing to ask.
        if not watch_images.background_enabled() or not configured():
            return None
        fetch = fetch_models
    try:
        return select(fetch(), patterns, fetched_on=today.isoformat())
    except Exception as exc:
        logging.warning("Topic benchmark skipped category=%s", safe_exception(exc))
        return None


def stored(value) -> dict | None:
    """A snapshot as stored on a run, structurally checked (older runs have none)."""
    if not isinstance(value, dict) or not isinstance(value.get("items"), list):
        return None
    items = []
    for item in value["items"]:
        if not isinstance(item, dict) or not isinstance(item.get("name"), str) or not item["name"]:
            continue
        score = item.get("score")
        if isinstance(score, bool) or not isinstance(score, (int, float)) or score <= 0:
            continue
        creator = item.get("creator")
        items.append({
            "name": item["name"], "creator": creator if isinstance(creator, str) else "",
            "score": score, "own": item.get("own") is True,
        })
    if len(items) < MIN_ITEMS or not any(item["own"] for item in items):
        return None
    fetched_on = value.get("fetched_on")
    return {**value, "items": items, "fetched_on": fetched_on if isinstance(fetched_on, str) else ""}


_ICON = (
    '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" '
    'stroke-linecap="round" aria-hidden="true"><path d="M3 13.5V9M8 13.5V3M13 13.5V6.5"/></svg>'
)


def _value(score) -> str:
    return f"{score:.1f}".removesuffix(".0")


def figure_html(snapshot: dict) -> Markup:
    """The chart as safe HTML; names from the API are escaped."""
    top = max(item["score"] for item in snapshot["items"])
    rows = "".join(
        f'<li class="af-row {"is-own" if item["own"] else "is-other"}">'
        f'<span class="af-label">{escape(item["name"])}'
        + (f'<span class="af-note">{escape(item["creator"])}</span>' if item["creator"] else "")
        + f'</span><span class="af-bar" aria-hidden="true"><i style="width:{max(100 * item["score"] / top, 1.5):.1f}%"></i></span>'
        f'<span class="af-value">{escape(_value(item["score"]))}</span></li>'
        for item in snapshot["items"]
    )
    try:
        day = date.fromisoformat(snapshot.get("fetched_on") or "")
        as_of = f", as of {day:%b} {day.day}, {day.year}"
    except ValueError:
        as_of = ""
    return Markup(
        '<figure class="af af-numbers af-benchmark">'
        f'<p class="af-kind">{_ICON}Benchmark</p>'
        f'<p class="af-title">{escape(METRIC_LABEL)}</p>'
        '<p class="af-unit">Higher is better. The other bars are the best model of each other lab.</p>'
        f'<ul class="af-rows has-bars">{rows}</ul>'
        f'<figcaption class="af-cap">Data: <a href="{SOURCE_URL}" target="_blank" rel="noopener">'
        f"Artificial Analysis</a>{escape(as_of)}. Measured by Artificial Analysis, not by consens.io.</figcaption>"
        "</figure>"
    )

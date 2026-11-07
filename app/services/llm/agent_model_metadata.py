"""Cached public provider metadata, never the allowlist of selectable models."""
from collections.abc import Mapping
from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import json
import logging
import os
from pathlib import Path
import threading
import time
from urllib.request import urlopen

BASELINE = json.loads(Path(__file__).with_name('agent_model_catalog.json').read_text(encoding='utf-8'))
MODELS_URL = 'https://openrouter.ai/api/v1/models'


def _normalize(entry):
    if not isinstance(entry, dict) or not isinstance(entry.get('id'), str):
        return None
    pricing = entry.get('pricing')
    context = entry.get('context_length')
    top = entry.get('top_provider') or {}
    if not isinstance(pricing, dict) or type(context) is not int or context <= 0 or not isinstance(top, dict):
        return None
    try:
        for key in ('prompt', 'completion', 'input_cache_read', 'input_cache_write', 'web_search'):
            value = pricing.get(key, pricing.get('prompt') if key != 'completion' else None)
            price = Decimal(str(value))
            if not price.is_finite() or price < 0:
                return None
    except (InvalidOperation, ValueError):
        return None
    maximum = top.get('max_completion_tokens')
    if maximum is not None and (type(maximum) is not int or maximum <= 0):
        return None
    reasoning = entry.get('reasoning') or {}
    if not isinstance(reasoning, dict):
        return None
    efforts = reasoning.get('supported_efforts', [])
    if efforts is not None and (not isinstance(efforts, list) or not all(isinstance(x, str) for x in efforts)):
        return None
    return {'pricing': pricing, 'context_length': context, 'top_provider': top, 'reasoning': reasoning, 'architecture': entry.get('architecture') if isinstance(entry.get('architecture'), dict) else {}}


def fetch_models():
    # Public endpoint: no keys, prompts, user identifiers or database data leave the app.
    with urlopen(MODELS_URL, timeout=5) as response:
        raw = response.read(8 * 1024 * 1024 + 1)
    if len(raw) > 8 * 1024 * 1024:
        raise ValueError('Model metadata response too large')
    rows = json.loads(raw).get('data')
    if not isinstance(rows, list):
        raise ValueError('Invalid model metadata response')
    models = {row['id']: metadata for row in rows if (metadata := _normalize(row)) is not None}
    if not models:
        raise ValueError('Empty model metadata response')
    return models


class CatalogSnapshot(Mapping):
    """The catalog as one snapshot() saw it, read like a dict. A model's
    entry is copied when it is first read, not the whole catalog: OpenRouter
    lists about 550 models, a copy of all of them takes about 20 ms, and a
    message reads the catalog some 45 times before its first request (once
    per model of the picker, mostly to read a single entry)."""

    def __init__(self, entries):
        # Shared between snapshots and never changed: every read copies.
        self._entries = entries
        self._copies = {}

    def __getitem__(self, key):
        if key not in self._copies:
            self._copies[key] = deepcopy(self._entries[key])
        return self._copies[key]

    def __contains__(self, key):
        return key in self._entries

    def __iter__(self):
        return iter(self._entries)

    def __len__(self):
        return len(self._entries)


class ModelMetadataCache:
    """OpenRouter's metadata, fetched again after five minutes (30 s after a
    failure). Only the process's first snapshot waits for the fetch; later
    ones hand out what is there while a thread fetches (``refreshing``), so
    no message waits for the whole catalog's download before its request."""

    def __init__(self):
        self._lock = threading.Lock()
        self._live = {}
        self._refresh_at = 0
        # Baseline and live entries merged, until the next refresh.
        self._merged = None
        self.refreshing = None

    def _fetch(self):
        try:
            models = fetch_models()
        except Exception as exc:
            logging.warning('Agent model metadata refresh failed category=%s', type(exc).__name__)
            return None
        version = datetime.now(timezone.utc).strftime('openrouter-%Y-%m-%dT%H:%M:%SZ')
        return {key: {**value, '_version': version} for key, value in models.items()}

    def _take(self, models):
        """Under the lock: a fetch's result (None: it failed)."""
        if models is None:
            self._refresh_at = time.monotonic() + 30
            return
        self._live.update(models)
        self._merged = None
        self._refresh_at = time.monotonic() + 300

    def _refresh(self):
        models = self._fetch()
        with self._lock:
            self._take(models)
            self.refreshing = None

    def snapshot(self):
        with self._lock:
            if time.monotonic() >= self._refresh_at and self.refreshing is None:
                if not self._live:
                    # Nothing fetched yet: the first snapshot waits for it,
                    # and callers at the same time wait with it.
                    self._take(self._fetch())
                else:
                    self.refreshing = threading.Thread(target=self._refresh, name='agent-model-metadata',
                                                       daemon=True)
                    self.refreshing.start()
            if self._merged is None:
                merged = {key: {**value, '_version': BASELINE['version']} for key, value in BASELINE['models'].items()}
                for key, value in self._live.items():
                    merged[key] = {**merged.get(key, {}), **value}
                self._merged = merged
            return CatalogSnapshot(self._merged)


_cache = ModelMetadataCache()


def snapshot():
    # Unit/browser suites stay offline; metadata integration tests replace this boundary.
    if os.getenv('UNIT_TEST_MODE') == '1' or os.getenv('E2E_TEST_MODE') == '1':
        return {key: {**deepcopy(value), '_version': BASELINE['version']} for key, value in BASELINE['models'].items()}
    return _cache.snapshot()


def pricing(model_id):
    """One model's OpenRouter prices (dollars per token, as strings), or None.

    For the pipeline's usage meter, which prices a call whose response named
    no cost. Live metadata first, then the baseline; offline in test suites."""
    if os.getenv('UNIT_TEST_MODE') == '1' or os.getenv('E2E_TEST_MODE') == '1':
        entry = BASELINE['models'].get(model_id)
    else:
        if time.monotonic() >= _cache._refresh_at:
            _cache.snapshot()  # refreshes the live metadata at most every 300 s
        with _cache._lock:
            entry = _cache._live.get(model_id) or BASELINE['models'].get(model_id)
    pricing = (entry or {}).get('pricing')
    return dict(pricing) if isinstance(pricing, dict) else None

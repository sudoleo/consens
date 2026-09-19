"""Cached public provider metadata, never the allowlist of selectable models."""
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
    return {'pricing': pricing, 'context_length': context, 'top_provider': top, 'reasoning': reasoning}


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


class ModelMetadataCache:
    def __init__(self):
        self._lock = threading.Lock()
        self._live = {}
        self._refresh_at = 0

    def snapshot(self):
        with self._lock:
            if time.monotonic() >= self._refresh_at:
                try:
                    models = fetch_models()
                    version = datetime.now(timezone.utc).strftime('openrouter-%Y-%m-%dT%H:%M:%SZ')
                    self._live.update({key: {**value, '_version': version} for key, value in models.items()})
                    self._refresh_at = time.monotonic() + 300
                except Exception as exc:
                    logging.warning('Agent model metadata refresh failed category=%s', type(exc).__name__)
                    self._refresh_at = time.monotonic() + 30
            result = {key: {**value, '_version': BASELINE['version']} for key, value in BASELINE['models'].items()}
            for key, value in self._live.items():
                result[key] = {**result.get(key, {}), **value}
            return deepcopy(result)


_cache = ModelMetadataCache()


def snapshot():
    # Unit/browser suites stay offline; metadata integration tests replace this boundary.
    if os.getenv('UNIT_TEST_MODE') == '1' or os.getenv('E2E_TEST_MODE') == '1':
        return {key: {**deepcopy(value), '_version': BASELINE['version']} for key, value in BASELINE['models'].items()}
    return _cache.snapshot()

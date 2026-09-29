"""In-memory answer receipts for /consensus route tests (review R09).

The real ``answer_receipts.store_receipt`` / ``load_receipts`` run against a
tiny document store, so every route test exercises the production binding
and integrity checks instead of a stub that accepts anything.
"""

from __future__ import annotations

from types import SimpleNamespace

import app.core.config as cfg
from app.services import answer_receipts

RUN_ID = "run_receipts_test"


class _Doc:
    def __init__(self, db, path):
        self.db, self.path = db, path

    def collection(self, name):
        return _Collection(self.db, self.path + (name,))

    def get(self, **_kwargs):
        value = self.db.docs.get(self.path)
        return SimpleNamespace(exists=value is not None, to_dict=lambda: dict(value or {}))

    def set(self, data, merge=False):
        self.db.docs[self.path] = {**(self.db.docs.get(self.path, {}) if merge else {}), **data}


class _Collection:
    def __init__(self, db, path):
        self.db, self.path = db, path

    def document(self, name):
        return _Doc(self.db, self.path + (name,))


class ReceiptDB:
    def __init__(self):
        self.docs = {}

    def collection(self, name):
        return _Collection(self, (name,))


def install(monkeypatch, chat_router):
    store = answer_receipts.ReceiptStore(ReceiptDB())
    monkeypatch.setattr(chat_router, "answer_receipt_store", store)
    return store


def issue(store, *, uid, question, provider, text, run_key=None, run_id=RUN_ID,
          model=None, sources=None, state="complete", provenance="developer"):
    """Store one /ask answer exactly as handle_ask would; returns its id."""
    label = cfg.PROVIDER_LABEL_BY_ID.get(str(provider).lower(), provider)
    key = next(k for k, v in cfg.PROVIDER_LABEL_BY_ID.items() if v == label)
    return store.store(
        uid=uid,
        run=answer_receipts.run_binding(uid, run_key, run_id),
        question=question,
        provider=label,
        model=model or cfg.PROVIDERS[key].base_model,
        text=text,
        sources=sources or [],
        state=state,
        provenance=provenance,
    )


class ReceiptClient:
    """TestClient wrapper: /consensus payloads with answer text are converted
    to receipts first, mirroring what the browser now sends after /ask_*."""

    def __init__(self, client, store, uid):
        self._client, self.store, self.uid = client, store, uid

    def post(self, url, *args, json=None, **kwargs):
        if url == "/consensus" and isinstance(json, dict) and "answer_receipts" not in json:
            json = receipted(self.store, json, uid=self.uid)
        return self._client.post(url, *args, json=json, **kwargs)

    def __getattr__(self, name):
        return getattr(self._client, name)


def receipted(store, payload, *, uid, provenance=None):
    """Convert legacy answer text fields of a test payload into receipts.

    ``answers`` / ``answer_<family>`` become ``answer_receipts``; per-model
    sources move from ``model_sources`` into the receipts. Empty answers are
    dropped, like the browser drops answers that never completed.
    """
    payload = dict(payload)
    question = payload.get("question") or ""
    run_key = payload.get("usage_run_key")
    payload.setdefault("run_id", RUN_ID)
    if provenance is None:
        provenance = "byok" if str(payload.get("useOwnKeys")).lower() == "true" else "developer"
    sources = payload.pop("model_sources", None) or {}
    supplied = payload.pop("answers", None)
    texts = {}
    for provider, label in cfg.PROVIDER_LABEL_BY_ID.items():
        field = "answer_claude" if provider == "anthropic" else f"answer_{provider}"
        value = payload.pop(field, None)
        if isinstance(supplied, dict):
            value = supplied.get(provider, supplied.get(label, value))
        if isinstance(value, str) and value.strip():
            texts[label] = value
    payload["answer_receipts"] = {
        label: issue(
            store, uid=uid, question=question, provider=label, text=text,
            run_key=run_key, run_id=payload["run_id"],
            sources=sources.get(label) or sources.get(label.lower()) or [],
            provenance=provenance,
        )
        for label, text in texts.items()
    }
    return payload

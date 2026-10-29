from __future__ import annotations

import re
import unicodedata
import copy
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.core.config as cfg
from app.api.routers import chat_history as chat_history_router
from app.core.rate_limit import api_uid_limiter, limiter
from app.core.security import CustomSecurityMiddleware
from app.services import chat_store
from google.api_core.datetime_helpers import DatetimeWithNanoseconds


AUTH_OWNER = {"Authorization": "Bearer owner-token"}
AUTH_OTHER = {"Authorization": "Bearer other-token"}
# Eine echte Engine aus ALLOWED_CONSENSUS_MODELS.
TURN_PAYLOAD = {
    "question": "What changed?",
    "mode": "regular",
    "deep_search": False,
    "selected_models": ["OpenAI", "Gemini"],
    "consensus_model": "OpenAI",
}
PROVIDERS = ("OpenAI", "Mistral", "Anthropic", "Gemini", "DeepSeek", "Grok")


class FakeSnapshot:
    def __init__(self, reference, data):
        self.reference = reference
        self.id = reference.id
        self._data = None if data is None else dict(data)

    @property
    def exists(self):
        return self._data is not None

    def to_dict(self):
        return None if self._data is None else dict(self._data)


class FakeDocumentRef:
    def __init__(self, database, path):
        self.database = database
        self.path = tuple(path)
        self.id = self.path[-1]

    def collection(self, name):
        return FakeCollectionRef(self.database, (*self.path, name))

    def get(self, transaction=None, **_options):
        # ``timeout``/``retry`` as the real client takes them; no effect here.
        if transaction is not None:
            return transaction.get(self)
        self.database.read_log.append(self.path)
        self.database.full_document_log.append(self.path)
        return FakeSnapshot(self, self.database.documents.get(self.path))

    def set(self, data, merge=False):
        self.database.apply_set(self, data, merge=merge)

    def update(self, data):
        self.database.apply_update(self, data)

    def delete(self):
        self.database.documents.pop(self.path, None)
        self.database.write_log.append(("delete", self.path))


class FakeAggregationResult:
    def __init__(self, value):
        self.value = value


class FakeAggregation:
    def __init__(self, value):
        self._value = value

    def get(self):
        return [[FakeAggregationResult(self._value)]]


class FakeCollectionRef:
    def __init__(self, database, path):
        self.database = database
        self.path = tuple(path)

    def document(self, document_id):
        return FakeDocumentRef(self.database, (*self.path, document_id))

    def order_by(self, field, direction=None):
        return FakeQuery(self, [(field, direction)])

    def where(self, filter=None):
        return FakeQuery(self, [], filters=[filter])

    def select(self, field_paths):
        # Like Firestore: only the named top-level fields come back, so code
        # that forgets a field it needs fails here as it would in prod.
        return FakeQuery(self, []).select(field_paths)

    def limit(self, value):
        # Echte CollectionReference kann das auch ohne vorheriges order_by.
        return FakeQuery(self, []).limit(value)

    def count(self):
        # Bildet die Firestore-Aggregation nach, inklusive der verschachtelten
        # Ergebnisform [[AggregationResult]], die der Store auspacken muss.
        return FakeAggregation(len(self._child_paths()))

    def _child_paths(self):
        depth = len(self.path) + 1
        return sorted(
            path
            for path in self.database.documents
            if len(path) == depth and path[:-1] == self.path
        )

    def stream(self):
        for path in self._child_paths():
            ref = FakeDocumentRef(self.database, path)
            self.database.read_log.append(path)
            yield FakeSnapshot(ref, self.database.documents.get(path))

    def list_documents(self):
        for path in self._child_paths():
            self.database.read_log.append(path)
            yield FakeDocumentRef(self.database, path)


class FakeQuery:
    def __init__(self, collection, orders, filters=None):
        self.collection = collection
        self.orders = list(orders)
        self.filters = [f for f in (filters or []) if f is not None]
        self.after_id = None
        self.after_values = None
        self.page_limit = None
        self.projection = None

    def select(self, field_paths):
        self.projection = [str(field) for field in field_paths]
        return self

    def order_by(self, field, direction=None):
        self.orders.append((field, direction))
        return self

    def where(self, filter=None):
        if filter is not None:
            self.filters.append(filter)
        return self

    def _matches_filters(self, snapshot):
        data = snapshot.to_dict() or {}
        for condition in self.filters:
            field = getattr(condition, "field_path", None)
            op = getattr(condition, "op_string", None)
            value = getattr(condition, "value", None)
            if op not in {"==", "<="}:
                raise AssertionError(f"unsupported fake filter operator: {op}")
            actual = data
            for part in field.split('.'):
                actual = actual.get(part) if isinstance(actual, dict) else None
            if op == "==" and actual != value:
                return False
            if op == "<=" and (actual is None or actual > value):
                return False
        return True

    def start_after(self, boundary):
        if isinstance(boundary, dict):
            self.after_values = {str(key): value for key, value in boundary.items()}
        else:
            self.after_id = boundary.id
        return self

    def limit(self, value):
        self.page_limit = value
        return self

    def stream(self):
        depth = len(self.collection.path) + 1
        items = []
        for path, data in self.collection.database.documents.items():
            if len(path) == depth and path[:-1] == self.collection.path:
                items.append(FakeSnapshot(FakeDocumentRef(self.collection.database, path), data))

        if self.filters:
            items = [item for item in items if self._matches_filters(item)]

        for field, direction in reversed(self.orders):
            reverse = str(direction).upper().endswith("DESCENDING")
            if str(field) != "__name__":
                items.sort(
                    key=lambda snapshot: snapshot.to_dict().get(field),
                    reverse=reverse,
                )
            else:
                items.sort(key=lambda snapshot: snapshot.id, reverse=reverse)

        if self.after_id is not None:
            ids = [snapshot.id for snapshot in items]
            if self.after_id in ids:
                items = items[ids.index(self.after_id) + 1:]
        if self.after_values is not None:
            items = [snapshot for snapshot in items if self._is_after(snapshot)]
        if self.page_limit is not None:
            items = items[:self.page_limit]
        if self.projection is None:
            self.collection.database.full_document_log.extend(item.reference.path for item in items)
        else:
            items = [
                FakeSnapshot(item.reference, {
                    field: value for field, value in item.to_dict().items()
                    if field in self.projection
                })
                for item in items
            ]
        return items

    def _is_after(self, snapshot):
        data = snapshot.to_dict()
        for field, direction in self.orders:
            field_name = str(field)
            document_value = snapshot.id if field_name == "__name__" else data.get(field_name)
            cursor_value = self.after_values[field_name]
            if document_value == cursor_value:
                continue
            descending = str(direction).upper().endswith("DESCENDING")
            return document_value < cursor_value if descending else document_value > cursor_value
        return False


class FakeTransaction:
    def __init__(self, database):
        self.database = database
        self.operations = []
        self.writes_started = False

    def get(self, ref):
        if self.writes_started:
            raise AssertionError("Firestore transaction read attempted after write")
        self.database.read_log.append(ref.path)
        return FakeSnapshot(ref, self.database.documents.get(ref.path))

    def get_all(self, refs):
        # Firestore's batched read: one round trip, snapshots in any order.
        return [self.get(ref) for ref in reversed(list(refs))]

    def _stage(self, operation, ref, data):
        self.writes_started = True
        self.operations.append((operation, ref, dict(data)))
        fail_after = self.database.fail_transaction_after_staged_writes
        if fail_after is not None and len(self.operations) >= fail_after:
            raise RuntimeError("injected transaction failure")

    def set(self, ref, data, merge=False):
        self._stage("set_merge" if merge else "set", ref, data)

    def update(self, ref, data):
        self._stage("update", ref, data)

    def delete(self, ref):
        self._stage("delete", ref, {})

    def commit(self):
        paths = [ref.path for _operation, ref, _data in self.operations]
        documents_before = copy.deepcopy(self.database.documents)
        clock_before = self.database.clock
        write_log_length = len(self.database.write_log)
        try:
            for operation, ref, data in self.operations:
                if operation == "delete":
                    ref.delete()
                elif operation in {"set", "set_merge"}:
                    self.database.apply_set(ref, data, merge=operation == "set_merge")
                else:
                    self.database.apply_update(ref, data)
        except Exception:
            self.database.documents = documents_before
            self.database.clock = clock_before
            del self.database.write_log[write_log_length:]
            raise
        self.database.transaction_commits.append(paths)


def _merge_maps(current, incoming):
    merged = dict(current)
    for key, value in incoming.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge_maps(merged[key], value)
        else:
            merged[key] = value
    return merged


class FakeChatDatabase:
    def __init__(self):
        self.documents = {}
        # Emulates SERVER_TIMESTAMP, which is always ~now. A fixed date in the
        # past would make freshly written documents look stale to any age-based
        # logic (e.g. the abandoned-turn sweep).
        self.clock = datetime.now(timezone.utc).replace(microsecond=0)
        self.read_log = []
        # Paths whose WHOLE document left the database (get or unprojected
        # query); a select() projection is not logged here.
        self.full_document_log = []
        self.write_log = []
        self.transaction_commits = []
        self.fail_transaction_after_staged_writes = None

    def collection(self, name):
        return FakeCollectionRef(self, (name,))

    def get_all(self, refs):
        return [ref.get() for ref in refs]

    def run_transaction(self, operation):
        transaction = FakeTransaction(self)
        result = operation(transaction)
        transaction.commit()
        return result

    def apply_set(self, ref, data, merge=False):
        incoming = self.resolve_timestamps(data)
        if merge and ref.path in self.documents:
            # merge=True merges nested maps too, as Firestore does.
            self.documents[ref.path] = _merge_maps(self.documents[ref.path], incoming)
        else:
            self.documents[ref.path] = dict(incoming)
        self.write_log.append(("set", ref.path))

    def apply_update(self, ref, data):
        if ref.path not in self.documents:
            raise RuntimeError("missing document")
        self.documents[ref.path].update(self.resolve_timestamps(data))
        self.write_log.append(("update", ref.path))

    def resolve_timestamps(self, data):
        resolved = {}
        for key, value in data.items():
            if value.__class__.__name__ == "Sentinel":
                self.clock += timedelta(microseconds=1)
                resolved[key] = self.clock
            else:
                resolved[key] = value
        return resolved

    def chats(self, uid):
        prefix = ("users", uid, "chats")
        return {
            path[-1]: data
            for path, data in self.documents.items()
            if len(path) == 4 and path[:-1] == prefix
        }

    def turns(self, uid, chat_id):
        prefix = ("users", uid, "chats", chat_id, "turns")
        return {
            path[-1]: data
            for path, data in self.documents.items()
            if len(path) == 6 and path[:-1] == prefix
        }

    def model_answers(self, uid, chat_id, turn_id):
        prefix = ("users", uid, "chats", chat_id, "turns", turn_id, "model_answers")
        return {
            path[-1]: data
            for path, data in self.documents.items()
            if len(path) == 8 and path[:-1] == prefix
        }


@pytest.fixture
def chat_api(monkeypatch):
    database = FakeChatDatabase()
    limiter._storage.reset()
    api_uid_limiter.reset()
    monkeypatch.setenv("CHAT_CURSOR_SECRET", "test-chat-cursor-secret-32-bytes")
    monkeypatch.setattr(chat_history_router, "db_firestore", database)

    def verify(token):
        if token == "owner-token":
            return "owner-uid"
        if token == "other-token":
            return "other-uid"
        raise RuntimeError("invalid token")

    monkeypatch.setattr(chat_history_router, "verify_user_token", verify)
    app = FastAPI()
    app.state.limiter = limiter
    app.include_router(chat_history_router.router)
    app.add_middleware(CustomSecurityMiddleware)
    return TestClient(app), database


def create_chat(client, *, title=None, headers=AUTH_OWNER):
    body = {} if title is None else {"title": title}
    response = client.post("/chats", json=body, headers=headers)
    assert response.status_code == 201
    return response.json()["chat"]


UIDS = {AUTH_OWNER["Authorization"]: "owner-uid", AUTH_OTHER["Authorization"]: "other-uid"}


def create_turn(client, chat_id, payload=None, *, headers=AUTH_OWNER):
    """A Consensus turn as it is stored. Since 2026-10-25 no route creates one
    (the browser runs no Consensus chat); the store method stays the Agent's."""
    store = chat_store.ChatStore(chat_history_router.db_firestore)
    return store.create_turn(UIDS[headers["Authorization"]], chat_id, **(payload or TURN_PAYLOAD))


def complete_turn(store, uid, chat_id, turn_id, *, question, model_answers, consensus,
                  differences="", differences_data=None, sources=None, result_id=None):
    """Writes a completed Consensus turn in the shape the retired completion
    left (until 2026-10-25): one document per family, the result on the turn."""
    turn_ref = store._turn_ref(uid, chat_id, turn_id)
    included = []
    for name, item in model_answers.items():
        provider = chat_store.normalize_provider(name)
        answer = str(item.get("answer") or "").strip()
        if not answer:
            continue
        included.append(provider)
        turn_ref.collection("model_answers").document(chat_store.PROVIDER_DOCUMENT_IDS[provider]).set({
            "schema_version": chat_store.MODEL_ANSWER_SCHEMA_VERSION,
            "provider": provider,
            "model_label": str(item.get("model_label") or provider),
            "answer": answer,
            "sources": chat_store.sanitize_sources(item.get("sources")),
            "created_at": chat_store.firestore.SERVER_TIMESTAMP,
            "updated_at": chat_store.firestore.SERVER_TIMESTAMP,
        })
    included = [provider for provider in chat_store.PROVIDER_ORDER if provider in included]
    updates = {
        "status": "completed",
        "consensus": consensus,
        "differences": differences,
        "differences_data": chat_store.normalize_turn_differences_data(differences_data),
        "sources": chat_store.normalize_turn_sources(sources),
        "included_models": included,
        "answer_count": len(included),
        "completed_at": chat_store.firestore.SERVER_TIMESTAMP,
        "updated_at": chat_store.firestore.SERVER_TIMESTAMP,
    }
    score = ((updates["differences_data"] or {}).get("agreement") or {}).get("score")
    if isinstance(score, int) and not isinstance(score, bool) and 0 <= score <= 100:
        updates["agreement_score"] = score
    if result_id:
        updates["result_id"] = result_id
    turn_ref.update(updates)
    return store.get_turn(uid, chat_id, turn_id)


def completion_payload(question=TURN_PAYLOAD["question"], providers=PROVIDERS):
    return {
        "question": question,
        "model_answers": {
            provider: {
                "model_label": f"{provider} Model",
                "answer": f"Answer from {provider}",
                "sources": [{
                    "id": f"S{index}",
                    "title": f"Source {index}",
                    "url": f"https://example.test/{provider.lower()}",
                    "provider": provider,
                    "token": "must-not-survive",
                }],
                "api_key": "sk-must-not-survive",
                "raw_attachment": "must-not-survive",
            }
            for index, provider in enumerate(providers, 1)
        },
        "consensus": "Shared conclusion",
        "differences": "Small differences remain",
        "differences_data": {
            "claims": [{
                "anchor": "Shared conclusion",
                "agree": list(providers),
                "dissent": [],
                "secret": "must-not-survive",
            }],
            "differences": [],
            "models_compared": list(providers),
            "agreement": {"score": 83, "level": "high", "unknown": "drop"},
            "api_key": "sk-must-not-survive",
        },
        "sources": [
            {
                "id": "S1",
                "title": "Turn source",
                "url": "https://example.test/turn",
                "provider": "OpenAI",
                "credential": "must-not-survive",
            },
            {"id": "S2", "title": "Unsafe", "url": "javascript:alert(1)"},
        ],
        "result_id": "AbCdEf0123456789",
    }


def test_all_chat_endpoints_require_verified_authentication(chat_api):
    client, _database = chat_api
    requests = (
        client.post("/chats", json={}),
        client.get("/chats"),
        client.get("/chats/" + "a" * 32),
        client.put("/chats/" + "a" * 32 + "/turns/" + "b" * 32 + "/task-checks", json={"checked": [0]}),
        client.get("/chats", headers={"Authorization": "Bearer invalid"}),
    )
    assert all(response.status_code == 401 for response in requests)


def test_chat_creation_uses_server_id_and_storage_allowlist(chat_api):
    client, database = chat_api
    chat = create_chat(client, title="  Project   Alpha  ")

    assert re.fullmatch(r"[0-9a-f]{32}", chat["id"])
    assert chat["id"] not in {"Project Alpha", "project-alpha"}
    assert chat["title"] == "Project Alpha"
    assert chat["status"] == "active"
    assert chat["turn_count"] == 0
    assert chat["latest_question"] == ""
    assert set(database.chats("owner-uid")[chat["id"]]) == {
        "schema_version", "title", "status", "created_at", "updated_at",
        "turn_count", "latest_question", "execution_mode",
    }

    rejected = client.post(
        "/chats",
        json={"title": "Unsafe", "api_key": "sk-do-not-store", "owner_uid": "other"},
        headers=AUTH_OWNER,
    )
    assert rejected.status_code == 422
    assert len(database.chats("owner-uid")) == 1


def test_chat_detail_is_owner_scoped_and_list_is_compact(chat_api):
    client, _database = chat_api
    first = create_chat(client, title="First")
    second = create_chat(client, title="Second")

    owner_detail = client.get(f"/chats/{first['id']}", headers=AUTH_OWNER)
    foreign_detail = client.get(f"/chats/{first['id']}", headers=AUTH_OTHER)
    listed = client.get("/chats", headers=AUTH_OWNER)

    assert owner_detail.status_code == 200
    assert owner_detail.headers["cache-control"] == "private, no-store"
    assert owner_detail.json()["chat"]["schema_version"] == 1
    assert foreign_detail.status_code == 404
    assert [item["id"] for item in listed.json()["chats"]] == [second["id"], first["id"]]
    assert "schema_version" not in listed.json()["chats"][0]
    assert "turns" not in listed.json()["chats"][0]


def test_chat_list_enforces_limit_and_owner_bound_cursor(chat_api):
    client, _database = chat_api
    chats = [create_chat(client, title=f"Chat {index}") for index in range(3)]

    first_page = client.get("/chats?limit=2", headers=AUTH_OWNER)
    cursor = first_page.json()["next_cursor"]
    second_page = client.get(f"/chats?limit=2&cursor={cursor}", headers=AUTH_OWNER)
    foreign_cursor = client.get(f"/chats?limit=2&cursor={cursor}", headers=AUTH_OTHER)
    tampered = client.get(f"/chats?limit=2&cursor={cursor[:-1]}x", headers=AUTH_OWNER)
    over_limit = client.get("/chats?limit=51", headers=AUTH_OWNER)

    assert [item["id"] for item in first_page.json()["chats"]] == [
        chats[2]["id"], chats[1]["id"]
    ]
    assert [item["id"] for item in second_page.json()["chats"]] == [chats[0]["id"]]
    assert second_page.json()["has_more"] is False
    assert foreign_cursor.status_code == 400
    assert tampered.status_code == 400
    assert over_limit.status_code == 422


def test_chat_cursor_keeps_original_boundary_when_boundary_chat_moves(chat_api):
    client, _database = chat_api
    chats = [create_chat(client, title=f"Chat {index}") for index in range(4)]

    first_page = client.get("/chats?limit=2", headers=AUTH_OWNER)
    delivered_ids = [item["id"] for item in first_page.json()["chats"]]
    cursor = first_page.json()["next_cursor"]
    boundary_chat_id = delivered_ids[-1]

    create_turn(
        client,
        boundary_chat_id,
        {**TURN_PAYLOAD, "question": "Move the boundary chat to the top"},
    )
    second_page = client.get(f"/chats?limit=2&cursor={cursor}", headers=AUTH_OWNER)
    second_ids = [item["id"] for item in second_page.json()["chats"]]

    assert delivered_ids == [chats[3]["id"], chats[2]["id"]]
    assert second_ids == [chats[1]["id"], chats[0]["id"]]
    assert set(delivered_ids).isdisjoint(second_ids)


def test_chat_cursor_preserves_nanoseconds_and_rejects_invalid_timestamp(chat_api):
    _client, _database = chat_api
    timestamp = DatetimeWithNanoseconds.from_rfc3339(
        "2026-08-05T12:34:56.123456789Z"
    )
    document_id = "a" * 32
    cursor = chat_store._encode_chat_cursor(
        timestamp, document_id, owner_scope="owner-uid"
    )

    decoded_timestamp, decoded_id = chat_store._decode_chat_cursor(
        cursor, owner_scope="owner-uid"
    )
    invalid = chat_store._encode_cursor_payload(
        {"v": 2, "k": "chats", "updated_at": 123, "id": document_id},
        owner_scope="owner-uid",
    )
    out_of_range = chat_store._encode_cursor_payload(
        {
            "v": 2,
            "k": "chats",
            "updated_at": "0000-01-01T00:00:00.000000Z",
            "id": document_id,
        },
        owner_scope="owner-uid",
    )
    wrong_resource = chat_store._encode_cursor_payload(
        {"v": 2, "k": "turns", "position": 1, "id": document_id},
        owner_scope="owner-uid",
    )

    assert decoded_timestamp.rfc3339() == "2026-08-05T12:34:56.123456789Z"
    assert decoded_timestamp.nanosecond == 123456789
    assert copy.deepcopy(decoded_timestamp).nanosecond == 123456789
    assert decoded_id == document_id
    with pytest.raises(chat_store.InvalidChatCursor):
        chat_store._decode_chat_cursor(invalid, owner_scope="owner-uid")
    with pytest.raises(chat_store.InvalidChatCursor):
        chat_store._decode_chat_cursor(out_of_range, owner_scope="owner-uid")
    with pytest.raises(chat_store.InvalidChatCursor):
        chat_store._decode_chat_cursor(wrong_resource, owner_scope="owner-uid")


def test_chat_cursor_signing_secret_is_required_for_followup_page(chat_api, monkeypatch):
    client, _database = chat_api
    create_chat(client, title="First")
    create_chat(client, title="Second")
    monkeypatch.delenv("CHAT_CURSOR_SECRET", raising=False)
    monkeypatch.delenv("WATCH_UNSUBSCRIBE_SECRET", raising=False)

    response = client.get("/chats?limit=1", headers=AUTH_OWNER)

    assert response.status_code == 503


def test_first_and_second_turn_are_monotone_and_update_chat(chat_api):
    client, database = chat_api
    chat = create_chat(client)
    first = create_turn(
        client,
        chat["id"],
        {
            **TURN_PAYLOAD,
            "question": "  First question\nwith context?  ",
            "selected_models": [" OpenAI ", "OpenAI", " Gemini "],
        },
    )
    second = create_turn(
        client,
        chat["id"],
        {**TURN_PAYLOAD, "question": "Second question?", "deep_search": True},
    )

    stored_chat = database.chats("owner-uid")[chat["id"]]
    stored_turns = database.turns("owner-uid", chat["id"])
    assert first["position"] == 1
    assert second["position"] == 2
    assert first["status"] == second["status"] == "pending"
    assert first["selected_models"] == ["OpenAI", "Gemini"]
    assert stored_chat["turn_count"] == 2
    assert stored_chat["latest_question"] == "Second question?"
    assert stored_chat["title"] == "First question with context?"
    assert all(
        set(turn) <= {
            "schema_version", "position", "status", "question", "mode",
            "deep_search", "selected_models", "consensus_model", "created_at",
            "updated_at", "client_request_id", "execution_mode",
        }
        for turn in stored_turns.values()
    )


def test_turn_client_request_id_returns_original_for_normalized_identical_retry(chat_api):
    client, database = chat_api
    chat = create_chat(client)
    payload = {
        **TURN_PAYLOAD,
        "question": "  What changed?  ",
        "mode": " regular ",
        "selected_models": [" OpenAI ", "OpenAI", " Gemini "],
        "client_request_id": "request-123",
    }
    first = create_turn(client, chat["id"], payload)
    second = create_turn(client, chat["id"], {
        **TURN_PAYLOAD,
        "client_request_id": "request-123",
    })

    assert second == first
    assert first["client_request_id"] == "request-123"
    assert len(database.turns("owner-uid", chat["id"])) == 1
    assert database.chats("owner-uid")[chat["id"]]["turn_count"] == 1


def test_turn_client_request_id_rejects_changed_payload(chat_api):
    client, database = chat_api
    chat = create_chat(client)
    payload = {**TURN_PAYLOAD, "client_request_id": "request-123"}
    original = create_turn(client, chat["id"], payload)
    with pytest.raises(chat_store.ChatIdempotencyConflict):
        create_turn(client, chat["id"], {
            **payload,
            "question": "A changed question must not reuse the original turn",
        })

    assert database.turns("owner-uid", chat["id"])[original["id"]]["question"] == (
        TURN_PAYLOAD["question"]
    )
    assert len(database.turns("owner-uid", chat["id"])) == 1
    assert database.chats("owner-uid")[chat["id"]]["turn_count"] == 1


def test_latest_question_is_bounded_preview_but_turn_keeps_full_question(chat_api):
    client, database = chat_api
    chat = create_chat(client)
    question = ("  Café\n\tＡＩ   context " * 30) + "complete ending  "
    expected_full = unicodedata.normalize("NFKC", question).strip()
    expected_preview = " ".join(expected_full.split())[
        :chat_store.LATEST_QUESTION_PREVIEW_MAX_LENGTH
    ]
    turn = create_turn(
        client,
        chat["id"],
        {**TURN_PAYLOAD, "question": question},
    )
    detail = client.get(f"/chats/{chat['id']}", headers=AUTH_OWNER).json()["chat"]

    assert len(expected_preview) == chat_store.LATEST_QUESTION_PREVIEW_MAX_LENGTH
    assert turn["question"] == expected_full
    assert turn["question"].endswith("complete ending")
    assert len(turn["question"]) > chat_store.LATEST_QUESTION_PREVIEW_MAX_LENGTH
    assert detail["latest_question"] == expected_preview
    assert database.chats("owner-uid",)[chat["id"]]["latest_question"] == expected_preview


def test_turn_list_is_sorted_bounded_and_cursor_paginated(chat_api):
    client, _database = chat_api
    chat = create_chat(client)
    turns = [
        create_turn(client, chat["id"], {**TURN_PAYLOAD, "question": f"Question {index}"})
        for index in range(3)
    ]

    store = chat_store.ChatStore(_database)
    first_page = store.list_turns("owner-uid", chat["id"], limit=2)
    second_page = store.list_turns(
        "owner-uid", chat["id"], limit=2, cursor=first_page["next_cursor"]
    )

    assert [item["id"] for item in first_page["turns"]] == [
        turns[0]["id"], turns[1]["id"]
    ]
    assert [item["id"] for item in second_page["turns"]] == [turns[2]["id"]]
    assert second_page["has_more"] is False


def test_unknown_and_foreign_chat_are_indistinguishable_for_turn_creation(chat_api):
    client, _database = chat_api
    owned = create_chat(client)
    unknown_id = "f" * 32

    unknown = client.post(
        f"/chats/{unknown_id}/turns", json=TURN_PAYLOAD, headers=AUTH_OWNER
    )
    foreign = client.post(
        f"/chats/{owned['id']}/turns", json=TURN_PAYLOAD, headers=AUTH_OTHER
    )
    malformed = client.get("/chats/not-a-valid-id", headers=AUTH_OWNER)

    assert unknown.status_code == foreign.status_code == malformed.status_code == 404
    assert unknown.json() == foreign.json()


def test_fail_turn_is_allowlisted_idempotent_and_terminal(chat_api):
    client, database = chat_api
    chat = create_chat(client)
    failed = create_turn(client, chat["id"])
    completed = create_turn(
        client, chat["id"], {**TURN_PAYLOAD, "question": "Completed question"}
    )
    store = chat_store.ChatStore(database)

    first = store.fail_turn(
        "owner-uid", chat["id"], failed["id"], error_code="cancelled"
    )
    writes_after_first = len(database.write_log)
    second = store.fail_turn(
        "owner-uid", chat["id"], failed["id"], error_code="cancelled"
    )
    assert second == first
    assert len(database.write_log) == writes_after_first
    assert set(database.turns("owner-uid", chat["id"])[failed["id"]]) == {
        "schema_version", "position", "status", "question", "mode", "deep_search",
        "selected_models", "consensus_model", "created_at", "updated_at",
        "error_code", "failed_at", "execution_mode",
    }
    with pytest.raises(chat_store.TurnStatusConflict):
        store.fail_turn(
            "owner-uid", chat["id"], failed["id"],
            error_code="insufficient_answers",
        )
    with pytest.raises(ValueError, match="allowed code"):
        store.fail_turn(
            "owner-uid", chat["id"], failed["id"],
            error_code="provider stacktrace and sk-secret",
        )

    complete_turn(
        store,
        "owner-uid", chat["id"], completed["id"],
        **completion_payload(question="Completed question"),
    )
    with pytest.raises(chat_store.TurnStatusConflict):
        store.fail_turn(
            "owner-uid", chat["id"], completed["id"], error_code="cancelled"
        )


def test_turn_detail_is_owner_scoped_whitelisted_and_reads_six_known_docs(chat_api):
    client, database = chat_api
    chat = create_chat(client)
    turn = create_turn(client, chat["id"])
    complete_turn(
        chat_store.ChatStore(database),
        "owner-uid", chat["id"], turn["id"], **completion_payload()
    )
    store = chat_store.ChatStore(database)
    database.read_log.clear()

    returned = store.get_turn("owner-uid", chat["id"], turn["id"])

    assert set(returned["model_answers"]) == set(PROVIDERS)
    assert all("api_key" not in answer for answer in returned["model_answers"].values())
    for uid, turn_id in (("other-uid", turn["id"]), ("owner-uid", "f" * 32),
                         ("other-uid", "f" * 32), ("owner-uid", "not-a-valid-id")):
        with pytest.raises(chat_store.ChatNotFound):
            store.get_turn(uid, chat["id"], turn_id)
    answer_reads = [path for path in database.read_log if "model_answers" in path]
    assert len(answer_reads) == 6
    assert {path[-1] for path in answer_reads} == {
        chat_store.PROVIDER_DOCUMENT_IDS[provider] for provider in PROVIDERS
    }


def test_turn_list_stays_compact_after_completion_and_failure(chat_api):
    client, database = chat_api
    chat = create_chat(client)
    completed = create_turn(client, chat["id"])
    failed = create_turn(
        client, chat["id"], {**TURN_PAYLOAD, "question": "Failed question"}
    )
    store = chat_store.ChatStore(database)
    complete_turn(
        store,
        "owner-uid", chat["id"], completed["id"], **completion_payload()
    )
    store.fail_turn(
        "owner-uid", chat["id"], failed["id"], error_code="consensus_failed"
    )

    listed = store.list_turns("owner-uid", chat["id"])["turns"]
    completed_meta, failed_meta = listed
    assert completed_meta["answer_count"] == 6
    assert completed_meta["agreement_score"] == 83
    assert completed_meta["completed_at"]
    assert failed_meta["error_code"] == "consensus_failed"
    assert failed_meta["failed_at"]
    forbidden = {
        "consensus", "differences", "differences_data", "sources",
        "model_answers", "completion_fingerprint",
    }
    assert all(forbidden.isdisjoint(item) for item in listed)


# ---------------------------------------------------------------------------
# Question-Limit: ein Turn haelt hoechstens die Frage, die auch die
# Consensus-Pipeline annimmt (cfg.get_consensus_question_char_limit()).
# ---------------------------------------------------------------------------


def test_turn_question_limit_matches_the_consensus_cap():
    assert chat_store._question_max_length() == cfg.get_consensus_question_char_limit()


def test_turn_rejects_a_question_the_consensus_cap_would_truncate(chat_api):
    client, database = chat_api
    chat = create_chat(client)
    limit = cfg.get_consensus_question_char_limit()
    payload = {**TURN_PAYLOAD, "question": "q" * (limit + 1)}

    with pytest.raises(ValueError):
        create_turn(client, chat["id"], payload)

    assert database.turns("owner-uid", chat["id"]) == {}


def test_get_turn_reads_model_answers_with_one_query(chat_api):
    client, database = chat_api
    chat = create_chat(client)
    turn = create_turn(client, chat["id"])
    store = chat_store.ChatStore(database)
    complete_turn(
        store,
        "owner-uid", chat["id"], turn["id"], **completion_payload(providers=("OpenAI",))
    )
    database.read_log.clear()

    detail = store.get_turn("owner-uid", chat["id"], turn["id"])

    assert set(detail["model_answers"]) == {"OpenAI"}
    answer_reads = [
        path for path in database.read_log if "model_answers" in path
    ]
    # One collection read for the single stored answer — not one get per
    # provider in PROVIDER_ORDER.
    assert len(answer_reads) == 1


def test_model_answer_under_a_foreign_document_id_is_ignored(chat_api):
    client, database = chat_api
    chat = create_chat(client)
    turn = create_turn(client, chat["id"])
    store = chat_store.ChatStore(database)
    complete_turn(
        store,
        "owner-uid", chat["id"], turn["id"], **completion_payload(providers=("OpenAI",))
    )
    # Same payload, wrong document id: the provider must not be trusted over
    # the path it was stored under.
    smuggled = ("users", "owner-uid", "chats", chat["id"], "turns", turn["id"],
                "model_answers", "gemini")
    database.documents[smuggled] = {
        **database.model_answers("owner-uid", chat["id"], turn["id"])["openai"],
    }

    detail = store.get_turn("owner-uid", chat["id"], turn["id"])

    assert set(detail["model_answers"]) == {"OpenAI"}


def test_list_turn_details_checks_the_chat_once_for_the_whole_page(chat_api):
    client, database = chat_api
    chat = create_chat(client)
    store = chat_store.ChatStore(database)
    for index in range(3):
        turn = create_turn(
            client, chat["id"], {**TURN_PAYLOAD, "question": f"Question {index}"}
        )
        if index != 1:
            complete_turn(
        store,
                "owner-uid",
                chat["id"],
                turn["id"],
                **completion_payload(
                    question=f"Question {index}", providers=("OpenAI", "Gemini")
                ),
            )
    database.read_log.clear()

    page = store.list_turn_details("owner-uid", chat["id"], status="completed")

    assert [turn["question"] for turn in page["turns"]] == ["Question 0", "Question 2"]
    assert page["has_more"] is False
    assert all(turn["model_answers"] for turn in page["turns"])
    chat_reads = [path for path in database.read_log if len(path) == 4]
    assert len(chat_reads) == 1


def test_list_turn_details_batches_model_answers_instead_of_one_query_per_turn(chat_api, monkeypatch):
    # Audit C6: a chat page used to run one model_answers query per turn.
    client, database = chat_api
    chat = create_chat(client)
    store = chat_store.ChatStore(database)
    for index in range(4):
        turn = create_turn(
            client, chat["id"], {**TURN_PAYLOAD, "question": f"Question {index}"}
        )
        if index != 2:
            complete_turn(
        store,
                "owner-uid",
                chat["id"],
                turn["id"],
                **completion_payload(
                    question=f"Question {index}", providers=("OpenAI", "Gemini")
                ),
            )
    batches = []
    original_get_all = database.get_all
    monkeypatch.setattr(
        database, "get_all", lambda refs: batches.append(list(refs)) or original_get_all(refs)
    )
    queried = []
    original_stream = FakeCollectionRef.stream

    def recording_stream(self):
        queried.append(self.path)
        return original_stream(self)

    monkeypatch.setattr(FakeCollectionRef, "stream", recording_stream)

    page = store.list_turn_details("owner-uid", chat["id"])

    assert len(batches) == 1
    assert len(batches[0]) == 6  # 3 completed turns x 2 answers, the pending one costs nothing
    assert not [path for path in queried if path[-1] == "model_answers"]
    answers = {turn["question"]: set(turn["model_answers"]) for turn in page["turns"]}
    assert answers == {
        "Question 0": {"OpenAI", "Gemini"},
        "Question 1": {"OpenAI", "Gemini"},
        "Question 2": set(),
        "Question 3": {"OpenAI", "Gemini"},
    }


def test_list_turn_details_keeps_the_query_for_turns_without_included_models(chat_api):
    client, database = chat_api
    chat = create_chat(client)
    turn = create_turn(client, chat["id"])
    store = chat_store.ChatStore(database)
    complete_turn(
        store,
        "owner-uid", chat["id"], turn["id"], **completion_payload(providers=("OpenAI",))
    )
    turn_path = ("users", "owner-uid", "chats", chat["id"], "turns", turn["id"])
    database.documents[turn_path].pop("included_models")
    smuggled = (*turn_path, "model_answers", "gemini")
    database.documents[smuggled] = {
        **database.model_answers("owner-uid", chat["id"], turn["id"])["openai"],
    }

    page = store.list_turn_details("owner-uid", chat["id"])

    assert set(page["turns"][0]["model_answers"]) == {"OpenAI"}


def test_list_turn_details_keeps_pagination_identical_to_list_turns(chat_api):
    client, database = chat_api
    chat = create_chat(client)
    store = chat_store.ChatStore(database)
    for index in range(3):
        create_turn(client, chat["id"], {**TURN_PAYLOAD, "question": f"Question {index}"})

    metadata_page = store.list_turns("owner-uid", chat["id"], limit=2)
    detail_page = store.list_turn_details("owner-uid", chat["id"], limit=2)

    assert detail_page["has_more"] == metadata_page["has_more"] is True
    assert detail_page["next_cursor"] == metadata_page["next_cursor"]
    assert [turn["id"] for turn in detail_page["turns"]] == [
        turn["id"] for turn in metadata_page["turns"]
    ]


def test_list_turn_details_rejects_a_foreign_owner(chat_api):
    client, database = chat_api
    chat = create_chat(client)
    create_turn(client, chat["id"])

    with pytest.raises(chat_store.ChatNotFound):
        chat_store.ChatStore(database).list_turn_details("other-uid", chat["id"])


# ---------------------------------------------------------------------------
# DSGVO Art. 17: Firestore kaskadiert nicht. Chats, Turns, Modellantworten und
# Context-Versionen muessen bei der Kontoloeschung alle verschwinden.
# ---------------------------------------------------------------------------


def test_delete_all_chats_removes_every_nested_level(chat_api):
    client, database = chat_api
    store = chat_store.ChatStore(database)
    chat = create_chat(client)
    turn = create_turn(client, chat["id"])
    complete_turn(
        store,
        "owner-uid", chat["id"], turn["id"], **completion_payload()
    )
    version_path = (
        "users", "owner-uid", "chats", chat["id"], "context_versions", "d" * 32,
    )
    database.documents[version_path] = {"status": "ready", "memory": {}}
    assert database.model_answers("owner-uid", chat["id"], turn["id"])

    store.delete_all_chats("owner-uid")

    survivors = [
        path for path in database.documents
        if len(path) > 2 and path[:2] == ("users", "owner-uid") and "chats" in path
    ]
    assert survivors == []


def test_delete_all_chats_descends_into_missing_parent_documents(chat_api):
    _client, database = chat_api
    chat_id = "a" * 32
    turn_id = "b" * 32
    chat_path = ("users", "owner-uid", "chats", chat_id)
    turn_path = (*chat_path, "turns", turn_id)
    answer_path = (*turn_path, "model_answers", "openai")
    context_path = (*chat_path, "context_versions", "c" * 32)
    # A None parent models Firestore's missing document that remains visible
    # through list_documents() because it still owns subcollections.
    database.documents[chat_path] = None
    database.documents[turn_path] = {"status": "completed", "position": 1}
    database.documents[answer_path] = {"answer": "private answer"}
    database.documents[context_path] = {"memory": {"private": "context"}}

    chat_store.ChatStore(database).delete_all_chats("owner-uid")

    assert not any(path[: len(chat_path)] == chat_path for path in database.documents)


def test_delete_all_chats_leaves_other_owners_untouched(chat_api):
    client, database = chat_api
    store = chat_store.ChatStore(database)
    owner_chat = create_chat(client)
    create_turn(client, owner_chat["id"])
    other_chat = create_chat(client, headers=AUTH_OTHER)
    create_turn(client, other_chat["id"], headers=AUTH_OTHER)

    store.delete_all_chats("owner-uid")

    assert database.chats("owner-uid") == {}
    assert set(database.chats("other-uid")) == {other_chat["id"]}
    assert database.turns("other-uid", other_chat["id"])


def test_delete_all_chats_is_idempotent(chat_api):
    client, database = chat_api
    store = chat_store.ChatStore(database)
    chat = create_chat(client)
    turn = create_turn(client, chat["id"])
    complete_turn(store, "owner-uid", chat["id"], turn["id"], **completion_payload())

    store.delete_all_chats("owner-uid")
    store.delete_all_chats("owner-uid")

    assert database.chats("owner-uid") == {}


# ---------------------------------------------------------------------------
# Loeschpfad: ohne DELETE war ein Bookmark der einzige Griff an einem Chat —
# war es weg, blieb das Transcript unerreichbar liegen.
# ---------------------------------------------------------------------------


def test_delete_chat_removes_the_whole_tree(chat_api):
    client, database = chat_api
    chat = create_chat(client)
    turn = create_turn(client, chat["id"])
    complete_turn(
        chat_store.ChatStore(database),
        "owner-uid", chat["id"], turn["id"], **completion_payload()
    )
    version_path = (
        "users", "owner-uid", "chats", chat["id"], "context_versions", "d" * 32,
    )
    database.documents[version_path] = {"status": "ready"}

    response = client.delete(f"/chats/{chat['id']}", headers=AUTH_OWNER)

    assert response.status_code == 200
    assert database.chats("owner-uid") == {}
    assert database.turns("owner-uid", chat["id"]) == {}
    assert database.model_answers("owner-uid", chat["id"], turn["id"]) == {}
    assert version_path not in database.documents


def test_delete_chat_is_owner_scoped_and_uniformly_404(chat_api):
    client, database = chat_api
    chat = create_chat(client)

    foreign = client.delete(f"/chats/{chat['id']}", headers=AUTH_OTHER)
    unknown = client.delete(f"/chats/{'f' * 32}", headers=AUTH_OWNER)
    malformed = client.delete("/chats/not-a-chat-id", headers=AUTH_OWNER)

    assert foreign.status_code == unknown.status_code == malformed.status_code == 404
    # The foreign attempt must not have touched the owner's chat.
    assert set(database.chats("owner-uid")) == {chat["id"]}


def test_delete_chat_requires_authentication(chat_api):
    client, database = chat_api
    chat = create_chat(client)

    response = client.delete(f"/chats/{chat['id']}")

    assert response.status_code == 401
    assert set(database.chats("owner-uid")) == {chat["id"]}


def test_deleting_a_chat_twice_reports_404_and_changes_nothing(chat_api):
    client, database = chat_api
    chat = create_chat(client)
    create_turn(client, chat["id"])

    assert client.delete(f"/chats/{chat['id']}", headers=AUTH_OWNER).status_code == 200
    writes = len(database.write_log)
    assert client.delete(f"/chats/{chat['id']}", headers=AUTH_OWNER).status_code == 404
    assert len(database.write_log) == writes


def test_deleting_chat_state_rejects_a_late_turn_before_it_can_write(chat_api):
    client, database = chat_api
    chat = create_chat(client)
    chat_path = ("users", "owner-uid", "chats", chat["id"])
    database.documents[chat_path]["status"] = "deleting"
    before = dict(database.documents)

    response = client.post(
        f"/chats/{chat['id']}/turns",
        json=TURN_PAYLOAD,
        headers=AUTH_OWNER,
    )

    assert response.status_code == 404
    assert database.turns("owner-uid", chat["id"]) == {}
    assert database.documents == before


def test_deleting_chat_state_rejects_late_failure_writes(chat_api):
    client, database = chat_api
    chat = create_chat(client)
    turn = create_turn(client, chat["id"])
    chat_path = ("users", "owner-uid", "chats", chat["id"])
    database.documents[chat_path]["status"] = "deleting"
    before = copy.deepcopy(database.documents)
    store = chat_store.ChatStore(database)

    with pytest.raises(chat_store.ChatNotFound):
        store.fail_turn(
            "owner-uid",
            chat["id"],
            turn["id"],
            error_code="consensus_failed",
        )

    assert database.documents == before
    assert database.model_answers("owner-uid", chat["id"], turn["id"]) == {}


def test_account_deletion_tombstone_fences_late_turn_failure(chat_api):
    client, database = chat_api
    chat = create_chat(client)
    turn = create_turn(client, chat["id"])
    database.documents[("account_deletion_jobs", "owner-uid")] = {
        "status": "pending"
    }
    before = copy.deepcopy(database.documents)

    with pytest.raises(chat_store.persistence_guard.AccountDeletionInProgress):
        chat_store.ChatStore(database).fail_turn(
            "owner-uid", chat["id"], turn["id"], error_code="consensus_failed"
        )

    assert database.documents == before


def test_account_deletion_tombstone_fences_late_chat_and_turn_creation(chat_api):
    client, database = chat_api
    existing_chat = create_chat(client)
    database.documents[("account_deletion_jobs", "owner-uid")] = {
        "status": "pending"
    }
    before = copy.deepcopy(database.documents)
    store = chat_store.ChatStore(database)

    with pytest.raises(chat_store.persistence_guard.AccountDeletionInProgress):
        store.create_chat("owner-uid", title="must not survive")
    with pytest.raises(chat_store.persistence_guard.AccountDeletionInProgress):
        store.create_turn(
            "owner-uid",
            existing_chat["id"],
            **TURN_PAYLOAD,
        )

    assert database.documents == before
    assert database.turns("owner-uid", existing_chat["id"]) == {}


def test_account_deletion_fences_normal_chat_delete_but_cleanup_can_continue(chat_api):
    client, database = chat_api
    chat = create_chat(client)
    turn = create_turn(client, chat["id"])
    store = chat_store.ChatStore(database)
    database.documents[("account_deletion_jobs", "owner-uid")] = {
        "status": "pending"
    }
    before = copy.deepcopy(database.documents)

    with pytest.raises(chat_store.persistence_guard.AccountDeletionInProgress):
        store.delete_chat("owner-uid", chat["id"])

    assert database.documents == before
    assert database.turns("owner-uid", chat["id"])[turn["id"]]["status"] == "pending"

    store.delete_all_chats("owner-uid")

    assert database.chats("owner-uid") == {}
    assert database.turns("owner-uid", chat["id"]) == {}


# ---------------------------------------------------------------------------
# R11: Eine bestaetigte Chat-Loeschung ist ein dauerhafter, idempotenter Auftrag.
# Scheitert die Kaskade (auch zwischen zwei Batches) oder stirbt der Prozess,
# beendet der stuendliche Retention-Loop sie; der Zaehler sinkt genau einmal.
# ---------------------------------------------------------------------------


def _deletion_jobs(database):
    return {
        path[-1]: data
        for path, data in database.documents.items()
        if path[0] == chat_store.CHAT_DELETION_JOBS_COLLECTION
    }


def _chat_counter(database, uid="owner-uid"):
    return database.documents[("users", uid, "chat_state", "quota")]["active_count"]


def _completed_chat(client, database, turns=2):
    chat = create_chat(client)
    store = chat_store.ChatStore(database)
    turn_ids = []
    for index in range(turns):
        turn = create_turn(client, chat["id"], {**TURN_PAYLOAD, "question": f"Q{index}?"})
        complete_turn(
        store,
            "owner-uid", chat["id"], turn["id"],
            **completion_payload(question=f"Q{index}?"),
        )
        turn_ids.append(turn["id"])
    return chat, turn_ids


def _fail_deleting(monkeypatch, *, predicate):
    """Let one document delete fail once, like a crash between two batches."""
    original = FakeDocumentRef.delete
    state = {"armed": True}

    def delete(self):
        if state["armed"] and predicate(self.path):
            state["armed"] = False
            raise RuntimeError("simulated Firestore outage")
        return original(self)

    monkeypatch.setattr(FakeDocumentRef, "delete", delete)


def test_interrupted_chat_cascade_is_resumed_by_retention_and_counts_once(chat_api, monkeypatch):
    client, database = chat_api
    chat, turn_ids = _completed_chat(client, database)
    other = create_chat(client)
    store = chat_store.ChatStore(database)
    assert _chat_counter(database) == 2
    # Fail on the SECOND turn: the first turn is already gone, i.e. the
    # cascade stops between two batches.
    _fail_deleting(
        monkeypatch,
        predicate=lambda path: len(path) == 6 and path[3] == chat["id"] and path[5] == turn_ids[1],
    )

    assert store.delete_chat("owner-uid", chat["id"]) is False

    # The deletion is confirmed: invisible everywhere, counted once, queued.
    assert _chat_counter(database) == 1
    assert [item["id"] for item in store.list_chats("owner-uid")["chats"]] == [other["id"]]
    with pytest.raises(chat_store.ChatNotFound):
        store.get_chat("owner-uid", chat["id"])
    with pytest.raises(chat_store.ChatNotFound):
        store.list_turn_details("owner-uid", chat["id"])
    jobs = list(_deletion_jobs(database).values())
    assert len(jobs) == 1
    assert jobs[0]["uid"] == "owner-uid" and jobs[0]["chat_id"] == chat["id"]
    assert jobs[0]["status"] == "retrying" and jobs[0]["attempts"] == 1
    assert jobs[0]["last_error"] == "RuntimeError"
    assert turn_ids[1] in database.turns("owner-uid", chat["id"])

    # Not due yet: a tick right now leaves the backoff alone.
    assert chat_store.resume_chat_deletions(database) == 0
    later = datetime.now(timezone.utc) + timedelta(hours=7)
    assert chat_store.resume_chat_deletions(database, now=later) == 1

    assert not any(len(path) > 3 and path[3] == chat["id"] for path in database.documents)
    assert set(database.chats("owner-uid")) == {other["id"]}
    assert _deletion_jobs(database) == {}
    assert _chat_counter(database) == 1
    # Repeating the tick is a no-op.
    assert chat_store.resume_chat_deletions(database, now=later) == 0


def test_chat_deletion_survives_a_crash_right_after_the_tombstone(chat_api):
    client, database = chat_api
    chat, _ = _completed_chat(client, database, turns=1)
    store = chat_store.ChatStore(database)

    # The request dies after committing tombstone + job (and after removing
    # the bookmark), before any cascade batch ran.
    store.request_chat_deletion("owner-uid", chat["id"])
    store.request_chat_deletion("owner-uid", chat["id"])  # idempotent retry
    assert _chat_counter(database) == 0
    assert len(_deletion_jobs(database)) == 1

    assert chat_store.resume_chat_deletions(database) == 1
    assert database.chats("owner-uid") == {}
    assert _deletion_jobs(database) == {}
    assert _chat_counter(database) == 0


def test_queued_chat_deletion_cannot_be_revived_by_late_writes(chat_api, monkeypatch):
    client, database = chat_api
    chat, turn_ids = _completed_chat(client, database, turns=1)
    store = chat_store.ChatStore(database)
    _fail_deleting(
        monkeypatch,
        predicate=lambda path: len(path) == 6 and path[3] == chat["id"],
    )
    assert store.delete_chat("owner-uid", chat["id"]) is False
    before = copy.deepcopy(database.documents)

    with pytest.raises(chat_store.ChatNotFound):
        create_turn(client, chat["id"])
    with pytest.raises(chat_store.ChatNotFound):
        store.fail_turn("owner-uid", chat["id"], turn_ids[0], error_code="consensus_failed")
    assert database.documents == before


def test_adopts_a_chat_stranded_in_deleting_without_a_job(chat_api):
    client, database = chat_api
    chat, _ = _completed_chat(client, database, turns=1)
    chat_path = ("users", "owner-uid", "chats", chat["id"])
    # Legacy state from before durable jobs: tombstoned, counter already
    # decremented, cascade never finished.
    database.documents[chat_path]["status"] = "deleting"
    database.documents[("users", "owner-uid", "chat_state", "quota")]["active_count"] = 0

    assert client.delete(f"/chats/{chat['id']}", headers=AUTH_OWNER).status_code == 200

    assert database.chats("owner-uid") == {}
    assert _deletion_jobs(database) == {}
    assert _chat_counter(database) == 0


def test_account_deletion_removes_pending_chat_deletion_jobs(chat_api, monkeypatch):
    client, database = chat_api
    chat, _ = _completed_chat(client, database, turns=1)
    store = chat_store.ChatStore(database)
    store.request_chat_deletion("owner-uid", chat["id"])
    assert len(_deletion_jobs(database)) == 1

    store.delete_all_chats("owner-uid")

    assert database.chats("owner-uid") == {}
    assert _deletion_jobs(database) == {}


# ---------------------------------------------------------------------------
# Verwaiste pending Turns: ein Reload verliert die Browser-Bindung, danach kann
# kein Lauf den Turn je abschliessen.
# ---------------------------------------------------------------------------


def _age_turn(database, chat_id, turn_id, *, seconds):
    path = ("users", "owner-uid", "chats", chat_id, "turns", turn_id)
    database.documents[path]["created_at"] = (
        datetime.now(timezone.utc) - timedelta(seconds=seconds)
    )


def test_stale_pending_turn_is_retired_as_abandoned(chat_api):
    client, database = chat_api
    chat = create_chat(client)
    stale = create_turn(client, chat["id"])
    _age_turn(
        database,
        chat["id"],
        stale["id"],
        seconds=chat_store.ABANDONED_TURN_MAX_AGE_SECONDS + 60,
    )

    retired = chat_store.ChatStore(database).purge_abandoned_turns("owner-uid", chat["id"])

    assert retired == [stale["id"]]
    stored = database.turns("owner-uid", chat["id"])[stale["id"]]
    assert stored["status"] == "failed"
    assert stored["error_code"] == "abandoned"


def test_a_recent_pending_turn_is_never_retired(chat_api):
    client, database = chat_api
    chat = create_chat(client)
    fresh = create_turn(client, chat["id"])
    _age_turn(
        database,
        chat["id"],
        fresh["id"],
        seconds=chat_store.ABANDONED_TURN_MAX_AGE_SECONDS - 60,
    )

    retired = chat_store.ChatStore(database).purge_abandoned_turns("owner-uid", chat["id"])

    assert retired == []
    assert database.turns("owner-uid", chat["id"])[fresh["id"]]["status"] == "pending"


def test_sweep_never_touches_completed_or_failed_turns(chat_api):
    client, database = chat_api
    chat = create_chat(client)
    store = chat_store.ChatStore(database)
    done = create_turn(client, chat["id"], {**TURN_PAYLOAD, "question": "Done"})
    complete_turn(
        store,
        "owner-uid", chat["id"], done["id"], **completion_payload(question="Done")
    )
    broken = create_turn(client, chat["id"], {**TURN_PAYLOAD, "question": "Broken"})
    store.fail_turn("owner-uid", chat["id"], broken["id"], error_code="cancelled")
    for turn_id in (done["id"], broken["id"]):
        _age_turn(
            database,
            chat["id"],
            turn_id,
            seconds=chat_store.ABANDONED_TURN_MAX_AGE_SECONDS + 600,
        )

    assert store.purge_abandoned_turns("owner-uid", chat["id"]) == []
    stored = database.turns("owner-uid", chat["id"])
    assert stored[done["id"]]["status"] == "completed"
    assert stored[broken["id"]]["error_code"] == "cancelled"


def test_chat_count_is_capped_per_owner_and_scoped_to_that_owner(chat_api, monkeypatch):
    """Chats kosten keinen Usage-Slot - ohne Deckel waechst Firestore beliebig."""
    monkeypatch.setattr(chat_store, "MAX_CHATS_PER_OWNER", 3)
    client, database = chat_api

    for _ in range(3):
        create_chat(client)
    blocked = client.post("/chats", json={}, headers=AUTH_OWNER)
    assert blocked.status_code == 403
    assert blocked.json()["detail"]["error_code"] == "chat_limit_reached"
    assert len(database.chats("owner-uid")) == 3

    # Das Limit ist pro Konto, nicht global.
    other = client.post("/chats", json={}, headers=AUTH_OTHER)
    assert other.status_code == 201

    # Platz schaffen macht wieder Platz.
    victim = next(iter(database.chats("owner-uid")))
    assert client.delete(f"/chats/{victim}", headers=AUTH_OWNER).status_code == 200
    assert client.post("/chats", json={}, headers=AUTH_OWNER).status_code == 201


def test_chat_limit_first_frees_chats_no_bookmark_leads_to(chat_api, monkeypatch):
    """Lokaler Test 2026-10-11: POST /chats endete mit 403 chat_limit_reached.

    Der Browser legt den Chat vor dem ersten Turn an; wird die Nachricht dann
    abgelehnt, bekommt der Chat nie ein Bookmark. Solche Chats sieht und
    loescht niemand, sie belegten aber das Limit.
    """
    monkeypatch.setattr(chat_store, "MAX_CHATS_PER_OWNER", 3)
    client, database = chat_api
    visible = create_chat(client)
    unreachable = create_chat(client)
    starting = create_chat(client)
    database.documents[("users", "owner-uid", "bookmarks", "b_visible")] = {
        "chat_id": visible["id"], "timestamp": database.clock,
    }
    for chat in (visible, unreachable):
        database.documents[("users", "owner-uid", "chats", chat["id"])]["updated_at"] -= timedelta(hours=2)

    created = client.post("/chats", json={}, headers=AUTH_OWNER)

    assert created.status_code == 201
    chats = database.chats("owner-uid")
    assert chats[unreachable["id"]]["status"] == "deleting"
    assert chats[visible["id"]]["status"] == "active"
    # Young enough to still get its first answer and bookmark.
    assert chats[starting["id"]]["status"] == "active"
    assert database.documents[("users", "owner-uid", "chat_state", "quota")]["active_count"] == 3
    # The regular durable deletion finishes the cascade.
    assert any(path[0] == chat_store.CHAT_DELETION_JOBS_COLLECTION for path in database.documents)

    # Nothing left to free: the limit holds.
    blocked = client.post("/chats", json={}, headers=AUTH_OWNER)
    assert blocked.status_code == 403
    assert blocked.json()["detail"]["error_code"] == "chat_limit_reached"


def test_a_failing_reclaim_keeps_the_chat_limit_answer(chat_api, monkeypatch):
    monkeypatch.setattr(chat_store, "MAX_CHATS_PER_OWNER", 1)
    client, _database = chat_api
    create_chat(client)

    def unavailable(self, uid, *, now=None):
        raise RuntimeError("bookmark scan unavailable")

    monkeypatch.setattr(chat_store.ChatStore, "reclaim_unreachable_chats", unavailable)
    blocked = client.post("/chats", json={}, headers=AUTH_OWNER)

    assert blocked.status_code == 403
    assert blocked.json()["detail"]["error_code"] == "chat_limit_reached"


def test_chat_count_falls_back_to_a_bounded_scan_without_aggregation(
    chat_api, monkeypatch
):
    """Ohne count()-Aggregation greift der begrenzte Scan - und zaehlt gleich."""
    monkeypatch.setattr(chat_store, "MAX_CHATS_PER_OWNER", 2)
    monkeypatch.delattr(FakeCollectionRef, "count")
    client, database = chat_api

    create_chat(client)
    create_chat(client)
    blocked = client.post("/chats", json={}, headers=AUTH_OWNER)

    assert blocked.status_code == 403
    assert blocked.json()["detail"]["error_code"] == "chat_limit_reached"
    assert len(database.chats("owner-uid")) == 2


def test_turns_per_chat_are_capped_without_corrupting_the_counter(
    chat_api, monkeypatch
):
    monkeypatch.setattr(chat_store, "MAX_TURNS_PER_CHAT", 2)
    client, database = chat_api
    chat = create_chat(client)

    create_turn(client, chat["id"], {**TURN_PAYLOAD, "question": "One"})
    create_turn(client, chat["id"], {**TURN_PAYLOAD, "question": "Two"})
    with pytest.raises(chat_store.ChatQuotaExceeded) as blocked:
        create_turn(client, chat["id"], {**TURN_PAYLOAD, "question": "Three"})

    assert blocked.value.error_code == "turn_limit_reached"
    # Die abgelehnte Anlage darf weder einen Turn noch einen Zaehlerstand
    # hinterlassen - sonst waere der Chat danach dauerhaft inkonsistent.
    assert len(database.turns("owner-uid", chat["id"])) == 2
    assert database.chats("owner-uid")[chat["id"]]["turn_count"] == 2


def test_write_endpoints_are_rate_limited_per_account_not_only_per_ip(
    chat_api, monkeypatch
):
    """Das IP-Limit ist hier die falsche Achse (IPv6 umgeht es, NAT teilt es).

    Der UID-Limiter sitzt hinter der Token-Pruefung, also trifft er genau das
    Konto, das die Schreibzugriffe ausloest - und nur dieses.
    """
    monkeypatch.setitem(chat_history_router.CHAT_UID_RATE_LIMITS, "create_chat", 3)
    client, _database = chat_api

    for _ in range(3):
        assert client.post("/chats", json={}, headers=AUTH_OWNER).status_code == 201
    throttled = client.post("/chats", json={}, headers=AUTH_OWNER)
    assert throttled.status_code == 429
    assert throttled.json()["detail"]["error_code"] == "chat_rate_limited"

    # Ein anderes Konto von derselben IP bleibt unberuehrt.
    assert client.post("/chats", json={}, headers=AUTH_OTHER).status_code == 201

    # Lesende Endpoints haengen nicht am Schreib-Budget.
    assert client.get("/chats", headers=AUTH_OWNER).status_code == 200


def test_creating_a_turn_retires_an_abandoned_predecessor(chat_api):
    client, database = chat_api
    chat = create_chat(client)
    abandoned = create_turn(client, chat["id"], {**TURN_PAYLOAD, "question": "Lost"})
    _age_turn(
        database,
        chat["id"],
        abandoned["id"],
        seconds=chat_store.ABANDONED_TURN_MAX_AGE_SECONDS + 60,
    )

    fresh = create_turn(client, chat["id"], {**TURN_PAYLOAD, "question": "Next"})

    stored = database.turns("owner-uid", chat["id"])
    assert stored[abandoned["id"]]["error_code"] == "abandoned"
    assert stored[fresh["id"]]["status"] == "pending"


def test_a_failing_sweep_never_blocks_turn_creation(chat_api, monkeypatch):
    client, database = chat_api
    chat = create_chat(client)

    def explode(self, uid, chat_id, *, now=None):
        raise RuntimeError("firestore unavailable")

    monkeypatch.setattr(chat_store.ChatStore, "purge_abandoned_turns", explode)
    turn = create_turn(client, chat["id"])

    assert database.turns("owner-uid", chat["id"])[turn["id"]]["status"] == "pending"


def test_turn_keeps_the_attachment_meta_of_its_own_question(chat_api):
    """Ein Anhang gehoert zu der Frage, mit der er rausgegangen ist.

    Vorher hing er am Bookmark-Dokument, das nur EINE Fassung kennt: die
    naechste Frage ohne Datei ueberschrieb sie und der Anhang war aus dem
    gespeicherten Chat verschwunden. Am Turn ueberlebt er jede Folgefrage.
    """
    client, database = chat_api
    chat = create_chat(client)

    with_file = create_turn(
        client,
        chat["id"],
        {
            **TURN_PAYLOAD,
            "question": "What does this chart show?",
            "attachments": [
                # Der Browser meldet .csv je nach System unterschiedlich; der
                # Server kennt nur den kanonischen Typ.
                {"name": "chart.png", "mime": "image/png", "size": 2048},
                {"name": "rows.csv", "mime": "text/csv", "size": 900},
            ],
        },
    )
    without_file = create_turn(
        client, chat["id"], {**TURN_PAYLOAD, "question": "And in euros?"}
    )

    assert with_file["attachments"] == [
        {"name": "chart.png", "mime": "image/png", "size": 2048},
        {"name": "rows.csv", "mime": "text/plain", "size": 900},
    ]
    # Die Folgefrage sagt nichts ueber die Datei der vorigen aus - und raeumt
    # sie auch nicht weg.
    assert "attachments" not in without_file
    stored = database.turns("owner-uid", chat["id"])
    assert stored[with_file["id"]]["attachments"][0]["name"] == "chart.png"
    assert "attachments" not in stored[without_file["id"]]

    page = chat_store.ChatStore(database).list_turns("owner-uid", chat["id"])
    listed = {turn["id"]: turn for turn in page["turns"]}
    assert listed[with_file["id"]]["attachments"][1]["mime"] == "text/plain"


def test_turn_attachments_never_carry_file_data_or_unknown_types(chat_api):
    """Datei-Bytes gehoeren an die Modelle, nicht nach Firestore."""
    client, database = chat_api
    chat = create_chat(client)

    turn = create_turn(
        client,
        chat["id"],
        {
            **TURN_PAYLOAD,
            "attachments": [
                {
                    "name": "secret.png",
                    "mime": "image/png",
                    "size": 10,
                    "data": "must-not-survive",
                },
                {"name": "payload.exe", "mime": "application/x-msdownload", "size": 5},
                {"name": "", "mime": "image/png", "size": 5},
            ],
        },
    )

    assert turn["attachments"] == [
        {"name": "secret.png", "mime": "image/png", "size": 10}
    ]
    stored = database.turns("owner-uid", chat["id"])[turn["id"]]
    assert "must-not-survive" not in repr(stored)


def test_turn_attachment_meta_survives_completion(chat_api):
    """Die Antwort ueberschreibt die Frage nicht.

    Die Antwort steht in demselben Dokument wie die Frage und ihr Anhang;
    gelesen wird beides zusammen.
    """
    client, database = chat_api
    chat = create_chat(client)
    turn = create_turn(
        client,
        chat["id"],
        {
            **TURN_PAYLOAD,
            "attachments": [{"name": "chart.png", "mime": "image/png", "size": 2048}],
        },
    )
    complete_turn(
        chat_store.ChatStore(database),
        "owner-uid", chat["id"], turn["id"], **completion_payload()
    )

    detail = chat_store.ChatStore(database).get_turn("owner-uid", chat["id"], turn["id"])
    assert detail["attachments"] == [
        {"name": "chart.png", "mime": "image/png", "size": 2048}
    ]


def test_task_checks_are_kept_on_a_completed_turn_and_read_back(chat_api):
    client, database = chat_api
    chat = create_chat(client)
    turn = create_turn(client, chat["id"])
    url = f"/chats/{chat['id']}/turns/{turn['id']}/task-checks"

    # Only an answer that exists can have its boxes ticked.
    pending = client.put(url, json={"checked": [0]}, headers=AUTH_OWNER)
    assert pending.status_code == 409

    complete_turn(
        chat_store.ChatStore(database),
        "owner-uid", chat["id"], turn["id"], **completion_payload()
    )
    chat_before = dict(database.chats("owner-uid")[chat["id"]])
    updated_before = database.turns("owner-uid", chat["id"])[turn["id"]]["updated_at"]

    saved = client.put(url, json={"checked": [3, 0, 3]}, headers=AUTH_OWNER)
    assert saved.status_code == 200
    assert saved.json() == {"status": "success", "checked": [0, 3]}
    stored = database.turns("owner-uid", chat["id"])[turn["id"]]
    assert stored["task_checks"] == [0, 3]
    # Ticking reorders nothing: neither the chat nor the turn moves.
    assert stored["updated_at"] == updated_before
    assert database.chats("owner-uid")[chat["id"]] == chat_before

    detail = chat_store.ChatStore(database).get_turn("owner-uid", chat["id"], turn["id"])
    assert detail["task_checks"] == [0, 3]
    page = chat_store.ChatStore(database).list_turn_details("owner-uid", chat["id"])
    assert page["turns"][0]["task_checks"] == [0, 3]

    cleared = client.put(url, json={"checked": []}, headers=AUTH_OWNER)
    assert cleared.json()["checked"] == []
    assert database.turns("owner-uid", chat["id"])[turn["id"]]["task_checks"] == []


@pytest.mark.parametrize("body", [
    {"checked": [-1]},
    {"checked": [200]},
    {"checked": ["1"]},
    {"checked": [True]},
    {"checked": [1.5]},
    {"checked": list(range(201))},
    {"checked": 1},
    {"checked": [0], "extra": "nope"},
    {},
])
def test_task_checks_reject_anything_but_item_positions(chat_api, body):
    client, database = chat_api
    chat = create_chat(client)
    turn = create_turn(client, chat["id"])
    complete_turn(
        chat_store.ChatStore(database),
        "owner-uid", chat["id"], turn["id"], **completion_payload()
    )
    response = client.put(
        f"/chats/{chat['id']}/turns/{turn['id']}/task-checks", json=body, headers=AUTH_OWNER
    )
    assert response.status_code == 422
    assert "task_checks" not in database.turns("owner-uid", chat["id"])[turn["id"]]


def test_task_checks_of_a_foreign_or_unknown_turn_are_404(chat_api):
    client, database = chat_api
    chat = create_chat(client)
    turn = create_turn(client, chat["id"])
    complete_turn(
        chat_store.ChatStore(database),
        "owner-uid", chat["id"], turn["id"], **completion_payload()
    )
    body = {"checked": [1]}
    foreign = client.put(f"/chats/{chat['id']}/turns/{turn['id']}/task-checks", json=body, headers=AUTH_OTHER)
    unknown = client.put(f"/chats/{chat['id']}/turns/{'f' * 32}/task-checks", json=body, headers=AUTH_OWNER)
    other_chat = create_chat(client)
    wrong_chat = client.put(f"/chats/{other_chat['id']}/turns/{turn['id']}/task-checks", json=body, headers=AUTH_OWNER)
    assert foreign.status_code == unknown.status_code == wrong_chat.status_code == 404
    assert "task_checks" not in database.turns("owner-uid", chat["id"])[turn["id"]]


def test_turn_detail_drops_malformed_stored_task_checks():
    detail = chat_store.turn_detail("a" * 32, {"status": "completed", "task_checks": ["x"]}, {})
    assert "task_checks" not in detail
    assert chat_store.turn_detail("a" * 32, {"task_checks": [2, 1]}, {})["task_checks"] == [1, 2]


def test_turn_detail_names_how_long_an_agent_turn_waited_for_the_user():
    """Its pauses stay on the document (agent_holds); the browser gets their
    sum, which "Thought for …" leaves out (UX audit 2026-10-29 E1)."""
    turn = {"execution_mode": "agent", "assistant_response": "A", "status": "completed",
            "agent_holds": [{"kind": "harm", "decision": "continue", "seconds": 61.25},
                            {"kind": "injection", "decision": "timeout", "seconds": 1800}, {"seconds": "x"}, "y"]}
    detail = chat_store.turn_detail("a" * 32, turn, {})
    assert detail["agent_wait_seconds"] == 1861.2 and "agent_holds" not in detail
    assert "agent_wait_seconds" not in chat_store.turn_detail("a" * 32, {**turn, "agent_holds": []}, {})


def test_a_transaction_aborted_while_reading_starts_again(monkeypatch):
    # The SDK repeats a transaction only when its commit is aborted; under
    # contention Firestore may already abort a read (CI 2026-10-24).
    from google.api_core.exceptions import Aborted

    transactions, reads = [], []

    class TransactionOnlyDatabase:
        def transaction(self, **kwargs):
            transactions.append(kwargs)
            return object()

    def read(tx):
        reads.append(tx)
        if len(reads) < 3:
            raise Aborted("Transaction lock timeout.")
        return "done"

    monkeypatch.setattr(chat_store.firestore, "transactional", lambda operation: operation)
    monkeypatch.setattr(chat_store.time, "sleep", lambda seconds: None)
    store = chat_store.ChatStore(TransactionOnlyDatabase())
    assert store._transaction(read) == "done"
    # Each new start is a fresh transaction with the commit retry budget.
    assert transactions == [{"max_attempts": 12}] * 3
    assert len(set(map(id, reads))) == 3

    # A lasting conflict still ends as the error, after a bounded number of starts.
    attempts = []

    def always_aborted(tx):
        attempts.append(tx)
        raise Aborted("Transaction lock timeout.")

    with pytest.raises(Aborted):
        store._transaction(always_aborted)
    assert len(attempts) == chat_store.TRANSACTION_READ_ATTEMPTS

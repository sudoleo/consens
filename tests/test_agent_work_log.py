"""The agent's work log (agent_work_log.py, docs/agent-work-log.md): written
live by the app in audit mode, what the agent sees and does, never the
reviewers; saved in order, long content in the object store; deleted with
the chat and after its retention."""
from datetime import datetime, timedelta, timezone
import json
import time

from firebase_admin import firestore
import pytest

from app.services import agent_work_log
from app.services.agent_work_log import INLINE_CHARS, PREVIEW_CHARS, WorkLog, context_data
from app.services.agent_tools import ReadOnlyTool, ToolRegistry
from app.services.llm.agent_client import AgentCompletion
from test_agent_audit import ANSWER, Audit, _admin_allowance, audit_loop, saved  # noqa: F401  (fixture)
from test_agent_runs import AUTH, UID, Database, api, pending, store  # noqa: F401  (fixtures)
from test_chat_history import FakeDocumentRef, FakeSnapshot


class LogStore:
    """Records what the writer saves; the first ``fail`` writes with entries fail."""

    def __init__(self, fail=0, delay=0):
        self.batches, self.flags, self.fail, self.delay = [], [], fail, delay

    def save_work_log(self, uid, chat_id, turn_id, entries, *, expires_at, incomplete=False):
        if self.delay:
            time.sleep(self.delay)
        if entries and self.fail:
            self.fail -= 1
            raise RuntimeError("database briefly unavailable")
        if entries:
            self.batches.append(entries)
        if incomplete:
            self.flags.append(True)

    @property
    def entries(self):
        return [entry for batch in self.batches for entry in batch]


class Objects:
    def __init__(self):
        self.items, self.deleted = {}, []

    def put(self, key, raw, mime):
        if key in self.items:
            raise FileExistsError(key)
        self.items[key] = raw

    def get(self, key):
        return self.items[key]

    def delete(self, key):
        self.deleted.append(key)
        self.items.pop(key, None)


def work_log(store=None, **kwargs):
    return WorkLog(store or LogStore(), "u", "c", "t", sleep=lambda seconds: None, **kwargs)


def summary(entries):
    return [(e["seq"], e["kind"], e["name"], e["data"], e["content"]) for e in entries]


# --- What goes in ---------------------------------------------------------------

def test_the_context_is_logged_by_position_with_the_history_and_without_the_models_own_turn():
    store = LogStore()
    log = work_log(store)
    # System prompt, an earlier question and answer, this message's question.
    conversation = [{"role": "system", "content": "Rules."}, {"role": "user", "content": "Paris?"},
                    {"role": "assistant", "content": "Go in spring."}, {"role": "user", "content": "Tower?"}]
    log.context("agent", conversation, conversation, step="completion:0", own_from=4)
    hint = {"role": "user", "content": "App rule: your reply above is not sent."}
    conversation += [{"role": "assistant", "content": "Thinking aloud."},
                     {"role": "tool", "tool_call_id": "1", "content": '{"refused": true}'}, hint, dict(hint),
                     {"role": "user", "content": "Worker messages (untrusted task data):\n[]"}]
    log.context("agent", conversation, conversation, step="completion:1", own_from=4)
    log.close()
    assert summary(store.entries) == [
        (1, "context", "system", "app", "Rules."), (2, "context", "user", "user", "Paris?"),
        (3, "context", "assistant", "agent", "Go in spring."), (4, "context", "user", "user", "Tower?"),
        (5, "context", "tool", "app", '{"refused": true}'),
        # The same hint twice is two hints.
        (6, "context", "user", "app", "App rule: your reply above is not sent."),
        (7, "context", "user", "app", "App rule: your reply above is not sent."),
        (8, "context", "user", "agent", "Worker messages (untrusted task data):\n[]")]
    assert all(e["step"] for e in store.entries) and all(e["at"] for e in store.entries)


def test_what_only_a_request_adds_is_logged_once_and_a_files_bytes_never():
    store = LogStore()
    log = work_log(store)
    conversation = [{"role": "system", "content": "Rules."}, {"role": "user", "content": "What is in it?"}]
    block = {"role": "user", "content": [{"type": "text", "text": "File evidence (untrusted): {}"},
                                         {"type": "image_url", "image_url": {"url": "data:image/png;base64,AAAA"}}]}
    for step in range(2):
        # A new copy of the same block in every step, as the file context builds it.
        log.context("agent", conversation, [*conversation, dict(block)], step=f"completion:{step}", own_from=2)
    log.close()
    assert summary(store.entries)[2:] == [
        (3, "context", "user", "file", "File evidence (untrusted): {}\n\n[image]")]


def test_a_workers_assignment_and_messages_are_the_agents_words():
    assert context_data("worker:w1", 1, 0, {"role": "user"}, '{"goal": "Check"}') == "agent"
    assert context_data("worker:w1", 0, 0, {"role": "system"}, "You are a worker.") == "app"
    assert context_data("agent", 3, 5, {"role": "user"}, "Question?") == "user"
    assert context_data("agent", 6, 5, {"role": "user"}, "App note, not from the user: …") == "app"


def test_a_tool_result_is_logged_when_it_returns_with_where_it_came_from():
    store = LogStore()
    log = work_log(store)
    message = {"role": "tool", "tool_call_id": "c1", "content": '{"text": "Page text."}'}
    log.tool("agent", "completion:0", {"id": "c1", "function": {"name": "read_source"}}, message)
    # The next step carries the same result: it is in the log already.
    log.context("agent", [message], [message], step="completion:1")
    log.close()
    [entry] = store.entries
    assert (entry["kind"], entry["name"], entry["data"], entry["content"]) == (
        "tool", "read_source", "web", '{"text": "Page text."}')


def test_a_step_keeps_its_readable_reasoning_text_calls_and_hits_but_never_encrypted_reasoning():
    store = LogStore()
    log = work_log(store)
    value = AgentCompletion()
    value._reasoning_parts = [{"type": "reasoning.summary", "summary": "Check the height."},
                              {"type": "reasoning.encrypted", "data": "c2VjcmV0"},
                              {"type": "reasoning.text", "text": "330 m it is."}]
    value.text, value.finish_reason = "The tower is 330 m tall.", "stop"
    value.tool_calls = [{"id": "c1", "type": "function", "function": {"name": "update_memory", "arguments": "{}"}}]
    value.sources = [{"url": "https://example.org/tower", "title": "Tower"}]
    value.citations = [{"url": "https://example.org/tower", "content": "It is 330 metres tall."}]
    model = type("Model", (), {"model": "anthropic/claude"})()
    log.step("agent", "completion:0", model, value, "succeeded")
    log.close()
    [entry] = store.entries
    body = json.loads(entry["content"])
    assert (entry["kind"], entry["data"], entry["name"], entry["format"]) == ("step", "agent", "anthropic/claude", "json")
    assert body["reasoning"] == "Check the height.\n\n330 m it is." and "c2VjcmV0" not in entry["content"]
    assert body["text"] == "The tower is 330 m tall." and body["status"] == "succeeded"
    assert body["tool_calls"] == [{"id": "c1", "name": "update_memory", "arguments": "{}"}]
    assert body["search_excerpts"] == [{"url": "https://example.org/tower", "content": "It is 330 metres tall."}]


def test_long_content_goes_to_the_object_store_and_the_entry_keeps_its_beginning():
    store, objects = LogStore(), Objects()
    log = work_log(store, objects=objects)
    log.add("tool", actor="agent", name="read_source", data="web", content="x" * (INLINE_CHARS + 10))
    log.close()
    [entry] = store.entries
    assert entry["ref"] == "work-log/u/c/t/000001" and len(entry["content"]) == PREVIEW_CHARS
    assert entry["chars"] == INLINE_CHARS + 10
    assert agent_work_log.entry_content(entry, objects) == "x" * (INLINE_CHARS + 10)


def test_without_an_object_store_long_content_is_kept_shortened(monkeypatch):
    monkeypatch.setattr(agent_work_log, "_objects", lambda: None)
    store = LogStore()
    log = work_log(store)
    log.add("tool", content="y" * (INLINE_CHARS + 5))
    log.close()
    [entry] = store.entries
    assert entry["truncated"] is True and len(entry["content"]) == INLINE_CHARS and "ref" not in entry


def test_nothing_is_written_before_the_run_owns_the_turn():
    store = LogStore()
    log = work_log(store, ready=lambda: False)
    log.add("start", content={"question": "?"})
    log.close(timeout=2)
    assert store.batches == [] and store.flags == []


def test_entries_that_cannot_be_saved_mark_the_log_incomplete_and_leave_no_content_behind():
    store, objects = LogStore(fail=3), Objects()
    log = work_log(store, objects=objects)
    log.add("tool", content="z" * (INLINE_CHARS + 1))
    log.close()
    assert store.batches == [] and store.flags == [True] and log.incomplete
    assert objects.items == {} and objects.deleted == ["work-log/u/c/t/000001"]


def test_the_runs_end_waits_for_the_log_at_most_its_limit():
    store = LogStore(delay=1)
    log = work_log(store)
    log.add("start", content={})
    started = time.monotonic()
    log.close(timeout=.2)
    assert time.monotonic() - started < .6


# --- In a turn --------------------------------------------------------------------

def test_an_audit_turn_logs_what_the_agent_sees_and_does_but_not_its_reviewers(store, monkeypatch, tmp_path):
    monkeypatch.setenv("AGENT_FILES_LOCAL_DIR", str(tmp_path))
    # Small limits: the system prompt goes to the (local) object store.
    monkeypatch.setattr(agent_work_log, "INLINE_CHARS", 2000)
    monkeypatch.setattr(agent_work_log, "PREVIEW_CHARS", 100)
    script = Audit()
    loop = audit_loop(store, script)
    list(loop.run())
    data = store.read_work_log(UID, loop.chat_id, loop.turn_id, limit=200)
    entries = data["entries"]
    assert [e["seq"] for e in entries] == list(range(1, len(entries) + 1)) and not data["incomplete"]
    assert (entries[0]["kind"], entries[-1]["kind"]) == ("start", "end")
    assert json.loads(entries[0]["content"])["question"] == "Tell me about the Eiffel Tower."
    context = [e for e in entries if e["kind"] == "context"]
    assert [(e["name"], e["data"]) for e in context] == [("system", "app"), ("user", "user")]
    # The system prompt is long: in the object store, whole.
    system = store.work_log_entry(UID, loop.chat_id, loop.turn_id, context[0]["seq"])
    assert len(loop.messages[0]["content"]) > 2000
    assert context[0]["ref"] and len(context[0]["content"]) == 100 and system["content"] == loop.messages[0]["content"]
    [step] = [e for e in entries if e["kind"] == "step"]
    body = json.loads(step["content"])
    assert (step["actor"], step["step"], body["status"], body["text"]) == ("agent", "completion:0", "succeeded", ANSWER)
    assert body["sources"] == [{"url": "https://www.toureiffel.paris/en", "title": "Official site"}]
    apps = [e["name"] for e in entries if e["kind"] == "app"]
    assert apps == ["memory_locked", "answer_fixed"]
    # The reviewers (both comparison models) are not the agent's work.
    assert {e["actor"] for e in entries} == {"agent", "app"}
    end = json.loads(entries[-1]["content"])
    assert end["status"] == "succeeded" and end["answer"] == ANSWER
    # The page learns that the turn has a log; the expiry stays on the server.
    assert saved(store, loop)["agent_work_log"] == {"incomplete": False}
    raw = store._turn_ref(UID, loop.chat_id, loop.turn_id).get().to_dict()
    expires = datetime.fromisoformat(raw["work_log_expires_at"])
    assert timedelta(days=29) < expires - datetime.now(timezone.utc) <= timedelta(days=30)
    assert "work_log_incomplete" not in raw


def test_the_log_holds_the_chats_history_as_the_agent_received_it(store):
    loop = audit_loop(store, Audit(), messages=[
        {"role": "system", "content": "Answer."}, {"role": "user", "content": "Paris trip?"},
        {"role": "assistant", "content": "Yes, go in spring."}, {"role": "user", "content": "And the tower?"}])
    list(loop.run())
    entries = store.read_work_log(UID, loop.chat_id, loop.turn_id, limit=200)["entries"]
    assert [(e["name"], e["data"], e["content"]) for e in entries if e["kind"] == "context"][1:] == [
        ("user", "user", "Paris trip?"), ("assistant", "agent", "Yes, go in spring."), ("user", "user", "And the tower?")]


def test_without_audit_mode_no_log_is_kept(store):
    loop = audit_loop(store, Audit(), audit="off")
    assert loop.work_log is None


def test_tool_results_are_logged_for_the_agent_but_not_for_the_apps_own_review(store):
    loop = audit_loop(store, Audit())
    loop.work_log.store = recorder = LogStore()
    loop.claimed = True
    from app.services.agent_comparison import JudgeArgs
    page = ReadOnlyTool("read_source", "Read a page.", JudgeArgs, lambda args, cancellation: {"text": "Page text."})
    registry = ToolRegistry([page], argument_limit=1000)
    value = AgentCompletion()
    value.step_id = "completion:0"
    call = {"id": "c1", "type": "function", "function": {"name": "read_source", "arguments": "{}"}}
    loop._execute(registry, value, loop.cancellation, call)
    loop.app_registry = registry
    loop._execute(registry, value, loop.cancellation, {**call, "id": "c2"})
    loop.work_log.close()
    assert [(e["kind"], e["name"], e["data"]) for e in recorder.entries] == [("tool", "read_source", "web")]


# --- Reading, deleting, retention ---------------------------------------------------

@pytest.mark.parametrize("admin", [True, False])
def test_only_accounts_with_audit_read_the_log(api, monkeypatch, admin):
    from app.api.routers import agent as agent_router
    client, store, _ = api
    monkeypatch.setattr(agent_router, "audit_allowed", lambda uid: admin)
    chat_id, turn = pending(store)
    response = client.get(f"/agent/chats/{chat_id}/turns/{turn['id']}/work-log", headers=AUTH)
    if admin:
        assert response.status_code == 200 and response.json()["entries"] == []
    else:
        assert response.status_code == 404


def test_the_reader_learns_when_entries_were_lost(store):
    chat_id, turn = pending(store)
    assert store.read_work_log(UID, chat_id, turn["id"])["incomplete"] is False
    store._turn_ref(UID, chat_id, turn["id"]).update({"work_log_incomplete": True})
    assert store.read_work_log(UID, chat_id, turn["id"])["incomplete"] is True


def test_deleting_the_chat_deletes_its_log_and_the_content_its_entries_name(store, monkeypatch):
    objects = Objects()
    objects.put("work-log/agent-user/other/t/000001", b"keep", "text/plain")
    monkeypatch.setattr(agent_work_log, "_objects", lambda: objects)
    chat_id, turn = pending(store)
    key = f"work-log/{UID}/{chat_id}/{turn['id']}/000002"
    entries = store._turn_ref(UID, chat_id, turn["id"]).collection("work_log")
    entries.document("000001").set({"seq": 1, "content": "short"})
    entries.document("000002").set({"seq": 2, "content": "x", "ref": key})
    objects.put(key, b"long", "text/plain")
    store._purge_chat(UID, chat_id)
    assert not entries.document("000001").get().exists and not entries.document("000002").get().exists
    assert list(objects.items) == ["work-log/agent-user/other/t/000001"]


def test_deleting_a_chat_without_a_log_never_calls_the_object_store(store, monkeypatch):
    def unexpected():
        raise AssertionError("no object store call expected")
    monkeypatch.setattr(agent_work_log, "_objects", unexpected)
    chat_id, _ = pending(store)
    store._purge_chat(UID, chat_id)


class GroupDatabase(Database):
    """Collection-group queries over turns, and DELETE_FIELD in updates."""

    def collection_group(self, name):
        return GroupQuery(self, name)

    def apply_update(self, ref, data):
        removed = [key for key, value in data.items() if value is firestore.DELETE_FIELD]
        super().apply_update(ref, {k: v for k, v in data.items() if k not in removed})
        for key in removed:
            self.documents[ref.path].pop(key, None)


class GroupQuery:
    def __init__(self, database, name):
        self.database, self.name, self.filters, self.field, self.page, self.after = database, name, [], None, None, None

    def where(self, filter=None):
        self.filters.append(filter)
        return self

    def order_by(self, field):
        self.field = field
        return self

    def limit(self, value):
        self.page = value
        return self

    def start_after(self, snapshot):
        self.after = snapshot.reference.path
        return self

    def stream(self):
        items = []
        for path, data in sorted(self.database.documents.items()):
            if len(path) < 2 or path[-2] != self.name:
                continue
            if all(data.get(f.field_path) is not None and data[f.field_path] <= f.value for f in self.filters):
                items.append(FakeSnapshot(FakeDocumentRef(self.database, path), data))
        items.sort(key=lambda snapshot: snapshot.to_dict()[self.field])
        if self.after is not None:
            paths = [item.reference.path for item in items]
            items = items[paths.index(self.after) + 1:] if self.after in paths else items
        return items[:self.page]


def test_retention_removes_logs_past_their_expiry_and_keeps_the_others(monkeypatch):
    from app.services.agent_runs import AgentRunStore
    store = AgentRunStore(GroupDatabase())
    objects = Objects()
    old_chat, old_turn = pending(store, request_id="old")
    new_chat, new_turn = pending(store, request_id="new")
    past = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    future = (datetime.now(timezone.utc) + timedelta(days=3)).isoformat()
    refs = {}
    for chat_id, turn, expiry in ((old_chat, old_turn, past), (new_chat, new_turn, future)):
        turn_ref = store._turn_ref(UID, chat_id, turn["id"])
        turn_ref.update({"work_log_expires_at": expiry, "work_log_incomplete": True})
        key = f"work-log/{UID}/{chat_id}/{turn['id']}/000001"
        refs[chat_id] = turn_ref.collection("work_log").document("000001")
        refs[chat_id].set({"seq": 1, "content": "x", "ref": key})
        objects.put(key, b"long", "text/plain")
    assert agent_work_log.cleanup_expired_work_logs(store.db, objects=objects) == 1
    assert not refs[old_chat].get().exists and refs[new_chat].get().exists
    old = store._turn_ref(UID, old_chat, old_turn["id"]).get().to_dict()
    assert "work_log_expires_at" not in old and "work_log_incomplete" not in old and old["status"] == "pending"
    assert "work_log_expires_at" in store._turn_ref(UID, new_chat, new_turn["id"]).get().to_dict()
    assert list(objects.items) == [f"work-log/{UID}/{new_chat}/{new_turn['id']}/000001"]

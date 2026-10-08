"""Agent turns run independently of their connection (app.services.agent_background)."""
from __future__ import annotations

import asyncio
import json
import threading
import time

import anyio
import pytest
from starlette.requests import Request

from app.api.routers import agent
from app.services.agent_live import AgentLiveBuffers
from app.services.agent_runtime import AgentCapacity, AgentStreamingResponse
from app.services.llm.agent_client import AgentCompletion
from app.services.llm.provider_runtime import ProviderCancellation, ProviderCancelled
from test_agent_runs import AUTH, UID, api, receipt, store  # noqa: F401 (fixtures)

pytestmark = pytest.mark.usefixtures("deepseek_default_agent")


@pytest.fixture
def runs(_fresh_agent_background):
    return _fresh_agent_background


@pytest.fixture
def live(monkeypatch):
    buffers = AgentLiveBuffers()
    monkeypatch.setattr(agent, "agent_live", buffers)
    return buffers


class Gate:
    """A provider call that streams one chunk, then waits for the test.

    It ends like a real provider call when the run is cancelled (Stop,
    shutdown), so the producer can settle and save.
    """

    def __init__(self, monkeypatch):
        self.open = threading.Event()
        self.entered = threading.Event()
        self.cancellations = []
        self.calls = 0
        created = self.cancellations

        class Recorded(ProviderCancellation):
            def __init__(self):
                super().__init__()
                created.append(self)

        monkeypatch.setattr(agent, "ProviderCancellation", Recorded)
        gate = self

        def stream(completion, **kwargs):
            gate.calls += 1
            value = receipt()
            completion.__dict__.update(value.__dict__)
            yield {"type": "delta", "text": completion.text}
            gate.entered.set()
            while not gate.open.wait(0.01):
                if gate.cancellations and gate.cancellations[-1].cancelled:
                    raise ProviderCancelled("Provider request cancelled")

        monkeypatch.setattr(AgentCompletion, "stream", stream)


def _request():
    return Request({"type": "http", "headers": [(b"authorization", b"Bearer verified")], "client": ("test", 123)})


def _chat(client):
    return client.post("/chats", json={"execution_mode": "agent"}, headers=AUTH).json()["chat"]["id"]


def _start(client, request_id, bookmark="bm1"):
    chat_id = _chat(client)
    payload = agent.AgentRequest(chat_id=chat_id, question="Hi", client_request_id=request_id, bookmark_id=bookmark)
    return chat_id, agent.run_agent.__wrapped__(_request(), payload)


def _idle(runs, timeout=10):
    deadline = time.monotonic() + timeout
    while runs.active():
        assert time.monotonic() < deadline, "the background run did not end"
        time.sleep(0.01)


def _turn(store, chat_id):
    return store.list_turns(UID, chat_id)["turns"][0]


def _terminal(live, chat_id, request_id):
    events = live.read(UID, chat_id, request_id)["events"]
    return [event for event in events if event["type"] in {"final", "error"}]


def test_a_response_nobody_reads_still_finishes_and_saves(api, runs, live, monkeypatch):
    client, store, calls = api
    capacity = AgentCapacity(1)
    monkeypatch.setattr(agent, "agent_capacity", capacity)
    chat_id, response = _start(client, "unread")
    assert isinstance(response, AgentStreamingResponse)
    _idle(runs)
    assert len(calls) == 1
    assert _turn(store, chat_id)["status"] == "completed"
    assert store.db.collection("users").document(UID).collection("bookmarks").document("bm1").get().exists
    assert [event["type"] for event in _terminal(live, chat_id, "unread")] == ["final"]
    capacity.acquire().release()


def test_closing_the_response_mid_run_does_not_stop_it(api, runs, live, monkeypatch):
    client, store, _ = api
    gate = Gate(monkeypatch)
    chat_id, response = _start(client, "leaves")
    assert gate.entered.wait(5)

    async def read_then_leave():
        chunks = []
        iterator = response.body_iterator
        with anyio.fail_after(5):
            async for chunk in iterator:
                chunks.append(chunk)
                if "event: accepted" in chunk:
                    break
        await iterator.aclose()
        return chunks

    chunks = anyio.run(read_then_leave)
    assert chunks[0].startswith(":") and any("event: accepted" in chunk for chunk in chunks)
    assert runs.active() == 1  # The reader left; the run did not.
    gate.open.set()
    _idle(runs)
    assert _turn(store, chat_id)["status"] == "completed"
    # A browser that reconnects reads the rest, including the answer.
    data = client.get(f"/agent/chats/{chat_id}/live", params={"request_id": "leaves", "after": 2}, headers=AUTH).json()
    assert data["known"] is True and data["done"] is True and data["events"][-1]["type"] == "final"


def test_stop_by_request_cancels_the_run_and_tells_every_follower(api, runs, live, monkeypatch):
    client, store, _ = api
    gate = Gate(monkeypatch)
    chat_id, _response = _start(client, "stop-me")
    assert gate.entered.wait(5)
    stopped = client.post(f"/agent/chats/{chat_id}/requests/stop-me/stop", headers=AUTH)
    assert stopped.status_code == 200 and stopped.json() == {"status": "stopping"}
    _idle(runs, timeout=3)  # In-process: no wait for the saved-state watcher.
    [terminal] = _terminal(live, chat_id, "stop-me")
    assert terminal["type"] == "error" and terminal["data"]["code"] == "cancelled"
    assert terminal["data"]["recoverable"] is True
    assert _turn(store, chat_id)["status"] == "failed"
    root = store.receipt_ref(UID, chat_id, _turn(store, chat_id)["id"]).get().to_dict()
    assert root["run_status"] == "cancelled" and "running" not in root["step_states"].values()
    assert gate.calls == 1
    # Stopping again is harmless.
    again = client.post(f"/agent/chats/{chat_id}/requests/stop-me/stop", headers=AUTH)
    assert again.status_code == 200 and again.json() == {"status": "not_running"}


def test_a_stop_that_overtakes_its_request_keeps_it_from_starting(api, runs, live):
    client, store, calls = api
    chat_id = _chat(client)
    early = client.post(f"/agent/chats/{chat_id}/requests/early/stop", headers=AUTH)
    assert early.status_code == 200 and early.json() == {"status": "not_running"}
    payload = {"chat_id": chat_id, "question": "Hi", "client_request_id": "early", "bookmark_id": "bm1"}
    response = client.post("/agent", json=payload, headers=AUTH)
    assert response.status_code == 409 and response.json()["code"] == "cancelled"
    assert not calls and runs.active() == 0
    assert _turn(store, chat_id)["status"] == "failed"
    # The marker is used up: a new request identity runs normally.
    retry = client.post("/agent", json={**payload, "client_request_id": "early-2"}, headers=AUTH)
    assert "event: final" in retry.text and len(calls) == 1


def test_stop_validates_its_path_and_owner(api, runs):
    client, _store, _ = api
    chat_id = _chat(client)
    assert client.post("/agent/chats/not-a-chat/requests/x/stop", headers=AUTH).status_code == 404
    assert client.post(f"/agent/chats/{chat_id}/requests/bad%20id!/stop", headers=AUTH).status_code == 404
    assert client.post(f"/agent/chats/{chat_id}/requests/x/stop").status_code == 401


def test_another_account_cannot_stop_a_run(api, runs, live, monkeypatch):
    client, store, _ = api
    gate = Gate(monkeypatch)
    chat_id, _response = _start(client, "mine")
    assert gate.entered.wait(5)
    other = client.post(f"/agent/chats/{chat_id}/requests/mine/stop", headers={"Authorization": "Bearer other"})
    assert other.status_code == 200 and other.json()["status"] == "not_running"
    assert runs.active() == 1 and not gate.cancellations[-1].cancelled
    gate.open.set()
    _idle(runs)
    assert _turn(store, chat_id)["status"] == "completed"


def test_turn_stop_cancels_a_run_of_this_process_at_once(api, runs, live, monkeypatch):
    client, store, _ = api
    gate = Gate(monkeypatch)
    chat_id, _response = _start(client, "sidebar")
    assert gate.entered.wait(5)
    turn_id = _turn(store, chat_id)["id"]
    assert client.post(f"/agent/chats/{chat_id}/turns/{turn_id}/stop", headers=AUTH).status_code == 200
    _idle(runs, timeout=2)
    assert _turn(store, chat_id)["status"] == "failed"


def test_shutdown_refuses_new_turns_and_saves_interrupted_ones(api, runs, live, monkeypatch):
    client, store, calls = api
    gate = Gate(monkeypatch)
    chat_id, _response = _start(client, "restart")
    assert gate.entered.wait(5)
    runs.begin_shutdown(grace=0.05)
    payload = {"chat_id": _chat(client), "question": "Hi", "client_request_id": "late", "bookmark_id": "bm2"}
    refused = client.post("/agent", json=payload, headers=AUTH)
    assert refused.status_code == 503 and refused.headers["retry-after"] == "5"
    assert runs.drain(grace=0.05, settle=5) == 0
    [terminal] = _terminal(live, chat_id, "restart")
    assert terminal["type"] == "error" and terminal["data"]["code"] == "run_interrupted"
    assert "server restarted" in terminal["data"]["error"]
    turn = store.get_turn(UID, chat_id, _turn(store, chat_id)["id"])
    # The saved turn says why it is incomplete, and its usage is settled.
    assert turn["status"] == "failed" and turn["agent_failure"]["code"] == "run_interrupted"
    root = store.receipt_ref(UID, chat_id, turn["id"]).get().to_dict()
    assert "running" not in root["step_states"].values()
    assert store.db.collection("users").document(UID).collection("bookmarks").document("bm1").get().exists
    assert gate.calls == 1


def test_drain_lets_a_running_turn_finish_within_the_grace(api, runs, live, monkeypatch):
    client, store, _ = api
    gate = Gate(monkeypatch)
    chat_id, _response = _start(client, "finishes")
    assert gate.entered.wait(5)
    threading.Timer(0.2, gate.open.set).start()
    assert runs.drain(grace=5, settle=1) == 0
    assert _turn(store, chat_id)["status"] == "completed"
    assert [event["type"] for event in _terminal(live, chat_id, "finishes")] == ["final"]


def test_drain_without_runs_returns_at_once(runs):
    started = time.monotonic()
    assert runs.drain(grace=30, settle=30) == 0
    assert time.monotonic() - started < 1
    assert runs.shutting_down


def test_registry_refuses_duplicates_and_forgets_finished_runs(runs):
    from app.services.agent_background import AgentRunDuplicate, AgentRunStopped
    release = threading.Event()
    common = dict(uid="u", chat_id="c" * 32, request_id="r", turn_id="t", cancel=release.set, interrupt=lambda _: release.set())
    first = runs.start(target=lambda: release.wait(5), **common)
    with pytest.raises(AgentRunDuplicate):
        runs.start(target=lambda: None, **common)
    assert runs.running("u", "c" * 32, "r")
    assert runs.stop("u", "c" * 32, request_id="r") is True
    assert first.finished.wait(5) and runs.active() == 0
    # A stop for something that is not running blocks exactly that request once.
    assert runs.stop("u", "c" * 32, request_id="r") is False
    with pytest.raises(AgentRunStopped):
        runs.start(target=lambda: None, **common)
    done = runs.start(target=lambda: None, **common)
    assert done.finished.wait(5)


def test_stop_markers_expire_and_are_bounded():
    from app.services.agent_background import AgentBackgroundRuns

    class Clock:
        now = 0.0

        def __call__(self):
            return self.now

    clock = Clock()
    runs = AgentBackgroundRuns(clock=clock, stop_ttl=10, max_stops=2)
    for request in ("a", "b", "c"):
        runs.stop("u", "c", request_id=request)
    assert list(runs._stops) == [("u", "c", "b"), ("u", "c", "c")]
    clock.now = 11
    finished = runs.start(uid="u", chat_id="c", request_id="b", turn_id="t", target=lambda: None,
                          cancel=lambda: None, interrupt=lambda _: None)
    assert finished.finished.wait(5)


def test_a_crashing_target_is_logged_and_forgotten(runs, caplog):
    def boom():
        raise RuntimeError("synthetic")
    run = runs.start(uid="u", chat_id="c", request_id="r", turn_id="t", target=boom,
                     cancel=lambda: None, interrupt=lambda _: None)
    assert run.finished.wait(5)
    assert runs.active() == 0 and "Agent background run crashed" in caplog.text


def test_sigterm_starts_the_drain_and_keeps_uvicorns_handler(monkeypatch):
    import main
    installed, previous_calls = {}, []
    monkeypatch.setattr(main.signal, "getsignal", lambda sig: lambda signum, frame: previous_calls.append(signum))
    monkeypatch.setattr(main.signal, "signal", lambda sig, handler: installed.setdefault(sig, handler))
    began = []
    monkeypatch.setattr(main.agent_background, "begin_shutdown", lambda: began.append(True))

    async def scenario():
        main._drain_agent_runs_on_sigterm()
        installed[main.signal.SIGTERM](main.signal.SIGTERM, None)
        await asyncio.sleep(0)
        await asyncio.sleep(0)

    asyncio.run(scenario())
    assert previous_calls == [main.signal.SIGTERM] and began == [True]


def test_tail_streams_frames_until_the_end_and_resets_a_late_reader():
    buffers = AgentLiveBuffers(max_events=3)
    run = buffers.open("u", "c", "r")
    buffers.record(run, "accepted", {"turn_id": "t"})
    for text in ("one ", "two ", "three ", "four"):
        buffers.record(run, "delta", {"text": text})
    buffers.finish(run)

    async def collect(after):
        return [chunk async for chunk in buffers.tail_sse(run, after, lead=": pad\n\n", interval=0.001)]

    chunks = anyio.run(collect, 0)
    assert chunks[0] == ": pad\n\n"
    # seq 1 (accepted) and 2 ("one ") were dropped: the reader gets the text
    # they produced, then every retained frame.
    assert chunks[1] == 'id: 2\nevent: reset\ndata: {"text": "one "}\n\n'
    assert [chunk.split("\n")[0] for chunk in chunks[2:]] == ["id: 3", "id: 4", "id: 5"]
    # A reader inside the window gets no reset.
    assert [chunk.split("\n")[0] for chunk in anyio.run(collect, 3)[1:]] == ["id: 4", "id: 5"]
    data = buffers.read("u", "c", "r", after=0)
    assert data["reset"] == {"seq": 2, "text": "one "}
    assert [event["seq"] for event in data["events"]] == [3, 4, 5] and data["done"] is True


def test_reset_text_follows_cleared_answers():
    buffers = AgentLiveBuffers(max_events=1)
    run = buffers.open("u", "c", "r")
    buffers.record(run, "delta", {"text": "draft"})
    buffers.record(run, "activity", {"kind": "status", "clear_response": True})
    buffers.record(run, "delta", {"text": "final "})
    buffers.record(run, "delta", {"text": "answer"})
    assert buffers.read("u", "c", "r")["reset"] == {"seq": 3, "text": "final "}


def test_tail_sends_keepalives_and_ends_for_an_evicted_run():
    buffers = AgentLiveBuffers(max_runs=1)
    run = buffers.open("u", "c", "r")

    async def first_two():
        chunks = []
        async for chunk in buffers.tail_sse(run, interval=0.001, keepalive=0.01):
            chunks.append(chunk)
            if len(chunks) == 2:
                return chunks

    assert anyio.run(first_two) == [": keepalive\n\n", ": keepalive\n\n"]
    buffers.record(run, "delta", {"text": "x"})
    buffers.open("u", "c", "other")  # Evicts the running buffer.
    buffers.finish(run)

    async def rest():
        return [chunk async for chunk in buffers.tail_sse(run, interval=0.001)]

    assert anyio.run(rest) == []


def test_a_running_buffer_is_shared_not_replaced():
    buffers = AgentLiveBuffers()
    run = buffers.open("u", "c", "r")
    assert buffers.open("u", "c", "r") is run
    buffers.finish(run)
    fresh = buffers.open("u", "c", "r")
    assert fresh is not run and run.evicted and fresh.seq == 0


def test_post_response_is_the_tail_with_the_stream_headers(api, runs):
    client, _store, _ = api
    chat_id = _chat(client)
    response = client.post("/agent", json={"chat_id": chat_id, "question": "Hi", "client_request_id": "headers",
                                           "bookmark_id": "bm1"}, headers=AUTH)
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.headers["cache-control"] == "private, no-store, no-transform"
    frames = [block for block in response.text.split("\n\n") if block.startswith("id: ")]
    assert frames[0].split("\n")[1] == "event: accepted" and frames[-1].split("\n")[1] == "event: final"
    assert json.loads(frames[-1].split("data: ", 1)[1])["turn"]["status"] == "completed"

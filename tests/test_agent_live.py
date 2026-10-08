"""Live replay of Agent streams for networks that buffer SSE (company proxies)."""
from __future__ import annotations

import json
import re

import pytest

from app.api.routers import agent
from app.services import agent_live as live_module
from app.services.agent_live import AgentLiveBuffers
from app.services.llm.streaming import SSE_HEADERS, SSE_PADDING, iter_sse_with_keepalive
from test_agent_runs import AUTH, UID, api, store  # noqa: F401 (fixtures)

pytestmark = pytest.mark.usefixtures("deepseek_default_agent")


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


def test_sequence_after_filter_and_done():
    buffers = AgentLiveBuffers()
    run = buffers.open("u", "c" * 32, "r1")
    assert [buffers.record(run, "delta", {"text": t})[0] for t in "abc"] == [1, 2, 3]
    data = buffers.read("u", "c" * 32, "r1", after=1)
    assert data["known"] is True and data["done"] is False
    assert [(e["seq"], e["type"], e["data"]["text"]) for e in data["events"]] == [(2, "delta", "b"), (3, "delta", "c")]
    assert data["last_seq"] == 3
    # Nothing new: last_seq stays where the reader is.
    assert buffers.read("u", "c" * 32, "r1", after=3) == {
        "events": [], "last_seq": 3, "done": False, "known": True, "more": False}
    buffers.finish(run)
    assert buffers.read("u", "c" * 32, "r1", after=3)["done"] is True


def test_unknown_and_other_accounts_are_not_known():
    buffers = AgentLiveBuffers()
    run = buffers.open("owner", "c" * 32, "r1")
    buffers.record(run, "delta", {"text": "secret"})
    for uid, chat, request in (("stranger", "c" * 32, "r1"), ("owner", "d" * 32, "r1"), ("owner", "c" * 32, "r2")):
        assert buffers.read(uid, chat, request) == {"events": [], "last_seq": 0, "done": False, "known": False, "more": False}


def test_per_run_event_and_byte_caps_drop_oldest_frames():
    buffers = AgentLiveBuffers(max_events=3)
    run = buffers.open("u", "c", "r")
    for index in range(5):
        buffers.record(run, "delta", {"text": str(index)})
    assert [e["seq"] for e in buffers.read("u", "c", "r")["events"]] == [3, 4, 5]
    buffers = AgentLiveBuffers(max_bytes=200)
    run = buffers.open("u", "c", "r")
    for index in range(10):
        buffers.record(run, "delta", {"text": "x" * 40})
    kept = buffers.read("u", "c", "r")["events"]
    assert kept and kept[-1]["seq"] == 10 and len(kept) < 10
    assert buffers.stats()["bytes"] <= 200


def test_global_caps_evict_ended_runs_first_and_ttl_expires_them():
    clock = Clock()
    buffers = AgentLiveBuffers(max_runs=2, clock=clock)
    first, second = buffers.open("u", "c", "1"), buffers.open("u", "c", "2")
    buffers.finish(second)
    buffers.open("u", "c", "3")
    assert buffers.read("u", "c", "1")["known"] is True
    assert buffers.read("u", "c", "2")["known"] is False
    buffers.finish(first)
    clock.now += live_module.ENDED_TTL_SECONDS
    assert buffers.read("u", "c", "1")["known"] is False
    assert buffers.read("u", "c", "3")["known"] is True
    clock.now += live_module.ACTIVE_TTL_SECONDS
    assert buffers.read("u", "c", "3")["known"] is False
    assert buffers.stats() == {"runs": 0, "bytes": 0}
    # The total byte budget evicts whole buffers, never just the newest frame.
    buffers = AgentLiveBuffers(max_total_bytes=300)
    old = buffers.open("u", "c", "old")
    buffers.record(old, "delta", {"text": "x" * 150})
    new = buffers.open("u", "c", "new")
    buffers.record(new, "delta", {"text": "y" * 150})
    assert buffers.read("u", "c", "old")["known"] is False
    assert buffers.read("u", "c", "new")["events"][0]["data"]["text"] == "y" * 150


def test_a_dropped_buffer_keeps_numbering_the_stream():
    buffers = AgentLiveBuffers(max_runs=1)
    run = buffers.open("u", "c", "1")
    assert buffers.record(run, "delta", {"text": "a"})[0] == 1
    buffers.open("u", "c", "2")
    assert buffers.record(run, "delta", {"text": "b"}) == (2, '{"text": "b"}')


def test_large_backlogs_are_paged(monkeypatch):
    monkeypatch.setattr(live_module, "MAX_EVENTS_PER_READ", 2)
    buffers = AgentLiveBuffers()
    run = buffers.open("u", "c", "r")
    for index in range(3):
        buffers.record(run, "delta", {"text": str(index)})
    buffers.finish(run)
    page = buffers.read("u", "c", "r")
    assert [e["seq"] for e in page["events"]] == [1, 2] and page["more"] is True and page["done"] is False
    rest = buffers.read("u", "c", "r", after=page["last_seq"])
    assert [e["seq"] for e in rest["events"]] == [3] and rest["more"] is False and rest["done"] is True


def test_padding_is_the_first_chunk_and_skipped_once_cancelled():
    from app.services.llm.provider_runtime import ProviderCancellation
    assert SSE_PADDING.startswith(":") and SSE_PADDING.endswith("\n\n") and len(SSE_PADDING) >= 2048
    def source():
        yield "event: delta\ndata: {}\n\n"
    stream = iter_sse_with_keepalive(source(), lead=SSE_PADDING)
    assert next(stream) == SSE_PADDING
    assert next(stream) == "event: delta\ndata: {}\n\n"
    cancelled = ProviderCancellation()
    cancelled.cancel()
    assert list(iter_sse_with_keepalive(source(), cancellation=cancelled, lead=SSE_PADDING)) == []
    assert "no-transform" in SSE_HEADERS["Cache-Control"]


def _frames(text):
    """(id, event, data) for every non-comment frame of an SSE body."""
    frames = []
    for block in text.split("\n\n"):
        fields = dict(line.split(": ", 1) for line in block.split("\n") if line and not line.startswith(":"))
        if fields:
            frames.append((int(fields["id"]), fields["event"], json.loads(fields["data"])))
    return frames


def test_agent_stream_numbers_frames_and_the_live_endpoint_replays_them(api, monkeypatch):
    client, store, calls = api
    buffers = AgentLiveBuffers()
    monkeypatch.setattr(agent, "agent_live", buffers)
    chat_id = client.post("/chats", json={"execution_mode": "agent"}, headers=AUTH).json()["chat"]["id"]
    payload = {"chat_id": chat_id, "question": "Hi", "client_request_id": "live-1", "bookmark_id": "agent_live"}
    response = client.post("/agent", json=payload, headers=AUTH)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "private, no-store, no-transform"
    assert response.headers["x-accel-buffering"] == "no"
    assert response.text.startswith(SSE_PADDING)
    frames = _frames(response.text)
    assert frames[0][1] == "accepted" and frames[-1][1] == "final"
    assert [seq for seq, _, _ in frames] == list(range(1, len(frames) + 1))

    url = f"/agent/chats/{chat_id}/live"
    live = client.get(url, params={"request_id": "live-1"}, headers=AUTH)
    assert live.status_code == 200 and live.headers["cache-control"] == "private, no-store"
    data = live.json()
    assert data["known"] is True and data["done"] is True and data["last_seq"] == len(frames)
    # Exactly what the stream sent this account, nothing more.
    assert [(e["seq"], e["type"], e["data"]) for e in data["events"]] == frames
    later = client.get(url, params={"request_id": "live-1", "after": 2}, headers=AUTH).json()
    assert [e["seq"] for e in later["events"]] == list(range(3, len(frames) + 1))

    # Owner-only: another account, another request or chat knows nothing.
    stranger = client.get(url, params={"request_id": "live-1"}, headers={"Authorization": "Bearer other"}).json()
    assert stranger["known"] is False and stranger["events"] == []
    assert client.get(url, params={"request_id": "other"}, headers=AUTH).json()["known"] is False
    assert client.get(f"/agent/chats/{'f' * 32}/live", params={"request_id": "live-1"}, headers=AUTH).json()["known"] is False
    assert client.get("/agent/chats/not-a-chat/live", params={"request_id": "live-1"}, headers=AUTH).status_code == 404
    assert client.get(url, params={"request_id": "bad id!"}, headers=AUTH).status_code == 422
    assert client.get(url, params={"request_id": "live-1"}).status_code == 401
    assert len(calls) == 1  # Polling never starts a model call.


def test_replayed_answer_opens_no_buffer(api, monkeypatch):
    client, store, calls = api
    buffers = AgentLiveBuffers()
    monkeypatch.setattr(agent, "agent_live", buffers)
    chat_id = client.post("/chats", json={"execution_mode": "agent"}, headers=AUTH).json()["chat"]["id"]
    payload = {"chat_id": chat_id, "question": "Hi", "client_request_id": "once", "bookmark_id": "agent_once"}
    assert client.post("/agent", json=payload, headers=AUTH).status_code == 200
    recovered = client.post("/agent", json={**payload, "recover_only": True}, headers=AUTH)
    assert recovered.headers["content-type"].startswith("application/json")
    # The stream's own buffer stays readable; recovery adds none.
    assert buffers.stats()["runs"] == 1
    assert re.fullmatch(r"\d+", str(buffers.read(UID, chat_id, "once")["last_seq"]))


def test_private_api_streams_keep_no_transform_under_the_security_middleware():
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse, StreamingResponse
    from fastapi.testclient import TestClient
    from app.core.security import CustomSecurityMiddleware
    app = FastAPI()
    app.add_middleware(CustomSecurityMiddleware)

    @app.get("/api/v1/stream")
    def stream():
        return StreamingResponse(iter([SSE_PADDING]), media_type="text/event-stream", headers=dict(SSE_HEADERS))

    @app.get("/api/v1/json")
    def plain():
        return JSONResponse({})

    client = TestClient(app)
    assert client.get("/api/v1/stream").headers.get_list("cache-control")[-1] == "private, no-store, no-transform"
    assert client.get("/api/v1/json").headers.get_list("cache-control")[-1] == "private, no-store"

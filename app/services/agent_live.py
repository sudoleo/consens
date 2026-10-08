"""Process-local frames of a running Agent turn: the one source every view reads.

The producer (app.services.agent_background) runs a turn independently of any
HTTP connection and records every frame here with a per-run sequence number.
Readers never drive the run, they only follow it:

- the POST /agent response tails the buffer as SSE (``tail_sse``), so closing
  that connection stops nothing;
- GET /agent/chats/{chat}/live returns the same frames as JSON, for networks
  that buffer SSE (company proxies, TLS-inspecting scanners) and for a browser
  that reconnects after a network drop, a sleeping tab or a reload.

Nothing here is persisted. A buffer exists only in the process that runs the
turn; another worker or a restart answers ``known: False`` and the browser
asks for the saved turn instead (``recover_only``). Buffers are keyed by
uid + chat_id + client_request_id, so the browser can address one before it
has received a single byte and no other account can ever read it.

Frames are bounded per run. A reader that fell behind the oldest retained
frame receives a ``reset`` first: the answer text as it stood just before
that frame (deltas appended, cleared where a status said so), so a late
reader still shows the right partial answer instead of a gap.
"""
from __future__ import annotations

import json
import threading
import time
from collections import OrderedDict, deque
from dataclasses import dataclass, field

import anyio
from fastapi.encoders import jsonable_encoder

MAX_EVENTS_PER_RUN = 10000
MAX_BYTES_PER_RUN = 4 * 1024 * 1024
MAX_RUNS = 64
MAX_TOTAL_BYTES = 48 * 1024 * 1024
ENDED_TTL_SECONDS = 600.0
# A run that never reported its end (a bug, a killed thread) must not keep
# its events forever.
ACTIVE_TTL_SECONDS = 3 * 3600.0
MAX_EVENTS_PER_READ = 500
TAIL_INTERVAL_SECONDS = 0.1
TAIL_KEEPALIVE_SECONDS = 15.0


def _text_effect(event_type, data):
    """How a frame changes the streamed answer text (agent-chat.js handlers)."""
    if not isinstance(data, dict):
        return None
    if event_type == "delta" and isinstance(data.get("text"), str) and data["text"]:
        return ("append", data["text"])
    if event_type == "activity" and data.get("kind") == "status" and data.get("clear_response"):
        return ("clear",)
    return None


@dataclass
class LiveRun:
    key: tuple
    created_at: float
    seq: int = 0
    bytes: int = 0
    done: bool = False
    ended_at: float | None = None
    # (seq, type, json text, size, text effect)
    events: deque = field(default_factory=deque)
    # The newest dropped frame and the answer text as it stood after it:
    # what a reader behind the retained window resets to.
    base_seq: int = 0
    base_text: str = ""
    # Evicted as a whole (global caps): its readers fall back to the saved turn.
    evicted: bool = False


class AgentLiveBuffers:
    def __init__(self, *, max_events=MAX_EVENTS_PER_RUN, max_bytes=MAX_BYTES_PER_RUN, max_runs=MAX_RUNS,
                 max_total_bytes=MAX_TOTAL_BYTES, ended_ttl=ENDED_TTL_SECONDS, active_ttl=ACTIVE_TTL_SECONDS,
                 clock=time.monotonic):
        self.max_events, self.max_bytes = max_events, max_bytes
        self.max_runs, self.max_total_bytes = max_runs, max_total_bytes
        self.ended_ttl, self.active_ttl = ended_ttl, active_ttl
        self._clock = clock
        self._lock = threading.Lock()
        self._runs: OrderedDict[tuple, LiveRun] = OrderedDict()
        self._total = 0

    @staticmethod
    def key(uid, chat_id, request_id):
        return (str(uid), str(chat_id), str(request_id))

    def open(self, uid, chat_id, request_id) -> LiveRun:
        """The buffer for one run: a fresh one, or the one still running.

        A request identity has exactly one producer, so a concurrent duplicate
        request shares the running buffer instead of cutting off its readers.
        """
        key = self.key(uid, chat_id, request_id)
        with self._lock:
            self._expire()
            old = self._runs.get(key)
            if old is not None and not old.done:
                return old
            if old is not None:
                del self._runs[key]
                self._evict(old)
            run = LiveRun(key=key, created_at=self._clock())
            self._runs[key] = run
            self._enforce_caps()
            return run

    def record(self, run: LiveRun, event_type: str, data) -> tuple[int, str]:
        """Assign the next sequence number and keep the frame; returns (seq, json)."""
        encoded = jsonable_encoder(data)
        text = json.dumps(encoded, ensure_ascii=False)
        size = len(text.encode("utf-8")) + len(event_type) + 24
        effect = _text_effect(event_type, encoded)
        with self._lock:
            run.seq += 1
            seq = run.seq
            if self._runs.get(run.key) is run:
                run.events.append((seq, event_type, text, size, effect))
                run.bytes += size
                self._total += size
                while run.events and (len(run.events) > self.max_events or run.bytes > self.max_bytes):
                    self._drop_oldest(run)
                self._enforce_caps()
        return seq, text

    def finish(self, run: LiveRun | None) -> None:
        if run is None:
            return
        with self._lock:
            if not run.done:
                run.done = True
                run.ended_at = self._clock()

    def read(self, uid, chat_id, request_id, after: int = 0) -> dict:
        key = self.key(uid, chat_id, request_id)
        with self._lock:
            self._expire()
            run = self._runs.get(key)
            if run is None:
                return {"events": [], "last_seq": int(after), "done": False, "known": False, "more": False}
            chunk, more, reset, done = self._slice(run, int(after), MAX_EVENTS_PER_READ)
        last_seq = chunk[-1][0] if chunk else (reset["seq"] if reset else max(int(after), 0))
        result = {
            "events": [{"seq": seq, "type": event_type, "data": json.loads(text)} for seq, event_type, text in chunk],
            "last_seq": last_seq,
            "done": done,
            "known": True,
            "more": more,
        }
        if reset:
            result["reset"] = reset
        return result

    def frames(self, run: LiveRun, after: int = 0, limit: int = MAX_EVENTS_PER_READ):
        """(frames, reset, done) of one run, also after it left the index."""
        with self._lock:
            chunk, _more, reset, done = self._slice(run, int(after), limit)
        return chunk, reset, done

    async def tail_sse(self, run: LiveRun, after: int = 0, *, lead: str | None = None,
                       interval: float = TAIL_INTERVAL_SECONDS, keepalive: float = TAIL_KEEPALIVE_SECONDS):
        """Follow a run as SSE until its last frame; leaving early stops nothing."""
        if lead:
            yield lead
        cursor = int(after)
        quiet_since = time.monotonic()
        while True:
            chunk, reset, done = self.frames(run, cursor)
            if reset:
                cursor = reset["seq"]
                data = json.dumps({"text": reset["text"]}, ensure_ascii=False)
                yield f"id: {cursor}\nevent: reset\ndata: {data}\n\n"
            for seq, event_type, text in chunk:
                cursor = seq
                yield f"id: {seq}\nevent: {event_type}\ndata: {text}\n\n"
            if chunk or reset:
                quiet_since = time.monotonic()
                continue
            if done:
                return
            if time.monotonic() - quiet_since >= keepalive:
                yield ": keepalive\n\n"
                quiet_since = time.monotonic()
            await anyio.sleep(interval)

    def stats(self) -> dict:
        with self._lock:
            return {"runs": len(self._runs), "bytes": self._total}

    def _slice(self, run, after, limit):
        if run.evicted:
            return [], False, None, run.done
        reset = None
        if after < run.base_seq:
            # Frames after the reader's position were dropped.
            reset = {"seq": run.base_seq, "text": run.base_text}
            after = run.base_seq
        pending = [(seq, event_type, text) for seq, event_type, text, _, _ in run.events if seq > after]
        chunk = pending[:limit]
        more = len(pending) > len(chunk)
        # Done only once the reader has every retained frame.
        return chunk, more, reset, run.done and not more

    def _drop_oldest(self, run):
        seq, _type, _text, size, effect = run.events.popleft()
        run.bytes -= size
        self._total -= size
        run.base_seq = seq
        if effect and effect[0] == "append":
            run.base_text += effect[1]
        elif effect:
            run.base_text = ""

    def _expire(self):
        now = self._clock()
        for key, run in list(self._runs.items()):
            age = now - (run.ended_at if run.done else run.created_at)
            if age >= (self.ended_ttl if run.done else self.active_ttl):
                self._drop(key)

    def _enforce_caps(self):
        # Ended buffers go first (oldest end first), then the oldest run.
        while len(self._runs) > self.max_runs or self._total > self.max_total_bytes:
            ended = [run for run in self._runs.values() if run.done]
            victim = min(ended, key=lambda run: run.ended_at) if ended else next(iter(self._runs.values()))
            self._drop(victim.key)

    def _drop(self, key):
        run = self._runs.pop(key, None)
        if run is not None:
            self._evict(run)

    def _evict(self, run):
        self._total -= run.bytes
        run.events.clear()
        run.bytes = 0
        run.base_text = ""
        run.evicted = True


agent_live = AgentLiveBuffers()

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
that frame (deltas appended, cleared where a status said so) and the newest
dropped frame of each kind that sets lasting state (turn id, review, memory,
allowance, resources), so a late reader still shows the right partial answer.
"""
from __future__ import annotations

import itertools
import json
import math
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
# What a retained frame costs beyond its JSON text (tuple, ints, str headers),
# measured on CPython; the caps count real memory, not just payload.
FRAME_OVERHEAD_BYTES = 256
ENDED_TTL_SECONDS = 600.0
# A run that never reported its end (a bug, a killed thread) must not keep
# its events forever.
ACTIVE_TTL_SECONDS = 3 * 3600.0
MAX_EVENTS_PER_READ = 500
TAIL_INTERVAL_SECONDS = 0.1
TAIL_KEEPALIVE_SECONDS = 15.0
# Frames whose newest instance stays meaningful after it scrolled out of the
# window: a late reader receives them with its reset (agent-chat.js handlers).
STICKY_TYPES = frozenset({"accepted", "started", "review", "memory", "quota", "resources", "watch"})


def _text_effect(event_type, data):
    """How a frame changes the streamed answer text (agent-chat.js handlers)."""
    if not isinstance(data, dict):
        return None
    if event_type == "delta" and isinstance(data.get("text"), str) and data["text"]:
        return "append"
    if event_type == "activity" and data.get("kind") == "status" and data.get("clear_response"):
        return "clear"
    return None


def _finite(value):
    """JSON without NaN/Infinity (invalid for browsers and JSONResponse)."""
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, dict):
        return {key: _finite(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_finite(item) for item in value]
    return value


def _encode(data) -> str:
    encoded = jsonable_encoder(data)
    try:
        text = json.dumps(encoded, ensure_ascii=False, allow_nan=False)
    except ValueError:
        text = json.dumps(_finite(encoded), ensure_ascii=False, allow_nan=False)
    try:
        text.encode("utf-8")
    except UnicodeEncodeError:
        # A lone surrogate from provider text must not fail the whole run.
        text = text.encode("utf-8", "replace").decode("utf-8")
    return text


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
    # what a reader behind the retained window resets to, together with the
    # newest dropped frame of each sticky type ({type: (seq, json text)}).
    base_seq: int = 0
    base_text: str = ""
    sticky: dict = field(default_factory=dict)
    # Memory held by base_text and sticky frames (part of the global total).
    base_bytes: int = 0
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
        """The buffer for one run: a fresh one, or the one still running."""
        return self.acquire(uid, chat_id, request_id)[0]

    def acquire(self, uid, chat_id, request_id) -> tuple[LiveRun, bool]:
        """(buffer, created). A request identity has one producer, so a
        concurrent duplicate request shares the running buffer instead of
        cutting off its readers, and must not end it (created is False)."""
        key = self.key(uid, chat_id, request_id)
        with self._lock:
            self._expire()
            old = self._runs.get(key)
            if old is not None and not old.done:
                return old, False
            if old is not None:
                del self._runs[key]
                self._evict(old)
            run = LiveRun(key=key, created_at=self._clock())
            self._runs[key] = run
            self._enforce_caps()
            return run, True

    def discard(self, run: LiveRun) -> None:
        """Remove a buffer that never got a producer."""
        with self._lock:
            run.done = True
            run.ended_at = self._clock()
            if self._runs.get(run.key) is run:
                del self._runs[run.key]
            self._evict(run)

    def record(self, run: LiveRun, event_type: str, data) -> tuple[int, str]:
        """Assign the next sequence number and keep the frame; returns (seq, json)."""
        text = _encode(data)
        size = len(text.encode("utf-8")) + len(event_type) + FRAME_OVERHEAD_BYTES
        effect = _text_effect(event_type, data if isinstance(data, dict) else None)
        with self._lock:
            run.seq += 1
            seq = run.seq
            if self._runs.get(run.key) is run:
                run.events.append((seq, event_type, text, size, effect))
                run.bytes += size
                self._total += size
                # Never the newest frame: an oversized final/error must arrive.
                while len(run.events) > 1 and (len(run.events) > self.max_events or run.bytes > self.max_bytes):
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
            result["reset"] = {"seq": reset["seq"], "text": reset["text"],
                               "frames": [{"seq": seq, "type": event_type, "data": json.loads(text)}
                                          for seq, event_type, text in reset["frames"]]}
        return result

    def frames(self, run: LiveRun, after: int = 0, limit: int = MAX_EVENTS_PER_READ):
        """(frames, reset, done, evicted) of one run, also after it left the index."""
        with self._lock:
            chunk, _more, reset, done = self._slice(run, int(after), limit)
            return chunk, reset, done, run.evicted

    async def tail_sse(self, run: LiveRun, after: int = 0, *, lead: str | None = None,
                       interval: float = TAIL_INTERVAL_SECONDS, keepalive: float = TAIL_KEEPALIVE_SECONDS):
        """Follow a run as SSE until its last frame; leaving early stops nothing."""
        if lead:
            yield lead
        cursor = int(after)
        quiet_since = time.monotonic()
        while True:
            chunk, reset, done, evicted = self.frames(run, cursor)
            if evicted:
                # The frames are gone: end without a terminal frame, so the
                # browser follows the saved turn instead of a silent stream.
                return
            if reset:
                for seq, event_type, text in reset["frames"]:
                    yield f"id: {seq}\nevent: {event_type}\ndata: {text}\n\n"
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
            frames = sorted((seq, event_type, text) for event_type, (seq, text) in run.sticky.items() if seq > after)
            reset = {"seq": run.base_seq, "text": run.base_text, "frames": frames}
            after = run.base_seq
        # Sequence numbers in the window have no gaps: index, don't scan.
        start = max(0, after - run.events[0][0] + 1) if run.events else 0
        chunk = [(seq, event_type, text) for seq, event_type, text, _, _ in
                 itertools.islice(run.events, start, start + limit)]
        more = start + len(chunk) < len(run.events)
        # Done only once the reader has every retained frame.
        return chunk, more, reset, run.done and not more

    def _drop_oldest(self, run):
        seq, event_type, text, size, effect = run.events.popleft()
        run.bytes -= size
        self._total -= size
        run.base_seq = seq
        if effect == "append":
            run.base_text += json.loads(text)["text"]
        elif effect == "clear":
            run.base_text = ""
        if event_type in STICKY_TYPES:
            run.sticky[event_type] = (seq, text)
        held = len(run.base_text.encode("utf-8", "replace")) + sum(
            len(item.encode("utf-8")) + FRAME_OVERHEAD_BYTES for _, item in run.sticky.values())
        self._total += held - run.base_bytes
        run.base_bytes = held

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
        if run.evicted:
            return
        self._total -= run.bytes + run.base_bytes
        run.events.clear()
        run.bytes = run.base_bytes = 0
        run.base_text = ""
        run.sticky = {}
        run.evicted = True


agent_live = AgentLiveBuffers()

"""Process-local replay of a running Agent stream for networks that buffer SSE.

Some company proxies and TLS-inspecting virus scanners hold an event stream
back until the response ends: the browser sees "Thinking…" for minutes and
then the whole answer at once. The run itself is fine, only its bytes are
stuck. Every Agent SSE frame therefore carries a per-run sequence number
(`id:` line) and is also kept here, bounded, so the browser can fetch the same
events with short JSON polls (`GET /agent/chats/{chat}/live`) and render them
through its normal stream handlers.

Nothing here is persisted. A buffer exists only in the process that runs the
stream; another worker or a restart answers ``known: False`` and the browser
keeps its ordinary behaviour (wait for the stream, 45-second status check).
A buffer holds exactly the frames its own SSE response sends to the same
account, keyed by uid + chat_id + client_request_id so the browser can address
it before it has received a single byte.
"""
from __future__ import annotations

import json
import threading
import time
from collections import OrderedDict, deque
from dataclasses import dataclass, field

from fastapi.encoders import jsonable_encoder

MAX_EVENTS_PER_RUN = 2000
MAX_BYTES_PER_RUN = 2 * 1024 * 1024
MAX_RUNS = 64
MAX_TOTAL_BYTES = 24 * 1024 * 1024
ENDED_TTL_SECONDS = 600.0
# A stream that never reported its end (a bug, a killed thread) must not
# keep its events forever.
ACTIVE_TTL_SECONDS = 3 * 3600.0
MAX_EVENTS_PER_READ = 500


@dataclass
class LiveRun:
    key: tuple
    created_at: float
    seq: int = 0
    bytes: int = 0
    done: bool = False
    ended_at: float | None = None
    events: deque = field(default_factory=deque)


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
        """A fresh buffer for one streaming response (replaces an older one)."""
        key = self.key(uid, chat_id, request_id)
        with self._lock:
            self._expire()
            old = self._runs.pop(key, None)
            if old is not None:
                self._total -= old.bytes
            run = LiveRun(key=key, created_at=self._clock())
            self._runs[key] = run
            self._enforce_caps()
            return run

    def record(self, run: LiveRun, event_type: str, data) -> tuple[int, str]:
        """Assign the next sequence number and keep the frame; returns (seq, json)."""
        encoded = jsonable_encoder(data)
        text = json.dumps(encoded, ensure_ascii=False)
        size = len(text.encode("utf-8")) + len(event_type) + 16
        with self._lock:
            run.seq += 1
            seq = run.seq
            if self._runs.get(run.key) is run:
                run.events.append((seq, event_type, encoded, size))
                run.bytes += size
                self._total += size
                while run.events and (len(run.events) > self.max_events or run.bytes > self.max_bytes):
                    dropped = run.events.popleft()
                    run.bytes -= dropped[3]
                    self._total -= dropped[3]
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
            pending = [item for item in run.events if item[0] > after]
            chunk = pending[:MAX_EVENTS_PER_READ]
            last_seq = chunk[-1][0] if chunk else max(int(after), 0)
            more = len(pending) > len(chunk)
            return {
                "events": [{"seq": seq, "type": event_type, "data": data} for seq, event_type, data, _ in chunk],
                "last_seq": last_seq,
                # Done only once the reader has every retained event.
                "done": run.done and not more,
                "known": True,
                "more": more,
            }

    def stats(self) -> dict:
        with self._lock:
            return {"runs": len(self._runs), "bytes": self._total}

    def _expire(self):
        now = self._clock()
        for key, run in list(self._runs.items()):
            age = now - (run.ended_at if run.done else run.created_at)
            if age >= (self.ended_ttl if run.done else self.active_ttl):
                self._drop(key)

    def _enforce_caps(self):
        # Ended buffers go first (oldest end first), then the oldest stream.
        while len(self._runs) > self.max_runs or self._total > self.max_total_bytes:
            ended = [run for run in self._runs.values() if run.done]
            victim = min(ended, key=lambda run: run.ended_at) if ended else next(iter(self._runs.values()))
            self._drop(victim.key)

    def _drop(self, key):
        run = self._runs.pop(key, None)
        if run is not None:
            self._total -= run.bytes
            run.events.clear()
            run.bytes = 0


agent_live = AgentLiveBuffers()

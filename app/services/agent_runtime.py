"""Bound active Agent producers; each holds one slot from admission to its end."""
from __future__ import annotations

import os
import threading

from fastapi.responses import StreamingResponse


class AgentCapacityExceeded(Exception):
    pass


class AgentCapacity:
    def __init__(self, limit):
        if not 1 <= limit <= 64:
            raise ValueError("AGENT_MAX_CONCURRENT_RUNS must be between 1 and 64")
        self._slots = threading.BoundedSemaphore(limit)

    def acquire(self):
        if not self._slots.acquire(blocking=False):
            raise AgentCapacityExceeded("Agent capacity is busy. Please try again shortly.")
        return AgentLease(self._slots)


class AgentLease:
    def __init__(self, slots):
        self._slots = slots
        self._lock = threading.Lock()
        self._state = "reserved"

    def start(self):
        with self._lock:
            if self._state != "reserved":
                return False
            self._state = "running"
            return True

    def release(self):
        with self._lock:
            if self._state != "released":
                self._state = "released"
                self._slots.release()


class AgentStreamingResponse(StreamingResponse):
    """The POST /agent response: a tail of the run's frames, nothing more.

    The run belongs to its producer thread (agent_background) and holds the
    lease; a client that disconnects only ends this response. ``lease`` is
    kept for observation (tests), never released here.
    """

    def __init__(self, *args, lease, **kwargs):
        super().__init__(*args, **kwargs)
        self._lease = lease


agent_capacity = AgentCapacity(int(os.getenv("AGENT_MAX_CONCURRENT_RUNS", "16")))

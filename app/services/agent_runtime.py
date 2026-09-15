"""Bound active Agent producers, including responses that never start streaming."""
from __future__ import annotations

import os
import threading

import anyio

from app.services.llm.streaming import ProviderStreamingResponse


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

    def abandon(self, cleanup):
        with self._lock:
            if self._state != "reserved":
                return
            self._state = "closing"
        try:
            cleanup()
        finally:
            self.release()


class AgentStreamingResponse(ProviderStreamingResponse):
    def __init__(self, *args, lease, cleanup, **kwargs):
        super().__init__(*args, **kwargs)
        self._lease, self._cleanup = lease, cleanup

    async def __call__(self, scope, receive, send):
        try:
            await super().__call__(scope, receive, send)
        finally:
            # A generator's finally block does not run if it was never entered.
            # Fence a late pump before cleaning that reservation up off-loop.
            with anyio.CancelScope(shield=True):
                await anyio.to_thread.run_sync(self._lease.abandon, self._cleanup)


agent_capacity = AgentCapacity(int(os.getenv("AGENT_MAX_CONCURRENT_RUNS", "16")))

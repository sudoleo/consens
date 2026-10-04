"""Measure one Consensus-pipeline operation and book it on the token account.

The transport reports usage (``llm.usage_meter``); this module only binds a
meter around one logical operation (an ``/ask_*`` answer, the ``/consensus``
analysis, a Resolve round, an API pipeline run) and books the totals exactly
once through ``usage_repository.book_operation``. Booking happens when the
operation ends: normally right before its final event, otherwise when the
stream is closed (client gone, error). A failed booking never fails the
user's answer; it is logged as an accounting error instead.
"""

from __future__ import annotations

import logging
import threading
from contextlib import contextmanager

from app.core.observability import safe_exception
from app.services.llm.usage_meter import UsageMeter, bind_usage_meter


class OperationBooking:
    def __init__(self, repository, uid: str, usage_run_key: str, operation: str, *, final: bool = False,
                 skip_empty: bool = False):
        self._repository = repository
        self.uid = uid
        self.usage_run_key = usage_run_key
        self.operation = operation
        self.final = final
        # Optional operations (chat memory) book nothing when no call ran, so
        # a later attempt of the same turn can still book its real call.
        self.skip_empty = skip_empty
        self.meter = UsageMeter()
        self._lock = threading.Lock()
        self._done = False
        self.token_budget: dict | None = None
        self.totals: dict | None = None

    @contextmanager
    def metering(self):
        with bind_usage_meter(self.meter):
            yield self

    def finish(self) -> dict | None:
        """Book once; later calls return the same snapshot."""
        with self._lock:
            if self._done:
                return self.token_budget
            self._done = True
        totals = self.totals = self.meter.close()
        if self.skip_empty and not totals["calls"]:
            return None
        try:
            self.token_budget = self._repository.book_operation(
                self.uid, self.usage_run_key, self.operation,
                measured=totals["measured"], estimated=totals["estimated"], final=self.final,
            )
        except Exception as exc:
            logging.error(
                "Token booking failed operation=%s measured=%d estimated=%d category=%s",
                self.operation.split(":")[0], totals["measured"], totals["estimated"], safe_exception(exc),
            )
            return None
        logging.info(
            "Tokens booked operation=%s calls=%d measured=%d estimated=%d missing=%d",
            self.operation.split(":")[0], totals["calls"], totals["measured"],
            totals["estimated"], totals["missing_calls"],
        )
        return self.token_budget

    def extras(self) -> dict:
        budget = self.finish()
        return {"token_budget": budget} if budget else {}


def metered_events(source, booking: OperationBooking):
    """Run an engine event generator under the booking's meter.

    The meter is bound inside this generator, i.e. on the thread that drives
    it (the SSE pump). The final event carries the booked account snapshot.
    """
    with booking.metering():
        try:
            for event in source:
                if isinstance(event, dict) and event.get("type") == "final":
                    event = {**event, "extras": {**(event.get("extras") or {}), **booking.extras()}}
                yield event
        finally:
            try:
                close = getattr(source, "close", None)
                if callable(close):
                    close()
            finally:
                # A failing transport cleanup must not skip spent-token
                # settlement. Storage failures are handled by finish(); the
                # original cleanup exception still reaches the caller.
                booking.finish()

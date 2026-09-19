"""Scoped transport injection for shared structured tasks (judges, repairs).

The default Consensus transport is unchanged. Agent supplies a metered transport
so every retry has the same cancellation, claim and usage guarantees as chat.
"""
from contextlib import contextmanager
from contextvars import ContextVar

task_transport = ContextVar("structured_task_transport", default=None)


@contextmanager
def bind_task_transport(transport):
    token = task_transport.set(transport)
    try:
        yield
    finally:
        task_transport.reset(token)

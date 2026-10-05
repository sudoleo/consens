"""Did a failed provider request ever reach the provider?

A started call without usage is charged a bounded estimate (usage meter,
Agent ledger). That estimate exists because a request that left this process
may have made the provider work. A request that provably never left it did
no provider work and settles as not started, i.e. free:

- connect-phase failures: DNS/name resolution, refused connection, connect
  timeout, no free pool connection (``requests``/urllib3 and ``httpx``);
- cancellation or analysis-budget stops raised before the socket task ran,
  which the transport marks with ``mark_not_dispatched``.

Everything else stays started. A connection error while reading a response
(``ProtocolError``, ``ChunkedEncodingError``, read timeout, TLS error, proxy
error) means the request was or may have been sent.
"""

from __future__ import annotations

import httpx
import requests
from urllib3.exceptions import ConnectTimeoutError, MaxRetryError, NewConnectionError

_NOT_DISPATCHED = "_consensio_provider_not_dispatched"

# httpcore maps only connection setup (socket, DNS, TLS handshake) to these;
# read/write failures become ReadError/WriteError/RemoteProtocolError.
_HTTPX_CONNECT_PHASE = (httpx.ConnectError, httpx.ConnectTimeout, httpx.PoolTimeout)


def mark_not_dispatched(exc: BaseException) -> BaseException:
    """Tag an exception raised before the request could be sent."""
    try:
        setattr(exc, _NOT_DISPATCHED, True)
    except Exception:
        # Exceptions without an instance dict stay conservatively "started".
        pass
    return exc


def _requests_connect_failure(exc: BaseException) -> bool:
    if isinstance(exc, requests.exceptions.ConnectTimeout):
        return True
    if not isinstance(exc, requests.exceptions.ConnectionError):
        return False
    if isinstance(exc, (requests.exceptions.SSLError, requests.exceptions.ProxyError)):
        return False
    # requests wraps urllib3's error as the first argument. Mid-body failures
    # arrive as ProtocolError/ReadTimeoutError there, never as a connect error.
    reason = exc.args[0] if exc.args else None
    if isinstance(reason, MaxRetryError):
        reason = reason.reason
    # NameResolutionError (urllib3 2) and NewConnectionError subclass
    # ConnectTimeoutError; all are raised while opening the socket.
    return isinstance(reason, (NewConnectionError, ConnectTimeoutError))


def never_reached_provider(exc: BaseException | None) -> bool:
    """True only when the failed request provably never reached the provider."""
    if exc is None:
        return False
    if getattr(exc, _NOT_DISPATCHED, False):
        return True
    if isinstance(exc, _HTTPX_CONNECT_PHASE):
        return True
    return _requests_connect_failure(exc)

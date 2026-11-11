"""Networks whose requests are refused before the app does any work.

A crawler wave reads every share and Topic page, each stored version
included, out of the data centres of two cloud providers. Nearly every
request comes from another address, so the limits per address never see it,
and it does not read robots.txt. A page it asks for costs up to a hundred
Firestore reads. Readers do not browse from those ranges, so the ranges are
refused as a whole.
"""
import ipaddress

from app.core.request_limits import client_of

# Allocations as the registries list them (RDAP), never single addresses:
# the wave rotates through them. A neighbouring range belongs to someone
# else (47.73/16 is Vodafone's customers, 47.128/14 Amazon), so a new entry
# is looked up first.
BLOCKED_NETWORKS = tuple(ipaddress.ip_network(network) for network in (
    # Alibaba Cloud
    "8.208.0.0/12", "47.74.0.0/15", "47.76.0.0/14", "47.80.0.0/13",
    # Tencent Cloud
    "43.128.0.0/10", "49.51.0.0/16", "129.226.0.0/16", "161.120.0.0/16",
    "170.106.0.0/16",
))
# A customer's server may well run in one of those clouds and call the API
# with its key.
OPEN_PREFIX = "/api/v1/"


def is_blocked(address: str) -> bool:
    try:
        parsed = ipaddress.ip_address(address)
    except ValueError:
        return False
    return any(parsed in network for network in BLOCKED_NETWORKS)


class NetworkBlockMiddleware:
    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") == "http" and not str(scope.get("path") or "").startswith(OPEN_PREFIX):
            headers = {key.lower(): value for key, value in scope.get("headers", [])}
            if is_blocked(client_of(headers, scope.get("client"))):
                await send({
                    "type": "http.response.start", "status": 403,
                    "headers": [(b"content-type", b"text/plain; charset=utf-8"), (b"content-length", b"9")],
                })
                await send({"type": "http.response.body", "body": b"Forbidden"})
                return
        await self.app(scope, receive, send)

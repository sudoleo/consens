"""Static caching and compression must never touch Server-Sent Events."""
import asyncio
import gzip
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.testclient import TestClient

from app.core.static_delivery import IMMUTABLE_CACHE_CONTROL, StaticDeliveryMiddleware, is_hashed_dist_path

ROOT = Path(__file__).resolve().parents[1]


def _app():
    app = FastAPI()
    app.add_middleware(StaticDeliveryMiddleware)

    @app.get("/stream")
    def stream():
        def events():
            for index in range(3):
                yield f"event: delta\ndata: {{\"text\": \"{'x' * 900}{index}\"}}\n\n"
        return StreamingResponse(events(), media_type="text/event-stream")

    @app.get("/page")
    def page():
        return HTMLResponse("<!doctype html><p>" + "consens " * 400 + "</p>")

    @app.get("/data")
    def data():
        return JSONResponse({"value": "x" * 4000})

    from fastapi.staticfiles import StaticFiles
    app.mount("/static", StaticFiles(directory=str(ROOT / "static")), name="static")
    return app


def test_event_stream_is_never_gzip_encoded():
    client = TestClient(_app())
    response = client.get("/stream", headers={"Accept-Encoding": "gzip, br"})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "content-encoding" not in response.headers
    assert "accept-encoding" not in response.headers.get("vary", "").lower()
    assert response.text.count("event: delta") == 3


def test_event_stream_frames_are_forwarded_one_by_one():
    """Each yielded SSE frame reaches the transport as its own body message."""
    sent = []

    async def app(scope, receive, send):
        await send({"type": "http.response.start", "status": 200,
                    "headers": [(b"content-type", b"text/event-stream; charset=utf-8")]})
        for index in range(3):
            await send({"type": "http.response.body", "body": f"data: {index}\n\n".encode(), "more_body": True})
        await send({"type": "http.response.body", "body": b"", "more_body": False})

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        sent.append(message)

    scope = {"type": "http", "method": "POST", "path": "/agent",
             "headers": [(b"accept-encoding", b"gzip")]}
    asyncio.run(StaticDeliveryMiddleware(app)(scope, receive, send))
    bodies = [m["body"] for m in sent if m["type"] == "http.response.body"]
    assert bodies == [b"data: 0\n\n", b"data: 1\n\n", b"data: 2\n\n", b""]
    assert all(name != b"content-encoding" for name, _ in sent[0]["headers"])


def test_main_app_serves_dist_immutable_and_keeps_json_errors_uncompressed():
    import main

    assert any(m.cls is StaticDeliveryMiddleware for m in main.app.user_middleware)
    client = TestClient(main.app)
    name = next(p.name for p in (ROOT / "static" / "dist").glob("app.*.js") if is_hashed_dist_path(f"/static/dist/{p.name}"))
    asset = client.get(f"/static/dist/{name}", headers={"Accept-Encoding": "gzip"})
    assert asset.headers["cache-control"] == IMMUTABLE_CACHE_CONTROL
    assert asset.headers["content-encoding"] == "gzip"
    # A pre-stream refusal of an SSE endpoint is JSON and stays identity-encoded.
    refused = client.post("/agent", json={}, headers={"Accept-Encoding": "gzip"})
    assert refused.status_code in (401, 403, 422)
    assert "content-encoding" not in refused.headers


def test_hashed_dist_file_is_immutable_and_gzip_encoded():
    dist = sorted(p for p in (ROOT / "static" / "dist").glob("app.*.js") if is_hashed_dist_path(f"/static/dist/{p.name}"))
    assert dist, "npm run build must have produced a hashed bundle"
    client = TestClient(_app())
    path = f"/static/dist/{dist[-1].name}"
    response = client.get(path, headers={"Accept-Encoding": "gzip"})
    assert response.status_code == 200
    assert response.headers["cache-control"] == IMMUTABLE_CACHE_CONTROL
    assert response.headers["content-encoding"] == "gzip"
    assert "accept-encoding" in response.headers["vary"].lower()
    # httpx decodes transparently; the decoded bytes equal the file.
    assert response.content == dist[-1].read_bytes()
    raw = client.get(path, headers={"Accept-Encoding": "identity"})
    assert "content-encoding" not in raw.headers
    assert raw.headers["cache-control"] == IMMUTABLE_CACHE_CONTROL


def test_unhashed_static_file_keeps_revalidation():
    client = TestClient(_app())
    response = client.get("/static/style.css", headers={"Accept-Encoding": "gzip"})
    assert response.status_code == 200
    assert "immutable" not in response.headers.get("cache-control", "")
    assert response.headers.get("etag")


def test_html_is_compressed_but_api_json_is_not():
    client = TestClient(_app())
    page = client.get("/page", headers={"Accept-Encoding": "gzip"})
    assert page.headers["content-encoding"] == "gzip"
    assert "consens consens" in page.text
    data = client.get("/data", headers={"Accept-Encoding": "gzip"})
    assert "content-encoding" not in data.headers


def test_gzip_payload_round_trips():
    client = TestClient(_app())
    with client.stream("GET", "/page", headers={"Accept-Encoding": "gzip"}) as response:
        raw = b"".join(response.iter_raw())
    assert gzip.decompress(raw).startswith(b"<!doctype html>")


def test_hashed_dist_pattern():
    assert is_hashed_dist_path("/static/dist/app.909f83048173.js")
    assert is_hashed_dist_path("/static/dist/app.11dad8ad9bf7.css")
    assert not is_hashed_dist_path("/static/dist/manifest.json")
    assert not is_hashed_dist_path("/static/js/agent-chat.js")
    assert not is_hashed_dist_path("/static/dist/app.js")


def test_static_cache_policy_revalidates_unversioned_and_pins_content_hashes():
    client = TestClient(_app())
    plain = client.get("/static/css/foundation.css")
    hashed = client.get("/static/css/foundation.css?v=0123456789ab")
    manual = client.get("/static/css/foundation.css?v=20261002-fein2")
    assert plain.status_code == hashed.status_code == manual.status_code == 200
    # Unversioned (nested imports, images): always revalidate via ETag.
    assert plain.headers["cache-control"] == "no-cache"
    # asset_url's content hash never changes under its URL.
    assert hashed.headers["cache-control"] == IMMUTABLE_CACHE_CONTROL
    # A hand-written mark is no proof of content and is never pinned.
    assert manual.headers["cache-control"] == "no-cache"
    revalidated = client.get("/static/css/foundation.css", headers={"if-none-match": plain.headers["etag"]})
    assert revalidated.status_code == 304

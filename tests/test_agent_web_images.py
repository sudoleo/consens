"""show_image (agent_web_images.py, since 2026-10-28): a picture from the web
under the agent's answer. The server fetches it (a picture, or the preview
picture a page names for itself), only bytes that are a picture, encoded
anew, kept in the chat's private store as the turn's ``web_image`` with its
source; an address the message did not hold waits for the reviewers first.
Asked for a picture of the best Hearthstone Battlegrounds player on
2026-10-28, the agent could only say where one was.
"""
import asyncio
import io
import json

import httpx
import pytest
from PIL import Image

from app.services import agent_vm_tools, agent_web_images, prompt_defaults, watch_images
from app.services.agent_web_images import INTRO, encode, fetch_picture, page_picture
from test_agent_audit import Audit, audit_loop
from test_agent_gate import go, replies
from test_agent_runs import UID, store  # noqa: F401  (fixture)

PAGE = "https://liquipedia.net/hearthstone/Jeef"
PICTURE = "https://liquipedia.net/commons/images/jeef.jpg"
FOUND = "https://www.toureiffel.paris/en"


def png(size=(400, 300), color=(30, 120, 200)):
    buffer = io.BytesIO()
    Image.new("RGB", size, color).save(buffer, "PNG")
    return buffer.getvalue()


def test_a_page_names_its_own_picture():
    assert page_picture('<meta property="og:image" content="/img/jeef.jpg">', PAGE) == \
        "https://liquipedia.net/img/jeef.jpg"
    assert page_picture('<meta name="twitter:image" content="https://cdn.example/a.png">', "https://x.example/") \
        == "https://cdn.example/a.png"
    ld = '<script type="application/ld+json">{"@type": "Person", "image": "https://x.example/p.webp"}</script>'
    assert page_picture(ld, "https://x.example/") == "https://x.example/p.webp"
    assert page_picture("<p>No picture here.</p>", "https://x.example/") == ""


def test_only_a_picture_comes_through_and_encoded_anew():
    data, mime, width, height = encode(png((3200, 1600)))
    assert mime == "image/webp" and (width, height) == (agent_web_images.MAX_SIDE, 800)
    with Image.open(io.BytesIO(data)) as image:
        assert image.format == "WEBP"
    # A name or a type never makes something a picture: the bytes decide.
    assert encode(b"<svg onload=alert(1)>") is None
    # No smallest size (Max, 2026-10-28): a small logo or chart comes as it
    # is, and the agent learns its size.
    assert encode(png((70, 70)))[2:] == (70, 70)


def test_a_page_brings_its_preview_picture_with_the_page_as_referer():
    seen, picture = [], png()

    async def get(url, kinds, referer=""):
        seen.append((url, referer))
        if url == PAGE:
            return url, f'<meta property="og:image" content="{PICTURE}">'.encode(), "text/html", False
        return url, picture, "image/jpeg", False
    assert asyncio.run(fetch_picture(PAGE, get=get)) == (picture, PICTURE, PAGE)
    assert seen == [(PAGE, ""), (PICTURE, PAGE)]

    async def direct(url, kinds, referer=""):
        return url, picture, "application/octet-stream", False
    # A picture's own address needs no page.
    assert asyncio.run(fetch_picture(PICTURE, get=direct)) == (picture, PICTURE, "")

    async def bare(url, kinds, referer=""):
        return url, b"<p>No picture here.</p>", "text/html", False
    with pytest.raises(ValueError, match="og:image"):
        asyncio.run(fetch_picture("https://x.example/", get=bare))


def test_the_fetch_takes_extra_headers_but_keeps_its_own(monkeypatch):
    """watch_images._fetch(headers=...): the Referer goes along, the pinned
    Host and the honest User-Agent stay."""
    async def pinned(url):
        return url, "liquipedia.net", "liquipedia.net"
    monkeypatch.setattr(watch_images, "pinned_target", pinned)
    seen = {}

    class Transport(httpx.AsyncBaseTransport):
        # A streamed body, as the network gives it (_fetch reads it raw).
        async def handle_async_request(self, request):
            seen.update(request.headers)
            return httpx.Response(200, headers={"content-type": "image/png"}, stream=httpx.ByteStream(b"picture"))

    async def fetch():
        async with httpx.AsyncClient(transport=Transport()) as client:
            return await watch_images._fetch(client, PICTURE, {"image/png"}, 100, "image/*",
                                             headers={"Referer": PAGE, "Host": "evil.example"})
    assert asyncio.run(fetch())[1] == b"picture"
    assert seen["referer"] == PAGE and seen["host"] == "liquipedia.net"
    assert seen["user-agent"] == watch_images.USER_AGENT


def test_the_picture_lands_under_the_answer_with_its_source(store, monkeypatch, tmp_path):
    from app.services.agent_files import AgentFiles
    monkeypatch.setenv("AGENT_FILES_LOCAL_DIR", str(tmp_path))
    monkeypatch.delenv("AGENT_READ_SOURCES", raising=False)
    monkeypatch.setattr(agent_vm_tools, "sees_pictures", lambda model: True)
    picture, fetched = png(), []

    async def fetch(url, get=None):
        fetched.append(url)
        if "blocked" in url:
            raise ValueError("status_403")
        return picture, PICTURE if url == PAGE else url + "/logo.png", url
    monkeypatch.setattr(agent_web_images, "fetch_picture", fetch)
    blocked = "https://blocked.example/player"
    script = Audit(tool_steps=4, step_tools={step: "show_image" for step in range(4)},
                   step_args={0: {"url": PAGE, "caption": "Jeef at Lobby Legends"}, 1: {"url": PAGE},
                              2: {"url": FOUND}, 3: {"url": blocked}}, live={})
    script.live.update(anthropic=replies(script, "anthropic", go), openai=replies(script, "openai", go))
    loop = audit_loop(store, script)
    # No block of its own (2026-10-28): the description says what it does, and
    # the answer section that pictures in the Markdown do not show.
    assert "show_image" in loop.registry.tools and "PICTURES" not in loop.messages[0]["content"]
    assert "pictures in it are not shown" in prompt_defaults.AGENT_AUDIT_SYSTEM_PROMPT
    assert set(loop.registry.tools["show_image"].arguments.model_json_schema()["properties"]) == {"url", "caption"}
    events = list(loop.run())
    shown, again, found, failed = [json.loads(m["content"]) for m in loop.messages if m.get("role") == "tool"]
    assert shown["status"] == "shown" and shown["page"] == PAGE and shown["picture"] == PICTURE
    assert "do not embed or link it" in shown["note"]
    # The same address again is the same picture, fetched once.
    assert again["status"] == "shown" and "already under your answer" in again["note"]
    assert found["status"] == "shown"
    assert failed == {"status": "failed", "url": blocked, "reason": "No picture: the site answered HTTP 403.",
                      "note": "Do not claim the user sees it."}
    assert fetched == [PAGE, FOUND, blocked]
    # No gate round since 2026-10-29: the reviewers follow the fetch live.
    assert not getattr(script, "gate_searches", {})
    saved = AgentFiles(store.db).list(UID, loop.chat_id)
    assert [(file["kind"], file["turn_id"], file["mime"]) for file in saved] == [
        ("web_image", loop.turn_id, "image/webp")] * 2
    assert saved[0]["origin"] == {"source": "web", "url": PICTURE, "page": PAGE, "host": "liquipedia.net",
                                  "caption": "Jeef at Lobby Legends"}
    assert PAGE not in saved[0]["name"] and saved[0]["name"].endswith(".webp")
    assert len([e for e in events if e.get("type") == "resources"]) == 2
    # The reviewers read result and picture as the web's, not the VM's.
    logged = [entry for entry, _ in loop.work_log.entries_after(0)]
    assert {e["data"] for e in logged if e["kind"] == "tool" and e.get("name") == "show_image"} == {"web"}
    assert {e["data"] for e in logged if e["kind"] == "context" and e["seq"] > 3 and e.get("name") == "user"} == {"web"}
    # The agent sees what it showed, as data.
    pictures = [m for m in loop.messages if m.get("role") == "user" and isinstance(m.get("content"), list)]
    assert [m["content"][0]["text"] for m in pictures][:1] == [INTRO.format(url=PAGE)]
    # The activity names the site, or that none gave a picture (agent-activity.js pictureSummary).
    done = [e for e in events if e.get("type") == "activity" and e.get("kind") == "tool" and e.get("name") == "show_image"
            and e.get("status") == "succeeded"]
    assert [(e.get("host"), e.get("outcome")) for e in done] == [
        ("liquipedia.net", None), ("liquipedia.net", None), ("toureiffel.paris", None), (None, "failed")]


def test_without_audit_there_is_no_show_image(store):
    loop = audit_loop(store, Audit(), audit="off")
    assert "show_image" not in loop.registry.tools

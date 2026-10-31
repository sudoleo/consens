"""find_pictures and show_image (agent_web_images.py, since 2026-10-28): a
picture from the web under the agent's answer. The server fetches it (a
picture, or the preview picture a page names for itself), only bytes that
are a picture, encoded anew; the agent looks at it first (since 2026-10-29),
and only one it shows is kept in the chat's private store as the turn's
``web_image`` with its source. Asked for a picture of the best Hearthstone
Battlegrounds player on 2026-10-28, the agent could only say where one was;
asked for the face of Delay Sports on 2026-10-29, it put a placeholder and a
site's icon under the answer before it had seen them.
"""
import asyncio
import base64
import io
import json

import httpx
import pytest
from PIL import Image

from app.services import agent_vm_tools, agent_web_images, prompt_defaults, watch_images
from app.services.agent_web_images import INTRO, encode, fetch_picture, page_picture, page_words
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


def test_a_page_gives_its_title_and_the_pictures_alt_text_to_choose_by():
    html = ('<title>Jeef - Liquipedia</title><meta property="og:title" content="Jeef  at\nLobby Legends">'
            '<meta property="og:image:alt" content="Jeef on stage">')
    assert page_words(html) == {"page_title": "Jeef at Lobby Legends", "alt": "Jeef on stage"}
    assert page_words("<title>Only a title</title>") == {"page_title": "Only a title", "alt": ""}
    assert page_words('<meta name="twitter:title" content="' + "x" * 300 + '">')["page_title"] == "x" * 200


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
            page = f'<title>Jeef</title><meta property="og:image" content="{PICTURE}">'
            return url, page.encode(), "text/html", False
        return url, picture, "image/jpeg", False
    assert asyncio.run(fetch_picture(PAGE, get=get)) == (picture, PICTURE, PAGE, {"page_title": "Jeef"})
    assert seen == [(PAGE, ""), (PICTURE, PAGE)]

    async def direct(url, kinds, referer=""):
        return url, picture, "application/octet-stream", False
    # A picture's own address needs no page.
    assert asyncio.run(fetch_picture(PICTURE, get=direct)) == (picture, PICTURE, "", {})

    async def bare(url, kinds, referer=""):
        return url, b"<p>No picture here.</p>", "text/html", False
    with pytest.raises(ValueError, match="og:image"):
        asyncio.run(fetch_picture("https://x.example/", get=bare))


def test_find_pictures_fetches_no_more_addresses_at_once_than_the_dns_gate_leaves(monkeypatch):
    """Bug hunt 2026-10-30: six addresses side by side met the source DNS gate
    (four lookups, dns_busy beyond, source_documents.pinned_target); the fifth
    and sixth failed as "it could not be fetched", and a full gate let other
    users' lookups fail. Three at a time, like agent_source_evidence; each
    address still gets its own CALL_SECONDS once it starts."""
    running, peak = 0, 0

    async def fetch(url, get=None):
        nonlocal running, peak
        running += 1
        peak = max(peak, running)
        await asyncio.sleep(0.01)
        running -= 1
        return b"", url, "", {}
    monkeypatch.setattr(agent_web_images, "fetch_picture", fetch)
    urls = [f"https://site{index}.example/" for index in range(6)]
    results = asyncio.run(agent_web_images._fetch_all(urls))
    assert [result[1] for result in results] == urls
    assert peak == 3


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


def test_the_agent_looks_first_and_only_what_it_shows_lands_under_the_answer(store, monkeypatch, tmp_path):
    from app.services.agent_files import AgentFiles
    monkeypatch.setenv("AGENT_FILES_LOCAL_DIR", str(tmp_path))
    monkeypatch.delenv("AGENT_READ_SOURCES", raising=False)
    monkeypatch.setattr(agent_vm_tools, "sees_pictures", lambda model: True)
    large, small, fetched = png((2000, 1000)), png((70, 70), (200, 30, 30)), []

    async def fetch(url, get=None):
        fetched.append(url)
        if "blocked" in url:
            raise ValueError("status_403")
        if url == PAGE:
            return large, PICTURE, PAGE, {"page_title": "Jeef - Liquipedia"}
        return small, url + "/logo.png", url, {}
    monkeypatch.setattr(agent_web_images, "fetch_picture", fetch)
    blocked = "https://blocked.example/player"
    script = Audit(tool_steps=5, step_tools={0: "find_pictures", 1: "find_pictures", 2: "show_image",
                                             3: "show_image", 4: "show_image"},
                   step_args={0: {"urls": [PAGE, FOUND, blocked, PAGE]}, 1: {"urls": [PAGE]},
                              2: {"picture": "p1", "caption": "Jeef at Lobby Legends"}, 3: {"picture": "p1"},
                              4: {"picture": "p9"}}, live={})
    script.live.update(anthropic=replies(script, "anthropic", go), openai=replies(script, "openai", go))
    loop = audit_loop(store, script)
    # No block of their own (2026-10-28): the descriptions say what they do,
    # and the answer section that a picture shows only where the agent places
    # one it showed (2026-10-31).
    assert {"find_pictures", "show_image"} <= set(loop.registry.tools)
    assert "PICTURES" not in loop.messages[0]["content"]
    assert "a picture shows in it only where you place one you showed" in prompt_defaults.AGENT_AUDIT_SYSTEM_PROMPT
    assert "picture:<id>" in loop.registry.tools["show_image"].description
    assert set(loop.registry.tools["find_pictures"].arguments.model_json_schema()["properties"]) == {"urls"}
    assert set(loop.registry.tools["show_image"].arguments.model_json_schema()["properties"]) == {"picture", "caption"}
    events = list(loop.run())
    looked, again, shown, twice, unknown = [json.loads(m["content"]) for m in loop.messages if m.get("role") == "tool"]
    # Side by side, each address once; a blocking site costs only its own entry.
    assert fetched == [PAGE, FOUND, blocked]
    assert looked["pictures"] == [
        {"id": "p1", "page": PAGE, "picture": PICTURE, "width": agent_web_images.MAX_SIDE, "height": 800,
         "page_title": "Jeef - Liquipedia"},
        {"id": "p2", "page": FOUND, "picture": FOUND + "/logo.png", "width": 70, "height": 70},
        {"url": blocked, "status": "failed", "reason": "No picture: the site answered HTTP 403."}]
    assert looked["note"].startswith("The user sees none of these.") and "follow as images" in looked["note"]
    assert agent_web_images.UNTRUSTED_WORDS in looked["note"]
    # The same address again is the same picture, not fetched again.
    assert [entry["id"] for entry in again["pictures"]] == ["p1"]
    assert shown["status"] == "shown" and shown["page"] == PAGE and shown["picture"] == PICTURE
    # It names what the agent writes where the picture belongs in its text.
    assert shown["markdown"] == "![Jeef at Lobby Legends](picture:p1)"
    assert agent_web_images.PLACE_NOTE in shown["note"] and "do not link it" in shown["note"]
    assert twice["status"] == "shown" and "already shown" in twice["note"] and twice["markdown"] == shown["markdown"]
    assert "No picture p9 in this message" in unknown["error"]
    # Only the picture it showed is stored and announced; what it only looked at never is.
    saved = AgentFiles(store.db).list(UID, loop.chat_id)
    assert [(file["kind"], file["turn_id"], file["mime"]) for file in saved] == [
        ("web_image", loop.turn_id, "image/webp")]
    assert saved[0]["origin"] == {"source": "web", "url": PICTURE, "page": PAGE, "host": "liquipedia.net",
                                  "caption": "Jeef at Lobby Legends", "ref": "p1"}
    assert PAGE not in saved[0]["name"] and saved[0]["name"].endswith(".webp")
    assert len([e for e in events if e.get("type") == "resources"]) == 1
    # The agent sees what it looked at, as data and smaller: p1 and p2, then p1 again.
    pictures = [m for m in loop.messages if m.get("role") == "user" and isinstance(m.get("content"), list)]
    assert [m["content"][0]["text"] for m in pictures] == [
        INTRO.format(id="p1", url=PAGE), INTRO.format(id="p2", url=FOUND), INTRO.format(id="p1", url=PAGE)]
    seen = pictures[-1]["content"][1]["image_url"]["url"]
    with Image.open(io.BytesIO(base64.b64decode(seen.split(",", 1)[1]))) as image:
        assert max(image.size) == agent_web_images.LOOK_SIDE
    # The reviewers read results and pictures as the web's, not the VM's.
    logged = [entry for entry, _ in loop.work_log.entries_after(0)]
    assert {e["data"] for e in logged
            if e["kind"] == "tool" and e.get("name") in {"find_pictures", "show_image"}} == {"web"}
    assert {e["data"] for e in logged if e["kind"] == "context" and e["seq"] > 3 and e.get("name") == "user"} == {"web"}
    # The activity counts what it looked at and names the site it showed (agent-activity.js).
    done = [(e["name"], e.get("count"), e.get("host"), e.get("outcome")) for e in events
            if e.get("type") == "activity" and e.get("kind") == "tool" and e.get("status") == "succeeded"
            and e.get("name") in {"find_pictures", "show_image"}]
    assert done == [("find_pictures", 2, "liquipedia.net", None), ("find_pictures", 1, "liquipedia.net", None),
                    ("show_image", None, "liquipedia.net", None), ("show_image", None, "liquipedia.net", None)]


def test_the_place_of_a_picture_stays_one_markdown_image():
    assert agent_web_images.picture_markdown("p2", " A [weird]\n caption ") == "![A (weird) caption](picture:p2)"
    assert agent_web_images.picture_markdown("f1") == "![](picture:f1)"


def test_looking_has_a_bound_per_message(store, monkeypatch):
    monkeypatch.delenv("AGENT_READ_SOURCES", raising=False)
    monkeypatch.setattr(agent_web_images, "LOOKS_PER_MESSAGE", 2)

    async def fetch(url, get=None):
        return png(color=(60 * int(url[9]), 0, 0)), url + "/p.png", url, {}
    monkeypatch.setattr(agent_web_images, "fetch_picture", fetch)
    script = Audit(tool_steps=1, step_tools={0: "find_pictures"},
                   step_args={0: {"urls": [f"https://x{index}.example/" for index in range(3)]}}, live={})
    loop = audit_loop(store, script)
    list(loop.run())
    [result] = [json.loads(m["content"]) for m in loop.messages if m.get("role") == "tool"]
    assert [entry.get("id") for entry in result["pictures"]] == ["p1", "p2", None]
    assert result["pictures"][2]["reason"] == "No more than 2 pictures to look at per message."


def test_without_audit_there_is_no_show_image(store):
    loop = audit_loop(store, Audit(), audit="off")
    assert "show_image" not in loop.registry.tools

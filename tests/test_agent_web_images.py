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

from app.services import agent_vm_tools, agent_web_images, picture_search, prompt_defaults, watch_images
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


def test_the_picture_tools_come_only_with_page_reading(store, monkeypatch):
    # The server fetches a picture as it reads a page, within read_source's
    # bounds: without page reading (AGENT_READ_SOURCES=0) neither tool.
    monkeypatch.setenv("AGENT_READ_SOURCES", "0")
    loop = audit_loop(store, Audit())
    assert not {"read_source", "find_pictures", "show_image"} & set(loop.registry.tools)


# --- The image search (search_pictures, picture_search.py, since 2026-10-31) ---
# Max, 2026-10-31: ChatGPT shows image results as a collage to click through,
# its model hardly looks first. Brave's image search answers with pictures,
# each with its page and title, and the agent chooses by those.
PAGE_A, PIC_A = "https://www.rbb24.de/sport/delay-sports.html", "https://www.rbb24.de/img/nerlich.jpg"
PAGE_B, PIC_B = "https://www.fupa.net/player/elias-nerlich", "https://image.fupa.net/nerlich.jpeg"
PAGE_C, PIC_C = "https://blocked.example/team", "https://blocked.example/team.jpg"
COPY = "https://imgs.search.brave.com/copy-{}.jpg"


def brave_result(page, picture, title, copy="", width=1200, height=800):
    return {"type": "image_result", "title": title, "url": page, "source": "x",
            "thumbnail": {"src": copy, "width": 500, "height": 333},
            "properties": {"url": picture, "placeholder": copy, "width": width, "height": height}}


def test_brave_answers_become_pictures_with_their_pages():
    data = {"type": "images", "results": [
        brave_result(PAGE_A, PIC_A, "  Elias Nerlich\nvon Delay Sports ", COPY.format("a")),
        # The same picture from another page, one without a page, one with
        # neither picture nor copy, and an address with credentials: left out.
        brave_result(PAGE_B, PIC_A, "again"), brave_result("", PIC_B, "no page"),
        brave_result(PAGE_B, "", "nothing"), brave_result(PAGE_B, "https://u:p@x.example/p.jpg", "credentials"),
        # Without the original's address its copy stands in; without its size the copy's.
        {"title": "x" * 300, "url": PAGE_C, "thumbnail": {"src": COPY.format("c"), "width": 500, "height": 281},
         "properties": {}},
        "no result", brave_result(PAGE_B, PIC_B, "Elias Nerlich (FuPa)", COPY.format("b"))]}
    found = picture_search.pictures(data, 10)
    assert found == [
        {"picture": PIC_A, "thumbnail": COPY.format("a"), "page": PAGE_A, "title": "Elias Nerlich von Delay Sports",
         "width": 1200, "height": 800},
        {"picture": COPY.format("c"), "thumbnail": COPY.format("c"), "page": PAGE_C, "title": "x" * 200,
         "width": 500, "height": 281},
        {"picture": PIC_B, "thumbnail": COPY.format("b"), "page": PAGE_B, "title": "Elias Nerlich (FuPa)",
         "width": 1200, "height": 800}]
    assert len(picture_search.pictures(data, 2)) == 2
    assert picture_search.pictures({"results": "broken"}, 5) == picture_search.pictures([], 5) == []


def test_the_search_asks_brave_with_the_key_and_safe_search(monkeypatch):
    seen = {}

    def answer(request):
        seen.update(url=request.url, key=request.headers.get("x-subscription-token"))
        return httpx.Response(200, json={"results": [brave_result(PAGE_A, PIC_A, "Elias Nerlich")]})
    monkeypatch.setenv(picture_search.KEY_ENV, "test-key")
    found = picture_search.search("Delay Sports Elias Nerlich", 10, transport=httpx.MockTransport(answer))
    assert [entry["picture"] for entry in found] == [PIC_A]
    assert seen["key"] == "test-key"
    assert str(seen["url"]).startswith(picture_search.ENDPOINT)
    assert dict(seen["url"].params) == {"q": "Delay Sports Elias Nerlich", "count": str(picture_search.ASK),
                                        "safesearch": "strict"}
    refused = httpx.MockTransport(lambda request: httpx.Response(401, json={"error": "bad key"}))
    with pytest.raises(httpx.HTTPStatusError):
        picture_search.search("x", 10, transport=refused)


def test_the_picture_search_comes_only_with_a_key(store, monkeypatch):
    monkeypatch.delenv("AGENT_READ_SOURCES", raising=False)
    assert not picture_search.enabled()
    loop = audit_loop(store, Audit())
    assert "search_pictures" not in loop.registry.tools
    assert "search_pictures" not in loop.registry.tools["show_image"].description
    monkeypatch.setenv(picture_search.KEY_ENV, "test-key")
    assert picture_search.enabled()
    loop = audit_loop(store, Audit())
    assert "search_pictures" in loop.registry.tools
    assert set(loop.registry.tools["search_pictures"].arguments.model_json_schema()["properties"]) == {"query"}
    assert "search_pictures" in loop.registry.tools["show_image"].description
    monkeypatch.setenv(picture_search.ENABLED_ENV, "0")
    assert "search_pictures" not in audit_loop(store, Audit()).registry.tools


def test_a_found_picture_comes_from_its_site_else_as_braves_copy():
    picture, asked = png((900, 600)), []

    async def get(url, referer=""):
        asked.append((url, referer))
        if "blocked" in url:
            raise ValueError("status_403")
        return url, picture, "image/jpeg", False
    encoded = asyncio.run(agent_web_images.fetch_found(PIC_A, COPY.format("a"), PAGE_A, get=get))
    assert encoded[1:] == ("image/webp", 900, 600) and asked == [(PIC_A, PAGE_A)]
    asked.clear()
    encoded = asyncio.run(agent_web_images.fetch_found(PIC_C, COPY.format("c"), PAGE_C, get=get))
    assert encoded[2:] == (900, 600) and asked == [(PIC_C, PAGE_C), (COPY.format("c"), "")]
    # Only the copy (no original address): asked once, with its page.
    asked.clear()
    with pytest.raises(ValueError, match="status_403"):
        asyncio.run(agent_web_images.fetch_found(PIC_C, PIC_C, PAGE_C, get=get))
    assert asked == [(PIC_C, PAGE_C)]


def test_the_agent_searches_pictures_and_shows_its_picks_without_looking(store, monkeypatch, tmp_path):
    from app.services.agent_files import AgentFiles
    monkeypatch.setenv("AGENT_FILES_LOCAL_DIR", str(tmp_path))
    monkeypatch.delenv("AGENT_READ_SOURCES", raising=False)
    monkeypatch.setenv(picture_search.KEY_ENV, "test-key")
    monkeypatch.setattr(agent_vm_tools, "sees_pictures", lambda model: True)
    queries, fetched = [], []

    def search(query, count):
        queries.append((query, count))
        return [{"picture": PIC_A, "thumbnail": COPY.format("a"), "page": PAGE_A,
                 "title": "Elias Nerlich von Delay Sports", "width": 1200, "height": 800},
                {"picture": PIC_B, "thumbnail": COPY.format("b"), "page": PAGE_B, "title": "", "width": None,
                 "height": None},
                {"picture": PIC_C, "thumbnail": "", "page": PAGE_C, "title": "Team", "width": 640, "height": 480}]

    async def fetch(picture, copy, page, get=None):
        fetched.append(picture)
        if "blocked" in picture:
            raise ValueError("status_403")
        # In the background the DNS gate may be full once: the fetch runs again.
        if picture == PIC_B and fetched.count(PIC_B) == 1:
            raise ValueError("dns_busy")
        return encode(png((900, 600), (len(fetched) * 40, 0, 0)))
    monkeypatch.setattr(picture_search, "search", search)
    monkeypatch.setattr(agent_web_images, "fetch_found", fetch)
    script = Audit(tool_steps=5, step_tools={0: "search_pictures", 1: "show_image", 2: "show_image",
                                             3: "find_pictures", 4: "show_image"},
                   step_args={0: {"query": "  Delay Sports\n Elias Nerlich "},
                              1: {"picture": "p1", "caption": "Elias Nerlich"}, 2: {"picture": "p3"},
                              3: {"urls": [PIC_B]}, 4: {"picture": "p2", "caption": "Auf dem Platz"}}, live={})
    loop = audit_loop(store, script)
    events = list(loop.run())
    found, shown, failed, looked, second = [json.loads(m["content"]) for m in loop.messages if m.get("role") == "tool"]
    assert queries == [("Delay Sports Elias Nerlich", agent_web_images.FOUND_PER_SEARCH)]
    # Ids, pages, the pages' own titles and sizes: words to choose by.
    assert found["pictures"] == [
        {"id": "p1", "page": PAGE_A, "picture": PIC_A, "width": 1200, "height": 800,
         "page_title": "Elias Nerlich von Delay Sports"},
        {"id": "p2", "page": PAGE_B, "picture": PIC_B},
        {"id": "p3", "page": PAGE_C, "picture": PIC_C, "width": 640, "height": 480, "page_title": "Team"}]
    assert "show_image" in found["note"] and agent_web_images.UNTRUSTED_WORDS in found["note"]
    # Shown: stored and placed like a picture it looked at; its size as fetched.
    assert shown["status"] == "shown" and (shown["width"], shown["height"]) == (900, 600)
    assert shown["markdown"] == "![Elias Nerlich](picture:p1)"
    assert "gallery" in shown["note"]
    # A site that gives neither the picture nor a copy: a result, not an error.
    assert failed == {"picture": "p3", "status": "failed", "reason": "No picture: the site answered HTTP 403.",
                      "note": "The user does not see it."}
    # Looking at a found picture keeps its id and its fetch.
    assert [entry["id"] for entry in looked["pictures"]] == ["p2"]
    assert second["status"] == "shown" and second["markdown"] == "![Auf dem Platz](picture:p2)"
    # A full DNS gate is tried again, a site's refusal is its answer.
    assert sorted(fetched) == sorted([PIC_A, PIC_B, PIC_B, PIC_C])
    # The agent sees only the picture it asked to look at: the search costs no image tokens.
    pictures = [m for m in loop.messages if m.get("role") == "user" and isinstance(m.get("content"), list)]
    assert [m["content"][0]["text"] for m in pictures] == [INTRO.format(id="p2", url=PAGE_B)]
    saved = AgentFiles(store.db).list(UID, loop.chat_id)
    assert sorted((file["origin"]["ref"], file["origin"]["url"], file["origin"]["caption"]) for file in saved) == [
        ("p1", PIC_A, "Elias Nerlich"), ("p2", PIC_B, "Auf dem Platz")]
    done = [(e["name"], e.get("count"), e.get("host"), e.get("outcome")) for e in events
            if e.get("type") == "activity" and e.get("kind") == "tool" and e.get("status") == "succeeded"
            and e.get("name") in {"search_pictures", "show_image"}]
    assert done == [("search_pictures", 3, None, None), ("show_image", None, "rbb24.de", None),
                    ("show_image", None, None, "failed"), ("show_image", None, "fupa.net", None)]
    logged = [entry for entry, _ in loop.work_log.entries_after(0)]
    assert {e["data"] for e in logged if e["kind"] == "tool" and e.get("name") == "search_pictures"} == {"web"}
    # Fetches still waiting end with the run.
    assert loop.image_tools._fetcher is None


def test_the_picture_search_has_a_bound_and_says_when_it_is_down(store, monkeypatch):
    monkeypatch.delenv("AGENT_READ_SOURCES", raising=False)
    monkeypatch.setenv(picture_search.KEY_ENV, "test-key")
    monkeypatch.setattr(agent_web_images, "SEARCHES_PER_MESSAGE", 2)
    answers = iter([[], httpx.ConnectError("down"), []])

    def search(query, count):
        answer = next(answers)
        if isinstance(answer, Exception):
            raise answer
        return answer
    monkeypatch.setattr(picture_search, "search", search)
    script = Audit(tool_steps=4, step_tools={index: "search_pictures" for index in range(4)},
                   step_args={index: {"query": f"Oologah Oklahoma {index}"} for index in range(4)}, live={})
    loop = audit_loop(store, script)
    list(loop.run())
    empty, down, again, over = [json.loads(m["content"]) for m in loop.messages if m.get("role") == "tool"]
    assert empty == again == {"pictures": [], "note": "The search found no pictures. Do not claim the user sees one."}
    # A search that did not answer is none of the message's searches.
    assert "not available right now" in down["error"]
    assert "No more than 2 picture searches per message" in over["error"]


def test_the_same_picture_found_twice_shows_once_with_its_page(store, monkeypatch, tmp_path):
    """Review 2026-10-31: a picture looked at by its own address, then
    found by the image search, keeps its id and gains the search's page; the
    same picture under two addresses shows once."""
    from app.services.agent_files import AgentFiles
    monkeypatch.setenv("AGENT_FILES_LOCAL_DIR", str(tmp_path))
    monkeypatch.delenv("AGENT_READ_SOURCES", raising=False)
    monkeypatch.setenv(picture_search.KEY_ENV, "test-key")
    same = png((900, 600), (10, 20, 30))
    monkeypatch.setattr(picture_search, "search", lambda query, count: [
        {"picture": PIC_A, "thumbnail": "", "page": PAGE_A, "title": "Elias Nerlich", "width": 900, "height": 600},
        {"picture": PIC_B, "thumbnail": "", "page": PAGE_B, "title": "", "width": 900, "height": 600}])

    async def fetch_picture(url, get=None):
        return same, url, "", {}

    async def fetch(picture, copy, page, get=None):
        return encode(same)
    monkeypatch.setattr(agent_web_images, "fetch_picture", fetch_picture)
    monkeypatch.setattr(agent_web_images, "fetch_found", fetch)
    script = Audit(tool_steps=4, step_tools={0: "find_pictures", 1: "search_pictures", 2: "show_image", 3: "show_image"},
                   step_args={0: {"urls": [PIC_A]}, 1: {"query": "Elias Nerlich"}, 2: {"picture": "p1"},
                              3: {"picture": "p2"}}, live={})
    loop = audit_loop(store, script)
    list(loop.run())
    looked, found, shown, twice = [json.loads(m["content"]) for m in loop.messages if m.get("role") == "tool"]
    assert looked["pictures"][0]["page"] == PIC_A
    assert [(entry["id"], entry["page"]) for entry in found["pictures"]] == [("p1", PAGE_A), ("p2", PAGE_B)]
    assert shown["status"] == "shown" and shown["page"] == PAGE_A
    assert twice["markdown"] == shown["markdown"] and "same picture as p1" in twice["note"]
    assert [file["origin"]["ref"] for file in AgentFiles(store.db).list(UID, loop.chat_id)] == ["p1"]

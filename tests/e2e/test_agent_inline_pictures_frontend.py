"""Pictures in the answer text (2026-10-31): built /app, isolated fixtures, no paid calls.

The agent places a picture it showed with ![caption](picture:p1)
(agent_web_images.picture_markdown); the app puts the stored picture there
(markdown-stream.js .md-picture, agent-workspace.js placePictures). A picture
it did not place stands under the text once the run is over.
"""
import io
import json

import pytest
from PIL import Image, ImageDraw, ImageFont
from playwright.sync_api import expect
from test_phase4_frontend import phase4_server, _real_firebase_page, _json
from test_agent_chat_frontend import CATALOG, _choose_mode, _snapshot


def _png(color):
    buffer = io.BytesIO()
    Image.new("RGB", (640, 360), color).save(buffer, "PNG")
    return buffer.getvalue()


def _grid(tint):
    """A picture with detail to zoom into: labelled squares, too small to
    read fitted."""
    image = Image.new("RGB", (1280, 720), (246, 246, 242))
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=22)
    for column in range(16):
        for row in range(9):
            x, y = column * 80, row * 80
            if (column + row) % 2:
                draw.rectangle([x, y, x + 79, y + 79], fill=tint)
            draw.text((x + 10, y + 10), f"{chr(65 + row)}{column + 1}", fill=(30, 40, 36), font=font)
    buffer = io.BytesIO()
    image.save(buffer, "PNG")
    return buffer.getvalue()


# The picture in the viewer: its transform, its box and its frame's, and the
# page's own zoom (image-zoom.js, attachments.js zoomable).
ZOOM = """() => {
  const body = document.getElementById('attachmentViewerBody');
  const img = body.querySelector('.attachment-viewer-image');
  const matrix = new DOMMatrix(getComputedStyle(img).transform);
  const box = img.getBoundingClientRect(), frame = body.getBoundingClientRect();
  const rect = r => ({left: r.left, top: r.top, right: r.right, bottom: r.bottom, width: r.width, height: r.height});
  return {scale: matrix.a, x: matrix.e, y: matrix.f, box: rect(box), frame: rect(frame),
    zoomed: body.classList.contains('is-zoomed'),
    actions: getComputedStyle(body.querySelector('.attachment-viewer-actions')).visibility,
    page: window.visualViewport ? visualViewport.scale : 1, wheel: window.__wheelPrevented ?? null};
}"""
SETTLED = "() => !document.querySelector('#attachmentViewerBody .attachment-viewer-image').classList.contains('is-settling')"


def _touch(cdp, page, fingers, steps=8):
    """Fingers from their start to their end: [((x0, y0), (x1, y1)), ...]."""
    at = lambda share: [{"x": x0 + (x1 - x0) * share, "y": y0 + (y1 - y0) * share, "id": index + 1}
                        for index, ((x0, y0), (x1, y1)) in enumerate(fingers)]
    cdp.send("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": at(0)})
    for step in range(1, steps + 1):
        cdp.send("Input.dispatchTouchEvent", {"type": "touchMove", "touchPoints": at(step / steps)})
        page.wait_for_timeout(16)
    cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})


@pytest.mark.parametrize("width,dark", [(1440, False), (390, True)])
def test_a_placed_picture_stands_in_the_text_and_the_others_under_it_after_the_run(browser, phase4_server, width, dark):
    context, page = _real_firebase_page(browser, phase4_server)
    chat, turn = "a" * 32, "b" * 32
    web = lambda letter, ref, caption: {
        "id": letter * 32, "name": f"picture-{letter}.webp", "mime": "image/png", "size": 4000, "status": "ready",
        "kind": "web_image", "turn_id": turn, "expires_at": "2099-10-29T10:00:00Z",
        "origin": {"source": "web", "url": f"https://example.org/{letter}.jpg", "page": "https://example.org/tower",
                   "host": "example.org", "caption": caption, "ref": ref}}
    files = [web("c", "p1", "The tower at night"), web("d", "p2", "A map of the city")]
    pictures = {files[0]["id"]: _png((40, 90, 160)), files[1]["id"]: _png((160, 120, 40))}
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    try:
        page.set_viewport_size({"width": width, "height": 900})
        page.route("**/user_status", lambda r: _json(r, {"tier": "pro", "is_pro": True, "agent_access": True}))
        page.route("**/agent/models", lambda r: _json(r, CATALOG))
        page.route("**/chats", lambda r: _json(r, {"chat": {"id": chat, "execution_mode": "agent"}}))
        page.route(f"**/agent/chats/{chat}/turns/{turn}/agents", lambda r: _json(r, {"agents": [], "status": "running"}))
        page.route(f"**/agent/chats/{chat}/files", lambda r: _json(r, {"files": files}))
        page.route(f"**/agent/chats/{chat}/files/*", lambda r: r.fulfill(
            status=200, content_type="image/png", body=pictures[r.request.url.split("/files/")[1].split("?")[0]]))
        page.evaluate("async () => { await window.__switchE2EUser('account-a'); }")
        _choose_mode(page, "agent")
        page.evaluate("dark => { document.documentElement.classList.toggle('dark-mode', dark); document.body.classList.toggle('dark-mode', dark); }", dark)
        # A real ReadableStream, pushed step by step, so the stream renderer
        # sees the picture's line arrive in pieces.
        page.evaluate("""data => {
          const fetch = window.fetch;
          window.fetch = (url, options) => {
            if (String(url) !== '/agent') return fetch(url, options);
            const request = JSON.parse(options.body);
            return Promise.resolve(new Response(new ReadableStream({start(controller) {
              window.__agentPush = (type, event) => controller.enqueue(new TextEncoder().encode(`event: ${type}\\ndata: ${JSON.stringify(event)}\\n\\n`));
              window.__agentFinish = text => {
                window.__agentPush('final', {chat_id: data.chat, turn_id: data.turn, response: text,
                  turn: {id: data.turn, execution_mode: 'agent', status: 'completed', consensus: text,
                    agent_settings: {policy: {delegation: true}}},
                  bookmark_meta: {id: request.bookmark_id, title: 'The tower', query: 'Show me the tower', mode: 'Agent', has_consensus: true}});
                controller.close();
              };
              window.__agentPush('accepted', {chat_id: data.chat, turn_id: data.turn});
            }}), {headers: {'Content-Type': 'text/event-stream'}}));
          };
        }""", {"chat": chat, "turn": turn})
        page.locator("#questionInput").fill("Show me the tower")
        page.locator("#sendButton").click()
        page.wait_for_function("() => typeof window.__agentPush === 'function'")
        page.evaluate("() => window.__agentPush('resources', {files: true})")
        body = page.locator("#agentAnswerBody")
        intro = "The tower is 330 metres tall and was finished in 1889.\n\n"
        page.evaluate("text => window.__agentPush('delta', {text})", intro + "![The tower at ni")
        expect(body).to_contain_text("finished in 1889")
        # Half a picture's line shows no raw marks.
        page.wait_for_timeout(400)
        assert "![" not in body.inner_text()
        rest = "ght](picture:p1)\n\nAt night it is lit for five minutes every hour.\n\n"
        page.evaluate("text => window.__agentPush('delta', {text})", rest)
        figure = body.locator('.md-picture[data-picture="p1"] .agent-vm-picture')
        expect(figure).to_be_visible()
        expect(figure.locator("img")).to_have_attribute("alt", "The tower at night")
        page.wait_for_function("""() => { const img = document.querySelector('#agentAnswerBody .md-picture img');
          return img && img.complete && img.naturalWidth === 640; }""")
        # In its place between the two paragraphs, within the answer's width.
        boxes = page.evaluate("""() => {
          const body = document.getElementById('agentAnswerBody');
          const [first, second] = [...body.querySelectorAll(':scope > p')];
          const picture = body.querySelector('.md-picture-line').getBoundingClientRect();
          return {first: first.getBoundingClientRect().bottom, second: second.getBoundingClientRect().top,
                  top: picture.top, bottom: picture.bottom, left: picture.left, right: picture.right,
                  bodyLeft: body.getBoundingClientRect().left, bodyRight: body.getBoundingClientRect().right};
        }""")
        assert boxes["first"] <= boxes["top"] and boxes["bottom"] <= boxes["second"]
        assert boxes["bodyLeft"] - 1 <= boxes["left"] and boxes["right"] <= boxes["bodyRight"] + 1
        # The picture it did not place waits while the answer is written.
        assert not page.locator(".agent-answer-pictures:visible").count()
        text = intro + "![The tower at night](picture:p1)\n\nAt night it is lit for five minutes every hour."
        placed = figure.element_handle()
        page.evaluate("text => window.__agentFinish(text)", text)
        page.wait_for_function("() => App.runRegistry.visible()?.status === 'succeeded'")
        # The full render keeps the same picture in its place; the other now stands under the text.
        slot = page.locator(".agent-answer-pictures")
        expect(slot).to_be_visible()
        expect(slot.locator(".agent-file-name")).to_have_text(["A map of the city"])
        assert page.evaluate("el => el.isConnected && !!el.closest('.md-picture[data-picture=\"p1\"]')", placed)
        assert "picture:" not in body.inner_text()
        assert page.evaluate("() => document.documentElement.scrollWidth <= window.innerWidth + 1")
        # The activity panel stays closed until its icon is clicked (2026-10-31).
        assert not page.locator("#agentSidebar:visible").count()
        body.scroll_into_view_if_needed()
        _snapshot(page, f"agent-inline-picture-{width}-{'dark' if dark else 'light'}")
        assert errors == []
    finally:
        context.close()


@pytest.mark.parametrize("width,dark", [(1440, False), (390, True)])
def test_a_picture_in_the_viewer_zooms_about_the_finger_or_cursor_and_never_the_page(browser, phase4_server, width, dark):
    """2026-11-02, Max: zoom into a picture's preview, Apple-like and without
    a toolbar (image-zoom.js): Ctrl + wheel or a pinch about the point under
    it, a double click or tap toggles, an enlarged picture drags to its edges
    and a swipe does not page it, + / - / 0, and the page's own zoom stays."""
    phone = width < 600
    context, page = _real_firebase_page(browser, phase4_server, has_touch=phone)
    chat, turn = "a" * 32, "b" * 32
    tints = {"c": (214, 230, 222), "d": (230, 222, 206)}
    files = [{"id": letter * 32, "name": f"chart-{letter}.webp", "mime": "image/png", "size": 40000, "status": "ready",
              "kind": "web_image", "turn_id": turn, "expires_at": "2099-10-29T10:00:00Z",
              "origin": {"source": "web", "url": f"https://site-{letter}.example/{letter}.png",
                         "page": f"https://site-{letter}.example/page", "host": f"site-{letter}.example",
                         "caption": f"Chart {letter}", "ref": f"p{index + 1}"}}
             for index, letter in enumerate(tints)]
    pictures = {file["id"]: _grid(tints[file["name"][6]]) for file in files}
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    try:
        page.set_viewport_size({"width": width, "height": 900})
        page.route("**/user_status", lambda r: _json(r, {"tier": "pro", "is_pro": True, "agent_access": True}))
        page.route("**/agent/models", lambda r: _json(r, CATALOG))
        page.route("**/chats", lambda r: _json(r, {"chat": {"id": chat, "execution_mode": "agent"}}))
        page.route(f"**/agent/chats/{chat}/turns/{turn}/agents", lambda r: _json(r, {"agents": [], "status": "running"}))
        page.route(f"**/agent/chats/{chat}/files", lambda r: _json(r, {"files": files}))
        page.route(f"**/agent/chats/{chat}/files/*", lambda r: r.fulfill(
            status=200, content_type="image/png", body=pictures[r.request.url.split("/files/")[1].split("?")[0]]))
        page.evaluate("async () => { await window.__switchE2EUser('account-a'); }")
        _choose_mode(page, "agent")
        page.evaluate("dark => { document.documentElement.classList.toggle('dark-mode', dark); document.body.classList.toggle('dark-mode', dark); }", dark)
        page.evaluate("""data => {
          const fetch = window.fetch;
          window.fetch = (url, options) => {
            if (String(url) !== '/agent') return fetch(url, options);
            const request = JSON.parse(options.body);
            return Promise.resolve(new Response(new ReadableStream({start(controller) {
              const push = (type, event) => controller.enqueue(new TextEncoder().encode(`event: ${type}\\ndata: ${JSON.stringify(event)}\\n\\n`));
              push('accepted', {chat_id: data.chat, turn_id: data.turn});
              push('resources', {files: true});
              push('final', {chat_id: data.chat, turn_id: data.turn, response: data.text,
                turn: {id: data.turn, execution_mode: 'agent', status: 'completed', consensus: data.text,
                  agent_settings: {policy: {delegation: true}}},
                bookmark_meta: {id: request.bookmark_id, title: 'Charts', query: 'Show me the charts', mode: 'Agent', has_consensus: true}});
              controller.close();
            }}), {headers: {'Content-Type': 'text/event-stream'}}));
          };
          // Whether the app took the last wheel from the browser (Ctrl + wheel is the page's zoom).
          window.addEventListener('wheel', event => { window.__wheelPrevented = event.defaultPrevented; });
        }""", {"chat": chat, "turn": turn, "text": "Two charts side by side.\n\n"
               "![Chart c](picture:p1) ![Chart d](picture:p2)\n\nBoth are from the same survey."})
        page.locator("#questionInput").fill("Show me the charts")
        page.locator("#sendButton").click()
        page.wait_for_function("() => App.runRegistry.visible()?.status === 'succeeded'")
        answer = page.locator("#agentAnswerBody")
        answer.locator('.md-picture[data-picture="p1"] .agent-vm-picture-open').click()
        viewer = page.locator("#attachmentViewerModal")
        count = page.locator("#attachmentViewerCount")
        expect(viewer).to_be_visible()
        expect(count).to_have_text("1 / 2")
        page.wait_for_function("""() => {
          const img = document.querySelector('#attachmentViewerBody .attachment-viewer-image');
          return img && img.complete && img.naturalWidth === 1280
            && !document.getElementById('attachmentViewerModal').getAnimations({subtree: true}).length;
        }""")
        fitted = page.evaluate(ZOOM)
        assert fitted["scale"] == 1 and not fitted["zoomed"] and fitted["actions"] == "visible"
        box = fitted["box"]
        if not phone:
            # Ctrl + wheel (a trackpad pinch) about the cursor; the browser keeps its zoom.
            at = (box["left"] + box["width"] * 0.3, box["top"] + box["height"] * 0.4)
            page.mouse.move(*at)
            page.keyboard.down("Control")
            for _ in range(3):
                page.mouse.wheel(0, -100)
            page.keyboard.up("Control")
            zoomed = page.evaluate(ZOOM)
            assert zoomed["wheel"] is True and zoomed["zoomed"] and 3.2 < zoomed["scale"] < 3.4
            # The point under the cursor stayed under it.
            assert abs((at[0] - zoomed["box"]["left"]) / zoomed["box"]["width"] - 0.3) < 0.003
            assert abs((at[1] - zoomed["box"]["top"]) / zoomed["box"]["height"] - 0.4) < 0.003
            page.wait_for_function("() => getComputedStyle(document.querySelector('.attachment-viewer-actions')).visibility === 'hidden'")
            _snapshot(page, f"agent-picture-zoomed-{width}-{'dark' if dark else 'light'}")
            # Dragged far right and down it stops at its top left corner: no gap.
            page.mouse.down()
            page.mouse.move(at[0] + 1500, at[1] + 1500, steps=6)
            page.mouse.up()
            dragged = page.evaluate(ZOOM)
            assert abs(dragged["box"]["left"] - dragged["frame"]["left"]) < 1
            assert abs(dragged["box"]["top"] - dragged["frame"]["top"]) < 1
            expect(count).to_have_text("1 / 2")
            # A double click fits it again, + zooms about the middle, 0 fits.
            page.mouse.dblclick(*at)
            page.wait_for_function(SETTLED)
            back = page.evaluate(ZOOM)
            assert back["scale"] == 1 and not back["zoomed"] and back["actions"] == "visible"
            page.keyboard.press("+")
            page.wait_for_function(SETTLED)
            assert abs(page.evaluate(ZOOM)["scale"] - 1.6) < 0.01
            page.keyboard.press("0")
            page.wait_for_function(SETTLED)
            assert page.evaluate(ZOOM)["scale"] == 1
            page.mouse.dblclick(*at)
            page.wait_for_function(SETTLED)
            assert abs(page.evaluate(ZOOM)["scale"] - 2.5) < 0.01
        else:
            cdp = context.new_cdp_session(page)
            x, y = box["left"] + box["width"] / 2, box["top"] + box["height"] / 2
            # Two fingers three times as far apart: the picture zooms, not the page.
            _touch(cdp, page, [((x - 30, y), (x - 90, y)), ((x + 30, y), (x + 90, y))])
            pinched = page.evaluate(ZOOM)
            assert pinched["page"] == 1 and pinched["zoomed"] and abs(pinched["scale"] - 3) < 0.05
            # The middle stayed in the middle.
            assert abs((pinched["box"]["left"] + pinched["box"]["right"]) / 2 - x) < 2
            _snapshot(page, f"agent-picture-zoomed-{width}-{'dark' if dark else 'light'}")
            # One finger drags it; a swipe of an enlarged picture does not page.
            _touch(cdp, page, [((x, y), (x - 200, y))])
            dragged = page.evaluate(ZOOM)
            assert abs(dragged["x"] - (pinched["x"] - 200)) < 2
            expect(count).to_have_text("1 / 2")
            # A double tap fits it again; fitted, a swipe pages.
            page.touchscreen.tap(x, y)
            page.touchscreen.tap(x, y)
            page.wait_for_function(SETTLED)
            back = page.evaluate(ZOOM)
            assert back["scale"] == 1 and not back["zoomed"] and back["page"] == 1
            # On the picture, clear of the arrows over its edges.
            _touch(cdp, page, [((x + 80, y), (x - 80, y))])
            expect(count).to_have_text("2 / 2")
            page.wait_for_function("() => document.querySelector('#attachmentViewerBody .attachment-viewer-image')?.complete")
            page.touchscreen.tap(x, y)
            page.touchscreen.tap(x, y)
            page.wait_for_function(SETTLED)
            assert abs(page.evaluate(ZOOM)["scale"] - 2.5) < 0.01
        # Closing lets go: the picture opens fitted again.
        page.keyboard.press("Escape")
        expect(viewer).to_be_hidden()
        answer.locator('.md-picture[data-picture="p1"] .agent-vm-picture-open').click()
        expect(viewer).to_be_visible()
        page.wait_for_function("() => document.querySelector('#attachmentViewerBody .attachment-viewer-image')?.complete")
        again = page.evaluate(ZOOM)
        assert again["scale"] == 1 and not again["zoomed"]
        assert errors == []
    finally:
        context.close()


@pytest.mark.parametrize("width,dark", [(1440, False), (390, True)])
def test_pictures_on_one_line_are_a_collage_the_viewer_pages_through(browser, phase4_server, width, dark):
    """2026-10-31, Max: ChatGPT's collage to click through. One large picture,
    two beside it, "+1" for the fourth; a click opens the viewer, whose arrows
    and keys page through the line (agent-workspace.js markGalleries,
    attachments.js pageGallery)."""
    context, page = _real_firebase_page(browser, phase4_server)
    chat, turn = "a" * 32, "b" * 32
    colors = {"c": (40, 90, 160), "d": (160, 120, 40), "e": (60, 140, 90), "f": (150, 60, 90)}
    files = [{"id": letter * 32, "name": f"picture-{letter}.webp", "mime": "image/png", "size": 4000, "status": "ready",
              "kind": "web_image", "turn_id": turn, "expires_at": "2099-10-29T10:00:00Z",
              "origin": {"source": "web", "url": f"https://site-{letter}.example/{letter}.jpg",
                         "page": f"https://site-{letter}.example/page", "host": f"site-{letter}.example",
                         "caption": f"Picture {letter}", "ref": f"p{index + 1}"}}
             for index, letter in enumerate(colors)]
    pictures = {file["id"]: _png(colors[file["name"][8]]) for file in files}
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    try:
        page.set_viewport_size({"width": width, "height": 900})
        page.route("**/user_status", lambda r: _json(r, {"tier": "pro", "is_pro": True, "agent_access": True}))
        page.route("**/agent/models", lambda r: _json(r, CATALOG))
        page.route("**/chats", lambda r: _json(r, {"chat": {"id": chat, "execution_mode": "agent"}}))
        page.route(f"**/agent/chats/{chat}/turns/{turn}/agents", lambda r: _json(r, {"agents": [], "status": "running"}))
        page.route(f"**/agent/chats/{chat}/files", lambda r: _json(r, {"files": files}))
        page.route(f"**/agent/chats/{chat}/files/*", lambda r: r.fulfill(
            status=200, content_type="image/png", body=pictures[r.request.url.split("/files/")[1].split("?")[0]]))
        page.evaluate("async () => { await window.__switchE2EUser('account-a'); }")
        _choose_mode(page, "agent")
        page.evaluate("dark => { document.documentElement.classList.toggle('dark-mode', dark); document.body.classList.toggle('dark-mode', dark); }", dark)
        page.evaluate("""data => {
          const fetch = window.fetch;
          window.fetch = (url, options) => {
            if (String(url) !== '/agent') return fetch(url, options);
            const request = JSON.parse(options.body);
            return Promise.resolve(new Response(new ReadableStream({start(controller) {
              const push = (type, event) => controller.enqueue(new TextEncoder().encode(`event: ${type}\ndata: ${JSON.stringify(event)}\n\n`));
              push('accepted', {chat_id: data.chat, turn_id: data.turn});
              push('resources', {files: true});
              push('final', {chat_id: data.chat, turn_id: data.turn, response: data.text,
                turn: {id: data.turn, execution_mode: 'agent', status: 'completed', consensus: data.text,
                  agent_settings: {policy: {delegation: true}}},
                bookmark_meta: {id: request.bookmark_id, title: 'Delay Sports', query: 'Show me Delay Sports', mode: 'Agent', has_consensus: true}});
              controller.close();
            }}), {headers: {'Content-Type': 'text/event-stream'}}));
          };
        }""", {"chat": chat, "turn": turn, "text": "Delay Sports is a football club from Berlin.\n\n"
               "![Picture c](picture:p1) ![Picture d](picture:p2) ![Picture e](picture:p3) ![Picture f](picture:p4)\n\n"
               "It plays in the Berlin-Liga."})
        page.locator("#questionInput").fill("Show me Delay Sports")
        page.locator("#sendButton").click()
        page.wait_for_function("() => App.runRegistry.visible()?.status === 'succeeded'")
        page.wait_for_function("""() => [...document.querySelectorAll('#agentAnswerBody .md-picture-line img')]
          .filter(img => img.complete && img.naturalWidth === 640).length === 4""")
        boxes = page.evaluate("""() => {
          const body = document.getElementById('agentAnswerBody').getBoundingClientRect();
          const line = document.querySelector('#agentAnswerBody .md-picture-line').getBoundingClientRect();
          const tiles = [...document.querySelectorAll('#agentAnswerBody .md-picture-line > .md-picture')].map(slot => {
            const box = slot.getBoundingClientRect();
            return {left: box.left, right: box.right, top: box.top, bottom: box.bottom, shown: box.width > 0};
          });
          const more = getComputedStyle(document.querySelector('[data-gallery-more]'), '::after').content;
          return {body: {left: body.left, right: body.right}, line: {top: line.top, bottom: line.bottom}, tiles, more};
        }""")
        lead, beside, third, fourth = boxes["tiles"]
        # One large on the left over the line's height, two stacked beside it, the fourth behind "+1".
        assert abs(lead["top"] - boxes["line"]["top"]) < 1 and abs(lead["bottom"] - boxes["line"]["bottom"]) < 1
        assert lead["right"] < beside["left"] and abs(beside["left"] - third["left"]) < 1
        assert beside["bottom"] < third["top"] and (lead["right"] - lead["left"]) > (beside["right"] - beside["left"])
        assert not fourth["shown"] and boxes["more"] == '"+1"'
        assert boxes["body"]["left"] - 1 <= lead["left"] and third["right"] <= boxes["body"]["right"] + 1
        assert page.evaluate("() => document.documentElement.scrollWidth <= window.innerWidth + 1")
        body = page.locator("#agentAnswerBody")
        body.scroll_into_view_if_needed()
        _snapshot(page, f"agent-picture-collage-{width}-{'dark' if dark else 'light'}")
        # The viewer opens on the clicked picture and pages through the line.
        body.locator('.md-picture[data-picture="p2"] .agent-vm-picture-open').click()
        viewer = page.locator("#attachmentViewerModal")
        expect(viewer).to_be_visible()
        expect(page.locator("#attachmentViewerTitle")).to_have_text("Picture d")
        expect(page.locator("#attachmentViewerCount")).to_have_text("2 / 4")
        expect(viewer.locator("a.attachment-viewer-source")).to_have_text("site-d.example")
        page.locator("#attachmentViewerNext").click()
        expect(page.locator("#attachmentViewerCount")).to_have_text("3 / 4")
        page.keyboard.press("ArrowRight")
        expect(page.locator("#attachmentViewerTitle")).to_have_text("Picture f")
        expect(viewer.locator(".attachment-viewer-image")).to_be_visible()
        _snapshot(page, f"agent-picture-gallery-viewer-{width}-{'dark' if dark else 'light'}")
        page.keyboard.press("Escape")
        expect(viewer).to_be_hidden()
        assert errors == []
    finally:
        context.close()

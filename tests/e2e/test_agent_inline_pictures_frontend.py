"""Pictures in the answer text (2026-10-31): built /app, isolated fixtures, no paid calls.

The agent places a picture it showed with ![caption](picture:p1)
(agent_web_images.picture_markdown); the app puts the stored picture there
(markdown-stream.js .md-picture, agent-workspace.js placePictures). A picture
it did not place stands under the text once the run is over.
"""
import io
import json

import pytest
from PIL import Image
from playwright.sync_api import expect
from test_phase4_frontend import phase4_server, _real_firebase_page, _json
from test_agent_chat_frontend import CATALOG, _choose_mode, _snapshot


def _png(color):
    buffer = io.BytesIO()
    Image.new("RGB", (640, 360), color).save(buffer, "PNG")
    return buffer.getvalue()


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

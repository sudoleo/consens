"""The finished "Thought for …" opens and closes in one glide: nothing below it jumps.

Measured frame by frame in the built /app with fully mocked HTTP, no paid calls.
"""
import json

import pytest
from playwright.sync_api import expect

from test_phase4_frontend import phase4_server, _real_firebase_page, _json
from test_agent_chat_frontend import CATALOG, _choose_mode

# Records, in every frame until the activity has settled, where the summary
# and the answer under it stand and how far the page is scrolled.
TRACK = """async () => {
  const host = document.getElementById('agentAnswerActivity');
  const summary = host.querySelector('details > summary');
  const answer = document.getElementById('agentAnswerBody');
  const frames = [];
  const sample = () => frames.push({
    summary: summary.getBoundingClientRect().top,
    answer: answer.getBoundingClientRect().top,
    scroll: window.scrollY,
  });
  sample();
  summary.click();
  let quiet = 0;
  while (quiet < 6) {
    await new Promise(resolve => requestAnimationFrame(resolve));
    sample();
    quiet = host.getAnimations({ subtree: true }).some(a => a.playState === 'running') ? 0 : quiet + 1;
  }
  return frames;
}"""


@pytest.mark.parametrize("width", [1280, 390])
def test_finished_activity_opens_and_closes_without_a_jump(browser, phase4_server, width):
    context, page = _real_firebase_page(browser, phase4_server)
    try:
        page.set_viewport_size({"width": width, "height": 900})
        page.emulate_media(reduced_motion="no-preference")
        page.route("**/user_status", lambda route: _json(route, {"tier": "pro", "is_pro": True, "agent_access": True}))
        page.route("**/agent/models", lambda route: _json(route, CATALOG))
        page.route("**/chats", lambda route: _json(route, {"chat": {"id": "a" * 32}}))
        answer = " ".join(["The first option fits the budget and the evidence supports it."] * 12)
        activity = [{"version": 1, "id": f"r{i}", "kind": "reasoning", "format": "summary",
                     "text": "Comparing the supporting evidence.\nChecking whether sources agree."} for i in range(3)]
        turn = {"id": "b" * 32, "status": "completed", "execution_mode": "agent", "question": "Which option fits?",
                "created_at": "2026-09-20T10:00:00Z", "completed_at": "2026-09-20T10:00:18Z",
                "consensus": answer, "agent_activity": activity,
                "agent_settings": {"model_id": CATALOG["default_model_id"], "label": "DeepSeek V4.1 Flash", "reasoning_effort": "default"}}

        def respond(route):
            final = {"response": answer, "chat_id": "a" * 32, "turn_id": turn["id"], "turn": turn}
            route.fulfill(content_type="text/event-stream", body="event: final\ndata: " + json.dumps(final) + "\n\n")
        page.route("**/agent", respond)
        page.evaluate("async () => { await window.__switchE2EUser('account-a'); }")
        _choose_mode(page, "agent")
        page.locator("#questionInput").fill(turn["question"])
        page.locator("#sendButton").click()
        page.wait_for_function("() => App.runRegistry.visible()?.status === 'succeeded'")
        details = page.locator("#agentAnswerActivity details")
        expect(details.locator(".agent-activity-title")).to_contain_text("Thought for")
        # Let the send's scroll to the question and the answer's reveal settle.
        page.wait_for_function("""() => document.getElementById('agentAnswer').getAnimations({ subtree: true })
          .every(a => a.playState !== 'running') && !document.body.classList.contains('chat-scroll-following')""")

        for opening in (True, False):
            frames = page.evaluate(TRACK)
            assert details.evaluate("el => el.open") == opening
            first, last = frames[0], frames[-1]
            # The summary is what the reader tapped: it stays under the finger.
            assert all(abs(f["summary"] - first["summary"]) <= 1 for f in frames), frames
            assert all(abs(f["scroll"] - first["scroll"]) <= 1 for f in frames), frames
            # The answer glides one way only: down while it opens, up while it
            # closes. A collapsed margin that vanished while the height moved
            # sent it 18px the other way first and back at the end.
            assert (last["answer"] > first["answer"] + 20) == opening, frames
            steps = [b["answer"] - a["answer"] for a, b in zip(frames, frames[1:])]
            wrong = [step for step in steps if (step < -1 if opening else step > 1)]
            assert not wrong, frames
    finally:
        context.close()

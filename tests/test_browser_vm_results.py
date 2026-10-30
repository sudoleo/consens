"""What browser.py on the browser VM answers and how fast (runtime audit
2026-10-30, docs/agent-workspace-runtime-audit-2026-10-30.md): the
server's rest at the end of a message (K2), a resident helper that heals
Chrome (A7) and the page's picture for its card (V7).

Nothing here calls Sprites or starts a browser: browser.py runs against
fakes of Playwright's objects, as in test_agent_workspace.py; its scripts
run in tests/js/workspace-browser-settle.test.mjs.
"""
import base64
import importlib.util
import io
import json
from pathlib import Path

from app.services import agent_browser, agent_workspace

BROWSER_PY = Path(agent_workspace.__file__).with_name("workspace_vm") / "browser" / "browser.py"


def load():
    spec = importlib.util.spec_from_file_location("workspace_vm_browser_results", BROWSER_PY)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main_answers(browser, monkeypatch, capsys, request):
    """One call of browser.py in this process: its answer and the holds it set."""
    holds, helped = [], []
    monkeypatch.setattr(browser.sys, "stdin", type("In", (), {"buffer": io.BytesIO(json.dumps(request).encode())})())
    monkeypatch.setattr(browser, "stay_awake", lambda expire=browser.AWAKE_FOR: holds.append(expire))
    monkeypatch.setattr(browser, "through_server", lambda request: helped.append(request))
    assert browser.main() == 0
    return json.loads(capsys.readouterr().out), holds, helped


# --- K2: the server's rest at the end of a message --------------------------------

def test_rest_shortens_the_hold_and_does_nothing_else(monkeypatch, capsys):
    """Audit K2: after every run the browser VM stayed awake 10 minutes (the
    hold of each call). The server's rest at the end of a message shortens
    it to two minutes: no helper, no browser, no page; any other call holds
    it its 10 minutes as before."""
    browser = load()
    started = []
    monkeypatch.setattr(browser, "ensure_browser", lambda: started.append(True))
    monkeypatch.setattr(browser, "finished_downloads", lambda: started.append("downloads") or [])
    answer, holds, helped = main_answers(browser, monkeypatch, capsys, {"action": "rest"})
    assert answer["status"] == "ok" and answer["text"] == browser.RESTED and answer["served"] is False
    assert holds == ["2m"] and browser.REST_FOR == "2m" and helped == [] and started == []
    # The server's own, like warm: never the agent's, never refused while the user has the browser.
    assert "rest" in browser.SERVER_ACTIONS and "rest" not in browser.ACTING
    assert "rest" not in agent_browser.ACTIONS
    # Through the resident helper (a call of an older server would get there): the same, no browser.
    assert browser.run({"action": "rest"}) == {"text": browser.RESTED} and started == []
    assert browser.ready({"action": "rest"}) is True and started == [] and "prepared" not in browser.KEPT
    # Every other call still holds the VM awake for AWAKE_FOR.
    answer, holds, _ = main_answers(browser, monkeypatch, capsys, {"action": "rm -rf /"})
    assert answer["status"] == "refused" and holds == ["10m"]


# --- A7: the resident helper heals Chrome itself ---------------------------------

def test_the_resident_helper_restarts_a_chrome_that_takes_no_connection(monkeypatch):
    """Audit A7: ready connected without a restart and declined; the call
    then healed the browser itself after waiting up to 80 s for the helper,
    past the server's 180 s with its own restart and watchdog. Now the
    helper restarts Chrome once, as a call of its own does, and the call
    waits READY_SECONDS (35 s) for it."""
    browser = load()
    restarts, tries = [], []

    class Chromium:
        def connect_over_cdp(self, endpoint, timeout):
            tries.append(timeout)
            if len(tries) == 1 or broken:
                raise TimeoutError("BrowserType.connect_over_cdp: Timeout 15000ms exceeded.")
            return type("Browser", (), {"close": lambda self: None})()
    broken = False
    monkeypatch.setitem(browser.KEPT, "playwright", type("Playwright", (), {"chromium": Chromium()})())
    monkeypatch.setattr(browser, "ensure_browser", lambda: None)
    monkeypatch.setattr(browser, "user_control", lambda: False)
    monkeypatch.setattr(browser, "restart_browser", lambda: restarts.append(True))
    assert browser.ready({"action": "click", "ref": "e1"}) is True and restarts == [True] and len(tries) == 2
    assert browser.KEPT.get("browser") is not None
    browser.disconnect()
    # Still none after the restart: declined, the call runs itself.
    broken = True
    assert browser.ready({"action": "read"}) is False and len(restarts) == 2 and "browser" not in browser.KEPT
    # A helper that takes the call at the last moment, then an action that
    # hangs until the watchdog restarts Chrome: well within the server's
    # limit (with 80 s it was the limit exactly, the exec's own time not counted).
    assert browser.READY_SECONDS == 35
    assert browser.READY_SECONDS + browser.CALL_LIMIT + browser.RESTART_SECONDS <= agent_browser.CALL_SECONDS - 30


# --- V7: the page's card -------------------------------------------------------

def test_the_cards_picture_is_720_pixels_wide_and_smaller_only_when_it_must_be():
    """Audit V7: 480 px at quality 60, shown up to 360 CSS pixels, was soft
    on a retina screen. Now 720 px; a page whose JPEG is over the server's
    PREVIEW_BYTES (a page full of small text: 98 KB) goes again smaller,
    and one too large even then has no picture, never a failed step."""
    browser = load()
    assert browser.PREVIEW_WIDTH == 720 and browser.PREVIEW_BYTES <= agent_browser.PREVIEW_BYTES
    sizes, sent = [], []

    class Session:
        def send(self, method, params):
            sent.append((params["quality"], params["clip"]["scale"]))
            return {"data": base64.b64encode(b"\xff\xd8\xff" + b"x" * sizes.pop(0)).decode()}

        def detach(self):
            sent.append("detached")

    class Page:
        context = type("Context", (), {"new_cdp_session": lambda self, page: Session()})()

        def evaluate(self, script):
            return [0, 0, 1280, 800]
    sizes[:] = [40_000]
    assert len(base64.b64decode(browser.preview(Page()))) == 40_003
    assert sent == [(50, 720 / 1280), "detached"]
    sent.clear()
    sizes[:] = [98_000, 53_000]
    assert len(base64.b64decode(browser.preview(Page()))) == 53_003
    assert sent == [(50, 720 / 1280), (35, 600 / 1280), "detached"]
    sent.clear()
    sizes[:] = [200_000, 150_000, 90_000]
    assert browser.preview(Page()) == "" and len(sent) == 4 and sent[-1] == "detached"
    # Whatever the helper sends fits the server's card.
    sizes[:] = [browser.PREVIEW_BYTES - 3]
    assert agent_browser.preview_url(browser.preview(Page())).startswith("data:image/jpeg;base64,")


def test_the_hold_is_one_put_with_its_expiry(monkeypatch):
    browser = load()
    ran = []
    monkeypatch.setattr(browser.subprocess, "run", lambda argv, **kwargs: ran.append(argv))
    browser.stay_awake(browser.REST_FOR)
    browser.stay_awake()
    assert [json.loads(argv[-1]) for argv in ran] == [{"expire": "2m"}, {"expire": "10m"}]
    assert all(f"http://sprite/v1/tasks/{browser.AWAKE_TASK}" in argv and "PUT" in argv for argv in ran)

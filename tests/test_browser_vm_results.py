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
import os
from pathlib import Path

import pytest

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


# --- L5: a download's answer is the file ------------------------------------------

class Response:
    def __init__(self, url, body=b"%PDF-1.7 invoice", kind="application/pdf", status=200):
        self.url, self.body_bytes, self.status, self.ok = url, body, status, status < 400
        self.headers = {"content-type": kind} if kind else {}

    def body(self):
        return self.body_bytes


class Fetching:
    """A browser context whose request API answers ``response``."""

    def __init__(self, response):
        self.request, self.response = self, response

    def get(self, url, **kwargs):
        return self.response


def test_a_download_says_name_bytes_and_type_and_never_the_tab(tmp_path, monkeypatch):
    """Audit L5: 4,000 characters of the tab followed every download, and a
    sign-in page saved as report.pdf, or nothing at all, counted as one. Now
    the answer is the file: name, bytes, Content-Type, where a redirect led;
    0 bytes is refused with that fact."""
    browser = load()
    monkeypatch.setattr(browser, "DOWNLOADS", str(tmp_path / "downloads"))
    page = type("Page", (), {"url": "https://shop.example/orders"})()
    target = "https://shop.example/report.pdf"
    answer = browser.on_page(Fetching(Response(target)), page, "download", {"action": "download", "url": target},
                             "", [])
    assert answer == {"text": "Downloaded report.pdf: 16 bytes, Content-Type application/pdf."}
    # A sign-in page where the file was: what came, and from where.
    login = Response("https://shop.example/login?next=/report.pdf", body=b"<html>Sign in</html>",
                     kind="text/html; charset=utf-8")
    said = browser.fetch(Fetching(login), page, target)
    assert said == ("Downloaded login: 20 bytes, Content-Type text/html; charset=utf-8, after a redirect to "
                    "https://shop.example/login?next=/report.pdf.")
    # Nothing came: refused, nothing saved.
    with pytest.raises(browser.Refused) as empty:
        browser.fetch(Fetching(Response(target, body=b"", kind="")), page, target)
    assert str(empty.value) == "The download came back empty: 0 bytes (HTTP 200, no Content-Type). Nothing was saved."
    assert sorted(os.listdir(tmp_path / "downloads")) == ["login", "report.pdf"]


# --- L4: a failure names its cause and the page -----------------------------------

# As Playwright 1.64 words it (measured locally against Chromium).
INTERCEPTED = """Locator.click: Timeout 10000ms exceeded.
Call log:
  - waiting for locator("[data-consens-ref=\\"e12\\"]").first
    - locator resolved to <button id="b" data-consens-ref="e12">Pay</button>
  - attempting click action
    2 × waiting for element to be visible, enabled and stable
      - element is visible, enabled and stable
      - scrolling into view if needed
      - done scrolling
      - <div class="consent-layer"></div> intercepts pointer events
    - retrying click action
    - waiting 20ms
    3 × waiting for element to be visible, enabled and stable
      - element is visible, enabled and stable
      - scrolling into view if needed
      - done scrolling
      - <div class="consent-layer"></div> intercepts pointer events
    - retrying click action
      - waiting 500ms
"""
NOT_EDITABLE = """Locator.fill: Error: Element is not an <input>, <textarea>, <select> or [contenteditable]
Call log:
  - waiting for locator("[data-consens-ref=\\"e4\\"]").first
    - locator resolved to <div id="t" data-consens-ref="e4">text</div>
    - fill("my secret text")
  - attempting fill action
    - waiting for element to be visible, enabled and editable
"""


class Tab:
    """A tab as on_failure sees it: its address, title and cookies, read's
    lines (SNAPSHOT_JS) and its main frame without frames in it, where no
    element has a ref."""

    def __init__(self, browser, url="https://shop.example/cart", title="Shop", lines=()):
        self.browser, self.url, self.name, self.lines = browser, url, title, list(lines)
        self.context = type("Context", (), {"cookies": lambda self, urls: []})()
        self.main_frame = type("Frame", (), {"child_frames": [], "locator": lambda self, selector: type(
            "Locator", (), {"count": lambda self: 0})()})()

    def is_closed(self):
        return False

    def title(self):
        return self.name

    def evaluate(self, script, arg=None):
        if script == "document.visibilityState":
            return "visible"
        if script == self.browser.SNAPSHOT_JS:
            return {"lines": self.lines, "count": arg + len(self.lines)}
        raise AssertionError(script)


def tabs(*pages):
    return type("Context", (), {"pages": list(pages)})()


def test_a_failure_says_why_and_where(tmp_path, monkeypatch):
    """Audit L4: only the first line of Playwright's message ("Timeout
    10000ms exceeded."), no page, and the agent took a read or a screenshot
    to find out. Now the last step of the call log that says why, and the
    page in front; never the text typed, never a page of the browser's own
    computer."""
    browser = load()
    monkeypatch.setattr(browser, "REF_COUNTER", str(tmp_path / "ref-count"))
    assert browser.failure_text(RuntimeError(INTERCEPTED)) == (
        "Locator.click: Timeout 10000ms exceeded.\n"
        "Last step in Playwright's log: <div class=\"consent-layer\"></div> intercepts pointer events")
    # Nothing in the log says more than the message: the message alone, never the typed text.
    said = browser.failure_text(RuntimeError(NOT_EDITABLE))
    assert said == "Locator.fill: Error: Element is not an <input>, <textarea>, <select> or [contenteditable]"
    assert browser.failure_text(RuntimeError("")) == "RuntimeError"
    assert browser.failed(RuntimeError(INTERCEPTED))["text"].endswith("intercepts pointer events")

    page = Tab(browser)
    failure = browser.on_failure(tabs(page), page, "click", RuntimeError(INTERCEPTED))
    assert isinstance(failure, browser.Failed) and failure.status == "failed"
    assert str(failure) == ("Locator.click: Timeout 10000ms exceeded.\n"
                            "Last step in Playwright's log: <div class=\"consent-layer\"></div> intercepts pointer "
                            "events\nPage: \"Shop\"\nURL: https://shop.example/cart\nCookies saved for this site: no")
    # A refusal on a page keeps its status and names the page as well.
    refused = browser.on_failure(tabs(page), page, "key", browser.Refused("key takes one of: Enter."))
    assert type(refused) is browser.Refused and str(refused).splitlines()[1] == 'Page: "Shop"'
    # A page of the browser's own computer: its address only, and no step of the log (it quotes the page).
    own = Tab(browser, url="file:///home/sprite/.consens/browser/profile/Default/Preferences", title="secret")
    failure = browser.on_failure(tabs(own), own, "click", RuntimeError(INTERCEPTED))
    assert str(failure) == ("Locator.click: Timeout 10000ms exceeded.\n"
                            "URL: file:///home/sprite/.consens/browser/profile/Default/Preferences")
    # A download changes no page: its reason alone.
    refused = browser.on_failure(tabs(page), page, "download", browser.Refused("The download failed: HTTP 403."))
    assert str(refused) == "The download failed: HTTP 403."


def test_a_ref_no_element_has_any_more_brings_the_page_as_it_is_now(tmp_path, monkeypatch):
    """Audit L4: "e12 is not on the page any more (it changed). Call read
    for the current refs." cost one more step; now the read follows."""
    browser = load()
    monkeypatch.setattr(browser, "REF_COUNTER", str(tmp_path / "ref-count"))
    monkeypatch.setattr(browser, "FRAME_REFS", str(tmp_path / "frame-refs.json"))
    page = Tab(browser, lines=['heading "Cart"', '[e40] button "Pay now"'])
    with pytest.raises(browser.StaleRef) as stale:
        browser.act(None, page, "click", {"ref": "e12"})
    refused = browser.on_failure(tabs(page), page, "click", stale.value)
    assert type(refused) is browser.Refused and str(refused) == (
        "e12 is not on the page any more (it changed). The page as it is now:\n"
        "Page: \"Shop\"\nURL: https://shop.example/cart\nCookies saved for this site: no\n"
        "heading \"Cart\"\n[e40] button \"Pay now\"")
    # To the server a refusal and a failure as before, now with the page.
    for error in (refused, browser.on_failure(tabs(page), page, "click", RuntimeError(INTERCEPTED))):
        monkeypatch.setattr(browser, "run", lambda request, error=error: (_ for _ in ()).throw(error))
        answer = browser.answer_for({"action": "click", "ref": "e12"})
        assert answer == {"status": error.status, "text": str(error)} and "URL: https://shop.example/cart" in str(error)


# --- T4: an action's effect, without waiting for the network to rest -------------

class Clock:
    """time as quiet sees it: the test moves it, the page's waits move it."""

    def __init__(self):
        self.now = 100.0

    def monotonic(self):
        return self.now

    def time(self):
        return self.now


class Request:
    def __init__(self, kind="fetch", navigation=False, frame=None):
        self.resource_type, self.navigation, self.frame = kind, navigation, frame

    def is_navigation_request(self):
        return self.navigation


class Settling:
    """A tab after an action, as quiet sees it through Playwright: QUIET_JS's
    answer from the times its DOM changed (seconds after the action), its
    request events at their times, and its load states."""

    def __init__(self, browser, clock, changes=(), events=(), gone_at=None):
        self.browser, self.clock, self.changes, self.gone_at = browser, clock, list(changes), gone_at
        self.start, self.last, self.handlers, self.waited = clock.now, None, {}, []
        self.events = sorted(events, key=lambda event: event[0])
        self.main_frame = object()

    def on(self, event, handler):
        self.handlers.setdefault(event, []).append(handler)

    def remove_listener(self, event, handler):
        self.handlers[event].remove(handler)

    def _deliver(self):
        # Playwright hands events over while one of its calls runs.
        while self.events and self.events[0][0] <= self.clock.now - self.start + 1e-9:
            _, event, argument = self.events.pop(0)
            for handler in list(self.handlers.get(event, [])):
                handler(argument)

    def evaluate(self, script, fresh):
        assert script == self.browser.QUIET_JS
        self._deliver()
        since = self.clock.now - self.start
        if self.gone_at is not None and since >= self.gone_at:
            return None
        if fresh:
            self.last = since
        self.last = max([self.last] + [at for at in self.changes if at <= since + 1e-9])
        return round((since - self.last) * 1000)

    def wait_for_timeout(self, ms):
        self.clock.now += ms / 1000
        self._deliver()

    def wait_for_load_state(self, state, timeout):
        self.waited.append(state)


def settle(browser, clock, page, short=False):
    traffic = browser.Traffic(page)
    begun = clock.now
    browser.quiet(page, traffic, short=short)
    traffic.stop()
    assert all(not handlers for handlers in page.handlers.values())
    return round(clock.now - begun, 2)


def test_an_actions_effect_is_there_once_the_page_rests_not_once_the_network_does(monkeypatch):
    """Audit T4: every action waited up to 2 s for the network to rest,
    which a page with tracking, polling or a websocket never does (a click:
    median 1.9 s in Prod); a page that had rested once got no wait at all,
    and the answer could come before a menu opened. Now 300 ms without a
    change of the page since the action, longer while a request it started
    is open, at most 1 s; after a scroll or most keys 100 ms, at most 0.3 s;
    a navigation loads as before."""
    browser = load()
    clock = Clock()
    monkeypatch.setattr(browser, "time", clock)
    # Nothing changes: the action's end plus 300 ms, no wait for the network.
    page = Settling(browser, clock)
    assert settle(browser, clock, page) == 0.3 and page.waited == []
    # A timer opens a menu after 150 ms: its answer comes after the menu.
    assert settle(browser, clock, Settling(browser, clock, changes=[0.15])) == 0.45
    # A request the action started answers after 0.6 s and fills the page.
    fetch = Request()
    page = Settling(browser, clock, changes=[0.6], events=[(0.05, "request", fetch), (0.6, "requestfinished", fetch)])
    assert settle(browser, clock, page) == 0.9
    # A page that never rests (polling, an animation): 1 s at most.
    endless = Request()
    assert settle(browser, clock, Settling(browser, clock, events=[(0.01, "request", endless)])) == 1.0
    assert settle(browser, clock, Settling(browser, clock, changes=[n / 10 for n in range(30)])) == 1.0
    # A scroll, a key: almost at once.
    assert settle(browser, clock, Settling(browser, clock), short=True) == 0.1
    assert browser.brief("scroll", {}) and browser.brief("key", {"key": "Tab"})
    assert not browser.brief("key", {"key": "Enter"}) and not browser.brief("click", {"ref": "e1"})


def test_a_navigation_loads_as_before(monkeypatch):
    """A link, a form sent: the tab's main frame asks for a new document;
    once it committed (or ended: a download, an error) the page loads as
    before, its document and then up to 2 s for the network."""
    browser = load()
    clock = Clock()
    monkeypatch.setattr(browser, "time", clock)
    page = Settling(browser, clock)
    navigation = Request("document", navigation=True, frame=page.main_frame)
    page.events = [(0.02, "request", navigation), (0.4, "framenavigated", page.main_frame)]
    assert settle(browser, clock, page) == 0.4 and page.waited == ["domcontentloaded", "networkidle"]
    # It ends without a new document (a download): no wait for one. (quiet
    # hears of it at its next look, after the 300 ms it waits anyway.)
    page = Settling(browser, clock)
    navigation = Request("document", navigation=True, frame=page.main_frame)
    page.events = [(0.02, "request", navigation), (0.2, "requestfailed", navigation)]
    assert settle(browser, clock, page) == 0.3 and page.waited == ["domcontentloaded", "networkidle"]
    # One that never commits waits LOADED_SECONDS at most.
    page = Settling(browser, clock)
    page.events = [(0.02, "request", Request("document", navigation=True, frame=page.main_frame))]
    assert settle(browser, clock, page) == 0.3 + browser.LOADED_SECONDS
    # A frame's document is no navigation of the page, but a request whose answer can change it.
    page = Settling(browser, clock)
    framed = Request("document", navigation=True, frame=object())
    page.events = [(0.02, "request", framed), (0.5, "requestfinished", framed)]
    assert settle(browser, clock, page) == 0.5 and page.waited == []
    # The watch went with its document: the page loaded anew.
    page = Settling(browser, clock, gone_at=0.1)
    assert settle(browser, clock, page) == 0.3 and page.waited == ["domcontentloaded", "networkidle"]
    # A same-document navigation (a router's pushState) is a change like any other.
    page = Settling(browser, clock, changes=[0.1])
    page.events = [(0.1, "framenavigated", page.main_frame)]
    assert settle(browser, clock, page) == 0.4 and page.waited == []


def test_the_hold_is_one_put_with_its_expiry(monkeypatch):
    browser = load()
    ran = []
    monkeypatch.setattr(browser.subprocess, "run", lambda argv, **kwargs: ran.append(argv))
    browser.stay_awake(browser.REST_FOR)
    browser.stay_awake()
    assert [json.loads(argv[-1]) for argv in ran] == [{"expire": "2m"}, {"expire": "10m"}]
    assert all(f"http://sprite/v1/tasks/{browser.AWAKE_TASK}" in argv and "PUT" in argv for argv in ran)

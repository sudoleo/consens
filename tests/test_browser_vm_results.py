"""What browser.py on the browser VM answers and how fast (runtime audit
2026-10-30, docs/agent-workspace-runtime-audit-2026-10-30.md): the
server's rest at the end of a message (K2), a resident helper that heals
Chrome (A7), the page's picture for its card (V7), a download's answer
(L5), failures with their cause and page (L4), an action's effect without
waiting for the network (T4) and only what changed after it (L2).

Nothing here calls Sprites or starts a browser: browser.py runs against
fakes of Playwright's objects, as in test_agent_workspace.py; its scripts
run in tests/js/workspace-browser-settle.test.mjs.
"""
import base64
import contextlib
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


class Sized(Fetching):
    """A request API whose HEAD answers ``head`` (a response, or an exception
    to raise) and that records which methods ran."""

    def __init__(self, response, head):
        super().__init__(response)
        self.head_answer, self.calls = head, []

    def head(self, url, **kwargs):
        self.calls.append("head")
        if isinstance(self.head_answer, Exception):
            raise self.head_answer
        return self.head_answer

    def get(self, url, **kwargs):
        self.calls.append("get")
        return self.response


def test_a_download_larger_than_the_server_keeps_is_never_read_into_memory(tmp_path, monkeypatch):
    """Download once read the whole file through Playwright's
    request API into the VM's memory (the driver, then base64 into Python)
    and only the server dropped it at 25 MB: a file of some GB took the
    browser down for the message. A HEAD first: what declares more than the
    server keeps is refused before the GET. A server without HEAD or without
    a length gets the GET as before."""
    browser = load()
    monkeypatch.setattr(browser, "DOWNLOADS", str(tmp_path / "downloads"))
    page = type("Page", (), {"url": "https://shop.example/orders"})()
    target = "https://cdn.example/disk.iso"
    head = Response(target, body=b"", kind="application/octet-stream")
    head.headers["content-length"] = str(4 * 1024 ** 3)
    big = Sized(Response(target), head)
    with pytest.raises(browser.Refused) as refused:
        browser.fetch(big, page, target)
    assert big.calls == ["head"]
    assert str(refused.value) == ("The file is larger than the 25 MB a download keeps: 4096 MB by its "
                                  "Content-Length. Nothing was saved.")
    assert not (tmp_path / "downloads").exists()
    assert browser.DOWNLOAD_BYTES == agent_browser.DOWNLOAD_BYTES
    # At the limit, or HEAD not allowed, failing or without a length: the GET as before.
    fits = Response(target, body=b"", kind="application/pdf")
    fits.headers["content-length"] = str(browser.DOWNLOAD_BYTES)
    for answer in (fits, Response(target, body=b"", status=405), TimeoutError("HEAD timed out"),
                   Response(target, body=b"", kind="")):
        sized = Sized(Response(target), answer)
        assert browser.fetch(sized, page, target).startswith("Downloaded disk")
        assert sized.calls == ["head", "get"]


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
    monkeypatch.setattr(browser, "LOOKED", str(tmp_path / "last-look.json"))
    page = Tab(browser, lines=['heading "Cart"', '[e40] button "Pay now"'])
    with pytest.raises(browser.StaleRef) as stale:
        browser.act(None, page, "click", {"ref": "e12"})
    refused = browser.on_failure(tabs(page), page, "click", stale.value)
    assert type(refused) is browser.Refused and str(refused) == (
        "e12 is not on the page any more (it changed). The page as it is now:\n"
        "Page: \"Shop\"\nURL: https://shop.example/cart\nCookies saved for this site: no\n"
        "heading \"Cart\"\n[e40] button \"Pay now\"")
    # It is the agent's look at the page now: the next action's answer goes from it.
    assert browser.remembered(page) == page.lines
    # To the server a refusal and a failure, each with the page.
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


class Answer:
    def __init__(self, request, status):
        self.request, self.status = request, status


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
    # A form sent with Enter answers with a redirect: its request finishes
    # (302) and the next one asks for the new document, which commits later.
    # Counting the finished 302 as the navigation's end once read the new
    # page before it loaded (half its elements).
    page = Settling(browser, clock)
    posted = Request("document", navigation=True, frame=page.main_frame)
    redirected = Request("document", navigation=True, frame=page.main_frame)
    page.events = [(0.02, "request", posted), (0.19, "response", Answer(posted, 302)),
                   (0.2, "requestfinished", posted), (0.25, "request", redirected),
                   (0.7, "framenavigated", page.main_frame)]
    assert settle(browser, clock, page) == 0.7 and page.waited == ["domcontentloaded", "networkidle"]
    # A redirect to a download ends with the download's request (heard at
    # quiet's next look, as below), never with LOADED_SECONDS.
    page = Settling(browser, clock)
    posted = Request("document", navigation=True, frame=page.main_frame)
    redirected = Request("document", navigation=True, frame=page.main_frame)
    page.events = [(0.02, "request", posted), (0.1, "response", Answer(posted, 303)),
                   (0.1, "requestfinished", posted), (0.15, "request", redirected),
                   (0.2, "requestfailed", redirected)]
    assert settle(browser, clock, page) == 0.3
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


# --- L2: after an action, what changed --------------------------------------------

PRODUCTS = [f'[e{n}] link "Product number {n} with a longer name"' for n in range(10, 40)]
CART = ['heading "Cart"', '[e1] button "Account" collapsed', '[e2] textbox "Search" (empty)', *PRODUCTS,
        '[e5] button "Pay"']


class Shop:
    """A tab for on_page as browser.py sees it through Playwright: read's
    lines (an action may change them), HIT_JS's two answers, a page that
    rests at once (QUIET_JS), what is in view, a locator for each listed ref,
    and its load states. The scripts themselves run in
    tests/js/workspace-browser-settle.test.mjs."""

    def __init__(self, browser, lines=CART, url="https://shop.example/cart"):
        self.browser, self.lines, self.url, self.name = browser, list(lines), url, "Shop"
        self.changes = {"count": 0, "changed": [], "removed": []}
        self.effect, self.in_view, self.waited, self.handlers = None, ([], []), [], {}
        self.context = type("Context", (), {"cookies": lambda self, urls: []})()
        page = self

        class Locator:
            def __init__(self, ref):
                self.ref, self.first = ref, self

            def count(self):
                return int(any(line.lstrip().startswith(f"[{self.ref}] ") for line in page.lines))

            def evaluate(self, script):
                return False

            def click(self, timeout):
                page.act()

            def fill(self, text, timeout):
                page.act()
        self.Locator = Locator
        self.keyboard = type("Keyboard", (), {"press": lambda self, key: page.act()})()
        # The page's own frame, with no frame in it (read's frames: test_agent_workspace.py).
        self.main_frame = type("Frame", (), {"child_frames": [], "locator": lambda self, selector: page.locator(
            selector)})()
        self.frames = [self.main_frame]

    def act(self):
        if self.effect:
            self.effect(self)

    def locator(self, selector):
        return self.Locator(selector.split('"')[1])

    def is_closed(self):
        return False

    def title(self):
        return self.name

    def on(self, event, handler):
        self.handlers.setdefault(event, []).append(handler)

    def remove_listener(self, event, handler):
        self.handlers[event].remove(handler)

    def wait_for_timeout(self, ms):
        pass

    def wait_for_load_state(self, state, timeout):
        self.waited.append(state)

    def go_back(self, wait_until, timeout):
        self.waited.append("back")

    def evaluate(self, script, arg=None):
        browser = self.browser
        if script == "document.visibilityState":
            return "visible"
        if script == browser.SNAPSHOT_JS:
            return {"lines": self.lines, "count": arg}
        if script == browser.HIT_JS:
            return {"view": [1280, 720], "at": []} if arg["mode"] == "before" else self.changes
        if script == browser.QUIET_JS:
            # It rests at once: the count starts at the action's end, then 300 ms went by.
            return 0 if arg else 10_000
        if script == browser.IN_VIEW_JS:
            return {"refs": self.in_view[0], "headings": self.in_view[1]}
        if script == browser.SCROLL_JS:
            self.act()
            return [0, 648, 720, 4000]
        raise AssertionError(script)


def acting(browser, page, action, **request):
    context = type("Context", (), {"pages": [page], "on": lambda *a: None, "remove_listener": lambda *a: None})()
    return browser.on_page(context, page, action, {"action": action, **request}, "", [])["text"]


@pytest.fixture
def browser(tmp_path, monkeypatch):
    module = load()
    monkeypatch.setattr(module, "REF_COUNTER", str(tmp_path / "ref-count"))
    monkeypatch.setattr(module, "LOOKED", str(tmp_path / "last-look.json"))
    return module


def test_after_an_action_on_the_same_page_only_what_changed_comes(browser):
    """Audit L2: every action brought read's list again (~950 tokens a
    step), also after a type without Enter or a key, and a click on a ref
    said only "Clicked e12.". Now the head of the page, what changed after
    the action (HIT_JS), and of read's list only the lines that changed
    since the agent's last look; the whole list after a navigation or a read."""
    page = Shop(browser)
    # The first look: the whole list.
    first = acting(browser, page, "key", key="Escape")
    assert first.splitlines()[:3] == ["Pressed Escape.", "No element of the page changed after it.", 'Page: "Shop"']
    assert '[e5] button "Pay"' in first and "Changed since" not in first

    # A click on a ref opens a menu: the change after it, nearest first, and the changed lines.
    def menu(tab):
        tab.lines[1] = '[e1] button "Account" expanded'
        tab.lines.append('[e46] link "Settings"')
        tab.changes = {"count": 2, "removed": [], "changed": [
            {"tag": "button#menu", "name": "Account", "ref": "e1", "box": [8, 66, 72, 87], "how": "aria-expanded"},
            {"tag": "div.menu", "name": "Settings", "ref": "", "box": [8, 90, 200, 120], "how": "new"}]}
    page.effect = menu
    clicked = acting(browser, page, "click", ref="e1")
    assert clicked == (
        "Clicked e1.\n"
        "Changed after it: 2 elements, nearest first: button#menu \"Account\" [e1] (box x 8-72, y 66-87) "
        "aria-expanded changed; div.menu \"Settings\" (box x 8-200, y 90-120) new.\n"
        "Page: \"Shop\"\nURL: https://shop.example/cart\nCookies saved for this site: no\n"
        "Changed since your last look at this page (+ new, ~ changed, - gone, unmarked: where; read lists all 35 lines):\n"
        "~ [e1] button \"Account\" expanded\n"
        "+ [e46] link \"Settings\"")
    # The server reads the page's title and address from it as before (agent_browser._activity).
    shown = agent_browser.BrowserTools._activity(
        type("Tools", (), {"vm": type("VM", (), {"_outcome": lambda self, result: {}})(), "_timing": None})(),
        agent_browser.BrowserArgs(action="click", ref="e1"), {"action": "click", "page": clicked})
    assert shown["page_title"] == "Shop" and shown["page_url"] == "https://shop.example/cart"

    # Typing changes its field's line; nothing else came.
    def typed(tab):
        tab.lines[2] = '[e2] textbox "Search" value="Paris"'
        tab.changes = {"count": 0, "changed": [], "removed": []}
    page.effect = typed
    assert acting(browser, page, "type", ref="e2", text="Paris").splitlines()[-2:] == [
        "Changed since your last look at this page (+ new, ~ changed, - gone, unmarked: where; read lists all 35 lines):",
        "~ [e2] textbox \"Search\" value=\"Paris\""]
    # Nothing changed: said so.
    page.effect = None
    assert acting(browser, page, "key", key="Tab").endswith(
        "The page's headings and elements are as at your last look (35 lines; read lists them).")
    # A menu item that went: its line as it was.
    page.effect = lambda tab: tab.lines.remove('[e46] link "Settings"')
    assert acting(browser, page, "key", key="Escape").endswith('- [e46] link "Settings"')
    # wait answers the same way.
    page.effect = None
    assert acting(browser, page, "wait", seconds=1).endswith("(34 lines; read lists them).")
    # read and open always bring the whole list.
    assert '[e39] link "Product number 39' in browser.on_page(None, page, "read", {"action": "read"}, "", [])["text"]
    page.effect = None
    opened = acting(browser, page, "back")
    assert opened.startswith("Went back.\nPage: \"Shop\"") and "Changed since" not in opened and "[e39]" in opened


def test_the_whole_list_comes_when_the_page_is_another_or_the_look_is_old(browser, monkeypatch):
    page = Shop(browser)
    browser.on_page(None, page, "read", {"action": "read"}, "", [])
    # Another document at the same address (a reload, a takeover): most of it is new.
    page.lines = ['heading "Cart"', *[f'[e{n}] link "Other product {n} with a longer name"' for n in range(50, 80)]]
    reloaded = acting(browser, page, "key", key="Enter")
    assert "Changed since" not in reloaded and "[e79]" in reloaded
    # Another address: the whole list.
    page.url = "https://shop.example/checkout"
    assert "Changed since" not in acting(browser, page, "key", key="Escape")
    # A look older than LOOK_SECONDS (a new message after a pause): the whole list.
    browser.on_page(None, page, "read", {"action": "read"}, "", [])
    real = browser.time.time
    monkeypatch.setattr(browser.time, "time", lambda: real() + browser.LOOK_SECONDS + 1)
    assert "[e79]" in acting(browser, page, "key", key="Escape")
    monkeypatch.setattr(browser.time, "time", real)
    # A short page comes whole: a diff would save nothing.
    short = Shop(browser, lines=['heading "Done"', '[e90] link "Home"'], url="https://shop.example/done")
    browser.on_page(None, short, "read", {"action": "read"}, "", [])
    assert acting(browser, short, "key", key="Escape").endswith('heading "Done"\n[e90] link "Home"')
    # A page of the browser's own computer: its address, nothing of it.
    own = Shop(browser, url="file:///etc/passwd")
    assert acting(browser, own, "key", key="Escape").endswith(f"URL: file:///etc/passwd\n{browser.OWN_COMPUTER}")


def test_a_scroll_brings_what_is_in_view_first(browser):
    """read's list does not depend on the view: after a scroll it came the
    same as before, and the agent took a screenshot to see where it was."""
    page = Shop(browser)
    browser.on_page(None, page, "read", {"action": "read"}, "", [])
    page.in_view = (["e20", "e21", "e22"], ['heading "Cart"'])

    def more(tab):
        tab.lines.append('[e47] link "Product 47, loaded on scrolling"')
    page.effect = more
    scrolled = acting(browser, page, "scroll", direction="down")
    assert scrolled.splitlines() == [
        "Scrolled down: the view shows 648-1368 of 4000 px.",
        "No element of the page changed after it.",
        'Page: "Shop"', "URL: https://shop.example/cart", "Cookies saved for this site: no",
        "In view now (4 of 35 lines; read lists all):",
        'heading "Cart"', *PRODUCTS[10:13],
        "Changed elsewhere since your last look (+ new, ~ changed, - gone, unmarked: where):",
        '+ [e47] link "Product 47, loaded on scrolling"']
    assert browser.scrolled(1, [0, 0, 720, 720]) == "The page did not move: the view shows 0-720 of 720 px."
    assert browser.scrolled(1, [2000, 3280, 720, 4000]) == (
        "Scrolled down: the view shows 3280-4000 of 4000 px, the end of the page.")
    assert browser.scrolled(-1, [500, 0, 720, 4000]) == "Scrolled up: the view shows 0-720 of 4000 px, the top of the page."
    assert browser.scrolled(-1, None) == "Scrolled up."


def test_lines_change_by_their_refs():
    browser = load()
    before = ['heading "A"', '[e1] button "Open" collapsed', '[e2] link "Gone"', "(outside the main content: x)",
              '  [e3] button "In a frame"']
    after = ['heading "A"', 'heading "B"', '[e1] button "Open" expanded', "(outside the main content: x)",
             '  [e3] button "In a frame"', '[e4] link "New"']
    assert browser.changes(before, after) == [("+", 'heading "B"'), ("~", '[e1] button "Open" expanded'),
                                              ("+", '[e4] link "New"'), ("-", '[e2] link "Gone"')]
    assert browser.changes(after, after) == []
    assert browser.changes(['heading "A"', 'heading "A"'], ['heading "A"']) == [("-", 'heading "A"')]


# read's frames and what lies over the page: read lists every
# frame's elements, the read after an action only those of a frame over the page.
CONSENT = ["(over the page:)", "frame https://consent.example/c, its elements:", '  [e50] button "Accept all"',
           '  [e51] button "Settings"', "(the page under it:)"]
NEWS = ['heading "News"', '[e1] link "Home"']
READ_FRAMES = ["frame https://ads.example/a, its elements:", '  [e60] link "Ad"',
               "frame https://video.example/v, its elements:", '  [e70] button "Play"']
ACTION_FRAMES = ["frame https://ads.example/a (read lists its elements)",
                 "frame https://video.example/v (read lists its elements)"]


def test_a_frames_elements_and_what_lies_over_the_page_change_as_the_page_does():
    """After an action read reads a frame only over the page: the elements
    of the others are neither gone nor new, only unread. A dialog over the
    page comes and goes with its lines; a change in a frame over the page
    says where it is."""
    browser = load()
    # Read listed every frame; after an action the others are not read: no change.
    assert browser.changes(NEWS + READ_FRAMES, NEWS + ACTION_FRAMES) == []
    # A consent dialog in a frame appears over the page: all of it is new.
    assert browser.changes(NEWS + ACTION_FRAMES, CONSENT + NEWS + ACTION_FRAMES) == [
        ("+", line) for line in CONSENT]
    # It went (Accept all): the frame goes as one line, with the lines around it.
    assert browser.changes(CONSENT + NEWS + READ_FRAMES, NEWS + ACTION_FRAMES) == [
        ("-", "(over the page:)"), ("-", "frame https://consent.example/c, its elements:"),
        ("-", "(the page under it:)")]
    # A step of the dialog: what changed in it, after where it is.
    step = ["(over the page:)", "frame https://consent.example/c, its elements:", '  [e50] button "Accept all"',
            '  [e51] button "Settings" expanded', '  [e52] checkbox "Analytics" unchecked', "(the page under it:)"]
    assert browser.changes(CONSENT + NEWS, step + NEWS) == [
        (" ", "(over the page:)"), (" ", "frame https://consent.example/c, its elements:"),
        ("~", '  [e51] button "Settings" expanded'), ("+", '  [e52] checkbox "Analytics" unchecked')]
    # A frame the last look did not read comes over the page: its elements are new to the agent.
    unread = ["heading \"News\"", "frame https://consent.example/c (read lists its elements)"]
    assert browser.changes(unread, CONSENT[:3] + CONSENT[4:] + NEWS[:1]) == [
        ("+", "(over the page:)"), (" ", "frame https://consent.example/c, its elements:"),
        ("+", '  [e50] button "Accept all"'), ("+", "(the page under it:)")]
    # A dialog of the page itself (no frame): its elements say they are over the page.
    dialog = ["(over the page:)", '[e80] button "Close"', '[e81] button "Next"', "(the page under it:)"]
    assert browser.changes(dialog + NEWS, dialog[:2] + ['[e81] button "Next" disabled'] + dialog[3:] + NEWS) == [
        (" ", "(over the page:)"), ("~", '[e81] button "Next" disabled')]


class ConsentFrame:
    """A frame over the page whose read gave e50 (frame-refs.json): its own
    document, watched for an action on e50 (HIT_JS, QUIET_JS)."""

    def __init__(self, browser, changes):
        self.browser, self.url, self.changes, self.detached, self.asked = (
            browser, "https://consent.example/c", changes, False, [])
        frame = self

        class Locator:
            first = None

            def count(self):
                return 1

            def click(self, timeout):
                frame.asked.append("click")
        Locator.first = Locator()
        self.Locator = Locator

    def locator(self, selector):
        assert selector == '[data-consens-ref="e50"]'
        return self.Locator()

    def is_detached(self):
        return self.detached

    def evaluate(self, script, arg=None):
        self.asked.append(script)
        if script == self.browser.HIT_JS:
            return {"view": [800, 400], "at": []} if arg["mode"] == "before" else self.changes
        if script == self.browser.QUIET_JS:
            return 0 if arg else 10_000
        raise AssertionError(script)

    def wait_for_timeout(self, ms):
        pass

    def wait_for_load_state(self, state, timeout):
        pass


def test_an_action_on_a_ref_in_a_frame_is_watched_in_that_frame(browser, tmp_path, monkeypatch):
    """A consent dialog in a frame: its changes are no change of
    the page's own document, which said "No element of the page changed
    after it." while the dialog had opened its settings."""
    monkeypatch.setattr(browser, "FRAME_REFS", str(tmp_path / "frame-refs.json"))
    browser.remember_frames({"e50": "https://consent.example/c"})
    page = Shop(browser, lines=CONSENT + NEWS)
    frame = ConsentFrame(browser, {"count": 1, "removed": [], "changed": [
        {"tag": "label", "name": "Analytics", "ref": "", "box": [150, 57, 234, 74], "how": "new"}]})
    page.frames = [page.main_frame, frame]
    clicked = acting(browser, page, "click", ref="e50")
    assert clicked.splitlines()[:2] == [
        "Clicked e50.",
        "Changed in its frame after it (boxes in the frame): 1 element: label \"Analytics\" (box x 150-234, y 57-74) new."]
    # Watched before the click, then its rest looked at in the frame.
    assert frame.asked[:3] == [browser.HIT_JS, "click", browser.QUIET_JS]
    # Accept all: the frame left the page.
    frame.detached = True
    assert acting(browser, page, "click", ref="e50").splitlines()[1] == "Its frame left the page after it."


def test_after_an_action_the_diff_holds_to_the_frames_read_listed(browser):
    """End to end: a read with every frame, then a click: the frames read
    does not read after an action stay out of the answer."""
    page = Shop(browser, lines=NEWS + [f'[e{n}] link "Story number {n} with a longer headline"' for n in range(10, 30)]
                + READ_FRAMES)
    browser.on_page(None, page, "read", {"action": "read"}, "", [])

    def opened(tab):
        tab.lines = CONSENT + NEWS + tab.lines[2:22] + ACTION_FRAMES
    page.effect = opened
    clicked = acting(browser, page, "click", ref="e1")
    assert clicked.split("Cookies saved for this site: no\n", 1)[1] == (
        "Changed since your last look at this page (+ new, ~ changed, - gone, unmarked: where; read lists all "
        "29 lines):\n+ (over the page:)\n+ frame https://consent.example/c, its elements:\n"
        "+   [e50] button \"Accept all\"\n+   [e51] button \"Settings\"\n+ (the page under it:)")


def test_only_the_elements_an_answer_shows_take_their_key(browser, tmp_path, monkeypatch):
    """Every snapshot once wrote the key of every element,
    also of those out of the part the answer showed (READ_CHARS from an
    offset, AFTER_ACTION_CHARS, only what changed). A row the list drew
    another chat into out of that part took the other chat as its key, and
    the agent's click on the ref it had read reached that chat without a
    StaleRef. Now only the elements whose lines the answer shows take what
    the snapshot saw (SHOWN_JS; tests/js/workspace-browser-keys.test.mjs)."""
    monkeypatch.setattr(browser, "FRAME_REFS", str(tmp_path / "frame-refs.json"))
    page = Shop(browser)
    shown, real = [], page.evaluate

    def evaluate(script, arg=None):
        if script == browser.SHOWN_JS:
            shown.append(arg)
            return None
        return real(script, arg)
    page.evaluate = evaluate
    # A read from an offset: the lines it shows, with the request's step.
    monkeypatch.setattr(browser, "STEP", "t.1")
    said = browser.on_page(None, page, "read", {"action": "read", "offset": 30}, "", [])["text"]
    assert said.endswith('[e37] link "Product number 37 with a longer name"\n'
                         '[e38] link "Product number 38 with a longer name"\n'
                         '[e39] link "Product number 39 with a longer name"\n[e5] button "Pay"')
    assert shown == [[["e37", "e38", "e39", "e5"], "t.1"]]

    # An action that changes two lines: only those two, not the 32 the answer leaves out.
    shown.clear()
    monkeypatch.setattr(browser, "STEP", None)

    def drawn(tab):
        tab.lines[1] = '[e1] button "Account" expanded'
        tab.lines[13] = '[e20] link "Another product the list drew into this row"'
    page.effect = drawn
    clicked = acting(browser, page, "click", ref="e1")
    assert clicked.endswith('~ [e1] button "Account" expanded\n'
                            '~ [e20] link "Another product the list drew into this row"')
    assert shown == [[["e1", "e20"], None]]
    # A line that went names an element as it was: no key to keep.
    shown.clear()
    page.effect = lambda tab: tab.lines.remove('[e5] button "Pay"')
    assert acting(browser, page, "key", key="Escape").endswith('- [e5] button "Pay"')
    page.effect = None
    assert acting(browser, page, "key", key="Escape").endswith("as at your last look (33 lines; read lists them).")
    assert shown == []


def test_the_keys_of_a_frames_elements_are_kept_in_that_frame(browser, tmp_path, monkeypatch):
    """shown_to_agent: an element's line of read, of a frame (indented under
    it), of find (a place) and a change (+, ~) keep their keys, each in the
    document read found it in; a gone line (-) and the rest of the text do not."""
    monkeypatch.setattr(browser, "FRAME_REFS", str(tmp_path / "frame-refs.json"))
    browser.remember_frames({"e50": "https://consent.example/c", "e51": "https://consent.example/c"})
    asked = []

    class Frame:
        def __init__(self, url):
            self.url = url

        def evaluate(self, script, arg=None):
            assert script == browser.SHOWN_JS
            asked.append((self.url, arg))
            if self.url.startswith("https://ads."):
                raise RuntimeError("Frame was detached")
    main, consent, ads = Frame("https://news.example/"), Frame("https://consent.example/c"), Frame("https://ads.example/a")
    page = type("Page", (), {"main_frame": main, "frames": [main, ads, consent],
                             "evaluate": lambda self, script, arg=None: main.evaluate(script, arg)})()
    monkeypatch.setattr(browser, "STEP", "t.7")
    text = "\n".join([
        'Page: "News"', "URL: https://news.example/", '[e1] link "Home"',
        "(over the page:)", "frame https://consent.example/c, its elements:", '  [e50] button "Accept all"',
        '+ [e2] link "New story"', '~   [e51] button "Settings" expanded', '- [e3] link "Gone story"',
        '[e4] "…a match in the text…"', "(… 12 more lines: read with offset 40)"])
    assert browser.shown_to_agent(page, text) == text
    assert asked == [("https://news.example/", [["e1", "e2", "e4"], "t.7"]),
                     ("https://consent.example/c", [["e50", "e51"], "t.7"])]
    # A frame that went away on the way keeps the others' keys and the answer.
    browser.remember_frames({"e60": "https://ads.example/a"})
    asked.clear()
    assert browser.shown_to_agent(page, '  [e60] link "Ad"\n[e1] link "Home"') == '  [e60] link "Ad"\n[e1] link "Home"'
    assert asked == [("https://ads.example/a", [["e60"], "t.7"]), ("https://news.example/", [["e1"], "t.7"])]
    assert browser.shown_to_agent(page, 'Page: "News"\nURL: https://news.example/') and len(asked) == 2


def test_an_action_that_ran_never_fails_because_the_page_cannot_be_read(browser):
    """The click ran; reading the page after it failed (it was going away):
    read again once it loaded, else the address and why."""
    page = Shop(browser)
    reads = []
    real = page.evaluate

    def evaluate(script, arg=None):
        if script == browser.SNAPSHOT_JS:
            reads.append(True)
            raise RuntimeError("Execution context was destroyed, most likely because of a navigation")
        return real(script, arg)
    page.evaluate = evaluate
    said = acting(browser, page, "click", ref="e1")
    assert said.startswith("Clicked e1.\n") and said.endswith(
        "URL: https://shop.example/cart\n(the page could not be read after it: Execution context was destroyed, "
        "most likely because of a navigation)")
    assert len(reads) == 2


def test_an_action_that_ran_never_fails_because_its_picture_cannot_be_taken(browser):
    """The click ran; the picture asked for after it (screenshot_after) hung
    on a web font that never loads and Chrome gave up after 30 s. Before, the
    answer said the click failed and the agent clicked again (a send twice);
    now it says what the click did and that no picture came."""
    page = Shop(browser)

    def screenshot(type):
        raise TimeoutError("Timeout 30000ms exceeded.\nCall log:\n  - taking page screenshot\n"
                           "  - waiting for fonts to load...")
    page.screenshot = screenshot
    answer = browser.on_page(type("Context", (), {"pages": [page]})(), page, "click",
                             {"action": "click", "ref": "e1", "screenshot_after": True}, "", [])
    assert "png" not in answer
    assert answer["text"].startswith("Clicked e1.\n")
    assert answer["text"].endswith("\n(no picture after it: Timeout 30000ms exceeded.)")


def test_the_hold_is_one_put_with_its_expiry(monkeypatch):
    browser = load()
    ran = []
    monkeypatch.setattr(browser.subprocess, "run", lambda argv, **kwargs: ran.append(argv))
    browser.stay_awake(browser.REST_FOR)
    browser.stay_awake()
    assert [json.loads(argv[-1]) for argv in ran] == [{"expire": "2m"}, {"expire": "10m"}]
    assert all(f"http://sprite/v1/tasks/{browser.AWAKE_TASK}" in argv and "PUT" in argv for argv in ran)


# --- What a page asks during a call: dialogs and file pickers ---------------------

class Dialog:
    """Playwright's Dialog as answer_dialog sees it."""

    def __init__(self, type, message="", default_value=""):
        self.type, self.message, self.default_value, self.answers = type, message, default_value, []

    def accept(self, prompt_text=None):
        self.answers.append(("accept", prompt_text))

    def dismiss(self):
        self.answers.append(("dismiss",))


def chosen(name, mime, content):
    """The file as upload hands it to Chrome: its bytes, not its path. Chrome
    reads a path only when the form is sent, and the server deletes the file
    once the call is over: a later submit failed with ERR_FILE_NOT_FOUND."""
    return {"name": name, "mimeType": mime, "buffer": content}


class Chooser:
    """Playwright's FileChooser: the file upload chose in it."""

    def __init__(self):
        self.files = []

    def set_files(self, files, timeout):
        self.files.append(files)


@pytest.fixture
def driven(browser, tmp_path, monkeypatch):
    """run() as main calls it, on one tab and without Chrome: the request in,
    its answer's text out."""
    monkeypatch.setattr(browser, "FRAME_REFS", str(tmp_path / "frame-refs.json"))
    monkeypatch.setattr(browser, "UPLOADS", str(tmp_path / "uploads"))
    monkeypatch.setattr(browser, "ensure_browser", lambda: None)
    monkeypatch.setattr(browser, "watchdog", lambda seconds: None)
    monkeypatch.setattr(browser, "agent_ports", lambda: set())
    monkeypatch.setattr(browser, "user_control", lambda: False)
    os.makedirs(browser.UPLOADS)

    def run(page, **request):
        context = type("Context", (), {"pages": [page], "on": lambda self, event, handler: None,
                                       "remove_listener": lambda self, event, handler: None})()

        @contextlib.contextmanager
        def chrome():
            yield type("Browser", (), {"contexts": [context]})()
        monkeypatch.setattr(browser, "chrome", chrome)
        return browser.run(request)["text"]
    return run


def shows(*dialogs):
    """An effect: the page shows ``dialogs`` one after another, as Chrome
    sends them to the listeners of its tab."""
    def effect(tab):
        for dialog in dialogs:
            for handler in list(tab.handlers.get("dialog", [])):
                handler(dialog)
    return effect


def opens_picker(chooser):
    """An effect: the page opens a file picker."""
    def effect(tab):
        for handler in list(tab.handlers.get("filechooser", [])):
            handler(chooser)
    return effect


def test_a_confirm_gets_cancel_and_the_answer_says_what_the_page_asked(browser, driven):
    """Unhandled, Playwright closed every dialog unseen: the agent's click on
    "Pay" got Cancel from the page's confirm and nothing it could tell
    changed. Now the answer names the question right after the click, and
    the same click with accept_dialog answers OK."""
    page = Shop(browser)
    asked = Dialog("confirm", "Pay   30 EUR now?")
    page.effect = shows(asked)
    said = driven(page, action="click", ref="e5")
    assert asked.answers == [("dismiss",)]
    assert said.splitlines()[:3] == [
        "Clicked e5.",
        'The page asked (confirm) "Pay 30 EUR now?"; it got Cancel, so what it asked about did not happen. To '
        "answer OK, take the same action again with accept_dialog.",
        "No element of the page changed after it."]
    # The call's listeners end with it: Chrome answers the user's dialogs as before.
    assert page.handlers["dialog"] == [] and page.handlers["download"] == []

    again = Dialog("confirm", "Pay 30 EUR now?")
    page.effect = shows(again)
    said = driven(page, action="click", ref="e5", accept_dialog=True)
    assert again.answers == [("accept", None)]
    assert said.splitlines()[1] == 'The page asked (confirm) "Pay 30 EUR now?"; it got OK.'


def test_alerts_prompts_and_leaving_a_page_are_answered_as_the_action_asked(browser, driven):
    """An alert has only OK; a prompt answers its default with accept_dialog
    (Playwright's accept() alone answers ""); leaving the page is what the
    action asked for, also without accept_dialog. A dialog during a read
    (a timer's alert) comes at the end of its answer."""
    page = Shop(browser)
    saved, renamed, leaving = Dialog("alert", "Saved."), Dialog("prompt", "New name?", "draft"), Dialog("beforeunload")
    page.effect = shows(saved, renamed, leaving)
    said = driven(page, action="key", key="Enter", accept_dialog=True).splitlines()
    assert saved.answers == [("accept", None)] and renamed.answers == [("accept", "draft")]
    assert leaving.answers == [("accept", None)]
    assert said[1:4] == ['The page showed a message (alert) "Saved."; it was closed with OK.',
                         'The page asked (prompt) "New name?"; it got OK with its default "draft".',
                         "The page warned before it was left (it may have had unsaved changes); it was left."]
    unsure = Dialog("prompt", "Your age?")
    page.effect = shows(unsure)
    assert driven(page, action="key", key="Enter").splitlines()[1].startswith(
        'The page asked (prompt) "Your age?"; it got Cancel')
    assert unsure.answers == [("dismiss",)]

    late, real = Dialog("alert", "Session ends in 1 minute"), page.evaluate

    def evaluate(script, arg=None):
        if script == browser.SNAPSHOT_JS:
            shows(late)(page)
        return real(script, arg)
    page.evaluate = evaluate
    said = driven(page, action="read")
    assert said.endswith('\nThe page showed a message (alert) "Session ends in 1 minute"; it was closed with OK.')
    # Only a gesture opens a file picker: a read takes none (each costs Chrome a message per tab).
    fresh = Shop(browser)
    driven(fresh, action="read")
    assert "filechooser" not in fresh.handlers and fresh.handlers["dialog"] == []


def test_upload_goes_on_the_button_that_opens_the_file_picker(browser, driven, monkeypatch):
    """Sites hide their file field (read lists no hidden element) behind a
    button, a label or a drop zone, and set_input_files on the button
    failed ("Element is not an <input>"). Now upload clicks it and chooses
    the file in the picker it opens, by ref or at x,y."""
    upload = os.path.join(browser.UPLOADS, "report.pdf")
    Path(upload).write_bytes(b"%PDF")
    page = Shop(browser)
    picker = Chooser()
    page.effect = opens_picker(picker)
    said = driven(page, action="upload", ref="e5", file=upload)
    assert picker.files == [chosen("report.pdf", "application/pdf", b"%PDF")]
    assert said.startswith("Clicked e5, which opened a file picker, and chose report.pdf in it.\n")
    assert "The page opened a file picker" not in said and page.handlers["filechooser"] == []

    # At x,y of the screenshot: the same click as click's, then the picker.
    moved = []
    page.mouse = type("Mouse", (), {"move": lambda self, x, y: moved.append((x, y)),
                                    "click": lambda self, x, y: page.act()})()
    picker = Chooser()
    page.effect = opens_picker(picker)
    said = driven(page, action="upload", x=320, y=240, file=upload)
    assert picker.files == [chosen("report.pdf", "application/pdf", b"%PDF")] and moved == [(320, 240)]
    assert said.startswith("Clicked at 320,240, which opened a file picker, and chose report.pdf in it.")

    # A click that opens none (it opened a menu): its answer, not a failure.
    monkeypatch.setattr(browser, "CHOOSER_SECONDS", 0.05)
    page.effect = None
    said = driven(page, action="upload", ref="e5", file=upload)
    assert said.startswith("Clicked e5, which opened no file picker, so no file was chosen.")


def test_upload_on_a_file_field_sets_it_and_a_click_names_the_picker_it_opened(browser, driven):
    """A file field (also through its label) takes the file directly; a
    click that opened a picker says that upload chooses there."""
    upload = os.path.join(browser.UPLOADS, "photo.jpg")
    Path(upload).write_bytes(b"jpg")
    page, put = Shop(browser), []

    class Field(page.Locator):
        def evaluate(self, script):
            return script == browser.FILE_FIELD_JS

        def set_input_files(self, files, timeout):
            put.append((self.ref, files))
    page.Locator = Field
    assert driven(page, action="upload", ref="e2", file=upload).startswith("Put photo.jpg into e2.\n")
    assert put == [("e2", chosen("photo.jpg", "image/jpeg", b"jpg"))]
    # Only a file the server put there for this call.
    with pytest.raises(browser.Refused, match="The file to upload is missing"):
        driven(page, action="upload", ref="e2", file=str(Path(upload).with_name("other.jpg")))

    page = Shop(browser)
    page.effect = opens_picker(Chooser())
    said = driven(page, action="click", ref="e5")
    assert said.splitlines()[:2] == [
        "Clicked e5.",
        "The page opened a file picker, which closed without a file. To choose one, take upload on the same element "
        "(its ref, or x and y) with file."]


def test_a_scroll_on_a_ref_or_at_x_y_moves_the_box_that_scrolls_there(browser, driven):
    """A chat list, a side pane or a dialog's text scrolls in a box of its
    own: scroll moved only the window, and its answer said that the page did
    not move. With a ref or x,y it moves the box there (BOX_SCROLL_JS); where
    none scrolls, the page as before."""
    page, asked = Shop(browser), []
    page.in_view = (["e10", "e11"], [])
    boxes = iter([{"tag": "div#chats.list", "moved": [0, 480, 600, 3000]},
                  {"tag": "div#chats.list", "moved": [480, 0, 600, 3000]},
                  {"tag": "div#chats.list", "moved": [2400, 2400, 600, 3000]}, None])

    class Row(page.Locator):
        def evaluate(self, script, arg=None):
            if script == browser.BOX_SCROLL_JS:
                asked.append((self.ref, arg))
                return next(boxes)
            return False
    page.Locator = Row
    said = driven(page, action="scroll", ref="e10", direction="down").splitlines()
    assert asked == [("e10", 1)]
    assert said[0] == "Scrolled down in the box around e10 (div#chats.list): it shows 480-1080 of 3000 px."
    # What is in view comes first, as after a scroll of the page.
    shown = said.index("In view now (2 of 34 lines; read lists all):")
    assert said[shown + 1:shown + 3] == ['[e10] link "Product number 10 with a longer name"',
                                       '[e11] link "Product number 11 with a longer name"']
    assert driven(page, action="scroll", ref="e10", direction="up").splitlines()[0] == (
        "Scrolled up in the box around e10 (div#chats.list): it shows 0-600 of 3000 px, the top of the box.")
    assert driven(page, action="scroll", ref="e10").splitlines()[0] == (
        "The box around e10 (div#chats.list) did not move: it shows 2400-3000 of 3000 px.")
    # Nothing around the ref scrolls on its own: the page.
    assert driven(page, action="scroll", ref="e10").splitlines()[:2] == [
        "Nothing around e10 scrolls on its own; the page instead.",
        "Scrolled down: the view shows 648-1368 of 4000 px."]

    # At x,y: the element there, as the screenshot shows it.
    pointed = []

    class Handle:
        def evaluate(self, script, arg=None):
            assert script == browser.BOX_SCROLL_JS
            return {"tag": "section.pane", "moved": [0, 400, 500, 900]}
    page.evaluate_handle = lambda script, arg: pointed.append(arg) or Handle()
    said = driven(page, action="scroll", x=900, y=300)
    assert pointed == [[900, 300]]
    assert said.startswith("Scrolled down in the box at 900,300 (section.pane): it shows 400-900 of 900 px, the end "
                           "of the box.")
    # Without ref and x,y: the page, as before.
    assert driven(page, action="scroll", direction="down").startswith("Scrolled down: the view shows 648-1368")

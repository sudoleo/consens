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


# read's frames and what lies over the page (4c8c2b8d): read lists every
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
    """A consent dialog in a frame (4c8c2b8d): its changes are no change of
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


def test_the_hold_is_one_put_with_its_expiry(monkeypatch):
    browser = load()
    ran = []
    monkeypatch.setattr(browser.subprocess, "run", lambda argv, **kwargs: ran.append(argv))
    browser.stay_awake(browser.REST_FOR)
    browser.stay_awake()
    assert [json.loads(argv[-1]) for argv in ran] == [{"expire": "2m"}, {"expire": "10m"}]
    assert all(f"http://sprite/v1/tasks/{browser.AWAKE_TASK}" in argv and "PUT" in argv for argv in ran)

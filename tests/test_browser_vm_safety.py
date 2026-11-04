"""The workspace browser's safety and pace (2026-11-03): a ref whose element
the page filled with other content is stale (KEY_JS), an action on an element
gives up after ACT_MS with its reason, a step's later browser calls do not
run once one failed, and wait waits for a text instead of a fixed time.

Nothing here starts a browser: browser.py runs against fakes of Playwright's
objects (as in test_browser_vm_results.py); the page scripts run in
tests/js/workspace-browser-keys.test.mjs.
"""
import json

import pytest

from app.services import agent_browser
from app.services.agent_browser import BrowserArgs
from app.services.agent_delegation import CALL_AFTER_BROWSER_FAILURE
from test_agent_runs import store  # noqa: F401  (fixture)
from test_agent_vm import Agent, _admin_allowance, fake_vm, results, vm_loop  # noqa: F401  (fixtures)
from test_browser_vm_results import load


class Element:
    """An element as located finds it: the key read kept and the key now."""

    def __init__(self, kept, now, fails=False):
        self.kept, self.now, self.fails, self.calls, self.steps = kept, now, fails, [], []

    def evaluate(self, script, arg=None):
        if self.fails:
            raise RuntimeError("Execution context was destroyed")
        if script == "el => el.isContentEditable":
            return False
        if "data-consens-key" in script:
            self.steps.append(arg)
            return [self.kept, self.now]
        if "IS_SECRET" in script or "password" in script:
            return False
        raise AssertionError(script)

    def click(self, timeout):
        self.calls.append(("click", timeout))

    def fill(self, text, timeout):
        self.calls.append(("fill", timeout))

    def select_option(self, choice=None, label=None, timeout=None):
        self.calls.append(("select", timeout))


def page_with(element):
    locator = type("Locator", (), {"count": lambda self: 1, "first": element})()
    frame = type("Frame", (), {"locator": lambda self, selector: locator})()
    return type("Page", (), {"main_frame": frame, "frames": [frame]})()


@pytest.fixture
def browser(tmp_path, monkeypatch):
    module = load()
    monkeypatch.setattr(module, "FRAME_REFS", str(tmp_path / "frame-refs.json"))
    return module


# --- A ref whose element shows something else now ---------------------------------

def test_a_ref_whose_element_the_page_filled_anew_is_stale(browser):
    """WhatsApp's chat list draws its rows anew while it scrolls: Anna's
    element, ref and all, showed Clara's chat, and the click reached her."""
    same = Element("DIV Anna Weber", "DIV Anna Weber")
    assert browser.located(page_with(same), "e17") == (None, same)
    with pytest.raises(browser.StaleRef) as stale:
        browser.located(page_with(Element("DIV Anna Weber", "DIV Clara Diaz")), "e17")
    assert str(stale.value) == ("e17 shows something else now than when you read it: the page reused its element. "
                                "The page as it is now:")
    # A ref read before keys existed, or an element that cannot answer now: as before.
    for element in (Element(None, "DIV Clara Diaz"), Element("DIV Anna", "DIV Clara", fails=True)):
        assert browser.located(page_with(element), "e17") == (None, element)
    # The check runs the key read used (one source for both).
    assert browser.KEY_JS in browser.KEY_CHECK_JS and "%KEY_JS%" not in browser.SNAPSHOT_JS
    assert browser.KEY_JS in browser.SNAPSHOT_JS


def test_a_ref_is_checked_as_the_agent_saw_it_before_its_step(browser, monkeypatch):
    """[type e40 Hallo enter, click e17] in one step: the snapshot after the
    type noted the row the send had moved as it is now, and the click reached
    another chat (bug hunt 2026-11-04). The request's step goes to the check
    and to every snapshot (KEY_CHECK_JS, SNAPSHOT_JS; the page scripts in
    tests/js/workspace-browser-keys.test.mjs)."""
    monkeypatch.setattr(browser, "run", lambda request: {"text": "ok"})
    monkeypatch.setattr(browser, "finished_downloads", lambda: [])
    browser.answer_for({"action": "read", "step": "a1b2.3"})
    assert browser.STEP == "a1b2.3"
    element = Element("DIV Anna Weber", "DIV Anna Weber")
    browser.located(page_with(element), "e17")
    assert element.steps == ["a1b2.3"]
    assert browser.snapshot_arg(5) == {"start": 5, "step": "a1b2.3"}
    # A request without a step, or with one that is no mark, as before.
    for request in ({"action": "read"}, {"action": "read", "step": "a b"}, {"action": "read", "step": 3}):
        browser.answer_for(request)
        assert browser.STEP is None and browser.snapshot_arg(5) == 5


def test_the_calls_of_one_step_carry_one_mark_and_the_next_step_another(store, fake_vm):
    fake_vm.browser = lambda request: {"status": "ok", "text": 'Page: "WhatsApp"\nURL: https://web.whatsapp.com/'}
    script = Agent([[("browser", {"action": "type", "ref": "e40", "text": "Hallo", "enter": True}),
                     ("browser", {"action": "click", "ref": "e17"})],
                    [("browser", {"action": "read"})]])
    loop = vm_loop(store, script)
    list(loop.run())
    steps = [step for step, request in zip(fake_vm.steps, fake_vm.requests)
             if request.get("action") in {"type", "click", "read"}]
    assert len(steps) == 3 and steps[0] == steps[1] != steps[2]
    assert all(step.startswith(loop.turn_id + ".") for step in steps)


def test_an_action_on_a_stale_ref_never_reaches_the_element(browser):
    element = Element("DIV Anna Weber", "DIV Clara Diaz")
    for action, request in (("click", {"ref": "e17"}), ("type", {"ref": "e17", "text": "Hi", "enter": True}),
                            ("select", {"ref": "e17", "option": "Clara"})):
        with pytest.raises(browser.StaleRef):
            browser.act(None, page_with(element), action, request)
    assert element.calls == []


# --- An action that cannot happen gives up after 3 s -----------------------------

def test_an_action_on_an_element_waits_three_seconds_not_ten(browser):
    """A layer over the element or a list that hid it kept the agent waiting
    10 s for nothing; failure_text then says why (test_browser_vm_results.py)."""
    assert browser.ACT_MS == 3_000
    element = Element("BUTTON Send", "BUTTON Send")
    browser.act(None, page_with(element), "click", {"ref": "e3"})
    field = Element("INPUT Search", "INPUT Search")
    browser.act(None, page_with(field), "type", {"ref": "e4", "text": "anna"})
    choice = Element("SELECT Country", "SELECT Country")
    browser.act(None, page_with(choice), "select", {"ref": "e5", "option": "Germany"})
    assert element.calls == [("click", 3_000)] and field.calls == [("fill", 3_000)]
    assert choice.calls == [("select", 3_000)]


# --- wait until a text is on the page --------------------------------------------

class Clock:
    def __init__(self):
        self.now = 1000.0

    def time(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


class Shows:
    """The tab in front, which shows the text from its ``after``-th look on."""

    def __init__(self, after, url="https://web.whatsapp.com/"):
        self.after, self.looks, self.url = after, 0, url

    def evaluate(self, script, query):
        self.looks += 1
        return self.after is not None and self.looks > self.after


def waiting(browser, monkeypatch, tab):
    clock = Clock()
    monkeypatch.setattr(browser.time, "time", clock.time)
    monkeypatch.setattr(browser.time, "sleep", clock.sleep)
    monkeypatch.setattr(browser, "current_page", lambda context: tab)
    monkeypatch.setattr(browser, "hidden", lambda page: page.url.startswith("file:"))
    monkeypatch.setattr(browser, "after_text", lambda page, action: f"Page after {action}")
    monkeypatch.setattr(browser, "with_picture", lambda page, request, answer: answer)
    monkeypatch.setattr(browser, "with_preview", lambda page, request, answer: answer)
    return clock


def test_wait_returns_once_the_text_is_on_the_page(browser, monkeypatch):
    tab = Shows(after=3)
    waiting(browser, monkeypatch, tab)
    answer = browser.wait_for_text(None, {"action": "wait", "text": "Delivered", "seconds": 20}, "Delivered")
    assert answer == {"text": '"Delivered" is on the page, after 0.8 s.\nPage after wait'}
    assert tab.looks == 4


def test_wait_says_when_the_text_did_not_come_and_never_fails(browser, monkeypatch):
    waiting(browser, monkeypatch, Shows(after=None))
    answer = browser.wait_for_text(None, {"action": "wait", "text": "Delivered", "seconds": 5}, "Delivered")
    assert answer == {"text": '"Delivered" did not appear within 5 s.\nPage after wait'}
    # Without seconds: at most 30, as a plain wait.
    clock = waiting(browser, monkeypatch, Shows(after=None))
    browser.wait_for_text(None, {"action": "wait", "text": "x"}, "x")
    assert 1030 <= clock.now <= 1030.5


def test_wait_reads_nothing_of_the_browsers_own_computer(browser, monkeypatch):
    waiting(browser, monkeypatch, Shows(after=0, url="file:///home/sprite/.consens/browser/profile"))
    answer = browser.wait_for_text(None, {"action": "wait", "text": "secret"}, "secret")
    assert answer == {"text": browser.hidden_text(Shows(after=0, url="file:///home/sprite/.consens/browser/profile"))}


def test_wait_takes_a_text_like_find_and_the_work_record_names_it():
    from app.services.agent_compaction import describe
    for text in ("   ", "x" * 201):
        with pytest.raises(ValueError, match="wait waits for a text"):
            agent_browser.required(BrowserArgs(action="wait", text=text))
    agent_browser.required(BrowserArgs(action="wait", text="Delivered", seconds=20))
    agent_browser.required(BrowserArgs(action="wait", seconds=5))
    assert describe("browser", json.dumps({"action": "wait", "text": "Delivered"}), json.dumps({})) == \
        'browser wait "Delivered"'


# --- A failed browser call ends its step's browser calls -------------------------

def test_a_failed_browser_call_leaves_the_steps_later_browser_calls_unrun(store, fake_vm):
    """Click the chat, type, Enter in one step: when the click failed, the
    text went into whatever had the focus, which could be another chat."""
    def answer(request):
        if request.get("action") == "click":
            return {"status": "refused", "text": "e17 shows something else now than when you read it"}
        return {"status": "ok", "text": 'Page: "WhatsApp"\nURL: https://web.whatsapp.com/'}
    fake_vm.browser = answer
    script = Agent([[("browser", {"action": "click", "ref": "e17"}),
                     ("browser", {"action": "type", "ref": "e40", "text": "See you at 8", "enter": True}),
                     ("vm_exec", {"command": "ls"})],
                    [("browser", {"action": "read"})]])
    loop = vm_loop(store, script)
    list(loop.run())
    click, typed, command, read = results(loop)[:4]
    assert "shows something else now" in click["error"]
    assert typed == {"error": CALL_AFTER_BROWSER_FAILURE}
    # Other tools of the step run as before, and the next step's browser calls too.
    assert command["exit_code"] == 0 and read["action"] == "read"
    assert [request.get("action") for request in fake_vm.requests if request.get("action") != "warm"][:2] == \
        ["click", "read"]

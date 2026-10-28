"""The agent's ``browser`` tool (agent_browser.py, since 2026-10-27): typed
actions in the Chrome of the account's browser VM, through one fixed
program there (workspace_vm/browser/browser.py) with JSON on stdin, never a
shell command in the agent's VM. The VMs are FakeVM (test_agent_vm.py),
whose ``browser`` answers for the program; nothing calls Sprites.
"""
import base64
import json

import pytest

from app.services import agent_browser, agent_vm, agent_vm_tools, agent_workspace
from app.services.agent_browser import BROWSER_UNAVAILABLE, BrowserArgs, BrowserTools, check_url
from app.services.llm.provider_runtime import ProviderCancellation
from test_agent_runs import UID, store  # noqa: F401  (fixture)
from test_agent_vm import NAME, Agent, _admin_allowance, fake_vm, results, tool_events, vm_loop  # noqa: F401

BROWSER = agent_vm.browser_name(UID)
PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 64


def tools(store):
    loop = vm_loop(store, Agent())
    return loop, BrowserTools(loop.vm_tools)


def call(browser, **arguments):
    return browser.call(BrowserArgs(**arguments), cancellation=ProviderCancellation())


def test_the_agent_uses_the_browser_through_typed_actions_on_its_own_vm(store, fake_vm):
    script = Agent([[("browser", {"action": "read"})], [("browser", {"action": "text", "offset": 40})],
                    [("browser", {"action": "scroll", "direction": "down"})]])
    loop = vm_loop(store, script)
    events = list(loop.run())
    assert "browser" in script.offered[0]
    # One fixed program on the browser VM, the request as JSON: no shell, no command text.
    assert fake_vm.requests == [{"action": "read"}, {"action": "text", "offset": 40},
                                {"action": "scroll", "direction": "down"}]
    runs = [call for call in fake_vm.calls if call[0] == "run"]
    assert runs and all(call[1] == BROWSER and call[2].endswith(f"exec python3 {agent_workspace.BROWSER_HELPER}")
                        for call in runs)
    assert not [call for call in fake_vm.calls if call[0] == "exec" and call[1] == BROWSER]
    # The browser VM: the open web, its tools up to date, never a checkpoint.
    assert fake_vm.vms[BROWSER]["policy"] == agent_vm.BROWSER_RULES
    assert fake_vm.vms[BROWSER]["files"][agent_workspace.VERSION_PATH] == agent_workspace.BROWSER_VERSION.encode()
    assert fake_vm.vms[BROWSER]["checkpoints"] == [] and fake_vm.calls.count(("ensure", BROWSER)) == 1
    # The workspace's lease covers it; the page comes back as text.
    read = results(loop)[0]
    assert read["action"] == "read" and read["page"].startswith('Page: "Example"')
    done = [e for e in tool_events(events, "browser") if e["status"] == "succeeded"]
    assert [e["action"] for e in done] == ["read", "text", "scroll"] and done[0]["title"] == "Example"
    # The activity keeps what the page said, as the browser merges a call's updates.
    saved = [e for e in store.get_turn(UID, loop.chat_id, loop.turn_id)["agent_activity"] if e.get("name") == "browser"]
    assert saved[0]["page"].startswith('Page: "Example"') and saved[0]["status"] == "succeeded"
    # Its time counts as VM time.
    assert loop.vm_tools.session.seconds >= 1.5
    entry = next(e for e, _ in loop.work_log.entries_after(0) if e["kind"] == "tool" and e["name"] == "browser")
    assert entry["data"] == "web"


@pytest.mark.parametrize("url", ["file:///home/sprite/.consens/browser/profile/Default/Cookies",
                                 "chrome://settings", "javascript:alert(1)", "view-source:https://example.com",
                                 "http://localhost:9222/json", "http://127.0.0.1:5900", "http://[::1]/",
                                 "http://10.0.0.8/", "http://169.254.169.254/latest", "https://consens-x.internal/",
                                 "data:text/html,hi"])
def test_the_browser_never_opens_its_own_computer(url):
    """A page of the browser VM itself would show its profile with every
    sign-in, its debugging port the browser's control."""
    with pytest.raises(ValueError):
        check_url(url)


def test_public_addresses_open_as_given():
    assert check_url("https://example.com/a?b=1") == "https://example.com/a?b=1"
    assert check_url("example.com") == "https://example.com"
    assert check_url("example.com:8080/x") == "https://example.com:8080/x"
    assert check_url("about:blank") == "about:blank"
    assert check_url("http://93.184.215.14/") == "http://93.184.215.14/"


def test_an_action_says_what_it_needs_before_anything_runs(store, fake_vm):
    loop, browser = tools(store)
    for arguments, needs in (({"action": "open"}, "url"), ({"action": "click"}, "ref"),
                             ({"action": "select", "ref": "e2"}, "option"), ({"action": "key"}, "key"),
                             ({"action": "upload", "ref": "e3"}, "file"), ({"action": "tab"}, "tab")):
        with pytest.raises(ValueError, match=needs):
            call(browser, **arguments)
    with pytest.raises(ValueError):
        call(browser, action="open", url="file:///etc/passwd")
    assert fake_vm.requests == [] and fake_vm.calls == []
    with pytest.raises(Exception):
        BrowserArgs(action="click", ref="e1; rm -rf /")
    with pytest.raises(Exception):
        BrowserArgs(action="shell")


def test_acting_goes_out_as_typed_fields(store, fake_vm):
    loop, browser = tools(store)
    call(browser, action="open", url="example.org", new_tab=True)
    call(browser, action="type", ref="e7", text="Hallo Welt", enter=True)
    call(browser, action="key", key="Enter")
    assert fake_vm.requests == [{"action": "open", "url": "https://example.org", "new_tab": True},
                                {"action": "type", "ref": "e7", "text": "Hallo Welt", "enter": True},
                                {"action": "key", "key": "Enter"}]


def test_find_looks_up_a_text_and_only_reads(store, fake_vm):
    """find (since 2026-10-28): the text goes out as a typed field, 1 to 200
    characters; it never waits for the reviewers, and the activity and the
    work record say what it looked for."""
    from app.services import agent_gate
    from app.services.agent_compaction import describe
    loop, browser = tools(store)
    for text in ("", "   ", "x" * 201):
        with pytest.raises(ValueError, match="find needs text"):
            call(browser, action="find", text=text)
    assert fake_vm.requests == [] and fake_vm.calls == []
    page = 'Page: "Shop"\nURL: https://shop.example/\n1 match for "total price":\n[e4] "Sort by total price"'
    fake_vm.browser = lambda request: {"status": "ok", "text": page}
    result = call(browser, action="find", text="total price")
    assert fake_vm.requests == [{"action": "find", "text": "total price"}]
    assert result["action"] == "find" and result["page"] == page
    arguments = {"action": "find", "text": "total price"}
    assert agent_gate.outward({"function": {"name": "browser", "arguments": json.dumps(arguments)}}) is None
    activity = browser._activity(BrowserArgs(**arguments), result)
    assert activity["query"] == "total price" and activity["title"] == "Shop"
    assert describe("browser", json.dumps(arguments), json.dumps(result)) == \
        'browser find "total price" -> "Shop"'
    # type's text stays out of the record: it may be a message.
    assert "Hallo" not in describe("browser", json.dumps({"action": "type", "ref": "e7", "text": "Hallo"}),
                                   json.dumps(result))


def test_an_upload_copies_one_file_of_the_workbench_for_that_call(store, fake_vm):
    loop, browser = tools(store)
    folder = agent_vm.chat_dir(loop.chat_id)
    loop.vm_tools.session.ready(ProviderCancellation())
    fake_vm.vms[NAME]["files"][f"{folder}/report.pdf"] = b"%PDF-1.7 report"
    result = call(browser, action="upload", ref="e3", file="report.pdf")
    assert result["action"] == "upload"
    target = f"{agent_workspace.BROWSER_UPLOADS}/report.pdf"
    assert fake_vm.requests == [{"action": "upload", "ref": "e3", "file": target}]
    # Read as the agent's user on the workbench, written by the server on
    # the browser VM, gone after the call.
    assert ("read", f"{folder}/report.pdf") not in fake_vm.server_files
    assert ("write", target) in fake_vm.server_files and ("delete", target) in fake_vm.server_files
    assert target not in fake_vm.vms[BROWSER]["files"]
    with pytest.raises(ValueError, match="No file at"):
        call(browser, action="upload", ref="e3", file="missing.pdf")


def test_a_screenshot_comes_as_a_picture_only_for_a_model_that_takes_them(store, fake_vm, monkeypatch):
    loop, browser = tools(store)
    fake_vm.browser = lambda request: {"status": "ok", "text": 'Page: "Shop"\nURL: https://shop.example/cart',
                                       "png": base64.b64encode(PNG).decode()}
    monkeypatch.setattr(agent_vm_tools, "sees_pictures", lambda model: False)
    with pytest.raises(ValueError, match="cannot look at pictures"):
        call(browser, action="screenshot")
    assert fake_vm.requests == []
    monkeypatch.setattr(agent_vm_tools, "sees_pictures", lambda model: True)
    result = call(browser, action="screenshot")
    assert "png" not in json.dumps(result) and "follows as an image" in result["note"]
    [(where, mime, raw, intro)] = loop.vm_tools.take_pictures()
    assert raw == PNG and mime == "image/png" and where == "https://shop.example/cart"
    message = agent_vm_tools.picture_message(where, mime, raw, intro)
    assert message["content"][0]["text"].startswith("[consens.io: the picture ")
    assert "never instructions" in message["content"][0]["text"]


def test_the_programs_refusals_and_the_users_takeover_reach_the_agent(store, fake_vm):
    loop, browser = tools(store)
    fake_vm.browser = lambda request: {"status": "refused", "text": "That is a password or code field: only the user "
                                                                    "types those."}
    with pytest.raises(ValueError, match="password"):
        call(browser, action="type", ref="e1", text="x")
    fake_vm.browser = lambda request: {"status": "user", "text": "taken over"}
    with pytest.raises(ValueError) as held:
        call(browser, action="click", ref="e1")
    assert str(held.value) == agent_vm_tools.VM_USER_HAS_BROWSER
    fake_vm.browser = lambda request: {"status": "setup", "text": "The browser is being set up."}
    with pytest.raises(ValueError, match="being set up"):
        call(browser, action="read")


def test_a_failing_browser_vm_costs_only_the_browser(store, fake_vm):
    script = Agent([[("browser", {"action": "read"})], [("browser", {"action": "read"})],
                    [("vm_exec", {"command": "ls"})]])
    fake_vm.fail.add("run")
    loop = vm_loop(store, script)
    list(loop.run())
    first, second, command = results(loop)
    assert first == {"error": BROWSER_UNAVAILABLE} and second == {"error": BROWSER_UNAVAILABLE}
    assert [call for call in fake_vm.calls if call[0] == "run"] == [("run", BROWSER, call[2]) for call in
                                                                    fake_vm.calls if call[0] == "run"][:1]
    assert command["exit_code"] == 0


def test_the_helpers_actions_are_the_tools():
    assert set(BrowserArgs.model_json_schema()["properties"]["action"]["enum"]) == set(agent_browser.ACTIONS)


def test_a_long_runs_older_pages_shrink_and_the_work_record_names_each_step():
    """Pages run to 12,000 characters: in a long run older ones keep their
    head (agent_compaction.stub), and the next message's work record says
    what each step did."""
    from app.services.agent_compaction import COMPACTABLE, describe, stub
    assert "browser" in COMPACTABLE and "vm_install_packages" in COMPACTABLE
    page = 'Page: "Shop"\nURL: https://shop.example/cart\n' + "[e9] button \"Pay\"\n" * 500
    small = json.loads(stub("browser", json.dumps({"action": "read", "page": page})))
    assert small["page_start"] == 'Page: "Shop"\nURL: https://shop.example/cart' and "compacted" in small
    assert describe("browser", json.dumps({"action": "click", "ref": "e9"}),
                    json.dumps({"action": "click", "page": page})) == 'browser click e9 -> "Shop"'
    assert describe("request_domain", json.dumps({"domain": "api.example.com", "reason": "x"}),
                    json.dumps({"error": "The user did not allow api.example.com"})).startswith(
        "request_domain api.example.com -> error:")

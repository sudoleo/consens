"""What browser.py on the browser VM answers and how fast (runtime audit
2026-10-30, docs/agent-workspace-runtime-audit-2026-10-30.md): the
server's rest at the end of a message (K2), a resident helper that heals
Chrome (A7) and the page's picture for its card (V7).

Nothing here calls Sprites or starts a browser: browser.py runs against
fakes of Playwright's objects, as in test_agent_workspace.py; its scripts
run in tests/js/workspace-browser-settle.test.mjs.
"""
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


def test_the_hold_is_one_put_with_its_expiry(monkeypatch):
    browser = load()
    ran = []
    monkeypatch.setattr(browser.subprocess, "run", lambda argv, **kwargs: ran.append(argv))
    browser.stay_awake(browser.REST_FOR)
    browser.stay_awake()
    assert [json.loads(argv[-1]) for argv in ran] == [{"expire": "2m"}, {"expire": "10m"}]
    assert all(f"http://sprite/v1/tasks/{browser.AWAKE_TASK}" in argv and "PUT" in argv for argv in ran)

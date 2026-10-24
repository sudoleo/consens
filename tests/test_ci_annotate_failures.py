import runpy
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "ci_annotate_failures.py"


def test_a_library_error_names_the_line_of_the_test_that_waited(tmp_path, capsys):
    # A timed-out Playwright wait ends in the library's frames; the
    # annotation still says which wait in the test ran out.
    traceback = (
        "tests/e2e/test_chat_scroll_frontend.py:203: in test_agent_send\n"
        "    page.wait_for_function(script)\n"
        "venv/lib/playwright/_impl/_frame.py:945: in wait_for_function\n"
        + "    library frame\n" * 200
        + "E   playwright._impl._errors.TimeoutError: Timeout 30000ms exceeded.\n"
    )
    report = tmp_path / "browser.xml"
    report.write_text(
        '<testsuite><testcase classname="tests.e2e.test_chat_scroll_frontend" name="test_agent_send">'
        '<failure message="TimeoutError">' + traceback + "</failure></testcase></testsuite>",
        encoding="utf-8",
    )
    runpy.run_path(str(SCRIPT), run_name="annotate")["main"](str(report))
    line = capsys.readouterr().out.strip()
    assert line.startswith("::error title=tests.e2e.test_chat_scroll_frontend::test_agent_send%0A")
    assert "at tests/e2e/test_chat_scroll_frontend.py:203%0ATimeoutError" in line
    assert "_frame.py:945" not in line.split("%0A")[1]

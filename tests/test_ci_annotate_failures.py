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


def test_a_suite_cut_off_by_the_time_limit_names_the_test_still_running(tmp_path, capsys):
    # The job's time limit ends pytest before its JUnit report (nightly runs
    # 2026-10-25); the progress log of tests/e2e/conftest.py still names it.
    progress = tmp_path / "browser-progress.log"
    progress.write_text(
        "100.0 start tests/e2e/test_a.py::test_quick\n"
        "104.0 end tests/e2e/test_a.py::test_quick\n"
        "104.0 start tests/e2e/test_b.py::test_slow\n"
        "194.0 end tests/e2e/test_b.py::test_slow\n"
        "194.5 start tests/e2e/test_c.py::test_hangs\n",
        encoding="utf-8",
    )
    script = runpy.run_path(str(SCRIPT), run_name="annotate")
    script["main"](str(tmp_path / "browser.xml"), str(progress))
    cut, slowest = capsys.readouterr().out.strip().splitlines()
    assert cut.startswith("::error title=Suite cut off after 2 tests::")
    assert "tests/e2e/test_c.py::test_hangs (running for" in cut
    assert slowest == ("::error title=Slowest finished tests::"
                       "90 s  tests/e2e/test_b.py::test_slow%0A4 s  tests/e2e/test_a.py::test_quick")

    script["cut_off"](str(tmp_path / "missing.log"))
    assert capsys.readouterr().out.startswith("::error title=No test report::")


def test_a_written_report_wins_over_the_progress_log(tmp_path, capsys):
    report = tmp_path / "browser.xml"
    report.write_text('<testsuite><testcase classname="tests.e2e.test_a" name="test_ok"/></testsuite>',
                      encoding="utf-8")
    progress = tmp_path / "browser-progress.log"
    progress.write_text("1.0 start tests/e2e/test_a.py::test_ok\n2.0 end tests/e2e/test_a.py::test_ok\n",
                        encoding="utf-8")
    runpy.run_path(str(SCRIPT), run_name="annotate")["main"](str(report), str(progress))
    assert capsys.readouterr().out == ""

"""Exercise the PowerShell entry point with disposable command-line tools.

No npm installation, browser, emulator or external service is used here.
The real script is run in a checkout path containing spaces, on each available
Windows PowerShell version. Failure propagation and caller state are observable
at the process boundary instead of being asserted from source strings.
"""

import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import threading
import time

import pytest


ROOT = Path(__file__).resolve().parents[1]
SHELLS = [shutil.which(name) for name in ("pwsh", "powershell")]
SHELLS = [shell for shell in SHELLS if shell] if os.name == "nt" else []
pytestmark = pytest.mark.skipif(not SHELLS, reason="Windows PowerShell entry point")


@pytest.fixture(params=SHELLS or [None], ids=lambda value: Path(value).stem if value else "unavailable")
def cli(tmp_path, request):
    root = tmp_path / "checkout with spaces"
    root.mkdir()
    shutil.copy2(ROOT / "dev.ps1", root / "dev.ps1")
    python_dir = root / "venv" / "Scripts"
    python_dir.mkdir(parents=True)
    shutil.copy2(sys.executable, python_dir / "python.exe")
    config = Path(sys.prefix) / "pyvenv.cfg"
    if config.exists():
        shutil.copy2(config, python_dir.parent / "pyvenv.cfg")
    else:
        (python_dir.parent / "pyvenv.cfg").write_text(
            f"home = {Path(sys._base_executable).parent}\ninclude-system-site-packages = false\n",
            encoding="utf-8",
        )

    for relative in ("tests/js/example.test.mjs", "tests/e2e/test_example.py", "tests/test_example.py", "tests/rules/firestore.rules.test.mjs",
                     "node_modules/vitest/vitest.mjs", "node_modules/esbuild/package.json"):
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()
    (root / "app/core").mkdir(parents=True)
    shutil.copy2(ROOT / "app/core/e2e_profile.py", root / "app/core/e2e_profile.py")
    (root / "app/services").mkdir()
    (root / "app/services/agent_tokens.py").write_text("def encoding(): return None\n", encoding="utf-8")
    (root / "firebase.json").write_text(json.dumps({
        "emulators": {"firestore": {"host": "127.0.0.1", "port": 9876}}
    }), encoding="utf-8")
    (root / "playwright").mkdir()
    (root / "playwright/sync_api.py").write_text(
        "from contextlib import contextmanager\nfrom types import SimpleNamespace\n"
        "@contextmanager\ndef sync_playwright():\n"
        "    yield SimpleNamespace(chromium=SimpleNamespace(executable_path=__file__))\n",
        encoding="utf-8",
    )
    (root / "uvicorn.py").touch()
    (root / "pytest.py").write_text(
        "if __name__ == '__main__':\n"
        "    import fake_tools\n    fake_tools.main('pytest')\n", encoding="utf-8",
    )
    (root / "fake_tools.py").write_text('''
import json, os, subprocess, sys, time

def record(tool, args):
    with open(os.environ['DEV_LOG'], 'a', encoding='utf-8') as stream:
        stream.write(json.dumps({'tool': tool, 'args': args, 'cwd': os.getcwd(), 'time': time.time(),
            'env': {key: os.environ.get(key) for key in (
                'RUN_E2E', 'UNIT_TEST_MODE', 'E2E_TEST_MODE', 'FIRESTORE_EMULATOR_HOST',
                'GOOGLE_CLOUD_PROJECT', 'GCLOUD_PROJECT', 'FIREBASE_PROJECT_ID',
                'GOOGLE_APPLICATION_CREDENTIALS', 'PYTHONUTF8')}}) + '\\n')

def main(tool, args=None):
    args = sys.argv[1:] if args is None else args
    record(tool, args)
    if tool == 'java':
        print('openjdk 21.0.8')
    if tool == 'firebase':
        record('emulator-start', [])
        try:
            code = subprocess.run(args[-1], shell=True).returncode
        finally:
            record('emulator-stop', [])
        raise SystemExit(code)
    failure = os.environ.get('DEV_FAIL')
    if failure == tool or (tool == 'npm' and failure == 'npm-' + args[0]):
        raise SystemExit(23)

if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2:])
''', encoding="utf-8")
    commands = root / "tools"
    commands.mkdir()
    for name in ("node", "npm", "java", "firebase"):
        (commands / f"{name}.cmd").write_text(
            f'@echo off\n"{sys.executable}" "{root / "fake_tools.py"}" {name} %*\nexit /b %errorlevel%\n',
            encoding="utf-8",
        )

    def run(target, *, failure="", test_path="", command="check", inherited=True):
        env = os.environ.copy()
        env.update({
            "PATH": str(commands) + os.pathsep + env.get("PATH", ""),
            "JAVA_HOME": "", "DEV_SCRIPT": str(root / "dev.ps1"),
            "DEV_LOG": str(tmp_path / "calls.jsonl"), "DEV_STATE": str(tmp_path / "state.json"),
            "DEV_TARGET": target, "DEV_COMMAND": command, "DEV_TEST_PATH": test_path,
            "DEV_FAIL": failure, "RUN_E2E": "inherited-run", "UNIT_TEST_MODE": "inherited-unit", "PYTHONUTF8": "0",
            "E2E_TEST_MODE": "inherited-e2e", "FIRESTORE_EMULATOR_HOST": "inherited-host:1234",
            "GOOGLE_APPLICATION_CREDENTIALS": "inherited-credential.json",
            "GOOGLE_CLOUD_PROJECT": "inherited-project", "GCLOUD_PROJECT": "inherited-gcloud",
            "FIREBASE_PROJECT_ID": "inherited-firebase",
        })
        if not inherited:
            for key in ("RUN_E2E", "UNIT_TEST_MODE", "E2E_TEST_MODE", "FIRESTORE_EMULATOR_HOST",
                        "GOOGLE_APPLICATION_CREDENTIALS", "GOOGLE_CLOUD_PROJECT", "GCLOUD_PROJECT",
                        "FIREBASE_PROJECT_ID"):
                env.pop(key, None)
        script = """
$originalPath = $env:PATH
& $env:DEV_SCRIPT $env:DEV_COMMAND $env:DEV_TARGET -TestPath $env:DEV_TEST_PATH
$code = $LASTEXITCODE
$state = @{ cwd = (Get-Location).Path; originalPath = $originalPath; env = @{} }
foreach ($name in @('PATH', 'RUN_E2E', 'UNIT_TEST_MODE', 'E2E_TEST_MODE',
    'FIRESTORE_EMULATOR_HOST', 'GOOGLE_APPLICATION_CREDENTIALS',
    'GOOGLE_CLOUD_PROJECT', 'GCLOUD_PROJECT', 'FIREBASE_PROJECT_ID', 'PYTHONUTF8')) {
    $state.env[$name] = [Environment]::GetEnvironmentVariable($name, 'Process')
}
$state | ConvertTo-Json -Depth 3 | Set-Content -LiteralPath $env:DEV_STATE -Encoding UTF8
exit $code
"""
        result = subprocess.run(
            [request.param, "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
            cwd=tmp_path, env=env, capture_output=True, text=True, timeout=45,
        )
        state = json.loads(Path(env["DEV_STATE"]).read_text(encoding="utf-8-sig"))
        assert state["cwd"] == str(tmp_path), result.stdout + result.stderr
        expected = {key: env.get(key) for key in state["env"]}
        # pwsh prepends its own runtime directory at shell startup, before
        # dev.ps1 runs; compare against the actual caller's PATH.
        expected["PATH"] = state["originalPath"]
        assert state["env"] == expected
        log = Path(env["DEV_LOG"])
        calls = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()] if log.exists() else []
        return result, calls

    run.shell = request.param
    return root, run


def test_frontend_runs_tests_then_build_check_from_repository_root(cli):
    root, run = cli
    result, calls = run("frontend", test_path="tests/js/example.test.mjs")
    assert result.returncode == 0, result.stdout + result.stderr
    assert [(call["tool"], call["args"]) for call in calls] == [
        ("npm", ["test", "--", "tests/js/example.test.mjs"]), ("npm", ["run", "build:check"])
    ]
    assert all(call["cwd"] == str(root) for call in calls)


@pytest.mark.parametrize("failure,expected_calls", [("npm-test", 1), ("npm-run", 2)])
def test_frontend_preserves_failure_and_stops(cli, failure, expected_calls):
    _, run = cli
    result, calls = run("frontend", failure=failure)
    assert result.returncode == 23, result.stdout + result.stderr
    assert len(calls) == expected_calls
    assert "[dev] OK" not in result.stdout


@pytest.mark.parametrize("failure", ["", "pytest"])
def test_backend_isolates_inherited_e2e_flags_and_restores_caller(cli, failure):
    _, run = cli
    result, calls = run("backend", failure=failure, test_path="tests/test_example.py")
    assert result.returncode == (23 if failure else 0), result.stdout + result.stderr
    assert len(calls) == 1
    assert calls[0]["args"] == ["tests/test_example.py", "-q"]
    assert calls[0]["env"]["UNIT_TEST_MODE"] == "1"
    assert calls[0]["env"]["RUN_E2E"] is None
    assert calls[0]["env"]["E2E_TEST_MODE"] is None


@pytest.mark.parametrize("failure", ["", "pytest"])
def test_browser_delegates_lifecycle_and_failure_to_firebase(cli, failure):
    _, run = cli
    result, calls = run("browser", failure=failure, test_path="tests/e2e/test_example.py")
    assert result.returncode == (23 if failure else 0), result.stdout + result.stderr
    assert [call["tool"] for call in calls] == [
        "java", "npm", "firebase", "emulator-start", "pytest", "emulator-stop"
    ]
    firebase = calls[2]
    assert firebase["args"] == [
        "emulators:exec", "--only", "firestore", "--project", "demo-consensio-e2e",
        "--config", "firebase.json", "--non-interactive",
        "venv\\Scripts\\python.exe -m pytest tests/e2e/test_example.py -q",
    ]
    assert calls[4]["env"] == {
        "RUN_E2E": "1", "UNIT_TEST_MODE": None, "E2E_TEST_MODE": "1",
        "FIRESTORE_EMULATOR_HOST": "127.0.0.1:9876", "GOOGLE_APPLICATION_CREDENTIALS": None,
        "GOOGLE_CLOUD_PROJECT": "demo-consensio-e2e", "GCLOUD_PROJECT": "demo-consensio-e2e",
        "FIREBASE_PROJECT_ID": "demo-consensio-e2e",
        "PYTHONUTF8": "1",
    }


@pytest.mark.parametrize('failure', ['', 'node'])
def test_rules_uses_client_runner_with_emulator_lifecycle_and_restores_environment(cli, failure):
    _, run = cli
    result, calls = run('rules', failure=failure)
    assert result.returncode == (23 if failure else 0), result.stdout + result.stderr
    assert [call['tool'] for call in calls] == ['java', 'firebase', 'emulator-start', 'node', 'emulator-stop']
    assert calls[1]['args'][-1] == 'node --test tests/rules/firestore.rules.test.mjs'
    assert calls[3]['args'] == ['--test', 'tests/rules/firestore.rules.test.mjs']
    assert calls[3]['env']['FIREBASE_PROJECT_ID'] == 'demo-consensio-e2e'
    assert calls[3]['env']['GOOGLE_APPLICATION_CREDENTIALS'] is None


def test_browser_rejects_nonlocal_emulator_before_start(cli):
    root, run = cli
    config = root / "firebase.json"
    config.write_text(json.dumps({"emulators": {"firestore": {"host": "example.com", "port": 8085}}}))
    result, calls = run("browser")
    assert result.returncode != 0
    assert "loopback" in result.stderr
    assert not any(call["tool"] == "firebase" for call in calls)


def test_browser_failure_restores_initially_absent_environment_entries(cli):
    _, run = cli
    result, calls = run("browser", failure="pytest", inherited=False)
    assert result.returncode == 23, result.stdout + result.stderr
    assert calls[-1]["tool"] == "emulator-stop"


def _hold_emulator_queue(shell, tmp_path, *, release):
    """Another session's run: owns the queue for the fixture's port 9876."""
    ready = tmp_path / "queue-held"
    released = tmp_path / "queue-released"
    end = (f"Set-Content -LiteralPath '{released}' ([DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds()); "
           "$m.ReleaseMutex()" if release else "exit 0")
    holder = subprocess.Popen([shell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command",
        "$m = New-Object System.Threading.Mutex($false, 'consensio-dev-emulator-9876'); $null = $m.WaitOne(); "
        "$owner = Join-Path ([IO.Path]::GetTempPath()) 'consensio-dev-emulator-9876.txt'; "
        "[IO.File]::WriteAllText($owner, 'browser tests/e2e/test_other.py in another checkout'); "
        f"Set-Content -LiteralPath '{ready}' held; Start-Sleep -Seconds 4; {end}"])
    deadline = time.monotonic() + 30
    while not ready.exists():
        assert holder.poll() is None and time.monotonic() < deadline, "queue holder did not start"
        time.sleep(0.1)
    return holder, released


def test_browser_queues_behind_another_run_and_starts_when_it_ends(cli, tmp_path):
    _, run = cli
    holder, released = _hold_emulator_queue(run.shell, tmp_path, release=True)
    result, calls = run("browser", test_path="tests/e2e/test_example.py")
    holder.wait(timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Queued behind: browser tests/e2e/test_other.py in another checkout" in result.stdout
    firebase = next(call for call in calls if call["tool"] == "firebase")
    assert firebase["time"] * 1000 >= int(released.read_text(encoding="utf-8-sig").strip())
    assert [call["tool"] for call in calls][-1] == "emulator-stop"


def test_queue_survives_a_run_that_died_without_releasing(cli, tmp_path):
    _, run = cli
    holder, _ = _hold_emulator_queue(run.shell, tmp_path, release=False)
    result, calls = run("rules")
    holder.wait(timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    assert [call["tool"] for call in calls] == ["java", "firebase", "emulator-start", "node", "emulator-stop"]


def test_browser_waits_for_an_emulator_port_held_outside_the_queue(cli):
    _, run = cli
    listener = socket.socket()
    listener.bind(("127.0.0.1", 9876))
    listener.listen()
    closed = []

    def close_later():
        time.sleep(4)
        closed.append(time.time())
        listener.close()

    closer = threading.Thread(target=close_later)
    closer.start()
    try:
        result, calls = run("browser", test_path="tests/e2e/test_example.py")
    finally:
        closer.join()
    assert result.returncode == 0, result.stdout + result.stderr
    assert "port 9876 is held by python" in result.stdout
    firebase = next(call for call in calls if call["tool"] == "firebase")
    assert firebase["time"] >= closed[0]


@pytest.mark.parametrize("target,path", [("backend", "tests/e2e/test_example.py"), ("frontend", "../outside.py")])
def test_rejects_tests_outside_selected_suite(cli, target, path):
    root, run = cli
    (root.parent / "outside.py").touch()
    result, calls = run(target, test_path=path)
    assert result.returncode == 1
    assert not calls


@pytest.mark.parametrize("target", ["backend", "browser"])
def test_venv_on_another_python_version_must_be_rebuilt(cli, target):
    root, run = cli
    (root / ".python-version").write_text("2.7\n", encoding="utf-8")
    result, calls = run(target)
    assert result.returncode == 1
    current = "%d.%d" % sys.version_info[:2]
    assert f"venv uses Python {current}, the project expects 2.7" in result.stderr
    assert "docs/testing.md" in result.stderr
    assert not calls


def test_venv_matching_python_version_passes_with_patch_level(cli):
    root, run = cli
    (root / ".python-version").write_text("%d.%d.99\n" % sys.version_info[:2], encoding="utf-8")
    result, calls = run("backend", test_path="tests/test_example.py")
    assert result.returncode == 0, result.stdout + result.stderr
    assert [call["tool"] for call in calls] == ["pytest"]


def test_missing_dependencies_have_actionable_error(cli):
    root, run = cli
    (root / "node_modules/vitest/vitest.mjs").unlink()
    result, calls = run("frontend")
    assert result.returncode == 1
    assert "npm ci" in result.stderr
    assert not calls

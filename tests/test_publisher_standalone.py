"""Stock-Python regression suite; runnable without pytest or backend packages."""

import os
from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "publish_consensus.py"


class PublisherStandaloneTests(unittest.TestCase):
    def run_python(self, args, *, cwd=ROOT, env=None):
        # No inherited keys, PYTHONPATH, user site, dotenv or installed packages.
        clean_env = {key: os.environ[key] for key in ("SYSTEMROOT", "PATH") if key in os.environ}
        clean_env.update(env or {})
        return subprocess.run(
            [sys.executable, "-E", "-S", *args], cwd=cwd, env=clean_env,
            capture_output=True, text=True, timeout=20,
        )

    def assert_success(self, result):
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_cli_reaches_configuration_validation_without_packages(self):
        with tempfile.TemporaryDirectory() as outside:
            for args, cwd in (
                (["scripts/publish_consensus.py"], ROOT),
                ([str(SCRIPT)], outside),
                (["-m", "scripts.publish_consensus"], ROOT),
            ):
                with self.subTest(args=args, cwd=cwd):
                    result = self.run_python(args, cwd=cwd)
                    self.assertEqual(result.returncode, 1)
                    self.assertIn("Publisher failed: CONSENSUS_API_KEY is required", result.stderr)
                    self.assertNotIn("Traceback", result.stderr)

    def test_topic_models_credentials_and_request_contract_without_packages(self):
        code = textwrap.dedent('''
            import os, runpy, socket
            from unittest.mock import patch
            def forbidden(*args, **kwargs):
                raise AssertionError("Unexpected network access")
            with patch.object(socket.socket, "connect", forbidden):
                p = runpy.run_path("scripts/publish_consensus.py")
                choose = p["choose_question"]
                calls = []
                def http(method, url, **kwargs):
                    calls.append((method, url, kwargs))
                    if method == "GET":
                        return 200, {"shares": []}
                    return 200, {"choices": [{"message": {"content":
                        "Is OpenAI GPT better than Claude for coding?"}}]}
                choose.__globals__["http_json"] = http
                os.environ["OPENROUTER_API_KEY"] = " test-key "
                for configured, expected in (
                    (None, "openai/gpt-5.6-luna"),
                    ("   ", "openai/gpt-5.6-luna"),
                    ("gpt-custom", "openai/gpt-custom"),
                    (" openai/gpt-custom ", "openai/gpt-custom"),
                    ("anthropic/claude-custom", "anthropic/claude-custom"),
                ):
                    if configured is None:
                        os.environ.pop("OPENAI_TOPIC_MODEL", None)
                    else:
                        os.environ["OPENAI_TOPIC_MODEL"] = configured
                    choose("https://consensus.invalid", "test-consensus-key")
                    method, url, request = calls[-1]
                    assert url == "https://openrouter.ai/api/v1/chat/completions"
                    assert request["headers"]["Authorization"] == "Bearer test-key"
                    assert request["headers"]["HTTP-Referer"] == "https://consens.io"
                    assert request["headers"]["X-Title"] == "consens.io"
                    payload = request["payload"]
                    assert payload["model"] == expected
                    assert payload["reasoning"] == {"effort": "low"}
                    assert payload["provider"] == {"zdr": True}
                    assert payload["tools"][0]["type"] == "openrouter:web_search"
                os.environ.pop("OPENROUTER_API_KEY")
                try:
                    choose("https://consensus.invalid", "test-consensus-key")
                except p["PublisherError"] as exc:
                    assert "OPENROUTER_API_KEY is required" in str(exc)
                else:
                    raise AssertionError("Missing topic credential accepted")
                os.environ["CONSENSUS_QUESTION"] = "Is OpenAI GPT better than Claude for coding?"
                before = len(calls)
                assert choose("https://consensus.invalid", "test-consensus-key").endswith("?")
                assert len(calls) == before
                assert "app.core.config" not in __import__("sys").modules
                assert "app.services.llm.engines" not in __import__("sys").modules
        ''')
        self.assert_success(self.run_python(["-c", code]))

    def test_scheduled_flow_without_packages_or_external_services(self):
        # Exercise the actual __main__, HTTP serialization and exit status, with
        # only urlopen replaced. Unexpected requests fail closed.
        code = textwrap.dedent('''
            import io, json, os, runpy, socket
            from pathlib import Path
            from unittest.mock import patch
            mode = os.environ["TEST_MODE"]
            base = "https://consensus.invalid"
            question = "Is OpenAI GPT better than Claude for coding?"
            share = {"share_id": "share-test", "url": base + "/s/test",
                     "indexing_status": "indexed", "in_sitemap": True}
            config = {"enabled": mode != "disabled", "weekly_watch_enabled": True,
                      "auto_index": True}
            expected = [("GET", base + "/api/v1/publisher/config", config)]
            if mode != "disabled":
                expected += [
                    ("GET", base + "/api/v1/shares?limit=20", {"shares": []}),
                    ("POST", "https://openrouter.ai/api/v1/chat/completions",
                     {"choices": [{"message": {"content": question}}]}),
                    ("POST", base + "/api/v1/consensus/runs", {"run_id": "run-test"}),
                    ("GET", base + "/api/v1/consensus/runs/run-test",
                     {"status": "succeeded", "result": {"differences_data": {"agreement": {
                         "score": 60 if mode == "publish" else 100,
                         "major_contradictions": 1 if mode == "publish" else 0}}}}),
                ]
            if mode == "publish":
                expected += [
                    ("POST", base + "/api/v1/consensus/runs/run-test/share", share),
                    ("POST", base + "/api/v1/shares/share-test/watch",
                     {"watch": {"interval": "weekly", "model_tier": "free"}}),
                    ("PUT", base + "/api/v1/shares/share-test/indexing", share),
                ]
            def urlopen(request, timeout):
                method, url, response = expected.pop(0)
                assert (request.method, request.full_url) == (method, url)
                if url.endswith("/consensus/runs"):
                    assert request.get_header("Idempotency-key") == "scheduled-publisher-test"
                    assert json.loads(request.data)["question"] == question
                result = io.BytesIO(json.dumps(response).encode())
                result.status = 200
                return result
            def forbidden(*args, **kwargs):
                raise AssertionError("Unexpected network access")
            with patch("urllib.request.urlopen", urlopen), patch.object(socket.socket, "connect", forbidden):
                try:
                    runpy.run_path("scripts/publish_consensus.py", run_name="__main__")
                except SystemExit as exc:
                    assert exc.code == 0, exc.code
                else:
                    raise AssertionError("CLI did not exit")
            assert not expected, expected
            if mode != "disabled":
                summary = Path(os.environ["GITHUB_STEP_SUMMARY"]).read_text()
                assert ("Published Consensus" if mode == "publish" else "Consensus run not published") in summary
        ''')
        for mode in ("publish", "skip", "disabled"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as temp:
                self.assert_success(self.run_python(["-c", code], env={
                    "TEST_MODE": mode,
                    "CONSENSUS_API_BASE_URL": "https://consensus.invalid",
                    "CONSENSUS_API_KEY": "test-consensus-key",
                    "OPENROUTER_API_KEY": "test-topic-key",
                    "CONSENSUS_IDEMPOTENCY_KEY": "scheduled-publisher-test",
                    "GITHUB_STEP_SUMMARY": str(Path(temp) / "summary.md"),
                }))


if __name__ == "__main__":
    unittest.main()

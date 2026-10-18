import importlib.util
from pathlib import Path

from app.services import telegram_notifier


def _load():
    path = Path(__file__).resolve().parents[1] / "scripts" / "task_ping.py"
    spec = importlib.util.spec_from_file_location("task_ping", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_ping_goes_to_its_own_chat_not_the_alert_chat(monkeypatch):
    task_ping = _load()
    sent = {}
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "alerts")
    monkeypatch.setenv(task_ping.CHAT_ID_VAR, "789")

    def fake_send(chat_id, text, **kwargs):
        sent.update(chat_id=chat_id, text=text)
        return {"status": "sent"}

    monkeypatch.setattr(telegram_notifier, "send_bot_message", fake_send)
    ok, _ = task_ping.send(["Chat-Report:", "3 Vorschläge  warten"])

    assert ok
    assert sent == {"chat_id": "789", "text": "🔔 Claude-Task: Chat-Report: 3 Vorschläge warten"}


def test_ping_is_cut_so_no_report_lands_in_telegram():
    task_ping = _load()
    text = task_ping.ping_text(["x" * 1000])

    assert len(text) == len(task_ping.PREFIX) + task_ping.MAX_CHARS
    assert text.endswith("…")


def test_ping_without_chat_id_reports_instead_of_sending(monkeypatch):
    task_ping = _load()
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "alerts")
    monkeypatch.delenv(task_ping.CHAT_ID_VAR, raising=False)
    monkeypatch.setattr(telegram_notifier, "send_bot_message", lambda *a, **k: 1 / 0)

    ok, reason = task_ping.send(["Freitags-Post fertig"])

    assert not ok
    assert task_ping.CHAT_ID_VAR in reason

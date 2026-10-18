"""Ping Max on Telegram when a scheduled Claude task needs him.

Scheduled tasks in the Claude desktop app finish silently: their sessions land
in the sidebar section "Routines" and nothing reaches the phone. A task calls
this once at the end, and only when it needs Max (a decision, a post to
publish, a fix it could not make):

  venv/Scripts/python.exe scripts/task_ping.py "Chat-Report: 3 Vorschläge warten auf dein OK"

Sends through the operator bot (TELEGRAM_BOT_TOKEN) to
TASK_PING_TELEGRAM_CHAT_ID from the local .env. Deliberately not
TELEGRAM_CHAT_ID: that would also switch on critical-error alerts from local
dev servers. The text is a ping, not the report: it is cut to MAX_CHARS, so
no chat content from a report ends up in Telegram.

Exit code: 0 sent, 1 not sent (reason on stderr).
"""
from __future__ import annotations

import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

CHAT_ID_VAR = "TASK_PING_TELEGRAM_CHAT_ID"
MAX_CHARS = 300
PREFIX = "🔔 Claude-Task: "


def ping_text(words: list[str]) -> str:
    text = " ".join(" ".join(words).split())
    if len(text) > MAX_CHARS:
        text = text[: MAX_CHARS - 1].rstrip() + "…"
    return PREFIX + text


def send(words: list[str]) -> tuple[bool, str]:
    from app.services.telegram_notifier import bot_token, send_bot_message

    if not " ".join(words).strip():
        return False, "no text given"
    chat_id = str(os.environ.get(CHAT_ID_VAR) or "").strip()
    if not bot_token() or not chat_id:
        return False, f"TELEGRAM_BOT_TOKEN or {CHAT_ID_VAR} missing in .env"
    result = send_bot_message(chat_id, ping_text(words))
    if result.get("status") != "sent":
        detail = result.get("description") or result.get("http_status") or ""
        return False, f"Telegram: {result.get('status')} {detail}".strip()
    return True, "sent"


def main(argv: list[str]) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
    ok, reason = send(argv)
    print(reason, file=sys.stdout if ok else sys.stderr)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

"""The Agent's Watch tools: it prepares a Watch, and runs it on schedule.

A Watch runs the Agent again on a schedule in its chat (agent_watches.py).
Two sides:

* ``prepare_watch`` (WatchTools), on the user's own turns: never creates
  anything. It keeps one proposal on the running turn (``agent_watch``:
  task, goal, interval, local time); the card under the completed answer
  (static/js/agent-watch.js) starts it through ``POST /agent/watches``,
  which reads the task from that saved turn. Why a card instead of a write
  (docs/agent-mode.md, "Watch"): a page, mail or file the Agent read must
  never start runs that act in the user's name and use their allowance; the
  browser knows the user's timezone, the server does not; the user sees the
  task before anything is scheduled.
* ``report_finding`` and ``finish_watch`` (WatchRunTools), only in a
  scheduled run: the run's one way to reach the user, with a page it opened
  in this run as evidence, and the end of the Watch once its goal is met.
  agent_watches.turn_ended reads both from the turn (``agent_watch_run``).

prepare_watch is registered only on the user's own account-mode turns,
without Google data (private mail must not become a recurring task), not in
a temporary chat (a Watch lives in its chat) and not in a scheduled run.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Literal

from pydantic import Field

from app.services.agent_document_spec import Strict
from app.services.agent_watches import (GOAL_MAX_CHARS, REASON_MAX_CHARS, TASK_MAX_CHARS, TASK_MIN_CHARS,
                                        URL_MAX_CHARS)

# In prompt_defaults.py style, facts and no recipe: what a Watch is and what
# prepare_watch does; the tool's result says what to tell the user
# (INSTRUCTIONS).
AUDIT_PROMPT = """WATCHES

A Watch runs you again on a schedule in this chat, without the user present, and is consens.io's only way to reach the user later: a run that finds something new for them emails it. It suits anything the user wants to be told, reminded of or kept up to date on later, or done again and again. prepare_watch prepares one as a card below your answer, which only the user starts; what its task says, the runs then do in the user's name."""

INSTRUCTIONS = {
    "prepared": "Prepared only, nothing runs yet. The user starts it with the Watch card below your answer. "
                "Continue as usual and never claim the Watch is active.",
    "already_watched": "This chat already has a Watch, so the card says so instead of offering a second one. "
                       "Tell the user: they end the current one on its card first.",
    "limit_reached": "The user has no free Watch; the card says how to free one. Tell the user briefly.",
}

# What a scheduled run is, in its system prompt (WatchRunTools).
RUN_PROMPT = """THIS WATCH RUN

This message is a scheduled run of a Watch the user started in this chat, and the user is not here. Do its task with your tools as the user would, and decide yourself how to look. Starting the Watch was the user's permission for what its task says; nobody can answer a question now, so for anything beyond the task use report_finding with needs_user. The user hears of this run only through report_finding: at most once, only when there is something new for them, with a page you opened in this run as evidence. A run with nothing new ends with a short answer and no report. Once the Watch's goal is met, call finish_watch."""

# The run's app context (agent_watches.run_context).
RUN_NOTE = "This message is a scheduled Watch run; the user is away.{goal}"

WEEKDAYS = Literal["", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


class PrepareWatch(Strict):
    task: str = Field(
        min_length=TASK_MIN_CHARS, max_length=TASK_MAX_CHARS,
        description="What each scheduled run does: an instruction to yourself that stands without the rest of "
                    "this chat, in the user's language, e.g. \"Check on ironman.com whether registration for "
                    "IRONMAN Hamburg 2027 is open.\"")
    goal: str = Field(
        default="", max_length=GOAL_MAX_CHARS,
        description="When the Watch is done, as a short statement of it having happened, e.g. \"Registration "
                    "is open\". Empty for one that keeps running, such as a weekly report.")
    interval: Literal["hourly", "every_6_hours", "daily", "weekly"] = Field(
        default="daily", description="How often it runs: hourly only when an hour matters.")
    run_time: str = Field(
        default="", pattern=r"^(?:(?:[01]\d|2[0-3]):[0-5]\d)?$",
        description="Local time HH:MM of a daily or weekly run; empty for 08:00.")
    run_weekday: WEEKDAYS = Field(default="", description="The day of a weekly run; empty for any.")


def _line(value) -> str:
    return " ".join(str(value or "").split())


def _default_outlook(store):
    def outlook(uid, chat_id):
        from app.core.security import get_user_tier
        from app.services import agent_watches
        return agent_watches.outlook(uid, chat_id, get_user_tier(uid), db=store.db)
    return outlook


def _save_on_turn(loop, field, value, *, merge=False):
    """``value`` on the running turn's ``field``; refused once it has ended."""
    from app.services import persistence_guard
    store = loop.store
    chat_ref = store._chat_ref(loop.uid, loop.chat_id)
    turn_ref = store._turn_ref(loop.uid, loop.chat_id, loop.turn_id)

    def operation(tx):
        persistence_guard.ensure_account_write_allowed(uid=loop.uid, db=store.db, transaction=tx)
        chat, turn = chat_ref.get(transaction=tx), turn_ref.get(transaction=tx)
        data = (turn.to_dict() or {}) if turn.exists else {}
        if (data.get("status") != "pending" or not chat.exists
                or (chat.to_dict() or {}).get("status") != "active"):
            raise ValueError("This answer has already finished. Nothing was saved.")
        current = data.get(field) if isinstance(data.get(field), dict) else {}
        tx.update(turn_ref, {field: {**current, **value} if merge else value})

    store._transaction(operation)


class WatchTools:
    """The ``prepare_watch`` tool of one Agent turn.

    ``loop.watch_proposal`` holds the latest proposal.
    """

    def __init__(self, loop, *, outlook=None):
        self.loop = loop
        self.outlook = outlook or _default_outlook(loop.store)

    def tools(self):
        from app.services.agent_tools import ReadOnlyTool
        return [ReadOnlyTool(
            "prepare_watch",
            "Prepare a Watch: you run again on a schedule in this chat and email the user when a run finds "
            "something new for them. Nothing starts until the user confirms the card below the answer.",
            PrepareWatch, self.prepare)]

    def prepare(self, args, *, cancellation=None):
        if cancellation is not None:
            cancellation.raise_if_cancelled()
        task = _line(args.task)
        if len(task) < TASK_MIN_CHARS:
            raise ValueError("Write the Watch's task as a complete sentence.")
        loop = self.loop
        try:
            outlook = self.outlook(loop.uid, loop.chat_id)
        except Exception as exc:
            # Only the category: the task is the user's text.
            logging.warning("agent watch outlook failed category=%s", type(exc).__name__)
            raise ValueError("Watches cannot be prepared right now. Answer without one and say so briefly.") from None
        interval, note = args.interval, None
        allowed = outlook.get("intervals") or ["daily", "weekly"]
        if interval not in allowed:
            interval = allowed[0]
            note = f"Runs that often are not available on this account; the card proposes {interval.replace('_', ' ')}."
        status = ("already_watched" if outlook["already_watched"]
                  else "limit_reached" if outlook["limit_reached"] else "prepared")
        timed = interval in {"daily", "weekly"}
        proposal = {"task": task, "goal": _line(args.goal).strip(" ."), "interval": interval,
                    "run_time": args.run_time if timed else "",
                    "run_weekday": args.run_weekday if interval == "weekly" else ""}
        try:
            _save_on_turn(loop, "agent_watch", proposal)
        except ValueError:
            raise
        except Exception as exc:
            # Firestore down, contention, account deletion: a proposal that
            # cannot be saved must never fail the paid turn it rides on.
            logging.warning("agent watch proposal not saved category=%s", type(exc).__name__)
            raise ValueError("The Watch could not be prepared right now. Answer without it and say so briefly.") from None
        loop.watch_proposal = {**proposal, "status": status}
        result = {"status": status, **proposal, "instruction": INSTRUCTIONS[status]}
        if note:
            result["note"] = note
        return result

    def mock_turn(self, question: str) -> None:
        """MOCK_LLM only: "Watch: <task>" prepares a Watch, for browser tests of the card."""
        match = re.match(r"^\s*watch:\s*(.{8,500})$", str(question or ""), re.IGNORECASE | re.DOTALL)
        if not match:
            return
        try:
            self.prepare(PrepareWatch(task=match.group(1).strip(), goal="It is officially announced"))
        except ValueError:
            logging.info("mock watch proposal refused")


class ReportFinding(Strict):
    summary: str = Field(
        min_length=3, max_length=600,
        description="What is new for the user, in one or two sentences in their language: the email's first line.")
    evidence_url: str = Field(
        min_length=8, max_length=URL_MAX_CHARS,
        description="The address of a page you opened or found in this run that shows it.")
    needs_user: bool = Field(
        default=False, description="True when the user has to do or decide something; the summary says what.")


class FinishWatch(Strict):
    reason: str = Field(min_length=3, max_length=REASON_MAX_CHARS,
                        description="Why the Watch's goal is met, in one sentence in the user's language.")


def _bare(url) -> str:
    """An address as compared: no fragment, no trailing slash."""
    return str(url or "").split("#", 1)[0].rstrip("/")


def _content_text(content) -> str:
    return content if isinstance(content, str) else json.dumps(content, ensure_ascii=False, default=str)


class WatchRunTools:
    """``report_finding`` and ``finish_watch`` of one scheduled run."""

    def __init__(self, loop):
        self.loop = loop

    def tools(self):
        from app.services.agent_tools import ReadOnlyTool
        return [
            ReadOnlyTool("report_finding",
                         "Tell the user what this Watch run found for them, with the page you saw it on. "
                         "They get it by email once this run ends.", ReportFinding, self.report),
            ReadOnlyTool("finish_watch", "End this Watch: its goal is met. No further runs.",
                         FinishWatch, self.finish),
        ]

    def evidence(self, url: str) -> dict | None:
        """The source behind ``url`` when this run saw it: a search result of
        this message or an address in one of its tool results; never one only
        from the chat or the model's own text (agent_read_source principle)."""
        wanted = _bare(url)
        if not wanted.startswith(("http://", "https://")):
            return None
        loop = self.loop
        for source in loop.search_sources:
            if isinstance(source, dict) and _bare(source.get("url")) == wanted:
                return {"url": str(source.get("url")), "title": _line(source.get("title"))[:240]}
        for message in loop.own_messages():
            if message.get("role") == "tool" and wanted in _content_text(message.get("content")):
                return {"url": url, "title": ""}
        return None

    def report(self, args, *, cancellation=None):
        if cancellation is not None:
            cancellation.raise_if_cancelled()
        source = self.evidence(args.evidence_url)
        if source is None:
            raise ValueError("Report only with a page you opened or found in this run: open it first, "
                             "then report with its address.")
        finding = {"summary": _line(args.summary), "evidence_url": source["url"],
                   "evidence_title": source["title"], "needs_user": bool(args.needs_user)}
        try:
            _save_on_turn(self.loop, "agent_watch_run", {"finding": finding}, merge=True)
        except ValueError:
            raise
        except Exception as exc:
            logging.warning("agent watch finding not saved category=%s", type(exc).__name__)
            raise ValueError("The finding could not be saved right now. Say it in your answer.") from None
        return {"status": "reported", "instruction": "The user gets this by email once this run ends. "
                                                     "Answer briefly with what you found."}

    def finish(self, args, *, cancellation=None):
        if cancellation is not None:
            cancellation.raise_if_cancelled()
        try:
            _save_on_turn(self.loop, "agent_watch_run", {"done": {"reason": _line(args.reason)}}, merge=True)
        except ValueError:
            raise
        except Exception as exc:
            logging.warning("agent watch end not saved category=%s", type(exc).__name__)
            raise ValueError("The Watch could not be ended right now. Say so in your answer.") from None
        return {"status": "finished", "instruction": "No further runs. The user is told by email."}

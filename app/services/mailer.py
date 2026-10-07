"""Small async SMTP service for Consensus Watch notifications."""

from __future__ import annotations

import asyncio
import html
import logging
import os
import re
import smtplib
import ssl
from email.message import EmailMessage
from urllib.parse import urlsplit
from datetime import datetime, timezone

from app.core.observability import safe_exception
from app.services.llm.mock_llm import mock_llm_enabled


def _smtp_config():
    values = {
        "host": os.environ.get("SMTP_HOST", "").strip(),
        "user": os.environ.get("SMTP_USER", "").strip(),
        "password": os.environ.get("SMTP_PASSWORD", "").strip(),
        "sender": os.environ.get("MAIL_FROM", "").strip(),
    }
    try:
        values["port"] = int(os.environ.get("SMTP_PORT", "587"))
    except ValueError:
        values["port"] = 587
    return values


def is_configured() -> bool:
    config = _smtp_config()
    return bool(config["host"] and config["sender"])


def _deliver(message: EmailMessage) -> bool:
    config = _smtp_config()
    # Last line of defence: a mock instance often inherits the real SMTP
    # credentials from .env, so never let fixture content reach a recipient.
    if mock_llm_enabled():
        logging.info("Mail skipped: MOCK_LLM=1")
        return False
    if not is_configured():
        logging.info("Consensus Watch mail skipped: SMTP_HOST/MAIL_FROM not configured")
        return False
    try:
        if config["port"] == 465:
            with smtplib.SMTP_SSL(config["host"], config["port"], context=ssl.create_default_context(), timeout=30) as smtp:
                if config["user"]:
                    smtp.login(config["user"], config["password"])
                smtp.send_message(message)
        else:
            with smtplib.SMTP(config["host"], config["port"], timeout=30) as smtp:
                smtp.ehlo()
                smtp.starttls(context=ssl.create_default_context())
                smtp.ehlo()
                if config["user"]:
                    smtp.login(config["user"], config["password"])
                smtp.send_message(message)
        return True
    except Exception as exc:
        logging.error(
            "Consensus Watch mail delivery failed category=%s",
            safe_exception(exc),
        )
        return False


async def send_message(message: EmailMessage) -> bool:
    return await asyncio.to_thread(_deliver, message)


def _base_message(recipient: str, subject: str, plain: str, html_body: str) -> EmailMessage:
    message = EmailMessage()
    message["From"] = _smtp_config()["sender"] or "consens.io"
    message["To"] = recipient
    message["Subject"] = subject
    message.set_content(plain)
    message.add_alternative(html_body, subtype="html")
    return message


# ---------------------------------------------------------------------------
# Shared building blocks
#
# Every notification answers the same questions in the same order: what
# changed, by how much, and what was asked. The helpers below keep that
# structure identical across all mails (and mirror what telegram_watch.py
# sends), so the first three lines are enough to understand the message.
# Long questions are clipped like the pages clamp them — the full text is
# always one click away.
# ---------------------------------------------------------------------------

INK = "#172033"
INK_SOFT = "#3d4759"
MUTED = "#667085"
PANEL = "#f3f6fb"
BORDER = "#d8deea"
ACCENT = "#335cff"
QUESTION_PREVIEW_CHARS = 200

_EYEBROW_STYLE = (
    f"margin:0;font-size:12px;font-weight:700;letter-spacing:.08em;"
    f"text-transform:uppercase;color:{MUTED}"
)
_FONT_STACK = "-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif"


# Typographic characters would force the whole plain-text part into base64,
# where URLs stop being clickable in text-only clients. The plain half stays
# ASCII wherever we control the wording.
_PLAIN_ASCII = str.maketrans({
    "→": "->", "←": "<-", "−": "-", "–": "-", "—": "-", "…": "...", "·": "-",
    "↑": "up", "↓": "down",
})


def _normalized(value) -> str:
    return " ".join(str(value or "").split())


def _ascii(text: str) -> str:
    return str(text or "").translate(_PLAIN_ASCII)


def _question_view(question, *, limit: int = QUESTION_PREVIEW_CHARS) -> tuple[str, bool]:
    """Collapse a long question to a readable opening; True = it was cut."""
    text = _normalized(question)
    if len(text) <= limit:
        return text, False
    cut = text[:limit]
    space = cut.rfind(" ")
    if space > limit * 0.6:
        cut = cut[:space]
    return cut.rstrip(" ,;:.–-") + "…", True


def _split_lead(summary) -> tuple[str, str]:
    """First sentence carries the change; the rest is detail."""
    text = _normalized(summary)
    if not text:
        return "", ""
    match = re.search(r"(?<=[.!?])\s+", text)
    if not match or match.start() > 180:
        return text, ""
    return text[:match.start()], text[match.end():]


def _question_html(question, url: str, *, label: str = "Question") -> str:
    text, truncated = _question_view(question)
    more = (
        f'<p style="margin:6px 0 0;font-size:13px"><a href="{html.escape(url)}" '
        f'style="color:{MUTED}">Read the full question</a></p>'
        if truncated and url else ""
    )
    return (
        f'<p style="{_EYEBROW_STYLE}">{html.escape(label)}</p>'
        f'<p style="margin:5px 0 0;font-size:17px;font-weight:600;line-height:1.4;color:{INK}">'
        f"{html.escape(text)}</p>{more}"
    )


def _question_plain(question, *, label: str = "QUESTION") -> str:
    text, _truncated = _question_view(question)
    return _ascii(f"{label}\n{text}")


def _change_block_html(label: str, summary, *, notable: bool = True) -> str:
    """The heart of the mail: what actually changed, not buried in prose."""
    lead, rest = _split_lead(summary)
    if not lead:
        return ""
    rule = ACCENT if notable else BORDER
    detail = (
        f'<p style="margin:8px 0 0;font-size:15px;color:{INK_SOFT}">{html.escape(rest)}</p>'
        if rest else ""
    )
    return (
        f'<div style="margin:18px 0;padding:2px 0 2px 14px;border-left:3px solid {rule}">'
        f'<p style="{_EYEBROW_STYLE}">{html.escape(label)}</p>'
        f'<p style="margin:6px 0 0;font-size:17px;font-weight:600;line-height:1.45;color:{INK}">'
        f"{html.escape(lead)}</p>{detail}</div>"
    )


def _change_block_plain(label: str, summary) -> str:
    lead, rest = _split_lead(summary)
    if not lead:
        return ""
    return _ascii(f"{label.upper()}\n{lead}" + (f"\n{rest}" if rest else ""))


def _button_html(url: str, label: str) -> str:
    return (
        f'<p style="margin:22px 0 0"><a href="{html.escape(url)}" '
        f'style="display:inline-block;background:{ACCENT};color:#fff;text-decoration:none;'
        f'padding:12px 18px;border-radius:8px;font-weight:600">{html.escape(label)}</a></p>'
    )


def _shell_html(*, eyebrow: str, heading: str, preheader: str, body: str,
                footer: str, width: int = 620) -> str:
    return (
        f'<!doctype html><html><body style="margin:0;background:#ffffff;'
        f'font-family:{_FONT_STACK};color:{INK};line-height:1.55">'
        f'<div style="display:none;max-height:0;overflow:hidden;opacity:0;color:transparent">'
        f"{html.escape(preheader)}</div>"
        f'<div style="max-width:{width}px;margin:auto;padding:24px">'
        f'<p style="{_EYEBROW_STYLE}">{html.escape(eyebrow)}</p>'
        f'<h1 style="margin:4px 0 0;font-size:23px;line-height:1.3;color:{INK}">'
        f"{html.escape(heading)}</h1>"
        f"{body}"
        f'<p style="font-size:12px;color:{MUTED};margin-top:32px">{footer}</p>'
        "</div></body></html>"
    )


def _subject_clip(text, limit: int = 72) -> str:
    clipped = _normalized(text)
    return clipped[:limit] + ("…" if len(clipped) > limit else "")


# Why a check moved, in the words of the evidence model
# (docs/watch-evidence-model.md). A cause without a sentence is not shown.
_CAUSE_SENTENCES = {
    "new_evidence": "New evidence: a source the earlier answer did not have.",
    "reassessment": (
        "Same evidence, read differently by the models, and a second check "
        "confirmed that reading before this message was sent."
    ),
    "model_change": (
        "The answering models changed, and a second check confirmed the new "
        "reading before this message was sent."
    ),
}


def _host(url: str) -> str:
    return (urlsplit(str(url or "")).hostname or "").lower().removeprefix("www.")


def _clean_sources(sources) -> list[dict]:
    clean = []
    for item in sources or []:
        if isinstance(item, dict) and str(item.get("url") or "").startswith(("http://", "https://")):
            clean.append({
                "title": _normalized(item.get("title"))[:160] or _host(item["url"]),
                "url": str(item["url"]),
            })
    return clean[:4]


def _why_html(cause, sources) -> str:
    sentence = _CAUSE_SENTENCES.get(str(cause or ""))
    items = _clean_sources(sources)
    if not sentence and not items:
        return ""
    links = "".join(
        f'<li style="margin:4px 0"><a href="{html.escape(item["url"])}" '
        f'style="color:{INK}">{html.escape(item["title"])}</a> '
        f'<span style="color:{MUTED}">· {html.escape(_host(item["url"]))}</span></li>'
        for item in items
    )
    return (
        f'<div style="margin:18px 0 0">'
        f'<p style="{_EYEBROW_STYLE}">Why</p>'
        + (f'<p style="margin:5px 0 0;color:{INK_SOFT}">{html.escape(sentence)}</p>' if sentence else "")
        + (f'<ul style="margin:8px 0 0;padding-left:18px">{links}</ul>' if links else "")
        + "</div>"
    )


def _why_plain(cause, sources) -> str:
    sentence = _CAUSE_SENTENCES.get(str(cause or ""))
    items = _clean_sources(sources)
    if not sentence and not items:
        return ""
    lines = ["WHY"] + ([sentence] if sentence else [])
    lines += [f"- {item['title']} ({item['url']})" for item in items]
    return _ascii("\n".join(lines))


def _held_html(held) -> str:
    text = _normalized(held)
    if not text:
        return ""
    return (
        f'<div style="margin:18px 0 0"><p style="{_EYEBROW_STYLE}">What held</p>'
        f'<p style="margin:5px 0 0;color:{INK_SOFT}">{html.escape(text)}</p></div>'
    )


def _held_plain(held) -> str:
    text = _normalized(held)
    return _ascii(f"WHAT HELD\n{text}") if text else ""


def _goal_html(goal, status_line) -> str:
    goal = _normalized(goal)
    if not goal:
        return ""
    return (
        f'<div style="margin:18px 0 0;padding:14px 16px;background:{PANEL};border-radius:12px">'
        f'<p style="{_EYEBROW_STYLE}">Waiting for</p>'
        f'<p style="margin:5px 0 0;font-weight:600;color:{INK}">{html.escape(goal)}</p>'
        + (
            f'<p style="margin:4px 0 0;font-size:14px;color:{MUTED}">{html.escape(status_line)}</p>'
            if status_line else ""
        )
        + "</div>"
    )


def _goal_plain(goal, status_line) -> str:
    goal = _normalized(goal)
    if not goal:
        return ""
    return _ascii(f"WAITING FOR\n{goal}" + (f"\n{status_line}" if status_line else ""))


def _goal_status_line(delta: dict) -> str:
    reason = _normalized(delta.get("goal_reason"))
    if delta.get("goal_status") == "not_met":
        return "Not yet. " + reason if reason else "Not yet."
    if delta.get("goal_status") == "met":
        return "Reported met, re-checking before the watch closes."
    return reason


def _delta_parts(delta: dict, *, notable: bool = True) -> tuple[str, str]:
    """The change log every Watch and follower mail is built from.

    What changed, why (with the sources that carry it), what held, and where
    the goal stands. No agreement score: it steps between fixed grades and
    is not a reason to write to anyone.
    """
    summary = delta.get("summary") or ""
    goal_line = _goal_status_line(delta)
    html_part = (
        _change_block_html("What changed", summary, notable=notable)
        + _why_html(delta.get("cause"), delta.get("sources"))
        + _held_html(delta.get("held"))
        + _goal_html(delta.get("goal"), goal_line)
    )
    plain_part = "\n\n".join(part for part in (
        _change_block_plain("What changed", summary),
        _why_plain(delta.get("cause"), delta.get("sources")),
        _held_plain(delta.get("held")),
        _goal_plain(delta.get("goal"), goal_line),
    ) if part)
    return html_part, plain_part


def build_change_message(*, recipient: str, question: str, delta: dict,
                         share_url: str, unsubscribe_url: str) -> EmailMessage:
    subject = f"Moved: {_subject_clip(question)}"
    lead, _rest = _split_lead(delta.get("summary"))
    delta_html, delta_plain = _delta_parts(delta)
    plain = (
        "Your Consensus Watch found a change backed by evidence.\n\n"
        + delta_plain + "\n\n"
        + _question_plain(question) + "\n\n"
        f"See what changed: {share_url}\nPause this watch: {unsubscribe_url}\n"
    )
    body = (
        delta_html
        + f'<div style="margin-top:22px">{_question_html(question, share_url)}</div>'
        + _button_html(share_url, "See what changed")
    )
    html_body = _shell_html(
        eyebrow="Consensus Watch · Moved",
        heading="The answer moved",
        preheader=lead or "A watched question moved on new evidence.",
        body=body,
        footer=(
            "Consensus Watch only writes when a change is backed by a source or "
            "confirmed by a second check. "
            f'<a href="{html.escape(unsubscribe_url)}">Pause this watch</a>.'
        ),
    )
    return _base_message(recipient, subject, plain, html_body)


def build_run_message(*, recipient: str, question: str, delta: dict, moved: bool,
                      consensus: str, share_url: str, unsubscribe_url: str) -> EmailMessage:
    """Full-content notification for users who opted into every successful run."""
    subject = f"New check: {_subject_clip(question)}"
    consensus_text = str(consensus or "").strip()
    if not moved:
        delta = {**delta, "summary": "Nothing moved on evidence in this check.", "cause": "", "sources": []}
    delta_html, delta_plain = _delta_parts(delta, notable=moved)
    plain = (
        "Consensus Watch completed a new check.\n\n"
        + delta_plain + "\n\n"
        + _question_plain(question) + "\n\n"
        f"THE ANSWER\n\n{consensus_text}\n\n"
        f"View history: {share_url}\nPause this watch: {unsubscribe_url}\n"
    )
    safe_consensus = html.escape(consensus_text).replace("\n", "<br>")
    body = (
        delta_html
        + f'<div style="margin-top:22px">{_question_html(question, share_url)}</div>'
        + f'<div style="margin-top:20px;padding:18px;border:1px solid {BORDER};border-radius:12px">'
        f'<p style="{_EYEBROW_STYLE}">The answer</p>'
        f'<div style="margin-top:8px;color:{INK_SOFT}">{safe_consensus}</div></div>'
        + _button_html(share_url, "View watch page and history")
    )
    html_body = _shell_html(
        eyebrow="Consensus Watch · Completed check",
        heading="The answer moved" if moved else "Checked again",
        preheader=_split_lead(delta.get("summary"))[0],
        body=body,
        footer=(
            "You chose to receive every check. "
            f'<a href="{html.escape(unsubscribe_url)}">Pause this watch</a>.'
        ),
        width=680,
    )
    return _base_message(recipient, subject, plain, html_body)


def build_condition_message(*, recipient: str, question: str, goal: str, reason: str,
                            sources, consensus: str, share_url: str,
                            unsubscribe_url: str) -> EmailMessage:
    """Sent once, when the goal a watch was waiting for is met on evidence."""
    clipped_goal = _normalized(goal)[:500]
    clipped_reason = _normalized(reason)[:400]
    subject = f"Resolved: {_subject_clip(clipped_goal)}"
    consensus_text = str(consensus or "").strip()
    items = _clean_sources(sources)
    plain = "\n\n".join(part for part in (
        "The goal your Consensus Watch was waiting for is met. The watch is complete.",
        _goal_plain(clipped_goal, ""),
        _change_block_plain("Why", clipped_reason),
        _why_plain("", items),
        _question_plain(question),
        f"THE ANSWER\n\n{consensus_text}" if consensus_text else "",
        f"Open the watch: {share_url}",
    ) if part) + "\n"
    safe_consensus = html.escape(consensus_text).replace("\n", "<br>")
    body = (
        _goal_html(clipped_goal, "")
        + _change_block_html("Why", clipped_reason)
        + _why_html("", items)
        + f'<div style="margin-top:22px">{_question_html(question, share_url)}</div>'
        + (
            f'<div style="margin-top:20px;padding:18px;border:1px solid {BORDER};border-radius:12px">'
            f'<p style="{_EYEBROW_STYLE}">The answer</p>'
            f'<div style="margin-top:8px;color:{INK_SOFT}">{safe_consensus}</div></div>'
            if consensus_text else ""
        )
        + _button_html(share_url, "Open the watch")
    )
    html_body = _shell_html(
        eyebrow="Consensus Watch · Resolved",
        heading="What you were waiting for happened",
        preheader=_split_lead(clipped_reason)[0] or clipped_goal,
        body=body,
        footer=(
            "The watch stopped checking and freed its slot. Open it to watch for "
            "something new."
        ),
        width=680,
    )
    return _base_message(recipient, subject, plain, html_body)


def build_follow_confirm_message(*, recipient: str, question: str,
                                 confirm_url: str, share_url: str) -> EmailMessage:
    """Double-Opt-in: einmalige Bestätigungs-Mail für Seiten-Follower."""
    clipped_question = _normalized(question)
    subject_question = clipped_question[:72] + ("…" if len(clipped_question) > 72 else "")
    subject = f"Confirm: follow \"{subject_question}\""
    plain = (
        "Confirm that you want to follow this question on consens.io.\n\n"
        + _question_plain(question) + "\n\n"
        "You will get one e-mail whenever the AI consensus shifts materially.\n"
        f"Confirm: {confirm_url}\n\n"
        f"Page: {share_url}\n"
        "If you did not request this, simply ignore this e-mail — nothing is stored.\n"
    )
    body = (
        f'<div style="margin-top:16px">{_question_html(question, share_url)}</div>'
        f'<p style="margin:14px 0 0;color:{INK_SOFT}">You will get one e-mail whenever the '
        "AI consensus shifts materially — no account needed.</p>"
        + _button_html(confirm_url, "Confirm and follow")
    )
    html_body = _shell_html(
        eyebrow="consens.io · Confirmation needed",
        heading="Follow this question?",
        preheader="One click confirms; we only write when the consensus moves.",
        body=body,
        footer=(
            "If you did not request this, simply ignore this e-mail — nothing is stored. "
            f'<a href="{html.escape(share_url)}">Open the page</a>.'
        ),
    )
    return _base_message(recipient, subject, plain, html_body)


def build_topic_follow_confirm_message(*, recipient: str, title: str,
                                       confirm_url: str, topic_url: str) -> EmailMessage:
    """Double opt-in confirmation for the independent curated Topics area."""
    clipped_title = " ".join(str(title or "").split())
    subject_title = clipped_title[:72] + ("…" if len(clipped_title) > 72 else "")
    subject = f'Confirm: follow "{subject_title}"'
    plain = (
        "Confirm that you want to follow this topic on consens.io.\n\n"
        f"{clipped_title}\n\n"
        "You will receive an e-mail when the curated consensus changes materially.\n"
        f"Confirm: {confirm_url}\n\n"
        f"Topic: {topic_url}\n"
        "If you did not request this, ignore this e-mail; nothing is stored.\n"
    )
    safe_title = html.escape(clipped_title)
    safe_confirm = html.escape(confirm_url)
    safe_topic = html.escape(topic_url)
    html_body = f"""<!doctype html><html><body style="font-family:Arial,sans-serif;color:#172033;line-height:1.55">
<div style="max-width:620px;margin:auto;padding:24px"><h1 style="font-size:22px">Follow this topic?</h1>
<p style="font-size:17px;font-weight:600">{safe_title}</p>
<p>You will receive an e-mail when the curated AI consensus changes materially.</p>
<p><a href="{safe_confirm}" style="display:inline-block;background:#335cff;color:#fff;text-decoration:none;padding:12px 18px;border-radius:8px">Confirm and follow</a></p>
<p style="font-size:12px;color:#667085;margin-top:32px">If you did not request this, ignore this e-mail; nothing is stored. <a href="{safe_topic}">Open the topic</a>.</p>
</div></body></html>"""
    return _base_message(recipient, subject, plain, html_body)


def build_topic_change_message(*, recipient: str, title: str, question: str,
                               delta: dict, topic_url: str,
                               unsubscribe_url: str) -> EmailMessage:
    """Material-change notification for a confirmed Topic follower."""
    clipped_title = _normalized(title)
    subject = f"Topic update: {_subject_clip(clipped_title)}"
    lead, _rest = _split_lead(delta.get("summary"))
    delta_html, delta_plain = _delta_parts(delta)
    plain = (
        f"The curated consensus moved.\n\n{clipped_title}\n\n"
        + delta_plain + "\n\n"
        + _question_plain(question) + "\n\n"
        f"Open the timeline: {topic_url}\nUnfollow: {unsubscribe_url}\n"
    )
    body = (
        delta_html
        + f'<div style="margin-top:22px">{_question_html(question, topic_url, label="Tracked question")}</div>'
        + _button_html(topic_url, "Open the timeline")
    )
    html_body = _shell_html(
        eyebrow="consens.io · Curated topic update",
        heading=clipped_title,
        preheader=lead or "The curated consensus moved.",
        body=body,
        footer=(
            "You follow this curated topic on consens.io. "
            f'<a href="{html.escape(unsubscribe_url)}">Unfollow</a>.'
        ),
    )
    return _base_message(recipient, subject, plain, html_body)


def build_follower_change_message(*, recipient: str, question: str, delta: dict,
                                  share_url: str, unsubscribe_url: str) -> EmailMessage:
    """Änderungs-Mail an bestätigte Seiten-Follower (nicht den Watch-Owner)."""
    subject = f"The AI consensus moved: {_subject_clip(question)}"
    lead, _rest = _split_lead(delta.get("summary"))
    # The goal belongs to the owner; followers subscribed to the question.
    delta_html, delta_plain = _delta_parts({**delta, "goal": ""})
    plain = (
        "A question you follow on consens.io moved.\n\n"
        + delta_plain + "\n\n"
        + _question_plain(question) + "\n\n"
        f"See what changed: {share_url}\nUnfollow: {unsubscribe_url}\n"
    )
    body = (
        delta_html
        + f'<div style="margin-top:22px">{_question_html(question, share_url)}</div>'
        + _button_html(share_url, "See what changed")
    )
    html_body = _shell_html(
        eyebrow="consens.io · Question you follow",
        heading="The AI consensus moved",
        preheader=lead or "A question you follow moved.",
        body=body,
        footer=(
            "You follow this question on consens.io. "
            f'<a href="{html.escape(unsubscribe_url)}">Unfollow</a>.'
        ),
    )
    return _base_message(recipient, subject, plain, html_body)


def build_paused_message(*, recipient: str, question: str, share_url: str,
                         unsubscribe_url: str) -> EmailMessage:
    subject = "Consensus Watch paused after repeated errors"
    plain = (
        "Your watch was paused after three failed checks.\n\n"
        + _question_plain(question) + f"\n\n{share_url}\nUnsubscribe: {unsubscribe_url}\n"
    )
    body = (
        f'<p style="margin:14px 0 0;color:{INK_SOFT}">We could not complete three consecutive '
        "checks, so this watch was paused automatically. Nothing was lost — resuming it "
        "continues the same history.</p>"
        f'<div style="margin-top:16px">{_question_html(question, share_url)}</div>'
        + _button_html(share_url, "Open the consensus page")
    )
    html_body = _shell_html(
        eyebrow="Consensus Watch · Paused",
        heading="This watch was paused",
        preheader="Three consecutive checks failed.",
        body=body,
        footer=f'<a href="{html.escape(unsubscribe_url)}">Pause/unsubscribe</a>',
    )
    return _base_message(recipient, subject, plain, html_body)


def _brief_status_label(status: str) -> str:
    return {
        "active": "Active",
        "paused": "Paused",
        "paused_error": "Paused after errors",
        "resolved": "Resolved",
    }.get(status, "Paused")


def _brief_summaries(item: dict) -> list:
    summaries = []
    resolution = item.get("resolution") or {}
    if resolution:
        summaries.append(
            "Resolved: " + (_normalized(resolution.get("reason")) or _normalized(item.get("goal")))
        )
    summaries += [
        _normalized(point.get("change_summary"))
        for point in (item.get("new_points") or [])
        if point.get("notable") and point.get("change_summary")
    ]
    return summaries


def _brief_goal_line(item: dict) -> str:
    goal = _normalized(item.get("goal"))
    if not goal:
        return "Watching for any change on evidence"
    return "Waiting for: " + (goal[:90] + "…" if len(goal) > 90 else goal)


def build_brief_message(*, recipient: str, date_label: str, items: list,
                        changes_count: int, site_url: str,
                        unsubscribe_url: str) -> EmailMessage:
    """Daily digest over all watches of one user (no per-watch mail replaced)."""
    watch_count = len(items)
    subject = (
        f"Morning brief: {changes_count} change{'s' if changes_count != 1 else ''} "
        f"across {watch_count} watch{'es' if watch_count != 1 else ''}"
        if changes_count else
        f"Morning brief: your {watch_count} watch{'es' if watch_count != 1 else ''}, no material changes"
    )
    plain_rows, html_rows = [], []
    # Watches that actually moved come first: the digest is scanned top-down
    # and a quiet week should never bury the one line that matters.
    for item in sorted(items, key=lambda entry: not _brief_summaries(entry)):
        question, _truncated = _question_view(item.get("question"), limit=150)
        plain_question = _ascii(question)
        status_label = _brief_status_label(str(item.get("status") or ""))
        goal_line = _brief_goal_line(item)
        url = site_url + str(item.get("share_path") or "")
        schedule = str(item.get("interval") or "").capitalize()
        if item.get("interval") == "weekly" and item.get("run_weekday"):
            schedule += f" on {str(item['run_weekday']).capitalize()}"
        if item.get("run_time") and item.get("timezone"):
            schedule += f" at {item['run_time']} ({item['timezone']})"
        summaries = _brief_summaries(item)
        plain = _ascii(f"- {plain_question}\n  {status_label} · {goal_line} · {schedule}\n")
        for summary in summaries[:3]:
            plain += f"  CHANGED: {summary}\n"
        if not summaries:
            plain += "  No material change.\n"
        plain += f"  {url}\n"
        plain_rows.append(plain)

        safe_question = html.escape(question)
        safe_url = html.escape(url)
        change_html = "".join(
            f'<p style="margin:9px 0 0;padding-left:11px;border-left:3px solid {ACCENT};'
            f'font-size:14px;color:{INK}"><strong>Changed.</strong> {html.escape(summary)}</p>'
            for summary in summaries[:3]
        )
        html_rows.append(
            f'<div style="margin:0 0 14px;padding:14px 16px;border:1px solid {BORDER};border-radius:12px">'
            f'<p style="margin:0;font-weight:600"><a href="{safe_url}" '
            f'style="color:{INK};text-decoration:none">{safe_question}</a></p>'
            f'<p style="margin:6px 0 0;font-size:13px;color:{MUTED}">{html.escape(status_label)} · '
            f"{html.escape(goal_line)} · {html.escape(schedule)}</p>"
            f"{change_html}"
            f"</div>"
        )
    plain = (
        f"Your Consensus Watch morning brief - {date_label}\n\n"
        + ("\n".join(plain_rows) if plain_rows else "You have no watches yet.\n")
        + f"\nOpen consens.io: {site_url}/app\nUnsubscribe from this brief: {unsubscribe_url}\n"
    )
    intro = (
        f"{changes_count} notable change{'s' if changes_count != 1 else ''} since your last brief."
        if changes_count else "No material changes since your last brief."
    )
    body = (
        f'<p style="margin:6px 0 18px;color:{MUTED}">{html.escape(date_label)} · '
        f"{html.escape(intro)}</p>"
        + "".join(html_rows)
        + _button_html(f"{site_url}/app", "Open your watch dashboard")
    )
    html_body = _shell_html(
        eyebrow="Consensus Watch · Morning brief",
        heading="Your consensus morning brief",
        preheader=intro,
        body=body,
        footer=(
            "You receive this daily digest because you enabled the Morning Brief. "
            f'<a href="{html.escape(unsubscribe_url)}">Unsubscribe from the brief</a> '
            "— individual watch alerts are unaffected."
        ),
        width=680,
    )
    return _base_message(recipient, subject, plain, html_body)


def build_account_setup_message(*, recipient: str, setup_url: str) -> EmailMessage:
    """Sign-up mail: choose a password. Replaces Firebase's "Reset your
    password" template, which this project cannot edit."""
    plain = (
        "Welcome to consens.io!\n\n"
        "One step left: choose a password for your account.\n"
        f"{setup_url}\n\n"
        "The next page is our login provider's standard page and is titled\n"
        "\"Reset your password\" - that's the right place. Afterwards you are\n"
        "taken straight back to consens.io.\n\n"
        "The link works for one hour. Didn't sign up? Just ignore this e-mail.\n"
    )
    body = (
        f'<p style="margin:14px 0 0;color:{INK_SOFT}">Thanks for signing up. Choose a '
        "password and you're in.</p>"
        + _button_html(setup_url, "Choose my password")
        + f'<p style="margin:18px 0 0;font-size:14px;color:{MUTED}">The next page is our '
        "login provider's standard page and is titled “Reset your password” – that's "
        "the right place. Afterwards you are taken straight back to consens.io.</p>"
    )
    html_body = _shell_html(
        eyebrow="consens.io",
        heading="One step left: choose your password",
        preheader="Choose a password and you're in.",
        body=body,
        footer="The link works for one hour. Didn't sign up? Just ignore this e-mail.",
    )
    return _base_message(recipient, "Finish setting up your consens.io account", plain, html_body)


def build_existing_account_message(*, recipient: str, login_url: str,
                                   reset_url: str) -> EmailMessage:
    """Sign-up with an address that already has an account. The sign-up form
    answers identically either way; only the mailbox owner learns this."""
    plain = (
        "Someone - probably you - just signed up on consens.io with this address,\n"
        "but it already has an account.\n\n"
        f"Log in as usual (with Google or your password): {login_url}\n\n"
        f"Forgot your password? Set a new one (link works for one hour):\n{reset_url}\n\n"
        "Didn't do this? Just ignore this e-mail - nothing has changed.\n"
    )
    body = (
        f'<p style="margin:14px 0 0;color:{INK_SOFT}">Someone – probably you – just signed '
        "up with this address, but it already has an account. Log in as usual, with "
        "Google or your password.</p>"
        + _button_html(login_url, "Log in")
        + f'<p style="margin:18px 0 0;font-size:14px;color:{MUTED}">Forgot your password? '
        f'<a href="{html.escape(reset_url)}" style="color:{INK}">Set a new one</a> '
        "(link works for one hour).</p>"
    )
    html_body = _shell_html(
        eyebrow="consens.io",
        heading="You already have an account",
        preheader="Log in as usual – or set a new password.",
        body=body,
        footer="Didn't do this? Just ignore this e-mail – nothing has changed.",
    )
    return _base_message(recipient, "You already have a consens.io account", plain, html_body)


def deliver_now(message: EmailMessage) -> bool:
    """Synchronous delivery for callers already off the event loop."""
    return _deliver(message)


def build_test_message(*, recipient: str) -> EmailMessage:
    """Small delivery probe used only by the authenticated admin endpoint."""
    sent_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    plain = (
        "Consensus Watch e-mail delivery is configured correctly.\n\n"
        f"This test was requested from the admin dashboard at {sent_at}.\n"
        "No watch was executed and no schedule was changed.\n"
    )
    html_body = f"""<!doctype html><html><body style="font-family:Arial,sans-serif;color:#172033;line-height:1.55">
<div style="max-width:620px;margin:auto;padding:24px"><h1 style="font-size:22px">Consensus Watch test successful</h1>
<p>The application connected to SMTP and submitted this message successfully.</p>
<p style="color:#667085">Requested from the admin dashboard at {html.escape(sent_at)}. No watch was executed and no schedule was changed.</p>
</div></body></html>"""
    return _base_message(recipient, "Consensus Watch e-mail test", plain, html_body)

"""Small async SMTP service for Consensus Watch notifications."""

from __future__ import annotations

import asyncio
import contextvars
import functools
import html
import logging
import os
import re
import smtplib
import ssl
from email.message import EmailMessage
from urllib.parse import quote, urlsplit
from datetime import datetime, timezone

from app.core import i18n
from app.core.observability import safe_exception
from app.services import notification_markdown
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


class _OneLineHeader(str):
    """A header the generator writes as it is, on one line.

    Past 78 characters the email package folds a value it cannot break at a
    space into RFC 2047 encoded-words (``=?utf-8?q?=3Chttps...``). That is
    fine for a subject, but a URL list (RFC 2369) is no text: mail clients
    no longer find the link in it. RFC 5322 allows 998 characters per line."""

    def __new__(cls, name: str, value: str):
        if len(name) + len(value) + 2 > 998 or "\r" in value or "\n" in value:
            raise ValueError(f"{name} does not fit on one header line")
        header = super().__new__(cls, value)
        header.name = name
        header.defects = []
        return header

    def __getnewargs__(self):
        # copy.deepcopy and pickle rebuild the header through __new__.
        return (self.name, str(self))

    def fold(self, *, policy) -> str:
        return f"{self.name}: {self}{policy.linesep}"


def _base_message(recipient: str, subject: str, plain: str, html_body: str,
                  *, unsubscribe_url: str = "") -> EmailMessage:
    message = EmailMessage()
    message["From"] = _smtp_config()["sender"] or "consens.io"
    message["To"] = recipient
    message["Subject"] = subject
    if unsubscribe_url:
        # One-click unsubscribe (RFC 2369 + RFC 8058): Gmail, Apple Mail and
        # Outlook show their own "Unsubscribe" next to the sender and POST
        # "List-Unsubscribe=One-Click" to this URL. Without it a reader who
        # wants out reports spam, which also hurts the sign-in mails sent
        # from the same address. The route acts on that POST, never on a GET.
        message["List-Unsubscribe"] = _OneLineHeader("List-Unsubscribe", f"<{unsubscribe_url}>")
        message["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"
    # Umlauts or a quoted question leave ASCII: quoted-printable keeps the
    # rest, links included, readable in the raw text, where base64 would not.
    message.set_content(plain, **({} if plain.isascii() else {"cte": "quoted-printable"}))
    message.add_alternative(html_body, subtype="html")
    return message


# ---------------------------------------------------------------------------
# The reader's language
#
# A mail speaks the language its reader reads the site in: the account's
# (account_language), a follower's from the confirming click, a sign-up's
# from its request. Every fixed word goes through _t and the dictionary
# (app/i18n/<lang>/mail.json, docs/i18n.md); questions, answers and change
# summaries stay in the language they were written in. _N marks a word that
# is translated later, where it is used.
# ---------------------------------------------------------------------------

_LANGUAGE = contextvars.ContextVar("mail_language", default=i18n.DEFAULT_LANGUAGE)


def _N(text: str) -> str:
    return text


def _t(text: str, *, context: str = "", **params) -> str:
    """``text`` in the reader's language, ``params`` filled in as given."""
    return i18n.t(text, _LANGUAGE.get(), params or None, context=context)


def _h(text: str, **markup) -> str:
    """``_t`` for a text node: the sentence escaped, ``markup`` inserted as given."""
    return i18n.fill(html.escape(i18n.t(text, _LANGUAGE.get()), quote=False), markup or None)


def _localized(build):
    """``build`` with a ``language`` keyword; English when missing or unknown."""
    @functools.wraps(build)
    def wrapper(*args, language: str = "", **kwargs):
        token = _LANGUAGE.set(language if language in i18n.LANGUAGES else i18n.DEFAULT_LANGUAGE)
        try:
            return build(*args, **kwargs)
        finally:
            _LANGUAGE.reset(token)
    return wrapper


# ---------------------------------------------------------------------------
# Shared building blocks
#
# Every notification answers the same questions in the same order: what
# changed, why, and what was asked. The helpers below keep that structure
# identical across all mails (and mirror what telegram_watch.py sends), so
# the first lines are enough to understand the message. Long questions are
# clipped like the pages clamp them -- the full text is one click away.
#
# A mail looks like the app: its tokens (static/css/public-tokens.css) as
# fixed colours, because mail clients know no CSS variables; one black
# button; no coloured rules; labels in sentence case. MAIL_DARK_CSS swaps
# the same roles in clients that honour prefers-color-scheme (Apple Mail,
# iOS Mail, Outlook.com); the cx-* class on an element names its role.
# ---------------------------------------------------------------------------

GROUND = "#ffffff"      # --ground
RAISE = "#f3f3f3"       # a filled object (goal, code, source chip) on --ground
INK = "#0a0a0a"         # --ink
INK_SOFT = "#5e5e5e"    # --ink-2 (the one grey)
MUTED = "#5e5e5e"       # --ink-3
BORDER = "#dfdfdf"      # --line over --ground
LINE_SOFT = "#eeeeee"   # --line-soft over --ground
BUTTON_TEXT = "#ffffff"
MAIL_PALETTE = {
    "ink": INK, "ink_2": INK_SOFT, "ink_3": MUTED,
    "line": BORDER, "line_soft": LINE_SOFT, "raise": RAISE,
}
# The dark tokens of the app, per role.
_DARK_ROLES = {
    ".cx-bg": "background:#050505",
    ".cx-ink": "color:#f5f5f5",
    ".cx-soft": "color:#a1a1a1",
    ".cx-muted": "color:#a1a1a1",
    ".cx-raise": "background:#161616",
    ".cx-line": "border-color:#282828",
    ".cx-line-soft": "border-color:#171717",
    ".cx-btn": "background:#f5f5f5",
    ".cx-btn-label": "color:#050505",
}
MAIL_DARK_CSS = (
    "@media (prefers-color-scheme: dark){"
    + "".join(f"{role}{{{rule}!important}}" for role, rule in _DARK_ROLES.items())
    + "}"
    # Outlook.com marks what it recolours in its own dark mode.
    + "".join(
        f"[data-ogsc] {role}{{{rule}!important}}" for role, rule in _DARK_ROLES.items()
        if rule.startswith(("color", "border"))
    )
    + "".join(
        f"[data-ogsb] {role}{{{rule}!important}}" for role, rule in _DARK_ROLES.items()
        if rule.startswith("background")
    )
)
QUESTION_PREVIEW_CHARS = 200

_FONT_STACK = "-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif"
_LABEL_STYLE = f"margin:0;font-size:13px;font-weight:600;line-height:1.4;color:{MUTED}"
# Invisible characters after the preheader: without them a client fills the
# preview with the mail's first lines, which repeat what the preheader said.
_PREHEADER_FILL = "&#847;&zwnj;&nbsp;" * 60


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
    """Collapse a long text to a readable opening at a word; True = cut."""
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


def _label_html(text: str) -> str:
    return f'<p class="cx-muted" style="{_LABEL_STYLE}">{html.escape(text)}</p>'


def _link_html(url: str, label: str, *, muted: bool = False) -> str:
    color, role = (MUTED, "cx-muted") if muted else (INK, "cx-ink")
    return (
        f'<a href="{html.escape(url)}" class="{role}" '
        f'style="color:{color};text-decoration:underline">{html.escape(label)}</a>'
    )


def _question_html(question, url: str, *, label: str = "") -> str:
    text, truncated = _question_view(question)
    more = (
        f'<p style="margin:6px 0 0;font-size:13px">'
        f'{_link_html(url, _t("Read the full question"), muted=True)}</p>'
        if truncated and url else ""
    )
    return (
        f'<div style="margin:28px 0 0">{_label_html(label or _t("Question"))}'
        f'<p class="cx-ink" style="margin:4px 0 0;font-size:16px;font-weight:600;'
        f'line-height:1.45;color:{INK}">{html.escape(text)}</p>{more}</div>'
    )


def _question_plain(question) -> str:
    text, _truncated = _question_view(question)
    return _ascii(f"{_t('Question').upper()}\n{text}")


def _change_block_html(label: str, summary, *, notable: bool = True) -> str:
    """The heart of the mail: what actually changed, not buried in prose."""
    lead, rest = _split_lead(summary)
    if not lead:
        return ""
    lead_style = (
        f"font-size:17px;font-weight:600;line-height:1.45;color:{INK}" if notable
        else f"font-size:16px;font-weight:500;line-height:1.5;color:{INK_SOFT}"
    )
    detail = (
        f'<p class="cx-soft" style="margin:6px 0 0;font-size:15px;line-height:1.6;'
        f'color:{INK_SOFT}">{html.escape(rest)}</p>'
        if rest else ""
    )
    return (
        f'<div style="margin:24px 0 0">{_label_html(label)}'
        f'<p class="{"cx-ink" if notable else "cx-soft"}" style="margin:4px 0 0;{lead_style}">'
        f"{html.escape(lead)}</p>{detail}</div>"
    )


def _change_block_plain(label: str, summary) -> str:
    lead, rest = _split_lead(summary)
    if not lead:
        return ""
    return _ascii(f"{label.upper()}\n{lead}" + (f"\n{rest}" if rest else ""))


def _button_html(url: str, label: str) -> str:
    """The one filled control: a bulletproof table button (Outlook ignores
    padding on links), black like the app's primary button."""
    return (
        '<table role="presentation" cellpadding="0" cellspacing="0" border="0" '
        'style="margin:28px 0 0;border-collapse:separate"><tr>'
        f'<td class="cx-btn" style="border-radius:999px;background:{INK}">'
        f'<a href="{html.escape(url)}" class="cx-btn-label" style="display:inline-block;'
        f"padding:12px 22px;font-family:{_FONT_STACK};font-size:15px;font-weight:600;"
        f'line-height:1.2;color:{BUTTON_TEXT};text-decoration:none;border-radius:999px">'
        f"{html.escape(label)}</a></td></tr></table>"
    )


def _secondary_link_html(url: str, label: str) -> str:
    return f'<p style="margin:16px 0 0;font-size:14px">{_link_html(url, label)}</p>'


def _shell_html(*, eyebrow: str, heading: str, preheader: str, body: str,
                footer: str, width: int = 600) -> str:
    return (
        f'<!doctype html><html lang="{_LANGUAGE.get()}"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<meta name="color-scheme" content="light dark">'
        '<meta name="supported-color-schemes" content="light dark">'
        '<meta name="x-apple-disable-message-reformatting">'
        f"<title>{html.escape(heading)}</title>"
        "<style>:root{color-scheme:light dark;supported-color-schemes:light dark}"
        "body{margin:0;padding:0;-webkit-text-size-adjust:100%}"
        "@media (max-width:520px){.cx-pad{padding:28px 20px 36px!important}"
        ".cx-h1{font-size:22px!important}}"
        f"{MAIL_DARK_CSS}</style></head>"
        f'<body class="cx-bg" style="margin:0;padding:0;background:{GROUND}">'
        '<div style="display:none;max-height:0;max-width:0;overflow:hidden;opacity:0;'
        'font-size:1px;line-height:1px;mso-hide:all">'
        f"{html.escape(preheader)}{_PREHEADER_FILL}</div>"
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" '
        f'class="cx-bg" style="background:{GROUND}"><tr><td align="center">'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" '
        f'style="max-width:{width}px"><tr>'
        f'<td class="cx-pad cx-ink" style="padding:36px 28px 44px;text-align:left;'
        f'font-family:{_FONT_STACK};font-size:15px;line-height:1.6;color:{INK}">'
        f'<p class="cx-ink" style="margin:0 0 28px;font-size:15px;font-weight:600;'
        f'letter-spacing:-0.01em;color:{INK}">consens.io</p>'
        f"{_label_html(eyebrow)}"
        f'<h1 class="cx-ink cx-h1" style="margin:4px 0 0;font-size:24px;line-height:1.25;'
        f'font-weight:600;letter-spacing:-0.01em;color:{INK}">{html.escape(heading)}</h1>'
        f"{body}"
        f'<p class="cx-muted cx-line" style="margin:36px 0 0;padding:16px 0 0;'
        f'border-top:1px solid {BORDER};font-size:12px;line-height:1.55;color:{MUTED}">'
        f"{footer}</p>"
        "</td></tr></table></td></tr></table></body></html>"
    )


def _subject_clip(text, limit: int = 72) -> str:
    """Subjects end at a word, never inside one."""
    return _question_view(text, limit=limit)[0]


# Why a check moved, in the words of the evidence model
# (docs/watch-evidence-model.md). A cause without a sentence is not shown.
_CAUSE_SENTENCES = {
    "new_evidence": _N("New evidence: a source the earlier answer did not have."),
    "reassessment": _N(
        "Same evidence, read differently by the models, and a second check "
        "confirmed that reading before this message was sent."
    ),
    "model_change": _N(
        "The answering models changed, and a second check confirmed the new "
        "reading before this message was sent."
    ),
}


def owner_page_path(path: str, *, private: bool) -> str:
    """The link a page's owner gets by mail. A private page opens only with
    the owner's session cookie, which a mail app or another browser lacks
    (the link ended on "This page is private"). Private links therefore go
    through the app's sign-in, which returns to the page once the cookie is
    set (static/firebase.js, ?next=); a browser that is signed in already
    passes straight through."""
    path = str(path or "")
    if not private or not path.startswith("/s/"):
        return path
    return "/app?next=" + quote(path, safe="/")


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


def _why_html(sentence, sources) -> str:
    """One "Why": the reason in a sentence, then the sources that carry it."""
    sentence = _normalized(sentence)
    items = _clean_sources(sources)
    if not sentence and not items:
        return ""
    links = "".join(
        f'<li class="cx-soft" style="margin:0 0 4px;color:{INK_SOFT}">'
        f'{_link_html(item["url"], item["title"])} '
        f'<span class="cx-muted" style="color:{MUTED}">· {html.escape(_host(item["url"]))}</span></li>'
        for item in items
    )
    return (
        f'<div style="margin:24px 0 0">{_label_html(_t("Why"))}'
        + (
            f'<p class="cx-soft" style="margin:4px 0 0;color:{INK_SOFT}">{html.escape(sentence)}</p>'
            if sentence else ""
        )
        + (f'<ul style="margin:8px 0 0;padding:0 0 0 18px">{links}</ul>' if links else "")
        + "</div>"
    )


def _why_plain(sentence, sources) -> str:
    sentence = _normalized(sentence)
    items = _clean_sources(sources)
    if not sentence and not items:
        return ""
    lines = [_t("Why").upper()] + ([sentence] if sentence else [])
    lines += [f"- {item['title']} ({item['url']})" for item in items]
    return _ascii("\n".join(lines))


def _held_html(held) -> str:
    text = _normalized(held)
    if not text:
        return ""
    return (
        f'<div style="margin:24px 0 0">{_label_html(_t("What held"))}'
        f'<p class="cx-soft" style="margin:4px 0 0;color:{INK_SOFT}">{html.escape(text)}</p></div>'
    )


def _held_plain(held) -> str:
    text = _normalized(held)
    return _ascii(f"{_t('What held').upper()}\n{text}") if text else ""


def _goal_html(goal, status_line, *, label: str = "") -> str:
    goal = _normalized(goal)
    if not goal:
        return ""
    return (
        f'<div class="cx-raise" style="margin:24px 0 0;padding:14px 16px;background:{RAISE};'
        f'border-radius:12px">{_label_html(label or _t("Waiting for"))}'
        f'<p class="cx-ink" style="margin:4px 0 0;font-weight:600;color:{INK}">{html.escape(goal)}</p>'
        + (
            f'<p class="cx-muted" style="margin:4px 0 0;font-size:14px;color:{MUTED}">'
            f"{html.escape(status_line)}</p>"
            if status_line else ""
        )
        + "</div>"
    )


def _goal_plain(goal, status_line, *, label: str = "") -> str:
    goal = _normalized(goal)
    if not goal:
        return ""
    label = (label or _t("Waiting for")).upper()
    return _ascii(f"{label}\n{goal}" + (f"\n{status_line}" if status_line else ""))


def _goal_status_line(delta: dict) -> str:
    reason = _normalized(delta.get("goal_reason"))
    if delta.get("goal_status") == "not_met":
        return _t("Not yet. {reason}", reason=reason) if reason else _t("Not yet.")
    if delta.get("goal_status") == "met":
        return _t("Reported met, re-checking before the watch closes.")
    return reason


def _answer_html(consensus: str, sources) -> str:
    """The answer as the page shows it: rendered, never escaped Markdown."""
    if not consensus:
        return ""
    rendered = notification_markdown.answer_mail_html(
        consensus, palette=MAIL_PALETTE, sources=sources,
    )
    return (
        f'<div class="cx-line" style="margin:32px 0 0;padding:24px 0 0;'
        f'border-top:1px solid {BORDER}">{_label_html(_t("The answer"))}'
        f'<div class="cx-ink" style="margin:10px 0 0;font-size:15px;line-height:1.6;'
        f'color:{INK}">{rendered}</div></div>'
    )


def _answer_plain(consensus: str, sources) -> str:
    if not consensus:
        return ""
    return _t("The answer").upper() + "\n\n" + notification_markdown.answer_plain(consensus, sources=sources)


def _delta_parts(delta: dict, *, notable: bool = True) -> tuple[str, str]:
    """The change log every Watch and follower mail is built from.

    What changed, why (with the sources that carry it), what held, and where
    the goal stands. No agreement score: it steps between fixed grades and
    is not a reason to write to anyone.
    """
    summary = delta.get("summary") or ""
    goal_line = _goal_status_line(delta)
    cause = _CAUSE_SENTENCES.get(str(delta.get("cause") or ""), "")
    cause = _t(cause) if cause else ""
    html_part = (
        _change_block_html(_t("What changed"), summary, notable=notable)
        + _why_html(cause, delta.get("sources"))
        + _held_html(delta.get("held"))
        + _goal_html(delta.get("goal"), goal_line)
    )
    plain_part = "\n\n".join(part for part in (
        _change_block_plain(_t("What changed"), summary),
        _why_plain(cause, delta.get("sources")),
        _held_plain(delta.get("held")),
        _goal_plain(delta.get("goal"), goal_line),
    ) if part)
    return html_part, plain_part


@_localized
def build_change_message(*, recipient: str, question: str, delta: dict,
                         share_url: str, unsubscribe_url: str) -> EmailMessage:
    subject = _t("Moved: {question}", question=_subject_clip(question))
    lead, _rest = _split_lead(delta.get("summary"))
    delta_html, delta_plain = _delta_parts(delta)
    plain = (
        _t("Your Watch found a change backed by evidence.") + "\n\n"
        + delta_plain + "\n\n"
        + _question_plain(question) + "\n\n"
        + _t("See what changed: {url}", url=share_url) + "\n"
        + _t("Pause this watch: {url}", url=unsubscribe_url) + "\n"
    )
    body = (
        delta_html
        + _question_html(question, share_url)
        + _button_html(share_url, _t("See what changed"))
    )
    html_body = _shell_html(
        eyebrow=_t("Watch · Moved"),
        heading=_t("The answer moved"),
        preheader=lead or _t("A watched question moved on new evidence."),
        body=body,
        footer=_h(
            "A Watch only writes when a change is backed by a source or "
            "confirmed by a second check. {link}.",
            link=_link_html(unsubscribe_url, _t("Pause this watch"), muted=True),
        ),
    )
    return _base_message(recipient, subject, plain, html_body, unsubscribe_url=unsubscribe_url)


@_localized
def build_run_message(*, recipient: str, question: str, delta: dict, moved: bool,
                      consensus: str, share_url: str, unsubscribe_url: str,
                      answer_sources=None) -> EmailMessage:
    """Full-content notification for users who opted into every successful run.

    ``answer_sources`` are the sources of the answer's version: its [S1]
    citations link to them."""
    subject = _t("New check: {question}", question=_subject_clip(question))
    consensus_text = str(consensus or "").strip()
    if not moved:
        delta = {**delta, "summary": _t("Nothing moved on evidence in this check."), "cause": "", "sources": []}
    delta_html, delta_plain = _delta_parts(delta, notable=moved)
    plain = "\n\n".join(part for part in (
        _t("Your Watch completed a new check."),
        delta_plain,
        _question_plain(question),
        _answer_plain(consensus_text, answer_sources),
        _t("Open the watch: {url}", url=share_url) + "\n" + _t("Pause this watch: {url}", url=unsubscribe_url),
    ) if part) + "\n"
    body = (
        delta_html
        + _question_html(question, share_url)
        + _answer_html(consensus_text, answer_sources)
        + _button_html(share_url, _t("Open the watch"))
    )
    html_body = _shell_html(
        eyebrow=_t("Watch · Moved") if moved else _t("Watch · Checked again"),
        heading=_t("The answer moved") if moved else _t("Checked again"),
        preheader=_split_lead(delta.get("summary"))[0],
        body=body,
        footer=_h(
            "You chose to receive every check. {link}.",
            link=_link_html(unsubscribe_url, _t("Pause this watch"), muted=True),
        ),
        width=640,
    )
    return _base_message(recipient, subject, plain, html_body, unsubscribe_url=unsubscribe_url)


@_localized
def build_condition_message(*, recipient: str, question: str, goal: str, reason: str,
                            sources, consensus: str, share_url: str,
                            unsubscribe_url: str, answer_sources=None) -> EmailMessage:
    """Sent once, when the goal a watch was waiting for is met on evidence.

    The subject names the goal and the question, so the one message the
    reader waited for is clear in the inbox list alone. Without a ``reason``
    of its own, the goal is met by the new answer."""
    clipped_goal = _normalized(goal)[:500]
    clipped_reason = _normalized(reason)[:400] or _t("The goal is met by the new answer.")
    goal_part = _subject_clip(clipped_goal, limit=48)
    question_part = _subject_clip(question, limit=max(32, 100 - len(goal_part)))
    subject = (
        _t("Reached: {goal} · {question}", goal=goal_part, question=question_part)
        if question_part else _t("Reached: {goal}", goal=goal_part)
    )
    consensus_text = str(consensus or "").strip()
    items = _clean_sources(sources)
    plain = "\n\n".join(part for part in (
        _t("The goal your Watch was waiting for is met. The watch is complete."),
        _goal_plain(clipped_goal, "", label=_t("You were waiting for")),
        _why_plain(clipped_reason, items),
        _question_plain(question),
        _answer_plain(consensus_text, answer_sources),
        _t("Open the watch: {url}", url=share_url),
    ) if part) + "\n"
    body = (
        _goal_html(clipped_goal, "", label=_t("You were waiting for"))
        + _why_html(clipped_reason, items)
        + _question_html(question, share_url)
        + _answer_html(consensus_text, answer_sources)
        + _button_html(share_url, _t("Open the watch"))
    )
    html_body = _shell_html(
        eyebrow=_t("Watch · Goal reached"),
        heading=_t("What you were waiting for happened"),
        preheader=_split_lead(clipped_reason)[0] or clipped_goal,
        body=body,
        footer=_h(
            "The watch stopped checking and freed its slot. Open it to watch for "
            "something new."
        ),
        width=640,
    )
    return _base_message(recipient, subject, plain, html_body)


@_localized
def build_follow_confirm_message(*, recipient: str, question: str,
                                 confirm_url: str, share_url: str) -> EmailMessage:
    """Double-Opt-in: einmalige Bestätigungs-Mail für Seiten-Follower."""
    subject = _t('Confirm: follow "{question}"', question=_subject_clip(question))
    plain = (
        _t("Confirm that you want to follow this question on consens.io.") + "\n\n"
        + _question_plain(question) + "\n\n"
        + _t("You will get one email whenever this answer changes materially.") + "\n"
        + _t("Confirm: {url}", url=confirm_url) + "\n\n"
        + _t("Page: {url}", url=share_url) + "\n"
        + _t("If you did not request this, simply ignore this email - nothing is stored.") + "\n"
    )
    body = (
        _question_html(question, share_url)
        + f'<p class="cx-soft" style="margin:16px 0 0;color:{INK_SOFT}">'
        + _h("You will get one email whenever this answer changes materially – no account needed.")
        + "</p>"
        + _button_html(confirm_url, _t("Confirm and follow"))
    )
    html_body = _shell_html(
        eyebrow=_t("Confirm follow"),
        heading=_t("Follow this question?"),
        preheader=_t("One click confirms; we only write when the consensus moves."),
        body=body,
        footer=_h(
            "If you did not request this, simply ignore this email – nothing is stored. {link}.",
            link=_link_html(share_url, _t("Open the page"), muted=True),
        ),
    )
    return _base_message(recipient, subject, plain, html_body)


@_localized
def build_topic_follow_confirm_message(*, recipient: str, title: str,
                                       confirm_url: str, topic_url: str) -> EmailMessage:
    """Double opt-in confirmation for the independent curated Topics area."""
    clipped_title = _normalized(title)
    subject = _t('Confirm: follow "{question}"', question=_subject_clip(clipped_title))
    plain = (
        _t("Confirm that you want to follow this topic on consens.io.") + "\n\n"
        f"{clipped_title}\n\n"
        + _t("You will receive an email when the curated consensus changes materially.") + "\n"
        + _t("Confirm: {url}", url=confirm_url) + "\n\n"
        + _t("Topic: {url}", url=topic_url) + "\n"
        + _t("If you did not request this, ignore this email; nothing is stored.") + "\n"
    )
    body = (
        _question_html(clipped_title, topic_url, label=_t("Topic"))
        + f'<p class="cx-soft" style="margin:16px 0 0;color:{INK_SOFT}">'
        + _h("You will receive an email when the curated AI consensus changes materially.")
        + "</p>"
        + _button_html(confirm_url, _t("Confirm and follow"))
    )
    html_body = _shell_html(
        eyebrow=_t("Confirm follow"),
        heading=_t("Follow this topic?"),
        preheader=_t("One click confirms; we only write when the curated consensus moves."),
        body=body,
        footer=_h(
            "If you did not request this, ignore this email; nothing is stored. {link}.",
            link=_link_html(topic_url, _t("Open the topic"), muted=True),
        ),
    )
    return _base_message(recipient, subject, plain, html_body)


@_localized
def build_topic_change_message(*, recipient: str, title: str, question: str,
                               delta: dict, topic_url: str,
                               unsubscribe_url: str) -> EmailMessage:
    """Material-change notification for a confirmed Topic follower."""
    clipped_title = _normalized(title)
    subject = _t("Topic update: {title}", title=_subject_clip(clipped_title))
    lead, _rest = _split_lead(delta.get("summary"))
    delta_html, delta_plain = _delta_parts(delta)
    plain = (
        _t("The curated consensus moved.") + f"\n\n{clipped_title}\n\n"
        + delta_plain + "\n\n"
        + _question_plain(question) + "\n\n"
        + _t("Open the timeline: {url}", url=topic_url) + "\n"
        + _t("Unfollow: {url}", url=unsubscribe_url) + "\n"
    )
    body = (
        delta_html
        + _question_html(question, topic_url, label=_t("Tracked question"))
        + _button_html(topic_url, _t("Open the timeline"))
    )
    html_body = _shell_html(
        eyebrow=_t("Topic you follow"),
        heading=clipped_title,
        preheader=lead or _t("The curated consensus moved."),
        body=body,
        footer=_h(
            "You follow this curated topic on consens.io. {link}.",
            link=_link_html(unsubscribe_url, _t("Unfollow"), muted=True),
        ),
    )
    return _base_message(recipient, subject, plain, html_body, unsubscribe_url=unsubscribe_url)


@_localized
def build_follower_change_message(*, recipient: str, question: str, delta: dict,
                                  share_url: str, unsubscribe_url: str) -> EmailMessage:
    """Änderungs-Mail an bestätigte Seiten-Follower (nicht den Watch-Owner)."""
    subject = _t("The AI consensus moved: {question}", question=_subject_clip(question))
    lead, _rest = _split_lead(delta.get("summary"))
    # The goal belongs to the owner; followers subscribed to the question.
    delta_html, delta_plain = _delta_parts({**delta, "goal": ""})
    plain = (
        _t("A question you follow on consens.io moved.") + "\n\n"
        + delta_plain + "\n\n"
        + _question_plain(question) + "\n\n"
        + _t("See what changed: {url}", url=share_url) + "\n"
        + _t("Unfollow: {url}", url=unsubscribe_url) + "\n"
    )
    body = (
        delta_html
        + _question_html(question, share_url)
        + _button_html(share_url, _t("See what changed"))
    )
    html_body = _shell_html(
        eyebrow=_t("Question you follow"),
        heading=_t("The AI consensus moved"),
        preheader=lead or _t("A question you follow moved."),
        body=body,
        footer=_h(
            "You follow this question on consens.io. {link}.",
            link=_link_html(unsubscribe_url, _t("Unfollow"), muted=True),
        ),
    )
    return _base_message(recipient, subject, plain, html_body, unsubscribe_url=unsubscribe_url)


@_localized
def build_paused_message(*, recipient: str, question: str, share_url: str,
                         unsubscribe_url: str, resume_url: str = "") -> EmailMessage:
    """Three failed checks paused the watch. The way out is resuming it, so
    that is the button; a link to pause it again would be no help. The
    List-Unsubscribe header still lets a mail client stop these mails."""
    subject = _t("Watch paused: {question}", question=_subject_clip(question))
    action_url, action_label = (resume_url, _t("Resume watch")) if resume_url else (share_url, _t("Open the watch"))
    plain = "\n\n".join(part for part in (
        _t("Your watch was paused after three failed checks in a row. Nothing was "
           "lost: resuming it continues the same history."),
        _question_plain(question),
        _t("Resume this watch: {url}", url=resume_url) if resume_url else "",
        _t("Open the watch: {url}", url=share_url),
    ) if part) + "\n"
    body = (
        f'<p class="cx-soft" style="margin:16px 0 0;color:{INK_SOFT}">'
        + _h("Three checks in a row could not be completed, so this watch was paused. "
             "Nothing was lost – resuming it continues the same history.")
        + "</p>"
        + _question_html(question, share_url)
        + _button_html(action_url, action_label)
        + (_secondary_link_html(share_url, _t("Open the watch")) if resume_url else "")
    )
    html_body = _shell_html(
        eyebrow=_t("Watch · Paused"),
        heading=_t("This watch was paused"),
        preheader=_t("Three checks in a row failed. Resume it with one click."),
        body=body,
        footer=_h("A resumed watch checks again on its usual schedule."),
    )
    return _base_message(recipient, subject, plain, html_body, unsubscribe_url=unsubscribe_url)


_BRIEF_STATUS = {
    "active": _N("Active"),
    "paused": _N("Paused"),
    "paused_error": _N("Paused after errors"),
    "resolved": _N("Resolved"),
}


def _brief_status_label(status: str) -> str:
    # A resolved watch reached its goal; plain "Resolved" is a settled disagreement.
    return _t(_BRIEF_STATUS.get(status, _BRIEF_STATUS["paused"]), context="watch status")


def _brief_reached(item: dict) -> str:
    """The "Reached" line of a watch whose goal was met, else ""."""
    resolution = item.get("resolution") or {}
    if resolution:
        return _normalized(resolution.get("reason")) or _normalized(item.get("goal"))
    if str(item.get("status") or "") == "resolved":
        return _normalized(item.get("goal"))
    return ""


def _brief_changes(item: dict) -> list:
    return [
        _normalized(point.get("change_summary"))
        for point in (item.get("new_points") or [])
        if point.get("notable") and point.get("change_summary")
    ]


def _brief_goal_line(item: dict) -> str:
    if str(item.get("status") or "") == "resolved":
        return ""  # the Reached line says it
    goal = _normalized(item.get("goal"))
    if not goal:
        return _t("Watching for any change on evidence")
    return _t("Waiting for: {goal}", goal=_question_view(goal, limit=90)[0])


def _city(timezone_name: str) -> str:
    """"America/Los_Angeles" -> "Los Angeles": how people name a time zone."""
    return str(timezone_name or "").rsplit("/", 1)[-1].replace("_", " ")


# Indexed by date.weekday() and date.month - 1; the watch's run_weekday by name.
_WEEKDAYS = (_N("Monday"), _N("Tuesday"), _N("Wednesday"), _N("Thursday"),
             _N("Friday"), _N("Saturday"), _N("Sunday"))
_WEEKDAY_NAMES = dict(zip(("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"),
                          _WEEKDAYS))
_MONTHS = (_N("January"), _N("February"), _N("March"), _N("April"), _N("May"), _N("June"),
           _N("July"), _N("August"), _N("September"), _N("October"), _N("November"),
           _N("December"))
# Interval alone and with its time, one sentence each. "Daily" alone is the
# preset (Alltag); as a schedule it is said in its own context.
_INTERVALS = {
    "daily": (_N("Daily"), _N("Daily at {time}")),
    "weekly": (_N("Weekly"), _N("Weekly at {time}")),
    "monthly": (_N("Monthly"), _N("Monthly at {time}")),
}


def _brief_schedule(item: dict, brief_timezone: str) -> str:
    if str(item.get("status") or "") == "resolved":
        return ""  # a reached watch no longer checks
    interval = str(item.get("interval") or "")
    run_time = str(item.get("run_time") or "")
    weekday = str(item.get("run_weekday") or "").lower()
    if interval == "weekly" and weekday:
        weekday = _t(_WEEKDAY_NAMES.get(weekday, weekday.capitalize()))
        schedule = (_t("Weekly on {weekday} at {time}", weekday=weekday, time=run_time) if run_time
                    else _t("Weekly on {weekday}", weekday=weekday))
    elif interval in _INTERVALS:
        alone, timed = _INTERVALS[interval]
        schedule = _t(timed, time=run_time) if run_time else _t(alone, context="watch schedule")
    else:
        schedule = " at ".join(part for part in (interval.capitalize(), run_time) if part)
    zone = str(item.get("timezone") or "")
    # The brief's own zone needs no name; another one is said as a city.
    # Patterns this open live under "mail|" only (i18n.t): on a page they
    # would catch any "... time".
    if run_time and schedule and zone and zone != brief_timezone:
        schedule = _t("{schedule} {city} time", context="mail", schedule=schedule, city=_city(zone))
    return schedule


@_localized
def brief_date_label(moment: datetime) -> str:
    """The brief's day as its reader writes it: "Friday, 23 October 2026"."""
    return _t("{weekday}, {day} {month} {year}", context="mail", weekday=_t(_WEEKDAYS[moment.weekday()]),
              day=moment.day, month=_t(_MONTHS[moment.month - 1]), year=moment.year)


def _brief_subject(changes_count: int, watch_count: int) -> str:
    # Whole sentences per number (docs/i18n.md): German counts differently.
    if not changes_count:
        return (_t("Morning brief: your {watches} watch, no material changes", watches=watch_count)
                if watch_count == 1 else
                _t("Morning brief: your {watches} watches, no material changes", watches=watch_count))
    if changes_count == 1:
        return (_t("Morning brief: {changes} change across {watches} watch", changes=1, watches=watch_count)
                if watch_count == 1 else
                _t("Morning brief: {changes} change across {watches} watches", changes=1, watches=watch_count))
    return (_t("Morning brief: {changes} changes across {watches} watch", changes=changes_count, watches=watch_count)
            if watch_count == 1 else
            _t("Morning brief: {changes} changes across {watches} watches", changes=changes_count,
               watches=watch_count))


@_localized
def build_brief_message(*, recipient: str, date_label: str, items: list,
                        changes_count: int, site_url: str,
                        unsubscribe_url: str, brief_timezone: str = "") -> EmailMessage:
    """Daily digest over all watches of one user (no per-watch mail replaced).

    ``brief_timezone`` is the brief's own: watch times in it are written without a
    zone name, times in another zone name its city. ``date_label`` comes from
    brief_date_label in the same language."""
    watch_count = len(items)
    subject = _brief_subject(changes_count, watch_count)
    watches_url = f"{site_url}/app/watches"
    plain_rows, html_rows = [], []
    reached_label, changed_label = _t("Reached."), _t("Changed.")
    # Watches with news come first: the digest is scanned top-down and a
    # quiet week should never bury the one line that matters.
    def has_news(entry):
        return bool(_brief_changes(entry) or (entry.get("resolution") or {}))

    for item in sorted(items, key=lambda entry: not has_news(entry)):
        question, _truncated = _question_view(item.get("question"), limit=150)
        url = site_url + owner_page_path(item.get("share_path"), private=item.get("visibility") == "private")
        meta = " · ".join(part for part in (
            _brief_status_label(str(item.get("status") or "")),
            _brief_goal_line(item),
            _brief_schedule(item, brief_timezone),
        ) if part)
        reached = _brief_reached(item)
        changes = _brief_changes(item)[:3]
        plain = _ascii(f"- {question}\n  {meta}\n")
        if reached:
            plain += _ascii(f"  {reached_label.rstrip('.').upper()}: {reached}\n")
        for summary in changes:
            plain += _ascii(f"  {changed_label.rstrip('.').upper()}: {summary}\n")
        if not changes and not reached:
            plain += "  " + _t("No material change.") + "\n"
        plain += f"  {url}\n"
        plain_rows.append(plain)

        news_html = "".join(
            f'<p class="cx-ink" style="margin:8px 0 0;font-size:14px;line-height:1.5;color:{INK}">'
            f'<strong style="font-weight:600">{html.escape(label)}</strong> {html.escape(text)}</p>'
            for label, text in ([(reached_label, reached)] if reached else [])
            + [(changed_label, summary) for summary in changes]
        )
        html_rows.append(
            f'<div class="cx-line" style="padding:16px 0;border-top:1px solid {BORDER}">'
            f'<p style="margin:0;font-size:16px;font-weight:600;line-height:1.4">'
            f'<a href="{html.escape(url)}" class="cx-ink" style="color:{INK};text-decoration:none">'
            f"{html.escape(question)}</a></p>"
            f'<p class="cx-muted" style="margin:4px 0 0;font-size:13px;line-height:1.5;color:{MUTED}">'
            f"{html.escape(meta)}</p>{news_html}</div>"
        )
    plain = (
        _t("Your morning brief – {date}", date=date_label) + "\n\n"
        + ("\n".join(plain_rows) if plain_rows else _t("You have no watches yet.") + "\n")
        + "\n" + _t("Open your watches: {url}", url=watches_url) + "\n"
        + _t("Unsubscribe from this brief: {url}", url=unsubscribe_url) + "\n"
    )
    if changes_count == 1:
        intro = _t("{changes} notable change since your last brief.", changes=1)
    elif changes_count:
        intro = _t("{changes} notable changes since your last brief.", changes=changes_count)
    else:
        intro = _t("No material changes since your last brief.")
    body = (
        f'<p class="cx-soft" style="margin:8px 0 24px;color:{INK_SOFT}">{html.escape(date_label)} · '
        f"{html.escape(intro)}</p>"
        + "".join(html_rows)
        + _button_html(watches_url, _t("Open your watches"))
    )
    html_body = _shell_html(
        eyebrow=_t("Morning brief"),
        heading=_t("Your watches this morning"),
        preheader=intro,
        body=body,
        footer=_h(
            "You receive this daily digest because you turned on the morning brief. "
            "{link} – individual watch alerts are unaffected.",
            link=_link_html(unsubscribe_url, _t("Turn off the brief"), muted=True),
        ),
        width=640,
    )
    return _base_message(recipient, subject, plain, html_body, unsubscribe_url=unsubscribe_url)


@_localized
def build_account_setup_message(*, recipient: str, setup_url: str) -> EmailMessage:
    """Sign-up mail: choose a password. Replaces Firebase's "Reset your
    password" template, which this project cannot edit."""
    plain = (
        _t("Welcome to consens.io!") + "\n\n"
        + _t("One step left: choose a password for your account.") + "\n"
        f"{setup_url}\n\n"
        + _t("The next page is our login provider's standard page and is titled\n"
             "\"Reset your password\" - that's the right place. Afterwards you are\n"
             "taken straight back to consens.io.") + "\n\n"
        + _t("The link works for one hour. Didn't sign up? Just ignore this email.") + "\n"
    )
    body = (
        f'<p class="cx-soft" style="margin:16px 0 0;color:{INK_SOFT}">'
        + _h("Thanks for signing up. Choose a password and you're in.")
        + "</p>"
        + _button_html(setup_url, _t("Choose my password"))
        + f'<p class="cx-muted" style="margin:20px 0 0;font-size:14px;color:{MUTED}">'
        + _h("The next page is our login provider's standard page and is titled “Reset your password” – "
             "that's the right place. Afterwards you are taken straight back to consens.io.")
        + "</p>"
    )
    html_body = _shell_html(
        eyebrow=_t("Account"),
        heading=_t("One step left: choose your password"),
        preheader=_t("Choose a password and you're in."),
        body=body,
        footer=_h("The link works for one hour. Didn't sign up? Just ignore this email."),
    )
    return _base_message(recipient, _t("Finish setting up your consens.io account"), plain, html_body)


@_localized
def build_existing_account_message(*, recipient: str, login_url: str,
                                   reset_url: str) -> EmailMessage:
    """Sign-up with an address that already has an account. The sign-up form
    answers identically either way; only the mailbox owner learns this."""
    plain = (
        _t("Someone - probably you - just signed up on consens.io with this address,\n"
           "but it already has an account.") + "\n\n"
        + _t("Log in as usual (with Google or your password): {url}", url=login_url) + "\n\n"
        + _t("Forgot your password? Set a new one (link works for one hour):") + f"\n{reset_url}\n\n"
        + _t("Didn't do this? Just ignore this email - nothing has changed.") + "\n"
    )
    body = (
        f'<p class="cx-soft" style="margin:16px 0 0;color:{INK_SOFT}">'
        + _h("Someone – probably you – just signed up with this address, but it already has an account. "
             "Log in as usual, with Google or your password.")
        + "</p>"
        + _button_html(login_url, _t("Log in"))
        + f'<p class="cx-muted" style="margin:20px 0 0;font-size:14px;color:{MUTED}">'
        + _h("Forgot your password? {link} (link works for one hour).",
             link=_link_html(reset_url, _t("Set a new one")))
        + "</p>"
    )
    html_body = _shell_html(
        eyebrow=_t("Account"),
        heading=_t("You already have an account"),
        preheader=_t("Log in as usual – or set a new password."),
        body=body,
        footer=_h("Didn't do this? Just ignore this email – nothing has changed."),
    )
    return _base_message(recipient, _t("You already have a consens.io account"), plain, html_body)


def deliver_now(message: EmailMessage) -> bool:
    """Synchronous delivery for callers already off the event loop."""
    return _deliver(message)


def build_test_message(*, recipient: str) -> EmailMessage:
    """Small delivery probe used only by the authenticated admin endpoint."""
    sent_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    plain = (
        "Watch email delivery is configured correctly.\n\n"
        f"This test was requested from the admin dashboard at {sent_at}.\n"
        "No watch was executed and no schedule was changed.\n"
    )
    body = (
        f'<p class="cx-soft" style="margin:16px 0 0;color:{INK_SOFT}">The application connected '
        "to SMTP and submitted this message successfully.</p>"
        f'<p class="cx-muted" style="margin:12px 0 0;font-size:14px;color:{MUTED}">Requested from '
        f"the admin dashboard at {html.escape(sent_at)}. No watch was executed and no schedule "
        "was changed.</p>"
    )
    html_body = _shell_html(
        eyebrow="Mail test",
        heading="Watch email test successful",
        preheader="SMTP delivery works.",
        body=body,
        footer="Sent from the admin dashboard.",
    )
    return _base_message(recipient, "consens.io email test", plain, html_body)

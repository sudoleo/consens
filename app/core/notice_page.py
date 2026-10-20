"""One public page for a short notice: what a mail link asks or did, a limit.

The pages behind the links of Watch, follow and brief mails (pause, resume,
confirm, unfollow, turn off) and the HTML answer to a rate limit share this
template (templates/notice.html): the public nav and footer, the page
tokens, the thing the link is about by name, and the next step as buttons.
A form button is the only thing that changes anything -- a GET only asks
(mail scanners open every link in a message).
"""

from __future__ import annotations

from typing import Iterable

from fastapi import Request
from fastapi.templating import Jinja2Templates

from app.core.assets import register_asset_globals

templates = Jinja2Templates(directory="templates")
register_asset_globals(templates)

WATCHES_LINK = {"href": "/app/watches", "label": "Open Watches"}


def notice_page(
    request: Request,
    *,
    heading: str,
    message: str,
    status_code: int = 200,
    eyebrow: str = "consens.io",
    subject_label: str = "",
    subject: str = "",
    action: str = "",
    button: str = "",
    links: Iterable[dict] = (),
):
    """``action``/``button``: the one form that acts (POST). ``links``: the
    ways on, ``{"href", "label"}``; the first is the primary button when the
    page has no form."""
    response = templates.TemplateResponse(
        request=request,
        name="notice.html",
        context={
            "eyebrow": eyebrow,
            "heading": heading,
            "message": message,
            "subject_label": subject_label,
            "subject": " ".join(str(subject or "").split()),
            "action": action,
            "button": button,
            "links": [dict(link) for link in links],
        },
        status_code=status_code,
    )
    response.headers["X-Robots-Tag"] = "noindex, noarchive"
    # The URL carries a personal token; no cache keeps the page.
    response.headers["Cache-Control"] = "no-store"
    return response

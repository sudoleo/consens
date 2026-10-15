"""The public HTML 404 for page navigations.

Unknown paths used to answer browsers and crawlers with FastAPI's raw
``{"detail": "Not Found"}``. A navigation now gets templates/not_found.html;
scripts calling the API keep their JSON errors.
"""

from fastapi import Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.core.assets import register_asset_globals

templates = Jinja2Templates(directory="templates")
register_asset_globals(templates)


def wants_html_page(request: Request) -> bool:
    """A browser or crawler navigating to a page, not a script calling the API.

    fetch() sends ``Accept: */*`` unless told otherwise; navigations and
    crawlers ask for text/html. Only GET/HEAD navigations get the HTML 404.
    """
    if request.method not in {"GET", "HEAD"}:
        return False
    return "text/html" in request.headers.get("accept", "").lower()


def not_found_page(request: Request) -> HTMLResponse:
    """The public HTML 404 (templates/not_found.html), never indexed."""
    response = templates.TemplateResponse(
        request=request, name="not_found.html", status_code=404
    )
    response.headers["X-Robots-Tag"] = "noindex, noarchive"
    return response

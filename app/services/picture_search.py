"""Brave's image search for the agent (search_pictures in agent_web_images.py,
since 2026-10-31).

Max, 2026-10-31: ChatGPT answers a question about something to see with a
collage of pictures to click through, and its model rarely has to look at
them first, its image search is that good. find_pictures could only take the
preview picture a page names for itself, often a logo or a banner, so the
agent guessed one page after the other and looked at each. An image search
answers with pictures, each with its page, the page's title and its size;
the agent chooses by those and shows its pick.

Brave over the other image searches (Claude, 2026-10-31, docs/agent-mode.md
"Bildersuche"): an index of its own, a copy of each picture on its own server
(500 px wide), safe search strict unless asked otherwise. Parallel's terms
license every query for training, Linkup and Tavily only give the pictures of
pages their web search found, You.com's is an unmaintained beta, Google's API
takes no new customers and the services that scrape Google break its terms.

What leaves: the words the agent searches for, from the server, with
consens.io's key; nothing of the user's account or browser (privacy.html).
Never in chats with Google data, like read_source and find_pictures
(agent_delegation.py).
"""
from __future__ import annotations

import os
from urllib.parse import urlsplit

import httpx

KEY_ENV = "BRAVE_SEARCH_API_KEY"
# Off with AGENT_PICTURE_SEARCH=0 although a key is set.
ENABLED_ENV = "AGENT_PICTURE_SEARCH"
ENDPOINT = "https://api.search.brave.com/res/v1/images/search"
SECONDS = 10.0
# Asked for a few more than are returned: some come without an address.
ASK = 12
TITLE_CHARS = 200


def enabled():
    """On with a key, unless AGENT_PICTURE_SEARCH=0."""
    return bool(os.environ.get(KEY_ENV, "").strip()) and os.environ.get(ENABLED_ENV, "1").strip() != "0"


def _web(value):
    """``value`` when it is an http(s) address without credentials, else ""."""
    if not isinstance(value, str) or len(value) > 2048:
        return ""
    try:
        parts = urlsplit(value.strip())
    except ValueError:
        return ""
    if parts.scheme not in ("http", "https") or not parts.hostname or parts.username or parts.password:
        return ""
    return value.strip()


def _size(value):
    return value if type(value) is int and 0 < value < 100_000 else None


def pictures(data, count):
    """Up to ``count`` pictures of a Brave image search answer, each
    {picture, thumbnail, page, title, width, height}; one without a page or
    without any picture address is left out, a picture found twice once."""
    found, seen = [], set()
    for item in (data.get("results") if isinstance(data, dict) else None) or []:
        if not isinstance(item, dict):
            continue
        properties = item.get("properties") if isinstance(item.get("properties"), dict) else {}
        thumbnail = item.get("thumbnail") if isinstance(item.get("thumbnail"), dict) else {}
        picture, copy, page = _web(properties.get("url")), _web(thumbnail.get("src")), _web(item.get("url"))
        if not page or not (picture or copy) or (picture or copy) in seen:
            continue
        seen.add(picture or copy)
        width, height = _size(properties.get("width")), _size(properties.get("height"))
        if width is None or height is None:
            width, height = _size(thumbnail.get("width")), _size(thumbnail.get("height"))
        found.append({"picture": picture or copy, "thumbnail": copy, "page": page,
                      "title": " ".join(str(item.get("title") or "").split())[:TITLE_CHARS],
                      "width": width, "height": height})
        if len(found) >= count:
            break
    return found


def search(query, count, *, transport=None):
    """Brave's pictures for ``query`` (pictures). Raises httpx.HTTPError or
    ValueError when the search does not answer with results; ``transport``
    stands in for the network in tests."""
    key = os.environ.get(KEY_ENV, "").strip()
    if not key:
        raise ValueError("no key")
    headers = {"Accept": "application/json", "X-Subscription-Token": key}
    params = {"q": query, "count": ASK, "safesearch": "strict"}
    with httpx.Client(timeout=SECONDS, trust_env=False, follow_redirects=False, transport=transport) as client:
        response = client.get(ENDPOINT, params=params, headers=headers)
        response.raise_for_status()
        data = response.json()
    if not isinstance(data, dict):
        raise ValueError("no results")
    return pictures(data, count)

"""Serverseitiges Markdown-Rendering für öffentliche Share-Seiten.

Die App rendert Markdown clientseitig mit marked + DOMPurify; auf der
öffentlichen Seite passiert beides serverseitig, damit Crawler den vollen
Inhalt sehen und kein unsanitisiertes LLM-HTML ausgeliefert wird:

  1. markdown-it-py mit html=False – rohes HTML im LLM-Text wird escaped,
     nie interpretiert.
  2. nh3 (ammonia) als zweite Schicht über dem erzeugten HTML; Links nur
     mit http(s)/mailto-Schema und rel="nofollow noopener noreferrer".

[S1]-Quellen-Tags werden vor dem Rendern zu Links auf die Anker der
Quellenliste (#src-1) umgeschrieben. Öffentliche Antworten nutzen nummerierte
Verweise: alte Domain-Labels bleiben nicht als Wortsalat im Lesetext stehen.
Gespeicherte Antworten und Quellenziele werden dabei nicht verändert.
"""

import re
from urllib.parse import quote, urlsplit

import nh3
from markdown_it import MarkdownIt
from markdown_it.token import Token

_MD = (
    MarkdownIt("commonmark", {"html": False, "linkify": False, "typographer": False})
    .enable("table")
    .enable("strikethrough")
)

_URL_SCHEMES = {"http", "https", "mailto"}
_LINK_REL = "nofollow noopener noreferrer"

# Läufe wie "[S1]", "[S1, S2]" oder "[1, 3]" (gleiches Muster wie im Frontend).
SOURCE_RUN_RE = re.compile(r"\[((?:S?\d+)(?:\s*,\s*S?\d+)*)\]", re.IGNORECASE)
_TERMINAL_SOURCE_ORDER_RE = re.compile(
    r"[ \t]*(\[((?:S?\d+)(?:\s*,\s*S?\d+)*)\])"
    r"([.!?]+(?:[\"'”’)\]}]+)?)(?=\s|$)",
    re.IGNORECASE,
)
# Fenced-Code-Blöcke und Inline-Code: dort keine Quellen-Tags ersetzen.
_CODE_SEGMENT_RE = re.compile(r"(```.*?(?:```|$)|`[^`\n]*`)", re.DOTALL)
# Markdown interpretiert die LaTeX-Delimiter \[, \], \( und \) als Escapes.
# Verdoppeln erhaelt sie im HTML, damit KaTeX sie auf Share-Seiten findet.
_MATH_DELIMITER_RE = re.compile(r"\\([\[\]()])")
# Same complete spans and CommonMark punctuation protection as math-render.js.
_MATH_SPAN_RE = re.compile(
    r"\$\$.*?\$\$|\\\[.*?\\\]|\\\(.*?\\\)"
    r"|\\begin\{(equation|align|alignat|gather|CD)\*?\}"
    r".*?\\end\{\1\*?\}",
    re.DOTALL,
)
_MARKDOWN_PUNCTUATION_RE = re.compile(r"[!-/:-@\x5b-\x60{-~]")
# "[ P(\text{a}) = \frac12 ]" without the backslashes of \[ \] (some models
# write it so): same guards as bareBracketsToDisplay in math-render.js.
_BARE_DISPLAY_RE = re.compile(
    r"(^|[^\\\]\w])\[(\s+)((?:[^\[\]\n]|\n(?![ \t]*\n))+?)(\s+)\](?![(\[:])"
)
_LATEX_COMMAND_RE = re.compile(r"\\[A-Za-z]")

# Second-Level-Suffixe wie in getSourceSiteName() im Frontend (z. B. bbc.co.uk).
_SLD_SUFFIXES = {"co", "com", "org", "net", "ac", "gov"}
# Nur harmlose Zeichen im Markdown-Link-Text (keine [, ], ( , ) usw.).
_LABEL_SAFE_RE = re.compile(r"[^A-Za-z0-9._äöü-]+")

# Geminis Grounding-Links zeigen auf einen signierten Google-Redirect; die echte
# Domain steckt dann im Titel der Quelle. Ohne diese Aufloesung traegt die halbe
# Quellenliste denselben nichtssagenden Host (und dasselbe Google-Favicon).
_INDIRECT_SOURCE_HOSTS = {"vertexaisearch.cloud.google.com"}
_BARE_DOMAIN_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?(?:\.[a-z0-9-]+)+$")


def source_host(url, title=""):
    """Die Domain, die eine Quelle tatsaechlich zeigt (Redirects aufgeloest)."""
    try:
        hostname = (urlsplit(str(url or "")).hostname or "").lower()
    except ValueError:
        hostname = ""
    hostname = re.sub(r"^www\.", "", hostname)
    if hostname in _INDIRECT_SOURCE_HOSTS:
        candidate = str(title or "").strip().lower().removeprefix("www.")
        if _BARE_DOMAIN_RE.fullmatch(candidate):
            return candidate
    return hostname


def source_site_name(url, title=""):
    """Kurzer, erkennbarer Site-Name einer Quelle ("en.wikipedia.org" → "wikipedia").

    Python-Pendant zu getSourceSiteName() in index.html, damit Inline-
    Citations auf der Share-Seite genauso aussehen wie im Consensus-Bereich.
    """
    hostname = re.sub(r"^(www|m|amp)\.", "", source_host(url, title))
    parts = [p for p in hostname.split(".") if p]
    if len(parts) < 2:
        return parts[0] if parts else ""
    if len(parts) >= 3 and parts[-2] in _SLD_SUFFIXES:
        return parts[-3]
    return parts[-2]


def _source_labels(sources):
    """Map Quellen-Nummer → (Anzeige-Label) für die Inline-Citations."""
    labels = {}
    for source in sources or []:
        match = re.match(r"^S?(\d+)$", str(source.get("id") or ""), re.IGNORECASE)
        if not match:
            continue
        number = match.group(1).lstrip("0") or "0"
        label = source_site_name(source.get("url"), source.get("title"))
        labels[number] = _LABEL_SAFE_RE.sub("", label) if label else ""
    return labels


def _link_source_tags(md_text, labels, dropped=frozenset()):
    def replace_run(match):
        tokens = [token.strip() for token in match.group(1).split(",")]
        numbers = []
        for token in tokens:
            number = token[1:] if token[:1] in ("s", "S") else token
            number = number.lstrip("0") or "0"
            if number in dropped:
                continue  # source excluded by the topic's source rules
            if number not in labels:
                return match.group(0)  # unbekannte Referenz: Lauf unverändert lassen
            if number not in numbers:
                numbers.append(number)
        if not numbers:
            return ""
        return " ".join(
            "[[%s]](#src-%s)" % (n, n) for n in numbers
        )

    def replace_outside_code(segment):
        # Fussnoten am Satzende folgen dem Satzzeichen: `Aussage.[S1]`.
        segment = _TERMINAL_SOURCE_ORDER_RE.sub(r"\3\1", segment)
        return SOURCE_RUN_RE.sub(
            lambda match: match[0] if segment[match.end():match.end() + 1] == "("
            else replace_run(match), segment,
        )

    parts = _CODE_SEGMENT_RE.split(md_text)
    return "".join(
        part if index % 2 else replace_outside_code(part)
        for index, part in enumerate(parts)
    )


def _bare_brackets_to_display(text):
    def wrap(match):
        before, opening, body, closing = match.groups()
        if len(body) > 2000 or not _LATEX_COMMAND_RE.search(body):
            return match[0]
        return before + "\\[" + opening + body + closing + "\\]"

    return _BARE_DISPLAY_RE.sub(wrap, text)


def _preserve_math_delimiters(md_text):
    def protect_segment(segment):
        segment = _bare_brackets_to_display(segment)
        pieces = []
        cursor = 0
        for match in _MATH_SPAN_RE.finditer(segment):
            pieces.append(_MATH_DELIMITER_RE.sub(r"\\\\\1", segment[cursor:match.start()]))
            pieces.append(_MARKDOWN_PUNCTUATION_RE.sub(lambda char: "\\" + char[0], match[0]))
            cursor = match.end()
        pieces.append(_MATH_DELIMITER_RE.sub(r"\\\\\1", segment[cursor:]))
        return "".join(pieces)

    parts = _CODE_SEGMENT_RE.split(md_text)
    return "".join(
        part if index % 2 else protect_segment(part)
        for index, part in enumerate(parts)
    )


def render_public_markdown(md_text, sources=None, excluded_sources=None, site_links=None):
    """Markdown → sanitisiertes HTML (sicher für `| safe` im Template).

    ``excluded_sources`` are sources removed by source rules: citations to
    them are dropped instead of showing as raw ``[S3]`` text. ``site_links``
    (``source_links.site_mentions``, Watch-Seiten) turns the first mention of a
    source's name into a link to it -- navigation, not a citation -- and gives
    every outbound link in the answer the same look: favicon, new tab.
    """
    text = str(md_text or "")
    labels = _source_labels(sources)
    dropped = frozenset(_source_labels(excluded_sources)) - frozenset(labels)
    if labels or dropped:
        text = _link_source_tags(text, labels, dropped)
    text = _preserve_math_delimiters(text)
    tokens = _MD.parse(text)
    _normalize_citation_links(tokens, sources)
    if site_links is not None:
        _link_site_mentions(tokens, site_links)
    html = _MD.renderer.render(tokens, _MD.options, {})
    return nh3.clean(html, url_schemes=_URL_SCHEMES, link_rel=_LINK_REL, attributes=_ALLOWED_ATTRIBUTES)


# Die Site-Links tragen Klasse, Favicon und öffnen in neuem Tab. Modell-
# Markdown kann keine Attribute setzen (html=False), Klassen kommen nur von hier.
_ALLOWED_ATTRIBUTES = {
    **nh3.ALLOWED_ATTRIBUTES,
    "a": set(nh3.ALLOWED_ATTRIBUTES.get("a", set())) | {"class", "target"},
    "img": set(nh3.ALLOWED_ATTRIBUTES.get("img", set())) | {"class", "loading"},
}


def _favicon_token(domain):
    icon = Token("html_inline", "", 0)
    icon.content = (
        f'<img class="wp-ref-icon" src="/api/topics/favicon?d={quote(str(domain), safe=".-")}" '
        'alt="" width="14" height="14" loading="lazy">'
    )
    return icon


def _site_link_tokens(link):
    opening = Token("link_open", "a", 1)
    opening.attrs = {"href": link["url"], "class": "wp-ref", "target": "_blank"}
    label = Token("text", "", 0)
    label.content = link["name"]
    return [opening, _favicon_token(link["domain"]), label, Token("link_close", "a", -1)]


def _link_site_mentions(tokens, site_links):
    """Wege zu den Quellen im Fließtext.

    Ausgehende Links der Antwort bekommen Favicon, Stil und neuen Tab; die
    erste Nennung je Quelle (``site_links``) wird zum Link auf sie -- nur in
    Textknoten außerhalb von Links und Code. Der Wortlaut bleibt unverändert.
    """
    pending = [link for link in site_links if link.get("name") and link.get("url")]
    for token in tokens:
        if token.type != "inline" or not token.children:
            continue
        children, depth = [], 0
        for child in token.children:
            if child.type == "link_open":
                depth += 1
                href = str(child.attrGet("href") or "")
                domain = source_host(href)
                if href.startswith(("https://", "http://")) and domain and domain not in _INDIRECT_SOURCE_HOSTS:
                    child.attrSet("class", "wp-ref")
                    child.attrSet("target", "_blank")
                    children.extend((child, _favicon_token(domain)))
                    continue
            elif child.type == "link_close":
                depth = max(0, depth - 1)
            if child.type != "text" or depth or not pending:
                children.append(child)
                continue
            content = child.content
            while pending:
                hits = []
                for link in pending:
                    match = re.search(
                        r"(?<![\w.-])" + re.escape(link["name"]) + r"(?![\w-])", content,
                    )
                    if match:
                        hits.append((match.start(), match.end(), link))
                if not hits:
                    break
                start, end, link = min(hits, key=lambda hit: hit[0])
                if start:
                    before = Token("text", "", 0)
                    before.content = content[:start]
                    children.append(before)
                children.extend(_site_link_tokens(link))
                pending.remove(link)
                content = content[end:]
            if content:
                rest = Token("text", "", 0)
                rest.content = content
                children.append(rest)
        token.children = children


def _normalize_citation_links(tokens, sources, *, strip=False):
    """Normalize legacy source links without touching prose, code or destinations.

    Work on parsed links, not domain-looking words: a mention of GitHub or
    Glitchwire in an actual sentence must survive. Only short source labels,
    raw URL labels and already-numbered references are citation candidates.
    """
    known = {}
    for source in sources or []:
        match = re.fullmatch(r"S?(\d+)", str(source.get("id") or ""), re.I)
        if not match:
            continue
        number = str(int(match[1]))
        label = source_site_name(source.get("url"), source.get("title"))
        entry = (number, label)
        known.setdefault(str(source.get("url") or ""), entry)
        known["#src-" + number] = entry
    for token in tokens:
        children = token.children or []
        omitted = set()
        for index, child in enumerate(children[:-2]):
            if child.type != "link_open":
                continue
            href = child.attrGet("href") or ""
            entry = known.get(href)
            label, close = children[index + 1:index + 3]
            if not entry or label.type != "text" or close.type != "link_close":
                continue
            number, site = entry
            value = label.content.strip().lower()
            if href.startswith("#src-") or value in {
                site.lower(), (site + site).lower(), href.lower(),
                source_host(href), "s" + number, number, "[" + number + "]",
            }:
                child.attrSet("href", "#src-" + number)
                label.content = "[" + number + "]"
                if strip:
                    omitted.update((index, index + 1, index + 2))
        if omitted:
            token.children = [child for index, child in enumerate(children) if index not in omitted]


def markdown_to_plaintext(md_text, limit=None, sources=None):
    """Reiner Text (für Meta-Descriptions/Anrisse): rendert und strippt alle Tags.

    Quellen-Marker wie "[S1]" werden entfernt – in einem SEO-Snippet sind sie
    nur technisches Rauschen.
    """
    text = SOURCE_RUN_RE.sub("", str(md_text or ""))
    tokens = _MD.parse(text)
    _normalize_citation_links(tokens, sources, strip=True)
    html = _MD.renderer.render(tokens, _MD.options, {})
    text = nh3.clean(html, tags=set())
    text = re.sub(r"\s+", " ", text).strip()
    if limit is not None and len(text) > limit:
        text = text[: limit - 1].rstrip() + "…"
    return text


# Chat framing around an answer that is published as a page: an opening line
# that announces the answer ("Here's the current picture ...:"), a "Short
# answer" heading right after it, and a closing offer ("If you want, I can
# also ..."). On a page that is updated every week nobody can take the offer,
# and the opening line ended up as the page's search snippet.
_FRAMING_OPENER_RE = re.compile(
    r"^(?:here(?:'|’)s|here is|below is|based on)\b[^\n]*:\s*$", re.IGNORECASE
)
_FRAMING_HEADING_RE = re.compile(
    r"^(?:#{1,6}\s*)?\**\s*(?:short answer|short version|quick answer|tl;?\s?dr|in short)\s*\**:?\s*$",
    re.IGNORECASE,
)
_FRAMING_OFFER_RE = re.compile(
    r"^\W*(?:if you(?:'|’)?d like|if you would like|if you want|would you like|want me to"
    r"|let me know|i can also|i could also)\b",
    re.IGNORECASE,
)


def strip_chat_framing(md_text) -> str:
    """The answer without the chat around it; the answer itself is untouched.

    Only whole paragraphs at the very start or end are dropped, and only when
    they are pure framing. Anything else stays as written.
    """
    blocks = re.split(r"\n\s*\n", str(md_text or "").strip())
    if len(blocks) > 1 and _FRAMING_OPENER_RE.match(blocks[0].strip()):
        blocks = blocks[1:]
    if blocks:
        # The heading is its own paragraph or the first line of the answer's.
        first, _, rest = blocks[0].strip().partition("\n")
        if _FRAMING_HEADING_RE.match(first.strip()):
            if rest.strip():
                blocks[0] = rest.strip()
            elif len(blocks) > 1:
                blocks = blocks[1:]
    while len(blocks) > 1 and _FRAMING_OFFER_RE.match(blocks[-1].strip()):
        blocks = blocks[:-1]
    return "\n\n".join(blocks)


def lead_sentences(md_text, limit=160) -> str:
    """The opening of an answer as plain text, cut at a sentence end if one
    fits: what a search snippet or a hub card shows of it."""
    # Headings label a section; the snippet wants its first sentences.
    body = re.sub(r"^\s{0,3}#{1,6}\s.*$", "", strip_chat_framing(md_text), flags=re.MULTILINE)
    text = markdown_to_plaintext(body)
    if len(text) <= limit:
        return text
    cut = text[:limit]
    end = max(cut.rfind(". "), cut.rfind("? "), cut.rfind("! "))
    if end >= limit // 3:
        return cut[: end + 1]
    return cut[: limit - 1].rsplit(" ", 1)[0].rstrip(",;:") + "…"

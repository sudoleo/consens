"""An HTML file the agent shared, shown in the chat as a page that runs.

The file is the agent's, so nothing of it is trusted: it is served only by
one route (routers/agent_files.py, ``PATH_PREFIX``), and every answer of that
route carries ``HEADERS``. Their policy puts the document into a sandbox of
its own origin (no access to the app's page, storage or sign-in, wherever
the address is opened), lets it run only what the file itself contains and
allows no script, style, font, picture, frame or request from or to another
address, no form, no popup, no download.

The file is not the answer's document itself but the ``srcdoc`` of a frame
in it (``document``): where a framed page may go is decided by the page
around it. Around the file that is this document, whose policy allows no
frame address at all, so the page stays the file.

``refusal`` says why a file is not shown this way, in words for the agent
(agent_vm_tools.share). It reads the markup for what the policy would keep
from loading; it is a courtesy to the agent, never the protection.

An HTML block written in an answer runs the same way (``written_document``,
markdown-stream.js "View as page"). Its code is in the browser already and
never comes here: the route answers one fixed document under the same
``HEADERS``, and the app's page hands that document the code as a message.
A frame of the app's own page could not run it: it would inherit the app's
policy, which allows no inline script and does allow the app's addresses.
"""

from __future__ import annotations

import html
import json
import re

PATH_PREFIX = "/agent/pages/"
# No address of a shared page reads as this one (agent_pages._TOKEN).
WRITTEN_PATH = PATH_PREFIX + "written"
# A page loads whole each time it comes into view, and nothing of it is cached.
MAX_BYTES = 2 * 1024 * 1024
# 'unsafe-eval' adds nothing to what the file's own inline script may do
# and is what charting libraries copied into a file need.
POLICY = "; ".join((
    "sandbox allow-scripts",
    "default-src 'none'",
    "script-src 'unsafe-inline' 'unsafe-eval'",
    "style-src 'unsafe-inline'",
    "img-src data: blob:",
    "media-src data: blob:",
    "font-src data:",
    "connect-src 'none'",
    "frame-src 'none'",
    "form-action 'none'",
    "base-uri 'none'",
    "frame-ancestors 'self'",
))
HEADERS = {
    "Content-Security-Policy": POLICY,
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "SAMEORIGIN",
    "Referrer-Policy": "no-referrer",
    "Cache-Control": "private, no-store",
}
CONTENT_TYPE = "text/html; charset=utf-8"

_NAMED = re.compile(r"\.html?$", re.IGNORECASE)
_TAG_NAME = re.compile(r"[a-zA-Z][a-zA-Z0-9:-]*")
# A start tag's attributes as a page's parser reads them: a quote opens a
# value only after "=", and a ">" inside one does not end the tag.
# Possessive, so a tag that never ends costs one pass.
_TAG_REST = re.compile(r"""(?:=[\t\n\f\r ]*(?:"[^"]*"|'[^']*')|[^>])*+>""")
_ATTRIBUTE = re.compile(r"""([^\s"'<>/=]+)(?:\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s"'=<>`]+)))?""")
_CLOSERS = {name: re.compile(rf"</{name}\b", re.IGNORECASE) for name in ("script", "style")}
# Only the beginning of an address says where it leads, and every run is
# bounded: a file of nothing but "url(" or spaces costs one pass.
_CSS_URL = re.compile(r"""url\(\s{0,40}(?:"([^"]{0,300})|'([^']{0,300})|([^)\s"']{1,300}))"""
                      r"""|@import\s{1,40}(?:"([^"]{0,300})|'([^']{0,300}))""", re.IGNORECASE)
_MODULE = re.compile(r"""(?:\bfrom\s{0,40}|\bimport\s{0,40}\(?\s{0,40})["']((?:https?:)?//[^"'\s]{1,300})""")
# What an element loads, by attribute.
_LOADS = {
    "script": ("src",), "img": ("src", "srcset"), "source": ("src", "srcset"), "video": ("src", "poster"),
    "audio": ("src",), "track": ("src",), "embed": ("src",), "iframe": ("src",), "frame": ("src",),
    "object": ("data",), "image": ("href", "xlink:href"), "use": ("href", "xlink:href"),
}
_READ = frozenset({*_LOADS, "link"})
_HERE = ("data:", "blob:", "about:", "javascript:", "#")
# What a refusal names: the first addresses, each by its beginning.
_NAMED_FIRST = 3
_ADDRESS_CHARS = 100


def named(name) -> bool:
    """Whether a file's name says it is an HTML page."""
    return bool(_NAMED.search(str(name or "")))


def text(raw):
    """The file as the text the route serves, or None: UTF-8 only (the
    answer says so in its type), a byte order mark aside."""
    try:
        return bytes(raw).decode("utf-8-sig")
    except UnicodeDecodeError:
        return None


def _elsewhere(value) -> str:
    """``value`` when it names something outside the file, else ''."""
    address = str(value or "").strip()
    if not address or address[:11].lower().startswith(_HERE):
        return ""
    address = html.unescape(address[:300]).strip()
    return "" if not address or address.lower().startswith(_HERE) else address


def _css(source, found):
    for match in _CSS_URL.finditer(source):
        address = _elsewhere(next((group for group in match.groups() if group is not None), ""))
        if address:
            found.append(address)


def _attributes(source):
    values = {}
    for match in _ATTRIBUTE.finditer(source):
        value = next((group for group in match.groups()[1:] if group is not None), "")
        values.setdefault(match.group(1).lower(), value)
    return values


def loads(source):
    """The addresses outside the file its markup loads, in its order: a
    script, a stylesheet, a picture, a frame, an import. One pass, whatever
    the markup: nothing here follows a parser's rules further than that a
    comment, a script and a style end where a page's parser ends them."""
    found, at = [], 0
    while True:
        at = source.find("<", at)
        if at < 0:
            break
        if source.startswith("<!--", at):
            end = source.find("-->", at + 4)
            if end < 0:
                break
            at = end + 3
            continue
        name = _TAG_NAME.match(source, at + 1)
        if not name:
            at += 1
            continue
        rest = _TAG_REST.match(source, name.end())
        if not rest:
            # The rest of the file is a tag that never ends.
            break
        tag, at = name.group().lower(), rest.end()
        written = source[name.end():rest.end() - 1]
        # Most tags load nothing: their attributes are read only where one could.
        attributes = _attributes(written) if tag in _READ or "style" in written.lower() else {}
        for attribute in _LOADS.get(tag, ()):
            # The first address of a srcset stands for it.
            address = _elsewhere(attributes.get(attribute, "").split(",")[0].strip().split(" ")[0]
                                 if attribute == "srcset" else attributes.get(attribute))
            if address:
                found.append(address)
        if tag == "link" and "stylesheet" in attributes.get("rel", "").lower().split():
            address = _elsewhere(attributes.get("href"))
            if address:
                found.append(address)
        if "style" in attributes:
            _css(attributes["style"], found)
        if tag in _CLOSERS:
            closer = _CLOSERS[tag].search(source, at)
            inner = source[at:closer.start()] if closer else source[at:]
            if tag == "style":
                _css(inner, found)
            elif not attributes.get("src"):
                found.extend(match.group(1) for match in _MODULE.finditer(inner))
            if not closer:
                break
            at = closer.end()
    return list(dict.fromkeys(found))


def refusal(raw):
    """Why the file is not shown as a page in the chat, in a sentence for
    the agent, or None when it is."""
    if len(raw) > MAX_BYTES:
        return (f"it is larger than {MAX_BYTES // (1024 * 1024)} MB, the most the chat loads as a page.")
    source = text(raw)
    if source is None:
        return "it is not UTF-8 text."
    outside = loads(source)
    if not outside:
        return None
    shown = ", ".join(address[:_ADDRESS_CHARS] for address in outside[:_NAMED_FIRST])
    more = len(outside) - _NAMED_FIRST
    return (f"it loads {shown}{f' and {more} more' if more > 0 else ''} from outside the file, and a page in the "
            "chat runs without the network: scripts, styles, fonts and pictures have to be inside the file itself "
            "(inline, pictures and fonts as data: URLs).")


# Added after the file's own text. A link to another document cannot open
# here: followed, it would leave the frame empty where the page stood. So a
# click on one does nothing. A link within the page (#…) goes there through
# the page's own address: a frame's document resolves "#end" against the
# address of the document around it, which is another document to the
# browser. The page's own handlers work as written. A convenience for the
# reader, no part of the protection: the page's script could take it away.
_STAY = ("<script>addEventListener('click',function(e){var a=e.target&&e.target.closest&&"
         "e.target.closest('a[href],area[href]');if(!a)return;var h=a.getAttribute('href')||'';"
         "if(/^javascript:/i.test(h))return;e.preventDefault();"
         "if(h.charAt(0)==='#')try{location.hash=h}catch(x){}},true)</script>")

# Added after it as well. The chat cannot look into the page, so the page
# says how tall its content is and the chat gives its frame that height
# (agent-workspace.js pageCard, which bounds it): the page then stands in the
# answer whole, without a second scrollbar. ``box`` is what the page's flow
# takes, the only measure that can be less than the frame; ``full`` reaches
# what lies outside the flow but is never less than the frame. A page that
# grew for ``full`` stays there until its flow changes: else the smaller
# ``box`` would take the height back, and the two would trade places for
# ever. Measured at once and on load, not on a frame of animation: a browser
# draws no frames for a page that is not on screen yet, and the height is
# wanted before it gets there. A convenience like _STAY: a page whose script
# says something else gets the height it says, within the chat's bounds.
_FIT = ("<script>(function(){var d=document.documentElement,last=0,asked=0,was=0,due=0;"
        "function fit(){due=0;var view=innerHeight,box=Math.ceil(d.getBoundingClientRect().height),"
        "full=d.scrollHeight,h;if(full>view+1){h=Math.max(full,box);asked=h;was=box}"
        "else if(asked&&Math.abs(view-asked)<2&&box===was)return;else{h=box;asked=0}"
        "if(h===last||!(h>0))return;last=h;try{top.postMessage({consensPage:{height:h}},'*')}catch(x){}}"
        "function soon(){if(!due)due=setTimeout(fit,30)}"
        "if(window.ResizeObserver){var o=new ResizeObserver(soon);o.observe(d);"
        "if(document.body)o.observe(document.body)}"
        "addEventListener('load',fit);addEventListener('resize',soon);"
        "addEventListener('click',soon,true);fit()})()</script>")


def document(source, name) -> bytes:
    """The answer's body: the file as the ``srcdoc`` of a sandboxed frame
    that fills a document of ours. The frame inherits this document's policy
    and sandbox, and the document names no address a frame of it may go to."""
    title = html.escape(str(name or "Page"), quote=True)
    source = source + "\n" + _STAY + _FIT
    return (
        '<!doctype html>\n<html lang="en"><head><meta charset="utf-8">'
        '<meta name="color-scheme" content="light"><title>' + title + "</title>"
        "<style>html,body{height:100%;margin:0;background:#fff}"
        "iframe{display:block;width:100%;height:100%;border:0}</style></head>"
        '<body><iframe sandbox="allow-scripts" title="' + title + '" srcdoc="'
        + html.escape(source, quote=True) + '"></iframe></body></html>\n'
    ).encode("utf-8")


# The script of ``written_document``. It hears one message, and only from the
# page that frames it: frame-ancestors lets no page but the app's do that, so
# opened by itself or from another site's window the document stays empty and
# shows nobody's markup under this address. The code stands as the ``srcdoc``
# of a frame, as a shared file does in ``document``; a later message, the
# page's own included, changes nothing.
_HOST = ("<script>(function(){var shown=0;addEventListener('message',function(e){"
         "if(shown||parent===window||e.source!==parent)return;"
         "var said=e.data&&e.data.consensPage,source=said&&said.source;"
         "if(typeof source!=='string')return;shown=1;"
         "var frame=document.createElement('iframe');frame.setAttribute('sandbox','allow-scripts');"
         "frame.title='Page';frame.srcdoc=source+'\\n'+%s;document.body.appendChild(frame)})})()</script>")


def written_document() -> bytes:
    """The answer's body for a page written in an answer: a document of ours
    that waits for the code and frames it. The same for every request; the
    frame it makes inherits this document's policy and sandbox."""
    # A "</script>" inside the literal would end the script it stands in:
    # the literal holds no "<" at all.
    stay = json.dumps(_STAY).replace("<", "\\u003c")
    return (
        '<!doctype html>\n<html lang="en"><head><meta charset="utf-8">'
        '<meta name="color-scheme" content="light"><title>Page</title>'
        "<style>html,body{height:100%;margin:0;background:#fff}"
        "iframe{display:block;width:100%;height:100%;border:0}</style></head>"
        "<body>" + _HOST % stay + "</body></html>\n"
    ).encode("utf-8")

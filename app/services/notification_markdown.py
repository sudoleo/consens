"""Model answers in notifications: the public pages' Markdown, re-emitted.

A Watch delivers a Markdown answer. Escaped into a mail or a Telegram
message it reads as ``##``, ``**`` and ``|---|`` -- in the very message a
reader waited weeks for. All outputs here start from the HTML the public
pages render (``public_markdown.render_public_markdown``: markdown-it with
``html=False``, then nh3), so a notification shows the answer exactly as
the page does. A small re-emitter then writes it for each channel:

- ``answer_mail_html``: the same elements with inline styles (mail clients
  ignore page CSS) plus the dark-mode classes of ``mailer.MAIL_DARK_CSS``;
  tables sit in a scroll box so a wide one never widens the mail.
- ``answer_plain``: paragraphs, ``- `` lists and ``a | b`` rows for the
  text part.
- ``answer_telegram``: the subset the Bot API accepts (b, i, s, code, a),
  lists as ``•`` lines, inside a length budget that never cuts a tag.

``[S1]`` citations become a small link to the source in mail and are left
out of text and Telegram, where the sources are listed separately. Images in
an answer are dropped: a URL a model wrote never loads in a mail client.
"""

from __future__ import annotations

import html
import re
from html.parser import HTMLParser

from app.services.public_markdown import (
    SOURCE_RUN_RE,
    render_public_markdown,
    source_site_name,
    strip_chat_framing,
)

_LINK_SCHEMES = ("http://", "https://", "mailto:")
_VOID = {"br", "hr", "img"}
_BLOCKS = {"p", "h1", "h2", "h3", "h4", "h5", "h6", "pre", "li", "tr", "hr"}
_CONTAINERS = {"ul", "ol", "blockquote", "table", "thead", "tbody", "root"}
# "[S1][S2]." -> "[S1, S2].": one run, so the public pipeline puts the whole
# run behind the full stop instead of splitting it around it.
_ADJACENT_RUNS_RE = re.compile(
    r"\[((?:S?\d+)(?:\s*,\s*S?\d+)*)\]\s*\[((?:S?\d+)(?:\s*,\s*S?\d+)*)\]", re.IGNORECASE,
)
_CODE_SEGMENT_RE = re.compile(r"(```.*?(?:```|$)|`[^`\n]*`)", re.DOTALL)
MONO = "SFMono-Regular,Menlo,Consolas,monospace"


class _Node:
    __slots__ = ("tag", "attrs", "children")

    def __init__(self, tag: str, attrs: dict):
        self.tag = tag
        self.attrs = attrs
        self.children: list = []


class _Tree(HTMLParser):
    """nh3's output as a small tree (it is well formed; stray end tags are
    ignored)."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = _Node("root", {})
        self._stack = [self.root]

    def handle_starttag(self, tag, attrs):
        node = _Node(tag, {key: value or "" for key, value in attrs})
        self._stack[-1].children.append(node)
        if tag not in _VOID:
            self._stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self._stack[-1].children.append(_Node(tag, {key: value or "" for key, value in attrs}))

    def handle_endtag(self, tag):
        for index in range(len(self._stack) - 1, 0, -1):
            if self._stack[index].tag == tag:
                del self._stack[index:]
                return

    def handle_data(self, data):
        self._stack[-1].children.append(data)


def _task_box(node) -> str | None:
    """A checklist item's box (public_markdown._mark_task_items) as a
    character: a notification has no stylesheet to draw it with."""
    if node.tag != "span" or "md-task-box" not in node.attrs.get("class", "").split():
        return None
    return "☑ " if node.attrs.get("data-checked") == "true" else "☐ "


def _merge_adjacent_runs(md_text: str) -> str:
    def merge(segment: str) -> str:
        previous = None
        while previous != segment:
            previous = segment
            segment = _ADJACENT_RUNS_RE.sub(lambda match: f"[{match[1]}, {match[2]}]", segment)
        return segment

    parts = _CODE_SEGMENT_RE.split(md_text)
    return "".join(part if index % 2 else merge(part) for index, part in enumerate(parts))


def _tree(md_text, sources, excluded_sources) -> _Node:
    text = _merge_adjacent_runs(strip_chat_framing(md_text))
    parser = _Tree()
    parser.feed(render_public_markdown(text, sources or [], excluded_sources=excluded_sources))
    parser.close()
    return parser.root


def _citations(sources) -> dict:
    """Number -> (url, short site name) for the [S1] links of the answer."""
    found = {}
    for source in sources or []:
        match = re.fullmatch(r"S?(\d+)", str(source.get("id") or ""), re.IGNORECASE)
        url = str(source.get("url") or "")
        if match and url.startswith(("http://", "https://")):
            found[str(int(match[1]))] = (url, source_site_name(url, source.get("title")) or "source")
    return found


def _without_runs(text: str) -> str:
    # A run the pipeline could not resolve ("[S9]": no such source) is noise.
    return SOURCE_RUN_RE.sub("", text)


def _text_of(node) -> str:
    if isinstance(node, str):
        return node
    if node.tag == "img":
        return ""
    return "".join(_text_of(child) for child in node.children)


# ---------------------------------------------------------------------------
# Mail
# ---------------------------------------------------------------------------

def _mail_styles(palette: dict) -> dict:
    ink, ink2, ink3 = palette["ink"], palette["ink_2"], palette["ink_3"]
    line, line_soft, raise_ = palette["line"], palette["line_soft"], palette["raise"]
    heading = f"font-weight:600;color:{ink}"
    return {
        "p": ("margin:0 0 12px", ""),
        "h1": (f"margin:20px 0 8px;font-size:17px;line-height:1.35;{heading}", "cx-ink"),
        "h2": (f"margin:20px 0 8px;font-size:17px;line-height:1.35;{heading}", "cx-ink"),
        "h3": (f"margin:18px 0 6px;font-size:15px;line-height:1.4;{heading}", "cx-ink"),
        "h4": (f"margin:16px 0 6px;font-size:15px;line-height:1.4;{heading}", "cx-ink"),
        "h5": (f"margin:16px 0 6px;font-size:15px;line-height:1.4;{heading}", "cx-ink"),
        "h6": (f"margin:16px 0 6px;font-size:15px;line-height:1.4;{heading}", "cx-ink"),
        "ul": ("margin:0 0 12px;padding:0 0 0 22px", ""),
        "ol": ("margin:0 0 12px;padding:0 0 0 22px", ""),
        "li": ("margin:0 0 4px", ""),
        "strong": (heading, "cx-ink"),
        "b": (heading, "cx-ink"),
        "em": ("font-style:italic", ""),
        "i": ("font-style:italic", ""),
        "s": ("text-decoration:line-through", ""),
        "del": ("text-decoration:line-through", ""),
        "a": (f"color:{ink};text-decoration:underline", "cx-ink"),
        "code": (
            f"font-family:{MONO};font-size:13px;background:{raise_};"
            "padding:1px 4px;border-radius:4px", "cx-raise",
        ),
        "pre": (
            f"margin:0 0 12px;padding:10px 12px;background:{raise_};border-radius:8px;"
            f"font-family:{MONO};font-size:13px;line-height:1.5;white-space:pre-wrap;"
            "word-break:break-word", "cx-raise",
        ),
        "blockquote": (
            f"margin:0 0 12px;padding:0 0 0 12px;border-left:2px solid {line};color:{ink2}",
            "cx-soft cx-line",
        ),
        "table": (
            "border-collapse:collapse;width:100%;font-size:14px;line-height:1.45", "",
        ),
        "th": (
            f"text-align:left;vertical-align:bottom;padding:6px 12px 6px 0;"
            f"border-bottom:1px solid {line};{heading}", "cx-ink cx-line",
        ),
        "td": (
            f"text-align:left;vertical-align:top;padding:6px 12px 6px 0;"
            f"border-bottom:1px solid {line_soft}", "cx-line-soft",
        ),
        "hr": (f"border:0;border-top:1px solid {line};margin:16px 0", "cx-line"),
        "citation": (
            f"display:inline-block;padding:0 6px;border-radius:999px;background:{raise_};"
            f"color:{ink3};font-size:12px;line-height:18px;text-decoration:none;"
            "vertical-align:1px", "cx-raise cx-muted",
        ),
    }


def _open(tag: str, styles: dict, extra: str = "", *, first: bool = False) -> str:
    style, classes = styles[tag]
    if first:
        # The answer box sets the space above its first line.
        style = re.sub(r"^margin:\d+px", "margin:0", style)
    class_attr = f' class="{classes}"' if classes else ""
    return f'<{tag}{extra}{class_attr} style="{style}">'


def _mail_node(node, styles, citations, *, in_code=False, in_pre=False, first=False) -> str:
    if isinstance(node, str):
        return html.escape(node if in_code else _without_runs(node), quote=False)
    tag = node.tag
    if tag == "img":
        return ""
    if tag == "br":
        return "<br>"
    box = _task_box(node)
    if box:
        return box
    if tag == "hr":
        style, classes = styles["hr"]
        return f'<hr class="{classes}" style="{style}">'
    child_code = in_code or tag in {"code", "pre"}
    child_pre = in_pre or tag == "pre"
    inner_parts = []
    for child in node.children:
        if isinstance(child, str) and not child.strip() and tag in _CONTAINERS | {"tr"}:
            continue  # the pipeline's newlines between block tags
        inner_parts.append(_mail_node(
            child, styles, citations, in_code=child_code, in_pre=child_pre,
            first=first and not inner_parts,
        ))
    inner = "".join(inner_parts)
    if tag == "root":
        return inner
    if tag == "a":
        href = node.attrs.get("href", "")
        if href.startswith("#src-"):
            cited = citations.get(href.removeprefix("#src-"))
            if not cited:
                return ""
            style, classes = styles["citation"]
            return (
                f' <a href="{html.escape(cited[0])}" class="{classes}" style="{style}">'
                f"{html.escape(cited[1], quote=False)}</a>"
            )
        if not href.startswith(_LINK_SCHEMES):
            return inner
        return _open("a", styles, f' href="{html.escape(href)}"') + inner + "</a>"
    if tag == "table":
        # A wide table scrolls inside its box instead of widening the mail.
        return (
            '<div style="overflow-x:auto;margin:0 0 12px">'
            + _open("table", styles, ' cellpadding="0" cellspacing="0" border="0"')
            + inner + "</table></div>"
        )
    if tag in {"thead", "tbody", "tr"}:
        return f"<{tag}>{inner}</{tag}>"
    if tag == "code" and in_pre:
        return inner
    if tag not in styles:
        return inner  # anything else keeps its text, never its tag
    if tag in _BLOCKS and not _visible(inner).strip():
        return ""  # a paragraph that only held an image
    extra = ""
    if tag == "ol" and node.attrs.get("start", "").isdecimal():
        extra = f' start="{int(node.attrs["start"])}"'  # a list text broke up counts on
    return f"{_open(tag, styles, extra, first=first)}{inner}</{tag}>"


def answer_mail_html(md_text, *, palette: dict, sources=None, excluded_sources=None) -> str:
    """The answer as mail HTML: inline styles, nothing a mail client loads."""
    root = _tree(md_text, sources, excluded_sources)
    return _mail_node(root, _mail_styles(palette), _citations(sources), first=True)


# ---------------------------------------------------------------------------
# Plain text and Telegram: the answer as a list of blocks
# ---------------------------------------------------------------------------

def _inline(node, mode: str, *, in_code=False) -> str:
    """One block's content: ``plain`` text or Telegram ``tg`` markup."""
    if isinstance(node, str):
        text = node if in_code else _without_runs(node)
        text = text.replace("\n", " ") if not in_code else text
        return html.escape(text, quote=False) if mode == "tg" else text
    tag = node.tag
    if tag == "img" or tag in {"ul", "ol"}:
        return ""  # images never travel; nested lists are blocks of their own
    if tag == "br":
        return "\n"
    box = _task_box(node)
    if box:
        return box
    child_code = in_code or tag == "code"
    inner = "".join(_inline(child, mode, in_code=child_code) for child in node.children)
    if tag == "a":
        href = node.attrs.get("href", "")
        if href.startswith("#src-"):
            return ""
        if not href.startswith(("http://", "https://")):
            return inner
        if mode == "tg":
            return f'<a href="{html.escape(href, quote=True)}">{inner}</a>' if inner.strip() else ""
        label = inner.strip()
        return label if label == href or not label else f"{label} ({href})"
    if mode == "tg":
        wrap = {"strong": "b", "b": "b", "em": "i", "i": "i", "s": "s", "del": "s", "code": "code"}.get(tag)
        if wrap and inner:
            return f"<{wrap}>{inner}</{wrap}>"
    if tag == "p":
        return inner + " "
    return inner


def _blocks(node, mode: str, *, depth=0, ordered=False, counter=None,
            group="") -> list[tuple[str, str]]:
    """``(kind, text)`` per block. Lines of one list or one table share a
    kind and follow each other directly; everything else is a paragraph."""
    blocks: list[tuple[str, str]] = []
    if isinstance(node, str):
        text = " ".join(node.split())
        return [("para", html.escape(text, quote=False) if mode == "tg" else text)] if text else []
    tag = node.tag
    if tag == "img":
        return []
    if tag in {"ul", "ol"}:
        start = node.attrs.get("start", "")
        count = [int(start) - 1 if tag == "ol" and start.isdecimal() else 0]
        group = group or f"list{id(node)}"
        for child in node.children:
            if isinstance(child, _Node) and child.tag == "li":
                blocks += _blocks(child, mode, depth=depth + 1, ordered=tag == "ol",
                                  counter=count, group=group)
        return blocks
    if tag == "li":
        counter[0] += 1
        marker = f"{counter[0]}." if ordered else ("•" if mode == "tg" else "-")
        indent = "  " * (depth - 1)
        text = " ".join(_inline(node, mode).split())
        if text:
            blocks.append((group, f"{indent}{marker} {text}"))
        for child in node.children:
            if isinstance(child, _Node) and child.tag in {"ul", "ol"}:
                blocks += _blocks(child, mode, depth=depth, group=group)
        return blocks
    if tag == "table":
        group = f"table{id(node)}"
        for child in node.children:
            blocks += _blocks(child, mode, depth=depth, group=group)
        return blocks
    if tag == "tr":
        cells = [cell for cell in node.children if isinstance(cell, _Node) and cell.tag in {"th", "td"}]
        header = any(cell.tag == "th" for cell in cells)
        if mode == "tg" and header:
            # A header row is bold as a whole; no entity nests inside it.
            row = _bold(" · ".join(" ".join(_without_runs(_text_of(cell)).split()) for cell in cells))
        else:
            row = (" · " if mode == "tg" else " | ").join(
                " ".join(_inline(cell, mode).split()) for cell in cells
            )
        if _visible(row).strip(" |·"):
            blocks.append((group or "row", row))
        return blocks
    if tag == "pre":
        code = _text_of(node).rstrip("\n")
        if code.strip():
            blocks.append(("para", html.escape(code, quote=False) if mode == "tg" else code))
        return blocks
    if tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
        text = " ".join(_without_runs(_text_of(node)).split())
        if text:
            blocks.append(("para", _bold(text) if mode == "tg" else text))
        return blocks
    if tag == "p":
        text = " ".join(_inline(node, mode).split())
        if text:
            blocks.append(("para", text))
        return blocks
    if tag == "hr":
        return []
    for child in node.children:
        blocks += _blocks(child, mode, depth=depth, group=group)
    return blocks


def _join(blocks) -> str:
    out = []
    previous = ""
    for kind, text in blocks:
        if out:
            out.append("\n" if kind == previous and kind != "para" else "\n\n")
        out.append(text)
        previous = kind
    return "".join(out)


def answer_plain(md_text, *, sources=None, excluded_sources=None) -> str:
    """The answer for the text part of a mail: no Markdown signs left."""
    return _join(_blocks(_tree(md_text, sources, excluded_sources), "plain"))


_TAG_RE = re.compile(r"<[^>]+>")


def _visible(markup: str) -> str:
    return html.unescape(_TAG_RE.sub("", markup))


def _bold(text: str) -> str:
    return f"<b>{html.escape(text, quote=False)}</b>"


def answer_telegram(md_text, *, sources=None, excluded_sources=None, limit=1_500) -> str:
    """The answer in Telegram's HTML subset, at most ``limit`` characters of
    markup. Whole blocks are kept; the first block that does not fit is cut
    at a word as plain text, so no tag is ever left open."""
    blocks = _blocks(_tree(md_text, sources, excluded_sources), "tg")
    kept: list[tuple[str, str]] = []
    for kind, text in blocks:
        if len(_join(kept + [(kind, text)])) <= limit:
            kept.append((kind, text))
            continue
        room = limit - len(_join(kept + [(kind, "")])) - 1  # 1 for the "…"
        words = _visible(text)[:max(0, room)]
        if " " in words:
            words = words.rsplit(" ", 1)[0]
        words = words.rstrip(" ,;:.")
        escaped = html.escape(words, quote=False)
        while len(escaped) > room and " " in words:
            words = words.rsplit(" ", 1)[0]
            escaped = html.escape(words, quote=False)
        if len(words) >= 40 and len(escaped) <= room:
            kept.append((kind, escaped + "…"))
            return _join(kept)
        return _join(kept) + ("…" if kept else "")
    return _join(kept)

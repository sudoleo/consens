"""German for German readers: one dictionary, applied where English is rendered.

The interface is written in English: templates, scripts and the server's
sentences. A German reader gets the same pages with every English segment that
has an entry in ``app/i18n/de/*.json`` replaced, in two places with the same
rules:

- on the server, in the finished HTML of every page (``app/core/i18n_middleware.py``),
  so the first paint, the tab title and the search snippet are German;
- in the browser, by ``static/js/i18n.js``, for everything a script writes
  later (a MutationObserver), with ``App.t`` for words that never reach the
  DOM (a confirm(), the clipboard).

The code itself never changes language: a script compares, stores and sends
its English words as before. Only what a reader sees is translated.

**Segments.** A block element (``p``, ``li``, ``button``, ``h2``, …) holds runs
of text and inline elements. A run is looked up whole, its inline elements
written as numbered markers, so a translation may reorder them::

    Read the <a href="/privacy">privacy policy</a> first.
    key:   Read the <0>privacy policy</0> first.
    value: Lies zuerst die <0>Datenschutzerklärung</0>.

The element keeps its attributes and, in the browser, its listeners: the
translation moves the original node. Elements without words (an icon, a
``<br>``) and elements that must not change (``code``, ``translate="no"``) are
self-closing markers ``<0/>``. A run without a whole entry falls back to its
pieces: every text node and inline element on its own.

**Patterns.** A key with ``{name}`` placeholders matches any text with the
same words around them (``{n} chats`` → ``{n} Chats``); a captured value that
has an entry of its own is translated too.

**Entries.** ``"English": "German"``; an identical value marks a name that
stays (``"consens.io": "consens.io"``) and counts as covered. Keys starting
with ``_`` are comments. Files whose name starts with ``page-`` stay on the
server (long public and legal pages); every other file also goes to the
browser.
"""

from __future__ import annotations

import hashlib
import html
import json
import re
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable


ROOT = Path(__file__).resolve().parents[2]
DICTIONARY_ROOT = ROOT / "app" / "i18n"
ENGINE_SCRIPT = ROOT / "static" / "js" / "i18n.js"

DEFAULT_LANGUAGE = "en"
LANGUAGES = ("en", "de")
TRANSLATED_LANGUAGES = ("de",)
LANGUAGE_COOKIE = "consens_lang"
LANGUAGE_NAMES = {"en": "English", "de": "Deutsch"}

# Pages with their own German address (/de/about). Every other page keeps one
# address and follows the reader's language; its content is a chat, a model
# answer or a topic, which stays in the language it was written in.
LOCALIZED_PATHS = frozenset({
    "/", "/about", "/ai-model-comparison", "/benchmark", "/consensus-engine",
    "/imprint", "/model-pulse", "/privacy", "/terms",
})
LOCALE_PREFIX = {"de": "/de"}
OG_LOCALE = {"en": "en_US", "de": "de_DE"}


# ---------------------------------------------------------------------------
# Text and patterns
# ---------------------------------------------------------------------------

_SPACE = re.compile(r"\s+")
_PLACEHOLDER = re.compile(r"\{([A-Za-z_]\w*|\d+)\}")
_MARKER = re.compile(r"<(\d+)>|</(\d+)>|<(\d+)/>")
_LETTER = re.compile(r"[^\W\d_]")


def normalize(text: str) -> str:
    """One space between words, none at the ends: the form every key has."""
    return _SPACE.sub(" ", text).strip()


def has_letter(text: str) -> bool:
    return bool(_LETTER.search(text))


# Words no name is made of: a value holding one is a piece of an English
# sentence, not a model, a file or a person.
GLUE_WORDS = frozenset({
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "has", "have", "in", "is", "it",
    "not", "of", "on", "or", "than", "that", "the", "there", "this", "to", "was", "were", "with", "your",
})


def english_prose(text: str) -> bool:
    return any(word in GLUE_WORDS for word in re.findall(r"[a-z]+", text.lower()))


def markers(text: str) -> list[str]:
    return sorted(match.group(0) for match in _MARKER.finditer(text))


def placeholders(text: str) -> list[str]:
    return sorted(_PLACEHOLDER.findall(text))


def fill(text: str, params: dict | None) -> str:
    """``{name}`` → ``params[name]``; unknown names stay as they are."""
    if not params:
        return text
    return _PLACEHOLDER.sub(lambda match: str(params[match.group(1)]) if match.group(1) in params else match.group(0), text)


@dataclass(frozen=True)
class _Pattern:
    key: str
    value: str
    regex: re.Pattern
    names: tuple[str, ...]
    hint: str
    weight: int

    @classmethod
    def build(cls, key: str, value: str) -> "_Pattern":
        parts = _PLACEHOLDER.split(key)
        literals = parts[0::2]
        names = tuple(parts[1::2])
        regex = "".join(
            re.escape(literal) + (f"(?P<p{index}>.+?)" if index < len(names) else "")
            for index, literal in enumerate(literals)
        )
        hint = max(literals, key=len)
        return cls(key, value, re.compile(regex, re.S), names, hint, sum(len(item) for item in literals))


class Catalog:
    """Exact entries in a dict, patterns tried longest-literal first."""

    def __init__(self, entries: dict[str, str]):
        self.exact: dict[str, str] = {}
        self.patterns: list[_Pattern] = []
        self.rejected: list[tuple[str, str]] = []
        for raw_key, raw_value in entries.items():
            if not isinstance(raw_key, str) or not isinstance(raw_value, str) or raw_key.startswith("_"):
                continue
            key, value = normalize(raw_key), normalize(raw_value)
            if not key or not value:
                continue
            if markers(key) != markers(value) or not set(placeholders(value)) <= set(placeholders(key)):
                self.rejected.append((raw_key, raw_value))
                continue
            if _PLACEHOLDER.search(key):
                self.patterns.append(_Pattern.build(key, value))
            else:
                self.exact[key] = value
        self.patterns.sort(key=lambda pattern: -pattern.weight)
        self.templates = {pattern.key: pattern.value for pattern in self.patterns}
        self.values = frozenset(self.exact.values()) | frozenset(self.templates.values())

    def __len__(self) -> int:
        return len(self.exact) + len(self.patterns)

    def lookup(self, text: str, *, nested: bool = True) -> str | None:
        found = self.exact.get(text)
        if found is not None:
            return found
        for pattern in self.patterns:
            if pattern.hint and pattern.hint not in text:
                continue
            match = pattern.regex.fullmatch(text)
            if match is None:
                continue
            captured: dict[str, str] = {}
            for index, name in enumerate(pattern.names):
                if name not in captured:
                    captured[name] = self._captured(match.group(f"p{index}"), nested)
            if any(value is None for value in captured.values()):
                continue
            return fill(pattern.value, captured)
        return None

    def _captured(self, value: str, nested: bool) -> str | None:
        """A value a pattern caught, translated when it has an entry of its own.

        One level deep, so "{0} Model agreement …" also translates the
        sentence that fills {0}; the space around the value stays. English
        prose without an entry is no value (None): "{n} questions" must not
        turn "Quick synthesis for everyday questions" into half German.
        """
        key = normalize(value)
        if not key or not has_letter(key):
            return value
        found = self.exact.get(key)
        if found is None and nested:
            found = self.lookup(key, nested=False)
        if found is None:
            return None if english_prose(key) else value
        lead, trail = _edge_space(value)
        return lead + found + trail

    def translate(self, text: str, params: dict | None = None) -> str:
        """``App.t`` on the server: the German sentence, or the English one."""
        key = normalize(text)
        found = self.templates.get(key)
        if found is None:
            found = self.lookup(key)
        return fill(found if found is not None else text, params)


def _dictionary_files(language: str) -> list[Path]:
    folder = DICTIONARY_ROOT / language
    return sorted(folder.glob("*.json")) if folder.is_dir() else []


def _read_entries(paths: Iterable[Path]) -> dict[str, str]:
    entries: dict[str, str] = {}
    for path in paths:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError(f"{path} must hold one JSON object")
        entries.update(data)
    return entries


def _files_signature(paths: list[Path]) -> tuple:
    return tuple((str(path), path.stat().st_mtime_ns, path.stat().st_size) for path in paths)


_catalog_lock = threading.Lock()
_catalogs: dict[str, tuple[tuple, Catalog]] = {}
_checked: dict[str, float] = {}
# How long a dictionary is used before the files are looked at again.
RECHECK_SECONDS = 2.0


def catalog(language: str) -> Catalog | None:
    """The dictionary for ``language``; reread when a file changed on disk."""
    if language not in TRANSLATED_LANGUAGES:
        return None
    now = time.monotonic()
    cached = _catalogs.get(language)
    if cached and now - _checked.get(language, 0.0) < RECHECK_SECONDS:
        return cached[1]
    files = _dictionary_files(language)
    signature = _files_signature(files)
    _checked[language] = now
    with _catalog_lock:
        cached = _catalogs.get(language)
        if cached and cached[0] == signature:
            return cached[1]
        built = Catalog(_read_entries(files))
        _catalogs[language] = (signature, built)
        _translated_cache.clear()
        return built


def t(text: str, language: str | None, params: dict | None = None) -> str:
    """A server sentence in ``language`` (mails, notices); English without an entry."""
    current = catalog(language or DEFAULT_LANGUAGE)
    if current is None:
        return fill(text, params)
    return current.translate(text, params)


# ---------------------------------------------------------------------------
# Client bundle (/i18n/<lang>.<hash>.js)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ClientBundle:
    language: str
    digest: str
    body: bytes

    @property
    def url(self) -> str:
        return f"/i18n/{self.language}.{self.digest}.js"


_bundle_lock = threading.Lock()
_bundles: dict[str, tuple[tuple, ClientBundle]] = {}


def client_bundle(language: str) -> ClientBundle | None:
    """Dictionary (without the server-only ``page-*`` files) plus the engine."""
    if language not in TRANSLATED_LANGUAGES:
        return None
    files = [path for path in _dictionary_files(language) if not path.name.startswith("page-")]
    signature = _files_signature(files) + _files_signature([ENGINE_SCRIPT])
    with _bundle_lock:
        cached = _bundles.get(language)
        if cached and cached[0] == signature:
            return cached[1]
        current = Catalog(_read_entries(files))
        entries = dict(current.exact)
        entries.update({pattern.key: pattern.value for pattern in current.patterns})
        data = json.dumps({"lang": language, "entries": entries}, ensure_ascii=False, separators=(",", ":"))
        # A dictionary value never ends a script element early.
        data = data.replace("</", "<\\/")
        body = ("window.__consensI18n=" + data + ";\n" + ENGINE_SCRIPT.read_text(encoding="utf-8")).encode("utf-8")
        bundle = ClientBundle(language, hashlib.sha256(body).hexdigest()[:12], body)
        _bundles[language] = (signature, bundle)
        return bundle


# ---------------------------------------------------------------------------
# HTML
# ---------------------------------------------------------------------------

# Elements whose words belong to the sentence around them.
PHRASING_TAGS = frozenset({
    "a", "abbr", "b", "bdi", "bdo", "cite", "data", "del", "dfn", "em", "font", "i", "ins",
    "mark", "q", "s", "small", "span", "strong", "sub", "sup", "time", "u",
})
# Inline, but never changed: a marker <n/> keeps them as they are.
OPAQUE_INLINE_TAGS = frozenset({
    "br", "wbr", "img", "svg", "math", "code", "kbd", "samp", "var", "input",
    "picture", "video", "audio", "canvas", "iframe", "object", "output", "meter", "progress",
})
# Never read or changed, nor anything inside.
SKIP_TAGS = frozenset({"script", "style", "textarea", "pre", "svg", "math", "noscript", "code", "kbd", "samp", "var"})
RAW_TEXT_TAGS = frozenset({"script", "style", "textarea"})
# Never translated inside, but their placeholder, title and label are.
FIELD_TAGS = frozenset({"textarea"})
VOID_TAGS = frozenset({
    "area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param",
    "source", "track", "wbr",
})
TEXT_ATTRIBUTES = frozenset({
    "title", "aria-label", "aria-description", "aria-placeholder", "aria-roledescription",
    "aria-valuetext", "placeholder", "alt", "label", "data-tooltip", "data-short", "data-label",
    "data-ghost", "data-compact", "data-description", "data-type-loop", "data-type-text",
    "data-placeholder", "data-drop-label", "data-show", "data-hide",
})
META_TEXT = frozenset({
    "description", "og:title", "og:description", "og:image:alt", "twitter:title",
    "twitter:description", "twitter:image:alt", "apple-mobile-web-app-title",
})
_IMPLIED_END = {
    "li": {"li"}, "option": {"option"}, "dt": {"dt", "dd"}, "dd": {"dt", "dd"},
    "tr": {"tr", "td", "th"}, "td": {"td", "th"}, "th": {"td", "th"}, "p": {"p"},
}

_TOKEN = re.compile(
    r"<!--.*?-->"
    r"|<!\[CDATA\[.*?\]\]>"
    r"|<![^>]*>"
    r"|<\?[^>]*>"
    r"|</[A-Za-z][\w:-]*\s*>"
    r"|<[A-Za-z][\w:-]*(?:\"[^\"]*\"|'[^']*'|[^'\">])*>",
    re.S,
)
_TAG_NAME = re.compile(r"[A-Za-z][\w:-]*")
_ATTRIBUTE = re.compile(r"""(\s+)([^\s"'>/=]+)(?:(\s*=\s*)(?:"([^"]*)"|'([^']*)'|([^\s"'=<>`]+)))?""")


class _Raw:
    """Markup passed through as it is: a comment, a doctype, script text."""

    __slots__ = ("raw",)

    def __init__(self, raw: str):
        self.raw = raw


class _Text:
    __slots__ = ("raw", "out")

    def __init__(self, raw: str | None, out: str | None = None):
        self.raw = raw
        self.out = out

    @property
    def text(self) -> str:
        return html.unescape(self.raw) if self.raw is not None else html.unescape(self.out or "")


class _Element:
    __slots__ = ("tag", "start", "end", "children", "_attrs", "_kind")

    def __init__(self, tag: str, start: str):
        self.tag = tag
        self.start = start
        self.end: str | None = None
        self.children: list = []
        self._attrs: dict[str, str] | None = None
        self._kind: str | None = None

    def attrs(self) -> dict[str, str]:
        if self._attrs is None:
            found: dict[str, str] = {}
            head = _TAG_NAME.match(self.start, 1)
            for match in _ATTRIBUTE.finditer(self.start, head.end() if head else 1):
                name = match.group(2).lower()
                value = next((group for group in match.group(4, 5, 6) if group is not None), "")
                found.setdefault(name, html.unescape(value))
            self._attrs = found
        return self._attrs

    def set_attributes(self, changes: dict[str, str]) -> None:
        """Rewrite attribute values in the start tag, the rest byte for byte."""
        if not changes:
            return
        head = _TAG_NAME.match(self.start, 1)
        out: list[str] = [self.start[:head.end()]]
        position = head.end()
        seen: set[str] = set()
        for match in _ATTRIBUTE.finditer(self.start, position):
            name = match.group(2).lower()
            out.append(self.start[position:match.start()])
            if name in changes and name not in seen:
                out.append(f'{match.group(1)}{match.group(2)}="{html.escape(changes[name], quote=True)}"')
            else:
                out.append(match.group(0))
            seen.add(name)
            position = match.end()
        out.append(self.start[position:])
        self.start = "".join(out)
        self._attrs = None

    @property
    def skipped(self) -> bool:
        return self.tag in SKIP_TAGS or self.marked

    @property
    def marked(self) -> bool:
        """Marked by the page itself as words that stay as they are."""
        attrs = self.attrs()
        return (
            attrs.get("translate", "").lower() == "no"
            or "notranslate" in attrs.get("class", "").split()
            or "data-i18n-skip" in attrs
            or attrs.get("contenteditable", "false").lower() in {"", "true", "plaintext-only"}
        )

    def kind(self) -> str:
        """``phrasing`` (words of the sentence), ``opaque`` (a marker) or ``block``."""
        if self._kind is None:
            if self.tag in OPAQUE_INLINE_TAGS:
                kind = "opaque"
            elif self.tag in PHRASING_TAGS:
                if self.skipped:
                    kind = "opaque"
                elif any(isinstance(child, _Element) and child.kind() == "block" for child in self.children):
                    kind = "block"
                elif any(isinstance(child, _Raw) for child in self.children):
                    kind = "block"
                elif _has_words(self):
                    kind = "phrasing"
                else:
                    kind = "opaque"
            else:
                kind = "block"
            self._kind = kind
        return self._kind


def _has_words(node) -> bool:
    if isinstance(node, _Text):
        # A placeholder ({count}) is a number or a name, no words of its own.
        return has_letter(_PLACEHOLDER.sub("", node.text))
    if isinstance(node, _Element):
        return any(_has_words(child) for child in node.children if not (isinstance(child, _Element) and child.kind() == "opaque"))
    return False


def parse(source: str) -> _Element:
    root = _Element("#root", "")
    root.end = ""
    stack = [root]
    position = 0
    length = len(source)
    while position < length:
        match = _TOKEN.search(source, position)
        if match is None:
            break
        if match.start() > position:
            stack[-1].children.append(_Text(source[position:match.start()]))
        token = match.group(0)
        position = match.end()
        if token.startswith("</"):
            tag = token[2:-1].strip().lower()
            for index in range(len(stack) - 1, 0, -1):
                if stack[index].tag == tag:
                    stack[index].end = token
                    for open_element in stack[index + 1:]:
                        open_element.end = ""
                    del stack[index:]
                    break
            else:
                stack[-1].children.append(_Raw(token))
            continue
        if token.startswith("<!") or token.startswith("<?"):
            stack[-1].children.append(_Raw(token))
            continue
        tag = _TAG_NAME.match(token, 1).group(0).lower()
        closes = _IMPLIED_END.get(tag)
        if closes and len(stack) > 1 and stack[-1].tag in closes:
            stack.pop().end = ""
        element = _Element(tag, token)
        stack[-1].children.append(element)
        if tag in RAW_TEXT_TAGS:
            closing = re.compile(rf"</{tag}\s*>", re.I).search(source, position)
            end = closing.start() if closing else length
            if end > position:
                element.children.append(_Raw(source[position:end]))
            element.end = closing.group(0) if closing else ""
            position = closing.end() if closing else length
            continue
        if tag in VOID_TAGS or token.endswith("/>"):
            element.end = ""
            continue
        stack.append(element)
    if position < length:
        stack[-1].children.append(_Text(source[position:]))
    for open_element in stack[1:]:
        open_element.end = ""
    return root


def render(node) -> str:
    out: list[str] = []

    def walk(item) -> None:
        if isinstance(item, _Raw):
            out.append(item.raw)
        elif isinstance(item, _Text):
            out.append(item.out if item.out is not None else item.raw)
        else:
            out.append(item.start)
            for child in item.children:
                walk(child)
            out.append(item.end or "")

    walk(node)
    return "".join(out)


def run_key(nodes: list) -> tuple[str, list]:
    """The lookup key of a run of text and inline elements, and its elements."""
    parts: list[str] = []
    elements: list[_Element] = []

    def visit(node) -> None:
        if isinstance(node, _Text):
            parts.append(node.text)
        elif isinstance(node, _Element) and node.kind() == "phrasing":
            index = len(elements)
            elements.append(node)
            parts.append(f"<{index}>")
            for child in node.children:
                visit(child)
            parts.append(f"</{index}>")
        elif isinstance(node, _Element):
            index = len(elements)
            elements.append(node)
            parts.append(f"<{index}/>")

    for node in nodes:
        visit(node)
    return normalize("".join(parts)), elements


def _edge_space(text: str) -> tuple[str, str]:
    stripped = text.strip()
    if not stripped:
        return text, ""
    start = text.find(stripped[0])
    return text[:start], text[start + len(stripped):]


def _build(value: str, elements: list[_Element]) -> list:
    result: list = []
    stack: list[list] = [result]
    position = 0
    for match in _MARKER.finditer(value):
        if match.start() > position:
            stack[-1].append(_Text(None, html.escape(value[position:match.start()], quote=False)))
        position = match.end()
        if match.group(1) is not None:
            stack.append([])
        elif match.group(2) is not None:
            children = stack.pop()
            element = elements[int(match.group(2))]
            element.children = children
            stack[-1].append(element)
        else:
            stack[-1].append(elements[int(match.group(3))])
    if position < len(value):
        stack[-1].append(_Text(None, html.escape(value[position:], quote=False)))
    return result


def _words(node) -> bool:
    if isinstance(node, _Text):
        return bool(node.text.strip())
    return isinstance(node, _Element) and node.kind() == "phrasing"


def _trim(nodes: list) -> tuple[int, int]:
    """The run without space, icons and breaks at its ends."""
    start, end = 0, len(nodes)
    while start < end and not _words(nodes[start]):
        start += 1
    while end > start and not _words(nodes[end - 1]):
        end -= 1
    return start, end


class _Translator:
    def __init__(self, current: Catalog, misses: list[str] | None, *, link_prefix: str = "", canonical: str = ""):
        self.catalog = current
        self.misses = misses
        self.link_prefix = link_prefix
        self.canonical = canonical
        # data-i18n-context of the nearest element that has one: "ctx|key"
        # entries win inside it ("agent freedom|Free" is not the plan Free).
        self.context = ""

    def find(self, key: str) -> str | None:
        if self.context:
            found = self.catalog.exact.get(f"{self.context}|{key}")
            if found is not None:
                return found
        return self.catalog.lookup(key)

    # -- attributes ----------------------------------------------------
    def attributes(self, element: _Element) -> None:
        attrs = element.attrs()
        changes: dict[str, str] = {}
        for name, value in attrs.items():
            if name in TEXT_ATTRIBUTES and value.strip():
                translated = self.lookup(value)
                if translated is not None:
                    changes[name] = translated
        if element.tag == "input" and attrs.get("type", "").lower() in {"submit", "button", "reset"} and attrs.get("value"):
            translated = self.lookup(attrs["value"])
            if translated is not None:
                changes["value"] = translated
        if element.tag == "meta" and attrs.get("content"):
            name = (attrs.get("name") or attrs.get("property") or "").lower()
            if name in META_TEXT:
                translated = self.lookup(attrs["content"])
                if translated is not None:
                    changes["content"] = translated
        if self.link_prefix and element.tag == "a":
            href = attrs.get("href", "")
            if href.startswith("/") and not href.startswith("//") and re.split(r"[?#]", href, maxsplit=1)[0] in LOCALIZED_PATHS:
                changes["href"] = self.link_prefix + href
        if self.canonical and element.tag == "link" and attrs.get("rel", "").lower() == "canonical":
            changes["href"] = self.canonical
        if self.canonical and element.tag == "meta" and attrs.get("property", "").lower() == "og:url":
            changes["content"] = self.canonical
        element.set_attributes(changes)

    def lookup(self, text: str) -> str | None:
        key = normalize(text)
        if not key or not has_letter(key):
            return None
        found = self.find(key)
        if found is None and self.misses is not None and key not in self.catalog.values:
            self.misses.append(key)
        return found

    # -- text ----------------------------------------------------------
    def container(self, element: _Element) -> None:
        if element.tag == "script" and element.attrs().get("type", "").lower() == "application/ld+json":
            self.structured_data(element)
            return
        if element.skipped:
            # A field's text is the reader's; its placeholder and label are ours.
            if element.tag in FIELD_TAGS and not element.marked:
                self.attributes(element)
            return
        outer_context = self.context
        self.context = element.attrs().get("data-i18n-context", outer_context) if element.tag != "#root" else outer_context
        try:
            self._container(element)
        finally:
            self.context = outer_context

    def _container(self, element: _Element) -> None:
        if element.tag != "#root":
            self.attributes(element)
        children = element.children
        result: list = []
        run: list = []
        for child in children + [None]:
            boundary = child is None or isinstance(child, _Raw) or (isinstance(child, _Element) and child.kind() == "block")
            if not boundary:
                run.append(child)
                continue
            if run:
                result.extend(self.run(run))
                run = []
            if child is not None:
                if isinstance(child, _Element):
                    self.container(child)
                result.append(child)
        element.children = result

    def inline_attributes(self, nodes: list) -> None:
        for node in nodes:
            if isinstance(node, _Element) and not node.skipped:
                self.attributes(node)
                if node.kind() == "phrasing":
                    self.inline_attributes(node.children)

    def run(self, nodes: list) -> list:
        self.inline_attributes(nodes)
        start, end = _trim(nodes)
        if start == end:
            return nodes
        core = nodes[start:end]
        if len(core) == 1 and isinstance(core[0], _Element):
            # One element around the whole run: its words are the run.
            core[0].children = self.run(core[0].children)
            return nodes
        key, elements = run_key(core)
        if not has_letter(key):
            return nodes
        found = self.find(key)
        if found is not None:
            first, last = core[0], core[-1]
            lead = _edge_space(first.text)[0] if isinstance(first, _Text) else ""
            trail = _edge_space(last.text)[1] if isinstance(last, _Text) else ""
            built = _build(found, elements)
            if lead:
                built.insert(0, _Text(None, lead))
            if trail:
                built.append(_Text(None, trail))
            return nodes[:start] + built + nodes[end:]
        if key in self.catalog.values:
            return nodes
        # No whole entry: every piece on its own. A miss is reported as the
        # whole run, the unit a translation should have.
        outer, self.misses = self.misses, ([] if self.misses is not None else None)
        try:
            for node in core:
                if isinstance(node, _Text):
                    self.text(node)
                elif isinstance(node, _Element) and node.kind() == "phrasing":
                    node.children = self.run(node.children)
        finally:
            missed, self.misses = self.misses, outer
        if missed and outer is not None:
            outer.append(key)
        return nodes

    def text(self, node: _Text) -> None:
        source = node.text
        key = normalize(source)
        if not key or not has_letter(key):
            return
        found = self.find(key)
        if found is None:
            if self.misses is not None and key not in self.catalog.values:
                self.misses.append(key)
            return
        if _MARKER.search(found):
            return
        lead, trail = _edge_space(source)
        node.out = lead + html.escape(found, quote=False) + trail

    def structured_data(self, element: _Element) -> None:
        raw = "".join(child.raw for child in element.children if isinstance(child, _Raw))
        try:
            data = json.loads(raw)
        except ValueError:
            return

        def walk(value):
            if isinstance(value, str):
                found = self.catalog.lookup(normalize(value)) if has_letter(value) else None
                return found if found is not None else value
            if isinstance(value, list):
                return [walk(item) for item in value]
            if isinstance(value, dict):
                return {key: (item if key.startswith("@") or key in {"url", "image", "logo", "sameAs", "inLanguage"} else walk(item)) for key, item in value.items()}
            return value

        translated = walk(data)
        if translated == data:
            return
        lead, trail = _edge_space(raw)
        text = json.dumps(translated, ensure_ascii=False, indent=2).replace("</", "<\\/")
        element.children = [_Raw(lead + text + trail)]


def _find(node: _Element, predicate: Callable[[_Element], bool]) -> Iterable[_Element]:
    for child in node.children:
        if isinstance(child, _Element):
            if predicate(child):
                yield child
            if child.tag not in RAW_TEXT_TAGS:
                yield from _find(child, predicate)


_translated_cache: "OrderedDict[tuple, str]" = OrderedDict()
_translated_lock = threading.Lock()
TRANSLATED_CACHE_SIZE = 48


def translate_html(source: str, language: str, *, link_prefix: str = "", canonical: str = "",
                   misses: list[str] | None = None) -> str:
    """The page in ``language``: words, readable attributes, ``lang``, structured data.

    ``link_prefix`` ("/de") points links to localized pages at their German
    address; ``canonical`` replaces the canonical link and ``og:url``. ``misses`` collects the English segments without an entry (tests
    and ``scripts/i18n.py``); a call that collects them is never cached.
    """
    current = catalog(language)
    if current is None:
        return source
    cache_key = (hashlib.sha256(source.encode("utf-8")).digest(), language, link_prefix, canonical, id(current))
    if misses is None:
        with _translated_lock:
            cached = _translated_cache.get(cache_key)
            if cached is not None:
                _translated_cache.move_to_end(cache_key)
                return cached
    root = parse(source)
    for element in _find(root, lambda item: item.tag == "html"):
        element.set_attributes({"lang": language})
        break
    for element in _find(root, lambda item: item.tag == "meta" and item.attrs().get("property", "").lower() == "og:locale"):
        element.set_attributes({"content": OG_LOCALE.get(language, language)})
    _Translator(current, misses, link_prefix=link_prefix, canonical=canonical).container(root)
    result = render(root)
    if misses is None:
        with _translated_lock:
            _translated_cache[cache_key] = result
            while len(_translated_cache) > TRANSLATED_CACHE_SIZE:
                _translated_cache.popitem(last=False)
    return result


def html_segments(source: str) -> list[str]:
    """Every key a page would look up, in document order (``scripts/i18n.py``).

    The keys of whole runs and of readable attributes; a run's pieces are only
    needed when nobody translates the whole run, so they are not listed.
    """
    found: list[str] = []

    class Collector(_Translator):
        def lookup(self, text: str) -> str | None:  # attributes
            key = normalize(text)
            if key and has_letter(key):
                found.append(key)
            return None

        def run(self, nodes: list) -> list:
            self.inline_attributes(nodes)
            start, end = _trim(nodes)
            if start == end:
                return nodes
            core = nodes[start:end]
            if len(core) == 1 and isinstance(core[0], _Element):
                self.run(core[0].children)
                return nodes
            key, _ = run_key(core)
            if has_letter(key):
                found.append(key)
            return nodes

        def structured_data(self, element: _Element) -> None:
            raw = "".join(child.raw for child in element.children if isinstance(child, _Raw))
            try:
                data = json.loads(raw)
            except ValueError:
                return

            def walk(value, key=""):
                if isinstance(value, str):
                    if has_letter(value) and not key.startswith("@") and key not in {"url", "image", "logo", "sameAs", "inLanguage"} and " " in value.strip():
                        found.append(normalize(value))
                elif isinstance(value, list):
                    for item in value:
                        walk(item, key)
                elif isinstance(value, dict):
                    for name, item in value.items():
                        walk(item, name)

            walk(data)

    Collector(Catalog({}), None).container(parse(source))
    return found


# ---------------------------------------------------------------------------
# Language of a request
# ---------------------------------------------------------------------------

def preferred_language(accept_language: str | None) -> str:
    """The first language the browser asks for that we have, else English."""
    best: tuple[float, int, str] | None = None
    for index, part in enumerate((accept_language or "").split(",")):
        piece = part.strip()
        if not piece:
            continue
        tag, _, params = piece.partition(";")
        quality = 1.0
        for param in params.split(";"):
            name, _, value = param.strip().partition("=")
            if name == "q":
                try:
                    quality = float(value)
                except ValueError:
                    quality = 0.0
        primary = tag.strip().lower().split("-")[0]
        if primary not in LANGUAGES or quality <= 0:
            continue
        candidate = (-quality, index, primary)
        if best is None or candidate < best:
            best = candidate
    return best[2] if best else DEFAULT_LANGUAGE


def chosen_language(cookie_value: str | None) -> str | None:
    value = (cookie_value or "").strip().lower()
    return value if value in LANGUAGES else None


def localized_path(path: str, language: str) -> str:
    """The address of a localized page in ``language`` (``/about`` → ``/de/about``)."""
    prefix = LOCALE_PREFIX.get(language, "")
    if not prefix:
        return path
    return prefix + ("/" if path == "/" else path)


def split_locale_prefix(path: str) -> tuple[str | None, str]:
    """``/de/about`` → ("de", "/about"); anything else → (None, path)."""
    for language, prefix in LOCALE_PREFIX.items():
        if path == prefix or path == prefix + "/":
            return language, "/"
        if path.startswith(prefix + "/"):
            return language, path[len(prefix):]
    return None, path


def alternate_links(path: str, site_url: str) -> str:
    """hreflang alternates of a localized page, for its <head>."""
    lines = [f'<link rel="alternate" hreflang="en" href="{site_url}{path}">']
    for language in TRANSLATED_LANGUAGES:
        lines.append(f'<link rel="alternate" hreflang="{language}" href="{site_url}{localized_path(path, language)}">')
    lines.append(f'<link rel="alternate" hreflang="x-default" href="{site_url}{path}">')
    return "\n  ".join(lines)


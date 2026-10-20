"""What the app says: every user-facing string of /app, for the copy tests.

``tests/test_ui_copy.py`` checks one name for the thing (a chat), one style
(sentence case, "Log in", "email", typographic ’ and …) and no internal names
in what a reader can see (Apple-Audit H3, H5, H10). This module finds those
strings:

- ``template_texts()``: text and the readable attributes (title, aria-label,
  placeholder, data-tooltip, alt, data-short, data-description) of
  ``templates/index.html``, without comments, Jinja, scripts and styles.
- ``script_texts()``: the string literals and template-literal chunks of the
  /app scripts that read as prose, without console output, selectors, event
  names and other code strings.

A small JavaScript tokenizer (strings, template literals with nested
``${}``, comments, regular expressions) is enough for the house style of
``static/js``; it fails loudly instead of guessing when it gets lost.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

# Scripts whose words a reader of /app can see. The admin, the public pages
# and their own scripts have their own audience and tests.
SKIP_SCRIPTS = {
    "static/js/admin.js", "static/js/admin-benchmark.js", "static/js/admin-prompt-config.js",
    "static/js/error-reporter.js",
}


@dataclass(frozen=True)
class Text:
    source: str
    line: int
    text: str
    context: str = ""

    def __str__(self) -> str:  # pragma: no cover - failure output only
        return f"{self.source}:{self.line}: {self.text!r}"


def app_scripts() -> list[str]:
    config = json.loads((ROOT / "static/js/bundles.json").read_text(encoding="utf-8"))
    files: list[str] = []
    for group in config["groups"]:
        if group.get("kind") == "module":
            files.append(group["entry"])
            continue
        for entry in group["files"]:
            files.append(entry if isinstance(entry, str) else entry["file"])
    return [file for file in files if file not in SKIP_SCRIPTS]


# ---------------------------------------------------------------------------
# JavaScript
# ---------------------------------------------------------------------------

KEYWORDS_BEFORE_REGEX = {
    "return", "typeof", "instanceof", "in", "of", "new", "delete", "void", "throw",
    "case", "do", "else", "yield", "await",
}


@dataclass
class _Token:
    kind: str  # "string", "template", "name", "punct", "number", "regex"
    value: str
    line: int


def tokenize(source: str) -> list[_Token]:
    tokens: list[_Token] = []
    index = 0
    line = 1
    length = len(source)
    # Each open template literal: the brace depth at which its ${ began.
    templates: list[int] = []
    depth = 0

    def last_significant() -> _Token | None:
        return tokens[-1] if tokens else None

    def regex_allowed() -> bool:
        previous = last_significant()
        if previous is None:
            return True
        if previous.kind in {"string", "template", "number", "regex"}:
            return False
        if previous.kind == "name":
            return previous.value in KEYWORDS_BEFORE_REGEX
        return previous.value not in {")", "]", "}"}

    def read_template_chunk(start: int) -> tuple[str, int, bool]:
        """From after ` or }, to the closing ` (False) or the next ${ (True)."""
        nonlocal line
        position = start
        chunk = []
        while position < length:
            char = source[position]
            if char == "\\":
                chunk.append(source[position:position + 2])
                position += 2
                continue
            if char == "`":
                return "".join(chunk), position + 1, False
            if char == "$" and source[position + 1:position + 2] == "{":
                return "".join(chunk), position + 2, True
            if char == "\n":
                line += 1
            chunk.append(char)
            position += 1
        raise ValueError("unterminated template literal")

    while index < length:
        char = source[index]
        if char == "\n":
            line += 1
            index += 1
            continue
        if char in " \t\r\f\v﻿":
            index += 1
            continue
        if source.startswith("//", index):
            end = source.find("\n", index)
            index = length if end == -1 else end
            continue
        if source.startswith("/*", index):
            end = source.find("*/", index + 2)
            if end == -1:
                raise ValueError(f"unterminated comment at line {line}")
            line += source.count("\n", index, end)
            index = end + 2
            continue
        if char in "'\"":
            position = index + 1
            value = []
            while position < length and source[position] != char:
                if source[position] == "\\":
                    value.append(source[position:position + 2])
                    position += 2
                    continue
                if source[position] == "\n":
                    raise ValueError(f"newline in string at line {line}")
                value.append(source[position])
                position += 1
            tokens.append(_Token("string", "".join(value), line))
            index = position + 1
            continue
        if char == "`":
            start_line = line
            chunk, index, opened = read_template_chunk(index + 1)
            tokens.append(_Token("template", chunk, start_line))
            if opened:
                templates.append(depth)
                depth += 1
            continue
        if char == "}" and templates and depth - 1 == templates[-1]:
            depth -= 1
            templates.pop()
            start_line = line
            chunk, index, opened = read_template_chunk(index + 1)
            tokens.append(_Token("template", chunk, start_line))
            if opened:
                templates.append(depth)
                depth += 1
            continue
        if char == "/" and regex_allowed():
            position = index + 1
            in_class = False
            while position < length:
                current = source[position]
                if current == "\\":
                    position += 2
                    continue
                if current == "\n":
                    raise ValueError(f"newline in regex at line {line}")
                if current == "[":
                    in_class = True
                elif current == "]":
                    in_class = False
                elif current == "/" and not in_class:
                    break
                position += 1
            position += 1
            while position < length and (source[position].isalnum()):
                position += 1
            tokens.append(_Token("regex", source[index:position], line))
            index = position
            continue
        match = re.compile(r"[A-Za-z_$][\w$]*").match(source, index)
        if match:
            tokens.append(_Token("name", match.group(0), line))
            index = match.end()
            continue
        match = re.compile(r"\d[\w.]*").match(source, index)
        if match:
            tokens.append(_Token("number", match.group(0), line))
            index = match.end()
            continue
        if char in "({[":
            depth += 1
        elif char in ")}]":
            depth -= 1
        # Multi-character operators are irrelevant here; one char at a time.
        tokens.append(_Token("punct", char, line))
        index += 1
    if templates:
        raise ValueError("unterminated template expression")
    return tokens


# Calls whose string arguments are code or logs, never words on the page.
CODE_CALLS = re.compile(
    r"(^|\.)(log|warn|error|info|debug|trace|querySelector|querySelectorAll|getElementById|closest|matches|"
    r"addEventListener|removeEventListener|dispatchEvent|CustomEvent|Event|createElement|createElementNS|"
    r"getAttribute|removeAttribute|hasAttribute|toggleAttribute|add|remove|toggle|contains|replace|"
    r"trackAppEvent|trackUmamiEvent|trackAsk|track|fetch|RegExp|matchMedia|getItem|setItem|removeItem|"
    r"getPropertyValue|setProperty|removeProperty|postMessage|open|startsWith|endsWith|includes|indexOf|"
    r"split|join|has|get|set|delete|test|exec|match|replaceAll|padStart|key|reportCriticalError|"
    r"beginAction|withRequestDeadline|streamSSERequest|api|request|post|onChange|on|off|define|require|"
    r"animate|scrollIntoView|focus|setStatus|registerPlugin)$"
)


def _callee(tokens: list[_Token], open_index: int) -> str:
    """The dotted name before the ( at ``open_index``."""
    parts: list[str] = []
    index = open_index - 1
    while index >= 0:
        token = tokens[index]
        if token.kind == "name":
            parts.append(token.value)
            index -= 1
            if index >= 0 and tokens[index].kind == "punct" and tokens[index].value in ".?":
                while index >= 0 and tokens[index].kind == "punct" and tokens[index].value in ".?":
                    index -= 1
                continue
            break
        break
    return ".".join(reversed(parts))


PROSE = re.compile(r"[A-Za-z’']{2,}[,;:]?\s+[A-Za-z’'(]")


def _is_prose(text: str) -> bool:
    plain = re.sub(r"\{\}|\\n|\\u[0-9a-fA-F]{4}|\\.", " ", text).strip()
    if not PROSE.search(plain):
        return False
    # Selectors, class lists, CSS values, URLs and code snippets.
    if re.search(r"(^|\s)[.#][a-z][\w-]*|\[data-|:not\(|=>|\bvar\(--|https?://|^[a-z][\w-]*(\s+[a-z][\w-]*)*$", plain):
        return False
    return True


def script_texts(files: list[str] | None = None) -> list[Text]:
    found: list[Text] = []
    for relative in files or app_scripts():
        source = (ROOT / relative).read_text(encoding="utf-8")
        tokens = tokenize(source)
        calls: list[str] = []
        for index, token in enumerate(tokens):
            if token.kind == "punct" and token.value in "([{":
                calls.append(_callee(tokens, index) if token.value == "(" else "")
                continue
            if token.kind == "punct" and token.value in ")]}":
                if calls:
                    calls.pop()
                continue
            if token.kind not in {"string", "template"}:
                continue
            context = next((call for call in reversed(calls) if call), "")
            if context and CODE_CALLS.search(context):
                continue
            # A property key ({ "Content-Type": … }) or a comparison is code.
            following = tokens[index + 1] if index + 1 < len(tokens) else None
            previous = tokens[index - 1] if index else None
            if (following is not None and following.kind == "punct" and following.value == ":" and token.kind == "string"
                    and previous is not None and previous.kind == "punct" and previous.value in "{,"):
                continue
            before = [item.value for item in tokens[max(0, index - 2):index] if item.kind == "punct"]
            after = [item.value for item in tokens[index + 1:index + 3] if item.kind == "punct"]
            if before[-2:] == ["=", "="] or after[:2] == ["=", "="] or before[-2:] == ["!", "="]:
                continue
            text = token.value
            if re.search(r"<[a-z][\w-]*[\s>/]", text):
                # Markup built in a string: its words and readable attributes.
                parser = _TemplateText()
                parser.feed(text.replace("\\n", " "))
                for _line, words, tag in parser.found:
                    if tag.startswith("@") or _is_prose(words):
                        found.append(Text(relative, token.line, words, f"{context}<{tag}>"))
                continue
            if _is_prose(text):
                found.append(Text(relative, token.line, text, context))
    return found


# ---------------------------------------------------------------------------
# The template
# ---------------------------------------------------------------------------

READABLE_ATTRIBUTES = {"title", "aria-label", "placeholder", "data-tooltip", "alt", "data-short", "data-description"}


class _TemplateText(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.found: list[tuple[int, str, str]] = []
        self.stack: list[str] = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "template"}:
            self.skip += 1
        if tag not in {"br", "img", "input", "meta", "link", "hr", "source", "path", "circle", "rect", "line", "polyline", "use"}:
            self.stack.append(tag)
        line = self.getpos()[0]
        for name, value in attrs:
            if name in READABLE_ATTRIBUTES and value and value.strip():
                self.found.append((line, value.strip(), f"@{name}"))

    def handle_startendtag(self, tag, attrs):
        line = self.getpos()[0]
        for name, value in attrs:
            if name in READABLE_ATTRIBUTES and value and value.strip():
                self.found.append((line, value.strip(), f"@{name}"))

    def handle_endtag(self, tag):
        if tag in {"script", "style", "template"} and self.skip:
            self.skip -= 1
        if tag in self.stack:
            while self.stack and self.stack.pop() != tag:
                pass

    def handle_data(self, data):
        if self.skip:
            return
        text = " ".join(data.split())
        if text:
            self.found.append((self.getpos()[0], text, self.stack[-1] if self.stack else ""))


def _strip_template(markup: str) -> str:
    def blank(match: re.Match) -> str:
        return "\n" * match.group(0).count("\n")

    for pattern in (r"\{#[\s\S]*?#\}", r"\{%[\s\S]*?%\}", r"\{\{[\s\S]*?\}\}", r"<!--[\s\S]*?-->"):
        markup = re.sub(pattern, blank, markup)
    return markup


def template_texts(relative: str = "templates/index.html") -> list[Text]:
    parser = _TemplateText()
    parser.feed(_strip_template((ROOT / relative).read_text(encoding="utf-8")))
    return [Text(relative, line, text, tag) for line, text, tag in parser.found]


def all_texts() -> list[Text]:
    return template_texts() + script_texts()

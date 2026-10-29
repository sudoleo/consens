"""Find every English segment the site can show, and the ones without German.

The dictionary (``app/i18n/<lang>/*.json``, rules in ``app/core/i18n.py``) is
keyed by the English a reader sees. This tool lists those keys from the
sources, so a new label cannot go out untranslated:

- templates: each run and readable attribute of every page template (Jinja
  expressions become ``{name}`` placeholders, Jinja tags split runs);
- scripts: string and template literals that read as interface text,
  markup built in strings, and ``"…" + value + "…"`` chains as patterns
  (``App.t("…", params, "watch schedule")`` under its context);
- server sentences: ``HTTPException`` details and ``{"error": …}`` bodies,
  and the sentences of exceptions a service raises for a card
  (``SERVER_RAISED``).

    python scripts/i18n.py missing            # keys without an entry, by file
    python scripts/i18n.py missing --json out.json
    python scripts/i18n.py check              # exit 1 when anything is missing

``tests/test_i18n.py`` runs the same check, and renders the localized pages
in German to catch what only exists at runtime.
"""

from __future__ import annotations

import argparse
import ast
import html
import itertools
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core import i18n  # noqa: E402


# Pages and scripts a German reader never sees.
SKIP_TEMPLATES = {"templates/admin.html", "templates/admin_benchmark.html", "templates/partials/admin_prompt_config.html"}
SKIP_SCRIPTS = {
    "static/js/admin.js", "static/js/admin-api.js", "static/js/admin-benchmark.js", "static/js/admin-config.js",
    "static/js/admin-prompt-config.js", "static/js/admin-agent-budget.js", "static/js/error-reporter.js",
    "static/js/i18n.js",
}


@dataclass(frozen=True)
class Found:
    key: str
    source: str
    line: int


# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------

_JINJA = re.compile(r"\{#.*?#\}|\{%-?.*?-?%\}|\{\{-?.*?-?\}\}", re.S)
_EXPRESSION_NAME = re.compile(r"[A-Za-z_]\w*")
_JINJA_KEYWORDS = {"not", "and", "or", "if", "else", "in", "is", "none", "true", "false", "loop"}


_STRING_LITERAL = re.compile(r"""(['"])([^'"]*)\1""")


def _placeholder(expression: str, index: int, literals: list[str] | None = None) -> str:
    body = expression.strip("{}-").strip()
    # A literal string ({{ "Text" }}): its words are the text.
    whole = re.fullmatch(r"""(['"])([^'"]*)\1""", body)
    if whole:
        return whole.group(2)
    # Words chosen in the expression ({{ "Logo" if … else "Image" }}) fill a
    # placeholder and are entries of their own.
    if literals is not None:
        literals.extend(match.group(2) for match in _STRING_LITERAL.finditer(body))
    head = body.split("|", 1)[0].strip()
    names = [name for name in _EXPRESSION_NAME.findall(head) if name.lower() not in _JINJA_KEYWORDS]
    simple = re.fullmatch(r"[A-Za-z_][\w.]*", head)
    if simple and names:
        return "{" + names[-1] + "}"
    # answer_model or "An AI model", "%.0f" | format(pulse.rate): named after
    # the first variable outside a string, so the key does not change when
    # another expression is added to the page.
    plain = _STRING_LITERAL.sub(" ", body)
    names = [name for name in _EXPRESSION_NAME.findall(plain)
             if name.lower() not in _JINJA_KEYWORDS and name not in {"format", "round", "int", "float", "length", "e", "safe"}]
    if names:
        return "{" + names[0] + "}"
    return "{" + str(index) + "}"


# A tag inside an attribute's value ("{% if a %}Answer check{% else %}…")
# leaves this mark in its key: the page translates each value it renders as
# a whole, and a key glued from both branches stands for none of them
# (composed_gaps; docs/a11y-audit-2026-10-23.md, L2).
TAG_IN_VALUE = "{%}"


def jinja_to_html(source: str, literals: list[str] | None = None) -> str:
    """Template source as HTML a parser can read: expressions as placeholders.

    Tags ({% %}) outside markup become comments, which split a run the way
    the branches they choose between would; inside a start tag they vanish,
    and inside a quoted value they leave ``TAG_IN_VALUE``.
    ``literals`` collects the strings inside expressions.
    """
    out: list[str] = []
    position = 0
    in_tag = False
    quote = ""
    counter = 0
    for match in _JINJA.finditer(source):
        chunk = source[position:match.start()]
        for char in chunk:
            if in_tag:
                if quote:
                    if char == quote:
                        quote = ""
                elif char in "\"'":
                    quote = char
                elif char == ">":
                    in_tag = False
            elif char == "<":
                in_tag = True
        out.append(chunk)
        token = match.group(0)
        position = match.end()
        if token.startswith("{#"):
            continue
        if token.startswith("{%"):
            if not in_tag:
                out.append("<!--j-->")
            elif quote:
                out.append(TAG_IN_VALUE)
            continue
        counter += 1
        out.append(_placeholder(token, counter, literals))
    out.append(source[position:])
    text = "".join(out)
    # A lone "<" that started an "in_tag" inside text is harmless: the HTML
    # parser treats it as text.
    return text


def _letters_outside_placeholders(key: str) -> bool:
    return i18n.has_letter(re.sub(r"\{[^{}]*\}|<\d+/?>|</\d+>", " ", key))


# Text a template sets for a partial: {% set public_footer_note = "…" %},
# {{ value | default('…') }}.
_JINJA_TEXT = re.compile(r"""\{%-?\s*set\s+\w+\s*=\s*(['"])([^'"]*)\1\s*-?%\}|default\(\s*(['"])([^'"]*)\3\s*\)""")


def template_keys(relative: str) -> list[Found]:
    source = (ROOT / relative).read_text(encoding="utf-8")
    literals: list[str] = []
    markup = jinja_to_html(source, literals)
    keys = [_unique_placeholders(key) for key in i18n.html_segments(markup)]
    # A page's own inline script writes words too (the questions filter).
    for script in re.finditer(r"<script(?![^>]*\bsrc=)(?![^>]*ld\+json)[^>]*>(.*?)</script>", markup, re.S | re.I):
        try:
            keys.extend(item.key for item in script_keys(relative, script.group(1)))
        except (ValueError, IndexError):
            continue
    literals.extend(match.group(2) or match.group(4) or "" for match in _JINJA_TEXT.finditer(source))
    for literal in literals:
        if looks_like_text(html.unescape(literal)):
            keys.extend(i18n.html_segments(f"<p>{literal}</p>"))
    found: list[Found] = []
    for key in keys:
        if _letters_outside_placeholders(key):
            line = _line_of(source, key)
            found.append(Found(key, relative, line))
    return found


def _line_of(source: str, key: str) -> int:
    probe = re.split(r"\{[^{}]*\}|<\d+/?>|</\d+>", key)
    probe = max(probe, key=len).strip()
    index = source.find(probe[:40]) if probe else -1
    return source.count("\n", 0, index) + 1 if index >= 0 else 0


# ---------------------------------------------------------------------------
# Scripts
# ---------------------------------------------------------------------------

KEYWORDS_BEFORE_REGEX = {
    "return", "typeof", "instanceof", "in", "of", "new", "delete", "void", "throw",
    "case", "do", "else", "yield", "await",
}


@dataclass
class Token:
    kind: str  # string, template, name, number, punct, regex
    value: str
    line: int
    parts: tuple = ()  # template: (chunks, expressions)


def _scan_expression(source: str, index: int) -> int:
    """From after ``${`` to its closing ``}`` (returns the index of it)."""
    depth = 0
    length = len(source)
    while index < length:
        char = source[index]
        if char in "'\"":
            index = _skip_string(source, index)
            continue
        if char == "`":
            index = _skip_template(source, index)
            continue
        if source.startswith("//", index):
            end = source.find("\n", index)
            index = length if end == -1 else end
            continue
        if source.startswith("/*", index):
            end = source.find("*/", index + 2)
            index = length if end == -1 else end + 2
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            if depth == 0:
                return index
            depth -= 1
        index += 1
    raise ValueError("unterminated template expression")


def _skip_string(source: str, index: int) -> int:
    quote = source[index]
    index += 1
    while index < len(source) and source[index] != quote:
        index += 2 if source[index] == "\\" else 1
    return index + 1


def _skip_template(source: str, index: int) -> int:
    index += 1
    while index < len(source):
        char = source[index]
        if char == "\\":
            index += 2
            continue
        if char == "`":
            return index + 1
        if source.startswith("${", index):
            index = _scan_expression(source, index + 2) + 1
            continue
        index += 1
    raise ValueError("unterminated template literal")


def tokenize(source: str) -> list[Token]:
    tokens: list[Token] = []
    index = 0
    line = 1
    length = len(source)

    def regex_allowed() -> bool:
        previous = tokens[-1] if tokens else None
        if previous is None:
            return True
        if previous.kind in {"string", "template", "number", "regex"}:
            return False
        if previous.kind == "name":
            return previous.value in KEYWORDS_BEFORE_REGEX
        return previous.value not in {")", "]", "}"}

    while index < length:
        char = source[index]
        if char == "\n":
            line += 1
            index += 1
            continue
        if char in " \t\r\f\v\ufeff":
            index += 1
            continue
        if source.startswith("//", index):
            end = source.find("\n", index)
            index = length if end == -1 else end
            continue
        if source.startswith("/*", index):
            end = source.find("*/", index + 2)
            line += source.count("\n", index, end)
            index = end + 2
            continue
        if char in "'\"":
            end = _skip_string(source, index)
            tokens.append(Token("string", _unescape(source[index + 1:end - 1]), line))
            index = end
            continue
        if char == "`":
            start_line = line
            chunks: list[str] = []
            expressions: list[str] = []
            position = index + 1
            current: list[str] = []
            while True:
                current_char = source[position]
                if current_char == "\\":
                    current.append(source[position:position + 2])
                    position += 2
                    continue
                if current_char == "`":
                    chunks.append("".join(current))
                    position += 1
                    break
                if source.startswith("${", position):
                    chunks.append("".join(current))
                    current = []
                    end = _scan_expression(source, position + 2)
                    expressions.append(source[position + 2:end])
                    position = end + 1
                    continue
                current.append(current_char)
                position += 1
            line += source.count("\n", index, position)
            tokens.append(Token("template", "", start_line, (tuple(_unescape(chunk) for chunk in chunks), tuple(expressions))))
            index = position
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
                    break
                if current == "[":
                    in_class = True
                elif current == "]":
                    in_class = False
                elif current == "/" and not in_class:
                    break
                position += 1
            position += 1
            while position < length and source[position].isalnum():
                position += 1
            tokens.append(Token("regex", source[index:position], line))
            index = position
            continue
        match = re.compile(r"[A-Za-z_$][\w$]*").match(source, index)
        if match:
            tokens.append(Token("name", match.group(0), line))
            index = match.end()
            continue
        match = re.compile(r"\d[\w.]*").match(source, index)
        if match:
            tokens.append(Token("number", match.group(0), line))
            index = match.end()
            continue
        tokens.append(Token("punct", char, line))
        index += 1
    return tokens


def _unescape(text: str) -> str:
    def replace(match: re.Match) -> str:
        escape = match.group(0)
        if escape.startswith("\\u{"):
            return chr(int(escape[3:-1], 16))
        if escape.startswith("\\u"):
            return chr(int(escape[2:], 16))
        if escape.startswith("\\x"):
            return chr(int(escape[2:], 16))
        return {"\\n": "\n", "\\t": "\t", "\\r": "\r", "\\b": "", "\\f": "", "\\v": "", "\\0": ""}.get(escape, escape[1:])

    return re.sub(r"\\u\{[0-9a-fA-F]+\}|\\u[0-9a-fA-F]{4}|\\x[0-9a-fA-F]{2}|\\.", replace, text, flags=re.S)


CODE_CALLS = re.compile(
    r"(^|\.)(log|warn|error|info|debug|trace|querySelector|querySelectorAll|getElementById|closest|matches|"
    r"addEventListener|removeEventListener|dispatchEvent|CustomEvent|Event|createElement|createElementNS|"
    r"getAttribute|removeAttribute|hasAttribute|toggleAttribute|add|remove|toggle|contains|replace|"
    r"trackAppEvent|trackUmamiEvent|trackAsk|track|fetch|RegExp|matchMedia|getItem|setItem|removeItem|"
    r"getPropertyValue|setProperty|removeProperty|postMessage|startsWith|endsWith|includes|indexOf|"
    r"split|join|has|get|delete|test|exec|match|replaceAll|padStart|key|reportCriticalError|"
    r"beginAction|withRequestDeadline|streamSSERequest|api|request|post|on|off|define|require|"
    r"animate|scrollIntoView|focus|registerPlugin|Intl\.\w+|DateTimeFormat|NumberFormat|toLocaleString|"
    r"toLocaleDateString|toLocaleTimeString|localeCompare|Error|TypeError|DOMException)$"
)
CODE_WORDS = {
    "Enter", "Escape", "Esc", "Tab", "Backspace", "Delete", "Home", "End", "PageUp", "PageDown",
    "ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight", "Shift", "Control", "Alt", "Meta", "Space",
    "Bearer", "GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "Content-Type", "Authorization", "Accept",
    "Date", "Error", "TypeError", "AbortError", "TimeoutError", "NotAllowedError", "SecurityError",
    "QuotaExceededError", "NetworkError", "Object", "Array", "Promise", "Symbol", "Intl", "JSON", "Math",
    "Number", "String", "Boolean", "Infinity", "NaN", "UTC", "Z", "Mac", "Win", "Windows", "Linux",
    "Android", "iPhone", "iPad", "Safari", "Chrome", "Firefox", "Edg", "CriOS", "FxiOS",
}
_SINGLE_WORD = re.compile(r"^[A-Z][a-zà-ÿ’']+(?:[ -][A-Za-zà-ÿ’']+)?[.!?…:]?$")
_PROSE = re.compile(r"[A-Za-z’']{2,}[,;:]?\s+[A-Za-z’'(]")
_CODE_LIKE = re.compile(r"(^|\s)[.#][a-z][\w-]*|\[data-|:not\(|=>|\bvar\(--|https?://|^[a-z][\w-]*(\s+[a-z][\w-]*)*$|^[\w-]+=")


_GLUE_WORDS = {"the", "your", "in", "of", "and", "with", "to", "is", "are", "not", "no", "for", "from", "this",
               "that", "than", "more", "any", "none", "without", "only", "was", "were", "has", "have", "be", "it"}


def looks_like_text(text: str) -> bool:
    plain = re.sub(r"\{[^{}]*\}", " ", text)
    plain = normalize_space(plain)
    if not i18n.has_letter(plain):
        return False
    if plain in CODE_WORDS:
        return False
    if _PROSE.search(plain) and not _CODE_LIKE.search(plain):
        return True
    # All lowercase reads like a class list, unless English glue words show it
    # is a piece of a sentence (" statements in your text hold up").
    if (_PROSE.search(plain) and " " in plain and not re.search(r"[-_./:#=]", plain)
            and set(plain.lower().split()) & _GLUE_WORDS):
        return True
    # A count and its noun ("{length} answers", "{count} sources").
    if re.fullmatch(r"\{\w+\} [a-z’']{3,}[.…]?", text.strip()):
        return True
    # A label and its value after a middle dot ("Activity · {0}"): a German
    # screen reader read it in English, and nothing reported it (UX audit I4).
    if re.fullmatch(r"[A-Z][a-z’']{2,}(?: [a-z’']+)* · \{\w+\}", text.strip()):
        return True
    # A lowercase phrase around a number or a value ("of {total} checked
    # statements", " of 1 statement") is a piece of a sentence, not a class list.
    if (re.search(r"\{[^{}]*\}|\d", text) and len(re.findall(r"[A-Za-z’']{2,}", plain)) >= 2
            and " " in plain.strip()
            and not re.search(r"[a-z0-9]-(?:[a-z0-9]|\s|$)|[/()#_:=;{}\[\]]|px\b|\.[a-z]", plain)):
        return True
    return bool(_SINGLE_WORD.match(plain))


def normalize_space(text: str) -> str:
    return " ".join(text.split())


def _callee(tokens: list[Token], open_index: int) -> str:
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
    return ".".join(reversed(parts))


_ICON_EXPRESSION = re.compile(r"icon|svg|Icon|ICON|chevron|CHEVRON")


def _template_text(token: Token) -> str:
    chunks, expressions = token.parts
    out = [chunks[0]]
    for index, expression in enumerate(expressions):
        # ${icons.ask}, ${EYE_ICON}: markup, an element without words on the page.
        out.append("<svg></svg>" if _ICON_EXPRESSION.search(expression) else _js_placeholder(expression, index))
        out.append(chunks[index + 1])
    return "".join(out)


def _js_placeholder(expression: str, index: int) -> str:
    head = expression.strip()
    simple = re.fullmatch(r"[A-Za-z_$][\w$]*(?:\??\.[A-Za-z_$][\w$]*)*", head)
    if simple:
        return "{" + re.split(r"\??\.", head)[-1].lstrip("$") + "}"
    return "{" + str(index) + "}"


_MARKUP = re.compile(r"<[a-z][\w-]*[\s>/]")


def _unique_placeholders(text: str) -> str:
    """Two different values never share a name: the second {label} is {label2}, the second {0} the next number."""
    seen: set[str] = set()
    numbers = [int(name) for name in re.findall(r"\{(\d+)\}", text)]
    following = (max(numbers) + 1) if numbers else 0

    def rename(match: re.Match) -> str:
        nonlocal following
        name = match.group(1)
        if name not in seen:
            seen.add(name)
            return match.group(0)
        if name.isdigit():
            name = str(following)
            following += 1
        else:
            suffix = 2
            while f"{name}{suffix}" in seen:
                suffix += 1
            name = f"{name}{suffix}"
        seen.add(name)
        return "{" + name + "}"

    return re.sub(r"\{([A-Za-z_]\w*|\d+)\}", rename, text)


def _keys_of_text(text: str) -> list[str]:
    text = _unique_placeholders(text)
    if _MARKUP.search(text):
        return [key for key in i18n.html_segments(text) if _letters_outside_placeholders(key)]
    key = i18n.normalize(text)
    return [key] if key and looks_like_text(key) else []


def _operand_end(tokens: list[Token], index: int) -> int:
    """Index after the operand starting at ``index`` (a value in a + chain)."""
    length = len(tokens)
    if index >= length:
        return index
    token = tokens[index]
    if token.kind in {"string", "template", "number"}:
        index += 1
    elif token.kind == "name" or (token.kind == "punct" and token.value == "("):
        if token.kind == "punct":
            index = _close(tokens, index) + 1
        else:
            index += 1
        while index < length:
            current = tokens[index]
            if current.kind == "punct" and current.value in ".?" and index + 1 < length and tokens[index + 1].kind == "name":
                index += 2
                continue
            if current.kind == "punct" and current.value == "?" and index + 2 < length and tokens[index + 1].value == "." and tokens[index + 2].kind == "name":
                index += 3
                continue
            if current.kind == "punct" and current.value in "([":
                index = _close(tokens, index) + 1
                continue
            break
    else:
        return index
    return index


def _close(tokens: list[Token], index: int) -> int:
    pairs = {"(": ")", "[": "]", "{": "}"}
    opening = tokens[index].value
    closing = pairs[opening]
    depth = 0
    while index < len(tokens):
        token = tokens[index]
        if token.kind == "punct" and token.value == opening:
            depth += 1
        elif token.kind == "punct" and token.value == closing:
            depth -= 1
            if depth == 0:
                return index
        index += 1
    return len(tokens) - 1


def _chains(tokens: list[Token]) -> list[tuple[int, str]]:
    """``"a " + x + " b"`` → (line, "a {x} b"), for chains with a text literal."""
    found: list[tuple[int, str]] = []
    index = 0
    length = len(tokens)
    while index < length:
        token = tokens[index]
        start_ok = token.kind in {"string", "template", "name", "number"} or (token.kind == "punct" and token.value == "(")
        if not start_ok:
            index += 1
            continue
        previous = tokens[index - 1] if index else None
        if previous is not None and previous.kind == "punct" and previous.value in {".", "+"}:
            index += 1
            continue
        operands: list[tuple[int, int]] = []
        position = index
        while True:
            end = _operand_end(tokens, position)
            if end == position:
                break
            operands.append((position, end))
            if end < length and tokens[end].kind == "punct" and tokens[end].value == "+" and not (
                    end + 1 < length and tokens[end + 1].kind == "punct" and tokens[end + 1].value in "+="):
                position = end + 1
                continue
            break
        literal = [tokens[a] for a, b in operands if b - a == 1 and tokens[a].kind in {"string", "template"}]
        if len(operands) >= 2 and literal:
            parts: list[str] = []
            counter = 0
            for a, b in operands:
                first = tokens[a]
                if b - a == 1 and first.kind == "string":
                    parts.append(first.value)
                elif b - a == 1 and first.kind == "template":
                    parts.append(_template_text(first))
                else:
                    name = first.value if b - a == 1 and first.kind == "name" else (
                        tokens[b - 1].value if tokens[b - 1].kind == "name" else str(counter))
                    parts.append("{" + name.lstrip("$") + "}")
                    counter += 1
            text = "".join(parts)
            if any(looks_like_text(item.value if item.kind == "string" else _template_text(item)) or
                   _MARKUP.search(item.value if item.kind == "string" else _template_text(item)) for item in literal):
                found.append((token.line, text))
            index = operands[-1][1]
            continue
        index += 1
    return found


_T_CALL = re.compile(r"(^|\.)App\.t$")


def _t_context(tokens: list[Token], index: int, callee: str) -> str:
    """App.t("…", params, "watch schedule"): the context its first argument is
    looked up under, so the key names that entry ("watch schedule|…")."""
    if not index or not _T_CALL.search(callee) or tokens[index - 1].value != "(":
        return ""
    depth = commas = 0
    for position in range(index + 1, len(tokens)):
        token = tokens[position]
        if token.kind != "punct":
            continue
        if token.value in "([{":
            depth += 1
        elif token.value in ")]}":
            if not depth:
                return ""
            depth -= 1
        elif token.value == "," and not depth:
            commas += 1
            if commas == 2:
                rest = tokens[position + 1:position + 3]
                if len(rest) == 2 and rest[0].kind == "string" and rest[1].value == ")":
                    return rest[0].value
                return ""
    return ""


def script_keys(relative: str, source: str | None = None) -> list[Found]:
    source = source if source is not None else (ROOT / relative).read_text(encoding="utf-8")
    # A line marked "i18n-ignore" holds words that are no English text (the
    # German words of App.format).
    ignored = {number for number, line in enumerate(source.splitlines(), 1) if "i18n-ignore" in line}
    tokens = [token for token in tokenize(source) if not (token.line in ignored and token.kind in {"string", "template"})]
    found: list[Found] = []
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
        if token.kind == "template":
            # Words inside ${…} are literals of their own.
            for expression in token.parts[1]:
                found.extend(Found(item.key, relative, token.line + item.line - 1) for item in script_keys(relative, expression))
        context = calls[-1] if calls else ""
        if context and CODE_CALLS.search(context):
            continue
        following = tokens[index + 1] if index + 1 < len(tokens) else None
        previous = tokens[index - 1] if index else None
        if (following is not None and following.kind == "punct" and following.value == ":" and token.kind == "string"
                and previous is not None and previous.kind == "punct" and previous.value in "{,"):
            continue
        before = [item.value for item in tokens[max(0, index - 2):index] if item.kind == "punct"]
        after = [item.value for item in tokens[index + 1:index + 3] if item.kind == "punct"]
        if before[-2:] == ["=", "="] or after[:2] == ["=", "="] or before[-2:] == ["!", "="] or (
                previous is not None and previous.kind == "name" and previous.value in {"case", "in", "typeof", "import", "from"}):
            continue
        text = token.value if token.kind == "string" else _template_text(token)
        prefix = _t_context(tokens, index, context)
        for key in _keys_of_text(text):
            found.append(Found(f"{prefix}|{key}" if prefix else key, relative, token.line))
    for line, text in _chains(tokens):
        for key in _keys_of_text(text):
            if "{" in key:
                found.append(Found(key, relative, line))
    return found


# ---------------------------------------------------------------------------
# Sentences composed from parts
# ---------------------------------------------------------------------------
# The page looks a text up as a whole (static/js/i18n.js). A template that
# chooses words inside ${…} and puts other text around them ("Difference:
# ${text}" with the word picked in the expression) has no entry of its own,
# so those words stayed English on a German page. Each such template is
# composed with its words, the other values standing in, and looked up the
# way the page does it; what finds nothing is reported.

_TRANSLATED_CALL = re.compile(r"\bApp\??\.t\s*\(|(?<![\w.])t\s*\(")
_PLAIN_WORDS = re.compile(r"[a-z’']{3,}(?: [a-z’']+)*")


def _chosen_words(expression: str) -> list[str]:
    """Interface words a ${…} picks itself (not through App.t): the branches
    of ``a ? "x" : "y"``, a fallback ``|| "x"``, a value in ``{key: "x"}``."""
    if _TRANSLATED_CALL.search(expression):
        return []
    tokens = tokenize(expression)
    return [token.value for index, token in enumerate(tokens) if token.kind == "string"
            and index and tokens[index - 1].kind == "punct" and tokens[index - 1].value in "?:|"
            and (_keys_of_text(token.value) or _PLAIN_WORDS.fullmatch(token.value))]


def composed_in(relative: str, source: str, current: i18n.Catalog) -> list[Found]:
    gaps: list[Found] = []
    ignored = {number for number, line in enumerate(source.splitlines(), 1) if "i18n-ignore" in line}
    for token in tokenize(source):
        if token.kind != "template" or token.line in ignored:
            continue
        chunks, expressions = token.parts
        # Markup is translated element by element, not as one text.
        if _MARKUP.search("".join(chunks)):
            continue
        choices = [_chosen_words(expression) for expression in expressions]
        if not any(choices) or (len(expressions) == 1 and not "".join(chunks).strip()):
            continue
        # A value no entry knows (a name, a number) stands in for the rest.
        options = [words or [f"Q{index}7"] for index, words in enumerate(choices)]
        for combination in itertools.islice(itertools.product(*options), 16):
            text = i18n.normalize(chunks[0] + "".join(value + chunks[index + 1] for index, value in enumerate(combination)))
            if not looks_like_text(re.sub(r"Q\d+7", "{x}", text)):
                continue
            translated = current.lookup(text)
            # A pattern whose placeholder took the chosen word whole
            # ("Allow {0} first." with "reading emails") leaves it English.
            kept = translated is not None and any(
                re.search(rf"(?<!\w){re.escape(word.strip())}(?!\w)", translated)
                and current.lookup(i18n.normalize(word)) != i18n.normalize(word)
                for word in combination if not word.startswith("Q") and re.search(r"[a-z]{3}", word))
            if translated is None or kept:
                gaps.append(Found(text, relative, token.line))
                break
    return gaps


# A label read aloud, put together from values only, one of them a word in
# a variable (``setAttribute("aria-label", `${label} ${count}`)``): the page
# looks the whole value up, finds no entry, and a German screen reader heard
# "Notes 4" (UX audit I4). The word goes through App.t first; a variable
# named like an interface word (label, word, text, …Word) that does not is
# reported. A value with words of its own is a pattern ("Choose model:
# {displayLabel}") and found as a key instead.
_READ_ATTRIBUTES = {"aria-label", "title", "placeholder", "aria-description", "aria-roledescription"}
_WORD_VARIABLE = re.compile(r"label|word|[a-z]\w*(?:Label|Word)")


def composed_attributes(relative: str, source: str) -> list[Found]:
    gaps: list[Found] = []
    tokens = tokenize(source)
    for index, token in enumerate(tokens[:-3]):
        opening, attribute, comma = tokens[index + 1:index + 4]
        if not (token.kind == "name" and token.value == "setAttribute" and opening.value == "("
                and attribute.kind == "string" and attribute.value in _READ_ATTRIBUTES and comma.value == ","):
            continue
        # Every template of the value, also in a branch (`n === null ? label : `${label} ${n}``).
        for value in tokens[index + 4:_close(tokens, index + 1)]:
            if value.kind != "template":
                continue
            chunks, expressions = value.parts
            words = [expression.strip() for expression in expressions
                     if _WORD_VARIABLE.fullmatch(expression.strip()) and not _TRANSLATED_CALL.search(expression)]
            if words and len(expressions) > 1 and not re.search(r"[A-Za-z]", "".join(chunks)):
                gaps.append(Found(f"{attribute.value}: {_template_text(value)} (App.t({words[0]}) first)", relative, value.line))
    return gaps


def composed_gaps(language: str = "de") -> list[Found]:
    current = i18n.catalog(language) or i18n.Catalog({})
    gaps = [gap for relative in script_files()
            for gap in composed_in(relative, (ROOT / relative).read_text(encoding="utf-8"), current)]
    gaps.extend(gap for relative in script_files()
                for gap in composed_attributes(relative, (ROOT / relative).read_text(encoding="utf-8")))
    gaps.extend(item for relative in template_files() for item in template_keys(relative) if TAG_IN_VALUE in item.key)
    return gaps


# ---------------------------------------------------------------------------
# Server sentences
# ---------------------------------------------------------------------------

_SERVER_KEYS = {"error", "message", "detail", "reason", "hint"}


def _string_of(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        parts: list[str] = []
        counter = 0
        for value in node.values:
            if isinstance(value, ast.Constant):
                parts.append(str(value.value))
            else:
                inner = value.value if isinstance(value, ast.FormattedValue) else value
                name = inner.attr if isinstance(inner, ast.Attribute) else (inner.id if isinstance(inner, ast.Name) else str(counter))
                parts.append("{" + name + "}")
                counter += 1
        return "".join(parts)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left, right = _string_of(node.left), _string_of(node.right)
        if left is not None and right is not None:
            return left + right
    return None


# Files whose data holds words for the page under other names.
SERVER_TEXT_KEYS = {"app/services/starter_questions.py": {"label", "question"}, "app/core/config.py": {"label", "hint"}}
# Files that mark every fixed word themselves: the first argument of these
# calls is a key, whatever it looks like ("Why" is no prose to the heuristic).
SERVER_MARKED = {"app/services/mailer.py": {"_t", "_h", "_N"}}
# Services whose exceptions carry a sentence for the page: the first argument
# of ``raise Name("…")`` for these classes reaches a card as the server's
# ``error`` (routers/agent.py: the hold, secret and notes endpoints answer
# with ``str(exc)``), e.g. "This pause is already over." (B7).
SERVER_RAISED = {"app/services/agent_sessions.py": {"TurnStatusConflict", "NotesFull"}}


def server_keys(relative: str) -> list[Found]:
    source = (ROOT / relative).read_text(encoding="utf-8")
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    found: list[Found] = []

    def add(node: ast.AST) -> None:
        text = _string_of(node)
        if text and looks_like_text(text) and (_PROSE.search(re.sub(r"\{[^{}]*\}", "x", text)) or relative in SERVER_TEXT_KEYS):
            found.append(Found(i18n.normalize(text), relative, getattr(node, "lineno", 0)))

    for node in ast.walk(tree):
        if isinstance(node, ast.Raise) and isinstance(node.exc, ast.Call) and node.exc.args:
            raised = node.exc.func
            name = raised.attr if isinstance(raised, ast.Attribute) else (raised.id if isinstance(raised, ast.Name) else "")
            if name in SERVER_RAISED.get(relative, ()):
                add(node.exc.args[0])
        if isinstance(node, ast.Call):
            name = node.func.attr if isinstance(node.func, ast.Attribute) else (node.func.id if isinstance(node.func, ast.Name) else "")
            if name in SERVER_MARKED.get(relative, ()) and node.args:
                text = _string_of(node.args[0])
                # A context names its own entry: "mail|{schedule} {city} time".
                context = next((_string_of(keyword.value) for keyword in node.keywords
                                if keyword.arg == "context"), None)
                if text and i18n.has_letter(text):
                    found.append(Found((f"{context}|" if context else "") + i18n.normalize(text),
                                       relative, node.lineno))
                continue
            if name in {"HTTPException", "_http_error", "http_error", "error_response", "PublicError", "UserFacingError"}:
                for keyword in node.keywords:
                    if keyword.arg in {"detail", "message"}:
                        add(keyword.value)
                for argument in node.args[1:2]:
                    add(argument)
        if isinstance(node, ast.Dict):
            for key, value in zip(node.keys, node.values):
                if isinstance(key, ast.Constant) and key.value in _SERVER_KEYS | SERVER_TEXT_KEYS.get(relative, set()) and value is not None:
                    add(value)
    return found


# ---------------------------------------------------------------------------
# Sources
# ---------------------------------------------------------------------------

def template_files() -> list[str]:
    files = sorted((ROOT / "templates").glob("*.html")) + sorted((ROOT / "templates" / "partials").glob("*.html"))
    relative = [path.relative_to(ROOT).as_posix() for path in files]
    return [item for item in relative if item not in SKIP_TEMPLATES]


def script_files() -> list[str]:
    files = sorted((ROOT / "static" / "js").glob("*.js")) + sorted((ROOT / "static").glob("*.js"))
    relative = [path.relative_to(ROOT).as_posix() for path in files]
    return [item for item in relative if item not in SKIP_SCRIPTS]


def server_files() -> list[str]:
    files = sorted((ROOT / "app" / "api" / "routers").glob("*.py")) + [ROOT / "main.py"]
    files += [ROOT / name for name in (*SERVER_TEXT_KEYS, *SERVER_MARKED, *SERVER_RAISED)]
    return [path.relative_to(ROOT).as_posix() for path in files if path.name != "admin.py"]


def all_keys() -> list[Found]:
    found: list[Found] = []
    for relative in template_files():
        found.extend(template_keys(relative))
    for relative in script_files():
        found.extend(script_keys(relative))
    for relative in server_files():
        found.extend(server_keys(relative))
    return found


def covered(current: i18n.Catalog, key: str) -> bool:
    if key in current.exact or key in current.templates or key in current.values:
        return True
    if "{" not in key:
        return current.lookup(key) is not None
    return False


def missing(language: str = "de") -> dict[str, list[Found]]:
    current = i18n.catalog(language) or i18n.Catalog({})
    grouped: dict[str, list[Found]] = {}
    seen: set[str] = set()
    for item in all_keys():
        if item.key in seen or covered(current, item.key) or TAG_IN_VALUE in item.key:
            continue
        seen.add(item.key)
        grouped.setdefault(item.source, []).append(item)
    return grouped


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=["missing", "check"])
    parser.add_argument("--lang", default="de")
    parser.add_argument("--json", help="write {file: {key: ''}} for translation")
    args = parser.parse_args(argv)
    grouped = missing(args.lang)
    total = sum(len(items) for items in grouped.values())
    current = i18n.catalog(args.lang)
    rejected = current.rejected if current else []
    if args.json:
        Path(args.json).write_text(json.dumps({source: {item.key: "" for item in items} for source, items in grouped.items()},
                                              ensure_ascii=False, indent=1), encoding="utf-8")
    if args.command == "missing" and not args.json:
        for source, items in grouped.items():
            print(f"\n{source} ({len(items)})")
            for item in items:
                print(f"  {item.line:5}  {item.key}")
    for key, value in rejected:
        print(f"invalid entry (markers or placeholders differ): {key!r} -> {value!r}")
    composed = composed_gaps(args.lang)
    if composed:
        print("\ncomposed from parts, no entry for the whole (write whole sentences, in a template one"
              " whole value per branch, or App.t each part):")
        for item in composed:
            print(f"  {item.source}:{item.line}  {item.key}")
    print(f"\n{total} keys without {args.lang}, {len(rejected)} invalid entries, {len(composed)} composed sentences")
    return 1 if (args.command == "check" and (total or rejected or composed)) else 0


if __name__ == "__main__":
    raise SystemExit(main())

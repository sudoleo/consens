"""Remove source-reference markup from newly generated consensus prose only.

The same scanner powers complete and streamed answers. Only ambiguous trailing
citation/code/math delimiters are buffered, so ordinary prose streams promptly.
Literal code and mathematical notation retain their exact bytes.
This module is deliberately not used when loading historical answers.
"""
from __future__ import annotations

import re

_FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")
_SOURCE = re.compile(r"\[S\d{1,6}(?:\s*,\s*S?\d{1,6})*\](?:\([^\n)]*\))?", re.I)
_ENVIRONMENT = re.compile(r"\\begin\{(equation|align|alignat|gather|CD)\*?\}")
_PARTIAL_SOURCE = re.compile(r"\[(?:S\d{0,6}(?:\s*,\s*S?\d{0,6})*)?(?:\](?:\([^\n)]*)?)?$", re.I)
_PARTIAL_ESCAPE = re.compile(r"\\(?:[a-zA-Z]*(?:\{[^}\n]*\}?)?)?$")
_PARTIAL_RUN = re.compile(r"[`$]+$")
# Same conservative inline-dollar contract as math-render.js: a short,
# single-line pair with a LaTeX signal, never arbitrary currency prose.
_INLINE_DOLLAR = re.compile(r"\$(?!\s)((?:[^$\n\\]|\\[^\n])+?)(?<![\s\\])\$(?![\w$])")
_PARTIAL_INLINE_DOLLAR = re.compile(r"(?<![\\$\w])\$(?![\s$])((?:[^$\n\\]|\\[^\n]){0,200})(?:\\)?(?:\$)?$")
_LATEX_SIGNAL = re.compile(r"\\[A-Za-z]|[\^_{}]")


class ConsensusCitationFilter:
    def __init__(self):
        self.pending = ""
        self.fence = ""
        self.literal = ""
        self.line_start = True
        self.indented_line = False
        self.previous_char = ""

    def feed(self, text: str, *, final: bool = False) -> str:
        self.pending += str(text or "")
        lines = self.pending.splitlines(keepends=True)
        self.pending = ""
        if lines and not final and not lines[-1].endswith(("\n", "\r")):
            self.pending = lines.pop()
        out = []
        for line in lines:
            out.append(self._line(line))
            self.previous_char = line[-1:]
            self.line_start = line.endswith(("\n", "\r"))
            if self.line_start:
                self.indented_line = False
        if self.pending:
            # A fence/indent prefix needs its line context. Other prose can
            # flow immediately, keeping only a potentially incomplete token.
            if self.fence or (self.line_start and re.match(r"^ {0,3}(?:$|[`~])", self.pending)):
                return "".join(out)
            cutoff = len(self.pending)
            for pattern in (_PARTIAL_SOURCE, _PARTIAL_ESCAPE, _PARTIAL_RUN):
                match = pattern.search(self.pending)
                if match:
                    start = match.start()
                    if start and self.pending[start - 1] == "\\":
                        start -= 1
                    cutoff = min(cutoff, start)
            complete_math = [match for match in _INLINE_DOLLAR.finditer(self.pending)
                if len(match[1]) <= 200 and _LATEX_SIGNAL.search(match[1])
                and not re.match(r"[\\$\w]", self.pending[match.start() - 1] if match.start() else self.previous_char)]
            dollar = _PARTIAL_INLINE_DOLLAR.search(self.pending)
            if (dollar and (dollar.start() or not re.match(r"[\\$\w]", self.previous_char))
                    and not any(match.start() <= dollar.start() < match.end() for match in complete_math)):
                cutoff = min(cutoff, dollar.start())
            for math in complete_math:
                if math.start() <= cutoff < math.end():
                    cutoff = math.start() if math.end() == len(self.pending) else math.end()
            if cutoff:
                out.append(self._line(self.pending[:cutoff]))
                self.previous_char = self.pending[cutoff - 1]
                self.pending = self.pending[cutoff:]
                self.line_start = False
        return "".join(out)

    def _line(self, line: str) -> str:
        marker = _FENCE.match(line.rstrip("\r\n")) if self.line_start else None
        if self.fence:
            if (marker and marker[1][0] == self.fence[0]
                    and len(marker[1]) >= len(self.fence) and not marker[2].strip()):
                self.fence = ""
            return line
        if not self.literal and marker and not (marker[1][0] == "`" and "`" in marker[2]):
            self.fence = marker[1]
            return line
        if self.line_start and not self.literal and line.startswith(("    ", "\t")):
            self.indented_line = True
        if self.indented_line:
            return line
        out = []
        i = 0
        while i < len(line):
            if self.literal:
                delimiter = self.literal
                if delimiter.startswith("`") and line[i] == "`":
                    run = re.match(r"`+", line[i:])[0]
                    out.append(run)
                    i += len(run)
                    if run == delimiter:
                        self.literal = ""
                    continue
                closes = line.startswith(delimiter, i)
                if closes:
                    out.append(delimiter)
                    i += len(delimiter)
                    self.literal = ""
                else:
                    out.append(line[i])
                    i += 1
                continue
            # Escaped source examples and math delimiters are literal. KaTeX
            # also accepts \( ... \) and \[ ... \] outside dollar math.
            environment = _ENVIRONMENT.match(line, i)
            if environment:
                opening = environment[0]
                self.literal = opening.replace("\\begin", "\\end", 1)
                out.append(opening)
                i = environment.end()
            elif line.startswith("\\[", i) and _SOURCE.match(line, i + 1):
                escaped = _SOURCE.match(line, i + 1)
                out.append(line[i:escaped.end()])
                i = escaped.end()
            elif line.startswith(("\\(", "\\["), i):
                opening = line[i:i + 2]
                self.literal = "\\)" if opening == "\\(" else "\\]"
                out.append(opening)
                i += 2
            elif line[i] == "\\" and i + 1 < len(line):
                out.append(line[i:i + 2])
                i += 2
            elif line[i] == "`":
                match = re.match(r"`+", line[i:])
                self.literal = match[0]
                out.append(match[0])
                i += len(match[0])
            elif line.startswith("$$", i):
                self.literal = "$$"
                out.append(self.literal)
                i += len(self.literal)
            elif line[i] == "$":
                previous = line[i - 1] if i else self.previous_char
                math = _INLINE_DOLLAR.match(line, i) if not re.match(r"[\\$\w]", previous) else None
                if math and len(math[1]) <= 200 and _LATEX_SIGNAL.search(math[1]):
                    out.append(math[0])
                    i = math.end()
                else:
                    out.append(line[i])
                    i += 1
            else:
                citation = _SOURCE.match(line, i)
                if citation:
                    i = citation.end()
                else:
                    out.append(line[i])
                    i += 1
        return "".join(out)


def strip_consensus_source_markers(text: str) -> str:
    return ConsensusCitationFilter().feed(text, final=True)

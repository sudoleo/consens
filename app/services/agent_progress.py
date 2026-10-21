"""Numeric stream counters and bounded highlights; never a second model call.

Provider summaries are preferred. Other visible reasoning supplies short,
verbatim sentence excerpts, explicitly identified as excerpts, not invented
semantic summaries. Full continuation/signature data stays in agent_client.
"""
import re
import time


class StreamProgress:
    """Numeric live telemetry; no transcript, token estimate or billing mutation."""
    def __init__(self, chars=0):
        self.chars = chars
        self.reasoning_lengths = {}
        self.last_sent = None
        self.last_at = None

    def update(self, event):
        text = event.get("text")
        if not isinstance(text, str):
            return
        if event.get("type") == "delta":
            self.chars += len(text)
        elif event.get("kind") == "reasoning" and event.get("format") in {"text", "summary"}:
            key = (event.get("id"), event["format"])
            previous = self.reasoning_lengths.get(key, 0)
            length = previous + len(text) if event.get("append") else len(text)
            self.chars += max(0, length - previous)
            self.reasoning_lengths[key] = max(previous, length)

    def snapshot(self, usage, *, streaming=True, force=False):
        measured = usage and all(type(usage.get(key)) is int and usage[key] >= 0
                                 for key in ("input_tokens", "output_tokens"))
        counts = ({key: usage.get(key) for key in ("input_tokens", "output_tokens", "complete")}
                  if measured else None)
        snapshot = {"chars": self.chars, "usage": counts, "streaming": streaming}
        now = time.monotonic()
        if not force and (snapshot == self.last_sent or self.last_at is not None and now - self.last_at < .5):
            return None
        self.last_sent, self.last_at = snapshot, now
        return snapshot


# A short announcement of the model's own next step ("I'll answer directly.",
# "Let me search.", "No search needed.") is true but says nothing about the
# question; shown as the one live line it reads like a strange verdict.
# Longer planning sentences name their topic and stay.
_PLAN_ONLY = re.compile(
    r"^(?:(?:ok(?:ay)?|so|alright|right|now|then|well)[,.!]?\s+)*"
    r"(?:i[\u2019']ll|i will|i[\u2019']m going to|i am going to|let me|let[\u2019']s|i should|i need to|i can"
    r"|no (?:need (?:to|for) )?(?:a |any )?(?:web )?search|(?:a |the )?(?:web )?search (?:is )?(?:not )?needed)\b",
    re.IGNORECASE)
_PLAN_ONLY_MAX_CHARS = 40


def _plan_only(sentence):
    return len(sentence) <= _PLAN_ONLY_MAX_CHARS and bool(_PLAN_ONLY.match(sentence))


# Highlights quote complete statements only (2026-10-21; before, the last
# sentence of the streamed buffer was cut at 177 characters, and "e.g.",
# "U.S." or "3." at the end of the buffer passed for the end of a
# sentence). A sentence ends where its punctuation is followed by
# whitespace that has arrived, not inside common abbreviations, initials or
# German ordinals ("am 3. Oktober"). Nothing is ever shortened: a sentence
# over _EXCERPT_MAX_CHARS gives way to a shorter one, or the previous
# highlight stays.
_EXCERPT_MIN_CHARS = 12
_EXCERPT_MAX_CHARS = 160
_WINDOW_CHARS = 8000
_CLOSERS = "\"'”’)]"
_SENTENCE_END = re.compile(r"[.!?]+[\"'”’)\]]*(?=\s)")
_LINE_END = re.compile(r"(?:[!?]|(?<!\.)\.)[\"'”’)\]]*$")
_ABBREVIATIONS = frozenset({
    "approx", "ca", "cf", "co", "corp", "dept", "dr", "esp", "est", "etc", "fig", "inc", "jr", "ltd",
    "mr", "mrs", "ms", "no", "nos", "nr", "prof", "sr", "st", "vol", "vs", "jan", "feb", "mar", "apr",
    "jun", "jul", "aug", "sep", "sept", "oct", "nov", "dec", "bzw", "evtl", "ggf", "inkl", "usw", "vgl",
    "zzgl", "abs", "bd", "bzgl", "hr", "fr", "mio", "mrd", "tsd",
})
# German ordinals ("am 3. Oktober", "im 19. Jahrhundert"): the number follows
# one of these words. "option 2. Then" and "costs 100. The" end a sentence.
_ORDINAL_AFTER = frozenset({
    "am", "vom", "zum", "zur", "im", "beim", "bis", "ab", "seit", "der", "die", "das", "den", "dem",
    "des", "ein", "eine", "einem", "einen", "einer", "jeden", "jedem", "jeder", "ihrem", "seinem",
})
# A heading line: "**Comparing options**" (OpenAI and Gemini summaries) or "## Plan".
_HEADING = re.compile(r"^(?:#{1,6}\s+(.+?)\s*#*|\*\*([^*\n]+)\*\*|__([^_\n]+)__)$")
_LIST_MARK = re.compile(r"^\s*(?:[-*•>]+\s+|\d{1,3}[.)]\s+)")


def _ends_sentence(line, match):
    marks = match.group().rstrip(_CLOSERS)
    if "!" in marks or "?" in marks:
        return True
    if marks != ".":
        return False  # an ellipsis trails off; it ends nothing
    # The two words before the period (a bounded look back: a word that
    # long is no abbreviation, and a long line is not split again per match).
    before = line[max(0, match.start() - 40):match.start()].split()
    word = before[-1].lstrip("([\"'“‘") if before else ""
    if "." in word or word.lower() in _ABBREVIATIONS or (len(word) == 1 and word.isalpha()):
        return False  # "e.g.", "U.S.", "z.B.", "etc.", "J. Smith"
    if word.isdigit() and len(word) <= 2 and len(before) > 1 and before[-2].lower() in _ORDINAL_AFTER:
        return False
    return True


def _sentences(line, finished):
    """The complete sentences of one line. A finished line also ends with
    its last sentence, if that one ends with punctuation."""
    sentences, start = [], 0
    for match in _SENTENCE_END.finditer(line):
        if _ends_sentence(line, match):
            sentences.append(line[start:match.end()])
            start = match.end()
    tail = line[start:].strip()
    if finished and tail and _LINE_END.search(tail):
        sentences.append(tail)
    return [cleaned for cleaned in map(_clean, sentences) if cleaned]


def _clean(text):
    text = re.sub(r"\*\*|__|`", "", _LIST_MARK.sub("", text))
    return re.sub(r"\s+", " ", text).strip()


def _heading(line):
    match = _HEADING.match(line.strip())
    return _clean(next(group for group in match.groups() if group)).rstrip(":") if match else ""


def _fits(text):
    return _EXCERPT_MIN_CHARS <= len(text) <= _EXCERPT_MAX_CHARS and not _plan_only(text)


class ReasoningProgress:
    def __init__(self, *, unlimited=False, min_seconds=0.0, clock=time.monotonic):
        # unlimited: a long step that writes the answer keeps showing signs of life for its
        # whole duration, paced by min_seconds instead of a fixed count.
        self.unlimited, self.min_seconds, self.clock = unlimited, min_seconds, clock
        self.text = ""
        self.summary = ""
        self.received_chars = 0
        self.published_chars = 0
        self.published_at = None
        self.updates = 0
        self.source = "excerpt"
        self.block = None
        self.truncated = False

    def update(self, event):
        if event.get("kind") != "reasoning" or event.get("format") not in {"text", "summary"}:
            return None
        source = "provider_summary" if event["format"] == "summary" else "excerpt"
        if self.source == "provider_summary" and source != self.source:
            return None
        if source != self.source:
            self.text, self.summary, self.received_chars, self.published_chars = "", "", 0, 0
            self.truncated = False
        self.source = source
        chunk = str(event.get("text", ""))
        # Each summary part is its own block ("reasoning.summary:1"); its
        # heading would otherwise stick to the last sentence of the part before.
        block = event.get("id")
        if block != self.block and self.text and not self.text.endswith("\n"):
            self.text += "\n\n"
        self.block = block
        text = self.text + chunk
        self.truncated |= len(text) > _WINDOW_CHARS
        self.text = text[-_WINDOW_CHARS:]
        # Growth is counted on everything received: the kept window stops
        # growing at 8000 characters and would otherwise freeze all updates.
        self.received_chars += len(chunk)
        # Reserve the final update for a native summary that may arrive late.
        limit = None if self.unlimited else 8 if source == "provider_summary" else 7
        if ((limit is not None and self.updates >= limit)
                or (self.summary and self.received_chars - self.published_chars < 400)
                or (self.published_at is not None and self.clock() - self.published_at < self.min_seconds)):
            return None
        summary = "\n".join(self._excerpts()[-3:])
        if not summary or summary == self.summary:
            return None
        self.summary, self.published_chars, self.published_at = summary, self.received_chars, self.clock()
        self.updates += 1
        return {"text": summary, "format": "summary", "summary_source": self.source, "append": False}

    def _excerpts(self):
        """One highlight per finished line, newest last: a heading stands
        for its section; otherwise the last fitting sentence of raw reasoning
        (where a paragraph arrives at its point) or the first of a provider
        summary (its topic sentence). The open line counts only while no
        line has finished, so a single long paragraph still shows progress."""
        text = self.text
        if self.truncated:
            # The window starts inside a sentence: skip to its end.
            cut = re.search(r"\n|[.!?][\"'”’)\]]*\s", text)
            text = text[cut.end():] if cut else ""
        *finished, current = text.split("\n")
        excerpts, sectioned = [], False
        def add(candidates, last):
            fitting = [sentence for sentence in candidates if _fits(sentence)]
            if fitting:
                excerpt = fitting[-1] if last else fitting[0]
                if excerpt in excerpts:
                    excerpts.remove(excerpt)
                excerpts.append(excerpt)
        for line in finished:
            if not line.strip():
                continue
            heading = _heading(line)
            if heading:
                # A heading too short or too long to quote leaves its
                # section to the sentences under it.
                sectioned = _fits(heading)
                add([heading], True)
                continue
            if sectioned:
                continue
            sentences = _sentences(line, True)
            if not sentences and self.source == "provider_summary" and not re.search(r"[.!?:;,]$", line.strip()):
                # A summary title without markup or punctuation.
                sentences = [_clean(line)]
            add(sentences, self.source == "excerpt")
        if not excerpts and current.strip() and not _heading(current):
            add(_sentences(current, False), self.source == "excerpt")
        return excerpts

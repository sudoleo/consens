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


class ReasoningProgress:
    def __init__(self):
        self.text = ""
        self.summary = ""
        self.published_chars = 0
        self.updates = 0
        self.source = "excerpt"

    def update(self, event):
        if event.get("kind") != "reasoning" or event.get("format") not in {"text", "summary"}:
            return None
        source = "provider_summary" if event["format"] == "summary" else "excerpt"
        if self.source == "provider_summary" and source != self.source:
            return None
        if source != self.source:
            self.text, self.summary, self.published_chars = "", "", 0
        self.source = source
        self.text = (self.text + str(event.get("text", "")))[-8000:]
        # Reserve the final update for a native summary that may arrive late.
        limit = 8 if source == "provider_summary" else 7
        if self.updates >= limit or (self.summary and len(self.text) - self.published_chars < 400):
            return None
        paragraphs = re.split(r"\n\s*\n", self.text)
        excerpts = []
        for paragraph in paragraphs:
            # Extract complete sentences from raw text. Provider summaries
            # may instead consist of short headings without punctuation.
            sentences = re.findall(r"[^.!?\n]+[.!?](?=\s|$)", paragraph)
            if not sentences and source == "provider_summary":
                sentences = [paragraph]
            if not sentences:
                continue
            for candidate in (sentences[-3:] if len(paragraphs) == 1 else sentences[:1]):
                sentence = re.sub(r"\s+", " ", candidate).strip(" #*\t")
                if len(sentence) > 180:
                    sentence = sentence[:177].rsplit(" ", 1)[0] + "…"
                if len(sentence) >= 12 and sentence not in excerpts:
                    excerpts.append(sentence)
        summary = "\n".join(excerpts[-3:])
        if not summary or summary == self.summary:
            return None
        self.summary, self.published_chars = summary, len(self.text)
        self.updates += 1
        return {"text": summary, "format": "summary", "summary_source": self.source, "append": False}

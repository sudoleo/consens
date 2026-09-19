"""Bounded, extractive progress highlights; never a second model call.

Provider summaries are preferred. Other visible reasoning supplies short,
verbatim sentence excerpts, explicitly identified as excerpts, not invented
semantic summaries. Full continuation/signature data stays in agent_client.
"""
import re


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

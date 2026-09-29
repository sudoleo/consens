"""Structured document content accepted by the document tools and the renderer.

Deliberately dependency-light: the isolated renderer subprocess imports this
module, and must not pull in Firestore, Firebase Admin or credentials.
"""
from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict, Field, model_validator

ID_PATTERN = r"^[a-f0-9]{32}$"


def _strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _strings(item)


def _has_control(text):
    return any((ord(c) < 32 and c not in "\n\t\r") or 0x7f <= ord(c) < 0xa0 for c in text)


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Table(Strict):
    headers: list[str] = Field(min_length=1, max_length=6)
    rows: list[list[str]] = Field(default_factory=list, max_length=60)

    @model_validator(mode="after")
    def bounded(self):
        if any(len(row) != len(self.headers) for row in self.rows):
            raise ValueError("Table rows must match the headers.")
        if any(len(cell) > 600 for row in [self.headers, *self.rows] for cell in row):
            raise ValueError("Table cells must be at most 600 characters.")
        return self


class Section(Strict):
    heading: str = Field(min_length=1, max_length=160)
    paragraphs: list[str] = Field(default_factory=list, max_length=30)
    table: Table | None = None


class Source(Strict):
    label: str = Field(min_length=1, max_length=200)
    file_id: str | None = Field(default=None, pattern=ID_PATTERN)
    locator: str = Field(default="", max_length=200)
    url: str = Field(default="", max_length=2000)

    @model_validator(mode="after")
    def safe_url(self):
        if self.url and (not re.match(r"^https?://[^\s/]+", self.url) or any(ord(c) < 32 for c in self.url)):
            raise ValueError("Sources require an HTTP(S) URL.")
        if not self.file_id and not self.url:
            raise ValueError("A source needs a file ID or URL.")
        return self


class DocumentSpec(Strict):
    title: str = Field(min_length=1, max_length=160)
    summary: str = Field(default="", max_length=3000)
    sections: list[Section] = Field(min_length=1, max_length=20)
    sources: list[Source] = Field(default_factory=list, max_length=30)
    uncertainties: list[str] = Field(default_factory=list, max_length=20)
    differing_views: list[str] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def bounded(self):
        if len(self.model_dump_json().encode()) > 40_000:
            raise ValueError("Document content exceeds the 40 KB limit.")
        # JSON encoding escapes control characters, so check the actual values.
        if any(_has_control(text) for text in _strings(self.model_dump())):
            raise ValueError("Document content must not contain control characters.")
        return self

"""Kleine Source-Maps fuer die Alert-Tests (Encoder nur fuer Testdaten)."""

from __future__ import annotations

import json
from pathlib import Path

_BASE64 = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"


def encode_vlq(values) -> str:
    out = ""
    for number in values:
        vlq = ((-number) << 1) | 1 if number < 0 else number << 1
        while True:
            digit = vlq & 31
            vlq >>= 5
            if vlq:
                digit |= 32
            out += _BASE64[digit]
            if not vlq:
                break
    return out


def encode_mappings(lines) -> str:
    """lines: pro generierter Zeile Segmente (gen_col, src, line, col), 0-basiert."""
    source = source_line = source_column = 0
    encoded_lines = []
    for segments in lines:
        column = 0
        encoded = []
        for gen_col, src, line, col in segments:
            encoded.append(encode_vlq([gen_col - column, src - source, line - source_line, col - source_column]))
            column, source, source_line, source_column = gen_col, src, line, col
        encoded_lines.append(",".join(encoded))
    return ";".join(encoded_lines)


def write_map(dist: Path, bundle: str, sources, lines) -> Path:
    path = dist / f"{bundle}.map"
    path.write_text(json.dumps({
        "version": 3, "file": bundle, "sources": list(sources), "names": [],
        "mappings": encode_mappings(lines),
    }), encoding="utf-8")
    return path

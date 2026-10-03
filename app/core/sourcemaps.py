"""Bundle-Koordinaten aus Browser-Fehlern auf die Quelldateien zurueckfuehren.

Die Bundles in ``static/dist`` sind minifiziert: ``app.<hash>.js:1:18420``
sagt dem Betreiber nichts. Der Build legt neben jedes JS-Bundle eine externe
Source-Map (``scripts/frontend-sourcemaps.mjs``); dieses Modul liest sie und
macht daraus ``static/js/<datei>.js:<zeile>:<spalte>``.

Bewusst klein und robust: ein eigener VLQ-Decoder statt einer Abhaengigkeit,
nur Bundle-Namen nach der festen Allowlist-Form (kein Pfad aus dem Request
erreicht das Dateisystem), und jede fehlende oder kaputte Map ergibt ``None``
statt einer Exception -- der Aufrufer ist ein Fehlerpfad.
"""

from __future__ import annotations

import bisect
import json
import logging
import re
from functools import lru_cache
from pathlib import Path

from app.core.observability import safe_exception


DIST_DIR = Path(__file__).resolve().parents[2] / "static" / "dist"
BUNDLE_SCRIPT = re.compile(r"(?:head|auth|firebase|demo|app)\.[a-f0-9]{12}\.js")
_BASE64 = {char: index for index, char in enumerate(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
)}
# Die Map des App-Bundles liegt bei rund 0,6 MB; groessere Dateien sind kein
# Build-Ergebnis und werden nicht geparst.
_MAX_MAP_BYTES = 8 * 1024 * 1024
_SAFE_SOURCE = re.compile(r"static/[A-Za-z0-9_./-]{1,200}")


def decode_vlq(segment: str) -> list[int]:
    """Ein Base64-VLQ-Segment einer Source-Map in seine Ganzzahlen."""
    values = []
    value = shift = 0
    for char in segment:
        digit = _BASE64.get(char)
        if digit is None:
            raise ValueError("invalid VLQ character")
        value += (digit & 31) << shift
        if digit & 32:
            shift += 5
            continue
        values.append(-(value >> 1) if value & 1 else value >> 1)
        value = shift = 0
    if shift:
        raise ValueError("truncated VLQ segment")
    return values


def decode_mappings(mappings: str) -> list[tuple[list[int], list[tuple[int, int, int]]]]:
    """Pro generierter Zeile: sortierte Spalten und (Quelle, Zeile, Spalte)."""
    lines = []
    source = source_line = source_column = 0
    for raw_line in mappings.split(";"):
        columns: list[int] = []
        targets: list[tuple[int, int, int]] = []
        column = 0
        for raw in raw_line.split(",") if raw_line else ():
            values = decode_vlq(raw)
            column += values[0]
            if len(values) >= 4:
                source += values[1]
                source_line += values[2]
                source_column += values[3]
                columns.append(column)
                targets.append((source, source_line, source_column))
        lines.append((columns, targets))
    return lines


class SourceMap:
    def __init__(self, data: dict):
        if data.get("version") != 3 or not isinstance(data.get("mappings"), str):
            raise ValueError("unsupported source map")
        self.sources = [str(item) for item in data.get("sources") or []]
        self.lines = decode_mappings(data["mappings"])

    def lookup(self, line: int, column: int) -> tuple[str, int, int] | None:
        """1-basierte Browser-Koordinaten -> 1-basierte Quellkoordinaten."""
        if line < 1 or column < 1 or line > len(self.lines):
            return None
        columns, targets = self.lines[line - 1]
        index = bisect.bisect_right(columns, column - 1) - 1
        if index < 0:
            return None
        source, source_line, source_column = targets[index]
        if not 0 <= source < len(self.sources):
            return None
        name = self.sources[source]
        # Nur Projektpfade wie static/js/x.js; was die Map sonst behauptet,
        # landet nicht in einer Telegram-Nachricht.
        if not _SAFE_SOURCE.fullmatch(name) or ".." in name:
            return None
        return name, source_line + 1, source_column + 1


@lru_cache(maxsize=6)
def _load(bundle: str, dist_dir: Path) -> SourceMap | None:
    path = dist_dir / f"{bundle}.map"
    try:
        if not path.is_file() or path.stat().st_size > _MAX_MAP_BYTES:
            return None
        return SourceMap(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, ValueError, TypeError, IndexError) as exc:
        logging.warning("Source map unreadable bundle=%s category=%s", bundle, safe_exception(exc))
        return None


def resolve_bundle_location(
    bundle: str, line: int, column: int, *, dist_dir: Path | None = None,
) -> str | None:
    """``static/js/x.js:12:5`` fuer eine Bundle-Koordinate, sonst ``None``."""
    if not isinstance(bundle, str) or not BUNDLE_SCRIPT.fullmatch(bundle):
        return None
    if type(line) is not int or type(column) is not int:
        return None
    source_map = _load(bundle, dist_dir or DIST_DIR)
    if source_map is None:
        return None
    found = source_map.lookup(line, column)
    if found is None:
        return None
    return f"{found[0]}:{found[1]}:{found[2]}"


def clear_cache() -> None:
    """Test-Helfer."""
    _load.cache_clear()

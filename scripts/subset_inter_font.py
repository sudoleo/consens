"""Split the self-hosted Inter into a Latin file and files for the rest.

Every page sets its text in Inter (``static/css/typography.css``). The two
variable source files cover about 2,850 characters and weigh 344 KB (upright)
and 379 KB (italic), although nearly every page needs only Latin letters and
a few symbols. This script writes three files per style:

* ``-latin``: Basic Latin, Latin-1, general punctuation and the symbols the
  interface and answers use (arrows, maths, currency, sub- and superscripts,
  check marks, shapes). Every page loads this one, about 135 KB.
* ``-latin-ext``: accented letters beyond Latin-1 (Polish, Czech, Turkish,
  Vietnamese names) and combining marks.
* ``-rest``: everything else in the source (Greek, Cyrillic, enclosed and
  technical symbols, Inter's private-use alternates).

``typography.css`` declares all three under the same family with
``unicode-range``; a browser downloads a file only for a page that contains
one of its characters. Every file keeps all OpenType features and both
variation axes (``wght``, ``opsz``), so text renders as with the source.

Each file carries the first 12 hex digits of its SHA-256 in its name
(``InterVariable-latin.<hash>.woff2``): the URL changes whenever the bytes
do, so the server lets browsers keep the file for a year without asking
again (``app/core/static_delivery.py``), and a returning visitor has Inter
before the first paint. Writing a file removes its older hashed copy and
moves the URL in ``typography.css``; the pages preload the Latin file at the
URL ``app/core/assets.font_preload_urls`` reads back from that stylesheet.

Sources: ``InterVariable.woff2`` and ``InterVariable-Italic.woff2`` (Inter
4.001, rsms/inter, SIL OFL) stay unchanged in ``static/fonts/inter``. No
stylesheet references them any more; a tab that still runs an older
stylesheet keeps finding them. A part's old, unhashed name
(``InterVariable-latin.woff2``) is answered with its current hashed file
(``app/core/static_delivery.legacy_font_target``), so renaming never leaves
an open tab without its font.

fonttools and brotli are not app dependencies; install them anywhere:

    py -3.12 -m pip install fonttools brotli
    python scripts/subset_inter_font.py          # write the six files
    python scripts/subset_inter_font.py --check  # verify files and CSS only

Both modes check that the files of a style together cover every character
of the source exactly once and that ``typography.css`` declares exactly the
ranges this script derives. ``tests/test_public_design_system.py`` imports
the range constants (fonttools is only needed inside the functions).
"""
from __future__ import annotations

import argparse
import hashlib
import io
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FONT_DIR = ROOT / "static" / "fonts" / "inter"
TYPOGRAPHY_CSS = ROOT / "static" / "css" / "typography.css"
STYLES = ("InterVariable", "InterVariable-Italic")

# Google Fonts' "latin" subset plus the symbol blocks the interface strings
# and typical answers contain (→ ≈ ≥ ✓ CO₂ ₹ ™ ½ ▸). A page made only of
# these never fetches another file. Declared in the CSS as written here.
LATIN_RANGES = (
    (0x0000, 0x00FF), (0x0131, 0x0131), (0x0152, 0x0153), (0x02BB, 0x02BC),
    (0x02C6, 0x02C6), (0x02DA, 0x02DA), (0x02DC, 0x02DC), (0x0304, 0x0304),
    (0x0308, 0x0308), (0x0329, 0x0329), (0x2000, 0x206F), (0x2070, 0x209F),
    (0x20A0, 0x20CF), (0x2100, 0x214F), (0x2150, 0x218F), (0x2190, 0x21FF),
    (0x2200, 0x22FF), (0x25A0, 0x25FF), (0x2600, 0x26FF), (0x2700, 0x27BF),
    (0xFEFF, 0xFEFF), (0xFFFD, 0xFFFD),
)
# Letters of names and places in answers: Latin Extended-A/B, IPA schwa,
# combining marks, phonetic extensions, Latin Extended Additional
# (Vietnamese), Extended-C and -D. The CSS declares only the characters of
# these blocks the source has and LATIN_RANGES does not.
LATIN_EXT_BLOCKS = (
    (0x0100, 0x024F), (0x0259, 0x0259), (0x0300, 0x036F), (0x1D00, 0x1DBF),
    (0x1E00, 0x1EFF), (0x2C60, 0x2C7F), (0xA720, 0xA7FF),
)
PARTS = ("latin", "latin-ext", "rest")

UNICODE_RANGE = re.compile(
    r'src:\s*url\([\'"]?\.\./fonts/inter/(?P<file>[\w.-]+)[\'"]?\)[^;]*;[^}]*?unicode-range:\s*(?P<ranges>[^;]+);',
    re.S,
)
# "InterVariable-latin.46c8bad697dd.woff2": the part, then its content hash.
HASHED_FILE = re.compile(r"^(?P<part>[\w-]+)\.(?P<hash>[0-9a-f]{12})\.woff2$")


def content_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:12]


def hashed_name(part: str, data: bytes) -> str:
    """``InterVariable-latin.woff2`` and its bytes -> ``InterVariable-latin.<hash>.woff2``."""
    return f"{part.removesuffix('.woff2')}.{content_hash(data)}.woff2"


def part_name(file_name: str) -> str:
    """The part a hashed file stands for: ``InterVariable-latin.woff2``."""
    match = HASHED_FILE.match(file_name)
    return f"{match['part']}.woff2" if match else file_name


def _within(ranges, codepoint: int) -> bool:
    return any(start <= codepoint <= end for start, end in ranges)


def part_of(codepoint: int) -> str:
    if _within(LATIN_RANGES, codepoint):
        return "latin"
    if _within(LATIN_EXT_BLOCKS, codepoint):
        return "latin-ext"
    return "rest"


def to_ranges(codepoints) -> list[tuple[int, int]]:
    ranges: list[tuple[int, int]] = []
    for codepoint in sorted(codepoints):
        if ranges and codepoint == ranges[-1][1] + 1:
            ranges[-1] = (ranges[-1][0], codepoint)
        else:
            ranges.append((codepoint, codepoint))
    return ranges


def css_ranges(ranges) -> str:
    return ", ".join(f"U+{start:04X}" if start == end else f"U+{start:04X}-{end:04X}" for start, end in ranges)


def parse_css_ranges(text: str) -> set[int]:
    codepoints: set[int] = set()
    for part in text.split(","):
        start, _, end = part.strip().removeprefix("U+").partition("-")
        codepoints.update(range(int(start, 16), int(end or start, 16) + 1))
    return codepoints


def declared_ranges(css: str) -> dict[str, str]:
    """unicode-range per font part (unhashed name) as typography.css declares it."""
    return {part_name(match["file"]): " ".join(match["ranges"].split()) for match in UNICODE_RANGE.finditer(css)}


def declared_files(css: str) -> dict[str, str]:
    """The file typography.css loads for each part: part name -> hashed file name."""
    return {part_name(match["file"]): match["file"] for match in UNICODE_RANGE.finditer(css)}


def subset(source: Path, codepoints) -> tuple[bytes, set[int]]:
    from fontTools import subset as ft_subset
    from fontTools.ttLib import TTFont

    options = ft_subset.Options()
    options.layout_features = ["*"]  # tnum, case, calt arrows, cv/ss: all of them
    options.name_IDs = ["*"]
    options.flavor = "woff2"
    font = TTFont(source)
    subsetter = ft_subset.Subsetter(options)
    subsetter.populate(unicodes=codepoints)
    subsetter.subset(font)
    buffer = io.BytesIO()
    font.save(buffer)
    return buffer.getvalue(), set(font.getBestCmap())


def main(argv=None) -> int:
    from fontTools.ttLib import TTFont

    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("--check", action="store_true", help="verify only, write nothing")
    args = parser.parse_args(argv)

    css = TYPOGRAPHY_CSS.read_text(encoding="utf-8")
    declared = declared_ranges(css)
    files = declared_files(css)
    problems: list[str] = []
    for style in STYLES:
        source = FONT_DIR / f"{style}.woff2"
        source_cmap = set(TTFont(source).getBestCmap())
        covered: list[int] = []
        for part in PARTS:
            codepoints = {codepoint for codepoint in source_cmap if part_of(codepoint) == part}
            expected_css = css_ranges(LATIN_RANGES if part == "latin" else to_ranges(codepoints))
            name = f"{style}-{part}.woff2"
            if args.check:
                target = FONT_DIR / files.get(name, name)
                if not target.is_file():
                    problems.append(f"typography.css: {name} points at a missing file ({target.name})")
                    continue
                data = target.read_bytes()
                if target.name != hashed_name(name, data):
                    problems.append(f"{target.name}: the name must carry the content hash: {hashed_name(name, data)}")
                cmap = set(TTFont(io.BytesIO(data)).getBestCmap())
            else:
                data, cmap = subset(source, codepoints)
                target = FONT_DIR / hashed_name(name, data)
                for stale in FONT_DIR.glob(f"{style}-{part}.*.woff2"):
                    if stale != target and part_name(stale.name) == name:
                        stale.unlink()
                target.write_bytes(data)
                previous = files.get(name)
                if previous and previous != target.name:
                    css = css.replace(f"../fonts/inter/{previous}", f"../fonts/inter/{target.name}")
            if cmap != codepoints:
                problems.append(f"{name}: {len(codepoints ^ cmap)} characters differ from the intended set")
            covered.extend(cmap)
            if declared.get(name) != expected_css:
                problems.append(f"typography.css: unicode-range for {name} must be:\n    {expected_css}")
            print(f"{target.name:46} {len(cmap):5} characters {len(data) / 1024:7.1f} KB")
        if sorted(covered) != sorted(source_cmap):
            problems.append(f"{style}: the files do not cover the {len(source_cmap)} source characters exactly once")
    if not args.check:
        TYPOGRAPHY_CSS.write_bytes(css.encode("utf-8"))

    for problem in problems:
        print("FAIL", problem, file=sys.stderr)
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())

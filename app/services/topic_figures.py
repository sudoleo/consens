"""Figures drawn from a Topic's answer.

Models answer in text; people take in a chart faster. After a check, one
cheap Judge call (``consensus_engine.query_answer_figures``) fills up to two
of three fixed templates from the finished answer:

* ``lineup``   -- the members of one family or list, one row each, with where
  each stands (available / limited / announced / confirmed / claimed / not
  confirmed) and its date, if the answer gives one,
* ``timeline`` -- dated events (the steps of a rollout, announcements),
* ``numbers``  -- comparable numbers in one unit (prices, scores).

Rows with dates share one time axis, so a reader sees order, gaps and where
the check itself stands. ``status`` is the lineup as earlier runs stored it
(three standings, no dates) and is drawn the same way.

consens.io draws them itself (HTML/CSS, no image model, nothing copied from
another site), so they are sharp, follow the theme and are real text for
search engines. The rules that make them trustworthy live here, not in the
prompt:

* **Nothing new.** Every date, number and name must appear in the answer as
  written; an item that fails is dropped, a figure left with fewer than two
  items is dropped.
* **Disagreement shows.** An item the answer marks as disputed is drawn as
  disputed instead of being settled by the figure.
* **A figure, not a list.** Rows that all stand the same only repeat the
  list under them: with dates they are drawn as a timeline, without they are
  dropped.
* The answer itself is never changed; the figure sits under the heading it
  belongs to.
"""

from __future__ import annotations

import calendar
import logging
import math
import re
from datetime import date

from markupsafe import Markup, escape

from app.core.observability import safe_exception
from app.services.public_markdown import markdown_to_plaintext

MAX_FIGURES = 2
MIN_ITEMS = 2
MAX_ITEMS = 8
KINDS = ("timeline", "lineup", "status", "numbers")
# Kinds whose rows are things with a standing; "status" is the stored
# spelling of earlier runs.
LINEUP_KINDS = ("lineup", "status")
STATUS_LABELS = {
    "available": "Available",
    "limited": "Limited access",
    "announced": "Announced",
    "confirmed": "Confirmed",
    "claimed": "Claimed, not settled",
    "not_confirmed": "Not confirmed",
}
STATUSES = tuple(STATUS_LABELS)
_PLACEHOLDER = "TOPICFIGURESLOT{}"

_MONTHS = {
    name: index
    for index, names in enumerate((
        ("january", "jan"), ("february", "feb"), ("march", "mar"), ("april", "apr"),
        ("may",), ("june", "jun"), ("july", "jul"), ("august", "aug"),
        ("september", "sep", "sept"), ("october", "oct"), ("november", "nov"),
        ("december", "dec"),
    ), start=1)
    for name in names
}
_MONTH_RE = "(" + "|".join(sorted(_MONTHS, key=len, reverse=True)) + r")\.?"
_RANGE_RE = r"\s*(?:[-–—]|to)\s*"
_DATE_PATTERNS = (
    (re.compile(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b"), ("y", "m", "d"), "day"),
    # "October 7–8, 2026": a span of days, placed at its first day.
    (re.compile(_MONTH_RE + r"\s+(\d{1,2})" + _RANGE_RE + r"(\d{1,2}),?\s+(\d{4})\b", re.I),
     ("M", "d", "d2", "y"), "days"),
    (re.compile(r"\b(\d{1,2})" + _RANGE_RE + r"(\d{1,2})\s+" + _MONTH_RE + r",?\s+(\d{4})\b", re.I),
     ("d", "d2", "M", "y"), "days"),
    (re.compile(_MONTH_RE + r"\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})\b", re.I), ("M", "d", "y"), "day"),
    (re.compile(r"\b(\d{1,2})(?:st|nd|rd|th)?\s+" + _MONTH_RE + r",?\s+(\d{4})\b", re.I), ("d", "M", "y"), "day"),
    (re.compile(_MONTH_RE + r",?\s+(\d{4})\b", re.I), ("M", "y"), "month"),
    # "2026–2030": a span of years, placed at its first year.
    (re.compile(r"\b(19\d{2}|20\d{2})\s*(?:[-–—]|to|or)\s*(19\d{2}|20\d{2})\b"), ("y", "y2"), "years"),
    (re.compile(r"\b(19\d{2}|20\d{2})\b"), ("y",), "year"),
)
# A value that is only a year or a span of years ("2031", "around 2027",
# "2026–2030"): a point in time, never a quantity to draw as a bar.
_YEAR_VALUE_RE = re.compile(
    r"(?:~|around |about |circa |c\. |by )?(?:19|20)\d{2}(?:\s*(?:[-–—]|to)\s*(?:19|20)\d{2})?s?",
    re.IGNORECASE,
)
_TIME_UNIT_RE = re.compile(r"\b(?:years?|yr|dates?|when)\b")
_ANY_MONTH_RE = re.compile(r"\b" + _MONTH_RE + r"(?![a-z])", re.I)
_NUMBER_RE = re.compile(r"\d[\d,]*(?:\.\d+)?")


def _normalize(text) -> str:
    text = str(text or "").lower()
    text = (text.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
            .replace("–", "-").replace("—", "-").replace(" ", " "))
    return re.sub(r"\s+", " ", text).strip()


def _in(fragment, haystack: str) -> bool:
    needle = _normalize(fragment).strip(" .,:;!?\"'()")
    return bool(needle) and needle in haystack


def _numbers_known(text, haystack: str) -> bool:
    """Every number written in ``text`` also stands in the answer."""
    return all(_in(number, haystack) for number in _NUMBER_RE.findall(str(text or "")))


def _date_parts(text):
    """(date, precision, last day of a span or None) for a written date."""
    text = str(text or "")
    for pattern, order, precision in _DATE_PATTERNS:
        if precision == "year" and _ANY_MONTH_RE.search(text):
            # A month is named but no pattern read it: reading only the year
            # would put the event at January 1st.
            return None
        match = pattern.search(text)
        if not match:
            continue
        parts = dict(zip(order, match.groups()))
        try:
            year = int(parts["y"])
            month = _MONTHS[parts["M"].lower().rstrip(".")] if "M" in parts else int(parts.get("m") or 1)
            day = int(parts.get("d") or 1)
            last = int(parts["d2"]) if parts.get("d2") else int(parts["y2"]) if parts.get("y2") else None
            return date(year, month, day), precision, last
        except (KeyError, ValueError):
            continue
    return None


def parse_date(text):
    """(date, precision) for a date as answers write it, else None."""
    parts = _date_parts(text)
    return (parts[0], parts[1]) if parts else None


def _number(value):
    match = _NUMBER_RE.search(str(value or ""))
    if not match:
        return None
    try:
        return float(match.group(0).replace(",", ""))
    except ValueError:
        return None


def _headings(answer_md: str) -> list[str]:
    headings = []
    for line in str(answer_md or "").splitlines():
        match = re.match(r"^\s{0,3}#{1,6}\s+(.*?)\s*#*\s*$", line)
        if match:
            headings.append(markdown_to_plaintext(match.group(1)))
    return headings


def _short(text, limit: int) -> str:
    text = " ".join(str(text or "").split())
    return text if len(text) <= limit else text[: limit - 1].rsplit(" ", 1)[0] + "…"


def _unit_is_time(unit) -> bool:
    """No unit, or one that says the value is a year ("year", "release
    date"); "Elo", "tokens" or "per year" make 2048 a quantity."""
    unit = _normalize(unit)
    return not unit or (bool(_TIME_UNIT_RE.search(unit)) and "per " not in unit)


def years_as_timeline(figure: dict) -> dict:
    """A numbers figure whose values are all years is a timeline: 2026, 2031
    and 2047 drawn as bars are three bars of almost the same length.
    Only when the unit allows it: a
    rating of 2048 stays a number."""
    items = figure.get("items")
    if (figure.get("kind") != "numbers" or not isinstance(items, list) or not items
            or not all(isinstance(item, dict) for item in items)
            or not all(_YEAR_VALUE_RE.fullmatch(str(item.get("value") or "").strip())
                       and _unit_is_time(item.get("unit")) for item in items)):
        return figure
    return {**figure, "kind": "timeline", "items": [
        {**item, "date": str(item.get("value") or "").strip()} for item in items
    ]}


def clean_figures(raw, answer_md: str) -> list[dict]:
    """Keep only what the answer states; anything malformed is dropped."""
    if not isinstance(raw, dict):
        return []
    haystack = _normalize(markdown_to_plaintext(answer_md))
    headings = _headings(answer_md)
    raw_figures = raw.get("figures")
    if not isinstance(raw_figures, list):
        return []
    figures = []
    for figure in raw_figures:
        if (not isinstance(figure, dict) or figure.get("kind") not in KINDS
                or not isinstance(figure.get("items"), list)):
            continue
        figure = years_as_timeline(figure)
        kind = figure["kind"]
        items = []
        for item in figure["items"][:MAX_ITEMS]:
            if not isinstance(item, dict):
                continue
            label = _short(item.get("label"), 80)
            note = _short(item.get("note"), 110)
            if not label or not _numbers_known(label, haystack) or not _numbers_known(note, haystack):
                continue
            entry = {"label": label, "note": note, "disputed": item.get("disputed") is True}
            if kind == "timeline":
                written = _written_date(item.get("date"), haystack)
                if not written:
                    continue
                entry.update(written)
            elif kind in LINEUP_KINDS:
                # A lineup lists names; "68% on CWE-Bench" or a price is a
                # number and belongs in a numbers figure, if anywhere.
                if not _in(label, haystack) or re.search(r"[%$€£]", label):
                    continue
                status = item.get("status")
                entry["status"] = status if isinstance(status, str) and status in STATUSES else ""
                written = _written_date(item.get("date"), haystack)
                if written:
                    entry.update(written)
                elif not entry["status"]:
                    continue
            else:
                value = _short(item.get("value"), 24)
                number = _number(value)
                if number is None or not _in(value, haystack):
                    continue
                entry.update({"value": value, "number": number, "unit": _short(item.get("unit"), 60)})
            items.append(entry)
        if kind in LINEUP_KINDS:
            # A standing every row shares tells them apart no better than
            # none: the rows are then dated things, a timeline, and the
            # undated ones have nothing left to say.
            kind = "lineup" if len({entry["status"] for entry in items}) > 1 else "timeline"
        if kind == "timeline":
            items = [
                {key: value for key, value in entry.items() if key != "status"}
                for entry in items if entry.get("sort")
            ]
            items.sort(key=lambda entry: entry["sort"])
        elif kind == "lineup":
            # Dated rows in order, the rest after them as the answer lists them.
            items.sort(key=lambda entry: (not entry.get("sort"), entry.get("sort", "")))
        _quiet_notes(items)
        if len(items) < MIN_ITEMS:
            continue
        title = _short(figure.get("title"), 70)
        if not _numbers_known(title, haystack):
            title = ""
        wanted = _normalize(markdown_to_plaintext(figure.get("after_heading")))
        heading = next((text for text in headings if wanted and _normalize(text) == wanted), "")
        figures.append({"kind": kind, "title": title, "after_heading": heading, "items": items})
    # One figure per template: two status boards on one page split one
    # picture in two. The fuller one stays, the first on a tie.
    best = {}
    for figure in figures:
        if len(figure["items"]) > len(best.get(figure["kind"], {}).get("items", [])):
            best[figure["kind"]] = figure
    return [figure for figure in figures if best.get(figure["kind"]) is figure][:MAX_FIGURES]


def _written_date(value, haystack: str) -> dict | None:
    """The fields of a date the answer states, or None."""
    written = _short(value, 40)
    parsed = parse_date(written)
    if not parsed or not _in(written, haystack):
        return None
    return {"date": written, "sort": parsed[0].isoformat(), "precision": parsed[1]}


def _plain_list(items) -> bool:
    """Every row stands the same and none has a date: the figure would only
    repeat the list in the text under it."""
    return (len({entry.get("status") for entry in items}) == 1
            and not any(entry.get("date") for entry in items))


_FIRST_PERSON_RE = re.compile(r"\b(?:i|i'm|i've|my|we|our|me)\b", re.IGNORECASE)


def _quiet_notes(items) -> None:
    """Notes explain an item. One in the model's own voice ("I did not find
    ...") or repeated on several items explains nothing; it is dropped."""
    counts = {}
    for entry in items:
        key = _normalize(entry["note"])
        counts[key] = counts.get(key, 0) + 1
    for entry in items:
        note = _normalize(entry["note"])
        echoes = note in _normalize(entry["label"])
        if note and (counts[note] > 1 or echoes or _FIRST_PERSON_RE.search(note)):
            entry["note"] = ""


def build(question: str, answer_md: str, *, query=None, keys=None, engine: str = "OpenAI") -> list[dict]:
    """Figures for one answer; ``[]`` when none helps or anything fails.

    A failure here must never cost the check it belongs to.
    """
    if query is None:
        from app.services import watch_images

        if not watch_images.background_enabled():
            return []
        from app.services.llm import provider_transport
        from app.services.llm.consensus_engine import query_answer_figures

        query = query_answer_figures
        keys = keys if keys is not None else provider_transport.developer_keys()
    try:
        raw = query(question, answer_md, keys or {}, engine)
        return clean_figures(raw, answer_md)
    except Exception as exc:
        logging.warning("Topic figures skipped category=%s", safe_exception(exc))
        return []


# Fields the drawing reads from every stored item, per kind (clean_figures
# writes them; a run imported by hand may not have them).
_ITEM_FIELDS = {
    "timeline": {"date": str},
    "lineup": {"status": str},
    "status": {"status": str},
    "numbers": {"value": str, "number": (int, float), "unit": str},
}


def _stored_item(kind: str, item):
    if not isinstance(item, dict) or not isinstance(item.get("label"), str) or not item["label"]:
        return None
    if any(not isinstance(item.get(name), types) for name, types in _ITEM_FIELDS[kind].items()):
        return None
    if kind == "numbers" and isinstance(item["number"], bool):
        return None
    note = item.get("note")
    entry = {**item, "note": note if isinstance(note, str) else "", "disputed": item.get("disputed") is True}
    if kind in LINEUP_KINDS:
        entry["date"] = item["date"] if isinstance(item.get("date"), str) else ""
        # A row says where a thing stands, when, or both.
        if item["status"] not in STATUSES + ("",) or not (item["status"] or _date_parts(entry["date"])):
            return None
    return entry


def stored_figures(value) -> list[dict]:
    """Figures as stored on a run, structurally checked (older runs have none).

    Items the drawing could not read are dropped, so a bad stored run costs
    its figure, never the public page."""
    if not isinstance(value, list):
        return []
    figures = []
    for figure in value[:MAX_FIGURES]:
        if not isinstance(figure, dict) or figure.get("kind") not in KINDS or not isinstance(figure.get("items"), list):
            continue
        items = [entry for entry in (_stored_item(figure["kind"], item) for item in figure["items"]) if entry]
        if len(items) < MIN_ITEMS or (figure["kind"] in LINEUP_KINDS and _plain_list(items)):
            continue
        title, heading = figure.get("title"), figure.get("after_heading")
        figures.append({**figure, "items": items,
                        "title": title if isinstance(title, str) else "",
                        "after_heading": heading if isinstance(heading, str) else ""})
    return figures


# ----------------------------------------------------------------------------
# Drawing
# ----------------------------------------------------------------------------

_CHECK = (
    '<circle cx="8" cy="8" r="8" fill="currentColor"/><path d="M4.6 8.2l2.2 2.2 4.6-4.7" '
    'fill="none" stroke="var(--af-on-glyph)" stroke-width="1.8" stroke-linecap="round" '
    'stroke-linejoin="round"/>'
)
_HALF = (
    '<circle cx="8" cy="8" r="6.5" fill="none" stroke="currentColor" stroke-width="1.6"/>'
    '<path d="M8 1.5a6.5 6.5 0 0 1 0 13z" fill="currentColor"/>'
)
_RING_DOT = (
    '<circle cx="8" cy="8" r="6.5" fill="none" stroke="currentColor" stroke-width="1.6"/>'
    '<circle cx="8" cy="8" r="2.6" fill="currentColor"/>'
)
_RING_DASH = (
    '<circle cx="8" cy="8" r="6.5" fill="none" stroke="currentColor" stroke-width="1.6"/>'
    '<path d="M5 8h6" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>'
)
# Four shapes for six standings: there (check), partly (half), named only
# (ring with a dot), nothing official (ring with a dash). The word next to the
# shape says which of the six it is.
_GLYPH_SHAPES = {
    "available": _CHECK, "confirmed": _CHECK, "limited": _HALF, "claimed": _HALF,
    "announced": _RING_DOT, "not_confirmed": _RING_DASH,
}
_GLYPHS = {
    status: f'<svg class="af-glyph is-{status.replace("_", "-")}" viewBox="0 0 16 16" '
            f'aria-hidden="true">{shape}</svg>'
    for status, shape in _GLYPH_SHAPES.items()
}

# A mark narrower than this share of the axis is drawn as a dot at its middle;
# a wider one as a bar from its first to its last day.
_DOT_BELOW_PERCENT = 3.5
_AXIS_PAD = 0.045
_MAX_TICKS = 7


def _date_label(entry: dict) -> str:
    """The date the way the page writes dates ("Sep 30, 2026"), as precise as
    the answer was; the answer's own spelling was what got checked."""
    parts = _date_parts(entry.get("date"))
    if not parts:
        return entry.get("date") or ""
    day, precision, last = parts
    if precision == "year":
        return str(day.year)
    if precision == "years" and last:
        return f"{day.year}–{last}"
    if precision == "month":
        return f"{day:%b} {day.year}"
    if precision == "days" and last:
        return f"{day:%b} {day.day}–{last}, {day.year}"
    return f"{day:%b} {day.day}, {day.year}"


def _day_span(written) -> tuple[int, int] | None:
    """First and last day (ordinals) a written date covers: "October 2026" is
    a month, "2030–2033" four years. Drawn that wide, so a figure never claims
    more precision than the answer."""
    parts = _date_parts(written)
    if not parts:
        return None
    day, precision, last = parts
    try:
        if precision == "days" and last:
            first, final = day, day.replace(day=last)
        elif precision == "month":
            first = day.replace(day=1)
            final = day.replace(day=calendar.monthrange(day.year, day.month)[1])
        elif precision == "years" and last:
            first, final = date(day.year, 1, 1), date(max(last, day.year), 12, 31)
        elif precision == "year":
            first, final = date(day.year, 1, 1), date(day.year, 12, 31)
        else:
            first = final = day
    except ValueError:
        first = final = day
    return first.toordinal(), max(final.toordinal(), first.toordinal())


def _tick_unit(days: float) -> str:
    """What the axis counts in: weeks for up to three weeks, half months up
    to six, months up to about two years, years beyond."""
    return "week" if days <= 21 else "half" if days <= 45 else "month" if days <= 800 else "year"


_MONTH_DAYS = {"week": (1, 8, 15, 22), "half": (1, 15), "month": (1,)}


def _axis(spans, as_of: date | None):
    """The shared time axis for dated rows: (start, end, marker, unit).

    The check's own day joins the axis when it lies inside the dates or not
    far behind the last one: then the reader sees how long ago that was.
    A forecast decades ahead is not stretched back to today. The axis opens
    at the round date before the first mark, so no mark stands left of the
    first label."""
    first = min(lo for lo, _hi in spans)
    last = max(hi for _lo, hi in spans)
    marker = None
    if as_of is not None:
        today = as_of.toordinal()
        if first <= today <= last:
            marker = today
        elif today > last and today - last <= max(1.5 * (last - first), 45):
            marker = last = today
    if last == first:
        first, last = first - 15, last + 15
    unit = _tick_unit(last - first)
    opening = date.fromordinal(first)
    if unit == "year":
        opening = date(opening.year, 1, 1)
    else:
        opening = opening.replace(day=max(day for day in _MONTH_DAYS[unit] if day <= opening.day))
    first = opening.toordinal()
    pad = max(1.0, _AXIS_PAD * (last - first))
    return first - pad, last + pad, marker, unit


def _ticks(start: float, end: float, unit: str) -> list[tuple[float, str]]:
    """Round dates along the axis, at most a handful of labels."""
    first, last = date.fromordinal(math.ceil(start)), date.fromordinal(math.floor(end))
    ticks = []
    if unit in ("week", "half"):
        day = first
        while day <= last:
            if day.day in _MONTH_DAYS[unit]:
                ticks.append((day.toordinal(), f"{day:%b} {day.day}"))
            day = date.fromordinal(day.toordinal() + 1)
        return ticks
    if unit == "month":
        months = []
        year, month = first.year, first.month
        if first.day > 1:
            year, month = (year + 1, 1) if month == 12 else (year, month + 1)
        while date(year, month, 1) <= last:
            months.append(date(year, month, 1))
            year, month = (year + 1, 1) if month == 12 else (year, month + 1)
        step = max(1, math.ceil(len(months) / _MAX_TICKS))
        for day in months:
            if (day.year * 12 + day.month - 1) % step:
                continue
            # The year only at its turn: every row says its own, and a first
            # label carrying one ran into the next on a short axis.
            label = f"{day:%b} {day.year}" if day.month == 1 else f"{day:%b}"
            ticks.append((day.toordinal(), label))
        return ticks
    years = [year for year in range(first.year, last.year + 1) if first <= date(year, 1, 1) <= last]
    step = next((size for size in (1, 2, 5, 10, 20, 25, 50) if len(years) / size <= _MAX_TICKS), 100)
    return [(date(year, 1, 1).toordinal(), str(year)) for year in years if year % step == 0]


def _edge(position: float) -> str:
    """A label near an edge of the axis hangs inward instead of over it."""
    return " is-start" if position < 12 else " is-end" if position > 88 else ""


def _chart(figure: dict, as_of: date | None = None) -> str:
    """Rows on one grid: standing, name, the place on a shared time axis, date.

    One drawing for timelines and lineups. Order and place come from the
    written dates, not from what an older version of this module stored: a
    reading fixed later fixes old figures too."""
    lineup = figure["kind"] in LINEUP_KINDS
    rows = []
    for entry in figure["items"]:
        span = _day_span(entry.get("date"))
        if not span and not lineup:
            continue
        rows.append({**entry, "span": span})
    if not rows:
        return ""
    # Dated rows in order (on the same day a single date before a span that
    # starts there), undated ones after them as stored.
    rows.sort(key=lambda row: (row["span"] is None, row["span"] or (0, 0)))
    spans = [row["span"] for row in rows if row["span"]]
    has_state = lineup and any(row.get("status") for row in rows)
    has_when = bool(spans)
    has_axis = len(spans) >= 2
    columns = ("s" if has_state else "") + "n" + ("p" if has_axis else "") + ("w" if has_when else "")

    def at(day: float) -> float:
        return 100 * (day - start) / (end - start)

    out = [f'<div class="af-chart is-{columns}" role="list" style="--af-rows:{len(rows) + 2}">']
    if has_axis:
        start, end, marker, unit = _axis(spans, as_of)
        ticks = [(at(day), label) for day, label in _ticks(start, end, unit)]
        grid = "".join(f'<i style="left:{left:.1f}%"></i>' for left, _label in ticks)
        if marker is not None:
            grid += f'<i class="af-asof" style="left:{at(marker):.1f}%"></i>'
        out.append(f'<div class="af-grid" aria-hidden="true">{grid}</div>')
        labels = "".join(
            f'<span class="af-tick{_edge(left)}" style="left:{left:.1f}%">{escape(label)}</span>'
            for left, label in ticks
        )
        out.append(f'<div class="af-scale" aria-hidden="true"><span class="af-plot">{labels}</span></div>')
    for index, row in enumerate(rows):
        cells = []
        if has_state:
            status = row.get("status") if row.get("status") in STATUS_LABELS else ""
            cells.append(
                f'<span class="af-state">{_GLYPHS[status]}{escape(STATUS_LABELS[status])}</span>'
                if status else '<span class="af-state"></span>'
            )
        cells.append(
            f'<span class="af-name"><span class="af-label">{escape(row["label"])}</span>'
            + (f'<span class="af-note">{escape(row["note"])}</span>' if row["note"] else "")
            + "</span>"
        )
        if has_axis:
            mark = ""
            if row["span"]:
                left, right = at(row["span"][0]), at(row["span"][1])
                mark = (
                    f'<i class="af-mark" style="left:{(left + right) / 2:.1f}%"></i>'
                    if right - left < _DOT_BELOW_PERCENT
                    else f'<i class="af-range" style="left:{left:.1f}%;width:{right - left:.1f}%"></i>'
                )
            cells.append(f'<span class="af-plot" aria-hidden="true">{mark}</span>')
        if has_when:
            cells.append(
                f'<time class="af-when" datetime="{date.fromordinal(row["span"][0]).isoformat()}">'
                f"{escape(_date_label(row))}</time>" if row["span"] else '<span class="af-when"></span>'
            )
        out.append(
            f'<div class="af-line{" is-disputed" if row["disputed"] else ""}" role="listitem" '
            f'style="grid-row:{index + 2}">{"".join(cells)}</div>'
        )
    if has_axis and marker is not None:
        left = at(marker)
        out.append(
            f'<div class="af-foot" aria-hidden="true" style="grid-row:{len(rows) + 2}"><span class="af-plot">'
            f'<span class="af-asof-label{" is-start" if left < 25 else ""}" style="left:{left:.1f}%">'
            f"checked {as_of:%b} {as_of.day}</span></span></div>"
        )
    out.append("</div>")
    return "".join(out)


def _numbers(figure: dict) -> str:
    items = figure["items"]
    units = {_normalize(entry.get("unit")) for entry in items}
    top = max(entry["number"] for entry in items)
    bars = len(units) == 1 and top > 0
    rows = []
    for entry in items:
        width = 100 * entry["number"] / top if bars else 0
        bar = (
            f'<span class="af-bar" aria-hidden="true"><i style="width:{max(width, 1.5):.1f}%"></i></span>'
            if bars else ""
        )
        rows.append(
            f'<li class="af-row{" is-disputed" if entry["disputed"] else ""}">'
            f'<span class="af-label">{escape(entry["label"])}'
            + (f'<span class="af-note">{escape(entry["note"])}</span>' if entry["note"] else "")
            + f"</span>{bar}"
            f'<span class="af-value">{escape(entry["value"])}</span></li>'
        )
    unit = next(iter(units)) if bars and units != {""} else ""
    unit_line = f'<p class="af-unit">{escape(items[0]["unit"])}</p>' if unit else ""
    return f'{unit_line}<ul class="af-rows{" has-bars" if bars else ""}">{"".join(rows)}</ul>'


_KIND_HEADS = {
    "timeline": ("Timeline", (
        '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" '
        'stroke-linecap="round" aria-hidden="true"><path d="M1.5 8h13"/>'
        '<circle cx="4" cy="8" r="1.8" fill="currentColor"/><circle cx="12" cy="8" r="1.8" fill="currentColor"/></svg>'
    )),
    "lineup": ("Overview", (
        '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" '
        'stroke-linecap="round" aria-hidden="true"><path d="M6.5 4h7M6.5 8h7M6.5 12h7"/>'
        '<circle cx="3" cy="4" r="1.2" fill="currentColor"/><circle cx="3" cy="8" r="1.2" fill="currentColor"/>'
        '<circle cx="3" cy="12" r="1.2" fill="currentColor"/></svg>'
    )),
    "numbers": ("In numbers", (
        '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" '
        'stroke-linecap="round" aria-hidden="true"><path d="M2 4h8M2 8h12M2 12h5"/></svg>'
    )),
}


def figure_html(figure: dict, *, answered_on: str = "", as_of: date | None = None) -> Markup:
    """One figure as safe HTML; every text from the answer is escaped.

    A small head (symbol + kind) marks it as a figure, not more text.
    ``as_of`` is the day of the check the answer comes from; a time axis
    marks it."""
    figure = years_as_timeline(figure)
    kind = "lineup" if figure["kind"] in LINEUP_KINDS else figure["kind"]
    body = _numbers(figure) if kind == "numbers" else _chart(figure, as_of)
    disputed = any(entry.get("disputed") for entry in figure["items"])
    caption = "Drawn by consens.io from this answer"
    caption += f" of {answered_on}" if answered_on else ""
    caption += ". Every date, number and name is taken from it."
    if disputed:
        caption += " Dashed: the sources or models disagree."
    kind_label, kind_icon = _KIND_HEADS[kind]
    head = f'<p class="af-kind">{kind_icon}{escape(kind_label)}</p>'
    title = f'<p class="af-title">{escape(figure["title"])}</p>' if figure.get("title") else ""
    return Markup(
        f'<figure class="af af-{kind}">{head}{title}{body}'
        f'<figcaption class="af-cap">{escape(caption)}</figcaption></figure>'
    )


def place(answer_md: str, figures) -> tuple[str, list[dict]]:
    """Mark where each figure goes: under its heading, else after the opening.

    Returns the markdown with one placeholder paragraph per figure; ``fill``
    swaps the rendered placeholders for the figures.
    """
    lines = str(answer_md or "").split("\n")
    placed = []
    slots_after: dict[int, list[str]] = {}
    for index, figure in enumerate(figures or []):
        target = None
        if figure.get("after_heading"):
            wanted = _normalize(figure["after_heading"])
            for number, line in enumerate(lines):
                match = re.match(r"^\s{0,3}#{1,6}\s+(.*?)\s*#*\s*$", line)
                if match and _normalize(markdown_to_plaintext(match.group(1))) == wanted:
                    target = number
                    break
            # A figure is a way in. Under a closing summary it would come
            # after the text it saves the reader; then it moves up front.
            if target is not None and target > len(lines) * 0.6:
                target = None
        if target is None:
            # After the first paragraph: the opening states the answer, the
            # figure shows it.
            target = next((n for n, line in enumerate(lines) if line.strip() and n + 1 < len(lines)
                           and not lines[n + 1].strip()), len(lines) - 1)
        slots_after.setdefault(target, []).append(_PLACEHOLDER.format(index))
        placed.append(figure)
    out = []
    for number, line in enumerate(lines):
        out.append(line)
        for slot in slots_after.get(number, []):
            out.extend(["", slot, ""])
    return "\n".join(out), placed


def fill(answer_html: str, figures, *, answered_on: str = "", as_of: date | None = None) -> Markup:
    html = str(answer_html or "")
    for index, figure in enumerate(figures or []):
        slot = _PLACEHOLDER.format(index)
        drawn = figure_html(figure, answered_on=answered_on, as_of=as_of)
        html = html.replace(f"<p>{slot}</p>", str(drawn))
        html = html.replace(slot, "")
    return Markup(html)

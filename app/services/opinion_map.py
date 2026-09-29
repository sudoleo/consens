"""Compact, text-minimised position maps for Consensus Watch history.

The map is derived from the already structured Differences result.  It keeps
short stance labels and provider membership, never complete model answers.
"""

from __future__ import annotations

import re

import app.core.config as cfg


SCHEMA_VERSION = 1
MAX_DIMENSIONS = 4
MAX_POSITIONS = 3
PROVIDERS = tuple(cfg.PROVIDER_LABEL_BY_ID.values())
# Familien-ID und Anzeigename gelten immer; dazu die gaengigen Zweitnamen.
_PROVIDER_ALIASES = {
    **{provider: label for provider, label in cfg.PROVIDER_LABEL_BY_ID.items()},
    **{label.lower(): label for label in PROVIDERS},
    "chatgpt": "OpenAI",
    "claude": "Anthropic",
    "google": "Gemini",
    "xai": "Grok",
}
_WORD_RE = re.compile(r"[a-z0-9]+", re.IGNORECASE)


def _clip(value, limit: int) -> str:
    return " ".join(str(value or "").split()).strip()[:limit]


def _provider(value) -> str:
    raw = _clip(value, 40)
    return _PROVIDER_ALIASES.get(raw.lower(), raw if raw in PROVIDERS else "")


def _tokens(value) -> set[str]:
    return {
        token for token in _WORD_RE.findall(str(value or "").lower())
        if len(token) > 2
    }


def similarity(left, right) -> float:
    """Token-overlap similarity of two generated labels (0.0 – 1.0).

    Public because the Claim Ledger chains the same comparison across every
    stored run instead of only against the direct predecessor.
    """
    a, b = _tokens(left), _tokens(right)
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


# Lexical threshold below which a provider's stance on a matched dimension
# counts as moved. Word overlap alone is only a fallback: see stance_changed.
STANCE_MOVED_BELOW = 0.24

_CURRENCY_SYMBOLS = {"$": "usd", "€": "eur", "£": "gbp", "¥": "jpy"}
_UNIT_ALIASES = {
    "%": "%", "percent": "%", "prozent": "%", "pct": "%", "‰": "‰",
    "eur": "eur", "euro": "eur", "euros": "eur", "usd": "usd", "dollar": "usd",
    "dollars": "usd", "gbp": "gbp", "pound": "gbp", "pounds": "gbp", "chf": "chf",
    "cent": "cent", "cents": "cent", "ct": "cent",
    "k": "thousand", "thousand": "thousand", "tsd": "thousand", "tausend": "thousand",
    "m": "million", "mio": "million", "million": "million", "millions": "million",
    "millionen": "million", "bn": "billion", "billion": "billion", "billions": "billion",
    "mrd": "billion", "milliarden": "billion", "trillion": "trillion",
    "x": "x", "times": "x", "fach": "x",
    "second": "s", "seconds": "s", "sec": "s", "s": "s", "sekunden": "s",
    "minute": "min", "minutes": "min", "min": "min", "minuten": "min",
    "hour": "h", "hours": "h", "h": "h", "stunde": "h", "stunden": "h",
    "day": "day", "days": "day", "tag": "day", "tage": "day", "tagen": "day",
    "week": "week", "weeks": "week", "woche": "week", "wochen": "week",
    "month": "month", "months": "month", "monat": "month", "monate": "month",
    "monaten": "month", "year": "year", "years": "year", "jahr": "year",
    "jahre": "year", "jahren": "year",
    "mm": "mm", "cm": "cm", "km": "km", "mg": "mg", "g": "g", "kg": "kg",
    "t": "t", "l": "l", "ml": "ml", "kb": "kb", "mb": "mb", "gb": "gb", "tb": "tb",
    "kw": "kw", "kwh": "kwh", "mw": "mw", "gw": "gw", "ghz": "ghz", "mhz": "mhz",
}
_NUMBER_RE = re.compile(
    r"(?P<pre>[$€£¥])?\s*(?P<sign>[-+−–])?\s*(?P<pre2>[$€£¥])?"
    r"(?P<num>\d+(?:[.,'  ]\d+)*)"
    r"(?:\s*(?P<unit>%|‰|[$€£¥]|[^\W\d_]+))?"
)
_NEGATIONS = frozenset({
    "not", "no", "never", "none", "nothing", "neither", "nor", "without", "cannot",
    "nicht", "kein", "keine", "keinen", "keinem", "keiner", "keines", "nie",
    "niemals", "ohne", "nichts", "weder",
})
_CONDITIONS = frozenset({
    "if", "unless", "only", "except", "until", "provided", "assuming", "depends",
    "depending", "conditional", "wenn", "falls", "nur", "außer", "ausser",
    "sofern", "bis", "solange", "abhängig", "vorausgesetzt",
})
# "may" and "march" are also a modal verb / a verb; they only count as a month
# next to a day or year number (see _months).
_AMBIGUOUS_MONTHS = frozenset({"may", "march"})
_MONTHS = frozenset({
    "january", "february", "march", "april", "may", "june", "july", "august",
    "september", "october", "november", "december", "januar", "februar", "märz",
    "maerz", "juni", "juli", "oktober", "dezember",
})
_MARKER_WORD_RE = re.compile(r"[^\W\d_]+(?:['’][^\W\d_]+)?")


def _canonical_number(raw: str) -> str:
    """Formatting-independent value: "1,000" == "1000" == "1.000,0" == "1000.0"."""
    groups = re.split(r"[.,'  ]", raw)
    if len(groups) > 1 and all(len(group) == 3 for group in groups[1:]):
        integer, fraction = "".join(groups), ""
    elif len(groups) > 1:
        integer, fraction = "".join(groups[:-1]), groups[-1]
    else:
        integer, fraction = raw, ""
    integer = integer.lstrip("0") or "0"
    fraction = fraction.rstrip("0")
    return integer + ("." + fraction if fraction else "")


def _months(text: str) -> tuple:
    found = set()
    tokens = re.findall(r"[^\W_]+", text.lower())
    for index, word in enumerate(tokens):
        if word not in _MONTHS:
            continue
        if word in _AMBIGUOUS_MONTHS:
            neighbours = tokens[max(0, index - 1):index] + tokens[index + 1:index + 2]
            if not any(neighbour.isdigit() for neighbour in neighbours):
                continue
        found.add(word)
    return tuple(sorted(found))


def _numbers(text: str) -> tuple:
    found = []
    for match in _NUMBER_RE.finditer(text):
        number = _canonical_number(match.group("num"))
        raw_sign = match.group("sign")
        # "2025-2026" is a range, not a negative number.
        sign = "-" if raw_sign in {"-", "−", "–"} and not (
            match.start("sign") > 0 and text[match.start("sign") - 1].isalnum()
        ) else ""
        currency = match.group("pre") or match.group("pre2") or ""
        unit = (match.group("unit") or "").lower()
        unit = _CURRENCY_SYMBOLS.get(unit) or _UNIT_ALIASES.get(unit, "")
        found.append((sign, number, _CURRENCY_SYMBOLS.get(currency, "") or unit))
    return tuple(sorted(found))


def significant_markers(value) -> tuple:
    """Meaning-bearing details that word overlap must never average away.

    Numbers (with sign and unit/currency), the count of negations, conditional
    or restricting qualifiers and month names. Two stances whose markers differ
    make a different statement even when almost every word is shared.
    """
    text = " ".join(str(value or "").split())
    words = [word.lower().replace("’", "'") for word in _MARKER_WORD_RE.findall(text)]
    negations = sum(1 for word in words if word in _NEGATIONS or word.endswith("n't"))
    conditions = tuple(sorted({word for word in words if word in _CONDITIONS}))
    months = _months(text)
    return _numbers(text), negations, conditions, months


def stance_changed(previous, current, *, lexical: bool = True) -> bool:
    """Whether one provider's stance moved between two runs.

    A change in any significant marker always counts. ``lexical`` adds the
    conservative word-overlap fallback for rewrites without such markers.
    """
    if significant_markers(previous) != significant_markers(current):
        return True
    return lexical and similarity(previous, current) < STANCE_MOVED_BELOW


def _dimensions(differences_data: dict, *, allow_single=False) -> list[dict]:
    raw_differences = differences_data.get("differences")
    if not isinstance(raw_differences, list):
        return []
    dimensions = []
    for raw in raw_differences[:MAX_DIMENSIONS]:
        if not isinstance(raw, dict):
            continue
        label = _clip(raw.get("claim"), 140)
        raw_positions = raw.get("positions")
        if not label or not isinstance(raw_positions, list):
            continue
        positions = []
        for position in raw_positions[:MAX_POSITIONS]:
            if not isinstance(position, dict):
                continue
            stance = _clip(position.get("stance"), 180)
            models = []
            for model in position.get("models") or []:
                name = _provider(model)
                if name and name not in models:
                    models.append(name)
            if stance and models:
                positions.append({"stance": stance, "models": models})
        if len(positions) >= (1 if allow_single else 2):
            dimension = {
                "label": label,
                "type": raw.get("type") if raw.get("type") in {"contradiction", "claim"} else "emphasis",
                "positions": positions,
            }
            # Topics stamp a stable identity on a claim so the Claim Ledger can
            # follow it across rewordings. Watches never set one.
            key = _clip(raw.get("key"), 40)
            if key:
                dimension["key"] = key
            dimensions.append(dimension)
    return dimensions


def _claim_dimensions(differences_data: dict) -> list[dict]:
    """Fallback map for unanimous runs using structured claim support."""
    raw_claims = differences_data.get("claims")
    if not isinstance(raw_claims, list):
        return []
    dimensions = []
    for raw in raw_claims:
        if len(dimensions) >= MAX_DIMENSIONS:
            break
        if not isinstance(raw, dict):
            continue
        # Seit dem Coverage-Judge stehen auch duenn belegte Saetze in der
        # Claim-Liste. Fuer die Opinion-Map (und damit fuer das Claim Ledger
        # der Topic-Seiten) taugen sie nicht: eine einzelne Stimme ist keine
        # Position, die man ueber Laeufe hinweg verfolgen koennte.
        if raw.get("coverage") == "thin":
            continue
        if len(raw.get("agree") or []) + len(raw.get("dissent") or []) < 2:
            continue
        anchor = _clip(raw.get("anchor"), 180)
        if not anchor:
            continue
        agree = []
        for model in raw.get("agree") or []:
            provider = _provider(model)
            if provider and provider not in agree:
                agree.append(provider)
        positions = []
        if agree:
            positions.append({"stance": anchor, "models": agree})
        dissent_groups = {}
        for item in raw.get("dissent") or []:
            if not isinstance(item, dict):
                continue
            provider = _provider(item.get("model"))
            if not provider:
                continue
            stance = _clip(item.get("quote"), 180) or "Does not support this claim"
            dissent_groups.setdefault(stance, []).append(provider)
        positions.extend(
            {"stance": stance, "models": models}
            for stance, models in list(dissent_groups.items())[:MAX_POSITIONS - len(positions)]
        )
        if positions:
            dimensions.append({"label": anchor, "type": "claim", "positions": positions})
    return dimensions


def sanitize_opinion_map(value) -> dict | None:
    """Whitelist a persisted map before it reaches a public response."""
    if not isinstance(value, dict):
        return None
    dimensions = []
    raw_dimensions = value.get("dimensions")
    # _dimensions expects the same label/positions shape, with claim instead of
    # label. Convert explicitly to keep one validation path.
    if isinstance(raw_dimensions, list):
        converted = []
        for dimension in raw_dimensions[:MAX_DIMENSIONS]:
            if isinstance(dimension, dict):
                converted.append({
                    "claim": dimension.get("label"),
                    "type": dimension.get("type"),
                    "positions": dimension.get("positions"),
                    "key": dimension.get("key"),
                })
        dimensions = _dimensions({"differences": converted}, allow_single=True)
    models = []
    raw_models = value.get("models")
    for item in raw_models if isinstance(raw_models, list) else []:
        if not isinstance(item, dict):
            continue
        provider = _provider(item.get("provider"))
        if not provider:
            continue
        raw_score = item.get("movement_score")
        movement_score = None
        if isinstance(raw_score, (int, float)) and not isinstance(raw_score, bool):
            movement_score = max(0, min(100, int(round(raw_score))))
        models.append({
            "provider": provider,
            # None = no comparable position (not "stable").
            "movement_score": movement_score,
            "moved": bool(item.get("moved")) and movement_score is not None,
            "summary": _clip(item.get("summary"), 240),
        })
    raw_shift = value.get("shift_score")
    shift_score = None
    if isinstance(raw_shift, (int, float)):
        shift_score = max(0, min(100, int(round(raw_shift))))
    if not dimensions and shift_score is None:
        return None
    return {
        "schema_version": SCHEMA_VERSION,
        "dimensions": dimensions,
        "models": models,
        "shift_score": shift_score,
        "shift_label": _clip(value.get("shift_label"), 24),
        "center": [
            _clip(item, 180) for item in (
                value.get("center")[:MAX_DIMENSIONS]
                if isinstance(value.get("center"), list) else []
            ) if _clip(item, 180)
        ],
    }


def _position_for(dimension: dict, provider: str):
    for position in dimension.get("positions") or []:
        if provider in (position.get("models") or []):
            return position
    return None


def _match_dimensions(current: list[dict], previous: list[dict]) -> list[tuple[dict, dict]]:
    matches = []
    used = set()
    for dimension in current:
        best_index, best_score = None, 0.0
        for index, candidate in enumerate(previous):
            if index in used:
                continue
            score = similarity(dimension.get("label"), candidate.get("label"))
            if score > best_score:
                best_index, best_score = index, score
        if best_index is not None and best_score >= 0.34:
            used.add(best_index)
            matches.append((dimension, previous[best_index]))
    return matches


def _movement_view(dimensions: list[dict], previous=None, *, consensus_changed=None):
    """Per-provider movement plus the aggregate Direction Shift.

    Model movement is scored independently of the Change Judge: one model can
    change its stance while the consensus stays put, and that stays visible.
    ``consensus_changed=False`` only narrows the evidence: a lexical rewrite
    is then treated as paraphrase, while a changed number, unit, sign,
    negation, condition or month still counts. No comparable position means
    ``movement_score=None`` / ``shift_score=None`` ("Not comparable"), never
    0 / Stable.
    """
    providers = [
        provider for provider in PROVIDERS
        if any(_position_for(dimension, provider) for dimension in dimensions)
    ]
    previous = sanitize_opinion_map(previous)
    previous_dimensions = previous.get("dimensions") if previous else []
    matches = _match_dimensions(dimensions, previous_dimensions)
    lexical = consensus_changed is not False
    model_views = []
    all_movements = []
    for provider in providers:
        moved_count = 0
        comparable = 0
        summaries = []
        for current_dimension, previous_dimension in matches:
            current_position = _position_for(current_dimension, provider)
            previous_position = _position_for(previous_dimension, provider)
            if not current_position or not previous_position:
                continue
            comparable += 1
            moved = stance_changed(
                previous_position.get("stance"),
                current_position.get("stance"),
                lexical=lexical,
            )
            if moved:
                moved_count += 1
                summaries.append(
                    f"{current_dimension['label']}: {current_position['stance']}"
                )
        movement_score = round(100 * moved_count / comparable) if comparable else None
        if comparable:
            all_movements.append(movement_score)
        model_views.append({
            "provider": provider,
            "movement_score": movement_score,
            "moved": moved_count > 0,
            "summary": _clip(" · ".join(summaries), 240),
        })

    shift_score = None
    # A completely reframed set of generated labels is not proof that all
    # providers reversed position, and not proof of stability either. Leave
    # it unscored instead of inventing a 100/100 or 0/100 shift.
    if previous and matches and all_movements:
        shift_score = round(sum(all_movements) / len(all_movements))
    if shift_score is None:
        shift_label = "Not comparable" if previous and previous_dimensions else "New baseline"
    elif shift_score <= 15:
        shift_label = "Stable"
    elif shift_score <= 45:
        shift_label = "Evolving"
    else:
        shift_label = "Turning"
    return model_views, shift_score, shift_label


def _map_from_dimensions(dimensions: list[dict], previous=None, *, consensus_changed=None):
    model_views, shift_score, shift_label = _movement_view(
        dimensions, previous, consensus_changed=consensus_changed,
    )
    center = []
    for dimension in dimensions:
        dominant = max(dimension["positions"], key=lambda item: len(item["models"]))
        center.append(dominant["stance"])
    return {
        "schema_version": SCHEMA_VERSION,
        "dimensions": dimensions,
        "models": model_views,
        "shift_score": shift_score,
        "shift_label": shift_label,
        "center": center,
    }


def build_opinion_map(differences_data: dict, previous=None, *, consensus_changed=None) -> dict | None:
    """Build a multidimensional map and compare it with the previous map.

    Movement compares each provider's stance on matched dimensions: changed
    numbers, units, signs, negations, conditions or months always count;
    otherwise a conservative word-overlap comparison decides. With
    ``consensus_changed=False`` (Change Judge: consensus stable) the lexical
    fallback is off, so rephrased stances cannot fabricate a Direction Shift,
    but a single model's substantive change remains visible.
    """
    if not isinstance(differences_data, dict):
        return None
    dimensions = _dimensions(differences_data)
    if not dimensions:
        dimensions = _claim_dimensions(differences_data)
    if not dimensions:
        return None
    return _map_from_dimensions(
        dimensions, previous, consensus_changed=consensus_changed,
    )


def recalculate_opinion_map(value, previous=None, *, consensus_changed=None) -> dict | None:
    """Re-score a persisted map against its real predecessor on read.

    This fixes legacy history points produced by the former fallback that
    treated non-matching generated dimension labels as a certain 100/100 turn.
    """
    current = sanitize_opinion_map(value)
    if not current:
        return None
    dimensions = current.get("dimensions") or []
    if not dimensions:
        return current
    return _map_from_dimensions(
        dimensions, previous, consensus_changed=consensus_changed,
    )

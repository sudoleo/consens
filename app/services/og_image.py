"""Server-rendered Open-Graph-Karten (1200x630 PNG) für Share- und Topic-Seiten.

Statt des Favicons zeigt der Link-Preview die Frage der Seite: darüber leise
das Datum, unten neben der Wortmarke, was hinter der Antwort steht (Agreement,
Modelle, Widersprüche). Watch- und Topic-Karten tragen statt Datum und Score
den Zustand ihrer Seite („Watch · Unchanged since …“, seit 2026-10-20). Rein
aus gespeicherten Daten gerendert – keine LLM-Calls.
Dazu die Markenkarte für alle übrigen Seiten (``render_brand_card``, als
static/og-home-v2.png gespeichert von scripts/render_brand_card.py).

Eine Sprache für alle Karten: heller Grund, Inter in ruhigem Gewicht, die
Bildmarke von consens.io. Keine Linien, keine Versalien-Etiketten; Farbe trägt
nur die Score-Ziffer (Ampel wie in der App: ab 65 grün, ab 40 amber, darunter
rot). Alles Wichtige bleibt im sicheren Bereich: WhatsApp zeigt die Karte im
Eingabefeld beschnitten auf etwa 1,6:1, also rund 90 px weniger an jeder Seite.
"""

from __future__ import annotations

import io
import logging
import os
from datetime import datetime

from cachetools import TTLCache

from app.core.assets import asset_url
from app.core.observability import safe_exception
from app.core.site import SITE_URL

try:
    from PIL import Image, ImageDraw, ImageFont
    _PIL_OK = True
except Exception:  # pragma: no cover - Pillow fehlt nur in Alt-Umgebungen
    _PIL_OK = False

WIDTH, HEIGHT = 1200, 630
# Seitenrand der Fragekarten: nach WhatsApps Beschnitt bleiben gut 50 px Luft.
MARGIN = 144
FONT_PATH = os.path.join("static", "fonts", "Inter-Variable.ttf")
# Bildmarke und Anbieter-Logos als Alphamasken; gefärbt wird beim Zeichnen.
MARK_PATH = os.path.join("static", "favicon-dark.png")
LOGO_DIR = os.path.join("static", "icons", "chat_icons")

# Grund der Markenkarte, Tinte und Ampel aus static/css/variables.css (hell).
BG = (250, 250, 247)
INK = (29, 30, 32)
MUTED = (100, 103, 109)
LOGO_GREY = (150, 152, 157)
AGREE = (40, 125, 104)
PARTIAL = (148, 107, 31)
DISPUTE = (177, 79, 91)

# Fragengröße nach Länge: die größte Stufe, in der die ganze Frage passt.
QUESTION_STEPS = ((84, 2), (72, 3), (62, 3), (54, 4), (48, 4), (42, 5))
QUESTION_TOP, QUESTION_BOTTOM = 112, 468
DATELINE_Y = 82  # Grundlinie der Datumszeile
FOOTER_Y = 548  # optische Mitte der Fußzeile
FACTS_SEPARATOR = "  ·  "

# Die Markenkarte der Landing: Vorschaubild jeder Seite ohne eigene Karte.
# Ihre Zeile ist der Hero-Satz der Landing (templates/landing.html, h1), die
# sechs Marken sind die Familien eines vollen Laufs.
BRAND_CARD = "/static/og-home-v2.png"
BRAND_HEADLINE = ("Six models answer.", "See where they disagree.")
BRAND_LOGOS = ("chatgpt.png", "claude.png", "gemini-icon.png", "grok.png", "deepseek.png", "mistral.png")

_cache = TTLCache(maxsize=256, ttl=1800)


def brand_card_url() -> str:
    return SITE_URL + asset_url(BRAND_CARD)


def date_label(value) -> str:
    """"Oct 12, 2026" aus einem datetime oder ISO-String; "" wenn unlesbar."""
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return ""
    if not isinstance(value, datetime):
        return ""
    return f"{value:%b} {value.day}, {value.year}"


def is_available() -> bool:
    return _PIL_OK and os.path.isfile(FONT_PATH) and os.path.isfile(MARK_PATH)


def _font(size: int, weight: int = 450):
    font = ImageFont.truetype(FONT_PATH, size)
    try:
        # Inter ist eine Variable Font mit Achsen (opsz, wght).
        font.set_variation_by_axes([min(size, 32), weight])
    except Exception:
        pass
    return font


def _wrap(draw, text: str, font, max_width: int, max_lines: int) -> tuple[list[str], bool]:
    """Zeilen und ob der ganze Text hineinpasst (sonst endet er mit …)."""
    words = []
    for word in str(text or "").split():
        # Ein Wort breiter als die Karte (eingefügte URL) bricht nach Zeichen,
        # statt über den Rand zu laufen.
        while len(word) > 1 and draw.textlength(word, font=font) > max_width:
            cut = len(word) - 1
            while cut > 1 and draw.textlength(word[:cut], font=font) > max_width:
                cut -= 1
            words.append(word[:cut])
            word = word[cut:]
        words.append(word)
    lines, current, used = [], "", 0
    for word in words:
        candidate = (current + " " + word).strip()
        if draw.textlength(candidate, font=font) <= max_width or not current:
            current = candidate
            used += 1
            continue
        lines.append(current)
        if len(lines) == max_lines:
            break
        current = word
        used += 1
    if current and len(lines) < max_lines:
        lines.append(current)
    complete = used >= len(words) and len(lines) <= max_lines
    if not complete and lines:
        last = lines[-1].rstrip(".,;:?!")
        while last and draw.textlength(last + "…", font=font) > max_width:
            last = last.rsplit(" ", 1)[0] if " " in last else last[:-1]
        lines[-1] = last + "…"
    return lines, complete


def _question_layout(draw, question: str):
    max_width = WIDTH - 2 * MARGIN
    for size, max_lines in QUESTION_STEPS:
        font = _font(size, 520)
        lines, complete = _wrap(draw, question, font, max_width, max_lines)
        if complete:
            return font, size, lines
    return font, size, lines


def _score_color(score: int):
    return AGREE if score >= 65 else PARTIAL if score >= 40 else DISPUTE


def _paste_mask(image, path: str, height: int, xy: tuple[int, int], color) -> int:
    """Zeichnet die Form einer PNG (ihren Alphakanal) in einer Farbe; gibt die Breite zurück."""
    with Image.open(path) as source:
        alpha = source.convert("RGBA").getchannel("A")
    width = round(alpha.width * height / alpha.height)
    image.paste(Image.new("RGB", (width, height), color), xy,
                alpha.resize((width, height), Image.LANCZOS))
    return width


def _lockup(draw, mark_height: int, word_size: int):
    """Font, Markenbreite, Abstand und Gesamtbreite von Bildmarke + Wortmarke."""
    word_font = _font(word_size, 420)
    with Image.open(MARK_PATH) as mark:
        mark_width = round(mark.width * mark_height / mark.height)
    gap = round(mark_height * 0.42)
    return word_font, mark_width, gap, mark_width + gap + int(draw.textlength("consens.io", font=word_font))


def _draw_lockup(image, draw, x: int, center_y: int, mark_height: int = 36, word_size: int = 28) -> int:
    """Bildmarke + Wortmarke ab x, mittig auf center_y; gibt die rechte Kante zurück."""
    word_font, mark_width, gap, total = _lockup(draw, mark_height, word_size)
    _paste_mask(image, MARK_PATH, mark_height, (x, center_y - mark_height // 2), INK)
    draw.text((x + mark_width + gap, center_y), "consens.io", font=word_font, fill=INK, anchor="lm")
    return x + total


def _draw_facts(draw, score, facts: list[str], left_limit: int) -> None:
    """Rechtsbündige Faktenzeile auf der Höhe der Wortmarke.

    Passt sie nicht neben die Marke, fallen Fakten von hinten weg; der Score
    bleibt immer stehen.
    """
    number_font = _font(28, 640)
    text_font = _font(24, 460)
    parts = []  # (text, font, fill)
    if isinstance(score, (int, float)):
        value = max(0, min(100, int(score)))
        parts.append([(str(value), number_font, _score_color(value)),
                      ("/100 agreement", text_font, MUTED)])
    parts.extend([[(fact, text_font, MUTED)] for fact in facts if fact])

    def width(groups):
        runs = [run for group in groups for run in group]
        gaps = draw.textlength(FACTS_SEPARATOR, font=text_font) * (len(groups) - 1)
        return sum(draw.textlength(text, font=font) for text, font, _ in runs) + gaps

    right = WIDTH - MARGIN
    while len(parts) > 1 and right - width(parts) < left_limit:
        parts.pop()
    # Eine gemeinsame Grundlinie, damit Ziffer und Text auf einer Zeile sitzen.
    baseline = FOOTER_Y + 10
    x = right - width(parts)
    for index, group in enumerate(parts):
        if index:
            draw.text((x, baseline), FACTS_SEPARATOR, font=text_font, fill=MUTED, anchor="ls")
            x += draw.textlength(FACTS_SEPARATOR, font=text_font)
        for text, font, fill in group:
            draw.text((x, baseline), text, font=font, fill=fill, anchor="ls")
            x += draw.textlength(text, font=font)


def render_card(*, question: str, score=None, facts: list[str] = (), dateline: str = "") -> bytes:
    image = Image.new("RGB", (WIDTH, HEIGHT), BG)
    draw = ImageDraw.Draw(image)

    if dateline:
        draw.text((MARGIN, DATELINE_Y), dateline, font=_font(24, 460), fill=MUTED, anchor="ls")

    font, size, lines = _question_layout(draw, question)
    line_height = round(size * 1.18)
    block = line_height * len(lines)
    y = QUESTION_TOP + max(0, (QUESTION_BOTTOM - QUESTION_TOP - block) // 2)
    for line in lines:
        draw.text((MARGIN, y), line, font=font, fill=INK)
        y += line_height

    brand_right = _draw_lockup(image, draw, MARGIN, FOOTER_Y)
    _draw_facts(draw, score, list(facts), brand_right + 48)

    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def render_brand_card() -> bytes:
    """Die Markenkarte: Wortmarke, Hero-Satz in zwei Tönen, sechs Marken.

    Alles steht zentriert, damit jede Vorschau es zeigt, auch eine, die das
    Bild seitlich beschneidet.
    """
    image = Image.new("RGB", (WIDTH, HEIGHT), BG)
    draw = ImageDraw.Draw(image)

    total = _lockup(draw, 38, 30)[3]
    _draw_lockup(image, draw, (WIDTH - total) // 2, 112, mark_height=38, word_size=30)

    headline = _font(70, 560)
    for line, fill, baseline in zip(BRAND_HEADLINE, (INK, MUTED), (272, 360)):
        draw.text((WIDTH // 2, baseline), line, font=headline, fill=fill, anchor="ms")

    # Each mark fits a 40 x 48 box, so the wide ones (DeepSeek, Mistral) do
    # not outweigh the round ones.
    gap, sizes = 44, []
    for name in BRAND_LOGOS:
        with Image.open(os.path.join(LOGO_DIR, name)) as logo:
            height = min(40, round(48 * logo.height / logo.width))
            sizes.append((height, round(logo.width * height / logo.height)))
    x = (WIDTH - sum(width for _, width in sizes) - gap * (len(sizes) - 1)) // 2
    for name, (height, width) in zip(BRAND_LOGOS, sizes):
        _paste_mask(image, os.path.join(LOGO_DIR, name), height, (x, 500 - height // 2), LOGO_GREY)
        x += width + gap

    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def share_facts(model_count: int, contradiction_count: int) -> list[str]:
    facts = [f"{model_count} AI models" if model_count else "Several AI models"]
    if contradiction_count:
        facts.append(f"{contradiction_count} contradiction{'s' if contradiction_count != 1 else ''}")
    return facts


def render_share_card(*, question: str, score, model_count: int,
                      contradiction_count: int, checked_label: str = "") -> bytes:
    return render_card(
        question=question, score=score,
        facts=share_facts(model_count, contradiction_count), dateline=checked_label,
    )


def card_png(cache_id: str, *, question: str, score=None, facts: list[str] = (),
             dateline: str = "") -> bytes | None:
    """Gecachte Karte; None wenn Rendering nicht verfügbar/fehlgeschlagen."""
    if not is_available():
        return None
    # Every rendered input participates: a corrected snapshot must not serve
    # an older question or statistic for thirty minutes.
    key = (cache_id, question, int(score) if isinstance(score, (int, float)) else -1,
           tuple(facts), dateline)
    cached = _cache.get(key)
    if cached is not None:
        return cached
    try:
        png = render_card(question=question, score=score, facts=list(facts), dateline=dateline)
    except Exception as exc:
        logging.error("og_image rendering failed category=%s", safe_exception(exc))
        return None
    _cache[key] = png
    return png


def watch_card_png(share_id: str, *, question: str, state_line: str,
                   model_count: int) -> bytes | None:
    """A Watch's card, built like a Topic card: above the question what its
    page leads with ("Watch · Unchanged since Sep 24", "Watch · Paused · last
    checked Oct 1"), no score -- the page shows none (Apple-Audit L13)."""
    return card_png(
        f"watch:{share_id}", question=question,
        facts=[f"{model_count} AI models" if model_count else "Several AI models"],
        dateline=" · ".join(part for part in ("Watch", state_line) if part),
    )


def share_card_png(share_id: str, *, question: str, score, model_count: int,
                   contradiction_count: int, checked_label: str = "") -> bytes | None:
    return card_png(
        share_id, question=question, score=score,
        facts=share_facts(model_count, contradiction_count), dateline=checked_label,
    )

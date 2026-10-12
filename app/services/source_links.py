"""Direkte Wege zu den Quellen einer Watch (seit 2026-10-12).

Wer ein Thema beobachtet, will nicht nur die Antwort lesen, sondern selbst
nachsehen: die Stellenanzeige, die Produktseite, die offizielle Ankündigung.
Dieses Modul wählt aus den vorhandenen Quellen

* die **Direktlinks** über der Antwort (``key_links``): Seiten, die die
  Antwort beim Namen nennt, und tiefe Links mit sprechendem Titel, je Domain
  einer;
* die **Namen im Text** (``site_mentions``): wo die Antwort eine Quelle beim
  Namen nennt ("bei Idealo und Geizhals"), führt der Name zu ihr.

Bewusst keine Satz-für-Satz-Belege: die Synthese hängt Quellen dabei oft
falsch an (docs/source-verification.md, seit 2026-09 abgeschaltet). Ein Name,
der zu genau dieser Seite führt, ist Navigation, kein Beleg -- er kann nicht
falsch zitieren. Keine Modell-Calls, keine Netzabrufe.
"""

from __future__ import annotations

import re
from urllib.parse import urlsplit

MAX_KEY_LINKS = 4
MAX_INLINE_LINKS = 8
MIN_NAME_LENGTH = 4

# Site-Namen, die zugleich gewöhnliche Wörter sind ("billiger kaufen", "die
# Zeit", "ein Test"): als Wort im Text sind sie meist keine Nennung der Seite.
# Ausgeschrieben als Domain ("zeit.de") werden sie trotzdem verlinkt.
_COMMON_WORDS = frozenset("""
billiger zeit welt bild spiegel focus stern test check chip kicker mobile post
real giga netto handel blick presse kurier heute morgen abend tag woche markt
time times money fortune nature science wired verge vice mint quartz medium
guardian independent economist observer register mirror sun star express news
shop store home best review reviews guide wiki deal deals price prices
""".split())


def _path_depth(url: str) -> int:
    try:
        path = urlsplit(url).path
    except ValueError:
        return 0
    return len([part for part in path.split("/") if part])


def _descriptive(entry: dict) -> bool:
    """Ein Titel, der mehr sagt als die Domain."""
    title = str(entry.get("title") or "").strip().lower()
    domain = str(entry.get("domain") or "").lower()
    return len(title) >= 12 and title not in {domain, "www." + domain}


def _quality(entry: dict) -> int:
    """Wie gut eine Quelle als Ziel taugt: tiefe direkte Seite mit Titel > Startseite > Weiterleitung."""
    score = 0
    if entry.get("is_direct"):
        score += 1
        if _path_depth(str(entry.get("url") or "")) > 0:
            score += 2
    if _descriptive(entry):
        score += 1
    return score


def _usable(entry: dict) -> bool:
    url = str(entry.get("url") or "")
    return url.startswith(("https://", "http://")) and bool(entry.get("domain"))


def best_by_domain(sources) -> dict[str, dict]:
    """Je Domain die Quelle, die als Ziel am meisten taugt (bei Gleichstand die erste)."""
    best: dict[str, tuple[int, int, dict]] = {}
    for index, entry in enumerate(sources or []):
        if not isinstance(entry, dict) or not _usable(entry):
            continue
        domain = str(entry["domain"]).lower()
        rank = (_quality(entry), -index)
        if domain not in best or rank > best[domain][:2]:
            best[domain] = (rank[0], rank[1], entry)
    return {domain: value[2] for domain, value in best.items()}


def _name_pattern(name: str):
    return re.compile(r"(?<![\w.-])" + re.escape(name) + r"(?![\w-])", re.IGNORECASE)


def _mention(entry: dict, text: str):
    """(start, end, Wortlaut) der ersten Nennung dieser Quelle im Text, sonst None.

    Die ausgeschriebene Domain ("geizhals.de") zählt immer; der Site-Name
    ("Geizhals", "Top4Running", "21run") nur, wenn er wie ein Name dasteht --
    nicht als gewöhnliches Wort und nicht mitten in einer Wortkette
    ("Adidas-Größe").
    """
    domain = str(entry.get("domain") or "").lower()
    site = str(entry.get("site") or "").lower()
    found = _name_pattern(domain).search(text) if domain else None
    if found:
        return found.start(), found.end(), found.group(0)
    if len(site) < MIN_NAME_LENGTH or site in _COMMON_WORDS or not re.fullmatch(r"[a-z0-9-]+", site):
        return None
    for match in _name_pattern(site).finditer(text):
        word = match.group(0)
        # Ein Name beginnt groß oder trägt eine Ziffer (Idealo, eBay, 21run);
        # klein geschrieben ist es meist das gewöhnliche Wort.
        if word[0].isupper() or any(ch.isdigit() for ch in word) or word != word.lower():
            return match.start(), match.end(), word
    return None


def site_mentions(sources, text: str, limit: int = MAX_INLINE_LINKS) -> list[dict]:
    """Quellen, die der Text beim Namen nennt, in Reihenfolge der Nennung.

    Je Domain eine Nennung (die erste) mit dem besten Ziel dieser Domain:
    ``{"name": Wortlaut im Text, "url", "domain", "title"}``.
    """
    text = str(text or "")
    found = []
    for domain, entry in best_by_domain(sources).items():
        # Im Lesetext nur echte Adressen: eine Weiterleitung verrät nicht,
        # wohin der Klick führt.
        if not entry.get("is_direct"):
            continue
        mention = _mention(entry, text)
        if mention:
            start, _end, word = mention
            found.append((start, {
                "name": word,
                "url": entry["url"],
                "domain": domain,
                "title": str(entry.get("title") or domain),
            }))
    found.sort(key=lambda item: item[0])
    return [item for _start, item in found[:limit]]


_TITLE_SEPARATORS = re.compile(r"\s+(?:[-|–—·:]|::)\s+")


def display_title(entry: dict) -> str:
    """Seitentitel ohne angehängten Seitennamen und lose Anführungszeichen.

    "Laufschuhe adidas Adizero Adios Pro 4 - Top4Running.de" -> "Laufschuhe
    adidas Adizero Adios Pro 4"; die Domain steht ohnehin darunter.
    """
    title = str(entry.get("title") or "").strip().strip("\"'“”„« »")
    names = {str(entry.get("site") or "").lower(), str(entry.get("domain") or "").lower()} - {""}
    parts = _TITLE_SEPARATORS.split(title)
    while len(parts) > 1:
        tail = parts[-1].strip().lower().replace(" ", "")
        if not any(name in tail or (len(tail) >= 4 and tail in name) for name in names):
            break
        parts.pop()
    cleaned = " - ".join(part.strip() for part in parts).strip()
    if cleaned != title:
        # Nur Schnitte an echten Trennern zurückbauen, nicht den Rest umformatieren.
        cut = title.rfind(parts[-1]) + len(parts[-1]) if parts else len(title)
        cleaned = title[:cut].strip()
    return cleaned or str(entry.get("domain") or "")


def key_links(sources, text: str, limit: int = MAX_KEY_LINKS) -> list[dict]:
    """Die Direktlinks über der Antwort.

    Eine Quelle je Domain. Vorn, was die Antwort beim Namen nennt, dann tiefe
    direkte Seiten mit sprechendem Titel (die Stellenanzeige, die
    Produktseite); eine Startseite oder Weiterleitung kommt nur, wenn die
    Antwort sie nennt. Bei Gleichstand gilt die Reihenfolge der Quellen.
    """
    text = str(text or "")
    order = {id(entry): index for index, entry in enumerate(sources or [])}
    ranked = []
    for domain, entry in best_by_domain(sources).items():
        mentioned = _mention(entry, text) is not None
        quality = _quality(entry)
        if not mentioned and quality < 4:
            continue
        ranked.append((-(int(mentioned) * 3 + quality), order.get(id(entry), 0), entry))
    ranked.sort(key=lambda item: item[:2])
    return [
        {**entry, "title": display_title(entry)}
        for *_rank, entry in ranked[:limit]
    ]

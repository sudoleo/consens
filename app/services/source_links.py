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
falsch an (seit 2026-09 abgeschaltet, docs/codebase-map.md „Quellen in der Synthese“). Ein Name,
der zu genau dieser Seite führt, ist Navigation, kein Beleg -- er kann nicht
falsch zitieren. Keine Modell-Calls, keine Netzabrufe.
"""

from __future__ import annotations

import re
from urllib.parse import unquote, urlsplit

from app.services.public_markdown import source_host, source_site_name

MAX_KEY_LINKS = 4
MAX_CARD_LINKS = 3
MAX_INLINE_LINKS = 8
MIN_NAME_LENGTH = 4

# consens.io itself. A search that finds the page about this very question
# hands it back as a source: a Watch then cited itself, under "Direct links"
# and in its source list (Apple-Audit L4). Such a link is never evidence.
OWN_HOSTS = ("consens.io",)


def is_own_page(url) -> bool:
    """True for a link to consens.io (any subdomain)."""
    try:
        host = (urlsplit(str(url or "")).hostname or "").lower().rstrip(".")
    except ValueError:
        return False
    return any(host == own or host.endswith("." + own) for own in OWN_HOSTS)


def without_own_pages(sources) -> list:
    """The sources without links to consens.io (see ``is_own_page``)."""
    return [
        source for source in sources or []
        if not (isinstance(source, dict) and is_own_page(source.get("url")))
    ]


def source_entries(sources) -> list[dict]:
    """Gespeicherte Quellen als Einträge mit Domain, Site-Name und ob die URL
    direkt ist (keine Grounding-Weiterleitung). Gleiche Felder wie die
    Quellenliste der Watch-Seite."""
    entries = []
    for source in sources or []:
        if not isinstance(source, dict):
            continue
        url = str(source.get("url") or "")
        domain = source_host(url, source.get("title"))
        title = str(source.get("title") or "").strip()
        if not title or title == url or re.fullmatch(r"\d+", title):
            title = domain or url
        entries.append({
            "title": title,
            "url": url,
            "domain": domain,
            "site": source_site_name(url, source.get("title")),
            "is_direct": bool(domain) and domain == source_host(url),
        })
    return entries

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


def _descriptive(entry: dict) -> int:
    """2 für einen Titel, der mehr sagt als die Domain; 1, wo der Titel bloß
    die Domain ist, aber der Pfad spricht; sonst 0."""
    title = str(entry.get("title") or "").strip().lower()
    domain = str(entry.get("domain") or "").lower()
    if title in {domain, "www." + domain}:
        return int(bool(entry.get("is_direct")) and bool(_slug_title(str(entry.get("url") or ""))))
    return 2 if len(title) >= 12 else 0


def _quality(entry: dict) -> int:
    """Wie gut eine Quelle als Ziel taugt: tiefe direkte Seite mit echtem
    Titel > mit sprechendem Pfad > Startseite > Weiterleitung."""
    score = 0
    if entry.get("is_direct"):
        score += 1
        if _path_depth(str(entry.get("url") or "")) > 0:
            score += 2
    return score + _descriptive(entry)


def _usable(entry: dict) -> bool:
    url = str(entry.get("url") or "")
    return url.startswith(("https://", "http://")) and bool(entry.get("domain")) and not is_own_page(url)


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


# " - ", " | ", " · ", " \ " (Anthropic writes "Introducing Claude \ Anthropic").
_TITLE_SEPARATORS = re.compile(r"\s+(?:[-|–—·:\\/]|::)\s+")
# Product names a site signs its titles with ("... - ChatGPT" on
# help.openai.com): stripped like the site's own name.
_SITE_ALIASES = {
    "openai": ("chatgpt",),
    "anthropic": ("claude",),
    "google": ("gemini",),
}


def _slug_title(url: str) -> str:
    """Lesbarer Titel aus dem letzten sprechenden Pfadteil, sonst leer.

    "/baseproducts/119030-adidas-adizero-adios-pro-4" -> "Adidas adizero
    adios pro 4". Nur für Quellen, deren Titel bloß die Domain ist.
    """
    try:
        parts = [unquote(part) for part in urlsplit(url).path.split("/") if part]
    except ValueError:
        return ""
    for part in reversed(parts):
        part = re.sub(r"\.(html?|php|aspx?)$", "", part, flags=re.IGNORECASE)
        words = [word for word in re.split(r"[-_+\s]+", part) if word]
        # Lange IDs, Hashes und Artikelnummern ("119030", "kj6244") raus;
        # kurze Zahlen gehören zum Namen ("Pro 4", "2026").
        words = [
            word for word in words
            if not re.fullmatch(r"\d{5,}|(?=[0-9a-f]*\d)[0-9a-f]{8,}|[a-z]{1,2}\d{3,}\w*", word, re.IGNORECASE)
        ]
        letters = [word for word in words if re.search(r"[^\W\d_]{2,}", word)]
        if len(letters) >= 2:
            text = " ".join(words)
            return (text[:1].upper() + text[1:])[:120]
    return ""


def display_title(entry: dict) -> str:
    """Seitentitel ohne angehängten Seitennamen und lose Anführungszeichen.

    "Laufschuhe adidas Adizero Adios Pro 4 - Top4Running.de" -> "Laufschuhe
    adidas Adizero Adios Pro 4"; die Domain steht ohnehin darunter. Ist der
    Titel bloß die Domain (aufgelöste Grounding-Weiterleitung), sagt der
    Pfad mehr.
    """
    title = str(entry.get("title") or "").strip().strip("\"'“”„« »")
    domain = str(entry.get("domain") or "").lower()
    if title.lower().removeprefix("www.") == domain and entry.get("is_direct"):
        return _slug_title(str(entry.get("url") or "")) or title
    names = {str(entry.get("site") or "").lower(), str(entry.get("domain") or "").lower()} - {""}
    names |= {alias for name in list(names) for alias in _SITE_ALIASES.get(name.split(".")[0], ())}
    parts = _TITLE_SEPARATORS.split(title)
    while len(parts) > 1:
        tail = parts[-1].strip().lower().replace(" ", "")
        # "Owner's Manual - Amp" on ampcode.com: a short brand that starts the
        # site's name counts as the name too.
        if not any(
            name in tail or (len(tail) >= 4 and tail in name) or (len(tail) >= 3 and name.startswith(tail))
            for name in names
        ):
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
    Produktseite); eine Startseite kommt nur, wenn die Antwort sie nennt, eine
    Google-Weiterleitung nie (sie verrät ihr Ziel nicht und verfällt). Bei
    Gleichstand gilt die Reihenfolge der Quellen.
    """
    text = str(text or "")
    order = {id(entry): index for index, entry in enumerate(sources or [])}
    ranked = []
    for domain, entry in best_by_domain(sources).items():
        if not entry.get("is_direct"):
            continue
        mentioned = _mention(entry, text) is not None
        quality = _quality(entry)
        if not mentioned and quality < 4:
            continue
        ranked.append((-(int(mentioned) * 3 + quality), order.get(id(entry), 0), entry))
    ranked.sort(key=lambda item: item[:2])
    # Two tiles with the same title (a GitHub file and its issue page) read
    # as a doubled link: the better-ranked one stays (Apple-Audit L12).
    links, titles = [], set()
    for *_rank, entry in ranked:
        title = display_title(entry)
        key = re.sub(r"\W+", " ", title).strip().lower()
        if key in titles:
            continue
        titles.add(key)
        links.append({**entry, "title": title})
        if len(links) == limit:
            break
    return links


def card_links(sources, text: str, limit: int = MAX_CARD_LINKS) -> list[dict]:
    """Die Direktlinks fürs Dashboard, kompakt zum Speichern am Watch-Dokument
    (``{url, title, domain}``): so liest die Liste keine weiteren Dokumente."""
    return [
        {"url": link["url"][:2000], "title": link["title"][:200], "domain": link["domain"][:120]}
        for link in key_links(source_entries(sources), text, limit=limit)
    ]

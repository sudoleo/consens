"""Google-Grounding-Weiterleitungen durch ihr Ziel ersetzen (seit 2026-10-12).

Geminis Websuche liefert Quellen als signierte Weiterleitung über
``vertexaisearch.cloud.google.com``, oft nur mit der Domain als Titel
("adidas.com"). Wer darauf klickt, sieht vorher nicht, wohin er kommt, und
solche Links verfallen nach einiger Zeit. Beim Speichern einer Watch-Prüfung
wird deshalb jede Weiterleitung einmal angefragt und durch ihr Ziel ersetzt
(``idealo.de/preisvergleich/…``).

Die einzelne Auflösung ist die des Agenten (``agent_read_source.
resolve_redirect``): nur dieser eine Google-Host wird angefragt, gelesen wird
nur der ``Location``-Header (dem Ziel wird nicht gefolgt, es wird nichts davon
geladen), das Ziel muss eine sichere öffentliche URL sein. Hier kommt nur das
parallele Abarbeiten mit festem Gesamtbudget dazu. Scheitert eine Auflösung,
bleibt die Weiterleitung stehen -- nichts geht verloren.

Was Google eindeutig nicht mehr kennt (404/410, ``expired_urls``), ist ein
toter Link: das Nachrüst-Skript entfernt solche Quellen und merkt sich ihre
Nummern als ``expired_source_ids``, damit alte ``[S3]``-Verweise im Text
wegfallen statt als nackter Text stehen zu bleiben.
"""

from __future__ import annotations

import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor, wait
from urllib.parse import urlsplit

from app.core.observability import safe_exception

REDIRECT_HOSTS = frozenset({"vertexaisearch.cloud.google.com"})
# Felder, in denen eine Quelle ihre Adresse trägt (Quellen, Belege, Dokumente
# der Quellenprüfung).
URL_KEYS = frozenset({"url", "source_url"})
MAX_URLS = 40
MAX_WORKERS = 6
BUDGET_SECONDS = 10.0


def is_redirect(url) -> bool:
    try:
        parts = urlsplit(str(url or ""))
    except ValueError:
        return False
    return parts.scheme == "https" and (parts.hostname or "").lower() in REDIRECT_HOSTS


def _enabled() -> bool:
    from app.services.llm.mock_llm import mock_llm_enabled

    if mock_llm_enabled():
        return False
    return not any(os.getenv(key) == "1" for key in ("UNIT_TEST_MODE", "E2E_TEST_MODE"))


def resolve_urls(urls, *, fetch=None, budget_seconds=BUDGET_SECONDS) -> dict[str, str]:
    """{Weiterleitung: Ziel} für die auflösbaren Weiterleitungen in ``urls``.

    ``fetch(url) -> Ziel oder ""`` ersetzt den Netzabruf in Tests; ohne ihn
    passiert in Unit-/E2E-/Mock-Läufen nichts. ``budget_seconds`` begrenzt
    die Wartezeit insgesamt (Agent-Vergleich: kürzer als die Watch-Prüfung).
    """
    pending = list(dict.fromkeys(str(url) for url in urls or [] if is_redirect(url)))[:MAX_URLS]
    if not pending or (fetch is None and not _enabled()):
        return {}
    if fetch is None:
        from app.services.agent_read_source import resolve_redirect as fetch
    resolved: dict[str, str] = {}
    started = time.monotonic()

    def run(url):
        try:
            target = fetch(url)
        except Exception as exc:
            logging.info("Source redirect skipped category=%s", safe_exception(exc))
            return
        if target and target != url and not is_redirect(target) and len(target) <= 2000:
            resolved[url] = target

    pool = ThreadPoolExecutor(max_workers=MAX_WORKERS, thread_name_prefix="source-redirect")
    try:
        futures = [pool.submit(run, url) for url in pending]
        wait(futures, timeout=max(0.0, budget_seconds - (time.monotonic() - started)))
    finally:
        # Nicht auf Nachzügler warten: das Budget gilt für die Prüfung.
        pool.shutdown(wait=False, cancel_futures=True)
    return dict(resolved)


def replace_urls(value, mapping: dict[str, str]):
    """(Kopie mit ersetzten ``url``-Feldern, ob sich etwas geändert hat).

    Läuft durch Listen und Dicts -- Quellen, Belege einer Änderung, Belege
    des Ziels, History-Punkte, Dokumente der Quellenprüfung --; nur die
    Adressfelder (``URL_KEYS``) werden ersetzt.
    """
    if not mapping:
        return value, False
    if isinstance(value, list):
        changed = False
        items = []
        for item in value:
            new, moved = replace_urls(item, mapping)
            items.append(new)
            changed = changed or moved
        return (items, True) if changed else (value, False)
    if isinstance(value, dict):
        changed = False
        out = {}
        for key, item in value.items():
            if key in URL_KEYS and isinstance(item, str) and item in mapping:
                out[key] = mapping[item]
                changed = True
                continue
            new, moved = replace_urls(item, mapping)
            out[key] = new
            changed = changed or moved
        return (out, True) if changed else (value, False)
    return value, False


def collect_redirects(value) -> list[str]:
    """Alle Weiterleitungen in Adressfeldern (``URL_KEYS``) einer verschachtelten Struktur."""
    found = []
    if isinstance(value, list):
        for item in value:
            found += collect_redirects(item)
    elif isinstance(value, dict):
        for key, item in value.items():
            if key in URL_KEYS and is_redirect(item):
                found.append(item)
            else:
                found += collect_redirects(item)
    return found


EXPIRED_CODES = frozenset({404, 410})


def _status(url: str):
    import httpx

    with httpx.Client(timeout=5.0, follow_redirects=False, trust_env=False) as client:
        return client.get(url, headers={"User-Agent": "consens.io source reader/1"}).status_code


def expired_urls(urls, *, status=None) -> set[str]:
    """Die Weiterleitungen, die Google eindeutig nicht mehr kennt (404/410).

    Nur der feste Google-Host wird gefragt. Zeitüberschreitung, 429 oder 5xx
    heißen "weiß nicht" -- solche Links bleiben stehen.
    """
    pending = list(dict.fromkeys(str(url) for url in urls or [] if is_redirect(url)))
    if not pending or (status is None and not _enabled()):
        return set()
    status = status or _status
    expired = set()

    def run(url):
        try:
            if status(url) in EXPIRED_CODES:
                expired.add(url)
        except Exception as exc:
            logging.info("Source redirect check skipped category=%s", safe_exception(exc))

    with ThreadPoolExecutor(max_workers=MAX_WORKERS, thread_name_prefix="source-expiry") as pool:
        list(pool.map(run, pending))
    return expired


def drop_urls(value, urls):
    """(Kopie ohne Einträge mit diesen ``url``s, ob sich etwas geändert hat,
    die ``id``s der entfernten Einträge).

    Wie ``replace_urls``: läuft durch Listen und Dicts; entfernt werden
    Listeneinträge (Quellen, Belege), deren ``url`` abgelaufen ist.
    """
    urls = set(urls or ())
    if not urls:
        return value, False, []
    if isinstance(value, list):
        items, changed, removed = [], False, []
        for item in value:
            if isinstance(item, dict) and item.get("url") in urls:
                changed = True
                if item.get("id"):
                    removed.append(str(item["id"]))
                continue
            new, moved, gone = drop_urls(item, urls)
            items.append(new)
            changed = changed or moved
            removed += gone
        return (items, True, removed) if changed else (value, False, [])
    if isinstance(value, dict):
        out, changed, removed = {}, False, []
        for key, item in value.items():
            new, moved, gone = drop_urls(item, urls)
            out[key] = new
            changed = changed or moved
            removed += gone
        return (out, True, removed) if changed else (value, False, [])
    return value, False, []


def resolve_sources(sources, *, fetch=None) -> list:
    """Quellen mit aufgelösten Weiterleitungen (Kopie; Rest unverändert)."""
    mapping = resolve_urls(collect_redirects(sources), fetch=fetch)
    return replace_urls(list(sources or []), mapping)[0]

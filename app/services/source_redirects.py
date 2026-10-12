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
"""

from __future__ import annotations

import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor, wait
from urllib.parse import urlsplit

from app.core.observability import safe_exception

REDIRECT_HOSTS = frozenset({"vertexaisearch.cloud.google.com"})
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


def resolve_urls(urls, *, fetch=None) -> dict[str, str]:
    """{Weiterleitung: Ziel} für die auflösbaren Weiterleitungen in ``urls``.

    ``fetch(url) -> Ziel oder ""`` ersetzt den Netzabruf in Tests; ohne ihn
    passiert in Unit-/E2E-/Mock-Läufen nichts.
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
        wait(futures, timeout=max(0.0, BUDGET_SECONDS - (time.monotonic() - started)))
    finally:
        # Nicht auf Nachzügler warten: das Budget gilt für die Prüfung.
        pool.shutdown(wait=False, cancel_futures=True)
    return dict(resolved)


def replace_urls(value, mapping: dict[str, str]):
    """(Kopie mit ersetzten ``url``-Feldern, ob sich etwas geändert hat).

    Läuft durch Listen und Dicts -- Quellen, Belege einer Änderung, Belege
    des Ziels, History-Punkte --; nur Felder namens ``url`` werden ersetzt.
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
            if key == "url" and isinstance(item, str) and item in mapping:
                out[key] = mapping[item]
                changed = True
                continue
            new, moved = replace_urls(item, mapping)
            out[key] = new
            changed = changed or moved
        return (out, True) if changed else (value, False)
    return value, False


def collect_redirects(value) -> list[str]:
    """Alle Weiterleitungen in ``url``-Feldern einer verschachtelten Struktur."""
    found = []
    if isinstance(value, list):
        for item in value:
            found += collect_redirects(item)
    elif isinstance(value, dict):
        for key, item in value.items():
            if key == "url" and is_redirect(item):
                found.append(item)
            else:
                found += collect_redirects(item)
    return found


def resolve_sources(sources, *, fetch=None) -> list:
    """Quellen mit aufgelösten Weiterleitungen (Kopie; Rest unverändert)."""
    mapping = resolve_urls(collect_redirects(sources), fetch=fetch)
    return replace_urls(list(sources or []), mapping)[0]

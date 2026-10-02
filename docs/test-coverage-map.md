# Testabdeckung: aktueller Bestand und offene Grenzen

**Stand: 02.10.2026 · Quellstand `2860844a` (lokaler `main`)**

Der Katalog enthält **254 Testdateien, 3.068 statische Definitionen und 4.053
Runnerfälle**. Seit dem Audit vom 26.09.2026 kamen 40 Dateien hinzu, zwei wurden
entfernt. Neue/geänderte Testkörper, Assertions, Fixtures und Produktverträge
wurden abgeglichen. Unveränderte Beschreibungen behalten ihre Aussagegrenze.
Testzahlen und bestandene Läufe beweisen keine vollständige fachliche Abdeckung.

## Einstieg

| Dokument | Inhalt |
|---|---|
| [Python-Katalog](test-coverage/backend.md) | 152 Dateien: API, Dienste, Infrastruktur, statische Frontendverträge |
| [JavaScript-Katalog](test-coverage/frontend.md) | 72 Dateien: jsdom, Module und Buildtests |
| [E2E-Katalog](test-coverage/e2e.md) | 30 Dateien: Browser, Smoke und Emulatortransaktionen |
| [Produktbereiche](test-coverage/areas.md) | Fachlicher Einstieg über alle Suiten |
| [Produktabgleich](test-coverage/product/README.md) | 301 Produktdateien, 87 Vertragsgruppen und aktuelle Befunde |
| [Aktualisierungsbericht](test-coverage/product/current-review.md) | Neue Funktionen, behobene Befunde und verbleibende Grenzen |
| [Laufbericht](test-coverage/findings.md) | Aktuelle Fehler und Ausführungsgrenzen |
| [Testanleitung](testing.md) | Einrichtung und sichere Befehle |
| [Inventar](test-coverage/inventory.json) | Jede Definition, Assertionstelle, jeder Runnerfall und Dateistatus |
| [Laufmetadaten](test-coverage/execution.json) | Befehle, Umgebung, Ergebnisse und Nachweise |
| [Auditverfahren](test-coverage/next-audit.md) | Anforderungen, Negativkontrollen und Pflege |

## Laufstand vom 02.10.2026

| Suite | Dateien | Definitionen | Runnerfälle | Ergebnis |
|---|---:|---:|---:|---|
| Pytest | 152 | 2.355 | 3.081 | 3.078 bestanden, 3 fehlgeschlagen |
| Vitest | 72 | 556 | 664 | 664 bestanden |
| Pytest-E2E | 30 | 157 | 308 | 219 bestanden, 30 fehlgeschlagen, 4 Setupfehler, 55 nicht ausgeführt |
| **Gesamt** | **254** | **3.068** | **4.053** | **3.961 bestanden, 33 fehlgeschlagen, 4 Setupfehler, 55 nicht ausgeführt** |

`npm run build:check` bestand. Drei lokale dist-Änderungen waren vor dem Auftrag
vorhanden und wurden nicht verändert; Browserresultate beziehen sich auf diesen
aktuellen lokalen Build. Der Quellstand wurde weder gefetcht noch umgeschaltet.

Der Benchmark-Resume-Fall bestand isoliert nach Manifestdrift im Gesamtlauf;
der Publisher-Test scheiterte auch isoliert in seiner Ergebnisprüfung.
Primärlaufzahlen bleiben unverändert. Alle roten IDs: [Laufbericht](test-coverage/findings.md).

253 E2E-Fälle wurden versucht. Vier benötigen den nicht gestarteten Emulator
und endeten im Setup. Die 55 nicht ausgeführten Fälle sind 43 integrierte
Smoke-Fälle und zwölf Transaktionsfälle.

## Neue Funktionen

Google/OAuth mit PKCE, getrennten Scopes und Datenzustimmung; Kalender-/Gmailaktionen
mit exakter Inhaltsbestätigung; private Agent-Dateien und DOCX/PDF-Versionen;
gemeinsames Tokenkonto samt Nachmessung; autoritative Antwortreceipts und
typisierte Abschlusszustände; belegbasierte Watches/Topics mit Recheck,
Zielabschluss, Probes und Outbox; ein Modusselektor/Agentpicker,
inkrementelles Markdown, Quellenpillen und Komprimierung ohne SSE-Pufferung.
Die konkrete Zuordnung steht im [Produktabgleich](test-coverage/product/README.md).

## Aussagegrenzen

Dateieinträge unterscheiden formulierte Assertions und bestandenen Lauf.
„Nicht in dieser Datei geprüft“ heißt nicht „nirgendwo geprüft“. Mocks,
Fixtures, Teilbelege und verbleibende Prüfaufträge stehen jeweils dabei.

`tests/conftest.py` ersetzt standardmäßig Promptconfig, Memory sowie nun auch
Tokenkontotarif/Adminrolle. Agenttests erhalten historische 250.000-Token-Defaults;
Tariftests überschreiben die Seams. Grüne Agenttests bestätigen nicht automatisch
produktive Tarifwerte. jsdom belegt kein Browserlayout; API-Doubles belegen
keinen tatsächlichen DB-Write oder Googleversand. Kein Lauf prüft Live-Modellqualität,
Cloud-IAM, produktive Zustellung oder vollständige visuelle/Accessibility-Abdeckung.

Templatebasierte Vitest-Registrierungen werden jetzt statisch erfasst; eine
Definition kann durch Schleifen/Parametrisierung mehrere Fälle erzeugen.
`report_ordinal` unterscheidet gleiche Runnernamen innerhalb eines Snapshots.
Assertionanker sind syntaktische Suchhilfen, keine Wirksamkeitsbewertung.

## Pflege und Historie

```powershell
venv/Scripts/python.exe docs/test-coverage/check_inventory.py
venv/Scripts/python.exe docs/test-coverage/product/check_product_audit.py
```

Node und installierte Repoabhängigkeiten werden für den JS-AST-Abgleich benötigt.
Die Checker kontrollieren Dateien, Hashes, Definitionen, Assertionstellen,
Zuordnung und Nachweise; sie führen keine Tests aus und bewerten Text nicht neu.
Generiertes dist wird separat durch `build:check` geprüft.
Nach inhaltlicher Aktualisierung:

```powershell
venv/Scripts/python.exe docs/test-coverage/render_catalog.py
venv/Scripts/python.exe docs/test-coverage/product/render_product_audit.py
```

[Historische Läufe](test-coverage/execution-2026-09-26.json) bleiben erhalten,
ebenso `historical_execution` je Datei und `retired_files` im Inventar.
Die alte Gesamtdokumentation liegt in Git (`a448baa7`). Coverage/Mutationsproben
vom 26.09.2026 sind **keine aktuelle Messung**. Datum/Hashes allein zu ersetzen
macht Beschreibungen nicht aktuell.

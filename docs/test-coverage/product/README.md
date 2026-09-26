# Produktabdeckung und Codex-Übergabe

**Audit: 26.09.2026 · Repositorystand: `cca637b9139032aa74a44acd20b39cde710ae159`**

Diese Ergänzung verbindet den vorhandenen [Katalog aller 216 Testdateien](../../test-coverage-map.md)
mit dem Produktcode. Sie enthält eine Verhaltensmatrix, suiteweit gegengeprüfte
Lücken und konkrete Implementierungsaufträge. In diesem Auftrag wurden
**keine Produktkorrekturen oder neuen Regressionstests implementiert**.
Die kleinen Auditproben sind separat gespeichert und werden von den normalen
Test-Runnern nicht gesammelt.

## Einstieg für Codex

1. `python docs/test-coverage/check_inventory.py` und
   `python docs/test-coverage/product/check_product_audit.py` ausführen.
   Bei Änderungen seit dem Audit betroffene Quellen/Tests neu prüfen.
2. Ein [Arbeitspaket](work-packages.md) auswählen, seine Abhängigkeiten,
   [Befunde](gaps.md), [Verhaltensbelege](matrix.md) und
   [Oracle-Hinweise](decisions.md) lesen.
3. Die benannte Grenze tatsächlich ausführen. Given/When/Then und
   Negativkontrolle liefern die Abnahme; vorhandene Tests/Helfer bevorzugen.
4. Ergebnis mit Commit, Befehlen, Pass/Fail/Skip und verbleibender Testgrenze
   dokumentieren. Nachweise historisch erhalten und neue Bewertungen bewusst
   ergänzen. Ein grüner Publisher-Workflow allein bestätigt keine Gesamtsuite.

| Dokument | Zweck |
|---|---|
| [matrix.md](matrix.md) | 77 gruppierte Verhaltensverträge, 83 konkrete exemplarische Testdefinitionen samt Assertionstellen; alle 216 Testdateien zugeordnet |
| [sources.md](sources.md) | 269 Produkt-/Betriebsdateien mit Vertragszuordnung und gemessener Pythonausführung |
| [routes.md](routes.md) | 158 registrierte App-Routeneinträge und 4 Frameworkrouten, einschließlich dynamischer Ask-Endpoints |
| [gaps.md](gaps.md) | 36 Befunde mit Codebeleg, bestehenden Prüfungen, Suchspur, Given/When/Then und Negativkontrolle |
| [work-packages.md](work-packages.md) | 30 geplante Pakete mit Abhängigkeiten, Zielstellen, Wiederverwendung und Abnahme |
| [journeys.md](journeys.md) | Acht schichtenübergreifende Abläufe, vorhandene Belege und noch getrennte Testgrenzen |
| [decisions.md](decisions.md) | Aktuelle und veraltete Testoracles, offene Produktentscheidungen, Modellqualität und vermiedene Fehlbefunde |
| [measurements.md](measurements.md) | Neuer Python-Branchlauf, zwei Mutations- und zwei DOM-Proben mit Wiederholungsanleitung |
| [audit.json](audit.json) | Kanonische manuell bewertete Verträge, Befunde und Paketstatus |
| [search-evidence.json](search-evidence.json) | Reproduzierbare Regex-Suchspuren über 224 versionierte Test-/Hilfsdateien |
| [sources.json](sources.json), [routes.json](routes.json) | Dateihashes, Python-Symbolfundstellen und Runtime-Routen |
| [python-coverage.json](python-coverage.json), [execution.json](execution.json) | Ausführungsdaten und Herkunft; keine semantische Coveragequote |

## Wichtigste Ergebnisse

Der neue reguläre Pythonlauf bestätigt den bekannten Stand: **2.717 bestanden,
1 fehlgeschlagen, 12 Windowsfälle übersprungen**. Die Messung erreicht
**83,37 % Statements** und **74,58 % Branches** im instrumentierten Pythonumfang.
Diese Zahlen messen Ausführung, einschließlich Code vor der bekannten
fehlgeschlagenen Assertion. Sie messen nicht die fachliche Wirksamkeit der Tests.

Die beiden gezielten Mutationen zeigen diesen Unterschied:

- **G-007:** Ein entfernter Undo-Revisionsschutz bleibt in allen 14 ausgewählten
  Memory-Edit-Tests unentdeckt.
- **G-020:** Ein vollständig weißes, gültiges PNG besteht beide vorhandenen
  OG-Kartentests.

Zwei weitere lokale Proben zeigen konkrete Verhaltensfehler:

- **G-018:** Eine Topic-Notiz mit inertem HTML-Text wird beim Anzeigen wieder als
  Markup interpretiert. Die Probe belegt Text→Element-Konvertierung, keinen
  ausgeführten externen Angriff.
- **G-019:** Der Adminclient zeigt den tatsächlichen strukturierten
  `error`-Umschlag der App als `[object Object]` statt als verständliche Nachricht.

Weitere wichtige Aufgaben betreffen regelgeprüfte Firestore-Clients, reguläre
Usage-Transaktionen, Kontolöschung gegen späte Writes, API-Recovery und echte
HTTP-Adapter hinter vorhandenen Service-Fakes. Die **267 Browserfälle** bleiben
aus dem vorherigen Audit ohne Laufnachweis; sie sollen ausgeführt und bewertet,
nicht pauschal neu geschrieben werden. Der neue Auftrag wiederholt weder den
fehlgeschlagenen Chromium-Download noch die bisherigen Vitest-/Emulatorläufe.

## Umfang und Methode

Der geprüfte Commit ergänzt nur die vorherige Dokumentation. Produkt- und
Testquellen entsprechen weiterhin `145db25bfe029ff7f50cd77595bd6b9e043c1a2f`.
Hashes und Gitvergleich sichern diese Aussage ab.

Das Dateiinventar umfasst versionierte `.py`, `.js`, `.mjs`, `.html`, `.css`,
`.json`, `.yml`, `.ps1` und `.rules` unter `app/`, `benchmark/`, `scripts/`,
`templates/`, `static/js/`, `static/css/` und `.github/workflows/` sowie
`main.py`, `static/firebase.js`, `static/app-ui.js`, `static/demo.js`,
`static/style.css`, `dev.ps1`, `firebase.json`, `firestore.rules`,
`firestore.indexes.json`, `package.json` und `vitest.config.mjs`.
Das sind **269 Dateien und 128.351 physische Quellzeilen**.

Generierte Bundles, vendorte Bibliotheken, Fonts/Bildassets, historische
Benchmark-/Evaluationsartefakte und Datensätze sind keine separat bewerteten
Produktquellmodule. Ihre relevanten Lade-/Build-/Datasetverträge sind über
BUILD/UI/BENCH berücksichtigt. Requirements, Locks, Runnerkonfiguration und
gemeinsame Fixtures sind zusätzlich im vorhandenen Testinventar gehasht.
Deploymentkonfiguration außerhalb der genannten Auswahl und produktive
Provider-/Datenbankzustände sind kein vollständig erfasstes Auditobjekt.

Die Verhaltensmatrix wurde aus tatsächlichen Modulen, Routern, Zustandswechseln
und dokumentierten Anforderungen formuliert und gegen Testkörper/Assertions
geprüft. Die **77 Zeilen sind bewusst gruppierte Verträge**. Sie sind weder
eine Aufzählung jedes möglichen Eingabefalls noch der Nachweis, dass alle
Produktanforderungen abschließend formalisiert sind. Besonders umfangreiche
CSS-/Templatebereiche bleiben Sammelbereiche mit klar benannter visueller Grenze.
Alle erfassten Dateien haben eine Zuordnung; daraus wird keine grüne Freigabe
jeder Funktion abgeleitet.

Für Lücken wurden benachbarte Tests, gemeinsame Fixtures, browserseitige
Routeersetzungen, Testhelfer und Quelltextprüfungen suiteweit abgeglichen.
`search-evidence.json` bewahrt sämtliche passenden Zeilen zu den dokumentierten
Suchbegriffen. Ein Nulltreffer allein wäre kein ausreichender Lückenbeleg.
Der Pythonlauf ergänzt diese Prüfung durch tatsächlich nicht ausgeführte
Methoden/Zweige; zwei gezielte Mutationen und zwei DOM-Proben prüfen konkrete
Gegenbeispiele. Eine automatische semantische Bewertung aus Dateinamen,
Importgraph oder Coveragewert wurde nicht vorgenommen.

## Aktualisierung und Grenzen

`audit.json` ist die kanonische Bewertung; `sources.json`, `routes.json`,
`search-evidence.json` und die Messdaten sind zugehörige Snapshots. Nach einer
inhaltlichen Aktualisierung:

```bash
python docs/test-coverage/product/render_product_audit.py
python docs/test-coverage/product/render_product_audit.py --check
python docs/test-coverage/product/check_product_audit.py
```

Der Checker prüft Inventar, Hashes, konkrete Fundstellen, Zuordnungen,
Suchspuren, Routen-/Paketreferenzen, Abhängigkeiten und erzeugte Seiten.
Er bewertet weder die fachliche Richtigkeit einer neuen Beschreibung noch die
Qualität einer Assertion automatisch. Fehlende/grüne Laufnachweise werden
dadurch nicht erzeugt. Pythonmessung erfasst keine JavaScript-/Browserbranches,
kein automatisches Python-Subprozess-Coverage und keine Live-Modellqualität.
Zwei überlebende Mutationen sind keine suiteweite Mutationsquote.

Die Paketfolge ist eine begründete Umsetzungsempfehlung. Die abschließende
Qualitätsbeurteilung verlangt zusätzlich eine nach den Änderungen erneut
geprüfte Gesamtmatrix, aktuelle Runnerstatus und die in
[decisions.md](decisions.md) getrennt beschriebene fachliche Modellevaluation.

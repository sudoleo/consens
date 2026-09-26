# Messungen und gezielte Auditproben

[Einstieg](README.md) · [Ausführungsmetadaten](execution.json) ·
[Pythonbericht](python-coverage.json)

## Regulärer Python-Branchlauf

| Größe | Ergebnis |
|---|---:|
| Tests | 2.717 bestanden, 1 fehlgeschlagen, 12 übersprungen |
| Laufzeit | 62,44 s |
| Statements | 23.236 / 27.872 = 83,37 % |
| Branches | 6.836 / 9.166 = 74,58 % |
| Fehlende Statements / Branches | 4.636 / 2.330 |
| Ausgeschlossene Statements | 64 |
| Partiell ausgeführte Branchstellen | 1.556 |
| Python / coverage.py | 3.12.14 / 7.16.1 |

Der bekannte Fehler ist weiterhin
`tests/test_consensus_progress_ui.py::test_archived_turns_use_the_same_drawer_row_as_the_live_answer`
([G-028](gaps.md#g-028)). Alle zwölf Skips stammen aus `test_dev_cli.py` und
benötigen Windows. Das [aufbewahrte Runnerprotokoll](evidence/python-branch-run.txt)
enthält Fehler und Skipgründe. Es bewahrt historische lokale Ausgabepfade;
nur nachgestellte Leerzeichen wurden für den Dokumentdiff entfernt.

Instrumentiert wurden `app`, `benchmark`, `scripts` und `main`, ausschließlich
während des regulären Pytestlaufs. Der kompakte JSONbericht enthält die Daten
aller 136 von coverage.py gemeldeten Dateien: ausgeführte/fehlende Statements,
Branches und vollständig unausgeführte Funktionskörper als Suchkandidaten.
Nicht importierte, von coverage.py nicht entdeckte oder nicht instrumentierte
Dateien bleiben über [sources.json](sources.json) sichtbar.
Eine Klasse-/Funktionsdefinition auszuführen bedeutet nicht, ihren Körper
fachlich geprüft zu haben. Subprozesse und dynamisch kompilierte Ersatzfunktionen
können außerhalb der Zuordnung liegen. Es wurden keine per-Test-Kontexte erfasst.

Wiederholung in einer isolierten Testumgebung mit den Repo-Abhängigkeiten aus
[docs/testing.md](../../testing.md), zusätzlich `coverage==7.16.1`:

```bash
mkdir -p test-results/product-audit
export COVERAGE_FILE="$PWD/test-results/product-audit/.coverage"
env -u RUN_E2E UNIT_TEST_MODE=1 \
  OPENROUTER_API_KEY=audit-placeholder-not-a-real-key \
  python -m coverage run --branch --source=app,benchmark,scripts,main \
  -m pytest tests -q -rs \
  --junitxml=test-results/product-audit/pytest.xml
python -m coverage json -o test-results/product-audit/coverage.json
unset COVERAGE_FILE
```

Der erste Lauf liefert auf dem Auditstand wegen G-028 Exitcode 1. Den
Coveragebericht anschließend bewusst erzeugen; den Fehler nicht durch
`|| true` als Erfolg ausgeben. Der neue Bericht ist eine neue Messung und darf
den historischen Snapshot erst nach geprüftem Vergleich ergänzen/ablösen.

## Mutationsproben M-01 und M-02

Die Proben ändern ausschließlich importierte Objekte im kurzlebigen Pytestprozess.
Sie schreiben keine Produktdatei und sind keine normale Suiteerweiterung.
[assertion_probe.py](probes/assertion_probe.py) ist nur über die folgenden
expliziten Aufrufe aktiv. Vorher den Auditchecker ausführen.

| Probe | Änderung | Auswahl | Ergebnis | Schlussfolgerung |
|---|---|---|---|---|
| M-01 | Genau eine Undo-Bedingung `current_revision != …` wird im AST auf `False` gesetzt | gesamte `test_memory_edit.py` | 14 bestanden | Bestehende Auswahl entdeckt den fehlenden Konfliktschutz nicht |
| M-02 | OG-Renderer liefert gültiges weißes 1200×630-PNG | `test_share_feature.py -k og_card` | 2 bestanden, 149 deselected | Format-/Statusassertions sichern den sichtbaren Inhalt nicht |

```bash
env PYTHONPATH=docs/test-coverage/product/probes:. \
  UNIT_TEST_MODE=1 OPENROUTER_API_KEY=audit-placeholder-not-a-real-key \
  AUDIT_PROBE=memory_undo_revision \
  python -m pytest tests/test_memory_edit.py -p assertion_probe -q

env PYTHONPATH=docs/test-coverage/product/probes:. \
  UNIT_TEST_MODE=1 OPENROUTER_API_KEY=audit-placeholder-not-a-real-key \
  AUDIT_PROBE=og_blank \
  python -m pytest tests/test_share_feature.py -k og_card -p assertion_probe -q
```

Die gespeicherten [Memory-](evidence/probe-memory.xml) und
[OG-JUnitdaten](evidence/probe-og.xml) enthalten die tatsächliche Auswahl.
Keine Aussage über nicht ausgewählte Tests oder äquivalente/ungetestete andere
Mutationen. Nach Umsetzung von WP-10/WP-23 muss die passende Negativkontrolle
scheitern. Bei neuem Renderer-Test in `test_og_image.py` die M-02-Auswahl
entsprechend erweitern; das alte `-k og_card` sammelt neue anders benannte Tests
nicht automatisch.

## DOM-Proben D-01 und D-02

```bash
node docs/test-coverage/product/probes/dom-probes.mjs
```

Die Probe lädt die tatsächlichen Frontendmodule, verwendet jsdom 24.1.3 und
vollständig synthetische Daten. Sie protokolliert Verhalten und ist kein
bestandener Regressionstest für das gewünschte Verhalten.

| Probe | Eingabe | Beobachtung auf dem Auditstand |
|---|---|---|
| D-01 | `Literal <b id="audit-inert-marker">example</b> text` als Topic-Notiz; Fokusereignis | Ein echtes `b`-Element entsteht, sichtbarer Text verliert die literalen Tags |
| D-02a | `{detail: {error_code: "not_found", message: "Account was not found"}}` | verständliche Nachricht |
| D-02b | `{error: {error_code: "not_found", message: "Account was not found"}}` | `[object Object]` |
| D-02c | `{error: "Account was not found"}` | verständliche Nachricht |

D-01 führt keinen Scriptpayload aus. D-02 ersetzt `fetch`; es gibt keine
externen Requests oder echten Tokens. Der Umschlag von D-02b entspricht
`main.handle_http_exception`; deshalb reicht die bestehende Browserfixture
mit `detail: String` als Gegenbeleg nicht aus.

## Getrennte Nachweise

Die früheren 515 bestandenen Vitestfälle, der Emulatorprimärlauf mit 9 Pass/3 Fail
und die 267 nicht ausgeführten Browserfälle bleiben in
[../execution.json](../execution.json) erhalten. Es wurde in diesem Folgeaudit
keine neue JS-/Browser-/Emulator-Coverage erhoben. Die vorherige Java17-Umgebung
entspricht außerdem nicht der für künftige Reproduktion dokumentierten
Java21-Voraussetzung; der Report-Race bleibt bis WP-02 ungeklärt.

Nächste Messung: JS-Branchinstrumentierung passend zur vorhandenen Vitestversion
einrichten, Quellmodule und ausgeführte Bundles sauber zuordnen und
ausgeschlossene Module explizit zeigen. Browser-/Backend-/Unitberichte getrennt
halten; Imports, Mock- oder Buildausführung nicht zu einer gemeinsamen
fachlichen Prozentzahl vermischen. Eine CI-Schwelle erst mit stabiler Basis
und nachvollziehbaren Ausnahmen festlegen. Fachliche Lücken bleiben anhand
von Gegenbeispielen/Assertions zu entscheiden.

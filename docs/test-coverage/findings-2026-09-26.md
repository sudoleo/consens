# Laufbefunde und Grenzen

Stand: 26.09.2026, Commit `145db25bfe029ff7f50cd77595bd6b9e043c1a2f`.
[Zum Katalog](../test-coverage-map.md).

## Nachgewiesene Auffälligkeiten

### F-01: Starrer Quelltextvertrag für historische Drawer

`tests/test_consensus_progress_ui.py::test_archived_turns_use_the_same_drawer_row_as_the_live_answer`
scheitert auch nach Korrektur der Testumgebung.

- [Assertion, Zeile 335](../../tests/test_consensus_progress_ui.py#L335):
  erwartet exakt `tab.className = "consensus-tab"`.
- [Implementierung, Zeile 400](../../static/js/consensus-run.js#L400):
  setzt `tab.className = "consensus-tab consensus-evidence-action"`.

Der literal geprüfte Vertrag ist veraltet oder muss gegen die gewünschte
Darstellung neu bewertet werden. Die zusätzliche Klasse allein beweist keinen
UIfehler. Im Folgeaudit zuerst das erwartete Verhalten und die korrespondierenden
Browserfälle prüfen; keinen Test allein für einen grünen Lauf abschwächen.

### F-02: Watch-Transaktionstest erreicht die Transaktion nicht

`tests/e2e/test_phase2_transactions.py::test_two_workers_cannot_exceed_owner_watch_limit`
scheitert mit `TypeError: create_watch() got an unexpected keyword argument 'is_pro'`.

Der [Testaufruf](../../tests/e2e/test_phase2_transactions.py#L52) übergibt
`is_pro=False`; die [aktuelle Funktion](../../app/services/watch_service.py#L388)
verlangt `tier`. Damit ist der in dieser Datei formulierte Racevertrag aktuell
nicht durch einen bestandenen Lauf belegt. Andere Watchtests können Teilaspekte
abdecken; das muss vor einer globalen Lückenbewertung zugeordnet werden.

### F-03: Pending-Share-Fixture erfüllt den Ablaufzeitvertrag nicht

`tests/e2e/test_phase2_transactions.py::test_two_workers_publish_one_pending_share_and_consume_one_quota`
scheitert mit `ShareError: Result not found or expired.`.

Die [Fixture](../../tests/e2e/test_phase2_transactions.py#L98) enthält kein
`expires_at`. Die [Produktionsfunktion](../../app/services/share_snapshots.py#L1037)
verlangt eine gültige Ablaufzeit und bricht vor dem Publikationstransaktionspfad
ab. Der Test muss im Folgeauftrag mit dem aktuellen Pending-Result-Vertrag
abgeglichen werden; die eigentliche konkurrierende Veröffentlichung wurde hier
nicht erfolgreich nachgewiesen.

### F-04: Unterschiedliche Ergebnisse bei parallelen Share-Meldungen

`tests/e2e/test_phase2_transactions.py::test_parallel_reports_never_lose_increments_or_noindex_transition`
scheitert im gemeinsamen Emulatorlauf:

```text
Aborted: Transaction lock timeout.
ValueError: Failed to commit transaction in 12 attempts.
```

Ein anschließender isolierter Lauf desselben unveränderten Tests mit frisch
gestartetem Emulator besteht in 19,41 Sekunden. Es liegt somit eine beobachtete
Instabilität vor; eine konkrete Ursache wie Testreihenfolge, Emulatorlast oder
Anwendungsfehler ist **noch nicht bestimmt**. Beide Ergebnisse bleiben im
Inventar erhalten. Die Primärlaufstatistik zählt den Fehler weiterhin.

Betroffen: [Test](../../tests/e2e/test_phase2_transactions.py#L161),
[`report_share`](../../app/services/share_snapshots.py#L1770) und
[Transaktionswrapper](../../app/services/share_snapshots.py#L734).

## Ausführungsumfang

| Lauf | Ergebnis | Einordnung |
|---|---|---|
| Reguläre Python-Suite | 2.717 bestanden, 1 fehlgeschlagen, 12 übersprungen; 32,56 s | Vollständige 2.730 gesammelte Fälle |
| JavaScript | 515 bestanden | Alle 57 Dateien |
| Emulator: Agent, Phase 2, Promptkonfiguration | 9 bestanden, 3 fehlgeschlagen; 44,18 s | Alle 12 Fälle dieser drei Dateien |
| Isolierter Wiederholungslauf F-04 | 1 bestanden; 19,41 s | Zusätzlicher Versuch, kein zusätzlicher Testfall im Bestand |
| Browser | 267 gesammelt, nicht ausgeführt | Chromiuminstallation blockiert |
| Windows-CLI | 12 Fälle übersprungen | Linuxumgebung; ausdrücklich `Windows PowerShell entry point` |

Die Browserinstallation über `python -m playwright install chromium` lieferte
für Chrome for Testing 148.0.7778.96 / Chromium v1223 wiederholt ein unbrauchbares
Archiv (`End of central directory record signature not found`, Downloadanzeige
0 MiB). Es stand kein lokales kompatibles Browserbinary zur Verfügung. Die
Browserdateien wurden inhaltlich geprüft und gesammelt; ihre Verhaltens- und
Layoutassertions sind durch diesen Audit **nicht als bestanden bestätigt**.

Der Emulatorlauf nutzte Firebase CLI 13.35.1, Firestore-Emulator 1.19.8 und
Java 17.0.20. Die Repository-Anleitung verlangt Java 21; dieser Lauf ist daher
kein Nachweis unter exakt der dort empfohlenen Javaumgebung. Für F-04 ist eine
Wiederholung in der vorgesehenen Umgebung Bestandteil der Ursachenprüfung.

## Reproduktionsumgebung

Linux, Python 3.12.14, Node 24.19.0, npm 11.9.0. Die Pythonumgebung wurde aus
`requirements-e2e.txt` und `benchmark/requirements-benchmark.txt` aufgebaut;
JavaScriptabhängigkeiten aus dem Lockfile mit `npm ci --ignore-scripts`.
Ein gebautes Frontend lag für die quell-/assetbezogenen Prüfungen vor.
Relevante Paketversionen und Befehle stehen in [execution.json](execution.json).

Die reguläre Suite wurde mit `UNIT_TEST_MODE=1` und dem expliziten Dummywert
`OPENROUTER_API_KEY=audit-placeholder-not-a-real-key` ausgeführt. Ein erster
Diagnoselauf ohne diesen Wert, ohne Benchmarkpakete und mit flacher Githistorie
hatte zusätzliche Fehler. Nach Installation der Benchmarkpakete, vollständigem
Git-Fetch und Dummykey blieb F-01 übrig. Es wurden dafür keine Test- oder
Produktdateien geändert.

Das zeigt auch eine spätere Auditfrage zur Testisolation: Mehrere Endpointtests
benötigen diesen Umgebungswert trotz ersetzter Provider. Der Asset-Cachevertrag
benötigt verlässliche Githistorie. Solche Voraussetzungen müssen im Folgeauftrag
explizit abgesichert oder korrekt dokumentiert werden.

Für Emulatorprüfungen wurden `E2E_TEST_MODE=1`, `RUN_E2E=1`,
`FIRESTORE_EMULATOR_HOST=127.0.0.1:8085` und ausschließlich das Projekt
`demo-consensio-e2e` verwendet. `GOOGLE_APPLICATION_CREDENTIALS` wurde entfernt.
Emulator und Pytest liefen als Kindprozesse desselben lokalen Aufrufs. Ein
vorheriger Versuch in getrennten Ausführungsumgebungen wurde ohne verwertbares
Testergebnis beendet und wird nicht als Testfehler gezählt.

## Grenzen der Bestandsaufnahme

- Es wurden keine instrumentierte Zeilen-/Branch-Coverage, Mutationstests,
  Lasttests oder realen Providerqualitätsmessungen ausgeführt.
- Source-Contract-Tests werden im Katalog nach tatsächlicher Arbeitsweise
  beschrieben. Der vorhandene Pytest-Marker allein erfasst nicht zuverlässig
  jede statische Frontendprüfung.
- Ein Test kann eine Fake-Implementierung stark absichern und trotzdem den
  realen Adapter oder die Integration offenlassen. Die Dateieinträge benennen
  diese Grenzen; die globale Gegenprüfung folgt erst im nächsten Auftrag.
- Die Beschreibungen fassen Assertions zusammen. Sie ersetzen weder die
  Produktanforderungen noch das erneute Lesen des Codes bei Änderungen.

## Dokumentationsabweichungen im Ausgangsstand

Der einleitende Altkommentar von [test_smoke.py](../../tests/e2e/test_smoke.py)
nennt unter anderem Anhänge und Followups als nicht abgedeckt. In derselben
Datei existieren inzwischen entsprechende Tests. Der Katalog folgt deren
tatsächlichem Inhalt.

Der CI-Abschnitt von `docs/testing.md` behauptete, es gebe keine Test-CI.
Tatsächlich führt [publisher-tests.yml](../../.github/workflows/publisher-tests.yml)
die Standalone-Publishertests bei Push auf main, PR und manueller Auslösung aus;
[publish-consensus.yml](../../.github/workflows/publish-consensus.yml) führt
dieselben Tests vor dem Publisher aus. Dieser Widerspruch wurde bei der
Verlinkung des Katalogs korrigiert. Die Publisherprüfungen sind bereits im
regulären Dateiinventar enthalten und werden nicht doppelt gezählt.

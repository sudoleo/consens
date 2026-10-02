# Umsetzung: Runtime, Werkzeuge und gemeinsame Gates

Die folgenden Einzel- und Zwischenläufe dokumentieren die Umsetzung in ihrer damaligen Reihenfolge. Damalige Hinweise auf noch folgende Emulator-/CI-/Gesamtprüfungen werden durch die integrierte Abnahme am Ende dieses Berichts aktualisiert.

Stand 02.10.2026, Ausgangsstand `73e39d96`. Dieser Bericht ergänzt die
historische Bestandsaufnahme; die zusammengeführte Abnahme wird im Audit erfasst.

| Paket | Änderung und Beleg | Negativkontrolle / Grenze |
|---|---|---|
| WP-04 | `dev.ps1` bietet `rules`, stellt UTF-8 und alle geerbten Umgebungswerte wieder her. 28 CLI-Fälle unter pwsh und Windows PowerShell bestanden. Reale Backendausführung: 22 bestanden; reale Frontendausführung: sieben bestanden. | Fehlercodes/Emulator-Teardown/Umgebungsrestore werden durch echte Subprozesse geprüft. Der erste Buildcheck erkannte nach Dependencyänderung korrekt ein veraltetes Manifest; Neubau und erneuter Buildcheck bestanden. Reale Emulator-Einstiege folgen im integrierten Lauf. |
| WP-05 | Vier Actions-Jobs für Python, JS/Build, Emulator/Chromium/Regeln und Windows eingerichtet; Publisherjobs bleiben bestehen. Keine Fehlerunterdrückung, Artefakte auch nach Fehler. | YAML und Jobgrenzen lokal geprüft. Ein erfolgreicher GitHub-Lauf auf dem integrierten Commit ist zusätzlich nötig. |
| WP-06 | 49 Node-Tests mit echtem Firebase-Client gegen Emulator 1.19.8 bestanden. Anonym, Owner, fremde Identität und Admin-Claim: Lesen, Query, Set, Update und Delete von zwölf Pfaden aus den tatsächlichen Service-Collections verweigert. | Temporär erlaubter Ownerwrite lässt dieselbe Denial-Assertion scheitern; Regeln werden im `finally` wiederhergestellt. Admin dient nur Seed/Teardown eigener IDs. Kein produktiver Rules-/IAM-Deploytest. |
| WP-25 | Reparatur- und Backfill-Entry-Points laufen in netzwerkgesperrten Subprozessen. Projekt-/Apply-/Emulatorguards, ausgewählter Account, Datenerhalt, Wiederholung und Force geprüft. Backfill erhält bestehende Teilkeys und zählt Dry-run-Änderungen korrekt. | Ausgangsstand: zwei rote Regressionen für überschriebenen Key und falsche Vorschauanzahl. Entfernte Apply-Sperre wird als unerlaubter Recovery-Aufruf erkannt. Dry-run des Backfills kann weiterhin den Judge kostenpflichtig aufrufen; Tests ersetzen ihn. |
| WP-26 | ASGI-Limit-Randwerte und echter Abbruch vor vollständigem Body geprüft. Ein abgebrochener gültiger JSON-Präfix wird nicht mehr als vollständiger Request weitergereicht. Reale TCP-/TLS-Tests für Providerabbruch vor Headern/im Stream, SDK-Deadline, Host/SNI, Redirectvalidierung und gzip-Budget. | Neue Disconnect-Regression war vorher rot. Aktivierte SDK-Retries werden über zwei tatsächliche Serverrequests erkannt. Öffentliche Quellen/Provider und Deployment-Proxies sind keine Testziele. |
| WP-28 | `run_sample`/`run_experiment` bleiben unterstützt. Argumente werden vor Dataset-/Providerarbeit validiert; Dry-run und Live sind exklusiv, Budget endlich/positiv und Run-ID ein einzelner Verzeichnisname. Echte Runner-/Manifest-/Record-/Resume-/Resultpfade mit lokalen Daten ausgeführt. | Entfernte Budgetvalidierung startet verbotene synthetische Providerarbeit und wird erkannt. Netzwerk in den Subprozessen gesperrt; kein Qualitätsnachweis bezahlter Modelle. |
| WP-34 | HTTP-200-Fehlerobjekte und ungültige Responseformen werden als Fehler bis Record, Resume und Statistik erhalten. Gültiger Text ohne Auswahl bleibt Enthaltung. Private Provider-/Exceptiontexte werden nicht in Fehlerrecords geschrieben. | Ausgangsstand neun neue Tests rot, nach Korrektur grün; Auswahl/Enthaltung sind Gegenkontrollen. Keine Aussage über Häufigkeit realer Providerfehler. |
| WP-38, Backend | Ursache der Manifestdrift: frische sekundengenaue Uhrzeit im Prompttemplate. Nur Datum/Uhrzeit/UTC-Offset werden normalisiert; Zeitzone/Prompt/Modell bleiben eingefroren, alte Dateien bleiben bytegleich. Publisher-Subprozesse nutzen explizit UTF-8 trotz `-E -S`. | Zwei deterministische Clock-Regressionen vorher rot; echte Konfigurationsdrift bleibt rot. Gesamtlauf und Browseranteil werden separat integriert. |

Gemeinsamer fokussierter Lauf:

```powershell
$env:UNIT_TEST_MODE = "1"
$env:PYTHONUTF8 = "1"
$env:OPENROUTER_API_KEY = "unit-dummy-key"
venv/Scripts/python.exe -m pytest tests/test_local_transport.py tests/test_benchmark_protocol.py tests/test_auxiliary_cli.py tests/test_request_body_limits.py tests/test_maintenance_scripts.py tests/test_benchmark_budget.py tests/test_benchmark_manifest_clock.py tests/test_publisher_standalone.py -q --junitxml=test-results/root-focused.xml
```

Ergebnis: **91 bestanden**, eine Python-3.9-DeprecationWarning, 72,48 s.
Zusätzlich bestanden 28 CLI-Vertragsfälle, 49 Rules-Fälle, die oben genannten
realen Windowsaufrufe sowie der Buildcheck. Lokale Runtime: Python 3.9.7,
Node 24.19.0 für Firebase/Regeln, Java 21.0.12.1, Firebase CLI 13.35.1,
Firestore-Emulator 1.19.8; kein Produktcredential oder echter Provider.

Die Inventarprüfung liest Node-/Git-Text nun explizit als UTF-8, damit derselbe
Prüfer auch ohne geerbtes `PYTHONUTF8` unter Windows funktioniert. Der
unveränderte Ausgangsaudit bestand beide Checker vor der Integration.

Die unabhängige Gegenprüfung fand zusätzlich eine Claim-Key-Kollision beim
Erhalt teilweise befüllter Runs: Bestehende Keys werden jetzt vorab reserviert,
Judge-Matches vor Fallbacks vergeben und Fallbackkollisionen deterministisch
aufgelöst. Zwei neue Regressionen waren davor rot. Die Rules-Pfade wurden mit
den tatsächlichen Repository-Collections abgeglichen; auch aktive lokale und
produktive Source-Queues sowie LLM-Receipts sind nun enthalten.

Nachgeschärfte Abnahme nach unabhängiger Kriterienprüfung:

- WP-19: Der wirkliche Topic-Scheduler führt native Due-Query, Claim und
  Runabschluss aus; eine zweite Variante belegt den Fehlerabschluss. Der
  wirkliche SEO-Loop persistiert einen externen Collectionfehler samt
  Benachrichtigungsstatus und gibt die native Lease frei. Cancellation an
  der nächsten Wartegrenze beendet beide Loops ohne weiteren Dispatch.
- WP-33: Mit und ohne bestehendes Konfigurationsdokument wird nach echter
  fehlgeschlagener Runtimeaktivierung der native Rollback-Commit gezielt
  abgewiesen. Der ursprüngliche Fehler bleibt sichtbar, ein kritischer
  Diagnoseeintrag weist auf den fehlgeschlagenen Rollback hin, der gespeicherte
  neue Stand wird nicht als wiederhergestellt ausgegeben, und die lokalen
  Runtimewerte entsprechen weiterhin dem vorherigen Snapshot.

Gemeinsamer Zusatzlauf der beiden nativen Dateien: **10 bestanden**,
19,52 s; ein dokumentierter SDK-Konkurrenzabbruch mit getrenntem Replay.
Der erste integrierte Backendlauf ergab 3.289 bestanden und eine veraltete
Cache-Key-Assertion. Diese prüft nun das versionierte Assetformat; der separate
Resilience-Test prüft weiterhin Aktualität und Konsistenz gegen Git.

Die native J-05-Browserreise deckte zusätzlich einen Agent-SSE-Abbruchfehler
auf: Verweigert ein Kontotombstone das Settlement beim Schließen des Producers,
konnte der Router während `GeneratorExit` noch einen Fehlerframe ausgeben.
Der Router bewahrt jetzt den Abbruch und protokolliert den sekundären
Cleanupfehler ohne weiteren Yield. Die gezielte Regression reproduzierte
zunächst `generator ignored GeneratorExit`; danach bestanden 66 benachbarte
Kapazitäts-, HTTP-, Reliability- und Streamingfälle.

Der erste vollständige Linux-E2E-Lauf zeigte außerdem eine Interferenz im
Testharness: Die synchrone Playwright-Session hält im Pytest-Thread bereits
eine Ereignisschleife aktiv. Die drei nativen Scheduler-Loop-Fälle konnten
dort kein weiteres `asyncio.run()` starten. Sie führen die unveränderten
Scheduler nun in einem eigenen Thread mit eigener Schleife aus; Exceptions
werden an den Test zurückgegeben. Die gemeinsame Prüfung mit einer vorher
gestarteten Playwright-Session schützt diese Suite-Grenze.

Dieser Kombinationslauf belegte zudem einen bisher nicht erfassten nativen
Lockabbruch beim Lesen innerhalb einer Transaktion: Die SDK gab `Aborted`
direkt weiter, während ein ausgeschöpfter Commitretry als `ValueError` mit
`Aborted`-Ursache erscheint. Der Testhelfer erfasst beide konkreten Formen,
meldet den Abbruch weiterhin als Warnung und prüft bei ausschließlich
abgebrochenen Versuchen den unveränderten Datenstand. Erst danach folgt der
bereits dokumentierte einzelne explizite Wiederholungsversuch. Andere Fehler
werden nicht abgefangen; die Produkt-Retrybudgets bleiben unverändert.

Der gemeinsame Lauf von `test_agreement_verdict.py` und
`test_scheduler_transactions.py` bestand danach mit **7 passed** in 26,66 s
(`test-results/integrated/scheduler-playwright-fixed.xml`).

## Integrierte Abnahme vom 02.10.2026

Zusammengeführter Code `ffaca3df`. Python: 3.303 bestanden; JavaScript: 705 bestanden; Chromium / native SDK / Smoke: 368 bestanden; Firestore-Clientregeln: 49 bestanden. Die tatsächlichen Befehle und Quellstände pro Lauf stehen in [execution.json](../execution.json); dieser Abschluss ersetzt keine historischen Primärergebnisse. [Aktueller Paketstatus](work-packages.md) und [Laufbericht](../findings.md) sind für die heutige Abnahme maßgeblich.

38 der 38 Arbeitspakete sind vollständig abgenommen. Die in den Berichten benannten Betriebsgrenzen bleiben ausdrücklich bestehen.

Die realen Windows-Einstiege einschließlich beider Shells, Rules und nativer Phase2 liefen [im GitHubjob](https://github.com/sudoleo/consens/actions/runs/36995379657/job/110800783247) auf `ffaca3df` erfolgreich.

# Umsetzung: Runtime, Werkzeuge und gemeinsame Gates

Stand 02.10.2026, Ausgangsstand `73e39d96`. Dieser Bericht ergänzt die
historische Bestandsaufnahme; die zusammengeführte Abnahme wird im Audit erfasst.

| Paket | Änderung und Beleg | Negativkontrolle / Grenze |
|---|---|---|
| WP-04 | `dev.ps1` bietet `rules`, stellt UTF-8 und alle geerbten Umgebungswerte wieder her. 28 CLI-Fälle unter pwsh und Windows PowerShell bestanden. Reale Backendausführung: 22 bestanden; reale Frontendausführung: sieben bestanden. | Fehlercodes/Emulator-Teardown/Umgebungsrestore werden durch echte Subprozesse geprüft. Der erste Buildcheck erkannte nach Dependencyänderung korrekt ein veraltetes Manifest; Neubau und erneuter Buildcheck bestanden. Reale Emulator-Einstiege folgen im integrierten Lauf. |
| WP-05 | Vier Actions-Jobs für Python, JS/Build, Emulator/Chromium/Regeln und Windows eingerichtet; Publisherjobs bleiben bestehen. Keine Fehlerunterdrückung, Artefakte auch nach Fehler. | YAML und Jobgrenzen lokal geprüft. Ein erfolgreicher GitHub-Lauf auf dem integrierten Commit ist zusätzlich nötig. |
| WP-06 | 37 Node-Tests mit echtem Firebase-Client gegen Emulator 1.19.8 bestanden. Anonym, Owner, fremde Identität und Admin-Claim: Lesen, Query, Set, Update und Delete von neun repräsentativen Pfaden verweigert. | Temporär erlaubter Ownerwrite lässt dieselbe Denial-Assertion scheitern; Regeln werden im `finally` wiederhergestellt. Admin dient nur Seed/Teardown eigener IDs. Kein produktiver Rules-/IAM-Deploytest. |
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
Zusätzlich bestanden 28 CLI-Vertragsfälle, 37 Rules-Fälle, die oben genannten
realen Windowsaufrufe sowie der Buildcheck. Lokale Runtime: Python 3.9.7,
Node 24.19.0 für Firebase/Regeln, Java 21.0.12.1, Firebase CLI 13.35.1,
Firestore-Emulator 1.19.8; kein Produktcredential oder echter Provider.

Die Inventarprüfung liest Node-/Git-Text nun explizit als UTF-8, damit derselbe
Prüfer auch ohne geerbtes `PYTHONUTF8` unter Windows funktioniert. Der
unveränderte Ausgangsaudit bestand beide Checker vor der Integration.

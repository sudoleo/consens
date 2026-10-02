# Integrierte Laufbefunde und Grenzen

**Stand: 02.10.2026 · Quellstand `ffaca3df` · Windows und Linux CI**

[Katalog](../test-coverage-map.md) · [Laufmetadaten](execution.json) ·
[Aktuelle Fehlerfälle](evidence/failures-implementation-2026-10-02.md) ·
[Negativkontrollenindex](evidence/negative-controls-implementation-2026-10-02.json) ·
[Stand vor der Umsetzung](findings-pre-implementation-2026-10-02.md)

| Suite | Dateien | Definitionen | Runnerfälle | Ergebnis |
|---|---:|---:|---:|---|
| Python | 169 | 2445 | 3303 | 3.303 bestanden |
| JavaScript | 77 | 579 | 705 | 705 bestanden |
| Chromium / native SDK / Smoke | 44 | 205 | 368 | 368 bestanden |
| Firestore-Clientregeln | 1 | 2 | 49 | 49 bestanden |

Die Zahlen stammen aus den endgültigen integrierten Runnerdateien. Vorherige
rote Primärläufe wurden dadurch nicht verändert: date-only Artefakte und der
vorherige Bericht bleiben erhalten. Neue versionierte Nachweise heißen
`*-implementation-2026-10-02.*`; sie bewahren Originalidentitäten, Status und
Meldungen, entfernen lediglich Capturelogs und Tracebackkörper.
Die tatsächlichen Quellstände und Befehle jedes einzelnen Laufs stehen in
`execution.json`; der Snapshotstand oben ist der zusammengeführte Code.
Backend, JavaScript und die separat archivierte Rules-Suite stammen aus lokalen
Windowsläufen. Der endgültige vollständige E2E-Nachweis stammt aus Linux CI;
die realen Windows-Einstiege sind zusätzlich in ihrem eigenen CI-Job belegt.
Der zusätzliche vollständige Linux-Backendlauf enthält 3.274 bestandene und
15 übersprungene Fälle: 14 Varianten benötigen Windows PowerShell; ein
Parquetfall benötigt eine optionale Engine. Diese originalen Skips bleiben im
separaten [Linux-JUnit](evidence/backend-linux-ci-implementation-2026-10-02.xml)
erhalten. Alle betreffenden Verträge laufen im primären Windows-Backend;
die [28 CLI-Fälle beider Shells](evidence/windows-cli-implementation-2026-10-02.xml)
sind zusätzlich separat archiviert. Sie werden nicht nochmals zur Primärsumme addiert.

Die vollständigen Listen neuer und entfallener Runneridentitäten stehen in
`execution.json` unter `runner_identity_changes`. Umbenennungen und geänderte
Parametrisierungen können jeweils eine neue und eine entfallene Identität
erzeugen; diese Differenz ist keine Behauptung über gleich viele neue Funktionen.

| Suite | Bisherige Identitäten | Aktuelle Identitäten | Hinzugekommen | Entfallen |
|---|---:|---:|---:|---:|
| Python | 3081 | 3303 | 222 | 0 |
| JavaScript | 664 | 705 | 41 | 0 |
| Chromium / native SDK / Smoke | 308 | 368 | 62 | 2 |
| Firestore-Clientregeln | 0 | 49 | 49 | 0 |


Ein zuvor abgebrochener lokaler E2E-Versuch enthielt einen nicht zugeordneten
Fehlerindikator ohne fertigen JUnit-/Tracebeleg. Die vermutete Phase2-Sharegrenze
bestand anschließend die Viererdatei und fünf unabhängige Einzelprozesse ohne
Replayhelfer. Das grenzt den Verdacht ein, belegt aber weder eine Ursache noch
eine Flakebehebung. Dieser unvollständige Versuch geht nicht in die obigen
Fallzahlen ein; maßgeblich ist der vollständige archivierte CI-Lauf.

Die Umsetzung behob unter anderem Memory-Datenverlust bei abgesenktem Limit,
Firestore-unzulässige Dokumenttabellen, stale SEO-/Probe-Writes, fehlende
Topic-Revocation und Tierfehlerprojektion, falsch gebundene Retention-/SEOdaten,
Benchmark-Protokollfehler/Manifestzeitdrift, stale Adminberichte sowie einen
realen Scrollsprung. Die Breitenbeobachtung des Composers korrigiert außerdem
eine nach abgeschlossener CSS-Transition zu hohe Textarea. Eine native Browserreise reproduzierte
`generator ignored GeneratorExit` beim Agentclose hinter Kontotombstone;
der Fehler wurde mit eigener Regression behoben.

Die unabhängige Abnahme verstärkte gezielt zuvor zu enge Nachweise:
Chatcompletion während committed deleting vor physischem Purge,
Admission/Buchung bei entfernter Transaktionsatomarität, volle Memory-HTTP-
Matrix und native Commitfehler, Own-Key-Affinität ohne persistierte Secrets,
echte Schedulerloops/Cancellation sowie abgewiesener Rollback-RPC.
Konkrete Befehle, Rot-/Grünbelege und Negativkontrollen stehen in den
[Persistenz-](product/implementation-persistence.md),
[Adapter-](product/implementation-adapters.md),
[Browser-](product/implementation-browser.md) und
[Runtimeberichten](product/implementation-runtime.md).

Der kompakte Negativkontrollenindex erhält Assertionauszüge und Hashes aus
32 archivierten lokalen Fehlermessungen sowie vier bewusst gebrochene Verträge in
bestandenen Tests. Er trennt gespeicherte Exitcodes, durch den ausgeführten
Harness belegte Exitcodes und unbekannte Werte. Implementierungscommits sind
ausdrücklich keine erfundenen Run-HEADs. Sechs weitere Rot-vor-Fix-Belege sind
als reine Berichtbelege gekennzeichnet; sie erhöhen keine Mutationsquote.
Zusätzlich belegt der reale rote CI-Lauf auf `2afe0cf1` mit25 fehlgeschlagenen
Fällen, Exit1 und trotzdem hochgeladenem Artefakt die Fehlerpropagation des
Workflows. Dies ist eine tatsächliche Regression, kein absichtlich injizierter Mutant.

38 der 38 Arbeitspakete sind vollständig abgenommen. Die in den Berichten benannten Betriebsgrenzen bleiben ausdrücklich bestehen.

Die Emulatorprüfung verwendet `demo-consensio-e2e`, expliziten E2E-Modus und
anonyme Credentials. Native SDK-Konflikte können das vorhandene Retrylimit
erschöpfen. Entsprechende Tests erfassen ausschließlich konkrete ABORTED-
Aufrufe als fehlgeschlagene Versuche mit Warnung. Nur wenn alle konkurrierenden
Versuche abgebrochen sind, muss der gespeicherte Zustand vor dem Replay
vollständig unverändert sein; bei gemischtem Ausgang gilt diese Gleichheit
nicht. Je abgebrochenem Worker folgt genau ein gesonderter nächster Aufruf,
dessen Fehler nicht abgefangen wird. Ein Abbruch zählt nicht als Erfolg.
Dabei sind ein direkt vom SDK-Read ausgelöstes `Aborted` und das nach verbrauchten
SDK-Retries verpackte `ValueError` mit genau dieser Ursache ausdrücklich
unterschieden; andere Exceptions bleiben Fehler.

Keine produktiven Konten, keine bezahlten Modelle, keine echte Google-/Mail-/
Telegramzustellung oder Bucket-IAM-Prüfung. Lokale TCP/TLS-Sockets sind echte
Transportnachweise, aber keine Deploymentproxy-/CDNmessung. Die historische
Branch-Coverage wurde nicht neu erhoben. Auswahl und Mockgrenzen stehen je
Testdatei; grüne Testzahlen bedeuten keine vollständige Produktfreigabe.

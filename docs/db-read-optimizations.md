# Firestore-Reads reduzieren — 09.09.2026

Die Änderungen erhalten die bestehenden API-Antworten, Nutzerzuordnung,
Usage-Limits, Run-Fingerprints, einmaligen Operations-Claims und den
transaktionalen Schutz gegen verspätete Writes nach Kontolöschung.
Es werden keine Produktionsdaten migriert oder gelöscht.

## Wirkung

| Pfad | Vorher | Jetzt |
|---|---|---|
| Usage je Modellaufruf | Reserve, Consume und Claim: 8 Dokument-Reads | Eine Autorisierungstransaktion: 3 Dokument-Reads |
| Usage bei sechs Modellen | 48 Reads | 18 Reads, 62,5 % weniger in diesem Teilpfad |
| Memory bei sechs Modellen | 6 Reads desselben Profils | 1 Read bei gemeinsamem Run-Key, warmem Snapshot und demselben Worker |
| Zeitraum-Rangliste | Alle Votes seit dem Stichtag pro Backend-Aufruf laden | Familienweise Index-Count-Aggregationen, zusätzlich 60-s-Cache |
| Verwandte Fragen | Bis zu 400 Share-Dokumente je unterschiedlicher Seite/Cache-Miss | Ein gemeinsamer Kandidatenbestand je Worker, 15 Minuten TTL |
| Langer Topic-Verlauf | Gesamte Run-Collection lesen | Normalerweise höchstens `max_items + 1` Run-Dokumente |

Die Usage-Zahlen sind durch instrumentierte Repository-Tests ohne SDK-Retries
belegt. Sie umfassen weder Auth-/Chat-/Bookmark-Reads noch `/prepare`.
Die neue Methode wird auch von `/consensus` und `/resolve` verwendet.
Eine Aussage zur gesamten Produktionsersparnis erfordert die tatsächliche
Verteilung von Runs, Seitenaufrufen, Cache-Hits und Transaktions-Retries.

Firestore berechnet Dokument- und gegebenenfalls Index-Reads. Eine Query, die
sechs Antwortdokumente liefert, bleibt sechs Dokument-Reads; weniger SDK-Aufrufe
sind nicht automatisch weniger abgerechnete Reads. Deshalb wurde auch die alte
`2 + N Reads`-Angabe des Chat-Verlaufs korrigiert. Count-Aggregationen sind
ebenfalls kostenpflichtig, vermeiden aber das Einzel-Laden sämtlicher Votes.

## Erhaltene Grenzen und Rückfallpfade

- Usage autorisiert nie aus einem Cache. Account-Tombstone, Run und Tagesstand
  werden in derselben Transaktion gelesen, bevor irgendein Write erfolgt.
  Reservierungen älterer Clients und Direktaufrufe funktionieren weiterhin.
  Bereits konsumierte Runs dürfen bei ausgeschöpfter Tagesquote fortgesetzt
  werden, werden aber nicht erneut berechnet. Jede Operation bleibt einmalig.
- Der Memory-Cache trennt UID, Run-Key, Repository und Zeichenlimit. Er hält
  höchstens 256 Einträge inklusive laufender Reads für 120 Sekunden. Parallele
  Requests teilen einen laufenden Read. Fehler bleiben ungecacht; ohne
  verwendbaren Run-Key wird frisch gelesen. Änderungen am Profil gelten für
  den nächsten Run; Profil-/Account-Löschung invalidiert lokale Snapshots und
  laufende Reads. Andere Worker haben eigene Caches und denselben Auth-/Write-Schutz.
- Die Rangliste behält historische Modell-Aliase und die bisherige
  Löschsemantik: Lifetime-Zähler bleiben bestehen, Zeitraum-Zähler zählen nur
  noch vorhandene Vote-Dokumente. Katalog und Count-Abfragen teilen einen
  Read-only-Transaktionssnapshot. Unvollständige/fehlgeschlagene Refreshes
  werden nicht gecacht.
- Related Shares bleiben ausschließlich indexiert, aktiv und öffentlich.
  Moderation invalidiert den gemeinsamen Kandidatenbestand im selben Prozess;
  andere Worker folgen wie zuvor ihrer TTL. Das Ranking wird pro Frage neu
  berechnet, einschließlich Ausschluss der geöffneten Seite.
- Topics prüfen bei kurzen Historien per Count im selben Transaktionssnapshot,
  ob die sortierte Query Legacy-Dokumente ohne Datum ausschließt. Nur wenn
  nötig, bei ungültigen Daten oder Datums-Gleichstand an der Auswahlgrenze
  wird der bisherige vollständige Lesepfad verwendet. Ein normaler kurzer
  Verlauf kostet N Dokument-Reads plus eine Count-Aggregation. Sonderfälle
  können weiterhin vollständige Historien lesen.

## Rollout

Der zusätzliche Composite-Index steht in `firestore.indexes.json`:
`model_votes`: `vote_type ASC`, `model ASC`, `created_at ASC`.

Beim nächsten autorisierten Deployment nur die Indizes ausrollen, mit
explizit ausgewähltem Firebase-Projekt:

```powershell
firebase deploy --only firestore:indexes --project <projekt-id>
```

Der Code funktioniert auch, wenn der Index noch fehlt oder aufbaut: Nur ein
entsprechender `FailedPrecondition` aktiviert den bisherigen Vote-Scan unter
dem neuen 60-s-Cache. Sobald der Index bereit ist, verwendet der nächste
Refresh automatisch Counts. Sonstige DB-Fehler bleiben echte Fehler.
Ein Daten-Backfill und ein Frontend-Build sind für diese Änderungen nicht nötig.

## Prüfung

Gezielte Regressionen prüfen Read-Zahlen, Parallelität, Tages-/Deep-Limits,
Replay-/Fingerprint-Konflikte, UTC-Wechsel, Kontolöschung, Cache-TTL und
Invalidierungsrennen, historische Topics und den Index-Rollout-Fallback.
Die Implementierungen wurden zusätzlich unabhängig von einem Agenten geprüft.
Alle Tests laufen mit In-Memory-Fakes oder gemocktem SDK-Transport; dieser
Arbeitsauftrag greift nicht auf die Produktionsdatenbank zu.

Verifikation am 09.09.2026:

- Erneuter Gesamtlauf der regulären Python-Suite inklusive SDK-Vertragstests:
  **1.698 bestanden** (13 bestehende Deprecation-Warnungen).
- JavaScript: **191 bestanden**, verteilt auf 33 Testdateien.
- Der isolierte Commit-Inhalt wurde zusätzlich geprüft: 1.698 Python-Tests
  und 181 JavaScript-Tests aus den 31 bereits committeten Frontend-Testdateien.
  Die Kopie verwendet unveränderte Git-Blobs und einen separaten Prüfindex;
  dadurch beeinflussen Windows-Zeilenenden und die übrigen lokalen Änderungen
  weder Build-Fingerabdruck noch Asset-Cache-Prüfung.
- `git diff --check` für die bearbeiteten Dateien ohne Whitespace-Fehler.
- Ein vorhandener Archiv-Quelltexttest wurde an die bereits geänderte
  Modell-Icon-Darstellung angepasst; die Prüfung historischer Modellnamen und
  fehlender Live-Buttons bleibt erhalten. Produktiver Frontend-Code wurde in
  diesem Auftrag nicht verändert.
  Diese Anpassung bleibt mit den zugehörigen Frontend-Änderungen außerhalb
  des isolierten DB-Commits.

Kein Produktions-Deployment, kein Live-Lasttest und kein Browser-/Emulator-E2E
in diesem Auftrag. Der neue Index ist als Deployment-Datei vorbereitet.

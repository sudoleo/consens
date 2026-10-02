# Aktualisierung vom 02.10.2026

[Einstieg](README.md) · [Katalog](../../test-coverage-map.md) · [Laufbericht](../findings.md)

Quellstand `2860844a`, Ausgangspunkt `145db25b`. 40 neue und zwei entfernte
Testdateien ergeben 254 Dateien. Definitionen/Assertionanker und Runnerfälle
wurden neu erfasst, Produktzuordnung auf 301 Dateien/87 Vertragsgruppen erweitert.

## Neue Funktionen und Grenzen

| Bereich | Aktuelle Belege | Verbleibende Grenze |
|---|---|---|
| AGENT-06 Dateien | Upload/Download, Parserlimits, Auswahl, Löschfences, Nachrichtenbindung | Cloud-Bucket/IAM und native Kaskade; G-044 |
| AGENT-07 Dokumente | Echte DOCX/PDF-Inhalte, Versionen, Quellenhashes, Fehlerpfade | Keine vollständige visuelle Seitenprüfung |
| GOOGLE-01 Verbindung | PKCE/State/Owner, Verschlüsselung, Widerruf, Scopes, Modellrouting, Zustimmung | Live-OAuth/Deployment |
| GOOGLE-02/03 Aktionen | Exakter Hash, ETag, Empfänger/Reply/Anhänge, unklare Writes nur reconciled | Native Claims und reale Zustellung; G-043 |
| CONS-06 Integrität | Serverreceipts, BYOK-Rankinggrenze, typisierter Abschluss | Browser/DB noch getrennt |
| QUOTA-03 Konto | Alle Modi, Holds, Meter, Schätzungen/Nachmessung, begrenzte Rootreceipts | Native Admission/Buchung; G-002 |
| WATCH-07/08 | Outbox, Leasefencing, Belege/Recheck, Zielabschluss, Probes | Native Claims/SDK und Live-Evidenzqualität; G-045 |
| UI-02/04 | Modusselektor, Agentpicker, Quellenpillen, Markdown, Differencesreader | Browserlauf enthält rote Fälle |
| BUILD-04 | Immutable/gzip, unkomprimierte SSE-Frames | Kein realer Proxy-/CDN-/Socketnachweis |

Entfernte Dateien: `run-progress-animation.test.mjs` und
`watch-drift-state.test.mjs`. Der neue Stepper und das Watch-Dashboard haben
aktuelle Verträge; alte Fallzahlen werden nicht übernommen.

## Alte Befunde neu bewertet

| Befund | Aktueller Stand |
|---|---|
| G-018 | Behoben in `76e4873e`; Textknoten und externe Skripte/CSP, aktuelle jsdom-/Pythonregressionen grün |
| G-037 | Behoben in `c929e343`; registrierter main-Handler bewahrt Retry-After/WWW-Authenticate |
| G-040 | CAS-/Revisionsrollback bewahrt simulierten fremden Writer (`6b80daa6`); nativer Lauf fehlt |
| G-003/G-004 | Dauerhafte Chatlöschjobs/erweiterte Kontokaskade; keine vollständige native Integration |
| G-005 | API-Recovery abgelaufener Reservierungen und Lösch-/Replaypfade ergänzt; Retention/Backfill/Restart offen |
| G-007/G-008 | Memory-CAS, Edit-Leasen und Undoablauf ergänzt; Undo-HTTP/Owner/Conflict/Limitwechsel nicht vollständig |
| G-038 | Undo sanitisiert weiter mit abgesenktem Limit; statischer Befund bleibt, alte Probe scheitert am neuen Leasevertrag |
| G-041 | Erneut beobachtet: Topichelper prüft Widerruf nicht und behandelt Rollenausfall abweichend |
| G-042 | Erneut beobachtet: HTTP-200-Fehlerbody wird als erfolgreiche Enthaltung indiziert |
| G-025/G-026 | Windows-/Chromiumresultate ergänzt; Emulator und rote Fälle bleiben offen |

Alle 46 Bewertungen: [gaps.md](gaps.md). Vier neue Aufgaben G-043–G-046 sind
WP-35–WP-38 zugeordnet. Ein Kernfehler kann behoben sein, während zur vollständigen
Paketabnahme noch native Integration oder erneute Negativkontrolle fehlt.

## Ausführung und Grenzen

Aktuelle Ergebnisse mit Originalfallnamen/Status/Meldungen:
[execution.json](../execution.json). Keine kostenpflichtigen Modelle oder
produktiven Konten dienten als Testziel.

Fünf historische unabhängige Proben wurden isoliert versucht. Topic-Auth und
Benchmarkklassifikation lieferten erneut Beobachtungen. Headerprobe
(Windows-Eventloop/Socketguard), Memoryprobe (neuer Leasenonce) und Rollbackprobe
(geänderter Transaktionsvertrag) scheiterten im alten Harness. Das belegt weder
korrektes noch falsches Produktverhalten.
[Beobachtungen](../evidence/probes-2026-10-02.json).

Die historischen Coverage-/Mutationsdaten wurden nicht neu erzeugt. Ihre
Positionen gehören zum damaligen Gitstand; neue Quellen erhalten keinen
erfundenen Coveragewert.

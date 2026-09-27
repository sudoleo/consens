# Isolierte Belege zum Produktcode-Review

Basis und Schweregrade stehen in [README.md](README.md). Diese Proben wurden eigens aus den Produktpfaden entwickelt, ohne die parallelen Testsuite-Findings zu lesen. **23 Proben wurden am 27. September 2026 erfolgreich ausgeführt; sie belegen Teilverhalten zu 20 verschiedenen Befunden.** Davon sind zehn Proben in der Gegenprüfung hinzugekommen. „Erfolgreich“ bedeutet hier, dass die Probe den dokumentierten Ist-Zustand nachweist; bei R07 ist das ein bewusstes Verhalten mit bedingtem Kostenrisiko. Es bedeutet weder Fehlerfreiheit noch 23 bestandene Sollverhaltens-Tests. Der maschinenlesbare Lauf steht in [repro/ERGEBNISSE.json](repro/ERGEBNISSE.json).

## Ausführung

Aus dem Repository-Root, in einer Umgebung mit den Projekt-Backendabhängigkeiten beziehungsweise `npm ci`:

```bash
python docs/code-review/repro/backend.py
node docs/code-review/repro/frontend.cjs
```

Verwendete Laufzeit bei der Prüfung: Python 3.12.14 mit FastAPI 0.128.8 und den bereits vorhandenen Projektabhängigkeiten; JavaScript über Node und die vorhandene jsdom-Abhängigkeit des Repositories. Die Node-Probe läuft in jsdom, nicht in einem echten Browser. Für die Python-Probe werden `UNIT_TEST_MODE=1`, ein unerreichbarer Emulator-Endpunkt und zusätzlich ein Socket-Verbindungsverbot gesetzt. Sie verwendet eine eigene In-memory-Datenbank; keine echten Provider, Firestore-Instanzen, Benutzerkonten, E-Mails oder Telegram-Nachrichten werden angesprochen.

Die API-Quote wird mit echten Repository- und Runner-Methoden geprüft. Der Fake implementiert nur die benötigten sequenziellen Datenoperationen: Er beweist den Fehler der Zustandsübergänge, nicht das Firestore-Verhalten bei Konfliktretries. Einzelne kleine Funktionen werden direkt aus dem aktuellen Quelltext extrahiert, damit Import/Lifespan keine zusätzlichen Seiteneffekte auslösen. Die Scripts gehören zunächst zur Review-Dokumentation; bei einer Behebung sind gezielte Tests in den normalen Testsuiten nötig.

## Beobachtungen

| Befund | Probe | Beobachtetes Baselineverhalten |
|---|---|---|
| R01 | Echtes `topic-page.js`, `data-note` mit harmlosem Span, Fokus auslösen | Ein zusätzliches Element `#review-injected` entsteht; Datentext wird HTML |
| R03 | Zweimal Create → Reserve → Execute → Delete mit identischem Key/Request | Zwei Pipeline-Ausführungen, aber nur ein verbrauchter Quoten-Slot |
| R04 | Echter Handler, 429 mit `Retry-After: 15` | Status 429 bleibt, Header fehlt |
| R05 | Receipt 23:59:59 UTC, Retry zwei Sekunden später | `UsageRunExpired` |
| R06a | Echter Streamadapter mit einem Delta und anschließendem EOF | Erfolgreiches `final`, ohne Fehler oder Unvollständigkeitskennzeichnung |
| R06b | Echter Streamadapter mit Delta und `finish_reason=length` | Ebenfalls erfolgreiches `final` |
| R07 | 100 reservieren, ohne finale Usage abrechnen, Limit 100 | `used=0`, `reserved=0`, `unknown=100`, `remaining=100` |
| R08 | Zitat enthält 4000 Euro, Original 400 Euro | `quote_models=['OpenAI']`; zurückgegebenes Zitat endet am gemeinsamen Präfix „400“ |
| R14 | News-URL, erlaubte Kategorie ausschließlich `primary` | Quelle wird als `primary` ausgegeben |
| R15 | Identischer Satz mit Preiswechsel 20 → 90 | Bewegungswert 0, Label `Stable` |
| R20 | Topic A im Formular, GET B scheitert, Save | `PUT /api/admin/topics/B` enthält A-Daten |
| R22 | `create_run` wirft, dann erneutes Collect | Lock bleibt gehalten, zweiter Aufruf `CollectionAlreadyRunning` |
| R10 | Pending-Context claimen → Turn auf completed setzen → echten Finalizer aufrufen | Fertiger Turn bekommt nachträglich Context-ID und neue Lesart |
| R12 | Originalprofil → neuere Fassung → alter Formularsnapshot | Originalinhalt wiederhergestellt, Revision trotzdem 3 |
| R13 | Edit reservieren → gleiche ID einen Tag später reservieren | Weiter `reserved` statt Terminal-/Recoveryzustand |
| R14b | Echte öffentliche Klassifizierung nach R14 | `role=primary`, `quality=high` für die allgemeine News-URL |
| R16 | Echtes Watch-Update auf paused → alter Run meldet Fehler | `status=active`, Owner-Zähler bleibt 0 |
| R21 | Vollständiges Attachment-Modul, verzögerter FileReader, Reset für Bookmarkansicht | Alte Datei erscheint später wieder als Pending-Anhang |
| R23a | Vollständiges Memory-Modul, Auswahl A, Auth-Event B, Submit | A-Auswahl wird mit B-Token geschickt |
| R23b | Request B → Auth-Event C → verspätete Antwort B | Memory-Reload für C und alter Undo-Hinweis |
| R25 | Echter Admin-Persist-Helfer, fremder Write B während Aktivierung A, A scheitert | Rollback ersetzt B durch Ausgangsstand X |
| R30 | A-Lease ablaufen → B claimt → A gibt frei → C claimt | C zugelassen trotz nicht abgelaufener B-Lease |
| R31 | `/Report?key=AbC` gegen `/report?key=abc` | Identischer Deduplizierungsschlüssel |

Die zusätzlichen Backend-Proben verwenden denselben einfachen Fake. R10 setzt die anderweitige Completion gezielt als Zustand, R16 ersetzt Index-Vorbereitung, Share-Read und reine Serialisierung, R25 schiebt den Fremdwrite an der Aktivierungsgrenze ein. Sie prüfen die echten Mutationen, nicht SDK-Konfliktretries oder parallel laufende HTTP-Requests. Bei R21/R23 werden echte DOM-Handler in jsdom ausgeführt; FileReader, Firebase-Identität und Fetch sind kontrollierte Stubs.

R01 beweist die HTML-Injection am Sink. Die Probe führt keine Schadfunktion aus und beweist nicht, dass ein Angreifer beliebigen Text zuverlässig durch einen echten LLM-Lauf schleusen kann. R07 beweist die Budgetarithmetik; die Voraussetzung bereits kostenpflichtiger Providerarbeit ist gesondert im Befund genannt. R05 beweist den Ablauf des Belegs, während die Folgen für interaktive und wiederhergestellte API-Runs statisch nachverfolgt wurden.

## Nicht ausgeführte Prüfungen

Kein Produktions-Penetrationstest, kein Lasttest, kein echter Firestore-Transaktions-/Indexlauf, keine kostenpflichtigen Provideraufrufe, kein SMTP-/Telegram-Versand. Die vollständige bestehende Testsuite wurde für diesen Dokumentationsauftrag nicht erneut gestartet. Daher werden statisch belegte oder bedingte Befunde ausdrücklich nicht als live reproduziert ausgegeben.

Für die Integration sind Dokumentstruktur, Quellenpfade, interne Links, IDs, Syntax der Proben und Git-Diff zu prüfen. Da keine Dateien unter `static/` oder Produktfunktionen geändert werden, ist ein neuer Frontendbuild für diesen Auftrag nicht erforderlich. Spätere Fixes unterliegen den jeweiligen Test-/Buildregeln in `AGENTS.md`.

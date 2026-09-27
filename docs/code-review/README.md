# consens: Produktcode-Review und Reparaturplan

**Prüfbasis:** `4d7c061036936b06bb98b2b306b2987a5844cde4`, Stand 26. September 2026. Die Zeilenangaben beziehen sich auf diesen Commit. **33 Befunde und Verbesserungsvorschläge**, getrennt nach Belegstärke; keine Produktänderungen. Die parallele Prüfung der Testsuite und deren Befunde wurden nicht als Quelle verwendet.

**Gegengeprüft am 27. September 2026 gegen `a448baa7` (voller SHA im [Gegenprüfungsprotokoll](GEGENPRUEFUNG.md)).** Der Produktcode ist gegenüber der Prüfbasis unverändert. Alle 33 Einträge wurden erneut geprüft; R07 wurde als bewusste Abrechnungsentscheidung auf P2 eingeordnet. Es verbleiben **5 P1, 26 P2 und 2 P3**; 23 Offline-Proben belegen Teilverhalten zu 20 Einträgen. Das Protokoll nennt auch Gegenargumente, Einschränkungen und die vorgenommenen Korrekturen.

Das größte Risiko liegt an den Übergängen zwischen Funktionen: Ein bereits bezahlter Aufruf wird erneut freigegeben, ein fertig gespeicherter Lauf verliert seine Benachrichtigung, ein alter Browserzustand schreibt in den inzwischen gewählten Datensatz. Der zweite Schwerpunkt ist die Glaubwürdigkeit des Produkts: „abgeschlossen“, „belegt“, „Primärquelle“ und „stabil“ sagen an einigen Stellen mehr aus, als der Code tatsächlich nachweist.

## Lesen und anschließend umsetzen

Jeder Eintrag beginnt mit **genau zwei verständlichen Sätzen**. Danach folgen Einstiegspunkte, Fehlerablauf, Reparaturvorschlag und Abnahmekriterien für Codex. Die Nummern bleiben als Referenzen stabil; die Reihenfolge ist keine reine Schweregradliste.

- **P1:** zuerst beheben; Sicherheitsgrenze, Kostenkontrolle oder wesentliche Ergebnisintegrität.
- **P2:** danach; konkreter Funktionsfehler oder relevantes, ausdrücklich bedingtes Betriebsrisiko.
- **P3:** geplante Verbesserung beziehungsweise irreführender Produkttext.
- **R = reproduziert:** isolierte Ausführung echter Produktfunktionen; Details in [BELEGE.md](BELEGE.md).
- **S = statisch belegt:** vollständiger Codepfad nachvollzogen, aber kein Ende-zu-Ende-Versuch gegen Produktion.
- **B = bedingtes Risiko:** Voraussetzung steht im Eintrag; kein behaupteter Produktionsvorfall.
- **V = Verbesserung:** bestehendes Verhalten ist teilweise ausdrücklich beabsichtigt; Produktentscheidung nötig.

Ein erfolgreicher Quelltextreview beweist keine Fehlerfreiheit. [ABDECKUNG.md](ABDECKUNG.md) nennt die abschnittsweise geprüften Dateien und die Grenzen: CSS wurde strukturell geprüft, nicht vollständig visuell; Infrastruktur, echte Provider und Datenbanklast wurden nicht live geprüft. Die kleinen Reproduktionen bestätigen das **beschriebene Ist-Verhalten** und müssen beim Fix in Tests des gewünschten Verhaltens umgewandelt werden.

## Priorisierte Übersicht

| ID | Prio | Beleg | Thema |
|---|---|---|---|
| R01 | P1 | R/S | Topic-Zusammenfassung wird erneut als HTML interpretiert |
| R02 | P1 | S | Verwundbare DOMPurify-Version ausgeliefert |
| R03 | P1 | R | API-Löschen umgeht erneute Quotenbelastung |
| R04 | P2 | R | HTTP-Fehler verlieren wichtige Header |
| R05 | P2 | R/S | Laufberechtigung endet mitten im Lauf um UTC-Mitternacht |
| R06 | P1 | R/S | Abgeschnittene Antworten gelten als fertig |
| R07 | P2 | R/B/V | Unbekannter Agent-Verbrauch stellt das volle Budget wieder her |
| R08 | P2 | R | Unscharfe Textsuche wird als Zitatbeleg verwendet |
| R09 | P1 | S | Modellantworten aus dem Client werden zu autoritativen Ergebnissen |
| R10 | P2 | R/S | Später Kontextabschluss kann fertigen Turn verändern |
| R11 | P2 | S | Chat-Löschung nach Bookmark-Löschung ohne dauerhafte Wiederholung |
| R12 | P2 | R/S | Manuelles Memory-Speichern überschreibt neuere Änderungen |
| R13 | P2 | R/S | Memory-Edit bleibt nach Absturz dauerhaft „processing“ |
| R14 | P2 | R | Nicht erlaubte Quellen werden in erlaubte Quellen umbenannt |
| R15 | P2 | R | Preisänderung wird als stabile Modellposition bewertet |
| R16 | P2 | R/S | Laufender Watch kann manuelles Pausieren rückgängig machen |
| R17 | P2 | S/V | Benachrichtigungen können dauerhaft verloren gehen |
| R18 | P2 | B | Widerruf und öffentliche Caches widersprechen sich |
| R19 | P2 | S | Eine Person kann durch fünf Reports Noindex auslösen |
| R20 | P2 | R | Topic-Admin speichert altes Formular unter neuer ID |
| R21 | P2 | R/S | Verspäteter Dateiimport landet im nächsten Entwurf |
| R22 | P2 | R | SEO-Collector bleibt nach frühem Datenbankfehler gesperrt |
| R23 | P2 | R/S | Memory-Dialog überlebt den Kontowechsel |
| R24 | P2 | S/B | Limit vor Filter versteckt relevante Moderations-/SEO-Einträge |
| R25 | P2 | R/B | Modellkonfiguration ist nicht prozessübergreifend konsistent |
| R26 | P2 | B | PDF-Extraktion ohne eigene Ressourcenbegrenzung |
| R27 | P2 | S | Benchmark-Audits liegen außerhalb des Budgetlimits |
| R28 | P3 | V | Memory-Undo behält vollständige alte Profile dauerhaft |
| R29 | P2 | B | Agent-Sitzungsdokument wächst mit allen Schritten |
| R30 | P2 | R/B | Alter Watch-Worker kann fremde globale Lease freigeben |
| R31 | P2 | R | Groß-/Kleinschreibung verschiedener Quellen wird zusammengelegt |
| R32 | P3 | S | Publisher-Admin verspricht nicht vorhandenen DeepSeek-Ausschluss |
| R33 | P2 | S | Alte Topic-Versionen werden nach 100 Läufen unerreichbar |

## 1. Sicherheitsgrenzen und Laufabrechnung

### R01 — Topic-Text wird erneut als HTML interpretiert

**In zwei Sätzen:** Ein Text aus einem Topic-Lauf wird beim Darüberfahren oder Fokussieren erneut als HTML eingesetzt. Enthält er schädliches Markup, kann daraus Code im Browser eines Besuchers werden.

**P1 · R/S.** Einstieg: `app/services/topic_runner.py:180–190`, `app/services/claim_ledger.py:396–455`, `templates/topic.html:222–229`, `static/js/topic-page.js:27–37`; CSP in `app/core/security.py:96–149`.

**Ursache und Ablauf:** `change_summary` stammt aus dem Pipeline-Ergebnis und wird als `cell.note` gespeichert. Jinja escaped das `data-note`-Attribut korrekt; der Browser decodiert es beim Lesen von `dataset.note` wieder. `show()` interpoliert diesen String unescaped in `read.innerHTML`. Die unveränderte Notiz erreicht diesen Pfad bei einem materiellen Folgelauf (`minor`/`major`); die erste Zelle und stabile Zellen verwenden feste Texte. Die Längen-/Whitespace-Normalisierung in `topics._clean_multiline` entfernt kein HTML. Auf `/topics/...` erlaubt die derzeitige CSP Inline-Skripte. Die Offline-Probe erzeugt über diese echte Funktion ein harmloses zusätzliches `<span>`; sie injiziert nichts in eine echte öffentliche Seite. Die erfolgreiche Unterbringung schädlicher Inhalte im Modelloutput wurde nicht live versucht.

**Fix:** Datum, Notiz und Score mit DOM-Knoten und `textContent` aufbauen. Kein zweites HTML-Parsing von Datentext; öffentliche Inline-Skripte anschließend in externe Dateien verschieben und deren CSP härten. Die CSP ist zusätzliche Absicherung, kein Ersatz für den Sink-Fix.

**Abnahme:** HTML-artiger Text erscheint auf Hover, Tastaturfokus und Touch wörtlich; weder zusätzliche Elemente noch Eventhandler entstehen. Dieselben Regeln gelten für historische und aktuelle Topic-Zellen. Bestehende Score-Formatierung bleibt erhalten.

### R02 — DOMPurify 3.0.6 ist als Sicherheitskomponente überholt

**In zwei Sätzen:** Die App und öffentliche Seiten liefern eine DOMPurify-Version mit veröffentlichten Sicherheitslücken aus. Ein bekannter Sanitizer-Bypass schwächt dadurch den Schutz beim Rendern fremder Modelltexte.

**P1 · S.** Einstieg: `package.json:13`, `scripts/vendor_frontend.mjs:8–18`, `templates/share.html:31`, `templates/topic.html:172`, `static/vendor/dompurify/3.0.6/`.

**Beleg:** Die tatsächlich gepinnte und ausgelieferte Version ist 3.0.6. Das [Hersteller-Advisory GHSA-gx9m-whjm-85jf / CVE-2024-47875](https://github.com/cure53/DOMPurify/security/advisories/GHSA-gx9m-whjm-85jf) nennt Versionen unter 3.1.3 als betroffen; erneut am 27. September 2026 am Hersteller-Advisory geprüft. Dies belegt die verwundbare Abhängigkeit, nicht jeden möglichen Exploit unter den zusätzlichen Sanitizer- und CSP-Regeln der Anwendung. R01 umgeht den Sanitizer vollständig und ist separat zu beheben.

**Fix:** Eine zum Umsetzungszeitpunkt gepflegte, gegen die veröffentlichten Advisories geprüfte Version pinnen; Lockfile, vendorte Dateien, Build-Manifest und öffentliche CDN-Verweise gemeinsam aktualisieren. Nicht lediglich auf die historische Mindestversion dieses einen Advisories springen.

**Abnahme:** Kein ausgelieferter Pfad verwendet mehr 3.0.6; App, öffentliche Shares und Topics verwenden die freigegebene Version. Hersteller-Regressionsfälle gegen die tatsächlich verwendeten Sanitizer-Konfigurationen sowie Markdown, Formeln und Quellenanker prüfen; anschließend `npm run build` und `npm run build:check`.

### R03 — Löschen und Wiederanlegen eines API-Runs umgeht die Quote

**In zwei Sätzen:** Ein abgeschlossener API-Lauf lässt sich löschen und mit demselben Schlüssel erneut ausführen. Die Modelle arbeiten dann ein weiteres Mal, aber das Tageskontingent zählt weiterhin nur einen Lauf.

**P1 · R.** Einstieg: `app/services/api_run_repository.py:create_or_get`, `_delete` (286–323); `app/services/api_consensus_runner.py:usage_key_for_run`, `reserve_run`, `execute_persisted_run`; `app/services/usage_repository.py:reserve`, `consume`.

**Ablauf:** Terminalen Run mit Schlüssel K erzeugen, abschließen, löschen, dieselbe Anfrage mit K erneut annehmen. `_delete` entfernt Run und API-Idempotenzmapping, nicht den Usage-Beleg. Die neue Run-ID erhält denselben Usage-Schlüssel; `reserve_run` akzeptiert auch `CONSUMED`, und `consume` ist idempotent. Ein neuer API-Run darf deshalb den Providerpfad betreten, ohne einen weiteren Slot zu belasten. Voraussetzung: gleicher UTC-Tag und unveränderter Request-/Plan-Fingerprint. Offline bestätigt: **2 Pipeline-Ausführungen, 1 verbrauchter Slot**.

**Fix:** Inhaltslöschung und Idempotenz-Tombstone trennen. Ein gelöschter logischer Run darf unter demselben Schlüssel nicht noch einmal kostenpflichtig starten; Antwortvertrag z. B. stabiler `410`/`409`. Alternativ neue kostenpflichtige Ausführung ausdrücklich mit neuer Identität und neuem Usage-Beleg verbinden. Nicht bloß `consume` blind erneut zählen lassen: legitime Retries müssen idempotent bleiben.

**Abnahme:** Create → Complete → Delete → Create(K) startet keine zweite Pipeline; parallele Wiederholungen ebenfalls nicht. Neuer Schlüssel startet genau einen neu berechneten Run. Inhaltslöschung funktioniert weiter und verlangt keine Aufbewahrung des vollständigen Prompts.

### R04 — Exception-Handler verwirft `Retry-After`

**In zwei Sätzen:** Der Server gibt zwar den richtigen Fehlerstatus zurück, verliert dabei aber zusätzliche HTTP-Informationen. Clients erfahren dadurch zum Beispiel nicht, wann sie nach einer Überlastung erneut anfragen sollen.

**P2 · R.** Einstieg: `main.py:225–226`, Aufrufer mit `HTTPException(..., headers=...)`, etwa Agent-Zulassungsgrenzen.

**Ursache:** Der globale Handler übernimmt nur `status_code` und `detail`, nicht `exc.headers`. Die Probe übergibt 429 plus `Retry-After: 15`; der Header fehlt anschließend.

**Fix:** Header im `JSONResponse` erhalten; vorhandenes JSON-Fehlerformat berücksichtigen. Authentifizierungsheader ebenso erhalten, soweit eine Route sie setzt.

**Abnahme:** 429/503 inklusive `Retry-After` bleiben über den real registrierten Handler erhalten; Fehler ohne Header funktionieren unverändert. Nicht auf einen isolierten Test der aufrufenden Route beschränken.

### R05 — UTC-Tagesgrenze beendet bereits gestartete Berechtigungen

**In zwei Sätzen:** Ein kurz vor Mitternacht gestarteter Vergleich kann seine Berechtigung verlieren, bevor der Consensus fertig ist. Bereits geleistete Modellarbeit ist dann bezahlt, aber der folgende Verarbeitungsschritt wird abgewiesen.

**P2 · R/S.** Einstieg: `app/services/usage_repository.py:authorize_operation`, `reserve`, `authorize`/Receipt-Prüfungen (u. a. 277, 400, 424, 533); `app/api/routers/chat.py:1147–1154`; `app/services/api_consensus_runner.py:recover_persisted_runs`.

**Ablauf:** Reservierung um 23:59:59 UTC setzt `expires_at` auf 00:00:00. `/prepare` verbraucht den Slot vor dem Fan-out; ein späterer `/ask`-/`/consensus`-Operationsclaim trifft auf den abgelaufenen Beleg. Zusätzlich bleibt ein API-Run in `accepted`, wenn Usage-Reservierung erfolgreich war, `mark_reserved` aber scheiterte: Recovery fängt den späteren Expiry-Fehler nur ab und versucht es bis zur Inhaltsretention wieder. Die Probe bestätigt die Zwei-Sekunden-Expiry; die vollständigen beiden Ablaufketten sind statisch belegt.

**Fix:** Abrechnungstag und begrenzte Ausführungs-/Retry-Gültigkeit getrennt speichern. Ein am Vortag belasteter Run darf seine bereits autorisierten Schritte beenden; neue Runs zählen für den neuen Tag. Nicht mehr wiederherstellbare Accepted-Runs in einen erklärbaren Terminalstatus überführen.

**Abnahme:** Uhr kontrollieren: Start vor Mitternacht, Abschluss danach ohne zweite Belastung; neue Anfrage zählt am Folgetag. Absturz zwischen Usage-Reserve und API-Markierung erzeugt weder Endlosschleife noch doppelte Providerarbeit.

### R06 — EOF und Tokenlimit werden als erfolgreicher Abschluss behandelt

**In zwei Sätzen:** Eine abgebrochene Modellantwort kann in der Oberfläche wie eine vollständig erzeugte Antwort aussehen. Der Consensus verarbeitet dann möglicherweise einen Satz, dessen entscheidende Einschränkung fehlt.

**P1 · R/S.** Einstieg: `app/services/llm/streaming.py:282–347`, `stream_chat_completion_text`; `app/services/llm/consensus_engine.py:stream_consensus` (u. a. 2522).

**Ursache:** Sobald mindestens ein Textstück existiert, emittiert `_stream_openrouter_chat_completion` ein erfolgreiches `final`, auch ohne Finish-Ereignis oder bei `finish_reason=length`. Der reine Textadapter transportiert die Finish-Semantik nicht weiter; auch die Synthese betrachtet nichtleeren Text als Erfolg. Beide Varianten wurden mit echten Streaming-Funktionen und künstlichen Provider-Events bestätigt. Gemeint sind normal endende Iteratoren ohne bestätigten Abschluss beziehungsweise mit `length`; geworfene Transportfehler und ausdrücklich erkannte Cancellation haben eigene Fehlerpfade und werden hier nicht pauschal als Erfolg bezeichnet.

**Fix:** Transportabschluss als typisierten Zustand durch die gesamte Pipeline reichen: vollständig, Tokenlimit, unterbrochen, Fehler, bewusst abgebrochen. Teiltext kann sichtbar bleiben, muss aber als solcher gespeichert werden; seine Verwendung für Synthese/Beurteilung benötigt eine ausdrückliche Regel. Keine stillen Retries, die sichtbare Texte verschiedener Versuche mischen.

**Abnahme:** Delta → EOF und Delta → `length` ergeben niemals einen normalen vollständigen Erfolg; `stop` funktioniert. UI, gespeicherter Chat, Share und API liefern denselben Vollständigkeitsstatus. Ein Abbruch darf keine als fertig bewertete Synthese erzeugen.

### R07 — Unbekannter Agent-Verbrauch wird vollständig freigegeben

**In zwei Sätzen:** Fehlt die endgültige Tokenabrechnung eines Agent-Aufrufs, erhält das Konto den gesamten reservierten Betrag zurück. So können bereits angefallene Modellkosten außerhalb des wirksamen Tageslimits bleiben.

**P2 · R/B/V.** Einstieg: `app/services/agent_quota.py:59–117`; Settlement in `agent_runs.py`/`agent_sessions.py`; provisorische Usage in `app/services/llm/agent_client.py`.

**Beleg und Grenze:** `settle` entfernt die Reservierung und erhöht bei unbekannter/provisorischer Usage sowohl `unknown` als auch `unknown_released`. `remaining` zieht nur `used` und `reserved` ab. Probe: Limit 100, Reservierung 100, Settlement ohne finale Usage → wieder 100 verfügbar, 0 verwendet. Kostenumgehung setzt voraus, dass der Provider bereits kostenpflichtig gearbeitet hat, bevor die finale Usage verloren geht, beispielsweise bei Abbruch. Ein echter kostenpflichtiger Abbruch wurde nicht erzeugt. **Gegenbeleg und Einordnung:** Modulvertrag, `normalize` und Recovery geben unbekannte terminale Reservierungen ausdrücklich frei, damit Konten nicht bis Mitternacht blockiert bleiben. Das ist kein versehentlicher Rechenfehler, sondern ein bewusstes Verfügbarkeits-/Kostenrisiko; deshalb P2 mit Produktentscheidung statt des bisherigen P1-Fehlerurteils.

**Vorschlag:** Den gewünschten Vertrag zuerst festlegen: Die bestehende Freigabe abgeschlossener Reservierungen erhalten, aber eine gesonderte, begrenzte Zulassungsregel für wiederholt unbekannten Verbrauch prüfen. Alternativ kurze Unsicherheitsfrist mit automatischer Auflösung und verständlicher Anzeige; keine stillschweigende Rückkehr zur absichtlich entfernten ganztägigen Sperre. Provider-Generation-ID zur nachträglichen Messung nutzen, soweit verfügbar, und Schätzungen strikt von gemessenen Tokens trennen. Nachweislich nie gestartete Aufrufe weiterhin freigeben.

**Abnahme:** Die gewählte Regel begrenzt wiederholte Aufrufe mit unbekanntem Verbrauch, ohne abgeschlossene normale Aufrufe bis Mitternacht zu sperren. Reconciliation läuft idempotent, misst nachträglich verfügbare Usage ein und belastet keinen Aufruf doppelt. Echte Vorabfehler geben Reservierungen weiterhin frei.

## 2. Bedeutung, Herkunft und Persistenz von Ergebnissen

### R08 — Ein ungefähr passendes Zitat gilt als verifiziert

**In zwei Sätzen:** Die Zitatprüfung akzeptiert auch Texte, bei denen nur ein längeres Teilstück übereinstimmt. Dadurch kann eine falsche Zahl oder Aussage weiterhin als belegte Modellposition erscheinen.

**P2 · R.** Einstieg: `app/services/llm/consensus_engine.py:_locate_span` (1298–1316), `_verify_claims`, `_verify_differences_data` (1430 ff.).

**Beleg:** Nach erfolgloser normalisierter Vollsuche genügt ein längster gemeinsamer Teilstring mit Mindestlänge und ungefähr 60 Prozent Deckung. Ein eingereichtes Zitat mit „4000 euros“ wird gegen die Antwort „400 euros“ akzeptiert; `quote_models` enthält OpenAI und das gespeicherte Zitat wird zum abgeschnittenen Originalpräfix bis „400“. Der Code zeigt also nicht die erfundene 4000 wörtlich an, bestätigt aber trotzdem den Beleg, ohne zu prüfen, ob der Rest der Modellposition noch dazu passt.

**Fix:** Belegprüfung auf vollständige normalisierte Zitatdeckung beschränken; tolerierte Formatnormalisierung explizit definieren. Fuzzy-Matching darf die Navigation zu einer ähnlichen Passage unterstützen, aber keinen Verified-/Support-Status vergeben. Verwaiste Positionen und Claims anschließend neu bewerten.

**Abnahme:** Änderungen an Zahl, Einheit, Negation und Bedingung werden nicht als verifiziert akzeptiert. Reine typografische Varianten bleiben auffindbar. Teiltreffer tragen keinen erfolgreichen Belegstatus und keine daraus abgeleitete Sicherheit.

### R09 — Clientantworten werden als echte Modellantworten weiterverarbeitet

**In zwei Sätzen:** Ein angemeldeter Nutzer kann erfundene Antworten unter Modellnamen an den Consensus-Endpunkt schicken. Daraus entstehen gespeicherte und teilbare Ergebnisse, deren Darstellung eine echte Modellherkunft nahelegt.

**P1 · S.** Einstieg: `app/api/routers/chat.py:_incoming_answers` (343–359), `/consensus` (1239 ff.), `persist_share_result` (1434 ff.); `app/services/persistence_guard.py:record_model_vote` (313–366).

**Ursache:** Auth, Quoten, Besitzerbindung und Textlängen werden geprüft; die Herkunft der Antworttexte, Quellen und Modelllabels wird jedoch nicht an serverseitige `/ask`-Ergebnisse gebunden. Der spätere Pending-/Chat-Datensatz wird zur autoritativen Grundlage für Shares und Votes. Die Vote-Sicherung verhindert Doppelvotes und fremde Ergebnis-IDs, nicht manipulierte Ausgangsantworten. Das ist keine behauptete fremde Kontoübernahme und erlaubt keinen beliebigen garantierten Judge-Sieger; es untergräbt die Provenienz und ermöglicht die Beeinflussung der Bewertung.

**Fix:** Modellantworten mit UID, Run, Frage, konkretem Modell und Inhaltsdigest serverseitig speichern oder signierte Antwortbelege ausgeben. Consensus liest/verifiziert genau diese Antworten. Importierte Antworten, sofern gewünscht, als eigenen Modus kennzeichnen und von authentischen Modellrankings ausschließen. BYOK muss ebenfalls eine klare Herkunftsregel besitzen.

**Abnahme:** Veränderte Texte/Quellen/Modellnamen sowie Belege eines anderen Nutzers oder Runs werden abgelehnt. Browser-Retries und legitime BYOK-Ergebnisse funktionieren. Ein importiertes Ergebnis kann niemals unbemerkt als eigener Modellaufruf in Share und Rangliste erscheinen.

### R10 — Kontextabschluss verändert einen bereits abgeschlossenen Turn

**In zwei Sätzen:** Eine verspätete Kontextberechnung kann die gespeicherte Bedeutung einer schon fertigen Frage nachträglich ändern. Die Antwort und der ihr zugeordnete Kontext passen dann nicht mehr sicher zusammen.

**P2 · R/S.** Einstieg: `app/services/chat_context.py:finalize_version` (704–740), Turn-Abschluss in `app/services/chat_store.py`.

**Ablauf:** Eine Kontextberechnung besitzt eine gültige Lease; während sie läuft, wird der Zielturn anderweitig abgeschlossen. `finalize_version` liest zwar das Turn-Dokument, prüft aber weder dessen Pending-Status noch die erwartete Context-Bindung oder den aktiven Chat. Anschließend schreibt es `context_version_id` und `resolved_question` auf den Turn. Die Lease schützt die Kontextversion, nicht den inzwischen veränderten Zielturn. Der Service weist einen bereits beim Start fertigen Turn ohne verknüpfte Version korrekt ab; diese Vorprüfung schützt nicht gegen den späteren Zustandswechsel. Während der Build noch läuft, können beim Consensus-Start gespeicherte und gesendete Context-ID beide fehlen, sodass dessen Gleichheitsprüfung passiert. Offline bestätigt: Claim auf pending → Completion-Zustand → echter Finalizer schreibt die neue Lesart auf den fertigen Turn; keine Behauptung eines nachgebauten parallelen HTTP-/Firestore-Laufs.

**Fix:** Im selben Commit aktive Chat-/Turn-Zustände und erwartete Kontextrevision prüfen. Fertige Turns unveränderlich halten; verspätete Berechnungen verwerfen oder als ungebundene Version abschließen. Den erlaubten Konfliktvertrag explizit machen.

**Abnahme:** Deterministisch verschachteln: Build starten → Turn abschließen/Chat löschen → Build finalisieren. Der fertige Turn behält ursprünglichen Kontext und Frage; Löschung erzeugt keine wiederbelebten Daten. Zwei Builds können die Zielbindung nicht gegenseitig überschreiben.

### R11 — Löschbestätigung trotz liegen gebliebenem Chat

**In zwei Sätzen:** Nach dem Löschen eines Bookmarks kann das zugehörige Gespräch weiter in der Datenbank liegen. Die Oberfläche meldet trotzdem Erfolg, und eine fehlgeschlagene Löschung wird nicht dauerhaft zur Wiederholung vorgemerkt.

**P2 · S.** Einstieg: `app/api/routers/bookmarks.py:906–927`, `app/services/chat_store.py:delete_chat` (1244 ff.).

**Ursache:** Erst Bookmark löschen, danach Chat kaskadierend entfernen; spätere Exceptions werden nur geloggt. `delete_chat` setzt einen Löschzustand und passt Zähler an, bevor alle Kinddaten entfernt sind. Der Account-Löschpfad kann Restdaten später beseitigen, ersetzt aber keinen Retry dieser einzelnen Gesprächslöschung. Die Daten sind nicht zwingend über sämtliche APIs unerreichbar; betroffen sind erfolgreiche Löschzusage und Aufräumgarantie.

**Fix:** Einen dauerhaften, idempotenten Chat-Löschauftrag vor dem Entfernen des sichtbaren Handles anlegen. Tombstone verhindert neue Turn-/Kontextwrites; Worker löscht Kindkollektionen in Batches und quittiert erst danach. Fehlerzustand und Wiederholung beobachtbar halten.

**Abnahme:** Fehler nach Bookmark-Löschung und zwischen beliebigen Löschbatches simulieren; nach Neustart werden alle Restdaten entfernt. Zähler sinken genau einmal, andere Gespräche bleiben erhalten, parallele Writes können das Gespräch nicht wiederbeleben.

### R12 — Memory hat beim manuellen Speichern keinen Versionsvergleich

**In zwei Sätzen:** Zwei geöffnete Memory-Editoren können ihre Änderungen gegenseitig überschreiben. Auch eine gerade erfolgreich gespeicherte KI-Korrektur kann durch ein älteres Formular wieder verschwinden.

**P2 · R/S.** Einstieg: `app/api/routers/users.py:UserMemoryRequest`, `app/services/user_memory.py:save` (364–402), `app/services/memory_edit.py:apply` (473), `static/js/user-memory.js`.

**Ursache:** Manuelles Speichern erhöht die Revision, verlangt aber keine erwartete Ausgangsrevision. Das KI-Apply prüft seine eigene Baseline, schützt also nur gegen Änderungen vor diesem Apply, nicht gegen einen anschließenden veralteten manuellen Write. Die zusätzliche Repository-Probe speichert Original → neuere Fassung → alten Formularsnapshot: Revision steigt auf 3, Inhalt fällt auf Original zurück. Das beabsichtigte Bewahren fehlender Legacy-`notes` ist vorhanden, verhindert diesen Konflikt bei explizit gesendeten Feldern aber nicht.

**Fix:** Revision mit Profil ausliefern, im Editor halten und beim Save atomar vergleichen. Konflikt mit aktuellem Profil zurückgeben; UI bietet erneutes Laden oder bewussten Merge. Legacy-Clients benötigen eine festgelegte Übergangsregel, die neue Inhalte nicht still überschreibt.

**Abnahme:** Zwei Tabs ändern unterschiedliche Felder; der zweite veraltete Save erhält 409 und verliert seinen Entwurf nicht. Dasselbe gilt für manuell → KI und KI → manuell. Bewusstes Leeren sowie alte Clients ohne `notes` bleiben korrekt behandelt.

### R13 — Reservierter Memory-Edit wird nach Prozessabsturz nicht abgeschlossen

**In zwei Sätzen:** Stirbt der Server während einer Memory-Korrektur, kann derselbe Auftrag dauerhaft als laufend gelten. Wiederholen hilft dann nicht, obwohl längst kein Modell mehr daran arbeitet.

**P2 · R/S.** Einstieg: `app/services/memory_edit.py:reserve` (313–326), Service-Dispatch (693–712), `static/js/memory-edit.js:submitEdit`.

**Ablauf:** Request-Dokument wird `reserved`, Prozess stirbt vor Apply/Fail. Beim Retry wird der vorhandene Datensatz sofort zurückgegeben, bevor die inzwischen abgelaufene In-flight-Lease geprüft wird. Diese Lease ermöglicht einen neuen Request mit anderer ID, repariert aber den alten nicht; unverändertes Feedback im Dialog verwendet dieselbe ID erneut. Die neue Probe reserviert tatsächlich und wiederholt nach einem Tag: weiterhin `reserved`; die Route übersetzt das zu HTTP 202 / `processing`. Ein neuer Auftrag mit neuer ID ist davon zu unterscheiden.

**Fix:** Request-Lease, Ausführungsnonce und Recovery-Status einführen. Nach Ablauf eindeutig „unterbrochen, erneut versuchbar“ oder sicherer Retry unter neuer Lease; alte Ergebnisse dürfen nicht später auf eine neue Memory-Revision schreiben. Bereits entstandene Providerkosten getrennt berücksichtigen.

**Abnahme:** Absturz nach Reserve, nach Providerantwort und vor Apply reproduzieren; derselbe Auftrag erreicht einen Terminalzustand. Wiederaufnahme erzeugt höchstens einen Apply und keine doppelte Quotenbelastung. Konkurrenz und spätes Altworker-Ergebnis werden abgefangen.

## 3. Quellen, Watches und öffentliche Inhalte

### R14 — Quellenregeln ändern das Etikett statt die Auswahl

**In zwei Sätzen:** Eine Quelle kann als Primärquelle erscheinen, obwohl sie ursprünglich als Berichterstattung erkannt wurde. Das passiert ausgerechnet dann, wenn der Topic nur Primärquellen erlauben soll.

**P2 · R.** Einstieg: `app/services/topic_runner.py:_source_type` (54–60), `evidence_from_sources` (63–95); Klassifizierung in `app/services/topics.py`.

**Beleg:** Ist die erkannte Kategorie nicht erlaubt, wird `allowed[0]` zurückgegeben. Mit `allowed_types=['primary']` wird eine allgemeine News-URL dadurch zu `primary`; die anschließende echte Klassifizierung bestätigt für diese allgemeine URL sogar `role=primary` und `quality=high`. Bekannte Community-/Gerüchte-/Forschungsdomains können das deklarierte Etikett dagegen wieder übersteuern; nicht jede Quelle erhält dieselbe falsche Darstellung. Die Regel ist keine echte Filterung. Voraussetzung ist eine eingeschränkte gespeicherte/API-Konfiguration; der aktuelle Admin-Editor sendet stets alle erlaubten Typen.

**Fix:** Erkannte Rolle unverändert speichern. Nicht erlaubte Quellen explizit ausschließen oder als nicht regelkonform kennzeichnen; Quellen-IDs und Zitatverweise dürfen dabei nicht auf eine andere Quelle springen. Falls nur ausgeschlossene Quellen vorliegen, „unzureichende geeignete Evidenz“ anzeigen.

**Abnahme:** Berichterstattung bleibt Berichterstattung, auch unter Primary-only. Ausschluss lässt Quellenverweise nachvollziehbar; keine falsche Primärquellen- oder Qualitätsaufwertung. Preferred-domain-Regeln und tatsächliche Kategorie bleiben getrennte Informationen.

### R15 — Wortähnlichkeit verfehlt inhaltliche Änderungen

**In zwei Sätzen:** Eine Aussage wie „20 Euro“ kann zu „90 Euro“ wechseln und trotzdem als stabil gelten. Die öffentliche Bewegungsanzeige misst damit teilweise ähnliche Wörter statt ähnliche Bedeutung.

**P2 · R.** Einstieg: `app/services/opinion_map.py:_tokens`, `similarity`, `_movement_view` (228–286); Verwendung in Watch-/Topic-Verlauf und Benachrichtigungen.

**Beleg:** Tokens mit höchstens zwei Zeichen fallen weg; Jaccard-Ähnlichkeit unter 0,24 ist die Grenze für Bewegung. Die Probe mit identischem Satz und geändertem zweistelligem Preis ergibt **0 / Stable**, sogar mit `consensus_changed=True`. Zudem überschreibt `consensus_changed=False` sämtliche Modellbewegungen, obwohl einzelne Modelle ihre Position wechseln können, ohne den Gesamtkonsens zu ändern.

**Fix:** Semantische Bewegungsdaten aus einem ausdrücklich auf diese Aufgabe gerichteten Vergleich beziehen oder das Ergebnis ehrlich als Wortlautähnlichkeit benennen. Zahlen, Einheiten, Negationen und Bedingungen erhalten. Modellbewegung getrennt von Bewegung des Consensus modellieren; unklare Vergleichbarkeit darf nicht 0 bedeuten.

**Abnahme:** Preis, Frist, Vorzeichen, Negation und eingeschränkte Gültigkeit lösen passende Änderungen aus; reine Paraphrase nicht. Einzelmodell-Wechsel bei gleichbleibendem Consensus bleibt sichtbar. Fehlender Vergleich erzeugt „nicht beurteilbar“.

### R16 — Ein alter Watch-Lauf kann eine Pause rückgängig machen

**In zwei Sätzen:** Wenn du einen laufenden Watch pausierst, kann dessen späterer Fehler ihn wieder aktivieren. Änderungen am Zeitplan können ebenfalls durch Daten aus dem alten Lauf überschrieben werden.

**P2 · R/S.** Einstieg: `app/services/watch_service.py:update_watch` (970–1066), `complete_watch_run` (1548 ff.), `fail_watch_run` (1630–1660); PATCH-Aufruf in `app/api/routers/watch.py`.

**Ablauf:** PATCH setzt `status=paused` und `claimed_until=None`, lässt aber `current_run_id` bestehen. Ein alter Worker mit derselben ID besteht den Abschluss-/Fehlercheck; `fail_watch_run` schreibt bei weniger als drei Fehlern ausdrücklich `status=active`. Terminberechnung verwendet zudem `claimed` statt den inzwischen geänderten Einstellungen. Der separate `pause_watch`-Pfad ist strenger; er beseitigt den Fehler im regulären Updatepfad nicht. Der Heartbeat beendet bei Leaseverlust nur sich selbst, nicht den laufenden Provideraufruf. Offline mit echtem Update und Fehlerabschluss bestätigt: Watch wieder `active`, aber Owner-`active_count` weiter 0 nach dem Pausieren; die Pause wird damit zusätzlich von der Zählerlogik entkoppelt.

**Fix:** Lauf- und Konfigurationsgeneration bei relevanten Änderungen erhöhen. Completion darf Resultat historisieren, aber Status, aktuellen Zeitplan und Notification-Regeln nur unter passenden Vorbedingungen verändern. Pause muss aktive Ausführungsrechte wirksam entziehen; Zählertransaktionen beibehalten.

**Abnahme:** Lauf claimen → pausieren → Fehler/Erfolg liefern: Watch bleibt pausiert, und der Aktivzähler entspricht dem tatsächlichen Status. Änderung von Uhrzeit/Intervall während eines Laufs bleibt bestehen. Resume startet keinen zweiten Worker für dieselbe Generation; Benachrichtigungsentscheidung berücksichtigt aktuelle Abmeldung/Pause.

### R17 — Zustandsfortschritt und Benachrichtigung sind nicht dauerhaft gekoppelt

**In zwei Sätzen:** Ein Watch kann einen wichtigen Wechsel erfolgreich speichern, ohne dass die angeforderte Nachricht jemals ankommt. Ein kurzer Server- oder Versandfehler reicht dafür, weil der Versandauftrag nicht zuverlässig zur Wiederholung gespeichert ist.

**P2 · S/V.** Einstieg: `app/services/watch_scheduler.py:488–570`, `app/services/telegram_watch.py:_claim_delivery` (400 ff.), `app/services/topics.py:claim_delivery` (1267 ff.), `app/services/watch_brief.py:_claim_in_transaction` (195 ff.), `app/services/topic_runner.py`.

**Ablauf:** Watch-Abschluss verschiebt den Zeitplan, danach folgen Mail/Telegram/Follower-Versand. Zwischen beiden Schritten kann der Prozess sterben; Versandfehler rollen den Lauf bewusst nicht zurück. Ein vorhandener Telegram-Delivery-Marker verhindert auch bei misslungenem/abgebrochenem Versand einen erneuten Claim. Topic-Marker `sending` haben nach Absturz keine Wiederaufnahme; ein regulär gemeldeter Topic-Versandfehler entfernt seinen Marker dagegen korrekt. Das ermöglicht einen expliziten erneuten Claim, ist aber noch keine dauerhafte Retry-Queue. Telegram besitzt einen unmittelbaren Plaintext-Retry bei HTTP 400, keinen allgemeinen Neustart-Retry; Morning Brief ist ausdrücklich als „at-most-once“ umgesetzt und verschiebt seine Baseline vor Versand. Das ist eine bewusste Verlust-statt-Duplikat-Entscheidung, die für Änderungswarnungen überprüft werden sollte.

**Fix:** Mit Ergebniscommit eine Outbox schreiben; Delivery-ID aus Ressource, Run, Kanal und Empfänger, mit Lease, Retry-Zeit, Versuchszähler und Terminalstatus. SMTP-Akzeptanz ist nicht Zustellung im Postfach; nach unklarem Versandabschluss sind Duplikate ohne Provider-Idempotenz nicht absolut vermeidbar. Diese Grenze ausdrücklich akzeptieren, statt „exactly once“ zu versprechen. Abmeldung vor jedem Versuch prüfen.

**Abnahme:** Neustart nach Resultatcommit und vor/nach Versand verliert keinen Auftrag. Kanalfehler blockieren andere Empfänger nicht; Retry startet keine neue LLM-Pipeline. Abgemeldete Empfänger erhalten keine nachgeholten Nachrichten. Monitoring zeigt dauerhaft fehlgeschlagene Deliveries.

### R18 — Widerruf wird durch öffentliche Caches verzögert

**In zwei Sätzen:** Ein widerrufener Share kann aus einem Cache weiterhin sichtbar sein. Besonders problematisch sind historische Watch-Seiten, die der Server für ein Jahr als unveränderlich freigibt.

**P2 · B.** Einstieg: `app/services/share_snapshots.py:785–823`, `app/api/routers/share.py:30`, `934–942`; unmittelbare Widerrufszusage in `templates/terms.html:124–125`.

**Voraussetzungen:** Eine andere Prozessinstanz hat den Share noch im lokalen 300-Sekunden-Cache oder Browser/CDN hält eine erfolgreiche öffentliche Antwort. `invalidate_share_cache` wirkt nur im aktuellen Prozess. Normale Shares erlauben `s-maxage=86400` plus Stale-Zeit; historische Watch-Versionen `max-age=31536000, immutable`. Der Inhalt ist zwar historisch unveränderlich, seine öffentliche Freigabe ist widerrufbar. Ein produktives CDN-/Replica-Setup wurde nicht unterstellt oder untersucht.

**Fix:** Revocation-Status zentral und frisch prüfen, Cache-Invalidation prozessübergreifend machen und widerrufbare Inhalte nicht langfristig `immutable` ausliefern. Zulässige maximale Widerrufsverzögerung festlegen und Header/Produkttext daran ausrichten; Edge-Purge nur als belastbar integrierte Ergänzung verwenden.

**Abnahme:** Zwei isolierte Worker vorwärmen, über einen widerrufen, über beide nachlesen; historische URLs mitprüfen. Cache-Header erlauben keine längere Verfügbarkeit als vereinbart. Private Seiten bleiben `private, no-store`; Widerruf löscht nicht bloß einen einzelnen Cacheeintrag.

### R19 — Reports zählen Klicks statt unabhängiger Meldungen

**In zwei Sätzen:** Eine einzelne Person kann eine öffentliche Seite durch wiederholtes Melden aus der Suchmaschinenindexierung drängen. Das bestehende Minutenlimit verlangsamt dies nur geringfügig.

**P2 · S.** Einstieg: `app/api/routers/share.py:374–387`, `app/services/share_snapshots.py:report_share` (1731 ff.), `AUTO_NOINDEX_REPORTS`.

**Ablauf:** Jeder anonyme POST zählt, auch mit demselben Grund. Nach fünf Reports wird ein indexierter Share auf Noindex gesetzt; drei Anfragen pro Minute verhindern fünf Anfragen über zwei Rate-Limit-Fenster nicht. Kein Nachweis unabhängiger Meldender, keine dauerhafte Deduplizierung.

**Fix:** Rohmeldungen weiterhin annehmen, aber automatische Deindexierung nicht allein daran knüpfen. Möglich sind moderierte Entscheidung oder datensparsame, zeitbegrenzte Missbrauchssignale und höhere Anforderungen an automatische Maßnahmen. Keine dauerhafte Identifizierungspflicht für legitime Meldungen einführen, ohne das Produkt bewusst zu ändern.

**Abnahme:** Wiederholungen desselben anonymen Melders können nicht allein eine Seite automatisch deindexieren. Echte Meldungen bleiben bearbeitbar; Datenschutztext beschreibt das tatsächliche neue Verfahren. Parallel gesendete Reports verlieren keine Zähler.

## 4. Frontend-Lebenszyklen und Administration

### R20 — Topic-Editor speichert A als B

**In zwei Sätzen:** Nach einem fehlgeschlagenen oder langsamen Wechsel zwischen Topics kann der Editor noch den alten Inhalt zeigen. Speichern überschreibt dann den neu ausgewählten Topic mit diesem alten Inhalt.

**P2 · R.** Einstieg: `static/js/admin.js:selectAdminTopic` (2310–2320), `fillAdminTopic`, `saveAdminTopic` (2386–2406).

**Beleg:** `selectedTopicId` wechselt vor dem GET auf B; bei Fehler bleibt Formular A stehen. `saveAdminTopic` verwendet globale ID B und aktuellen Formularinhalt A. Die Probe führt die echten beiden Funktionen mit fehlgeschlagenem GET aus und beobachtet `PUT /api/admin/topics/B` mit A-Daten. Überholende erfolgreiche Antworten erzeugen denselben Fehler.

**Fix:** Ausgewählte ID, tatsächlich geladene Formular-ID und Request-Generation getrennt halten. Während des Wechsels Save deaktivieren; nur passende Antwort übernehmen. Save bindet den Snapshot an die Formular-ID und idealerweise eine serverseitige Revision. Dieselbe Regel auf weitere asynchrone Admin-Editoren anwenden, ohne ungeprüft identische Fehler zu behaupten.

**Abnahme:** A → B mit GET-Fehler erlaubt kein Speichern von A als B. A-langsam/B-schnell überschreibt B nicht mit der späten A-Antwort. Kontowechsel, neuer Topic und Refresh invalidieren offene Editorrequests.

### R21 — Dateiimport überlebt das Zurücksetzen des Entwurfs

**In zwei Sätzen:** Eine noch eingelesene Datei kann nach dem Öffnen eines gespeicherten Gesprächs plötzlich wieder als Anhang auftauchen. Wer schnell weiterarbeitet, kann sie dadurch einer anderen Frage mitgeben als beabsichtigt.

**P2 · R/S.** Einstieg: `static/js/attachments.js:addFiles` (618–681), `clearPendingAttachments` (486–490), `detachForMessage`; `showBookmarkAttachments` (778–781) und Aufruf in `static/firebase.js:2361–2362`.

**Ursache:** Verkleinern und Base64-Lesen laufen asynchron. Deren spätere Callbacks schreiben immer in das aktuelle globale `pendingAttachments`; Clear leert lediglich schon fertige Dateien und kehrt bei leerer Liste sofort zurück. Pending-Reads besitzen keine Entwurfs- oder Auth-Generation. Bereits korrekt an eine Nachricht angehängte Dateikopien sind ein anderer Zustand und sollen erhalten bleiben. Die neue jsdom-Probe lädt das vollständige Modul, verzögert nur FileReader, ruft den echten `showBookmarkAttachments`-Reset auf und beobachtet danach die Datei wieder in `pendingAttachments`.

**Fix:** Dateien während des Imports an Draft-ID und Owner-Generation binden. Clear/Detach/Neuer Chat invalidiert ausstehende Imports für diesen Entwurf; wenn möglich Reader abbrechen, ansonsten Completion verwerfen. Senden während des Imports bewusst sperren oder eindeutig erklären.

**Abnahme:** Reader künstlich verzögern, Entwurf leeren/wechseln, dann fertigstellen: kein Wiederauftauchen im neuen Entwurf. Senden während eines Imports nimmt keinen späteren Fremdanhang auf. Fehlerfreier Mehrfachimport hält Reihenfolge und Limit ein.

### R22 — SEO-Collector verliert seine Sperre bei Initialisierungsfehler

**In zwei Sätzen:** Ein früher Datenbankfehler kann die SEO-Sammlung bis zum Serverneustart blockieren. Jeder spätere Versuch meldet dann fälschlich, dass bereits eine Sammlung läuft.

**P2 · R.** Einstieg: `app/services/seo_data.py:SeoDataService.collect` (245–259, zugehöriges `finally`).

**Beleg:** Lock-Acquire geschieht vor `clock`, `date_window` und `repository.create_run`; das `try/finally` beginnt erst danach. Wirft `create_run`, bleibt die prozessweite Sperre gehalten. Probe: erster Aufruf simulierter DB-Fehler, zweiter Aufruf `CollectionAlreadyRunning`.

**Fix:** Unmittelbar nach erfolgreichem Acquire einen `try/finally`-Bereich beginnen. Fehlerhafte Run-Erstellung separat behandeln, ohne ein nicht existentes Run-Dokument vorauszusetzen.

**Abnahme:** Fehler in Clock, Datumsberechnung und Run-Anlage geben das Lock frei. Ein tatsächlich laufender Collector blockiert weiterhin einen zweiten; nach Erfolg und späterem Fehler funktioniert der nächste Aufruf.

### R23 — Memory-Dialog ist nicht an sein Ursprungskonto gebunden

**In zwei Sätzen:** Eine für Konto A ausgewählte Textstelle kann nach einem Kontowechsel versehentlich im Memory von Konto B landen. Auch eine verspätete Antwort für A kann danach noch den sichtbaren Dialog und Undo-Hinweis verändern.

**P2 · R/S.** Einstieg: `static/js/memory-edit.js:post` (342–356), `submitEdit`, `bind` (438); Auth-Generationen in `static/js/auth-session-state.js` als vorhandenes Vorbild.

**Ursache:** Auth-Events rufen lediglich `hideMenu` auf; Dialog, Auswahl, Request-ID und Undo bleiben bestehen. `post` nimmt das beim Absenden aktuelle Konto und prüft dessen UID nur nach `getIdToken`, nicht nach Fetch/JSON. Die Backend-Besitzerprüfung schützt das jeweilige Tokenkonto korrekt; der Fehler ist die Zuordnung der UI-Absicht. Die jsdom-Gegenprobe lädt das vollständige Modul: Auswahl A → Auth-Event B → Submit verwendet Token B und Auswahl A; Antwort dieses Requests nach weiterem Wechsel zu C löst Reload für C und den alten Undo-Hinweis aus. Kontowechsel etwa über einen zweiten Tab ist ausreichend; der echte Firebase-Login selbst wurde nicht automatisiert.

**Fix:** Auswahl/Dialog an UID plus Auth-Generation binden und bei jedem Auth-Wechsel schließen/leeren. Response- und Undo-Anwendung nur für die noch aktuelle Generation; laufende Fetches abbrechen, soweit sinnvoll. Vor Submit explizit die Selection-Ownership prüfen.

**Abnahme:** A öffnet Dialog → Logout/Login B → kein Absenden der A-Auswahl in B möglich. A-Request endet nach Wechsel: kein B-Reload und kein A-Undo im B-UI. Normaler Tokenrefresh desselben unveränderten Kontos funktioniert.

### R24 — Begrenzte Listen verlieren relevante Einträge vor der Filterung

**In zwei Sätzen:** Moderation und SEO können wichtige Einträge übersehen, sobald mehr Daten vorhanden sind. Einträge außerhalb des zuerst abgeschnittenen Ausschnitts kommen gar nicht bis zur eigentlichen Auswahl.

**P2 · S/B.** Einstieg: `app/services/share_snapshots.py:list_shares_for_admin` (1438–1480), `list_shares_for_owner` (1779 ff.); `app/services/seo_repository.py:list_pages`, `app/services/seo_data.py:overview` (520–522), `app/services/seo_weekly_review.py:696–697`.

**Voraussetzungen:** Mehr als 500 Shares für Moderation beziehungsweise mehr Seiten als `MAX_REVIEW_PAGES` (100) für Weekly Review. Shares werden in DB-Standardreihenfolge begrenzt, dann nach Reports gefiltert/priorisiert, ohne Fortsetzungscursor. SEO-Seiten werden alphabetisch abgeschnitten; Weekly Review lädt auch inaktive Seiten vor der späteren Auswahl. Relevanz oder neueste Änderung bestimmt diesen ersten Ausschnitt nicht. Die eigene Share-Liste ist ebenfalls begrenzt und benötigt einen klaren Fortsetzungsvertrag.

**Fix:** Relevante Filter und stabile Reihenfolge in die Abfrage verschieben und cursorbasiert durchblättern. Für begrenzte Weekly-Review-Arbeit eine dauerhafte Rotation/Queue nach letzter Prüfung und Priorität verwenden. `truncated`, Gesamt-/Restanzahl und Fortsetzung sichtbar machen, statt Vollständigkeit zu suggerieren.

**Abnahme:** Gemeldeter Share jenseits des ersten 500er-Fensters ist auffindbar. Mehr als 100 SEO-Seiten werden über mehrere Wochen fair berücksichtigt; inaktive Seiten verdrängen aktive nicht unbemerkt. Keine Duplikate oder ausgelassenen IDs an Seitengrenzen.

### R25 — Modellkonfiguration kann zwischen Prozessen auseinanderlaufen

**In zwei Sätzen:** Bei mehreren Serverprozessen können Anfragen mit unterschiedlichen Modell- und Limitkonfigurationen laufen. Ein fehlgeschlagenes Admin-Update kann außerdem eine inzwischen erfolgreich gespeicherte Änderung eines anderen Prozesses zurückrollen.

**P2 · R/B.** Einstieg: `app/api/routers/admin.py:_persist_and_activate_models` (51–75), `app/core/config.py:load_models_from_db` (1891 ff.), Konfigurationsreads im normalen Anfragepfad.

**Voraussetzungen und Ablauf:** Mindestens zwei Prozesse/Instanzen oder konkurrierende Konfigurationsautoren. Das Python-Lock schützt nur eine Instanz. Prozess A liest Revision X, schreibt A, B schreibt B, A-Aktivierung scheitert und A schreibt blind X zurück. Selbst ohne diesen Fehlerpfad wird nicht automatisch jede normale Chat-Instanz auf dieselbe neue Konfiguration synchronisiert. Die Agent-Route lädt explizit neu; das ist noch kein globaler Konsistenzvertrag. In-place-Änderungen mehrerer Dictionaries erschweren zudem einen atomaren Lesesnapshot. Die neue Probe führt den echten Persist-/Rollback-Helfer aus und schiebt beim Aktivieren einen zweiten DB-Write ein: B wird durch X ersetzt. Das belegt die Interleaving-Logik, nicht ein vermessenes Mehrprozess-Deployment.

**Fix:** Versionierte unveränderliche Konfigurationssnapshots, transaktionaler Compare-and-swap auf erwartete Revision, Aktivierungsprüfung vor Veröffentlichung soweit möglich. Worker übernehmen eine veröffentlichte Revision atomar; jeder Run speichert seine Revision. Rollback darf nur die eigene noch aktuelle Revision ersetzen.

**Abnahme:** Zwei Worker sehen dieselbe freigegebene Revision nach definierter Aktualisierungsfrist. Konkurrenz plus Aktivierungsfehler verliert keine fremde Änderung. Ein einzelner Run verwendet nicht Modellliste aus X und Limits aus Y.

## 5. Ressourcen, Betrieb und langfristige Wartbarkeit

### R26 — PDF-Textlimit begrenzt nicht die Arbeit der Extraktion

**In zwei Sätzen:** Eine kleine PDF-Datei kann bei der Verarbeitung viel Speicher oder Rechenzeit brauchen. Das Limit für den fertigen Text greift erst, nachdem eine Seite bereits vollständig verarbeitet wurde.

**P2 · B.** Einstieg: `app/services/llm/attachments.py:extract_pdf_text` (454–480), Upload-/Attachment-Grenzen im selben Modul.

**Beleg und Grenze:** Uploadgröße ist begrenzt, aber `PdfReader` und `page.extract_text()` laufen ohne gesondertes Seiten-, Dekompressions-, CPU- oder Prozessspeicherbudget. Die 24.000-Zeichen-Grenze wird erst nach `extract_text` geprüft. Kein schädliches PDF wurde ausgeführt und kein konkreter Provider-/Bibliotheksfehler behauptet; das Risiko betrifft die lokal kontrollierbare Ressourcenisolation.

**Fix:** Extraktion in begrenzten Workerprozess auslagern, Zeit-/Speicherbudget und Seitenobergrenze definieren, Abbruch sauber zurückmelden. Vorabchecks sind Ergänzung, weil komprimierte Größe die Extraktionsarbeit nicht zuverlässig vorhersagt. Für große normale Dokumente verständlichen Fallback anbieten.

**Abnahme:** Kontrollierte synthetische Stressdateien beziehungsweise instrumentierte langsame Extraktion werden innerhalb des Budgets beendet. Andere Anfragen bleiben bedienbar; temporäre Daten verschwinden. Normale PDFs und absichtlich leere/gescannte Seiten erhalten korrekte Meldungen.

### R27 — Benchmark-Budget umfasst nicht alle ausgelösten Modellaufrufe

**In zwei Sätzen:** Ein Benchmark mit gesetztem Budget kann anschließend weitere kostenpflichtige Prüfungen außerhalb dieses Budgets starten. Beim Fortsetzen werden zudem frühere Fehlversuche nicht vollständig in den bisherigen Verbrauch eingerechnet.

**P2 · S.** Einstieg: `benchmark/runner.py:spent_from_index` (110–116), `run_pilot` (815–840), `audit_option_permutation`, `audit_consensus_order`, `audit_anonymized_consensus`; CLI in `benchmark/__main__.py:233–239`.

**Ursache:** `budget` geht nur an `run`; sobald dieser nicht `stopped` meldet, starten drei weitere Auditgruppen ohne Budgetübergabe. Besonders deutlich bei Resume eines schon fertigen Runs: übersprungene Zellen verhindern nicht erneute Auditkosten. `spent_from_index` summiert ausschließlich den letzten erfolgreichen Cell-Datensatz, keine früheren kostenpflichtigen Versuche. Fehlende Usage wird im Transport teilweise zu Null, obwohl Unbekannt nicht Kostenlos bedeutet.

**Fix:** Gemeinsames Attempt-Kostenjournal für Hauptlauf, Retry und Audits; alle Calls vor Start reservieren. Budget als Schätzung kennzeichnen und unbekannte Kosten konservativ behandeln. Audits selbst resumierbar/idempotent speichern. Die Budgetkorrektur auf diese tatsächlich ausgelösten Aufrufe begrenzen; eine allgemeine Neugestaltung des Benchmarks ist dafür nicht erforderlich.

**Abnahme:** Enge Grenze stoppt vor dem ersten nicht gedeckten Auditcall. Resume wiederholt fertige Audits nicht und berücksichtigt bezahlte Fehlversuche. Hauptlauf und Bericht nennen tatsächliche Kostendeckung/Unbekannte; Modellantwortqualität wird nicht mit Transportfehlern verwechselt.

### R28 — Undo hält komplette alte Memory-Inhalte dauerhaft vor

**In zwei Sätzen:** Alte Memory-Inhalte bleiben in vollständigen Undo-Kopien gespeichert, obwohl das Rückgängigmachen nur kurz möglich ist. Wer sensible Angaben aus dem aktuellen Memory entfernt, entfernt damit diese alten Kopien noch nicht.

**P3 · V.** Einstieg: `app/services/memory_edit.py:489–509`, Undo-Prüfung (552 ff.), `app/services/retention_maintenance.py`, `templates/privacy.html:70–71`.

**Einordnung:** Dieses Verhalten ist im Privacy-Text ausdrücklich beschrieben und die Kontolöschung deckt die Daten ab. Deshalb kein behaupteter Rechtsverstoß und kein heimlich undokumentierter Datenfluss. Dennoch wachsen alte Vollprofile weiter, obwohl ihre funktionale Undo-Frist verstrichen ist.

**Vorschlag:** Inhaltsretention von minimalen Idempotenz-/Revisionsmetadaten trennen. Vollständige `before`-Profile nach Undo-Fenster plus definierter betrieblicher Frist entfernen; nötige Status-/Digest-Daten länger behalten. Produkttext an die Entscheidung anpassen.

**Abnahme:** Nach Frist enthalten Revisionen keine alten Profile mehr, Retention ist wiederholbar und Kontolöschung funktioniert weiter. Vor Frist funktioniert Undo; spätes Retry eines bereits ausgeführten Edits wird trotzdem korrekt erkannt.

### R29 — Agent-Schritte sammeln sich in einem zentralen Dokument

**In zwei Sätzen:** Lange Agent-Sitzungen sammeln immer mehr Zustandsdaten an einer gemeinsamen Stelle. Dadurch können Speichergrenzen und Schreibkonflikte den Lauf stoppen, obwohl das Tokenbudget noch reicht.

**P2 · B.** Einstieg: `app/services/agent_sessions.py:claim` (73–111), `_delegated_settlement` (186–195), `publish_agent`; `app/services/agent_policy.py:for_chat` und `snapshot` (26–45).

**Voraussetzungen:** Lange beziehungsweise stark delegierende Ausführungen innerhalb **eines einzelnen Agent-Turns**, insbesondere bei großzügigem Kontobudget. Ein neuer Turn erhält ein eigenes Root-Receipt; der Befund behauptet kein unbegrenztes Wachstum eines einzigen Dokuments über sämtliche Fragen eines Chats. `step_states`, `step_usage` und `reservations` wachsen im zentralen Receipt-Dokument; mehrere Worker aktualisieren es transaktional. Der Chat-Modus deaktiviert mehrere ursprüngliche Run-Limits zugunsten des Kontobudgets. Es existieren an anderen Stellen Checkpoint-/Payload-Grenzen, aber kein entsprechend durchgehendes Größenbudget für diesen zentralen Schrittverlauf. Eine konkrete maximale Laufanzahl oder ein gemessener Ausfall wird nicht behauptet.

**Fix:** Abgeschlossene Schritte als einzelne unveränderliche Dokumente speichern; Root nur Aggregate, aktuelle Leases und begrenzte Arbeitsmenge. Kompaktierung und Obergrenzen anhand serialisierter Größe einführen. Technische Sicherheitsgrenzen nicht ausschließlich aus einem Geld-/Tokenbudget ableiten; Überschreitung als resumierbaren Stopp darstellen.

**Abnahme:** Tausende synthetische Schritte und parallele Settlements halten den Root begrenzt, verlieren keine Usage und keine Events. Kompaktierung verändert keine laufenden Leases. Nutzer erhält bei technischem Limit einen gespeicherten, fortsetzbaren Zustand.

### R30 — Globale Watch-Lease besitzt keinen Eigentümer

**In zwei Sätzen:** Ein alter Watch-Worker kann nach Ablauf seiner eigenen Sperrzeit die Sperre eines neu gestarteten Workers löschen. Dadurch können mehr Scheduler gleichzeitig arbeiten als beabsichtigt.

**P2 · R/B.** Einstieg: `app/services/watch_service.py:_worker_lease_transaction`, `acquire_worker_lease`, `release_worker_lease` (1418–1445); Scheduler-`finally` in `app/services/watch_scheduler.py`.

**Ablauf:** A erhält Lease, arbeitet länger als deren Dauer; B übernimmt die abgelaufene Lease. A beendet seinen Durchlauf und schreibt unabhängig von einem Owner-/Nonce-Abgleich `claimed_until=None`. C kann nun starten, obwohl B noch läuft. Die separaten Watch-Claims/Run-IDs verhindern mehrere Folgefehler; dieser Befund ist keine pauschale Behauptung doppelter Ergebniscommits. Betroffen sind globale Koordination und Lastbegrenzung. Die neue Probe lässt A ablaufen, B übernehmen und weist C zunächst korrekt ab; nach A-Freigabe wird C trotz B zugelassen.

**Fix:** Owner-Token/Fencing-Generation in die globale Lease aufnehmen; nur Eigentümer darf erneuern oder freigeben. Heartbeat für lange Durchläufe, Stop bei Leaseverlust. Den bestehenden Schutz je Watch erhalten.

**Abnahme:** A ablaufen lassen → B übernehmen → A freigeben: B bleibt Eigentümer, C wird abgewiesen. Nach echtem Tod von B übernimmt C nach Frist. Alle Zeitabläufe mit kontrollierter Uhr prüfen.

### R31 — Quellen-URLs verlieren bedeutende Groß-/Kleinschreibung

**In zwei Sätzen:** Verschiedene Quellen können beim Zusammenführen fälschlich zu einer Quelle werden. Das passiert, wenn sich ihr Pfad oder ein Parameter nur durch Groß- und Kleinschreibung unterscheidet.

**P2 · R.** Einstieg: `static/js/sources.js:normalizeEvidenceUrl` (438–448), `mergeEvidenceSourcesInto` (452 ff.), Quellen-ID-Neuzuordnung.

**Beleg:** Die gesamte URL wird mit `toLowerCase()` normalisiert. `https://example.test/Report?key=AbC` und `https://example.test/report?key=abc` ergeben denselben Schlüssel, obwohl die Ressourcen unterschiedlich sein können. Auch das pauschale Entfernen des abschließenden Slash benötigt einen begründeten Ressourcenvertrag.

**Fix:** Nur eindeutig bedeutungsfreie Bestandteile normalisieren, insbesondere Scheme/Hostname. Pfad und Parameterwerte erhalten; Trackingparameter nur nach expliziter Regel entfernen. Fragment- und Slash-Strategie bewusst wählen und mit Backend-Kanonisierung abstimmen.

**Abnahme:** Beide Beispiel-URLs behalten getrennte Quellen und korrekte Zitat-IDs. Unterschiede allein in Host-Großschreibung deduplizieren weiterhin. Keine Quellenreferenz springt nach Merge auf ein anderes Dokument.

### R32 — Publisher-UI behauptet einen nicht vorhandenen Provider-Ausschluss

**In zwei Sätzen:** Im Publisher-Admin steht, dass DeepSeek ausgeschlossen sei. Die aktuelle Serverkonfiguration und der gespeicherte Modellplan gewährleisten diesen Ausschluss jedoch nicht.

**P3 · S.** Einstieg: `templates/admin.html:294–301`, `static/js/admin.js:1669`, `app/services/publisher_config.py:233`, `app/services/api_consensus_runner.py:execute_consensus_pipeline`; dieselbe veraltete Zusage in `docs/codebase-map.md`, Abschnitt 2.

**Beleg:** `public_config` liefert `excluded_providers=[]`; die Pipeline verwendet den gespeicherten Preset-Modellplan, ausdrücklich ohne heimliches Entfernen eines Providers. Das ist kein Fehler des Modellplans: Der widersprechende UI-Text ist der Fehler. Auch innerhalb des Admin-Templates gibt es abweichende neuere Hinweise.

**Fix:** Statische Ausschlussbehauptung in UI und Architekturkarte entfernen und tatsächlich konfigurierte Familien anzeigen. Falls ein Ausschluss gewünscht wird, muss er zuerst als klare Produktregel im initialen Plan und im Watch-Rerun umgesetzt werden; diesen Auftrag nicht aus altem Text ableiten.

**Abnahme:** Admin zeigt für Initiallauf und Rerun exakt die serverseitigen Provider. Presetwechsel aktualisiert die Darstellung; keine unbelegte Zusage zu Anbieter- oder Länderbeschränkungen bleibt stehen.

### R33 — Alte Topic-Versionen sind gespeichert, aber nicht mehr verlinkbar

**In zwei Sätzen:** Nach genügend Topic-Läufen kann ein früherer Versionslink plötzlich 404 liefern. Die Version ist noch gespeichert, wird aber bei der Suche nach ihr nicht mehr geladen.

**P2 · S.** Einstieg: `app/api/routers/topics.py:344–352`, `app/services/topics.py:list_runs` (855–910), vorhandenes `get_run`.

**Ablauf:** Öffentliche Route lädt `list_runs` mit Standardlimit 100 und sucht `?version=...` ausschließlich in dieser Liste. Eine ältere gültige Version scheitert dadurch; der alte Direktlink lebt kürzer als das gespeicherte unveränderliche Ergebnis. Abgeleitete Aussagen zum gesamten Verlauf benötigen ebenfalls eine klare Grenze, wenn nur die jüngsten 100 Checks vorliegen.

**Fix:** Explizite Versions-ID direkt unter dem bereits autorisierten öffentlichen Topic laden. Verlauf separat paginieren und begrenzten Ausschnitt kenntlich machen. Bei historischen Ansichten Vergleichsbaseline und Zeitraum bewusst auf die gewählte Version beziehen.

**Abnahme:** 101 oder mehr Runs anlegen: ältester gültiger Link funktioniert weiterhin, fremde/nicht existente ID liefert 404. Aktuelle Ansicht bleibt begrenzt schnell; Counts und „seit letztem Besuch“ behaupten keine Vollständigkeit bei abgeschnittenem Verlauf.

## Das große Ganze: sinnvolle Umsetzungspakete

Ein Komplettumbau ist nicht der erste Schritt. Mehrere gute Schutzmechanismen sind bereits vorhanden: Account-Lösch-Tombstones, serverseitige Besitzerprüfungen, transaktionale Quoten, Run-Tokens, sanitisiertes öffentliches Markdown, SSRF-/Netzwerkgrenzen für Quellenabrufe und isolierte Entwicklungsprofile. Diese Mechanismen sollten systematisch auf die noch offenen Übergänge ausgedehnt werden, statt parallele Sonderlösungen einzuführen.

1. **Sicherheitsgrenzen zuerst:** R01 und R02 separat und klein beheben; R09 als eigener Provenienzvertrag mit Migration behandeln. Danach nicht nur HTML-Rendering, sondern auch Speicherung und öffentliche Ableitungen prüfen.
2. **Kosten und Ausführungsidentität:** R03 und R05 gemeinsam entwerfen, R07 mit ausdrücklicher Kosten-/Verfügbarkeitsentscheidung ergänzen; R04 als kleiner unabhängiger Fix. Gemeinsame Invariante: Jede kostenpflichtige Ausführung gehört zu genau einem nicht wiederverwendbaren Beleg, dessen Tagesabrechnung und Ausführungszustand getrennt sind.
3. **Ehrliche Ergebniszustände:** R06, R08, R14, R15 und R31. Ein explizites Ergebnismodell für Vollständigkeit, Herkunft, Quellenbeleg und Vergleichbarkeit bis in Chat, API, Share und Watch weiterreichen; „fehlend/unklar“ darf nicht zu „erfolgreich/stabil“ werden.
4. **Revisionen und verspätete Arbeit:** R10, R12, R13, R16, R20, R21, R23 und R25. Backend verwendet Compare-and-swap/Fencing, Frontend eine kleine gemeinsame Operation-Identität aus Auth-, Draft-/Entity- und Request-Generation. Die vorhandenen neueren Run-/Auth-Module als Vorbild nehmen; kein gleichzeitiger Austausch des gesamten `window.App`-Systems.
5. **Dauerhafte Nebenwirkungen:** R11, R17, R18 und R30. Löschjobs, Versandoutbox und widerrufbare Veröffentlichung brauchen getrennte, wiederaufnehmbare Zustände. Erfolgreicher LLM-Run bleibt erfolgreich, auch wenn eine Nachricht noch aussteht; erfolgreicher Versand ist nicht dasselbe wie erfolgreicher Ergebniscommit.
6. **Wachstum und Bedienbarkeit:** R22, R24, R26–R29, R32 und R33. Pagination, Ressourcenbudgets, Kostennachweise und Retention vor höherem Volumen absichern. Oberflächen sollen begrenzte Datenmengen und veraltete Informationen erkennen lassen.

### Arbeitsauftrag für eine spätere Codex-Sitzung

> Lies zunächst `docs/code-review/README.md` und den konkreten Eintrag. Prüfe, ob der Befund im aktuellen HEAD noch besteht; die Referenzbasis ist oben angegeben. Implementiere das kleinste konsistente Paket einschließlich der genannten Randfälle, Migrationen und Abnahmekriterien. Verwende die Offline-Belege nur als Fehlernachweis und drehe ihre Assertions in Regressionstests des Sollverhaltens um. Erhalte Quoten-, Besitzer-, Lösch- und Idempotenzgarantien. Aktualisiere die Codebase-Map bei Architektur-/Flow-Änderungen und baue Frontendänderungen gemäß AGENTS.md. Markiere den Befund erst mit Fix-Commit, tatsächlicher Validierung und verbleibenden Grenzen als erledigt. Ziehe Erkenntnisse aus dem separaten Testaudit erst in dieser Umsetzungssitzung ergänzend hinzu.

### Bewusst nicht als gesicherte Fehler geführt

- Die API-Key-Limitierung besitzt zusätzliche IP-Limits; aus einem formalen Präfix allein wurde kein vollständiger Rate-Limit-Bypass abgeleitet.
- Der DeepSeek-Einsatz des Publishers ist nach aktuellem Code beabsichtigt; R32 korrigiert den Text, nicht heimlich das Produktverhalten.
- Fehlgeschlagene Differences-Analysen liefern an wichtigen Stellen `None`; eine pauschale Behauptung, jeder Judge-Ausfall werde grün angezeigt, wäre nicht belegt.
- Alte Bookmark-ID- und Demo-Pfade enthalten verdächtige Muster, aber deren praktische Erreichbarkeit wurde nicht hinreichend belegt, um daraus eigenständige Fehler zu machen.
- Es wurde keine gesetzliche Konformitätsprüfung, keine vollständige Abhängigkeits-CVE-Prüfung und kein Penetrationstest gegen Produktion durchgeführt. R02 basiert auf einem konkret geprüften Hersteller-Advisory; weitere Abhängigkeiten sind dadurch nicht als sicher bewertet.

# Widersprüche anhand vorhandener Quellen prüfen (v4)

Neue Runs prüfen ausschließlich geeignete, von Differences erkannte faktische
Widersprüche anhand bereits vorhandener Modellquellen. Das ist **keine vollständige
Faktenprüfung des Consensus**. Consensus, Agreement, Coverage und Modellpositionen
bleiben unverändert; `/resolve` ist eine unabhängige, explizit gestartete Modellrunde.
Die alten v1–v3-Verträge stehen weiter unten und gelten nur für alte Prüfungen.

Differences und Claims behalten ihre bisherige Erkennung, Markierung und
Bewertung – auch bei Empfehlungen, abweichenden Präferenzen und deaktivierter
Quellenprüfung. `factual_check` filtert ausschließlich den separaten Prüfauftrag.
Ein Fehler beim Quellen-UI darf den Aufbau der Differences/Claims nicht abbrechen.

## Synthese und Auslösung

`consensus_engine.py` behält Quelleninformationen im Synthese-Input und verbietet
S-Verweise in der Ausgabe. `llm/consensus_citations.py` entfernt unerwartete
S-Citation-Marker inkrementell vor Ausgabe, Differences und Speicherung. Der
Scanner erhält Codebeispiele, Code-Fences und Mathematik und behandelt über
Stream-Chunks geteilte Marker/Delimiter konsistent. Normale Prosa wird sofort
weitergegeben. Modellantworten behalten ihre Quellen; gespeicherte Consensus-Texte
werden beim Lesen nicht nachträglich bereinigt.

Der vorhandene Differences-Aufruf liefert zusätzlich
`factual_check: {checkable: boolean, question: string, reason: string}` pro
Difference. Präferenzen, Empfehlungen und bloße Schwerpunkte sind ausdrücklich
nicht prüfbar. Der Server validiert Consensus-Anker und Modellzitate und ergänzt
`consensus_anchor_validated` sowie `positions[].quote_models`. Fehlende Angaben
in Legacy-Differences werden nicht als Freigabe interpretiert. Ein separater
Klassifizierungsaufruf wird nicht verwendet.

Nur `type: contradiction`, `severity: major`, `checkable: true`, eine nichtleere
Streitfrage und validierte Anker aller Positionen ergeben einen Prüfauftrag.
Die Quellenprüfung startet nach erfolgreichem Differences-Abschluss in
`consensus_pipeline.py` und im separaten SSE-Pfad von `chat.py`. Der Browser
bekommt `consensus.final` schon davor, dann `differences.final`, anschließend den
`source_verification`-Jobverweis. HTTP-/SSE-Abschluss warten nicht auf Fetch/Judge.
API, Watches und Topics benutzen dieselbe Pipeline mit ihrem Owner-/Run-Kontext.

## Modus, Identität und Ergebnisse

`schema_version: 4`, `check_type: contradiction_evidence` und
`prompt_version: contradiction-evidence-v3` unterscheiden neue Prüfungen.
`source_verification.py` bleibt der gemeinsame Entry Point und dispatcht
`plan_source_verification`, `execute_source_package`, `merge_source_verification`
und `verify_sources` in den neuen Modus von `contradiction_verification.py`.
Dafür übergeben Aufrufer `differences_data`, `model_answers`, `model_sources`
und `run_id`. Ohne `differences_data` bleibt der Legacy-v3-Vertrag verfügbar.

Ein Finding beschreibt einen ganzen Streitpunkt, kein Satz-/Quellen-Paar:

- `contradiction_id`, `difference_index`, `run_id`, `answer_version`, `positions_version`.
- `question`, `consensus_anchor`, `anchor_occurrence`, `positions` mit stabilen P1/P2-IDs,
  Originalzitat, Stance (`summary`), Modellen und tatsächlichen Zitatgebern.
- `state: pending|checked|unavailable|omitted`, `checked`, `reason_code`, `reason`.
- `verdict: supports_position|conditions_explain|sources_conflict|insufficient_evidence`.
- `supported_position_id` nur für die ausdrücklich gestützte Position.
- `evidence[]` mit `source_id`, `position_id`, Originalzitat, Datum, Geltungsbereich
  und Einschränkungen. `checked_at` und Dokumentprovenienz bleiben verfügbar.

Vor der Quellenprüfung ausgeschlossene große Widersprüche stehen separat in
`exclusions[]`: `exclusion_id`, Run-/Antwortbindung, Difference-Index, Anker,
ursprüngliche Positionen, `positions_version`, Streitfrage und alle `reason_codes`.
`not_factual` protokolliert die Klassifizierung, `missing_checkability`,
`invalid_consensus_anchor` und `unverified_model_positions` die fehlenden
Prüfvoraussetzungen. `scope.detected_contradictions` und
`scope.excluded_contradictions` erhalten die erkannten bzw. ausgeschlossenen
Streitpunkte auch dann, wenn kein Judge-Auftrag entstehen konnte. Ohne Auftrag,
aber mit technischen Ausschlüssen lautet der Grund
`contradiction_inputs_unavailable`, nicht `no_checkable_contradictions`.
Diese Diagnosen sind keine Quellenurteile und werden direkt an der Difference
angezeigt. Alte v4-Snapshots ohne `exclusions` können entsprechende Hinweise aus
ihren vorhandenen Differences für die Anzeige ableiten; gespeicherte Inhalte
werden dafür nicht umgeschrieben. Der neue Promptvertrag trennt Cache- und
Idempotenzschlüssel von bisherigen Prüfungen.

Ob ein Ereignis stattgefunden hat, ist eine faktische Streitfrage. Abweichende
Datumsannahmen oder unbelegte Berichte machen sie nicht zu einer Präferenz oder
automatisch zu Fiktion. Fehlende Evidenz wird erst in der Quellenprüfung als
unzureichend bewertet; sie ist kein Grund, eine Tatsachenfrage auszufiltern.

Die ID bindet Promptvertrag, Run, Antwortversion, Difference, Frage, Anker und
Positionen. Der dauerhafte Jobschlüssel bindet zusätzlich den vollständigen
Prüfplan, Quellen, Frage/Folgekontext und eingefrorene Limits. Ändert sich eine
geprüfte Position, darf kein früherer Befund übernommen werden. Result-Commit,
Merge, Owner-/Public-Polling und Browser-Kartenbindung prüfen diese Identität.

Ein substanzielles Urteil braucht valide wortgetreue Belegpassagen. Zitate müssen
sowohl im tatsächlich gesendeten Auszug als auch im abgerufenen Originaltext
vorkommen und einer dem Streitpunkt zugeordneten Quelle und Position angehören.
Bis zu acht Zitate mit je 400 und insgesamt 1.600 Zeichen sind zulässig.
Erfundene Zitate, falsche Zuordnung und nicht belegte Datumsangaben sind keine
Evidenz. Widersprüchliche Quellen und unterschiedliche Bedingungen benötigen
Belege für alle Positionen. Eine gestützte Position braucht ihre eigenen Belege;
fehlt die Gegenseite im Abruf, wird daraus kein Sieg durch Quellenmangel.

Abgelehnte Findings behalten ihre kompatible Kategorie `evidence_mismatch` oder
`invalid_output` und speichern zusätzlich bis zu zwölf `validation_errors`.
Jeder Eintrag enthält einen stabilen `code` und gegebenenfalls `evidence_index`
(nullbasiert), `source_id` und `position_id`. Nur dem Prüfauftrag bekannte IDs
werden übernommen, keine Rohzitate, freien Modellfehlermeldungen oder Credentials.
Die Codes unterscheiden unter anderem `quote_not_in_passages`,
`quote_not_in_original`, `source_position_mismatch`, `date_not_in_source`,
`missing_required_evidence`, ungültige Felder und überschrittene Beleglimits.
Die Diagnosen bleiben über Job-Persistenz, Polling und Wiederherstellung erhalten
und erscheinen verständlich mit Belegnummer/Quelle direkt an der Contradiction.
Historische Ablehnungen ohne Diagnose bleiben ausdrücklich unspezifisch; fehlende
Details werden nicht nachträglich erfunden. Abgelehnte Zitate werden niemals als
validierte Evidenz dargestellt.

Datierung, Geltungsbereich, Populationen, Definitionen und Einschränkungen sind
Teil der Beurteilung. Abruf- oder Copyrightdatum beweisen keine Aktualität.
Modellmehrheit ist kein Quellenbeweis; fehlende Quellen, Fetch-Fehler und fehlende
Belege sind keine Widerlegung. Auch ein korrekt validiertes Quellenzitat beweist
nicht, dass sein Dokument inhaltlich wahr ist. Webseiten- und Modelltext bleiben
untrusted data. Die Zitatvalidierung ersetzt keine semantische Wahrheitsgarantie.

## Quellenwahl und Gesamtbudgets

`source_catalog.py` und die modellbezogenen Quellen bleiben die einzigen
Quellenbestände. Direkte Zuordnung entsteht aus der strittigen Originalpassage
und ihren unmittelbar zugehörigen Referenzen. Ohne direkte Zuordnung werden
begrenzt vorhandene Quellen des jeweiligen Modells, andernfalls des gemeinsamen
Katalogs, herangezogen. Dieser Fallback ist als `origin: catalog_fallback`
markiert; direkte Zuordnung als `reference`. Eine Round-Robin-Auswahl berücksichtigt
alle Positionen vor zusätzlichen URLs einer Seite. Reicht das URL-Budget nicht
für eine vorhandene Gegenseite, bleibt die Prüfung ausdrücklich ausgelassen.
Teilweise begrenzte Quellenabdeckung trägt `coverage_limited`/`omitted_sources`.

URL-identische Dokumente werden einmal sicher abgerufen; relevante Passagen
werden je Position ausgewählt und bleiben gemeinsam erhalten. Prüfinterne
D-IDs identifizieren kanonische URLs, S-IDs in Modellantworten bleiben erhalten.
`source_documents.py` übernimmt den bisherigen sicheren Abruf, Bytebudgets und
Passageauswahl. Es gibt **keine neue Websuche** und keinen Browserabruf als Fallback.
PDF und sonstige nicht unterstützte Formate bleiben explizit nicht abrufbar.

Ein v4-Job hat genau ein begrenztes Paket und einen primären Judge-Aufruf.
Ein optional konfiguriertes Ersatzmodell erlaubt höchstens einen zusätzlichen
Versuch bei technischen Ausfällen. Die folgenden Limits gelten für den gesamten Auftrag und
werden bei Aufnahme gespeichert; Umgebungsschlüssel haben Präfix
`SOURCE_VERIFICATION_`. Positive Werte sind höchstens viermal so groß wie Default.

| Suffix | Default | Gesamtgrenze |
| --- | ---: | --- |
| MAX_CONTRADICTIONS | 4 | Automatisch zu untersuchende Streitpunkte |
| MAX_URLS | 8 | Eindeutige vorhandene Dokument-URLs |
| INPUT_TOKENS | 24000 | Konservative UTF-8-Byte-Obergrenze inkl. Prompt/Envelope |
| TOTAL_SECONDS | 60 | Aktive Ausführung des gesamten Pakets |
| FALLBACK_SOURCES_PER_POSITION | 2 | Katalogergänzung pro Position ohne direkte Zuordnung |

Bestehende `INPUT_CHARS` (32000), `DOCUMENT_CHARS` (4000), `TOTAL_CHARS` (24000),
`MAX_BYTES` (400000), `FETCH_SECONDS` (5), `OUTPUT_TOKENS` (3000) und
`OUTPUT_CHARS` (20000) begrenzen zusätzlich Input, Passagen, Abruf und Ausgabe.
Auslassungen bleiben als Findings mit `contradiction_limit`, `url_limit`,
`input_limit` oder `time_limit` sichtbar. Ein Tokenbudget ist eine obere Schranke,
kein Versprechen, es voll auszunutzen. Queue-Wartezeit/BYOK-Pausen gehören nicht
zur aktiven Ausführungszeit. Repository-RPCs behalten ihre eigenen Zeitgrenzen.

## Jobs, Wiederaufnahme und alte Daten

Im Adminbereich stehen `Source-check model` und `Source-check fallback model`.
Die Felder `app_config/models.source_verification_model` und
`source_verification_fallback_model` speichern vollständige OpenRouter-IDs.
Der Fallback ist standardmäßig leer (`Disabled`); Gemini 3.5 Flash Lite ist eine
auswählbare Empfehlung, sofern ein anderes primäres Modell verwendet wird.
Gleiche Modelle und ungültige IDs werden beim Speichern abgewiesen. Alte
Admin-Payloads erhalten die vorhandene Einstellung; fehlende DB-Werte laden als
deaktiviert. Beide Modelle werden bei Job-Annahme eingefroren; alte Jobs ohne
Fallback-Feld bleiben auch nach Konfigurationsänderungen bei einem Modell.

Der Ersatzversuch erfolgt ausschließlich bei HTTP 404/429/5xx, Transportfehlern
oder einem Timeout mit verbleibendem Gesamtbudget. Fehlende/ungültige Credentials,
ungültige JSON-Ausgaben, abgelehnte Belege und fachliche Urteile lösen keinen
Fallback aus. Beide Aufrufe verwenden dieselben Owner-/BYOK-Credentials und ZDR.
Mit aktivem Ersatzmodell erhält der erste Aufruf höchstens die Hälfte der nach
Abrufen verbleibenden Zeit. Vor dem zweiten Aufruf muss auch die wiederholte
vollständige Eingabe ins gesamte Inputbudget passen. Es gibt keine weiteren
Abrufe oder Websuche durch den Fallback. `runtime.model_attempts` speichert
Modell, Status und sicheren Fehlercode, `runtime.model` das tatsächlich
verwendete Modell, `fallback_used` den zweiten Versuch. Ein Modellwechsel ist
kein erfolgreiches Quellenurteil. Der versionierte Urteilscache bindet beide
Modellwahlen und erhält die Modellprovenienz bei Cachetreffern.
Transaktionale Cache-Schreibzugriffe werden erst nach erfolgreichem Speichern
des Prüfergebnisses ausgeführt; sie können dessen Prüfdeadline nicht mehr
überschreiten. Einzelne begrenzte Cache-Lesezugriffe bleiben im Prüfbudget.
Ein v4-Paket mit bereits begonnenem, aber ungewissem Abschluss startet bei
Wiederaufnahme keine bezahlte Prüfung erneut. Es erhält `worker_interrupted`,
falls das vorherige Ergebnis nicht gesichert wurde. Eine reine Credential-Pause
verbraucht diesen Versuch nicht. Damit vervielfacht ein Speicherfehler weder
Fallback-Aufrufe noch das zugelassene Gesamtbudget.

Die vorhandenen Firestore-Jobs, Pakete, Lease-Tokens, ownergebundenes Polling,
Revisionsprüfung, BYOK-Wiederaufnahme, Parent-/Account-Löschgrenzen und Retention
werden weiterverwendet. Der Quellen-Judge kommt weiterhin aus der bestehenden
Admin-Modellkonfiguration und wird im Plan eingefroren. Dokument-Cache bleibt
UID-gebunden; Urteilscache trennt v3/v4 und bindet Modus, Prompt, Modell, Kontext,
Datum, Positionen, Originalauszüge und Ausgabegrenze. Cache-Hits werden erneut
validiert und zählen nicht als bezahlter Call.

Neue v4-Abruffehler lösen keine automatische Fetch-Wiederholung aus. Nach einem
Prozessabbruch vor dem Result-Commit beendet die Lease-Recovery das Paket ohne
erneuten Modellaufruf als nicht verfügbar. Das bleibt ausdrücklich keine
Exactly-once-Garantie für externe Modellaufrufe. Ein verlorener Own-Key
pausiert den Auftrag als `awaiting_credentials`, ohne Entwickler-Key-Fallback.

### Worker-Kompatibilität und getrennte Umgebungen

Neue Aufträge liegen physisch in `source_check_jobs_dispatch_v1_local` oder
`source_check_jobs_dispatch_v1_production`. Render (`RENDER_SERVICE_NAME`) bzw.
`ENVIRONMENT=prod/production` wählt Production, sonst Local. Protokoll und
Umgebung gehen in die weiterhin 64-stellige Job-ID ein und stehen im Header.
Worker scannen und übernehmen ausschließlich ihre eigene Queue. Dadurch kann
auch ein alter Worker, der noch gar keine Versionsfelder kennt, neue Aufträge
nicht versehentlich übernehmen. Bei inkompatiblen Änderungen am gespeicherten
Plan-/Limits-Vertrag ist eine neue Dispatch-Protokollversion erforderlich;
normale kompatible Releases behalten ihre Queue und wartenden Aufträge.

Hintergrund des Fixes vom 11.09.2026: Local und der ältere Production-Build
`6b115b7` nutzten dieselbe globale Collection `source_check_jobs`. Die dortige
`Limits`-Struktur verstand neue Contradiction-Pläne nicht. Die Wiederholungen
nach jeweils 15 Sekunden endeten irreführend als `worker_interrupted`, bevor
der Judge oder das Ersatzmodell aufgerufen werden konnten.

Die alte Collection und die andere Umgebung bleiben für owner-/versionsgebundenes
Polling, Share-/Bookmark-Wiederherstellung, Retention und Accountlöschung
zugänglich. Sie werden nicht in die neue Queue kopiert oder automatisch erneut
ausgeführt. BYOK-Wiederaufnahme auf der falschen Umgebung/Worker-Version liefert
HTTP 409, bevor der Prozess den Schlüssel übernimmt. Bestehende Ergebnisse
bleiben unverändert. Der erste historische Read sucht begrenzt in drei bekannten
Collections; ein begrenzter Prozesscache bindet folgende Reads an denselben Pfad.

Bekannte Workerfehler speichern lease-gebunden einen sicheren `last_failure`
mit Paketindex und `worker_preparation_failed`, `worker_execution_failed` oder
`result_persistence_failed`, ohne Exception-Text oder Nutzdaten. Die nächste
Wiederaufnahme übernimmt diesen Grund nur für dasselbe Paket in das Ergebnis.
`worker_interrupted` bleibt für einen unbekannten vorherigen Ausgang ohne
gespeicherte Fehlerphase. Die UI zeigt die jeweilige Phase direkt am Widerspruch.

Neue `check_sources: false` Runs speichern `status: disabled` ohne Fetch/Judge
oder `sources.*`-Events. Der Schalter und `localStorage.checkSources` bleiben
erhalten; seine eingefrorene Einstellung gilt nur für den jeweiligen neuen Run.
Alte null-Snapshots und alte v1/v2/v3-Texte/Befunde bleiben unverändert lesbar.
Ein Legacy-v3-Plan läuft weiter mit seiner damaligen Satz-/Quellen-Semantik.
Bookmarks, Shares, Chat-Turns, API, Watches und Topics speichern denselben
Jobverweis; Wiederöffnen startet keinen neuen Judge. Public-/API-Abrufe prüfen
Run/Antwortbindung zusätzlich zur Berechtigung.

## Darstellung und Abnahme

Englische UI: „Check contradictions“, Hilfetext „Check contradictions against
existing sources“. Ergebnisse stehen direkt bei ihrer Contradiction, mit
Belegpassagen, Quellenlinks, Position und Bedingungen. Topics erhalten bei Bedarf
gebundene Streitpunktkarten im Quellenbericht. Originalzitate bleiben unverändert.
Kein Zustand behauptet „Antwort verifiziert“.
Der kompakte Status und seine Begründung bleiben sichtbar; `View evidence`
öffnet Originalpassagen/Links und erhält den offenen Zustand bei Updates.
Neue Consensus-Ansichten unterbinden auch nachträgliche Quellen-Linkifizierung
numerischer Notation wie `[1]`; die ursprünglichen Modellantworten behalten
ihre Quellenverweise. Der Sanitizer erhält zusätzlich die vom Math-Renderer
unterstützten, LaTeX-haltigen Inline-Dollar-Ausdrücke.

- Keine geeigneten Widersprüche: `skipped` / `no_checkable_contradictions`,
  „No checkable contradictions detected“.
- Ausgeschaltet: `disabled`; bisher gespeichertes null bleibt Legacy/unbekannt.
- Differences fehlgeschlagen: `failed` / `differences_failed`, keine Prüfung.
- Infrastrukturfehler: `failed` / `persistence_error` bzw. konkrete Abruf-/Judgegründe.
- Fachlich unzureichend: `checked` / `insufficient_evidence`.
- Budgetauslassung: `omitted` und konkreter Grund; kein positives Abschlussurteil.

Gezielte Tests: `test_consensus_citations.py`, `test_contradiction_verification.py`,
`test_contradiction_jobs.py`, `test_consensus_chat_history.py`, die bestehenden
Source-Check-Repository-/API- und Legacy-Tests sowie JS-Tests der
Quellenprüfung/Bookmarks/Streams. Manuelle Originalquellen-Abnahme:
[source-verification-manual-review.md](source-verification-manual-review.md).
Die Beispiele messen konkrete Fehlerfälle, keine allgemeine Faktenprüfungsquote.

Abschlussstand 11.09.2026: `python -m pytest tests` **2002 bestanden**,
`npm test` **285 bestanden**, sieben gezielte Browserprüfungen (Desktop/Mobil
und öffentliche Composer-Mockups) bestanden; `npm run build` erfolgreich.
Die Live-Abnahme umfasste genau drei Judge-Aufrufe: zwei fachlich zutreffende,
originalbelegte Positionsurteile und eine sichere Enthaltung wegen
`evidence_mismatch`. Keine nachträglichen Änderungen bestehender Antworten.

---

Die folgenden Abschnitte dokumentieren ausschließlich den unverändert lesbaren
Legacy-Vertrag (v1–v3). Beschreibungen „Check Sources prüft …“ beziehen sich dort
auf damalige Jobs und nicht auf neu erzeugte v4-Consensus-Antworten.

# Historischer Vertrag: zitierte Satz-/Quellen-Paare (v1–v3)

Check Sources prueft jede im fertigen Consensus zitierte Satz-/Quellen-Zuordnung.
Unzitierte Quellen der Modellantworten und literale S-Tags in Code-Beispielen
gehoeren nicht zum Pruefumfang. Die Option wird beim Start des Runs eingefroren;
Aenderungen betreffen keine laufenden oder gespeicherten Ergebnisse. Consensus,
Coverage, Differences und Agreement bleiben von den Befunden unabhaengig.

## Belegvertrag

`schema_version: 3`, `check_type: source_evidence` und
`prompt_version: source-evidence-v3` kennzeichnen die neue Pruefung. Jeder Befund
enthaelt `support: supported|partial|contradicted|unknown`. Topic bleibt separat
`relevant|off_topic|unknown`, Zeit bleibt
`suitable|outdated|unknown|not_relevant`. Gleiche Themen bedeuten keine Belegwirkung.
Der Judge bewertet auch Zahlen, Einheiten, fehlende Bedingungen, Zielgruppen und
korrekte Zuschreibung von Meinungen. Fehlende Evidenz bedeutet unknown, nicht
contradicted. Ein historisches Dokument kann eine historische Frage beantworten.

Jedes supported-, partial- oder contradicted-Urteil braucht Originalpassagen.
Der Prompt fordert ein bis zwei Zitate mit jeweils maximal 200 Zeichen;
die harte Validierung toleriert bis zu vier mit jeweils maximal 400 und
insgesamt maximal 800 Zeichen, ohne Originalstellen abzuschneiden oder
aus einer groesseren Menge auszuwaehlen. Servercode prueft Zuordnung,
Enums, Laenge und exaktes Vorkommen sowohl im gesendeten Auszug als auch im
abgerufenen Text. Kuenstliche Verbindungen getrennter Auszuege gelten nicht als
Originalzitat. Ein zusaetzliches aeusseres Anfuehrungszeichenpaar darf entfernt
werden, wenn der verbleibende Inhalt in beiden Texten exakt vorkommt; es gibt
keine unscharfen Textvergleiche. Gruende sollen laut Prompt 120 Zeichen umfassen;
die harte Validierungsgrenze liegt bei 600 Zeichen, damit laengere Erklaerungen
keinen sonst gueltigen Befund verwerfen. Fehlende dokumentarische
Datierung erzwingt zeitliches unknown; Copyright und Abrufzeit beweisen keine
Aktualitaet. Bei unbekannter/unpassender Zeit oder unpassendem Thema wird
supported auf unknown zurueckgestuft. Die Auswertung beweist nicht die Wahrheit
der Quelle selbst. Alle Webseiteninhalte bleiben untrusted data im Judge-Prompt.

Fehlende Pflichtzitate oder ein nicht wortgetreues Zitat in einem ansonsten
strukturell gueltigen Ergebnis ergeben `evidence_mismatch`. Der gesamte Befund
bleibt `unavailable`/ungeprueft, alle drei Achsen `unknown`, ohne Zitate;
eine passende Teilmenge kann kein positives Urteil retten. Ungueltige IDs,
Enums, Duplikate, Struktur oder ueberschrittene harte Mengengrenzen bleiben
`invalid_output`. Diese Unterscheidung benoetigt keinen zweiten Modellaufruf.

`state: pending` und `reason_code: null` kennzeichnen noch ausstehende Arbeit.
`state: checked` umfasst auch ein inhaltliches unknown. `state: unavailable`
bezeichnet eine abgeschlossene, technisch oder durch harte Inputgrenzen nicht
moegliche Pruefung mit sicherem Fehlercode. Jeder abgeschlossene Befund hat sein
eigenes `checked_at`; Dokumente tragen Hash, URL und Abrufprovenienz. Die
`source_version` basiert auf Inhalt/Identitaet, nicht auf dem Abrufzeitpunkt.

## Planung und dauerhafte Ausfuehrung

`plan_source_verification(...)` erstellt einen serialisierbaren Plan mit initialem
Snapshot, stabilen Paket-IDs und allen originalen Satz-/Quellen-Paaren.
`execute_source_package(...)` fuehrt genau ein Paket aus;
`merge_source_verification(...)` fuehrt Ergebnisse idempotent zusammen. Das
kompatible `verify_sources(...)` verarbeitet alle Pakete sequenziell.

Ein Paket enthaelt eine eindeutige Dokument-URL mit deren Quellen-IDs und eine
begrenzte Anzahl Aussagen. `MAX_PAIRS`, Ausgabetokens und Inputgroesse begrenzen
das einzelne Paket, nicht den Gesamtumfang. `CLAIM_CHARS` ist ein weiches
Packziel: lange Originalsaetze werden nicht abgeschnitten. Auch bei einem
unvermeidbaren `input_limit` wird der Quellenabruf versucht und jede Zuordnung
mit explizitem Endstatus erhalten. Es gibt keine erste-Sechs-/erste-32-Auswahl
und keine nachtraegliche Snapshot-Schleife, die Befunde aus Platzgruenden loescht.

Produktive Browser-, API-, Watch- und Topic-Laufkontexte reichen Besitzer und
stabile Run-Identitaet an `source_check_jobs.py` weiter. `source_check_repository.py`
speichert einen kleinen Firestore-Jobheader, einen komprimierten Plan und
separate Paketergebnisse. Vier Worker verarbeiten begrenzte aktive Arbeit mit
persistenten 300-Sekunden-Leases. Neustarts verlieren keine wartenden Pakete.
Lease-Tokens verhindern, dass ein verspaeteter Worker ein fremdes Ergebnis
ueberschreibt; abgeschlossene Pakete werden nicht erneut gestartet. Der
Consensus-Abschluss wartet nicht auf den gesamten Quellenauftrag.

Ein Prozessabbruch nach einem externen Modellaufruf, aber vor dem Ergebnis-Commit,
kann das unfertige Paket nach Lease-Ablauf erneut ausfuehren. Es gibt keine
Exactly-once-Garantie fuer externe Calls. Der persistente Versuchszähler begrenzt
die Ausfuehrung eines Pakets auf drei Versuche; danach werden seine Paare als
nicht pruefbar abgeschlossen.

Repository-Reads und Query-Streams haben je RPC ein Fuenf-Sekunden-Timeout ohne
automatische SDK-Retries. Mehrere Reads ergeben kein gemeinsames
Fuenf-Sekunden-Budget fuer den gesamten Endpoint. Transaktionen verwenden drei
Konfliktversuche; Begin-/Commit-/Rollback-Aufrufe behalten ihre SDK-Defaults.
Die gemeinsame Account-Tombstone-Pruefung behält ihre bestehende Timeout-Policy.

Die Queue-Abfrage durchlaeuft begrenzte Seiten mit einem Snapshot-Cursor und
einem festen Zeitstichtag pro Durchlauf. Prozesslokal bleiben Cursor und noch
nicht verbrauchte Kandidaten erhalten; am Ende beginnt der Scan wieder vorne.
So koennen viele alte Own-Key-Auftraege anderer lebender Knoten spaetere lokale
oder Entwickler-Key-Auftraege nicht dauerhaft verdecken. Jeder Worker-Tick
prueft hoechstens 24 Kandidaten und laedt hoechstens eine neue Seite. Es bleibt
bei einem einzelnen next_attempt_at-Index; kein zusaetzlicher Composite-Index
ist fuer die Queue-Pagination erforderlich.

Status und alle Befunde sind owner-geschuetzt paginiert abrufbar. Eine Revision
verhindert die unbemerkte Mischung von Seiten verschiedener Bearbeitungsstaende.
Gespeicherte Chat-/Bookmark-/Share-/API-/Watch-/Topic-Snapshots tragen den Jobverweis;
Wiederoeffnen verursacht keinen erneuten Judge-Aufruf. Unreferenzierte Jobs werden
nach 30 Tagen bereinigt; existierende Elternreferenzen verlaengern die Aufbewahrung.
Account- und Ressourcenloeschungen werden vor Writes geprueft.

### Abrufvertrag

| Endpoint | Bindung |
| --- | --- |
| `GET /api/source-checks/{job_id}` | Firebase-Bearer-Token des Jobbesitzers |
| `GET /api/v1/consensus/runs/{run_id}/source-check` | `X-API-Key` der Run-UID; URL steht auch in `result.source_verification.status_url` |
| `GET /api/share/{share_id}/source-check?version=original` | Aktiver Share, veroeffentlichte Antwortversion; bei privaten Shares zusaetzlich Besitzer-Auth |
| `GET /api/share/{share_id}/source-check?version={watch_run_id}` | Aktiver Share und genau diese zugehoerige Watch-Version |
| `GET /api/topics/{slug}/source-check?version={run_id}` | Aktives/pausiertes Topic und genau diese Run-/Antwortversion |

Ohne `version` verwenden Shares den Originalstand, Topics ihren letzten Run.
Die oeffentlichen Seiten uebergeben die aktuell angezeigte Version explizit.
Ressourcenstatus und Berechtigung werden auf jeder Seite erneut geprueft.
Alle Antworten verwenden `Cache-Control: private, no-store`.

Die erste Seite verwendet `cursor=0`; jede Antwort enthaelt `source_verification`
mit Gesamtfortschritt, `revision` und hoechstens vier Paketen an Befunden sowie
`next_cursor`. Folgeaufrufe senden `cursor=next_cursor` und dieselbe `revision`.
Bei `409` beginnt der Client den gesamten Seitendurchlauf neu; Ergebnisse
verschiedener Revisionen werden nicht gemischt. Quellen und Dokumente koennen
auf mehreren Seiten vorkommen und werden anhand ihrer IDs zusammengefuehrt.
`after_revision` ist fuer spaeteres Polling der ersten Seite vorgesehen: Ist der
Stand unveraendert, liefert der Server `unchanged: true` und nur den kompakten
Header, ohne Plan- und Paketergebnisse erneut zu lesen. Fehlende oder fremde
Jobs ergeben `404`, Cursor ausserhalb des Plans `400`, nicht erreichbare
Speicherung `503`. Fehlerhafte Query-Typen oder negative Zahlen werden bereits
von der Request-Validierung mit `422` abgewiesen.

Im Browser darf `sources.final` einen solchen Jobverweis enthalten. Weder dieses
Event noch ein abgeschlossener Consensus bedeuten, dass alle Belege positiv
ausgefallen sind. History, Bookmarks und oeffentliche Seiten laden den aktuellen
Stand desselben Auftrags; sie starten keine zweite Pruefung.

Eigene OpenRouter-Keys werden nur im Prozessspeicher gehalten. Nach einem
Neustart pausiert ein solcher Auftrag mit `awaiting_credentials`, bis derselbe
authentifizierte Besitzer den Key erneut bereitstellt. Es gibt keinen Wechsel
auf einen Entwickler-Key. Keys kommen niemals in Plan, Job, Befund oder Cache.
Der Modelltransport erzwingt ZDR.

Own-Key-Jobs sind ueber eine nicht geheime Prozess-ID an den Knoten gebunden,
der ihren Key im Speicher haelt. Eine separate Heartbeat-Schleife erneuert
alle zehn Sekunden eine 30 Sekunden gueltige Prozessmarke, auch waehrend alle
Paket-Worker auf Modelle warten. Andere lebende Knoten ueberspringen solche
Auftraege ohne Bearbeitungsversuch. Nach Ablauf der Prozessmarke werden
wartende eigene-Key-Auftraege ohne Modellaufruf auf awaiting_credentials
gesetzt. Ein Resume-POST darf wartende Auftraege an seinen tatsaechlichen
HTTP-Knoten uebertragen; laufende Pakete bleiben durch ihre Lease geschuetzt.
Es wird deshalb keine sticky HTTP-Zuordnung vorausgesetzt.

`POST /api/source-checks/{job_id}/resume` erwartet den Besitzer-Bearer-Token
und `{"openrouter_key":"…"}`. Der Key wird nur im Prozessspeicher gehalten und
ist fuer den Auftrag hoechstens 24 Stunden nutzbar. Die laufende Heartbeat-Schleife
entfernt abgelaufene Keys auch ohne neue Auftraege aus dem Prozessspeicher.
Der Endpoint nimmt nur
eigene-Key-Auftraege an; Jobs mit
Server-Key liefern `409`. Das automatische Resume der UI ist auf den
urspruenglichen eigenen-Key-Modus beschraenkt.

## Dokumente, Auswahl und Wiederverwendung

`source_documents.py` ruft oeffentliche HTML-/Textdokumente ohne Cookies,
Umgebungs-Proxies, Browserausfuehrung oder Suche ab. DNS-Antworten und Redirects
werden geprueft; die Verbindung wird an die validierte IP gebunden, TLS-SNI und
Zertifikatspruefung verwenden den Originalhost. Komprimierte und dekomprimierte
Bytes sind begrenzt. Private/sonstige unsichere Ziele bleiben gesperrt.

Nach Entfernen von Navigation/Skripten wird ein vorhandener Haupt-/Artikelinhalt
bevorzugt. Abschnitte und Tabellen bleiben erhalten. Der begrenzte gesamte Body
wird extrahiert; relevante Originalpassagen werden anhand Frage und Aussagen mit
benachbarten Bedingungen ausgewaehlt. Es wird nicht nur der Dokumentanfang
geprueft. HTML-/JSON-LD-/time-/HTTP-Datierungen behalten ihre Herkunft.

Identische URLs werden im synchronen Lauf einmal abgerufen. Ein prozesslokaler
LRU haelt bis zu 128 Dokumente, Singleflight fuehrt zeitgleiche Abrufe zusammen,
ein kurzer Negativcache daempft Fehlerstuerme. Die Hintergrundauftraege verwenden
zusaetzlich tenant-gebundene Firestore-Dokument- und Judge-Caches. Der Judge-Key
enthaelt Frage, aufgeloesten Kontext, Auszuege/Metadaten, aktuelles Datum,
Modell und Promptvertrag. Cache-Ausgaben durchlaufen immer erneut den Validator;
Cache-Hits zaehlen nicht als bezahlte Calls.

Nicht unterstuetzte Formate, einschliesslich PDF, bleiben explizit
`unsupported_document`. Zugriffssperren, Timeouts, fehlende Quellen, mehrdeutige
IDs, leere Dokumente und fehlerhafte Modellantworten haben getrennte Fehlercodes.
Voruebergehende reine Abruffehler werden bis zu drei Versuche mit mindestens
31 Sekunden Abstand eingeplant, solange kein Judge-Aufruf stattgefunden hat.
Es gibt keine automatischen Wiederholungen eines fehlgeschlagenen bezahlten
Judge-Aufrufs. Bei Tokenabbruch werden nur vollstaendig decodierte und danach
validierte Befunde behalten; fehlende Befunde werden explizit unavailable.

## Oberflaeche und gespeicherte Versionen

Die Oberflaeche zeigt Fortschritt und Auffaelligkeiten statt eines pauschalen
positiven Abschluss-Hakens. Alle zitierten Quellen bleiben im Bericht sichtbar,
auch wenn sie warten oder nicht pruefbar sind. Satzansichten verbinden vorhandene
Modellpositionen mit Belegwirkung; Agreement bleibt ein separater Modellwert.
Originalzitate, Quellenlinks und konkrete Gruende sind pro Befund einsehbar.
Einzelne Belegverweise werden direkt nach einem positiven v3-Befund gruen;
Quellenkarten erst, wenn alle zugeordneten Pruefungen positiv abgeschlossen sind.
Widersprueche bleiben rot, Teilbelege/Unklarheiten gelb und ausstehende Pruefungen
neutral. Farbe wird durch Statuslabels ergaenzt. Der Tab nennt gepruefte,
ausstehende und nicht pruefbare Zuordnungen; der Bericht fasst technische
Gruende wie Zugriff verweigert, Weiterleitungsschleife und Timeout zusammen.
Quellenlisten verwenden explizite S-IDs und uebernehmen den Status auch dann,
wenn sie erst nach dem Befund gerendert werden; Ansichtswechsel loeschen ihn.
Gesammelte Modellquellen ohne Verweis im Consensus stehen ausserhalb der
Belegpruefung und tragen ein neutrales Label statt eines Warte-/Fehlerstatus.
Das gestaltete Quellen-Hover zeigt einen kurzen Hinweis, ob dieser konkrete
Belegverweis geprueft wurde, sein Ergebnis und gegebenenfalls die Begruendung.
Es macht deutlich, dass damit keine allgemeine Wahrheitsgarantie fuer die
Quelle verbunden ist. Die Befunde sind an den jeweiligen Verweis gebunden;
ein geoeffnetes Popup aktualisiert sich bei neuen Pruefergebnissen. Verweise
mit eigenem Popup haben kein natives `title`-Attribut, damit beim langen
Hover kein zweites Browser-Tooltip erscheint. Tastaturfokus, Escape und
Screenreader-Beschriftungen bleiben erhalten.

Alte gespeicherte v1/v2-Snapshots bleiben lesbar und werden nicht neu bewertet.
Ein historischer v2-Themenbefund erhaelt keine erfundene v3-Belegwirkung. Der
Legacy-Snapshotleser bleibt auf 300 kB begrenzt; grosse neue Ergebnisse werden
ueber den dauerhaften Jobverweis und Paketseiten bereitgestellt, nicht still
auf einen scheinbar vollstaendigen kleinen Snapshot gekuerzt.

## Konfiguration und Messung

Das Feld `source_verification_model` in `app_config/models` waehlt das Modell;
Standard ist `google/gemini-3.5-flash-lite`. Es ist im Admin-Bereich unter
Consensus & Deep Think → Source Checks editierbar und wird mit den anderen
Modelleinstellungen gespeichert, validiert und geladen. Ein fehlender Wert
wird beim Backfill ergaenzt; alte Admin-Tabs ohne dieses Feld behalten beim
Speichern den aktiven Wert. `SOURCE_VERIFICATION_MODEL` aus der Umgebung hat
keinen Vorrang mehr. Neue Auftraege speichern das ausgewaehlte Modell in ihren
Limits und im Snapshot; Transport und Judge-Cache verwenden genau diesen Wert.
Bereits angelegte Jobs behalten ihr gespeichertes Modell auch bei Admin-Aenderungen.
Numerische `SOURCE_VERIFICATION_*`-Limits sind positive Werte, maximal das
Vierfache des Defaults. Der Hintergrundauftrag friert sie bei der Aufnahme ein.

| Suffix | Default | Bedeutung |
| --- | ---: | --- |
| MAX_SOURCES | 6 | Kompatibilitaetsoption; Pakete verwenden genau eine URL |
| MAX_PAIRS | 32 | Maximale Paarzahl pro Paket, zusaetzlich ausgabebegrenzt |
| CLAIM_CHARS | 1200 | Weiches Packziel, keine Satzkuerzung |
| INPUT_CHARS | 32000 | Harte serialisierte Judge-Eingabegrenze |
| DOCUMENT_CHARS | 4000 | Relevante Originalauszuege pro Paket |
| TOTAL_CHARS | 24000 | Zusaetzliches Auszugsbudget |
| MAX_BYTES | 400000 | Abruf-/Extraktionsgrenze |
| FETCH_SECONDS | 5 | Einzelabruf-Frist |
| SECONDS | 60 | Paketfrist |
| OUTPUT_TOKENS | 3000 | Judge-Ausgabebudget; reduziert Paarzahl pro Paket |
| OUTPUT_CHARS | 20000 | Validierungsgrenze fuer Modellantwort |
| CACHE_SECONDS | 3600 | Positiver Dokumentcache |

PII-freie Metriken erfassen Pakete, bearbeitete Paare, Laufzeiten, Abruffehler,
Cache-Hits, Queue-/Persistenzfehler und verfuegbare Provider-Usage. URLs, Inhalte
und Credentials werden nicht zu Metriklabels oder Log-Nachrichten.

`firestore.indexes.json` enthaelt Ausnahmen fuer grosse Jobfelder und die
komprimierten Cache-/Plan-/Paket-Payloads. Die Queue benoetigt keinen neuen
Composite-Index. Die Feldkonfiguration ist als lokale Deployment-Aenderung
vorbereitet; erst das Ausrollen des Firestore-Index-Workflows aktiviert sie.

## Validierung

`tests/test_source_verification.py` deckt Originalzitate, alle Beleg-Enums,
Zeitregeln, fehlende/manipulierte Ausgabe, alle Quellen ueber Paketgrenzen,
lange Aussagen, idempotente Merges, Cache-Accounting, relevante spaete Stellen,
Singleflight, Negativcache sowie DNS-/Redirect-/Kompressionsschutz ab.
Repository-/Worker-Tests pruefen Ownergrenzen, Leases, Neustarts, Credentials,
Wiederaufnahme, Pagination und Cachekontexte. JS-Tests pruefen Fortschritt,
Befunde, Originalpassagen, sichere Ausgabe und Wiederanzeige.

`python scripts/evaluate_source_verification.py` zeigt 15 synthetische Beispiele
mit Beleg-/Themen-/Zeit-Sollwerten, einschliesslich Zahlenwiderspruch, Einheiten,
fehlender Bedingungen, Meinungszuschreibung und Prompt-Injection im Quellentext.
`--live` fuehrt kostenpflichtige Modellaufrufe aus; fuer v3 wurde bislang kein
solcher Lauf ausgefuehrt. Der Report misst Fehlalarme, uebersehene Probleme,
falsche Beleg-/Zeitbestaetigung, unbekannte/ungepruefte Ergebnisse, gelieferte
Kosten und Latenz. Offline-Tests belegen die implementierten Vertraege, nicht
allgemeine semantische Genauigkeit auf realen Webseiten.

Historische v1/v2-Live-Messwerte bleiben in den bestehenden Artefakten
`artifacts/source-verification-evaluation-guarded.json` und
`artifacts/source-verification-live-regression.json`; sie sind kein v3-Nachweis.

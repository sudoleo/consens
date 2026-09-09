# Quellenpruefung: Belegwirkung, Thema und Zeitraum (v3)

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

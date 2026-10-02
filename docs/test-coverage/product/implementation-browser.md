# Umsetzung Browser-/Frontend-Pakete, 02.10.2026

Die folgenden Einzel- und Zwischenläufe dokumentieren die Umsetzung in ihrer damaligen Reihenfolge. Damalige Hinweise auf noch folgende Emulator-/CI-/Gesamtprüfungen werden durch die integrierte Abnahme am Ende dieses Berichts aktualisiert.

## WP-01 (Frontendanteil)

Die alte exakte Klassenstringpruefung ist durch Klassenmitgliedschaft ersetzt.
Ein zusaetzlicher DOM-Fall rendert zwei echte archivierte Turns mit allen drei
Drawern: gemeinsame Zeile, eindeutige IDs, ARIA-Zustaende, korrektes Oeffnen und
Schliessen, keine Aktion im fremden Turn oder Live-Footer.

## WP-20

Fuenf neue Chromiumfaelle fuer das originale Topic-Skript: Focus/Enter und
Touchpreview mit anschliessender Navigation, inerte HTML-Notizen, neue Checks,
historischer Besuch und gesperrter Storage. Negativkontrollen pruefen keine
Elementinjektion, keine Navigation beim ersten Touch, keinen Seen-Write beim
historischen Besuch. Die bestehenden sieben DOMfaelle bleiben gruen.

## WP-21

Behoben: error-Objekte aus main erzeugen lesbare Nachrichten statt
[object Object]. Neun Clientfaelle decken beide Umschlaege, Listen, unbekannte
Objekte, Nicht-JSON, Auth und keinen automatischen zweiten Write ab. Ein
Prompteditor-Integrationstest nutzt den echten Client und prueft den erhaltenen
Entwurf nach HTTP409. Oeffentliche Admin-Cachebuster aktualisiert.

## WP-22 (Vieweranteil)

Behoben: spaete Antworten konnten die neue Auswahl ersetzen; Fehler liessen
den alten Report stehen. Generationen begrenzen jede Liste/Detailauswahl.
Sieben DOMfaelle pruefen kompakte Darstellung, inerten Nutztext, keine
Rohprompts/-antworten, verspaeteten Erfolg/Fehler, 403/404, falsche Run-ID und
Refresh auf eine leere Liste. Echte Backend-Autorisierung wird getrennt geprueft.

## WP-24

Neun dynamische Faelle fuehren das Originalskript in frischem jsdom aus.
notrack=1/0/fehlend/leer/anders und Storagefehler werden vor einem
instrumentierten Tracker-/Seitenstart geprueft. Kein getItem-Zweig erfunden.

## WP-30

Vier Dateisystemfaelle rufen vendorFrontend direkt auf kleinen synthetischen
Paketen auf. Pins, alle Lizenz-/Fontbytes, Fontreihenfolge, alte Assets,
Check-only ohne Writes, fehlende/veraltete Bytes und identische Mtime bei
unveraenderten Inputs werden geprueft. Kein Paketdownload.

## Ausgefuehrte Pruefungen

- `npm test -- tests/js/admin-api.test.mjs tests/js/admin-benchmark.test.mjs tests/js/admin-prompt-config.test.mjs tests/js/analytics-opt-out.test.mjs tests/js/vendor-frontend.test.mjs tests/js/frontend-output.test.mjs tests/js/stored-turn-markers.test.mjs tests/js/topic-page.test.mjs`: 59 bestanden.
- `UNIT_TEST_MODE=1 RUN_E2E=1 python -m pytest tests/e2e/test_topic_frontend.py tests/test_consensus_progress_ui.py tests/test_analytics_partial.py tests/test_frontend_build.py tests/test_account_tier_admin.py -q`: 48 bestanden, eine bestehende Python3.9-DeprecationWarning.
- Gesamte Frontendsuite: `npm test -- --reporter=json --outputFile=test-results/frontend-all.json`: 695 bestanden.
- Negativkontrolle: Urspruengliche Adminclient-/Viewerquellen aus HEAD voruebergehend gegen die neuen Tests ausgefuehrt; 11 Fehler, 16 bestanden. Anschliessend korrigierten Stand bytegenau wiederhergestellt.
- `npm run build`: bestanden; keine inhaltliche Aenderung der App-Bundles.

## WP-03 / WP-38 (Browseranteil)

Der Ausgangslauf der sieben betroffenen Dateien hatte 68 bestandene und 27
fehlgeschlagene Faelle. Fachlich veraltete Fixtures wurden auf ownergebundene
Antwortreceipts, Dokument-Turn-IDs und aktuelle mobile Bedienung aktualisiert.
Die Tests pruefen weiterhin die Antworten, Bindungen, gespeicherten Daten und
Fehler; fehlende Receipts duerfen sichtbar bleiben, aber keinen Consensus starten.
Sekundaertextfarben, gruppierte Quellenpills und unvollstaendige Agentantworten
folgen den aktuellen Produktvertraegen. Layoutgrenzen nutzen gerundete CSS-Pixel.

Der Scrolltest hielt zuvor einen beim finalen Markdownrender entfernten DOM-Knoten.
Er verfolgt jetzt denselben Absatzinhalt nach jedem Render weiter. Damit wurde ein
echter 48px-Sprung durch einen noch anstehenden Resize-Follow-Frame sichtbar.
chat-scroll trennt nun explizites Send/Latest vom passiven Resize-Follow. Vier
neue DOMfaelle pruefen Abschluss, sehr schnelle erste Antworten und Reduced Motion.
Die Negativkontrolle mit altem Produktcode scheitert genau am Resize-Abschlussfall
(1 fehlgeschlagen, 13 bestanden zum Zeitpunkt der Kontrolle).

Importierte Phase4-Fixtures teilen pro pytest-Lauf genau einen Serverprozess.
Ein bereits belegter Port wird abgewiesen statt unbemerkt fremden Code zu testen.
Ein Negativfall prueft dies explizit. E2E_PHASE4_PORT erlaubt parallele isolierte
Laeufe; Screenshots landen im ignorierten test-results-Verzeichnis.

- Fokussierter Abschlusslauf Scroll/Phase4: 40 bestanden, 118,51 s.
- Gesamter writerfreier Browserlauf: `UNIT_TEST_MODE=1 RUN_E2E=1 E2E_PHASE4_PORT=8043 python -m pytest tests/e2e --ignore=tests/e2e/test_smoke.py --ignore=tests/e2e/test_agent_transactions.py --ignore=tests/e2e/test_phase2_transactions.py --ignore=tests/e2e/test_prompt_config_transactions.py --ignore=tests/e2e/test_agreement_verdict.py --ignore=tests/e2e/test_run_cancel_and_progress.py -q`: 256 bestanden, 738,20 s; eine bestehende Python3.9-Warnung. JUnit: test-results/browser-all.xml.
- Emulatorfaelle werden separat gemeinsam mit den Backendpaketen geprueft.
- Abschliessende gesamte Frontendsuite: 699 bestanden; `npm run build:check` bestanden.

## WP-29: persistierte Nutzerreisen

Sechs neue Chromiumfaelle in `tests/e2e/test_persisted_journeys.py` verwenden
das originale gebaute AppFirebase, `main.app` mit normalem E2E-Lifespan und den
nativen Firestore-Emulator. Die separat gestartete `journey_server.py` ersetzt
Firebase-Identity, externe Modellantworten und Mailtransport. App-HTTP-Routen,
Auth-/Ownerpruefung, Claims, SSE, Context, Speichern und Buchungen bleiben echt;
direkte Browser-Firestore-Zugriffe schlagen fehl. Keine komplette erwartete
UI-Payload wird injiziert. Zufallsowner und gezieltes Cleanup erlauben parallele
Emulatorfaelle ohne globales Loeschen. J03 braucht fuer seinen echten Worker eine
ansonsten inaktive Quellenqueue; der Harness prueft das vor jedem Tick und
bricht vor Verarbeitung fremder faelliger Jobs ab.

- J01: zwei echte Consensuslaeufe, Bookmark-Reload und Folgefrage im gleichen
  Chat; getrennte Turn-IDs, erster Turn ohne Kontextversion und eine korrekt
  gebundene Follow-up-Kontextversion mit recent/target; fremder
  Owner mit 404. Genau zwei konsumierte regulaere Runreceipts, je eine
  Consensusbuchung und exakte Summe des gemeinsamen Tokenkontos.
- J02: echte Agent-Admission und acht gemessene Providersteps (Orchestrator,
  sechs unabhaengige Antworten, begonnene Synthese). Stop speichert eine
  Teilantwort mit failed/cancelled, bucht 1200 Tokens und gibt Reservierungen frei.
  Reload liest den nativen Snapshot; recover_only liefert ihn ohne weiteren
  Providerstart und ohne zweite Buchung.
- J03: ausdruecklich importierter historischer V3-Job fuer einen gespeicherten
  Turn. Own-Key-Resume ueber AppFirebase und echter `jobs.process_one` inklusive
  Queue-Scan, Worker-Affinitaet, Cache, Judge-Request/-Parsing, Passage-/Zitat-
  Validierung und nativen Lease-/Packagecommits. Nur Dokumentfetch und externe
  Judge-HTTP-Antwort sind Fixtures. Neun Judgecalls verwenden ausschliesslich
  den Own-Key, ein Fetch versorgt dank nativen Caches alle neun Pakete.
  Neun Findings ueber mehrere HTTP-Seiten und Revisionswechsel; alte Revision
  409, Fremdowner 404, Fremdworker ohne Claim, neun Wiederholungen gespeicherter
  Ergebnisse mit alter Lease wirkungslos. Terminaler Worker startet keinen
  weiteren Aufruf und vergisst den Key; decodierte native Plaene, Ergebnisse
  und Caches enthalten keinen Key. Die UI liest auch nach Reload 9/9.
  Neue V4-Runs erhalten keinen kuenstlichen Altjob.
- J04: der originale Saved-Bookmark-Adapter erzeugt das Pending-Result und der
  Share-Dialog publiziert ueber echtes POST. Followformular, abgefangene Mail,
  Double-Opt-in, native Watchanlage, Claim, echte Pipeline mit externem
  Modellmock und nativer Versionscommit. Eine unterscheidbare neue Antwort
  erscheint nur in ihrer Version, die Baseline bleibt unveraendert; fremde
  Shareloeschung wird abgewiesen.
- J05: nativer Memory-CAS, laufende Synthese, echte Kontoloeschung mit Tombstone,
  spaeter Providerabschluss, Wechsel auf zweiten Owner und Reload seines
  Kontrollbookmarks. Passive Callthrough-Beobachtung der echten StreamingResponse
  und ihrer echten Capacity-Lease belegt vor Release den laufenden Producer.
  Nach Release wartet der Fall explizit auf Responseende und Leasefreigabe nach
  dem Producer-/Settlement-/Cleanupabschluss. Erst dann: kein wiederbelebtes
  Konto/Unterdokument, alte Identitaet
  gesperrt, anderer Owner samt Tokenbuchung unveraendert und alte Antwort unsichtbar.
- Negativreise: ein echter erschoepfter Bookmark-Quota-Datensatz provoziert den
  Speicherfehler. Consensus und nativer completed Turn bleiben erhalten,
  Fehlerhinweis und persistence.error bleiben ehrlich; kein Bookmark wird erfunden.

Gefundener Produktfehler: AppFirebase berechnete `has_consensus` auch fuer reine
Servermetadaten aus nicht vorhandenen `responses` und verlor so das Kennzeichen.
Der Upsert uebernimmt jetzt explizite boolesche Metadaten. Der neue DOMtest
verwirft truthy Strings und priorisiert vorhandene vollstaendige Antwortdaten.
Die Nutzerreise prueft denselben Vertrag nach einem echten Save.

Grenzen: kein echter externer Login, Modell-/Maildienst oder produktiver Betrieb;
historische Fetch-/Judgeergebnisse sind deterministische externe Fixtures.
Der E2E-Lifespan unterdrueckt globale Scheduler; J04 treibt den ownergebundenen
Claim-/Pipeline-/Commitpfad gezielt. MOCK_LLM unterdrueckt Live-Pending-Publikation,
daher fuehrt J04 den realen Saved-Bookmark-Pending-Adapter aus. Traces und native
Endzustaende liegen unter test-results/journey-*.zip beziehungsweise *-state.json.

Integrierte Validierung vor der abschliessenden Worker-/Abschlussbeobachtung
(inklusive GeneratorExit-Backendfix):
`UNIT_TEST_MODE=1 RUN_E2E=1 python -m pytest tests/e2e/test_persisted_journeys.py -q
--junitxml=test-results/journeys-integrated.xml` bestand mit **6 passed** in
117,14 s. J05 hatte zuvor einen echten Abbruchfehler aufgedeckt: Beim Schliessen
des Generators konnte ein Fehler im Cleanup den GeneratorExit ersetzen. Der
integrierte Backendfix erhaelt den Abbruch und gibt die Kapazitaet frei; der
native Loesch-/Ownerwechselpfad besteht jetzt gemeinsam mit allen anderen Reisen.
Zehn direkt betroffene Bookmark-DOMfaelle bestanden ebenfalls.
`npm run build:check` bestaetigte nach dem Merge die aktuellen Assets.
Runnerbelege: `test-results/journeys-integrated.xml`,
`test-results/journeys-integrated.log` und `test-results/bookmark-final.log`.

Nach dem Review wurden J03 mit echtem Worker und J05 mit deterministischer
Producerabschluss-Beobachtung erneut gezielt geprueft:
`UNIT_TEST_MODE=1 RUN_E2E=1 python -m pytest tests/e2e/test_persisted_journeys.py -q
-k j03` ergab **1 passed, 5 deselected** in 23,11 s; `-k j05` ergab
**1 passed, 5 deselected** in 25,29 s. Belege sind
`test-results/journey-worker-recheck.{log,xml}` und
`test-results/journey-late-producer.{log,xml}`. Ein vorheriger J03-Versuch brach
vor dem Workerstart an einer abgelaufenen lokalen Keepalive-Verbindung ab;
Kontrollrequests verwenden nun ebenfalls `Connection: close`, ohne Retry.
Die komplette integrierte E2E-Suite prueft der koordinierende Hauptlauf.


## WP-03/WP-38: integrierte Smoke-Nacharbeit

Der gemeinsame Voll-CI-Lauf fand 22 Smoke-Fehler. Der Firebase-UI-Stub schrieb
noch auf die inzwischen schreibgeschuetzte `window.isUserPro`-Ansicht und brach
vor der Authinitialisierung ab. Er publiziert nun Identitaet und Tier ueber die
originalen Besitzer (`authState`, `accountTier`, `updateUserTierUI`). `app_page`
wartet auf die bekannte passende Identitaet; der erste Smoke prueft den exakten
Owner-/Generation-/Free-Zustand. Produktguards bleiben aktiv.

Die gesamte Smoke-Datei folgt wieder den gegenwaertigen Produktvertraegen:
Modus vor Textfeld, Modelle rechts beziehungsweise mobil in eigener Zeile;
Display-Settings vor Themewechsel; sichtbarer Modellpicker setzt `custom` und
persistiert die echte Benutzerauswahl. Die Splitmarkierung muss den sichtbaren
Dissens-CSS-Token verwenden, die Zahl bleibt neutral. Ueberlappende Contradiction-
Passagen behalten ihr einzelnes zugaengliches Steuerelement. Ein archivierter
Claim oeffnet im echten Reader den archivierten Turn. Der moderne V4-Lauf zeigt
keinen erfundenen Sources-Tab; vorhandene Legacyquellen pruefen separate Faelle.
Der Reader erhaelt Fokus, Escape und die Antwortverknuepfung; mobile Aktionen
wandern in den Header und auf Desktop zurueck. Copy wird wirklich geklickt,
nur die Betriebssystem-Zwischenablage wird ersetzt: konkrete Badgetexte fehlen,
ein legitimer Bruch `3/7` bleibt erhalten. Der Attachmentfall prueft den echten
HTTP-Dispatch und die unveraenderliche Providerzulassung des Runs, auch nachdem
der Picker fuer die naechste Nachricht wiederhergestellt wurde.

Ein echter Produktfehler blieb nach der Korrektur der alten Erwartungen rot:
Die Containerbreite animiert nach einem Viewport-/Sidebarwechsel weiter, nachdem
das einmalige Resize-Ereignis schon verarbeitet ist. Ein in der schmalen
Zwischenbreite geleertes Feld blieb bei 180 statt 52 Pixeln. Die Negativkontrolle
wartet auf das Ende der realen CSS-Transition und danach bis zu fuenf Sekunden;
sie scheitert mit altem Produktcode genau an dieser Hoehe. Der benachbarte
Bottom-Row-Test besteht nach demselben Transition-Wait unveraendert. Beleg:
`test-results/smoke-width-negative.{log,xml}` (1 failed, 1 passed, 18,97 s;
Basis-HEAD caa7bac6 plus uncommittierte Testaenderungen, kein sauberer Laufcommit
und kein separat archivierter pytest-Prozessexit).

Die bisherige Autosize-Logik liegt jetzt in `composer-autosize.js` vor app-init;
`App.resizeQuestionInput` und ihre bestehenden Ereignisse bleiben erhalten.
Ein nach tatsaechlicher Breite gefilterter ResizeObserver misst pro Frame
hoechstens einmal und reagiert nicht auf seine eigenen Hoehenaenderungen.
Vier neue JS-Verhaltensfaelle pruefen Endbreite ohne weiteres Viewportereignis,
Framebuendelung/keine Hoehenschleife, Multiline-Bestaendigkeit sowie bestehende
Placeholder-/Viewportreaktionen. Der Python-Strukturfall prueft zusaetzlich
Initialisierung und reale Bundlereihenfolge statt alter Funktionspositionen.

Mockgrenzen: Diese Smoke-Suite behaelt ihren vollstaendigen Firebase-Clientstub,
MOCK_AUTH und MOCK_LLM. Der Watch-Validierungsfall setzt einen ausdruecklichen
Result-Kontext und eine konfigurierte, noch nicht verbundene Telegramgrenze;
er behauptet keine echte Publikation. Tierwechsel nutzen zwei ausdruecklich
verschiedene Katalogoptionen, damit identische Produktionsdefaults den Test
nicht ausschalten. Native Persistenz, Publikation und Buchungen deckt WP-29 ab.

Gezielte Pruefungen: `npm exec vitest run tests/js/composer-autosize.test.mjs`
**4 passed**, `UNIT_TEST_MODE=1 python -m pytest tests/test_navigation_settings_ui.py -q`
**27 passed**. `npm run build` wurde nach Integration von a831e3e1 ausgefuehrt.
Logs: `test-results/smoke-autosize-js.log`, `test-results/smoke-navigation.log`.

Der Abschlusslauf auf a831e3e1 plus diesem Patch bestand vollstaendig:
`UNIT_TEST_MODE=1 RUN_E2E=1 FIRESTORE_EMULATOR_HOST=127.0.0.1:8085 E2E_PORT=8031
python -m pytest tests/e2e/test_smoke.py -q --junitxml=test-results/smoke-final.xml`
ergab **43 passed** in 102,06 s, pytest-Exit **0**. Die bestehende Python3.9-
DeprecationWarning betrifft den asyncio-Subprozessadapter. Belege:
`test-results/smoke-final.{log,xml}`, `test-results/smoke-final.exit`.
Der lange Reader-/Copy-/Run-again-Fall bestand zuvor einzeln mit **1 passed**
in 16,35 s (`test-results/smoke-reader7.{log,xml}`). `npm run build:check`
bestand ebenfalls (`test-results/smoke-build-check.log`); das neue generierte
Appbundle enthaelt LF, keine CRLF-Normalisierung. Ganze JS-/E2E-/CI-Pruefungen
fuer den integrierten Abschluss uebernimmt der koordinierende Hauptlauf.

## Integrierte Abnahme vom 02.10.2026

Zusammengeführter Code `ffaca3df`. Python: 3.303 bestanden; JavaScript: 705 bestanden; Chromium / native SDK / Smoke: 368 bestanden; Firestore-Clientregeln: 49 bestanden. Die tatsächlichen Befehle und Quellstände pro Lauf stehen in [execution.json](../execution.json); dieser Abschluss ersetzt keine historischen Primärergebnisse. [Aktueller Paketstatus](work-packages.md) und [Laufbericht](../findings.md) sind für die heutige Abnahme maßgeblich.

38 der 38 Arbeitspakete sind vollständig abgenommen. Die in den Berichten benannten Betriebsgrenzen bleiben ausdrücklich bestehen.

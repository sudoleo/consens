# Umsetzung Browser-/Frontend-Pakete, 02.10.2026

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
Emulatorfaelle ohne globales Loeschen.

- J01: zwei echte Consensuslaeufe, Bookmark-Reload und Folgefrage im gleichen
  Chat; getrennte Turn-/Context-IDs, autoritative recent-/target-Bindung, fremder
  Owner mit 404. Genau zwei konsumierte regulaere Runreceipts, je eine
  Consensusbuchung und exakte Summe des gemeinsamen Tokenkontos.
- J02: echte Agent-Admission und acht gemessene Providersteps (Orchestrator,
  sechs unabhaengige Antworten, begonnene Synthese). Stop speichert eine
  Teilantwort mit failed/cancelled, bucht 1200 Tokens und gibt Reservierungen frei.
  Reload liest den nativen Snapshot; recover_only liefert ihn ohne weiteren
  Providerstart und ohne zweite Buchung.
- J03: ausdruecklich importierter historischer V3-Job fuer einen gespeicherten
  Turn. Echte native Lease-/Packagecommits, Own-Key-Resume ueber AppFirebase,
  neun Findings ueber mehrere HTTP-Seiten und Revisionswechsel; alte Revision
  409, Fremdowner 404, zweiter Commit derselben Lease wirkungslos. Die UI liest
  auch nach Reload 9/9. Neue V4-Runs erhalten keinen kuenstlichen Altjob.
- J04: der originale Saved-Bookmark-Adapter erzeugt das Pending-Result und der
  Share-Dialog publiziert ueber echtes POST. Followformular, abgefangene Mail,
  Double-Opt-in, native Watchanlage, Claim, echte Pipeline mit externem
  Modellmock und nativer Versionscommit. Eine unterscheidbare neue Antwort
  erscheint nur in ihrer Version, die Baseline bleibt unveraendert; fremde
  Shareloeschung wird abgewiesen.
- J05: nativer Memory-CAS, laufende Synthese, echte Kontoloeschung mit Tombstone,
  spaeter Providerabschluss, Wechsel auf zweiten Owner und Reload seines
  Kontrollbookmarks. Kein wiederbelebtes Konto/Unterdokument, alte Identitaet
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

Validierung vor Integration des zusaetzlich gefundenen GeneratorExit-Backendfixes:
J01/J02/J03/J05/Speicherfehler gemeinsam bestanden; J04 nach Praezisierung des
Originalansicht-Selektors einzeln bestanden (40,54 s). Zehn direkt betroffene
Bookmark-DOMfaelle und `npm run build:check` bestanden. Der integrierte Abschlusslauf
aller sechs Reisen wird nach dem Merge des Backendfixes dokumentiert.

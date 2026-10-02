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
- WP-03/WP-38 Browser: Ausgangslauf und Fehleranalyse laufen noch; Ergebnis wird hier ergaenzt.

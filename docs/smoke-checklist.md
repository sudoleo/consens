# Smoke-Checkliste — Frontend (index.html Refactor)

**Aktueller automatisierter Laufstand 02.10.2026:** siehe
[Testübersicht](test-coverage-map.md) und [rote Fälle](test-coverage/findings.md).
219 Browserfälle bestanden, 30 scheiterten, vier endeten im Setup, 55 wurden
nicht ausgeführt. Die unten genannten älteren Baselines/abgehakten manuellen
Prüfungen bleiben historisch und sind keine Freigabe des aktuellen Stands.

## Neue Funktionsgruppen und Restprüfung

- [ ] Sidebar-Breite (2026-10-08, Desktop ≥1100px): rechte Sidebar-Kante
      greifen (Cursor wird zum Doppelpfeil, dünne Linie erscheint) und ziehen →
      Sidebar, Zahnrad-Fußzeile und Toggle folgen, die Lesespalte bleibt mittig;
      neu laden → gleiche Breite ohne Springen; Doppelklick → zurück auf
      Standard; mit Tab auf den Griff und Pfeiltasten. Im schmalen Fenster und
      bei eingeklappter Sidebar kein Griff. Automatisiert:
      `sidebar-resize.test.mjs`, `tests/e2e/test_sidebar_resize.py`.
- [ ] Google als Quelle (Standard: nur lesen): echte OAuth-Rückkehr mit nur
      Lese-Scopes, Widerruf, Zustimmung **einmal pro Chat** (Folgefrage ohne
      Checkbox, Info-Chip „Private chat · Google data“), keine Schreib-Zeilen im
      Dialog „Gmail & Calendar“; die Offline-Browserfälle ersetzen keinen echten
      Providerlauf. Nur mit `GOOGLE_WRITES_ENABLED=1`: exakte Vorschau vor
      Senden/Terminspeichern.
- [ ] Google Drive: (+) → „Add from Google Drive“ nur im Agent-Modus; echter
      Picker (Google-Konto wählen, Doc/Sheet/Slide/PDF), Chip „Google Drive“,
      Zustimmung vor dem Senden, Datei am gesendeten Turn; Wechsel nach
      Compare/Consensus entfernt den Drive-Anhang mit Hinweis.
- [ ] Private Dateien/Dokumente: gespeicherte Version am richtigen Turn,
      Download und bestätigtes Entfernen, lesbare Warnung für Teilinhalt;
      erzeugte DOCX/PDF-Seiten zusätzlich visuell prüfen.
- [ ] Gemeinsames Tokenkonto: Moduswechsel, Holds, geschätzter Verbrauch,
      Kontowechsel und UTC-Reset gegen dieselbe Kontoanzeige prüfen.
- [ ] Watch/Topic: stehende Antwort bei dünner Evidenz, neue Belege, Recheck,
      erreichtes Ziel und erneutes Öffnen mit anderem Ziel; Zustellfehler und
      Unsubscribe in einer kontrollierten Testumgebung prüfen.
- [ ] Aktuelle Browserabweichungen bei Scrollabschluss, Quellenpillenstatus,
      Agent-Stop/Reasoning und Runwechsel anhand des Laufberichts nachstellen.
- [ ] Ruhe beim Laden (2026-10-03): eingeloggt neu laden — die Chat-Skelette
      blenden in die Einträge über, nichts springt. `/app?demo=1`: die Frage
      wird im zentrierten Feld getippt, beim Absenden gleitet das Feld nach
      unten (kein Sprung aus dem Bild, keine seitliche Verschiebung der Spalte
      beim Agent-Start). Die Widerspruchsmarken laufen bis zur letzten durch.
- [ ] Bookmark-Titel: Nach der ersten Antwort eines neuen Chats wechselt der
      Sidebar-Name kurz darauf weich von der Frage auf einen 2–6-Wörter-Titel
      und bleibt bei Follow-ups und nach Reload stehen.
- [ ] Agent-Memory (2026-10-04, echter Provider): Settings → Memory → „Let
      Agent update memory“ an. Im Agent „Ich bin Vegetarierin, merk dir das“ →
      kurze Bestätigung ohne Modellvergleich, darunter „Memory updated · Saved: …“.
      Danach eine normale Frage mit einer neuen Tatsache („Ich bin nach München
      gezogen, welcher Radladen…?“) → Vergleich läuft wie gewohnt, Memory
      aktualisiert die alte Wohnort-Erinnerung statt eine zweite anzulegen.
      Undo unter der Antwort und Settings-Liste (Bearbeiten/Löschen) prüfen.
      Schalter aus → „merk dir …“ wird nur mit Hinweis auf den Schalter
      beantwortet, nichts gespeichert. Im Usage-Panel der zweiten Nachricht
      eines Claude-Chats sollten `cached_input_tokens` > 0 sein.
- [ ] Gepufferter Agent-Stream (2026-10-08, Prod, Firmennetz bzw. puffernder
      Proxy/Virenscanner): Agent-Frage mit Reasoning senden. Nach etwa 5 s
      erscheinen Reasoning-Auszüge, Aktivität und Text live (DevTools → Network:
      `GET /agent/chats/…/live` alle ~1,5 s, `known: true`), die fertige Antwort
      steht genau einmal da, ohne Minuten-Warten auf das Stream-Ende. Im
      Heimnetz kommt kein einziger `/live`-Aufruf. Umami: `app_stream_buffered`
      nur im Firmennetz. Automatisiert: `agent-live.test.mjs`,
      `test_agent_live.py`, `test_agent_chat_frontend.py::test_buffering_proxy_*`.
- [ ] Lauf ohne Verbindung (2026-10-08, Prod, am besten am Handy): Agent-Frage
      mit Vergleich senden, sobald „Thinking…“ steht 1) WLAN/Mobilfunk für
      ~20 s aus → Aktivität zeigt „Reconnecting…“, nach dem Einschalten läuft
      der Fortschritt weiter und die Antwort kommt genau einmal; 2) App
      wechseln oder Bildschirm sperren, nach 1–2 min zurück → Fortschritt bzw.
      fertige Antwort ohne Fehler; 3) Seite neu laden → der Lauf erscheint
      wieder mit Fortschritt und endet mit der Antwort, kein zweiter
      Modellaufruf (Admin-Usage); 4) Tab schließen, später öffnen → Antwort im
      Verlauf. Stop-Knopf während eines Laufs → Aktivität „Response stopped“,
      Network zeigt `POST …/requests/…/stop`. Automatisiert:
      `test_agent_background.py`, `agent-live.test.mjs`,
      `agent-chat.test.mjs` („agent turns that outlive their connection“).
- [ ] Eingefügten Text prüfen (2026-10-09, echter Provider): neuer Agent-Chat
      zeigt „Ask anything, or paste an AI answer to check it“ (Handy: „Ask, or
      paste an AI answer to check“). Eine ChatGPT-Antwort mit einem bekannten
      Fehler einfügen, „Stimmt das?“ davor → die eigene Nachricht bleibt, wie
      sie abgeschickt wurde (kein Umbau, keine Marken). Über der Antwort zuerst
      „YOUR TEXT · Checking …“, dann die Zähler (Farbe nur auf den Zahlen) und
      auf einer Schiene nur die widersprochenen/geteilten Sätze, dazwischen
      Faltzeilen wie „17 sentences hold“; „Show full text“ zeigt alle Sätze
      (standardmäßig nur rot/gelb gefärbt, die übrigen klickbar und beim Hover
      nur grau, nie grün). Ein Zähler/Satz öffnet die Karte, „View answer“ die
      Modellantwort. Die Antwort nennt den Fehler und trägt selbst keine Marken
      und keinen Score. Aktivität: Vergleichsfrage enthält den Text nicht; im
      Agent-Panel genau eine Prüfzeile „Text check“, kein zweiter Antwort-Check
      nach dem Schreiben.
      Gegenprobe „Fasse diesen Text zusammen: …“ → keine Karte.
      Automatisiert: `test_agent_passage_check.py`, `passage-check.test.mjs`,
      `test_passage_check_frontend.py`.

Teilweise automatisiert: die Playwright-Suite `tests/e2e/` deckt Konsolen-
Fehler beim Laden, Send→Streaming, Consensus→Differences+Agreement-Score,
Modell-Ausschluss, Theme-Toggle, Picker-Persistenz und die Phase-4-Auth-/View-
Races ab (Lauf: siehe
`tests/e2e/README.md`). Die übrigen Punkte weiterhin manuell durchgehen
(oder zumindest die vom Cluster betroffenen), bevor committet wird. Backend
bleibt durch `venv/Scripts/python -m pytest tests/` abgesichert
(Baseline 2026-08-11 nach Phase 6: regulär 1076 passed; Phase-4-Browser-Races 8 passed;
Emulator-E2E zuletzt 2026-08-09 mit 39 passed. Sichere Befehle:
`docs/testing.md`).

## Browser-Konsole
- [ ] Beim Laden **keine** JS-Fehler in der Konsole (besonders: keine
      `ReferenceError: X is not defined`, keine `window.X is not a function`).
- [ ] `/app`, `/app/watches`, `/admin` und `/admin/benchmark` laden unter der strikten Script-CSP
      ohne `unsafe-inline`-Violation. Login-/Skeleton-First-Paint, Senden,
      Bookmark-Auswahl, Provider-Exclude, Settings und API-Key-Test reagieren
      über die externen Bootstrap-/Eventmodule weiterhin genau einmal.
- [ ] Ein absichtlich ausgelöster ungefangener Testfehler erzeugt genau einen
      same-origin `POST /api/client-errors`; ein bewusster Stop des laufenden
      Runs erzeugt keinen Fehlerreport.

## Öffentliche Seiten
- [ ] Demo-Einstieg auf `/` und `/app`: gleiches Play-Symbol, Theme-Kontrast,
      abgerundete Form und sichtbarer Tastaturfokus. „Try the demo“ wird in der
      App bis 640 px zu „Demo“; bei 320/390 px bleiben Demo und Senden innerhalb
      des Composers. Touch-Ziele sind mindestens 44 px hoch. Klick/Enter startet
      den bestehenden Demo-Ablauf, ohne dass der Einstieg doppelt auslöst.
- [ ] `/`, `/about`, `/ai-model-comparison`, `/consensus-engine`, `/benchmark`,
      `/privacy`, `/terms`, `/imprint` und öffentliche Share-/Unavailable-Seiten
      verwenden dieselbe Navigation, denselben Footer und die an `/app`
      angelehnten Tokens. Light/Dark folgen der gespeicherten App-Einstellung
      bzw. ohne Einstellung dem System-Theme.
- [ ] Desktop und Mobile haben keinen horizontalen Overflow; Focus States sind
      auf Links, Buttons und Formularfeldern klar sichtbar. Landingpage und
      Consensus-Engine-Seite zeigen dieselbe aktuelle Consensus-/Differences-
      Darstellung. Der Landingpage-Walkthrough verwendet die aktuellen
      Modellnamen, nennt Detail-/Widerspruchsmarker „fine rule“ bzw. „heavier
      amber rule“ und hält Einzelantworten im Agent Mode standardmäßig verborgen.
- [ ] Agreement-Verdict, Claim-/Difference-Marker und Focus-Wash sind in App,
      Landing und Consensus-Engine-Mockup visuell identisch; Änderungen kommen
      aus `components-consensus-visuals.css`, ohne Drift einer Landing-Kopie.

## Admin
- [ ] Reasoning budget: Sparprofil wählen, Vorschau für Antworten/Reasoning an/
      Consensus/Hilfsaufrufe wechseln, Modell-Ausnahme setzen und entfernen.
      Geschützte Modelle einblenden; reine Vorschau markiert nichts als geändert.
      Save und Reload erhalten die Policy; Reload vor Save verwirft Änderungen.
      Mistral zeigt im Sparprofil `none`, Kimi K3 bleibt aktiviert, Muse bleibt `low`.
- [ ] `/admin` authentifiziert, wechselt alle Tabs und lädt/speichert Models,
      Limits, API, Shares, Watches, Topics und SEO mit dem externen
      `admin.js`/`admin-api.js`; Formular-Submit lädt die Seite nicht neu.
- [ ] Light-/Dark-unabhängiges Admin-Layout hat nach der Auslagerung nach
      `admin.css` keine fehlenden Abstände, abgeschnittenen Tabellen oder
      ungestylten Dialoge. Die Browser-Konsole meldet keine Modul-/CSP-Fehler.
- [ ] `/admin#seo` (SEO-Puls): Schalter speichert und überlebt Reload, die
      Zeitplanzeile nennt den nächsten Montag 09:00 bzw. „paused“. „Run now“
      füllt Wochenzahlen, 12-Wochen-Balken und „What moved“ und schickt die
      Telegram-Notiz; ohne GSC-Credentials erscheint das Fehlerbanner statt
      leerer Zahlen.
- [ ] „Keep indexed“ unter „Set to noindex by the pulse“ entfernt die Zeile, die
      Share-Seite liefert wieder `index, follow`. API-Tab „Former Publisher
      pages“: „Pause watch“/„Resume watch“ und „Pause all watches“ ändern den
      Status sichtbar.

## Kern-Flow
- [x] Keine Verschiebung (09.10.2026): Senden bringt die neue Frage einmal nach
      oben (Agent und Consensus, Erst- und Folgefrage); Streamen, Markierungen,
      Quellen-Pills, Evidenzzeile und Laufende bewegen kein sichtbares Wort und
      scrollen nicht (Wortpositionen pro Frame gemessen, 1400/390px). Gast-
      Reload 1400/375px ohne Layout-Shift-Eintrag. Offen für Handtest:
      angemeldeter Reload mit eingeklappter Sidebar und Agent als letztem Modus.
- [x] Consensus-Scroll (18.09.2026): Einmaliger Sprung beim Absenden und bei
      „Latest message“, kein automatisches Mitlaufen mit Consensus-Deltas.
      Schnelle Ausgabe, weitere Deltas nach dem Klick, Abschluss und Reduced
      Motion bei 1280/390/320px im Browser geprüft; Agent-Following weiterhin
      erfolgreich. Neuer Button in Hell/Dunkel visuell kontrolliert.
- [x] Lesebreite (18.09.2026): 768px-Standardspalte und Zentrierung rechts der
      Desktop-Sidebar in 28 Browserzuständen bei 320–1907px geprüft, jeweils
      Startansicht und Gespräch sowie Desktop-Sidebar offen/geschlossen.
      Composer und Inhalt bleiben bündig, ohne horizontalen Overflow;
      Desktop-/Mobil-Screenshots in Hell und Dunkel visuell kontrolliert.
- [x] Delegation (16.09.2026): zwei parallele Worker, Rückfrage/Antwort und
      Nacharbeit derselben Sitzung im Integrationstest; getrennte Kosten pro
      Agent und Run, atomare Firestore-Reservierung und Deduplizierung geprüft.
      Agenten-Seitenleiste bei 1440/390/320 px in Hell/Dunkel mit echten Browser-
      Renderern geprüft: Nachrichten, gespeicherte Ansichten, Schließen/Escape,
      Kontowechsel und kein horizontaler Overflow. Live-Protokolle und begrenzter
      Qualitäts-/Kostenvergleich siehe `agent-delegation.md`.
- [ ] Agent Beta: als Pro und Admin auswählen, Text senden, Folgefrage und
      gespeicherten Chat öffnen; eingebettete Vergleiche und Prüfungen bleiben
      dem jeweiligen Turn zugeordnet. Free/Plus
      erhalten keinen Zugang. Moduswechsel erfordert einen neuen Chat.
      Abbruch/Recover erzeugt keinen Doppelaufruf; Kosten im Admin-Lookup
      inklusive unbekannter/offener Messungen prüfen. Automatisiert durch
      `test_agent_runs.py`, `agent-chat.test.mjs` und
      `test_agent_chat_frontend.py` (Browser-APIs gemockt).
      Agent zeigt in `.composer-models` genau EINEN Chip („<Chatmodell>
      +6“: Chatmodell + Zahl der Vergleichsmodelle, nie der Modusname); sein
      Menü öffnet mit „Agent“ (Modell, Reasoning) und „Compare with“
      (Presets/Custom, 2–6 Modelle). Agent-Modell darin per Maus/Tastatur
      (Rechts hinein, Links zurück) wechseln,
      nur unterstützte Reasoning-Stufen wählen; Chatmodell während eines
      Laufs gesperrt, Vergleichsmodelle bleiben änderbar. (+) „Reasoning“ und
      „Comparison models“ öffnen die jeweilige Ebene desselben Menüs; in
      Consensus/Compare bleibt der eigene Modell-Chip. Reasoning getrennt vom Antworttext auf-/zuklappen,
      während des Denkens stoppen. Folgefrage mit anderem Modell senden und
      nach Bookmark-Restore Modell, Denkstufe, Aktivität und Usage prüfen.
      Mobil zuerst den eingeklappten Composer antippen; Picker bei 320/390 px
      und in Light/Dark vollständig im Viewport halten.
      Alle drei Picker per Klick, Pfeiltasten, Home/End und Escape bedienen;
      Auswahl gibt den Fokus zurück. Lange Modellnamen und eine scrollende
      Modellliste bei 320×568 prüfen. Live-Reasoning: Lichtlauf wie beim
      Quellencheck, ein Scrollbereich, Zurückscrollen bleibt erhalten; nach
      Abschluss automatisch zu, manuelle Wahl beibehalten. Reduced Motion
      deaktiviert den Lichtlauf. Katalogfehler mit Reload, entfernte Modellwahl,
      fehlendes Reasoning/Usage, Output-Limit und Fehler nach Streamstart prüfen.
      Quellen im Fließtext als Pillen (Favicon + Domain, auf der Grundlinie)
      anzeigen, inklusive benannter Markdown-Links und „Paper (https://…)“;
      ein Linktext, der nur die Domain nennt, erscheint nicht doppelt,
      benachbarte Quellen bilden eine Pille „domain +N“, lange Domains enden
      mit Ellipse, ein fehlendes Favicon zeigt ein neutrales Monogramm (hell,
      dunkel, 390 px). Quellenvorschau per
      Hover/Fokus, passende nummerierte Quellenliste und gespeicherte/archivierte
      Antworten auch nach fehlgeschlagenem Run prüfen. Code/`[1]` bleiben Text.
      Automatisiert: `agent-citations.test.mjs`, `test_agent_comparison_frontend.py`.
      Agent-Seitenleiste während Vergleich/Judge öffnen: `Tokens pending`
      schimmert, empfangene Zeichen zählen als `chars` hoch, Provider-Messungen
      ersetzen sie durch Tokens. Nach Abschluss/Stop und im gespeicherten
      Verlauf endet die Animation; Reduced Motion/Forced Colors bleiben lesbar.
      Automatisiert: `test_agent_delegation_frontend.py`.
      Ein Modell, das beim Check noch schreibt: unter Answers mit Chip
      „Incomplete“, Begründungszeile und Teiltext; in der Leiste „Incomplete ·
      n s“ mit „Incomplete answer · not used“. Nicht in Antwort oder Check.
      Automatisiert: `test_agent_comparison.py`, `agent-review.test.mjs`,
      `model-answer-reader.test.mjs`, `agent-delegation.test.mjs`.
- [ ] Sources/Differences: kompakte Quellenlisten, kontrastreiche Titel und
      Aussagen, Check-details-Chevrons und kleiner Resolve-Button in Light/Dark
      bei 320/390 px sowie als Desktop-Sidebar. Disclosures per Enter bedienen;
      Touch-Ziele bleiben 44 px hoch, abgeschlossener Resolve blendet den Button
      aus. Source Checks stehen mobil mittig unter den Tabs; nach dem letzten
      Ergebnis bleiben 24 px Luft vor dem Composer. Automatisiert:
      `tests/e2e/test_inspector_polish.py`.
- [ ] Differences-Panel (Agent- und Consensus-Chat, Light/Dark, Desktop-Dock
      und 390 px): kein Untertitel, Frage als eine abgeschnittene Zeile ohne
      Label; im Agent-Chat eine Statuszeile `N of M models answered · Checked`,
      fehlende Modelle erst nach Aufklappen. Karten: Punkt + `Critical`/
      `Minor`/`Emphasis`, kritische zuerst, Titel in normalem Gewicht, keine
      Positionszahl; nur eine Karte gleichzeitig offen. Pro Position eine Zeile
      Icon + Modellname (Klick öffnet die Originalantwort), Zitat leiser.
      Inline-Marker und Source-check-Status öffnen weiterhin die richtige
      Karte. Automatisiert: `tests/e2e/test_agent_comparison_frontend.py`
      (`test_differences_reader_stays_calm_with_missing_models`).
- [ ] Landingpage-Szene 02 scrubbt einen Agent-Turn wie in /app (Uhr,
      Notizen, Modell-Icons 0→6, Writing/Checking, Marken, 45/100) ohne
      Höhensprung der Karte; Reduced Motion zeigt den fertigen Turn.
- [ ] Consensus-Run: Stepper-Kopf zeigt erledigte/aktive/offene Schritte, Preset
      und Uhr; schmal (320/390 px) eine Zeile mit vier Segmenten. Modellzeilen
      zeigen Icon, Balken und `Writing`/`Thinking`/`Waiting`, danach nur die
      Zeit bzw. `No answer`/`Skipped`/`Canceled`; ausgefallene Modelle sinken
      nach unten und der Hinweis darunter nennt sie einmal. Empfangene Zeichen
      stehen im Tooltip, Balken bleiben monoton, neue oder gewechselte Runs
      zeigen keine fremden Werte. Light/Dark passen; Reduced Motion bleibt
      statisch. Screenreader lesen nur Phasen-/Abschlusswechsel vor, Skip ist
      per Tastatur erreichbar. Automatisiert: `test_consensus_live_progress.py`
      (isolierte Browser-Komponente) und `run-progress-scope.test.mjs`.
      Neue Chunks zaehlen ruhig hoch, bleiben hoechstens beim empfangenen
      Wert und stoppen bei Abschluss/Ansichtswechsel. `Skip` veraendert beim
      Erscheinen keine Balkenbreite oder Zeilenhoehe; Touch-Ziele sind 44 px.
- [ ] Modellantwort-Sidebar mit sechs Antworten: 520–720 px Dockbreite ab
      1400 px, ruhige einzeilige Kopfzeile und 14-px-Lesetext. Chat und
      Composer bleiben neben der Sidebar sichtbar. Light/Dark, eingeklappte
      Navigation, Expand, Zweiervergleich und Fragewechsel prüfen; auf Touch
      bleiben Bedienelemente mindestens 44 px hoch, Schließen/Expand auch breit.
- [ ] Anhänge: PDF/Text/Bild im neuen Chat unter dem Feld in der Toolbar;
      Vorschau und Entfernen separat per Tastatur/Touch erreichbar. Lange Namen
      und zwei Dateien passen in Light/Dark bei 390 px. Nach dem Senden stehen
      Dateien an der Frage. Agent-Toolbar bleibt verborgen; neue Folgefrage-
      Dateien erscheinen stattdessen im Composer. Moduswechsel/„New comparison“,
      Fehler vor dem Senden und mobile Collapse-Zustände verlieren keine Dateien.
- [ ] Agent-Dateien/Dokumente bei 1440/390 px, Hell/Dunkel: Upload zeigt je Datei
      eine Fortschrittszeile, ein abgelehnter Upload bleibt mit Grund am Chip.
      Dokumentkarte (Titel, Version, DOCX/PDF) steht NACH der Antwort und nur bei
      der Turn, die sie erzeugt hat (auch bei archivierten Turns im Verlauf);
      frühere Versionen eingeklappt; keine chatweite Dateiliste unter der
      Antwort. Hochgeladene Dateien stehen als Chip an ihrer Nachricht; Klick
      öffnet die Vorschau (Bild, PDF, Text) mit „Download“ und „Remove from
      chat“ samt Bestätigung. Entfernen an Karten nur über ⋯ mit Bestätigung;
      Screenreader hört „Download <Datei>, version n“. Teils lesbare Dateien zeigen
      „Partly read“ an Chip und Antwort.
- [ ] Skeletons: Bei gedrosseltem Laden bleiben Chat-Platzhalter bis zur
      Metadatenantwort stehen; leere Liste, Fehler und Logout entfernen sie.
      Wartende Modellantworten zeigen Textzeilen bis zum ersten Token oder
      Abbruch/Fehler. Light/Dark, Mobile und Reduced Motion pruefen.
- [ ] Frischer `/app`-Load passt ohne vertikales Scrollen in den Desktop-
      Viewport; der Consensus-Picker hat keinen horizontalen Scrollbalken.
- [ ] Frischer `/app`-Load: keine Topbar; Brand + Collapse im Sidebar-Kopf,
      eingeloggter Account (Name/Plan + Avatar) und Settings im Sidebar-Footer.
      Ausgeloggt stehen Login/Sign-up nur oben rechts; die Sidebar zeigt kein
      zweites Login-Feld. Das Account-Popup hat in Light und Dark einen
      vollständig deckenden, gut lesbaren Hintergrund. Per Tastatur: Tab
      erreicht den Avatar, Enter öffnet mit Fokus auf „Shared links“, Pfeile
      wandern bis „Logout“, Escape schließt und fokussiert wieder den Avatar.
      Mit Agent Mode steht das Eingabefeld mit Begrüßung mittig und wechselt
      nach dem Senden in den geführten Thread. Ausschalten zeigt sofort das
      Vergleichsraster mit ausgewählten Modellen und ruhigen Platzhaltern;
      der Composer gleitet nach unten. Mobil einspaltig, alle Modelle oberhalb
      des fixierten Composers erreichbar. Light/Dark, Reduced Motion,
      Modellauswahl, gespeichertes Off und „New comparison“ prüfen. Anschalten
      erhält den Entwurf; vorhandene Antworten bleiben beim Umschalten stehen.
- [ ] Login-Dialog: Fokus wandert beim Öffnen hinein, Tab bleibt im Dialog,
      Escape/Backdrop/benannter Close-Button schließen ihn und geben den Fokus
      an den Auslöser zurück. Mit altem `id_token` und blockiertem Firebase-CDN
      verschwinden die Skeletons; Login/Sign-up bleiben sichtbar und erklären
      den temporären Auth-Ausfall statt tote Aktionen zu zeigen.
- [ ] Sidebar-Navigation: Models ist eine einzelne kompakte Zeile mit
      Providerzahl. Gäste sehen beim Klick „Please log in to configure your
      models.“; der Picker bleibt geschlossen und die mobile Sidebar offen.
      Eingeloggt öffnet die Zeile den Run-Picker am Composer; sie klappt keine
      Providerzeilen auf. Der Custom-Picker nutzt Checkboxen statt
      Toggle-Switches und bleibt in Light/Dark vollständig deckend und lesbar.
      Auch die Modell-Icons unter dem Input öffnen per Klick, Enter und
      Leertaste den Picker; Gäste sehen denselben Login-Hinweis. Nach einem
      Modellwechsel bleiben die neu gerenderten Icons anklickbar.
      Bei offener Desktop-Sidebar bleibt das Eingabefeld in der Viewport-Mitte;
      mobil verschwindet die schwebende Brand vollständig.
- [ ] Mobile Sidebar: Consensus/Watches erscheinen als kompakte Textnavigation
      mit beiden ausgeschriebenen Namen und Unterstreichung der aktiven Ansicht.
      Bei 320–1099 px, Light/Dark und Tastaturbedienung bleiben beide Ziele
      erreichbar; ein Ansichtswechsel schließt die Sidebar. Beim Vergrößern auf
      Desktop kehrt die Navigation als schwebender Switch zurück.
- [ ] Mobile Gast-Kopfleiste: Log in und Sign up öffnen den jeweiligen Auth-Dialog;
      New chat erscheint erst angemeldet. Beide Buttons wirken flach und bleiben
      auch bei 320 px neben den Aktionen einer fertigen Antwort ohne Überlappung
      bedienbar. Light/Dark, Login/Logout und Fokusrückgabe nach Schließen prüfen.
- [ ] Landing: Der Benchmark-Abschnitt steht vor `#watch` und trägt darunter
      den Live-Streifen „No model wins every time.“ (Top-5-Raten mit
      Fair-Share-Tick, Link auf `/model-pulse`); im Hero steht keine Pulse-Zeile
      mehr. `/model-pulse` zeigt Best-answer-Raten (Picks ÷ Läufe der Familie)
      mit Band und Fair-Share-Tick; Zeitraum/Runs/„Only runs with“/Sortierung
      wechseln ohne Reload, die URL folgt, ohne JS funktioniert das Formular.
      Mit „Only runs with“ ist die Rivalen-Zeile markiert und jede andere zeigt
      `vs <Rivale> W–L`. Familien unter 10 Läufen stehen nur in „Too few runs“.
      Light/Dark (Logos invertiert), 320–1440 px ohne horizontalen Überlauf;
      `/benchmark` verlinkt zurück auf den Model pulse.
- [ ] Settings: Memory, Model behavior, Runs, Display, Connections und Account
      bleiben bei 320/390/700/768/1440 px Breite und geringer Höhe erreichbar.
      Kein horizontaler Inhaltsüberlauf; Kopf und Schließen bleiben beim Scrollen
      sichtbar. Kurze Memory-Felder wechseln passend zur Inhaltsbreite zwischen
      einer und zwei Spalten. Light/Dark, Tastaturnavigation und mobile
      Eingabefokussierung prüfen; Schalter, API-Key-Feld und System Prompt
      funktionieren weiterhin. Account-Löschung nur im isolierten Testprofil.
- [ ] Settings → Display → Answer & source highlights: All / Contradictions /
      Disagreements & issues / Critical contradictions / None bei 320/390 px und Desktop prüfen. Graue Detail-
      widersprüche bleiben unter Contradictions sichtbar, graue Emphasis nicht.
      Wechsel gilt sofort und nach Reload auch für archivierte Antworten;
      Default ohne gespeicherte Wahl: Disagreements & issues. Ausgefilterte Passagen haben
      keine unsichtbaren Tabstopps/Hover-Aktionen; Text, Quellenlinks und
      vollständige Differences bleiben verfügbar. Quellenmarkierungen folgen
      demselben Filter, auch nach spät eintreffenden Prüfergebnissen.
- [ ] Antwort-Footer: Differences / Answers / Sources bei 320–1440 px und
      Full/Summary/Hidden gleichmäßig ausgerichtet, auch in gespeicherten Turns.
      Dezente Icons vor den Labels; bis 640 px Icon/Anzahl über dem Label,
      gleiche Spalten und mindestens 56 px hohe Touch-Flächen. Quellenhinweise
      (✓/!/?), zweistellige Anzahlen und leere/ausgeblendete Tabs verschieben
      keine Labels. Quellenstatus steht auf Desktop separat, auch bei
      Pending/Reconnecting/Unavailable oder langen Statusmeldungen; mobil
      bleibt der Hinweis neben der Sources-Anzahl. Ohne Quellen keine leere
      Statuszeile. Keine Legende/Hide-Aktion unter der Antwort.
      Share/Watch/Cite stehen auf Desktop neben der Hauptnavigation; mobil
      im Header als Icons mit zugänglichen Namen. Run again bleibt erreichbar, ohne sich mit
      Laufzeit oder Kosten zu überlagern; Cite-Menü sitzt am neuen Host.
- [ ] Source-check-Status anklicken: Bei v4 direkt zur Prüfbegründung in
      Differences, inklusive Gründen für ausgelassene/unverfügbare Prüfungen.
      Bei mehreren Karten wird zuerst eine nicht abgeschlossene Prüfung geöffnet;
      nur ihr Prüfbereich bekommt Fokus und eine nach 2,8 Sekunden ausblendende
      Markierung. Wiederholter Klick startet den Hinweis neu. Polling erhält die
      Restdauer, Run-Wechsel/Clear entfernt ihn. Legacy/ohne Einzelbefund führt
      zum markierten Sources-Bericht. Reduced Motion ohne Bewegung;
      Forced Colors mit sichtbarem Systemrahmen.
- [ ] Mobile Navigation bei 320–1099 px: Menü mit 44-px-Touchfläche in einer
      deckenden Kopfleiste; kein durchscheinender Antworttext. Inhaltsanfang
      bleibt unterhalb der Leiste, Menü/View-Switch/Gast-Login überlappen nicht.
      Abwärtsscrollen blendet die gesamte Leiste aus; Hochscrollen und
      Tastatur-Navigation holen sie zurück, auch im Watch-Dashboard. Sidebar
      öffnen/schließen und Fokus-Rückgabe funktionieren. Light/Dark, Reduced
      Motion und Desktop-Float-Navigation bleiben bedienbar.
- [ ] „Show agreement score“ ist standardmäßig aktiv. Ausschalten blendet die
      numerische Score-Anzeige im aktuellen Consensus und in archivierten Turns
      aus; die qualitative Einordnung/Widerspruchswarnung bleibt sichtbar. Nach
      Reload bleibt die Auswahl erhalten.
- [ ] EIN Moduswähler als erste Gruppe im (+)-Menü (Agent · Beta / Consensus /
      Compare, Haken am aktuellen) bei 1440/390/320 px, hell und dunkel: kein
      Moduschip mehr in der Composer-Zeile; jede Option mit einer Zeile
      Erklärung, Compare und Consensus für alle Stufen, Agent nur mit
      Agent-Zugang. Settings → Runs → Mode zeigt dieselbe Wahl und bleibt
      synchron; die Wahl übersteht ein Neuladen und folgt in einem zweiten Tab.
      Kein Agent-Mode-Schalter mehr im (+)-Menü, in Settings oder unter dem
      Input. In einem offenen Consensus-Chat ist Agent deaktiviert („Available
      in a new chat“); in einem Agent-Chat verschwindet die Modusgruppe aus dem
      (+), „New chat“ bringt sie zurück. Der Composer ist in allen drei Modi
      derselbe: (+) links (auf dem Startbildschirm unter dem Feld, im
      Desktop-Chat vor dem Feld), Modelle und Senden rechts; auch der Compare-Start mit den
      leeren Antwortkarten zeigt ihn so, samt Werkzeugleiste. Der Modell-Chip
      sagt nur, wer antwortet („6 models“), nie „Compare“. Direkt nach dem Laden mit gespeicherter Agent-Wahl
      sendet nichts als Consensus, solange der Agent-Zugang noch lädt.
- [ ] Frage eingeben + senden → alle ausgewählten Modelle streamen Antworten.
- [ ] Bei null oder einem ausgewählten Modell ist Senden deaktiviert; Sidebar-
      Zähler und Custom-Picker nennen „choose at least 2“. Ab zwei Modellen startet
      der Lauf; nur Consensus endet in Consensus + Differences, Compare
      endet nach den Modellantworten. Mit Anhang und genau
      OpenAI + stale DeepSeek wird nach dem Attachment-Filter erneut geprüft:
      kein Usage-Run, kein `/prepare`, kein Ein-Modell-Fan-out.
- [ ] Antworten alle ausgewählten `/ask_*` mit HTTP-/Netzfehler, endet der Lauf
      sichtbar und in Analytics als Fehler; kein Consensus startet. Nach dem
      ersten echten Lauf bleiben die in Settings gewählten Markierungsfilter
      aktiv; Antworttext und Quellenlinks bleiben bei „No highlights“ lesbar.
- [ ] In Compare bleibt die Oberfläche im direkten Vergleich: Frage und
      Antwortleser, kein Pipeline-Block und kein `/consensus`-Request. Alle
      Modellantworten und Status sind gleichzeitig sichtbar: zwei offene Spalten,
      mobil untereinander, ohne aeusseren Rahmen und Copy-Schaltflaechen.
      Vor dem Start gibt es keine leeren Modellboxen. Warten wird nur im
      Modellkopf gezeigt; Fehlermeldungen bleiben sichtbar. Frage, Seitenmasse
      und Composer entsprechen dem normalen Chat (auch Sidebar auf/zu).
      Der Picker bleibt beim Oeffnen und Resize vollstaendig im Viewport. Streaming eines Modells erhaelt
      Textauswahl und geoeffnete Quellen in unveraenderten Nachbarantworten. Consensus, Differences und Claims bleiben
      leer/verborgen. Das gilt in Light/Dark und mobil ohne horizontalen Overflow.
- [ ] Agent-Mode-Modellantwort-Leser bei 390/768/1024/1440px: mobil/tablet modal mit
      Rueckweg, Escape/Fokus-Rueckgabe, Desktop angedockt. Zwei Antworten nur ab
      760px Leserbreite nebeneinander, sonst A/B-Umschaltung. Lange Namen,
      Fragen, Code, Tabellen und Quellen bleiben lesbar. Scrollposition bleibt
      bei Streams und beim Wechsel zurueck zu einem Modell erhalten.
- [ ] Frage 1 im Leser oeffnen, waehrend Frage 2 streamt: Modelltext und Quellen
      bleiben bei Frage 1. Archivierte Claim-Spruenge oeffnen deren Modell im
      gemeinsamen Leser. Run-/Bookmark-Wechsel und Logout zeigen keine alten
      Reader-Inhalte. Keine gestapelten Vollantworten im Chat-Verlauf.
- [ ] Mit Agent Mode erscheint die kompakte Pipeline: Zähler folgt den fertigen
      Modellantworten, danach wird „Consensus & differences“ ohne falsche
      Prozent-/Zeitprognose aktiv; Abschluss, Fehler und Stop blenden die Zeile
      wieder aus.
- [ ] Senden während Lauf abbrechen (Stop) funktioniert.
- [ ] Modell per Checkbox ein-/ausschließen blendet die Antwortbox korrekt ein/aus.
- [ ] Der Custom-Picker listet alle neun Familien (inkl. Kimi, GLM und Muse); sind
      sechs gewaehlt, ist die siebte sichtbar gesperrt. Eine Familie abwaehlen
      gibt die gesperrten wieder frei, und jede Handauswahl schaltet die
      Kopfzeile von Daily/Balanced/High Quality auf die Custom-Anzeige um.
- [ ] Echter Bild-/PDF-Anhang pausiert DeepSeek mit sichtbarer Erklärung; nach
      Entfernen aller Anhänge wird die vorherige DeepSeek-Auswahl wiederhergestellt.
- [ ] Die Anhang-Sperre haengt am gewaehlten MODELL, nicht an der Familie:
      GLM 5.3 Flash bleibt mit Anhang waehlbar, GLM 5.3 wird pausiert; der
      Reasoning-Schalter aendert daran nichts (er tauscht kein Modell). Kimi
      bleibt in beiden Faellen waehlbar.
- [ ] Muse liefert eine echte Antwort: Muse Glimmer 30B als Free-Modell und
      Muse Spark 1.3 als Pro-Modell. Spark braucht dafuer die einmalige
      18+-Bestaetigung des OpenRouter-Kontos
      (https://openrouter.ai/settings/preferences); fehlt sie, meldet der Lauf
      fuer Muse einen Fehler, waehrend die uebrigen Familien normal antworten.
- [ ] Quellen-Chips / Evidence-Links erscheinen und sind klickbar.
- [ ] „Ask about this“ auf einem markierten Abschnitt einer Antwort: das Zitat
      steht über dem Eingabefeld, der Fokus liegt im Feld, das × entfernt es
      wieder. Abgeschickt beginnt die Frage im Thread-Kopf, im Seitentitel und
      im Bookmark-Namen mit dem GETIPPTEN Text, das Zitat folgt darunter — die
      Zitatfläche ist danach leer. Ein am Kontingent gescheiterter Lauf gibt
      Entwurf und Zitat unverändert zurück. Light/Dark und mobil prüfen
      (eingeklappter Composer zeigt das Zitat nicht, klappt aber nicht von
      selbst zu, solange es steht).
- [ ] Zitat- und Anhang-Leiste sehen aus wie eine Familie: gleiche Kachel auf
      `--ground`, gleiche Ecken, gleicher neutraler ×-Knopf, alles linksbündig
      und exakt bündig mit dem Eingabefeld darunter (Light/Dark, 375 px). Die
      Dateityp-Plakette ist monochrom; die DeepSeek-Notiz trägt als einzige
      Fläche Farbe (Ampel-Gelb) und läuft nicht über den Rand hinaus.

## User Memory
- [ ] Einstellungen → Memory zeigt vier kurze „About you“-Felder und darunter
      „Saved memories“ als große, vertikal vergrößerbare Textarea mit sichtbarem,
      serverseitig geliefertem Free-/Pro-Zeichenlimit.
- [ ] Eine mehrabsätzige Erinnerungszusammenfassung einfügen, speichern,
      Einstellungen schließen/neu öffnen: Absatz- und Listenstruktur bleiben
      erhalten; nach Neuladen und auf einem zweiten Gerät erscheint derselbe
      Kontostand.
- [ ] Eine Aussage in Frage, Consensus und einer Modellantwort markieren: jeweils
      erscheint das kompakte Menü „Ask about this | Remember | Correct memory“
      (über der eigenen Frage nur die beiden Memory-Aktionen, ausgeloggt nur
      „Ask about this“). „Remember“ öffnet
      den vorausgefüllten Dialog: ohne verwandten Eintrag wird genau einmal
      angehängt; bei einem eindeutigen Widerspruch wird nur die kleinste passende
      Passage aktualisiert und ein nicht widersprochenes Detail darin bleibt erhalten.
      „Correct memory“ ändert ohne zweite Bestätigung genau den passenden Eintrag.
      Beide Ergebnisse zeigen den app-nativen Status-Toast mit „Undo“.
- [ ] Memory-Aktionsmenü, Dialog, Fokusführung, Escape/Backdrop-Schließen und
      Undo-Toast in hellem/dunklem Theme sowie auf schmalem Viewport prüfen.
- [ ] Undo innerhalb des sichtbaren Zeitfensters stellt den vorherigen Inhalt
      exakt wieder her; nach einer zwischenzeitlichen manuellen Memory-Änderung
      wird Undo verständlich und ohne Überschreiben abgewiesen.
- [ ] Mit aktivierter Memory enthält jeder ausgewählte `/ask_*`-Request den
      gespeicherten Text; der Schalter pausiert Kurzprofil und Notiz gemeinsam,
      ohne den Text zu löschen. Watch-Reruns verwenden beides weiterhin nicht.
- [ ] „Clear all“ leert alle fünf Felder erst als Entwurf; dauerhaft gelöscht
      wird erst nach „Save memory“.

## Multi-Turn Chat
- [ ] Frische Frage sendet nach `/prepare` zunächst ohne Chat-Bindung an
      `/ask_*`; Chat und pending Turn 1 entstehen genau einmal erst bei der
      automatischen oder manuellen Consensus-Anforderung. Ohne Consensus-
      Anforderung entsteht kein Turn-1-Orphan. Turn 1 sendet kein Legacy-
      `context` und keine `context_version_id` an `/ask_*`.
- [ ] Nach einem completed Turn bleibt das Eingabefeld offen und trägt keine
      Follow-up-Meldung: die nächste Frage geht ohne Zwischenschritt als
      Turn 2, Turn 3 und weiter im selben Chat raus; die aktive Chat-Zuordnung
      bleibt nach jedem completed Turn erhalten. Der einzige Ausstieg ist
      „New comparison“ in der Sidebar.
- [ ] Eine aktive Fortsetzung baut vor dem Provider-Fan-out genau einmal
      `/chats/{chat}/turns/{turn}/context`; alle `/ask_*` und `/consensus`
      erhalten exakt dieselben `chat_id`, `turn_id`, `context_version_id` und
      niemals parallel den Legacy-`context`.
- [ ] Developer-Modus verwendet beim Context-Build denselben von `/prepare`
      konsumierten `usage_run_key`. Own-Key sendet ausschließlich den Key des
      gemeinsame OpenRouter-Key als `openrouter_key`; im
      Netzwerk-Payload stehen keine weiteren Nutzer-Keys und kein Developer-
      Fallback.
- [ ] Fehlt im Own-Key-Modus ein Key eines ausgewählten Antwort-Providers oder
      des Memory-Providers, stoppt der Lauf vor Usage, `/prepare`, Turn-Anlage
      und Fan-out; Frage und completed Vorgänger bleiben stehen.
- [ ] Ein kurzzeitiges `202 building` wird begrenzt wiederholt; eine
      `degraded`-Version startet den normalen Fan-out. Context-Fehler oder Stop
      lassen den completed Vorgänger sichtbar und beschädigen ihn nicht.
- [ ] Nach einem mehrdeutigen Abbruch bleiben pending Turn-ID und
      `client_request_id` beim Retry stabil. Ein serverseitig bereits
      completed Turn wird ohne neue Provider-/Consensus-/Differences-Aufrufe
      sowie ohne Bookmark-, Vote-, Completion-Analytics- oder Watch-Nudge-
      Schreibvorgang wiedergegeben — auch wenn Modell, Tarif oder Keybestand
      inzwischen geändert wurden. `failed` startet keine Fortsetzung hinter
      diesem Turn.
- [ ] Liefert eine aktive Fortsetzung weniger als zwei Modellantworten, sendet
      der Browser genau eine Dispositionsanfrage: der pending Turn wird ohne
      aktuelle Modell-/Tierprüfung, Engine-/Credential-Aufruf und ohne neue Usage-Einheit als
      `insufficient_answers` failed markiert.
- [ ] Frühere Turns bleiben vollständig sichtbar. Consensus, Agreement,
      Differences, Sources und Modellantworten gehören jeweils zum richtigen
      Turn; `[S…]`-Links eines alten Turns öffnen nicht die Quellen des neuen.
- [ ] Turn 3 und weitere Turns hängen jeweils unterhalb des vollständigen
      bisherigen Verlaufs an; kein neuer Turn ersetzt Turn 2 oder einen anderen
      bereits gerenderten Vorgänger.
- [ ] Ein altes Bookmark ohne `chat_id` bleibt im Legacy-One-Hop-Pfad. Ein
      Chat-Bookmark lädt dagegen alle completed Turns paginiert und stellt
      ausschließlich seine letzte completed Chat-/Turn-Basis für ein weiteres
      Follow-up wieder her. Bei einem absichtlichen Transcript-Fehler bleibt
      die gespeicherte Chat-Bindung fortsetzbar und die reduzierte Anzeige wird
      erklärt; ohne nutzbaren Frage-/Consensus-Kontext nennt das Input-Feld den
      nächsten Lauf ausdrücklich einen neuen Vergleich. Clear und Logout leeren aktive, pending, Context-
      und Bookmark-Zuordnung vollständig.
- [ ] Eine Premium-Consensus-Engine bleibt für ein Free-Konto gesperrt, auch
      mit aktivem Own-Key-Schalter: 403, kein Engine-Call, kein Turn-Write.
- [ ] Kontolöschung entfernt neben Bookmarks/Usage auch alle Chats inklusive
      Turns, Modellantworten und Context-Versionen — in der Firestore-Konsole
      darf unter `users/{uid}/chats` nichts zurückbleiben.
- [ ] Einen bereits authentifizierten Bookmark-/Chat-/Share-/Watch-Write während
      der Kontolöschung künstlich verzögern: Nach gesetztem Tombstone wird er
      abgewiesen und kein bereits quittierter Cleanup-Bereich neu angelegt. Ein
      vor der Löschung erzeugter Follow-Bestätigungslink ist danach ungültig.
- [ ] Bei absichtlich unterbrochenem Löschbereich antwortet `/delete_account`
      mit `202 cleanup_pending`; die UI behauptet nicht „deleted“, beendet aber
      die lokale Session. Nach Wiederherstellung räumt der Maintenance-Retry
      nur die offenen Bereiche auf und der Job wechselt zu `completed`.
- [ ] Ein Chat-Bookmark mit vielen Turns öffnet sich zügig: pro Seite genau ein
      Chat-Read und eine Query je Turn statt sechs Einzel-Gets pro Turn.
- [ ] Ein Follow-up-Lauf löst den Kontext genau einmal auf, nicht sechsmal:
      im Server-Log steht pro Turn ein Context-Resolve, nicht einer je `/ask_*`.
- [ ] Ein Chat-Bookmark löschen entfernt auch den Chat: unter
      `users/{uid}/chats/{chat}` bleibt nichts zurück. Ein Legacy-Bookmark ohne
      `chat_id` löscht weiterhin nur sich selbst.
- [ ] Nach einem mehrdeutigen Abbruch zeigt der Replay eines bereits completed
      Turns die **gespeicherten** Modellantworten in den Antwortboxen; Provider
      ohne gespeicherte Antwort sind leer und nicht mit der vorherigen Antwort
      gefüllt. Die Agreement-Zahl zählt die gespeicherten Modelle.
- [ ] Ein pending Turn, dessen Browser-Bindung durch Reload verloren ging, wird
      beim nächsten Turn im selben Chat als `abandoned` retired — completed und
      failed Turns bleiben unangetastet.
- [ ] Eine Frage mit geschütztem Leerzeichen (aus Word/PDF/Webseite kopiert)
      als **Follow-up** stellen: der Lauf geht durch. Vor dem NFKC-Fix liefen
      alle sechs `/ask_*` in 409 und der Lauf brach ohne Antwort ab.
- [ ] `CHAT_CURSOR_SECRET` ist in Render gesetzt (nicht nur der Fallback
      `WATCH_UNSUBSCRIBE_SECRET`): ein Chat mit mehr als 50 Turns lässt sich aus
      dem Bookmark vollständig nachladen, statt mit 503 abzubrechen.
- [ ] Free-Konto kann keinen Turn mit einer Premium-Engine anlegen (403
      `pro_required`) — dieselbe Grenze wie in `/consensus`.
- [ ] Limits greifen mit ehrlicher Meldung statt „Please retry": bei erreichtem
      Chat-Limit „…Delete one to start another.", bei erreichter Chat-Länge
      „…Start a new comparison to continue."

## Consensus (höchstes Risiko)
- [ ] Presets: Daily/Balanced setzen sichtbar alle sechs Antwortmodelle und die
      konfigurierte Consensus-Engine; eine manuelle Modellwahl wechselt zu Custom.
- [ ] High Quality zeigt ein Pro-Badge, hat beim Hover/Fokus eine dezente
      Power-Animation, oeffnet fuer Free den Kosten-Erklaerdialog (kein Kauf-,
      kein Zugangs-Request-Button) und setzt fuer Pro das vollstaendige
      Premium-Model-Set. Der Reasoning-Schalter bleibt davon unabhaengig.
- [ ] Consensus und Differences erscheinen oberhalb der Modellantworten; der
      Reveal scrollt nur dann sanft zum Ergebnis, wenn es außerhalb des
      relevanten Viewports liegt.
- [ ] Consensus manuell generieren → Antwort + Differences erscheinen.
- [ ] Beim Lesen eines Consensus verschwinden der fixierte
      Consensus/Watches-Schalter und der schwebende Burger nach deutlichem
      Herunterscrollen; Aufwärtsscrollen, Seitenanfang oder Tastatur-Navigation
      bringen beide ohne Flackern zurück. Dasselbe gilt im scrollenden
      Watch-Dashboard für den View-Schalter.
- [ ] Auto-Consensus folgt dem Modus: Consensus triggert ihn nach Abschluss;
      Compare sendet keinen `/consensus`-Request und blendet „Check
      contradictions“ in Leiste und (+)-Menü aus. Die Demo (`?demo=1`) zeigt
      in Consensus Konsens und Differences, in Compare nur die Antworten.
- [ ] Credibility-Frame-Farbe (cred-very … cred-not) wird gesetzt.
- [ ] Consensus-Insights: Claim-Badges, Difference-Karten, Klick öffnet Popover,
      „Jump to model answer" highlightet die Originalantwort.
- [ ] Verdict-Semantik: Score 85+/65+/40+/20+/<20 zeigt High/Strong/Partial/
      Low/Very low agreement; Grün beginnt erst bei 65. „No contradictions"
      bzw. disputed/critical/minor bleiben als getrennte Detailaussage sichtbar.
- [ ] Resolve-Runde: „Resolve with the models"-Button an Widerspruchs-Karten
      (nur Contradictions mit ≥2 beteiligten Modellen), Klick zeigt Outcome-Badge
      + Modell-Zeilen, Usage-Counter aktualisiert sich, Fehlerfall reaktiviert
      den Button.
- [ ] Share-Dialog: Link erstellen, Liste anzeigen, Link kopieren.
- [ ] Mobil Share in der Topbar öffnen: Der Dialog erscheint mittig im sichtbaren
      Bildschirm, auch nach dem Scrollen. Auf kleinen Bildschirmen bleiben Titel
      und Schließen sichtbar; lange Inhalte scrollen innerhalb des Dialogs.
- [ ] Während Share-/Bookmark-Requests Konto A → Logout → Konto B wechseln:
      späte A-Antworten ändern weder B-Sidebar/-Session noch das aktuelle Modal.
      Bei schnellem Bookmark-Klick A→B bleibt B sichtbar, auch wenn A zuletzt
      antwortet. Ein Bookmark-Listenfehler zeigt Fehler + Retry statt „leer“.
- [ ] Während ein Watch-Create noch auf das ID-Token wartet, den Dialog schließen
      oder zu Share wechseln: Es wird kein veralteter POST gesendet und keine
      verspätete Antwort überschreibt den zuletzt gewählten Modalinhalt.
- [ ] Tab über UTC-Mitternacht offen lassen: Countdown läuft bis 00:00 UTC und
      lädt den neuen `/usage`-Stand; ein vorheriges `0 / Limit` blockiert danach
      nicht weiter. Den ersten Refresh einmal fehlschlagen lassen: er wird erneut
      versucht und erst der bestätigte Serverstand markiert den neuen Tag. Ein transienter `/user_status`-Fehler wird durch ein
      erfolgreiches Pro-`/usage` inklusive Badge/Features geheilt.

## Consensus-Lauf (früher „Agent Mode“)
- [ ] Consensus/Compare wechseln, Timer läuft, Status-Text korrekt;
      in Compare bleiben sechs direkte Antworten sichtbar und der
      Consensus-/Differences-/Claims-Pfad unberührt.
- [ ] Nach der ersten fertigen Modellantwort erscheint dezent „Compare answers“
      (auch im eingeklappten Mobile-Panel); der Toggle zeigt/versteckt die
      einzelnen Antwortboxen, ohne Agent Mode auszuschalten, und startet bei
      einer neuen Frage wieder in der cleanen, verborgenen Ansicht.
- [ ] Mobile Consensus: Tipp auf eine unterstrichene Passage öffnet denselben
      Agreement-Dialog wie die Quote; Fokus bleibt im Dialog und kehrt zurück.
- [ ] Mobile Footer: Score, Aktionen und die drei Detail-Tabs bleiben kompakt,
      gleichmäßig ausgerichtet und erzeugen keinen horizontalen Scroll.
- [ ] Mobile Composer: Plus, Modell-Picker und Send-Pfeil liegen auf derselben
      horizontalen Achse; der Composer bleibt am unteren Viewport-Rand fixiert.
      Das Fragefeld wächst beim Tippen bis 180 px, scrollt danach intern und
      schrumpft beim Löschen wieder auf seine Ausgangshöhe. Enter auf der
      Handy-Tastatur fügt einen Absatz ein und sendet nicht.
      Am vollständigen Scrollende liegen die geschlossenen Detail-Tabs direkt
      darüber, ohne Leerraum oder verdeckten Inhalt.
- [ ] iPhone (echtes Safari, nicht emuliert): im Thread ins Feld tippen —
      der Composer sitzt direkt auf der Tastatur bzw. ihrer Formularleiste,
      ohne Thread-Streifen dazwischen und ohne Hinweissatz; Tastatur zu, sitzt
      er wieder am unteren Rand. Automatisiert nur mit nachgestelltem
      `visualViewport` (`test_mobile_navigation.py`).
- [ ] Landing auf dem Handy (375 px) bis ganz unten scrollen: die Seite
      verschiebt sich nie seitlich (`test_public_composer_mockups.py`).
- [ ] Quellen-Pillen im Consensus stehen hinter Punkt, Frage- oder
      Ausrufezeichen (Favicon-only-Pillen bleiben an ihrer Domain); dasselbe
      gilt für die Quellenverweise auf öffentlichen Share-Seiten.
      „Copy consensus“ liefert Domains in Klammern statt „uci.org+2“.
- [ ] „Run again“ kehrt zum normalen Composer zurück, übernimmt die vorige
      Frage, startet aber erst nach einem bewussten Klick auf Senden. Der Knopf
      beziffert vorher den ungefähren Preis („Run again · about 8% of today“,
      Tooltip mit Rest in Prozent); ohne bekanntes Konto entfällt der Zusatz. Nach dem Klick
      steht über dem Eingabefeld, dass Senden einen vollständigen neuen Lauf
      startet — der Hinweis verschwindet mit dem Absenden oder mit
      „New comparison“.

- [ ] Anhänge hängen an der Nachricht, nicht am Feld: nach dem Senden ist die
      Anhangleiste des Composers leer und die Chips stehen unter der gesendeten
      Frage (auch nach dem Archivieren im Verlauf und beim Bookmark-Restore).
      Eine Folgefrage schickt die Datei nicht erneut mit.
- [ ] Handy: nach dem Absenden und beim Scrollen nach unten schrumpft der
      Composer in jedem Modus auf eine Zeile ((+), Feld, Senden); Modus,
      Modelle und Fuß kommen beim Antippen oder Hochscrollen an ihrem Platz
      zurück. Anhänge und ein Zitat bleiben eingeklappt sichtbar. Desktop und
      Startbildschirm klappen nie ein.

## Consensus Watch
- [ ] Nach erfolgreichem Consensus erscheint „Watch“ neben Share; Aktivierung
      verlangt die explizite Wahl zwischen privater Eigentümer-Seite und öffentlicher,
      nicht indexierter Link-Seite und bietet Weekly/Monthly. Ein Klick auf „Start
      watching“ markiert fehlende Pflichtangaben direkt am jeweiligen Feld und scrollt
      zum ersten Fehler. Der Dialog bleibt auf iPhone-Größen vollständig im sichtbaren
      Bereich. Private Seiten sind in einem fremden oder ausgeloggten Browser nicht lesbar.
- [ ] „Schedule and alerts“ trägt rechts einen „Edit“-Schalter, die drei
      Werte-Chips öffnen selbst ihr Feld (Fokus liegt danach darin), und
      „Customize schedule and alerts“ steht direkt darunter — über den
      Zustellkanälen, nicht am Dialogende.
- [ ] Lokale Run-Uhrzeit ist bei Erstellung wählbar und zeigt die erkannte Zeitzone;
      Weekly bietet auch Free-Nutzern einen Wochentag-Picker und startet standardmäßig
      am morgigen Wochentag statt erst nach einer vollen Woche. „Watched“ erlaubt eine
      spätere Änderung von Tag und Uhrzeit. `next_run_at` entspricht dem gewählten
      lokalen Wochentag und der Uhrzeit (mit bis zu 30 Minuten Scheduler-Toleranz),
      auch über einen Sommer-/Winterzeitwechsel hinweg.
- [ ] Free: Daily ist als Pro markiert/gesperrt und das aktive Limit öffnet den
      bestehenden Pro-Teaser. Dashboard und Create-Dialog zeigen vorher den
      autoritativen Plan, „aktiv von Limit“ und freie Plätze; pausierte Watches
      sind ausdrücklich als nicht mitgezählt erklärt. Bei 1/1 (Free) bzw. 5/5
      (Pro) ist die Erstellung bereits vor dem Request gesperrt. Pro: Daily und
      bis zu fünf aktive Watches funktionieren.
- [ ] Das Watch-Dashboard ist eine eigene Seite `/app/watches`: erreichbar über
      den schwebenden View-Switch „Chat/Consensus | Watches“ (gleitender Thumb,
      beide Segmente mit Icon; Agent-Modus beschriftet das erste Segment „Chat“)
      und „Watched“ im Nutzericon-Menü; Browser-Back/Forward und Deep-Link/Reload
      auf `/app/watches` funktionieren (vor dem Login erscheint ein Hinweis statt
      Daten). Logout lässt URL und Hinweis stehen; ein später Login rendert ohne
      Reload das Dashboard. „Watched“ aus einem Share-Dialog schließt das Modal vor
      dem Ansichtswechsel. Ohne Watch zeigt die Seite „Tell us what you are waiting
      for.“, drei Beispielkarten (Frage + Ziel, öffnen den Dialog vorbefüllt) und die
      offene Erklärung „Why a Watch, not a scheduled prompt“ samt Vergleichstabelle.
      Mit Watches: Kennzahlenzeile (watching / moved / resolved this week / next
      check), eingeklappte Erklärung, Abschnitte Watching / Resolved / Paused und
      Delivery. Karten zeigen Status (Moved, Re-checking, Answer stands, Watching,
      Resolved, Paused), Frage, „Waiting for“ + Zielstatus, den Satz des Zustands,
      tragende Quellen, die Check-Leiste und rechts nächsten Check + Tages-Scan;
      **kein** Agreement-Score. „Settings“ klappt Ziel, Intervall/Tag/Uhrzeit,
      Alerts, Kanäle, Google-Listing, Pause/Resume und Delete in der Karte auf.
      Eine abgeschlossene Watch bietet „Watch for something new“; dasselbe Ziel
      wird abgelehnt, ein neues oder leeres Ziel reaktiviert sie. ESC führt zurück.
      Light/Dark und Mobile ohne Overflow.
- [ ] Create-Dialog: nach der Frage steht „What are you waiting for?“ ganz oben;
      Zielvorschläge laden als Chips (Platzhalter während des Ladens, Klick füllt
      bzw. leert das Feld, Ausfall blendet sie nur aus). „Only when it resolves“
      ohne Ziel zeigt den Fehler am Zielfeld. „Back“ behält Frage und Ziel.
- [ ] Der Watches-Schalter pulsiert als neuer, unbestätigter Einstieg nur zweimal
      dezent, stoppt nach dem ersten Öffnen dauerhaft und ist bei reduzierter Bewegung
      still. Er konkurriert nicht mit dem resultatspezifischen Watch-Hinweis.
- [ ] Morning Brief (Karte im Dashboard): Toggle aktiviert die tägliche
      Digest-Mail mit Uhrzeit (Browser-Zeitzone) und Modus „Every morning“ /
      „Only when something changed“; Einstellungen überleben ein erneutes
      Öffnen. Schlägt PATCH für Uhrzeit oder Modus fehl, springen die Controls
      auf den letzten serverbestätigten Wert zurück. Mit Test-SMTP: Brief-Mail listet alle Watches mit Ziel,
      Bewegungen und Abschlüssen (kein Score); der Abmelde-Link deaktiviert nur den Brief, nicht
      die Watch-Mails.
- [ ] Ohne Watch ist der Morning-Brief-Toggle deaktiviert und erklärt „Create a
      watch first“; ein direkter Aktivierungs-Request wird abgelehnt. Nach dem
      Löschen der letzten Watch ist ein zuvor aktiver Brief ausgeschaltet.
- [ ] Aktive Watch-Seite erklärt vor dem ersten Vergleich verständlich, dass
      erst eine Baseline vorliegt; Status bleibt sichtbar, Zeitplan/letzter/
      nächster Lauf sind über „Schedule and check dates“ erreichbar. Mit History rendert
      sie den neuesten gespeicherten Consensus statt des ursprünglichen Texts,
      einen Stable/Changed-Drift-Header; Direction Shift und Agreement Change
      stehen erst in „advanced change metrics“. Der Drift-Header enthält den
      kompakten Agreement-Chart; Hover erklärt jeden Punkt, Klick springt zur
      passenden sichtbaren Run-Zeile. Der Link „View full chart“ öffnet die große
      SVG-Kurve. Chart, Run-Liste und Position Map funktionieren in Light/Dark
      ohne Mobile-Overflow. Jede neue Vollversion ist aus ihrer Run-Zeile erreichbar;
      `?version=original` zeigt unverändert die
      Ausgangsversion. Eine normale Shared Page ohne Watch bleibt unverändert.
      Neue History zeigt direkt unter den Quellen die stets offene, mehrdimensionale
      Position Map mit verständlichen Positionskarten, Modell-Chips und Direction
      Shift; Provider-Trajektorien sind nachrangig aufklappbar. Alte
      Punkte ohne `opinion_map` degradieren auf den Agreement-Chart.
- [ ] Fehlende SMTP-Konfiguration blockiert Watch-Läufe nicht. Mit Test-SMTP:
      ein Check mit `moved` sendet genau eine Multipart-Mail „Moved: …“ als
      Änderungsprotokoll (What changed → Why mit Quellen → What held → Waiting
      for → Question, keine Agreement-Zeile); `held`, `confirming`, `restated`
      senden im Modus „When it moves“ nichts. „After every check“ sendet bei
      jedem Lauf genau eine Mail mit der Antwort. Ein belegt erreichtes Ziel
      sendet genau eine „Resolved: …“-Mail, die Watch steht danach auf
      „Resolved“ und läuft nicht mehr. Abmelde-Link pausiert ohne Login.
- [ ] Belegmodell (`docs/watch-evidence-model.md`): ein Check, dessen Suche die
      Quellen der geltenden Antwort nur nicht wiederfindet, steht als „Answer
      stands“; die öffentliche Seite zeigt weiter die geltende Version plus
      „Latest check: …“. Eine Neubewertung ohne neue Quelle steht als
      „Re-checking“, der nächste Lauf ist rund 20 Minuten später fällig.
      Persistierte Ereignisse: `watch.checked`, `watch.changed`,
      `watch.confirming`, `watch.condition_met`, `watch.run_failed`.
- [ ] Tages-Scan: eine weekly/monthly-Watch zeigt im Dashboard „Daily scan:
      nothing new (…)“; findet der Scan eine neue Quelle, ist der volle Check
      sofort fällig. Admin-Limit „Evidence probes per day“ = 0 schaltet ihn ab.
- [ ] Mit gesetztem `TELEGRAM_BOT_TOKEN`, `TELEGRAM_BOT_USERNAME` und
      `TELEGRAM_WEBHOOK_SECRET`: „Connect Telegram“ öffnet den Bot, `/start`
      verbindet ausschließlich den eingeloggten Account und das Dashboard zeigt
      danach Identität, „Send test“ und „Disconnect“. Abgelaufene oder erneut
      verwendete Deep-Links werden abgelehnt.
- [ ] Telegram lässt sich beim Erstellen und je Watch an-/abschalten; mindestens
      E-Mail oder Telegram bleibt aktiv. Ein materieller Change erzeugt genau
      eine Telegram-Nachricht als Änderungsprotokoll (mit Quellen-Links, ohne Score) und Buttons. „Mute 24h“
      unterdrückt weitere Telegram-Alerts, „Pause“ verlangt eine zweite
      Bestätigung und pausiert nur die eigene Watch. Ein erneuter Scheduler-
      Versuch für dieselbe Run-ID verschickt kein Duplikat.

## Curated Topics
- [ ] Belegmodell auf Topics: ohne `?version` zeigt die Seite den geltenden Run
      (`accepted_run_id`); ein neuester Check mit „held“/„confirming“ erscheint als
      „Latest check: …“-Hinweis, in Timeline und Check-Streifen als eigener,
      nicht-materieller Zustand, und seine Claims zählen im Claim Ledger als Lücke.
      Der Hub zeigt Score und Satz des geltenden Runs.
- [ ] `/topics` zeigt nur Topics mit mindestens einem veröffentlichten Snapshot;
      Suche und Kategorie-Filter funktionieren ohne Reload. Navigation, Footer,
      Light/Dark, Focus States und Mobile-Layout bleiben ohne horizontalen
      Overflow.
- [ ] `/topics/{slug}` zeigt das vollständige Dossier und die Timeline beim
      ersten Laden bereits geöffnet. Die fünf bestgereihten aktuellen Quellen
      sind sichtbar, alle weiteren starten in einem eigenen Detail eingeklappt;
      ältere Evidence bleibt separat eingeklappt. Quellen tragen die Rollen
      Primary source, Research paper, Documentation, Reporting, Community oder
      Rumor und sind nach Qualität sortiert. Alle Links öffnen sicher in einem
      neuen Tab.
- [ ] Die visuelle Timeline zeigt alle versionierten Stände und ihre Agreement-
      Entwicklung. Ein historischer `?version=<run_id>`-Link rendert den
      unveränderlichen alten Consensus samt damaligen Modellen/Evidence,
      kennzeichnet die historische Ansicht und verlinkt zur aktuellen Version.
- [ ] Topic-Follow sendet mit Test-SMTP eine Double-Opt-in-Mail; erst der
      Bestätigungslink persistiert das Abo. Ein neuer Minor-/Major-Snapshot
      versendet genau ein Update, Stable nicht; der Abmelde-Link entfernt nur
      das Topic-Abo und verändert weder Nutzer-Watches noch Share-Follower.
- [ ] `/admin#topics`: Create/Edit, Slug/Kategorie/Intervall, Status
      Active/Paused/Archived, konkrete Modelle je Provider, Quellenpräferenzen
      und SEO lassen sich verständlich speichern. `/admin/topics` leitet auf
      diesen Tab um.
- [ ] „Run now“ benötigt keinen manuell eingetragenen Consensus, Score,
      Evidence-Link oder Opinion Change. Der Lauf recherchiert aktuelle Quellen,
      führt nur die ausgewählten Modelle aus und legt eine neue unveränderliche
      Version mit Agreement, Change-Summary, Opinion Map und Evidence an. Ein
      zweiter Run vergleicht gegen den ersten Stand.
- [ ] Daily/Weekly/Biweekly/Monthly setzt einen sichtbaren `next_run_at`; der
      Topic-Scheduler führt fällige aktive Topics aus. Manual setzt keinen
      Termin, Paused/Archived laufen weder automatisch noch über „Run now“.
      Bei fehlendem SMTP wird ein erfolgreicher Material-Change-Run gespeichert
      und der Admin transparent auf nicht versendete Updates hingewiesen.

## Modelle / Picker
- [ ] Custom Model Picker öffnet/wählt, sichtbarer Name aktualisiert.
- [ ] Tier-Defaults (Free vs. Pro) werden beim Tier-Wechsel angewandt; eine
      zuvor explizit im Picker gewählte Provider-Auswahl bleibt erhalten.
- [ ] Modell-Auswahl bleibt nach Reload erhalten (localStorage).

## Attachments (Pro)
- [ ] Datei anhängen → Chip erscheint, Vorschau öffnet, Entfernen funktioniert.
- [ ] PNG/JPG/WebP mit Strg+V im Fragefeld einfügen → Bild-Chip erscheint;
      normaler Text-Paste bleibt unverändert möglich.
- [ ] PDF/DOCX/TXT/MD/CSV/PNG/JPG/WebP auf den Input ziehen → Drop-Hinweis
      erscheint und nach dem Ablegen wird der passende Datei-Chip angelegt.
- [ ] Mit einem echten Anhang zeigt der Modell-Picker ein Modell weniger und
      beim Senden entsteht kein `/ask_deepseek`-Request; nach Entfernen wird
      die vorherige DeepSeek-Auswahl wiederhergestellt. Dasselbe gilt fuer
      `/ask_glm`, sobald GLM 5.3 das effektive Modell ist.
- [ ] Bookmark-Attachments werden angezeigt.

## Auth / Usage / Tier

- Mit Free mehrere gesperrte Funktionen anklicken (High Quality,
  Resolve): ein kurzer Hinweis wird ersetzt, kein Vollbild-Dialog;
  Frage und Modellauswahl bleiben erhalten und der Composer bleibt bedienbar.
  Nach fünf Sekunden verschwindet der Hinweis automatisch; ein weiterer
  Klick auf eine gesperrte Funktion startet die fünf Sekunden erneut.
- „About early access“ im Hinweis oder „Early access“ in der Sidebar öffnet
  die kurze Erklärung mit Kontaktmail. Schließen, Escape, Tab-Schleife und
  Fokus-Rückgabe auf Desktop und Mobil prüfen. Plus darf Resolve,
  Pro alle vorhandenen Funktionen weiterhin direkt nutzen.
- [ ] Anhänge für alle Konten: Free öffnet über (+) → „Add files“ den
      Dateidialog (kein Stufen-Badge), ein Gast bekommt stattdessen das
      Login-Modal. Im Agent-Modus meldet der 26. gespeicherte Upload eines
      Free-Kontos „File storage limit reached (25 files or 25 MB)“.
- [ ] E-Mail-Registrierung mit neuer und bestehender Adresse zeigt denselben
      neutralen „Check your inbox“-Zustand; die `/register`-Bodies sind exakt
      gleich und enthalten weder UID/E-Mail noch Custom-Token. Das eingesendete
      Legacy-Passwort erlaubt bei einer neuen Adresse keinen direkten Login;
      beide Fälle führen ausschließlich über den Link im Postfach.
- [ ] Login (E-Mail + Google), Logout.
- [ ] Login-Dialog auf echtem iPhone (Safari) und Android (Chrome): Öffnen
      fokussiert kein Feld (Google bleibt sichtbar), Tabs Log in/Sign up,
      „Los“ auf der Tastatur loggt ein, falsches Passwort zeigt „E-mail or
      password is not correct“. Mit `FIREBASE_AUTH_DOMAIN=www.consens.io`:
      Google läuft als Redirect, Kontoauswahl nennt consens.io, nach der
      Rückkehr schließt der Dialog von selbst.
- [ ] Aus der LinkedIn-App (In-App-Browser): Google zeigt den Hinweis „doesn’t
      work inside the LinkedIn app“ mit „Copy link“ (Android zusätzlich „Open in
      Chrome“); E-Mail-Login funktioniert dort weiter.
- [ ] Sign-up mit Gmail-Adresse: „Open Gmail“, Resend-Cooldown, „Use a
      different address“. Der Link in der Mail endet nach dem Passwort-Setzen
      über „Continue“ auf `/app?setup=1` mit vorausgefülltem Login.
- [ ] Nach Logout verschwinden Account-Label, Kontingent-Ring/-Panel, Usage-
      Zahlen, Watch-Kontingent und Bookmark-Inhalte sofort; Bookmarks und Suche
      sind als Gast nicht klick- bzw. fokussierbar. Auch eine vor dem Logout
      gestartete langsame Usage-/Bookmark-Antwort darf nichts wieder einblenden.
- [ ] Free-User: Usage-Counter + Limit-Anzeige korrekt, Limit-Fehler greift.
- [ ] Pro-User: Premium-Modelle freigeschaltet, UI-Status korrekt.
- [ ] Derselbe `usage_run_key` löst pro Provider/Consensus/Resolve nur einen
      externen Lauf aus; ein paralleler oder wiederholter Request endet vor
      Providerarbeit eindeutig mit 409.

## Bookmarks / Sidebar
- [ ] Models und Bookmarks beginnen auf derselben Icon-/Textachse und verwenden
      dieselbe Titelgröße/-stärke; im Gastzustand bleibt Bookmarks deaktiviert.
- [ ] Nach einer fertigen Antwort öffnet „Models“ den Picker normal — es gibt
      keine Entscheidung mehr, die ihn sperren könnte.
- [ ] Bookmarks laden/aufklappen, Chat-Suche filtert.
- [ ] Ein abgewiesener Bookmark-Save (Count-/Speicher-/Rate-Limit) zeigt genau
      eine verständliche Meldung, auch wenn sechs Modell-Merges parallel
      denselben Fehler erhalten; es entsteht keine Popup-Kaskade.
- [ ] Turn 1, Turn 2, Turn 3 und weitere Follow-ups aktualisieren genau ein
      Sidebar-Bookmark. Nach Reload öffnet dieses eine Bookmark den vollständigen
      Verlauf in richtiger Reihenfolge und ein weiteres Follow-up bleibt im
      selben Chat sowie im selben Bookmark.
- [ ] Bookmark aus dem frischen Leerzustand öffnen: Input dockt ohne Hero-Sprung
      oben an und die gespeicherten Antworten sind direkt sichtbar.
- [ ] Einen gespeicherten Consensus nach Reload öffnen: Share-Link und Watch
      lassen sich ohne erneuten Consensus-Lauf erstellen (während der kurzen
      Vorbereitung zeigt der Dialog einen deaktivierten Ladezustand).
- [ ] Model insights über Help → FAQ öffnen/schließen; im Thread bleibt es verborgen.
- [ ] Nach einem echten abgeschlossenen Consensus lässt sich genau dessen
      Consensus-Bookmark speichern; ein frei erfundenes oder fremdes
      `result_id` wird abgewiesen. Wiederholtes Klicken auf denselben
      Best-answer-Vote erhöht Model Pulse nicht erneut.

## Demo & Sonstiges
- [ ] „Demo"-Query startet den Demo-Flow (demo.js Integration intakt).
- [ ] Moduswahl Agent (auch als Gast über `/app?demo=1`): die Demo spielt einen
      Agent-Turn — „Working for …s“, Planungsnotiz, „Comparing perspectives…“,
      gestreamte Antwort, „Checking the answer…“ mit Schimmer, danach „Thought
      for …s“, Markierungen und Evidenzzeile mit 45/100, Contradictions 2,
      Answers 6 (öffnet alle sechs Antworten). „New chat“ beendet die Ansicht.
- [ ] Demo zeigt 52/100 „Partial agreement" (amber), drei Differences-Karten
      (kritisch: Schlusszeile, klein: Ursache benennen, Gewichtung: Entschuldigung
      oder Plan) und sechs Claim-Badges — davon 5/6 und 4/6 mit Dissens. Alle
      Anker sitzen INLINE im Konsenstext, keiner landet in der Fallback-Liste
      „Key claims". Quellenliste ist bei diesem Szenario bewusst leer.
- [ ] Demo erzeugt weder einen Best-answer-Vote noch einen Eintrag in der
      Differences-Telemetrie oder einen Bookmark-Persistenzaufruf.
- [ ] Die Demo tippt erst die Frage, fügt danach den Nachrichtenentwurf in
      einem Zug ein, leert beim simulierten Absenden das Eingabefeld und
      startet erst dann die Modell-Ladeanimation.
      Nach Abschluss sieht ein ausgeloggter Nutzer eine
      Login-/Registrierungs-Aufforderung; deren Button öffnet das Login-Modal.
      Nach erfolgreichem Login verschwindet die Aufforderung.
- [ ] Dark/Light-Toggle in Settings (Desktop und Mobile).
- [ ] Mobile-Layout (< 768px): Overlay-Sidebar, Info-Popups.
- [ ] System-Prompt-Modal + Help-Modal (app-ui.js) öffnen/speichern.

### Gemeinsame Detail-Seitenleiste
- [ ] Differences und Sources aus aktuellem und archiviertem Turn oeffnen rechts denselben Leser; auf Handy/Tablet bildschirmfuellend.
- [ ] Abschnitts- und Fragenwechsel behalten die korrekte Zuordnung; Schliessen stellt Karten/Quellenlisten an ihren Ursprungsort zurueck.
- [ ] Differences zeigen zuerst Typ und Kernaussage. Aufklappen zeigt Positionen, Zitate, Pruefhinweis und vorhandene Resolve-Aktionen; Marker oeffnen die passende Karte.
- [ ] Quellen zeigen Titel/Domain; laengere Auszuege sind separat aufklappbar.
- [ ] Kurze Fragen haben keinen nutzlosen Chevron; lange Fragen lassen sich ohne doppelten Text auf- und zuklappen.
- [ ] Desktop 1440/1920/2560px: Chat in der Restflaeche zentriert, Leser waechst mit; linke Navigation ein- und ausklappen.
- [ ] Quellen-Favicons geladen und fehlgeschlagen: Titel, Domain und Referenznummer bleiben in beiden Faellen lesbar; Fehler zeigen einen Buchstaben statt kaputtem Bild.
- [ ] Ein einzelner Unterschied direkt offen; erweiterte Desktopansicht mit Positionen nebeneinander, Handy untereinander.

### Check Sources: dauerhafte Belegprüfung
- [ ] Check Sources vor dem Start ausschalten und während des Laufs einschalten:
      Der gestartete Lauf behält seine ursprüngliche Einstellung; erst der nächste
      Consensus übernimmt die Änderung.
- [ ] Mehr Quellen und Satz-Quellen-Zuordnungen als ein Prüfpaket verwenden:
      Alle zitierten Quellen erhalten einen Status. Quellenanzahl, geprüfte
      Zuordnungen, noch ausstehende Prüfungen und nicht prüfbare Einträge bleiben
      getrennt sichtbar; kein später Quellenverweis verschwindet wegen seiner Position.
- [ ] Quellen-GET absichtlich verzögern: Consensus, Differences und Laufabschluss
      sind bereits benutzbar. Die Quellenprüfung aktualisiert sich anschließend
      schrittweise, ohne Antwort, Agreement-Score, Claim-Knoten oder offene
      Quellenpassagen und Tastaturfokus zu ersetzen.
- [ ] Quellen mit widersprechender Zahl, fehlender Bedingung, unklarem Beleg,
      falschem Zeitraum und Abruf-Timeout prüfen: „Statement contradicted“,
      „Partly supported“, „Support unclear“ und „Not checked“ bleiben unterscheidbar.
      Originalpassage, Prüfzeit und konkrete technische Fehlerursache sind lesbar;
      ein Prüfabschluss allein erzeugt keinen positiven Gesamt-Haken.
- [ ] Einen identischen Quellenbeleg mehrerer Modelle öffnen: Herkunft nennt die
      beteiligten Modelle und erklärt die gemeinsame Quelle. Modell-Zustimmung
      und -Dissens gehören zum selben Satz und bleiben von Quellenbelegen getrennt.
- [ ] Während der Quellenprüfung zu einem anderen Lauf oder Bookmark wechseln:
      Ergebnisse landen nur im ursprünglichen Lauf. Ein geschlossenes oder neu
      geöffnetes Bookmark sowie historische Turns laden auch aus kompakten,
      bereits abgeschlossenen Job-Snapshots die vollständigen Details nach.
- [ ] Ausloggen oder einen Lauf entfernen, während ein Quellen-GET offen ist:
      Der Request wird abgebrochen; seine verspätete Antwort verändert weder
      fremde Inhalte noch die neue Sitzung. Tab ausblenden stoppt regelmäßige
      Abfragen; Rückkehr setzt die Aktualisierung fort.
- [ ] Unveränderte Job-Revision mehrmals abfragen: nur kompakter Header-Check
      mit `after_revision`, keine erneuten Detailseiten und keine DOM-Neuzeichnung.
      Bei Änderungen werden alle Cursor-Seiten derselben Revision geladen;
      ein Revisionswechsel währenddessen startet die Seitensammlung neu.
- [ ] Quellen-GET mit 403/404 beantworten: „Updates unavailable“ und eine
      verständliche Erklärung erscheinen; der letzte Befund bleibt erhalten.
      Drei vorübergehende Abruffehler zeigen einen Wiederholungs-Hinweis;
      erfolgreiche Aktualisierung entfernt ihn, ohne den Belegstatus umzudeuten.
- [ ] Eigenkey-Lauf nach verlorenem Worker-Credential öffnen: höchstens eine
      automatische Wiederaufnahme mit dem vorhandenen eigenen Schlüssel;
      ein Serverkey-Lauf darf diesen Schlüssel nicht verwenden. Ohne Schlüssel
      bleibt die notwendige Eingabe sichtbar, ohne einen neuen Consensus zu starten.
- [ ] Öffentliche Share-/Topic-Ansichten zeigen nur ihren gebundenen Snapshot und
      laden dessen Quellenstatus nach. Bei historischen Versionen wandern weder
      Befunde noch Quellen aus einer neueren Version hinein.
- [ ] Desktop sowie 390/320px, Hell/Dunkel und reduzierte Bewegung prüfen:
      Quellenstatus bleibt sichtbar, Badges und Originalpassagen umbrechen ohne
      horizontales Scrollen; reduzierte Bewegung deaktiviert Ladeanimationen.

- [ ] Frische Sitzung in Consensus: gespeicherten Direktvergleich oeffnen.
      Alle gespeicherten Modelle sind sichtbar, auch aktuell ausgeschlossene.
      „Direct comparison“ erklaert das Ergebnis; die Wahl fuer die naechste
      Frage bleibt Consensus. Wechsel zu einem
      Consensus-Bookmark und zurueck zeigt keine leeren oder fremden Antworten.

## Agent · Beta: Vergleiche und Prüfungen

- [ ] Mobil bei 320/369/390 px Folgefrage fokussieren, auch mit kurzer
  Tastatur-Ansicht: Chatmodell steht in einer eigenen Zeile über Plus, Compare
  und Senden; die drei Aktionen haben eine gemeinsame Mittellinie.
  Lange Labels kürzen sich innerhalb ihres Buttons;
  Dropdown-Pfeile bleiben direkt am Label. Beide Picker bleiben bedienbar.
- [ ] Während der Chatmodellkatalog lädt oder nicht verfügbar ist: Nachricht
  tippen können, Senden gesperrt und Erklärung am Composer. Bei ungültiger
  Vergleichsauswahl öffnet „Choose models“ den Picker; nach Korrektur verschwindet
  der Hinweis. Auch im mobilen Folgefragen-Composer prüfen.
- [ ] Leere Nachricht sperrt Senden; ein hinzugefügtes Zitat gibt es frei.
  Während der Antwort bleibt Stop nutzbar und ein neuer Entwurf kann entstehen.
- [ ] Ein Fehler/Stop vor dem Versand erhält Text und Zitat im Composer.
  Ein inzwischen neu geschriebener Entwurf oder anderer Chat bleibt unverändert.
- [ ] Unter einer Agent-Antwort steht kein Copy-Button (Desktop und Handy).
- [ ] Am Ende eines geprüften Laufs bleiben die Claim-Marken stehen (kein
  erneutes Einblenden); Reload eines Agent-Chats: Bookmarks und Eingabefeld
  springen nicht.
- [ ] Handy, Antwortleser „Answers“: Modellauswahl schließt das Dropdown.
- [ ] Folgefragen direkt im Composer; kein zusätzlicher „Follow up“-Button.
  Contradictions/Review, Answers und Sources haben dezente Icons, lesbare
  Anzahlen und öffnen weiterhin den passenden Antwortleser. Bei 320/390 px
  stehen sie in drei gleichen Spalten ohne abgeschnittene Beschriftungen.

- [ ] Vergleichsmodelle im Picker auf eins/keines reduzieren: Senden ist gesperrt,
      Enter erhält den Entwurf und erstellt keinen Chat. Zwei Modelle wählen
      gibt Senden wieder frei; Desktop und Mobil prüfen.
- [ ] „Hi“ und notwendige Rückfragen erscheinen einmalig ohne Vergleichsaufruf.
      Bei inhaltlichen Anfragen erscheint vor der Synthese kein kurzlebiger
      Antwortvorspann. Eine Folgefrage zu einer gespeicherten fehlgeschlagenen
      Antwort behält deren Kontext und behandelt sie nicht als geprüft.

- [x] Zuverlässigkeitsprüfung (20.09.2026): Token-Warten bleibt bei geschlossenen
      Aktivitätsdetails mit Erklärung sichtbar; Desktop-Taskzeile zeigt den
      Wartezustand. Stop bleibt bedienbar, kein horizontaler Overflow bei
      1280/390/320 px, Hell/Dunkel. Browserprüfung mit simulierten APIs und
      visuelle Kontrolle der Screenshots unter
      `artifacts/agent-reliability-2026-09-20/`; Details und Grenzen im
      [Zuverlässigkeitsaudit](agent-reliability-audit-2026-09-20.md).

- [ ] Bottom-Bar vor und nach dem Senden bei 1440/390/320 px: vor dem Senden
      zeigt das (+)-Menü „Agent“ mit Haken, im offenen Agent-Chat tritt die
      Modusgruppe zurück und das Eingabefeld behält seine Breite.
      „Check contradictions against sources“ gibt es nur noch unter Settings →
      Runs; ein laufender Run und Recovery behalten den eingefrorenen Wert.
      Unter einer Agent-Antwort mit geprüften Widersprüchen sagt der
      Contradictions-Link, was die Quellen ergaben („· 1 settled by sources“,
      „· checking sources“).
      „Reasoning“ öffnet per Klick/Enter die vorhandene Reasoning-Auswahl,
      „Attach“ öffnet wie das (+)-Menü die Dateiauswahl (Upload in den privaten
      Chatspeicher). Kein horizontaler Overflow.
- [ ] Bei aktivierter Quellenprüfung erscheinen Ergebnis und aufklappbare
      Originalbelege direkt in den Widerspruchskarten, auch nach Öffnen des
      gespeicherten Chats. Off lässt Modellvergleich/Coverage aktiv. Fehlende
      oder abgelehnte Belege werden nicht als Bestätigung dargestellt.
- [ ] Mit Quellenprüfung endet der Agent-Lauf direkt nach dem Antwort-Check
      (kein Warten auf Abrufe); der Contradictions-Link zeigt „checking sources“,
      bis der Hintergrundjob fertig ist, dann z. B. „1 settled by sources“, und
      ein offener Reader zeigt die Urteile an den Karten. Neu laden während der
      Prüfung: der gespeicherte Turn verfolgt denselben Job weiter. Der
      Kontostand sinkt um die gemessenen Tokens der Prüfung.

- [ ] Im Agent-Chat ersetzt der verbleibende Tokenanteil als Prozentzahl den
  Run-Zähler im Sidebar-Footer (Rest unter 1 % als „<1%“). Panel: absolute
  Tokens, Rücksetzzeit in Ortszeit und UTC, keine Watches-Zeile.
  Keine Budgetzeile im Composer. Modus-/Accountwechsel zeigt keine fremden oder
  veralteten Zahlen.
- [ ] Agent-Aktivität bei 1920/1440 px mit offener und eingeklappter linker
  Navigation öffnen/schließen: die Spalte rückt neben die Leiste, nichts liegt
  darunter. Unter 1200 px öffnet sie nie selbst; das Panel-Symbol neben den
  Modell-Icons öffnet ein Sheet
  mit Scrim, Escape/Scrim schließt und gibt den Fokus zurück.
- [ ] Lauf mit Mail-Entwurf/Kalenderänderung: Aktivität zeigt „Email draft ready
  for review“ und „Waiting for your confirmation below“; nach dem Lauf steht über
  dem Composer „n items need your review · Review“, das Bookmark trägt einen
  Punkt, der Tab-Titel „(n)“. Review springt zur ersten offenen Karte.
- [ ] Tokenreservierung abgelehnt: Klartext mit Bedarf/Rest und Rücksetzzeit,
  Aktionen „Try a smaller model“/„Choose models“, Frage steht wieder im Composer.
  Ein vor dem Start abgelehnter Request (z. B. fehlende Google-Zustimmung) zeigt
  „Message not sent“, keine Recovery und keinen „Failed“-Eintrag.
  Modellname und Tokens stehen oben, Rolle sowie Status/Laufzeit darunter.
  Lange Namen und Metadaten bleiben auch bei 390/320 px in beiden Themes
  vollständig lesbar; keine Überschneidungen innerhalb der Einträge.
- [ ] Lange Agent-/Consensus-Antworten und gespeicherte Turns in beiden Themes
  bei Desktop- und Mobilbreite lesen: 16 px Schrift mit 28 px Zeilenhöhe,
  erkennbare Absatz- und Listenabstände, auch bei verschachtelten Listen.
  Markdown-Überschriften bleiben linksbündig mit normaler Groß-/Kleinschreibung;
  Tabellen, Code und Formeln erzeugen keinen horizontalen Seiten-Overflow.
- [ ] Agent-Antwort nach der Synthese weiterlesen, während Judge und optionale
  Quellenprüfung laufen: kein Leeren/Neuschreiben der Antwort und nur ein
  Prüfzyklus, auch bei unvollständigen Modellantworten. Überarbeitung erst nach
  neuer Nutzernachricht. Beim Lesen unten oder mitten in einer langen Antwort
  bleibt dieselbe Zeile stehen, wenn der Status darüber wechselt oder bei
  Abschluss einklappt; offener/geschlossener Verlauf und Reduced Motion prüfen.
- [ ] Agent-Reihenfolge: vollständige mehrteilige Antwort wird zuerst sichtbar,
  erst danach starten Coverage-/Differences-Judges und setzen Markierungen.
  Einleitung neben einem frühen Judge-Aufruf ersetzt nie den Antwortteil.
  Nach der Prüfung bleiben Wortlaut und Leseposition erhalten. Bei Stopp während
  der Synthese bleibt der Teiltext ungeprüft; keine Judges starten dafür.
- [ ] Agent-Synthese beginnt mit der eigentlichen Antwort, ohne interne Toolsyntax,
  Statusparameter, Arbeitsanweisungen oder Reasoning-Vorspann. Gesprächskontext,
  Quellen und bewusst angeforderte Codebeispiele bleiben erhalten.
- [ ] Agent-Synthese bei einer persönlichen Empfehlungsfrage: klare, begründete
  Empfehlung anhand der Nutzerkriterien, keine übernommenen Ich-Präferenzen oder
  erfundenen Erlebnisse der Vergleichsmodelle. Bedingungen bleiben erhalten;
  kein unbelegter absoluter Sieger. Aussagen sind für Coverage einzeln prüfbar,
  echte Unterschiede werden sachlich genannt statt für grüne Markierungen verdeckt.
- [ ] Oben am Pfeil steht die Laufzeit; sie zählt während Token-Warten weiter
  und bleibt nach Abschluss/Stop sowie beim Öffnen gespeicherter Turns stehen.
  Darunter wechseln sich kurze Meldungen des Steuerungsmodells in der Fragesprache
  und bestätigte Arbeitsschritte ab. Der aktuelle Status erscheint genau einmal.
  Meldungen sind dezent dunkelgrau im hellen und hellgrau im dunklen Modus,
  auch im geöffneten und gespeicherten Verlauf. Schritte bleiben schwarz bzw. weiß.
  Nur aktive Arbeitsschritte tragen einen ruhigen, schmalen Lichtreflex (2,4 s),
  auch im geöffneten Live-Verlauf. Die aktuelle Statuszeile („Thinking…“, aktiver
  Schritt, „Writing answer…“) beginnt mit dem consens-Zeichen in Textfarbe; ein
  einziger Reflex läuft ohne Sprung erst durch das Zeichen, dann durch das Label.
  Laufzeit, Absätze und fertige Schritte bleiben ohne Reflex; Reduced Motion und
  Forced Colors zeigen Zeichen und Text vollständig deckend.
  Frühere Absätze und Arbeitsschritte bleiben erhalten;
  Reasoning-Rohtext erscheint nicht als Fortschritt. Beim Abschluss oder Stop
  verschwinden die Live-Absätze und ein geöffneter Verlauf klappt zu. Pfeil/Enter
  öffnet danach alle gespeicherten Absätze und Toolschritte in ihrer Reihenfolge,
  ohne inneren Scrollkasten. Auch bei 320/390 px keine abgeschnittenen Texte.
- [ ] Duration-Verlauf auch direkt beim Abschluss und nach erneutem Öffnen prüfen:
  Bereits während „Thinking…“ sind Modell, Reasoning-Einstellung und aktuelle
  Phase sichtbar. Ein laufender Vergleich zeigt sein Ziel und seinen Zweck;
  noch nicht verfügbare Ergebnisse öffnen keinen leeren Antwortleser.
  vorhandene Meldungen bleiben bei unvollständigem Abschluss-Snapshot erhalten.
  Vergleichsziel, Modelle, Unterschiede und Prüfstatus sind im aufgeklappten
  Bereich lesbar; Originalantworten und vollständige Prüfung lassen sich öffnen.
  Alte Turns ohne Aktivitäten nutzen vorhandene Vergleichsdetails. Veraltete
  Prüfungen erscheinen als ausstehend, vollständig fehlende Details als Hinweis.
- [ ] Neue Statusabsätze und der erste Antworttext blenden dezent ein; bereits
  sichtbarer Text animiert bei Streaming-Updates nicht erneut. Der Statusbereich
  zieht sich bei Abschluss weich zusammen. Schnelles Auf-/Zuklappen und Turnwechsel
  hinterlassen keine fixierten Höhen oder unsichtbaren Fokusziele. Reduced Motion
  und Forced Colors zeigen alle Zustandswechsel unmittelbar ohne Animation.
- [ ] Reasoning ist im Chatmodellmenü erreichbar (auch per Tastatur); der
  Composer enthält im laufenden Chat nur Chatmodell und Compare-Auswahl.
- [ ] Sources enthält Chat-Recherche und zitierte Antwortlinks, auch wenn
  Vergleichsmodelle keine Quellenmetadaten liefern oder kein Vergleich läuft.

- [ ] Chatmodell und Compare-Preset getrennt wählen; Custom zeigt nur
  Vergleichsmodelle, keine Consensus-Engine. Escape gibt den Fokus zurück.
- [ ] Einen ausdrücklichen Vergleich und zwei Teilfragen testen: unabhängige
  Einzelantworten in Aktivitäten öffnen, anschließend gestreamte Synthese und
  Prüfstatus sehen. Vergleichsgrundlage wechseln und Markierungen/Details prüfen.
- [ ] Antwort nach Prüfung überarbeiten lassen: neue Version und erneute Prüfung;
  eine alte Markierung darf nicht auf den neuen Text wandern.
- [ ] Während Vergleich und Judge stoppen; gesicherten Turn wieder öffnen.
  Fehlende/teilweise/abgebrochene Prüfung bleibt erkennbar, Recovery startet
  keinen neuen Provider-Aufruf. Ein Account-/Chatwechsel mischt keine Daten.
- [ ] Kontingent nahe der Grenze mit zwei parallelen Chats prüfen; Chat,
  Vergleich und Judges teilen Tokens — seit 2026-10-01 auch mit Compare und
  Consensus (ein Konto, ein UTC-Reset).
- [ ] Prozentanzeige während Calls und nach Budgetfehler/Disconnect prüfen:
  aktueller Serverwert; Panel zeigt Reserven. Eine unzureichende Reserve wird
  nicht als leeres Budget bezeichnet. Optionale Suche darf vor dem Claim
  entfallen, sofern der Kernaufruf weiter ins Budget passt.
- [ ] Tool-Nennungen im Denkfortschritt bleiben normaler Text; nur bestätigte
  laufende Calls erhalten eine Statuszeile. Nach Ende verschwindet die Vorschau.
- [ ] Agentenleiste öffnet sanft, respektiert manuelles Schließen und Reduced
  Motion. Modellzeilen zeigen gemessene Tokens statt Dollarbeträgen. Judge-
  Details erscheinen sofort ohne Detailrequest; Worker zeigen beim ersten
  Laden einen Skeleton, beim erneuten Öffnen den Cache ohne weiteren Request.
- [ ] Bei langer Modellliste bis ans Ende scrollen: Titel, Gesamtverbrauch und
  Stop/Schließen bleiben sichtbar und bedienbar; nur die Modellliste scrollt.
- [ ] Desktop und 390/320px, Hell/Dunkel, Tastatur und Reduced Motion prüfen.
- [ ] Agent-Budget: Reservierung und Freigabe ohne gemessenen Verbrauch verändern
  den Prozentwert nicht; der Kontingent-Dialog zeigt Reserven separat. Admin →
  Limits speichert Tageslimit je Stufe und Laufschätzungen je Stufe/Modus und
  kann alle Konten zurücksetzen.
- [ ] Ein Tokenkonto für alle Modi: Ring im Sidebar-Fuß ist ein ruhiges
  20-px-Glyph ohne Zahl; Hover/Screenreader nennen „62% of today's allowance
  left · resets …“. Panel: eine Hauptzahl, dünner Balken, Reset-Zeile,
  Detailzeile („409k of 660k tokens · a Consensus run uses about 8%“), Watches
  separat. Hell/Dunkel, Desktop und 320/390 px; bei ≤ 25 % färben sich nur
  Bogen und Balken amber, leer rot. Ein Compare- oder Consensus-Lauf senkt den
  Prozentwert nach seinen Antworten bzw. dem Consensus; Agent zeigt dieselbe
  Zahl. Reicht das Konto nicht für einen typischen Lauf des Modus, erscheint
  die Absage-Karte vor dem Senden (Reasoning an: Angebot „Send without
  reasoning“, wenn ein normaler Lauf noch passt).
- [ ] Reasoning-Schalter (Compare/Consensus) mit einem Free-Konto: (+)-Zeile
  „Reasoning“ ohne Pro-Badge, Startleiste zeigt „Reasoning On/Off“ ohne
  „· Pro“; mit Reasoning an laufen dieselben gewählten Modelle und dieselbe
  Consensus-Engine (keine Modell-Überschrift wechselt), Antworten dürfen
  länger sein. Ein altes Bookmark mit Modus „Deep Think“ lädt und schaltet
  Reasoning nicht ein.
- [ ] Auch ein fehlgeschlagener Agent-Run ohne Hauptantwort bleibt als Bookmark
  erhalten: Frage, Fehler, Aktivität und vorhandene Vergleichsantworten sind
  nach Reload sowie später im älteren Verlauf sichtbar.
  Nach Transportabbruch erzeugt Recovery auch bei Mehrfachklicks keinen weiteren
  Failed-Bookmark. „Question“ steht weder über aktuellen noch früheren Fragen.
  Bereits gespeicherte Teilantworten erhalten sofort ihren dauerhaften Bookmark;
  nach Reload bleiben Text und Fehler sichtbar. Bei unbekanntem Zustand steht
  „Check saved answer“, bei laufendem Producer „Check run status“. Nach Ablauf
  der Lease kann derselbe gespeicherte Zwischenstand ohne Modellaufruf geöffnet werden.
- [ ] Nach einem Agent-Abbruch (z. B. „model is busy“) steht „Retry“ unter dem
  Fehler: Klick schickt dieselbe Frage im selben Chat erneut, ohne das
  Eingabefeld anzufassen; die Sidebar zeigt weiter genau eine Zeile.
  Bei „busy“ öffnet „Choose another model“ die Modellwahl.
- [ ] Überlappende Modell-Icons oberhalb der Antwort zeigen die richtigen Anbieter,
  auch Kimi, GLM und Muse. Mehrere Aufrufe desselben Modells bleiben in Activity
  einzeln sichtbar. Denkfortschritt bleibt kurz und als Zusammenfassung/Auszug
  gekennzeichnet; Judge-JSON und technische Aufgaben erscheinen nicht als Textwand.
- [ ] Rote Textstellen mit Maus und Enter öffnen die passende Widerspruchskarte.
  Modelllinks öffnen formatierte Einzelantworten, Footer-Links dieselben Ansichten
  und Quellen. Escape bringt den Fokus zurück. Activity und Antwortleser verdecken
  sich nicht; bei 1440px liegen Chat und Composer links neben dem Leser.
- [ ] Den gespeicherten letzten Turn und ältere Turns öffnen: gleiche Karten,
  Markdown-Antworten und Modell-Icons; Accountwechsel schließt den Leser.

## Chat-Scrollen (beide Modi)

- [ ] Ein gespeichertes oder lokal vorhandenes Bookmark öffnen: einmaliger sanfter
  Sprung ans Ende des geladenen Gesprächs. Hochscrollen oder ein Bookmark-/Kontowechsel
  unterbricht ihn; Reduced Motion springt sofort. Ein Hintergrundlauf scrollt nicht mit.
- [ ] Bookmark löschen: sofort weich ausgeblendet, ohne auf DELETE zu warten.
  Eine verzögerte Liste darf es nicht zurückbringen; bei einem Löschfehler kommt
  der Eintrag mit verständlicher Meldung zurück und kann erneut gelöscht werden.
- [ ] Im Agent- und Consensus-Chat eine Folgefrage nach einer langen Antwort senden:
  sanfter Sprung ans Ende; die wachsende Antwort folgt beim Mitlesen unten.
- [ ] Währenddessen hochscrollen, Text markieren oder einen Dialog öffnen:
  kein Zurückziehen. „Latest message“ führt wieder ans Ende; Chat-/Kontowechsel
  und Hintergrundantworten bewegen die neue Ansicht nicht.
- [ ] Mobil den Composer vergrößern/Viewport ändern und Reduced Motion aktivieren:
  letzte Antwort bleibt erreichbar, reduzierte Bewegung verzichtet auf Animation.

### Todo-Runde 3 (2026-10-02)
- [ ] Sidebar-Fuß in EINER Zeile: Imprint · Privacy · Terms links, Feedback-
      und GitHub-Zeichen rechts; das Kontingent-Glyph ist ein Kuchen im Ring
      (kein offener Bogen, der wie ein Ladekreisel aussieht).
- [ ] Landing: H1 „Six models answer. See where they disagree.“ auf Desktop
      zweizeilig; Composer-Mockups ohne Moduschip und ohne graue (+)-Fläche;
      der Modell-Chip nennt das echte Default-Modell des Agents.
- [ ] Demo und Landing erzählen die Wärmepumpen-Frage (1978, alte Heizkörper),
      43/100, „55 °C“ bricht nie zwischen Zahl und Einheit um.

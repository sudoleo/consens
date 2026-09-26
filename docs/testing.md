# Tests und sichere Ausführung

Die vollständige [Bestandsaufnahme der Testabdeckung](test-coverage-map.md)
beschreibt alle Testdateien, Assertionschwerpunkte, Mockgrenzen und den
verifizierten Laufstatus. Sie enthält außerdem ein maschinenlesbares Inventar
und das Vorgehen für den anschließenden Abgleich mit dem Produktionscode.

## Gemeinsamer Einstieg unter Windows

Delegation: `tests/test_agent_delegation.py` prüft Kommunikation, Abbruch,
Budgets und Wiederherstellung ohne bezahlte Aufrufe;
`tests/e2e/test_agent_transactions.py` atomare Schritte im Firestore-Emulator;
`tests/e2e/test_agent_delegation_frontend.py` die gebaute Desktop-/Mobilansicht.
Optionale kostenpflichtige Provider-Probes und Qualitäts-/Kostenvergleiche stehen
in [agent-delegation.md](agent-delegation.md); sie sind kein Teil normaler Tests.

PowerShell 5.1 oder neuer, aus dem Projektverzeichnis:

```powershell
.\dev.ps1 check frontend
.\dev.ps1 check backend
.\dev.ps1 check browser
```

| Ziel | Ablauf |
|---|---|
| `frontend` | `npm test`, danach `npm run build:check`. Ein veralteter Build führt zum Fehler; mit `npm run build` bewusst neu erzeugen. |
| `backend` | `venv/Scripts/python.exe -m pytest tests -q` mit `UNIT_TEST_MODE=1`; geerbte E2E-Schalter werden für den Lauf entfernt. |
| `browser` | Voraussetzungen und Build prüfen, dann Firebase `emulators:exec` mit der Playwright-Suite. Die CLI startet und beendet ihren Emulator auch bei fehlgeschlagenen Tests; die Pytest-Fixtures verwalten den App-Server und Browser. |

Die Frontend-Suite prüft auch die atomare Build-Veröffentlichung, unveränderte
Vendor-Dateien und die begrenzte Aufbewahrung voriger Bundles in temporären
Verzeichnissen (`tests/js/frontend-output.test.mjs`), ohne den Projekt-Build zu ändern.

Eine einzelne Datei oder ein Verzeichnis innerhalb der gewählten Suite:

```powershell
.\dev.ps1 check frontend -TestPath tests/js/app-state.test.mjs
.\dev.ps1 check backend -TestPath tests/test_streaming.py
.\dev.ps1 check browser -TestPath tests/e2e/test_phase2_transactions.py
```

Testpfade beziehen sich auf das Projektverzeichnis, auch wenn das Skript aus
einem anderen Arbeitsverzeichnis aufgerufen wird. `-TestPath` akzeptiert die
üblichen Repository-Pfade aus Buchstaben, Ziffern, `_`, `-`, `.` und Trennern;
für weitere Runner-Optionen oder Pytest-Selektoren die direkten Befehle unten
verwenden. `backend` lehnt explizite `tests/e2e`-Pfade ab.

`.\dev.ps1 help` zeigt die Kurzreferenz. Das Skript installiert keine Pakete
und verändert keine Builds. Fehlende Voraussetzungen werden mit einem Setup-Hinweis
gemeldet. Für Browserprüfungen braucht es zusätzlich die unten beschriebenen
E2E-Abhängigkeiten, Chromium, Firebase CLI und Java 21+ auf `PATH` oder unter
`JAVA_HOME`. Der erste Emulatorstart kann den von der CLI benötigten Emulator
herunterladen; Browser-Flows benötigen weiterhin die dokumentierten CDN-Assets.

Videoproduktion und ihre Prüfungen liegen separat in
[sudoleo/consens-video](https://github.com/sudoleo/consens-video).

Firestore-Host und Port stammen aus `firebase.json`, die Demo-Projekt-ID und
Loopback-Prüfung aus `app/core/e2e_profile.py`. Geerbte Projekt- und Credential-
Einstellungen werden für den Browserlauf ersetzt beziehungsweise entfernt.
Danach stellt das Skript Arbeitsverzeichnis und alle von ihm geänderten
Umgebungsvariablen wieder her, auch bei Fehlern. Fehlercodes der aufgerufenen
Werkzeuge werden weitergegeben; fehlende Voraussetzungen liefern Exit-Code 1.
Ein bereits belegter Emulatorport ist ein Startfehler, kein Anlass, fremde
Prozesse zu beenden. Auch der App-Testport muss frei sein.

### Pflege

`dev.ps1` koordiniert bestehende Werkzeuge: npm-Skripte bleiben in `package.json`,
Pytest-Fixtures und Testisolation in `tests/`, Emulator-Konfiguration und
Sicherheitsvertrag in ihren bestehenden Dateien. Neue Tests innerhalb einer
Suite werden automatisch vom jeweiligen Runner gefunden. Änderungen an diesen
Einstiegspunkten oder Voraussetzungen im selben Auftrag in `dev.ps1`, dieser
Dokumentation und gegebenenfalls `tests/e2e/README.md` nachziehen. Keine zweite
Liste einzelner Tests im Skript pflegen.

Die Regressionstests für Aufruf, Fehlercodes, Pfadauswahl und Wiederherstellung
der Shell laufen mit temporären CLI-Doubles auf den verfügbaren Windows-
PowerShell-Versionen; sie ersetzen keinen echten Emulatorlauf:

```powershell
.\dev.ps1 check backend -TestPath tests/test_dev_cli.py
```

## Abhängigkeiten

Agent-Admission benötigt `tiktoken` und `regex` aus `requirements.txt` (auch in
`requirements-test.txt` eingebunden). Das cl100k-Vokabular ist inklusive Lizenz
unter `app/services/llm/tokenizer_data/` eingecheckt. `dev.ps1` prüft beim
Python-Setup auch das lokale Laden samt Hash; es gibt keinen Download beim
ersten Chat oder Test. Fehlende Pakete wie üblich über die Requirements installieren.

`tests/test_agent_admission.py` prüft realistische Promptgrößen bei 20.933 Resttokens,
paralleles Warten/Stop, Anpassung des Provider-Outputs samt Receipt, echte Erschöpfung,
Reasoning-Mindestplatz, Unicode/Sondertokens ohne Netzwerk, Suchreserven und
Produktkontext. `tests/e2e/test_agent_transactions.py` prüft dasselbe Warten über
zwei getrennte Runs gegen den isolierten Firestore-Emulator.

`tests/test_agent_reliability.py` verbindet Admission, Provider-Transport,
Settlement und Recovery: verwaiste Starts, Stop vor Dispatch, lebende aber
fortschrittslose SSE-Verbindungen und gespeicherte Teilantworten. Die
Firestore-Prüfung umfasst auch gleichzeitigen Stop/Claim ohne lokalen
Prozess-Lock sowie ältere Belegformate vor einem verwaisten Run. Kurze
Netzwerkfristen und die sichtbare Warteanzeige werden in den Agent-JS- und
Browsertests geprüft. Ergebnisse und Grenzen:
[Agent-Zuverlässigkeitsaudit](agent-reliability-audit-2026-09-20.md).

### Standalone Publisher

Der Scheduled Publisher benötigt nur Python 3.11 und die Standardbibliothek.
Sein CI-Vertrag läuft ohne Paketinstallation, ohne geerbte Credentials und mit
deaktivierten site-packages; HTTP-Aufrufe werden im Test ersetzt:

```powershell
python -E -S -m unittest discover -s tests -p test_publisher_standalone.py -v
```

Die Tests prüfen direkten Skriptstart (auch außerhalb des Repos), Modulstart,
Modell-ID-Auflösung, Credentials sowie automatisches Auswählen, Publizieren,
Watch/Indexing und die Disabled-/Disagreement-Skip-Pfade. Sie laufen bei Push/PR
in `publisher-tests.yml` und vor jedem produktiven Publisher-Lauf. Die reguläre
Backend-Suite findet dieselben Tests ebenfalls automatisch.

Die Abhängigkeiten sind nach Zweck getrennt:

- `requirements.txt`: produktive Laufzeit,
- `requirements-test.txt`: reguläre Unit-/Integrationstests,
- `requirements-e2e.txt`: zusätzlich Python Playwright und das gepinnte
  `greenlet`,
- `benchmark/requirements-benchmark.txt`: ausschließlich Offline-Benchmark-
  Dataset-/Parquet-Abhängigkeiten (`huggingface-hub`, `pandas`, `pyarrow`).

Installation der regulären Testumgebung:

```powershell
venv\Scripts\python.exe -m pip install -r requirements-test.txt
```

Für E2E zusätzlich:

```powershell
venv\Scripts\python.exe -m pip install -r requirements-e2e.txt
venv\Scripts\python.exe -m playwright install chromium
```

## Reguläre Suite

Agent-Vergleiche: `tests/test_agent_comparison.py` führt den gemeinsamen
Differences-/Coverage-Parser mit deterministischen Providern aus und prüft
exakte Versionen, mehrere Teilgrundlagen, Ausfälle, Abbruch, UTC-Wechsel sowie
atomare Tokenreservierungen. `tests/test_agent_answer_lifecycle.py` reproduziert
einen frühen Judge-Aufruf mit bloßer Einleitung: Erst der vollständig gestreamte
toolfreie Antwortschritt darf die Judges starten. Geprüft werden Event-Reihenfolge,
gespeicherter Wortlaut, Hash-Bindung, leere Antworten, Tokenlimit und Nutzer-Stopp.
`tests/test_agent_synthesis_context.py` prüft die isolierte Synthese ohne internen
Tool-/Reasoning-Kontext, erhaltene Gesprächsinhalte und Quellen, mehrere/teilweise
Vergleiche sowie den Provider-Payload mit unterdrücktem Reasoning bei unveränderter
Denkstufe. Sichtbarer Stream, gespeicherter Text und Judge-Bindung bleiben identisch.
`tests/test_agent_chat_integrity.py` prüft mit der echten Chat-Policy die Reihenfolge
mehrerer Tools in einem Batch, automatische bestehende Prüfungen bei fehlendem
Toolcall, Protokollstillstand und gepufferte Direktantworten. Weitere Regressionen
decken fehlgeschlagene Turns im Folgekontext, gültige lange/mit „Error“ beginnende
Vergleichstexte sowie tatsächliche Worker-Abläufe mit Annahme, Überarbeitung und
geprüftem Ersatztext im Synthesekontext ab.
`tests/test_agent_progress.py` prüft begrenzte
Fortschrittsmeldungen aus validierten Toolargumenten, Reihenfolge vor Toolstart,
Persistenz, unveränderte Übernahme mehrsprachiger Texte und Aufruf-/Tokenabrechnung. Provider-
Reasoning des Steuerungsmodells bleibt aus dem Chatstatus ausgeschlossen;
Worker-/Legacy-Auszüge behalten ihre Grenzen und den Vorrang von Provider-
Zusammenfassungen. `tests/js/agent-review.test.mjs` prüft Bindungen und
Quellen aus Chat-Recherche, Antwortlinks und Vergleichsmodellen, auch ohne
Vergleich. `tests/js/agent-citations.test.mjs` prüft hochgestellte Quellenzahlen,
Paper-Titel, URL-Deduplizierung, explizite/mehrdeutige Quellen-IDs, Code- und
Zahlennotation, nachgelieferte Metadaten, Streaming sowie unveränderte Originaltexte
und die Reihenfolge von Prüfmarkierungen und Zitierdarstellung.
`tests/js/sidebar-quota.test.mjs` prüft die Agent-Prozentprojektion
und den Wechsel zurück zum unveränderten Consensus-Kontingent.
`tests/js/agent-answer-actions.test.mjs` prüft kanonischen Copy-Text ohne UI-
Zusätze, stabile Aktionen, Clipboard-Fehler/Fallback, Fokus und verspätete
Rückmeldungen nach Turnwechsel. Die Agent-Chat-Tests prüfen außerdem Lade-/Fehler-
und vollständig unverfügbare Kataloge sowie die Rückgabe ungesendeter Entwürfe
einschließlich Zitaten, ohne neuere Texte oder andere Konten/Chats zu überschreiben.
Die gebaute Browser-Suite prüft Kopieren mit der echten Chromium-Zwischenablage,
Folgefragen, Ladehinweise, Entwurfsrettung und die direkte Auswahlkorrektur bei
1280/390/320 px; alle Modellaufrufe bleiben simuliert.

`tests/js/agent-chat.test.mjs` prüft abwechselnde Fortschrittsabsätze und bestätigte Schritte, stabile DOM-Knoten,
HTML-Escaping, vollständigen Verlauf über das Hilfsereignisfenster hinaus,
automatisches Zuklappen beim Abschluss sowie erneutes manuelles Öffnen. Laufzeit-
Tests decken Minutengrenzen, Token-Warten, Stop, Timer-Cleanup und gespeicherte
Endzeitstempel inklusive ungültiger/fehlender Zeitangaben ab. Ungültige
Vergleichsauswahl (0/1/7 Modelle) erhält den Entwurf und startet keine Requests;
gültige Auswahl (2/6) wird vollständig übertragen.
Geöffnete Live-Details werden bereits vor dem ersten Fortschrittsereignis geprüft;
unvollständige finale Snapshots erhalten vorhandene Meldungen. Die Review-Tests
prüfen Vergleichszweck, Teilstatus, veraltete Prüfungen und Links zu Originalantworten.
Legacy-Reasoning und die Reasoning-Ebene im Chatmodell-Picker bleiben abgedeckt.
`tests/e2e/test_agent_status_frontend.py` prüft die gebaute App mit offenem SSE-
Stream bei 1280/390/320 px: Schritt-Reihenfolge, laufende/eingefrorene Uhr,
Absatzabstände, dezente Absatzfarben und kontrastreiche Schritte im hellen/dunklen
Modus, Abschluss mit geöffnetem Verlauf, Aufklappen per Tastatur und vollständigen
Verlauf ohne inneren Scrollkasten.
Sie öffnet den Verlauf auch während des ersten „Thinking…“ und lädt einen
abgeschlossenen Turn erneut. `test_agent_comparison_frontend.py` prüft die
zusätzlichen Details und Leser-Links live, gespeichert und in archivierten Turns,
auch bei leerer `agent_activity` und vorhandenem Review. Auf Desktop und Mobil
prüft sie außerdem den echten Modellpicker: 0/1 Modelle sperren Senden, Entwurf
und Netzwerk bleiben bei Enter/direktem Aufruf unverändert; zwei Modelle geben
Senden wieder frei.
Der Lauf prüft zudem kurze Ein-/Ausblend- und Höhenübergänge, einmalige Animation
pro neuem Absatz/Antwortbeginn, schnelle Richtungswechsel, Abschluss bei offenem
und geschlossenem Verlauf sowie Reduced Motion und Forced Colors ohne Bewegung.
Wie die Agent-Chat-Suite nutzt sie den writerfreien Phase-4-Server, gemockte APIs
und keine bezahlten Modellaufrufe; Screenshots über `AGENT_SCREENSHOTS`.
Zusätzlich: aktualisierte Kontingente bei SSE-Fehlern/Disconnect, veraltete und
fremde Snapshots sowie Tool-Nennungen gegenüber bestätigten Aufrufen.
Agentenleiste: `agent-delegation.test.mjs` prüft gemessene Tokenzahlen (ohne
Doppelzählung), sofortige Judge-Details ohne weitere Requests und Skeleton/
Cache für Worker. `test_agent_delegation_frontend.py` prüft diese Abläufe mit
gedrosseltem Detailabruf, sanfter Öffnung und Reduced Motion auf Desktop/Mobil.
`test_agent_progress.py` prüft außerdem den gedrosselten Unicode-Zeichenzähler,
gemeldete Token-Snapshots, unveränderte Abrechnung und fehlende zusätzliche
Journaleinträge. `agent-delegation.test.mjs` prüft monotone, turngebundene
Live-Zähler und den Wechsel zu gemessenen Tokens; `agent-chat.test.mjs` verwirft
späte Fortschrittsereignisse nach Stop. Der Browserlauf sendet die Ereignisse
durch einen offenen SSE-Stream und prüft Schimmer, Zeichenzähler, Tokenwechsel,
Abschluss sowie Reduced Motion/Forced Colors bei 1440/390/320 px.
Budget/Recovery: `test_agent_budget_config.py` prüft Adminrechte, strikte Limits,
Revisionen, Cache und Reset ohne Nutzer-Scan. `test_agent_comparison.py` prüft
Reset während laufender Calls und Migration ungenutzter Prüfreserven;
`agent-chat.test.mjs` prüft deduplizierte Recovery ohne neue Run-Einträge sowie
veraltete Budgetgenerationen. Sidebar-Tests trennen Reserven vom Prozentverbrauch
und prüfen SSE statt Vollpolling. `test_admin_agent_budget.py` prüft Speichern/
Reset im echten Admin-Frontend auf Desktop und 390/320px.
`test_agent_comparison.py` injiziert temporäre Speicherfehler vor und nach dem
Abrechnungs-Commit: kein doppelter Modellaufruf, keine offenen Belege und erhaltene
Modellantworten nach kurzem Ausfall. Bei erschöpften sofortigen Wiederholungen
bleibt die Prüfung als fehlgeschlagen erkennbar, die Abrechnung endet sauber.
`test_analysis_quality_budget.py`
prüft den noch laufenden Coverage-Future bei unbegrenztem Agent-Budget.
`test_agent_continuation.py` prüft gespeicherte Teilantworten im Fehler-SSE und
Recovery einer abgelaufenen Lease bei unveränderter Abrechnung. Der Browserlauf
`test_agent_chat_frontend.py` prüft die direkte Übernahme des Bookmarks aus dem
Fehlerereignis sowie dessen Öffnen nach echtem Reload bei 1280/390 px, auch ohne
Hauptantwort, mit reinen Vergleichsantworten und als später archivierten Fehler.
`test_bookmark_lifecycle_frontend.py` prüft verzögerte Löschungen, sofortiges
Ausblenden, deduplizierte Klicks, Metadaten-Refresh während DELETE, Wiederherstellung
bei 4xx/5xx sowie einmaliges Scrollen beim Öffnen von Agent-/Consensus-Bookmarks.
Die HTTP-Antworten sind vollständig gemockt; der Server bleibt writerfrei.
`chat-scroll.test.mjs` prüft außerdem Leseabbruch, View-/Kontowechsel und den
einmaligen Sprung nach einer gespeicherten Ansicht.
`test_agent_comparison.py` prüft die Zulassung ohne optionale Suche bei zu großer
Suchreserve und verhindert dabei doppelte Calls/Belege. `test_agent_runs.py`
prüft Quote und konkrete Reservierungsfehler in terminalen SSE-Ereignissen.
`model-answer-reader.test.mjs` prüft isolierte Vergleichskontexte,
Grundlagenwechsel, Aktualisierung und Fokus. `tests/e2e/test_agent_comparison_frontend.py`
prüft die gebaute Desktop-/Mobilansicht: zentrale Modell-Icons, rote Textlinks,
Widerspruchskarten, Markdown-Antworten, Quellen, Tastatur, kollisionsfreies
Desktop-Docking, gespeicherte/archivierte Turns und Account-Reset. Wie Phase 4
ohne Emulator ausführbar. Mit `AGENT_SCREENSHOTS=artifacts/agent-evidence-ui`
werden Screenshots geschrieben. Es werden keine echten Modelle aufgerufen.
Der Browserlauf prüft außerdem Quellenverweise in Live-/Vergleichsantworten
sowie gespeicherte Paper-URLs aus einem fehlgeschlagenen Turn auf Desktop und
Mobil: hochgestellte Zahlen, Quellenvorschau per Tastatur, Quellenliste,
unveränderter Markdown und dieselben Verweise im archivierten Verlauf.

Agent Beta: Backend-Verträge in `tests/test_agent_runs.py` und
`tests/test_agent_loop.py` (gemeinsame Websuche aller angebotenen Modelle, Schrittbudgets, Tool-Schemas, Abbruch
und Teilabrechnung) sowie `tests/test_agent_search.py` (Provider-Gesamtkosten,
Cache-Writes, geteilte Usage-Chunks, HTTP-/SSE-429 und Wartefristen). Browser-State in
`tests/js/agent-chat.test.mjs`. Der isolierte Layout-/Bookmark-Browserlauf
`tests/e2e/test_agent_chat_frontend.py` nutzt dieselben vollständig gemockten
APIs und den writerfreien Server wie die Phase-4-Suite (siehe E2E-README).
Er prüft auch die Haiku-Wahl vor der ersten Nachricht, rechtsbündige Fragen,
fehlende Statusstriche und Kostenanzeigen. Er benötigt keinen laufenden
Emulator und ruft kein reales Modell auf.

`tests/test_agent_model_catalog.py` prüft neue und entfernte Admin-DB-Einträge,
deren Reihenfolge, dynamische Preise/Reasoning, die Annahme neuer Modell-IDs und
Replay ohne erneuten Konfigurationsabruf. Auch Cache-Bündelung, Rückfall bei
Providerfehlern und ungültige Metadaten sind abgedeckt. Der Picker-Browsertest
`test_all_pro_chat_models_are_grouped_by_provider` kann über
`AGENT_CATALOG_FIXTURE=<JSON-Pfad>` einen zuvor rein lesend erzeugten
`agent_model_options()`-Snapshot der echten Admin-DB verwenden. Er prüft sämtliche
Einträge in ihrer Reihenfolge und deaktivierte, nicht auflösbare IDs auf Desktop
und Mobil. `AGENT_SCREENSHOTS=<Verzeichnis>` speichert die Ansichten.

`tests/test_agent_contradictions.py` prüft Tool-Freigabe, Originalbelege,
getrennte Modell-/Quellenurteile, Primär-/Fallback-Abrechnung, Versionsbindung,
Abbruch und Wiederholung/Recovery ohne zusätzlichen Quellen-Judge. Die Agent-Frontend-Tests prüfen
zusätzlich eingefrorene Einstellungen, die Startleiste und die Reasoning-Verknüpfung.
`tests/e2e/test_agent_comparison_frontend.py` prüft den einzeiligen Composer nach
dem Senden und bei gespeicherten Chats, das (+)-Menü per Touch mit Quellenprüfung,
Reasoning und Compare sowie Quellenbelege an Widerspruchskarten auf Desktop und Mobil.
Die Transaktionsprüfung `tests/e2e/test_agent_transactions.py` prüft mit
`dev.ps1 check browser -TestPath tests/e2e/test_agent_transactions.py` auch
mehrere bezahlte Schritte innerhalb desselben Owner-Slots im lokalen Emulator.

```powershell
venv\Scripts\python.exe -m pytest tests -q
```

`tests/conftest.py` schließt `tests/e2e/` aus, solange `RUN_E2E` nicht exakt
`1` ist, und aktiviert für die reguläre Suite `UNIT_TEST_MODE=1`. Dadurch wird
Firebase Admin mit anonymen Credentials und dem nicht produktiven Demo-Projekt
`demo-consensio-unit` an einem geschlossenen Loopback-Port initialisiert; ein
vergessener Fake kann dadurch keinen externen Dienst erreichen. Alle fachlichen
Datenzugriffe verwenden weiterhin die jeweiligen In-Memory-Fakes. Unit-/
Integrationstests dürfen daher keine Browserinstallation, Firebase-Credentials
oder externen Dienste voraussetzen.

Die Laufzeitstabilitäts-Verträge sind zusätzlich gezielt prüfbar:

```powershell
venv\Scripts\python.exe -m pytest tests\test_router_event_loop_contract.py tests\test_provider_timeouts.py tests\test_streaming.py tests\test_background_task_supervision.py -q
```

Sie prüfen Threadpool-Parallelität für blockierende Router, zentrale effektive
Provider-Budgets ohne SDK-Retries, das Schließen von Streams bei Disconnect und
Supervisor-Restart/Health/Alerting. Der Retention-Paginationstest liegt in
`tests/test_share_feature.py`.

Die Phase-5-Betriebs- und Abuse-Verträge sind gebündelt prüfbar:

```powershell
venv\Scripts\python.exe -m pytest tests\test_phase5_operations.py tests\test_bookmarks.py tests\test_watch_feature.py tests\test_account_deletion_retry.py -q
```

Sie decken persistente Bookmark-/Feedback-Quoten, run-gebundene genau-einmalige
Votes, Double-Opt-in-Budgets, Favicon-Singleflight/LRU, Correlation/Metriken,
indexierte Fälligkeitsabfragen, Admin-Pagination, Account-Cleanup und die
Frontend-`result_id`-Bindung ab.

Reine Quelltextverträge tragen den Marker `source_contract`. Sie laufen in der
regulären Suite mit, gelten aber nicht als Ersatz für Browserverhalten. Eine
gezielte Bestandsaufnahme ist möglich mit:

```powershell
venv\Scripts\python.exe -m pytest -m source_contract -q
```

Kritische Verträge aus `test_agent_mode_ui.py` und
`test_frontend_resilience.py` haben korrespondierende Playwright-Flows für
Disclosure/Agent Mode, Streaming-Degradation und die App-Shell. Der Cache-
Vertrag inventarisiert dagegen bewusst alle aktiven lokalen JS-/CSS-URLs,
prüft ein einheitliches `?v=YYYYMMDD-label` je Asset und vergleicht das Datum
mit dem letzten Git-Commit beziehungsweise einer aktuellen Arbeitsbaumänderung.

## Browser-E2E

`tests/e2e/test_browser_failure_recovery.py` nutzt den writerfreien Phase-4-Server
mit gemocktem Firebase und APIs. Es prüft lokal ausgelieferte Markdown-/Math-
Abhängigkeiten bei blockiertem jsDelivr sowie abgelehnte Login-/Vote-/Refresh-
Tokens. Der Lauf erfolgt wie Phase 4 direkt mit `RUN_E2E=1` ohne Emulator.

Die E2E-Suite ist ein separater Lauf und benötigt den Firestore-Emulator. Sie
darf nie durch beliebige Credentials oder ein Firebase-Standardprojekt ersetzt
werden. Vollständiges Setup, Writer-Inventar und Befehle:
[`tests/e2e/README.md`](../tests/e2e/README.md).

Die vollständig gemockten Phase-4-Frontend-Races sind separat ohne Java/
Firestore-Emulator ausführbar (weiterhin `RUN_E2E=1`, writerfreies E2E-Profil):

```powershell
$env:RUN_E2E = "1"
venv\Scripts\python.exe -m pytest tests\e2e\test_phase4_frontend.py -q
Remove-Item Env:RUN_E2E
```

## CI

Ein allgemeiner GitHub-Actions-Workflow für die reguläre Suite,
JavaScript-Tests, Frontend-Build und Emulator-E2E-Suite ist nicht vorhanden;
insbesondere ist `.github/workflows/tests.yml` entfernt. Diese Prüfungen werden
lokal mit den Befehlen in diesem Dokument ausgeführt.

Die Standalone-Publishertests bilden eine Ausnahme:
[`publisher-tests.yml`](../.github/workflows/publisher-tests.yml) führt sie bei
Push auf `main`, Pull Requests und manueller Auslösung aus.
[`publish-consensus.yml`](../.github/workflows/publish-consensus.yml) führt
dieselben Tests vor dem produktiven Publisher-Lauf aus. Sie gehören ebenfalls
zum regulären Testbestand und sind keine zusätzliche Testdateimenge.

Tests dürfen weiterhin nicht still von der lokalen `.env` abhängen; nötige
Environment-Variablen im Test selbst setzen (`monkeypatch.setenv`) statt sie
vorauszusetzen.

Für manuelle Frontend-QA bleibt [`smoke-checklist.md`](smoke-checklist.md)
verbindlich.

# Tests und sichere Ausführung

## Gemeinsamer Einstieg unter Windows

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

`.\dev.ps1 help` zeigt die Kurzreferenz. Das Skript installiert keine Pakete und
verändert keine Builds. Fehlende Voraussetzungen werden mit einem Setup-Hinweis
gemeldet. Für Browserprüfungen braucht es zusätzlich die unten beschriebenen
E2E-Abhängigkeiten, Chromium, Firebase CLI und Java 21+ auf `PATH` oder unter
`JAVA_HOME`. Der erste Emulatorstart kann den von der CLI benötigten Emulator
herunterladen; Browser-Flows benötigen weiterhin die dokumentierten CDN-Assets.

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

Für Tests existiert bewusst kein GitHub-Actions-Workflow. Insbesondere ist
`.github/workflows/tests.yml` entfernt, damit Pushes keine Test-Runs oder
Fehlermails auslösen. Reguläre Suite, JavaScript-Tests, Frontend-Build und bei
Bedarf die Emulator-E2E-Suite werden ausschließlich lokal mit den Befehlen in
diesem Dokument ausgeführt. Die verbliebenen GitHub-Workflows sind
Betriebs-Automationen und keine Test-CI.

Tests dürfen weiterhin nicht still von der lokalen `.env` abhängen; nötige
Environment-Variablen im Test selbst setzen (`monkeypatch.setenv`) statt sie
vorauszusetzen.

Für manuelle Frontend-QA bleibt [`smoke-checklist.md`](smoke-checklist.md)
verbindlich.

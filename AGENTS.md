# Agent-Hinweise

## Zusammenarbeit

- Der Nutzer wünscht eine stärkere eigene, begründete Meinung: klare Empfehlungen
  aussprechen, Annahmen kritisch prüfen und bei guten Gründen widersprechen.
  Nicht bloß zustimmen oder die Position bei jedem Einwand wechseln; sie anhand
  von Evidenz und den Zielen des Nutzers überprüfen und Änderungen begründen.

## Features eigenständig liefern und integrieren

- Einzelne Feature-/Umsetzungsaufträge ohne parallele Arbeit standardmäßig
  direkt auf `main` im bestehenden Checkout erledigen, einschließlich passender
  Tests/Builds und Dokumentation. Dafür nicht eigens Branch, Worktree oder PR
  anlegen. Einen bestehenden abweichenden Arbeitskontext nicht blind auf `main`
  umstellen; laufende Arbeit und uncommittete Änderungen zuerst berücksichtigen.
- Wenn der Nutzer ausdrücklich einen PR verlangt oder mehrere Aufgaben am
  Projekt parallel bearbeitet werden, pro Aufgabe einen eigenen Branch und
  Worktree verwenden. Dieser Ablauf umfasst Commit, Push, PR und Merge in den
  vorgesehenen Zielbranch und ist vom Nutzer autorisiert. Nicht erneut nach
  routinemäßiger Freigabe oder manueller Orchestrierung fragen. Explizite
  Einschränkungen im jeweiligen Auftrag (z. B. „nur Entwurf“, „nicht mergen“)
  gehen vor.
- Vor Änderungen den Arbeitskontext und relevante laufende Tasks prüfen, um
  parallele Arbeit zu erkennen. Im PR-/Parallelbetrieb auch offene PRs prüfen
  und Abhängigkeiten, Überschneidungen sowie die Merge-Reihenfolge eigenständig
  abstimmen. Verfügbare Task-Werkzeuge zum Lesen und Koordinieren dieser Arbeit
  verwenden. Keine fremden uncommitteten Änderungen überschreiben oder mitcommitten.
- Im PR-/Parallelbetrieb die eigene Änderung bis zur Integration begleiten:
  aktuellen Zielbranch
  einbeziehen, Konflikte unter Erhalt der beteiligten Features lösen, das
  kombinierte Ergebnis prüfen und erforderliche CI-/Branch-Regeln einhalten.
  Bei zwischenzeitlichen Zielbranch-Änderungen betroffene Prüfungen wiederholen.
  Keine Schutzregeln umgehen und keine unbeteiligten PRs pauschal mergen.
- **Deploys nur auf Ansage:** Nach Commit, Push oder Merge nicht von selbst
  nach Prod (Render) deployen. Nur deployen, wenn der Nutzer es in der
  laufenden Session ausdrücklich verlangt; eine Freigabe aus einer früheren
  Session oder Aufgabe gilt nicht. Im Abschluss stattdessen sagen, dass die
  Änderung auf `main` liegt, aber noch nicht live ist.
- **CI nach jedem Push prüfen, ohne darauf zu warten:** Ein rotes `main` bremst
  alle folgenden Sessions, und die verursachende Session kennt den Fehler am
  besten. Nach jedem Push auf `main` deshalb
  `venv/Scripts/python.exe scripts/ci_status.py --wait` im Hintergrund starten
  und den Auftrag trotzdem sofort abschließen; der Nutzer wartet nicht auf die
  CI. Meldet sich der Hintergrundlauf grün (Exit 0), nichts dazu sagen. Meldet
  er rot (Exit 1), reparieren: veraltete Tests an gewolltes Verhalten anpassen,
  echte Fehler im Code beheben, wackelige (zeitabhängige) Tests
  deterministisch machen statt sie erneut anzustoßen. Vor UI-Änderungen geänderte Texte, IDs und Selektoren
  in `tests/e2e` suchen und die Treffer mitziehen, denn die Browser-Suite läuft
  nur nachts. Was dort rot wird, repariert der tägliche CI-Wächter (geplante
  Aufgabe `consens-ci-watch`).
- Nur bei fehlenden Zugängen, einem nicht eigenständig lösbaren Blocker oder
  einer wesentlichen ungeklärten Produktentscheidung den Nutzer einbeziehen.
  Abschluss mit tatsächlicher Validierung und gegebenenfalls PR-/Merge-Status berichten;
  unvollständige Integration ausdrücklich benennen.
- Nach jedem Merge auf `main` den lokalen Checkout des Nutzers aktualisieren:
  steht eine Shell auf seinem Rechner zur Verfügung, dort `.\dev.ps1 update`
  selbst ausführen und das Ergebnis berichten; sonst den Befehl als einzigen
  nötigen Schritt nennen (installiert geänderte Abhängigkeiten, ein laufender
  `uvicorn --reload` lädt neu).

## Codebase

**Gezielt nachschlagen:** [`docs/codebase-map.md`](docs/codebase-map.md) ist die
Architektur-Referenz für Stack, Routing, Module, Kern-Flows, Daten und kritische
`window.*`/DOM-Verträge. Bei unbekannten Abläufen und übergreifenden Änderungen
die relevanten Abschnitte über Überschriften oder Suche finden und lesen;
weitere Abschnitte bei erkennbaren Abhängigkeiten nachladen. Für klar begrenzte
Text-, Stil- oder Dokumentationskorrekturen genügt der betroffene Kontext.

**Pflicht:** Wenn du **Architektur, Module, API-Endpoints oder Kern-Flows**
änderst, dokumentiere das im selben Commit/PR in `docs/codebase-map.md` mit
(siehe Abschnitt „Bei Änderungen aktualisieren" dort). Die Karte muss zum Code
passen — bei Abweichung gilt der Code, und die Karte wird korrigiert.

**Schnell-Hinweise:**
- Frontend-Module reden über `window.*` / `window.App` (keine ES-Imports). Die
  Script-Ladereihenfolge ist ein Vertrag — für `/app` steht sie in
  `static/js/bundles.json`, nicht mehr in `templates/index.html`.
- **Deutsch:** Jeder sichtbare englische Text hat eine deutsche Fassung in
  `app/i18n/de/*.json` ([`docs/i18n.md`](docs/i18n.md)). Wer Text ändert oder
  hinzufügt, trägt sie im selben Commit ein; `venv/Scripts/python.exe
  scripts/i18n.py missing` listet die Lücken, `tests/test_i18n.py` bricht sonst
  ab. Skripte nie gegen sichtbaren Text vergleichen (`window.App.t(text)`),
  Einzahl/Mehrzahl als ganze Sätze.
- Nach Änderungen unter `static/` für `/app`: `npm run build` (Marke kommt aus
  dem Inhalt, es gibt dort nichts mehr von Hand zu bumpen) — Details in
  [`docs/frontend-build.md`](docs/frontend-build.md). Öffentliche Seiten und
  `admin.html` binden Assets über `{{ asset_url('/static/...') }}` (Inhalts-Hash
  inkl. verschachtelter Imports); handgeschriebene `?v=`-Marken gibt es nirgends
  mehr, ein Test verbietet sie.
- Windows-Einstieg für Tests: `.\dev.ps1 check frontend|backend|browser`,
  optional `-TestPath <Datei oder Verzeichnis>`; direkte Runner-Befehle und Setup
  stehen in `docs/testing.md`. Bei Änderungen an Test-/Build-Einstiegspunkten
  oder Voraussetzungen `dev.ps1` und die zugehörige Dokumentation im selben
  Auftrag mitpflegen. Prüfumfang nach betroffenem Verhalten und Risiko wählen;
  vollständige Suiten bei übergreifenden Änderungen oder vorgeschriebenen Checks.
  Nach erfolgreichen Prüfungen nur bei weiteren Änderungen, Fehlern oder
  konkreten offenen Risiken erneut oder breiter testen.
- **Laufzeitbudget:** Die vollständige Browser-Suite (`tests/e2e`, gemessen
  ca. 6–12 s pro Fall, bei über 300 Fällen 1 Stunde und mehr) wird lokal
  **nicht** nach einer Implementierung gestartet. Stattdessen nur die Dateien
  zum geänderten Verhalten (`-TestPath tests/e2e/<datei>`, meist 1–3 Dateien),
  dazu `frontend` (Sekunden) und bei Backend-Änderungen die betroffenen
  Backend-Dateien statt aller. Der Gesamtlauf dauert 6–10 min, während
  andere Sessions arbeiten länger, und bremst sie alle (4 Kerne); die CI
  führt ihn bei jedem Push ohnehin aus. Lokal deshalb nur bei übergreifenden
  Änderungen (Abhängigkeiten, Python-Version, `conftest.py`, gemeinsame
  Kern-Infrastruktur). Die volle Browser-Suite
  läuft in der CI (`workflow_dispatch` → `browser-and-rules`) und nur lokal,
  wenn der Nutzer sie ausdrücklich verlangt. Browser- und Rules-Läufe nur über
  `dev.ps1` starten: Es reiht sie rechnerweit ein (feste Ports
  8085/8031/8033) und meldet, hinter wem sie warten. Im Hintergrund starten
  und abwarten; kein direktes `emulators:exec`/`pytest tests/e2e`, keinen
  Lauf „nochmal“ anstoßen, keine fremden Prozesse beenden. Für Verhalten ohne
  Auto-Tests die betroffenen Punkte in `docs/smoke-checklist.md` prüfen;
  reine Dokumentationskorrekturen auf Inhalt, Links und Diff prüfen.

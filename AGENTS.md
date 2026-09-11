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
- Nur bei fehlenden Zugängen, einem nicht eigenständig lösbaren Blocker oder
  einer wesentlichen ungeklärten Produktentscheidung den Nutzer einbeziehen.
  Abschluss mit tatsächlicher Validierung und gegebenenfalls PR-/Merge-Status berichten;
  unvollständige Integration ausdrücklich benennen.

## Codebase

**Erst lesen:** [`docs/codebase-map.md`](docs/codebase-map.md) — kompakte
Architektur-Karte (Stack, Routing, Frontend-Module, Kern-Flows, Backend, Daten,
kritische `window.*`/DOM-Verträge, lokale Befehle).

**Pflicht:** Wenn du **Architektur, Module, API-Endpoints oder Kern-Flows**
änderst, dokumentiere das im selben Commit/PR in `docs/codebase-map.md` mit
(siehe Abschnitt „Bei Änderungen aktualisieren" dort). Die Karte muss zum Code
passen — bei Abweichung gilt der Code, und die Karte wird korrigiert.

**Schnell-Hinweise:**
- Frontend-Module reden über `window.*` / `window.App` (keine ES-Imports). Die
  Script-Ladereihenfolge ist ein Vertrag — für `/app` steht sie in
  `static/js/bundles.json`, nicht mehr in `templates/index.html`.
- Nach Änderungen unter `static/` für `/app`: `npm run build` (Marke kommt aus
  dem Inhalt, es gibt dort nichts mehr von Hand zu bumpen) — Details in
  [`docs/frontend-build.md`](docs/frontend-build.md). Die öffentlichen Seiten
  und `admin.html` hängen weiter am manuellen `?v=`-Buster.
- Tests: `npm test` (JS-Verhalten, Vitest + jsdom) und
  `.\venv\Scripts\python.exe -m pytest tests`. Für alles, was noch keine
  Auto-Tests hat, `docs/smoke-checklist.md` durchgehen.

# Frontend-Build & JS-Tests

Betrifft **`/app`** (`templates/index.html`). Die öffentlichen Seiten
(`landing.html`, `share.html`, `topic.html`, …) hängen weiterhin am manuellen
`?v=`-Regime — siehe „Noch offen“ unten.

## Warum

Vorher lud `/app` **36 einzelne JS-Dateien (872 KB)**, deren Reihenfolge in
`index.html` beziehungsweise einem lokalen ESM-Import stand, und jede Datei
trug eine **von Hand
gepflegte `?v=`-Marke**. Vergaß man den Bump, bekamen wiederkehrende Nutzer
altes JS/CSS. Automatische Frontend-Tests gab es keine; die Absicherung waren
Python-Tests, die den JS-Quelltext nach Teilstrings durchsuchten.

Jetzt: **5 gehashte Bundles (419 KB)**, Reihenfolge in einer Datei, Marke aus dem
Inhalt, plus ein echter JS-Test-Runner.

## Befehle

Unter Windows führt `.\dev.ps1 check frontend` die JS-Tests und anschließend
den Build-Abgleich aus; `-TestPath tests/js/<datei>.test.mjs` begrenzt die Tests.
Setup und weitere Prüfziele: [`testing.md`](testing.md).

```bash
npm install
```

```bash
npm run build
```

```bash
npm test
```

`npm run build:check` prüft nur, ob `static/dist/` zu den Quellen passt (Exit 1,
wenn nicht). Denselben Abgleich macht `tests/test_frontend_build.py` im
normalen pytest-Lauf, ohne Node.

Der Größenvergleich in `tests/test_frontend_build.py` normalisiert CRLF auf LF,
damit Windows und Linux dieselben Werte prüfen. Die JS-Bundles müssen mindestens
45 % kleiner als ihre Quellen sein; der bestehende LF-Stand liegt bei rund 49 %
Ersparnis. Der Spielraum berücksichtigt UI-Texte, die beim Minifizieren erhalten
bleiben. Request-Anzahl und öffentliche `window.*`-Verträge werden separat geprüft.

## Lokalen Backend-Stand prüfen

Ein neuer Frontend-Build lädt Python-Module eines laufenden Uvicorn-Workers nicht
neu. Auch mit `--reload` kann ein hängen gebliebener lokaler Watcher neue Dateien
übersehen. Wenn neue Assets zusammen mit altem API-Verhalten auftreten, den
Build-Commit in der App mit `git rev-parse --short HEAD` und die Startzeit des
Python-Workers mit den Änderungen vergleichen. Den zugehörigen lokalen Server
anschließend vollständig neu starten und einen **neuen** Lauf prüfen.
Ein neu geladener alter Bookmark bleibt weiterhin ein historisches Ergebnis.
Ein Cache-Reload im Browser allein behebt veraltete Backend-Module nicht.

## Wie es zusammenhängt

```
static/js/bundles.json      Ladereihenfolge (die EINE Quelle der Wahrheit)
        │
        ├── scripts/build_frontend.mjs   →  static/dist/*.js|css + manifest.json
        │
        └── app/core/assets.py           →  die <script>/<link>-Tags für Jinja
```

**`static/js/bundles.json`** listet die Gruppen in Ladereihenfolge. Ein neues
Skript wird **nur hier** eingetragen — nicht mehr in `index.html`. Notizen zu
Reihenfolge-Zwängen stehen als `note` neben der Datei.

**Der Build** hängt die Dateien jeder Klassik-Gruppe in genau dieser Reihenfolge
aneinander und minifiziert das Ergebnis. Bewusst **Verkettung statt
Modul-Bundling**: die Dateien teilen einen globalen Scope und reden über ~85
`window.*`-Verträge miteinander. In Modul-Scopes gewickelt wäre jede implizite
Globale still weg. esbuild läuft deshalb ohne `--bundle`/`--format`, damit
Top-Level-Namen unangetastet bleiben; `tests/test_frontend_build.py` prüft das
nach. Zwischen zwei Dateien steht ein `;` als ASI-Schutz.

`firebase.js` und `demo.js` sind echte ES-Module und werden einzeln gebündelt
(Firebase-SDK bleibt externer CDN-Import).

Die vorherigen jsDelivr-Abhängigkeiten von `/app` (Marked, DOMPurify, KaTeX)
werden aus `static/vendor/<paket>/<version>/` lokal ausgeliefert. Der Build
kopiert über `scripts/vendor_frontend.mjs` die exakt in `package.json` gepinnten
npm-Dateien samt Lizenzen und KaTeX-Fonts; `build:check` vergleicht deren Bytes.
Unveränderte Vendor-Dateien werden nicht erneut geöffnet/überschrieben; geänderte
Dateien werden über eine temporäre Datei im selben Verzeichnis atomar ersetzt.
Die Dateien sind mitcommittet und im Manifest-Fingerprint enthalten, sodass
Produktion weiterhin kein Node benötigt. Bei Versionsupdates auch die Pfade
in `templates/index.html` anpassen. `asset_url` ergänzt Inhalts-Hashes.

CSS: `style.css` ist ein `@import`-Aggregator. Der Build zieht die Kette in
Kaskadenreihenfolge in **eine** Datei. `static/dist/` liegt neben `static/css/`,
deshalb zeigen `url(../fonts/…)` und `url(../icons/…)` weiter auf dieselben
Dateien.

**`app/core/assets.py`** rendert daraus die Tags. Zwei Modi:

| | wann | Ergebnis |
|---|---|---|
| **built** | `static/dist/manifest.json` liegt vor | 5 gehashte Bundles |
| **source** | kein Build-Output **oder** `FRONTEND_DEV=1` | 36 Einzeldateien, jede mit Inhalts-Hash |

Der Source-Modus ist der Entwicklungspfad: Datei speichern, neu laden, fertig —
kein Build, kein Bump. Launch-Config dafür: `consensio-mock-dev` (Port 8035).

Auch lokale Abhängigkeiten müssen direkt in `bundles.json` stehen. Deshalb ist
`email-verify.js` Teil der `head`-Gruppe und stellt
`window.App.emailVerification` bereit, statt hinter einem zweiten, unbemerkt
veraltbaren ESM-Import zu liegen. Der Build schreibt außerdem seine vollständige
Input-Liste ins Manifest; der Python-Abgleich hasht diese Liste samt
`bundles.json`, Build-Skript und Lockfile.
Text-Inputs außerhalb von `static/vendor/` werden für den Fingerprint auf
LF-Zeilenenden normalisiert, damit Windows-CRLF und Linux-Checkouts denselben
Build erkennen. Vendor-Dateien einschließlich Fonts bleiben bytegenau geprüft.

## Deploy

`static/dist/` wird **mitcommittet**, damit der Render-Deploy kein Node braucht.
Nach jeder Änderung an `static/` also `npm run build` und das Ergebnis mit
committen. Fehlt es, fällt `assets.py` automatisch auf die Einzeldateien zurück
— die App läuft, nur eben unminifiziert.

`scripts/frontend-output.mjs` veröffentlicht vollständige JS-/CSS-Dateien vor
dem atomaren Manifestwechsel. Erst danach werden alte Bundles bereinigt;
`previous_assets` im Manifest hält je JS-/CSS-Gruppe die letzten zwei
Vorgängerversionen vor, auch bei identischen Rebuilds. Diese Dateien ebenfalls
mitcommitten: Sie überbrücken verspätete Asset-Requests beim Versionswechsel.
Das ist ein begrenztes Übergangsfenster, keine dauerhafte Archivierung alter
Deployments. `/app` und `/app/watches` liefern ihr HTML mit `private, no-store`.
Die Node-Regressionstests `tests/js/frontend-output.test.mjs` laufen im normalen
`dev.ps1 check frontend`; keine zusätzlichen Voraussetzungen.

Alternative, falls das Diff-Rauschen stört: `static/dist/` ignorieren und im
Render-Build-Command `npm ci && npm run build` ergänzen.

## JS-Tests

`tests/js/*.test.mjs`, Vitest + jsdom. Die Module sind keine ES-Module und
lassen sich nicht importieren, deshalb lädt `tests/js/helpers/appWindow.mjs` sie
als `<script>` in ein frisches jsdom — genau wie der Browser:

```js
const { window } = loadScripts(["static/js/composer-quote.js"], { body: MARKUP });
window.App.quote.set("…");
```

Jeder Aufruf bekommt ein eigenes Fenster, damit ein Modul, das Listener bindet
oder Globals einfriert, nicht ins nächste Testfile leckt.

Abgedeckt: `app-state.js` (Owner-Enforcement), `composer-quote.js`,
`consensus-anchor.js`. Der erste Lauf hat direkt einen echten Mangel gefunden —
`Object.freeze` auf der Owner-Tabelle war flach, jedes Skript konnte einen Owner
umschreiben und danach vorn herein schreiben. Behoben in `app-state.js`.

## Noch offen

- Die öffentlichen Seiten (`landing.html`, `share.html`, `topic.html`,
  `topics.html`, `questions.html`, `benchmark.html`, `consensus-engine.html`,
  `model-pulse.html`, `about/terms/privacy/imprint`) sowie `admin.html` laufen
  weiter mit handgepflegten `?v=`-Marken. Der Vertrag dafür ist unverändert und
  wird von `tests/test_frontend_resilience.py` durchgesetzt.
- Die verbleibenden Python-Quelltext-Verträge (`source_contract` und die
  Teilstring-Prüfungen in `test_*_ui.py`) sind weiter da. Sie sollten Stück für
  Stück nach `tests/js/` wandern, wo sie Verhalten statt Schreibweise prüfen.

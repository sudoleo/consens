# Frontend-Build & JS-Tests

Betrifft **`/app`** (`templates/index.html`). Die öffentlichen Seiten und
`admin.html` nutzen seit 2026-10-04 `asset_url()` — siehe „Öffentliche Seiten“
unten. Handgepflegte `?v=`-Marken gibt es nirgends mehr.

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
in `templates/index.html`, die Asset-Allowlists in `static/js/error-reporter.js`
und `app/api/routers/client_errors.py` sowie die jsDelivr-Verweise der
öffentlichen Seiten (`share.html`, `topic.html`) anpassen und das alte
Vendor-Verzeichnis entfernen. `tests/js/dompurify-vendor.test.mjs` liest die
DOMPurify-Version aus `package.json` und prüft den ausgelieferten Pfad.
`asset_url` ergänzt Inhalts-Hashes.

**Source-Maps.** Jedes JS-Bundle bekommt eine externe Map
`static/dist/<name>.<hash>.js.map` (ohne `sourcesContent`, ohne `names`, ohne
`sourceMappingURL`-Kommentar im Bundle — der Dateinamen-Hash bleibt ein Hash der
ausgelieferten Bytes). Für Klassik-Gruppen zeigt esbuilds Map zunächst in die
Verkettung; `scripts/frontend-sourcemaps.mjs` schreibt sie auf die echten Dateien
um (`sources` = `static/js/<datei>.js`). Zweck sind die Browser-Fehler-Alerts:
`app/core/sourcemaps.py` löst damit `app.<hash>.js:1:<spalte>` auf die Quellzeile
auf ([`error-alerts.md`](error-alerts.md)). Die Maps verraten nichts Neues — die
unminifizierten Quellen unter `static/js` sind ohnehin öffentlich. Sie werden mit
ihrem Bundle veröffentlicht, mitcommittet und zusammen mit ihm bereinigt
(`frontend-output.mjs`); `build:check` vergleicht auch sie.

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
Die erzeugten Dateien unter `static/dist/` einschließlich `manifest.json`
werden über `.gitattributes` mit `-text` ebenfalls bytegenau ein- und ausgecheckt.
Git darf ihre Zeilenenden auch bei `core.autocrlf=true` nicht verändern: Sonst
weichen die ausgelieferten Bytes vom Dateinamen-Hash und vom Build-Abgleich ab.
Bereits konvertierte lokale Artefakte lassen sich mit `npm run build` neu erzeugen.

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
`dev.ps1 check frontend`. Der Checkoutfall benötigt das im Projekt ohnehin
verwendete Git: Ein temporäres Repository prüft mit `core.autocrlf=true`
Manifestbytes, JS-/CSS-Bytes und deren Dateinamen-Hashes. Eine ungeschützte
Textdatei dient als CRLF-Gegenkontrolle; globale Git-Einstellungen bleiben unberührt.

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

## Öffentliche Seiten und Admin

Templates außerhalb von `/app` binden jede lokale Datei als
`{{ asset_url('/static/...') }}` (registriert in `pages.py`, `share.py`,
`topics.py`). `asset_url` hängt `?v=<12 hex>` an, gebildet aus dem Inhalt der
Datei **und** aller lokalen Dateien, die sie per `@import url(...)` bzw.
ES-`import`/`export from`/`import()` transitiv nachlädt. Die verschachtelten
URLs selbst bleiben unversioniert. `StaticDeliveryMiddleware` liefert:

- `static/dist/<name>.<hash>` und URLs mit `?v=<12 hex>`: ein Jahr `immutable`;
- jede andere `/static`-Antwort (verschachtelte Imports, Bilder, alte
  Hand-Marken): `no-cache`, also Revalidierung per ETag (meist 304).

Damit gibt es nichts mehr hochzuzählen, und ein vergessener Bump kann kein
veraltetes CSS mehr ausliefern. `tests/test_frontend_resilience.py` verbietet
handgeschriebene `?v=` und unversionierte CSS/JS-Links in Templates;
`tests/test_frontend_assets.py` prüft, dass eine Änderung tief in der
Import-Kette die Einstiegs-URL ändert; `tests/test_static_delivery.py` prüft
die Cache-Header. Die `?v=`-Marken in `static/style.css` waren ohnehin wirkungslos:
der Build inlined die Imports in `dist/app.<hash>.css`.

## Noch offen

- Die verbleibenden Python-Quelltext-Verträge (`source_contract` und die
  Teilstring-Prüfungen in `test_*_ui.py`) sind weiter da. Sie sollten Stück für
  Stück nach `tests/js/` wandern, wo sie Verhalten statt Schreibweise prüfen.

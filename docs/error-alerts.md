# Kritische Fehler-Alerts (Telegram)

Architektur und Regeln: [`codebase-map.md`](codebase-map.md), Abschnitt
„Kritische Fehler-Alerts (Telegram)“. Diese Seite ist die Anleitung für den
Betreiber.

## Triage a Telegram alert

1. **Den ganzen Alert in Claude Code einfügen**, im Repo-Checkout, etwa mit
   „Finde und behebe diesen Fehler“. Die letzte Zeile `fix-context: …` ist dafür
   gemacht: Sie nennt Commit, Route bzw. Codestelle und die Frames mit
   Repo-Pfaden, also genau die Dateien und Zeilen, die zu öffnen sind.
2. **Auf den Commit achten.** Zeilennummern gelten für `commit=`. Ist `main`
   inzwischen weiter, zuerst `git show <commit>:<pfad>` bzw. `git log
   <commit>..main -- <pfad>` ansehen; vielleicht ist der Fehler schon behoben.
3. **Log-Zeile in Render finden** (nur Server-Alerts): Im Render-Dashboard des
   Dienstes unter *Logs* nach der Correlation-ID suchen, z. B.
   `req-3f9c0a1b2c3d4e5f`. Die passende Zeile lautet
   `… ERROR [corr=req-…] root: Unhandled request exception method=… route=…
   category=… at=<datei:zeile:funktion>`; Zeilen derselben Anfrage davor tragen
   dieselbe `corr`. Bei mehreren Instanzen grenzt `Instance:` ein. Der 500er
   selbst trägt die ID im Header `x-correlation-id`; ein Nutzer-Screenshot aus
   den DevTools reicht also zum Zuordnen.
4. **Wiederholungen einordnen.** `fp=` ist pro Fehlerstelle stabil. Steht
   `(+N similar since last alert)` im Alert, wurden seit der letzten Meldung
   N gleichartige Fälle unterdrückt (Dedup 10 min, Budgets: Server 10, Browser
   5 Alerts je 10 min und Prozess).

## Felder

| Feld | Bedeutung |
|---|---|
| `Source` | `server` oder `browser` |
| `Type` | Server: Exception-Klasse (bei HTTP-artigen Fehlern mit Status), Hintergrund: `background_task_repeated_failure`; Browser: Kategorie (`unhandled_error`, `run_failed`, …) |
| `Environment` | Render-Dienstname bzw. `production`; ohne Render-Variablen `local` (`ENVIRONMENT` übersteuert) |
| `Instance` | `RENDER_INSTANCE_ID` oder Hostname |
| `Commit` | Laufender Build (Kurz-SHA) |
| `Phase` | `request`, `stream` (abgefangener Fehler, Anfrage lief weiter), `background`; Browser: Ablaufphase |
| `Route: GET /x -> 500` | Methode + Routen-Template (keine IDs) und Status; bei Stream-Alerts steht unter `Path` die Codestelle, z. B. `chat.consensus_stream` |
| `Correlation` | ID der Anfrage, identisch mit Log-Zeile und `x-correlation-id` |
| `Bundle` | Browser: laufendes `app.<hash>.js` (identifiziert den Deploy) |
| `Error` | Browser: Fehlername; bei `TypeError`/`ReferenceError`/`RangeError`/`SyntaxError` mit entschärfter Message |
| `Location` | Browser: aufgelöste Quellstelle `static/js/<datei>.js:zeile:spalte` und in Klammern die Bundle-Koordinate |
| `Frames (innermost first)` | Server: Repo-Pfade `datei:zeile:funktion`, Bibliotheken ausgeblendet, max. 8; Browser: aufgelöste Stack-Frames, max. 5 |
| `fix-context` | Kompakte Zusammenfassung zum Einfügen: `fp`, `commit`, `route`, `corr`, ggf. `bundle`/`loc`, `frames=a < b` (a wird von b aufgerufen) |

Bewusst **nicht** enthalten: Exception-Messages von Serverfehlern (können
Fragetext, Modellantworten oder Provider-Bodies tragen), Request-Parameter,
IDs, URLs und Browser-Stacktexte. Wer mehr Kontext braucht, findet ihn über die
Correlation-ID im Log, nicht im Alert.

## Wenn keine Alerts ankommen

- Lokal: Alerts gehen nur mit `TELEGRAM_BOT_TOKEN` in der `.env` raus und sind
  dann als `Environment: local` markiert.
- Ein abgelehnter Versand steht als WARNING im Log:
  `Critical Telegram notification not delivered fp=… status=… description=…`
  (z. B. `Bad Request: chat not found` → `CRITICAL_ERROR_TELEGRAM_CHAT_ID`
  prüfen). Der Slot wird dabei freigegeben, der nächste gleiche Fehler versucht
  es erneut.
- Browser-Orte ohne `static/js/…`: Die `.map` des Bundles fehlt (Build ohne
  Source-Maps oder ein sehr alter, bereits bereinigter Bundle-Hash). Dann bleibt
  nur die Bundle-Koordinate; `npm run build` erzeugt die Maps wieder.

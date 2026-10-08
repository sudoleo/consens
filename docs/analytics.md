# Analytics (Umami): welches Event was bedeutet

Stand 2026-10-08. Tracking-Code: `templates/partials/analytics.html` (Snippet,
Website-ID) und `static/js/analytics-opt-out.js` (Selbst-Ausschluss,
Bot-Filter, Kampagnen-Parameter, `open_app`). App-Events laufen über
`window.trackUmamiEvent` (`static/js/app-bootstrap.js`), das Schlüssel wie
`question`/`email` und Werte mit `@` verwirft. Unter `/app` ersetzt
`consensioBeforeSend` den Seitentitel (dort steht die Frage, `setAppTitle`)
durch „consens.io app“ — Fragetexte gehen nie an Umami.

## Die Kern-Events (für Auswertungen und Funnels)

Diese sechs reichen für fast jede Frage. Sie haben in jedem Modus dieselbe Form.

| Event | Bedeutet | Daten |
|---|---|---|
| `open_app` | Klick von einer öffentlichen Seite in die App | `from` (landing, share, benchmark, model-pulse, …), `place` (welcher Knopf), `demo` |
| `signup` | neues Konto | `method` (google, email) |
| `login` | Anmeldung mit bestehendem Konto | `method` |
| `ask` | eine Frage wurde abgeschickt | `mode` (agent, consensus, compare), `follow_up`, `files`, `reasoning` |
| `answer` | dieser Lauf ist fertig (einmal pro Lauf) | `mode`, `status` (ok, partial, failed) |
| `landing_hero_demo_start` | Demo gestartet | – |

Der Weg zur ersten Frage als Umami-Funnel:
`/` (Seite) → `open_app` → `signup` → `ask`.
Erfolgsquote eines Modus: `answer` mit `status=ok` ÷ `ask` mit demselben `mode`.
Ein vom Nutzer abgebrochener Lauf sendet `ask`, aber kein `answer`; ein vom
Server abgelehnter (Kontingent, belegter Dienst) endet in beiden Modi mit
`answer` `status=failed`. Ein nach abgerissenem Stream wiederhergestellter Lauf
zählt normal mit `ok`/`partial`.

`signup` per E-Mail zählt die angeforderte Einrichtungs-Mail (das Backend
verrät aus Datenschutzgründen nicht, ob die Adresse schon ein Konto hatte).
Google unterscheidet neu/bestehend über die Zeitstempel des Kontos.

## Detail-Events (Diagnose, nicht für Funnels)

Laufen unverändert weiter, damit die Kurven seit Mai 2026 durchgehen:

- `app_query_started` / `app_query_completed` / `app_query_blocked` /
  `app_query_canceled`: nur die alten Pipeline-Läufe (Consensus/Vergleich),
  nicht der Agent. Ausnahme: `app_query_canceled` feuert auch, wenn ein
  Agent-Lauf über den Senden-/Stopp-Knopf abgebrochen wird (gemeinsamer
  Knopf in `query-send.js`). `app_query_completed` fehlt, wenn Consensus automatisch
  startet — dafür gibt es `app_consensus_completed`. Ersetzt durch `ask`/`answer`.
- `app_consensus_started` / `app_consensus_completed`: der Consensus-Schritt
  einer Pipeline (auch manuell nachgestartet).
- `app_consensus_insights_rendered`: Qualitätsmessung der Markierungen
  (wie viele Claims im Text verankert wurden). Feuert bei jedem Anzeigen,
  auch beim Öffnen eines Bookmarks — keine Nutzungszahl.
- `app_new_comparison`: Klick auf „New comparison“.
- `app_memory_hint` (`action`: shown, dismissed) und `app_auto_memory_on`
  (`source: hint` beim Einschalten aus dem Hinweis unter einer Agent-Antwort,
  ohne `source` aus Settings): wie viele den Gedächtnis-Hinweis sehen und annehmen.
- `app_stream_buffered` (seit 2026-10-08, ohne Daten): einmal pro Agent-Lauf,
  wenn das Netz den Antwort-Stream zurückhält (Firmen-Proxy, Virenscanner) und
  die App den Fortschritt stattdessen per Polling holt (`agent-live.js`).
  Zählt, wie viele Läufe ohne diesen Fallback nur „Thinking…“ gezeigt hätten;
  ins Verhältnis zu `ask` mit `mode=agent` setzen.
- `auth_*`: jeder einzelne Anmeldeversuch mit Ergebnis und Fehlercode.
- `landing_*`, `benchmark_*`, `pulse_*`, `consensus_engine_*`, `hub_*`,
  `share_*`, `topic_open`: die einzelnen Knöpfe der öffentlichen Seiten.
  `open_app` fasst die App-Einstiege davon zusammen.

## Seit 2026-10-07 nicht mehr gesendet

`app_bookmark_saved` (feuerte pro gespeicherter Modellantwort, bis zu sieben
Mal pro Frage), `app_sidebar_toggle`, `app_sidebar_section_toggled`,
`app_theme_changed`, `app_account_menu_toggled`. Ihre alten Zahlen bleiben in
Umami lesbar.

## Was nicht in die Zahlen kommt

- **Der Betreiber:** Sobald `/user_status` `is_admin` meldet, setzt die App
  `localStorage['umami.disabled']`. `?notrack=0` schaltet das Gerät bewusst
  wieder ein (und merkt sich das), `?notrack=1` wieder aus.
- **Bots mit Webdriver/Headless-Kennung** senden nichts.
- **Lokale Server**: `data-domains` lässt nur consens.io zu.

Was trotzdem durchkommt: eine Bot-Welle aus Singapur seit Mitte September
2026 (1 Seitenaufruf, 0 Sekunden, kein Webdriver-Flag). In Auswertungen mit
dem Filter `Country ≠ Singapore` arbeiten.

## Kampagnen messen

`data-exclude-search` entfernt die Query aus jeder URL (Token in Mail-Links).
Zurückgeholt werden nur `utm_source`, `utm_medium`, `utm_campaign`,
`utm_content`, `utm_term` und `ref`. Jeder geteilte Link (LinkedIn, HN,
Mails) bekommt deshalb z. B. `?utm_source=linkedin&utm_campaign=post-2026-10-14`;
die LinkedIn-App verschluckt sonst den Referrer und alles landet unter „direct“.

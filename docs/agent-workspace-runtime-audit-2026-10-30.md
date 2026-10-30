# Arbeitsplatz zur Laufzeit: Audit (2026-10-30)

Stand von `main` am 2026-10-30 (b72adcef). Live ist 842ae1c9 vom
2026-10-29 22:41 UTC. Der residente Browser-Helfer (1c1b4a4e) und die neuen
Logzeilen „Agent VM ready …“ und „Agent browser call …“ sind also noch nicht
in Prod.

Grundlage:
- Prod-Messung aller Agent-Turns mit Arbeitsplatz vom 26. bis 30.10. Gelesen
  wurden Turns, Belege, Arbeitsprotokoll, Render-Logs und die Sprites-API (nur
  GET), dazu die OpenRouter-`generation_time` je Schritt. Keine Writes, keine
  Modell-Calls.
- Vier unabhängige Code-Prüfungen: Tempo und Abbrüche, Modell-Interaktion,
  Ansicht und App-Tempo, Kosten. Zwei Frontend-Sonden liefen ohne Server über
  `file://` (150 Schritte gegen `agent-activity.js`, noVNC nachgebaut).

Jeder Befund unten ist am Code nachgeprüft. Was nur vermutet ist, steht so
da. Architektur: [agent-mode.md](agent-mode.md) „Agent VM“, „Arbeitsplatz auf
Abruf“, „Arbeitsplatz“, „Browser-VM“; [codebase-map.md](codebase-map.md)
„Agent VM“. Verwandt: [agent-audit-readiness-2026-10-29.md](agent-audit-readiness-2026-10-29.md)
(Prüfer, Halts, Gate) und
[ux-audit-agent-audit-2026-10-29.md](ux-audit-agent-audit-2026-10-29.md)
(98 UX-Befunde, umgesetzt). Deren Befunde wiederholt dieses Dokument nicht.

## Kurzfassung

- **Die VM bremst nicht, die Zahl der Schritte schon.** Ein Lauf besteht aus
  Schritten: Das Modell denkt (Median 3,0 s), ruft ein Werkzeug auf (Browser
  1,9 s, Befehl 1,4 s) und schickt dafür jedes Mal den ganzen Verlauf neu.
  Modellzeit ist 44 % der Laufzeit, VM und Browser je 16 %. Etwa 30 % der
  Modellzeit ist kein Rechnen beim Anbieter, sondern Weg und Buchung (Median
  0,8 s je Schritt). Die größten Hebel: mehrere Aktionen pro Schritt (heute
  ist es genau eine, T2), Ergebnisse, die keinen Nachschau-Schritt brauchen
  (L2, L4), und ein Zeitgefühl für das Modell (L3).
- **Der Start ist meist schnell, dauert aber manchmal fast eine Minute.**
  Der erste Browser-Aufruf einer Nachricht braucht im Median 5,5 s. Nach einer
  Pause von mehr als 5 min sind es 14,9 s, im Extremfall 59 s. Während das
  Modell nach `open_workspace` noch nachdenkt, passiert auf den VMs nichts
  (T1). Diese Zeit ließe sich fast ganz hinter dem Modellschritt verstecken.
- **Abbrüche: in Prod keiner durch die VM, der Code ist aber zerbrechlich.**
  Ein einziger Verbindungsfehler (Handshake beim Aufwachen, 502, Timeout)
  schaltet Werkbank *und* Browser für den Rest der Nachricht ab (A1). Die
  Sperre auf den Arbeitsplatz wird während langer Wartezeiten nicht
  verlängert (A2). Ein Speicherfehler beim Teilen einer Datei beendet den
  ganzen Lauf (A3). Bei den heutigen Läufen unter 9 min trat das kaum auf. Bei
  Läufen über eine Stunde trifft es fast sicher.
- **Live-Ansicht: am Handy kaum nutzbar.** Nach „Übernehmen“ öffnet sich keine
  Tastatur (V1). Das Bild ist auf ein Viertel verkleinert, Schrift wird 4 px
  groß (V5). Ein Verbindungsabbruch (App-Wechsel zur 2FA-App) lässt ein leeres
  Feld ohne „Zurückgeben“ zurück (V2).
- **App-Tempo:** Jedes Textstück der Antwort zeichnet die ganze Aktivität
  neu, zehnmal pro Sekunde, mit quadratisch wachsendem Aufwand. Bei
  150 Schritten auf einem gedrosselten Handy: 120 ms pro Bild, p95 330 ms
  (P1).
- **Kosten: klein, mit zwei Lecks.** 70 Turns kosteten zusammen 2,89 $
  (Median 0,02 $). Die VMs kosten geschätzt eine Größenordnung weniger. Zwei
  Lecks: Ein localhost-Tunnel kann beide VMs bis zu 6 h wach halten (K1).
  Die Browser-VM bleibt nach jedem Lauf 10 min wach (K2).
- **Was fehlt, um mehr zu wissen:** 47 % der Arbeitsplatz-Turns liegen in
  gelöschten Chats, ihre Details sind weg. Warum ein Lauf mit Wrap-up endete
  oder die VM ausfiel, wird nirgends gespeichert (I1–I6).

Reihenfolge: Paket 1 (Messbarkeit und Abbrüche) zuerst, weil es billig ist
und die Grundlage für alles Weitere liefert. Dann Tempo (Paket 2) und
Modell-Ergebnisse (Paket 3), die zusammen die Schrittzahl senken. Danach
Ansicht, App-Tempo und Kosten (Pakete 4–6). Eine Entscheidung liegt bei Max
(Abschnitt 4).

## 1. Ist-Stand (Prod-Messung 26.–30.10.)

**Bestand.** 70 von 171 Agent-Turns nutzten den Arbeitsplatz. Ein Turn zählt,
wenn er `agent_vm` hat oder ein Werkzeug des Arbeitsplatzes aufruft. 69 Turns
kamen aus Max' Konten, 1 von einem Freund. 33 Turns liegen in gelöschten
Chats; sie sind über die Checkpoint-Kommentare der Werkbank den Belegen
zugeordnet. Agent-Modelle: DeepSeek V4.1 Flash (23), MiMo (17), Terra (10),
Luna (10), Sonnet/Haiku (7), DeepSeek 1017 (3). `open_workspace` kam
nur zweimal vor (live erst seit 29.10. 22:41 UTC). Kein Lauf dauerte länger
als 10 min (max 8,5 min).

**Zeiten (s).** Gesamt = Turn angelegt bis Ende. Modellzeit = Beleg
`created_at` bis `settled_at`. Werkzeugzeit = Abstand im Arbeitsprotokoll.

| | n | Median | p90 | max |
|---|---|---|---|---|
| Gesamt | 70 | 64 | 283 | 507 |
| Agent-Schritte je Turn | 70 | 5 | 26 | 45 |
| Modellzeit je Schritt | 642 | 3,0 | 8,1 | 154 |
| davon nicht beim Anbieter (Wand − OpenRouter `generation_time`) | 640 | 0,83 | 2,2 | – |
| Turn bis zum ersten VM-/Browser-Ergebnis | 36 | 11,8 | 29,8 | 123 |
| Browser, erster Aufruf der Nachricht | 18 | 5,5 | 17,6 | 58,7 |
| · nach Pause > 5 min / < 5 min | 8 / 8 | 14,9 / 4,6 | – | – |
| Browser, spätere Aufrufe | 112 | 1,9 | 4,5 | 31,9 |
| · `open` / `click` / `read` / `type` | 20 / 27 / 9 / 5 | 3,4 / 1,9 / 1,4 / 3,5 | 17,3 / 2,4 / 1,8 / 31,9 | – |
| `vm_exec`, Vorlauf beim ersten Aufruf | 17 | 2,5 | 9,5 | 63,0 |
| `vm_exec`, Vorlauf später | 69 | 0,1 | 0,2 | 0,4 |
| Lücke Werkzeugende → nächster Schritt | 285 | 0,3 | 0,6 | 2,2 |
| Schluss (letzter Schritt → Ende, Schlussrunde) | 70 | 6,7 | 20,5 | 75 |

Anteile an 2.944 s Laufzeit (22 vorhandene Turns seit 28.10.): Modell 44 %,
VM-Werkzeuge 16 %, Browser 16 %, Schlussrunde 8 %, Gate-Warten 5 % (bis
29.10.), Nutzer (ask_user, Halt) 5 %, Lücken 3 %, Start 2 %.

**Abbrüche und Fehler.**

| Ursache | Anzahl | Bemerkung |
|---|---|---|
| Vom Nutzer gestoppt | 3 | zwei davon nach Schleifen aus Screenshot/Klick |
| Gescheitert: Stream-Abbruch → `provider_error` (Sonnet) | 1 | 28.10. 11:47, dazu vier weitere Schrittabbrüche bei Opus/Sonnet in derselben Viertelstunde |
| Gescheitert, Ursache unbekannt | 2 | Chats gelöscht, keine Logzeile (27.10.) |
| Browser-VM für die Nachricht aus (502 beim Warmlauf) | 1 | 29.10. 10:30, vor dem Neuanlegen der Browser-VM |
| Policy-ReadTimeout (Browser und Ansicht aus) | 1 | 29.10. 09:56, seit d8e21ab9 behoben |
| Exec-Handshake `InvalidMessage`, per Retry gerettet | 5 | Zeichen des Aufwachens; Ausreißer 29 s und 59 s |
| Browser-Fehlerergebnisse | 13 von 121 | 7 Eingabe des Agenten, 3 Seiten-/CDP-Timeout, 3 „page closed“ |
| `vm_exec` mit Exit ≠ 0 | 12 von 86 | alles Fehler im Befehl, kein VM-Timeout |
| `agent_vm.unavailable` / `busy` | 0 / 0 | |

**Kosten.** Belege `estimated_cost_nano_usd`, n = 70: Agent 2,16 $, Prüfer
0,70 $ (24 %), Rest 0,03 $; je Turn Median 0,02 $, p90 0,09 $, max 0,36 $.
Der Agent las 83 % seines Inputs aus dem Cache: im ersten Schritt einer
Nachricht 40 %, nach `open_workspace` 8 % (n = 2), in Schritten mit neuem
Bild 81 %, sonst 91 %. Der Kontext wächst von 11k Tokens (Schritt 1) über
20k (10) auf 38k (40). VM-Kosten (geschätzt, die Sprites-API liefert keine
Nutzung): Browser-VM 4–5 h wach, 0,11–0,33 $; Werkbank 0,01–0,63 $.
Preise laut fly.io/pricing (2026-10-30): 0,0385 $ je CPU-Stunde, 0,021875 $
je GB-Stunde RAM, 0,000683 $ je GB-Stunde Speicher im Wachzustand, alles nach
tatsächlichem Verbrauch.

**Live-Ansicht** (nur Render-Logs). 30 Öffnungen, alle Max: 27 liefen,
Median 106 s, zusammen 3,1 h. Eine lief bis zum 1-h-Limit. Sieben wurden
nach höchstens 30 s geschlossen, sechs innerhalb von 120 s nach dem
Schließen neu geöffnet (Näherung für Wiederverbindungen). Drei scheiterten
(29.10. vormittags, behoben).

## 2. Befunde

IDs: A = Abbrüche, T = Tempo, L = Modell-Interaktion, V = Ansicht, P =
App-Tempo, K = Kosten, I = Messbarkeit für den Betreiber. Wirkung: hoch /
mittel / niedrig.

### Abbrüche

**A1 · Ein Verbindungsfehler schaltet den Arbeitsplatz für die ganze
Nachricht ab** (hoch · verifiziert)
- Wo: `agent_vm_tools.py:710–724` (`_provider`: jede Ausnahme →
  `session.failed()` → `VM_UNAVAILABLE`), `:454–457` (jede Ausnahme in
  `ready()`), `agent_browser.py:412–421, 501–504` (`off=True`).
  `BrowserTools.call` hängt am Start der Werkbank (`agent_browser.py:469`).
  Scheitert dort ein Marker-Exec, das Setup oder der Policy-POST, fällt auch
  der Browser aus, obwohl er nur die Sperre braucht.
- Was passiert: Ein Handshake-Abbruch beim Aufwachen (5× in 4 Tagen, bisher
  per Retry gerettet), ein 502 oder ein ReadTimeout. Der Agent liest „do not
  call VM tools again“. Bei einem 2-h-Lauf ist der Arbeitsplatz damit beim
  ersten Aussetzer verloren.
- Vorschlag: Transportfehler als Werkzeugfehler zurückgeben („Verbindung
  brach ab, ob der Befehl lief, ist unbekannt“). Abschalten erst nach drei
  Fehlern in Folge. Idempotente Lesewege (Version, Notizen, Policy-GET,
  Checkpoint-Liste) einmal wiederholen. Den Browser nach erfolgreichem
  `claim` nicht an der übrigen Werkbank-Vorbereitung scheitern lassen.

**A2 · Die Sperre auf den Arbeitsplatz verlängert sich nur vor Aufrufen**
(mittel · verifiziert)
- Wo: `agent_workspace.py:64–66` (600 s, Verlängerung ab 480 s),
  `agent_vm_tools.py:482–501` (`renew` nur aus `_start`). `_hold_wait`,
  `_ask_wait` und `_takeover_wait` verlängern nicht.
- Was passiert: `ask_user` oder eine Übernahme dauert 15 min (erlaubt sind
  30). Oder auf einen Aufruf bei 479 s folgt ein `vm_exec` mit 300 s. Die
  Sperre läuft ab, ein anderer Chat desselben Kontos nimmt den Arbeitsplatz
  und setzt seine Domain-Regeln. Der laufende Agent bekommt danach „busy“.
  `vm-restore` prüft nur `held_by` (`routers/agent.py:849–851`). In diesem
  Fenster ist ein Restore unter dem laufenden Agenten möglich.
- Vorschlag: Der Wächter-Thread läuft ohnehin alle 3–10 s. Er verlängert die
  Sperre alle ~4 min, solange die Nachricht sie hält.

**A3 · Ein Speicherfehler in `vm_share_file` beendet den ganzen Lauf**
(mittel · verifiziert)
- Wo: `agent_vm_tools.py:999–1003` ruft `files.save` ungeschützt auf.
  `_execute` fängt nur `ValueError`/`TypeError`
  (`agent_delegation.py:1290`), `run()` macht aus allem anderen
  `completion.failure` (`:3368–3370`).
- Was passiert: `ServiceUnavailable` von GCS oder Firestore beendet einen
  Lauf mit bezahlter VM-Arbeit.
- Vorschlag: In Werkzeugen des Arbeitsplatzes jede Ausnahme als
  Werkzeugfehler zurückgeben und melden (`report_server_exception`). Nur
  `ProviderCancelled` reicht durch.

**A4 · Exec-Frist und Aufwachen passen nicht zusammen** (mittel · Code
verifiziert, Kaltstartdauer vermutet)
- Wo: `agent_vm.py:97` (`WS_OPEN_SECONDS` 20, mit einem Retry ~41 s),
  `:597–624` (`started` vor dem Verbindungsaufbau). REST-Aufrufe bekommen
  dagegen 90 s (`WAKE_SECONDS`).
- Was passiert: Nach langer Pause schläft die Werkbank kalt, und der erste
  Kontakt ist der Handshake eines `vm_exec`. Nach 41 s kommt
  `VMUnavailable`, wegen A1 ist die VM dann aus. Oder der Aufbau dauert 25 s,
  und der Server gibt 5 s vor dem `timeout` auf der VM auf.
- Vorschlag: Die Befehlsfrist ab dem geöffneten Socket rechnen. Nach mehr
  als 5 min ohne Kontakt erst ein REST-Weckruf mit `WAKE_SECONDS`. Offen
  ist, ob Sprites den Prozess vor der 101-Antwort startet. Dann startet der
  Retry einen Befehl doppelt; das an einer Test-Sprite klären.

**A5 · Kurz vor dem Zeitlimit frisst ein Browser-Aufruf die Reserve
für die Antwort** (niedrig · verifiziert)
- Wo: `agent_browser.py:483, 500`: Die Restzeit gilt einmal für
  `warming.join` und noch einmal für `_helper`. `ready()` hat keine eigene
  Obergrenze (Setup bis 180 s, Checkpoint bis 120 s).
- Was passiert: Der Hardstopp des Wächters (`agent_delegation.py:697–708`)
  endet als Fehler statt mit Wrap-up.
- Vorschlag: Die Restzeit auf beide Wartephasen aufteilen. `ready()` an
  `answer_time_left` binden.

**A6 · Das Ende einer Nachricht wartet auf das Netz** (niedrig ·
verifiziert)
- Wo: `VMSession.close()` (`agent_vm_tools.py:607–613`) setzt bei Chats mit
  freigegebenen Domains die Regeln zurück, synchron vor `finish_run`
  (`agent_delegation.py:3410` vor `:3432`), mit `WAKE_SECONDS` 90. Bei
  Stop oder Deploy-Interrupt hat `_kill` 30 s je Befehl (`agent_vm.py:687–694`).
- Was passiert: Beim Deploy bleiben nach dem Interrupt ~20 s bis SIGKILL.
  Weckt das Zurücksetzen eine schlafende Werkbank, verfehlt `finish_run`
  die Frist. Der Turn hängt dann, bis der Reaper ihn schließt.
- Vorschlag: Regeln erst nach `finish_run` oder in einem eigenen Thread
  zurücksetzen, `_kill` mit 5 s.

**A7 · Der Helfer gibt bei hängendem Chrome auf, statt zu heilen** (niedrig
· verifiziert, nur `main`)
- Wo: `browser.py:1564–1580`: `ready()` verbindet ohne Neustart und meldet
  bei Fehlschlag `declined`. Hängt `display.sh`, wartet der Aufruf bis
  `READY_SECONDS` 80 (`:1448, :1483`). Mit Heilung und 70-s-Wächter liegt
  das über den 180 s des Servers.
- Was passiert: 15 s mehr und doppelter `display.sh`, im schlimmsten Fall
  „did not answer in time“ statt „failed“ mit Neustart. In Prod brauchte ein
  erstes `open` 58,7 s (Handshake-Retry, CDP-Timeout, Seiten-Timeout).
- Vorschlag: Im Helfer `connect()` mit Neustart nutzen, `READY_SECONDS`
  ~35 s.

### Tempo

**T1 · Kein Vorwärmen bei `open_workspace`** (hoch · verifiziert)
- Wo: `agent_delegation.py:756–787` (`_request_workspace`,
  `_open_workspace`) tauschen nur Prompt und Werkzeuge. Einziger Aufrufer
  von `ready()` ist `VMTools._start` (`agent_vm_tools.py:700–708`), also
  der erste Werkzeugaufruf. `_warm` startet erst im Browser-Aufruf
  (`agent_browser.py:468`).
- Was passiert: Während des ganzen Modellschritts nach `open_workspace`
  (3–20 s) passiert nichts. Danach wartet der erste Aufruf auf Sperre,
  Regeln, Version, Marker, Checkpoint und Notizen, also 9–12 serielle
  Rundgänge. Gemessen: erster Browser-Aufruf 5,5 s Median, 14,9 s nach einer
  Pause, max 59 s.
- Vorschlag: `_request_workspace` startet einen Thread mit
  `session.ready(cancellation)` und `_warm`, vorher Status und Tageslimit
  prüfen wie in `_warm`. Zustandsmaschine und Lock von `ready()` tragen das
  schon: Der erste Aufruf wartet nur noch auf den Rest. Beginnt eine Nachricht
  schon offen, reicht `_warm` ohne Sperre und Checkpoint.

**T2 · Nur ein Werkzeugaufruf pro Schritt** (hoch · verifiziert, Wirkung
geschätzt)
- Wo: `llm/agent_client.py:1098` schickt `parallel_tool_calls=False`
  (Vorgabe vom 16.09., vor dem Arbeitsplatz). Die Schleife kann vier Aufrufe
  je Schritt nacheinander abarbeiten, mit Gate und Halt
  (`agent_delegation.py:1528`, `tool_call_limit = 4`). Ein fünfter wird
  still verworfen (`agent_client.py:879–881`).
- Was passiert: Plan plus Aktion, Datei schreiben plus ausführen, `find`
  plus `click`, drei Formularfelder: je ein eigener Schritt mit dem ganzen
  Kontext und ~4–5 s.
- Wirkung (geschätzt): 15–30 % weniger Schritte in Arbeitsplatz-Läufen.
- Vorschlag: Mehrere Aufrufe zulassen, sobald der Arbeitsplatz offen ist.
  Die Beschreibung nennt nur die Tatsachen: Die Aufrufe eines Schritts laufen
  nacheinander, eine Ref gilt über sie hinweg. Ein verworfener fünfter
  Aufruf bekommt das Ergebnis „nicht ausgeführt: höchstens 4 je Schritt“.
  Halt und Pause brechen die übrigen Aufrufe des Schritts ab (testen).

**T3 · 0,8 s je Schritt liegen außerhalb des Anbieters** (mittel · gemessen,
Ursache noch nicht getrennt)
- Wo: Belege `created_at`/`settled_at` gegen OpenRouter `generation_time`.
  Darin stecken OpenRouters Routing, der Verbindungsaufbau und unsere
  Claim-/Settle-Transaktionen (siehe Tempo-Analyse 21.10.: Anlage vor Claim,
  Settlement vor Ergebnisnutzung, je ~0,2 s, damals bewusst nicht gemacht).
- Was passiert: Bei 40 Schritten sind das ~30 s, mehr als der ganze
  Kaltstart.
- Vorschlag: Erst trennen: `request_started_at` und `first_token_at` am
  Beleg (I7). Dann den größeren Teil angehen: Anlage in den Claim falten,
  Settlement nach der Ergebnisnutzung.

**T4 · Nach jeder ändernden Aktion bis zu 2 s Warten auf Netzruhe**
(mittel · verifiziert)
- Wo: `browser.py:671–679` (`settle`: `networkidle` mit 2 s), aufgerufen
  nach click, type, key, scroll, select, tab, back, forward, open, wait
  (`:1235, :1240`).
- Was passiert: Seiten mit Tracking, Polling oder Websockets werden nie
  ruhig und kosten jedes Mal die vollen 2 s. Gemessen: `click` Median 1,9 s,
  `read` 1,4 s.
- Vorschlag: Nach Navigation wie bisher. Ohne Navigation „DOM 300 ms
  unverändert, höchstens 1 s“. Bei scroll und key ohne Navigation fast nichts.

**T5 · Die Werkbank startet mit, auch wenn nur der Browser gebraucht wird**
(mittel · verifiziert)
- Wo: `BrowserTools.call` → `VMTools._start` (`agent_browser.py:469`) →
  `ready()` mit Sperre, Wecken, Version, Ordner, Checkpoint, Notizen, Keys
  (`agent_vm_tools.py:384–448`). Dazu setzt `started=True` die Grenzen eines
  langen Laufs (24 → 200 Schritte, 15 → 120 min;
  `agent_delegation.py:722–727`). Bis zu 6.000 Zeichen `NOTES.md` kommen mit
  dem ersten Browser-Ergebnis in den Kontext.
- Was passiert: Ein reiner Web-Lauf (Delay Sports) wartet auf die Werkbank,
  bekommt Notizen, die er nicht braucht, und das lange Schrittlimit.
- Vorschlag: Für den Browser nur die Sperre. Werkbank, Checkpoint und
  Notizen erst beim ersten `vm_*`-Aufruf. Die langen Grenzen gelten mit
  `open_workspace` ohnehin.

**T6 · Serielle Rundgänge in `ready()` und je Aufruf** (niedrig bis mittel
· verifiziert, Wirkung geschätzt)
- Wo: Marker, Notizen und Keys sind je ein eigener `agent-run`-Exec. Die
  Regeln gehen bei jeder Nachricht als POST raus, auch unverändert. Der
  Checkpoint läuft als POST-Stream und lädt danach die ganze Liste, um die
  eigene ID zu finden (`agent_vm.py:481–509`). Je Aufruf zwei Reads
  desselben Konto-Dokuments (`agent_delegation.py:2365`,
  `agent_vm_tools.py:473`) und je Exec eine neue WSS-Verbindung mit TLS
  (`agent_vm.py:564–581`).
- Was passiert: `ready()` braucht 2–4 s, je Aufruf 0,1–0,4 s Overhead.
- Vorschlag: Ein Exec für Marker, Notizen und Keys. Regeln nur bei
  Änderung. Den Checkpoint parallel laufen lassen, nur der erste ändernde
  Werkbank-Aufruf wartet darauf. Prüfen, ob das `complete`-Ereignis die ID
  schon trägt. Vorher mit den neuen Logzeilen messen (I5).

**T7 · Der erste Netz-Aufruf wartet auf den Tunnel, auch ohne
localhost-Seite** (niedrig · verifiziert)
- Wo: `agent_browser.py:404–409`: Hatte das Konto je localhost-Ports und
  ist der Tunnel beendet, wartet jede Netz-Aktion bei `page_url is None` bis
  zu 20 s auf seinen Neustart. Beim ersten Aufruf jeder Nachricht ist
  `page_url` leer.
- Vorschlag: Nur warten, wenn das Ziel localhost ist (die Aktion kennt ihre
  URL) oder die letzte Seite des Kontos localhost war.

### Modell-Interaktion

Gemessen (Audit, ohne Memory): Systemprompt + Werkzeuge mit geschlossenem
Arbeitsplatz 2,7k Tokens je Schritt, offen 7,5k (davon `browser` 1,2k,
`prepare_settings_change` 0,7k, `ask_user` 0,5k). Ein Browser-Ergebnis nach
einer Aktion ~950 Tokens. Kompaktiert wird ab 150.000 Zeichen, etwa ab
Schritt 33. Grundsatz für alle Vorschläge: Fakten im Ergebnis, keine
Wann-Regeln im Prompt ([Verfassung statt Regeln](agent-mode.md)).

**L1 · Von sechs gefundenen Bildern verschwinden drei, bevor das Modell sie
sieht** (hoch · verifiziert)
- Wo: `find_pictures` liefert bis zu 6 Bilder je Aufruf
  (`agent_web_images.py:64, 305–315`) und sagt „The pictures follow as
  images … in this order“. Gleich danach ersetzt `_show_pictures` →
  `older_pictures` (`agent_delegation.py:874–888`,
  `agent_compaction.py:108–114`, `PICTURES_KEPT = 3`) alle außer den letzten
  drei durch „Open it again with vm_view_image“. `vm_view_image` gibt es bei
  geschlossenem Arbeitsplatz gar nicht.
- Was passiert: Das Modell zeigt Bilder per `show_image` und schreibt
  Bildunterschriften zu p1–p3, ohne sie gesehen zu haben, oder es holt sie
  erneut. Im Delay-Sports-Lauf hing ein Mannschaftsfoto mit falscher
  Unterschrift unter der Antwort. Dass dies die Ursache war, ist vermutet.
- Vorschlag: Bilder des aktuellen Ergebnis-Batches nie verdrängen. Der
  Ersatztext nennt den Weg zurück passend zur Herkunft (`find_pictures`
  erneut, `vm_view_image`, `screenshot`).

**L2 · Nach jeder Aktion kommt die ganze Seite noch einmal** (hoch ·
verifiziert, Wirkung simuliert)
- Wo: `browser.py:1237–1252` hängt nach jeder Aktion
  `read_text(page, 0, 4000)` an, auch nach `type` ohne Enter, `key` und
  `download`. Einen Bericht über die Wirkung (`hit_report`) gibt es nur für
  Klicks an x,y und `drag` (`:1330–1336, :857`). Ein Klick per Ref meldet
  „Clicked e12.“. Nach `scroll` kommt dieselbe Liste wie vorher, denn sie
  hängt nicht vom sichtbaren Bereich ab (`SNAPSHOT_JS`, `:153–158`).
- Was passiert: ~950 Tokens Wiederholung je Aktion. Dazu Folgeschritte,
  weil die Änderung nicht zu sehen ist: ein Screenshot nach dem Scrollen,
  ein `read` mit Offset, wenn ein Menü hinter Zeichen 4.000 aufging. Im
  Tic-Tac-Toe-Lauf kamen 20 Screenshots auf 16 Klicks.
- Wirkung (simuliert, 45 Schritte): Input 1,24 → 0,67 Mio. Tokens, dazu
  vermiedene Schritte.
- Vorschlag: Bleibt die Seite dieselbe, Kopfzeile (URL, Titel) plus
  Wirkungsbericht für jede Aktion (`HIT_JS` gibt es schon) plus nur neue
  oder geänderte Elementzeilen. Die volle Liste nach einer Navigation oder
  bei `read`. Nach `scroll` die sichtbaren Elemente zuerst.

**L3 · Das Modell weiß nicht, wie viel Zeit und wie viele Schritte es
verbraucht hat** (hoch · verifiziert)
- Wo: Grenzen und Verbrauch stehen nur einmal im Ergebnis von
  `open_workspace` (`agent_delegation.py:764–769`). Beginnt die Nachricht
  mit offenem Arbeitsplatz, erfährt das Modell sie nie. Das Wrap-up sagt nur
  „has reached its limit“, ohne welches (`:3028–3032`).
- Was passiert: Delay Sports: Die Antwort stand nach 30 s fest, danach
  folgten 5 Minuten Bildersuche.
- Vorschlag: Eine reine Faktzeile am Ende jedes Ergebnis-Batches, z. B.
  „Schritt 31 · 4,8 min in dieser Nachricht“. Neuer Inhalt am Ende, bricht
  den Cache nicht. Das Wrap-up nennt die Grenze und dass eine Folgenachricht
  weitermachen kann.

**L4 · Fehlerergebnisse nennen weder Ursache noch Zustand** (mittel ·
verifiziert)
- Wo: `failed()` behält nur die erste Zeile einer Playwright-Meldung
  (`browser.py:1395–1397`). Übrig bleibt „Timeout 10000ms exceeded“, die
  Ursache im Call-Log fehlt (etwa „<div …> intercepts pointer events“).
  `refused`/`failed` werden zu `{"error": text}` ohne URL und Titel
  (`agent_browser.py:523–524`). Eine veraltete Ref sagt nur „Call read“
  (`browser.py:826`).
- Was passiert: 1–2 Folgeschritte je Fehler (`read` oder Screenshot). In
  Prod hatte ein `type` 31,9 s (Tastendruck-Timeout).
- Vorschlag: Die letzte aussagekräftige Call-Log-Zeile, die Kopfzeile der
  Seite und bei veralteter Ref gleich das aktuelle `read` mitgeben.

**L5 · Download-Ergebnis zeigt den Tab statt der Datei** (mittel ·
verifiziert; offenes Paket 4 aus dem Delay-Sports-Lauf)
- Wo: `browser.py:1249–1252` hängt auch nach `download` 4.000 Zeichen
  Tab-Zustand an. 0 Byte gilt als `ok`. `fetch` nennt keinen Content-Type
  (`:1100–1120`), eine Login-Seite als `report.pdf` gilt als Erfolg.
- Vorschlag: Nur Name, Bytes und Content-Type. 0 Byte als `refused` mit
  dieser Tatsache.

**L6 · Das Ausblenden alter Bilder bricht den Prompt-Cache** (mittel ·
verifiziert, gemessen)
- Wo: `agent_delegation.py:887–888` ersetzt ab dem vierten Bild das
  älteste sichtbare *in der Mitte des Verlaufs*. Ab dort schreibt der
  Anbieter alles neu in den Cache. Anders als `compact()` ohne
  Mindestgewinn (`MIN_GAIN`).
- Was passiert: Mit `screenshot_after` bei jedem Zug passiert das in jedem
  Schritt. Gemessen: Schritte mit neuem Bild 81 % Cache-Treffer statt 91 %.
  Bei DeepSeek kaum Geld, bei Terra/Sonnet ~0,02–0,04 $ je Bruch. Ein
  Terra- oder Sonnet-Lauf mit 15 Bildern zahlt so ungefähr einen zweiten
  Lauf.
- Vorschlag: Bilder gesammelt entfernen, etwa bis 10 stehen lassen und dann
  auf 3 kürzen, oder nur zusammen mit einer Kompaktierung. Der Agent sieht
  dabei eher mehr.

**L7 · Kleinere Widersprüche** (niedrig · verifiziert)
- „unknown tool“ sagt „read_source opens only URLs that comparison answers
  cited“ (`agent_tools.py:121–123`). Im Audit liest `read_source` jede
  öffentliche Seite.
- Ruft ein Modell bei geschlossenem Arbeitsplatz direkt `browser` auf, nennt
  der Fehler `open_workspace` nicht.
- `github_import` sagt noch „in your VM“, sonst heißt es überall
  „workspace“.

### Ansicht

**V1 · Am Handy lässt sich nach „Übernehmen“ nichts tippen** (hoch · Code
verifiziert, nicht am Gerät)
- Wo: `workspace-view.js:57` lädt nur `core/rfb.js`. noVNCs Tastatur hängt
  am Canvas. Das einzige Textfeld (`pasteTarget`, `:306–310`) hat
  `tabIndex = -1` und `pointer-events: none`.
- Was passiert: iOS und Android öffnen für ein Canvas keine
  Bildschirmtastatur. Anmelden, wofür die Übernahme vor allem da ist, geht
  am Handy nur über „Einfügen“.
- Vorschlag: Ein Knopf „Tastatur“ fokussiert ein unsichtbares, fokussierbares
  `<input>` (16 px, `autocapitalize`/`autocorrect` aus). `beforeinput` und
  `keydown` gehen an `rfb.sendKey`, wie `keyboardinput` in noVNCs
  `app/ui.js`. Backspace und Enter eigens behandeln.

**V2 · Nach einem Verbindungsabbruch bleibt die Ansicht leer, ohne
„Zurückgeben“** (hoch · verifiziert, Sonde)
- Wo: Der `disconnect`-Handler (`workspace-view.js:655–660`) setzt nur
  `rfb = null` und sagt „Close and open it again.“ `showTurn` blendet die
  Leiste aus, sobald `!view.rfb` (`:494`). Die Statuszeile ist einzeilig mit
  Auslassung (`workspace-view.css:224–232`).
- Was passiert: Der Nutzer wechselt am Handy in die 2FA-App, iOS schließt
  den Websocket. Zurück in der App bleibt die Übernahme aktiv, der grüne
  Rand steht, das Feld ist leer, „Zurückgeben“ ist weg. Der einzige Ausweg
  ist Schließen, das den Browser still zurückgibt, mitten im Login und ohne
  `consensio:workspace-handback`.
- Vorschlag: Ohne Server-Code (4409/4410/4402/4429) automatisch neu
  verbinden, mit Backoff 1/2/5/10 s und zusätzlich bei `visibilitychange`
  und `online`. Dabei Skeleton und „Verbinde neu …“. Leiste und
  „Zurückgeben“ bleiben stehen. Fehlertexte zweizeilig plus Knopf „Neu
  verbinden“.

**V3 · Kaltstart, langer Befehl und Hänger sehen gleich aus** (hoch für die
Verständlichkeit · verifiziert)
- Wo: Der Server meldet `started_at` erst nach der Vorbereitung
  (`agent_vm_tools.py:787`), das Frontend nutzt es nirgends. `vmMeta` zeigt
  bei `vm_exec` „Running…“ ohne Zeit, bei Browser-Schritten nichts
  (`agent-activity.js:630`). Ein Browser-Aufruf darf bis 180 s dauern
  (`agent_browser.py:79`).
- Vorschlag: Ohne `started_at` „Arbeitsplatz startet …“, mit `started_at`
  „Läuft · 42 s“. Beim Browser `started_at` nach Start und Warmlauf melden
  (`agent_browser.py:469–488`). Nach ~30 s ohne neue Ausgabe „Keine Ausgabe
  seit 45 s · Limit 3 min“.

**V4 · Eine vergessene Live-Ansicht verbraucht die VM-Zeit des Tages**
(mittel · verifiziert, in Prod einmal bis zum Limit)
- Wo: `app/api/routers/agent_workspace.py:319–321` rechnet die volle
  Wanduhrzeit an, bis `VIEW_SECONDS` = 1 h. Pro hat 2 h am Tag
  (`agent_vm_time.py:29`). `workspace-view.js` trennt weder bei verborgenem
  Tab noch bei Untätigkeit (`onVisible`, `:558–563`).
- Was passiert: Panel öffnen, Tab wechseln, vergessen: Die Hälfte der
  Tageszeit ist weg, später sagt ein Aufruf „workspace time for today used
  up“.
- Vorschlag: Nach ~60 s verborgenem Tab trennen, solange der Agent den
  Browser hat, und beim Zurückkommen neu verbinden (braucht V2). Im Kopf
  des Panels die Restzeit des Tages.

**V5 · Am Handy ist das Bild unlesbar klein** (mittel · Sonde)
- Wo: Xvfb fest 1280×800 (`display.sh:61`), `scaleViewport = true`,
  `resizeSession = false` (`workspace-view.js:650–651`).
- Gemessen: bei 390 px Skalierung 0,278, eine 14-px-Schrift wird 3,9 px.
  Das Bild belegt 356×222 px eines 356×680-px-Felds. Angedockt bei 1440 px:
  0,544, also 7,6 px.
- Vorschlag: Bild oben statt mittig. Bei Übernahme auf schmalen Schirmen
  „100 %“ anbieten (`scaleViewport = false`, `clipViewport`,
  `dragViewport`). Später prüfen: Bildschirmgröße während der Übernahme an
  den Client anpassen (Xvnc kann das), damit Seiten ihr Handy-Layout zeigen.
  Beim Zurückgeben wieder 1280×800, damit die Koordinaten des Agenten
  stimmen.

**V6 · Am Handy sieht man im Panel nicht, was der Agent tut** (mittel ·
verifiziert)
- Wo: Unter 1100 px liegt das Panel als Vollbild über dem Chat
  (`workspace-view.css:8–21`). Die Statuszeile sagt fest „Watching. Click
  the screen to take over.“ (`workspace-view.js:479`).
- Vorschlag: Solange der Agent den Browser hat, die Überschrift des
  laufenden Schritts in die Statuszeile spiegeln.

**V7 · Kleinere Darstellungsfehler** (niedrig · Sonde/Code)
- Panelkopf bricht bei 390 px um, das Schließen-Kreuz steht allein in der
  zweiten Zeile (`workspace-view.css:542–552`). Titel und Kreuz gehören in
  die erste Zeile.
- Die Seitenkarte ist 480 px breit bei Qualität 60 (`browser.py:138–139`),
  angezeigt bis 360 CSS-px: auf Retina weich. 720 px bei etwas niedrigerer
  Qualität, solange `PREVIEW_BYTES` (64 KB) reicht.

### App-Tempo

**P1 · Jedes Textstück der Antwort zeichnet die ganze Aktivität neu**
(hoch auf schwächeren Handys · Sonde)
- Wo: Auch reine Antwort-`delta`s lösen alle 100 ms `registry.update` aus
  (`agent-chat.js:2576, 2590`) → `project()` → `agentActivity.render`. Darin
  `.includes()` in `flatMap`/`filter` über alle Events (O(n²),
  `agent-activity.js:1170–1182, 1306–1307`), `compactReasoning` dreimal je
  Reasoning (`:1110, :1173, :1367`), Signaturen per `JSON.stringify` inklusive
  Ausgaben (~950 KB Strings je Render; `:773, :825, :935, :1335`). Jeder
  frühere Schritt steht doppelt im DOM (Zeitleiste und Faltliste).
- Gemessen (150 Schritte): Desktop 17,7 ms je Render (p95 44), 4×
  gedrosselt 120 ms (p95 330). 4.202 DOM-Knoten, Aktivitäts-JSON 2,1 MB.
  Mit aufgeklapptem Verlauf 178 ms.
- Was passiert: Ab ~100 Schritten ist der Hauptthread eines mittleren Handys
  ausgelastet: Tippen im Feld hakt, Scrollen ruckelt, der Akku leidet.
- Vorschlag: `delta`s rendern die Aktivität nicht (Dirty-Flag). `receive()`
  vergibt je Event eine Revision, Knoten vergleichen nur sie. `Set`s statt
  `.includes`. `compactReasoning` je Event-ID und Textlänge zwischenspeichern.
  Zeitleiste und Faltliste erst beim Aufklappen bauen.

**P2 · Bilder unter der Antwort laden alle sofort als data:-URL** (mittel ·
Code verifiziert, Absturz vermutet)
- Wo: `agent-workspace.js:39–41, 423–434, 452–462`. `project()` füllt alle
  Verlaufszeilen (`:593`), also lädt jeder Chat beim Öffnen alle Bilder aller
  Turns, bis 5 MB je Datei (`agent_vm_tools.py:94`): ~6,7 MB base64 plus
  Bitmap.
- Was passiert (vermutet): iOS lädt den Tab bei Speicherdruck neu.
- Vorschlag: Laden, wenn das Bild in Sicht kommt (IntersectionObserver).
  Serverseitig eine Vorschau bis 1600 px (wie
  `agent_web_images.MAX_SIDE`).

**P3 · Endlose Glanz-Animation** (niedrig · vermutet)
- `label-shine` animiert `background-position` ohne Ende
  (`agent-chat.css:913–927, 1326`) und zwingt jedes Bild neu zu malen. Mit
  einer Transform-Animation oder nur bei sichtbarem Element messen.

### Kosten

**K1 · Der localhost-Tunnel kann beide VMs bis zu 6 h wach halten** (hoch
für die VM-Kosten · Code verifiziert, Verhalten der Dev-Clients vermutet)
- Wo: `agent_tunnel.py:62` (`TUNNEL_SECONDS` 6 h), `:201–206` (Leerlauf nach
  10 min ohne Bytes), aber schon jeder Verbindungsversuch (`O`, `:238–239`)
  und jedes Datenpaket (`:277–278`) zählt als Nutzung. Dazu startet
  `agent_browser.py:392–410` den Tunnel bei jedem Browser-Aufruf neu, sobald
  das Konto je localhost-Ports hatte.
- Was passiert: Bleibt eine Dev-Seite im Chrome der Browser-VM offen, pingt
  ihr Live-Reload regelmäßig (Vite nach einem Serverausfall ~1/s, Next.js
  seinen HMR-Kanal). Der Tunnel gilt nie als untätig. Seine zwei offenen
  Execs halten beide VMs wach, und Chrome läuft deshalb weiter. Das ergibt
  bis zu 6 h, ~0,27 $ je Vorfall. Es zählt nicht zur VM-Zeit. Reine Web-Läufe
  wecken über den Neustart die Werkbank mit.
- Vorschlag: Den Tunnel nur leben lassen, solange eine Nachricht läuft oder
  die Live-Ansicht offen ist, plus 2 min. Ohne Ansicht sieht niemand die
  App. `resume` nur für localhost-Aktionen.

**K2 · Die Browser-VM bleibt nach jedem Lauf 10 min wach** (mittel ·
verifiziert)
- Wo: `browser.py:96, 530, 641, 1736` (`stay_awake`, Hold der Tasks-API
  10 min nach jedem Aufruf). Es gibt kein Lösen am Nachrichtenende,
  `VMSession.close` (`agent_vm_tools.py:603–622`) fasst die Browser-VM
  nicht an.
- Was passiert: 0,005–0,01 $ je Nachricht mit Browser, bei 20 Läufen am Tag
  rund 2–3 % der Modellkosten. Es zählt nicht zur VM-Zeit.
- Vorschlag: Am Nachrichtenende per Helfer-Aktion den Hold auf ~2 min
  kürzen. Eine offene Live-Ansicht hält die VM selbst wach. Der Foony-Fall
  („offline zwischen zwei Zügen“) lag innerhalb eines Laufs und bleibt
  abgedeckt.

**K3 · Bildbrüche im Cache** siehe L6.

**K4 · Checkpoints wachsen ohne Ende, auch für reine Browser-Nachrichten**
(niedrig · verifiziert, Wachstum vermutet)
- Wo: `agent_vm_tools.py:421–427`, `agent_workspace.py:576–583`: jede
  Nachricht mit Arbeitsplatz macht einen Checkpoint. Wiederherstellen geht
  14 Tage (`RESTORE_DAYS`), gespeichert bleiben sie für immer. Die REST-API
  kann sie nicht löschen, nur die CLI (`sprite checkpoint delete`).
- Was passiert: Speicher wächst monatlich weiter (geschätzt 0,1–0,6 $ je
  Monat und Entwickler-Konto). Die Liste, die jeder Checkpoint lädt (T6),
  wird länger.
- Vorschlag: Kein Checkpoint für Nachrichten ohne Werkbank-Aufruf (folgt
  aus T5). Alte über die CLI-API löschen, wenn sie sich als Endpunkt findet,
  sonst als Wartungsskript.

**K5 · Hintergrundprozesse buchen ihr volles Limit** (niedrig ·
verifiziert)
- Wo: `agent_vm_processes.py:44` (Standard 30 min), `:258–260`: Die Reserve
  wird beim Start voll gebucht und bei Stopp oder frühem Ende nie
  erstattet. Vier Dev-Server-Starts verbrauchen die 2 h eines Pro-Kontos.
- Vorschlag: Beim Ende die nicht genutzte Zeit erstatten.

**K6 · Reine Browser-Lesezugriffe lösen eigene Prüferrunden aus**
(Entscheidung, Abschnitt 4)
- Wo: `agent_audit.py:113–115`: `QUIET_TOOLS` kennt `vm_read_file`, aber kein
  `browser`. `read`, `text`, `find`, `tabs` und `screenshot` wirken nicht
  nach außen.
- Wirkung (geschätzt): ~30 % weniger Live-Runden in Browser-Läufen, ~4 %
  der Kosten, ~11 % des Tageskontingents eines Audit-Laufs.

**K7 · Veralteter Kommentar** (niedrig) — `agent_vm_time.py:26–28` rechnet
mit alten Preisen („$1 at full load on 8 CPUs“). Heute kosten 2 h auf
8 CPUs ~0,62 $ plus RAM.

Ohne Befund: Größe der Sprites (fest 8 vCPU/100 GB, RAM verwaltet die
Plattform, kein Hebel), Zeitangaben im Prompt, Werkzeugliste (bricht den Cache
nur einmal bei `open_workspace`, gewollt), Retries/Hedging, das Ende der
Live-Ansicht nach 1 h.

### Messbarkeit für den Betreiber

Damit sich die nächste Frage „warum dauerte das so lange?“ aus den Daten
beantworten lässt, ohne Chats lesen zu müssen:

- **I1 · Grund des Wrap-ups geht verloren** (verifiziert):
  `_merged_wrap_up(reason)` (`agent_delegation.py:3017–3032`) verwirft den
  Grund, wenn das Wrap-up gelingt. Zeit-, Schritt-, Kontext- und
  Kontingentgrenze sind nicht von einem freiwilligen Ende zu unterscheiden.
  → Arbeitsprotokoll-Eintrag `limit` und Feld am Turn.
- **I2 · VM-Ausfall ohne Grund** (verifiziert): `summary()`
  (`agent_vm_tools.py:576–587`) speichert nur `unavailable: True`.
  `_unexpected` loggt `VMUnavailable` nicht (`:203–208`), und mehrere
  Stellen werfen es ohne Logzeile (`agent_vm.py:439, 468, 543, 553, 680`).
  → `unavailable_reason` (Operation und Fehlerart, keine Daten).
- **I3 · Logzeilen ohne Turn:** „Agent browser call …“ und „Agent VM ready
  …“ tragen keine Turn- oder Schritt-ID. → Gekürzte Turn-ID und Schritt in
  jede VM-/Browser-Logzeile.
- **I4 · Keine Dauer an Browser-Schritten:** Browser-Events in
  `agent_activity` und Werkzeugeinträge im Arbeitsprotokoll haben kein
  `duration_ms` (`agent_work_log.py:306–317`). → `started_at` und
  `duration_ms` mitschreiben.
- **I5 · Phasen des Starts:** `agent_vm` am Turn speichert weder die Phasen
  von `ready()` (Sperre, Regeln, Version, Ordner, Checkpoint, Notizen, Keys)
  noch, ob die Sprite kalt war, noch Browser-Aufrufe und -Sekunden. → Felder
  `phases`, `cold`, `browser_calls`, `browser_seconds`.
- **I6 · Gelöschte Chats:** 47 % der Arbeitsplatz-Turns verlieren mit dem
  Chat alle Details. → Anonyme Zeiten je Arbeitsplatz-Turn (Schritte, Dauer,
  erster Aufruf, Ausfälle) in `ops_metrics/agent-audit-{tag}`, wie die
  vorhandenen Zähler.
- **I7 · Anbieter-Latenz:** Belege brauchen `request_started_at` und
  `first_token_at`, um Anbieterzeit von unserem Overhead zu trennen (T3).
  OpenRouters `latency` ist für die meisten Anbieter 0.
- **I8 · Live-Ansicht:** Close-Code und Relay-Fehler ins Log, Ansichten je
  Tag zählen.
- **I9 · Gate-Einträge:** `checked`-Einträge hatten in den gemessenen Daten
  weder `step` noch `gate_ms`, obwohl `scripts/audit_report.py` beides
  liest. Seit 29.10. betrifft das nur noch Domain- und Memory-Gates. Prüfen,
  ob der Schreibweg die Felder setzt.

## 3. Pakete und Reihenfolge

| Paket | Inhalt | Warum zuerst/später |
|---|---|---|
| 1 · Messen und Halten | I1–I9, A1, A2, A3, A6 | Billig. Ohne I-Felder lässt sich Paket 2 nicht nachmessen. A1–A3 werden mit längeren Läufen sicher fällig. |
| 2 · Tempo | T1, T2, T4, T5, T7, A4, A5, A7, danach T6 und T3 nach Messung | T1 und T2 bringen am meisten. T6 und T3 erst mit den Zahlen aus Paket 1. |
| 3 · Modell-Ergebnisse | L1–L7 | L1 ist ein Fehler. L2–L4 senken mit T2 die Schrittzahl. |
| 4 · Ansicht | V1–V7 | V1 und V2 machen die Übernahme am Handy erst brauchbar. |
| 5 · App-Tempo | P1–P3 | Unabhängig vom Server, eigener Strang. |
| 6 · Kosten | K1, K2, K4, K5, K7 (K3 = L6) | Kleine Beträge, K1 aber ohne Obergrenze unter 6 h. |

Pakete 3, 4 und 5 berühren getrennte Dateien und können parallel laufen.
Paket 2 und 6 berühren beide `agent_browser.py` und `browser.py`.

Nach dem Deploy messen:
- Erster Arbeitsplatz-Aufruf je Nachricht (Ziel: Median ≤ 2 s, p90 ≤ 6 s,
  gemessen ab dem Ende des Modellschritts nach `open_workspace`).
- Schritte je Arbeitsplatz-Lauf und Anteil Screenshot/`read` nach Aktionen
  (Ziel: −20 %).
- Overhead je Schritt (Ziel: Median ≤ 0,5 s).
- `unavailable_reason` und Wrap-up-Gründe in einer Woche echter Läufe.
- Wachzeit der Browser-VM nach Lauf-Ende (Ziel: ≤ 2 min ohne Ansicht).

## 4. Entscheidung für Max

**Sollen reine Browser-Lesezugriffe (lesen, suchen, Screenshot) ohne eigene
Prüferrunde laufen, wie heute schon das Lesen von Dateien (K6)?**

Empfehlung: ja. Die Prüfer sehen jeden Lesezugriff weiter, nur in der Runde
des nächsten handelnden Schritts, spätestens nach drei stillen Schritten.
Ein Halt kommt heute ohnehin erst nach dem nächsten Schritt: Eine Runde
dauert 20–40 s, ein Schritt ~5 s. Gespart werden ~11 % des Tageskontingents
eines Audit-Laufs. Dagegen spricht nur das Prinzip „jeder Fremdinhalt sofort
geprüft“.

## 5. Bewusst nicht vorgeschlagen

- Prüferbefunde an den Agenten zurückgeben (Max' Produktentscheidung,
  [agent-mode.md](agent-mode.md) „Audit statt Vergleich“).
- Niedrigere Denkstufen, weniger Recherche oder kürzere Limits als
  Tempo-Hebel.
- Wann-Regeln im Prompt („suche keine Bilder, wenn …“). L3 gibt dem Modell
  stattdessen die Fakten Zeit und Schritte.
- Größere oder kleinere Sprites: Die Größe ist fest, abgerechnet wird der
  Verbrauch.
- Weitere Arbeit am Kaltstart über T1 hinaus, bevor die Logzeilen aus
  Paket 1 eine Woche Daten liefern.

## 6. Methode und Grenzen

- Datenbasis klein und fast nur Max: 70 Turns in vier Tagen, ein fremder.
  Kein Lauf über 10 min, Handy-Nutzung nicht erfasst. Läufe über eine Stunde
  (bis 200 Schritte/2 h erlaubt) kommen in den Daten nicht vor. A1–A5 sind
  deshalb aus dem Code abgeleitet, nicht beobachtet.
- 33 Turns in gelöschten Chats: nur Belege und Checkpoint-Kommentar, keine
  Werkzeugzeiten.
- Die Zahlen stammen von 842ae1c9. Der residente Browser-Helfer auf `main`
  spart laut Messung an der echten Browser-VM ~0,55 s je Browser-Aufruf.
- VM-Kosten sind geschätzt: Die Sprites-API liefert keine Nutzung, Annahmen
  1–2 GB RAM und 0,05–0,25 CPU im Leerlauf.
- Frontend-Sonden liefen mit 4× CPU-Drossel in Chromium, nicht auf einem
  iPhone.
- Messskripte und Rohdaten lagen nur im Scratchpad der Audit-Session. Die
  Methode ist in den Abschnitten oben beschrieben und lässt sich aus
  Firestore (`llm_calls`, `turns`, `work_log`), Render-Logs (`GET /v1/logs`)
  und OpenRouter `/api/v1/generation` wiederholen.

# Audit-Modus produktionsreif: Analyse und Spezifikation (2026-10-29)

Stand von `main` am 2026-10-29 (7b3f12c0). Grundlage: Prod-Messung aller
erhaltenen Audit-Läufe vom 25. bis 29.10. (nur gelesen, keine Modell-Calls),
Render-Logs derselben Tage und zwei unabhängige Code-Prüfungen (Server-Naht,
Browser). Jeder Befund unten ist am Code nachgeprüft; was nur vermutet ist,
steht so da. Architektur: [agent-mode.md](agent-mode.md) „Audit statt
Vergleich“, [agent-work-log.md](agent-work-log.md),
[codebase-map.md](codebase-map.md) ab „Audit statt Vergleich“.

## Kurzfassung

- **Was schon gut läuft:** Seit dem 27.10. haben alle 29 Läufe ihre Prüfung
  vollständig bekommen. Nach dem letzten Wort der Antwort dauert es im Median
  10 s, bis die Marken stehen. Nichts ist hängen geblieben, und kein Deploy
  hat einen Lauf abgeschnitten.
- **Was noch nicht bewiesen ist:** Die Zahlen kommen fast nur aus Max'
  Konto, meist mit ein bis zwei Prüfern und Läufen unter sechs Minuten. Drei
  Prüfer (das Standard-Preset seit 28.10.), lange Läufe in der Werkbank und
  Handy-Nutzung kommen in den Daten praktisch nicht vor. 65 Läufe fehlen
  ganz, weil ihre Chats gelöscht wurden.
- **Was kaputt gehen kann:** Mehrere Randfälle treffen genau die
  Sicherheitsschicht. Eine Pause lässt sich nicht mehr entscheiden, wenn ihr
  Speichern scheitert. Ein zweiter Halt geht still verloren. Auf dem Handy
  gilt die Browser-Übergabe nach 90 s im Hintergrund als zurückgegeben. Ein
  Lauf, dem der Browser länger als 40 min folgt, wird als „Verbindung
  verloren“ aufgegeben.
- **Was am meisten Zeit kostet:** die Schlussrunde des langsamsten Prüfers
  (GPT-6 Luna p90 40 s). Bisher gibt es weder eine Frist noch eine zweite
  Anfrage, die einen Hänger abfängt.
- **Was am meisten Kontingent kostet:** Die Prüfer verbrauchen 48 % des
  Tageskontingents eines Audit-Laufs, machen aber nur 22 % der Kosten aus.
  80 % davon entfallen auf die Live-Runden.

Reihenfolge der Umsetzung: erst die Sicherheits- und Verlustfehler (Paket 1),
dann Messbarkeit (Paket 2), dann Tempo, Abbrüche, Langlauf (Pakete 3–5). Eine
Entscheidung liegt bei Max (Abschnitt 7).

## 1. Ziel und Maßstab

„Produktionsreif“ heißt hier: Der Audit-Modus hält seine Versprechen auch
außerhalb des Normalfalls und lässt sich daran messen. Die Versprechen sind:
Prüfer laufen unabhängig mit, ein Halt erreicht den Nutzer immer, ein Fehler
der Prüfung kostet nie die Antwort, und die Marken stehen Sekunden nach der
Antwort.

| ID | Kennzahl | Ist (25.–29.10.) | Ziel |
|---|---|---|---|
| Z1 | Marken nach dem letzten Wort (Antwort fixiert → Review fertig) | p50 10 s · p90 35 s · max 74 s | p50 ≤ 10 s · p90 ≤ 20 s · max ≤ 60 s |
| Z2 | Reviews `succeeded` unter completed Audit-Turns | 74/76 (seit 27.10. 29/29) | ≥ 98 %, `failed` ≤ 0,5 % |
| Z3 | Turn scheitert wegen der Prüfung | 0 | 0 (Invariante) |
| Z4 | Halt oder Karte, die der Nutzer nicht entscheiden kann | nicht gemessen, Code-Lücken S1, S2, B2 | 0 |
| Z5 | Gate-Wartezeit vor einem Aufruf | p50 4,7 s · p90 9,6 s · max 13 s | p90 ≤ 10 s, nie über `GATE_SECONDS` (20 s) |
| Z6 | Prüfer-Threads oder -Sitzungen nach Turn-Ende | 0 (Code geprüft) | 0, auch nach Crash und Reap |
| Z7 | Browser verliert einen laufenden oder pausierten Lauf | Code-Lücken B1, B2 | 0 bei Reload, Tab-Wechsel, Netzwechsel, > 40 min |
| Z8 | Prüfer-Anteil am Tageskontingent | 48 % (seit 28.10.) | Entscheidung Max (Abschnitt 7) |

**Freigabe:** Die Pakete 1–4 sind umgesetzt und Z1–Z7 halten über mindestens
100 Audit-Turns. Darunter müssen sein: 30 mit drei Prüfern und 10
Werkbank-Läufe über 10 min. Dazu kommen die Handy-Fälle aus dem Smoke
(A-L4), denn das Gerät wird bewusst nicht gespeichert. Gemessen wird mit
`scripts/audit_report.py` (A-M8).

## 2. Ist-Stand (Prod-Messung)

**Datenbasis.** 79 Audit-Turns mit vollständigen Daten (76 Max, 3 ein fremdes
Konto) vom 25.10. 21:19 bis 29.10. 14:16 MEZ. Dazu 65 gelöschte Turns, von
denen nur die Rechnungsbelege (`llm_calls`) übrig sind. Prüfer je Turn: einer
in 46, zwei in 32, sechs in einem, **drei in keinem**. Zwischen 26.10. abends
und 28.10. mittags fehlen fast alle Turns (gelöscht), Vorher/Nachher-Vergleiche
über die Deploys dieser Tage sind deshalb nicht möglich.

**Status.** 76 completed, 2 cancelled (Stop vor der Antwort), 1 failed
(`provider_error` des Chatmodells Opus 5.5 nach 8 s, nicht die Prüfung).
Reviews: 74 succeeded, 1 partial, 1 failed. Beide Ausfälle waren die
Schlussrunde von MiMo V2.6 Flash mit `review_unreadable` vor dem zweiten
Versuch (b79baee9). Von 141 Prüfer-Instanzen war keine `no_time`,
`rate_limited`, `provider_error`, `context_limit` oder `audit_unavailable`.
Live-Runden: 5 von 303 gescheitert (1,7 %), nie zwei in Folge, also nie eine
Fehlerpause. Ein neues Gespräch wegen vollem Kontext kam nie vor.

**Laufzeiten (76 completed).**

| Strecke | Median | p90 | Max |
|---|---|---|---|
| Gesamt | 27 s | 225 s (127 s ohne Pausen) | 374 s |
| Agent bis zur fixierten Antwort | 15 s | 200 s | 338 s |
| Marken nach dem letzten Wort | 10 s | 35 s | 74 s |
| davon: Fixieren → erste Schluss-Anfrage | 0,5 s | – | 5,7 s |
| davon: Schlussrunde (Modell) | 8,4 s | 29 s | – |
| davon: Speichern | 0,7 s | – | – |

Die Schlussrunde dauert je nach Modell unterschiedlich lang (Median/p90/Max):
Luna 13/40/72 s, Qwen 20/25/29 s, MiMo Pro 9/14/67 s, GLM 8/15 s, MiMo Flash
2/4/28 s, DeepSeek 2/14/18 s. In 9 von 52 Prüfer-Instanzen mit Werkzeug-Schritten
lief beim Fixieren noch eine Live-Runde. Der Rückstand beim Fixieren lag im
Median bei 3 ungelesenen Einträgen (p90 6, max 21). Seit das alte
6-Runden-Limit fiel, lagen höchstens 3 handelnde Schritte ungelesen.

**Live-Runden.** Je Turn Median 0, p90 13, max 28 Anfragen. Dauer je
Live-Anfrage: MiMo Pro 4/10/53 s, Luna 4/8/29 s, Qwen 3/6 s, MiMo Flash 2/2 s.
Fast jeder handelnde Schritt bekommt eine eigene Runde (0,82 Runden je Schritt
und Prüfer). Die Kurzfassung der Anweisungen (`instructions_brief`) wirkt:
Die erste Prüfer-Anfrage hat im Median 4,9k statt 10,8k Input-Tokens.

**Gate und Halts.**
- 29 Gate-Runden (28.10. 12:59 bis 29.10. 11:00, fast alle Browser-Klicks):
  26 go, 2 Injection-Halts (MiMo Pro), 1 `unchecked`, weil MiMo Pro unlesbar
  antwortete.
- Gate-Wartezeit: Median 4,7 s, p90 9,6 s, max 13 s.
- 13 Halts gesamt: 9 `ask_user` für den Browser (Rückgabe im Median nach
  8 s), 3 Injection-Halts eines Prüfers und 1 `unchecked`.
- Alle Halts wurden mit `continue` entschieden. Kein einziges `stop`,
  `steer`, `deny` oder Timeout.

**Tokens und Kosten.**

| | Calls | Input | davon Cache | Output | Kosten |
|---|---|---|---|---|---|
| Agent | 379 | 6,84M | 81 % | 250k | $1,75 |
| Prüfer | 418 | 7,88M | 71 % | 148k | $1,13 |
| – live | 303 | | | | $0,40 |
| – Schluss | 115 | | | | $0,73 |

Seit dem 28.10. (31 Turns mit `quota_charged`) machen die Prüfer 22 % der
Kosten aus, aber 48 % des Tageskontingents: 1,64M Prüfer- gegen 1,81M
Agent-Tokens. 80 % des Prüfer-Kontingents entfallen auf die Live-Runden. Je
Turn kosten die Prüfer etwa $0,012–0,016.

**Render-Logs.**
- „Agent reviewer reply unusable“: 5 Zeilen, alle seit 28.10. MiMo Pro kam
  4× mit `no_marks` bzw. `broken_json` (`finish=stop`, keine Reasoning-Tokens).
  DeepSeek kam 1× mit `tool_calls` und 0 Zeichen in einer Gate-Runde, die
  keine Werkzeuge hat.
- „Agent search without citations“: 10 Zeilen, 9× GPT-6.1 Terra (das
  Standard-Chatmodell seit 28.10.), 1× Luna. Alle mit leeren `shapes`: Der
  Stream enthielt keine einzige Spur der Treffer (keine Annotation, kein
  unbekanntes Feld).
- „Agent shutdown“: 30 Zeilen, alle mit 0 laufenden Turns.
- Tracebacks: keiner aus dem Audit.

**Bewertung.** Im beobachteten Normalfall ist der Audit-Modus stabil und
schnell genug. Was fehlt, ist der Beweis für die Fälle, die in den Daten
nicht vorkommen: drei Prüfer, lange Läufe, das Handy, volle Gespräche,
Fehlerpausen, mehrere Halts. Für genau diese Fälle zeigt der Code Lücken
(Abschnitt 4). Ohne bessere Messung (Paket 2) lässt sich Produktionsreife
weder belegen noch überwachen.

## 3. Ein Lauf auf der Zeitachse

Du drückst Senden. Der Agent startet, und jeder Prüfer startet seinen eigenen
Thread (`AnswerAudit.follow`). Der Agent macht einen Schritt, zum Beispiel
einen Befehl in der Werkbank. Die App schreibt ihn ins Arbeitsprotokoll und
führt ihn **sofort** aus. Jeder Prüfer liest die neuen Einträge in einer
Live-Runde, mit bis zu zwei eigenen Suchen. Findet er Gefahr, setzt er einen
Halt: Der Lauf hält vor dem nächsten Schritt, und du entscheidest auf der
Karte. Nur vor zwei Arten von Aufrufen (Domain freigeben, Memory ändern
nach Fremdinhalt) wartet der Agent vorher auf alle Prüfer (Gate).

Dann schreibt der Agent die Antwort. Du siehst sie streamen. Mit dem letzten
Wort wird sie fixiert (`capture`), und jeder Prüfer startet seine
Schlussrunde. Steckt er gerade noch in einer Live-Runde, startet er erst
danach (T1). Die Schlussrunde bekommt den Rest des Protokolls und die
Antwort, mit bis zu drei Suchen. Erst wenn **alle** Prüfer fertig sind,
erscheinen die Marken auf einmal. Solange bleibt der Turn offen, und eine
neue Nachricht wartet in der Schlange.

Kritischer Pfad nach dem letzten Wort, also das Maximum über alle Prüfer:
Rest der laufenden Live-Runde + Schlussrunde + gegebenenfalls zweiter
Versuch + Speichern. Begrenzt ist das heute nur durch den harten Stopp des
Turns (900 + 300 s, in der Werkbank 7.200 + 300 s) und durch die Stille-Grenze
eines Streams (`AGENT_PROVIDER_STALL_SECONDS` = 180).

## 4. Befunde

Schwere: **hoch** = trifft die Sicherheitsschicht oder verliert Arbeit bzw.
Entscheidungen, **mittel** = falsches Verhalten in plausiblen Fällen,
**niedrig** = selten oder nur kosmetisch. „Kein Test“ heißt, dass kein Test
den Fall abdeckt.

### Sicherheit und verlorene Entscheidungen

| ID | Schwere | Ort | Szenario → Folge |
|---|---|---|---|
| S1 | hoch | `agent_delegation.py:1822–1826`, `agent_sessions.py` `decide_hold` | `store.set_hold` scheitert (kurzer Firestore-Fehler) → der Fehler wird nur geloggt, die Karte geht trotzdem raus. Jede Entscheidung (auch `/secret`) bekommt 409 „This pause is already over“. Nach 30 min stoppt der Turn, nur Stop hilft. Kein Test. |
| S2 | hoch | `agent_audit.py:1353–1357, 1366`, `agent_delegation.py:1812–1815` | Halt A ist offen, Prüfer B hält auf einen anderen Eintrag → `request_hold` gibt False zurück (eingereiht wird nur hinter einer ask-Karte), der Schlüssel steht aber schon in `halts`. B kommt nie wieder, sein Grund fehlt auf der Karte und im Protokoll. Dasselbe gilt während einer Gate- oder Domain-Karte. Nur der ask-Fall ist getestet. |
| S3 | mittel | `agent_delegation.py:2592–2611` | Ein Turn-, Wiederholungs- oder Ungültig-Limit führt in den Schlussschritt, und währenddessen hält ein Prüfer → `_finish_merged` fixiert die Antwort ohne `_hold_wait` (der normale Pfad 2876–2883 hat ihn). Die Karte bleibt bis „ended“ stehen, ein Steer-Text landet ungelesen. Kein Test. |
| S4 | mittel | `agent_delegation.py:1820`, Schritt-Schleife | Ein Halt für Schritt N kommt meist, während Schritt N+1 schon beim Anbieter streamt. N+1 läuft zu Ende, mit bis zu 5 Suchrunden. Seine Aufrufe warten zwar (`_hold_wait` zwischen Aufrufen), seine Suchanfragen sind aber schon raus und damit ein möglicher Kanal, über den Daten abfließen. Code verifiziert, Risiko vermutet. |
| S5 | mittel | `routers/agent.py:878` (`AgentHoldDecision.action`), `agent_delegation.py:1903` | `deny` wird für jeden Halt angenommen. Bei einem Prüfer- oder Gate-Halt wird daraus `continue`, und ein gegatetes `update_memory` läuft. Die Oberfläche bietet `deny` dort nicht an; erreichbar ist es nur über einen eigenen API-Aufruf. |
| S6 | hoch | `static/js/workspace-view.js:52, 504–505`, `agent_workspace.py:89` (`CONTROL_SECONDS` 90), `agent_delegation.py:2049–2052` | Der Nutzer hat den Browser (ask_user `browser`), das Handy wechselt in die 2FA-App oder die Seite lädt neu → JS-Intervall steht, die Übernahme läuft nach 90 s ab, `_handed_back` meldet „handed_back“, und der Agent übernimmt mitten im Login. Gewollter Ablauf getestet (`test_a_browser_card_waits_until_the_user_had_the_browser`), der Handy-Fall nicht. |
| S7 | hoch | `static/js/agent-chat.js:1336, 1346–1348` | Eine Key-Karte (ask `secret`) ist offen, und der Nutzer fügt den Key ins Hauptfeld ein und drückt Enter → `steer` → `user_notes`. Der Key landet beim Agenten, bei den Prüfern und 30 Tage im Arbeitsprotokoll, genau das, was die Karte verhindern soll. Kein Test. |

### Tempo

| ID | Schwere | Ort | Befund |
|---|---|---|---|
| T1 | mittel | `agent_audit.py:1021–1039, 1563–1566` | Die Schlussrunde wartet auf eine laufende Live-Runde desselben Prüfers. Gemessen bisher ≤ 6 s, im schlimmsten Fall eine ganze Live-Runde (MiMo Pro max 53 s). Die Live-Runde ist danach doppelt bezahlt, weil die Schlussrunde dieselben Einträge liest (`entries_after(self.cursor)`). Kein Test. |
| T2 | hoch | `agent_audit.py` `_final`, `_request`; `worker_request` | Die Schlussrunde hat weder eine eigene Frist noch Hedging. Der langsamste Prüfer bestimmt Z1 (Luna p90 40 s, max 72 s). Der Turn bleibt solange `pending`, der Chat gesperrt; die Grenze ist nur der harte Stopp (bis ~19 min, in der Werkbank ~2 h). |
| T3 | mittel | `agent_delegation.py:1874–1886, 1934–1946` | Das Gate hat keine eigene Frist. Es wartet auf die laufende Live-Runde jedes gefragten Prüfers (die Gate-Runde kommt erst danach, `ReviewerSession.run`), und diese Zeit zählt zur Turn-Zeit (nur Halts pausieren die Uhr). Seit 29.10. selten (nur Domain/Memory). |
| T4 | niedrig | Wächter-Takt 3 s, `agent_delegation.py:1774` | Eine Entscheidung auf der Karte erreicht den Lauf erst mit dem nächsten Wächter-Poll (bis 3 s), obwohl Endpunkt und Lauf im selben Prozess laufen. |
| T5 | vermutet | `agent_sessions.py:99–103`, `agent_quota.py:50–54` | Ein Prozess-Lock je Konto (128 Stripes) reiht `claim`/`settle` von bis zu 6 Prüfern und dem Agenten hintereinander, jeweils mit einer Firestore-Rundreise. Zu Beginn der Schlussrunde kommen bis zu 6 Claims nacheinander. Der Beitrag zur Latenz ist nicht gemessen (Fixieren → erste Schluss-Anfrage max 5,7 s). |

### Robustheit Server

| ID | Schwere | Ort | Befund |
|---|---|---|---|
| R1 | mittel | `agent_delegation.py:2270–2272, 2894–2897`, `agent_runs.py:527–544` | Eine Unterbrechung **nach** der fixierten Antwort (Deploy nach der Grace-Zeit, Firestore > 60 s weg, Wächter-Stopp, also `watch_error`) macht den Turn `failed` („server restarted“). Ein Nutzer-Stopp an derselben Stelle lässt ihn `completed` (getestet). |
| R2 | mittel | `agent_delegation.py:1191–1192, 1028, 733, 2566` | Das Tageskontingent hat im Audit-Modus keine Reserve für das Ende: Überziehen und der Schlussschritt nach Ablehnung gibt es nur nach bezahlten Vergleichen, und im Audit gibt es nie Vergleiche. Nahe am Limit kann der Turn ohne Antwort enden, oder die Schlussrunde wird abgelehnt. Code verifiziert, Häufigkeit vermutet. |
| R3 | mittel | `agent_audit.py` `_gate_round`, `_request` | Eine unlesbare Gate-Antwort (DeepSeek: Tool-Call statt JSON) bekommt keinen zweiten Versuch und führt sofort zur Karte `unchecked`. Gezählt wird sie als `provider_error` statt als unlesbar. |
| R4 | niedrig | `agent_delegation.py:2916`, `agent_audit.py:1599`, `agent_journal.py:131`, `:1769` | Joins beim Aufräumen haben keinen Timeout. Hängt ein Thread, wartet `finish_run`, bis die Lease nach 120 s abläuft und der Reaper `run_interrupted` schreibt. Beim Prod-Shutdown darf allein `work_log.close` 20 s dauern. |
| R5 | niedrig | `agent_delegation.py:2109`, `agent_runs.py:528` | Eine unbeantwortete Domain-Karte stoppt nach 30 min den ganzen Turn, statt wie „Nicht erlauben“ zu wirken. Ein Hold-Timeout setzt keinen eigenen Fehlercode, der Turn zeigt nur „Response stopped“. |
| R6 | niedrig | zwischen `agent_delegation.py:2876` und `agent_audit.py:1563` | Ein Halt in diesem schmalen Fenster zeigt eine Karte, die nichts mehr bewirkt (`halt` verwirft sie erst ab `final_answer`), und die Turn-Uhr steht still. Der Fall ist laut Kommentar 2929–2931 bekannt. |
| R7 | niedrig | `agent_runs.py:541–558` | Nach Crash oder Reap setzt `finish_run` nur `review.status`, einzelne `audit.reviewers[].status` bleiben `running`. |
| R8 | niedrig | `agent_live.py:46–49` | `ACTIVE_TTL` gilt 3 h nach Wanduhr. Ein Werkbank-Turn mit 7.500 s Laufzeit plus Pausen überschreitet das, dann ist der Live-Puffer weg. |
| R9 | niedrig | `agent_delegation.py:1826, 2086` | `put_nowait` ohne Schutz gegen `queue.Full`. Ist die Queue voll, steht der Halt ohne Karte im Speicher, und der Prüfer-Thread stirbt. Sehr unwahrscheinlich. |
| R10 | niedrig | Wächter, `agent_ask.py:48` | Während einer 30-min-Pause liest der Wächter 2 Dokumente alle 3 s (~1.200 Reads), eine Browser-Karte zusätzlich `control_state` jede Sekunde (~1.800 Reads). |
| R11 | niedrig | `agent_background.py` Drain (Prod 280 s) | Ein Lauf, der beim Deploy in einer Pause wartet, überlebt den Neustart nicht (Threads sind prozesslokal). Bisher unbeobachtet, weil 30 von 30 Shutdowns keinen laufenden Turn hatten. |

### Abbrüche im Browser

| ID | Schwere | Ort | Befund |
|---|---|---|---|
| B1 | hoch | `static/js/agent-live.js:66, 161, 230, 289–297`, `agent-chat.js:2377–2382, 2600–2605` | `followSince` wird nur bei Poll-Ereignissen neu gesetzt, `bytes()` setzt ihn nie, und `poll()` prüft `MAX_FOLLOW_MS` (40 min) vor dem Abruf. Folgt der Browser einem gesunden Lauf länger als 40 min, beendet ihn das nächste `visibilitychange` oder `online`: „Connection lost“, `failRun`, `forgetPending`. Die Karte einer Pause verschwindet, und der Lauf stoppt nach 30 min. Lange Werkbank-Läufe auf dem Handy sind genau dieser Fall. Kein Test. |
| B2 | hoch | `agent-chat.js:1944–1945, 497–539, 2057–2061`, `run-view.js:218–228`, `tab-status.js:20–26` | Die Karte erscheint nur im sichtbaren Lauf und nur, wenn `selectedMode()` gerade `agent` ist. Ein pausierter Lauf in einem anderen Chat zeigt in der Seitenleiste „Working“ mit Spinner, der Tab-Titel bleibt stumm. Ein zweiter Tab oder ein zweites Gerät zeigt den Turn statisch, ohne Folgen und ohne Karte, denn Resume gibt es nur aus dem `sessionStorage` desselben Tabs. Sicherheitspausen und `ask_user` laufen so ungesehen in den Timeout. Kein Test. |
| B3 | mittel | `agent-chat.js:1520–1524, 1572–1575, 1368–1370, 1980` | Der Entscheidungs-POST hat keine Frist. Bei einer halboffenen Verbindung hängt er minutenlang, alle Knöpfe der Karte sind gesperrt (auch Stop), und kein Text sagt „wird gesendet“. Kein Test. |
| B4 | mittel | `agent-chat.js:1320–1322, 1354–1357, 2124–2125` | Wartende Nachrichten (`#agentQueue`) leben nur im Speicher. Reload oder Tab-Verwurf verliert sie, zum Beispiel alles, was während der Schlussprüfung getippt wurde. Das widerspricht dem Kommentar „never lost“. Kein Test. |
| B5 | niedrig | `agent-chat.js:2437–2467`, `agent-review.js:687, 697` | `failRun` lässt die Prüfung auf `running`. Die Aktivität zeigt bis zum Neuöffnen „Reviewing the answer…“. |
| B6 | niedrig | `agent-chat.js:1528–1538` | Nach `hold_over` (anderswo entschieden, Stream tot) bleibt die Karte mit aktiven Knöpfen stehen. |
| B7 | niedrig | `agent_sessions.py:508` | „This pause is already over.“ hat keine deutsche Fassung, und `scripts/i18n.py missing` erfasst diesen Server-Text nicht. |
| B8 | niedrig | `agent-review.js:529–530, 704, 758` | Bei `cancelled`/`missing` sind die Live-Befunde der Prüfer nicht erreichbar, auch nicht nach einem Stopp wegen einer Pause. |
| B9 | niedrig | `agent-activity.js:415–417` | Die Obergrenze von 63 Hilfseinträgen schließt `hold` ein. In langen Läufen fallen frühere Pausen aus der Live-Aktivität (der gespeicherte Turn hat sie). |
| B10 | vermutet | `agent-activity.js:1041–1059, 573–576, 407, 416`, `agent-work-log.js:176–181` | Jedes Rendern (100-ms-Takt) serialisiert die Ausgabe aller VM-Schritte, `receive` ist O(n) je Ereignis, das Aufholen nach einem Reload also O(n²). Ob es spürbar ruckelt, ist nicht gemessen. |

### Kontingent und Quellen

| ID | Schwere | Befund |
|---|---|---|
| K1 | strategisch | Die Prüfer verbrauchen 48 % des Tageskontingents eines Audit-Laufs bei 22 % der Kosten. Das Kontingent zählt Tokens (Cache-Treffer zu 25 %), und Prüfer schicken in jeder Runde ihr ganzes Gespräch erneut. Ein Audit-Lauf verbraucht so fast doppelt so viel Kontingent wie derselbe Lauf ohne Prüfer. |
| K2 | mittel | Cache-Trefferquote der Prüfer 71 % gegen 81 % beim Agenten. Je Modell nicht ausgewertet. Qwen ist mit 9 Instanzen der teuerste Prüfer ($0,30). |
| K3 | mittel | Bei GPT-6.1 Terra (Standard-Chatmodell) und Luna kommen die Suchtreffer oft gar nicht im Stream an (leere `shapes`). Die Prüfer sehen dann nur `searches: n`, können die Quellen nicht nachprüfen, und der Agent kann seine eigenen Treffer nicht mit `read_source` lesen. Wie oft das bei allen Terra-Suchschritten passiert, ist nicht gemessen. |

### Messlücken

| ID | Lücke |
|---|---|
| G1 | Wird ein Chat gelöscht, verschwinden Turn, Sitzungen und Protokoll. Der Beleg am Root sagt nicht, ob es ein Audit-Lauf war (65 Turns fehlen). |
| G2 | Belege (`llm_calls`) sagen nicht, ob ein Call eine Live-, Gate-, Schluss- oder Reparaturrunde war. |
| G3 | Die Urteile der einzelnen Prüfer im Gate und Start und Ende des Gates werden nicht gespeichert, nur `checked`/`paused`. |
| G4 | `following=False`, Fehlerpausen, ein neues Gespräch bei vollem Kontext und der Rückstand beim Fixieren hinterlassen keine Spur. |
| G5 | Die Historie der Halts steht nur im Protokoll (30 Tage) und in der begrenzten `agent_activity`; am Root steht nur der letzte Halt. |
| G6 | `failure.code` vermischt Ursachen: Ein Tool-Call statt JSON zählt als `provider_error`. |
| G7 | Live-Befunde eines Laufs, der vor der Antwort gestoppt wird, stehen nur in den Sitzungsnachrichten, nicht in `agent_review`. |
| G8 | Es gibt kein Skript im Repo, das diese Messung wiederholt (die Skripte lagen nur im Scratchpad). |

### Langlauf und Last

| ID | Schwere | Befund |
|---|---|---|
| L1 | hoch | In Prod nie durchlaufen: drei Prüfer, ein neues Gespräch bei vollem Kontext (`_fresh`/`_carry`), die Fehlerpause, `following=False`, ein Werkbank-Lauf über 10 min mit Prüfern, mehrere gleichzeitige Audit-Turns auf einer Instanz (Render Starter, 0,5 CPU). Je Audit-Turn laufen 4 + n Threads (Lauf, Wächter, Journal, Protokoll-Writer, n Prüfer) über die ganze Laufzeit. |
| L2 | mittel | `tests/test_agent_tempo.py` deckt den Audit-Modus nicht ab, es gibt keinen Tempo- oder Lasttest mit Prüfern. |

**Was gut gelöst ist (bleibt so):**
- Hold-IDs mit `replaces` und die Entscheidung in einer Transaktion: Doppelklick
  und zwei Tabs bekommen 409.
- Ein Nutzer-Stopp in der Schlussrunde stoppt nur die Prüfer, die Antwort
  bleibt.
- Ein Prüfer, der nicht antworten kann, ist nie ein Go.
- Der VM-Interrupt prüft `loop.hold` unter dem Session-Lock.
- Der `hold`-Frame ist sticky und kommt nach Reload wieder.
- `close()` und `finish_run` lassen keine Review in `required`/`running`
  stehen.
- Nach dem Turn-Ende läuft kein Prüfer-Thread weiter.

## 5. Anforderungen

Jede Anforderung nennt, was gelten muss, und wie es abgenommen wird. Tests
laufen ohne Modellkosten (Fakes, `MOCK_LLM`), Browser-Fälle in `tests/js` bzw.
gezielt in `tests/e2e`. Wo eine Anforderung Verhalten ändert, das in
`docs/agent-mode.md` oder `docs/codebase-map.md` steht, wird dort im selben
Commit nachgezogen.

### Paket 1 · Sicherheit und verlorene Entscheidungen (zuerst)

- **A-S1 Eine Pause ist immer entscheidbar.** `set_hold` wird wiederholt (3
  Versuche mit Backoff, wie `WRITE_ATTEMPTS`). Scheitert er endgültig,
  nimmt der Endpunkt die Entscheidung trotzdem an: Er prüft die Hold-ID gegen
  den laufenden Lauf im selben Prozess (`agent_background` kennt ihn) und gibt
  sie direkt an `DelegationLoop` (siehe A-T4). Erst danach kommt `409
  hold_over`.
  *Abnahme:* Test, in dem `set_hold` wirft: `continue`, `steer`, `stop` und
  `/secret` wirken trotzdem.
- **A-S2 Kein Halt geht verloren.** Ein Halt bei offener Pause wird in die
  offene Karte übernommen (`reasons`, Frame `hold` neu gesendet, Protokoll
  `paused` mit dem zweiten Grund). Bei einer ask-Karte bleibt es bei
  `queued_hold`. Der Schlüssel in `AnswerAudit.halts` wird erst gesetzt, wenn
  der Halt angezeigt oder angehängt wurde.
  *Abnahme:* Tests für Halt während Prüfer-Halt, Gate-Karte und Domain-Karte.
- **A-S3 Der Schlussschritt respektiert offene Halts.** Vor `_finish_merged`
  im Limit-Pfad (2611) gilt derselbe `_hold_wait`- und Steer-Zweig wie bei
  2876.
  *Abnahme:* Test „Turn-Limit + Halt während des Schlussschritts → Antwort
  wartet auf die Entscheidung“.
- **A-S4 Ein Halt stoppt auch den laufenden Modellschritt.** `request_hold`
  bricht einen streamenden Agentenschritt ab (eigene Cancellation je Schritt,
  nicht die des Turns). Nach `continue` läuft dieser Schritt neu; die
  abgebrochenen Kosten werden wie bei `_passing_failure` mit dem verbrauchten
  Stand abgerechnet. Halts sind selten (3 in 79 Turns), die doppelten Kosten
  zählen also nicht.
  *Abnahme:* Test „Halt während Schritt N+1 → N+1 abgebrochen, nach continue
  neu, nach steer mit der Nachricht“.
- **A-S5 `deny` nur, wo es etwas bedeutet.** Der Endpunkt nimmt `deny` nur
  für Holds mit `domain` oder `ask: confirm` an, sonst `422`. Intern wird
  `deny` nie zu `continue`.
  *Abnahme:* Route-Test.
- **A-S6 Ablauf ist keine Rückgabe.** Solange eine ask-Karte `browser` offen
  ist, zählt nur ein ausdrückliches „Hand back“ oder das Schließen der Ansicht
  als Rückgabe. Ein Ablauf von `control` (90 s ohne Refresh) bleibt „der
  Nutzer hat den Browser“. Zusätzlich frischt `workspace-view.js` die
  Übernahme bei `visibilitychange` → sichtbar sofort auf.
  *Abnahme:* Server-Test „control abgelaufen bei offener browser-Karte → kein
  handed_back“; JS-Test für das Auffrischen beim Sichtbarwerden.
- **A-S7 Keys nie über das Hauptfeld.** Ohne Erkennung von Schlüsseln (keine
  Muster, kein Raten am Text): Es zählt nur der Zustand. Hat der Agent um
  einen Key gebeten und die Key-Karte ist offen (`hold.ask === "secret"`),
  wird Text im Hauptfeld nie als Nachricht gesendet. Enter legt ihn verdeckt
  ins Key-Feld der Karte, und der Nutzer bestätigt dort mit einem Klick
  („Als Key speichern“). Wer statt eines Keys etwas schreiben will („hab ich
  nicht“), nimmt „Write to the agent“ an der Karte. Ein Key, den jemand
  ungefragt in eine normale Nachricht schreibt, bleibt eine normale
  Nachricht: Das ist seine Wahl, wie in jedem Chat.
  *Abnahme:* JS-Test „Key-Karte offen + Enter im Hauptfeld → kein steer,
  Text steht verdeckt im Key-Feld“.

### Paket 2 · Messbarkeit

- **A-M1 Tageszähler, die das Löschen überstehen.** Am Turn-Ende schreibt die
  App anonyme Tagesaggregate (`ops_metrics/agent-audit-{YYYY-MM-DD}`, ohne
  UID, ohne Inhalte): Turns je Status, Prüferzahl, Histogramm-Buckets für
  Gesamtzeit, Zeit bis zur Antwort, Marken nach dem letzten Wort, Gate-Wartezeit
  und Dauer der Schlussrunde je Modell, Zähler für Halts je Art und
  Entscheidung, Ausfälle je Code. Ein Increment je Turn per Transaktion, nie
  auf dem kritischen Pfad, Fehler nur geloggt. (Datenschutz: kein
  Personenbezug.)
- **A-M2 Rundenart am Beleg.** `llm_calls` bekommt `round: live | gate | final
  | repair | hedge` für Prüfer-Calls.
- **A-M3 Gate-Spur.** Der App-Eintrag `checked`/`paused` trägt `gate_ms` und
  die Urteile je Prüfer (`go`/`halt`/`failed`, Modell, `ms`) als strukturierte
  Felder.
- **A-M4 Prüferzustand in der Review.** `audit.reviewers[]` bekommt die
  Zähler `fresh` (neue Gespräche), `pauses` (Fehlerpausen),
  `unfollowed_at_seq`, `backlog` beim Fixieren (`entries`, `steps`, Sekunden
  seit Rundenbeginn), `final_ms` und `hedged`.
- **A-M5 Halt-Historie.** `agent_holds[]` am Turn (höchstens 20): `kind`,
  `gate`, `ask`, `domain`, Prüfermodell, `decision`, `seconds`, ohne Grundtext.
- **A-M6 Ehrliche Fehlercodes.** Eine Antwort mit Tool-Call statt JSON heißt
  `review_tool_calls`, eine leere `review_empty`; `provider_error` bleibt für
  Fehler des Anbieters.
- **A-M7 Live-Befunde gestoppter Läufe.** Bei `cancelled` speichert die Review
  die Live-Befunde wie bei einer gescheiterten Schlussrunde (`live: true`).
  Notes zeigt sie (zugleich B8).
- **A-M8 Messskript im Repo.** `scripts/audit_report.py` (nur lesen, Muster
  `scripts/cache_hit_rate.py`) liefert die Tabellen aus Abschnitt 2 und die
  Ziele Z1–Z8 aus Turns, Belegen und A-M1, mit `--days`, `--exclude-own`,
  `--json`.
- **A-M9 Treffer-Diagnose für Terra/Luna (K3).** Messen, welcher Anteil aller
  Suchschritte von Terra 6.1 ohne Treffer bleibt (Metrik
  `search_without_citations` gegen alle Suchschritte). Bleibt er hoch,
  bekommen OpenAI-Modelle im Agenten die Suchmaschine `exa` (wie Grok).
  Kosten und Qualität dieser Umstellung entscheidet Max anhand der Zahl.

*Abnahme Paket 2:* `audit_report.py` gibt für einen Testdatensatz (Emulator
oder Fake) alle Kennzahlen aus; Unit-Tests für A-M1 bis A-M7.

### Paket 3 · Tempo

- **A-T1 Schlussrunde sofort.** Wird die Antwort fixiert, bricht jeder Prüfer
  seine laufende Live-Runde ab. Der Cursor bleibt stehen, die Einträge gehen
  in die Schlussrunde, und Halts gibt es ab dann ohnehin nicht mehr. Dafür
  braucht jede Runde eine eigene Cancellation unter der des Prüfers;
  `ProviderCancelled` aus diesem Abbruch beendet weder den Thread noch die
  Sitzung.
  *Abnahme:* Test mit Fake-Prüfer, dessen Live-Runde 30 s dauert: Die
  Schlussrunde beginnt < 1 s nach dem Fixieren.
- **A-T2 Hedging und Frist für die Schlussrunde.** Hat ein Prüfer nach
  `FINAL_HEDGE_SECONDS` keine Antwort, startet eine zweite Anfrage auf neuer
  Sitzung mit denselben Nachrichten. Die erste brauchbare gewinnt, die andere
  wird abgebrochen. Der Wert ist je Modell das p75 seiner Schlussrunden aus
  den Belegen, mindestens 12 s, ohne Daten 20 s. Hart begrenzt wird die
  Schlussrunde durch `FINAL_ROUND_SECONDS` (90 s, inklusive zweitem
  Versuch), danach `no_time`: Es gelten die Live-Befunde, die Antwort steht.
  Denkstufe und Suchrunden bleiben unverändert (keine Abstriche). Vorher den
  Anteil der eigenen Wartezeit gegen OpenRouter-`generation_time` messen
  (wie bei der Tempo-Analyse vom 2026-10-21: eigene Zeitstempel gegen
  `created_at`/`latency`/`generation_time`): Ist Luna selbst langsam, hilft der
  Hedge auf einen anderen Endpunkt; liegt es an unserer Schlange, A-T5.
  *Abnahme:* Test mit Fake, der beim ersten Versuch hängt: Marken nach
  Hedge-Zeit + Antwortzeit; Test „beide hängen → no_time nach 90 s, Turn
  completed“.
- **A-T3 Gate mit Frist und Vorrang.** Eine Gate-Runde bricht eine laufende
  Live-Runde desselben Prüfers ab (ihre Einträge gehen ins Gate). Jeder Prüfer
  hat `GATE_SECONDS` = 20 s, danach zählt er als `failed`, also Karte
  `unchecked`, nie ein Go. Eine unlesbare Gate-Antwort bekommt innerhalb der
  Frist einen Reparaturversuch (`REPAIR_NOTE`, auch bei Tool-Call). Die
  Gate-Wartezeit pausiert die Turn-Uhr wie ein Halt.
  *Abnahme:* Tests für „Live-Runde läuft beim Gate“, „Prüfer schweigt 20 s“,
  „Tool-Call statt JSON → Reparatur → go“.
- **A-T4 Entscheidungen im Prozess zustellen.** `POST …/hold`, `/notes` und
  `/stop` wecken den Lauf im selben Prozess sofort (Condition), Firestore
  bleibt die Wahrheit für andere Instanzen. Der Wächter-Takt bleibt das Netz.
  *Abnahme:* Test „Entscheidung → Lauf geht < 0,5 s weiter“.
- **A-T5 Konto-Lock messen, dann bündeln.** Zeit unter
  `agent_quota.account_lock` je Turn messen (Metrik). Liegt der Anteil an der
  Zeit Fixieren → erste Schluss-Anfrage über 1 s, Claims der Schlussrunde in
  eine Transaktion bündeln (wie `publish_agents`).
  *Stand 2026-10-29:* gemessen (`AgentSessionStore.lock_time`, Metriken
  `agent_account_lock:waited`/`held`/`final_rounds`, Logzeile je Turn),
  gebündelt noch nicht: Jeder Prüfer beansprucht seine Anfrage in seinem
  eigenen Thread über `_admit_chat_step` mit eigener Reservierung; eine
  gemeinsame Transaktion bräuchte einen Sammelpunkt quer über diese Threads
  im Claim-Pfad, und ihr Nutzen ist erst mit den Zahlen belegt.

### Paket 4 · Abbrüche und Randfälle

Server:
- **A-R1** Nach der fixierten Antwort ist jede Unterbrechung ein Stopp der
  Prüfung: Turn `completed`, Review `cancelled` mit Live-Befunden (A-M7).
  Test mit `watch_error` in der Schlussrunde.
- **A-R2** Im Audit-Modus dürfen der Schlussschritt des Agenten und die
  Schlussrunden der Prüfer das Tageskontingent überziehen, wie die Judges im
  Vergleichsmodus. Die Reserve für lange Läufe (`_long_run_limit`) rechnet die
  Prüfer mit ein (geschätzt aus ihrem bisherigen Verbrauch im Turn).
- **A-R3** Joins beim Aufräumen bekommen Fristen (Prüfer 10 s nach dem
  Abbruch, Journal und Protokoll zusammen höchstens 15 s). Danach wird ein
  Log mit dem Thread-Namen geschrieben, und `finish_run` läuft trotzdem.
- **A-R4** Eine unbeantwortete Domain-Karte wirkt nach 30 min wie „Nicht
  erlauben“, der Lauf geht weiter. Der Hold-Timeout eines Prüfer- oder
  Gate-Halts setzt `failure.code = hold_timeout` mit eigenem Text („Paused
  for 30 minutes without a decision, so the response stopped.“ samt
  deutscher Fassung).
- **A-R5** Ab dem Fixieren der Antwort nimmt `request_hold` keinen
  Prüfer-Halt mehr an (Fenster R6 schließen). Eine schon offene Karte endet
  mit `ended`.
- **A-R6** `finish_run` setzt nach Crash oder Reap auch jede
  `audit.reviewers[]`-Zeile in `waiting`/`running` auf `failed`
  (`run_interrupted`).
- **A-R7** Der Live-Puffer verlängert seine TTL mit jedem Frame (3 h ab dem
  letzten Frame, nicht ab dem Start).
- **A-R8** `outgoing.put_nowait` an Halt-Stellen fängt `queue.Full` ab: Der
  Halt bleibt sticky im Live-Puffer, der Prüfer-Thread lebt weiter.
- **A-R9** Während einer Pause pollt der Wächter alle 10 s statt alle 3 s
  (A-T4 stellt Entscheidungen sofort zu), und `control_state` wird alle 3 s
  gelesen statt jede Sekunde.
- **A-R10** Deploys: Das Deploy-Vorgehen (Render-API, manuell) prüft
  vorher, ob Agent-Turns laufen oder pausiert sind, und nennt sie. Ein Turn,
  der vor der Antwort durch den Neustart endet, speichert wie heute seinen
  `agent_work_record`.

Browser:
- **A-B1** `agent-live.js`: `followSince` wird auch in `bytes()` neu gesetzt,
  und das Folgelimit greift erst nach einem leeren Poll ohne Stream-Bytes.
  Während einer offenen Pause gilt es gar nicht. Test mit Fake-Uhr über 40 min.
- **A-B2** Eine offene Pause ist überall sichtbar: Die Zeile in der
  Seitenleiste und der Tab-Titel sagen „Paused“ bzw. „Needs you“, auch für
  einen nicht sichtbaren Chat und unabhängig von `selectedMode()`. Öffnet
  man einen Chat mit laufendem Turn (anderer Tab, anderes Gerät), folgt der
  Browser ihm über `/live` mit der `request_id` am Turn und zeigt die Karte.
  Tests: JS für Zeile und Titel, e2e „zweiter Tab sieht die Karte“.
- **A-B3** Der Entscheidungs-POST läuft unter `App.withRequestDeadline`
  (15 s) und zeigt „Sending…“. Stop ist nie gesperrt.
- **A-B4** Die Warteschlange `#agentQueue` steht im Pending-Eintrag
  (`sessionStorage`) und überlebt einen Reload.
- **A-B5** `failRun` setzt die Prüfung wie `cancelRun` auf einen Endzustand
  (B5). `hold_over` schließt die Karte (`holdDone`, B6).
- **A-B6** Alle neuen und bestehenden Server-Texte an Karten haben ihre
  deutsche Fassung, und `scripts/i18n.py missing` erfasst auch die
  Fehlertexte von `agent_sessions.py` (B7).
- **A-B7** Ältere Pausen bleiben in der Live-Aktivität (eigenes Kontingent
  außerhalb der 63 Hilfseinträge, B9).
- **A-B8** Rendern vergleicht je Eintrag eine Revision statt des Inhalts, und
  `receive` arbeitet über eine Map (B10). Erst messen: 200 VM-Schritte in
  `tests/e2e` mit Performance-Trace; nur bei > 16 ms je Render umsetzen.

### Paket 5 · Langlauf, Last, Tests

- **A-L1 Tempo-Test für den Audit-Modus.** `tests/test_agent_audit_tempo.py`
  nach dem Muster von `test_agent_tempo.py`: Fake-Prüfer mit gemessenen
  Latenzen (Abschnitt 2), drei und sechs Prüfer, 40 Werkzeug-Schritte. Er misst
  den Server-Anteil je Runde, die Marken nach dem letzten Wort, die
  Gate-Wartezeit und die Zahl lebender Threads nach dem Turn-Ende (muss 0
  sein).
- **A-L2 Langlauf-Test.** Ein simulierter Werkbank-Lauf mit 200 Schritten
  und großen Ausgaben zwingt jeden Prüfer mindestens einmal in ein neues
  Gespräch (`_fresh`/`_carry`), einmal in die Fehlerpause und einmal in
  `following=False`. Danach muss die Schlussrunde mit den bisherigen Befunden
  kommen. Dazu eine Speicher-Obergrenze für `WorkLog._entries` je Turn messen
  und dokumentieren.
- **A-L3 Parallelität.** Zwei bis drei gleichzeitige Audit-Turns mit je drei
  Prüfern in einem Prozess (Fakes mit realistischen Firestore-Rundreisen wie in
  `test_agent_tempo.py`): Z1 darf sich gegenüber einem Einzellauf um höchstens
  20 % verschlechtern.
- *Stand 2026-10-29* (A-L1 bis A-L3 in `tests/test_agent_audit_tempo.py`,
  rund 40 s): Fakes mit den Latenzen aus Abschnitt 2 im Maßstab 1:40, eine
  Rundreise 0,1 s Prod, Transaktionen parallel bis auf den Konto-Lock;
  gemessen unter Windows mit 4 Kernen. Die CPU-Zeit des Servers skaliert
  nicht mit, in Prod-Sekunden umgerechnete Server-Anteile sind zu hoch.
  - A-L1 (40 Schritte, Luna hängt in der ersten Schlussanfrage, MiMo Pro
    steckt beim Fixieren in einer Live-Runde, ein Gate-Schritt): Marken nach
    dem letzten Wort 0,95–1,02 s mit drei, 1,02–1,11 s mit sechs Prüfern,
    davon 0,83 s Hedge-Weg (20 s Hedge-Zeit + Lunas Median 13 s). Erste
    Schlussanfrage 0,13 bzw. 0,20–0,25 s nach dem Fixieren, Server je
    Live-Runde Median 32–47 bzw. 63–79 ms, Gate 0,19–0,27 s (unter
    `GATE_SECONDS`, ≈ 8–11 s Prod). Beide Anfragen hängen: Marken nach
    2,33 s (90 s + Speichern), `no_time`. Nach jedem Turn 0 lebende Threads.
  - Befund Konto-Lock: Jede Prüfer-Runde kostet rund vier Transaktionen
    unter `account_lock` (Claim, Abrechnung, zwei Sitzungs-Updates des
    Journals). Mit drei Prüfern war der Lock rund 60 % der Turn-Zeit belegt,
    mit sechs rund 85 %; der Server-Anteil je Agentenschritt stieg von 37 ms
    (ohne Prüfer) auf 38–53 bzw. 69–100 ms, der Turn dauerte 6,2–7,0 bzw.
    7,3–9,0 s statt 4,5 s. Das ist die Zahl für A-T5.
  - Befund Hedge-Zeit: `FINAL_HEDGE_SECONDS` (20 s) liegt auf Qwens Median.
    Bis acht Schlussrunden eines Modells im Prozess liefen, bekommt etwa
    jede zweite Qwen-Schlussrunde einen Hedge (hier in jedem Lauf), also
    eine zweite bezahlte Anfrage. Bei rund zehn Audit-Turns am Tag und einem
    Neustart je Deploy wird die Schwelle selten erreicht.
  - A-L2 (199 Befehle mit voller Ausgabe, dann die Antwort): Jeder Prüfer
    ging 26–28-mal in ein neues Gespräch, machte eine Fehlerpause, folgte ab
    Schritt 190 nicht mehr, und seine Schlussrunde kam in einem neuen
    Gespräch mit allen Live-Befunden; `fresh`, `pauses` und
    `unfollowed_at_seq` stimmen. Protokoll im Speicher: 496 Einträge, 4,9
    Mio. Zeichen, rund 5 MB ([agent-work-log.md](agent-work-log.md)). Mit dem
    echten Tokenizer dauerte derselbe Lauf 17 statt 4 s: `input_estimate`
    (tiktoken über das ganze Gespräch, bei jeder Reservierung) kostete 20 s
    CPU in 1.528 Aufrufen. Auf Render Starter (0,5 CPU) hält das unter dem
    GIL jeden Thread des Prozesses auf.
  - A-L3 (drei Turns zugleich mit Daily, zwei in einem Konto, einer in
    einem anderen; Tokens aus den Zeichen gezählt, weil der Tokenizer im
    Maßstab 1:40 den GIL sättigt): kein Deadlock, keine Threads danach. Der
    Turn im eigenen Konto: Marken 0 bis +15 % gegenüber dem Einzellauf
    (0,41–0,44 s), das Ziel hält. Die zwei Turns eines Kontos: +7 bis
    +54 %, das Ziel hält nicht; ihr Server-Anteil je Live-Runde stieg von 32
    auf 94–140 ms, ihre Werkbank-Schritte liefen etwa 50 % langsamer.
    Ursache: der gemeinsame Konto-Lock. Der Test prüft deshalb ≤ 20 % (plus
    50 ms Uhrschritt) für das eigene Konto und < 2× für ein geteiltes.
- **A-L4 Echter Smoke nach Deploy** (`docs/smoke-checklist.md` ergänzen):
  Daily mit drei Prüfern, ein Werkbank-Lauf über 10 min, auf dem iPhone
  ein Halt mit App-Wechsel und Rückkehr, eine Browser-Übergabe mit
  2FA-App-Wechsel, ein zweites Gerät öffnet den pausierten Chat.

### Paket 6 · Kontingent und Kosten

- **A-K1 Cache der Prüfer.** Die Cache-Trefferquote je Prüfermodell mit
  `scripts/cache_hit_rate.py` auswerten (Art `audit`). Wo sie unter 80 %
  liegt, Ursache suchen (Endpunkt-Wechsel trotz `x-session-id`, Reasoning im
  Verlauf, Präfix ändert sich) und beheben. Das spart ohne Abstriche.
- **A-K2 Gewicht der Prüfer im Kontingent.** Umsetzung je nach Max'
  Entscheidung (Abschnitt 7): Prüfer-Tokens zählen im Tageskontingent mit dem
  Faktor `AUDIT_REVIEWER_QUOTA_WEIGHT` (in `agent_quota.measured_tokens`,
  Belege mit `round` aus A-M2). Die Live-Runden behalten ihre Suchen und
  Denkstufen.

## 6. Reihenfolge und Umfang

| Paket | Inhalt | Umfang | Abhängigkeit |
|---|---|---|---|
| 1 | A-S1 bis A-S7 | klein bis mittel, je Punkt ein Commit | keine; A-S1 nutzt A-T4, das dafür vorgezogen wird |
| 2 | A-M1 bis A-M9 | mittel | keine; vor Paket 3, damit Vorher/Nachher messbar ist |
| 3 | A-T1 bis A-T5 | mittel, A-T2 am größten | A-M2, A-M4 für die Messung |
| 4 | A-R1 bis A-R10, A-B1 bis A-B8 | mittel, viele kleine Punkte | A-B2 braucht die `request_id` am Turn |
| 5 | A-L1 bis A-L4 | mittel | A-T1 bis A-T3 (sonst misst A-L1 den alten Stand) |
| 6 | A-K1, A-K2 | klein | A-M2; A-K2 erst nach Max' Wort |

Jedes Paket geht direkt auf `main`, mit Tests, Doku und `npm run build` bei
Änderungen unter `static/`. Deploy nur auf Max' Ansage.

## 7. Entscheidungen

**Technisch entschieden (in dieser Spezifikation):**
- Ein Halt bricht auch den laufenden Modellschritt ab (A-S4). Die doppelten
  Kosten sind bei der beobachteten Halt-Häufigkeit vernachlässigbar.
- Die Schlussrunde bekommt Hedging und eine Frist von 90 s, ohne Denkstufe oder
  Suchen zu kürzen (A-T2; Max' Vorgabe: schneller nur ohne Abstriche bei
  Denkzeit und Recherche, Hänger per Hedging abfangen).
- Das Gate hat eine Frist von 20 s. Danach entscheidet der Nutzer, nie ein
  stilles Go (A-T3).
- Eine unbeantwortete Domain-Karte ist ein „Nicht erlauben“ statt eines
  Stopps (A-R4).
- Die Marken erscheinen weiter erst, wenn alle Prüfer fertig sind. Der
  Hedge macht den langsamsten schneller, statt die Regel aufzuweichen.
- Befunde gehen weiterhin nicht an den Agenten (Max, 2026-10-25/28: Die
  Prüfer sind unabhängig und dienen der Sicherheit, nicht der Verbesserung).

**Offen für Max (strategisch):**
1. **Sollen Prüfer im Tageskontingent nach ihren Kosten statt nach ihren
   Tokens zählen?** Heute verbraucht ein Audit-Lauf fast das doppelte
   Kontingent, obwohl die Prüfer nur ein Fünftel der Kosten machen. Wer
   Sicherheit wählt, ist früher am Tageslimit. Empfehlung: ja, Prüfer-Tokens
   zählen zur Hälfte (`AUDIT_REVIEWER_QUOTA_WEIGHT = 0.5`). Damit liegt ihr
   Anteil am Kontingent etwa bei ihrem Anteil an den Kosten, und das Limit
   schützt weiter vor Ausreißern.

Erst nach A-M9 (mit einer Zahl): Bekommen OpenAI-Modelle im Agenten die
Suchmaschine `exa`, damit Prüfer und Agent die Treffer sehen?

## 8. Messmethode

Read-only gegen Prod-Firestore, wie in `scripts/cache_hit_rate.py`:
`users/{uid}/llm_calls` (`purpose == "agent"`, `created_at` im Zeitraum),
`users/{uid}/chats/{chat}/turns/{turn}` mit `agent_review.mode == "audit"`,
die Sitzungen unter `…/turns/{turn}/agents` (Prüfer: `kind == "audit"`) und das
Arbeitsprotokoll `…/turns/{turn}/work_log` (`answer_fixed`-, `checked`-,
`paused`- und `decision`-Einträge). Laufzeiten:
- **Gesamt:** Anlage bis `finished_at`.
- **Bis zur Antwort:** Anlage bis zum App-Eintrag der fixierten Antwort.
- **Marken nach dem letzten Wort:** fixierte Antwort bis Review fertig
  (letzter Schluss-Beleg + Speichern).
- **Schlussrunde:** Belege nach dem Fixieren.
- **Rückstand:** letzter gelesener Eintrag der Prüfer-Sitzung gegen den Stand
  beim Fixieren.

Render-Logs über `GET /v1/logs` (Dienst `srv-cva01khc1ekc738oe7e0`,
`type=app`, Textfilter). Max' Konten zählen hier mit, werden aber getrennt
ausgewiesen. Gelöschte Turns lassen sich nur über Belege schätzen (G1), bis
A-M1 läuft. Ab Paket 2 ersetzt `scripts/audit_report.py` diese Handarbeit.

## 9. Bewusst nicht im Umfang

- Rückkanal der Befunde an den Agenten (Max' Produktentscheidung).
- Wieder ein Gate je Browser-Klick ([agent-mode.md](agent-mode.md)
  „Vorab-Prüfung“: seit 2026-10-29 bewusst entfernt). Die Lücke
  „Klick überholt eine laufende Live-Runde“ wird über A-M3/A-M4 gemessen,
  bevor etwas nachgerüstet wird.
- Weniger Suchrunden oder niedrigere Denkstufen für Prüfer.
- Mehr-Instanz-Betrieb. Läufe bleiben prozesslokal
  ([codebase-map.md](codebase-map.md), „Agent-Turns laufen ohne Verbindung
  weiter“). A-R10 macht Deploys nur sichtbar.

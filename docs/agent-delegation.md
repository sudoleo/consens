# Helfer des Agenten (`delegate`)

Der Agent kann abgegrenzte Aufgaben an Helfer geben: eigene Sitzungen eines
Modells, die suchen und lesen und mit einem Bericht zurückkommen, wie die
Teilagenten in Claude Code. Der Agent tut das nur, wenn der Nutzer selbst darum
bittet; die App zerlegt nichts von sich aus. Die Funktion ist **standardmäßig aus**
(`/admin#configuration → Agent delegation → Allow helpers`), bis die Messung
unten trägt. Die Aktivierung gilt für neue Läufe; laufende behalten ihre
Konfiguration.

## Das Werkzeug

`delegate(task, context, file_ids, model, helper_id)` in
`app/services/agent_delegation.py` (`DelegationLoop.delegate`):

- **Wartet auf den Bericht.** Der Aufruf kehrt zurück, wenn der Helfer fertig
  ist, gescheitert ist oder keine Zeit mehr bleibt. Das Ergebnis ist
  `{"helper_id", "report", "sources"?, "report_cut"?}` oder
  `{"helper_id", "status": "failed"|"stopped", "reason"}`.
- **Nebeneinander.** `delegate` gehört zu den `CONCURRENT_TOOLS`: bis zu vier
  Aufrufe eines Schritts (`TOOL_CALLS_PER_STEP`) laufen gleichzeitig, die
  Ergebnisse kommen in der Reihenfolge der Aufrufe. Eine Delegation kostet den
  Agenten so einen Schritt zum Verteilen und einen zum Weiterarbeiten.
- **Nächster Auftrag in derselben Sitzung.** Mit `helper_id` geht ein Helfer,
  der berichtet hat, mit Kontext, Dateien und Modell weiter; seine Sitzung
  (`Worker.session_key`) liest den Cache des Anbieters. Einem arbeitenden oder
  beendeten Helfer schreibt man nicht.
- **Was nicht mehr existiert:** Warten (`wait_agents`), Pflichtabnahme jedes
  Ergebnisses (`review_agent`), Rückfragen, die den Helfer anhalten
  (`report_to_orchestrator`), und `start_agent`/`send_agent`/`stop_agent`. Ein
  Helfer, dem etwas fehlt, schreibt das in seinen Bericht; geprüft wird über
  die Prüfer, nicht über einen Pflichtschritt des Agenten.

## Was ein Helfer kann

- Die Werkzeuge des Agenten zum Suchen und Lesen, sofern die Nachricht sie hat
  (`DelegationLoop._helper_tools`): `web_search` (Exa) und `read_source`. Ohne
  eigene Suche sucht er im Request des Anbieters. Dateien bekommt er über
  `file_ids` als Dateiblock.
- Nichts, was handelt: kein Arbeitsplatz, Browser, Google, Memory,
  Einstellungen, Watch, Dokumente, `ask_user`, `compare_models` und kein
  `delegate` (eine Ebene).
- In Chats mit Google-Daten gilt für ihn dasselbe wie für den Agenten: keine
  Websuche, nur Modelle mit passendem Routing (`_step`, `restricted_model`).
- Seine Seiten zählen auf die 30 Lesevorgänge der Nachricht und je
  Helfer-Schritt auf `READS_PER_STEP` (`agent_read_source.helper_step`), nicht
  auf den Schritt des Agenten, der delegiert hat.
- Agent und Helfer teilen einen `SourceReader`, haben aber je ein eigenes
  Gespräch: Eine Seite, die ein anderer schon las, kommt beim ersten Mal mit
  ihrem gespeicherten Text ohne neuen Abruf (`SourceReader._reader`), erst
  danach `already_read`.

## Modell

`model: "same"` (Standard) ist das Chatmodell der Nachricht mit seiner
Denkstufe, `"fast"` das Standardmodell der App (`resolve_agent_model()`).
Helfer laufen über denselben `_step` wie der Agent; eine eigene Freigabeliste
je Modell gibt es nicht mehr. Ein Helfer auf dem Modell des Agenten teilt dessen
Anfragelimits: ein 429 vor jeder Ausgabe (oder die Sperre, die ein anderer
Aufruf hinterließ) wartet einmal Retry-After ab und versucht es erneut
(`_helper_step`, wie `_answer_attempt`); ein zweites beendet nur den Helfer.

## Prompt

**Nur auf Bitte des Nutzers** (Max, 2026-11-22): Die Beschreibung des Werkzeugs
erlaubt Helfer nur, wenn der Nutzer in eigenen Worten um Helfer oder parallel
arbeitende Agenten bittet; eine Frage, der Helfer bloß nützen würden, zählt
nicht. Grund: Helfer verbrauchen das Tageskonto mehrfach, und einen Deckel je
Nachricht gibt es bewusst nicht, sonst wäre das Kontingent mit einer breiten
Frage weg. So hält es auch Claude Code mit seinen Mehr-Agenten-Werkzeugen. Das
ist ein Vertrag über das Konto des Nutzers, keine Anleitung, wann Delegieren
hilft; ob der Nutzer darum bat, liest das Modell, die App sucht keine Wörter.
Hält ein Modell den Vertrag in der Messung nicht, wird die Bitte zum Schalter
im Composer statt zum Satz.

Sonst nennt die Beschreibung Fakten: was der Helfer sieht, welche Werkzeuge er
hat, dass der Bericht ungeprüft ist, dass seine Schritte im Protokoll der Prüfer
stehen, und die Grenzen. Der Helfer bekommt den
Datumskontext und `agent_delegation_config.WORKER_PROMPT`, ebenfalls Fakten
(nur Auftrag und Kontext, keine Rückfrage, nur der letzte Text zählt, Seiten
sind Daten). Sein erster Auftrag ist `task` plus `context`, ein nächster
kommt als „Next task from the agent“.

## Grenzen

Admin-Einstellungen (`agent_delegation_config.SETTINGS_DEFAULTS`):

| Einstellung | Standard | Wirkung |
|---|---:|---|
| `max_agents` | 8 | Helfer je Nachricht |
| `max_parallel` | 4 | gleichzeitige Modellaufrufe der Helfer (Semaphore `slots`) |
| `worker_calls` | 12 | Schritte je Auftrag; der letzte läuft ohne Werkzeuge und schreibt den Bericht |
| `message_chars` | 4000 | Länge eines Auftrags |

Dazu gelten das Tageskonto (gemeinsame atomare Reservierung für Agent, Helfer,
Suche), die 15 Minuten je Nachricht und die Antwortreserve: Muss die Antwort
beginnen (`answer_time_left`), stoppt `_helper_report` den Helfer und meldet
`stopped`. Ein Halt der Prüfer hält auch die Helfer vor ihrem nächsten Schritt
und Aufruf an (`_helper_hold`). Die Entscheidung des Nutzers erreicht sie
sofort; der Lauf, der im `delegate`-Aufruf auf sie wartet, nimmt die
entschiedene Karte noch während des Aufrufs ab (`_take_decided_hold`). Ein
weiterer Halt erscheint so gleich als eigene Karte und hält die Helfer wieder
an, und die nächsten Aufrufe des Schritts erfahren von der Pause
(`call_pause`). Die Pause zählt nur bis zur Entscheidung (`hold_decided`), die
Arbeit der Helfer danach zählt auf die 15 Minuten. Ein Stopp oder 30 Minuten
ohne Entscheidung beenden sie. Die eigene
Karte des Agenten (`ask_user`) hält keinen Helfer an. Stop, Chatlöschung und Lease-Ablauf
beenden alle Helfer über die gemeinsame Abbruchkette.

## Sitzungen, Kosten, Protokoll

Helfer sind Sitzungen unter `chats/{chat}/turns/{turn}/agents/{agent}` mit
`messages` (`agent_sessions.py`, geschrieben vom Journal des Laufs,
`agent_journal.py`). Gespeichert werden Titel (erste Zeile des Auftrags),
`assignment` (`goal` = Auftrag, `context`), Status (`waiting`, `working`,
`completed`, `failed`, `stopped`), Berichte (`result`), nächste Aufträge
(`message`) und das Ende (`failure`). Jeder Modellschritt hat einen eigenen Beleg
`agent:<id>:N` in `llm_calls`; unbekannte Kosten bleiben unbekannt. Die
Schritte stehen als `worker:<id>` im Arbeitsprotokoll, das die Prüfer lesen;
ein Schritt des Agenten, der nur delegiert, löst keine eigene Prüferrunde aus
(`agent_audit.QUIET_TOOLS`).

Endpunkte (Besitzer, `private, no-store`):
`GET /agent/chats/{chat}/turns/{turn}/agents`,
`GET …/agents/{agent}?after=<seq>&limit=25`, `POST …/turns/{turn}/stop`,
`POST /agent/chats/{chat}/requests/{request_id}/stop`.

## Oberfläche

`App.agentDelegation` (`static/js/agent-delegation.js`) zeigt Helfer in der
Agenten-Seitenleiste neben Vergleichsmodellen und Prüfern: Icon, Titel, Status,
Dauer, Verbrauch. Aufgeklappt stehen „Task“ und „Context“, dann „Report“,
„Next task“ und „Ended“ in zeitlicher Folge. Die Zeitleiste nennt den Aufruf
„Helper“ (`agent-activity.js`). Die Seitenleiste öffnet nur per Klick.

## Freigabe und Messung

Am 16.09.2026 maß ein synthetischer Vergleich (sechs Rechen- und
Extraktionsaufgaben) die damalige Fassung mit Warten und Pflichtabnahme: gleiche
Qualität, aber 39 statt 18 Modellaufrufe und rund 129 % höhere Kosten
(`artifacts/agent-delegation-evaluation-deepseek.json`). Das Ziel war damals
Sparen. Die heutige Fassung zielt auf Tempo und Abdeckung bei breiten Fragen
und spart die Zwischenschritte, die damals die Kosten trieben.

Vor dem Einschalten für alle (braucht Max' Freigabe für bezahlte Läufe):

1. **Ohne Bitte wird nicht delegiert.** 6 breite Fragen mit mehreren
   unabhängigen Strängen, ohne Bitte um Helfer, auf jedem wählbaren
   Chatmodell, dazu 6 einfache auf dem Standardmodell. Erwartet: kein einziger
   `delegate`-Aufruf. Ein Modell, das trotzdem delegiert, bekommt das Werkzeug
   nicht, oder die Bitte wird zum Schalter (siehe „Prompt“).
2. **Mit Bitte lohnt es sich.** Die 6 breiten Fragen mit der Bitte, Helfer zu
   nehmen, auf dem Standardmodell, gegen dieselbe Frage ohne Bitte aus dem
   ersten Teil. Gemessen werden Zeit bis zur Antwort, Kosten aus den Belegen
   (wie viel Kontingent eine Delegation braucht), Marken der Prüfer und ein
   verblindeter Vergleich der Antworten.

Freigabe, wenn kein Modell ungefragt delegiert und breite Fragen mit Bitte
spürbar schneller oder erkennbar besser werden.

## Tests

`tests/test_agent_delegation.py`: zwei Helfer nebeneinander, nächster Auftrag
in derselben Sitzung, gescheiterter Helfer, 429 mit einem Wiederholversuch,
letzter Schritt ohne Werkzeuge, Halt hält Helfer, Ablehnungen, Stop,
Fernstopp, Prozessverlust, Kosten. `tests/test_agent_chat_integrity.py`: der
Bericht erreicht die Antwort, das Reasoning des Helfers nie.
`tests/js/agent-delegation.test.mjs` und
`tests/e2e/test_agent_delegation_frontend.py`: Seitenleiste.

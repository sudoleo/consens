# Tempo-Plan Agent (2026-11-05)

Anlass: Ein Lauf mit GPT-6.1 Terra (Recherche, dann ein Diagramm im
Arbeitsplatz) brauchte bei uns 136 s. Copilot war mit GPT-5.6 Sol, also einem
langsameren Modell, bei derselben Aufgabe nach weniger als der Hälfte der Zeit
fertig. Dieser Plan legt jede Sekunde des Laufs auf eine Ursache im Code und
ordnet die Hebel nach Wirkung.

Datengrundlage: Prod-Belege (`llm_calls`, Zeitstempel je Schritt), die
Aktivität des Turns und OpenRouter `/api/v1/generation` sowie
`/api/v1/models/{id}/endpoints`. Alles wurde nur gelesen, es gab keine
Modellaufrufe. Dazu kommen die eigenen Läufe der letzten 7 Tage (75 Turns mit
Chat-Schritten). Die Messskripte liegen noch nicht im Repo (siehe P0).

## 1. Wohin die 136 s gingen

Lauf vom 2026-11-05 12:40 UTC: 12 Schritte des Chatmodells, 15 Websuchen, 1×
`read_source`, 1× `open_workspace`, 7× `vm_exec`, 1× `vm_share_file`, Prüfer
aus.

| Block | Zeit | Anteil | Ursache |
|---|---:|---:|---|
| Schritte 0–4 mit Websuche | 85,0 s | 62 % | 15 Suchen laufen nacheinander im Modell-Request (OpenAI-eigene Suche, `engine: auto`), je Suche ~5 s |
| Schritte 5–10, Arbeitsplatz ohne Suche | 26,7 s | 20 % | 6 Modell-Rundgänge, TTFT 1,6–4,4 s auf einem langsamen Endpunkt |
| Werkzeuge (`vm_exec`, Download, Teilen) | 8,9 s | 7 % | echte Arbeit; 0,1–2,9 s je Aufruf |
| Eigener Overhead zwischen den Schritten | 7,9 s | 6 % | 0,6–0,85 s je Lücke: Firestore-Transaktionen und Lesezugriffe |
| Antwortschritt 11 | 5,5 s | 4 % | TTFT 4,0 s |
| Vorlauf und Abschluss | 2,2 s | 2 % | 0,17 s bis zum ersten Request, 2,0 s vom letzten Token bis `completed_at` |

Die Modelle selbst sind nicht der Engpass. OpenRouter meldet für jeden Schritt
eine `generation_time`, die bis auf 0,02–0,65 s unserer Messung entspricht.
Unser Code bremst also nicht innerhalb eines Requests. Zeit kosten die
Reihenfolge der Arbeit, die Wahl des Endpunkts und die Buchhaltung zwischen
den Requests.

### Endpunkte für GPT-6.1 Terra (OpenRouter, letzte 30 min, 2026-11-05)

| Endpunkt | TTFT p50 | TTFT p90 | Durchsatz p50 |
|---|---:|---:|---:|
| **Azure (gewählt, `sort: throughput`)** | **3,48 s** | **8,70 s** | 63 tok/s |
| Azure EU | 1,40 s | 2,61 s | 29 tok/s |
| Azure US | 1,28 s | 2,23 s | 42 tok/s |
| Amazon Bedrock us-east-1 | 1,29 s | 4,25 s | 76 tok/s |
| OpenAI fast | 1,77 s | 3,87 s | 57 tok/s |

Ein Agent-Schritt schreibt im Median rund 200 Tokens (meist ein Tool-Call).
Dafür zählt die TTFT, nicht der Durchsatz. Die Sortierung nach Durchsatz hat
für alle 12 Schritte den Endpunkt mit der höchsten TTFT gewählt.
`DEFAULT_PROVIDER_ROUTING = {"sort": "throughput", …}` steht in
`app/core/openrouter_contract.py:21`. Die Sticky-Session (`x-session-id`)
hält danach den ganzen Chat auf diesem Endpunkt.

### Breiter Blick: eigene Läufe der letzten 7 Tage (75 Turns)

- Gesamtzeit p50 21 s, p90 156 s; Schritte p50 3, p90 14.
- Websuche: **p50 5,1 s, p90 11,2 s je Suche**, nacheinander.
- Overhead je Lücke zwischen zwei Schritten, ohne die gemessene Werkzeugzeit:
  **p50 0,81 s, p90 3,0 s**. Das deckt sich mit dem Audit vom 2026-10-30.
- TTFT unserer Schritte: Terra p50 2,2 s / p90 4,5 s, DeepSeek V4.1 Flash
  p50 3,3 s / **p90 12,0 s**, V4.1 Flash 1017 p50 1,2 s / p90 3,7 s.
- Lücken nach Werkzeug, Median: `browser` 2,7 s, `vm_exec` 1,3 s (p90 13,8 s),
  2× `read_source` 6,3 s, `compare_models` 44 s.

### Warum Copilot schneller ist (Einordnung, nicht überprüfbar)

Copilots Innenleben kennen wir nicht. Unsere Zahlen erklären den Abstand aber
auch ohne ein schnelleres Modell. Copilot sucht mit Bing-Abfragen, die
parallel laufen, statt in einer Kette von Suchrunden im Modell. Es spricht
seinen Azure-Endpunkt direkt an. Und es führt zwischen den Schritten keine
Kontingent-Buchhaltung in einer Datenbank. Rechnet man die Hebel P1–P3 unten
auf den Beispiellauf, kommt man auf ~60 s. Das ist das Niveau, das Max bei
Copilot gesehen hat.

## 2. Maßnahmen, nach Wirkung geordnet

Die Schätzungen beziehen sich auf den Beispiellauf (136 s). Max' Grundsatz
„Tempo ohne Abstriche“ gilt für alle Maßnahmen: keine Recherche, keine
Denkzeit und keine Prüfung streichen. Schneller werden wir, indem wir
dieselbe Arbeit parallel und auf schnelleren Wegen erledigen.

### P0 – Messung ins Repo (Voraussetzung)

- `scripts/agent_speed.py` (nur lesend) entsteht aus den Scratchpad-Skripten.
  Es liefert je Turn die Zeitleiste Schritt für Schritt (`request_started_at`,
  `first_token_at`, `stream_ended_at`), die Lücken minus Werkzeugzeit, Suchen
  je Schritt, Endpunkt und TTFT laut OpenRouter (`/generation`) sowie
  Aggregate (p50/p90).
- Jede der folgenden Maßnahmen wird nach dem Deploy damit nachgemessen.
- Ein Wächtertest misst die Rundgänge zwischen zwei Schritten (Muster:
  `tests/test_agent_tempo.py`, `tests/test_agent_first_request.py`).

### P1 – Suche parallel statt nacheinander (geschätzt −40 bis −55 s)

Befund:
- `openrouter:web_search` läuft als Server-Tool im Modell-Request
  (`app/services/agent_tools.py:43`, `app/services/llm/engines.py:59`).
- Jede Suchrunde ist ein voller Modelldurchlauf: suchen, Ergebnis lesen, die
  nächste Suche formulieren. Im Beispiel waren das 15 Runden à ~5 s.
- Angeboten wird sie in **jedem** Schritt mit bis zu 5 Runden
  (`AGENT_SEARCH_ROUNDS = 5`, `app/services/agent_audit.py:71`). Deshalb
  suchte Terra auch noch in den Arbeitsplatz-Schritten 3 und 4.
- Die OpenAI-eigene Suche bindet die Anfrage zudem an Endpunkte von OpenAI und
  Azure. Das engt P2 ein.

Umbau:
1. Ein eigenes Funktionswerkzeug `web_search(queries: [1–5])`. Alle Abfragen
   eines Aufrufs laufen gleichzeitig. Das Ergebnis behält das heutige Format
   (5 Treffer × 2.000 Zeichen je Abfrage, Quellen wie heute in `sources`).
   Das Modell bündelt seine Fragen in einem Aufruf, statt sie über fünf
   Runden zu verteilen. Die Seiten selbst liest weiter `read_source`.
2. Als Suchdienst bietet sich Brave an, das für `search_pictures` schon
   angebunden ist (`app/services/picture_search.py`). Alternative ist Exa über
   OpenRouter. Vorher klären: Erlaubt Braves Tarif die Nutzung durch KI, und
   wie fällt die Qualität im Vergleich zur OpenAI-eigenen Suche aus?
   Letzteres auf dem Prüfstand testen, nicht an Einzelläufen.
3. Übergang ohne neues Werkzeug: `engine: "exa"` für alle Familien. Bei Grok
   brachte das 4 s statt 20 s TTFT (`engines.py:45-56`). Das ist nur ein
   Zwischenschritt, denn auch Exa-Runden laufen innerhalb eines Requests
   nacheinander.

Risiko: Die Qualität der Recherche. Deshalb liegt die Entscheidung über den
Suchdienst bei Max, nach einem A/B-Test auf dem Prüfstand. Der Test braucht
bezahlte Modellaufrufe und damit Max' OK.

### P2 – Endpunkt nach TTFT statt nach Durchsatz (geschätzt −15 bis −25 s)

- Für die Schritte des Chatmodells nach Latenz sortieren (`sort: "latency"`)
  oder `preferred_max_latency` setzen, mit Durchsatz als zweitem Kriterium.
  Im Beispiel würde die TTFT von p50 3,5 s auf ~1,3–1,4 s fallen. Bei 12
  Schritten spart das ~2 s je Schritt.
- Vergleichsmodelle, Prüfer und lange Einzelantworten können beim Durchsatz
  bleiben. Getrennt wird über den Aufrufer (`AgentCompletion.stream`,
  `app/services/llm/agent_client.py:1111`).
- Zu prüfen:
  - Halten die schnelleren Endpunkte `data_collection: deny` ein?
  - Liegt der Prompt-Cache auf dem gewählten Endpunkt? Ja: Die
    Sticky-Session gilt ab dem ersten Request.
  - Bleibt die OpenAI-eigene Suche verfügbar, solange P1 nicht steht? Sie
    läuft nur auf OpenAI und Azure. Daher ist `azure/eu` bzw. `azure/us`
    wahrscheinlich die Wahl statt Bedrock.
- Das ist eine reine Konfiguration ohne Folgen für die Qualität. Deshalb zuerst
  bauen.

### P3 – Overhead je Schritt von 0,8 s auf ≤ 0,2 s (geschätzt −6 bis −8 s, p90 deutlich mehr)

Zwischen zwei Schritten laufen heute nacheinander auf dem Run-Thread:
- `settle` als Transaktion unter dem Konto-Lock (`app/services/agent_runs.py:455`)
- der Chat-Read nur für `google_data` (`app/services/agent_delegation.py:1710`)
- in Arbeitsplatz-Läufen ein `remaining_allowance`-Read je Schritt
  (`agent_delegation.py:961`)
- `claim` als Transaktion mit 7 und mehr Reads unter dem Konto-Lock
- ein neuer HTTP-Client samt neuer Event-Loop und neuem TLS-Handshake zu
  OpenRouter (`app/services/llm/provider_runtime.py:448-449`; im Beispiel
  50–560 ms je Request, zusammen 1,5 s)

Umbau:
1. Das Settlement von Schritt N und der Claim von Schritt N+1 laufen in einer
   Transaktion. Alternativ wird der nächste Claim vorab reserviert, während
   das Werkzeug läuft.
2. `google_data` einmal je Turn lesen und nur bei einer Änderung im eigenen
   Prozess neu holen.
3. Die verbleibende Allowance aus dem Ergebnis des Claims übernehmen statt
   eines eigenen Reads.
4. Ein dauerhafter `httpx.AsyncClient` mit Keep-Alive auf einer eigenen
   Event-Loop (ein Thread je Prozess), auf den alle Modellaufrufe zugreifen.
   Er spart DNS, TCP und TLS je Request, ebenso das Laden des CA-Bundles bei
   0,5 CPU. Abbrechen und Zeitlimits (`_guard_provider_io`) bleiben wie heute.
5. `tail_sse` pollt den Puffer alle 100 ms (`app/services/agent_live.py:53`).
   Ein Event zum Aufwecken ersetzt das Polling.

### P4 – Weniger und parallele Werkzeug-Rundgänge (geschätzt −3 bis −10 s, je nach Lauf)

- `parallel_tool_calls` ist nur bei offenem Arbeitsplatz an
  (`agent_delegation.py:882`). Im Chat kostet jeder weitere Aufruf einen vollen
  Modell-Rundgang. Künftig ab Schritt 0 für alle einschalten. Weil es ab
  Schritt 0 gilt, wechselt `tool_choice` nie mitten im Lauf, und der Cache
  bleibt.
- Unabhängige Aufrufe eines Schritts laufen heute nacheinander
  (`agent_delegation.py:3439`). Lesende Werkzeuge sollen gleichzeitig laufen
  (`read_source`, `find_pictures`, `search_chats`, `read_file`, Lesen im
  Arbeitsplatz). Schreibende Werkzeuge, der Browser und `ask_user` bleiben in
  ihrer Reihenfolge.
- `read_source` ist ein ganzer Hilfs-Modellschritt mit zwei synchronen
  `save_review`-Writes (`app/services/agent_read_source.py`). Zwei Lesungen
  dauerten im Median 6,3 s.
- Ehrliche Einordnung: Im Beispiellauf hat Terra seine Shell-Befehle schon
  selbst verkettet. Die Schritte 5–10 hängen jeweils vom Ergebnis des
  vorigen ab. P4 wirkt dort wenig, bei Recherche-Läufen mit mehreren Lesungen
  deutlich.

### P5 – Erster Aufruf im Arbeitsplatz (geschätzt −2 bis −9 s in Arbeitsplatz-Läufen)

- Die Werkbank vorwärmen, sobald eine Nachricht mit offenem Arbeitsplatz
  beginnt (Chat-Feld `agent_workspace_used`), nicht erst nach
  `open_workspace`.
- Der erste ändernde Aufruf soll nicht auf den Checkpoint warten
  (`app/services/agent_vm_tools.py:1321`). Gemessener Vorlauf des ersten
  Aufrufs: Median 2,5 s, p90 9,5 s (Audit 2026-10-30).

### P6 – Antwort sichtbar früher (−1 bis −2 s gefühlt je Antwort)

- Server: Antworttext erscheint erst ab 300 Zeichen (`ANSWER_HOLD_CHARS`,
  `app/services/agent_answer_mode.py:20`). Kürzere Antworten kommen erst am
  Ende des Schritts. Künftig ab dem ersten Token streamen. Folgt doch ein
  Tool-Call, wandert der Text wie heute in die Zeitleiste (`_move_preamble`).
- Browser:
  - Das erste Wort wartet auf den 100-ms-Flush, weil `paint()` nur in eine
    Antwort malt, die schon streamt (`static/js/agent-chat.js:2529`).
  - Danach blendet die Live-Zeile 160 ms aus.
  - Dann läuft der getaktete Rückstand von 0,15–0,8 s
    (`static/js/stream-reveal.js:29-30`).
  - Das erste Wort soll sofort erscheinen, die Taktung erst danach greifen.
- Der Stille-Timer des Polling-Fallbacks startet vor dem POST
  (`static/js/agent-live.js:284`). Bei langsamem Vorlauf pollt er grundlos
  und meldet `app_stream_buffered` fälschlich. Er soll erst mit den Headern
  der Antwort starten.
- Ohne Prüfer wird der Composer erst mit `final` frei, also nach Bookmark,
  Journal und Snapshot (im Beispiel 2,0 s). Die Übergabe (`handover`) soll
  auch ohne Prüfer laufen.

### P7 – Messen statt ändern: Reasoning-Zusammenfassung

- Terra-Schritte mit 24–43 Reasoning-Tokens hatten eine TTFT von 3,6–3,7 s,
  ein Schritt ohne Reasoning eine von 1,5 s (alle auf demselben Endpunkt).
  `summary: "auto"` wird für OpenAI immer gesetzt
  (`app/services/llm/agent_client.py:473`).
- Ob die Zusammenfassung selbst TTFT kostet, klärt ein kleiner A/B-Test
  (wenige Aufrufe, nur mit Max' OK). Denkstufen bleiben unangetastet.

## 3. Reihenfolge und Erwartung

| Schritt | Hebel | Art | Erwartung im Beispiel |
|---|---|---|---|
| 1 | P0 Messskript + Wächter | Technik | – |
| 2 | P2 Routing nach TTFT | Technik, Konfiguration | 136 → ~115 s |
| 3 | P3 Overhead je Schritt | Technik | → ~108 s |
| 4 | P6 Antwort früher sichtbar | Technik, Frontend | gefühlt −1 bis −2 s |
| 5 | P1 parallele Suche | **Produktentscheidung** nach A/B | → ~60 s |
| 6 | P4, P5 | Technik | je nach Lauf |

- P2, P3 und P6 ändern nichts an Antworten, Recherche oder Prüfung. Sie können
  sofort gebaut werden.
- P1 bringt am meisten, berührt aber die Qualität der Recherche. Deshalb
  kommt erst der Prüfstand, dann entscheidet Max.
- Deploys nur auf Max' Ansage. Nach jedem Deploy mit P0 nachmessen.

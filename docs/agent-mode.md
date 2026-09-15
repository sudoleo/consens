# Agent · Beta

Ein Textmodell im normalen Chat, verfügbar für Pro-Nutzer und Admins. Der
Modus ist pro Unterhaltung festgelegt. Neue Chats starten über den vorhandenen
Sidebar-Knopf; die Consensus-Ausführung bleibt separat auswählbar.

## Modellwahl und Aktivität (2026-09-15)

Der Composer verwendet denselben Custom-Modell-Picker wie Consensus, mit einer
eigenen Auswahl für genau ein Agent-Modell. Modell und Reasoning-Einstellung
können zwischen Nachrichten wechseln; während einer Antwort sind sie gesperrt.
Die letzte Wahl wird kontogebunden gespeichert, die Wahl eines geöffneten Chats
stammt aus dessen letztem Turn. Consensus-Presets werden dadurch nicht geändert.

`GET /agent/models` liefert nach derselben Admin-/Pro-Prüfung den konfigurierten
Standard plus die Schnittmenge aus `cfg.MODEL_CONFIGS` und dem überprüften
`app/services/llm/agent_model_catalog.json`. Labels, interne IDs, API-Aliasse und
Provider-Routing kommen aus der vorhandenen Registry. Der öffentliche
[OpenRouter-Katalog](https://openrouter.ai/api/v1/models) wurde am 15.09.2026
abgerufen; es gibt keinen Live-Abruf beim Öffnen des Pickers. Bei neuen Modellen
oder Preis-/Fähigkeitsänderungen den Snapshot nach Prüfung aktualisieren.
Unbekannte Registry-Modelle werden bis dahin nicht angeboten.

Der Picker bietet nur die im Katalog bestätigten Reasoning-Stufen an. „Default“
behält die Modellkonfiguration bzw. den Provider-Standard; benannte
No-Reasoning-Varianten bleiben fest. Die Agent-Wahl ist unabhängig von der
Consensus-Economy-Policy. `POST /agent` akzeptiert `model_id` und
`reasoning_effort`; Labels, Preise, Routing und Usage kommen ausschließlich vom
Server. Geänderte Einstellungen unter derselben Request-ID liefern 409,
ungültige Auswahlwerte vor dem Modellaufruf 422. Recovery nutzt den gespeicherten
Snapshot auch nach einer Konfigurationsänderung.

Modus, Modell und Denkstufe verwenden denselben Custom-Picker mit eigenem
Agent-Zustand. Menübreiten passen sich dem sichtbaren Viewport an; Tastaturwahl,
Escape und Fokusrückgabe funktionieren für alle drei Controls. Nicht mehr
verfügbare gespeicherte Modelle werden mit Hinweis auf den angebotenen Standard
abgeglichen; derselbe Wert wird angezeigt und gesendet.

Die aufklappbare Aktivitätsanzeige öffnet sich beim ersten sichtbaren Reasoning
und klappt nach Abschluss automatisch zu. Eine manuelle Auf-/Zu-Auswahl bleibt
bestehen. Ein gemeinsamer Scrollbereich folgt neuen Textblöcken, solange der
Nutzer nicht zurückscrollt. Die Statuszeile verwendet den Strich-/Lichtlauf des
Quellenchecks; bei Reduced Motion/Forced Colors und nach Stop/Fehler/Abschluss
bleibt sie statisch. Gestoppte Turns werden auch im gespeicherten Zustand als
gestoppt beschriftet, ein Output-Limit ist bereits eingeklappt erkennbar.
Die Anzeige bleibt im Verlauf verfügbar. Sie zeigt ausschließlich vom Provider
gelieferte Reasoning-Texte/Zusammenfassungen, Arbeitsstatus und gemeldeten
Verbrauch mit simulierten Kosten. OpenAI-Summaries werden angefordert.
Verschlüsselte Reasoning-Blöcke werden weder angezeigt noch gespeichert.
Fehlendes sichtbares Reasoning und fehlende Usage sind ausdrücklich erkennbar;
es werden keine Denktexte erfunden. Die Stopptaste nutzt weiterhin den gemeinsamen
Abbruchmechanismus. Begrenzung: 32.000 Zeichen sichtbares Reasoning, höchstens
32 Reasoning-/Status-Einträge vor den abschließenden Status-/Usage-Ereignissen;
eine gekürzte Darstellung wird gekennzeichnet. Das Antwortlimit bleibt separat.

`activity`-SSE-Ereignisse haben `version: 1`, `step_id: completion:0`, eine `id`
und `kind: status | reasoning | usage`. Reasoning-Deltas tragen `append: true`
und `format: text | summary`; gespeicherte Ereignisse enthalten den zusammen-
gefügten Text. `agent-activity.js` verarbeitet und rendert diese Ereignisse für
laufende Antworten und gespeicherte Turns. Neue Tool-Schritte können später
denselben Vertrag um eigene Schritt-IDs und Ereignistypen erweitern.

## Konfiguration

Der Server verwendet den bestehenden OpenRouter-Betreiberschlüssel. Die
Modell-/Tarifkonfiguration liegt zentral in `app/services/llm/agent_client.py`.
Optionale Umgebungsvariablen werden vor einem neuen Aufruf validiert:

| Variable | Standard |
|---|---|
| `AGENT_MODEL` | `deepseek/deepseek-v4.1-flash` |
| `AGENT_LABEL` | `DeepSeek V4.1 Flash` |
| `AGENT_MAX_OUTPUT_TOKENS` | `4096` (erlaubt: 256–16384) |
| `AGENT_INPUT_USD_PER_MILLION` | `0.15` |
| `AGENT_OUTPUT_USD_PER_MILLION` | `0.60` |
| `AGENT_CACHE_READ_USD_PER_MILLION` | `0.003` |
| `AGENT_PRICING_VERSION` | `openrouter-2026-09-14` |
| `AGENT_MAX_CONCURRENT_RUNS` | `16` pro Prozess (erlaubt: 1–64) |

Die initialen Simulationstarife entsprechen dem am 14.09.2026 gelesenen
[OpenRouter-Modellangebot](https://openrouter.ai/deepseek/deepseek-v4.1-flash).
Provider können unterschiedliche Tarife haben. Das sind feste simulierte
Kosten, keine Abbildung einer OpenRouter-Rechnung. Ein anderes `AGENT_MODEL`
benötigt einen Katalogeintrag: Kontext-/Outputgrenzen, Registry-Routing und
ohne expliziten Override auch Label, Tarife und Preisversion stammen dann von
diesem Modell. Bereits beanspruchte Aufrufe
behalten ihren Snapshot; abgeschlossene Requests bleiben trotz Konfigurations-
oder Schlüsselwechsel ohne neuen Modellaufruf wiederherstellbar.

Weitere Picker-Modelle nutzen feste Basistarife aus dem Katalogsnapshot,
einschließlich Cache-Read-Tarif (sonst normaler Input-Tarif). Zeitabhängige
Angebote, Schwellenpreise, Cache-Write- und Web-Tool-Zuschläge werden in dieser
Simulation nicht nachgebildet. Der bestehende `AGENT_*`-Tarif für das
Standardmodell bleibt separat konfigurierbar; diese Werte sind weiterhin keine
Provider-Rechnung.

## Verbrauch

`users/{uid}.agent_usage` enthält die kumulierten Input-/Output-Tokens und
`estimated_cost_nano_usd` (geteilt durch 1.000.000.000 ergibt USD).
Cache-Hits werden zum Cache-Tarif berechnet. Reasoning-Tokens sind eine
Teilmenge der Output-Tokens und werden nicht nochmals addiert. Die Admin-
Kontoansicht zeigt die Summe, die Tokenmengen und unvollständige Messungen.

`measured_calls`, `unmetered_calls` und `unsettled_calls` unterscheiden
gemessene, ohne Provider-Usage beendete und noch offene Aufrufe. Ein Abbruch
vor der letzten Usage-Nachricht kann reale, hier **unbekannte** Kosten
verursachen. Der Beleg zeigt das ausdrücklich; es werden keine fiktiven
Tokenzahlen ergänzt. Ein Prozessabsturz hinterlässt einen offenen Beleg,
den ein Retry nicht erneut ausführen darf. Kosten werden derzeit weder vom
Guthaben noch vom Consensus-Tageskontingent abgezogen.

## Grenzen und Erweiterung

Ein Textmodell, Streaming, persistenter Verlauf. Kein Fan-out, Judge,
Webzugriff, eigenes API-Key-Routing oder weiterer LLM-Aufruf für Memory.
Dateien und `stream: false` werden abgewiesen. Das Providerbudget beträgt 180 Sekunden;
ein Kontext über 120.000 Zeichen erfordert einen neuen Chat.
Für kleinere Modellfenster wird zusätzlich vor dem bezahlten Aufruf ein
konservatives UTF-8-Bytebudget inklusive Output-Reserve geprüft. Das ist keine
exakte Tokenzählung und noch keine Kontextkomprimierung. Sichtbares Reasoning
wird im Verlauf gespeichert, aber nicht in spätere Modellprompts übernommen.

### Parallelität und Abbruch

Pro Prozess laufen höchstens 16 Agent-Produzenten; die konfigurierbare Grenze
weist Überlast vor Turn-Anlage mit 503 und `Retry-After: 5` ab. Pro Nutzer
erlaubt eine Firestore-Transaktion maximal zwei aktive Agent-Läufe auch über
mehrere Instanzen. Die Reservierung unter `chat_state/agent_runs` entsteht
atomar mit dem Beleg und wird beim Settlement entfernt. Nach Prozessabsturz
läuft sie nach fünf Minuten aus; offene Belege bleiben sichtbar und werden
nicht erneut ausgeführt. Replays fertiger Antworten brauchen keinen freien Slot.

Der Claim entsteht erst beim Start des Stream-Produzenten. Disconnect vor
der ersten Iteration gibt den unbezahlten Turn und den Prozess-Slot frei.
Der gemeinsame SSE-Puffer ist auf 64 Ereignisse begrenzt; 30 Sekunden ohne
freien Pufferplatz brechen den Produzenten ab. Datenbank-RPCs liegen außerhalb
des Providerbudgets. Lang laufende Hintergrundaufgaben benötigen später eine
dauerhafte Job-Ausführung mit Checkpoints; diese Version führt begrenzte
Chat-Antworten innerhalb eines HTTP-Requests aus.

Ein späterer Agent-Loop kann weitere explizite Schritte mit eigenen
`llm_calls`-Belegen anfügen. Transport, Turn-Persistenz und Abrechnung sind
getrennt. Die Consensus-Pipeline ist noch kein Tool und wird nicht implizit
gestartet. Beim Einbau von Tools müssen Berechtigungen, Schrittbudgets und
Tool-Ergebnisse zusätzlich modelliert werden.

## Prüfungen

`tests/test_agent_runs.py` prüft Zugriff, einzelne Requests, echte Usage-
Chunks, Idempotenz, Transaktionen, Verlauf und Löschrennen.
`tests/test_agent_capacity.py` und `tests/test_stream_backpressure.py` prüfen
konkurrierende Zulassung, Lease-Ablauf, Disconnect vor Streamstart und langsame
Clients. `tests/e2e/test_agent_transactions.py` prüft die Konkurrenz zusätzlich
mit echten Firestore-Transaktionen im isolierten lokalen Emulator.
`tests/js/agent-chat.test.mjs` prüft Dispatch, Fortsetzung, Berechtigungen und
Auth-Wechsel. `tests/e2e/test_agent_chat_frontend.py` prüft die gebaute App,
echten Bookmark-Restore und Desktop-/Mobile-Layout mit gemockten APIs,
dem writerfreien Phase-4-Testserver und ohne bezahlte Modellaufrufe.

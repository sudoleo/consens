# Agent · Beta

Ein Textmodell im normalen Chat, verfügbar für Pro-Nutzer und Admins. Der
Modus ist pro Unterhaltung festgelegt. Neue Chats starten über den vorhandenen
Sidebar-Knopf; die Consensus-Ausführung bleibt separat auswählbar.

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

Die initialen Simulationstarife entsprechen dem am 14.09.2026 gelesenen
[OpenRouter-Modellangebot](https://openrouter.ai/deepseek/deepseek-v4.1-flash).
Provider können unterschiedliche Tarife haben. Das sind feste simulierte
Kosten, keine Abbildung einer OpenRouter-Rechnung. Bei einem Modellwechsel
auch Tarife und Preisversion aktualisieren. Bereits beanspruchte Aufrufe
behalten ihren Snapshot; abgeschlossene Requests bleiben trotz Konfigurations-
oder Schlüsselwechsel ohne neuen Modellaufruf wiederherstellbar.

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
Dateien werden abgewiesen. Das Gesamtbudget beträgt 180 Sekunden;
ein Kontext über 120.000 Zeichen erfordert einen neuen Chat.

Ein späterer Agent-Loop kann weitere explizite Schritte mit eigenen
`llm_calls`-Belegen anfügen. Transport, Turn-Persistenz und Abrechnung sind
getrennt. Die Consensus-Pipeline ist noch kein Tool und wird nicht implizit
gestartet. Beim Einbau von Tools müssen Berechtigungen, Schrittbudgets und
Tool-Ergebnisse zusätzlich modelliert werden.

## Prüfungen

`tests/test_agent_runs.py` prüft Zugriff, einzelne Requests, echte Usage-
Chunks, Idempotenz, Transaktionen, Verlauf und Löschrennen.
`tests/js/agent-chat.test.mjs` prüft Dispatch, Fortsetzung, Berechtigungen und
Auth-Wechsel. `tests/e2e/test_agent_chat_frontend.py` prüft die gebaute App,
echten Bookmark-Restore und Desktop-/Mobile-Layout mit gemockten APIs,
dem writerfreien Phase-4-Testserver und ohne bezahlte Modellaufrufe.

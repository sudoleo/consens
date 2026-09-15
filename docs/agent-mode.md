# Agent · Beta

Ein begrenzter Modell-/Tool-Lauf im normalen Chat, verfügbar für Pro-Nutzer und Admins. Der
Modus ist pro Unterhaltung festgelegt. Neue Chats starten über den vorhandenen
Sidebar-Knopf; die Consensus-Ausführung bleibt separat auswählbar.

## Modellwahl und Aktivität (2026-09-15)

Der Composer verwendet denselben Custom-Modell-Picker wie Consensus, mit einer
eigenen Auswahl für genau ein Agent-Modell. Modell und Reasoning-Einstellung
können zwischen Nachrichten wechseln; während einer Antwort sind sie gesperrt.
Die letzte Wahl wird kontogebunden gespeichert, die Wahl eines geöffneten Chats
stammt aus dessen letztem Turn. Consensus-Presets werden dadurch nicht geändert.

`GET /agent/models` liefert nach derselben Admin-/Pro-Prüfung den konfigurierten
Standard plus die Daily-Antwortmodelle aus `cfg.CONSENSUS_PRESET_MODELS["fast"]`,
soweit sie in `cfg.MODEL_CONFIGS` und dem überprüften
`app/services/llm/agent_model_catalog.json` enthalten sind. Labels, interne IDs, API-Aliasse und
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
verfügbare gespeicherte Modelle werden auf den angebotenen Standard abgeglichen;
die korrigierte nächste Auswahl wird in Session und LocalStorage gespeichert.
Ein kurzes Popup erklärt die Änderung einmal. Historische Modelleinstellungen
bleiben erhalten. Im Composer stehen keine dauerhaften Hinweise neben den Pickern.
Änderungen werden bereits beim `input`-Ereignis in der Capture-Phase gespeichert,
bevor nachfolgende UI-Projektionen alte Werte zurücksetzen können. Ein neu
angelegter Lauf ohne Chat-ID hat einen eigenen Auswahl-Schlüssel; laufende
Antworten zeigen ihre eingefrorenen Einstellungen statt einer früheren Draft-Wahl.
Die Frage verwendet wie Consensus den rechtsbündigen Flex-Container und eine
an den Inhalt angepasste Nachrichtenblase.

Die aufklappbare Aktivitätsanzeige öffnet sich beim ersten sichtbaren Reasoning
und klappt nach Abschluss automatisch zu. Eine manuelle Auf-/Zu-Auswahl bleibt
bestehen. Ein gemeinsamer Scrollbereich folgt neuen Textblöcken, solange der
Nutzer nicht zurückscrollt. Die Statuszeile verwendet den Lichtlauf des
Quellenchecks; bei Reduced Motion/Forced Colors und nach Stop/Fehler/Abschluss
bleibt sie statisch. Gestoppte Turns werden auch im gespeicherten Zustand als
gestoppt beschriftet, ein Output-Limit ist bereits eingeklappt erkennbar.
Die Anzeige bleibt im Verlauf verfügbar. Sie zeigt ausschließlich vom Provider
gelieferte Reasoning-Texte/Zusammenfassungen, Arbeitsstatus und gemeldeten
Verbrauch mit Provider-Kosten oder ausdrücklich markierten Schätzungen.
Vor den Statusbezeichnungen stehen keine Striche. OpenAI-Summaries werden angefordert.
Verschlüsselte Reasoning-Blöcke werden weder angezeigt noch gespeichert.
Fehlendes sichtbares Reasoning und fehlende Usage sind ausdrücklich erkennbar;
es werden keine Denktexte erfunden. Die Stopptaste nutzt weiterhin den gemeinsamen
Abbruchmechanismus. Begrenzung: 32.000 Zeichen sichtbares Reasoning, höchstens
32 Reasoning-/Status-Einträge vor den abschließenden Status-/Usage-Ereignissen;
eine gekürzte Darstellung wird gekennzeichnet. Das Antwortlimit bleibt separat.

`activity`-SSE-Ereignisse haben `version: 1`, eine `step_id`, eine laufweit eindeutige `id`
und `kind: status | reasoning | usage | tool`. Reasoning-Deltas tragen `append: true`
und `format: text | summary`; gespeicherte Ereignisse enthalten den zusammen-
gefügten Text. `agent-activity.js` verarbeitet und rendert diese Ereignisse für
laufende Antworten und gespeicherte Turns. Schritt-IDs sind `completion:0..2`,
`tool:0..1`, `completion:N:web_search` und `run`. IDs enthalten den Schritt als
Präfix. `status.clear_response` ersetzt bei einer Modellfortsetzung einen
vorherigen Zwischenantworttext. Die eigentliche Turn-Antwort ist nur die letzte
Modellantwort. Tool-Einträge zeigen `running`, `succeeded`, `failed`, `blocked`,
`cancelled` oder `unknown` sowie begrenzte Ergebnisse/Quellen. Die Anzeige öffnet
sich auch für Tool-Ereignisse. Der Browser hält höchstens 64 Aktivitätseinträge;
der Server begrenzt Reasoning weiterhin über den gesamten Lauf auf 32.000 Zeichen.

## Begrenzter Tool-Loop und modellübergreifende Websuche (2026-09-15)

`agent_loop.py` steuert Modell → explizites Tool → Ergebnis → Modell mit einem
gemeinsamen Budget. `agent_tools.py` enthält die Freigaben und die erweiterbare
Registry für lokale, ausschließlich lesende Tools; sie ist im Produkt zunächst
leer. Neue Einträge brauchen ein striktes Pydantic-Argumentschema (`extra=forbid`),
eine serverseitige Freigabe und einen abbrechbaren Executor. Argumente sind auf
2.048 Zeichen beschränkt; unbekannte Tools, doppelte JSON-Schlüssel, falsche Typen,
zusätzliche Felder, parallele Calls und wiederholte Call-IDs werden abgewiesen.
Ergebnisse sind auf 8.000 Zeichen begrenzt. Kein `eval`, Shell- oder Schreibtool.
Die Fortsetzung mit Client-Tools ist zunächst nur für Haikus nicht denkendes
Protokoll freigegeben; andere Modelle benötigen eine Prüfung ihrer kompletten
Reasoning-/Signatur-Rückgabe. Es werden keine verschlüsselten Blöcke gespeichert.

**Jedes angebotene Modell erhält dieselbe Suchintegration wie Consensus.**
`engines.web_search_tool` liefert `openrouter:web_search` mit `engine: auto`;
Grok verwendet wie Consensus `exa`. OpenRouter führt native Suche oder Exa
innerhalb des gewählten Modellrequests aus. Das Modell entscheidet, ob es sucht.
Kein eigener Suchdienst und kein zusätzliches Suchmodell. Agent setzt `max_uses: 2`,
`max_tool_calls: 2`, fünf Ergebnisse pro Suche, zehn insgesamt und 2.000 Zeichen
pro Ergebnis; die Ergebnisgrenzen gelten für Exa, nicht für native Suche.
ZDR und Registry-Routing bleiben erhalten. Ohne expliziten Registry-Pin darf
OpenRouter zwischen Providern desselben Modells wechseln. Agent erzwingt weder
`only: ["anthropic"]` noch `require_parameters`, die funktionierende Haiku-Routen
ausgeschlossen hatten. `tool_choice` wird nur für echte Client-Tools gesetzt.
Der bestehende DeepSeek-Standard bleibt erhalten. Der Katalog liefert
`tools_by_effort`; der Turn speichert
die Freigaben in `agent_settings.tools` und die Budgetversion in `.policy`.

Die Chat-API liefert Quellenannotationen und `usage.server_tool_use.web_search_requests`,
aber keine zugesicherten nativen Startzeiten oder Suchqueries. Deshalb zeigt
die Aktivität ausschließlich bestätigte Nutzung/Quellen, niemals erfundene
„Suche läuft“-Schritte. Ohne Zähler/Quellen erscheint keine Suchzeile, auch nicht
bei Fehlern oder Abbruch. Fehlende Such-Usage verbraucht nur intern vorsorglich
das reservierte Suchbudget. Alte gespeicherte `unknown`-Server-Suchereignisse ohne
positiven Zähler oder Quellen werden ebenfalls ausgeblendet. Je Request
werden höchstens fünf unterschiedliche HTTP(S)-Quellen mit Titel/URL übernommen;
sie bleiben im Turn und werden sicher als Links dargestellt. Native interne
Suchinhalte liegen beim Provider; dessen `max_results` ist **kein** natives
Kontextlimit. Fehlende Rohresultate werden nicht rekonstruiert.

Der Systemprompt in `app/services/agent_runs.py` (`get_agent_system_prompt`) setzt
`AGENT_SYSTEM_PROMPT`, den frischen Datumsblock aus `llm/base.get_date_context`
und die ausgewählte Modellidentität zusammen. Datum, Wochentag, Uhrzeit bei
Request-Start und `Europe/Berlin` mit aktuellem UTC-Offset werden pro Nachricht
neu berechnet, auch bei gespeicherten Chats über Mitternacht. Berlin ist die
Anwendungsreferenz, kein angenommener Nutzerstandort; eine abweichende Nutzer-
Zeitzone oder ein ausdrücklich genanntes Bezugsdatum hat Vorrang. Das Datum
muss damit nicht über ein Tool erfragt werden. Derselbe Datumsblock wird von
Consensus-Einzelantworten, Synthese und Differences verwendet.
Der Prompt steht vor der User-/Assistant-Historie. Er fordert direkte
Antworten bei Begrüßungen, Smalltalk und Aufgaben, die ohne Tools zuverlässig
lösbar sind. Für aktuelle/externe Informationen oder einen ausdrücklichen
Suchauftrag darf das Modell suchen. Tool-Schemas werden separat angeboten;
ihre Verfügbarkeit löst keine Suche aus.

Geprüfte offizielle Dokumentation (15.09.2026):

- [OpenRouter: Web Search](https://openrouter.ai/docs/guides/features/server-tools/web-search): Auto/Exa, native Suche, Gebühren und Grenzen. Native `max_uses` wird nur an Anthropic weitergegeben.
- [OpenRouter: Server Tools](https://openrouter.ai/docs/guides/features/server-tools): serverseitige Schleife, gemeinsame Schrittgrenze und Kombination mit Client-Tools.
- [OpenRouter: Client Tools](https://openrouter.ai/docs/guides/features/tool-calling): gestreamte Tool-Aufrufe und Ergebnisrückgabe.
- [OpenRouter: Usage Accounting](https://openrouter.ai/docs/cookbook/administration/usage-accounting): `usage.cost` als Gesamtbetrag, native Tokenzahlen und Cache-Details.
- [OpenRouter: Fehler](https://openrouter.ai/docs/api_reference/errors-and-debugging): HTTP-/SSE-Fehler und `Retry-After`.
- [Claude: Web Search](https://platform.claude.com/docs/en/agents-and-tools/tool-use/web-search-tool) und [Haiku-Modellprofil](https://openrouter.ai/anthropic/claude-haiku-4.5): konkrete Fähigkeit, Providergrenzen und Preise.
- [Öffentlicher Haiku-Endpunktkatalog](https://openrouter.ai/api/v1/models/anthropic/claude-haiku-4.5/endpoints): Anthropic-Preise und unterstützte Parameter. `parallel_tool_calls` ist dort nicht angeboten und wird nicht gesendet; der Parser begrenzt Client-Calls selbst.

### Gemeinsame Budgets

`AgentPolicy` ist serverseitig und wird je Turn eingefroren:

| Grenze | Wert |
|---|---|
| Bezahlte Modellrequests | höchstens 3, Schritte `completion:0..2` |
| Tool-Nutzungen | Budget 2, serverseitige Suche und Client-Tools gemeinsam; native Providergrenzen siehe oben |
| Laufzeit | 180 Sekunden gemeinsam ab Produzentenstart |
| Input + Output | 4.000.000 Tokens als konservatives Zulassungsbudget einschließlich verdeckter Suchsegmente |
| Simulierte Kosten | 1 USD Zulassungsbudget pro Nachricht |
| Output pro Modellrequest | weiterhin standardmäßig 4.096 Tokens |
| Tool-Ergebnis / Quellen | 8.000 Zeichen / 5 Links |

`agent_costs.py` reserviert vor jedem Claim ein konservatives UTF-8-Inputbudget
plus Output-Reserve und prüft das Modellfenster. Native Suche reserviert wegen
unbekannten Provider-Kontexts das volle Modellfenster je möglichem Suchsegment
einschließlich Modellfortsetzung. Exa reserviert stattdessen die begrenzten
Suchergebnisse einschließlich UTF-8-/Protokollreserve je Fortsetzung. Das größere
Tokenbudget erlaubt die vollen Fenster von Gemini und Luna; das Kostenbudget
bleibt bei 1 USD. Fehlen Tokenzahlen oder eine vollständige Kostensumme,
bleibt die gesamte Reserve gebunden. Unbekannte Suchnutzung verbraucht vorsorglich
alle dafür reservierten Tool-Slots. Diese Beträge sind Simulationen und keine
harte Obergrenze einer Provider-Rechnung. Native interne Modellsegmente werden
nicht als zusätzliche von uns gestartete HTTP-Requests gezählt.

## Konfiguration

Der Server verwendet den bestehenden OpenRouter-Betreiberschlüssel. Die
Modell-/Tarifkonfiguration liegt zentral in `app/services/llm/agent_client.py`.
Optionale Umgebungsvariablen werden vor einem neuen Aufruf validiert:

| Variable | Standard |
|---|---|
| `AGENT_MODEL` | `deepseek/deepseek-v4.1-flash` |
| `AGENT_LABEL` | `DeepSeek V4.1 Flash` |
| `AGENT_MAX_OUTPUT_TOKENS` | `4096` (erlaubt: 256–16384) |
| `AGENT_INPUT_USD_PER_MILLION` | Katalogwert, aktuell `0.30` für den Standard |
| `AGENT_OUTPUT_USD_PER_MILLION` | Katalogwert, aktuell `1.20` für den Standard |
| `AGENT_CACHE_READ_USD_PER_MILLION` | Katalogwert, aktuell `0.006` für den Standard |
| `AGENT_CACHE_WRITE_USD_PER_MILLION` | Katalogwert, sonst Input-Tarif |
| `AGENT_PRICING_VERSION` | `openrouter-2026-09-15` |
| `AGENT_MAX_CONCURRENT_RUNS` | `16` pro Prozess (erlaubt: 1–64) |

Die Tarife dienen der Budgetreservierung und der gekennzeichneten Schätzung,
falls `usage.cost` fehlt. Auch das Standardmodell liest immer seinen aktuellen
Katalogsnapshot; die früheren fest eingebauten DeepSeek-Tarife überstimmen ihn
nicht mehr. Ein anderes `AGENT_MODEL`
benötigt einen Katalogeintrag: Kontext-/Outputgrenzen, Registry-Routing und
ohne expliziten Override auch Label, Tarife und Preisversion stammen dann von
diesem Modell. Bereits beanspruchte Aufrufe
behalten ihren Snapshot; abgeschlossene Requests bleiben trotz Konfigurations-
oder Schlüsselwechsel ohne neuen Modellaufruf wiederherstellbar.

Für jede Modellantwort hat ein valider `usage.cost` Vorrang: Er umfasst die
aktuelle Route, Cache-/Kontexttarife und Suchgebühren. Darauf werden keine
weiteren Token- oder Suchkosten addiert. Der Katalogfallback berechnet nur
gemeldete Input-/Output-Tokens, Cache-Reads und Cache-Writes sowie bekannte
Suchnutzung zum konfigurierten Such-/Katalogtarif. Er bleibt ausdrücklich eine
Schätzung: Native/Exa-Routen und Tarifstufen können vom Snapshot abweichen.
`AGENT_*`-Tarif-Overrides verändern niemals einen gemeldeten Provider-Gesamtbetrag.

## Verbrauch

`users/{uid}.agent_usage` enthält die kumulierten Input-/Output-Tokens und
`estimated_cost_nano_usd` (geteilt durch 1.000.000.000 ergibt USD).
Der Feldname bleibt kompatibel; neue Usage hat `cost_source: provider | catalog | mixed`.
Die Kontosumme trennt zusätzlich `provider_cost_nano_usd` und `catalog_cost_nano_usd`;
alte Summen ohne Herkunft werden in der Adminansicht als geschätzter Anteil behandelt.
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

Jeder bezahlte Schritt besitzt einen eigenen Beleg unter
`llm_calls/{sha256(chat,turn,step)}`. Claim und Verbrauchszähler bzw. Settlement
und Kostensumme sind jeweils atomar. Belege enthalten keine Fragen oder Antworten.
Der erste Beleg hält zusätzlich `run_token`, `run_status`, `last_step` und den
Policy-Snapshot. Eine Fortsetzung benötigt denselben Laufbesitzer, den erfolgreich
abgerechneten Vorgänger, eine aktive Lease und das passende Schrittbudget.
`settle(final=False)` gibt den Nutzer-Slot nicht frei. `finish_run` finalisiert
Turn, Aktivitäten und aggregierte Usage und gibt den einen Lauf-Slot atomar frei.
Eine verlorene Finish-Transaktion kann einen pending Turn hinterlassen; ohne
gespeicherte Antwort erlaubt Recovery keinen neuen Modellaufruf.

`agent_usage.complete=false` kennzeichnet eine Teilsumme: fehlende Tokens oder,
bei fehlendem Provider-Gesamtbetrag, unbekannte Suchkosten. Eine vorhandene
Gesamtkostensumme braucht keine Suchanzahl, um vollständig zu sein. `incomplete_calls` zählt solche
Belege zusätzlich zu `measured_calls`; Adminansicht und Chat weisen darauf hin.
Bereits gemessene Kosten früherer Schritte bleiben bei späterem Fehler erhalten.
Bekannte Suchkosten werden auch ohne gemeldete Tokenzahlen verbucht; die
Tokenfelder bleiben dann `null`. Auf mehrere Usage-Chunks verteilte Token- und
Suchangaben werden pro Request vor dem einmaligen Settlement zusammengeführt.

### Providerfehler und 429

HTTP-Fehler und Fehler innerhalb eines HTTP-200-SSE-Streams behalten ihren
Statuscode. Der Chat unterscheidet Rate-Limit, fehlende Route und fehlenden
Providerzugriff. Logs enthalten Modell-ID, sichere Fehlerkategorie und Wartezeit,
keine Provider-Rohtexte, Prompts oder Schlüssel. `Retry-After` bleibt erhalten.
`agent_provider_limits.py` sperrt weitere Agent-Anfragen für dieselbe Modell-/
API-Key-Kombination pro Prozess bis zum angegebenen Zeitpunkt (ohne Header:
30 Sekunden). Die Map enthält höchstens 256 Einträge, Schlüssel nur als Hash.
Prüfung vor Turn-Anlage und vor jedem Schritt; fertige Antworten bleiben ohne
Provideranfrage wiederherstellbar. Andere Modelle bleiben nutzbar. Keine
automatischen Transport-Retries; OpenRouter-Fallbacks betreffen dasselbe Modell.
Die Wartefrist ersetzt keine providerseitigen oder instanzübergreifenden Limits.

Live-Prüfung am 15.09.2026: Die alte Haiku-Agent-Route lieferte HTTP 404,
der Consensus-Request HTTP 200. Nach der Angleichung waren Suchanfragen für
Haiku, beide DeepSeek-Modelle, Gemini, Grok und Mistral samt Quellen und
Provider-Gesamtkosten erfolgreich. Luna lieferte auch mit unverändertem
Consensus-Request `rate_limit_exceeded` vom Upstream. Das ist kein Beleg für
eine funktionierende Luna-Live-Anfrage; dessen Suchvertrag ist zusätzlich mit
gemocktem Transport geprüft. Der Key war nicht im Free-Tier und hatte kein
gemeldetes Ausgabenlimit. Diese punktuelle Prüfung ersetzt keinen Lasttest.

## Grenzen und Erweiterung

Ein gewähltes Chatmodell, Streaming, persistenter Verlauf und die oben
freigegebenen Tools. Kein Fan-out, Judge, eigener Suchdienst, eigenes
API-Key-Routing oder weiterer LLM-Aufruf für Memory.
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
atomar mit dem ersten Beleg und wird erst beim Laufabschluss entfernt. Nach Prozessabsturz
läuft sie nach fünf Minuten aus; offene Belege bleiben sichtbar und werden
nicht erneut ausgeführt. Replays fertiger Antworten brauchen keinen freien Slot.

Der Claim entsteht erst beim Start des Stream-Produzenten. Disconnect vor
der ersten Iteration gibt den unbezahlten Turn und den Prozess-Slot frei.
Der gemeinsame SSE-Puffer ist auf 64 Ereignisse begrenzt; 30 Sekunden ohne
freien Pufferplatz brechen den Produzenten ab. Das Zeitbudget wird auch vor und
nach Datenbank-/Tool-Schritten geprüft; laufende synchrone Datenbank-RPCs selbst
werden nicht unterbrochen. Die fünfminütige Owner-/Chat-Lease wird bei Erst-Claim
gemeinsam gesetzt und zwischen Schritten nicht verlängert. Damit bleibt Abstand
zum dreiminütigen Providerbudget. Lang laufende Hintergrundaufgaben benötigen später eine
dauerhafte Job-Ausführung mit Checkpoints; diese Version führt begrenzte
Chat-Antworten innerhalb eines HTTP-Requests aus.

Transport (`llm/agent_client.py`), Ablauf (`agent_loop.py`), Policy/Tools
(`agent_policy.py`, `agent_tools.py`), Kosten (`agent_costs.py`) und persistente
Belege (`agent_runs.py`) sind getrennt. Die Registry ist die Erweiterungsstelle
für spätere explizit freigegebene Tools. Modell-Delegation und Kontextkomprimierung
sind nicht Bestandteil dieser Version. Die Consensus-Pipeline ist kein Tool.

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
`tests/test_agent_loop.py` prüft zusätzlich den nativen Request-/Usage-Vertrag,
den vollständigen Client-Tool-Loop mit einem lokalen Testtool, Argumentvalidierung,
gemeinsame Budgets, Schrittbelege, Mehrfach-Claims, Abbruch und Löschung zwischen
Schritten. Das ist keine Aussage über bezahlte Live-Provideraufrufe oder Produktionslast.

# Agent Runtime / Token Admission — 19. September 2026

## Änderung

Die bisherige Byte-Reserve konnte einen ausführbaren Aufruf ablehnen. Parallel
reservierte Calls wurden als endgültige Erschöpfung behandelt. Chat, Worker,
Vergleiche und Judges verwenden nun dieselbe tokenisierte Admission mit
abbrechbarem Warten, optionalem Suchverzicht und einem tatsächlich an den
Provider übergebenen, passenden Outputlimit. Gemessene Usage bleibt die einzige
Quelle für den verbrauchten Tagesanteil. Tokenizer-Daten sind offline gebündelt.

Der Produktprompt beschreibt consens.io und setzt die Consensus-Pipeline als
Standard für Sachfragen. Nicht freigegebene Worker-Anweisungen/Kataloge entfallen.
Nach einer reinen Server-Suchantwort kann eine zusätzliche Runde mit vorhandenen
Quellen und ohne erneute Suche die Client-Tools aufrufen.

## Regressionen

Vollständige Backend-Suite über `dev.ps1 check backend`: **2.531 bestanden**.
Ein vorher zeitabhängiger Replay-Test hält seinen injizierten Request-Zeitpunkt
jetzt konstant; sein Sicherheitsvertrag (kein zweiter Provideraufruf) ist unverändert.

`tests/test_agent_admission.py`: 15 Fälle, darunter großer Prompt mit 20.933
verfügbaren Tokens, parallele Vergleiche bei knappem Budget, Stop beim Warten,
kein bezahlter Retry, Provider-/Receipt-Outputlimit, explizite Reasoning-Budgets,
abgeschnittene Teilantwort, Unicode/Sondertoken-Text ohne Netzwerk, Suchkontext
und Übergabe nach einer Server-Suchantwort bis zum geprüften Consensus-Abschluss.

`tests/e2e/test_agent_transactions.py`: sechs Tests im isolierten Firestore-Emulator
bestanden. Der neue Fall startet zwei getrennte Chats mit gemeinsamem knappem
Tageskontingent: der zweite wartet, beide werden abgeschlossen, gemessene Tokens
werden genau einmal gezählt und keine Reservierung bleibt hängen.

`npm run build:check` über den E2E-Einstieg bestanden; keine Frontend-Änderung.

## Live-Routing

Begrenzte Aufrufe von `deepseek/deepseek-v4.1-flash` über den echten Adapter;
keine Account-/Chat-Datenbankwrites. Die Prüfung betrachtet die Toolauswahl,
nicht die inhaltliche Qualität einer vollständigen Live-Consensus-Antwort.

| Anfrage | Bestätigtes Verhalten | Gemessener Input + Output |
|---|---|---:|
| Warum ist der Himmel blau? | `compare_models` | 1.627 + 428 |
| Wer ist aktuell der beste Zwift-Fahrer der letzten 3 Jahre? | Recherche mit drei Quellen, dann `compare_models` | 4.202 + 657 |
| Hallo! | Direkte Antwort ohne Tool | 1.621 + 61 |

Ein erster Live-Versuch mit der Zwift-Frage endete nach Recherche ohne
Client-Toolcall. Dafür wurde die zusätzliche Orchestrierungsrunde ergänzt und
deterministisch durch den vollständigen Review-Fluss getestet. Ein Zwischenlauf
des Probeadapters hatte noch dessen altes 2.048-Zeichen-Argumentlimit; der finale
Probeadapter nutzt wie die App 24.000 Zeichen und vier Toolcalls pro Antwort.
Der abschließende Zwift-Aufruf lieferte bereits direkt `compare_models`.

Wiederholbar mit `venv/Scripts/python.exe artifacts/agent-runtime-admission/probe_routing.py --live`,
optional `--case fact|current|greeting`; höchstens zwei bezahlte Requests je Fall.
Credentials werden weder ausgegeben noch gespeichert. Rohberichte bleiben lokal.

## Grenzen und Quellen

cl100k plus Zuschlag ist eine modellübergreifende Zulassungsschätzung, keine
garantierte Obergrenze für fremde Tokenizer oder Provider-interne Verarbeitung.
Mehr gemeldeter Verbrauch wird weiterhin vollständig verbucht. Ohne finale
Usage bleibt Verbrauch unbekannt; es wird keine fiktive Messung abgebucht.
Kein Live-Test sämtlicher Provider und kein Produktiv-Deployment.

Der Suchadapter berücksichtigt den dokumentierten Server-Tool-Loop und dessen
Abschlussaufforderung am Schrittlimit:
[OpenRouter Server Tools](https://openrouter.ai/docs/guides/features/server-tools).
Die Ergebnisschranken stammen aus den
[Web Search Parameters](https://openrouter.ai/docs/guides/features/server-tools/web-search).
Tokenizer: [tiktoken 0.12.0](https://github.com/openai/tiktoken/tree/0.12.0).

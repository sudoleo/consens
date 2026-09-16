# Delegation im Agent-Chat

Implementierung zur [Spezifikation](agent-delegation-spec.md), Stand 16.09.2026.
Der ausgewählte Chatagent kann abgegrenzte Aufgaben delegieren. Einfache Fragen
bleiben direkte Antworten. Consensus ist weder aufgerufen noch verändert.
Die Funktion ist **standardmäßig aus**, weil der Live-Vergleich das Kostenkriterium
der Spezifikation nicht erfüllt. Zum gezielten Einsatz kann ein Admin unter
`/admin#configuration → Agent delegation → Allow delegation` sie aktivieren.
Die Aktivierung gilt für neue Runs; laufende Runs behalten ihre Konfiguration.

## Sitzungen und Kommunikation

`agent_delegation.py` erweitert den bestehenden Provider-/Run-Pfad um
`start_agent`, `send_agent`, `wait_agents`, `stop_agent`, `review_agent`.
Worker erhalten ausschließlich Auftrag und ausgewählten Kontext und können mit
`report_to_orchestrator` Zwischenresultate, Blocker und Rückfragen senden.
Fragen pausieren die Sitzung bis zur Antwort. Nachrichten während einer
Modellantwort werden an der nächsten gültigen Fortsetzungsgrenze zugestellt.
Nacharbeit verwendet dieselbe Agent-ID und denselben Gesprächsverlauf.
Token-Deltas führen nicht zu neuen Orchestrator-Aufrufen. Der Orchestrator kann
parallel selbst arbeiten oder explizit auf semantische Nachrichten warten.

Pro Modellantwort werden maximal vier Toolaufrufe angenommen; sämtliche Resultate
werden vor der nächsten Modellantwort in der ursprünglichen Reihenfolge geliefert.
Das ist nötig, weil einzelne Provider trotz `parallel_tool_calls=false` mehrere
Aufrufe liefern. Die tatsächliche Worker-Parallelität begrenzt ein gemeinsames
Semaphore. Worker haben keine Delegationstools. Bevor eine finale Antwort gespeichert
wird, müssen alle Ergebnisse oder unabhängig geprüften Ersatzlösungen mit
`review_agent` bewertet sein. `accepted=false, use_fallback=true` erlaubt eine
eigene, ausdrücklich geprüfte Korrektur ohne unnötige Echo-Nacharbeit.
Die Bewertung durch ein Modell ist keine Garantie fachlicher Richtigkeit.

## Provider und Modellwahl

Fähigkeiten und Tarife stammen aus `llm/agent_model_catalog.json`. Freigegeben sind
nur explizit geprüfte `delegation.tested_efforts`. Am 16.09. waren echte
Tool-Fortsetzungen für **Auto/default** mit Haiku 4.5, DeepSeek V4/V4.1 Flash,
Gemini 3.5 Flash Lite, Grok 4.3 ohne Reasoning und Mistral Small erfolgreich.
GPT-5.6 Luna ist nach Providerfehler nicht freigegeben. Nicht geprüfte manuelle
Reasoning-Stufen verwenden weiterhin den bestehenden direkten Chatpfad.
`GET /agent/models` liefert dies als `delegation_by_effort` aus.

Die vollständigen Reasoning-/Signaturblöcke werden ausschließlich im flüchtigen
Provider-Gespräch zur Fortsetzung erhalten. Verschlüsselte Blöcke werden nicht in
SSE, Seitenleiste oder Datenbank kopiert. Öffentliche Worker-Nachrichten sind eigene
Toolargumente/Ergebnisse, keine rekonstruierten Denkprotokolle. Grundlage des
Adapters: [OpenRouter-Fortsetzungsprotokoll](https://openrouter.ai/docs/guides/best-practices/reasoning-tokens)
und [Toolaufrufe](https://openrouter.ai/docs/guides/features/tool-calling).

## Persistenz, Abbruch und Kosten

Die Root-Receipt-ID ist die Run-ID; Agent, Auftrag, Nachricht/Ereignis und
Modellschritt haben stabile Identitäten. Modellschritte heißen `completion:N`
oder `agent:<uuid>:N`. Alle Pfade liegen unter dem authentifizierten Nutzer.
`agent_sessions.py` verwaltet kompakte Dokumente unter
`chats/{chat}/turns/{turn}/agents/{agent}` und getrennte `messages`-Subcollections.
`agent_events` enthält geordnete, deduplizierbare Zustandsereignisse mit globaler
Sequenznummer. Der bestehende 64-Einträge-Trace bleibt davon getrennt.

Jeder tatsächliche Provideraufruf erhält genau einen `llm_calls`-Beleg.
Claim, gemeinsame Token-/Kostenreserve und Account-Zähler werden atomar geschrieben;
Settlement, Freigabe bekannter Reserven und Account-Kosten ebenfalls.
Das Budget umfasst Orchestrierung, Worker, Suche und Nacharbeit. Provider-Gesamtkosten
haben Vorrang; Katalogschätzungen und unvollständige Messungen bleiben markiert.
`cost_complete` ist unabhängig von vollständigen Tokenzahlen. Unbekannte Anteile
werden niemals zu null oder zu einem Einsparungsbeleg. Agent- und Run-Summen verwenden
dieselben Schrittbelege; Reasoning ist bereits in Output-Tokens enthalten.

Das System friert Admin-Konfiguration, Prompts und Modell-/Tarifsnapshots pro Run ein.
Default: 32 Modellaufrufe, 48 Koordinationsaufrufe, 300 Sekunden, 4 Mio. konservativ
reservierte Tokens, 3 USD Kostenreserve, 4 Agenten, 2 gleichzeitig arbeitende Worker,
64 Nachrichten, 48.000 Kontextzeichen je Sitzung, 4.000 Zeichen je Nachricht,
8 Modellaufrufe je Worker und 2 Suchen insgesamt. Ein Worker lässt zwei Modellaufrufe
für den Orchestrator frei. Reserven sind Zulassungsgrenzen, keine Provider-Rechnungsgrenze.

Abbruch schließt sämtliche Provider-Sockets und wartet auf alle Worker. Ein Watchdog
prüft Run-Abbruch, Chatlöschung und Account-Sperren. Die Lease dauert Laufzeit plus
30 Sekunden. Nach Prozessverlust werden offene Belege beim Lesen nach Lease-Ablauf
als abgebrochen/unbekannt abgeschlossen; bereits bezahlte Schritte werden nie
neu gestartet. Reload lädt gespeicherte Sitzungen. Ein verlorener HTTP-Stream
wird aus Sicherheitsgründen abgebrochen, nicht als Hintergrundjob fortgesetzt.
Chat- und Kontolöschung entfernen auch Sitzungen/Nachrichten; entstandene Account-
Kosten bleiben bei Chatlöschung bestehen. Verspätete Resultate können gelöschte
Chats oder abgeschlossene Runs nicht wiederherstellen.

## Oberfläche und API

`App.agentDelegation` verarbeitet die `delegation`-SSE-Ereignisse. Eine gemeinsame
Projektion steuert Modell-Icons neben der Aktivität und die rechte Seitenleiste;
mobil wird sie als ausklappbare Detailfläche angezeigt. Manueller Schließzustand,
geöffnete Agenten und Scrollposition gelten pro Account und Turn. Bei Kontowechsel
werden ausstehende Requests verworfen. Texte werden mit `textContent` ausgegeben,
Quellen nur als validierte HTTP(S)-Links. Escape, native Details/Buttons und
Reduced Motion werden unterstützt. Stop beendet den ganzen Run.

Owner-/Pro-/Admin-geschützte Endpoints mit `private, no-store`:

- `GET /agent/chats/{chat}/turns/{turn}/agents`: maximal acht kompakte Agenten,
  Run-Status und bekannte Gesamtkosten.
- `GET /agent/chats/{chat}/turns/{turn}/agents/{agent}?after=<seq>&limit=25`:
  Auftrag und paginierte Nachrichten, maximal 50 je Request.
- `POST /agent/chats/{chat}/turns/{turn}/stop`: persistentes Abbruchsignal.

`/admin#configuration` verwaltet Delegationsregeln, beide Rollenprompts und Limits
im bestehenden revisionsgesicherten Dokument `app_config/prompts.delegation`.
Ältere Dokumente erhalten Defaults; ältere Save-Clients erhalten bereits gespeicherte
Delegationseinstellungen. Bestehende Turns bleiben unverändert lesbar.

## Nachweise und Qualitäts-/Kostenvergleich

Deterministischer Abnahmetest: `tests/test_agent_delegation.py` führt zwei parallele
Worker mit Rückfrage, Antwort, falschem Ergebnis, Korrektur in derselben Sitzung,
Prüfung und endgültiger Übernahme aus. Weitere Tests prüfen Teilfehler, Kosten,
Abbruch, Ablauf nach Prozessverlust, doppelte Events, Zugriff und Protokollblöcke.
Die Firestore-Racetests laufen in `tests/e2e/test_agent_transactions.py`;
Browser- und JS-Tests prüfen Kontowechsel, Wiederherstellung, doppelte Ereignisse,
echte Nachrichten und Desktop-/Mobilansichten.

Reproduzierbare Live-Prüfungen (kostenpflichtig, lokale `.env`; keine DB-Writes):

```powershell
.\venv\Scripts\python.exe scripts/probe_agent_delegation.py --live
.\venv\Scripts\python.exe scripts/evaluate_agent_delegation.py --live --worker deepseek-v4-flash --repeats 3
```

Der Vergleich verwendet denselben Orchestrator ohne und mit Delegation, sechs feste
synthetische Aufgaben (Arithmetik, Extraktion, zwei unabhängige Tabellen, Planung,
Regeln, Codeanalyse), exakte maschinelle Prüfkriterien, vollständige Schrittbelege,
Gesamtkosten und Laufzeiten. Die Reihenfolge wechselt zwischen Wiederholungen.
Die Tabellenaufgabe verlangt bei verfügbaren Tools explizit getrennte Prüfungen,
damit die Workerstrategie tatsächlich geprüft wird; die anderen Aufgaben erlauben
direkte Antworten. Der Datensatz ist mit SHA-256 eingefroren. Er belegt keine Qualität
für beliebige offene Fragen oder aktuelle Webrecherche. Caching/Routing können die
gemessenen Gesamtkosten beeinflussen; deshalb keine Hochrechnung einzelner Tarife.
Freigabe verlangt mindestens drei vollständige Paare pro Aufgabe, keine fehlgeschlagene
Prüfung, vollständige Providerkosten, tatsächliche Delegation und mindestens 5 %
Gesamtersparnis mit Ersparnis in jeder Wiederholung. Unbekannte Kosten blockieren
eine Preispräferenz. Ein gescheiterter Vergleich ändert die Workerwahl nicht automatisch.

### Ergebnis vom 16.09.2026

Orchestrator: DeepSeek V4.1 Flash; Worker-Kandidat: DeepSeek V4 Flash;
drei Wiederholungen je Aufgabe. [Vollständige Belege](../artifacts/agent-delegation-evaluation-deepseek.json)
und [Live-Protokollprüfung](../artifacts/agent-delegation-protocol.json).

| Variante | Objektive Prüfungen | Gesamtkosten (Provider) | Modellaufrufe | Summe Laufzeiten |
|---|---:|---:|---:|---:|
| Ohne Delegation | 18/18 | 0,007289580 USD | 18 | 138,192 s |
| Mit Delegation | 18/18 | 0,016690483 USD | 39 | 211,942 s |

Damit **keine Freigabe als Standard oder einer automatischen Preispräferenz**: gleiche Qualität in
diesem begrenzten Datensatz, aber rund 129 % höhere Gesamtkosten. Die beiden
Tabellenprüfungen verwendeten tatsächlich zwei Worker; übrige Aufgaben wurden
direkt gelöst. Die Workerstrategie kostet dort acht statt eines Modellaufrufs.
Kleine Rechen-, Extraktions- und Regelaufgaben direkt zu lösen ist daher die
begründete Ausgangswahl. Für umfangreichere unabhängige Aufgaben fehlen noch
positive Belege; kein allgemeines Einsparungsversprechen.

Ein [einzelner Mistral-Vorlauf](../artifacts/agent-delegation-ledger-check.json)
zeigte Rechenfehler und wiederholte Nacharbeit. Er diente zur Verbesserung der
Ersatzlösungs-Schnittstelle und ist wegen anderer Harness-Version und nur einer
Aufgabe **kein fairer Modell-Rangvergleich** mit dem abschließenden Datensatz.

# Agent Beta: Zuverlässigkeit, Limits und Wartezeiten

Prüfung vom 20.09.2026. Direkte Umsetzung auf `main`, ohne parallele Codearbeit.
Umfang: API-Vorbereitung, gemeinsame Admission für Orchestrator/Worker/Vergleiche/
Judges, Tagesledger, Provider-SSE, Abbruch/Recovery, Speicherung sowie Browser-UX.
Die Änderungen ergänzen den [Accounting-Audit](agent-accounting-audit.md).

## Einschätzung

Der gemeinsame Ledger mit atomaren Claims und idempotentem Settlement ist eine
tragfähige Grundlage. Ein höheres Tokenlimit allein hätte die gefundenen Probleme
nicht behoben: Es gab Lebenszykluslücken vor dem ersten Call, Stillstand trotz
lebender Verbindung und verlorene Teilantworten. Diese Fehler sind behoben.
Eine Garantie „alle Fehler gefunden“ oder nachgewiesene Produktionslatenz lässt
sich aus deterministischen Tests nicht ableiten.

Als Herzstück braucht der Agent zusätzlich belastbare Messungen unter realer Last
und einen bewussten Vertrag für Verbindungsverlust. Ein unbegrenzt erlaubter Run
ist nicht automatisch ein dauerhafter Hintergrundauftrag. Der aktuelle Producer
lebt weiterhin im Webprozess und hängt an der Clientverbindung.

## Behobene Fehler

| Priorität | Auslöser und bisherige Folge | Korrektur |
|---|---|---|
| Hoch | 20 ältere `run_status=running`-Belege ohne Producer-Lease lagen vor einem verwaisten neuen Run: die Recovery fand dessen Reservierung nicht. | Die Datenbank filtert vor dem Seitenlimit auf das Producer-Protokoll (`policy.delegation`). Regression mit 25 Legacy-Belegen. |
| Hoch | Stop kam während der Token-Zulassung, bevor ein Root-Receipt existierte: Stop schrieb nichts; später konnte der Call doch starten. | Transaktionaler Stop beendet den pending Turn oder markiert den bereits beanspruchten Producer. Erster Claim und Stop sind atomar gegeneinander gesichert. |
| Hoch | Prozessausfall vor dem ersten Claim: Recovery blieb dauerhaft „running“, weil nur Root-Leases betrachtet wurden. | Abgelaufene Chat-Reservierungen werden auch ohne Root terminal; die Sperre eines neueren Turns wird nicht verändert. |
| Hoch | Provider sendete unbegrenzt Kommentare/Leerereignisse, während die Socket-Timeouts nie auslösten. | Fortschritts-Watchdog prüft auch einen ausstehenden Read; Default 180 s Stille, konfigurierbar, kein Gesamtlaufzeitlimit. |
| Hoch | Nach fertigem Vergleich scheiterte die Synthese mitten im Text: nur der leere/vorige Review-Snapshot blieb gespeichert. | Teiltext wird nach Settlement als ungeprüfte Version gesichert; Timeout, Outputlimit und Stop sind getestet. |
| Mittel | Eine Vergleichsantwort war fertig, andere liefen noch: der gemeinsame Review wurde erst nach allen Antworten gespeichert. | Jede fertige Antwort wird sofort checkpointed und über SSE projiziert. Endreihenfolge bleibt deterministisch. |
| Mittel | Aktive Reservierungen lösten Warten aus, obwohl auch deren vollständige Freigabe nicht für Input + Mindestantwort gereicht hätte. | Solche unmöglichen Zulassungen enden sofort, ohne weitere Provideraufrufe oder zusätzliche Reserven. |
| Mittel | Loop-Konstruktor scheiterte außerhalb des geschützten API-Blocks. | Vorbereitung räumt Turn und Prozesskapazität auch bei Initialisierungsfehlern auf. |
| Mittel | Abbruch zwischen Statusereignis und Dispatch konnte als unbekannter Verbrauch erscheinen. | Letzte Cancellation-Prüfung vor Dispatch; nachweislich nicht gestarteter Call erhält Nullverbrauch statt unbekannter Usage. |
| Mittel | Modellkatalog, Budget, Sidebar, Stop oder Recovery hingen ohne Netzwerkdeadline. Auch ein toter Browser-SSE-Kanal blieb endlos offen. | Wiederverwendbarer, abbrechbarer Request-Wrapper: 15 s für Steueranfragen, 45 s ohne Bytes für SSE. Recovery startet keine neue Generierung. |
| Mittel | Ab Ereignis 65 wurden neue Live-Aktivitäten verworfen; alte Statusupdates galten als zeitlich neuester Stand. | Fenster der neuesten 64 Ereignisse, aktualisierte Statusereignisse werden korrekt zeitlich eingeordnet. |
| Mittel | Token-Warten sah wie Arbeit aus, wartende Vergleichsmodelle wie laufende Calls. | Sichtbarer Wartegrund, passender Status in Taskzeile/Sidebar, echte Arbeitsanzeige erst nach Admission. |
| Mittel | API akzeptierte bis zu neun Vergleichsfamilien trotz Sechsergrenze des Pickers. | Serverseitige Auswahl nutzt dieselbe `MAX_RUN_FAMILIES`-Konstante. |

Zusätzlich wurden zwei bereits veraltete CSS-Import-Cache-Keys korrigiert, die der
vollständige Backend-Check sichtbar machte. Das Produktionsbundle wurde neu gebaut.

## Geprüfte Invarianten

- Keine Modellwiederholung durch Buchhaltungsretry, Recovery oder Timeout.
- Gemessene Input-/Outputtokens werden einmal gezählt. Cache/Reasoning sind
  Unterkategorien; unbekannte finale Usage wird nicht als Messung erfunden.
- Reservierungen enden beim Settlement; andere aktive Reservierungen bleiben erhalten.
- UTC-Tag und Budgetgeneration bleiben beim begonnenen Aufruf gebunden.
- Stop vor, während und nach Admission; Account-/Chat-Fencing und Auth-Wechsel.
- Produktive lange Streams und Runs bleiben möglich. Stille/Transportverlust wird
  unabhängig von einer Gesamtlaufzeit behandelt.
- Fehlgeschlagene Synthese und fertige Vergleiche bleiben lesbar und werden nicht
  als erfolgreich geprüft dargestellt.
- Desktop/Mobil, geschlossene Aktivitätsdetails, Overflow, Stop, Wiederherstellung,
  Modellwechsel, verspätete Budgets und reduzierte Animationen.

## Verbleibende technische und produktseitige Risiken

1. **Dauerhafte Ausführung bei Verbindungsverlust.** Ein Tabwechsel ist abgefangen,
   eine tatsächlich geschlossene SSE-Verbindung beendet weiterhin den Producer.
   Für verlässlich im Hintergrund weiterlaufende Aufgaben empfehle ich als nächsten
   Architekturauftrag eine persistente Job-Ausführung mit Lease, Eventcursor und
   Wiederanschluss; expliziter Stop muss separat behandelt werden. Das ändert
   Kosten-/Abbruchsemantik und sollte als eigener Produktvertrag umgesetzt werden.
2. **Unbekannte Providerrechnung.** Finale Usage kann nach Abbruch fehlen. Die
   Reserve wird freigegeben, der Verbrauch bleibt unbekannt; das finanzielle
   Risiko liegt dann beim Betreiber. Ein späterer Abgleich anhand der vorhandenen
   `generation_id` wäre der nächste Accounting-Schritt. Nicht jeden Netzwerkabbruch
   als kostenlosen Call interpretieren. OpenRouter garantiert Billing-Abbruch
   nicht für alle gerouteten Provider; siehe die
   [primäre Streaming-Dokumentation](https://openrouter.ai/docs/api_reference/streaming).
3. **Datenbankausfälle.** Firestore-Ledger-/Chat-Transaktionen verwenden weiterhin
   den synchronen SDK-Pfad mit SDK-Retries; Stop kann deren laufenden Commit nicht
   unterbrechen. Die 15-s-Frist im Browser ist keine garantierte serverseitige
   Transaktionsfrist. Ein systematisches RPC-/Retry-Budget für die gesamte
   Persistenzschicht ist weiterhin technische Schuld; private SDK-Methoden wurden
   nicht überschrieben.
4. **Qualität gegen Latenz.** Bei sechs Vergleichsmodellen und zwei parallelen
   Unteraufrufen entstehen mindestens drei Ausführungswellen, dazu Orchestrierung,
   Synthese und Judges. Das ist eine strukturelle Wartezeit, kein Anzeigeproblem.
   Meine Empfehlung: zwei oder drei schnelle Vergleichsmodelle als bewusstes
   Standardprofil prüfen; weitere Perspektiven für komplexe Fragen. Die geltende
   Produktregel „jede Frage durch Consensus“ und die Nutzerauswahl bleiben bestehen.
5. **Messbarkeit.** Die vorhandenen Providermetriken liefern Aggregate, aber keinen
   nachgewiesenen p50/p95-Verlauf für erste sichtbare Antwort, Admission-Wartezeit,
   Synthese und Prüfabschluss über Deployments. Genau diese Messungen sollten vor
   einer breiten Freigabe die Modell-/Parallelitätsentscheidung bestimmen. Lokale
   Mock-Laufzeiten sind kein Ersatz für reale Providerlatenzen.
6. **Sehr lange Chats.** Initial bleiben 120.000 Zeichen und das Modellfenster
   verbindlich; der Review-Snapshot hat 600 kB. Es gibt bewusst keinen Kompressor.
   Ein unbegrenzt wachsender Chat ist damit kein zugesagter Produktumfang. Der
   Run-Root sammelt außerdem Schrittzustände und Usage bis zur Firestore-Dokumentgrenze;
   für sehr große zukünftige Agentaufträge gehören diese Daten in paginierbare Belege.

## Validierung

| Prüfung | Ergebnis |
|---|---|
| Vollständiger Backend-Check (`.\dev.ps1 check backend`) | 2.706 bestanden; 14 Deprecation-Warnungen des lokalen Python-3.9-Asyncio-Pfads |
| Vollständiger Frontend-Check (`.\dev.ps1 check frontend`) | 56 Dateien, 488 Tests bestanden |
| Agent-Browserprüfungen: Chat, Vergleiche, Delegation | 44 Desktop-/Mobilfälle bestanden; die drei Warte-/Stop-Ansichten nach der finalen Sidebar-Korrektur erneut bestanden |
| Firestore-Emulator (`.\dev.ps1 check browser -TestPath tests/e2e/test_agent_transactions.py`) | 7 bestanden, einschließlich parallelem Stop/Claim und Recovery hinter 25 Legacy-Belegen |
| Produktionsbundle | `npm run build` und abschließendes `npm run build:check` erfolgreich; Vorversionen für bereits geöffnete Tabs erhalten |
| Diff und Darstellung | `git diff --check` sauber; Wartezustand bei 1280 px hell, 390 px dunkel und 320 px hell visuell geprüft |

Die neuen Fälle stehen in `tests/test_agent_reliability.py`, in den Agent-
Frontendtests und in `tests/e2e/test_agent_transactions.py`. Der neue Stop-/Start-
Racetest deaktiviert absichtlich den lokalen Account-Lock und prüft die echte
Firestore-Transaktion wie bei zwei Serverprozessen.

Provideraufrufe sind deterministische Doubles bzw. echte HTTPX-Streamparser mit
simulierter Transportgegenstelle. Keine bezahlten Live-Modellaufrufe und keine
Produktionsdaten wurden verwendet. Visuelle Belege:
[Desktop](../artifacts/agent-reliability-2026-09-20/agent-allowance-wait-1280-light.png),
[Mobil dunkel](../artifacts/agent-reliability-2026-09-20/agent-allowance-wait-390-dark.png),
[Mobil 320 px](../artifacts/agent-reliability-2026-09-20/agent-allowance-wait-320-light.png).

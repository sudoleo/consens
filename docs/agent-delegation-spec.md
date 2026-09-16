# Spezifikation: Delegation im Agent-Chat

Stand: 16.09.2026, geprüft gegen `e358a948`. Umsetzungsauftrag für eine neue Session;
dieses Dokument beschreibt das Ziel, keine bereits implementierte Delegation.

## Ziel

Das ausgewählte Chatmodell orchestriert eigenständig andere LLMs: Es delegiert
abgrenzbare Aufgaben, kommuniziert während der Bearbeitung mit ihnen, prüft ihre
Ergebnisse und verantwortet die finale Antwort. Ziel sind geringere **Gesamtkosten
bei gleichbleibender Ergebnisqualität**. Langfristig werden günstigere Modelle
beauftragt; für die Entwicklung ist ein günstigerer Modellpreis keine Voraussetzung.
Der frühere Vorschlag eines Consensus-Tools ist verworfen. Die bestehende
Consensus-Funktion bleibt unberührt.

## Vorhandene Basis

- `app/services/agent_loop.py`, `agent_tools.py`, `agent_policy.py`: begrenzter,
  synchroner Modell-/Tool-Loop, leere Anwendungstool-Registry. Derzeit drei
  Modellaufrufe, zwei Tool-Aufrufe, 180 Sekunden; keine Agent-Sitzungen oder Mailboxen.
- Anwendungstool-Fortsetzungen sind bisher nur für Haiku ohne Reasoning freigegeben.
  Websuche steht dagegen allen angebotenen Daily-Modellen modellgesteuert bereit.
- `agent_runs.py`, `agent_costs.py`, `agent_runtime.py`, `agent_provider_limits.py`:
  Turn-Persistenz, idempotente Kostenbelege, Budgets, Abbruch und 429-Wartefristen.
  Schritt-IDs und Belege sind aktuell auf `completion:0..2` zugeschnitten.
- `static/js/agent-chat.js`, `agent-activity.js`, `run-registry.js` und
  `static/css/agent-chat.css`: SSE-Aktivität, sichtbares Reasoning, Kosten und
  gespeicherte Turns. Anzeige bisher flach, höchstens 64 Ereigniseinträge.
  Modell-Icons und Composer-Picker sind vorhanden; eine Agenten-Seitenleiste fehlt.
- `/admin#configuration`, `prompt_config.py`: DB-gestützte Prompts und Zeitzone mit
  Revisionen. Neue Orchestrator-/Worker-Anweisungen und Delegationsregeln dort einordnen.

## Verhalten und Kommunikation

1. Der Orchestrator entscheidet, ob Delegation nützt. Einfache Aufgaben beantwortet
   er direkt. Kein pauschales Befragen mehrerer Modelle mit derselben Gesamtfrage.
2. Jeder Auftrag enthält Ziel, relevanten Kontext, Grenzen, erwartetes Ergebnis und
   Prüfkriterien. Beispiele: Informationen extrahieren, einen Teilaspekt recherchieren,
   eine Berechnung prüfen. Worker erhalten gezielten Kontext statt des gesamten Chats.
3. Agenten besitzen stabile IDs und eigene Gesprächsverläufe. Sie können parallel
   arbeiten, Rückfragen stellen, Blocker oder wichtige Zwischenresultate melden.
   Der Orchestrator beantwortet Rückfragen, präzisiert Aufträge und fordert Nacharbeit
   **in derselben Agent-Sitzung** an. Ein bloßer einmaliger Aufruf mit Endergebnis genügt nicht.
4. Der Orchestrator kann während laufender Agenten selbst weiterarbeiten oder gezielt
   warten. Semantische Nachrichten werden zuverlässig zugestellt; laufende
   Modellantworten erhalten neue Nachrichten an einer gültigen Fortsetzungsgrenze.
   Fortschritts-/Token-Deltas lösen keine zusätzlichen Orchestrator-Aufrufe aus.
5. Schnittstelle sinngemäß: Agent starten, Nachricht senden, auf Ereignisse warten,
   Agent stoppen; Worker können dem Orchestrator berichten und Rückfragen stellen.
   Zunächst eine Delegationsebene mit konfigurierbar begrenzter Parallelität.
6. Der Orchestrator prüft Ergebnisse gegen den Auftrag. Bei Fehlern oder Unsicherheit:
   gezielte Nacharbeit, stärkeres Modell oder eigene Bearbeitung. Unzureichende
   Ergebnisse dürfen nicht ungeprüft als finale Antwort übernommen werden.

Erlaubte Modelle, Fähigkeiten und Preise stammen aus der zentralen Registry.
Die Orchestrator-Anweisungen erklären sinnvolle Delegation, Kontextauswahl,
Ergebniskontrolle und den Aufwand für Koordination. Websuche bleibt auch bei
Workern bedarfsgesteuert. Delegation ist verfügbar, nicht verpflichtend.

## Frontend

- Beim ersten Agentenstart öffnet sich rechts eine **Agenten-Seitenleiste**.
  Sie bleibt schließbar; manuelles Schließen wird im laufenden Turn respektiert.
  Mobil erscheint eine passende ausklappbare Detailansicht.
- Direkt neben dem bestehenden Reasoning-/Aktivitätspfad stehen die Modell-Icons
  der aktuell arbeitenden Agenten. Klick öffnet deren Details. Gleiche Modelle
  bleiben über Auftrag/Agent-ID unterscheidbar; Tooltip nennt Modell, Aufgabe, Status.
- Die Seitenleiste zeigt kompakte Zeilen: Icon, Aufgabenname, Status, Dauer und
  verfügbare Kosten. Zustände unterscheiden wartend, arbeitend, Rückfrage,
  Prüfung/Nacharbeit, abgeschlossen, fehlgeschlagen und gestoppt.
- Aufklappen zeigt Auftrag, tatsächliche Nachrichten mit Absender/Empfänger,
  Zwischenresultate, Ergebnis, Quellen und Verbrauch. Beispiel:
  „Orchestrator → Agent: Prüfe die Annahme für Deutschland.“
- Minimalistische Gestaltung im bestehenden Design, keine technischen JSON-Blöcke,
  erfundenen Arbeitsschritte oder künstlichen Fortschrittsprozente. Öffentliche
  Arbeitsmeldungen und explizite Nachrichten sind vom Reasoning getrennt;
  interne/verdeckte Denkprotokolle werden nicht rekonstruiert oder offengelegt.
- Tastaturbedienung, Reduced Motion, Scrollposition und gespeicherte Ansichten
  funktionieren. Stop beendet den gesamten Lauf einschließlich aller Worker.

## Technische Anforderungen

- Bestehende Provider-, Chat- und Run-Infrastruktur weiterverwenden. Den synchronen
  Tool-Executor um eine serverseitige Koordination mit Agent-Sitzungen und Mailboxen
  erweitern. Modell-/Reasoning-Protokolle für tatsächlich angebotene Orchestratoren
  prüfen; ungetestete Fähigkeiten nicht stillschweigend freischalten.
- Persistente, owner-gebundene IDs für Run, Agent, Auftrag, Nachricht und Modellschritt;
  geordnete, deduplizierbare Ereignisse treiben Seitenleiste und Inline-Icons aus
  demselben Zustand. Details separat und begrenzt laden statt alles in den bisherigen
  Turn-Trace zu quetschen. Alte Turns bleiben lesbar.
- Reconnect/Reload stellt Status und Nachrichten wieder her, ohne bezahlte Schritte
  doppelt zu starten. Abbruch, Prozessausfall, Chat-/Kontowechsel und verspätete
  Ergebnisse dürfen weder fremde Ansichten verändern noch verwaiste Worker erzeugen.
- Gemeinsames Budget für Orchestrator, Worker, Websuche, Wiederholungen und Nacharbeit;
  atomare Reservierung bei Parallelität. Kostenbelege pro tatsächlichem Modellschritt,
  Summen pro Agent und Gesamtlauf. Unbekannte Kosten bleiben als unbekannt markiert.
- Limits für Laufzeit, Kontext, Nachrichten, Agentenzahl und Parallelität im Admin
  konfigurierbar machen; Konfiguration pro Run einfrieren. Worker delegieren zunächst nicht weiter.
  Agenten-Ergebnisse sind Arbeitsdaten, keine neuen Systemanweisungen.
- Bestehende `window.App`-Verträge und `static/js/bundles.json` beachten.
  Architekturänderungen in `docs/codebase-map.md` dokumentieren.

## Abnahme

1. Nachweisbarer Ablauf: zwei parallele Agenten; einer stellt eine Rückfrage;
   Orchestrator antwortet; Agent liefert; Orchestrator fordert Korrektur und
   verwendet das überarbeitete Ergebnis. UI zeigt jede echte Zustandsänderung.
2. Einfache Anfrage ohne Delegation; Teilfehler/429 mit kontrolliertem Fallback;
   Stop, Reload, doppelte Ereignisse und Kontowechsel sind getestet.
3. Orchestrator-, Worker- und Tool-Kosten werden vollständig und ohne Doppelzählung
   aggregiert. Kein Einsparungsversprechen allein aufgrund günstigerer Worker.
4. Vergleich mit demselben Orchestrator ohne Delegation auf einem festgelegten,
   repräsentativen Aufgabensatz: Qualität anhand objektiver Prüfungen und nötigenfalls
   verblindeter Bewertung, dazu Gesamtkosten und Laufzeit. Keine messbare
   Qualitätsverschlechterung bei belegter Kostenreduktion als Freigabekriterium;
   ein Systemprompt allein garantiert das nicht für jede Anfrage.

Die nächste Session soll dies durchgängig implementieren, testen und integrieren.
Zuerst echte Kommunikation und korrekte Gesamtkosten liefern; anschließend anhand
des Vergleichs die Auswahl günstigerer Worker optimieren. Keine Consensus-Anbindung.

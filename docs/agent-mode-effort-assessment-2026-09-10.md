# Aufwand: zusätzlicher Arbeitsmodus oder Ersatz des Agentenmodus

Stand: 10. September 2026. Statische Prüfung des lokalen Codes. Entwurf und
Aufwandsschätzung, keine Änderung der Produktarchitektur. Keine Tests oder
Produktionsaufrufe ausgeführt; die bestehende Testbasis wurde nicht neu verifiziert.

## Schätzgrundlage

Eine Codex-Stunde meint kumulierte aktive Bearbeitung in diesem Repository,
einschließlich Lesen, Implementierung, Testausführung, Auswertung und Korrekturen.
Die Spannen sind meine Planungsschätzung aus den unten genannten Abhängigkeiten,
keine gemessene Codex-Geschwindigkeit und keine garantierte Lieferzeit.
Warten auf Entscheidungen, Kontofreigaben, externe Infrastruktur oder Nutzungslimits
ist nicht enthalten. Keine angenommene Beschleunigung durch parallele Agenten.

Der vergleichbare Zielumfang beider Varianten ist eine begrenzte erste Beta:

- Ein serverseitiger Koordinator kann Modelle nach Bedarf mit Teilaufgaben
  beauftragen, Ergebnisse prüfen und innerhalb enger Grenzen nacharbeiten.
- Recherche mit vorhandener Provider-Websuche und explizitem URL-Abruf;
  Auswertung bereits unterstützter Upload-Formate; begrenzte, definierte
  Berechnungswerkzeuge; herunterladbare Markdown- und CSV-Ergebnisse.
- Strukturierte Schritte, Quellenprovenienz, ein finales Ergebnis sowie
  einfache Rückfragen und Fortsetzungen im vorhandenen Chat.
- Serverseitige Aufruf-, Token-, Zeit- und Kostenreservierungen. Preisgrundlagen
  und die vom Provider gelieferten Nutzungsdaten müssen dafür angebunden werden;
  ein harter Geldrahmen verlangt konservative Reservierung vor externen Calls.
- Speicherung des Arbeitsstands, Status nach Reload, Abbruch und kontrollierte
  Wiederaufnahme sicher wiederholbarer Schritte; Behandlung fehlender Own-Keys.
- Bestehende Auth-, Tier-, Own-Key-, Lösch- und Persistenzverträge bleiben gültig.
- Automatisierte Verhaltenstests, Browserregressionen, Dokumentation und Build
  sowie ein kleiner realer Aufgabensatz für Qualität und Kosten.

Nicht enthalten: beliebige Codeausführung, allgemeine Browserbedienung,
schreibende externe Integrationen, OAuth-Verbindungen, hochwertige DOCX/PPTX/XLSX-
Bearbeitung, ein Dateimanager, kollaborative Workspaces oder beliebig lange Jobs.
Eine Codex-ähnliche Universalumgebung lässt sich aus dem bisherigen Gespräch
nicht seriös als festes Gesamtpaket schätzen.

## Verifizierte Ausgangslage

| Bereich | Vorhanden | Konsequenz |
| --- | --- | --- |
| Modelltransport | `app/services/llm/engines.py:138` baut gemeinsame OpenRouter-Payloads mit nativer Websuche. Der Antwortpfad ab Zeile 256 normalisiert Text und Quellen. | Provideranbindung wiederverwenden; strukturierte Agentenaktionen, Werkzeugergebnisse und Nutzungsdaten ergänzen. Eine allgemeine lokale Werkzeugschleife ist im geprüften Pfad nicht implementiert. |
| Browser-Ausführung | `static/js/query-send.js:499` fragt alle gewählten Provider parallel ab; Zeile 527 startet danach Auto-Consensus. Zeile 590 verlangt mindestens zwei Provider. | Dynamische Auswahl und wiederholte Teilaufträge brauchen einen eigenen serverseitigen Runner. Ein Patch nur an `agent-mode.js` reicht nicht. |
| Frontend-State | `static/js/run-registry.js:220` friert die Konfiguration ein; `modelResults` und Fortschritt bilden ausgewählte Modelle ab. | Run-Identität, Sichtwechsel und Auth-Abgrenzung sind nützlich. Dynamische Arbeit benötigt eine separate Schrittstruktur und neue Statusereignisse. |
| Speicherung | `app/services/chat_store.py:831` finalisiert mit Consensus, Differences und Modellantworten. Eine veränderte zweite Completion ist ein Konflikt. Modellantworten werden je Provider abgelegt. | Arbeitsaufträge brauchen eigene Schritt-IDs und Zwischenstände. Finale Ergebnisse einmal abschließen; alte Turns über ihren bisherigen Vertrag anzeigen. |
| Asynchrone Arbeit | `api_consensus_runner.py:289`, `api_run_repository.py:64` und `source_check_jobs.py:107` bieten persistente Jobs, Claims und Recovery-Muster. | Gute Vorlagen, aber keine fertige allgemeine Agentenlaufzeit. Die API arbeitet weiterhin eine feste Consensus-Pipeline ab; ihre Recovery ersetzt keine Wiederaufnahme einzelner Arbeitsschritte. |
| Budgets | `usage_repository.py:51` kennt Regular-/Deep-Think-Runs; `claim_operation` verhindert wiederholte Autorisierung derselben Operation. `provider_runtime.py:189` begrenzt Analysezeit und Call-Anzahl. | Vorhandene Schutzmechanismen nutzen. Dynamische Schritte und kumulierte Geld-/Tokenbudgets zusätzlich modellieren. Tages-Run-Zähler sind kein Geldbudget. |
| Quellen und Uploads | `source_documents.py` lädt und extrahiert öffentliche Dokumente; `llm/attachments.py:317` verarbeitet vorhandene Upload-Typen. Quellenprüfungen haben dauerhafte Jobs. | Abruf, Extraktion und Validierung teilweise wiederverwendbar. Ein gemeinsamer Belegbestand vor der Synthese und die Bindung an Arbeitsschritte fehlen. |
| Dateien | Uploads werden verarbeitet, eine allgemeine Agenten-Artefaktverwaltung wurde im geprüften Anwendungscode nicht gefunden. Datei-Bytes werden bisher nicht in Firestore gespeichert. | Ausgabeformate, sichere Download-Endpunkte, Eigentümerbindung, Aufbewahrung und Löschung bauen. Fortsetzbare Jobs benötigen einen bewussten Umgang mit Upload-Inhalten. |
| Weitere Produkte | API, Watches und Topics rufen `run_consensus_pipeline` auf; der Browser hat zusätzlich einen eigenen Streamingpfad in `chat.py`. | Browser-Agentenmodus ersetzen und sämtliche Consensus-Produkte umstellen sind verschiedene Vorhaben. Gemeinsame Änderungen haben größere Regressionseffekte. |

Die vorhandenen Pytest-, Vitest- und isolierten Playwright-/Emulator-Tests sind
ein Vorteil. Sie enthalten aber bisherige Produktannahmen, die beim Ersatz
bewusst getrennt oder aktualisiert werden müssen. Bestehende grüne Tests würden
noch keine gute agentische Aufgabenlösung nachweisen.

## Aufwandsspannen

Die Werte sind jeweils Gesamtaufwände ab dem jetzigen Stand. Prototyp und Beta
sind nicht zu addieren. Die Varianten sind Alternativen.

| Variante | Vorführbarer Prototyp | Nutzbare erste Beta im beschriebenen Umfang |
| --- | --- | --- |
| Zusätzlicher Arbeitsmodus | 4–8 Codex-Stunden | 18–35 Codex-Stunden, ungefähr 8–12 abgegrenzte Arbeitspakete |
| Bestehenden Agentenmodus ersetzen | 6–12 Codex-Stunden | 25–50 Codex-Stunden, ungefähr 12–18 Arbeitspakete |

Ein Prototyp zeigt einen echten durchgängigen Arbeitsablauf mit wenigen
Werkzeugen in einer Entwicklungsumgebung. Er ist kein produktionsreifer Modus:
Recovery, Kostenabrechnung, eigene Keys, alle Verlaufsszenarien und Qualitäts-
evaluation sind dort noch nicht vollständig abgedeckt.

Die Beta-Spannen ergeben sich aus folgenden Planungsblöcken. Die Blöcke sind
technische Bereiche; größere Blöcke werden in mehrere Codex-Aufträge zerlegt.
Lokale Tests und Korrekturen gehören zum jeweiligen Block, übergreifende
Regressionen zum Integrationsblock.

### Gemeinsamer Kern beider Varianten: 12–24 Codex-Stunden

| Block | Aufwand | Überprüfbares Ergebnis |
| --- | --- | --- |
| Run-/Schrittdaten und API | 2–4 h | Owner-gebundene Aufgaben, eindeutige Schritte, Zustandsübergänge und Statusabruf. |
| Koordinator und Modellaufträge | 2–4 h | Begrenzte Aktionsauswahl, gezielte Teilaufträge, strukturierte Rückgaben und Stop-Regeln. |
| Werkzeuge, Belege und Dateien | 4–7 h | Recherche/Abruf, Upload-Auswertung, definierte Berechnungen, Markdown-/CSV-Ausgaben und geschützte Speicherung. |
| Budgets und Fehlerbehandlung | 2–5 h | Reservierung vor Aufrufen, Abbruch, Wiederaufnahmegrenzen, Own-Key-Verhalten und sichere Fehlerzustände. |
| Prüfung der Lösung | 2–4 h | Prüfung von Aufgabe und Belegen, begrenzte Nacharbeit sowie kleiner realer Evaluationssatz. |

### Integration als zusätzlicher Modus: weitere 6–11 Codex-Stunden

- Composer-Modus, Fortschritt und Ergebnisansicht: 2–4 h.
- Chat-Fortsetzung, Verlauf, Rückfragen und Dateizugriff: 2–3 h.
- Regressionen zwischen Modi, Basisintegration der Ergebnisansicht für gespeicherte
  und geteilte Ergebnisse, Dokumentation, Build und Freischaltung: 2–4 h.

Voraussetzung ist eine bewusst getrennte Ergebnisart. Agentenschritte werden
nicht als fingierte Vergleichsantworten gespeichert; alte Läufe behalten ihre
bisherige Darstellung. Der neue Modus darf bestehende Vergleichsprodukte nutzen,
ohne sie semantisch umzudeuten.

### Integration als Ersatz: weitere 13–26 Codex-Stunden

- Browser-Ausführung und dynamische Fortschrittsanzeige umstellen: 3–6 h.
- Bestehende Chat-/Bookmark-Verträge und Altbestand kompatibel halten: 3–6 h.
- Quellen-, Agreement- und Share-Darstellung nach Ergebnisart trennen: 2–4 h.
- Presets, Mindestmodellzahl, Schalter, Demo und unmittelbar betroffene
  Produkttexte anpassen: 2–4 h.
- Übergreifende Regressionen, Dokumentation, Build und kontrollierter Wechsel:
  3–6 h.

Der Ersatz lässt zunächst Direktvergleich, bisherige öffentliche Ergebnisse
sowie die bestehenden API-/Watch-/Topic-Pipelines bestehen. Sollen auch API,
Watches, Topics, Publisher und die gesamte öffentliche Produktkommunikation auf
die neue Aufgabenlogik wechseln, plane ich weitere 15–30 Codex-Stunden ein.
Auch dieser Zuschlag setzt denselben begrenzten Werkzeugumfang voraus.

## Empfehlung und Unsicherheit

Für die erste belastbare Version den zusätzlichen Modus wählen, den gemeinsamen
Runner aber bereits als möglichen späteren Nachfolger bauen. Ein späterer
Standardwechsel sollte dann weder eine zweite Agentenengine noch eine zweite
Werkzeugimplementierung benötigen. Koexistenz kostet langfristig Wartung;
die Empfehlung betrifft das geringere Einführungsrisiko und die Möglichkeit,
Qualität und Kosten am selben Produkt zu vergleichen.

Das größte Schätzrisiko ist die Zuverlässigkeit der Koordinatorentscheidungen,
nicht das Schreiben eines weiteren Schalters. Weitere Treiber sind echte
Nutzungsdaten des Providers, Dokumentqualität, wiederaufnehmbare Uploads und die
gewünschte Tiefe von Artefakten oder externen Aktionen.

Nach einem 4–8-Stunden-Prototyp mit einem repräsentativen Ablauf würde ich die
Restschätzung anhand der tatsächlichen Toolfehler, Modellentscheidungen und
Integrationsprobleme ersetzen. Geprüfte Beispielaufgaben müssen dabei auch
Abbruch, Budgetende, fehlende Belege und eine notwendige Rückfrage enthalten.

# Agent · Beta

Agent · Beta ist ein eigener Chatmodus für Pro-Nutzer und Admins. Das ausgewählte
Chatmodell beantwortet einfache Fragen direkt und kann bei Abwägungen,
Empfehlungen und plausibel unterschiedlichen Antworten selbst Vergleiche starten.
Eine Nutzerbestätigung ist dafür nicht nötig; Konkretisierungsfragen sind möglich.
Der separate Consensus-Modus behält seinen bisherigen Ablauf und seine Run-Limits.

## Modelle und Bedienung

Der Chatmodell-Picker und die Denkstufe gelten für die nächste Nachricht.
Die Auswahl wird kontogebunden gespeichert und während eines Laufs eingefroren.
GET /agent/models nutzt die Daily-Antwortmodelle plus AGENT_MODEL als Standard;
Preise, Kontextgrenzen und Reasoning-Stufen stammen aus dem bestehenden
app/services/llm/agent_model_catalog.json. IDs, Labels und Routing kommen aus
cfg.MODEL_CONFIGS. Der Default bleibt deepseek/deepseek-v4.1-flash.

Der vorhandene Consensus-Preset-/Model-Picker erscheint daneben als Compare.
Er wählt die Vergleichsmodelle aus derselben Konfiguration; Agent bietet keine
zusätzliche Presetliste und keinen Synthese-/Consensus-Modell-Picker an. Manuelle
Familien-/Modellwahl bleibt möglich. Mindestens zwei Vergleichsmodelle müssen
gewählt sein; ohne übergebene Auswahl gilt das zentrale Standardpreset.

Das Modell kann eine ganze Frage oder bis zu drei begründete Teilfragen
vergleichen. Jede Vergleichsgruppe erhält denselben neutralen Auftrag samt
notwendigem Kontext. Keine Vergleichsantwort beeinflusst die andere. Das
Chatmodell erhält Antworten, Quellen, Status und Modellmetadaten und schreibt
die Synthese selbst. Ein ausdrücklicher Nutzerwunsch nach Vergleich oder Prüfung
ist im Tool-Prompt vorgesehen; bei einer Prüfung wird nötigenfalls erst eine
unabhängige Vergleichsgrundlage eingeholt.

## Antwortversionen und Prüfungen

Nach einem Vergleich ist judge_answer verpflichtend. Das Tool prüft genau den
bereits sichtbaren Synthesetext mit der vorhandenen Differences-/Coverage-Pipeline.
Ein fehlender Toolcall wird einmal eingefordert; danach endet der Lauf mit
fehlender Prüfung. Das Backend lässt keinen stillen ungeprüften Abschluss zu.

Die Anzeige unterscheidet vollständig, teilweise, fehlgeschlagen, fehlend und
abgebrochen. Vollständig bedeutet, dass beide Judges ihre Aufgabe abgeschlossen
haben und die Vergleichsgrundlage vollständig ist. Modellübereinstimmung ist
keine unabhängige Faktenprüfung. Ohne Vergleich läuft keine automatische Prüfung.

Die Prüfung bindet den SHA-256 der Antwort und den Hash der konkret verwendeten
Modellantworten samt Quellen. Nach der Prüfung wird der Text nicht umgeschrieben.
Mit finalize=false kann das Modell einmal überarbeiten; die neue Textversion
muss erneut geprüft werden. Maximal zwei Versionen und 18 Judge-Versuche pro
Nachricht verhindern unbegrenzte Reparaturschleifen. Ankündigungen weiterer
Tool-Aufrufe zählen noch nicht als Syntheseversion. Jeder Teilvergleich behält
seine eigene Prüfung: dieselben Modelle zählen nicht mehrfach als unabhängige
Stimmen. Nicht abgedeckte Aussagen bleiben in der Coverage sichtbar.

Aktivitäten verwenden die bestehende Agent-Seitenleiste mit Status, Usage und
aufklappbaren Details. Oberhalb der Antwort steht ein überlappender Modellstapel
mit den Icons des zentralen Katalogs; wiederholte Aufrufe desselben Modells
belegen einen Platz, bleiben aber einzeln in der Aktivität sichtbar.
Unter der Antwort stehen ein kompakter Prüfstatus und Links zu Widersprüchen,
Einzelantworten und Quellen. Rote Textmarkierungen öffnen unmittelbar die
passende Widerspruchskarte im gemeinsamen Consensus-Antwortleser. Modelllinks
zeigen dort die formatierte Originalantwort. Bei mehreren Teilvergleichen wählt
ein beschriftetes Auswahlfeld die konkrete Markierungsgrundlage. Kontext und
frühere Antwortversionen stehen in den Details des Lesers. Live-Ansicht und
gespeicherter Verlauf verwenden denselben Review-Snapshot.
Die Quellenansicht vereinigt Quellen aus der Chat-Recherche, der jeweiligen
Vergleichsgrundlage und expliziten Links in den Antworten. Sie ist auch ohne
Vergleich verfügbar. Provider-/Suchquellen werden auf dem Turn gespeichert;
alte Turns können sie weiterhin aus ihrem Aktivitätsjournal darstellen.

Der Composer zeigt Chatmodell und Compare-Auswahl. Reasoning ist eine zweite
Ebene im Chatmodellmenü; der während einer Unterhaltung gesperrte Modusschalter
belegt dort keinen Platz. Der Modellstapel verwendet dezente 15-px-Icons.

Die Denkphase zeigt kurze Fortschrittsauszüge: vorhandene Provider-
Zusammenfassungen haben Vorrang, sonst werden vollständige Sätze aus sichtbarem
Reasoning ausgewählt und ausdrücklich als Auszüge bezeichnet. `agent_progress.py`
begrenzt sie auf drei Zeilen mit je 180 Zeichen und acht Updates pro Modellschritt;
es entstehen keine zusätzlichen Modellaufrufe. Der Turn speichert pro Schritt
nur den letzten Kurztext, Worker-Sitzungen nur den aktuellen Fortschritt;
das bestehende Event-Journal enthält die begrenzten Kurztext-Updates. Der
Antwortbereich zeigt während des Laufs kurze, einheitliche Absätze unterhalb
des standardmäßig geschlossenen Thinking-Disclosures, einschließlich aktueller
Tool-Aktivität. Nach Laufende verschwindet diese Vorschau. Nur explizites
Aufklappen zeigt alle verfügbaren Schritt-Zusammenfassungen, Tools und Usage;
es gibt keine automatische Expansion und keine vertikalen Zitatlinien.
Alte, ausführliche
Aktivitäten werden beim Anzeigen ebenfalls gekürzt; bestehende Daten werden
nicht migriert. Private Provider-Fortsetzungsdaten bleiben ausschließlich im
laufenden Protokoll und werden nicht als sichtbare Aktivität gespeichert.

## Tageskontingent

AGENT_DAILY_TOKEN_LIMIT ist zentral über die Umgebung konfigurierbar und beträgt
standardmäßig 250000 Tokens pro UID und UTC-Tag (Reset um 00:00 UTC). Der bestehende
Kontingent-Ring im Sidebar-Footer zeigt im Agent-Chat den verbleibenden Anteil
als abgerundete Prozentzahl. Sein Panel enthält die exakten Tokenzahlen und
Reset-Zeit. Consensus zeigt dort weiterhin das Run-Limit; der Composer enthält
keine Budgetzeile. Das Kontingent gilt gemeinsam für Chat, delegierte Worker,
Vergleichsmodelle und alle Judge-/Repair-/Retry-Aufrufe.

Gezählt wird Provider-Input plus Provider-Output. Cache-Reads/-Writes sind bereits
im Input enthalten, Reasoning bereits im Output. Diese Kategorien werden für
Transparenz gespeichert, aber niemals zusätzlich zum Kontingent addiert.
Provider-Gesamtkosten haben Vorrang; ohne sie berechnet die App eine gekennzeichnete
Katalogschätzung. Die bestehende Kostenkontrolle gilt zusätzlich zur Tokenquote.

Vor jedem bezahlten Schritt reserviert der Server transaktional ein konservatives
Budget zusammen mit dessen dedupliziertem Beleg. Settlement ersetzt es genau
einmal durch gemessene Tokens. Bei fehlender Usage bleibt die Reservierung für
den Tag bestehen und wird als unbekannt gekennzeichnet. Abbrüche und Fehler
schenken keine bereits verbrauchten Tokens zurück. Replays führen keinen neuen
Call aus. Beim UTC-Wechsel zählt ein Call zu seinem Starttag; nur ungenutzte
Synthese-/Judge-Reserven wandern auf den neuen Tag.

Vor einem Vergleich schützt der Server zusätzliche Tokens und Kosten für
Synthese und Judges gegen andere parallele Runs und Worker. Zu wenig verfügbares
Budget kann einen Vergleich ablehnen oder eine Teilgrundlage ergeben; eine
fehlgeschlagene Prüfung wird dabei nie zu einer erfolgreichen umgedeutet.

Technische Standardgrenzen stammen aus der gemeinsamen Delegationskonfiguration:

| Grenze | Standard |
|---|---|
| Bezahlte Provider-Aufrufe | 32 pro Nachricht, alle Rollen zusammen |
| Tool-Aufrufe | 48 |
| Laufzeit | 300 Sekunden |
| Zusätzliche Kostenreserve | 3 USD pro Nachricht |
| Parallele Unteraufrufe | 2 |
| Antwortmodelle pro Vergleich | vorhandene Auswahl, mindestens 2 |
| Vergleichsantwort | 2048 Output-Tokens, maximal 6000 Zeichen |
| Synthese | AGENT_MAX_OUTPUT_TOKENS, standardmäßig 4096 |
| Kontext | 120000 Zeichen plus Modellfensterprüfung |
| Review-Snapshot | maximal 600 kB |
| Gleichzeitige Runs je UID | 2 |
| Produzenten pro Prozess | AGENT_MAX_CONCURRENT_RUNS, standardmäßig 16 |

Reservierungen sind Zulassungskontrollen, keine Garantie für die tatsächliche
Provider-Rechnung. Meldet der Provider höheren Verbrauch, wird er vollständig
verbucht und weiterer Verbrauch blockiert. Unbekannte Nutzung ist kein Nullwert.

## Recherche, Delegation und Providerprotokoll

Recherche nutzt den vorhandenen OpenRouter-Websuch-Builder. Agent begrenzt ihn
auf Exa mit drei Treffern à maximal 1000 Zeichen pro Suche; maximal eine Suche
pro Modellrequest aus dem gemeinsamen Suchbudget. Damit kann das Tageskontingent
begrenzt reservieren, ohne komplette native Modellfenster zu blockieren. Kein
neuer Suchdienst und kein zusätzliches Suchmodell. Consensus bleibt bei seiner
bisherigen Suchkonfiguration. Nur tatsächliche Quellenannotationen oder gemeldete
Suchzähler erzeugen eine Suchaktivität; Startzeiten/Queries werden nicht erfunden.
Vergleichsmodelle recherchieren nicht selbst, sondern nutzen den vom Chatmodell
bereitgestellten Kontext und Quellen. Sie sehen keine anderen Vergleichsantworten.

Worker-Delegation bleibt standardmäßig deaktiviert und verwendet weiter die
geprüften Modell-/Reasoning-Kombinationen und die bestehende Admin-Konfiguration;
siehe [agent-delegation.md](agent-delegation.md). Vergleichstools sind davon
unabhängig. Der gemeinsame Tool-Loop erhält die kompletten Provider-Fortsetzungs-
informationen intern; verschlüsselte Reasoning-Blöcke werden nie öffentlich oder
persistiert. Sichtbares Reasoning bleibt auf 32000 Zeichen begrenzt.

Systemprompt, frisches Datum/Zeitzone, ausgewählte Modellidentität und
abgeschlossene Unterhaltung werden vom Server zusammengestellt. Toolargumente,
Antworten und Quellen sind untrusted data, keine Berechtigungen. Strikte Schemas,
servereigene Modellauflösung und Limits verhindern eine Änderung der Policy
über Toolergebnisse. Dateien, Share und Watch sind weiterhin nicht freigeschaltet.

## Persistenz, Stop und Recovery

AgentRunStore hält einen atomaren Beleg je completion:N oder agent:<uuid>:N unter
users/{uid}/llm_calls. Der erste Beleg bindet Producer-Token, Lease, Policy,
Schrittzustände und Eventsequenz. Verbrauch bleibt bei einer Chat-Löschung
bestehen; Account-Tombstones verhindern verspätete Writes nach Kontolöschung.

Abbruch schließt Provider und wartet auf die aktiven Tool-/Judge-Threads. Ein
Prozessabsturz erlaubt kein erneutes Ausführen bereits beanspruchter Schritte;
abgelaufene Leases werden in terminale unbekannte Belege überführt. Gespeicherte
Vergleichsantworten mit abgebrochener Prüfung bleiben im Agent-Verlauf sichtbar.
Recover saved answer lädt ausschließlich den existierenden Snapshot. Auch eine
fehlgeschlagene Antwort kann so mit ihrem tatsächlichen Prüfstatus gelesen werden.
Ein neuer Versuch ist eine neue Nachricht mit neuem Budget, kein versteckter Retry.

## Validierung

- Backend: tests/test_agent_comparison.py sowie bestehende Agent-, Delegation-,
  Budget-, Chat-, Bookmark- und Consensus-Judge-Tests.
- Browser-State: tests/js/agent-review.test.mjs und bestehende Agent-Tests.
- Oberfläche: tests/e2e/test_agent_comparison_frontend.py mit gemockten Providern,
  Desktop, 390/320 Pixel, Hell/Dunkel, Tastatur und gespeicherter Ansicht.
- Transaktionen im Firestore-Emulator: tests/e2e/test_agent_transactions.py.

Befehle, isolierte Testumgebung und Build-Vertrag stehen in [testing.md](testing.md).
Die deterministischen Tests ersetzen keine kostenpflichtigen Providerprobes für
jede Modell-/Reasoning-Kombination; deren frühere Ergebnisse bleiben unter artifacts/.

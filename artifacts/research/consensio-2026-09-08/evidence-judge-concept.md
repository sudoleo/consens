# Dritter Judge für Quellenprüfung

## Entscheidung

Die erste Version prüft, ob zitierte Originalquellen wichtige Aussagen der fertigen Consensus-Antwort tragen. Sie ergänzt die Modellanalyse um einen separaten Quellenstatus. Sie verändert weder den Agreement-Score noch nachträglich den bereits finalisierten Antworttext. Zusätzliche Recherche und automatische Antwortrevision sind spätere Erweiterungen.

Dies ist ein Architekturvorschlag vom 9. September 2026, keine implementierte Funktion. Grundlage sind die bestehenden Quellenparser, `consensus_pipeline.py`, der Satzindex in `consensus_engine.py`, die Snapshot-Projektion und der Streaming-Vertrag.

## Ablauf

1. **Originalquellen bereitstellen.** Ein Backend-Service sammelt die URLs aus dem konkreten Lauf und lädt geeignete öffentliche Dokumente. Identische Abrufe werden zusammengelegt. URL-Zitate und vorhandene Provider-Snippets sind Suchhinweise; das stärkere Prüfprädikat setzt vom Server abgerufenen Inhalt voraus. Originalinhalt, Abrufdatum, Inhalts- und Extraktorversion werden miteinander verbunden. Bereits während der Antwortgenerierung verfügbare Quellen können vorgeladen werden, sofern Budget und Zugriffsprüfung dies erlauben.
2. **Aussagen auswählen.** Nach der Synthese liefert der bestehende Satzindex die verankerbaren Sätze. Ein kleiner strukturierter Planungscall wählt höchstens fünf entscheidende faktische Claims einschließlich ihrer Satz-IDs und vorhandenen Quellen-IDs. Auch einstimmige Aussagen kommen infrage. Gemischte Sätze werden in Teilbehauptungen mit erhaltener Einschränkung zerlegt. Empfehlungen, Geschmack und kreative Formulierungen erhalten keine vorgetäuschte Faktenbewertung.
3. **Passagen finden.** Der Server sucht im extrahierten Dokument nach passenden Abschnitten und übergibt begrenzte Ausschnitte mit Überschrift und Nachbarkontext. Eine nicht gefundene Passage führt zu einem offenen Befund. Ein begrenzter zweiter Abschnitt kann im selben Tokenbudget berücksichtigt werden. Der erste Modus umfasst öffentliche HTML-Texte und textbasierte PDFs; nicht lesbare oder aufwendig dynamische Dokumente werden ausdrücklich als nicht geprüft geführt.
4. **Quellen-Judge ausführen.** Ein gemeinsamer strukturierter Call bewertet die ausgewählten Claims und ihre Passagen. Er sieht keine Modellnamen oder Zustimmungszählung. Seine Aufgabe ist Quellenstützung, nicht freie Beantwortung aus Trainingswissen. Geprüft werden Aussage, Einschränkungen, Zeitpunkt, Version, Zahlen/Einheiten und unmittelbarer Beleg gegenüber Schlussfolgerung. Anweisungen in Dokumenten bleiben untrusted data.
5. **Ergebnis technisch prüfen.** Claim-/Dokument-IDs müssen existieren. Ausgegebene Zitate müssen in der bezeichneten Dokumentversion vorkommen. Fehlende Claims werden als unvollständig ausgewiesen. Bei Schemafehlern ist maximal ein weiterer Call innerhalb desselben Gesamtbudgets zulässig. Ein auffindbares Zitat allein genügt nicht für semantische Korrektheit; dafür bleibt die fachliche Bewertung verantwortlich.
6. **Separat anzeigen und speichern.** Pro geprüfter Aussage erscheinen Status, Begründung, Originalpassage und Quelle. Nicht gewählte Aussagen bleiben ungeprüft. Die UI zeigt beispielsweise „5 von 18 faktischen Aussagen geprüft“. Die Quellenauswertung wird unveränderlich an Run und Antwortrevision gebunden.

## Vertrag für den Judge

Eingabe pro Claim: `claim_id`, `sentence_id`, exakter Claimtext, Geltungsbereich, Bewertungszeitpunkt und Kandidatenpassagen mit `document_version_id`, `passage_id`, Wortlaut und Kontext.

Ausgabe pro Claim:

```json
{
  "claim_id": "c3",
  "status": "partial",
  "evidence": [{"document_version_id": "d7-v2", "passage_id": "p4", "quote": "Available in preview for enterprise customers."}],
  "reason": "Die Quelle bestätigt die Funktion nur als Enterprise-Preview.",
  "missing_qualifier": "Preview; nur Enterprise-Kunden"
}
```

Erlaubte Statuswerte: `supported`, `partial`, `contradicted`, `conflicting`, `insufficient`. Abruffehler und nicht ausgeführte Prüfungen sind separate technische Zustände. Ein fehlender Beleg bedeutet nicht, dass eine Aussage falsch ist. Auch `supported` bedeutet ausdrücklich „durch die geprüfte Passage gestützt“, keine allgemeine Wahrheitsgarantie.

Herstellerdokumentation kann eine dokumentierte Eigenschaft belegen; eine Herstellerbehauptung über Marktführerschaft benötigt andere Evidenz. Mehrere Quellen werden nicht durch bloßes Zählen stärker. In Version 1 werden exakte Duplikate erkannt, andere Herkunftsbeziehungen als unbekannt behandelt; eine verlässliche Erkennung sämtlicher Abschreibketten wird nicht versprochen.

## Integration in consens.io

Ein neues `evidence_verification`-Servicepaket trennt sicheren Abruf, Textaufbereitung, Judge und Job-/Ergebnisspeicherung. Ein gemeinsamer Einstieg akzeptiert eine serverseitig gebundene Antwortrevision und Quellreferenzen. Topics, Watches, API und Browser benutzen dieselbe Bewertungslogik. Die Browser-SSE-Route benötigt einen eigenen Adapter, weil sie nicht vollständig durch den synchronen Pipelinepfad läuft.

Der Job startet, sobald die Ausgangsantwort serverseitig persistiert ist. Die Antwort bleibt sofort lesbar; Quellenprüfung erscheint zunächst als „läuft“. Ein additiver ownergeschützter Status-/Resultatabruf verbindet das nachgelieferte Ergebnis mit der richtigen Antwort. Im ersten Pilot ist begrenztes Polling ausreichend; globale oder endlose Poll-Schleifen werden vermieden. Bereits vorhandenes `consensus.final` bleibt der Abschluss genau dieser Antwortrevision.

Das bestehende Differences-JSON wird nicht mit einem zweiten Agreement-Wert überladen. Ein eigenes `source_verification`-Objekt referenziert den Prüfjob, die Antwortrevision, Abdeckung und Claim-Ergebnisse. Chat-/Share-Allowlists müssen kompakte neue Referenzen explizit erlauben; öffentliche Shares dürfen ausschließlich die zum veröffentlichten Snapshot gehörende Prüfung zeigen. Private Belege werden nicht durch öffentliche Resultate erreichbar.

Spätere Korrekturen erzeugen eine sichtbare neue Antwortrevision und erneuern deren Coverage/Differences, da alte Satzanker und Urteile sonst nicht mehr passen. Sie dürfen eine bereits kopierte oder geteilte Antwort nicht lautlos umschreiben.

## Skalierung und Budgets

- **Kleiner Normalfall:** ein Planungscall plus ein Judge-Call für höchstens fünf Claims; keine eigene LLM-Anfrage je Modell, Quelle und Satz. Ein kompletter Cachetreffer kann Arbeit weiter reduzieren.
- **Startlimits:** höchstens acht Dokumente, begrenzte Dokumentgrößen, ungefähr 12.000 Input-Tokens für die gebündelte Prüfung und eine Job-Deadline von 45 Sekunden. Diese Werte sind Pilotannahmen, keine garantierten Latenzen. Offene Arbeit bleibt sichtbar offen.
- **Zweistufiger Cache:** Dokumentcache nach kanonischer URL, Zugriffskontext und Version; Urteilscache nach exaktem Claim einschließlich Scope/Zeit, Passage-/Dokumenthash und Modell-/Prompt-/Policyversion. Semantisch ähnliche Texte teilen zunächst keine Urteile automatisch. Ein Inhaltscache benötigt zuerst einen frischen Abruf oder einen noch gültigen Frischezustand.
- **Singleflight und Backpressure:** Gleichzeitige identische Dokumentabrufe werden zusammengelegt. Dokument-/LLM-Parallelität, Queuegröße und Budgets sind begrenzt. Bei voller Queue wird die Quellenprüfung ehrlich verschoben oder als nicht durchgeführt angezeigt; keine zusätzlichen unbeschränkten Threads pro Request.
- **Persistente Jobs:** deduplizierter Schlüssel aus Owner, Ausgangsrevision und Policy; Leases, Wiederverwendung abgeschlossener Stufen und Schutz vor doppelter Veröffentlichung. Unklare externe Call-Ausgänge werden nicht blind als garantiert kostenlose Retries behandelt.
- **Worker separat betreibbar:** Der gemeinsame Service kann für den Pilot mit begrenzter Hintergrundausführung beginnen. Für mehr Last konsumieren separate Worker persistente Jobs; horizontale Skalierung respektiert globale Kosten- und Providerlimits.
- **Watches:** Unveränderte Versionen können vorhandene Bewertungen wiederverwenden. Abruffristen richten sich nach Aktualität; ein unveränderter bekannter Quellenbestand beweist nicht, dass keine neuen Quellen existieren. Eine spätere Research-Version ergänzt deshalb periodische Entdeckung neuer Belege.

Kosten wachsen damit hauptsächlich mit einzigartigen neuen Quellen und Prüfungen. Bei lauter neuen Fragen gibt es wenig Cachegewinn: Dann begrenzen Claim-Auswahl und Jobbudgets den Aufwand. Ein pauschaler Kostenvorteil ist ohne Nutzungsdaten nicht belegbar.

Der Abrufservice prüft interne/private Zieladressen einschließlich DNS und Redirects, begrenzt Formate/Größen und führt Dokumentinhalt nicht als Code aus. Caches privater Inhalte bleiben ownergebunden; private URLs werden nicht global indiziert. Neue Writes und Artefakte folgen Account-Löschbarrieren, Retention und Löschkaskaden. Provider-Tokens/Kosten werden als Metadaten erfasst, keine Inhalte in Betriebslogs.

## Pilot und Erfolgskriterium

Start auf ausgewählten öffentlichen Topics, anschließend optional in der App. Ein erstes gelabeltes Set enthält korrekt belegte Aussagen, fehlende Einschränkungen, falsche Zitate, widersprüchliche Quellen und Abruffehler. Ein separater gesperrter Test prüft Präzision der Bestätigungen, erkannte Belegfehler, ungeprüften Anteil, Kosten und p95-Latenz.

Der konkrete erste Nutzen lautet: **Nutzer erkennen, welche wichtigen Aussagen durch ihre Quellen gedeckt sind und wo Einschränkungen fehlen.** Version 1 stellt keine Vollrecherche dar und korrigiert Antworten noch nicht automatisch. Erst wenn die Quellenurteile verlässlich sind, folgen gezielte Nachrecherche, korrigierte Antwortrevisionen und evidenzbezogene Watch-Alarme.

# Folgeaudit: von vorhandenen Tests zu belegter Abdeckung

[Zum Katalog](../test-coverage-map.md). Dieser Ablauf gehört zum nächsten
Auftrag; die Bestandsaufnahme selbst implementiert keine fehlenden Tests.

## 1. Ausgangsstand verifizieren

`check_inventory.py` ausführen, geänderte Test-/Produktdateien identifizieren und
betroffene Einträge erneut lesen. Aktuellen Runnerbestand sammeln. Die vier
Befunde aus [findings.md](findings.md) sowie Windows- und Browserausführung
klären. Ein bekannter roter oder nicht ausgeführter Test darf nicht als grüner
Nachweis in eine Bewertung eingehen.

## 2. Vom Produkt zum Test prüfen

Aus `docs/codebase-map.md`, den tatsächlichen Routern/Services, Frontendmodulen,
Jobs, Datenmodellen und vorhandenen Produktanforderungen eine Liste erwarteter
Verhaltensverträge erstellen. Jeden Vertrag unabhängig von vorhandenen
Testnamen formulieren: Eingabe/Voraussetzung, erwartetes Ergebnis, relevante
Zustandsänderungen und verbotene Nebenwirkungen.

Anschließend über [areas.md](areas.md) und das JSON geeignete Tests finden und
deren Assertions lesen. Auch Produktionsmodule ohne direkten Testverweis und
Codepfade hinter Mocks prüfen. Der Testkatalog allein kann vollständig
ungetestete Funktionen nicht entdecken.

Für jeden Vertrag einen prüfbaren Datensatz führen:

| Feld | Erforderlicher Inhalt |
|---|---|
| ID und Bereich | Stabiler Bezeichner, z. B. `AGENT-RECOVERY-01` |
| Erwartung | Produktanforderung oder ausdrücklich begründete Invariante |
| Produktionspfad | Module, Funktionen, Endpoints und Datenübergänge |
| Belege | Testdatei, konkrete Testdefinition, relevante Assertion |
| Ebene und Grenze | Was tatsächlich läuft; was durch ein Double ersetzt ist |
| Zustand | Belegt / teilweise belegt / Test fehlschlägt / Ausführung offen / kein Beleg gefunden / Produktentscheidung offen |
| Gegenbeispiel | Konkreter Fehler oder Eingabefall, der von den vorhandenen Assertions unbemerkt bliebe |
| Nächster Schritt | Passende Testebene, erwartetes Ergebnis und Validierung |

„Kein Beleg gefunden“ erst nach dem Abgleich aller relevanten Dateien verwenden.
Keine Lücke aus dem Fehlen eines Tests in einer einzelnen Datei ableiten.

## 3. Wirksamkeit statt Menge bewerten

Pro Vertrag prüfen:

- Prüfen Assertions den fachlichen Output und die Nebenwirkungen oder nur
  HTTPstatus, Mockaufruf, Stringvorkommen bzw. einen Snapshot?
- Könnte die Implementierung falsch sein und der Test dennoch grün bleiben?
  Bei kritischen Invarianten gezielte Mutationen einsetzen: beispielsweise
  Ownerprüfung entfernen, Idempotenzschlüssel ignorieren oder Revision vertauschen.
- Decken Fixtures gültige reale Formen ab? Prüfen sie fehlende/ungültige Daten,
  Grenzen, Fehler, Teilerfolge und Rückwärtskompatibilität?
- Sind Abbruch, Wiederholung, verspätete Antworten, konkurrierende Writes,
  Konten-/Turnwechsel sowie Budget-/Tageswechsel passend zum Produkt abgesichert?
- Stimmen Fake und realer Adapter im benötigten Vertrag überein? Wird der
  entscheidende Sicherheits-/Transaktionsschritt eventuell weggemockt?
- Sind Zeit, Zufall, Umgebung, Reihenfolge und gemeinsame Zustände kontrolliert?
  Wiederholungen gezielt zur Klärung beobachteter Instabilität einsetzen.
- Gibt es redundant gleiche Prüfungen, während ein anderer Vertrag fehlt?
  Parametrisierungen nach ihrem zusätzlichen Aussagewert beurteilen.

Für fachliche Modellqualität gelten andere Kriterien als für Parser und
Orchestrierung: repräsentative Aufgaben, unabhängige Erwartungskriterien,
begründete Referenzen und Auswertung von Fehlerarten. Deterministische
Provider-Doubles können diesen Qualitätsnachweis nicht liefern.

## 4. Messung ergänzen

Python- und JavaScript-Zeilen-/Branch-Coverage mit den für das Repository
passenden Werkzeugen getrennt erheben. Browser-/Backendmessung und Testsuiten
nicht zu einer bedeutungslosen gemeinsamen Prozentzahl vermischen. Nicht
erreichter Code, nie genommene Zweige und produktive Dateien außerhalb der
Messkonfiguration sind Kandidaten für Gegenprüfung.

Ein hoher Prozentwert ersetzt keine starken Assertions; ein niedriger Wert
belegt allein noch keine relevante Produktlücke. Mutationsergebnisse getrennt
mit äquivalenten, nicht ausführbaren oder unklaren Mutationen dokumentieren.

## 5. Fehlende Tests implementieren

Mit besonders folgenreichen Verträgen beginnen: Kontentrennung und
Berechtigungen, Abrechnung, Exactly-once-/Idempotenzverhalten, Datenverlust,
Persistenz/Recovery und zentrale Nutzerabläufe. Das dient der sachlichen
Reihenfolge, nicht der Beschränkung des Gesamtumfangs.

Für jede belegte Lücke die kleinste ausreichende Testebene wählen. Einen
kritischen Ablauf zusätzlich über seine relevanten Integrationsgrenzen prüfen.
Test nach Möglichkeit gegen einen gezielt eingebauten oder reproduzierten
Fehler scheitern lassen und danach die korrekte Implementierung bestätigen.
Produktverhalten nicht aus der aktuellen Implementierung als Soll kopieren.

Bei unklarer Produktanforderung zuerst Erwartung klären; weder Test noch
Produktcode still auf ein geratenes Verhalten festlegen. Gefundene reale
Produktfehler von veralteten Tests und Umgebungsproblemen unterscheiden.

Nach jeder Änderung die betroffenen Einträge und Vertragsbelege aktualisieren.
Zum Abschluss die erforderlichen Gesamtläufe mit dokumentierter Umgebung
ausführen und offene Fälle explizit ausweisen. Ein sinnvoller Abschluss ist
ein nachvollziehbarer Beleg für jeden vereinbarten Vertrag; nicht eine bestimmte
Testanzahl oder pauschal „100 % Coverage“.

## Wiederverwendbarer Auftrag an Codex

> Lies `docs/test-coverage-map.md`, `docs/test-coverage/findings.md` und die
> relevanten Einträge in `inventory.json`. Verifiziere ihre Aktualität. Prüfe
> für den vereinbarten Produktbereich zuerst Anforderungen und Produktionscode,
> dann sämtliche passenden Tests einschließlich Fixtures, Mocks und Assertions.
> Erstelle pro Verhaltensvertrag belegbare Zuordnungen und konkrete
> Gegenbeispiele für tatsächliche Lücken. Unterscheide fehlende Tests,
> unwirksame Assertions, fehlschlagende/veraltete Tests, nicht ausgeführte Fälle
> und ungeklärte Produktentscheidungen. Implementiere anschließend die
> autorisierten fehlenden Tests und notwendigen Fehlerkorrekturen; aktualisiere
> Katalog und Laufnachweise. Behaupte keine Abdeckung allein aus Testnamen,
> Imports, Mockaufrufen oder Prozentwerten.

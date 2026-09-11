# Machbarkeit besserer Quellenzuordnung

Stand: 10. September 2026. Analyse des lokalen Codes, keine Produktionsmessung und keine Änderung des Produktverhaltens.

**Urteil:** Originalpassagen vor der Synthese bereitzustellen ist technisch machbar und als begrenzter Versuch sinnvoll. Automatische inhaltliche Korrekturen nach Abschluss sind ein eigener Architekturumbau. Die erste Empfehlung, problematische Verweise einfach zu entfernen oder Aussagen automatisch zu korrigieren, war zu pauschal.

## 1. Verifizierter Istzustand

- `app/services/llm/citations.py::_ensure_source` reduziert Provider-Seitentext auf einen ungefähr 300 Zeichen langen Teaser. `snippet` und `extract` enthalten denselben gekürzten Text. Der volle Belegtext steht danach in dieser Struktur nicht mehr zur Verfügung.
- `app/services/llm/consensus_engine.py::_format_sources_for_prompt` übergibt höchstens fünf Quellen je Modell, jeweils ID, Titel und URL. Selbst die Teaser gelangen nicht in diesen Promptteil. Die Modellantwort selbst kann natürlich Zitate enthalten.
- `app/services/source_catalog.py` vereinheitlicht Quellenidentitäten. Das hilft gegen ID-Verwechslungen, beweist aber keine semantische Belegwirkung.
- `source_documents.py` bietet bereits sicheren Abruf, Dokumentextraktion, Auswahl von Originalpassagen, lokalen Cache und Singleflight. Die Auswahl basiert auf Wortüberlappung mit Frage/Aussagen und Nachbarkontext; sie ist keine garantierte semantische Suche. PDF, JavaScript-Inhalte und Zugriffssperren begrenzen die Abdeckung.
- `source_verification.py` prüft zitierte ganze Sätze je Quelle separat. Default: eine URL je Paket, durch 3.000 Ausgabetokens effektiv höchstens zehn Paare je Paket; lange Eingaben können kleinere Pakete erzeugen.
- Quellenjobs laufen dauerhaft im Hintergrund. Vier Worker je Prozess bearbeiten verschiedene Aufträge; die Pakete eines Jobs laufen aufgrund des Job-Lease und `completed_packages` nacheinander. Die zusätzliche Owner-Sperre gilt nur pro Prozess.
- In `chat.py` wird der Antworttext vor Abschluss der Quellenprüfung gestreamt. `ChatStore.complete_turn` verweigert eine zweite Completion mit verändertem Inhalt. Prüfungen besitzen einen Hash der Antwortversion; Share-, Bookmark-, Watch- und Kontextdaten hängen ebenfalls an konkreten Ergebnissen.

## 2. Konzeptionelle Grenzen

**Eine Quelle ist nicht automatisch die Wahrheit.** Originalpassagen verbessern Nachvollziehbarkeit; sie ersetzen keine Bewertung von Aktualität, Autorität, Widersprüchen und Bedingungen. Eine Einzelquelle darf nicht automatisch die Synthese mehrerer Positionen überschreiben.

**Ein Satz kann mehrere Aussagen und Belege enthalten.** Beispiel: „Das Paket kostet 20 Euro und läuft zwölf Monate.[S1][S2]“. Belegt S1 den Preis und S2 die Laufzeit, kann die Kombination vollständig sein, obwohl jede Einzelprüfung nur `partial` ergibt. Vor automatischer Reparatur braucht es atomare Teilclaims mit Belegzuordnung oder eine Bewertung der gemeinsam zitierten Quellen. Ein solches Gegenbeispiel erklärt eine mögliche Fehlerklasse, nicht deren Häufigkeit in Produktion.

**Unknown und unavailable sind keine Widerlegung.** Fehlende Datierung, zu kleine Auszüge, gesperrte Seiten und Extraktionsfehler dürfen keine automatische inhaltliche Änderung auslösen. Auch ein `contradicted`-Urteil verlangt eine Prüfung von Geltungsbereich und Gegenbelegen.

**Verweise löschen kann nur die Messung verbessern.** Der aktuelle Checker betrachtet ausschließlich zitierte Sätze. Entfernt man alle S-Tags, verschwinden die Paare aus dem Prüfplan. Deshalb muss eine Evaluation zusätzlich messen, wie viele belegpflichtige Aussagen überhaupt belegt werden. Ein entfernter Verweis ist noch keine behobene Aussage.

**Freie Synthese bleibt nötig.** Schlussfolgerungen, Empfehlungen, kreative Aufgaben und Nutzerdaten benötigen nicht pauschal einen Webbeleg. Belegpassagen sollten Fakten und Zuschreibungen absichern, ohne jeden Satz in ein Quellenzitat zu verwandeln.

## 3. Sinnvoller technischer Entwurf

### Stufe A: Belege vor der Synthese

1. Nach Vereinheitlichung der Quellen-IDs einen serverseitigen Belegspeicher aufbauen: Quellen-ID, kanonische URL, Dokumenthash, Abruf-/Datumsherkunft, Originalpassage mit Position und zugehöriger Ausgangsaussage. UI-Teaser bleiben separat.
2. Zunächst den bestehenden sicheren Abruf und die Passageauswahl wiederverwenden. Provider-Auszüge können zusätzliche Hinweise liefern, sind aber kein serverseitig validierter Dokumentinhalt. Im Browserpfad übermittelte Texte dürfen nicht als vertrauenswürdige Abrufnachweise gelten.
3. Vor der Synthese nach Relevanz, zentralen Fakten und unterschiedlichen Modellpositionen auswählen. Feste Gesamtbudgets für Zeit, URLs und Promptzeichen einführen; die erste-Fünf-Auswahl pro Modell durch eine begründete Auswahl ersetzen. Nicht geladene Quellen sichtbar als nicht angereichert behandeln.
4. Die Synthese erhält einen deduplizierten Belegkatalog und explizite Bindungen an Aussagen. Zahlen, Einheiten, Zielgruppen und Zeiträume müssen beim Umformulieren erhalten bleiben; inferierte Schlussfolgerungen bleiben als solche erkennbar.
5. Der anschließende Checker bewertet den tatsächlich formulierten Text weiter unabhängig. Für denselben Run sollte er möglichst dieselbe Dokumentversion verwenden; sonst können zwischenzeitliche Seitenänderungen künstliche Abweichungen erzeugen.

Ein zusätzlicher generativer Modellaufruf ist für diese erste Stufe nicht zwingend nötig. Abruf, Auswahl und ein größerer Syntheseprompt verursachen trotzdem Kosten und Latenz. Die vorhandene lexikalische Passageauswahl ist ein sinnvoller Ausgangspunkt; ihre Trefferqualität muss insbesondere bei anderssprachigen Quellen und Paraphrasen geprüft werden.

Der gemeinsame Vorbereitungsdienst muss Browser-Streaming und JSON sowie API-, Watch- und Topic-Runs erreichen. Eine Änderung nur in `consensus_pipeline.py` reicht wegen des separaten Browser-Streamingpfads nicht. Das Verhalten bei deaktiviertem „Check Sources“ muss bewusst festgelegt werden: neue Abrufarbeit nicht stillschweigend unter einer abgeschalteten Option ausführen.

### Stufe B: Korrektur erst nach belegtem Nutzen

Für den Standardlauf vorerst keine automatische nachträgliche Textänderung. Einen möglichen späteren Prüfmodus vor der endgültigen Speicherung ausführen: Entwurf → Quellenprüfung → höchstens ein gezielter Reparaturdurchgang → erneute Prüfung der betroffenen Aussagen → Coverage/Differences auf dem endgültigen Text → Speicherung.

Bei inhaltlichen Änderungen reichen alte Claims, Satzpositionen, Agreement und Prüfungen nicht weiter. Auch reine Quellenänderungen verändern aktuell den Antwortversionshash und benötigen neue Bindungen; inhaltliche Judges ließen sich nur bei nachgewiesen unverändertem Wortlaut wiederverwenden. Bereits publizierte oder als Folgekontext verwendete Ergebnisse dürfen nicht still überschrieben werden. Nachträgliche Korrekturen benötigen eine ausdrückliche neue Antwortrevision mit konsistenten abhängigen Daten.

Eine blockierende Endprüfung erhöht die Wartezeit. Alternativ braucht die Oberfläche einen klar vorläufigen Entwurf und ein separates finales Ergebnis. Beides ist eine Produktentscheidung und kein kleiner Prompt-Fix. Ein erschöpftes Budget muss einen ehrlichen unverifizierten Zustand liefern, keine endlose Reparaturschleife.

## 4. Skalierung und Wirtschaftlichkeit

Die bestehende Queue mit Leases, Wiederaufnahme, Caches und Paketgrenzen ist eine brauchbare Grundlage. Sie begrenzt gleichzeitig aktive Arbeit, aber nicht automatisch die gesamte Arbeit oder Kosten eines Runs. Ein Vorabruf kann mehr URLs bearbeiten als der heutige Check, der nur die final zitierten Quellen lädt.

Erforderlich sind daher Gesamtbudgets pro Run und Nutzer, begrenzte Abrufparallelität, eine Gesamtfrist für die Vorbereitungsphase sowie kontrollierte Überlastbehandlung. Angenommene Prüfpaare dürfen bei Überlast nicht still verschwinden. Bei größerem Verkehr sollten Quellenworker unabhängig vom Webserver skalieren können. Own-Key-Aufträge und globale Nutzerfairness brauchen dabei ihre bisherigen beziehungsweise ausdrücklich erweiterten Bindungen.

**Kapazitätsmodell, keine Messung:** Bei `P` Paketen pro Run und durchschnittlich `t` Sekunden pro Paket brauchen die vier Worker ungefähr `P × t` Worker-Sekunden pro Run. Die idealisierte Kapazitätsgrenze eines Prozesses ist `240 / (P × t)` Runs pro Minute. Bei angenommenen acht Paketen und zehn Sekunden wären das drei Runs pro Minute, noch ohne Speicherzugriffe, Warteschlange und Reserven. Ein einzelner Job benötigt wegen seiner seriellen Pakete ungefähr 80 Sekunden. Die konfigurierte 60-Sekunden-Paketfrist ist weder eine typische Laufzeit noch eine Gesamtfrist für den Job.

Zusatzkosten entstehen aus mehr Synthese-Eingabetokens, Abruf-/Speicherarbeit und gegebenenfalls Reparatur, erneuter Belegprüfung und neuen Judges. Dokumentcaches können viel wiederverwenden; der Judge-Cache bindet jedoch Frage, Text, Datum, Modell und Prompt. Geänderte Texte erzeugen deshalb nicht automatisch Cachetreffer. Eurobeträge oder ein tragbares Produktionsvolumen lassen sich ohne reale Token-, Latenz- und Trefferverteilungen nicht seriös nennen.

## 5. Nachweis vor einer Einführung

Ein begrenzter Vergleich auf beispielsweise 50–100 realistischen, datensparsam zusammengestellten Fragen sollte aktuelle Synthese, Synthese mit Originalpassagen und eine Variante mit einmaliger Reparatur bei gleichem Ausgangsmaterial vergleichen. Umfang und Freigabeschwellen sind Vorschläge, keine bereits erfüllten Kriterien.

Messen: korrekte Quellenzuordnungen, Abdeckung belegpflichtiger Aussagen, Erhalt von Bedingungen/Zahlen, unbegründete Reparaturen, Qualität und Lesbarkeit der Gesamtantwort, Quote nicht prüfbarer Fälle, Zeit bis Ersttext und Finale, p50/p95-Latenz sowie Kosten je Run. Eine manuell bewertete Stichprobe verhindert, dass Generator und Checker ihre gemeinsamen Fehler gegenseitig bestätigen. Abgerufene Dokumentversionen müssen für den Vergleich identisch sein; zusätzliche Suche wäre eine getrennte Variable.

Die Forschung zeigt die grundsätzliche Machbarkeit von Recherche plus gezielter Revision: [RARR](https://aclanthology.org/2023.acl-long.910/). Sie beweist nicht die Wirksamkeit im aktuellen Produkt. Für die getrennte Bewertung von Antwort- und Zitationsqualität ist [ALCE](https://aclanthology.org/2023.emnlp-main.398/) eine passende methodische Referenz.

## 6. Durchgeführte Prüfung

- Quellcodeanalyse von Citation-Normalisierung, Promptbau, Dokumentabruf, Prüfpaketen, Worker-/Repository-Verhalten, Streaming und Chat-Completion.
- Deterministische Probe am aktuellen Code: Teaser fehlt im Synthese-Quellenblock; S7 fehlt bei sieben Quellen; längerer Provider-Auszug bleibt als 300-Zeichen-Teaser; ein Satz mit zwei Quellen erzeugt zwei Pakete mit demselben vollständigen Satz; nach Entfernen der Verweise verbleiben null Prüfpaare.
- Zusätzlich ausgeführt: `python -m pytest tests/test_source_check_jobs.py tests/test_source_check_repository.py tests/test_consensus_chat_history.py -q`: **96 bestanden**. Die vorherige Analyse hatte bereits 160 Tests für Engine, Katalog und Quellenprüfung bestanden.
- Kein produktiver Modellvergleich, kein Lasttest und keine gemessene Qualitätssteigerung. Produktcode unverändert.

**Entscheidung:** Begrenzter Versuch mit Originalpassagen ist sinnvoll. Automatische Korrektur bleibt eine spätere, gesondert zu validierende Funktion mit finaler Antwortversion, vollständiger Nachbewertung und Kostenlimit.

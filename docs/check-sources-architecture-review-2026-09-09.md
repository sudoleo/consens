**Check Sources im Verbund mit der Consensus Engine — Architektur- und Produktreview**

Stand: 9. September 2026. Bewertet ist der aktuelle lokale Arbeitsbaum einschließlich seiner bereits vorhandenen, noch nicht committeten Änderungen. Die Analyse ist kein Nachweis des Produktionsstands. Produktcode wurde für dieses Review nicht geändert.

**Gesamturteil:** Die technische Grundlage ist gut begrenzt und sinnvoll vom Consensus getrennt. Der gegenwärtige Nutzen ist jedoch enger als die prominente Kombination aus „Check Sources“, „Verify sources“ und Haken vermuten lässt. Die wichtigsten nächsten Investitionen sind eindeutige Quellenidentitäten, bessere Auswahl tatsächlicher Quellenpassagen und eine Ergebnisdarstellung, die Prüfumfang und Auffälligkeiten unmittelbar zeigt. Mehr Modelle oder größere Tokenbudgets wären dafür zunächst die falsche Priorität.

**Was aktuell tatsächlich passiert**

Die Antwortmodelle liefern Antworten samt Quellen. Im Browser werden lokale Quellen-IDs in gemeinsame IDs übersetzt. Die Synthese erhält Modellantworten und kompakte Quellenlisten aus ID, Titel und URL; vollständige Quelldokumente sieht sie an dieser Stelle nicht. Sie soll vorhandene Quellenverweise für zentrale Fakten übernehmen.

Nach dem fertigen Consensus laufen die bestehenden Differences-/Coverage-Judges und die optionale Quellenprüfung parallel. Coverage prüft, welche Modellantwort einen Consensus-Satz unterstützt, widerspricht oder nicht behandelt. Differences ermittelt inhaltliche Unterschiede. Der Agreement-Score wird deterministisch aus diesen Ergebnissen berechnet. Der dritte Judge bekommt ausschließlich zitierte Consensus-Sätze und begrenzte Auszüge der zugehörigen Dokumente.

Dieser Judge prüft in Version 2 **Thema und zeitliche Passung**. Der Systemprompt untersagt ausdrücklich die Bewertung von Wahrheit, Belegwirkung und Richtigkeit; abweichende Zahlen oder fehlende Bedingungen sollen nicht als Themenfehler gelten. Er sucht keine neuen Quellen. Bei fehlenden Consensus-Zitaten erfolgt kein Abruf und kein Judge-Call. Abschalten von Check Sources ändert weder Synthese noch die beiden vorhandenen Judges.

Der Quellenstatus erscheint separat im Stream. Der abschließende Run, sein Share-Ergebnis und die Chat-Completion warten dennoch auf die Quellenprüfung. Das Feature ist somit inhaltlich und bei der frühen Anzeige entkoppelt, aber nicht vollständig vom Abschluss und der Persistenz.

Belege: [Quellenprompt](../app/services/source_verification.py), Zeilen 103–119; [Synthese und Quellenlisten](../app/services/llm/consensus_engine.py), Zeilen 312–343 und 416–445; [Streaming-Abschluss](../app/api/routers/chat.py), Zeilen 1642–1692 und 1730–1752; [Agreement-Berechnung](../app/services/llm/consensus_scoring.py).

**Was gut ist und erhalten bleiben sollte**

- Die drei Analysen beantworten unterschiedliche Fragen. Insbesondere bleibt Modellübereinstimmung von Quellenpassung getrennt. Eine Addition zu einem vermeintlichen Wahrheitsprozentsatz würde diese Klarheit zerstören. Der bestehende Score berücksichtigt außerdem unzureichende Modellabdeckung und setzt bei zu wenig Evidenz keinen belastbaren Gesamtwert.
- Der Quellencheck ist begrenzt: standardmäßig sechs eindeutige URLs, 32 Satz-/Quellen-Paare, 32.000 Eingabezeichen, 3.000 Ausgabetokens und ein Judge-Call ohne automatischen Retry. Ohne zitierte Sätze entstehen keine externen Aufrufe.
- Der Abruf hat für beliebige öffentliche URLs wichtige Schutzmaßnahmen: Prüfung aller DNS-Adressen und Redirects, Bindung an die geprüfte IP, TLS-Prüfung für den ursprünglichen Host, keine Cookies oder Umgebungs-Proxies sowie Grenzen für komprimierte und entpackte Daten. Das ist eine gute Grundlage; die Untersuchung ersetzt keinen vollständigen Sicherheitstest.
- Ergebnisvalidierung geschieht im Code: IDs, doppelte Befunde, Enums, Längen und angegebene Originalzitate werden geprüft. Mehrdeutige Quellen bleiben ungeprüft. Ungültige Resultate werden nicht als positive Prüfung behandelt.
- Es gibt explizite Teilprüfungen, einen Cache und begrenzte Worker. Gespeicherte Ergebnisse binden sich an den Antworttext; Bookmarks und Shares lösen keinen erneuten Judge aus. Das spart Geld und erhält den damaligen Zustand.
- Die UI zeigt Thema und Zeitraum getrennt, macht unbekannte und ungeprüfte Zuordnungen sichtbar und behandelt alte Belegurteile nicht einfach als neue Themenurteile. Diese Vorsicht ist richtig.

Belege: [Limits, Validierung und Snapshots](../app/services/source_verification.py); [Abruf und Cache](../app/services/source_documents.py); [Quellenbericht](../static/js/source-verification.js).

**Priorität 1: Das Vertrauenssignal ist stärker als der geprüfte Sachverhalt**

Konkretes Beispiel aus dem vorhandenen Evaluationssatz: Der Consensus nennt 20 Euro im Jahr 2024, das Dokument ausdrücklich 30 Euro für denselben Zeitraum. Das erwartete Ergebnis der aktuellen Themenprüfung lautet trotzdem `relevant / suitable`. Dasselbe gilt für einen Preis, der nur für Studierende gilt, während die Antwort ihn allen zuschreibt. Dies ist beabsichtigte v2-Semantik, kein Modellfehler.

Für einen Nutzer, der eine Quellenprüfung aktiviert, sind genau Zahlen, Bedingungen und Einschränkungen naheliegende Erwartungen. Die FAQ erklärt die Grenze korrekt; die Hauptbedienelemente vermitteln sie weniger deutlich. „Sources reviewed ✓“ erscheint bereits bei einem einzigen geprüften Paar, auch bei Teilprüfungen und auch dann, wenn alle geprüften Ergebnisse auffällig sind. Der Haken bezeichnet den abgeschlossenen Vorgang; er fasst dessen Ergebnis nicht zusammen. Auf schmalen Bildschirmen bleibt am Tab nur das Statussymbol sichtbar. Das ist eine plausible Fehlinterpretationsgefahr, kein durch Nutzertests bereits gemessener Befund.

Empfehlung: Check Sources als Dachbegriff ist vertretbar, wenn direkt am Ergebnis „Topic & time checked“ und eine klare Zusammenfassung stehen, beispielsweise „2 source issues · 3 unclear · 4/6 citation links checked“. Ein pauschaler Haken sollte nicht die Auffälligkeiten überstrahlen. Wichtig ist auch die Zähleinheit: `scope.pairs` zählt Satz-/Quellen-Zuordnungen, nicht eindeutige Quellen. Sechs geprüfte Zuordnungen können sämtlich auf derselben Website beruhen.

Falls das stärkere Produktversprechen gewollt ist, sollte eine **explizite Belegprüfung** hinzukommen: Stützt das Dokument die konkrete Aussage? Das kann zunächst begrenzt für wenige wichtige Aussagen oder auf Nutzeraktion geschehen. Themenpassung, Belegwirkung und unabhängige Faktenprüfung müssen begrifflich getrennt bleiben. Ein belegter Satz ist noch kein Beweis für eine vertrauenswürdige Quelle.

Belege: [Evaluationsfälle `missing_condition` und `contradiction`](../scripts/evaluate_source_verification.py); [Status und Haken](../static/js/source-verification.js), Zeilen 20–28, 71–101 und 124–129; [Composer/FAQ](../templates/index.html), Zeilen 537–539 und 1476–1484. Die gespeicherte mobile Aufnahme `artifacts/source-verification-ui/reviewed-390-False.png` wurde ergänzend angesehen; kein neuer Browserlauf wurde durchgeführt.

**Priorität 1: Serverseitige Quellenidentitäten sind nicht vereinheitlicht**

Im Browser führen `prepareResponseSourcesForEvidence` und `rewriteSourceTags` lokale Quellen-IDs in eine gemeinsame Nummerierung über. Die gemeinsame serverseitige Pipeline übernimmt dagegen Quellen und Antworttexte aus den Providern unverändert. Zwei Anbieter können daher beide `S1` für verschiedene URLs liefern. Diese Mehrdeutigkeit erreicht bereits die Synthese.

Der Quellencheck erkennt den Konflikt korrekt und prüft `S1` dann überhaupt nicht. Der Schutz ist richtig; der vorgelagerte Datenvertrag ist unvollständig. Die gemeinsame Pipeline wird von API, Watch und Topics aufgerufen, daher betrifft dies gerade die automatisch skalierenden Nutzungsarten. Nachgelagertes `sanitize_sources` löst den Bezug im Consensus nicht nachträglich: Es setzt eine doppelte ID beim zweiten Eintrag leer und erwartet laut eigener Dokumentation bereits globale Frontend-IDs.

Offline reproduziert über `analyze_provider_answers`: zwei Modellantworten, zwei verschiedene URLs, beide `S1` → `partial`, null geprüfte Paare, null Abrufe. Dies belegt den Fehler für diese Eingabekonstellation; seine Produktionshäufigkeit wurde nicht gemessen.

Empfehlung: Vor jeder Synthese serverseitig einen gemeinsamen Quellenkatalog erzeugen und Antwortverweise deterministisch umschreiben. Herkunft `(Provider, lokale Quellen-ID)` erhalten; gemeinsame URL-Identität zusätzlich abbilden. Browser, API, Watch und Topics müssen denselben Vertrag verwenden. Erst dann ist der Quellencheck über alle Kanäle vergleichbar.

Belege: [Browser-Mapping](../static/js/sources.js), Zeilen 423–474; [Provider-Übernahme](../app/services/llm/provider_transport.py), Zeilen 148–153; [gemeinsame Analyse](../app/services/consensus_pipeline.py), Zeilen 81–116; [Ambiguitätsschutz](../app/services/source_verification.py), Zeilen 275–290; [Sanitizer](../app/services/share_snapshots.py), Zeilen 177–228.

**Priorität 1: Das begrenzte Textbudget wird noch nicht gezielt eingesetzt**

Der Extraktor entfernt einige HTML-Nebenelemente und behält anschließend die ersten 4.000 Textzeichen. Er wählt keine für den geprüften Satz passende Passage. Eine lange Einleitung kann das gesamte Budget verbrauchen, während Preise, Bedingungen, Tabellen oder Gültigkeitsangaben später im Dokument stehen. Ein synthetisches HTML-Dokument mit einer entscheidenden Information hinter der Einleitung reproduziert genau diesen Verlust.

Abrufe erfolgen nacheinander. Die ersten maximal 32 Paare und sechs URLs werden nach Auftreten ausgewählt; es gibt keine Priorisierung nach Wichtigkeit, Konflikt, Zeitbezug oder schwacher Modellabdeckung. Im Test mit sieben Quellen bleibt die siebte ungeprüft. Drei langsame Abrufe können bei fünf Sekunden je Abruf das gesamte standardmäßige Fetch-Fenster von 15 Sekunden aufbrauchen. PDFs und JavaScript-seitig geladene Inhalte bleiben grundsätzlich außen vor.

Empfehlung: Zuerst innerhalb des vorhandenen Download-/Textbudgets bessere Passagen auswählen: Hauptinhalt erkennen, Absätze/Tabellen strukturieren, nach Entitäten und Aussagebegriffen gewichten, passende Abschnitte samt Nachbarkontext an den Judge geben. Dazu sind zunächst weder ein Planungs-LLM noch Embeddings nötig. Alle ausgewählten Claims einer URL gemeinsam berücksichtigen. Begrenzte Abrufparallelität hilft gegen langsame Einzelquellen, braucht aber ein gemeinsames globales und gegebenenfalls hostbezogenes Limit.

PDF-Unterstützung wäre für bestimmte wissenschaftliche oder technische Fragen wertvoll, sollte aber erst anhand realer Ausfallkategorien priorisiert werden. Ein unbeschränkter Browser-Fallback pro Quelle wäre für den gegenwärtigen Kostenrahmen keine gute Standardlösung.

Belege: [Extraktion](../app/services/source_documents.py), Zeilen 100–145; [Auswahl und serielle Abrufe](../app/services/source_verification.py), Zeilen 259 und 281–337; [unterstützte Formate](../app/services/source_documents.py), Zeilen 74–79.

**Priorität 2: Begrenzte Last ist noch keine verlässliche Prüfabdeckung bei Wachstum**

Vier Worker und vier Slots gelten für die gesamte Quellenprüfung pro Python-Prozess, einschließlich Abruf und Modellwartezeit. Bei voller Belegung gibt es keine Warteschlange: Die nächste Prüfung wird unmittelbar mit ungeprüften Paaren abgeschlossen. Derselbe Pool bedient die verschiedenen Pipeline-Aufrufer; es gibt innerhalb dieses Moduls keine reservierten Slots für interaktive Nutzer gegenüber Hintergrundläufen.

Der Cache umfasst 128 Dokumente für standardmäßig eine Stunde, ausschließlich im Prozess. Zeitgleiche Cache-Misses derselben URL werden nicht zusammengeführt; Fehler werden nicht negativ gecacht. Nach Neustarts und über mehrere Prozesse hinweg wird erneut abgerufen. Der Cache spart außerdem nur den Dokumentabruf, nicht den Judge-Call für einen neuen Run.

Eine Größenordnung, ausdrücklich kein Lasttest: Bei durchschnittlich 20 Sekunden Belegungszeit erlauben vier dauerhaft ausgelastete Slots rechnerisch zwölf Prüfungen pro Minute und Prozess; bei 40 Sekunden sechs. Reale brauchbare Kapazität liegt wegen Lastspitzen unter dieser idealisierten Vollauslastung. Mit dem einzelnen vorhandenen Live-Regressionsergebnis von 35,8 Sekunden wären es rechnerisch rund 6,7 pro Minute. Ein solcher Einzelwert liefert weder den Produktionsmittelwert noch p95.

Auch die Kosten skalieren mit neuen Läufen: Derselbe lokale Regressionstest nennt 0,004587 USD für einen synthetischen 32-Paar-Call. 100.000 identische Calls wären rechnerisch 458,70 USD **nur für den Quellen-Judge**. Das ist keine Kostenprognose und enthält weder Antwortmodelle noch Synthese, andere Judges oder Infrastruktur. Entscheidend ist die zusätzliche Kostenlast je tatsächlich nutzbarer Prüfung, nicht lediglich die Kosten je gestartetem Call.

Empfehlung: Zuerst Kapazitätsausfälle und Latenzen messbar machen, dann eine kurze begrenzte Warteschlange beziehungsweise faire Kapazitätsverteilung einführen. Gleichzeitige Abrufe derselben URL bündeln und erfolglose Abrufe kurz zwischenspeichern. Ein gemeinsamer Cache lohnt sich erst bei nachgewiesener Wiederverwendung und mehreren Prozessen. Ein späterer Ergebnis-Cache muss Aussage, Frage/Zeitraum, Dokumentinhalt, Modell und Promptversion einbeziehen; die URL allein reicht nicht.

Belege: [Worker und Kapazitätspfad](../app/services/source_verification.py), Zeilen 27–28 und 391–423; [Cache](../app/services/source_documents.py), Zeilen 148–165; [einzelner Live-Regressionswert](../artifacts/source-verification-live-regression.json).

**Priorität 2: Betriebsdiagnose und tatsächliche Qualität sind noch nicht ausreichend sichtbar**

Fetch-Fehler werden pauschal übersprungen. Der resultierende ungeprüfte Eintrag unterscheidet nicht zwischen voller Kapazität, PDF, blockierter Adresse, HTTP-Fehler, Timeout, ID-Konflikt oder Textlimit. `fetched_sources` zählt tatsächlich URL-Versuche, auch erfolglose. Im simulierten Kapazitätsausfall steht dort sogar eins, obwohl gar kein Netzwerkabruf stattfand. Der UI-Text fasst dies als „Source unavailable or check limit reached“ zusammen.

Tokenkosten und Dauer sind im Snapshot vorhanden; die Quellenmodule schreiben aber keine eigenen aggregierten Qualitäts-/Kapazitätsmetriken in `record_metric`. Nur per Run gespeicherte Daten zu untersuchen wird im Betrieb unnötig aufwendig. Im Quellenworker wird außerdem die Cancellation übernommen, jedoch kein expliziter Correlation-Kontext.

Empfehlung: Inhaltsfreie Kategorien für ungeprüfte Paare/Dokumente speichern und aggregieren: `capacity`, `ambiguous_id`, `unsupported_format`, `http_error`, `timeout`, `input_limit`, `output_limit`, `invalid_output`. Dazu erfolgreiche Abrufe getrennt von Versuchen, Cache-Treffer, geprüfte Paare/eindeutige Dokumente, unknown-Anteil, p50/p95-Dauer, zusätzliche Zeit bis zum Run-Abschluss und Kosten erfassen. Diese Informationen erlauben gezielte Verbesserungen ohne Prompts oder Antworttexte zu loggen.

Die vorhandenen Unit-Tests prüfen Verträge und Sicherheitsgrenzen gut. Sie beantworten nicht, wie zuverlässig das Modell reale Webseiten beurteilt. Der Evaluationssatz ist klein und synthetisch; frühere v1-Ergebnisse sind kein Nachweis für v2. Der neue 32-Paar-Lauf ist ein Laufzeit-/Robustheitsfall. Der vorhandene Prompt-Injection-Fall erwartet sogar dasselbe Themenurteil, das die eingeschleuste Anweisung verlangt; allein daran lässt sich keine erfolgreiche Abwehr erkennen.

Vor einer stärkeren Qualitätsaussage braucht es einen menschlich bewerteten v2-Satz mit realistischen Dokumentauszügen, mehreren Sprachen, Tabellen, falschen Datierungen, irrelevanten Passagen, Gegenbelegen und mehrdeutigen Quellen. Besonders relevant ist die Rate beruhigender Resultate bei unzureichender oder unpassender Evidenz. Keine Live-Modellcalls wurden für dieses Review ausgelöst.

**Die größte ungenutzte Verbindung zur Consensus Engine**

Bereits heute bestehen zwei wertvolle Zuordnungen: Consensus-Satz → Modellpositionen und Consensus-Satz → Quellenbefunde. Die gemeinsame Satznummerierung ermöglicht eine zusätzliche Darstellung ohne weiteren Judge: „Modelle stimmen überein, Quellenlage unklar“ oder „Modelle widersprechen sich, angeführte Quellen betreffen unterschiedliche Zeiträume“. Die zweite Aussage darf nur erscheinen, wenn die konkreten Befunde sie tatsächlich tragen; eine erkannte Zeitabweichung beweist noch nicht die Ursache des Modellkonflikts.

Ein gemeinsamer Satz-Reader könnte Modellbeiträge, Zitatverweise und Quellenpassung nebeneinander zeigen. Agreement bleibt unverändert; der Nutzer sieht jedoch, wo er genauer hinsehen sollte. Zusätzlich lässt sich zeigen, ob mehrere Modelle dieselbe URL anführen. Das misst gemeinsame Quellenverwendung, nicht automatisch die vollständige Unabhängigkeit ihrer Evidenz. Syndizierte Artikel und übernommene Primärquellen bleiben ohne weitere Herkunftsanalyse offen.

Für eine spätere Belegprüfung wären diese vorhandenen Informationen eine gute Priorisierungsgrundlage: zentrale Zahlen, Bedingungen, zeitabhängige Aussagen und Konflikte zuerst. Da die Judges derzeit parallel laufen, sollte der schnelle Standardcheck nicht auf Coverage warten müssen. Die Auswahl kann zunächst deterministisch erfolgen; eine optionale Vertiefung kann die später verfügbaren Coverage-/Differences-Befunde nutzen.

Auch Watch hat Potenzial: Eine relevante Änderung der Quellenpassung kann interessant sein, obwohl der Consensus-Wortlaut stabil bleibt. Die bestehenden Watch-Ergebnisse speichern den Snapshot bereits, die Änderungsanalyse erhält dagegen den alten und neuen Consensus. Ein getrenntes Signal für Quellenänderungen müsste zeitweilige Abruffehler von belastbaren Änderungen unterscheiden und dürfte nicht wegen jedes Cache- oder Datumswechsels alarmieren. `source_version` enthält derzeit auch Abrufmetadaten und ist deshalb kein reiner Inhaltsänderungsindikator.

Für gespeicherte Ergebnisse sollte der Prüfzeitpunkt sichtbar sein. `checked_at` wird gespeichert, im Quellenbericht aber nicht ausgegeben. Gerade „Time matches“ darf Monate später nicht wie eine frische Prüfung aussehen. Bei positiven Urteilen fehlen häufig Originalpassagen: Das spart Tokens und Speicher, erschwert aber die eigene Nachprüfung. Gezielt gespeicherte kurze relevante Auszüge wären ein nachvollziehbarer nächster Schritt, besonders für eine spätere Belegprüfung.

**Empfohlene Reihenfolge**

1. Gemeinsamen serverseitigen Quellenkatalog herstellen; Browser/API/Watch/Topics auf denselben ID-Vertrag bringen. Ergebniszusammenfassung, Zähleinheiten und sichtbaren Prüfzeitpunkt präzisieren.
2. Abruf-/Kapazitätsursachen messen und Auszüge nach Relevanz auswählen; vorhandene Budgets zunächst beibehalten. Gegen einen realistischen v2-Evaluationssatz prüfen.
3. Modellpositionen und Quellenbefunde im selben Satz-Reader zusammenführen. Begrenzte Kapazitätsverteilung und Cache-Verbesserungen anhand gemessener Last ergänzen.
4. Erst danach eine begrenzte Belegprüfung beziehungsweise gezielte Vertiefung testen. Zusätzlichen Nutzen, Fehlalarme, Latenz und Kosten je hilfreichem Befund messen. Einen vollständigen autonomen Research-Agenten würde ich daraus aktuell nicht machen.

**Validierung dieses Reviews**

- 100 Backend-Tests für Quellenprüfung und Chat-Integration bestanden.
- 24 weitere Backend-Tests für Consensus Engine und Antwortvertrag bestanden.
- 10 JavaScript-Tests für Quellenbericht, Judge-Events und Coverage-Darstellung bestanden.
- Fünf zusätzliche Offline-Probes bestanden: Quellen-ID-Kollision in der echten Analyse-Orchestrierung, erlaubte Passung trotz Zahlenwiderspruch, verlorene Passage hinter dem Textlimit, ausgeschöpfte Worker-Kapazität und reihenfolgeabhängige Quellenauswahl. Judge und Abrufe waren dabei kontrolliert ersetzt; dies misst keine Modellgenauigkeit.

Reproduktion: `venv\Scripts\python.exe artifacts/check-sources-architecture-review/probes.py`. [Probe-Code](../artifacts/check-sources-architecture-review/probes.py) und [Resultate](../artifacts/check-sources-architecture-review/probe-results.json). Es gab keinen Produktionslasttest, keine neue Browser-E2E-Ausführung und keine kostenpflichtigen Modellaufrufe. Die bestehenden uncommitteten Produktänderungen wurden nicht bearbeitet.

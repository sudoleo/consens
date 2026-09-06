# UX-Analyse: Chat und Antwortprüfung in consens.io

Stand: 6. September 2026. Scope: Fragen, Composer, Antworten, Modellvergleich, Markierungen, Differences, Quellen, Fortsetzungen und unmittelbar zugehörige Aktionen. Keine Analyse von Landingpage, Watches-Dashboard, Billing oder Admin.

## Methode und Grenzen

Heuristische Analyse anhand der öffentlichen Live-App auf https://www.consens.io/app und des lokalen Frontend-Codes. Die interaktive Demo wurde vollständig durchlaufen; Markierungsdetails, Differences und der Sprung zur Modellantwort wurden bedient. Desktop im vorhandenen Browserformat sowie mobile Ansicht mit 390 × 844 Pixeln geprüft. Die mobile Markierungsansicht wurde geöffnet und visuell geprüft.

Die Live-Seite zeigte Build `439d78b`. Lokaler Code und Deployment sind nicht als identisch verifiziert. Die lokale Architekturkarte hatte bereits Änderungen; sie wurde nicht verändert. Keine Änderungen am Produktcode.

**Live** bezeichnet beobachtetes Verhalten der öffentlichen Demo. **Code** bezeichnet implementiertes Verhalten, das ohne angemeldete Sitzung nicht vollständig durchgespielt wurde. **Hypothese** bezeichnet eine erwartbare Nutzerinterpretation, keinen durch Nutzerstudien belegten Effekt. Authentifizierte Mehrfach-Turns, echte Providerfehler, Uploads, Resolve-Aufrufe und Screenreader-Nutzung wurden nicht live getestet. Browser-Accessibility-Tree ist kein Ersatz für einen Screenreader-Test. Keine pauschale WCAG-Konformitätsaussage.

## Gesamturteil

Die Grundstruktur ist sinnvoll: erst eine nutzbare Antwort, dann bei Bedarf ihre Grundlage prüfen. Die Differenzierung liegt in der Möglichkeit, Uneinigkeit sichtbar und nachvollziehbar zu machen.

Das größte Risiko ist semantisch: Die Oberfläche verbindet **Gespräch**, **Synthese**, **Modellabgleich** und **Bewertung**. Grüne Sätze, Quoten, ein Agreement-Score und „checks“ können zusammen wesentlich mehr Sicherheit vermitteln, als ein Vergleich von Modellantworten rechtfertigt. Gleichzeitig müssen Nutzer den Unterschied zwischen mehreren Arten von Zustimmung, Abweichung und fehlender Abdeckung lernen.

Die empfohlene Leitidee lautet: **„Ich stelle eine Frage, erhalte eine zusammengeführte Antwort und sehe, welche Punkte ich vor einer Entscheidung prüfen sollte.“**

## Mentale Modelle

| Nutzererwartung | Aktuelle Signale | Möglicher Bruch | Ziel |
|---|---|---|---|
| „Ich rede in einem fortlaufenden Chat.“ | Composer und Frageblase | „New comparison“, „Bookmarks“, Fortsetzung nur im passenden Modus | Einheitliches Gesprächsvokabular und erkennbare Kontextkontinuität |
| „Die Antwort hilft mir weiter.“ | Consensus als Hauptantwort | „Consensus“ kann volle Einigkeit suggerieren | Synthese und offene Entscheidungen gemeinsam zeigen |
| „Grün heißt richtig/geprüft.“ | Flächige grüne Markierungen, 6/6 | Modellzustimmung ist kein externer Faktennachweis | Zustimmung ausdrücklich als Modellvergleich benennen |
| „4/4 bedeutet alle Beteiligten.“ | 4/4 innerhalb eines Sechs-Modell-Laufs | Nenner zählt nur Modelle, die die Aussage behandeln | Zustimmung, Widerspruch und Nichtbehandlung gemeinsam erklären |
| „Ein Widerspruch muss aufgelöst werden.“ | Critical, Resolve | Unterschied kann von Präferenzen oder fehlendem Nutzerkontext abhängen | Erst Entscheidungsbedingung klären, dann ggf. erneut prüfen |
| „Meine alte Antwort bleibt untersuchbar.“ | Verlauf im selben Chat | Historische Interaktionen werden reduziert | Gleiche Prüfhandlungen pro Turn anbieten |
| „Das Modell über der Antwort hat sie geschrieben.“ | Modellpicker im Antwortkopf | Auswahl für den nächsten Lauf und Herkunft der bestehenden Antwort liegen eng zusammen | Ergebnis-Herkunft von künftiger Konfiguration trennen |

## Priorisierte Befunde

Priorität 1: vor weiteren Chat-Features bearbeiten; Priorität 2: nächste UX-Iteration; Priorität 3: Verfeinerung. Die Prioritäten bewerten die erwartete Auswirkung, keine gemessene Häufigkeit.

### 1. Zustimmung wirkt wie ein Faktencheck — Priorität 1

**Live + Code.** Fast jeder prüfbare Satz der Demo erhält eine grüne oder andersfarbige Markierung. Die Legende sagt „Every checkable sentence was compared against each model“; der Toggle heißt „Hide checks“. Dazu kommt der Agreement-Score. Die Einschränkung „Models agreeing is not proof“ ist vorhanden, aber erst nach der Antwort beziehungsweise im Detail.

**Mentales Modell:** Farbige Prüfung erinnert an Korrektur, Freigabe und Validierung. Nutzer können die Warnung kennen und Grün beim schnellen Lesen dennoch als Bestätigung behandeln.

**Empfehlung:** Eine kurze Erklärung direkt am Antwortanfang: „Zusammengeführt aus 6 Modellantworten. Markierungen zeigen Modellzustimmung.“ Den Toggle „Modellabgleich anzeigen“ nennen. Kritische Punkte früh signalisieren; die ausführliche Analyse kann unterhalb bleiben. Kein großer Score-Block oberhalb des Textes nötig.

**Prüfkriterium:** Nutzer erklären ohne Hilfestellung, dass 6/6 weder Wahrheit noch sechs unabhängige Quellen bedeutet.

### 2. Der wechselnde Nenner verschleiert fehlende Abdeckung — Priorität 1

**Live + Code.** „She is scanning for a date“ trägt 4/4. Der geöffnete Dialog heißt „All 4 models agree“, listet vier zustimmende Modelle und zwei unter „Not addressed“. Der zugängliche Buttonname ist präziser als die sichtbare Überschrift. Berechnet wird der Nenner aus Zustimmung plus Abweichung, ohne Nichtbehandlung.

**Problem:** 2/2 kann oberflächlich genauso vollständig aussehen wie 6/6. Der Titel „All 4 models agree“ verstärkt dies.

**Empfehlung:** Im Detail stets „4 stimmen zu · 0 widersprechen · 2 behandeln den Punkt nicht“. Inline einen knappen, erklärbaren Support-Indikator verwenden. Nicht einfach 4/6 daraus machen: Das könnte die zwei schweigenden Modelle als Gegenstimmen erscheinen lassen.

**Code:** `static/js/consensus-insights.js`, `openClaimPopover`, `claimBadgeLabel`, Badge-Rendering.

### 3. Grau bezeichnet zwei fachlich verschiedene Zustände — Priorität 1

**Live + Code.** Die Legende erklärt Grau sowohl als Detailabweichung als auch als zu geringe Behandlung durch die Modelle. Ein kleiner Widerspruch wird zudem im Inline-Button als „differ on a detail“ beschrieben, in der Karte als „Contradiction · minor detail“.

**Problem:** „Untersucht und nur leicht verschieden“ ist etwas anderes als „nicht ausreichend untersucht“. Amber und Rot benötigen ebenfalls eine klare Grenze: Nicht jede Meinungsverschiedenheit ist eine faktische Unvereinbarkeit.

**Empfehlung:** Ein gemeinsames Statusmodell für Text, Dialog und Karte: „gestützt“, „unvereinbare Aussagen“, „andere Gewichtung“, „zu wenig Vergleichsbasis“. Schweregrad getrennt vom Typ führen. Farbe immer durch Label oder Symbol ergänzen; fehlende Abdeckung beispielsweise neutral gestrichelt darstellen.

### 4. Die Demo widerspricht ihrer eigenen Modellbasis — Priorität 1

**Live, reproduziert in dieser Sitzung.** Die Antwort spricht von sechs Modellen. Markierungen, Analyse und „Answers 6“ verwenden sechs. Der Lauf meldete „4 answers in 8.4 s“ und endete mit „4 models · 23 s“. Im geöffneten Antwortvergleich waren Mistral und Claude als ausgeschlossen dargestellt; GLM und Muse hatten Modellköpfe ohne sichtbare Antworttexte.

**Problem:** Ausgerechnet die Oberfläche, die Nachvollziehbarkeit demonstriert, liefert widersprüchliche Angaben zur Grundlage. Das ist ein konkreter Demo-Befund, kein Nachweis desselben Fehlers in echten Läufen.

**Empfehlung:** Demo-Modellprofil, Antworten, Markierungen und Zähler gemeinsam fixieren. Nichtteilnehmende Familien aus der Ergebnisansicht entfernen. Separat prüfen, ob eine konfigurierte Auswahl ungewollt die Demo-Darstellung beeinflusst; die genaue Ursache wurde nicht isoliert.

### 5. Die Markierungsdichte schwächt Lesbarkeit und Warnsignale — Priorität 2

**Live.** Ganze Absätze erscheinen nahezu durchgehend grün hinterlegt, zusätzlich mit wiederholtem 6/6. Mobile Quoten können auf eigene Zeilen umbrechen. Auch der Satz, der einen Drei-gegen-drei-Konflikt beschreibt, ist grün mit 6/6: fachlich erklärbar als Zustimmung zur Beschreibung des Konflikts, beim Scannen jedoch widersprüchlich.

**Empfehlung:** Standardmäßig Unstimmigkeiten und fehlende Abdeckung hervorheben, normale Zustimmung zurückhaltender. Ein vollständiger Prüfmodus darf alle Satzprüfungen zeigen. Die vorhandene Ausblendfunktion beibehalten, aber vor oder unmittelbar an der Antwort erreichbar machen. Metaaussagen über den Vergleich nicht genauso markieren wie die eigentlichen Empfehlungen.

### 6. Der Score verdichtet zu stark — Priorität 1

**Live + Code.** Die Demo zeigt 45/100 „Partial agreement“, einen kritischen und einen kleineren Konflikt. Im Code bestimmt der Gesamtwert die Farbe des Verdicts; ein hoher Score kann daher grundsätzlich ruhig wirken, obwohl eine wichtige Einzelfrage strittig bleibt.

**Problem:** Der Nutzer muss seine konkrete Entscheidung bewerten, nicht den mittleren Zustand aller Aussagen. 45/100 besitzt außerdem eine Genauigkeitsanmutung, deren Bedeutung ohne Methodik unklar bleibt.

**Empfehlung:** Den wichtigsten offenen Punkt sprachlich priorisieren. Score sekundär lassen und an derselben Stelle als Bewertung der Modellübereinstimmung erklären. Typ und Schwere eines Konflikts unabhängig davon sichtbar halten. Ein hoher Wert darf einen entscheidungsrelevanten Widerspruch nicht überdecken.

### 7. Differences sind gut strukturiert, aber der nächste Schritt ist nicht immer der richtige — Priorität 2

**Live.** Die Karten zeigen Streitfrage, Modellgruppen, Positionen, Zitate, Antwortsprünge und „Worth verifying“. Das ist ein starker Ansatz. Beim Beispiel „Schlusssatz behalten oder streichen?“ hängt die Entscheidung davon ab, ob das Datum verhandelbar ist. Trotzdem folgt „Resolve with the models“ als hervorgehobene Aktion.

**Mentales Modell:** Der Button verspricht eine Lösung durch mehr Modellarbeit, obwohl dem System eine Information des Nutzers fehlt.

**Empfehlung:** Zuerst „Ist der 29. noch verhandelbar?“ als gezielte Rückfrage mit sichtbarem Bezug anbieten. Je nach Konflikt „Kontext ergänzen“, „Quelle prüfen“ oder „Modelle erneut abgleichen“. „Critical“ verständlicher als entscheidungsrelevante Folge formulieren. Reine Stilabwägungen nicht wie objektive Fehler behandeln.

### 8. „Resolve“ und „Resolved“ können einen Wahrheitsabschluss suggerieren — Priorität 2

**Code; kein Resolve live ausgelöst.** Eine Resolve-Runde konfrontiert Modelle mit Gegenpositionen; das Ergebnis kann anzeigen, dass Modelle ihre Position geändert haben. Dafür existiert das Label „Resolved“.

**Empfehlung:** „Nach Gegenprüfung einig“ beziehungsweise „Widerspruch bleibt“. Kurz erklären, wer seine Position geändert hat und warum. Das Ergebnis muss erkennen lassen, ob nur die Difference ergänzt oder auch die Hauptantwort neu geschrieben wurde. Vor Start Umfang und Kontingentfolge sichtbar nennen, nicht nur im Tooltip.

### 9. Chat, Comparison und Bookmark bilden kein einheitliches Objekt — Priorität 1

**Live + Code.** Sidebar: „New comparison“ und „Bookmarks“. Der Code bietet fortlaufende Gespräche und einen Suchplatzhalter „Search chats“. Fortsetzung entsteht nach erfolgreichem Consensus; `isArmed()` hängt zusätzlich vom Agent Mode ab.

**Problem:** Nutzer müssen erraten, ob ein Eintrag eine einzelne Antwort, ein manuell gespeichertes Ergebnis oder einen automatisch gespeicherten Chat repräsentiert. Ein Moduswechsel kann außerdem die erwartete Fortsetzung verändern.

**Empfehlung:** Für das Gespräch „Chats“ und „Neuer Chat“ verwenden; „Vergleich“ für den Arbeitsschritt innerhalb eines Turns. Agent Mode nach seinem Effekt benennen, etwa „Antworten zusammenführen“. Beim Wechsel in einen kontextlosen Modus die Folge ausdrücklich anzeigen. Keinen zusätzlichen Follow-up-Schalter und keine Zwangswahl einführen: natürliches Weiterschreiben ist richtig.

### 10. Historische Antworten verlieren Prüfbarkeit — Priorität 1

**Code.** Vergangene Turns werden statisch gerendert. Difference-Sprungaktionen werden im Archiv ausgelassen; bestehende Buttons werden bei statischen Kopien teilweise durch Anzeigeelemente ersetzt. Das verhindert falsche Sprünge in den neuesten Turn, reduziert aber die Interaktionskontinuität.

**Problem:** Was vor der Anschlussfrage klickbar war, ist danach nicht mehr auf dieselbe Weise untersuchbar. Der Nutzer hat seine Frage erweitert, nicht seine alten Belege aufgegeben.

**Empfehlung:** Prüfdetails, Originalantworten und Quellen turnbezogen erreichbar halten. Neue Resolve-Ausführung darf weiterhin explizit behandelt werden. Lesende Interaktionen sollten nicht verschwinden. Vor Umsetzung prüfen, welche historischen Markierungen bereits neu aufgebaut werden und welche nur noch Anzeige sind.

### 11. Modellkonfiguration und Antwort-Herkunft liegen zu eng beieinander — Priorität 2

**Live + Code.** Antwortköpfe enthalten Modellpicker und „Exclude answer“. Gleichzeitig konfigurieren Teile der Auswahl den nächsten Lauf. Dazu wechseln Benennungen zwischen OpenAI, ChatGPT, Claude und konkreten Modellnamen.

**Problem:** Nach einer Änderung ist nicht selbstverständlich, ob die vorhandene Antwort neu berechnet wurde, nur unsichtbar ist oder beim nächsten Lauf nicht mehr beteiligt sein wird.

**Empfehlung:** Herkunft der bestehenden Antwort unveränderlich anzeigen. Künftige Auswahl im Composer konfigurieren und als „Für die nächste Frage“ kennzeichnen. Jede Ausschlussaktion nach ihrer tatsächlichen Wirkung benennen; falls eine neue Synthese nötig ist, dies sichtbar anbieten. Einheitliches primäres Modelllabel in Quote, Karte und Antwortkopf.

### 12. Fortschritt erklärt Phasen; Vollständigkeit braucht ebenso klare Zustände — Priorität 2

**Live + Code.** Modellantworten, Synthese und Widerspruchsprüfung werden als Phasen dargestellt. Der Code erlaubt das Überspringen langsamer Modelle, Abbruch, Teilergebnisse und Hintergrundläufe. „New comparison“ bricht einen laufenden Vergleich bewusst nicht ab.

**Empfehlung:** Nach Teilfehlern „4 von 6 Antworten verfügbar; 2 fehlgeschlagen“ zeigen und die Konsequenz für den Abgleich erklären. „Antwort fertig, Modellabgleich noch offen“ von „vollständig geprüft“ trennen. Neue Chats sollten laufende Arbeit mit eindeutigem Status in der Sidebar zurücklassen. Bei Retry zwischen noch nicht gestarteter Anfrage und neuem kostenpflichtigem Lauf unterscheiden. Diese Fehlerpfade brauchen einen angemeldeten Durchlauf, bevor konkrete Defekte behauptet werden.

### 13. Zitatnachfragen sind stark, verlieren aber Herkunft — Priorität 2

**Code.** „Ask about this“ überträgt ausgewählten Antworttext in einen separaten Zitatbereich. Der Quote-State speichert Text, nicht Modell und Turn; `compose()` bezeichnet ihn allgemein als Passage aus der vorherigen Antwort. Bei 1.200 Zeichen wird gekürzt.

**Empfehlung:** Die gute Trennung zwischen Frage und Zitat beibehalten. „Zitat aus Claude · Antwort 2“ mitspeichern und anzeigen; Kürzung kenntlich machen. Sonst sind Rückfragen zu konkurrierenden Modellantworten unnötig mehrdeutig. „Remember“ daneben ausdrücklich als dauerhafte Präferenz/Aufzeichnung erklären, damit es nicht mit Markieren oder Speichern dieses Chats verwechselt wird.

### 14. Quellen und Modellzustimmung müssen getrennte Belegarten bleiben — Priorität 2

**Code; die geprüfte Demo hatte keinen Quellen-Tab.** Es gibt Zitationsverweise und ein separat aufklappbares Quellenverzeichnis mit „Verify sources“. Die Zuordnung von Quellen erfolgt auch turnbezogen.

**Empfehlung:** Quellen als externe Belege, Modellantworten als Vergleichsgrundlage benennen. Beim Zitat sollte klar sein, ob eine Quelle lediglich von einem Modell genannt wurde oder die konkrete Aussage tatsächlich geprüft wurde. Ohne externe Belege besser „Keine externen Quellen in diesem Ergebnis“ als eine vermeintliche Vollprüfung durch grüne Modellmarkierungen. Die vorhandenen Quellenlinks nicht als defekt bewerten; der komplette Flow bleibt live zu prüfen.

### 15. Mobile Details sind brauchbar, die Hauptansicht bleibt dicht — Priorität 2

**Live + Code.** Bei 390 × 844 Pixeln war das Markierungsdetail gut lesbar, mit separaten Modellgruppen, erreichbarem Schließen-Button und aus dem Accessibility-Tree entferntem Hintergrund. Die Hauptansicht kombiniert hingegen Markierungen, Legende, Score, Details, Aktionen und einen großen feststehenden Demo-Loginbereich. Die obere Navigation überlagert beim Scrollen einen Teil des Textbereichs. Auf Desktop reichte der geöffnete 4/4-Popover im beobachteten Ausschnitt unter den sichtbaren unteren Rand; Erreichbarkeit der restlichen Inhalte gesondert prüfen.

**Empfehlung:** Lesefläche mobil priorisieren und insbesondere nach Ende der Demo die Loginaufforderung kompakter halten. Popover an verfügbare Höhe anpassen; lange Inhalte intern scrollbar halten. Kleine Quoten benötigen größere unsichtbare Trefferflächen. Fokus-Rückkehr, Escape, Zoom, echte Bildschirmtastatur und Farberkennung separat testen. Positiv: Der Composer-Code schützt Entwürfe, Anhänge und Zitate vor automatischem Einklappen und berücksichtigt reduzierte Bewegung.

## Empfohlenes Zielbild pro Chat-Turn

1. **Frage:** vollständig aufklappbar, Anhänge sichtbar zugehörig, bei Zitaten Herkunft erhalten.
2. **Kurze Herkunftszeile:** „Aus 6 Modellantworten zusammengeführt“; bei Ausfällen ehrliche Vollständigkeit.
3. **Antwort:** gut lesbar; strittige Entscheidungen bereits im Text verständlich.
4. **Prüfhinweis:** z. B. „Ein Punkt hängt von deinem Kontext ab: Ist das Datum verhandelbar?“
5. **Vertiefung:** „Unterschiede“, „Modellantworten“, „Quellen“. Labels dürfen knapp sein, ihre Bedeutung muss konsistent bleiben.
6. **Aktionen:** Kopieren nahe an der Antwort; Teilen und weitere Aktionen zurückhaltend. Nachfragen auf einen konkreten Streitpunkt vor einer pauschalen Resolve-Runde anbieten.
7. **Composer:** Gespräch einfach fortsetzen. Konfiguration gilt erkennbar für die nächste Frage.

Es braucht dafür weder einen zweiten Follow-up-Composer noch zusätzliche Pflichtdialoge. Die vorhandene Struktur kann weitgehend bleiben; entscheidend sind konsistente Begriffe, sparsamere Markierungen und turnbezogene Prüfbarkeit.

## Umsetzungsreihenfolge

**Zuerst:** Demo-Konsistenz; Nenner-/Abdeckungssemantik; eindeutige Farbzustände; Verhältnis zwischen Agreement und Richtigkeit; Chat-Terminologie und Kontextwirkung des Moduswechsels.

**Danach:** Markierungsdichte reduzieren; historische Details interaktiv halten; kontextbezogene Differences-Aktionen; Herkunft von Zitaten und Modellantworten klarstellen.

**Anschließend:** Mobile Verdichtung, lange Popover, Quellenzustände, Teilfehler und Kontingentfolgen anhand echter angemeldeter Abläufe verifizieren.

## Nutzertest zum Validieren der Hypothesen

Vorschlag: fünf bis acht Personen mit unterschiedlichen Erfahrungen mit KI-Chats; ein Teil mobil. Qualitative Beobachtung, keine repräsentative Messung. Erfolgsziele vor dem Test festlegen.

| Aufgabe | Beobachten |
|---|---|
| Eine Antwort lesen und entscheiden, ob man ihr vertraut | Wird Agreement mit Richtigkeit verwechselt? |
| 4/4 bei sechs Modellen erklären | Werden zwei Nichtbehandlungen erkannt, ohne sie als Gegenstimmen zu zählen? |
| Eine rote und eine graue Passage erklären | Lassen sich Widerspruch, Gewichtung und fehlende Abdeckung unterscheiden? |
| Den wichtigsten Streitpunkt und seine Konsequenz nennen | Wird zuerst eine Nutzerinformation benötigt oder blind Resolve gewählt? |
| Gegenposition in der Originalantwort finden und zurückkehren | Bleiben Stelle und Gedankengang erhalten? |
| Anschlussfrage stellen, dann eine alte Aussage prüfen | Bleiben Kontext und Prüfbarkeit erwartungskonform? |
| Modellwahl ändern und Wirkung vorhersagen | Ist klar, ob die aktuelle oder nächste Antwort betroffen ist? |
| Einen teilweise fehlgeschlagenen Lauf fortsetzen | Sind Vollständigkeit, nächste Aktion und Kontingentfolge verständlich? |

Erheben: ungestütztes Verständnis, Fehlinterpretationen, Zeit bis zur relevanten Gegenposition, Abbrüche und subjektive Sicherheit vor/nach dem Öffnen der Belege. Allgemeine Zufriedenheit allein würde die zentralen Vertrauensprobleme nicht zuverlässig erfassen.

## Relevante Codebereiche

- `templates/index.html`: Frage, Composer, Legende, Ergebnisaktionen und Detailflächen.
- `static/js/consensus-insights.js`: Markierungen, Nenner, Popover, Score, Differences und Resolve.
- `static/js/consensus-run.js`: Gesprächsfortsetzung und historische Turns.
- `static/js/run-view.js`, `query-send.js`: Sichtwechsel, Hintergrundläufe und Fehlerzustände.
- `static/js/model-picker.js`, `app-init.js`, `agent-mode.js`: Modellauswahl und Ergebnisdarstellung.
- `static/js/composer-quote.js`, `memory-edit.js`: Auswahlaktionen und Zitatkontext.
- `static/js/composer-collapse.js`: mobiler Composer.
- `static/js/sources.js`: externe Quellen und Zitationsverweise.
- `static/demo.js`: Demo-Inhalte und deren Zusammenspiel mit dem aktuellen Modellprofil.

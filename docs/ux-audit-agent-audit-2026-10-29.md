# UX-Audit Audit-Modus auf Apple-Niveau (2026-10-29)

Vier Prüfer haben den Agent-Audit-Modus mit echtem App-Code in simulierten Läufen durchgespielt (Frage, Denken, Befehle, Antwort, Marken, Karten, Arbeitsplatz; hell/dunkel, 1280/390/320 px, Deutsch/Englisch; 618 Screenshots, gemessen per `getBoundingClientRect`/`getComputedStyle`). Stand `main` 2e1c1a05 = Prod, nichts geändert. Entscheidungsseite mit Screenshots: https://claude.ai/artifact/HLaPHqwm8VsAmJ4mR3d38Q (Max entscheidet je Paket Ja/Später/Nein). Die Sonden (untracked e2e-Tests) lagen im Scratchpad der Session.

**98 Befunde** in 10 Paketen, 13 sofort sichtbar. Schwere: 1 sofort sichtbar, 2 zweiter Blick, 3 Feinschliff. Aufwand: S Minuten bis 1 h, M einige Stunden, L ein Tag oder mehr.

## Ursachen

- **Kein Abstandsraster.** Die Audit-Stylesheets nutzen 63 verschiedene Abstände, nur 47 % liegen auf einem 4-px-Raster. Für Radien, Kurven und Dauern gibt es Tokens, für Abstände keine. Daher die Lücken unter der Antwort, die als Summen entstehen.
- **Zwei Kartenfamilien.** Die Prüfer-, Domain- und Gate-Karten stammen vom 27.10., die Fragen des Agenten aus dem Design-Pass vom 29.10. Die älteren haben das neue Raster nie bekommen.
- **Eine Leiste, dreimal gebaut.** Nur-Quellen, Prüfung/Vergleich und Watch/Teilen sind drei verschiedene Bauteile. Darum steht auf dem Handy mal alles in einer Zeile und mal „Quellen“ allein.
- **Daten, wie sie ankommen.** Exit-Codes, Adressen, interne Namen, JSON und Minutenzeiten gehen ohne Übersetzung in Sätze auf den Bildschirm.
- **Kein gemeinsames Wörterbuch.** Die Prüfer heißen viermal anders, Pause und Schlussrunde dreimal. Jede Stelle formuliert selbst, daher auch falsche Sätze wie „stoppt“, wo es weitergeht.
- **Alte Regeln für neues Denken.** Eine Zeile vom 20.09. ersetzt das Denken durch Notizen, und eine Überschriften-Regel aus der Zeit vor Terra wirft alle Sätze unter einer Überschrift weg.

## Schon auf Apple-Niveau

- Kein seitliches Scrollen in 51 gemessenen Fällen (390/360/320 px, quer, hell/dunkel, Deutsch/Englisch).
- Alle gemessenen Texte bestehen AA in beiden Themes, auch Marken und Fokusring.
- Reduce Motion wirkt überall: Leser und Marken blenden nur noch, nichts fährt.
- Die Uhr tickt in einem Feld fester Breite; Pfeil und Logos stehen beim Ticken still.
- Die Fragen des Agenten (Erlauben, Browser, Übergabe) halten das Apple-Raster: Glyphe im getönten Kreis, ein Knopf, ein Link, Frist erst in den letzten fünf Minuten.
- Lesetypografie der Antwort: 17 px, Zeilenlänge 66 Zeichen, Tabellen mit Haarlinien.
- Marken färben nur die strittigen Worte, im Dunkeln Ton in Ton.
- Dialoge holen den Fokus hinein, Escape gibt ihn an den Auslöser zurück.
- Ein zweiter Halt auf der offenen Karte tauscht nur die Gründe; deine getippte Antwort bleibt stehen.
- Kein iOS-Zoom: jedes Feld hat am Handy 16 px.

## Paket A · Das Denken bleibt sichtbar

Was der Agent denkt, ist das, was Prüfer und du nachvollziehen wollen. Heute verschwindet es ganz, sobald er einmal eine Notiz schreibt, und bei Terra bleiben vom Denken nur die Überschriften. Dazu spricht die Spur in fünf Schriftgrößen, der Plan steht dreimal da, und Browser-Schritte zeigen rohe Adressen.

Empfehlung: Ja, zuerst – das Herz des Audit-Modus · Aufwand: etwa 1 Session

### A1 · Denk-Auszüge verschwinden, sobald der Agent eine Notiz schreibt

*sofort sichtbar · Agent arbeitet · Desktop und Handy · Aufwand S · sicher · Prüfer Lauf (R1)*

- **Was man sieht:** Während der Agent sucht und rechnet, stehen in der aufgeklappten Aktivität seine Gedanken („Clarifying the question“, „Checking the numbers“, „Verifying the subsidy“). Sobald er einmal einen Satz zu seiner Arbeit schreibt („The calculation is done …“), sind alle Gedanken weg – live und auch nach dem Lauf. Die fertige Zeitleiste zeigt nur noch Werkzeugschritte.
- **Apple-Maßstab:** Was einmal gezeigt wurde, darf nicht still verschwinden, schon gar nicht der Teil, um den es Max beim Nachdenken geht.
- **Fix:** Reasoning nie global ausfiltern: `reasoning` immer aus den Ereignissen nehmen und Notizen als zusätzliche Einträge in Zeitfolge führen; höchstens das Reasoning desselben Schritts weglassen, wenn dessen Notiz es wörtlich wiederholt. Test in test_agent_chat_frontend um einen Lauf mit Notiz ergänzen.
- **Beleg:** Sonde: rt4-vm-many-open (vor der Notiz) hat 3 Einträge .agent-activity-reasoning (y 248.8/408/517.4); r11-done-open (nach der Notiz, gleicher Lauf) hat 0 von 15 Einträgen. Ursache static/js/agent-activity.js:867 `const reasoning = progress.length ? [] : …` – jeder `progress`-Eintrag (Notiz `completion:N/note` aus app/services/agent_delegation.py:2691, aber auch Gate-, Retry- und Rate-Limit-Zeilen 2132/2520/2523/2937) blendet sämtliches Reasoning aus. Die Regel stammt aus 22265896 (20.09.), als `progress` noch Ersatz-Zusammenfassungen waren.

### A2 · Aufgeklapptes Denken zeigt nur Überschriften

*sofort sichtbar · Agent arbeitet · Desktop und Handy · Aufwand M · sicher · Prüfer Lauf (R2)*

- **Was man sieht:** Aus mehreren Absätzen Nachdenken des Standardmodells bleiben Zwei-Wort-Titel: „Clarifying the question / Planning the research“, „Checking the numbers“, „Verifying the subsidy“. Auch aufgeklappt gibt es keinen einzigen Satz, der sagt, was der Agent eigentlich überlegt hat. Bei Claude-artigem Denken bleibt pro Schritt ein einziger Satz, frühere Sätze sind beim Aufklappen weg.
- **Apple-Maßstab:** Ein Aufklapper, der nach dem Öffnen kaum mehr zeigt als zu, verspricht Inhalt, den er nicht hält.
- **Fix:** Live: Überschrift plus erster Satz ihres Abschnitts („Checking the numbers – The search found 11.8 ct/kWh …“). Gespeichert: die Zusammenfassung bis ca. 4.000 Zeichen je Schritt; aufgeklappt als Absätze unter der Überschrift in --font-size-ui, wie ChatGPT/Claude „Thought for …“ öffnen.
- **Beleg:** Sonde speist realistische OpenAI-Zusammenfassungen (Überschrift + 2–3 Sätze, 350–600 Zeichen je Schritt) durch app/services/agent_progress.py ReasoningProgress: Ergebnis je Schritt 18–45 Zeichen („Clarifying the question\nPlanning the research“, „Checking the numbers“ …). Ursache agent_progress.py:215–219: eine passende Überschrift setzt `sectioned`, alle Sätze darunter werden übersprungen; zusätzlich 400-Zeichen-Sperre zwischen Updates (Zeile 178), sodass „Choosing the efficiency“ nie ankommt. Gespeichert wird nur dieser letzte Kurztext (docs/agent-mode.md:2470). Claude-Text: von 6 Sätzen kommen 2 an, die Historie zeigt 1 (p2-excerpt-frames.json, p2-excerpt-open).

### A3 · Fünf Schriftgrößen in einer Spur, Nebensache größer als Schritt

*Feinschliff · Agent arbeitet · Desktop und Handy · Aufwand S · wahrscheinlich · Prüfer Lauf (R21)*

- **Was man sieht:** In den Live-Zeilen sind die Denk-Sätze und Notizen größer als die Schritte („Plan · 2 of 4 done“, „5 earlier steps“, Befehle); dazu kleinere Schreibmaschinen- und Metaschrift. Alles im selben Grau, die Ebenen unterscheiden sich nur um 1 px.
- **Apple-Maßstab:** Ruhige Typohierarchie heißt wenige, klar verschiedene Stufen; hier konkurrieren 14/13/12/11,7 px.
- **Fix:** Zwei Stufen: Spur einheitlich `--font-size-ui` (13 px, lh 1.6) für Gedanken, Notizen und Schritte; Code/Ausgabe 12 px mono. Gewicht 500 nur für die laufende Zeile.
- **Beleg:** rt5-note-1280: Notiz 14 px/24.5, Plan/Fold/Schritt 13 px/21.45, Ausgabe 12 px/18.6 mono, Befehl 11.7 px mono, Meta 12 px; alle rgb(94,94,94). static/css/agent-chat.css:765, 768–770, 776–777, 841–848, 873–876.

### A4 · Abstände in der Spur ohne gemeinsames Raster

*Feinschliff · Agent arbeitet · Desktop und Handy · Aufwand S · wahrscheinlich · Prüfer Lauf (R22)*

- **Was man sieht:** Zwischen den Live-Zeilen und in der Zeitleiste wechseln die Abstände leicht, ohne dass man sagen kann warum.
- **Apple-Maßstab:** Ein Raster aus wenigen Abständen trägt die Ruhe; hier sind es sieben Werte.
- **Fix:** Auf 8/16 px vereinheitlichen (Spur-Einträge 16, innen 8, Live-Block oben 0/unten 24 über einen Token `--trace-gap`).
- **Beleg:** static/css/agent-chat.css: Absätze 14 px (770), Schritte/Befehle/Plan/Fold 16 px (777, 829, 884, 935), Live-Block −8 px/24 px (768), Zeitleiste 14 px (726), Prüferrunden 12 px (152), Notizen 10 px (168), Ausgabe 6 px (873). Gemessen rt5: Plan→Fold 16 px, Befehl→Notiz 16 px, Notiz→Status 14 px.

### A5 · Der Plan steht dreimal in der Zeitleiste

*zweiter Blick · Agent arbeitet · Desktop und Handy · Aufwand S · sicher · Prüfer Lauf (R9)*

- **Was man sieht:** In der fertigen Zeitleiste stehen „Plan · 1 of 4 done“, „Plan · 2 of 4 done“, „Plan · 3 of 4 done“ als drei eigene Punkte zwischen den Schritten.
- **Apple-Maßstab:** Zwischenstände einer Checkliste sind Rauschen; der Verlauf soll erzählen, nicht protokollieren.
- **Fix:** In der Zeitleiste nur den letzten Planstand zeigen (an der Stelle des ersten, mit allen Haken), frühere Planstände weglassen; live bleibt er angepinnt.
- **Beleg:** r11-done-open-1280: 3 von 15 Zeitleisten-Einträgen sind `.agent-plan` (y 309.6, 522.2, 776.9). static/js/agent-activity.js:1057 baut für jedes `update_plan` einen eigenen Eintrag.

### A6 · Prüfungs-Eintrag sagt alles zweimal

*Feinschliff · Antwort & Prüfung · Desktop und Handy · Aufwand S · sicher · Prüfer Lauf (R18)*

- **Was man sieht:** In der Zeitleiste: „Prüfung · Antwort wird geprüft…“, danach „Prüfung · 3 Modelle“ und darunter noch einmal „Modelle: GPT-6 Luna, Claude Haiku 5.5, DeepSeek V4.1 Flash“.
- **Apple-Maßstab:** Etikett-Doppelpunkt-Liste und doppelte Wörter lesen sich wie ein Formular.
- **Fix:** Eine Zeile: „3 KIs haben geprüft: GPT-6 Luna, Claude Haiku 5.5, DeepSeek V4.1 Flash“ (laufend: „3 KIs prüfen die Antwort…“), darunter das Ergebnis.
- **Beleg:** p2-history-vm-open-de / r11-done-open-390-light-de. static/js/agent-review.js:706–709 (`'Review · Reviewing the answer…'`, `Models: ${names}`).

### A7 · Gelesene Quelle als Text, gesuchte Quellen als Pillen

*Feinschliff · Agent arbeitet · Desktop und Handy · Aufwand S · sicher · Prüfer Lauf (R23)*

- **Was man sieht:** „Searched the web“ zeigt darunter anklickbare Quellen-Pillen mit Logo; „Read source · bdew.de“ ist nur grauer Text, obwohl es die eine Seite ist, die der Agent wirklich gelesen hat.
- **Apple-Maßstab:** Gleiches sieht gleich aus; die gelesene Quelle ist die wichtigere und verdient denselben Baustein.
- **Fix:** read_source mit `url` ausliefern und als eine `.src-ref`-Pille unter „Read source“ zeigen.
- **Beleg:** r11-done-open-1280: „Read source · bdew.de“ 21.4 px Textzeile, Suchen 46.8 px mit .src-ref. static/js/agent-activity.js:470–475 und 1079–1100: Pillen nur aus `item.sources`, read_source trägt nur `host`.

### A8 · Suchbegriff auf der Seite in Code-Schrift ohne Anführungszeichen

*Feinschliff · Agent arbeitet · Desktop und Handy · Aufwand S · sicher · Prüfer Lauf (R24)*

- **Was man sieht:** „Sucht auf der Seite nach Förderfähige Kosten“ – der Begriff steht in kleiner Schreibmaschinenschrift und ohne Anführungszeichen, der Satz liest sich grammatisch falsch.
- **Apple-Maßstab:** Nutzertext statt Terminal: ein Suchbegriff ist ein Zitat.
- **Fix:** Für `find` (und `type`) das Ziel in Textschrift mit typografischen Anführungszeichen („…“ bzw. “…”) setzen; Mono nur für Befehle, Pfade, Code.
- **Beleg:** rt6-browser-1280-light-de, p2-history-browser-open. static/js/agent-activity.js:527 (`find` → `item.query` ins `<code>`-Ziel), Mono-Stil static/css/agent-chat.css:841–845.

### A9 · Browser-Schritt zeigt die rohe Adresse statt des Seitentitels

*zweiter Blick · Agent arbeitet · Desktop und Handy · Aufwand S · sicher · Prüfer Lauf (R8)*

- **Was man sieht:** „Opened https://www.kfw.de/inlandsfoerderung/Heizungsfoerderung/“ bzw. „Geöffnet https://…“ in Schreibmaschinenschrift, obwohl die Seite „Heizungsförderung für Privatpersonen | KfW“ heißt und das bekannt ist.
- **Apple-Maßstab:** Kein Rohtext für Nutzer; Safari zeigt Titel und Domain, nicht den Pfad.
- **Fix:** Für `open` den Titel in Textschrift zeigen, Domain leise dahinter („Opened Heizungsförderung für Privatpersonen · kfw.de“); URL als `title`-Tooltip/Link.
- **Beleg:** p2-history-browser-open-en / r11: Kopf „Opened https://www.kfw.de/…“ in --font-mono. static/js/agent-activity.js:525 nimmt `item.url || … || item.title`, obwohl app/services/agent_browser.py:593–596 `title` liefert.

## Paket B · Unter der Antwort: eine Leiste, ein Raster

Die Knöpfe unter der Antwort werden an drei Stellen verschieden gebaut. Auf dem Handy steht „Quellen“ allein in der Mitte und Watch und Teilen kleben an den Rändern, mit offener Leiste bricht der Fuß in zwei Zeilen, während der Prüfung springt er, und dieselben Befunde zählen dreimal anders. Abstände zwischen Antwort, Leiste und nächster Frage folgen keinem Raster.

Empfehlung: Ja – das hast du selbst bemerkt · Aufwand: etwa 1 Session

### B1 · Handy: „Quellen“ steht allein in der Mitte, Watch und Teilen eine Zeile tiefer an den Rändern

*sofort sichtbar · Handy · Handy · Aufwand S · sicher · Prüfer Antwort (A1)*

- **Was man sieht:** Unter einer Agent-Antwort ohne Vergleich oder Prüfung (nur Quellen) steht auf dem Handy „Quellen 3“ einsam mittig in einer eigenen Zeile. Darunter klebt „Watch“ ganz links und „Teilen“ ganz rechts, dazwischen 260 px Leere. Unter einer geprüften Antwort ist es dagegen eine saubere Werkzeugzeile.
- **Apple-Maßstab:** Dieselbe Werkzeugleiste hat je nach Antwortart zwei verschiedene Formen, eine davon sieht kaputt aus.
- **Fix:** Die Nur-Quellen-Leiste wie die Prüf-Leiste bauen: nav mit 'consensus-footer-tabs agent-evidence-links agent-evidence-grid' (agent-review.js:817), dann gelten dieselben Zellen 44×56 px (Glyphe 16 px über Wort, 5 px Abstand) und eine Zeile von Kante zu Kante. Zusätzlich die globale Regel aus shell.css:1894 auf .run-provenance begrenzen, damit kein Agent-Link mehr 100 % breit wird.
- **Beleg:** 390 px: Quellen-Zelle 348×44 px ab x=16, Glyphe bei x=149 (zentriert); Watch 44×56 bei x=16, Teilen 44×56 bei x=320, beide 44 px tiefer (y 2017,7 statt 1973,7), Abstand 260 px (measure-answer/noaudit-plain-390.json). Ursache: agent-review.js:817 baut die Nur-Quellen-Leiste ohne Klasse agent-evidence-grid, deshalb greifen die Handy-Regeln agent-chat.css:615-626 nicht; stattdessen macht shell.css:1885-1905 (@media max-width 640px, shell.css:1825) jede .consensus-tab 100 % breit. Watch/Teilen hängen als zweites Kind von .agent-review (components-watch.css:1016-1023).

### B2 · Desktop mit offener Agent-Leiste: der Antwortfuß bricht in zwei Zeilen

*sofort sichtbar · Antwort & Prüfung · Desktop · Aufwand S · sicher · Prüfer Antwort (A2)*

- **Was man sieht:** Bei einer Agent-Antwort mit Vergleich (Score, Widersprüche, Antworten, Quellen, Watch, Teilen) und offener Agent-Leiste rechts rutscht „Share“ allein in eine zweite Zeile. Auf Deutsch rutschen sogar „Watch“ und „Teilen“ nach unten.
- **Apple-Maßstab:** Ein Ergebnisfuß in zwei Zeilen wirkt zufällig umgebrochen; Max hat genau das (B6, 2026-10-02) abgelehnt.
- **Fix:** Antwortspalte als Container abfragen (container-type auf .agent-answer) und unter ~720 px Spaltenbreite das Score-Element wie auf dem Handy in eine eigene Zeile über die Links setzen (agent-chat.css:616-Regel als @container). Ergebnis: eine Linkzeile mit 12 px Box-Abstand, 28 px Glyph-zu-Glyph, auch auf Deutsch. Prüfen mit offener und geschlossener Agent-Leiste.
- **Beleg:** 1280 px, Spalte 626 px: erste Zeile 58/100 · Contradictions 1 · Answers 3 · Sources 3 · Watch (bis x=862), Share bei x=279, y+36 px; Leiste 72 px statt 36 px hoch. Deutsch: Watch x=279 und Teilen x=364 in Zeile 2 (b-comparison-1280-en/de.json). Platzbedarf ≈ 665 px (EN) bzw. ≈ 710 px (DE) > 626 px. Ursache: .agent-review { flex-wrap: wrap } agent-chat.css:568; Agent-Leiste seit 2026-10-28 ab 1200 px standardmäßig offen.

### B3 · Während der Prüfung steht „Quellen 2“ über „Antwort wird geprüft…“ – danach springt die Leiste

*zweiter Blick · Antwort & Prüfung · Desktop und Handy · Aufwand M · sicher · Prüfer Antwort (A3)*

- **Was man sieht:** Solange die Prüfer arbeiten, steht unter der Antwort schon „Quellen 2“ und erst darunter „Antwort wird geprüft…“. Wenn die Prüfung fertig ist, verschwindet die Statuszeile, vorne erscheint „Anmerkungen“, „Quellen“ rückt nach rechts und zählt plötzlich 3. Auf dem Handy wechselt „Quellen“ von mittig in voller Breite auf eine Zelle unter vier.
- **Apple-Maßstab:** Was schon sichtbar ist, darf sich nicht verschieben; die Statuszeile sollte den Platz der fertigen Leiste halten, nicht unter einer zweiten Leiste stehen.
- **Fix:** Im Audit-Modus während der Prüfung keine Nur-Quellen-Leiste bauen; stattdessen die fertige Leiste als ruhigen Platzhalter zeigen: „Anmerkungen“ ausgegraut (ink-3, ohne Zahl) mit „wird geprüft…“ daneben, Quellen schon an ihrer endgültigen Stelle mit der Zahl aus der Aktivität. Höhe auf dem Handy 56 px (nicht 92), Desktop 36 px. Dann tauscht beim Ende nur ein Wort.
- **Beleg:** 1280: während der Prüfung Sources-Zeile 36 px bei y=1447,9, x=279, darunter Statuszeile 36 px + 18 px Rand bei y=1501,9; fertig: Sources bei x=383,4 (+104 px), Zählung 2→3, Statuszeile weg (−54 px). 390: Sources 348×44 (zentriert), Statuszeile 92 px hoch; fertig Zelle 47×56 bei x=116 (b-running-1280-en.json, b-running-390-en.json). Ursache: agent-chat.js:893-894 rendert während des Laufs ohne Review (live ? null) und ohne Aktivitätsquellen (events: []), agent-review.js:806-821 baut dann die Nur-Quellen-Leiste direkt hinter die Antwort (agent-review.js:809), vor die Statuszeile aus agent-chat.js:667. Die 92 px der Statuszeile (agent-chat.css:1048) sind für Score + Links gedacht, Audit hat keinen Score.

### B4 · „Keine Einwände“ heißt unter der Antwort „Anmerkungen 0“

*zweiter Blick · Antwort & Prüfung · Desktop und Handy · Aufwand S · sicher · Prüfer Antwort (A4)*

- **Was man sieht:** Haben alle Prüfer nichts auszusetzen, steht unter der Antwort nur „Anmerkungen 0“. Dass das ein gutes Ergebnis ist, erfährt man erst, wenn man den Leser öffnet: dreimal „Keine Einwände.“. Dasselbe „0“ steht auch, wenn die Prüfung komplett fehlschlug.
- **Apple-Maßstab:** Eine Null beschriftet Abwesenheit (Max' Regel seit „Sources 0“), und das beste Ergebnis der Prüfung bleibt stumm.
- **Fix:** Zahl 0 als null übergeben. Bei erfolgreicher Prüfung ohne Marken das Wort selbst sprechen lassen: Zelle „Keine Einwände“ mit Haken-Glyphe in ink-2 (öffnet weiter den Leser). Bei Fehlschlag nur „Anmerkungen“ ohne Zahl.
- **Beleg:** Zustand „keine Einwände“: Zellen „Notes 0“ (84,6×36 px) · „Sources 3“ (state-noobjections-1280-en.json, -390-de.json); Zustand „fehlgeschlagen“: „Notes 0“ unter „The review could not be completed“ (state-failed-1280-en.json); Folgefrage ohne Marken ebenfalls „Notes 0“ (H-followup-1280-light-en.png). Ursache: agent-review.js:781-782 übergibt die Zahl immer, evidenceButton zeigt sie, sobald sie nicht null ist (agent-review.js:357, 370).

### B5 · Drei verschiedene Zahlen für dieselben Befunde

*zweiter Blick · Antwort & Prüfung · Desktop und Handy · Aufwand S · sicher · Prüfer Antwort (A5)*

- **Was man sieht:** Im Text sind 6 Stellen markiert, die Aktivität sagt „9 markierte Stellen · 2 Anmerkungen zur Arbeit“, die Leiste sagt „Anmerkungen 11“. Bei teilweiser Prüfung: Aktivität „6 marked passages“, Leiste „Notes 8“.
- **Apple-Maßstab:** Wer Zahlen nachzählt und sie nicht findet, misstraut der ganzen Prüfung.
- **Fix:** Eine Zählung für alle Orte: Leiste „Anmerkungen 11“, Aktivität „11 Anmerkungen: 6 Stellen im Text, 3 weitere, 2 zur Arbeit“ – oder in der Aktivität ganz ohne Zahlen. „Markiert“ nur für Stellen, die im Text farbig sind.
- **Beleg:** Fixture mit 7 Marken auf 6 Sätzen, 2 nicht platzierten, 2 zur Arbeit: 6 .is-audit-Sätze (marks in audit-1280-light-en.json), Aktivität „9 marked passages · 2 notes on the work“ (A-audit-activity-1280-light-en.png), Leiste „Notes 11“. Ursache: renderAuditActivity zählt auditMarks inklusive „unplaced“ als „markierte Stellen“ (agent-review.js:696, 712-713), die Leiste zählt Marken + Arbeit (agent-review.js:781).

### B6 · Alte Turns zeigen keine Prüfer-Logos neben „Fertig nach“

*zweiter Blick · Verlauf & Weiterfragen · Desktop und Handy · Aufwand S · sicher · Prüfer Antwort (A10)*

- **Was man sieht:** In der aktuellen Antwort stehen neben „Thought for 1m 52s“ die drei Prüfer-Logos und das Leisten-Symbol. Sobald die Antwort in den Verlauf rutscht oder der Chat neu geöffnet wird, steht nur noch „Thought for 1m 52s“.
- **Apple-Maßstab:** Was der Live-Turn kann, sollte der Verlauf nicht verlieren (Max, 2026-08-06 und 2026-10-18).
- **Fix:** In renderAudit für .thread-history-answer-body denselben Logo-Stapel aus review.audit.reviewers bauen und in die Aktivitätszeile hängen (Logos 15 px, einfarbig, Farbe bei Hover, wie live).
- **Beleg:** Gespeicherter Chat mit 3 Audit-Turns: Verlaufs-Zusammenfassungen logos 0, live 6 Bildknoten (3 Marken) (saved-1280-light-en.json history_activity, activity). Ursache: renderAudit entfernt _agentModels (agent-review.js:757) und baut sie nicht neu; nur der Vergleichspfad setzt .agent-history-models neben die Aktivitätszeile (agent-review.js:1004-1031).

### B7 · Handy: zwei Knöpfe werden an die äußersten Ränder gespreizt

*zweiter Blick · Handy · Handy · Aufwand S · sicher · Prüfer Antwort (A11)*

- **Was man sieht:** Bei einer gestoppten Antwort gibt es nur „Anmerkungen“ und „Quellen“. Sie stehen ganz links und ganz rechts, 300 px auseinander, als gehörten sie nicht zusammen.
- **Apple-Maßstab:** Gleichmäßig verteilt wirkt nur mit vier oder fünf Zellen; zwei Zellen brauchen eine feste Position.
- **Fix:** Raster mit festen Spalten statt space-between: grid-template-columns repeat(4, 1fr) bzw. repeat(5, 1fr), jede Zelle an ihrer Stelle, links beginnend; oder space-between nur mit :has(> :nth-child(4)).
- **Beleg:** 390 px, gestoppt ohne Antwort: Notes bei x=16, Sources rechts bündig bis x=364 (S-stopped_early-390-en.png; Leiste ohne Watch/Teilen, weil der Turn als failed gespeichert ist). Ursache: .agent-review { justify-content: space-between } für jede Zellenzahl (agent-chat.css:615).

### B8 · Gestoppt ohne Antwort: Grund und „Erneut“ stehen unter der Leiste

*zweiter Blick · Antwort & Prüfung · Desktop und Handy · Aufwand S · sicher · Prüfer Antwort (A12)*

- **Was man sieht:** Nach einem Stopp vor der Antwort kommt unter „Stopped after 1m 52s“ zuerst eine Lücke, dann „• Review stopped“, dann „Notes · Sources“ und erst danach „Response stopped. Available results have been saved.“ mit schwarzem „Retry“.
- **Apple-Maßstab:** Das Wichtigste – was passiert ist und was ich tun kann – gehört nach oben, die Belege danach.
- **Fix:** Bei leerem Antworttext: Meldung + Retry direkt unter der Aktivität (16 px), Leiste darunter ohne eigene Statuszeile; Text „Gestoppt. Die Prüfer hatten bis dahin 4 Anmerkungen.“ statt zweier Stopp-Sätze.
- **Beleg:** Reihenfolge (y): Aktivität 179–233, Prüfstatus 251, Leiste 272–308, Fehlermeldung 321, Retry 354 (b-stopped-stopped_early.json order). Leerer Antwortkörper behält 18 px Abstand unter der Aktivität (agent-chat.css:689). Status „Review stopped“ und Meldung „Response stopped…“ sagen dasselbe zweimal (agent-review.js:637, agent_runs.py:545).

### B9 · Die Glyphen der Leiste stehen 8 px rechts der Textkante

*Feinschliff · Antwort & Prüfung · Desktop · Aufwand S · sicher · Prüfer Antwort (A22)*

- **Was man sieht:** „Weitere Anmerkungen“ und der Antworttext beginnen an derselben Kante, das erste Symbol der Leiste ein Stück weiter rechts. Unter einer Antwort ohne Prüfzeile beginnt Watch dagegen bündig.
- **Apple-Maßstab:** Eine Antwort hat eine linke Kante; alles darunter richtet sich danach.
- **Fix:** agent-chat.css:574 margin-left: -8px (die Innenluft des Links nach außen), dann sitzt die Glyphe auf x=279 wie der Text; Watch/Teilen ohne Review-Zeile unverändert.
- **Beleg:** Text/„Other notes“ x=279, Glyphe „Notes“ x=287 (rowLeftVsText ink −17,5 px gegen die eingerückte Liste, +8 px gegen die Textkante; audit-1280-light-en.json). .agent-evidence-links { margin-left: -8px } (agent-chat.css:601) wird von .agent-review > .agent-evidence-links { margin-left: 0 } (agent-chat.css:574) aufgehoben; .agent-watch-pill-row behält -8px (components-watch.css:1007).

### B10 · „Anmerkungen“ trägt das Symbol für Widersprüche

*Feinschliff · Antwort & Prüfung · Desktop und Handy · Aufwand S · sicher · Prüfer Antwort (A24)*

- **Was man sieht:** Vor „Anmerkungen“ steht dieselbe Gabel, die im Vergleichsmodus „Widersprüche“ bedeutet.
- **Apple-Maßstab:** Ein Symbol, zwei Bedeutungen; die Prüfer widersprechen nicht einander, sie kommentieren.
- **Fix:** Eigenes Glyph für Audit-Anmerkungen (Sprechblase mit Linie oder Stift am Rand) über einen Schlüssel 'notes' im Pfad-Objekt; section bleibt 'differences'.
- **Beleg:** evidenceButton wählt das Glyph nach section 'differences' (agent-review.js:363-367), Audit nutzt dieselbe section mit Label „Notes“ (agent-review.js:782, auditContext labels :683).

### B11 · Gesprächsrhythmus aus acht Einzelwerten

*Feinschliff · Verlauf & Weiterfragen · Desktop und Handy · Aufwand M · wahrscheinlich · Prüfer Antwort (A25)*

- **Was man sieht:** Zwischen Frage und „Thought for“ sind 56 px, zwischen Leiste und nächster Frage 74 px. Die Antwort sitzt dadurch kaum näher an ihrer Frage als an der nächsten.
- **Apple-Maßstab:** Ein Raster aus wenigen Werten macht Zugehörigkeit lesbar; hier summieren sich 18+16+22 und 8+22+34+10.
- **Fix:** Abstandsstufen 4/8/12/16/24/32/48 als Tokens; Frage→Aktivität 24, Aktivität→Text 12, Text→Leiste 16, Leiste→nächste Frage 48. Live und Verlauf aus denselben Tokens.
- **Beleg:** Verlauf 1280: Frage-Blase unten 1707,1 → Aktivität 1763,1 (56 px); Leiste unten 2039 → nächste Frage 2113 (74 px) (saved-1280-light-en.json history). Werte: .thread-ask 10/18 (shell.css:2253-2258), Antwort-Rand 16 (shell.css:2558-2560), .agent-answer padding 22 (agent-chat.css:340), .agent-activity 18 (agent-chat.css:689), .agent-review 18/8 (agent-chat.css:568), .thread-history-turn 34 (shell.css:2501-2506). foundation.css kennt Radien und Dauern, aber keine Abstände.

### B12 · Compare-Antworten sprechen eine andere Fußsprache als Agent-Antworten

*zweiter Blick · Antwort & Prüfung · Desktop und Handy · Aufwand M · sicher · Prüfer Antwort (A27)*

- **Was man sieht:** Unter jeder Compare-Antwort steht ein Ausklapper „Sources · 1“ mit Pfeil rechts außen – kein Symbol, kein Watch, kein Teilen. Auch die Schrift ist kleiner (16 statt 17 px), Zwischenüberschriften fast textgroß.
- **Apple-Maßstab:** Dieselbe Rolle (eine Antwort und ihre Belege) braucht dasselbe Bauteil.
- **Fix:** Compare-Antworten mit derselben Leiste wie Agent abschließen (Glyphe + Wort: Quellen n, Kopieren), Typo-Tokens der Antwort (17 px/1.7, H3 1.125em) übernehmen; Ausklapper entfällt, Quellen öffnen den Leser.
- **Beleg:** Compare 1280: Antwort 16 px/28, H3 17 px; Fuß details.answer-reader-sources 48 px hoch, 18,4 px unter dem Text, 13 px (compare-1280.json); Agent: 17 px/28,9, H3 19,1 px, Glyphen-Leiste 36 px. Typo model-answer-reader.css:147-151, Fuß :164-167, keine Aktionen im Direktmodus (model-answer-reader.js:591).

### B13 · Dateifehler als grauer Kasten mit Rohtext unter jeder Antwort

*Feinschliff · Antwort & Prüfung · Desktop und Handy · Aufwand S · wahrscheinlich · Prüfer Antwort (A28)*

- **Was man sieht:** Kann die Dateiliste des Chats nicht laden, steht unter der Leiste ein grauer Kasten „Couldn’t load this chat’s files. Authentication failed“ mit gerahmtem „Retry“ – auch unter Antworten, die gar keine Dateien haben.
- **Apple-Maßstab:** Ein getönter Kasten in der rahmenlosen Seite liest sich wie ein Fehlerbanner, und „Authentication failed“ ist kein Alltagssatz.
- **Fix:** Nur zeigen, wenn der Turn eigene Dateien hat (turnInfo.fileIds), und dann als leise Zeile ohne Fläche in ink-3: „Dateien konnten nicht laden · Erneut versuchen“ (unterstrichener Link).
- **Beleg:** Kasten 626×56 px (Handy 348×64), 16 px unter der Leiste (audit-1280-light-en.json after #agentAnswerResources); entstand im ersten Lauf ohne Datei-Attrappe. agent-workspace.js:587-592 zeigt ihn bei jedem error, obwohl der Kommentar sagt „only when this answer's own files are missing“; Fläche/Rahmen agent-workspace.css:214-219, :123.

### B14 · Deutsch: doppelte Lücke in „Fertig nach  1 Min. 52 Sek.“

*Feinschliff · Antwort & Prüfung · Desktop und Handy · Aufwand S · sicher · Prüfer Antwort (A26, auch R19)*

- **Was man sieht:** Zwischen „Fertig nach“ und der Zeit steht auf Deutsch eine sichtbar größere Lücke als im Englischen.
- **Apple-Maßstab:** Ein Wortabstand ist ein Wortabstand.
- **Fix:** Nach dem Lauf den Platzhalter (data-ghost) entfernen, wenn die Zeit eingefroren ist; während des Laufs die Zeit rechtsbündig im Verb-Feld ausrichten.
- **Beleg:** Abstand Verb→Zeit DE 9,2 px, EN 3,5 px; das unsichtbare Platzhalter-Verb ist englisch „Working for“ bzw. übersetzt „Arbeitet seit“ (75,6 px) gegen „Fertig nach“ (69,9 px) (b-audit-1280-de-open.json, b-audit-390-de--.json title). agent-activity.js:180-182, agent-chat.css:708-710. — Auch gefunden als R19 („„Fertig nach  2 Min.“ mit doppelter Lücke“): p2-meta-de.json: Verbfeld 73.5 px (Breite des Geists „Arbeitet seit“), Text „Fertig nach“ 69.6 px → 3.9 px + 3.9 px Leerzeichen = 7.8 px Lücke; EN 73.3/73.3 px, keine Lücke. static/css/agent-chat.css:708–710 (`::after content: attr(data-ghost)`).

## Paket C · Karten: eine Familie, eine Hauptaktion

Wenn der Lauf auf dich wartet, muss die Entscheidung in einer Sekunde klar sein. Heute gibt es zwei Kartenfamilien mit eigenem Raster, bis zu drei Links neben dem Knopf, rohes JSON im Beleg, falsche Sätze („stoppt nach 30 Minuten“ bei einer Netzanfrage, die weiterläuft) und auf dem kleinen Handy rutscht die Karte unter die Kopfleiste.

Empfehlung: Ja – hier geht es um Sicherheitsentscheidungen · Aufwand: 1–2 Sessions

### C1 · Beleg eines Agentenschritts als Roh-JSON

*sofort sichtbar · Pausen & Fragen · Desktop und Handy · Aufwand M · sicher · Prüfer Karten (K7)*

- **Was man sieht:** Hält ein Prüfer einen Browser-Klick an, steht im Beleg „browser: {"action": "click", "ref": "e14"}“ – was angeklickt werden sollte, steht nirgends. Bei einer Gedächtnis-Änderung steht „update_memory: {"changes": [{"op": "add", …}]}“ und dazu der Satz „Er wirkt außerhalb des Arbeitsplatzes und läuft nur, wenn du ihn lässt.“, der fürs Gedächtnis gar nicht stimmt.
- **Apple-Maßstab:** Rohdaten mit internen Kennungen an einer Sicherheitsentscheidung; die Doku verspricht „nie Protokoll-JSON“.
- **Fix:** halt_step je Werkzeug in Worten: Browser „Klick auf „Jetzt kaufen – 129 €““ (Beschriftung des Elements aus dem letzten read statt ref), „Tippt „jens@…“ und sendet“; Memory „Merken: „Max reist …““; Befehle bleiben als Code. Label in Aktivitätswörtern („Browser“, „Gedächtnis“), Satz der unchecked-Karte je Werkzeug („Der Agent will sich etwas über dich merken. Das passiert nur mit deinem OK.“).
- **Beleg:** Mit agent_audit.halt_step berechnet: click → 'browser: {"action": "click", "ref": "e14"}', type → '… "enter": true}', update_memory → JSON (gerendert: card-unchecked-*.png). agent_audit.py:669 _CALL_KEYS = command/url/query/path/task/question, kein action/ref/text/changes; agent_audit.py:679 fällt auf json.dumps zurück; Werkzeugname roh („browser:“, „vm_exec:“). Satz fest in agent-chat.js:1718 aus der Zeit, als das Gate Netzaufrufe prüfte (seit 10-29 nur Domain + Memory).

### C2 · Zwei Kartenfamilien mit eigenem Raster

*sofort sichtbar · Pausen & Fragen · Desktop und Handy · Aufwand M · sicher · Prüfer Karten (K3)*

- **Was man sieht:** Die Fragen des Agenten (Erlauben, Browser, Key) haben eine Glyphe im getönten Kreis und alles steht bündig an einer Kante. Die Karten der Prüfer, der Netzzugriff und „nicht jeder Prüfer konnte prüfen“ sehen anders aus: winziges nacktes Symbol, Titel eingerückt, Text darunter wieder links, kleinere Ecken, weniger Luft. Es wirkt wie zwei verschiedene Apps.
- **Apple-Maßstab:** Dieselbe Bauteilart (Entscheidung über dem Feld) braucht ein Raster; hier existieren zwei Generationen nebeneinander.
- **Fix:** holdCard und domainCard auf das askCard-Raster ziehen: .agent-ask-glyph mit Pause (--partial-bg) bzw. Globus, Titel/Grund/Beleg/Knöpfe auf eine Kante, Radius --radius-lg, Meta-Zeile entfällt (Art als erstes Wort der Grundzeile).
- **Beleg:** Ask-Karten: Glyphe 30×30 im Kreis, Radius 16 px, Padding 16/18/16/16, eine Textkante x=337 (1280). Prüfer/Domain/Gate: Symbol 16×16 ohne Fläche, Radius 14 px, Padding 14/16, zwei Kanten (Titel x=319, Grund/Beleg/Knöpfe x=295), extra Meta-Zeile. agent-chat.css:433-452 vs 482-502; agent-chat.js:1763-1824 (domainCard), 1913-1969 (holdCard) vs 1852-1912 (askCard).

### C3 · Zu viele Wege auf einer Karte, doppelt zum Feld

*sofort sichtbar · Pausen & Fragen · Desktop und Handy · Aufwand S · sicher · Prüfer Karten (K4)*

- **Was man sieht:** Die Netzzugriffs-Karte hat einen Knopf und drei unterstrichene Links („Nicht erlauben“, „Dem Agenten schreiben“, „Stoppen“), auf dem Handy in zwei Reihen. Die Prüfer-Karte hat „Stoppen“, obwohl direkt darunter der Stopp-Knopf im Feld ist, und „Dem Agenten schreiben“ öffnet ein zweites Textfeld direkt über dem Eingabefeld – zwei Felder übereinander.
- **Apple-Maßstab:** Eine Entscheidung soll eine Hauptaktion und höchstens eine Alternative haben (eigene Regel aus 438aacdc); doppelte Wege kosten Nachdenken.
- **Fix:** Stop-Links streichen (Stop = Knopf im Feld, wie askCard). „Dem Agenten schreiben“ streichen: das Eingabefeld ist die Antwort (Platzhalter während der Pause „Antworte dem Agenten…“, Senden = steer). Domain: „Für diesen Chat erlauben“ + „Nicht erlauben“. Key: „Speichern“ + „Nicht jetzt“.
- **Beleg:** Domain: 1 .btn + 3 Links (Desktop y=758, Handy zweite Reihe y=720), Prüfer/Gate: 1 + 2, Key: 1 + 2; Regel „ein Knopf + max. ein Link“ (consensio-ask-user, Kommentar agent-chat.js:1833-1838). agent-chat.js:1815-1820, 1960-1965, 1894-1898; holdReply 1974-2026 erzeugt zweites Textfeld (Screenshot card-halt2-d-en-reply).

### C4 · Pausenkarte wächst über den Bildschirm hinaus

*sofort sichtbar · Pausen & Fragen · Handy · Aufwand M · sicher · Prüfer Handy & System (M1, auch K10)*

- **Was man sieht:** Hält ein Prüfer an, steht die Karte über dem Feld und nimmt auf kleinen iPhones fast den ganzen Bildschirm ein. Tippt man „Dem Agenten schreiben“, rutscht die Überschrift unter die Symbole oben (Seitenleiste, Neuer Chat). Bei der Netzzugangs-Karte verschwindet so genau die Adresse, über die man entscheiden soll. Mit offener Tastatur und im Querformat ist der Kopf der Karte ganz weg, und Wischen bringt ihn nicht zurück.
- **Apple-Maßstab:** Ein iOS-Sheet ist nie höher als der freie Platz und scrollt in sich; nie verschwindet der Satz, um den es geht, unter der Statusleiste.
- **Fix:** Unter 1100 px: .agent-hold-card { max-height: calc(100dvh - var(--app-mobile-header-height) - var(--thread-composer-height) - 16px); overflow-y: auto; overscroll-behavior: contain; } und die Aktionszeile per position: sticky; bottom: 0 in der Kartenfarbe halten. Solange das Antwortfeld der Karte offen ist, das Hauptfeld darunter ausblenden: sonst stehen zwei Textfelder übereinander. Den Beleg (pre) dann auf 3 Zeilen begrenzen.
- **Beleg:** Gemessen (Kartenoberkante / Titel, Kopfleiste endet bei 56 px): 320×568 Pause 61,7 px; mit Antwortfeld −10,3 / 3,7 px. Netzzugang 320×568: 0,9 / 14,9 px, mit Antwortfeld −23,1 / −9,1 px. 390×500 (Tastatur, angenähert): 11 px, mit Antwortfeld −13 / 1 px. 568×320 quer: −82 / −68 px. Kein Scrollbereich (scrollers = []), mouse.wheel ändert nichts. Auf 320×568 deckt die Karte 440 von 568 px. Ursache: .agent-hold-card ohne max-height/overflow (static/css/agent-chat.css:433-436), liegt in der fixierten .input-section (static/css/shell.css:2060-2075), die mit Tastatur per translate angehoben wird (shell.css:2210-2213). — Auch gefunden als K10 („Handy mit Tastatur: Karte füllt den ganzen Schirm, Titel weg“): Simuliert 390×508 (844 minus ~336 px Tastatur): Karte 513,8 px hoch, Oberkante y=-71,8 (Titel außerhalb), Antwortfeld y=310–374, Eingabefeld darunter (keyboard-halt2.json). Ursache: Beleg bis 6 Zeilen (agent-chat.css:459) + zwei Gründe + Feld, kein Einklappen beim Schreiben.

### C5 · Wartende Nachrichten laufen am Handy aus dem Bild

*sofort sichtbar · Handy · Handy · Aufwand S · sicher · Prüfer Karten (K30)*

- **Was man sieht:** Schreibe ich am Handy während der Arbeit zwei Nachrichten, ragen die grauen Zeilen über den rechten Bildschirmrand; der Zustand „Wird vor dem nächsten Schritt gelesen“ ist mitten im Wort abgeschnitten („Wird vor dem näch“).
- **Apple-Maßstab:** Inhalt, der aus dem Bildschirm läuft, ist ein sichtbarer Layoutfehler.
- **Fix:** .agent-queue { grid-template-columns: minmax(0, 1fr); }; unter 480 px den Zustand unter den Text setzen.
- **Beleg:** 390×844 DE: #agentQueue 358 px breit, Grid-Spur 501 px, Zustand x=278–506 (137 px über die Kante) (queue-phone-de.json). agent-chat.css:407 .agent-queue { display:grid } ohne grid-template-columns: minmax(0,1fr); der nicht umbrechende Text (agent-chat.css:413) setzt die min-content-Breite der Spur (dieselbe Falle wie im Landing-Mockup, consensio-design-preferences).

### C6 · Key-Karte läuft auf 320 px rechts aus dem Kasten

*sofort sichtbar · Pausen & Fragen · Handy · Aufwand S · sicher · Prüfer Handy & System (M2, auch K9)*

- **Was man sieht:** Fragt der Agent nach einem Key, ragen Titel, Text und Eingabefeld rechts über die graue Karte hinaus. „Nicht jetzt“ und „Dem Agenten schreiben“ brechen Wort für Wort in zwei bis drei Zeilen um und stehen schief nebeneinander.
- **Apple-Maßstab:** Ein Inhalt, der über seinen eigenen Rahmen läuft, ist auf dem iPhone ein sichtbarer Layoutfehler.
- **Fix:** .agent-ask-body { grid-template-columns: minmax(0, 1fr); } und für die Aktionen flex-wrap: wrap mit white-space: nowrap je Knopf (der Link rutscht dann als Ganzes in die nächste Zeile, wie in .agent-hold-actions).
- **Beleg:** 320 px, Deutsch: .agent-ask-body scrollWidth 237 > clientWidth 212, Spalte 237,125px; Titel, Text, Feld enden bei x = 311,1 px, Innenkante der Karte 286 px, Karte endet bei 304 px. Auf 320/EN und auf 360/390 passt es. „Nicht jetzt“ 34,8×48,6 px in 2 Zeilen, „Dem Agenten schreiben“ in 3 Zeilen. Ursache: .agent-ask-card .agent-hold-actions { flex-wrap: nowrap } (static/css/agent-chat.css:502) zwingt die Mindestbreite der Reihe auf das implizite auto-Raster von .agent-ask-body (agent-chat.css:492, ohne grid-template-columns). — Auch gefunden als K9 („Key-Karte am Handy: Links brechen in sich um“): 390×844 DE: „Nicht jetzt“ 43 px breit, 48,6 px hoch (2 Zeilen), „Dem Agenten schreiben“ 101,9 px / 48,6 px (card-secret-m-de.json). agent-chat.css:502 .agent-ask-card .agent-hold-actions { flex-wrap: nowrap } bei 282 px Textspalte.

### C7 · Prüfer-Karten drohen ab der ersten Sekunde mit dem Stopp

*zweiter Blick · Pausen & Fragen · Desktop und Handy · Aufwand S · sicher · Prüfer Karten (K5)*

- **Was man sieht:** Jede Prüfer- und Netzzugriffs-Karte sagt sofort „Stoppt in 30 Minuten, wenn du nicht entscheidest“. Die Fragen des Agenten zeigen die Frist erst in den letzten fünf Minuten.
- **Apple-Maßstab:** Eine Drohung, die 25 Minuten lang nicht zählt, ist Rauschen; zwei Regeln für dasselbe Element sind inkonsistent.
- **Fix:** ASK_CLOCK_MINUTES für alle Karten; davor keine Zeile (die Pause selbst ist sichtbar genug).
- **Beleg:** Frische Karte: Uhrzeile sichtbar mit „Stops in 30 minutes without your decision“ (state-halt2-fresh-clock, state-domain-fresh-clock), ask-Karten hidden (state-confirm-fresh-clock). agent-chat.js:1569-1575: ASK_CLOCK_MINUTES nur für hold.ask.

### C8 · Netzzugriff: Karte und Verlauf sagen „stoppt“, obwohl es weitergeht

*zweiter Blick · Pausen & Fragen · Desktop und Handy · Aufwand S · sicher · Prüfer Karten (K6)*

- **Was man sieht:** Die Netzzugriffs-Karte warnt „Stoppt in 30 Minuten, wenn du nicht entscheidest“, und im Verlauf steht danach „Nach 30 Minuten ohne Entscheidung gestoppt“. Tatsächlich bleibt die Adresse nur zu, und der Agent arbeitet weiter.
- **Apple-Maßstab:** Die Oberfläche sagt etwas anderes, als passiert; das untergräbt Vertrauen in genau die Sicherheitsschicht.
- **Fix:** Domain-Karte: Uhr „Ohne Entscheidung bleibt die Adresse in {n} Minuten gesperrt“ (nur ≤5 min, s. C7); domainStates.timeout = „Nach 30 Minuten nicht erlaubt“.
- **Beleg:** Server: Domain-Timeout = „deny“, Lauf geht weiter (agent_delegation.py:2399 „not allowed, the work goes on“, :2409 kein Stop bei hold.domain). Client: holdClock agent-chat.js:1574 für jede Nicht-ask-Karte; Aktivität agent-activity.js:663 timeout „Stopped after 30 minutes without a decision“, domainStates :665 übernimmt es. Gemessen: activity-holds-en.json „Network access · Stopped after 30 minutes without a decision“.

### C9 · Die Pause steht dreimal untereinander

*zweiter Blick · Pausen & Fragen · Desktop und Handy · Aufwand S · sicher · Prüfer Karten (K14)*

- **Was man sieht:** Im Verlauf steht „Pausiert von MiMo … · Wartet auf deine Entscheidung“, direkt darunter „Pausiert, wartet auf dich“ und unten die Karte mit demselben Inhalt.
- **Apple-Maßstab:** Dieselbe Botschaft dreimal kostet Aufmerksamkeit; Apple sagt es einmal, dort, wo man handelt.
- **Fix:** Solange die Karte offen ist: keinen eigenen Eintrag „Wartet auf deine Entscheidung“, nur die Statuszeile „Pausiert“ ohne Zusatz; den Eintrag erst mit der Entscheidung schreiben.
- **Beleg:** card-halt2-d-de-light.png: Eintrag agent-hold-step (state waiting) + current-status „Paused for your decision“ (agent-activity.js:903-905, 933) + Karte (alle drei gleichzeitig sichtbar bei 1280 und 390 px).

### C10 · Zwei Prüfer, aber „Ein Prüfer hat pausiert“

*zweiter Blick · Pausen & Fragen · Desktop und Handy · Aufwand S · sicher · Prüfer Karten (K15)*

- **Was man sieht:** Halten zwei Prüfer an, steht im Titel „Ein Prüfer hat die Arbeit pausiert“, darunter nur die erste Art „Prompt Injection“ mit beiden Namen, und die Namen stehen noch einmal vor jedem Grund.
- **Apple-Maßstab:** Titel und Inhalt widersprechen sich; Wiederholung statt Klarheit.
- **Fix:** Titel nach Anzahl („Zwei Prüfer haben die Arbeit pausiert“, ganze Sätze im Wörterbuch), Meta ohne Namen, die Art je Grundzeile.
- **Beleg:** card-halt2-*.png: Titel fest (agent-chat.js:1934-1935), Meta = holdKinds[hold.kind] + hold.reviewer (beide Namen, :1937-1948), Gründe je „Name: Satz“ (:1705,1720); der zweite Grund ist 'safety', die Meta zeigt nur 'injection'. Kommt der zweite Halt auf die offene Karte, tauscht renderHold nur die [data-reason]-Zeilen (agent-chat.js:2065-2074): Meta bleibt „Prompt injection · MiMo V2.6 Flash“ ohne den zweiten Prüfer (second-after.json; die getippte Antwort bleibt erhalten).

### C11 · Key-Karte: Hauptfeld lädt zum Schreiben ein, macht aber einen Key daraus

*zweiter Blick · Pausen & Fragen · Desktop und Handy · Aufwand S · sicher · Prüfer Karten (K11)*

- **Was man sieht:** Während der Agent einen Key will, steht im Eingabefeld weiter „Schreib deine nächste Nachricht…“. Schreibe ich dort „Ich hab keinen Key“ und drücke Enter, verschwindet der Text als Punkte im Key-Feld – ein Klick auf „Speichern“ würde den Satz als Key ablegen.
- **Apple-Maßstab:** Ein Feld, das etwas anderes tut, als es anbietet, ist eine Falle.
- **Fix:** Solange die Key-Karte offen ist, sagt das Feld es selbst: Platzhalter „Füg den Key oben in die Karte ein“ (ganzer Satz im Wörterbuch); nach dem Verschieben kurz „In das Key-Feld verschoben – Speichern legt ihn ab“ an der Karte. Keine Texterkennung, A-S7 bleibt.
- **Beleg:** Gemessen: Platzhalter „Write your next message…“, nach Enter steht der Text (26 Zeichen) im Key-Feld, Fokus dort (secret-mainfield-1280.json). agent-chat.js:1216 Platzhalter ohne Pausen-Fall, :1392-1400 verschiebt den Text; nur der Senden-Tooltip sagt „Ins Key-Feld legen“ (:1378).

### C12 · Fehler beim Entscheiden nur als kurzer Toast, Rohtext

*zweiter Blick · Pausen & Fragen · Desktop und Handy · Aufwand S · sicher · Prüfer Karten (K12)*

- **Was man sieht:** Kommt meine Entscheidung nicht an, erscheint oben mittig kurz „Internal error“ und die Karte sieht aus wie vorher. Ich weiß nicht, ob es geklappt hat.
- **Apple-Maßstab:** Fehler gehören an die Stelle, an der man gehandelt hat, in Worten des Nutzers.
- **Fix:** Fehlerzeile in der Karte an der Stelle der Uhr („Hat nicht geklappt. Noch mal?“ in --dispute), Server-Text nur für bekannte Codes; Toast weg.
- **Beleg:** Mit 500 gemockt: Toast mit dem Server-Text „Internal error“ bei y≈390, Karte unverändert mit Frist-Zeile (state-halt2-failed.png). agent-chat.js:1610-1613 zeigt data.error roh per App.showPopup.

### C13 · „Wird gesendet …“ lässt die Frage-Karten wachsen

*Feinschliff · Pausen & Fragen · Desktop und Handy · Aufwand S · sicher · Prüfer Karten (K13)*

- **Was man sieht:** Tippe ich „Erlauben“, schiebt sich eine Zeile „Wird gesendet …“ über die Knöpfe und die Karte springt nach oben; der Knopf wird nur blass.
- **Apple-Maßstab:** Ein Zustand soll im Knopf sichtbar sein, nicht das Layout verschieben.
- **Fix:** Zustand im gedrückten Knopf (Text bleibt, kleiner Fortschrittspunkt/Opacity), Uhrzeile nicht einblenden.
- **Beleg:** Erlauben-Karte: Oberkante 676,7 → 651,3 px (+25,4 px) beim Senden (card-confirm-d-en vs state-confirm-sending). agent-chat.js:1879-1881 Uhrzeile ask-Karten erst hidden, :2078-2079 setzt „Sending…“.

### C14 · Verlauf spricht in der Vergangenheit, während noch gewartet wird

*Feinschliff · Pausen & Fragen · Desktop und Handy · Aufwand S · sicher · Prüfer Karten (K17)*

- **Was man sieht:** Während die Karte offen ist, steht im Verlauf „Der Agent wollte api.github.com erreichen“ bzw. „The agent waited while you had the browser“ – mit „Wartet auf dich“ darunter.
- **Apple-Maßstab:** Zeitform und Zustand widersprechen sich.
- **Fix:** Solange waiting: Präsens („Der Agent möchte … erreichen“, „Du hast den Browser“), nach der Entscheidung Vergangenheit.
- **Beleg:** agent-activity.js:669-670 askHeads und :708 Domain-Kopf nur in Vergangenheit, unabhängig von state='waiting'.

### C15 · Timeout wirkt wie ein Fehler

*zweiter Blick · Pausen & Fragen · Desktop und Handy · Aufwand M · wahrscheinlich · Prüfer Karten (K19)*

- **Was man sieht:** Habe ich 30 Minuten nicht entschieden, steht der Chat rot auf „Fehlgeschlagen“, der Verlauf sagt „Failed after …“, rechts „Schließt laufende Modellaufrufe ab…“ bleibt stehen, und darunter steht „Gespeicherte Antwort prüfen“, auch wenn es keine Antwort gab.
- **Apple-Maßstab:** Ein bewusst gestoppter Lauf ist kein Fehler; Rot und Rest-Status erzeugen falschen Alarm.
- **Fix:** hold_timeout als Stopp darstellen (grau „Gestoppt“, Kopf „Gestoppt nach …“), Satz „Ohne deine Entscheidung nach 30 Minuten gestoppt.“, „Erneut versuchen“ bleibt, „Gespeicherte Antwort prüfen“ nur mit Antwort.
- **Beleg:** timeout-en.png / timeout-de.png: Sidebar „Failed“ in --dispute, Kopf „Failed after 0s“, Panelzeile „Finishing pending model calls…“; failureNotice hold_timeout agent-chat.js:709-711 hängt an einem failed-Status.

### C16 · Begründung des Agenten als Code gesetzt

*Feinschliff · Pausen & Fragen · Desktop und Handy · Aufwand S · sicher · Prüfer Karten (K22)*

- **Was man sieht:** Auf der Netzzugriffs-Karte steht die Begründung des Agenten („Ich brauche die GitHub-API …“) in Schreibmaschinenschrift in einem grauen Codefeld, wie eine Terminal-Ausgabe.
- **Apple-Maßstab:** Prosa im Codekasten wirkt technisch und fremd; die ask-Karten zeigen die Worte des Agenten als ruhige Zeile.
- **Fix:** domain_reason wie .agent-ask-request (normale Schrift, --ink-3) direkt unter dem Titel; das Codefeld bleibt echten Befehlen/Dateien vorbehalten.
- **Beleg:** agent-chat.js:1797-1808 nutzt .agent-hold-evidence-text (agent-chat.css:458-462: --font-mono, getönte Fläche) für domain_reason.

### C17 · Beleg mitten in der Zeile abgeschnitten

*Feinschliff · Handy · Handy · Aufwand S · sicher · Prüfer Karten (K26)*

- **Was man sieht:** Am Handy endet der Code-Beleg der Prüfer-Karte mit einer halb angeschnittenen Zeile („… gegenüber dem Nutzer“).
- **Apple-Maßstab:** Harte Schnitte im Text wirken wie ein Darstellungsfehler; die App lässt Scroll-Ränder sonst weich auslaufen.
- **Fix:** Unteren Rand per mask-image weich auslaufen lassen (wie Beispielfragen-Reihe, b68e9a1b) oder Höhe auf ganze Zeilen inkl. Padding rechnen.
- **Beleg:** card-halt2-m-en-light.png: <pre> 127,6 px hoch, Inhalt länger (agent-chat.css:459 max-height calc(6*1.55em + 16px), overflow:auto, keine Maske).

### C18 · Nach der Entscheidung ist der Fokus weg

*Feinschliff · Pausen & Fragen · Desktop und Handy · Aufwand S · sicher · Prüfer Karten (K29)*

- **Was man sieht:** Tippe ich „Weiterlaufen lassen“ oder „Erlauben“, verschwindet die Karte ohne Übergang; mit der Tastatur steht der Fokus danach nirgends, der nächste Tab springt an den Seitenanfang.
- **Apple-Maßstab:** Nach einer Aktion landet der Fokus an einer sinnvollen Stelle (hier: das Eingabefeld), und Flächen verschwinden mit einer kurzen Bewegung.
- **Fix:** Vor dem Entfernen Fokus auf #questionInput (preventScroll), Karte mit --dur-state ausblenden (opacity, translateY 3 px), reduced-motion ohne.
- **Beleg:** document.activeElement nach dem Klick: <body> (after-halt1-1280.json, after-confirm-390.json); das Eingabefeld bleibt bei y=822 bzw. 794 (kein Sprung). agent-chat.js:1618-1623 holdDone → renderHold agent-chat.js:2054 replaceChildren() ohne Fokusübergabe und ohne Austritt (nur agent-hold-in, agent-chat.css:437-440).

### C19 · Entfernen-X der Warteschlange nur 32 px

*Feinschliff · Handy · Handy · Aufwand S · sicher · Prüfer Karten (K31)*

- **Was man sieht:** Das kleine X zum Entfernen einer wartenden Nachricht ist am Handy schwer zu treffen.
- **Apple-Maßstab:** Unter 44 pt Tippziel.
- **Fix:** @media (pointer: coarse) { .agent-queue-remove { width: 44px; height: 44px; margin-left: -12px; } } – die Trefferfläche darf über die 40-px-Zeile stehen.
- **Beleg:** queue-phone-queued-de.json: .agent-queue-remove 32×32 px; agent-chat.css:418-422 ohne pointer:coarse-Regel (die Karten-Links haben eine, agent-chat.css:474).

## Paket D · Marken und Anmerkungen

Die Marken sind das Ergebnis der Prüfung. „Falsch“ ist nur im Leser rot, „Unvollständig“ ist im Dunkeln kaum zu sehen, Links sehen aus wie Text, und der Anmerkungen-Leser sortiert nach Prüfer statt nach Stelle. Gestoppte oder gescheiterte Prüfungen wiederholen denselben Satz, ohne zu sagen, was jetzt zu tun ist.

Empfehlung: Ja · Aufwand: 1–2 Sessions

### D1 · „Falsch“ und „Zweifelhaft“ sind nur im Leser farbig, in der Karte und unter der Antwort grau

*zweiter Blick · Antwort & Prüfung · Desktop und Handy · Aufwand S · sicher · Prüfer Antwort (A7)*

- **Was man sieht:** Im Anmerkungen-Leser steht „Falsch“ rot und „Zweifelhaft“ bernstein. In der Karte am Text steht dasselbe „Falsch“ klein und grau hinter dem Prüfernamen, ebenso die Etiketten unter „Weitere Anmerkungen“. Das wichtigste Wort der Karte fällt nicht auf.
- **Apple-Maßstab:** Eine Bedeutung braucht überall dieselbe Farbe; Max' Regel: die Ampelfarbe gehört auf das wichtigste Glyph.
- **Fix:** .cx-card-side[data-kind='wrong'] .cx-card-tag { color: var(--dispute) }, [data-kind='doubtful'] → var(--partial), Unvollständig bleibt ink-2; dieselbe Zuordnung für .cx-audit-note. Besser: ein Satz Tokens (--kind-wrong, --kind-doubtful) für Leser, Karte, Liste und Prüfer-Zeitleiste.
- **Beleg:** Leser: Wrong rgb(173,75,87), Doubtful rgb(137,101,18), Incomplete rgb(94,94,94) (b-audit-1280-en-open.json kinds); Karte: cx-card-tag „Wrong“/„Doubtful“ rgb(94,94,94) 13 px (hover in audit-1280-light-en.json); Fallback-Etikett rgb(94,94,94) 12 px/600. Farbe nur in agent-chat.css:653-654; die Karte färbt .cx-card-meta pauschal ink-2 (components-consensus-insights.css:237-246), obwohl auditCard side.dataset.kind setzt (consensus-insights.js:2585).

### D2 · Die Marke „Unvollständig“ ist kaum zu sehen, im Dunkeln fast gar nicht

*zweiter Blick · Antwort & Prüfung · Desktop und Handy · Aufwand S · sicher · Prüfer Antwort (A9)*

- **Was man sieht:** „New windows matter less than most people expect.“ ist als unvollständig markiert, hebt sich aber nur als hauchzarter Grauschleier ab – im Dunkelmodus praktisch unsichtbar. Rote und bernsteinfarbene Stellen sieht man sofort, die graue übersieht man.
- **Apple-Maßstab:** Eine Markierung, die man suchen muss, ist keine; jede Stufe braucht eine klare Form.
- **Fix:** Unvollständig zusätzlich mit einer feinen gestrichelten Linie in ink-3 zeichnen (die vorhandene mark_lines-Form, components-consensus-visuals.css:500-503, für is-audit.is-minor immer an) oder die Fläche auf --cx-mark-note-strong (#e3e3e4 hell, ink 16 % dunkel) heben; Ziel ≥ 1,25:1 wie Bernstein.
- **Beleg:** Fläche gegen Seite: hell Grau #ececed 1,18:1, Bernstein 1,23:1, Rot 1,30:1; dunkel Grau 1,18:1 (ink 9 % auf #050505) gegen 1,32:1/1,28:1, und nur Rot/Bernstein färben im Dunkeln auch die Schrift (Ton in Ton), Grau nicht (marks in audit-1280-dark-en.json: spotColor rgb(245,245,245)). Quelle: components-consensus-visuals.css:360 und :390 (--cx-mark-note), AUDIT_CLASSES incomplete→is-minor consensus-insights.js:2546.

### D3 · Links sehen aus wie Text

*zweiter Blick · Antwort & Prüfung · Desktop und Handy · Aufwand M · sicher · Prüfer Antwort (A8)*

- **Was man sieht:** Die Quelle eines Einwands („kfw.de“) steht in Karte und Leser als graues Wort ohne Unterstrich. In Compare-Antworten ist „See the KfW page.“ ein Link, sieht aber exakt aus wie der Text daneben.
- **Apple-Maßstab:** Was man anklicken kann, muss man sehen; Max' Regel: ein gefüllter Knopf je Karte, sonst unterstrichene Links.
- **Fix:** !important in base.css:33 entfernen und Links in Fließtext und Karten einheitlich zeichnen: text-decoration underline 1px, Farbe color-mix(currentColor 35 %), text-underline-offset 3px (wie .agent-vm-restore). Compare-Antworten wie Agent-Antworten mit Quellen-Pillen (sourceReferences 'agent') oder mindestens unterstrichen.
- **Beleg:** cx-card-source „kfw.de“: color rgb(94,94,94), text-decoration-line none (hover in audit-1280-light-en.json), obwohl components-consensus-insights.css:281-289 underline setzt; .agent-audit-source ebenso none (b-audit-1280-en-open.json source), obwohl agent-chat.css:657 underline setzt; Compare-Antwortlink „KfW page“ rgb(10,10,10), decoration none = Textfarbe (compare-1280.json). Ursache: base.css:32-34 a { text-decoration: none !important; color: inherit }.

### D4 · „Weitere Anmerkungen“ zitieren Bruchstücke ohne Zusammenhang – und die Karte behauptet „In der Antwort“

*zweiter Blick · Antwort & Prüfung · Desktop und Handy · Aufwand S · sicher · Prüfer Antwort (A6)*

- **Was man sieht:** Unter der Antwort steht „Weitere Anmerkungen“ mit Zeilen wie „the speed bonus ends in 2030 Zweifelhaft“ – kleingeschrieben, ohne Prüfer, ohne Einwand. Der Satz steht so gar nicht in der Antwort. Tippt man drauf, sagt die Karte trotzdem „In der Antwort“ über dem Zitat.
- **Apple-Maßstab:** Die Karte sagt etwas Falsches, und die Liste zeigt Wortfetzen statt einer Aussage.
- **Fix:** Liste zeigt die Anmerkung, nicht das Zitat: „MiMo: Der Bonus sinkt ab 2029, er endet nicht.“ mit Art in Ampelfarbe, das Zitat klein und in „…“ dahinter. In der Karte statt „In der Antwort“ ehrlich „Nicht im Text gefunden“ (oder kein Etikett).
- **Beleg:** Fallback-Zeilen 13 px/19,5 ink-2 mit Etikett 12 px/600 (audit-1280-light-en.json other_notes); Karte der nicht platzierten Anmerkung: cx-card-tag „In the answer“ über „the speed bonus ends in 2030“ (other_card, A-audit-othernote-card-1280-light-en.png). Ursache: auditCard setzt das Etikett immer (consensus-insights.js:2582), auch für die Fallback-Liste (consensus-insights.js:2653-2659); die Liste zeigt nur item.quote (consensus-insights.js:2649-2651). Nicht platziert heißt laut agent_audit.place_marks: Zitat nicht, mehrfach oder nur außerhalb der Sätze gefunden.

### D5 · Der Anmerkungen-Leser sortiert nach Prüfer statt nach Stelle

*zweiter Blick · Antwort & Prüfung · Desktop und Handy · Aufwand M · wahrscheinlich · Prüfer Antwort (A15)*

- **Was man sieht:** Der Leser listet erst alles von GPT-6 Luna, dann alles von MiMo, dann DeepSeek. Dieselbe Stelle („capped at 30,000 euros per home.“) taucht zweimal weit auseinander auf, und das einzige „Falsch“ von DeepSeek steht weit unten.
- **Apple-Maßstab:** Der Nutzer fragt „was stimmt an meiner Antwort nicht?“, nicht „was hat Modell X gesagt?“.
- **Fix:** Nach Stellen in Antwort-Reihenfolge gruppieren, die schwerste Art zuerst; je Stelle das Zitat einmal, darunter die Prüfer mit Art und Notiz (wie die Karte am Text). Darüber eine Zeile „1 falsch · 4 zweifelhaft · 3 unvollständig“. Nicht platzierte und „Zum Vorgehen“ danach.
- **Beleg:** 11 Einträge in 3 Prüfer-Abschnitten von 382/263/395 px Höhe (b-audit-1280-en-open.json reviewers); „capped at 30,000…“ bei OpenAI (Wrong) und DeepSeek (Doubtful); das zweite „Wrong“ erst im dritten Abschnitt (ab y=881). Aufbau: auditPanel iteriert reviewers (agent-review.js:651-677).

### D6 · Bei 1280 px öffnet der Leser als riesiger Dialog für drei Zeilen

*zweiter Blick · Antwort & Prüfung · Desktop · Aufwand M · wahrscheinlich · Prüfer Antwort (A19)*

- **Was man sieht:** „Quellen“ öffnet einen Dialog fast so groß wie das Fenster; drei Quellen stehen oben, darunter rund 500 px leere weiße Fläche. Die Anmerkungen laufen über 1040 px breite Zeilen. Der Titel „Notes“ wiederholt den aktiven Reiter „Notes“.
- **Apple-Maßstab:** Die Fläche sollte zum Inhalt passen; ein Seitenpanel oder Blatt würde die Antwort sichtbar lassen.
- **Fix:** Ab 1200 px angedockt wie ab 1400 (clamp(480px, 36vw, 640px)), oder für Kontexte ohne Antworten (Notes/Sources) ein Dialog von max. 720 px Breite mit Höhe nach Inhalt (max. 80vh). Titel = Frage, Reiter allein benennen den Abschnitt.
- **Beleg:** Dialog 1120×852 px bei x=75 (b-audit-1280-en-open.json edges.dialog), Inspector-Inhalt bis 1152 px breit; angedockt erst ab 1400 px (model-answer-reader.css:169-171), sonst inset 24px (model-answer-reader.css:62-76).

### D7 · Gestoppte Prüfung im Leser: viermal derselbe Satz, „Während der Arbeit“ nur an manchen

*zweiter Blick · Antwort & Prüfung · Desktop und Handy · Aufwand S · sicher · Prüfer Antwort (A13)*

- **Was man sieht:** Im Leser steht oben „Prüfung gestoppt“ und bei jedem der drei Prüfer noch einmal „Keine abschließende Prüfung: die Prüfung wurde gestoppt.“. Danach sind einige Anmerkungen mit „Während der Arbeit“ markiert, andere aus derselben Phase nicht.
- **Apple-Maßstab:** Wiederholung statt Gestaltung; ein Etikett, das mal da ist und mal nicht, verunsichert.
- **Fix:** Eine Zeile oben: „Gestoppt – diese Anmerkungen kamen, während der Agent arbeitete.“ Den Grund je Prüfer nur zeigen, wenn er sich unterscheidet. Live-Kennzeichen in place_marks für alle Einträge setzen (oder im Leser ganz weglassen, weil die Kopfzeile es sagt).
- **Beleg:** Notes-Panel cancelled: „Review stopped“ + 3× „No final review: the review was stopped.“ (state-cancelled-1280-en.json notes). „During the run“ nur an Arbeits-Anmerkungen (#7, #4), nicht an „capped at 30,000…“. Ursache: agent-review.js:650-666 wiederholt den Grund je Prüfer; das Etikett hängt nur im Zweig item.entry (agent-review.js:590-607); place_marks setzt live nur für process-Einträge (app/services/agent_audit.py:1016-1017), nicht für claims/unplaced – entgegen docs/agent-mode.md („live: true in audit.claims/unplaced/process“).

### D8 · Gescheiterte Prüfung: Technik-Gründe, doppelt gesagt, ohne nächsten Schritt

*zweiter Blick · Antwort & Prüfung · Desktop und Handy · Aufwand M · sicher · Prüfer Antwort (A29)*

- **Was man sieht:** Unter der Antwort steht „• The review could not be completed“ und „Notes 0“. Im Leser: „its review could not be read“, „it called a tool instead of giving its review“. Die Aktivität sagt „No review: A, B, C“ und noch einmal „The review could not be completed“ plus „Read the notes“ zu genau dieser Liste.
- **Apple-Maßstab:** Ein Fehlzustand sagt in einem Satz, was er für mich bedeutet, und bietet, wenn möglich, einen Ausweg.
- **Fix:** Unter der Antwort: „Nicht geprüft – die Prüfer sind nicht fertig geworden.“ (ink-3, kein Punkt, keine Zahl). Gründe im Alltagston („kam nicht rechtzeitig“, „Antwort unbrauchbar“), Aktivität nur eine Zeile. Wenn technisch möglich: „Erneut prüfen“ als Link.
- **Beleg:** state-failed-1280-en.json: status, notes, activity_insight; Texte agent-review.js:535-541 (auditReasons), :637, :711, :714. Kein Weg, die Prüfung zu wiederholen.

### D9 · Leser: die Statuszeile klebt am ersten Prüfernamen

*Feinschliff · Antwort & Prüfung · Desktop und Handy · Aufwand S · sicher · Prüfer Antwort (A14)*

- **Was man sieht:** „Review stopped“ bzw. „The review could not be completed“ steht ohne Luft direkt über „GPT-6 Luna“, als wäre es dessen Untertitel.
- **Apple-Maßstab:** Ein Abschnitt braucht Luft vor dem nächsten; die Zuordnung muss man sehen, nicht raten.
- **Fix:** .agent-audit-panel > .agent-evidence-status { margin: 0 0 16px }, dieselben 16 px wie nach dem Hinweis.
- **Beleg:** Abstand Statuszeile → erster Prüfer 0 px (b-stopped-cancelled.json, b-stopped-stopped_early.json: statusToFirstReviewer 0); mit „Unmarked text …“ dazwischen sind es 16 px (agent-chat.css:642). .agent-evidence-status hat margin-top 0 und keinen unteren Abstand (agent-chat.css:633).

### D10 · Leser: harte Trennlinien, die 10 px vor der Kante aufhören

*Feinschliff · Antwort & Prüfung · Desktop und Handy · Aufwand S · sicher · Prüfer Antwort (A16)*

- **Was man sieht:** Zwischen den Prüfern laufen durchgehende Linien, die rechts früher enden als die Linie unter den Reitern. Auf dem Handy ist der rechte Rand dadurch 26 px, der linke 16 px.
- **Apple-Maßstab:** Zwei rechte Kanten in einer Fläche und ein ungleicher Rand fallen beim zweiten Blick auf; im System sind Trenner auslaufende Haarlinien.
- **Fix:** Trenner als auslaufende Haarlinie (border-image-Verlauf wie .cx-card-actions, components-consensus-insights.css:187) in --line-soft; scrollbar-gutter: stable both-edges oder padding-right 0, damit links und rechts gleich (16/16 Handy, 33/33 Desktop).
- **Beleg:** 1280: Reiter-Linie bis x=1162, Prüfer-Trenner bis x=1152 (Innenrand links 33 px, rechts 43 px); 390: Reiter bis x=364, Inhalt bis x=354 bei linkem Rand 16 (b-audit-*-open.json edges). Trenner 1px solid rgba(10,10,10,.13) volle Breite (agent-chat.css:639). Ursache der Kante: .answer-reader-scroll padding-right 6px + scrollbar-gutter stable (model-answer-reader.css:129).

### D11 · „Zur Arbeit“ ist als Überschrift kaum von „Unvollständig“ zu unterscheiden – und klingt schief

*zweiter Blick · Antwort & Prüfung · Desktop und Handy · Aufwand S · sicher · Prüfer Antwort (A17, auch M10)*

- **Was man sieht:** Unter den Anmerkungen eines Prüfers kommt „Zur Arbeit“ und direkt darunter „Unvollständig“ – fast gleich groß, gleich grau, gleich fett. Man liest es als zwei Etiketten. „Zur Arbeit“ klingt außerdem nach Arbeitsweg.
- **Apple-Maßstab:** Überschrift und Etikett brauchen klar verschiedene Rollen; der deutsche Text soll klingen wie von einem deutschen Team geschrieben.
- **Fix:** Überschrift als Abschnitt: 13 px/600 in ink mit 24 px Abstand davor und auslaufender Haarlinie; Deutsch „Zum Vorgehen“ (englisch „About the work“ oder „On how it worked“). Die Art „Unvollständig“ bekommt wie die anderen eine Farbe (D1).
- **Beleg:** „On the work“/„Zur Arbeit“ 12 px/550 rgb(94,94,94), „Incomplete“ 13 px/550 rgb(94,94,94) (b-audit-1280-de-open.json workHead, kinds). CSS agent-chat.css:660 und :650; Übersetzung app/i18n/de/app-agent.json:685. — Auch gefunden als M10 („Überschrift „Zur Arbeit“ liest sich wie „zum Job““): app/i18n/de/app-agent.json:685 "On the work": "Zur Arbeit"; gerendert in notes-390-light-de.png (static/js/agent-review.js:674).

### D12 · Quellen-Leser: Nummer und Pfeil stehen rechts übereinander

*Feinschliff · Antwort & Prüfung · Desktop und Handy · Aufwand S · sicher · Prüfer Antwort (A18)*

- **Was man sieht:** Rechts in jeder Quellenzeile steht die Nummer „1“ und 19 px darunter ein „↗“ – zwei kleine Zeichen gestapelt, keines auf Höhe des Titels.
- **Apple-Maßstab:** Zwei Zeichen ohne gemeinsame Kante wirken wie verrutscht.
- **Fix:** Nummer weglassen (die Liste ist kurz und ungeordnet) und nur den Pfeil auf die erste Titelzeile setzen (align-self: first baseline), 16 px vom rechten Rand.
- **Beleg:** Zeile 1: Nummer y=191,3 (x 1128–1136), Pfeil y=210,3 (x 1125–1137), Titel y=186,3 (b-audit-1280-en-open.json edges_sources). Nummer im Fluss angehängt, Pfeil absolut positioniert (model-answer-reader.js:309-313; model-answer-reader.css:311, :412).

### D13 · Teilweise geprüft: drei Lagen Kleinschrift kleben übereinander

*Feinschliff · Antwort & Prüfung · Desktop und Handy · Aufwand S · sicher · Prüfer Antwort (A23)*

- **Was man sieht:** Unter der Antwort stehen „• 2 of 3 models reviewed the answer“, direkt darunter „Other notes“, darunter die Zitate, darunter die Leiste – alles 12–13 px grau, mit 4–6 px Abstand.
- **Apple-Maßstab:** Ohne Abstufung liest sich Status, Überschrift und Inhalt als ein grauer Block.
- **Fix:** Status als leises Wort am Ende der Leiste („2 von 3 geprüft“, ink-3) statt eigener Zeile; vor „Weitere Anmerkungen“ 16 px, zwischen Liste und Leiste 12 px.
- **Beleg:** Status 15 px hoch, margin-bottom 6 px (agent-chat.css:596), dann Fallback-Titel 15 px und Zeilen 23,5 px, 10 px bis zur Leiste (agent-chat.css:591) (S-partial-1280-en-zoom.png).

### D14 · Handy: Etiketten unter „Weitere Anmerkungen“ sind winzig, ihre Tippflächen überlappen

*zweiter Blick · Handy · Handy · Aufwand S · wahrscheinlich · Prüfer Antwort (A30)*

- **Was man sieht:** Die Etiketten „Zweifelhaft“ und „Unvollständig“ sind die einzigen Knöpfe zu diesen Anmerkungen, nur so hoch wie ein Wort, und stehen eine Zeile übereinander. Mit dem Finger trifft man leicht das falsche.
- **Apple-Maßstab:** Touch-Ziele brauchen 44 px und dürfen sich nicht überdecken.
- **Fix:** Die ganze Zeile als Knopf (min-height 44 px auf coarse, 12 px Innenabstand), Etikett nur Anzeige; Zeilen 44 px auseinander.
- **Beleg:** Etiketten 52×16 bzw. 66×16 px, Zeilenabstand 23,5 px (audit-390-light-en.json other_notes); Trefferfläche je 44 px hoch mittig (components-consensus-visuals.css:673-680, Breite 44 px components-consensus-insights.css:69-74) → ~20 px Überlappung (rechnerisch, nicht getippt).

### D15 · „Read the notes“ in der Aktivität ist weder Link noch Knopf

*Feinschliff · Antwort & Prüfung · Desktop · Aufwand S · sicher · Prüfer Antwort (A31)*

- **Was man sieht:** In der aufgeklappten Aktivität steht unter der Prüfung „Read the notes“ als fetter dunkler Text – ohne Symbol, ohne Unterstrich, anders als „Notes“ unter der Antwort.
- **Apple-Maßstab:** Derselbe Weg sollte überall gleich aussehen (Glyphe + Wort), sonst rätselt man, ob es klickbar ist.
- **Fix:** evidenceButton('differences', 'Notes', null) wiederverwenden (Glyphe 15 px, 12 px/500 ink-2, Hover-Ton), oder als unterstrichener Link.
- **Beleg:** button.consensus-tab ohne agent-evidence-link-Stil (agent-review.js:727), sichtbar in A-audit-activity-1280-light-en.png; Leiste nutzt evidenceButton mit Glyphe (agent-review.js:349-372).

### D16 · Quellen-Link in den Anmerkungen kaum erkennbar und zu klein

*zweiter Blick · Antwort & Prüfung · Desktop und Handy · Aufwand S · sicher · Prüfer Handy & System (M5)*

- **Was man sieht:** Unter einer Anmerkung steht „colosseo.it“ als graue Zeile. Dass man es antippen kann, sieht man kaum: die Unterstreichung ist im Hellen fast und im Dunkeln ganz unsichtbar. Die Zeile ist zudem nur fingerdünn.
- **Apple-Maßstab:** Ein Link muss ohne Raten als Link erkennbar und mit dem Finger treffbar sein.
- **Fix:** Wie die Quellen der Antwort als Quellen-Pille (source-pill.css, .src-ref) zeigen; oder die Textlink-Klasse aus J2 (Unterstreichung currentColor, Offset 3px) und unter pointer: coarse min-height: 44px; display: inline-flex; align-items: center.
- **Beleg:** a.agent-audit-source 65,7×20,8 px, Treffer 61×22 (390 und 320 px). Unterstreichung in var(--line): 1,33:1 auf Weiß, 1,38:1 auf #050505. Regel: static/css/agent-chat.css:657 (text-decoration-color: var(--line); text-underline-offset: 0.2em). Die Prüfer-Zeitleiste nutzt für dasselbe .agent-review-note-source mit currentColor (agent-chat.css:177).

### D17 · Zwei Zitatstile für dasselbe Zitat

*Feinschliff · Antwort & Prüfung · Desktop und Handy · Aufwand S · sicher · Prüfer Handy & System (M12)*

- **Was man sieht:** Dasselbe beanstandete Zitat steht im Anmerkungen-Leser gerade in deutschen Anführungszeichen („…“), in der Prüfer-Zeitleiste kursiv in englischen (“…”).
- **Apple-Maßstab:** Ein Baustein, eine Form – und auf Deutsch deutsche Anführungszeichen.
- **Fix:** quotes-Zeile streichen (der Browser setzt sie nach lang), font-style wie .agent-audit-quote – oder beide Listen über eine Klasse rendern.
- **Beleg:** static/css/agent-chat.css:175 .agent-review-note-quote { font-style: italic; quotes: "“" "”"; } gegen .agent-audit-quote (agent-chat.css:655, <q> mit Sprach-Anführungszeichen). Screenshots sheet-session-390-light-de.png und notes-390-light-de.png.

## Paket E · Ein Zustand, überall derselbe

Während die Prüfer prüfen oder der Lauf auf dich wartet, sagt die Kopfzeile weiter „Working for“, die Chatliste „Thinking“ oder ein abgeschnittenes „Wartet auf …“. Auf dem Handy überdecken sich die Prüfer-Logos, und unter 1200 px kommt die Aktivität als riesiges Blatt.

Empfehlung: Ja · Aufwand: unter 1 Session

### E1 · Während der Prüfung sagt der Kopf weiter „Working for“

*zweiter Blick · Antwort & Prüfung · Desktop und Handy · Aufwand S · wahrscheinlich · Prüfer Lauf (R25, auch K28)*

- **Was man sieht:** Die Antwort steht, die Prüfer arbeiten. Oben steht weiter „Working for 2m 19s“; der Hinweis „Reviewing the answer…“ steht klein unter der Antwort, auf dem Laptop schon unterhalb des Bildschirms. Zu sehen ist nur ein Schimmer über dem Text.
- **Apple-Maßstab:** Der aktuelle Zustand gehört dahin, wo der Blick ist, in Worten – nicht nur als Lichteffekt.
- **Fix:** Im Kopf während `review.status === 'running'` „Reviewing · 2m 19s“ / „Wird geprüft · 2 Min. 19 Sek.“ (gleiches Feld fester Breite) und die Prüfer-Logos daneben atmen lassen.
- **Beleg:** rt9-reviewing-1280-light-en: Kopf „Working for 2m 19s“ (y 205), `.agent-check-status` bei y 945 > Viewport 900, 12 px rgb(94,94,94). Kopf aus static/js/agent-activity.js:141–148 (`durationLabel` kennt nur Working/Thought); reviewStage steht nur in den Live-Zeilen, die mit dem Antwortbeginn verschwinden (agent-activity.js:955–957 `answering`/`showPreview`). — Auch gefunden als K28 („Die Uhr läuft in der Pause weiter“): Gemessen bei offener Prüfer-Karte: „Working for 0s“ → nach 4,2 s „Working for 4s“, deutsch „Arbeitet seit 0 Sek.“ → „4 Sek.“ (pauseclock-*.json). agent-activity.js:196-210 updateClock tickt bei running, agent-activity.js:141-148 durationLabel kennt keinen Pausenzustand; der Server hält die Turn-Uhr an (paused_seconds, docs/agent-mode.md „Aussteuern“).

### E2 · Chatliste nennt einen anderen Zustand als die Aktivität

*zweiter Blick · Agent arbeitet · Desktop · Aufwand S · sicher · Prüfer Lauf (R10)*

- **Was man sieht:** Während Befehle laufen und Seiten gelesen werden, steht in der Chatliste „Thinking“ („Denkt nach“). Während die Prüfer die Antwort prüfen, steht dort „Writing ans…“ (abgeschnitten, deutsch „Schreibt An…“), obwohl die Aktivität „Reviewing the answer…“ sagt.
- **Apple-Maßstab:** Ein Zustand, ein Wort – überall gleich, und nie abgeschnitten.
- **Fix:** statusLabel aus demselben Zustand ableiten wie die Kopfzeile der Aktivität, in Kurzform: „Working“, „Reviewing“/„Wird geprüft“, „Paused“; Wörter ≤ 10 Zeichen, damit nichts abgeschnitten wird.
- **Beleg:** rt4/rt6 (Befehl/Browser läuft): Chatliste „Thinking“; rt9-reviewing-bottom: „Writing ans…“, DE „Schreibt An…“. static/js/run-view.js:230–231: `streamText` → „Writing answer“, irgendein Reasoning-Ereignis → „Thinking“; Prüfung und Werkzeuge kennt die Funktion nicht.

### E3 · „Wartet auf dich“ in der Seitenleiste abgeschnitten

*sofort sichtbar · Pausen & Fragen · Desktop und Handy · Aufwand S · sicher · Prüfer Karten (K8)*

- **Was man sieht:** In der Chatliste steht beim wartenden Lauf „Waiting for …“ bzw. „Wartet auf …“ – das wichtigste Wort fehlt. Nach einem Timeout „Fehlgeschl…“.
- **Apple-Maßstab:** Ein Status, der abgeschnitten ist, ist kein Status; Apple kürzt den Titel, nie den Zustand.
- **Fix:** Kürzeres Wort aus dem Glossar („Du bist dran“ gibt es schon, 'Your turn') oder max-width 96 px; der Titel davor trägt die Ellipse.
- **Beleg:** Statusbreite 78 px, Inhalt 86 px (EN) / 87 px (DE), sidebar-browser-*.json; layout.css:1286 max-width:78px mit text-overflow:ellipsis. „Pausiert“ passt (46 px).

### E4 · Prüfer-Logos auf dem Handy ohne Worte und halb verdeckt

*zweiter Blick · Handy · Handy · Aufwand S · sicher · Prüfer Lauf (R12)*

- **Was man sieht:** Auf dem Handy stehen unter dem Feld drei bunte Logos ohne Erklärung, so eng übereinander, dass das OpenAI-Logo nur als halbes „C“ zu sehen ist. Wofür sie stehen, sagt nur ein Tooltip, den es auf dem Handy nicht gibt.
- **Apple-Maßstab:** Max hat die Worte am 28.10. gerade eingeführt, weil Neue nicht wussten, warum dort Logos stehen – auf dem Handy gilt das noch mehr.
- **Fix:** Unter 561 px eine Kurzform zeigen („3 KIs“ / „3 AIs“) und die Überdeckung auf ≤ 6 px begrenzen (Versatz 16 px wie am Desktop).
- **Beleg:** r12-composer-chat-390 / zoom-composer-390.png: Marken 22 px breit bei x 74/86/98 (12 px Versatz = 45 % Überdeckung); #composerReviewersLabel display:none. static/css/shell.css:3864 (`margin-left: -10px` unter 480 px), static/css/composer.css:112.

### E5 · Dieselben Prüfer-Worte verschwinden an zwei verschiedenen Breiten

*Feinschliff · Frage stellen · Desktop und Handy · Aufwand S · sicher · Prüfer Lauf (R13)*

- **Was man sieht:** Zwischen etwa 560 und 700 px Breite (kleines Tablet, schmales Fenster) steht im Chat „3 KIs prüfen mit“, auf dem Startbildschirm aber nur die Logos.
- **Apple-Maßstab:** Ein Bauteil, eine Regel – sonst wirkt es wie zwei Bauteile.
- **Fix:** Eine gemeinsame Grenze (bzw. die Container-Query aus H2) für beide Labels.
- **Beleg:** Startleiste `#composerModelLabel.composer-tool-label` weg ab ≤ 700 px (static/css/shell.css:3870–3871), Chat `.composer-reviewers-label` erst ≤ 560 px (static/css/composer.css:112).

### E6 · Aktivitätsleiste unter 1200 px als 1066 px breites Blatt

*zweiter Blick · Agent arbeitet · Desktop · Aufwand S · sicher · Prüfer Lauf (R14)*

- **Was man sieht:** Auf einem Tablet quer oder einem kleineren Laptop-Fenster kommt die Prüfer-Liste als riesiges Blatt von unten über die ganze Breite; Name links, Zeit fast einen Meter Lesestrecke weiter rechts.
- **Apple-Maßstab:** Auf großen Flächen nutzt Apple Seitenleisten oder Popover, Bottom-Sheets nur auf dem Telefon.
- **Fix:** Ab ≥ 700 px das Blatt rechts verankern und auf `min(420px, 100vw - 24px)` begrenzen (gleiche Breite wie das Panel), Bottom-Sheet nur darunter.
- **Beleg:** r22-1100-light-en: Blatt 1066 px breit, „Round 3“ bei x 81, Zeit „10:00“ bei x 1052 (≈ 970 px Abstand). static/css/agent-chat.css:315–321 (`@media (max-width: 1199px)`: left/right 12 px, bottom-anchored).

## Paket F · Befehle und Prüfer-Runden ruhig

Befehlsblöcke zeigen oben eine halbe Zeile, füllen live bis zu 213 px, und ein fehlgeschlagener Befehl sieht aus wie ein gelungener. Zeit und Pfeil wechseln ihren Platz. Pro-Nutzer sehen das rohe Arbeitsprotokoll mit JSON und internen Namen.

Empfehlung: Ja · Aufwand: unter 1 Session

### F1 · Ein fehlgeschlagener Befehl sieht aus wie ein gelungener

*zweiter Blick · Agent arbeitet · Desktop und Handy · Aufwand S · sicher · Prüfer Lauf (R5)*

- **Was man sieht:** Neben einem Befehl, der mit Fehler abbricht, steht nur klein und grau „Exit 1“ (deutsch „Exit-Code 1“) – genau so grau wie „3s“ beim erfolgreichen Befehl daneben. Erst wer aufklappt, sieht den Traceback.
- **Apple-Maßstab:** Zustände sind gestaltet: ein Fehler braucht ein erkennbares Zeichen und ein Wort, das Laien verstehen, kein Shell-Jargon.
- **Fix:** Bei exit_code≠0 bzw. timed_out die Meta in `--dispute` (nur das Wort, keine Fläche) und als „Fehlgeschlagen · Code 1“ / „Failed · code 1“; im Verlauf den Punkt der Schiene ebenfalls in `--dispute`.
- **Beleg:** p2-history-vm-open-de: „Exit-Code 1“ und „3 Sek.“ beide 12 px rgb(94,94,94). static/js/agent-activity.js:547 (`Exit {code}`), static/css/agent-chat.css:848 `.agent-vm-meta { color: var(--ink-3) }` ohne Zustandsregel; `data-status` ist bei Exit≠0 trotzdem `succeeded`.

### F2 · Halbe Zeile oben im Live-Ausgabefeld

*zweiter Blick · Agent arbeitet · Desktop und Handy · Aufwand S · sicher · Prüfer Lauf (R3)*

- **Was man sieht:** Läuft ein Befehl mit viel Ausgabe, steht oben im grauen Feld eine waagerecht durchgeschnittene Textzeile – nur die untere Hälfte der Buchstaben ist zu sehen.
- **Apple-Maßstab:** Angeschnittene Glyphen wirken wie ein Renderfehler; Apple lässt Scrollbereiche weich auslaufen.
- **Fix:** Oben eine Maske über das Padding legen (`mask-image: linear-gradient(transparent, #000 10px)` nur solange scrollTop > 0) oder das obere Padding auf 0 und den Abstand außen geben; Kommentar 878–880 passt dann wieder.
- **Beleg:** zoom-vm-output-1280.png: über „Year 5“ ragt die Unterkante von „Year 4“. Feldhöhe gemessen 109 px = 5 × 18.6 px + 16 px Padding (static/css/agent-chat.css:881 `max-height: calc(5lh + 16px)`); static/js/agent-activity.js:606 scrollt ans Ende, daher füllt die vorige Zeile die 8 px Innenabstand oben.

### F3 · Ein langer Befehl füllt die Live-Zeilen

*zweiter Blick · Agent arbeitet · Desktop und Handy · Aufwand S · sicher · Prüfer Lauf (R4)*

- **Was man sieht:** Schreibt der Agent ein kleines Skript, steht während es läuft der komplette Quelltext als Kopfzeile in Schreibmaschinenschrift da – auf dem Handy zehn Zeilen, die Ausgabe darunter nur eine Zeile. Ist der Befehl fertig, schrumpft alles auf eine Zeile zusammen.
- **Apple-Maßstab:** Die Live-Fläche soll sagen, was gerade passiert, nicht einen Codeblock vorlesen; Notizen werden schon auf drei Zeilen begrenzt, Befehle nicht.
- **Fix:** In `.agent-progress` den Befehlskopf auf 2 Zeilen klemmen (`-webkit-line-clamp: 2`, letzte Zeile mit …), ganz erst in der Zeitleiste oder per Klick; die Ausgabe behält ihre 5 Zeilen.
- **Beleg:** rt3-vm-390: Befehlskopf 213.3 px hoch (Plan 111 px, Ausgabe 1 Zeile); 1280: ca. 170 px. static/css/agent-chat.css:847 `.agent-vm[open] > summary .agent-vm-target { white-space: pre-wrap }` gilt auch live; Notizen dagegen 773–775 `line-clamp: 3`. Layout-Shift-Messung rt5: Block wandert beim Zuklappen 699→450 px.

### F4 · Zeit und Pfeil der Befehlszeile wechseln ihren Platz

*zweiter Blick · Agent arbeitet · Desktop und Handy · Aufwand S · sicher · Prüfer Lauf (R6)*

- **Was man sieht:** Bei einem Befehl steht „Running…“ mit Pfeil ganz rechts am Rand, beim nächsten direkt hinter dem Text, beim kurzen Befehl klebt der Pfeil am letzten Zeichen. Je nach Länge springt die Zeile.
- **Apple-Maßstab:** Gleiches sieht gleich aus: Status und Aufklapper gehören immer an dieselbe Kante.
- **Fix:** `.agent-vm-meta { margin-left: auto }` (Zeit und Pfeil immer an der rechten Kante, wie die Zeiten in der Prüfer-Zeitleiste) oder konsequent direkt hinter dem Text – eins von beiden.
- **Beleg:** rt3: Meta/Pfeil bei x≈829–898 (rechter Rand); rt4: x≈713–782; rt5: Pfeil bei x≈562. Ursache static/css/agent-chat.css:841–847: Ziel `flex: 0 1 auto`, geöffnet `pre-wrap` → volle Breite; Meta 848 ohne `margin-left:auto`.

### F5 · Arbeitsprotokoll zeigt Pro-Nutzern das Rohprotokoll

*zweiter Blick · Agent arbeitet · Desktop und Handy · Aufwand S · sicher · Prüfer Lauf (R15)*

- **Was man sieht:** Unten in der Leiste steht „Arbeitsprotokoll“. Aufgeklappt: „#3 Agent Schritt completion:0 Modell 10:00“, „#14 App App answer_fixed App“, umrandete Etiketten („Nutzer“, „VM“, gestrichelt „Web“) und JSON mit geschweiften Klammern.
- **Apple-Maßstab:** Interne Bezeichner, Protokollnummern und JSON sind Entwickler-Werkzeug; umrandete Pillen widersprechen der rahmenlosen Linie.
- **Fix:** Entweder wieder `.admin-only` (Karte korrigieren) oder für Pro eine Lesefassung: nur Agentenschritte in den Worten der Aktivität, ohne #/Rohnamen/JSON, Herkunft als leises Wort statt Rahmen-Pille.
- **Beleg:** p2-worklog-de. static/js/agent-delegation.js:405 `agent-work-log-host audit-only` (seit ab9885fe, vorher `admin-only`), static/style.css:62 zeigt `.audit-only` jedem Pro-Konto mit Audit; Einträge static/js/agent-work-log.js:107–125; Rahmen static/css/agent-chat.css:277–278. docs/codebase-map.md („`.admin-only`“, „nur Admins“) widerspricht dem Code.

### F6 · Uhrzeiten in Prüfer-Runden und Protokoll sind alle gleich

*Feinschliff · Agent arbeitet · Desktop und Handy · Aufwand S · sicher · Prüfer Lauf (R16)*

- **Was man sieht:** Jede Runde eines Prüfers trägt rechts „10:00“ – vier Runden, viermal dieselbe Zeit. Im Arbeitsprotokoll ebenso.
- **Apple-Maßstab:** Eine Zahl, die sich nie ändert, ist Rauschen.
- **Fix:** Relative Zeit seit Laufbeginn („nach 0:17“, tabellarische Ziffern) oder die Zeit nur an der Schlussprüfung.
- **Beleg:** r21-panel-live-reviewer: Runden mit created_at 09:00:17 … 09:00:45 UTC, alle „10:00“. static/js/agent-delegation.js:545 `App.format.time(message.created_at)` (Minutengenau); Läufe dauern 1–3 min.

### F7 · Prüfer-Kennzahlen als Mini-Tabelle zwischen harten Linien

*Feinschliff · Agent arbeitet · Desktop und Handy · Aufwand S · sicher · Prüfer Lauf (R17)*

- **Was man sieht:** Im geöffneten Prüfer stehen „Runden 4 · Anmerkungen 1 · Schlussprüfung 2“ als drei Spalten mit Etikett über Zahl, eingerahmt von zwei durchgehenden Linien; darüber eine dritte Linie unter „Auszüge aus dem Nachdenken“.
- **Apple-Maßstab:** Max: höchstens ein Etikett pro Block, Haarlinien laufen an beiden Enden aus; drei Linien auf 110 px sind ein Kasten-Ersatz.
- **Fix:** Eine Satzzeile in --ink-3: „4 Runden · 1 Anmerkung · Schlussprüfung mit 2“ ohne Linien; die Rundenliste darunter trägt den Rest.
- **Beleg:** r14-panel-reviewer-1280-light-de: Block 268×61 px bei y 216; static/css/agent-chat.css:148 `border-top/bottom: 1px solid var(--line-soft)` (nicht maskiert); Aufbau static/js/agent-delegation.js:534–538.

## Paket G · Arbeitsplatz und Übergabe

Neben der offenen Aktivität ist der Arbeitsplatz bei 1280 px nur 155 px breit, seine Knöpfe ragen in die Nachbarspalte. Sobald du den Browser übernimmst, verschwindet die Bitte des Agenten, was du tun sollst.

Empfehlung: Ja, die ersten beiden sofort · Aufwand: unter 1 Session

### G1 · Arbeitsplatz zu schmal neben der offenen Aktivität

*sofort sichtbar · Arbeitsplatz · Desktop · Aufwand M · sicher · Prüfer Karten (K1)*

- **Was man sieht:** Öffne ich den Arbeitsplatz auf dem Laptop, während rechts die Agent-Aktivität offen ist, wird er zu einem schmalen Streifen. Bei 1280 px ist er 155 px breit: Der Hinweis bricht in zehn Zeilen, „Du hast den Browser“ steht Wort für Wort untereinander, „Zurückgeben“ liegt über dem Text und ragt in die Aktivität. Bei 1440 px liegen „Einfügen“/„Übernehmen“ und das X über der Überschrift „Agent activity“.
- **Apple-Maßstab:** Zwei Seitenleisten überlappen sich und die wichtigste Taste liegt über fremdem Text; bei Apple macht eine Leiste der anderen Platz.
- **Fix:** Reicht room nicht für MIN_WIDTH (380), klappt das Öffnen des Arbeitsplatzes die Aktivität ein (bzw. legt den Arbeitsplatz über sie, rightOffset 0) und merkt sich das; zusätzlich container-type:inline-size auf .workspace-view und die ≤760-Regeln als @container (max-width: 420px) schreiben, damit Kopf und Leiste nach der echten Panelbreite umbrechen.
- **Beleg:** Panelbreite 1280×900: 155 px (x 769–924), Kopf reicht bis x=1200 (276 px über die Panelkante, Schließen-X bei x=1168); 1440×900: 315 px, Kopf bis x=1174 (90 px über die Kante bei 1084). Ursache workspace-view.js:128-131 bounds(): room = Breite − Sidebar 260 − Aktivität 346 − MIN_CHAT 520 = 154 → max (154) < min (260), layout() workspace-view.js:146 nimmt dann max. Kopf ist eine nicht umbrechende Flex-Zeile (workspace-view.css:136), Umbruch nur per Viewport-Query max-width:760px (workspace-view.css:510), nicht nach Panelbreite. Aktivität ist seit 10-28 ab 1200 px standardmäßig offen.

### G2 · Die Bitte des Agenten verschwindet, sobald ich den Browser habe

*sofort sichtbar · Arbeitsplatz · Desktop und Handy · Aufwand S · sicher · Prüfer Karten (K2)*

- **Was man sieht:** Der Agent schreibt „Bitte melde dich bei GitHub an (mit 2FA) und gib mir den Browser dann zurück.“ Sobald ich „Browser öffnen“ tippe (oder die Ansicht schon offen ist), ist die Karte weg und über dem Bild steht nur noch „Du hast den Browser · Der Agent wartet.“ Was ich dort tun soll, steht nirgends mehr – genau in dem Moment, in dem ich es brauche.
- **Apple-Maßstab:** Die Aufgabe verschwindet in dem Moment, in dem man sie erledigen soll; Apple behält den Auftrag sichtbar, bis er erledigt ist.
- **Fix:** In showTurn die Bitte auch bei user zeigen: Titel „Du hast den Browser“, leise Zeile = Bitte des Agenten (statt „Der Agent wartet.“), „Der Agent wartet.“ nur ohne Bitte (ungefragte Übernahme).
- **Beleg:** Leistentext nach Übernahme: „You have the browser / The agent waits. / Hand back“ (ws-asked-*.json, ws-opened-*.json), Karte hidden=true. workspace-view.js:470 waiting = waitingFor !== null && !user; :482 Bitte nur wenn waiting, also nie, während der Nutzer den Browser hat. agent-chat.js:2053 blendet die Chat-Karte bei offener Ansicht aus.

### G3 · Arbeitsplatz: Tipp-Ziele unter 44 px

*zweiter Blick · Handy · Handy · Aufwand S · sicher · Prüfer Karten (K23)*

- **Was man sieht:** Am Handy sind „Browser“/„Terminal“ 24 px hoch, „Einfügen“ 28 px, das Schließen-X 32 px; am Desktop ist „Zurückgeben“ 32 px statt 36 px wie alle anderen Hauptknöpfe.
- **Apple-Maßstab:** 44-pt-Regel; gerade im Vollbild-Panel am Handy trifft man das X schlecht.
- **Fix:** @media (pointer: coarse): Tabs/Einfügen/Schließen min-height 44 px (Trefferfläche per Padding oder ::before, Optik bleibt); .workspace-view-turn-button ohne eigenes min-height (erbt .btn 36/44).
- **Beleg:** ws-idle-390-light-de.json: Tabs h=24, Einfügen h=28, Schließen 32×32; Desktop „Zurückgeben“ h=32 (ws-idle-1440). workspace-view.css:158 (.workspace-view-tab padding 4px 12px), :211 (.workspace-view-close 32px), :335 (.workspace-view-turn-button min-height 32px); keine pointer:coarse-Regel in workspace-view.css.

### G4 · Grüner Steuer-Rand auch um das Terminal

*Feinschliff · Arbeitsplatz · Desktop und Handy · Aufwand S · sicher · Prüfer Karten (K24)*

- **Was man sieht:** Habe ich den Browser und wechsle zu „Terminal“, trägt das Terminal den grünen Rand, die Leiste „Du hast den Browser · Zurückgeben“ ist aber weg.
- **Apple-Maßstab:** Der Rand sagt „du steuerst das hier“, gemeint ist aber der Browser; das einzige Signal zeigt aufs falsche Objekt.
- **Fix:** Rand nur an #workspacePane-browser; im Terminal-Tab eine kompakte Leiste „Du hast den Browser · Zurückgeben“ lassen.
- **Beleg:** ws-terminal-1440-dark-en.png; workspace-view.css:340 .workspace-view.is-user .workspace-view-screen::after trifft auch #workspacePane-terminal (gleiche Klasse); showTurn blendet die Leiste außerhalb des Browser-Tabs aus (workspace-view.js:472).

### G5 · Langer Hinweistext über dem Bild

*Feinschliff · Arbeitsplatz · Desktop und Handy · Aufwand S · sicher · Prüfer Karten (K25)*

- **Was man sieht:** Über dem Browserbild steht dauerhaft ein vierzeiliger Satz („Melde dich hier selbst auf Websites an und tipp dein Passwort oder füge es ein: Der Agent pausiert so lange …“), darunter die Leiste mit ihrem eigenen Text.
- **Apple-Maßstab:** Zwei erklärende Blöcke übereinander vor dem eigentlichen Inhalt.
- **Fix:** Eine Zeile: „Melde dich hier selbst an – der Agent tippt nie ein Passwort.“; ausblenden, solange die Leiste steht.
- **Beleg:** Hinweis 314 px breit, 70 px hoch (4 Zeilen) bei 1440 (ws-idle-1440); workspace-view.js:88-91 HINTS.browser, workspace-view.css Hinweis immer sichtbar ab 761 px.

## Paket H · Handy und Tastatur

Tippziele in der Aktivität sind 19–28 px statt 44, der Platzhalter im Feld ist abgeschnitten, die Kopfleiste bleibt hell über dem Aktivitäts-Blatt, und am kleinen Handy landet der Fokus unter Karte oder Kopfleiste. Eine fertige Prüfung sagt der Screenreader nicht an.

Empfehlung: Ja, danach am iPhone abnehmen · Aufwand: unter 1 Session + 10 Minuten Test von dir

### H1 · Tippziele in der Aktivität auf dem Handy 19–28 px

*zweiter Blick · Handy · Handy · Aufwand S · sicher · Prüfer Lauf (R7, auch M4)*

- **Was man sieht:** Auf dem Handy muss man Befehle, „Plan · 2 of 4 done“, „5 earlier steps“, die Quellen-Pillen und die Prüfer-Logos sehr genau treffen; daneben tippt man ins Leere.
- **Apple-Maßstab:** Apple verlangt 44 pt pro Ziel; die App hält das sonst überall ein (Apple-Audit F5).
- **Fix:** Für `.agent-vm > summary`, `.agent-vm-fold > summary`, `.agent-plan > summary`, `.agent-activity-sources .src-ref`, `.agent-inline-model`, `.agent-sidebar-toggle` unter `(pointer: coarse)` ein `::before { inset: var(--hit-slop) }` bzw. `min-height: 44px` mit negativem Margin – Zeichnung bleibt gleich.
- **Beleg:** r11-done-open-390 (has_touch): Befehlsköpfe 328×21.4 px, Plan-Köpfe 125×21.4, Quellen-Pillen 19.4 px hoch, Prüfer-Logos 25×25, Panel-Symbol 28×28; die Kopfzeile selbst 44 px. static/css/agent-chat.css:834 (`min-height: 1.65em`), 885–888, 937–940, 201 (28 px), 224–227 (25 px); im Gegensatz zu 191–194 (`.agent-sidebar-close` mit `--hit-slop`) keine `(pointer: coarse)`-Regel. — Auch gefunden als M4 („Zu kleine Tippziele in der Aktivitätszeile“): Mit elementFromPoint gemessen (390 und 320 px, touch): button.agent-inline-model 25×25, Treffer 19×26 bzw. 26×26 (margin-left −6px überlappt, static/css/agent-chat.css:224-228); .agent-sidebar-toggle 28×28, Treffer 28×28 (agent-chat.css:200); summary.agent-vm-head 21,4 px hoch (agent-chat.css:834); „2 frühere Schritte“ 21,4 px (agent-chat.css:885-888); „Anmerkungen lesen“ 36 px (agent-chat.css:992-995). Für .agent-sidebar-close gibt es die Unsichtbar-Fläche schon (agent-chat.css:191-194), für diese Knöpfe nicht. Pausenkarte (EN): „Stop“ nur 30,4 px breit (Treffer 32×44).

### H2 · Platzhalter im Eingabefeld abgeschnitten

*zweiter Blick · Frage stellen · Desktop und Handy · Aufwand S · sicher · Prüfer Lauf (R11, auch M3, K27)*

- **Was man sieht:** Am Laptop mit offener Aktivitätsleiste steht im Feld „Write your next messag…“ bzw. „Schreib deine nächste Na…“. Auf dem Handy wird „Schreib deine nächste Nachricht“ hart vom Stopp-Knopf abgeschnitten, das „t“ fehlt halb.
- **Apple-Maßstab:** Der wichtigste Satz der Seite darf nicht mitten im Wort enden.
- **Fix:** Prüfer-Worte per Container-Query ausblenden, sobald das Feld unter ~300 px fällt (wie `@container composer-options` in shell.css:3874), und den laufenden Platzhalter kürzen („Nachricht an den Agenten…“ / „Message the agent…“).
- **Beleg:** rt5-note-1280-light-de: #questionInput 232 px breit (EN 218.6) von 626 px; Prüfer-Knopf 166.7/180.1 px, Chip 119.3 px. rt5-note-390-light-de: Feld 260 px, Text braucht ~265 px. Platzhalter static/js/agent-chat.js:1216; Worte des Prüfer-Knopfs erst unter 561 px weg (static/css/composer.css:112). — Auch gefunden als M3 („Platzhalter „Schreib deine nächste Nachricht…“ hart abgeschnitten“): Screenshots reviewing-390-dark-de-full.png, hold-320-light-de.png, hold-320-dark-en.png. Text aus app/i18n/de/app-agent.json:200. Gemessen: Text 257,5 px breit, Feldinhalt 240 px (390) bzw. 174 px (320); englisch 199,8 px. Das Feld selbst hat white-space: pre-wrap und text-overflow: clip. Die Ellipse fürs Feld steht nur im Desktop-Block @media (min-width: 1100px) (static/css/composer.css:244, 261-264); unter 1100 px setzt composer.css:350-354 sie nur auf ::placeholder – laut eigenem Kommentar (composer.css:259-260) zeichnet Chromium sie dann nicht. Deutscher Satz: app/i18n/de/app-agent.json:200. — Auch gefunden als K27 („Platzhalter abgeschnitten, sobald Prüfer im Feld stehen“): queue-1280-en.png bei 1280 px mit Audit an (#composerReviewers + Chip „DeepSeek V4.1 Flash“); Platzhalter agent-chat.js:1216. Schnittstelle zum Bereich „Frage stellen“.

### H3 · Kopfleiste bleibt hell über dem Aktivitäts-Sheet

*zweiter Blick · Handy · Handy · Aufwand S · sicher · Prüfer Handy & System (M6)*

- **Was man sieht:** Öffnet man auf dem Handy die Agent-Aktivität, dimmt die Seite ab, aber oben bleiben Seitenleisten- und Stift-Symbol samt heller Leiste ungedimmt stehen und lassen sich antippen. Im Hellen liegt oben ein weißer Streifen über dem grauen Dimmer.
- **Apple-Maßstab:** Ein modales iOS-Sheet dimmt alles dahinter gleich, auch Navigationsleiste und Statusleiste.
- **Fix:** In shell.css die bestehende Regel ergänzen: body.agent-sidebar-sheet .app-mobile-header { opacity: 0; visibility: hidden; pointer-events: none; } (wie bei .sidebar.active) oder Scrim und Sheet auf calc(var(--z-header) + 1) heben.
- **Beleg:** z-index: .app-mobile-header var(--z-header) = 1500 (static/css/shell.css:3910) über .agent-sidebar-scrim 1290 (static/css/agent-chat.css:313) und dem Sheet 1300 (agent-chat.css:319), obwohl das Sheet role=dialog aria-modal=true trägt. Für das Seitenmenü blendet shell.css:4192-4199 die Kopfleiste aus, für body.agent-sidebar-sheet nicht. Gemessen bei offenem Sheet (390 px, hell und dunkel): Seitenleisten- und Neuer-Chat-Knopf per elementFromPoint erreichbar (reachable: true), Kopf-Hintergrund rgb(255,255,255) bzw. rgb(5,5,5) ungedimmt. Das Satz-Sheet (claim-sheet-backdrop, z-modal − 1 = 1999) dimmt die Kopfleiste dagegen.

### H4 · Am kleinen Handy landet der Fokus unter Karte und Kopfleiste

*zweiter Blick · Pausen & Fragen · Handy · Aufwand S · sicher · Prüfer Handy & System (M16)*

- **Was man sieht:** Mit Tastatur (z. B. iPad-/Bluetooth-Tastatur oder Schaltersteuerung) springt der Fokus bei offener Pausenkarte auf Elemente, die gerade unter der Kopfleiste oder der Karte liegen – man sieht nicht, wo man ist.
- **Apple-Maßstab:** WCAG 2.4.11: Fokus darf nicht verdeckt sein; iOS scrollt fokussierte Ziele frei.
- **Fix:** html { scroll-padding-top: var(--app-mobile-header-height) } unter 1100 px; zusammen mit C4 (Karte höchstens so hoch wie der freie Platz) bleibt dann immer ein sichtbares Band für das Fokusziel.
- **Beleg:** 320×568, Tab ab Seitenanfang: „Arbeitet seit 0 Sek.“ (top 4,4 px) und „2 frühere Schritte“, Befehlszeile unter header.app-mobile-header.is-scrolled; beide Modell-Logos (top 13,9 px) unter div.input-section. 5 der ersten 7 Tab-Ziele verdeckt; auf 390×844 keines. Ursache: syncFocusReserve setzt scroll-padding-bottom auf die Höhe der .input-section samt Karte (static/js/app-init.js:575-584, bei 320×568 rund 500 px), für die fixe 56-px-Kopfleiste (shell.css:3907-3910) gibt es kein scroll-padding-top: zwischen Kopf und Karte bleibt ein Band von gut 10 px, in das der Browser das Ziel scrollt.

### H5 · Fertige Prüfung wird nicht angesagt

*zweiter Blick · Antwort & Prüfung · Desktop und Handy · Aufwand S · wahrscheinlich · Prüfer Handy & System (M17)*

- **Was man sieht:** VoiceOver sagt „Antwort wird geprüft…“, aber wenn die Marken kommen, sagt es nichts. Wer nicht sieht, erfährt nicht, dass und wie viele Stellen beanstandet wurden.
- **Apple-Maßstab:** Ein Zustandswechsel, den Sehende sehen, wird auf iOS angesagt (UIAccessibility announcement / Live-Region).
- **Fix:** Bei succeeded/partial einen kurzen Satz nur für Screenreader in die Statuszeile („Prüfung fertig: 3 markierte Stellen, 1 Anmerkung zum Vorgehen“) – visuell weiter versteckt (.visually-hidden statt hidden), damit die Leiste ruhig bleibt.
- **Beleg:** Live-Regionen gemessen: während der Prüfung .agent-check-status role=status „Antwort wird geprüft…“; danach fehlt sie, und .agent-review-status role=status ist hidden mit leerem Text. Ursache: auditStatus() gibt für succeeded '' zurück (static/js/agent-review.js:633-638), renderAudit blendet die Statuszeile dann aus (agent-review.js:765-768).

### H6 · Fokusring an Textknöpfen eckig und viel größer als das Wort

*Feinschliff · Pausen & Fragen · Desktop und Handy · Aufwand S · sicher · Prüfer Handy & System (M18)*

- **Was man sieht:** Kommt man per Tastatur auf „Dem Agenten schreiben“, erscheint ein eckiger Kasten, deutlich höher als der Text; überall sonst ist der Ring abgerundet.
- **Apple-Maßstab:** Ein Fokusring folgt der Form des Bedienelements; ein eckiger Kasten um ein Wort wirkt wie ein Debug-Rahmen.
- **Fix:** Mit der Textlink-Klasse aus J2: :focus-visible { border-radius: var(--radius-2xs); outline-offset: 2px } und die 44-px-Fläche per ::after statt min-height.
- **Beleg:** Screenshot hold-top-320-light-de.png: Ring 2px solid #5e5e5e um 44 px Höhe, Ecken 0. .agent-hold-link hat keinen Radius (static/css/agent-chat.css:467-470, 474); base.css:66 rundet den Ring nur für <a>, Textknöpfe sind <button>. Gleiches gilt für .agent-watch-link, .agent-memory-head button.

## Paket I · Ein Wort für jedes Ding

Die Prüfer heißen KIs, Prüfer, Modelle und Vergleichsmodelle; die Schlussrunde und die Pause haben je drei Namen. „Failed after“ und Vorlesetexte bleiben auf Deutsch englisch, und einige Sätze klingen übersetzt. Mein Vorschlag: überall „Prüfer“, nur im Chip bleibt „3 KIs prüfen mit“.

Empfehlung: Ja – „Prüfer“ als ein Wort, sag Bescheid, falls nicht · Aufwand: unter 1 Session

### I1 · Vier Namen für die Prüfer

*zweiter Blick · Antwort & Prüfung · Desktop und Handy · Aufwand M · sicher · Prüfer Handy & System (M8)*

- **Was man sieht:** Dieselben Modelle heißen im Feld „2 KIs prüfen mit“, auf der Pausenkarte und im Sheet „Prüfer“, in der Aktivität „Prüfung · 2 Modelle“ und „Modelle: …“, in der Marken-Karte „1 Modell hat einen Einwand“, in den Anmerkungen bei Teilergebnis „1 von 2 Modellen haben die Antwort geprüft“ und im Vorlesetext des Chips „Vergleichsmodelle“.
- **Apple-Maßstab:** Apple benennt eine Rolle überall gleich; wechselnde Wörter lassen vermuten, es seien verschiedene Dinge.
- **Fix:** Im Audit-Modus überall „Prüfer“ (ein Prüfer / 2 Prüfer); der Chip darf „2 KIs prüfen mit“ behalten, aber Aktivität, Marken-Karte, Anmerkungen und Vorlesetexte sagen „Prüfer“. Eigene Sätze für audit (z. B. „1 Prüfer hat einen Einwand“, „Prüfung · 2 Prüfer“) und „reviewer → Prüfer“ ins Glossar von docs/i18n.md.
- **Beleg:** app/i18n/de/app-agent.json:445 „{count} KIs prüfen mit“, :642 „Prüfer“, :658 „Prüfung · {count} Modelle“, :476 „Modelle: {0}“, :664 „1 Modell hat einen Einwand“, :649 „{done} von {total} Modellen…“, :161 „Agent und Vergleichsmodelle“. Gemessen im deutschen Lauf: Marken-aria-label „… Zweifelhaft: 1 Modell hat einen Einwand · Details öffnen“; Chip-aria-label „Agent und Vergleichsmodelle: …“. docs/i18n.md (Glossar) kennt nur „comparison models → Vergleichsmodelle“.

### I2 · Schlussrunde und Pause heißen je dreifach anders

*Feinschliff · Antwort & Prüfung · Desktop und Handy · Aufwand S · sicher · Prüfer Handy & System (M9, auch K16)*

- **Was man sieht:** Die letzte Runde eines Prüfers heißt im Sheet „Schlussprüfung“, als Fehler „Keine abschließende Prüfung“ und als Abschnitt „Abschließende Anmerkungen“. Ein Halt heißt „pausiert“ („Ein Prüfer hat die Arbeit pausiert“) oder „angehalten“ („Ein Prüfer hat einen Schritt angehalten, bevor er lief“), im Tooltip am Feld „halten ihn bei Zweifeln an“.
- **Apple-Maßstab:** Ein Vorgang, ein Wort: sonst sucht man den Unterschied, den es nicht gibt.
- **Fix:** „Schlussprüfung“ und „pausiert“ durchziehen: „Keine Schlussprüfung: …“, „Anmerkungen der Schlussprüfung“, „Ein Prüfer hat vor einem Schritt pausiert“.
- **Beleg:** app/i18n/de/app-agent.json:973 „Schlussprüfung“, :684 „Keine abschließende Prüfung: {0}.“, :690 „Abschließende Anmerkungen“, :945 „… angehalten, bevor er lief“; app-shell.json „Unabhängige KIs … halten ihn bei Zweifeln an“. — Auch gefunden als K16 („Ein Zustand, sechs Wörter“): run-view.js:227, tab-status.js:14-16, agent-activity.js:58, 661, 671, 904, agent-chat.js:1552-1553 („Needs your decision“), query-send.js:743 („Cancel this run“), Agent-Aktivität „Stop run“.

### I3 · „Failed after“ und „Stopped after“ bleiben englisch

*zweiter Blick · Pausen & Fragen · Desktop und Handy · Aufwand S · sicher · Prüfer Karten (K18)*

- **Was man sieht:** Nach einem Timeout steht im deutschen Verlauf „Failed after 0 Sek.“; nach „Stoppen“ auf einer Karte „Stopped after …“.
- **Apple-Maßstab:** Gemischte Sprache in einer Zeile wirkt unfertig.
- **Fix:** „Failed after“ → „Fehlgeschlagen nach“, „Stopped after“ → „Gestoppt nach“ ins Wörterbuch; SETTLED_VERBS-Liste in den i18n-Test aufnehmen.
- **Beleg:** timeout-de.png: „Failed after 0 Sek.“. agent-activity.js:145-146 baut den Satz, setTitle :162/:177 übersetzt nur das Verb allein; app-agent.json hat nur „Working for“ und „Thought for“ als Verb (Z. 101-102), „Failed after“ und „Stopped after“ fehlen; scripts/i18n.py missing meldet 0, weil die ganzen Sätze vorhanden sind.

### I4 · Vorlesetexte bleiben englisch: „Activity · 2“, „Notes 4“

*zweiter Blick · Antwort & Prüfung · Desktop und Handy · Aufwand S · sicher · Prüfer Handy & System (M7)*

- **Was man sieht:** Auf der deutschen Oberfläche liest VoiceOver das Panel-Symbol als „Activity · 2“ und die Links unter der Antwort als „Notes 4“ und „Sources 1“; der Tooltip am Panel-Symbol ist ebenfalls englisch.
- **Apple-Maßstab:** Wer die deutsche Oberfläche nutzt, hört und sieht nirgends Englisch, auch nicht im Vorlesetext.
- **Fix:** App.t("Activity · {n}", { n }) mit Eintrag „Aktivität · {n}“; in evidenceButton das Label vorher übersetzen: `${App.t(label, null, 'answer tabs')} ${count}`. scripts/i18n.py um Vorlagen in setAttribute('aria-label'/'title', `…`) erweitern.
- **Beleg:** aria-label/title im deutschen Lauf gemessen: button.agent-sidebar-toggle „Activity · 2“; button.agent-evidence-link „Notes 4“. Quelle: static/js/agent-delegation.js:846 (`Activity · ${…}` ohne App.t, kein Eintrag „Activity · {n}“ in app/i18n/de), static/js/agent-review.js:357 (`${label} ${count}` – der Satz als Ganzes hat keinen Eintrag; der sichtbare Text „Anmerkungen“ wird übersetzt). scripts/i18n.py missing meldet trotzdem 0 Lücken. Nebenbefund: auch „Account menu for …“ bleibt englisch, obwohl app/i18n/de/app-shell.json:400 einen Eintrag hat (gesetzt in static/firebase.js:771) – die Attribut-Übersetzung greift dort nicht. Sonst waren alle sichtbaren und vorgelesenen Texte in 11 Audit-Zuständen deutsch.

### I5 · Deutsche Texte: Werkzeug, Werkbank, holprige Sätze

*Feinschliff · Pausen & Fragen · Desktop und Handy · Aufwand S · sicher · Prüfer Karten (K20)*

- **Was man sieht:** „Ergebnis eines Werkzeugs“, „Weit weg von deiner Anfrage“, „… läuft nur, wenn du ihn lässt“, „Ins Key-Feld legen“, „Dein Terminal auf der Werkbank“, „30 Minuten pausiert, ohne dass du entschieden hast, deshalb wurde die Antwort gestoppt.“, und Auslassungen mal „Wird gesendet …“, mal „Nachricht…“.
- **Apple-Maßstab:** Glossar sagt Tool statt Werkzeug; „Werkbank“ ist ein internes Wort; Sätze klingen übersetzt.
- **Fix:** „Tool-Ergebnis“, „Weicht von deiner Anfrage ab“, „… läuft nur mit deinem OK“, „In das Key-Feld“, „Dein Terminal im Arbeitsplatz“, „Gestoppt: 30 Minuten ohne deine Entscheidung.“, eine Ellipsen-Regel ins Glossar.
- **Beleg:** app-agent.json:940 „Ergebnis eines Werkzeugs“ (docs/i18n.md Z.200: „Werkzeug“ ist ausdrücklich Zwangseindeutschung), :889, :946, :929, :816-817; app-shell.json:308 „Wird gesendet …“ vs app-agent.json „Sag dem Agenten, wie es weitergehen soll…“; Wörterbuch: 23 Einträge enden auf „ …“, 91 auf „…“.

### I6 · Fortschrittszeile der Domain-Prüfung ohne Deutsch

*Feinschliff · Agent arbeitet · Desktop und Handy · Aufwand S · wahrscheinlich · Prüfer Karten (K21)*

- **Was man sieht:** Vor der Netzzugriffs-Karte erscheint im deutschen Verlauf vermutlich „The reviewers check this request before you decide.“ auf Englisch.
- **Apple-Maßstab:** Gemischte Sprache.
- **Fix:** Eintrag „Die Prüfer sehen sich die Anfrage an, bevor du entscheidest.“ und agent_delegation.py-Aktivitätstexte in den i18n-Scan aufnehmen.
- **Beleg:** agent_delegation.py:2201 sendet den Satz als Aktivitätstext; im Wörterbuch fehlt er (nur die Variante „… this step before it runs.“, app-agent.json:949). scripts/i18n.py prüft Aktivitätstexte aus app/services nicht (SERVER_TEXT_KEYS, scripts/i18n.py:783-791).

### I7 · Holprige Sätze: „Antwort von Agent“, „es rief ein Tool auf“

*Feinschliff · Antwort & Prüfung · Desktop und Handy · Aufwand S · sicher · Prüfer Handy & System (M11)*

- **Was man sieht:** VoiceOver nennt die Antwort „Antwort von Agent“. Scheitert eine Schlussprüfung, steht „Keine abschließende Prüfung: es rief ein Tool auf, statt seine Prüfung abzugeben“ – der Prüfer ist plötzlich „es“; im Nachbarsatz heißt er „seine Prüfung war nicht lesbar“.
- **Apple-Maßstab:** Kasus- und Genusfehler fallen deutschen Lesern sofort auf.
- **Fix:** „Antwort des Agenten“; Gründe einheitlich aus Sicht des Prüfers: „er hat ein Tool aufgerufen, statt zu prüfen“, „seine Antwort war leer“.
- **Beleg:** app/i18n/de/app-shell.json:96 "Agent answer": "Antwort von Agent" (aria-label von #agentAnswer, gemessen); app-agent.json:692 „es rief ein Tool auf …“ neben :645 „seine Prüfung war nicht lesbar“ (Gründe aus static/js/agent-review.js:535-541).

### I8 · „Prompt Injection“ als einziges Fachwort unter den Haltegründen

*Feinschliff · Pausen & Fragen · Desktop und Handy · Aufwand S · vermutet · Prüfer Handy & System (M20)*

- **Was man sieht:** Unter dem Kartentitel steht als Grund „Prompt Injection“, die anderen Gründe heißen „Sicherheitskritischer Schritt“, „Möglicher Schaden“, „Weit weg von deiner Anfrage“.
- **Apple-Maßstab:** Die Zeile soll in einer Sekunde sagen, was los ist; ein Fachbegriff ist für Laien leer.
- **Fix:** „Versteckte Anweisung“ (der Fachbegriff bleibt im Grundtext des Prüfers) – nur nach Max' OK, er wollte Injection ausdrücklich als Grund.
- **Beleg:** app/i18n/de/app-agent.json:890 "Prompt injection": "Prompt Injection" (holdKinds, static/js/agent-chat.js:1552-1553).

### I9 · Deutsche Auslassungspunkte mal mit, mal ohne Leerzeichen

*Feinschliff · Agent arbeitet · Desktop und Handy · Aufwand S · sicher · Prüfer Lauf (R20)*

- **Was man sieht:** Im selben Lauf: „Denkt nach…“, „Sucht im Web…“, „Antwort wird geprüft…“ – aber „Antwort wird geschrieben …“, „Perspektiven werden verglichen …“, „Wartet auf dich …“.
- **Apple-Maßstab:** Typografische Kleinigkeiten müssen einer Regel folgen, sonst wirkt der Text zusammengesetzt.
- **Fix:** Eine Regel in docs/i18n.md festhalten (Vorschlag: ohne Leerzeichen, wie die Mehrheit und Apple-UI) und per tests/test_i18n.py prüfen.
- **Beleg:** app/i18n/de/app-agent.json:5, 8, 118, 638, 699 (ohne Leerzeichen) gegen app/i18n/de/public.json:225–226 und app-agent.json:926 (mit); im Wörterbuch 73 Einträge ohne, ca. 23 mit Leerzeichen.

## Paket J · Ein System aus wenigen Werten

Die Audit-Oberfläche nutzt 63 verschiedene Abstände, 15 Radien, 22 Zeilenhöhen, 6 Knopfarten und drei Schließen-Kreuze. Wenige Tokens für Abstände und ein Textknopf statt sieben Kopien machen B, C und D billiger und halten das Ergebnis stabil.

Empfehlung: Ja, zusammen mit B und C · Aufwand: etwa 1 Session

### J1 · Drei verschiedene Schließen-Kreuze

*Feinschliff · Antwort & Prüfung · Desktop und Handy · Aufwand S · sicher · Prüfer Handy & System (M13)*

- **Was man sieht:** Die Marken-Karte schließt mit einem Kreuz im grauen Kreis, das Aktivitäts-Sheet mit einem kleineren, dünneren Kreuz ohne Fläche, der Anmerkungen-Leser mit einem dritten in anderer Größe.
- **Apple-Maßstab:** foundation.css verspricht „one drawn X everywhere“ (Apple-Audit G3); im Audit-Modus gibt es drei.
- **Fix:** Sheet-Kreuz auf <button class="close-button"> + App.closeIcon() umstellen; Icon-Knöpfe auf zwei Größen (32/44 touch) und --radius-sm bzw. Pille.
- **Beleg:** .close-button 32 px rund, 16 px, Strich 1,75 (static/css/foundation.css:163-200, Marken-Karte); .agent-sidebar-close 34 px, Radius 10 px, 14 px, Strich 1,4, eigenes SVG (static/css/agent-chat.css:188-189, static/js/agent-delegation.js:357-362); .answer-reader-icon-button 36/32/44 px (static/css/model-answer-reader.css:95, 358, 435). Daneben Icon-Knöpfe mit 28 px/Radius 7 (agent-chat.css:200, 209) und 32 px/Radius 9 (agent-chat.css:418-420).

### J2 · Textlinks in vier Spielarten, siebenmal kopiert

*Feinschliff · Pausen & Fragen · Desktop und Handy · Aufwand M · sicher · Prüfer Handy & System (M14)*

- **Was man sieht:** Die unterstrichenen Textknöpfe sehen leicht verschieden aus: Linie mal kräftig, mal blass, mal fast unsichtbar, mal näher, mal weiter vom Text.
- **Apple-Maßstab:** Ein System aus wenigen Werten: ein Link-Stil, nicht vier.
- **Fix:** Eine Klasse .text-link in foundation.css (Farbe --ink-2, Unterstreichung currentColor 40 %, Offset 3px, coarse 44 px); Karten verwenden sie.
- **Beleg:** Unterstreichung currentColor/Offset 3px: agent-chat.css:469 (.agent-hold-link), 534, 1169, 1210, 1254, 1271, 1303, agent-google.css:21, 112; 35 % currentColor: agent-chat.css:855, 909, agent-workspace.css:193-194 (Offset 2px); var(--line): agent-chat.css:657 (Offset 0.2em), 1463, 1476-1478, 1488-1490, components-consensus-insights.css:286-288, 958-960, 1052-1054. Nahezu dieselben Deklarationen (min-height 32px; padding 4px 0; border 0; …) stehen für .agent-hold-link, .agent-watch-link, .agent-pr-link, .agent-memory-head button, .agent-composer-notice button jeweils neu, die 44-px-Regel je Klasse dazu.

### J3 · Werte außerhalb der Skala: Gewicht 550, 15 px, Radien 7/9 px

*Feinschliff · Antwort & Prüfung · Desktop und Handy · Aufwand S · sicher · Prüfer Handy & System (M15)*

- **Was man sieht:** Prüfernamen und „Falsch/Zweifelhaft“ in den Anmerkungen sind etwas weniger fett als die übrigen Überschriften; Titel im Arbeitsplatz sind eine Zwischengröße. Fällt einzeln kaum auf, macht das Bild aber unruhig.
- **Apple-Maßstab:** typography.css erlaubt vier Gewichte und eine feste Skala; Zwischenwerte sind genau das Rauschen, das Apple vermeidet.
- **Fix:** 550 → var(--font-weight-semibold) bzw. medium; 15px → --font-size-sm/base; rohe px → Tokens; Radien auf --radius-2xs/xs/sm; Fallback korrigieren.
- **Beleg:** font-weight: 550 in static/css/agent-chat.css:633, 643, 650, 660; font-size 15px workspace-view.css:144, 0.9375rem components-consensus-insights.css:107, font: 15px/1.8 in model-answer-reader.css:147; rohe 13px/12px/16px in workspace-view.css:165, 189, 205, 244, 316, 324, 470, 507; Radius 7px (agent-chat.css:200, 209), 9px (:420), 1,5px (:44); falscher Fallback var(--radius-2xs, 3px) (workspace-view.css:419, Token = 6px).

### J4 · Status in der Chatliste unter AA auf der gewählten Zeile

*Feinschliff · Verlauf & Weiterfragen · Desktop und Handy · Aufwand S · sicher · Prüfer Handy & System (M19)*

- **Was man sieht:** Steht der Lauf auf Pause, zeigt die Chatliste „Pausiert“ in Bernstein. Auf der gerade offenen (grau hinterlegten) Zeile ist das Wort etwas zu blass; dasselbe gilt für „Fertig“ in Grün und Fehler in Rot.
- **Apple-Maßstab:** Statuswörter in 12 px brauchen 4,5:1 – die Ampel wurde nur auf Seite und erhabener Fläche abgestimmt, nicht auf der Auswahl.
- **Fix:** Auf .bookmark.is-active die Statusfarbe per color-mix 15 % Richtung --ink abdunkeln, oder --selected in der Seitenleiste auf --raise-selected (deckend, heller) setzen.
- **Beleg:** Gemessen: span.run-entry-status „Pausiert“ #896512 auf #e6e6e6 = 4,28:1 (12 px, hell). Grün #217863 4,28:1, Rot #ad4b57 4,29:1 auf derselben Fläche. Regeln static/css/layout.css:1300-1302 auf .bookmark.is-active { background: var(--selected) } (static/css/shell.css:713-716). Dunkel bestanden.

### J5 · Zwischenüberschrift direkt nach Überschrift steht fast so weit weg wie ein neuer Abschnitt

*Feinschliff · Antwort & Prüfung · Desktop und Handy · Aufwand S · sicher · Prüfer Antwort (A20)*

- **Was man sieht:** „What decides whether it works“ steht allein, weil die Unterüberschrift „Flow temperature“ fast genauso weit darunter steht wie der vorige Abschnitt darüber.
- **Apple-Maßstab:** Nähe zeigt Zugehörigkeit; eine H3 direkt unter ihrer H2 gehört zu ihr.
- **Fix:** .consensus-answer-body :is(h1,h2,h3) + :is(h2,h3,h4) { margin-top: .5em } → H2→H3 ≈ 10 px; gilt auch für den Verlauf.
- **Beleg:** Abstände: p→H2 31,9 px, H2→H3 28,7 px, H2→p 12,8 px, H3→p 11,5 px (typo.rhythm in audit-1280-light-en.json). Ursache: margin 1.5em 0 .6em für alle Überschriften (shell.css:2833-2840).

### J6 · Code in Klammern wirkt wie mit Leerzeichen gesetzt

*Feinschliff · Antwort & Prüfung · Desktop und Handy · Aufwand S · wahrscheinlich · Prüfer Antwort (A21)*

- **Was man sieht:** „(Heizlastberechnung)“ erscheint als „( Heizlastberechnung )“ – der graue Code-Kasten schiebt die Klammern weg.
- **Apple-Maßstab:** Satzzeichen sollen am Wort kleben, nicht an einer Fläche abstehen.
- **Fix:** Inline-Code padding 0 .25em und margin-inline -.05em; oder Fläche weg und nur Monospace in ink-2 (wie Apple-Dokumentation).
- **Beleg:** code 14 px, padding 1px 5px, Hintergrund ink 7 % (typo.code in audit-1280-light-en.json); sichtbar in jedem Screenshot der Liste „Next steps“.

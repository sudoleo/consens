# Agent · Beta

Agent · Beta ist ein eigener Chatmodus für Pro-Nutzer und Admins. Das ausgewählte
Chatmodell schickt jede Nutzerfrage und jeden Bearbeitungsauftrag durch die Consensus-Pipeline:
unabhängige Vergleichsantworten, eigene Synthese und anschließende Prüfung.
Websuche darf die Frage und aktuelle Belege vorbereiten. Nur reine Begrüßungen,
Bestätigungen ohne Frage/Auftrag und unvermeidbare Rückfragen bleiben direkt möglich.
Eine Nutzerbestätigung ist dafür nicht nötig; bei sinnvoll lösbaren Unklarheiten
arbeitet das Modell mit begründeten Annahmen weiter.
Vor jeder inhaltlichen Antwort wartet es auf die Vergleichsergebnisse und bildet
daraus die Synthese. Es darf keine eigene Antwort vorwegnehmen und nachträglich
nur bestätigen lassen. Alle Antworten werden anhand ihrer Begründung, Belege und
Aktualität abgewogen, statt nach Modellnamen oder Stimmenmehrheit. Fehlende
Ergebnisse werden nicht durch unbelegte Erinnerungen ersetzt; verbleibende
Unsicherheit wird inhaltlich erklärt. Der freigegebene Agent-Systemprompt steht
in `prompt_defaults.py` und in der Admin-Konfiguration; der ergänzende
Tool-Protokollprompt in `agent_comparison.py` konkretisiert denselben Ablauf.
Der separate Consensus-Modus behält seinen bisherigen Ablauf und seine Run-Limits.
Agent-Antworten zeigen oberhalb der Nachricht keine Modellüberschrift; dies gilt
auch für frühere Nachrichten und wieder geöffnete Chats.

## Modelle und Bedienung

Der Chatmodell-Picker und die Denkstufe gelten für die nächste Nachricht.
Die Auswahl wird kontogebunden gespeichert und während eines Laufs eingefroren.
Der Chatmodell-Picker gruppiert Modelle nach Anbieter; die jeweilige Modellliste
und die Reasoning-Ebene öffnen im bestehenden Menü.

Der Composer erklärt Sendesperren direkt am Eingabefeld, auch in einer laufenden
Unterhaltung. Bei fehlender Vergleichsauswahl öffnet „Choose models“ den
vorhandenen Picker. Während der Modellkatalog lädt, darf bereits getippt werden;
Senden wartet auf eine verfügbare Auswahl. Leere Nachrichten bleiben gesperrt,
Zitate können wie bisher eigenständig gesendet werden. Nach der Antwort lautet
der Platzhalter „Ask a follow-up“, während der Antwort „Write your next message…“.
Ein vor dem Versand gescheiterter oder gestoppter Start gibt den Entwurf samt
Zitat zurück, sofern der Nutzer inzwischen keinen anderen Entwurf begonnen oder
Chat/Account gewechselt hat. Bereits versendete Nachrichten werden nicht erneut
als ungesendet angeboten.

Agent-Antworten haben seit 2026-10-04 keinen eigenen Copy-Button mehr.
Folgefragen werden direkt im Eingabefeld gestellt.
Contradictions/Review, Answers und Sources verwenden dieselben dezenten Aktionen
mit vorangestellten Icons. Bis 540 px stehen die drei Bereiche gleichmäßig in
einer Zeile, mit Icon und Anzahl über der vollständigen Beschriftung. Alle drei
bleiben auch bei null Ergebnissen erreichbar und haben ausreichende Touch-Flächen.

GET /agent/models lädt die vollständigen Anbieterlisten samt Reihenfolge aus
Firestore `app_config/models` über die gemeinsame Konfiguration. Presets und
Premium-Zuordnung filtern diese Liste nicht zusätzlich. Vor einer neuen Nachricht
wird die Konfiguration ebenfalls gelesen; gespeicherte Antworten lassen sich
ohne diesen Abruf wiederherstellen. Beide Abrufe schreiben nichts in die DB.
IDs, Labels und Routing kommen aus cfg.MODEL_CONFIGS; AGENT_MODEL ergänzt den
Standard (seit 2026-10-04 openai/gpt-6-luna, das günstige Basismodell; vorher
deepseek/deepseek-v4.1-flash). Der Standard trägt die Registry-ID wie alle
anderen Modelle (einmal in der Liste); die OpenRouter-ID wird für ältere Clients
weiter aufgelöst. Er steht im eingebauten Katalog `agent_model_catalog.json`,
damit der Agent auch ohne Live-Katalog startet; die Landing-Mockups zeigen sein
Label (`agent_model_label()`). Hilfsagenten (Delegation) hat Luna nicht geprüft;
die Delegation ist ohnehin standardmäßig aus.

Preise, Kontextgrenzen und Reasoning-Stufen werden aus dem öffentlichen
OpenRouter-Modellkatalog nachgeladen und fünf Minuten zwischengespeichert.
Neue Admin-Modelle benötigen deshalb keinen zusätzlichen Codeeintrag.
Bei Abruffehlern bleiben zuletzt geladene Metadaten und der eingecheckte
agent_model_catalog.json als Rückfall verfügbar. Nicht auflösbare Modell-IDs
bleiben mit einem Hinweis deaktiviert sichtbar; es werden keine Preise erfunden.

Der vorhandene Consensus-Preset-/Model-Picker erscheint daneben als Compare.
Er wählt die Vergleichsmodelle aus derselben Konfiguration; Agent bietet keine
zusätzliche Presetliste und keinen Synthese-/Consensus-Modell-Picker an. Manuelle
Familien-/Modellwahl bleibt möglich. Zwei bis sechs Vergleichsmodelle müssen
gewählt sein. Bei ungültiger Auswahl ist Senden gesperrt; auch direkte Send-Aufrufe
werden vor Chat-Erstellung und Leeren des Entwurfs abgefangen. Der Browser sendet
die konkrete Auswahl, auch eine leere Auswahl wird nicht still durch Defaults
ersetzt. API-Aufrufe ohne Auswahl behalten das zentrale Standardpreset.

Die gemeinsame Bottom-Bar steht im Beta-Chat nur vor der ersten Frage. Danach
liegen ihre Optionen im bestehenden (+)-Menü im Input. Der Composer selbst ist
derselbe wie in Compare und Consensus (`static/css/composer.css`): (+) und Modus
links, Chatmodell, Compare-Auswahl und Senden rechts; auf dem Desktop im Chat
eine Zeile, auf dem Handy eingeklappt (+), Feld und Senden. Ein neuer Chat zeigt
die Startleiste wieder.
Der Moduswähler (Compare / Consensus / Agent, `run-mode.js`) tritt in einem
offenen Agent-Chat zurück: Compare und Consensus brauchen einen neuen Chat,
weil die Chat-Familien serverseitig getrennt sind. „Check contradictions“ schaltet das
Quellenprüfungs-Tool für die nächste Nachricht frei. Der gemeinsame On/Off-Wert
wird beim Senden eingefroren und bei Recovery wiederverwendet. „Reasoning“
(`#composerReasoningToggle`, im (+)-Menü `#agentReasoningMenuOption`) öffnet direkt die vorhandene Reasoning-Auswahl des Chatmodells und zeigt deren
aktuelle Stufe. Modelle ohne wählbares Reasoning und laufende Nachrichten sperren
dieses Menü. „Attach“ lädt PDF, Word, Text und Bilder in den privaten Chat-Dateispeicher.
Siehe [Agent integrations](agent-integrations.md) für Limits und Konfiguration.

Das Modell kann eine ganze Frage oder mehrere begründete Teilfragen
vergleichen. Jede Vergleichsgruppe erhält denselben neutralen Auftrag samt
notwendigem Kontext. Die Vergleichsmodelle kennen den Chatverlauf nicht. Das
Chatmodell muss deshalb bei Bedarf Bezüge konkretisieren und relevante frühere
Anforderungen mitgeben. Keine Vergleichsantwort beeinflusst die andere. Das
Chatmodell erhält Antworten, Quellen, Status und Modellmetadaten und schreibt
die Synthese selbst. Auch bei einem Prüfwunsch wird zuerst eine unabhängige
Vergleichsgrundlage eingeholt.

### Tiefe, Parallelität und Quorum

Einstellungen → **Agent · Beta** (nur für Konten mit Agent-Zugang, gespeichert im
Browser unter `consensio.agentPreferences.v1`) legt drei Werte fest, die jede
Nachricht als `agent_preferences` mitschickt und der Turn in `agent_settings`
einfriert (Teil der Request-Identität bei Recovery): **Answer depth**
(`auto` lässt das Chatmodell wählen, `quick`/`full` überschreiben seine Wahl; der
Orchestrierungsprompt nennt die feste Tiefe) und **Answer start**
(`balanced` wie unten beschrieben, `fast` ab der Hälfte der Antworten mit 1,1-facher
Nachfrist und mindestens einer Sekunde, `all` wartet auf jedes Modell) und
**Agent freedom** (`autonomy`, siehe unten). „Check contradictions“ bleibt im
Reiter Runs und im Composer.

### Agent freedom: geführt oder frei

`guided` (Standard) ist der bisherige Ablauf: jeder Vergleich fragt alle gewählten
Vergleichsmodelle. `free` (Opt-in) gibt dem Chatmodell als einziges Ziel die
bestmögliche Antwort und lässt es den Weg wählen: `compare_models` bekommt das
Pflichtfeld `models` (`free_compare_args`: das Schema zählt genau die Familien der
Compare-Auswahl dieses Turns samt Modellnamen als Enum auf, mindestens zwei), der
Orchestrierungsprompt den Zusatz `FREE_PROMPT`. Das Chatmodell entscheidet so pro
Vergleich, welche Familien es fragt, und wie viele Runden es braucht (im Chat ohnehin
nur durch das Tokenkonto begrenzt). Die Auswahl im Compare-Picker bleibt der Pool:
der Nutzer bestimmt, welche Modelle infrage kommen, der Agent, welche er wann fragt.
Jeder Vergleich speichert die gefragten Familien als `asked` (im geführten Modus die
ganze Auswahl); Quorum, `failed_models`, `pending_models` und `status` beziehen
sich auf sie. Welcher Modus lief, steht im Turn unter
`agent_settings.agent_preferences.autonomy` – die Grundlage für den Vergleich
free gegen guided.

Zwei Regeln setzt der Server durch, nicht der Prompt:

- **Mindestens zwei Familien je Vergleich.** Unbekannte Familien und weniger als
  zwei Einträge scheitern schon an der Schema-Validierung, eine doppelt genannte
  Familie an `ComparisonTools._choose` – jeweils als Toolfehler vor jedem bezahlten
  Aufruf. Damit hat jeder Vergleich etwas, das Differences und Coverage
  gegeneinander prüfen können.
- **Keine ungeprüfte Sachantwort.** Antwortet das Chatmodell im freien Modus ohne
  jeden Vergleich direkt, veröffentlicht der Server den Text nicht, sondern
  verlangt einmal (`DelegationLoop._free_floor`) einen Vergleich oder die
  Bestätigung, dass es nur ein Gruß, eine Quittung oder eine nötige Rückfrage ist.
  Bestätigt es, gilt die Antwort wie im geführten Modus als direkte Antwort.

Danach laufen Synthese und Judges unverändert; der Judge kommt in beiden Modi
immer am Ende. Ältere Turns ohne `autonomy` gelten bei der Recovery-Identität als
`guided` (`stored_preferences`).

`compare_models` hat zwei Entscheidungsfelder. `depth` (Standard `full`) steuert
die Längenvorgabe der Vergleichsmodelle: `quick` für kurze Sachfragen, kleine
Folgefragen, Umformulierungen und Alltagsrat (etwa 1500 Zeichen, falls die Aufgabe
nicht mehr braucht), `full` für Analysen, Entscheidungen, Gesundheit, Recht, Geld
und ausführliche Ausgaben (keine Längenvorgabe). Im geführten Modus antworten alle
gewählten Vergleichsmodelle in beiden Stufen; die Auswahl im Compare-Picker wird nicht
still verkleinert. Im freien Modus wählt das Chatmodell sie pro Vergleich (`models`).
`next_step` ist Pflicht: `answer` beim letzten Vergleich lässt den Server direkt
Synthese und Prüfung ausführen, ohne weitere Orchestrierungsrunde, die nur
`judge_answer` aufrufen würde. `more_work` gilt, wenn noch ein Vergleich, ein
Dokument oder eine Aktionsvorbereitung folgt; danach ruft das Chatmodell wie
bisher `judge_answer` auf. Der direkte Weg gilt nur, wenn der letzte Toolaufruf
ein angenommener Vergleich war, alle Worker geprüft sind und für die Nachricht
kein Google-Zugriff freigegeben ist.

Alle Vergleichsmodelle laufen gleichzeitig (eigener Semaphore je Vergleich,
unabhängig von `max_parallel` der Worker-Delegation); Differences und Coverage
haben eigene Plätze. Damit gleichzeitige Reservierungen sich nicht gegenseitig
blockieren, erhält jede Vergleichsantwort als Output-Grenze einen fairen Anteil
(60 % des freien Tageskontingents geteilt durch die Modellanzahl), höchstens die
Completion-Grenze des Modells. Weil der gespeicherte Review (600 kB) alle
Antworttexte enthält, teilen sich die Vergleichsantworten eines Turns zusätzlich
300000 Zeichen (etwa vier Zeichen je Token); die Grenze fällt nie unter
`MAX_TOKENS`. Das Chatmodell erhält für seine Planung je Antwort höchstens
`result_chars` Zeichen (`text_shortened_for_routing`), die Synthese immer den
vollständigen Text. Vergleichsantworten
und der Antwortschritt starten bei Konkurrenz mit einer kleineren, noch
passenden Grenze (mindestens `MAX_TOKENS`), statt auf das Settlement anderer
Aufrufe zu warten.

Die Synthese wartet nicht auf das langsamste Modell. Sobald das Quorum vorliegt
(`full`: alle bis auf eines, `quick`: die Hälfte, jeweils mindestens zwei),
bekommen Nachzügler noch das 1,5-fache (`quick`: 1,25-fache) der Zeit bis zum
Quorum, mindestens zwei Sekunden. Danach beginnt die Synthese mit den vorhandenen
Antworten (`synthesis_providers`). Laufende Modelle stehen bis dahin als
`pending_models` im Review. Eine Antwort, die während der Synthese eintrifft,
wird mit `late: true` markiert: Sie gehört zur Prüfbasis von Differences und
Coverage, nie zum Antworttext. Wer beim Start der Judges noch schreibt, wird
gestoppt und als fehlend mit `late_cutoff` geführt; die Prüfung nutzt die
übrigen Antworten. Der Antworttext bleibt in jedem Fall unverändert. Was ein so
gestopptes (oder mitten in der Antwort ausgefallenes) Modell schon geschrieben
hatte, bleibt als `failed_models[].partial_text` gespeichert und steht unter
Answers als „Incomplete“ — lesbar, aber weder in der Antwort noch in ihrer
Prüfung, weil ein halber Text beim Differences-Judge falsche Auslassungen
erzeugen würde (wie unterbrochene Antworten im Consensus-Modus).

## Antwortversionen und Prüfungen

Nach den Vergleichen leitet `judge_answer` in die Antwortphase über. Vor seiner
Ausführung streamt dasselbe Chatmodell die vollständige Synthese in einem eigenen
Schritt ohne Tools und Suche. Vorherige Tools im selben Batch werden zuerst
ausgeführt, ebenso die Prüfung aller unterstützenden Agenten. Erst wenn dieser
Schreibschritt vollständig endet, prüfen
Differences und Coverage genau den bereits sichtbaren Text. Eine Einleitung neben
einem verfrühten Judge-Aufruf zählt nicht als Antwort. Der Schreibschritt wird wie
jeder Modellaufruf abgerechnet. Bei Abbruch oder Tokenlimit bleibt der Teiltext
ungeprüft erhalten; die Judges starten nicht.
Der Schreibschritt verwendet die konfigurierten Consensus-Anweisungen mit der
eigenen beratenden Stimme des Chatmodells. Er erhält den tatsächlichen Gesprächs-
verlauf sowie Vergleichsantworten, Quellen und zuletzt geprüfte Worker-Ergebnisse
oder deren geprüften Ersatztext. Überarbeitung entzieht alten Ergebnissen die
Freigabe. Er erhält keine internen Toolgespräche,
Statusfelder oder Reasoning-Fortsetzungen. Die Agent-Anweisungen steuern weiterhin
die Orchestrierung. Die Reasoning-Ausgabe des Providers wird für den Schreibschritt
unterdrückt; Modell und gewählte Denkstufe bleiben erhalten. Der sichtbare Antwort-
text wird nicht nachträglich durch Stichwortfilter verändert.
Beendet das Modell die Orchestrierung ohne nötigen Prüfaufruf, führt der Server
die bestehenden Prüf-Tools einschließlich ihrer Fallback-Judges selbst aus.
Zusätzliche Erinnerungsrunden entfallen. Das Backend lässt keinen stillen
ungeprüften Abschluss zu. Routing-Text bleibt von Beginn an gepuffert, damit
Einleitungen nicht kurz im Antwortbereich erscheinen und wieder verschwinden.
Vollständige Direktantworten wie Begrüßungen werden einmalig ausgegeben.
Bei Abbruch vor dieser Entscheidung wird der ungeklärte Routing-Text auch in
Recovery nicht zur Antwort. Bereits gestreamte Synthese-Teilantworten bleiben
wie bisher gespeichert und ungeprüft lesbar.

Differences und Coverage verwenden im Beta-Chat ausschließlich die
Standard-Judges aus `app_config/models.judge_models`, auch bei einem teuren
Chatmodell. Zuerst wird eine andere Modellfamilie gewählt (standardmäßig Luna,
bei OpenAI-Chats Gemini). Nach dem begrenzten Retry folgt der konfigurierte
Gemini-Standard-Judge, aktuell Gemini 3.5 Flash-Lite, ausdrücklich auch bei
Gemini als Chatmodell. Ist Gemini bereits der primäre Judge, übernimmt der
OpenAI-Standard-Judge. Beide Prüfungen behalten die niedrige Judge-Denkstufe;
die Pro-Tabelle und weitere Modellfamilien werden nicht als Ausweichstufen genutzt.

Bei eingeschaltetem „Check contradictions“ folgt das Tool `check_contradictions`.
Es verwendet den bestehenden Contradiction Judge für große, faktisch prüfbare
Widersprüche und bereits vorhandene Originalquellen. Seit 2026-10-03 läuft die
Prüfung als Hintergrundjob in derselben Queue wie in Consensus
(`source_check_jobs.py`): das Tool reiht je Vergleich einen Job ein, der Turn
endet sofort danach mit dem Jobverweis, und die Seite verfolgt den Job, bis er
fertig ist. Abruf, validierte Zitate, Ausschlussgründe, konfigurierte
Judge-Modelle und Verfügbarkeits-Fallbacks sind dieselben wie in Consensus.
Die Kosten bleiben auf dem Tokenkonto: der Job reserviert seine Obergrenze bei
der Aufnahme und bucht die gemessenen Tokens mit seinem Ergebnis; reicht das
Konto nicht, wird nicht geprüft (`token_budget_exhausted`).
Ohne passende Widersprüche wird die Quellenprüfung ohne Job, Abrufe oder
bezahlten Quellen-Judge übersprungen. Ausgeschaltet ist das Tool nicht verfügbar;
Differences und Coverage bleiben Bestandteil jedes Modellvergleichs.
`judge_answer(finalize=true)` beendet bei eingeschalteter Quellenprüfung erst
nach dem Einreihen; das Modell erhält `check_contradictions` als nächsten
Tool-Schritt und sieht selbst keine Quellenurteile. Fehlerhafte oder fehlende
Belege bleiben ausdrücklich ungeprüft. Ergebnisse und Originalbelege stehen
direkt an den Widerspruchskarten und als kurze Notiz am Contradictions-Link
(„checking sources“ → „1 settled by sources“), auch im gespeicherten Verlauf.
Eine neue Antwort oder Vergleichsgrundlage braucht eine neue Prüfung;
wiederholte Tool-Aufrufe derselben Prüfung reihen keinen weiteren Job ein.

Die Anzeige unterscheidet vollständig, teilweise, fehlgeschlagen, fehlend und
abgebrochen. Vollständig bedeutet, dass beide Judges ihre Aufgabe abgeschlossen
haben und die Vergleichsgrundlage vollständig ist. Modellübereinstimmung ist
keine unabhängige Faktenprüfung. Ohne Vergleich läuft keine automatische Prüfung.

Die Prüfung bindet den SHA-256 der Antwort und den Hash der konkret verwendeten
Modellantworten samt Quellen. Nach der Prüfung wird der Text nicht umgeschrieben.
Die erste fertige Synthese bleibt für diesen Turn unverändert. Auch
`finalize=false` öffnet keine weitere Schreib-/Prüfrunde; das Feld bleibt nur zur
Kompatibilität akzeptiert. Weitere Vergleiche sind nur vor der Synthese möglich.
Überarbeitungen erfolgen erst auf eine neue Nutzernachricht. Ankündigungen weiterer
Tool-Aufrufe zählen noch nicht als Syntheseversion. Jeder Teilvergleich behält
seine eigene Prüfung: dieselben Modelle zählen nicht mehrfach als unabhängige
Stimmen. Nicht abgedeckte Aussagen bleiben in der Coverage sichtbar.

Die Synthese spricht als beratender Assistent und begründet Empfehlungen anhand
der Nutzerkriterien und der verglichenen Aussagen. Persönliche Präferenzen oder
Erlebnisse der Vergleichsmodelle werden nicht übernommen. Bedingungen und
Unsicherheit bleiben an der jeweiligen Aussage; Fakten und daraus abgeleitete
Empfehlung werden klar formuliert. Unbelegte Superlative und eine künstliche
Einstimmigkeit sind nicht vorgesehen. Die Judges prüfen weiterhin auch
Empfehlungen; tatsächliche Unterschiede bleiben sichtbar.

Aktivitäten verwenden die bestehende Agent-Seitenleiste mit Status, Usage und
aufklappbaren Details. Oberhalb der Antwort steht ein überlappender Modellstapel
mit den Icons des zentralen Katalogs; wiederholte Aufrufe desselben Modells
belegen einen Platz, bleiben aber einzeln in der Aktivität sichtbar.
In der Agent-Seitenleiste schimmert die Zählerzeile während eines Modellaufrufs.
Solange noch keine Tokenmessung vorliegt, zählt sie empfangene Antwort- und
sichtbare Reasoning-Zeichen als `chars`. Sobald der Anbieter Tokenzahlen liefert,
zeigt sie die gemessene Summe aus Input und Output. Es werden keine Tokens aus
Zeichen geschätzt. Nach Abschluss/Abbruch endet die Animation; gespeicherte
Ansichten bleiben statisch. Reduced Motion und Forced Colors deaktivieren den
Schimmer.
Während Differences und Coverage die feste Antwort prüfen, läuft ein leichter
Lichtschimmer im Takt der Thinking-Überschrift über die Antwort (Overlay in
Seitenfarbe, kein Textverlauf, damit Tabellen, Code und Links lesbar bleiben);
er blendet aus, sobald die Prüfung endet. Die Markierungen erscheinen dann sofort,
auch wenn eine Quellenprüfung noch läuft, und streichen sich beim ersten Mal in
Lesereihenfolge an wie ein Textmarker (höchstens etwa 0,9 s Versatz, Badges
folgen). Erneutes Rendern derselben Antwort und gespeicherte Chats zeigen sie ohne
Animation; Reduced Motion und Forced Colors verzichten auf beides.
Rund um die Antwort gilt ein Farbsystem: Antworttext `--ink`; Thinking samt
Verlauf und Tools, Aktionen und Evidenzlinks `--ink-2` (Hover `--ink`, Aktionen
einheitlich Gewicht 500); Zähler und Metatext `--ink-3`. Es gibt kein separates
Schwarz mehr.
Unter der Antwort stehen ein kompakter Prüfstatus und Links zu Widersprüchen,
Einzelantworten und Quellen. Rote Textmarkierungen öffnen unmittelbar die
passende Widerspruchskarte im gemeinsamen Consensus-Antwortleser. Modelllinks
zeigen dort die formatierte Originalantwort. Bei mehreren Teilvergleichen wählt
ein beschriftetes Auswahlfeld die konkrete Markierungsgrundlage. Kontext und
frühere Antwortversionen stehen in den Details des Lesers. Live-Ansicht und
gespeicherter Verlauf verwenden denselben Review-Snapshot.
Fehlt nur eine Modellantwort, während Differences und Coverage vollständig
vorliegen, bleibt die Zeile unter der Antwort leer; der Leser nennt das Modell
und den Grund. Unter der Antwort steht nur etwas, wenn die Prüfung selbst
eingeschränkt ist (weniger als zwei Antworten, fehlender Differences- oder
Coverage-Judge).
Der Review bleibt technisch `partial`; fehlende Stimmen werden nicht als
Zustimmung gezählt. `Answers` zählt nur vollständige Antworten, der Leser zeigt
auch die ausgefallenen Modelle und bei neuen Runs deren sicheren Fehlergrund
(z. B. Provider-Rate-Limit). Fehlende Prüfer, ungeprüfte Sätze und unvollständige
Quellenprüfungen werden separat erklärt. Alte gespeicherte Runs nutzen dafür
ihre vorhandenen Judge-Metadaten; sie werden nicht erneut kostenpflichtig geprüft.
Grüne Markierungen zeigen die Zustimmung per Mausvorschau oder Tastaturfokus.
Ein nachlaufendes Scroll-/Resize-Ereignis positioniert die Vorschau neu, wenn der
Zeiger noch auf der Passage steht; auch nachträglich angeschlossene Mäuse werden
erkannt. Klick/Tap öffnet weiterhin die vollständigen Details.
Die Quellenansicht vereinigt Quellen aus der Chat-Recherche, allen
Vergleichsgrundlagen und expliziten Links in den Antwortversionen. Sie ist auch ohne
Vergleich verfügbar. Provider-/Suchquellen werden auf dem Turn gespeichert;
alte Turns können sie weiterhin aus ihrem Aktivitätsjournal darstellen.
Im Antworttext erscheinen Quellen als hochgestellte Nummern mit der gemeinsamen
Quellenvorschau bei Hover oder Tastaturfokus. Ausgeschriebene URLs werden durch
diese Verweise ersetzt; Namen wie „Self-Consistency“ bleiben lesbar. Dieselbe
Darstellung gilt für gespeicherte und unvollständige Antworten, frühere Versionen
und Vergleichsantworten. Die Nummerierung folgt der jeweiligen Quellenliste;
der gemeinsame Turn-Katalog bleibt beim Grundlagenwechsel gleich. Originaltext
und Judge-Bindung bleiben unverändert. Code und Zahlennotation wie `[1]` werden
nicht als Quellen interpretiert.

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
Antwortbereich zeigt während des Laufs kurze Reasoning-Absätze unterhalb
des standardmäßig geschlossenen Thinking-Disclosures. Der aktuelle Arbeits-,
Tool- oder Review-Status steht genau einmal in dessen durchgehend lesbarer
Überschrift; eine zweite Statusbox entfällt. Nach Laufende verschwindet diese Vorschau. Nur explizites
Aufklappen zeigt alle verfügbaren Schritt-Zusammenfassungen, Tools und Usage;
es gibt keine automatische Expansion und keine vertikalen Zitatlinien.
Alte, ausführliche
Aktivitäten werden beim Anzeigen ebenfalls gekürzt; bestehende Daten werden
nicht migriert. Private Provider-Fortsetzungsdaten bleiben ausschließlich im
laufenden Protokoll und werden nicht als sichtbare Aktivität gespeichert.

## Tageskontingent

Seit 2026-10-01 teilt Agent das Tageskonto mit Compare, Consensus und Deep
Think (siehe codebase-map, „Ein Tokenkonto für alle Modi“). Das Limit pro
Stufe (Free/Plus/Pro/Admin) und die erwarteten Tokens eines typischen Laufs
liegen in app_config/agent_budget und sind in Admin → Limits speicherbar
(Defaults: Pro/Admin 5 000 000 Tokens pro UID und UTC-Tag, Reset um 00:00 UTC).
`AGENT_DAILY_TOKEN_LIMIT` gibt es nicht mehr. Der Button „Reset all
allowances“ setzt das Konto aller Nutzer über eine neue Budgetgeneration
zurück, ohne Nutzer-Scan. Begonnene Aufrufe rechnen weiter gegen
ihre ursprüngliche Generation ab. Einstellungen greifen spätestens beim nächsten
Config-Refresh nach 30 Sekunden; der Admin-Client verwendet Revisionsschutz.
Der bestehende
Kontingent-Ring im Sidebar-Footer zeigt im Agent-Chat den verbleibenden Anteil
als abgerundete Prozentzahl des noch unverbrauchten Budgets: Limit minus
gemessene verbrauchte Tokens. Reservierungen lassen die Anzeige nicht mehr springen.
Sein Panel trennt unverbrauchte, für neue Calls verfügbare und reservierte Tokens
und enthält die Reset-Zeit. Consensus zeigt dort weiterhin das Run-Limit; der Composer enthält
keine Budgetzeile. Das Kontingent gilt gemeinsam für Chat, delegierte Worker,
Vergleichsmodelle und alle Judge-/Repair-/Retry-Aufrufe.

Gezählt wird Provider-Input plus Provider-Output. Cache-Reads/-Writes sind bereits
im Input enthalten, Reasoning bereits im Output. Diese Kategorien werden für
Transparenz gespeichert, aber niemals zusätzlich zum Kontingent addiert.
Provider-Gesamtkosten haben Vorrang; ohne sie berechnet die App eine gekennzeichnete
Katalogschätzung. Kosten werden erfasst; im Agent-Chat gilt allein die zentrale
Tokenquote als Verbrauchsgrenze.

Vor jedem bezahlten Schritt reserviert der Server transaktional das erwartbare
Inputvolumen mit Sicherheitsaufschlag und erlaubtem Output zusammen mit dessen
dedupliziertem Beleg. Der Input wird lokal tokenisiert (tiktoken/cl100k plus
25 % und Protokollreserve), einschließlich Tools und Antwortschemas.
Settlement ersetzt die Reserve genau einmal durch gemessene Tokens. Bei
fehlender finaler Usage endet die Reservierung ebenfalls; unbekannter Verbrauch
bleibt als unbekannt gekennzeichnet und wird nicht als Schätzung abgebucht. Abbrüche und Fehler
schenken keine bereits verbrauchten Tokens zurück. Replays führen keinen neuen
Call aus. Beim UTC-Wechsel zählt ein Call zu seinem Starttag; nur ungenutzte
Synthese-/Judge-Reserven wandern auf den neuen Tag.
Die Prozentanzeige erhält Live- und terminale Kontingent-Snapshots auch bei
Fehlern; das Panel nennt zusätzlich reservierte Tokens. Ein Restbudget kann
kleiner als die nötige Reserve für den nächsten Aufruf sein. Dieser Fall wird
mit konkreten Zahlen als unzureichende Reserve erklärt, nicht als leeres Budget.
Kann die optionale Suche nicht reserviert werden, darf derselbe Schritt vor
jedem Provider-Aufruf ohne Suche neu zugelassen werden. Das Modell wird über
fehlende neue Recherche informiert; reicht auch die reine Antwort nicht ins
Budget, endet der Lauf weiterhin vor dem bezahlten Aufruf.
Web Search bleibt nach Reasoning und Tool-Fortsetzungen erlaubt. „Skipped ·
budget reserve“ bezeichnet eine unzureichende Reserve für Suchkontext und
Folgeantwort, kein generelles Suchverbot nach dem Denken.

Die Wiederherstellungsaktion prüft denselben Lauf mit derselben Request-Identität.
„Recover saved answer“ erscheint bei bestätigt gespeichertem Antworttext,
„Check saved answer“ bei unbekanntem Zustand und „Check run status“ bei einem
noch laufenden Producer. Eine abgelaufene Lease wird bei dieser Abfrage beendet.
Mehrfachklicks werden zusammengeführt; es entsteht kein weiterer Bookmark.
Fehlgeschlagene Turns bleiben auch ohne Antworttext als Bookmark erhalten;
Frage, Fehlergrund, Aktivität und vorhandene Vergleichsantworten bleiben lesbar.
Nach einem Transportabbruch bleibt eine reine Wiederherstellungsabfrage möglich.
Enthält das Fehlerereignis bereits einen gespeicherten Turn samt Bookmark,
übernimmt die Oberfläche beides sofort und zeigt den Fehler weiterhin an.

Unter jedem Abbruch nach dem Absenden (Provider busy, Timeout, verlorene
Verbindung, gespeicherter Fehl-Turn) steht „Retry“: Es schickt dieselbe Frage
mit denselben Dateien als neuen Turn in denselben Chat und denselben Bookmark,
mit neuer Request-Identität und dem *jetzt* gewählten Modell. Bei
`provider_rate_limited`/`provider_unavailable` steht daneben „Choose another
model“. Budget-Absagen behalten ihre eigenen Aktionen; ein vor dem Start
abgelehnter Text kommt wie bisher ins Eingabefeld zurück (kein Retry).

Kommt 45 s lang kein Byte über den Stream, gibt der Browser nicht sofort auf:
Manche Netze (Firmen-Proxys, Virenscanner) halten einen Event-Stream bis zum
Ende zurück. Er fragt per `recover_only` mit derselben Identität nach. Ein
gespeicherter Turn (fertig oder fehlgeschlagen) beendet das Warten,
`recovery_state: running` hält den Stream offen, zweimal ohne Turn bricht ab.

Toolnamen in Reasoning-Auszügen bleiben normaler Text. Nur bestätigte laufende
Tool-Aufrufe erhalten eine dezente Statuszeile. Thinking bleibt geschlossen.
Die Agentenleiste öffnet sanft und zeigt gemessene Input+Output-Tokens statt
Dollarbeträgen; unbekannte/teilweise Usage bleibt erkennbar. Judge-Details
erscheinen sofort aus bereits geladenen Sitzungsdaten, ohne zusätzlichen
Datenbankabruf. Andere Details zeigen beim ersten Laden einen Skeleton und
bleiben anschließend im Cache. Reduced Motion deaktiviert die Animationen.
Während Live-Session-Ereignisse eintreffen, entfallen die früheren 2,5-Sekunden-
Vollabfragen. Nach zehn Sekunden ohne Update wird bei sichtbarem Tab abgeglichen;
am Ende wird der terminale Zustand noch einmal geladen. Die Lease-Prüfung teilt
ihren Receipt-Snapshot mit der Listenansicht, statt ihn doppelt zu lesen.

Jeder tatsächlich anstehende Modellaufruf reserviert seinen geschätzten Input
und erlaubten Output; Suchkontext zählt erst nach der Suche. Blockieren noch
laufende Calls das Budget, warten neue Calls abbrechbar auf deren Settlement.
Sie erzeugen während des Wartens keine eigenen Reserven oder Provideraufrufe.
Ohne solche Konkurrenz entfällt bei Bedarf zunächst optionale Suche; danach
wird die tatsächliche Outputgrenze passend zu Restbudget und Kontextfenster
gesetzt. Explizite Reasoning-Budgets behalten ihren erforderlichen Platz.
Reicht es auch für Input und eine minimale Antwort nicht, wird vor dem Provider
gestoppt. Eine am Outputlimit abgeschnittene Antwort bleibt als Teilantwort erhalten.
Eine zusätzliche pauschale Reserve für zukünftige Synthese-/Judge-Aufrufe entfällt
im Chat. Reicht das Tagesbudget für einen nächsten Aufruf nicht, bleiben vorhandene
Ergebnisse mit ihrem tatsächlichen, gegebenenfalls unvollständigen Prüfstatus erhalten.

Das zentrale Tageskontingent ist die einzige Verbrauchsgrenze des Agent-Chats.
Es gibt kein Tool-, Such-, Nachrichten- oder Dollarbudget pro Lauf. Alte
Admin-Werte dafür werden von `AgentPolicy.for_chat` nicht angewendet;
Legacy-/Evaluierungsaufrufe und die bestehende Consensus-Pipeline bleiben begrenzt.
Seit 2026-10-05 gelten pro Nachricht weiche Schutzgrenzen (Konstanten in
`AgentPolicy.for_chat`, nicht im Admin), damit eine Schleife gültiger Aufrufe
nicht das ganze Tageskonto in einem Turn verbrennt (jeder Orchestrierungsschritt
sendet den gesamten Verlauf erneut, die Kosten wachsen quadratisch):

| Schutzgrenze pro Nachricht | Standard | Verhalten |
|---|---|---|
| Vergleiche (`turn_comparisons`) | 4 | Der fünfte `compare_models` liefert einen Tool-Fehler („call judge_answer now“), nichts Bezahltes startet; der vierte meldet „last comparison allowed“. |
| Orchestrierungsschritte (`turn_steps`) | 24 | Vor dem 25. Routing-Schritt: Wrap-up (siehe unten). |
| Zeit (`turn_seconds`) | 15 min | Vor dem nächsten Routing-Schritt: Wrap-up; harter Stopp in `_check` (auch mitten im Schritt, Watcher bricht ab) nach weiteren `TURN_WRAP_UP_SECONDS` = 5 min. |
| Identische Toolcalls (`turn_identical_calls`) | 2 | Gleicher Toolname + gleiche normalisierte JSON-Argumente (ohne `status_update`): 3. Aufruf wird mit Tool-Fehler abgelehnt, der 4. beendet den Turn per Wrap-up. `wait_agents` ist ausgenommen. |

Wrap-up: Gibt es einen Vergleich mit mindestens zwei Antworten (oder schon eine
Synthese) und sind alle Worker geprüft, schreibt der Server die Synthese und
startet die Judges wie im Normalpfad; der Turn endet regulär. Sonst endet er mit
`AnalysisBudgetExceeded` (`run_limit`, „… The available results have been saved;
send a follow-up message to continue.“); gespeicherte Vergleiche bleiben erhalten.
Technische Grenzen schützen Providerprotokoll, Speicher und Parallelität:

| Grenze | Standard |
|---|---|
| Parallele Worker-Unteraufrufe | 2 (`max_parallel`, nur Delegation) |
| Parallele Vergleichsantworten | alle gewählten Modelle eines Vergleichs |
| Parallele Judge-Aufrufe | 6 |
| Antwortmodelle pro Vergleich | vorhandene Auswahl, mindestens 2 |
| Vergleichsantwort | Completion-Grenze des Modells (höchstens 65536), begrenzt durch fairen Budgetanteil und Reviewgröße; Längenvorgabe nur bei `depth=quick`. Eine am Output-Limit abgeschnittene Antwort bleibt als Evidenz erhalten (`answers[].truncated`); ohne Text gilt sie als `output_limit` |
| Synthese | Completion-Grenze des Chatmodells (höchstens 32768), begrenzt durch Kontextfenster und Restbudget |
| Orchestrierungsschritte | AGENT_MAX_OUTPUT_TOKENS, standardmäßig 4096 |
| Geprüfte Antwortsätze | 320; Coverage prüft in parallelen Fenstern zu 80 Sätzen |
| Kontext | Modellfensterprüfung; initialer Chatverlauf maximal 120000 Zeichen |
| Review-Snapshot | maximal 600 kB |
| Gleichzeitige Runs je UID | 2 |
| Produzenten pro Prozess | AGENT_MAX_CONCURRENT_RUNS, standardmäßig 16 |

Reservierungen sind Zulassungskontrollen, keine Garantie für die tatsächliche
Provider-Rechnung. Meldet der Provider höheren Verbrauch, wird er vollständig
verbucht und weiterer Verbrauch blockiert. Unbekannte Nutzung ist kein Nullwert.
Drei aufeinanderfolgende Tool-Batches ohne gültig ausgeführten Aufruf stoppen
als Protokollstillstand, statt das Tageskontingent mit derselben ungültigen
Anfrage aufzubrauchen. Gültige Arbeit begrenzen nur die Schutzgrenzen pro
Nachricht oben.

## Recherche, Delegation und Providerprotokoll

### Websuche

Einzige Quelle für das Suchverhalten im Agent-Modus; Code und Kommentare
verweisen hierher.

**Eine Konfiguration für alle Modelle.** `agent_tools.search_tools` baut für
jedes Modell dasselbe Tool wie der Consensus-Modus (`engines.web_search_tool`,
Engine `auto`), begrenzt auf 5 Treffer à 2000 Zeichen pro Runde. Welcher
Suchweg greift, entscheidet OpenRouter, nicht unser Code:

| Familie | Suchweg unter `auto` |
|---|---|
| Gemini | Google-Grounding (eigene Suche) |
| OpenAI | OpenAI-Websuche (eigene Suche) |
| Anthropic | Anthropic-Websuche (eigene Suche) |
| DeepSeek, Kimi, GLM, Mistral, Meta | Exa (keine eigene Suche auf OpenRouter) |
| Grok | **Exa, fest** — einzige Ausnahme im Code (`engines._SEARCH_ENGINE_BY_PROVIDER`) |

Grok ist ausgenommen, weil xAIs eigene Suche jede Begrenzung ignoriert
(gemessen 2026-08-31: 66k Prompt-Tokens, ≈ 0,10 $, 20 s bis zum ersten Token;
im Betrieb bis zu 55 Quellen für eine Wetterfrage). Die Trefferbegrenzung wirkt
sicher nur auf Exa; ob die eigene Suche der Anbieter sie beachtet, ist nicht garantiert.

**Wer wie oft sucht.** Das ist die einzige Stellschraube, und sie ist eine
Produktentscheidung, keine Modell-Sonderlösung:

- Vergleichsmodelle: eine Runde, unabhängig von `quick`/`full`. Ihr Prompt
  (`agent_comparison.comparison_system_prompt`) nennt das Datum, verlangt bei
  zeitabhängigen Fakten eine Suche mit Monat und Jahr in der Anfrage und
  erklärt Angaben im `context` ohne Quelle für ungeprüft.
- Orchestrator: vor dem ersten Vergleich bis zu drei Runden
  (`ORCHESTRATOR_SEARCH_ROUNDS`); die Funde gehen mit URLs als `context` an alle
  Vergleichsmodelle, eigene Erinnerung an Produkte, Versionen oder Preise nicht.
  Danach höchstens eine Runde pro Schritt.
- Judges und der Antwortschritt suchen nie.

Ohne Datum und Suche hatten sich fünf Vergleichsmodelle auf denselben
veralteten Trainingsstand geeinigt („Claude 3.5 Sonnet, GPT-4o“ als neueste
Modelle) — ein Scheinkonsens, den die Prüfung nicht erkennen kann.

**Reservierung.** Jede Suchrunde reserviert für jedes Modell gleich
`agent_costs.SEARCH_INPUT_TOKENS` (32k), höchstens so viel, wie das
Kontextfenster noch fasst. Grundlage, gemessen 2026-10-01 pro Runde: eigene
OpenAI-Suche bis ≈ 11k Tokens, Exa (5 × 2000 Zeichen) ≈ 2,5k, Anthropic ≈ 2k,
Google ≈ 0 (pro Anfrage abgerechnet). Die Abrechnung bucht den echten Verbrauch;
eine ungewöhnlich große Runde kann das Tageslimit deshalb leicht überschreiten
(weiche Grenze, kein Abbruch). Die Suchgebühr kommt aus dem Katalogpreis des
Modells, sonst gilt die Exa-Pauschale. Passt eine Reservierung nicht, stuft
`smaller_search` ab (mehrere Runden → eine → keine); parallele
Vergleichsantworten stufen ab, statt auf Geschwister zu warten.

**Messung 2026-10-01** (echter Vergleichs-Prompt, ZDR, Exa gegen eigene Suche):
Faktenfragen („neuestes Modell von X“, Preise) beantworteten Gemini 3.5
Flash-Lite, Gemini 3.8 Flash und Claude Haiku 4.5 mit beiden Wegen zu 100 %
richtig, GPT-5.6 Luna mit Exa zu 75 %, mit eigener Suche zu 90 %. Bei offenen
„was ist aktuell am besten“-Fragen nannte die eigene Suche deutlich öfter
aktuelle Modelle (Anteil aktueller Namen: Gemini 3.5 Flash-Lite 83 → 100 %,
Gemini 3.8 Flash 7 → 48 %, GPT-5.6 Luna 41 → 100 %, Haiku gemischt). Kosten pro
Aufruf: Google-Grounding ≈ 2,9 ct statt ≈ 0,8 ct mit Exa, OpenAI 1,2 statt 0,8 ct,
Anthropic gleich. Grenze: Familien ohne eigene Suche bleiben bei offenen Fragen
auf die Exa-Treffer angewiesen, die oft ältere Übersichtsartikel sind.

Nur tatsächliche Quellenannotationen oder gemeldete Suchzähler erzeugen eine
Suchaktivität; Startzeiten/Queries werden nicht erfunden. Vergleichsmodelle
sehen keine anderen Vergleichsantworten. Kein eigener Suchdienst, kein
zusätzliches Suchmodell; Provider-Routing/ZDR bleiben bestehen.

Worker-Delegation bleibt standardmäßig deaktiviert und verwendet weiter die
geprüften Modell-/Reasoning-Kombinationen und die bestehende Admin-Konfiguration;
siehe [agent-delegation.md](agent-delegation.md). Vergleichstools sind davon
unabhängig. Der gemeinsame Tool-Loop erhält die kompletten Provider-Fortsetzungs-
informationen intern; verschlüsselte Reasoning-Blöcke werden nie öffentlich oder
persistiert. Sichtbares Reasoning bleibt auf 32000 Zeichen begrenzt.

Gestreamte `reasoning_details` werden wie im OpenRouter-SDK zusammengesetzt:
Text- und Summary-Fragmente verlängern den vorherigen Block derselben Art (gleicher
`type`, keine abweichende `index`/`id`/`format`/`signature`). `reasoning.encrypted`
bleibt immer ein eigener, unveränderter Eintrag. `index` allein ist keine
Identität: Gemini 3.x sendet Gedankentext und Thought-Signatur beide mit `index: 0`.
Beim Zurückspielen entfällt unsignierter `reasoning.text` in den Formaten
`google-gemini-v1` und `anthropic-claude-v1`, weil beide Anbieter unsignierte
Gedanken ablehnen; Geminis Signatur im verschlüsselten Block trägt die Fortsetzung.
Fehlerhafte Einzelfragmente werden übersprungen statt den Lauf zu beenden.

Systemprompt, frisches Datum/Zeitzone, ausgewählte Modellidentität und
Unterhaltung werden vom Server zusammengestellt. Fehlgeschlagene frühere Turns
behalten Nutzerfrage und gespeicherte Antwort, mit einem ausdrücklichen Hinweis
auf ihren möglicherweise unvollständigen oder ungeprüften Stand. Toolargumente,
Antworten und Quellen sind untrusted data, keine Berechtigungen. Strikte Schemas,
servereigene Modellauflösung und Limits verhindern eine Änderung der Policy
über Toolergebnisse. Dateien, Share und Watch sind weiterhin nicht freigeschaltet.

Der feste Produktkontext erklärt allen beteiligten Modellen knapp ihre Rolle in
consens.io. Jede Nutzerfrage und jeder Bearbeitungsauftrag geht durch
`compare_models → eigene Synthese → judge_answer`, ergänzt um
`check_contradictions`, wenn aktiviert. Websuche darf vorher aktuelle Fakten oder
die Fragestellung klären; jedes Vergleichsmodell kennt das Datum und sucht bei
zeitabhängigen Fakten selbst einmal (siehe „Websuche“). Das gilt auch für einfache, subjektive und Folgefragen,
Fragen zu consens.io sowie Textumformung/Übersetzung. Nur reine Begrüßungen und
Bestätigungen ohne Frage/Auftrag sowie unvermeidbare Rückfragen dürfen direkt
beantwortet werden. Rückfragen sind auf fehlende Angaben beschränkt, ohne die keine
nützliche Antwort möglich ist; sonst mit begründeten Annahmen weiterarbeiten.
Diese Entscheidung bleibt promptgesteuert; ein zweiter Router oder eine
sprachabhängige Keyword-Klassifikation erzwingt den Vergleich nicht.
Das Chatmodell soll consens.io hilfreich, klar und korrekt in der Nutzersprache
vertreten, den Produktzweck erklären können und keine nicht erfolgten Prüfungen
oder garantierte Wahrheit behaupten. Alte allgemeine Hinweise auf direkte Antworten
in gespeicherten Admin-Prompts werden durch diese konkrete Produktregel präzisiert.
Liefert der Provider am Suchlimit eine Antwort ohne Vergleichs-Toolcall, folgt
einmalig eine Orchestrierungsrunde mit den gesammelten Quellen und ohne neue
Websuche. Sie führt die Recherche zurück in den Consensus-Ablauf; nur eine
unvermeidbare Rückfrage kann den Vergleich aufschieben.

## Persistenz, Stop und Recovery

`accepted` liefert dem Browser die Turn-ID schon während der Budget-Zulassung.
Stop ist bereits vor dem ersten bezahlten Claim wirksam. Verwaiste Starts ohne
Receipt werden nach Ablauf ihrer fünfminütigen Chat-Reservierung bei Status/Recovery
geschlossen; ein neuerer Turn desselben Chats bleibt gesperrt, solange er aktiv ist.
Bereits fertige Vergleichsantworten werden sofort einzeln gespeichert. Bricht die
anschließende Synthese ab, bleibt auch deren Teiltext als ungeprüfte Antwortversion
erhalten. Die Oberfläche zeigt wartende Token-Zulassung ausdrücklich an und hält
bei langen Runs die neuesten 64 Aktivitätsereignisse sichtbar.

Ein einzelner Provider-Aufruf ohne Text-, Reasoning-, Tool- oder Tokenfortschritt
endet nach standardmäßig 180 Sekunden (`AGENT_PROVIDER_STALL_SECONDS`, 30–600).
Reine Keepalives verlängern diese Frist nicht. Lange Aufrufe mit Fortschritt
bleiben erlaubt; Modelle mit lange verborgenem Reasoning können einen höheren
Wert benötigen. Fehlende finale Usage bleibt unbekannt, und kein solcher Aufruf
wird automatisch wiederholt. Der Browser erkennt einen völlig stummen SSE-Kanal
nach 45 Sekunden; kurze Steueranfragen laufen nach 15 Sekunden in einen
wiederholbaren Fehler statt endlos im Ladezustand zu bleiben.

AgentRunStore hält einen atomaren Beleg je completion:N oder agent:<uuid>:N unter
users/{uid}/llm_calls. Der erste Beleg bindet Producer-Token, Lease, Policy,
Schrittzustände und Eventsequenz. Eine 120-Sekunden-Lease wird während aktiver
Läufe etwa alle 30 Sekunden transaktional für Producer, Chat und Account erneuert.
Der Watchdog liest alle drei Sekunden statt zweimal pro Sekunde; kurze temporäre
Datenbankfehler werden bis zu 60 Sekunden toleriert. Abgelaufene, gestoppte oder
ersetzte Producer werden nie wiederbelebt. Verbrauch bleibt bei einer Chat-Löschung
bestehen; Account-Tombstones verhindern verspätete Writes nach Kontolöschung.
Ein kontogebundener Lock-Pool serialisiert kurze Agent-Transaktionen im selben
Prozess. Temporäre Abrechnungsfehler wiederholen nur die idempotente Speicherung
der ursprünglichen Usage, niemals den Modellaufruf. Firestore sichert weiterhin
konkurrierende Prozesse ab. Coverage wartet bei unbegrenzter Agent-Laufzeit
ohne numerisch unendlichen Thread-Timeout auf das Ergebnis; Provider-Abbruch
und Transportgrenzen bleiben wirksam.

Abbruch schließt Provider und wartet auf die aktiven Tool-/Judge-Threads. Ein
Prozessabsturz erlaubt kein erneutes Ausführen bereits beanspruchter Schritte;
abgelaufene Leases werden in terminale unbekannte Belege überführt. Gespeicherte
Vergleichsantworten mit abgebrochener Prüfung bleiben im Agent-Verlauf sichtbar.
Direktantworten behalten auch bereits gestreamten Teiltext. `agent_failure` speichert
einen sicheren Fehlercode und verständlichen Grund, der nach Reload sichtbar bleibt;
rohe Provider-Fehlertexte werden nicht übernommen.
Recover saved answer lädt ausschließlich den existierenden Snapshot. Auch eine
fehlgeschlagene Antwort oder ein Turn ohne Hauptantwort kann so mit seinem
tatsächlichen Prüfstatus gelesen werden, auch später im archivierten Verlauf.
Ein neuer Versuch ist eine neue Nachricht mit neuem Budget, kein versteckter Retry.

## Validierung

- Backend: tests/test_agent_continuation.py prüft 102 Aufrufe über simulierte 17 Minuten,
  erneuerbare Leases, weitere Reviews, Kontingent-Stopp und erhaltene Fehler/Teiltexte.
  tests/test_agent_comparison.py sowie bestehende Agent-, Delegation-,
  Budget-, Chat-, Bookmark- und Consensus-Judge-Tests.
- Browser-State: tests/js/agent-review.test.mjs und bestehende Agent-Tests.
- Oberfläche: tests/e2e/test_agent_comparison_frontend.py mit gemockten Providern,
  Desktop, 390/320 Pixel, Hell/Dunkel, Tastatur und gespeicherter Ansicht.
- Transaktionen im Firestore-Emulator: tests/e2e/test_agent_transactions.py.

Befehle, isolierte Testumgebung und Build-Vertrag stehen in [testing.md](testing.md).
Die deterministischen Tests ersetzen keine kostenpflichtigen Providerprobes für
jede Modell-/Reasoning-Kombination; deren frühere Ergebnisse bleiben unter artifacts/.

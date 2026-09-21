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

Abgeschlossene und gestoppte Antworten lassen sich über „Copy answer“ kopieren,
auch im Verlauf und nach Wiederherstellung. Kopiert wird das ursprüngliche
Antwort-Markdown ohne Statusanzeigen oder Prüfmarkierungen; Erfolg oder Fehler
erscheint direkt an der Aktion. Folgefragen werden direkt im Eingabefeld gestellt.
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
Standard (weiterhin deepseek/deepseek-v4.1-flash).

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
liegen ihre Optionen im bestehenden (+)-Menü im Input; das leere Eingabefeld
ist wie beim Consensus einzeilig und wächst beim Schreiben. Auf Mobil bleibt
das (+) auch eingeklappt direkt erreichbar. Ein neuer Chat zeigt die Startleiste wieder.
„Agent Mode On“ ist vorerst eine Statusanzeige ohne Umschaltfunktion; sie ändert
den bisherigen Consensus-Modus nicht. „Check contradictions“ schaltet das
Quellenprüfungs-Tool für die nächste Nachricht frei. Der gemeinsame On/Off-Wert
wird beim Senden eingefroren und bei Recovery wiederverwendet. „Deep Think“
öffnet direkt die vorhandene Reasoning-Auswahl des Chatmodells und zeigt deren
aktuelle Stufe. Modelle ohne wählbares Reasoning und laufende Nachrichten sperren
dieses Menü. „Attach“ bleibt wegen der Textbeschränkung deaktiviert.

Das Modell kann eine ganze Frage oder mehrere begründete Teilfragen
vergleichen. Jede Vergleichsgruppe erhält denselben neutralen Auftrag samt
notwendigem Kontext. Die Vergleichsmodelle kennen den Chatverlauf nicht. Das
Chatmodell muss deshalb bei Bedarf Bezüge konkretisieren und relevante frühere
Anforderungen mitgeben. Keine Vergleichsantwort beeinflusst die andere. Das
Chatmodell erhält Antworten, Quellen, Status und Modellmetadaten und schreibt
die Synthese selbst. Auch bei einem Prüfwunsch wird zuerst eine unabhängige
Vergleichsgrundlage eingeholt.

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
Widersprüche und bereits vorhandene Originalquellen. Abruf, validierte Zitate,
Ausschlussgründe, konfigurierte Judge-Modelle und Verfügbarkeits-Fallbacks sind
dieselben wie in Consensus. Jeder bezahlte Versuch zählt zum Agent-Tokenbudget.
Ohne passende Widersprüche wird die Quellenprüfung ohne Abrufe oder bezahlten
Quellen-Judge übersprungen. Ausgeschaltet ist das Tool nicht verfügbar;
Differences und Coverage bleiben Bestandteil jedes Modellvergleichs.
`judge_answer(finalize=true)` beendet bei eingeschalteter Quellenprüfung erst
nach deren Abschluss; das Modell erhält `check_contradictions` als nächsten
Tool-Schritt. Fehlerhafte oder fehlende Belege bleiben ausdrücklich ungeprüft.
Ergebnisse und Originalbelege stehen direkt an den Widerspruchskarten, auch
im gespeicherten Verlauf. Eine neue Antwort oder Vergleichsgrundlage braucht
eine neue Prüfung; wiederholte Tool-Aufrufe derselben Prüfung starten keinen
weiteren Quellen-Judge.

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
Unter der Antwort stehen ein kompakter Prüfstatus und Links zu Widersprüchen,
Einzelantworten und Quellen. Rote Textmarkierungen öffnen unmittelbar die
passende Widerspruchskarte im gemeinsamen Consensus-Antwortleser. Modelllinks
zeigen dort die formatierte Originalantwort. Bei mehreren Teilvergleichen wählt
ein beschriftetes Auswahlfeld die konkrete Markierungsgrundlage. Kontext und
frühere Antwortversionen stehen in den Details des Lesers. Live-Ansicht und
gespeicherter Verlauf verwenden denselben Review-Snapshot.
Fehlt nur eine Modellantwort, während Differences und Coverage vollständig
vorliegen, lautet der Status `Comparison checked · 1 model unavailable`.
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

Das Tagesbudget ist in Admin → Limits separat speicherbar und liegt in
app_config/agent_budget. Ohne gespeicherte Einstellung gilt AGENT_DAILY_TOKEN_LIMIT,
standardmäßig 250000 Tokens pro UID und UTC-Tag (Reset um 00:00 UTC). Der Button
„Reset all Agent budgets“ setzt das Agent-Kontingent aller Konten über eine neue
Budgetgeneration zurück, ohne Nutzer-Scan. Begonnene Aufrufe rechnen weiter gegen
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
Es gibt kein Laufzeit-, Runden-, Tool-, Such-, Nachrichten- oder Dollarbudget pro
Lauf. Alte Admin-Werte dafür werden von `AgentPolicy.for_chat` nicht angewendet;
Legacy-/Evaluierungsaufrufe und die bestehende Consensus-Pipeline bleiben begrenzt.
Technische Grenzen schützen Providerprotokoll, Speicher und Parallelität:

| Grenze | Standard |
|---|---|
| Parallele Unteraufrufe | 2 |
| Antwortmodelle pro Vergleich | vorhandene Auswahl, mindestens 2 |
| Vergleichsantwort | standardmäßig 2048 Output-Tokens; 6000 Zeichen als Promptvorgabe, vollständige längere Antworten bleiben erhalten |
| Synthese | AGENT_MAX_OUTPUT_TOKENS, standardmäßig 4096 |
| Kontext | Modellfensterprüfung; initialer Chatverlauf maximal 120000 Zeichen |
| Review-Snapshot | maximal 600 kB |
| Gleichzeitige Runs je UID | 2 |
| Produzenten pro Prozess | AGENT_MAX_CONCURRENT_RUNS, standardmäßig 16 |

Reservierungen sind Zulassungskontrollen, keine Garantie für die tatsächliche
Provider-Rechnung. Meldet der Provider höheren Verbrauch, wird er vollständig
verbucht und weiterer Verbrauch blockiert. Unbekannte Nutzung ist kein Nullwert.
Drei aufeinanderfolgende Tool-Batches ohne gültig ausgeführten Aufruf stoppen
als Protokollstillstand, statt das Tageskontingent mit derselben ungültigen
Anfrage aufzubrauchen. Gültige Arbeit erhält dadurch kein pauschales Rundenlimit.

## Recherche, Delegation und Providerprotokoll

Recherche nutzt den vorhandenen OpenRouter-Websuch-Builder. Agent begrenzt ihn
auf Exa mit drei Treffern à maximal 1000 Zeichen pro Suche; maximal eine Suche
pro Modellrequest, erneut verfügbar in weiteren Runden. Damit kann das Tageskontingent
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
die Fragestellung klären. Das gilt auch für einfache, subjektive und Folgefragen,
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

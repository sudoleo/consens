# Manuelle fachliche Abnahme der Widerspruchsprüfung

Stand: 11.09.2026. Prüfung durch Codex anhand live geöffneter Originaldokumentation
und lokal ausgeführter Sprachbeispiele. Die gegenübergestellten Modellpositionen
sind **Rekonstruktionen typischer API-Verwechslungen**, keine beobachteten
Produktionsantworten und keine Aussagen über die Fehlerrate eines Providers.
Es wurden keine Nutzerdaten oder gespeicherten Antworten verwendet.

## Durchführung und technische Beobachtung

Für jeden der drei Fälle wurde ein eigener v4-Auftrag über `verify_sources`
ausgeführt: ein `major`-Widerspruch, eine konkrete `factual_check.question`,
validierter Consensus-Anker, zwei originale rekonstruierte Modellpassagen mit
S-Referenzen und ein eindeutiger Run-Schlüssel
`manual-2026-09-11:<Fallname>`. Beide Positionen erhielten dieselben vorhandenen
Dokumentationsquellen; es gab keine automatische Websuche. Die Namen OpenAI und
Gemini dienten ausschließlich als technische Modellschlüssel der Testdaten.

Verwendet wurden `Limits.configured()`, der normale sichere Dokumentabruf und
`resolve_developer_api_keys()`; der konfigurierte Judge war
`google/gemini-3.5-flash-lite`. Der Schlüssel war verfügbar und wurde weder
ausgegeben noch gespeichert. Im ersten Versuch innerhalb der Netzwerksandbox
schlug der Abruf für sämtliche Quellen mit `network_error` fehl. Die Prüfung
wies alle drei Fälle korrekt als `partial/unavailable` aus und startete keinen
Judge. Die separat verwendete Web-Leseumgebung konnte die Originalseiten öffnen.

Nach erteilter Netzwerkfreigabe wurde derselbe begrenzte Lauf außerhalb der
Sandbox wiederholt. Alle vier eindeutigen URLs wurden erfolgreich über den
normalen sicheren Abruf geladen. Es gab genau drei echte Judge-Aufrufe,
einen je Fall, ohne Wiederholungsaufruf:

| Fall | Eindeutige URLs im Prüfplan | Laufzeit | Tatsächliches Live-Ergebnis |
|---|---:|---:|---|
| `python-sort` | 1 | 1.812 ms | `partial`, `unavailable`, `evidence_mismatch` |
| `python-round` | 1 | 4.157 ms | `complete`, `supports_position`, P1 |
| `javascript-sort` | 2 | 3.265 ms | `complete`, `supports_position`, P1 |

Die zwei positiven Positionsurteile bestanden die Originalzitatvalidierung und
stimmen mit der manuellen fachlichen Bewertung überein. Beim Sortierfall konnte
die Judge-Ausgabe die Belegvalidierung nicht bestehen: kein Urteil und keine
unverifizierten Zitate wurden übernommen. Die unverarbeitete Judge-Ausgabe wurde
nicht gespeichert; der genaue fehlerhafte Zitattext ist deshalb nicht Teil
dieses Berichts. Der Fall wurde nicht durch wiederholte Modellaufrufe auf ein
positives Ergebnis optimiert. Consensus und Agreement blieben unverändert.

## 1. Python: Rückgabewert von `list.sort()`

- P1: `list.sort()` liefert `None`; `sorted()` liefert eine neue Liste.
- P2: `list.sort()` liefert eine neue sortierte Liste.
- Prüffrage: Welchen Rückgabewert haben diese beiden APIs für gewöhnliche
  Python-3-Listen?

Originalpassage: “It modifies the list in-place (and returns `None` to avoid
confusion).” Die Dokumentation erklärt daneben die neue Ergebnisliste von
`sorted()`. [Python Sorting Techniques](https://docs.python.org/3/howto/sorting.html#sorting-basics)

Manuelle Erwartung: `supports_position`, `supported_position_id: P1`. Die Quelle
belegt das unterschiedliche Verhalten ausdrücklich. Dass beide Positionen
dieselbe URL zitieren, macht die falsche Lesart nicht ebenso gut belegt.
Die URL soll einmal abgerufen werden; relevante Abschnitte über beide APIs
müssen erhalten bleiben. Es liegt kein Widerspruch zwischen Quellen vor.

Live beobachtet: Dokument erfolgreich geladen, ein Judge-Aufruf; das Ergebnis
wurde wegen `evidence_mismatch` verworfen. Das ist eine sichere Enthaltung,
erreicht in diesem Versuch aber nicht die fachlich mögliche Klärung.

Lokal beobachtet unter Python 3.9.7: Für `values = [3, 1, 2]` war
`values.sort()` gleich `None`, danach `values == [1, 2, 3]`;
`sorted([3, 1, 2])` ergab `[1, 2, 3]`. Das Beispiel prüft Built-ins,
keine selbst überschriebenen Methoden einer Unterklasse.

## 2. Python: Rundung exakt halber Werte

- P1: Python `round()` rundet exakte Halbwerte zur geraden Alternative.
- P2: Python `round()` rundet exakte Halbwerte von null weg.
- Prüffrage: Welche Regel gilt für Python-3-Built-ins bei einem exakten Gleichstand?

Originalpassage: “if two multiples are equally close, rounding is done toward
the even choice”. [Python: round](https://docs.python.org/3/library/functions.html#round)

Manuelle Erwartung: `supports_position`, P1. Der Gleichstand und die
Built-in-Typen sind Teil des Geltungsbereichs. Die gleiche Dokumentation erläutert
auch die binäre Darstellung von Fließkommazahlen; daraus folgt keine abweichende
Rundungsregel für exakte Halbwerte. Andere Objekte können eigenes
`__round__`-Verhalten implementieren. Solche Bedingungen müssten bei einer
entsprechend anders formulierten Streitfrage berücksichtigt werden.

Lokal unter Python 3.9.7: `round(0.5)`, `round(-0.5)` und `round(1.5)` lieferten
`0`, `0`, `2`. `round(2.675, 2)` ergab `2.67`; dieser zusätzliche Kontrollfall
darf nicht als Beleg für P2 missverstanden werden.

Live beobachtet: `supports_position` für P1 mit validierter Originalpassage zur
geraden Alternative. Das Urteil war fachlich zutreffend; der Geltungsbereich
benannte Python-Built-ins, das unbekannte Dokumentdatum blieb leer.

## 3. JavaScript: Mutation durch `sort()`

- P1: `sort()` verändert das ursprüngliche Array; `toSorted()` erzeugt ein neues.
- P2: `sort()` erzeugt ein neues Array und lässt das ursprüngliche unverändert.
- Prüffrage: Wie unterscheiden sich Mutation und Rückgabereferenz dieser APIs?

Originalpassage zu `sort()`: “The reference to the original array, now sorted.”
[MDN: sort, Return value](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Array/sort#return_value)

Originalpassage zu `toSorted()`: “A new array with the elements sorted in
ascending order.”
[MDN: toSorted, Return value](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Array/toSorted#return_value)

Manuelle Erwartung: `supports_position`, P1, mit Einschränkung auf eine Laufzeit,
die `toSorted()` implementiert. Unterschiedliche APIs erklären, wie die
Verwechslung entstehen kann; P2 behauptet trotzdem das falsche Verhalten von
`sort()`. Ein Urteil `sources_conflict` wäre fachlich falsch.

Lokal unter Node.js v18.12.0 veränderte `sort((a, b) => a - b)` das Array
`[3, 1, 2]` zu `[1, 2, 3]` und lieferte dieselbe Referenz zurück. `toSorted`
war in dieser lokalen Laufzeit nicht verfügbar; der Ausführungsversuch ergab
`TypeError`. Deshalb ist seine Semantik hier dokumentarisch, nicht durch lokale
Ausführung bestätigt. Die aktuelle MDN-Dokumentation und die alte lokale
Laufzeit widersprechen sich dadurch nicht.

Live beobachtet: `supports_position` für P1 mit je einem validierten Zitat aus
beiden MDN-Seiten. Das Urteil war fachlich zutreffend. Die Modellbegründung
benannte den Quellenbeleg gegen P2; sie leitete dies nicht aus fehlendem Abruf
oder Modellmehrheit ab. Die Verfügbarkeit auf alten Laufzeiten wurde im
Live-Urteil nicht zusätzlich erläutert und bleibt eine wichtige manuelle
Geltungsbereichsnotiz.

## Abnahmegrenze

### Nachprüfung: Differences, Claims und lokale Versionsmischung

Am 11.09.2026 meldete der Nutzer fehlende Differences und weiterhin farbige
S-Quellen auf `127.0.0.1:8000/app`. Die laufende Seite lud bereits den neuen
Frontend-Build, während der Python-Worker noch vor der Umstellung gestartet
worden war und den alten Build `82558be` meldete. Der sichtbare gespeicherte
Döner-Vergleich enthielt Claims, eine `different_emphasis`-Difference sowie eine
historische Satz–Quellen-Prüfung. Das war kein neuer v4-Prüflauf.

Drei echte Analyseaufrufe mit bewusst gegensätzlichen Modellantworten prüften
die Erkennung separat: Der Vergleich von `list.sort()` und `sorted()` ergab
einen großen Widerspruch und einen geteilten Claim; explizit unterschiedliche
PostgreSQL-/MongoDB-Empfehlungen blieben als großer Widerspruch mit
`factual_check.checkable: false` erhalten. Prüfbarkeit ist damit eine Zusatzangabe
für die Quellenprüfung und kein Filter für Differences oder Claims. Diese
gezielten Fälle belegen keine allgemeine Erkennungsquote.

Zusätzlich wurden zwei unabhängige Darstellungsrisiken korrigiert: Fehler in
den Quellen-UI-Hooks dürfen die ursprünglichen Karten und Markierungen nicht
abbrechen; neue Consensus-Texte dürfen numerische Schreibweisen wie `[1]`
nicht über den Modellquellenkatalog in farbige S-Links umwandeln. Die
Stream-/Polling-Abnahme prüft beide Schalterstellungen sowie unveränderte
Claim- und Difference-DOM-Knoten nach dem Eintreffen des Quellenurteils.
Gespeicherte Legacy-Antworten und ihre Quellenlinks bleiben erhalten.

Die drei Beispiele zeigen zwei fachlich passende Live-Urteile mit validierten
Quellenzitaten und eine Enthaltung durch die Belegvalidierung. Der erste
Sandbox-Versuch prüfte außerdem die ehrliche Behandlung realer Abruffehler.
Diese kleine, gezielt ausgewählte Stichprobe ergibt keine allgemeine
Genauigkeitsquote. Sie misst nicht die Erkennungsqualität des Differences-Judges:
Differences wurde hier als bereits erkannter Prüfauftrag rekonstruiert.
Consensus, Agreement und Modellpositionen wurden durch die Prüfungen nicht
geändert. Die Funktion untersucht einzelne erkannte Streitpunkte anhand
vorhandener Quellen; sie verifiziert nicht den gesamten Consensus.

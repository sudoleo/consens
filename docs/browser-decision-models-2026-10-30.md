# Entscheidungsmodelle für Browser-Klicks (Test 2026-10-30)

Frage von Max: Könnte der Agent ein Entscheidungsmodell wie Jev (TypeSafe) als
Werkzeug nutzen, das sich per Klick zu einem Ziel durchklickt („geh zu X“),
während DeepSeek jederzeit selbst übernehmen kann? Getestet mit echten Aufrufen
nach Max' Freigabe, Kosten zusammen unter 0,10 $. Nichts davon ist im Code; die
Skripte lagen nur im Scratchpad.

## Was Jev ist

- Kein LLM: beantwortet typisierte Fragen über einen `state` (Text, JSON,
  Bilder) mit Wahrscheinlichkeiten. Typen: Choice (bis 255 Optionen), Noul
  (ja/nein), Score, Box (Rechteck im Bild, nur Jev 1.14).
- Über OpenRouter ohne Warteliste, mit unserem Schlüssel, aber nicht über Chat
  Completions: `POST https://openrouter.ai/api/alpha/decisions` mit `model`,
  `state`, `questions` (Objekt mit eigenen IDs). Antwort `answers` plus
  `usage.cost`.
- 0,042 $ pro Mio. Eingabe-Tokens, Ausgabe frei. TypeSafe nennt Bilder und Box
  selbst noch nicht produktionsreif; jede Anfrage mit Bild läuft im langsameren
  Long-Context-Modus. Es gibt einen AVV, ZDR nur für Enterprise.
- Auf OpenRouter gibt es inzwischen 22 Entscheidungsmodelle über dieselbe API;
  zum Vergleich liefen `openai/gpt-6-luna-decisions` (0,10 $/Mio.) und
  `perplexity/pplx-decider-v1.2` (0,02 $/Mio.) mit.

## 1. Wahl per Ref: 11 echte Klickschritte aus Max' Läufen

Seite so, wie DeepSeek sie per `read` sah, die Refs als Optionen, das Ziel des
Schritts in einem Satz (so, wie DeepSeek es einem Werkzeug geben würde).

| Modell | richtig | Zeit je Wahl |
| - | - | - |
| GPT-6 Luna Decisions | 11/11 | ~0,4 s |
| Perplexity Decider 1.2 | 10/11 | ~0,27 s |
| Jev 1.14 | 8/11 (auch mit umgekehrter Optionsreihenfolge) | ~0,2 s (warm) |

Jevs Fehler: zweimal die mittlere Zelle eines Tic-Tac-Toe-Bretts aus namenlosen
Knöpfen (unsicher, 0,15–0,28), und einmal auf chess.com für „Premium-Angebot
schließen“ der Knopf „Für 0,00 € ausprobieren“ mit 91 % Sicherheit, also ein
sicherer, folgenreicher Fehlgriff. „Ziel erreicht?“ als Noul auf der Seite nach
dem Klick taugt bei keinem Modell als verlässliches Stoppsignal (Jev meist
unter 0,2, auch wenn das Ziel erreicht war).

## 2. Klickschleife auf 8 echten Seiten

Prototyp: unser `browser.py` liest die Seite (`page_lines`, Frames inklusive),
das Modell wählt einen Ref oder DONE/HELP, höchstens 8 Klicks, die bisherigen
Klicks samt Fehlschlägen im `state`. Ziele wie „Sportseite öffnen“ (bild.de,
Consent im iframe), „gegen den Computer spielen“ (chess.com), „Wetterwarnungen“
(dwd.de), „Releases“ (GitHub), Wikipedia-Artikel, Python-Tutorial, „Netzwelt“
(spiegel.de). Erfolg prüfte Code an URL und Titel. Vergleich: DeepSeek Flash
ohne Reasoning in derselben Schleife.

| Wähler | erreicht | Wahl Median / p90 | Anteil an der Laufzeit |
| - | - | - | - |
| DeepSeek Flash (ohne Reasoning) | 7/8 | 0,55 s / 2,0 s | 19 % |
| Jev 1.14 | 6/8 | 0,28 s / 0,8 s | 8 % |
| GPT-6 Luna Decisions | 5/6 | 0,43 s / 1,35 s | 18 % |

Jev blieb auf bild.de hängen: Der Cookie-Dialog lag über der Seite, Jev klickte
ohne Verlauf neunmal dasselbe blockierte „SPORT“; mit Verlauf vier verschiedene
Sport-Links, dann den Dialog weg und meldete DONE auf der Startseite. Luna und
DeepSeek klickten zuerst „Alle akzeptieren“. Auf spiegel.de gaben alle HELP
(Rubrik hinter dem Menü), was in der Schleife das richtige Verhalten ist.

## 3. Box auf Screenshots

Klick auf die Mitte der Box, Treffer gegen die echte Elementbox: 10 von 13
sichtbaren Zielen, ~0,22 s. Sicher bei eindeutigen Zielen (König, „Aufgeben“,
alle vier Canvas-Felder eines gezeichneten Tic-Tac-Toe, „Docs“ auf python.org,
Suchfeld), falsch bei allem, was Koordinaten oder gleiche Figuren verlangt
(„Springer auf g1“ wurde b1, leere Felder f3/c6), dann aber mit niedriger
Sicherheit. Ein Ziel außerhalb des Bildes erkannte die begleitende Noul richtig
(0,01).

## 4. Nachtrag: 17 Entscheidungsmodelle auf 19 Fällen

Die Kategorie ist erst sechs Wochen alt; mehrere Modelle sind jünger als
Jev 1.14. Dieselben 11 echten Schritte plus 8 live gespeicherte Startseiten
(bild.de und spiegel.de mit Consent-Dialog darüber, chess.com, GitHub, dwd.de,
python.org, zwei Wikipedia-Artikel), nur die Wahl:

| Modell | richtig | Median | Preis/Mio. Eingabe |
| - | - | - | - |
| openai/gpt-6-luna-decisions | 19/19 | 0,41 s | 0,10 $ |
| baseten/mammoth-1 (Qwen3.5-27B) | 18/19 | 0,41 s | 0,10 $ |
| cloudflare/clef (27B) | 18/19 | 0,86 s | 0,24 $ |
| liquid/d1-ultra | 17/19 | 0,30 s | 0,042 $ |
| inception/mercury-decide, nace-ai/drex-max | 17/19 | ~0,5 s | 0,02–0,06 $ |
| perplexity/pplx-decider-v1.2, respan/span-02 | 16/19 | ~0,3–0,4 s | 0,01–0,02 $ |
| typesafe/jev-1.14, liquid/d1.1, baseten/elephant-1 | 15/19 | 0,3 s (Jev unter Last 1,6 s) | 0,02–0,042 $ |
| kleinere (Microsoft, Kev 4B, Clef Flash, Joey-1) | 11–14/19 | | |

Der Prüfstein war bild.de: Nur Luna und Mammoth wählten zuerst den
Consent-Knopf, die anderen „SPORT“ hinter dem Dialog. In der Klickschleife mit
Verlauf erreichten Luna, Mammoth und d1-ultra bild.de, chess.com und dwd.de
(spiegel.de: alle HELP); auf chess.com klickten Luna und Mammoth über das Ziel
hinaus bis „Play“, weil „Ziel erreicht?“ bei allen schwach bleibt. Alle
Entscheidungsaufrufe beider Runden zusammen: 620 Aufrufe, 0,15 $.

## Einordnung

- Die Entscheidung ist in der Schleife nicht der Engpass: 80–90 % der Zeit sind
  Laden und Klicken. Jev spart gegenüber einem DeepSeek-Aufruf ohne Reasoning
  etwa 0,3 s je Klick, gegenüber einem echten Agentenschritt (Median 2,7 s mit
  Reasoning und ganzem Gespräch) gut 2 s.
- In Max' 19 Browser-Läufen (28.–30.10.) navigiert der Agent fast nur per
  `open` mit Adresse; Strecken von mehreren Navigationsklicks hintereinander
  sind selten, die meisten Klicks gehören zu Spielen. Ein „geh zu X“ würde
  heute in wenigen Läufen ein paar Sekunden sparen.
- Jev ist von den getesteten Modellen das schnellste, aber nicht das genaueste,
  und es hat einen sicheren Fehlgriff gezeigt. Für eine solche Schleife müsste
  jeder Klick ohnehin denselben Weg wie heute nehmen (Treffer-Rückmeldung,
  Gate) und vor allem, was kauft, sendet oder etwas annimmt, an den Agenten
  zurückgeben.

- Bessere Wähler als Jev gibt es (Luna Decisions, Mammoth-1); sie lösen den
  Qualitätseinwand, nicht den kleinen Hebel.

**Entscheidung:** nicht bauen. Der größere Hebel bleibt die Zahl der
Agentenschritte (siehe `docs/agent-workspace-runtime-audit-2026-10-30.md`).
Wiedervorlage, falls die Prod-Logs viele Navigationsstrecken oder verfehlte
Klicks an x,y auf Canvas-Seiten zeigen: dann zuerst Box als optionales Ziel in
Worten für `click`/`drag` testen, nicht die ganze Schleife.

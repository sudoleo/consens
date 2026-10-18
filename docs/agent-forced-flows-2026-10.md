# Erzwungene Agent-Abläufe: Versprechen oder Ablauf? (2026-10-17)

Frage von Max: Claude Code lässt das Modell fast alles selbst entscheiden. Wir
erzwingen noch Abläufe, zum Beispiel den Judge nach der Antwort. Warum nicht
alles als Werkzeug dem Agenten geben?

Diese Analyse wurde ohne Codeänderung und ohne Modell-Aufrufe erstellt. Grundlage ist der Code auf `main` (b06037ef).

## Kurzfassung

- **Die Grenze ist nicht „Werkzeug oder Code“, sondern „Arbeit oder Versprechen“.**
  Arbeit heißt: wie der Agent zur Antwort kommt. Die gehört dem Agenten. Versprechen
  heißt: worauf sich der Nutzer verlassen kann. Das bleibt im Code. Claude Code macht
  es genauso: Die Arbeit ist frei, Rechte, Hooks und Sandbox sind es nicht.
- **Fast alles, was heute fest im Code steht, ist Versprechen oder Grenze.** Nur
  drei kleine Leitplanken und der geführte Modus sind echte „Abläufe aus
  Misstrauen“.
- **Der wichtigste Befund:** Die Prüfung kann der Agent schon heute umgehen, indem er
  nicht vergleicht. Seit dem 11.10. entscheidet er das selbst. Die Freiheit, nach
  der du fragst, gibt es also bereits, nur eine Ebene über dem Judge. Die offene
  Frage ist, ob er sie gut nutzt.
- **Der größte Hebel ist „geführt“ statt „frei“** (Agent freedom). Im Standard
  fragt jeder Vergleich alle gewählten Modelle. Im freien Modus wählt der Agent
  die Modelle selbst. Das gibt es seit dem 4.10., gemessen ist es nie.

**Empfehlung:** Judge, Mindestfamilien, Unabhängigkeit und Grenzen bleiben. Die
drei Leitplanken bekommen ein Ablaufdatum: erst zählen, wie oft sie greifen,
dann entfernen. „Frei“ wird Standard, wenn die Messung es trägt.

> Korrektur zu meiner ersten Antwort: `judge_answer` war vor dem 11.10. nicht
> „der Judge als Werkzeug“, sondern das Fertig-Signal des Agenten. Die Prüfung
> lief schon damals über die App (`_finish_review`). Herausgenommen wurde das
> Werkzeug, um „fertig“ und „prüfen“ zu trennen (Werkzeuge mit einem Zweck), nicht
> weil der Agent die Prüfung ausgelassen hätte. Der Judge war nie optional.

## Alle Stellen, an denen der Code entscheidet

### A. Versprechen an den Nutzer: bleiben im Code

Würde der Agent sie auslassen dürfen, wären es keine Versprechen mehr. Oder der
Geprüfte würde seine eigene Prüfung steuern.

| Was | Wo | Warum fest |
|---|---|---|
| Prüfung (Differences + Coverage) nach jeder Antwort, die auf Vergleichen beruht | [`_finish_review`](../app/services/agent_delegation.py#L1364), Werkzeug nur im `app_registry` ([agent_comparison.py:583](../app/services/agent_comparison.py#L583)) | Der Agent prüft sich nicht selbst und formuliert auch nicht die Eingabe seiner Prüfung. Die sichtbare Uneinigkeit ist das Produkt. |
| Mindestens zwei Familien je Vergleich (frei) | Schema + [`_choose`](../app/services/agent_comparison.py#L589) | Ohne Untergrenze wird der freie Modus zum Ein-Modell-Router (Benchmark 10-04). Mit nur einer Antwort gibt es nichts zu prüfen. |
| Antwort steht fest, bevor geprüft wird | [`compare` lehnt nach der Antwort ab](../app/services/agent_comparison.py#L875), `capture`, Hash in `review_is_bound` | Die Prüfung muss genau zu dem Text gehören, den der Nutzer sieht. |
| Unabhängigkeit der Vergleichsmodelle | [nach `read_source` kein Vergleich](../app/services/agent_comparison.py#L877), [eingefügter Text nicht in die Aufgabe](../app/services/agent_comparison.py#L627), [Antworten anonym und gemischt](../app/services/agent_comparison.py#L1063) | Sieht ein Modell schon die Antwort, stimmt es ihr eher zu. Dann sagt die Prüfung nichts mehr. |
| Ehrlich bei dünner Grundlage | [unter zwei Antworten keine Prüfung versprechen](../app/services/agent_comparison.py#L1092), `review_issues` | „Geprüft“ darf nur dastehen, wenn wirklich geprüft wurde. |

### B. Grenzen für Kosten, Zeit und Sicherheit: bleiben im Code

Die gibt es in Claude Code auch: maximale Schritte, Rechteprüfung, Sandbox. Sie
sollen das normale Verhalten nicht formen, sondern nur den Ausreißer stoppen.

| Was | Wo | Herkunft |
|---|---|---|
| Pro Nachricht: 4 Vergleiche, 24 Schritte, 15 min + 5 min, gleicher Aufruf höchstens zweimal, 3 ungültige Runden → Abschluss | [agent_policy.py:41](../app/services/agent_policy.py#L41), [`_turn_limit`/`_identical_call`](../app/services/agent_delegation.py#L410), [L1749](../app/services/agent_delegation.py#L1749) | 6d23b576: Eine Schleife gültiger Vergleiche konnte das ganze Tageskonto verbrennen. |
| Zeitreserve für die Antwort, Quorum wartet nicht in sie hinein | [`ANSWER_RESERVE_SECONDS`](../app/services/agent_delegation.py#L64), `_await_quorum` | Bezahlte Vergleiche enden immer mit einer Antwort. |
| Suchrunden des Agenten: 3 vor dem ersten Vergleich, danach 1 | [`ORCHESTRATOR_SEARCH_ROUNDS`](../app/services/agent_delegation.py#L45) | 646dac21: Kostengrenze. |
| `read_source` nur für zitierte Quellen oder Links des Nutzers, höchstens 5 | [agent_read_source.py:55](../app/services/agent_read_source.py#L55), [L439](../app/services/agent_read_source.py#L439) | Abfluss von Daten über Links, die eine Seite oder Antwort unterschiebt. |
| Memory: Opt-in, wörtlicher Beleg, gesperrt nach fremdem Inhalt | [`MEMORY_LOCKED`](../app/services/agent_memory.py#L787), [Belegprüfung](../app/services/agent_memory.py#L935) | 8ccc72f1: Eine Seite könnte sonst das Gedächtnis vergiften. |
| Watch und Google-Aktionen nur vorbereiten, der Nutzer startet per Karte | [agent_watch.py](../app/services/agent_watch.py#L44), [agent_delegation.py:329](../app/services/agent_delegation.py#L329) | Fremder Inhalt darf nichts Dauerhaftes auslösen. |

### C. Abläufe aus Misstrauen: Kandidaten zum Freigeben

Jede dieser Leitplanken geht auf einen echten, live beobachteten Modellfehler
zurück. Solche Fehler werden mit neuen Modellen seltener. Deshalb brauchen sie
ein Ablaufdatum statt Dauerbestand.

| Was | Wo | Herkunft | Empfehlung |
|---|---|---|---|
| **Geführter Modus als Standard**: Jeder Vergleich fragt alle gewählten Modelle. | [`autonomy = "guided"`](../app/services/agent_comparison.py#L77) | bc514356 (10-04): Frei kam nur als Opt-in, „erst messen“. | **Größter Hebel.** Frei gegen geführt messen (siehe unten). Trägt die Messung, wird frei der Standard. |
| Antwort nach eigener Websuche ohne Vergleich wird **einmal** zurückgehalten (ab 800 Zeichen) | [`_tool_reminder`](../app/services/agent_delegation.py#L1505), ebenso [`_consensus_search_handoff`](../app/services/agent_delegation.py#L1270) | Regel von Max am 10-11: „eigene Recherche → immer Vergleich“, im Code seit 6e7da484. | Sie liegt zwischen A und C, weil sie den Vergleich gerade bei Fakten schützt. Sie ist aber nur weich (danach steht die Antwort). **Zählen:** Greift sie oft, macht sie echte Arbeit und gehört eher nach A. Greift sie fast nie, kann sie weg. |
| `check_text` auf die eigene Frage des Nutzers wird abgelehnt | [`own_request`](../app/services/agent_comparison.py#L491) | 88214055: Luna hat am 10-11 die eigene Frage als „Text zum Prüfen“ gesetzt. | Behalten, solange sie greift. Sie kostet nichts und verhindert sichtbaren Unsinn. Zählen, nach 4 Wochen ohne Auslösung löschen. |
| Memory als **Pflichtfeld** an `compare_models`/`check_text` (nur mit Opt-in) | [`memory_field`](../app/services/agent_memory.py#L843) | b94aa8a7/6e7da484: Ein optionales Feld wurde einfach weggelassen („vegetarisch“ nicht gemerkt). | Mit den heutigen Modellen (Sonnet 5.5, Luna) neu proben, ob ein optionales Feld reicht: `scripts/probe_agent_routing.py --memory`, wenige Cent. |

Keine erzwungenen Abläufe, sondern Hinweise im Stil von Claude Code:
`AGENT_WRITE_NOTE` nach jedem Vergleich und die Anweisung im Vergleichsergebnis
(„write the answer when they suffice…“). Der Agent entscheidet trotzdem selbst.
Text neben einem Werkzeugaufruf wird zurückgenommen (`_retract`). Das ist Anzeige,
keine Entscheidung. Die Prüfung von Worker-Ergebnissen (`review_agent`) gilt nur
für die Delegation, und die ist in Prod aus.

### Schon freigegeben (die Richtung stimmt bereits)

- 10-11: Der Agent entscheidet selbst, ob er vergleicht. `next_step` (vorausplanen)
  ist entfallen, ebenso die Pflicht zum Vergleich bei direkten Antworten im freien
  Modus (`_free_floor`).
- 10-14: Kein `answer`-Werkzeug und kein getrennter Antwortschritt mehr. Der Agent
  schreibt die Antwort als letzte Nachricht selbst.
- 10-14: Der Rückhalt direkter Antworten (`_direct_reply_reminder`) wurde auf
  „nur nach eigener Suche“ eingeengt (`_tool_reminder`).
- 10-15: `check_contradictions` wurde entfernt.

## Der eigentliche Freiheitsgrad: vergleichen oder nicht

Ob die Prüfung läuft, hängt heute an einer einzigen Entscheidung des Agenten: Ruft
er `compare_models` auf? Wenn nicht, gibt es eine direkte Antwort ohne Prüfung und
ohne Kennzeichnung (Entscheidung vom 10-11). Geschützt ist das nur durch den Prompt
(„When in doubt, compare“) und den weichen `_tool_reminder` nach eigener Suche.

Wer das Versprechen „geprüft“ ernst nimmt, sollte also nicht beim Judge
nachschärfen, sondern hier messen. Die Frage: Wie viele direkte Antworten waren
eigentlich Faktenfragen, die einen Vergleich gebraucht hätten? Die Routing-Probe
vom 10-11 traf 12/12 und 13/13. Das sind aber gestellte Fälle, keine echten Chats.

## Messplan (Kosten vorher nennen, nichts davon ohne Max' OK)

1. **Leitplanken zählen.** Kostenlos, kleine Codeänderung. Heute hinterlassen
   `_tool_reminder`, die Ablehnung identischer Aufrufe und `_consensus_search_handoff`
   keine Spur im Turn. Vorschlag: ein Zähler `guards` pro Turn (z. B. in
   `agent_review`) für Reminder, Such-Übergabe, `own_request`, identische Aufrufe,
   ungültige Runden, Vergleichslimit und Memory-Sperre. Nach 4 Wochen ansehen. Was
   nie greift, wird gelöscht.
2. **Frei gegen geführt.** Bezahlt. `scripts/evaluate_agent_answers.py` misst schon
   Zeit, Kosten, Übereinstimmung und Hauptwidersprüche und kann mit `--baseline` +
   `--pairwise` blind vergleichen. Es fehlt nur ein Schalter `--autonomy free`.
   Dieselben ~20 Fragen einmal geführt, einmal frei. Kriterien: Qualität (blind),
   Kosten, Zeit, gefundene Uneinigkeit (frei darf nicht weniger finden) und die Zahl
   gefragter Familien. Grob geschätzt 5–10 $, vorher genau beziffern.
3. **Anteil direkter Antworten.** Prod lesen, nur mit OK. Aus den Turns seit 10-11:
   Anteil ohne Vergleich, davon eine Stichprobe von Hand. Wie viele waren
   Faktenfragen?
4. **Memory-Pflichtfeld.** Wenige Cent. Probe mit optionalem Feld gegen Luna und
   Sonnet 5.5.

Danach entscheidet Max eine Sache: ob „frei“ der Standard wird. Den Rest
(Leitplanken löschen oder behalten) entscheiden die Zahlen.

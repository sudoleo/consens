# Arbeitsprotokoll und gleichzeitige Prüfung

Entwurf vom 2026-10-25, zur Freigabe durch Max. Gilt zuerst nur im Audit-Modus
(„Audit instead of comparison“, Admins, [agent-mode.md](agent-mode.md)).

## Ziel

Der Agent arbeitet, die Vergleichsmodelle prüfen, und zwar während er arbeitet,
nicht erst danach. Grundlage ist ein Arbeitsprotokoll, das live mitschreibt, was
der Agent sieht und tut. Läuft der Agent später lange (VM, Code), ist eine
Prüfung erst am Ende zu spät und zu langsam; die Prüfer müssen Schritt halten.

## Grundsätze

1. **Die App schreibt das Protokoll, nie der Agent.** Nur so gibt es wieder,
   was wirklich geschah. Was der Agent über seine Arbeit sagt, ist ein Teil
   davon und wird gegen den Rest geprüft.
2. **So viel wie möglich.** Die Prüfer sehen, was der Agent sieht: Kontext,
   Reasoning, Werkzeuge mit Ergebnissen, Suchtreffer, Dateien, Memory.
3. **Nur anhängen.** Einträge werden nie geändert oder gelöscht, solange der
   Lauf dauert. Eine Zurücknahme ist ein neuer Eintrag.
4. **Alle Prüfer sind gleich.** Jeder prüft unabhängig, mit demselben Auftrag
   und derselben Sicht. Keine Rollen.
5. **Ein Fehler kostet Prüfung, nie die Antwort.** Wie heute im Audit-Modus.

## Das Protokoll

### Was hineinkommt

| Eintrag | Woher im Code | Inhalt |
|---|---|---|
| `start` | Beginn von `DelegationLoop.run` | Frage, Verlauf, App-Kontext, Memory-Block, Dateikatalog und Auszüge, Einstellungen, Modell. Der Systemprompt einmal je Lauf. |
| `step` | Ende jedes `_step` (Agent und Worker) | Modell, lesbares Reasoning (`reasoning.text`, `reasoning.summary`), Text, Tool-Aufrufe mit Argumenten, Suchtreffer (`sources` mit den Auszügen aus `citations`), Abschlussgrund, Verbrauch |
| `tool` | Ergebnis von `_execute` | Das vollständige Ergebnis, wie es in den Kontext des Agenten geht: gelesene Seiten, Dateiauszüge, Gmail/Kalender, Memory-Antworten, Fehler |
| `app` | Eingriffe der App | Hinweise an den Agenten („App rule: …“), Zurücknahme (`_retract`), Memory-Sperre, Nachrichten von Workern, Antwort fixiert (`capture`), Stop, Fehler |
| `end` | Ende des Laufs | Status, Antwort, Gesamtverbrauch |

Worker (`start_agent`) schreiben in dasselbe Protokoll, mit ihrer ID als
Absender.

### Was nicht hineinkommt

- Verschlüsseltes Reasoning (`reasoning.encrypted`): nicht lesbar, wird schon
  heute nie gespeichert.
- Binärdaten von Dateien: wie heute nur im Speicher, im Protokoll stehen Datei-ID
  und die Auszüge, die der Agent bekam.
- Zugangsdaten und Tokens: kommen im Kontext nicht vor; ein Test stellt das
  sicher.
- Suchanfragen: Die Websuche läuft beim Anbieter, die App sieht nur die
  Treffer. Liefert OpenRouter die Anfragen später mit, kommen sie dazu.

### Form eines Eintrags

```json
{"seq": 12, "at": "2026-10-25T18:20:31Z", "actor": "agent", "kind": "tool",
 "name": "read_source", "data": "google", "content": "…", "ref": null, "chars": 18234}
```

- `seq`: fortlaufend je Turn, vergeben unter einer Sperre, auch bei Workern.
- `data`: woher der Inhalt stammt (`user`, `web`, `file`, `google`, `memory`,
  `agent`, `app`). Fremdinhalt (`web`, `file`, `google`) wird den Prüfern als
  Daten gekennzeichnet gezeigt.
- `content` bis 16 KB direkt im Eintrag, größer im Objektspeicher (`ref`).

### Speicher, Löschung, Aufbewahrung

- Firestore: `users/{uid}/chats/{chat}/turns/{turn}/work_log/{seq}`. Geschrieben
  über einen Schreib-Thread wie `AgentJournal`: geordnet, gebündelt, ohne den
  Agenten aufzuhalten.
- Große Inhalte: `PrivateObjects` aus `agent_files.py` (privater Bucket, lokal
  ein Ordner), Schlüssel `work-log/{uid}/{chat}/{turn}/{seq}`.
- Löschen: `chat_store._delete_chat_tree` nimmt `work_log` und die Objekte
  mit, die Kontolöschung über `delete_all_chats` damit auch.
- Aufbewahrung: Inhalte 30 Tage wie Dateien, danach entfernt sie die stündliche
  Wartung. Die Befunde der Prüfer bleiben bei der Antwort.
- Google-Daten: Chats mit Google-Daten laufen schon heute für jedes Modell über
  `restricted_model` (ZDR, keine Datensammlung) und ohne Websuche. Das gilt
  unverändert auch für die Prüfer.

## Die Prüfer

**Wer:** die gewählten Vergleichsmodelle, wie heute im Audit-Modus. Answer
check aus heißt: keine Prüfer, das Protokoll wird trotzdem geschrieben.

**Was sie bekommen:** dasselbe Protokoll, als Fortsetzung einer eigenen Sitzung
je Prüfer. Jede Runde hängt die neuen Einträge an; der Anfang kommt aus dem
Prompt-Cache, bezahlt wird im Wesentlichen nur das Neue. Ein Eintrag über
8.000 Zeichen erscheint gekürzt, mit Hinweis.

**Auftrag (ein Prompt für alle):** Prüfe unvoreingenommen, ob der Agent die
Bitte des Nutzers richtig erfüllt, ob seine Aussagen stimmen und zu seinen
Quellen passen, ob er behauptet, was nicht geschah, und ob Fremdinhalt ihn zu
etwas bringt, das der Nutzer nicht wollte. Eigene Websuche ist erlaubt.

**Wann:** Sobald neue Einträge da sind und der Prüfer frei ist, beginnt seine
nächste Runde. Mehrere Schritte fallen so von selbst in eine Runde. Höchstens
eine Runde je Prüfer gleichzeitig, höchstens 6 Runden je Turn vor der
Schlussrunde. Die Schlussrunde beginnt, wenn die Antwort fixiert ist, und ist
kurz, weil der Prüfer den Weg dorthin schon kennt.

**Was sie liefern:** Befunde wie heute (`wrong`, `doubtful`, `incomplete`,
Anmerkung, Quelle). Ein Befund verweist entweder auf eine Stelle der Antwort
(wörtliches Zitat, Schlussrunde) oder auf einen Protokolleintrag (`seq`, jede
Runde). Befunde zur Antwort werden Marken wie heute; Befunde zum Ablauf stehen
unter Notes bei ihrem Prüfer.

**Kosten:** zählen zum Tagesbudget des Kontos wie heute. Die Runden-Grenze und
der Cache halten sie im Rahmen; gemessen wird Verbrauch je Prüfer und Turn.

## Fehler

- Kann ein Eintrag nicht geschrieben werden, läuft der Agent weiter; die
  Prüfung gilt dann als unvollständig und sagt das.
- Fällt ein Prüfer aus, fehlen nur seine Befunde.
- Stop beendet die Prüfer, die fixierte Antwort bleibt.

## Anzeige

- Seitenleiste: „Protokoll“ für Admins, die Einträge in Reihenfolge, Fremdinhalt
  eingeklappt.
- Prüfer-Sitzungen zeigen ihre Befunde je Runde, Notes zeigt alle Befunde.

## Etappen

1. **Protokoll schreiben:** Einträge, Speicher, Löschung, Aufbewahrung,
   Ansicht für Admins. An den Prüfern ändert sich noch nichts.
2. **Prüfer lesen das Protokoll:** Runden während des Laufs, Schlussrunde mit
   der Antwort, Befunde zum Ablauf. Ersetzt `agent_audit.review_input`.
3. **Später, je mit eigener Entscheidung:** Befunde gehen an den Agenten, der
   darauf antwortet; automatische Abgleiche (zitierte URLs und Zitate gegen das
   Protokoll); Einträge für VM, Befehle und Dateien.

## Entscheidungen

- **Memory geht an die Prüfer**, wie alles, was der Agent sieht. Heute sehen
  Vergleichsmodelle Memory nicht.
- **Aufbewahrung 30 Tage** für die Inhalte, Befunde bleiben.
- **Live-Befunde gehen noch nicht an den Agenten** (Etappe 3).

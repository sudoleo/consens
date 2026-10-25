# Arbeitsprotokoll und gleichzeitige Prüfung

Vom 2026-10-25, von Max freigegeben. Etappe 1 (das Protokoll) ist umgesetzt
(`app/services/agent_work_log.py`), Etappe 2 (die Prüfer lesen es) noch
nicht. Gilt zuerst nur im Audit-Modus („Audit instead of comparison“, Admins,
[agent-mode.md](agent-mode.md)).

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
| `start` | Beginn von `DelegationLoop.run` (`_log_start`) | Frage, Modell, Einstellungen, gewählte Dateien, Grenzen des Laufs |
| `context` | `_step`, direkt vor der Anfrage | Was die Anfrage trägt, je Akteur nur, was noch nicht im Protokoll steht. Nach Position im Gespräch des Akteurs: im ersten Schritt Systemprompt (mit Memory-Block), Verlauf (frühere Fragen und Antworten) und Frage mit App-Kontext, danach alles, was der Lauf anhängt, etwa Hinweise der App und Nachrichten von Workern, auch derselbe Hinweis ein zweites Mal. Was nur die einzelne Anfrage trägt (Dateiblock, Notiz eines Schritts, geänderter Systemprompt), einmal je Text. Die eigenen Nachrichten des Modells in diesem Lauf sind seine `step`-Einträge. |
| `step` | Ende jedes `_step` (Agent und Worker), nach der Abrechnung | Modell, Status, lesbares Reasoning (`reasoning.text`, `reasoning.summary`), Text, Tool-Aufrufe mit Argumenten, Suchtreffer (`sources` mit den Auszügen aus `citations`), Abschlussgrund, Verbrauch |
| `tool` | Ergebnis von `_execute` | Das vollständige Ergebnis, wie es in den Kontext des Agenten geht: gelesene Seiten, Dateiauszüge, Gmail/Kalender, Memory-Antworten, Fehler |
| `app` | Eingriffe der App | Zurücknahme eines gezeigten Texts (`retract`), Memory-Sperre (`memory_locked`), Antwort fixiert (`answer_fixed`) |
| `end` | Ende des Laufs | Status, Abschlussgrund, Antwort, Fehler, Gesamtverbrauch |

Worker (`start_agent`) schreiben in dasselbe Protokoll, mit ihrer ID als
Absender (`worker:<id>`). Nie im Protokoll: die Prüfer, die Judges und die
Seitenabrufe der App für `read_source` (`DelegationLoop._log_actor`); ihr
Ergebnis steht als `tool`-Eintrag darin.

### Was nicht hineinkommt

- Verschlüsseltes Reasoning (`reasoning.encrypted`): nicht lesbar, wird schon
  heute nie gespeichert.
- Binärdaten von Dateien: wie heute nur im Speicher, im Protokoll stehen Datei-ID
  und die Auszüge, die der Agent bekam.
- Zugangsdaten und Tokens: Sie stehen nie im Kontext eines Modells (der
  API-Schlüssel geht nur in den Header der Anfrage), also auch nicht im
  Protokoll.
- Suchanfragen: Die Websuche läuft beim Anbieter, die App sieht nur die
  Treffer. Liefert OpenRouter die Anfragen später mit, kommen sie dazu.

### Form eines Eintrags

```json
{"seq": 12, "at": "2026-10-25T18:20:31+00:00", "actor": "agent", "kind": "tool",
 "name": "read_source", "data": "web", "step": "completion:3", "format": "text",
 "chars": 18234, "content": "…die ersten 2.000 Zeichen…", "ref": "work-log/…/000012"}
```

- `seq`: fortlaufend je Turn, vergeben unter einer Sperre, auch bei Workern.
- `data`: woher der Inhalt stammt (`user`, `web`, `file`, `google`, `memory`,
  `agent` für Modellausgaben, `app`). Inhalt aus `web`, `file`, `google` und
  `agent` ist für jeden späteren Leser Daten, nie Anweisung
  (`UNTRUSTED_DATA`). Im Kontext entscheidet die Herkunft, nicht der Text
  (`context_data`): `user` sind nur Nachrichten des Nutzers vor der Frage
  dieses Laufs und die Frage selbst; was der Lauf danach als Nutzernachricht
  anhängt, ist von der App (`app`) oder von Workern (`agent`); alles, was ein
  Worker liest, ab seinem Auftrag, schrieb der Agent (`agent`).
- `format`: `text`, oder `json` für `start`, `step`, `app` mit Daten und `end`.
- `content` bis 16.000 Zeichen direkt im Eintrag. Länger: ganz im
  Objektspeicher (`ref`), im Eintrag die ersten 2.000 Zeichen. Ohne
  Objektspeicher bleibt er auf 16.000 Zeichen gekürzt (`truncated`).

### Speicher, Löschung, Aufbewahrung

- Firestore: `users/{uid}/chats/{chat}/turns/{turn}/work_log/{seq:06d}`.
  Ein Schreib-Thread speichert geordnet, bis zu 50 Einträge je Transaktion
  (`AgentSessionStore.save_work_log`), ohne die Kontosperre, auf die
  Modellaufrufe warten. Die Transaktion liest weder den Root-Beleg noch
  sonst etwas, das Belegung, Abrechnung oder Sitzungen eilig schreiben (eine
  Server-Transaktion sperrt, was sie liest), nur Löschmarke, Turn und Chat:
  Sie schreibt, solange der Turn läuft (`pending`), der Chat aktiv ist und
  das Konto nicht gelöscht wird. Der Schreib-Thread beginnt erst nach dem
  ersten belegten Schritt des Laufs; ein Lauf ohne Modellaufruf hat kein
  Protokoll. Drei Versuche je Bündel; danach sind die Einträge verloren,
  schon abgelegte Inhalte werden wieder entfernt, und der Turn trägt
  `work_log_incomplete`. Am Laufende wartet der Lauf höchstens 20 s auf den
  Rest; was dann noch fehlt, ist verloren, und dem Protokoll fehlt der
  `end`-Eintrag, was die Ansicht als unvollständig zeigt.
- Große Inhalte: `PrivateObjects` aus `agent_files.py` (privater Bucket, lokal
  ein Ordner, ein Client je Konfiguration), Schlüssel
  `work-log/{uid}/{chat}/{turn}/{seq}`.
- Löschen: `chat_store._delete_chat_tree` ruft je Turn
  `agent_work_log.delete_turn_log`: erst die Inhalte, die Einträge mit `ref`
  nennen, dann die Einträge. Ein Turn ohne Protokoll kostet eine leere
  Abfrage und keinen Aufruf des Objektspeichers. Die Kontolöschung läuft über
  `delete_all_chats` mit.
- Aufbewahrung: Der Turn trägt `work_log_expires_at` (30 Tage nach dem
  Start); die stündliche Wartung (`cleanup_expired_work_logs`, Index auf der
  Collection-Group `turns`) entfernt danach Einträge und Inhalte. Die Befunde
  der Prüfer bleiben bei der Antwort. Die Inhalte sind von der Indizierung
  ausgenommen (`firestore.indexes.json`).
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

- Kann ein Eintrag nicht geschrieben werden, läuft der Agent weiter; das
  Protokoll gilt dann als unvollständig (`work_log_incomplete`), und die
  Ansicht sagt das. In Etappe 2 sagt es auch die Prüfung.
- Fällt ein Prüfer aus, fehlen nur seine Befunde.
- Stop beendet die Prüfer, die fixierte Antwort bleibt.

## Anzeige

- Seitenleiste: Abschnitt „Work log“ am Ende der Sitzungsliste, nur für
  Admins und nur bei Turns mit Protokoll (`agent_work_log` am Turn, im
  laufenden Turn die Audit-Einstellung). Lädt erst beim Öffnen, folgt einem
  laufenden Turn alle 3 s und lädt nach dessen Ende die letzten Einträge.
  Jede Zeile: Nummer, Absender, Art, Name, Herkunft (Fremdinhalt gestrichelt
  umrandet), Uhrzeit; der Inhalt öffnet sich auf Klick, ein langer ganz über
  „Show all“. Endpunkte: `GET /agent/chats/{chat}/turns/{turn}/work-log` und
  `.../work-log/{seq}`, beide nur für Admins.
- Etappe 2: Prüfer-Sitzungen zeigen ihre Befunde je Runde, Notes zeigt alle
  Befunde.

## Etappen

1. **Protokoll schreiben** (umgesetzt 2026-10-25): Einträge, Speicher,
   Löschung, Aufbewahrung, Ansicht für Admins. An den Prüfern ändert sich
   noch nichts.
2. **Prüfer lesen das Protokoll:** Runden während des Laufs, Schlussrunde mit
   der Antwort, Befunde zum Ablauf. Ersetzt `agent_audit.review_input`.
3. **Später, je mit eigener Entscheidung:** Befunde gehen an den Agenten, der
   darauf antwortet; automatische Abgleiche (zitierte URLs und Zitate gegen das
   Protokoll); Einträge für VM, Befehle und Dateien.

## Entscheidungen (Max, 2026-10-25)

- **Memory geht an die Prüfer**, wie alles, was der Agent sieht. Heute sehen
  Vergleichsmodelle Memory nicht.
- **Aufbewahrung 30 Tage** für die Inhalte, Befunde bleiben.
- **Live-Befunde gehen noch nicht an den Agenten** (Etappe 3).
- **Keine Rollen:** Alle Prüfer sind gleich und prüfen unabhängig.

Tests: `tests/test_agent_work_log.py`, `tests/js/agent-work-log.test.mjs`.

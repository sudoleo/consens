# Watches & Topics: Belegmodell

Stand 2026-10-01. Dieses Dokument ist der Vertrag für die Änderungserkennung von
Consensus Watches und Topics. Die Regeln leben in genau einem Modul,
`app/services/drift_signal.py`; Judge-Prompt und Belegprüfung in
`app/services/llm/consensus_engine.py` (`query_consensus_change`) und
`app/services/evidence_change.py`.

## Warum

Bis hierhin stellte jeder Check die Frage neu und ließ einen Judge zwei Texte
vergleichen. Der Judge sah keine Quellen und konnte deshalb nicht unterscheiden,
ob die Welt sich bewegt hat oder ob die Websuche diesmal etwas übersehen hat.
Der GPT-6-Topic zeigt die Folge: 9. Sep. „GPT-6 Astra offiziell angekündigt",
23. Sep. „nicht bestätigt", 30. Sep. „hypothetisch" – während Astra längst
veröffentlicht war. Jeder Rückfall wurde als echte Änderung gemeldet.

## Mentales Modell

**Watch** – privat, mit Ziel. „Sag mir, wenn X passiert." Die Watch wartet auf
etwas, meldet nur belegte Bewegung und ist **abgeschlossen**, sobald das Ziel
belegt eingetreten ist.

**Topic** – öffentlich, kuratiert, ohne Ende. Eine Chronik, die festhält, was
wann belegt war. Topics schließen nie; sie nutzen dieselbe Änderungserkennung,
aber keine Ziele.

Gemeinsam ist beiden: **Eine Antwort ändert sich nur durch Belege.** Was ein
Check nicht wiederfindet, gilt nicht als widerlegt.

Abgrenzung zu einem geplanten Chat-Prompt (so erklärt es die App):

| Geplanter Prompt | consens.io Watch |
| --- | --- |
| ein Modell beantwortet die Frage neu | drei Modellfamilien unabhängig, gegengeprüft |
| jedes Mal eine neue Antwort, Vergleich macht der Mensch | meldet nur, was sich belegt geändert hat – mit Quelle |
| ein Suchtreffer weniger = andere Antwort | Fehlende Quelle ≠ Gegenbeleg; Neubewertung erst nach Bestätigung |
| läuft, bis man es abstellt | kennt sein Ziel und schließt ab |

## Ein Check

1. Die Modelle antworten wie bisher **unabhängig** (kein Vorwissen im Prompt –
   die Unabhängigkeit ist der Kern des Produkts).
2. Der Change-Judge vergleicht die neue Antwort mit der **geltenden** Antwort
   (nicht mit dem letzten Lauf) und bekommt **beide Quellenlisten**; jede neue
   Quelle trägt `seen_before`.
3. Er liefert `changed`, `severity`, `change_summary`, `held_summary`, die
   **Ursache** (`cause`) und die tragenden Quellen (`evidence`), bei einem Ziel
   außerdem `condition_status`, `condition_reason`, `condition_evidence`.
4. Der Server prüft die Belege deterministisch (`evidence_change.verify`):
   * zitierte IDs müssen Quellen dieses Laufs sein, sonst fallen sie weg;
   * `new_evidence` braucht mindestens eine zitierte Quelle, deren URL in der
     geltenden Antwort nicht vorkam – sonst wird daraus `reassessment`;
   * hat sich die Modellbesetzung gegenüber der geltenden Antwort geändert,
     wird aus `reassessment` → `model_change`.

### Ursachen (`cause`)

| Wert | Bedeutung |
| --- | --- |
| `new_evidence` | neue, zitierte Quelle trägt die Änderung |
| `evidence_missing` | die Quellen der geltenden Antwort tauchten nicht auf, nichts widerspricht ihr |
| `reassessment` | dieselbe Beleglage, die Modelle lesen sie anders |
| `model_change` | wie `reassessment`, aber die Modellbesetzung hat gewechselt |
| `none` | keine inhaltliche Änderung |

## Signal je Check (`drift_signal.annotate_points`)

Aus Ursache, Schwere und dem **nächsten** Check abgeleitet, nie gespeichert –
alte Historie wird beim Lesen neu bewertet.

| Signal | Regel | geltende Antwort? |
| --- | --- | --- |
| `moved` | major + `new_evidence`, **oder** major-Neubewertung, die der direkt folgende Check wiederholt (der folgende Check ist dann `moved`) | ja |
| `confirming` | major + `reassessment`/`model_change`, Nachprüfung steht aus (nur der neueste Check) | nein |
| `preliminary` | der erste Sichtpunkt einer später bestätigten Neubewertung | nein |
| `reverted` | major-Neubewertung, die der nächste Check nicht wiederholt | nein |
| `held` | major + `evidence_missing` – die geltende Antwort bleibt stehen | nein |
| `restated` | `changed`, aber minor | ja |
| `stable` | sonst | ja |

* `trigger == "changed"` ⇔ `signal == "moved"` (Badge, Kurve, Mail, Brief,
  Follower – ein Balken für alles).
* Der Agreement-Score löst **kein** Ereignis mehr aus. Er springt zwischen
  festen Stufen (90/84/64/39) und bleibt als `score_event` nur eine Markierung
  in der Kurve.
* Historie ohne `cause` (vor diesem Modell geschrieben) behält die alte Regel
  (major oder Score-Band) – kein Backfill.

### Bestätigung

Ein `confirming`-Check setzt `next_run_at = jetzt + CONFIRMATION_DELAY`
(20 min). Der Nachprüf-Check vergleicht wieder mit der geltenden Antwort. Es
gibt höchstens einen Nachprüf-Check pro Ereignis; Schleifen sind ausgeschlossen,
weil ein Check nach `confirming` entweder `moved` oder nicht-major ist.

### Geltende Antwort (`accepted_run_id`)

Watch und Topic führen einen Zeiger auf den letzten Check, dessen Antwort gilt
(Signal `moved`, `restated`, `stable`). Er ist die Vergleichsbasis
für den nächsten Check und die Standardansicht der öffentlichen Seite.
Fehlt er (Altbestand), gilt der letzte erfolgreiche Lauf.

## Ziel und Abschluss (nur Watches)

* Feld bleibt `condition` (≤ 500 Zeichen); die Oberfläche nennt es „Ziel" –
  „Worauf wartest du?". Ziele werden bei jedem Check bewertet, unabhängig vom
  Alarmmodus.
* `POST /api/watch/goal-suggestions` schlägt bis zu drei beobachtbare Ziele zur
  Frage vor (ein günstiger Judge-Call, rate-limitiert).
* **Abschluss**: `condition_status == "met"` **und** (mindestens eine
  verifizierte `condition_evidence` **oder** der vorige Check war mit demselben
  Ziel ebenfalls `met`). Ohne Beleg löst ein erstes `met` einen Nachprüf-Check
  aus.
* Abschluss setzt `status = "resolved"`, `resolution = {run_id, at, reason,
  sources}`, gibt den Slot frei (zählt nicht mehr als aktiv) und meldet
  „Resolved". Weiterbeobachten (`status = active`) braucht ein neues oder
  leeres Ziel.
* Alarmmodi: `changes_only` = bewegt oder abgeschlossen (Standard),
  `condition` = nur abgeschlossen, `every_run` = jeder Check.

## Vorprüfung (`watch_probe`)

Zwischen zwei vollen Checks (weekly/monthly, keine Publisher-Watches) prüft
einmal täglich **ein** günstiges Modell mit Websuche, ob es seit dem letzten
Check neue Belege zur Frage oder zum Ziel gibt. Findet es eine Quelle, die in
der geltenden Antwort fehlt, wird der volle Check auf jetzt vorgezogen. Sonst
passiert nichts. Eigener Tagesdeckel `watch_probe_max_per_day`; Fehler bleiben
folgenlos (der reguläre Check kommt ohnehin).

## Benachrichtigung

Mail und Telegram sind ein kurzes Änderungsprotokoll: **Was sich geändert hat**,
**Warum** (Ursache + neue Quellen mit Host), **Was gleich blieb**, Zielstand.
Die Score-Zeile entfällt.

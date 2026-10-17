# Agent ändert Kontoeinstellungen — Evaluation (2026-10-17)

Frage: Kann der consens.io-Agent auf Zuruf („stell X um“) die Kontoeinstellungen
des Nutzers ändern, mit den Grenzen der Stufe, wie Claude Code es mit
`set_setting`/`effortLevel` macht? Nur Evaluation: Code gelesen, nichts
umgesetzt, keine Modell-Calls. Die Reasoning-Matrix unten ist offline aus dem
Code-Katalog berechnet (`UNIT_TEST_MODE=1`, `agent_model_options()`).

**Stand:** v1 umgesetzt am 2026-10-17 (Max: „mach“), so wie unten empfohlen.
Abweichungen vom Plan: Für nicht angebotene Stufen nimmt das Werkzeug die
nächstgelegene (nicht immer die darunter, sonst würde „Medium“ bei Mistral zu
„Off“); es liest keine Kontoeinstellungen, „jetzt“ für Modell und Vorlieben kommt
vom laufenden Turn, für Preset und Anzeige nur aus der Karte; das Modell
übernimmt die Karte über die Picker-Funktion (`App.agentChat.applyPick`), weil
ein offener Chat sonst mit seinem gespeicherten Modell weiterliefe. Der
Pro-Hinweis nennt keine Kontaktadresse. Ablauf und Regeln:
[agent-mode.md](agent-mode.md) „Einstellungen umstellen“ und
[codebase-map.md](codebase-map.md) „Agent-Einstellungen“.

**Zweite Runde (2026-10-17, vor dem Deploy):** unabhängiges Review und
Live-Proben mit echten Modellen (Claude Sonnet 5.5 in 17 Fällen, GPT-5.6 Luna in
10). Daraus kamen: `read_settings` (was gilt, Standards, Wahl des Kontos) und
Rückfragen statt Raten bei unklaren Wünschen; Modellsuche nach Wörtern mit
Tippfehler-Vorschlag, ohne Pro direkt „alle Treffer sind Pro“; das
Werkzeug liest doch das Kontodokument (Preset, Anzeige, Kontowahl des Modells
für „schon so“); mehrere Aufrufe eines Turns addieren sich; nach Fremdinhalten
nur mit Zitat aus der Nutzernachricht; Pro wie im Picker (ohne Admin);
Google-Modellbeschränkung; die Karte merkt sich übernommen/abgewiesen pro
Antwort; der Grund bei Pro-Stufen sagt, dass kein anderes Modell sie aufhebt
(Sonnet schlug sonst „anderes Modell wählen“ als Umweg vor); `claim_counts`
als `on`/`off` (Sonnet schickte `"false"` als Text). Wer fragt, wie man Pro
bekommt, erhält die Worte des Early-Access-Dialogs samt contact@consens.io.

**Empfehlung in einem Satz:** Variante (c) — ein Werkzeug
`prepare_settings_change`, das nur vorschlägt und am Server gegen Stufe und
Modell prüft, plus eine Karte unter der Antwort mit „alt → neu“, die der Nutzer
mit einem Klick übernimmt. Die Karte schreibt über den bestehenden Weg
`App.userSettings.set` → `PATCH /api/my/settings`; einen neuen Schreibpfad gibt
es nicht.

---

## 1. Bestand

### Einstellungen am Konto

`app/services/user_settings.py` (`UserSettings`, Pydantic strict, alle Felder
optional), gespeichert unter `users/{uid}/settings/app`. `GET/PATCH
/api/my/settings` (`app/api/routers/users.py:505`), Browser-Besitzer
`static/js/user-settings.js` (`App.userSettings`), Paritätstest
`tests/test_user_settings.py::test_the_browser_keeps_and_checks_the_settings_the_server_stores`.

| Einstellung | Werte | Stufen-Grenze? | Wo erzwungen |
|---|---|---|---|
| `run_mode` | compare / consensus / agent | keine | – |
| `agent_model.model_id` | Registry-ID | Premium-Modelle nur Pro; das Standard-Chatmodell (Sonnet 5.5, „Early access“) für alle | Lauf: `require_model_access` (`routers/agent.py:73`) → 403 |
| `agent_model.reasoning_effort` | default, none … max | high/xhigh/max nur Pro | Lauf: `require_reasoning_access` (`routers/agent.py:86`) → 403; Auto ohne Pro → Medium (`free_default_effort`) |
| `agent_preferences` | depth auto/quick/full, quorum balanced/fast/all, autonomy guided/free | keine | – |
| `compare_models` | je Familie `{enabled, model}` | Premium-Modelle nur Pro | Lauf: `llm/base.py:63` → 403, Agent-Vergleich über `require_model_access` |
| `consensus_model` | Modell-ID | Premium nur Pro | Lauf (wie oben) |
| `consensus_preset` | fast (Daily) / balanced (Open Models) / thorough (High Quality) / custom | `thorough` ist `pro_only` | indirekt: die Modelle darin sind Premium → 403 im Lauf |
| `system_prompt` | Freitext ≤ 12 000 Zeichen | keine | Länge am Server |
| `agreement_display` | full / summary / off | keine | – |
| `consensus_highlights` | none / all / contradictions / concerns / critical | keine | – |
| `claim_counts` | bool | keine | – |

**Wichtigster Befund:** `PATCH /api/my/settings` prüft **nur die Form**, nie die
Stufe (`validate_changes`). Ein Free-Konto kann `agent_model = Opus 4.8 / max`
speichern; erst der nächste Lauf antwortet 403. Die Stufe wird also **am Server
erzwungen, aber erst beim Lauf**, und im UI vorher gesperrt dargestellt
(`agent-chat.js` `locked()`/`effortLocked()`, fällt bei gespeicherter
Pro-Stufe auf Auto zurück). Das ist richtig so: nach einem Downgrade muss der
Datensatz lesbar bleiben. Für den Agenten heißt es aber: Das Werkzeug muss die
Stufe **selbst beim Vorschlag** prüfen, sonst bereitet es Einstellungen vor, die
den nächsten Lauf scheitern lassen.

**Early:** Eine eigene Early-Stufe gibt es im Code nicht mehr (`is_user_early`,
`EARLY_MODELS` sind weg). „Early access“ ist nur noch das Badge des
Standard-Chatmodells: als Chatmodell frei für alle, als Vergleichsmodell Pro.
**Plus** ist bei Modellen und Reasoning exakt Free (`is_pro` ist für Plus
False); Plus unterscheidet sich nur bei Resolve, Kontingent und Watch-Slots.

### Was bewusst nicht am Konto liegt

Theme, Sidebar, Entwurf, eigener OpenRouter-Key, Analytics-Opt-out, gesehene
Hinweise (Browser). Eigene Endpunkte: Memory (`/api/my/memory*`, inkl.
Opt-in „Let Agent update memory“), Watch-Brief (`PATCH /api/my/watch-brief`),
Telegram, Google-Verbindungen, Shares/Indexing, `/delete_account`.

## 2. Reasoning pro Stufe und Modell

**Korrektur der Vermutung:** Nicht „Pro hat nur xhigh und max“, sondern
umgekehrt: **high, xhigh und max sind die Pro-Stufen** (`PRO_REASONING_EFFORTS`,
`agent_client.py:404`). Pro hat jede Stufe, die das Modell anbietet; Free und
Plus haben die Stufen darunter. Kompliziert wird es, weil jedes Modell eine
andere Liste anbietet (aus dem OpenRouter-Katalog, in Prod alle 5 Minuten live
nachgeladen) und manche Registry-Einträge eine Stufe fest vorgeben.

Chatmodelle für alle (Code-Registry; Prod-Liste kommt aus der Admin-Konfiguration):

| Modell | Pro | Free / Plus | „Auto“ ohne Pro |
|---|---|---|---|
| Claude Sonnet 5.5 (Default) | low, medium, high, xhigh, max | low, medium | Medium |
| GPT-5.6 Luna | none … max | none, low, medium | Medium |
| GPT-5.4 mini | none … xhigh | none, low, medium | Medium |
| GPT-5 mini / Nano | minimal … high | minimal, low, medium | Medium |
| Gemini 3.1/3.5 Flash-Lite, 3.6 Flash | minimal … high | minimal, low, medium | Medium |
| Grok 4.3 | none … high | none, low, medium | Medium |
| DeepSeek V4.1 Flash | low, high, max | **nur low** | Modell-Default (high) |
| Mistral Small 4 | none, high | **nur none** | aus |
| GLM 5.3 Flash | low, high, max | nur low | fest low |
| Muse Glimmer 30B | low … xhigh | low, medium | fest low |
| gpt-oss-120b | low, medium, high | low, medium | fest low |
| Kimi K2.6, Haiku 4.5, Gemini 2.5 Flash, Gemma 4, GPT-4.1/4o | – | – | nur Auto |

Premium-Modelle (nur Pro, dann alle angebotenen Stufen): GPT-5.6 Sol (none … max),
Opus 4.8 (low … max), Grok 4.7 (low … xhigh), DeepSeek V4 Pro (high, xhigh),
Kimi K3 / GLM 5.3 (low, high, max), Gemini 3.1 (low … high), Gemini 3.5 Flash,
GPT-5 … 5.5, Mistral Medium 3.5 (none, high), Gemini 2.5 Pro (nur Auto).

Nebenbefund, nicht Teil dieser Aufgabe: Bei DeepSeek V4.1 Flash denkt ein
Free-Konto unter „Auto“ auf dem Modell-Default **high**, das es explizit nicht
wählen darf (`free_default_effort` greift nur, wo Medium angeboten wird). Bei
dem Preis harmlos und so dokumentiert („ohne Medium bleibt Auto“); das Werkzeug
behandelt Auto deshalb einfach als immer erlaubt.

### Regel für den Agenten

Eine Regel, eine Quelle: Das Werkzeug ruft dieselben Funktionen wie
`run_agent` auf (`resolve_agent_model`, `_choices`, `PRO_REASONING_EFFORTS`,
`_premium_allowed`); es gibt keine zweite Liste.

1. **Erlaubt = vom Modell angeboten ∩ von der Stufe erlaubt.** Auto (`default`)
   ist immer erlaubt.
2. **Stufe zu hoch für das Konto** (Free will Max): auf die **höchste erlaubte**
   Stufe begrenzen (Sonnet: Medium; DeepSeek Flash: Low), Status `adjusted`
   mit Grund. Der Agent sagt ehrlich: „Max ist auf Pro; ich habe dir Medium
   vorbereitet, das Höchste für dein Konto.“ Kein Upsell (es gibt nichts zu
   kaufen), dieselbe Formulierung wie die App selbst.
3. **Modell bietet die Stufe nicht an** (Mistral hat kein Medium): die
   nächstgelegene erlaubte Stufe, bei Gleichstand die leichtere; Status
   `adjusted`, Grund nennt die Liste des Modells (und welche davon Pro sind).
4. **Premium-Modell ohne Pro: ablehnen, nicht ersetzen.** Ein anderes Modell als
   gewünscht wäre eine Überraschung. Status `refused`, der Agent nennt das freie
   Modell derselben Familie (Opus → Sonnet 5.5).
5. **Modellwechsel prüft die Stufe neu.** Sonnet/Max → GPT-5 mini wird Medium
   bzw. für Pro High. Ohne genannte Stufe bleibt Auto.
6. **Relative Wünsche** („denk gründlicher“, „schneller“): eine Stufe hoch bzw.
   runter vom aktuellen Wert, nicht direkt Max. Das Werkzeugergebnis liefert
   dafür `current` und `allowed`; die Liste steht nicht im System-Prompt (der
   bleibt statisch und cachebar).
7. **Wirkt ab der nächsten Nachricht.** Der laufende Turn ist schon aufgelöst;
   der Agent sagt das, statt so zu tun, als denke er jetzt schon anders.

## 3. Mechanik — drei Varianten

Entscheidender technischer Befund: Der Browser liest Kontowerte **nur beim
Login** (`user-settings.js` `start` → `fetchAccount`); es gibt kein Nachladen
bei Fokus oder nach einem Turn. Und jeder Lauf schickt Modell, Stufe,
Vorlieben und Vergleichsmodelle **aus dem Browser-Zustand** mit (`AgentRequest`).
Ein Wert, den nur der Server ändert, wirkt im offenen Tab also erst nach einem
Neuladen. Außerdem ignorieren alle Module Änderungen mit `source: "local"`
(`agent-chat.js:1533`, `run-mode.js:96`, `model-picker.js:485` …), weil sie
die selbst ausgelöst haben.

| | (a) `set_setting` schreibt direkt | (b) Einstellungs-„Datei“ lesen/schreiben | (c) vorbereiten + Karte |
|---|---|---|---|
| Sicherheit | schwach: eine Injektion aus Web/Datei/Mail schreibt ohne Klick; Pro-Konten zahlen Max-Stufen aus ihrem Tokenkonto | schwächer: freies JSON, der Agent muss unberührte Werte mit zurückschreiben (Risiko, `system_prompt` oder `compare_models` zu überschreiben) | stark: Werkzeug schreibt nichts; nur der Klick des Nutzers in seiner Sitzung schreibt — eine Injektion kann nicht klicken |
| Aufwand | mittel: neuer Server-Schreibpfad **plus** Push ins offene Tab (sonst wirkungslos bis Reload) | höher: wie (a) plus Diff/Merge eines Dokuments, Validierung trotzdem pro Feld | mittel: Werkzeug + Karte; Schreiben über den vorhandenen PATCH-Weg |
| UX | null Klicks, aber still; „hat es geklappt?“ erst nach Reload | unanschaulich: ein Dokument statt „alt → neu“ | ein Klick, sichtbar „Reasoning: Auto → Medium“, sofort wirksam im Tab |
| Fehleranfälligkeit | Konflikt mit dem Tab: der nächste Lauf nutzt den alten Browser-Wert, Revisionen laufen auseinander | hoch: LLM reproduziert Werte, Teil-Schreibungen | gering: Karte rechnet „alt“ beim Anzeigen aus dem aktuellen Browserwert; Server validiert wie immer |

**Zu (b):** Der brauchbare Kern der Idee ist **lesen**, nicht schreiben: Der
Agent bekommt im Werkzeugergebnis eine Sicht auf die aktuellen Werte und das
Erlaubte (wie eine Datei, die er liest). Schreiben über ein Dokument ist nur
eine unschärfere Form von (a). In Claude Code funktioniert das, weil der Nutzer
dort einen Datei-Diff mit Freigabe sieht; das wäre hier wieder (c).

**Zu (c) technisch:** `App.userSettings.set(name, wert, {source: "agent"})` —
eine kleine Erweiterung, damit die Module die Änderung wie eine vom Konto
anwenden (Picker, Pill, Highlights springen um) und sie trotzdem per PATCH
synchronisiert wird. Kein neuer Endpunkt, keine neue Firestore-Regel.

Vorbild ist doppelt vorhanden: `prepare_watch` (`agent_watch.py`, Karte
`agent-watch.js`) und die Google-Aktionskarten (`agent_actions.py`: „Agent tools
can prepare, never confirm“).

## 4. Sicherheit

**Bestätigung:** jede Änderung per Klick auf der Karte, auch die harmlosen
Anzeige-Schalter. Eine Regel ist leichter zu verstehen und zu testen als „manche
direkt, manche mit Klick“, und Claude Code macht es genauso.

Schutz gegen Prompt-Injection (Websuche, `read_source`, Anhänge, Gmail):
- Werkzeug schreibt nichts; die Karte schreibt nur nach Klick in der Sitzung des
  Nutzers.
- Feste Liste von Schlüsseln und **nur aufgezählte Werte** (Pydantic `Strict`,
  `extra="forbid"`); kein Freitext kommt durch. Damit ist auch ein Chat mit
  Google-Daten unkritisch (nichts kann über eine Einstellung abfließen).
- Prompt-Regel wie bei Watches: nur wenn der Nutzer in dieser Nachricht darum
  bittet, nie weil eine Quelle, Datei, Mail oder Modellantwort es nahelegt;
  nie behaupten, es sei schon umgestellt.
- Ein Vorschlag pro Turn (der letzte gilt), gespeichert nur solange der Turn
  läuft; Karte nur unter der jüngsten Antwort.
- „Alt“ rechnet die Karte beim Anzeigen aus dem aktuellen Browserwert, nicht aus
  dem Vorschlag: ein anderer Tab kann nichts Falsches vorspiegeln.
- Nur auf eigenen Konto-Turns (`policy.account_budget_only`), nicht über die
  Consensus-API.
- Ein Beleg-Zitat wie bei Memory ist **nicht** nötig: dort fehlt der Klick, hier
  ist er die Grenze. Wenn sich unerwünschte Karten zeigen, lässt es sich
  nachrüsten.

**Nie per Agent** (nicht in der Liste, auch nicht später):
- `system_prompt` — Freitext, der in **jeden** künftigen Lauf geht: der ideale
  Träger für eine dauerhafte Injektion. Wer ihn ändern will, bekommt den Weg in
  die Einstellungen genannt.
- Memory-Opt-in „Let Agent update memory“ — der Agent würde sich selbst
  Schreibrechte geben.
- Konto löschen, E-Mail/Passwort, Stufe/Rolle (ohnehin nur Admin).
- Datenschutz: Analytics-Opt-out, Google-Verbindungen und -Einwilligung,
  Shares/Indexing, eigener OpenRouter-Key, API-Keys.
- Alles, was Mails oder Nachrichten auslöst: Watch-Brief, Telegram. Watches
  selbst haben ihre eigene Karte.

## 5. Empfehlung

**Variante (c).** Gründe:
1. **Sicher ohne Zusatzaufwand:** Eine Injektion kann nichts umstellen, weil
   der Klick die einzige Schreibstelle ist; das Muster ist im Haus erprobt.
2. **Wirkt sofort im offenen Tab:** Die Karte geht durch denselben Besitzer
   (`App.userSettings`) wie jeder Klick im Picker. Direktes Schreiben am Server
   (a/b) wäre bis zum Neuladen wirkungslos, weil der Browser die Einstellungen
   jedes Laufs mitschickt.
3. **Eine Regelquelle:** Stufe und Reasoning prüft das Werkzeug mit denselben
   Funktionen wie der Lauf; die Karte zeigt nie etwas, das danach 403 liefert.

### Erste Version

Drin (alle aufgezählt, alle häufig gefragt):
- `agent_model` — Modell und Reasoning, mit den Regeln aus §2.
- `agent_preferences` — Tiefe (Quick/Full), Antwortstart, guided/free.
- `consensus_preset` — Daily / Open Models / High Quality (letzteres Pro); das
  ist die Aufstellung, die ein Agent-Vergleich nutzt.
- `agreement_display`, `consensus_highlights`, `claim_counts` — harmlos und
  billig mitzunehmen.

Nicht in v1: `compare_models`/`consensus_model` (Familien-Feinwahl, verschachtelt,
selten per Sprache verlangt), `run_mode` (der Agent würde sich selbst
abschalten; die Pill ist ein Klick), `system_prompt` (nie).

### Grober Umsetzungsplan (≈ 1 Tag)

Backend
- `app/services/agent_settings.py` (neu): Argument-Schema (`Strict`, Union je
  Schlüssel mit aufgezählten Werten, höchstens ein paar Änderungen pro Aufruf),
  `SettingsTools` wie `WatchTools`: liest bei Aufruf (nicht pro Turn) Stufe
  (`get_user_tier`, gecacht) und `users/{uid}/settings/app`, wendet §2 an,
  speichert den Vorschlag als `agent_settings_proposal` am laufenden Turn
  (Transaktion wie `WatchTools._save`), Ergebnis je Änderung
  `prepared|adjusted|refused` + `current` + `allowed` + Grund; Prompt-Abschnitt;
  `mock_turn` („Settings: …“) für Browser-Tests.
- `agent_delegation.py`: registrieren auf Konto-Turns; `agent_answer_mode.SIDE_TOOLS`
  um das Werkzeug ergänzen.
- Hilfsfunktion „höchste erlaubte Stufe“ neben `free_default_effort` in
  `agent_client.py`, damit Werkzeug und Lauf dieselbe Logik teilen.

Frontend
- `static/js/agent-settings-card.js` (neu) + CSS, in `static/js/bundles.json`
  nach `agent-watch.js`; Karte „alt → neu“ je Zeile, „Apply“ / „Dismiss“,
  Status nach dem Klick.
- `user-settings.js`: Option `source: "agent"` für `set`.
- `agent-chat.js`: Vorschlag der abgeschlossenen jüngsten Antwort an die Karte
  geben (wie beim Watch-Vorschlag).
- `npm run build`.

Tests
- `tests/test_agent_settings.py`: Liste der Schlüssel, unbekannter Schlüssel,
  Reasoning-Matrix (Free/Plus/Pro × Sonnet/DeepSeek Flash/Mistral), Premium
  abgelehnt für Free/Plus, `thorough` nur Pro, Admin wie Pro, Vorschlag nur bei
  laufendem Turn, **das Werkzeug ruft nie `FirestoreUserSettingsRepository.update`**.
- `tests/js/agent-settings-card.test.mjs`, Ergänzung `tests/js/user-settings.test.mjs`
  (`source: "agent"` wird synchronisiert und von Modulen angewandt).
- Eine E2E-Datei mit dem Mock-Trigger.
- Vor dem Deploy ein kurzer Live-Probe mit `scripts/probe_agent_routing.py`
  (5–6 Prompts: „nimm Max“, „denk gründlicher“, Injektion in einer Quelle,
  Frage ohne Einstellungswunsch) — braucht dein OK, Kosten wenige Cent.

Doku: `docs/codebase-map.md` (neues Agent-Werkzeug, Karte, `source: "agent"`),
`docs/agent-mode.md`.

### Offene Produktfragen an Max

1. **Priorität:** Bauen wir das jetzt? Bei ~11 Wochennutzern ist Reichweite der
   Engpass (Potenzialanalyse vom 2026-10-07); das hier ist Komfort, kein
   Wachstum. Meine Meinung: lohnt sich nur als kleine v1 (≈ 1 Tag), weil der
   Agent heute auf „nimm Opus“ oder „denk gründlicher“ nichts tun kann —
   sonst parken.
2. **Pro-Hinweis:** Wenn ein Free-Konto Max oder ein Premium-Modell will, sagt
   der Agent „ist auf Pro“ (wie die App). Sollen wir zusätzlich auf
   `contact@consens.io` verweisen, oder lieber nur nüchtern begrenzen?

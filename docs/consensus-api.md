# Consensus API v1

Der vollständige maschinenlesbare Vertrag wird von FastAPI unter
`/openapi.json` ausgeliefert. Die v1-Routen verwenden das OpenAPI-
Security-Scheme `ConsensusApiKey` (`X-API-Key`).

API-v1-Antworten werden mit `Cache-Control: private, no-store` ausgeliefert.
IP- und API-Key-bezogene Rate-Limits schützen Authentifizierung, Polling und
Worker-Kapazität; ein `429` bzw. `503` soll mit Backoff erneut versucht werden.

## Schlüssel ausgeben

Im Admin-Dashboard unter `/admin#api` können Schlüssel für bestehende Firebase-
UIDs ausgegeben, gefiltert und widerrufen werden. Nur ein Firebase-Admin kann
einen Schlüssel ausgeben; der zugrunde liegende HTTP-Aufruf lautet:

```http
POST /api/admin/api-keys
Authorization: Bearer <firebase-id-token>
Content-Type: application/json

{"uid":"firebase-uid","label":"production"}
```

Die Antwort enthält `api_key` genau einmal. Firestore speichert nur den
SHA-256-Hash als Dokument-ID in `api_consensus_keys`. Admins können Schlüssel
mit `GET /api/admin/api-keys?uid=…` auflisten und mit
`DELETE /api/admin/api-keys/{key_id}` widerrufen.
Schlüssel werden nur für aktive, E-Mail-verifizierte Firebase-Nutzer
ausgegeben. Gelöschte, deaktivierte oder lokal zur Löschung gesperrte Accounts
können keinen API-Schlüssel mehr verwenden.

Jeder Schlüssel trägt explizite Scopes:

- `consensus:run`: Runs starten, lesen und löschen.
- `share:write`: eigene erfolgreiche Runs publizieren sowie eigene Shares
  auflisten, lesen und widerrufen.
- `share:index`: eigene geeignete Shares direkt indexierbar bzw. wieder auf
  `noindex` setzen. Dieser Scope kann ausschließlich für eine Admin-UID
  ausgegeben werden und der Endpoint prüft die Admin-Rolle erneut.

Neue Schlüssel erhalten standardmäßig `consensus:run` und `share:write`.
Legacy-Schlüssel ohne gespeichertes Scope-Feld erhalten dieselben sicheren
Defaults, aber niemals rückwirkend `share:index`.
Für den Scheduled Publisher muss im Admin-Dashboard „Direct indexing“ aktiviert
werden; äquivalent kann die Ausgabe mit
`{"uid":"<admin-uid>","label":"scheduled-publisher","scopes":["consensus:run","share:write","share:index"]}`
erfolgen.

## Run starten

```http
POST /api/v1/consensus/runs
X-API-Key: cns_live_…
Idempotency-Key: 019f78b5-unique-per-logical-run
Content-Type: application/json

{"question":"Welche Evidenz spricht für und gegen diese These?","deep_think":false}
```

Antwort: HTTP `202`, `Location: /api/v1/consensus/runs/{run_id}` und ein
Run-Objekt. Der Request akzeptiert nur `question` und optional `deep_think`;
Modelle, Modellanzahl, Kosten und Limits werden ausschließlich serverseitig
bestimmt. Derselbe Idempotency-Key mit identischem Request liefert denselben
Run. Mit anderem Request folgt HTTP `409`.

Reguläre Consensus-API-v1-Runs verwenden die feste serverseitige
Sechs-Provider-Auswahl OpenAI, Mistral, Anthropic, Gemini, DeepSeek und Grok.
DeepSeek ist für API-Kunden verpflichtend und verarbeitet den Prompt in China;
es gibt keinen allgemeinen per-Request Opt-out. Die einzige Ausnahme ist der
interne, Admin-only Scheduled Publisher. Sein Skript setzt den typisierten
Header `X-Consensus-Publisher: true`; der Server prüft erneut die Admin-Rolle
und entfernt DeepSeek aus Antwortmodellen, Consensus-Engine/Fallbacks und
Differences-Judges. Dieser Header ist kein Provider-Schalter für normale API-
Kunden.

## Status/Ergebnis lesen

```http
GET /api/v1/consensus/runs/{run_id}
X-API-Key: cns_live_…
```

Mögliche Statuswerte sind `accepted`, `reserved`, `running`, `succeeded` und
`failed`. Nur `succeeded` enthält `result`; nur `failed` enthält `error`.
Ein Schlüssel kann ausschließlich Runs seiner zugeordneten UID lesen.

### Quellenprüfung nachladen

Die Quellenprüfung läuft als dauerhafter Hintergrundauftrag. Ein Run kann
bereits `succeeded` sein, während seine Quellen noch `queued` oder `running`
sind. `result.source_verification` enthält den beim Run-Abschluss gespeicherten
Stand mit `job_id`, `answer_version` und `status_url`, sofern ein Auftrag
angenommen wurde. Das normale Run-GET aktualisiert diesen Snapshot nicht;
den aktuellen Prüfstand liefert der zusätzliche Endpoint:

```http
GET /api/v1/consensus/runs/{run_id}/source-check
X-API-Key: cns_live_…
```

Er ist an den Run und dessen UID gebunden; eine fremde Job-ID gewährt keinen
Zugriff. Ohne gespeicherten Quellenauftrag liefert er `404`. Die v1-Anforderung
besitzt weiterhin keinen per-Request-Schalter für diese Prüfung.

Die Antwort enthält `source_verification` und `next_cursor`. Der Snapshot
enthält den Gesamtfortschritt und die `revision`, seine `findings`, `documents`
und `sources` dagegen nur die aktuelle Paketseite. Eine Seite umfasst höchstens
vier Pakete. Alle im Consensus zitierten Satz-/Quellen-Paare werden geplant;
Paketgrenzen kürzen weder die Quellenliste noch die Anzahl geplanter Prüfungen.
Unzitierte Modellquellen und S-Tags in Code-Beispielen gehören nicht dazu.

Zum vollständigen Lesen:

1. Die erste Seite ohne Cursor laden und deren `source_verification.revision`
   merken.
2. Solange `next_cursor` nicht `null` ist, diesen Wert als `cursor` und die
   gemerkte Revision als `revision` mitsenden. Befunde zusammenführen und
   Quellen/Dokumente anhand ihrer ID deduplizieren.
3. Bei `409` alle bisher gelesenen Seiten dieses Durchlaufs verwerfen und
   wieder bei der ersten Seite beginnen: Zwischenzeitlich wurde ein Paket
   abgeschlossen oder der Jobstatus geändert.
4. Für spätere Aktualisierungen auf der ersten Seite
   `after_revision=<zuletzt vollständig gelesene Revision>` verwenden. Bei
   unverändertem Stand kommt `unchanged: true` mit einem kompakten Header und
   `next_cursor: null`; die bereits gelesenen Befunde bleiben beim Client.

Beispiel für eine Folgeseite:

```http
GET /api/v1/consensus/runs/{run_id}/source-check?cursor=4&revision=7
X-API-Key: cns_live_…
```

Jobstatus `complete` bedeutet abgeschlossene Verarbeitung, keine pauschale
Bestätigung der Quellen. V3 trennt `support: supported|partial|contradicted|unknown`
von Thema und zeitlicher Eignung; technisch nicht prüfbare Paare bleiben explizit
`unavailable`. Dokumentabruf und Judge-Eingaben sind begrenzt; beispielsweise
werden PDFs nicht unterstützt. Vollständiger Ergebnis- und Ausführungsvertrag:
[source-verification.md](source-verification.md).

Run- und Share-Inhalte behalten ihre Antwortversion; der zugehörige Quellenjob
kann seinen Bearbeitungsstand weiterentwickeln. Eine Share-Publikation bindet
den Auftrag an die veröffentlichte Ressource, sodass die Quellenprüfung auch
nach Ablauf des ursprünglichen API-Runs verfügbar bleiben kann.

## Aufbewahrung und vorzeitige Löschung

Jeder Run und sein Idempotenz-Mapping erhalten bei Annahme ein `expires_at` und
werden spätestens 30 Tage danach gelöscht. Zusätzlich zur Firestore-TTL-
Eignung räumt ein periodischer serverseitiger Fallback abgelaufene Datensätze
auf. Die Antwort enthält `expires_at`.

Ein bereits terminaler Run (`succeeded` oder `failed`) kann früher gelöscht
werden:

```http
DELETE /api/v1/consensus/runs/{run_id}
X-API-Key: cns_live_…
```

Erfolg liefert HTTP `204`. Noch laufende bzw. reservierte Runs liefern `409`,
damit Usage- und Provider-Lifecycle nicht durch eine Lösch-Race entkoppelt
werden. Nach der Löschung kann derselbe Idempotency-Key wieder für einen neuen
logischen Run verwendet werden.

## Erfolgreichen Run publizieren

```http
POST /api/v1/consensus/runs/{run_id}/share
X-API-Key: cns_live_…
```

Der Run muss `succeeded` sein und derselben UID wie der Schlüssel gehören.
Der Endpoint erzeugt direkt einen unveränderlichen, öffentlichen Share-Snapshot
und liefert `share_id`, kanonische absolute `url`, `index_eligible`,
`indexing_status`, `robots` und `in_sitemap`. Wiederholungen für denselben Run
liefern denselben Link (`200` statt initial `201`) und verbrauchen keine weitere
Share-Quote. API-Publikationen verwenden nicht das kurzlebige Browser-
`pending_results`-Zwischenformat; sie bleiben dadurch während der Run-Retention
publizierbar.

Status und Lifecycle:

```http
GET    /api/v1/shares?limit=20
GET    /api/v1/shares/{share_id}
DELETE /api/v1/shares/{share_id}
```

`DELETE` widerruft die Seite wie der bestehende Browser-Flow, setzt sie sofort
auf `noindex` und liefert `204`.

## Seite indexierbar schalten

```http
PUT /api/v1/shares/{share_id}/indexing
X-API-Key: cns_live_…
Content-Type: application/json

{"indexed":true}
```

Hierfür sind Scope `share:index` **und** eine aktuell aktive Admin-Rolle nötig.
Automatische Freigabe ist nur möglich, wenn der bestehende Share-Quality-Filter
erfüllt ist. Existiert bereits eine indexierte Seite mit demselben normalisierten
Frage-Hash, antwortet die API mit `409 duplicate` samt Canonical-Ziel. Nach
Erfolg liefert die Seite `index, follow` und ist in `sitemap-shares.xml` enthalten.
Das macht die URL indexierbar; die tatsächliche Aufnahme in einen externen
Suchindex bleibt Sache der jeweiligen Suchmaschine/Search Console.

## Geplanter Publisher via GitHub Actions

`scripts/publish_consensus.py` bildet den kompletten Ablauf ab:

1. Admin-Konfiguration über `GET /api/v1/publisher/config` laden und bei
   `enabled=false` ohne LLM-Call erfolgreich beenden,
2. letzte eigene Share-Fragen laden,
3. optional per OpenRouter Chat Completions + Web Search eine neue, nicht
   redundante Frage wählen,
4. die Frage als kurze, einzelne Google-Suchintention prüfen (6–16 Wörter,
   höchstens 110 Zeichen, kein „As of …“, keine verschachtelte Trade-off-Frage)
   und bei Bedarf bis zu zweimal neu generieren,
5. Consensus-Run im Admin-only Publisher-Modus ohne DeepSeek starten, pollen
   und publizieren,
6. per `POST /api/v1/shares/{share_id}/watch` idempotent einen wöchentlichen
   Watch anlegen; dieser ist serverseitig dauerhaft auf die in
   `app_config/models.watch_models.free` konfigurierten Free Watch Provider
   gepinnt, wobei DeepSeek selbst dann explizit ausgeschlossen bleibt,
7. den geeigneten Share abhängig von der Admin-Konfiguration direkt
   indexierbar schalten,
8. bei konfiguriertem `TELEGRAM_BOT_TOKEN` und `TELEGRAM_CHAT_ID` die fertige
   Frage samt Share-URL per Telegram senden. Ein fehlgeschlagener
   Benachrichtigungsversand wird als Warnung geloggt und macht die bereits
   erfolgreiche Veröffentlichung nicht nachträglich rot.

Für Telegram muss der Empfänger den Bot zuerst mit `/start` aktivieren. Danach
werden Bot-Token und numerische Ziel-Chat-ID im Repository unter
**Settings → Secrets and variables → Actions** als `TELEGRAM_BOT_TOKEN` und
`TELEGRAM_CHAT_ID` angelegt. Der Bot-Token gehört nie in Workflow-YAML, Logs
oder Quellcode.

Die Admin-Steuerung liegt unter `/admin#api` und wird in Firestore als
`app_config/scheduled_consensus_publisher` gespeichert. Änderbar sind:

- Publisher an/aus,
- Topic Brief,
- automatische Indexfreigabe,
- Weekly-Watch an/aus sowie Wochentag, lokale Uhrzeit und IANA-Zeitzone.

Intervall, Provider-Tier und DeepSeek-Ausschluss des automatisch erzeugten
Watches sind bewusst nicht editierbar: `weekly`, `free`, `exclude deepseek`.
Die zugehörigen API-Routen sind Admin-
only und benötigen einen Schlüssel mit `share:write`; die Indexfreigabe
benötigt zusätzlich weiterhin `share:index`. Diese internen Publisher-Watches
zählen nicht gegen das persönliche aktive Watch-Limit der Admin-UID, bleiben
aber Teil des globalen täglichen Watch-Run-Budgets.

Der Workflow `.github/workflows/publish-consensus.yml` läuft standardmäßig
montags, mittwochs und freitags um 07:15 UTC und kann manuell mit einer festen
Frage gestartet werden. Bei der automatischen Themenwahl verlangen die
`Search-opportunity requirements` ein konkretes AI-Modell- oder Produktereignis
aus den letzten 24 Stunden (höchstens 48) als Auslöser — Release, Rückzug,
Preis- oder Limitänderung, Benchmark- oder Capability-Behauptung — zusammen mit
einem belegten Nachfragesignal (laufende Diskussion auf Hacker News, X oder
Reddit, oder Berichterstattung mehrerer Medien am selben Tag).

Die Frage selbst muss das Ereignis überleben: ob eine Behauptung standhält oder
was sich praktisch ändert, nicht ob etwas echt ist oder wann es erscheint —
Letzteres ist binnen einer Woche beantwortet und die Seite stirbt mit der
Antwort. Ob am Ende veröffentlicht wird, entscheidet der Judge: Läufe über
`CONSENSUS_MAX_AGREEMENT_SCORE` (Default 80) oder unter
`CONSENSUS_MIN_CONTRADICTIONS` (Default 1) werden verworfen.
Im GitHub-Repository werden folgende Actions-Secrets benötigt:

- `CONSENSUS_API_KEY`: Key einer Admin-UID mit allen drei Scopes.
- `OPENROUTER_API_KEY`: für die automatische Themenwahl über OpenRouter; bei
  manueller Frage wird dieser zusätzliche Themenwahl-Call nicht ausgeführt.

Optionale Repository-Variablen: `CONSENSUS_API_BASE_URL` und
`OPENAI_TOPIC_MODEL` (Default `gpt-5.6-luna`). Topic Brief und Index-Schalter
kommen im normalen Actions-Lauf aus Firestore statt aus GitHub-Variablen.
Der Workflow verwendet eine Run-stabile Idempotency-Key-ID; ein Retry kann
deshalb keinen zweiten Consensus-Run für denselben Workflow-Lauf starten.

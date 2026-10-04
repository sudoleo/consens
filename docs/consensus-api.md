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
Für direkte Indexfreigabe per API muss bei der Ausgabe im Admin-Dashboard
„Direct indexing“ aktiviert werden; äquivalent kann die Ausgabe mit
`{"uid":"<admin-uid>","label":"admin-indexing","scopes":["consensus:run","share:write","share:index"]}`
erfolgen.

## Run starten

```http
POST /api/v1/consensus/runs
X-API-Key: cns_live_…
Idempotency-Key: 019f78b5-unique-per-logical-run
Content-Type: application/json

{"question":"Welche Evidenz spricht für und gegen diese These?","reasoning":false}
```

Antwort: HTTP `202`, `Location: /api/v1/consensus/runs/{run_id}` und ein
Run-Objekt. Der Request akzeptiert nur `question` und optional `reasoning`;
Modelle, Modellanzahl, Kosten und Limits werden ausschließlich serverseitig
bestimmt. `reasoning: true` lässt dieselben serverseitig gewählten Modelle
länger nachdenken (mehr Tokens, langsamer, gegen die größere Reasoning-Schätzung
des Tokenkontos admittiert); es steht jeder Kontostufe offen und ändert weder
Antwortmodelle noch Consensus-Engine. `deep_think` ist ein veralteter Alias
desselben Schalters (Deep Think gibt es seit 2026-10-02 nicht mehr): ist eines
der beiden Felder `true`, ist Reasoning an. Das Run-Objekt trägt `reasoning`
und – aus Kompatibilität – `deep_think` mit demselben Wert.

Derselbe Idempotency-Key mit identischem Request liefert denselben Run
(`reasoning: true` und `deep_think: true` gelten dabei als identisch). Mit anderem Request folgt HTTP `409`; wurde der Run dieses Keys bereits
gelöscht, folgt HTTP `410` (`run_deleted`, siehe unten).

Reguläre Consensus-API-v1-Runs verwenden die feste serverseitige
Sechs-Provider-Auswahl OpenAI, Mistral, Anthropic, Gemini, DeepSeek und Grok.
DeepSeek ist für API-Kunden verpflichtend und verarbeitet den Prompt in China;
es gibt keinen per-Request Opt-out. Den früheren Publisher-Header
`X-Consensus-Publisher` wertet der Server seit 2026-10-04 nicht mehr aus.

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
werden. Gelöscht werden Frage, Modellplan, Ergebnis und Fehlertext; bis zum
ursprünglichen `expires_at` bleibt nur ein inhaltsfreier Tombstone mit dem
gehashten Idempotency-Key. Derselbe Idempotency-Key startet deshalb keinen
neuen Run: Ein erneuter `POST` mit diesem Key liefert stabil HTTP `410` mit
`{"error":{"code":"run_deleted",…}}`, `GET` und ein erneutes `DELETE` liefern
`404`. Für eine neue Berechnung einen neuen Idempotency-Key verwenden; sie
belastet das Tageskontingent als eigener Run.

Ein Run, der seine Reservierung nicht mehr einlösen kann (etwa nach einem
Serverabsturz direkt nach der Annahme), endet ohne Providerarbeit als `failed`
mit `error.code = "reservation_expired"`; ein noch reservierter Slot wird
freigegeben. Bereits belastete Runs dürfen nach dem UTC-Tageswechsel zu Ende
laufen, ohne ein zweites Mal gezählt zu werden.

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

## Geplanter Publisher (entfernt)

Der Scheduled Publisher (`scripts/publish_consensus.py`, GitHub-Workflow
`publish-consensus.yml`, `GET /api/v1/publisher/config`,
`POST /api/v1/shares/{share_id}/watch`) ist seit 2026-10-04 entfernt: 16
automatisch publizierte Seiten brachten in ~11 Wochen 2 Klicks. Bestehende
Publisher-Shares und ihre Weekly-Watches bleiben als Daten erhalten; die Watches
lassen sich unter `/admin#api` („Former Publisher pages“) pausieren. Die
wöchentliche Search-Console-Auswertung übernimmt der SEO-Puls
(`docs/codebase-map.md`, §4 „SEO-Puls“).

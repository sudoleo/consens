# consens.io — Codebase Map

Google als Quelle (03.10.2026): Google ist in Consens eine **Quelle von Belegen,
keine Hand**. Agent-Chats lesen Gmail und Kalender pro Nachricht und nehmen Dateien
aus Google Drive als normale Anhänge; zurückgeschrieben wird standardmäßig nichts.
- `google_connections.writes_enabled()` (`GOOGLE_WRITES_ENABLED=1`, Default aus)
  schaltet den ganzen Schreibpfad: ohne ihn registrieren `CalendarTools`/`GmailTools`
  nur `calendar_read` bzw. `gmail_read`/`import_gmail_attachment`, `start()` lehnt
  `calendar_write`/`gmail_send` ab, `public_connection` blendet gespeicherte
  Schreib-Grants aus, `AgentActions.prepare`/`confirm` werfen 403 (vor jedem Claim),
  der Agent-Prompt sagt „read-only, Text in die Antwort schreiben“. Ältere Vorschläge
  lassen sich nur noch verwerfen (`reject`); die Karte erklärt das.
- `restricted_model()` gilt für jeden Modellaufruf eines Chats mit `google_data`
  (Root, Vergleich, Judges): Provider-Routing behält seine Felder und erzwingt
  `zdr: true` + `data_collection: "deny"`; kein Endpunkt → der Aufruf scheitert bei
  OpenRouter wie jedes ausgefallene Modell. `GOOGLE_ALLOWED_MODEL_IDS`/`_PROVIDERS`
  sind nur noch optionale Verengung (vorher Pflicht, sonst alles gesperrt). Live-Probe
  03.10.2026: 48/52 Katalogmodelle aller neun Familien antworten unter der Regel; die
  vier Ausfälle haben auch ohne `deny` keinen ZDR-Endpunkt bzw. fehlende 18+-Bestätigung.
- Drive: `drive_picker()` liefert die öffentliche Picker-Konfiguration
  (`GOOGLE_CLIENT_ID`, `GOOGLE_PICKER_API_KEY`, `GOOGLE_PROJECT_NUMBER`) oder `None`;
  kein Server-Secret, keine gespeicherte Verbindung. `GET /agent/google/connections`
  meldet zusätzlich `writes` und `drive`. `agent-drive.js` (Bundle nach
  `agent-google.js`) zeigt `#attachDriveOption` im (+)-Menü nur im Agent-Modus bei
  konfiguriertem Picker, holt per Google Identity Services ein kurzlebiges
  `drive.file`-Token (nur im Seitenspeicher), öffnet Googles Picker (`setAppId` =
  Projektnummer) und lädt die Datei im Browser (Docs → DOCX, Sheets → CSV der ersten
  Tabelle, Slides → PDF, sonst `alt=media`). `App.attachments.addRemote` hält dafür
  einen Lade-Chip (zählt als Import, Send wartet) und schickt die Bytes durch dieselbe
  Prüfung wie lokale Dateien; der Anhang trägt `origin: {source:'google_drive', file_id}`.
  Der Upload sendet `drive_file_id` → Datei-Meta `kind: "drive_file"` + `origin`;
  `/agent` setzt `google_data`, sobald ein `file_id` ein Drive-File ist. Verlässt der
  Entwurf den Agent-Modus, entfernt `agent-google.js` Drive-Anhänge mit Hinweis.
- Zustimmung **einmal pro Chat**: `/agent` speichert beim ersten zugestimmten Lauf
  `google_consent` am Chat; `final` und `GET .../actions` melden `google_consent`.
  Der Browser schickt die Zustimmung danach bei jeder Nachricht dieses Chats mit
  (`chatConsented`), der Server verlangt sie weiterhin pro Request. Die Checkbox
  „Share with the models in this chat“ erscheint, solange der Chat sie nicht hat
  (Gmail/Kalender aktiv, Drive-Datei im Entwurf oder Altchat mit `google_data`).
- UI-Sprache: (+)-Menü „Add from Google Drive“ und „Gmail & Calendar · Read as
  sources“ direkt unter „Add files“ (verbunden: „Connected · konto“ mit grünem
  Punkt); Dialog „Gmail & Calendar“; Info-Chip „Private chat · Google data“.
  Dokumentation: `docs/google-integrations-setup.md`.
- Sichtbarkeit: `user_allowed(uid)` prüft `GOOGLE_TEST_USERS` (bestätigte
  consens-E-Mails, `*` = alle, leer = niemand; E-Mail per Firebase Admin, 5 min
  gecacht). Andere Konten bekommen von `GET /agent/google/connections`
  `configured:false, drive:null` und sehen nichts; connect/finish/calendars/
  confirm/renew, Drive-Uploads und `google_selection` in `/agent` antworten 403.
- Lokaler Test: `configuration()` akzeptiert eine `http://localhost`-Rückleitung,
  solange weder `RENDER_SERVICE_NAME` noch `ENVIRONMENT=production` gesetzt ist.

Gmail in Agent Mode (27.09.2026): `agent_gmail.py` adds root-only `gmail_read`,
`import_gmail_attachment` and `prepare_gmail_draft` to the same server registry.
`GoogleSelection.gmail` is explicit per message; older Calendar-only frozen
settings normalize without changing replay identity. Shared Google connections
request `gmail.readonly` and `gmail.send` separately. Reads target queries/IDs,
paginate complete threads and body excerpts, strip active HTML, and keep bounded
account/header/message references under chat `google_evidence` (30 days). Selected
MIME parts use the private file pipeline with an origin tuple; generated document
versions can be attached by owned file ID. No bulk mailbox sync or raw body cache.

Local drafts are immutable `actions` with `kind=gmail_send`; revisions supersede
previous approval, preserve original-thread metadata and bind attachment hashes.
The exact-preview confirmation endpoint constructs MIME and sends once; unknown
results can only be searched by deterministic Message-ID in Sent. Per-user
`google_write_intents` retain a minimal 30-day hash/status fence across chat deletion,
preventing equivalent unresolved writes in other chats. Hourly expiry and account
deletion remove these records; proposal bodies stay chat-owned. No model-visible
send/confirm tool exists. Headers are built at prepare time; local build errors
after confirmation are `failed`, not `unknown`. Previews flag recipients neither
named by the user nor in the replied thread (`recipient_warnings`). Chat deletion
removes `actions` and `google_evidence`. UI cards restore exact To/Cc/Bcc, reply reference, body,
attachments and checked status; restored/revised cards always require fresh review.

The existing Google routing/consent rules apply to all Gmail-derived data, including
comparisons, synthesis and judges. Local drafts need no compose/modify scope; public
readonly use requires restricted-scope verification/security assessment as detailed
in `docs/google-integrations-setup.md`. `tests/test_agent_gmail.py` includes the real
files → two-model comparison → document → draft → synthesis/review integration.

Google/Calendar in Agent Mode (27.09.2026): `agent_google.py` exposes owner-bound
connection controls at `/agent/google/{connections,connect,finish}` and the isolated
popup callback; connect/finish/actions require Agent access, listing and disconnect
only the owner. `google_connections.py` owns PKCE/state/OIDC validation, owner-bound
encrypted token envelopes, refresh leases, revocation, daily API limits and the
allowlisted Google transport. Tokens never enter tools or model contexts. The
`google_selection` and model-sharing consent are frozen in `agent_settings` and
checked on replay. `agent_calendar.py` registers selected-calendar read/search,
instances/freebusy and preparation tools; workers get no direct connection tools.
Calendar excerpts and proposals enter the existing tool-free synthesis as explicit
untrusted evidence. A chat's `google_data` marker enforces the Google routing rule
(ZDR + no data collection, optional allowlists; see "Google als Quelle" above) for all
later steps, including comparison and judges; web search/source checks stop.

`agent_actions.py` persists exact proposals in chat `actions` subcollections. Only
the authenticated `/agent/chats/{chat}/actions/{id}/confirm` endpoint can claim an
external write; tools cannot confirm. Hash/revision binding, ETags, deterministic
event IDs and durable unknown outcomes prevent retry-driven duplicate operations.
`reject` and read-only `status` are separate endpoints. `renew` re-prepares a
stored proposal without a model call (expired approval, newly granted Gmail send
permission, or removing a flagged recipient; content may only shrink); the new
version supersedes the old one and needs its own review. `GET .../actions` lists
actions and Gmail evidence by `created_at` and returns the chat's `google_data`
marker, which the `/agent` `final` event also carries.
`agent-google.js` (+ `agent-google.css`) supplies the Google data dialog (opened
only from the (+) menu row `#agentGoogleMenuOption`, which appears once the
installation reports Gmail/Calendar configured — no toolbar entry since
2026-10-03; connections load when (+) opens), removable composer chips
`#agentGoogleChips` with the per-chat consent `#googleDataConsent`, and the
action cards in `#agentGoogleActions` (after `#agentAnswer`): verb title, status
badge, per-address acknowledgement of flagged recipients, calendar diff with
changed rows, "Earlier versions" per `replaces` chain, expiry rechecked every 30 s.
Contract on `App.agentGoogle`: `blocker()` → `{message, action:'google-consent'|
'google-open', label}|null` (incomplete or unconsented selection, or a chat whose
`google_data` is set; `selection()` throws instead of dropping a visible choice),
`consent(bool?)`, `resetConsent()`, `open()`, `pendingCount(chatId)`,
`evidenceFor(messageId)` → `{subject, from}|null`, `refreshActions(chatId, force)`
(one request per 300 ms per chat; the module also projects the current chat from
`refreshControls()` and reloads after a finished Agent run), `noteGoogleData(chatId,
googleData, consented)`, `config()` → `{configured, writes, drive}`, `knownDrive()`,
`agentActive()`. It listens to `consensio:attachments-change` (attachments.js) so a
Drive file in the draft asks for consent.
It dispatches `consensio:agent-google-change` and `consensio:agent-actions-change`
(`{chatId, pending, googleData}`).
Hourly retention purges expired OAuth states/actions (skipped without Google
configuration); chat deletion removes `actions`; account deletion revokes stored
grants at Google (`GoogleConnections.revoke_all`) and removes credentials and
pending grants. `markdown-stream.js` renders model answers without auto-loading
remote resources (no remote images/media/style), closing markup exfiltration. See `docs/google-integrations-setup.md` for required
secrets, indexes, approved model routing, Google verification and live-test limits.

Agent documents (27.09.2026): `agent_documents.py` registers `create_document`,
`read_document`, and `revise_document` on the root's existing bounded ToolRegistry.
The tools run before the immutable synthesis/review handoff. The synthesis receives
saved output descriptors explicitly, and `resources` SSE refreshes the
`agent-workspace.js` document cards (one per `document_id`, after the answer). No worker receives document-write tools. Files reuse
the private owner/chat-bound store and authenticated download route from PR 1.
`agent_document_render.py` renders strict structured content offline in a bounded
subprocess using python-docx and ReportLab, then reopens both formats. Versions
live at `users/{uid}/chats/{chat}/documents/{id}/versions/{number}`; the parent
manifest serializes revisions and publication requires both saved, verified files.
Each immutable version binds content hash, parent, turn, source-file hashes and
comparison-answer hashes. The answer judges do not independently review these
documents. The retention task removes expired version content after 30 days and
the manifest with its last version; `ChatStore._delete_chat_tree` removes
`documents/*/versions/*` and the manifests, `AgentFiles.cleanup_chat` their files.
The render subprocess imports only `agent_document_spec.py` (no Firebase).
See `docs/agent-integrations.md` for limits, font configuration and validation.

Öffentliche Seiten (seit 03.10.2026): `/model-pulse?period=7d|30d|90d|all&mode=all|consensus|agent&with=<provider>&sort=rate|lift|runs`
zeigt pro Familie die **Best-answer-Rate** (Picks ÷ Läufe, in denen die
Familie war) statt absoluter Picks, dazu den Fair Share (Σ 1/n der Läufe,
Tick am Balken), `lift` (Picks ÷ Fair Share), ein 95-%-Wilson-Band und —
mit `with=` — die Head-to-Head-Bilanz gegen eine Rivalen-Familie. Unter
`MIN_RUNS` (10) Läufen wird eine Familie gelistet, aber nicht gerankt. Rechnung
und Cache: `app/services/model_pulse.py` (`build_view` rein; `PulseLedger`
lädt einmal alle `model_votes` mit `pulse_version == 1`, liest danach höchstens
1×/Minute nur Votes ab dem letzten Zeitstempel − 5 min nach und lädt alle 6 h
voll neu, damit Kontolöschungen herausfallen; gehalten werden nur Zeit, Quelle,
Teilnehmer, Pick — kein Owner). Server rendert die erste Ansicht (GET-Formular
ohne JS), `model-pulse.js` holt Filterwechsel über `GET /api/model-pulse` und
schreibt sie in die URL; Lesefehler → 503 + Retry-After statt Nullständen.
Die Landing zeigt im Benchmark-Abschnitt (seit 03.10.2026 vor `#watch`) einen
Live-Streifen aus derselben Ansicht (`landing_pulse_preview`: Top 5, versteckt
unter 3 gerankten Familien); die frühere Pulse-Statuszeile im Hero ist entfallen.
`/api/model-leaderboard` (absolute Picks, `period=all|since-2026-08-31`) bleibt
als Legacy-API bestehen (Lifetime-Read
ohne SDK-Retries, mit 5-s-Timeout). Öffentliche Legacy-Citations werden in
`public_markdown.py` beim Rendern nummeriert; bekannte kurze Quellenlinks werden
auf bestehende Quellenanker abgebildet, beschreibende Links und Aussagen bleiben
erhalten. `share_snapshots.build_citation` verlinkt die Quellenliste der gewählten
Antwortversion statt alle Redirect-URLs in den kopierbaren Beleg zu schreiben.
Share-Meta-Descriptions lassen bekannte Citation-Labels weg; die öffentliche
Quellenliste wird erst per JS eingeklappt und ist ohne JS vollständig sichtbar.
Historische Snapshots und Original-Quellenziele werden nicht migriert.

Kompakte Architektur-Übersicht für Coding-Agents. Ziel: in wenigen Minuten
verstehen, wie das Projekt gebaut ist, wo Logik liegt und was bei Änderungen zu
beachten ist. Bewusst kurz gehalten — keine vollständige Datei-/Funktionsliste.

> Nur verifizierte Fakten. Wenn dieses Dokument von der Realität abweicht, gilt
> der Code. Pflege-Regeln siehe **Bei Änderungen aktualisieren** am Ende.

---

## 1. Projektüberblick & Stack

consens.io vergleicht Antworten mehrerer LLM-Provider nebeneinander und
synthetisiert daraus einen **Consensus** plus eine strukturierte
**Differences**-Analyse. Optional: Agent Mode (Auto-Consensus), separater
**Agent · Beta** (Chatmodell mit dynamischen Vergleichs-/Judge-Tools, Admin/Pro), Datei-Anhänge
(ab Plus), öffentliche Share-Seiten. Es gibt drei Kontostufen: **Free**,
**Plus** und **Pro** (siehe §4 „Auth / Usage / Tier").

- **Backend**: Python, FastAPI (`fastapi==0.128.8`), via `uvicorn` ausgeliefert.
  SSE-Streaming über `StreamingResponse`. Rate-Limiting via `slowapi`.
- **LLM-Modelle**: neun Registry-Familien (OpenAI, Mistral, Anthropic, Gemini,
  DeepSeek, Grok, Kimi, GLM, Meta/Muse), alle über einen OpenRouter-Chat-
  Completions-Transport mit ZDR. Ein Lauf wählt davon höchstens sechs.
  Provider-Label-Konvention: Claude = `Anthropic`, Muse = `Meta`.
- **Auth & Daten**: Firebase Auth (ID-Token) + Firestore (`firebase-admin`).
- **Frontend**: kein Framework. Jinja2-Templates + Vanilla-JS-Module unter
  `static/js/`, überwiegend als klassische `<script defer>`-Tags. `window.App`
  ist Bus und State-Owner; ausgewählte `window.*`-Getter/-Funktionen bleiben als
  Kompatibilitätsvertrag (siehe §8).
- **Markdown/Mathematik**: `marked` + `DOMPurify` clientseitig und
  `markdown-it-py` + `nh3` für Share-Seiten; KaTeX setzt in beiden Ansichten
  LaTeX-Ausdrücke nach dem sanitisierten Markdown-Rendern.
- **Hosting**: Render. Der tägliche Render-Restart setzt weiterhin flüchtigen
  Prozess-State zurück; Retention/Cleanup läuft davon unabhängig periodisch
  im überwachten Background-Task (siehe §7).

---

## 2. Einstiegspunkte / Routing / Templates

**`main.py`** ist der App-Entry: lädt `.env`, fügt das vor dem
Framework-Parsing greifende `RequestBodyLimitMiddleware`,
`CustomSecurityMiddleware` (CSP etc.), `CorrelationMiddleware` + slowapi-Limiter
hinzu, mountet
`/static`, registriert globale Exception-Handler und inkludiert alle Router.
Äußerste Schicht ist `StaticDeliveryMiddleware` (`app/core/static_delivery.py`):
content-gehashte Bundles `static/dist/<gruppe>.<12 hex>.js|css` und
`asset_url()`-URLs mit `?v=<12 hex>` erhalten
`Cache-Control: public, max-age=31536000, immutable`, jede andere
`/static`-Antwort `no-cache` (ETag-Revalidierung), statische Textassets und
HTML ab 1 KiB gzip bei passendem `Accept-Encoding`. API-JSON und
`text/event-stream` laufen unverändert Frame für Frame durch (SSE wird nie
komprimiert oder gepuffert); `tests/test_static_delivery.py` sichert beides ab.
Jeder Request erhält eine PII-freie `req-*`-Correlation-ID (auch als
`X-Correlation-ID` in der Response); `GET /health/metrics` liefert nur
prozesslokale, aggregierte Provider-/Scheduler-Zähler und Laufzeiten ohne
Prompts, Antworten, E-Mails oder andere Nutzdaten.
Im `lifespan`-Startup ist nur `load_models_from_db()` readiness-kritisch; dessen
Firestore-Read deaktiviert SDK-Retries und besitzt ein echtes Fünf-Sekunden-
Budget. Schema-Backfill und Dokumentanlage sind davon getrennt und laufen erst
nach Readiness als überwachter Einmal-Task. Alle übrigen nicht abbrechbaren
Cleanup-/Recovery-Arbeiten starten ebenfalls erst nach Readiness. Ein separater
Einmal-Task verifiziert und ergänzt fehlende Publisher-
Lineage bei alten Free-Publisher-Watches; ein weiterer best-effort Einmal-Task
räumt abgelaufene Telegram-Link-/Delivery-Metadaten auf und registriert bei
vollständiger Telegram-Konfiguration den User-Bot-Webhook.
`app/core/background_tasks.py` überwacht alle Lifespan-Tasks, startet abgestürzte
Loops mit exponentiellem Backoff neu, alarmiert nach drei aufeinanderfolgenden
Fehlern und hält Start-/Fehler-/letzte Erfolgszeiten für
`GET /health/maintenance`. Cancellable Tasks übernehmen den 60-Sekunden-API-
Maintenance-, 5-Minuten-Account-Cleanup-, stündlichen Retention- und
30-Minuten-Consensus-Watch-Tick.
`_scheduler_task` in `main.py` startet jeden Lifespan-Task, der in die
(lokal geteilte) Produktions-Firestore schreibt, dort löscht oder Jobs claimt,
nur wo er hingehört, und meldet ihn sonst in `GET /health/maintenance` als
`disabled`: Consensus-Watch-, Topic-, SEO-Weekly-Review-Scheduler,
Consensus-API-Maintenance, Retention-Maintenance, die Source-Check-Worker,
beide Account-Cleanups (`consensus-api-account-cleanup`,
`full-account-deletion-cleanup`: löschen Daten echter Tombstone-Konten und
Firebase-Auth-User) sowie die Einmal-Tasks (`_run_once`, `restart=False`)
`model-configuration-backfill` (schriebe die Normalisierung des lokalen Codes
nach `app_config/models`, die der Live-Sync übernähme),
`publisher-watch-lineage-backfill` und `telegram-watch-startup-maintenance`
(löscht Metadaten und würde per `setWebhook` die Prod-Registrierung des Bots
überschreiben). Regel (`_background_writers_off_reason`): unter `MOCK_LLM=1`
läuft keiner davon; ohne Mock laufen sie seit 2026-10-03 nur in Produktion
(`RENDER_SERVICE_NAME` oder `ENVIRONMENT=prod/production`, `_is_production`)
oder lokal mit `LOCAL_BACKGROUND_JOBS=1`. Ein lokaler Server bezahlte sonst jede
Abfrage der Deployment-Loops doppelt (~10k Reads/Tag pro Dev-Server, plus
volle Collection-Scans bei jedem `--reload`) und konkurrierte um dieselben
Slots. Ausnahme `local=True`: die Source-Check-Worker arbeiten auf jedem
Nicht-Mock-Server ihre eigene lokale Queue ab (s. Quellenprüfung). Einzig der
lesende `model-configuration-sync` läuft immer; der Lifespan-Test erzwingt,
dass jeder neue Task bewusst einer der beiden Seiten zugeordnet wird. Es gibt
keinen lokalen Firestore-Emulator außerhalb des E2E-Profils.
Im expliziten Browser-Testprofil `E2E_TEST_MODE=1` überspringt der Lifespan
dagegen alle Startup-, Cleanup-, Recovery-, Backfill-, Webhook- und Scheduler-
Writer. `app/core/e2e_profile.py` erlaubt Firebase vor der Initialisierung nur
mit der festen Demo-Projekt-ID `demo-consensio-e2e` und einem lokalen
`FIRESTORE_EMULATOR_HOST`; Request-Persistenz läuft dann ausschließlich gegen
den Emulator. Produktive Credentials sind kein E2E-Fallback.

Router liegen unter `app/api/routers/` und werden in `main.py` eingebunden:

Handler mit synchroner Firebase-/Firestore-Arbeit sind normale `def`-Handler;
FastAPI führt ihr zusammenhängendes Auth-/Read-/Transaktionsbündel im Worker-
Threadpool aus. `async def` bleibt nur für echte Await-Pfade (Mail, explizites
`asyncio.to_thread`, Webhook) und darf nicht ohne Await eingeführt werden.

| Router | Zweck (Auswahl an Pfaden) |
|---|---|
| `agent.py` | `GET /agent/models` und `POST /agent`: Admin/Pro-geschützter Modellkatalog aus den vollständigen Firestore-Anbieterlisten samt Reihenfolge, aktuellen Provider-Metadaten und konfiguriertem Standard und begrenzter Modell-/Tool-Lauf im bestehenden Chat. Strikte Auswahl, owner-gebundene IDs, SSE mit bestätigten Fortschritten, Tool-Ergebnissen/Quellen und aggregierter Usage. Alle angebotenen Chatmodelle nutzen den gemeinsamen Websuch-Builder mit begrenzten Exa-Ergebnissen; kein eigener Suchdienst. Vorrang für gemeldete Provider-Gesamtkosten, idempotente Schrittbelege, modellgebundene 429-Wartefrist und Wiederaufnahme fertiger Antworten. Geprüfte Delegation mit eigenen Sitzungen, Mailboxen, Seitenleiste und atomarem gemeinsamen Budget; ergänzende `/agent/chats/{chat}/turns/{turn}/agents`-Detail-/Stop-Endpunkte. Kein `/prepare` oder Memory-Kompressor; dynamische Vergleichs-/Judge-Tools mit eigener Tokenquote (siehe Agent-Beta-Abschnitt). `recover_only` startet nie einen Modellaufruf. |
| `source_checks.py` | Dauerhafte Quellenprüfung: owner-gebundenes `GET /api/source-checks/{job_id}` mit `cursor`, `revision` und `after_revision`; `POST .../{job_id}/resume` nimmt den eigenen OpenRouter-Key nur in den Prozessspeicher auf. `GET /api/share/{share_id}/source-check?version=...` und `GET /api/topics/{slug}/source-check?version=...` prüfen pro Paketseite aktive Ressource, Sichtbarkeit, Run- und Antwortversion. Seiten liefern `source_verification` plus `next_cursor`, bei geändertem Stand 409. API-Key-Clients verwenden den rungebundenen Endpoint in `api_v1.py`: `GET /api/v1/consensus/runs/{run_id}/source-check`, auch als `result.source_verification.status_url` ausgegeben. |
| `pages.py` | HTML-Seiten + SEO: `/` (Landing, auch mit aktiver Session direkt erreichbar), `/model-pulse` (öffentliche Best-answer-Raten mit Filtern; API `GET /api/model-pulse`), `/app` (Haupt-App), `/app/watches` (gleiche App-Shell; watch.js öffnet anhand des Pfads das Watch-Dashboard), `/admin` (inkl. Topics-Tab), `/admin/topics` (308-Kompatibilitätsredirect auf `/admin#topics`), `/admin/benchmark` (Benchmark-Run-Visualisierung), `/about`, `/ai-model-comparison`, `/consensus-engine` (nutzerfreundliche Consensus-Engine-Erklärung), `/privacy` `/imprint` `/terms`, `robots.txt`, `sitemap*.xml`. Außerdem der öffentliche, familienaggregierte Best-answer-Zähler `GET /api/model-leaderboard` (60 s Browser-/CDN-Cache; `period=all|since-2026-08-31`; alle neun Familien einschließlich Nullständen, Kimi/GLM und Meta/Muse mit eigenem Verfügbarkeitsdatum aus `_LEADERBOARD_AVAILABLE_SINCE`). Beide Zeiträume nutzen zusätzlich einen serverseitigen 60-s-Cache mit serialisiertem Refresh pro Zeitraum/Prozess. Der gemeinsame Zeitraum zählt die datierten, deduplizierten `model_votes` ab 31.08.2026 über indexierte `count()`-Abfragen pro Familie; Modellkatalog und Counts werden im selben Read-only-Transaktionssnapshot gelesen. Solange der neue `model_votes`-Index aus `firestore.indexes.json` fehlt/aufbaut, greift nur für diesen Indexfehler der gecachte Legacy-Scan. Kontolöschungen entfernen weiterhin Votes aus dem Zeitraum, ohne Lifetime-Zähler zurückzusetzen; `/feedback`, `/vote`, `/check_keys` bleiben die weiteren internen Seiten-Routen (Key-Test nur für verifizierte Logins). Feedback ist persistent pro UID auf 30 Sekunden und 10/UTC-Tag begrenzt. Ein Best-answer-Vote muss an ein noch gültiges, owner-gebundenes `result_id` gebunden sein, zum serverseitigen Gewinner passen und kann pro Lauf genau einmal zählen. |
| `chat.py` | Kern-LLM-Flow: `/prepare`, die aus `cfg.PROVIDERS[*].ask_endpoint` erzeugten `/ask_*`-Routen (aktuell zusätzlich `/ask_kimi` und `/ask_glm`), `/consensus`, `/resolve`. `/prepare` und die `/ask_*`-Endpoints akzeptieren weiter das optionale Legacy-`context`-Feld für nicht migrierte Bookmark-Fortsetzungen. Additiv laden `/ask_*` das owner-gebundene Tripel `chat_id`/`turn_id`/`context_version_id`; Legacy- und Versionskontext zusammen werden abgewiesen. Alle `/ask_*`-Endpoints laufen über `handle_ask` + die deklarative Familien-Registry `ASK_PROVIDERS`; Transport und Credential sind für alle OpenRouter, `useOwnKeys` wählt optional `openrouter_key`. `/consensus` akzeptiert optional Chat-/Turn-IDs plus `turn_sources` und die exakt am Turn verknüpfte `context_version_id`, prüft alles owner-gebunden vor dem Judge und finalisiert nach Consensus, Differences und Share-`result_id` in Streaming- wie JSON-Pfad über `ChatStore`. Sendet der Browser die stabile `bookmarkId`, schreibt `/consensus` den autoritativen Bookmark-Snapshot vor seinem erfolgreichen Final-Event und liefert kompakte `bookmark_meta`; ein separater Browser-Request ist nur noch Fallback. Ein bereits completed Turn wird mit Consensus, Differences, Quellen und Modellantworten owner-geschützt wiedergegeben, ohne Engine-/Differences-/Share-/Statistik-/Completion- oder Usage-Write; ohne IDs bleibt der Legacy-Vertrag unverändert. |
| `chat_history.py` | Additive, owner-gebundene Chat-Persistenz: `POST/GET /chats`, `GET /chats/{chat_id}`, `DELETE /chats/{chat_id}` (dreistufige Kaskade über `ChatStore.delete_chat`; vor der Enumeration wird der Chat transaktional auf `deleting` gesetzt und zugleich ein dauerhafter `chat_deletion_jobs`-Auftrag angelegt, damit kein paralleler Turn als Subcollection-Waise nachrutschen kann und eine unterbrochene Kaskade vom Retention-Loop fortgesetzt wird; `deleting`-Chats sind in Liste, Detail, Turns und neuen Context-Versionen bereits unsichtbar bzw. gesperrt), `POST/GET /chats/{chat_id}/turns`, das vollständige `GET /chats/{chat_id}/turns/{turn_id}` sowie `POST /chats/{chat_id}/turns/{turn_id}/context` für eine idempotente autoritative Context-Version. Das UID-Budget `build_context` liegt ausschließlich auf diesem POST, nicht auf dem Turn-GET. Listen sind begrenzt und mit selbstenthaltenden, UID-/Ressourcen-gebundenen HMAC-Cursors paginiert (`updated_at` + Dokument-ID für Chats, `position` + Dokument-ID für Turns); Cursor-Dokumente werden nicht erneut als veränderliche Seitengrenze gelesen. Create-Chat serialisiert das Owner-Limit über `chat_state/quota`, Create-Turn ist über `client_request_id` idempotent. `ChatStore.complete_turn`/`fail_turn` lesen Chat, Turn und Account-Tombstone in derselben Transaktion und akzeptieren ausschließlich einen weiterhin `active` Chat; eine nach dem `deleting`-Marker eintreffende Completion kann deshalb keine Modellantwort-Waisen erzeugen. Completion bleibt per Payload-Fingerprint idempotent. Es gibt bewusst keinen öffentlichen Completion-/Fail-Write-Endpoint. Alle `/chats`-Antworten erhalten über die Security-Middleware `private, no-store`. Bei einer aktiven Fortsetzung erzeugt der Browser den pending Turn nach `/prepare` vor Context und Fan-out; Turn 1 entsteht erst bei der Consensus-Anforderung. Consensus-Turns werden serverseitig über `/consensus`, Agent-Turns über `/agent` finalisiert. |
| `client_errors.py` | Nimmt unter `POST /api/client-errors` ausschließlich same-origin, größenbegrenzte kritische Browsermeldungen an (5/min pro IP). Freitext, Stack, konkrete IDs/Slugs und Providerdetails werden verworfen; nur allowgelistete Typ-/Phasenkategorien, eine abstrahierte Route und bei echten Skript-/Stylesheet-Ladefehlern eine grobe Ressourcenklasse (`app_bundle`, `static_asset`, `jsdelivr_dependency`, `firebase_dependency`, `same_origin_resource`, `unknown_resource`) erreichen den nicht-blockierenden Telegram-Alert. Runtime-Fehler liefern zusätzlich Bundle-Koordinaten (Ort + bis zu fünf `[bundle, zeile, spalte]`-Frames), die über `static/dist/<bundle>.map` auf `static/js/…:zeile:spalte` aufgelöst werden, den Namen des laufenden App-Bundles und nur bei `TypeError`/`ReferenceError`/`RangeError`/`SyntaxError` die entschärfte Message (lange Literale → „…“, URLs/Mails/Secrets raus, max. 200 Zeichen). Der Endpoint liefert keine Konfigurationsdetails zurück. |
| `auth.py` | `/register`, `/confirm-registration` (setzt nach verifiziertem Login zusätzlich eine kurzlebige HttpOnly-Session für private servergerenderte Seiten), `DELETE /auth/session` (lokales Logout-Cleanup). `/register` gibt für Neuanlage, Bestand und Create-Race exakt `{"status":"check_inbox"}` zurück, nie UID/E-Mail/Custom-Token. Unbekannte Adressen erhalten ein serverseitig zufälliges, dem anonymen Aufrufer unbekanntes Übergangspasswort; neue und bestehende Adressen durchlaufen danach denselben Firebase-Mailbox-Setup-Pfad (`PASSWORD_RESET`-Mail mit `continueUrl = {PUBLIC_SITE_URL}/app?setup=1`, damit Firebases „Passwort gespeichert“-Seite zurück in den vorausgefüllten Login führt; lehnt Firebase die Continue-URL mit 400 ab, geht dieselbe Mail ohne sie raus). Der Browser versucht keinen Login mit den eingesendeten Legacy-Credentials. Nur ein tatsächlich neues Konto löst den PII-freien Telegram-Admin-Alert aus. `/confirm-registration` prüft Revocation live und erkennt damit auch gerade neu angelegte Google-Konten serverseitig. |
| `firebase_auth_proxy.py` | Same-Origin-Proxy für Firebases Sign-in-Helfer: `GET/HEAD/POST /__/auth/*` und `GET /__/firebase/init.json` werden transparent an `https://<FIREBASE_PROJECT_ID>.firebaseapp.com` (überschreibbar per `FIREBASE_AUTH_PROXY_UPSTREAM`) weitergereicht (Firebase „redirect best practices“, Proxy-Option). Weitergereicht werden nur Request-Zeile, Content-Negotiation-Header und der Handler-Body, nie Cookies/Authorization; zurück nur Inhalts-/Cache-Header, kein `Set-Cookie`. `CustomSecurityMiddleware` lässt auf diesen Pfaden die App-CSP weg und setzt `X-Frame-Options: SAMEORIGIN` (das `/__/auth/iframe` rahmt die App selbst). Wirksam erst, wenn `FIREBASE_AUTH_DOMAIN` den App-Host nennt (siehe §7). Ohne Projekt-ID 404, Upstream-Fehler neutral 502. |
| `users.py` | `/user_status`, `/usage`, `/usage/run/release`, `GET`/`PUT /api/my/memory` sowie `POST /api/my/memory/edit|undo` (User-Memory samt explizitem, revisioniertem Luna-Patch, siehe §3), `/delete_account`, `/track-interest`. `/delete_account` legt vor jeder Löschung einen persistenten, fail-closed Auftrag über `FirestoreAccountDeletion` an. Die idempotente Kaskade umfasst API-Zugang/Telegram, alle Nutzer-Subcollections, Chats, Waitlist/Feedback, Pending Results, Persistence-Guards/Votes, Watches/Briefs, Follow-Challenges/E-Mail-Follows, eigene Shares über deren bestehende Hard-Delete-Kaskade, Profil und Firebase Auth. Jeder Bereich wird separat quittiert und bei Fehlern vom fünfminütigen Maintenance-Loop erneut versucht; bis dahin lautet die Antwort ehrlich `202 cleanup_pending`, erst der vollständige Abschluss ergibt 200. Owner-gebundene Create/Update/Delete-Transaktionen lesen den Account-Tombstone als ersten Teil derselben Mutation; nur interne Cleanup-Kaskaden verwenden explizite Bypässe. Dadurch können bereits authentifizierte, verspätete Requests keinen zuvor quittierten Bereich neu befüllen. `/track-interest` ist der idempotente Pro-Beta-Zugangsrequest (ein Pending-Dokument pro UID, kein Billing); aktive Pro-Konten werden abgewiesen. **Seit 2026-07-25 ruft die App diesen Endpunkt nicht mehr auf** — es wird nichts mehr angeboten, das man anfragen könnte; der Endpunkt bleibt nur bestehen, damit vorhandene Waitlist-Dokumente nicht verwaisen. |
| `bookmarks.py` | `GET /bookmarks` liefert ausschließlich kompakte Metadaten, standardmäßig 30 Einträge und einen opaken Cursor; `GET /bookmarks/{id}` liefert owner-geschützt den Vollinhalt. Sidebar-Name: `title` ist die erste Frage (`query` die letzte); seit 2026-10-03 benennt `POST /bookmarks/{id}/title` die Unterhaltung einmalig ChatGPT-artig mit 2–6 Wörtern (`app/services/chat_titles.py`: ein strukturierter Call über `query_engine_json` mit dem Chat-Memory-Modell der ersten verfügbaren Familie, Gemini zuerst, auf Betreiberkosten; MOCK_LLM liefert `Topic: …`). Der Titel landet zuerst auf dem Chat-Dokument (Agent- und Follow-up-Saves kopieren dessen `title`), dann mit `title_source: "generated"` auf dem Bookmark; `persistence_guard.write_bookmark` verwirft in derselben Transaktion jedes spätere `title` ohne `title_source`, damit Modell-/Consensus-Saves desselben Laufs den Namen nicht zurücksetzen. Scheitert der Call, bleibt die Frage der Name (`status: "skipped"`, nie ein Fehler); fehlende Bookmarks werden nicht neu angelegt. Listenmetadaten tragen `title_source`. Chat-Bookmarks referenzieren additiv `chat_id`/letzte `turn_id`; `GET /bookmarks/{id}/conversation` paginiert dafür die vollständigen owner-gebundenen completed Turns aus `ChatStore`, statt den wachsenden Transcript in ein Bookmark-Dokument zu kopieren; der Normalpfad läuft über `ChatStore.list_turn_details` (Chat einmal pro Seite geprüft, Modellantworten je Turn mit **einer** Query) und benötigt damit `2 + N` SDK-Aufrufe pro Seite. Abgerechnet werden weiterhin Dokument-Reads: Chat + gelesene Turn-Dokumente (inklusive Pagination-Sentinel) + alle zurückgegebenen Antwortdokumente; eine Query ist nicht ein einzelner Dokument-Read. Scheitert nur dieser optimierte Collection-Read, fällt der Endpoint korrektheitshalber auf `list_turns` + owner-gebundene Turn-Details zurück, statt den Browser auf zwei Bookmark-Snapshots zu reduzieren. Der Endpunkt ist bewusst ein synchrones `def`, damit die blockierenden Reads im Threadpool statt auf dem Event-Loop laufen. `/bookmark` (POST/DELETE), `/bookmark/consensus` sowie `POST /bookmark/consensus/share-result` erhalten Speichern, Löschen und die sichere Share-/Watch-Rehydration. Consensus-Inhalte werden aus einem owner-gebundenen Pending Result oder completed Turn serverseitig materialisiert, nicht aus frei behaupteten Clientfeldern; die alten, ignorierten Client-Kopien bleiben für gecachte Clients im Schema, werden aber nicht mehr formvalidiert und können den autoritativen Save daher nicht mit 422 blockieren. Quellenlisten werden nicht nach Anzahl gekürzt; die bestehenden Dokument- und Request-Bytebudgets begrenzen den Save ausdrücklich. `persist_authoritative_consensus_bookmark` ist der gemeinsame Writer für den primären `/consensus`-Abschluss und den idempotenten `/bookmark/consensus`-Fallback. Der breite slowapi-IP-Schutz sitzt vor der Tokenprüfung; die eigentlichen Modell- und Consensus-Save-Budgets gelten danach pro UID, damit der interne Preset-Fan-out nicht mit fremden Nutzern an einem Proxy-/NAT-Bucket konkurriert. Persistent gelten höchstens 250 Bookmarks, 750 kB je Dokument und 25 MB geschätztes Gesamtbudget pro UID. `DELETE /bookmark` liest die Chat-Bindung und legt **vor** dem Entfernen des Bookmarks per `ChatStore.request_chat_deletion` in einer Transaktion Tombstone (`status=deleting`), einmaligen Zählerabzug und einen dauerhaften Auftrag `chat_deletion_jobs/{sha256(uid:chat)[:40]}` an; erst danach wird das Bookmark gelöscht und `run_chat_deletion` versucht die Kaskade sofort. Scheitert sie (auch zwischen zwei Batches) oder stirbt der Prozess, bleibt der Auftrag mit `attempts`, `last_error` (nur Kategorie) und Backoff (`next_attempt_at`, 1 min bis 6 h) sichtbar und `resume_chat_deletions` im stündlichen Retention-Loop beendet ihn; quittiert wird erst nach vollständiger Kaskade. Kann der Auftrag nicht angelegt werden, bleibt das Bookmark bestehen und die Antwort ist 500 (nichts gelöscht, erneut versuchbar). Saves akzeptieren eine validierte stabile `bookmarkId`, sodass alle Turns einer laufenden Unterhaltung dasselbe Sidebar-Bookmark aktualisieren; Legacy-Saves ohne ID bleiben fragebasiert. `previous_question`/`previous_turn` bleiben als kompatibler Ein-Turn-Fallback für alte Bookmarks ohne Chat-Bindung erhalten. Alle Bookmark-Antworten sind wie `/chats` `private, no-store`. Die Save-Endpunkte liefern weiterhin den zusammengeführten Datensatz zurück; der Client reduziert ihn sofort auf Listenmetadaten und hält höchstens das geöffnete Detail im Cache. Der seltene Browser-Fallback sendet nur IDs plus kleine Legacy-Texte, nutzt `keepalive`, wiederholt Netz-/408-/425-/429-/5xx-Fehler begrenzt und zeigt einen endgültigen Fehler dedupliziert verständlich an. |
| `share.py` | `/api/share` (POST), `/api/share/{id}` (DELETE), `/api/my/shares` (neueste zuerst, in Firestore sortiert über Index `shares(owner_uid, created_at desc)`, `?cursor=`, Antwort mit `has_more`/`next_cursor`; der Dialog zeigt einen Hinweis, wenn ältere Links fehlen), `/api/share/{id}/report`, öffentliche Seite `/s/{slug_id}`, `sitemap-shares.xml`. |
| `watch.py` | Consensus Watch: `/api/watch` (POST), `/api/watch/goal-suggestions` (POST, bis zu drei beobachtbare Ziele zur Frage über einen Judge-Call, 6/min; ein Fehler liefert eine leere Liste), `/api/my/watches` (inkl. Original-Baseline-Score, kompakter History mit Drift-Signal je Watch, `resolution`, `last_probe` und autoritativer Plan-/Active-/Resolved-Metadaten für die UI), `/api/watch/{id}` (PATCH/DELETE; `status=active` auf einer abgeschlossenen Watch braucht ein neues oder leeres Ziel), Morning-Brief-Einstellungen `/api/my/watch-brief` (GET/PATCH), nutzergebundene Telegram-Verbindung `/api/my/telegram` (GET/DELETE), `/api/my/telegram/link|test` (POST) und der per Secret-Header geschützte `/api/telegram/webhook`; außerdem öffentliche, HMAC-signierte `/watch/unsubscribe`- und `/watch/brief/unsubscribe`-Links. |
| `topics.py` | Eigenständige öffentliche Topic-Ticker: Hub `/topics`, versionierte Detailseite `/topics/{slug}` (`?version=<run_id>`, rendert Position Map + Agreement-Kurve über `services/history_view.py` — dieselbe Darstellung wie die Watch-Seiten, bewusst nur bis zum gewählten Snapshot), `sitemap-topics.xml`, Double-Opt-in-Follow unter `/api/topics/{slug}/follow` + `/topic-follow/confirm|unsubscribe`; der Versand-Claim ist persistent gehasht und besitzt Resend-, Empfänger- und globales Stundenbudget. Der Favicon-Proxy ist auf 30 Requests/Minute, acht parallele Requests, einen eigenen Vierer-Executor, zwei Sekunden Upstream-Zeit sowie einen 2.000-Einträge-LRU einschließlich 24-h-Negativcache begrenzt. Admin-CRUD liegt unter `/api/admin/topics`. Ein leeres `POST /api/admin/topics/{id}/runs` führt den konfigurierten Research-/Consensus-Run aus; ein Payload mit `consensus_md` bleibt als expliziter Legacy-Import verfügbar. |
| `api_v1.py` | Nutzergebundene asynchrone Consensus-API: Run-Start/Status/Löschung unter `/api/v1/consensus/runs`, transaktional idempotentes Publizieren erfolgreicher Runs per `POST .../{run_id}/share`, eigene Share-Liste/-Details/-Widerruf unter `/api/v1/shares` sowie direkte Admin-Indexfreigabe per `PUT /api/v1/shares/{share_id}/indexing`. Der Admin-only Scheduled Publisher liest `GET /api/v1/publisher/config`, startet Runs per `X-Consensus-Publisher: true` mit demselben Balanced-Preset-Modellplan wie jeder API-Run (kein Provider-Ausschluss) und bindet per `POST /api/v1/shares/{share_id}/watch` idempotent einen Weekly-Watch mit festem Free-Watch-Modellprofil; `public_config` meldet die tatsächlich genutzten Familien als `initial_run_providers`/`watch_providers`, die Admin-UI zeigt genau diese Listen; dessen globale Kapazität wird zusammen mit Watch und Publisher-Zähler in derselben Transaktion geprüft. Auth über gescopte `X-API-Key`s, Run-Idempotenz über den Pflichtheader `Idempotency-Key`; Pydantic-Modelle bilden den Vertrag in `/openapi.json` ab. |

Der Scheduled Publisher läuft per GitHub Actions montags, mittwochs und freitags.
Er bleibt ein Standardbibliothek-CLI: `scripts/publish_consensus.py` ergänzt
beim direkten Dateiaufruf den aus `__file__` ermittelten Repo-Root. Gemeinsame
OpenRouter-URLs/Headers und Publisher-Reasoning liegen dependency-frei in
`app/core/openrouter_contract.py`; Backend-Config und Engine re-exportieren
ihre bisherigen Namen. Aufgeschobene Typannotationen halten den gemeinsamen
Import auch mit dem lokalen Python-3.9-Backend kompatibel. Der Publisher importiert weder Backend-Config noch
Engine. `OPENAI_TOPIC_MODEL` akzeptiert bare OpenAI-IDs oder qualifizierte
OpenRouter-IDs; leer bedeutet `gpt-5.6-luna`. Credentials bleiben in
`app/services/llm/credentials.py`. `tests/test_publisher_standalone.py` prüft
den CLI und den gemockten Publishing-Flow ohne site-packages bei Push/PR und
vor jedem geplanten Lauf (siehe `docs/testing.md`).
Seine identisch in `scripts/publish_consensus.py` und
`app/services/publisher_config.py` gehaltenen `Search-opportunity requirements`
nehmen ein frisches AI-Produktereignis (höchstens 24, notfalls 48 Stunden alt)
als Auslöser, verlangen aber eine Frage, die das Ereignis überlebt: ob eine
Behauptung hält, nicht ob etwas existiert oder wann es erscheint. Über die
Veröffentlichung entscheidet danach der Judge: Runs, deren Modelle sich einig
sind, werden bezahlt und trotzdem verworfen.
| `admin.py` | `/api/admin/shares` (Filter `reported` = `reports_count > 0` nach Report-Anzahl bzw. `all` = neueste zuerst, jeweils in der Firestore-Abfrage vor dem Limit; `cursor`/`limit`, Antwort mit `has_more`/`next_cursor`, UI mit „Load more“), `/api/admin/shares/{id}/moderate`, `DELETE /api/admin/shares/{id}` (sofortiger Hard-Delete inklusive Watch/History/Followern), `/api/admin/models` (GET/POST; enthält auch die validierte `memory_edit`-Konfiguration), Publisher-Steuerung unter `/api/admin/publisher-config` (GET/PUT), API-Key-Ausgabe/-Liste/-Widerruf unter `/api/admin/api-keys`, Kontostufen unter `/api/admin/account-tier` (GET Lookup per UID/E-Mail, PUT setzen) und `/api/admin/account-tiers` (Liste + Audit), `/api/admin/watches` (cursor-paginierte Diagnose-Liste mit `limit`, `next_cursor`, `has_more`; im API-Tab zusätzlich als gefilterte Publisher-Watch-Seitenliste), `/api/admin/watches/{id}/run` (fällig stellen + Scheduler sofort wecken), `/api/admin/watches/test-email` (SMTP-Test an die verifizierte Admin-Adresse), read-only SEO-Übersicht `GET /api/admin/seo` (liest jede Seite samt 28 Tagesmetriken, also Tausende Firestore-Reads: `admin.js` lädt sie seit 2026-10-03 erst beim ersten Öffnen des SEO-Tabs, `ensureSeoOverview`; die beiden Watch-Listen teilen sich beim Laden einen `/api/admin/watches`-Request), sanitisierten Live-Check `POST /api/admin/seo/check`, manueller Search-Console-Lauf `POST /api/admin/seo/collect` sowie speicherbare read-only Judgements per `POST /api/admin/seo/pages/{page_id}/recommendation` und optional `.../content-judge`, `/api/admin/benchmark/runs` (Liste) + `/api/admin/benchmark/runs/{run_id}` (Detail, liest Firestore-publizierte kompakte Benchmark-Reports mit lokalem Disk-Fallback über `benchmark/report_reader.py`). Alle hinter `is_user_admin`. |

Weekly-SEO-Admin-Erweiterung: `GET /api/admin/seo/review`, `PUT
/api/admin/seo/review/config` und `POST /api/admin/seo/review/run` liefern bzw.
steuern Status, Zeitplan und manuellen Start. Gruppen-Vorschau/-Ausführung laufen
über `POST /api/admin/seo/reviews/{run_id}/preview|apply`. Redaktionelle
Snapshot-Entscheidungen werden per `POST .../{run_id}/editorial-decision`
gespeichert; ein vom Portfolio-Judge vorgeschlagener Publisher Topic Brief wird
explizit per `POST .../{run_id}/topic-brief/accept|reject` entschieden. Alle
Endpunkte sind admin-only.

Akquise-Strategie (seit 2026-07-26): Publisher-Brief und
`SEARCH_OPPORTUNITY_RULES` wählen dauerhaft nachgefragte, **strittige** Fragen
statt des News-/Meme-Fensters; `evaluate_disagreement` im Publisher-Skript
veröffentlicht einen fertigen Lauf nur bei Agreement ≤ 80 und mindestens einem
Widerspruch. Dieselbe Schwelle bewertet den Bestand: `seo_dossier` liefert
`consensus_signal`, `seo_recommendation.classify_distinctiveness` macht daraus
distinctive/commodity, distinctive Seiten bekommen 120 statt 60 Tage vor
`noindex` und bei Unsichtbarkeit `refresh_title_and_intro`.

**Zentrale Templates** (`templates/`, gerendert mit `Jinja2Templates`):
`landing.html` (Marketing), `index.html` (die App — Haupt-Markup; die
Script-/Style-Tags rendert `app/core/assets.py` aus `static/js/bundles.json`),
`admin.html`, `admin_benchmark.html` (Admin-Benchmark-Visualisierung, eigenes
Template + Firebase-Auth-Modul wie `admin.html`), `share.html` (öffentliche
Consensus-Seite), `share_unavailable.html`, plus statische Rechts-/SEO-Seiten
und SEO-Erklärseiten wie `ai-model-comparison.html` / `consensus-engine.html`.
`topics.html` und `topic.html` bilden den öffentlichen Topics-Hub bzw. die
Timeline-/Evidence-Detailseite; die Topic-Redaktion liegt als eigener Tab in
`admin.html` unter `/admin#topics` (`/admin/topics` redirectet dorthin).
Alle öffentlichen HTML-Seiten teilen Navigation und Footer über
`templates/partials/public_nav.html` und `public_footer.html`. Das Umami-Snippet
liegt seit 2026-07-31 ebenfalls zentral in `templates/partials/analytics.html`
(einzige Stelle mit der Website-ID) und bringt den Selbst-Ausschluss per
`?notrack=1` mit; die Admin-Templates tracken gar nicht mehr. Seit 2026-08-07
begrenzt `data-domains="consens.io,www.consens.io"` das Tracking auf die
Live-Domain — lokale Server (jeder uvicorn-Port) und Preview-Deploys senden
gar nichts mehr; neue Domains muessen dort eingetragen werden. Die vier Informationsseiten beschreiben automatische
Chat-/Bookmark-Speicherung, zusätzliche KI-/Suchaufrufe und tatsächliche Retention;
Betreiberangaben werden als direkt lesbares HTML ausgegeben. Offene rechtliche
Betriebsfragen und Quellen: `docs/legal-review-2026-09-05.md`. Die primäre
Navigation beschränkt sich auf Product, Watches, Topics, Questions, Benchmark
und die App-CTA; Model guide und About liegen im Footer. Seit 2026-10-02
erzählt die Landingpage Agent als Standard: Hero seit der Todo-Runde 3
(2026-10-02) „Six models answer. See where they disagree.“ (die alte Zeile
„One agent does the work. Six models check it.“ hatte den Mechanismus
verdreht: die sechs antworten, ein unbeteiligter Judge prüft). Composer-Mockups
wie in /app: (+) ohne Fläche, KEIN Moduschip mehr (der Modus steckt im (+)),
rechts der Modell-Chip `{{ agent_label }} +6 ⌄` – `pages.py::landing` rendert
das echte Default-Modell des Agents (`agent_client.agent_model_label()`, ohne
Netzzugriff), nie ein Schaufenster-Modell; Lippe
`partials/composer_toolbar_mockup.html` mit Reasoning Auto · Attach ·
Modell-Icons, ohne eigenes Fenster um Szene 01). Szene 02 (`#agent-mode`, `.lp-agent`) baut seit
2026-10-02 einen Agent-Turn so nach, wie `agent-activity.js`/`agent-review.js`
ihn zeichnen: Uhr „Working for …s“ → „Thought for 24s“, Agent-Notizen,
„Comparing perspectives…“ mit sechs nacheinander fertig werdenden Modell-Icons,
eine Live-Statuszeile (Writing answer… / Checking the answer…), gestreamte
Antwort, danach Markierungen und Evidenzzeile („43/100 agreement ·
Contradictions 2 · Answers 6“); keine Ladebalken mehr. Treiber
`landing-scenes.js` (`buildRunScene`, Standbild bei reduced motion = fertiger
Turn über `render.still`). Szene 03 und Watch sprechen von „answer“ statt
„consensus“. Seit dem Feinschliff (2026-10-02) ist die H1 `.lp-hero-claim` die lauteste
Zeile der Seite (Display-Größe, zweiter Satz in `--ink-3`), die ganze Landing
steht auf EINEM Grund (`--ground`; Abschnitte trennt eine auslaufende
Haarlinie statt zweier Tonstufen), die Szenen 01/02 laufen mit 210vh (Desktop)
bzw. 170vh durch und enden ohne Leerlauf, ihre Schiene ist 1 px und trägt an
der Spitze das Hauslicht. `.lp-reveal` blendet nicht mehr aus: Blöcke sind ab
dem ersten Frame sichtbar, nur unterhalb der Falz startende (`.is-armed`)
steigen 8 px ein. Der Schluss wiederholt das Hero-Feld leer (öffnet `/app`).
Die öffentliche Navigation hat bis 700 px ein Menü (`<details class="nav-menu">`
in `partials/public_nav.html`, Stil in `static/css/public-nav.css`, importiert
von `landing.css` und `public-pages.css`). Der Landing-Hero
ist seit 2026-07-17 demo-first: Ein klickbares Input-Feld (Look des /app-Inputs,
"Try the demo"-Button, Provider-Chips darunter) verlinkt auf `/app?demo=1`;
Landing-Hero und App-Composer teilen die `.demo-action`-Gestaltung aus
`static/css/demo-action.css` (Import in `landing.css` und `static/style.css`):
seit 2026-10-02 schlank: 36 px hoch wie der Senden-Kreis, Pille, 13 px/500,
Play-Zeichen als Glyph ohne eigenen Kreis; auf Touch-Geräten wächst nur die
Trefferfläche (`::after`) auf 44 px, nicht die Zeichnung.
Die App zeigt ebenfalls „Try the demo“, bis 640 px platzsparend „Demo“;
der zugängliche Name und der Startablauf bleiben unverändert. Für Gäste
nimmt der Demo-Knopf den Platz des Senden-Knopfs ein (`components-misc.css`:
`#sendButton[data-icon="send"]` ist ausgeblendet, solange der Chip sichtbar
ist; im Lauf als Stopp-Knopf, beim Tippen, im Agent-Modus und im
eingeklappten Handy-Composer steht Senden wie immer da).
Seit 2026-10-01 tragen die Bedienelemente, die eine Frage an die Modelle
schicken, ein Licht von unten aus `static/css/send-glow.css` (ebenfalls in
`landing.css` und `static/style.css` importiert): ein `::before` mit
Hausgrün (`--agree`) als Schimmer und beleuchteter Unterkante, links unten am
hellsten. Klasse `send-glow` auf `#sendButton`, `.lp-send` und „Try the
demo“ (Markup in `landing.html` und `static/demo.js`). Zustände stehen beim
Bedienelement: in `shell.css` aus, solange nichts gesendet werden kann, beim
Stopp-Knopf atmet es seit 2026-10-02 nur noch in der Deckkraft
(`send-glow-breathe`, kein umlaufendes Licht mehr; Start-Ring und
Stopp-Einblendung deutlich kleiner); in `landing.css` geht es an,
sobald die Mockup-Frage fertig ist. Das Licht ist diesen Elementen vorbehalten.
`static/demo.js` erkennt den Parameter und startet die Demo automatisch in der
echten App. Dabei wird zuerst die vollständige Frage in den Composer getippt;
beim simulierten Absenden wandert sie in den Thread-Kopf, der Composer wird
geleert und erst danach beginnen Fortschrittsanzeige und Modell-Spinner. Seit
2026-08-14 ist das Szenario die Prüfung einer heiklen Nachricht („Wir
verschieben den Launch um zwei Wochen — kann ich das so an die Kundin
schicken?"): Die Frage wird getippt, der Nachrichtenentwurf danach in einem Zug
eingefügt. Seit 2026-08-18 bleibt der Demo-Lauf bis zum Abschluss aller sechs
Antworten sichtbar und führt danach über die getrennten Zustände „Writing the
consensus" und „Checking for contradictions" zum Ergebnis; die lokale synchrone
Widerspruchsauswertung hält ihren angekündigten Zustand dafür 1,1 Sekunden. Der
Szenario ist seit 2026-10-02 eine Waermepumpe im Haus von 1978 mit den
Original-Heizkoerpern (vorher: eine Kundennachricht umformulieren, was Max
„laecherlich“ fand). Der Lauf hat drei strittige Stellen (kritischer
Widerspruch zur Vorlauftemperatur 55 °C vs. 45 °C, kleiner zum Gaskessel als
Reserve, eine abweichende Gewichtung zur Reihenfolge Heizlastberechnung vs.
Wintertest) und 19 Claims; der Score 43/100 ist nicht gegriffen, sondern die
Rechnung aus `consensus_scoring.py` auf genau diese Daten. Zahl und Einheit
(°C, kW, m²) trennt ein geschuetztes Leerzeichen, auch in Zitaten und Tests.
Quellen gibt es bewusst keine – erfundene Belege waeren die schlechtere Demo,
und der Quellen-Tab blendet sich bei leerer Liste ohnehin aus. Der
Landing-Walkthrough (Szene 01–03) zeigt denselben Lauf, damit Hero, Demo und
Mockups eine Geschichte erzählen. Die Demo aktiviert vor jedem Start das konfigurierte Balanced-Preset ueber
`App.selectConsensusPreset('balanced')`, einschliesslich aller sechs Familien
und ihrer aktuellen Modelllabels. Daily-/Custom-Ausschluesse werden dabei durch
Balanced ersetzt. Die sechs redaktionell geschriebenen Demo-Perspektiven werden
bei geaenderten Preset-Familien samt Claims, Zitaten und Differences konsistent
auf die aktuelle Aufstellung abgebildet; es werden keine LLMs aufgerufen.
Modell-Spinner setzen `responseState=pending` ohne Antworttext. Waehrend des
Streams wird aus den lokalen HTML-Vorlagen reines Markdown in
`dataset.consensusAnswer` geschrieben; der Leser interpretiert Ladeindikator-HTML
nicht als Antwort. Alle sechs Texte enden mit `responseState=complete`.
Die Demo verwendet bei deaktiviertem Agent Mode ebenfalls
`enterDirectComparisonView()` statt eigener Hero-Klassen, damit die Antworten
im gemeinsamen Thread-Layout sichtbar bleiben. Seit 2026-10-02 spielt sie bei
der Moduswahl Agent (Default, auch für Gäste von der Landing) einen Agent-Turn
(`runAgentDemoFlow`): `App.agentChat.demoView(true)` hält `#agentAnswer`
sichtbar und setzt `body.single-agent-active.agent-demo-active` (auch ohne
Agent-Zugang); die Demo rendert Aktivität über `App.agentActivity.render`, die
Antwort per `renderMarkdownStream`, danach ein lokales `agent_review` mit
einer Comparison und dem Demo-`differencesData` über `App.agentReview.render`
(Marken, 43/100, Answers/Contradictions im Antwortleser). Die Aufrufe hinter
dem Turn (sechs Vergleichsantworten, zwei Judges) reicht sie als ganzen
Schnappschuss an `App.agentDelegation.demo({turnId, running, agents, usage})`:
dieselben Modell-Icons neben der Uhr, dieselbe Aktivitätsleiste und derselbe
Lichtweg wie ein echter Lauf, ohne Request und ohne Stop; Tokenzahlen sind aus
den Fixture-Texten geschätzt (~4 Zeichen/Token). `demo(null)` gibt alles frei
(`clearDemoAgentAnswer`, und `agent-chat.js` bei jedem Render ohne
Demo-Ansicht). Ein echter Lauf
(`registry.visible()`), der Hero-Zustand oder „New chat“ beenden die
Demo-Ansicht. Die Demo-Texte (Fixtures und Landing-Mockups) kommen seit
2026-10-02 ohne Geviertstriche aus. Compare und Consensus behalten ihre bisherigen Demo-Abläufe.
Sie bleibt vollständig clientseitig und ruft weder
`recordModelVote` noch `/consensus`/Bookmark-Persistenz auf; Demo-Läufe verändern
damit weder das Best-answer-Nutzungssignal noch `differences_stats`.
Produktgeschichte führt danach über Ask/Run/Decide zum vierten
Landing-Schritt `#watch`: Eine kompakte Baseline→Change→Telegram-Visualisierung
erklärt Consensus Watch und verlinkt direkt auf `/app/watches`; derselbe Anker
ist in der öffentlichen Navigation erreichbar. Direkt davor steht seit
03.10.2026 der Benchmark-Abschnitt mit dem Live-Streifen aus dem Model Pulse
(„No model wins every time.“), der auf `/model-pulse` verlinkt. Die Seite
zeigt Best-answer-Raten pro Lauf, in dem eine Familie war (siehe oben), und
trennt dieses
Judge-Signal ausdrücklich vom kontrollierten Accuracy-Benchmark.
`/benchmark` verlinkt im Hero zurück auf diese zweite Perspektive. Die Consensus-Engine-Seite nutzt weiterhin die Ergebnisdarstellung
aus `partials/product_result_mockup.html`.
Eingabe-Mockups im Landing-Hero und der Ask-Szene verwenden zusätzlich
`partials/composer_toolbar_mockup.html`: dieselbe 36-px-Leiste wie die App
(Reasoning, Attach und sechs gestapelte Provider-Icons; Modus und Check
contradictions stehen seit 2026-10-02 nicht mehr darin), seitlich
12 px eingerückt. Der Input liegt wie in `/app` explizit vor der animierten
Leiste, damit seine abgerundete Unterkante vollständig sichtbar bleibt.
Im Hero ersetzt sie die separate Provider-Zeile. Die
Ask-Szene blendet sie beim Senden aus (reservierter Platz stabilisiert die
Scroll-Zeitachse); reine Agent-Ergebnis-Mockups bleiben ohne Eingabeleiste.
Die Vorschau enthält keine scheinbar bedienbaren Schalter; der Hero-Input
verlinkt weiterhin auf die echte Demo.
Container-Queries kürzen die Werkzeuglabels anhand der tatsächlichen Breite
des jeweiligen Mockups, damit die Ask-Vorschau auch auf Desktop und bei 320 px
mit dem zusätzlichen Check-Sources-Eintrag nicht überläuft.
**Seit 2026-07-25 spiegeln alle
Marketing-Mockups die Inline-Confidence-Darstellung der App** (Scene 03 in
`landing.html` inkl. der drei Slider-Beispiele, `product_result_mockup.html`
und die beiden Mockups in `consensus-engine.html`): eine Antwort in voller
Breite, Uneinigkeit als farbige `.cx-claim`-Marke im Satz, die Differences als
zugeklapptes `details.consensus-differences-panel` darunter.
`components-consensus-visuals.css` enthält dafür das gemeinsame Marken-,
Verdict- und Differences-Vokabular (`--cx-mark-*` auf der Ampel
`--agree`/`--partial`/`--dispute`, `--cx-major-line`, `--cx-flash`,
`.diff-card.is-focused`) und wird von App und
Landing importiert. Landing-
spezifisch sind nur die Lesehilfe `.lp-mark-key` unter der Scene-03-Überschrift,
das Einlaufen der Marker beim Scroll (`.lp-scene-visual.is-visible` /
`.lp-slide.is-active`) und ein kleiner Handler in `landing.html`, der
`[data-diff-open]` auf die passende Karte klickbar macht. Seit 2026-07-27 tragen alle diese Mockups
zusätzlich die rahmenlose Shell-Sprache: Der Verdict ist eine Zeile (Score-Ring
+ Headline + Judge-Fußnote) statt eines gefüllten Balkens. Die gemeinsamen, an `/app`
ausgerichteten Light-/Dark-Tokens liegen in `static/css/public-tokens.css` und
werden von `landing.css` sowie `public-pages.css` importiert; seitenbezogene
Layouts bleiben in diesen beiden Dateien bzw. in `benchmark.css` und
`consensus-engine.css`. `topics.css` ergänzt ausschließlich Hub-, Dossier-,
Timeline-, Evidence- und Follow-Komponenten der beiden Topic-Templates und importiert
dieselbe Token-Schicht mit eigenem Cache-Buster.
Die gemeinsame Typografie-Grundlage liegt in `static/css/typography.css` und
wird von `variables.css` (App/Admin) sowie `public-tokens.css` (Marketing/Public)
importiert. Sie hostet Inter Variable lokal als normale und kursive WOFF2-Datei,
definiert die verbindlichen Größen-, Gewichts-, Zeilenhöhen- und Laufweiten-Tokens
und lässt Formularelemente die Produktschrift erben. Google-Fonts-Links und deren
CSP-Freigaben existieren nicht mehr; Monospace bleibt ausschließlich für Code und
technische Identifikatoren, KaTeX behält seine eigene Mathematikschrift.
Die Typo-Skala hat seit dem Feinschliff (2026-10-02) neun Textstufen:
`--font-size-xs` 12 (Untergrenze, `--font-size-micro` ist nur noch ein Alias),
`-ui` 13 (Bedienelemente), `-sm` 14, `-base` 16, `-read` 17 (Antworttext),
`-lg` 18, `-title` 20, `-xl` 24, `-2xl` 32, dazu zwei Display-Größen. Hart
kodierte Pixelgrößen gibt es im App-CSS nur noch für Glyphen in Icons (<11 px).
Daneben liegt **`static/css/foundation.css`**, ebenfalls von `variables.css`
und `public-tokens.css` importiert: `--radius-2xs` (6 px, neben xs 8 · sm 10 ·
md 14 · lg 16 · xl 20 · pill; Regel: innerer Radius = äußerer minus Abstand),
die Bewegungs-Tokens (`--ease-standard`/`--ease-out`/`--ease-in`,
`--dur-press` 120 · `--dur-state` 200 · `--dur-layer` 320 · `--dur-light` 560 ms),
EIN Fokusring (`--focus-ring`, `--focus-ring-offset`; `base.css` setzt ihn per
`:where(...)` als Default für jedes fokussierbare Element) und `--light` für das
Hauslicht. Komponenten wählen den nächstliegenden Token statt eines eigenen Werts.
**Buttons:** Der gefüllte Standardknopf ist opt-in (`.btn`, Altname `.button`,
`components-input.css`). Die frühere globale `button:not(...)`-Kette mit rund
90 Ausnahmen ist entfernt; ein `<button>` startet neutral. Admin-Seiten
geben klassenlosen Buttons den alten Look in `admin.css`.
`shell.css` gibt Agent-/Consensus-Antworten und gespeicherten Turns denselben
Leserhythmus: 17 px (`--font-size-read`) mit 1,7-facher Zeilenhöhe, Fließtext
höchstens 66 Zeichen breit (Tabellen, Code, Formeln volle Spalte), ein kurzer
erster Absatz (≤ 240 Zeichen, gefolgt von weiterem Inhalt) wird zum Lead
(`.has-lead`, gesetzt von `markAnswerLead` in `markdown-stream.js` bei jedem
Rendern, auch im Stream), normale Laufweite, eigene Absatz-,
Listen- und Überschriftenabstände. Die Regeln für den Consensus-Labelkopf gelten
nur für direkte `h2`-Kinder, nicht für Markdown-Überschriften im Antworttext.
Statusmeldungen, Antwortleser, Codeblöcke und Tabellen behalten ihre eigene Typografie.
`index.html`, `admin.html` und `admin_benchmark.html` enthalten keine Inline-Skripte, Inline-Styles oder
HTML-Eventhandler mehr. Jinja-Konfiguration liegt ausschließlich in escaped
`data-*`-Metadaten und wird von `app-bootstrap.js` beziehungsweise
`admin-config.js` gelesen; `app-dom-events.js` bindet die früheren Inline-
Handler. Die routenspezifische CSP für `/app`, `/app/watches`, `/admin` und alle `/admin/*`-Unterpfade
kommt deshalb bei `script-src` ohne `'unsafe-inline'` aus. Seit 2026-09-29 gilt
das auch für die öffentlichen Topic-Detailseiten `/topics/{slug}` (Review R01):
`topic.html` lädt das Theme per `static/js/public-theme.js` und bündelt Strip,
Rückkehrer-Band, Follow-Formular und Zitat-Chips in `static/js/topic-page.js`;
Datentext (z. B. `change_summary` im Check-Strip) wird dort nur per
`textContent`/DOM-Knoten eingesetzt, nie erneut als HTML geparst. Die übrigen
öffentlichen Seiten (einschließlich des Hubs `/topics`) behalten die bisherige
Policy während der weiteren Style-Migration.

---

## 3. Frontend-Architektur

Geladen werden (Reihenfolge ist Vertrag, steht in `static/js/bundles.json`,
siehe §8): zuerst die synchronen `app-bootstrap.js`, `app-state.js`,
`auth-session-state.js`, `run-registry.js`, `watch-state.js` und
`error-reporter.js` (Gruppe
`head`, render-blockierend, weil sie den First Paint seeden), dann lokale Vendor-Libs
(`marked`, `DOMPurify`, KaTeX + Auto-Render), der same-origin
`email-verify.js` als inhaltsadressierte `window.App.emailVerification`-Brücke,
den `auth-bootstrap.js`-Watchdog vor `firebase.js` + `demo.js` (ES-Module), dann
deferred `app-ui.js` und die Feature-Module unter `static/js/` in fester
Reihenfolge, zuletzt `app-init.js` und `app-dom-events.js`.

In Produktion liefert `npm run build` daraus fünf inhaltsgehashte Bundles
(419 KB statt 872 KB in 36 lokalen JS-Requests); ohne Build-Output oder mit
`FRONTEND_DEV=1` gehen dieselben Dateien einzeln raus. Siehe
`docs/frontend-build.md`. Das Build-Manifest inventarisiert alle Inputs
einschließlich Konfiguration, Build-Skript und lokaler Modulabhängigkeiten, damit
der Python-Staleness-Test auch indirekte Änderungen erkennt.
Der gemeinsame Node-/Python-Fingerprint normalisiert CRLF zu LF für Text-Inputs
außerhalb `static/vendor/`; Vendor-Assets bleiben bytegenau. Dadurch ist ein
unter Windows erstellter Commit auch nach einem Linux-Checkout aktuell.
`.gitattributes` erhält die Bytes unter `static/vendor/` und `static/dist/`
einschließlich Build-Manifest mit `-text`; Windows-Autocrlf darf die erzeugten
Inhalte und ihre Dateinamen-Hashes nicht verändern. Der Node-Outputtest belegt
dies durch einen echten temporären Git-Checkout mit CRLF-Gegenkontrolle.
`scripts/frontend-output.mjs` publiziert geänderte Bundle-/Vendor-Dateien über
atomaren Dateiersatz und schaltet das Manifest erst nach den Bundles um;
unveränderte Dateien bleiben unangetastet. `previous_assets` hält pro JS-/CSS-
Gruppe zwei Vorgängerversionen auch über identische Rebuilds vor. Erst nach dem
Manifestwechsel werden ältere gehashte Bundle-Dateien entfernt. Das App-HTML
für `/app` und `/app/watches` wird mit `private, no-store` ausgeliefert.

**Modul-Verantwortlichkeiten** (alle in `static/js/` außer markiert):

- **`app-bootstrap.js`** — liest die escaped Jinja-Konfiguration aus
  `#appBootstrapConfig`, initialisiert die bisherigen read-only `window.*`-
  Configwerte sowie den sicheren Umami-Wrapper und stellt Agent-/Auth-/Skeleton-
  First-Paint ohne Inline-Skript her. Bereits aufgeloeste Auth-Zustaende werden
  nicht durch gecachte Token/Skeletons ueberschrieben. `css/skeleton.css` liefert
  gemeinsame Light-/Dark-Platzhalter fuer Account, Chatliste, wartende
  Modellantworten und den oeffentlichen Model Pulse: formgetreue Zeilen,
  verzögertes Einblenden, ruhiger Transform-Shimmer, statisch bei Reduced Motion.
  Die Chatlisten-Skeletons bleiben in `firebase.js` bis zur erfolgreichen
  Metadatenantwort erhalten und blenden dann in die echten Zeilen über
  (`revealLoadedBookmarks`); Fehler/Logout/Watchdog raeumen sie weiter ab.
  Der Antwortleser ersetzt Platzhalter mit dem ersten Text oder einem terminalen
  Zustand; Statuslabels bleiben sichtbar, die leere Ladeflaeche ist `aria-busy`.
- **`app-state.js`** — einzige Schreibschnittstelle für laufbezogene Frage,
  Evidence, Citation-/Share-Kontext, Tierlimits und Spinner-Markup der
  **gerade projizierten Ansicht**. Der autoritative State eines aktiven Laufs
  liegt dagegen in dessen `RunContext`. Legacy-`window.*`-Namen bleiben als
  read-only Getter erhalten; direkte Schreiber werfen, jeder State-Key
  akzeptiert nur seinen deklarierten Owner.
- **`auth-session-state.js`** — besitzt UID, Auth-Generation und den bekannten
  Auth-Zustand; Firebase publiziert darüber `consensio:auth-state`, asynchrone
  UI-Antworten prüfen denselben Snapshot.
- **`run-registry.js`** — session-lokale Autorität für parallele Browser-Läufe.
  `window.App.runRegistry` besitzt höchstens zwei gleichzeitig ausführende
  `RunContext`s, eindeutige Run-/Request-IDs, Status/Phase, eingefrorene
  Provider-/Modell-/Mode-/Reasoning-(`deepSearch`)/Own-Key-Konfiguration, Auth-Snapshot,
  private ChatSession, Usage-Key, Attachments, Evidence, Modell-/Consensus-
  Puffer, AbortController, Bookmark-/Persistenzstatus und Fehler. Es trennt
  `visibleRunId`, `selectedConversationBasis` und eine geöffnete gespeicherte
  Ansicht; Sichtwechsel ändern niemals die Ausführung. Pro Chat-/Bookmark-
  Basis verhindert ein Lock zwei gleichzeitige Follow-ups; bei unklarer
  serverseitiger Turn-Disposition bleibt der Fence bis zum Session-Reset.
- **`watch-state.js`** — besitzt Telegram-, Limit-, Request- und Session-Epoch-
  State des Watch-Frontends. `watch.js` hält nur Rendering und Produktaktionen.
- **`app-dom-events.js`** — zentrale Event-Delegation für Bookmarks, Send,
  Provider-Exclude, Settings und Key-Test; ersetzt HTML-Eventattribute.
- **`error-reporter.js`** — lädt vor allen App-Modulen, fängt ungefangene
  Browserfehler, Promise-Rejections und relevante Asset-Ladefehler ab und stellt
  `window.App.reportCriticalError` für explizite Run-Abbrüche bereit. Nur
  Skripte, Stylesheets und explizit mit `data-critical-resource="true"`
  markierte Elemente gelten als alarmwürdig; dekorative Bilder, Quellen- und
  Dokument-Favicons bleiben bei ihren lokalen Fallbacks. Asset-Alarme senden
  eine allowgelistete Ressourcenklasse und für bekannte lokale Assets zusätzlich
  den geprüften Dateinamen (gehashte Bundles, gepinnte Vendor-Libs, Analytics-Opt-out),
  keine URL/Query. Client und Server deduplizieren je Asset; unterschiedliche
  Dateien derselben Klasse bleiben damit diagnostizierbar. Erwartete
  `AbortError`-Abbrüche werden ignoriert; Session-Deduplizierung verhindert
  Wiederholungen desselben Fehlers. Runtime-Alarme ergänzen einen allowgelisteten
  JS-/DOM-Fehlernamen und, sofern verfügbar, den same-origin Bundle-Dateinamen
  (`head|auth|firebase|demo|app` mit zwölfstelligem Content-Hash) mit Zeile/Spalte,
  dazu bis zu fünf Stack-Frames als reine `[bundle, zeile, spalte]`-Tupel und
  jeder Report den Namen des laufenden `app.<hash>.js` (`bundle`).
  `/api/client-errors` validiert diese Felder erneut, löst sie über die
  Source-Maps auf und gibt die Message nur bei `TypeError`/`ReferenceError`/
  `RangeError`/`SyntaxError` entschärft weiter; Stacktexte, URLs und sonstige
  Meldungen bleiben draußen. Alte Clients bleiben kompatibel.
  Vor dem Keepalive-Request begrenzt der Reporter Meldung/Details/Stack und die
  übrigen Felder auf die Intake-Limits; fehlende Fehlergründe erhalten einen
  gültigen Fallback. Synchrone Transportfehler und Promise-Rejections des
  Reportings dürfen selbst keinen weiteren ungefangenen Fehler auslösen.
- **`auth-bootstrap.js`** — kleiner same-origin Classic-Script-Watchdog vor dem
  Firebase-ES-Modul. Falls dessen gstatic-Imports nicht ausführbar sind, räumt
  er stale Auth-/Usage-/Bookmark-Skeletons ab, zeigt die Gastaktionen trotz
  altem `localStorage.id_token` und öffnet einen bedienbaren Fehlerdialog statt
  einer toten Login-Aktion. `consensio:auth-state` beendet den Watchdog;
  `consensio:auth-unavailable` informiert insbesondere den Watch-Deep-Link.
- **`app-core.js`** — MUSS zuerst laden. Definiert `window.App`-Bus, `modelPrefs`
  (zentrales Mapping Provider→DOM-IDs), `modelAcceptsAttachments(pref, modelId)`
  (immer das gewaehlte Modell; der Reasoning-Schalter tauscht keins), gemeinsame Helfer
  (`getModelOptionLabel`, `getSelectedModelCount`, `setAppTitle`, `showPopup`,
  `trackAppEvent`, `exitHeroMode`) sowie den zentralen
  `window.App.renderUsageDisplay(data, owner)`-Eingang: reicht das
  `token_budget` einer API-Antwort (auch aus Fehler-Details) an
  `App.tokenBudget` weiter; Antworten ohne das Feld (eigene Keys) ändern nichts.
  Jeder `RunContext.usage` hält seinen logischen
  Idempotency-Key, geteilt von `/prepare`, allen `/ask_*` und `/consensus` genau
  dieses Laufs; `window.App.usageRun` ist nur die Legacy-/UI-Brücke.
  `setAppTitle` setzt den Standardtitel oder
  einen gekürzten, fragebezogenen Browser-Tab-Titel; `exitHeroMode` schaltet
  Antwortbereich und Input vom zentrierten Leerzustand in den Laufzustand.
- **`model-picker.js`** — Modellauswahl/Custom-Picker, Default-Modelle, localStorage-
  Persistenz (`restoreModelSelections`). Der Consensus-Picker hat seit 2026-07-18
  eine Preset-Ebene (Daily/Balanced/High Quality + Custom): Presets kommen aus
  `window.CONSENSUS_PRESETS` und setzen als zusammenhaengendes Model-Set genau
  sechs aus den Registry-Familien gewählte Antwortmodelle plus Consensus-Engine. High Quality (interne ID
  `thorough`) ist Pro-only und zeigt
  ein Pro-Badge; eine manuelle Antwort- oder Consensus-Modellwahl wechselt zu
  Custom. Die nativen Selects werden dabei OHNE change-Event gesetzt. Die High-Quality-Basis nutzt OpenAI GPT-5.6 Sol; gespeicherte
  Legacy-Werte mit GPT-5.5 werden bei der Normalisierung migriert. Zustand in localStorage
  `pref_consensus_preset` ("custom" = explizite Modellwahl, ausgeloest durch
  jedes change-Event am Dropdown); `pref_select_consensus` bleibt die
  Custom-Wahl. Bestandsnutzer mit gespeicherter Modellwahl migrieren zu
  "custom"; die volle Modell-Liste bleibt bewusst ohne Beschreibungen.
  **Seit 2026-07-27 ist „Custom" die ganze Aufstellung eines Laufs**, nicht
  mehr nur die Engine-Liste: `state.view` kennt `presets` → `custom`
  (Uebersicht: alle Registry-Familien mit Ein-/Ausschluss-Toggle + aktuellem
  Modell, darunter die Consensus-Engine) → `provider:<key>` bzw. `engine`
  (die jeweilige Modell-Liste, mit Rueckweg). Die Auswahl feuert `change` auf
  dem ZIEL-Select, damit `app-init.js` wie bisher `pref_select_*` speichert
  und auf „custom" umschaltet; nur Provider-Zeilen kehren danach in die
  Uebersicht zurueck statt das Menue zu schliessen. Vorher waren die sechs
  Antwortmodelle vom Composer aus gar nicht erreichbar (im Agent Mode sind
  die Antwortboxen verborgen).
  **Verknüpfte Picker (seit 2026-10-01):** `App.linkModelPicker(primary,
  companion | null, {ownLabel, companionLabel, ariaLabel})` legt zwei Selects
  in einen Chip und ein Menü. Der Companion behält Select, Persistenz und
  Regeln, zeichnet aber in das Menü des Primary (`state.parent`/`ownMenu`,
  `menu.dataset.owner` = wer gerade zeichnet; nur der darf `[data-value]`
  markieren). Einstieg ist die View `overview` mit je einem Abschnitt und
  `[data-picker-level]`-Zeilen (`models`, `secondary`, `companion`), die in die
  bestehenden Ebenen führen; deren Rückwege enden wieder in `overview`.
  `openModelPicker(companion)` öffnet den Primary auf der Companion-Ebene,
  `collapseExpandedModelPicker(companion)` schließt den Primary;
  `openModelPicker(select, {secondary | level: "models"})` springt direkt in
  eine eigene Ebene, `collapseExpandedModelPicker(select, {ownLevelsOnly})`
  schließt nur, wenn eine eigene Ebene offen ist. Ist ein Link angefragt,
  bevor beide Picker existieren, holt `initCustomModelPicker` ihn nach. Jede
  Ebene behält den Fokus im Menü (`data-focus-key`: dieselbe Zeile, sonst die
  gewählte/erste). Rechts betritt Gruppen-, Abschnitts-, Custom-,
  Provider- und Reasoning-Zeilen, Links nimmt die Rückweg-Zeile.
- **Rahmenlose Shell (seit 2026-07-27)** — `static/css/shell.css` wird als
  **letztes** `@import` in `static/style.css` geladen und gewinnt damit bei
  gleicher Spezifität. Es trägt die Material-Ebene des Redesigns: Elevation
  (nur echte Floating-Layer behalten `--lift`), Sidebar, Topbar, Composer,
  Thread- und Watch-Flächen. Grundlage ist eine Fünf-Werte-Oberflächenskala in
  `variables.css` (`--ground`/`--raise`/`--well` + `--ink`/`--ink-2`/`--ink-3`,
  `--line`/`--line-soft`) plus die Ampel `--agree`/`--partial`/`--dispute`; die
  alten Glas-Tokens (`--glass-*`, `--liquid-shadow`, `--card-shadow`) sind als
  **Aliasse auf diese Skala** erhalten geblieben, damit die ~400 bestehenden
  Aufrufstellen weiterlaufen — sie malen nur keine Transluzenz, Blur, Inner-
  Highlights und Schatten mehr. `static/css/public-tokens.css` spiegelt die
  identische Skala, deshalb sind Landing-/Public-Mockups aus demselben Material
  wie `/app` (Testvertrag: `tests/test_public_design_system.py`). Dark Mode
  überschreibt die Grundwerte + die Ampel.
  Seit 2026-09-06 hebt `shell.css` Chat-Fragen (auch historische), Claim-Popovers
  und Claim-/Contradiction-Hoverkarten mit dem lokalen Token `--chat-surface`
  ab: dezentes Neutralgrau (`#f5f5f5`) in Light,
  unveraendert `#303338` in Dark. Der Composer nutzt eigene
  `--composer-*`-Tokens fuer Flaeche, Kontur, Schatten und einen maskierten
  6-px-Backdrop-Blur hinter dem transparenten Thread-Wrapper. Desktop bleibt
  sticky, Mobile fixed; die bestehende Hoehenreserve und Menue-Ebene bleiben
  erhalten. Die anschliessende /app-Vereinheitlichung nutzt `--app-surface`
  auf `body` fuer alle angehobenen Flaechen und bindet dort `--raise`,
  `--chat-surface`, Container-/Response-/Glass-Aliasse neu. Hover und Auswahl
  haben eigene `--app-surface-hover`/`--app-surface-selected`-Toene.
  Der Consensus-/Watches-Umschalter ist in Threads und Direktvergleichen
  ausgeblendet; auf Start- und Watch-Ansicht bleibt er sichtbar. Sein aktives
  Segment ist in Light weiss mit dezenter Kontur.
  Die Thread-Container starten deshalb mit 30 px oberem Padding (46 px bis
  1099 px fuer die verbleibende Float-Navigation, vorher 58 px).
  Light-Highlights nutzen produktweit Jade/Bernstein/Rosenrot und Schiefergrau.
  `variables.css` und `public-tokens.css` spiegeln die neue Grundpalette
  (Canvas #fafafa, Flaechen #f5f5f5, Felder weiss) und Status-Akzente.
  Beide importieren `status-palette.css`: gemeinsame Light-Regeln fuer
  Statuspunkte, Claim-Labels, Resolve-Konturen, Verdict sowie Watch-/Admin-
  Statusanzeigen. Explizite Highlight-/Hover-Flaechen stehen im gemeinsamen
  `components-consensus-visuals.css`. Dark-Paletten bleiben unveraendert;
  Text und Quoten neutral. Oeffentliche CSS-Importketten werden mitversioniert.
  Modals, Picker, Account-/Anhang-/Kopiermenues, Memory-Dialoge und neutrale Buttons
  verwenden dieselbe Skala; Primaer- und destruktive Aktionen behalten ihre
  Bedeutung. `components-input.css`
  nimmt `.close` aus dem generischen Primaerbutton-Stil aus, damit die
  vorhandenen neutralen Dialog-Schliessen-Stile greifen.
  Die anschliessende Light-Invertierung setzt ausschliesslich in
  `body:not(.dark-mode)` den Canvas und Sidebar-Grund auf fast weisses
  `#fafafa`, eingelassene Felder auf Weiss (`--ground`/`--well` plus
  BG-/Input-/Chip-Aliasse); angehobene
  Popups, Fragen und neutrale Buttons nutzen wieder das urspruengliche
  Warmgrau. Der schwebende Composer ist entsprechend grau mit fast weissem
  Blur-Hintergrund. Die Dark-Palette und Public-Seiten bleiben unveraendert.
- **Kontext am Composer: eine Familie (seit 2026-08-17)** — Zitat
  (`.composer-quote`) und Anhänge (`.attachment-bar`/`.attachment-chip`) hängen
  beide an der nächsten Frage und sehen deshalb gleich aus: Kachel auf
  `--ground` (seit 2026-09-06 auf der hellen/angehobenen Composer-Flaeche, wie
  (+) und Lauf-Schalter), `--radius-sm`, **keine** Rahmen, Verläufe, Blur oder
  Schatten, Dateityp-Plakette monochrom auf `--ink`-Wash statt in Rot/Blau.
  Drei Fallen, die das alte Bild „gebastelt" wirken ließen und Regression-Gefahr
  bleiben: (1) der Composer-Block ist **zentriert** (Hero-Begrüßung) — jede neue
  Vollzeilen-Fläche darin braucht `text-align: left`, sonst stehen Labels und
  Dateinamen mittig; (2) `flex-basis: 100%` ohne `box-sizing: border-box`
  addiert das Padding **auf** die Zeilenbreite (die DeepSeek-Notiz stand
  deshalb 20 px über den Rand); (3) Chips an der Nachricht
  (`.message-attachments`) liegen auf `--ground` statt im Well und heben
  deshalb in `shell.css` auf `--raise` — dieselbe Kachel, ein anderer Grund.
  Entfernen (×) ist an beiden Stellen derselbe neutrale Knopf, nie rot: es ist
  kein Alarm. Der einzige Farbträger ist die DeepSeek-Notiz in der
  Ampel-Gelbstufe `--partial-bg` (vorher ein eigenes Amber `#f59e0b`).
- **Sidebar-Rhythmus** — Models liegt in `.sidebar-pinned`, Bookmarks im
  scrollenden `.sidebar-content`. Diese Container-Grenze addiert 14 px (10 px
  Flex-`gap` der Sidebar + 2 × 2 px Scroll-Padding) auf den Sektionsabstand;
  `shell.css` zieht sie mit
  `.sidebar > .sidebar-content { margin-top: -14px }` wieder heraus; ab
  1100 px sind es `-10px`, weil beide Container dort ihre je 2 px
  Scroll-Padding verlieren. Der
  Zusatzabstand vor `.sidebar-pinned` ist auf 8 px reduziert (plus 10 px
  Container-Gap), damit `New comparison → Models` enger bleibt. Models und
  Bookmarks teilen dieselben Icon-/Textspalten und dieselbe Titeltypografie;
  der Bookmark-Toggle sowie seine Suche sind bis zum verifizierten Login
  nativ deaktiviert.
- **Ein einziger Sidebar-Toggle** — `.app-nav-float .sidebar-toggle` erscheint
  nur bei geschlossener Sidebar, `#sidebarToggleInner` sitzt rechts neben der
  Wortmarke in `.sidebar-brand-row`.
  `shell.css` blendet den schwebenden per `body:not(:has(.sidebar.collapsed))`
  (Overlay ≤1099px: `body:has(.sidebar.active)`) aus. `app-init.js` bindet
  **alle** `.sidebar-toggle`-Buttons an denselben Handler; `updateToggleButton`
  pflegt aria/title auf allen. Eine geschlossene Sidebar wird zusätzlich
  `inert` + `aria-hidden`, damit ihre offscreen liegenden Controls weder in der
  Tab-Reihenfolge noch im Accessibility-Tree bleiben. Darunter liegt
  `#newRunButton` („New comparison“) als vollbreites Navigationselement. Er
  leert über `runRegistry.clearVisible()` nur die aktuelle Projektion samt
  Fortsetzungsbasis und kehrt in `is-hero` zurück; aktive Runs und deren
  Bookmark-Saves laufen weiter. Nur
  `firebase.js::resetLoadedRunAfterLogout` cancelt/verwirft sämtliche Contexts.
- **Reading Chrome** — `app-init.js` beobachtet beim lesbaren Consensus den
  Window-Scroll und im geöffneten Watch-Dashboard dessen eigenen
  Scroll-Container. Nach deutlichem Abwärtsscrollen fahren der fixierte
  `#viewSwitch` und der schwebende `.app-nav-float` aus dem Lesebereich;
  Aufwärtsscrollen, Seitenanfang und Tastatur-Navigation blenden sie wieder ein.
  Der Zustand ist rein transient als `body.is-reading-chrome-hidden` und
  verändert weder Sidebar-Persistenz noch Watch-/Consensus-Daten.
- **Mobile Kopfleiste** — `header.app-mobile-header` zeigt bei ≤1099 px links
  das Menü und rechts angemeldet New chat sowie Share/Watch/Cite für die fertige Antwort.
  Auf dem Startbildschirm (`body.is-hero`) steht neben dem Menü die Marke
  (`.brand-float`, Logo + „consens.io“, 44 px Touchfläche; ≤359 px neben
  Log in/Sign up nur das Logo), im Thread gehört der Platz den Aktionen; ein
  mittlerer Titel entfällt. Die deckende Fläche ist 56 px hoch mit
  Safe-Area-Zuschlag; ihre feine Unterkante erscheint erst, wenn darunter
  gescrollt ist (`.is-scrolled` aus `mobile-header.js`, Window- oder
  Watch-Scroll). Alle Icons teilen Tinte (`--ink`), 22-px-Glyphen und
  44 × 44 px Touchflächen; auf Touch-Geräten bleibt keine Hover-Fläche stehen.
  `mobile-header.js` lädt nach `consensus-actions.js` und `watch.js` und verschiebt
  dieselben `#consensusFooterActions`-DOM-Knoten nach `#mobileConversationActions`,
  auf Desktop exakt zurück in den Footer. Readiness folgt `#runProvenance`,
  `#consensusOutput`, Hero und Watch-Ansicht; es gibt keine duplizierten Handler.
  Der Cite-Dialog verankert sich dadurch am sichtbaren Icon, Escape schließt ihn
  und setzt den Fokus zurück. Gäste sehen Log in und Sign up statt New chat;
  die Sichtbarkeit folgt dem bestehenden Auth-Container ohne eigene Session-Kopie.
  Beide Auth-Aktionen bleiben auch neben den Antwortaktionen erreichbar. Ihre
  dezent gerundeten Flächen sind 32 px hoch, die Touchziele weiterhin 44 px.
  Das mobile Seitenmenü liegt beim Öffnen über der Watch-Seite.
  `#viewSwitch` wandert mobil nach `#mobileSidebarViews` und erscheint dort als
  kompakte Textnavigation mit ausgeschriebenem Consensus/Watches, aktiver
  Unterstreichung und 44-px-Touchflächen. Auf Desktop kehrt er als Pillen-Switch
  an seinen ursprünglichen Ort zurück. Auch aus Watches führt New chat über den bestehenden
  `#newRunButton`-Handler zum leeren Composer, ohne Hintergrund-Runs abzubrechen.
  Beide Sidebar-Toggles
  referenzieren `#appSidebar` per `aria-controls`. Der Inhaltsanfang reserviert
  die Leistenhöhe. Reading Chrome blendet mobil die gesamte Leiste gemeinsam
  aus/ein; eine offene Overlay-Sidebar blendet sie ebenfalls aus. Auf Desktop
  bleibt der Wrapper `display: contents` und die bestehende Float-Anordnung
  erhalten. Reader-Dialoge bleiben oberhalb der Kopfleiste.
- **`token-budget.js`** (head-Bundle, vor `firebase.js`) — `App.tokenBudget`,
  der einzige Browser-Besitzer des gemeinsamen Tokenkontos (Compare,
  Consensus, Reasoning-Läufe, Agent; siehe §4 „Ein Tokenkonto für alle Modi").
  `apply(snapshot, {uid, authoritative})` validiert, bindet an den angemeldeten
  Account und ordnet parallele Snapshots (Konfigurationsrevision → UTC-Tag →
  Ledger-`revision` → `observed_at`); `/usage` und `/user_status` sind
  autoritativ (Reset darf den Wert erhöhen). `fromResponse(data)` liest
  `token_budget` auch aus `{detail: …}`. `view()` liefert Prozent übrig
  (`(limit − used − estimated) / limit`, abgerundet, `<1%` statt 0 bei Rest),
  verfügbar für neue Arbeit (`remaining`, also ohne Holds/Reservierungen),
  Zustand `ok|low|out` (≤ 25 % bzw. ≤ 0) und die Reset-Zeit.
  `canStart(mode)` ist dieselbe Regel wie die Server-Admission (verfügbar ≥
  erwartete Tokens des Modus, `null` = unbekannt), `runShare(mode)` der
  ungefähre Anteil eines typischen Laufs („≈ 8 %"). Feuert
  `consensio:token-budget`. Agent (`agent-chat.js::receiveBudget`) speist
  dasselbe Objekt; `App.agentChat.tokenBudget()` liest es nur noch.
- **`sidebar-quota.js`** — Ring im Sidebar-Footer (`#quotaTrigger`) + Panel
  `#sidebarQuota`, für alle Modi dieselbe Ansicht von `App.tokenBudget`
  (seit 2026-10-01). Der Ring ist ein ruhiges 20-px-Glyph mit 2-px-Strich und
  **ohne Zahl im Inneren** (`pathLength=100`, Offset = verbrauchter Anteil);
  Prozentwert und Reset stehen im `title`/`aria-label` und im Panel. Panel:
  Kopf „Today's allowance" + Plan, eine Hauptzahl (`#quotaPercent` „62 %
  left today"), dünner Balken `#quotaTrack` (`role=meter`), Reset-Zeile, eine
  Detailzeile (`#quotaDetail`: „409k of 660k tokens · a Consensus run uses
  about 8 %" bzw. in Agent „Agent books each model call"), Watches als
  eigene kleine Zeile (aus `#watchUsageDisplay`, eigenes Kontingent) und nur
  bei Bedarf eine Fußnote (Holds laufender Arbeit, Schätzungen, leeres Konto,
  veralteter Stand). Ampelfarbe nur auf Ring-Bogen und Balkenfüllung
  (`--partial` ≤ 25 %, `--dispute` leer), nie auf einer Fläche. Bus:
  `window.App.sidebarQuota.{sync,setOpen}`; `runs()`/`deep()` und die
  Run-/Deep-Think-Zeilen gibt es nicht mehr. Der Lauf-Hinweis nennt bei
  eingeschaltetem `#reasoningToggle` den „Reasoning run" (Schätzungs-Key
  `deep_think`).
  Seit 2026-07-27 trägt der Panel-Kopf auch den **Plan**: `#quotaPlanLabel`
  („Free") bzw. `#proBadge` — das Badge sass vorher neben „New
  comparison" und konkurrierte dort mit der einzigen Aktion der Kopfzeile.
  Plus und Pro zeigen nur das Badge (`planLabel.hidden`), nie „Pro Pro"; das
  Badge trägt den Namen der Stufe und ist bei Plus neutral statt golden
  (`.pro-badge.is-plus`) — Gold gehört den teuren Modellen, die Plus nicht hat. Die **Wortmarke**
  ist aus demselben Grund aus dem Footer (unter dem Account-Icon) nach oben in
  `.sidebar-brand-row` gewandert; unten bleibt nur die Meta-Zeile.
- **Navigation/Settings-Shell** (`templates/index.html`, `layout.css`,
  `shell.css`, `components-modals.css`, `app-init.js`, `firebase.js`) — Models
  und Bookmarks sind Sidebar-Abschnitte mit integrierten Icons. Models bleibt
  eine einzelne kompakte Zeile mit Providerzahl; Gäste erhalten beim Klick den
  kurzen Hinweis „Please log in to configure your models.“. Eingeloggt öffnet
  der Klick den bestehenden Run-Picker am Composer, statt die Providerzeilen in der Navigation
  aufzuklappen. Die Modell-Icons unter dem Composer sind mit
  `#composerModelPicker` ebenfalls ein nativer Button und nutzen denselben
  Picker-Einstieg samt Gast-Hinweis und Fokusübergabe. Klick, Enter und
  Leertaste öffnen damit die vorhandene Modellwahl; nur der Sidebar-Einstieg
  schließt zuvor eine mobile Overlay-Sidebar. Die Provider-Inklusion im Custom-Picker nutzt klare
  Checkboxen statt Toggle-Switches. Die Chat-Suche belegt keine
  permanente Zeile mehr, sondern ersetzt bei Hover/Fokus den Bookmarks-Titel
  (auf Touch-Geräten bleibt sie dauerhaft erreichbar). Die frühere Sidebar-/
  Help-FAQ-Rangliste lebt jetzt ausschließlich auf `/model-pulse`; die
  Landingpage verlinkt oben dezent dorthin und die App-Shell lädt keinen
  Firestore-Live-Listener mehr. Die gemeinsame Lesespalte für Fragen, Antworten
  und Composer ist standardmäßig 768px breit (`--app-container-width` auf
  `body`, `layout.css`) und schrumpft auf kleinen Viewports. Bei offener
  Desktop-Sidebar ab 1100px zentriert `--app-sidebar-offset: 260px` die Spalte
  und den Startseiten-View-Switch im verbleibenden Bereich rechts der Navigation;
  eingeklappt und im mobilen Overlay-Modus gilt die Viewport-Mitte. Der mobile
  fixierte Composer verwendet dieselbe Breite wie der Spalteninhalt; mobil
  stehen Menü und im Gespräch die Wortmarke in der deckenden Kopfleiste. Gast-Login/-Sign-up
  sitzt oben rechts, während der Sidebar-Footer nur für eingeloggte Accounts
  das Avatar-Menü mit deckender Light-/Dark-Fläche zeigt. Settings sind seit
  2026-08-17 **Reiter statt einer langen Bahn**: `.settings-layout` trägt links
  die Liste `.settings-nav` (ab 700px eine 184px-Spalte, darunter eine
  waagerecht scrollende Leiste über dem Panel) und rechts `.settings-body` mit
  genau EINEM sichtbaren `.settings-category[role=tabpanel]`. Sechs
  aufgeklappte Kategorien untereinander waren beim Öffnen eine Wand — man
  musste scrollen, um überhaupt zu wissen, was es gibt.
  Reihenfolge: **Memory, Model behavior, Runs, Display, Connections, Account**
  (vorher: Experience, Connections, Model behavior, Account) — sie erzählt „was
  die Modelle über dich wissen → was du ihnen sagst → wie ein Lauf abläuft →
  wie das Ergebnis aussieht → Technik → Konto". Die bestehenden Control-IDs
  bleiben der JavaScript-Vertrag; nur die frühere Sammelkategorie Experience
  ist in Runs (`#runModeSetting`, seit 2026-09-30 statt `#agentModeSwitch`/
  `#autoConsensusToggle`) und Display (Theme, `#agreementDisplaySelect`) aufgeteilt.
  Die Reiter tragen die Sprache der Sidebar-Listen: flache Zeile, transparent
  im Ruhezustand, mindestens 44 px hoch, Hover und Auswahl sind ein Tint. Seit der
  Button-Stil opt-in ist (`.btn`, 2026-10-02), tragen die Reiter ihn schlicht
  nicht; eine Ausnahmeliste gibt es nicht mehr. Die Tints
  werden aus `--text-color` gemischt, **nicht** aus der Oberflächenskala: im
  Dark Mode ist `--raise` exakt der Modalhintergrund, ein Hover darauf wäre
  unsichtbar.
  Der Controller sitzt in `app-ui.js` (`window.App.settingsTabs`), folgt dem
  WAI-ARIA-Tabs-Muster (genau ein Reiter in der Tab-Reihenfolge, Pfeiltasten +
  Home/End dazwischen) und öffnet **immer auf dem ersten Reiter** — der zuletzt
  benutzte wäre clever, aber man findet Einstellungen über einen festen Ort.
  **Die Panel-Sichtbarkeit gehört ausschließlich diesem Controller.**
  `firebase.js` hat früher `style.display` direkt auf `#accountSettingsSection`
  gesetzt; ein Inline-Style hätte den Controller übersteuert. Es ruft jetzt
  `setTabAvailable("accountSettingsSection", …)` und schaltet damit nur den
  REITER frei. Verschwindet der aktive Reiter (Logout bei offenem Account-Tab),
  fällt die Auswahl auf den ersten verfügbaren zurück statt ein leeres Panel zu
  zeigen. Die Version steht in `.settings-footer` am Fenster, nicht im Body —
  dort stünde sie unter jedem einzelnen Panel.
  Das Settings-Fenster nutzt bis zu 960 × 760 px mit stabiler Höhe beim
  Reiterwechsel; Dynamic-Viewport-Höhe und Safe-Area-Abstände begrenzen es.
  Kopf, Navigation und Footer bleiben außerhalb des scrollenden Inhalts.
  Kurze Memory-Felder bilden bei ausreichend Inhaltsbreite zwei Spalten,
  Notiz und Aktionen bleiben über die volle Breite. Auswahl-/Aktionszeilen
  umbrechen bei Platzmangel; mobile Eingaben vermeiden Fokus-Zoom mit 16 px.
  Der Controller synchronisiert `aria-orientation` mit dem 700-px-Breakpoint
  und hält aktivierte Reiter im sichtbaren Navigationsausschnitt.
  Display → `#consensusHighlightsSelect` steuert Antwort- und Quellenmarkierungen
  browserlokal über `consensio.consensusHighlightMode.v1`: `all`,
  `contradictions` (inklusive grauer Detailwidersprüche), `concerns`
  (Default: kritische Widersprüche, Split-Claims und auffällige/unklare Quellen)
  oder `critical` (kritische Widersprüche). Fachliche Optionsnamen und ein
  umbrechender Hilfetext erklären die Farben. Bestehende explizite Auswahlen
  bleiben erhalten; fehlende/ungültige Werte fallen auf `concerns` zurück.
  „No highlights“ verwendet weiterhin `consensio.showConsensusMarkers.v1`.
  `consensus-insights.js` setzt `body[data-consensus-highlight-mode]`; CSS
  filtert damit auch später eintreffende `data-source-check`-Markierungen auf
  Quellenlinks. `concerns` zeigt `contradicted`, `issue`, `unknown`; die beiden
  Widerspruchsfilter zeigen bei Quellen nur `contradicted` (keine eigene
  Schwere-Einstufung bei Quellen). Links und detaillierte Prüfergebnisse
  bleiben zugänglich. Satzfilter und Passage-Tabstopps werden beim Rendern
  direkt auf den Antwort-/Fallback-Containern synchronisiert, auch bevor ein
  archivierter Turn in den DOM eingefügt wird; Folgeanfragen blenden deshalb
  keine zuvor ausgefilterten Claims vorübergehend ein.
  Satzfilter gelten auch für archivierte Turns und
  Fallback-Claims (`data-coverage`); `.is-marker-filtered` entfernt dabei
  Stil, Badges und unsichtbare Passage-Aktionen ohne Text-/Datenverlust.
  Der Difference-Typ, nicht allein Grau, unterscheidet Detailwidersprüche
  von Emphasis/Thin. Es gibt keine separate Legende oder Hide/Show-Aktion
  unter der Antwort mehr; die Einstellung liegt ausschließlich unter Display.
  Die Display-Einstellung `#agreementDisplaySelect` speichert ihre
  browserlokale Wahl unter `consensio.agreementDisplay.v1` und kennt drei
  Stufen: `full` (Standard), `summary` — die Body-Klasse
  `.agreement-score-hidden` nimmt nur die Zahl samt Messbalken, qualitative
  Einordnung und Widerspruchshinweise bleiben sichtbar — und `off`, wo
  `.agreement-verdict-hidden` den ganzen Urteilsbereich in Live- und
  archivierten Consensus-Füßen entfernt, samt Haarlinie darüber; unter der
  Antwort bleiben dann nur die Schubladen (Differences / Answers / Sources).
  In dieser Stufe wird der Live-Fuß ab 641px zu einem `flex-wrap`-Streifen
  (Schubladen `order:1`, Lauf-Fakten `order:2`, Share/Watch/Cite `order:3`),
  damit die Schubladen neben die Aktionen rücken statt eine Zeile tiefer unter
  eine halbleere zu wandern. Bewusst kein drittes Grid-Raster mit fester
  Media-Query: ob die drei nebeneinander passen, hängt an der Zahl der Chips
  und der Länge der Lauf-Fakten — passt es nicht, bricht die Aktionsgruppe von
  selbst um. Die Fakten-Hülle bekommt `flex: 0 1 auto` und wird per `:has()`
  ausgeblendet, wenn sie weder Fakten noch ein sichtbares „Run again" trägt;
  mit `flex-grow` bzw. als leere Hülle hat sie die Aktionen sonst grundlos in
  den Umbruch gedrängt. Das Handy behält sein gestapeltes Raster.
  Der Vorgängerschlüssel `consensio.showAgreementScore.v1` wird weiter gelesen
  (`false` = `summary`) und mitgeschrieben, damit ein Rollback dieselbe Wahl
  sieht.
  Die Usage-Gruppe zeigt zusätzlich das aktive Watch-Kontingent aus
  `/api/my/watches`. Gesperrte Features zeigen einen kurzen Hinweis ohne
  Unterbrechung; der Sidebar-Link „Early access“ (seit 2026-10-02 ein
  Textlink in der Tarifzeile `#accountPlanLine` unter der Adresse
  `#accountIdentity`, die dasselbe Konto-Menü öffnet wie das neutrale
  Kürzel; firebase.js füllt die Adresse, user-tier.js `#accountPlanName`)
  öffnet die allgemeine Erklärung
  mit Kontaktmail und Hinweis auf spätere bezahlte Angebote. Verhalten und
  Modulvertrag stehen unter **Auth / Usage / Tier**.
- **User Memory (`user-memory.js`, `memory-edit.js`, `app/services/user_memory.py`,
  `app/services/memory_edit.py`, seit 2026-08-17)** —
  ein **selbst geschriebener** Kontext aus Kurzprofil (`role`, `focus`, `style`,
  `constraints`), großer Freitext-Notiz `notes` und Schalter `enabled`, der
  jedem `/ask_*` vorangeht. Die Notiz ist eine nutzerkontrollierte Notebox für
  importierte Erinnerungszusammenfassungen: sie ändert sich nur durch das
  Settings-Formular oder eine explizit abgesendete **Remember**-/
  **Correct memory**-Aktion.
  Im interaktiven Fan-out teilt `load_profile_text(..., run_key=usage_run_key)`
  pro UID/Run/Repository/Zeichenlimit einen prozesslokalen Snapshot (120 s,
  höchstens 256 Einträge inklusive laufender Reads). Parallele Aufrufe teilen
  denselben Read; Fehler werden nicht gecacht. Neue Runs und Einstellungen
  lesen frisch; Profil-Edits verändern keinen noch gültigen Run-Snapshot.
  Profil-/Account-Löschung invalidiert lokale Snapshots samt laufenden Reads.
  Erster Reiter der
  Einstellungen (`#memorySettingsSection`) — Prominenz kommt aus der Position,
  nicht aus Sondergestaltung; das Panel hat keine eigene Optik mehr.
  Im Panel stehen eine Zeile Erklärung, der Schalter, die vier kurzen
  „About you“-Felder, die große „Saved memories“-Textarea und die Aktionen;
  die vollständige Begründung liegt zugeklappt in
  `<details class="settings-note">` („How it works"). Die erste Fassung hatte
  Absatz + vier Aufzählungspunkte vor den Eingabefeldern — eine Textwand vor
  dem eigentlichen Formular. Die Zeichenzähler erscheinen erst ab 80 % der
  Feldgrenze (`data-near`), vier dauerhafte „0/250" wären vier Zahlen ohne
  Aussage. Es gibt weiterhin **keine automatische Ableitung** aus Antworten;
  Remember/Correct memory braucht eine markierte Aussage plus ausdrückliche
  Nutzereingabe. Den früheren Memory-Button neben **Senden** („Save to Memory
  instead of asking“, `#rememberDraftButton`) gibt es seit 2026-08-17 nicht mehr:
  ein zweiter Weg ins Gedächtnis am Composer war überflüssig neben der
  Textauswahl. „Remember“ speichert einen Fakt neu oder gleicht genau eine
  eindeutig verwandte bzw. widersprüchliche Passage ab, „Correct memory“ ist
  der gezielte Korrekturpfad.
  Drei Grenzen sind Vertrag, nicht Sparmaßnahme:
  1. **Deckel** 250 Zeichen je Kurzfeld; `notes` ist serverseitig aus
     `app_config/models.memory_edit` je Stufe begrenzt (12.000 Free,
     18.000 Plus, 24.000 Pro; Plus wird beim Speichern zwischen Free und Pro
     eingeklemmt). Der Text
     geht allen sechs Modellen **identisch** voran und ist damit ein gemeinsamer
     Bias: je mehr davon, desto ähnlicher die Antworten und desto höher der
     Agreement-Score, ohne dass die Modelle sich einiger wären. Dieselbe
     Überlegung hat `differences_data` aus dem Chat-Kontext entfernt (§
     `chat_context.py`).
  2. **Form statt Inhalt.** Der Rahmen (`ABOUT THE USER … END OF USER PROFILE.`)
     sagt ausdrücklich, dass das Profil beeinflusst, WIE geantwortet wird, nie
     WAS wahr ist: „the question and the evidence win".
  3. **Nur im interaktiven Lauf.** Injiziert wird ausschließlich in `handle_ask`
     (wie der Follow-up-Kontext). Watch-Reruns, Publisher- und Topic-Läufe rufen
     `engines.py` direkt und sehen das Profil nie — eine Watch-Baseline muss mit
     der Welt driften, nicht mit dem Profil ihres Besitzers. Judge/Differences
     und Share-Snapshots bekommen es ebenfalls nicht.
  Reihenfolge im Prompt: Basisanweisung → Profil → darum herum der Chat-Kontext
  (`build_chat_context_system_prompt` legt Kontext nach vorn, Anweisung nach
  hinten). Das Profil steht damit bei der stehenden Anweisung, nicht im
  Datenteil. `use_memory: false` im Request überspringt es für genau einen Lauf.
  Jeder eingeloggte interaktive `/ask_*`-Lauf erhält außerdem unabhängig vom
  Profil-Schalter eine kurze Read-only-Grenze: Antwortmodelle dürfen weder
  behaupten noch andeuten, persönliche Informationen gespeichert, geändert
  oder für künftige Requests vorgemerkt zu haben. Dieselbe Negativregel steht
  im Consensus-Prompt. Schreiben kann ausschließlich der explizite
  Memory-Endpoint; Watch, Publisher und Topics bleiben weiterhin außerhalb.
  Speicher: `users/{uid}/memory/profile` (Schema v2; alte v1-Dokumente ohne
  `notes` bleiben kompatibel), Write transaktional hinter
  `persistence_guard`, Löschung über `_delete_user_subcollections` (die
  Subcollection `memory` steht dort — fehlt sie, überlebt das Profil das
  gelöschte Konto). `sanitize_profile` ebnet Whitespace ein, kappt je Feld und
  entfernt Prompt-Rahmenmarken (sonst könnte ein Feld den Chat-Kontext-Rahmen
  vorzeitig schließen). `load_profile_text` ist fail-open: ein nicht lesbares
  Profil loggt und lässt den Lauf ohne Profil weiterlaufen. Die vier Kurzfelder
  werden whitespace-normalisiert; `notes` bewahrt Absatz-/Listenstruktur.
  Endpunkte `GET`/`PUT /api/my/memory` (users.py). `GET` liefert zusätzlich
  `revision`; `PUT` verlangt `expected_revision` (Compare-and-swap in derselben
  Transaktion wie der Tombstone-Check). Weicht die gespeicherte Revision ab
  (zweiter Tab, Remember/Correct, Undo), antwortet der Server 409
  `{error_code: revision_conflict, revision}` ohne Inhalte; `user-memory.js`
  behält den Entwurf und bietet „Load latest“ oder bewusst „Keep my draft“
  (übernimmt die gemeldete Revision für den nächsten Save). Alte Clients ohne
  `expected_revision` erhalten 409 mit Reload-Hinweis statt still neuere Inhalte
  zu überschreiben; das Bewahren fehlender Legacy-`notes` bleibt für interne
  Aufrufer erhalten. Ein Reload nach Remember/Correct/Undo
  (`load(true, {keepDraft: true})`) überschreibt einen ungespeicherten
  Settings-Entwurf nicht. Der Schalter speichert immer
  den zuletzt **gespeicherten** Textstand und lässt den Entwurf in den Feldern
  unberührt — sonst committet oder verwirft ein Klick nebenbei einen halb
  getippten Satz. Kein `localStorage`-Spiegel: das Profil lebt am Konto.
  Gelesen wird **erst beim Öffnen der Einstellungen**, nicht beim Login:
  `consensio:auth-state` feuert bei jedem Seitenaufruf eines eingeloggten
  Kontos und verwirft dort nur den gemerkten Stand (nachgeladen wird sofort,
  wenn das Fenster gerade offen steht — sonst zeigte es das Profil des vorigen
  Kontos). Sonst hinge an jedem Seitenaufruf ein Firestore-Read für ein Panel,
  das die meisten nie öffnen.
  `memory-edit.js` bietet nach einer Textauswahl in aktiver/archivierter
  Frage, Consensus (`#consensusAnswerBody`, `#agentAnswerBody`,
  `.thread-history-answer`) oder Modellantwort das app-native Kontextmenü **Ask about
  this | Remember | Correct memory** an (die erste Aktion gehört
  `composer-quote.js` und braucht kein Konto; ohne Konto bleiben die beiden
  Memory-Aktionen samt Trenner weg). Der Dialog besitzt Quellvorschau, Fokusfalle,
  Escape-/Backdrop-Schließen, zustandsabhängige Copy und einen gemeinsamen
  Undo-Toast; mobil erscheint er als Bottom-Sheet. `POST /api/my/memory/edit`
  akzeptiert `client_request_id`, Quelltyp, markierten Text, `intent=add|correct`
  und höchstens das konfigurierte Feedback-Limit; die explizite Eingabe ist die
  Freigabe, es gibt keinen zweiten Bestätigungsschritt. Vor dem Luna-Call
  reserviert `FirestoreMemoryEditRepository` transaktional UID-/UTC-Tag-,
  Minuten- und globales UTC-Tagesbudget sowie einen exklusiven In-flight-Lease.
  Der Provider läuft außerhalb der Transaktion, ohne Retry, mit konfiguriertem
  Timeout, `reasoning.effort=none`, Output-Cap und strikt strukturiertem
  `{operation,target,replacement}`. Bei `intent=add` darf Luna entweder einen
  neuen Eintrag anhängen oder die kleinste eindeutig vorkommende, verwandte
  bzw. widersprüchliche Passage ersetzen. Der Prompt verpflichtet den Replace,
  alle nicht widersprochenen Details im Target zu erhalten; `delete` weist der
  Server in diesem Modus ab. Ohne klaren Bezug wird angehängt. Bei
  `intent=correct` bleibt der sichere Append-Fallback erlaubt, wenn keine
  eindeutige Passage existiert.
  Der Server erlaubt insgesamt nur `replace|append|delete`,
  genau drei Felder, höchstens eine kurze Passage und bei Replace/Delete genau
  ein Vorkommen von `target` im aktuellen Memory.
  Die gepinnte OpenAI-SDK-Version `1.63.2` besitzt noch keine `responses`-
  Resource; `request_memory_patch` nutzt deshalb kompatibel denselben
  `/v1/responses`-Endpunkt direkt über `httpx`, weiterhin mit hartem Timeout
  und ohne Transport-Retry. Neuere SDKs laufen über `client.responses.create`.
  Commit und Account-Deletion-Fence teilen eine Transaktion; eine geänderte
  Ausgangsrevision ergibt 409.
  Requests liegen content-frei gehasht in derselben `memory`-Subcollection,
  Revisionen enthalten den exakten Vorzustand. `POST /api/my/memory/undo` kann
  ihn innerhalb 60 Sekunden nur ohne zwischenzeitliche Änderung wiederherstellen.
  Sinkt das aktuelle Notizlimit unter die gespeicherte Länge, lehnen Patch und
  Undo mit `memory_limit` (HTTP 422) ohne Profil-/Revisionswrite ab; eine Änderung
  eines anderen Feldes darf bestehende Notizen niemals still kürzen.
  Der vollständige Vorzustand (`before`) wird 30 Tage nach dem Edit vom
  stündlichen Retention-Loop (`cleanup_memory_edit_records`) entfernt; die
  inhaltsfreien Status-/Revisionsfelder bleiben bis zur Kontolöschung für
  Idempotenz, `undo_expires_at` wird dabei zu `undo_closed_at` (Query-Ausstieg,
  wiederholbar). Jede Reservierung trägt `lease_nonce` und `lease_until`
  (≥ Provider-Timeout + 15 s); `apply_patch`/`fail` schreiben nur mit passender
  Nonce, ein verspäteter Altworker erhält `lease_lost`. Wiederholt der Browser
  dieselbe `client_request_id` nach abgelaufener Lease, übernimmt der Server den
  Auftrag einmal unter neuer Nonce (UID-Tages-/Minutenquote nicht erneut,
  globales Provider-Budget für den echten Zusatzcall schon); ein zweiter
  Abbruch bzw. ein nie wiederholter Auftrag endet über Retry oder Retention
  terminal als `failed/interrupted` (HTTP 409) und gibt die In-flight-Lease frei.
  Idempotente Wiederholungen rufen Luna nie erneut auf. Provider-begonnene
  Fehler bleiben budgetiert.
  `memory-edit.js` bindet Auswahl, Dialog, Request und Undo-Toast an
  `{uid, App.authState.generation}`: ein Kontowechsel schließt Dialog und Toast,
  verwirft Auswahl/Request-ID und bricht den Fetch ab; vor dem Absenden sowie
  nach Token, Fetch und JSON wird die Bindung geprüft, sodass eine späte Antwort
  weder das Memory des neuen Kontos neu lädt noch dessen UI einen alten
  Undo-Hinweis zeigt. Tokenrefresh desselben Kontos bleibt unberührt. Memory-Inhalte erscheinen weder in Logs noch
  Metriken/Alerts. Watch, Publisher, Topics, Judge und Shares bleiben außerhalb.
- **`math-render.js`** — gemeinsame KaTeX-Brücke für App und öffentliche
  Share-/Watch-Seiten. Bewahrt `\[...\]`/`\(...\)` durch den Markdown-Pass und
  exponiert `window.ConsensusMath.{prepareMarkdown,stripMath,render}`.
  Innerhalb einer Formel ist Markdown Notation, kein Markup: Backslashes und
  alle ASCII-Satzzeichen werden geschützt; insbesondere bleibt ein einzelnes
  `=` in mehrzeiligen Formeln Formelinhalt statt Setext-Überschrift. Derselbe
  Schutz gilt serverseitig in `public_markdown.py` für Share-/Watch-Seiten.
  Ohne Escape-Schutz verschluckt `17{,}5\%` → `17{,}5%` als
  TeX-Kommentar das Ergebnis. `$...$` wird nur dann als Formel gelesen, wenn
  der Inhalt ohne Leerzeichen an beiden Dollarzeichen liegt, in einer Zeile
  bleibt und ein LaTeX-Signal trägt — „6,7 Mrd. $ in Q1“ bleibt Betrag.
  `stripMath()` liefert die formelfreie Fassung eines Satzes; die Ankersuche
  braucht sie, weil eine gerenderte Formel im DOM ein übersprungener
  `.katex`-Block ist, der Anker aber den LaTeX-Quelltext trägt.
  `wrapBareLatex()` repariert die Anzeige gespeicherter Anker aus älteren
  Läufen, in denen die Zeile *zwischen* den `$$` als eigener „Satz" landete:
  nur wenn außer LaTeX nichts im Anker steht, wird er nachträglich als Formel
  gesetzt — ein einziges Wort Text lässt ihn Text bleiben.
- **`markdown-stream.js`** — Markdown-Rendering (`injectMarkdown`) + SSE-Helfer
  (`createStreamRenderer`, `streamSSERequest`); setzt LaTeX nach jedem
  gedrosselten Streaming-Render über `window.ConsensusMath`. Fehlt `marked`
  oder `DOMPurify` nach einem Asset-Ladefehler, rendert es sicher als Plaintext
  und meldet den degradierten Zustand, statt eine Promise-Rejection auszulösen.
  `injectMarkdown(el, md, evidenceSources?)` akzeptiert optional turnbezogene
  Quellen; ohne dritten Parameter gilt weiter `window.currentEvidenceSources`.
- **`sources.js`** — Quellen/Evidence-Mapping; nutzt DOM-Datasets
  `dataset.consensusAnswer` / `dataset.consensusSources`; `window.currentEvidenceSources`.
  Zwei Darstellungen: **im Chat-Fliesstext** (Container ist bzw. liegt in
  `#consensusAnswerBody`, `.consensus-answer-body` oder der Kernaussagen-Liste)
  werden `[S3]`-Tags seit 2026-10-01 zu **Quellen-Pillen** `.src-ref` statt
  hochgestellter Zahlen (User-Entscheidung): Favicon (14 px, über den eigenen
  Proxy `/api/topics/favicon`, kein Drittanbieter im Browser) + kurze Domain
  ohne `www.` auf der Grundlinie, `--well`-Fläche, Radius voll, lange Domains
  mit Ellipse. Scheitert das Favicon, ersetzt ein neutrales Monogramm
  `.src-ref-glyph` das Bild. Benachbarte Tags (`[S1, S2]`, `[S1][S2]`) werden
  **eine** Pille „uci.org +2“ (`.is-group`, `data-source-numbers="1 2 3"`);
  `aria-label` lautet „Source: uci.org (and 2 more)“. Steht die Domain direkt
  vor dem Tag schon im Text, zeigt die Pille nur das Favicon (`.is-compact`) —
  der Prosatext selbst bleibt unverändert, weil Anker und Claim-Marken ihn
  wörtlich suchen. Die Nummer bleibt am Element (`data-source-number`, aus der
  expliziten Quellen-ID `S3` → `3`, unabhängig von Sortierung oder Lücken in
  `window.currentEvidenceSources`); `sourceData`/`sourceGroup` tragen die
  aufgelösten Quellen des Turns. Nur alte Einträge ohne ID verwenden den
  Positions-Fallback; fehlende oder mehrdeutige explizite IDs erhalten keine
  Domain (Pille „Source 9“ ohne Link). Dieselben IDs stehen in
  `#consensusSourcesList`
  (`app-init.js::renderEvidenceSources`, geoeffnet ueber den Quellen-Chip).
  In den Modellantworten bleiben es die Favicon-Chips `.source-link`.
  Agent-Antworten verwenden separat `window.linkifyAgentSources`: sichere
  HTTP(S)-Links und eindeutig auflösbare `[S#]`-Tags werden zu denselben
  Pillen mit Quellenvorschau; nebeneinanderstehende Pillen (nur Leerraum,
  Komma, Semikolon dazwischen) fasst `mergeAdjacentSourceRefs` zusammen. Die
  Nummern entsprechen der deduplizierten Quellenliste des jeweiligen Turns
  bzw. der Einzelantwort. Benannte Links behalten ihren Text; ein Linktext,
  der nur die eigene Domain wiederholt (`[njaped.no](https://njaped.no/)`),
  wird durch die Pille ersetzt statt verdoppelt. Ausgeschriebene URLs und
  reine Zitat-Klammern („(url1, url2)“) entfallen samt Klammer. Code, Formeln
  und reine Zahlennotation wie `[1]` bleiben unberührt. Die Umwandlung betrifft
  nur den DOM, nicht Markdown oder Review-Hash; `agent-review.js` liest die
  Quellen einer Pille über `sourceGroup` zurück.
  Hover/Fokus auf `.src-ref` oeffnet `#sourceTeaser` (Favicon, Host, Titel,
  Snippet, Prüfstatus); bei einer Gruppen-Pille eine Zeile je Quelle. Klick
  öffnet wie bisher die (erste) Quelle bzw. bei geprüften Zitaten die
  Prüfergebnisse. Quellenprüfung (`source-verification.js::mark`) bindet an
  eine Gruppen-Pille je Nummer ein Urteil (`checks`-Map) und färbt sie nach
  dem schwersten. Copy consensus/Copy citation lesen Pillen über
  `window.App.sourceRefs.plainText/urls` („ (uci.org, pcs.com)“). Share- und
  Topic-Seiten rendern serverseitig aus Markdown und sind nicht betroffen.
  `normalizeTerminalSourceTagOrder` korrigiert Modell-Output der Form
  `Aussage [S1].` zu `Aussage.[S1]`, damit die Quellen-Pille nach
  Satzendzeichen (und ggf. schliessendem Anfuehrungszeichen) steht. Der
  DOM-Linkifier besitzt denselben Fallback fuer alte Bookmarks; das
  serverseitige Pendant liegt in `app/services/public_markdown.py`. Fuer alte
  Modellantwort-Bookmarks verschiebt `rewriteSourceTags` ausserdem einen
  eindeutigen, reinen `[S…]`-Block vor dem ersten Wort hinter die erste
  vollstaendige Aussage; der Consensus-Renderpfad ruft diese Reparatur nicht auf.
- **`attachments.js`** — Attachment-UI/Payload (ab Plus), inklusive Bild-Paste im
  Fragefeld und Drag-and-drop aller unterstützten Dateitypen auf den
  Input-Container. Bilder bis 15 MB werden vor der Base64-Kodierung auf
  höchstens 1568 px Kantenlänge als JPEG verkleinert; kleine Screenshots
  bleiben unverändert. Der Server wiederholt die Aufbereitung innerhalb
  seines 5-MB-Eingangslimits, prüft vor dem Dekodieren zusätzlich ein festes
  Pixelbudget und korrigiert bei einer JPEG-Konvertierung MIME und Dateiendung.
  Solange ein echter
  Anhang für die nächste Frage bereitliegt, wird DeepSeek temporär mit einem
  sichtbaren Kompatibilitätshinweis deaktiviert, weil dessen Chat-API keine
  Datei-/Bild-Inputs akzeptiert; `query-send.js` erzwingt dieselbe Sperre
  zusätzlich nach dem Tier-Refresh von `/prepare` und direkt beim
  Request-Fan-out. Der Auswahl-Restore darf den dabei deaktivierten Provider
  nicht reaktivieren. Nach Entfernen wird die vorherige Auswahl
  wiederhergestellt. **Seit 2026-08-07 gibt der Composer seine Anhänge beim
  Senden ab** (User-Vorgabe: „Anhänge sollten nicht nach dem Senden im
  Chatfenster hängen, sondern an der Nachricht"): `detachForMessage()` leert
  `window.pendingAttachments` und liefert die Metadaten, die
  `window.App.setThreadQuestionAttachments` als statische Chips unter die
  gesendete Frage (`#threadAskAttachments`) hängt; beim Archivieren wandern sie
  mit dem Turn in `#threadHistory`. Eine Folgefrage schickt die Datei damit
  NICHT erneut mit — wer sie wieder braucht, hängt sie wieder an. Bookmark-
  Anhänge (`showBookmarkAttachments`) landen aus demselben Grund an der
  wiederhergestellten Frage statt im Eingabefeld. Im Agent-Modus bleibt die
  Datei im Chat gespeichert: Chips mit Datei-`id` sind klickbar und öffnen die
  Vorschau mit Download/Entfernen (siehe Abschnitt Agent-Dateien).
  Jeder Import gehört zu einer Entwurfs-Generation: `clearPendingAttachments`,
  `detachForMessage` und `consensio:auth-state` beginnen eine neue, verwerfen
  verspätete FileReader-/Verkleinerungsergebnisse und setzen den
  Pending-Zähler zurück, sodass eine alte Datei weder im nächsten Entwurf
  auftaucht noch dessen Dateilimit belegt.
  `window.App.attachments.isImporting()` meldet laufende Imports;
  `window.sendQuestion` (Vergleich und Agent) sendet währenddessen nicht und
  zeigt einen Hinweis.
  `window.pendingAttachments`, `getAttachmentsPayload`,
  `window.App.attachments.{detachForMessage,messageMeta,renderMessageAttachments}`.
  `messageMeta()` liefert dieselben Metadaten, ohne die Dateien abzugeben: die
  Blase der gerade abgeschickten Frage (`#threadPendingAsk`) zeigt die Chips
  schon, waehrend der Composer die Daten noch haelt — ein Lauf, der nicht
  stattfindet, gibt Text UND Anhänge unveraendert zurueck. Solange sie schwebt,
  blendet `body.thread-message-pending` den Composer-`#attachmentBar` aus,
  damit dieselben Chips nicht zweimal dastehen.
- **`run-mode.js`** (Head-Bundle, vor `app-bootstrap.js`) — **einzige Quelle**
  der Moduswahl Compare / Consensus / Agent; siehe „Modus: Compare, Consensus,
  Agent". Kein DOM; `agent-mode.js` rendert den Wähler.
- **`agent-mode.js`** — gruppiertes Lauf-Panel (Status-Hub, Timer; die Namen
  „agent-mode" sind historisch und meinen den Consensus-Lauf, nicht Agent Beta),
  der Moduswähler `#runModeSelect` samt Settings-Spiegel `#runModeSetting` und
  die Composer-Werkzeugleiste `#composerModeBar` direkt unter dem Input:
  Quellenprüfung (nur Consensus/Agent), Reasoning (`#composerReasoningToggle`), Upload-Shortcut und
  Anbieter-Favicons der nächsten Frage.
  Die Leiste gehört in jedem Modus und jeder Breite zum Startbildschirm (Hero
  oder Compare-Start mit leeren Antwortkarten, `App.composer.isStartScreen()`).
  In einem Chat stehen die Werkzeuge im (+)-Menü; nur solange ein Direktvergleich
  auf dem Schirm steht, bleibt die Leiste angedockt (`data-docked="true"`) als
  reine Statuszeile ohne Werkzeuge. Sie
  schließt ohne Abstand unter dem Input an und ist seitlich um 12 px eingerückt.
  Sie bleibt auf Desktop und Mobile eine einzelne 36-px-Zeile. Die Erklärung
  ist am Modusschalter als Tooltip/Screenreader-Beschreibung verfügbar;
  die doppelte Modellzahl entfällt und mobil zeigt der Bereitschaftsstatus die Kurzform.
  Reasoning und Upload nutzen per Klick die bestehenden Controls
  (`#reasoningToggle` ohne Gate, Upload mit Plus-Gate). Mobil sind beide reine Icon-Buttons. Ein auf Hero-Wechsel
  begrenzter Body-Observer synchronisiert Chatstart und „New comparison“
  samt Anhangsplatzierung.
  Unter 700px tatsächlicher Leistenbreite kürzt eine Container-Query die Werkzeuglabels,
  auch neben dem angedockten Reader auf Desktop. Einen eigenen Status-Chip im
  Input gibt es seit 2026-10-02 nicht mehr (früher `#deepThinkInputIndicator`).
  Die Modell-Favicons überlappen leicht wie ein Icon-Stapel.
  Beim Einblenden erscheinen Opazität und 5-px-Versatz über 260 ms; bei
  `prefers-reduced-motion` entfällt die Animation. Der lange Folgeturn-Hinweis
  `#modeNotice` ist entfernt, damit die Leiste kompakt bleibt.
  `window.App.renderComposerMode()` synchronisiert sie mit Settings/Plus-Menü;
  `answerReader.directSummary()` liefert separat die Bereitschaft des sichtbaren
  Direktvergleichs (auch Bookmarks und Fehler). Der Leser aktualisiert die Leiste
  bei Projektion/Reset und blendet seinen bisherigen Direktvergleich-Header aus.
  `composer-collapse.js` lässt Klicks auf die Modusleiste auch eingeklappt direkt durch.
  Die bestehende Kopplung bleibt die einzige
  Stelle, die den Auto-Consensus-Toggle erzwingt/sperrt. `setAgentModeStatus`
  verwaltet weiterhin jeden Modelllauf, reicht Statusereignisse aber nur im
  Agent Mode an die gefuehrte Consensus-Pipeline weiter.
  Seit 2026-07-27 ist das Panel `#agentModePanel` als **Fortschrittsanzeige
  stillgelegt** (in `shell.css` auf `display:none`): zwei Progress-UIs fuer
  einen Request waren genau der Ueberschuss, den der gefuehrte Lauf abbaut.
  Agent Mode gruppiert Modelle, steuert Auto-Consensus und erklärt den Modus
  an der Composer-Leiste. Der session-lokale
  „Compare answers/Hide answers"-Disclosure (`#agentModeAnswersRow`) ist ins Markup
  der Provenance-Zeile gewandert — agent-mode.js adressiert ihn unveraendert
  per `getElementById`, die Position ist kein Vertrag. Sie gilt nur fuer fertige
  Agent-Mode-Ergebnisse: `.agent-mode-enabled:not(.agent-mode-show-answers)`
  blendet dort die Antwortboxen aus. Im Direktvergleich zeigt der gemeinsame
  Leser alle ausgewaehlten Modellantworten; die alten Boxen bleiben Renderziele. Sobald der fertige Consensus-Fuss sichtbar ist, bleibt
  `#agentModeAnswersRow` immer vorhanden; er haengt nicht mehr an einer
  fehleranfaelligen Erkennung aktiver/abgeschlossener Modellboxen.
  Vorher war der Schalter an den Agent Mode gebunden und damit in zwei von
  drei Faellen unsichtbar, obwohl er das Wichtigste dahinter oeffnet.
  Seit 2026-07-28 haengt an diesem Disclosure auch die **Vorschau-Klammer** der
  Antwortboxen (`syncAnswerPreviews`): statt sechs eigener Innen-Scrolls
  (`.collapsible-content` mit `max-height` + `overflow-y`) bekommen
  ueberlaufende Boxen `.is-clamped` (gleiche Hoehe, Ausblendkante) plus einen
  `.response-answer-more`-Knopf; geklappt wird nur, was wirklich ueberlaeuft,
  und nie waehrend des Streams (`is-streaming` / `dataset.responseState`).
  Die Nutzerentscheidung steht in `dataset.answerOpen` und wird beim naechsten
  Lauf verworfen. (Die frühere Falle, ihn aus einem globalen
  Button-Selektor auszunehmen, entfällt seit `.btn` opt-in ist.)
  **Folgefalle:** wer den Text einer Antwortbox liest, muss `textContent`
  nehmen — `innerText` liefert fuer `display:none` den leeren String. Die
  Zaehlung in `consensus-lifecycle.js`, die Zitations-Modelle in
  `consensus-run.js`/`consensus-actions.js` und `isBoxDone` in
  `consensus-progress.js` sind entsprechend umgestellt.
  Seit **2026-08-31** ist die globale Stream-Fortschritts-Bruecke
  (`--stream-progress`, der 120-ms-Agent-Ticker und
  `window.App.agentMode.streamProgressByResponseId()`) **entfallen**.
  `consensus-progress.js` berechnet die visuellen Modell-Balken stattdessen
  lokal aus dem sichtbaren Antwortstream, haelt sie innerhalb eines Laufs
  monoton und setzt sie erst beim terminalen Modellstatus auf 100 Prozent.
  Seit 2026-08-31 zeigt die Moduswahl **immer die Einstellung fuer die
  naechste Nachricht** (heute `App.runMode`), nie den projizierten Lauf.
  Die Body-Klassen (`agent-mode-enabled` &c.) folgen weiterhin dem Lauf auf
  dem Schirm. In Compare gibt es keinen Folgeturn, jede Frage ist ein
  eigener Lauf — `isArmed()` in `consensus-run.js` prueft
  `App.runMode.pipeline()`, damit der Platzhalter kein Follow-up verspricht.
- **`consensus-progress.js`** — der **gefuehrte Lauf** `#consensusRun` unter dem
  Input, seit 2026-07-27 die **einzige** Fortschrittsanzeige (auch im Agent
  Mode; dessen Panel ist als Progress-Flaeche stillgelegt, siehe unten) — und
  seit **2026-08-31 nur noch im Agent Mode ueberhaupt**: im Direktvergleich
  gibt es keinen Ablauf anzukuendigen (sechs Antworten, danach nichts), also
  keinen Block. Gesperrt an zwei Stellen: `run-view.js::syncPipeline` ruft die
  Pipeline bei `agentMode === false` gar nicht erst, und `isDirectComparison()`
  (Body-Klasse `direct-comparison-active`) haelt `show()`/`onPrepare`/
  `onQueryStatus` auch gegen fremde Aufrufer zu (Lifecycle, Demo, Replay).
  Vier Phasen in dieser Reihenfolge: `prepare → answers → consensus →
  differences`, genau eine aktiv. Seit **2026-09-30** ist der Block eine
  ruhige Karte mit Stepper-Kopf (`#runSteps`, je `li.run-step[data-step]`
  mit `data-status="done|active|pending"`; erledigt = Haken, aktiv =
  pulsierender Punkt, offen = leerer Kreis), rechts `#runMeta`
  (`Preset · N models`, gesetzt beim Fan-out) und die Uhr `#runTime`. Die
  frueheren grauen Haken-Zeilen (`#runPast`), die Taetigkeitszeile
  (`#runLabel`, drei Striche, Textschimmer) und die `Next: … → …`-Zeile sind
  entfallen: der Stepper nennt alle Schritte zugleich. Die Dauer der
  Antwortphase steht als Tooltip am erledigten Schritt `answers`. Schmale
  Karten (Container-Query bis 600 px) zeigen statt des Steppers eine Zeile
  (`#runCompactLabel` + `#runCompactCount`) ueber vier Segmenten und darunter
  `#runMeta` plus `#runMetaNext`; 601–680 px ruecken das Preset unter die
  Schritte. Die Modell-Zeilen (`#runDetail`) existieren nur waehrend der
  Antwortphase: Status-Icon (Spinner/Haken/gestrichelter Kreis, ein SVG,
  CSS waehlt per `data-state`), Name, 4-px-Balken, reservierte Skip-Spalte
  und ein Wort Status rechts: `Writing`, `Thinking`, `Waiting`, bei Abschluss
  nur die **gemessene** Zeit (`12.3s`), terminal `No answer` (Fehler),
  `Skipped`, `Canceled`. Die Zeichenzahl pro Modell (seit 2026-09-11 samt
  260-ms-Zaehlanimation) ist wieder aus der Zeile entfernt und steht nur noch
  im Tooltip (`1,234 characters received so far`); gezaehlt wird weiter in
  Unicode-Codepoints aus dem projizierten rohen `dataset.consensusAnswer`,
  der Wert treibt ausserdem die Balkenschaetzung. Ohne Antworttext laufen
  `Thinking`/`Waiting` als wandernder Kurzbalken statt einer geratenen
  Fuellung; `Writing` fuellt monoton mit Lichtstreifen, erst der terminale
  Status setzt 100 %. Ausgefallene Modelle (`error|skipped|canceled`) sinken
  per `order` ans Ende, bekommen eine leere gestrichelte Schiene, und
  `#runNote` sagt es einmal ruhig: `Claude didn't answer. The consensus uses
  the other 5 answers.` (nur in Antwort- und Consensus-Phase; in
  `differences` steht dort der Hinweis auf das unbeteiligte Pruefmodell).
  Phasen ohne ehrlichen Prozentwert laufen indeterminiert
  (`.run-track.is-indeterminate`); waehrend des Fan-outs ist der Gesamtbalken
  ausgeblendet. Nur `#runStatus` ist eine Live-Region und wird bei Phasen-/
  Abschlusswechsel aktualisiert. `Skip` erscheint in der von Anfang an
  reservierten Aktionsspalte ohne Layoutsprung; die rechte Kante der
  Statusangaben stimmt mit der Uhr im Kopf ueberein. Bis 640 px stehen
  Icon+Name, Skip und Status ueber einem durchgehenden Balken (Touch: 44 px
  Zeilen- und Skip-Hoehe). Reduced Motion stoppt Puls, Spinner, Sweeps,
  Lichtstreifen und Uebergaenge; Forced Colors blendet den Balkenschimmer aus.
  `.run-model-track` teilt sich die Grundform mit `.agent-session-track` in
  der Agent-Sidebar, die ihre 2-px-Schiene in `agent-chat.css` selbst setzt.
  Die Landingpage (Szene 02, `landing-scenes.js` + `.lp-run*` in
  `landing.css`) spiegelt diesen Aufbau mit denselben Schritten, Wörtern und
  Zustaenden.
  Am Ende klappt der Block zusammen und uebergibt an den **Provenance-Fuss**
  `#runProvenance` unter der Antwort. Desktop: Differences / Answers / Sources
  bilden die primäre Zeile, Share / Watch / Cite stehen daneben. Eine zweite,
  zurückhaltende Zeile enthält Quellenstatus und Laufdetails. Bis 640 px
  nutzen die sichtbaren Navigationspunkte gleichmäßig die volle Breite;
  `.consensus-evidence-action` zeigt dort Icon und Anzahl über dem Kurzlabel
  mit mindestens 56 px hohen Touch-Flächen. Auf Desktop stehen die dezenten
  15-px-Icons vor dem Label, mit mindestens 44 px hohen Zielen. Die Gestaltung
  gilt auch für archivierte Turns aus `consensus-run.js` und
  `model-answer-reader.js::registerTurn`. Quellenstatus und Laufdetails
  (Modellzahl/Dauer) sind mobil ausgeblendet. Share/Watch/Cite wandern bis
  1099 px mit demselben DOM in den mobilen Header (siehe `mobile-header.js`);
  „Run again“ bleibt unten rechts. Die Header-Icons behalten 44-px-Ziele,
  aria-label und Tooltips.
  `.run-provenance` nutzt Grid mit Varianten für ausgeblendetes Verdict.
  Die stabilen Hosts `#consensusFooterTabs`, `#consensusFooterActions` und
  `.consensus-footer-facts` stehen direkt darin. Sichtbare Kurzlabels kommen
  weiterhin aus `data-short`; die vollständigen Namen bleiben für Screenreader.
  Der Status `#consensusSourceCheckStatus` liegt separat in
  `.consensus-footer-source-status` als `#consensusSourceCheckButton`. Dieser
  öffnet über `sourceVerification.openResults` bei v4 die konkrete Prüfbegründung
  in Differences: zuerst eine nicht abgeschlossene/ausgelassene Prüfung, sonst
  das erste Ergebnis. Nur die zugehörige Karte wird aufgeklappt; der Prüfbereich
  erhält Fokus, wird in Sicht gescrollt und für 2,8 Sekunden dezent hervorgehoben.
  Polling erhält den verbleibenden Hinweis, ein anderer Run/Antwortstand oder
  Clear entfernt ihn. Reduced Motion verzichtet auf Animation und sanftes Scrollen;
  Forced Colors nutzt einen Systemrahmen. Legacy-Prüfungen und v4 ohne gebundenes
  Einzelergebnis öffnen und markieren den Statusbericht in Sources.
  Sources referenziert den Status auch mobil per
  `aria-describedby`. Mobil zeigt `data-check-state` am Sources-Tab ein Häkchen
  nur bei vollständiger positiver v3-Prüfung; `!` bedeutet Quellenprobleme,
  `?` unklare/unvollständige oder technisch nicht verfügbare Ergebnisse. Der
  Statushinweis steht in `.consensus-tab-meta` neben der Anzahl, ohne die
  symmetrische Ausrichtung der Labels zu verschieben. Pending
  behält den Label-Schimmer. Ohne Prüfung bleibt das Icon leer; ein neuer Lauf
  setzt den Zustand zurück. Leere Statuszeilen und Status bei verstecktem Sources-Tab
  sind nicht sichtbar. Die Markierungserklärung und der Hide/Show-Button sind
  entfernt; ihre Aufgabe übernimmt Settings → Display.
  Der Run-again-Knopf setzt über `#newRunButton` den normalen Hero-/Composer-
  Ausgangszustand zurück und füllt die letzte Frage vor, sendet aber nicht
  automatisch. Eine Wiederholung ist ein
  **vollstaendiger zweiter Lauf** und kostet entsprechend Kontingent; seit
  2026-07-28 steht der Preis deshalb am Knopf (`#runReplayCost`, seit
  2026-10-01 „· about 8 % of today" statt „uses 1 run", ohne bekanntes Konto
  leer) und nach dem Klick bis zum Absenden ueber dem Eingabefeld
  (`#composerRunNotice`). Beides liest `labelRunAgain` / `prepareRunAgain` in
  `consensus-progress.js` aus `App.tokenBudget.runShare/canStart` — derselben
  Quelle wie der Ring; `consensio:token-budget` zieht das Label nach.
  Das Verdict bleibt unter der Antwort: Ampelfarbe auf der Agreement-Zahl,
  Headline mit dem schwerwiegendsten Thema, eine Meta-Zeile. Der Gauge
  (`.verdict-gauge`, Zahl /100 und Messbalken) ist weiterhin zentral in
  `components-consensus-insights.css` definiert. Die Footer-Hülle trägt keine
  Summary-Fläche; eine feine Unterkante trennt ein sichtbares Verdict von
  der Navigation. Full/Summary/Hidden beeinflussen ausschließlich das Urteil.
  Die Tabs bleiben rahmenlos mit Hover-/Fokus- und Offen-Zuständen.
  Der Footer erscheint bei `stage === "idle"|"done"|"differences"`;
  Quellen sind nach fertiger Synthese unabhängig von laufenden Judges zugänglich.
  Geschlossene Differences-/Sources-Panels nehmen keinen zusätzlichen Platz ein;
  geöffnete Panels behalten ihre interne Oberkante. Öffentliche Marketing-
  Mockups haben eigene Footer-Strukturen und werden durch diese App-Hülle
  nicht geändert.
  Beim Oeffnen fahren alle drei Disclosures ihren jeweiligen Inhaltsanfang
  nach dem Layout per sanftem `scrollIntoView({block:"nearest"})` an:
  Differences den Drawer, Sources den ersten Quellen-Eintrag und Compare
  answers die erste eingeschlossene Modellantwort.
  `onConsensusEnd()` rendert ihn auch ohne aktive Query-Pipeline (spaeter
  manuell gestarteter Consensus); `firebase.js::loadSingleBookmarkUI` tut
  dasselbe explizit fuer wiederhergestellte Bookmarks.
  Die strittigen
  Stellen werden aus den tatsaechlich gerenderten Marken gezaehlt, nicht
  separat gebucht; `consensus-insights.js` ruft dafuer nach dem Markieren
  `renderProvenance()` nach; `app-init.js::renderEvidenceSources` ebenso fuer
  den Quellen-Chip. Bruecke: `window.App.consensusPipeline.{onPrepare,
  onQueryStatus,onConsensusStart,onDifferencesStart,onConsensusEnd,
  renderProvenance,dismiss}`. `onPrepare` kommt aus `query-send.js` **vor**
  `/prepare`, `onDifferencesStart` aus dem ersten `differences.delta`
  (`consensus-run.js`).
- **Composer-Hoehe** — `composer-autosize.js` wird vor `app-init.js` geladen.
  `App.initComposerAutosize` installiert dessen bisherige Input-/Viewport- und
  Placeholder-Listener; `App.resizeQuestionInput()` bleibt der explizite Trigger.
  CSS-Min-/Maxhoehe bestimmen Wachstum und internen Scrollbereich. Mehrzeilige
  Eingaben behalten ihre Form bis zum Leeren. Ein ResizeObserver verfolgt zudem
  die tatsaechliche Feldbreite waehrend Sidebar-/Viewport-Transitionen und misst
  pro Animationsframe hoechstens einmal nach. Reine Hoehenmeldungen werden
  ignoriert, damit eigene Schreibzugriffe keine Schleife erzeugen. So bleibt
  nach einer schmalen Zwischenbreite kein ueberhohes leeres Feld stehen.
  `tests/js/composer-autosize.test.mjs` prueft diese Ereignisgrenzen; der Smoke-
  Browserfall prueft echtes Layout inklusive der abgeschlossenen Transition.
- **Hero ↔ Thread gleitet (2026-10-03)** — `.input-section` hat keine
  `transform`-Transition mehr: die Hero-Zentrierung `translateY(… - 50%)` liess
  das Feld bei jeder Höhenänderung und beim Ausstieg von falscher Stelle
  gleiten (beim Ausstieg von unterhalb des Bildschirms herauf).
  `App.glideComposer(change)` (app-core.js) misst das Feld vor dem
  Klassenwechsel, liest die neue Lage im nächsten Frame und animiert die
  Differenz per WAAPI-`translate` (420 ms); `exitHeroMode`,
  `enterDirectComparisonView` und „New comparison“ nutzen es. Die Agent-Demo
  tippt im Hero und verlässt ihn erst beim simulierten Absenden.
  `html { scrollbar-gutter: stable }` (shell.css) hält die Spalte beim
  Erscheinen der Scrollleiste still; die Agent-Spalte zentriert über `100%`
  statt `100vw` und steht damit exakt wie der normale Thread.
- **Thread-Layout: Composer unten (2026-07-27)** — ab dem ersten Lauf liest
  sich `/app` als Thread: Frage oben, Lauf, Antwort, Modellantworten, Composer
  am unteren Bildrand. Das DOM behaelt die Reihenfolge Input → Consensus →
  Responses (die Hero-Zentrierung rechnet damit); `shell.css` dreht sie nur
  fuer `body:not(.is-hero)` per Flex-`order` und macht `.input-section`
  zum letzten Flex-Abschnitt mit eigenem auslaufenden Horizont
  (`.consensus-section::before` ist in diesem Zustand aus). Die Frage steht im
  Thread-Kopf `#threadAsk` („Question“-Eyebrow + rechts stehender, aber
  linksbündig gesetzter Text, 3-Zeilen-Clamp mit
  „Show full question“): `window.App.setThreadQuestion` (app-core.js), gefuellt
  von `query-send.js` (send), `demo.js` (nach der Tipp-Phase) und
  `firebase.js::loadSingleBookmarkUI`; geleert von „New comparison“ und
  `clearResponseBoxes`. Der Text ist auf `max-width: 70%` begrenzt und nach
  rechts gerückt: User-Turn und linksbündige Antwort bleiben sofort
  unterscheidbar. Gesetzt wird er trotzdem linksbündig — rechtsbündiger
  Flattersatz über mehrere Zeilen liest sich schlecht (Befund 2026-08-14).
  Er liest sich in derselben Größe wie die Antwort (`--font-size-base`) und
  steht auf einer eigenen Blase (`--raise`, `--radius-lg`). Deren Innenluft ist
  ein **durchsichtiger Rahmen statt Padding**: `overflow: hidden` schneidet erst
  an der Außenkante des Paddings ab, sonst bliebe unter dem 3-Zeilen-Clamp ein
  angeschnittener Streifen der vierten Zeile sichtbar.
  Denselben Clamp und denselben „Show full question“-Link bekommt jede
  archivierte Frage im Verlauf (`.thread-history-question`, gebaut in
  `consensus-run.js::appendHistoryTurn`); der Klick-Handler in app-core.js
  hängt am `.thread-ask-more`-Knopf, nicht an einer festen ID. Die
  **Demo** laesst ihre Frage waehrend des animierten Laufs zusaetzlich im
  Composer stehen (echte Laeufe leeren ihn), damit der selbst getippte Text
  nicht mitten im Ablauf verschwindet. Nach der fertigen Antwort ersetzt bei
  Gaesten `#postDemoLoginPrompt` den ganzen deaktivierten Composer; die Frage
  bleibt im Thread-Kopf sichtbar. Der Composer wird beim Senden **geleert** —
  deshalb ist `window.lastQuestion` die Quelle fuer `getConsensus` und die
  Citation, nicht mehr `#questionInput`. **Seit 2026-08-15 sofort** (im Thread;
  der Direktvergleich leert weiter erst nach `/prepare`): zwischen Klick und
  dem Moment, in dem der Lauf den neuen Turn aufmacht, liegen `/prepare` und im
  laufenden Gespraech das Binden des Chat-Kontexts. Ab der dritten Frage dauerte
  das so lange, dass es aussah, als sei der Klick ins Leere gegangen (User-Befund
  2026-08-15). Der Uebergang gehoert `sentMessage` in `query-send.js`:
  `hold()` leert das Feld und zeigt die Nachricht als eigene Blase
  `#threadPendingAsk` (gleiche Optik wie der Kopf, gefuellt von
  `window.App.setPendingThreadQuestion`; `body.thread-message-pending` schiebt
  sie per `order: 4` UNTER die bisherige Antwort und den gefuehrten Lauf gleich
  mit), `promote()` macht sie nach dem Archivieren zum Kopf, `restore()` gibt
  sie unveraendert und abschickbar ins Feld zurueck, wenn der Lauf gar nicht
  stattfindet (Kontingent, fehlender Key, Abbruch) — parallel zu
  `followup.restoreAfterBlockedRun()`, das denselben Lauf beim Kontext haelt.
  Deshalb blendet ein Follow-up den bisherigen Konsens auch NICHT mehr beim
  Absenden aus, sondern erst beim Archivieren: bis dahin ist er die Antwort auf
  die Frage, die oben noch als Kopf steht.
  `App.chatScroll` (`chat-scroll.js`, nach `app-core.js` in `bundles.json`) steuert
  das Scrollen im Agent- und Consensus-Chat. `App.revealSentMessage()` aktiviert
  es beim tatsächlichen Absenden. `openBookmark()` ruft nach der Projektion
  `App.chatScroll.opened()` für einen einmaligen sanften Sprung ans Gesprächsende
  auf, auch bei noch lokal vorhandenen Runs; mobil schließt dabei die Sidebar.
  Gespeicherte Ansichten binden die
  Animation an Bookmark und Auth-Generation; neue Auswahl und Leseinteraktionen
  brechen sie ab. `getSelectedConversationIdentity()` liest dafür nur ID/Modus,
  ohne den gespeicherten Antwort-/Reviewtext pro Animationsframe zu kopieren.
  Recovery, Direktvergleich und Hintergrundläufe erzwingen keinen
  Sprung. Nach zwei Layout-
  Frames scrollt es sanft zum Dokumentende. Im Consensus-Chat wird das Ziel beim
  Absenden eingefroren: Streaming verschiebt weder das laufende Sprungziel noch
  die anschließende Leseposition. „Latest message“ springt dort ebenfalls nur
  einmal zum aktuellen Ende; auch manuelles Scrollen aktiviert kein Mitlaufen.
  Im Agent-Chat folgt es wachsendem Inhalt, solange unten mitgelesen wird.
  `run-view.js` bindet die Projektion an Run und Account;
  ResizeObserver plus Viewport-Resize berücksichtigen Markdown, Bilder und Composer.
  Wheel/Touch/Scrolltasten/Pointer und Textauswahl unterbrechen sofort, auch vor
  dem ersten Frame. Erst bewusstes Abwärtsscrollen bis ans Ende oder „Latest message“
  aktiviert im Agent-Chat das Folgen erneut. Die dezente Schaltfläche mit
  SVG-Abwärtspfeil liegt oberhalb des Composers, blendet sich kurz ein (ohne
  Animation bei Reduced Motion) und gibt den
  Tastaturfokus ohne Scrollsprung ans Eingabefeld zurück. Reduced Motion scrollt
  sofort; Verkleinerung des Inhalts zieht nie nach oben. Dialoge, versteckte Tabs,
  Run-/Kontowechsel stoppen ausstehende Animationen. Verhaltenstests liegen in
  `tests/js/chat-scroll.test.mjs` und `tests/e2e/test_chat_scroll_frontend.py`.
  Der gefuehrte Lauf `#consensusRun` liegt jetzt als
  Container-Kind im Thread (unter der Frage), nicht mehr in der Input-Section.
  Antwort-Typo im Mockup-Mass: `.consensus-main`-H2 als Eyebrow, Body 1.03rem/
  1.7 auf max. 64ch; `.consensus-main` ist `overflow:visible`, weil der alte
  `overflow-x:auto` mit den -8px-Copy-Icons einen Quer-Scrollbalken unter der
  Provenance-Zeile malte. Neue stille Buttons brauchen
  seit 2026-10-02 keinen Ausschluss mehr: der gefuellte Look ist opt-in (`.btn`).
  Der Thread behält weiterhin `100dvh` und kein aeusseres Body-Bottom-Padding.
  Auf Desktop ist der Composer sticky und wird bei kurzen Antworten durch
  `margin-top:auto` an den unteren Rand geschoben. Sein Untergrund
  (`.input-section::before`) endet dort mit ihm: reichte er tiefer, wurde die
  Seite über das Spaltenende hinaus scrollbar, und der in der Spalte gehaltene
  Composer stieg am Thread-Ende um diese Strecke (40 px) hoch (gefixt
  2026-10-02); nur der fixierte Composer ≤1099 px reicht über den Rand. Auf ≤1099 px ist er dagegen
  wirklich viewport-fixiert. `app-init.js::syncThreadComposerReserve()` misst
  seine aktuelle Höhe mit `ResizeObserver` (normaler Composer, kompaktes Gate
  oder Login-Hinweis) und schreibt sie als `--thread-composer-height`; dieselbe
  Höhe wird als Bottom-Padding der Thread-`.container` reserviert. Dafür wird
  dort `container-type` aufgehoben, da es ein `position:fixed`-Containing-Block
  erzeugen würde. So endet der Ergebnis-Footer am vollständigen Scrollende
  oberhalb des Composers, ohne Überdeckung. Zusätzlich gibt
  `.consensus-output` dem letzten Ergebnis auf allen Breiten 24 px Luft
  unterhalb des Footers; die gemessene Composer-Reserve bleibt unverändert. Die Menues am
  Composer (`.attach-menu`, Consensus-Picker)
  oeffnen im Thread nach **oben** in Richtung des gelesenen Ergebnisses; im
  Hero normalerweise nach unten. Der Modell-Picker passt Richtung, Position
  und Maximalhoehe an den tatsaechlichen freien Viewport an. Das Fragefeld wächst über
  `composer-autosize.js::resizeQuestionInput()` automatisch mit seinem Inhalt: bis
  220 px auf Desktop bzw. 180 px auf Mobile; danach scrollt nur noch die
  Textarea. Programmatische Leerungen/Füllungen lösen dafür ein `input`-Event
  aus. Der vorhandene `ResizeObserver` zieht die mobile Thread-Reserve bei
  jeder Höhenänderung mit. Menüs der Composer-Picker setzt
  `fitComposerPicker()` in den sichtbaren Viewport, ohne horizontalen
  Dokument-Scroll. Wo die Teile des Composers stehen, regelt allein
  `css/composer.css` (siehe „Composer: eine Anatomie für alle Modi“). Ein
  Platzhalterwechsel misst das leere Feld neu (MutationObserver in `composer-autosize.js`),
  sonst bliebe es nach einem langen Platzhalter zu hoch. Verborgene `.response-section`-Platzhalter sind im
  mobilen Hero und im fertigen Thread bei geschlossenem „Compare answers"
  `display:none`; ebenso nimmt das geschlossene Differences-`<details>` keinen
  Restplatz ein. Dadurch reservieren weder leere Wrapper noch Flex-Resthoehe
  sichtbaren Leerraum zwischen Differences und Composer.
- **Composer-Reduktion (2026-07-27)** — die Eingabezeile ist auf Anhang (+),
  EINEN Lauf-Schalter („N models · Preset", der bestehende Consensus-Picker mit
  vorangestellter Modellanzahl) und Senden reduziert. Entfallen sind dort
  `#toggleAllButton` (heute: der eine Moduswähler `#runModeSelect`),
  `#modeExplainerTrigger` samt `#modeExplainer`-Section (Modi werden dort
  erklaert, wo man sie schaltet) und `#clearButton` (→ „New comparison").
  Alle betroffenen JS-Stellen waren bereits null-gesichert.
- **`consensus-lifecycle.js`** — Consensus-Sichtbarkeit/Availability,
  Run-State, Abort/Cancel, Run-ID-Gating, Auto-Consensus-Persistenz. Exponiert die
  `window.App.consensusLifecycle.*`-Brücke (siehe §4/§8).
- **`share-dialog.js`** — `window.openShareDialog`, Share-Liste und die gemeinsame
  `window.App.sharedModal.*`-Steuerung für den Share-/Watch-Dialog (einziger
  innerer Scrollbereich, Background-Scroll-Lock, Escape/Focus-Restore). Der
  normale Share-Dialog schließt weiterhin über den Backdrop; im Watch-Modus
  verhindern unbeabsichtigte Außenklicks das Schließen. Jeder Share-Request ist
  an UID/Auth-Generation und eine Modal-/View-Epoch gebunden; Ansichtswechsel,
  Logout und Schließen aborten laufende Fetches, späte Antworten dürfen den
  gemeinsam mit Watch genutzten DOM-Knoten nicht mehr überschreiben.
- **`consensus-actions.js`** — Copy/Citation/Share-Buttons am Consensus.
- **`watch.js`** — `window.openWatchDialog` (Create-Dialog im Share-Modal),
  `window.openWatchDashboard` und das Routing der eigenen Seite `/app/watches`
  (Vollbild-View `#watchDashboard` unter dem fixen View-Switch, URL-Sync via
  pushState/popstate, Deep-Link wartet auf den asynchronen Firebase-Auth-Status).
  Gerendert wird das Dashboard von `watch-dashboard.js`; `watch.js` stellt dafür
  `window.App.watchUi` bereit (API-Helfer mit Session-Epoch, Popup, Schedule-/
  Intervall-/Alert-Optionen, Telegram-Connect, Limit-Rendering) und ruft
  `window.App.watchDashboard.render()`. Der View-Switch `#viewSwitch`
  (Chat/Consensus | Watches) ist ein Segment mit gleitendem Thumb
  (`.view-switch-thumb`, `data-active="chat|watches"` aus `setViewSwitchState`);
  `agent-chat.js` setzt nur das Label im ersten Segment (Agent = „Chat“,
  sonst „Consensus“), Icon und Thumb bleiben. Ein kurzer, auf zwei Zyklen
  begrenzter Puls weist dort dezent auf Watches hin, verschwindet beim ersten
  Öffnen lokal dauerhaft und respektiert `prefers-reduced-motion`.
  **Create-Dialog**: Schritt 1 die Frage (Query-first) bzw. direkt Schritt 2 für
  einen fertigen Consensus. Schritt 2 beginnt mit **„What are you waiting
  for?“** (`#watchGoal`, ≤ 500 Zeichen, gespeichert als `condition`): bis zu drei
  Zielvorschläge kommen asynchron von `POST /api/watch/goal-suggestions` als
  `.watch-goal-chip` (Klick füllt/leert das Feld, ein Fehler blendet sie nur aus).
  Darunter die Defaults-Zusammenfassung mit `#watchEditDefaults` und den drei
  `.watch-setup-chip`-Buttons, die per `data-edit-field` das Panel
  `#watchAdvancedSettings` öffnen (liegt bewusst **über** den Zustellkanälen),
  dann Kanäle und „Start watching“. Alert-Regeln: „When it moves (or resolves)“
  (`changes_only`), „Only when it resolves“ (`condition`, braucht ein Ziel),
  „After every check“ (`every_run`). `POST /api/watch` akzeptiert alternativ zu
  `result_id`/`share_id` ein exklusives `question`-Feld; der Pfad startet keinen
  App-Consensus. Dashboard und Dialog zeigen vor der Aktion den serverseitigen
  Plan, aktive Watches/Limit und freie Plätze; am Limit wird die Create-Aktion
  vor dem Request deaktiviert. Nach dem dritten speicherbaren Consensus zeigt
  `window.App.watch.*` einmalig einen Hinweis am Watch-Button mit der **Aktion
  selbst** („Watch this question“, `nudgeWatchDefaults()`: wöchentlich, morgiger
  Wochentag, 09:00 lokal, privat, E-Mail nur auf Belege); „Add a goal or change
  the schedule“ öffnet den vollen Dialog, ein 429 ebenfalls. Der Hinweis ist ein
  eigener Viewport-Layer unter `<body>` und übermalt nie den Composer.
  `window.App.watch.resetAfterLogout()` leert das Dashboard beim Session-Ende;
  auf einem direkten `/app/watches`-Deep-Link wechselt die Seite deterministisch
  zum Login-Hinweis, `consensio:auth-state` rendert nach späterem Login neu.
- **`watch-dashboard.js`** — rendert `/app/watches` in `#watchDashBody`
  (`window.App.watchDashboard.{render, cardState}`, Styles mit `wd-`-Präfix in
  `static/css/components-watch.css`). Es präsentiert nur das Server-Signal aus
  `drift_signal` (siehe `docs/watch-evidence-model.md`), leitet nichts selbst ab:
  `cardState` liefert pro Watch Ton/Label/Satz/Quellen — *Moved* (mit
  `evidence_sources` und „Held: …“), *Re-checking* (`confirming`), *Answer
  stands* (`held`), *Watching* (letzte Bewegung oder „No change on evidence in
  N checks“), *Resolved* (Grund + Quellen aus `resolution`), *Paused*, *First
  check pending*. Aufbau: ruhige Kennzahlenzeile (watching / moved / resolved
  this week / next check), einklappbares „Why a Watch, not a scheduled prompt“
  (`.wd-explainer`, Offen-Zustand in `consensio.watchExplainer.open.v1`; im
  Leerzustand offen mit Vergleichstabelle `.wd-compare`), Abschnitte
  *Watching* (Moved → Re-checking → Held → Watching → Pending, dann nach nächstem
  Check) / *Resolved* / *Paused*, am Ende *Delivery* (Telegram-Verbindung und
  Morning Brief im `.switch`/`.slider`-Stil des Input-Felds). Jede Karte zeigt
  Status, Frage (3 Zeilen geklemmt), „Waiting for“ + Zielstatus, den Satz des
  Zustands, tragende Quellen, eine Check-Leiste (ein Strich je Check, Form nach
  Signal) und rechts nächsten Check + Tages-Scan (`last_probe`). „Settings“
  klappt in der Karte Ziel-Editor, Intervall/Tag/Uhrzeit, Alerts, Kanäle,
  Google-Listing, Pause/Delete auf; eine abgeschlossene Watch bietet „Watch for
  something new“ (PATCH `status=active` + neues oder leeres Ziel). Kein
  Agreement-Score im Dashboard.
- **`user-tier.js`** — Free/Pro-UI, Premium-Modellstatus (`updateUserTierUI`,
  `updatePremiumModelsState`) und Plan-Label im Sidebar-Account-Footer.
- **`email-verify.js`** (klassisches Head-Skript,
  `window.App.emailVerification`) — der Streifen `#verifyBanner` für
  angemeldete, aber unbestätigte Sessions (`showEmailVerificationGate` /
  `hideEmailVerificationGate`). Kennt Firebase bewusst nicht: `firebase.js`
  reicht Resend/Recheck/Sign-out als Callbacks herein (siehe §4, Auth).
- **`consensus-insights.js`** — strukturierte Auswertung: **Inline-Marker im
  Antworttext**, Claim-Badges, Difference-Karten, Credibility-Frame-Farben,
  Jump-to-answer, Resolve-Runde (Button an Widerspruchs-Karten → `POST
  /resolve`). Seit 2026-07-24 ist die Uneinigkeit *im* Antworttext markiert
  statt in einer zweiten Spalte daneben (Rechtschreibprüfungs-Metapher):
  Claim-Popover und Difference-Karten laufen für den Sprung zur Fundstelle über
  denselben `jumpToModelAnswer`-Pfad. Dieser deckt verborgene Einzelantworten
  zuerst über `window.App.agentMode.showModelAnswers()` auf und
  markiert/scrollt synchron zum Zitat; die Geometrie-Abfrage erzwingt das
  aktualisierte Layout selbst. Der aktive Agent Mode wird dabei nicht
  verändert.
  Difference-Karten zeigen pro Position die Modell-Icons aus den Antwortboxen
  mit deren Dark-Theme-Klassen und zugänglichen Modellnamen/Tooltips; ohne Icon
  dient der Anfangsbuchstabe als Fallback. Der zusätzliche „Worth verifying“-
  Block entfällt. Der Resolve-Button füllt die Kartenbreite mit rechtsbündigem
  Plus-Badge; die Sprunglinks zu den Modellantworten bleiben erhalten.
  Der Verdict leitet Farbe und Überschrift aus derselben Score-Skala ab wie das
  Backend: 85+ „High", 65–84 „Strong", 40–64 „Partial", 20–39 „Low", darunter
  „Very low agreement"; Grün beginnt erst bei 65. Contradictions und Emphasis
  stehen getrennt davon in der Detailzeile. Alte Snapshots ohne Score fallen
  weiterhin auf die Difference-Schwere zurück.
  `locateAnchor` löst den verifizierten Anker auf; bei wiederholtem sichtbarem
  Wortlaut wählt `anchor_occurrence` das vom Judge gemeinte Vorkommen. Die
  Vorkommenszählung normalisiert dafür wie der Browser Markdown-Auszeichnung
  und Quellenchips, sodass etwa gleichlautende Sätze mit `[S1]`/`[S2]` nicht
  beide an der ersten Passage landen. `sentenceBounds`
  dehnt ihn auf den umgebenden Satz aus, `wrapFlatRange` wrappt die
  betroffenen Textknoten in `<span class="cx-claim is-unanimous|is-minor|
  is-split|is-major">`. Seit dem Satz-Index (2026-08-07) ist der Anker in der
  Regel bereits ein GANZER Satz; `endsAtSentenceBoundary` verhindert deshalb,
  dass `sentenceBounds` noch weiter dehnt — sonst verschluckt der erste Satz
  den zweiten und beide Claims landen auf derselben Markierung.
  `searchVariants` probiert zusätzlich eine von `[S1]`-Quellentags befreite
  Fassung: im DOM ist der Tag ein übersprungener `.src-ref`-Chip, ein Anker mit
  Tag fand seine Stelle sonst nie. Gewrappt wird pro Textknoten (nicht per
  `Range.extractContents`), damit `<strong>`, `[S1]`-Links und KaTeX exakt an
  ihrem Platz bleiben; `code`/`pre`/`.katex`/Badges werden übersprungen.
  Seit **2026-08-15 (User-Vorgabe) ist die Marke ein farbiger Textmarker statt
  einer Unterstreichung**: eine Linie unter dem Satz ist im Web die Form eines
  Links, der Leser erwartet einen Sprung und bekommt eine Bewertung. Die Farbe
  spricht die Ampel des Hauses (`--agree`/`--partial`/`--dispute`, Tokens
  `--cx-mark-*` in `components-consensus-visuals.css`): `is-unanimous` grün
  (volle Zustimmung, auch „4/4"), `is-minor` ein neutraler Grau-Wash (Difference
  ohne `severity: major`), `is-split` bernstein (Claim mit Dissens — dieselbe
  Note wie sein gelbes Badge), `is-major` rot (Widerspruch). Deckung bewusst
  niedrig, damit der Textkontrast (≥ 12:1) unangetastet bleibt; seit
  2026-10-02 (User-Vorgabe: ruhig, Apple-Prinzip) sind die Marken reine
  Systemfarben in sehr geringer Deckung (Grün #34c759, Orange #ff9500, Rot
  #ff3b30, Grau #8e8e93; dunkel die Dark-Varianten) und nach Informationswert
  gestaffelt: Grün (der Normalfall) am leisesten, dann Grau, Bernstein, Rot.
  Dark-Rot mischt nicht aus dem korallfarbenen `--dispute`, das sonst mit
  Bernstein verschwamm. Hover
  vertieft denselben Ton (`--cx-mark-*-strong`), statt eine zweite Fläche zu setzen.
  Treffen zwei Marken denselben Satz, hebt `markSentence` die Marke über
  `MARK_LEVELS` (unanimous < minor < split < major) auf die stärkere Stufe an,
  statt die zuerst gesetzte Klasse zu behalten.
  Die Inline-Quote ist standardmäßig ausgeblendet. Settings → Display →
  `#claimCountsSwitch` aktiviert sie browserlokal über
  `consensio.showClaimCounts.v1` / die Body-Klasse `claim-counts-visible`.
  Ohne Badge übernimmt die Passage den Tastaturzugang; Hover und Klick bleiben
  für Live- und gespeicherte Antworten verfügbar. Hover und Detaildialog betonen
  die Quote fett und beziehen den Nenner ausdrücklich auf Modelle, die den Claim
  behandelt haben; „Not addressed“ bleibt separat. Dünne Abdeckung zeigt keine Quote.
  Das optionale `.claim-badge` daneben zeigt die scanbare Quote
  „4/6", jetzt als ruhige Mikro-Marke mit tabellarischen Ziffern, transparenter
  Flaeche und feiner Kontur. Sie ist damit klar von den Quellen-Pillen
  (Favicon + Domain) unterschieden; Neutral = Einigkeit, Bernstein
  (`has-dissent`) = Abweichung. Wenn Claim und Difference denselben Satz
  belegen, bleibt genau EIN Steuerelement sichtbar — welches, entscheidet seit
  2026-08-07 die Schwere: bei **Widerspruch** gewinnt die Passage selbst und das
  Claim-Badge entfaellt, bei **Emphasis** bleibt es wie bisher beim Badge.
  Grund: seit die Claims über den Satz-Index jeden prüfbaren Satz abdecken,
  trägt ein strittiger Satz fast immer AUCH ein Claim-Badge — mit der alten
  Regel (Badge gewinnt immer) verschwand damit praktisch jeder
  Widerspruch aus dem Text, und der Klick auf den strittigen Satz
  öffnete „4 of 6 models agree" statt der Widerspruchs-Karte (User-Befund
  2026-08-07). Das unterlegene Control bleibt als `suppressed` im Group-Objekt,
  Preview und Zaehlung kennen es weiterhin; eine zurueckgetretene Passage gibt
  dabei `role`/`tabindex` ab, damit ein Satz nie zwei Fokusziele hat. Treffen mehrere Claims denselben Satz, bleibt
  ebenfalls nur eine Marke sichtbar: die konservative Satzquote des am
  wenigsten gestuetzten Claims. Die Kopien in
  `landing.css` **und die Mockup-Markups** (`landing.html`,
  `consensus-engine.html`, `partials/product_result_mockup.html`) tragen
  dieselbe Mikro-Quote.
  Hover und Claim-Popover nennen zusätzlich Modelle unter `Not addressed`;
  Schweigen wird damit erst auf Wunsch sichtbar und weder als Zustimmung noch
  als Widerspruch ausgegeben. `renderStoredConsensusClaims` verankert dieselben
  Claims containerlokal in archivierten Chat-Turns, sodass ein Bookmark-Restore
  nicht nur beim neuesten Turn Claim-Support zeigt. „View answer“ öffnet dort
  den gemeinsamen Modellantwort-Leser mit genau diesem archivierten Turn
  statt der globalen Modellbox des neuesten Turns.
  Dasselbe gilt seit 2026-08-17 für die Differences-Schublade: `buildDifference
  Cards(container, …)` baut die Karten in einen beliebigen Container, und
  `window.renderStoredDifferenceCards(container, differences_data, {modelLabel})`
  gibt einem archivierten Turn die gleiche Darstellung wie dem Live-Lauf.
  Vorher fiel jeder Turn beim Rutschen in den Verlauf auf den Judge-Freitext
  zurück — inklusive dessen `BestModel:`-Zeile (User-Befund 2026-08-17).
  Die Archivfassung ist statisch: keine `.diff-jump-link`s (sie zeigten auf die
  Antwortboxen des aktuell projizierten Laufs) und kein Resolve-Knopf (eine Resolve-Runde
  läuft gegen die Modelle des aktiven Laufs), ein persistiertes
  `diff.resolution` bleibt als Ergebnis sichtbar. Die Modellnamen kommen über
  `storedModelLabeller(turnData.model_answers)` aus dem Turn selbst statt aus
  den Live-Boxen. Turns ohne `differences_data.differences` (alte Bookmarks)
  behalten den Freitext-Fallback, jetzt mit Credibility-Badge und ohne die
  `BestModel:`-Zeile (`stripBestModelLine`).
  Die öffentliche Share-/Watch-Seite folgt derselben Autorität: Sobald
  `differences_data.differences` als Liste vorliegt, wird sie auch leer als
  echter „keine Unterschiede“-Befund gerendert. Der Legacy-Credibility-Text
  erscheint nur bei Snapshots ohne strukturierte Liste; eine enthaltene
  `BestModel:`-Zeile wird weiterhin separat als „Best answer“ dargestellt.
  Ausserdem steht `.src-ref` jetzt im `MARK_SKIP_SELECTOR` — ohne das wurde
  die Quellenzahl selbst als Satzteil gewrappt und trug die Markierung
  der Passage (eine angestrichene „3" sieht aus wie ein Fehler). Ein Satz wird höchstens einmal dekoriert
  (Widersprüche laufen zuerst, Claims hängen sich an). Der Spalten-Balancer
  ist mit dem einspaltigen Layout entfallen; `window.balanceConsensusColumns`
  existiert nicht mehr.
  `attachControl` koppelt die Passage an ihr Steuerelement: auf **allen**
  Eingabegeräten bekommt jeder `.cx-claim`-Span `is-interactive` und einen
  Klick, der dieselbe Aktion auslöst wie das Badge. Nur der
  Hover ist auf echte Zeigergeräte (`(hover: hover) and (pointer: fine)`)
  begrenzt, damit sein Zustand auf Touch nicht hängen bleibt. Der
  Hover wirkt in beide Richtungen: `.cx-claim.is-hovered` (vertiefte Marke)
  ↔ `.claim-badge.is-linked-hover`. Wo ein Badge steht, ist es das
  fokussierbare Steuerelement und die Passage nur ein zusätzlicher Mausweg.
  Inline-Quoten haben auf Mausgeraeten nur ihre sichtbare Trefferflaeche;
  auf Touch erweitert `::after` nur die Hoehe auf 44 px. So ueberdeckt das
  Badge keine direkt folgende `.src-ref`-Quelle. Nur alleinstehende Badges
  in Fallback-Zeilen behalten eine nach innen gerichtete 44-px-Touchbreite.
  An einer **Differenz** gibt es daneben seit 2026-08-15 nichts mehr — dort
  macht `attachPassageControl` den ersten Span selbst zum Steuerelement
  (`role="button"`, `tabindex="0"`, sprechendes `aria-label`, Enter/Space),
  sonst wäre der Widerspruch für Tastatur und Screenreader unerreichbar.
  Das Claim-Detail ist mobil ein echtes modales Dialogfenster (`aria-modal`,
  Fokuswechsel/-falle/-rückgabe, inerter Hintergrund); Desktop bleibt ein
  nichtmodaler Popover am Badge.
  Seit **2026-10-01** sortiert `buildDifferenceCards` die Karten nach Schwere
  (kritischer Widerspruch → Detail-Widerspruch → andere Gewichtung, stabil
  innerhalb einer Stufe) und schreibt den Index in der übergebenen Liste als
  `data-difference-index` an jede Karte. Inline-Marker, `focusDifferenceCard`,
  `storedDifferenceFocus`, `answerReader.openPanel(…, index)` und
  `sourceVerification.openResults` adressieren Karten über diesen Datenindex
  (`App.differenceCardAt`), nie über die Kartenposition. Der Kartenkopf nennt
  die Schwere in einem Wort (`Critical`/`Minor`/`Emphasis`, alte Daten ohne
  Severity `Contradiction`; volle Bedeutung im Tooltip und als
  `.visually-hidden`-Text), farbig ist nur der `.sev-dot`. Jede Position hat
  eine Kopfzeile mit Icon + Modellname je Modell; ist die Originalantwort
  erreichbar, ist genau dieses Paar der `.diff-jump-link` (keine separate
  `.diff-position-links`-Zeile, kein Pfeil, keine Pille).
  `.diff-card.is-focused` markiert die geöffnete Karte mit einem verblassenden
  Bernstein-Wash (`diffCardFlash`), nicht mehr mit einem 2px-Ring: der Ring
  las sich über die volle Listenbreite wie ein grauer Rahmen um den ganzen
  Differences-Bereich.
- **`consensus-anchor.js`** — reine, deterministische Textnormalisierung,
  Satzgrenzen-, Range- und Ankersuche für Consensus-Marker. Das Modul kennt
  weder Netzwerk noch Modal-/Produkt-State und wird von `consensus-insights.js`
  als gebundener DOM-Adapter verwendet. Unicode-Erweiterungen beim Lowercasing
  (`İ` → `i` + kombinierender Punkt) erhalten pro normalisierter UTF-16-Einheit
  ursprüngliche Start-/End-Offsets, damit Zitatmarkierungen gültige DOM-Ranges
  bilden. Suchtext und Zitat werden identisch pro Unicode-Codepoint normalisiert
  (auch griechisches Sigma und Zeichen außerhalb der BMP).
- **`consensus-run.js`** — `window.App.executeConsensusRun(context, options)` ist
  der einzige Consensus-Ausführungspfad: baut `/consensus`-Payload, fährt den
  SSE-Stream, rendert Ergebnis + Citation/Share-Meta und archiviert jeden
  abgeschlossenen Turn inklusive turnbezogener Quellen, Differences und
  Modellantworten. Payload, Stream, Turn-Disposition und Persistenz bleiben am
  übergebenen `RunContext`; nur dessen sichtbare Projektion darf den Haupt-DOM
  ändern. `window.getConsensus` ist nur noch eine Brücke: sie delegiert an den
  sichtbaren, laufenden Context und startet sonst nichts (der alte DOM-/
  Singleton-Ablauf ist seit 2026-10-04 entfernt). Bricht der Stream ab, liest
  `recoverConsensusResult` den Turn owner-gebunden nach: `completed` ersetzt
  Consensus **und** Modellantworten durch die gespeicherten (Replay, zählt nicht
  als `app_consensus_completed`), `failed` ist eine echte Disposition und gibt
  die Gesprächssperre frei; nur unbekannt/pending bleibt gesperrt. Ein
  Tokenlimit-Fehler öffnet für den sichtbaren Lauf das `#runBlocked`-Panel.
  `parseBestModel`.
- **`chat-session.js`** — `window.App.createChatSession(initial)` erzeugt pro
  `RunContext` eine private Chat-Zustandsmaschine für completed Basis, pending
  Turn/Context, stabile `client_request_id`, Usage-Key und whitelisted
  Run-Metadaten. Sie hält keine Provider-Antworten, kapselt Chat-/Turn-Anlage,
  Context-Build samt begrenztem 202-Retry und owner-gebundene Turn-
  Reconciliation. `window.App.chatSession` bleibt nur der Kompatibilitäts-
  Spiegel der sichtbaren Ansicht. Das Modul muss nach `app-core.js`, aber vor
  `consensus-run.js` geladen werden.
- **`run-view.js`** — einziger Projektor von `runRegistry.visibleRunId` in den
  gemeinsam genutzten Ergebnis-DOM und die Kompatibilitäts-Globals. Er baut
  Modellboxen, Quellen, Consensus/Differences, Chat-Verlauf, Pipeline und
  gefrorene Mode-/Modell-Labels aus dem Context wieder auf. Registry-Ereignisse
  dürfen für Hintergrundläufe nur deren anklickbare Sidebar-Zeile aktualisieren
  (Preparing/Models answering/Writing consensus/Completed/Failed/Canceled).
  Beim Streaming bleiben unveränderte Modellboxen (inklusive Ladeindikatoren)
  und abgeschlossene History-Turns im DOM erhalten. Inhalts-Signaturen beziehen
  Status, Fehler und Quellen ein; ein Sichtwechsel invalidiert die Projektion.
  So parst eine Folgefrage nicht pro Token den gesamten bisherigen Verlauf neu
  und erhält geöffnete History-Details sowie deren Fokus.
- **`query-send.js`** — `window.sendQuestion`: `/prepare` + `/ask_*`-Fan-out,
  vorgelagerte Turn-/Context-Bindung, Streaming-Rendering, Usage/Tier-UI,
  Agent-Mode-gebundener Auto-Consensus-Trigger und vollständiger RunContext-
  Lifecycle. Vor dem ersten `await` werden Frage, Mode, Provider-/Modelllabels,
  Consensus-Engine, Flags, Auth, Attachments, Conversation-Basis und lokale
  Credentials gesnapshottet. Jeder Callback und jedes Save adressiert danach
  explizit `runId`/Context; `cancelCurrentQuery(runId)` bricht gezielt nur
  dessen Controller ab. Ein valider Agent-Mode-Lauf
  beendet über `window.exitHeroMode()` den zentrierten Input-Leerzustand; der
  Direktvergleich zeigt `#threadAsk` als Dokumentkopf, darunter alle
  Modellantworten im offenen Raster und danach den Composer. Die Frage
  bleibt beim Senden sichtbar. Vor
  `/prepare` gilt eine harte Mindestzahl von zwei ausgewählten Modellen;
  `app-init.js::updateQuestionInputAccess` deaktiviert den Send-Button bereits
  synchron dazu, während `query-send.js` programmgesteuerte Starts nochmals
  abweist. Nach Attachment-/Tier-/Run-Filtern wird dieselbe Mindestzahl vor
  Usage-Reservierung erneut geprüft. Schlagen sämtliche tatsächlichen
  Modellrequests fehl, endet der Lauf als Fehler (inklusive Fehlertelemetrie),
  nicht als erfolgreicher Agent-Mode-Abschluss. Beim Laufstart wird gezielt nur
  `#consensusAnswerBody` geleert; die Markerlegende bleibt erhalten.
  Ein `usage_storage_busy` aus `/prepare` wird mit demselben Idempotency-Key
  kurz erneut versucht; bleibt Firestore beschäftigt, endet der Lauf vor dem
  Fan-out mit einer erneut versuchbaren Thread-Karte (kein falscher
  Provider-Gesamtausfall).
  Der Send-Button spiegelt den GANZEN Lauf: `window.isRunActive()` = Modell-
  Phase ODER Consensus-Phase; `window.App.syncSendButtonRunning()` wird von
  `consensus-lifecycle.js` bei Start/Ende der Consensus-Phase gerufen, damit
  der Cancel-Button bis zum fertigen Consensus/Differences stehen bleibt
  (ein Klick bricht dann via `cancelCurrentConsensus` ab).
- **`tab-status.js`** (seit 2026-10-02, nach `query-send.js` gebündelt) —
  solange die Seite verborgen ist (`document.hidden`), nennt der Tab-Titel den
  sichtbaren Lauf: „Working… · <Titel>“, danach „Answer ready“ bzw. „Run
  stopped“. Hört auf `consensio:run-registry-change` und `visibilitychange`;
  sobald die Seite wieder vorne ist, steht der normale Titel da. Ein Lauf, der
  schon vor dem Verlassen fertig war, wird nicht gemeldet.
- **Der Lichtweg (Agent, seit 2026-10-02)** — das Hauslicht aus
  `send-glow.css` hat genau drei Orte: der Senden-Knopf, eine Haarlinie
  `.agent-light` unter der laufenden Aktivitätszeile (`agent-activity.js` legt
  sie zwischen `details.agent-activity` und `.agent-progress` an, sichtbar nur
  bei `.agent-activity.is-running`) und die Agreement-Zahl. Auf der Linie steht
  das Licht beim Anteil fertiger Vergleichsmodelle (`agent-delegation.js`
  `renderOverview` setzt `--light-p` und `.has-light-progress` auf
  `#agentAnswerActivity`, `agent-chat.js` setzt beides bei einem neuen Turn
  zurück): Vergleiche füllen 14–84 %, die Zeile „Answer check“ ist eine eigene
  letzte Strecke (88 %, fertig 100 %) statt ein weiteres Modell im Nenner, und
  `view.light` hält den Wert monoton (vorher sprang das Licht beim Start der
  Judges zurück); ohne Vergleich gleitet es langsam. Die Linie sitzt
  (`margin: -14px 0 13px`, Handy -18/17) optisch mittig zwischen der Grundlinie
  der Uhr und der ersten Fortschrittszeile. Beim ersten Markieren einer
  geprüften Antwort (`#agentAnswerBody.is-marks-revealing`) fängt
  `.agent-agreement-num` das Licht einmal ein. Reduzierte Bewegung: kein
  Gleiten, kein Aufleuchten. Alles Drückbare gibt beim Druck auf 97 % nach
  (`base.css`, Spezifität 0, eigene Transforms gewinnen).
- **`composer-collapse.js`** — der Composer klappt auf dem Handy (bis 1099 px,
  `COLLAPSE_QUERY` muss zur Grenze in `composer.css` passen) in jedem Modus auf
  (+), Feld und Senden ein: beim Absenden (`window.App.composer.collapse()` aus
  `query-send.js`) und beim Scrollen nach unten. Antippen, Fokus oder
  Hochscrollen holt Modus, Modelle und Fuß zurück; getippter Text wird nie unter
  den Fingern weggeräumt. Zustand ist allein `body.composer-collapsed`; Desktop
  und der Startbildschirm (`App.composer.isStartScreen()`: Hero oder
  Compare-Start) sind bewusst ausgenommen. Ein
  stehendes Zitat (`#composerQuote`) zählt wie ein Anhang als „Angefangenes“
  und verhindert das automatische Zuklappen.
- **`composer-keyboard.js`** (seit 2026-10-04, nach `composer-collapse.js`) —
  hält den fixierten Thread-Composer auf dem Handy (≤1099 px) an der
  Tastaturkante. Safari auf iOS ignoriert `interactive-widget=resizes-content`
  und lässt das Layout-Viewport unter der Tastatur stehen; `bottom: 0` lag dort
  hinter der Tastatur bzw. nach Safaris Scroll mitten im Bild. Solange ein
  Textfeld fokussiert ist und `visualViewport` mehr als 120 px kürzer als
  `documentElement.clientHeight` ist (ungezoomt), setzt das Modul
  `body.keyboard-open` und `--keyboard-edge` = `offsetTop + height`;
  `shell.css` (Abschnitt C) hängt den Composer per `top` +
  `translate(-50%, -100%)` daran und blendet den Hinweissatz aus. Android
  (Layout-Viewport schrumpft mit) und Desktop bleiben unberührt.
  Export `window.App.composerKeyboard.sync`.
- **`composer-quote.js`** (seit 2026-08-17) — **„Ask about this"**: der in einer
  Antwort markierte Abschnitt wandert als sichtbares Zitat über das Eingabefeld
  (`#composerQuote`, gefüllt aus dem Auswahlmenü in `memory-edit.js`) und geht
  beim Senden als Teil der Frage raus. `window.App.quote` =
  `{set, clear, text, has, compose, focusComposer, element}`; Zitatlänge gedeckelt
  auf 1200 Zeichen. **`compose(question)` stellt die getippte Frage VORAN** und
  hängt `Quoted from the previous answer:\n„…"` an — Thread-Kopf, Seitentitel und
  Bookmark-Name sind reiner, whitespace-eingeebneter Text und würden sonst mit
  einem fremden Absatz (bzw. einem nirgends gerenderten Markdown-`>`) beginnen.
  Ab `compose()` ist das Zitat Teil der Frage: Lauf, Chat-Kontext, Bookmark und
  die sechs Modelle sehen genau EINEN Text, deshalb weiß außer `query-send.js`
  (Senden) und `app-init.js` (`clearResponseBoxes`) niemand davon. `query-send.js`
  hält Entwurf und Zitat getrennt in `sentMessage.{draft,quote}`, damit ein
  geplatzter Lauf beides unverändert zurückgibt. Das Menü zeigt „Ask about this"
  nur über Consensus-/Modellantworten (die eigene Frage zu zitieren wäre ein
  Kreis) — anders als Remember/Correct memory **ohne Konto**.
- **`app-init.js`** — das gesamte `initApp()`: Theme, Usage/Limits + User-Status,
  Response-Box-Toggles, Sidebar/Layout, Modals, Tooltips, Evidence-Rendering,
  API-Key-Test. Bis 768 px erzeugt Enter im Composer immer einen Absatz; nur
  Desktop-Enter sendet. Der Sidebar-Eintrag „Models“ zeigt Gästen einen kurzen
  Login-Hinweis und öffnet für eingeloggte Nutzer den Modell-Picker; eine
  Follow-up-/Neuvergleich-Wahl ist dafür nicht nötig.
  `clearResponseBoxes({silent?})` entfernt außerdem den kompletten
  fragebezogenen Share-/Citation-/Evidence-State. Der Usage-Countdown rechnet
  bis UTC-Mitternacht und fordert beim erkannten UTC-Tageswechsel über
  `window.refreshUsageData()` einen neuen autoritativen Serverstand an, statt
  lokal zu früh zu laufen oder die Seite neu zu laden. Der neue UTC-Tag wird
  erst nach einem bestätigten Refresh markiert; Fehler werden begrenzt erneut
  versucht, damit ein veraltetes `0 / Limit` den neuen Tag nicht blockiert. Läuft als letztes
  Script, ruft `initApp()` direkt auf.

Das Admin-Dashboard ist ebenfalls externisiert: `static/css/admin.css` enthält
die vormals template-lokalen Styles, `static/js/admin.js` Auth, Rendering und
Aktionen. `static/js/admin-api.js` kapselt den authentifizierten JSON-Transport;
`static/js/admin-prompt-config.js` besitzt den separaten Configuration-Tab:
Laden/Speichern, Änderungsanzeige, Zurücksetzen einzelner Prompts auf App-Defaults
und Schutz vor verspäteten Antworten eines vorherigen Login-Zustands.
`admin.html` bleibt Markup und trägt nur deklarative `data-*`-Konfiguration.
Der Configuration-Tab liegt im inkludierten Partial `partials/admin_prompt_config.html`.

**Nicht unter `static/js/`** (älter, eigene Verantwortung):
- **`static/firebase.js`** (ES-Modul) — Firebase-Init, Login/Logout, Token-Handling,
  `window.auth`, Bookmarks-CRUD-Calls, Feedback, Voting, Tier-Sync sowie das
  Nutzericon-Menü im Sidebar-Footer (Avatar, Name/Plan, „Shared links“ und
  direkt darunter „Watched“). Ein geöffnetes Bookmark beendet den Hero-
  Leerzustand sofort. Bookmark-
  Jeder vom Server bestätigte Save (`upsertBookmarkMeta`, nicht das Laden der
  Liste) fordert für ein Bookmark ohne `title_source: "generated"` einmal pro
  Sitzung `POST /bookmarks/{id}/title` an (`requestBookmarkTitle`) und blendet
  den Namen in Sidebar-Zeile, Run-Zeile und `bookmarksData` weich ein
  (`applyBookmarkTitle`); ältere Unterhaltungen bekommen ihn beim nächsten
  Turn. Die Sidebar zeigt den ganzen Namen, gekürzt nur noch per CSS-Ellipse
  (vorher hart nach fünf Wörtern mit „...“). Die erste Listenseite übernimmt
  vom Skeleton an Ort und Stelle (`revealLoadedBookmarks`): das Skeleton
  blendet absolut positioniert aus, die ersten 16 Zeilen blenden gestaffelt
  ein. `onIdTokenChanged` richtet eine Sitzung (UID + Auth-Generation) nur
  einmal ein; der stündliche Token-Refresh erneuert nur noch das
  Session-Cookie (`/confirm-registration`) statt Status, Usage, Watches und
  Account-Menü neu zu laden. `/usage` läuft beim Start nur noch, wenn
  `/user_status` scheiterte (gleiche Nutzlast).
  Die paginierte Liste hält nur kompakte Metadaten in `window.bookmarksData`;
  Vollinhalte kommen erst beim Öffnen über `GET /bookmarks/{id}` und nur das
  aktuell geöffnete Detail bleibt im Cache. Suche lädt bei Bedarf weitere
  Metadatenseiten, nicht deren Antworten. Saves reduzieren das serverseitige
  Merge-Ergebnis sofort wieder auf Listenmetadaten. Modell- und Consensus-Saves
  derselben Bookmark-ID laufen browserseitig in Aufrufreihenfolge durch eine
  gemeinsame Queue; der Consensus-Write kommt dadurch sicher nach den bis zu
  sechs Modell-Writes und repariert als autoritativer Vollsnapshot auch einen
  fehlgeschlagenen Modell-Write. Die Firestore-Transaktion behält zusätzlich
  ein erhöhtes Konflikt-Retry-Budget für alte, noch parallel schreibende Clients.
  Im Multi-Run-Pfad tragen `saveBookmark`/`saveBookmarkConsensus` explizit
  `runId`, Bookmark-ID, Auth-Snapshot, Quellen, Attachments und Chat-Bindung.
  Die Queue zählt offene Writes im zugehörigen `RunContext`; weder aktuelle
  Globals noch ein später ausgewählter Bookmark dürfen Ziel oder Payload
  ändern. Ab Sendestart reserviert jeder Context für eingeloggte Nutzer sofort
  einen eigenen gesperrten, animierten Bookmark-Rahmen in der Sidebar. Modell-
  und Consensus-Saves aktualisieren nur diese Zeile; endgültig bereit wird sie
  erst nach terminalem Erfolg, bestätigtem Consensus-Write und null offenen
  Writes.
  Agent-Runs speichern auch terminale Fehler ohne Hauptantwort als Bookmark:
  Frage, Fehler, Aktivität und verfügbare Vergleiche bleiben nach Reload erhalten.
  Beim alten Consensus-Flow ohne ersten Save verschwindet weiterhin nur der lokale
  Platzhalter; bei dessen Follow-ups wird das vorige Bookmark restauriert.
  Löschen setzt sofort die Mutationssperre und blendet die Zeile über 180 ms aus
  (Reduced Motion sofort), während der DELETE in der bestehenden Write-Queue
  läuft. Listen-Refresh und Run-Updates dürfen sie währenddessen nicht neu anlegen.
  Fehler stellen Zeile und Metadaten wieder her; bei unklarem Ausgang bleibt
  die Schreibsperre bis zum erneuten Löschen oder Reload bestehen. Doppelklicks
  teilen dieselbe Löschung, alte Auth-Generationen verändern keine neue Ansicht.
  Beim Restore stammen die
  sichtbaren Namen der Einzelantworten und die Citation-Metadaten aus den
  gespeicherten `model_labels`; die aktuellen Modell-Selects und `localStorage`
  bleiben unverändert und werden erst für einen neuen Lauf wieder in die UI
  gespiegelt. Alte Bookmarks ohne Provenienz zeigen keinen erfundenen aktuellen
  Modellnamen. `window.App.bookmarkSession` ist nur der Kompatibilitäts-Spiegel
  der sichtbaren Context-/Bookmark-Ansicht; die stabile ID selbst gehört dem
  jeweiligen `RunContext`. Chat-gebundene Bookmarks laden
  beim Öffnen alle completed Transcript-Seiten sowie bei Agent-Chats alle failed
  Turns einschließlich solcher ohne Synthese, rendern alle Vorgänger per
  `renderStoredTurns()` und stellen die letzte gespeicherte Chat-/Turn-Basis wieder
  her. Transiente 429/5xx werden einmal wiederholt; fehlende oder zyklische
  Cursor gelten nicht als vollständiger Verlauf. Scheitert nur die Anzeige des
  Transcripts, bleibt die gespeicherte Chat-/Turn-Bindung autoritative
  Fortsetzungsbasis und ein Popup erklärt die reduzierte Anzeige.
  Legacy-Bookmarks ohne `chat_id` verwenden weiter `previous_turn` für die
  Anzeige und ihre letzte Frage/Consensus-Antwort als Ein-Turn-Kontext. Fehlt
  selbst dieser Kontext, nennt der Input den nächsten Lauf ausdrücklich einen
  neuen Vergleich. Sidebar, Thread-Kopf, Titel und Citation verwenden die
  jeweils letzte completed Frage. Das Login-Modal (Ablauf unter §4
  „Auth / Usage / Tier“, Login-Dialog) zeigt nach einer E-Mail-Registrierung
  einen neutralen Mailbox-Setup-Erfolgszustand, ohne einen Probe-Login mit dem
  eingesendeten Legacy-Passwort.
  Logout löscht zuerst erfolgreich die HttpOnly-Session und wartet danach
  Firebase `signOut()` ab; erst dann wird der ausgeloggte Zustand gezeigt.
  Dabei ruft der Client `runRegistry.clearAll("logout")` auf: alle laufenden
  Query-/Consensus-Streams werden abgebrochen, alle Conversation-Fences und
  Contexts verworfen sowie Usage-, Watch-, Bookmark-/Share-UI und Detail-Caches
  und lokal gespeicherte eigene
  OpenRouter-Key geleert und der Hero-
  Ausgangszustand wiederhergestellt. UID/Auth-Generation schützen nach jedem
  relevanten Await Usage sowie Bookmark-List/Detail/Conversation/Save/Delete;
  eine zusätzliche Bookmark-View-Epoch macht die letzte Auswahl autoritativ.
  Listenfehler zeigen einen eigenen Retry-Zustand statt einer scheinbar leeren
  Liste. `/usage` synchronisiert neben dem Tokenkonto auch den Tierstatus und heilt
  so einen transient fehlgeschlagenen `/user_status`-Startcheck in derselben
  Sitzung; beim Start läuft es nur noch in diesem Fehlerfall. Der dynamische Account-Menü-Außenklick-Listener wird bei
  jedem Token-Callback entfernt, bevor ein neuer gebunden wird.
- **`static/demo.js`** (ES-Modul) — Demo-Flow (`runDemoFlow`, im Agent-Modus
  `runAgentDemoFlow` auf der echten Agent-Oberfläche) für die „Demo"-Query;
  zeigt Gästen nach Abschluss der Demo am Eingabebereich eine Login-/Registrierungs-
  Aufforderung, ohne die Demo-Frage aus dem deaktivierten Feld zu entfernen, und
  beendet beim Start denselben Hero-Leerzustand wie eine echte Anfrage.
- **`static/app-ui.js`** — alleiniger Binder für System-Prompt-/Help-Modal
  (keine zweite Bindung mehr in `app-init.js`) + App-Width-Resizer.
  `window.App.getCustomSystemPrompt()` liefert nur persönliche Anweisungen;
  bekannte historische App-Defaults werden aus `localStorage.systemPrompt`
  entfernt, damit die zentrale Admin-Konfiguration greifen kann.

**Abhängigkeitsrichtung**: Bootstrap-/State-Owner + `run-registry.js` →
`app-core.js` → Feature-Module/`run-view.js` →
`app-init.js`/`app-dom-events.js`. Classic-Script-Module kommunizieren weiter
über `window.App`; die verbliebenen `window.*`-Namen sind überwiegend
Kompatibilitäts-Getter oder schmale Funktionsbrücken. DOM-/Control-State wie
`.excluded` konfiguriert den **nächsten** Lauf. Ergebnis-Datasets und Globals
sind nur Projektion der sichtbaren Ansicht und dürfen nie als Quelle für einen
laufenden Request, Consensus oder Save gelesen werden. Entfernte Controls wie
`#consensusButton`, `#toggleAllButton` oder `#apiTestArea` sind kein Vertrag.

---

## 4. Kern-Flows

### Agent · Beta: dynamische Vergleiche und Tokenkontingent (2026-09-19)

**Zugang seit 2026-10-02: jedes angemeldete Konto.** `require_agent_access`
verlangt nur noch eine UID (`/user_status` meldet `agent_access: true`); das
Tageskonto begrenzt Agent pro Stufe. Pro bleiben die Premium-Modelle:
`require_model_access` lehnt in `POST /agent` ein Chatmodell oder
Vergleichsmodell aus `cfg.PREMIUM_MODELS` für Free/Plus mit 403 ab (ein
ausgefallener Tarif-/Rollendienst liefert sicher 503), `/agent/models` markiert
sie mit `premium`, und `agent-chat.js` zeigt sie mit Pro-Badge, aber gesperrt
(`locked()`/`selectable()`). Uploads (`POST /agent/chats/{chat}/files`) folgen
der Anhangregel ab Plus (`require_uploads`); Liste, Download und Löschen
bleiben offen, weil Agent Dokumente für jedes Konto in denselben Speicher schreibt. Detail und Turn-Stop laufen owner- und
turngebunden über den echten Store. Beide Antworten sind `private, no-store`;
Stop setzt die Delegationssperre nur für diesen Turn, auch bei Wiederholung.

Zuverlässigkeitsprüfung (20.09.2026): `POST /agent` sendet bereits vor der
Token-Admission `accepted` mit der dauerhaften Chat-/Turn-ID. Der Browser kann
damit auch wartende Runs zuordnen. Stop und erster Claim konkurrieren in derselben
Firestore-Transaktion; ohne Root-Beleg wird der pending Turn terminal gesetzt.
Status/Recovery schließen verwaiste Turns ohne Root nach Ablauf ihrer fünfminütigen
Chat-Reservierung, ohne eine neuere Turn-Sperre freizugeben. Loop-Initialisierung
liegt im geschützten Vorbereitungspfad und gibt bei Fehlern Kapazität/Turn frei.
Allowance-Recovery filtert vor dem 20er-Limit zusätzlich auf `policy.delegation`,
damit alte Receipt-Formate ohne Producer-Lease keine aktuellen verwaisten Reserven
verdecken. Admission wartet nur, wenn Input plus minimaler Output nach Freigabe
der konkurrierenden Reserven überhaupt passen könnten. Die Vergleichsauswahl
erzwingt auch serverseitig `MAX_RUN_FAMILIES` (sechs).

`ProviderProgressWatchdog` begrenzt einzelne Agent-Providerstreams auf standardmäßig
180 Sekunden **ohne Fortschritt** (`AGENT_PROVIDER_STALL_SECONDS`, 30–600).
Text, Reasoning, Tool-Deltas und steigende Tokenzähler erneuern die Frist; bloße
SSE-Kommentare/Leerereignisse nicht. Der Socket-Guard prüft sie auch während
ausstehender Reads. Das ist keine Gesamtlaufzeitgrenze und kein bezahlter Retry.
Stop direkt vor Dispatch wird als `not_started` abgerechnet. Vergleichsantworten
werden einzeln checkpointed; abgebrochene Synthesen bleiben mit ungeprüfter
Antwortversion erhalten. Noch laufende gespeicherte Vergleiche werden terminal.

`request-deadline.js` stellt `App.withRequestDeadline` bereit (vor den Agent-
Modulen in `bundles.json`): 15 Sekunden für Modellauswahl, Budget, Details, Stop,
Auth/Chat-Anlage und reine Recovery; der Agent-SSE-Kanal verwendet 45 Sekunden
ohne empfangene Bytes. `markdown-stream.js` meldet dafür auch Keepalive-Chunks
über den optionalen `onProgress`-Hook. Abbruch, Auth-Fencing und reine Recovery
bleiben erhalten. Die Aktivitätsprojektion hält die neuesten 64 Hilfsereignisse
sowie alle Fortschrittsabsätze und zeigt Token-Warten samt Erklärung außerhalb der geschlossenen Details; die
Taskzeile zeigt ebenfalls „Waiting for tokens“. Siehe
[Audit und verbleibende Grenzen](agent-reliability-audit-2026-09-20.md).

Agent · Beta ist ein eigener, pro Unterhaltung unveränderlicher execution_mode
für alle angemeldeten Konten (bis 2026-10-01 nur Pro und Admins). Der alte Agent-Mode-Schalter gehört weiterhin zur
unveränderten Consensus-Pipeline. POST /agent besitzt strikte owner-gebundene
Chat-/Turn-/Request-Identitäten; recover_only startet niemals Modellaufrufe.
Fertige Antworten sowie gespeicherte fehlgeschlagene Vergleichsantworten können
mit exakt derselben Auswahl wiedergegeben werden. Recovery ist eine deduplizierte
Registry-Aktion am bestehenden Lauf; sie erzeugt weder einen neuen lokalen
Bookmark-Eintrag noch einen Modellaufruf. Terminale Fehler liefern recoverable;
ohne gespeicherte Antwort verschwindet der Link. Bei unbekanntem Transportstatus
bleibt die reine Lese-Wiederherstellung möglich. /agent/models liefert
die vollständigen Anbieterlisten samt Reihenfolge aus Firestore `app_config/models`,
den konfigurierten Standard und `token_budget`. Seit 2026-10-04 lädt kein
Request die Konfiguration mehr neu (vorher `load_models_from_db` bei jedem
GET/POST: ein Firestore-Read pro Request und ein ungeschütztes Leeren/Neubefüllen
der globalen Maps, während andere Requests sie lasen). Neue Revisionen kommen
über den Admin-Save im eigenen Prozess und den 60-s-Task `model-configuration-sync`.
Premium-Zuordnung und Presets sind keine zweite Allowlist. `provider` und
`provider_label` ordnen jedes Modell seiner Registry-Familie zu.

`llm/agent_model_metadata.py` lädt Preise, Kontextgrenzen und erlaubte Denkstufen
vom festen öffentlichen OpenRouter-Endpunkt `/api/v1/models` ohne Authentifizierung
oder Nutzerdaten. Der prozesslokale Cache bündelt gleichzeitige Abrufe, hält gültige
Metadaten fünf Minuten und versucht nach Fehlern frühestens nach 30 Sekunden neu.
Abrufe sind auf fünf Sekunden und 8 MiB begrenzt; zuletzt gültige Werte und der
eingecheckte `agent_model_catalog.json` bleiben als Rückfall erhalten. Das Modul
prüft Preise/Limits und versieht die Metadaten mit einer Version für Kostenbelege.
Nicht auflösbare Admin-IDs bleiben als `available: false` mit `unavailable_reason`
sichtbar und werden bei der Auswahl abgelehnt. Der statische Katalog hält außerdem
die separat geprüften Delegationsfähigkeiten; er begrenzt die Chatmodellauswahl nicht.

Chatmodell und Vergleichsmodelle teilen sich seit 2026-10-01 EINEN Chip in
`.composer-models` (`.agent-model-picker`, Label „<Chatmodell> +6“: Name
kürzt, `.model-picker-display-count` bleibt ganz). `renderControls` verknüpft
`#consensusModelDropdown` über `App.linkModelPicker` in dessen Menü; der
Consensus-Chip (`.consensus-model`) ist im Agent-Modus `hidden` und kehrt außerhalb
unverknüpft zurück. Das Menü öffnet mit „Agent“ (Chatmodell, Reasoning) und
„Compare with“ (n Modelle · Preset, Familienliste). Der Chip bleibt aktiv,
solange der Companion es ist: Während eines Laufs ist nur die Chatmodell-Zeile
gesperrt, die Vergleichsmodelle für die nächste Nachricht bleiben änderbar.
Die Chatmodell-Ebene zeigt zuerst eine kompakte Anbieterübersicht mit Modellzahl.
Agent-Antworten haben keine Modellüberschrift über der Nachricht: weder die
aktive bzw. wiederhergestellte Antwort in `agent-chat.js` noch archivierte
Agent-Turns in `consensus-run.js`. Die Überschrift normaler Consensus-Turns bleibt bestehen.
`agent-chat.js` erzeugt native `optgroup`-Elemente in der bestehenden Anbieterreihenfolge;
`model-picker.js` aktiviert sie über `grouped: true` als `groups` → `group:<key>`
mit Rückweg (verknüpft: `overview` → `groups` → `group:<key>`). Nur Modelle der
geöffneten Familie stehen in der Liste. Reasoning bleibt eine separate Ebene für
das ausgewählte Modell (verknüpft eine Zeile der Übersicht statt am Listenende);
der Composer-Knopf „Reasoning" öffnet sie im Agent-Modus direkt.
Auswahl/Persistenz laufen weiter über dasselbe native Select. Tastatur unterstützt
Pfeile, Home/End, Enter, Escape sowie Links/Rechts für den Ebenenwechsel.
Kataloge ohne Anbietermetadaten behalten die flache Auswahlliste.
Die Quote wird außerdem beim Start/Settlement als `quota`-SSE, in terminalen
Fehlern und beim vorhandenen Agent-Listenpoll geliefert. `observed_at` ordnet
Snapshots; agent-chat.js ignoriert ältere/fremde Kontenwerte und niedrigere
Konfigurationsrevisionen. Nach Transportabbruch lädt GET /agent/budget nur das
Kontingent neu; es landet in `App.tokenBudget`, dem gemeinsamen Konto aller Modi. Der Sidebar-Ring zeigt (Limit − gemessener − geschätzter Verbrauch) / Limit;
vorläufige Reservierungen ändern die Prozentzahl nicht. Im Panel stehen zusätzlich
die tatsächlich für neue Calls verfügbaren und die reservierten Tokens.

**Auswahl und Orchestrierung.** agent-chat.js trennt Chatmodell/Denkstufe vom
bestehenden Consensus-Preset-/Model-Picker: consensusModelDropdown erhält
comparisonOnly und zeigt im Agent-Modus ausschließlich Vergleichsmodelle
(Custom: Abschnitt „Comparison models“, ohne Consensus-Engine) — als Abschnitt
„Compare with“ im Menü des einen Agent-Chips, nicht als eigener Chip. Es
gibt keine zweite Presetliste, keine Auto/Immer/Aus-Einstellung und keinen
Synthesemodell-Picker. Die eingefrorene comparison_models-Auswahl kommt als
Provider→interne Modell-ID mit POST /agent; unbekannte Familien/Modelle werden
abgelehnt. Der Browser validiert zwei bis sechs Vergleichsmodelle, sperrt Senden
bei ungültiger Auswahl und erhält auch bei direkten Aufrufen den Entwurf vor
Chat-Erstellung/Netzwerkzugriff. Er sendet nie `null` als Ersatz für eine leere
Auswahl. API-Aufrufe ohne Auswahl behalten das zentrale Default-Preset. Der öffentliche
Metering-Katalog ergänzt die gemeinsame Registry automatisch um aktuelle
Provider-Metadaten; neue Admin-Einträge benötigen keinen zusätzlichen Codeeintrag.

Die gemeinsame `#composerModeBar` ist wie in jedem Modus nur auf dem Startbildschirm
sichtbar. Nach Chatstart nutzt Beta das vorhandene `#attachMenu`: Quellenprüfung und Agent-Status verwenden
dieselben Controls, `#agentReasoningMenuOption` öffnet die Denkstufe des Chatmodells
und `#agentComparisonMenuOption` die Vergleichsebene, beide im selben Menü des
Agent-Chips (ebenso die Composer-Notiz `compare`/`choose-model`; ihre Notizen
`.agent-composer-notice` lässt `composer-collapse.js` wie das (+) durch, sonst
schluckte der eingeklappte Handy-Composer den Tap). Der Upload bleibt
deaktiviert; die Reasoning-Schalterzeile von Compare/Consensus (`#reasoningToggle`)
ist in Beta verborgen, dort steht stattdessen der (+)-Eintrag „Reasoning"
(`#agentReasoningMenuOption`) mit dem gewählten Effort.
Der Composer ist derselbe wie in Compare und Consensus (`composer.css`), auch
das (+) auf dem Startbildschirm und im eingeklappten Handy-Composer.
`composer-collapse.js` lässt Pointer/Fokus auf Plus und dessen Menü direkt durch,
ohne das Layout zwischen Touch und Klick zu verschieben. Ein neuer Chat zeigt die
Startleiste wieder. In einem offenen Agent-Chat tritt die Modusgruppe im (+)
zurück (Compare und Consensus brauchen einen neuen Chat). `Reasoning` (`#composerReasoningToggle`) öffnet über
`openModelPicker(select, {secondary: true})` die bestehende Reasoning-Auswahl;
`Attach` bleibt bis zur Unterstützung von Anhängen deaktiviert. Vergleichsicons
und Compare-Picker verwenden weiterhin dieselbe Modellauswahl.
`openModelPicker` klappt einen mobilen Composer vor dem Messen und Fokussieren
des Menüs auf. So öffnen die Shortcuts im Hero und (+)-Menü für Modelle und
Reasoning auch dann ein bedienbares Menü, wenn dessen Elternbereich zuvor
eingeklappt war. Ein nur bei offenem Menü aktiver ResizeObserver passt die
Position während des Aufklappens an. Beim Einpassen begrenzen die sichtbare
Kopfleiste und der View-Schalter den oberen Menüraum, damit kein Eintrag darunter
verdeckt wird; ein offenes Picker-Menü liegt über seinen Nachbarn in der Zeile. Touch-Tests prüfen beide Shortcuts,
freie Trefferflächen der Optionen und den Quellen-Schalter bei 320 und 390 px.
`agent-chat.js` friert `checkSources` im RunContext ein und sendet es als
`POST /agent.check_sources`, einschließlich Recovery. Alte API-Clients ohne das
Feld bleiben bei `false`; die UI verwendet die gemeinsame gespeicherte Auswahl
(Default On). Der Server speichert Einstellung und Source-Limits/Modellwahl in
`agent_settings`; dieselbe Request-ID mit anderer Tool-Freigabe ergibt 409.

POST /agent verwendet den bestehenden DelegationLoop mit `AgentPolicy.for_chat`.
`account_budget_only` ersetzt zusätzliche Laufzeit-, Call-, Tool-, Worker-Runden-,
Such-, Nachrichten- und Dollarlimits durch das zentrale Tages-Tokenbudget. Im
persistierten Policy-Snapshot stehen die nicht angewendeten Limits auf null.
Der injizierte AnalysisBudget ist nur für diesen Lauf zeit-/aufrufunbegrenzt;
Consensus und Legacy-Aufrufer behalten ihre eigenen Grenzen.
Worker-Delegation bleibt separat durch delegation_config.enabled und die
geprüfte Modell-/Reasoning-Kombination freigegeben. policy.delegation aktiviert
hier auch ohne Worker-Freigabe das gemeinsame persistente Schrittjournal.
agent_loop.py bleibt die gemeinsame Basis und der eigenständig testbare direkte
Legacy-Loop. Der ausgewählte Chat-Provider erhält seine vollständigen
Reasoning-/Signaturblöcke für Tool-Fortsetzungen zurück; verschlüsselte Blöcke
werden weder angezeigt noch persistiert. Weitere Details zur Worker-Kommunikation
stehen in [agent-delegation.md](agent-delegation.md).

**Vergleich und Prüfung.** agent_comparison.py registriert compare_models und
judge_answer mit strikten Pydantic-Argumenten. Der abschließend injizierte
Produktprompt erklärt consens.io und setzt für jede Nutzerfrage und jeden
Bearbeitungsauftrag `compare_models → Synthese →
judge_answer` voraus; eingeschaltete Widerspruchsprüfung folgt wie bisher.
Der Agent wartet vor einer inhaltlichen Antwort auf `compare_models` und nutzt
die Ergebnisse samt Belegen als Grundlage. Eine vorab geschriebene eigene Antwort
mit bloßer nachträglicher Bestätigung ist ausgeschlossen. Der Admin-Agent-Prompt
und sein versionierter Default in `prompt_defaults.py` übernehmen die eigenständige
Abwägung des Consensus-Syntheseprompts: alle Beiträge berücksichtigen, Begründung,
Belege und Aktualität statt Modellidentität oder Stimmen zählen, wichtige
Unsicherheit sachlich erklären. Eigene Erinnerung ersetzt weder Vergleich noch
fehlende Belege. `finalized=true` ist ein Protokollabschluss, kein Erfolgsbeleg für
alle Teilprüfungen. Der ergänzende Produktprompt hält diese Regeln ebenfalls fest.
Die Agent-Synthese behält die eigene beratende Stimme, übernimmt aber keine
Ich-Präferenzen, Erlebnisse oder Identität eines Vergleichsmodells. Empfehlungen
nennen die maßgeblichen Nutzerkriterien; belegte Aussagen und daraus abgeleitete
Abwägung bleiben unterscheidbar. Reichweite, Zeitraum und Einschränkungen werden
erhalten, qualifizierte Vorteile nicht in unbelegte Gesamtsieger/Superlative
verstärkt. Eigenständig bestreitbare Aussagen stehen in getrennten, konkreten
Sätzen, mit zugehörigen Bedingungen. Das erleichtert die bestehende satzweise
Coverage-Prüfung, ohne deren Regeln oder Widerspruchsmarkierungen zu verändern.
Die Anleitung gilt auch bei älteren gespeicherten Agent-Prompts; sie verlangt
weder Rollenabgabe noch künstliche Einstimmigkeit oder das Verbergen von Differenzen.
Websuche darf die Anfrage und aktuelle Belege zuerst konkretisieren. Direkte
Antworten sind nur für reine Begrüßungen/Bestätigungen ohne Frage oder Auftrag
und unvermeidbare Rückfragen vorgesehen. Einfache, subjektive und Folgefragen,
Produktfragen sowie Textumformung/Übersetzung durchlaufen ebenfalls die Pipeline.
Bei sinnvoll lösbaren Unklarheiten mit begründeten Annahmen weiterarbeiten.
Das Modell vertritt consens.io hilfreich und korrekt in der Nutzersprache,
erklärt den Produktzweck bei Bedarf und behauptet weder nicht erfolgte Prüfungen
noch garantierte Wahrheit.
Diese Regel konkretisiert auch ältere gespeicherte Admin-Prompts; kein zweiter
LLM-Router und keine sprachabhängige Keyword-Klassifikation. Die Entscheidung
vor dem ersten Vergleich bleibt promptgesteuert, keine semantische Servergarantie.
Deaktivierte Worker
liefern weder Worker-Katalog noch Delegationsprompt im Chatkontext. Auch
Vergleichsmodelle, Judges und Worker erhalten eine knappe Rollen-/Produkterklärung.
Beendet der Server-Suchloop einen Request mit recherchiertem Text ohne Client-Tool,
führt `_consensus_search_handoff` einmalig in die Client-Tool-Orchestrierung zurück:
Antwort und Quellen bleiben im Kontext, die nächste Runde bietet keine neue
Suche an. So verdrängt OpenRouters Abschlussaufforderung am Suchlimit nicht den
Consensus-Ablauf; ausdrückliche Direktantwort-Ausnahmen bleiben möglich.
Das Modell entscheidet selbst,
ob es die ganze Frage oder mehrere begründete Teilfragen vergleicht. Es
liefert einen neutralen Auftrag mit nötigem Kontext; alle Vergleichsmodelle
sehen dieselbe isolierte Aufgabe, keinen Chatverlauf und keine Antworten anderer
Vergleichsmodelle. Der Produktprompt verpflichtet das Chatmodell ausdrücklich,
Bezüge wie „davon“ aufzulösen und relevante frühere Anforderungen in Frage/Kontext
zu übernehmen; unabhängige Fragen brauchen keinen unnötigen Gesprächsrückblick.
`ComparisonTools.compare` startet alle Vergleichsmodelle gleichzeitig in eigenen
Threads (`compare_slots`, je Aufruf eine `ComparisonCancellation`) und wartet nur
bis Quorum plus Nachfrist (`quorum_size`, `QUORUM_GRACE`, `MIN_GRACE_SECONDS`).
`_rebuild` normalisiert Quellen wie zuvor `fan_out_provider_answers` (das der
Consensus-Modus unverändert nutzt) und führt `pending_models`, `failed_models` und
`late`. `freeze_for_synthesis` legt `synthesis_providers` fest,
`finish_comparisons` stoppt vor den Judges verbliebene Nachzügler (`late_cutoff`)
und fixiert `basis_hash`; `close` beendet sie am Laufende (`stopped`). Was ein
gestopptes oder mitten im Stream ausgefallenes Modell bis dahin geschrieben hat
(`Worker.partial_text` aus `_step`), bleibt als
`failed_models[].partial_text` erhalten: nur für den Leser, nie in Synthese,
`answers`/`basis_hash`, Judges oder dem Tool-Ergebnis an den Orchestrator.
Die Agent-Sitzung bekommt dazu eine Nachricht `kind: "partial"` und `partial: true`.
Würde der Review-Snapshot 600 KB überschreiten, fallen zuerst diese Teiltexte weg. Vergleichsmodelle
erhalten keine Delegations-/Vergleichstools, aber eine Suchrunde
(`call(..., kind="comparison")` → `_step(searches_enabled=True)`) und mit
`comparison_system_prompt` das aktuelle Datum. Judges suchen nie; der
Orchestrator recherchiert vor dem ersten Vergleich bis zu drei Runden
(`ORCHESTRATOR_SEARCH_ROUNDS`). Suchkonfiguration (`search_tools`: eine für alle
Modelle, Engine `auto`, nur Grok fest Exa), Reservierung
(`SEARCH_INPUT_TOKENS` pro Runde, `smaller_search`) und Messwerte stehen
ausschließlich in [agent-mode.md](agent-mode.md), Abschnitt „Websuche“. Die Output-Grenze ist die Completion-Grenze des
Modells, begrenzt durch `_output_share` (fairer Anteil am freien Tageskontingent
über `agent_quota.remaining_tokens`). `depth=quick` gibt eine kurze Längenvorgabe,
`full` keine. Technische Token-, Kontext- und Snapshotgrenzen gelten weiter. Leere, abgebrochene oder Tool-Antworten gelten als fehlgeschlagen.
Strukturierte Transportfehler werden am Fehlerfeld erkannt, nicht am Wort
„Error“ im Antworttext; nur Legacy-Stringadapter behalten ihre Fehlerkonvention.
Mindestens zwei vollständige Antworten sind eine brauchbare Prüfgrundlage.

Nach den Vergleichen fordert das Chatmodell mit `judge_answer` die Antwortphase
an; nach `compare_models(next_step="answer")` erkennt `DelegationLoop._answer_ready`
das Ende der Vergleiche und springt ohne weitere Orchestrierungsrunde direkt in
Schreibschritt und `_finish_review`. Der Schreibschritt nutzt
`answer_output_limit` (Completion-Grenze des Chatmodells). `_admit_chat_step`
kürzt für Vergleichsantworten und Antwortschritt bei Konkurrenz die Output-Grenze
(`clamp_floor`), statt zu warten. Die Judges indexieren im Chat bis zu
`CHAT_MAX_CONSENSUS_SENTENCES` Sätze; `_run_coverage_windows` teilt Coverage in
parallele Fenster (`COVERAGE_WINDOW`). `DelegationLoop._write_synthesis` schiebt unmittelbar vor diesem Tool einen
eigenen Schreibschritt desselben Chatmodells ein: leere Tool-Registry, keine
native Suche, `allow_tool_calls=false` und ein eigener Antwortkontext
verlangen die vollständige Antwort. Dieser Schritt wird normal als nächster
`completion:N` reserviert und abgerechnet. Tool-Begleittext oder ein vorzeitiger
Antwortversuch nach Vergleichen wird nicht als Synthese angezeigt/gespeichert;
auch ein reiner Textabschluss führt erst in den dedizierten Schreibschritt.
Vorherige Tools desselben Batches, insbesondere weitere Vergleiche und
Worker-Prüfungen, werden zuerst ausgeführt. Alle Worker müssen geprüft sein.
Auch vor dem ersten Vergleich bleibt Routing-Text gepuffert. Nur eine vollständig
beendete Direktantwort ohne Toolcalls wird einmalig ausgegeben; Begrüßungen und
notwendige Rückfragen benötigen damit keinen zusätzlichen Modellaufruf.
Bricht diese ungeklärte Routing-Phase ab, wird ihr Text auch über Recovery nicht
als Antwort veröffentlicht; Nutzerfrage, Fehler und Abrechnung bleiben gespeichert.
Erst nach vollständigem, nicht leerem `stop` des Schreibschritts wird der sichtbare Text
festgeschrieben und der angeforderte Judge ausgeführt. Bei Abbruch/Tokenlimit
bleibt nur die ungeprüfte Teilantwort erhalten, ohne gestartete Judges.
`ComparisonTools.synthesis_messages` verwendet die konfigurierten Consensus-
Anweisungen, ergänzende Regeln für die beratende Stimme, Datum und Modellidentität.
Der tatsächliche Nutzer-/Antwortverlauf wird beim Start vor allen Laufzeit-
Ergänzungen gesichert. Hinzu kommen ausschließlich Vergleichsfragen/-kontext,
Antworttexte mit Quellen, Anzahl fehlender Antworten, normalisierte Recherche-
Quellen und die zuletzt mit `review_agent` angenommenen Worker-Ergebnisse.
Überarbeitungsaufträge entziehen alten Ergebnissen die Freigabe; bei geprüftem
Fallback gelangt der Ersatztext statt des verworfenen Ergebnisses in die Synthese.
Agent-Systemprompt, Tool-Replay, Status-/Routingfelder und private
Reasoning-Fortsetzungen gelangen nicht in diesen Schreibkontext. Die originale
Tool-Konversation bleibt für die Orchestrierung unverändert. Für den isolierten
Schreibschritt setzt eine Modellkopie `reasoning.exclude=true` und entfernt
`reasoning.summary`, ohne Effort oder Tokenbudget zu ändern. Provider-Reasoning
wird weiterhin nicht in Antwort, Live-Status oder Verlauf projiziert. Die eigentliche
Synthese wird für Folgeschritte nach den Tool-Ergebnissen in den Kontext aufgenommen.
Der Toolcall prüft diesen exakten Text, keinen vom Modell frei behaupteten
Prüftext. Er nutzt query_differences samt Coverage, Satzindizes,
Zitatprüfung und begrenzten Repairs. `chat_mode=true` hält beide Judges auf den
Standardmodellen aus `app_config/models.judge_models`, unabhängig von der
Premium-Einstufung des Chatmodells. Primär bleibt eine andere Familie bevorzugt
(standardmäßig Luna, für OpenAI-Chats Gemini); nach dem begrenzten Retry folgt
der Gemini-Standard-Judge (aktuell Gemini 3.5 Flash-Lite), auch bei einem
Gemini-Chatmodell. Ist Gemini bereits primär, folgt der OpenAI-Standard-Judge.
Pro-Judges und dritte Familien werden im Chat nicht als Fallback eingeplant;
die niedrige Judge-Denkstufe und die bisherigen Consensus-Pläne bleiben erhalten.
`_chat_judge_attempts` liefert denselben Plan an Differences und den parallel
laufenden Coverage-Judge. Die echten Agent-Tests simulieren Luna-Ausfälle,
leere Antworten und Cooldowns mit Standard- und Pro-Gemini-Chatmodellen.
llm/task_transport.py injiziert nur den gemessenen Providertransport via
ContextVar; der Coverage-Thread übernimmt den Kontext. Außerhalb dieser Bindung
bleibt der Consensus-Transport unverändert. Jeder Judge-/Retry-/Repair-Aufruf
hat einen eigenen Agent-Schrittbeleg; der Producer wartet auch beim Abbruch
auf die Settlement-Abschlüsse. `_collect_coverage` wartet bei unbegrenztem
Agent-Budget ohne Timeout statt mit `float('inf')`, das Thread-Wartefunktionen
überlaufen lässt; endliche Consensus-Deadlines bleiben begrenzt.
Ein konfiguriertes Chatmodell ohne Engine-Alias
verwendet seine Familie nur zur Judge-Policy-Auswahl, niemals zur Synthese.

Bei `check_sources=true` ergänzt `agent_contradictions.py` das strikte Tool
`check_contradictions`; ausgeschaltet wird es nicht registriert. Seit
2026-10-03 prüft es **nicht mehr im Turn**, sondern reiht je Vergleich einen
Job in die Consensus-Queue `source_check_jobs.py` ein
(`submit_advisory(..., limits=<eingefrorene Turn-Limits>, binding={basis_hash},
metering=…)`, Kontext: `run_key` = Vergleichs-ID, Parent-Referenz
`users/{uid}/chats/{chat_id}`, Server-Key). Grund: Abruf und Quellen-Judge
kosteten bis zu 60 s je Vergleich (bis zu drei), obwohl ihr Ergebnis erst
nach der Antwort angezeigt wird. Der Turn finalisiert direkt nach
`judge_answer` mit `checks[].source_verification` = kleinem Jobverweis
(`status: queued`, `job_id`, Antwort-Hash als `answer_version`, Vergleichs-ID
als `run_id`, `basis_hash`; der `basis_hash` steht im Plan-Snapshot und damit in
jedem gepollten Job-Snapshot). `source_check_is_bound` akzeptiert neben
terminalen Zuständen `queued`/`running` nur mit `job_id`; `finish_run` prüft
diese Bindung. Ohne Differences entsteht `failed`/`differences_failed`, ohne
prüfbare Widersprüche `skipped` – beide ohne Job. Fasst das Tool nicht der
Orchestrator an, reiht der Server es nach der Synthese ein (`_finish_review`).
Identische Tool-Wiederholungen und Neueinreichungen derselben Grundlage
treffen dieselbe Job-ID (keine zweite Reservierung). Stop vor dem Einreihen
hinterlässt keinen Job; ein einmal eingereihter Job läuft zu Ende. Planung,
Abruf, Belegvalidierung, Fallback-Modell, Leases, Recovery und Polling sind
die der Consensus-Jobs (§ Quellenprüfung). Google-Daten-Chats: unverändert kein
Tool (`agent.py` setzt `check_sources` aus, `_execute` weist es ab).

**Abrechnung (Entscheidung 2026-10-03): der Hintergrundjob bleibt auf dem
Agent-Tokenkonto.** Vorher liefen Primär-/Fallback-Judge über `metered_model`
mit Schrittbelegen; ohne Metering würden die Kosten still auf den Server-Key
wandern. `ContradictionChecks.metering()` übergibt Konto, Periode
(`agent_quota.period_key`) und Stufenlimit; `SourceCheckRepository.create`
reserviert die Obergrenze `package_token_bound(limits)` (Input-Budget +
Output-Cap je erlaubtem Modellversuch, Default 27 000 bzw. 30 000 mit Fallback)
im selben Commit wie die Job-Aufnahme (`job.metering`, Zustand `reserved`).
Deckt das Konto sie nicht, wird nichts aufgenommen: `failed` mit
`reason_code`/`runtime.error_code` `token_budget_exhausted` („Not checked:
today's token allowance is used up“), der Turn endet trotzdem. `finish_package`
settlet im selben Commit wie das Paketergebnis über `agent_quota.settle`
(Messwerte `prompt_tokens`/`completion_tokens`; kein Call oder Cache-Treffer =
0; unbekannte Usage nach gestartetem Call oder `worker_interrupted`/
`worker_execution_failed`/`result_persistence_failed` = begrenzte Schätzung
wie bei Agent-Schritten) in die Periode der Reservierung. `delete` gibt eine
offene Reservierung zurück (nicht während einer Kontolöschung). Die Kosten
erscheinen im Kontostand, nicht in `agent_usage` des Turns.
Die frühere Agent-Transport-Injektion `judge_sources(..., transport=...)` ist
entfernt.

`agent-review.js` bindet diese Ergebnisse an dieselben Widerspruchskarten im
Answer Reader. Wartende Jobs verfolgt `render` selbst (`followSources`): je
`job_id` eines gezeigten Reviews ein `App.sourceVerification.observe`
(Owner-Auth, `GET /api/source-checks/{job_id}`); jede neue Revision ersetzt
`check.source_verification` im Review-Objekt (Basis-Hash aus dem Verweis) und
zeichnet Antwortzeile und offenen Reader neu (`refreshContext`). Ein gespeicherter
Turn spielt seinen Verweis ab und beobachtet den Job erneut; das neueste
Snapshot je Job (`settledSources`) ersetzt beim erneuten Zeichnen einer älteren
Kopie den Verweis sofort. `sameBinding` in `source-verification.js` prüft
zusätzlich `basis_hash`. `context.mark` baut das markierte DOM nur bei geändertem Text,
Check, Quellen oder `_agentRenderSerial` neu (sonst würde jede Live-Aktualisierung
die Animation neu starten); `revealMarks` setzt eine laufende Animation nach einem
neuen DOM über negative Verzögerungen fort — seit 2026-10-03 auch, wenn der
neue Render selbst kein `reveal` verlangt (z. B. `reveal: false` einer
eingetroffenen Quellenprüfung), solange derselbe `answer_hash` noch im
Reveal-Fenster ist; vorher standen dann alle Marken schlagartig da. `query-send.js::setSendButtonRunning`
tauscht das Icon nur bei echtem Zustandswechsel (`data-icon`) und setzt beim Start
eines Laufs einmal `is-launching` (drei Bögen fächern aus, `shell.css`). `agent-chat.js::project` rendert den Review schon während des
Laufs, sobald er `succeeded`/`partial` ist (Quellenprüfung darf weiterlaufen);
davor setzt `setAnswerChecking` `.is-answer-checking` (Schimmer) auf
`#agentAnswerBody`. `renderAnswer` zählt `_agentRenderSerial` hoch, damit ein
neu injizierter Text seine Marken wieder erhält; `revealMarks` animiert sie nur
beim ersten Auftreten je `answer_hash` (`evidence.reveal`); `sourceVerification.render` akzeptiert dafür explizite
`differenceCards`. Veraltete Antwort-/Grundlagenbindungen werden nicht angezeigt.

Die serverseitigen Antwortversionen enthalten Text, SHA-256, Vergleichs-IDs und
Prüfungen; jede Prüfung bindet zusätzlich den Hash der konkreten Antworten
inklusive Quellen/Modellmetadaten. finish_run validiert diese Bindungen erneut.
Mehrere Teilvergleiche werden getrennt gegen dieselbe Synthese geprüft; ihre
Stimmen werden nicht zu einem künstlich größeren Panel addiert. Die erste fertige
Synthese wird serverseitig festgeschrieben: spätere Orchestrator-Deltas werden
weder veröffentlicht noch als Teilantwort gespeichert. `capture` erhält den
exakten Text und seine Hash-/Prüfbindung; neue Vergleiche nach der Synthese werden
abgewiesen. Judge und das Einreihen der optionalen Quellenprüfung schließen auch bei
`finalize=false` ab (das Feld bleibt zur Kompatibilität akzeptiert). Teilweise,
fehlgeschlagene oder übersprungene Prüfungen bleiben ehrlich gekennzeichnet,
lösen aber keine automatische Überarbeitung aus. Nach vollständigem Protokoll-
Abschluss werden auch weitere Toolcalls derselben Modellantwort nicht ausgeführt.
Eine gewünschte Überarbeitung beginnt mit einer neuen Nutzernachricht.
Tool-Begleittext bleibt Planung und öffnet keine Syntheseversion; dies gilt auch
für Einleitungen neben einem vorzeitigen Judge-Aufruf. Weitere Teilvergleiche
bleiben vor der dedizierten Synthese möglich.
Beendet das Chatmodell die Orchestrierung ohne erforderlichen Judge-Toolcall,
führt der Server nach der Synthese `judge_answer` und gegebenenfalls
`check_contradictions` über dieselbe Tool-Registry aus. Abrechnung, Bindungen und
bestehende Fallback-Judges bleiben identisch; zusätzliche Erinnerungsrunden sind
nicht nötig. Drei aufeinanderfolgende Tool-Batches ohne einen gültig ausgeführten
Toolcall brechen als Protokollstillstand ab; gültige Arbeit hat weiterhin kein
pauschales Runden- oder Laufzeitlimit. Ungeprüfte Antworten werden nie erfolgreich
abgeschlossen. Ohne Vergleich
ist keine automatische Prüfung erforderlich. Ein ausdrücklicher Prüfwunsch kann
zuerst mit compare_models eine Grundlage einholen.

**Journal, Abbruch und Verlauf.**
`AgentRunStore.messages` übernimmt sowohl abgeschlossene als auch fehlgeschlagene
frühere Turns. Bei Fehlern bleiben Nutzerfrage und gespeicherte Teilantwort im
Kontext, ausdrücklich als möglicherweise unvollständig/ungeprüft gekennzeichnet.
Ohne gespeicherten Antworttext steht ein entsprechender Hinweis. Laufende Turns
werden nicht als Gesprächsergebnis übernommen; die vorhandene Kontextgrenze gilt.
`chat_store.turn_detail` liefert für Agent-Turns `assistant_response` und den
Kompatibilitätsalias `consensus` unverändert aus. Kein Trimmen, NFKC-Normalisieren
oder erneutes Kürzen beim Lesen: Schon abschließende Leerzeilen gehören zum
geprüften Hash. So bleiben Prüfungen und Markierungen nach Final-Event,
Recovery und erneutem Öffnen des Verlaufs an denselben Text gebunden.
AgentRunStore/AgentSessionStore verwenden users/{uid}/llm_calls mit deduplizierten
completion:N- und agent:<uuid>:N-Belegen, Producer-Token, Lease,
Budget-/Tarifsnapshot und Status. Ein beanspruchter
Provider-Schritt wird auch nach einem Prozessabsturz nie erneut ausgeführt.
Größenvertrag des Root-Belegs je Turn (R29): `step_states`, `step_usage` und
`reservations` enthalten alle laufenden Schritte, aber höchstens
`ROOT_SETTLED_STEP_WINDOW` (32) abgeschlossene. Ältere abgeschlossene Schritte
faltet `compact_root` beim Claim/Settlement in `compacted_usage` (komponierbares
`aggregate_usage`) und `compacted_steps`; ihr eigener unveränderlicher
`llm_calls`-Beleg bleibt maßgeblich (Vorgängerprüfung, Replay-Schutz,
Worker-Usage beim Reaping). Leser verwenden `root_usage(root)`. Mehr als
`ROOT_MAX_RUNNING_STEPS` (64) gleichzeitig laufende Schritte oder ein serialisierter
Root über `ROOT_MAX_BYTES` (256 kB) stoppen vor Reservierung und Claim mit
`run_limit` und dem Hinweis, per Folgenachricht fortzusetzen; die bisherigen
Ergebnisse bleiben gespeichert. Das gilt unabhängig vom Token-/Kontobudget.
Kurze Agent-Transaktionen teilen innerhalb eines Prozesses einen kontogebundenen
Lock-Pool, damit parallele Claims, Statusmeldungen und Abrechnungen nicht um
dieselben Root-/Kontingentdokumente konkurrieren. Firestore bleibt die atomare
Absicherung zwischen Prozessen; Modellaufrufe laufen weiterhin parallel.
DelegationLoop wiederholt bei temporären Datenbankfehlern ausschließlich die
idempotente Abrechnung mit den ursprünglichen Messwerten, auch bei unklarem
Commit-Ergebnis. Offene Abrechnungen werden nach dem Join vor finish_run erneut
abgeschlossen; ein noch laufender Beleg verhindert weiterhin den Run-Abschluss.
SSE-Toolarbeit läuft in einem kontrollierten Thread, während der Producer
Aktivitäten weiter ausgibt. Stop/Disconnect schließt Provider und wartet auf die
aktiven Worker/Tools. Scheitert dabei das Settlement etwa an einem
Kontotombstone, bewahrt der Router `GeneratorExit`, protokolliert den
Cleanupfehler und gibt keinen weiteren SSE-Frame aus; die lokale Kapazität
wird weiterhin freigegeben. Abgelaufene Leases werden zu terminalen unbekannten
Belegen; terminale Belege geben auch bei fehlender Usage ihre Reserve frei.
Budgetabruf und Run-Start suchen zusätzlich kontogebunden nach abgelaufenen
Root-Belegen (höchstens 20 pro Abruf), auch wenn der Eintrag in der aktiven
Lease-Liste verloren ging. Ablaufprüfung und Sperren des alten Producers
erfolgen atomar; eine inzwischen verlängerte Lease wird nicht abgebrochen.
Eine gespeicherte vollständige Usage eines einzelnen
terminalen Agent-Aufrufs kann den fehlenden Beleg rekonstruieren; Aggregate
mehrerer Aufrufe werden nicht auf einzelne Schritte verteilt. Gelöschte Chats
werden dabei nicht wiederhergestellt. Aktive Chat-Producer erneuern ihre
120-Sekunden-Lease etwa alle 30 Sekunden atomar mit Account-Lease und Chat-Lock.
Der Watchdog prüft alle drei Sekunden statt zweimal pro Sekunde und toleriert
kurze temporäre DB-Ausfälle bis 60 Sekunden. Abgelaufene oder ersetzte Producer
dürfen keine Lease erneuern. Eine Chat-Löschung löscht keine
entstandenen Kosten; Account-Tombstones sperren verspätete Writes.

agent_review wird vor Vergleich/Judge und nach Änderungen zusammen mit dem
exakten Antworttext auf dem Turn gespeichert. Terminale Abbrüche wandeln einen
laufenden Prüfstatus in cancelled/failed/missing um. Agent-Bookmarks dürfen
zusätzlich alle fehlgeschlagenen Turns darstellen, auch ohne Hauptantwort.
`_save_interrupted` speichert deren Bookmark inklusive Chat-Bindung auch nach
einem Fehler vor dem ersten Modellaufruf oder vor Eintritt in den SSE-Generator.
Frage, Aktivität, Fehler und vorhandene Vergleichsantworten bleiben über den
Turn abrufbar; API- und UI-Verlaufsfilter verlangen für failed Agent-Turns keine Synthese.
Consensus-Bookmarks bleiben auf completed beschränkt. Recovery gibt nur den
vorhandenen Snapshot zurück, ohne erneut zu vergleichen oder zu belasten.
Bei pending prüft `recover_only` zuerst auf eine abgelaufene Producer-Lease und
schließt diese wie die Sitzungsabfrage ab. Eine gültige Lease bleibt aktiv.
Das Fehler-SSE kann `saved_answer` samt `bookmark_meta` enthalten: Die UI
übernimmt den bestätigten Bookmark sofort und behält Fehler/Prüfstatus des Turns.
Ohne bestätigten Bookmark steuert `recovery_state` (`running`, `saved`,
`unavailable`) die Wiederherstellungsaktion; unbekannter Zustand heißt
„Check saved answer“, laufender Zustand „Check run status“.
assistant_response bleibt kanonisch; consensus ist der alte Lesealias.
Direkte Teilantworten bleiben bei Providerfehlern erhalten. `agent_failure`
enthält den sicheren Fehlercode und Grund auch im gespeicherten Turn; die UI
zeigt ihn live und nach Reload. Provider-Timeouts sind von Kontingent-Stopp und
Nutzerabbruch getrennt, rohe Provider-Fehler werden nicht gespeichert.
Scheitert ein Lauf erst nach abgeschlossenem Review, behält
`AgentRunStore.finish` den Review-Status `succeeded`/`partial`; nur laufende
bzw. ausstehende Reviews werden zu `failed`/`missing`/`cancelled`.
`agentReview.failureNote` entscheidet über den Hinweis unter der Antwort: unter
einer vollständigen, geprüften Antwort keiner, sonst ein ruhiger Satz zur
möglicherweise unvollständigen Antwort, ohne Antwort der sichere Fehlertext.
Live-Ansicht, gespeicherter Turn und Verlauf (`consensus-run.js`) nutzen ihn.

**Composer und Antwortaktionen (21.09.2026).** `agentChat.sendBlocker()` verbindet
Zugriff, Katalogstatus, verfügbare Chatmodelle, Vergleichsauswahl, Anhänge und
Fortsetzbarkeit mit der Sendesperre in `app-init.js`. Ein kurzer Hinweis außerhalb
der im Chat verborgenen Modusleiste erklärt die Sperre auch mobil; „Choose models“
öffnet den bestehenden Compare-Picker. Leere Agent-Nachrichten sperren Senden,
ein vorhandenes Zitat zählt als Nachricht. Während eines Laufs bleibt Stop
bedienbar. `agentChat.syncComposer()` erhält vorhandene ARIA-Beschreibungen und
setzt nach der gemeinsamen Follow-up-Projektion den passenden Agent-Platzhalter:
Einstieg, Entwurf während der Antwort oder Folgefrage im bestehenden Chat.

Fehler/Stop vor dem ersten `/agent`-Request stellen den unveränderten Entwurf
mit getrenntem Zitat wieder her. Dafür gelten Kontobindung, sichtbarer Run und
ein unveränderter leerer Composer; neuere Texte/Zitate/Anhänge bleiben erhalten.
Nach Dispatch erfolgt keine automatische Rückgabe als ungesendete Nachricht:
die bestehende reine Recovery bleibt für unklaren Serverstatus zuständig.

`agent-answer-actions.js` läuft nach `agent-review.js` und vor `consensus-run.js`.
`agent-preferences.js` (nach `agent-review.js`) speichert Tiefe und Quorum der
Einstellungen im Browser, gibt den Reiter `agentSettingsSection` über
`App.settingsTabs.setTabAvailable` nur bei `agentChat.canUse()` frei (Aufruf aus
`agentChat.renderShell`) und liefert `App.agentPreferences.get()` für das Feld
`agent_preferences` von POST `/agent` (`AgentPreferences` in `agent_comparison.py`,
Werte in `agent_settings.agent_preferences`).
`App.agentAnswerActions.render` ergänzt aktuelle, wiederhergestellte und
archivierte Agent-Antworten um „Copy answer“ aus dem kanonischen Markdown,
ohne Activity, Prüfmarkierungen oder Bedienelemente. Während Streaming sind die
Aktionen verborgen; gestoppte Teilantworten bleiben kopierbar. Stabile Buttons,
lokales Statusfeedback und eine Projektionsrevision verhindern Fokusverlust und
verspätete Copy-Rückmeldungen am falschen Turn. Folgefragen verwenden direkt den
Composer, ohne zusätzliche Antwortaktion. `agent-review.js::evidenceButton`
gibt Contradictions/Review, Answers und Sources dieselbe dezente Icon-Gestaltung
und lesbare ARIA-Namen samt Anzahl; der Antwortleser-Vertrag bleibt unverändert.
Bis 540 px stehen die drei Vergleichsaktionen in gleich breiten Spalten mit
Icon/Anzahl über dem Label. Einzelne Quellenaktionen ohne Vergleich bleiben
kompakt. Die Gestaltung gilt auch für gespeicherte und archivierte Antworten.

**UI-Verträge.** agent-activity.js zeigt die Laufzeit in der Überschrift des
standardmäßig geschlossenen Disclosures. Live zählt sie sekündlich ab dem Start
des Runs inklusive Wartephasen; Abschluss und Stop frieren sie ein. Gespeicherte
Turns verwenden `created_at` und `completed_at` bzw. `failed_at`, fehlende oder
ungültige Zeitstempel ergeben „Details“. Parallele Toollaufzeiten
werden nicht addiert. Der Timer kündigt nicht jede Sekunde per Screenreader an
und wird beim Verbergen/Turnwechsel aufgeräumt. Darunter wechseln sich die kurzen
Fortschrittsabsätze des Steuerungsmodells und bestätigte Toolschritte in ihrer
Ereignisreihenfolge ab. Laufende Schritte aktualisieren sich im selben DOM-Knoten
zu abgeschlossenen Schritten; ohne aktives Tool steht der aktuelle Thinking-/
Writing-/Review-Status am Ende. Fortschrittsabsätze sind im hellen Modus dunkelgrau
und im dunklen hellgrau, damit sie sich von der Antwort abheben. Arbeitsschritte
bleiben schwarz bzw. weiß; in Forced Colors gilt für beide `CanvasText`.
`ProgressArgs.status_update` ergänzt die bestehenden Tools
`compare_models`, `judge_answer` und `check_contradictions` um maximal 400 Zeichen;
für ältere Aufrufer ist das Feld optional. Der injizierte Produktprompt verlangt
es bei jedem dieser Aufrufe: ein bis zwei konkrete Sätze in der Sprache der
aktuellen Frage bzw. der gewünschten Antwort, mit Arbeitszweck oder Befund und
nächstem Prüfschritt. Keine privaten Gedankengänge, Toolnamen oder unbelegten
Erfolgsmeldungen. Es entstehen keine zusätzlichen Status-Tools oder Modellrunden.
`DelegationLoop._execute` veröffentlicht den validierten Text vor dem zugehörigen
Toolstart als `activity` mit `kind: progress` und stabiler Schritt-/Toolcall-ID.
Die Meldungen werden in `agent_activity` gespeichert, nicht in der Synthese oder
den neutralen Vergleichsaufträgen. Provider-Reasoning des Chat-Steuerungsmodells
wird nicht mehr als Live-Status oder Chatverlauf projiziert; vollständige private
Fortsetzungsdaten bleiben im laufenden Provider-Protokoll.

Die Live-Absätze verwenden stabile DOM-Knoten in einem höflich angekündigten
`role=log`; die rotierende 64er-Grenze für Hilfsereignisse entfernt keine
Fortschrittsmeldungen oder bestätigten Toolschritte. Token-Warten ergänzt einen
sichtbaren Hinweis.
Bei Abschluss, Fehler oder Stop verschwindet die Live-Anzeige und auch ein zuvor
geöffneter Verlauf klappt zu. Anschließendes manuelles Öffnen über Pfeil/Enter
zeigt die vollständigen Absätze, bestätigte Tools und Usage; spätere Projektionen
erhalten diese Wahl. Der Verlauf fließt ohne verschachtelten Scrollkasten im Chat.
Schon während des Nachdenkens ergänzt der geöffnete Verlauf Chatmodell,
Reasoning-Einstellung und aktuelle Phase, statt nur dieselben Live-Absätze mit
einer Trennlinie erneut zu zeigen. Die Werte stammen aus den eingefrorenen
Run-Einstellungen bzw. bestätigten Statusereignissen. Noch laufende Vergleiche
zeigen Ziel und Begründung; Links zu Antworten/Prüfung werden erst mit den
zugehörigen Ergebnissen bedienbar.
Der Abschluss-Snapshot ergänzt die bereits empfangenen Aktivitäten anhand ihrer
IDs; gespeicherte Zustände überschreiben passende Live-Einträge, ein unvollständiger
Snapshot löscht keine vorher sichtbaren Fortschrittsmeldungen aus dem lokalen Turn.
`agentReview.renderActivity` ergänzt im Disclosure die gespeicherten Vergleichsziele,
Begründungen und Modellnamen sowie gebundene Prüfergebnisse, bis zu drei erkannte
Unterschiede und den Umfang der Quellenprüfung. Dieselbe Text-/Hash-/Basisbindung
wie im Antwortleser verhindert Aussagen aus veralteten Prüfungen. Auch ohne
`agent_activity` bleiben vorhandene `agent_review`-Details beim Wiederöffnen sichtbar.
Schaltflächen öffnen die zugehörigen Originalantworten bzw. die vollständige Prüfung
im bestehenden Antwortleser. Ein WeakMap ordnet dem Review-Snapshot dessen
Leserkontexte zu; diese werden auch bei inhaltlich gleichen neuen Snapshots gebunden.
Wenn weder Verlauf noch Vergleichsdetails gespeichert sind, erscheint ein klarer
Hinweis statt einer leeren Trennlinie. Zusätzliche Modellaufrufe entstehen nicht.
`agentActivity.reveal` blendet neue Absätze und den ersten Antworttext mit 4 px
Versatz über 220 ms ein; weitere Streaming-Chunks starten keine neue Animation.
Statuswechsel blenden über 160 ms über. Die Live-Vorschau wächst bzw. verschwindet
mit animierter Höhe und Abständen; der Verlauf öffnet/schließt mit gemessenen
Höhen über die Web Animations API. Inhalte bleiben beim Schließen kurz sichtbar,
sind aber sofort `inert` (Live-Vorschau zusätzlich `aria-hidden`); erst danach
werden sie verborgen/entfernt. Schnelle Richtungswechsel brechen alte Animationen
ab, `agentActivity.dispose` räumt sie beim Turnwechsel ab. Reduced Motion und
Forced Colors überspringen Bewegung und beenden laufende Übergänge sofort;
ohne Web Animations gilt derselbe unmittelbare Fallback.
Liegt der Aktivitätsbereich oberhalb des Viewports, beendet die Projektion seine
laufenden Höhenanimationen und führt Änderungen ohne Animation aus.
`chatScroll.preserveAbove` gleicht die Änderung der Dokumentposition unmittelbar
aus, sodass die gerade gelesene Antwortzeile stehen bleibt; bereits erfolgtes
natives Scroll-Anchoring wird nicht doppelt verrechnet. Nach Run-Abschluss endet
dauerhaftes Nachscrollen. Ein noch laufender bewusster Send-/Latest-Sprung darf
einmal fertiglaufen. `chat-scroll.js` trennt diesen expliziten Sprung von einem
nur eingeplanten Resize-/Follow-Frame; Letzterer wird beim Abschluss verworfen,
damit neue Copy-/Evidenzzeilen die Antwort nicht nach oben verschieben.
Sichtbare Statusbereiche behalten ihre kurzen Übergänge.
Tool-Nennungen bleiben Text; ausschließlich bestätigte running-Toolereignisse
oder der Review-Status bestimmen den aktuellen Arbeitsschritt im Verlauf.
Alte gespeicherte Reasoning-Verläufe bleiben als begrenzte Auszüge lesbar.
`agent_progress.py`/`agent_loop.py` behalten für Legacy-Läufe und Worker drei Zeilen
à 180 Zeichen und acht Updates je Modellschritt; Provider-Zusammenfassungen haben
Vorrang. Worker verwenden weiterhin `progress_text`/`progress_kind` in ihrer Sitzung.
agent-delegation.js verwendet das bestehende geordnete Activity-Journal,
überlappende Modell-Icons und die Agent-Detailseitenleiste auch für Vergleichs-
und Judge-Aufrufe (kind). Der Stapel dedupliziert identische API-Modelle, die
Seitenleiste behält jeden Aufruf.
Der Kopf mit Titel, Stop/Schließen und die Übersicht bleiben außerhalb des
Scrollbereichs sichtbar. Die Übersicht (`.agent-sidebar-overview`) nennt
`n of m done` (plus `· k without result` für `failed`/`stopped`) und rechts den
Gesamtverbrauch (`.agent-sidebar-usage`); darunter ein Segment pro Zeile
(`.agent-sidebar-segments i[data-state=done|busy|out|idle]`) in der Bildsprache
der Consensus-Pipeline: grün fertig, Sweep laufend, gestrichelt raus. Die Leiste
wächst mit ihren Zeilen bis zur Viewporthöhe (`max-height` statt fester Höhe),
statt als leerer Vollhöhenrahmen zu stehen. Nur `.agent-session-list` scrollt;
gespeicherte Scrollpositionen pro Turn beziehen sich auf diese Liste.
Aufgeklappte Details haben bewusst keinen eigenen Scrollbereich mehr (zwei
Scrollbalken nebeneinander): sie fließen in der Liste, der Kopf einer offenen
Zeile klebt (`position: sticky`) oben, und ein vom Nutzer geöffneter Eintrag
(Fokus auf dem `summary`, also Klick, Taste oder Modell-Icon) wird per
`reveal()` in Sicht gescrollt — höher als die Liste: Anfang oben.
Die Inline-Icons behalten ihre DOM-Knoten pro API-Modell: Statuswechsel,
Tokenupdates und zusätzliche Aufrufe desselben Modells aktualisieren nur ihre
Metadaten und das Ziel der Detailansicht. Neu hinzukommende Icons blenden sich
einmal über 240 ms mit 4 px Versatz ein; mehrere neue Icons sind um jeweils
24 ms (maximal 96 ms) versetzt. Dadurch bleiben Fokus und Animation bei
laufenden Updates stabil. Reduced Motion deaktiviert die Bewegung vollständig.
Die Leiste blendet sich mit kurzer Bewegung als Overlay ein; Chat und Composer
behalten beim Öffnen und Schließen ihre Position und Breite. Reduced Motion
deaktiviert die Einblendbewegung. Kompakte Einträge zeigen Modellname und Tokens
in der ersten Zeile, darunter Aufgabe sowie Status/Laufzeit; lange Namen und
Metadaten dürfen umbrechen. Während eines Modellaufrufs schimmert die Tokenzahl dezent:
zunächst `Tokens pending`, dann tatsächlich empfangene Antwort-/sichtbare
Reasoning-Zeichen (`chars`), bis der Provider Input+Output-Tokens meldet.
Unter den Metadaten steht pro laufendem Modell ein dezenter 2-px-Ladebalken.
`agent-session-track` nutzt den gemeinsamen `run-model-track` samt
`runModelShimmer`-Animation und versetzten Startzeiten aus der Consensus-Pipeline.
Der Balken zeigt Aktivität ohne geschätzte Prozentzahl, bleibt beim Wechsel zu
gemessenen Tokens aktiv und verschwindet beim Streamende, Abschluss/Abbruch oder
in gespeicherten Ansichten. Reduced Motion/Forced Colors deaktivieren den Schimmer.
`StreamProgress` in `agent_progress.py` liefert höchstens alle 500 ms numerische
`delegation_progress`-SSE-Snapshots sowie Start/Ende. Diese flüchtigen Ereignisse
halten nur den neuesten Zwischenstand pro Sitzung neben der bestehenden Queue,
ohne Datenbank-/Journal-Schreibvorgänge oder zusätzliche Modellaufrufe. Ein
langsamer Leser füllt dadurch nicht die Queue für dauerhafte Ereignisse.
Abgeschlossene frühere Schritte werden genau einmal zur aktuellen
Provider-Messung addiert; Fortschritt verändert weder Belege noch Quoten.
`agent-chat.js` reicht die Snapshots an `App.agentDelegation.receiveProgress`
weiter. Account, Turn, Agent, Sitzungssequenz und eigene Fortschrittssequenz
verhindern veraltete Updates; Zeichenstände fallen innerhalb einer Sitzung nicht
zurück. Abschluss/Abbruch und gespeicherte Ansichten beenden den Schimmer.
Reduced Motion/Forced Colors lassen die Zahl lesbar und unbewegt. Fehlende
Endwerte bleiben unavailable, unvollständige Tokensummen tragen ein +.
Laufzeiten verwenden serverseitig monotone Sitzungsdauern (einschließlich Warten
und Review); Fortschrittsereignisse tragen `duration_ms`. Die Sidebar ergänzt
nur bei laufenden Sitzungen `performance.now()` seit Empfang. Browser-Uhrzeit
und `created_at` werden dafür nicht verrechnet. Gespeicherte/terminale Ansichten
frieren ein, auch bei verspäteter Projektion. Der Reparatur-Poll liefert aktive
Sitzungsdauern anhand der Serverzeit. Nach abgelaufener Prozess-Lease bleibt die
letzte dauerhaft bestätigte Dauer als `duration_incomplete`/„≥“ erhalten; ein
späterer Reload wird nicht als zusätzliche Modelllaufzeit gezählt.
Judge-Details werden aus dem bestehenden öffentlichen Sitzungs-Snapshot sofort
gerendert (Zweck, Fortschritt, Status, Tokenaufschlüsselung), ohne Detail- oder
Nachrichtenabfrage. Worker-/Vergleichsdetails laden weiter nur bei Bedarf,
zeigen sofort einen Skeleton und nutzen den vorhandenen message_seq-Cache.
Live-SSE ersetzt regelmäßige Vollabfragen: erst nach zehn Sekunden ohne Session-
Update wird reparierend gepollt, nur bei sichtbarem Browser-Tab. Am Laufende folgt
ein finaler Abgleich; ein älterer Poll darf einen beendeten Lauf nicht reaktivieren.
Läuft die serverseitige Abwicklung nach lokalem Stop noch, setzt die Ansicht
reparierende Abfragen bis zum terminalen Serverstatus fort. Timer und Schimmer
bleiben dabei beendet; die Oberfläche benennt ausstehende Modellabschlüsse.
delegation_view verwendet den Receipt-Snapshot der Lease-Prüfung erneut und spart
dadurch eine doppelte Dokumentabfrage.
App.createModelMark löst Anbieter/Modelle über
MODEL_FAMILIES inklusive apiPrefix auf; unbekannte Modelle erhalten ein Initial.
Die Icons sind 15px groß. Im Composer öffnet das Chatmodellmenü über die
optionale `secondarySelect`-Ebene von model-picker.js auch die Reasoning-Wahl.
Ein gesperrter Agent-Modusschalter und die frühere Tokenzeile bleiben verborgen.
Die Aktivitätsliste enthält auch weitere Vergleichs-/Judge-Runden über 64 Sitzungen;
Parallelitäts- und Nachrichtengrößen bleiben begrenzt. agent-review.js steht in bundles.json vor
consensus-run.js und rendert live aus review-SSE-Ereignissen oder gespeichertem
agent_review. Vor Markierungen prüft es Text-/Versions-/Basisbindung.
`agent_comparison.py::review_issues` persistiert `checks[].issues` mit getrennten
Gründen für ausgefallene Modelle, fehlende Judge-Ergebnisse und unvollständige
Satz-/Kontextabdeckung. `comparisons[].failed_models[].failure` enthält nur den
sicheren Fehler aus `agent_failure`, niemals rohe Provider-Antworten. Eine
fehlende Modellantwort hält den Gesamtstatus `partial`. Im Leser erscheint ein
Modell mit `partial_text` als `status: "incomplete"` (Chip „Incomplete“, eine
sichtbare Begründungszeile `.answer-reader-note`, Kopieren erlaubt), eine am
Output-Limit abgeschnittene Antwort (`answers[].truncated`) als fertige Antwort
mit `badge: "Cut off"` und `note`; die Agent-Leiste zeigt „Incomplete“ statt
„No answer“ und die Überschrift „Incomplete answer · not used“. Die Zeile unter der Antwort
(`summaryText`) bleibt bei einer fertigen Prüfung leer und spricht nur, wenn die
Prüfung selbst eingeschränkt ist: `Not compared · fewer than two models answered`,
`Disagreements not checked` oder `Partly checked` (Coverage fehlt). Fehlende
Modelle, ungeprüfte Sätze und Quellenlücken stehen nur im Leser: seit
2026-10-01 als **eine** leise Zeile `evidenceStatus` (`4 of 6 models answered ·
Checked` bzw. `· Partly checked`), hinter der ein `<details>` die fehlenden
Modelle mit Grund, späte Antworten und kleinere Prüflücken auflistet. Nur
entscheidende Lücken (`decisive`: keine Differences-/Coverage-Prüfung, zu wenige
Antworten) stehen sichtbar darunter. Danach folgen die Karten; Quellenprüfbericht
(`.agent-source-check`), Quellenprüf-Hinweise, „Model agreement is not
independent fact checking.“ und die Kontext-Disclosures stehen in
`.agent-evidence-footer` unter den Karten. `statusText` (`Comparison checked · N
models without an answer`) bleibt nur für die Aktivitätsdetails.
Copy und die Evidenz-Links teilen eine Zeile: `agent-answer-actions.js` hängt die
Leiste in `.agent-review` (auch bei noch nicht eingehängten Verlaufs-Turns),
`agent-review.js` erhält sie beim Neuaufbau. Key claims (Claims ohne Inline-Marke)
stehen vor dieser Zeile. Archivierte Agent-Turns blenden den Consensus-Fuß
(`.thread-history-footer`) aus, weil `.agent-review` dieselben Links trägt.
Schlägt ein Lauf erst nach einer vollständigen, geprüften Antwort fehl, zeigt die
Kopfzeile `Thought for …` (dieselbe Regel wie `failureNote`).
Statuslabels: `Partly checked`, `Check could not run`, `Answer not checked`;
Ausfallgründe erscheinen nur als kurze Code-Phrase (`failureReason`).
`Answers` zählt vollständige Antworten; die Details behalten auch Fehlermodelle.
Alte Reviews werden aus ihren vorhandenen Judge-Metadaten erklärt. Gebundene
unvollständige Quellenprüfungen erhalten zusätzlich einen eigenen Hinweis.
Deutsche Ordinalzahlen vor Monaten und Ordnungswörtern („10. Oktober“, „19.
Jahrhundert“) sind kein Satzende: `_ORDINAL_FOLLOWERS` in `consensus_engine.py`
und `ORDINAL_FOLLOWERS` in `consensus-anchor.js` müssen gleich bleiben.
`wrapFlatRange` markiert Satzteile, die Fett/Kursiv/Links trennen, mit
`cx-join-start`/`cx-join-end`; nur die äußeren Enden tragen Innenabstand und
Rundung, sonst entstünde an jeder Elementgrenze ein sichtbarer Zusatzabstand.
`consensus-insights.js` hält die aktive Hover-Gruppe; Scroll/Resize versteckt
veraltete Geometrie und plant die Vorschau erneut, wenn Zeiger/Fokus noch auf
der Passage liegt. Mausfähigkeit wird beim Eintritt über `any-hover`/`any-pointer`
geprüft, nicht nur beim Erzeugen der Markierungen. Die gemeinsame Implementierung
gilt für Agent, Consensus und gespeicherte Turns.
Pro Turn vereinigt die Quellenansicht Provider-/Suchquellen, die Quellen aller
Vergleichsgrundlagen und sichere HTTP(S)-Links aus Antworten und früheren
Textversionen. Der gemeinsame Katalog hält die Quellenzahlen beim Wechsel der
Vergleichsgrundlage konsistent. `agent-review.js` setzt zuerst die gebundenen
Prüfmarkierungen und danach die Quellen-Pillen (Favicon + Domain); Live-, gespeicherte,
abgebrochene und archivierte Antworten verwenden dieselbe Darstellung. Frühere
Textversionen im Leser erhalten ebenfalls Quellenverweise. Vergleichsantworten
aktivieren über `sourceReferences: 'agent'` in `model-answer-reader.js` dieselbe
Darstellung mit ihrer eigenen Quellenliste. agent_runs.py persistiert Provider-/Suchquellen beim Abschluss auch
auf `turn.sources`; alte Turns nutzen weiterhin `agent_activity`. Ohne Vergleich
öffnet der Sources-Footer einen Leser mit ausschließlich dem Quellen-Tab.
Pro Vergleich verwendet es die gemeinsamen renderStoredConsensusClaims und
renderStoredDifferenceCards. Ein kompakter Footer öffnet Widersprüche, formatierte
Einzelantworten und Quellen im gemeinsamen model-answer-reader.js. Dessen
openContext/refreshContext verwenden explizite Vergleichs-Snapshots mit eigenem
renderPanel/contextGroup; globale Consensus-Ziele werden nicht ausgeliehen.
Rote Textmarkierungen öffnen über focusDifference die konkrete Karte; deren
answerNavigation führt zur zugehörigen Originalantwort. Die Live-Aktivitätsleiste
und der Antwortleser sind wechselseitig sichtbar. Vergleichsgrundlagen lassen
sich über ein beschriftetes Auswahlfeld per Tastatur umschalten. Frühere
Textversionen, Kontext und Teilergebnisse bleiben im Leser einsehbar. Archivierte
Agent-Turns erhalten denselben Footer und einen Modellstapel. succeeded bedeutet abgeschlossene
Modellvergleichsprüfung, ausdrücklich keine unabhängige Faktenprüfung.
Fehlende Coverage, fehlende Sätze, gekürzte Grundlagen und ausgefallene Modelle
werden nicht als vollständig geprüft dargestellt.

**Tokenkontingent und Kosten.** agent_quota.py ist das zentrale UTC-Tageskonto,
seit 2026-10-01 gemeinsam mit Compare/Consensus/Reasoning-Läufen (§4 „Ein Tokenkonto
für alle Modi"). Das Limit kommt aus der Kontostufe
(`app_config/agent_budget.tier_limits[free|plus|pro|admin]`, `account_tier`:
Admin-Rolle vor gespeicherter Stufe); das frühere globale
`daily_token_limit`/`AGENT_DAILY_TOKEN_LIMIT` gibt es nicht mehr. Agent bleibt
Pro/Admin (`require_agent_access`), das Konto selbst ist für jede Stufe da.
agent_budget_config.py liest die Einstellung mit 30 Sekunden Cache je Prozess/DB.
Admin → Limits verwendet
GET/PUT /api/admin/agent-budget und POST /api/admin/agent-budget/reset mit
Admin-Rollenprüfung, strikter Eingabe und erwarteter revision. Jede Änderung
schreibt eine Audit-Revision. Reset wechselt reset_epoch für alle Agent-Konten,
ohne Nutzer-Scan oder Löschung der Usage-Historie. Laufende Calls settlen in ihrer
ursprünglichen Generation; nur ungenutzte Review-Holds wandern vor weiteren
Claims/Prüfungen mit. Veraltete Admin-Requests scheitern mit 409, DB-Fehler werden
nicht als erfolgreiche Änderungen ausgegeben. Gezählt wird ausschließlich
Provider-Input + Provider-Output. Cached input und cache writes sind Teil des
Inputs; reasoning ist Teil des Outputs. Provider-Gesamtkosten haben Vorrang vor
Katalogschätzungen; Kosten werden erfasst, begrenzen den Agent-Chat aber nicht zusätzlich.
Jeder Claim reserviert transaktional im selben Commit wie sein Beleg unter
users/{uid}/chat_state/agent_tokens_YYYY-MM-DD[_reset_epoch]. Settlement tauscht die Reserve
gegen gemessene Tokens genau einmal aus. Jeder terminale Beleg gibt seine
Reserve frei, auch wenn finale Tokenzahlen fehlen. „Begrenzte Unsicherheit“
(R07): Ein gestarteter Call ohne finale Usage wird weder ganz freigegeben noch
ganz belastet, sondern mit einer Schätzung verbucht: gemessene provisorische
Untergrenze, mindestens `UNKNOWN_ESTIMATE_FRACTION` (50 %) der Reserve. Sie
steht im eigenen Ledger-Feld `estimated`, strikt getrennt von gemessenem
`used`, und zählt gegen `remaining`; die API liefert `estimated` mit. Der Beleg
erhält `quota_estimate` und `quota_reconcile=pending` (mit Provider-
`generation_id`) bzw. `final` (ohne). `agent_usage_reconciliation.py` fragt
OpenRouter `GET /generation?id=…` im Hintergrund ab (angestoßen vom Budgetabruf
bei `estimated > 0`, je UID höchstens einmal pro Minute, in Unit/E2E/Mock aus)
und ersetzt die Schätzung transaktional durch die gemessenen Tokens; der
Belegstatus `pending → measured|final` ist der Exactly-once-Zaun. Nach sechs
Versuchen oder 24 Stunden bleibt die Schätzung endgültig. Nachweislich nie
gestartete Calls (`not_started`, `provider_rejection`) bleiben freie Nullmessungen.
Eine ganztägige Sperre gibt es weiterhin nicht. `unknown` summiert
die Reservierungsgrenzen solcher Belege, nicht deren tatsächlichen Verbrauch.
`unknown_released` markiert die bereits freigegebenen Grenzen kumulativ.
Budgetabruf und Ledger-Transaktionen lösen alte unbekannte Reserven anhand der
Differenz transaktional genau einmal auf, ohne gemessenen Verbrauch oder aktive
Reserven zurückzusetzen. Auch ein während des Rollouts noch vom alten Server
abgeschlossener Beleg wird dadurch nachträglich korrekt freigegeben.
Zwischenstände vor dem terminalen Stream-Chunk sind `provisional`: Sie dürfen
als gemessene Untergrenze angezeigt werden, gelten nach Streamabbruch aber nicht
als finale Abrechnung. Der finale Usage-Chunk ersetzt kumulative Zwischenstände.
`complete` beschreibt ausschließlich die Tokenmessung; fehlende Suchpreisdaten
setzen separat `cost_complete=false` und blockieren keine bekannten Tokens.
Explizite HTTP-Ablehnungen vor jeder Generierung (400/401/402/403/404/413/422/429)
werden als Nullverbrauch mit `source=provider_rejection` verbucht und geben die
Reserve frei. Ein Abbruch nach Admission, aber vor Start des Provider-Adapters,
gibt die Reserve mit `source=not_started` ebenfalls frei. HTTP 408/5xx, Transportabbrüche und Fehler innerhalb eines
angenommenen Streams bleiben ohne finale Usage unbekannt.
Jede Änderung am Tagesledger erhöht dessen transaktionale `revision`. Die UI
ordnet Budgets nach Config-Revision, UTC-Tag und Ledger-Revision, unabhängig von
Server-Uhrabweichungen; ältere Antworten können keinen neueren Stand ersetzen.
Bei sichtbarem Agent-Chat werden Budgets auch im Leerlauf alle 60 Sekunden sowie
bei Fokus/Tab-Rückkehr aktualisiert. Fehlgeschlagene Aktualisierungen markieren
den letzten bestätigten Stand; Auth-Wechsel verwerfen alte Requests/Ansichten.
Tooltip und Budgetpanel unterscheiden unverbrauchte Tokens von momentan für
neue Calls verfügbaren Tokens. Geschätzte Tokens (`estimated`) zählen im Ring
als verbraucht und werden im Panel als Schätzung bis zur Messung benannt.
`scripts/repair_agent_allowance.py --email <Konto> --project-id <Projekt>` liest
gezielt den aktuellen Ledger; erst `--apply` führt denselben Recovery-Pfad aus.
Das Skript prüft das Projekt, verweigert Emulator-/Unit-Test-Kontexte und startet
weder Modellaufrufe noch einen globalen Reset.
Auch Abbrüche, Fehler und Judge-Wiederholungen zählen. Tageswechsel migrieren
nur ungenutzte Prüfreserven; bereits gestartete Calls werden ihrem Claim-Tag
zugeordnet. Andere parallele Chats können reserviertes Budget nicht ausgeben.
`agent_tokens.py` zählt Chatkontext, vollständige Tool-Fortsetzungen, Schemas
und strukturierte Antwortformate lokal mit tiktoken/cl100k. Die unveränderten
Vokabeldaten samt Lizenz liegen komprimiert in `llm/tokenizer_data/`; Laden
prüft SHA-256 und benötigt weder Netzwerk noch einen beschreibbaren Cache.
Ein gemeinsamer Lock um Cache-Zugriff und Aufbau verhindert mehrfache
Tokenizer-Initialisierung bei gleichzeitigen Kaltstarts; `encoding.cache_clear()`
setzt den Cache unter demselben Lock zurück.
25 % Zuschlag plus Protokollreserve berücksichtigen abweichende Tokenizer;
das ist eine Zulassungsschätzung, keine gemessene Usage und keine garantierte
Provider-Obergrenze. `agent_costs.RunCosts.estimate` trennt diese Kalkulation
von der lokalen Reservierung. Begrenzter Suchkontext zählt erst in Folgeaufrufen,
nicht bereits vor der Suche. Legacy-Aufrufer behalten ihre konservativen Grenzen.

`DelegationLoop._admit_chat_step` verwendet diesen Pfad gemeinsam für Chat,
Worker, Vergleichsmodelle und Judges. Konkurrenz durch aktive Reservierungen
führt zu abbrechbarem Warten mit lokalem Settlement-Signal und Poll-Backoff
(maximal drei Sekunden), auch über getrennte Runs/Prozesse. Die vorhandene
Lease-Recovery bereinigt verwaiste Produzenten; fehlgeschlagene idempotente
Settlement-Schreibvorgänge werden vor weiterem Warten nachgeholt. Wartende
Aufrufe halten keine eigene Reservierung und erzeugen keinen bezahlten Beleg.
Wenn auch ohne Konkurrenz zu wenig Budget für die optionale Suche bleibt,
entfällt sie mit ausdrücklichem Hinweis an das Modell. Anschließend passt sich
`max_tokens` an Restbudget/Modellfenster an; ein Minimum für sichtbare Antwort
und explizite Reasoning-Budgets bleibt erhalten. Derselbe angepasste Wert geht
an Provider und Receipt. Ein echter Output-Abbruch (`length`) speichert die
Teilantwort als fehlgeschlagen statt fälschlich als vollständige Antwort.

Eine endgültig abgelehnte Reservierung ist von leerem Tagesbudget getrennt
(`agent_token_reservation` / `agent_tokens_exhausted`); Fehler nennen benötigte
und damals verfügbare Tokens. Scheitert vor dem Provider-Aufruf allein die
Zulassung mit optionaler Suche, versucht DelegationLoop denselben Schritt ohne
Suchreserve. Der Systemkontext macht fehlende neue Recherche ausdrücklich;
Modellfenster und Tageskontingent bleiben verbindlich. Der
abgelehnte Versuch schreibt keinen Beleg und startet keinen bezahlten Aufruf.

Im Chat entfallen pauschale Reserven für hypothetische Synthese-/Judge-Aufrufe;
alle tatsächlich anstehenden Aufrufe reservieren weiterhin atomar im Tagesledger.
Die alten Review-Holds bleiben für Legacy-Läufe korrekt abrechenbar. Modellfenster,
Output-, Speicher- und Parallelitätsgrenzen bleiben technische Anforderungen:
standardmäßig zwei parallele Unteraufrufe, initial 120.000 Zeichen Chatverlauf,
bis zu 600 kB Review-Snapshot. Kein LLM-Kompressor. Der Admin-Prompteditor zeigt
nur wirksame Worker-Parallelitäts-/Nachrichtengrößen und verweist auf Limits für
das zentrale Tagesbudget; alte Config-Felder bleiben beim Speichern erhalten.
Konten behalten maximal zwei aktive Läufe; AGENT_MAX_CONCURRENT_RUNS begrenzt
Produzenten pro Prozess (Default 16). Consensus behält seine Run-Limits.

Agent nutzt den gemeinsamen `engines.web_search_tool`-Builder mit derselben
Engine-Wahl wie Consensus (Details: [agent-mode.md](agent-mode.md), „Websuche“).
Es gibt keinen neuen Suchdienst. Provider-Routing/ZDR bleiben bestehen.
Nur bestätigte Zähler/Quellen erzeugen Suchaktivität. Kosten-/Tokenwerte bleiben
bei unvollständiger Provider-Usage ausdrücklich unvollständig.

Validierung: test_agent_comparison.py prüft echte gemeinsame Judge-Prompts/Parser
mit deterministischen Providern, mehrere Grundlagen, Versionen, Teilausfälle,
fehlende Calls, Abbruch, UTC-Wechsel und atomare Kontingente. Ergänzend bestehende
Agent-/Consensus-Tests, agent-review.test.mjs sowie die gebaute Desktop-/Mobil-
Ansicht in test_agent_comparison_frontend.py; siehe [testing.md](testing.md).

### Browser-Run-Lifecycle und Sichtwechsel

- Ein Send erzeugt vor dem ersten Netzwerk-`await` genau einen `RunContext` im
  `runRegistry`. In einer Browser-Session dürfen höchstens **zwei** Contexts im
  Status `starting|running` sein; ein dritter Start wird vor `/prepare`
  abgewiesen. Ein schneller zweiter Klick innerhalb desselben Gestenfensters
  startet beziehungsweise cancelt nicht versehentlich erneut.
- Ausführung, sichtbare Ergebnisansicht und Fortsetzungsbasis sind drei
  getrennte Zustände. „New comparison“ ruft `clearVisible()` auf und leert nur
  Projektion/Conversation-Auswahl; laufende Fetches gehen im Hintergrund weiter.
  Ein Klick auf `.bookmark.run-entry[data-run-id]` setzt `visibleRunId` und
  projiziert den exakten Zwischen-/Endstand dieses Contexts zurück. Nur Logout
  beziehungsweise ein Auth-Reset cancelt und verwirft alle Runs.
- Jeder asynchrone Callback prüft Run- und Auth-Identität, mutiert ausschließlich
  den eigenen Context und rendert den Haupt-DOM nur, wenn dessen `runId` gerade
  sichtbar ist. Quellen-Mapping arbeitet auf expliziten Listen statt
  `window.currentEvidenceSources`; `/consensus`, Resolve und Bookmark-Saves
  bauen ihre Payloads aus dem gebundenen Context, nie aus Antwortboxen oder
  „current“-Globals.
- Cancel ist run-spezifisch: Haupt-Send/Cancel betrifft nur den sichtbaren Run;
  Registry- und Lifecycle-APIs akzeptieren eine `runId`. Provider-Controller,
  Consensus-Controller und sensible Credentials/Attachment-Bytes bleiben pro
  Context und werden bei terminalem Ende bereinigt.
- Zwei frische Vergleiche dürfen parallel laufen. Zwei Follow-ups derselben
  Conversation-/Bookmark-Basis sind gesperrt, weil serverseitige Turn-Reihenfolge
  und Bookmark-Mutation seriell bleiben müssen. Ein normal terminaler Turn gibt
  das Lock frei; ein abgebrochener/fehlgeschlagener Turn mit unbekannter
  serverseitiger Disposition behält den Fence bis zum Reload/Session-Reset.

### Anfrage an Modelle (Streaming)

`llm/base.get_date_context()` liefert den gemeinsamen serverseitigen Datumsblock
für den Standard-Systemprompt der Einzelantworten, Agent, Consensus-Synthese
und Differences. Er enthält Datum/Wochentag, Uhrzeit bei Prompt-Erzeugung sowie
die konfigurierte Referenzzeitzone (Default `Europe/Berlin`) inklusive Sommer-/Winterzeit-Offset. Es ist
kein beim Serverstart eingefrorener Wert. Eigene Client-Systemprompts behalten
ihren bisherigen Vorrang; der Standard wird nicht ungefragt angehängt.
Ohne persönliche Anweisungen sendet `query-send.currentSystemPrompt` einen leeren
Wert; `/prepare` setzt den konfigurierten Einzelantwort-Standard und den frischen
serverseitigen Datumsblock ein. Nur vor einem ausdrücklich gespeicherten eigenen
Prompt ergänzt der Browser wie bisher sein lokales Datum. Dieser persönliche
Client-Prompt behält Vorrang in `/prepare` und im Fan-out.

1. Frontend `sendQuestion` (`query-send.js`) ruft zuerst **`POST /prepare`**:
   Auth sowie transaktionale Admission auf dem Tokenkonto (`run_mode`
   `compare|consensus`, Reasoning-Schätzung aus `deep_search`) und sofortiger Consume
   des vom Client erzeugten, kostenfreien `usage_run_key`; Antwort: finaler
   `system_prompt`, `token_budget` und `run_estimate`. Vorher blockt
   `usageLimit.blockIfExhausted` clientseitig mit derselben Regel.
   Echtzeitdaten holen sich die Modelle über das gemeinsame OpenRouter-Web-Tool
   in jedem Modell-Call (`engines.py`), daher kein Intent-Router mehr.
   Bei `usage_storage_busy` wiederholt der Client `/prepare` kurz mit demselben
   Key. Bleibt Firestore beschäftigt, bleibt die Frage erhalten und der Lauf
   endet vor dem Fan-out mit einer Retry-Karte.
2. Fan-out an die ausgewählten **`/ask_<provider>`**-Endpoints (parallel), je mit
   `stream:true`. Backend prüft Auth, Pro-Status (nur für Premium-Modelle),
   Wortlimit (`validate_question_word_limit`) und Modell (`validate_model`),
   parst Attachments und bestätigt den bereits konsumierten Run idempotent.
   Alle parallelen Provider teilen denselben Key und sehen `consumed`; sie
   kosten nichts zusätzlich. Clientseitige Modellanzahl/Kosten werden nicht
   akzeptiert.
   Einen eigenen OpenRouter-Key dürfen nur verifizierte Nutzer verwenden; er umgeht
   die Usage-Zählung, aber nicht Auth/Pro-Gates.
3. **SSE-Protokoll Modellantwort** (`streaming_model_response` in `streaming.py`):
   `event: delta {text}` … dann `event: final {response, sources,
   token_budget, is_pro_user, tier, key_used}` (`token_budget` = Konto nach der
   Buchung dieser Antwort; eigene Keys: `usage: "own_keys"`). Bei Fehler kommt
   ein `final` mit `error`. Provider-SDK-Content-Blöcke werden an dieser Grenze
   rekursiv zu Text normalisiert; Objektwerte gelangen weder als Delta noch als
   `[object Object]` ins Frontend. `sse_pack` führt außerdem jeden Event-Payload
   durch FastAPIs `jsonable_encoder`, weil SSE die normale Response-Kodierung
   umgeht; Firestore-`DatetimeWithNanoseconds` aus kompakten Bookmark-Metadaten
   wird dadurch vor dem abschließenden `json.dumps` zum ISO-Zeitstring. Frontend
   rendert Deltas und wertet `final` aus. OpenRouter-URL-Annotationen werden in
   `citations.py` zu `[S…]`-Marken. Nullbreite/ungueltige Provider-Offsets nutzen
   defensiv die beim Streaming erreichte Textposition und die naechste
   Satz-/Absatzgrenze; ohne brauchbaren Anker landen sie am Antwortende, niemals
   vor dem ersten Wort. Wiederholte kumulative Annotation-Snapshots werden im
   Stream dedupliziert.
   Nicht-SSE-Antworten werden zuerst als Text gelesen und, falls möglich, als
   JSON geparst; Plain-Text-/Proxy-/HTTP-Fehler bleiben dadurch sichtbar und
   werden nicht mehr zur generischen „No response received“-Meldung.
   `llm/provider_runtime.py` setzt für alle OpenAI-kompatiblen SDK-Clients und
   REST-Transporte zentrale Connect-/Read-Budgets (Default 10/120 s) und
   `max_retries=0`; fachliche Judge-Fallbacks bleiben explizit im Engine-Code.
   Browserabbruch beendet einen begonnenen SSE-Lauf: das Cancellation-Signal
   schließt aktive HTTP-/SDK-Streams, unterbindet weitere Provider-Retries und
   der abgebrochene Generator erreicht keine nachgelagerte Persistenz.
4. **Agent Mode an:** `consensus-progress.js` begleitet den gefuehrten Lauf
   rahmenlos unter dem Input. Der Gesamtzaehler basiert auf
   `dataset.responseState`; die einzelnen Modell-Balken wachsen monoton aus
   dem sichtbaren Stream und erreichen erst beim Abschluss 100 Prozent. Nach
   dem Fan-out wechselt die Anzeige zur nicht prozentual geschaetzten
   Synthesephase und verschwindet bei Abschluss, Fehler oder Abbruch.
   **Agent Mode aus:** `model-answer-reader.js` zeigt alle Originalantworten
   rahmenlos in zwei Spalten (bei schmaler Leseflaeche untereinander). Die
   Frage steht einmal als normale Chat-Nachricht darueber, der Composer darunter. Die Frage wird
   nur an `/ask_*` gefächert. Es gibt keinen Pipeline-Block, keinen
   `/consensus`-Aufruf und folglich keine Differences oder Claims. Die Body-
   Klasse `.direct-comparison-active` haelt diesen Layoutzustand auch mobil
   sichtbar. Der Differences-Spinner hatte bis
   2026-07-27 eine eigene Leiste (`.differences-progress`), die mit ihr
   dieselbe Phase doppelt zeigte und deshalb entfallen ist. Im zweiten
   Schritt ist auch der verbliebene Text „Comparing responses" weg:
   `window.consensusDifferencesSpinnerHTML` ist leer, `consensus-run.js`
   faellt bewusst NICHT auf `window.spinnerHTML` zurueck, und
   `differencesPanel.setSynthesizing()` laesst das Panel jetzt ZU (ein
   aufgeklapptes leeres Panel waere die dritte Anzeige desselben Vorgangs).
5. **Ein hängendes Modell blockiert den Lauf nicht**: jedes `/ask_*` bekommt in
   `query-send.js` einen eigenen `AbortController` (der Lauf-Controller
   kaskadiert darauf). Haben mindestens zwei Modelle geantwortet und wartet der
   Lauf danach ≥ 8 s weiter, bietet die Modellzeile im gefuehrten Lauf
   „Skip" an; `window.App.skipModel(boxId)` bricht genau dieses
   Modell ab, markiert die Box als `responseState="error"` +
   `responseSkipped="true"` und zaehlt es einmalig als beantwortet.

### Follow-up-Fragen
Nach jedem erfolgreichen Consensus kann derselbe owner-gebundene Chat um eine
weitere Frage ergänzt werden. Es gibt keine harte Turn-2-Sperre mehr: Turn 2,
Turn 3 und spätere Turns benutzen eine serverseitig autoritative Context-Version.
- Frontend: Die autoritative Fortsetzungsbasis liegt getrennt von der Ansicht
  in `runRegistry.selectedConversationBasis`; ein neuer `RunContext` erhält
  davon einen Snapshot und eine eigene `ChatSession`. `window.App.followup`
  (in `consensus-run.js`) hält **nur noch den Kompatibilitäts-/DOM-State der
  sichtbaren Projektion, keine Ausführungsautorität und keine eigene Fläche**.
  `run-view.js` baut ihn bei jedem Sichtwechsel aus `historyTurns` und der
  completed Basis des gewählten Contexts neu auf. **Seit 2026-08-07 hat der
  Composer überhaupt keine
  Follow-up-Affordance mehr** (User-Vorgabe: „Das Follow-up-Feature ist
  überflüssig, Chats sollten standardmäßig fortführbar sein"): der frühere
  Kontext-Chip (`#followupChipBar`, `.followup-chip`, `discard()`/`arm()`) und
  das zweite „New comparison" (`.followup-newrun`) am Feld sind ersatzlos
  entfallen, ebenso der leere `#followupBar` in der Provenance-Zeile. Davor war
  bereits (2026-08-06) das **Composer-Gate** (`#composerGate`,
  `body.composer-locked`, Zwangswahl) gefallen. `isArmed()` ist jetzt schlicht
  „die sichtbare Projektion enthält einen fortsetzbaren Turn". Die nächste
  Frage liest jedoch ausschließlich die gewählte Registry-Basis. Der **einzige
  Ausstieg ist `#newRunButton`** in der Sidebar: Er leert über
  `clearResponseBoxes` Sichtprojektion, Fortsetzungsbasis und `#threadHistory`,
  ohne einen Hintergrundlauf abzubrechen. **Für alle Nutzer offen** (seit
  2026-08-04): kein Pro-Gate (Badge, Teaser-Modal, 403 `pro_required`), ein
  Follow-up zählt als ein normaler Lauf gegen das Tagesbudget.
  Ein restauriertes Bookmark setzt über `showSavedView(view, basis)` dieselbe
  getrennte Fortsetzungsbasis und projiziert sie anschließend über `offer()`.
  `syncInputLock()` zieht nur noch die Login-Schranke nach und setzt den
  Platzhalter passend zum Kontext-Zustand; `updateQuestionInputAccess` ruft es
  am Ende selbst auf, sonst überschriebe es den Follow-up-Platzhalter nach
  jedem Auth-Update.
  `query-send.js` snapshottet die Registry-Basis beim Senden. Hat die neu
  erzeugte private `ChatSession` eine bestätigte `activeChatId` plus
  `activeTurnId`, wird
  **kein** Legacy-`context` gesendet. Stattdessen entsteht nach erfolgreichem
  `/prepare` der pending Follow-up-Turn; der Browser baut vor dem Provider-Fan-out genau
  einmal `/context` und hängt dasselbe
  `{chat_id, turn_id, context_version_id}` an alle sechs `/ask_*` sowie später
  an `/consensus`. `ready` und `degraded` sind gleichermaßen verwendbare,
  autoritative Versionen; `202 building` wird begrenzt wiederholt.
  Der Context übernimmt den vorherigen completed Turn in `historyTurns`; der
  Projektor rendert ihn als statischen Turn in `#threadHistory` und die neue
  Frage in `#threadAsk`. Sichtwechsel bauen beide Bereiche vollständig aus dem
  gewählten Context neu auf; der alte Live-Renderbaum ist nie die Datenquelle.
  Interaktive Marker der Archivkopie werden zu reinen Anzeigeelementen. Das
  archivierte Agreement
  nutzt mit einem wachsenden `.verdict-main` die volle Threadbreite; die
  Judge-Fußnote bleibt wie im Live-Footer kompakt inline. Differences, Quellen
  und Modellantworten werden mit dem Turn gespeichert und in der Archivkopie
  turnbezogen gerendert; Citation-Auflösung verwendet nicht den globalen
  `window.currentEvidenceSources`-Stand eines späteren Turns. „New comparison“/
  `clearResponseBoxes` leert nur den sichtbaren Verlauf; der Context eines
  laufenden Hintergrund-Runs bleibt erhalten.
- Alte Bookmark-Restores bzw. Reloads ohne aktive Chat-Zuordnung bleiben bis
  zur späteren History-Migration bewusst im Legacy-Pfad: `context` enthält
  genau das letzte `{previous_question, previous_consensus}`-Paar. Dieser Pfad
  erzeugt keinen irreführenden Chat, dessen Historie mit Turn 2 beginnt.
- Backend-Legacy: `normalize_followup_context` (`chat.py`) validiert und kappt beide
  Texte serverseitig (`followup_max_question_chars` /
  `followup_max_consensus_chars` in `LIMITS`). `/prepare` verarbeitet den
  Kontext bewusst gar nicht; die **Injektion
  passiert ausschließlich in `handle_ask`** via `build_followup_system_prompt`
  (`base.py`), damit der Kontextblock nie doppelt im Prompt steht und auch den
  `/prepare`-Fallback-Pfad des Frontends überlebt.

### Consensus & Differences

**Ergebnisintegrität (2026-09-29, Review R06/R09):**
`llm/completion.py` definiert den typisierten Abschlusszustand
`complete | token_limit | interrupted | error | cancelled`. Nur
`finish_reason=stop` bzw. das SSE-Ende `[DONE]` gilt als `complete`; ein EOF
ohne Bestätigung ist `interrupted`, `length` ist `token_limit`.
`/ask_*` liefert `completion` im finalen Payload. Eingaberegel für die
Synthese (`completion.usable_as_input`): `complete` wird normal verwendet,
`token_limit` als deutlich markierte gekürzte Antwort (`TRUNCATION_NOTE`,
häufig bei Reasoning-Modellen am 4096-Token-Budget), `interrupted`/`error`/
`cancelled` nie; das Frontend kennzeichnet gekürzte Antworten sichtbar und
unterbrochene als `incomplete` (`run-view.js`, Answer Reader), speichert
diese nicht per Bookmark als fertig und gibt sie nie an die Synthese. Eine
`/ask`-Antwort ohne gespeicherten Beleg wird im Browser sofort als nicht
verwendbar markiert. Lehnt `/consensus` Belege ab (400/409/503), wird der
wartende Chat-Turn auf `failed` gesetzt. `stream_chat_completion_text` endet mit einem
`completion`-Event; `stream_consensus` meldet eine abgeschnittene Synthese als
`final` mit `error` + `completion`, ohne stillen Retry, und sendet vor einem
Retry nach Fehler `consensus.reset` (Versuche mischen nie). `/consensus`
liefert `consensus_completion`; eine unvollständige Synthese erzeugt weder
Share-Result noch Chat-Completion (Turn → `failed`/`consensus_incomplete`).
`provider_transport.fan_out_provider_answers` (API/Watch/Topics) wendet
dieselbe Regel an.
**Antwortbelege (R09):** Jede erfolgreiche `/ask_*`-Antwort wird in
`answer_receipts/{id}` gespeichert (`services/answer_receipts.py`: UID,
Run-Bindung aus `usage_run_key` bzw. `run_id`, Frage-Hash, Familie, konkretes
Modell, Text, SHA-256, Quellen, `completion`, `provenance`
`developer|byok`, 24 h TTL, Retention-Sweep und Kontolöschung). Die Antwort
enthält `answer_receipt`. `/consensus` akzeptiert Modellantworten nur als
`answer_receipts: {familie: id}`; Freitext in `answers`/`answer_<familie>`
wird mit 400 `answer_receipts_required` abgelehnt, fremde, abgelaufene,
veränderte oder run-/frage-/familienfremde Belege mit 409. Text, Quellen und
Modelllabel stammen aus dem Beleg. Enthält ein Ergebnis eine BYOK-Antwort,
trägt `pending_results.answer_provenance="byok"`; solche (und ältere
Ergebnisse ohne Provenienz) zählen weder für `differences_stats` noch für
Votes/Leaderboard (`persistence_guard.record_model_vote` → `vote_not_eligible`).

**SSE-Abschluss und Browserdiagnose (2026-09-12):** `markdown-stream.js`
beendet den Reader mit dem autoritativen `final`-/`error`-Event; ein späterer
Netzfehler beim Warten auf EOF darf ein fertiges Ergebnis nicht verwerfen.
`consensus.final` bleibt ein Zwischenereignis: Differences und Persistenz
werden weiterhin bis zum gesamten `final` abgewartet. Ein EOF ohne Abschluss
ist ein expliziter Streamfehler. Consensus-Alerts unterscheiden über das
serverseitig allowgelistete `failure_kind` Request-, Read-, Eventhandler-,
unvollständige Stream- und sonstige Verarbeitungsfehler. Die Kategorie wird
in Telegram angezeigt und bei der Deduplizierung berücksichtigt; Freitext,
Stack und Nutzdaten werden am Browser-Intake weiterhin verworfen.

**Browser-Ausfallsicherung (2026-09-17):** Der SSE-Reader erkennt LF, CRLF und
CR auch über Chunk-Grenzen hinweg. Nach Request-/Read-/EOF-Fehlern prüft
`executeConsensusRun` höchstens dreimal innerhalb von fünf Sekunden den
ownergebundenen `GET /chats/{chat_id}/turns/{turn_id}` (ohne Cache).
Nur ein gespeicherter `completed`-Turn mit Consensus wird als Replay übernommen;
es gibt keinen erneuten Modell-POST, Vote oder Bookmark-Write. Authwechsel und
Cancel verwerfen späte Antworten. Ohne bestätigten Abschluss bleiben Teiltext
und Conversation-Fence erhalten; der ursprüngliche Fehler wird gemeldet.
Firebase-Tokenfehler beim Login, Auth-Refresh und Vote werden lokal behandelt;
ein Auth-Refresh-Fehler zeigt einen Verbindungs-/Reload-Hinweis.

`/app` lädt Marked, DOMPurify und KaTeX einschließlich Fonts aus `static/vendor/`
mit gepinnten Versionspfaden und Inhalts-Hashes. `scripts/vendor_frontend.mjs`
kopiert beim Frontend-Build die npm-Dateien und Lizenzen unverändert und prüft
sie bei `build:check` bytegenau. Das Build-Manifest umfasst auch diese Dateien.
Firebase bleibt ein externer gstatic-Import; öffentliche Seiten bleiben unverändert.

**Quellenprüfung v4 (2026-09-11):** Neue Consensus-Antworten enthalten keine
S-Quellenverweise. `llm/consensus_citations.py` entfernt unerwartete S-Zitate
inkrementell vor Streaming-Ausgabe, nachgelagerter Analyse und Speicherung;
literaler Code und Mathematik bleiben erhalten. Synthese-Prompts behalten die
Quelleninformationen der Modellantworten. Bestehende Antworten werden beim
Laden nicht umgeschrieben. `source_catalog.py` vereinheitlicht weiterhin lokale
Modell-IDs, dedupliziert URLs mit Modellprovenienz und erhält unbekannte oder
mehrdeutige Referenzen ohne erfundenen Link. Alle Modellquellen bleiben zugänglich.
Chat-/Bookmark-/Share-Normalizer behalten vollständige Quellenlisten; vorhandene
Request- und Dokument-Bytebudgets (750.000 Bytes für Turn/Modellantwort) gelten
weiterhin ausdrücklich, ohne stilles Abschneiden nach einer Quellenanzahl.

Der bestehende Differences-Aufruf liefert additiv
`differences[].factual_check = {checkable, question, reason}`. Präferenzen,
Empfehlungen und Schwerpunkte sind keine faktisch prüfbaren Streitfragen.
`consensus_anchor_validated` und `positions[].quote_models` entstehen aus der
serverseitigen Validierung der Originalpassagen. Fehlende/ungültige Metadaten
lösen keine automatische Prüfung aus. Agreement, Coverage, Consensus und die
ursprünglichen Modellpositionen werden durch Quellenbefunde nicht verändert.
`/resolve` bleibt eine getrennte, ausschließlich explizit gestartete Modellrunde.

`source_verification.py` dispatcht neue Pläne nach
`contradiction_verification.py`: Schema 4, `check_type: contradiction_evidence`,
`prompt_version: contradiction-evidence-v4`. Nur `contradiction` + `major`,
faktisch prüfbare Frage, gültiger Consensus-Anker und je Seite eine Haltung mit
mindestens einem antwortenden Modell werden aufgenommen. Das Modellzitat
verortet eine Seite nur und ist kein Beleg: Eine Seite ohne wörtlich
auffindbares Zitat (`located_by: stance`, leeres `quote`) blockiert die
Prüfung nicht mehr, sondern nutzt den gekennzeichneten Katalog-Fallback der
eigenen Modellquellen. `unverified_model_positions` bleibt für Seiten ohne
Haltung oder ohne antwortendes Modell.
Jeder Befund trägt stabile `contradiction_id`, `difference_index`, `run_id`,
`answer_version` und `positions_version`; Positionen heißen innerhalb eines
Streitpunkts P1, P2 usw. Die vorhandenen Quellen werden anhand der jeweiligen
Modellpassage und Referenzen zugeordnet; ein begrenzter Katalog-Fallback ist
als solcher gekennzeichnet. URL-Deduplizierung verwendet D-IDs nur innerhalb
der Prüfung, Quellen in Modellantworten behalten ihre S-IDs. Bei gemeinsamer
URL bleiben die relevanten Originalpassagen beider Seiten erhalten.

Vorab ausgeschlossene große Widersprüche bleiben in `exclusions[]` mit
Run-/Antwort-/Positionsbindung und allen Ausschlussgründen sichtbar; die
Scope-Felder `detected_contradictions`/`excluded_contradictions` zählen sie.
Fehlende Prüfbarkeitsangaben, ungültige Anker oder nicht zuordenbare Modellzitate
führen ohne verbleibenden Prüfauftrag zu `contradiction_inputs_unavailable`.
Die UI zeigt den Grund direkt an der Difference, getrennt von Quellenurteilen.
Abgelehnte Quellenurteile tragen außerdem bis zu zwölf `validation_errors`
mit festen Codes und ausschließlich bekannten Quellen-/Positions-IDs sowie
optionalem Belegindex. Die bisherigen Kategorien `evidence_mismatch` und
`invalid_output` bleiben kompatibel. Job-Persistenz und Polling erhalten die
konkreten Gründe; die UI zeigt sie direkt am Widerspruch, ohne abgelehnte
Rohzitate als Evidenz auszugeben.
Für alte v4-Snapshots ohne dieses Feld werden ausschließlich Anzeigehinweise
aus den gespeicherten Differences abgeleitet. Sachliche Termin-/Ereignisfragen
bleiben prüfbar; Fiktion wird nicht aus widersprechenden Modellantworten
unterstellt. Der Differences-Prompt nennt das aktuelle UTC-Serverdatum.

Ein einziges begrenztes Paket pro neuem Auftrag umfasst alle ausgewählten
Streitpunkte und URLs. Konfigurierbare Gesamtbudgets kommen aus
`SOURCE_VERIFICATION_MAX_CONTRADICTIONS` (4), `MAX_URLS` (8), `INPUT_TOKENS`
(24.000, konservative Obergrenze), `TOTAL_SECONDS` (60) und
`FALLBACK_SOURCES_PER_POSITION` (2); bestehende Input-/Ausgabe-/Abrufgrenzen
wirken zusätzlich. Ausgelassene Streitpunkte bleiben `state: omitted` mit
konkretem Budgetgrund; fehlende Quellen und Abruffehler bleiben getrennt.
Keine neue Websuche und keine zusätzliche Klassifizierungsrunde.

Urteile: `supports_position` mit benannter Position, `conditions_explain`,
`sources_conflict` oder `insufficient_evidence`. Substanzielle Urteile benötigen
wortgetreue Originalzitate aus gesendetem Auszug **und** abgerufenem Dokument,
mit validierter Quellen-/Positionszuordnung. Bedingungen, Datum, Geltungsbereich
und Einschränkungen gehören zum Judge-Vertrag. Quellenfehler und fehlende
Belege widerlegen keine Position; Modellmehrheit ist kein Quellenbeweis.

Consensus-Chat-Kontexte und seit 2026-10-03 Agent-Turns (je Vergleich, siehe
Agent-Abschnitt „check_contradictions“) geben UID und stabile Run-ID an
`source_check_jobs.py`. Start erst **nach erfolgreichem Differences-Abschluss**
in `consensus_pipeline.py` und im separaten Streaming-Pfad von `chat.py`.
`submit_source_check` nimmt optional eingefrorene `limits`, eine `binding`
(Felder für jeden Job-Snapshot) und `metering` (Kontobuchung, nur Agent).
`consensus.final` liefert vorher den Antworttext; `differences.final` beendet
den Vergleich. Danach können `sources.final` und das gemeinsame `final` einen
noch wartenden Jobverweis liefern. Der Antwortabschluss wartet nicht auf
Abrufe oder Judge. Neue ausgeschaltete Prüfungen speichern `status: disabled`;
Differences-Fehler speichern `failed`/`differences_failed`; ohne geeignete
Streitpunkte steht `skipped`/`no_checkable_contradictions`. Keiner dieser
Zustände besagt, dass die Antwort verifiziert sei.

Bestehende Job-/Owner-/BYOK-/Lease-/Recovery-Infrastruktur bleibt erhalten:
kompakter Firestore-Header, komprimierter Plan, separate Paketergebnisse, vier
Worker, 300-s-Leases und tokengebundene Result-Commits. V4-Idempotenz bindet Run,
Antwort, Positionen, Kontext, Quellen und eingefrorene Limits; Judge-Caches
trennen Modus/Schema/Prompt/Modell und validieren Treffer erneut. Abrufcache
bleibt tenantgebunden. Normale v4-Abruffehler werden nicht automatisch erneut
versucht und vervielfachen damit nicht das Gesamtbudget. Nach Prozessabbruch vor
Ergebnis-Commit beendet v4 die Wiederaufnahme ohne erneuten externen Call als
nicht verfügbar (keine Exactly-once-Garantie). BYOK bleibt nur im
Prozessspeicher, pausiert nach Schlüsselverlust und wird ownergebunden resumed;
kein Wechsel auf Entwickler-Keys. Vorhandene Account-/Parent-Löschgrenzen,
5-s-Read-RPCs und referenzgebundene Retention bleiben erhalten.

`source_documents.py` übernimmt unverändert den sicheren HTML-/Textabruf mit
DNS-/Redirect-Prüfung, IP-Pinning, TLS-Prüfung und Bytebudgets sowie die relevante
Originalpassagenauswahl. Keine Cookies, Proxies, Browserausführung oder Suche.
PDF bleibt ausdrücklich `unsupported_document`. Das Modell kommt weiterhin aus
`app_config/models.source_verification_model` (Default
`google/gemini-3.5-flash-lite`), wird bei Aufnahme eingefroren und im Admin unter
Consensus → Source Checks gewählt.
Das daneben wählbare `source_verification_fallback_model` ist standardmäßig
leer (`Disabled`) und erlaubt ein anderes Registry-Modell als Ersatz. Beide
Modellwahlen werden pro Job eingefroren; ältere Jobs ohne Fallback-Feld bleiben
deaktiviert. Nur Verfügbarkeitsfehler (HTTP 404/429/5xx, Netzfehler, Timeout)
lösen einen zweiten Versuch aus, nie ungültige Belege oder Credentials. Beide
Versuche teilen Gesamtzeit/Inputbudget und dieselben BYOK-/Owner-Credentials;
der erste erhält bei aktivem Ersatz höchstens die Hälfte der verbleibenden Zeit.
`runtime.model_attempts`, `runtime.model` und `fallback_used` dokumentieren die
Ausführung. Der Cachevertrag `verdict-dispatch-v1` bindet beide Modelle und
speichert deren Provenienz neben der weiterhin separat validierten Ausgabe.
Transaktionale Cachewrites erfolgen nach dem erfolgreichen Ergebnis-Commit,
außerhalb der Prüfdeadline. Ein erneut übernommenes v4-Paket mit ungewissem
vorherigem Abschluss wird als `worker_interrupted` gespeichert, ohne nochmals
bezahlte Modellaufrufe auszulösen; Credential-Pausen bleiben wiederaufnehmbar.
Bekannte Fehler erhalten stattdessen den lease-gebunden gespeicherten Grund
`worker_preparation_failed`, `worker_execution_failed` oder
`result_persistence_failed` aus `last_failure` für genau diesen Paketindex.
Die Quellen-UI benennt die Fehlerphase; rohe Exceptions werden nicht gespeichert.

Neue Jobs sind physisch nach Dispatch-Protokoll und Umgebung getrennt:
`source_check_jobs_dispatch_v1_local` / `_production`. Render oder
`ENVIRONMENT=prod/production` wählt Production, sonst Local. Beide Werte binden
die Job-ID und stehen im Header; Worker scannen/claimen nur ihre eigene Queue.
Inkompatible Plan-/Limits-Verträge benötigen eine neue Dispatch-Version,
kompatible Releases behalten wartende Jobs. Die alte globale Collection
`source_check_jobs` und die andere Umgebung bleiben begrenzt lesbar (höchstens
drei bekannte Collections, positiver Routingcache), einschließlich Polling,
Shares, Retention und Accountlöschung. Es gibt keine automatische Migration
oder Wiederholung alter Ergebnisse. Fremde BYOK-Queues können nicht auf den
aktuellen Worker umgebogen werden; `/resume` liefert nach Ownerprüfung HTTP 409.
Die physische Trennung schützt auch vor alten Workern ohne Versionsprüfung.

Polling (seit 2026-10-03): Firestore berechnet jede Query, auch eine leere.
Vier Worker mit je einem Scan alle 2 s kosteten ~170k Reads am Tag pro
Prozess (lokale Dev-Server eingeschlossen). Jetzt scannt im Leerlauf nur ein
„Scout“-Worker, mit Backoff von `IDLE_POLL_MIN` 2 s bis `IDLE_POLL_MAX` 30 s;
`submit_source_check`/`resume_source_check` wecken per `wake_workers()` alle
vier sofort, gefundene Arbeit hält alle beschäftigt, bis die Queue leer ist.
Retries mit Verzögerung (15/31 s) werden spätestens beim nächsten Scout-Scan
übernommen. Der Worker-Heartbeat (`source_check_workers/{id}`) wird nur noch
geschrieben, solange dieser Prozess einen BYOK-Schlüssel hält (oder erzwungen
bei Submit/Resume mit eigenem Key): nur dafür liest `claim()` ihn.

Neue Chat-/Bookmark-/Share-Snapshots speichern den v4-Jobverweis;
Wiederöffnen startet keinen neuen Judge. Owner-Polling bleibt paginiert und
revisionsgebunden; öffentliche/API-Endpunkte prüfen außerdem die jeweilige
Antwort-/Run-Bindung. `share_snapshots.py` erhält die neuen Differences-Metadaten.
Legacy v1/v2/v3-Befunde und deren Bedeutung bleiben lesbar; der v3-Prüfmodus
für zitierte Satz-/Quellen-Paare bleibt zur Verarbeitung alter Pläne erhalten.

`static/js/source-verification.js` exportiert `window.App.sourceVerification`
(`render`, `renderCurrent`, `clear`, `openResults`, `watch`, `observe`, `applySourceList`,
`getCitationCheck`, `refreshDifferences`, `bindDifferenceCard`). Ladung nach
`consensus-anchor.js` in `bundles.json`, außerdem auf öffentlichen Ergebnissen.
RunContext: `consensus.sourceVerification`. V4-Ergebnisse erscheinen direkt
bei ihrer Contradiction, mit validierten Belegpassagen und Quellenlinks.
Die kompakte Ergebniskarte trennt Prüfstatus, Urteil und Begründung; bei
Fehlschlägen, unzureichender Evidenz und ausgeschlossenen Prüfungen erklärt
ein kurzer Hinweis, wie der Nutzer den offenen Widerspruch einordnen kann.
Nur ein mit Evidenz belegtes, gültiges Positions-/Bedingungsurteil erhält
den positiven Status. Die 2,8-sekündige Navigationsmarkierung liegt innerhalb
der Karte, damit Scrollcontainer sie nicht abschneiden; Reduced Motion und
Forced Colors verwenden ebenfalls eine innenliegende Markierung.
Neue Runs setzen zusätzlich `consensus.sourceReferenceMode: none` und am
Antwortcontainer `data-source-references="none"`. Dadurch macht die Darstellung
aus numerischen `[1]`-Notationen keine Quellenlinks; Modellantworten und Legacy-
Consensus behalten ihre Verweise. Source-Check-Hooks sind vom Aufbau der
Differences-Karten/Claim-Marker getrennt abgesichert. Der Prüfstatus bleibt
sichtbar, `View evidence` klappt die Originalpassagen bei Bedarf auf und behält
seinen Zustand bei Polling. `factual_check` ist ausschließlich Prüfmetadatum;
es filtert weder Differences noch Claims oder deren Agreement-Beitrag.
Positions-/Ankervergleich und Run-/Antwortbindung verhindern Zuordnung zu
einem anderen Streitpunkt; Polling erneuert Befunde, ohne Texte/Agreement
neu zu berechnen. Topics ohne bestehende Karten erhalten gebundene
Streitpunktkarten im Bericht. Legacy-S-Citation-Bericht, Hover, Quellenfarben
und `applySourceList` behalten die ursprüngliche v1–v3-Semantik.
Details, Budgets und Abnahme: [source-verification.md](source-verification.md).

**Pipeline-Härtung (2026-09-07):**
- Synthese und beide Judges verwenden denselben Antwort-Cap aus
  `get_consensus_answer_char_limit()` (Default 40.000 Zeichen je Modell).
  Die separate Judge-Kürzung auf 6.000 Zeichen entfällt. Der Satzindex bleibt
  auf 80 Einträge begrenzt; weitere prüfbare Sätze werden vollständig gezählt
  und als `evidence_coverage.unindexed_sentences` ausgewiesen. Antworten am
  Eingabe-Cap werden konservativ als `truncated_answers` markiert.
- Agreement und Abdeckung sind getrennt: `coverage_percent` zählt Claims mit
  mindestens zwei behandelnden Modellen relativ zu allen Claims einschließlich
  nicht indexierter Sätze. Unter 50 % oder ohne auswertbaren Claim gilt
  `coverage_status=insufficient`, `score=null`, `level=insufficient`.
  Bei 50–79 % oder gekürzter Beweisbasis gilt `limited` und höchstens 64/100;
  ab 80 % ohne Eingabelücke gilt `sufficient`. Dies sind konservative
  Produktgrenzen, keine kalibrierte Wahrscheinlichkeit sachlicher Richtigkeit.
  App und Shares zeigen die Abdeckung separat. Snapshots erhalten alle 80
  Claims, Coverage-Judge-Metadaten, `evidence_coverage`, `analysis_runtime`
  sowie `scored_claims`/`thin_claims`/`total_claims` und den Null-Score.
  Watch/Topic-Verläufe akzeptieren fehlende Scores; daraus entstehen weder
  künstliche Nullpunkte noch numerische Drift-Alarme.
- `llm/provider_runtime.py::analysis_budgeted` bindet ein gemeinsames,
  threadsicheres Budget von Synthesestart bis zum Abschluss beider Judges.
  Default: 180 Sekunden und höchstens acht externe Analyse-Aufrufe insgesamt
  (einschließlich Fallbacks und Coverage-Repair), konfigurierbar über
  `ANALYSIS_TIMEOUT_SECONDS` (10–600) und `ANALYSIS_MAX_CALLS` (3–12).
  Der Browser-SSE-Producer und `consensus_pipeline.analyze_provider_answers`
  bilden die äußere Grenze; einzelne Engine-Einstiege erhalten denselben
  Schutz bei direkter Nutzung. Der davor liegende Antwort-Fan-out bleibt
  durch seine bestehenden Provider-Limits geschützt.
- Nicht streamende Engine-Aufrufe und Analyse-SSE verwenden HTTPX-Tasks auf
  dem vorhandenen synchronen Provider-Worker. Disconnect und Deadline brechen
  auch das Warten auf HTTP-Header oder weitere Body-Daten ab; es entstehen
  keine zusätzlichen Netzwerk-Worker und keine Transport-Retries. Das Budget
  wird explizit an den Coverage-Thread weitergegeben. `analysis_runtime`
  enthält sämtliche bezahlten Versuche und die gesamte Analyse-Laufzeit;
  Judge-`duration_ms` umfasst Wiederholungen und beim Coverage-Judge Repair.
  Providerseitig bereits verbrauchte Tokens können durch Abbruch nicht
  rückwirkend erstattet werden.

- Im App-Layout steht `#consensusOutput` oberhalb der Modellantworten: Das
  synthetisierte Ergebnis ist die Primäransicht, die einzelnen Antworten sind
  darunter die prüfbare Grundlage.
- **Inline-Confidence statt Zwei-Spalten (seit 2026-07-24):** `.consensus-box`
  ist einspaltig. Die Antwort (`.consensus-main`, volle Breite) rendert in den
  stabilen Container **`#consensusAnswerBody`** — einziges Render-/Streamziel,
  Zugriff ausschließlich über **`window.App.consensusBodyEl(scope?)`**
  (das alte `.consensus-main p` gibt es nicht mehr). Darunter liegt der
  kompakte Antwort-Footer; Markierungsfilter werden ausschließlich über
  Settings → Display gesteuert (Default: Disagreements & issues, siehe oben).
  Der zugeklappte
  `<details id="consensusDifferencesPanel" class="consensus-differences
  consensus-differences-panel">`; `#differencesCards` und das Karten-Rendering
  sind inhaltlich unverändert. `window.App.differencesPanel.{setSynthesizing,
  expandForFallback}` steuert offen/zu: während der Synthese offen (Spinner),
  danach zu (strukturierte Karten) bzw. offen (Freitext-Fallback).
  Der Consensus-Prompt glättet Uneinigkeit nicht mehr weg und rahmt die
  Synthese als journalistische, eigenständige Abwägung statt als mechanisches
  Mehrheitsvotum. Eigenes Modellgedächtnis darf dabei aktuelle, in den
  Antworten belegte Informationen nicht allein wegen möglicher Cutoff-Lücken
  verwerfen (Prompt-Version **V3**, siehe `docs/benchmark-plan.md`). Der Verdict-Header nennt das
  strittige **Thema** statt einer Zählung (deterministisch aus
  `differences[].claim`, kein zusätzlicher LLM-Call). Hintergrund und
  Entscheidungen: `docs/consensus-inline-confidence-brief.md`.
  Die lokale Produkt-Demo spiegelt denselben Coverage-Vertrag: Jeder ihrer 19
  prüfbaren Consensus-Sätze besitzt einen expliziten `supported`-/`split`-Claim;
  Difference-Marker übersteuern an überlappenden Sätzen weiterhin das Badge.
- `executeConsensusRun(context)` (`consensus-run.js`) liest Modellantworten,
  `excluded_models`, Modelllabels, Quellen und `consensus_model` ausschließlich
  aus dem gebundenen Context und ruft **`POST /consensus`** (`stream:true`) mit
  dessen `usage_run_key`. Ein späterer Sicht-/Picker-Wechsel kann den Payload
  deshalb nicht verändern. Der Endpoint validiert/konsumiert den Run
  idempotent und erzeugt keine zweite Usage-Einheit. `getConsensus` delegiert
  für einen aktiven Registry-Run dorthin; sein DOM-basierter Pfad ist nur noch
  Legacy/Demo.
- **Chat-Turn-Persistenz und Context-Verdrahtung (Sessions 5–6):** Nach
  erfolgreichem `/prepare` legt `query-send.js` den logischen Run fest. Nur bei
  einer aktiven Fortsetzung erzeugt die private ChatSession des Contexts den
  pending Turn bereits
  **vor** Context-Build und Provider-Fan-out, weil der autoritative Context an
  diesen Ziel-Turn gebunden wird. Bei einer frischen Frage entstehen Chat und
  Turn erst, wenn `getConsensus` tatsächlich aufgerufen wird; ein Lauf ohne
  Consensus hinterlässt dadurch keinen Turn-1-Orphan. Bei einer Fortsetzung
  wird ausschließlich die durch den letzten completed Turn bestätigte
  `activeChatId` verwendet. `activeChatId` + `activeTurnId` bezeichnen innerhalb
  genau dieser ChatSession immer eine completed Basis; der neue Lauf liegt bis
  zur autoritativen Completion
  separat in `pendingChatId`/`pendingTurnId`. Der Turn-Request enthält nur
  `question`, `mode`, `deep_search`, `selected_models`, `consensus_model` und die
  pro logischem Run stabile `client_request_id`.
- Im Own-Key-Modus validiert `query-send.js` vor Usage-Reservierung, `/prepare`
  und Turn-Anlage den einen lokalen OpenRouter-Key. Fehlt er, bleibt der completed
  Vorgänger unverändert und es entsteht kein pending Turn.
  Bei aktiven Fortsetzungen ruft `query-send.js` danach genau einmal den
  Context-Endpoint. Developer-Läufe senden denselben bereits durch `/prepare`
  konsumierten `usage_run_key`; Own-Key-Läufe senden denselben `openrouter_key`
  an Context, Antworten, Consensus und Resolve. Keys gehen nie an `/prepare`. Erst nach einer fertigen
  `ready|degraded`-Version beginnt der Fan-out; alle `/ask_*` laden dieselbe
  Version und komprimieren nicht selbst.
- Mit Chat-IDs sendet `executeConsensusRun` zusätzlich die contextgebundenen
  `turn_sources` sowie
  bei fortgesetzten Turns dieselbe `context_version_id`.
  `/consensus` akzeptiert IDs nur paarweise im 32-Hex-Format, prüft UID,
  Chat/Turn, Status, normalisierte Frage und die exakte Context-Verknüpfung
  read-only **vor** dem teuren Engine-
  Call. Weil `/consensus` die Frage auf `consensus_max_question_chars` kappt,
  gilt genau dieselbe Grenze beim Anlegen des Turns (`_question_max_length`):
  ein Turn mit längerer gespeicherter Frage könnte sonst nie abgeschlossen
  werden, weil die gekappte Frage nicht mehr passt und jeder Retry dauerhaft
  an 409 scheitert. Der Tarif-Check bleibt davon unberührt — Premium-Engines
  sind Pro-exklusiv **auch** mit `useOwnKeys=true`: eigene Keys bezahlen den
  Call, heben das Tier-Gate aber nicht auf. Nach dem Ergebnis baut `/consensus`
  aus den bereits gekappten `included_answers`,
  serverseitig erlaubten Labels und providerbezogenen Quellen das vollständige
  `ChatStore.complete_turn`-Payload. Completion erfolgt genau einmal im
  jeweiligen erfolgreichen Streaming-/JSON-Pfad, erst nach finalem Consensus,
  finalen Differences und dem optionalen `result_id`. Responses mit IDs tragen
  zusätzlich die autoritative Disposition `chat_turn_state=completed|failed|pending`:
  Nur `completed` zusammen mit `chat_persisted=true` promotet `pendingChatId` zu
  `activeChatId`; `failed` verwirft den lokalen pending State, `pending` erhält
  IDs und stabile `client_request_id` für einen Retry. Allgemeine UI-
  Fehlerklassifikation ist keine Persistenzwahrheit.
- Ein completed Preflight liest das vollständige owner-gebundene Turn-Detail
  und gibt gespeicherten Consensus, Differences, `differences_data`, Quellen,
  Modellantworten und `result_id` direkt wieder (`chat_replayed=true`): JSON normal, bei Streaming
  als kurzer kompatibler `consensus.final`-/`final`-SSE-Ablauf. Dabei laufen
  weder LLMs noch `complete_turn`, Share-Snapshot, Differences-Statistik oder
  `/consensus`-Usage-Consume. Er läuft vor der aktuellen Modell-Allowlist sowie
  Tier- und Credential-Prüfung, damit ein gespeichertes Ergebnis auch nach
  Modell-, Tarif- oder Key-Änderungen lesbar bleibt. Der Browser rendert und
  promotet den Replay, unterdrückt dabei aber Bookmark-Dual-Write, Best-Model-
  Vote, Completion-Analytics und Watch-Nudge. Nach einem mehrdeutigen lokalen Transportabbruch
  liest der Browser zuerst den owner-gebundenen Turn: `completed` wird über
  diesen Replay-Pfad dargestellt, `failed` autoritativ verworfen und `pending`
  mit denselben IDs sowie demselben Usage-/Request-Key wiederholt.
  Ein completed Alt-Turn ohne Consensus wird sicher abgewiesen und niemals
  still neu berechnet.
- Terminale Consensus-Fehler markieren den validierten pending Turn best effort
  mit einem allowgelisteten Code; zu wenige serverseitige Antworten verwenden
  `insufficient_answers`, ein zuverlässig erkannter Stream-Abbruch `cancelled`.
  Hat eine aktive Fortsetzung nach dem Fan-out weniger als zwei Antworten,
  sendet der Browser eine dispositionsbezogene `/consensus`-Anforderung. Der
  Server prüft und markiert den Turn noch vor aktueller Modell-/Tierprüfung,
  Engine-/Credential-Auflösung und ohne weitere Usage-Einheit als failed; es
  bleibt kein solcher pending Orphan.
  Nur nach erfolgreichem `fail_turn` lautet die Disposition `failed`; korrigierbare
  frühe Fehler und ein gescheitertes `fail_turn` lassen sie retrybar. Scheitert
  nur `complete_turn`, bleibt der Turn pending/retrybar und der fertige Consensus
  wird mit `chat_persisted=false`, `chat_turn_state=pending` ausgeliefert. Fehler von
  `POST /chats` oder `POST /turns` blockieren einen aktiven Follow-up vor dem
  Fan-out; eine frische erste Frage darf bei ausgefallener optionaler Persistenz
  weiterhin ohne Chat-Bindung laufen. Ein lokaler Abort behauptet keine
  serverseitige Terminalität und erhält bekannte pending IDs. Der Server bricht
  den zugehörigen SSE-Providerlauf kooperativ ab und persistiert kein nur
  teilweise erzeugtes Ergebnis. Ein Abbruch oder
  Verlassen der Seite nach der frühen Follow-up-Turn-Anlage, aber vor einer
  autoritativen `/consensus`-Disposition kann daher weiterhin einen pending
  Turn hinterlassen; ein Retry im laufenden Browser ist durch die stabile
  `client_request_id` abgesichert. Dafür gibt es bewusst noch keinen Cleanup-Job.
  Ein nicht completed Chat wird nie als persistierte Grundlage
  eines folgenden Follow-ups verwendet.
- Die bisherigen `saveBookmark(...)`-/`saveBookmarkConsensus(...)`-Aufrufe
  bleiben als Dual-Write für Sidebar, Restore, Share und Watch aktiv. Innerhalb
  eines Browser-Chats verwenden alle Turns dieselbe stabile Bookmark-ID; nach
  erfolgreicher Chat-Completion speichert das Bookmark nur `chat_id`/letzte
  `turn_id`, und der Restore liest den vollständigen kanonischen Transcript
  paginiert aus `ChatStore`. Ein altes Bookmark ohne Chat-Bindung bleibt im
  Legacy-Ein-Turn-Kontextpfad und erzeugt keinen irreführenden Chat, dessen
  Historie mit Turn 2 beginnt.
- **Multi-Turn-Context (Session 4 Backend, seit Session 5 im Browser aktiv):**
  `POST /chats/{chat_id}/turns/{turn_id}/context` liest ausschließlich frühere
  owner-gebundene completed Turns. Bei Zielposition 2 bleibt der jüngste
  completed Turn als begrenzter Wortlaut-Kontext erhalten; ab Zielposition 3
  wird genau einmal pro Context-Version die ältere Historie in strukturierte
  Memory (`decisions`, `constraints`, `entities_facts`, `open_questions`,
  `user_preferences`, `uncertainties`, `corrections`) überführt, während der
  jüngste completed Turn separat bleibt. Deterministische Version-ID,
  Build-Lease und Ziel-Turn-Verknüpfung machen Retries idempotent; `/ask_*`
  laden die fertige Version nur noch und führen keine Komprimierung aus.
  Die Auflösung bleibt bewusst serverseitig pro Call (der fertige Kontext darf
  nie über den Client laufen und dort manipulierbar werden), aber alle sechs
  `/ask_*`-Calls eines Laufs treffen denselben `ResolvedContextCache`
  (prozesslokal, owner-gebundener Schlüssel, 120 s TTL, max. 128 Einträge).
  Damit kostet ein Follow-up-Turn ~3 statt ~18 Firestore-Reads und ein Rendern
  statt sechs. Fehler werden nie gecacht, damit ein Konflikt nicht für die
  Dauer der TTL einfriert; eine fertige Context-Version ist unveränderlich,
  ein Treffer kann also nie einen überholten Kontext liefern.
  Ein completed Ziel-Turn kann nur seine bereits verknüpfte fertige Version
  wiedergeben und erhält nie nachträglich einen neuen Context-Build.
  Harte Budgets sind 24.000 Context-Zeichen, 8.000 Memory-Zeichen, 14.000 für
  den jüngsten Turn und 2.500 Output-Tokens. Komprimierungs-/Credentialfehler
  erzeugen eine gekennzeichnete deterministische Fallback-Version und ändern
  keine Roh-Turns. Der Developer-Modus akzeptiert nur einen bereits durch
  `/prepare` konsumierten `usage_run_key`, bindet dessen Usage-Dokument per
  SHA-256-Zielhash idempotent an genau diesen Chat/Turn und erzeugt keinen zweiten Slot;
  Own-Key nutzt ausschließlich `openrouter_key`, speichert/loggt ihn nicht und
  fällt bei Fehlen niemals auf den serverseitigen OpenRouter-Key zurück.
- **Reasoning-Schalter** (seit 2026-10-02, ersetzt Deep Think; für alle
  Stufen, kein Pro-Gate): `#reasoningToggle` im (+)-Menü bzw.
  `#composerReasoningToggle` in der Startleiste. Ein lässt dieselben gewählten
  Antwortmodelle länger nachdenken: kein Pro-Modell-Tausch, kein Zusatzprompt,
  weiter eine Suchrunde, Consensus-Engine unverändert. Serverseitig füllt
  `cfg.effective_model_reasoning(..., reasoning=True)` nur eine noch offene
  Modell-Policy mit `REASONING_EFFORT_ON` („high"); explizite Policies
  (`MODEL_REQUEST_CONFIG`) und Mistral-Defaults gewinnen, `cap_model_reasoning`
  (Admin-Sparprofil) gilt weiter. Output-Cap: `max(Stufenlimit,
  reasoning_max_tokens)` (`get_output_token_limit(tier, True)`); das Wortlimit
  hängt nicht am Schalter. Der Lauf wird gegen die Reasoning-Schätzung
  admittiert. **Kompatibilitätsnamen (bewusst behalten):** Wire-/Persistenzfeld
  `deep_search` (`/ask_*`, `/prepare`, `/consensus`, Chat-Turns,
  Run-Config `config.deepSearch`), `deep_think` (API-v1-Alias, Usage-Payload,
  Schätzungs-Key in `app_config/agent_budget`, `RunKind.DEEP_THINK`) — sie
  bedeuten heute „Reasoning an". Bookmarks akzeptieren weiter `mode: "Deep Think"`
  (alte Einträge laden ohne den Schalter anzufassen); neue Läufe schreiben
  immer `"Standard"`. Ein altes Firestore-Feld `deep_think_model` und die alten
  `free_/pro_deep_search_max_*`-Limits werden ignoriert
  (`pro_deep_search_max_tokens` wird einmalig zu `reasoning_max_tokens`).
- Backend (`chat.py::consensus` → `consensus_pipeline.py` →
  `consensus_engine.py`): validiert (mind. **2**
  eingeschlossene Antworten), kappt Frage/Antworten serverseitig
  (`cap_engine_text`, Limits `consensus_max_answer_chars` /
  `consensus_max_question_chars` — Kosten-/Abuse-Schutz, da die Texte vom
  Client kommen), prüft Engine-Keys, dann `stream_consensus` gefolgt von
  `stream_differences`. **SSE-Events**: `consensus.delta`, danach unmittelbar
  `consensus.final {text}` als autoritativer Abschluss der Synthese, anschließend
  `differences.delta` (Frontend rendert Differences-Deltas nicht), dann
  `final {consensus_response,
  differences, differences_data, result_id?, …usage}`. Das Frontend sichert
  `consensus.final` sofort: ein späterer Judge-, Rendering- oder Mobilnetzabbruch
  darf die fertige Antwort nicht mehr durch den generischen Consensus-Fehler
  ersetzen, sondern degradiert nur die Differences-Anzeige. Während Reasoning-Phasen
  tragen die Delta-Events gedrosselt `{reasoning: true}`; ein SSE-Wrapper sendet
  zusätzlich Kommentar-Keepalives, wenn eine Engine länger keine Bytes liefert.
  `differences_data` ist
  strukturiertes JSON (Verdict, Karten, `best_model`, `models_compared`).
  Jeder Eintrag in `differences[]` trägt zusätzlich **`consensus_anchor`**: die
  Stelle in der KONSENSANTWORT (nicht in einer Modellantwort), an der der
  Widerspruch hängt; das Frontend markiert damit den Satz inline.
  `positions[].quote` bleibt unverändert ein Zitat aus der jeweiligen
  Modellantwort. Alte Bookmarks/Snapshots ohne das Feld degradieren auf „nur
  Karte".
  **Satz-Index (seit 2026-08-07):** Der Judge schreibt Anker nicht mehr ab.
  `_enumerate_consensus_sentences` nummeriert die prüfbaren Sätze der
  Konsensantwort sowie einzelne Datenzellen von Markdown-Tabellen (auch kurze
  Werte; beide Judges berücksichtigen Spaltenüberschrift und Zeilenkontext).
  Tabellenköpfe und Trennzeilen bleiben Kontext; Zellenanker überschreiten
  keine Zellgrenzen. Überschriften, Code und **abgesetzte Formeln**
  — `$$…$$`, `\[…\]` — bleiben außen vor. Listenzähler und `[S1]`-Tags gehören
  nicht zum Fließtext-Satz. Der Index stellt jedem Eintrag ein `[n] ` voran;
  der Judge liefert nur noch `claims[].s` bzw. `differences[].s` (`0` = der
  Konsens sagt dazu nichts), der Server setzt daraus den exakten Originalsatz
  in `anchor`/`consensus_anchor` ein. Der Anker ist damit per Konstruktion
  auffindbar und kostet ~2 statt ~60 Output-Tokens — erst das finanziert
  `MAX_DIFF_CLAIMS = 20` (vorher 8) und die Prompt-Regel „jeder prüfbare Satz"
  statt „die 3–6 zentralen". Die wörtliche Abschrift bleibt als Lesepfad für
  ältere Payloads erhalten. Ein Claim braucht **mindestens zwei** beteiligte
  Modelle (`MIN_CLAIM_SUPPORT`): „1/1 — all models agree" liest sich wie eine
  Bestätigung, ist aber nur eine Stimme, und verzerrte zusätzlich den
  Agreement-Score. Jeder nummerierte Eintrag behält zusätzlich `sentence_id`
  und die nullbasierte `anchor_occurrence`; beide Felder passieren die
  Snapshot-Whitelist und bleiben damit in Chats, Bookmarks und Shares erhalten.
  Doppelte Dissent-Einträge desselben Modells zählen nur einmal. Zwei Claims
  auf demselben Satz werden serverseitig auf den
  am wenigsten gestützten zusammengezogen (dieselbe Regel, die das Frontend
  für die sichtbare Quote anwendet).
- Kritische Fehleralarmierung: Schlagen alle ausgewählten Modellrequests fehl,
  meldet `query-send.js` genau einen zusammengefassten `run_failed`-Alert. Ein
  Consensus-Abbruch wird nur gemeldet, wenn kein verwertbarer Consensus-Text
  erhalten blieb; bewusste Stop-/Skip-Aktionen und Usage-Limits bleiben ruhig.
  Ungefangene Backend-Exceptions erzeugen zusätzlich über den globalen
  Exception-Handler einen serverseitigen Alert und antworten weiterhin nur mit
  einem neutralen HTTP 500 (mit `x-correlation-id`). Aufbau, Dedup und Budgets
  der Alerts: „Kritische Fehler-Alerts (Telegram)“ unten.
- Robustheit Differences (`consensus_engine.py`): einheitlicher Engine-Dispatch
  (`_resolve_engine`/`_call_engine_text`/`_stream_engine_text`) über OpenRouter
  Chat Completions. Strukturierte Aufgaben senden in Streaming- und
  Non-Streaming-Pfaden das jeweilige JSON-Schema als
  `response_format=json_schema` mit `strict=true`; der gemeinsame Parser
  validiert danach weiterhin die Pflichtfelder `differences` und
  `best_model` und repariert begrenzt abgeschnittenes JSON. Die Belegliste
  (`claims`) verlangt dieses Schema seit 2026-08-31 NICHT mehr: sie kommt aus
  dem Coverage-Judge (siehe unten). Alt-Payloads mit `claims` laufen weiter
  durch `_normalize_claims`.
  Judge-Policy (`_resolve_differences_engine`): die Judge-Familie ist immer
  eine ANDERE als die der gewählten Consensus-Engine (Self-Judging-Bias);
  die Stufe folgt der Engine — Standard-Engine → Standard-Judge
  (`DIFFERENCES_JUDGE_MODEL_BY_PROVIDER`), Pro-Engine → Pro-Judge über die
  Engine-Aliasse (`<Familie>-Pro`). Attempt-Plan: primärer Judge, Retry,
  nächste Fremd-Familie (Pro fail-opent zuletzt auf einen Standard-Judge);
  ohne Fremd-Key fail-open auf den eigenen Standard-Judge. Nicht
  wiederholbare Providerfehler (400/401/403/404) überspringen den identischen
  Retry und gehen direkt zur nächsten Familie; 429/5xx/Transportfehler sowie
  unparsbares JSON dürfen weiter retryen. Der tatsächlich
  genutzte Judge steht als `differences_data.judges.differences`
  ({provider, model, tier, attempts, duration_ms}) im Payload/Snapshot und in
  der Telemetrie. Judges laufen mit providerkompatibler niedriger
  Reasoning-Effort-Kappung (normalerweise `low`, für Mistral `none`; ein
  explizites `MODEL_REQUEST_CONFIG` wie „Reasoning aus“ bleibt vorrangig);
  die Consensus-Synthese selbst behält die volle Modell-Denktiefe.
  das Frontend zeigt ihn als Fußnote im Verdict-Header. Außerdem:
  JSON-Truncation-Repair aus `consensus_parsing.py`, serverseitige Anchor-/Quote-Verifikation gegen
  Konsens- bzw. Modellantworten (nicht belegbare Zitate werden geleert).
  Die Normalisierung hält auch bei Unicode-Lowercase-Erweiterungen (`İ`) einen
  Original-Offset je Ausgabezeichen vor; exakte, fuzzy und Markdown-bereinigte
  Zitatsuche teilen diesen Vertrag. Das verhindert verschobene Zitate und den
  am 18.09.2026 protokollierten `IndexError` in `_locate_span`.
  Belegstatus (`quote_models`, erhaltene Dissent-Zitate,
  `consensus_anchor_validated`) setzt nur eine VOLLSTÄNDIGE normalisierte
  Deckung; toleriert werden ausschließlich Groß-/Kleinschreibung,
  typografische Anführungszeichen/Striche (inklusive ASCII-Apostroph, ‚ ‹ ›),
  Whitespace, unsichtbare Zeichen (weiches Trennzeichen, Zero-Width),
  Randauslassungen sowie Markdown-Layout: Fett, Kursiv, Durchstreichung,
  `[S#]`/Links und Zeilenmarker (Aufzählung, kurze Ordnungszahl, Überschrift,
  Blockzitat). Wörter, Zahlen, Negationen, Code und `snake_case` bleiben
  wörtlich; eine Auslassung in der Mitte zählt nie. Ein verworfenes
  Positionszitat trägt `positions[].quote_rejection = {reason, matched_share}`
  (`no_answer`, `internal_ellipsis`, `reworded`, `not_found`) ohne Textinhalt.
  Fuzzy-Suche (`allow_fuzzy=True`) dient nur der Navigation (Claim-Anker,
  nicht validierter Widerspruchs-Anker) und vergibt nie einen Belegstatus.
  Unparsbares JSON erreicht den Nutzer nie als Rohtext.
- Coverage-Judge (`coverage_judge.py` + `consensus_engine._run_coverage_judge`,
  seit 2026-08-31): belegt JEDEN nummerierten Konsens-Satz statt der "3-6
  zentralen". Läuft PARALLEL zum Differences-Judge in einem eigenen Thread
  (`_coverage_in_background`, Cancellation wird ausdrücklich mitgebunden), auf
  einer Fremd-Familie in der STANDARD-Stufe — die Aufgabe ist kontrollierte
  Klassifikation, kein Denken. Der Zwang gegen stilles Überspringen steckt in
  drei Schichten: (a) das Structured-Output-Schema führt die Satz-IDs als Enum
  und JEDES Modell-Label als Pflicht-Property von `models`; (b) der Prompt
  enthält die verbindliche ID-Liste; (c) der Server vergleicht die Antwort
  gegen diese Liste (`missing_sentence_ids`) und fordert Fehlende in GENAU
  einem gezielten Repair-Call nach. Was danach offen bleibt, wird neutral als
  `coverage: "thin"` gerendert statt weggelassen. Klassifikationen:
  `claim` (wird markiert) / `not_a_claim` / `too_vague` / `context_only`;
  Stances je Modell: `supports` / `contradicts` / `not_addressed` / `unclear`.
  Ergebnis landet als `differences_data.claims` (unveränderte Feldform plus
  `coverage`) und der Judge als `differences_data.judges.coverage`
  ({provider, model, tier, attempts, duration_ms, sentences, covered,
  repaired, missing}). Fällt der Coverage-Judge komplett aus, bleibt der Lauf
  intakt und die Antwort einfach ohne Marken — besser als jeder Satz grau.
- Agreement-Score (`consensus_scoring.py::compute_agreement_score`): 0-100 oder null bei unzureichender Abdeckung aus Claim-Zustimmungsquoten
  minus severity-gewichteter Widerspruchs-Penalty (major 0.25 / minor 0.10 /
  emphasis 0.05), mit Caps ("very" nur ohne Differenzen; 1 Major → max
  "partially", 2+ Major → max "hardly"; 2 Modelle → max 75). Liegt als
  `differences_data.agreement` im Payload/Snapshot; der Legacy-Credibility-Satz
  wird daraus abgeleitet (nie divergierende Verdicts). Widersprüche tragen
  `severity` ("major"/"minor", Default major); Frontend zeigt Score im
  Verdict-Header; dessen Überschrift und Ampelfarbe folgen ausschließlich dem
  Score, während "critical"/"minor detail" und das betroffene Thema separat
  den Widerspruchsstatus zeigen. Claims mit weniger als
  `MIN_SCORED_CLAIM_SUPPORT` (2) behandelnden Modellen gehen NICHT in den Score
  ein (`scored_claims`/`thin_claims` weisen das aus): sie sind seit dem
  Coverage-Judge sichtbar, aber eine einzelne Stimme belegt nichts. Dieselbe
  Schwelle filtert sie aus der Opinion-Map (und damit aus dem Claim Ledger).
  alte Bookmarks/Snapshots ohne die Felder degradieren aufs bisherige Rendering.
- Consensus-Fehlerpfad: `query/stream_consensus` versuchen es bei Provider-
  Fehlern (503, Timeout, ...) ein zweites Mal (`CONSENSUS_MAX_ATTEMPTS`);
  gescheiterte Finals tragen `error: true`. `chat.py` erkennt Fehlertexte über
  `is_consensus_error_text` und überspringt dann Differences (Judge darf nie
  den Fehlertext "analysieren") sowie die Share-Persistenz; die Differences-
  Spalte zeigt `DIFFERENCES_SKIPPED_TEXT`.
- Bei erfolgreichem Lauf eines verifizierten Nutzers wird das Ergebnis als
  `pending_result` für das Share-Feature persistiert (→ `result_id`).

### Resolve-Runde
`POST /resolve` (`chat.py` → `resolve_engine.py`) konfrontiert die
dissentierenden Modelle eines Widerspruchs (Karte aus `differences_data`)
gezielt mit der Gegenposition: pro beteiligtem Modell ein paralleler Call auf
dem günstigen Judge-Modell seines Providers
(`DIFFERENCES_JUDGE_MODEL_BY_PROVIDER`), Structured Output
`{decision: maintain|revise, position, reason}`. Aggregiertes Outcome:
`resolved` (≥1 revidiert, ≥1 bleibt) / `standoff` (alle bleiben) /
`mutual_revision` (alle revidieren) / `error`. Verifizierter Login **und
mindestens Plus** nötig (`entitlements.resolve`; Fehlercode `plus_required`) —
die Runde läuft auf dem günstigen Standard-Judge, nicht auf Frontier-Modellen,
deshalb ist sie keine Pro-Grenze,
kostet 1 eigenen persistenten Run (außer `useOwnKeys`), Eingaben werden wie bei
`/consensus` serverseitig gekappt (`normalize_resolve_positions`), Ergebnis
wird **nicht** persistiert. Frontend: „Resolve with the models"-Button an
Contradiction-Karten in `consensus-insights.js` (nur bei ≥2 beteiligten
Modellen). Vor dem ersten `await` bindet der Handler Run-ID, Auth, Frage,
Providerpositionen, Credentials und Bookmark-ID. Eine späte Resolve-Antwort
mutiert nur die Differences dieses Contexts, rendert nur bei weiterhin
sichtbarer Run-ID und schreibt eine optionale Bookmark-Aktualisierung explizit
an dessen Bookmark statt an die inzwischen geöffnete Ansicht.

### Modus: Compare, Consensus, Agent (seit 2026-09-30)
Eine Wahl, ein Besitzer: `static/js/run-mode.js` (`App.runMode`) haelt
`localStorage.runMode` ∈ {`compare`, `consensus`, `agent`}. `DEFAULT_MODE`
steht dort als eine Konstante (seit 2026-10-02 `agent`). Beim ersten Laden
migriert das Modul die Altschluessel (`agentMode=false` → compare, sonst der
Default) und loescht `agentMode` und `autoConsensus`; andere Tabs folgen ueber
das `storage`-Event. Weil bis dahin jeder Erstbesuch ungefragt `consensus`
speicherte, zieht `migrateDefault()` einen gespeicherten `consensus`-Wert genau
einmal auf den Default (Marke `localStorage.runModeDefault =
"agent-2026-10-02"`, auch von `set()` gesetzt); `compare` bleibt. E2E-Tests,
die `runMode` vorbelegen, setzen die Marke mit.
- `preference()` ist die Wahl fuer neue Nachrichten, `effective()` das, was die
  naechste Nachricht tatsaechlich tut: ein offener Agent-Chat bleibt Agent, ein
  offener Consensus-Chat kann nur zwischen Compare und Consensus wechseln
  (serverseitig getrennte Chat-Familien, `agent-chat.js` meldet sie ueber
  `App.agentChat.modeState()`), und ohne Agent-Zugang laeuft eine Agent-Wahl
  als Consensus. `pipeline()` (= nicht Compare) ersetzt das fruehere
  `isAgentModeEnabled()` und fuellt das persistierte Laufsfeld
  `config.agentMode`/`autoConsensus` (Feldname historisch).
- `availability()` liefert je Modus `enabled`/`reason`; der Wähler zeigt
  gesperrte Modi mit Grund statt sie zu verstecken, Agent nur mit Zugang. In
  einem offenen Agent-Chat gibt es nichts zu wählen: dort tritt `#runModeControl`
  (die Modusgruppe im (+)-Menü) zurück, das (+) heißt dann „Chat options“.
- Aenderungen laufen nur ueber `set(mode, {source})`, feuern
  `consensio:run-mode-change` und `app_run_mode_changed` (mode, previous, source).
- Solange eine gespeicherte Agent-Wahl auf den Agent-Zugang des Kontos wartet,
  sperrt `updateQuestionInputAccess()` das Senden, statt still als Consensus
  zu senden. Scheitert `/user_status`, setzt `firebase.js` den Zugang auf
  „nicht erlaubt“; der Wähler zeigt dann sichtbar Consensus.
- UI seit 2026-10-02: der Modus ist die ERSTE Gruppe im (+)-Menü
  (`#runModeControl.attach-menu-modes`): `agent-mode.js::renderModeRows` baut
  drei Zeilen Agent · Consensus · Compare (`.attach-menu-mode[data-value]`,
  `aria-pressed`, Haken am aktuellen, gesperrte mit Grund, Agent mit „Beta“);
  ein Klick ruft `onRunModeChoice` und schließt das Menü. `#runModeSelect`
  bleibt versteckt im Container als Wert dahinter (Settings-Spiegel
  `#runModeSetting`, Tests, `change`-Listener). In der Composer-Zeile steht kein
  Moduschip mehr; das (+) heißt „Mode, files and options“.
  Compare sperrt die Quellenprüfung (Settings-Schalter disabled). Entfernt: `#composerAgentToggle`, `#agentModeMenuSwitch`,
  `#agentModeSwitch`, `#autoConsensusToggle`, `#chatExecutionMode`,
  `window.setAgentMode`, `window.isAgentModeEnabled`, `window.toggleAllResponses`.

### Composer: eine Anatomie für alle Modi
`templates/index.html` gliedert die Composer-Zeile in drei Gruppen, für Compare,
Consensus und Agent dieselben: `.composer-lead` ((+) `#attachTrigger`, darin
seit 2026-10-02 der Modus), `.composer-models` (wer antwortet: in Agent
nur `#agentModelControls`, sonst der Modell-Chip `#consensusModelDropdown`)
und `.input-actions-container` (Demo, Senden). Wo sie
stehen, entscheidet allein `static/css/composer.css`; `shell.css` gestaltet nur
die Box. Zustände: Startbildschirm (Hero oder Compare-Start) und aufgeklappt =
Feld oben, darunter (+) links, Modelle und Senden rechts; Desktop im
Chat = eine Zeile [(+)][Feld][Modelle][Senden], ab der zweiten Textzeile
(`.is-multiline`) wie der Startbildschirm; Handy (≤640 px, seit 2026-10-04) =
unter dem Feld EINE Zeile [(+)][Modelle … ][Senden], der Chip nimmt den
freien Platz und kürzt einen langen Modellnamen per Ellipse; Handy
eingeklappt = [(+)][Feld][Senden], Anhänge
und Zitat bleiben darüber sichtbar. (+) steht nie woanders, Senden
immer rechts außen. Alle Picker der Zeile teilen eine Optik (ruhiges Label mit
Chevron). Das (+)-Menü `#attachMenu` hat seit
2026-10-02 eine Zeilenanatomie (`composer.css`, „The (+) menu“): 16-px-Icon ·
Label (höchstens eine kurze Zeile darunter) · Wert mit Chevron oder Schalter;
„Add files“ ohne Stufen-Badge, Comparison models zeigt die Anzahl. Ab 701 px
steht jede Einstellung nur einmal: Reasoning, Comparison models und Google
data schaltet die Leiste unter dem Feld (`#composerModeBar`), das (+)-Menü
trägt dort den Modus und Dateien; auf dem Handy (Leiste nur mit Icons) bleibt
das Menü vollständig. Reasoning trägt überall
denselben Vierzack-Funken, Anhänge dieselbe Büroklammer. In der Leiste stehen
Zustände („On“, „Auto“) in Labelgröße auf derselben Grundlinie, Anbieterzeichen
ruhen einfarbig (Filter auf dem Badge, damit invertierte Mono-Logos im Dark
Mode invertiert bleiben) und zeigen ihre Farbe bei Hover. Rechtliches steht
in der Sidebar-Fußzeile, seit der Todo-Runde 3 in EINER Zeile
(`.sidebar-footer-meta`): links Imprint · Privacy · Terms als leise Wörter
(Impressum direkt erreichbar), rechts `.sidebar-footer-icons` mit zwei gleich
großen Zeichen, Feedback (`#feedbackButton`, Sprechblase) und GitHub (Build-Commit
im Tooltip); About steht im Public-Footer. Das Kontingent-Glyph über ihr ist
ein Kuchen (Tagesrest) in einem feinen Ring statt eines offenen Bogens, der wie
ein Ladekreisel aussah (`#quotaRingArc` r=3.5, stroke-width 7, gleiche
dashoffset-Logik in `sidebar-quota.js`). Unter dem Feld steht nur der
Hinweissatz. Pro Modus gibt es genau EINEN
Modell-Chip; er nennt nur, wer antwortet („6 models · Balanced“ mit Consensus,
„6 models“ in Compare, „<Chatmodell> +6“ in Agent: Chatmodell plus Zahl
der Vergleichsmodelle, deren Menü beide Abschnitte trägt), nie den Modusnamen.

### Consensus-Lauf (historisch „Agent Mode“)
Wo dieses Dokument „Agent Mode an/aus“ sagt, ist heute Consensus bzw. Compare
gemeint. `agent-mode.js` koppelt Auto-Consensus: nach Abschluss aller Modellantworten löst
`query-send.js` automatisch `executeConsensusRun(context)` aus. Run-State/Gating
läuft für Registry-Runs über deren Status/Controller und die kompatible
`consensus-lifecycle.js`-Brücke (`isActiveRun`, `finishRun`, `setSynthesizing`,
`cancelCurrentConsensus(runId)`). Auto-Consensus ist keine eigene Einstellung
mehr: `config.autoConsensus` = `App.runMode.pipeline()` beim Start des Laufs,
und `consensus-progress.js` liest den Wert des sichtbaren Laufs. Standardmäßig
bleiben die Einzelantwortboxen verborgen; `#agentModeAnswersToggle` oeffnet den
gemeinsamen `window.App.answerReader`, ohne Agent Mode oder dessen
Auto-Consensus-Kopplung zu deaktivieren. Die bisherige Body-Klasse
`.agent-mode-show-answers` bleibt nur als Legacy-Fallback ohne Reader-Modul.

Bei deaktiviertem Agent Mode ist der Fan-out selbst das Endergebnis. Der Client
bleibt in der durch `.direct-comparison-active` markierten Vergleichsansicht,
zeigt den Antwortleser inline mit Modellstatus und startet weder Consensus noch
Differences/Claims. Follow-up-/Chat-Turn-Persistenz wird in diesem Ein-Frage-Pfad nicht
begonnen, weil deren Abschluss an `/consensus` gebunden ist.

### Gemeinsamer Modellantwort-Leser
`static/js/model-answer-reader.js` wird in `bundles.json` nach den Attachments
und vor `agent-mode.js` geladen. `window.App.answerReader` stellt `project`,
`openLive`, `toggleLive`, `isLiveOpen`, `registerTurn`, `canOpenStored`,
`openStored`, `showDirectBookmark`, `syncPreview`, `directSummary`, `close` und `reset` bereit. `run-view.js` projiziert ausgewaehlte
RunContexts explizit; ein auf die alten Response-Boxen begrenzter Observer
bedient Demo und Legacy-Bookmark-Restores. Das Modul startet keine Modelllaeufe;
dekorative Quellen-Favicons nutzen den bestehenden `/api/topics/favicon?d=`-Proxy
(lazy geladen, bei Fehlern mit Buchstaben-Fallback).

`#modelAnswerReader` ist eine einzige Leseflaeche: inline in `.response-section`
beim Direktvergleich, sonst in einem nativen `dialog` ausserhalb `.container`.
Der Direktvergleich zeigt alle Modelle ohne Auswahl-Tabs und ohne aeusseren Rahmen.
Der Ergebnis-Kopf bleibt verborgen; der Composer zeigt den Bereitschaftsstatus
und bei abweichender naechster Einstellung „Shown: Compare result“. Nur die leere
Vorschau zeigt die Einleitung „One question. Individual answers.“. Der gespeicherte
Ergebnismodus bleibt getrennt von der Einstellung fuer die naechste Frage.
Die Agent-Mode-Ausblendregel in `shell.css` nimmt
`.direct-comparison-active` explizit aus.
`firebase.js::loadSingleBookmarkUI` uebergibt Direktvergleich-Bookmarks nach dem
Restore an `answerReader.showDirectBookmark`. Der Reader haelt deren Antworten,
Modelllabels und Quellen als eigenen Snapshot; aktuelle Modell-Ausschluesse
oder alte DOM-Datasets duerfen die gespeicherten Antworten nicht filtern oder
ersetzen. DOM-Observer erhalten diesen Snapshot, Run-Projektion, Ansichtswechsel
und Reset loeschen ihn. Die Agent-Mode-Praeferenz bleibt beim Oeffnen unveraendert.
Der bestehende `#threadAsk` bleibt inklusive Anhaengen/Expand die einzige Frage
und verwendet dieselbe rechtsbuendige Nachrichtenblase wie Agent Mode.
`enterDirectComparisonView()` entfernt `is-hero`: Seitenbreite, Zentrierung,
kompakter Composer, mobile Collapse-/Scrollreserve und Menues kommen aus dem
normalen Thread-Layout, ohne direkte Layout-Sondermasse. Vor der ersten Frage
zeigt Agent Mode den zentrierten Composer; ausgeschaltet erscheint bereits
die Vergleichsvorschau (siehe „Agent Mode“ unten). Die alten Response-Ziele
bleiben verborgen; die Vorschau ist zugaenglich. Der Composer wird im DOM hinter die Antworten versetzt
und beim Verlassen an seinen Kommentaranker zurueckgesetzt.
Der Direktvergleich zeigt keinen Copy-Button pro Antwort und keine grauen
Warteflaechen; Pending/Reasoning/Streaming stehen ausschliesslich im Modellkopf.
Fehlertexte bleiben sichtbar. Der Composer-Picker misst beim Oeffnen, Scrollen
und Resize den verfuegbaren Viewport (inkl. VisualViewport), waehlt oben/unten
und begrenzt Breite und Hoehe; sein bestehender DOM-/Tastaturvertrag bleibt.
Modellfamilie und gespeicherte Version werden separat gezeigt; fehlende
Versionsdaten ersetzen niemals den bekannten Familiennamen.
Ab 1400px ist der einfache Leser rechts angedockt, mit entsprechend schmalerer
Chatspalte. Die Dockbreite waechst zwischen 520 und 720px (36vw); der Chat bleibt in der
Restflaeche zwischen linker Navigation und Leser zentriert, auch bei eingeklappter
Navigation. Die Textbreite des Chats bleibt auf 900px begrenzt.
Auf kleineren Viewports sowie beim erweiterten Zweiervergleich oeffnet er modal
(native Fokusbegrenzung/Escape); bis 1099px bildschirmfuellend
inklusive Safe-Area-Abstaenden. Im Dialog stehen zwei Antworten erst ab 760px tatsaechlicher
Leserbreite nebeneinander, sonst schaltet man zwischen A und B um.
Unter 500px ersetzt eine kompakte Modellauswahl die mehrzeilige Modellnavigation.
`static/css/model-answer-reader.css` folgt `shell.css` und verwendet ausschliesslich
App-Tokens und die bestehende Inter-/Markdown-Typografie.
Der Leser blendet beim Oeffnen in 180ms ein: angedockt mit 16px Bewegung von
rechts, modal mit 8px von unten und sanftem Backdrop. Abschnittswechsel und
Streaming starten die Animation nicht neu; Schliessen bleibt unmittelbar.
Bei `prefers-reduced-motion: reduce` entfaellt die Oeffnungsanimation.
Nur der Dialog verwendet kompaktere Kopf-/Kartenabstaende (24px Seitenrand,
mobil 16px): Titel (14px) und Bereitschaftsstatus teilen eine umbrechende Zeile,
Frage, Tabs und Modellchips folgen mit reduziertem Abstand. Modellchips und
Icon-Buttons sind am Desktop 32px hoch; Touch behaelt mindestens 44px hohe
Ziele (Schliessen/Erweitern auch 44px breit). Angedockte Antworten verwenden
14px/1.7 mit proportionalen Markdown-Titeln und kuerzeren Absatzabstaenden;
Difference-Titel bleiben 14px. Der Inline-Leser bleibt davon unberuehrt.
Im erweiterten Popup teilen Frage, Tabs, Modellauswahl und Inhalt dieselbe
volle Innenbreite statt separater 840-/720px-Spalten. Desktop-Popups verwenden
32px Seitenabstand und 16px Fliesstext fuer Einzelantworten; Zweiervergleich
und angedockter Leser behalten ihre eigene Typografie.
Die Frage steht im Dialog als **eine** abgeschnittene, aufklappbare Zeile ohne
Label (sie steht bereits im Chat); erst mehrere Turns bzw. Vergleichsgrundlagen
blenden `.answer-reader-context-top` mit der Frageauswahl ein (Desktop rechts
neben der Frage, bis 759px darüber). In Differences/Sources bleibt der
Untertitel `#answerReaderStatus` leer und verborgen; der aktive Tab benennt den
Abschnitt. Modellnavigation und Antwortkopf nutzen die vorhandenen
Provider-Icons. Fertige Antworten zeigen keinen redundanten Status-Badge;
laufende und fehlgeschlagene Modelle behalten ihren sichtbaren Status.
Frage- und Modellauswahl verwenden eigene Listbox-Popovers mit App-Tokens,
Fragevorschauen beziehungsweise Provider-Icons und Tastaturbedienung. Die
versteckten Selects halten nur die Auswahlwerte. Escape schliesst zuerst ein
offenes Auswahlmenue, danach den Leser; ein Klick auf den Modal-Hintergrund
schliesst den Leser ebenfalls. Die Frage klappt ohne doppelte Textausgabe auf.
Der Frage-Chevron wird nur bei abgeschnittenem Text angezeigt. `openPanel(kind,
trigger, turn, index, options)` integriert Differences und Sources in denselben Leser;
`options.reveal` lässt einen expliziten Ergebnissprung auch bei wiederholtem Klick offen.
die Abschnittsnavigation bleibt an die ausgewaehlte Frage gebunden. Live- und
Archiv-Footer sowie Difference-Marker oeffnen diese Ansicht. Die bestehenden
Karten/Quellenlisten werden mit Platzhaltern in den Leser verschoben und beim
Schliessen/Wechsel zurueckgesetzt; IDs und Event-Handler bleiben erhalten. Der
Legacy-Differences-Text bleibt als Streaming-Ziel an Ort und Stelle (Lesekopie).
Differences starten als aufklappbarer Ueberblick: Schwere-Punkt + ein Wort,
darunter die Kernaussage in normalem Gewicht, Haarlinien statt Kartenrahmen,
keine Positionszahl. Kritische Funde stehen oben. Ihre Positionen, Zitate,
Pruefhinweise und Resolve-Aktionen bleiben erhalten.
Ein einzelner Unterschied wird direkt geoeffnet; mehrere starten als Ueberblick.
Seit 2026-10-01 ist die Liste ein Akkordeon: der `toggle`-Listener im Inspector
schliesst beim Oeffnen einer Karte die zuvor offene (auch bei Marker-Spruengen
und `refreshContext`). Typografie im Inspector: 14px Inhalt, 12px Meta, 13px
Zitate, durchgehend regulaeres Gewicht.
In der erweiterten Desktopansicht stehen Modellpositionen zweispaltig.
Quellenkarten zeigen Favicon, Domain, Titel und unveraenderte Referenznummer;
Auszuege werden separat aufgeklappt. Archivdaten bleiben turn-lokal.

Modell-Icons im Leser und Direktvergleich haben weder Hintergrund noch Rahmen;
monochrome Logos uebernehmen die bestehende Dark-Theme-Invertierung.

Direktvergleich-Saves geben die eingefrorene `modelLabel` des RunContext ueber
`query-send.js` und `firebase.js::saveBookmark` an `POST /bookmark` weiter.
Der Endpoint validiert das optionale Label und speichert es pro Anbieter in
`model_labels` zusammen mit der Antwort; weitere Anbieter bleiben erhalten.
Alte Clients ohne Label ersetzen eine eventuell veraltete Version durch den
Anbieternamen. Bei historischen Antworten ohne konkrete Modellversion bleibt
die Versionszeile im Direktvergleich leer; die aktuelle Picker-Auswahl wird
niemals als historische Modellversion ausgegeben.
Ein offener Live-Inspector schliesst beim Run-Wechsel, bevor er als alter Turn
weiter angezeigt werden kann: seine Quellen-/Differences-Knoten sind weiterhin
die wiederverwendeten Live-Renderziele. Gespeicherte Antwort-Snapshots bleiben
davon unabhaengig. `memory-edit.js` erkennt `.answer-reader-body` als
Modellantwort, haengt das Auswahlmenue bei einem nativen Reader-Dialog in diesen
Dialog und schliesst den Leser vor „Ask about this“ oder dem Memory-Dialog,
damit Composer und Memory wieder fokussierbar sind.
Die originalen `.response-box`-IDs bleiben versteckte Render-/Konfigurationsziele;
im ungesendeten Hero bleiben sie verborgen und inert; die Modellauswahl erfolgt
ueber Sidebar und Composer-Picker.
`consensus-run.js::appendHistoryTurn` registriert Turn-Daten an ihrem Article per
WeakMap und ersetzt die gestapelten Originaltexte durch einen Reader-Button.
Die Quellen, Modellnamen und Texte des Readers kommen jeweils aus diesem Turn;
`consensus-insights.js` fuehrt Live- und gespeicherte Claim-Spruenge in denselben
Leser. Eine alte ausgewaehlte Antwort bleibt bei spaeteren Turn-Projektionen
angeheftet; Wechsel in einen anderen Lauf, neue Ansicht und Logout schliessen
beziehungsweise resetten den Leser. Modellwechsel merken lokale Lesepositionen
(maximal 100 Eintraege), ein Stream wechselt weder Modell noch Leseposition.
Die bisherigen Schubladen sind nur der Fallback ohne geladenes Reader-Modul.

Die Moduswahl steht im Abschnitt „Modus: Compare, Consensus, Agent". Compare und
Consensus sind fuer alle Stufen frei; Agent erscheint nur mit Agent-Zugang.

**Default fuer neue Nutzer**: `run-mode.js` setzt `DEFAULT_MODE` (consensus),
`agent-mode.js` `agentModePanelCollapsed = "false"`, solange die Keys fehlen. Der
Einstieg zeigt in Consensus den zentrierten Composer. In Compare
zeigt `answerReader.syncPreview(enabled, models)` sofort das echte
Direktvergleichsraster mit den aktuell ausgewaehlten Modellnamen und statischen
Antwortplatzhaltern. `direct-comparison-preview` markiert diesen Leerzustand;
er nutzt die Thread-Shell (`direct-comparison-active`, ohne `is-hero`) mit
unten angedocktem Composer. Die Vorschau ist weder RunContext noch Antwort
und zeigt keinen Bereitschafts-/Ladestatus. `updateAgentModeUI()` synchronisiert
sie auch bei Modellwechseln, „New comparison“ und gespeicherter Off-Praeferenz.
Anschalten kehrt nur aus der Vorschau zum Hero zurueck; laufende und gespeicherte
Ergebnisse bleiben unveraendert. Run-/Bookmark-Projektionen entfernen die
Vorschaumarke und ersetzen die Platzhalter. Der Composer animiert beim Wechsel
seine Positionsdifferenz in 300 ms; Reduced Motion bleibt unmittelbar. Mobil
steht das Raster einspaltig, mit derselben fixierten Eingabe und Scrollreserve
wie die Antworten. Eine explizite Wahl (`App.runMode.set`) ueberschreibt den
Default dauerhaft.

### Attachments (alle Konten seit 2026-10-02)
Noch nicht gesendete Dateien stehen als kompakte Vorschau-/Entfernen-Chips in
der Leiste unter dem Eingabefeld. `attachments.js` verschiebt dieselbe
`#attachmentBar` auf dem Startbildschirm in die `#composerModeBar`; in einem Chat
(Leiste verborgen oder nur angedockt) steht sie in jedem Modus an ihrem
Composer-Anker oberhalb des Felds, auch im eingeklappten Handy-Composer. `App.attachments.syncComposerPlacement()` wird beim Toolbar-Rendering
und Attachment-Rendering aufgerufen; Fokus, Datei-Bytes und Listener bleiben
erhalten. Neue Dateien oeffnen einen eingeklappten mobilen Composer. Beim Senden
geht die vorhandene Metadaten-Uebergabe weiterhin an die jeweilige Frage; leere
Entwuerfe und gespeicherte Nachrichten zeigen keine bearbeitbaren Datei-Chips.
`css/composer-attachments.css` gestaltet ausschliesslich den Composer-Tray;
Vorschau und Entfernen sind getrennte native Buttons.
Frontend `attachments.js` baut Payload; Backend `app/services/llm/attachments.py`
validiert: max **2** Dateien, serverseitig je **5 MB** und zusammen höchstens
**6 MB**, MIMEs PDF/DOCX/TXT/PNG/JPEG/WebP
(TXT umfasst auch die UI-Endungen MD und CSV). Word- und Textdateien werden
serverseitig als begrenzter Text extrahiert und als Text-Fallback an alle
Provider angehängt. Große Bilder dürfen clientseitig bis 15 MB ausgewählt
werden, werden aber vor dem Upload auf höchstens 1568 px und ungefähr 900 kB
gebracht; serverseitig gelten zusätzlich 40 Mio. Pixel vor dem Dekodieren und
1,5 MB nach der Aufbereitung. Bild-Support:
openai/anthropic/gemini/grok/kimi/glm; PDF-Support:
openai/anthropic/gemini. PDFs über 2 MB werden für alle Familien als einmal
extrahierter Text verwendet; nur nicht extrahierbare Scans bleiben für
PDF-fähige Familien nativ. Die PDF-Textextraktion (`extract_pdf_text`) läuft
nicht im Webprozess, sondern über `agent_file_extract.run_isolated` im
Modus `pdf-text` im selben Wegwerf-Subprozess wie Agent-Dateien (15 s Walltime,
unter Linux 10 s CPU und 768 MiB Adressraum, höchstens 80 Seiten, Abbruch der
Seitenschleife bei 24.000 Zeichen, keine Temp-Dateien). Timeout, Budget- oder
Parserfehler gelten als „kein Text“ und führen zum bestehenden Hinweis bzw.
nativen Versand. **Im klassischen Consensus landen in Firestore nie Datei-Bytes**, nur
Metadaten (Name/Typ/Größe) — siehe `bookmarks.py::sanitize_attachment_meta`.
Bilder können zusätzlich zum Dateiauswahldialog per Paste im `#questionInput`
angehängt werden. Drag-and-drop auf `.chat-input-container` akzeptiert wie der
Dateiauswahldialog die vollständige PDF/DOCX/TXT/MD/CSV/PNG/JPEG/WebP-Whitelist;
alle Wege nutzen dasselbe Gate sowie dieselben Anzahl-/Größenlimits. Seit
2026-10-02 ist `entitlements.attachments` für jede Stufe wahr (Dateien kosten
Tokens aus dem gemeinsamen Kontingent); nötig ist nur ein Konto: `/ask_*` lässt
Anhänge nur mit verifiziertem Token zu („Sign in to attach files.“), der
Client öffnet für Gäste den Login statt des Dateidialogs (`canAttach()` in
`attachments.js`). Agent-Uploads (`POST /agent/chats/{id}/files`) haben
zusätzlich 30 Uploads je 10 Minuten pro Konto (`api_uid_limiter`,
`agent:upload`) und einen Speicher je Stufe aus
`agent_files.UPLOAD_QUOTAS` (Free 25 Dateien/25 MB, Plus/Pro 100/100 MB;
generierte Dokumente nutzen die Standardgrenzen).
Solange ein sendbarer Anhang vorliegt, schließt der Client DeepSeek sowohl im
sichtbaren Auswahlzustand als auch defensiv im tatsächlichen Request-Fan-out aus.
Base64 wird anhand der kodierten Länge **vor** dem Dekodieren begrenzt. DOCX
akzeptiert nur sichere Word-Pfade und höchstens 256 ZIP-Einträge; Einzeldatei,
Gesamtexpansion und Kompressionsverhältnis besitzen feste Budgets. `document.xml`
wird nur chunkweise bis zum Budget expandiert und DTD/Entities werden abgewiesen.

### Ein Tokenkonto für alle Modi (seit 2026-10-01)

Compare, Consensus (je mit oder ohne Reasoning) und Agent · Beta buchen auf **dasselbe**
Tageskonto pro Nutzer (`users/{uid}/chat_state/agent_tokens_{periode}`,
`app/services/agent_quota.py`). Die Nutzerin sieht eine Zahl, wo immer sie
fragt (Ring, Panel, Agent, Absage-Karte). Reset (00:00 UTC bzw. Admin-Reset
über `reset_epoch`), Revisionen und Admin-Steuerung sind dieselben wie zuvor bei
Agent.

- **Konfiguration** (`app/services/agent_budget_config.py`, Dokument
  `app_config/agent_budget`, revisioniert mit Audit-Kopien unter
  `revisions/`): `tier_limits{free,plus,pro,admin}` und
  `run_estimates{tier}{compare,consensus,deep_think}` (`deep_think` ist der
  behaltene Key der Schätzung eines Laufs mit Reasoning an). Fehlende Felder
  erhalten ihren Default, vorhandene ungültige Werte schlagen geschlossen fehl
  (503). Das alte Einzelfeld `daily_token_limit` wird ignoriert und beim
  nächsten Speichern entfernt. Admin → Limits zeigt eine Tabelle Stufe ×
  (Tokens/Tag, Compare-, Consensus-, Reasoning-Lauf); `PUT
  /api/admin/agent-budget` nimmt `{revision, tier_limits?, run_estimates?}`
  (strikt, Teilwerte werden mit dem Stand gemischt), `GET` liefert zusätzlich
  `defaults`. Stufe: `agent_quota.account_tier(uid, tier)` = `admin` bei
  Admin-Rolle, sonst `free|plus|pro`. Agent für alle Stufen zu öffnen
  (2026-10-02) war deshalb nur eine Zugangsentscheidung, keine Ledger-Änderung.
- **Agent** bleibt bei strikter Einzelabrechnung (Reserve vor jedem Call,
  Settlement mit Messwerten, Schätzung + Reconciliation bei fehlender Usage);
  nur das Limit kommt aus der Stufe.
- **Pipeline: messen und danach buchen.**
  - *Admission* (`/prepare`, Legacy-Direktaufrufe in `authorize_operation`,
    API v1 beim Annehmen): ein Lauf startet nur, wenn `remaining` (Limit −
    gemessen − geschätzt − Agent-Reservierungen − aktive Pipeline-Holds) die
    erwarteten Tokens eines typischen Laufs von Modus und Stufe deckt
    (`run_mode`: `compare`, sonst `consensus`; Reasoning-Schätzung `deep_think`
    aus `deep_search`;
    Resolve gegen die Compare-Schätzung). Der Lauf legt diese Schätzung als
    Hold (`pipeline_holds`, zehn Minuten) ins Konto, damit parallele Tabs das
    Puffer nicht doppelt nutzen; es gibt **keine** Reservierung pro Call.
    Absage: 403 `token_budget_exhausted` mit `token_budget` und
    `required_tokens`; zu viele junge Läufe: 429 `usage_run_capacity`.
  - *Messen* (`app/services/llm/usage_meter.py`, Transportschicht): jeder
    OpenRouter-Request über `_iter_openrouter_chunks` (gestreamte Antworten
    und Engines, mit `stream_options.include_usage`), `cancellable_post_json`
    (Judges, Repairs, Resolve) und `engines.query_model` meldet
    `prompt_tokens + completion_tokens` an den per ContextVar gebundenen
    Meter. Threads über `copy_context().run` (Coverage-Judge, Provider-Fan-out,
    Resolve) melden in denselben Meter. Fehlt die finale Usage (Abbruch,
    Timeout, Tab zu), gilt dieselbe begrenzte Schätzung wie bei Agent: 50 %
    der Call-Grenze (Input-Schätzung + Output-Cap); eine HTTP-Ablehnung kostet
    nichts. Ohne gebundenen Meter (Watch, Topics, Agent-Client) sind alle Hooks
    No-ops. MOCK_LLM bucht kleine synthetische Messwerte. Nicht gemessen
    werden die beratende Consensus-Quellenprüfung (eigener Hintergrundjob mit
    eigenem Budget) und spätere Arbeit nach der Buchung einer Operation. Die
    Agent-Quellenprüfung läuft in derselben Queue, bucht aber über
    `job.metering` auf dieses Konto (Reserve bei Aufnahme, Settlement je
    Paketergebnis, siehe Agent-Abschnitt „check_contradictions“).
  - *Buchen* (`app/services/run_metering.py::OperationBooking`): jede
    abgeschlossene Operation (`ask:<familie>`, `consensus`, `resolve`, API
    `pipeline`, Chat-Memory `context:<turn>` nur wenn ein Call lief) bucht
    ihre Summe genau einmal über
    `usage_repository.book_operation` (`booked_operations` als Zaun) in die
    Kontoperiode ihrer Admission; `final=True` (Consensus, Resolve, API) gibt
    den Rest-Hold frei. Gebucht wird vor dem `final`-Event (das das gebuchte
    `token_budget` trägt) bzw. beim Schließen des Streams. Ein Buchungsfehler
    bricht die Antwort nie ab, sondern wird als `Token booking failed` geloggt.
  - *Überziehen*: eine laufende Operation darf das Konto unter null drücken;
    danach scheitert die nächste Admission. Begrenzt, weil nur Läufe mit
    ausreichendem Puffer starten und jeder junge Lauf seine Schätzung hält.
  - `usage_run_key` bleibt Idempotenz und Bindung; Run-Zähler, Run-Limits und
    Deep-Think-Kontingent sind entfernt. API v1 hängt am selben Pfad. Watches,
    Topics und Publisher-Watches behalten ihre eigenen globalen Budgets.
- **Anzeige**: ein Prozent-Ring für alle Modi (`token-budget.js`,
  `sidebar-quota.js`, §3). „Uses 1 run" ist ein ungefährer Anteil („about 8 %
  of today"). Die Absage-Karte (`usage-limit.js`, `#runBlocked`) nennt den
  Rest in Prozent, den Bedarf des Modus und die Reset-Zeit; reicht nur der
  Reasoning-Lauf nicht, bietet sie „Send without reasoning" an
  (`data-bucket="reasoning"`, Warnton statt Absage).

**Herleitung der Defaults** (Prinzip: ein typischer Nutzer behält ungefähr
seine bisherige Tageskapazität; Limit ≈ bisheriges Run-Limit × Tokens eines
typischen Laufs). Bisherige Produktionswerte (2026-10-01, nur gelesen):
Free 12, Plus 30, Pro 50 Runs/Tag (davon 5 Deep Think), Agent 750 000 Tokens
(Pro/Admin); Output-Caps Free/Plus 4 096 (500 Wörter), Pro 8 192 (1 000
Wörter), Deep Think 16 384, Consensus 16 384, Differences 8 192, Coverage
12 288.

| Baustein (Free/Plus) | Input | Output | Summe |
|---|---|---|---|
| Antwort (Systemprompt ~130, Frage, Websuche ~4 000; gemessen Exa ≈ 4 800 Prompt-Tokens) | ~4 300 | ~850 (Agent-Belege günstiger Vergleichsmodelle: Ø 760–1 100) | ~5 200 × 6 ≈ 31 000 |
| Synthese (Prompt mit 6 Antworten gemessen 4 400 + Quellen) | ~6 200 | ~1 000 | ~7 200 |
| Differences-Judge (Prompt gemessen 5 300) | ~5 400 | ~2 000 | ~7 400 |
| Coverage-Judge | ~5 000 | ~2 500 | ~7 500 |
| **Consensus-Lauf** | | | **≈ 53 000 → 55 000** |
| **Compare-Lauf** (nur Antworten) | | | **≈ 31 000 → 32 000** |

Pro (1 000 Wörter, längere Antworten und Judge-Prompts): Antwort ~6 100 × 6
≈ 37 000, Synthese ~11 500, Judges je ~12 000 → Consensus ≈ 75 000, Compare
≈ 40 000. Deep Think (16 384-Cap, bis zu fünf Suchrunden, Reasoning):
Antworten ~16 500 × 6 ≈ 99 000 + Synthese ~16 000 + Judges ~28 000 →
≈ 150 000. Seit 2026-10-02 trägt der Reasoning-Lauf (gleiche Modelle, Effort
„high", Output bis `reasoning_max_tokens` = 8 192, eine Suchrunde) bewusst
weiter diese Schätzung: Admission irrt lieber zur sicheren Seite; nach
Prod-Daten im Admin nachjustieren.

| Stufe | Rechnung | Default `tier_limits` |
|---|---|---|
| Free | 12 × 55 000 | 660 000 |
| Plus | 30 × 55 000 | 1 650 000 |
| Pro | 50 × 75 000 + 5 × (150 000 − 75 000) Deep-Think-Aufschlag + 750 000 bisheriges Agent-Konto ≈ 4,9 Mio. | 5 000 000 |
| Admin | wie Pro | 5 000 000 |

Nachjustieren: Admin → Limits. Belastbare Werte liefern die gebuchten
Operationen (`usage_runs.booked_operations`, `pipeline_used` im Kontodokument)
nach einigen Tagen Betrieb; die Schätzung pro Lauf sollte etwa dem Median eines
vollständigen Laufs entsprechen, das Limit dem gewünschten Tagesvolumen.

### Auth / Usage / Tier
- **Early-Access-Hinweise:** `static/js/feature-access.js` lädt im App-Bundle
  nach `app-core.js`. Der bestehende Aufruf `App.showProFeatureModal(feature)`
  zeigt einen kurzen, nicht blockierenden Hinweis in `#featureAccessNotice`;
  weitere gesperrte Funktionen ersetzen dessen Text statt Dialoge zu stapeln.
  Der Hinweis verschwindet nach fünf Sekunden automatisch; ein neuer Hinweis
  startet die Frist erneut. Manuelles Schließen und Öffnen der Erklärung
  löschen den laufenden Timer ebenfalls.
  Pro sowie Plus bei Resolve/Anhängen passieren weiterhin ohne Hinweis.
  `App.showAccessInfo()` öffnet die kurze Erklärung in `#proFeatureModal`
  ausschließlich über einen bewussten Info-Klick (Sidebar, Hinweis oder Watch).
  Sie nennt Early Access, begrenzte Verfügbarkeit, geplante bezahlte Angebote
  und `contact@consens.io`. Escape, Fokus-Rückgabe und Tab-Schleife gehören
  zum Dialog. Tier-Aktualisierungen schließen den Funktionshinweis über
  `App.dismissFeatureAccessNotice()`. Die Landingpage enthält keinen Kosten-
  oder Testphasen-Abschnitt; FAQ und About erläutern den aktuellen Zugang.
- Firebase-ID-Token wird mit `verify_user_token` geprüft (Standard: nur
  E-Mail-verifizierte Nutzer; `allow_unverified=True` nur für Registrierung/Delete).
- Das Login-Overlay ist ein echtes `role="dialog"` mit `aria-modal`,
  Überschriftsreferenz, fokussierbarem benanntem Close-Button, Fokus-Einstieg,
  Tab-Schleife, Escape/Backdrop-Abbruch und Fokus-Rückgabe an den Auslöser.
- **Login-Dialog (seit 2026-10-04, `static/firebase.js`, Stil allein in
  `static/css/auth-modal.css`):** ein Formular mit zwei Tabs (`#authTabLogin`
  / `#authTabRegister`, Pfeiltasten), Google zuerst. Enter bzw. „Los“ der
  Handy-Tastatur submitten das Formular, der Tab entscheidet über Login oder
  Registrierung. Sign-up ist EIN E-Mail-Feld (keine Bestätigungsfelder mehr);
  die Erfolgsansicht nennt die Adresse, bietet für bekannte Anbieter „Open
  Gmail/Outlook/…“, „Send the link again“ (30/60-s-Cooldown, derselbe
  `/register`-Aufruf) und „Use a different address“. Die Adresse liegt bis zum
  nächsten Login unter `consensio.authEmail`; `/app?setup=1` (Continue-URL der
  Setup-/Reset-Mail) öffnet den Login vorausgefüllt mit Hinweis und entfernt
  den Parameter. „Forgot password?“ antwortet immer neutral („If an account
  exists …“) und führt ebenfalls über `/app?setup=1` zurück. Jede Aktion zeigt
  einen Ladezustand; Fehler stehen am auslösenden Element (`#googleError`
  unter Google, `#loginError`/`#registerError` unter dem Formular). Ein falsches
  Passwort heißt auch dann „E-mail or password is not correct“, wenn SDK 9.22
  es als `auth/internal-error` mit `INVALID_LOGIN_CREDENTIALS` meldet. Auf
  Touch-Geräten wird beim Öffnen kein Feld fokussiert (die Tastatur verdeckte
  sonst Google). Demo-Ende („register“) und gesperrte Anhänge („login“) öffnen
  den Dialog über `window.App.openAuthModal(mode, trigger, source)`.
  **Google:** In In-App-Browsern (LinkedIn, Instagram, Facebook, TikTok,
  Snapchat, LINE, Android-WebView) startet kein Google-Login (Google verweigert
  ihn dort); stattdessen erscheint `#inAppBrowserNotice` mit „Copy link“ und
  auf Android „Open in Chrome“ (`intent://`). Sonst Popup — außer auf
  Mobilgeräten, wenn `FIREBASE_AUTH_DOMAIN` gleich dem App-Host ist
  (`firebase_auth_proxy.py`): dann `signInWithRedirect`, Rückkehr über
  `sessionStorage["consensio.googleRedirectPending"]` + `getRedirectResult`.
  Ein blockiertes Popup fällt in diesem Fall automatisch auf den Redirect
  zurück. Nach Popup-/E-Mail-Login lädt die Seite unter ihrer eigenen URL neu
  (Deep-Links wie `/app/watches` bleiben, eine Gast-Demo verschwindet);
  `onIdTokenChanged` schließt ein offenes Modal für jeden bestätigten Nutzer.
- **Revocation-Entscheidung:** seltene sensible Grenzen (`/confirm-registration`,
  `/delete_account`, sämtliche Admin-Endpunkte) verwenden den live prüfenden
  `check_revoked=True`-Pfad. Normale App-Requests prüfen das signierte ID-Token
  plus den allgemeinen `account_deletion_jobs`-Tombstone mit 30-s-Cache, damit
  nicht jeder Fan-out einen Firebase-Revocation-Read auslöst. Pending Jobs sperren
  ohne Ablauf; completed Jobs bleiben mindestens zwei Stunden (länger als ein
  ID-Token) gesperrt. Logout beendet nur lokale Firebase-/Cookie-Sessions und
  ist ausdrücklich kein globaler Token-Widerruf.
- Token-Quelle: `extract_id_token` liest Body `id_token`, sonst `Authorization:
  Bearer`, sonst Cookie `session`.
- **Unbestätigte Sessions bleiben angemeldet (seit 2026-08-04).** Früher hat
  `onIdTokenChanged` unbestätigte Nutzer sofort ausgeloggt; wer den Link nicht
  im selben Moment fand, stand wieder vor der Login-Maske. Jetzt bleibt die
  Firebase-Session stehen (kein `id_token` in `localStorage`, keine
  Server-Session, keine authentifizierten Calls — die Schranke bleibt
  serverseitig `verify_user_token`), und `static/js/email-verify.js` zeigt den
  Streifen `#verifyBanner`: Resend mit 60-s-Cooldown, „I've confirmed it"
  (`user.reload()` + erzwungenes Token, ohne Seitenneuladen), Spam-Hinweis und
  „Use a different address" als einziger verbliebener Sign-out. Ein Wechsel
  zurück in den Tab prüft stumm nach (`visibilitychange`/`focus`), weil der
  Link meist in einem anderen Tab geöffnet wird. Der Bestätigungslink trägt
  `continueUrl = /app?verified=1`. Getippt werden darf dabei schon:
  `window.userCanTypeQuestions()` (Feld) und `window.userCanAskQuestions()`
  (Senden) sind zwei getrennte Rechte, und der Entwurf liegt bis zum ersten
  echten Lauf unter `consensio.questionDraft.v1` — die Frage überlebt den
  Umweg über das Postfach.
- Eigene API-Keys sind ein eingeloggtes Feature: `/check_keys`, `/ask_*` mit
  User-Key und `/consensus` mit `useOwnKeys` verlangen ein verifiziertes Token.
- **Unvertrauenswürdige Request-Größen sind vor teurer Arbeit begrenzt:** Das
  ASGI-Bodylimit verwirft sowohl zu großes `Content-Length` als auch erst beim
  chunked Lesen anwachsende Bodies mit 413, bevor FastAPI JSON/Form parst.
  Nach dem einmaligen Body-Replay reicht die Middleware echte nachfolgende
  ASGI-Receive-Events weiter; insbesondere wird kein künstliches
  `http.disconnect` erzeugt, das laufende SSE-Antworten abbrechen würde.
  Bei Abbruch während des Einlesens wird auch ein bereits gepufferter Teil
  verworfen und der echte Disconnect weitergegeben; ein gültiger JSON-Präfix
  darf nicht als vollständiger Request eine Mutation auslösen.
  Chat-Frage und System-Prompt besitzen getrennte Zeichen- und UTF-8-Bytecaps;
  Legacy-Follow-up-Kontext wird bei Überschreitung abgewiesen statt still
  gekappt. Dadurch fallen auch extrem lange Ein-Wort-Strings vor Providerarbeit.
- **Drei Stufen** (`app/core/entitlements.py`): `users/{uid}.tier` ist
  `free`, `plus` oder `pro`; der historische Tag `premium` bedeutet weiterhin
  Pro, alles Unbekannte fällt auf Free. Admin bleibt `users/{uid}.role == admin`.

  | | Frontier-Modelle | Anhänge | Resolve | Tokenkonto/Tag (Default) |
  |---|---|---|---|---|
  | Free | – | – | – | 660 000 |
  | Plus | – | ✓ | ✓ | 1 650 000 |
  | Pro | ✓ | ✓ | ✓ | 5 000 000 |
  | Admin (Rolle) | wie Stufe | wie Stufe | wie Stufe | 5 000 000 |

  Der Reasoning-Schalter (früher Pro-only „Deep Think") ist seit 2026-10-02
  keine Berechtigung mehr: alle Stufen dürfen ihn nutzen; `entitlements.deep_think`
  und das Feld `deep_think` der Admin-Kontoansicht sind entfernt.

  Plus existiert für Tester, die Funktionen ausprobieren sollen, **ohne einen
  Frontier-Lauf auslösen zu können**. Herleitung der Tokenkonten: §4 „Ein
  Tokenkonto für alle Modi".
- **Zwei Flags, eine Regel:** `is_user_pro(uid)` behält überall seine alte
  Bedeutung „darf teure Modelle" und ist für Plus **False**;
  `is_user_plus(uid)`/`entitlements.attachments|resolve` decken die
  Komfortfunktionen ab. Jeder Pfad, der noch nicht tier-bewusst ist, behandelt
  einen Plus-Account damit automatisch wie Free — eine Lücke kostet höchstens
  Komfort, nie Geld. Aus demselben Grund fällt `_tier_limit` in
  `config.py` bei einem fehlenden Plus-Schlüssel auf den Free-Wert zurück, nie
  auf den Pro-Wert.
- `get_user_tier(uid)` ist die einzige Quelle für die Stufe; die Limit-Getter in
  `config.py` nehmen jetzt `tier` statt `is_pro` (ein Bool bleibt erlaubt:
  `True` → Pro, `False` → Free). `/user_status`, `/usage`, `/prepare`, `/ask_*`,
  `/consensus` und `/resolve` liefern zusätzlich zu `is_pro_user` das Feld
  `tier`; das Frontend hält es in `window.userTier` plus den abgeleiteten
  `window.isUserPro` / `window.isUserPlus` (`app-state.js`,
  `App.normalizeTier`).
- **Tier-Flags sind gecacht**: `get_user_tier`/`is_user_pro`/`is_user_admin`
  teilen sich einen TTL-Cache (60s, `security.py::_tier_cache`) über das
  `users/{uid}`-Dokument — ein Firestore-Read statt zwei pro Aufrufstelle.
  Firestore-Ausfälle werden als `TierStatusUnavailable` statt als Free-/Nicht-
  Admin-Status behandelt und von User-/Chat-/Admin-Grenzen als 503 abgebildet.
  Fehler werden nicht gecacht; `/delete_account` und jede Admin-Tier-Änderung
  invalidieren via `invalidate_tier_cache(uid)`. Ein separates Early-Tier
  existiert nicht mehr.
- **Stufe setzen (Admin):** `app/services/account_tier.py` ist die einzige
  Schreibstelle für `users/{uid}.tier`. `GET /api/admin/account-tier?identifier=`
  schlägt per UID **oder** E-Mail nach, `PUT /api/admin/account-tier`
  (`{identifier, tier, note}`) setzt die Stufe, `GET /api/admin/account-tiers`
  listet alle Konten oberhalb von Free plus die letzten Änderungen. Jede
  Änderung schreibt `tier_updated_at`/`tier_updated_by`/`tier_note` in das
  Profil (merge, andere Felder bleiben) und ein unveränderliches Dokument in
  `account_tier_audit`; anschließend wird der Tier-Cache verworfen, damit die
  Stufe sofort statt erst nach ≤60 s greift. Ein Konto in Löschung bekommt
  keine neue Stufe (`persistence_guard`). UI: Admin-Tab **Accounts**.
- **Usage ist persistent und tokenbasiert (seit 2026-10-01):** siehe §4 „Ein
  Tokenkonto für alle Modi". `app/services/usage_repository.py`
  (`FirestoreUsageRepository`) hält weiterhin genau einen Beleg pro logischem
  Lauf (`usage_run_key`: Idempotenz, Request-Fingerprint, Operations-Claims
  `ask:<provider>`/`consensus`/`resolve`, Chat-Kontext-Bindung, 12
  Transaktions-Retries, strukturierte 503 bei Erschöpfung). Run-Zähler,
  Run-Limits und das Deep-Think-Teilkontingent sind entfallen. `/prepare`
  admittiert und konsumiert sofort; Fan-out und `/consensus` bestätigen den
  Consume nur noch und claimen ihre Operation. `/resolve` erzeugt einen eigenen
  Lauf. `/usage` und `/user_status` liefern `token_budget`;
  `/usage/run/release` gibt nur nicht konsumierte Läufe (samt Hold) frei.
  Bookmark-, Feedback- und Vote-Grenzen liegen ebenfalls persistent in
  Firestore (`persistence_guard.py`); es gibt keinen prozesslokalen Abuse-
  Counter mehr.
- Wort-, Output-, Memory- und Watch-Limits kommen aus `app/core/config.py`
  (`get_word_limit`, `get_output_token_limit`, …) und können per Firestore
  (`app_config/models.limits`) überschrieben werden; veraltete Schlüssel wie
  `*_consensus_run_limit` und `free_/pro_deep_search_max_*` fallen bei der
  Normalisierung weg (`pro_deep_search_max_tokens` wird einmalig zu
  `reasoning_max_tokens`, solange das neue Feld fehlt). Mit Reasoning gilt
  `get_output_token_limit(tier, True) = max(Stufenlimit, reasoning_max_tokens)`;
  `get_word_limit` ignoriert den Schalter. Das Tokenkonto
  lebt getrennt in `app_config/agent_budget`.
- Die Antwortmodell-Picker wenden bei einem Tier-Wechsel die Free-/Pro-
  Defaults erneut an, solange der Nutzer für den jeweiligen Provider keine
  explizite Auswahl (`pref_select_*`) gespeichert hat. Explizite Picker-Werte
  haben Vorrang. Normale Watch-Runs lesen die aktuelle Stufe des Owners
  bei jedem Lauf neu und wählen danach `WATCH_MODELS_BY_TIER` (ein Upgrade wirkt
  deshalb auch auf bereits bestehende Watches nach Ablauf des Tier-Cache).
  **Plus fährt dabei die Free-Watch-Modelle**: mehr Watch-Slots
  (`watch_plus_active_limit`) und optional das tägliche Intervall
  (`watch_plus_daily_interval_allowed`), aber unveränderte Kosten pro Lauf.
  Publisher-Watches tragen dagegen intern `model_tier=free`; der Scheduler
  behandelt sie unabhängig vom Owner-Tier dauerhaft wie einen Free-Watch.
  Als interner Content-Betrieb zählen sie nicht gegen das aktive persönliche
  Watch-Limit der Admin-UID; das globale tägliche Watch-Run-Budget gilt weiter.

### Nutzergebundene Consensus-API (v1)
- Admins stellen über `POST /api/admin/api-keys` einen gescopten Schlüssel für eine
  aktive, E-Mail-verifizierte Firebase-UID aus. Nur die einmalige Antwort enthält den
  Klartextschlüssel (`cns_live_…`); Firestore speichert ausschließlich dessen
  SHA-256-Hash als Dokument-ID. Defaults sind `consensus:run` + `share:write`;
  `share:index` ist nur für Admin-UIDs ausstellbar und wird am Index-Endpoint
  zusammen mit der aktuellen Admin-Rolle erneut geprüft. Legacy-Keys erhalten
  nur die sicheren Defaults. Liste und Widerruf laufen über
  `GET/DELETE /api/admin/api-keys`.
- `POST /api/v1/consensus/runs` akzeptiert ausschließlich `question`,
  `reasoning` (dokumentierter Name des Reasoning-Schalters) und `deep_think`
  (veralteter Alias; eines von beiden `true` = Reasoning an, für alle Stufen,
  kein Pro-403 mehr); unbekannte Felder werden abgelehnt. Gespeichert wird der
  Schalter weiter als `request.deep_think` (Idempotenz alter Runs), die Antwort
  trägt `reasoning` und `deep_think` mit demselben Wert. Der Server wählt die
  sechs Antwortmodelle und die Consensus-Engine aus dem konfigurierten
  Balanced-Preset — mit und ohne Reasoning dieselben. Kosten, Limits, Modelle
  oder Modellanzahl sind keine Request-Felder.
- API-v1-Runs verwenden bewusst immer die sechs Familien des Balanced-Presets,
  einschließlich DeepSeek; für API-Kunden gibt es keinen Provider-Opt-out. Das gilt seit
  2026-08-25 auch für den admin-only Scheduled Publisher: sein typisierter
  Header `X-Consensus-Publisher: true` markiert nur noch die Herkunft (Lineage,
  Idempotenz, Kapazität) und verändert den Modellplan nicht mehr. Der frühere
  DeepSeek-Ausschluss in Antwort-Fan-out, Consensus-Engine/Fallback und
  Differences-Judges ist entfernt — er war nirgends sichtbar und hat nach einem
  Wechsel des Watch-Modellprofils auf DeepSeek unbemerkt nur noch zwei statt
  drei Antworten produziert. Der Modus wird Teil des Idempotenz-Requests und
  kann daher nicht mit einem regulären Run unter demselben Key kollidieren.
- UID + gehashter `Idempotency-Key` zeigen auf genau einen persistenten Run;
  derselbe Key mit anderem Request ergibt 409. Der API-State folgt
  `accepted → reserved → running → succeeded|failed`. Der transaktionale
  `reserved→running`-Claim ist die einzige Berechtigung zum Providerstart.
  Doppelte HTTP-Requests/Worker können deshalb weder doppelt konsumieren noch
  den Provider-Fan-out doppelt starten.
- Die Usage-Reservierung nutzt `FirestoreUsageRepository` auf demselben
  Tokenkonto wie App und Agent: beim Annehmen wird der Lauf gegen die
  Consensus- bzw. Reasoning-Schätzung (`deep_think`) der Stufe admittiert
  (`token_admission_for_run`, Admin-Rolle zählt), beim Übergang zu `running`
  konsumiert, und nach der Pipeline bucht `OperationBooking("pipeline",
  final=True)` die gemessenen Tokens aller Antworten und Judges, auch bei
  Fehlern. Kein Konto mehr → 429 („daily token allowance does not cover another
  run"). Fehler vor Providerstart releasen (Hold frei), Fehler nach
  Providerstart bleiben konsumiert. Watches, Topics und Publisher-Watches
  behalten ihre eigenen globalen Budgets; der Publisher-Run selbst läuft über
  API v1 und bucht damit auf das Konto der Admin-UID.
  Provider- und Engine-Aufrufe liegen immer außerhalb aller Transaktionen.
  Jeder neue Run speichert seinen eigenen, nicht wiederverwendbaren
  Usage-Beleg `usage_key = consensus-api:run:{run_id}`; Retries desselben Runs
  teilen ihn, ein späterer Run erbt ihn nie. Ältere Runs ohne Feld behalten den
  historischen Schlüssel `consensus-api:{idempotency_hash}`.
- Kann ein `accepted` Run seine Reservierung nicht mehr verwenden (Usage-Beleg
  abgelaufen, etwa nach Absturz zwischen Usage-Reserve und `mark_reserved`),
  gibt `fail_unrecoverable_accepted_run` einen noch reservierten Slot frei und
  beendet den Run als `failed` mit `error.code=reservation_expired`
  (Recovery und erneuter POST); kein Endlos-Retry, keine Providerarbeit.
- `api_consensus_runner.py` übergibt die Ausführung an die neutrale
  `consensus_pipeline.py`: `provider_transport.py` führt den deterministischen
  parallelen Provider-Fan-out aus, danach laufen unverändert `query_consensus`
  und `query_differences`. Browser, API, Watch und Topic verwenden damit
  dieselbe Pipeline; es gibt keine zweite Consensus-Engine. Produktadapter
  projizieren nur ihre zusätzlichen Persistenzfelder.
  `GET /api/v1/consensus/runs/{run_id}`
  liefert nur eigene Runs und nach Erfolg das persistierte Ergebnis. Reservierte
  Runs werden beim Startup sicher neu eingeplant; laufende Runs werden nie
  wiederholt und nach abgelaufenem Lease als `worker_interrupted` beendet. Vor
  dem Usage-Consume wird der Firebase-/Block-Status erneut geprüft. Eine
  deduplizierte Queue lässt höchstens 32 aktive/wartende Run-IDs bei zwei
  parallelen Pipelines zu; der periodische Maintenance-Tick nimmt persistierte
  Restarbeit wieder auf und reconciled pre-provider Usage-Reservierungen.
- Run-Inhalt und Idempotenz-Mapping tragen `expires_at` (30 Tage ab Annahme);
  periodischer Cleanup löscht beide, bestehende v1-Dokumente werden beim
  ersten Maintenance-Lauf nachmigriert. `DELETE /api/v1/consensus/runs/{run_id}`
  löscht Inhalt eigener terminaler Runs früher: Das Run-Dokument wird durch
  einen inhaltsfreien Tombstone (`status=deleted`, UID, Key-Hash, Zeitstempel,
  ursprüngliches `expires_at`) ersetzt, das Idempotenz-Mapping bleibt. Derselbe
  Key liefert danach stabil `410` mit `error.code=run_deleted` und startet nie
  erneut kostenpflichtige Arbeit; `GET`/erneutes `DELETE` liefern 404.
  Tombstone und Mapping verschwinden mit dem ursprünglichen Retention-Ablauf.
  Der Retention-Backfill liest Run und Mapping erneut in einer Transaktion:
  vorhandene Ablaufdaten bleiben erhalten, fehlende Annahmedaten werden nicht
  erfunden, und ein inzwischen an einen anderen Run gebundenes Mapping wird
  weder verändert noch neu angelegt. Naive Legacy-Zeitstempel gelten als UTC.
  Alle v1- und Admin-Key-Antworten sind
  `private, no-store`. Limits greifen vor Auth pro IP/API-Key und danach pro UID.
- Der maschinenlesbare Vertrag kommt aus den typisierten FastAPI-Routen unter
  `/openapi.json` (Security-Scheme `ConsensusApiKey`, Header `X-API-Key` und
  Pflichtheader `Idempotency-Key`).
- Erfolgreiche eigene Runs werden per `POST .../{run_id}/share` direkt (ohne
  24h-Pending-Zwischenschritt) in einen unveränderlichen Public-Snapshot
  überführt. Eine deterministisch aus der privaten Run-ID abgeleitete 95-Bit-
  Share-ID macht Retries idempotent; `GET /api/v1/shares` liefert Resume-/
  Themenhistorie, `DELETE` widerruft. `PUT .../indexing` erzwingt neben
  `share:index` den Quality-Filter sowie Deduplikation gegen bereits indexierte
  gleiche `question_hash`-Seiten und schreibt API-Key-/Review-Auditfelder.
- `scripts/publish_consensus.py` orchestriert Themenwahl (optional OpenAI
  Responses API + Web Search), einen deterministischen Search-Title-Quality-
  Check mit bis zu drei Auswahlversuchen, Run/Poll, Publish, Weekly-Watch und
  optionale Indexfreigabe ohne externe Python-Abhängigkeiten. Nach erfolgreicher
  Veröffentlichung sendet es bei gesetztem `TELEGRAM_BOT_TOKEN` und
  `TELEGRAM_CHAT_ID` Frage und Share-URL per Telegram; Benachrichtigungsfehler
  bleiben nicht-fatal und der Token wird nicht in Fehler-URLs geloggt. Vor dem
  Lauf liest das Skript die Admin-Konfiguration aus Firestore über API v1; deaktivierte
  Publisher enden erfolgreich ohne LLM-Call. `.github/workflows/publish-consensus.yml`
  startet ihn montags, mittwochs und freitags um 07:15 UTC oder manuell. Die
  Themenauswahl priorisiert anhand einer Websuche hochaktuelle, eng benannte
  KI-Produkt-/Modellfragen mit jungem Suchfenster und geringer Konkurrenz im
  exakten Suchintent; Policy-/Regulierungsfragen werden für automatisch gewählte
  Titel hart ausgeschlossen. Secrets bleiben ausschließlich in
  GitHub Actions. Publisher-Run und Watch-Runs laufen auf demselben
  Providerkreis wie alles andere; das früher persistierte
  `excluded_providers=[deepseek]` ist Code- wie datenseitig entfernt.
- Nur ein API-Run mit persistiertem `request.publisher_mode=true` markiert den
  erzeugten Share als `publication_source=scheduled_publisher`; normale API-
  und Nutzer-Shares erhalten diese Lineage nicht. Neue Publisher-Watches sind
  auf maximal 12 aktive (im Publisher-Config-Dokument konfigurierbar) begrenzt.
  Für Kapazität/Admin-Zähler gilt das ausschließlich vom Admin-Publisher
  gesetzte `model_tier=free` als Legacy-Marker; ein Hintergrund-Backfill ergänzt
  fehlende explizite Lineage nur nach Verifikation des ursprünglichen
  `request.publisher_mode`.
  Volle Kapazität liefert `watch_skipped_capacity`, lässt die Veröffentlichung
  erfolgreich und pausiert/löscht keine bestehenden Watches.

### Sharing
- `og_image.share_card_png` bindet seinen Cache an alle gezeichneten Inhalte:
  Share-ID, Frage, Score, Modell-/Konfliktzahl, Historienwerte und Prüflabel.
  Die öffentliche OG-Route verwendet weiterhin den neuesten gültigen
  öffentlichen Stand und eine leere Historie; private/widerrufene Shares
  erhalten kein Bild. Reale PNG-Regionen und semantische Zeichenaufrufe werden
  gemeinsam geprüft, damit ein gültiges, aber leeres PNG nicht genügt.
- `/consensus` legt ein `pending_results`-Dokument an → `result_id`.
- Die Consensus-API publiziert dagegen direkt aus ihrem 30-Tage-Run-Snapshot;
  `source_api_run_id` bleibt serverintern und wird nie Teil der Public-Payload.
- Consensus-Bookmarks speichern diese ID mit, solange sie gültig ist. Bei
  Follow-ups wird der Live-Verweis bewusst nicht übernommen, weil dessen
  Pending-Snapshot nur die aktuelle Frage kennt. Beim
  Teilen/Watchen eines älteren, geöffneten Bookmarks erzeugt
  `POST /bookmark/consensus/share-result` aus dem serverseitigen Bookmark
  best-effort einen neuen sanitisierten Pending-Snapshot; Share/Watch warten
  auf diese Rehydration und können dadurch auch außerhalb der Ursprungssession
  verwendet werden. Ein Versions-Gate verhindert, dass eine verspätete Antwort
  auf ein inzwischen anderes angezeigtes Ergebnis zeigt.
- `POST /api/share` (`share.py` → `share_snapshots.create_share_from_pending`)
  macht daraus einen unveränderlichen Share-Snapshot (`shares`-Collection) mit
  Slug. Pending-Backlink, Tagesquote und Share-Anlage bilden eine einzige
  Firestore-Transaktion; parallele Retries liefern denselben aktiven Share und
  verbrauchen die Quote nur einmal. Dasselbe gilt für die deterministische
  Publikation erfolgreicher API-Runs. Besucher-Reports aktualisieren
  Gesamtzähler und Grundaggregat transaktional, sodass parallele Meldungen keine
  Increments verlieren; ab `REPORT_REVIEW_THRESHOLD` (5) setzen sie nur
  `needs_review`. Seit Review R19 ändern Reports `indexed` nie selbst, weil sich
  anonyme Meldungen nicht als unabhängig nachweisen lassen; Deindexieren oder
  Blocken ist eine Moderationsentscheidung (`moderate_share`).
- **`GET /s/{slug_id}`** rendert read-only aus dem Snapshot (keine LLM-Calls).
  `public_markdown.py` erhält LaTeX-Delimiter im serverseitigen HTML; die
  Share-Seite setzt sie anschließend mit derselben KaTeX-Brücke wie die App.
  Public-Snapshots enthalten JSON-LD, Canonical-Dedup über `question_hash` und
  „verwandte Fragen"; **Indexierung (`index, follow`) nur wenn der Admin `indexed`
  setzt** — nie automatisch; sonst `noindex`. Private Watch-Snapshots werden am
  Endpoint serverseitig auf die Eigentümer-Session geprüft und nie indexiert,
  gecacht, reportet oder als Related/Sitemap-Ziel ausgegeben. Public-Caching via
  `SHARE_CACHE_CONTROL` + In-Process-Cache (`get_share_cached` /
  `invalidate_share_cache`). Seit Review R18 gibt es eine feste obere Grenze für
  die Widerrufsverzögerung (`PUBLIC_REVOCATION_MAX_DELAY_SECONDS`, 5 Minuten):
  Der In-Process-Cache lebt 60 s (Invalidierung wirkt nur im eigenen Prozess,
  andere Worker holen den Status spätestens nach der TTL frisch), und
  `SHARE_CACHE_CONTROL` erlaubt Browsern/Proxies 60 s plus 60 s
  `stale-while-revalidate`. Aktuelle Watch-Seite, historische
  `?version=`-Ansichten und die OG-Karte nutzen denselben Header; nichts
  Widerrufbares wird mehr `immutable` oder langlebig ausgeliefert. Terms und
  Privacy sagen entsprechend „within a few minutes“ statt „immediately“.
  Verwandte Fragen teilen pro Prozess einen kompakten Kandidatenbestand
  (weiterhin höchstens 400 `indexed`-Dokumente pro Scan, nur `active` und
  `public`, TTL 15 Minuten). Frageausschluss und Ranking erfolgen je Seite im
  Speicher; Cache-Fill und Moderationsinvalidierung sind serialisiert.
  Explizit übergebene DBs umgehen diesen Cache.
- Lösch-/Moderationswege: Owner `DELETE /api/share/{id}`, Besucher-`report`,
  Admin-`moderate`. Der Admin kann Shares außerdem sofort hart löschen; dabei
  werden zugehörige Watch-Scheduler-Daten, Watch-History und Follower entfernt.
  Sonst erfolgt der 30-Tage-Hard-Delete widerrufener Shares via `cleanup_revoked_shares`.

### Kuratierte Topics
- Alle fünf Topic-Adminmethoden verifizieren Firebase-Tokens mit
  `check_revoked=True` und prüfen danach die echte Adminrolle. Ein Ausfall des
  Rollendienstes ergibt 503; nicht autorisierte Requests lesen oder verändern
  keine Topics. Der gemeinsame HMAC-Unterbau von Topic-/Watch-Follow-Tokens
  bedeutet keine Austauschbarkeit: Watch-, Share-Follower- und Topic-Aktionen
  verlangen ihre eigene Payloadform, bevor ein Dokumentzugriff erfolgt.
- `query_claim_identity` akzeptiert ausschließlich JSON-Integer als Index,
  keine Bool-/Float-/String-Coercion. Nur bekannte, einmal verwendete Keys und
  Indices im übergebenen Fenster werden gebunden. Ungültige Antworten bzw.
  ein unbekanntes Modell ergeben keine Zuordnung; der Aufrufer behält seinen
  bisherigen Fallback für neue Claims. Promptfenster und Retryplan bleiben
  begrenzt. Die Entscheidung und Nachweise stehen unter
  [Adapter-Implementierung](test-coverage/product/implementation-adapters.md).
- `topics.list_runs` liest lange Historien über `observed_at DESC` mit
  `max_items + 1` als Limit und gibt die letzten Runs weiter chronologisch
  nach Datum/Version/Dokument-ID aus. Bei kurzen Historien beweist eine
  ungefilterte `count()`-Abfrage im selben Read-only-Transaktionssnapshot,
  ob auch Legacy-Dokumente ohne Datum enthalten sind. Nur bei Abweichung,
  ungültigen Datumswerten oder Timestamp-Gleichstand an der Seitengrenze
  bleibt der vollständige Kompatibilitätsread erhalten. Kein neuer Topic-Index
  oder Backfill nötig; der normale kurze Verlauf kostet N Dokumente plus
  die Count-Aggregation statt zweier Vollabfragen.
- `/topics/{slug}` liest für Timeline und aktuelle Ansicht die neuesten 100 Runs
  (`TOPIC_PAGE_RUNS`). Ein expliziter `?version=<run_id>` außerhalb dieses
  Fensters wird direkt per `topics.get_run` unter dem bereits aufgelösten Topic
  geladen (Review R33); fremde oder unbekannte IDs bleiben 404. Das As-of-Bild
  einer solchen Version stammt aus `topics.list_runs_until` (ein begrenzter
  `observed_at <= run`-Read, neueste 100 bis einschließlich der Version). Ist ein
  Fenster abgeschnitten (`run_count` bzw. Versionsnummer größer als die
  gelesenen Runs), nennen Zähler den gespeicherten Gesamtwert, und Texte wie
  „since the first check“, „Every check“ oder „since {Datum}“ behaupten keine
  Vollständigkeit mehr.
- Topics sind bewusst **keine Shares und keine Nutzer-Watches**. `topics/{id}`
  hält redaktionelle Metadaten plus die ausführbare `run_config` mit konkretem
  `provider_models`-Mapping, `update_interval`, Quellenpräferenzen, SEO, Status
  `active|paused|archived`, `next_run_at` und kurze Lease-/Fehlerfelder. Das
  denormalisierte `models`-Array enthält nur öffentliche Labels; ausführbare
  Modell-IDs stehen ausschließlich in `run_config`.
- `topic_runner.py` hängt über den eigenen Adapter `topic_pipeline.py` direkt an
  der neutralen Provider-/Consensus-/Differences-Pipeline und importiert keine
  Watch-Services. Die pro Topic gespeicherte Modellauswahl bleibt maßgeblich. Jeder Lauf
  recherchiert aktuelle Webquellen neu, dedupliziert sie zu Evidence, vergleicht
  Consensus (über `evidence_change.assess`, mit Quellen) mit dem **geltenden**
  Run (`accepted_run_id`, Altbestand `latest_run_id`) und die Opinion Map mit dem
  Vorgänger und schreibt einen unveränderlichen
  Vollsnapshot nach
  `topics/{id}/runs/{run_id}`: Consensus-Markdown, Agreement, Change-Typ/
  -Summary, wichtige Modellbewegungen, Differences/Opinion Map, Modelle,
  Quellenregeln und Evidence.
  Run-Dokument und Latest-Pointer/-Score/`run_count` am Topic werden gemeinsam
  in einer Transaktion veröffentlicht. Automatische Completion und
  Fehlerabschluss sind an `current_run_id` gebunden; ein abgelaufener Worker
  kann deshalb keinen neueren Claim überschreiben. Mindestens zwei konfigurierte Provider sind Pflicht; Links,
  Consensus-Text, Agreement und Meinungsänderungen werden nicht manuell für
  normale Runs eingegeben. Der eigene 60-Sekunden-Scheduler in `main.py`
  beansprucht fällige Topics per Firestore-Lease; manuelle Admin-Runs benutzen
  denselben Claim. Paused/archived Topics werden nicht ausgeführt.
- `/topics/{slug}` rendert SSR, sanitisiertes Markdown, JSON-LD, Current- und
  historische `?version=`-Ansichten. Das vollständige Dossier mit Consensus,
  Position Map, Agreement-Verlauf und aktuellen Quellen sowie die Timeline
  starten geöffnet; die schwer scanbaren separaten „What holds now / What
  changed / Why“-Karten sind entfallen. Von den nach Qualität sortierten
  aktuellen Quellen sind die besten fünf direkt sichtbar, der Rest und ältere
  Evidence starten separat eingeklappt. Die
  Hub-Karte verwendet den letzten Snapshot-/Change-Status statt freien
  redaktionellen Beschreibungstexts. Evidence bekommt die Rollen
  `primary|research|documentation|reporting|community|rumor`, wird nach Rolle
  sortiert und trennt direkte Quellen von nachrangigen Community-/Gerüchte-/
  Redirect-Signalen. Seit Review R14 ändern Quellenregeln nie das Etikett:
  `topic_runner.split_evidence_from_sources` behält die erkannte Rolle und
  schließt Quellen mit nicht erlaubter Rolle aus (`excluded_evidence` am Run,
  mit Original-ID/URL, öffentlich nur als Anzahl). Bleibt keine erlaubte Quelle,
  zeigt die Seite „Insufficient eligible evidence“. `preferred_domains` sind nur
  noch ein Sortierhinweis innerhalb einer Rolle (`is_preferred`) und machen eine
  Quelle nicht mehr zur Primärquelle. Nur Topics mit
  Run und Status Active/Paused erscheinen im Hub; `seo.noindex` entfernt sie
  zusätzlich aus `sitemap-topics.xml`. Historische Query-Ansichten sind
  `noindex` und werden wie die aktuelle Ansicht nur kurz gecacht (max-age 60,
  s-maxage 300), damit ein archiviertes Topic auch mit seinen Versionen
  verschwindet (Review R18).
- Besucher-Follows sind ein eigener Double-Opt-in-Flow in `topic_followers` und
  teilen keine Dokumente mit `watch_followers`. Minor/Major-Runs legen bei
  konfiguriertem SMTP je Follower ein Outbox-Item im selben Commit wie den Run an
  (`notification_outbox`, Retry und Abmeldeprüfung vor jedem Versuch);
  Stable-Runs nicht. Der Admin-Run verwendet dieselbe Drift-Schwelle wie Watch-Seiten.
  Bestätigungs-/Abmelde-Tokens verwenden den vorhandenen HMAC-Unterbau und
  `WATCH_UNSUBSCRIBE_SECRET`, tragen aber einen eigenen Topic-Token-Typ.
- Der Topic-Editor liegt als Tab unter `/admin#topics`; `/admin/topics` ist nur
  ein 308-Kompatibilitätsredirect dorthin. `admin.js` trennt Listenauswahl
  (`selectedTopicId`), tatsächlich geladene Formular-ID (`loadedTopicId`) und
  eine Editor-Generation: nur die jüngste Auswahl füllt das Formular, Save ist
  während eines Wechsels und nach fehlgeschlagenem Laden gesperrt und schreibt
  ausschließlich an die ID, deren Daten das Formular hält. Neuer Topic,
  Reload und Kontowechsel (`resetAdminTopicEditor`) invalidieren offene
  Editor-Requests. Seine `/api/admin/*`-Antworten werden
  durch die Security-Middleware als `private, no-store` ausgeliefert.

### SEO-Leistungsdaten und Recommendation Judge (Search Console, v2)
- `FirestoreSeoRepository.list_metrics_for_pages` bündelt höchstens 400
  Dokumentreferenzen pro BatchGet. Ungeordnete Ergebnisse werden über den
  angeforderten Dokumentpfad zugeordnet; `snapshot.id` bestimmt den Tag.
  Gespeicherte `page_id`-/`date`-Felder können keine Messung in eine fremde
  Seite oder einen anderen Tag verschieben. Fehlende Dokumente bleiben
  fehlende Messungen statt künstlichem Nulltraffic.
- Der manuelle admin-only Lauf `POST /api/admin/seo/collect` übernimmt exakt die
  statischen URLs aus `pages.py::SITEMAP_URLS`, aktive, öffentliche,
  indexierte Shares aus `list_indexed_share_urls` sowie indexierbare Topics aus
  `list_indexed_topic_urls`; er verändert weder diese
  Seiten noch Indexierungs-, Publisher- oder Robots-Zustände.
- `google_search_console.py` nutzt ausschließlich den Scope
  `webmasters.readonly` über `google-auth` + autorisiertes HTTP. Search Analytics
  fragt `page,date` mit `dataState=final`, Pagination, maximal 31 Tagen pro
  Teilabfrage und einem harten Seitenlimit ab. Der letzte erfasste Tag liegt drei
  UTC-Tage zurück; pro neu/missing URL-Tag werden beim ersten Lauf bis zu 90 Tage
  zurück aufgefüllt, danach nur fehlende finale Tage.
- `POST /api/admin/seo/check` prüft per read-only `sites.get` live, ob das
  Service Account auf die konfigurierte Property zugreifen kann. Die Antwort
  enthält nur einen sanitisierten Status und niemals Credential-Dateipfad,
  Credential-Felder oder Google-Response-Body.
- `seo_data.py` filtert GSC-Zeilen auf das aktuelle indexierbare URL-Set und
  schreibt fehlende URL-/Tageswerte idempotent. `GET /api/admin/seo` aggregiert
  Klicks, Impressions, CTR und impressionsgewichtete Position über 7/28 Tage
  und klassifiziert transparent als `insufficient_data`, `emerging`, `winner`,
  `opportunity`, `declining` oder `invisible`. Zusätzlich wird pro Seite ein
  minimiertes Dossier (First-Seen/Publish-/Änderungszeit, Titel, Description,
  begrenzte Inhaltszusammenfassung sowie Quellen-/Watch-Frische) gepflegt. Für
  die letzten 28 finalisierten Tage werden maximal 20 Top-Queries mit Klicks,
  Impressions, CTR und Position als eigener Snapshot gesammelt; höchstens 100
  noch fehlende Seiten-Snapshots pro Lauf. Row-Cap und aus Datenschutzgründen
  verworfene Kontakt-/Identifier-Queries werden als `partial` markiert.
- `seo_recommendation.py` erzeugt aus Status, Dossier, finalen Daten und
  Query-Abdeckung deterministisch `wait|monitor|protect_winner|refresh_title_and_intro|
  refresh_content|investigate_decline|noindex_candidate`. Letzteres verlangt
  gleichzeitig mindestens 60 Beobachtungstage, 28 finale Tageszeilen, praktisch
  keine Sichtbarkeit, keinen positiven Trend und keinerlei technische/Query-
  Unklarheit; `invisible` allein reicht nie. Ergebnisse landen idempotent und
  append-only im Journal. Der separate Content-Judge wird nur durch den Admin-
  Button für `opportunity`, `declining` oder bereits abgesicherte
  `noindex_candidate`-Fälle aufgerufen, validiert ein striktes JSON-Schema und
  kann den Noindex-Schutz nicht überstimmen. Er ist nur mit explizitem Modell
  aktiv. Keine Empfehlung mutiert Seiten, Indexierungs-, Robots-, Redirect-
  oder Publisher-Zustände. Umami-, GA4- und URL-Inspection gehören weiterhin
  nicht zum Flow. GSC-Zeilen
  können unvollständig sein und treffen zeitverzögert ein; die Admin-Ansicht
  weist darauf hin.

### Wöchentlicher SEO-Portfolio-Review
- `seo_weekly_review.py` wird alle 15 Minuten vom eigenen Lifespan-Task geprüft
  (Defaultintervall sieben Tage, Defaultzeit 09:00 Europe/Berlin) und kann im
  SEO-Admin per „Run now“ gestartet
  werden. Ein transaktionaler, 45 Minuten gültiger Lease in
  `app_config/seo_weekly_review` verhindert prozessübergreifende Doppelläufe.
- Jeder Lauf aktualisiert zuerst Search Console und erzeugt dann für alle
  aktuell oder historisch in `seo_pages` erfassten Seiten die bestehende
  deterministische Empfehlung (die normale Admin-Tabelle bleibt active-only).
  Der Portfolio-Lauf ist vor den teuren Unterabfragen auf 100 Seiten begrenzt
  und verwendet die vom Overview bereits geladenen Seiten-, 28-Tage- und
  Query-Daten für die Recommendation erneut; pro Seite gibt es keinen zweiten
  Firestore-Metrikscan. Die Auswahl ist eine dauerhafte Rotation statt eines
  alphabetischen Schnitts: `seo_pages.weekly_review_seen_at` (nie gesehen zuerst,
  dann am längsten nicht gesehen, aktive Seiten vor inaktiven) bestimmt die 100
  Seiten, jeder Lauf stempelt seine Seiten. Das Review speichert
  `portfolio_coverage` (`considered_pages`, `total_pages`, `truncated`), und die
  Admin-Hinweisleiste zeigt eine Teilabdeckung ausdrücklich an.
  Erst danach darf genau ein Portfolio-Judge-Call mit GPT-5.6 Terra und
  mittlerem Reasoning erfolgen, sofern der Server-OpenAI-Key gesetzt ist; bei
  vollständig fehlgeschlagener Collection gibt es keinen Call. Unvollständige Query-Daten dürfen im Bericht
  stehen, blockieren aber serverseitig Noindex und Delete.
- Die sieben Gruppen sind `keep_indexed`, `pause_watch_only`, `resume_watch`,
  `noindex_only`, `noindex_and_pause_watch`, `delete_candidate` und
  `manual_improvement` (im Admin als „Editorial decision required“). Für diese
  Gruppe speichert der Run eine seitenbezogene Entscheidungsvorlage; immutable
  Share-Snapshots schlagen einen neuen Nachfolger statt einer In-place-Änderung
  vor. Bestätigungen speichern nur Entscheidung/Follow-up und mutieren den
  Snapshot nicht. Gespeicherte Vorschläge mutieren nichts. Preview/Apply
  prüfen Lineage, Index-/Watch-Zustand, Recommendation-Fingerprint und Noindex-
  Safeguards erneut; kombinierte Aktionen protokollieren beide Teilergebnisse.
  Watch-Pause/Resume ändern nie `indexed`, Noindex nie implizit den Watch.
  `Apply all` schließt Hard-Delete serverseitig aus; Noindex/Delete-Bulk ist nur
  für Shares mit `publication_source=scheduled_publisher` erlaubt.
- Der Judge darf bei mindestens drei reifen Seiten optional einen Topic Brief
  vorschlagen. Die Admin-Annahme vergleicht den damaligen mit dem aktuellen
  Brief und speichert nur `topic_brief` über `publisher_config.save_config`;
  automatische Prompt- oder Action-Übernahmen existieren nicht.

### Kritische Fehler-Alerts (Telegram, seit 2026-10-03)

Ziel: Ein Alert lässt sich unverändert in Claude Code einfügen und führt dort
direkt zur Codestelle. Betreiber-Anleitung: [`error-alerts.md`](error-alerts.md).

- **Quellen.** (1) Globaler Exception-Handler in `main.py` (ungefangene
  Request-Exceptions, auch nach Stream-Beginn), (2) `background_tasks.py`
  (Absturz eines Lifespan-Tasks nach drei Fehlern bzw. Einmal-Task sofort),
  (3) `error_alerts.report_server_exception(exc, where=…)` an Stellen, die
  Fehler abfangen und nur loggen: `chat.consensus_stream`,
  `chat.differences_stream`, `consensus_engine.coverage_merge`,
  `consensus_engine.coverage_judge`, `agent.turn_stream`. Dort alarmieren nur
  Programmierfehler (`error_context.is_unexpected_exception`: AttributeError,
  Lookup-/Name-/Type-/Arithmetik-/Assertion-/Rekursionsfehler,
  NotImplementedError) — Abbrüche, Provider-/Netz-/Timeout-, Firestore- und
  Domänenfehler (inkl. ValueError) bleiben beim Log. (4) Browser über
  `POST /api/client-errors` (§2, `error-reporter.js` §3).
- **Inhalt Server.** `error_context.server_error_report`: `type` =
  `safe_exception`, bis zu acht Repo-relative Frames `pfad:zeile:funktion`
  (innerster zuerst, Bibliotheks-Frames entfernt), `commit`
  (`version.get_commit_short`), `instance`, `correlation_id`, beim Handler
  `path` = `METHODE Routen-Template` und `status`. Die Exception-Message bleibt
  bewusst draußen (kann Nutzerinhalt tragen); die Frames sind der Fundort.
- **Correlation-ID.** `CorrelationMiddleware` legt die ID zusätzlich unter
  `observability.CORRELATION_SCOPE_KEY` in den ASGI-Scope: Starlettes
  `ServerErrorMiddleware` ruft den Handler außerhalb der Middleware auf (Kontext
  schon zurückgesetzt, send-Wrapper umgangen). Der Handler nimmt die ID aus dem
  Scope (sonst `err-…`), loggt in deren `correlation_scope` (Log-Zeile mit
  `[corr=…]` und `at=<safe_traceback>`) und setzt `x-correlation-id` am 500er.
- **Zustellung.** `telegram_notifier.dispatch_critical_error_notification`
  reserviert synchron (Dedup + Budget) und sendet auf einem Daemon-Thread
  `critical-alert` — unabhängig vom Response; früher hing der Alert als
  BackgroundTask am 500er und lief bei schon gestarteten SSE-Antworten nie.
  Background-Tasks und Browser-Intake senden weiter synchron im eigenen
  Thread bzw. BackgroundTask des 202ers.
- **Dedup/Budget.** Schlüssel ist `critical_fingerprint` (8 Hex; Quelle, Typ,
  Phase, Pfad, Ressource/Asset/Failure, Fehlername, Ort bzw. innerster Frame —
  ohne Message). Identische Alerts 10 min unterdrückt; je Prozess eigene Budgets
  `server` 10 und `browser` 5 pro 10 min. Unterdrückte werden je Fingerprint
  gezählt und am nächsten zugestellten Alert als `(+N similar since last alert)`
  angezeigt. Ein fehlgeschlagener Versand (HTTP-Fehler, `ok:false`, Exception)
  gibt Slot und Zähler frei und loggt WARNING mit Telegram-`description`
  (nie den Token).
- **Format.** Klartext ≤ 4096 Zeichen: Kopfzeilen (Source, Type, Environment,
  Instance, Commit, Time, Phase, `Route: … -> 500` bzw. `Path:`, Correlation,
  Browser: Bundle, `Error: Name: message`, `Location: static/js/x.js:z:s
  (bundle app.<hash>.js:1:s)`), Meldung, `Frames (innermost first)`, Details;
  zuletzt immer (Kürzung davor) die Zeile `fix-context: fp=… commit=… route=…
  corr=… [bundle=… loc=…] frames=a < b`.
- **Source-Maps.** Der Build schreibt `static/dist/<bundle>.js.map`
  ([`frontend-build.md`](frontend-build.md)); `app/core/sourcemaps.py`
  dekodiert sie (lru-gecacht, nur allowgelistete Bundle-Namen, fehlende oder
  kaputte Map → Bundle-Koordinate bleibt stehen).

---

## 5. Backend-Struktur

```
main.py                      App-Entry, Middleware, Router-Registrierung, lifespan
app/core/
  background_tasks.py        Supervisor, Restart-Backoff, Alerts und Task-Health
  config.py                  Modell-Kataloge, Tier-Limits, Firestore-Sync (load_models_from_db)
  entitlements.py            Die drei Kontostufen free/plus/pro: normalize_tier + Entitlements
  site.py                    Validierte kanonische PUBLIC_SITE_URL ohne Router-Abhängigkeit
  security.py                Firebase-Init, Token/Tier/Admin-Checks (get_user_tier, is_user_pro, is_user_plus), CSP-Middleware
  request_limits.py          ASGI-Bodylimit vor JSON-/Form-Parsing (Content-Length + chunked)
  rate_limit.py              slowapi-Limiter (erste, von Render gesetzte Client-IP in XFF) + prozesslokale UID-Budgets
  observability.py           PII-freie Correlation-IDs (auch im ASGI-Scope), strukturierte Logs + Prozessmetriken
  error_context.py           Inhaltsfreier Alert-Fundort: Repo-Frames, Commit, Instanz, Programmierfehler-Filter
  sourcemaps.py              VLQ-Decoder: Browser-Bundle-Koordinate -> static/js/<datei>.js:<zeile>:<spalte>
app/api/routers/             siehe §2
  api_v1.py                  Gescopte Run-, Publish-, Share-Lifecycle- und Indexing-API + OpenAPI-Modelle
  chat_history.py            Owner-gebundene Chat-/Turn-API inkl. vollständigem Turn-Detail
app/services/
  prompt_config.py           DB-Konfiguration der Systemprompts, Validierung, Transaktionsrevisionen und 30-s-Cache
  prompt_defaults.py         Versionierte Ausgangstexte für Agent, Einzelantworten und Synthese
app/services/llm/
  provider_runtime.py        Zentrale Timeout-/Retry-Policy + Stream-Cancellation
  provider_transport.py      Kanonischer Provider-Fan-out, Labels, Key-/Transport-Dispatch
  base.py                    System-Prompt, Wortzählung, validate_model
  engines.py                 Gemeinsamer OpenRouter-Payload und query_model
  streaming.py               OpenRouter-SSE-Streamer, SSE-Helfer, Response-Adapter
  consensus_engine.py        query/stream_consensus + query/stream_differences, strukturierter Engine-Dispatch
  consensus_parsing.py       JSON-Extraktion und abgesicherte Truncation-Reparatur
  consensus_scoring.py       Deterministischer Agreement-Score und Schwellen
  coverage_judge.py          Schema/Prompt/Parsing des Coverage-Judges (rein, ohne LLM-Call)
  resolve_engine.py          Resolve-Runde (run_resolve_round, normalize_resolve_positions)
  citations.py               Antwort-Parsing + Quellen (source_response, make_llm_result)
  attachments.py             Attachment-Validierung/Aufbereitung
  usage_meter.py             Token-Meter der Transportschicht (ContextVar; Usage je OpenRouter-Request, Schaetzung bei fehlender Usage)
app/services/
  consensus_pipeline.py      Neutraler Fan-out→Synthese→Differences→Score-Vertrag für alle Produkte
  chat_store.py              Firestore-Pfade, Turn-Lifecycle/Antwortdokumente, atomare Finalisierung, Idempotenz, Cursor + Allowlists, Loesch-Kaskade
  chat_context.py            Owner-gebundene Context-Versionen, strukturierte Memory, Frage-Auflösung vor dem Fan-out, Budgets, Lease/Idempotenz, Fallback-Rendering + Provider-Cache
  usage_repository.py        Run-Belege auf dem Tokenkonto (admission/authorize_operation/reserve/consume/release/book_operation/get_run/context-target-binding)
  run_metering.py            OperationBooking: Meter um eine Pipeline-Operation binden, Summe genau einmal buchen
  agent_quota.py             Gemeinsames UTC-Tokenkonto (Agent-Reserve/Settle, Pipeline-Admission/Holds/Buchung, account_tier)
  agent_budget_config.py     Admin-Konfiguration des Kontos: tier_limits, run_estimates, Revision/Reset
  api_account_cleanup.py     Fail-closed Account-Blocks + retrybare API-Datenlöschung
  account_deletion.py         Persistenter Vollkonto-Tombstone + bereichsweise Retry-Kaskade
  persistence_guard.py       Transaktionale Bookmark-/Feedback-Budgets + run-gebundene Votes
  registration.py            Nicht-enumerierender Firebase-Mailbox-Setup-Pfad
  follow_challenges.py       Gehashte persistente Resend-/Empfänger-/Globalbudgets für Double-Opt-in
  api_key_repository.py      SHA-256-gehashte, UID-gebundene API-Schluessel
  api_run_repository.py      Idempotenz + persistente API-Run-State-Machine
  api_consensus_runner.py    Asynchroner At-most-once-Orchestrator auf bestehenden Engines
  publisher_config.py       Firestore-Steuerung des Scheduled Publishers + Weekly/Free-Watch-Fakten
  google_search_console.py  Read-only Search-Analytics-HTTP-Client + sichere Config-Fehler
  seo_repository.py         Firestore-Modell fuer SEO-Seiten, Tages-/Query-Metriken, Runs + Judgement-Journal
  seo_dossier.py            Minimierte statische/Share-Seitendossiers ohne UID/Secrets
  seo_data.py               URL-Discovery, inkrementelle Collection, Query-Snapshots + Statusregeln
  seo_recommendation.py     Deterministische Regeln + optionaler strukturierter Content-Judge
  seo_weekly_review.py      Leased Terra-Portfolio-Review, Gruppen/Entscheidungen + Topic-Brief-Vorschlag
  telegram_notifier.py      Gemeinsamer Bot-API-Client, Critical-Alerts (Fingerprint, Budgets, fix-context) + SEO-Review-Meldungen
  error_alerts.py           report_server_exception: abgefangene Programmierfehler in Streams als Alert
  telegram_watch.py         User-Link-Deep-Links/Webhook, Callback-Aktionen + ein Watch-Nachrichtenversuch (send_watch_message)
  notification_outbox.py     Dauerhafte Benachrichtigungs-Outbox (notification_outbox): stabile Delivery-IDs, Lease, Versuche, Terminalstatus
  notification_delivery.py   Ein Zustellversuch je Outbox-Item mit Abmelde-/Pause-/Kanalprüfung + Retry-Pass run_outbox_tick
  share_snapshots.py         Snapshot-Lifecycle (pending→share), Quoten, Cleanups, Sitemap-Quellen
  favicons.py                Begrenzter Favicon-Fetch, Singleflight, LRU-/Negativcache
  retention_maintenance.py   Periodischer Pending-/Revoked-Share-Cleanup + Outbox-Retention (30 Tage, nur Terminalstatus)
  watch_service.py           Watch-CRUD, Tier-/Intervall-/Zielregeln, Lauf-Abschluss (Signal, geltende Antwort, Abschluss), Unsubscribe-Tokens
  evidence_change.py         Change-Judge mit Quellen + serverseitige Belegprüfung (Ursache, tragende Quellen), geteilt von Watch und Topic
  watch_probe.py             Täglicher Beleg-Scan zwischen zwei Checks: Claim, ein günstiger Such-Call, Vorziehen des vollen Checks
  opinion_map.py             Datenminimierte, mehrdimensionale Provider-Positionen + Direction-Shift-Berechnung
  watch_brief.py             Morning-Brief-Settings (watch_briefs), transaktionaler Claim, Digest-Aggregation, Brief-Unsubscribe-Tokens
  watch_scheduler.py         Owner-gebundener Global-Lease, Tagesbudget, Pipeline-Adapter, run_brief_tick + Outbox-Retry-Pass
  mailer.py                  Multipart-HTML/Plaintext-SMTP-Versand via Thread-Executor
  public_markdown.py         Server-Markdown-Rendering für Share-Seiten
  topics.py                  Kuratierte Topic-Konfiguration, immutable Runs, Public-Discovery und eigene Follower/Dedupe-Daten
  topic_runner.py            Leased Topic-Research/Consensus-Runs, automatische Evidence/Meinungsänderungen + Intervall-Scheduler
  topic_pipeline.py          Topic-spezifische Projektion auf die neutrale Consensus-Pipeline
  differences_stats.py       Anonyme Differences-Telemetrie (differences_stats-Collection, §6)
```

Wichtige Verträge im Backend:
- Provider-Label-Set überall identisch: `OpenAI, Mistral, Anthropic, Gemini,
  DeepSeek, Grok` (Claude→Anthropic). `normalize_model_name` vereinheitlicht.
- `/consensus` braucht **mind. 2** nicht-ausgeschlossene Antworten.
- `*-Pro`-Consensus-Engines und Premium-Modelle sind Pro-gated.

---

## 6. Datenhaltung / Firebase / Konfiguration

**Firestore-Sicherheitsregeln und Indizes** (`firestore.rules` und
`firestore.indexes.json`, Quellen der Wahrheit im Repo; Deployment per Firebase
CLI mit `firebase deploy --only firestore:rules,firestore:indexes`):
- **Deny-all für alle Clients.** Kein Browser-Code spricht direkt mit Firestore —
  `static/firebase.js` initialisiert zwar `getFirestore()`, benutzt die Variable
  `db` aber nirgends. Sämtlicher Datenzugriff läuft über das Backend mit dem
  Firebase-Admin-SDK, und das umgeht die Regeln vollständig.
- **Schreibrechte auf `users/{uid}` dürfen NIE wieder geöffnet werden.**
  `app/core/security.py` liest Pro- (`tier`) und Admin-Status (`role`) aus genau
  diesem Dokument. Eine frühere Regel erlaubte dem eingeloggten Eigentümer
  `write` — damit konnte sich jeder Nutzer per `setDoc(..., {role:"admin"})`
  selbst zum Admin machen. Wer Rollen künftig client-schreibbar braucht, muss
  sie vorher aus `users/{uid}` herauslösen (z. B. Firebase Custom Claims).

**Firestore-Collections** (verifiziert über Code):
- `users/{uid}` — `tier` (`free`/`plus`/`pro`, historisch auch `premium` = Pro)
  plus `tier_updated_at`/`tier_updated_by`/`tier_note`, `role`; Subcollections `bookmarks`, `counters`, `chats`,
  `chat_state`, `watch_state` und `watch_uniques` sowie
  die produktive run-basierte Usage:
  `bookmarks` speichert pro laufender Unterhaltung genau ein Dokument unter der
  stabilen ID des ersten Turns. `query`/`responses` bilden den letzten Stand;
  nach erfolgreicher Persistenz referenzieren `chat_id` und `turn_id` den
  kanonischen owner-gebundenen Transcript. Vollständige ältere Turns werden
  nicht im Bookmark dupliziert. `previous_question`/`previous_turn` bleiben nur
  als Legacy-Fallback für Bookmarks ohne Chat-Bindung.
  - `chats/{chat_id}` — serverseitig zufällig erzeugte, nicht aus Titel oder
    Frage abgeleitete 32-Hex-ID; Felder `schema_version`, `title`,
    `status=active|deleting`, `created_at`, `updated_at`, `turn_count` und
    `latest_question`. Letzteres ist nur eine NFKC-normalisierte, whitespace-
    zusammengefasste Vorschau von höchstens 300 Zeichen; die vollständige Frage
    bleibt ausschließlich im Turn. Ein leer erstellter Chat erhält mit dem ersten Turn einen
    normalisierten, serverseitig auf 120 Zeichen gekappten Titel aus der Frage.
    Alle Zugriffe beginnen beim verifizierten Pfad `users/{uid}`; unbekannte und
    fremde IDs liefern gleichförmig 404. `GET /chats` liefert nur kompakte
    Metadaten, absteigend nach `updated_at`, höchstens 50 Dokumente pro Seite.
    `chat_state/quota` hält den transaktionell serialisierten `active_count`;
    Altbestände initialisieren ihn beim ersten Schreibzugriff aus dem begrenzten
    Owner-Bestand. Create und das Setzen von `status=deleting` erhöhen bzw.
    verringern ihn in derselben Transaktion. Erst danach löscht die idempotente
    Kaskade Turns, Modellantworten, Context-Versionen und zuletzt den Chat.
  - `chats/{chat_id}/turns/{turn_id}` — `schema_version`, monoton aus dem
    Chat-Zähler vergebene `position`, `status=pending|completed|failed`, begrenzte `question` und
    `mode`, boolesches `deep_search`, begrenzte/normalisierte
    `selected_models`, `consensus_model`, `created_at`, `updated_at` und optional
    `client_request_id`/`context_version_id`. Turn-Anlage und Chat-Update (`turn_count`,
    `updated_at`, `latest_question`) laufen in einer Firestore-Transaktion. Bei
    `client_request_id` wird die Turn-ID aus einem serverseitigen SHA-256-Digest
    abgeleitet; derselbe Key im selben Chat erzeugt deshalb keinen zweiten Turn.
    Stimmt der normalisierte Payload (`question`, `mode`, `deep_search`,
    `selected_models`, `consensus_model`) mit dem vorhandenen Turn überein, wird
    dieser zurückgegeben; andernfalls endet der Retry ohne Änderung mit 409.
    `GET .../turns` sortiert nach `position` und liest höchstens 100 Dokumente
    pro Seite; es bleibt kompakt und enthält keine Ergebnis-Texte oder Quellen.
    `GET .../turns/{turn_id}` liefert owner-gebunden die whitelisted Vollansicht;
    unbekannte/fremde Chat-Turn-Kombinationen sind gleichförmig 404.
  - Bei erfolgreicher Finalisierung ergänzt das Turn-Dokument `consensus`,
    `differences`, sanitierte `differences_data` und `sources`, ausschließlich
    kanonische `included_models`, serverseitig berechnete `answer_count` und
    (nur falls vorhanden) den aus den sanitisierten Differences abgeleiteten
    `agreement_score`; optional kommt eine validierte `result_id` hinzu.
    `completion_fingerprint`, `completed_at` und `updated_at` sind intern;
    der Fingerprint wird nie von der API ausgegeben. Der SHA-256-Fingerprint
    umfasst die normalisierte Turn-Identität, Antworten samt Modell-Labels und
    Quellen, Consensus, Differences, Differences-JSON, Turn-Quellen und
    `result_id` in kanonischer JSON-Serialisierung. Ein identischer Completion-
    Retry schreibt nichts, ein abweichender endet als Conflict.
  - `pending → completed` und `pending → failed` sind die einzigen Übergänge.
    Ein identischer Fail-Retry ist schreibfrei idempotent; abweichende Fail-
    Retries, `failed → completed` und `completed → failed` sind Conflicts.
    Failed Turns ergänzen ausschließlich `status=failed`, einen der Codes
    `consensus_failed|cancelled|insufficient_answers|persistence_interrupted`,
    `failed_at` und `updated_at`; Providerfehler oder freie Clienttexte werden
    nicht persistiert.
  - `chats/{chat_id}/turns/{turn_id}/model_answers/{provider}` speichert pro
    erfolgreicher Antwort genau ein Dokument. Die einzige Pfad-Allowlist ist
    die Provider-Registry (`cfg.PROVIDER_LABEL_BY_ID`, aktuell
    `openai|mistral|anthropic|gemini|deepseek|grok|kimi|glm|meta`); Dokumentfelder sind
    `schema_version`, kanonischer `provider`, begrenztes `model_label` und
    `answer`, über den Share-Sanitizer normalisierte `sources`, `created_at` und
    `updated_at`. Leere/fehlgeschlagene Antworten erzeugen kein Dokument. Turn,
    höchstens sechs Antwort-Dokumente und `chat.updated_at` werden in einer
    Firestore-Transaktion nach allen Reads geschrieben; `turn_count` und
    `latest_question` bleiben dabei unverändert. Consensus (100.000 Zeichen),
    Differences (50.000), Modellantworten (dynamisches Consensus-Answer-Limit),
    Modell-Labels (80), Result-ID (16) und Quellenfelder (URL 2.000, Titel 300,
    Provider 40) sind serverseitig begrenzt. Quellen haben kein Anzahl-Limit;
    Turn und jedes Modellantwort-Dokument werden oberhalb von 750.000
    serialisierten Bytes vor den Writes abgewiesen. Responses und Persistenz verwenden
    Feld-Allowlists; API-Keys, Tokens, Credentials, Roh-Attachments und
    unbekannte Felder werden verworfen.
  - `watch_state/quota` serialisiert die Zahl aktiver Owner-Watches;
    `watch_uniques/{sha256(uid,scope,key)}` bindet je nach Anlage entweder die
    Share-ID oder den Query-`question_hash` an genau eine Watch. Anlage,
    Pause/Resume, Auto-Pause und Löschung pflegen Zähler, Uniqueness-Key und bei
    Query-first zusätzlich die Share-Hülle transaktional. Die Kontolöschung
    entfernt beide Subcollections nach der Watch-Kaskade.
  - `chats/{chat_id}/context_versions/{version_id}` ist eine ausschließlich
    abgeleitete, owner-gebundene Context-Version. Sie referenziert Ziel-Turn,
    jüngsten wörtlichen completed Turn und die bis zu einer Position
    zusammengefassten älteren completed Turns, enthält die validierte
    strukturierte Memory, eine auf tatsächlich referenzierte Turns begrenzte
    Provenienzkarte (`turn_id → source_count`), den Vorgänger-Versionslink,
    Quell-Fingerprint, Builder-/Schema-Version,
    Engine-Metadaten, feste Budgetwerte und `ready|building`-Lifecyclefelder.
    Eine deterministische ID plus zeitlich begrenzte Build-Lease verhindert
    parallele Komprimierungen; erst die fertige Version wird atomar am Ziel-Turn
    als `context_version_id` **und `resolved_question`** verknüpft. Letzteres ist
    die einmal vor dem Fan-out selbststehend gemachte aktuelle Frage
    (`ChatMemoryCompressor.resolve_question`, läuft ab dem ersten Follow-up):
    sie ersetzt die Frage nie, sondern geht zusätzlich in den Kontext der sechs
    Modelle und — vom Turn gelesen, nie aus dem Request — an Consensus- und
    Judge-Engine. Steht die Frage schon für sich oder scheitert der Rewrite,
    bleibt sie leer und die Frage geht roh raus. Keys, Providerfehlertexte und Roh-Prompts
    werden nie gespeichert. Vollständige Turns werden weder ersetzt noch
    verändert; bei Fehlern entsteht eine explizit `degraded` markierte,
    deterministische Fallback-Memory. Die Provenienzkarte hält validierte
    Turn-/Quellenreferenzen inkrementeller Memory auch dann stabil, wenn der
    betreffende Roh-Turn außerhalb des begrenzten 200-Turn-Lesefensters liegt.
    Zwei Dinge gelangen bewusst in **keinen** abgeleiteten Kontext:
    `differences_data` (Meta-Ebene des Laufs — Agreement-Score, Widersprüche,
    Judge-Metadaten, Modell-Klarnamen; sie las sich im Kontext wie Inhalt und
    hob die Anonymisierung des Consensus-Prompts ab dem zweiten Turn auf) und
    die Antwort eines *anderen* Modells. Vom letzten Turn sieht ein Provider den
    gemeinsamen Konsens plus **seine eigene** Antwort aus `model_answers` —
    deshalb wird der Kontext pro Provider gerendert und der Fan-out-Cache ist
    pro Provider verschlüsselt. Memory aus älteren Builder-Versionen wird nie
    fortgeschrieben.
  - Erfolgreiche normale Browser-Runs schreiben den ersten completed Turn;
    Turn 2 und alle späteren Fortsetzungen schreiben nur bei einer als completed
    bestätigten `activeChatId` in denselben Chat. Pending Chat-/Turn-/Context-IDs
    bleiben bis zur autoritativen Disposition separat; `/ask_*` schreiben nicht
    direkt. Legacy-Follow-ups ohne aktive Chat-Zuordnung bleiben ausschließlich
    im Bookmark-Flow. Bookmarks werden vorübergehend parallel weitergeschrieben.
  - `usage_days/{YYYY-MM-DD}` — **seit 2026-10-01 nicht mehr geschrieben**
    (frühere Run-Zähler). Alte Dokumente bleiben unverändert liegen und werden
    beim Account-Löschen mit entfernt.
  - `usage_runs/{sha256(idempotency_key)}` — idempotenter Run je UID + Key; der
    Klartext-Key wird nicht gespeichert. Enthält (Schema 3)
    `kind=regular|deep_think` (`deep_think` = Reasoning an, Kompatibilitätsname),
    den UTC-Tag der Admission, `quota_day`
    (Kontoperiode inkl. Reset-Generation), `token_tier`, `admission_mode`,
    `admission_estimate`, `token_limit_at_admission`, `booked_operations`
    (`{operation: {measured, estimated, booked_at}}`, Exactly-once-Zaun der
    Buchung), `request_fingerprint`, `expires_at`,
    `operation_claims` mit Claim-Zeit/Payload-Fingerprint und
    `status=reserved|consumed|released`. `utc_date` ist nur der Abrechnungstag;
    `expires_at` (`execution_expiry`) ist die getrennte Ausführungs-/Retry-
    Gültigkeit: Ende des Abrechnungstags, mindestens aber zwei Stunden
    (`MIN_EXECUTION_WINDOW`) nach der Reservierung. Ein um 23:59 belasteter Run
    beendet seine autorisierten Schritte nach Mitternacht ohne zweite Belastung;
    neue Runs zählen für den neuen Tag. Ein für Chat-Memory verwendeter Run
    erhält zusätzlich ausschließlich `context_target_hash` und
    `context_bound_at`; derselbe konsumierte Key kann damit nur einen
    Chat-/Turn-Context finanzieren, ohne einen weiteren Zähler zu verändern.
    Erlaubte Übergänge: `reserved → consumed` (Admission bei `/prepare`) oder
    `reserved → released` (fehlgeschlagener/abgebrochener Run gibt seinen Hold
    frei); beide Zielzustände sind terminal, Wiederholungen idempotent. Der Key
    kann nicht für einen anderen Run-Typ/Request wiederverwendet oder über
    seine begrenzte Ausführungsgültigkeit hinaus abgespielt werden. Provider-/LLM-Aufrufe finden immer
    außerhalb der Transaktion und erst nach Consume plus erfolgreichem
    Operations-Claim statt. Beim Account-Löschen werden beide Subcollections entfernt.
    `/ask_*`, `/consensus` und `/resolve` bündeln Run-Bindung, gegebenenfalls
    Admission/Consume und Operations-Claim in `authorize_operation`: zwei
    Dokument-Reads (Account-Tombstone, Run) für vorbereitete Läufe; nur ein
    Legacy-Direktaufruf ohne `/prepare` liest zusätzlich das Kontodokument und
    wird dort admittiert. `/prepare` und die externe Consensus-API behalten
    ihren Reserve-/Consume-Vertrag.
  - `chat_state/agent_tokens_{YYYY-MM-DD}[_{reset_epoch}]` — das gemeinsame
    Tokenkonto (Agent + Pipeline): `used` (gemessen, beide Modi), `reserved`
    (Agent-Reservierungen), `estimated` (Agent-Schätzungen, später
    reconciled), `pipeline_used` (Anteil der Pipeline an `used`),
    `pipeline_estimated` (Schätzungen für Pipeline-Calls ohne finale Usage),
    `pipeline_holds` (`{run_hash: {tokens, expires_at}}`, max. 32 aktive,
    zehn Minuten), `pipeline_runs`, `unknown`/`unknown_released`, `revision`.
  - `api_consensus_idempotency/{sha256(idempotency_key)}` — Mapping von UID +
    gehashtem HTTP-Idempotency-Key auf `run_id` und kanonischen `request_hash`;
    verhindert auch bei parallelen POSTs doppelte Runs. Kein Klartext-Key.
- `api_consensus_keys/{sha256(api_key)}` — admin-ausgegebene API-Schlüssel mit
  `uid`, nicht-geheimem Präfix/Label, `status=active|revoked`, den Scopes
  `consensus:run|share:write|share:index` und Audit-Zeitstempeln. Der
  Klartextschlüssel wird nie gespeichert.
- `api_consensus_account_blocks/{uid}` — temporärer fail-closed Tombstone bei
  Account-Löschung (`blocked`, `cleanup_pending`, Fehler-/Audit-Zeitstempel).
  Er wird vor jeder Löschkaskade geschrieben, von HTTP und Worker geprüft und
  nach erfolgreichem Cleanup plus Firebase-Löschung entfernt; transiente
  Cleanup-Fehler werden periodisch wiederholt.
- `account_deletion_jobs/{uid}` — allgemeiner, idempotenter Löschauftrag und
  Auth-Tombstone mit `status=pending|completed`, `completed_areas`, aktuellen
  Fehlern und Audit-Zeitstempeln. Pending sperrt ohne Zeitlimit; nach kompletter
  Kaskade werden E-Mail/sonstige Hilfsdaten entfernt und nur der UID-Tombstone
  noch zwei Stunden behalten. Der Maintenance-Loop wiederholt ausschließlich
  nicht quittierte Bereiche und entfernt abgelaufene completed Tombstones.
  Sämtliche owner-gebundenen Mutationen — unter anderem Usage, Chats/Context,
  Bookmarks/Votes/Feedback, Pending-/Public-Shares, Watches/Briefs/Telegram,
  API-Runs/-Keys und Waitlist — lesen diesen Tombstone innerhalb derselben
  Firestore-Transaktion wie ihren Write. Cleanup-interne Deletes besitzen dafür
  einen benannten Bypass; normale Requests nicht.
- `account_tier_audit/{id}` — eine unveränderliche Zeile je Stufenwechsel
  (`uid`, `from_tier`, `to_tier`, `changed_by`, `note`, `changed_at`), von
  `app/services/account_tier.py` geschrieben und im Admin-Tab **Accounts**
  gelesen. Ein fehlgeschlagener Audit-Write lässt die bereits gesetzte Stufe
  stehen und wird geloggt — der Adminvorgang darf daran nicht scheitern.
- `api_consensus_runs/{run_id}` — UID-gebundener v1-API-Run mit serverseitig
  eingefrorenem Request/Modellplan, `idempotency_hash`, eigenem `usage_key`, Status und Status-
  Zeitstempeln, einstündigem Running-Lease, der bei Annahme eingefrorenen Stufe
  (`tier_at_acceptance`, mit `is_pro_at_acceptance` als Altfeld) sowie terminal
  `result` oder sanitisiertem `error` und 30-Tage-`expires_at`. Erlaubte Hauptfolge:
  `accepted → reserved → running → succeeded|failed`; zusätzlich
  `accepted → failed` (`reservation_expired`) und nach Owner-Löschung der
  inhaltsfreie Tombstone `succeeded|failed → deleted` bis zum Retention-Ablauf.
- `app_config/prompts` — globale Prompt-Konfiguration aus `prompt_config.py`:
  `prompts.agent`, `prompts.answers`, `prompts.consensus`, `reference_timezone`,
  `delegation` (aktiviert, Rollenprompts, Laufzeit-/Kontext-/Nachrichten-/Parallelitäts-
  und Budgetlimits; Defaults/Migration in `agent_delegation_config.py`),
  ganzzahlige `revision`, UTC-`updated_at` und Admin-UID bzw. Wartungskennung `updated_by`.
  `GET /api/admin/prompt-config` (Router `admin.py`) liest frisch und liefert
  zusätzlich Defaults und Limits; es erzeugt keinen Datensatz.
  `PUT /api/admin/prompt-config` verlangt `revision` plus vollständige `config`,
  validiert IANA-Zeitzone und exakt drei nichtleere Texte (je höchstens 10.000
  Zeichen / 28.000 UTF-8-Bytes, keine Steuerzeichen außer Tab/Zeilenumbrüchen).
  Die Grenzen lassen Platz für den Datumsblock beim `/prepare`→`/ask_*`-Roundtrip
  mit dessen 12.000-Zeichen-/32.000-Byte-Limit.
  Beide Endpoints prüfen widerrufbare Auth-Tokens und `is_user_admin`.
  Eine Firestore-Transaktion prüft die erwartete Revision und schreibt aktive
  Konfiguration sowie vollständigen Audit-Snapshot unter
  `app_config/prompts/revisions/{revision:012d}` gemeinsam. Konflikte liefern 409;
  der Browser bewahrt den Entwurf. Unveränderte bereits gespeicherte Werte
  erzeugen keine neue Revision. Runtime-Reads sind pro Worker 30 Sekunden
  gecacht; bei Lesefehlern bleibt der letzte gültige Stand oder der App-Default
  aktiv. Admin-Lese-/Schreibfehler liefern 503 und keine vorgetäuschte Speicherung.
  `prompt_defaults.py` ist der versionierte Fallback und die Quelle für Reset.
  Freitext wird als Text behandelt, nicht als interpolierte Vorlage. Datum,
  Modellidentität, Verlauf, Quellen-/Antwort-Scaffolding und Tooldefinitionen
  werden weiterhin im Code zusammengesetzt. Eigene Nutzer-Prompts haben für
  Einzelantworten Vorrang. Judge-/Resolve-/Spezialprompts bleiben im Code.
- `app_config/models` — von `load_models_from_db()` gelesen/erzeugt: erlaubte
  Modelle pro Provider, `premium`, `consensus`, `preset_models`,
  `judge_models`, `judge_models_pro`, `judge_families`, `watch_models`,
  `watch_consensus_models`, `defaults`,
  `limits` sowie die sichere, einzeln normalisierte `memory_edit`-Konfiguration
  (Kill-Switch, OpenAI-Modell, Zeichen- und Tageslimits je Stufe, Minuten-/
  Globallimit, Input-/Output- und Timeout-Caps).
  **Single Source of Truth für Limits/Modelle in Produktion** (überschreibt die
  `config.py`-Fallbacks beim Startup). Providerlisten und `premium` sind dabei
  autoritativ: der Runtime-Loader ergänzt keine versteckten Pflichtmodelle und
  Premium enthält nur IDs, die auch in einer Providerliste stehen.
  `GET /api/admin/models` normalisiert Legacy-/Tombstone-Werte ausschließlich
  für die Response und bleibt strikt read-only, damit ein paralleler Read nie
  einen frisch gespeicherten Judge-Wert mit einem älteren Komplett-Snapshot
  überschreibt. Nur `POST /api/admin/models` persistiert die Modellkonfiguration
  und wird bei inkonsistenten Defaults/Presets/Watches/Judges mit 400
  abgelehnt statt serverseitig still korrigiert. Erst danach wird persistiert
  und unter einem Runtime-Lock vollständig neu geladen; schlägt ein Apply-Schritt
  fehl, werden sowohl das vorherige Firestore-Dokument als auch alle zuvor
  aktiven Runtime-Sets/Maps/Limits restauriert und der Admin-Request schlägt
  fehl. Das Dokument trägt eine monotone `revision` (R25): `GET` liefert sie, die
  Admin-UI sendet sie beim Speichern zurück, und `POST` schreibt per
  Transaktion nur, wenn sie noch aktuell ist (sonst 409, nichts geschrieben).
  Der Rollback nach fehlgeschlagener Aktivierung ersetzt nur die eigene, noch
  gespeicherte Revision (unter neuer Revisionsnummer) und nie eine inzwischen
  von einem anderen Prozess geschriebene. Jeder Prozess merkt sich die aktive
  Revision und prüft sie im Lifespan-Task `model-configuration-sync` alle 60 s
  mit einem Read; bei neuer Revision lädt er vollständig neu. Ein einzelner
  Reload muss dabei vollständig sein: `apply_model_order`/`apply_default_models`
  laufen vor Preset-/Judge-/Watch-Normalisierung, die auf sie zurückfällt, und
  `rebuild_model_configs` baut `MODEL_CONFIGS` daneben auf und tauscht dann ein
  (nie leer für Leser). Grenze: ein
  einzelner Lauf liest weiter die prozessweiten Maps; eine Aktivierung während
  eines laufenden Requests ist nicht als Snapshot pro Lauf eingefroren.
  `consensus` steuert den App-Consensus-Picker;
  Fehlende Limitfelder werden beim Startup normalisiert und per Merge in das
  Admin-Dokument zurückgeschrieben (Schema-Backfill ohne Verlust vorhandener Werte).
  Werte können historische Engine-Aliase (`Gemini-Pro`) oder direkte Modell-IDs aus
  den Provider-Listen sein. In `/admin` können Provider-Modelle per `Consensus`-
  Checkbox in diese Liste aufgenommen werden. Das frühere Feld
  `deep_think_model` (Deep-Think-Engine) wird seit 2026-10-02 beim Lesen
  ignoriert, beim Admin-Speichern verworfen und nicht mehr geschrieben.
  `judge_models`/`judge_models_pro` setzen Standard- bzw. Pro-Differences-/
  Resolve-Judge je Provider (`apply_judge_models`/`apply_pro_judge_models` in
  config.py, in-place — consensus_engine/resolve_engine aliasen dieselben
  dicts; entfernte Legacy-Aliasse sind ausgeschlossen; Fallbacks kommen nur aus
  der jeweiligen konfigurierten Providerliste; Judges laufen mit gekappter
  Denktiefe: OpenAI/Gemini `low`, Mistral wegen dessen API-Vertrag `none`).
  `judge_families` mappt Engine-Familie → bevorzugte Judge-Familie
  (`apply_judge_families`; nie die eigene Familie, ohne Eintrag/Credential Auto
  über `JUDGE_FAMILY_PRIORITY`). Auto priorisiert OpenAI, dann Gemini; für
  OpenAI-Engines bleibt Gemini zuerst (keine Selbstprüfung). Danach folgen
  unverändert DeepSeek, Grok, Anthropic, Mistral, Kimi, GLM und Meta.
  Die Standard-/Pro-Modellzuordnung bleibt admin-konfiguriert. Differences
  und Coverage behalten ihre Retry-/Fallback-Pläne auch bei manueller
  Familienpräferenz; ein Provider-Rate-Limit verhindert den Wechsel zur
  nächsten geplanten fremden Familie nicht. In Serverpfaden verwenden
  alle Familien denselben OpenRouter-Key; im Own-Key-Modus gibt es keinen
  Fallback auf das Server-Credential.
- `app_config/scheduled_consensus_publisher` — Admin-Steuerung für den GitHub-
  Publisher: `enabled`, Themen-Brief, automatische Indexfreigabe sowie
  Aktivierung, lokaler Wochentag, Uhrzeit und IANA-Zeitzone des Weekly-Watches.
  Intervall (`weekly`) und Modellprofil (`free`) sind absichtlich nicht
  konfigurierbar und werden serverseitig erzwungen; `excluded_providers` bleibt
  als leeres Feld im Vertrag, damit ein künftiger Ausschluss eine lesbare
  Tatsache wäre statt einer Regel im Ausführungspfad;
  `max_active_publisher_watches` begrenzt neue aktive Watches (Default 12).
- `app_config/seo_weekly_review` — `enabled`, `interval_days` (Default 7),
  lokale `run_time` + IANA-`timezone`, `last_run_at`, `next_run_at` sowie
  kurzlebiger `lease_run_id`/`lease_until`.
- `pending_results` — kurzlebige Consensus-Ergebnisse fürs Sharing (TTL/Cleanup),
  mit `answer_provenance` (`developer|byok`) für die Ranking-Berechtigung.
- `answer_receipts/{receipt_id}` — serverseitige `/ask_*`-Antwortbelege
  (Owner, Run-Bindung, Frage-Hash, Familie, konkretes Modell, Text, Digest,
  Quellen, Abschlusszustand, Provenienz); 24 h `expires_at`, Retention-Sweep,
  Kontolöschung. Einzige Quelle für Modellantworten in `/consensus`.
- `source_check_jobs_dispatch_v1_local/{sha256}` bzw.
  `source_check_jobs_dispatch_v1_production/{sha256}` — UID-/Run-/Antwortversion-
  und Dispatch-Protokoll-/Umgebung-gebundener Jobheader; alte
  `source_check_jobs/{sha256}` bleiben über den historischen Lesepfad erreichbar.
  Header mit `worker_protocol`, `queue_environment`, letzter Worker-ID und
  optionalem `last_failure` (sicherer Fehlercode/Paketindex), außerdem
  Status, Revision, Paket-/Quellen-/Satzfortschritt, Lease-Token,
  `next_attempt_at` und Aufbewahrungsreferenzen. `data/plan` enthält den
  vollständigen komprimierten Plan, `packages/{index}` getrennte komprimierte
  Ergebnisse; jeweils höchstens 700.000 Zeichen Base64-Payload. Die gesamte
  Planung wird atomar angenommen, kein Quellenzähl-Limit kürzt den Inhalt.
  Paketseiten umfassen vier Pakete. Unreferenzierte Jobs werden nach 30 Tagen
  per Cleanup gelöscht; lebende Elternreferenzen verlängern die Aufbewahrung.
- `source_check_cache/{sha256}` — UID-gebundene Dokument-/Judge-Cacheeinträge
  mit komprimiertem Payload und `expires_at`; keine API-Keys. Die eigene
  Cache-ID bindet auch Frage-/Dokument-/Promptkontext des jeweiligen Cachetyps.
- `source_check_workers/{process-id}` — nicht geheime 30-s-Prozessmarken für
  Own-Key-Affinität, alle zehn Sekunden separat erneuert; außerdem Dispatch-
  Protokoll, Queue-Umgebung und Worker-Build zur Diagnose, keine Keys.
  Queue und Ablaufbereinigung nutzen einzelne Feldindizes.
  `firestore.indexes.json` nimmt die großen Jobfelder `snapshot`,
  `source_totals`, `statement_totals`, `references` sowie Cache-/Plan-/Paket-
  `payload` aus der automatischen Indexierung. Diese Konfiguration muss beim
  Deployment über den bestehenden Firestore-Index-Workflow mit ausgerollt
  werden; die lokalen Änderungen allein stellen keine Indexkonfiguration bereit.
- `persistence_usage/{kind-sha256(uid)}` — transaktionale, restart- und
  multi-worker-feste Bookmark-Anzahl/-Bytes sowie Feedback-Cooldown/-Tageszahl;
  weder UID noch E-Mail stehen im Dokumentpfad. `model_votes/{sha256(uid:result)}`
  bindet genau einen Vote an Owner, Pending Result und serverseitigen Gewinner.
  Erst derselbe Firestore-Commit erhöht `leaderboard/{provider}`. Seit
  2026-10-02 zählen auch Agent-Turns: `AgentRunStore.finish_run` schreibt bei
  erfolgreichem, geprüftem Turn (`agent_review.status` succeeded/partial) in
  derselben Transaktion `model_votes/{sha256(uid:agent:chat:turn:BestModel)}`
  (`source: "agent"`, `vote_subject_id: agent:{turn}`) und erhöht
  `leaderboard/{family}.BestModel` — Pick aus dem Check der breitesten
  Comparison (`persistence_guard.agent_best_model_choice`, Alias Claude →
  Anthropic). Unter `MOCK_LLM=1` wird nichts geschrieben. Seit 2026-10-03
  tragen beide Vote-Arten zusätzlich `participants` (Provider-Keys der
  verglichenen Antworten: Consensus aus `pending.included_models`, Agent aus
  der breitesten Comparison), `picked` und `pulse_version: 1` — der Nenner der
  Model-Pulse-Rate (`model_pulse.participation`; weniger als zwei Familien oder
  ein Pick außerhalb des Laufs → Felder entfallen). Ältere Votes ergänzt
  `scripts/backfill_model_pulse.py` (Dry-Run per Default, `--apply` schreibt nur
  diese drei Felder), soweit Chat-Turn/Bookmark des Laufs noch existiert.
- `memory_edit_usage/{sha256(uid)}` und `global_usage/memory-edit-YYYY-MM-DD` —
  persistente per-User-/Minuten-/Tages- und globale Tagesreservierungen samt
  kurzem In-flight-Lease; keine Memory- oder Feedback-Inhalte. Idempotenz- und
  Revisionsdokumente liegen unter `users/{uid}/memory` und werden mit dem Konto
  gelöscht; der Undo-Vorzustand darin verfällt nach 30 Tagen. Single-Field-
  Collection-Group-Indizes auf `memory.undo_expires_at` und `memory.lease_until`
  (`firestore.indexes.json`) tragen die Retention-Queries.
- `chat_deletion_jobs/{sha256(uid:chat)[:40]}` — dauerhafte, idempotente
  Einzelchat-Löschaufträge (`uid`, `chat_id`, `status`, `attempts`,
  `last_error`-Kategorie, `next_attempt_at`), angelegt atomar mit dem
  `deleting`-Tombstone, gelöscht nach vollständiger Kaskade bzw. mit
  `delete_all_chats` bei der Kontolöschung. Keine Inhalte.
- `follow_challenges/{sha256(scope:resource:email)}` — ausschließlich gehashte
  Double-Opt-in-Challenges mit 15-Minuten-Resendfenster, höchstens fünf Sends
  pro Empfänger/UTC-Tag und global höchstens 500/Stunde; kein E-Mail-Klartext.
- `shares` — unveränderliche Snapshots (Slug, `visibility=public|private`,
  `indexed`, `status`, `owner_uid`, `question_hash`, optional interne
  `source_api_run_id`, `publication_source=scheduled_publisher` und Index-
  Review-Auditfelder, …). `publication_source` existiert nur bei explizitem
  Publisher-Modus. Public-Shares sind per
  Link lesbar; private Watch-Snapshots ausschließlich mit Eigentümer-Session.
- `topics/{topic_id}` — kuratierte, share-/watch-unabhängige Topic-Konfiguration
  mit `run_config.provider_models`, Intervall/`next_run_at`, Run-Lease/-Status
  und Latest-Pointer. `runs/{run_id}` darunter enthält append-only Vollsnapshots
  mit Consensus, Agreement, Change-/Meinungsbewegung, Modellen, Source Rules
  und zeitlich zugeordneter Evidence. `topic_followers` speichert nach
  Double-Opt-in nur `topic_id`, E-Mail und Zeitpunkt;
  `topic_follower_deliveries/{sha256(topic:run:follower)}` dedupliziert
  Material-Change-Mails. Es werden keine IP-/User-Agent-Daten gespeichert.
- `watches` — owner-gebundene Scheduling-Metadaten (`share_id`, `visibility`,
  Intervall, optionaler `run_weekday` für Weekly sowie lokale `run_time`
  (`HH:MM`) + IANA-`timezone`,
  optional internes `model_tier=free` für Publisher-Watches,
  denormalisierte `publication_source` für begrenzte Publisher-Kapazitätschecks
  ohne N+1-Reads der Share-Dokumente,
  (das früher hier persistierte `excluded_providers` ist entfernt: es wurde
  nirgends angezeigt und hat still einen Provider aus jedem Publisher-Lauf
  genommen),
  das aus Kompatibilitätsgründen so benannte `email_mode` als kanalneutrale
  Alert-Regel `changes_only|condition|every_run`, `email_enabled`,
  `telegram_enabled`, optionales `telegram_muted_until`, private
  `condition`, `last_condition_status`, Status, nächste Ausführung,
  Lease/Fehlerzähler sowie bis zu 16 denormalisierte `history_points` für
  Dashboard-Listen); keine IP-/User-Agent-Daten. Conditions werden nie in
  öffentliche Share-Payloads oder History-Punkte kopiert.
  Erfolgreiche Checks ohne messbaren Agreement-Score (`null`) bleiben in
  Watch-/Topic-Verlaeufen, Versionslinks, Change-Events und Position Maps erhalten.
  `history_view.py` laesst ihre Y-Koordinate leer und unterbricht die Zahlenkurve;
  Templates zeigen dafuer „Insufficient evidence“, niemals null/0 als Messwert.
  Verlaufspunkte liegen datenminimiert in `shares/{id}/watch_history` und
  verändern den Share-Snapshot nicht. Neben Score/Change-Metadaten können sie
  eine kompakte `opinion_map` tragen: maximal vier aus der strukturierten
  Differences-Analyse abgeleitete Dimensionen, kurze Standpunkte,
  Provider-Gruppen und einen 0–100 `shift_score`; niemals Rohantworten. Ein
  Stable-Urteil ergibt 0 Shift. Nicht zuverlässig gematchte, neu formulierte
  Dimensionen bleiben unbewertet statt automatisch 100/100; bestehende History
  wird beim Lesen sequenziell gegen den realen Vorgänger neu bewertet.
- `watch_runtime` — globaler Worker-Lease und datumsgebundener Tageszähler;
  verhindert parallele Scheduler-Worker und begrenzt Watch-Versuche restartfest.
  `global_worker` trägt `claimed_until`, `owner` (zufälliges Token je Tick) und
  `acquired_at`; nur der Eigentümer darf erneuern oder freigeben (R30).
- `notification_outbox/{sha256(kind,resource,run,channel,recipient)}` — dauerhafte
  Benachrichtigungsaufträge für Watch-Owner (Mail/Telegram, inkl. Pause nach drei
  Fehlern), Watch-Seiten-Follower, Topic-Follower und Morning Brief. Felder:
  `kind`, `channel`, `uid` (Owner, leer bei Topic), `resource_id`, `run_id`,
  `recipient_id` (UID oder Follower-Dokument-ID, keine E-Mail), `payload` (nur
  Frage, Scores, Change-Summary, Richtung; kein Consensus-Volltext),
  `status=pending|sent|skipped|failed`, `attempts`, `next_attempt_at` (zugleich
  Lease-Ende), `lease_owner`, `deliver_until`, `last_error` (Kategorie).
  Composite-Index `(status, next_attempt_at)` in `firestore.indexes.json`,
  `payload` ist vom Einzelfeldindex ausgenommen. Terminale Items löscht die
  Retention nach 30 Tagen; Kontolöschung entfernt alle Items der UID. Die alten
  Marker in `telegram_watch_deliveries` und `topic_follower_deliveries` werden
  vom Versandpfad nicht mehr geschrieben und laufen über die bestehenden Cleanups aus.
- `watch_briefs/{uid}` — user-level Morning-Brief-Einstellungen (`enabled`,
  `send_time` `HH:MM`, IANA-`timezone`, `mode` = `always|changes_only`,
  `next_send_at`, `last_evaluated_at`, `last_sent_at`, `enabled_at`). Reine
  Aggregation vorhandener Watch-/History-Daten — keine LLM-Calls, daher nicht
  Pro-gated.
- `telegram_connections/{uid}` + `telegram_chats/{sha256(chat_id)}` — nur
  serverseitig lesbare 1:1-Zuordnung eines Firebase-Accounts zu einem privaten
  Telegram-Chat; Link-Identität/Status, keine Nachrichteninhalte.
  `telegram_link_tokens/{sha256(token)}` hält einmalige 10-Minuten-Deep-Links;
  `telegram_watch_deliveries/{sha256(watch:run:kind)}` dedupliziert Zustellungen
  und protokolliert nur Status/IDs/Zeitpunkte, nicht den Consensus-Text; der
  Startup-Cleanup entfernt Deliveries nach 90 Tagen und abgelaufene Link-Tokens.
- `benchmark_runs` — admin-only Benchmark-Dashboard-Snapshots aus lokalen Runs:
  `manifest`, `results`, `audits`, abgeleitete Fragenmatrix; **keine**
  `calls.jsonl`-Rohantworten, Prompts oder Request-Payloads.
- `seo_pages/{sha256(url)}` — eine aktuell oder historisch beobachtete
  indexierbare Seite mit `url`, `origin=static_page|share|topic`, optionaler
  `share_id`, `active`, `indexable`, First-/Last-Seen-Zeitstempeln und dem
  minimierten `dossier` (Share-Inhaltsrepräsentation hart auf 3200 Zeichen begrenzt).
  `metrics_coverage_start|end` markieren ein nachweislich lückenlos
  persistiertes finales Tagesfenster. Folgeläufe lesen dadurch nicht erneut
  alle 90 Tagesdokumente je URL, sondern prüfen nur noch Tage außerhalb dieses
  Wasserstands; alte Datensätze ohne Marker werden einmalig per Dokumentabgleich
  migriert. Mehrseitige Tagesfenster werden über begrenzte Firestore-`get_all`-
  Pakete statt einer seriellen Subcollection-Query pro URL geladen; Page-Sync
  und Coverage-Wasserstände werden ebenfalls gesammelt per Write-Batch
  persistiert.
  Untercollection `daily_metrics/{YYYY-MM-DD}` ist die idempotente URL-/Tag-
  Einheit mit `url`, `date`, `clicks`, `impressions`, `ctr`, `position`,
  `collected_at`, `source=google_search_console`, `origin` und optionaler
  `share_id`. Untercollection `query_snapshots/{final_date}` enthält das finale
  28-Tage-Fenster, maximal 20 Top-Query-Zeilen, Coverage-/Partial-Metadaten und
  keine Länder/Geräte/UIDs; Query-Zeilen mit E-Mail-, Telefon- oder IP-Mustern
  werden nicht gespeichert. Ein fehlender GSC-Row wird für die
  aktuelle indexierbare URL als Nulltag (Position `null`) persistiert, weil GSC
  Zeilen auslassen kann — aber nur nach einer vollständig paginierten Abfrage;
  bei erreichtem Request-Cap bleiben ausgelassene URL-/Tage für einen Retry offen.
- `seo_collection_runs/{run_id}` — Audit eines manuellen Laufs mit Status,
  Start/Ende, finalisiertem Datumsfenster, URL-/Tages-/Zeilen-/Request-Zählern,
  Truncation-Flag und ausschließlich sanitisierten Fehlertexten. Credential-
  Dateipfad/-Inhalte, insbesondere `private_key`, und Google-Response-Bodies
  werden weder gespeichert, geloggt noch über Admin-Endpunkte ausgegeben.
- `seo_judgements/{det-hash|llm-uuid}` — append-only Journal mit `page_id`,
  Zeitpunkt, Regelversion, Datenfenster, raw-content-freier Dossier-Summary,
  Empfehlung, Konfidenz, Evidenz, Review-Frist, Schutzflags, optionaler strikt
  validierter LLM-Auswertung und nullable `user_feedback`. Deterministische
  Retries verwenden denselben Hash und überschreiben keinen Eintrag; Admin-UID,
  Secrets und vollständige Share-Inhalte werden nicht gespeichert.
- `seo_weekly_reviews/{run_id}` — kompakter Portfolio-Snapshot mit Status,
  Collection-Ergebnis, Summary/Findings, Gruppen, begrenzten Seitenempfehlungen
  und Fingerprints, redaktionellen Entscheidungsvorlagen/-bestätigungen,
  damaligem/optional vorgeschlagenem Topic Brief samt Pending/Accepted/Rejected-
  Entscheidung, Telegram-Versandstatus sowie den letzten 50 Action-Audits. Keine
  Secrets, Owner-UIDs oder vollständigen Share-Inhalte.
- `differences_stats` — anonyme Differences-Telemetrie (Schema v3): pro erfolgreichem
  Consensus-Lauf ein Dokument mit Zähl-/Strukturdaten (Agreement-Score,
  Widersprüche mit Severity und beteiligten Providern, Modell-Metadaten,
  seit v2 `judges`-Metadaten des tatsächlich genutzten Differences-Judges,
  seit v3 zusätzlich dessen erfolgreiche Attempt-Nummer und Versuchsdauer,
  `schema_version`) — **niemals** Frage-/Antwort-/Claim-Texte, Zitate, UID
  oder IP (anonym i. S. v. ErwGr. 26 DSGVO). Schema + Datenschutz-Regeln in
  `app/services/differences_stats.py`; geschrieben aus `chat.py::consensus`
  (fire-and-forget, Mock-Läufe schreiben nicht).
- `feedback`, `pro_waitlist`, `leaderboard`. Feedback speichert nur den
  validierten Inhalt und die UID; Abuse-Grenzen liegen separat in
  `persistence_usage`. Leaderboard-Zähler können nur über den transaktionalen,
  run-gebundenen Vote-Claim wachsen.

Die drei Scheduler lesen Fälligkeit index-first statt über Collection-Scans:
`watches(status,next_run_at)`, `topics(status,next_run_at)` und
`watch_briefs(enabled,next_send_at)`, jeweils sortiert und mit hartem `limit`;
der Outbox-Retry-Pass liest `notification_outbox(status,next_attempt_at)`.
Die benötigten Composite-Indizes stehen in `firestore.indexes.json`. Listen von
Watches lesen Shares gesammelt per `get_all`; die kompakte Dashboard-History
kommt aus `watches.history_points`. Kann die Detail-History nicht geladen
werden, meldet die API `history_status=unavailable` statt fälschlich eine leere
History zu behaupten.

Zusätzlich enthält die Indexdatei `model_votes(vote_type,model,created_at)` für
die Zeitraum-Rangliste. Vor dessen Bereitstellung bleibt der gecachte
Legacy-Scan aktiv; danach wechseln neue Cache-Refreshes automatisch auf
indexierte Count-Aggregationen. Grenzen, gemessene Read-Zahlen und Rollout:
[`docs/db-read-optimizations.md`](db-read-optimizations.md).

**Service-Account-JSONs** im Root (gitignored):
`consensai-firebase-adminsdk-*.json` für Firebase Admin sowie ausschließlich
der über `GSC_SERVICE_ACCOUNT_JSON` referenzierte Schlüssel für Search Console.
LLM-Aufrufe verwenden keinen Gemini-Service-Account und kein Google ADC; das
alte Gemini-ADC-JSON ist entfernt.

**Umgebungsvariablen** (`.env`, Beispiel in `.env.example`):
- Hintergrund-Writer lokal: `LOCAL_BACKGROUND_JOBS=1` startet auf einem
  Nicht-Produktionsserver die sonst nur in Produktion laufenden Scheduler,
  Cleanups und Startup-Backfills (§2 Lifespan); unter `MOCK_LLM=1` wirkungslos.
- Request-Schutz: `MAX_REQUEST_BODY_BYTES` (Default 16 MiB, erlaubter Bereich
  1 KiB bis 32 MiB) begrenzt den vollständigen HTTP-Body vor Framework-Parsing.
- Firebase Web-Config: `FIREBASE_API_KEY`, `FIREBASE_AUTH_DOMAIN`,
  `FIREBASE_PROJECT_ID`, `FIREBASE_STORAGE_BUCKET`, `FIREBASE_MESSAGING_SENDER_ID`,
  `FIREBASE_APP_ID` (ans Frontend durchgereicht via `/app`-Template).
  `FIREBASE_AUTH_DOMAIN` auf den App-Host (`www.consens.io`) gesetzt, läuft
  Google-Sign-in first-party über `firebase_auth_proxy.py` (Kontoauswahl nennt
  consens.io statt `consensai.firebaseapp.com`, Handys nutzen den Redirect).
  Voraussetzung: `https://www.consens.io/__/auth/handler` als autorisierte
  Redirect-URI im Google-OAuth-Client des Firebase-Projekts. Lokal bleibt
  `<projekt>.firebaseapp.com`. `FIREBASE_AUTH_PROXY_UPSTREAM` überschreibt das
  Proxy-Ziel (Default `https://<FIREBASE_PROJECT_ID>.firebaseapp.com`).
- Kanonischer öffentlicher Origin: `PUBLIC_SITE_URL` (Default
  `https://www.consens.io`). `app/core/site.py` akzeptiert ausschließlich einen
  absoluten HTTP(S)-Origin ohne Credentials, Pfad, Query oder Fragment; Router
  und Hintergrundservices importieren ihn ohne gegenseitige Abhängigkeit.
- Build-Kennung in der App-Fußzeile: `app/core/version.py` löst den laufenden
  Commit auf — zuerst aus den Host-Variablen (`RENDER_GIT_COMMIT`, `GIT_COMMIT`,
  `SOURCE_VERSION`, `COMMIT_SHA`, `VERCEL_GIT_COMMIT_SHA`), sonst durch Lesen von
  `.git/HEAD` (kein `git`-Subprozess). `/app` reicht ihn als `app_commit` plus
  `repo_url` ins Template; ist er leer, blendet das Template die Zeile aus. Die
  früher handgepflegte Versionsnummer (`v1.11.1`) ist damit ersetzt.
- Ausschließlich für Tests: `UNIT_TEST_MODE=1` initialisiert Firebase Admin im
  regulären pytest-Lauf ohne Service-Account gegen das nicht produktive
  `demo-consensio-unit` und einen geschlossenen Loopback-Port; ein ungemockter
  Zugriff kann daher keinen externen Dienst erreichen. `E2E_TEST_MODE=1`
  verlangt zusätzlich
  `FIRESTORE_EMULATOR_HOST` sowie die in `app/core/e2e_profile.py` fest
  allowgelisteten Demo-Projekt-ID. Das Profil ist in Produktion verboten und
  in der normalen `.env` deaktiviert.
- Der serverseitige LLM-Key ist ausschließlich `OPENROUTER_API_KEY`.
  App-Consensus, Consensus-API und Benchmark lösen ihn über
  `llm.credentials.resolve_developer_api_keys` mit identischer
  Leerwert-Behandlung auf. Es gibt keinen provider-spezifischen Developer-Key
  und keinen Gemini-ADC-Fallback im Benchmark.
- Consensus-Watch-/Topic-Follow-Mail und Abmeldung: `SMTP_HOST`, `SMTP_PORT`,
  `SMTP_USER`, `SMTP_PASSWORD`, `MAIL_FROM`, `WATCH_UNSUBSCRIBE_SECRET`.
  Topic-Tokens tragen einen eigenen Typ und abonnieren ausschließlich
  `topic_followers`, verwenden aber bewusst denselben serverseitigen HMAC-Key.
- Chat-Pagination: `CHAT_CURSOR_SECRET` signiert die opaken, an UID und
  Ressourcentyp gebundenen, selbstenthaltenden Cursor. Chat-Cursor enthalten
  Version, Typ, kanonisches/lossloses RFC3339-`updated_at` und Dokument-ID;
  Turn-Cursor enthalten Version, Typ, `position` und Dokument-ID. `start_after`
  verwendet diese signierten Originalwerte direkt und liest das Cursor-Dokument
  nicht erneut. Für bestehende Deployments dient
  `WATCH_UNSUBSCRIBE_SECRET` als Fallback; mindestens einer der beiden Werte muss
  gesetzt sein, sobald eine Chat- oder Turn-Liste eine Folgeseite ausgibt.
- Search Console (nur serverseitig): `GSC_SITE_URL` (URL-Prefix- oder
  `sc-domain:`-Property) und `GSC_SERVICE_ACCOUNT_JSON` (**ausschließlich ein
  Dateipfad**, trotz Variablennamen; `GSC_SERVICE_ACCOUNT_FILE` gilt als
  gleichwertiger Aliasname, weil Render diese Schreibweise trägt). Relative Pfade werden gegen den Repository-
  Root aufgelöst, absolute Pfade (z. B. Render Secret Files unter `/etc/secrets`)
  direkt verwendet. Verwendet ausschließlich
  `https://www.googleapis.com/auth/webmasters.readonly`; fehlende/ungültige
  Werte bleiben für normale App-Flows nicht-fatal und erscheinen sanitisiert im
  Admin-SEO-Tab. Diese Search-Console-Credentials sind unabhängig vom
  OpenRouter-LLM-Key.
- Optionaler SEO-Content-Judge: `SEO_CONTENT_JUDGE_MODEL`; ohne explizites
  Modell bleibt er aus. Bei Aktivierung nutzt er serverseitig
  `OPENROUTER_API_KEY`; der deterministische Judge benötigt beides nicht.
- Portfolio-Judge: `SEO_PORTFOLIO_JUDGE_MODEL` (Fallback auf
  `SEO_CONTENT_JUDGE_MODEL`, danach `gpt-5.6-terra`) plus
  `OPENROUTER_API_KEY`; ohne Server-Key bleibt der Weekly Review
  vollständig deterministisch.
- SEO-Review-Telegram: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` und optional
  `SEO_ADMIN_URL` (Default `https://www.consens.io/admin#seo`). Jeder terminale
  Review versucht genau eine nicht-fatale Nachricht; Ergebnis/Skip wird im Run
  gespeichert.
- Kritische App-/Serverfehler verwenden `TELEGRAM_BOT_TOKEN` und optional
  `CRITICAL_ERROR_TELEGRAM_CHAT_ID`; ohne eigene Ziel-ID fällt der Versand auf
  `TELEGRAM_CHAT_ID` zurück. Fehlende Konfiguration deaktiviert Alerts
  best-effort, ohne App-Flows zu beeinflussen. Die Umgebungszeile der Alerts
  (auch der Registrierungsmeldung) ist auf Render (`RENDER` oder
  `RENDER_SERVICE_NAME` gesetzt) `RENDER_SERVICE_NAME`/`ENVIRONMENT`/
  `production`, sonst `ENVIRONMENT` oder `local`; die Instanz kommt aus
  `RENDER_INSTANCE_ID` (Fallback Hostname). Die Unit-Suite entfernt
  `TELEGRAM_BOT_TOKEN` per Autouse-Fixture, damit eine lokale `.env` nie echte
  Nachrichten aus Fehlerpfad-Tests auslöst.
- Neue E-Mail/Passwort- und Google-Registrierungen verwenden denselben
  Telegram-Admin-Kanal. Eine prozesslokale, gehashte UID-Deduplizierung für 24
  Stunden verhindert Doppelmeldungen zwischen Create- und Confirm-Flow.
  Die Hintergrundnachricht enthält nur Registrierungsart, Umgebung und UTC-Zeit,
  weder E-Mail-Adresse noch UID; Telegram-Fehler beeinflussen die Registrierung
  nicht.
- User-Telegram-Watches verwenden denselben `TELEGRAM_BOT_TOKEN` plus
  `TELEGRAM_BOT_USERNAME` (ohne `@`) und `TELEGRAM_WEBHOOK_SECRET`. Sind alle
  drei gesetzt, registriert der Startup-Einmal-Task automatisch
  `${SITE_URL}/api/telegram/webhook` mit Telegrams Secret-Token-Header. Chat-IDs
  kommen ausschließlich aus dem verifizierten `/start`-Webhook, nie aus
  Nutzereingaben.
- Provider-Transport: `PROVIDER_CONNECT_TIMEOUT_SECONDS` (Default 10, Clamp
  1–30) und `PROVIDER_READ_TIMEOUT_SECONDS` (Default 120, Clamp 10–300).
  Automatische SDK-Retries bleiben fest deaktiviert; semantische Judge-Retries
  stehen explizit im Code.
- Retention: `RETENTION_MAINTENANCE_INTERVAL_SECONDS` (Default 3600, Clamp
  60–86400) steuert den vom Prozess-Restart unabhängigen Cleanup-Tick.

Provider-Registry (`cfg.PROVIDERS` in `app/core/config.py`): eine Modellfamilie
ist genau ein `ProviderConfig`-Eintrag (Familien-ID, Label, OpenRouter-Praefix,
Basis-Modell = Alias `<Label>`, Pro-Modell = Alias `<Label>-Pro`, erlaubte
Modelle, `required_models`). Daraus abgeleitet und deshalb NICHT einzeln zu
pflegen: `DEFAULT_MODEL_BY_PROVIDER`, `FREE_DEFAULT_MODEL_BY_PROVIDER`,
`PROVIDER_LABEL_BY_ID`, `OPENROUTER_MODEL_PREFIXES`, `CONSENSUS_ENGINE_ALIASES`,
`VALID_LEADERBOARD_MODELS`, `DEFAULT_CONSENSUS_MODELS`, die Judge-/Chat-Memory-
Basiswerte, `MODEL_ORDER_BY_PROVIDER`, der Firestore-Load samt Backfill sowie
`provider_transport.PROVIDER_ORDER/PROVIDER_LABELS`, `engines`, `topics`,
`opinion_map`, `share_snapshots`, `chat_store`, `watch_scheduler`, Admin und
Picker. Die `ALLOWED_*_MODELS`-Namen bleiben Aliasse auf DASSELBE Set-Objekt der
Registry (der Firestore-Load mutiert in place). Familienspezifische Hygiene
steht in `PROVIDER_MODEL_MIGRATIONS`/`PROVIDER_DEPRECATED_MODELS`, Reasoning-
Varianten als Daten in `MODEL_REQUEST_CONFIG`: Kimi K2.6 sendet
`reasoning.enabled=false`, K3 zwingend `reasoning.enabled=true` (auch mit Reasoning-Schalter;
explizite Modell-Policies gewinnen dort).
Beide Kimi-Modelle begrenzen OpenRouter auf `provider.only=["moonshotai"]`
mit `allow_fallbacks=false`; das bestehende `zdr=true` bleibt beim Merge erhalten.
Live-Diagnose: automatische Routen lieferten kaputte Tool-Ausgaben; K3 suchte
auf der Moonshot-Route erst mit aktiviertem Reasoning. Suche bleibt modellgesteuert
über `openrouter:web_search`, ohne gemeinsame Quellen oder neue Transport-Retries.
Die Modellkonfiguration gilt auch für Consensus-Aufrufe; Ausgabe-/Suchbudgets
bleiben unverändert. GLM 5.3 Flash/5.3 sendet `reasoning.effort=low`.
Feste Reasoning-Werte liegen ebenfalls zentral in `config.py`
(`REASONING_EFFORT_FOR_*`, `judge_reasoning_effort`);
`effective_model_reasoning` bildet daraus mit den Modell-Overrides exakt die
Prioritaet des Antwort-Request-Builders. Memory Edit, SEO-Review und Publisher
importieren diese Werte statt eigener Stringliterale.
Bewusst abweichende Reihenfolgen (`_CONSENSUS_ALIAS_ORDER`,
`watch_scheduler._WATCH_ENGINE_PREFERENCE`)
haengen unbekannte Familien hinten an, statt sie zu verlieren;
`tests/test_provider_registry.py` haelt das fest. Consensus- und
Differences-Prompt bekommen die Antworten als Mapping Familie->Text
(`_model_answer_items`, Schluessel duerfen Familien-ID oder Label sein) und sind
damit unabhaengig von der Anzahl der Familien; `/consensus` nimmt sie als Feld
`answers` entgegen und liest die alten `answer_<familie>`-Felder weiter.

Frontend: `/app` bekommt die Familien als `data-model-families` in
`#appBootstrapConfig` (Quelle `cfg.get_model_families()`); `app-bootstrap.js`
legt sie auf `window.MODEL_FAMILIES`, `app-core.js` macht daraus
`window.App.modelPrefs` -- die EINE Liste, aus der Antwortboxen (Jinja-Schleife
in `index.html`), Sendepfad (`query-send.js`), Projektion (`run-view.js`),
Fortschritt, Zitate, Bookmarks (`firebase.js`) und Anhang-Regel
(`attachments.js`) ihre Familien ziehen. Die DOM-IDs bleiben Vertrag und
werden aus `dom_key`/`short_label` gebildet (`anthropic` -> `claudeResponse`,
`selectClaude`), die Namen aus `title`/`short_label`/`citation_label`.
Eine neue Familie braucht damit nur einen Registry-Eintrag und ein Icon unter
`static/icons/chat_icons/`; `/ask_<dom_key>` wird aus der Registry registriert.

Ein Lauf vergleicht hoechstens `cfg.MAX_RUN_FAMILIES` (6) Modelle, auch wenn
mehr Familien konfiguriert sind: der Picker sperrt die naechste Familie
sichtbar (`model-picker.js`, `capBlocksInclusion`), `/consensus` weist mehr
Antworten mit 400 ab. Weniger als sechs bleibt wie bisher moeglich.
`attachment_models` legt die Fähigkeit pro Modell fest (`None` = alle, leeres
Set = keines). DeepSeek bleibt mit Anhang stumm; bei GLM kann 5.3 Flash Anhänge
lesen, GLM 5.3 ist text-only. Frontend und Backend prüfen deshalb das
tatsächlich gewählte Modell (der Reasoning-Schalter tauscht keins). Meta
liest beide Modelle Bilder (`PROVIDER_IMAGE_SUPPORT`), steht aber bewusst nicht
in `PROVIDER_PDF_SUPPORT`: nur Muse Spark 1.3 verarbeitet PDFs nativ, das freie
Muse Glimmer 30B nicht — die Familie bekommt deshalb den Text-Fallback.

**Betriebsvoraussetzung Meta:** `meta/muse-spark-1.3` ist bei OpenRouter
attestierungspflichtig und antwortet ohne die einmalige 18+-Bestätigung des
Kontos mit `403 … missing_attestation_types: [age_18plus]`
(https://openrouter.ai/settings/preferences). `meta/muse-glimmer-30b` läuft
ohne diese Bestätigung. Beide Modelle erfüllen `provider: {"zdr": true}`;
Muse denkt zwingend, deshalb steht `reasoning.effort` fest auf `low` und ein
zu kleines `max_tokens` liefert nur Reasoning-Tokens und ein leeres Final
(siehe `_responses_empty_result`). Der Contributor-Tarif
`meta/muse-spark-1.3-contributor` ist bewusst nicht aufgenommen: Meta darf
dort Prompts und Antworten für seine Produkte verwenden, was der ZDR-Zusage in
Terms/Privacy widerspricht.

Code-Fallback-Modell-IDs und Labels liegen in `app/core/config.py`
(`ALLOWED_*_MODELS`, `PREMIUM_MODELS`, `DEFAULT_MODEL_BY_PROVIDER`,
`FREE_DEFAULT_MODEL_BY_PROVIDER`, `MODEL_LABEL_OVERRIDES`). In Produktion sind
Providerlisten, Reihenfolge, Free-Defaults und Premium-Zuordnung aus
`app_config/models` autoritativ. Ebenfalls in `config.py`: die festen
Produkt-Metadaten `CONSENSUS_PRESET_DEFINITIONS` und Basiswerte ausschließlich
für ein fehlendes/noch nicht migriertes Dokument.
Firestore `preset_models` speichert pro Daily/Balanced/High Quality (ID:
`thorough`) unter `answers` genau sechs unterschiedliche Familienmodelle plus
`consensus`; das alte Top-Level-Provider-Schema wird beim Laden migriert.
Daily/Balanced bleiben Free-faehig und
High Quality bleibt unabhaengig von der Konfiguration Pro-only. Grok-Alt-Aliasse
(u. a. 4.1 Fast) werden beim Laden auf explizite interne Grok-4.3-Varianten
migriert: `grok-4.3-no-reasoning` sendet API-Modell `grok-4.3` mit
`reasoning.effort=none` und bleibt Free, während das Pro-Modell `grok-4.3`
  explizit `high` nutzt, sofern die Admin-Premium-Zuordnung es Pro-gated.
  Presets dürfen ausschließlich bereits konfigurierte Provider-Modelle
  referenzieren; sie fügen selbst keine Providerzeilen hinzu.
  `cfg.virtual_model_ids()` listet alle internen IDs, deren API-Modell
  abweicht. Jede Stelle, die eine konfigurierte Modell-ID in einen
  Provider-Request schreibt, muss vorher über `get_model_config(...).api_model`
  auflösen — die Judge-/Fallback-Pfade der Differences-, Resolve- und
  Consensus-Engine taten das früher nicht und quittierten
  `grok-4.3-no-reasoning` mit HTTP 400 „Model not found“. Das Admin-Dashboard
  blendet die Auflösung als `→ <api_model>` hinter dem Optionsnamen ein.
  Die Admin-Dropdowns blenden Premium-Modelle in Free-Kontexten (Free Watch,
  Daily/Balanced-Preset) nicht mehr aus, sondern zeigen sie deaktiviert mit dem
  Zusatz „— Pro only“, damit die Liste vollständig bleibt.

Die frühere Early-/Frontier-Low-Schicht ist vollständig entfernt. Es gibt nur
Free- und Pro-Zugriff; alte interne Low-Aliasse sowie nicht mehr im
OpenRouter-Katalog vorhandene Legacy-Modell-IDs stehen als Tombstones in
`REMOVED_MODEL_IDS` und werden beim Laden/Speichern aus bestehenden Admin-Daten
entfernt. Gemini
  3.5 Flash-Lite ist der Code-/Firestore-Free-Default, Gemini 3.6 Flash ist eine
  direkte Modell-ID. Gemini-Payloads senden modellgenerationsunabhängig keine
  optionale `temperature`, damit neue Admin-IDs nicht an geänderten
  Sampling-Schemas scheitern. Bekannte tote Preview-IDs bleiben Tombstones.

Admin-Modellkonfig (`/admin`, `app_config/models` in Firestore): Provider-Listen sind
geordnet (Picker-Reihenfolge via `MODEL_ORDER_BY_PROVIDER`/`get_ordered_models`, im Admin
per ↑/↓ sortierbar); Feld `defaults` setzt den Free-Default je Provider (`apply_default_models`,
nur Nicht-Premium erlaubt, sonst `_BASE_FREE_DEFAULTS`). Feld `watch_models`
enthält getrennte `free`-/`pro`-Mappings Provider→Modell; je Tier sind mindestens zwei
Provider nötig, Free wird serverseitig auf Nicht-Premium begrenzt. Die Zeile
„Actually runs“ unter dem Raster nennt pro Tier die Provider, die der nächste
Lauf wirklich verwendet, und benennt jeden konfigurierten Provider, der
wegfällt, mit Grund (Pro-only im Free-Tier, kein Server-Key) — sichtbar an der
Stelle, an der man die Auswahl trifft. Grundlage ist `meta.provider_credentials`
(reine Booleans je Provider); ein leeres Objekt heißt „keine Aussage“ und zeigt
bewusst gar nichts an. Das getrennte Feld
`watch_consensus_models` wählt pro Tier genau eine Synthese-Engine (Alias oder direkte
konfigurierte Modell-ID); Free darf auch hier keine Pro-/Premium-Engine verwenden.
  `normalize_models_document` erhält die Reihenfolge (kein `sorted` mehr), entfernt
  verwaiste Premium-IDs und validiert `defaults`, `preset_models`, `watch_models`,
  `watch_consensus_models`,
  Judges. Provider-
Modelllisten werden bewusst nicht live gegen Provider-APIs validiert; diese
Pflege bleibt eine explizite Admin-Aufgabe.
Das Admin-UI (Tabs: Models / Consensus / Configuration / Limits / Accounts / API /
Shared Pages / Consensus Watch / Topics / SEO) besitzt unter `/admin#configuration`
einen unabhängigen Save-/Reload-Bereich für Systemprompts und Referenzzeitzone.
Die anderen Konfigurations-Tabs bekommen via
  `GET /api/admin/models` ein `_meta`-Objekt (Alias-Auflösung, Labels und
  referenzierende Defaults/Presets/Watches/Judges). `app_config/models.reasoning_policy`
  speichert das zentrale Sparprofil (`existing`/`economy`) und Modell-Ausnahmen.
  GET/POST liefern/speichern es über den bestehenden Save-/Reload-/Rollback-Flow;
  fehlende Felder alter Clients erhalten die aktive Policy. Ohne DB-Feld bleibt
  das bisherige Verhalten erhalten. Der Models-Tab zeigt eine Vorschau je
  Einsatzbereich mit bearbeitbaren Modell-Ausnahmen; geschützte Modelle sind
  zuschaltbar. `cap_model_reasoning` begrenzt verifizierte Modelle auf `low`,
  Mistral auf das unterstützte `none`; Pflicht-Reasoning, unbekannte Modelle und
  bereits reduzierte Einstellungen bleiben erhalten. `effective_model_reasoning`
  (Antworten inklusive Reasoning-Schalter, `reasoning=True` → `REASONING_EFFORT_ON`;
  Admin-Vorschau „Answers with Reasoning on") und `effective_engine_reasoning`
  (synchrone/streamende Consensus-, Judge-, Resolve- und Memory-Aufrufe) verwenden
  dieselbe Policy. Feste Extraktions-/SEO-/Publisher-Tasks behalten ihre Werte.
  Details und Quellen: `docs/reasoning-policy.md`.
  `_meta.reasoning` projiziert dieselbe Runtime-Policy ohne Aktivierung: Die
  eingeklappten technischen Details zeigen weiterhin
  die effektiven Einstellungen je Laufart sowie aufgeklappt je Modell, Deep-
  Think-Modell, Standard-/Pro-Judge und Chat-Memory-Modell einschließlich
  Policy-Name und aufgelöstem API-Modell (Judges und Chat-Memory teilen sich
  denselben `_call_engine_text`-Effort-Cap, deshalb dieselbe Auflösung);
  Modelle mit explizitem Override tragen zusätzlich
  direkt in ihrer Zeile ein Reasoning-Badge. „Provider default“ bedeutet, dass
  consens.io kein `reasoning`-Feld mitsendet. Das „In use“-Badge ist
  informativ und sperrt keine Providerzeile; nichts wird nach einem Save heimlich
  als „Required“ wieder eingefügt. Der
„API“-Tab gibt Schlüssel für eine bestehende Firebase-UID aus, zeigt den
Klartextschlüssel genau einmal zum Kopieren und listet/widerruft danach nur
Hash-ID, Präfix, Label, UID, Status und Audit-Zeitstempel. Zusätzlich listet er
die vom Scheduled Publisher erzeugten Weekly-Watch-Seiten (`model_tier=free`)
mit Link, Lauf-/Indexstatus und sofortiger Admin-Löschaktion. Der separate
„Consensus Watch“-Tab zeigt die Free-/Pro-Watch-Modellmatrix, operative Watch-Metadaten,
SMTP-Konfigurationsstatus und admin-only Aktionen für eine echte Testmail sowie den sofortigen Start einer aktiven Watch;
der eigentliche Lauf bleibt im normalen Lease-/Budget-/Scheduler-Pfad. E2E-Zugriff auf
Admin-Endpunkte: `MOCK_ADMIN=1` (wirkt nur zusammen mit `MOCK_AUTH=1`).
Der Topics-Tab unter `/admin#topics` lädt/speichert ausschließlich die Topics-
API; Pause/Archive und Snapshot-Publishing berühren die bestehenden Shared-
Pages-/Watch-Tabs nicht. `/admin/topics` redirectet auf diesen Tab.

---

## 7. Tests, Smoke-Checks & lokale Befehle

**Inventar/Laufstand 02.10.2026:** 254 Dateien, 3.068 statische Definitionen,
4.053 Runnerfälle. Python: 3.078 bestanden/3 fehlgeschlagen; JavaScript:
664 bestanden; E2E: 219 bestanden/30 fehlgeschlagen/4 Setupfehler/55 nicht
ausgeführt. Buildcheck bestanden. Vollständiger [Testkatalog](test-coverage-map.md),
[Befunde](test-coverage/findings.md) und [Produktmatrix](test-coverage/product/README.md).
Neue Bereiche umfassen Google/Kalender/Gmail, private Dateien/Dokumentversionen,
gemeinsames Tokenkonto, Antwortreceipts und Watch-Evidenz/Outbox. Historische
Coveragewerte von 26.09.2026 sind keine Messung des aktuellen Codes.

- **Windows-Einstieg:** `dev.ps1 check frontend|backend|browser` koordiniert
  die vorhandenen npm-/Pytest-Befehle; `-TestPath` begrenzt den Lauf auf eine
  Datei oder ein Verzeichnis der gewählten Suite. Frontend prüft zusätzlich
  den Build-Stand. Browser nutzt Firebase `emulators:exec` für Start und Stopp,
  liest Host/Port aus `firebase.json` und den Demo-Projekt-/Loopback-Vertrag
  aus `app/core/e2e_profile.py`. Die aufrufende Shell erhält ihre Umgebung und
  ihr Arbeitsverzeichnis auch bei Fehlern zurück. Regressionstests des Einstiegs:
  `tests/test_dev_cli.py`; Setup und Pflege: `docs/testing.md`.
- **Reguläre Tests** (`tests/`, pytest; Browser-Suite standardmäßig
  ausgeschlossen). Abhängigkeiten kommen aus `requirements-test.txt`, Lauf:
  ```powershell
  .\venv\Scripts\python.exe -m pytest tests -q
  ```
  Reine String-/Quelltextverträge sind mit `source_contract` gekennzeichnet und
  laufen weiterhin mit; sie gelten ausdrücklich nicht als Verhaltensabdeckung.
  Aktuelle Ergebnisse und Fehler stehen im oben verlinkten Laufbericht.
- **JS-Verhaltenstests** (`tests/js/`, Vitest + jsdom):
  ```powershell
  npm test
  ```
  `tests/js/helpers/appWindow.mjs` lädt die Klassik-Skripte als `<script>` in ein
  frisches jsdom — sie sind keine ES-Module und lassen sich nicht importieren.
  Deckt unter anderem `app-state.js`, `composer-quote.js`,
  `consensus-anchor.js`, `run-registry.js`, `run-view.js`, getrennte
  ChatSessions und quelllistenreines Evidence-Mapping ab. Die Multi-Run-Tests
  prüfen Admission (max. 2), eingefrorene Config, Sichtwechsel, gezielten
  Cancel, Logout-Cleanup, Conversation-Locks und späte Hintergrund-Callbacks.
  Hierhin gehören schrittweise die Teilstring-Prüfungen aus `test_*_ui.py`.
- **Frontend-Build** (`npm run build`, esbuild): siehe
  `docs/frontend-build.md`. `npm run build:check` meldet ein veraltetes
  `static/dist/`; dasselbe prüft `tests/test_frontend_build.py` ohne Node.
- **Playwright-Smoke-Suite** (`tests/e2e/`, Python-Playwright):
  automatisiert die risikoreichsten Punkte der `docs/smoke-checklist.md`
  (Laden ohne Konsolen-Fehler, Send→Streaming, kompakte Antwort→Consensus-
  Pipeline inkl. Mobile-Clipping/Ergebnis-Reihenfolge,
  Consensus→Differences+Score inkl. Inline-Marken (`.cx-claim.is-major` als
  eigenes Steuerelement mit aria-label, keine `.cx-marker`-Punkte mehr),
  zugeklapptem `#consensusDifferencesPanel` und markenfreiem Copy-Text, Watch-Dialog mit Pflicht-Sichtbarkeit/Condition-
  Feld, Exclude, Theme, Picker-Persistenz). Ein deterministischer Race-Test hält
  zwei komplette Ask-/Consensus-Fan-outs gleichzeitig an, löst sie in
  umgekehrter Reihenfolge, wechselt die sichtbare Run-Zeile, cancelt gezielt
  nur einen Lauf und verifiziert getrennte Consensus-/Bookmark-Payloads sowie
  Restore nach einer Metadaten-Aktualisierung. Startet einen eigenen uvicorn auf
  Port 8031 mit `E2E_TEST_MODE=1`, `MOCK_LLM=1` (deterministische Fixtures in
  `app/services/llm/mock_llm.py`, Seams: `_run_ask`,
  `_call_engine_text`/`_stream_engine_text`),
  `MOCK_AUTH=1` (Sentinel-Token statt Firebase, Browser-Stub ersetzt
  `firebase.js` per Playwright-Route), lokale Dummy-Eigenkeys (kein Einfluss
  des live geladenen Free-Limits; `MOCK_LLM` verhindert echte Calls) und
  `DISABLE_RATE_LIMIT=1`. Firestore ist technisch auf den lokalen Emulator und
  `demo-consensio-e2e` begrenzt; der E2E-Lifespan startet keine produktionsnahen
  Jobs. Lauf mit bereits gestartetem Emulator:
  ```powershell
  $env:RUN_E2E = "1"
  $env:FIRESTORE_EMULATOR_HOST = "127.0.0.1:8085"
  .\venv\Scripts\python.exe -m pytest tests\e2e -v
  ```
  Ohne `RUN_E2E=1` wird `tests/e2e` nicht eingesammelt (Baseline bleibt).
  Ein Service-Account ist weder nötig noch zulässig; Java/Firebase CLI starten
  den Emulator, Netzzugang lädt CDN-Assets. Verifizierte Baseline am
  2026-08-09: **39 passed, 1 warning**. Der writerfreie Phase-4-Browserlauf
  wurde nach Phase 6 erneut mit **8 passed, 1 warning** verifiziert. Details in
  `tests/e2e/README.md`.
- **Persistierte Browserreisen**: `test_persisted_journeys.py` ergaenzt sechs echte AppFirebase-/HTTP-/Firestore-
  Reisen auf einem separaten Server (Port 8044, optional `E2E_JOURNEY_PORT`).
  Der normale E2E-Lifespan bleibt aktiv; nur externe Identity-/Provider-/Mail-
  Grenzen werden ersetzt. Der ausschliesslich vom Test gestartete
  `journey_server.py` steuert Provider-Gates, native historische Jobfixtures,
  echte Quellenworker-Ticks mit Own-Key-Affinitaet, gezielte Watchausfuehrung
  und Cleanup zufaelliger Testowner. Der Quellenworker braucht eine ansonsten
  inaktive Queue; eine Vorpruefung verhindert die Verarbeitung fremder Testjobs.
  Passive Beobachtung der echten Agent-Response und Capacity-Lease macht
  Loeschassertionen vom tatsaechlichen Producer-/Cleanupabschluss abhaengig.
  App-Routen
  werden nie abgefangen. Grenzen und Befehle stehen in `tests/e2e/README.md`.
- **Regression-CI**: `.github/workflows/tests.yml` trennt Python, JS/Build,
  Emulator/Chromium/Clientregeln und Windows-Einstiege. Normale Push-/PR-Läufe
  prüfen nur Python und JS/Build; reine Änderungen unter `docs/` oder an
  Markdown im Repository-Stamm lösen sie nicht aus. Der Wechsel von Entwurf zu
  reviewbereit führt alle vier Gruppen aus; manuell sind `quick`, einzelne
  Gruppen oder `full` wählbar, sobald der Workflow auf dem Default-Branch liegt.
  Spätere Pushes wiederholen nur die schnellen Prüfungen. Node 24, Java 21 und
  Demo-Projekt sind festgelegt; kein Produktcredential nötig.
  `publisher-tests.yml` und die Vorprüfung in `publish-consensus.yml` bleiben.
  `dev.ps1 check rules` kapselt den separaten Client-Regelrunner mit demselben
  Emulator-Lebenszyklus wie `browser`; `npm run test:rules` nutzt einen bereits
  laufenden lokalen Emulator. Tests/Details: `docs/testing.md`.
- **Frontend darüber hinaus manuell.** Nach JS-Änderungen
  an nicht abgedeckten Flows (Resolve, Share, Attachments, Follow-up,
  Bookmarks, Agent Mode, Demo, Mobile) die manuelle
  **`docs/smoke-checklist.md`** durchgehen.
- **Benchmark-Runner** (`benchmark/`, kein GUI-Pfad): `python -m benchmark
  --smoke|--pilot|--final`; fertige lokale Runs werden mit
  `python -m benchmark --publish-run <run_id>` oder `--publish-all` als kompakte
  Admin-Dashboard-Snapshots nach Firestore publiziert. `--smoke` ist ein
  dedizierter 1-Frage-MMLU-Pro-Pfad
  mit eigenem Manifest/Run-Kontext; Smoke und Pilot haben separate Live-Gates,
  der finale Run bleibt durch `LIVE_EXECUTION_ENABLED` hart gegatet. Die MC-
  Auswertung akzeptiert nur die letzte `FINAL_ANSWER: X`-Zeile. Alle sechs
  Modellfamilien und die Synthese laufen über denselben OpenRouter-Chat-
  Completions-Transport mit `OPENROUTER_API_KEY`; Benchmark-Payloads bleiben
  im `benchmark_mode` ohne Websuche. `--budget` deckt alle bezahlten Versuche
  ab: Hauptlauf, Fehlversuche und E4-Audits (`AuditLedger`, Journal
  `audit_calls.jsonl`, Prüfung vor jedem Audit-Call, Resume ohne erneute
  Audit-Kosten); fehlende Usage wird mit der Vorab-Obergrenze verbucht.
  HTTP-200-Fehlerobjekte und ungültige Chat-Completions-Bodies sind strukturierte
  Fehler, keine Enthaltung; gültiger Text ohne Auswahl bleibt Enthaltung.
  Transport-/Synthesefehler speichern keine privaten Exception-/Providertexte.
  Manifestvergleich ersetzt nur flüchtiges Datum/Uhrzeit/UTC-Offset durch
  Platzhalter, auch beim Lesen älterer Manifeste; Zeitzone, Instruktionen und
  Modellparameter bleiben eingefroren. `run_sample` und `run_experiment` sind
  unterstützte Einstiegspunkte: Dry-run/Live schließen sich aus, Live verlangt
  ein positives endliches Budget, Sample-Run-IDs bleiben ein einzelner
  Verzeichnisname. Die Validierung erfolgt vor Dataset- oder Providerarbeit.
- **Claim-Key-Backfill** (`scripts/backfill_claim_keys.py`): Normalbetrieb ergänzt
  nur fehlende Keys; vorhandene Teilzuordnungen bleiben erhalten und werden
  vor Judge-/Fallbackzuordnungen reserviert. Neue Zuordnungen kollidieren weder
  mit erhaltenen Keys noch untereinander. `--force`
  erlaubt ausdrücklich erneute Zuordnung. Dry-run zählt geplante Änderungen
  korrekt und schreibt nichts, kann aber weiterhin den Identity-Judge aufrufen.
- JS-Syntaxcheck einzelner Module:
  ```powershell
  node --check static\js\<modul>.js
  ```
- App lokal starten (Render nutzt eigenes Start-Kommando ohne `--proxy-headers`):
  ```powershell
  .\venv\Scripts\python.exe -m uvicorn main:app --reload
  ```

**Cleanup-Jobs**: `retention_maintenance_loop` führt
`cleanup_expired_pending` und `cleanup_revoked_shares` (plus Source-Checks,
Agent-Dateien/-Dokumente, Google-Daten, fällige `chat_deletion_jobs` über
`resume_chat_deletions` sowie `cleanup_memory_edit_records` für 30-Tage-Undo-
Snapshots und abgelaufene Memory-Edit-Leases) direkt nach Task-Start
und danach standardmäßig stündlich aus; der tägliche Render-Restart ist keine
Voraussetzung mehr. Revoked-Shares werden bereits per `revoked_at < cutoff`
gefiltert, deterministisch sortiert und vollständig in begrenzten Seiten
abgearbeitet. Consensus-API-Retention/Lease-/Queue-Recovery laufen alle 60
Sekunden; fehlgeschlagene API- und Vollkonto-Löschkaskaden alle fünf Minuten.
Alle Loops werden beaufsichtigt und melden nach jedem erfolgreichen Tick Health.
Die Retention-Schritte laufen unabhängig weiter, wenn einer scheitert; ein Tick
mit gescheitertem Schritt setzt den Task über `task_partially_failed` auf
`degraded` (`/health/maintenance` meldet dann `degraded`, `last_success_at` bleibt
der letzte vollständige Tick). Beim dritten Fehl-Tick in Folge geht genau ein
Telegram-Alert (`background_task_repeated_failure`, mit Frames, ohne
Exception-Text) raus; ein sauberer Tick setzt Zähler und Episode zurück.
Unter `MOCK_LLM=1` startet die Retention-Maintenance nicht (siehe Lifespan-Abschnitt).

**Weekly SEO Review** läuft in einem eigenen Lifespan-Task mit 15-minütigem
Fälligkeitscheck; `next_run_at` wird aus Intervall, lokaler Uhrzeit und Zeitzone
DST-fest berechnet. Das persistente Config-/Lease-Dokument ist unabhängig vom
30-Minuten-Watch-Worker; ein Review führt keine Empfehlung automatisch aus.
Auch der Lease-Abschluss prüft `lease_run_id` und schreibt den nächsten Termin
in einer Firestore-Transaktion. Ein alter Worker oder wiederholter Abschluss
kann einen neu vergebenen Lease und dessen Zeitplan nicht überschreiben.
Jeder terminale Lauf (auch Collection-Fehler) versucht anschließend eine
Telegram-Nachricht mit Ergebnis, offenen redaktionellen Entscheidungen,
Topic-Brief-Entscheidungsbedarf und Admin-Link; Versandfehler bleiben nicht-fatal.
Die synchrone Pipeline läuft außerhalb des asyncio-Event-Loops. Manueller
Collector und Weekly Review teilen zusätzlich eine prozessweite Nonblocking-
Sperre, damit ihre GSC-/Firestore-Arbeit nicht parallel denselben Webprozess
belastet. Latest-Run, Latest-Review und Latest-Query-Snapshot werden in
Firestore jeweils per sortiertem `limit(1)` statt durch vollständige
Historien-Scans gelesen.

**Consensus Watch** läuft als eigener asyncio-Lifespan-Task alle 30 Minuten.
Firestore-Transaktionen claimen einen globalen Worker-Lease, den einzelnen
Watch-Lease und das globale Tagesbudget; innerhalb eines Workers laufen Watches
strikt sequenziell. Der globale Lease trägt ein Owner-Token: der Tick erneuert
ihn per Heartbeat, bricht bei Verlust vor dem nächsten Watch ab und gibt ihn nur
frei, solange er noch Eigentümer ist; ein abgelaufener alter Worker kann den
Lease eines Nachfolgers damit weder freigeben noch verlängern (R30). Jeder Einzel-Claim verwendet den dann aktuellen Zeitpunkt
(nicht den Tick-Start), erneuert seine 15-Minuten-Lease während langer Läufe
alle fünf Minuten und fenced Completion wie Fehlerabschluss über
`current_run_id`. History, Watch-Pointer und Share-Pointer committen gemeinsam.
Claim, Completion und Fehlerabschluss prüfen außerdem den Account-Tombstone
in ihrer Schreibtransaktion; bereits authentifizierte Worker bleiben nach
Beginn einer Kontolöschung für neue Persistenzwrites gesperrt.
Ein alter Worker kann einen neueren Claim weder leeren noch pausieren. Jede
Änderung über `update_watch`/Admin-Status/Unsubscribe erhöht
`config_generation`; ein echter Statuswechsel (Pause, Resume) entzieht
zusätzlich den laufenden Claim (`current_run_id=None`). Ein alter Lauf kann einen
pausierten Watch daher weder reaktivieren noch den Aktivzähler verfälschen, und
Resume startet keinen zweiten Worker für denselben Claim. Zeitplanänderungen
während eines Laufs bleiben erhalten: Abschluss und Fehler übernehmen dann das
bereits neu berechnete `next_run_at`; Alert-Regel, Kanäle und Condition werden
beim Commit aus dem aktuellen Dokument gelesen, eine während des Laufs geänderte
Condition wird weder alarmiert noch als Status gespeichert (R16). Die Reruns ermitteln den aktuellen Pro-Status des Eigentümers und
nutzen das entsprechende `WATCH_MODELS_BY_TIER`-Mapping aus Firestore `watch_models`;
je konfiguriertem Provider läuft genau ein Modell (mindestens zwei), deren Antwort-Calls
laufen innerhalb des einzelnen Watch-Runs parallel. Ein fehlender Server-Key ist
der einzige Grund, aus dem ein konfigurierter Provider aus einem Lauf fällt; es
gibt keinen zweiten, unsichtbaren Filter über der Admin-Konfiguration. Die Synthese sowie die nachgelagerte
Differences-/Change-Analyse verwenden die tierabhängige Engine aus
`watch_consensus_models`. Ist deren Provider mangels Key nicht verfügbar,
fällt der Scheduler deterministisch auf den ersten erfolgreichen
Watch-Antwortprovider in `PROVIDER_ORDER` zurück. Keine Attachments/Follow-ups und keine
In-Memory-Usage-Zähler. Jeder erfolgreiche Lauf schreibt unter
`shares/{share_id}/watch_history/{run_id}` genau eine unveränderliche Version:
kompakte Drift-/Score-Felder plus aktuellen Consensus, Differences, Quellen- und
Modellmetadaten. Das Share-Dokument bleibt der unveränderliche Original-Baseline-
Snapshot und erhält nur `latest_watch_run_id`/`last_watch_run_at`; nach drei
Fehlern pausiert die Watch. **Belegmodell (seit 2026-10-01, Vertrag:
`docs/watch-evidence-model.md`):** jeder Check vergleicht mit der *geltenden*
Antwort (`watch.accepted_run_id`, Altbestand: letzter Lauf) statt mit dem
letzten Lauf, und zwar über `evidence_change.assess`: der Change-Judge
(`query_consensus_change`, Structured Output) bekommt beide Antworten **und**
beide Quellenlisten (neue mit `seen_before`) und nennt `cause`
(`new_evidence` / `evidence_missing` / `reassessment`), tragende Quellen,
`change_summary` und `held_summary`; der Server prüft die zitierten IDs, stuft
`new_evidence` ohne neue URL zu `reassessment` und eine Neubewertung nach
Modellwechsel zu `model_change` um. Ein zweiter Vergleich Original → Current
liefert weiter den kumulativen Baseline-Drift. Alte kompakte History bleibt
lesbar. Event-Typen für spätere Webhooks: `watch.checked`, `watch.changed`,
`watch.confirming`, `watch.condition_met` (= Abschluss) und `watch.run_failed`.
Was ein Check bedeutet, entscheidet ausschließlich
`app/services/drift_signal.py` (`annotate_points` für Watch-Punkte,
`annotate_runs` für Topic-Runs) — eine Regel für Badge, Kurve, Dashboard,
Morning Brief, Mail, Telegram, Follower und Topic-Record. Signale: `moved`
(major + neue Belege, oder eine Neubewertung, die der direkt folgende Check
wiederholt), `confirming` → `preliminary`/`reverted`, `held` (major +
`evidence_missing`: die geltende Antwort bleibt), `restated`, `stable`;
`trigger == "changed"` ⇔ `moved`. Der Agreement-Score löst kein Ereignis mehr
aus (nur noch `score_event` als Kurvenmarke). History ohne `cause` behält die
alte Regel (major oder Score-Band) und wird beim Lesen neu bewertet, kein
Backfill. Ein `confirming`-Check zieht den nächsten Lauf um
`drift_signal.CONFIRMATION_DELAY` (20 min) vor; höchstens eine Nachprüfung pro
Ereignis.
**Ziel und Abschluss:** die Alert-Regel bleibt im Legacy-Feld `email_mode`,
das Ziel im Feld `condition` (UI: „What are you waiting for?“). Das Ziel wird bei
jedem Check bewertet (`condition_status`, `condition_reason`, zitierte
`condition_evidence`). Belegt ein Check `met` mit einer Quelle dieses Laufs —
oder wiederholt er ein `met` für dasselbe Ziel —, setzt `complete_watch_run`
`status = "resolved"`, `resolution = {run_id, at, condition, reason, sources}`,
`next_run_at = None` und gibt den Aktiv-Slot frei; ein erstes unbelegtes `met`
löst eine Nachprüfung aus. Weiterbeobachten (`PATCH status=active`) verlangt ein
neues oder leeres Ziel (`goal_reached`, 409). `changes_only` meldet `moved` oder
den Abschluss, `condition` nur den Abschluss, `every_run` jeden Check. Ein Ziel,
das während des Laufs geändert wurde, wird weder bewertet noch gespeichert (R16).
**Tages-Scan (`watch_probe.py`):** aktive Owner-Watches mit Intervall weekly/
monthly tragen `next_probe_at` (Index `status`+`next_probe_at`). Im Watch-Tick
claimt `run_probe` at-most-once (Termin rückt vor, Tagesdeckel
`watch_probe_max_per_day` aus den Admin-Limits, 0 = aus) und fragt ein
günstiges Free-Watch-Modell mit Websuche (`NEW: yes|no`) nach Neuem seit dem
letzten Check. Nur ein „yes“ mit einer Quelle, die die geltende Antwort nicht
zitiert, zieht `next_run_at` auf jetzt und weckt den Scheduler; das Ergebnis
steht als `last_probe` am Watch. Ist der volle Check < 30 h entfernt, entfällt
der Scan.
Ein einmalig konsumierter `probe_claim_token` bindet das Ergebnis an seinen Claim. Vor dem Schreiben
werden Token, `config_generation`, Ziel, Zeitplan, Modellstufe und letzte erfolgreiche Vollprüfung
mit dem Claim-Snapshot verglichen. Veraltete Antworten verändern weder
`last_probe` noch `next_run_at`; Account-Tombstones sperren auch diesen Write.
E-Mail und Telegram sind getrennte, pro Watch aktivierbare Kanäle; mindestens
einer muss aktiv bleiben. Legacy-Watches bleiben E-Mail-only. Telegram nutzt
denselben fertigen Run ohne zusätzlichen LLM-Call, dedupliziert über
Watch/Run/Alert-Art und bietet `Open`, `Mute 24h` sowie zweistufiges `Pause`.
Ein 403 vom Bot deaktiviert die Verbindung. Bei der Erstellung ist
`visibility=private|public` Pflicht im UI:
fehlende Pflichtwerte werden direkt am jeweiligen Feld angezeigt; der mobile
Create-Dialog bleibt innerhalb des dynamischen Viewports und scrollt intern.
private Seiten erfordern die kurzlebige Eigentümer-Session, sind `noindex,nofollow`,
`private,no-store` und erscheinen weder in Sitemap/Related noch im Report-Flow.
Neu angelegte Watches bekommen eine lokale Ausführungszeit; das Backend berechnet
`next_run_at` zeitzonen- und DST-fest und behält die lokale Uhrzeit bei Folge-Runs,
Fehler-Retries und Resume bei. Weekly-Watches können einen lokalen Wochentag wählen;
Legacy-Watches ohne Wochentag bzw. Zeitfelder nutzen weiter die bisherige reine
Intervalladdition.
Alle Benachrichtigungen (Change, Every-run, Resolved, Follower, Topic, Telegram)
sind ein **Änderungsprotokoll** in fester Reihenfolge: **was sich geändert hat**
(erster Satz hervorgehoben) → **warum** (Ursachensatz + tragende Quellen) →
**was gleich blieb** (`held_summary`) → **Ziel** und sein Stand → **Frage** →
Button. Es gibt bewusst keine Agreement-Zeile mehr. Die Outbox trägt dafür
`payload.delta` (`notification_outbox.delta_view`: summary, held, cause,
sources, goal, goal_status, goal_reason); Items ohne `delta` (vor 2026-10-01
eingereiht, durch `deliver_until` begrenzt) rendern nur den Summary. Bausteine
liegen zentral in `mailer.py` (`_delta_parts`, `_change_block_html`,
`_why_html`, `_question_html`, `_shell_html` inkl. Preheader für die
Inbox-Vorschau); eine abgeschlossene Watch schickt genau eine „Resolved“-Mail
(sie passiert das Pause-Gate der Zustellung als einzige); lange Fragen werden auf ~200 Zeichen gekürzt und verlinken auf
die Seite. Der Textteil bleibt bewusst ASCII (`_ascii`), sonst landet die
komplette Plaintext-Hälfte in Base64 und URLs sind nicht mehr klickbar.
Telegram sendet dieselbe Struktur als HTML (`parse_mode=HTML`), Frage und langer
Consensus stehen in `<blockquote expandable>`; wird die Auszeichnung abgelehnt
(HTTP 400), geht dieselbe Nachricht als Klartext raus.
Watch-Seiten erklären nur vor dem ersten Vergleich die Baseline; bei vorhandener
History beginnt der Inhalt direkt mit Status und Zeitplan. Lange Fragen klappen im Seitenkopf auf drei Zeilen
ein (`#shareQuestion` + `#shareQuestionMore`, gleiche Geste wie `#threadAsk` in
/app; ohne JS bleibt der volle Text stehen), in der Dashboard-Karte auf drei. Zeitplan und Check-Daten stehen im Kopf stets
sichtbar; nur Direction-/Agreement-Metriken liegen in einklappbaren
Expertendetails. Vor der ersten echten Vergleichsstufe
werden keine Entwicklungsmetriken suggeriert. Bei vorhandener History integriert
der Drift-Header einen kompakten Agreement-Chart: seine Punkte besitzen Hover-
Beschreibungen und springen in die stets sichtbare Run-Liste. Die große Kurve
bleibt als dezentes, zunächst geschlossenes Detail aus dem Header verlinkt. Die normale Watch-URL
rendert serverseitig die **geltende** Vollversion (`accepted_run_id`, sonst die
neueste) über dem unveränderten Share-Baseline-Dokument; steht der neueste Check
nicht (`held`/`confirming`), nennt die Seite ihn als „Latest check: …“ über der
geltenden Antwort. Ein Ziel bzw. ein Abschluss steht als `.watch-goal-banner`
im Kopf (öffentliche Seiten zeigen das Ziel), die Quellen hinter einer Bewegung
als `.watch-evidence-list`; `?version=<run_id>` öffnet eine unveränderliche (aber nur kurz gecachte, widerrufbare) historische Vollversion und
`?version=original` den Ausgangs-Consensus. Shared Pages ohne Watch behalten ihr
bisheriges Snapshot-Verhalten. Ein Backend-`display_version` ist die einzige
Quelle für Consensus, Differences, Agreement, Modelle, Quellen, Answer-Zeit und
Citation; kompakte History-Metadaten werden nie in den Share-Snapshot gemischt.
Fehlt die aktuelle Vollversion (auch bei Legacy-History), zeigt die Seite einen
klaren Hinweis und rendert den Original-Snapshot vollständig konsistent. Der
Drift-Header stellt Stable/Changed sowie den Change-Summary vor den Text; seine
Expertendetails trennen Direction Shift und Agreement Change. Die Engine-
Provenienz und der Vergleichshinweis stehen als Methodennotiz am Seitenende.
Direkt unter den Quellen rendert die öffentliche Watch-History eine stets offene,
menschenlesbare **Position Map**: statt einer universellen Ja/Nein-Achse zeigt
sie pro frage-spezifischer Dimension klar benannte Positionskarten samt
Modell-Chips. Provider-Bewegungen über die Läufe bleiben als nachrangiges Detail
verfügbar; der Kopf zeigt den gemeinsamen
**Direction Shift**. Die Berechnung ist deterministisch aus dem ohnehin
vorhandenen Differences-JSON plus dem Change-Judge-Ergebnis und verursacht
keinen zusätzlichen LLM-Call. `opinion_map.stance_changed` wertet geänderte
Zahlen (mit Vorzeichen/Einheit/Währung), Negationen, Bedingungen und Monate
immer als Bewegung; nur ohne solche Marker entscheidet die Wortüberlappung.
Modellbewegung ist vom Change-Judge entkoppelt: `consensus_changed=False`
schaltet lediglich den lexikalischen Fallback ab (Paraphrase), ein
Einzelmodell-Wechsel bleibt sichtbar. Ohne vergleichbare Position gilt
`movement_score=None` bzw. `shift_score=None` („Not comparable“), nie 0/Stable.
**Morning Brief**: opt-in tägliche Digest-Mail pro Nutzer (nicht pro Watch),
konfiguriert im Watch-Dashboard (`/api/my/watch-brief`), gespeichert in
`watch_briefs/{uid}`; Aktivierung setzt mindestens eine vorhandene Watch voraus.
Der 30-Minuten-Loop ruft nach `run_watch_tick` ein
`run_brief_tick` auf: fällige Briefs werden über den Composite-Index begrenzt
gelesen und transaktional geclaimt (Zeitplan rückt vor und das Outbox-Item
entsteht im selben Commit, siehe Zustellgarantie unten), dann wird der Digest
aus `list_watches(include_history=True)` aggregiert (Ziel statt Score, notable
Events seit dem letzten Brief = `trigger == "changed"` aus `drift_signal` oder
ein Abschluss) und als
Multipart-Mail versendet. Modus `changes_only` überspringt Briefs ohne notable
Changes. Kein LLM-Call, kein Watch-Lease nötig; unverifizierte E-Mail-Adressen
werden übersprungen. `/watch/brief/unsubscribe` (eigener HMAC-Token-Typ,
gleicher `WATCH_UNSUBSCRIBE_SECRET`) deaktiviert nur den Brief.
**Zustellgarantie (R17, Produktentscheidung 2026-09):** alle Benachrichtigungen
laufen über die dauerhafte Outbox `notification_outbox` (at-least-once mit
stabiler Delivery-ID, **kein** exactly-once). Watch-Ergebnis und Pause nach drei
Fehlern schreiben ihre Items in derselben Transaktion wie Ergebnis bzw.
Fehlerstatus; der Brief-Claim rückt den Zeitplan vor und legt sein Item in
derselben Transaktion an; Topic-Runs legen Follower-Items im Run-Commit an.
Direkt danach folgt ein erster Zustellversuch; jeder 30-Minuten-Tick ruft
anschließend `run_notification_outbox_tick` für alle fälligen Items auf (neu,
nach Absturz mitten im Versuch nach Ablauf des 10-Minuten-Leases, oder im
Backoff 15 min … 6 h). Vor **jedem** Versuch prüft `notification_delivery`
den aktuellen Zustand: Watch aktiv/nicht gelöscht, Kanal an, Telegram nicht
stummgeschaltet und verbunden, Follower noch vorhanden, Brief noch aktiv,
Konto nicht in Löschung, E-Mail verifiziert; sonst wird das Item `skipped`.
Ein Kanal- oder Empfängerfehler blockiert andere Items nicht. Nach acht
Versuchen oder nach `deliver_until` (3 Tage, Brief 12 Stunden) wird es
`failed` und erscheint in `/health/metrics` unter `notification:<kind>` als
Failure. Retries lesen nur Payload und immutable Watch-Version; sie starten nie
eine neue LLM-Pipeline. Grenze: SMTP-Annahme ist keine Postfachzustellung, und
ein Absturz nach Provider-Annahme, aber vor dem Statuscommit, erzeugt ein
Duplikat. `last_condition_status=met` wird jetzt mit dem Ergebnis committet,
weil der Alarm im selben Commit dauerhaft eingeplant ist.
Im Admin-Dashboard kann eine aktive Watch fällig gestellt und der In-Process-Scheduler
sofort aufgeweckt werden; der HTTP-Request wartet nicht auf die Modellaufrufe.
Der manuelle Lauf verbraucht reale Modellaufrufe, schreibt reguläre History, rückt den Zeitplan vor
und wendet unverändert die konfigurierte Mailregel an. Der unabhängige SMTP-Test führt
keinen Watch-Lauf aus und ändert keinen Zeitplan.
Query-first-Watches legen beim Erstellen nur eine nicht indexierte Share-Hülle
mit Frage und `awaiting_first_watch_run=true` an. Share-Hülle, Watch,
Owner-Zähler und Query-Uniqueness-Key entstehen gemeinsam; normale Share-Watches
verwenden entsprechend einen Share-Uniqueness-Key. Altbestände initialisieren
diese Indizes beim ersten Schreibzugriff. Auch die globale Publisher-Kapazität
wird innerhalb dieser Anlage-Transaktion statt über einen vorgelagerten Count
durchgesetzt. Der erste planmäßige Watch-Lauf
gilt ausdrücklich als Baseline (kein Changes-only-Alert durch den vorher leeren
Text), schreibt zugleich die erste immutable History-Version und füllt die
Share-Baseline. Condition- und Every-run-Regeln dürfen beim ersten Lauf bereits
auslösen; vor diesem Lauf zeigt die Watch-Seite transparent den ausstehenden
ersten Check statt eines leeren Consensus-Panels.

---

## 8. Kritische Verträge & Stolperfallen

- **Nur `/api/v1` steht in `/openapi.json`.** Alle übrigen Router werden in
  `main.py` mit `include_in_schema=False` eingebunden, damit die interne App-
  und Admin-Oberfläche nicht als fertige Landkarte veröffentlicht wird. Ein neuer
  interner Router muss in diese Schleife — sonst taucht er öffentlich auf.
- **Test-Flags sind in Produktion ein harter Startfehler.** `MOCK_AUTH`,
  `MOCK_ADMIN`, `MOCK_LLM`, `DISABLE_RATE_LIMIT`, `UNIT_TEST_MODE` und
  `E2E_TEST_MODE` aktivieren Mock-Kontrollen beziehungsweise credentialfreie
  Test-Initialisierung. `app/core/security.py` verweigert den Start, wenn eines
  davon zusammen mit `RENDER_SERVICE_NAME` oder `ENVIRONMENT=production` gesetzt
  ist. Außerhalb expliziter pytest-/E2E-Läufe ändert sich lokal nichts.
- **`/register` darf nie verraten, ob eine E-Mail existiert.** Beide Fälle geben
  exakt `{"status": "check_inbox"}` zurück; das gilt auch für das Create-Race.
  UID, E-Mail und Custom-Token werden nie zurückgegeben. Ein neuer Firebase-User
  bekommt nur ein langes serverseitiges Zufallspasswort; anschließend erhalten
  neue und bestehende Adressen denselben gehosteten Passwort-Setup-Link. Der
  Browser zeigt den neutralen Erfolgs-Screen und führt keinen Probe-Login aus.
  Eine spezifische Fehlermeldung oder ein Login-Seitenkanal wäre Konto-Enumeration.
- **Script-Ladereihenfolge für `/app` steht in `static/js/bundles.json`.**
  Seit 2026-08-17 listet `templates/index.html` die Dateien nicht mehr selbst;
  es rendert die Tags aus `app/core/assets.py`, das dieselbe `bundles.json`
  liest wie der Build (`scripts/build_frontend.mjs`, `npm run build`). Ein neues
  Skript wird **nur dort** eingetragen. Reihenfolge-Zwänge stehen als `note`
  neben der jeweiligen Datei. `app-init.js`/`app-dom-events.js` sind aus dem
  `</body>` in die deferred `app`-Gruppe gewandert — deferred Skripte laufen
  ohnehin erst nach dem Parsen, ihre Position im Dokument war nie die
  Reihenfolge. Details: `docs/frontend-build.md`. Die Zwänge selbst gelten
  unverändert:
  `app-bootstrap.js` setzt Config, die State-Owner und `run-registry.js` laden
  vor Firebase und den Feature-Modulen; `app-core.js` ergänzt den bestehenden
  `window.App`-Bus;
  `chat-session.js` muss vor `consensus-run.js` und `query-send.js` laufen;
  `run-view.js` muss nach `consensus-run.js`, aber vor `query-send.js` laufen;
  `composer-quote.js` liegt bei `memory-edit.js` (dessen Auswahlmenü es füllt)
  und muss vor `query-send.js` stehen, das beim Senden `window.App.quote`
  abfragt;
  `consensus-anchor.js` muss vor `consensus-insights.js` laufen;
  KaTeX + Auto-Render müssen vor `math-render.js`, dieses wiederum vor
  `markdown-stream.js` geladen werden;
  `app-init.js` initialisiert danach die App; `app-dom-events.js` bindet zuletzt
  die delegierten DOM-Events (beide am Ende der deferred `app`-Gruppe).
  Reihenfolge umstellen oder ein Modul rausnehmen ⇒ `ReferenceError` /
  `window.X is not a function`.
- **`window.App` ist die Classic-Script-Modulschnittstelle.** Es gibt keine ES-Imports zwischen den
  Feature-Modulen. Wer eine Funktion umbenennt/verschiebt, muss alle `window.`-
  Aufrufstellen mitziehen (Grep über `static/js/` + `static/firebase.js` +
  `static/demo.js`). Wichtige Globals u. a.: `window.sendQuestion`,
  `window.getConsensus`, `window.canGenerateConsensus`, `window.App.consensusBodyEl`,
  `window.updateConsensusButtonAvailability`, `window.revealConsensusOutput` /
  `hideConsensusOutput`, `window.cancelCurrentConsensus`, `window.openShareDialog`,
  `window.openWatchDialog`, `window.openWatchDashboard`,
  die read-only Kompatibilitäts-Getter `window.currentEvidenceSources`,
  `window.consensusCitationMeta`, `window.lastShareResultId`,
  `window.currentBookmarkShareResultContext`,
  `window.currentBookmarkShareResultPromise`,
  `window.resolveCurrentShareResultId`, `window.clearPreparedBookmarkShareResult`,
  `window.isUserPro`, `window.pendingAttachments`, `window.ConsensusMath`,
  `window.App.reportCriticalError`.
- **`window.App.runRegistry`** ist der einzige Owner paralleler Browser-Runs
  (`create/get/update/setStatus/show/showSavedView/clearVisible/cancel/clearAll`).
  Jeder Netzwerk-Callback erhält oder schließt über eine konkrete `runId`; ein
  Vergleich gegen `visibleRunId` entscheidet ausschließlich über Rendering,
  nie darüber, ob der Hintergrundlauf weiterarbeiten oder speichern darf.
- **`window.App.emailVerification`** wird im render-blockierenden Head-Bundle
  definiert und von `firebase.js` konsumiert. Die Brücke hält
  `email-verify.js` im content-gehashten Manifest statt hinter einem separaten,
  manuell versionierten ESM-Import.
- **`window.App.followup`** (definiert in `consensus-run.js`) ist nur der
  Follow-up-Kompatibilitäts- und Verlauf-State der sichtbaren Projektion
  (`offer/consume/reset/render`,
  `isArmed/hasContinuableExchange/markContinuationUnavailable/
  archiveCurrentExchange/renderStoredTurn/renderStoredTurns/clearHistory`).
  `run-view.js` speist ihn aus dem gewählten Context; `query-send.js` darf ihn
  nicht als Fortsetzungsquelle verwenden. `app-init.js` (reset in
  `clearResponseBoxes`) und `user-tier.js` (render bei Tier-Wechsel) hängen
  weiterhin daran; einziges DOM-Ziel ist `#threadHistory` in `index.html`.
- **`window.App.createChatSession(initial)`** (definiert in `chat-session.js`)
  erzeugt die laufzeitlokale Chat-Zuordnung jedes Contexts (`activeChatId` +
  `activeTurnId` ausschließlich
  als completed Basis, `pendingChatId`/`pendingTurnId`/
  `pendingContextVersionId`, stabile pending Request-/Usage-ID und whitelisted
  logische Run-Metadaten). `query-send.js` startet diesen privaten State nach
  `/prepare`,
  erzeugt bei aktiven Fortsetzungen Turn und Context vor dem Provider-Fan-out
  und reconciliert mehrdeutige
  Abbrüche; `consensus-run.js` verändert ihn nur anhand der autoritativen
  `chat_turn_state`-Disposition. `window.App.chatSession` bleibt nur ein durch
  `run-view.js` gesetzter Legacy-Spiegel und ist keine Ausführungsquelle.
  Ein owner-gebundenes Chat-Bookmark setzt nach vollständigem Transcript-Load
  über `showSavedView` die letzte completed Basis für den nächsten Context.
- **`window.App.bookmarkSession`** (definiert in `firebase.js`) spiegelt nur die
  Bookmark-Dokument-ID der sichtbaren Unterhaltung. Im Multi-Run-Pfad gehören
  ID, Pending-/Save-Zähler und Fehler zu `RunContext.bookmark`/
  `RunContext.persistence`; alle Save-Aufrufe müssen `runId` und Bookmark-ID
  explizit tragen. „New comparison“ ändert die Projektion, nicht diese
  Hintergrund-Persistenz; Logout verwirft alle Contexts.
  `bookmarkMeta` erhaelt das boolesche `has_consensus` serverseitiger Metadaten;
  nur vollstaendige Dokumente mit `responses` leiten es erneut aus dem Text ab.
  Sonst verlor ein real gespeicherter Consensus beim Meta-Upsert seine Kennzeichnung.
- **`window.App.setAppTitle(question?)`** (definiert in `app-core.js`) hält den
  Standard- bzw. fragebezogenen Browser-Tab-Titel bei Query-Send, Bookmark-Open
  und Clear synchron zur aktuellen Ansicht.
- **`window.App.consensusBodyEl(scope?)`** (definiert in `app-core.js`) ist das
  EINZIGE Renderziel des Konsenstextes (`#consensusAnswerBody`). Nie wieder per
  `.consensus-main p` adressieren — dieses `<p>` existiert nicht mehr; alle
  Aufrufer (`consensus-run.js`, `consensus-lifecycle.js`, `consensus-actions.js`,
  `consensus-insights.js`, `query-send.js`, `app-init.js`, `firebase.js`,
  `demo.js`) gehen über den Helfer. Reihenfolge bleibt Vertrag: erst
  `injectMarkdown` (inkl. KaTeX), **danach** `renderConsensusInsights` — sonst
  zerstört der Math-Renderer die Marker bzw. die Ankersuche trifft KaTeX-Knoten.
- **`window.App.differencesPanel.{setSynthesizing,expandForFallback}`**
  (definiert in `consensus-insights.js`) steuert das zugeklappte
  `<details>` unter der Antwort. Wer einen neuen Freitext-Fallback-Pfad baut,
  muss `expandForFallback()` rufen — sonst verschwindet die Analyse
  stillschweigend hinter einer zugeklappten Zeile.
- **`window.App.consensusLifecycle.*`** ist die gezielte Run-State-Brücke
  (`startRun/isActiveRun/finishRun/setSynthesizing/isRunning/
  markPendingCanceled/initAutoConsensusToggle`). Für Registry-Contexts delegiert
  sie Status, Synthese und Cancel an die explizite Run-ID; der Singleton-Pfad
  ist nur Legacy. Run-ID-Gating nicht umgehen, sonst rendern alte Läufe in neue.
- **`window.App.watch.showFeatureNudge()`** wird nach einem erfolgreichen
  Consensus-Final aufgerufen und zeigt den einmaligen, lokal dismissbaren
  Consensus-Watch-Hinweis nur für eingeloggte Nutzer mit `result_id`;
  `.resetAfterLogout()` leert und schließt die geladene Watch-Ansicht.
- **`window.App.sharedModal.open(mode)` / `.close()`** koordinieren den gemeinsam
  genutzten `#shareModal` für Share und Watch einschließlich Modusklasse,
  Background-Scroll-Lock und Rückgabe des Fokus an den Auslöser.
- **DOM-als-View/Next-Run-State**: `dataset.consensusAnswer`,
  `dataset.consensusSources` und `dataset.responseState` spiegeln nur den
  sichtbaren Context; `.excluded`-Klassen konfigurieren die nächste
  Run-Aufstellung. Die session-lokalen
  `.agent-mode-show-answers`-, `.direct-comparison-active`- und die persistente
  `.agreement-score-hidden`-/`.agreement-verdict-hidden`-Body-Klassen
  u. a. bleiben UI-/Darstellungs-State, sind aber keine Ausführungsquelle eines
  bereits gestarteten Runs.
  Vorsicht beim Umbauen von Markup. Alte, nicht vorhandene Control-IDs
  `#consensusButton`, `#toggleAllButton` und `#apiTestArea` sind kein Vertrag mehr.
- **Jinja↔JS-Brücke**: Config geht nur über die escaped `data-*`-Attribute von
  `#appBootstrapConfig`; `app-bootstrap.js` erzeugt daraus die read-only Werte
  (`FIREBASE_CONFIG`, `APP_LIMITS`, `FREE_DEFAULT_MODELS`, `PRO_DEFAULT_MODELS`,
  `CONSENSUS_PRESETS` inklusive Antwort-/Consensus-Model-Sets,
  `DEFAULT_CONSENSUS_PRESET`, `FREE_LIMIT`) oder
  serverseitig gerenderte Template-Optionen wie
  `consensus_models` für den Consensus-Picker. Dessen
  `data-engine-provider` hält weiterhin die logische Modellfamilie fest; im
  Own-Key-Modus geht der eine lokale `openrouter_key` an `/context`.
  `app-init.js` kann kein Jinja rendern — neue Server-Werte müssen im Meta-
  Vertrag plus `app-bootstrap.js` ergänzt werden. Admin nutzt entsprechend
  `#adminBootstrapConfig` + `admin-config.js`.
- **CSP** (`CustomSecurityMiddleware` in `security.py`): neue externe Hosts (Skripte,
  `connect-src`-Ziele, Frames) müssen explizit in die Policy. Sonst blockt der
  Browser still. `/app`, `/app/watches`, `/admin`, `/admin/*` und `/topics/*` erzwingen bei `script-src`
  die strict-variante ohne `'unsafe-inline'`; neue Inline-Skripte/-Handler würden
  dort deshalb nicht ausgeführt. `style-src` bleibt vorerst kompatibel.
- **Static-Caching, zwei Regime.** Für **`/app`** kommt die Marke seit
  2026-08-17 aus dem Dateiinhalt (`app/core/assets.py`); dort gibt es nichts
  mehr zu bumpen, wohl aber nach jeder `static/`-Änderung ein `npm run build`,
  weil `static/dist/` mitcommittet wird. `tests/test_frontend_build.py`
  vergleicht dazu einen im Manifest hinterlegten Quell-Fingerabdruck mit den
  echten Dateien und schlägt bei vergessenem Build fehl.
  Für die **öffentlichen Seiten und `admin.html`** seit 2026-10-04 ebenfalls:
  Templates nutzen `{{ asset_url('/static/...') }}`; der Hash umfasst die
  transitiven lokalen `@import`-/ESM-Abhängigkeiten, deren eigene URLs
  unversioniert bleiben. `StaticDeliveryMiddleware` cacht `?v=<12 hex>` und
  `static/dist` ein Jahr `immutable`, alles andere unter `/static` ist
  `no-cache` (ETag-Revalidierung). Handgeschriebene `?v=` verbietet
  `tests/test_frontend_resilience.py`; Details in `docs/frontend-build.md`.
- **Provider-Label-Konvention**: Frontend nutzt teils `Claude`, Backend kanonisch
  `Anthropic`. Beim Verdrahten neuer Modelle Mapping in `app-core.js::modelPrefs`
  und Backend-`normalize_model_name` synchron halten.
- **Provider-Laufzeitvertrag**: Neue LLM-Transporte verwenden ausschließlich
  `llm/provider_runtime.py` für Timeout-/SDK-Retry-Konfiguration. Ein SSE-
  Disconnect bedeutet „Serverarbeit abbrechen“; aktive Responses müssen am
  normalen Ende und bei Cancellation geschlossen werden. Automatische
  Transport-Retries dürfen keinen zweiten kostenpflichtigen Versuch verstecken.
  OpenRouter-Fehler im JSON-Body oder SSE-Event werden auch bei HTTP 200 als
  `_ProviderResponseError` behandelt. Nur numerische HTTP-Fehlercodes (400–599,
  auch als dreistellige ASCII-Zeichenfolge) bleiben für `safe_exception` erhalten;
  408/504 werden wie HTTP-Timeouts klassifiziert. Rohmeldungen und Metadaten
  werden verworfen. Ein Fehlerbody gilt dadurch nicht als leere Modellantwort.
- **Observability ist content-frei.** Request- und Scheduler-Correlation-IDs,
  Provider/Job-Name, Erfolg/Fehler/Timeout, Anzahl und Laufzeit dürfen geloggt
  bzw. unter `/health/metrics` aggregiert werden. Prompts, Modellantworten,
  Difference-Quotes/Anchors, E-Mails, Tokens und rohe Exception-Strings externer
  Provider dürfen nicht in Logs oder Metrik-Labels gelangen.
  Dasselbe gilt für globale Exception-Handler und Browser-Alerts: geloggt und
  alarmiert werden nur `safe_exception`-/Typkategorien, Route-Templates und
  allowgelistete Phasen, niemals Stacktraces, Exceptiontexte oder konkrete URLs.
  Für Provider-Fehler gibt es zusätzlich `provider_diagnostic(exc)`: Aus dem
  OpenRouter-Fehlerobjekt (auch aus dem begrenzt gelesenen Body einer HTTP-4xx/5xx-
  Streaming-Antwort) werden nur allowgelistete Tokens abgeleitet, also Providername,
  Upstream-Statusenum (z. B. `INVALID_ARGUMENT`) und eine feste Fehlerklasse
  (`thought_signature`, `context_length`, `tool_protocol` …). Der Providertext
  wird nur klassifiziert, nie kopiert. „Agent completion failed“ loggt dazu
  `detail=` und `where=` (`safe_traceback`).
- **Account-Deletion-Fence:** Jede neue owner-gebundene Firestore-Mutation liest
  `account_deletion_jobs/{uid}` in derselben Transaktion vor ihrem Write. Ein
  separater Vorcheck ist wegen TOCTOU nicht ausreichend. Nur idempotente interne
  Cleanup-Pfade dürfen einen expliziten Bypass verwenden; Double-Opt-in-Tokens
  müssen einen noch vorhandenen Challenge-State atomar konsumieren, damit die
  Kontolöschung alte Bestätigungslinks invalidiert.
- **Blocking-I/O-Vertrag**: Router mit synchronem Firebase-/Firestore-SDK sind
  `def`; echte Async-Routen lagern vollständige blockierende Bündel per
  `asyncio.to_thread` aus. Einzelne SDK-Calls dürfen nicht direkt in einem
  `async def` landen. `test_router_event_loop_contract.py` schützt dies.
- **Usage-Key ist ein Backend-/Frontend-Vertrag.** Ein frischer logischer Lauf
  nutzt denselben `usage_run_key` in `/prepare`, allen `/ask_*` und
  `/consensus`; Resolve nutzt einen eigenen Key. Run-Typ (`regular` oder
  `deep_think` = Reasoning an) und Limits werden ausschließlich serverseitig bestimmt. Niemals
  clientseitige Kosten, Modellanzahl oder Float-Inkremente übernehmen; niemals
  Provider-Aufrufe in die Firestore-Transaktionsfunktion verschieben. Vor jeder
  Developer-Key-Operation muss nach Consume der passende einmalige Claim
  (`ask:<provider>`, `consensus`, `resolve`) erfolgreich sein; ein bereits
  belegter Claim ist kein Retry-Ticket und wird vor externer Arbeit abgewiesen. Der
  Chat-Context-Endpoint darf im Developer-Modus nur einen bereits konsumierten
  Run verwenden und bindet dessen Hash-Metadaten vor dem LLM-Call einmalig an
  genau einen Chat/Turn; diese Bindung verändert keine Usage-Zähler.
- **Own-Key-Vertrag:** Die App bietet genau ein optionales `openrouterKey`-Feld in
  `localStorage`. Im Own-Key-Modus senden alle Registry-`/ask_*`-Flows,
  `/consensus` und `/resolve` ausschließlich `openrouter_key`; `/prepare` trägt
  weiterhin keine Provider-Key-Felder. Die Modell-/Antwortboxen folgen der
  Registry; die historischen Endpoint-Namen
  bleiben unverändert.
- **Datenminimierung ist Designentscheidung**: keine IP-/User-Agent-Speicherung,
  keine Datei-Bytes in Firestore. Nicht „aus Versehen" mitloggen.

---

### Eigenständige Videoproduktion

Die Videoproduktion wurde in das eigenständige öffentliche Repository
[sudoleo/consens-video](https://github.com/sudoleo/consens-video) ausgelagert.
Dort liegen der 60-Sekunden-Film, Canvas-Szenen, Assets, npm-/Python-Abhängigkeiten,
Render- und Medienprüfungen sowie die Produktions- und Anpassungsanleitung.
Dieses App-Repository enthält keine Video-Toolchain und kein `check video`-Ziel
mehr. Die Videoproduktion benötigt weder App-Server, Firebase, API-Schlüssel noch
Dateien aus diesem Repository; ihre `window.*`-Funktionen gehören nur zur
generierten Filmseite. Änderungen am Film und seine Prüfungen erfolgen im neuen
Repository. Die vorhandene Git-Historie dieser App bleibt erhalten.

## 9. Bei Änderungen aktualisieren

Diese Datei ist die zentrale Architektur-Karte. **Aktualisiere sie im selben
Commit/PR**, wenn sich Folgendes ändert:

- **Architektur/Module**: neues/entferntes/umbenanntes JS-Modul oder Backend-
  Service; geänderte Ladereihenfolge oder Modul-Verantwortlichkeit (§2, §3, §5).
- **API**: neuer/entfernter/umbenannter Endpoint oder geändertes Request/Response-
  bzw. SSE-Format (§2, §4).
- **Flows**: Änderung an Query-Fan-out, Consensus/Differences, Agent Mode,
  Attachments, Auth/Usage oder Sharing (§4).
- **Verträge**: neue/entfernte `window.*`- bzw. `window.App.*`-Schnittstelle, neues
  DOM-Dataset-als-State, neue Jinja↔JS-Brücke, CSP-Erweiterung (§8).
- **Daten/Config**: neue Firestore-Collection/-Feld, neue Umgebungsvariable,
  geänderte Limit-/Modell-Quelle (§6).
- **Cache-Busting (immer, auch bei Kleinständerungen)**: Nach **jeder** Änderung
  an Dateien unter `static/`:
  - **`/app`**: `npm run build` laufen lassen und `static/dist/` mitcommitten.
    Die Marke selbst kommt aus dem Inhalt, es gibt dort nichts von Hand zu
    bumpen. Lokal reicht der Source-Modus (`FRONTEND_DEV=1`, Launch-Config
    `consensio-mock-dev`), der die Einzeldateien mit Inhalts-Hash ausliefert.
  - **Öffentliche Seiten und `admin.html`**: nichts zu tun. Neue Dateien im
    Template immer als `{{ asset_url('/static/...') }}` einbinden, verschachtelte
    Imports ohne `?v=`; der Inhalts-Hash übernimmt den Rest.

Faustregel: Wenn ein neuer Agent durch deine Änderung an einer der obigen Stellen
**überrascht** würde, gehört es hier rein. Kurz halten — verifizierte Fakten statt
Implementierungsdetails. Bei Detailtiefe lieber auf den Code verweisen.

Check contradictions ist seit der Todo-Runde 3 (2026-10-02) eine stehende
Einstellung statt eines Werkzeugs im Composer: `#composerSourcesToggle` (Leiste)
und `#sourceCheckMenuSwitch` ((+)-Menü) sind entfernt, es bleibt nur
`#sourceCheckSwitch` unter Settings → Runs („Check contradictions against
sources“), gespeichert unter `localStorage.checkSources` (Default On). Grund:
Der Schalter stand prominent, steuerte aber nur den späteren Quellenabgleich,
dessen Ergebnis hinter Klicks lag. Das Ergebnis rückt dafür an die Antwort:
`App.sourceVerification.brief(snapshot)` liefert eine kurze Phrase („1 settled
by sources“, „sources inconclusive“, „checking sources“, sonst leer), die
`agent-review.js` als `.agent-evidence-note` an den Contradictions-Link unter
einer Agent-Antwort hängt (nur bei gebundenem Snapshot). Englischsprachige
Hilfetexte erklären „Check contradictions against existing sources“ und die
Produktgrenze: keine vollständige Faktenprüfung des Consensus.
Im bisherigen Consensus-Modus ohne Agent Mode sind alle drei Quellenprüfungs-Controls ausgeschaltet und gesperrt.
Die gespeicherte Auswahl bleibt erhalten und gilt wieder beim Aktivieren von Agent Mode.
`window.App.isSourceCheckEnabled()` liefert bei aktivem Agent Mode oder im Beta-Chat die Auswahl für den nächsten Lauf;
`query-send.js` friert sie als `config.checkSources` im RunContext ein.
`/consensus` akzeptiert `check_sources: false`: keine Fetch-/Judge-Aufrufe,
keine `sources.*`-Events, neuer Snapshot `status: disabled`. Bereits gespeicherte
completed Turns werden unverändert wiedergegeben, einschließlich früherer
null-/v1-/v2-/v3-Ergebnisse. Jobverweise laden den aktuellen Stand nach, ohne
neuen Auftrag. Die neutrale Pipeline startet standardmäßig keine Prüfung
(`check_sources=None`); nur `/consensus` übergibt ausdrücklich die Chat-Auswahl.
Watches, Topics und API-Läufe erzeugen weder Jobs noch Disabled-Prüfberichte.
Ihre bisherigen Consensus-/Differences-/Agreement-/Quellen-Abläufe bleiben erhalten.
Watch-History-Reader und Watch-Seiten unterdrücken auch versehentlich gespeicherte
Prüfungen, einschließlich Original-/Historienansicht; Topic-Seiten zeigen nur die
bisherigen Quellen. Gespeicherte Antworten und Quellen werden nicht migriert.
Die Job-Annahme weist Nicht-Chat-Kontexte ab; noch fällige Nicht-Chat-Jobs werden
beim Claim transaktional als `cancelled`/`chat_only` beendet, vor Credentials,
Plan-Read, Fetch oder Judge. Alte API-/Topic-Prüfendpunkte bleiben für historische
Daten lesbar. Chat-Shares behalten ihre gespeicherten Prüfergebnisse.

Die Prüfung erklärt erkannte faktische Streitpunkte anhand vorhandener Quellen.
Verworfene Prüfurteile erscheinen als „Contradiction remains unresolved“
(bei mehreren mit Anzahl), mit verständlicher Erklärung und den gespeicherten
Validierungsgründen im Detail. Gemischte Ergebnisse trennen abgeschlossene
Prüfungen, ungeklärte Widersprüche, nicht verfügbare und ausgelassene Prüfungen;
die gespeicherten Statuswerte und die Validierung bleiben unverändert.
„No checkable contradictions detected“ heißt ausschließlich, dass Differences
keinen geeigneten Prüfauftrag erkannt hat. Laufende Arbeit, deaktivierte
Prüfung, fehlgeschlagene Analyse/Abrufe, unzureichende Evidenz und Budgetauslassung
haben unterschiedliche Anzeigen. Originalpassagen werden nicht übersetzt.
Die Legacy-Darstellung zitierter Satz-/Quellen-Paare bleibt erhalten: Hover,
Originalpassagen, Quellenzeilen und bestehende Prüf-Farben funktionieren beim
Wiederöffnen alter Antworten. „No highlights“ verbirgt über
`consensus-markers-hidden` weiterhin deren Markierungen, ohne Links/Befunde
zu entfernen. Sources und Differences bleiben flache Reader-Listen;
Resolve bleibt eine unabhängige sekundäre Aktion mit erhaltenem `[hidden]`.

## Agent-Dateien (2026-09-27)

`agent_files.py` (Router/Service) ergänzt owner- und chat-gebundene private Dateien:
`POST/GET /agent/chats/{chat}/files`, `GET/DELETE .../{file}`. Der bestehende
Composer lädt vor `/agent` hoch und sendet ausschließlich validierte `file_ids`;
die Auswahl wird in `agent_settings` eingefroren und bei Replay verglichen.
`agent-workspace.js` zeigt Download, Status, Warnungen und Löschen auch nach Reload.
Die Anhangs-Metadaten des Turns (`attachments`, `normalize_attachment_meta`)
behalten bei Agent-Uploads die Datei-`id` (32 Hex) und `warnings`, damit der
Chip an der Nachricht die Datei später wieder öffnen kann; Consensus-Anhänge
bleiben reine Metadaten. Gmail-Importe tragen die `turn_id` des holenden Turns.
Der Upload nimmt optional `drive_file_id` (nur bei konfiguriertem Drive-Picker,
sonst 403): die Datei wird `kind: "drive_file"` mit `origin: {source:
"google_drive", file_id}` und bringt den Chat beim nächsten `/agent` unter die
Google-Regeln (siehe „Google als Quelle“ oben). Die Bytes holt der Browser selbst.
Dateien werden nicht in Shares, Memory oder Watch-Inputs übernommen.

`GET .../files` liefert die Liste chronologisch (`created_at`, Firestore streamt in
zufälliger ID-Reihenfolge), Dokumentversionen mit `title` (neue Versionen tragen
ihn am Dateieintrag, ältere über einen Manifest-Read pro Dokument) und importierte
Gmail-Anhänge mit `origin_subject`/`origin_from` nur zur Anzeige (`origin` bleibt
der Wiederverwendungs-Schlüssel).

UI-Vertrag (2026-09-30, `agent-workspace.js` + `agent-workspace.css`). Jede Datei
steht an der Nachricht oder Antwort, zu der sie gehört; es gibt keine chatweite
Dateiliste unter der Antwort mehr:
- `App.agentWorkspace.refresh(chatId, force)`: ohne `force` projiziert es nur die
  gecachte Liste neu (billig, darf bei jedem Render laufen, z. B. Turnwechsel).
  Chatwechsel oder `force` holen die Liste, gebündelt auf höchstens einen Request
  pro 300 ms (sofort plus ein nachlaufender). Ein frisch angelegter, noch nicht
  angenommener Chat des sichtbaren Laufs gilt als leer (kein GET). Ein erster
  Ladefehler wird einmal still wiederholt, danach „Couldn't load chat files… Retry“.
  `refresh` lädt KEINE Google-Aktionen mehr: der Aufrufer ruft
  `App.agentGoogle?.refreshActions?.(chatId, force)` separat
  (`resources`-Events je nach Payload-Schlüssel `documents`/`files` bzw.
  `actions`/`gmail_evidence`).
- `#agentAnswerResources` (nach `#agentAnswerBody`, vor `#agentAnswerError`; wird
  angelegt, falls das Template es nicht enthält): Upload-Fortschritt pro Datei,
  Hinweis „n file(s) were only partly readable“ für die mit dieser Nachricht
  gesendeten Dateien (`agent_settings.file_ids`) und je `document_id` eine
  Dokumentkarte der angezeigten Turn (`turn_id`): Titel, aktuelle Version,
  DOCX/PDF-Download, Badge „New/Updated in this answer“, frühere Versionen
  eingeklappt, ein Revisionshinweis. Dazu die in dieser Turn geholten
  Mail-Anhänge („From email: Betreff (Absender)“, Fallback
  `App.agentGoogle?.evidenceFor`). Keine Roh-IDs in der Oberfläche.
- Archivierte Agent-Turns (`appendHistoryTurn` in `consensus-run.js`) bekommen
  eine eigene Ressourcenzeile: `App.agentWorkspace.renderTurnResources(row, turnId)`
  registriert sie (`data-agent-turn-resources`), jede Projektion füllt sie aus der
  gecachten Liste mit den Dokumentversionen bis zu dieser Turn (kompakt) und
  ihren Mail-Anhängen.
- Uploads sind Chips an der Nachricht (`#threadAskAttachments` bzw. im Verlauf).
  Ein Chip mit Datei-`id` öffnet den gemeinsamen Viewer (`attachments.js`), der
  die Datei über `App.agentWorkspace.openFile(id)` lädt (Bild als Data-URL, PDF
  und Text im Frame, sonst Hinweis) und darunter „Download“ sowie „Remove from
  chat“ mit Inline-Bestätigung anbietet (`App.agentWorkspace.removeFile(id)`).
  Der Chat ist der sichtbare; der Server prüft Owner und Chat bei jedem Request.
- Entfernen nur über das Overflow-Menü (⋯) mit expliziter Bestätigung; der Fokus
  startet auf „Cancel“. Alle Download-/Menü-Buttons haben sprechende `aria-label`s.
- `upload()` zeigt Fortschritt ohne die Liste zu leeren. Scheitert eine Datei,
  bleibt sie mit Serverbegründung am Composer-Chip
  (`App.attachments.markError(file, message)`), `context.metadata.uploadFailed`
  wird gesetzt und der Fehler lautet „Couldn't upload <Name>. <Grund>“.
  Nachrichten-Chips (`setThreadQuestionAttachments`) tragen optional `warnings`
  und zeigen dann „Partly read“.

Bytes liegen im privaten GCS-Bucket `AGENT_FILES_BUCKET`; auf einem lokalen Checkout
ohne Bucket automatisch unter `%LOCALAPPDATA%/consens/agent-files` (sonst
`~/.local/share/consens/agent-files`), nie auf einem Deploy (`RENDER_SERVICE_NAME`
oder `ENVIRONMENT=production`) und nie in Tests. Metadaten und begrenzte
Auszüge unter `users/{uid}/chats/{chat}/files/{id}`. Kontoquote unter
`chat_state/file_quota`: 100 Dateien / 100 MiB; Datei 5 MiB, Aufbewahrung 30 Tage.
Upload reserviert transaktional, schreibt ein privates Objekt und finalisiert
nur bei weiterhin aktivem Chat und Konto. Fehler/Stop räumen Reservierung und
Objekt auf. Die Chat-Löschkaskade löscht Objekte vor Metadaten; bestehende Account-
Löschung durchläuft dieselbe Kaskade. Ohne konfigurierten Objektspeicher
(`StorageNotConfigured`) scheitert der Upload vor jeder Reservierung mit 503,
und die Löschkaskade überspringt den Objektspeicher statt abzubrechen. Die
stündliche Retention räumt abgelaufene Dateien und verwaiste Uploads seitenweise
mit Zeitbudget auf; ein einzelner fehlschlagender Löschvorgang wird geloggt und
im nächsten Lauf wiederholt. Collection-group-Indizes siehe Setup.

Dokumentversionen unter `documents/{document_id}/versions/{version}` speichern
Tabellenzeilen mit `storage_schema_version=2` als `{"cells": [...]}`-Maps:
Firestore erlaubt keine direkt ineinander verschachtelten Arrays. Der interne
Codec in `agent_documents.py` stellt beim Lesen die unveränderte DocumentSpec
mit Zeilenlisten wieder her. Inhaltshash, API, Rendering und frühere Versionen
behalten dieselbe Bedeutung; alte Datensätze ohne Schemafeld bleiben lesbar.

`agent_file_extract.py` läuft mit 15 s Walltime und auf Linux 10 s CPU / 768 MiB
Adressraum; höchstens 80 PDF-Seiten, 120 Auszüge / 120.000 Zeichen. DOCX-Tabellen
behalten Zellreihenfolge, Textdateien Zeilenbereiche und PDFs Seitennummern.
Scans ohne Text bleiben ausdrücklich als unvollständig erkennbar. Kein OCR.
`run_isolated` ist der gemeinsame Einstieg; klassische Consensus-Anhänge nutzen
ihn im Modus `pdf-text` (siehe Attachments).
`FileContext` ergänzt `read_file`, gezielte Auszüge und native Bilder bei
expliziter Modellfähigkeit. Von `read_file` geöffnete Bilder ergänzen die
Nutzerauswahl (`selection()`), verdrängen sie aber nie. Native PDFs werden nur
gesendet, wenn ihre seitenbasierte Tokenreservierung ins Kontextfenster passt.
Vergleiche erhalten die Auswahl, Worker nur explizite `file_ids`; Judges
erhalten die vorhandene Vergleichsevidenz. Private Bilddaten
werden nur im flüchtigen Provider-Payload ergänzt, mit konservativer
Tokenreservierung und tatsächlicher Usage-Abrechnung. Tool-Daten sind keine
Berechtigungen. Anleitung, Grenzen und PR-Matrix: `docs/agent-integrations.md`.

## Agent-Laufoberfläche: Rendering, Aktivität, Composer (2026-09-30)

**Shell/Run-Trennung.** `agent-chat.js` teilt das Rendern: `renderShell()`
(Modus, Picker, Google-Einstieg, gespeicherte Projektion) läuft nur, wenn sich
eine seiner Eingaben ändert (Signatur aus Modus, Konto, Katalog, Auswahl,
sichtbarem Run/Status, Basis); `App.agentChat.render()` ohne Argument ist daher
billig, `render()` aus eigenen Aktionen erzwingt es. `project(context)` ruft
`projectFrame()` einmal pro Run/Sicht (Titel, Frage, Anhänge, Verlauf, Listen)
und danach nur noch den Lauf: Antwort, Aktivität, Delegation. Der
Registry-Listener rendert keinen zweiten Durchgang. Evidence-Links
(`agentReview.render`) und „Copy answer“ entstehen erst am Ende eines Laufs.
Seit 2026-10-02 führt die Evidenzzeile `.agent-review` mit einem dezenten
Agreement-Score (`.agent-agreement`, „72 /100 agreement“): Wert aus
`check.differences_data.agreement` der gewählten Vergleichsbasis (wechselt mit
„Evidence for“), gleiche Stufenwörter wie der Consensus-Verdict, nur die Zahl in
Ampelfarbe, kein Balken; ohne bewertbare Abdeckung (`coverage_status:
insufficient`) oder bei nicht gebundenem Check keine Zahl. Settings → Agreement
score gilt auch hier (`agreement-score-hidden` zeigt die Wörter,
`agreement-verdict-hidden` blendet aus). „Copy answer“ ist seitdem ein reines
Symbol am Zeilenende (Name per `aria-label`).

**Streaming-Markdown.** `markdown-stream.js::renderMarkdownStream(el, md)`
zerlegt die wachsende Antwort an Leerzeilen außerhalb von Code-/Mathe-Blöcken in
Top-Level-Blöcke; fertige Blöcke werden genau einmal geparst, nur der letzte
offene neu. Listen/Zitate über Leerzeilen bleiben zusammen, eine Grenze gilt erst
mit vollständiger Folgezeile. Ein im offenen Block begonnenes, noch nicht
geschlossenes `**` rendert `closeOpenStrong` schon fett statt mit rohen
Sternchen (nicht in Code-Fences). Fremde Schreibzugriffe oder nicht nur wachsender
Text starten neu. Die finale Antwort rendert einmal vollständig mit
`injectMarkdown` (gleiche Sanitisierung). `resetMarkdownStream(el)` verwirft den
Zustand.

**Ressourcen-Refresh.** Ein `resources`-SSE-Ereignis ruft
`App.agentWorkspace?.refresh(chatId, true)` nur bei Schlüsseln
`documents`/`files` und `App.agentGoogle?.refreshActions?.(chatId, true)` nur
bei `actions`/`gmail_evidence`; ohne erkennbare Schlüssel beide. Beide Seiten
entprellen selbst (300 ms). Ein neuer Chat ohne Uploads projiziert leere Listen
(`refresh(null)`), bis Ressourcen gemeldet werden oder der Lauf endet; vor
`/agent` entstehen keine Listen-GETs mehr.

**Composer und Fehler.** `sendBlocker()` hängt nach den Modellprüfungen
`App.agentGoogle?.blocker?.()` an (Fehler darin blockieren nie). Aktionen der
Composer-Notiz und der Antwortfehler (`#agentAnswerErrorActions`) laufen über
einen Handler: `compare`, `choose-model`, `reload`, `google-consent`
(`App.agentGoogle.consent(true)`), `google-open` (`App.agentGoogle.open()`).
Eine Nicht-SSE-4xx-Antwort von `POST /agent` ohne angenommenen Turn gilt als
nicht gesendet: Entwurf/Zitat kommen zurück, keine Recovery, kein „Failed“-
Sidebar-Eintrag (Folgefrage: Zeile kehrt zum gespeicherten Chat zurück).
`agent_token_reservation`/`agent_tokens_exhausted` erhalten Klartext mit
Rücksetzzeit in Ortszeit und Aktionen; ohne Antworttext kehrt die Frage in den
Composer zurück. Budget-Polling läuft nur im Agent-Modus: alle 5 min, bei
Fokus/Sichtbarkeit nur, wenn der letzte bestätigte Kontostand (Fetch oder
Laufmeldung) älter als 60 s ist oder der letzte Refresh scheiterte.
Serverseitig fragt `agent_quota.snapshot` laufende Delegations-Wurzeln nur
alle `RECOVERY_QUIET_S` (120 s) pro Nutzer erneut ab, wenn keine lief, und
merkt sich ein geschlossenes leeres Vortagsblatt (`PREVIOUS_DAY_GRACE` 2 h nach
Mitternacht) für 10 min.

**Wartet auf Nutzer.** Nach Laufende zeigt `#agentReviewNotice` über dem
Composer „n items need your review“ aus `App.agentGoogle?.pendingCount?.(chatId)`
(aktualisiert auch über `consensio:agent-actions-change`), markiert das
Bookmark mit `.needs-review` und stellt dem Tab-Titel „(n)“ voran. „Review“ und
die Aktivitätszeile „Waiting for your confirmation below“ (nach erfolgreichem
`prepare_calendar_event`/`prepare_gmail_draft`) rufen
`App.agentChat.revealPendingReview()` (scrollt zur ersten offenen Karte und
fokussiert deren erste Bedienung). Alle Integrations-Tools haben Lauf-/Fertig-
Texte in `agent-activity.js`; unbekannte Tools zeigen neutrale Texte. Die
Websuche nennt Anzahl und Domains ihrer Quellen (`Searched the web · 3 sources:
skat.dk, virk.dk, borger.dk`). Die Kopfzeile lautet `Working for 12s` während des
Laufs und `Thought for 3m 7s` danach (`Stopped after`/`Response failed after`).
`Writing answer…` erscheint nur, wenn nach dem letzten `responding`-Status kein
Tool-Schritt mehr kam; Text vor einem Tool-Aufruf ist Vorrede, nicht Antwort.

**DOM-Haken.** `templates/index.html`: `#agentAnswerResources` direkt nach
`#agentAnswerBody` (Paket B rendert Dokumentkarten hinein),
`#agentAnswerErrorActions` nach `#agentAnswerError`, `#agentReviewNotice` vor
`.chat-input-container`.

**Aktivitätsleiste.** Ab 1200 px ist sie seit 2026-10-02 das Spiegelbild der
App-Sidebar rechts (volle Höhe, `--ground`, eine Haarlinie `--line-soft` zur
Spalte, keine Karte, kein Schatten; Zeilen ohne Trennlinien mit Ton beim
Hover, Segmente nur in Tinte, laufender Aufruf als wandernder Abschnitt ohne
Schiene, Faltzeichen nur bei Hover/Fokus/offen); `.auth-top-actions` rückt
für Gäste neben die Leiste. Unter 1200 px bleibt sie ein schwebendes Sheet.
Unter 1200 px öffnet `agent-delegation.js` die Leiste nie
selbst; das Panel-Symbol neben den Modell-Icons (`.agent-sidebar-toggle`,
`aria-label` „Activity · n“, `aria-controls="agentSidebar"`) öffnet ein
Sheet mit Scrim, Fokusfalle und Escape. Ab 1200 px öffnet sie automatisch nur
für einen LAUFENDEN Turn (`get(chat, turn, live)`: `project({running})` bzw.
Live-SSE) und nur, wenn die Lesespalte daneben mindestens 600 px behält; ein
geöffnetes Bookmark oder ein fertiger Turn bleibt seit 2026-10-02 zu, bis man
sie über Chip/Toggle öffnet; offen rückt die Spalte
nach links (`body.agent-sidebar-open`), statt unter der Leiste zu liegen. Nur
explizites Öffnen/Schließen wird pro Turn gemerkt. Der 2,5-s-Takt existiert nur
während eines laufenden bzw. abschließenden Laufs und endet danach.
Zeilenstatus hängt per `aria-describedby` am Eintrag; Texte/Titel werden nur bei
Änderung geschrieben. Judge-Aufrufe (`kind: "judge"`) erscheinen nicht einzeln:
`checkRow` fasst alle Versuche, Wiederholungen und Backup-Judges zu einer Zeile
„Answer check“ (`id: answer-check`, ohne Detail-Request) zusammen. Ihr Status
ist das Ergebnis der Checks (`completed`, sobald jeder Check einmal fertig ist;
`failed` nennt die nicht ausführbaren Checks), Tokens sind die Summe der
gemessenen Judge-Aufrufe. Chip-Zähler und Modell-Icons zählen Judges nicht mit.
Eine ausgefallene Vergleichsantwort heißt `No answer`; beendete Aufrufe ohne
gemessene Tokens zeigen keine Tokenzeile.

**Kontingent.** `.quota-row[hidden]` blendet Watches im Agent-Modus
aus; ein Rest unter 1 % zeigt „<1%“ (Ring `--partial`, erst bei 0 `--dispute`),
die Zeile absolute Tokens, der Fuß die Rücksetzzeit in Ortszeit und UTC.

Folgeaufgabe: Agent-Module als eigene, nur bei `agentAccess.allowed` geladene
Bundle-Gruppe ausliefern (bewusst nicht Teil dieser Änderung).


### Audit-Regressionsschutz: Admin und oeffentliche Browsermodule (2026-10-02)

`admin-api.js::adminErrorMessage` entpackt sowohl den main-Fehlerumschlag
`error` als auch FastAPIs `detail`. Angezeigt werden ausschliesslich bekannte
Stringfelder (`message`/`error`); Listen, unbekannte Objekte und Nicht-JSON
fallen auf den HTTP-Status zurueck. Ein Fehler loest keinen zweiten Write aus;
der Prompteditor behaelt seinen konfliktbehafteten Entwurf.

`admin-benchmark.js` verwendet denselben Client. Listen- und Detailgenerationen
verwerfen Antworten einer vorherigen Auswahl oder Aktualisierung. Beim Wechsel
verschwindet der alte Report sofort; die gelieferte `run_id` muss zur Auswahl
passen. Die Darstellung verwendet nur kompakte Kennzahlen/Fragenmetadaten;
Rohprompts und Rohantworten werden auch aus unerwarteten Zusatzfeldern nicht
in die Ansicht uebernommen.

`tests/e2e/test_topic_frontend.py` prueft das unveraenderte Topic-Skript mit
kontrolliertem SSR-Markup in Chromium: Keyboardnavigation, zweistufiges Touch-
Preview, inerte Notizen und historische/gesperrte Storagezustaende. Die
writerfreie Browserfixture verwendet genau einen Server je pytest-Aufruf,
auch wenn mehrere Module die Fixture importieren. `E2E_PHASE4_PORT` (Default
8033) trennt parallele Worktrees; ein bereits belegter Port bricht den Start
ab. Screenshots bleiben unter `test-results/`.

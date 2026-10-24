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
  Gäste (Agent-Composer seit 2026-10-21, Apple-Audit H3) sehen „Gmail &
  Calendar“ bzw. „Add from Google Drive“ genau dann, wenn jedes Konto sie hat:
  `entries_for_everyone()` (`GOOGLE_TEST_USERS` = `*` und `available()` bzw.
  `drive_picker()`) geht über `pages.py` als `data-google-for-everyone` ins
  Template, `app-bootstrap.js` legt es als `window.GOOGLE_FOR_EVERYONE` ab,
  `agent-google.js::guestEntry(kind)` entscheidet für beide Einträge; ein Klick
  öffnet den Login („Log in to use Gmail and Calendar.“ / „Log in to add
  files.“). Mit einer Testnutzer-Liste sieht ein Gast, was ein nicht gelistetes
  Konto sieht: nichts.
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
later steps, including comparison and judges; web search stops.

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
remote resources (no remote images/media/style), closing markup exfiltration:
an image source must be `data:image/…` or resolve, by the browser's own URL
parser, to the page's origin; SVG `image`/`feImage` and MathML `mglyph` are
forbidden tags. See `docs/google-integrations-setup.md` for required
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
Share-Meta-Descriptions lassen bekannte Citation-Labels weg; bei Watch-Seiten
beginnt die Description mit der Zustandszeile („Paused · last checked Oct 1“)
und nennt weder Score noch Widersprüche, die die Seite nicht zeigt; das Ziel
einer pausierten Watch heißt „Was waiting for“ (`check.state(goal_label=…)`,
Zweitprüfung 16). Die öffentliche
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

- **Backend**: Python 3.12, FastAPI (`fastapi==0.143.2` mit `starlette==1.8.0`),
  via `uvicorn` ausgeliefert. SSE-Streaming über `StreamingResponse`.
  Rate-Limiting via `slowapi`. Die Python-Version steht nur in
  `.python-version` (Render, CI, Dependabot und `dev.ps1` lesen sie). Direkte
  Abhängigkeiten in `requirements.in`, daraus erzeugt die voll gepinnte
  `requirements.txt` (pip-compile, mit `# via`); Ablauf in `docs/testing.md`.
- **LLM-Modelle**: zehn Registry-Familien (OpenAI, Mistral, Anthropic, Gemini,
  DeepSeek, Grok, Kimi, GLM, Meta/Muse, Qwen), alle über einen OpenRouter-Chat-
  Completions-Transport mit einem Routing (schnellster Endpunkt ohne
  Datensammlung, ZDR nur in Google-Chats). Ein Lauf wählt davon höchstens sechs.
  Provider-Label-Konvention: Claude = `Anthropic`, Muse = `Meta`.
- **Auth & Daten**: Firebase Auth (ID-Token) + Firestore (`firebase-admin`).
- **Frontend**: kein Framework. Jinja2-Templates + Vanilla-JS-Module unter
  `static/js/`, überwiegend als klassische `<script defer>`-Tags. `window.App`
  ist Bus und State-Owner; ausgewählte `window.*`-Getter/-Funktionen bleiben als
  Kompatibilitätsvertrag (siehe §8).
- **Markdown/Mathematik**: `marked` + `DOMPurify` clientseitig und
  `markdown-it-py` + `nh3` für Share-Seiten; KaTeX setzt in beiden Ansichten
  LaTeX-Ausdrücke nach dem sanitisierten Markdown-Rendern.
- **CI**: `.github/workflows/tests.yml` (Backend/Frontend bei jedem Push,
  `dependency-audit` mit pip-audit, nachts zusätzlich Browser/Emulator/Rules;
  fehlgeschlagene Tests als Annotationen über `scripts/ci_annotate_failures.py`,
  ohne Login lesbar mit `scripts/ci_status.py`; täglicher CI-Wächter als
  geplante Aufgabe `consens-ci-watch`),
  `.github/dependabot.yml` (monatlich je ein gesammelter PR für pip, npm,
  Actions; keine pip-/npm-Majors). Details in
  `docs/testing.md`.
- **Hosting**: Render. Der tägliche Render-Restart setzt weiterhin flüchtigen
  Prozess-State zurück; Retention/Cleanup läuft davon unabhängig periodisch
  im überwachten Background-Task (siehe §7).

---

## 2. Einstiegspunkte / Routing / Templates

**`main.py`** ist der App-Entry: lädt `.env` (nicht unter `UNIT_TEST_MODE=1`), fügt das vor dem
Framework-Parsing greifende `RequestBodyLimitMiddleware`,
`CustomSecurityMiddleware` (CSP etc.), `CorrelationMiddleware` + slowapi-Limiter,
`I18nMiddleware` (Sprache, `/de/…`, deutsche HTML-Antworten; siehe §4
„Deutsch für deutsche Leser“) und als äußerste `StaticDeliveryMiddleware`
hinzu, mountet
`/static`, registriert globale Exception-Handler und inkludiert alle Router.
Seit 2026-10-15 fängt ein Handler für Starlettes `HTTPException` (Routing,
`StaticFiles`; die eigenen Routen werfen FastAPIs Unterklasse) unbekannte Pfade
ab: Eine GET/HEAD-Navigation mit `Accept: text/html` bekommt die HTML-404
`templates/not_found.html` (`app/core/not_found.py`, `noindex`), Skripte
weiter FastAPIs `{"detail": "Not Found"}`. `allow_head_on_get_routes` nimmt
`HEAD` in jede interne GET-Route auf (uvicorn sendet nur die Header), und zwar
am Router VOR `include_router`: Seit FastAPI 0.14x landen eingebundene Router
nicht mehr als Kopie in `app.routes`, ein nachträgliches Ändern wirkt nicht.
Ausgenommen bleiben die dokumentierte `/api/v1` (sonst wüchse das
OpenAPI-Schema) und der Auth-Proxy `/__/*`.
**Fehlerformat und Drosselung (seit 2026-10-20, Apple-Audit H6):** Der Handler
für FastAPIs `HTTPException` liefert `{"error": <Satz>}` plus die Felder aus
`exc.error_fields` (z. B. `code`, `watch_id` der Watch-Routen). Ein
strukturiertes Detail (`{error|message, error_code|code, …}`, etwa Tageskontingent,
Pro-/Plus-Grenze, Memory-Konflikt mit `revision`, Chat-Turn-Zustand) wird seit
2026-10-21 flach ausgeliefert (`main.error_body`, Zweitprüfung 2):
`{"error": <Satz>, "code": …, "error_code": …, …weitere Felder}`;
`error_code` bleibt als Alias für ältere Leser. Vorher stand es verschachtelt
als `{"error": {...}}`, und die Clients fanden weder Satz noch Code (leeres
Kontingent las „You don’t have access to this.“). Ausgenommen ist nur die
öffentliche `/api/v1/` mit ihrem dokumentierten `{"error": {"code",
"message"}}`. Ein 429 einer Route ohne eigenen Code (Agent-Sendegrenze,
Provider-Cooldown) bekommt `code: "rate_limited"` und `retry_after` aus seinem
`Retry-After`-Header; eigene Codes (`chat_rate_limited`, `limit_reached`,
`usage_run_capacity`, `feedback_cooldown`/`feedback_daily_limit`) bleiben.
Jede Grenze pro Konto (`api_uid_limiter`: Bookmark-Saves, Agent-Turns,
Einstellungen, Uploads, Chat-Schreibzugriffe) sendet seit Nachprüfung 2 diesen
Header: `ApiUidRateLimitExceeded.retry_after` sind die Sekunden, bis der
älteste gezählte Aufruf das Fenster verlässt, `exc.headers` ist der Header für
die `HTTPException`; `persistence_guard.PersistenceLimitError.retry_after`
trägt die Wartezeit des Feedback-Cooldowns (30 s) bzw. bis Mitternacht UTC.
Kann die Kontoprüfung hinter einem gültigen Token nicht gelesen werden
(`security.AuthenticationUnavailable`), antwortet jeder Router mit
`security.auth_unavailable_error()` = 503 + `Retry-After: 5`, nie 401 (der
Browser hielte die Anmeldung sonst für weg); die private Watch-Seite zeigt
dann „One moment, please“ statt „Log in“. Jede
slowapi-Grenze (`RateLimitExceeded`, alle Routen inkl. `/api/v1`) antwortet mit
429 `{"error": "Too many requests in a short time. …", "code": "rate_limited",
"retry_after": <s>}` und `Retry-After` (`rate_limit.retry_after_seconds` aus dem
Fenster des getroffenen Limits, `rate_limit_message`), nie mit „10 per 1
minute“; ein Browser, der ein Seitenformular abschickt (`Accept: text/html`),
bekommt dieselbe Aussage als `templates/notice.html`. Clients unterscheiden so
Drosselung (`rate_limited`, nie ein Upgrade-Angebot) von der Plan-Grenze
(`limit_reached`).
Äußerste Schicht ist `StaticDeliveryMiddleware` (`app/core/static_delivery.py`):
content-gehashte Bundles `static/dist/<gruppe>.<12 hex>.js|css` und
`asset_url()`-URLs mit `?v=<12 hex>` erhalten
`Cache-Control: public, max-age=31536000, immutable`, jede andere
`/static`-Antwort `no-cache` (ETag-Revalidierung), statische Textassets und
HTML ab 1 KiB gzip bei passendem `Accept-Encoding`. API-JSON und
`text/event-stream` laufen unverändert Frame für Frame durch (SSE wird nie
komprimiert oder gepuffert); `tests/test_static_delivery.py` sichert beides ab.
Seit 2026-10-08 tragen alle App-SSE-Antworten `Cache-Control: … no-transform`
(`SSE_HEADERS`; Agent `private, no-store, no-transform`, auch wenn
`CustomSecurityMiddleware` auf `/api/v1/` u. a. den Header überschreibt) und
senden als ersten Chunk `SSE_PADDING` (2 KiB SSE-Kommentar,
`iter_sse_with_keepalive(lead=…)`, Consensus-Replay direkt), damit Proxys, die
erst nach einigen KiB weiterreichen, sofort freigeben. Clients ignorieren
Kommentare (`markdown-stream.js`, `iter_sse_events`).
Jeder Request erhält eine PII-freie `req-*`-Correlation-ID (auch als
`X-Correlation-ID` in der Response); `GET /health/metrics` liefert nur
prozesslokale, aggregierte Provider-/Scheduler-Zähler und Laufzeiten ohne
Prompts, Antworten, E-Mails oder andere Nutzdaten.
Im `lifespan`-Startup ist nur `load_models_from_db()` readiness-kritisch; dessen
Firestore-Read deaktiviert SDK-Retries und besitzt ein echtes Fünf-Sekunden-
Budget. Schema-Backfill und Dokumentanlage sind davon getrennt und laufen erst
nach Readiness als überwachter Einmal-Task. Alle übrigen nicht abbrechbaren
Cleanup-/Recovery-Arbeiten starten ebenfalls erst nach Readiness. Ein
best-effort Einmal-Task räumt abgelaufene Telegram-Link-/Delivery-Metadaten auf und registriert bei
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
`disabled`: Consensus-Watch-, Topic-, SEO-Puls-Scheduler (`seo-pulse-scheduler`),
Consensus-API-Maintenance, Retention-Maintenance,
beide Account-Cleanups (`consensus-api-account-cleanup`,
`full-account-deletion-cleanup`: löschen Daten echter Tombstone-Konten und
Firebase-Auth-User) sowie die Einmal-Tasks (`_run_once`, `restart=False`)
`model-configuration-backfill` (schriebe die Normalisierung des lokalen Codes
nach `app_config/models`, die der Live-Sync übernähme) und
`telegram-watch-startup-maintenance`
(löscht Metadaten und würde per `setWebhook` die Prod-Registrierung des Bots
überschreiben). Regel (`_background_writers_off_reason`): unter `MOCK_LLM=1`
läuft keiner davon; ohne Mock laufen sie seit 2026-10-03 nur in Produktion
(`RENDER_SERVICE_NAME` oder `ENVIRONMENT=prod/production`, `_is_production`)
oder lokal mit `LOCAL_BACKGROUND_JOBS=1`. Ein lokaler Server bezahlte sonst jede
Abfrage der Deployment-Loops doppelt (~10k Reads/Tag pro Dev-Server, plus
volle Collection-Scans bei jedem `--reload`) und konkurrierte um dieselben
Slots. Einzig der
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
| `agent.py` | `GET /agent/models` und `POST /agent`: Admin/Pro-geschützter Modellkatalog aus den vollständigen Firestore-Anbieterlisten samt Reihenfolge, aktuellen Provider-Metadaten und konfiguriertem Standard und begrenzter Modell-/Tool-Lauf im bestehenden Chat. Strikte Auswahl, owner-gebundene IDs, SSE mit bestätigten Fortschritten, Tool-Ergebnissen/Quellen und aggregierter Usage. Alle angebotenen Chatmodelle nutzen den gemeinsamen Websuch-Builder mit begrenzten Exa-Ergebnissen; kein eigener Suchdienst. Vorrang für gemeldete Provider-Gesamtkosten, idempotente Schrittbelege, modellgebundene 429-Wartefrist und Wiederaufnahme fertiger Antworten. Geprüfte Delegation mit eigenen Sitzungen, Mailboxen, Seitenleiste und atomarem gemeinsamen Budget; ergänzende `/agent/chats/{chat}/turns/{turn}/agents`-Detail-/Stop-Endpunkte, `POST /agent/chats/{chat}/requests/{request_id}/stop` (Stop per Request-Identität), `POST /agent/chats/{chat}/turns/{turn}/share-result` (Pending-Snapshot einer fertigen Agent-Antwort fürs Teilen, seit 2026-10-21, siehe „Sharing“) sowie `GET /agent/chats/{chat}/live?request_id=…&after=<seq>` (prozesslokale Frames des laufenden Turns für puffernde Netze und Wiederverbinden, siehe §4 „Agent-Turns laufen ohne Verbindung weiter“). Der Turn läuft auf einem eigenen Thread (`agent_background.py`); die POST-Antwort ist nur ein Tail seiner Frames. Kein `/prepare` oder Memory-Kompressor; liest pro Turn einmal das Nutzer-Memory (Profil, Notiz, Einzel-Erinnerungen) und bietet nach Opt-in `update_memory` bzw. das Feld `memory` an `compare_models`/`check_text` samt SSE-Event `memory` an (siehe §3 „Agent-Memory“); dynamische Vergleichs-/Judge-Tools mit eigener Tokenquote (siehe Agent-Beta-Abschnitt). `recover_only` startet nie einen Modellaufruf. `agent_settings.answer_mode` ist seit 2026-10-14 immer `merged` (der Agent schreibt die Antwort selbst); ältere Turns mit getrenntem Antwortschritt tragen `separate` oder kein Feld. Seit 2026-10-23 speichert jeder Agent-Turn den App-Kontext seiner Frage (`app_context`, nur am Dokument); spätere Nachrichten wiederholen die Frage damit byte-gleich (Prompt-Cache, siehe „Feste Cache-Punkte“). |
| `pages.py` | HTML-Seiten + SEO: `/` (Landing; wer eingeloggt ist, kommt beim direkten Aufruf — getippt, Lesezeichen, Suchtreffer, `Sec-Fetch-Site` `none`/`cross-site` — per 302 auf `/app`. Merker ist das identitätslose Cookie `consens_app=1`, das `auth-session-state.js` beim Login setzt und beim Logout löscht. Klicks innerhalb der Seite (Logo, „Product“, `/#watch`) und `/?home` zeigen weiter die Landing; die Antwort trägt `Vary: Cookie, Sec-Fetch-Site`), `/model-pulse` (öffentliche Best-answer-Raten mit Filtern; API `GET /api/model-pulse`), `/app` (Haupt-App; Tab-Titel `consens.io`, gleich `DEFAULT_APP_TITLE` in `app-core.js`; `noindex`, aber mit OG-/Twitter-Tags, weil die Adresse geteilt wird), `/app/watches` (gleiche App-Shell; watch.js öffnet anhand des Pfads das Watch-Dashboard), `/admin` (inkl. Topics-Tab), `/admin/topics` (308-Kompatibilitätsredirect auf `/admin#topics`), `/admin/benchmark` (Benchmark-Run-Visualisierung), `/about`, `/ai-model-comparison`, `/consensus-engine` (nutzerfreundliche Consensus-Engine-Erklärung), `/privacy` `/imprint` `/terms` (dazu 301 von `/datenschutz` und `/impressum`), `robots.txt`, `sitemap*.xml`. Außerdem der öffentliche, familienaggregierte Best-answer-Zähler `GET /api/model-leaderboard` (60 s Browser-/CDN-Cache; `period=all|since-2026-08-31`; alle neun Familien einschließlich Nullständen, Kimi/GLM und Meta/Muse mit eigenem Verfügbarkeitsdatum aus `_LEADERBOARD_AVAILABLE_SINCE`). Beide Zeiträume nutzen zusätzlich einen serverseitigen 60-s-Cache mit serialisiertem Refresh pro Zeitraum/Prozess. Der gemeinsame Zeitraum zählt die datierten, deduplizierten `model_votes` ab 31.08.2026 über indexierte `count()`-Abfragen pro Familie; Modellkatalog und Counts werden im selben Read-only-Transaktionssnapshot gelesen. Solange der neue `model_votes`-Index aus `firestore.indexes.json` fehlt/aufbaut, greift nur für diesen Indexfehler der gecachte Legacy-Scan. Kontolöschungen entfernen weiterhin Votes aus dem Zeitraum, ohne Lifetime-Zähler zurückzusetzen; `/feedback`, `/vote`, `/check_keys` bleiben die weiteren internen Seiten-Routen (Key-Test nur für verifizierte Logins). Feedback ist persistent pro UID auf 30 Sekunden und 10/UTC-Tag begrenzt. Ein Best-answer-Vote muss an ein noch gültiges, owner-gebundenes `result_id` gebunden sein, zum serverseitigen Gewinner passen und kann pro Lauf genau einmal zählen. |
| `chat.py` | Kern-LLM-Flow: `/prepare`, die aus `cfg.PROVIDERS[*].ask_endpoint` erzeugten `/ask_*`-Routen (aktuell zusätzlich `/ask_kimi` und `/ask_glm`), `/consensus`, `/resolve`. `/prepare` und die `/ask_*`-Endpoints akzeptieren weiter das optionale Legacy-`context`-Feld für nicht migrierte Bookmark-Fortsetzungen. Additiv laden `/ask_*` das owner-gebundene Tripel `chat_id`/`turn_id`/`context_version_id`; Legacy- und Versionskontext zusammen werden abgewiesen. Alle `/ask_*`-Endpoints laufen über `handle_ask` + die deklarative Familien-Registry `ASK_PROVIDERS`; Transport und Credential sind für alle OpenRouter, `useOwnKeys` wählt optional `openrouter_key`. `/consensus` akzeptiert optional Chat-/Turn-IDs plus `turn_sources` und die exakt am Turn verknüpfte `context_version_id`, prüft alles owner-gebunden vor dem Judge und finalisiert nach Consensus, Differences und Share-`result_id` in Streaming- wie JSON-Pfad über `ChatStore`. Sendet der Browser die stabile `bookmarkId`, schreibt `/consensus` den autoritativen Bookmark-Snapshot vor seinem erfolgreichen Final-Event und liefert kompakte `bookmark_meta`; ein separater Browser-Request ist nur noch Fallback. Ein bereits completed Turn wird mit Consensus, Differences, Quellen und Modellantworten owner-geschützt wiedergegeben, ohne Engine-/Differences-/Share-/Statistik-/Completion- oder Usage-Write; ohne IDs bleibt der Legacy-Vertrag unverändert. |
| `chat_history.py` | Additive, owner-gebundene Chat-Persistenz: `POST/GET /chats`, `GET /chats/{chat_id}`, `DELETE /chats/{chat_id}` (dreistufige Kaskade über `ChatStore.delete_chat`; vor der Enumeration wird der Chat transaktional auf `deleting` gesetzt und zugleich ein dauerhafter `chat_deletion_jobs`-Auftrag angelegt, damit kein paralleler Turn als Subcollection-Waise nachrutschen kann und eine unterbrochene Kaskade vom Retention-Loop fortgesetzt wird; `deleting`-Chats sind in Liste, Detail, Turns und neuen Context-Versionen bereits unsichtbar bzw. gesperrt), `POST/GET /chats/{chat_id}/turns`, das vollständige `GET /chats/{chat_id}/turns/{turn_id}` sowie `POST /chats/{chat_id}/turns/{turn_id}/context` für eine idempotente autoritative Context-Version. Seit 2026-10-21 hält `PUT /chats/{chat_id}/turns/{turn_id}/task-checks` (`{checked: [int]}`, Positionen 0–199, höchstens 200, sonst 422; UID-Budget `task_checks` 60) die angehakten Checklisten-Kästchen einer Antwort: `ChatStore.set_task_checks` ersetzt in einer Transaktion (Account-Tombstone, lebender Chat, Turn `completed`, sonst 404/409) das Feld `task_checks` am Turn, ohne `updated_at` von Chat oder Turn zu bewegen (die Chatliste ordnet sich nicht um); `turn_detail` reicht das Feld an Turn-Detail und Konversationsseiten durch (`static/js/task-checks.js`). Das UID-Budget `build_context` liegt ausschließlich auf diesem POST, nicht auf dem Turn-GET. Listen sind begrenzt und mit selbstenthaltenden, UID-/Ressourcen-gebundenen HMAC-Cursors paginiert (`updated_at` + Dokument-ID für Chats, `position` + Dokument-ID für Turns); Cursor-Dokumente werden nicht erneut als veränderliche Seitengrenze gelesen. Create-Chat serialisiert das Owner-Limit über `chat_state/quota`, Create-Turn ist über `client_request_id` idempotent. `ChatStore.complete_turn`/`fail_turn` lesen Chat, Turn und Account-Tombstone in derselben Transaktion und akzeptieren ausschließlich einen weiterhin `active` Chat; eine nach dem `deleting`-Marker eintreffende Completion kann deshalb keine Modellantwort-Waisen erzeugen. Completion bleibt per Payload-Fingerprint idempotent. Es gibt bewusst keinen öffentlichen Completion-/Fail-Write-Endpoint. Alle `/chats`-Antworten erhalten über die Security-Middleware `private, no-store`. Bei einer aktiven Fortsetzung erzeugt der Browser den pending Turn nach `/prepare` vor Context und Fan-out; Turn 1 entsteht erst bei der Consensus-Anforderung. Consensus-Turns werden serverseitig über `/consensus`, Agent-Turns über `/agent` finalisiert. |
| `client_errors.py` | Nimmt unter `POST /api/client-errors` ausschließlich same-origin, größenbegrenzte kritische Browsermeldungen an (5/min pro IP). Freitext, Stack, konkrete IDs/Slugs und Providerdetails werden verworfen; nur allowgelistete Typ-/Phasenkategorien, eine abstrahierte Route und bei echten Skript-/Stylesheet-Ladefehlern eine grobe Ressourcenklasse (`app_bundle`, `static_asset`, `jsdelivr_dependency`, `firebase_dependency`, `same_origin_resource`, `unknown_resource`) erreichen den nicht-blockierenden Telegram-Alert. Runtime-Fehler liefern zusätzlich Bundle-Koordinaten (Ort + bis zu fünf `[bundle, zeile, spalte]`-Frames), die über `static/dist/<bundle>.map` auf `static/js/…:zeile:spalte` aufgelöst werden, den Namen des laufenden App-Bundles und nur bei `TypeError`/`ReferenceError`/`RangeError`/`SyntaxError` die entschärfte Message (lange Literale → „…“, URLs/Mails/Secrets raus, max. 200 Zeichen). Der Endpoint liefert keine Konfigurationsdetails zurück. |
| `auth.py` | `/register`, `/confirm-registration` (setzt nach verifiziertem Login zusätzlich eine kurzlebige HttpOnly-Session für private servergerenderte Seiten), `DELETE /auth/session` (lokales Logout-Cleanup). `/register` gibt für Neuanlage, Bestand und Create-Race exakt `{"status":"check_inbox"}` zurück, nie UID/E-Mail/Custom-Token. Unbekannte Adressen erhalten ein serverseitig zufälliges, dem anonymen Aufrufer unbekanntes Übergangspasswort; neue und bestehende Adressen durchlaufen danach denselben Mailbox-Setup-Pfad: Der Admin-SDK-Reset-Link (`continueUrl = {PUBLIC_SITE_URL}/app?setup=1`, damit Firebases „Passwort gespeichert“-Seite zurück in den vorausgefüllten Login führt) geht in einer EIGENEN SMTP-Mail raus (`registration.send_own_setup_email` → `mailer.build_account_setup_message` „Finish setting up …“ bzw. für Konten mit mindestens einem Login `build_existing_account_message` „You already have an account“ mit Login-Knopf + optionalem Reset; „Send the link again“ vor dem ersten Login bekommt wieder die Setup-Mail, `needs_password_setup`). Grund: Firebases Vorlage sagt „Reset your password“ und ist in diesem Projekt gesperrt. Ohne SMTP oder bei Fehlern geht wie früher Firebases `PASSWORD_RESET`-Mail raus (lehnt Firebase die Continue-URL mit 400 ab, ohne sie). Die HTTP-Antwort bleibt in allen Fällen identisch. Neben dem IP-Limit (3/min) gehen pro Adresse höchstens 5 Setup-Mails je Stunde raus (prozesslokal über `api_uid_limiter`, Schlüssel = SHA-256 der Adresse); darüber antwortet `/register` gleich und versendet nichts, damit niemand über viele IPs ein fremdes Postfach flutet. Der Browser versucht keinen Login mit den eingesendeten Legacy-Credentials. Nur ein tatsächlich neues Konto löst den PII-freien Telegram-Admin-Alert aus. `/confirm-registration` prüft Revocation live und erkennt damit auch gerade neu angelegte Google-Konten serverseitig; es läuft bei jedem Login und Seitenaufruf und ist deshalb nur gegen Fluten begrenzt (30/min pro IP). |
| `firebase_auth_proxy.py` | Same-Origin-Proxy für Firebases Sign-in-Helfer: `GET/HEAD/POST /__/auth/*` und `GET /__/firebase/init.json` werden transparent an `https://<FIREBASE_PROJECT_ID>.firebaseapp.com` (überschreibbar per `FIREBASE_AUTH_PROXY_UPSTREAM`) weitergereicht (Firebase „redirect best practices“, Proxy-Option). Weitergereicht werden nur Request-Zeile, Content-Negotiation-Header und der Handler-Body, nie Cookies/Authorization; zurück nur Inhalts-/Cache-Header, kein `Set-Cookie`. `CustomSecurityMiddleware` lässt auf diesen Pfaden die App-CSP weg und setzt `X-Frame-Options: SAMEORIGIN` (das `/__/auth/iframe` rahmt die App selbst). Wirksam erst, wenn `FIREBASE_AUTH_DOMAIN` den App-Host nennt (siehe §7). Ohne Projekt-ID 404, Upstream-Fehler neutral 502. Unter `/__/auth/` nur schlichte Helfernamen (Segmente aus `[A-Za-z0-9_.-]`, kein `.`/`..`), sonst 404: Der Server dekodiert `%2F`, httpx löst Punkt-Segmente auf, `..%2F` holte sonst jede Seite der Hosting-Site ohne CSP. |
| `users.py` | `/user_status`, `/usage` (kann die Kontoprüfung nicht gelesen werden – `AuthenticationUnavailable` –, antworten beide 503 mit `Retry-After`, nie 401: der Browser fragt dann nach, statt Agent für die Sitzung abzuschalten), `/usage/run/release`, `GET`/`PUT /api/my/memory` sowie `POST /api/my/memory/edit|undo` (User-Memory samt explizitem, revisioniertem Luna-Patch, siehe §3), `POST`/`DELETE /api/my/memory/items` und `POST /api/my/memory/changes/{change_id}/undo` (gespeicherte Einzel-Erinnerungen, siehe §3 „Agent-Memory“), `GET`/`PATCH /api/my/settings` (Kontoeinstellungen, siehe §4 „Kontoeinstellungen“), `/delete_account`, `/track-interest`. `/delete_account` legt vor jeder Löschung einen persistenten, fail-closed Auftrag über `FirestoreAccountDeletion` an. Die idempotente Kaskade umfasst API-Zugang/Telegram, alle Nutzer-Subcollections, Chats, Waitlist/Feedback, Pending Results, Persistence-Guards/Votes, Watches/Briefs, Follow-Challenges/E-Mail-Follows, eigene Shares über deren bestehende Hard-Delete-Kaskade, Profil und Firebase Auth. Jeder Bereich wird separat quittiert und bei Fehlern vom fünfminütigen Maintenance-Loop erneut versucht; bis dahin lautet die Antwort ehrlich `202 cleanup_pending`, erst der vollständige Abschluss ergibt 200. Owner-gebundene Create/Update/Delete-Transaktionen lesen den Account-Tombstone als ersten Teil derselben Mutation; nur interne Cleanup-Kaskaden verwenden explizite Bypässe. Dadurch können bereits authentifizierte, verspätete Requests keinen zuvor quittierten Bereich neu befüllen. `/track-interest` ist der idempotente Pro-Beta-Zugangsrequest (ein Pending-Dokument pro UID, kein Billing); aktive Pro-Konten werden abgewiesen. **Seit 2026-07-25 ruft die App diesen Endpunkt nicht mehr auf** — es wird nichts mehr angeboten, das man anfragen könnte; der Endpunkt bleibt nur bestehen, damit vorhandene Waitlist-Dokumente nicht verwaisen. |
| `bookmarks.py` | `GET /bookmarks` liefert ausschließlich kompakte Metadaten, standardmäßig 30 Einträge und einen opaken Cursor; seit 2026-10-16 liest die Liste per Projektions-Query nur `query`, `title`, `title_source`, `mode`, `timestamp`, `pinned`, `pinned_at` und `list_summary` (statt ganzer Dokumente mit allen Antworten, bis 750 kB, Audit C4). Seit 2026-10-22 heftet `PATCH /bookmarks/{id}/pin` (`{pinned: bool}`, strikt) einen Chat oben an: `persistence_guard.write_bookmark` merged `pinned: true` + `pinned_at` (bzw. `false`/`null`), legt nie ein gelöschtes Bookmark neu an (404) und übersteht wie der Name jeden späteren Save; die erste Seite von `GET /bookmarks` (ohne Cursor) bringt zusätzlich `pinned` mit, alle angehefteten Chats (Gleichheitsfilter `pinned == true`, automatischer Einzelfeld-Index, höchstens `MAX_PINNED_BOOKMARKS` = 50, neuester Pin zuerst), damit ein alter angehefteter Chat nicht erst auf Seite fünf kommt; scheitert diese Zusatzabfrage, kommt die Seite ohne sie. `list_summary` (`has_consensus`, `model_count`, `source_count`, `attachment_count`) schreibt `persistence_guard.write_bookmark` bei JEDEM Save neu aus dem zusammengeführten Dokument; ältere Bookmarks ohne gültige Summary liest die Liste weiterhin voll (`get_all`, nur diese Zeilen), bis `scripts/backfill_bookmark_list_summary.py --apply` sie nachträgt. Neue Listenfelder brauchen deshalb einen Eintrag in `_BOOKMARK_LIST_FIELDS`; `GET /bookmarks/{id}` liefert owner-geschützt den Vollinhalt. Sidebar-Name: `title` ist die erste Frage (`query` die letzte); seit 2026-10-03 benennt `POST /bookmarks/{id}/title` die Unterhaltung einmalig ChatGPT-artig mit 2–6 Wörtern (`app/services/chat_titles.py`: ein strukturierter Call über `query_engine_json` mit dem Chat-Memory-Modell der ersten verfügbaren Familie, Gemini zuerst, auf Betreiberkosten; MOCK_LLM liefert `Topic: …`; höchstens `BOOKMARK_TITLES_PER_HOUR` = 30 Modellaufrufe pro Konto und Stunde, darüber `skipped`). Der Titel landet zuerst auf dem Chat-Dokument (Agent- und Follow-up-Saves kopieren dessen `title`), dann mit `title_source: "generated"` auf dem Bookmark; `persistence_guard.write_bookmark` verwirft in derselben Transaktion jedes spätere `title` ohne `title_source`, damit Modell-/Consensus-Saves desselben Laufs den Namen nicht zurücksetzen. Scheitert der Call, bleibt die Frage der Name (`status: "skipped"`, nie ein Fehler); fehlende Bookmarks werden nicht neu angelegt. Listenmetadaten tragen `title_source`. Auf dieselbe Art sagt seit 2026-10-16 `POST /api/my/starter-questions` die Beispielfragen eines leeren neuen Chats voraus (`app/services/starter_questions.py`): Projektions-Query `select(["title", "query"])` der neuesten 12 Bookmarks (nie die Antworten), ab 3 Chats ein strukturierter Call mit demselben Modell wie die Titel (Namen + letzte Frage als Daten, Datum im Prompt), Rückgabe höchstens drei `{label, question}` (Wiederholungen schon gestellter Fragen, Labels über 40 Zeichen und weniger als zwei brauchbare verworfen); `STARTER_PREDICTIONS_PER_HOUR` = 12 pro Konto und Stunde, geprüft vor dem Read; jedes Scheitern ist `status: "skipped"`. MOCK_LLM liefert `More on …?`. Chat-Bookmarks referenzieren additiv `chat_id`/letzte `turn_id`; `GET /bookmarks/{id}/conversation` paginiert dafür die vollständigen owner-gebundenen completed Turns aus `ChatStore`, statt den wachsenden Transcript in ein Bookmark-Dokument zu kopieren; der Normalpfad läuft über `ChatStore.list_turn_details` (Chat einmal pro Seite geprüft; seit 2026-10-16 holt `_page_model_answers` die Modellantworten aller completed Turns der Seite gesammelt per `get_all` über die aus `included_models` bekannten Dokument-IDs, je 100 Dokumente ein Aufruf, Audit C6; pending/failed Turns lesen keine Antworten, nur completed Turns ohne `included_models` behalten die Query pro Turn) und benötigt damit meist 3 SDK-Aufrufe pro Seite statt `2 + N`. Abgerechnet werden weiterhin Dokument-Reads: Chat + gelesene Turn-Dokumente (inklusive Pagination-Sentinel) + alle zurückgegebenen Antwortdokumente; eine Query ist nicht ein einzelner Dokument-Read. Scheitert nur dieser optimierte Collection-Read, fällt der Endpoint korrektheitshalber auf `list_turns` + owner-gebundene Turn-Details zurück, statt den Browser auf zwei Bookmark-Snapshots zu reduzieren. Der Endpunkt ist bewusst ein synchrones `def`, damit die blockierenden Reads im Threadpool statt auf dem Event-Loop laufen. `/bookmark` (POST/DELETE), `/bookmark/consensus` sowie `POST /bookmark/consensus/share-result` erhalten Speichern, Löschen und die sichere Share-/Watch-Rehydration. Consensus-Inhalte werden aus einem owner-gebundenen Pending Result oder completed Turn serverseitig materialisiert, nicht aus frei behaupteten Clientfeldern; ein neuer Share-Snapshot eines Bookmarks entsteht ausschließlich aus dessen completed Turn (`_completed_turn_payload`, Abschnitt „Sharing“), weil `POST /bookmark` `query` und `sources` weiterhin überschreiben darf; die alten, ignorierten Client-Kopien bleiben für gecachte Clients im Schema, werden aber nicht mehr formvalidiert und können den autoritativen Save daher nicht mit 422 blockieren. Quellenlisten werden nicht nach Anzahl gekürzt; die bestehenden Dokument- und Request-Bytebudgets begrenzen den Save ausdrücklich. `persist_authoritative_consensus_bookmark` ist der gemeinsame Writer für den primären `/consensus`-Abschluss und den idempotenten `/bookmark/consensus`-Fallback. Der breite slowapi-IP-Schutz sitzt vor der Tokenprüfung; die eigentlichen Modell- und Consensus-Save-Budgets gelten danach pro UID, damit der interne Preset-Fan-out nicht mit fremden Nutzern an einem Proxy-/NAT-Bucket konkurriert. Persistent gelten höchstens 500 Bookmarks, 750 kB je Dokument und 25 MB geschätztes Gesamtbudget pro UID. Die Bookmark-Grenze ist nur Netz unter dem Chat-Limit (`MAX_CHATS_PER_OWNER`, vor dem Lauf): sie greift erst nach dem bezahlten Lauf und liegt deshalb mindestens beim Doppelten (Test). Lehnt sie den Agent-Abschluss ab, meldet `/agent` „Your saved chats are full …“ (Code `bookmark_count_limit`/`bookmark_storage_limit`, `recoverable`, Recover → 409 statt 500); nach dem Freiräumen holt „Recover saved answer“ den Eintrag nach. Die App zeigt die `bookmark_*`-Codes (auch `bookmark_unavailable`) immer, selbst unter einer geprüften Antwort (`agent-chat.js` failureNotice); das Chat-Limit erscheint vor dem Lauf als „Message not sent. You've reached the maximum number of saved chats …“, der Entwurf bleibt im Feld. `DELETE /bookmark` liest die Chat-Bindung und legt **vor** dem Entfernen des Bookmarks per `ChatStore.request_chat_deletion` in einer Transaktion Tombstone (`status=deleting`), einmaligen Zählerabzug und einen dauerhaften Auftrag `chat_deletion_jobs/{sha256(uid:chat)[:40]}` an; erst danach wird das Bookmark gelöscht und `run_chat_deletion` versucht die Kaskade sofort. Scheitert sie (auch zwischen zwei Batches) oder stirbt der Prozess, bleibt der Auftrag mit `attempts`, `last_error` (nur Kategorie) und Backoff (`next_attempt_at`, 1 min bis 6 h) sichtbar und `resume_chat_deletions` im stündlichen Retention-Loop beendet ihn; quittiert wird erst nach vollständiger Kaskade. Kann der Auftrag nicht angelegt werden, bleibt das Bookmark bestehen und die Antwort ist 500 (nichts gelöscht, erneut versuchbar). Saves akzeptieren eine validierte stabile `bookmarkId`, sodass alle Turns einer laufenden Unterhaltung dasselbe Sidebar-Bookmark aktualisieren; Legacy-Saves ohne ID bleiben fragebasiert. `previous_question`/`previous_turn` bleiben als kompatibler Ein-Turn-Fallback für alte Bookmarks ohne Chat-Bindung erhalten. Alle Bookmark-Antworten sind wie `/chats` `private, no-store`. Die Save-Endpunkte liefern weiterhin den zusammengeführten Datensatz zurück; der Client reduziert ihn sofort auf Listenmetadaten und hält höchstens das geöffnete Detail im Cache. Der seltene Browser-Fallback sendet nur IDs plus kleine Legacy-Texte, nutzt `keepalive`, wiederholt Netz-/408-/425-/429-/5xx-Fehler begrenzt und zeigt einen endgültigen Fehler dedupliziert verständlich an. |
| `share.py` | `/api/share` (POST), `/api/share/{id}` (DELETE), `/api/my/shares` (neueste zuerst, in Firestore sortiert über Index `shares(owner_uid, created_at desc)`, `?cursor=`, Antwort mit `has_more`/`next_cursor`; der Dialog zeigt einen Hinweis, wenn ältere Links fehlen), `/api/share/{id}/report`, öffentliche Seite `/s/{slug_id}` mit Vorschaukarte `/s/{slug_id}/og.png` (Frage, Agreement, Modell-/Widerspruchszahl, Antwortdatum; für Watches seit 2026-10-20 „Watch · <Kopfzeile der Seite>“ und Modellzahl ohne Score), `/questions` (Watch-Zeilen mit der Kopfzeile ihrer Seite), `sitemap-shares.xml`. |
| `watch.py` | Consensus Watch: `/api/watch` (POST), `/api/watch/goal-suggestions` (POST, bis zu drei beobachtbare Ziele zur Frage über einen Judge-Call auf Betreiberkosten, 6/min pro IP und `GOAL_SUGGESTIONS_PER_HOUR` = 20 pro Konto und Stunde, darüber `{"status": "limited", "goals": []}`; ein Fehler liefert eine leere Liste), `/api/my/watches` (inkl. Original-Baseline-Score, kompakter History mit Drift-Signal je Watch, `resolution`, `last_probe` und autoritativer Plan-/Active-/Resolved-Metadaten für die UI), `/api/watch/{id}` (PATCH/DELETE; PATCH auch `requirements` = „Details that matter“ und `reject_match`; `status=active` auf einer abgeschlossenen Watch braucht ein neues oder leeres Ziel, neue Details oder `reject_match: true` = „Not what I wanted“, siehe [watch-evidence-model.md](watch-evidence-model.md) „Details und abgelehnte Treffer“), `/api/watch/{id}/image/{token}` (GET ohne Login, 60/min: die gespeicherte Watch-Vorschau aus `watch_images`, nur mit passendem Inhalts-Token, `Cache-Control: private` 30 Tage; siehe §4 „Watch-Bild“), `/api/watch/{id}/image` (DELETE, Owner: Bild entfernen, danach wird nie wieder eins gesucht), Morning-Brief-Einstellungen `/api/my/watch-brief` (GET/PATCH), nutzergebundene Telegram-Verbindung `/api/my/telegram` (GET/DELETE), `/api/my/telegram/link|test` (POST) und der per Secret-Header geschützte `/api/telegram/webhook`; außerdem öffentliche, HMAC-signierte Mail-Links `/watch/unsubscribe`, `/watch/resume`, `/watch/brief/unsubscribe` und `/watch/follow/confirm|unsubscribe` (GET prüft nur den Token und fragt per Button, erst der POST auf dieselbe URL handelt; Seiten aus `templates/notice.html`, siehe §4 „Links in Mails“). Fehler kommen als `{error, code, …details}` (`WatchError.details`, z. B. `already_watched` mit `watch_id`; `limit_reached` ist die Plan-Grenze, eine Drosselung ist immer `rate_limited`). PATCH nimmt auch `visibility` (`private`/`public`, gleiche Prüfung wie beim Anlegen; ändert Seite und Watch in einer Transaktion, privat heißt raus aus dem Google-Index samt Anfrage; Follower-Mails ruhen, solange die Seite privat ist). `/api/my/watches` liefert je Watch die volle `question` sowie `checking` (Check läuft, Lease aktiv) und `due` (aktiv, `next_run_at` erreicht). |
| `topics.py` | Eigenständige öffentliche Topic-Ticker: Hub `/topics`, versionierte Detailseite `/topics/{slug}` (unbekannter Slug: HTML-404 für Browser, JSON für Skripte; `?version=<run_id>`; seit 2026-10-15 aus denselben Teilen wie die Watch-Seiten gebaut, siehe §4 „Kuratierte Topics“), `/api/topics/{topic_id}/image/{token}` (GET ohne Login, 60/min: das Topic-Bild aus `topic_images`, nur mit passendem Inhalts-Token, öffentlich 30 Tage cachebar), `/topics/{slug}/og.png` (GET ohne Login, 60/min: Vorschaukarte mit Seitentitel, Modellzahl und letzter Prüfung aus `og_image.card_png`; 404 wie die Seite für archivierte, unveröffentlichte und unbekannte Topics; eine Stunde cachebar, steht auch als `image` im Article-JSON-LD), `sitemap-topics.xml`, Double-Opt-in-Follow unter `/api/topics/{slug}/follow` + `/topic-follow/confirm|unsubscribe` (GET fragt, POST handelt wie bei den Watch-Links); der Versand-Claim ist persistent gehasht und besitzt Resend-, Empfänger- und globales Stundenbudget. Der Favicon-Proxy beantwortet Cache-Treffer ohne Limit (eine geteilte Seite braucht ~13 Domains, Apple-Audit I7); nur ein Abruf bei Google zählt, `FAVICON_LOOKUPS_PER_MINUTE` = 60 je IP (prozesslokal über `api_uid_limiter`; dessen Aufräumlauf über 4.096 Schlüssel nutzt das Fenster jedes Schlüssels und läuft höchstens alle 5 s, viele Favicon-Besucher setzen so keine Stundenlimits zurück), darüber kommt der Globus mit `no-store` statt eines 429. Dazu acht parallele Requests, ein eigener Vierer-Executor, zwei Sekunden Upstream-Zeit sowie ein 2.000-Einträge-LRU einschließlich 24-h-Negativcache. Angefragt wird `sz=128`; ein Icon unter `favicons.MIN_ICON_PX` = 64 px gilt als keins (Globus statt eines unscharfen Logos bei 20 px × DPR 3, Apple-Audit I13). Admin-CRUD liegt unter `/api/admin/topics`. Ein leeres `POST /api/admin/topics/{id}/runs` führt den konfigurierten Research-/Consensus-Run aus; ein Payload mit `consensus_md` bleibt als expliziter Legacy-Import verfügbar. |
| `api_v1.py` | Nutzergebundene asynchrone Consensus-API: Run-Start/Status/Löschung unter `/api/v1/consensus/runs`, transaktional idempotentes Publizieren erfolgreicher Runs per `POST .../{run_id}/share`, eigene Share-Liste/-Details/-Widerruf unter `/api/v1/shares` sowie direkte Admin-Indexfreigabe per `PUT /api/v1/shares/{share_id}/indexing`. Der frühere Scheduled Publisher (`GET /api/v1/publisher/config`, Header `X-Consensus-Publisher`, `POST /api/v1/shares/{share_id}/watch`) ist seit 2026-10-04 entfernt (siehe §4 „SEO-Puls“). Auth über gescopte `X-API-Key`s, Run-Idempotenz über den Pflichtheader `Idempotency-Key`; Pydantic-Modelle bilden den Vertrag in `/openapi.json` ab. |

Gemeinsame OpenRouter-URLs/Headers liegen dependency-frei in
`app/core/openrouter_contract.py` (keine Backend-Imports); Engine und
Agent-Usage-Abgleich importieren sie von dort. Credentials bleiben in
`app/services/llm/credentials.py`. Der GitHub-Actions-Publisher
(`scripts/publish_consensus.py`, `publish-consensus.yml`,
`publisher-tests.yml`), der dieses Modul früher mitnutzte, ist seit 2026-10-04
entfernt.

| Router | Zweck (Auswahl an Pfaden) |
|---|---|
| `admin.py` | `/api/admin/shares` (Filter `reported` = `reports_count > 0` nach Report-Anzahl bzw. `all` = neueste zuerst, jeweils in der Firestore-Abfrage vor dem Limit; `cursor`/`limit`, Antwort mit `has_more`/`next_cursor`, UI mit „Load more“), `/api/admin/shares/{id}/moderate`, `DELETE /api/admin/shares/{id}` (sofortiger Hard-Delete inklusive Watch/History/Followern), `/api/admin/models` (GET/POST; enthält auch die validierte `memory_edit`-Konfiguration), API-Key-Ausgabe/-Liste/-Widerruf unter `/api/admin/api-keys`, Kontostufen unter `/api/admin/account-tier` (GET Lookup per UID/E-Mail, PUT setzen) und `/api/admin/account-tiers` (Liste + Audit), `/api/admin/watches` (cursor-paginierte Diagnose-Liste mit `limit`, `next_cursor`, `has_more`; im API-Tab zusätzlich als gefilterte Liste „Former Publisher pages“ der Legacy-Publisher-Watches), `/api/admin/watches/{id}/run` (fällig stellen + Scheduler sofort wecken), `POST /api/admin/watches/{id}/status` (`{status: active|paused}` über `watch_service.set_watch_status_admin`; „Pause watch“/„Resume watch“/„Pause all watches“ in derselben Liste), `/api/admin/watches/test-email` (SMTP-Test an die verifizierte Admin-Adresse), SEO-Puls unter `GET /api/admin/seo` (Status aus einem Dokument), `PUT /api/admin/seo/config` (`{enabled}`), `POST /api/admin/seo/run` (erzwungener Lauf, 6/Stunde, 409 bei laufendem Lease) und `POST /api/admin/seo/shares/{share_id}/keep` (wieder indexieren + von späteren Sweeps ausnehmen; siehe §4 „SEO-Puls“; die beiden Watch-Listen teilen sich beim Laden einen `/api/admin/watches`-Request), `/api/admin/benchmark/runs` (Liste) + `/api/admin/benchmark/runs/{run_id}` (Detail, liest Firestore-publizierte kompakte Benchmark-Reports mit lokalem Disk-Fallback über `benchmark/report_reader.py`). Alle hinter `is_user_admin`. |

**Zentrale Templates** (`templates/`, gerendert mit `Jinja2Templates`):
`landing.html` (Marketing), `index.html` (die App — Haupt-Markup; die
Script-/Style-Tags rendert `app/core/assets.py` aus `static/js/bundles.json`),
`admin.html`, `admin_benchmark.html` (Admin-Benchmark-Visualisierung, eigenes
Template + Firebase-Auth-Modul wie `admin.html`), `share.html` (öffentliche
Consensus-Seite), `watch_share.html` (dieselbe Route `/s/…`, sobald die Seite
Watch-Metadaten oder -History hat), `share_unavailable.html`, `notice.html` (Hinweisseite hinter Mail-Links und für ein HTML-429, `app/core/notice_page.py`), plus statische Rechts-/SEO-Seiten
und SEO-Erklärseiten wie `ai-model-comparison.html` / `consensus-engine.html`.
`topics.html` und `topic.html` bilden den öffentlichen Topics-Hub bzw. die
Detailseite; `topic.html` und `watch_share.html` setzen sich seit 2026-10-15 aus
denselben Makros in `templates/partials/check_page.html` zusammen (Kopf mit
Bild, Zustandszeile, Direktlinks, Antwort mit Quellen, Verlauf,
Modellvergleich); die Topic-Redaktion liegt als eigener Tab in
`admin.html` unter `/admin#topics` (`/admin/topics` redirectet dorthin).
Alle öffentlichen HTML-Seiten teilen Navigation und Footer über
`templates/partials/public_nav.html` und `public_footer.html`. Das
Link-Vorschaubild (`og:image`, `twitter:card` `summary_large_image`, 1200 × 630)
kommt seit 2026-10-18 überall aus `templates/partials/og_card.html`, auch für
`/app`: Ohne eigene Karte zeigt eine Seite die Markenkarte der Landing
(`static/og-home-v2.png` mit `asset_url`-Hash; gezeichnet von
`og_image.render_brand_card`, gespeichert mit `scripts/render_brand_card.py`
und danach `scripts/shrink_images.py`), nie das Favicon. Eigene Karten
setzen `og_card_image`/`og_card_alt` vor dem Include (Share-, Watch- und
Topic-Seiten, gerendert von `app/services/og_image.py`). Nur `landing.html`
schreibt dieselben Tags noch selbst aus; `tests/test_og_cards.py` verbietet
eigene `og:image`-Tags neben dem Partial. Das Umami-Snippet
liegt seit 2026-07-31 ebenfalls zentral in `templates/partials/analytics.html`
(einzige Stelle mit der Website-ID) und bringt den Selbst-Ausschluss per
`?notrack=1` mit; die Admin-Templates tracken gar nicht mehr. Seit 2026-08-07
begrenzt `data-domains="consens.io,www.consens.io"` das Tracking auf die
Live-Domain — lokale Server (jeder uvicorn-Port) und Preview-Deploys senden
gar nichts mehr; neue Domains muessen dort eingetragen werden. Seit 2026-10-07
ruft der Tracker vor jedem Send `consensioBeforeSend` (`analytics-opt-out.js`):
Webdriver/Headless senden nichts, `utm_*`/`ref` kommen trotz
`data-exclude-search` zurueck; `/user_status` liefert `is_admin`, worauf die App
den Betreiber-Browser ausschliesst. Die Kern-Events `open_app`, `signup`,
`login`, `ask`, `answer` (Helfer `App.trackAsk`/`App.trackAnswer` in
`app-core.js`, gleich fuer Agent und Pipeline) und die Bedeutung aller
Event-Namen stehen in [`docs/analytics.md`](analytics.md). Die vier Informationsseiten beschreiben automatische
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
rechts der Modell-Chip „6 AIs cross-check ⌄“ wie in /app (seit 2026-10-23
nennt er, was die Vergleichsmodelle tun, keinen Modellnamen); Lippe
`partials/composer_toolbar_mockup.html` mit Reasoning Auto · Attach ·
Modell-Icons, ohne eigenes Fenster um Szene 01). Szene 02 (`#agent-mode`, `.lp-agent`) baut seit
2026-10-02 einen Agent-Turn so nach, wie `agent-activity.js`/`agent-review.js`
ihn zeichnen: Uhr „Working for …s“ → „Thought for 24s“, Agent-Notizen,
„Comparing perspectives…“ mit sechs nacheinander fertig werdenden Modell-Icons,
eine Live-Statuszeile (Writing answer… / Checking the answer…), gestreamte
Antwort, danach Markierungen und Evidenzzeile („43/100 agreement ·
Contradictions 2 · Answers 6“); keine Ladebalken mehr. Treiber
`landing-scenes.js` (`buildRunScene`, Standbild bei reduced motion = fertiger
Turn über `render.still`). Seit 2026-10-20 (Apple-Audit I1) faltet sich der Log
zum Abschluss in die Uhrzeile (`.lp-agent-log.is-folded`, Höhenübergang über
`.lp-agent-log-items`, statt `hidden`), der Platz für den höchsten Zustand ist am
Platzhalter um die Karte reserviert (nicht in der Karte), das Vergleichs-Label
hat die Breite seiner längeren Fassung; gemessen wird mit `.is-measuring`
(Übergänge aus). In `/app` faltet der Aktivitätslog vermutlich genauso hart
(gemeldet, nicht geändert). Szene 03 und Watch sprechen von „answer“ statt
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
von `landing.css` und `public-pages.css`); ab derselben Breite verschwinden
die Textlinks (eine Grenze für beide Seitenfamilien). Das Menü ist ein
rahmenloses Zwei-Strich-Zeichen rechts außen hinter dem CTA (`order: 1`),
offen kreuzen sich die Striche zum X; der CTA bleibt die einzige Fläche.
Seit 2026-10-20 trägt die Leiste auf allen öffentlichen Seiten denselben CTA
„Open app“ (keine Seitenvarianten mehr, nur `public_nav_event`) und lädt
`static/js/public-nav.js`: Das Menü schließt bei Tipp daneben, Link, Escape
und echtem Scrollen und geht mit derselben Bewegung, mit der es kommt
(`.is-closing`); `html.is-scroll-smooth` (sanftes Scrollen) wird erst nach
`load` gesetzt, damit `/#watch` von einer anderen Seite direkt springt statt
8.000 px zu gleiten; Anker landen unter der Leiste (`scroll-padding-top:
54px`), eine späte Verschiebung bis zum ersten Eingriff wird ausgeglichen; auf
der Landing markiert die Leiste „Watches“, solange `#watch` die Mitte des
Bildschirms hält. Alle öffentlichen Seiten stehen auf EINEM Raster
(`--page-width`/`--page-gutter` in `public-tokens.css`, 20 px, unter 700 px
16 px; Watch-/Topic-Spalte 860 px auf derselben linken Kante) und einem
Material: Panels (`.legal-panel`, `.notice`) sind Abschnitte mit Haarlinie, keine
grauen Kästen mit Schiene; `body { overflow-x: clip }` als Netz gegen
seitliches Schwimmen bei 320 px. Höhen im Seitenfluss der Landing sind `svh`,
nie `dvh` (Safari-Leiste).
Der Landing-Hero
zeigt ein klickbares Input-Feld (Look des /app-Inputs, "Try the demo"-Button,
Provider-Chips darunter). Seit 2026-10-04 öffnet ein Klick ins Feld die App
(`#heroAskField`, Stretched-Link über `#heroField`, `/app?focus=1`), nur der
Button `#heroDemoButton` startet die Demo (`/app?demo=1`). `?focus=1` setzt
`app-init.js` den Cursor in `#questionInput`, sobald das Konto tippen darf
(`updateQuestionInputAccess`); Gäste sehen das gesperrte Feld mit Login-Zeile;
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
Mockups eine Geschichte erzählen. Die Demo zeigt vor jedem Start das konfigurierte Daily-Preset ueber
`App.previewConsensusPreset('fast')`, einschliesslich aller sechs Familien
und ihrer aktuellen Modelllabels (seit 2026-10-15; vorher Balanced). Eine eigene
Open-Models-/Custom-Wahl wird dabei nur für die Vorführung durch Daily ersetzt. Die sechs redaktionell geschriebenen Demo-Perspektiven werden
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
ist in der öffentlichen Navigation erreichbar. Seit 2026-10-20 spricht das
Beispiel die Sprache der echten Watches (Ziel „Waiting for“, Bewegung mit
Quelle, Telegram-Gliederung, kein Score) und darunter steht „See a live
watch“ – nur, wenn es eine laufende, kuratierte öffentliche Watch gibt
(`share_snapshots.live_watch_path`: aktive, öffentliche Watch, neuester Check,
**nur indexierte Seiten** – dieselbe Menge wie `/questions` und Sitemap; eine
nur per Link öffentliche Seite steht nie auf der Startseite, auch nicht als
Ersatz; 15-min-Cache, Moderation leert ihn, eine Minute Pause nach einem
Lesefehler, `stream(retry=None, timeout=3)`, damit die Landing nie auf
Firestore wartet; `pages.landing_live_watch`). Direkt davor steht seit
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
`consensus-engine.css`. `topics.css` trägt seit 2026-10-15 nur noch die Zeilen des Hubs `/topics`;
die Topic-Detailseite nutzt die `.wp-*`-Regeln der Watch-Seite in
`public-pages.css` (dort auch `.wp-subheading` für die Leitfrage unter dem Titel).
Die gemeinsame Typografie-Grundlage liegt in `static/css/typography.css` und
wird von `variables.css` (App/Admin) sowie `public-tokens.css` (Marketing/Public)
importiert. Sie hostet Inter Variable lokal, seit 2026-10-18 je Schnitt (normal,
kursiv) in drei WOFF2-Teilen mit disjunkter `unicode-range`: `-latin` (Latein,
Latin-1, Satzzeichen und die Symbolblöcke der Oberfläche, ca. 130/145 KB statt
344/379 KB) lädt jede Seite, `-latin-ext` (Akzente jenseits Latin-1,
Vietnamesisch) und `-rest` (Griechisch, Kyrillisch, Sonderzeichen) nur eine
Seite, die eines ihrer Zeichen enthält. Alle Teile behalten jedes
OpenType-Feature und beide Achsen. Erzeugt und geprüft werden sie mit
`scripts/subset_inter_font.py` (`--check`; braucht fonttools + brotli, keine
App-Abhängigkeit) aus den unveränderten Quelldateien `InterVariable[-Italic].woff2`,
die kein Stylesheet mehr lädt. Ein Test verlangt, dass jedes Nicht-ASCII-Zeichen der Oberfläche
(Templates, JS, CSS) im Latein-Teil liegt.
**Schriftladen ohne Tausch (seit 2026-10-20, Apple-Audit B3):** Jeder Teil trägt
die ersten 12 Hex-Stellen seines SHA-256 im Namen
(`InterVariable-latin.<hash>.woff2`; das Skript schreibt Namen und URL in
`typography.css` mit, `--check` prüft sie), `StaticDeliveryMiddleware` liefert
solche Fonts `immutable` (vorher `no-cache`: ein 304 bei jedem Besuch, die
Schrift kam nach dem ersten Bild). Den alten, ungehashten Namen eines Teils
(`InterVariable-latin.woff2`, so in den Bundles von 9cef4a9) beantwortet die
Middleware mit der aktuellen Hash-Datei (`static_delivery.legacy_font_target`,
`no-cache`): ein vor dem Deploy geöffneter Tab lädt kursiv/latin-ext erst beim
ersten solchen Zeichen nach und bekäme sonst eine 404 und die Ersatzschrift
(Zweitprüfung, Schriften; `tests/test_static_delivery.py` prüft jede
Font-URL der behaltenen Bundles). JEDE Seite (`/app` und alle öffentlichen
Templates) bindet als Erstes im `<head>` `partials/font_preload.html` ein; die
URL liest `app/core/assets.font_preload_urls()` aus `typography.css`, damit
Preload und `@font-face` nie auseinanderlaufen. Der aufrechte Latein-Teil hat
`font-display: optional`: gezeichnet wird Inter, wenn sie zum ersten Bild da ist
(Wiederbesuch immer, Erstbesuch fast immer), sonst für diesen Seitenaufruf die
Ersatzschrift – nie beides nacheinander (mit `swap` lag die Landing bei CLS 0,06
bei jedem Besuch). Kursiv, latin-ext und rest bleiben `swap`. `Inter Fallback`
hat zwei Faces: 100–549 gegen Arial (size-adjust 107,06 %), 550–900 gegen Arial
Bold (101,2 %, gemessen gegen Inter 600/700 bei 14–18 px); vorher machte der
Browser fette Überschriften aus dem Normalschnitt breiter als Inter. Gemessen
lokal (gedrosselt 120 ms/8 Mbit und 300 ms/1,6 Mbit, kalt/warm, 1440 und
390 px): CLS beim Laden < 0,01 auf allen öffentlichen Seiten. Die Typografie-Grundlage
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
**Material-Bausteine (seit 2026-10-20, Apple-Audit Welle 2, w2c):** ein zweiter
Block `:root, .dark-mode` in `foundation.css` leitet aus den Themenwerten ab
(auch auf `body.dark-mode` deklariert, sonst erbt der dunkle App-Body die helle
Tinte): `--hover` / `--selected` (Tinten-Waschung `--ink` in `--hover-mix` 6 %
/ `--selected-mix` 10 %, dunkel 4,5 % / 8 %; für Ghost-Knöpfe, Menü- und
Listenzeilen, transparent in Ruhe), `--raise-hover` / `--raise-selected`
(deckend, für Flächen, die in Ruhe `--raise` tragen), `--button-bg-hover`
(gefüllter Knopf, ein Tonschritt Richtung Seite), `--field-focus-border` +
`--field-focus-ring` (der eine Feld-Fokus: Rand dunkelt, 3-px-Hof außen, Feld
behält seine Größe), `--chevron-mask` (das eine Chevron, SVG-Maske, zeigt nach
unten; drehen mit `--chevron-turn`: -90deg rechts, 90deg links, 180deg oben)
und `--file-mask` (Dokument-Glyphe für Dateityp-Plaketten). Dazu die Utility
`.chevron` (1em-Box, `currentColor`, `--chevron-size`); Pseudo-Element-Chevrons
nutzen dieselben drei Zeilen (`background: currentColor` + `mask`). Hover-Regeln
stehen immer in `@media (hover: hover) and (pointer: fine)` (Touch-Vertrag,
§8). Gemessen vorher/nachher
(App + öffentliche CSS ohne Admin): Hover-Hintergründe 67 → 35 verschiedene
Werte (88 × `var(--hover)`), `opacity: 1`-Gegenregeln 41 → 9 (übrig nur
echtes Aufdecken), Hover-Ausblendungen 11 → 3, Schriftgrößen < 12 px 12 → 0,
gedrehte Rand-Chevrons 25 Regeln / 52 Rotationen → 0 (übrig 3 Häkchen),
Schatten 119 → 107 verschiedene Werte; Radien unverändert 36.
**Buttons:** Der gefüllte Standardknopf ist opt-in (`.btn`, Altname `.button`,
`components-input.css`). Die frühere globale `button:not(...)`-Kette mit rund
90 Ausnahmen ist entfernt; ein `<button>` startet neutral. Admin-Seiten
geben klassenlosen Buttons den alten Look in `admin.css`. Seit 2026-10-20
(Apple-Audit G4) ist `.btn` der EINE gefüllte Knopf: 36 px (44 px bei
`pointer: coarse`), `--radius-sm`, flach, ohne Verlauf/Schatten/Anheben, Hover
`--button-bg-hover`, Druck aus `base.css`. Dieselbe Regel trägt die älteren
Primärknöpfe (`.share-primary-btn`, `.btn-pro`, `.auth-primary-action`,
`.memory-edit-submit`, `.watch-nudge-btn`, `.post-demo-login-action`,
`.agent-google-btn.is-primary`, Agent-Fehler-Retry
`.agent-answer-error-actions button:first-child`, `.wd-button.is-primary`,
`.wd-action.is-strong`, `.run-blocked-btn.is-primary`, `.verify-banner-btn`,
`.auth-top-signup`, `#feedbackForm .feedback-submit`); deren eigene Regeln
setzen nur noch Platz (Breite, Abstand). Neuer Code schreibt `class="btn"`.
Die globale `button:hover { opacity: .9 }` ist entfernt (G5). Öffentliche CTAs
(`.nav-cta`, `.button-primary`, `.lp-btn--primary`) bleiben Pillen ihres
Kontexts, heben sich aber nicht mehr an. Die gewählte Option eines Menüs
(`.model-picker-option.is-selected`) steht in voller Tinte ohne eigene Fläche,
Grau heißt „nicht wählbar“ (G6).
`shell.css` gibt Agent-/Consensus-Antworten und gespeicherten Turns denselben
Leserhythmus: 17 px (`--font-size-read`) mit 1,7-facher Zeilenhöhe, Fließtext
höchstens 66 Zeichen breit (Tabellen, Code, Formeln volle Spalte), normale
Laufweite, eigene Absatz-, Listen- und Überschriftenabstände. Seit 2026-10-09
gibt es dort keinen größeren Lead-Absatz und kein `text-wrap: pretty/balance`
mehr: beides setzte im Stream schon gelesene Zeilen neu (Layout-Shift-Audit). Die Regeln für den Consensus-Labelkopf gelten
nur für direkte `h2`-Kinder, nicht für Markdown-Überschriften im Antworttext.
Statusmeldungen, Antwortleser, Codeblöcke und Tabellen behalten ihre eigene Typografie.
`index.html`, `admin.html` und `admin_benchmark.html` enthalten keine Inline-Skripte, Inline-Styles oder
HTML-Eventhandler mehr. Jinja-Konfiguration liegt ausschließlich in escaped
`data-*`-Metadaten und wird von `app-bootstrap.js` beziehungsweise
`admin-config.js` gelesen; `app-dom-events.js` bindet die früheren Inline-
Handler. Die routenspezifische CSP für `/app`, `/app/watches`, `/admin` und alle `/admin/*`-Unterpfade
kommt deshalb bei `script-src` ohne `'unsafe-inline'` aus. Seit 2026-09-29 gilt
das auch für die öffentlichen Topic-Detailseiten `/topics/{slug}` (Review R01):
`topic.html` lädt das Theme per `static/js/public-theme.js`, die mit der
Watch-Seite geteilten Skripte per `static/js/check-page.js` (lange Frage
einklappen, fehlendes Bild/Favicons ausblenden, Quellenliste falten,
`#src-N`/`#watch-run-…`-Sprünge) und das Follow-Formular per
`static/js/topic-page.js`; die Serverantwort wird dort nur per `textContent`
eingesetzt, nie als HTML geparst. Die übrigen
öffentlichen Seiten (einschließlich des Hubs `/topics`) behalten die bisherige
Policy während der weiteren Style-Migration.

---

## 3. Frontend-Architektur

Geladen werden (Reihenfolge ist Vertrag, steht in `static/js/bundles.json`,
siehe §8): zuerst die synchronen `app-text.js` (Formatierer, Fehlertexte,
Glossar; seit 2026-10-20), `app-bootstrap.js`, `app-state.js`,
`auth-session-state.js`, `run-registry.js`, `watch-state.js` und
`error-reporter.js` (Gruppe
`head`, render-blockierend, weil sie den First Paint seeden), dann lokale Vendor-Libs
(`marked`, `DOMPurify`, KaTeX + Auto-Render; alle `defer`, seit 2026-10-15 auch
marked und DOMPurify: kein Head-Skript ruft sie, und deferred Skripte und Module
laufen in Dokumentreihenfolge, also vor `firebase.js` und der `app`-Gruppe), der same-origin
`email-verify.js` als inhaltsadressierte `window.App.emailVerification`-Brücke,
die Gruppe `auth` (deferred) mit den Ebenen-Modulen `motion.js`,
`modal-dialog.js`, `popover.js`, `notices.js`, `confirm-dialog.js`, dem
`auth-bootstrap.js`-Watchdog und `chat-list.js` (Gruppen der Chatliste) vor
`firebase.js` + `demo.js` (ES-Module; der
Login-Dialog öffnet schon beim Auswerten von `firebase.js`), dann deferred
`app-ui.js` und die Feature-Module unter `static/js/` in fester Reihenfolge,
zuletzt `tooltip.js`, `app-init.js` und `app-dom-events.js`.

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
Das hilft nur bei einem echten Seitenaufruf: Ein offenes Fenster (installierte
App, Homescreen-App, tagelang offener Tab) behielt seinen Build über viele
Deploys. Seit 2026-10-15 holt `app-update.js` (unten) neue Deploys selbst.

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
  Provider-Exclude, Settings und Key-Test; ersetzt HTML-Eventattribute. Dazu
  die Sprungmarke `.skip-link` (erster Tab-Stopp in `index.html`, seit
  2026-10-24): im Chat in `#questionInput`, in der Watch-Ansicht auf
  `#watchDashTitle`, sonst auf das unsichtbare `h1#appHeading`.
- **`error-reporter.js`** — lädt vor allen App-Modulen, fängt ungefangene
  Browserfehler, Promise-Rejections und relevante Asset-Ladefehler ab und stellt
  `window.App.reportCriticalError` für explizite Run-Abbrüche bereit. Nur
  Skripte, Stylesheets und explizit mit `data-critical-resource="true"`
  markierte Elemente gelten als alarmwürdig; dekorative Bilder, Quellen- und
  Dokument-Favicons bleiben bei ihren lokalen Fallbacks. Asset-Alarme senden
  eine allowgelistete Ressourcenklasse und für bekannte lokale Assets zusätzlich
  den geprüften Dateinamen (gehashte Bundles, gepinnte Vendor-Libs, Analytics-Opt-out),
  keine URL/Query. Eigene Assets (same-origin) melden seit 2026-10-09 nur, wenn
  ein ungecachter `HEAD`-Request sie ebenfalls nicht bekommt: Headless-Scraper
  blockieren Stylesheets selbst und lösten pro Seite zwei Fehlalarme aus; CDN-
  Ressourcen melden sofort. Gemeldet wird nur eine Server-Antwort ohne `ok`;
  ein `HEAD` ohne Antwort (Netz weg, Reload bricht Download und Probe ab, Alarm
  2026-10-22) meldet seit 2026-10-23 nichts mehr. Client und Server deduplizieren je Asset; unterschiedliche
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
  Seit 2026-10-04 meldet der Reporter `error`-Events ohne Error-Objekt und ohne
  same-origin Datei gar nicht mehr (`isUnattributableError`: cross-origin
  „Script error.“ von Google-Picker/Firebase/Erweiterungen, ResizeObserver-
  Loop-Hinweis); sie ergaben nur leere Alerts ohne Ort.
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
- **`app-text.js`** (seit 2026-10-20, Apple-Audit H1, H8, H9; erstes Skript
  der `head`-Gruppe, reine Funktionen, also auch für `firebase.js` und
  `token-budget.js` jederzeit da) — wie die App schreibt, an einer Stelle:
  - **`App.format`**: eine Locale (`en-US`, die der Oberfläche), nie die des
    Browsers. `date(v, {year: "auto"|true|false, weekday, timeZone})` →
    „Oct 19“ (anderes Jahr: „Oct 19, 2025“), `month(v)` → „October“ (Überschrift
    der Monatsgruppen der Chatliste), `time(v, {timeZone})` → „14:03“
    (24 h wie die Watch-Zeiten), `dateTime` → „Oct 19, 14:03“, `upcoming(v)` →
    „today, 14:30“/„tomorrow, 09:00“/„Friday, 09:00“, `relative(v)` →
    „just now“/„12m ago“/„3h ago“/„yesterday“/„4 days ago“/„on Oct 3“,
    `duration(ms, {minutes})` → „23s“/„3m 7s“/„1h 2m 5s“ bzw. „5h 12m“ (die
    eine Schreibweise für Zeitspannen: „Thought for“, Reset, Agent-Zeilen,
    „Next check in 12m“), `number(n, {digits})` → „48,213“, `count(n, word)`.
    `App.watchFields` (`scheduleText` ausgenommen) setzt darauf auf.
    `tests/test_ui_copy.py` verbietet in `/app` `toLocale*String()` ohne Locale
    und eigene `Intl.*Format` außerhalb von `app-text.js`.
  - **`App.userError(error, {context, fallback})`**: jeder Fehler als Satz mit
    nächstem Schritt, nie die Worte der Engine („Failed to fetch“, „Load
    failed“, „The string did not match the expected pattern.“, „HTTP 503“).
    Offline (`navigator.onLine === false` + Netzfehler) → „You’re offline. …“;
    Netzfehler sonst, kein JSON (Proxy-/Portal-HTML) und nackte 502/503/504 →
    „consens.io can’t be reached right now. …“; `rate_limited`/429 → der
    Satz des Servers bzw. dieselbe Warte-Regel aus `retry_after`; 401 →
    „Your session has ended. Log in again.“; ein Satz des Servers
    (`{error|detail|message, code}`, auch `already_watched`, `limit_reached`)
    oder unserer (`new Error("…")`) bleibt — bei 5xx nur, wenn er einen `code`
    trägt oder wie ein Satz endet (`.`/`?`/`!`/`…`); Log-Etiketten wie „Error
    updating watch“ oder „Chat storage error“ werden „Something went wrong on
    our side. …“ (Nachprüfung 2026-10-21); Programmfehler (TypeError …) →
    `fallback`; `AbortError` → „“. `context: "send"` endet mit „Your message
    is back in the box.“ (die Nachricht ging zurück ins Feld), weitere
    Kontexte `load|save|upload|delete` liefern den Fallback.
    `App.userError.kind(error)` → `offline|unreachable|timeout|rate_limited|
    session|message|server|status|unknown|aborted`.
  - **`App.readJson(response)`**: Body als JSON ohne Parse-Fehler der Engine
    (leer → `{}`; kein JSON bei 2xx → Fehler `unreadable`, bei 4xx/5xx → `{}`).
    **`App.httpError(response, data, fallback)`**: Ablehnung als `Error`
    (`name "HttpError"`, `status`, `code`, `retryAfter`, `data`,
    `serverMessage`, `unreadable`). Muster: `const data = await
    App.readJson(response); if (!response.ok) throw App.httpError(response,
    data);` und beim Anzeigen `App.userError(error, {fallback})` über
    `App.toast`/`App.composerNotice`/`App.watchFields.setError`.
    **`App.errorFields(data)`** (seit 2026-10-21): die Felder einer Ablehnung
    flach, gleich in welcher Form der Server sie schickt — vereinbart ist
    `{error: "<Satz>", code, retry_after}`, `main.py` verpackt ein Detail-
    Objekt einer Route aber als `{error: {error, error_code, …}}`, FastAPI als
    `{detail: {…}}`. `error` ist danach der Satz, Felder oben schlagen
    verschachtelte. `httpError`, `userError`, `usageLimit.isLimitError`/`show`,
    `query-send.js` (`unwrapApiError`), `agent-chat.js` (`failRun`) und der
    Resolve-Teaser lesen darüber; sonst erkannte Consensus/Compare ein leeres
    Tageskontingent nicht (Karte fehlte, „You don’t have access to this.“).
    `streamSSERequest` gibt keinen HTML-Body mehr als `data.error` weiter.
    `request-deadline.js` wirft bei Zeitüberschreitung einen `TimeoutError`.
  - **`App.words`**: das Glossar (Apple-Audit H9), ein Wort je Zustand:
    die Prüfung heißt „Answer check“ (laufend „Checking the answer…“, fertig
    „Checked“, teilweise „Partly checked“, sonst „Answer check pending|failed|
    stopped|off“, „Not checked“), ein Lauf „Working“/„Failed“/„Stopped“
    (auch Tab-Titel, Chatzeile, Stepper „Answer check“), Verbrauch heißt
    „allowance“.
- **`app-core.js`** — MUSS zuerst laden. Definiert `window.App`-Bus, `modelPrefs`
  (zentrales Mapping Provider→DOM-IDs), `modelAcceptsAttachments(pref, modelId)`
  (immer das gewaehlte Modell; der Reasoning-Schalter tauscht keins), gemeinsame Helfer
  (`getModelOptionLabel`, `getSelectedModelCount`, `setAppTitle`, `showPopup`,
  `trackAppEvent`, `exitHeroMode`, `scrollBehavior`, seit 2026-10-20
  `askToLogIn(lead, {trigger, source})`: ein Gast an einer Tür, die ein
  Konto braucht, bekommt den Login-Dialog mit einer Zeile, wofür — Modellwahl,
  Reasoning, Anhang, Gmail & Calendar, Drive, Teilen, Resolve, Senden mit
  Dateien, Settings; ohne Firebase sagt es die Hinweiszeile, Apple-Audit H2,
  H3) sowie den zentralen
  `window.App.renderUsageDisplay(data, owner)`-Eingang: reicht das
  `token_budget` einer API-Antwort (auch aus Fehler-Details) an
  `App.tokenBudget` weiter; Antworten ohne das Feld (eigene Keys) ändern nichts.
  Jeder `RunContext.usage` hält seinen logischen
  Idempotency-Key, geteilt von `/prepare`, allen `/ask_*` und `/consensus` genau
  dieses Laufs; `window.App.usageRun` ist nur die Legacy-/UI-Brücke.
  `setAppTitle` setzt den Standardtitel oder
  einen gekürzten, fragebezogenen Browser-Tab-Titel; `exitHeroMode` schaltet
  Antwortbereich und Input vom zentrierten Leerzustand in den Laufzustand.
  `scrollBehavior()` liefert `"smooth"` oder bei `prefers-reduced-motion:
  reduce` `"auto"` (pro Aufruf gelesen); jedes `scrollTo`/`scrollIntoView` mit
  `behavior` in `/app` nimmt den Wert von hier (Audit F15,
  `tests/js/reduced-motion-and-head.test.mjs` verbietet ein hartes `"smooth"`).
- **`modal-dialog.js`** (`window.App.modalDialog`, seit 2026-10-15; seit
  2026-10-20 in der `auth`-Gruppe vor `firebase.js`) — Helfer für **jedes**
  modale Fenster der App, alle native `<dialog class="modal">`: Settings, Help
  (`app-ui.js`), Feedback (`feedback-dialog.js`), Login (`firebase.js`,
  `auth-bootstrap.js`, `demo.js`), Share/Watch (`share-dialog.js`, `watch.js`),
  der Early-Access-Hinweis (`feature-access.js`), die Anhang-Vorschau
  (`attachments.js`) und `App.confirm`. `bind(dialog, {keepOpen?, onClose?})`,
  `open(dialog, {opener?, focus?})`, `close(dialog)`, `isOpen(dialog)`. `open`
  nutzt `showModal()` (Top-Layer, Hintergrund inert, Stapeln ohne z-index),
  schließt offene Popover (`App.popover.closeAll`), merkt den Auslöser
  (aktives Element, sonst `opener`, weil Safari geklickte Buttons nicht
  fokussiert; liegt das aktive Element in einem Popover oder hat gerade ein
  Popover geschlossen, ist es dessen Auslöser — ein Dialog aus einem Menü
  gibt den Fokus an den Menüknopf zurück, nicht ins Leere) und setzt den Fokus auf `focus` bzw. `[autofocus]`; Tab bleibt
  im Dialog (letztes → erstes Element, Shift umgekehrt); jedes Schließen
  (Button, Escape, `close()`) gibt den Fokus an den Auslöser zurück. Der
  Hintergrund schließt nur einen Klick, der auch dort begann (Audit F5),
  `keepOpen()` kann auch den verhindern (Login mit Getipptem, Watch-Dialog).
  Escape im Dialog stoppt die Weitergabe an Escape-Handler dahinter; ohne
  `showModal()` (jsdom) setzt/entfernt der Helfer `open` selbst. `close()`
  bleibt synchron (Fokus und Seite sofort zurück); das Ausblenden malt CSS
  (`overlays.css`, `display`/`overlay` mit `allow-discrete`).
  `App.closeIcon()` liefert das eine gezeichnete Schließen-Kreuz.
- **Ebenen über dem Inhalt (seit 2026-10-20, Apple-Audit C1, C4, E1, E3, E6,
  E10, G1, G3)** — ein Material und eine Bewegung für alles, was über der
  Seite liegt (`static/css/overlays.css`, nach allen Komponenten geladen):
  - **Scrim:** ein Token `--scrim` (`foundation.css`, hell/dunkel) hinter
    jedem modalen Fenster, dem Antwortleser (`::backdrop`), dem Memory-Dialog,
    dem Gmail-/Calendar-Sheet, dem Satzkarten-Sheet (auch auf der Startseite,
    `landing.css`), dem Agent-Aktivitäts-Sheet und der Handy-Schublade;
    nirgends mehr `backdrop-filter` (`tests/js/overlays.test.mjs` verbietet
    jeden Wert außer `none`, Admin ausgenommen).
  - **Dialogfläche:** `--raise`, `--lift`, `--radius-lg`, eine Haarlinie
    `--line-soft` für `.modal-content` (und Memory-/Google-Sheet). Der
    Elternteil des Selektors steht in `:where()`, die Regel wiegt also nur
    eine Klasse: Eine Ebene mit eigener Form schreibt sie mit einer etwas
    spezifischeren Regel (am Handy das bündige Gmail-&-Calendar-Sheet,
    `.agent-google-overlay > .agent-google-sheet`, unten eckig, ohne Linie).
    Bewegung: Dialog blendet in `--dur-layer`/`--ease-out` ein, die Fläche
    steigt 8px aus 98 % (`@starting-style`); Ausgang `--dur-state`/`--ease-in`.
  - **Popover (`popover.js`, `App.popover`):** (+)-Menü, Modellwahl,
    Kontomenü, „…“-Menüs (Chatzeile, Cite, Agent-Dateien), Kontingent-Karte,
    Satzkarte. `register(el, {close})`, `opened(el, {trigger})` (vor dem
    Zeigen: schließt alle anderen, setzt Richtung `--popover-shift`/
    `--popover-origin-y` vom Auslöser aus), `closed(el)`, `closeAll`,
    `anyOpen`, `menuKeys(el, {items, close, opener})` (Pfeile mit Umlauf,
    Home/End, Escape mit Rückgabe, Tab verlässt), `focusItem`, `leave(el,
    done)` für Menüs, die beim Schließen entfernt werden (`.is-leaving`),
    `triggerOf(el)` (Auslöser des Popovers um `el`) und `recentTrigger()`
    (Auslöser des in der letzten Sekunde geschlossenen Popovers;
    `modal-dialog.js` nimmt beide für die Fokus-Rückgabe).
    Rein: 4px + 98 % in `--dur-state`/`--ease-out`; raus `--dur-press`/
    `--ease-in`. Die Bewegung kommt aus CSS (`display` allow-discrete), das
    Öffnen/Schließen der Module bleibt synchron.
  - **Hinweise (`notices.js`):** `App.toast({message, tone, action, undo,
    onExpire, duration, key})` → `{update, settle, cancel, dismiss,
    focusAction}`; eine Zeile über dem Composer (`--toast-lift`: Composer,
    Tastatur, Safe Area), immer nur eine, weitere warten (eine mit Aktion
    verdrängt sofort, die vorige wird „expired“; Ersetzen — Aktion oder
    gleicher `key` — schaltet die Warteschlange nicht weiter), `role=status`,
    Dauer nach Wortzahl (3–10 s, mit Aktion ≥ 5 s), Fehler (`tone: "error"`,
    allgemein `duration: Infinity` ohne Aktion) bleiben bis zum Schließen,
    blockieren aber nichts: jede neue Zeile (mit oder ohne Aktion) stellt
    den Fehler zur Seite (`parked`), läuft ihre volle Zeit, dann kommt der
    Fehler wieder; neue Zeilen reihen sich vor geparkten Fehlern ein, und
    ein geparkter Fehler drängt die Zeile davor nicht; derselbe Fehler noch einmal ersetzt den geparkten (Nachprüfung 2 N2). Hover/Fokus pausieren, asynchrone
    Aktionen zeigen ihren Fortgang und melden über `update()`. Ist ein
    modaler Dialog offen, zieht die Zeile in ihn (sonst läge sie inert
    darunter); öffnet oder schließt einer, während sie steht, folgt sie ihm
    (MutationObserver auf `open`). `App.toast.current()`,
    `App.toast.settleAll()`. Dünne Weiterleitungen: `App.showPopup(message,
    options)` (`app-core.js`, ~100 Aufrufer), `App.undoNotice.show({text,
    actionLabel, onAction, onExpire, duration})` (Chat löschen),
    `App.watchDashboard.showUndoToast(message, {undo, commit, timeout})`,
    `window.showMobileInfoPopup`; Memory-Undo (`memory-edit.js`), Memory-Löschen
    (`user-memory.js`) und der Feature-Hinweis (`feature-access.js`) rufen
    `App.toast` direkt. `App.composerNotice.show(message, {tone, for,
    duration})` / `.clear()` sagt Eingabefehler (zu lange Nachricht, zu viele
    Wörter, falsche/zu große/zu viele Dateien – eine Zeile pro Wurf) als
    `#composerInputNotice` unter `#agentComposerNotice`, faltet weich auf und
    zu und verschwindet beim nächsten Tippen; ein neuer Hinweis während des
    Zufaltens dreht die Faltung um, statt mit ihr zu verschwinden.
  - **Bestätigung (`confirm-dialog.js`):** `App.confirm({title, body,
    confirmLabel, cancelLabel, danger})` → `Promise<boolean>`; ein
    `#appConfirmDialog`, bei `danger` Fokus auf Cancel. Ersetzt jedes
    `confirm()`/`alert()` außerhalb des Admins (Logout, Konto löschen, Link
    widerrufen, Telegram trennen); öffentliche Formulare melden Fehler inline
    (`.share-form-error`). `tests/js/overlays.test.mjs` verbietet
    `alert(`/`confirm(` in `static/` und `templates/` (außer Admin).
  - **Schließen-Kreuz:** `.close-button` + `.close-icon` in `foundation.css`
    (SVG-X 16px, Strich 1,75, 32-px-Kreis, auf Touch 44 px Trefferfläche);
    nirgends mehr „×“/„✕“-Glyphen (Test).
- **`motion.js`** (`window.App.motion`, `auth`-Gruppe, zuerst) — Bewegungs-
  Tokens für Skript: `ms("layer")`, `ease("out")`, `reduced()`,
  `leave(el, done)`, `switchTheme(apply)` (Hell/Dunkel in einem Schritt:
  `html.is-theme-switching` schaltet für das Bild alle Transitions ab, eine
  View-Transition blendet die Seite einmal über). FLIP-Gleiten (`app-core.js`,
  Antwortleser), Zeilen-/Chip-Animationen (`firebase.js`, Starter, Aktivität)
  lesen Dauer und Kurve hier.
- **`disclosure.js`** (`window.App.disclosure`) — jedes `<details>` in `/app`
  öffnet und schließt seine Höhe weich (`--dur-state`); Module mit eigener
  Bewegung („Thought for …“, Watch-Einstellungen, Reader-Frage) stoppen den
  Klick per `preventDefault`, `data-disclosure="static"` nimmt eines aus.
  Reduzierte Bewegung: sofort.
- **`tooltip.js`** (`window.App.tooltip`, `init()` ruft `app-init.js` als
  Letztes) — der eine Tooltip (`.global-tooltip`, `role=tooltip`) für `title`
  und `data-tooltip`: Zeiger nach 500 ms (beim Weiterziehen sofort), Tastatur-
  Fokus, Tipp auf eine Marke ohne eigene Aktion; das `title`-Attribut wird nur
  während des Hoverns geparkt (`data-tooltip-title`), damit der Browser keinen
  zweiten zeichnet. Wiederholt ein Tooltip nur den sichtbaren Text, erscheint
  er nicht; Ausnahme `data-tooltip-overflow` (seit 2026-10-22, Chat-Titel der
  Sidebar): der eigene Text, aber nur solange das Element ihn abschneidet
  (`scrollWidth > clientWidth`).
- **Bewegungs-Regeln (`static/css/motion.css`, Apple-Audit C8, C10, C11, C13,
  C14):** Theme-Wechsel ohne Verschmieren, ein Spinner (`.spinner` und die
  übrigen Ladezeichen: Spur + Bogen in `currentColor`, eine Drehung je
  `--dur-spin`), was sich wiederholt (Schimmer, Puls, Hervorheben) läuft im
  einen `--dur-beat` (das Hauslicht atmet in `calc(var(--dur-beat) * 2)`),
  reduzierte Bewegung: Seitenleiste blendet statt zu fahren, Spalte gleitet
  nicht, Ebenen blenden ohne Steigen, Spinner dreht langsamer. Drücken:
  `--press-scale` (0,97, bei reduzierter Bewegung 1) für jeden Knopf; Zeilen
  dunkeln beim Drücken ab. Fokus: der eine Ring (`--focus-ring`, auch im
  Dunkelmodus aus der dunklen `--ink-2`, ≥ 7:1), kein `outline: none` hinter
  einem Hover-Ton mehr, in Menüs nach innen versetzt; Textlinks runden die
  Ecken. `tests/js/motion-tokens.test.mjs` verlangt in jeder Transition und
  Animation nur `var(--dur-*)`/`var(--ease-*)` (keine rohen
  Zeiten/Kurven, kein `transition: all`, keine eigenen Dauer-Properties) und
  prüft Spinner, Takt, Ring und Druck. Seit der Nachprüfung gilt das für
  jedes Stylesheet, das ein Nutzer bekommt: `static/style.css` und jedes von
  einem Template verlinkte Blatt samt aller (auch verschachtelten) Imports,
  also auch Startseite, Benchmark, Topics, Consensus Engine und die übrigen
  öffentlichen Seiten (Admin ausgenommen).
- **Handy-Schublade (`app-init.js`, `syncDrawerFocus`):** die offene
  Overlay-Seitenleiste macht die Seite dahinter `inert`, holt den Fokus zu
  sich und gibt ihn beim Schließen an `#toggleSidebarButton`; Escape schließt
  sie (Capture: ein offener Dialog oder ein Popover bekommt Escape zuerst).
  Seit 2026-10-20 (Apple-Audit F11, `bindDrawerSwipe`) folgt sie einem
  Finger nach links (Pointer-Events `pointerType: "touch"`, auf der Leiste
  oder dem abgedunkelten Rest): die Leiste per Inline-`transform`
  (`.sidebar.is-dragging` ohne Transition), das Dimm (`body::after`) per
  pausierter Web Animation; ab einem Drittel Weg oder einem Wisch schließt sie
  (`closeOverlaySidebar`, Fokus zurück an den Menüknopf), sonst gleitet sie
  zurück; Leiste und Dimm laufen von der Fingerstelle weiter (für das Dimm
  eine eigene Animation, weil eine abgebrochene Script-Animation ihren Wert
  keiner CSS-Transition übergibt). `touch-action: pan-y pinch-zoom` an der
  offenen Leiste, `pinch-zoom` am `body` (das Pseudo-Element fragt der
  Browser nicht); mit „Reduce motion“ wandert nichts mit, der Wisch schließt
  trotzdem.
- **`feedback-dialog.js`** (`window.App.feedback`, seit 2026-10-15) — der
  Feedback-Dialog `#feedbackModal`; vorher teils in `app-init.js`, teils als
  `window.sendFeedback` in `firebase.js`. Gäste sehen statt des Formulars einen
  Login-Hinweis mit `contact@consens.io` (`#feedbackGuestNote`; „Log in“ schließt
  den Dialog und ruft `App.openAuthModal("login", #feedbackButton, "feedback")`).
  Eingeloggt: `POST /feedback` mit ID-Token, Prüfung von `response.ok`, Antwort
  in der Statuszeile `#feedbackStatus` (englisch, kein `alert()`), Submit-Button
  bis zur Antwort gesperrt (ein Doppelklick ist eine Nachricht). FastAPI-
  Validierungslisten werden zu einem Satz. Ein getippter Text hält den Dialog
  bei Hintergrund-Klick offen.
- **`settings-search.js`** (`window.App.settingsSearch`, seit 2026-10-23) —
  die Suche in Settings (`#settingsSearch`): Wortteile, Tippfehler, englische
  und deutsche Schlüsselwörter; Ablauf unter „Settings … Suche“ im
  Layout-Abschnitt. `matches(query, texts)` ist der Abgleich ohne DOM.
- **`model-picker.js`** — Modellauswahl/Custom-Picker, Default-Modelle,
  Persistenz als Kontoeinstellungen `compare_models`, `consensus_model` und
  `consensus_preset` über `App.userSettings` (lokale Kopie unter den bisherigen
  `pref_check_*`/`pref_select_*`/`pref_consensus_preset`-Schlüsseln;
  `restoreModelSelections`, bei Werten vom Server, aus einem anderen Tab oder
  nach dem Abmelden `applyAccountModelPreferences`, das ungespeicherte Familien
  erst auf den Seiten-Default setzt). `markConsensusPresetCustom({family,
  engine})`: wer ein Preset verlässt, behält die Aufstellung auf dem Schirm als
  eigene Wahl; innerhalb von Custom wird nur das Geänderte gespeichert, dazu
  Familien ohne gespeichertes Modell (eine gespeicherte Pro-Wahl, die vor dem
  Laden der Stufe gesperrt erscheint, bleibt so erhalten). Der Consensus-Picker hat seit 2026-07-18
  eine Preset-Ebene (Daily/Open Models/High Quality + Custom): Presets kommen aus
  `window.CONSENSUS_PRESETS` und setzen als zusammenhaengendes Model-Set genau
  sechs aus den Registry-Familien gewählte Antwortmodelle plus Consensus-Engine. High Quality (interne ID
  `thorough`) ist Pro-only und zeigt
  ein Pro-Badge neben dem Namen. Rechts in der Namenszeile jeder Preset-Zeile
  stehen die Anbieterzeichen seiner Antwortmodelle als Stapel
  (`createPresetMarks`, über `App.createModelMark`; einfarbig, Farbe bei Hover,
  Tooltip mit den Modellnamen, `aria-hidden`); alle Preset-Zeilen halten die
  Haken-Spalte frei, damit die Stapel bündig stehen. Eine manuelle Antwort- oder Consensus-Modellwahl wechselt zu
  Custom. Die nativen Selects werden dabei OHNE change-Event gesetzt. Die High-Quality-Basis nutzt OpenAI GPT-5.6 Sol; gespeicherte
  Legacy-Werte mit GPT-5.5 werden bei der Normalisierung migriert. Zustand in
  `consensus_preset` ("custom" = explizite Modellwahl, ausgeloest durch
  jedes change-Event am Dropdown); `consensus_model` bleibt die
  Custom-Wahl. Bestandsnutzer mit gespeicherter Modellwahl migrieren zu
  "custom"; die volle Modell-Liste bleibt bewusst ohne Beschreibungen.
  **Seit 2026-07-27 ist „Custom" die ganze Aufstellung eines Laufs**, nicht
  mehr nur die Engine-Liste: `state.view` kennt `presets` → `custom`
  (Uebersicht: alle Registry-Familien mit Ein-/Ausschluss-Toggle + aktuellem
  Modell, darunter die Consensus-Engine) → `provider:<key>` bzw. `engine`
  (die jeweilige Modell-Liste, mit Rueckweg). Die Auswahl feuert `change` auf
  dem ZIEL-Select, damit `app-init.js` über `markConsensusPresetCustom()` die
  Wahl aller Familien speichert und auf „custom" umschaltet; nur Provider-Zeilen kehren danach in die
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
  überschreibt die Grundwerte + die Ampel. **Gemessene Stufen (seit
  2026-10-20, Apple-Audit G7/G13/G15, Vertrag `tests/test_material_tokens.py`
  mit OKLab- und WCAG-Rechnung):** Grund → `--raise` 3,6 hell (`#eeeeee`) und
  3,7 dunkel (`#212325`), vorher 1,5 hell und 10,3 in der dunklen App;
  `shell.css` überschreibt `--raise` nicht mehr (die bläuliche App-Fläche
  `#303338` ist weg, `--app-surface*` sind nur noch Aliasse auf
  `--raise`/`--raise-hover`/`--raise-selected`). Graustufen gespreizt:
  `--ink-2` `#4a4d53` / dunkel `#b0b2b6`, `--ink-3` `#606369` / `#94979b`
  (Abstand ink-2 → ink-3 8 bzw. 9, vorher 2,8), `--ink-3` hält ≥ 4,5:1 auf
  Grund, `--raise` und gehovertem `--raise`; Text bekommt seinen Ton aus der
  Farbe, nicht aus `opacity`. Die Ampel ist textsicher auf Grund und `--raise`
  (`--agree #217863`, `--partial #896512`, `--dispute #ad4b57`; dunkel
  `--dispute #f07f76`, ein Rot statt des Korall, das neben Bernstein braun
  wirkte), die `-bg`-Töne sitzen auf demselben Farbton. Die Mail-Palette
  (`app/services/mailer.py`) zieht die Graustufen mit.
  Seit 2026-09-06 hebt `shell.css` Chat-Fragen (auch historische) mit dem
  lokalen Token `--chat-surface` ab (seit 2026-10-20 = `--raise`); die Karte
  einer Marke (Vorschau und festgehaltene Karte) trägt seit 2026-10-23 ihre
  eigene Fläche `--cx-card-bg`, eine Stufe heller als die Seite
  (`components-consensus-insights.css`). Der Composer ist seit 2026-10-20 das
  gehobene Feld `--field` (= `--well`) mit `--field-line` und `--field-lift`
  (aktiv `--field-lift-active`) aus `variables.css`/`public-tokens.css`:
  dasselbe Material wie das Startseiten-Feld (`--lp-field*` in `landing.css`
  sind Aliasse), deckend, ohne Blur (Apple-Audit G8); `--composer-*` sind
  Aliasse darauf. Desktop bleibt
  sticky, Mobile fixed; die bestehende Hoehenreserve und Menue-Ebene bleiben
  erhalten. `--app-surface`/`--app-surface-hover`/`--app-surface-selected`
  auf `body` sind seit 2026-10-20 nur noch Aliasse auf `--raise`,
  `--raise-hover`, `--raise-selected`.
  Der Consensus-/Watches-Umschalter ist in Threads und Direktvergleichen
  ausgeblendet; auf Start- und Watch-Ansicht bleibt er sichtbar. Sein aktives
  Segment ist in Light weiss mit dezenter Kontur. Seit 2026-10-20 steht er in
  beiden Ansichten an derselben Stelle (`left: calc(50vw +
  --app-sidebar-offset / 2)` ab 1100 px, Apple-Audit J4), weil auch die
  Watch-Seite rechts der Seitenleiste beginnt. Die Regel liegt in
  `components-watch.css` neben der Grundregel des Schalters (in `layout.css`
  verlor sie gegen die spätere `left: 50vw` und griff nie) und gleitet mit
  `left var(--dur-layer) var(--ease-standard)` wie die Spalte (C3). Gewählt
  wird über Thumb und Tinte, nie über fettere Schrift (C9).
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
  Seit 2026-10-18 stehen sie per `order: -1` ÜBER der Blase (erst das Bild,
  dann die Frage), Bildkacheln ohne Rahmenlinie mit den Ecken der Blase.
  Bilder an der Nachricht zeigen sich seit 2026-10-06 selbst als kleine
  Kachel (`.is-image-tile`, 96 px hoch) statt als „IMG“-Plakette:
  `attachments.js` (`imageTile`) nimmt direkt nach dem Senden das Bild aus dem
  Composer (`sentImages`, Schlüssel Name|Größe|Typ, gefüllt in `messageMeta`),
  später die gespeicherte Agent-Datei (`openFile`, einmal pro Datei,
  `storedImages`, als `data:`-URL wie im Viewer: die CSP erlaubt für Bilder
  `data:`, aber kein `blob:`, eine Blob-URL fiel bis 2026-10-08 auf „IMG“
  zurück); fehlt beides, bleibt die Plakette. Solange die gespeicherte Datei
  lädt (`is-thumb-loading`), ist die Kachel ein ruhiger Platzhalter im
  Skelett-Ton mit wanderndem Licht und das `<img>` hat `alt=""` ohne `src`;
  erst beim `load` bekommt es den Dateinamen als Alt-Text und blendet ein
  (seit 2026-10-22: vorher malte der Browser beim Öffnen alter Chats eine
  Sekunde lang sein Symbol für ein kaputtes Bild plus Dateinamen).
  Die Vorschau (`#attachmentViewerModal`) zentriert ohne `[open]`-Bindung:
  beim Ausblenden behält der Dialog sein `display`, die Zentrierung fiel aber
  mit `[open]` weg und das Bild sprang dafür nach links oben (bis 2026-10-22).
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
  Container-Gap), damit `New comparison → Models` enger bleibt. Seit
  2026-10-20 (Apple-Audit G2) sind `#newRunButton`, `#sidebarModelPicker` und
  `#bookmarksToggle` EIN Zeilenbauteil: Grid `18px minmax(0, 1fr) auto`,
  16-px-Glyphe mittig in der 18-px-Spalte, 9 px Abstand, Label 14 px/500,
  `min-height: 36px`, `padding: 6px 8px`, derselbe 4-px-Einzug wie die
  Sektionen (Glyphen bei x = 24, Wörter bei x = 51); Models trägt die Anzahl
  als zweite Zeile in `--ink-3` (12 px). New comparison ist in Ruhe transparent
  und auf dem leeren Start als „hier bist du“ `--selected` getönt. In der
  Schublade (≤1099 px) verlieren die Sektionen ihren 4-px-Einzug, damit Models
  und Chat-Titel bündig mit New chat stehen. Der Bookmark-Toggle sowie seine
  Suche sind bis zum verifizierten Login nativ deaktiviert.
- **Ziehbare Sidebar-Breite** (seit 2026-10-08) — `static/js/sidebar-resize.js`
  (Head-Bundle, `App.sidebarResize` `{get, set, reset, bounds}`) setzt
  `--sidebar-width` auf `<html>` (Default 260px in `layout.css :root`), schon vor
  dem ersten Paint aus `localStorage["sidebar_width"]`. Daraus leiten sich ab:
  `.sidebar`-Breite, `.sidebar-settings`, `.app-nav-float` (`left`),
  `--app-sidebar-offset` und `--reader-left-rail` (Antwort-Reader). Der Griff
  `#sidebarResizer` (`role="separator"`, nach `#appSidebar` eingefügt,
  `position: fixed` auf der Kante) gibt es nur ab 1100px bei offener Sidebar;
  die Overlay-Sidebar (≤1099px) behält `min(82vw, 360px)`. Ziehen (Pointer
  Capture, `body.is-resizing-sidebar` schaltet Transitions und Textauswahl ab),
  Doppelklick = 260px und Speicher löschen, Pfeiltasten ±10 (Shift ±40),
  Pos1/Ende = Grenzen. Grenzen 200px bis min(480px, 40 % des Fensters); ein
  schmaleres Fenster deckelt nur die Anzeige, die gewählte Breite bleibt
  gespeichert. Neue Stellen, die neben der Sidebar Platz rechnen, nutzen
  `var(--sidebar-width)` statt 260px.
- **Ein einziger Sidebar-Toggle** — `.app-nav-float .sidebar-toggle` erscheint
  nur bei geschlossener Sidebar, `#sidebarToggleInner` sitzt rechts neben der
  Wortmarke in `.sidebar-brand-row`. Beide zeichnen dasselbe Panel-Icon (`.sidebar-panel-icon`,
  Rechteck mit linker Schiene statt Burger, 20 px, flacher Hover).
  `shell.css` blendet den schwebenden per `body:not(:has(.sidebar.collapsed))`
  (Overlay ≤1099px: `body:has(.sidebar.active)`) aus. **Ein- und Ausklappen ab
  1100 px (seit 2026-10-20, Apple-Audit C3):** es gibt nie zwei Logos und nie
  zwei Panel-Glyphen. Der schwebende Toggle liegt bei offener Leiste genau auf
  `#sidebarToggleInner` (`left: sidebar-width - 46px`) und ist dort
  `visibility: hidden` statt `display: none`; beim Schließen tritt der innere
  sofort ab und der schwebende gleitet (`left`, `--dur-layer`,
  `--ease-standard`, wie Leiste und Spalte) in die Ecke, beim Öffnen gleitet er
  zurück und übergibt per verzögerter `visibility` (`--dur-layer`), wenn die
  Leiste angekommen ist. Die schwebende Wortmarke `.brand-float` bleibt ab
  1100 px gelegt und blendet: aus in 60 ms, bevor die Marke der Leiste den
  Rand erreicht; ein, nachdem sie hinausgeglitten ist (Verzögerung
  `--dur-layer / 2`). `.app-nav-float` selbst nimmt keine Klicks
  (`pointer-events: none`, nur seine sichtbaren Teile). `body.is-sidebar-settling`
  schaltet alle drei Übergänge ab. Auch die Agent-Spalte (≥1200 px) gleitet
  mit `--dur-layer` statt 200 ms. Regression pro Bild:
  `tests/e2e/test_sidebar_resize.py::test_logo_toggle_and_switch_move_with_the_sidebar`. `app-init.js` bindet
  **alle** `.sidebar-toggle`-Buttons an denselben Handler; `updateToggleButton`
  pflegt aria/title auf allen. Eine geschlossene Sidebar wird zusätzlich
  `inert` + `aria-hidden`, damit ihre offscreen liegenden Controls weder in der
  Tab-Reihenfolge noch im Accessibility-Tree bleiben. Darunter liegt
  `#newRunButton` („New comparison“) als vollbreites Navigationselement. Er
  leert über `runRegistry.clearVisible()` nur die aktuelle Projektion samt
  Fortsetzungsbasis und kehrt in `is-hero` zurück; aktive Runs und deren
  Bookmark-Saves laufen weiter. Nur
  `firebase.js::resetLoadedRunAfterLogout` cancelt/verwirft sämtliche Contexts.
- **Sidebar-Startzustand** (seit 2026-10-18) — ab 1100px gilt die eigene Wahl
  (`localStorage["sidebar_collapsed"]`, nur der Toggle schreibt sie), ohne sie
  ist die Sidebar für Gäste eingeklappt und für Konten offen
  (`app-init.js::prefersCollapsedSidebar`; Gast = kein `auth.currentUser`, bei
  unbekannter Auth kein `id_token`). `app-bootstrap.js` malt dieselbe Regel in
  den ersten Frame, `checkWindowSize` und ein Listener auf
  `consensio:auth-state` halten sie: Anmelden öffnet, Abmelden schließt, ohne
  Gleiten (`body.is-sidebar-settling` schaltet die Transitions kurz ab) und
  ohne etwas zu speichern. Die Overlay-Sidebar (≤1099px) startet immer zu und
  öffnet sich beim Login nicht.
- **Reading Chrome** — `app-init.js` beobachtet beim lesbaren Consensus und
  auf der geöffneten Watch-Seite den Window-Scroll (die Watch-Seite scrollt
  seit 2026-10-20 im Dokument, F14; der alte Listener auf ihren eigenen
  Scroll-Container ist harmlos übrig). Nach deutlichem Abwärtsscrollen fahren der fixierte
  `#viewSwitch` und der schwebende `.app-nav-float` aus dem Lesebereich;
  Aufwärtsscrollen, Seitenanfang und Tastatur-Navigation blenden sie wieder ein.
  Der Zustand ist rein transient als `body.is-reading-chrome-hidden` und
  verändert weder Sidebar-Persistenz noch Watch-/Consensus-Daten.
- **Mobile Kopfleiste** — `header.app-mobile-header` zeigt bei ≤1099 px seit
  2026-10-13 keine Leiste mehr, sondern zwei Gruppen: links das Menü als
  44-px-Knopf, rechts New chat und, für die fertige Antwort, Watch und „…“.
  Seit 2026-10-20 (Apple-Audit G17, Max' Entscheidung „rahmenlos wie am
  Desktop“) stehen beide als bloße Glyphen ohne erhabenen Kreis, Ring oder
  Schatten (vorher Inseln im Composer-Material); Hover `--hover`, das offene
  „…“-Menü `--selected`, über gescrolltem Text trägt sie der `--ground`-Verlauf
  des Kopfs. Share steht mobil
  nicht als Icon in der Pille, sondern als erste Zeile „Share publicly“ im
  „…“-Menü (`.consensus-menu-share` aus `consensus-actions.js`, nur ≤1099 px
  sichtbar; sie fokussiert den Toggle und klickt den echten `#consensusShareButton`,
  damit der Dialog den Fokus dorthin zurückgibt). Der Toggle zeigt in der Insel
  drei Punkte statt des Zitatzeichens und heißt dort „Share, copy and cite“
  (`mobile-header.js`), im Desktop-Footer weiter „Citation and copy options“.
  Auf dem Startbildschirm (`body.is-hero`) steht neben dem Menü die Marke
  (`.brand-float`, Logo + „consens.io“, 44 px Touchfläche; ≤359 px neben
  Log in/Sign up nur das Logo), im Thread gehört der Platz den Aktionen; ein
  mittlerer Titel entfällt. Der Kopf ist 56 px hoch mit Safe-Area-Zuschlag,
  selbst transparent und `pointer-events: none` (nur die Inseln nehmen Taps);
  sobald darunter gescrollt ist (`.is-scrolled` aus `mobile-header.js`,
  Window-Scroll, auch auf der Watch-Seite), liegt `--ground` deckend hinter
  dem ganzen Kopf und läuft 20 px darunter aus (`::before`, ohne Blur; seit
  2026-10-20, Apple-Audit F13: vorher war der Grund schon 24 px unter der
  Oberkante halb durchsichtig, und die Zeile zwischen den Knöpfen blieb lesbar). **Safari-Leisten (seit 2026-10-18):**
  iPhone-Safari (iOS 26, kein `theme-color` mehr) färbt die Streifen hinter
  Statusleiste und unterer Leiste nach dem fixierten Kasten an der Kante
  (WebKit `fixedContainerEdges`: Mitte der Kante 4 px innen treffen, ohne
  `pointer-events`, aufwärts bis zur ersten fixed/sticky-Box mit ≥ 90 %
  Viewport-Breite; ist sie nicht auch fast viewporthoch, gilt der deckende
  Hintergrund auf dem Weg). Fehlt er, misst Safari Pixel und behält das
  Ergebnis; viewportgroße Ebenen (Buchstabenwolken, Dialoge, Dimmer; bis
  2026-10-20 auch die fixierte Watches-Seite) und die Sidebar behalten die
  vorige Farbe — so blieben weiße
  Leisten stehen, sporadisch und zuverlässig nach einem Theme-Wechsel. Jede
  Kante hat deshalb einen flachen, vollbreiten Kasten in Seitenfarbe:
  oben `.app-mobile-header-edge` (Span im Kopf, 24 px, `--ground`, nach 8 px
  ausgeblendet, `pointer-events: none`), unten im Thread die fixierte
  `.input-section` (`--composer-halo`, deckungsgleich mit ihrem Halo), auf
  Startbildschirm und Watches `.app-bottom-edge` (fixed, 24 px, z 1 über den
  Wolken bzw. 1401 über `.watch-page`, im Thread aus). Solange Sidebar oder
  Dialog offen sind, hält Safari die alte Farbe absichtlich fest; danach
  folgt sie. Neue fixierte Ebenen an einer Kante: flach + deckende
  Seitenfarbe, oder darunter bleiben; `SAFARI_BAR_COLOURS` in
  `tests/e2e/test_mobile_navigation.py` bildet die Regel nach und meldet
  „kept from before“. Popover an den Inseln (`.consensus-actions-menu`,
  `.watch-feature-nudge`) liegen darüber. Der einmalige Watches-Hinweis
  (`#viewSwitchWatches.has-watch-pulse`) erscheint mobil als ruhiger grüner Punkt
  am Menü-Knopf und am Watches-Reiter der Sidebar, bis Watches geöffnet wurde.
  Alle Icons teilen Tinte (`--ink`), 22-px-Glyphen und
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
  `#viewSwitch` wandert mobil nach `#mobileSidebarViews`. Dort zeigt er seit
  2026-10-18 nur noch `#viewSwitchWatches` als Navigationszeile (Augen-Glyph,
  wie New chat); die Chat-Hälfte ist im Menü ausgeblendet, zurück geht es wie
  in jeder Chat-App über New chat oder einen Chat der Liste. Auf Desktop kehrt
  er als Pillen-Switch an seinen ursprünglichen Ort zurück. Auch aus Watches führt New chat über den bestehenden
  `#newRunButton`-Handler zum leeren Composer, ohne Hintergrund-Runs abzubrechen.
  **Mobiles Menü in ChatGPT-Sprache** (seit 2026-10-18, eigener Block am Ende
  von `shell.css`, vollständig unter `max-width: 1099px`): eine Liste
  schlichter Zeilen statt gestapelter Bedienelemente. New chat (Stift-Glyph)
  und Watches sind 44-px-Zeilen mit 20-px-Glyph, transparent im Ruhezustand;
  getönt (`--drawer-tint-strong`, aus `--ink` gemischt) ist nur, wo man ist:
  New chat auf dem leeren Startbildschirm (`body.is-hero` ohne offene
  Watch-Seite), Watches bei offener Watch-Seite, der offene Chat (`.is-active`).
  „Chats“ (vorher „Bookmarks“, auch auf Desktop) ist eine leise Überschrift
  ohne Symbol, der Pfeil erscheint nur bei eingeklappter Liste. Chat-Zeilen sind
  40 px hoch, rechts steht ein gedämpftes ··· (`.bookmark-menu-button`,
  `BOOKMARK_MENU_ICON` in `firebase.js`, auch für Desktop-Hover); es öffnet seit
  2026-10-20 ein echtes Menü (seit 2026-10-22 Pin, dann Rename, Share, Delete, siehe „Chatliste:
  Zeilen, Menü, Löschen mit Undo“). Die Liste läuft oben und unten
  per `mask-image` weich aus statt eine Zeile anzuschneiden; Trennlinien
  (Reiter-Unterstrich, Linie über dem Konto) entfallen, der Tarif im Fuß ist
  grau (Gold bleibt am Kürzel). Imprint · Privacy · Terms bleiben bewusst
  sichtbar unter dem Konto (Impressum direkt erreichbar).
  Beide Sidebar-Toggles
  referenzieren `#appSidebar` per `aria-controls`. Landmarks (seit
  2026-10-24): `#appSidebar` ist `<nav aria-label="Chats">`, der Chat
  `main#appMain.container` mit einem unsichtbaren `h1#appHeading` (Titel des
  offenen Chats, `App.setAppTitle`), die Watch-Seite `main#watchDashboard`;
  es ist immer nur eines der beiden `main` sichtbar. Der Inhaltsanfang reserviert
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
  (`.pro-badge.is-plus`) — Gold gehört den teuren Modellen, die Plus nicht hat.
  Seit 2026-10-22 ist `.pro-badge` überall ein getöntes Etikett („Pro“ in
  tiefem Gold auf zarter Goldfläche, ohne Rand, Glanz und Schatten). Die **Wortmarke**
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
  permanente Zeile mehr, sondern ersetzt bei Hover/Fokus den Titel „Chats“
  (auf Touch-Geräten bleibt sie dauerhaft erreichbar). Die frühere Sidebar-/
  Help-FAQ-Rangliste lebt jetzt ausschließlich auf `/model-pulse`; die
  Landingpage verlinkt oben dezent dorthin und die App-Shell lädt keinen
  Firestore-Live-Listener mehr. Die gemeinsame Lesespalte für Fragen, Antworten
  und Composer ist standardmäßig 768px breit (`--app-container-width` auf
  `body`, `layout.css`) und schrumpft auf kleinen Viewports. Bei offener
  Desktop-Sidebar ab 1100px zentriert `--app-sidebar-offset: var(--sidebar-width)` die Spalte
  und den Startseiten-View-Switch im verbleibenden Bereich rechts der Navigation;
  eingeklappt und im mobilen Overlay-Modus gilt die Viewport-Mitte. Der mobile
  fixierte Composer verwendet dieselbe Breite wie der Spalteninhalt; mobil
  stehen Menü und auf dem Startbildschirm die Wortmarke als schwebende Inseln oben. Gast-Login/-Sign-up
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
  **Suche (seit 2026-10-23, `static/js/settings-search.js`, `App.settingsSearch`):**
  Über den Reitern sitzt in `.settings-side` das Feld `#settingsSearch` (mobil
  über der Reiterleiste). Getippt zeigt `.settings-layout.is-searching` die
  Treffer aller verfügbaren Kategorien unter ihren Titeln (Beschreibung,
  `.settings-note` und Nicht-Treffer `.is-search-miss` ausgeblendet; Panels
  versteckter Reiter werden nie durchsucht). Gesucht wird in den sichtbaren
  Wörtern einer Zeile `.settings-group > .settings-section` (also in der
  Seitensprache; gespeicherte Memories, Status-Zeilen und Textfelder nicht), in
  ihrem `data-settings-keywords` und in Titel + `data-settings-keywords` ihrer
  Kategorie; die Schlüsselwörter stehen englisch UND deutsch im Template und
  werden nicht übersetzt. **Neue Einstellungszeile = Schlüsselwörter
  mitpflegen.** Jedes Query-Wort muss passen: Wortanfang, ab vier Buchstaben
  jeder Wortteil (auch über Bindestrich/Leerzeichen hinweg,
  „buchstabenanimation“), sonst ein Tippfehler (ab fünf Buchstaben einer, ab
  neun zwei; Tausch zählt einfach). Umlaute passen ausgeschrieben und schlicht,
  Füllwörter („the“, „aus“) müssen nicht passen. Tippfehler-Treffer zeigen sich
  nur, wenn nichts exakt passt. Treffer im Text tönt
  `::highlight(settings-search)`. Ein Reiterklick, Pfeiltasten in der Leiste
  oder Escape im Feld beenden die Suche (`exit` → `settingsTabs.activate`);
  Enter springt zum ersten Treffer, Buchstaben auf den Reitern landen im Feld;
  `openSettingsModal` leert sie. Tests: `tests/js/settings-search.test.mjs`.
  Display → `#consensusHighlightsSelect` steuert Antwort- und Quellenmarkierungen
  über die Kontoeinstellung `consensus_highlights` (`none` oder ein Filter;
  lokal `consensio.showConsensusMarkers.v1` + `consensio.consensusHighlightMode.v1`): `all`,
  `contradictions` (inklusive grauer Detailwidersprüche), `concerns`
  (alle Widersprüche inklusive leichter und Split-Claims — passt damit zur Zahl „Contradictions N“ im Antwort-Fuß)
  oder `critical` (kritische Widersprüche). Default ist seit 2026-10-19
  wieder `concerns` (User-Vorgabe): eine Marke heißt „hier sind sich die
  Modelle nicht einig“; Zustimmung (Grün) und dünne Abdeckung (Grau) erscheinen
  nur, wenn jemand ausdrücklich `all` wählt (von 2026-10-12 bis 2026-10-19 war
  `all` der Default). Derselbe Default steht in `consensus-insights.js`
  (`DEFAULT_HIGHLIGHT_MODE`), `passage-check.js`, `agent-settings.js`,
  `templates/index.html` und `agent_settings.DISPLAY`. Fachliche Optionsnamen und ein
  umbrechender Hilfetext erklären die Farben. Bestehende explizite Auswahlen
  bleiben erhalten; fehlende/ungültige Werte fallen auf `all` zurück.
  „No highlights“ verwendet weiterhin `consensio.showConsensusMarkers.v1`.
  `consensus-insights.js` setzt `body[data-consensus-highlight-mode]`.
  Links und detaillierte Prüfergebnisse bleiben zugänglich. Satzfilter und Passage-Tabstopps werden beim Rendern
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
  Wahl als Kontoeinstellung `agreement_display` (lokal
  `consensio.agreementDisplay.v1`; der Vorgänger-Schalter
  `consensio.showAgreementScore.v1` wird beim Lesen migriert) und kennt drei
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
  Der Vorgängerschlüssel `consensio.showAgreementScore.v1` wird beim Lesen
  einmal migriert (`false` = `summary`) und danach entfernt; er wird nicht mehr
  mitgeschrieben.
  Die Usage-Gruppe zeigt zusätzlich das aktive Watch-Kontingent aus
  `/api/my/watches`. Gesperrte Features zeigen einen kurzen Hinweis ohne
  Unterbrechung; der Sidebar-Link „Early access“ (seit 2026-10-02 ein
  Textlink in der Tarifzeile `#accountPlanLine` unter dem Namen
  `#accountIdentity`, der dasselbe Konto-Menü öffnet wie das Kürzel;
  firebase.js füllt Kürzel und Namen, user-tier.js `#accountPlanName`).
  Seit 2026-10-22 ist die Kontozeile `.sidebar-account` eine Fläche wie das
  Konto oben in den macOS-Einstellungen: Monogramm mit Verlauf (zwei
  Buchstaben aus `displayName`, sonst der erste der Adresse; die Stufe färbt
  den Verlauf), darüber der Google-Name oder der Teil der Adresse vor dem @
  (die volle Adresse steht im Tooltip und im Menü), darunter der Tarif grau.
  Das `::before` von `#accountIdentity` spannt Trefferfläche und Fokusring
  über die ganze Zeile; Kürzel und Early-access-Link liegen darüber
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
  Aussage. Ohne das Opt-in „Let Agent update memory“ (siehe „Agent-Memory“
  unten) gibt es **keine automatische Ableitung** aus Antworten;
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
     (wie der Follow-up-Kontext). Watch-Reruns und Topic-Läufe rufen
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
  im Consensus-Prompt. Schreiben können nur die expliziten Memory-Endpunkte
  und — nach Opt-in — der Agent über `agent_memory.py`; die Antwortmodelle der
  `/ask_*`-Läufe nie. Watch und Topics bleiben weiterhin außerhalb.
  Speicher: `users/{uid}/memory/profile` (Schema v2; alte v1-Dokumente ohne
  `notes` bleiben kompatibel), Write transaktional hinter
  `persistence_guard`, Löschung über `_delete_user_subcollections` (die
  Subcollection `memory` steht dort — fehlt sie, überlebt das Profil das
  gelöschte Konto). `sanitize_profile` ebnet Whitespace ein, kappt je Feld und
  entfernt Prompt-Rahmenmarken (sonst könnte ein Feld den Chat-Kontext-Rahmen
  vorzeitig schließen; seit 2026-10-08 nur die exakten Großbuchstaben-Marken
  wie `ABOUT THE USER`/`END OF USER PROFILE` — vorher fraß die
  case-insensitive Suche normale Sätze wie „about the user settings“). `load_profile_text` ist fail-open: ein nicht lesbares
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
  Aufrufer erhalten. Liegt die gespeicherte Notiz über dem aktuellen Limit
  (Pro → Free, Admin senkt `memory_*_chars`), zeigt `GET` nur die gekappte
  Ansicht; ein `PUT`, das genau diese Ansicht oder keine Notiz schickt
  (Schalter, anderes Feld), lässt den vollen Text gespeichert. Erst eine
  geänderte Notiz ersetzt ihn. Ein Reload nach Remember/Correct/Undo
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
  Escape-/Backdrop-Schließen, zustandsabhängige Copy und Undo über die
  gemeinsame Hinweis-Zeile (`App.toast`); mobil erscheint er als Bottom-Sheet. `POST /api/my/memory/edit`
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
  Fehler bleiben budgetiert. Der Browser behält die Request-ID deshalb nur,
  solange keine Serverantwort kam (Netz, Gateway, `processing`) oder der Server
  `edit_in_progress`/`lease_lost` meldet; nach jeder anderen Absage mit
  `error_code` sendet ein erneuter Versuch eine neue ID.
  `memory-edit.js` bindet Auswahl, Dialog, Request und Undo-Toast an
  `{uid, App.authState.generation}`: ein Kontowechsel schließt Dialog und Toast,
  verwirft Auswahl/Request-ID und bricht den Fetch ab; vor dem Absenden sowie
  nach Token, Fetch und JSON wird die Bindung geprüft, sodass eine späte Antwort
  weder das Memory des neuen Kontos neu lädt noch dessen UI einen alten
  Undo-Hinweis zeigt. Tokenrefresh desselben Kontos bleibt unberührt. Memory-Inhalte erscheinen weder in Logs noch
  Metriken/Alerts. Watch, Topics, Judge und Shares bleiben außerhalb.
- **Agent-Memory (`app/services/agent_memory.py`, `agent-memory.js`, seit
  2026-10-04)** — neben Profil und Notiz eine Liste kurzer Einzel-Erinnerungen
  (`users/{uid}/memory/entries`, **ein** Dokument: `items[]` mit
  `{id: m+6 hex, text ≤ 300, origin agent|user, created_at, updated_at}`,
  höchstens 100; `revision`; Undo-Log `changes[]` mit Vorher/Nachher, höchstens
  50 Einträge und 30 Tage, `changes_purge_at` für die stündliche Retention
  `cleanup_memory_change_logs`). Der Agent **schreibt nur nach Opt-in**:
  Settings → Memory → „Let Agent update memory“ (`auto_memory` im
  Profil-Dokument, Default aus, nur wirksam bei `enabled`). Dann entscheidet der
  Orchestrator selbst, was er speichert, ändert oder löscht — ohne zusätzlichen
  Modellaufruf: Änderungen reiten als **Pflichtfeld** `memory` auf dem ohnehin
  fälligen `compare_models`- bzw. `check_text`-Aufruf (`[]` = bewusst nichts; ein optionales Feld
  ließ GPT-6 Luna im ersten Praxistest einfach weg) (`agent_comparison.py` baut das Schema per
  `create_model`, die Ausführung in `DelegationLoop._execute`; ein abgelehnter
  Memory-Teil bricht den Vergleich nie ab, das Ergebnis steht unter `memory`
  im Tool-Result und nie im gespeicherten Vergleich; gespeicherte wie abgelehnte
  Versuche landen inhaltsfrei als Tool-Eintrag `update_memory` in `agent_activity`,
  Ablehnungen mit Grundcode `reason` wie `evidence_not_found`, `invalid_id`,
  `text_too_long`, `unavailable` — nie mit Evidence oder Memory-Text; das gilt
  seit 2026-10-08 auch für ein abgelehntes eigenständiges `update_memory`).
  Seit 2026-10-08 ist `MemoryChange` bewusst **nachsichtig** (alle Felder
  optional/nullable, keine Schema-Längen, unbekannte Felder ignoriert, kein
  `maxItems` auf `memory`): `id: null` beim Hinzufügen, ein zu langer Text
  oder sechs Änderungen ließen vorher den ganzen `compare_models`-Aufruf an der
  Schemaprüfung scheitern (drei abgelehnte Runden beenden den Turn). Alle
  Regeln prüft jetzt `MemoryTools.apply`/`normalize_change` und meldet sie als
  normale Memory-Ablehnung (`MemoryRefused`, ein `ValueError` mit `code`).
  Dort endet auch jeder Speicherfehler (Firestore, Contention): geloggt wird
  nur die Kategorie, das Modell liest „Memory could not be saved right now.
  Nothing was saved.“ — vorher schlug der ganze Agent-Turn mit der
  irreführenden Provider-Meldung fehl. Eine Nachricht, die nur
  ums Merken/Vergessen bittet, nutzt das Tool `update_memory` und antwortet
  danach mit kurzem Klartext; auch jede andere Antwort ohne Vergleich speichert
  bei Bedarf über `update_memory` (`MEMORY_WRITE_PROMPT`: erst speichern, dann
  antworten). Mit Vergleich fährt die Pflichtentscheidung `memory` auf
  `compare_models`/`check_text`
  (`memory_field`; jeder weitere Vergleich derselben Nachricht übergibt `[]`,
  die erste Entscheidung gilt). Von 2026-10-11 bis 2026-10-14 saß sie auf dem
  `answer`-Tool des getrennten Antwortschritts.
  Seit 2026-10-12 nimmt das Feld jede Form an (`_memory_changes`: `null` oder
  unlesbarer Text = keine Änderung, ein Objekt = eine Änderung, ein Eintrag ohne
  Objekt = eine Änderung, die `apply` sichtbar ablehnt); vorher scheiterte der
  ganze Aufruf. Angewandt wird es nach dem Werkzeug (`DelegationLoop._execute`),
  nie bei einem abgelehnten Vergleich (`status: refused` oder Toolfehler).
  Serverseitige Verträge: (1) jede Agent-Änderung trägt `evidence`, ein
  wörtliches Zitat, das in einer **Nutzer**-Nachricht des Chats vorkommen muss
  (`evidence_matches`, normalisiert nur Groß-/Kleinschreibung, Leerraum,
  typografische Anführungen; seit 2026-10-07 mindestens `MIN_EVIDENCE_CHARS` = 12
  Zeichen, kürzere Zitate nur als ganze Nachricht). Seit 2026-10-08 zählt ein
  per „Ask about this“ zitierter Antwortabsatz nicht als Nutzerwort:
  `user_words` schneidet ihn genau in dem Format ab, das `composer-quote.js`
  anhängt (gemeinsamer Vertrag `tests/fixtures/composer_quote_format.json`,
  in Python und vitest geprüft; eine reine „Please comment on this
  passage…“-Nachricht fällt ganz weg; die Modelle sehen die Frage
  unverändert). Seit 2026-10-12 entfernt `MemoryTools._user_messages` auch Links
  (`_LINK`): eine gelesene Seite kennt ihre eigene URL und hätte sie als
  „Zitat“ des Nutzers angeben können. Die Garantie ist genau: der Server belegt, dass der Nutzer die
  zitierten Worte geschrieben hat, nicht, dass der Memory-Text dasselbe sagt
  (Wortüberlappung würde sprachübergreifende Saves fälschlich ablehnen).
  Text aus Webseiten, Dateien, Mails oder Tool-Ergebnissen kommt also nicht
  mit seinem eigenen Zitat ins Gedächtnis; ein davon gelenkter Orchestrator
  könnte aber eine umformulierte Erinnerung mit passenden Nutzerworten
  belegen — Settings › Memory (Bearbeiten, Löschen, Undo) ist der Rückhalt (Memory-Poisoning); (2)
  `looks_like_secret` weist Keys, Passwörter, Karten- (Luhn) und IBAN-Nummern
  für jede Herkunft ab; (3) `FirestoreAgentMemoryRepository.apply` prüft in
  derselben Transaktion Tombstone, `auto_memory`/`enabled` und dass der Turn
  noch `pending` ist, schreibt alles-oder-nichts, dedupliziert gleiche Texte
  (No-op) und hängt eine Kurzfassung an `turn.agent_memory`
  (`{change_id, op, item_id, undone}`, höchstens 12 je Turn, über
  `chat_store`-Allowlist im Turn-View; seit 2026-10-08 **ohne** `text`, damit
  eine später gelöschte Erinnerung nicht in jedem Chat weiterlebt — der
  Hinweis zeigt nur während des Laufs und bekommt die Texte aus dem
  SSE-Event, Undo braucht nur `change_id`). Jede angewandte Änderung geht live als
  SSE-Event `memory` (`{changes: [...]}`, mit Text) an den Browser. Gelesen wird pro Turn
  genau einmal (`snapshot`: Profil + Einträge in einem `get_all`, fail-open,
  bewusst ohne prozessweiten Cache, damit gelöschte Erinnerungen sofort aus dem
  nächsten Prompt verschwinden). Prompt: `orchestrator_prompt` hängt
  Memory-Daten plus die passende Regel (schreiben / nur lesen / pausiert /
  seit 2026-10-08 getrennt: nicht lesbar = `MEMORY_UNAVAILABLE_PROMPT`, statt
  einem eingeschalteten Nutzer „pausiert“ zu melden) **ans
  Ende** des System-Prompts; der Agent schreibt die Antwort mit genau diesem
  Block (bis 2026-10-14 bekam ein getrennter Antwortschritt die Daten über
  `synthesis_prompt` ohne IDs und Schreibregeln). Balance (Max' Vorgabe):
  `MEMORY_RELEVANCE_RULES` im Agent-Prompt (`MEMORY_USE_PROMPT`) — eine
  Erinnerung zählt nur, wenn sie die Antwort gegenüber einem Fremden ändert,
  wird still angewendet und nur aus drei Gründen ausgesprochen (Nachfrage,
  sonst unverständliche Auswahl, Konflikt/veraltet), dann höchstens ein
  Halbsatz; Schreiben nach dem Test „bessere Antwort in einem künftigen,
  fremden Chat?“, `[]` ist der Normalfall. Vergleichsmodelle sehen Memory nicht
  pauschal: der Orchestrator gibt relevante Punkte im `compare_models`-Kontext
  weiter (gegen den gemeinsamen Bias, siehe Deckel oben). `/ask_*` rendert die
  Einträge über `render_profile(items=...)` nach der Notiz — seit 2026-10-08
  innerhalb des dokumentierten Deckels (`MAX_PROFILE_CHARS` +
  Stufen-Notizgrenze): höchstens `MAX_ITEMS_PROMPT_CHARS` = 3.000 Zeichen,
  neueste zuerst, vor der Notiz reserviert (vorher bis 100 × 300 Zeichen
  zusätzlich an alle sechs Modelle).
  Endpunkte (users.py): `GET /api/my/memory` liefert zusätzlich `items`,
  `items_revision` und `limits.items/item_chars`; `PUT` nimmt `auto_memory`
  (fehlt das Feld, bleibt der gespeicherte Wert — alte Browser setzen ihn nicht
  zurück); `POST /api/my/memory/items` (`changes` ≤ 20, `expected_revision`,
  antwortet seit 2026-10-20 mit `change_id` der Änderung, damit auch eine von
  Hand gelöschte Erinnerung ein Undo hat; 409 `revision_conflict` mit
  Revision; scheitert nach dem Schreiben nur das
  erneute Lesen der Liste, antworten alle drei Schreib-Endpunkte trotzdem
  `success` mit `items_stale: true` statt 503, und der Browser lädt die Liste
  separat nach), `DELETE /api/my/memory/items` (löscht
  Einträge **und** Undo-Log), `POST /api/my/memory/changes/{id}/undo` (stellt
  nur wieder her, solange jeder betroffene Eintrag exakt im Nachher-Zustand ist,
  sonst 409 `undo_conflict`; idempotent; markiert `turn.agent_memory` als
  `undone`). UI: `user-memory.js` zeigt Schalter `#memoryAutoSwitch` (bei pausiertem
  Memory nur noch ausschaltbar, nicht einschaltbar; speichert sofort nur sich
  selbst), die Liste
  `#memoryItemsSection` mit Bearbeiten/Löschen/Hinzufügen und zweistufigem
  „Delete all“ (Löschen zeigt „Memory deleted · Undo“ über `App.toast` und
  nimmt es über `/changes/{change_id}/undo` zurück; ein geleertes Feld löscht
  nicht, „Save“ wartet auf Text, Apple-Audit E9); `agent-memory.js` (`App.agentMemory.render/receive`) zeigt
  „Memory updated“ mit Undo und „Manage memory“ (öffnet Settings, Memory ist
  der erste Reiter) nur WÄHREND des laufenden Agent-Laufs; `render` ohne
  `running` (fertige, wiedergeöffnete, Verlaufsantwort) entfernt den Hinweis,
  die Aktivitätszeile „Updated memory“ und Settings behalten den Nachweis.
  Seit 2026-10-07 zeigt `App.agentMemory.nudge` Konten ohne „Let Agent update
  memory“ ab der zweiten fertigen Agent-Antwort in diesem Browser unter
  höchstens drei Antworten eine Zeile mit „Turn on“/„Not now“
  (`localStorage` `consensio.memoryHint.v1`: answers/shown/off). Seit
  2026-10-08 entscheidet nur `agent_settings.memory.hint === true` des fertigen
  Live-Turns (kein Extra-Read; `MemorySnapshot.settings()`: Memory lesbar,
  nicht pausiert, Opt-in aus). `auto === false` allein reichte vorher und
  traf auch bewusst pausierte Konten und Turns mit fehlgeschlagenem Read;
  ältere Turns ohne Marke zeigen nichts. „Turn on“ lädt über
  `App.userMemory.enableAgentMemory()` zuerst frisch (`load(true)`, ein
  ungespeicherter Entwurf bleibt) und setzt nur „Let Agent update memory“;
  ein pausiertes Memory schaltet es nie mehr still wieder ein (Profiltexte
  bleiben). Settings lädt beim Öffnen jedes Mal frisch (`load(true,
  {keepDraft})`), damit Schalter und Revision aus einem anderen Tab nicht
  veralten. „Not now“ und
  jedes Speichern der Schalter in Settings beenden den Hinweis
  (`dismissNudge`). Wiedergeöffnete Antworten zeigen ihn nicht. Die Texte
  versprechen kein dauerhaftes Undo unter der Antwort mehr, sondern verweisen
  auf Settings › Memory.
  `consensio:memory-changed` lässt eine geladene Settings-Liste nachladen.
  `MOCK_LLM`: eine Agent-Frage „Remember: <Fakt>“ speichert den Fakt, damit der
  Ablauf ohne Provider im Browser prüfbar ist.
- **Agent-Watch (`app/services/agent_watch.py`, `agent-watch.js`, seit
  2026-10-11)**: Der Agent legt keine Watch an, er bereitet sie vor, auch auf
  „erinnere mich, wenn …“ (`ORCHESTRATOR_PROMPT` nennt Erinnern; eine Watch ist
  der einzige Weg, den Nutzer später zu erreichen).
  `prepare_watch` (registriert nur in Account-Mode-Turns mit Vergleich und ohne
  Google-Daten, `DelegationLoop(google_data=…)`) prüft Frage/Ziele/Intervall,
  fragt lesend `watch_service.creation_outlook` (schon beobachtet: jede Watch
  mit gleichem `question_hash`; freie Slots; Daily) und speichert einen
  Vorschlag als `turn.agent_watch` (`question` ≤ 200, `goals[≤3]`, `interval`;
  nur bei `pending`). Den Kartenhinweis (Antwort endet mit einem Satz zur
  Karte; `already_watched`/`limit_reached` stattdessen benannt) trägt
  `ORCHESTRATOR_PROMPT` selbst, den Status sieht der Agent im Toolergebnis (bis
  2026-10-14: `prepared_watch` in der Evidenz des getrennten Antwortschritts
  plus `SYNTHESIS_PROMPT`); kein eigenes SSE-Event. `App.agentWatch.render(body,
  {key, proposal})` zeigt die Karte unter einer abgeschlossenen Antwort
  (`agent-chat.js` reicht den Vorschlag nur bei `status: completed` durch):
  „Start watching“ = `POST /api/watch` mit `App.watchUi.watchDefaults`
  plus Frage und erstem Ziel, „Adjust“ = `openWatchDialog("create", {question,
  goals, goal, interval, source: "agent"})`. Den Zustand (watching/paused/
  resolved/full) liest die Karte über `App.watch.watchedFor` und
  `App.watchState.limits` und folgt `consensio:watches-changed`, das
  `watchUi.receiveWatchList` bei jeder Antwort von `/api/my/watches` sendet
  (Dialog, Hinweis, Dashboard). Ein Turn mit
  Vorschlag bekommt keinen `offerWatch`-Hinweis. Ablauf und Begründung:
  [agent-mode.md](agent-mode.md) „Watch vorschlagen“. `MOCK_LLM`: „Watch:
  <Frage>“ bereitet einen Vorschlag vor.
- **Agent-Einstellungen (`app/services/agent_settings.py`, `agent-settings.js`,
  seit 2026-10-17)**: Auf „stell X um“ schreibt der Agent keine Einstellung, er
  bereitet sie vor. Zwei Werkzeuge, registriert auf jedem Account-Mode-Turn
  mit Vergleich, auch mit Google-Daten (nur aufgezählte Werte):
  `read_settings` (ohne Argumente; ein leerer Argument-String gilt in
  `ToolRegistry.validate` als `{}`) liefert, was für die nächste Nachricht
  gilt (Modell/Stufe vom laufenden Turn, Vorlieben aus
  `comparison.preferences`, Preset und Anzeige aus dem Kontodokument, einmal
  pro Turn gelesen, unlesbar = Standard), die Standards und die Wahl des
  Kontos samt Pro-Sperren, seit 2026-10-22 auch die Vergleichsmodelle mit
  Namen: `models_this_message` (was die Seite für diese Nachricht schickte,
  auch Custom) und `models_per_lineup` (jede Aufstellung aus
  `CONSENSUS_PRESET_MODELS`; live konnte der Agent nicht sagen, wie viele
  Modelle „Daily“ fragt); damit beantwortet der Agent „was ist eingestellt?“
  und fragt bei unklaren Wünschen („schneller“, „GPT“) mit echten Optionen
  zurück, statt zu raten (`ORCHESTRATOR_PROMPT`). `prepare_settings_change`
  nimmt eine Liste `changes: [{setting, value}]` (nur das Genannte, jede
  Einstellung einmal, Werte je Einstellung geprüft; eine Probe mit neun
  optionalen Feldern ließ Claude alle mit erfundenen Werten füllen; Objekt-,
  `name: wert`- und JSON-String-Formen liest ein `model_validator`, leere
  Werte fallen weg; Auto zählt bei der Stufenwahl mit der Stufe, auf der es
  läuft, `_Choice.strength`):
  Chatmodell (Name, wie der Nutzer ihn nennt: exakt, enthalten oder
  alle Wörter; mehrdeutig/unbekannt = Ablehnung mit Treffern bzw. ähnlichsten
  Namen, nie geraten), Reasoning (Stufe oder `higher`/`lower`), Tiefe,
  Antwortstart, Agent-Freiheit, Antwortprüfung (`answer_check` →
  `agent_preferences.judges`), Vergleichs-Preset und die drei
  Anzeige-Schalter. Es prüft mit denselben
  Regeln wie `POST /agent` (`agent_model_options()`: `premium`,
  `reasoning_efforts`, `free_default_effort`; `PRO_REASONING_EFFORTS`;
  `pro_only` der Presets; Pro = `is_user_pro` wie im Picker, ohne Admin; in
  Chats mit Google-Daten zusätzlich `restricted_model`; nach Fremdinhalten
  (`memory_locked`) nur mit `evidence`-Zitat aus der neuesten Nachricht): ein
  Premium-Modell ohne Pro wird abgelehnt (mit den freien Modellen derselben
  Familie), eine zu hohe Stufe auf die höchste erlaubte begrenzt, eine nicht
  angebotene auf die nächstgelegene (Gleichstand: die leichtere), Auto ohne
  Pro als Medium vorgeschlagen; ein Modellwechsel behält eine angebotene
  Stufe, sonst Auto. Ergebnis je Änderung `prepared|adjusted|refused|unchanged`
  mit Grund; Gesamtstatus `prepared` nur, wenn alles wie verlangt vorbereitet
  ist (sonst schreibt `_side_results_accepted` eine mitgeschriebene Antwort
  neu). Was schon gilt, ist `unchanged` und kommt nicht auf die Karte.
  Gespeichert wird nur bei mindestens einer Änderung, als
  `turn.agent_settings_proposal = {settings: {name: wert}, notes:
  {agent_model: grund}}` in Kontoform (vorher durch
  `user_settings.validate_changes`), nur bei `pending`; mehrere Aufrufe eines
  Turns addieren sich (ein späterer Wert gewinnt, eine nun als gültig erkannte
  Einstellung verlässt die Karte). Systemprompt, Memory,
  Datenschutz, Verbindungen, Benachrichtigungen und Konto stehen bewusst
  nicht im Schema. `App.agentSettings.render(body, {key, proposal})` zeigt die
  Karte unter einer abgeschlossenen Antwort (nach Memory-Hinweis und
  Watch-Karte): je Zeile „jetzt → neu“, „jetzt“ aus dieser Seite beim Rendern
  (`App.agentChat.pick()`/`modelLabel`, `App.agentPreferences.get()`,
  `App.activeConsensusPresetId()`, `App.userSettings.get`), Gleiches fällt
  weg (fährt der Chat das Modell schon, Zeile „Chat model in new chats“);
  nichts mehr offen = „Settings in place“. „Apply“ übernimmt nur die
  bekannten Einstellungen: das Modell über `App.agentChat.applyPick` (wie der
  Picker: dieser Chat und die Kontowahl, sonst bliebe ein offener Chat auf
  seinem Modell; löscht den Neuer-Chat-Entwurfsslot; `false`, wenn
  `effortFor` die Stufe ändern würde), den Rest über
  `App.userSettings.set(…, {source: "agent"})`, damit die Besitzer-Module ihn
  sofort anzeigen; gespeichert wird per PATCH wie jede Änderung. Übernommen
  oder „Dismiss“ merkt sich die Karte pro `chat:turn` (Live- und
  Verlaufsansicht nutzen denselben Schlüssel) in localStorage
  `consensio.agentSettingsCards.v1` (≤ 100). Die Aktivitätszeile liest
  `outcome` (`SettingsTools.activity`). `claim_counts` heißt im Werkzeug
  `on`/`off` (ein Modell schickte `"false"` als Text). Begründung: [agent-settings-evaluation-2026-10-17.md](agent-settings-evaluation-2026-10-17.md).
  `MOCK_LLM`: „Settings: depth=quick, reasoning=low“ bereitet das vor.
- **`math-render.js`** — gemeinsame KaTeX-Brücke für App und öffentliche
  Share-/Watch-Seiten. Bewahrt `\[...\]`/`\(...\)` durch den Markdown-Pass und
  exponiert `window.ConsensusMath.{prepareMarkdown,stripMath,render}`.
  **KaTeX nur bei Formel (seit 2026-10-18):** Share-, Watch- und Topic-Seiten
  binden `templates/partials/katex.html` ein. Das Stylesheet und die beiden
  KaTeX-Skripte stehen nur dann im HTML, wenn der Jinja-Global
  `page_has_math()` (`app/core/math_assets.py`, registriert über
  `register_asset_globals`) im Template-Kontext eine Formel findet; die
  Prüfung ist absichtlich eine Obermenge dessen, was `render()` setzt. Das
  Meta-Tag `katex-assets` nennt die Dateien immer: Findet `render()` eine
  Formel ohne geladenes KaTeX, lädt es CSS + Skripte einmal nach
  (`async=false`, Reihenfolge wie `defer`) und setzt danach alle wartenden
  Blöcke. Seit 2026-10-20 auch `/app` (Apple-Audit B12): `index.html` trägt
  nur das Meta-Tag, KaTeX lädt beim ersten Formel-Treffer im Stream oder in
  einer gespeicherten Antwort, nicht mehr bei jedem Start.
  Innerhalb einer Formel ist Markdown Notation, kein Markup: Backslashes und
  alle ASCII-Satzzeichen werden geschützt; insbesondere bleibt ein einzelnes
  `=` in mehrzeiligen Formeln Formelinhalt statt Setext-Überschrift. Derselbe
  Schutz gilt serverseitig in `public_markdown.py` für Share-/Watch-Seiten.
  Ohne Escape-Schutz verschluckt `17{,}5\%` → `17{,}5%` als
  TeX-Kommentar das Ergebnis. `$...$` wird nur dann als Formel gelesen, wenn
  der Inhalt ohne Leerzeichen an beiden Dollarzeichen liegt, in einer Zeile
  bleibt und ein LaTeX-Signal trägt — „6,7 Mrd. $ in Q1“ bleibt Betrag.
  Die Regex dafür kommt ohne Lookbehind aus: Safari/iOS unter 16.4 kann ihn
  nicht parsen und verwarf damit das ganze verkettete App-Bundle
  (`tests/js/frontend-syntax.test.mjs` verbietet `(?<=`/`(?<!` im Frontend).
  `stripMath()` liefert die formelfreie Fassung eines Satzes; die Ankersuche
  braucht sie, weil eine gerenderte Formel im DOM ein übersprungener
  `.katex`-Block ist, der Anker aber den LaTeX-Quelltext trägt.
  `wrapBareLatex()` repariert die Anzeige gespeicherter Anker aus älteren
  Läufen, in denen die Zeile *zwischen* den `$$` als eigener „Satz" landete:
  nur wenn außer LaTeX nichts im Anker steht, wird er nachträglich als Formel
  gesetzt — ein einziges Wort Text lässt ihn Text bleiben.
- **`markdown-stream.js`** — Markdown-Rendering (`injectMarkdown`, `morphMarkdown`,
  `renderMarkdownStream`, `keepTextSelection`, ein Parse je Render über
  `renderMarkdownFragment`) + SSE-Helfer
  (`createStreamRenderer`, `streamSSERequest`; eine `id:`-Zeile wird als zweites
  Argument an `renderer.receive(data, id)` gereicht, nur wenn vorhanden); setzt LaTeX nach jedem
  gedrosselten Streaming-Render über `window.ConsensusMath`. Fehlt `marked`
  oder `DOMPurify` nach einem Asset-Ladefehler, rendert es sicher als Plaintext
  und meldet den degradierten Zustand, statt eine Promise-Rejection auszulösen.
  `injectMarkdown(el, md, evidenceSources?)` akzeptiert optional turnbezogene
  Quellen; ohne dritten Parameter gilt weiter `window.currentEvidenceSources`.
  **Checklisten (seit 2026-10-21):** `- [ ] Punkt` / `- [x] Punkt` werden zu
  Kästchen. marked zeichnet das Kästchen als Formularfeld, das
  `MODEL_HTML_CONFIG` zu Recht verbietet (vorher verschwand es, der Punkt las
  sich als normaler Spiegelstrich); `ensureTaskMarkers` lässt marked (einmal
  je Instanz, per `marked.use`) stattdessen `span.md-task[data-checked]`
  schreiben, `enhanceTaskLists` macht daraus nach dem Sanitizer einen
  `button.md-task-box[role=checkbox][aria-checked]` (aria-label = Wortlaut
  des Punkts), `li.md-task-item`, Liste `.md-task-list`. Nur ein Marker am
  Anfang seines Listenpunkts wird ein Kästchen, jeder andere fällt weg. Neue
  Kästchen sind `disabled`; nach jedem Schreiben (`injectMarkdown`,
  `morphMarkdown`, `renderMarkdownStream`, `createStreamRenderer`) ruft
  `syncTaskBoxes(el)` `App.taskChecks.apply(el)`. Im Stream hält
  `holdOpenTask` eine Zeile `- [` / `- [x` zurück (kann noch ein Link werden),
  `- [ ]` steht sofort als Kästchen. Optik in `shell.css` (im Spiegelstrich-
  Listen steht das Kästchen an der Stelle des Punkts, die Wörter behalten ihre
  Spalte; nummerierte Listen behalten die Zahl), öffentlich `.share-md`.
- **`task-checks.js`** — `App.taskChecks` (`scope`, `apply`, `flush`), lädt nach
  `markdown-stream.js`. Abhaken geht nur in der Antwort eines **gespeicherten,
  fertigen Turns**: die Render-Stelle nennt ihn vor dem Schreiben per
  `scope(el, {chatId, turnId, checked})` (`data-task-turn`/`data-task-chat` am
  Antwort-Element: `#agentAnswerBody` in `agent-chat.js` für gespeicherten und
  fertigen Live-Turn, `#consensusAnswerBody` in `run-view.js` über
  `completedBasis`, Verlaufs-Turns in `consensus-run.js::buildHistoryTurn`;
  wandert der Live-Turn in den Verlauf, nimmt das Element die Attribute mit).
  Ohne Turn (Einzelantworten im Leser, laufende Antwort) bleiben Kästchen
  `disabled`. Gezählt wird die Reihenfolge der Kästchen dieser Antwort (nicht
  in einer darin verschachtelten `.consensus-answer-body`). Ungetickt zeigt
  ein Turn das Geschriebene (`[x]` angehakt); ab dem ersten Klick gilt die
  Liste. Klicks auf dieser Seite gewinnen über später gerenderte, ältere
  Turn-Daten. Speichern: 600 ms nach dem letzten Klick die ganze Liste per
  `PUT /chats/{chat}/turns/{turn}/task-checks` (eine Anfrage je Turn
  gleichzeitig, Wiederholung nach 2 s/8 s bei Netz/401/408/429/5xx, beim
  Verstecken des Tabs `keepalive`).
- **`stream-reveal.js`** — `App.streamReveal` (`active`, `stream`, `settle`,
  seit 2026-10-22): Takt und „Licht“ einer gestreamten Agent-Antwort, Ablauf
  unter „Agent-Laufoberfläche“. `active()` ist nur mit CSS Custom Highlight API,
  ohne `prefers-reduced-motion` und ohne ausgeschaltete Kontoeinstellung
  `letter_animations` (Settings → Display → Letter animations, seit 2026-10-23)
  wahr; sonst malt `agent-chat.js` wie vorher jeden Frame, was angekommen ist.
  Ausschalten mitten im Stream: der direkte Maler schreibt, das Modul gibt die
  Antwort über `_markdownWrites` ab. Tests: `tests/js/stream-reveal.test.mjs`.
- **`sources.js`** — Quellen/Evidence-Mapping; nutzt DOM-Datasets
  `dataset.consensusAnswer` / `dataset.consensusSources`; `window.currentEvidenceSources`.
  Zwei Darstellungen: **im Chat-Fliesstext** (Container ist bzw. liegt in
  `#consensusAnswerBody`, `.consensus-answer-body` oder der Kernaussagen-Liste)
  werden `[S3]`-Tags seit 2026-10-01 zu **Quellen-Pillen** `.src-ref` statt
  hochgestellter Zahlen (User-Entscheidung): Favicon (14 px, über den eigenen
  Proxy `/api/topics/favicon`, kein Drittanbieter im Browser) + kurze Domain
  ohne `www.` auf der Grundlinie, `--well`-Fläche, Radius voll, lange Domains
  mit Ellipse. Scheitert das Favicon, steht derselbe Globus wie auf den
  öffentlichen Seiten im selben Kasten (`.src-ref-glyph`, leer, von CSS
  gemalt; vorher ein 8,5-px-Buchstabe). **Ein Bauteil für App und öffentliche
  Seiten (seit 2026-10-20, Apple-Audit G9):** `static/css/source-pill.css`,
  importiert von `style.css` und `public-pages.css`, trägt das Site-Icon
  (abgerundetes Quadrat, Radius = ein Viertel der Seite, Logo auf heller
  Platte `--site-icon-plate`, dunkel `#e9e9e7`, damit schwarze Marken sichtbar
  bleiben; `--site-icon-size` 14 px im Text, 20 px am Kopf einer Listenzeile;
  fehlend der Globus `--globe-mask`) und die Zitat-Pille für `.src-ref`,
  `.source-link` (rohe Modellantworten) und `.share-md a[href^="#src-"]`
  (öffentliche Antwort). Klassen: `.site-icon`, `.src-ref-favicon`,
  `.source-favicon`, `.source-teaser-favicon`, `.wd-source-icon`,
  `.wp-ref-icon`, `.wp-link-icon`, `.share-source-favicon`,
  `.answer-reader-site-icon` (Leser, jetzt 20 px statt 36-px-Kachel, Fallback
  `.site-icon-fallback`). Keine andere Datei setzt Größe, Radius oder Tönung
  eines Site-Icons oder einer Pille (Test in `tests/test_material_tokens.py`). Benachbarte Tags (`[S1, S2]`, `[S1][S2]`) werden
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
  Snippet); bei einer Gruppen-Pille eine Zeile je Quelle. Eine Pille, die ihre
  Quelle selbst trägt (`sourceData`), braucht dafür keine Nummer (die Quellen
  eines Schritts in der Agent-Aktivität); dann entfällt die Ziffer. Der Teaser ist ein
  Tooltip; zum Öffnen gibt es seit 2026-10-20 (Apple-Audit F6)
  `window.App.sourceSheet` (`sources.js`, `#sourceSheet`, `{open(pill,
  {asModal}), close, isOpen}`): auf Touch öffnet schon der erste Tipp auf
  jede Pille die Liste aller Quellen dahinter (eine einzelne mit Auszug),
  jede Zeile ein Link in neuem Tab, 44 px hoch; am Handy (≤ 768 px) als Karte
  in der Bildmitte über dem Scrim (Backdrop mit `.claim-sheet-backdrop`, also
  dieselbe Bewegung, Scroll-Sperre und `touch-action`), sonst als Popover an
  der Pille. Mit Maus oder Tastatur öffnet eine Gruppen-Pille dieselbe Liste
  an der Pille (erste Quelle fokussiert, Pfeile, Escape gibt den Fokus an die
  Pille zurück); eine einzelne Pille öffnet ihre Quelle wie bisher. Teil von
  `App.popover` (ein offener Layer), Bewegung aus `overlays.css`. Steht die
  Pille in einem offenen `<dialog>` (der Antwortleser ist modal), hängen Liste
  und Backdrop in diesem Dialog, das Popover dann `position: fixed`; auf
  `<body>` lagen sie inert unter dem Top-Layer (Nachprüfung 2026-10-21).
  Die Liste geht mit diesem Dialog: ein haltbares `cancel` (Android-Zurück)
  schließt zuerst nur sie (wie Escape), jedes `close` des Dialogs (Kreuz,
  nicht haltbares Zurück, Layoutwechsel modal ↔ angedockt ↔ direkt) schließt
  sie mit; den Fokus gibt dann der Leser an seinen Knopf zurück, nur ein
  verlorener Fokus geht an die noch sichtbare Pille. Vorher hielt der
  Backdrop im geschlossenen Dialog die Seite gesperrt (Nachprüfung 2 N1).
  Copy consensus/Copy citation lesen Pillen über
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
  Dateien ohne Text sind seit 2026-10-22 eine Nachricht: `messageText()`
  liefert die Namen der sendbaren Anhänge, und `agent-chat.js` `send` sowie
  `window.sendQuestion` schicken sie als Frage (Server, Verlauf und Titel
  brauchen eine; ein Dateiname ist der eigene Inhalt des Nutzers, keine
  untergeschobenen Worte). `updateQuestionInputAccess` gibt Senden im
  Agent-Modus schon mit Anhang frei (live tippte ein Nutzer „.“, um einen
  Screenshot zu schicken).
  `window.pendingAttachments`, `getAttachmentsPayload`,
  `window.App.attachments.{detachForMessage,messageMeta,renderMessageAttachments}`.
  `messageMeta()` liefert dieselben Metadaten, ohne die Dateien abzugeben: die
  Blase der gerade abgeschickten Frage (`#threadPendingAsk`) zeigt die Chips
  schon, waehrend der Composer die Daten noch haelt — ein Lauf, der nicht
  stattfindet, gibt Text UND Anhänge unveraendert zurueck. Solange sie schwebt,
  blendet `body.thread-message-pending` den Composer-`#attachmentBar` aus,
  damit dieselben Chips nicht zweimal dastehen.
- **`user-settings.js`** (Head-Bundle, erste Datei) — `App.userSettings`:
  **einziger Besitzer der Kontoeinstellungen** (Modus, Agent-Modell und
  -Einstellungen, Check sources, Modellauswahl, System-Prompt, drei
  Display-Optionen): lokale Kopie, Migration alter Speicherformate und Abgleich
  mit `/api/my/settings`; siehe §4 „Kontoeinstellungen“. Kein DOM.
- **`run-mode.js`** (Head-Bundle, nach `user-settings.js`, vor `app-bootstrap.js`) —
  **einzige Quelle** der Moduswahl Compare / Consensus / Agent (Kontoeinstellung
  `run_mode`); siehe „Modus: Compare, Consensus, Agent". Kein DOM;
  `agent-mode.js` rendert den Wähler.
- **`agent-mode.js`** — gruppiertes Lauf-Panel (Status-Hub, Timer; die Namen
  „agent-mode" sind historisch und meinen den Consensus-Lauf, nicht Agent Beta),
  der Moduswähler `#runModeSelect` samt Settings-Spiegel `#runModeSetting` und
  die Composer-Werkzeugleiste `#composerModeBar` direkt unter dem Input:
  Reasoning (`#composerReasoningToggle`), Upload-Shortcut und
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
  Seit 2026-07-27 war das Panel `#agentModePanel` als **Fortschrittsanzeige
  stillgelegt** (nur per CSS ausgeblendet): zwei Progress-UIs fuer einen
  Request waren genau der Ueberschuss, den der gefuehrte Lauf abbaut. Seit
  2026-10-05 sind Markup, Panel-CSS, der 1-Hz-Timer und das Chip-Rendering
  ganz entfernt; `getActiveAgentModels()` speist nur noch
  `answerReader.syncPreview`, `setAgentModeStatus` haelt Status und Body-Klassen.
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
  Der 200-ms-Ticker bewegt seit 2026-10-15 nur Uhr und Modellzeilen
  (`renderDetail`: Fuellung aus dem Stream, Skip-Angebot); Schritte, Zaehler und
  `#runNote` rendert der MutationObserver bei `data-response-state`,
  `data-response-error`, `data-response-skipped` und `class`. In einem
  versteckten Tab (`document.hidden`) laeuft kein Ticker; `visibilitychange`
  zeichnet beim Zurueckkommen sofort nach (die Uhr zaehlt ab `startedAt`).
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
  onQueryStatus,onConsensusStart,onConsensusText,onDifferencesStart,onConsensusEnd,
  renderProvenance,dismiss}`. `onPrepare` kommt aus `query-send.js` **vor**
  `/prepare`, `onDifferencesStart` aus dem ersten `differences.delta`
  (`consensus-run.js`). Seit 2026-10-09 weicht die Karte, sobald Konsens-Text
  existiert (`run-view.js::syncPipeline` → `onConsensusText()` → `hideNow()`),
  solange darunter noch nichts steht; vorher klappte sie ~0,7 s nach der
  fertigen Antwort zu und zog sie 100–130 px hoch. Der Lauf lebt in der
  Provenienzzeile weiter.
- **Composer-Hoehe** — `composer-autosize.js` liegt seit 2026-10-20 im
  `head`-Bundle (vor `app-bootstrap.js`): `App.sizeQuestionInput(input,
  {instant})` misst und setzt die Hoehe ohne Listener, damit
  `app-bootstrap.js` einen wartenden Entwurf vor dem ersten Paint groessen kann.
  `App.initComposerAutosize` (app-init.js) installiert die Input-/Viewport- und
  Placeholder-Listener; `App.resizeQuestionInput()` bleibt der explizite,
  synchrone Trigger. Tippen misst einmal pro Frame (rAF, nach allen
  Schreibzugriffen des Tasks, Apple-Audit D3) und darf im Hero weich wachsen
  (`transition: height` nur fuer `body.is-hero`); jede andere Hoehe wird ohne
  Transition gesetzt.
  CSS-Min-/Maxhoehe bestimmen Wachstum und internen Scrollbereich. Mehrzeilige
  Eingaben behalten ihre Form bis zum Leeren. Ein ResizeObserver verfolgt zudem
  die tatsaechliche Feldbreite waehrend Sidebar-/Viewport-Transitionen und misst
  pro Animationsframe hoechstens einmal nach. Reine Hoehenmeldungen werden
  ignoriert, damit eigene Schreibzugriffe keine Schleife erzeugen. So bleibt
  nach einer schmalen Zwischenbreite kein ueberhohes leeres Feld stehen.
  Gemessen wird in einem versteckten Zwilling (`textarea.input-field-twin` am
  Body-Ende, `aria-hidden`, `contain: layout style`) mit den Groessen-Styles
  des Feldes: das Feld selbst schrumpft nie fuer die Messung, die Seite wird nie
  kuerzer (Apple-Audit A12) und die Hoehe hat einen Startwert zum Gleiten (B5).
  `tests/js/composer-autosize.test.mjs` prueft diese Ereignisgrenzen; der Smoke-
  Browserfall prueft echtes Layout inklusive der abgeschlossenen Transition.
- **Hero ↔ Thread gleitet (2026-10-03)** — `.input-section` hat keine
  `transform`-Transition mehr: die Hero-Zentrierung `translateY(… - 50%)` liess
  das Feld bei jeder Höhenänderung und beim Ausstieg von falscher Stelle
  gleiten (beim Ausstieg von unterhalb des Bildschirms herauf).
  `App.glideComposer(change)` (app-core.js) misst die Box vor dem
  Klassenwechsel (beim Senden schon am Anfang des Klicks: `App.anchorGlide()`
  aus `query-send.js`, D3), liest die neue Lage im nächsten Frame und animiert
  die Differenz per WAAPI-`translate` (420 ms); `exitHeroMode`,
  `enterDirectComparisonView` und „New chat“ nutzen es. Seit 2026-10-20 ist es
  eine Bewegung auch für die Form (Apple-Audit C2): die Höhe der Box läuft mit
  (`.chat-input-container.is-morphing`, Bedienzeile an der Unterkante); beim
  Verlassen des Starts wandert die Unterkante (der Thread-Composer steht unten),
  beim Zurückkehren die Oberkante. Die Werkzeugleiste blendet unter dem Feld
  aus (`#composerModeBar.is-leaving`, aus dem Fluss, 150 ms), die Begrüßung
  über `visibility` in der Transition, der Hinweis des leeren Feldes kommt am
  Ende. `body.composer-gliding` hält dabei `composer-collapse.js` (keine eigene
  Höhenanimation) und die Thread-Reserve still; ein zweiter Aufruf ohne
  Grenzwechsel lässt eine laufende Bewegung in Ruhe. Die Agent-Demo
  tippt im Hero und verlässt ihn erst beim simulierten Absenden.
  `html { scrollbar-gutter: stable }` (shell.css) hält die Spalte beim
  Erscheinen der Scrollleiste still; die Agent-Spalte zentriert über `100%`
  statt `100vw` und steht damit exakt wie der normale Thread.
- **Erstes Bild von `/app` = Endzustand (seit 2026-10-20, Apple-Audit B1, B2,
  B4, B6, B10, B11, B13)** — `app-bootstrap.js` zeichnet vor dem ersten Paint,
  was die Module später zeichnen, und die Module übernehmen es statt es zu
  ersetzen. Gemeinsame Bausteine:
  `App.expectedSession()` → `{known, account, verified, uid}` (vor Firebase aus
  `id_token`, Firebases eigenem `localStorage`-Nutzer
  `firebase:authUser:<apiKey>:[DEFAULT]` und `consensio.googleRedirectPending`;
  danach die Antwort; `app-init.js` nutzt es für Gast-Composer und Sidebar.
  Endet die erwartete Sitzung (Firebase meldet `null`), zeichnet `firebase.js`
  das Feld nach `publishAuthState(null)` neu und `agent-chat.js` die Shell
  bei `consensio:auth-state`; vorher blieb das Feld gesperrt mit Agent-Chip
  unter „Log in“ stehen, Nachprüfung 1);
  `App.isGuest()` (seit 2026-10-21, die eine Gast-Regel: niemand angemeldet
  oder erwartet und der Login erreichbar; eine unbestätigte Anmeldung ist ein
  Konto; `app-init.js::isGuestComposer`, `agent-chat.js`, `model-picker.js`
  lesen sie); `App.expectsAgent()` (auch für einen Gast, dessen Wahl Agent ist,
  Apple-Audit H3); `App.firstFrame` `{look(), remember(), agentModel(),
  agentEffort(), forget()}` — bei `pagehide`/verborgen merkt es pro Konto, was
  der Composer zeigte (`localStorage consensio.firstFrame.v1`: Agent-Modellname
  und Reasoning-Stufe nur aus geladener Modellliste, `select.dataset.catalog ===
  "ready"`, dazu der Consensus/Compare-Chip), Logout vergisst es; ohne Eintrag
  gilt `data-agent-default-label` (pages.py, `agent_model_label()`). Gezeichnet
  werden: Agent-Chip (ein Knopf `.model-picker-display[data-seeded]`, den
  `model-picker.js::initCustomModelPicker` adoptiert; `agent-chat.js` zeigt
  denselben Namen statt „Loading models…“, bis die Liste da ist, und die Zahl
  `+N` steht schon, solange die Verknüpfung noch wartet), Consensus-Chip,
  Reasoning-Wort (`data-seeded` bis `agent-chat.js` die Stufen gezeichnet hat),
  die Anbieter-Marken der Werkzeugleiste (aus `MODEL_FAMILIES` und den
  gespeicherten Familien, `#composerModelIcons[data-providers]`; `agent-mode.js`
  behält dieselben Knoten), die Familien-Checkboxen, „Try the demo“ (steht jetzt
  im Template, `hidden`; `demo.js` verdrahtet es nur), Senden (im Template
  `disabled`), ein wartender Gast-Entwurf samt Höhe und `--starters-room`,
  Skelette für Chatliste und Konto-Fuß bei wiederherzustellender Sitzung und auf
  dem Handy der Watches-Punkt am Menü. Die Werkzeugleiste steigt nur beim
  Wiederkommen ein (`.is-revealing`), nie beim ersten Paint. Der Umschalter heißt
  immer „Chat“, der Sidebar-Knopf immer „New chat“ (Max, H3); im mobilen Kopf
  wird der Umschalter nie gezeichnet (er lebt im Menü), die leere rechte Insel
  eines Gasts ab dem ersten Bild nicht. `continueSignedIn()` speichert vor dem
  Neuladen nach dem Login das `id_token`. Der Startbildschirm hält die Oberkante
  des Feldes fest (`--hero-lift: 130px`, `--hero-shift` an `.container`):
  Hinweise, Anhänge, neue Beispielfragen und Zeilen wachsen nach unten,
  `#verifyBanner` steht im DOM nach dem Composer und folgt dessen Verschiebung,
  ein Composer-Hinweis nimmt im Hero den Platz der Beispielfragen ein (B5). Der
  leere Start ist nicht verschiebbar: `body.is-hero { min-height: 100svh }`,
  `overscroll-behavior-y: none`, bei Höhe ≤ 500 px Beispielfragen einzeilig
  (F10). `index.html` wärmt Googles CDN und die beiden Firebase-Module per
  `preconnect`/`modulepreload` vor (B9). Enter: `App.enterSends(event)` / `App.isComposingKey(event)` (app-core.js)
  — Touch-Tastatur macht Absätze, Tastatur sendet, Eingabemethoden
  (`isComposing` oder `keyCode 229`) nie; alle Enter-Handler von Textfeldern
  fragen das (E7, E8). Messung: `tests/e2e/test_first_frame.py` (Bild für Bild
  ab dem Neuladen), `tests/js/first-frame.test.mjs`.
- **Senden in einem Task, eine Projektion (seit 2026-10-20, Apple-Audit D3)** —
  `App.runRegistry.batch(fn)` projiziert mehrere Änderungen (in
  `agent-chat.js::send` Anlegen, Starten, Feld leeren) einmal am Ende; Ereignisse
  gehen weiter einzeln raus. Dazu lesen die Module im Klick weniger Layout:
  Fragen-Faltung nur noch im ResizeObserver, leere Aktivitätsvorschau und
  leere Antwort ohne Messung, Sidebar-Zeile und Kopfkante im nächsten Frame.
- **Buchstabenwolken im Hero (seit 2026-10-16)** — `static/js/letter-clouds.js`
  (App-Gruppe vor `app-init.js`, `App.letterClouds` `{state(), splash(x, y)}`)
  und `static/css/letter-clouds.css`. Das Modul hängt `.letter-clouds` als
  erstes Kind in `<body>` (fixed, `z-index: 0`, `pointer-events: none`,
  die Farbe für Safaris untere Leiste gibt `.app-bottom-edge` darüber, siehe
  „Mobile Kopfleiste“; jede spätere positionierte Ebene liegt darüber) und läuft nur, solange
  `body.is-hero` gesetzt und keine `.watch-page` sichtbar ist (MutationObserver
  auf `body.class` und `.watch-page[hidden]`). Verlässt der Nutzer den Hero
  (erste Frage, Bookmark, Demo, Watches), bekommt die Ebene `.is-off`
  (ausblenden, dann `visibility: hidden`) und die Schleife (rAF und Timer) endet; im Chat
  kostet sie nichts: Nach dem Ausblenden (`transitionend` der Deckkraft) gibt
  sie ihre Leinwände frei (0×0, bei DPR 2 rund 30 MB), eine Größenänderung
  merkt sie sich nur (`stale`) und misst beim nächsten Start neu (seit
  2026-10-20, Apple-Audit D11). Ein neues Format übernimmt die Zeichen, die
  schon dastehen; neu gewürfelt werden nur hinzugekommene Zellen (Tastatur,
  Drehen). Bauweise: ein Glyphen-Canvas (Atlas, fast nie neu
  gemalt, Deckkraft 0.26; seit 2026-10-20 in voller Gerätedichte bis 3x statt
  höchstens 2x, Apple-Audit G16: auf dem iPhone waren die Zeichen 1,5-fach
  hochskaliert; gemessen 390 px, DPR 3 gegen 2: Haupt-Thread Ruhe +3–5 ms/s
  bei ~25–33 ms/s, Welle +10–20 ms/s, Leinwand 1170×2532 statt 780×1688,
  am echten iPhone noch nachzumessen) unter einem winzigen Nebel-Canvas in der
  berechneten Seitenfarbe (1 Punkt je 10 px, vom Browser weich hochskaliert);
  pro Bild ändert sich nur der Nebel. Wolken = zwei gedrehte Abtastungen
  eines normierten, kachelbaren Wertrauschens (ungedreht zeichnet das Gitter
  gerade Kanten, ohne Normierung schwankte die Bedeckung 0–50 %), blenden
  über 7 s ein und lichten sich um `.input-section`. Ruhe 10 Bilder/s, die
  ein `setTimeout` weckt (dazwischen schläft der Tab, kein rAF pro
  Bildschirmtakt; `state().running` zählt rAF oder Timer), Welle im vollen
  Bildtakt per rAF; die Wolken werden auch dann nur im Ruhetakt neu
  gerechnet. Das Rauschen wird ohne Gleitkomma-`%` abgetastet (Koordinaten um
  `OFF` positiv verschoben, Bitmasken kacheln), die Welle ohne `atan2`/`sin`
  pro Punkt (Vielfache des Winkels per Tschebyschow-Rekursion, Ring auf
  0.76–1.24 R0 ± 3 Breiten begrenzt); beides malt bitgenau dasselbe wie die
  Fassung vom 2026-10-16 vor der Optimierung. Messung 2026-10-16 (i5-7500,
  60 Hz, 1440x900): Ruhe Haupt-Thread 2,7 → 1,2 %, Renderer+GPU 7,2 → 4,2 %
  eines Kerns; Welle bei 6x Drosselung p95 17 → 8 ms. Achtung beim Nachmessen:
  DevTools-CPU-Drosselung dehnt `setTimeout` etwa 5x, rAF nicht.
  `pointerdown` auf einer freien Stelle (nicht Steuerelemente,
  `.input-section`, Sidebar, Navigation, Dialoge) startet die Welle: Radius
  und Breite schwanken je Richtung, sie bremst ab, zerfällt in Flecken und
  hat 1–2 Nachläufer. Solange ein solcher Klick gedrückt ist, bricht
  `selectstart` ab: Doppel-, Dreifachklick oder Ziehen markierten sonst den
  Hinweis unter dem Composer. Theme-Wechsel (`body.dark-mode`, System) malt neu,
  verdeckter Tab rechnet nicht. Ohne `matchMedia` (reduzierte Bewegung nicht
  prüfbar) oder Canvas bleibt das Modul aus; `prefers-reduced-motion` zeigt
  ruhende Wolken ohne Welle. Die Kontoeinstellung `letter_animations: false`
  (Settings → Display → Letter animations, seit 2026-10-23) zeigt gar keine:
  `wanted()` ist dann falsch, ein Umschalten (`userSettings.onChange`) blendet
  die Ebene sofort aus oder ein. Tests: `tests/js/letter-clouds.test.mjs`,
  Browser `tests/e2e/test_letter_clouds.py`.
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
  das Scrollen im Agent- und Consensus-Chat wie ChatGPT/Claude (seit 2026-10-09,
  Layout-Shift-Audit): `App.revealSentMessage()` → `sent()` bringt beim
  tatsächlichen Absenden die neue Frage (`#threadAsk`, sonst
  `#threadPendingAsk`) einmal sanft nach oben, genau an die Stelle, an der eine
  erste Frage auf ungescrollter Seite steht (Spalten-Padding + Frage-Margin).
  Danach scrollt nichts mehr von selbst: kein Mitlaufen beim Streamen, beim
  Review, am Laufende. Damit die Frage auch bei kurzer Antwort oben stehen kann,
  hängt `.chat-scroll-reserve` (letztes Kind von `.container`, `order: 4`)
  genau so viel Leerraum an, dass der neueste Turn den Viewport füllt; Antwort,
  Evidenzzeile und spät geladene Dateien wachsen in diesen Raum, die Seite wird
  erst länger, wenn der Turn den Viewport übersteigt. Die Reserve rechnet in
  Dokumentkoordinaten (Frage, Reserve-Oberkante, Composer im Fluss oder
  `padding-bottom` beim fixierten Handy-Composer) und wird bei jedem
  ResizeObserver-/Resize-/Projektionsdurchlauf nachgeführt. Was nach der
  Spalte kommt, misst sie am Layout (Body- minus Spaltenunterkante), nie über
  das gerundete `scrollHeight`, und sie rundet ab: sonst tauschten Reserve und
  Seitenhöhe bei gebrochener Lage (Frage bei 292,625 px, Full-HD-Fenster) in
  jedem Frame 1 px, und die Scrollleiste flackerte den ganzen Lauf über.
  `openBookmark()` ruft nach der Projektion `App.chatScroll.opened()` auf, auch
  bei noch lokal vorhandenen Runs: **seit 2026-10-20 ohne Fahrt** (Apple-Audit
  A2/A3) — die neueste Frage wird synchron vor dem ersten Bild an ihre
  Landeposition geschrieben (`behavior: "instant"`, nicht ans absolute Ende,
  mobil also nie unter dem schwebenden Kopf) und folgt ihr nur noch
  `OPEN_SETTLE_MS` (600 ms) lang, falls spätes Layout sie verschiebt; jede
  Leseinteraktion beendet das. Die 420-ms-Fahrt gibt es nur noch für Senden
  (`sent()`, Frage nach oben) und „Latest message“. `closeMenu()` schließt das
  Handy-Menü; `openBookmark` ruft es schon beim Antippen.
  „Latest message“ (`latest()`) springt einmal zu dem Inhaltsende, das
  beim Drücken bestand (gemessen an der Reserve-Unterkante); Text, der während
  des Sprungs ankommt, verlängert ihn nicht, ein wachsender Composer schon.
  Gespeicherte Ansichten binden die
  Animation an Bookmark und Auth-Generation; neue Auswahl und Leseinteraktionen
  brechen sie ab. `getSelectedConversationIdentity()` liest dafür nur ID/Modus,
  ohne den gespeicherten Antwort-/Reviewtext pro Animationsframe zu kopieren.
  Recovery, Direktvergleich und Hintergrundläufe erzwingen keinen
  Sprung. Das Sprungziel wird pro Frame neu gemessen (Frage setzt sich,
  History wird angehängt, Composer klappt ein). `run-view.js` bindet die
  Projektion an Run und Account.
  Wheel/Touch/Scrolltasten/Pointer und Textauswahl unterbrechen sofort, auch vor
  dem ersten Frame. Die dezente Schaltfläche mit
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
  oder Login-Hinweis) und schreibt sie als `--thread-composer-height` an die
  `.container` (nicht an `<html>`; während `composer-animating`/
  `composer-gliding` erst einmal mit der Endhöhe, Apple-Audit D9); dieselbe
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
  innerer Scrollbereich, Background-Scroll-Lock, Escape/Focus-Restore). Esc
  schließt nur diese Ebene (`preventDefault` + `stopPropagation`, nichts bei
  `isComposing`); die Watch-Seite darunter hat seit 2026-10-20 gar keinen
  Esc-Handler mehr (J1: eine Seite ist keine Ebene). Der
  normale Share-Dialog schließt weiterhin über den Backdrop; im Watch-Modus
  verhindern unbeabsichtigte Außenklicks das Schließen. Jeder Share-Request ist
  an UID/Auth-Generation und eine Modal-/View-Epoch gebunden; Ansichtswechsel,
  Logout und Schließen aborten laufende Fetches, späte Antworten dürfen den
  gemeinsam mit Watch genutzten DOM-Knoten nicht mehr überschreiben.
  `openShareDialog(view, {prepare, trigger})`: `prepare(viewEpoch)` nennt die
  Antwort, wenn es nicht die Standardquelle ist (`lastShareResultId` bzw. der
  geöffnete Chat-Eintrag). Warum etwas nicht teilbar ist, steht seit
  2026-10-21 als `#shareDialogError` (`role="alert"`) im Dialog, in den Worten
  des Servers; bei bleibenden Gründen (4xx) verschwindet der Knopf, bei
  Netz/5xx/429 heißt er „Try again“ (früher: toter Knopf „Saved consensus
  unavailable“, Fehler nur in der Konsole). `App.answerShare.button(answerBody,
  {chatId, turnId, eligible})` setzt unter jede fertige Agent-Antwort (live,
  wiedergeöffnet, jeder Agent-Turn im Verlauf) die Share-Pille direkt hinter
  die Watch-Pille (`watch.js`, gleiche Zeile; ohne Evidenzzeile teilen sich
  beide `.agent-watch-pill-row`, die erst leer verschwindet); ein Turn im
  Verlauf nimmt beim Klick den Chat auf dem Bildschirm. `App.answerShare.open`
  öffnet den Dialog für einen Turn (auch aus dem Chat-Menü, wenn der Chat als
  laufender Agent-Run sichtbar ist, `firebase.js shareBookmark`).
- **`consensus-actions.js`** — Copy/Citation/Share-Buttons am Consensus.
- **`watch-fields.js`** (seit 2026-10-20, vor `watch.js`) —
  `window.App.watchFields`: die Bausteine, aus denen der „New watch“-Dialog
  und die Karten-Einstellungen gebaut sind (Apple-Audit J7): `goalList`
  (Radioliste „What are you waiting for?“ mit angebotenen Zielen, „Something
  else…“, „Any change to the answer“), `intervalSelect`/`weekdaySelect`/
  `timeInput`, `alertSelect` (+ `relabelAlerts`), `visibilitySelect`,
  `detailsInput` und `field()` (Label + Steuerelement + Hinweis + Fehler;
  Gruppen wie die Kanäle als `div[role=group][aria-labelledby]`, nie als
  `<label>`, J10) samt `markSaved()` („✓ Saved“ am Label) und `setError()`.
  Dieselben Labels an beiden Stellen: How often · Day · Time · Notify me ·
  Send to · Watch page · Details that matter. Außerdem die eine Schreibweise
  für Zeiten (J5, J30): `scheduleText`/`scheduleLabel` („weekly on Tuesday at
  09:00“, Zeitzone nur bei Abweichung und als Stadt: „(New York time)“),
  `checksSentence` („Checks weekly on …“) und `timezoneNote` („In New York
  time“) — seit 2026-10-23 schon in der Sprache des Lesers: ganze Sätze je
  Form über `App.t` (Kontext `watch schedule`, `intervalSelect` trägt ihn
  als `data-i18n-context`, docs/i18n.md), nie verkettet,
  `nextCheck(watch, now)` („Checking now…“ bei `checking`, „Check due now“
  bei `due` oder vergangenem `next_run_at`, „Next check in 12 min“, „Next
  check tomorrow, 09:00“), `relativePast`, `dateTimeTitle` (24 h).
- **`watch.js`** — `window.openWatchDialog` (Create-Dialog im Share-Modal),
  `window.openWatchDashboard(options)` und das Routing der eigenen Seite
  `/app/watches` (URL-Sync via pushState/popstate, Deep-Link wartet auf den
  asynchronen Firebase-Auth-Status). **Seit 2026-10-20 (Apple-Audit F14, C6,
  J4, J6) scrollt die Seite im Dokument** statt als fixierte Ebene: offen ist
  `body.is-watch-view`, der Chat (`.container`) tritt per `display: none` zur
  Seite und bekommt beim Zurück seinen Scrollstand wieder (`setWatchView`);
  `.watch-page-inner` beginnt am Desktop rechts der Seitenleiste wie die
  Chat-Spalte. Der Wechsel blendet durch (`is-view-out` 120 ms → Tausch →
  `is-view-in`/`is-view-settle` 200 ms mit 8 px Anstieg), der Umschalter
  bleibt stehen; aus einem Thread heraus blendet er mit (`is-switch-out/in`,
  nur Desktop). Ein Chat aus der Seitenleiste schließt Watches ohne
  Scroll-Rücksprung. Gäste sehen die Seite auch (J3): ein Beispiel-Kartenbild
  (`renderGuest`) und im Kopf „Log in to start watching“; jede Einladung
  (Kopfknopf, Watch-Knopf, Nudge) öffnet `App.openAuthModal("login", …,
  "watch")` und merkt sich die Frage in `consensio.watchAfterLogin.v1`
  (1 h), nach dem Reload öffnet der Dialog damit von selbst.
  `/app/watches?create=1` (CTA der öffentlichen Watch-Seite) öffnet den Dialog
  nach bekanntem Login bzw. den Login. Gerendert wird das Dashboard von
  `watch-dashboard.js`; `watch.js` stellt dafür `window.App.watchUi` bereit
  (API-Helfer mit Session-Epoch; Fehler tragen `status`, `code`, `watchId`,
  `retryAfter` aus `{error, code}` oder FastAPI-`detail`; `buildChannels`,
  Telegram-Kopplung, Limit-Rendering, `smoothHeight`, `requireAccount`) und ruft
  `window.App.watchDashboard.render()`. **Telegram-Kopplung** (J19): eine
  Kopplung pro Seite (`connectTelegram`, `onTelegramStatus`,
  `cancelTelegramPairing`), „Waiting for Telegram…“ + Cancel, prüft bis zum
  Ablauf des Links (10 min, mit wachsenden Pausen) und sofort bei Rückkehr in
  den Tab, nie mit „refresh this page“; nur die Stelle, von der aus verbunden
  wurde, hakt Telegram danach an. **Watch-Knöpfe** (J15, J17, J20): dieselbe
  Pille unter Consensus (`#consensusWatchButton`) und Agent
  (`.agent-watch-pill` in `nav.agent-evidence-links`, sonst eigene Zeile
  `.agent-watch-pill-row`; `App.watch.answerButton(body, {question, eligible,
  followUp, history})`). Seit 2026-10-21 (Max' Entscheidung J20,
  Nachprüfung 9) unter **jeder** fertigen Agent-Antwort: live aus
  `agent-chat.js` `project()` (ohne eigene Agent-Watch-Karte), in einem wieder
  geöffneten Chat aus dem Basis-Zweig von `renderShell` (Frage des
  `currentTurn`, nie die des vorher gezeigten Chats; ohne Antwort weg) und an
  jedem Agent-Turn des Verlaufs aus `consensus-run.js` `buildHistoryTurn`
  (`history: true`, außerhalb der Seite gebaut, auch mit vorbereiteter Watch,
  weil der Verlauf deren Karte nicht zeigt). Auf dem Telefon (≤540 px)
  sind Watch und Share seit 2026-10-22 zwei weitere Zellen der Belegleiste:
  eine Werkzeugzeile von Kante zu Kante (Glyphe über Wort, ohne Fläche;
  `nav.agent-evidence-grid` steht dafür auf `display: contents`, die Zeile
  verteilt mit `space-between`, `agent-chat.css` und `components-watch.css`).
  Jede Pille trägt die Frage ihres
  eigenen Turns; nur die der Live-Antwort heißt `#agentAnswerWatchButton`
  (ein nach oben gewanderter Turn verliert die ID). Folgefragen (`followUp`:
  ein Turn über ihr im Verlauf) öffnen beim Fragefeld. Eine schon
  beobachtete Frage (`watchedFor`) heißt dort „Watching“ und öffnet ihre
  Watch auf der Seite (`openWatchDashboard({focus: id})`). Der View-Switch `#viewSwitch`
  (Chat/Consensus | Watches) ist ein Segment mit gleitendem Thumb
  (`.view-switch-thumb`, `data-active="chat|watches"` aus `setViewSwitchState`);
  `agent-chat.js` setzt nur das Label im ersten Segment (Agent = „Chat“,
  sonst „Consensus“), Icon und Thumb bleiben. Ein kurzer, auf zwei Zyklen
  begrenzter Puls weist dort dezent auf Watches hin, verschwindet beim ersten
  Öffnen lokal dauerhaft und respektiert `prefers-reduced-motion`.
  **Create-Dialog** (seit 2026-10-10 entschlackt): ohne bekannte Frage zuerst
  das Fragefeld („What should we keep checking?“, Enter = Continue); eine
  bekannte Frage (Dashboard-Beispiel, Nudge „customize“, fertiger Consensus)
  springt direkt zum Ziel, die Frage steht oben mit `#watchQuestionEdit`.
  Seit 2026-10-20 (J2) ist der Dialog oben verankert
  (`#shareModal.is-watch-dialog`, `--watch-dialog-top`), am Handy ab dem
  ersten Schritt ein volles Sheet, dessen Aktionsleiste mit offener Tastatur
  an der Tastaturkante endet (F8, wie jede Ebene mit Feldern:
  `--keyboard-top`/`--keyboard-height`); die Aktionsleiste ist Dialogfläche mit
  Haarlinie, ohne Blur und Tönung (G14). Drei Vorschlagszeilen sind vom
  ersten Bild an reserviert, Höhenänderungen gleiten (`smoothHeight`), und
  während jemand in „Something else…“ tippt, hält die Liste ihre Höhe, bis
  das Feld verlassen wird. „Any change to the answer“ ist von Anfang an
  gewählt (J16), der erste Vorschlag übernimmt, solange niemand gewählt hat;
  der Fokus landet im neuen Schritt auf der gewählten Zeile (J27). Eine schon
  beobachtete Frage öffnet statt des Formulars „Watching“ mit „Open watch“
  (J17, auch bei `code: "already_watched"`); ohne freien Platz steht vor
  jeder Eingabe der Limit-Schritt mit „Show my watches“ (J25). „Details that
  matter“ stehen jetzt auch im Dialog (unter „Change“; nach dem POST per
  PATCH `requirements` gespeichert). Wörter (J18): „New watch“, „Start
  watching“, „Watching“, Seite „Watches“, erreicht = „Reached“, „watch“ im
  Satz klein; ein Primärknopf `.wd-button.is-primary` für alle Stellen.
  Kern ist **„What are you waiting for?“** als Radioliste
  (`name="watchGoalChoice"`): bis zu drei Vorschläge von `POST
  /api/watch/goal-suggestions` (pro Frage im Dialog gecacht; ein Fehler lässt
  nur sie weg), ein vorgegebenes Ziel als erste Zeile, „Something else…“
  (`#watchGoalCustomChoice` + Textfeld `#watchGoal`, ≤ 500 Zeichen) und „Any
  change to the answer“ (`#watchGoalNone`). Solange der Nutzer nichts gewählt
  hat, ist die erste Zeile **vorausgewählt** (Vorschläge als Chips über einem
  leeren Feld wurden nicht als „noch anklicken“ erkannt); gespeichert wird die
  Wahl als `condition`. Darunter **eine** Zeile `#watchSettingsSummary`
  („Weekly on Sunday at 09:00 · E-mail · Private“) in `<details
  id="watchAdvancedSettings">`, „Change“ klappt Intervall/Tag/Zeit, Alert-Regel,
  Kanäle (Telegram nur, wenn der Bot konfiguriert ist) und Sichtbarkeit auf;
  Validierungsfehler öffnen es selbst. Alert-Regeln: „When it moves (or
  resolves)“ (`changes_only`), „Only when it resolves“ (`condition`, braucht ein
  Ziel), „After every check“ (`every_run`). `POST /api/watch` akzeptiert
  alternativ zu `result_id`/`share_id` ein exklusives `question`-Feld; der Pfad
  startet keinen App-Consensus. Das Limit zeigt der Dialog nur, wenn es
  erreicht ist (`#watchDialogLimit`), dann ist die Create-Aktion vor dem
  Request deaktiviert; Zahl und freie Plätze stehen im Dashboard-Kopf und in
  der Sidebar. Nach dem dritten speicherbaren Consensus zeigt
  `window.App.watch.*` einmalig einen Hinweis am Watch-Button mit der **Aktion
  selbst** („Watch this question“, `watchDefaults()`: wöchentlich, morgiger
  Wochentag, 09:00 lokal, privat, E-Mail nur auf Belege; dieselben Defaults
  nimmt die Agent-Watch-Karte); „Add a goal or change
  the schedule“ öffnet den vollen Dialog, ein 429 ebenfalls.
  `openWatchDialog("create", options)` nimmt `question`, `goal` (vorgewählt),
  `goals` (Vorschläge des Aufrufers, dann kein `goal-suggestions`-Call),
  `interval` und `source` (Analytics). „Edit“ (`#watchQuestionEdit`) ändert
  seit 2026-10-21 nur die Frage: Zeitplan, Benachrichtigung, Kanäle,
  Sichtbarkeit, Details und der offene Einstellungsblock kommen als
  `settings` zurück (nur das Ziel gehört zur Frage; ohne Ziel wird „Only when
  it is reached“ zur ersten Regel). Der Login-Hinweis für Gäste sagt „Your
  question waits for you.“ nur, wenn eine Frage wartet. `receiveWatchList` (aus
  `loadWatchLimits` und dem Dashboard) hält neben den Limits die Watch-Liste
  (`watchState.watches`) und meldet `consensio:watches-changed`. Die Liste
  kommt über `watchUi.requestWatchList({fresh})`: höchstens ein GET zugleich,
  wer währenddessen fragt, teilt ihn (`fresh` nur nach einer eigenen
  Änderung); das Dashboard lädt Liste, Brief und Telegram über ein geteiltes
  `load()`, und der erste Blick auf `/app/watches` kommt einmal (`firstLook`:
  Route oder Auth-Zustand, wer zuerst da ist; die Anmeldung nimmt für die
  Seitenleiste über `App.watch.loadState` die geladene Liste) – je ein Request statt
  3×/2×/2× (Nachprüfung 2). Der Schritt „alle Plätze belegt“
  (`renderLimitStep(intent, {resume, reload})`) fragt beim Öffnen einmal neu
  und folgt `consensio:watches-changed`: wird ein Platz frei (eine Löschung,
  deren Undo abgelaufen ist), kommt das Formular zurück. Wird der Dialog
  geschlossen, während eine Watch startet, gilt sie trotzdem: Details werden
  nachgetragen, die Karte erscheint auf der Seite, eine Zeile sagt „Watch
  started“ (bzw. „Watch not started …“ als Fehler);
  `App.watch.watchedFor(question)` vergleicht wie `question_hash`
  (Groß/Klein, Leerraum, Schluss-„?!.“). Der Hinweis ist ein
  eigener Viewport-Layer unter `<body>` und übermalt nie den Composer.
  `window.App.watch.resetAfterLogout()` leert das Dashboard beim Session-Ende;
  auf einem direkten `/app/watches`-Deep-Link wechselt die Seite deterministisch
  zur Gast-Ansicht, `consensio:auth-state` rendert nach späterem Login neu.
  Das erste Bild von `/app/watches` malt `app-bootstrap.js` (J6):
  `body.is-watch-view`, sichtbare Seite, Umschalter auf Watches und das
  Kartenskelett (`App.watchSkeleton()`), bevor überhaupt ein Chat gemalt
  wird; die Limitzeile im Kopf ist von Anfang an reserviert.
- **`watch-dashboard.js`** — rendert `/app/watches` in `#watchDashBody`
  (`window.App.watchDashboard.{render, refresh, cardState, renderGuest,
  renderSkeleton, focusWatch, addCreated, showUndoToast, commitPending,
  reset}`, Styles mit `wd-`-Präfix in `static/css/components-watch.css`).
  **Seit 2026-10-20 (D6, J8, J13, J14) wird die Seite einmal pro Besuch
  gebaut und danach Karte für Karte geändert**: jede Karte ist ein Eintrag
  (`page.cards`), `updateCard(id, watch)` setzt die Serverantwort ein und
  baut nur ihren Inhalt, ihre Fußzeile und ihre Aktionen neu — offene
  Einstellungen bleiben offen, der Fokus bleibt auf seinem Knopf. Ein
  späteres Laden (`refresh`, Rückkehr in den Tab nach > 60 s, fälliger Check
  mit Pausen 1/2/5/10 min) gleicht nur ab; neu sortiert wird beim nächsten
  Besuch. Pause/Resume ändern die Karte am Platz und sagen „Watch paused ·
  Undo“; Delete faltet die Karte weich weg und schickt den DELETE erst, wenn
  das Undo (6 s) verstrichen ist (oder beim Verlassen der Seite/des Tabs).
  `showUndoToast(message, {undo, commit, timeout})` leitet seit 2026-10-20
  an die gemeinsame Hinweis-Zeile weiter (`App.toast`, `notices.js`): eine
  zur Zeit, pausiert bei Hover/Fokus, ein Kontowechsel verwirft sie ohne
  Commit. `commitPending()` lässt das offene Undo geschehen, speichert
  Getipptes offener Karten und liefert seit 2026-10-21 ein Promise, das
  erfüllt ist, wenn alles gesendet wurde: `firebase.js` `performLogout`
  wartet darauf (neben den Chat-Löschungen, zusammen höchstens 3 s), bevor
  das Token geht. Vorher lief eine gerade gelöschte Watch nach dem Logout
  weiter. Ändernde Watch-Anfragen (`watchUi.api`, alles außer GET) und das
  Chat-Löschen (`DELETE /bookmark`) gehen mit `keepalive`, damit ein Undo, das
  beim Schließen des Tabs abläuft, noch ankommt. Eine Pause, deren Antwort
  nach einem Delete kommt, zeigt kein eigenes Undo (es hätte das des Deletes
  beendet). Falten (`collapse`/`expand`): eins pro Knoten (`folds`), ein
  späteres übernimmt dort, wo das laufende steht, das Ende des älteren landet
  nie (schnelles Undo ließ die Karte sonst für immer versteckt; dasselbe für
  die Sektion um die letzte Karte); gefaltet wird in `border-box`, sonst wuchs
  die Karte im ersten Bild um ihr Padding. Ein fehlgeschlagenes Speichern
  lässt getipptes Ziel, Uhrzeit und Details im Feld (Auswahlfelder zeigen
  wieder den gespeicherten Wert); Verlassen des Zielfelds versucht es erneut.
  Einstellungen klappen über `grid-template-rows` 0fr→1fr in `--dur-layer`
  auf (geschlossen `inert`). **Speichermodell** (J7, J9, J11): jede Änderung
  landet sofort und sagt „Saved“ am Feld — Auswahl nach 350 ms (mehrere
  schnelle Änderungen = ein PATCH), Texte und Uhrzeiten erst beim Verlassen
  des Feldes oder Enter, nie während des Tippens, Felder werden nie gesperrt;
  beim Zuklappen wird Getipptes gespeichert. Begründung: die Karte ist die
  laufende Watch, es gibt keinen Entwurf, und kein zweiter Knopf kann Text
  zurücklassen. Die Felder sind die des Dialogs (`watch-fields.js`), dazu
  „Watch page“ (PATCH `visibility`, ignoriert ein älterer Server das Feld,
  steht der Fehler am Feld) und „Remove picture“ mit Undo statt des × auf dem
  Bild (J23; das Bild führt wie die Frage zur eigenen Watch-Seite). Sektionen:
  Watching · Paused (Fehler zuerst) · Reached (J22); pausierte Karten haben
  „Resume“ neben „Settings“, erreichte einen Fuß mit Delete (J21). Der
  Kopf bleibt in jedem Zustand gleich (eine Überschrift, „New watch“; am
  Limit als einfacher Knopf), der Leerzustand zeigt darunter auf derselben
  Kante nur „Start from an example“ (J24); die Kennzahlenzeile lässt Nullen
  weg, „Why a watch, not a scheduled prompt“ steht zugeklappt am Seitenende
  (J29). Zeiten werden alle 30 s neu gelesen (J5). Ein Ladefehler lässt die
  Liste stehen und zeigt „Try again“ (`.wd-alert`, J6). Eine neue Watch steht
  nach dem Erfolgsschritt oben in „Watching“ und ist kurz markiert
  (`addCreated`, J15) – egal ob „Done“, Kreuz, Esc oder Backdrop ihn schließt
  (`close`-Event des Dialogs, nicht nach einem Logout). Es präsentiert nur das Server-Signal aus
  `drift_signal` (siehe `docs/watch-evidence-model.md`), leitet nichts selbst ab:
  `cardState` liefert pro Watch Ton/Label/Satz/Quellen — *Moved* (mit
  `evidence_sources`), *Re-checking* (`confirming`), *Answer stands* (`held`),
  *Watching* (`lead` „Last moved …:“ + Satz der letzten Bewegung oder „The
  answer has held through N checks.“), *Resolved* (Grund + Quellen aus
  `resolution`), *Paused*, *First check pending*; `quoted` markiert einen Satz
  des Judges (`change_summary`, `resolution.reason`), der mit
  `data-i18n-skip` in seiner Sprache bleibt. Aufbau: ruhige Kennzahlenzeile (watching / moved / reached
  this week / next check, Nullen weggelassen), Abschnitte *Watching* (neu
  angelegte zuerst, dann Moved → Re-checking → Held → Watching → Pending,
  dann nach nächstem Check) / *Paused* / *Reached*, *Delivery*
  (Telegram-Verbindung und Morning Brief im `.switch`/`.slider`-Stil des
  Input-Felds, Brief-Uhrzeit beim Verlassen des Feldes gespeichert) und am
  Ende das einklappbare „Why a watch, not a scheduled prompt“
  (`.wd-explainer` mit Vergleichstabelle `.wd-compare`, standardmäßig zu;
  `consensio.watchExplainer.open.v2` merkt nur, was der Leser selbst
  umschaltet — v1 speicherte auch das `toggle`-Event des eigenen
  `open = true` und hielt die Kachel so dauerhaft offen). Jede Karte ist ein
  Teaser (Max 2026-10-23: „zu viel Input, schreckt ab“) — Status (Zeit als
  „checked 3 h ago“ bzw. „last check …“; bei „First check pending“ ohne Zeit,
  die steht im Fuß; „Goal reported, confirming“ nur bei `goal_state`
  confirming, sonst kein Zielstand: „Not yet“ ist keine Nachricht), Frage
  (2 Zeilen geklemmt, mobil 3), ein Satz zum Geschehen (`.wd-headline`, 2 bzw.
  3 Zeilen) und eine Zeile Link-Chips (`.wd-sources`: Favicon + Site, eine je
  Site, max. drei, Seitentitel als Tooltip; bei einer Bewegung ihre Belege,
  sonst `watch.key_links`; mobil wischbar statt umbrechend). Ziel, Details
  (`watch.requirements`), Zeitplan, Kanäle und Verlauf stehen auf der
  Watch-Seite bzw. in „Settings“. Die Frage ist der Link der Karte: ihr
  `::after` deckt die ganze Karte ab, Chips, Fuß, Notiz und Einstellungen
  liegen per `z-index` darüber; Hover tönt die Karte, der Fokusring liegt auf
  dem `::after`. Pro Karte gibt es keine Versalien-Etiketten; die Fußzeile
  läuft als Fließtext mit echten Trennpunkten (`.wd-sep`, per geschütztem
  Leerzeichen an den Teil davor gebunden, damit kein Umbruch eine Zeile mit
  „·“ beginnt; `.wd-item-main`, `display: flow-root` hält das Bild darin). Oben
  rechts schwebt immer etwas zum Wiedererkennen (`.wd-image` float, Karte
  `.has-image`), alle Arten auf derselben Höhe `--wd-anchor` (60 px, mobil
  44 px), der Text fließt herum.
  Hat die Watch ein Bild (`watch.image`), ist es eine 3:2-Kachel (`is-item` ganz
  auf Weiß, im Dunkelmodus mitsamt Foto gedämpft, J31; `is-article` füllend) oder bei `is-logo` die abgerundeten
  App-Icon-Kacheln ohne Rahmen (Haarlinien-Schatten per `drop-shadow`). Sonst — und sobald ein
  Bild entfernt wird oder nicht lädt — steht das Symbol der Watch
  (`watch.symbol`, `.wd-image.is-symbol` > `.wd-symbol`, Strichzeichnung aus
  `SYMBOL_ICONS`, unbekannte Namen → `eye`). Nur Pfade
  `/api/watch/{id}/image/{token}` werden gerendert, „Remove picture“ in den
  Einstellungen ruft nach dem Undo `DELETE /api/watch/{id}/image`. Im Fuß
  stehen links leise „Next check tomorrow, 09:00“ (nur laufende Watches, dazu
  „Daily scan found news …“ aus `last_probe`; „nothing new“ und Ausfälle nicht),
  rechts („Resume“)/(die zwei Wege einer erreichten Watch)/„Settings“. „Settings“
  klappt in der Karte die Zielliste, „Details that matter“ (PATCH
  `requirements`, mit „Ruled out: …“ aus `rejected_sources`),
  How often/Day/Time, Notify me, Send to, Watch page, Google-Listing,
  Bild und Pause/Delete auf; eine
  abgeschlossene Watch bietet „Not what I wanted“ (PATCH `status=active`,
  `reject_match: true`, optional `requirements`; Ziel bleibt, der Treffer zählt
  nie wieder) und „Watch for something new“ (PATCH `status=active` + neues oder
  leeres Ziel); es ist immer nur das Feld des gewählten Wegs sichtbar. Kein
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
  Die Logos der festgehaltenen Karte einer Marke und die Difference-Karten
  laufen für den Sprung zur Fundstelle über denselben `jumpToModelAnswer`-Pfad. Dieser deckt verborgene Einzelantworten
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
  Seit 2026-10-20 (Apple-Audit G15) behalten die Marken diese Helligkeit und
  Buntheit, nehmen aber den Farbton der Ampel-Tokens
  (`oklch(from var(--dispute) L C h)` in `@supports`, davor dieselbe Rechnung
  als feste Farbe; ein Test hält beide im Gleichschritt); dafür ist das
  dunkle `--dispute` ein Rot statt Korall geworden. `--cx-major-line` ist
  `--partial`. Hover
  vertieft denselben Ton (`--cx-mark-*-strong`), statt eine zweite Fläche zu setzen.
  Treffen zwei Marken denselben Satz, hebt `markSentence` die Marke über
  `MARK_LEVELS` (unanimous < minor < split < major) auf die stärkere Stufe an,
  statt die zuerst gesetzte Klasse zu behalten.
  **Nur die Stelle des Streits (seit 2026-10-19, User-Vorgabe):** eingefärbte
  Sätze über die halbe Antwort lasen sich im Light Mode wie ein angestrichenes
  Schulbuch, im Dark Mode lag heller Text auf dunklen Farbbändern. Nennt ein
  Dissens die bestrittenen Worte (`claims[].dissent[].target`, siehe
  Coverage-Judge), wrappt `wrapSpots` (`consensus-insights.js`) genau diese
  Worte im Satz in `<span class="cx-spot">` (Suche mit
  `normalizeForSearch`/`findRangesInText` über die Textknoten der Satz-Spans,
  überlappende Stellen verschmolzen, von hinten nach vorn gewrappt; weil der
  Server die Markdown-Originalspanne liefert, sucht `visibleWords` zusätzlich
  ohne ungepaarte `**`, Links und `[S1]`-Tags); der Satz
  bekommt `.has-spot` und verliert seine Fläche, bleibt aber Steuerelement
  (Klick, Tastatur, Hover, Highlights-Filter). Ein Widerspruch und ein Claim
  auf demselben Satz teilen die Spans, die rote Marke nimmt also die Stelle
  des Claims. Ohne gefundene Stelle (ältere Läufe, verworfene Ziele) bleibt
  der ganze Satz markiert. Hover legt einen Hauch der Satzfarbe über den
  Satz und vertieft die Stelle. Bernstein und Rot sind seitdem klarer (Honig
  #f0b429, Rot #e5484d, deckend über `--ground` gemischt); im Dark Mode nimmt
  die Schrift der Stelle denselben Ton an (`--cx-ink-split`/`--cx-ink-major`).
  `resetConsensusInsights` löst `.cx-spot` vor `.cx-claim` auf; Filter und
  „No highlights“ nehmen der Stelle die Fläche (`shell.css`); der Marker-Strich
  beim ersten Erscheinen läuft über die Stelle (`agent-chat.css`).
  Die Inline-Quote ist standardmäßig ausgeblendet. Settings → Display →
  `#claimCountsSwitch` aktiviert sie über die Kontoeinstellung `claim_counts`
  (lokal `consensio.showClaimCounts.v1`) / die Body-Klasse `claim-counts-visible`.
  Ohne Badge übernimmt die Passage den Tastaturzugang; Hover und Klick bleiben
  für Live- und gespeicherte Antworten verfügbar. Bei einer unbestrittenen
  Aussage betont die Karte (Vorschau und festgehalten) die Quote fett und
  bezieht den Nenner ausdrücklich auf Modelle, die den Claim behandelt haben;
  „Not addressed“ bleibt separat. Dünne Abdeckung zeigt keine Quote. Eine
  bestrittene Aussage zeigt keine Quote, sondern die Gegenüberstellung (Karte
  einer Marke, unten).
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
  nicht nur beim neuesten Turn Claim-Support zeigt. Ein Logo der
  festgehaltenen Karte öffnet dort den gemeinsamen Modellantwort-Leser mit
  genau diesem archivierten Turn statt der globalen Modellbox des neuesten
  Turns.
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
  der Passage (eine angestrichene „3" sieht aus wie ein Fehler). Seit
  2026-10-21 wickelt `wrapFlatRange` auch keinen Text in einem Link, dessen
  Beschriftung seine eigene Adresse oder nur seine Domain ist
  (`window.isBareSourceLink`, sources.js): `linkifyAgentSources` setzt nach dem
  Markieren eine Quellen-Pille an seine Stelle und verwirft die Beschriftung,
  ein Span darin fiel mit aus dem Dokument, und die Hover-Karte seines Satzes
  stand oben links (bei Widersprüchen; ein Claim-Badge im Link hielt die
  Beschriftung bisher zufällig davon ab, als Domain zu gelten). Der Linktext
  zählt für die Ankersuche weiter mit; ein Satz, der nur aus einem solchen
  Link besteht, gilt als nicht verankert. Ein Satz wird höchstens einmal dekoriert
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
  **Die Karte einer Marke (seit 2026-10-23, Max: „das muss perfekt sein“):**
  Jede Marke zeigt dieselbe Karte, in der Sprache der Differences-Schublade:
  Behauptungen, die sich gegenüberstehen, „vs“ dazwischen, unter jeder
  `.cx-card-meta` mit Logo-Stapel (`App.createModelMark`, einfarbig, Farbe
  unter dem Zeiger), ein oder zwei Namen, ab drei die Anzahl („3 models“) und
  an der Seite der Antwort „In the answer“ (geprüfter Nutzertext: „In your
  text“, `sideLabel`). `differenceCard` = Thema als Titel + Seiten wie in
  `buildDifferenceCards` (Antwortseite vorn, „vs“ nur bei Widerspruch);
  `claimCard` bestritten = Seite der Antwort (die eine `.cx-spot`-Stelle, sonst
  der Anker) gegen die Zitate der Abweichler (gleiche Zitate = eine Seite),
  unbestritten/dünn = Quote als Titel, Logos, „Not addressed“ (`.cx-card-aside`)
  und der Satz, dass Übereinstimmung kein Beweis ist; `provisionalCard` ohne
  Urteil. Keine Etiketten in Versalien, kein „Click for …“. Dieselbe Karte
  erscheint als Vorschau beim Hovern (`.insight-preview`), festgehalten nach
  Klick/Enter (`#claimPopover`, `openCard`) und auf dem Handy (≤ 768 px) als
  Blatt vom unteren Rand (`.claim-popover.is-modal`, Griff, graues ×,
  `settleAboveSheet` schiebt den Satz knapp darüber).
  **Die Vorschau ist erreichbar (seit 2026-10-23, Max: dass ein Klick sie
  festhält, war nicht zu erraten):** wer mit dem Zeiger hineinfährt, behält sie
  und kann ihre Wege nehmen. Verlässt der Zeiger Satz oder Karte, geht sie erst
  nach `HOVER_LEAVE_MS` (`leaveHoverPreview`); die Karte hört auf `mouseenter`/
  `mouseleave` wie die Sätze (ein `pointerenter` käme vor dem `mouseleave` des
  Satzes und ließe sie unter dem Zeiger verschwinden). Steht eine Karte, wechselt
  sie zu einer anderen Marke erst nach `HOVER_SWITCH_MS`, damit eine Marke auf
  dem Weg in die Karte sie nicht wegnimmt. Ihre Knöpfe tragen `tabindex=-1`
  (die Vorschau bleibt `aria-hidden`; Tastatur und Screenreader bekommen
  dieselben Wege in der festgehaltenen Karte). Ein Weg aus der Vorschau
  (`ctx.close` = `leavePreviewFor`) setzt den Fokus vorher auf die Marke.
  **Wege in den Leser:** die Fußzeile `.cx-card-actions` (`cardActions`) mit
  Glyphe und Wort der Antwortleiste (`agent-review.js evidenceButton`):
  „Contradictions“ (sonst „Differences“, `openInDrawer` → `focusDifference` →
  Karte im Leser, dort Resolve und Zitate) und „Answers“ (erste Antwort, die
  `navigation.canOpen` öffnen kann, zuerst die der Gegenseite, an ihrem
  Zitat). Der Titel ist reiner Text; der frühere Chevron am Thema war der
  einzige, unsichtbare Weg in die Schublade. Die Logos öffnen weiter die
  Antwort ihres Modells. Alle Wege geben den Fokus zuerst an die Marke zurück,
  damit der Leser ihn beim Schließen dorthin zurückgibt und nicht an einen
  Knopf der geschlossenen Karte. Ein Leser fehlt der Seite: die Vorschau baut
  trotzdem (`canOpenStored?.()`).
  **Pin (seit 2026-10-23):** oben rechts in der Karte (`cardPin`,
  `.cx-card-pin`): in der Vorschau umrandet (`aria-pressed=false`), ein Klick
  heftet an wie ein Klick auf den Satz; an der festgehaltenen Karte gefüllt,
  ein Klick löst sie (`closeClaimPopover`). Vorläufige Marken haben keinen
  (`pinnable: false`, sie öffnen nichts), das Handy-Blatt hat sein ×. Die
  erste Zeile der Karte hält ihm Platz frei.
  `placeCard` rechnet für Vorschau und festgehaltene Karte gleich: die Karte
  steht über der ersten oder unter der letzten Zeile ihres Satzes (nie auf
  ihm), auf der Seite der strittigen Worte, unten begrenzt vom Eingabefeld
  (`cardFloor`). Worauf sie zeigt (`cardAnchor`), ist die `.cx-spot`-Stelle,
  sonst ALLE Spans des Satzes: nur der erste war zu wenig, ein Satz mit
  **fett** oder Link zerfällt in mehrere, und die Karte hielt dessen erste
  Zeile für die Stelle (stand über dem Satz statt darunter). Ihr Text beginnt
  bündig unter dem Anfang der Zeile, an der sie steht (`lineStart`: oberste
  Zeile darüber, unterste darunter), bleibt aber im Textblock: rechts endet sie
  an dessen Kante, außer der Block ist schmaler als sie (Tabellenzelle). Ihr
  Pfeil (`--cx-arrow-x`, `::before`, Kontur per `drop-shadow` über Karte und
  Pfeil) zeigt auf diesen Zeilenanfang. Stand die Vorschau schon da, bleibt die Karte
  beim Klick exakt stehen (`is-instant`, keine Bewegung). Am Rechner folgt die
  festgehaltene Karte beim Scrollen ihren Worten (`refreshPinnedCard`), die
  Vorschau ebenso, solange ihr Satz oder sie selbst unter dem Zeiger bleibt
  (`refreshHoverPreview`; vorher blendete jedes Scroll-Ereignis sie aus und
  wieder ein; Scrollen in einer langen Karte selbst bewegt nichts). Von Marke
  zu Marke ohne stehende Karte wartet
  die Vorschau kein zweites Mal (`HOVER_WARM_MS`); Ein- und Ausblenden laufen
  über die Popover-Bewegung in `overlays.css`. Umami:
  `app_consensus_marker_opened` mit `kind` (claim/difference) und `previewed`.
  **Hover-Vorschau (`.insight-preview`, seit 2026-10-21 nachgeschärft):**
  `canHoverPassages` fragt genau die CSS-Kapsel ab (vorher `any-hover`/`any-pointer`,
  das manches Handy erfüllt); dieselbe Prüfung gilt in `refreshHoverPreview`
  (Scroll/Resize). Fokus zeigt die Vorschau nur, wenn er per Tab kam
  (`focusPassage`: Tab-Taste seit dem letzten `pointerdown`, `:focus-visible`,
  echter Zeiger): ein Tippen fokussiert den Satz ebenfalls, und ein
  geschlossener Leser (`model-answer-reader.js` `close()`) oder eine geschlossene
  Claim-Karte geben den Fokus an ihn zurück – auf dem Handy stand die
  Vorschau danach von selbst da. `placeCard` verankert nur an
  Spans im Dokument mit Fläche (`getClientRects()`), ohne solche keine Karte;
  solange die Claim-Karte offen ist, keine Vorschau daneben. Neu markieren
  (`renderInlineMarkers`), `resetConsensusInsights` und `agent-review.js::overText`
  nehmen eine Vorschau ihrer Marken mit (`App.claimPopover.hidePreview(root)`).
  Inline-Quoten haben auf Mausgeraeten nur ihre sichtbare Trefferflaeche;
  auf Touch erweitert `::after` nur die Hoehe auf 44 px. So ueberdeckt das
  Badge keine direkt folgende `.src-ref`-Quelle. Nur alleinstehende Badges
  in Fallback-Zeilen behalten eine nach innen gerichtete 44-px-Touchbreite.
  An einer **Differenz** gibt es daneben seit 2026-08-15 nichts mehr — dort
  macht `attachPassageControl` den ersten Span selbst zum Steuerelement
  (`role="button"`, `tabindex="0"`, sprechendes `aria-label`, Enter/Space),
  sonst wäre der Widerspruch für Tastatur und Screenreader unerreichbar.
  Die festgehaltene Karte ist mobil ein echtes modales Blatt (`aria-modal`,
  Fokuswechsel/-falle/-rückgabe, inerter Hintergrund); am Rechner bleibt sie
  ein nichtmodaler Popover an ihren Worten (Escape oder Klick daneben
  schließt). Ein Klick auf eine Widerspruchs-Passage öffnet seit 2026-10-23
  diese Karte statt direkt den Leser; in den Leser führt ihr Thema.
  Seit **2026-10-01** sortiert `buildDifferenceCards` die Karten nach Schwere
  (kritischer Widerspruch → Detail-Widerspruch → andere Gewichtung, stabil
  innerhalb einer Stufe) und schreibt den Index in der übergebenen Liste als
  `data-difference-index` an jede Karte. Inline-Marker, `focusDifferenceCard`,
  `storedDifferenceFocus`, `answerReader.openPanel(…, index)` und
  `sourceVerification.openResults` adressieren Karten über diesen Datenindex
  (`App.differenceCardAt`), nie über die Kartenposition. **Seit 2026-10-23
  in der Reihenfolge, in der man es versteht** (Max: „zuerst WAS die
  Ausgangssituation ist, DANN die Aussage, die konkurriert, DANN welches Modell
  was sagt“; der Leser zeigt die Antwort nicht): Hat der Unterschied einen
  `consensus_anchor` und eine `in_answer`-Seite, ist der **markierte Satz der
  Antwort** wörtlich der Kopf der Karte (`.diff-card-claim.is-answer-text` mit
  `.diff-answer-mark` in der Farbe seiner Marke im Text, rot kritisch, grau
  sonst; darüber `.diff-position-lead` „In the answer“, zugeklappt
  ausgeblendet). Die Farbe zeigt die Schwere, deshalb weder Thema noch Punkt
  darüber. Die Seite der Antwort zeigt darunter nur noch, wer sie vertritt;
  jede andere Seite beginnt mit „In contrast“ (Emphasis: „Weighted
  differently“) statt „vs“. Ohne Satz in der Antwort bleibt das Thema der Kopf,
  ein kritischer Widerspruch mit rotem `.sev-dot.is-crit` davor (hängender
  Einzug). Die frühere Schwere-Zeile („● Critical/● Minor“ in eigener Schrift
  und Farbe) ist weg („zu viel fürs Auge und das Gehirn“), Bernstein für
  Details auch (im Text sind sie grau). Screenreader hören Schwere und Thema
  vorab (`.diff-card-meaning`, `differenceMeaning`). Erst ein Resolve-Ergebnis
  legt eine `.diff-card-tags`-Zeile über den Kopf (`markCardResolved`). Die
  Share-Seite (`templates/share.html`, `check_page.difference_cards`:
  `answer_html`, `contrast`) zeigt dieselbe Form.
  **Gelbe Sätze in der Liste (seit 2026-10-23, Max):** Was im Text gelb
  markiert ist, steht auch in der Liste: Claims der Satzprüfung mit
  `coverage: "split"` und benannter Stelle (`dissent[].target`), deren Satz
  kein Unterschied schon trägt (`listedClaim`), werden als kleinere
  Unterschiede angehängt (`claimDifference`, `buildDifferenceCards`
  `options.claims`; live aus `renderConsensusInsights`, gespeichert aus
  `renderStoredDifferenceCards`). Kopf ist ihr Satz, farbig nur die Stelle
  (`wrapSpots` → `.cx-spot`, Bernstein, `.diff-card.is-split`), darüber das
  Thema „Not every model agrees“; darunter wer zustimmt, dann je Gegenseite
  „In contrast“ und ihr Zitat; ohne Resolve. Kennung `data-difference-index`
  `c<i>` (Index im gefilterten Claims-Array, dieselbe Filterung wie die
  Marken); die Hover-Karte eines solchen Satzes führt mit „Differences“ dorthin
  (`focusDifference("c<i>")`; `differenceCardAt` und `answerReader.openPanel`
  finden Karten über die Kennung). Gibt es nur solche Sätze, entfällt der
  leere Zustand. Die Share-Seite zeigt sie nicht (dort gibt es keine gelben
  Marken). Die Karte an der Marke im Text
  (`differenceCard`) bleibt bei Thema, Seiten und „vs“: dort steht der Satz
  daneben.
  **Gegenüberstellung (seit 2026-10-16):** Ein Widerspruch sind Behauptungen,
  die sich gegenüberstehen. Der Körper ist `.diff-sides`: jede Position als Satz
  (`.diff-position-stance`), darunter eine Metazeile `.diff-position-meta`
  (wer das sagt, „In the answer“, „Show quote“, durch Mittelpunkte getrennt),
  zwischen den Seiten ein leises `.diff-versus-mark` „vs“ in Metagröße und
  -grau. Seit 2026-10-21 hat das „vs“ weder Ampelfarbe noch Haarlinien. Im Leser (`model-answer-reader.css`)
  setzt der Tab die Chat-Typografie fort, drei Stufen: Thema als Titel
  (17px/600), Behauptungen in Antwortgröße (17px/400), alles Übrige eine
  Metastufe (13px, `--ink-2`); Abstände im 4px-Raster, ein Chevron für Karte
  und „smaller differences“ am rechten Inhaltsrand. Die Seiten stehen **immer
  untereinander** (seit dem Nachschliff am selben Tag: nebeneinander bei zwei,
  untereinander bei drei Seiten wirkte in derselben Frage willkürlich). Die
  Seite mit `in_answer` steht vorn und trägt „In the answer“. Eine andere
  Gewichtung (`emphasis`) bekommt kein „vs“. Gibt es einen kritischen
  Widerspruch, stehen die kleineren Unterschiede (ab zwei) gebündelt in
  `details.diff-more` („N smaller differences“, zu) hinter den kritischen,
  und jede Karte darin ist zugeklappt (nur ihr Thema, Drill-down einzeln).
  Die Gruppenzeile steht in Tinte und 500 statt im Metadaten-Grau, damit sie
  als Weg zu mehr erkennbar ist (seit 2026-10-23); im Leser sitzt der Chevron
  einer Karte ohne Schwere-Zeile auf der ersten Titelzeile.
  Wer eine Karte darin gezielt öffnet (Marker, Leser-`index`,
  `refreshContext`), öffnet die Gruppe mit (`openDifferenceCard`).
  Zugeklappte Überschriften sind auf zwei Zeilen begrenzt. Mehrere Modelle einer Seite
  zeigen nur Icons + Anzahl („4 models“, Namen bleiben Linktext/Tooltip),
  ein Modell Icon + Name; ist die Originalantwort erreichbar, ist genau das
  Icon/Name-Paar der `.diff-jump-link`. Das Zitat steht hinter
  `.diff-quote-toggle` („Show quote“ in der Metazeile, per
  Dokument-Delegation über `closest(".diff-position")`, damit es auch in den
  in den Leser verschobenen Karten greift); ohne `stance` ist das Zitat
  selbst die Behauptung und erscheint nur einmal.
  **Alte Daten (vor 2026-10-16)** bereitet `readableDifference` für Karte und
  Hover-Vorschau auf, ohne die Daten zu ändern: die Zuschreibung am
  Satzanfang („Model F sagt, …“, „Die Synthese sagt, dass …“) fällt weg,
  „die Synthese“ markiert die Antwortseite (wenn keine `in_answer` trägt),
  ein „Model X“ am Satzanfang einer Position mit genau einem Modell nennt
  dessen Namen, und diese Zuordnung gilt für die ganze Liste (ein Prüflauf,
  dieselben Labels). Nach „dass“ bleibt der Satz stehen (sonst stünde das
  Verb ohne Hauptsatz am Ende), nur der Sprecher wird benannt („Die Antwort
  sagt, dass …“). Eine Überschrift, die beide Seiten erzählt (über 60 Zeichen mit
  Label/„Synthese“), bekommt `.is-narrative` und steht nur im zugeklappten
  Zustand.
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
  schon vor dem Verlassen fertig war, wird nicht gemeldet. Für Screenreader
  schreibt es außerdem „Answer ready“ in die Statuszeile `#answerStatus`
  (`role="status"`, in `main#appMain`), sobald der sichtbare Lauf von
  `starting`/`running` auf `succeeded` wechselt; der Start leert sie.
- **`app-update.js`** (seit 2026-10-15, nach `tab-status.js`, `App.appUpdate`) —
  ein offenes App-Fenster holt neue Deploys selbst. Es vergleicht seinen Build
  (`data-app-build`) mit `GET /api/build`: beim Verlassen (`visibilitychange`
  → hidden), beim Zurückkommen, bei `pageshow` aus dem bfcache und alle 15 min,
  solange die Seite vorne ist (frühestens alle 60 s). Neu geladen wird nur,
  solange die Seite verborgen ist (seit 2026-10-20 nie mehr beim Zurückkommen,
  Apple-Audit B7; ein vorne gelernter Build lädt beim nächsten Verlassen sofort,
  ohne neue Anfrage) — und nur im Leerlauf: kein Lauf/keine
  Aktion (`runRegistry.activeCount()`), leerer Composer, kein Anhang/Import,
  kein Zitat, kein befülltes fokussiertes Textfeld, kein offenes `.modal` oder
  `dialog` (angedockter Leser zählt nicht) und nichts Ungespeichertes im Bild
  (Start, Watch-Seite oder gespeicherter Chat; ein Gast-Ergebnis oder ein
  fehlgeschlagener Lauf blockiert). Vor `location.reload()` merkt es sich in
  `sessionStorage` (`consens.appUpdate.restore`) uid + `bookmarkId` und die
  Lesestelle (`place`: der oberste sichtbare `[data-turn-key]` und sein Abstand
  zur Oberkante, dazu `scrollY`); nach dem Neuladen öffnet es beim ersten
  `consensio:auth-state` desselben Kontos `window.openBookmark(id)` mit
  `App.chatScroll.returnTo(fn)` davor — das Öffnen steht dann ohne Fahrt an
  genau dieser Stelle und hält sie, solange das Layout nachzieht —, solange der
  Nutzer noch auf dem leeren Start ist
  (max. 5 min alt). War der Anmeldestand schon bekannt, bevor das deferred
  App-Bundle lief (das Firebase-Modul war fertig, das Bundle lud noch), ist das
  Ereignis vorbei: dann liest es nach `load` `window.__consensioAuthState`. `consens.appUpdate.attempt` verhindert eine Schleife, wenn
  während eines Deploys noch die alte Instanz antwortet (gleicher Ziel-Build
  frühestens nach 10 min erneut). Verborgene Seiten fragen nie periodisch
  und laden nicht wiederholt — jeder Reload kostet die Start-Reads des Kontos.
  Umami: `app_updated` (`reopened`).
- **Der Lichtweg (Agent, seit 2026-10-02)** — das Hauslicht aus
  `send-glow.css` sitzt am Senden-Knopf und an der Agreement-Zahl: beim ersten
  Markieren einer geprüften Antwort (`#agentAnswerBody.is-marks-revealing`)
  fängt `.agent-agreement-num` das Licht einmal ein. Den Fortschritt der
  Vergleichsmodelle zeigen seit 2026-10-07 die Modell-Icons in der
  Aktivitätszeile selbst (Max-Entscheidung, statt der früheren Haarlinie
  `.agent-light` zwischen Zeile und Live-Text, die den Abstand eng machte):
  unter `.agent-activity.is-running` ist ein Icon mit `data-status`
  waiting/working/question/rework blass und grau und pulsiert sanft
  (`agent-model-wait`), failed/stopped bleibt blass; `completed` blendet in
  die eigene Farbe über. Kein Rahmen um die Icons (Max). Den Status setzt
  `agent-delegation.js` schon immer auf die `.agent-inline-model`-Buttons.
  Seit 2026-10-08 füllt eine ruhige Zeile die sonst stille Vergleichsphase
  („Comparing perspectives…“): `agentDelegation.liveHighlights(chatId, turnId)`
  liefert seit 2026-10-21 für jedes noch laufende Vergleichsmodell (Judges nie)
  die letzte Zeile seines `progress_text` mit `order` (Reihenfolge, in der die
  Modelle kamen); `agent-chat.js::project` reicht die Liste als `highlights` an
  `agentActivity.render`, das sie nur live und nur in dieser Phase als
  `Modell: Satz` unter den Schritt setzt (ein `<p>` unter dem internen Schlüssel
  `comparison-highlight`, `aria-hidden`, damit der Screenreader-Log nicht
  überläuft; nie gespeichert). `comparisonLine` lässt jeden Auszug mindestens
  `LINE_DWELL_MS` (2,5 s) stehen und gibt die Zeile dann reihum an das nächste
  Modell mit neuem Auszug (ohne Neues behält sie das sprechende Modell); ein
  eigener Timer (`scheduleLine`) rückt sie auch ohne neues Ereignis weiter, und
  `crossfade` blendet den Text weich über (bei reduced-motion sofort). Bis
  2026-10-21 gewann immer das Modell, das zuletzt berichtet hatte: die Zeile
  wechselte etwa alle 0,5–1 s. Damit die Zeile nicht
  nach wenigen Sätzen einfriert, nutzen Vergleichsantworten
  `ReasoningProgress(unlimited=True, min_seconds=THINKING_UPDATE_SECONDS)`
  (andere Worker behalten das Limit), und `comparison_selection` fordert für
  OpenAI-Modelle mit Reasoning `reasoning.summary = "auto"` an
  (`agent_client.with_reasoning_summary`, wie im Chat-Modell), sonst kämen nur
  verschlüsselte Blöcke. Keine zusätzlichen Modellaufrufe und kein
  zusätzliches Reasoning: es wird nur lesbar, was ohnehin gestreamt wird.
  Seit 2026-10-09 lässt `ReasoningProgress` kurze Ansagen des eigenen nächsten
  Schritts weg (`_plan_only`: ≤ 40 Zeichen, beginnt mit „I'll/Let me/I should…"
  oder „No search needed"): GLM zeigte sonst nach der Such-Entscheidung
  „I'll answer directly." als einzige Live-Zeile.
  Modelle ohne Reasoning (z. B. Haiku, Mistral Small) liefern keine Zeile.
  Die Landing-Schiene (`.lp-scene-rail`) zeichnet weiter die alte Linie.
  Reduzierte Bewegung: kein Pulsieren, kein Aufleuchten. Alles Drückbare gibt
  beim Druck auf 97 % nach (`base.css`, Spezifität 0, eigene Transforms
  gewinnen).
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
- **`composer-invite.js`** (seit 2026-10-15, vor `app-init.js`, nur zur Laufzeit
  gerufen) — lädt zur ersten Frage ein. `window.App.composerInvite`:
  `sendAsGuest()` (erste Prüfung in `window.sendQuestion`, `query-send.js`):
  für einen Gast Entwurf speichern (`App.saveQuestionDraft`), den Sendewunsch
  `localStorage["consensio.sendAfterLogin.v1"] = {at, source, text, mode?}` merken
  (`mode` nur, wenn der Gast selbst einen Modus gewählt hat,
  `userSettings.get("run_mode")`) und den
  Registrierungsdialog mit Begründungszeile öffnen; `afterAccessUpdate(canStartRun)`
  (Ende von `updateQuestionInputAccess`): sobald ein Konto fragen darf, setzt es
  einen mitgebrachten `mode` (`App.runMode.set(mode, {source: "guest"})`, auch
  gegen die Einstellung eines bestehenden Kontos, die dann so gespeichert wird;
  ohne `mode` gilt der Modus des Kontos, im Standard Agent), und erst danach
  wartet es, bis die Sitzung in diesem Modus laufen darf; sobald die neue Sitzung laufen darf,
  einmal `window.sendQuestion()` (höchstens 1 h alt, nur in einen neuen Chat,
  nur wenn das Feld genau `text` hält, nie während `App.reloadingAfterSignIn`
  aus `firebase.js::continueSignedIn`, der Wunsch wird beim ersten Versuch
  gelöscht). Vertrag in `app-init.js`: der erste Aufruf von
  `updateQuestionInputAccess` kommt erst nach `App.restoreQuestionDraft()` —
  `/user_status` kann nach dem Login-Reload schon vor dem App-Start da sein,
  und ein leeres Feld verbrauchte sonst den einen Versuch
  (`tests/e2e/test_composer_invite.py`, beide Reihenfolgen); `takeAskContext()` für
  `App.trackAsk` (`source` typed/example/pasted, `after_login`). Dazu die
  Klicks auf die Beispielfragen `#composerStarters` (füllen nur das Feld;
  kuratierte wie vorhergesagte, `data-starter="predicted"`) und
  `--starters-room` auf `.input-section` (Höhe der Beispielzeile samt Rand),
  um das der Hinweis beim Tippen in ihren Platz gleitet (composer.css).
- **`composer-starters.js`** (seit 2026-10-16, Head-Bundle vor
  `app-bootstrap.js`) — vorhergesagte Beispielfragen. `window.App.composerStarters`:
  `seed(row)` (aus dem First-Paint-Seed von `app-bootstrap.js`, sobald der
  „Check an AI answer“-Knopf geparst ist) malt die gespeicherte Vorhersage
  `localStorage["consensio.starterQuestions.v1"] = {uid, basis, at, questions}`,
  wenn sie zum Konto passt (vor der Auth über die `user_id` im gespeicherten
  ID-Token, sonst `__consensioAuthState`) und höchstens 7 Tage alt ist;
  `refresh()` (von `firebase.js` nach der ersten Listenseite, nach jedem
  bestätigten Save und nach einem Löschen; 1,5 s entprellt) fragt
  `POST /api/my/starter-questions`, sobald das Konto ≥ 3 Chats hat und sich die
  IDs der neuesten 12 (`basis`) geändert haben; unter 3 Chats wird die
  Vorhersage vergessen. „skipped“ oder ein Fehler lässt stehen, was da ist.
  Vorhergesagte Knöpfe stehen vor „Check an AI answer“, die kuratierten bleiben
  `hidden` im DOM und kommen zurück; unter Zeiger oder Fokus wird nie
  getauscht (erst bei `pointerleave`/`focusout`), sonst blenden sie weich ein.
  `clear()` (`clearAuthenticatedUiState`, ein anderes Konto oder Gast im
  `consensio:auth-state`-Event) nimmt Knöpfe und Speicher weg. Die
  Vorhersage wird nicht angekündigt: man erkennt die eigenen Themen.
- **`composer-keyboard.js`** (seit 2026-10-04, nach `composer-collapse.js`) —
  hält den fixierten Thread-Composer auf dem Handy (≤1099 px) an der
  Tastaturkante. Safari auf iOS ignoriert `interactive-widget=resizes-content`
  und lässt das Layout-Viewport unter der Tastatur stehen; `bottom: 0` lag dort
  hinter der Tastatur bzw. nach Safaris Scroll mitten im Bild. Solange ein
  Textfeld fokussiert ist und `visualViewport` mehr als 120 px kürzer als
  `documentElement.clientHeight` ist (ungezoomt), setzt das Modul
  `body.keyboard-open` und schreibt `--keyboard-lift` (Abstand der sichtbaren
  Unterkante über der Layout-Unterkante) an `.input-section` und den
  sichtbaren Bereich als `--keyboard-top` (Safaris Verschiebung) und
  `--keyboard-height` an jede offene Ebene mit Feldern (`dialog[open]`,
  Memory- und Gmail-&-Calendar-Sheet) — nie an `<html>` (Apple-Audit D9).
  `overlays.css` lässt diese Ebenen dann genau den sichtbaren Bereich decken
  (seit 2026-10-20, Apple-Audit F8: Login, Feedback, Settings, Teilen/Watch,
  Memory …), Sheets mit eigenem Scrollbereich nehmen `max-height: 100%`;
  `#shareModal` und `#systemPromptModal` (eigene `100dvh`) haben dafür eine
  Zeile. `tests/e2e/test_keyboard_dialogs.py`;
  `shell.css` (Abschnitt C) hebt den unten fixierten Composer per `transform`
  an (kein Layout beim Mitscrollen) und blendet den Hinweissatz aus. Seit
  2026-10-20 (F9) merkt es sich die Tastaturhöhe je Ausrichtung
  (`localStorage consensio.keyboardLift.v1`): beim Fokus in ein Composer-Feld
  fährt der Composer sofort mit der Tastatur hoch (`body.keyboard-moving`,
  280 ms iOS-Kurve, Vorhersage hält höchstens 1 s ohne Meldung), beim Verlassen
  mit ihr herunter; Safaris späte Meldung korrigiert nur. Android
  (Layout-Viewport schrumpft mit, keine Meldung einer verdeckenden Tastatur)
  und Desktop bleiben unberührt.
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
  (Senden) und `app-init.js` (`clearResponseBoxes`) niemand davon. Einzige
  Ausnahme ist die Anzeige: `App.quote.split(text)` trennt die gesendete
  Nachricht wieder in `{typed, quote}`, und `App.fillQuestionText` (app-core.js,
  für `#threadAsk`, `#threadPendingAsk` und `.thread-history-question-text`)
  zeigt das Zitat als `.thread-ask-quote`-Block unter der Frage statt des
  „Quoted from …"-Satzes. Seit 2026-10-09 behält die Blase außerdem die Absätze
  (`App.normalizeQuestionText` ebnet nur Leerzeichen und Leerzeilen-Folgen ein,
  `white-space: pre-wrap`); mehrere Absätze werden `.thread-ask-paragraph`-
  Blöcke, damit eine Leerzeile keine der eingeklappten Zeilen belegt.
  Eingeklappt wird großzügig: `App.observeQuestionFold(wrap, text)` (aktiver
  Kopf, schwebende Nachricht und jede archivierte Frage) setzt `is-long` erst,
  wenn mindestens drei Zeilen über acht hinaus verschwänden; dann clampt CSS
  auf 8 Zeilen, und „Show more ⌄" steht unten links in der Blase
  (`.thread-ask-bubble` = Fläche um Text und Link, Anhänge darunter).
  `dataset.question` bleibt der volle normalisierte Text (Identität der Nachricht). `query-send.js`
  hält Entwurf und Zitat getrennt in `sentMessage.{draft,quote}`, damit ein
  geplatzter Lauf beides unverändert zurückgibt. Das Menü zeigt „Ask about this"
  nur über Consensus-/Modellantworten (die eigene Frage zu zitieren wäre ein
  Kreis) — anders als Remember/Correct memory **ohne Konto**.
- **`app-init.js`** — das gesamte `initApp()`: Theme, Usage/Limits + User-Status,
  Response-Box-Toggles, Sidebar/Layout, FAQ-Aufklapper, Tooltips, Evidence-Rendering,
  API-Key-Test. Die FAQ-Fragen im Help-Dialog werden beim Start zu echten
  `button.faq-question` in ihrer `h3` (APG-Accordion, `aria-expanded`/
  `aria-controls`), damit die Tastatur sie erreicht. Die Bookmark-Suche filtert
  nach dem `await` auf `loadAllBookmarkMetadata` mit dem aktuellen Feldwert
  (Audit F6). Bis 768 px erzeugt Enter im Composer immer einen Absatz; nur
  Desktop-Enter sendet. Der Sidebar-Eintrag „Models“ zeigt Gästen einen kurzen
  Login-Hinweis und öffnet für eingeloggte Nutzer den Modell-Picker; eine
  Follow-up-/Neuvergleich-Wahl ist dafür nicht nötig.
  `clearResponseBoxes({silent?})` entfernt außerdem den kompletten
  fragebezogenen Share-/Citation-/Evidence-State. Der Usage-Countdown rechnet
  bis UTC-Mitternacht und fordert beim erkannten UTC-Tageswechsel über
  `window.refreshUsageData()` einen neuen autoritativen Serverstand an, statt
  lokal zu früh zu laufen oder die Seite neu zu laden. Der neue UTC-Tag wird
  erst nach einem bestätigten Refresh markiert; Fehler werden begrenzt erneut
  versucht, damit ein veraltetes `0 / Limit` den neuen Tag nicht blockiert. Der
  Sekundentakt ruht in einem versteckten Tab; `visibilitychange` rechnet beim
  Zurückkommen sofort nach (auch einen inzwischen erreichten UTC-Tageswechsel).
  Der unsichtbare `#countdownDisplay` („Resets in: HH:MM“) ändert sich nur
  einmal pro Minute: Über den MutationObserver auf `#usageDisplay` hält er
  `sidebar-quota.js` („in 3 h 12 min“) frisch, und jede Sekunde neu geschrieben
  zog er das Panel jede Sekunde nach. `sidebar-quota.js::sync` schreibt nur
  geänderte Werte (seit 2026-10-20, Apple-Audit D10). Läuft als letztes
  Script, ruft `initApp()` direkt auf. `localStorage` nur über
  `readStored`/`writeStored` (try/catch plus Seiten-Ablage wie in
  `user-settings.js`): bei gesperrtem Speicher wirft schon der Zugriff, und ein
  Wurf in `initApp()` ließ die App halb verdrahtet stehen.
  `tests/js/app-init-storage.test.mjs` bootet dafür die echten Gruppen `head` +
  `app` aus `bundles.json` in jsdom.

Das Admin-Dashboard ist ebenfalls externisiert: `static/css/admin.css` enthält
die vormals template-lokalen Styles, `static/js/admin.js` Auth, Rendering und
Aktionen. `static/js/admin-api.js` kapselt den authentifizierten JSON-Transport;
`static/js/admin-prompt-config.js` besitzt den separaten Configuration-Tab:
Laden/Speichern von Zeitzone und Delegations-Einstellungen, Änderungsanzeige,
schreibgeschützte Anzeige der Systemprompts (`#promptCatalog`, je Eintrag ein
`<details>` mit `<pre id="prompt-{key}">` aus `prompts_readonly`) und Schutz vor
verspäteten Antworten eines vorherigen Login-Zustands.
`admin.html` bleibt Markup und trägt nur deklarative `data-*`-Konfiguration.
Der Configuration-Tab liegt im inkludierten Partial `partials/admin_prompt_config.html`.

**Nicht unter `static/js/`** (älter, eigene Verantwortung):
- **`static/firebase.js`** (ES-Modul) — Firebase-Init, Login/Logout, Token-Handling,
  `window.auth`, Bookmarks-CRUD-Calls, Voting, Tier-Sync sowie das
  Nutzericon-Menü im Sidebar-Footer (Avatar, Name/Plan, „Shared links“ und
  direkt darunter „Watched“). Ein geöffnetes Bookmark beendet den Hero-
  Leerzustand sofort. Bookmark-
  Jeder vom Server bestätigte Save (`upsertBookmarkMeta`, nicht das Laden der
  Liste) fordert für ein Bookmark ohne `title_source` `"generated"`/`"user"`
  (`KEPT_TITLE_SOURCES`) einmal pro
  Sitzung `POST /bookmarks/{id}/title` an (`requestBookmarkTitle`); ein vom
  Nutzer gesetzter Name kommt über `PATCH /bookmarks/{id}/title` (`{title}`,
  `rename_bookmark`, schreibt erst das Bookmark, dann den Chat-Titel) und bleibt.
  Der generierte Name landet nur auf einem Bookmark ohne eigenen Namen
  (Guard in derselben Transaktion) und danach nur dann auf dem Chat, wenn das
  Bookmark ihn noch trägt (`_name_chat_as_generated`): ein Umbenennen während
  der Titel-Erzeugung wird nie überschrieben. `requestBookmarkTitle` blendet
  den Namen in Sidebar-Zeile, Run-Zeile und `bookmarksData` weich ein
  (`applyBookmarkTitle`); ältere Unterhaltungen bekommen ihn beim nächsten
  Turn. Liste, Saves und Löschen stoßen außerdem
  `App.composerStarters.refresh()` an (vorhergesagte Beispielfragen), der
  Logout `clear()`. Die Sidebar zeigt den ganzen Namen, gekürzt nur noch per CSS-Ellipse
  (vorher hart nach fünf Wörtern mit „...“). Die erste Listenseite übernimmt
  vom Skeleton an Ort und Stelle (`revealLoadedBookmarks`): das Skeleton
  blendet absolut positioniert aus, die ersten 16 Zeilen blenden gestaffelt
  ein. `onIdTokenChanged` richtet eine Sitzung (UID + Auth-Generation) nur
  einmal ein; der stündliche Token-Refresh erneuert nur noch das
  Session-Cookie (`/confirm-registration`) statt Status, Usage, Watches und
  Account-Menü neu zu laden. `/usage` läuft beim Start nur noch, wenn
  `/user_status` scheiterte (gleiche Nutzlast).
  Die paginierte Liste hält nur kompakte Metadaten in `window.bookmarksData`;
  `GET /bookmarks` sortiert nach `timestamp` und Dokument-ID (absteigend, kein
  eigener Index) und gibt als `next_cursor` die Sortierwerte der letzten Zeile
  aus (seit 2026-10-11): Wird dieses Bookmark gelöscht oder wandert es durch
  einen neuen Agent-Turn nach oben, setzt „Load more“/die Suche trotzdem dort
  fort, wo die Liste stand (vorher 400 „Bookmark cursor expired“).
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
  jedem Token-Callback entfernt, bevor ein neuer gebunden wird. Das Account-Menü
  besteht seit 2026-10-05 aus echten `<button>`s (Öffner `#emailIcon` mit
  `aria-haspopup`/`aria-expanded`, Einträge `role="menuitem"`): Öffnen fokussiert
  den ersten Eintrag, Pfeile/Home/End wandern, Escape schließt und gibt den Fokus
  an den Öffner (`#emailIcon` oder `#accountIdentity`) zurück, Tab schließt.
  Adresse und Name werden per `textContent` gesetzt, nie ins Markup interpoliert.
- **`static/demo.js`** (ES-Modul) — Demo-Flow (`runDemoFlow`, im Agent-Modus
  `runAgentDemoFlow` auf der echten Agent-Oberfläche) für die „Demo"-Query;
  zeigt Gästen nach Abschluss der Demo am Eingabebereich eine Login-/Registrierungs-
  Aufforderung, ohne die Demo-Frage aus dem deaktivierten Feld zu entfernen, und
  beendet beim Start denselben Hero-Leerzustand wie eine echte Anfrage.
- **`static/app-ui.js`** — alleiniger Binder für Settings (`#systemPromptModal`)
  und Help (`#helpModal`), keine zweite Bindung mehr in `app-init.js`. Beide
  sind seit 2026-10-15 native `<dialog>` mit `aria-labelledby` und echtem
  Schließen-Button, geöffnet über `App.modalDialog`: Settings leert die Suche
  (`App.settingsSearch.clear`), setzt die Reiter
  vor dem Öffnen zurück und fokussiert den aktiven Reiter; Help ist ein
  Geschwister (nicht mehr Kind) von Settings und stapelt sich per `showModal()`
  darüber, Escape schließt zuerst Help, der Fokus geht an `#helpButton`. Der eigene
  System-Prompt ist die Kontoeinstellung `system_prompt` (`query-send.js` liest
  sie für jeden Lauf; leer = zentrale Admin-Konfiguration). Bekannte historische
  App-Defaults, die ältere Versionen selbst unter `localStorage.systemPrompt`
  ablegten, verwirft `user-settings.js` beim Lesen; `app-init.js` schreibt seit
  2026-10-12 keinen Default mehr (er machte den Standardtext zur „eigenen“
  Anweisung).

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

**Prompt-Caching (seit 2026-10-04).** Der System-Prompt des Orchestrators ist
über alle Nachrichten eines Chats byte-gleich: `AgentRunStore.messages` legt
nur `prompts.agent` ins System; Uhrzeit (sekundengenau) und gewähltes Modell
stehen als App-Kontextblock (`with_app_context`, Marker
`APP_CONTEXT_OPEN/CLOSE`) **vor** der neuesten Nutzerfrage, die
Verlaufsnachrichten bleiben wörtlich. Vorher stand die Uhrzeit oben im System
und machte jeden Cache ab dort bei jeder Nachricht ungültig.
`DelegationLoop` hängt danach (wie bisher) Orchestrator-/Vergleichsregeln an
und zuletzt Memory, sodass eine Memory-Änderung nur ab dort neu cached.
Was sich zwischen den Nachrichten eines Chats ändert, steht seit 2026-10-21
ebenfalls im App-Kontextblock der neuesten Frage (`DelegationLoop._app_context`
→ `agent_runs.add_app_context`): die Dateiliste („Files available in this
chat: …“, ändert sich mit jedem Upload) und die Google-Auswahl dieser
Nachricht („Google data access was explicitly enabled for this message: …“).
Im System bleiben nur ihre festen Regeln (`UNTRUSTED`, Google-Regeln), die mit
denselben Tools kommen und gehen; die Tool-Liste ändert sich mit Dateien oder
Google ohnehin, das ist selten. Hinweise für **einen** Schritt („Web search is
unavailable for this step …“ in `_admit_chat_step`, `GOOGLE_NO_SEARCH` in
`_step`) hängt `with_step_note` als eigene Nutzer-Nachricht **ans Ende** der
Anfrage statt an `messages[0]`: so bleibt der Präfix der vorigen Schritte
lesbar. Ausnahme: der Hinweis im Rückfall begrenzter Läufe (`_step`, bei
`AgentTokenBudgetExceeded` ohne Kontomodus) hängt noch am System; Chats laufen
im Kontomodus und erreichen ihn nicht.
`answer_conversation` (der echte Verlauf für Memory-Belege, Passagensuche,
lesbare Links) entfernt den App-Kontextblock (`strip_app_context`). `prompt_cache_control` setzt für
`anthropic/`- und `qwen/`-Modelle OpenRouters automatisches
`cache_control: {type: ephemeral}` (die übrigen Anbieter cachen Präfixe selbst),
für jeden Schritt der Tool-Schleife einschließlich des Schritts, der die Antwort
schreibt. Bis 2026-10-14 lief der getrennte Antwortschritt mit eigener Uhr ohne
Cache (`prompt_cache=False`) und las Gespräch und Vergleichsantworten ein zweites
Mal. Gemessene `cached_input_tokens`/`cache_write_tokens` laufen wie bisher über
`measured_usage` in Kosten und Kontingent.

**Cache nur, wo ihn jemand liest (seit 2026-10-21).** Ein Cache-Write kostet bei
Anthropic ein Viertel mehr als normaler Input, ein Read ein Zehntel. Pro
Aufrufart: Schritte des Chatmodells lesen den Präfix im nächsten Schritt und
(über die festen Cache-Punkte, siehe unten) in der nächsten Nachricht → Cache. Vergleichsantworten (`kind: comparison`) sind
eine Anfrage, deren Suchrunden den eigenen Prompt wieder lesen (14 Tage bis
2026-10-21: 21 von 49 Claude-Antworten lasen Cache, netto positiv) → Cache nur
mit Suche. Judges sind einmalige Aufrufe (Retries, Hedges und Coverage-Fenster
unterscheiden sich im Nutzerblock, an dem der automatische Breakpoint sitzt) →
kein Cache. `DelegationLoop.worker_completion` setzt dafür
`AgentCompletion.one_off` (Vergleich, Judge) und `AgentCompletion.stream`
sendet `cache_control` nur, wenn `not one_off` oder die Anfrage Suchrunden hat.
Seitenlesungen (`PageFetch`, Responses-API) senden ohnehin keinen Marker.
Messen: `scripts/cache_hit_rate.py` (nur lesend; pro Tag, Familie und
Aufrufart Anteil `cached_input_tokens/input_tokens`, Writes/Reads und für
Anthropic die Netto-Ersparnis in vollen Input-Tokens; `--exclude-own` lässt
Max' Konten weg).

**Such-Tool und Cache (live gemessen 2026-10-21).** Die Probe bestand aus sechs
Sonnet-5.5-Calls über OpenRouter, alle auf dem Anthropic-Endpunkt in einer Session,
mit gleichem Präfix von 8,8k Tokens. Ergebnis:
- `max_uses` 3 → 1 (samt `max_total_results`) und `max_tool_calls` lesen den Cache
  voll, 8806 von 8810 Tokens. Der Wechsel 3 → 1 Runden zwischen Recherche und
  Folgeschritten kostet also nichts.
- Fehlt `openrouter:web_search` ganz, gibt es einen vollen Miss. Die Definition des
  Such-Tools selbst sind rund 2,5k Prompt-Tokens.

Den Präfix brechen also nur Schritte mit `searches_enabled=False`: der Schritt nach
`_consensus_search_handoff` (Recherche am Such-Cap) und der Abschluss am Turn-Limit
(`_wrap_up`). Beide lassen das Tool bewusst weg, denn `tool_choice: none` würde
auch `compare_models` sperren. Ungeprüft ist, ob `max_tool_calls: 0` bei stehendem
Tool die Suche zuverlässig sperrt. Erst prüfen, wenn `cache_hit_rate.py` nach dem
Deploy diese Schritte als Kostenposten zeigt.

**Sticky Endpunkt (seit 2026-10-21).** Jeder Endpunkt cacht nur für sich
(Claude läuft bei Anthropic, Vertex und Bedrock mit getrennten Caches). Ohne
Session hält OpenRouter ein Gespräch erst nach einem gesehenen Cache-Treffer
auf einem Endpunkt, der Durchsatz-Sort konnte den nächsten Schritt also auf
einen kalten Endpunkt schicken (2026-10-17: Sonnet schrieb den Cache in 93 von
134 Calls, las ihn in 32). Deshalb trägt jeder Schritt des Chatmodells
(`AgentLoop.run`, `DelegationLoop._step` ohne `worker`) OpenRouters
Session als Header `x-session-id` (gleichwertig zum Body-Feld `session_id`,
kann den Request aber nie ungültig machen) aus
`openrouter_contract.provider_session_id`: ein SHA-256-Präfix über uid und
Chat-ID, gleich für alle Nachrichten eines Chats, ohne beide im Klartext. OpenRouter bleibt damit ab dem ersten erfolgreichen
Aufruf beim selben Endpunkt (pro Modell, Fallback bei Ausfall, vergessen nach
10 min Leerlauf). Jeder Hilfsaufruf (Vergleichsantwort, Judge, delegierter
Worker) bekommt seit 2026-10-21 eine eigene Session
(`provider_session_id(uid, chat_id, worker.id)` über
`DelegationLoop.worker_completion` → `AgentCompletion.session_id`): Der Retry
einer leer beendeten Antwort und der nächste Schritt eines Workers senden
denselben Präfix noch einmal; die erste Anfrage nimmt weiter den schnellsten
Endpunkt, und kein Hilfsaufruf teilt die Session des Chats oder eines anderen.
Seitenlesungen (`PageFetch`) senden keine. Die Session gehört dem Adapter
(`AgentCompletion.stream`), ein Registry-Feld `session_id` wird verworfen.
Nachgemessen nach dem Deploy (Receipts 2026-10-21 23:55 bis 2026-10-22 12:30,
`cache_hit_rate.py`): Innerhalb einer Nachricht wirkt die Session, der
zweite Sonnet-Schritt las jedes Mal den ganzen Write des ersten. Über Nachrichten
hinweg las kein einziger erster Schritt (0 von 20, Folgefragen eine Minute
später eingeschlossen); das lag am Breakpoint, nicht am Endpunkt (siehe
nächster Absatz).

**Feste Cache-Punkte (seit 2026-10-22).** Der automatische Breakpoint sitzt
auf dem letzten Block. Den Präfix eines Schritts setzt der nächste Schritt
fort, die nächste Nachricht nicht: Wo der Schritt seine Tool-Aufrufe hatte,
steht dort die fertige Antwort, und der App-Kontext der Frage ändert sich
jedes Mal. Eine Leseposition gibt es aber nur, wo eine frühere Anfrage einen
Breakpoint hatte. So schrieb jede neue Nachricht ihren ganzen Prompt neu
(Sonnet: 9–20k Tokens zum Write-Preis, rund 3 Cent pro Nachricht; GPT-6 Luna
setzt eigene Breakpoints und las 98 %). `agent_client.with_cache_points`
setzt deshalb für Anfragen mit Marker zwei eigene Breakpoints: das Ende des
System-Prompts (über alle Nachrichten eines Chats gleich, Memory schließt ihn
ab) und die letzte frühere Nachricht des Chats (`AgentLoop.history_end` =
Index vor der neuen Frage, nur Schritte des Chatmodells über
`AgentCompletion.history_end`; Worker markieren nur ihr System). Die nächste
Nachricht liest damit System und Verlauf bis zur vorletzten Antwort. Ein
Token wird nur einmal geschrieben, egal welcher Breakpoint ihn abdeckt: Bei
einem Miss kosten die Punkte nichts. Mit dem automatischen sind es drei der
vier erlaubten Breakpoints; die Punkte gehen nur in den Request
(`content` als ein Textblock mit `cache_control`), `self.messages` bleibt
unverändert. OpenRouter dokumentiert beide Formen, die Kombination nicht
(Anthropic selbst schon). Deshalb gibt es ein Netz: Lehnt der Anbieter die
Anfrage mit HTTP 400 vor der ersten Zeile ab, geht dieselbe Anfrage einmal
ohne die Punkte raus (`_sse_lines`; ein 400 kostet nichts). Klappt das, setzt
der Prozess `_CACHE_POINTS_REFUSED` und sendet keine Punkte mehr (Log-Warnung
„Provider refused explicit cache points“, Metrik `cache_points_refused`).
Scheitert auch die zweite Anfrage, lag es nicht an den Punkten, und der
Fehler bleibt. Live nicht geprobt; nach dem Deploy mit `cache_hit_rate.py`
den Anteil gelesener Tokens der ersten Sonnet-Schritte (`step completion:0`)
von Folgefragen nachmessen.

Nachgemessen 2026-10-23 (Receipts seit dem Deploy 2026-10-22 14:18, live ist
`cae2e3f`): **Die Punkte wirken nicht.** Keine der sieben Folgefragen unter fünf
Minuten (35–241 s nach der vorigen Nachricht) las den Cache, jeder erste
Sonnet-Schritt schrieb wieder den ganzen Prompt. Innerhalb einer Nachricht las
jeder Folgeschritt weiter den vollen Write des vorigen. Im Render-Log stand
keine „Provider refused explicit cache points“-Warnung, die Punkte gingen also
raus und wurden angenommen. Die Generation-Statistik von OpenRouter
(`GET /api/v1/generation?id=<generation_id aus dem Receipt>`, kein
Modell-Call) nennt für **jeden** Claude-Schritt `provider_name: Google`, also
Vertex. Die Session hält, am Endpunkt liegt es nicht. Reservierte Ausgabe und
Suchrunden waren über die Folgefragen gleich, eine geänderte
Thinking-Konfiguration scheidet damit aus. Zum Vergleich las GPT-6 Luna bei
Folgefragen fast den ganzen Präfix (83 s später 11 979 von 12 803 Tokens).
Tools, System und Verlauf sind über Nachrichten also stabil. Offen bleibt,
ob OpenRouter oder Vertex die Block-Marker neben dem Top-Level-Feld
verwirft oder ob Claudes Präfix etwas Eigenes enthält. Klären lässt sich das
nur mit einer Live-Probe (wenige Haiku-/Sonnet-Calls, ein paar Cent): zwei
Nachrichten nacheinander, einmal mit beiden Markerformen, einmal nur mit
Block-Markern (letzter Block explizit statt Top-Level), einmal ohne Suchtool,
dazu einmal auf dem Endpunkt `anthropic` gepinnt. Es geht um rund 2–3 Cent je
Folgefrage (Woche bis 10-22: 20 von 51 ersten Claude-Schritten). Die Punkte
bleiben drin, weil sie bei einem Miss nichts kosten.

**Live-Probe 2026-10-23 (auf Max' OK, 10 Sonnet-5.5-Calls, rund 18 Cent, alle
bei Google/Vertex):** Je ein Paar aus erster Nachricht und Folgefrage, eigener
System-Prompt von rund 6k Tokens, Produktions-Routing und Session-Header.
- Ohne Tools, Produktionsform: die Folgefrage liest den System-Prompt
  (6.393 von 6.440 Tokens). Die Punkte funktionieren also an sich, auch bei Vertex.
- Mit `openrouter:web_search` (mit oder ohne Funktions-Tool, mit oder ohne
  Top-Level-Feld, nur explizite Punkte): 0 gelesen. **Mit dem Such-Tool
  cacht eine Anfrage nur an ihrem letzten Breakpoint**; Punkte mitten im
  Prompt legen nichts an. Innerhalb einer Nachricht trifft der nächste
  Schritt trotzdem, weil sein Prompt den vorigen ganz fortsetzt.
- Mit Such-Tool, die Folgefrage wiederholt die erste Frage byte-gleich samt
  App-Kontext: 7.449 von 7.490 gelesen, 0,4 statt 2 Cent.

**Umsetzung:** `create_turn(app_context=…)` speichert den App-Kontext der Frage
(`get_agent_turn_context`, im Agent-Router einmal berechnet und an
`store.messages(context=…)` weitergereicht) am Turn-Dokument, nie in seiner
Projektion (`turn_metadata`), höchstens `MAX_APP_CONTEXT_CHARS`.
`AgentRunStore.messages` wiederholt frühere Fragen mit ihrem gespeicherten
Kontext (`with_app_context`), Turns von vorher ohne. Damit beginnt der erste
Schritt der nächsten Nachricht mit genau dem Prompt des ersten Schritts der
vorigen, und Anthropics Rückblick (bis 20 Blöcke vom letzten Breakpoint)
findet dessen Eintrag. Kein Treffer bei Fragen mit Dateien oder Google-Daten
(der Dateiblock bzw. der Zusatzkontext aus `DelegationLoop._app_context` steht
nicht im gespeicherten Kontext) und nach einer Kürzung des Verlaufs
(`HISTORY_OMITTED_NOTE`). Memory-Belege und Vergleiche lesen die Fragen ohne
Kontext (`answer_conversation` mit `strip_app_context`). Der Eintrag lebt fünf
Minuten ab dem letzten Lesen; der zweite Schritt einer Nachricht frischt ihn
auf. Test: `tests/test_agent_runs.py`
(`test_the_next_message_repeats_the_question_exactly_as_it_was_sent`).
Nachmessen nach dem Deploy: `cache_hit_rate.py --days 2 --family anthropic`.

**Zugang seit 2026-10-02: jedes angemeldete Konto.** `require_agent_access`
verlangt nur noch eine UID (`/user_status` meldet `agent_access: true`); das
Tageskonto begrenzt Agent pro Stufe. Pro bleiben die Premium-Modelle:
`require_model_access` lehnt in `POST /agent` ein Chatmodell oder
Vergleichsmodell aus `cfg.PREMIUM_MODELS` für Free/Plus mit 403 ab (ein
ausgefallener Tarif-/Rollendienst liefert sicher 503), `/agent/models` markiert
sie mit `premium`, und `agent-chat.js` zeigt sie mit Pro-Badge, aber gesperrt
(`locked()`/`selectable()`). Ebenso seit 2026-10-07 die Denkstufen High, Extra
high und Max (`PRO_REASONING_EFFORTS`, `require_reasoning_access` → 403 für
Free/Plus; `agent-chat.js` `effortLocked()` zeigt sie gesperrt mit Pro-Badge und
fällt bei gespeicherter Wahl auf Auto zurück). Seit 2026-10-08 läuft „Auto“
ohne Pro als Medium, wo das Modell Medium anbietet: Auto schickt sonst keine
Stufe, und Sonnet 5.5 denkt dann mit seinem Standard „high“, einer Pro-Stufe.
`agent_client.free_default_effort(model_id)` entscheidet (Registry-Einträge mit
fester niedriger Einstellung wie Kimi aus / GLM low behalten sie, eine fest
eingetragene Pro-Stufe („high“) wird Medium; ohne Medium bleibt
Auto), `run_agent` löst damit auf, die gespeicherte Auswahl und die
Request-Identität behalten „default“. `/agent/models` meldet je Modell
`free_default_effort`; `agent-chat.js` (`autoEffort`/`visibleEfforts`/`effortFor`)
blendet für Nicht-Pro dann „Auto“ aus und wählt Medium. Ausnahme seit 2026-10-07: das Standard-Chatmodell
(`default_agent_model_id()`, derzeit Claude Sonnet 5.5) ist als Chatmodell für
jede Stufe frei; `/agent/models` meldet es mit `premium: false` und
`early_access: true`, der Picker zeigt ein neutrales „Early access“-Badge
(`.pro-badge.is-neutral`). Als Vergleichsmodell bleibt es Pro. Begründung und
Blindtest in `docs/agent-mode.md`. Uploads (`POST /agent/chats/{chat}/files`) folgen
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
`provider_label` ordnen jedes Modell seiner Registry-Familie zu. `aliases`
(seit 2026-10-12) bildet migrierte IDs aus `cfg.PROVIDER_MODEL_MIGRATIONS` auf
ihren gelisteten Nachfolger ab, wie `resolve_agent_model` es serverseitig tut.
`agent-chat.js` wählt damit für eine gespeicherte Alt-ID (z. B.
`grok-4.3-no-reasoning`) den Nachfolger statt des Defaults. Die Auswahl für die
nächste Nachricht wird nur bei dauerhafter Ursache zurückgeschrieben (migrierte
ID, Modell nicht mehr gelistet), und in die Kontoeinstellung `agent_model` nur,
wenn sie von dort kam (bis 2026-10-12 `agent_settings_<uid>`; ein Konto ohne
gespeicherte Einstellungen übernimmt den Wert beim ersten Abgleich): Ein alter Chat mit totem Modell ändert die Wahl für neue Chats nicht,
ein gelistetes, gerade nicht verfügbares (`available: false`) oder noch als Pro
gesperrtes Modell fällt nur pro Nachricht zurück (Hinweis einmal je Chat).

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
`.composer-models` (`.agent-model-picker`). Seit 2026-10-23 sagt das Label,
was die Vergleichsmodelle tun: „6 AIs cross-check“ („6 KIs prüfen mit“,
`App.words.crossCheck`, unter 2 Modellen „No cross-check“); das Chatmodell
steht im Tooltip („<Chatmodell> writes the answer, 6 AIs cross-check it.“)
und im Menü. Vorher „<Chatmodell> +6“, das Neulingen nichts sagte. Der erste
Frame (`app-bootstrap.js`) zeichnet dasselbe Label; `App.firstFrame` merkt
sich den Namen des Chatmodells aus dessen Select. `renderControls` verknüpft
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
Auswahl. API-Aufrufe ohne Auswahl behalten das zentrale Default-Preset
(`cfg.DEFAULT_CONSENSUS_PRESET`, seit 2026-10-15 Daily wie
`cfg.APP_DEFAULT_CONSENSUS_PRESET`, mit dem die App seit 2026-10-12 startet). Der öffentliche
Metering-Katalog ergänzt die gemeinsame Registry automatisch um aktuelle
Provider-Metadaten; neue Admin-Einträge benötigen keinen zusätzlichen Codeeintrag.

Die gemeinsame `#composerModeBar` ist wie in jedem Modus nur auf dem Startbildschirm
sichtbar. Nach Chatstart nutzt Beta das vorhandene `#attachMenu`: Agent-Status verwendet
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
freie Trefferflächen der Optionen bei 320 und 390 px.
`POST /agent.check_sources` gibt es seit 2026-10-15 nicht mehr als Schalter
(Quellenprüfung entfernt); das Feld wird von alten offenen Seiten noch
angenommen und ignoriert.

POST /agent verwendet den bestehenden DelegationLoop mit `AgentPolicy.for_chat`.
`account_budget_only` ersetzt zusätzliche Laufzeit-, Call-, Tool-, Worker-Runden-,
Such-, Nachrichten- und Dollarlimits durch das zentrale Tages-Tokenbudget. Im
persistierten Policy-Snapshot stehen die nicht angewendeten Limits auf null.
Der injizierte AnalysisBudget ist nur für diesen Lauf zeit-/aufrufunbegrenzt;
Consensus und Legacy-Aufrufer behalten ihre eigenen Grenzen. Seit 2026-10-05
begrenzen weiche Schutzgrenzen pro Turn (`AgentPolicy.turn_*`, gesetzt nur in
`for_chat`, im Snapshot sichtbar) eine Schleife gültiger Aufrufe: 4 Vergleiche
(der fünfte ist ein Tool-Fehler), 24 Orchestrierungsschritte, 15 min bis zum
Wrap-up plus 5 min (`TURN_WRAP_UP_SECONDS`) bis zum harten Stopp in `_check`, und
höchstens zwei identische Toolcalls (3. abgelehnt, 4. beendet; `wait_agents`
ausgenommen). Wrap-up (`_merged_wrap_up`) = der Agent schreibt die Antwort in
einem letzten Schritt ohne aufrufbare Tools aus einem Vergleich mit ≥2
Antworten, danach Judges; sonst `AnalysisBudgetExceeded` mit
gespeicherten Teilergebnissen; seit 2026-10-12 enden auch drei ungültige
Tool-Batches in Folge per Wrap-up (`TURN_INVALID_LIMIT`). Details und
Tabelle: [agent-mode.md](agent-mode.md) („Tageskontingent“-Abschnitt).
Worker-Delegation bleibt separat durch delegation_config.enabled und die
geprüfte Modell-/Reasoning-Kombination freigegeben. policy.delegation aktiviert
hier auch ohne Worker-Freigabe das gemeinsame persistente Schrittjournal.
agent_loop.py bleibt die gemeinsame Basis und der eigenständig testbare direkte
Legacy-Loop. Der ausgewählte Chat-Provider erhält seine vollständigen
Reasoning-/Signaturblöcke für Tool-Fortsetzungen zurück; verschlüsselte Blöcke
werden weder angezeigt noch persistiert. Weitere Details zur Worker-Kommunikation
stehen in [agent-delegation.md](agent-delegation.md).

**Vergleich und Prüfung.** agent_comparison.py registriert für den Agenten
`compare_models` (Frage, Kontext, Tiefe; frei: Familien) und `check_text` (wie
`compare_models` plus Passage) mit strikten Pydantic-Argumenten, in
fester Reihenfolge (Prompt-Cache). Ein Tool, das die Steuerung beendet, gibt es
nicht: die Antwort ist der Klartext eines Schritts ohne Toolcalls (bis
2026-10-14 das Tool `answer` mit getrenntem Antwortschritt, unten). `judge_answer` ist
`ComparisonTools.app_tools` (bis 2026-10-15 auch `check_contradictions`): der Server führt sie über
`DelegationLoop.app_registry` aus (`_finish_review`, `_execute_stream(..., registry)`),
das Modell sieht sie nicht. `ToolRegistry.validate` nimmt ein
Array-/Objekt-Argument, das als JSON-Text kommt (Sonnet schickte `"memory": "[]"`
und scheiterte dreimal an der Validierung), als den deklarierten Container
(`_decode_stringified`); alles andere lehnt die Validierung ab. Seit 2026-10-07 steuert allein
der Code-Prompt `prompt_defaults.AGENT_SYSTEM_PROMPT` (gespeicherte Admin-Prompts
wirken nicht mehr; seit 2026-10-14 = Steuerteil `_AGENT_STEERING` plus
Schreibregeln `AGENT_ANSWER_SECTION`). Seit 2026-10-11 entscheidet der Agent nach „COMPARE OR
ANSWER DIRECTLY“, ob er vergleicht (Fakten, Aktuelles, Rat, Strittiges, Recherche,
auf Wunsch; im Zweifel ja) oder direkt antwortet (Chat/App/frühere Antworten,
Umformulieren/Übersetzen, Gruß/Rückfrage, Watch, eine gezeigte Seite lesen);
beides in guided und free. Urteile (Meinung, Bewertung, Kritik, Empfehlung)
werden seit 2026-10-22 immer verglichen, auch zu angehängten Dateien und bei
„deine Meinung“; nur auf ausdrücklichen Wunsch ohne Vergleich. Sonst mit begründeten Annahmen weiterarbeiten. Die Schreibregeln (Journalist, Treue zur Substanz, eigene
Beraterstimme, keine Superlative, Uneinigkeit nur wo sie die Entscheidung ändert,
Quellenauszüge, `checked_text`, Antwort ohne Vergleich) stehen im Abschnitt
„WRITING THE ANSWER“ (`AGENT_ANSWER_SECTION`), weil der Agent die Antwort selbst
als letzte Nachricht seiner Tool-Schleife schreibt (unten). Die Judges startet
der Server selbst (`_finish_merged` → `_finish_review`), außer der Nutzer hat
die Antwortprüfung ausgeschaltet (`AgentPreferences.judges == "off"`: dann
`ComparisonTools.skip_review`, Review-Status `off`); ist die Antwort
fixiert, bekommt der Agent keinen weiteren Schritt mehr. `finalized=true`
ist ein Protokollabschluss, kein Erfolgsbeleg für alle Teilprüfungen. Die
Entscheidung vor dem ersten Vergleich bleibt promptgesteuert: kein zweiter
LLM-Router, keine sprachabhängige Keyword-Klassifikation.
Deaktivierte Worker
liefern weder Worker-Katalog noch Delegationsprompt im Chatkontext. Auch
Vergleichsmodelle, Judges und Worker erhalten eine knappe Rollen-/Produkterklärung.
Vor dem ersten Vergleich darf der Orchestrator bis zu drei Runden suchen
(`ORCHESTRATOR_SEARCH_ROUNDS`), nur um die Frage zu verstehen und zu formulieren;
seine Funde und Quellen gibt er nicht in den `context` (seit 2026-10-06), jedes
Vergleichsmodell recherchiert selbst. Beendet der Server-Suchloop einen Request
mit recherchiertem Text ohne Client-Tool, führt `_consensus_search_handoff`
einmalig ohne Quellenliste in die Client-Tool-Orchestrierung zurück.
Das Modell entscheidet selbst,
ob es die ganze Frage oder mehrere begründete Teilfragen vergleicht. Es
liefert einen neutralen Auftrag mit nötigem Kontext; alle Vergleichsmodelle
sehen dieselbe isolierte Aufgabe, keinen Chatverlauf und keine Antworten anderer
Vergleichsmodelle. Der Produktprompt verpflichtet das Chatmodell ausdrücklich,
Bezüge wie „davon“ aufzulösen und relevante frühere Anforderungen in Frage/Kontext
zu übernehmen; unabhängige Fragen brauchen keinen unnötigen Gesprächsrückblick.
Im freien Modus (`AgentPreferences.autonomy == "free"`) wählt es zusätzlich pro
Vergleich die Familien (`free_compare_args`: Enum der Turn-Auswahl, mindestens zwei,
Duplikate in `_choose`; jeder Vergleich speichert `asked`).
`ComparisonTools.compare` startet alle gefragten Vergleichsmodelle gleichzeitig in eigenen
Threads (`compare_slots`, je Aufruf eine `ComparisonCancellation`) und wartet nur
bis Quorum plus Nachfrist (`quorum_size`, `QUORUM_GRACE`, `MIN_GRACE_SECONDS`);
Standard ist seit 2026-10-07 `all` (jedes Modell, auch bei `quick`), weil eine
späte Antwort nicht mehr in die Prüfung kommt; `balanced` wartet nur bei `full`
auf alle. Seit 2026-10-08 endet jedes Warten mit mindestens zwei Antworten,
sobald `DelegationLoop.answer_time_left()` ≤ 0 ist: Zeit bis zum harten Stopp
minus `ANSWER_RESERVE_SECONDS` nach Denkstufe des Chatmodells (none 120 s … max
600 s); Nachzügler werden dann wie beim Quorum spät/`late_cutoff`. Dieselbe
Reserve zieht `_turn_limit` vor (Wrap-up, bevor eine „max“-Antwort nicht mehr
vor den harten Stopp passt).
`_rebuild` normalisiert Quellen wie zuvor `fan_out_provider_answers` (das der
Consensus-Modus unverändert nutzt) und führt `pending_models`, `failed_models` und
`late`. `judge()` prüft seit 2026-10-07 nur Antworten ohne `late`.
`judge_transport` filtert die Judge-Temperatur wie der Consensus-Pfad
(`_effective_temperature`, OpenAI gpt-5 und neuer, Gemini, Mistral-Reasoning).
Die Judges sehen jede Antwort als `<response label="Model A">…</response>`-Block
(`_response_block`), nicht mehr als `- Model A:`-Zeile.
`freeze_for_synthesis` legt `synthesis_providers` fest,
`finish_comparisons` stoppt vor den Judges verbliebene Nachzügler (`late_cutoff`)
und fixiert `basis_hash`; `close` beendet sie am Laufende (`stopped`). Was ein
gestopptes oder mitten im Stream ausgefallenes Modell bis dahin geschrieben hat
(`Worker.partial_text` aus `_step`), bleibt als
`failed_models[].partial_text` erhalten: nur für den Leser, nie in Synthese,
`answers`/`basis_hash`, Judges oder dem Tool-Ergebnis an den Orchestrator.
Die Agent-Sitzung bekommt dazu eine Nachricht `kind: "partial"` und `partial: true`.
Würde der Review-Snapshot 600 KB überschreiten, fallen zuerst diese Teiltexte weg. Vergleichsmodelle
erhalten keine Delegations-/Vergleichstools, aber Websuche
(`call(..., kind="comparison", search_rounds=…)` → `_step(searches_enabled=True)`;
`SEARCH_ROUNDS`: `quick` eine Runde, `full` bis zu drei, für alle Konten gleich;
ihre Suche wird gebucht, nicht reserviert, `soft_search`) und mit
`comparison_system_prompt` das aktuelle Datum. Judges suchen nie; der
Orchestrator sucht vor dem ersten Vergleich nur für sich selbst. Sobald ein Vergleich
bezahlte Antworten hat (bis 2026-10-14: schon ab seinem Start), dürfen die Schritte
des Agenten und die Judges das Tageslimit überziehen
(`_admit_chat_step` → `claim(overdraft=True)`). Jeder Schritt des Agenten im
Kontomodus kann die Antwort schreiben und wird mit dem Steuer-Budget zugelassen
(`_routing_model`); sein Antwortbudget darüber (`_answer_output`) reserviert er
einmal statt pro Suchrunde (`RunCosts.estimate(answer_output=…)`), und nur dieser
Teil darf schon vor einem Vergleich überziehen (`claim(overdraft=<Tokens>)` →
`agent_quota.reserve`): eine Direktantwort kurz vor dem Limit wird nicht
abgeschnitten, und Recherche geht nicht früher verloren. Suchkonfiguration (`search_tools`: eine für alle
Modelle, Engine `auto`, nur Grok fest Exa), Reservierung
(`SEARCH_INPUT_TOKENS` pro Runde, `smaller_search`) und Messwerte stehen
ausschließlich in [agent-mode.md](agent-mode.md), Abschnitt „Websuche“. Die Output-Grenze ist die Completion-Grenze des
Modells, begrenzt durch `_output_share` (fairer Anteil am freien Tageskontingent
über `agent_quota.remaining_tokens`). `depth=quick` gibt eine kurze Längenvorgabe,
`full` keine. Technische Token-, Kontext- und Snapshotgrenzen gelten weiter. Leere, abgebrochene oder Tool-Antworten gelten als fehlgeschlagen.
Strukturierte Transportfehler werden am Fehlerfeld erkannt, nicht am Wort
„Error“ im Antworttext; nur Legacy-Stringadapter behalten ihre Fehlerkonvention.
Mindestens zwei vollständige Antworten sind eine brauchbare Prüfgrundlage.

**Die Antwort schreibt der Agent selbst (seit 2026-10-14).** Mit Vergleichs-Tools
(`DelegationLoop.merged`, gesetzt, sobald `comparison_models` übergeben ist, auch
in begrenzten Läufen) ist der Klartext eines Schritts ohne Toolcalls die
Antwort; ein reiner Delegationslauf ohne Vergleichs-Tools endet weiter mit
seinem gestreamten Text. Nach einem Vergleich schreibt derselbe Aufruf, der die
Antworten liest, die Antwort (Vergleiche plus ein Agent-Aufruf); eine
Direktantwort ist ein einziger Aufruf. Nach jedem Vergleich sieht der Agent die
Antworten und entscheidet selbst: weiter vergleichen, eine Quelle lesen oder
schreiben (`next_step` gibt es seit 2026-10-11 nicht mehr, `CompareArgs`
ignoriert `reason`/`next_step` versteckt). `ComparisonTools._merged_result` ist
das Toolergebnis jedes `compare_models`/`check_text`: die vollen Antworttexte mit
ihren Quellen-URLs (keine gekürzte Routing-Fassung), `missing_answers` (Familie,
Modell, Grund), die Quellenliste mit Auszügen (`source_entries`, unten), nach
`check_text` zusätzlich `passage_check` und `checked_text`, dazu eine Anweisung
(schreiben, sobald die Antworten reichen; nur Fehlendes neutral nachvergleichen;
mit `read_source` zuerst der Lesehinweis). Die Tiefe steht nicht darin, sie
steuerte nur die Vergleichsmodelle. Der Vergleich ist damit fixiert (`_freeze`:
die Antwort ruht auf genau diesen Antworten, Nachzügler sind `late`). Hat ein
Vergleich des Schritts mindestens zwei Antworten geliefert, hängt `run` danach
`prompt_defaults.AGENT_WRITE_NOTE` als eigene Nutzer-Nachricht an: die nächste
Nachricht ist die vollständige Antwort aus allen Ergebnissen (wie Claude Codes
Erinnerungen am Ort der Arbeit, nicht nur im System-Prompt).
Streaming (`_orchestrate` → `_step(answer_candidate=True)`, `_candidate_delta`;
Konstanten in `agent_answer_mode.py`): Text erscheint ab `ANSWER_HOLD_CHARS`
(300) Zeichen, nie nach Beginn eines Toolcalls und vor dem ersten Vergleich nie
nach eigenen Suchtreffern; kürzerer Text (Gruß, Rückfrage) erscheint, wenn der
Schritt endet. `hold` (`_hold_answer`: ungeprüfte Worker, Mailbox oder eigene
Recherche ohne Vergleich) blendet ihn ganz aus. Folgt doch ein Toolcall, nimmt
`_retract` den Text per Status `retract` mit `clear_response` zurück und zeigt
ihn als Fortschrittszeile `note` (höchstens `NOTE_CHARS` = 400 Zeichen); folgen
nur `SIDE_TOOLS` (`update_memory`, `prepare_watch`), bleibt der Text die Antwort
(`_answered_with_tools`), aber nur, wenn ihre Ergebnisse angenommen sind
(`_side_results_accepted`), sonst `_retract` und ein weiterer Schritt. Nach einem Batch mit
fremdem Inhalt (`MEMORY_LOCKING_TOOLS`) sperrt `memory_locked` jede weitere
Memory-Änderung der Nachricht (`agent_memory.MEMORY_LOCKED`). Eigene Recherche ohne Vergleich:
`_consensus_search_handoff` (oben), danach hält `_tool_reminder` eine Antwort
über `DIRECT_REPLY_CHARS` (800) Zeichen einmal zurück (`TOOL_REMINDERS`);
kürzere Rückfragen stehen sofort, nach der Erinnerung steht auch eine lange
Antwort. Ungeprüfte Worker-Ergebnisse halten die Antwort zurück (`_retract`
plus Aufforderung zu `review_agent`). `_finish_merged` gleicht den sichtbaren
Text an (`_show_answer`, auch nach `_drop_presearch_text`), fixiert ihn
(`freeze_for_synthesis`, `capture`) und führt nach Vergleichen über
`_finish_review` `judge_answer`
über `app_registry` als eigene sichtbare Zeile aus („Checked the answer“). Mit
ausgeschalteter Antwortprüfung (`judges: off`, seit 2026-10-17) schließt
`skip_review` die Antwort ohne Judge ab: je Vergleich ein an Text und Grundlage
gebundener Check mit Status `off` ohne `differences_data`; `review_is_bound`
und `finish_run` zählen `off` zu `REVIEW_DONE`, die Seite zeigt „Answer check
off“ (`agent-review.js`). Ohne
Vergleich setzt er `ComparisonTools.direct`: keine Judges; `capture()` fixiert
den Text ohne Version, eine Review (`snapshot`-Status `direct`, Standard ohne
Vergleiche) entsteht nur mit gelesenen Seiten. Festgeschrieben und geprüft wird
nur ein vollständiger, nicht leerer Schritt ohne Toolcalls. Endet er am
Tokenlimit (`length`) oder bricht ab, bleibt schon sichtbarer Text nach
Vergleichen als ungeprüfte Teilantwort (`capture` nach dem Settlement, keine
Judges) und ohne Vergleich als Text des fehlgeschlagenen Turns erhalten,
gespeichert wird genau der gesehene Text (`value.published`); nie
sichtbarer Text (kurz, zurückgehalten oder zurückgenommen) wird nicht
gespeichert, außer eine kurze Antwort am Ausgabelimit (`_keep_cut_answer`
zeigt und speichert sie). Schon gezeigter Antworttext bleibt auch, wenn der
Schritt danach sucht (`_drop_presearch_text` schneidet nur Ungezeigtes). Turn-Grenzen: `_merged_wrap_up` (oben) schreibt die Antwort in
einem letzten Schritt mit gelisteten, nicht aufrufbaren Tools
(`allow_tools=False` → `tool_choice: none`, der Prompt-Cache bleibt), mit der
gewählten Denkstufe und dem Antwortbudget; offene Toolcalls bekommen vorher ein
Ergebnis (`_close_open_calls`). Bis 2026-10-14 beendete das Tool `answer` die
Steuerung, und ein getrennter, toolfreier Antwortschritt desselben Modells
(`_write_synthesis` mit `synthesis_messages`, `AGENT_ANSWER_PROMPT`/
`AGENT_DIRECT_ANSWER_PROMPT`, App-Fakten und `turn_summary`) schrieb aus einer
Evidenz-Nachricht, ohne Prompt-Cache und mit Gespräch und Antworten ein zweites
Mal gelesen (Git-Tag `agent-separate-answer-last`). Messung und Begründung:
[agent-mode.md](agent-mode.md), „Die Antwort schreibt der Agent selbst (seit
2026-10-14)“; `scripts/evaluate_agent_answers.py` misst den Weg live, auf Wunsch
gegen gespeicherte Antworten (`--baseline`, `--pairwise`), und zeigt je
Provider-Aufruf, wohin die Zeit geht (Zulassung, erster Token, Stille,
Settlement).

Jeder Schritt des Agenten mit Vergleichs-Tools bekommt das Steuer-Budget `routing_output_limit`
(`_routing_model`, seit 2026-10-08: `AGENT_MAX_OUTPUT_TOKENS` +
`ROUTING_REASONING_HEADROOM` = 16.384 bei denkenden Modellen; Prod: Sonnet „max“
brauchte 3.808/3.998 von 4.096 im ersten Schritt; die Reservierung wächst je
Suchrunde mit) und darüber, weil er die Antwort schreiben kann, das
Antwortbudget `answer_output_limit` (`_answer_output`, Zulassung oben): die
Completion-Grenze des Chatmodells; denkende Modelle bekommen seit 2026-10-07
`ANSWER_REASONING_HEADROOM` obendrauf, weil Reasoning im selben Budget zählt und
adaptives Denken bei Claude weder Effort noch `reasoning.max_tokens` einhält.
Seit 2026-10-08 entscheidet `agent_client.reasoning_active` über diese
Zuschläge: kein Headroom bei Effort `none`, `reasoning.enabled=false` (Kimi
K2.6) oder Modellen, die nur auf Anfrage denken (`default_enabled=false`), sonst
verdoppelten Reservierung und Stop-Schätzung (`unknown_estimate`) sich grundlos.
Endet ein Agent-Schritt ohne verwertbares Ergebnis (`_output_limited`:
`length` ohne Text, `length` mit halb geschriebenem Toolcall, oder nach Reasoning
`stop`/kein finish_reason ohne Text und Toolcall), wirft `AgentCompletion.stream`
`ModelOutputLimit` und setzt `output_limited` (Code `output_limit`, nicht mehr
`provider_error`); der `stop`-Fall ist die Unterklasse `ModelEmptyAnswer`
(Code `empty_answer`, seit 2026-10-15): kein Limit, sondern Zufall. `_step` wertet
das für Agent-Schritte (nicht Worker) als erledigten, bezahlten Schritt
(`_thought_only`), damit der nächste Claim nicht an einem fehlgeschlagenen
Vorgänger scheitert; eine Vergleichsantwort mit `retry_empty` ebenso
(`value.empty_answer`), und `AgentComparison.call` versucht sie genau einmal unter
`agent:<id>:1` erneut (gpt-oss-120b: 1 von 13 gleichen Aufrufen endete nach
Denken und Suche ohne Wort).
`run` wiederholt ihn genau einmal mit `lighter_reasoning` (`RETRY_EFFORTS`:
bewusst zuerst `low`, dann minimal → none, nie eine Stufe über der aktuellen)
unter eigenem `completion:N` (Fortschrittszeile `completion:N/retry`, schon
gestreamter Text wird zurückgenommen); die leichtere Stufe bleibt für weitere
Schritte des Turns (`routing_lighter`, auch im Antwortbudget), der Wrap-up
wiederholt ebenso einmal. Ohne leichtere Stufe oder bei erneutem Leerlauf endet
der Turn mit `output_limit` und `TURN_OUTPUT_LIMIT` (Rat: niedrigere Denkstufe
oder anderes Chatmodell). **429 nach bezahlten Vergleichen:** `_orchestrate`
(und der Wrap-up) ruft dann `_answer_attempt`, das einen kostenlosen 429
(`_free_rate_limit`: HTTP-Ablehnung, `provider_rejection`, kein Text;
`_step(retry_rate_limit=True)` settled ihn als erledigten Nullschritt) oder eine
kurze Prozess-Sperre (`AgentProviderCooldown`, dann ohne Claim auf demselben
Index) genau einmal nach Retry-After bzw. `RATE_LIMIT_RETRY_SECONDS` (3 s)
wiederholt, nur bis `RATE_LIMIT_RETRY_MAX_SECONDS` (10 s) und mit mindestens
60 s bis zum harten Stopp; `_pause` bleibt abbrechbar, der Retry umgeht die
selbst gesetzte Sperre (`check_cooldown=False`). `_admit_chat_step` kürzt für
Vergleichsantworten und für Agent-Schritte nach einem Vergleich bei Konkurrenz
die Output-Grenze (`clamp_floor`), statt zu warten. Die Judges indexieren im
Chat bis zu `CHAT_MAX_CONSENSUS_SENTENCES` Sätze; `_run_coverage_windows` teilt
Coverage in parallele Fenster (`COVERAGE_WINDOW`, im Agent `AGENT_COVERAGE_WINDOW`
= 16 Sätze).
**Prüfung beim Schreiben (seit 2026-10-17):** Jede gezeigte Antwort-Delta ruft
`ComparisonTools.answer_progress(value.published)` (`DelegationLoop._step` nach
`_candidate_delta`). `agent_coverage_prefetch.CoveragePrefetch` startet für je 16
feste Sätze (`consensus_engine.settled_sentence_count`: nur Zeilen, auf die
noch eine vollständige Zeile folgt) ein Coverage-Fenster über
`judge_transport` (gemessen, Turn-Abbruch, Google-Routing) mit dem bisher
geschriebenen Text (`prefetch_coverage_window`, Stimmen nach Modellname statt
Label). `judge()` übergibt sie als `coverage_prefetch` an `query_differences`;
`_run_coverage_with_prefetch` startet sofort die nicht laufenden Sätze,
sammelt die frühen Fenster ein, übernimmt nur wortgleiche Sätze an derselben
Nummer (`_adopt_prefetched`, neue Labels) und fragt den Rest erneut. Ein
anderer Prüfbestand (`judge_basis`: Antworten, Frage, gelesene Seiten) verwirft
alles. `_retract` und ein Schnitt in `_show_answer` stoppen laufende Fenster
(`discard_answer_progress`, noch wartende Fenster starten gar nicht mehr),
`judge()`/`skip_review()` schließen den Pool, `ComparisonTools.close()` wartet
am Laufende auf laufende Fenster (sonst Settle-Konflikt in `finish_run`).
Nur Chat-Läufe (`account_budget_only`); neu gerechnet wird nur nach einem
Zeilenumbruch. Das Einsammeln endet mit der Frist der Prüfung
(`_ComparisonWindows.results` beachtet deren Stopp). `JUDGE_PARALLEL` = 12.
Coverage-Meta trägt `prefetched` (übernommene Sätze); `duration_ms` misst die
Zeit nach Antwortende.
**Vorläufige Marken (seit 2026-10-18):** `judge()` gibt `query_differences`
`coverage_progress=partial(ComparisonTools.preview_coverage, comparison_id,
answer_hash)` mit. `_CoverageProgress` sammelt die Voten jedes fertigen
Fensters (übernommene frühe Fenster in Fertig-Reihenfolge,
`_ComparisonWindows.results` per `wait(FIRST_COMPLETED)`, Rest- und Neufrage-Fenster
über `_run_coverage_windows(progress=…)`, ein einzelnes Fenster in
`_run_coverage_judge`) und baut daraus Claims nur für beantwortete Sätze
(`_coverage_claims(only=…)` + `_verify_claims`); ein fehlschlagender Empfänger
kostet die Prüfung nie (`_report_coverage`). `preview_coverage` legt sie als
Event `coverage_preview` (`answer_hash`, `comparison_id`, alle Claims bisher,
`models_compared`, `checked`, `sentences`) in `outgoing`, nur solange die
Review dieses exakten Texts `running` ist; nie gespeichert, kein Score, keine
Differences. Der Live-Puffer hält das neueste als Sticky-Frame. Im Browser
siehe `agent-review.js::preview` (unten).
Im Toolergebnis eines Vergleichs nennen die Antworten ihre Quellen nur per URL
(seit 2026-10-10); `sources` führt jede zitierte Quelle einmal mit `cited_by`,
`supports` (gestützte Antwortsätze) und `excerpt` (Originalauszug), gebaut von
`agent_source_evidence.py` (zusammen höchstens `EXCERPT_BUDGET_CHARS` je
Vergleich; auf Seitenabrufe wartet das Ergebnis höchstens `PAGE_WAIT_SECONDS`,
nie über `answer_time_left` hinaus; ein Fehler kostet nur die Auszüge, ein Stopp
bricht ab; gebundene Läufe kürzen die Auszüge auf den Platz bis `context_chars`; siehe
agent-mode.md, „Quellenauszüge für die Antwort“). `AgentCompletion` behält dafür bis zu `ANSWER_SOURCES_MAX` (10)
Quellen je Aufruf und in `citations` Zitattext und Position, beides nur im
Speicher; gespeichert und gestreamt werden weiter nur URL und Titel. Text vor
dem Eintreffen der ersten Suchergebnisse (Claudes „Ich suche nach …“) streicht
`AgentCompletion` am Stream-Ende samt Offset-Verschiebung
(`citations.presearch_end`/`shift_citation`; agent-mode.md, „Text vor den
Suchergebnissen“). Die Suchzahl liest `measured_usage` über
`reported_searches` aus `usage.server_tool_use_details` (die alte Form
`server_tool_use` gilt weiter). Sucht ein Modell öfter als `max_uses` erlaubt,
bricht nichts ab: Die echte Zahl wird gebucht, gebundene Suchbudgets werden
negativ, und `/health/metrics` zählt `search_overrun:<modell>` (agent-mode.md,
„Websuche“).
Das Orchestrator-Tool `read_source` (seit 2026-10-11 standardmäßig an,
`AGENT_READ_SOURCES=0` schaltet ab; `agent_read_source.SourceReader`, nur
Kontomodus, nicht bei Google-Daten) öffnet vor der Antwort, seit 2026-10-11 auch ohne Vergleich, eine von einer
Vergleichsantwort zitierte URL, eine gespeicherte Quelle früherer Nachrichten
(`AgentRunStore.messages(sources=…)` → `DelegationLoop.chat_sources`) oder eine
URL aus den Nachrichten des Nutzers (`user_urls` über `agent_memory.user_words`; nie
Links nur aus Antworttext, seit 2026-10-12 auch nicht aus einem per „Ask about
this“ zitierten Antwortabsatz),
über einen abgerechneten Helferschritt (`DelegationLoop._step(...,
server_tools=[engines.web_fetch_tool(...)], completion=PageFetch())`, Responses
API, Text aus dem Output-Item `openrouter:web_fetch`; über Chat Completions
käme er nicht an). Der Text geht als Toolergebnis an den Agenten (er zählt
dort wie ein Quellenauszug, `AGENT_READ_SOURCE_PROMPT`), als `read_sources` in
den Review-Snapshot und als eigene
`<page label="Page n">`-Blöcke an den Coverage-Judge
(`query_differences(read_sources=...)`, `claims[].read_sources`, keine Stimme).
Ablehnungen und nicht lesbare Seiten sind Ergebnisse (`refused`/`failed`), keine
Toolfehler, damit sie nicht als `invalid_tool_rounds` den Turn beenden; nach
einem gelesenen Abruf lehnt `compare_models` ab. `ReadOnlyTool.activity` liefert
dem Tool-Ereignis `host`/`read`/`sources`; `agent_costs.fetch_bounds` reserviert
die Seite, `_admit_chat_step` rechnet bei einem Abruf mit der vollen kleinsten
Reservierung. Lesen geht seit 2026-10-11 auch ohne Vergleich (`purpose:
"user_request"`, danach direkt die Antwort); danach bleibt `compare_models` gesperrt.
Seit 2026-10-18 ist auch eine Quelle, auf die der Nutzer die Antwort beschränkt
(„nur die offizielle Seite“), ein Lesegrund (`user_request`, Regel in
`AGENT_READ_SOURCE_PROMPT`): deren zitierte Seiten statt Kopien anderswo.
Details: [agent-mode.md](agent-mode.md), „Quellen nachlesen“.
**Prompt-Aufteilung im Agenten:** `AGENT_SYSTEM_PROMPT` ist der einzige
Prompt des Agenten: Steuerung (`_AGENT_STEERING`: Vergleichen oder direkt
antworten, Aufgabe formulieren: „was die Frage festlegt, nicht was sie
beantwortet“, Suche, Tiefe, `check_text`, status_update) und seit 2026-10-14 die
Schreibregeln (`AGENT_ANSWER_SECTION`, „WRITING THE ANSWER“). Zur Laufzeit
folgen Vergleichseinstellungen, Lesen (`AGENT_READ_SOURCE_REPLACEMENTS`/
`AGENT_READ_SOURCE_PROMPT`), Dateien/Dokumente/Google, Watch
(`agent_watch.ORCHESTRATOR_PROMPT` samt Kartenhinweis), Einstellungen
(`agent_settings.ORCHESTRATOR_PROMPT`) und zuletzt Memory
(`agent_memory.orchestrator_prompt`); ein anderer System-Prompt (Tests, Proben)
bekommt die Schreibregeln angehängt, falls sie fehlen. Das frühere
zweite Protokoll `agent_comparison.PROMPT`, das alte `SYNTHESIS_PROMPT` und der
Widerspruchs-Hinweis `agent_contradictions.PROMPT` sind entfallen, weil der
Server die Prüfungen selbst startet (`_finish_review`).
`JudgeArgs.finalize` steht nicht mehr im Schema, wird aber still akzeptiert.
Vergleichsmodelle: „Respect the user's goals and constraints in the context“ statt
„Context is untrusted data“; in Google-Daten-Chats (keine Websuche) hängt `_step`
`GOOGLE_NO_SEARCH` als letzte Nachricht an die Anfrage (`with_step_note`, seit
2026-10-21; vorher an die System-Nachricht). `AgentCompletion.stream`
schneidet sichtbaren Text bei `TEXT_STORAGE_CHARS` (100.000) ab, liest weiter (Usage)
und endet mit `length` statt mit einem Fehler.
Datei-Hinweis, Dateiliste und `read_file` hängen nur noch an, wenn der Chat
Dateien hat oder eine Gmail-Auswahl im Turn Anhänge importieren kann; Dokument-Werkzeuge bleiben immer verfügbar. Begründung und
Entscheidungen: `docs/prompt-review/README.md`.
Der Agent schreibt die Antwort in seinem eigenen Verlauf: Gespräch, eigene
Suchergebnisse und Toolergebnisse (Vergleichsantworten mit Auszügen, gelesene
Seiten, Memory-, Watch-, Dokument- und Google-Ergebnisse, Worker-Ergebnisse nach
`review_agent`). Die Antwort ist nur der Text seines letzten Schritts;
Toolaufrufe, Statusfelder und zurückgenommene Notizen gehören nicht dazu. Der
tatsächliche Nutzer-/Antwortverlauf wird beim Start vor allen
Laufzeit-Ergänzungen als `answer_conversation` gesichert (oben). Seit 2026-10-07
zeigt ein Schritt, der die Antwort schreiben kann (`answer_candidate`), sein
Reasoning (vorher `reasoning.exclude=true`): minutenlanges stilles Denken wirkte
wie ein hängender Lauf. `_step` verdichtet es mit
`ReasoningProgress(unlimited=True, min_seconds=THINKING_UPDATE_SECONDS)` zu
kurzen wörtlichen Auszügen in EINER Fortschrittszeile `completion:N/thinking`
(kind `progress`, höchstens alle 3 s ersetzt, seit 2026-10-21 nur der neueste
vollständige Auszug; im Browser blendet die Zeile weich über). Seit 2026-10-08 auch über
`REASONING_STORAGE_CHARS` (32.000) hinaus: `reasoning_events` speichert nur bis
dahin und liefert den Rest als `transient`-Ereignis nur an die Fortschritts-
anzeigen (nie in `AgentCompletion.activity`). In die Antwort gelangt es nie;
Reasoning-/Signaturblöcke bleiben Fortsetzungsdaten für denselben Provider
(`_preserve_reasoning`, nur solange Tools aufrufbar sind) und werden nicht
gespeichert.

`judge_answer` prüft genau den fixierten Antworttext, keinen vom Modell frei
behaupteten Prüftext. Er nutzt query_differences samt Coverage, Satzindizes,
Zitatprüfung und begrenzten Repairs. `chat_mode=true` hält beide Judges auf den
Standardmodellen aus `app_config/models.judge_models`, unabhängig von der
Premium-Einstufung des Chatmodells. Primär prüft seit 2026-10-04 immer der
OpenAI-Standard-Judge (Luna), auch für OpenAI-Chats; nach dem begrenzten Retry
folgt der Gemini-Standard-Judge (aktuell Gemini 3.5 Flash-Lite). Ist Gemini bereits primär, folgt der OpenAI-Standard-Judge.
Pro-Judges und dritte Familien werden im Chat nicht als Fallback eingeplant;
die niedrige Judge-Denkstufe und die bisherigen Consensus-Pläne bleiben erhalten.
`_chat_judge_attempts` liefert denselben Plan an Differences und den parallel
laufenden Coverage-Judge. Seit 2026-10-07 ruft der Agent `query_differences(...,
passes=2)`: ein zweiter, unabhängiger Differences-Lauf startet parallel
(`_in_background`, gleicher Kontext/Cancellation/Budget wie der Coverage-Thread),
`merge_difference_passes` hängt nur seine neuen Funde an (gleich = Zitat in
Zitat, gleicher Claim oder gleicher Konsens-Satz, verglichen nur mit Funden des
ersten Laufs; seit der Messung vom 2026-10-07 ohne die frühere Bedingung
„gleiche Modelle“: 79 bewertete Lauf-Paare, Duplikate 14 → 5, kein echter Fund
verloren; die Zusatzfunde des zweiten Laufs sind zu ~64 % echt, gegenüber
~82 % in einem einzelnen Lauf, und senken den Score im Mittel um 5–11 Punkte),
der Score wird danach
in `_apply_coverage` neu berechnet; `judges.differences` trägt `passes` und
`second_pass_added`. Judge-Audit (20 Fragen, 230 blind bewertete Funde): ein
Luna-Lauf fand 60–68 % der echten Streitpunkte, zwei zusammen 78 %, Median
+1,6 s. Fällt ein Lauf aus, trägt der andere. Der zweite Lauf versucht nur den primären Judge (Luna) samt Retry; fällt Luna aus, weicht allein der erste Lauf auf Gemini aus, der teurere Fallback läuft also nie doppelt. Der zweite Lauf hat eine eigene, an die Turn-Cancellation gekoppelte
`ProviderCancellation` (Nutzer-Stopp beendet beide); `judge_transport` reicht
die Cancellation des Threads an `ComparisonTools.call` weiter. Liegt der erste
Lauf vor, bekommt der zweite nur noch eine Nachfrist
(`_second_pass_grace`: halbe Dauer des ersten, 8–30 s) und wird danach
abgebrochen (`judges.differences.second_pass_failed`); endet der erste Lauf mit
einem Fehler, wird der zweite vor dem Warten auf den Thread gestoppt. Bei
endlichem Aufrufbudget mit weniger als vier freien Aufrufen bleibt es bei
einem Lauf. `JUDGE_PARALLEL` ist 7 (zwei Differences-Läufe plus bis zu vier
Coverage-Fenster). Die „Answer check“-Zeile (`agent-delegation.js`, `span`)
misst eine Prüfung vom ersten Start bis zum letzten Ende statt die Dauer
paralleler Läufe zu addieren; `differences_stats` behält `passes` und
`second_pass_added`. Ebenfalls seit 2026-10-07 nennt
`query_differences` dem Judge die Sprache der Konsensantwort ausdrücklich
(`_answer_language`, Funktionswörter für EN/DE/FR/ES/IT/PT/NL, sonst leer und
die allgemeine Regel): Luna schrieb Funde sonst teils spanisch/französisch
unter englischen Antworten. Die echten Agent-Tests simulieren Luna-Ausfälle,
leere Antworten und Cooldowns mit Standard- und Pro-Gemini-Chatmodellen.
llm/task_transport.py injiziert nur den gemessenen Providertransport via
ContextVar; der Coverage-Thread übernimmt den Kontext. Außerhalb dieser Bindung
bleibt der Consensus-Transport unverändert. Jeder Judge-/Retry-/Repair-Aufruf
hat einen eigenen Agent-Schrittbeleg; der Producer wartet auch beim Abbruch
auf die Settlement-Abschlüsse. `_collect_coverage` wartet bei einem gebundenen
unbegrenzten Budget ohne Timeout statt mit `float('inf')`, das Thread-Wartefunktionen
überlaufen lässt; endliche Consensus-Deadlines bleiben begrenzt. Der
Werkzeug-Thread von `judge_answer` (`_execute_stream`) bindet das Turn-Budget
nicht (Thread-lokal): `query_differences` öffnet dort seine eigene
180-s-Analysefrist, die Judge-Calls selbst laufen über `call` mit dem
Turn-Budget. Nach Ablauf dieser Frist wird Coverage beendet statt abgewartet
(siehe `JUDGE_ATTEMPT_SECONDS` unter „Consensus & Differences“).
Ein konfiguriertes Chatmodell ohne Engine-Alias
verwendet seine Familie nur zur Judge-Policy-Auswahl, niemals zur Synthese.

Bis 2026-10-15 reihte das Tool `check_contradictions` (`agent_contradictions.py`)
nach `judge_answer` je Vergleich eine Quellenprüfung der Widersprüche als
Hintergrundjob auf dem Agent-Tokenkonto ein; sie ist mit der ganzen
Quellenprüfung entfernt (siehe „Quellenprüfung entfernt“). Einen Faktenstreit
klärt der Agent vor dem Schreiben mit `read_source`.

`agent-review.js`: `context.mark` baut das markierte DOM nur bei geändertem Text,
Check, Quellen oder `_agentRenderSerial` neu (sonst würde jede Live-Aktualisierung
die Animation neu starten); `revealMarks` setzt eine laufende Animation nach einem
neuen DOM über negative Verzögerungen fort — seit 2026-10-03 auch, wenn der
neue Render selbst kein `reveal` verlangt (`reveal: false`), solange derselbe
`answer_hash` noch im Reveal-Fenster ist; vorher standen dann alle Marken schlagartig da. `query-send.js::setSendButtonRunning`
tauscht das Icon nur bei echtem Zustandswechsel (`data-icon`) und setzt beim Start
eines Laufs einmal `is-launching` (drei Bögen fächern aus, `shell.css`). `agent-chat.js::project` rendert den Review schon während des
Laufs, sobald er `succeeded`/`partial` ist;
davor setzt `setAnswerChecking` `.is-answer-checking` (Schimmer) auf
`#agentAnswerBody`. Seit 2026-10-21 steht dabei an der Stelle der späteren
Evidenzzeile die leise Statuszeile `p.agent-check-status` („Checking the
answer…“, `App.words.checking`, `role="status"`; Ränder und Höhe wie
`.agent-review`: 36 px, 44 px bei `pointer: coarse`, bis 540 px 92 px bzw.
56 px ohne Agreement-Score), die einzige Anzeige bei reduced-motion und
forced-colors; die Evidenzzeile ersetzt sie im selben Render. Der Prüfzustand
beginnt mit dem letzten Wort: `_step` sendet das SSE-Ereignis `answer_check`
(live, nie gespeichert, kein Sticky-Frame), sobald `_answer_check_follows` gilt
(Antwortschritt endet sauber mit genau dem sichtbaren Text, ohne Toolaufruf,
nach Vergleichen, Answer Check an, keine offenen Worker oder Mailbox), noch vor
Settlement, Kontingent-Snapshot und den Review-Checkpoints von
`freeze_for_synthesis`/`capture` (zusammen mehrere Firestore-Schreibvorgänge,
bis dahin startete der Schimmer erst mit dem Review mit `versions`). Der
Handler merkt sich den Text (`context.metadata.answerCheckText`); `project`
zeigt die Prüfung, solange genau dieser Text steht und noch keine Version
vorliegt, danach übernimmt `review.status` `required`/`running`. Ein
zurückgenommener oder geänderter Text löscht die Ankündigung, das Laufende
beendet den Zustand; ein Reload ohne Live-Frames sieht nur den gespeicherten
Review. `renderAnswer` (`renderAnswerBody`) zählt `_agentRenderSerial` hoch, damit ein
neu gerenderter Text seine Marken wieder erhält; `revealMarks` animiert sie nur
beim ersten Auftreten je `answer_hash` (`evidence.reveal`). Veraltete
Antwort-/Grundlagenbindungen werden nicht angezeigt.
Seit 2026-10-18 legt der Handler `coverage_preview` das neueste Event je
Vergleich in `context.metadata.coveragePreview` (ein `activity`-Status mit
`clear_response` leert es). `project` ruft, solange der Lauf läuft und die
Review noch nicht fertig ist, `agentReview.preview(body, checking ? liveReview :
null, previews, evidence)`: Sie markiert nur bei exakt gebundenem Text
(`answer_hash`, Versionstext = `dataset.markdown`, Status `required`/`running`)
die Claims des Vergleichs, den die Evidenzzeile zeigen wird
(`_selectedBasis` oder der erste), mit `differences: []`, losgelöster
Fallback-Box (keine „Key claims“) und ohne Score. **Neutral seit 2026-10-21**
(Max: erst wurde ein Satz gelb, das Gelb verschwand, dann wurde ein ganz
anderer rot): `renderStoredConsensusClaims(…, { provisional: true })` setzt
jeden verankerten Claim als `.cx-claim.is-provisional` ohne Stufenklasse,
Badge, `.cx-spot` und „Key claims“; der Highlights-Filter lässt sie immer
stehen (außer „No highlights“). Aussehen: nur eine leise gepunktete Linie in
Tinte (`--cx-provisional-line`, hell/dunkel, `forced-colors`: `GrayText`),
keine Fläche, kein Platzbedarf. Hover (nur echter Zeiger) zeigt kein Urteil
(„Compared with N model answers“ / „The result appears once the whole answer
is checked“), Klick öffnet nichts, kein Tabstopp. Neue Marken bekommen
`.is-mark-arriving` (die Linie blendet ein), `body._shownMarks` merkt die
Satztexte je `answer_hash`, `.has-provisional-marks` kennzeichnet den Zustand.
Ohne passende Vorschau nimmt `preview` die Marken einmal wieder ab
(`_previewMarks.first` erkennt, ob ihr DOM noch steht). `context.mark`
ersetzt sie im selben Task durch die finalen (nie ein Moment ohne Marken) und
setzt den Zustand zurück; finale Marken auf vorher vorläufigen Sätzen tragen
kurz `.was-provisional` (`handOver`): die Linie bleibt, bis ihre Farbe per
`revealMarks` anstreicht (`--cx-reveal-delay`), und blendet dann aus; ein Satz,
den das Ergebnis nicht färbt, verliert sie sofort weich. Weil die vorläufigen
Marken keine Farbe zeigten, streicht `revealMarks` jede farbige Marke an
(kein `.is-mark-shown` mehr). Bei `prefers-reduced-motion` (und
`forced-colors`) gibt es keine Animation: die Farben stehen sofort da.
`settleHandOver` räumt die Klasse am Ende des Anstreichens bzw. nach
`HAND_OVER_MS` ab.

Die serverseitigen Antwortversionen enthalten Text, SHA-256, Vergleichs-IDs und
Prüfungen; jede Prüfung bindet zusätzlich den Hash der konkreten Antworten
inklusive Quellen/Modellmetadaten. finish_run validiert diese Bindungen erneut.
Mehrere Teilvergleiche werden getrennt gegen dieselbe Synthese geprüft; ihre
Stimmen werden nicht zu einem künstlich größeren Panel addiert. Die erste fertige
Synthese wird serverseitig festgeschrieben: spätere Orchestrator-Deltas werden
weder veröffentlicht noch als Teilantwort gespeichert. `capture` erhält den
exakten Text und seine Hash-/Prüfbindung; neue Vergleiche nach der Synthese werden
abgewiesen. Die Judges schließen auch bei
`finalize=false` ab (das Feld bleibt zur Kompatibilität akzeptiert). Teilweise,
fehlgeschlagene oder übersprungene Prüfungen bleiben ehrlich gekennzeichnet,
lösen aber keine automatische Überarbeitung aus. Nach vollständigem Protokoll-
Abschluss werden auch weitere Toolcalls derselben Modellantwort nicht ausgeführt.
Eine gewünschte Überarbeitung beginnt mit einer neuen Nutzernachricht.
Text neben einem Toolcall bleibt Planung und öffnet keine Syntheseversion
(`_retract`, höchstens als Fortschrittszeile `note`; Ausnahme nur reine
`SIDE_TOOLS`). Weitere Teilvergleiche bleiben möglich, bis der Agent die Antwort
schreibt. Danach führt der Server `judge_answer` über `app_registry` aus (bei
`judges: off` stattdessen `skip_review`). Abrechnung, Bindungen und
bestehende Fallback-Judges bleiben identisch; zusätzliche Erinnerungsrunden sind
nicht nötig. Drei aufeinanderfolgende Tool-Batches ohne einen gültig ausgeführten
Toolcall brechen als Protokollstillstand ab; gültige Arbeit begrenzen nur die
weichen Schutzgrenzen pro Turn (4 Vergleiche, 24 Schritte, 15 min, keine
identischen Wiederholungen; siehe oben bei `AgentPolicy.for_chat`), die nach
Möglichkeit noch eine geprüfte Antwort liefern. Ungeprüfte Antworten werden nie erfolgreich
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
Bricht Firestore bei solcher Konkurrenz schon ein Lesen ab (das SDK wiederholt
nur abgebrochene Commits), beginnt `ChatStore._transaction` die Transaktion bis
zu `TRANSACTION_READ_ATTEMPTS`-mal neu, statt einen Stopp oder Claim scheitern
zu lassen (seit 2026-10-24).
**Wartezeit im Server (seit 2026-10-21).** Weil alle Transaktionen eines Kontos
hintereinander laufen, darf keine davon zwischen einem Modell-Stream und dem
Server stehen, und jede liest ihre Dokumente in einem Rundgang:
- `AgentSessionStore._read_all` liest per `Transaction.get_all` alle Dokumente
  einer Transaktion auf einmal (Claim, Settlement, `publish_agents`,
  `save_review`, `protect_review`; der Löschungs-Tombstone kommt über
  `persistence_guard.deletion_ref` und `ensure_account_write_allowed(snapshot=)`
  mit). Vorher war jeder Lesezugriff ein eigener Rundgang, ein Claim las neun
  Dokumente nacheinander.
- Sitzungs-Updates schreibt das Journal des Laufs
  (`agent_journal.AgentJournal`, ein Thread `agent-journal` je Lauf):
  `DelegationLoop._publish(wait=False)` übergibt und arbeitet weiter, das
  Journal schreibt je Sitzung in Reihenfolge. Seit 2026-10-22 geht alles, was
  fällig ist, sobald der Schreib-Thread frei ist, in **eine** Transaktion
  (`AgentSessionStore.publish_agents`, je Sitzung das vorderste Update,
  höchstens `BATCH_LIMIT` = 32): sechs gleichzeitig startende Antworten sind
  ein Schreibvorgang statt sechs hintereinander. `publish_agents` liefert je
  Update das Event oder die Ablehnung nur dieses Updates (Limit, fehlende
  Assignment, gestoppter Lauf bei nicht beendendem Status), die übrigen werden
  trotzdem gespeichert; Konto, Chat und `run_token` lehnen alle ab.
  `publish_agent` ist der Einzelfall davon. Wartende Aufrufer (neue Sitzung
  vor ihrem Claim, Nachrichten eines delegierten Workers fürs Postfach) kommen
  bei vollem Stapel zuerst, mit allem, was ihre Sitzung vorher übergab. Noch
  ungeschriebene Updates einer Sitzung werden ein Update (`completed` +
  Ergebnis). Live-Zeilen (`progress=True`) ersetzen eine wartende Zeile; die
  Zeilen aller Sitzungen gehen lauf-weit höchstens alle
  `THINKING_UPDATE_SECONDS / 2` hinaus, dann alle zusammen; eine Zeile hinter
  einem Status reist mit ihm. `_journal_write` versucht einen kurzen
  Datenbankausfall einmal mit denselben Event-IDs, `_journal_failed` beendet
  den Lauf nur, wenn er nicht mehr schreiben darf (Stopp, Chat/Konto
  gelöscht). `run()` schließt das Journal nach `comparison.close()` und vor dem
  Settlement-Nachlauf und `finish_run`.
- `_stream_progress` und `_events` nutzen `DelegationLoop.live_lock` statt der
  Lauf-Condition: Kein Stream wartet mehr, während ein anderer Aufruf schreibt.
  Das Journal legt sein Event vor der neuen `session_seq` in `outgoing`.
- `ComparisonTools.checkpoint` nimmt den Schnappschuss unter `self.lock`,
  schreibt aber außerhalb davon (`_save_lock`, nummeriert). Wer als Nächster
  schreibt, schreibt den neuesten Schnappschuss (`_latest`, seit 2026-10-22);
  wessen Schnappschuss darin steckt, kehrt ohne eigenen Schreibvorgang zurück.
  Eintreffende Vergleichsantworten speichern nach dem Lock.
Belegt mit `tests/test_agent_tempo.py` (sechs Modelle, Datenbank mit Latenz je
Rundgang, ein Konto-Lock) und `tests/test_agent_journal.py`. Prod-Befund und
Zahlen: [agent-mode.md](agent-mode.md) „Wartezeit im Server“.
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
Stille im `/agent`-Stream (45 s ohne Byte) ruft `onIdle` von
`App.withRequestDeadline` (`request-deadline.js`) auf: `checkStalledRun` in
`agent-chat.js` fragt mit `recover_only` und derselben Identität nach; ein
gespeicherter Turn beendet den Lauf, `running` wartet weiter, zweimal kein Turn
bricht ab (Firmen-Proxys puffern SSE). Davor greift seit 2026-10-08 der
**gepufferte Agent-Stream**-Fallback (unten). Fehlerhinweise tragen die Aktion
`retry` (`retryFailed` → `send(null, {retry})`): gleiche Frage, `file_ids`,
`chat_id` und Bookmark, neue Request-Identität, aktuelles Modell; die Zeile des
gescheiterten Laufs in der Sidebar wird übernommen.

**Agent-Turns laufen ohne Verbindung weiter (seit 2026-10-08).** Ein Turn
hängt nicht mehr an der HTTP-Verbindung, die ihn gestartet hat. `POST /agent`
bereitet ihn wie bisher vor (Admission, Lease, `create_turn`, `DelegationLoop`)
und startet dann `produce()` über `app/services/agent_background.py`
(`agent_background.start`, eigener Thread mit kopierten ContextVars). Der
Producer schreibt jedes Frame mit einer pro Lauf monotonen Nummer (SSE `id:`,
`agent.py::pack`) in `app/services/agent_live.py` (`agent_live`); die
POST-Antwort (`AgentStreamingResponse`, ein schlichter `StreamingResponse`) ist
nur `agent_live.tail_sse(...)`: 2-KiB-Padding, dann die Frames aus dem Puffer
(alle 100 ms nachgesehen, Keepalive nach 15 s Stille), Ende nach dem letzten
Frame. Ein Verbindungsabbruch beendet nur diesen Tail; der Turn rechnet zu Ende,
rechnet ab und speichert Antwort und Bookmark selbst. Kein Rückstau mehr: ein
langsamer Leser kann einen Lauf nicht mehr abbrechen.

*Stop ist explizit.* `POST /agent/chats/{chat}/requests/{request_id}/stop`
(30/min) bricht einen Turn dieses Prozesses sofort ab (`ProviderCancellation`
wie früher beim Disconnect); kennt der Prozess ihn nicht, setzt es für einen
laufenden gespeicherten Turn `stop_delegation` (wirkt überall über den 3-s-
Watcher) und hinterlegt eine 10-min-Marke, damit ein noch nicht angekommener
POST derselben Identität nie startet (`AgentRunStopped` → 409 `cancelled`,
Turn `failed`, kein Modellaufruf; Registrierung und Marke unter demselben Lock).
Ein Stop vor dem ersten Modellaufruf speichert den Turn mit `cancelled`
(`DelegationLoop.run` setzt `completion.failure` für `release_unclaimed`).
`POST …/turns/{turn}/stop` bricht zusätzlich einen Turn dieses Prozesses sofort
ab. Ein gestoppter Turn sendet jetzt ein Terminal-Frame `error` mit
`code: cancelled` (für andere Tabs und wiederverbindende Browser). Zwei
gleichzeitige POSTs derselben Identität: der zweite bekommt 409
`request_running` (schon vor der Vorbereitung, wenn der Prozess die Identität
laufen hat; sonst `AgentRunDuplicate`, das `start()` vor Shutdown und Stop-Marke
prüft), `agent_live.acquire` teilt einen noch laufenden Puffer statt ihn zu
ersetzen. Kommt SIGTERM während der Vorbereitung, endet der schon angelegte Turn
mit `run_interrupted` (503).

*Neustart/Deploy.* Render schickt SIGTERM und wartet die Shutdown-Frist des
Dienstes (Standard 30 s, max. 300 s über `maxShutdownDelaySeconds`), dann
SIGKILL. `main.py::_drain_agent_runs_on_sigterm` hängt sich in der Lifespan vor
uvicorns Handler und ruft über die Event-Loop `agent_background.begin_shutdown`:
keine neuen Turns (503, `Retry-After: 5`), laufende dürfen
`AGENT_SHUTDOWN_GRACE_SECONDS` (Default 20) zu Ende rechnen, danach bekommt jeder
verbliebene Turn `AgentRunInterrupted` („The server restarted during this
response…“, Code `run_interrupted`) und speichert ab, bevor SIGKILL kommt. Das
Lifespan-Ende wartet per `agent_background.drain` (Grace + 8 s). Die Grace muss
unter der Render-Frist bleiben; wer die Frist erhöht, erhöht beide. Prod (seit
2026-10-08): `maxShutdownDelaySeconds` 300 am Render-Dienst, Env
`AGENT_SHUTDOWN_GRACE_SECONDS=280`; zusammen mit Renders 60 s Überlappung hat
ein laufender Turn beim Deploy gut sechs Minuten.

*Puffer (`agent_live`).* Je Lauf ≤ 10000 Frames/4 MiB (älteste zuerst
verworfen, das neueste nie, damit auch ein übergroßes `final`/`error` ankommt),
≤ 64 Läufe/48 MiB gesamt (beendete zuerst), 10 min TTL nach Ende, 3 h für nie
beendete; Schlüssel uid + chat_id + client_request_id. Gezählt wird echter
Speicher (`FRAME_OVERHEAD_BYTES` = 256 je Frame plus der für Nachzügler
aufgehobene Text). Frames werden als gültiges JSON gespeichert (NaN → `null`,
einzelne Surrogates ersetzt). Liest jemand hinter dem behaltenen Fenster,
bekommt er zuerst die neuesten verworfenen Frames mit bleibendem Zustand
(`STICKY_TYPES`: accepted, started, review, coverage_preview, memory, quota, resources) und dann
`reset` mit dem Antworttext bis dorthin (Deltas angehängt, bei `activity`
`status` + `clear_response` geleert), im Tail als eigene Frames bzw.
`event: reset`. Ein als Ganzes verdrängter Puffer (`evicted`) liefert nichts
mehr und beendet seinen Tail ohne Terminal-Frame; der Browser folgt dann dem
gespeicherten Turn. `acquire()` meldet, ob die Anfrage den Puffer angelegt hat:
nur dann darf sie ihn (und den Turn) bei einem Startfehler beenden;
`AgentRunDuplicate` verwirft einen eigenen, nie benutzten Puffer (`discard`).
`GET /agent/chats/{chat}/live?request_id=…&after=<seq>` (Agent-Zugang,
120/min, `private, no-store`, kein Firestore) liefert `{events:[{seq,type,data}],
last_seq, done, known, more, reset?: {seq, text, frames}}` mit höchstens 500
Frames (Index statt Scan: die Nummern im Fenster sind lückenlos);
`known:false` heißt: dieser Prozess kennt den Lauf nicht (anderer Worker,
Neustart, abgelaufen, fremdes Konto). Nichts wird persistiert; `recover_only`
öffnet keinen Puffer und zählt nicht gegen das Sendelimit
(`api_uid_limiter` „agent:turn“ prüft erst vor einem neuen Turn). Prod läuft mit
einem Prozess; mehrere Worker kennten die Läufe der anderen nicht (der Browser
fiele auf `recover_only` zurück).

*Client.* `agent-chat.js::follow` ist der eine Weg, einem Turn zu folgen
(`send` mit POST-Stream, `resume` ohne). `agent-live.js`
(`App.agentLive.watch`, vor `agent-chat.js` im Bundle) hat zwei Betriebsarten:
Puffernetz (kein Byte 5 s nach dem Senden → Polling alle 1,5 s, Bytes pausieren
es, 4× `known:false` legt es still, ohne den Watch zu beenden) und
`reconnect()`: Stream mit `streamFailureKind`
`request_failed`/`stream_read_failed`/`stream_incomplete` abgebrochen, 45 s
ohne Byte (`withRequestDeadline` `onIdle`, statt der früheren
`checkStalledRun`-Prüfung), Tab nach ≥ 20 s Stille wieder sichtbar bzw.
`online` (der Server schickt spätestens alle 15 s ein Keepalive), oder Reload.
Dann Polling bis zum Turn-Ende: Netzfehler nur mit Backoff (bis 10 s),
`online` und sichtbarer Tab pollen sofort, jeder Poll mit frischem ID-Token und
10-s-Timeout, nie zwei Polls gleichzeitig; Stream-Bytes halten Polls zurück,
solange der Stream lebt (20 s). `known:false` fragt `recover_only`:
gespeicherter Turn beendet, `running` (z. B. alter Server im Deploy) prüft nach
5 s, dann doppelt so lange bis 60 s; erst dreimal nichts über mindestens 20 s
(ein Turn kann noch in Vorbereitung sein) oder 30 min Folgen geben auf, mit
dem ursprünglichen Fehler. `app_stream_resumed` zählt nur einen wirklich
toten Stream (Fehler, 45 s oder 20 s Stille). Alle Frames laufen durch
`deliver(type, data, seq)`; `App.agentLive.sequence()` verwirft schon
angewandte Nummern, `reset` setzt `streamText`. Während Polls scheitern, zeigt
die Aktivität „Reconnecting…“ (`agent-activity.js`, Spec `reconnecting`). Der
Stop-Knopf (`registry.cancel(..., "user")` → `cancelRun` → `stopOnServer`) ruft
den Request-Stop und wiederholt ihn bei Netzfehler, 429 oder 5xx (Backoff bis
30 s, sofort bei `online`, höchstens 10 min); bis zur Antwort steht `stop: true`
im Pending-Eintrag, ein Reload liefert ihn dann nach, statt dem Turn zu folgen.
Antwortet der Server `not_running` für einen angenommenen Turn, holt
`recoverAnswer` das gespeicherte Ergebnis. Logout/Kontowechsel stoppen den
Turn nicht. Nach dem Absenden liegt `{at, body, title, followup, settings,
attachmentMeta, stop?}` in `sessionStorage["agent_pending_runs_<uid>"]` (≤ 4,
20 min), bis der Tab ein bekanntes Ende gesehen hat (Erfolg/gespeicherter
Fehler; ein Transportproblem behält ihn); nach einem Reload legt
`resumePending` (sobald Katalog bereit, Agent-Modus) dafür wieder einen
Run-Context an und folgt ihm ohne neuen Aufruf; ein Follow-up öffnet danach
seinen Bookmark ganz. Analytics:
`app_stream_buffered`, `app_stream_resumed`, `app_run_resumed`
(docs/analytics.md).
assistant_response bleibt kanonisch; consensus ist der alte Lesealias.
Direkte Teilantworten bleiben bei Providerfehlern erhalten. `agent_failure`
enthält den sicheren Fehlercode und Grund auch im gespeicherten Turn; die UI
zeigt ihn live und nach Reload. Provider-Timeouts sind von Kontingent-Stopp und
Nutzerabbruch getrennt, rohe Provider-Fehler werden nicht gespeichert.
Seit 2026-10-15 (Audit A15) haben Ablehnungen, die sich unverändert wiederholen
würden, eigene Codes statt `provider_error` („Trying again … usually works“):
`provider_rejected` (HTTP 400/413/422), `conversation_too_long`
(`agent_runs.ConversationTooLong`), `file_unavailable` und `google_error`
(die eigenen, nutzerlesbaren Texte von `FileUnavailable`/`GoogleError`).
`agent-chat.js::failureNotice` bietet bei diesen drei ersten kein „Retry“ an.
Scheitert beim Speichern des Endes einer Vergleichsantwort oder eines
Seitenlesens (`DelegationLoop._terminal`) Firestore nur kurz
(`_transient_store_error`, wie bei `_settle_step`), folgt ein Versuch nach
`TERMINAL_RETRY_SECONDS`; danach fehlt nur dieser Eintrag. Bis dahin brach jeder
solche Fehler den ganzen Turn als „stopped“ ab (Audit A12). Geschlossener Chat,
Lauf oder Konto brechen weiter ab.
Scheitert ein Lauf erst nach abgeschlossenem Review, behält
`AgentRunStore.finish_run` den Review-Status `succeeded`/`partial`/`off`; nur laufende
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

`agent-preferences.js` (nach `agent-review.js`) speichert Tiefe, Quorum,
Agent freedom (`autonomy`: `guided`/`free`) und Answer check (`judges`:
`on`/`off`, `#agentJudgesSelect`; Details in `docs/agent-mode.md`) als
Kontoeinstellung `agent_preferences` (nur gewählte Felder), gibt den Reiter `agentSettingsSection` über
`App.settingsTabs.setTabAvailable` nur bei `agentChat.canUse()` frei (Aufruf aus
`agentChat.renderShell`) und liefert `App.agentPreferences.get()` für das Feld
`agent_preferences` von POST `/agent` (`AgentPreferences` in `agent_comparison.py`,
Werte in `agent_settings.agent_preferences`).
Agent-Antworten haben seit 2026-10-04 keinen eigenen Copy-Button mehr
(`agent-answer-actions.js` entfernt, User-Vorgabe); kopiert wird per Auswahl
oder im Antwortleser. Folgefragen verwenden direkt den Composer, ohne
zusätzliche Antwortaktion. `agent-review.js::evidenceButton`
gibt Contradictions/Review, Answers und Sources dieselbe dezente Icon-Gestaltung
und lesbare ARIA-Namen samt Anzahl; der Antwortleser-Vertrag bleibt unverändert.
Bis 540 px stehen die Vergleichsaktionen in gleich breiten Spalten mit
Icon/Anzahl über dem Label (`grid-auto-columns`: drei, ohne Review bei
ausgeschalteter Antwortprüfung zwei). Einzelne Quellenaktionen ohne Vergleich bleiben
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
tragen dieselbe Sekundärtinte; in Forced Colors gilt für beide `CanvasText`.
Aufgeklappt ist der Verlauf seit 2026-10-23 eine Zeitleiste ohne Rahmen und
ohne Linie über die Spalte (`.agent-activity-timeline`): je Eintrag ein Punkt
auf einer dünnen Schiene, die jeder Eintrag selbst zeichnet (vom Abstand
darüber bis zu seinem Ende; der erste beginnt, der letzte endet am Punkt).
Schritte stehen in den Worten des Live-Laufs (`historyTitle`: „Searched the
web“, „Read source“, „Checked the answer“; Fehlschläge weiter „Web search ·
Failed“), ihre Quellen als die Pillen der Antwort (`createSourceRef` aus
`sources.js`, Zeile `.agent-activity-sources`, Vorschau beim Hover). Läuft der
Turn ohne aktives Tool, ist `.agent-activity-current` (`role="status"`) der
letzte Eintrag. Die Vergleiche (`agent-review.js` `renderActivity`) sind die
nächsten Einträge (Überschrift nur für Screenreader, der Punkt eines Funds in
Ampelfarbe); am Ende steht leise `.agent-activity-run-details` mit
`label(settings)` (Modell, Reasoning nur wenn nicht Standard). Der Container
`.agent-answer-activity` ist `flow-root`, damit beim Auf- und Zuklappen nichts
darunter springt (`tests/e2e/test_agent_activity_motion_frontend.py`).
`ProgressArgs.status_update` ergänzt die Tools
`compare_models`, `check_text` und `read_source` um maximal 400 Zeichen (bis 2026-10-14 auch `answer`);
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
Bei Abschluss, Fehler oder Stop verschwindet die Live-Anzeige; ein vom Leser
geöffneter Verlauf bleibt offen, solange er im Bild ist, und klappt nur oberhalb
des Viewports zu (siehe „Keine Verschiebung“). Manuelles Öffnen über Pfeil/Enter
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
Begründungen und Modellnamen sowie gebundene Prüfergebnisse und bis zu drei erkannte
Unterschiede. Neu gebaut wird es nur, wenn sich Gezeigtes ändert: Die Signatur
enthält statt der wachsenden Antwort nur, ob eine Prüfung an ihr hängt, und von
Modelltexten nur, ob es sie gibt; vorher ersetzte jeder 100-ms-Takt die Karten,
und Klicks auf ihre Schaltflächen gingen verloren (seit 2026-10-20, Apple-Audit D7).
`safeSources` parst die Links eines Textes einmal und merkt sie sich (begrenzter
Cache nach Text, Apple-Audit D5). Dieselbe Text-/Hash-/Basisbindung
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
dauerhaftes Nachscrollen (seit 2026-10-09 gibt es gar keins mehr, siehe
`App.chatScroll`). Ein noch laufender bewusster Send-/Latest-Sprung darf
einmal fertiglaufen.
Sichtbare Statusbereiche behalten ihre kurzen Übergänge.
Tool-Nennungen bleiben Text; ausschließlich bestätigte running-Toolereignisse
oder der Review-Status bestimmen den aktuellen Arbeitsschritt im Verlauf.
Alte gespeicherte Reasoning-Verläufe bleiben als begrenzte Auszüge lesbar.
`agent_progress.py`/`agent_loop.py` behalten für Legacy-Läufe und Worker drei Zeilen
und acht Updates je Modellschritt; Provider-Zusammenfassungen haben Vorrang.
Seit 2026-10-21 ist jede Zeile eine vollständige Aussage (`_excerpts`, Tests
`test_agent_progress.py`): ein Satz endet nur, wenn nach dem Satzzeichen
wirklich Whitespace angekommen ist, nie in „e.g.“, „U.S.“, „Dr.“, Initialen
oder deutschen Ordinalzahlen („am 3. Oktober“, `_ends_sentence`); rohes Denken
zeigt den letzten passenden Satz der neuesten fertigen Zeile (die offene Zeile
nur, solange keine fertig ist), eine Überschrift („**Comparing options**“,
OpenAI-/Gemini-Summaries; jeder Summary-Teil mit eigener `id` beginnt einen
neuen Block) steht für ihren Abschnitt, Summaries ohne Überschrift sprechen mit
ihrem ersten Satz. Gekürzt wird nichts mehr (vorher 177 Zeichen + „…“): ein Satz
über 160 Zeichen weicht einem kürzeren, sonst bleibt der alte Auszug stehen.
`compactReasoning` (agent-activity.js) wendet dieselben Satzgrenzen auf
gespeicherte Zeilen an (≤ 180 Zeichen, abgeschnittene „…“-Zeilen fallen weg).
Worker verwenden weiterhin `progress_text`/`progress_kind` in ihrer Sitzung.
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
(Fokus auf dem `summary`, also Klick oder Taste) wird per
`reveal()` in Sicht gescrollt — höher als die Liste: Anfang oben.
Ein Modell-Icon über der Antwort (`show()`) öffnet seit 2026-10-14 nur die
Leiste auf der Zeile dieses Modells: geschlossen, per `reveal()` in Sicht, mit
kurzem Ton (`summary.is-pointed`); vorher klappte es Reasoning und Antwort
gleich mit auf.
Seit 2026-10-09 öffnet ein Klick auf eine geschlossene Vergleichsmodell-Zeile
stattdessen den Answer-Reader auf genau dieser Antwort, „Answer check“ dort die
Differences (`openInReader` in `agent-delegation.js`; Kontext über
`comparison_id` der Sitzung und `App.agentReview.contextFor`). Eine offene
Zeile klappt dagegen wie jede andere zu (vor 2026-10-14 öffnete auch ihr
Faltzeichen den Reader, sie ließ sich nicht mehr schließen). Die Agent-Leiste
schließt dabei wie bei jedem Reader-Öffnen. Gibt es noch keinen Reader-Kontext
(Lauf läuft, Worker-Zeile), klappt die Zeile wie bisher auf. `agent-review.js`
behält dafür die Kontexte der letzten 64 Vergleiche (`contextsByKey`) statt nur
die der zuletzt gerenderten Antwort.
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
Metadaten dürfen umbrechen. Während eines Modellaufrufs zeigt die Tokenzahl
(`.is-loading`, ohne Schimmer) zunächst `Tokens pending`, dann tatsächlich
empfangene Antwort-/sichtbare Reasoning-Zeichen (`chars`), bis der Provider
Input+Output-Tokens meldet. Seit 2026-10-04 bewegt sich pro Zeile nichts mehr:
kein Ladebalken, kein Schimmer, der Lauf zeigt sich in „Working · 14s“ und der
zählenden Zahl. Die Segmentleiste im Kopf füllt fertige Modelle in Tinte,
laufende Segmente stehen im Halbton und atmen langsam (`agent-segment-breathe`,
aus bei Reduced Motion/Forced Colors).
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
2026-10-01 als **eine** leise Zeile `evidenceStatus` (`4 of 6 models answered`
bzw. `· Partly checked`), hinter der ein `<details>` die fehlenden
Modelle mit Grund, späte Antworten und kleinere Prüflücken auflistet. Eine
vollständige Prüfung aller Antworten hat seit 2026-10-23 **keine** Zeile (vorher
„4 models answered · Checked“, Max: „verwirrt und bringt nix“); „Checked“ steht
nie mehr in der Zeile, und `evidenceStatus` gibt dann `null`. Nur
entscheidende Lücken (`decisive`: keine Differences-/Coverage-Prüfung, zu wenige
Antworten) stehen sichtbar darunter. Danach folgen die Karten; ältere
Antwortversionen stehen in `.agent-evidence-footer` unter den Karten (ein
leerer Footer bleibt per `:has()` verborgen). „Model agreement is not independent fact checking.“
und „Comparison context“ sind dort entfallen (der Grund steht in den
Aktivitätsdetails). `statusText` (`Comparison checked · N
models without an answer`) bleibt nur für die Aktivitätsdetails.
Key claims (Claims ohne Inline-Marke) stehen vor der Evidenzzeile. Archivierte Agent-Turns blenden den Consensus-Fuß
(`.thread-history-footer`) aus, weil `.agent-review` dieselben Links trägt.
Schlägt ein Lauf erst nach einer vollständigen, geprüften Antwort fehl, zeigt die
Kopfzeile `Thought for …` (dieselbe Regel wie `failureNote`).
Statuslabels: `Partly checked`, `Check could not run`, `Answer not checked`,
`Answer check off` (keine Prüfhinweise: `checkIssues` ist für `off` leer; unter
der Antwort steht für `off` keine Zeile, nur Aktivität und Reader nennen es).
Die Evidenzzeile lässt `Sources` ohne Quelle weg (kein „Sources 0“). Archivierte
Agent-Turns setzen ihre Modell-Logos (`.agent-history-models`) neben
`Thought for …` in die Aktivitätszeile, wie der Live-Turn (agent-delegation.js);
eine eigene Zeile nur ohne Aktivität. Die Logos ruhen einfarbig (Farbe bei Hover).
Ausfallgründe erscheinen nur als kurze Code-Phrase (`failureReason`).
`Answers` zählt vollständige Antworten; die Details behalten auch Fehlermodelle.
Alte Reviews werden aus ihren vorhandenen Judge-Metadaten erklärt.
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
`daily_token_limit`/`AGENT_DAILY_TOKEN_LIMIT` gibt es nicht mehr. Agent ist
seit 2026-10-02 für jedes angemeldete Konto offen (`require_agent_access`);
Pro bleiben Premium-Modelle und hohe Denkstufen.
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
gestartete Calls (`not_started`, `provider_rejection`, `not_dispatched`) bleiben
freie Nullmessungen; `not_dispatched` heißt: der Request kam nie beim Provider an
(Verbindungsaufbau gescheitert oder Abbruch vor dem Senden, siehe
`app/services/llm/provider_dispatch.py`).
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
standardmäßig zwei parallele Unteraufrufe, 120.000 Zeichen Chatverlauf
(`agent_runs.CONTEXT_CHAR_LIMIT`), bis zu 600 kB Review-Snapshot. Kein
LLM-Kompressor. Ein längerer Chat behält seit 2026-10-15 seine neuesten
Nachrichten (`history_start`): die ältesten fallen in Schritten von
`HISTORY_STEP_TURNS` (4) weg, damit der Verlauf ein paar Nachrichten lang am
selben Punkt beginnt und im Prompt-Cache bleibt; der App-Kontext der neuen
Nachricht sagt dem Modell das (`HISTORY_OMITTED_NOTE`). Vorher brach jede
weitere Nachricht ab, gespeichert als `provider_error`, und der Chat war tot
(Audit A9). Passt nur die neue Nachricht nicht ins Modellfenster, kommt
`ConversationTooLong` (422, `conversation_too_long`). Der Admin-Prompteditor zeigt
nur wirksame Worker-Parallelitäts-/Nachrichtengrößen und verweist auf Limits für
das zentrale Tagesbudget; alte Config-Felder bleiben beim Speichern erhalten.
Konten behalten maximal zwei aktive Läufe; AGENT_MAX_CONCURRENT_RUNS begrenzt
Produzenten pro Prozess (Default 16), auch solche, deren Browser längst weg ist
(der Producer hält seinen Slot bis zum Turn-Ende). Consensus behält seine Run-Limits.
Ein einzelner Chat-Turn ist trotzdem nicht unbegrenzt: Vergleichs-, Schritt-,
Zeit- und Wiederholungsgrenzen pro Turn (`AgentPolicy.turn_*`, oben bei
`AgentPolicy.for_chat`) stoppen Schleifen gültiger Aufrufe vor dem Tageskonto.

Agent nutzt den gemeinsamen `engines.web_search_tool`-Builder mit derselben
Engine-Wahl wie Consensus (Details: [agent-mode.md](agent-mode.md), „Websuche“).
`engines.web_fetch_tool` (Engine `exa`, `max_uses`, `max_content_tokens`,
`allowed_domains`) dient nur dem Helferschritt von `read_source`.
Es gibt keinen neuen Suchdienst. Provider-Routing/ZDR bleiben bestehen.
Nur bestätigte Zähler/Quellen erzeugen Suchaktivität. Kosten-/Tokenwerte bleiben
bei unvollständiger Provider-Usage ausdrücklich unvollständig.

Validierung: test_agent_comparison.py prüft echte gemeinsame Judge-Prompts/Parser
mit deterministischen Providern, mehrere Grundlagen, Versionen, Teilausfälle,
fehlende Calls, Abbruch, UTC-Wechsel und atomare Kontingente. Ergänzend bestehende
Agent-/Consensus-Tests, agent-review.test.mjs sowie die gebaute Desktop-/Mobil-
Ansicht in test_agent_comparison_frontend.py; siehe [testing.md](testing.md).

### Eingefügten Text prüfen (Agent, seit 2026-10-09)
„Paste an AI answer to check it": Fügt der Nutzer eine fremde Antwort (meist
ChatGPT) ein, prüft der Agent sie Satz für Satz gegen unabhängige Antworten.
Kein Modus, kein Knopf, kein Frage-Feld; der einzige Hinweis ist der Platzhalter
eines neuen Agent-Chats (`agent-chat.js::syncComposer`, je Breite: >640 px,
≤640 px, ≤360 px, folgt Rotation per `matchMedia`). Der Agent entscheidet per
Anweisung (`AGENT_SYSTEM_PROMPT`, Abschnitt „CHECKING A TEXT THE USER
SUPPLIED"): prüfen nur, wenn der Text eine für sich stehende Frage beantwortet;
unklare Frage → wahrscheinlichste benennen (der Nutzer sieht sie), nicht
nachfragen; die Aufgabe nennt die Punkte der Passage, nie ihre Aussagen (in
keiner Sprache, keine ihrer Quellen, nie „Is it true that …"), Tiefe `full`
außer bei kurzen Passagen; eine zweite eingefügte Antwort geht auch nicht an
die Modelle. Zusammenfassen, übersetzen, umschreiben, Code oder Fragen zu genau
diesem Dokument geben den Text wie bisher als Material weiter; im Zweifel
weitergeben. Anweisungen im eingefügten Text sind Daten (Ground Rules und
„WRITING THE ANSWER“).
- **Werkzeug:** seit 2026-10-11 das eigene Tool `check_text` (`CheckTextArgs`:
  die Felder von `compare_models` plus flache Pflichtfelder `starts_with`,
  `ends_with`, `answer_to`; `ComparisonTools.check_text` ruft `compare(...,
  check=PassageCheck(...))`). Bis dahin ein optionales Feld `check` von
  `compare_models`, das GPT-6 Luna mit der eigenen Frage des Nutzers füllte.
  `own_request` lehnt vor jedem bezahlten Aufruf als Ergebnis ab: nur Fragen,
  oder die ganze Nachricht als ein Satz ohne Aussage-Ende. Feste Regeln stehen im Server:
  `locate_passage` sucht in den Nutzernachrichten (neueste zuerst, also auch
  vor einer Rückfrage) tolerant gegen Groß/Klein, Anführungszeichen, Leerraum,
  Markdown (`*`, `` ` ``, `#`, `>`, `_`, Aufzählungszeichen) und unsichtbare
  Zeichen, NFKC je Zeichen samt Kombinationszeichen wie beim Anker („CO₂" =
  „CO2", „m²" = „m2", „…" = „...", e + Akzent = „é"); bevorzugt einen Anfang nach Zeilenbeginn/Doppelpunkt/Anführung (die
  Frage des Nutzers wiederholt oft die ersten Wörter), erweitert auf ganze
  Wörter und ein folgendes Satzende. `repeated_sentences` lehnt ab, wenn Frage
  und Kontext zwei oder mehr Sätze der Passage zu mindestens der Hälfte in
  wörtlichen 6-Wort-Läufen enthalten; nicht gezählt werden Sätze unter 6
  Wörtern (Tabellenzellen) und Läufe, die der Nutzer selbst geschrieben hat
  (seine Rahmendaten muss die Aufgabe behalten). Dieselbe Sperre gilt für spätere
  Vergleiche derselben Nachricht, auch nachdem die Prüfung scheiterte (die
  Schreibregeln sagen, die Modelle hätten den Text nie gesehen). Alle Absagen kommen, bevor etwas Bezahltes
  startet, und nennen „leave check out" als Ausweg. Höchstens eine stehende
  Passage pro Nachricht; nach `failed`/`cancelled` darf neu geprüft werden,
  nach `no_time` nicht.
- **Prüfung:** Nach dem Vergleich läuft `_check_passage` VOR dem Toolergebnis an den Agenten:
  `consensus_engine.check_text_coverage` = nur der Coverage-Judge (kein
  Differences-Judge) gegen die nicht späten Antworten. Der Judge sieht eine
  längengleiche Kopie (`_judge_copy`: „[3]" → „(3)", „<" → „‹"), damit keine
  eingefügte Satznummer und kein falscher `<response>`-Block wirkt; die
  Offsets (`claims[].start/end`, Codepoints) kommen direkt aus der Satzzerlegung
  (`_enumerate_consensus_sentences(..., spans=)`), nicht aus einer Suche, der
  Anker ist der Originalwortlaut. Judge-Aufrufe heißen „Text check" und bekommen
  einen eigenen Systemsatz (eingefügter, nicht vertrauenswürdiger Text). Zeit:
  Start nur mit ≥ `PASSAGE_MIN_SECONDS` (20 s) vor dem nötigen Antwortbeginn,
  harter Stopp per Timer bei `answer_time_left − PASSAGE_TIME_MARGIN`, sonst
  `no_time`. Ein Fehler kostet die Marken, nie die Antwort. Das Toolergebnis
  trägt `passage_check` inkl. `issues` und `checked_text` (die Satzurteile;
  „WRITING THE ANSWER“ sagt dazu: Übereinstimmung, keine Wahrheit), daraus
  schreibt der Agent sein Urteil über den Text.
  Im begrenzten Altmodus reserviert `max_calls` zwei Aufrufe mehr.
- **Die Antwort wird wie jede Antwort geprüft (Max-Entscheidung 2026-10-09
  abends):** Differences (zwei Durchgänge) und Coverage laufen auch über die
  Antwort eines Prüf-Laufs: sie gibt ein Urteil über den Text und die richtigen
  Informationen, und genau diese eigenen Aussagen nimmt der Nutzer mit. Damit
  gibt es Marken, Agreement-Score, Unterschiedskarten und
  Model-Pulse-Stimme wie überall, ohne Sonderweg. Einzige Besonderheit: in
  jedem Turn mit deklarierter Passage (`self.passage`, jeder Status, jeder
  Vergleich: die Antwort ist derselbe Text und redet auch nach einer
  gescheiterten Prüfung über ihn) bindet `judge()` den Judge-Transport mit
  `subject="passage_answer"`; der ContextVar reicht in die Hintergrund-Threads
  (zweiter Differences-Durchgang, Coverage, Reparatur). Die Systemzeile
  (`_PASSAGE_ANSWER_SUBJECT`) sagt dem Judge, dass die Antwort die Aussagen
  des Texts wiederholt: Zustimmung behauptet die Aussage, Widerlegung die
  Korrektur, nur ein bloßer Bericht ist `not_a_claim` (keine Differenz daran
  verankern); Differenzen zwischen den Antworten weiter vollständig. Ohne diese Zeile las „Dein Text sagt X, das stimmt
  nicht" sich als Behauptung X. Zwischenstand von 7303e034 bis zu dieser
  Änderung (beide 2026-10-09): die Antwort-Judges entfielen, gespeicherte
  Checks tragen `skipped: "passage_checked"` ohne `differences_data`;
  `agent-review.js` erklärt sie weiter („This comparison checked your text …"),
  `agent-activity.js` sagt dort „Checked your text",
  `agent-delegation.js` nennt die Zeile „Text check", solange nur der
  Text-Judge lief oder läuft.
- **Daten:** `agent_review.passage_check` = `{version, status
  (waiting|running|succeeded|partial|failed|cancelled), comparison_id,
  answer_to, text, hash, basis_hash, providers, claims[], models_compared,
  sentences, issues[], judges}`. Bewusst NEBEN `checks`, weil `review_is_bound`
  Checks und Vergleiche eins zu eins paart. Änderungen unter `self.lock`
  (`settle`). Über 600 kB verliert die gespeicherte Kopie zuerst Gegenzitate und
  Judge-Details. `close()`, `agent_runs.finish_run` und `agent-chat.js::cancelRun`
  setzen ein hängendes `waiting/running` auf `failed`/`cancelled`. Die Passage
  wird nicht in `comparisons[]` gespeichert. `agent_memory.MemoryTools` zählt die
  Passage im laufenden Turn nie als eigene Worte (`_user_messages` lässt die
  deklarierte Passage weg; `memory` an `check_text` wird erst nach dem Werkzeug
  angewandt, wenn die Passage schon deklariert ist); für spätere Turns gilt die
  Memory-Anweisung („nichts aus eingefügtem Text"), ein echter Ausschluss wäre
  eine zusätzliche Firestore-Abfrage pro Lauf.
- **Oberfläche (seit 2026-10-09 eine Karte über der Antwort):**
  `static/js/passage-check.js` (`App.passageCheck.apply(answerBody, review,
  {live})`, in bundles.json nach `agent-review.js`) setzt `.passage-check`
  direkt VOR den Antwortkörper (`#agentAnswerBody` bzw.
  `.thread-history-answer-body`, Referenz `body._passageCard`). Die
  Nutzernachricht bleibt unverändert so, wie sie abgeschickt wurde (der Agent
  entscheidet erst im Lauf, ob er prüft; eine nachträglich umgebaute Blase
  sprang, und nur manchmal). Kein Kasten, kein Versalien-Etikett, kein Grau
  als Füllung (Max 2026-10-09: „billig, oldschool HTML"): Kopf ist EIN Satz in
  Lesefarbe, halbfett, Ampelfarbe nur auf seiner Zahl („Models disagree with
  4 of 28 statements in your text" für widersprochen UND geteilt; ohne
  Widerspruch nie bloß „alles gut": „No model contradicts your text; 20 of 28
  statements are confirmed" bzw. „…, but none of its 9 statements is
  confirmed"; „All 28 statements in your text hold up"; mit nicht erreichten
  Sätzen `sentences_unchecked`/`unindexed_sentences` heißt es „checked
  statements"); darunter ein 3-px-Satzstreifen (Sätze in Lesereihenfolge, je
  Lauf eines Urteils ein Segment mit `flex-grow` = Satzzahl, Ampelfarbe,
  `aria-hidden`, passt auch bei 320 Sätzen aufs Handy) und eine Legende mit
  Farbpunkten in denselben Farben (`--pc-holds`/`--pc-unconfirmed`; Zähler als Knöpfe, Klick:
  erster Satz dieses Urteils, sonst klappt der Volltext auf; bei nur einem
  Urteil entfällt sie, der Satz sagt es schon), rechts „Show full text". Dann
  der Text auf einer Schiene wie ein Zitat der Antwort. Zugeklappt stehen
  dort nur widersprochene/geteilte Sätze (höchstens 8) wörtlich, darunter in
  Lesefarbe (nicht grau, seit 2026-10-09 abends) „N of M models disagree –
  Modell: „was es stattdessen sagt"" (erstes Gegenzitat, Markdown entfernt,
  ≤ 180 Zeichen; Klick auf die Zeile öffnet dieselbe Karte wie der Satz).
  Keine Faltzeilen zwischen den Zitaten; ohne Zitat keine leere Schiene; mehr
  als 8 widersprochene Sätze → „N more in the full text" (klappt auf). Der
  Toggle trägt `aria-controls` auf die Schiene. Seit 2026-10-21 startet die
  Karte immer zugeklappt, unter jeder Highlights-Einstellung (Max: erst
  zählen die Unterschiede); nur ein Klick des Nutzers klappt sie auf, ein
  Wechsel der Einstellung malt nur neu (vorher öffnete „All checks“ auf dem
  Volltext und klappte mit, `card._passageChosen` gibt es nicht mehr). Zeigt
  dieselbe Karte den Text eines anderen Turns, klappt sie wieder zu.
  „Show full text" zeigt die ganze Passage
  mit `cx-claim pc-claim`-Marken (hält/geteilt/widersprochen/unbestätigt =
  `is-unanimous`/`is-split`/`is-major`/`is-thin`; widersprochen = mehr Gegen-
  als Fürstimmen), gemalt nach der Highlights-Einstellung
  (`body[data-consensus-highlight-mode]`, Standard seit 2026-10-19
  „concerns"); bestrittene Worte
  (`dissent[].target`) tragen wie in der Antwort allein die Farbe (`.cx-spot`,
  `spotRanges`); der Rest ist
  `is-quiet` und zeigt unter Zeiger/Fokus nur neutrales Grau, nie seine
  Urteilsfarbe. Zitierte Sätze sind immer gemalt. Seit 2026-10-21 zeigt ein
  gemalter Satz mit echter Maus (oder per Tab) dieselbe Hover-Vorschau wie ein
  Satz der Antwort (`App.claimPopover.attachPreview(span, claim, models)` in
  `mark()`, Hover-only-Gruppe ohne eigenen Klick); `is-quiet` zeigt keine.
  Der Klick schließt die Vorschau (Dokument-Capture), solange die Karte offen
  ist, erscheint keine, und die Fokus-Rückgabe beim Schließen bringt sie nicht
  zurück. Klick/Enter auf einen Satz
  öffnet die gemeinsame Karte (`App.claimPopover`, Seite des Texts „In your
  text“), deren Logos über `App.agentReview.contextFor` in die Antwort führen, während des Laufs über einen
  Minimal-Kontext aus `review.comparisons`. Darunter „Checked against N models
  that answered „…" without seeing your text.", eine an beiden Enden
  auslaufende Haarlinie trennt zur Antwort. Eingefügtes Markdown wird Text
  (`displayText`: Fett/Kursiv, Überschriften, Zitatzeichen, Code-Zäune,
  Inline-Code, Links → Linktext, Tabellen mit „·"; ob ein Stück eine Zeile
  beendet, entscheidet der ganze Text, sonst liefen Tabellenzellen, die je ein
  eigener Satz sind, zusammen). Die Antwort selbst trägt Marken und Score wie
  jede Antwort (siehe oben). Die Signatur ist
  kanonisch (Firestore liefert Maps ohne Reihenfolge), ein Laufende zeichnet
  nichts neu, der aufgeklappte Zustand bleibt (zeigt dieselbe Karte den Text
  eines anderen Turns, klappt sie zu); abgehängte Karten fallen bei jedem
  `apply` aus der Beobachterliste. Aufgerufen aus `agent-chat.js`
  (live, gespeichert, und leerend für Consensus/neuen Chat), `run-view.js`
  (leerend) und `consensus-run.js::appendHistoryTurn`. Der Aufklapp-Link der
  Nachricht heißt seit 2026-10-09 „Show more"/„Show less" und steht in der
  Blase (`.thread-ask-bubble`).
- **Länge:** Im Agent-Modus prüft `validateInputText` die Zeichengrenze des
  Servers (`consensus_max_question_chars`, 8.000; Codepoints nach NFKC wie
  `normalize_question`) statt der Wortgrenze; der doppelte Klick-Validator in
  `app-init.js` ist entfallen (jede Absage kam zweimal).
- **Tests:** `tests/test_agent_passage_check.py`, `tests/js/passage-check.test.mjs`,
  `tests/js/claim-hover-preview.test.mjs` (Hover-Vorschau aller Marken),
  `tests/e2e/test_passage_check_frontend.py`.

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
- **Chat öffnen (`firebase.js` `openBookmark`, seit 2026-10-20, Apple-Audit
  D2):** Das Antippen antwortet sofort: Handy-Menü zu
  (`App.chatScroll.closeMenu`), Zeile markiert (`syncActiveBookmark` setzt
  `.bookmark.is-active` + `aria-current` für den Chat auf dem Schirm, nachgeführt
  bei jedem Registry-Ereignis und neuen Zeilen). Ein Chat aus dem Speicher
  (`bookmarkViewCache`, die letzten 10 geöffneten, LRU; jeder Save über
  `upsertBookmarkMeta`, Löschen und `bookmarkUi.invalidate` werfen ihn raus)
  steht sofort da und wird im Hintergrund geprüft; nur eine echte Änderung
  (`bookmarkViewSignature`) rendert ihn neu, ohne die Leseposition zu bewegen.
  Sonst zeigt `showChatOpening` sofort Frage (aus der Listen-Meta) und
  `.answer-skeleton` (`.thread-opening`, `body.chat-opening` blendet den
  vorigen Chat nur aus; ein Fehler gibt ihn unverändert zurück), und
  `loadBookmarkView` lädt Detail (`/bookmarks/{id}`) und Transkript
  (`/bookmarks/{id}/conversation`, jetzt nur per Bookmark-ID) **parallel**; ein
  fehlendes, fehlerhaftes oder fremdes Transkript (`chat_id` ≠ Detail) fällt wie
  bisher auf die gespeicherten Fortsetzungsdaten zurück. Jedes Registry-
  Sichtereignis räumt eine noch stehende Öffnung weg.
- **Chatliste: Zeilen, Menü, Löschen mit Undo (seit 2026-10-20, Apple-Audit
  E2/E5/H11/C7/A11/C12).** Eine gespeicherte Zeile ist `div.bookmark[data-id]`
  mit `p[role=button][tabindex=0]` (Titel = Tastatur-Bedienelement, Enter/Leertaste
  öffnet, der Fokusring liegt um die ganze Zeile) und `.bookmark-menu-button`
  („…“, `aria-haspopup="menu"`). Klicks und Tasten laufen über je **einen
  delegierten Listener** (`firebase.js` für gespeicherte Zeilen, `run-view.js`
  für `.run-entry`). Das Menü (`.bookmark-menu`, auf `<body>`, Material des
  Composer-Menüs) bietet Pin/Unpin (siehe „Chatliste: Gruppen, Pin, Suche“), Rename (Titel wird zum gleich großen Feld; Enter/
  Verlassen speichert über `PATCH /bookmarks/{id}/title`, `title_source:
  "user"`, das wie `generated` spätere Saves und Namensgenerierung übersteht,
  `persistence_guard.KEPT_TITLE_SOURCES`), Share (öffnet den Chat, dann den
  Share-Dialog) und Delete. Share steht nur bei einem Chat mit gespeicherter
  Antwort (`bookmarkShareable`: Listen-Meta `has_consensus` aus der Projektion
  von `GET /bookmarks`, auch für Agent-Chats); ein Direktvergleich ohne
  Consensus bekommt es nicht. Agent-Chats waren am 2026-10-21 kurz
  ausgenommen, bis ihre Antworten teilbar wurden (siehe „Sharing“). **Löschen** blendet die Zeile sofort aus
  (`.is-undo-pending`), verlässt einen offenen Chat sofort und zeigt
  `App.undoNotice` „Chat deleted · Undo“ (5 s, Hover/Fokus pausieren); erst
  danach läuft das unveränderte `deleteBookmark` (Fence, Run-Abbruch, DELETE).
  Ein neuer Lauf (Registry `created`), eine verdeckte Seite und Logout löschen
  sofort (`settleUndoableBookmarkDeletes`), damit Chat-Limit und Seitenende nie
  warten. Die Lauf-Zeile (`ensureRunRow`) wird einmal gebaut und schreibt
  danach nur geänderte Wörter (Puls läuft durch), hat die Höhe einer
  gespeicherten Zeile und wird am Ende **an Ort und Stelle** zur gespeicherten
  Zeile (`settleRunRow`: Status blendet aus, `padding-right` gleitet).
  Neue Zeilen öffnen ihren Platz weich (`bookmarkUi.insertSoftly`). Eine Suche
  ohne Treffer sagt „No chats match …“ (`#bookmarksSearchEmpty`, `app-init.js`
  `filterBookmarks`); die leere Liste eines neuen Kontos bleibt leer.
- **Chatliste: Gruppen, Pin, Suche (seit 2026-10-22).** `static/js/chat-list.js`
  (`App.chatList.sync/groupOf`) beobachtet `#bookmarksContainer` per
  `MutationObserver` und ordnet nach jeder Änderung: angeheftete Chats zuerst
  unter „Pinned“ (Listen-Meta `pinned`, neuester `pinned_at` oben), der Rest
  neueste zuerst unter `h3.chat-list-heading` (Today, Yesterday, Previous 7
  days, Previous 30 days, dann Monat, dann Jahr; Kalendertage, Mitternacht
  plant einen neuen Durchlauf). Die Module, die Zeilen anlegen (`firebase.js`,
  `run-view.js`), wissen nichts von Überschriften; ein Durchlauf ohne Abweichung
  schreibt nichts (Ende des Observer-Echos), bewegt nur Knoten am falschen Platz
  und gibt einer bewegten fokussierten Zeile den Fokus zurück. Jede Zeile behält
  die Zeit, mit der sie in die Liste kam (`data-list-time`): ein Follow-up
  speichert mit neuer Zeit, der Chat bleibt bis zum nächsten Laden stehen; ein
  Lauf ohne gespeicherten Chat ist neu (oben). Eine Gruppe ohne sichtbare Zeile
  (Suche, Undo) blendet ihre Überschrift aus. `loadBookmarks` legt `pinned` vor
  die Seite und ruft `sync()` vor dem Einblenden, damit Überschriften mit ihren
  Zeilen kommen. Das Zeilenmenü beginnt mit Pin/Unpin (`pinBookmark`: sofort
  umsortiert, `PATCH /bookmarks/{id}/pin`, Fehler stellt zurück und sagt es);
  Saves ohne `pinned` lassen den Pin der Meta stehen (`upsertBookmarkMeta`).
  Der Titel nutzt auf dem Desktop die ganze Zeile und läuft nur dort, wo „…“
  erscheint, per Maske darunter aus; abgeschnittene Titel zeigen ihren vollen
  Text als Tooltip. Die Lupe neben „Chats“ steht immer da (vorher nur bei
  Hover), Ctrl+K/⌘K öffnet von überall die Suche (Sidebar und Liste klappen
  auf), und die Suche trifft Titel und Frage (`meta.query`).
- **`App.undoNotice`** — seit 2026-10-20 eine dünne Weiterleitung an
  `App.toast` (`notices.js`; `undo-notice.js`/`.css` sind entfernt):
  `show({text, actionLabel, onAction, onExpire, duration})` →
  `{settle(), cancel()}`; eine neue Zeile mit Aktion erledigt die vorige
  (ihr `onExpire` läuft), `current()`.
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
   Stream dedupliziert. Was das Modell vor den ersten Suchergebnissen schrieb
   (Zitation ohne Spanne, `citations.is_search_result`), fehlt im `final`
   (`presearch_end`, gleiche Regel wie im Agent-Stream).
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
  davon einen Snapshot und eine eigene `ChatSession`. `runRegistry.retitle(
  bookmarkId, title, {source})` ist der eine Weg, einen umbenannten Chat
  umzubenennen (`firebase.js` `applyBookmarkTitle` ruft nur ihn): jeder Lauf
  des Chats, auch ein laufender, bekommt `bookmark.title` (+ `latestMeta`,
  ein Ereignis, damit seine Seitenleisten-Zeile nachzieht), dazu die Basen
  (gewählte, `basis`/`completedBasis` jedes Laufs), aus denen die nächste
  Nachricht ihren Namen nimmt. `window.App.followup`
  (in `consensus-run.js`) hält **nur noch den Kompatibilitäts-/DOM-State der
  sichtbaren Projektion, keine Ausführungsautorität und keine eigene Fläche**.
  `run-view.js` gleicht ihn bei jedem Sichtwechsel mit `historyTurns` und der
  completed Basis des gewählten Contexts ab (Verlauf: nur anhängen, siehe unten). **Seit 2026-08-07 hat der
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
  Der Context übernimmt den vorherigen completed Turn in `historyTurns` schon
  bei `registry.create({historyTurns})` (Agent und Consensus), damit seine
  erste Projektion den Turn bereits im Verlauf zeigt; der Projektor rendert ihn
  in `#threadHistory` und die neue Frage in `#threadAsk`.
  **Verlauf wird nie verkürzt (seit 2026-10-20, Apple-Audit A1/A4):**
  `followup.renderStoredTurns(turns, {adopt})` vergleicht die Turns auf der
  Seite per `turnKey` (Turn-ID, Frage, Status, Review-Status, Textlänge), lässt
  den passenden Anfang stehen, entfernt nur Nachfolgendes, das nicht mehr
  dazugehört, und hängt Fehlendes an; ein anderer Chat ersetzt den Verlauf in
  einem Schritt (`replaceChildren`, außerhalb der Seite gebaut,
  `buildHistoryTurn` → `{node, attached}`). Vorher leerte jeder Lauf/Chatwechsel
  den Verlauf zuerst: die Seite war kurz zu kurz, der Browser kappte scrollY,
  und eine Folgefrage sprang nach oben und fuhr zurück. Im Agent-Modus wandert
  der Live-Turn beim Start der Folgefrage **als DOM-Knoten** in den Verlauf
  (`agent-chat.js` `liveTurn.owns/take`, nur wenn `#agentAnswer[data-turn-key]`
  genau den fortgesetzten Turn zeigt): `#threadAsk` und `#agentAnswer` samt
  Aufgeklapptem, Karten, Marken und Logos ziehen um, ihre Vertrags-IDs werden
  entfernt, und frische Kopien des Seiten-Originals (`pristine`, beim Laden
  geklont) übernehmen die IDs. `agentDelegation.release()` lässt die Logos am
  umgezogenen Turn (Klick öffnet dann dessen Antworten im Leser). Die Knöpfe
  der Live-Fläche (`#agentAnswerErrorActions`, `#agentRecover`) bleiben nicht
  am umgezogenen Turn; ihre Klicks sind am `document` delegiert, damit sie auf
  jeder Kopie wirken (Nachprüfung B2: nach der ersten Folgefrage taten Retry,
  „Choose another model“ und „Check/Recover saved answer“ nichts). Der Satz
  eines Fehlschlags ist `.agent-answer-error` (Klasse, nicht ID) und behält im
  Verlauf sein Aussehen. Agent-Turns
  im Verlauf (`.thread-history-turn.is-agent-turn`, Antwort zusätzlich
  `.agent-answer`, Aktivität `.agent-answer-activity`) haben exakt die Boxen
  des Live-Turns; frisch gebaute ebenso. Consensus-Turns werden weiter frisch
  gebaut (kein Umzug des Live-Consensus), aber nur angehängt.
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

**Quellen in der Synthese (seit 2026-09-11):** Neue Consensus-Antworten enthalten keine
S-Quellenverweise. `llm/consensus_citations.py` entfernt unerwartete S-Zitate
inkrementell vor Streaming-Ausgabe, nachgelagerter Analyse und Speicherung;
literaler Code und Mathematik bleiben erhalten. Synthese-Prompts behalten die
Quelleninformationen der Modellantworten. Bestehende Antworten werden beim
Laden nicht umgeschrieben. `source_catalog.py` vereinheitlicht weiterhin lokale
Modell-IDs, dedupliziert URLs mit Modellprovenienz und erhält unbekannte oder
mehrdeutige Referenzen ohne erfundenen Link; Browser-`turn_sources` nummerieren
nur Dokumente, die ein Modell geliefert hat (Audit S3). Alle Modellquellen bleiben zugänglich.
Chat-/Bookmark-/Share-Normalizer behalten vollständige Quellenlisten; vorhandene
Request- und Dokument-Bytebudgets (750.000 Bytes für Turn/Modellantwort) gelten
weiterhin ausdrücklich, ohne stilles Abschneiden nach einer Quellenanzahl.
Neue Runs setzen `consensus.sourceReferenceMode: none` und am Antwortcontainer
`data-source-references="none"`: Die Darstellung macht aus numerischen
`[1]`-Notationen keine Quellenlinks; Modellantworten und ältere Consensus-Texte
behalten ihre Verweise.

**Quellenprüfung entfernt (2026-10-15, Max' Entscheidung):** Die nachgelagerte
Prüfung großer faktischer Widersprüche gegen die zitierten Modellquellen
(„Check contradictions“, bis 2026-09 als „Check sources“ für zitierte Sätze)
ist samt Hintergrundjobs ausgebaut: `source_verification.py`,
`contradiction_verification.py`, `source_check_jobs.py`,
`source_check_repository.py`, `routers/source_checks.py`
(`/api/source-checks/…`, `/api/share/{id}/source-check`,
`/api/topics/{slug}/source-check`, `/api/v1/consensus/runs/{id}/source-check`),
das Agent-Tool `check_contradictions` (`agent_contradictions.py`), der
Worker `source-check-workers`, die Kontoeinstellung `check_sources`, das
Admin-Modell `source_verification_model`/`_fallback_model`, das SSE-Event
`sources.final` und `static/js/source-verification.js`. Grund: Sie lief erst
nach der fertigen Antwort, änderte sie nie, der Agent sah ihr Ergebnis nicht,
und sie lieferte mangels passender Quellen meist kein Urteil. Einen
Faktenstreit klärt der Agent vor dem Schreiben selbst mit `read_source`.
Differences liefert dafür kein `factual_check`, `consensus_anchor_validated`
oder `positions[].quote_models` mehr; der Satz „Whether an event happened …
are factual questions“ blieb als eigene Regel im Differences-Prompt.
Anfragen alter offener Seiten mit `check_sources` werden angenommen und
ignoriert (`AgentRequest`, `/consensus`). Gespeicherte `source_verification`-
Felder älterer Chats, Bookmarks und Shares liest niemand mehr; die
Firestore-Collections (`source_check_jobs*`, `source_check_cache`,
`source_check_workers`) entfernt `scripts/purge_source_checks.py` einmalig
(Dry-Run, `--apply` löscht). `source_documents.py` (sicherer Abruf,
`FetchLimits`) bleibt für die Quellenauszüge des Agents und Watch-Bilder.

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
- Analyse-Budget pro Phase (Audit C3): Der Browser-SSE-Producer und
  `consensus_pipeline.analyze_provider_answers` laufen in
  `llm/provider_runtime.py::analysis_run_scope` (`@analysis_run`). Der Lauf
  trägt die gemeinsame Cancellation; Synthese (`query/stream_consensus`) und
  Judges (`query/stream_differences`, beide Judges samt Coverage-Thread) sind
  Phasen mit je eigenem threadsicherem `AnalysisBudget` (`@analysis_budgeted`
  mit `max_calls`): je `ANALYSIS_TIMEOUT_SECONDS` (Default 180 s, 10–600) und
  so viele Calls, wie der längste Versuchsplan braucht —
  `SYNTHESIS_MAX_CALLS` = 3 (zweimal die gewählte Engine, ein Fallback),
  `JUDGE_PHASE_MAX_CALLS` = 8 (Pro-Differences-Plan 4 + Coverage 3 + Repair 1;
  ein Test hält beide gegen die Pläne). Eine langsame Synthese kostet die
  Judges also keine Zeit mehr. `AnalysisBudget.snapshot()` einer Phase meldet
  die Summe aller Phasen des Laufs (`analysis_runtime`). Ein schon gebundenes
  Budget (Agent) regiert dagegen jede Phase weiter; ein Engine-Einstieg ohne
  Lauf öffnet sein eigenes Budget (Agent-Judges je Prüfung im Tool-Thread).
  `ANALYSIS_MAX_CALLS` (3–12) gilt für alle übrigen Budgets. Der davor liegende Antwort-Fan-out bleibt
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
- Jeder Judge-Versuch hat seit 2026-10-15 eine eigene Zeitgrenze
  `JUDGE_ATTEMPT_SECONDS` (90 s): Coverage samt Repair, Differences in
  `query_differences.run_pass` (beide Pässe) und in `stream_differences`,
  außerdem der Visual-Judge der Watch-/Topic-Bilder (`pick_watch_visual`; Prod
  2026-10-15: zwei hängende Luna-Versuche à 120 s Lese-Timeout hielten die
  Bildsuche eines Topics vier Minuten auf, bevor die nächste Familie in rund
  2 s antwortete).
  Gemessen: Coverage (Agent-Belege) Median 13 s, p90 21 s; Differences
  (`differences_stats` seit 2026-08, 500+ Läufe) Median 2–6 s, p99 ≤ 21 s,
  Maximum 59 s, Pro-Stufe höchstens 27 s.
  `_attempt_time_limit` gibt dem Versuch eine eigene, mit dem Aufrufer
  verknüpfte Cancellation. Läuft sie ab (`_AttemptTimedOut`), wird der Versuch
  beendet, sein Retry übersprungen und der nächste Eintrag des Plans
  (`_coverage_attempts`/`_differences_attempts`, Chat: Gemini) übernimmt. Der
  zweite Differences-Pass kennt nur den primären Judge und endet dann ohne Ausweichen, nie
  doppelt; ein Nutzer-Stopp beendet beide Judges weiterhin ohne Ausweichen.
  Innerhalb dieser Grenze startet `_hedged_judge_call` seit 2026-10-18 nach
  `JUDGE_HEDGE_SECONDS` (15 s) eine identische zweite Anfrage an dasselbe
  Modell, wenn die erste noch läuft (Coverage-Fenster, Coverage-Repair,
  Differences in `run_pass`; nicht `stream_differences`). Die erste Antwort
  gewinnt, die andere wird über ihre eigene, verknüpfte Cancellation beendet;
  die erste Anfrage bleibt im aufrufenden Thread (sonst unverändertes
  Verhalten), das Duplikat läuft im Thread `<Aufrufer>-judge-hedge`. Ein
  Duplikat startet nur, wenn das Budget danach noch einen Call für den
  Fallback-Judge übrig hat (`_spare_judge_call`). Ein Hänger kostet so rund
  15 s plus eine normale Judge-Dauer statt 90 s bis zum Familienwechsel.
  Seit 2026-10-21 bekommt `_hedged_judge_call(call, fallback=, won=)` nach
  `JUDGE_FALLBACK_SECONDS` (30 s) zusätzlich denselben Check auf der nächsten
  Familie des Plans (`_next_family`: Coverage-Fenster und `run_pass`, Chat:
  Gemini); die erste Antwort gewinnt, `won["fallback"]` lässt Repair und
  `_judge_metadata` den Judge nennen, der wirklich geantwortet hat. Der zweite
  Differences-Pass hat keine andere Familie im Plan, der Fallback läuft also nie
  doppelt; Coverage-Repair hedgt nur dasselbe Modell. Jede weitere Anfrage läuft
  in einer eigenen Kopie des Aufrufer-Kontexts (ein `Context` darf nur in einem
  Thread zugleich laufen).
  Gegen eine durchweg langsame Spur hilft der Hedge nicht (Chat-Review
  2026-10-19: jeder Luna-Call 20–24 s auf OpenAIs Standard-Spur, 8 Duplikate,
  keins gewann). Deshalb fragen die Agent-Judges (`judge_transport`) per
  `JUDGE_SERVICE_TIER_BY_PROVIDER` bei der OpenAI-Familie `service_tier:
  "priority"` an (OpenRouter-Endpunkt `openai/fast`, doppelter Preis, ~2 ct
  pro geprüfter Antwort; fällt ohne Priority-Endpunkt auf die Standard-Spur
  zurück). Andere Familien bleiben auf der Standard-Spur (Anthropics Priority
  ist der teure Fast-Mode); der Consensus-Pfad (`_call_engine_text`) bleibt
  unverändert.
  Der Coverage-Thread hat eine eigene, verknüpfte Cancellation
  (`_coverage_in_background` → `(pool, future, stop)`); läuft die Frist von
  `_collect_coverage` ab, wird er beendet statt abgewartet. Anlass: Agent-
  Judges laufen über den Task-Transport mit dem Turn-Budget statt der
  180-s-Analysefrist; ein Luna-Coverage-Call mit 243 s überlebte die Frist,
  der Agent wartete beim Aufräumen 64 s darauf und verwarf ihn dann — die
  Antwort hatte keine einzige grüne Marke (`coverage_unavailable`).

- Im App-Layout steht `#consensusOutput` oberhalb der Modellantworten: Das
  synthetisierte Ergebnis ist die Primäransicht, die einzelnen Antworten sind
  darunter die prüfbare Grundlage.
- **Inline-Confidence statt Zwei-Spalten (seit 2026-07-24):** `.consensus-box`
  ist einspaltig. Die Antwort (`.consensus-main`, volle Breite) rendert in den
  stabilen Container **`#consensusAnswerBody`** — einziges Render-/Streamziel,
  Zugriff ausschließlich über **`window.App.consensusBodyEl(scope?)`**
  (das alte `.consensus-main p` gibt es nicht mehr). Darunter liegt der
  kompakte Antwort-Footer; Markierungsfilter werden ausschließlich über
  Settings → Display gesteuert (Default: All checks, siehe oben).
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
  bei fortgesetzten Turns dieselbe `context_version_id`. `turn_sources` sind
  nur Nummerierungs-Hinweise: `source_catalog.normalize_source_catalog`
  übernimmt einen Eintrag nur, wenn eine Modellantwort des Laufs (Receipt)
  dieselbe URL geliefert hat, und dann mit deren Titel/Inhalt. Fremde Links
  oder umbenannte Titel aus dem Browser erreichen weder Turn noch Bookmark,
  Consensus-Prompt oder Share (seit 2026-10-15, Audit S3; die Liste des
  Browsers entsteht ohnehin nur aus den `/ask_*`-Quellen desselben Laufs).
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
  `insufficient_answers`, ein zuverlässig erkannter Stream-Abbruch vor der
  fertigen Synthese `cancelled` (danach wird der Turn `completed`, siehe
  „Persistenzreihenfolge“ unter Consensus & Differences).
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
  ersetzen, sondern degradiert nur die Differences-Anzeige. **Persistenz-
  reihenfolge (seit 2026-10-05):** Alle Writes eines erfolgreichen Laufs
  (Differences-Statistik, Share-`pending_result`, `complete_turn`,
  Sidebar-Bookmark) laufen über EINE Funktion `persist_completed_run` im
  Handler — JSON-Antwort, gestreamtes `final` und abgebrochener Stream teilen
  sie. Normal persistiert der Stream nach den Judges und vor `final`. Schließt
  der SSE-Pump die Quelle (Client weg, 30-s-Rückstau, z. B. Handy-Tab im
  Hintergrund während der Judges) **nach** der fertigen Synthese
  (`answer_committed`, gesetzt direkt vor `consensus.final`), persistiert der
  `GeneratorExit`-Zweig den Lauf synchron als `completed`: noch nicht
  abgeschlossene Analyse wie eine gescheiterte (`differences_data: null`,
  bekannter UI-Zustand),
  eine bereits fertige Analyse unverändert. Reload bzw. Resubmit sieht dann den
  Replay statt 409; die Tokenbuchung schließt `metered_events` danach genau
  einmal ab. Nur ein Abbruch **vor** der fertigen Synthese markiert den Turn
  `cancelled`. `ProviderCancelled` im Judge (Client weg) löst keinen
  Server-Alert aus. Während Reasoning-Phasen
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
  **Datenformat für die Gegenüberstellung (seit 2026-10-16):** `claim` ist in
  der App eine kurze neutrale Themenzeile („Frontier token prices in 2026“),
  nicht mehr ein Satz über beide Seiten; Topics (`statement_claims`) behalten
  „the disputed point in one short sentence“ als Aussage. `positions[].stance`
  ist die Behauptung der Seite, direkt formuliert („Frontier token prices rose
  67% year on year“), nie „Model A says …“. `positions[].in_answer`
  (Schema-Pflichtfeld, boolean) markiert die Seite, die die Konsensantwort
  selbst vertritt; `_normalize_differences` speichert es nur als `true` und
  höchstens einmal je Differenz, der Share-Sanitizer reicht es durch.
  **Eine Behauptung = eine Seite (seit 2026-10-21):** `_normalize_differences`
  führt Positionen mit gleicher Behauptung zusammen (`_stance_key`: Groß-/
  Kleinschreibung, Whitespace, Satzzeichen am Ende): Modelle werden vereinigt,
  `in_answer` geht mit, das erste vorhandene Zitat bleibt. Ein Modell steht nur
  in seiner ersten Position; eine Position ohne verbleibendes Modell entfällt.
  Fallen so alle Seiten zu einer zusammen, ist es kein Unterschied mehr und die
  Differenz entfällt (eine vom Judge einseitig gelieferte Differenz bleibt wie
  bisher). Der Prompt verlangt dasselbe. `readableDifference`
  (`consensus-insights.js`) wendet die Regel beim Anzeigen an, ohne die Daten
  zu ändern, damit gespeicherte Chats dieselbe Behauptung nicht zweimal mit
  „vs“ zeigen. Live-Befund: Lunas Satz „In the answer“, darunter derselbe Satz
  für zwei weitere Modelle, dann Grok.
  `_named_models` ersetzt übrig gebliebene Judge-Labels in `claim`/`stance`/
  `verify` („Model F“, „Modell F“, „Models A and C“) durch die echten
  Modellnamen; unbekannte Labels bleiben stehen. Auslöser war ein Live-Befund
  vom 2026-10-16: „Model F beschreibt …, während die Synthese …“ war für
  Nutzer nicht zuzuordnen.
  **Satz-Index (seit 2026-08-07):** Der Judge schreibt Anker nicht mehr ab.
  `_enumerate_consensus_sentences` nummeriert die prüfbaren Sätze der
  Konsensantwort sowie einzelne Datenzellen von Markdown-Tabellen (auch kurze
  Werte; beide Judges berücksichtigen Spaltenüberschrift und Zeilenkontext).
  Tabellenköpfe und Trennzeilen bleiben Kontext; Zellenanker überschreiten
  keine Zellgrenzen. Überschriften, Code und **abgesetzte Formeln**
  — `$$…$$`, `\[…\]` — bleiben außen vor. Listenzähler, das Kästchen eines
  Checklistenpunkts (`- [ ] `, im Render ein Button ohne Text; gespiegelt in
  `consensus-insights.js::inlineMarkdownSource`) und `[S1]`-Tags gehören
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
  Judge-Policy (`_resolve_differences_engine`): die Judge-Familie ist die
  erste verfügbare der Prioritätsliste (OpenAI zuerst) — seit 2026-10-04
  auch für Engines derselben Familie. Der frühere Fremd-Familien-Zwang schob
  OpenAI-Läufe (Agent-Default Luna) auf Gemini Flash-Lite, das teurer und
  deutlich schwächer ist; ein starker Judge wiegt bei der Belegprüfung mehr
  als die Familienfremdheit (User-Entscheidung). Die Stufe folgt der Engine — Standard-Engine → Standard-Judge
  (`DIFFERENCES_JUDGE_MODEL_BY_PROVIDER`), Pro-Engine → Pro-Judge über die
  Engine-Aliasse (`<Familie>-Pro`). Attempt-Plan: primärer Judge, Retry,
  nächste Familie (Pro fail-opent zuletzt auf einen Standard-Judge); ohne
  Key fail-open auf den Standard-Judge der Engine-Familie. Nicht
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
  Ein Positions- oder Dissent-Zitat bleibt nur bei VOLLSTÄNDIGER normalisierter
  Deckung erhalten; toleriert werden ausschließlich Groß-/Kleinschreibung,
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
  der ersten Prioritäts-Familie (OpenAI) in der STANDARD-Stufe — die Aufgabe ist kontrollierte
  Klassifikation, kein Denken. Der Zwang gegen stilles Überspringen steckt in
  drei Schichten: (a) das Structured-Output-Schema führt die Satz-IDs als Enum
  und JEDES Modell-Label als Pflicht-Property von `models`; (b) der Prompt
  enthält die verbindliche ID-Liste; (c) der Server vergleicht die Antwort
  gegen diese Liste (`missing_sentence_ids`) und fordert Fehlende in GENAU
  einem gezielten Repair-Call nach. Was danach offen bleibt, wird neutral als
  `coverage: "thin"` gerendert statt weggelassen. Klassifikationen:
  `claim` (wird markiert) / `not_a_claim` / `too_vague` / `context_only`;
  Stances je Modell: `supports` / `contradicts` / `not_addressed` / `unclear`.
  Jedes Gegenzitat (`counter_quotes[]`) nennt seit 2026-10-19 auch `target`:
  die Worte DIESES Satzes, denen es widerspricht (kürzeste Spanne, meist 1–6
  Wörter, nie aus Antwort oder Nachbarsatz, nie mit „…“ gekürzt). Der Server
  prüft sie in `_verify_claims` mit derselben exakten Regel wie Zitate gegen
  den Satz (`_verified_target`, eine Spanne „A … B“ zählt über ihre beiden
  Enden; ohne Buchstabe oder Ziffer fällt sie weg) und leert den Rest; bei
  der Prüfung eingefügter Texte zeigt sie danach auf den eingefügten Text,
  nicht auf die Judge-Kopie (`_judge_copy` schreibt `<`/`[1]` anders, aber
  längengleich); `parse_coverage_payload` liefert sie als
  `targets`, die Vorab-Fenster tragen sie mit (`_adopt_prefetched`).
  Echttest mit dem Prod-Judge: 92 % der Ziele standen wörtlich im Satz.
  Ergebnis landet als `differences_data.claims` (unveränderte Feldform plus
  `coverage`, `dissent[].target` nur wenn vorhanden; `sanitize_differences_data`
  behält es, max. 200 Zeichen) und der Judge als `differences_data.judges.coverage`
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
  Schwelle filtert sie aus der Opinion-Map.
  alte Bookmarks/Snapshots ohne die Felder degradieren aufs bisherige Rendering.
- Consensus-Fehlerpfad: `query/stream_consensus` versuchen es bei
  wiederholbaren Provider-Fehlern (429, 5xx, Timeout, ...) ein zweites Mal
  (`CONSENSUS_MAX_ATTEMPTS`), danach einmal auf einer Fallback-Familie.
  400/402/403/404 überspringen den zweiten Versuch und gehen direkt zum Fallback
  (`_provider_error_is_retryable`; ein 402 kann heißen, dass nur diese eine
  Anfrage mehr kostet als das Restguthaben, das günstigere Fallback darf es
  also noch versuchen); nur ein 401 (am Statuscode, nie am Fehlertext erkannt)
  beendet die Synthese sofort, weil jeder Versuch denselben OpenRouter-Key
  nutzt (`_provider_error_ends_run`, Audit C10). Läuft die Zeit der Synthese-Phase ab, lautet der Text
  `CONSENSUS_TIME_LIMIT_TEXT` statt „empty response“; das Stream-Final trägt
  `code: "synthesis_time_limit"`, und der Chat-Turn scheitert mit diesem
  `error_code` (`consensus_failure_code`, Audit C3).
  Gescheiterte Finals tragen `error: true`. `chat.py` erkennt Fehlertexte über
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
Eine Wahl, ein Besitzer: `static/js/run-mode.js` (`App.runMode`) haelt die
Kontoeinstellung `run_mode` ∈ {`compare`, `consensus`, `agent`} (lokal
`localStorage.runMode`, siehe „Kontoeinstellungen“). `DEFAULT_MODE`
steht dort als eine Konstante (seit 2026-10-02 `agent`); wer nie waehlte, hat
keinen gespeicherten Wert. Andere Tabs, der Server und das Abmelden melden
Aenderungen ueber `consensio:settings-change`, das `run-mode.js` als
`consensio:run-mode-change` weitergibt. Der einmalige Reset vom 2026-10-12
(„Kontoeinstellungen“) hat jeden Browser auf Agent gesetzt und dabei die
Altschluessel `agentMode`, `autoConsensus` und die fruehere Marke
`runModeDefault` entfernt. E2E-Tests, die `runMode` oder die Modellwahl vor dem
Laden vorbelegen, setzen die Reset-Marke `consensio.settingsReset = "2026-10-12"`
mit, sonst entfernt der Reset ihre Werte.
- `preference()` ist die Wahl fuer neue Nachrichten, `effective()` das, was die
  naechste Nachricht tatsaechlich tut: ein offener Agent-Chat bleibt Agent, ein
  offener Consensus-Chat kann nur zwischen Compare und Consensus wechseln
  (serverseitig getrennte Chat-Familien, `agent-chat.js` meldet sie ueber
  `App.agentChat.modeState()`), und ohne Agent-Zugang laeuft eine Agent-Wahl
  als Consensus. Ein Gast (`modeState().guest`, `App.isGuest()`) bekommt Agent
  wie ein Konto im Standard (Max, Apple-Audit H3; geschickt wird erst nach dem
  Login, `composer-invite.js`). `pipeline()` (= nicht Compare) ersetzt das fruehere
  `isAgentModeEnabled()` und fuellt das persistierte Laufsfeld
  `config.agentMode`/`autoConsensus` (Feldname historisch).
- `availability()` liefert je Modus `enabled`/`reason`; der Wähler zeigt
  gesperrte Modi mit Grund statt sie zu verstecken, Agent nur mit Zugang oder
  für einen Gast. In
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
  Entfernt: `#composerAgentToggle`, `#agentModeMenuSwitch`,
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
und Zitat bleiben darüber sichtbar. Einzeilig ist der Thread-Composer seit
2026-10-13 eine Pille (`--composer-pill-radius: 25px` = Rand + 6 px Padding +
halber 36-px-Knopf, also konzentrisch zu (+) und Senden): Handy eingeklappt
und Desktop ohne `.is-multiline`; aufgeklappt, mehrzeilig, auf dem
Startbildschirm und mit sichtbarer Modusleiste bleibt die 20-px-Box. Der
Radius wechselt mit der Auf-/Zuklapp-Bewegung. (+) steht nie woanders, Senden
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
stehen seit 2026-10-22 in ihren eigenen Farben (auch im Landing-Mockup
`.lp-composer-model`): bei 14 px erkennt man eine Marke an der Farbe, und auf
dem Handy gibt es keinen Hover. Unter den Antworten und im Modell-Picker ruhen
sie weiter einfarbig mit Farbe bei Hover. Unter einem leeren
neuen Chat (Hero) stehen seit 2026-10-15 vier Beispielfragen
(`#composerStarters`, Pillen ohne Rahmen; auf dem Handy eine seitlich
scrollende Zeile): ein Klick füllt nur das Feld (`composer-invite.js`). Seit
2026-10-16 sind es drei pro Seitenaufruf zufällig aus einem kuratierten Pool
(`app/services/starter_questions.py::CURATED_STARTERS`, `pick_curated()` im
`/app`-Kontext `starters`; Labels ≤ 22 Zeichen, damit jede Dreierkombination plus „Check an
AI answer“ in die 768 px breite Desktop-Zeile passt, ~7,2 px je Zeichen) plus „Check an AI answer“; ein Konto
mit ≥ 3 Chats sieht stattdessen drei aus seinen neuesten Chats vorhergesagte
(`composer-starters.js`, `POST /api/my/starter-questions`). Sobald
Text im Feld steht, werden sie per `#questionInput:not(:placeholder-shown)`
unsichtbar, behalten aber ihren Platz, damit der zentrierte Composer nicht
springt. Seit 2026-10-16 blenden sie dabei nacheinander aus (140 ms, je
20 ms versetzt), danach gleitet der Hinweis `.app-footer` per `transform` um
`--starters-room` in ihren Platz (340 ms, `--ease-standard`); geleert läuft es
umgekehrt (erst der Hinweis, dann die Fragen). `--starters-room` = Zeilenhöhe +
Rand, gemessen per ResizeObserver in `composer-invite.js`
(`trackStartersRoom`); reduzierte Bewegung blendet nur und lässt den Hinweis
springen. Rechtliches steht
in der Sidebar-Fußzeile, seit der Todo-Runde 3 in EINER Zeile
(`.sidebar-footer-meta`): links Imprint · Privacy · Terms als leise Wörter
(Impressum direkt erreichbar), rechts `.sidebar-footer-icons` mit zwei gleich
großen Zeichen, Feedback (`#feedbackButton`, Sprechblase; öffnet
`#feedbackModal`, für Gäste mit Login-Hinweis statt Formular, siehe
`feedback-dialog.js`) und GitHub (Build-Commit
im Tooltip); About steht im Public-Footer. Das Kontingent-Glyph über ihr ist
ein Kuchen (Tagesrest) in einem feinen Ring statt eines offenen Bogens, der wie
ein Ladekreisel aussah (`#quotaRingArc` r=3.5, stroke-width 7, gleiche
dashoffset-Logik in `sidebar-quota.js`). Unter dem Feld steht nur der
Hinweissatz. Pro Modus gibt es genau EINEN
Modell-Chip; er nennt nur, wer antwortet („6 models · Daily“ mit Consensus,
„6 models“ in Compare, „6 AIs cross-check“ in Agent: was die
Vergleichsmodelle tun, das Menü trägt Chatmodell und Vergleich), nie den
Modusnamen.

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
Navigation. Die Textbreite des Chats bleibt auf 900px begrenzt. Andocken und
Lösen halten die Zeile fest, die den Leser öffnete (sonst den ersten Textblock
oben im Bild): `modeLayout` misst sie vor dem Klassenwechsel und scrollt im
selben Bild um die Verschiebung zurück (`readingAnchor`, seit 2026-10-20,
Apple-Audit A8).
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
Seit 2026-10-23 starten alle Karten zugeklappt auf ihren Kopf (Max:
„Unterschiede immer zuerst eingeklappt“; vorher oeffnete die gewichtigste beim
Betreten), auch im Live-Panel und auf der Share-Seite. Offen ist nur, was der
Leser oeffnet, oder die eine Karte, auf die ein Marker springt (`index`).
Die offene Karte liegt im Leser auf einer getoenten, gerundeten Flaeche
(`--raise`, 14px Radius, wie eine ausgewaehlte Zeile bei Apple), ihre und die
Haarlinie darueber weichen; alle Karten und die Gruppe tragen dafuer dieselbe
Einrueckung (`--diff-open-inset`), damit Oeffnen keinen Text verschiebt. Beim
Zuklappen blendet die Flaeche mit aus (`disclosure.js` setzt
`data-disclosing="open|close"` waehrend der Bewegung), und das Akkordeon
klappt die zuvor offene Karte mit derselben Bewegung zu statt sofort. Seiten
stehen 24px auseinander (vorher 12px, „zu eng“), innerhalb einer Seite 4px.
`details.is-disclosing { overflow: hidden !important }` (motion.css): die
Differences-Karten setzten `overflow: visible` spezifischer, ihr Inhalt lief
beim Zuklappen ueber die Zeilen darunter (Text ueber Text).
Seit 2026-10-01 ist die Liste ein Akkordeon: der `toggle`-Listener im Inspector
schliesst beim Oeffnen einer Karte die zuvor offene (auch bei Marker-Spruengen
und `refreshContext`). Typografie im Inspector: 14px Inhalt, 12px Meta, 13px
Zitate, durchgehend regulaeres Gewicht.
Positionen stehen immer untereinander (Gegenüberstellung in
`components-consensus-insights.css`); eine eigene Zwei-Spalten-Regel der
erweiterten Desktopansicht gibt es nicht mehr.
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
damit Composer und Memory wieder fokussierbar sind. Das Menü kommt mit der
Maus auf `mouseup`, mit Shift auf `keyup`, und seit 2026-10-20 (Apple-Audit
F7) nach einer Berührung über `selectionchange`: ein Finger wählt ohne
`mouseup`. Solange die Griffe wandern, wartet es (unsichtbar), steht die
Auswahl 350 ms still, erscheint es unter dem Griff (28 px unter der Auswahl,
nie dort, wo das Kopieren-Menü des Systems sitzt; ohne Platz darunter 56 px
darüber); verschwindet die Auswahl, geht das Menü mit (außer der Finger ist
auf dem Menü). Auf Touch haben die Aktionen 44-px-Flächen.
`tests/e2e/test_touch_selection.py` wählt ohne Maus-Ereignis.
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
Consensus sind fuer alle Stufen frei; Agent erscheint mit Agent-Zugang und
fuer Gaeste (seit 2026-10-21, sie melden sich beim Senden an).

**Default fuer neue Nutzer**: `run-mode.js` nimmt `DEFAULT_MODE` (seit
2026-10-02 `agent`, ohne Agent-Zugang laeuft es als Consensus), solange keine
Wahl gespeichert ist. Der
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
    nichts, ebenso ein Request, der nachweislich nie beim Provider ankam
    (`provider_dispatch.never_reached_provider`: DNS-/Verbindungs-/Connect-
    Timeout-Fehler von requests/urllib3 und httpx sowie Abbruch/Budgetende,
    die `_guard_provider_io` vor dem ersten Lauf des Sende-Tasks markiert).
    Fehler beim Lesen der Antwort (ProtocolError, ChunkedEncodingError,
    Read-Timeout, TLS) bleiben gestartet. Sonst bucht ein DNS-Ausfall jeden
    Versuch der Retry-Pläne mit 50 %. Ohne gebundenen Meter (Watch, Topics, Agent-Client) sind alle Hooks
    No-ops. MOCK_LLM bucht kleine synthetische Messwerte. Nicht gemessen
    wird spätere Arbeit nach der Buchung einer Operation.
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
    Topics und die Legacy-Publisher-Watches (`model_tier=free`) behalten ihre
    eigenen globalen Budgets.
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
- Der Login ist seit 2026-10-20 ein nativer `<dialog class="modal">` über
  `App.modalDialog` (Überschriftsreferenz, benannter Close-Button, Fokus-
  Einstieg, Tab-Schleife, Escape/Backdrop-Abbruch nur ohne Getipptes,
  Fokus-Rückgabe an den Auslöser, Ein- und Ausblenden wie jedes Fenster).
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
  sonst Google). Der Hintergrund schließt nur bei einem Klick, dessen Druck
  dort begann (Markieren aus einem Feld heraus schloss ihn sonst), und nur,
  solange nichts eingetippt ist; X und Escape schließen immer.
  Demo-Ende („register“) und gesperrte Anhänge („login“) öffnen
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
- **Gäste tippen (seit 2026-10-15).** `window.App.isGuestComposer()` (app-init.js,
  gleich `App.isGuest()` aus app-bootstrap.js: keine Firebase-Sitzung, Login
  erreichbar, keine noch wiederhergestellte Sitzung) zählt zu
  `userCanTypeQuestions()`; nur `data-auth-unavailable`
  sperrt das Feld noch („Sign in to start…“). Gäste bekommen den Platzhalter
  eines neuen Chats (`App.askPlaceholder()`, app-bootstrap.js, auch für Agent),
  `body.is-guest` (ab dem ersten Paint) blendet den Consensus-Chip aus, lässt
  „Try the demo“ neben Agents Chip stehen (agent-chat.css, components-misc.css)
  und zeigt die Begrüßung auch auf dem Handy. **Seit 2026-10-21 (Max,
  Apple-Audit H3)** sieht ein Gast mit Standardwahl ab dem ersten Bild Agents
  Composer eines neuen Chats wie ein Konto: Chip mit `data-agent-default-label`
  und `+N`, „What do you want to be sure about?“ (ein Satz für jeden Modus), Reasoning „Auto“; im (+)-Menü Agent
  gewählt, Consensus und Compare daneben. Geladen wird nichts, was ein Konto
  braucht (keine `/agent/models`), und es steht kein Hinweis unter dem Feld.
  Jede Wahl darin ist eine Tür zum Login mit Satz (`App.askToLogIn`): Chip,
  Reasoning und Vergleichsmodelle über `model-picker.js::openModelPicker` (ein
  Gast im Composer öffnet kein Menü: „Log in to choose your models.“ / „Log in
  to choose the reasoning.“, `trigger` gibt den Fokus zurück), Anhang über
  `attachments.js` („Log in to add files.“), Gmail & Calendar und Drive über
  `agent-google.js`/`agent-drive.js` (nur wo jedes Konto sie hat, siehe
  Google). Eine eigene Wahl des Gasts (Consensus, Compare) gilt wie für jedes
  Konto. Ohne erreichbaren Login ist niemand Gast, dann kein Agent
  (`consensio:auth-unavailable` rendert die Shell neu). Senden ist aktiv, sobald Text im Feld steht, und
  öffnet über `composer-invite.js` den Registrierungsdialog
  (`openAuthModal(mode, trigger, source, {lead})`: die Begründungszeile gilt
  für beide Tabs bis zum Schließen). Nach dem Login lädt die Seite neu, der
  Entwurf kommt zurück ins Feld (auch im Gast-Zweig von `onIdTokenChanged`)
  und geht einmal von selbst raus, im Agent wie gesehen oder im Modus, den der
  Gast im (+)-Menü wählte (`mode` im Sendewunsch, siehe `composer-invite.js`).
  Ohne Konto läuft weiterhin nichts, was Modellkosten erzeugt (Agent bleibt
  `require_agent_access`).
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
  explizite Auswahl (`compare_models[<Familie>].model`, lokal `pref_select_*`) gespeichert hat. Explizite Picker-Werte
  haben Vorrang. Normale Watch-Runs lesen die aktuelle Stufe des Owners
  bei jedem Lauf neu und wählen danach `WATCH_MODELS_BY_TIER` (ein Upgrade wirkt
  deshalb auch auf bereits bestehende Watches nach Ablauf des Tier-Cache).
  **Plus fährt dabei die Free-Watch-Modelle**: mehr Watch-Slots
  (`watch_plus_active_limit`) und optional das tägliche Intervall
  (`watch_plus_daily_interval_allowed`), aber unveränderte Kosten pro Lauf.
  Die Legacy-Publisher-Watches (vom 2026-10-04 entfernten Scheduled Publisher
  angelegt, seit 2026-10-04 alle im Admin pausiert) tragen dagegen intern
  `model_tier=free`; der Scheduler behandelt sie unabhängig vom Owner-Tier
  dauerhaft wie einen Free-Watch. Neue Watches setzen das Feld nie
  (`create_watch` kennt kein `model_tier` mehr).
  Ein Resume zählt nicht gegen das aktive persönliche Watch-Limit der
  Admin-UID; das globale tägliche Watch-Run-Budget gilt weiter. Einen eigenen
  Publisher-Kapazitätszähler gibt es nicht mehr, und ihr Zeitplan ist wie bei
  jeder Watch über `update_watch` änderbar.

### Kontoeinstellungen (seit 2026-10-12)
Einstellungen, die einem Konto auf jedes Gerät folgen, liegen am Konto statt nur
im Browser. **Server**: `app/services/user_settings.py` (Schema `UserSettings`,
alle Felder optional = nur Gewähltes, `FirestoreUserSettingsRepository`) unter
`users/{uid}/settings/app` mit `values`, `revision`, `field_revisions` (Revision
der letzten Änderung je Einstellung) und `updated_at`.
`GET /api/my/settings` → `{settings, revision, field_revisions}` (`revision` 0 =
nie gespeichert; ein beschädigter Wert gilt als 1). `PATCH /api/my/settings` mit
`{settings: {name: wert | null}}` (1 bis 11 Namen) ändert nur die genannten
Einstellungen (`null` = zurück zum Default; `compare_models` ist eine Einheit und
wird als Ganzes ersetzt; `agent_preferences` wird seit 2026-10-17 feldweise
zusammengeführt, `FIELDWISE_SETTINGS`: eine offene Seite einer älteren Version
kennt ein neueres Feld wie `judges` nicht und darf es mit ihrer nächsten
Änderung nicht löschen; einzeln entfernt wird nie ein Feld, `null` setzt die
ganze Einstellung zurück. Der Browser lässt ein unbekanntes Feld aus dem Konto
ebenso einzeln weg, `user-settings.js`) und prüft **Einstellung für Einstellung**
(`validate_changes`): Unbekannte Namen und Werte außerhalb der Regeln kommen in
`rejected` zurück, die übrigen werden trotzdem gespeichert (eine Version mehr
oder weniger im Browser verliert so nicht die ganze Änderung). 422 nur für eine
kaputte Anfrage (leeres/zu großes `settings`, weitere Felder), 403 während einer
Kontolöschung, 429 über 60/min pro IP und pro Konto. Der Body ist auf 256 KB
begrenzt (`PATH_MAX_REQUEST_BODY_BYTES`), Antworten unter `/api/my/` sind
`private, no-store`. `users/{uid}` selbst bleibt für den Browser gesperrt
(Tier/Rolle). Formregeln statt Katalogprüfung: ein Modell, das den Katalog
verlässt, macht den Datensatz nicht unlesbar; gespeicherte Altwerte, die nicht
mehr validieren, fallen je Einstellung weg.

Die Einstellungen: `run_mode`, `agent_model` (`{model_id, reasoning_effort}`),
`agent_preferences` (`depth`/`quorum`/`autonomy`/`judges`, nur gewählte),
`compare_models` (`{Familienlabel: {enabled, model}}`),
`consensus_model`, `consensus_preset`, `system_prompt` (höchstens 12.000 Zeichen
/ 32.000 Bytes; ein Lauf akzeptiert 64 mehr für die Datumszeile, die
`query-send.js` voranstellt, `chat.py`), `agreement_display`,
`consensus_highlights`, `claim_counts`, `letter_animations` (Display → Letter
animations; fehlt = an, `false` = aus; `app-ui.js` bindet
`#letterAnimationsSwitch`, `stream-reveal.js` und `letter-clouds.js` lesen sie).
**Bewusst im Browser** bleiben Theme,
Sidebar-Breite/-Zustand, `agentShellExpected` (vor dem ersten Paint nötig,
gerätebezogen), der Fragen-Entwurf (würde bei jedem Tastendruck schreiben), der
eigene OpenRouter-Key (fremdes Geheimnis), das Analytics-Opt-out, gesehene
Hinweise und alles im sessionStorage.

**Browser**: `static/js/user-settings.js` (`App.userSettings`, Head-Bundle) ist
der einzige Besitzer: `get(name)`, `set(name, wert | null, {derived, source})`,
`accepts(name, wert)`, `onChange(names, handler)` über
`consensio:settings-change` (`detail.source`: `local`, `agent` (die
Einstellungskarte des Agenten, `set(…, {source: "agent"})`: gespeichert wie
`local`, aber die Module wenden sie an wie einen Kontowert), `server`, `tab`,
`signout`; `previous`; nach einer Rückkehr aus dem Back/Forward-Cache gleicht
`pageshow` nach). Die lokale Kopie liegt unter den bisherigen
localStorage-Schlüsseln (`runMode`, `checkSources`, `pref_*`, `systemPrompt`,
`consensio.*`); `consensio.agentModel.v1` ersetzt das frühere
`agent_settings_<uid>`. Alte Speicherformate werden beim Lesen migriert, nur
hier. Das Modul wirft beim Laden nichts (jeder Lesefehler wird zu „nicht
gesetzt“), denn alle späteren Module brauchen `App.userSettings`.

**Einmaliger Reset (2026-10-12):** Fehlt die Marke
`consensio.settingsReset = "2026-10-12"`, entfernt `user-settings.js` beim Laden
einmal Modus (`runMode`, `agentMode`, `autoConsensus`) und Modellwahl
(`pref_check_*`, `pref_select_*`, `pref_consensus_preset`) sowie einen
System-Prompt, den die App früher selbst als Standard schrieb oder der zu lang
ist, und setzt die Marke. Die frühere Marke `runModeDefault` wird dabei auf
`agent-2026-10-02` gesetzt, damit ein noch offener Tab der Vorversion eine neue
Consensus-Wahl nicht auf Agent zurückdreht. Jeder Browser startet so einmal mit
Agent und dem App-Preset Daily; Compare-Wahlen und Modell-IDs aus der Zeit davor
werden nicht hochgeladen (ein noch offener Tab der Vorversion kann bis zum
Neuladen Modellwahlen schreiben; alte IDs scheitern an den Options-Prüfungen und
richten keinen Fehler an). System-Prompt, Display, Agent-Einstellungen/-Modell
und Check sources bleiben. Das App-Preset steht in
`cfg.APP_DEFAULT_CONSENSUS_PRESET` (`fast` = Daily, an die Seite als
`default_consensus_preset`); API und der Rückfall eines Agent-Vergleichs ohne
Auswahl nehmen `cfg.DEFAULT_CONSENSUS_PRESET` (seit 2026-10-15 ebenfalls Daily).
Die Demo zeigt Daily über `App.previewConsensusPreset` nur an (bis zum Neuladen oder zur
nächsten eigenen Wahl), sie speichert es nicht.

**Abgleich**: `firebase.js` ruft nach einer verifizierten Anmeldung
`start({uid, getToken})` neben `/user_status` auf (erst nachdem
`/confirm-registration` zurück ist und die Auth-Generation noch stimmt), `stop()`
beim Abmelden, im Zweig für unbestätigte Adressen, beim Kontowechsel ohne
Abmelden und nach einer Kontolöschung. Regeln beim Laden (`adopt`):
- Was diese Seite vor der Antwort änderte (`touched`), gilt.
- Eine Änderung aus einer früheren Seite (`pending` in
  `consensio.settingsSync.v1` mit `owner` und `base` = neueste bekannte
  Revision) gilt nur, wenn das Konto diese Einstellung seit `base` nicht
  geändert hat (`field_revisions`) — sonst ist der Wert des Kontos neuer (auch
  wenn die eigene, unbestätigte Anfrage schon angekommen war).
- Ein Konto ohne Einstellungen (`revision` 0) bekommt die Werte dieses
  Browsers — außer sie gehören laut Sync-Datensatz einem anderen Konto (dann
  Defaults).
- Der erste Abgleich eines Browsers überhaupt (Marke
  `consensio.settingsSeeded` fehlt, kein eigener Sync-Datensatz) füllt
  Einstellungen, die das Konto noch nicht hat, mit den Werten des Browsers;
  danach gilt der Server ganz. Das alte `agent_settings_<uid>` wird übernommen,
  wenn das Konto kein `agent_model` hat.
- Sonst gilt der Wert des Kontos; fehlt er, der Default.
- Eine Antwort, die älter ist als `base` (ein anderer Tab hat inzwischen
  gespeichert), wird einmal neu angefragt; eine Antwort ohne gültige Form gilt
  als Fehler.
Änderungen gehen gesammelt (400 ms) per PATCH, eine Anfrage zur Zeit je Konto;
nicht-`keepalive`-Anfragen brechen nach 15 s ab. `set(…, {derived: true})`
(eine Korrektur der App, etwa ein Agent-Modell, das die Liste verlassen hat)
bleibt vor der Antwort des Kontos lokal und kann dessen Wert nie überstimmen.
Eine Änderung ohne Sitzung (offline, abgelaufenes Token) wird für den `owner`
des Browsers vorgemerkt. Nach der Antwort (`settle`) verlässt ein gesendeter
Wert die Liste; ein Wert, der sich während der Anfrage änderte, kommt (wieder)
hinein, auch wenn ein anderer Tab ihn schon gesendet hatte und von dieser
älteren Anfrage überholt wurde. Vorübergehende Fehler (401/408/429/5xx/Netz,
Zeitüberschreitung) werden mit Backoff wiederholt; eine Ablehnung (übrige 4xx)
verwirft die Änderung mit Konsolenwarnung. `pagehide`/`visibilitychange` senden
mit `keepalive`; der Logout sendet parallel zum Session-Cleanup und wartet
höchstens 3 s (`flush({timeoutMs})`), danach `stop()`: die Werte des Kontos
verlassen den Browser (auch noch nicht zugestellte Änderungen), die eines Gasts
(nie synchronisiert) bleiben.
Module wenden Werte aus `server`/`tab`/`signout` selbst an (Modus, Modellwahl
über `applyAccountModelPreferences` samt Überschriften und
Anhang-Verträglichkeit, Agent-Modell — ein Tab, dessen Modellliste die Wahl
nicht kennt, lädt die Liste vor jeder Korrektur neu —, Agent-Einstellungen,
Check sources, Display, offener System-Prompt-Editor ohne eigenen Entwurf).

Tests: `tests/test_user_settings.py` (Schema, Teil-Annahme, Repository,
`field_revisions`, Route, Konto-Limit, Kontolöschung, Gleichlauf der Regeln mit
dem Browser), `tests/js/user-settings.test.mjs` (Speicher, Reset, Ereignisse,
alle Abgleichsregeln oben), `tests/js/model-preferences.test.mjs` (Demo-Vorschau,
was eine Modelländerung speichert, Werte vom Konto), die Journey
`test_settings_follow_the_account_to_another_device` (echter Server +
Emulator). Die übrigen Browser-Tests stellen `/api/my/settings` pro Seite im
Speicher bereit, mit den Regeln der echten Route (`_route_account_settings` in
`test_phase4_frontend.py`); der Firebase-Stub der Standard-Fixture startet
keinen Abgleich.

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
  Daily-Preset (`cfg.DEFAULT_CONSENSUS_PRESET`) — mit und ohne Reasoning dieselben. Kosten, Limits, Modelle
  oder Modellanzahl sind keine Request-Felder.
- API-v1-Runs verwenden bewusst immer die sechs Familien des Daily-Presets,
  einschließlich DeepSeek; für API-Kunden gibt es keinen Provider-Opt-out. Der
  frühere DeepSeek-Ausschluss in Antwort-Fan-out, Consensus-Engine/Fallback und
  Differences-Judges ist entfernt — er war nirgends sichtbar und hat nach einem
  Wechsel des Watch-Modellprofils auf DeepSeek unbemerkt nur noch zwei statt
  drei Antworten produziert. Den Publisher-Header `X-Consensus-Publisher` und
  `request.publisher_mode` gibt es seit 2026-10-04 nicht mehr.
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
  Providerstart bleiben konsumiert. Watches, Topics und die
  Legacy-Publisher-Watches behalten ihre eigenen globalen Budgets.
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
  ersten Maintenance-Lauf nachmigriert. Ein vollständiger Scan hinterlässt den
  Erledigt-Marker `app_config/api_consensus_runs_retention_backfill`
  (`completed_at`, `updated`); jeder spätere Prozessstart liest nur diesen
  Marker statt der ganzen Collection (Audit C12). `DELETE /api/v1/consensus/runs/{run_id}`
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
- Der Scheduled Publisher (`scripts/publish_consensus.py`, GitHub Actions)
  ist seit 2026-10-04 entfernt (Begründung in §4 „SEO-Puls“). Bestehende Shares
  behalten `publication_source=scheduled_publisher` nur noch als Daten; neue
  Shares bekommen das Feld nie. Die zugehörigen Weekly-Watches (`model_tier=free`)
  sind seit 2026-10-04 im API-Tab pausiert und bleiben nur lesbar, fortsetzbar
  und löschbar. Der globale Kapazitätszähler (`watch_runtime/publisher_capacity`,
  `publisher_active_limit`, Fehlercode `publisher_capacity`) ist entfernt; ein
  noch vorhandenes Zähler-Dokument in Prod ist verwaist und wird nie gelesen.

### Sharing
- Vorschaukarten (`app/services/og_image.py`, seit 2026-10-18 in einer
  Sprache): heller Grund, darüber leise das Datum („Answered Oct 12, 2026“
  bzw. bei Topics „Checked …“), die Frage in Inter 520 so groß, wie sie ganz
  passt (84 → 42 px, erst danach „…“), unten links Bildmarke + Wortmarke,
  rechts Agreement und Fakten. Die Markenkarte (`render_brand_card`) steht
  zentriert: Wortmarke, der Hero-Satz der Landing in zwei Tönen („Six models
  answer.“ / „See where they disagree.“), darunter die sechs Anbieter-Marken
  als graue Silhouetten. **Sicherer Bereich:** WhatsApp zeigt die Karte im
  Eingabefeld auf etwa 1,6:1 beschnitten (rund 90 px weniger je Seite; die
  alte Markenkarte verlor dort das „T“ ihres Titels). Deshalb 144 px Rand,
  und `tests/test_og_image.py`/`tests/test_og_cards.py` verlangen für jede
  Karte und die gespeicherte PNG mindestens 130 px leeren Rand links und
  rechts. Farbe trägt nur die
  Score-Ziffer (Ampel wie in der App: ab 65 grün, ab 40 amber, darunter rot);
  passt die Faktenzeile nicht neben die Wortmarke, fallen Fakten von hinten
  weg, der Score bleibt. Keine Linien, keine Versalien, keine Sparkline mehr.
  `og_image.card_png` bindet seinen Cache an alle gezeichneten Inhalte
  (Karten-ID, Frage, Score, Fakten, Datumszeile). Die öffentliche Share-Route
  verwendet den neuesten gültigen öffentlichen Stand; private/widerrufene
  Shares erhalten kein Bild, ihre Seiten zeigen die Markenkarte. Reale
  PNG-Regionen, Ampelfarben und semantische Zeichenaufrufe werden gemeinsam
  geprüft (`tests/test_og_image.py`), damit ein gültiges, aber leeres PNG nicht
  genügt.
- `/consensus` legt ein `pending_results`-Dokument an → `result_id`.
- Die Consensus-API publiziert dagegen direkt aus ihrem 30-Tage-Run-Snapshot;
  `source_api_run_id` bleibt serverintern und wird nie Teil der Public-Payload.
- Consensus-Bookmarks speichern diese ID mit, solange sie gültig ist. Bei
  Follow-ups wird der Live-Verweis bewusst nicht übernommen, weil dessen
  Pending-Snapshot nur die aktuelle Frage kennt. Beim
  Teilen/Watchen eines älteren, geöffneten Bookmarks nutzt
  `POST /bookmark/consensus/share-result` einen noch gültigen Pending-Verweis
  oder baut einen neuen Pending-Snapshot aus dem **completed Chat-Turn**, auf
  den das Bookmark zeigt (`chat_id`/`turn_id`): Frage, Antwort,
  Differences-Text, Quellen (nur von Modellen gelieferte, siehe
  `turn_sources` unter „Consensus & Differences“) und Modell-Labels kommen nur von dort, nie aus
  `query`/`sources`/`model_labels` des Bookmarks, die auch der Modell-Save
  `POST /bookmark` schreibt (seit 2026-10-15, Audit S3: vorher ließ sich so
  eine echte Antwort unter erfundener Frage mit fremden Quell-Links öffentlich
  teilen). Vom Bookmark kommen nur serverseitig geschriebene Felder:
  `differences_data` (trägt ein Resolve-Ergebnis, das der Turn nicht kennt),
  `consensus_model`, `vote_subject_id`; gebunden über den Abgleich, dass der
  Consensus des Bookmarks der des Turns ist. Ohne passenden completed Turn
  (Legacy-Bookmarks ohne Chat-Bindung, ~325 aus der Zeit vor August 2026,
  sobald ihr Pending-Verweis nach 24 h abgelaufen ist) antwortet der Endpunkt
  409. Jede Absage legt `requestBookmarkShareResult` mit dem Satz des Servers
  (`App.userError`) in `window.currentBookmarkShareResultError` ab, die Absage
  selbst (mit Status) in `currentBookmarkShareResultContext.error`. Der
  Watch-Dialog zeigt den Satz als Fehlerzeile, der Knopf bleibt für einen neuen
  Versuch; der Share-Dialog zeigt ihn als `#shareDialogError` und bietet „Try
  again“ nur, wenn ein neuer Versuch helfen kann (seit 2026-10-21, vorher ein
  toter Knopf „Saved consensus unavailable“). Share/Watch warten
  auf diese Rehydration und können dadurch auch außerhalb der Ursprungssession
  verwendet werden. Ein Versions-Gate verhindert, dass eine verspätete Antwort
  auf ein inzwischen anderes angezeigtes Ergebnis zeigt.
- **Agent-Antworten (seit 2026-10-21).** Bis dahin lehnte der Endpunkt
  Agent-Chats ab (400 „Sharing Agent Beta answers is not available yet.“),
  obwohl Agent seit Oktober der Standard ist. `POST /agent/chats/{chat}/turns/
  {turn}/share-result` (Share-Pille unter der Antwort) und ein Agent-Eintrag
  über `POST /bookmark/consensus/share-result` (Chat-Menü; die Antwort des
  Eintrags muss die seines Turns sein) bauen beide über
  `bookmarks.prepare_agent_share_result` →
  `share_snapshots.build_agent_pending_result` den Snapshot nur aus dem
  completed Agent-Turn: Frage, Agent-Antwort (`assistant_response`), Quellen
  des Turns, Antwortmodell (`consensus_model` = Modell-Slug,
  `answer_model_label` aus `agent_settings.label`) und `answer_mode: "agent"`.
  Hat der Agent verglichen, kommen die Modelle des Vergleichs dazu, mit dem die
  App die Antwort markiert (der erste, dessen Prüfung dieses Textes Befunde
  hat, sonst der erste; späte Antworten nicht), und deren Prüfung nur, wenn sie
  an genau diesen Text und diese Antworten gebunden ist (`answer_hash`/
  `basis_hash`) und nicht „off“ war. Die Pending-ID ist je Turn stabil
  (`agent_pending_result_id`, `save_pending_result(result_id=…)` lässt einen
  gültigen Snapshot stehen): erneutes Teilen derselben Antwort liefert denselben
  Link, auch nach Reload oder aus dem Chat-Menü; `vote_subject_id` ist
  `agent:{turn}` wie beim Agent-Pick. Nicht teilbar (409 mit Satz für den
  Dialog): nicht fertige Turns und Chats mit Google-Daten (Turn-
  `agent_settings.google_data`/`google_selection` oder Chat-`google_data`, das
  Gmail-Werkzeuge mitten in der Antwort setzen). `lastShareResultId` bleibt für
  Agent leer (Votes und Consensus-Watch lesen es). Die Share-Seite
  (`share.html`, `is_agent`) heißt dann „Shared answer“/„Answer“/„Models
  compared“/„About this answer“, zitiert „Answer to … Answer model: …“, und
  lässt weg, was eine direkte Antwort nicht hat (keine Modellzeile, kein
  Scoreboard, kein Differences-Umschalter, keine Judge-Zeile); die OG-Karte
  nennt dann keine Modelle statt „Several AI models“. Für alle Shares gilt
  seitdem: „0 contradictions“ wird nicht mehr gezählt.
  Seit 2026-10-22 zitiert eine geteilte Agent-Antwort wie der Agent in der
  App: `render_public_markdown(…, source_pills=True)` (nur Agent, nicht
  Watch-Seiten) lässt bei Links auf Quellen der Antwort die Worte stehen und
  setzt die Quellenpille `a.src-ref` (Favicon + Domain, `source-pill.css`)
  dahinter, wie `sources.js` `linkifyAgentSources`. „Models compared“ ist
  ein zugeklapptes `details.wp-disclosure` mit der grauen Logoreihe. Die
  Differences-Ansicht jeder Share-Seite zeigt die Karten der App
  (`check_page.difference_cards`: kritisch zuerst, kleinere gebündelt,
  Seiten untereinander mit „vs“, Antwortseite vorn, „Show quote“ per
  `check-page.js`; CSS unter `#differencesView` in `public-pages.css`).
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
  Checklistenpunkte (`- [ ] …`) zeichnet `_mark_task_items` als nicht
  anklickbares `span.md-task-box[data-checked]` im `li.md-task-item`
  (Spiegelstrich-Liste `.md-task-list`); Mails/Telegram/Klartext setzen dafür
  ☐/☑ (`notification_markdown._task_box`).
  Public-Snapshots enthalten JSON-LD, Canonical-Dedup über `question_hash` und
  „verwandte Fragen"; **Indexierung (`index, follow`) nur wenn der Admin `indexed`
  setzt** — nie automatisch; sonst `noindex`. Private Watch-Snapshots werden am
  Endpoint serverseitig auf die Eigentümer-Session geprüft und nie indexiert,
  gecacht, reportet oder als Related/Sitemap-Ziel ausgegeben. Ohne Session
  antwortet die Seite mit 403 und „Sign in to view“ → `/app?next=/s/…`:
  `firebase.js` öffnet ohne Login den Login-Dialog und springt nach
  `/confirm-registration`, das das `session`-Cookie setzt, auf die Seite zurück;
  ein schon angemeldeter Browser läuft direkt durch. Nur `/s/<pfad>` gilt als
  Ziel. Mails an den Eigentümer verlinken private Seiten gleich so
  (`mailer.owner_page_path`, Watch-Mails und Morning Brief); mit fremder Session
  gibt es keinen Sign-in-Knopf. Public-Caching via
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
- `topics.list_runs` liest lange Historien über `observed_at DESC` mit
  `max_items + 1` als Limit und gibt die letzten Runs weiter chronologisch
  nach Datum/Version/Dokument-ID aus. Bei kurzen Historien beweist eine
  ungefilterte `count()`-Abfrage im selben Read-only-Transaktionssnapshot,
  ob auch Legacy-Dokumente ohne Datum enthalten sind. Nur bei Abweichung,
  ungültigen Datumswerten oder Timestamp-Gleichstand an der Seitengrenze
  bleibt der vollständige Kompatibilitätsread erhalten. Kein neuer Topic-Index
  oder Backfill nötig; der normale kurze Verlauf kostet N Dokumente plus
  die Count-Aggregation statt zweier Vollabfragen.
- Gerenderte Topic-Seiten und der Hub liegen seit 2026-10-20 (Apple-Audit I12)
  `TOPIC_PAGE_CACHE_SECONDS` = 120 s im Prozess (`routers/topics._topic_page_cache`,
  Schlüssel Slug + `?version`, höchstens 200 Seiten, nur 200er); jede Admin-Änderung
  (Topic anlegen/ändern, Run) leert ihn (`invalidate_topic_pages`), ein geplanter
  Run erscheint spätestens nach 120 s. `tests/conftest.py` leert ihn vor und nach
  jedem Test.
- `/topics/{slug}` liest für Verlauf und aktuelle Ansicht die neuesten 100 Runs
  (`TOPIC_PAGE_RUNS`). Ein expliziter `?version=<run_id>` außerhalb dieses
  Fensters wird direkt per `topics.get_run` unter dem bereits aufgelösten Topic
  geladen (Review R33) und in den Verlauf einsortiert; fremde oder unbekannte
  IDs bleiben 404. Zähler und Datum („Checked 100 times since …“, auch in der
  Meta-Description) stammen immer aus demselben gelesenen Fenster und
  behaupten deshalb keine Vollständigkeit über das Fenster hinaus.
- Topics sind bewusst **keine Shares und keine Nutzer-Watches**. `topics/{id}`
  hält redaktionelle Metadaten plus die ausführbare `run_config` mit konkretem
  `provider_models`-Mapping, `update_interval`, Quellenpräferenzen, SEO, Status
  `active|paused|archived`, `next_run_at` und kurze Lease-/Fehlerfelder. Das
  denormalisierte `models`-Array enthält nur öffentliche Labels; ausführbare
  Modell-IDs stehen ausschließlich in `run_config`.
- `topic_runner.py` hängt über den eigenen Adapter `topic_pipeline.py` direkt an
  der neutralen Provider-/Consensus-/Differences-Pipeline und importiert keine
  Watch-Services. Die pro Topic gespeicherte Modellauswahl bleibt maßgeblich,
  läuft aber so, wie sie heute laufen kann: `cfg.runnable_provider_models`
  (`runnable_model_id` je Familie) hebt eine migrierte ID auf ihre aktuelle Form
  und ersetzt ein inzwischen entferntes Modell durch das Standardmodell seiner
  Familie (Watch-Modell der Stufe → Free-Default → Basis-Modell, Free nie
  Premium). `run_config`, `models` und frühere Runs bleiben unverändert; nur der
  neue Run trägt die tatsächlich gelaufenen Modelle. Watches speichern keinen
  Modellplan, sie lesen bei jedem Lauf `WATCH_MODELS_BY_TIER`. Jeder Lauf
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
- **Seitenaufbau seit 2026-10-15: wie die Watch-Seite.** `/topics/{slug}`
  rendert SSR aus `templates/partials/check_page.html` (geteilt mit
  `watch_share.html`): Kicker nur mit der Kategorie (führt zum Hub),
  redaktioneller Titel als H1, das Topic-Bild rechts; dann **eine kompakte
  Zustandszeile** (`check_page.state_view`/`drift_view`, dieselbe Regel wie bei
  Watches, aber `compact=True`: eine Zeile ohne Fläche, „Changed on …“ als
  Link auf den Verlaufseintrag mit Satz und Belegen, dazu „checked weekly“ bzw.
  „paused“; Zähler und „Latest check: …“ stehen als Notiz über dem Verlauf);
  bis zu vier **Direktlinks** (`source_links.key_links`, auf dem Handy eine
  wischbare Reihe); die Leitfrage als H2 über der **offenen Antwort** mit
  Quellen (direkte Quellen nach Rolle zuerst, ab 6
  gefaltet) und Quellennamen im Text als Links (`site_mentions`); Follow;
  **Verlauf** nur mit Bewegungen, ruhige Checks gefaltet, Agreement-Kurve nur
  Desktop und über die volle Spalte (`build_history_view(width=PAGE_CHART_WIDTH)`,
  860, auch auf Watch-Seiten); der Modellvergleich zugeklappt. Die Punkte baut
  `routers/topics._history_points` aus den Runs mit der Topic-eigenen Regel
  (`drift_signal.topic_point`: Judge-Grad und Ursache, nie der Score).
  Entfernt wurden Befund-Satz (`topic_finding.py`), Claim Ledger
  (`claim_ledger.py`: Aussagenliste Split/Settled/New/Dropped, Check-Streifen,
  Quellen-Chronik, Rückkehrer-Band), Positionskarte/Direction Shift,
  Seiten-Balken, Score-Seitenleiste und das As-of-Fenster `list_runs_until`.
  Damit entfällt auch der Claim-Identity-Judge (`query_claim_identity`) pro
  Lauf, den nur der Ledger las. `opinion_map` wird weiter gespeichert
  (Opinion-Changes), aber nicht mehr gezeigt.
- **Antworttext ohne Chat-Rahmen** (`public_markdown.strip_chat_framing`):
  Eine Einleitungszeile, die die Antwort nur ankündigt („Here's the current
  picture …:“), eine „Short answer“-Überschrift direkt danach und ein
  Schlussangebot („If you want, I can also …“) fallen beim Rendern weg; nur
  ganze Absätze am Anfang/Ende, die Antwort selbst bleibt wörtlich. Die
  gespeicherten Runs bleiben unverändert.
- **Snippet = Antwortanfang.** Meta-/OG-Description und JSON-LD `abstract`
  sind `public_markdown.lead_sentences` (erste Sätze ohne Überschriften, an
  einem Satzende gekürzt) plus „Checked by N AI models, M times since …“; das
  handgesetzte `seo.description` greift nur ohne verwertbaren Antwortanfang.
  `create_run` schreibt denselben Anfang der geltenden Antwort als
  `accepted_lead` ans Topic, damit der Hub ihn ohne Run-Reads zeigt.
- **Weiterleitungen.** `topic_pipeline.execute_topic` löst Google-Grounding-
  Weiterleitungen vor Judge und Speicherung über
  `source_redirects.resolve_sources` auf (wie Watches). Alte Runs tragen sie
  noch: die Seite blendet `is_indirect`-Quellen aus Liste, Direktlinks und
  Text aus und lässt ihre `[S#]`-Marker fallen (`_sources_view`).
- **Topic-Bild** (`app/services/topic_images.py`, seit 2026-10-15): dieselbe
  Suche wie bei Watches (`watch_images.search`: Produktfoto → Logos der
  offiziellen Seiten → Artikelbild; nie KI-Bild/Stockfoto). Nach jedem Check im
  Hintergrund (`schedule_after_run`, nur ohne fertiges Bild), die offiziellen
  Seiten wählt einmal pro Topic der Visual-Judge (`watch_scheduler.pick_visual`,
  das Symbol wird ignoriert). Bytes in `topic_images/{topic_id}`, Stand im Feld
  `image` des Topics (`status`, `token`, Maße, Quelle, Versuche, `sites`);
  ein fertiges Bild wird nicht ersetzt, Fehlversuche sind wie bei Watches
  gedeckelt. Ausgeliefert über `/api/topics/{id}/image/{token}`, nie in
  og:image/JSON-LD. Ohne gutes Bild zeigt die Seite (und der Hub) das
  **Symbol** des Topics (`topic.symbol`, vom selben Judge-Call gewählt, Liste
  `watch_symbols.SYMBOLS`, Zeichnungen serverseitig in
  `watch_symbols.SYMBOL_PATHS` = `SYMBOL_ICONS` in watch-dashboard.js, ein Test
  hält beide gleich; seit 2026-10-15 auch `sigma` für Mathematik).
  `image.status = dismissed` beendet die Suche, wenn das gefundene Bild nicht
  taugt (Mathe-Topic: nur eine reißerische Thumbnail-Grafik). Ein **redaktionell
  gewähltes Bild** setzt `scripts/set_topic_image.py` (Trockenlauf Standard,
  `--crop`, `--apply` = Prod-Write; `topic_images.set_editorial_image`,
  `picked_by: editor`): ein echtes Bild aus einer der Quellen, nie KI-Bild
  oder Stockfoto; es ersetzt Suche, Symbol und `dismissed`. Seit 2026-10-15:
  Mathe = IMO-Goldmedaille aus dem Nature-Artikel, AGI = Prognose-Grafik der
  AI-Impacts-Umfrage (LessWrong-Spiegel).
- **Abbildungen aus der Antwort** (`app/services/topic_figures.py`, seit
  2026-10-15): Nach jedem Check füllt ein Judge-Call
  (`consensus_engine.query_answer_figures`, Differences-Judge-Kette,
  Structured Output) aus der bereinigten Antwort höchstens zwei von drei festen
  Vorlagen: `timeline` (datierte Ereignisse), `status` (bestätigt / behauptet /
  nicht bestätigt), `numbers` (vergleichbare Zahlen einer Einheit). Die Regeln
  liegen im Code, nicht im Prompt (`clean_figures`): jedes Datum, jede Zahl und
  jeder Status-Name muss wörtlich in der Antwort stehen, sonst fällt der
  Eintrag; unter zwei Einträgen fällt die Abbildung; je Vorlage nur eine
  (die vollere); Status-Namen ohne `%`/Währung; eine Zahlen-Abbildung, deren Werte nur Jahre
  oder Jahresspannen sind, wird als Zeitleiste gezeichnet (`years_as_timeline`,
  auch für schon gespeicherte); Notizen in Ich-Form, doppelte
  oder den Namen wiederholende Notizen fallen weg; „disputed“ wird gestrichelt
  in Bernstein gezeichnet. Gespeichert als `figures` am Run (ältere Versionen
  behalten ihre eigene), gezeichnet als HTML/CSS (`figure_html`, `.af-*` in
  `public-pages.css`, alle Texte escaped; eigene Fläche mit Kopfzeile
  „Timeline“/„Overview“/„In numbers“ samt Symbol, damit sie nicht als Fließtext
  gelesen wird) unter der Überschrift, zu der sie
  gehört (`place`/`fill`; liegt die im letzten Drittel, rückt sie nach dem
  ersten Absatz nach oben). Ein Fehlschlag kostet nur die Abbildung, nie den
  Check; in Unit-/E2E-/Mock-Läufen wird kein Modell gefragt. Probe 2026-10-15
  auf den drei Live-Antworten: 6–39 s, 17 von 19 Einträgen bestanden.
  Nachtrag für bestehende Runs: `scripts/backfill_topic_visuals.py`
  (`--figures` übernimmt schon erzeugte Abbildungen, `--apply` = Prod-Write).
- **Hub `/topics`**: eine flache Zeile pro Topic mit Titel, dem ersten ganzen
  Satz von `accepted_lead` (`lead_sentences(limit=150, min_sentence=30)`,
  höchstens drei Zeilen; sonst Leitfrage), einer leisen Meta-Zeile
  „Kategorie · Changed …/Checked …“ und dem Bild rechts. Kein Score, keine
  Snapshot-Zahl, kein Filter, keine Versalien-Kicker.
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

### SEO-Puls (Search Console, seit 2026-10-04)
- **Warum.** Ersetzt den Scheduled Publisher und den wöchentlichen
  LLM-SEO-Portfolio-Review samt Collection/Recommendation-Judge. Search-Console-
  Daten vom 2026-10-04: 16 automatisch publizierte Seiten brachten in ~11 Wochen
  415 Impressions und 2 Klicks; die Review-Texte las niemand; der Anstieg Ende
  September kam fast ganz von der markenartigen Query „consens“ auf der
  Startseite, nicht von der Publisher-Pause. Entfernt sind Skript und Workflows,
  `publisher_config.py`, `seo_data.py`, `seo_repository.py`, `seo_dossier.py`,
  `seo_recommendation.py`, `seo_weekly_review.py`, alle alten
  `/api/admin/seo/*`-, `/api/admin/publisher-config`- und Publisher-v1-Endpunkte
  sowie der Startup-Einmal-Task `publisher-watch-lineage-backfill`.
- **Ablauf.** `app/services/seo_pulse.py` (`SeoPulseService`,
  `default_service`, `seo_pulse_scheduler_loop`). Lifespan-Task
  `seo-pulse-scheduler` (nur Produktion über `_scheduler_task`) tickt alle
  15 Minuten; fällig ist der Lauf montags 09:00 Europe/Berlin. Der erste Tick
  nach einem Deploy setzt nur `next_run_at` und feuert nie sofort. Ein
  transaktionaler 15-Minuten-Lease (`lease_until`/`lease_run_id`, `_acquire`)
  verhindert prozessübergreifende Doppelläufe. Der geplante Lauf prüft
  `enabled`/`next_run_at` in derselben Lease-Transaktion noch einmal
  (`_acquire(..., due_only=True)`, Audit C14): ein zweiter Prozess, der vor dem
  Ende des ersten „fällig“ gelesen hat, sweept und meldet nicht ein zweites
  Mal; nur der erzwungene Admin-Lauf überspringt diese Prüfung.
- **Daten.** Fenster: die letzten 7 Tage bis heute−2 (GSC-Verzug) gegen die
  7 Tage davor. Genau fünf Search-Console-Abfragen über
  `GoogleSearchConsoleClient.search(start_date, end_date, dimensions, *,
  data_state="all")` (paginiert, Scope `webmasters.readonly`): `date`, `page`
  diese Woche, `page` Vorwoche, `page,query` diese Woche, `page` über 90 Tage.
  Kein LLM, keine gespeicherten Seitenmetriken. Ergebnis: Wochensummen
  (Impressions, Klicks, impressionsgewichtete Position) für Woche/Vorwoche,
  `movers.up` (Top 3) und `movers.down` (Top 2) nach Impressions-Delta jeweils
  mit der stärksten Query der Seite.
- **Einzige automatische Aktion.** Indexierte, aktive Shares, älter als 90 Tage,
  mit 0 Klicks und < 10 Impressions in den letzten 90 Tagen gehen per
  `share_snapshots.moderate_share(indexed=False, source="seo_pulse_dormant")`
  auf noindex, höchstens 25 pro Lauf; Share-IDs in `keep_share_ids` sind
  ausgenommen. „Keep indexed“ (`POST /api/admin/seo/shares/{share_id}/keep`)
  indexiert wieder (`source="seo_pulse_keep"`) und trägt die ID in
  `keep_share_ids` ein. Statische Seiten und Topics fasst der Puls nie an.
  Dafür liest jeder Lauf einmal alle `shares` mit `indexed == true`.
- **Zustand** in genau einem Dokument `app_config/seo_pulse` (siehe §6).
- **Meldung.** `telegram_notifier.send_admin_note(text)` an
  `CRITICAL_ERROR_TELEGRAM_CHAT_ID`/`TELEGRAM_CHAT_ID`: ~6–10 Zeilen (Woche,
  Impressions/Klicks gegen Vorwoche, bewegte Seiten mit Query, Anzahl noindex,
  Admin-Link `SEO_ADMIN_URL`) oder eine Fehlerzeile. Ein GSC-Fehler endet als
  `report.error` (sanitisiert), verschiebt `next_run_at` normal und gibt den
  Lease frei; ein Telegram-Fehler bricht den Lauf nie.
- **Admin.** SEO-Tab „SEO pulse“: Schalter (`PUT /api/admin/seo/config`),
  „Run now“ (`POST /api/admin/seo/run`, 6/Stunde, 409 bei laufendem Lease),
  Zeitplanzeile, Fehlerbanner, Wochenzahlen + 12-Wochen-Balken, „What moved“,
  „Set to noindex by the pulse“ mit „Keep indexed“. Status liefert
  `GET /api/admin/seo` (ein Dokument-Read).
- **Legacy.** Firestore `seo_pages` (+ Metrik-Subcollections),
  `seo_collection_runs`, `seo_judgements`, `seo_weekly_reviews`,
  `app_config/scheduled_consensus_publisher` und `app_config/seo_weekly_review`
  liest und schreibt kein Code mehr; Altdaten können in Prod noch liegen.
- Tests: `tests/test_seo_pulse.py`, `tests/js/seo-admin-pulse.test.mjs`,
  native E2E `test_scheduler_transactions.py::test_native_seo_pulse_lease_is_exclusive_and_released`
  und `::test_native_seo_pulse_failure_releases_lease_and_reschedules`;
  Mutation `WP-19` (`tests/e2e/native_mutations.py`) zielt auf
  `SeoPulseService._acquire`.

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
  rate_limit.py              slowapi-Limiter (Client-IP aus Cloudflares CF-Connecting-IP; XFF nur Rückfall ohne Cloudflare, weil Render dort nur anhängt) + prozesslokale UID-Budgets + Retry-After/Satz für 429 (retry_after_seconds, rate_limit_message)
  not_found.py               HTML-404 für Seiten-Navigationen (wants_html_page, not_found_page)
  notice_page.py             Eine öffentliche Hinweisseite (templates/notice.html): Seiten hinter Mail-Links, HTML-429
  observability.py           PII-freie Correlation-IDs (auch im ASGI-Scope), strukturierte Logs + Prozessmetriken
  error_context.py           Inhaltsfreier Alert-Fundort: Repo-Frames, Commit, Instanz, Programmierfehler-Filter
  sourcemaps.py              VLQ-Decoder: Browser-Bundle-Koordinate -> static/js/<datei>.js:<zeile>:<spalte>
app/api/routers/             siehe §2
  api_v1.py                  Gescopte Run-, Publish-, Share-Lifecycle- und Indexing-API + OpenAPI-Modelle
  chat_history.py            Owner-gebundene Chat-/Turn-API inkl. vollständigem Turn-Detail
app/services/
  prompt_config.py           DB-Einstellungen (Zeitzone, Delegation) mit Code-Prompts, Validierung, Transaktionsrevisionen und 30-s-Cache
  prompt_catalog.py          Schreibgeschützter Katalog aller Systemprompts aus dem Code für den Admin
  prompt_defaults.py         Code-eigene Systemprompts für Agent, Einzelantworten und Synthese
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
  citations.py               Antwort-Parsing + Quellen (source_response, make_llm_result), Text vor Suchergebnissen (presearch_end)
  attachments.py             Attachment-Validierung/Aufbereitung
  usage_meter.py             Token-Meter der Transportschicht (ContextVar; Usage je OpenRouter-Request, Schaetzung bei fehlender Usage)
  provider_dispatch.py       Klassifikator "Request nie beim Provider angekommen" (Connect-Fehler, Abbruch vor Dispatch) -> kostenlos statt Schaetzung
app/services/
  consensus_pipeline.py      Neutraler Fan-out→Synthese→Differences→Score-Vertrag für alle Produkte
  chat_store.py              Firestore-Pfade, Turn-Lifecycle/Antwortdokumente, atomare Finalisierung, Idempotenz, Cursor + Allowlists, Loesch-Kaskade
  agent_memory.py            Agent-Memory: Einzel-Erinnerungen (ein Dokument), Opt-in-Fence, Evidence-/Secret-Prüfung, Undo-Log, Prompts, update_memory-Tool
  agent_watch.py             prepare_watch: Watch-Vorschlag am Turn (agent_watch), Agent-Prompt samt Kartenhinweis; startet nie eine Watch
  agent_settings.py          read_settings + prepare_settings_change: aktuelle Einstellungen/Wahl des Kontos lesen, Vorschlag am Turn (agent_settings_proposal) nach Stufe/Modell geprüft, Agent-Prompt samt Rückfrage-Regeln; schreibt nie eine Einstellung
  agent_answer_mode.py       Der Agent schreibt die Antwort selbst als letzte Nachricht seiner Tool-Schleife (seit 2026-10-14, kein Schalter): Konstanten für die Streaming-Sperre (ANSWER_HOLD_CHARS), Notiz (NOTE_CHARS), Erinnerung (TOOL_REMINDERS) und SIDE_TOOLS
  agent_source_evidence.py   Quellenauszüge für die Vergleichsergebnisse des Agenten: Google-Weiterleitungen beim Eintreffen einer Vergleichsantwort durch ihre Seiten ersetzt (resolve_redirects, 3 s), Zitattext + gestützter Satz je Vergleichsantwort, Seitenabruf ohne Suchtext, gepoolte Quellenliste mit Zeichenbudget (nur im Speicher)
  agent_journal.py           Journal eines Agent-Laufs (seit 2026-10-21): ein Thread schreibt die Sitzungs-Updates je Sitzung in Reihenfolge, alles Fällige in einer Transaktion (publish_agents, seit 10-22), wartende Aufrufer zuerst, ungeschriebene Updates zusammengelegt, Live-Zeilen gedrosselt
  agent_coverage_prefetch.py Coverage-Fenster der Agent-Antwort schon beim Schreiben (je 16 feste Sätze, über judge_transport); judge() übernimmt wortgleiche Sätze, fragt nur den Rest (seit 2026-10-17); fertige Fenster gehen als vorläufige Marken (coverage_preview) an die Seite (seit 2026-10-18)
  agent_read_source.py       Tool read_source (an, AGENT_READ_SOURCES=0 schaltet ab): Orchestrator liest nach dem Vergleich eine zitierte oder im Chat verlinkte URL über OpenRouters web_fetch (Responses API, PageFetch, Standard-Judge als Helfer), Grenzen 5/Nachricht 3/Schritt, Seitentext im Toolergebnis (der Agent schreibt daraus), read_sources für Review und Coverage-Judge
  chat_context.py            Owner-gebundene Context-Versionen, strukturierte Memory, Frage-Auflösung vor dem Fan-out, Budgets, Lease/Idempotenz, Fallback-Rendering + Provider-Cache
  usage_repository.py        Run-Belege auf dem Tokenkonto (admission/authorize_operation/reserve/consume/release/book_operation/get_run/context-target-binding)
  run_metering.py            OperationBooking: Meter um eine Pipeline-Operation binden, Summe genau einmal buchen
  agent_quota.py             Gemeinsames UTC-Tokenkonto (Agent-Reserve/Settle, Pipeline-Admission/Holds/Buchung, account_tier)
  agent_background.py        Agent-Turns auf eigenem Thread statt an der Verbindung (start/stop per Request oder Turn, Stop-vor-Start-Marke, Drain bei SIGTERM)
  agent_live.py              Prozesslokale Frames je laufendem Turn (SSE-Tail für POST /agent, JSON für /live, reset bei Fensterverlust)
  agent_budget_config.py     Admin-Konfiguration des Kontos: tier_limits, run_estimates, Revision/Reset
  api_account_cleanup.py     Fail-closed Account-Blocks + retrybare API-Datenlöschung
  account_deletion.py         Persistenter Vollkonto-Tombstone + bereichsweise Retry-Kaskade
  persistence_guard.py       Transaktionale Bookmark-/Feedback-Budgets + run-gebundene Votes
  registration.py            Nicht-enumerierender Firebase-Mailbox-Setup-Pfad
  follow_challenges.py       Gehashte persistente Resend-/Empfänger-/Globalbudgets für Double-Opt-in
  api_key_repository.py      SHA-256-gehashte, UID-gebundene API-Schluessel
  api_run_repository.py      Idempotenz + persistente API-Run-State-Machine
  api_consensus_runner.py    Asynchroner At-most-once-Orchestrator auf bestehenden Engines
  google_search_console.py  Read-only Search-Analytics-HTTP-Client (generisches paginiertes search()) + sichere Config-Fehler
  seo_pulse.py              Wöchentlicher deterministischer SEO-Puls (Lease, Bericht, Dormant-Noindex, Telegram-Notiz)
  telegram_notifier.py      Gemeinsamer Bot-API-Client, Critical-Alerts (Fingerprint, Budgets, fix-context) + Admin-Notiz (send_admin_note)
  error_alerts.py           report_server_exception: abgefangene Programmierfehler in Streams als Alert
  telegram_watch.py         User-Link-Deep-Links/Webhook, Callback-Aktionen (Bestätigung per editMessage* in der Meldung) + ein Watch-Nachrichtenversuch (send_watch_message)
  notification_markdown.py  Antwort-Markdown aus der Public-Pipeline neu geschrieben: Mail-HTML mit Inline-Stilen, Klartext, Telegram-Subset
  notification_outbox.py     Dauerhafte Benachrichtigungs-Outbox (notification_outbox): stabile Delivery-IDs, Lease, Versuche, Terminalstatus
  notification_delivery.py   Ein Zustellversuch je Outbox-Item mit Abmelde-/Pause-/Kanalprüfung + Retry-Pass run_outbox_tick
  share_snapshots.py         Snapshot-Lifecycle (pending→share), Quoten, Cleanups, Sitemap-Quellen
  favicons.py                Begrenzter Favicon-Fetch (sz=128, < 64 px = kein Icon), Singleflight, LRU-/Negativcache, cached_favicon ohne Abruf
  retention_maintenance.py   Periodischer Pending-/Revoked-Share-Cleanup + Outbox-Retention (30 Tage, nur Terminalstatus)
  watch_service.py           Watch-CRUD, Tier-/Intervall-/Zielregeln, Lauf-Abschluss (Signal, geltende Antwort, Abschluss), Unsubscribe-Tokens
  evidence_change.py         Change-Judge mit Quellen + serverseitige Belegprüfung (Ursache, tragende Quellen), geteilt von Watch und Topic
  watch_probe.py             Täglicher Beleg-Scan zwischen zwei Checks: Claim, ein günstiger Such-Call, Vorziehen des vollen Checks
  watch_images.py            Watch-Bild: Gegenstand (schema.org Product …), sonst Logos der Seiten, um die es geht, sonst passenden Artikel (og:image) unter den Quellen finden, Bild SSRF-sicher holen, WebP-Vorschau speichern/ausliefern; Judge-Wahl von Symbol + Seiten einmal pro Watch
  watch_symbols.py           Feste Symbolliste (Name -> Bedeutung) fürs Dashboard, wenn eine Watch kein Bild hat; Standardsymbol
  opinion_map.py             Datenminimierte, mehrdimensionale Provider-Positionen + Direction-Shift-Berechnung
  watch_brief.py             Morning-Brief-Settings (watch_briefs), transaktionaler Claim, Digest-Aggregation, Brief-Unsubscribe-Tokens
  watch_scheduler.py         Owner-gebundener Global-Lease, Tagesbudget, Pipeline-Adapter, run_brief_tick + Outbox-Retry-Pass
  mailer.py                  Multipart-HTML/Plaintext-SMTP-Versand via Thread-Executor
  public_markdown.py         Server-Markdown-Rendering für Share-Seiten; auf Watch-Seiten Namen der Quellen als Links + ausgehende Links mit Favicon (`site_links`)
  source_links.py            Watch-Seiten: Direktlinks über der Antwort (`key_links`) und Nennungen der Quellen im Text (`site_mentions`); kompakt fürs Dashboard (`card_links`); Navigation, kein Beleg; `is_own_page`/`without_own_pages` halten consens.io aus Quellen und Judge
  source_redirects.py        Google-Grounding-Weiterleitungen durch ihr Ziel ersetzen: beim Speichern einer Watch-Prüfung (10-s-Budget) und für jede Agent-Vergleichsantwort (agent_source_evidence.resolve_redirects, 3 s); paralleles `agent_read_source.resolve_redirect`
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
  `static/firebase.js` lädt seit 2026-10-05 nur noch App- und Auth-SDK (das
  ungenutzte Firestore-SDK blockierte vorher den App-Start), und die CSP führt
  `firestore.googleapis.com` nicht mehr eigens. Sämtlicher Datenzugriff läuft über das Backend mit dem
  Firebase-Admin-SDK, und das umgeht die Regeln vollständig.
- **Schreibrechte auf `users/{uid}` dürfen NIE wieder geöffnet werden.**
  `app/core/security.py` liest Pro- (`tier`) und Admin-Status (`role`) aus genau
  diesem Dokument. Eine frühere Regel erlaubte dem eingeloggten Eigentümer
  `write` — damit konnte sich jeder Nutzer per `setDoc(..., {role:"admin"})`
  selbst zum Admin machen. Wer Rollen künftig client-schreibbar braucht, muss
  sie vorher aus `users/{uid}` herauslösen (z. B. Firebase Custom Claims).

**Firestore-Collections** (verifiziert über Code):
- `users/{uid}` — `tier` (`free`/`plus`/`pro`, historisch auch `premium` = Pro)
  plus `tier_updated_at`/`tier_updated_by`/`tier_note`, `role`, `language`
  (`en`/`de`, die Sprache der letzten App-Ladung für Konto-Mails, nur der
  Server schreibt sie: `account_language`); Subcollections `bookmarks`, `counters`, `chats`,
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
    Bei erreichtem Limit (`MAX_CHATS_PER_OWNER`, 403 `chat_limit_reached`)
    räumt `create_chat` seit 2026-10-11 zuerst Chats ab, auf die kein Bookmark
    zeigt und die älter als 1 h sind (`reclaim_unreachable_chats`, max. 25,
    reguläre Löschung per `request_chat_deletion`). Solche Chats entstehen, weil
    der Browser den Chat vor dem ersten Turn anlegt (abgelehnte Agent-Nachricht,
    Stop, Lauf ohne gespeicherte Antwort); ohne Bookmark sieht und löscht sie
    niemand. Erst wenn nichts frei wird, bleibt es bei 403; Agent zeigt dann wie
    Consensus den Text aus `App.chatPersistenceErrorMessage` (chat-session.js).
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
  Die Kontolöschung (Bereich `tier_audit`) löscht die Zeilen des Kontos und
  leert `changed_by`, wo das Konto nur als Admin steht.
- `api_consensus_runs/{run_id}` — UID-gebundener v1-API-Run mit serverseitig
  eingefrorenem Request/Modellplan, `idempotency_hash`, eigenem `usage_key`, Status und Status-
  Zeitstempeln, einstündigem Running-Lease, der bei Annahme eingefrorenen Stufe
  (`tier_at_acceptance`, mit `is_pro_at_acceptance` als Altfeld) sowie terminal
  `result` oder sanitisiertem `error` und 30-Tage-`expires_at`. Erlaubte Hauptfolge:
  `accepted → reserved → running → succeeded|failed`; zusätzlich
  `accepted → failed` (`reservation_expired`) und nach Owner-Löschung der
  inhaltsfreie Tombstone `succeeded|failed → deleted` bis zum Retention-Ablauf.
- `app_config/prompts` — globale Laufzeit-Einstellungen aus `prompt_config.py`
  (Dokumentname historisch): `reference_timezone`, `delegation` (aktiviert,
  Laufzeit-/Kontext-/Nachrichten-/Parallelitäts- und Budgetlimits; Defaults in
  `agent_delegation_config.py`), ganzzahlige `revision`, UTC-`updated_at` und
  Admin-UID bzw. Wartungskennung `updated_by`.
  **Systemprompts sind seit 2026-10-07 code-eigen und im Admin nur lesbar:**
  `get_config()` behält seine Form (`prompts.agent|answers|consensus`,
  `delegation.orchestrator_prompt|worker_prompt`), setzt die Texte aber immer aus
  `prompt_defaults.DEFAULT_PROMPTS` bzw. `agent_delegation_config.PROMPTS`.
  Prompttexte in älteren Dokumenten werden beim Lesen ignoriert (das Dokument lädt
  weiter fehlerfrei) und beim nächsten Speichern entfernt; neue Revisionen
  enthalten keine Prompttexte. Prompt-Änderungen gehen nur über Code + Deploy.
  `GET /api/admin/prompt-config` (Router `admin.py`) liest frisch und liefert die
  editierbare Sicht (`config`/`defaults` ohne Prompttexte), Limits sowie
  `prompts_readonly` aus `prompt_catalog.prompt_catalog()`; es erzeugt keinen Datensatz.
  `PUT /api/admin/prompt-config` verlangt `revision` plus `config` mit
  `reference_timezone` und optional vollständigen `delegation`-Einstellungen
  (fehlt `delegation`, bleibt die gespeicherte erhalten). Von Alt-Clients
  mitgeschickte `prompts` bzw. Delegations-Prompttexte werden verworfen.
  Beide Endpoints prüfen widerrufbare Auth-Tokens und `is_user_admin`.
  Eine Firestore-Transaktion prüft die erwartete Revision und schreibt aktive
  Konfiguration sowie vollständigen Audit-Snapshot unter
  `app_config/prompts/revisions/{revision:012d}` gemeinsam. Konflikte liefern 409;
  der Browser bewahrt den Entwurf. Unveränderte bereits gespeicherte Werte
  erzeugen keine neue Revision (außer ein Altdokument trägt noch Prompttexte).
  Runtime-Reads sind pro Worker 30 Sekunden
  gecacht; bei Lesefehlern bleibt der letzte gültige Stand oder der App-Default
  aktiv. Admin-Lese-/Schreibfehler liefern 503 und keine vorgetäuschte Speicherung.
  `MAX_PROMPT_CHARS`/`MAX_PROMPT_BYTES` (10.000 Zeichen / 28.000 UTF-8-Bytes)
  bleiben als Obergrenze der Code-Prompts (Test), damit der Datumsblock beim
  `/prepare`→`/ask_*`-Roundtrip mit dessen 12.000-Zeichen-/32.000-Byte-Limit passt.
  `prompt_catalog.py` listet die angezeigten Prompts als eine Liste
  `{key, label, used_for, source, text}` (`agent`: Agent-Steuerung samt Schreibregeln, `comparison`: Vergleichsmodelle mit Datums-Platzhalter für Tiefe „full“,
  `answers`/`consensus`: Consensus-Einzelantworten/-Endantwort,
  `delegation_orchestrator`/`delegation_worker`; bis 2026-10-14 zusätzlich die
  Prompts des getrennten Antwortschritts); neue Prompts = ein Eintrag in `_ENTRIES`. Datum, Modellidentität, Verlauf,
  Quellen-/Antwort-Scaffolding und Tooldefinitionen werden im Code zusammengesetzt.
  Eigene Nutzer-Prompts haben für Einzelantworten Vorrang. Judge-/Resolve-/
  Spezialprompts bleiben im Code.
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
  (nie leer für Leser). Dasselbe gilt für alle geteilten Mengen, Listen und
  Dicts, die Requests ohne Lock lesen (Provider-Modelle, `PREMIUM_MODELS`,
  `ALLOWED_CONSENSUS_MODELS`, `LIMITS`, Presets, Watch-Modelle, Judge-Familien,
  `MEMORY_EDIT_CONFIG`; Audit C8): neue Werte werden vorher berechnet und in
  place ohne leeren Moment getauscht (`_replace_set`: erst ergänzen, dann
  kürzen; `_replace_dict`; Listen per `lst[:] = neu`). `PREMIUM_MODELS` wächst
  vor dem Tausch der Modellmengen und schrumpft danach, damit ein neues
  Pro-Modell nie kurz Free ist; der Rollback (`_restore_runtime_config`) folgt
  derselben Reihenfolge. Grenze: ein
  einzelner Lauf liest weiter die prozessweiten Maps; eine Aktivierung während
  eines laufenden Requests ist nicht als Snapshot pro Lauf eingefroren.
  `consensus` steuert den App-Consensus-Picker;
  Fehlende Limitfelder werden beim Startup normalisiert und per Merge in das
  Admin-Dokument zurückgeschrieben (Schema-Backfill ohne Verlust vorhandener Werte).
  `normalize_limits_config` erzwingt Mindestwerte (`_LIMIT_MINIMUMS`, Audit
  C16): `*_max_tokens` ≥ 1024, `*_max_words` ≥ 50,
  `consensus_max_answer_chars` ≥ 1000, `consensus_max_question_chars` ≥ 200;
  ein kleinerer Wert (z. B. ein Tippfehler 0) fällt auf den Default zurück,
  auch beim Admin-Speichern. Zähler wie die Watch-Limits behalten 0 als echte
  Einstellung, die Follow-up-Kontext-Caps kürzen nur den Kontext.
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
  (`apply_judge_families`; die eigene Familie ist erlaubt, ohne
  Eintrag/Credential Auto über `JUDGE_FAMILY_PRIORITY`). Auto priorisiert
  OpenAI, dann Gemini, für jede Engine-Familie. Danach folgen
  unverändert DeepSeek, Grok, Anthropic, Mistral, Kimi, GLM und Meta.
  Die Standard-/Pro-Modellzuordnung bleibt admin-konfiguriert. Differences
  und Coverage behalten ihre Retry-/Fallback-Pläne auch bei manueller
  Familienpräferenz; ein Provider-Rate-Limit verhindert den Wechsel zur
  nächsten geplanten fremden Familie nicht. In Serverpfaden verwenden
  alle Familien denselben OpenRouter-Key; im Own-Key-Modus gibt es keinen
  Fallback auf das Server-Credential.
- `app_config/api_consensus_runs_retention_backfill` — Erledigt-Marker des
  einmaligen `expires_at`-Backfills der v1-API-Runs (`completed_at`, Zahl der
  ergänzten Runs); fehlt er, scannt der nächste Maintenance-Lauf einmal.
- `app_config/seo_pulse` — einziger Zustand des SEO-Pulses (§4 „SEO-Puls“):
  `enabled` (Default true), `next_run_at`, `last_run_at`, Lease
  `lease_until`/`lease_run_id` (15 min), `report` (Fenster, Woche/Vorwoche mit
  Impressions/Klicks/Position, `movers.up|down` samt Top-Query, `noindexed`,
  `generated_at` oder `error`), `history` (letzte 12 Wochen: `end`,
  `impressions`, `clicks`), `noindexed`-Protokoll (letzte 50) und
  `keep_share_ids`. Keine Seitenmetriken, keine Secrets.
- Legacy, von keinem Code mehr gelesen oder geschrieben (seit 2026-10-04):
  `app_config/scheduled_consensus_publisher` (Publisher-Steuerung) und
  `app_config/seo_weekly_review`.
- `pending_results` — kurzlebige Consensus-Ergebnisse fürs Sharing (TTL/Cleanup),
  mit `answer_provenance` (`developer|byok`) für die Ranking-Berechtigung.
- `answer_receipts/{receipt_id}` — serverseitige `/ask_*`-Antwortbelege
  (Owner, Run-Bindung, Frage-Hash, Familie, konkretes Modell, Text, Digest,
  Quellen, Abschlusszustand, Provenienz); 24 h `expires_at`, Retention-Sweep,
  Kontolöschung. Einzige Quelle für Modellantworten in `/consensus`.
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
- `users/{uid}/settings/app` — Kontoeinstellungen (seit 2026-10-12): `values`
  (nur gewählte Einstellungen, Schema `UserSettings` in
  `app/services/user_settings.py`), `revision`, `updated_at`. Geschrieben nur
  über `PATCH /api/my/settings` mit dem Tombstone-Zaun; gelöscht mit dem Konto
  (Subcollection `settings`). Siehe §4 „Kontoeinstellungen“.
- `users/{uid}/memory/entries` — gespeicherte Einzel-Erinnerungen (`items`,
  `revision`, Undo-Log `changes`, `changes_purge_at`, siehe §3 „Agent-Memory“);
  `users/{uid}/memory/profile` trägt zusätzlich `auto_memory`. `items` und
  `changes` sind vom Indexing ausgenommen, `memory.changes_purge_at` hat einen
  Collection-Group-Index für `cleanup_memory_change_logs` (stündlicher
  Retention-Loop). Agent-Turns tragen `agent_memory` (welche Erinnerung
  geändert wurde: `change_id`, `op`, `item_id`, `undone`, seit 2026-10-08 ohne
  Text); gelöscht mit Chat bzw. Konto. Seit 2026-10-11 kann ein Agent-Turn
  `agent_watch` tragen (`question`, `goals`, `interval`: der Watch-Vorschlag,
  siehe §3 „Agent-Watch“; ob er gestartet wurde, steht nur in `watches`).
  Seit 2026-10-17 kann er `agent_settings_proposal` tragen (`settings` in
  Kontoform, `notes`; siehe §3 „Agent-Einstellungen“; übernommen wird nur
  über die Karte nach `users/{uid}/settings/app`).
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
  `source_api_run_id`, Legacy-`publication_source=scheduled_publisher` und
  Index-Review-Auditfelder inkl. `review_source`, z. B. `seo_pulse_dormant`/
  `seo_pulse_keep`, …). `publication_source` tragen nur alte Publisher-Shares;
  neue Shares erhalten es seit 2026-10-04 nie. Public-Shares sind per
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
  `model_tier` (leer; nur die Legacy-Publisher-Watches tragen intern `free`,
  ebenso ein altes, nicht mehr gelesenes `publication_source`),
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
- `watch_images/{watch_id}` — die Vorschau einer Watch (seit 2026-10-11): `content`
  (WebP, Kante ≤ 320 px, ≤ 120 kB), `content_type`, `token` (sha256-Präfix des
  Inhalts), `width`/`height`, `owner_uid`, `created_at`. Am Watch-Dokument steht
  dazu `image = {status: ready|none|dismissed, kind: item|article|logo, token, width,
  height, source_url, source_host, attempts, tries, version, sites, picked_at}`
  (`sites` = Domain-Wahl des Judges, auch `[]`) und seit 2026-10-12 `symbol`
  (Name aus `watch_symbols.SYMBOLS`, einmal gesetzt) sowie `visual_tries`
  (Fehlschläge des Judges, Deckel 3) und `key_links` (bis zu drei
  `{url, title, domain}` fürs Dashboard aus der Antwort, die die Watch-Seite
  zeigt: beim Anlegen aus dem Share, dann mit jedem angenommenen Check —
  `source_links.card_links`, damit die Liste keine Checks nachliest). Gelöscht in derselben Transaktion wie die
  Watch (`_delete_watch_record`, damit auch Share-Hard-Delete und Kontolöschung)
  und beim Entfernen durch den Owner.
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
- Legacy-SEO-Collections `seo_pages` (+ Subcollections `daily_metrics`,
  `query_snapshots`), `seo_collection_runs`, `seo_judgements` und
  `seo_weekly_reviews`: seit 2026-10-04 von keinem Code mehr gelesen oder
  geschrieben; Altdaten können in Prod noch liegen.
- `differences_stats` — anonyme Differences-Telemetrie (Schema v3): pro erfolgreichem
  Consensus-Lauf ein Dokument mit Zähl-/Strukturdaten (Agreement-Score,
  Widersprüche mit Severity und beteiligten Providern, Modell-Metadaten,
  seit v2 `judges`-Metadaten des tatsächlich genutzten Differences-Judges,
  seit v3 zusätzlich dessen erfolgreiche Attempt-Nummer und Versuchsdauer,
  `schema_version`) — **niemals** Frage-/Antwort-/Claim-Texte, Zitate, UID
  oder IP (anonym i. S. v. ErwGr. 26 DSGVO). Schema + Datenschutz-Regeln in
  `app/services/differences_stats.py`; geschrieben aus `chat.py::consensus`
  (`source: "app"`) und seit 2026-10-15 aus `ComparisonTools.record_stats`
  nach `judge_answer`, ein Dokument je geprüftem Agent-Vergleich (`source:
  "agent"`, bei einem geprüften eingefügten Text `"agent_text"`;
  `consensus_model` = Chatmodell). Vorher schrieb nur Consensus, mit Agent als
  Standard (seit 2026-10-02) fiel der Datensatz von ~90 auf 2 Läufe pro Woche.
  Fire-and-forget, Mock-Läufe schreiben nicht.
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
  1 KiB bis 32 MiB) begrenzt den vollständigen HTTP-Body vor Framework-Parsing;
  `PATH_MAX_REQUEST_BODY_BYTES` setzt für kleine JSON-Routen (heute
  `/api/my/settings`, 256 KB) eine engere Grenze. Ein 422 nennt höchstens
  `MAX_VALIDATION_DETAILS` (20) Probleme und zählt den Rest (`omitted`), damit
  ein Body mit vielen Schlüsseln keine riesige Antwort erzeugt.
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
  früher handgepflegte Versionsnummer (`v1.11.1`) ist damit ersetzt. Derselbe
  Wert steht als `data-app-build` in `#appBootstrapConfig`, und
  `GET /api/build` (`pages.py`, `{"build": …}`, `no-store`, 60/min, kein
  Firestore) nennt den gerade laufenden — beides für `app-update.js`.
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
  SEO-Puls (Fehlerbanner im Admin-SEO-Tab). Diese Search-Console-Credentials
  sind unabhängig vom OpenRouter-LLM-Key.
- SEO-Puls-Telegram: `TELEGRAM_BOT_TOKEN`, Ziel-Chat wie bei kritischen
  Fehlern (`CRITICAL_ERROR_TELEGRAM_CHAT_ID`, sonst `TELEGRAM_CHAT_ID`) und
  optional `SEO_ADMIN_URL` (Default `https://www.consens.io/admin#seo`). Jeder
  Lauf versucht genau eine nicht-fatale Notiz. `SEO_CONTENT_JUDGE_MODEL`,
  `SEO_PORTFOLIO_JUDGE_MODEL` und `OPENAI_TOPIC_MODEL` werden seit 2026-10-04
  nicht mehr gelesen.
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
Picker. Die Modellmenge einer Familie heißt nur noch `PROVIDERS[key].models`
(die früheren `ALLOWED_*_MODELS`-Aliasse sind seit Audit C16 entfernt; der
Firestore-Load mutiert die Menge in place). Familienspezifische Hygiene
steht in `PROVIDER_MODEL_MIGRATIONS`/`PROVIDER_DEPRECATED_MODELS`, Reasoning-
Varianten als Daten in `MODEL_REQUEST_CONFIG`: Kimi K2.6 sendet
`reasoning.enabled=false`, K3 zwingend `reasoning.enabled=true` (auch mit Reasoning-Schalter;
explizite Modell-Policies gewinnen dort).
Beide Kimi-Modelle begrenzen OpenRouter auf `provider.only=["moonshotai"]`
mit `allow_fallbacks=false`; die Standard-Felder `sort`/`data_collection` bleiben beim Merge erhalten.
Live-Diagnose: automatische Routen lieferten kaputte Tool-Ausgaben; K3 suchte
auf der Moonshot-Route erst mit aktiviertem Reasoning. Suche bleibt modellgesteuert
über `openrouter:web_search`, ohne gemeinsame Quellen oder neue Transport-Retries.
Die Modellkonfiguration gilt auch für Consensus-Aufrufe; Ausgabe-/Suchbudgets
bleiben unverändert. GLM 5.3 Flash/5.3 sendet `reasoning.effort=low`.
Feste Reasoning-Werte liegen ebenfalls zentral in `config.py`
(`REASONING_EFFORT_FOR_*`, `judge_reasoning_effort`);
`effective_model_reasoning` bildet daraus mit den Modell-Overrides exakt die
Prioritaet des Antwort-Request-Builders. Memory Edit und die übrigen festen
Tasks importieren diese Werte statt eigener Stringliterale.
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
Die Logo-URL kommt immer aus `ProviderConfig.icon_url` (`asset_url`, also mit
Inhalts-Hash und ein Jahr Browser-Cache), für Picker, Model Pulse, Leaderboard
und Share-Seiten; Templates binden Logos über `{{ asset_url(...) }}` ein
(`tests/test_static_images.py` verbietet nackte `src="/static/icons/…"`). Ein
neues PNG-Logo vor dem Commit mit `scripts/shrink_images.py` auf 144 px
verkleinern (Budget 20 KB pro Logo, ebenda auch das Landing-OG-Bild ≤ 300 KB).

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

**Meta nur mit Glimmer (seit 2026-10-08):** `meta/muse-spark-1.3` ist
nicht wählbar. Sein einziger OpenRouter-Endpunkt („Meta“) steht nicht in
`GET /api/v1/endpoints/zdr`, und ohne die 18+-Bestätigung des Kontos antwortet
er vorher schon mit `403 … age_18plus`. Spark steht deshalb in
`ZDR_UNAVAILABLE_MODEL_IDS`; die Familie hat kein wählbares Pro-Modell und
keinen Alias `Meta-Pro`, der Pro-Judge fällt auf Glimmer zurück
(`_BASE_PRO_JUDGE_BY_PROVIDER`). `meta/muse-glimmer-30b` läuft unter ZDR
(Phala/DeepInfra/Together). Muse denkt zwingend, deshalb steht `reasoning.effort` fest auf `low` und ein
zu kleines `max_tokens` liefert nur Reasoning-Tokens und ein leeres Final
(siehe `_responses_empty_result`). Der Contributor-Tarif
`meta/muse-spark-1.3-contributor` ist bewusst nicht aufgenommen: Meta darf
dort Prompts und Antworten für seine Produkte verwenden, was dem Routing
`data_collection=deny` und der Zusage in Terms/Privacy widerspricht.

**Qwen (seit 2026-10-22, zehnte Familie):** Basis `qwen/qwen3.8-27b` (offene
Gewichte, 0,04/1,35 $ je Mio., Text/Bild/Video, rund 20 Anbieter inkl.
ZDR-Endpunkten, am schnellsten bei Cerebras), Pro `qwen/qwen3.8-max-prime`
(4/12 $, nur bei Alibaba, kein ZDR-Endpunkt: in Google-Chats fällt es aus wie
jedes andere nicht routbare Modell). Beide laufen mit `reasoning.effort` `low`
(`MODEL_REQUEST_CONFIG`). Live-Probe mit dem echten Vergleichs-Payload: ohne
Reasoning rief 27B die Websuche in 5 von 8 Antworten nicht auf und hielt 2025
für das laufende Jahr; mit dem Standardaufwand (`xhigh`) liefen 3 von 8 ins
Output-Limit; `low` suchte 8 von 8 Mal, Median 12 s (gpt-oss-120b 4 s). Die
Max-Modelle brauchten 24–138 s, das offene 2.4T-A95B brach zwei von drei
Antworten am Limit ab. Bilder nativ (`PROVIDER_IMAGE_SUPPORT`), PDFs über den
Text-Fallback.

Code-Fallback-Modell-IDs und Labels liegen in `app/core/config.py`
(`ALLOWED_*_MODELS`, `PREMIUM_MODELS`, `DEFAULT_MODEL_BY_PROVIDER`,
`FREE_DEFAULT_MODEL_BY_PROVIDER`, `MODEL_LABEL_OVERRIDES`). In Produktion sind
Providerlisten, Reihenfolge, Free-Defaults und Premium-Zuordnung aus
`app_config/models` autoritativ. Ebenfalls in `config.py`: die festen
Produkt-Metadaten `CONSENSUS_PRESET_DEFINITIONS` und Basiswerte ausschließlich
für ein fehlendes/noch nicht migriertes Dokument.
Firestore `preset_models` speichert pro Daily/Open Models (ID: `balanced`)/High
Quality (ID: `thorough`) unter `answers` genau sechs unterschiedliche
Familienmodelle plus `consensus`; das alte Top-Level-Provider-Schema wird beim
Laden migriert. Daily/Open Models bleiben Free-faehig und
High Quality bleibt unabhaengig von der Konfiguration Pro-only. Open Models
(seit 2026-10-15, vorher das mit Daily deckungsgleiche „Balanced“) ist eine
zweite Meinung aus sechs Modellen mit offenen Gewichten (Qwen3.8 27B,
Gemma 4 31B, DeepSeek V4.1 Flash, Kimi K2.6, GLM 5.3 Flash, Muse Glimmer 30B;
Beleg je Modell: `hugging_face_id` im OpenRouter-Katalog) mit demselben
Schreiber wie Daily. Free-Presets haben je Familie praktisch nur ein aktuelles
Modell, ein zweites Free-Preset unterscheidet sich deshalb nur in der
Aufstellung. Bis 2026-10-22 stand dort gpt-oss-120b (OpenAI, also das Labor
des Schreibers; las nur Text und nannte in der Live-Probe trotz Suche
Zinssatz und Förderung von 2024). Ein gespeichertes Open Models mit gpt-oss
migriert ohne Firestore-Write: `DEPRECATED_CONSENSUS_PRESET_MODELS` nennt es,
und weil die Basis keine OpenAI-Belegung mehr hat, fällt die Familie aus dem
Preset und die Basis füllt den Platz mit Qwen (`_normalize_preset_answers`).
gpt-oss-120b bleibt wählbar und liest nur Text: `ProviderConfig.text_only_models`
nimmt einzelne Modelle einer sonst anhangfähigen Familie von Anhängen aus.
`scripts/model_release_check.py` (lokaler geplanter Task
`consens-model-release-check`, alle 3 Tage) prüft das Dokument nur lesend
(`.get()`): neue OpenRouter-Modelle, verschwundene konfigurierte IDs,
Preset-Befunde (Modell nicht in der Familienliste, Premium in Daily/Open Models,
neueres Modell derselben Reihe, identische Presets) und je eine Live-Probe (App-Routing) der
genutzten Modelle. Zustand liegt neben dem Task
(`~/.claude/scheduled-tasks/consens-model-release-check/last-seen.json`), damit
nur Neues gemeldet wird; der Aufruf ist in `.claude/settings.local.json`
freigegeben, weil ein unbeaufsichtigter Lauf sonst an der Rückfrage hängt.
`scripts/daily_chat_review.py` (lokaler geplanter Task `consens-chat-review`,
täglich 07:15, seit 2026-10-18) liest nur: Turns externer Konten seit dem
letzten Lauf (eigene Konten per E-Mail-Marker `maxl.plack`/`ml.plack`/`nodon`
über Firebase Auth ausgeschlossen, Nutzer als Pseudonym `U…`), je Turn Frage,
Antwortanfang, Ablauf aus den Receipts (Vergleichsdauer, langsamstes Modell,
Ausfälle, Schreib- und Prüfdauer, Judge-Timeouts, langsamster Judge-Call,
Kosten; gestoppte Judge-Calls, meist Hedge-Verlierer, getrennt als
`judge_calls_stopped` und nicht in der Prüfdauer) und Prüfstatus, dazu
gezählte Warnungen aus dem Render-Log. `collect` gibt JSON aus und merkt sich
den Stand in `pending.json`, `save` übernimmt ihn nach `state.json` (beides
unter `~/.claude/scheduled-tasks/consens-chat-review/`). Der Task schreibt
daraus einen kurzen Bericht mit Vorschlägen, die Max bestätigen muss; beide
Befehle sind in `.claude/settings.local.json` freigegeben. Weil Läufe
geplanter Tasks in der Desktop-App still enden, pingt ein Task, der Max
braucht (Vorschläge, fertiger Freitags-Post, offene Entscheidung), einmal per
`scripts/task_ping.py "<Satz>"`: Operator-Bot, Ziel
`TASK_PING_TELEGRAM_CHAT_ID` aus der lokalen `.env` (bewusst nicht
`TELEGRAM_CHAT_ID`, sonst alarmierten lokale Server), Text auf 300 Zeichen
gekürzt, damit kein Bericht in Telegram landet; ebenfalls freigegeben. Grok 4.3 ist
seit 2026-10-11 ein einziger Free-Eintrag „Grok 4.3“ ohne feste Denkstufe
(OpenRouter-Standard „low“; Reasoning-Schalter und Agent-Menü setzen die Stufe).
Grok-Alt-Aliasse (u. a. 4.1 Fast) und die früheren Varianten
`grok-4.3-no-reasoning`, `grok-4.20-non-reasoning` und `grok-4.20` migrieren
beim Laden und in `comparison_selection`/`resolve_agent_model` auf `grok-4.3`
(`GROK_MODEL_MIGRATIONS`), ebenso in `base.validate_model`/`handle_ask` (`/ask_*`)
und den Judge-/Chat-Memory-Zuordnungen; der Grok-Pro-Alias ist `grok-4.7`. Ein
Dokument von vor der Zusammenlegung (`predates_grok_merge`: führt noch eine der
alten Varianten) meint mit `grok-4.3` unter `premium` die frühere Pro-Variante;
Loader und `admin.normalize_models_document` nehmen es dann aus der Pro-Liste.
Danach entscheidet der Admin wieder frei. Ebenso migriert seit 2026-10-15
`deepseek-v4-flash` auf `deepseek-v4.1-flash` (`DEEPSEEK_MODEL_MIGRATIONS`,
`DEEPSEEK_FLASH_MODEL` ist jetzt V4.1 Flash): In den Prod-Receipts vom
30.09.–14.10. brauchte V4 Flash als Vergleichsantwort im Median 63 s statt
18 s und war in 10 von 16 Läufen mit ihm das langsamste Modell; pro Antwort
kosten beide etwa gleich viel. Die Prod-Presets führten schon V4.1 Flash, der
Free-Default (`defaults.deepseek`), Judge-, Chat-Memory- und Watch-Zuordnungen
und gespeicherte Auswahlen noch V4 Flash. Der Loader migriert alle beim Laden;
Free-Default, Judges und Chat-Memory schreibt er zurück (`schema_backfill`),
Watch-Zuordnungen und Providerliste erst ein Admin-Save. Eine gespeicherte Reasoning-Ausnahme
für ein Modell, das kein Sparmodell mehr ist, verwirft das Laden
(`validate_reasoning_policy(drop_retired=True)`) statt die ganze Konfiguration
abzulehnen; Admin-Saves bleiben strikt.
  Presets dürfen ausschließlich bereits konfigurierte Provider-Modelle
  referenzieren; sie fügen selbst keine Providerzeilen hinzu.
  `cfg.virtual_model_ids()` listet alle internen IDs, deren API-Modell
  abweicht. Jede Stelle, die eine konfigurierte Modell-ID in einen
  Provider-Request schreibt, muss vorher über `get_model_config(...).api_model`
  auflösen — die Judge-/Fallback-Pfade der Differences-, Resolve- und
  Consensus-Engine taten das früher nicht und quittierten die damalige
  Variante `grok-4.3-no-reasoning` mit HTTP 400 „Model not found“. Das Admin-Dashboard
  blendet die Auflösung als `→ <api_model>` hinter dem Optionsnamen ein.
  Die Admin-Dropdowns blenden Premium-Modelle in Free-Kontexten (Free Watch,
  Daily/Open-Models-Preset) nicht mehr aus, sondern zeigen sie deaktiviert mit dem
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

**Provider-Routing (seit 2026-10-17):** Jeder Modellaufruf sendet
`openrouter_contract.provider_routing()` = `{"sort": "throughput",
"data_collection": "deny"}`: der Endpunkt mit dem höchsten gemessenen Durchsatz
unter denen, die Prompts nicht sammeln. Gesetzt in `AgentCompletion.stream`,
`PageFetch.stream`, `build_provider_payload`, `_call_engine_text`, dem
Consensus-Stream und `memory_edit`; Registry-Felder des Modells (Kimi
`only`) kommen obendrauf. Ein `service_tier` im `request_config` geht als
Top-Level-Feld mit (Agent-Judges der OpenAI-Familie: `priority`, siehe
`JUDGE_SERVICE_TIER_BY_PROVIDER`). Die Schritte des Chatmodells senden dazu eine
Session pro Chat (`x-session-id`), damit sie beim Endpunkt mit ihrem Prompt-Cache bleiben,
jeder Hilfsaufruf eine eigene (siehe „Sticky Endpunkt“ im Agent-Abschnitt). Zero Data Retention gilt nur noch in Chats mit
Google-Daten (`google_connections.restricted_model` setzt `zdr: true` +
`deny` auf jeden Aufruf des Laufs, auch Vergleich und Judges). Grund: unter
ZDR lief GPT-6 Luna nur über Azure (Hänger bis Minuten, 429-Wellen); ohne ZDR
landet es direkt bei OpenAI, DeepSeek bei den schnellsten US-Hostern.
Die 429-Sperre (`agent_provider_limits.ProviderCooldowns`) schlüsselt deshalb
auch nach der Provider-Route: ein 429 auf dem ZDR-Weg eines Google-Chats sperrt
das Modell nicht für alle anderen Chats.
Datenschutz/AGB/About beschreiben das, die Landing-Zeile zu ZDR ist entfernt.

**Tombstones aus der ZDR-Zeit (2026-10-08 bis 2026-10-17):** Unter
`provider.zdr=true` scheiterte ein Modell ohne ZDR-Endpunkt mit
`404 No endpoints found matching your data policy`.
`cfg.ZDR_UNAVAILABLE_MODEL_IDS` (`gpt-3.5-turbo`, `chat-latest`,
`gemini-3.1-flash-lite-preview`, `muse-spark-1.3`) fließt in
`REMOVED_MODEL_IDS`: der Firestore-Load entfernt sie aus Providerlisten und
Premium, gespeicherte Free-Defaults/Presets/Judges/Chat-Memory/Watches fallen
auf das Familien-Default zurück, `_consensus_engine_available` verwirft
Familien-Aliasse auf ein stillgelegtes Modell, und `/agent/models` listet sie
nicht. Eine im Browser gespeicherte Auswahl findet keine Option mehr
(`setPickerToValue` bzw. `agent-chat.js selection()`) und bleibt beim
gerenderten Default; `/ask_*` lehnt die alte ID mit 400 ab.
`tests/test_zdr_unavailable_models.py` hält das fest; wieder aufnehmen erst
nach einem echten Aufruf mit dem heutigen Routing. Prüfung neuer Modelle: ein
echter Aufruf mit `provider_routing()` (`scripts/model_release_check.py probe`).

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
  dieselbe Policy. Feste Extraktions-Tasks behalten ihre Werte (die früheren
  SEO-Review-/Publisher-Zeilen sind seit 2026-10-04 entfernt).
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
als „Former Publisher pages“ die vom entfernten Scheduled Publisher erzeugten
Legacy-Weekly-Watch-Seiten (`model_tier=free`) mit Link, Lauf-/Indexstatus,
„Pause watch“/„Resume watch“ je Zeile, „Pause all watches“ und sofortiger
Admin-Löschaktion; die frühere Publisher-Konfiguration ist entfernt. Der
SEO-Tab ist der SEO-Puls (§4 „SEO-Puls“). Der separate
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
  Spätere Pushes wiederholen nur die schnellen Prüfungen. Nachts (02:17 UTC)
  läuft `browser-and-rules` auf `main` in eigener Concurrency-Gruppe; der
  eigene Job `dependency-audit` (pip-audit) läuft bei Push/PR und nachts.
  Python aus `.python-version`, Node 24, Java 21 und Demo-Projekt sind
  festgelegt; kein Produktcredential nötig.
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
`cleanup_expired_pending` und `cleanup_revoked_shares` (plus
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

**SEO-Puls** (`seo-pulse-scheduler`, nur Produktion) prüft alle 15 Minuten die
Fälligkeit (montags 09:00 Europe/Berlin, DST-fest über `zoneinfo`). Der erste
Tick nach einem Deploy setzt nur `next_run_at`. Ein transaktionaler
15-Minuten-Lease in `app_config/seo_pulse` verhindert Doppelläufe; der Abschluss
schreibt Bericht, nächsten Termin und gibt den Lease frei, auch bei
Search-Console-Fehlern. Die synchrone Arbeit läuft per `asyncio.to_thread`
außerhalb des Event-Loops. Details §4 „SEO-Puls“.

**Consensus Watch** läuft als eigener asyncio-Lifespan-Task alle 30 Minuten;
seit 2026-10-20 (Apple-Audit J5) schläft er nur bis zur nächsten fälligen
Watch (`watch_scheduler.next_tick_seconds`: ein Read über
`watch_service.earliest_next_run_at` ohne Retries mit 3 s Frist, mindestens
`MIN_TICK_SECONDS` = 30 s, höchstens 30 min; eine Watch, die erst während
eines langen Ticks fällig wurde (`scanned_at` = Beginn des Ticks), läuft im
nächsten kurzen Tick; eine schon beim Scan fällige und danach noch fällige
Watch wartet den normalen Takt ab statt einer Dauerschleife), damit „Next
check 09:00“ um 09:00 läuft.
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
**Watch-Bild (`watch_images.py`, seit 2026-10-11; Logos + Symbol seit
2026-10-12):** ein echtes Bild aus den Quellen oder keins — kein KI-Bild, keine
Stockfoto-Suche, kein Platzhalter, kein Logo eines Shops oder Verlags. Zweck
ist das Wiedererkennen einer Watch auf einen Blick. Nach jedem erfolgreichen
Check (`watch_scheduler` nach `complete_watch_run`) und beim Anlegen aus einer
fertigen Antwort (Router nach `create_watch`, nicht bei Query-first) startet im
Hintergrund (ein Daemon-Thread zur Zeit, 8 offene Aufträge, aus in
Unit-/E2E-/Mock-Modus) ein Versuch (`refresh_for_watch`). Fehlt der Watch noch
ein Symbol oder die Seitenwahl, fragt er zuerst **einmal pro Watch** den
günstigen Judge (`watch_scheduler.pick_visual` →
`consensus_engine.pick_watch_visual`, Free-Stufe, Structured Output, ohne
Websuche): `symbol` aus der festen Liste `watch_symbols.SYMBOLS` (Enum) und
`sites` = höchstens zwei der übergebenen Quell-Domains, die dem Gegenstand der
Frage selbst gehören (nie eine Seite, die nur berichtet, vergleicht oder
verkauft); was nicht in den Listen steht, fällt weg. Das Symbol steht danach
fest (`watch.symbol`), die Seitenwahl reist als `image.sites` mit (auch `[]`),
damit spätere Checks nicht erneut fragen — außer der Judge sah gar keine
Domain (Watch ohne Quellen): dann gilt nur das Symbol und ein späterer Check
mit Quellen fragt erneut. Fällt der Judge aus, gilt für Logos die Namensregel
(`named_sites`: der Domainname, z. B. `hs-hannover` aus
`karriere.hs-hannover.de`, ist ein Name aus Frage/Ziel; IP-Adressen haben
keinen) und das Dashboard zeigt das Standardsymbol; nach drei Fehlschlägen
(`visual_tries`) wird er für diese Watch nicht mehr gefragt und `symbol` =
Standardsymbol. Dann werden bis zu 5 Quellen-URLs (mehrfach zitierte
zuerst, ein Host pro Runde; consens.io selbst, Reddit/YouTube/X/Facebook/
Instagram/TikTok/LinkedIn/Google/GitHub/Medium/Quora/Stack Overflow/HN und PDFs
übersprungen, auch wenn eine Weiterleitung dort endet; eine Weiterleitung zählt
als ihre Zielseite) über
`source_documents.pinned_target` abgerufen (DNS-gepinnt, nur öffentliche IPs,
Redirects je Hop neu geprüft, Seiten ≤ 2 MB, Bilder ≤ 5 MB, Icons ≤ 1 MB, 6 s je
Abruf). Drei Stufen mit je eigenem Zeitbudget (Seiten + Gegenstand 25 s, Logos
15 s, Artikelbilder 15 s; bis zum Abbruch gesammelte Artikel bleiben), Seiten
werden nur einmal gelesen: (1) **Gegenstand** (`kind="item"`) — eine Seite, die
sich selbst als schema.org Product/Vehicle/Book/(echte) Event/Unterkunft
ausweist (JSON-LD/Microdata, sonst `og:type` product/item) und deren Name zur
Frage + Ziel passt (`Question`/`match_score`): kein Zubehör-/Merch-Wort, das die
Frage nicht nennt (Socken, Hülle, Kabel …); keine andere Zahl am selben Platz
(„Pro 3“ statt „Pro 4“, „iPhone 16“ statt „17“ — Größen/Speicher an anderer
Stelle stören nicht); und der Name deckt ≥ 75 % der Namen aus der Frage ab oder
enthält drei Wörter der Frage am Stück (trennt Schwestermodelle). Das
Seitenbild (`og:image`) erbt nur ein eigenständiger Gegenstand (oberste Ebene,
`@graph`, `mainEntity`, Microdata ohne äußeres itemscope) auf einer Seite, die
kein Artikel ist — nie einer aus Rezension, Liste oder Video. Die erste Stufe
gewinnt auf jeder Quelle. (2) **Logo** (`kind="logo"`) — sonst das App-Icon
der gewählten Seiten (Judge oder Namensregel): Startseite der Domain (sonst die
zitierte Seite) lesen, `apple-touch-icon`/`fluid-icon` (größtes zuerst), große
PNG-Icons, `/apple-touch-icon.png`, zuletzt `.ico` (`page_icons`; SVG und
Masken nie, ≤ 3 Icon-Abrufe je Seite). Ein Icon braucht ≥ 64 px
(`make_logo`); ein `.ico` wird nur geöffnet, wenn die echten Maße jedes
Eintrags (PNG-IHDR bzw. BMP-Kopf, `_ico_fits`) ≤ 1024 px sind — Pillow
dekodiert `.ico` schon in `Image.open`, und das Verzeichnis darf lügen. Füllt
das Icon die Fläche, füllt es die 144-px-Kachel; ein Zeichen auf
Durchsicht steht verkleinert auf Weiß bzw. — wenn es hell ist — auf Dunkel; eine
leere Fläche ist kein Logo. Bis zu zwei Kacheln werden mit abgerundeten Ecken
und Lücke zu einem WebP mit Durchsicht (`compose_logos`, ≤ 304 × 144 px).
Logos stehen vor Artikeln, weil man das Logo dessen, um den es geht, sicherer
wiedererkennt als die Teilen-Grafik eines Verlags. (3) **Thema**
(`kind="article"`) — sonst ein Artikel (schema.org Article/NewsArticle/
BlogPosting …, sonst `og:type` article), dessen Überschrift passt (≥ 3
gemeinsame Wörter oder 2 bei kurzer Überschrift, und mindestens ein gemeinsames
Wort ist ein Name aus der Frage: Großbuchstabe außer am Satzanfang oder Ziffer,
`entity_tokens`); genommen wird das Vorschaubild, das der Verlag fürs Teilen
festlegt (`og:image` zuerst), ohne Pfade mit default/fallback/generic. Das Bild
muss ein Foto sein (≥ 160 px, Seitenverhältnis ≤ 3:1, kein Logo-/Platzhalter-
Pfad, nicht flächig) und wird als WebP neu kodiert: nur die Decoder JPEG/PNG/
WebP/GIF, JPEG per `draft()` gleich verkleinert dekodiert (6300² ≈ 4 MB statt
~475 MB), andere Formate nur bis 8 MP (≈ 32 MB), EXIF-Ausrichtung nur bei JPEG. Drei Versuche, in denen
Seiten gelesen, aber nichts Passendes gefunden wurde (`attempts`), beenden die
Suche; Versuche ohne eine einzige lesbare Seite (Bot-Sperre, Timeout) zählen
nur in `tries` (Deckel 8). Beide Zähler gelten nur für die aktuelle Suche
(`image.version` = `SEARCH_VERSION`, 2 = Logos): kommt eine Stufe dazu, beginnt
die Zählung neu. Bestehende, auch pausierte Watches rüstet
`scripts/backfill_watch_visuals.py` nach (Trockenlauf ruft Judge und Seiten,
schreibt nichts; `--apply` = Prod-Write). Ein gefundenes oder entferntes Bild bleibt. Die
Speicher-Transaktion liest die Watch und den Konto-Tombstone, damit eine
gelöschte Watch kein Bild zurückbekommt. Ausgeliefert wird nur von consens.io
(`GET /api/watch/{id}/image/{token}`, Prozess-LRU mit Generationszähler gegen
ein Entfernen während des Reads; ein falsches Token zu einem bekannten Bild
kostet keinen Read, eine unbekannte Watch-ID genau einen), die Quelle sieht
keine Besucher-IP. Die gecachte Watch-Seite blendet ein inzwischen entferntes
Bild per `error`-Handler aus. Das Bild
steht im Dashboard und im Kopf der Watch-Seite als 3:2-Kachel (Gegenstand ganz
auf Weiß, Artikelfoto füllend) bzw. als rahmenlose Logo-Kacheln, verlinkt auf
seine Quelle (bei Logos die erste Domain, Titel „Logo: a.com, b.com“), aber nie
in OG-Karte, `og:image` oder JSON-LD. Ohne Bild zeigt nur das Dashboard das
Symbol (`watch.symbol` in `_serialize`, `watch_symbols.clean_symbol`); die
Zeichnungen liegen unter denselben Namen in `watch-dashboard.js`
(`SYMBOL_ICONS`, ein Test hält beide Listen gleich).
**Tages-Scan (`watch_probe.py`):** aktive Owner-Watches **mit Ziel** und Intervall weekly/
monthly tragen `next_probe_at` (Watches ohne Ziel halten strikt ihren Wochentag;
eine Zieländerung berechnet `next_probe_at` neu) (Index `status`+`next_probe_at`). Im Watch-Tick
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
`_why_html`, `_question_html`, `_answer_html`, `_button_html`, `_shell_html`
inkl. Preheader für die Inbox-Vorschau); eine abgeschlossene Watch schickt
genau eine Ziel-erreicht-Mail (sie passiert das Pause-Gate der Zustellung als
einzige; Betreff „Reached: <Ziel> · <Frage>“, ein „Why“ mit Grund und Quellen,
Label „You were waiting for“); lange Fragen werden auf ~200 Zeichen am Wortende
gekürzt und verlinken auf die Seite, Betreffe enden ebenfalls an einem Wort.
Der Textteil bleibt bewusst ASCII (`_ascii`), sonst landet die
komplette Plaintext-Hälfte in Base64 und URLs sind nicht mehr klickbar. Wo er
doch ASCII verlässt (deutsche Mails, Umlaute in Fragen), setzt
`_base_message` quoted-printable fest. Feste Wörter laufen über das Wörterbuch
(`_t`, siehe „Deutsch für deutsche Leser“).
**Aussehen der Mails (seit 2026-10-20, Apple-Audit K2/K8):** Jede Mail sieht aus
wie die App: die Tokens aus `public-tokens.css` als feste Farben
(`mailer.GROUND/INK/INK_SOFT/MUTED/BORDER/RAISE`, `MAIL_PALETTE`), Wortmarke
„consens.io“ oben, Labels in Satzschreibung, ein schwarzer Pill-Knopf als
Tabellen-Button (Outlook), keine farbigen Randstriche, Footer-Links mit eigener
Farbe. `<head>` trägt `lang`, `viewport`, `color-scheme`/`supported-color-schemes`,
`<title>` und `MAIL_DARK_CSS`: ein `@media (prefers-color-scheme: dark)`-Block
(plus `[data-ogsc]`/`[data-ogsb]` für Outlook.com), der über die Rollen-Klassen
`cx-bg|ink|soft|muted|raise|line|line-soft|btn|btn-label` die dunklen App-Tokens
setzt. Neue Elemente bekommen Inline-Stil UND die passende `cx-*`-Klasse. Der
Preheader endet in unsichtbaren Füllzeichen (`_PREHEADER_FILL`), damit die
Inbox-Vorschau nicht die ersten Zeilen der Mail wiederholt.
**Die Antwort in Benachrichtigungen (Apple-Audit K1):** Every-run- und
Ziel-erreicht-Mail sowie Telegram (every_run und condition) zeigen die Antwort
gerendert, nie als escaptes Markdown. `app/services/notification_markdown.py`
nimmt dafür das HTML der öffentlichen Seiten (`public_markdown.render_public_markdown`,
markdown-it ohne HTML + nh3, vorher `strip_chat_framing`) und schreibt es neu:
`answer_mail_html(md, palette=mailer.MAIL_PALETTE, sources=…)` mit Inline-Stilen
(Überschriften, Listen, Tabellen in einer Scrollbox, Links, Code) und
`cx-*`-Klassen; `answer_plain` für den Textteil (Absätze, `- `-Listen,
`a | b`-Zeilen, „Text (URL)“); `answer_telegram(md, limit=…)` im erlaubten
Telegram-Subset (b, i, s, code, a; Listen als „•“-Zeilen), innerhalb eines
Markup-Budgets, das nie in einem Tag schneidet. `[S1]`-Verweise werden in der
Mail zu kleinen Links auf die Quelle der Version (`get_watch_version(...).sources`,
`notification_delivery._watch_version_answer`), in Text und Telegram entfallen sie;
Bilder aus Antworten werden nie übernommen (eine Modell-URL lädt nie im Mailprogramm).
Telegram sendet dieselbe Struktur und dieselben Wörter als HTML
(`parse_mode=HTML`, keine Emojis); Frage und Antwort stehen in
`<blockquote expandable>`. Die Antwort bekommt nur den Platz, den die übrigen
Blöcke unter Telegrams 4.096 sichtbaren Zeichen lassen (unter 200: keine
Antwort, die Seite hat sie); `telegram_notifier.send_bot_message` kürzt HTML
nur noch über `clip_html` (zählt sichtbare Zeichen in UTF-16 wie Telegram,
schneidet nie in Tag oder Entity, schließt offene Tags, „…“) statt die
Auszeichnung roh bei 4.096 abzuschneiden. Wird die Auszeichnung trotzdem
abgelehnt (HTTP 400), geht dieselbe Nachricht als Klartext raus, Links als
„Titel (URL)“ (`_notification_text(..., plain=True)`): der Platz wird dann am
Klartext gemessen (`telegram_notifier.plain_length`), die Antwort bekommt nur
den Rest, die Meldungsblöcke werden notfalls gekürzt, die Frage unten nie
(Nachprüfung 2 N3; vorher schnitt `clip_plain` sie ab). Knöpfe je Art: „Open watch“ (private
Watches über `mailer.owner_page_path`, also `/app?next=/s/<id>`) plus
„Mute 24h“/„Pause“; eine pausierte Watch bekommt „Resume watch“ (`wr:`), eine
erreichte nur „Open watch“. **Bestätigung am Ort der Aktion (K7):** „Pause“
ersetzt per `editMessageReplyMarkup` die Knöpfe der Meldung durch
„Confirm pause“/„Cancel“; „Confirm pause“ pausiert und schreibt per
`editMessageText` (Text + `entities` der Meldung, neue Statuszeile
`STATUS_PAUSED`) und „Resume watch“ an dieselbe Meldung; „Resume watch“ setzt
`STATUS_RESUMED`. Lehnt Telegram die Textänderung ab, werden nur die Knöpfe
getauscht; ohne zugängliche Meldung kommt wie früher eine Rückfrage, jetzt mit
der Frage der Watch. `/start` ohne Token verweist auf „Watches → Connect
Telegram“.
**Links in Mails (seit 2026-10-19):** Ein Link aus einer Mail fragt nur, der
Button auf der geöffneten Seite handelt. Mail-Scanner, Linkvorschauen und
Link-Checker öffnen jeden Link einer Nachricht (auch per HEAD); vorher
pausierte schon das bloße Öffnen von `/watch/unsubscribe` die Watch und
bestätigte `/watch/follow/confirm` einen Double-Opt-in ohne den Empfänger.
Betroffen sind alle Mail-Links: `/watch/unsubscribe`, `/watch/resume`
(seit 2026-10-20), `/watch/brief/unsubscribe`, `/watch/follow/confirm|unsubscribe`
und `/topic-follow/confirm|unsubscribe`. GET (und HEAD) prüft nur den Token
(`parse_unsubscribe_token`, `parse_resume_token`, `parse_brief_unsubscribe_token`,
`watch_followers.parse_follow_confirm_token|parse_follow_unsubscribe_token`,
`topics.parse_follow_token`), zeigt Fehler sofort und sonst ein Formular,
das per POST auf dieselbe URL samt Token geht; nur der POST schreibt.
**Die Seiten dahinter (Apple-Audit K3)** sind eine Jinja-Vorlage im Stil der
öffentlichen Seiten: `templates/notice.html` über `app/core/notice_page.notice_page(...)`
(public-pages/public-shell-CSS, Navigation, Footer, `no-store`, noindex). Sie
nennen, worum es geht (Frage der Watch über `watch_service.watch_link_view`,
Frage der Seite, Topic-Titel) und bieten den nächsten Schritt: nach dem
Pausieren „Resume watch“ (eigener Token `make_resume_token`, Payload `rs: 1`;
ein Pause-Link setzt nie fort, ein Resume-Link pausiert nie) und „Open Watches“.
Eine schon pausierte Watch zeigt beim Öffnen des Pause-Links ihren Zustand mit
„Resume watch“; eine erreichte Watch bleibt „resolved“ (der Pause-Link setzt
sie nicht mehr auf „paused“). `POST /watch/resume` (`watch_service.resume_from_token`)
setzt unter den Grenzen des Owners fort (`update_watch` mit seiner Stufe; voll →
„No free watch slot“, erreichtes Ziel → nur in der App). Die „Paused“-Mail nach
drei Fehlern (K6) hat „Resume watch“ als Hauptknopf und keinen Pausier-Link
mehr; ihr List-Unsubscribe-Header bleibt. Der Morning Brief (K5) führt auf
`/app/watches`, erreichte Ziele stehen als eigene Zeile „Reached. …“, Zeiten in
der Zeitzone des Briefs ohne Namen, andere als Stadt („Los Angeles time“).
Jede Mail, deren Text einen Abmeldelink zeigt (Change, Every-run, Pause,
Follower, Topic, Morning Brief), trägt dazu `List-Unsubscribe: <URL>` und
`List-Unsubscribe-Post: List-Unsubscribe=One-Click` (RFC 2369/8058): Gmail,
Apple Mail und Outlook zeigen dann ihren eigenen Abmelde-Knopf und schicken
genau diesen POST, beantwortet mit 200 ohne Weiterleitung. Die
„Resolved“-Mail und Bestätigungsmails haben keinen Header (kein Link im
Text, noch keine Liste). Der Header steht als eine Zeile im Kopf
(`mailer._OneLineHeader`): Pythons `email`-Paket faltet sonst jeden Wert über
78 Zeichen ohne Leerzeichen in RFC-2047-Wörter (`=?utf-8?q?=3Chttps…`), in
denen kein Mailprogramm die URL mehr findet.
**Watch-Seiten** (`templates/watch_share.html`, seit 2026-10-10) sind eine
ruhige Spalte mit genau drei Aussagen; ihre Teile liegen seit 2026-10-15 als
Makros in `templates/partials/check_page.html` und bauen auch die Topic-Seiten,
die geteilten Skripte in `static/js/check-page.js`: (1) eine Zustandszeile
(`app/services/check_page.state_view`, in `routers/share.py` als
`_watch_state_view` eingebunden: „Unchanged since …“, „Changed on …“
mit Satz und Belegen, „Resolved on …“, „Waiting for the first check“, „Answer
from …“ für `?version=` und „Latest version unavailable“), darunter Ziel,
„Latest check: …“ für einen nicht geltenden neuesten Check und eine Faktenzeile
(Checks seit, nächster Check bzw. pausiert); (2) die Antwort mit Quellen (ab 6
eingeklappt); (3) eine Zeitleiste (`history_view.timeline`): der neueste Check,
jede Bewegung und der Start stehen einzeln, ruhige Checks dazwischen klappen zu
„N checks, no change“ zusammen (Anker `#watch-run-check-N` öffnen die Gruppe).
Die Agreement-Kurve steht nur auf breiten Bildschirmen über der Zeitleiste
(`.wp-chart`, unter 700 px ausgeblendet). Scoreboard, Modell-Chips,
Consensus/Differences-Umschalter, Position Map, Direction Shift, Zitierblock
und „Related questions“ gibt es dort bewusst nicht mehr; die Modell-
Unterschiede liegen zugeklappt am Ende („How the N models compared“). Lange
Fragen klappen auf drei Zeilen ein (`#shareQuestion` + `#shareQuestionMore`).
Hat die Watch ein Bild (`watch_page.image`), steht es rechts neben der Frage
(`.wp-head.has-image`); unter 700 px rückt es neben die Kicker-Zeile, damit die
Frage die volle Breite behält.
**Wege zu den Quellen (seit 2026-10-12, `source_links.py`):** Wer ein Thema
beobachtet, will selbst nachsehen. Zwischen Zustand und Antwort stehen deshalb
bis zu vier **Direktlinks** (`watch_key_links`, `.wp-links`: Kacheln mit
Favicon, Seitentitel ohne angehängten Seitennamen, Domain, ↗; zwei Spalten,
mobil eine): je Domain die Quelle, die als Ziel am meisten taugt (tiefe direkte
Seite mit echtem Titel > mit Titel aus dem Pfad > Startseite >
Grounding-Weiterleitung), vorn die
Seiten, die die Antwort beim Namen nennt, sonst nur tiefe direkte Seiten mit
Titel (die Stellenanzeige, die Produktseite). Im Antworttext wird die erste
Nennung je Quelle zum Link (`site_mentions` → `render_public_markdown(…,
site_links=…)`, `.wp-ref`: Favicon über `/api/topics/favicon`, kräftig, leise
unterstrichen, neuer Tab): ausgeschriebene Domain immer, Site-Name nur wie ein
Name (groß, mit Ziffer oder Binnenmajuskel, nicht in einer Wortkette wie
„Adidas-Größe“, nicht wenn er ein gewöhnliches Wort ist wie „billiger“,
„Zeit“), nur in Textknoten außerhalb von Links/Code und nur auf Seiten mit
echter Adresse (keine Weiterleitung). Ausgehende Links, die die Antwort selbst
setzt, bekommen denselben Stil. Das ist Navigation, kein Satz-für-Satz-Beleg:
die Synthese schreibt bewusst keine S-Verweise (seit 2026-09-11), ein Name,
der zu genau dieser Seite führt, kann nicht falsch zitieren. Die vollständige
Quellenliste bleibt am Ende; normale Share-Seiten bleiben unverändert. `nh3`
erlaubt dafür `class`/`target` an `a` und `class`/`loading` an `img` — Modell-
Markdown kann keine Attribute setzen (`html=False`). Ist ein Titel bloß die
Domain (aufgelöste Weiterleitung), zeigt die Kachel einen Titel aus dem
sprechenden Pfad („Adidas adizero adios pro 4“; lange IDs/Hashes fallen weg).
**Echte Adressen (`source_redirects.py`):** Geminis Grounding-Quellen sind
signierte Weiterleitungen über `vertexaisearch.cloud.google.com`, meist nur mit
der Domain als Titel, und sie verfallen (Stichprobe 2026-10-12: Juli → 404,
Oktober → 302). `watch_scheduler.execute_watch` ersetzt sie deshalb direkt nach
dem Sammeln der Quellen, vor Judge und Ziel-Bewertung, durch ihr Ziel: je
Weiterleitung eine Anfrage an den festen Google-Host, nur der
`Location`-Header (dem Ziel wird nicht gefolgt), parallel mit 10 s
Gesamtbudget; Unauflösbares bleibt stehen. Weil die Weiterleitungen pro Lauf
neu signiert sind, galten Gemini-Quellen bisher bei jedem Check als „neu
gesehen“; aufgelöste Adressen wiederholen sich und machen `seen_before` im
Change-Judge erst verlässlich. `scripts/backfill_watch_links.py` löst in allen
Checks, im Ausgangs-Share und am Watch-Dokument auf, was noch auflösbar ist, und
setzt die Dashboard-Links (Trockenlauf ohne Writes, `--apply` = Prod-Write).
Was Google eindeutig nicht mehr kennt (404/410 — Zeitüberschreitung, 429, 5xx
zählen nicht, `source_redirects.expired_urls`), ist ein toter Link und wird
dort entfernt (`drop_urls`, auch aus Belegen und History-Punkten); die Nummern
entfernter Quellen stehen als `expired_source_ids` am Check bzw. Share,
`public_share_payload`/`_watch_version_payload` reichen sie als
`expired_sources` an `render_public_markdown(excluded_sources=…)`, damit alte
`[S3]`-Verweise wegfallen statt als nackter Text zu stehen. Direktlinks nehmen
nie eine Weiterleitung auf (sie verrät ihr Ziel nicht und verfällt).
**Öffentliche Seiten nach dem Apple-Audit (seit 2026-10-20):**
*Zustand ehrlich:* `check_page.state_view` kennt pausierte Watches
(`PAUSED_STATUSES`; Seite übergibt `status`/`last_run`): Ton `paused`, grauer
Punkt, „Paused · last checked Oct 1“, Kicker „Watch · paused“ (Max: nicht neu
starten, ehrlich zeigen). `check_page.watch_summary(status, points, …)` liefert
dieselbe Kopfzeile für Orte, die auf die Seite zeigen: Zeilen in `/questions`
(`share_snapshots._hub_watch_state`, liest die neueste öffentliche Watch je
Share und ihre `history_points`, längere Reihen aus der History; je
Hub-Cache-Eintrag, 15 min) und die Vorschaukarte (`og_image.watch_card_png`:
„Watch · …“ über der Frage, Modellzahl, kein Score). Watch-Zeilen im Hub zeigen
kein Score/Modell/Widerspruch des Ausgangs-Snapshots mehr; „tracked over time“
zählt nur aktive Watches. *Keine Selbstzitate:* `source_links.is_own_page` /
`without_own_pages` (consens.io samt Subdomains): Direktlinks, Namen im Text und
Quellenliste lassen eigene Seiten weg, ihre `[S#]` fallen wie abgelaufene
Weiterleitungen (`routers/share.py`, Topic-Liste über `_sources_view`); der
Watch-Judge bekommt sie gar nicht erst (`watch_scheduler.execute_watch`,
`evidence`), gespeichert bleiben sie, damit ihre Verweise auflösbar bleiben.
*Direktlinks:* gleiche Titel nur einmal, Signaturen hinter `-|–—·:\/` inkl.
Produktnamen (`_SITE_ALIASES`: „- ChatGPT“ auf openai.com) und kurzer Marken am
Namensanfang („- Amp“ auf ampcode.com) fallen weg; am Handy auf allen
`.wp-shell`-Seiten eine Wischreihe, am Desktop nimmt eine ungerade letzte Kachel
die ganze Zeile. *Modellvergleich:* `check_page.named_differences` ersetzt die
„Model A/B/C“ alter Judge-Texte durch die Familien der Positionen (Beleg:
eine Haltung, die mit so vielen Buchstaben beginnt, wie die Position Familien
nennt, sagt „diese Buchstaben sind diese Familien“ – als Menge, nie nach
Listenreihenfolge; `_judge_letter_blocks` schneidet die Belege, ein Label wird
nur ersetzt, wenn es ganze Blöcke abdeckt; Widersprüche lassen den Buchstaben
stehen) und lässt die
Familienzeile weg, wenn der Satz sie schon nennt; `consulted_models_view`
liefert `display` ohne doppelte Familie („Gemini 3.5 Flash-Lite“);
`consensus_model_view` löst gespeicherte Modell-IDs (`gpt-5.6-luna`) zum Namen
auf. *Gefaltet vom Server:* lange Fragen (`is-clamped`, wirkt nur unter
`@media (scripting: enabled)`; der Link sitzt auf der dritten Zeile und
verschiebt nichts) und Quellenlisten (`is-collapsed[ is-short]`) kommen
gefaltet an; `share.html` nutzt dafür jetzt auch `check-page.js` statt eigener
Inline-Kopien. *Eine Disclosure:* `.wp-disclosure`/`.wp-disclosure-toggle` +
`.wp-chevron` für ruhige Checks, Quellenliste und Modellvergleich;
`check-page.js` animiert die Höhe (WAAPI, ~0,5 s, ohne bei reduzierter
Bewegung), setzt den Fokus nach „Show all sources“ auf die erste neue Quelle und
hinterlegt den Ziel-Check eines Sprungs kurz (`.is-flash`). Fehlende
Website-Icons (`.site-icon`) behalten ihr Feld (Globus, `.is-missing`) und
blenden weich ein; im Dunkelmodus auf heller Plakette. Kurve: Änderungen
amber und größer, Checks ohne Score als hohle Marke auf der Achse. Zeitleiste:
der Satz des Zustandskastens steht im zugehörigen Eintrag nicht noch einmal
(`history(…, shown_text=…)`). Lesespalte 66ch, Antwort-Überschriften 18/16 px,
Tippziele unter 700 px 44 px. Titel kürzt `routers/share.clip_words` an der
Wortgrenze (`<title>` 70, `og:`/`twitter:title` 110). `render_public_markdown`
setzt eine ganze Gruppe von Verweisen hinter den Satzpunkt („Claim.[1][2]“,
vorher „Claim [1].[2]“), ein „!“ davor wird escaped (sonst Bild-Syntax).
Geteilte Antworten ohne Watch: `create_share_from_pending` startet nach dem
Anlegen `share_snapshots.schedule_share_cleanup` (Daemon-Thread, aus in
Unit-/E2E-/Mock-Modus), das `clean_share_sources` ausführt — aufgelöste
Adressen ersetzen die Quellen; danach wird der Share-Cache invalidiert. Der Teilen-Klick wartet nie auf Google.
`scripts/backfill_share_links.py` bereinigt bestehende Shares mit
`check_expired=True` (Trockenlauf ohne Writes, `--apply` = Prod-Write).
Die normale Watch-URL rendert serverseitig die **geltende** Vollversion
(`accepted_run_id`, sonst die neueste) über dem unveränderten
Share-Baseline-Dokument; `?version=<run_id>` öffnet eine unveränderliche (aber
nur kurz gecachte, widerrufbare) historische Vollversion und
`?version=original` den Ausgangs-Consensus. Shared Pages ohne Watch behalten
`share.html` mit ihrem bisherigen Snapshot-Verhalten. Ein Backend-
`display_version` ist die einzige Quelle für Consensus, Differences, Modelle,
Quellen, Answer-Zeit und Citation; kompakte History-Metadaten werden nie in den
Share-Snapshot gemischt. Fehlt die aktuelle Vollversion (auch bei
Legacy-History), sagt die Zustandszeile das und die Seite rendert den
Original-Snapshot konsistent.
Die **Position Map** (`opinion_map`) wird weiter pro Check gespeichert, seit
2026-10-15 aber auf keiner Seite mehr gezeigt (Topic-Seiten folgen dem
Watch-Bauplan): statt einer universellen Ja/Nein-Achse pro
frage-spezifischer Dimension benannte Positionen samt Modellen und ein
gemeinsamer **Direction Shift**. Die Berechnung ist deterministisch aus dem ohnehin
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
gleicher `WATCH_UNSUBSCRIBE_SECRET`) deaktiviert nur den Brief (per POST, siehe
„Links in Mails“).
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
diese Indizes beim ersten Schreibzugriff. Der erste planmäßige Watch-Lauf
gilt ausdrücklich als Baseline (kein Changes-only-Alert durch den vorher leeren
Text), schreibt zugleich die erste immutable History-Version und füllt die
Share-Baseline. Condition- und Every-run-Regeln dürfen beim ersten Lauf bereits
auslösen; vor diesem Lauf zeigt die Watch-Seite transparent den ausstehenden
ersten Check statt eines leeren Consensus-Panels.

---

**Material-Vertrag (seit 2026-10-20):** `tests/test_material_tokens.py` rechnet
die Oberflächen- und Textstufen in OKLab/WCAG nach (gleiche Stufe hell/dunkel,
gespreizte Graustufen, `--ink-3` ≥ 4,5:1, Ampel textsicher, Marken auf dem
Ampel-Farbton) und hält die Bauteile: ein Hover-Token statt Transparenz, ein
gefüllter Knopf, gewählte Option in Tinte, ein Composer-Material, ein
Quellen-Bauteil, Schrift ≥ 12 px (Lint über alle App- und öffentlichen
Stylesheets außer Admin), ein Chevron, ein Feld-Fokus, Umschalter ohne
Fettsprung, eine Sidebar-Zeile, Gleiten mit der Leiste, bloßer Menüknopf am
Handy.

### Deutsch für deutsche Leser (i18n, seit 2026-10-22)

Ausführlich in [`i18n.md`](i18n.md). Die Oberfläche bleibt im Code englisch;
ein Wörterbuch `app/i18n/de/*.json` (Englisch → Deutsch, `page-*.json` und
`mail.json` nur für den Server) übersetzt, was ein Leser sieht:
- **Sprache:** `app/core/i18n_middleware.py` (zwischen `CorrelationMiddleware`
  und `StaticDeliveryMiddleware`): `/de/<Seite>` für `i18n.LOCALIZED_PATHS`
  (Start, About, Privacy, Terms, Imprint, Consensus engine, Model guide,
  Benchmark, Model pulse; Präfix wird vor dem Routing entfernt), sonst Cookie
  `consens_lang`, sonst `Accept-Language`. Deutsche Browser auf englischen
  Adressen lokalisierter Seiten → 302 auf `/de/…`; `?lang=en|de|auto` setzt
  bzw. löscht das Cookie. `request.state.language` trägt die Sprache;
  `/api/`, `/static/`, `/__/`, `/admin`, `/health` und der Google-Callback
  laufen unberührt durch.
- **Server:** jede deutsche HTML-Antwort durch `i18n.translate_html`
  (Läufe aus Text und Inline-Elementen als Ganzes mit Markern `<0>…</0>`,
  sonst stückweise; Platzhalter `{name}` fangen nur ganze Elemente; Attribute, Meta, JSON-LD, `lang`,
  Links auf lokalisierte Seiten, Canonical/hreflang). Ergebnis-Cache per
  Inhalts-Hash. `Content-Language: de`, `Vary: Accept-Language, Cookie`.
- **Browser:** `/i18n/de.<hash>.js` = Wörterbuch + `static/js/i18n.js`, als
  erstes Skript im `<head>` jeder deutschen Seite (nicht in `bundles.json`).
  Ein `MutationObserver` übersetzt alles, was Skripte schreiben; `App.t`,
  `App.lang`, `App.i18n`. `app-text.js` stellt `App.t` auf englischen
  Seiten bereit und formatiert mit `App.format` in `de-DE`.
- **Verträge:** Skripte vergleichen „schon gesetzt?“ gegen
  `window.App.t(text)`, nie gegen rohes Englisch; Selektoren nie auf
  übersetzte Attribute (Tabs: `data-tab`, nicht `data-short`); Modell- und
  Nutzerinhalt trägt `data-i18n-skip` (Markdown-Container setzen es selbst),
  Namen `translate="no"`; mehrdeutige Wörter per `data-i18n-context`
  (`agent freedom|Free`). Einzahl/Mehrzahl als ganze Sätze, nie `"model" + "s"`.
- **Prüfung:** `scripts/i18n.py missing|check` (Vorlagen, Skripte,
  Server-Sätze; seit 2026-10-23 auch Sätze, die Wörter im `${…}` wählen
  und so keinen Eintrag als Ganzes haben, `composed_gaps`; seit 2026-10-24
  auch lesbare Attribute einer Vorlage mit `{% if %}` im Wert, `TAG_IN_VALUE`),
  `tests/test_i18n.py`, `tests/js/i18n.test.mjs`.
- **Mails (seit 2026-10-23):** in der Sprache des Lesers. Konto-Mails
  (Watch, Morning Brief) lesen `users/{uid}.language`
  (`app/services/account_language.py`: `/user_status` schreibt sie nach der
  Antwort per Background-Task, nur bei Änderung, mit Löschsperre; `of` liest
  sie in `notification_delivery`), Follower die Sprache ihres
  Bestätigungsklicks (`language` am Dokument in `watch_followers` bzw.
  `topic_followers`), Bestätigungs- und Registrierungsmails die der Anfrage
  (`i18n_middleware.request_language`, auch für das von der Middleware
  ausgelassene `/api/`). `mailer.py`: `_t`/`_h`/`_N` und `@_localized` am
  `build_*` (Parameter `language`), Sätze in `mail.json`,
  `mailer.brief_date_label` für das Datum des Morning Brief; `i18n.t(...,
  context=)` für mehrdeutige Wörter (`watch schedule|Daily` = Täglich, nicht
  das Preset Alltag). Tests: `tests/test_mail_language.py`.
- **Noch englisch:** Telegram-Nachrichten, Admin, Topic-Inhalte,
  OG-Bilder; vom Server formatierte Daten (`date_display`).

### Was die App sagt: Namen, Schreibstil, Admin-Zahlen (seit 2026-10-20, Apple-Audit H3–H5, H10)

`tests/test_ui_copy.py` prüft jeden sichtbaren Text von `/app`
(`tests/ui_text.py`: Text und lesbare Attribute von `templates/index.html`
sowie die Prosa-Literale aller `/app`-Skripte über einen kleinen
JS-Tokenizer; Konsole, Selektoren, Objekt-Schlüssel und `===`-Vergleiche
zählen nicht):
- **Ein Name: „Chat“** (New chat · Chats · Chat | Watches, auch für Gäste).
  „bookmark“ bleibt interner Name (IDs, Klassen, API-Felder, Server-Schlüssel
  wie „Bookmark limit reached.“, die `showBookmarkSaveError` übersetzt), nie
  ein Wort auf der Seite; „comparison“ benennt nur die Vergleichsmodelle,
  „Consensus“ den Modus, nie das Produkt.
- **Schreibstil:** Sentence case für Titel, Knöpfe, Labels (Eigennamen und
  Funktionsnamen wie Agent, Watch, Morning Brief behalten ihre Großbuchstaben;
  „Privacy Policy“/„Terms of Use“ als Dokumenttitel); „Log in“ als Verb, nie
  „login“/„logout“/„sign in“; „email“; typografisch ’ und ….
- **Keine internen Namen:** kein „Luna“ (das Memory-Modell), keine „judges“,
  „drawers“, kein Build-Hash in Settings (der steht nur im Tooltip des
  GitHub-Zeichens). Die Titel „Differences judge“/„Coverage judge“ sind
  Schlüssel, die `agent-delegation.js` zu „Answer check“ faltet.
- **Tokens und Dollar nur für Admins:** `.admin-only` (Agent-Verbrauchszeile
  `.agent-usage`, Sidebar-Summe, Token je Agent-Zeile, Token-Aufschlüsselung,
  Token-Zahlen im Kontingent-Panel) blendet `style.css` aus, solange
  `body.viewer-is-admin` fehlt; `firebase.js` setzt die Klasse aus
  `/user_status` `is_admin` und nimmt sie beim Logout weg. Nutzertexte sprechen
  von „allowance“ in Prozent („A Consensus run uses about 8%.“, „8% is held
  for a message still running.“, Agent-Absagen „Not enough of today’s
  allowance is left for this step.“).
- **Hilfe** (`#helpModal`, „Help“): sechs Fragen zum heutigen Produkt (eine
  Nachricht, die Marken, Watches, Kontingent, Gedächtnis, Daten).
- **Gäste in Settings:** `#settingsGuestNote` unter dem Kopf (app-ui.js
  `syncSettingsGuestNote`, beim Öffnen und bei `consensio:auth-state`) sagt,
  warum Memory und Schlüssel ausgegraut sind; „Log in“ schließt Settings und
  ruft `App.askToLogIn`. Der Watches-Hinweispunkt erscheint nur für Konten.
- **API-Schlüssel-Test:** `#openrouterFeedback` zeigt ein gezeichnetes Häkchen
  (`.is-valid`, `--agree`) bzw. Kreuz (`.is-invalid`, `--dispute`) mit
  `aria-label`, nie einen Stern; Fehler über `App.userError`.

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
- **Die Frage einer Nachrichtenblase steht in `data-question`, nicht im Text.**
  `.thread-ask-text` und `.thread-history-question-text` tragen seit 2026-10-09
  `dataset.question` (die whitespace-kollabierte Frage). `renderThreadQuestion`
  (Gleichheit, Disclosure-State), die Verlaufs-Idempotenz in
  `consensus-run.js::appendHistoryTurn` und der Reader-Fallback lesen dieses
  Feld, weil eine geprüfte Passage (`passage-check.js`) den `textContent`
  verändert. Wer den Text einer Blase direkt setzt, setzt `dataset.question` mit
  (`clearPendingThreadQuestion` löscht es). Zugehörige `window.App`-Schnitt-
  stellen: `passageCheck.{apply, restore, verdict, from}`, `claimPopover.{open(claim,
  anchor, models, navigation, {spans, sideLabel}), close, attachPreview(span, claim,
  models, {sideLabel}), hidePreview}` (aus `consensus-insights.js`), `agentReview.contextFor`,
  `syncThreadAskClamp`. Globale `.cx-claim`-Schleifen in `consensus-insights.js`
  schließen `.pc-claim` aus, sonst nähme die Highlights-Einstellung den Marken
  auf der Nachricht Rolle und Label.
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
  `window.currentBookmarkShareResultError`,
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
  archiveCurrentExchange/renderStoredTurn/renderStoredTurns/clearHistory/
  turnKey/buildHistoryTurn`; `renderStoredTurns` hängt nur an, siehe
  „Follow-up-Fragen“).
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
- **`window.App.watch.showFeatureNudge(source?)`** wird nach einem erfolgreichen
  Consensus-Final (ohne Argument) und nach einem Agent-Lauf
  (`agent-chat.js offerWatch`, `source = {eligible, question, anchor}`) aufgerufen
  und zeigt den einmaligen, lokal dismissbaren Consensus-Watch-Hinweis nur für
  eingeloggte Nutzer. Consensus startet die Watch per `result_id`, Agent per
  `question` (Anker `#agentWatchAnchor`; geeignet nur: erste Nachricht des Chats
  mit Quellen, weil eine Watch die nackte Frage neu stellt). Zähler (ab 3.
  Lauf) und „dismissed“ sind modusübergreifend;
  `.resetAfterLogout()` leert und schließt die geladene Watch-Ansicht. Die
  Karte `#watchFeatureNudge` liegt als eigene Ebene direkt unter `<body>` (über
  dem fixierten Composer, ohne die Antwort anzuheben), seit 2026-10-20
  `position: absolute` in Seitenkoordinaten: Der Browser scrollt sie mit, und
  `placeWatchFeatureNudge` schreibt nur dort, wo sie im Bild gehalten wird
  (Oberkante, über dem Composer). Fixiert lief sie jedem Scroll ein Bild
  hinterher (Apple-Audit D8).
- **Jedes modale Fenster ist ein nativer `<dialog class="modal">` im
  Top-Layer** (Settings, Help, Feedback, Login, Share/Watch, Early Access,
  Anhang-Vorschau, `App.confirm`). Sie werden nur über
  `window.App.modalDialog.open/close` geschaltet, nie über `style.display` oder
  `hidden` (`dialog.modal[open]` zeigt sie, `user-memory.js` prüft die
  berechnete `display`; beim Schließen bleibt `display` für die Dauer des
  Ausblendens gesetzt, ein Test sollte `open` prüfen). `showModal()` macht
  alles außerhalb inert: Was aus einem Dialog heraus erscheint und kein
  modaler `<dialog>` ist, muss in ihn hinein (so machen es `App.toast` und
  der Tooltip) oder selbst `showModal()` nutzen. Der Hintergrund-Klick braucht
  ein `pointerdown` auf dem Dialog selbst (Audit F5).
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
  Browser still. jsDelivr steht seit 2026-10-15 nicht mehr darin (Marked,
  DOMPurify und KaTeX kommen überall aus `static/vendor`); dazu
  `object-src 'none'` und `base-uri 'self'`. `/app`, `/app/watches`, `/admin`, `/admin/*` und `/topics/*` erzwingen bei `script-src`
  die strict-variante ohne `'unsafe-inline'`; neue Inline-Skripte/-Handler würden
  dort deshalb nicht ausgeführt. `style-src` bleibt vorerst kompatibel.
  Die Middleware arbeitet auf der Header-Liste (`_ResponseHeaders`, seit
  2026-10-17): Ihre Header ersetzen gleichnamige der Route, statt daneben eine
  zweite Kopie zu senden, und mehrere `Set-Cookie` einer Antwort bleiben alle
  erhalten. Eine eigene CSP behält nur `/agent/google/callback` (Nonce).
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
- **SSE-Antworten (seit 2026-10-08)**: neue Streams nutzen `SSE_HEADERS`
  (`no-transform`) und `iter_sse_with_keepalive(..., lead=SSE_PADDING)`; ein
  Test, der den ersten Chunk liest, muss das Padding überspringen. Agent-Frames
  laufen nur über `agent.py::pack` (Nummer + Live-Puffer) und im Browser nur über
  `deliver` in `agent-chat.js` (Dedupe per `App.agentLive.sequence()`); ein
  Handler, der daran vorbei direkt an `streamSSERequest` hängt, rendert bei
  gepuffertem Stream doppelt.
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
- **Touch ist keine Maus (seit 2026-10-20, Apple-Audit F3, F4, F15).** Ein Tipp
  lässt `:hover` auf Touch-Geräten stehen, bis man woanders tippt (der
  Reasoning-Schalter sah danach eingeschaltet aus). Deshalb steht JEDE Regel mit
  `:hover` in `static/css/*.css` (außer `admin*.css`) in genau dieser Kapsel:
  `@media (hover: hover) and (pointer: fine) { … }`. `:focus-visible`,
  `[aria-expanded="true"]`, `.is-open` usw. stehen daneben außerhalb (eine
  gemischte Regel wird geteilt, Werte identisch), damit Tastatur- und
  Offen-Zustände überall gleich aussehen. JS-Hover fragt dieselbe Kapsel ab
  (`consensus-insights.js::canHoverPassages`, seit 2026-10-21; `any-pointer`
  erfüllt auch manches Handy), und ein Fokus, der nicht per Tab kam, zeigt
  keine Hover-Vorschau (§3, Hover-Vorschau). Gegenregeln „A tap leaves :hover
  stuck“ unter `(hover: none)` gibt es nicht mehr. Was auf Touch sichtbar sein
  muss (Chat-Menü „…“, Suche, Faltzeichen), zeigt ein eigener
  `@media (hover: none)`-Block, nie ein Hover. `foundation.css` setzt am
  `:root` `-webkit-tap-highlight-color: transparent` (kein grauer/blauer
  Browser-Blitz; das Drücken ist `--press-scale` aus `base.css`) und
  `text-size-adjust: 100%` (Safari vergrößert im Querformat keine Schrift);
  `variables.css` und `public-tokens.css` importieren es, also gilt es für `/app`
  und jede öffentliche Seite. `tests/js/touch-contract.test.mjs` verbietet
  ungeschützte Hover-Regeln, eine zweite Schreibweise der Kapsel und lokale
  Tap-/Textgrößen-Regeln; der CSS-Leser dafür ist
  `tests/js/helpers/css-rules.mjs` (`parseCss`, `walkRules`, `ancestors`,
  `splitSelectors`).
  **44-px-Trefferflächen (F5):** Unter `@media (pointer: coarse)` bekommt jedes
  kleinere Bedienelement eine unsichtbare Trefferfläche aus einem eigenen
  Pseudo-Element: `.x { position: relative } .x::after { content: ""; position:
  absolute; inset: var(--hit-slop) }`. `--hit-slop` (`foundation.css`) ist
  `min(0px, calc(50% - 22px))`: jede Seite wächst nur so weit, wie das Element
  kleiner als 44 px ist. Gezeichnet bleibt alles gleich groß. Ausnahmen mit
  Begründung im CSS: Senden (beide Pseudos belegt) wird ein 44-px-Kasten mit
  `padding: 4px; margin: -4px; background-clip: content-box`; die Adresse im
  Seitenmenü clippt ihren Text, ihre Fläche ist Padding mit Gegenmargin (die
  Tarifzeile darunter lässt Taps durch); Pillen/Picker mit eigenem
  Ellipsis-Label setzen auf Touch `overflow: visible`; die Quellen-Pille im
  Fließtext reicht 44 px in die Breite, aber nach oben und unten nur über
  ihre eigene Zeile (`--src-ref-line`, per `@property` registriert, `1lh` des
  umgebenden Textes, `source-pill.css`) – 44 px griffen in die Nachbarzeilen
  über deren Wörter, Links und Pillen (Nachprüfung); die Beispielfragen in
  der seitwärts scrollenden Zeile holen sich 6 px Innenraum und geben ihn per
  Margin zurück (`--starters-room` misst deshalb die Margin-Box); Reasoning/
  Anhang stehen auf dem Handy 16 px auseinander. Wo zwei Flächen kollidieren,
  behält ein Feld oder ein Knopf seine Taps („Forgot password?“ nimmt die 39 px
  zwischen Passwortfeld und Knopf). Fließtext-Links (Rechtliches im
  Login-Text) und volle Listenzeilen (Chats 40 px) bleiben bewusst so.
  `tests/e2e/test_touch_targets.py` misst mit `elementFromPoint` bei 320/390 px.
  **Eine Scroll-Sperre (F2):** `foundation.css` hält nur `html` auf
  `overflow: hidden; overscroll-behavior: none` (dessen Overflow ist der des
  Viewports; Rad und Finger, Safari ab 16, bewegen nichts). `body` bleibt
  bewusst ohne eigenen Overflow: sonst würde er zur Scroll-Box, und der
  sticky Composer am Desktop klebte hinter dem Dialog am Threadende statt am
  Fensterrand (Nachprüfung Punkt 4, `test_touch_layers.py` misst ihn). Die
  Sperre gilt, solange eine deckende Ebene
  offen ist – erkannt am Zustand der Ebene selbst, per
  `html:has(:is(dialog:modal, .sidebar.active, body.agent-sidebar-sheet,
  .claim-sheet-backdrop:not([hidden]), .memory-edit-backdrop:not([hidden]),
  .agent-google-overlay:not([hidden]), …))`; es gibt nichts zu halten oder zu
  vergessen. Die früheren Einzelsperren (`html.share-modal-open`,
  `html.memory-edit-open`, `body.agent-google-sheet-open`) sind entfallen. Eine
  neue deckende Ebene kommt in diese eine Liste. Scrollende Ebenen enden an
  ihrem Rand (`overscroll-behavior: contain` an Seitenleiste, Chatliste,
  Satzkarte, Dialog), Dimmflächen ohne Inhalt nehmen keinen Pan
  (`touch-action: none`). `tests/e2e/test_touch_layers.py` prüft Sperre und
  Wischen mit CDP-Touch-Events.
  **Notch und Home-Balken (F12):** `/app` hat `viewport-fit=cover`
  (`templates/index.html`), damit `env(safe-area-inset-*)` überhaupt wirkt
  (vorher rechneten alle Abstände mit 0). Die Ränder halten frei: der Kopf
  (`--app-mobile-header-height` + Padding), der fixierte Composer
  (`padding-bottom: calc(10px | 8px + inset)`, Breite minus linke/rechte
  Insets; sein Grund reicht weiter bis an die Kante), der `body`-Rand im
  Querformat (`max(10px | 6px, inset)` links/rechts), die Schublade (oben,
  unten, links), das Aktivitäts-Sheet, das Modellmenü am Handy, Hinweise
  (`overlays.css`), Antwortleser und Dialoge. Öffentliche Seiten bleiben ohne
  `cover` (Safari rahmt sie im Querformat in der Seitenfarbe).
  `tests/e2e/test_safe_areas.py` simuliert die iPhone-Insets per CDP
  (`Emulation.setSafeAreaInsetsOverride`), hoch- und querformatig.

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
- **Sichtbarer Text**: neuer oder geänderter englischer Text braucht seinen
  Eintrag in `app/i18n/de/*.json` (`scripts/i18n.py missing`, docs/i18n.md);
  `tests/test_i18n.py` bricht sonst ab.
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

„Check contradictions“ (bis 2026-10-15 eine stehende Einstellung
`#sourceCheckSwitch` unter Settings → Runs, Kontoeinstellung `check_sources`)
ist mit der Quellenprüfung entfernt (siehe „Quellenprüfung entfernt“).
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
  Hinweis „Parts of <Name> couldn't be read“ (mehrere: „Parts of n files …“) für die mit dieser Nachricht
  gesendeten Dateien, nur bei echten Leselücken: `agent_files.public_file` filtert seit 2026-10-16
  den immer gleichen Word-Hinweis (`WORD_LIMITS_NOTE`, nur noch im Tool-Ergebnis für das Modell,
  `for_model=True`) und Scan-Seiten-Hinweise eines PDFs ganz ohne Textebene bis 2 MB
  (`NATIVE_PDF_MAX_BYTES`), weil das Modell solche PDFs selbst als Datei liest; übrige Scan-Seiten
  heißen „Pages 2 and 5 are scanned images and were not read.“ (alte OCR-Formulierung wird umgeschrieben),
  Dateiauswahl über `agent_settings.file_ids`; dazu je `document_id` eine
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
  und zeigen dann „Partly read“. Bilder sind seit 2026-10-05 nie „partly read“:
  für Vision-Modelle vollständig, Modelle ohne Bildverständnis bekommen eine eigene
  Prompt-Zeile; `public_file` und der Chip filtern den alten Bild-Hinweis älterer Uploads.

Bytes liegen im privaten GCS-Bucket `AGENT_FILES_BUCKET`; auf einem lokalen Checkout
ohne Bucket automatisch unter `%LOCALAPPDATA%/consens/agent-files` (sonst
`~/.local/share/consens/agent-files`), nie auf einem Deploy (`RENDER_SERVICE_NAME`
oder `ENVIRONMENT=production`) und nie in Tests. Der Bucket-Client meldet sich mit
derselben Admin-Schlüsseldatei an wie Firebase (`security.FIREBASE_ADMIN_KEY_FILE`),
solange kein `GOOGLE_APPLICATION_CREDENTIALS` gesetzt ist. Metadaten und begrenzte
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
Tokenreservierung und tatsächlicher Usage-Abrechnung. Seit 2026-10-15 (Audit
A6) steht der Dateiblock des Hauptmodells direkt hinter der Frage der Nachricht
(`DelegationLoop.turn_start` als `anchor`, Auszugssuche mit der Frage), nicht
hinter dem neuesten Tool-Ergebnis: In jedem Schritt derselbe Block an derselben
Stelle, also aus dem Prompt-Cache statt jedes Mal voll bezahlt. Vergleichs- und
andere Worker-Aufrufe hängen ihn weiter ans Ende ihres eigenen Prompts.
`FileContext` (eine Instanz pro Turn) lädt Bild-/PDF-Bytes einmal pro Turn
(`_raw`, gebunden an den SHA-256 des Datensatzes); die Metadaten liest jeder
Aufruf weiter einmal, damit eine gelöschte oder abgelaufene Datei sofort
scheitert. Tool-Daten sind keine
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
(`agentReview.render`) entstehen erst am Ende eines Laufs. Endet der Lauf mit
genau dem Text, den die Live-Prüfung schon vollständig samt Claim-Marken
gerendert hat, schaltet `renderAnswer` nur `renderMode` auf `full` und behält
dieses DOM (sonst fielen alle Marken weg und wurden neu aufgebaut: Flackern).
Vorläufige Coverage-Marken (`agentReview.preview`, seit 2026-10-18, seit
2026-10-21 neutral ohne Urteil) zeichnet `project` schon, während die feste
Antwort geprüft wird.
Seit 2026-10-20 (Apple-Audit D4) malt `follow()` gestreamten Text einmal pro
Frame (`schedulePaint` → `renderAnswerBody(..., 'stream')`, nur in eine Antwort,
die dieser sichtbare Lauf schon streamt), getrennt vom 100-ms-Takt der übrigen
Projektion; ein Frame über 8 ms rückt den nächsten um das Doppelte hinaus.
Sobald die Review den gestreamten Text als Version hält („settled“), rendert
`project` ihn vollständig (`morphMarkdown` mit `streamSourcePills`, in die
gezeigten Knoten und mit `keepTextSelection`) – auch eine Antwort, die mit
einer Tabelle endet, zeigt sie so schon während der Prüfung.
**Takt und Licht (seit 2026-10-22, `stream-reveal.js`).** Wo
`App.streamReveal.active()` gilt, malt `renderAnswerBody` im Modus `stream` nicht
selbst, sondern reicht den angekommenen Text mit `renderMarkdownStream` als
Maler an `App.streamReveal.stream`. Das Modul malt in eigenen Frames ein
wachsendes Präfix aus ganzen Wörtern, etwa 0,15 s hinter dem angekommenen Text
(bis 0,8 s, wenn ein Proxy in Sekundenbrocken puffert: der Abstand folgt der
gemessenen Pause zwischen zwei Brocken); ein großer Brocken wird schneller
nachgeholt, nie in einem Sprung. Ein vom Stream zerschnittenes Wort wartet
250 ms auf seinen Rest; „-“, „###“, „1.“, „>“ am Zeilenanfang stehen nur mit
ihrem ersten Wort (vorher stand für etwa 25 Frames je Antwort ein leerer
Punkt oder eine leere Überschrift da). Über 1200 Zeichen Rückstand (Reload
eines laufenden Turns) wird sofort gezeigt. Ein Frame mit mehr als 8 ms
Malzeit rückt den nächsten um das Doppelte hinaus (vorher in `follow()`).
Ein gemaltes Wort steht sofort ganz im Layout (bricht nie halb um), seine
Buchstaben kommen aber im Tempo des Texts nacheinander ins Bild, höchstens
100 ms nach dem Malen: Jeder blendet weich ein und erscheint in
`--stream-light` (hell `--agree`, dunkel heller gemischt, `variables.css`), das
in etwa sechs Wörtern zu Tinte abkühlt. Gezeichnet wird mit der CSS Custom
Highlight API (`stream-light-<Farbe>-<Stufe>`, Regeln in einem
`adoptedStyleSheets`-Blatt, je Textfarbe eigene, Stufe 0 = noch nicht im Bild);
kein Knoten kommt hinzu, Auswahl und Links im wachsenden Absatz bleiben. Was
kein Text ist (Aufzählungspunkt, Quellen-Pill, Kästchen, Linie, Tabelle), blendet
`agent-chat.css` über `#agentAnswerBody.is-stream-revealing` mit ein. Wird der
Text fest (Modus `full`), rendert `renderAnswerBody` über
`App.streamReveal.settle(body, text, render)`: Ein Rückstand läuft im Takt
weiter, die volle Darstellung folgt dem letzten Wort. Kommt sie so später als
der Aufruf, ersetzt sie die Quellen-Pills und Marken, die `agentReview.render`
schon auf den getakteten Text gesetzt hatte: `renderAnswerBody` zählt dann
`_agentRenderSerial` hoch und projiziert die Ansicht per
`registry.renderVisible()` neu (im Microtask, nachdem das Modul den Text
gemessen hat). Bis 2026-10-23 blieben die `[S1]`-Pills einer Antwort ohne
Vergleich so bis zum Reload aus. Ein Text, der nicht an
den getakteten anschließt (anderer Chat), rendert sofort und beendet das Licht.
Schreibt jemand anderes in die Antwort (`_markdownWrites`, etwa die Marken der
Review), gibt das Modul sie ab. Der WAAPI-Fade des Antwortbeginns
(`agentActivity.reveal`) entfällt für getakteten Text.
Die Ladehinweis-Zeile „Loading chat models…“ erscheint erst nach 1,2 s
(`LOADING_NOTICE_DELAY_MS`); vorher schob ihr kurzes Aufblitzen den zentrierten
Composer beim Reload hoch und wieder runter. Erstes Zeichnen: Endete die letzte
angemeldete Sitzung in Agent: seit 2026-10-20 erwartet `app-bootstrap.js`
Agent für jede bestätigte Sitzung (`App.expectsAgent()`: Agent ist für jedes
Konto offen und Standardmodus) und seit 2026-10-21 auch für einen Gast
(`App.isGuest()`, Apple-Audit H3), außer Konto oder Gast wählten einen anderen
Modus oder dieser Browser sah das Konto ohne Agent-Zugang (`localStorage.agentShellExpected` =
`"0"`, geschrieben in `renderShellNow` aus `App.agentAccess.allowed`). Dann
setzt es `html.agent-shell-expected` und `body.single-agent-active`; bis der
Zugang bekannt ist, hält `agent-chat.js` Agents Aussehen (`expectingAgent()`,
exportiert `App.agentChat.looksAgent()`: Chip, Reasoning, keine Demo, Agent-Texte;
gesendet wird erst mit bekanntem Zugang; eine Anmeldung ohne Neuladen setzt die
Erwartung nach derselben Regel). Keine 10-s-Notbremse mehr; ein
fehlgeschlagener `/user_status` (5xx/Netz) lässt den Zugang offen, fragt mit
wachsender Pause erneut (`firebase.js` `STATUS_RETRY_MS`, sofort bei `online`,
Rückkehr oder „Try now“ = `App.retryAccountStatus()`) und zeigt im Composer
„Your account could not be reached. Trying again…“ (`App.agentAccessCheck`);
nur eine Ablehnung (4xx) setzt `allowed: false` (Apple-Audit B8). `auth-unavailable`
löst die Erwartung auf.
Seit 2026-10-02 führt die Evidenzzeile `.agent-review` mit einem dezenten
Agreement-Score (`.agent-agreement`, „72 /100 agreement“): Wert aus
`check.differences_data.agreement` der gewählten Vergleichsbasis (wechselt mit
„Evidence for“), gleiche Stufenwörter wie der Consensus-Verdict, nur die Zahl in
Ampelfarbe, kein Balken; ohne bewertbare Abdeckung (`coverage_status:
insufficient`) oder bei nicht gebundenem Check keine Zahl. Settings → Agreement
score gilt auch hier (`agreement-score-hidden` zeigt die Wörter,
`agreement-verdict-hidden` blendet aus).

**Streaming-Markdown.** `markdown-stream.js::renderMarkdownStream(el, md)`
zerlegt die wachsende Antwort an Leerzeilen außerhalb von Code-/Mathe-Blöcken in
Top-Level-Blöcke; fertige Blöcke werden genau einmal geparst, nur der letzte
offene neu. Listen/Zitate über Leerzeilen bleiben zusammen, eine Grenze gilt erst
mit vollständiger Folgezeile. Ein im offenen Block begonnenes, noch nicht
geschlossenes `**` rendert `closeOpenStrong` schon fett statt mit rohen
Sternchen (nicht in Code-Fences). Fremde Schreibzugriffe oder nicht nur wachsender
Text starten neu. Seit 2026-10-20 (Apple-Audit D4/A5/A6) wird der offene Block
nicht mehr ersetzt, sondern in die gezeigten Knoten **gemorpht**
(`morphNodes`: gleiche Knotenart bleibt dasselbe Objekt, Text wächst per
`appendData`, Attribute und `sourceData`/`sourceGroup` der Pills wandern mit;
anderes wird aus dem neuen Render übernommen, das Ergebnis gleicht ihm Knoten für
Knoten) – ein Link im entstehenden Absatz bleibt klickbar, eine Auswahl darin
bleibt; wird der Block fertig, morpht sein endgültiger Render in dieselben Knoten.
Eine noch einströmende Tabelle (Zeile mit führendem `|` außerhalb von Fences)
steht als `.stream-table-pending` da: je angekommener Zeile ein leiser
`.skeleton`-Balken in Zeilenhöhe (`aria-hidden`), die Tabelle erscheint erst
vollständig – vorher rutschten die Spaltenköpfe mit jeder Zeile seitlich.
Markdown wird einmal geparst: `renderMarkdownFragment(md)` lässt DOMPurify
(`RETURN_DOM_FRAGMENT`) seinen eigenen DOM liefern, entschärft entfernte Bilder,
solange die Knoten noch in DOMPurifys inertem Dokument stehen (ein `<img>` lädt
ab der Übernahme ins Seitendokument), und übernimmt sie erst dann
(`document.adoptNode`). `window.morphMarkdown(el, md, { decorate })` rendert den
festen Text vollständig wie `injectMarkdown(el, md, [])`, aber in die gezeigten
Knoten. `window.keepTextSelection(root, change)` hält eine Auswahl über `change`
hinweg als Position im Fließtext (Claim-Badges und Pills zählen nicht) und
setzt sie nur zurück, wenn sie verloren ging. Jeder Markdown-Schreibvorgang zählt
`el._markdownWrites` hoch; Marken-Renderer erkennen daran (zusammen mit dem
ersten Knoten) einen neuen Render, denn ein Morph behält den ersten Knoten.
`resetMarkdownStream(el)` verwirft den Zustand. `injectMarkdown(el, md, [])`
merkt sich, was es geschrieben hat (`el._plainMarkdown`);
`window.isPlainMarkdown(el, md)` ist wahr, solange `el` genau das noch
unmarkiert zeigt. `agent-review.js` `mark()` markiert dann direkt statt
denselben Text ein zweites Mal zu rendern (Apple-Audit D5: jeder geöffnete
Agent-Turn lief zweimal durch Markdown). Vorläufige und endgültige Marken
(`preview()`, `mark()`) und das Abnehmen der Marken legen sich über den Text
(`overText`): Rückmorph auf den schlichten Render, Marken, Pills, Auswahl
zurück – vorher ersetzte jede Prüf-Aktualisierung die ganze Antwort (A6).
Optional `renderMarkdownStream(el, md, { decorate })`: `decorate(holder)`
gibt jedem Block vor dem Einhängen seine endgültige Inline-Form; Agent nutzt das
für Quellen-Pills (`agent-chat.js::streamSourcePills` → `linkifyAgentSources`
mit den Links des Blocks). Pills zeigen den Host, ihre Breite hängt also nicht
an der finalen Quellennummerierung; der Review-Pass baut dieselbe Geometrie.

**Keine Verschiebung (2026-10-09, `docs/layout-shift-audit-2026-10-09.md`).**
Was schon sichtbar ist, bewegt sich nicht mehr: Claim-Marken (`.cx-claim`)
haben keinen horizontalen Innen-/Außenabstand mehr, der Überstand ist ein
`box-shadow` in Markenfarbe (`--cx-paint`, `--cx-bleed`; `cx-join-*` lassen die
innere Seite weg), Filter/Ausblenden setzen auch `box-shadow: none`. Die
Fortschrittszeilen über der Antwort (`.agent-progress`) verschwinden ohne
Animation, sobald Antworttext steht und kein Tool läuft (eine Präambel vor einem
laufenden Tool zählt nicht); die App-Prüfungen der fertigen Antwort
(`judge_answer`, `answerChecks`) holen sie nicht zurück –
bis 2026-10-12 klappten sie dafür ein zweites Mal auf und zu. Eine vom Leser geöffnete Aktivitäts-Historie bleibt
am Laufende offen, solange sie im Bild ist (oberhalb des Viewports klappt sie mit
`preserveAbove`-Korrektur zu). Der Antwortbeginn blendet nur ein
(`reveal(body, {lift:false})`). Laden: `app-bootstrap.js` setzt per
MutationObserver vor dem ersten Paint `agent-mode-enabled`, das gespeicherte
Theme (`body.dark-mode` nach `localStorage.theme`, sonst Systemvorgabe — vorher
erst in `app-init.js`, jeder dunkle Reload malte zuerst hell, und iPhone-Safari
behielt das Weiß hinter der Statusleiste), den
Sidebar-Zustand (`sidebar_collapsed`, sonst Gast zu/Konto offen; Overlay < 1100 px
immer zu), `#authTopActions`
nur für Gäste ohne `id_token` und bei `html.agent-shell-expected` die
Agent-Texte (Begrüßung, „New chat“, Composer-Platzhalter), die `renderShellNow`
bzw. `syncComposer` bis zur bekannten Berechtigung hält; Gäste ohne `id_token`
bekommen sofort denselben Platzhalter eines neuen Chats (`App.askPlaceholder()`)
und `body.is-guest` (seit 2026-10-15, Gäste tippen). Solange eine gespeicherte Sitzung
noch wiederhergestellt wird (Auth unbekannt, `id_token` vorhanden), lässt
`updateQuestionInputAccess` den Platzhalter stehen — vorher wechselte er beim
Reload Vorlage → „Sign in…“ → „Enter your question“ → Agent-Text.
`#composerModeBar` ist im Template sichtbar (Startbildschirm).
Inter wird in `index.html` vorgeladen, bis dahin setzt „Inter Fallback“ (Arial
mit Inter-Metriken, `typography.css`) den Text ohne Umbruchänderung;
`.sidebar-content` reserviert eine dünne Scrollbar-Rinne.

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
`agent-delegation.js` öffnet die Leiste seit 2026-10-17 auf keiner Breite
selbst, auch nicht für einen laufenden Turn (vorher ab 1200 px automatisch
bei Platz neben der Spalte). Das Panel-Symbol neben den Modell-Icons
(`.agent-sidebar-toggle`, `aria-label` „Activity · n“,
`aria-controls="agentSidebar"`) oder ein Modell-Icon öffnet sie: unter 1200 px
als Sheet mit Scrim, Fokusfalle und Escape, ab 1200 px daneben; offen rückt
die Spalte nach links (`body.agent-sidebar-open`), statt unter der Leiste zu
liegen. Nur explizites Öffnen/Schließen wird pro Turn gemerkt, **und seit
2026-10-20 auch pro Chat** (`agent-panel:{uid}:{chatId}` in sessionStorage,
Apple-Audit A9): ein neuer Turn übernimmt die Wahl des Chats, und solange eine
Folgefrage ihren Turn noch nicht kennt (`project({chatId, running})` ohne
`turnId`), bleibt eine offene Leiste mit „Starting…“ stehen, statt zu- und
wieder aufzugehen. Sie geht auf demselben Weg, wie sie kam
(`setPanelVisible`, `.is-leaving` gleitet/blendet samt Scrim aus, erst danach
`hidden`; C5). Logo-Einflug (`.agent-inline-model.is-arriving`) nur für Modelle,
die während eines laufenden Turns dazukommen; ein gespeicherter Turn zeigt seine
Logos sofort aus `agent_review` (`project({models})`, `agent-chat.js`
`reviewModels`), die spätere Agent-Liste ergänzt dieselben Knöpfe (A10). Der
2,5-s-Takt existiert nur
während eines laufenden bzw. abschließenden Laufs und endet danach.
Die Kopfzeile tickt in einem Feld fester Breite (A7): `.agent-activity-verb`
reserviert die Breite des breiteren Verbs („Working for“/„Thought for“, das
andere unsichtbar per `data-ghost`), `.agent-activity-time[data-unit]` die des
größten Werts seiner Einheit. Eine live tickende Uhr hält den Platz ihrer
eigenen Einheit (bis 59 s nur `seconds`; bis 2026-10-21 von der ersten Sekunde
an den Minuten-Platz, das ließ eine Minute lang eine breite Lücke vor dem
Pfeil); bei 1 min weitet sich der Platz einmal weich (`setTitle` misst alte
und neue Breite und animiert `width` mit `overflow: clip`, bei reduced-motion
sofort). Das Endlabel behält mindestens den Platz, in dem die Uhr zuletzt
tickte. Pfeil und Logos stehen beim Ticken innerhalb einer Einheit und am
Laufende still (Chevron bei 9 s und 10 s bzw. bei 1 min und „Thought for“ auf
demselben Pixel), der Wortlaut bleibt.
Zeilenstatus hängt per `aria-describedby` am Eintrag; Texte/Titel werden nur bei
Änderung geschrieben. Judge-Aufrufe (`kind: "judge"`) erscheinen nicht einzeln:
`checkRow` fasst alle Versuche, Wiederholungen und Backup-Judges zu einer Zeile
„Answer check“ (`id: answer-check`, ohne Detail-Request) zusammen. Ihr Status
ist das Ergebnis der Checks (`completed`, sobald jeder Check einmal fertig ist;
`failed` nennt die nicht ausführbaren Checks), Tokens sind die Summe der
gemessenen Judge-Aufrufe. Chip-Zähler und Modell-Icons zählen Judges nicht mit.
Der Helfer eines Quellen-Abrufs (`kind: "source"`, „Read source · host“) ist
eine eigene Zeile mit Modell, Tokens und ggf. Grund und zählt im Chip und in
„n of m done“ mit, bekommt aber kein Modell-Icon (er ist keine Stimme der
Antwort).
Lief bisher nur der Judge eines eingefügten Texts („Text check"; die
Antwort-Judges folgen nach dem Schreiben, gespeicherte Turns vom 2026-10-09
haben keine), heißt die Zeile „Text check" und verweist auf die Karte über der
Antwort.
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

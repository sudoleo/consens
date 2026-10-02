# Implementierung der Backendadapter, 02.10.2026

[Arbeitspakete](work-packages.md) · [Architektur](../../codebase-map.md)

Diese Nachweise ergänzen WP-11, WP-12, WP-13, WP-15, WP-16, WP-17,
WP-18, den Pythonteil von WP-22, WP-23, WP-27, WP-31 und WP-32.
WP-21 erhält zusätzlich einen echten `main.app`-Fehlervertrag für die
Browserprüfung. Die übergreifende Paketabnahme und Browsernachweise werden im
zentralen Audit geführt.

Die abschließende Abnahme ergänzt außerdem WP-10 (Memory-HTTP-Grenze und
native Commitfehler) und WP-14 (native Own-Key-Workerzuordnung); siehe unten.

## Testgrenzen

Die neuen HTTP-Prüfungen verwenden `TestClient(main.app)` mit den tatsächlich
registrierten Routen, Middleware und Exceptionhandlern. Auth-, Admin-, Tier-,
Owner- und Serviceguards bleiben aktiv. `adapter_test_support.py` ersetzt
Firebase-SDK-Authentifizierung und Datenbankzugang, leert lediglich lokale
Auth-/Limit-Caches und stellt echte Key-, Run- und Cleanup-Repositories bereit.
Die übrigen lokalen Tests verwenden vorhandene transaktionsfähige DB-Doubles.
Mail, Telegram und kostenpflichtige Modellantworten enden an kontrollierten
externen Grenzen. Ein Background-Executor sammelt echte Recoveryaufträge,
deren Funktionen anschließend ausgeführt werden.

Drei zusätzliche SDK-Prüfungen laufen gegen Firestore-Emulator 1.19.8,
`demo-consensio-e2e`, mit anonymen Credentials und eindeutigen Collections bzw.
UIDs. `native_support` löscht nur die registrierten eigenen Dokumentwurzeln.
Die Migration wird zusätzlich mit zwei konkurrierenden Transaktionen geprüft.
Dies belegt lokale SDK- und Transaktionssemantik, keine Produktions-IAM,
Providerqualität oder reale Nachrichtenzustellung.

## Paketnachweise und behobene Fehler

| Paket | Ausgeführter Vertrag | Tests |
|---|---|---|
| WP-11 | Recovery von `accepted`/`reserved`, lebende und abgelaufene Leases, kein zweiter Providerstart oder Verbrauch, abgelaufene Daten und wiedergebundene Idempotenzschlüssel, wiederholbarer Backfill nach Fehlern. Historischer Source-GET prüft UID, Run/Job/Antwort-/Promptversion, alle Seiten, negative Cursor, Revisionkonflikt und unveränderte Polls. | `test_api_run_recovery.py`, `test_api_source_history.py`, `e2e/test_api_retention_transactions.py` |
| WP-12 | Lookup/Create-Race im echten Registrierungsservice: gleiche neutrale Antwort für neu/bestehend/Race, nur eine Neunutzerbenachrichtigung. `user_status` über echte Tarifauflösung für Free, Plus, Pro, Free-Admin und Auth-/Tierausfall. | `test_http_adapter_auth.py` |
| WP-13 | Echter App-Share-POST mit autoritativem Pending-Ergebnis, gefälschten Inhalts-/Owner-/Visibilityfeldern, Quota, Ablauf, Transaktionsfehler und idempotentem Retry; HTTP-Antwort und gespeicherter Share stimmen überein. | `test_share_http_contract.py` |
| WP-15 | Watch PATCH/DELETE, Telegram Link/Test/Disconnect, Owner-/Allowlist-/Tarifregeln, nicht verbundener Versand, Provider-/Storefehler; gültige, ungültige, abgelaufene und fremde Tokentypen bei Watch- und Followerabmeldung; escaped Bestätigungs-HTML. | `test_watch_http_contract.py` |
| WP-16 | Alle fünf Adminmethoden einschließlich PUT und Run-Anlage mit echter Adminprüfung, Revocation und 503. Hub/Sitemap bei aktiv/pausiert/noindex/archiviert/unveröffentlicht; Follow über den tatsächlich erzeugten E-Mail-Link, neutrale Wiederholung, Confirm-/Unsubscribe-Token und escaped Titel. | `test_http_adapter_auth.py`, `test_topic_public_http.py` |
| WP-17 | Echter Identity-Helper/Parser/Retryplan bei bekannten, unbekannten und doppelten Keys, ungültigen Indices, begrenztem Prompt, ungültigem Modell, Transport-/JSONfehlern und sicherem Logging. | `test_claim_identity_judge.py` |
| WP-18 | 615 Referenzen in 400/215-Batches, ungeordnete/fehlende Snapshots, veraltete Payloadidentität, Datumsvarianten, begrenzte Latest-/Judgmentqueries und echte SDK-Rückgaben. Fehlende Messung bleibt fehlend. | `test_seo_repository.py`, `e2e/test_seo_repository_queries.py` |
| WP-22 | Benchmark-Adminliste und -detail führen die tatsächlichen Guards und den kompakten Reportservice aus; Nichtadmin vor Read, ungültige/fehlende IDs 404, keine Rohprompts/-antworten. Viewer und Auswahlwechsel gehören zum separaten Browserpaket. | `test_http_adapter_auth.py` |
| WP-23 | Echtes Pillow-Rendering mit Frage, Score, Modell-/Konfliktzahl und unscored-Verhalten. Dekodierung, mehrere nichtleere Bildregionen und geänderte Fragepixel; echte OG-Route verwendet gespeicherte Werte, private/widerrufene Shares 404. Alle Cacheinputs und Renderfehler-Retry geprüft. | `test_og_image.py`, `test_share_http_contract.py` |
| WP-27 | Echter Feedbackhandler/Persistenzguard mit Auth, Allowlist, persistiertem Cooldown trotz lokalem Limiterreset, Tageslimit und Storefehler; Statistik schreibt Zähler/Modellmetadaten, keine Frage/Antwort/UID/Run-ID, und Fehler bleiben nichtfatal. | `test_feedback.py` |
| WP-31 | Tatsächliche Agent-Kapazitätsablehnung 503 und API-UID-Limit 429 durch `main.app`, sichere Antwort plus serverseitiges `Retry-After`; Requestheader werden nicht reflektiert, keine Arbeit/unerlaubten Writes. | `test_agent_http_contract.py` |
| WP-32 | Echte Agentdetail-Pagination ohne Lücken, UID-/Chat-/Turn-Bindung, Parametergrenzen und Pro-/Adminregel. Wiederholter Stop verändert ausschließlich seinen Turn; spätes Workerpublish scheitert. Private Antworten ohne Cache, kein Modellstart. | `test_agent_http_contract.py` |

Die roten Regressionstests zeigten folgende Produktfehler:

- Topic-Admin akzeptierte ein widerrufenes Token, weil `check_revoked=True`
  fehlte; Rollendienst-Ausfälle wurden zu 500 statt 503.
- Agent-Zugriff projizierte denselben Tierausfall als 500; Turn-Stop vergaß
  `Cache-Control: private, no-store`.
- Retention-Backfill konnte den Ablauf eines inzwischen an einen anderen Run
  gebundenen Idempotenzdokuments überschreiben. Er liest jetzt beide Dokumente
  transaktional erneut und aktualisiert nur die noch passende Bindung.
- Identity-Indizes wurden über `int(...)` umgedeutet; ein ungültiges Modell
  konnte einen nicht iterierbaren Retryplan ergeben.
- SEO-BatchGet vertraute gespeicherten `page_id`-/`date`-Werten statt dem
  angeforderten Dokumentpfad und konnte eine Messung falsch zuordnen.
- Der OG-Cache ignorierte Frage, Modell-/Konfliktzahl und Änderungen der
  Historienwerte bei gleicher Länge; sein Schlüssel enthält nun alle Inhalte.
- Watch-/Share-Follower-Token akzeptierten unpassende Aktionstypen teilweise
  erst nach Dokumentzugriff oder als erfolgreiche Abmeldung. Der jeweilige
  Service validiert nun die eigene Payloadform vor Zugriffen.

### Präzisierung von D-06

Der Identity-Judge fordert bereits JSON-Integer. Deshalb gilt ausdrücklich
`type(index) is int`: `true`, `false`, `0.0`, `0.5`, numerische Strings, `null`,
negative und zu große Werte erzeugen keine Bindung. Eine stille Umdeutung
könnte zwei unterschiedliche Claims gleichsetzen und ist hier gefährlicher
als eine ausgelassene Zuordnung. Der Aufrufer behält seinen bisherigen
Fallback für nicht zugeordnete Claims. Bekanntes Fenster: 24 Claims, neues
Fenster: 12 Claims, je 300 Textzeichen, Antwortbudget: 512 Tokens. Der echte
Retry-/Fallbackplan bleibt begrenzt; Fehlerlog enthält keine Modellinhalte.

Die OG-Route gewinnt dadurch keine historische Versionsauswahl/Sparkline:
sie nutzt weiterhin den neuesten gültigen öffentlichen Stand und übergibt
eine leere Historie. Der zusätzliche Cachetest schützt die vorhandene
Rendererfähigkeit für Aufrufer mit Historienwerten.

## Ausführung und Negativkontrollen

Der fokussierte Lauf mit neuen und betroffenen bestehenden Backendtests war
grün: **810 passed, 2 bestehende asyncio-DeprecationWarnings, 32,40 s**.
Die drei nativen Emulatorprüfungen waren grün: **3 passed, 4,98 s**.
Nach anschließender reiner Formatierung und stärkerer Mail-/Nichtwriteassertion
wurden die drei betroffenen HTTP-Fälle erneut erfolgreich ausgeführt.
Kein externer Provider oder Nachrichtendienst wurde aufgerufen.

Schneller Wiederholungslauf der neuen HTTP-/Servicefälle plus Account-Envelope:

```powershell
$env:UNIT_TEST_MODE = '1'
$env:PYTHONUTF8 = '1'
$env:OPENROUTER_API_KEY = 'dummy'
$adapterTests = @(
  'tests/test_claim_identity_judge.py', 'tests/test_http_adapter_auth.py',
  'tests/test_og_image.py', 'tests/test_seo_repository.py',
  'tests/test_agent_http_contract.py', 'tests/test_feedback.py',
  'tests/test_share_http_contract.py', 'tests/test_api_run_recovery.py',
  'tests/test_api_source_history.py', 'tests/test_watch_http_contract.py',
  'tests/test_topic_public_http.py', 'tests/test_account_tier_admin.py'
)
venv/Scripts/python.exe -m pytest @adapterTests -q
```

Für den 810er-Regressionslauf kamen diese bestehenden Dateien hinzu:
`test_topics_feature`, `test_auth_revocation`, `test_registration_security`,
`test_auth_session`, `test_tier_cache`, `test_plus_tier`, `test_share_feature`,
`test_watch_feature`, `test_seo_data`, `test_seo_weekly_review`,
`test_benchmark_reports`, `test_benchmark_report_reader`, `test_differences_stats`,
`test_consensus_api`, `test_agent_capacity`, `test_agent_search`,
`test_agent_delegation`, `test_agent_reliability`, `test_api_run_repository`,
`test_api_run_billing_identity`, `test_source_check_api`, `test_source_check_scope`
(jeweils `tests/<Name>.py`). Lokale Laufartefakte liegen unter
`test-results/adapters-focused.xml` und `test-results/adapters-focused.log`.

Für den bereits laufenden, isolierten Emulator zusätzlich:

```powershell
$env:RUN_E2E = '1'
$env:E2E_TEST_MODE = '1'
$env:FIRESTORE_EMULATOR_HOST = '127.0.0.1:8085'
$env:GOOGLE_CLOUD_PROJECT = 'demo-consensio-e2e'
$env:GCLOUD_PROJECT = 'demo-consensio-e2e'
$env:FIREBASE_PROJECT_ID = 'demo-consensio-e2e'
Remove-Item Env:GOOGLE_APPLICATION_CREDENTIALS -ErrorAction SilentlyContinue
venv/Scripts/python.exe -m pytest tests/e2e/test_api_retention_transactions.py tests/e2e/test_seo_repository_queries.py -q
```

Zwölf temporäre Einzelmutationen wurden nacheinander tatsächlich ausgeführt.
Jede erzeugte einen Assertionfehler (Exit 1), keinen Collection-/Setupfehler;
die ursprünglichen Quelldateien wurden jeweils bytegenau zurückgesetzt.
Lokale Protokolle: `test-results/mutation-WP-*.log` und
`test-results/adapter-mutation-results.json`.

| Paket | Absichtlich eingebrachter Fehler | Erkennende Assertion |
|---|---|---|
| WP-11 | Run-ID-Prüfung vor Mapping-Backfill entfernt | Fremde Ablaufdaten bleiben unverändert |
| WP-12 | SDK-Create-Race nicht mehr als bestehenden Nutzer behandelt | Alle drei HTTP-Antworten 200/check_inbox |
| WP-13 | Appadapter publiziert mit `visibility=private` | Autoritativer gespeicherter Public-Share |
| WP-15 | Watch-PATCH verwendet feste fremde UID | Fremder Request 403 und unveränderter Store |
| WP-16 | Topic-Admin entfernt `check_revoked=True` | Widerrufene Tokens und SDK-Flag je Methode |
| WP-17 | Bekannte/einmalige Claim-Keys nicht geprüft | Nur bekannte eindeutige Zuordnungen |
| WP-18 | BatchGet bevorzugt Payload-`page_id` | Exakte Zuordnung anhand Dokumentidentität |
| WP-22 | Admin-Listenguard entfernt | Nichtadmin vor jeglichem Reportread abgewiesen |
| WP-23 | Renderer liefert gültiges weißes PNG | Mehrere Bildregionen enthalten gezeichneten Inhalt |
| WP-27 | Statistikwrapper schreibt unbearbeitete Eingaben | Keine privaten Inhalts-/Identitätsmarker gespeichert |
| WP-31 | `main` verwirft Exceptionheader | Tatsächliche 429-Antwort enthält `Retry-After: 60` |
| WP-32 | Stop-Aufruf am Store entfernt | Nur Zielturn ist gesperrt, später Workerwrite scheitert |

`test_account_tier_admin.py::test_unknown_account_has_structured_error_in_real_main_app`
belegt zusätzlich für WP-21: unbekanntes Konto ergibt durch den echten
Haupthandler 404 mit `error.error_code=not_found` und lesbarer
`error.message`, ohne SDK-Diagnose. Ein isolierter Router mit `detail` ersetzt
diesen Vertrag nicht.

## Ergänzende Abnahme: WP-10, WP-14 und saubere Mailumgebung

`tests/test_memory_http_contract.py` führt zwölf Fälle durch `main.app` und
den echten Memory-Service bzw. das echte Repository aus. Nur Firebase-SDK-Auth
und die Datenbankgrenze sind Doubles; weder `verify_user_token` noch
`get_user_tier` oder ein Router-/Repositoryguard wird ersetzt. Die Fälle prüfen
401, Tarifausfall 503, fremde/fehlende Revision 404, ungültige ID 422,
abgelaufenes Undo und spätere manuelle Revision 409 sowie abgesenktes Limit
422. Jeder Fehler lässt den vollständigen Store unverändert und startet keinen
Provider. Eine bereits vor der Kontolöschung authentifizierte Anfrage wird bei
Edit und Undo durch den Tombstone im Repository mit 403 abgefangen. Erfolgreiches
Undo stellt sämtliche Profilfelder wieder her; Wiederholung verändert weder
Revision noch Quota.

`tests/e2e/test_memory_edit_transactions.py` verwendet auch an seiner
HTTP-Grenze die SDK-Auth-Fixture und echte Tier-/Memory-Guards. Ein gezielter
Fehler bei `DocumentReference.get` belegt den echten 503-Pfad. Der native
Tombstonetest umfasst zusätzlich Reserve und Undo. Zwei neue Commitfehlerfälle
lassen die echten Transaktionen sämtliche vier Apply- bzw. zwei Undo-Writes
vorbereiten und brechen ausschließlich am SDK-Committransport ab. Profil,
Request, Revision und Quota bleiben danach exakt unverändert. Die sieben
nativen Memory-Fälle verwenden eigene UIDs und behalten den gemeinsamen
Emulator-Tageszähler bei.

`tests/e2e/test_source_check_transactions.py` ergänzt den vollständigen
Own-Key-Workerpfad: Zwei echte Repositories arbeiten in isolierten nativen
Collections. Nur der zugewiesene Worker besitzt den zufälligen Dummy-Schlüssel
im flüchtigen Keyregister. Der fremde Worker erhält keinen Claim und darf mit
fremder UID auch nicht neu binden. Der richtige Worker verarbeitet genau ein
Paket über den echten Jobservice, übergibt den Schlüssel ausschließlich an den
kontrollierten Modelltransport und entfernt ihn anschließend aus dem Speicher.
Wiederholung erzeugt keinen zweiten Modellaufruf. Entpackte Job-/Paket- und
Cachedaten, Worker-Dokumente und erfasste Logs enthalten keinen Schlüssel.
Fetch und Judge sind externe Doubles; ein Rückfall auf Entwicklercredentials
lässt den Test unmittelbar fehlschlagen.

Die beiden ergänzenden Negativkontrollen liefen als isolierte Pytest-Prozesse
mit nur im Prozess ersetzten Methoden. Die Entfernung der Undo-Revisionsprüfung
erzeugte 200 statt 409 im echten HTTP-Fehlerfall. Die Entfernung der
Own-Key-Affinitätsprüfung ließ den fremden Worker das native Jobdokument
verarbeiten. Beide Kontrollen endeten mit genau einem Assertionfehler und Exit
1, ohne Import-/Setupfehler; Produktdateien wurden dabei nicht verändert.
Lokale Belege: `test-results/followup-mutation-memory.log`,
`test-results/followup-mutation-affinity.log` und
`test-results/followup-mutation-results.json`.

Die öffentliche Topic-Mailfixture setzt jetzt den tatsächlich ausgewerteten
`MAIL_FROM` statt `SMTP_FROM` und prüft den erzeugten From-Header. Dadurch hängt
der Bestätigungslinktest nicht von einer geerbten lokalen Mailkonfiguration ab;
der echte Konfigurationsguard bleibt aktiv und nur der Versand ist ersetzt.
Der gemeinsame Lauf der folgenden vier Dateien ergab **32 passed**. Dabei
waren sämtliche Mailumgebungsvariablen vor dem Start entfernt. Wiederholung mit
den oben dokumentierten sicheren Emulatorvariablen:

```powershell
@('SMTP_HOST','SMTP_FROM','MAIL_FROM','SMTP_USER','SMTP_PASSWORD','SMTP_PORT') |
  ForEach-Object { Remove-Item "Env:$_" -ErrorAction SilentlyContinue }
venv/Scripts/python.exe -m pytest tests/test_topic_public_http.py tests/test_memory_http_contract.py tests/e2e/test_memory_edit_transactions.py tests/e2e/test_source_check_transactions.py -q
```

Diese Nachweise belegen lokale HTTP-, Job- und native Transaktionsverträge;
sie ersetzen keine produktive Firebase-Authentifizierung oder echte Provider-
bzw. Mailzustellung. Das lokale JUnit-Artefakt liegt unter
`test-results/adapters-followup.xml`.

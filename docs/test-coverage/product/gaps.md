# Verifizierte Befunde und ergänzende Tests

[Einstieg](README.md) · [Arbeitspakete](work-packages.md) · [Suchbelege](search-evidence.json)

36 Befunde. „Verifiziert“ bezeichnet den geprüften Code-/Testabgleich. Nur G-018/G-019 sind hier direkt beobachtete Verhaltensfehler; G-007/G-020 zusätzlich durch überlebende gezielte Mutationen belegte Assertionslücken. Die übrigen Kategorien unterscheiden fehlende Fälle/Integration, defekte Tests, Ausführungsnachweis und CI.

P1/P2/P3 ordnen die Umsetzung nach möglichen Folgen und Voraussetzungen; sie sind keine Incident-Schweregrade. Suchtreffer allein beweisen weder Vorhandensein noch Abwesenheit eines Tests. Die Schlussfolgerung verbindet Suche, Testkörper, Mockgrenzen und gegebenenfalls Branchlauf/Probe. Suggested paths sind Vorschläge, vorhandene passende Dateien bevorzugen.

| ID | Priorität / Art | Befund | Paket |
|---|---|---|---|
| [G-001](#g-001) | P1 / ` missing_integration ` | Deny-all-Regeln mit Clientidentitäten prüfen | [WP-06](work-packages.md#wp-06) |
| [G-002](#g-002) | P1 / ` missing_integration ` | Reguläre Usage mit echten Firestore-Transaktionen absichern | [WP-07](work-packages.md#wp-07) |
| [G-003](#g-003) | P1 / ` missing_integration ` | Chat-Löschen gegen Turn/Completion im Emulator | [WP-08](work-packages.md#wp-08) |
| [G-004](#g-004) | P1 / ` missing_integration ` | Vollständige Kontokaskade und API-Cleanup prüfen | [WP-09](work-packages.md#wp-09) |
| [G-005](#g-005) | P1 / ` missing_case ` | API-Neustart-Recovery und Retention tatsächlich ausführen | [WP-11](work-packages.md#wp-11) |
| [G-006](#g-006) | P1 / ` missing_integration ` | Source-Queue-Leases und Result-Commits im Emulator | [WP-14](work-packages.md#wp-14) |
| [G-007](#g-007) | P1 / ` assertion_gap ` | Undo-Konflikt, Ablauf und Wiederholung | [WP-10](work-packages.md#wp-10) |
| [G-008](#g-008) | P1 / ` missing_case ` | Memory-Patch gegen konkurrierenden Save und Kontolöschung | [WP-10](work-packages.md#wp-10) |
| [G-009](#g-009) | P2 / ` missing_case ` | Konkurrierende Registrierung ohne Auskunfts-/Benachrichtigungsleck | [WP-12](work-packages.md#wp-12) |
| [G-010](#g-010) | P1 / ` missing_case ` | Historischer API-v1-Source-Check-Adapter | [WP-11](work-packages.md#wp-11) |
| [G-011](#g-011) | P1 / ` missing_case ` | App-POST-/api/share durch den echten Router prüfen | [WP-13](work-packages.md#wp-13) |
| [G-012](#g-012) | P1 / ` missing_case ` | user_status-Adapter einschließlich Free-Admin und Ausfällen | [WP-12](work-packages.md#wp-12) |
| [G-013](#g-013) | P2 / ` missing_case ` | Watch-PATCH/DELETE und Telegram-Link/Test als HTTP-Vertrag | [WP-15](work-packages.md#wp-15) |
| [G-014](#g-014) | P1 / ` missing_case ` | Topic-Admin-Auth/PUT sowie öffentliche Adapter | [WP-16](work-packages.md#wp-16) |
| [G-015](#g-015) | P2 / ` missing_case ` | Admin-Benchmark-Routen und Reportviewer | [WP-22](work-packages.md#wp-22) |
| [G-016](#g-016) | P2 / ` missing_case ` | Claim-Identity-Judge selbst prüfen | [WP-17](work-packages.md#wp-17) |
| [G-017](#g-017) | P2 / ` missing_case ` | SEO-Readadapter hinter den Service-Fakes | [WP-18](work-packages.md#wp-18) |
| [G-018](#g-018) | P1 / ` observed_behavior_defect ` | Topic-Notizen werden erneut als HTML interpretiert | [WP-20](work-packages.md#wp-20) |
| [G-019](#g-019) | P2 / ` observed_behavior_defect ` | Strukturierte Adminfehler verlieren ihre Nachricht | [WP-21](work-packages.md#wp-21) |
| [G-020](#g-020) | P2 / ` assertion_gap ` | OG-Test akzeptiert leeres Bild | [WP-23](work-packages.md#wp-23) |
| [G-021](#g-021) | P2 / ` assertion_gap ` | Analytics-Opt-out ausführen statt Strings suchen | [WP-24](work-packages.md#wp-24) |
| [G-022](#g-022) | P1 / ` missing_case ` | Account-Reparaturskript ohne Produktionszugriff prüfen | [WP-25](work-packages.md#wp-25) |
| [G-023](#g-023) | P2 / ` missing_case ` | Claim-Key-Backfill-Dry-run, Idempotenz und Datenerhalt | [WP-25](work-packages.md#wp-25) |
| [G-024](#g-024) | P1 / ` missing_automation ` | Allgemeine Suite in CI absichern | [WP-05](work-packages.md#wp-05) |
| [G-025](#g-025) | P1 / ` execution_gap ` | 267 vorhandene Browserfälle ausführen | [WP-03](work-packages.md#wp-03) |
| [G-026](#g-026) | P2 / ` execution_gap ` | Windows-Einstieg tatsächlich validieren | [WP-04](work-packages.md#wp-04) |
| [G-027](#g-027) | P1 / ` broken_test ` | Zwei veraltete Emulatorfixtures reparieren | [WP-01](work-packages.md#wp-01) |
| [G-028](#g-028) | P2 / ` broken_test ` | Veralteten Footer-Stringvertrag korrigieren | [WP-01](work-packages.md#wp-01) |
| [G-029](#g-029) | P1 / ` unstable_test ` | Report-Race-Instabilität isolieren | [WP-02](work-packages.md#wp-02) |
| [G-030](#g-030) | P1 / ` missing_integration ` | Wenige vollständige Browser→Backend→Persistenz-Flows | [WP-29](work-packages.md#wp-29) |
| [G-031](#g-031) | P2 / ` missing_integration ` | Due-Queries und Scheduler-Claims mit SDK-Formen | [WP-19](work-packages.md#wp-19) |
| [G-032](#g-032) | P2 / ` missing_integration ` | Lokale echte Transportgrenzen statt ausschließlich MockTransport | [WP-26](work-packages.md#wp-26) |
| [G-033](#g-033) | P2 / ` missing_case ` | Ungültige Body-Header und Konfigurationsgrenzen | [WP-26](work-packages.md#wp-26) |
| [G-034](#g-034) | P2 / ` missing_case ` | Feedback-Adapter und Statistik-Persistenzwrapper | [WP-27](work-packages.md#wp-27) |
| [G-035](#g-035) | P3 / ` missing_case ` | Weitere ausführbare CLI-Einstiege | [WP-28](work-packages.md#wp-28) |
| [G-036](#g-036) | P2 / ` missing_case ` | Vendorhelper mit Version- und Check-only-Grenzen ausführen | [WP-30](work-packages.md#wp-30) |

<a id="g-001"></a>

## G-001 · Deny-all-Regeln mit Clientidentitäten prüfen

**P1 · missing_integration** · Verträge: [AUTH-05](matrix.md#auth-05) · Paket: [WP-06](work-packages.md#wp-06)

**Produktbeleg:** [firestore.rules](../../../firestore.rules#L31) — ` allow read, write: if false; `; [tests/e2e/test_agent_transactions.py](../../../tests/e2e/test_agent_transactions.py#L24) — ` db = firestore.Client `

**Vorhandene relevante Prüfungen:**

Kein direkter repräsentativer Testbeleg für diese Grenze; Suchtreffer und verwandte Verträge sind separat berücksichtigt.

**Suiteweite Gegenprüfung:** Kein Rules-Test gefunden. Alle vorhandenen Firestore-Emulatorfälle verwenden Server-/Admin-SDK und können eine versehentliche Freigabe von role/tier für Browserclients nicht erkennen.

**Suchspur:** 224 versionierte Test-/Hilfsdateien durchsucht, 0 passende Zeilen. Regexe: ` firestore\.rules `, ` assertFails|assertSucceeds|initializeTestEnvironment|rules-unit-testing `. Vollständige Treffer mit Pfad/Zeile in [search-evidence.json](search-evidence.json) unter ` G-001 `.

| Szenario | Erwartung |
|---|---|
| Given | Geladene Repo-Regeln und getrennte anonyme, Owner- und fremde Clientidentität; Daten ausschließlich über Admin-Testsetup angelegt. |
| When | Jede Identität liest/schreibt users/{uid}, role/tier und repräsentative Untercollections über den regelgeprüften Client. |
| Then | Alle Clientoperationen scheitern; Admin-Testsetup bleibt funktionsfähig. Eine allow-true-Mutation muss scheitern. |

**Zielstellen:** ` tests/rules/firestore.rules.test.mjs ` (vorgeschlagen)

**Wiederverwenden:** [firebase.json](../../../firebase.json), [tests/e2e/README.md](../../../tests/e2e/README.md)

**Validierung nach Implementierung:** ` Separaten Rules-Runner mit dem lokalen Demo-Emulator einrichten; nicht den bestehenden Vitest-Glob oder Admin-SDK als Rules-Test verwenden. `

**Gezielte Negativkontrolle:** Temporär nur im Test-Ruletext write für users/{uid} erlauben; Owner-Schreibtest muss rot werden.


<a id="g-002"></a>

## G-002 · Reguläre Usage mit echten Firestore-Transaktionen absichern

**P1 · missing_integration** · Verträge: [QUOTA-01](matrix.md#quota-01) · Paket: [WP-07](work-packages.md#wp-07)

**Produktbeleg:** [app/services/usage_repository.py](../../../app/services/usage_repository.py#L242) — ` Reserve/consume/claim atomically `; [app/services/usage_repository.py](../../../app/services/usage_repository.py#L779) — ` def _transaction( `

**Vorhandene relevante Prüfungen:**

- [test_same_operation_race_has_exactly_one_authorization](../../../tests/test_usage_authorization.py#L68) — Atomare Autorisierungslogik mit FakeFirestore und Threads. Assertionstellen: [72](../../../tests/test_usage_authorization.py#L72), [73](../../../tests/test_usage_authorization.py#L73), [76](../../../tests/test_usage_authorization.py#L76), [77](../../../tests/test_usage_authorization.py#L77).
- [test_parallel_unique_reservations_cannot_oversubscribe_limit](../../../tests/test_run_usage_repository.py#L112) — Repository-/Transaktionsverträge mit FakeFirestore und Threads. Assertionstellen: [131](../../../tests/test_run_usage_repository.py#L131), [132](../../../tests/test_run_usage_repository.py#L132), [134](../../../tests/test_run_usage_repository.py#L134).

**Suiteweite Gegenprüfung:** Lockbasierte Usage-Fakes testen die Regel; die drei vorhandenen Emulator-Dateien prüfen Agentledger, Chat-Create-Limit, Watch/Share und Promptrevision. Kein Emulatorfall prüft reguläres authorize_operation/Reserve/Consume/Release.

**Suchspur:** 224 versionierte Test-/Hilfsdateien durchsucht, 55 passende Zeilen. Regexe: ` usage_repository|FirestoreUsageRepository `, ` daily_token_admission|authorize_operation|parallel_unique_reservations `. Vollständige Treffer mit Pfad/Zeile in [search-evidence.json](search-evidence.json) unter ` G-002 `.

| Szenario | Erwartung |
|---|---|
| Given | Mehrere Repositoryinstanzen, gleicher UID/UTC-Tag, letzter freier Slot; zusätzlich zweiter Owner. |
| When | Gleiche Operation und verschiedene Run-Keys konkurrieren; Release/Consume/UTC-Wechsel werden kontrolliert verschachtelt. |
| Then | Ein Claimgewinner je Operation, keine Überbuchung, genau ein regulärer Charge, separate Deep-Zähler und unveränderte fremde Daten. Endzustand direkt aus Firestore lesen. |

**Zielstellen:** ` tests/e2e/test_usage_transactions.py ` (vorgeschlagen)

**Wiederverwenden:** [tests/usage_test_support.py](../../../tests/usage_test_support.py), [tests/e2e/test_agent_transactions.py](../../../tests/e2e/test_agent_transactions.py), [app/core/e2e_profile.py](../../../app/core/e2e_profile.py)

**Validierung nach Implementierung:** ` RUN_E2E=1 python -m pytest tests/e2e/test_usage_transactions.py -q (mit sicherem Demo-Emulatorprofil) `

**Gezielte Negativkontrolle:** Claim oder Tagescounter außerhalb der Transaktion verschieben; barrier-gesteuertes Rennen muss dies entdecken.


<a id="g-003"></a>

## G-003 · Chat-Löschen gegen Turn/Completion im Emulator

**P1 · missing_integration** · Verträge: [CHAT-01](matrix.md#chat-01), [CHAT-02](matrix.md#chat-02) · Paket: [WP-08](work-packages.md#wp-08)

**Produktbeleg:** [app/services/chat_store.py](../../../app/services/chat_store.py#L1244) — ` def delete_chat( `; [app/services/chat_store.py](../../../app/services/chat_store.py#L872) — ` def complete_turn( `

**Vorhandene relevante Prüfungen:**

- [test_deleting_chat_state_rejects_late_completion_and_failure_writes](../../../tests/test_chat_history.py#L1484) — Router und ChatStore mit speicherbasiertem Transaktionsmodell. Assertionstellen: [1493](../../../tests/test_chat_history.py#L1493), [1497](../../../tests/test_chat_history.py#L1497), [1505](../../../tests/test_chat_history.py#L1505), [1506](../../../tests/test_chat_history.py#L1506).
- [test_two_workers_cannot_exceed_owner_chat_limit](../../../tests/e2e/test_phase2_transactions.py#L134) — Firestore-Emulatorintegration mit echten SDK-Transaktionen und Threads. Assertionstellen: [149](../../../tests/e2e/test_phase2_transactions.py#L149), [153](../../../tests/e2e/test_phase2_transactions.py#L153).

**Suiteweite Gegenprüfung:** Der bestehende echte Chat-Race schützt das Create-Chat-Limit. Delete/late Complete/Fail werden bislang über gesetzte Fake-Zustände geprüft; das ist kein reales TOCTOU-Rennen.

**Suchspur:** 224 versionierte Test-/Hilfsdateien durchsucht, 15 passende Zeilen. Regexe: ` delet.*complet|complet.*delet|deleting_chat|account_deletion_tombstone `, ` test_two_workers_cannot_exceed_owner_chat_limit `. Vollständige Treffer mit Pfad/Zeile in [search-evidence.json](search-evidence.json) unter ` G-003 `.

| Szenario | Erwartung |
|---|---|
| Given | Aktiver Chat mit pending Turn und separatem fremdem Owner. |
| When | Delete-Marker und Completion/Fail/Create-Turn konkurrieren mit kontrollierten Barrieren; beide zulässigen Commitreihenfolgen testen. |
| Then | Nach abgeschlossener Kaskade keine neuen Antwort-/Context-/Turn-Waisen; vor Delete vollständig committed Daten werden mitgelöscht; fremder Owner unverändert. |

**Zielstellen:** ` tests/e2e/test_chat_lifecycle_transactions.py ` (vorgeschlagen)

**Wiederverwenden:** [tests/test_chat_history.py](../../../tests/test_chat_history.py), [tests/e2e/test_phase2_transactions.py](../../../tests/e2e/test_phase2_transactions.py)

**Validierung nach Implementierung:** ` RUN_E2E=1 python -m pytest tests/e2e/test_chat_lifecycle_transactions.py -q (Demo-Emulator) `

**Gezielte Negativkontrolle:** Den active/deleting-Read aus der Completion-Transaktion entfernen; Late-Write-Szenario muss rot werden.


<a id="g-004"></a>

## G-004 · Vollständige Kontokaskade und API-Cleanup prüfen

**P1 · missing_integration** · Verträge: [AUTH-03](matrix.md#auth-03) · Paket: [WP-09](work-packages.md#wp-09)

**Produktbeleg:** [app/services/account_deletion.py](../../../app/services/account_deletion.py#L93) — ` areas = ( `; [app/services/api_account_cleanup.py](../../../app/services/api_account_cleanup.py#L85) — ` def cleanup_uid( `; [app/services/api_account_cleanup.py](../../../app/services/api_account_cleanup.py#L135) — ` def retry_pending( `

**Vorhandene relevante Prüfungen:**

- [test_failed_area_remains_pending_and_only_that_area_is_retried](../../../tests/test_account_deletion_retry.py#L69) — Service mit In-Memory-Datenbank. Assertionstellen: [157](../../../tests/test_account_deletion_retry.py#L157), [158](../../../tests/test_account_deletion_retry.py#L158), [159](../../../tests/test_account_deletion_retry.py#L159), [160](../../../tests/test_account_deletion_retry.py#L160), [161](../../../tests/test_account_deletion_retry.py#L161), [162](../../../tests/test_account_deletion_retry.py#L162), [163](../../../tests/test_account_deletion_retry.py#L163), [164](../../../tests/test_account_deletion_retry.py#L164), [165](../../../tests/test_account_deletion_retry.py#L165), [166](../../../tests/test_account_deletion_retry.py#L166), [167](../../../tests/test_account_deletion_retry.py#L167), [168](../../../tests/test_account_deletion_retry.py#L168), [170](../../../tests/test_account_deletion_retry.py#L170), [171](../../../tests/test_account_deletion_retry.py#L171), [172](../../../tests/test_account_deletion_retry.py#L172), [173](../../../tests/test_account_deletion_retry.py#L173).
- [test_delete_account_cascades_into_the_owner_chats](../../../tests/test_account_deletion_chats.py#L98) — API mit Service-Double. Assertionstellen: [102](../../../tests/test_account_deletion_chats.py#L102), [103](../../../tests/test_account_deletion_chats.py#L103), [104](../../../tests/test_account_deletion_chats.py#L104).

**Suiteweite Gegenprüfung:** Endpointtest ersetzt gesamten Löschservice, Retrytest die eigentlichen Bereichslöschungen. API-cleanup_uid/retry_pending sind im regulären Branchlauf vollständig unausgeführt. Emulator nutzt nur Teilkaskaden als Teardown.

**Suchspur:** 224 versionierte Test-/Hilfsdateien durchsucht, 28 passende Zeilen. Regexe: ` FirestoreAccountDeletion|FirestoreApiAccountCleanup|cleanup_uid|retry_pending `, ` completed_areas|_delete_api_access `. Vollständige Treffer mit Pfad/Zeile in [search-evidence.json](search-evidence.json) unter ` G-004 `.

| Szenario | Erwartung |
|---|---|
| Given | Eigene Daten in allen 14 Kaskadenbereichen plus Kontrollowner; Firebase Auth/Mail/Telegram-Transport bleiben externe Doubles. |
| When | Löschung mit einem gezielten Bereichs-/Checkpointfehler, anschließend neuer Serviceprozess/Instanz und Retry; parallel bereits authentifizierter Write. |
| Then | Nur fehlgeschlagene Bereiche werden wiederholt, alle eigenen Daten entfernt, fremde Daten erhalten, pending ehrlich bis Abschluss; Sperre verhindert Neubefüllung. |

**Zielstellen:** [tests/test_api_account_cleanup.py](../../../tests/test_api_account_cleanup.py), ` tests/e2e/test_account_deletion_transactions.py ` (vorgeschlagen)

**Wiederverwenden:** [tests/test_account_deletion_retry.py](../../../tests/test_account_deletion_retry.py), [tests/test_chat_history.py](../../../tests/test_chat_history.py)

**Validierung nach Implementierung:** ` python -m pytest tests/test_api_account_cleanup.py tests/test_account_deletion_retry.py -q; anschließend neuer Emulator-Kaskadentest `

**Gezielte Negativkontrolle:** Eine Kaskadenoperation durch No-op ersetzen oder pending vorzeitig löschen; Residualdaten-/Sperrassertion muss rot werden.


<a id="g-005"></a>

## G-005 · API-Neustart-Recovery und Retention tatsächlich ausführen

**P1 · missing_case** · Verträge: [API-02](matrix.md#api-02) · Paket: [WP-11](work-packages.md#wp-11)

**Produktbeleg:** [app/services/api_consensus_runner.py](../../../app/services/api_consensus_runner.py#L241) — ` def recover_persisted_runs( `; [app/services/api_consensus_runner.py](../../../app/services/api_consensus_runner.py#L211) — ` def cleanup_expired_runs( `; [app/services/api_run_repository.py](../../../app/services/api_run_repository.py#L265) — ` def backfill_retention( `

**Vorhandene relevante Prüfungen:**

- [test_runner_claim_prevents_duplicate_usage_and_provider_start](../../../tests/test_consensus_api.py#L493) — Main-App-API und Runner mit Repository-/LLM-/Scheduler-Doubles; einzelne Quelltextverträge. Assertionstellen: [542](../../../tests/test_consensus_api.py#L542), [543](../../../tests/test_consensus_api.py#L543), [544](../../../tests/test_consensus_api.py#L544).
- [test_expired_post_provider_worker_keeps_consumed_usage](../../../tests/test_consensus_api.py#L728) — Main-App-API und Runner mit Repository-/LLM-/Scheduler-Doubles; einzelne Quelltextverträge. Assertionstellen: [750](../../../tests/test_consensus_api.py#L750).

**Suiteweite Gegenprüfung:** Claims/Einzel-Expiry-Helfer sind belegt. Die Recovery-/Retention-Orchestrierung und Legacy-Backfill werden von keinem regulären Test ausgeführt; suiteweite Symbolsuche findet keinen eigenen Aufruf.

**Suchspur:** 224 versionierte Test-/Hilfsdateien durchsucht, 4 passende Zeilen. Regexe: ` recover_persisted_runs|cleanup_expired_runs|backfill_retention `, ` fail_expired_run|expired_post_provider|expired_pre_provider `. Vollständige Treffer mit Pfad/Zeile in [search-evidence.json](search-evidence.json) unter ` G-005 `.

| Szenario | Erwartung |
|---|---|
| Given | Persistierte accepted/reserved/running/terminal Runs, abgelaufene und frische Leases, alte Runs ohne expires_at. |
| When | Recovery zweimal und nach simuliertem Prozessneustart ausführen; Scan-/Reserve-/Schedulefehler pro Fall injizieren. |
| Then | Nur pre-provider Arbeit wird eingeplant; unklare laufende Arbeit niemals doppelt generiert; Reserven korrekt freigegeben/Verbrauch erhalten; Retention löscht Run und Mapping konsistent und erhält noch gültige Daten. |

**Zielstellen:** ` tests/test_api_run_recovery.py ` (vorgeschlagen), [tests/test_api_run_repository.py](../../../tests/test_api_run_repository.py)

**Wiederverwenden:** [tests/test_consensus_api.py](../../../tests/test_consensus_api.py), [tests/test_api_run_repository.py](../../../tests/test_api_run_repository.py), [tests/usage_test_support.py](../../../tests/usage_test_support.py)

**Validierung nach Implementierung:** ` python -m pytest tests/test_api_run_recovery.py tests/test_api_run_repository.py tests/test_consensus_api.py -q `

**Gezielte Negativkontrolle:** running in die Requeue-Menge aufnehmen; Provider-/Schedule-Zähler muss den Doppelstart erkennen.


<a id="g-006"></a>

## G-006 · Source-Queue-Leases und Result-Commits im Emulator

**P1 · missing_integration** · Verträge: [SRC-03](matrix.md#src-03) · Paket: [WP-14](work-packages.md#wp-14)

**Produktbeleg:** [app/services/source_check_repository.py](../../../app/services/source_check_repository.py#L358) — ` def claim( `; [app/services/source_check_repository.py](../../../app/services/source_check_repository.py#L406) — ` def finish_package( `

**Vorhandene relevante Prüfungen:**

- [test_expired_lease_reclaims_unfinished_package_and_rejects_stale_worker](../../../tests/test_source_check_repository.py#L214) — Repository mit lockbasiertem FakeDb und Threads. Assertionstellen: [219](../../../tests/test_source_check_repository.py#L219), [221](../../../tests/test_source_check_repository.py#L221), [222](../../../tests/test_source_check_repository.py#L222), [224](../../../tests/test_source_check_repository.py#L224), [225](../../../tests/test_source_check_repository.py#L225), [226](../../../tests/test_source_check_repository.py#L226), [227](../../../tests/test_source_check_repository.py#L227).

**Suiteweite Gegenprüfung:** Repository-/Jobtests verwenden Fake-Transaktionen und manipulierte Worker-IDs. Keine der vorhandenen Emulatordateien ruft diese Queue auf. Kritisch ist der Resultwrite nach konkurrierender Neubeanspruchung/Löschung.

**Suchspur:** 224 versionierte Test-/Hilfsdateien durchsucht, 69 passende Zeilen. Regexe: ` SourceCheckRepository|finish_package|lease_token `, ` transactional|run_transaction `. Vollständige Treffer mit Pfad/Zeile in [search-evidence.json](search-evidence.json) unter ` G-006 `.

| Szenario | Erwartung |
|---|---|
| Given | Ein Job mit zwei Paketen, zwei Workerinstanzen, eigene Key-Affinität und ownergebundener Snapshot. |
| When | Claim/Leaseablauf/Neubeanspruchung und verspäteten finish_package-Write kontrolliert verschachteln; parallel Owner-/Referenzlöschung. |
| Then | Nur aktueller Leaseholder committed, Pakete zählen einmal, keine wiederbelebten Jobs, Revision/Pagination konsistent; eigene Keys erscheinen in keinem Dokument. |

**Zielstellen:** ` tests/e2e/test_source_check_transactions.py ` (vorgeschlagen)

**Wiederverwenden:** [tests/test_source_check_repository.py](../../../tests/test_source_check_repository.py), [tests/test_source_check_jobs.py](../../../tests/test_source_check_jobs.py), [tests/e2e/test_prompt_config_transactions.py](../../../tests/e2e/test_prompt_config_transactions.py)

**Validierung nach Implementierung:** ` RUN_E2E=1 python -m pytest tests/e2e/test_source_check_transactions.py -q (Demo-Emulator) `

**Gezielte Negativkontrolle:** Leasevergleich beim Commit entfernen; verspätetes Ergebnis muss den Test scheitern lassen.


<a id="g-007"></a>

## G-007 · Undo-Konflikt, Ablauf und Wiederholung

**P1 · assertion_gap** · Verträge: [MEM-02](matrix.md#mem-02) · Paket: [WP-10](work-packages.md#wp-10)

**Produktbeleg:** [app/services/memory_edit.py](../../../app/services/memory_edit.py#L523) — ` def undo( `; [app/services/memory_edit.py](../../../app/services/memory_edit.py#L557) — ` if current_revision != int(revision.get `

**Vorhandene relevante Prüfungen:**

- [test_replace_is_revision_checked_and_undo_restores_exact_content](../../../tests/test_memory_edit.py#L118) — Edit-Service/Repository und Router mit DB-/LLM-Doubles. Assertionstellen: [129](../../../tests/test_memory_edit.py#L129), [143](../../../tests/test_memory_edit.py#L143), [147](../../../tests/test_memory_edit.py#L147), [148](../../../tests/test_memory_edit.py#L148), [159](../../../tests/test_memory_edit.py#L159), [160](../../../tests/test_memory_edit.py#L160), [161](../../../tests/test_memory_edit.py#L161), [162](../../../tests/test_memory_edit.py#L162).

**Suiteweite Gegenprüfung:** Einziger Repository-Undo-Aufruf ist der Erfolgsroundtrip. Entfernen ausschließlich des Revisionskonflikt-Guards im Testprozess lässt alle 14 Memory-Edit-Tests bestehen (Probe M-01). Kein Test setzt vor Undo eine neuere Revision.

**Suchspur:** 224 versionierte Test-/Hilfsdateien durchsucht, 1 passende Zeilen. Regexe: ` undo\(|undo_expired|revision_not_found|invalid_revision `, ` revision_conflict `. Vollständige Treffer mit Pfad/Zeile in [search-evidence.json](search-evidence.json) unter ` G-007 `.

| Szenario | Erwartung |
|---|---|
| Given | Angewandter Patch Revision 4→5; danach expliziter unabhängiger Save auf Revision 6. Separate Fälle: fremder Owner, ungültige/fehlende ID, abgelaufenes Fenster, bereits undone. |
| When | Undo des alten Patches versuchen beziehungsweise identisches Undo wiederholen. |
| Then | Neuere Daten bleiben byte-/feldgleich, Konflikt ist sichtbar und macht keine Writes; Ablauf/Ownerfehler bleiben fail-closed; legitimer Retry erhöht Revision nicht erneut. |

**Zielstellen:** [tests/test_memory_edit.py](../../../tests/test_memory_edit.py)

**Wiederverwenden:** [tests/test_memory_edit.py](../../../tests/test_memory_edit.py)

**Validierung nach Implementierung:** ` python -m pytest tests/test_memory_edit.py -q `

**Gezielte Negativkontrolle:** Probe M-01 (Guard current_revision != after_revision entfernt) muss nach Ergänzung rot werden.


<a id="g-008"></a>

## G-008 · Memory-Patch gegen konkurrierenden Save und Kontolöschung

**P1 · missing_case** · Verträge: [MEM-02](matrix.md#mem-02), [AUTH-03](matrix.md#auth-03) · Paket: [WP-10](work-packages.md#wp-10)

**Produktbeleg:** [app/services/memory_edit.py](../../../app/services/memory_edit.py#L439) — ` def apply_patch( `; [app/services/memory_edit.py](../../../app/services/memory_edit.py#L473) — ` if current_revision != int(request.get `

**Vorhandene relevante Prüfungen:**

- [test_replace_is_revision_checked_and_undo_restores_exact_content](../../../tests/test_memory_edit.py#L118) — Edit-Service/Repository und Router mit DB-/LLM-Doubles. Assertionstellen: [129](../../../tests/test_memory_edit.py#L129), [143](../../../tests/test_memory_edit.py#L143), [147](../../../tests/test_memory_edit.py#L147), [148](../../../tests/test_memory_edit.py#L148), [159](../../../tests/test_memory_edit.py#L159), [160](../../../tests/test_memory_edit.py#L160), [161](../../../tests/test_memory_edit.py#L161), [162](../../../tests/test_memory_edit.py#L162).

**Suiteweite Gegenprüfung:** Memory-Edit-Fixture ersetzt ensure_account_write_allowed vollständig. apply_patch-Konfliktzweig wurde nicht ausgeführt. Guardtests anderer Repositories schützen diese konkreten Edit/Undo-Mutationen nicht.

**Suchspur:** 224 versionierte Test-/Hilfsdateien durchsucht, 7 passende Zeilen. Regexe: ` memory_edit.*ensure_account|ensure_account_write_allowed `, ` baseline_revision|revision_conflict `. Vollständige Treffer mit Pfad/Zeile in [search-evidence.json](search-evidence.json) unter ` G-008 `.

| Szenario | Erwartung |
|---|---|
| Given | Reservierter Edit, danach neuer manueller Save oder persistierter Account-Tombstone, anschließend verspätete Providerantwort. |
| When | apply_patch sowie reserve/undo mit realem Guard aufrufen; auch Commitfehler nach mehreren geplanten Writes injizieren. |
| Then | Kein Überschreiben neuerer Memory, keine Wiederanlage nach Löschung, keine partiellen Profile-/Request-/Revisionswrites. Bereits beanspruchte Kosten nicht still zurückerfinden. |

**Zielstellen:** [tests/test_memory_edit.py](../../../tests/test_memory_edit.py), ` tests/e2e/test_memory_edit_transactions.py ` (vorgeschlagen)

**Wiederverwenden:** [tests/test_memory_edit.py](../../../tests/test_memory_edit.py), [app/services/persistence_guard.py](../../../app/services/persistence_guard.py)

**Validierung nach Implementierung:** ` python -m pytest tests/test_memory_edit.py -q; ergänzend Memory-Emulatortest `

**Gezielte Negativkontrolle:** Guard entfernen oder Revisionsvergleich deaktivieren; neue Nichtänderungsassertions müssen scheitern.


<a id="g-009"></a>

## G-009 · Konkurrierende Registrierung ohne Auskunfts-/Benachrichtigungsleck

**P2 · missing_case** · Verträge: [AUTH-01](matrix.md#auth-01) · Paket: [WP-12](work-packages.md#wp-12)

**Produktbeleg:** [app/services/registration.py](../../../app/services/registration.py#L48) — ` except firebase_admin.auth.EmailAlreadyExistsError: `

**Vorhandene relevante Prüfungen:**

- [test_new_user_gets_an_unguessable_server_side_password](../../../tests/test_registration_security.py#L12) — Registrierungsservice mit Firebase-/HTTP-Doubles. Assertionstellen: [24](../../../tests/test_registration_security.py#L24), [25](../../../tests/test_registration_security.py#L25), [27](../../../tests/test_registration_security.py#L27), [28](../../../tests/test_registration_security.py#L28).
- [AuthSessionTests::test_new_and_existing_registration_responses_are_identical](../../../tests/test_auth_session.py#L110) — API mit Auth-/Mail-/Notifier-Doubles. Assertionstellen: [141](../../../tests/test_auth_session.py#L141), [142](../../../tests/test_auth_session.py#L142).

**Suiteweite Gegenprüfung:** Neue und vorhandene Nutzer werden geprüft; Firebase-Create-Race wird nicht simuliert. Die betreffende Exceptionkante wurde nicht ausgeführt.

**Suchspur:** 224 versionierte Test-/Hilfsdateien durchsucht, 8 passende Zeilen. Regexe: ` EmailAlreadyExists|find_or_provision_user|create.race `. Vollständige Treffer mit Pfad/Zeile in [search-evidence.json](search-evidence.json) unter ` G-009 `.

| Szenario | Erwartung |
|---|---|
| Given | Erster Lookup ergibt UserNotFound, create_user meldet EmailAlreadyExists, erneuter Lookup liefert den Gewinner. |
| When | Den realen Provisioner durch /register aufrufen, mit Mail/SDK-Doubles an der äußeren Grenze. |
| Then | Identische öffentliche Antwort und Mailboxpfad wie Bestand; created=False, kein zweiter New-user-Alert, kein Klartextkennwort/UID in Response oder Logs. |

**Zielstellen:** [tests/test_registration_security.py](../../../tests/test_registration_security.py), [tests/test_auth_session.py](../../../tests/test_auth_session.py)

**Wiederverwenden:** [tests/test_auth_session.py](../../../tests/test_auth_session.py)

**Validierung nach Implementierung:** ` python -m pytest tests/test_registration_security.py tests/test_auth_session.py -q `

**Gezielte Negativkontrolle:** Race als created=True zurückgeben oder Exception durchreichen; Response-/Notification-Assertions müssen scheitern.


<a id="g-010"></a>

## G-010 · Historischer API-v1-Source-Check-Adapter

**P1 · missing_case** · Verträge: [API-03](matrix.md#api-03), [SRC-04](matrix.md#src-04) · Paket: [WP-11](work-packages.md#wp-11)

**Produktbeleg:** [app/api/routers/api_v1.py](../../../app/api/routers/api_v1.py#L372) — ` def get_run_source_check( `

**Vorhandene relevante Prüfungen:**

- [test_v4_public_share_rejects_wrong_job_version_on_every_page](../../../tests/test_source_check_api.py#L125) — Router mit SourceCheckRepository/FakeDb und Share-/Topic-Doubles. Assertionstellen: [138](../../../tests/test_source_check_api.py#L138), [140](../../../tests/test_source_check_api.py#L140).

**Suiteweite Gegenprüfung:** Der API-v1-Handler ist im Branchlauf vollständig unausgeführt. Andere Source-Check-Routertests belegen shared check_page, aber nicht API-Key/Run/snapshot-Verkabelung dieses Endpoints.

**Suchspur:** 224 versionierte Test-/Hilfsdateien durchsucht, 43 passende Zeilen. Regexe: ` /api/v1/consensus/runs/.{0,100}source-check `, ` get_run_source_check|expected_snapshot|answer_version `. Vollständige Treffer mit Pfad/Zeile in [search-evidence.json](search-evidence.json) unter ` G-010 `.

| Szenario | Erwartung |
|---|---|
| Given | Historischer eigener v4-Run mit job_id, passender api:run_id/answer_version; kontrollierter Fremdrun und manipulierte Snapshotbindung. |
| When | GET mit gültigem/ungültigem Key, falschem Owner, fehlendem Job, falscher Version sowie cursor/revision/after_revision. |
| Then | Nur passende historische Ressource lesbar; Fehler vor Paketread; 404/409/unchanged/private-no-store korrekt; kein neuer Job oder Providercall. |

**Zielstellen:** [tests/test_consensus_api.py](../../../tests/test_consensus_api.py), [tests/test_source_check_api.py](../../../tests/test_source_check_api.py)

**Wiederverwenden:** [tests/test_source_check_repository.py](../../../tests/test_source_check_repository.py), [tests/test_consensus_api.py](../../../tests/test_consensus_api.py)

**Validierung nach Implementierung:** ` python -m pytest tests/test_consensus_api.py tests/test_source_check_api.py tests/test_source_check_scope.py -q `

**Gezielte Negativkontrolle:** Run-/Antwortbindung entfernen; falsche historische Referenz muss rot werden.


<a id="g-011"></a>

## G-011 · App-POST-/api/share durch den echten Router prüfen

**P1 · missing_case** · Verträge: [SHARE-01](matrix.md#share-01) · Paket: [WP-13](work-packages.md#wp-13)

**Produktbeleg:** [app/api/routers/share.py](../../../app/api/routers/share.py#L302) — ` def create_share( `

**Vorhandene relevante Prüfungen:**

- [ShareFlowTests::test_create_share_is_idempotent](../../../tests/test_share_feature.py#L780) — Große Unit-/Service-/Router-/SSR-Suite mit FakeDb und lokalen Cachethreads. Assertionstellen: [790](../../../tests/test_share_feature.py#L790), [791](../../../tests/test_share_feature.py#L791), [792](../../../tests/test_share_feature.py#L792).

**Suiteweite Gegenprüfung:** Snapshotservice ist breit geprüft, HTTP-POST-Adapter im regulären Lauf gar nicht ausgeführt. API-v1-Publish ist ein anderer Adapter; Browser-Share-Modal liefert keinen aktuellen erfolgreichen Integrationstest.

**Suchspur:** 224 versionierte Test-/Hilfsdateien durchsucht, 26 passende Zeilen. Regexe: ` create_share\(|["\x27]/api/share["\x27] `, ` create_share_from_pending `. Vollständige Treffer mit Pfad/Zeile in [search-evidence.json](search-evidence.json) unter ` G-011 `.

| Szenario | Erwartung |
|---|---|
| Given | Gültiger eigener Pending-Result, fremder/abgelaufener Result und authloser Request. |
| When | POST /api/share über main.app oder App mit denselben Handlern/Middleware, mit echtem Snapshotservice und Fake-DB. |
| Then | UID/visibility/result_id werden richtig weitergegeben, Owner/Quota/Statusfehler korrekt übersetzt, keine Clientkopie wird publiziert, Retry hat gleiche Share-ID. |

**Zielstellen:** [tests/test_share_feature.py](../../../tests/test_share_feature.py)

**Wiederverwenden:** [tests/test_share_feature.py](../../../tests/test_share_feature.py), [tests/test_bookmarks.py](../../../tests/test_bookmarks.py)

**Validierung nach Implementierung:** ` python -m pytest tests/test_share_feature.py -q `

**Gezielte Negativkontrolle:** Owner durch fremde UID ersetzen oder visibility ignorieren; Assertions auf gespeicherte Ressource müssen scheitern.


<a id="g-012"></a>

## G-012 · user_status-Adapter einschließlich Free-Admin und Ausfällen

**P1 · missing_case** · Verträge: [QUOTA-02](matrix.md#quota-02), [AUTH-02](matrix.md#auth-02) · Paket: [WP-12](work-packages.md#wp-12)

**Produktbeleg:** [app/api/routers/users.py](../../../app/api/routers/users.py#L54) — ` def get_user_status( `

**Vorhandene relevante Prüfungen:**

Kein direkter repräsentativer Testbeleg für diese Grenze; Suchtreffer und verwandte Verträge sind separat berücksichtigt.

**Suiteweite Gegenprüfung:** JS-/Browsertests konsumieren vorgegebene /user_status-Payloads; kein regulärer Request führt diesen Handler aus. Damit wird die echte Kombination aus Tarif, Adminrolle und Limits nicht geprüft.

**Suchspur:** 224 versionierte Test-/Hilfsdateien durchsucht, 26 passende Zeilen. Regexe: ` /user_status|get_user_status|checkUserStatusOnLoad `. Vollständige Treffer mit Pfad/Zeile in [search-evidence.json](search-evidence.json) unter ` G-012 `.

| Szenario | Erwartung |
|---|---|
| Given | Free/Plus/Pro, jeweils Admin/Nonadmin soweit zulässig; gültiges, fehlendes und ungültiges Bearer-Token; Tier-Read-Ausfall. |
| When | GET /user_status am echten Router ausführen. |
| Then | Payloadflags und Limits stimmen mit serverseitigen Entitlements überein; Free-Admin hat Agentzugriff ohne Pro zu werden; Tierausfall gibt keine Rechte und bleibt ausdrücklich temporär. |

**Zielstellen:** ` tests/test_user_status.py ` (vorgeschlagen)

**Wiederverwenden:** [tests/test_tier_cache.py](../../../tests/test_tier_cache.py), [tests/test_account_tier_admin.py](../../../tests/test_account_tier_admin.py), [tests/js/plus-tier-gates.test.mjs](../../../tests/js/plus-tier-gates.test.mjs)

**Validierung nach Implementierung:** ` python -m pytest tests/test_user_status.py tests/test_tier_cache.py tests/test_plus_tier.py -q `

**Gezielte Negativkontrolle:** agent_access nur an Pro binden oder Plus als Pro ausgeben; jeweilige Payloadassertion muss scheitern.


<a id="g-013"></a>

## G-013 · Watch-PATCH/DELETE und Telegram-Link/Test als HTTP-Vertrag

**P2 · missing_case** · Verträge: [WATCH-01](matrix.md#watch-01), [WATCH-04](matrix.md#watch-04) · Paket: [WP-15](work-packages.md#wp-15)

**Produktbeleg:** [app/api/routers/watch.py](../../../app/api/routers/watch.py#L105) — ` def patch_watch( `; [app/api/routers/watch.py](../../../app/api/routers/watch.py#L194) — ` def remove_watch( `; [app/api/routers/watch.py](../../../app/api/routers/watch.py#L133) — ` def create_telegram_link( `; [app/api/routers/watch.py](../../../app/api/routers/watch.py#L149) — ` def test_telegram( `

**Vorhandene relevante Prüfungen:**

- [WatchCrudTests::test_free_create_list_update_pause_delete](../../../tests/test_watch_feature.py#L174) — Große Service-/Scheduler-/Router-/Mailformat-Suite mit DB-/LLM-/Versand-Doubles plus UI-Sourceverträge. Assertionstellen: [176](../../../tests/test_watch_feature.py#L176), [177](../../../tests/test_watch_feature.py#L177), [178](../../../tests/test_watch_feature.py#L178), [179](../../../tests/test_watch_feature.py#L179), [180](../../../tests/test_watch_feature.py#L180), [181](../../../tests/test_watch_feature.py#L181), [182](../../../tests/test_watch_feature.py#L182), [185](../../../tests/test_watch_feature.py#L185), [187](../../../tests/test_watch_feature.py#L187), [189](../../../tests/test_watch_feature.py#L189).
- [WatchRouteTests::test_telegram_connection_routes_and_webhook_secret](../../../tests/test_watch_feature.py#L2501) — Große Service-/Scheduler-/Router-/Mailformat-Suite mit DB-/LLM-/Versand-Doubles plus UI-Sourceverträge. Assertionstellen: [2509](../../../tests/test_watch_feature.py#L2509), [2510](../../../tests/test_watch_feature.py#L2510), [2514](../../../tests/test_watch_feature.py#L2514), [2522](../../../tests/test_watch_feature.py#L2522), [2523](../../../tests/test_watch_feature.py#L2523).

**Suiteweite Gegenprüfung:** Service-CRUD und einzelne Connection-/Webhook-Routen sind vorhanden. Diese vier Handler sind im regulären Lauf unausgeführt; Source-/Browser-Matches ersetzen sie mit Payloads.

**Suchspur:** 224 versionierte Test-/Hilfsdateien durchsucht, 1 passende Zeilen. Regexe: ` patch_watch|remove_watch|create_telegram_link|test_telegram\( `, ` /api/watch/|/api/my/telegram/(link|test) `. Vollständige Treffer mit Pfad/Zeile in [search-evidence.json](search-evidence.json) unter ` G-013 `.

| Szenario | Erwartung |
|---|---|
| Given | Eigene/fremde Watch, verbundenes/unverbundenes Telegram, gültige/ungültige Felder, Servicefehler. |
| When | Reale HTTP-Methoden mit Auth und strukturierten Fehlern durchlaufen. |
| Then | Ownerprüfung vor Mutation, Patchallowlist/Tier/Schedule unverändert durchgereicht, Delete beendet passend Brief/Watch, Link/Test führt nicht ohne autorisierten Owner aus. |

**Zielstellen:** [tests/test_watch_feature.py](../../../tests/test_watch_feature.py)

**Wiederverwenden:** [tests/test_watch_feature.py](../../../tests/test_watch_feature.py)

**Validierung nach Implementierung:** ` python -m pytest tests/test_watch_feature.py -q `

**Gezielte Negativkontrolle:** PATCH als falscher Owner oder Testnachricht ohne Verbindung zulassen; Fehler-/Nichtaufrufassertion muss scheitern.


<a id="g-014"></a>

## G-014 · Topic-Admin-Auth/PUT sowie öffentliche Adapter

**P1 · missing_case** · Verträge: [TOPIC-01](matrix.md#topic-01), [TOPIC-04](matrix.md#topic-04) · Paket: [WP-16](work-packages.md#wp-16)

**Produktbeleg:** [app/api/routers/topics.py](../../../app/api/routers/topics.py#L133) — ` def _require_admin( `; [app/api/routers/topics.py](../../../app/api/routers/topics.py#L650) — ` async def admin_update_topic( `; [app/api/routers/topics.py](../../../app/api/routers/topics.py#L247) — ` async def topics_hub( `; [app/api/routers/topics.py](../../../app/api/routers/topics.py#L285) — ` async def sitemap_topics( `; [app/api/routers/topics.py](../../../app/api/routers/topics.py#L526) — ` async def follow_topic( `

**Vorhandene relevante Prüfungen:**

- [test_admin_topic_api_creates_updates_and_versions_without_share_data](../../../tests/test_topics_feature.py#L1037) — Große Service-/Router-/SSR-Suite mit FakeFirestore; einzelner echter SDK-Queryaufbau mit RPC-Mock. Assertionstellen: [1049](../../../tests/test_topics_feature.py#L1049), [1054](../../../tests/test_topics_feature.py#L1054), [1055](../../../tests/test_topics_feature.py#L1055), [1057](../../../tests/test_topics_feature.py#L1057), [1058](../../../tests/test_topics_feature.py#L1058), [1061](../../../tests/test_topics_feature.py#L1061), [1062](../../../tests/test_topics_feature.py#L1062), [1063](../../../tests/test_topics_feature.py#L1063).

**Suiteweite Gegenprüfung:** Der Testname „creates_updates“ enthält keinen PUT; Adminprüfung ist ersetzt. Hub/Sitemap/Follow und echter topics._require_admin werden im regulären Lauf nicht ausgeführt; Servicetests sind kein Routerbeleg.

**Suchspur:** 224 versionierte Test-/Hilfsdateien durchsucht, 23 passende Zeilen. Regexe: ` admin_update_topic|topics_hub|sitemap_topics|follow_topic|_require_admin `, ` /api/admin/topics|/sitemap-topics.xml `. Vollständige Treffer mit Pfad/Zeile in [search-evidence.json](search-evidence.json) unter ` G-014 `.

| Szenario | Erwartung |
|---|---|
| Given | Admin, normaler Nutzer, ungültiges Token; aktive/noindex/archivierte Topics und Follow-Challenges. |
| When | PUT /api/admin/topics/{id}, GET /topics, GET /sitemap-topics.xml und Follow-POST an echten Routern ausführen. |
| Then | Adminprüfung vor Service, actor_uid/ID-Token-Allowlist korrekt, keine privaten/archivierten Hub-/Sitemap-Leaks; XML escaped; Follow neutral und ohne Doppelmail. |

**Zielstellen:** [tests/test_topics_feature.py](../../../tests/test_topics_feature.py)

**Wiederverwenden:** [tests/test_topics_feature.py](../../../tests/test_topics_feature.py), [tests/test_auth_revocation.py](../../../tests/test_auth_revocation.py)

**Validierung nach Implementierung:** ` python -m pytest tests/test_topics_feature.py tests/test_auth_revocation.py -q `

**Gezielte Negativkontrolle:** Admincheck aus PUT entfernen; Nonadmin-Test muss vor Mutation rot werden.


<a id="g-015"></a>

## G-015 · Admin-Benchmark-Routen und Reportviewer

**P2 · missing_case** · Verträge: [BENCH-03](matrix.md#bench-03) · Paket: [WP-22](work-packages.md#wp-22)

**Produktbeleg:** [app/api/routers/admin.py](../../../app/api/routers/admin.py#L787) — ` def admin_list_benchmark_runs( `; [app/api/routers/admin.py](../../../app/api/routers/admin.py#L801) — ` def admin_get_benchmark_run( `; [static/js/admin-benchmark.js](../../../static/js/admin-benchmark.js#L26) — ` async function `

**Vorhandene relevante Prüfungen:**

- [test_publish_run_dir_stores_compact_report_only](../../../tests/test_benchmark_reports.py#L76) — Report-Publisher mit FakeCollection. Assertionstellen: [83](../../../tests/test_benchmark_reports.py#L83), [86](../../../tests/test_benchmark_reports.py#L86), [87](../../../tests/test_benchmark_reports.py#L87), [88](../../../tests/test_benchmark_reports.py#L88), [89](../../../tests/test_benchmark_reports.py#L89), [90](../../../tests/test_benchmark_reports.py#L90).

**Suiteweite Gegenprüfung:** Reader/Publish-Services sind belegt; beide Admin-HTTP-Handler im regulären Lauf unausgeführt und der Viewer nur statisch referenziert.

**Suchspur:** 224 versionierte Test-/Hilfsdateien durchsucht, 3 passende Zeilen. Regexe: ` /api/admin/benchmark|admin_list_benchmark_runs|admin_get_benchmark_run|admin-benchmark.js `. Vollständige Treffer mit Pfad/Zeile in [search-evidence.json](search-evidence.json) unter ` G-015 `.

| Szenario | Erwartung |
|---|---|
| Given | Ein kompakter Report, fehlende/traversierende ID, Backendfehler und Nonadmin. |
| When | Listen-/Detailroute und Viewerladung inklusive Auswahlwechsel/Fehlerantwort ausführen. |
| Then | Auth vor Read, kompakte Daten ohne Rohprompts, 404/Fehler korrekt und kein Stale-Report nach Auswahlwechsel. |

**Zielstellen:** [tests/test_benchmark_reports.py](../../../tests/test_benchmark_reports.py), ` tests/js/admin-benchmark.test.mjs ` (vorgeschlagen)

**Wiederverwenden:** [tests/test_benchmark_report_reader.py](../../../tests/test_benchmark_report_reader.py), [tests/test_benchmark_reports.py](../../../tests/test_benchmark_reports.py), [tests/js/helpers/appWindow.mjs](../../../tests/js/helpers/appWindow.mjs)

**Validierung nach Implementierung:** ` python -m pytest tests/test_benchmark_reports.py tests/test_benchmark_report_reader.py -q; npm test -- tests/js/admin-benchmark.test.mjs `

**Gezielte Negativkontrolle:** Adminprüfung überspringen oder verspätetes erstes Result rendern; negative Fälle müssen rot werden.


<a id="g-016"></a>

## G-016 · Claim-Identity-Judge selbst prüfen

**P2 · missing_case** · Verträge: [TOPIC-02](matrix.md#topic-02) · Paket: [WP-17](work-packages.md#wp-17)

**Produktbeleg:** [app/services/llm/consensus_engine.py](../../../app/services/llm/consensus_engine.py#L2358) — ` def query_claim_identity( `

**Vorhandene relevante Prüfungen:**

- [test_claim_identity_result_maps_claims_onto_the_keys_they_continue](../../../tests/test_topics_feature.py#L1019) — Große Service-/Router-/SSR-Suite mit FakeFirestore; einzelner echter SDK-Queryaufbau mit RPC-Mock. Assertionstellen: [1034](../../../tests/test_topics_feature.py#L1034).
- [test_claim_identity_falls_back_to_fresh_keys_when_the_judge_is_unavailable](../../../tests/test_topics_feature.py#L998) — Große Service-/Router-/SSR-Suite mit FakeFirestore; einzelner echter SDK-Queryaufbau mit RPC-Mock. Assertionstellen: [1016](../../../tests/test_topics_feature.py#L1016).

**Suiteweite Gegenprüfung:** Vorhandene Topicfälle ersetzen query_claim_identity. Seine komplette Validierung/Fallbackschleife ist unausgeführt; getestete Ledgerkeys sind bereits vorgegeben.

**Suchspur:** 224 versionierte Test-/Hilfsdateien durchsucht, 3 passende Zeilen. Regexe: ` query_claim_identity|known_keys|claim_identity_result `. Vollständige Treffer mit Pfad/Zeile in [search-evidence.json](search-evidence.json) unter ` G-016 `.

| Szenario | Erwartung |
|---|---|
| Given | Bekannte Keys und neue Claims, synthetischer Transport mit gültigen/ungültigen matches und mehreren Versuchsergebnissen. |
| When | Realen Helper mit unbekannten/doppelten Keys, wiederholten/out-of-range/nichtnumerischen Indices, malformed JSON, leerem Input und Providerfehler aufrufen. |
| Then | Nur zulässige eindeutige Zuordnungen, begrenzte Inputs, definierter Fallback ohne Topicabbruch und redigierte Logs. Bool/Float-Indexsemantik vor Fix ausdrücklich entscheiden. |

**Zielstellen:** ` tests/test_claim_identity_judge.py ` (vorgeschlagen)

**Wiederverwenden:** [tests/test_consensus_engine.py](../../../tests/test_consensus_engine.py), [tests/test_topics_feature.py](../../../tests/test_topics_feature.py)

**Validierung nach Implementierung:** ` python -m pytest tests/test_claim_identity_judge.py tests/test_topics_feature.py tests/test_claim_ledger.py -q `

**Gezielte Negativkontrolle:** known_keys-/used-Prüfung entfernen; erfundene/mehrfach vergebene IDs müssen erkannt werden.


<a id="g-017"></a>

## G-017 · SEO-Readadapter hinter den Service-Fakes

**P2 · missing_case** · Verträge: [SEO-02](matrix.md#seo-02), [SEO-04](matrix.md#seo-04) · Paket: [WP-18](work-packages.md#wp-18)

**Produktbeleg:** [app/services/seo_repository.py](../../../app/services/seo_repository.py#L247) — ` def list_metrics_for_pages( `; [app/services/seo_repository.py](../../../app/services/seo_repository.py#L375) — ` def last_run( `; [app/services/seo_repository.py](../../../app/services/seo_repository.py#L426) — ` def list_judgments( `

**Vorhandene relevante Prüfungen:**

- [test_review_reuses_overview_context_without_second_metric_scan](../../../tests/test_seo_weekly_review.py#L298) — Review-Service mit Repository-/Judge-/Action-Doubles. Assertionstellen: [346](../../../tests/test_seo_weekly_review.py#L346), [347](../../../tests/test_seo_weekly_review.py#L347), [348](../../../tests/test_seo_weekly_review.py#L348).

**Suiteweite Gegenprüfung:** Reviewtests prüfen vorgegebene Repositoryantworten. Konkretes BatchGet-Mapping, aktuellster Lauf und begrenzte Judgmentlisten sind im realen Repository unausgeführt.

**Suchspur:** 224 versionierte Test-/Hilfsdateien durchsucht, 33 passende Zeilen. Regexe: ` list_metrics_for_pages|list_judgments|last_run|latest_review|recent_reviews `. Vollständige Treffer mit Pfad/Zeile in [search-evidence.json](search-evidence.json) unter ` G-017 `.

| Szenario | Erwartung |
|---|---|
| Given | Mehrere Page-IDs, doppelte Inputs, über 400 Dokumentrefs, fehlende/ungeordnete Snapshots, leere und naive/aware Zeitstempel. |
| When | Reale Repositorymethoden mit SDK-kompatiblem Double, ergänzend Emulator für Queries, aufrufen. |
| Then | Exakte Seiten-/Datumszuordnung, keine Vermischung, bounded Batchgrößen, korrekt sortierte neueste Daten und deterministische leere Ergebnisse; Datenfehler nicht als Nulltraffic ausgeben. |

**Zielstellen:** ` tests/test_seo_repository.py ` (vorgeschlagen)

**Wiederverwenden:** [tests/test_seo_data.py](../../../tests/test_seo_data.py), [tests/test_seo_weekly_review.py](../../../tests/test_seo_weekly_review.py)

**Validierung nach Implementierung:** ` python -m pytest tests/test_seo_repository.py tests/test_seo_data.py tests/test_seo_weekly_review.py -q `

**Gezielte Negativkontrolle:** BatchGet-Snapshots nach Rückgabereihenfolge statt Dokumentpfad zuordnen; ungeordnete Fixture muss rot werden.


<a id="g-018"></a>

## G-018 · Topic-Notizen werden erneut als HTML interpretiert

**P1 · observed_behavior_defect** · Verträge: [TOPIC-05](matrix.md#topic-05) · Paket: [WP-20](work-packages.md#wp-20)

**Produktbeleg:** [app/services/claim_ledger.py](../../../app/services/claim_ledger.py#L433) — ` note = str(run.get("change_summary") `; [templates/topic.html](../../../templates/topic.html#L225) — ` data-note="{{ cell.note }}" `; [static/js/topic-page.js](../../../static/js/topic-page.js#L32) — ` read.innerHTML = parts.join `

**Vorhandene relevante Prüfungen:**

- [test_topic_templates_expose_timeline_evidence_follow_and_admin_controls](../../../tests/test_topics_feature.py#L825) — Große Service-/Router-/SSR-Suite mit FakeFirestore; einzelner echter SDK-Queryaufbau mit RPC-Mock. Assertionstellen: [831](../../../tests/test_topics_feature.py#L831), [832](../../../tests/test_topics_feature.py#L832), [833](../../../tests/test_topics_feature.py#L833), [834](../../../tests/test_topics_feature.py#L834), [837](../../../tests/test_topics_feature.py#L837), [838](../../../tests/test_topics_feature.py#L838), [839](../../../tests/test_topics_feature.py#L839), [842](../../../tests/test_topics_feature.py#L842), [846](../../../tests/test_topics_feature.py#L846), [847](../../../tests/test_topics_feature.py#L847), [848](../../../tests/test_topics_feature.py#L848), [850](../../../tests/test_topics_feature.py#L850), [851](../../../tests/test_topics_feature.py#L851), [852](../../../tests/test_topics_feature.py#L852), [853](../../../tests/test_topics_feature.py#L853), [854](../../../tests/test_topics_feature.py#L854), [855](../../../tests/test_topics_feature.py#L855), [856](../../../tests/test_topics_feature.py#L856), [857](../../../tests/test_topics_feature.py#L857), [858](../../../tests/test_topics_feature.py#L858), [859](../../../tests/test_topics_feature.py#L859), [860](../../../tests/test_topics_feature.py#L860).

**Suiteweite Gegenprüfung:** Suite enthält nur Template-/Datenbelege. Lokale DOM-Probe D-01 mit inertem <b id=...>-Text erzeugt ein echtes Element und entfernt die literalen Tags aus dem angezeigten Text. Datenpfad: change_summary→cell.note→escaped Attribut→dataset→innerHTML. Kein externer Exploit oder produktiver XSS-Aufruf wurde ausgeführt.

**Suchspur:** 224 versionierte Test-/Hilfsdateien durchsucht, 1 passende Zeilen. Regexe: ` topic-page|topicStripRead|topicReturn|topic-seen:|readStrip|returningReader `. Vollständige Treffer mit Pfad/Zeile in [search-evidence.json](search-evidence.json) unter ` G-018 `.

| Szenario | Erwartung |
|---|---|
| Given | SSR-escaped Notiz mit wörtlichem HTML, Quotes und Sonderzeichen; normaler/Touch-/historischer/Storage-blockierter Besuch. |
| When | Topicmodul laden und Zelle fokussieren/hovern/antippen; aktuellen und historischen Besuch wiederholen. |
| Then | Notiz bleibt Text, keine aus Notiz erzeugten Elemente/Handler. Touchvorschau, zweite Navigation, Unseen-Marker und historische Storageisolation funktionieren weiterhin. |

**Zielstellen:** ` tests/js/topic-page.test.mjs ` (vorgeschlagen), ` tests/e2e/test_topic_frontend.py ` (vorgeschlagen)

**Wiederverwenden:** [tests/js/helpers/appWindow.mjs](../../../tests/js/helpers/appWindow.mjs), [tests/test_claim_ledger.py](../../../tests/test_claim_ledger.py)

**Validierung nach Implementierung:** ` npm test -- tests/js/topic-page.test.mjs; ergänzend gezielter Topic-Browserfall `

**Gezielte Negativkontrolle:** Aktuelles innerHTML-Verhalten muss am literalen Notiztest scheitern; kein Snapshot akzeptieren, der die Injection festschreibt.


<a id="g-019"></a>

## G-019 · Strukturierte Adminfehler verlieren ihre Nachricht

**P2 · observed_behavior_defect** · Verträge: [ADMIN-02](matrix.md#admin-02) · Paket: [WP-21](work-packages.md#wp-21)

**Produktbeleg:** [static/js/admin-api.js](../../../static/js/admin-api.js#L20) — ` const message = data.error `; [main.py](../../../main.py#L226) — ` content={"error": exc.detail} `; [app/api/routers/admin.py](../../../app/api/routers/admin.py#L570) — ` detail={"error_code": exc.code `

**Vorhandene relevante Prüfungen:**

- [test_configuration_tab_saves_reloads_and_preserves_conflicting_draft](../../../tests/e2e/test_admin_prompt_config.py#L15) — Chromium-Browserintegration mit simulierten Admin-APIs. Assertionstellen: [30](../../../tests/e2e/test_admin_prompt_config.py#L30), [46](../../../tests/e2e/test_admin_prompt_config.py#L46), [47](../../../tests/e2e/test_admin_prompt_config.py#L47), [49](../../../tests/e2e/test_admin_prompt_config.py#L49), [50](../../../tests/e2e/test_admin_prompt_config.py#L50), [51](../../../tests/e2e/test_admin_prompt_config.py#L51), [53](../../../tests/e2e/test_admin_prompt_config.py#L53), [55](../../../tests/e2e/test_admin_prompt_config.py#L55), [56](../../../tests/e2e/test_admin_prompt_config.py#L56), [57](../../../tests/e2e/test_admin_prompt_config.py#L57), [64](../../../tests/e2e/test_admin_prompt_config.py#L64), [65](../../../tests/e2e/test_admin_prompt_config.py#L65), [72](../../../tests/e2e/test_admin_prompt_config.py#L72), [73](../../../tests/e2e/test_admin_prompt_config.py#L73), [74](../../../tests/e2e/test_admin_prompt_config.py#L74), [76](../../../tests/e2e/test_admin_prompt_config.py#L76), [77](../../../tests/e2e/test_admin_prompt_config.py#L77), [78](../../../tests/e2e/test_admin_prompt_config.py#L78), [85](../../../tests/e2e/test_admin_prompt_config.py#L85), [86](../../../tests/e2e/test_admin_prompt_config.py#L86), [88](../../../tests/e2e/test_admin_prompt_config.py#L88), [90](../../../tests/e2e/test_admin_prompt_config.py#L90), [91](../../../tests/e2e/test_admin_prompt_config.py#L91), [92](../../../tests/e2e/test_admin_prompt_config.py#L92), [94](../../../tests/e2e/test_admin_prompt_config.py#L94), [95](../../../tests/e2e/test_admin_prompt_config.py#L95), [96](../../../tests/e2e/test_admin_prompt_config.py#L96), [101](../../../tests/e2e/test_admin_prompt_config.py#L101).

**Suiteweite Gegenprüfung:** Browserkonfliktfixture liefert detail:String und ist nicht ausgeführt. Reale App verpackt strukturierte HTTPException.detail unter error. Probe D-02: detail:Object wird verständlich, error:Object dagegen als [object Object] angezeigt.

**Suchspur:** 224 versionierte Test-/Hilfsdateien durchsucht, 4 passende Zeilen. Regexe: ` createAdminClient|admin-api.js|\[object Object\] `, ` Configuration changed in another session `. Vollständige Treffer mit Pfad/Zeile in [search-evidence.json](search-evidence.json) unter ` G-019 `.

| Szenario | Erwartung |
|---|---|
| Given | createAdminClient mit Responseformen aus main.handle_http_exception, Standard-FastAPI, nicht-JSON und leerem Body. |
| When | Fehlerhafte Adminanfrage einschließlich AccountTierError ausführen. |
| Then | Verständliche erlaubte Nachricht/HTTP-Fallback statt Objektstring; Token-/Statusfehler propagieren, kein zweiter Write. Panelentwurf bleibt bei Konflikt erhalten. |

**Zielstellen:** ` tests/js/admin-api.test.mjs ` (vorgeschlagen), [tests/test_account_tier_admin.py](../../../tests/test_account_tier_admin.py)

**Wiederverwenden:** [tests/e2e/test_admin_prompt_config.py](../../../tests/e2e/test_admin_prompt_config.py), [tests/js/admin-prompt-config.test.mjs](../../../tests/js/admin-prompt-config.test.mjs)

**Validierung nach Implementierung:** ` npm test -- tests/js/admin-api.test.mjs tests/js/admin-prompt-config.test.mjs; python -m pytest tests/test_account_tier_admin.py -q `

**Gezielte Negativkontrolle:** Unveränderter Client muss am main-error-Objektfall rot werden; echten Responseumschlag verwenden.


<a id="g-020"></a>

## G-020 · OG-Test akzeptiert leeres Bild

**P2 · assertion_gap** · Verträge: [SHARE-04](matrix.md#share-04) · Paket: [WP-23](work-packages.md#wp-23)

**Produktbeleg:** [app/services/og_image.py](../../../app/services/og_image.py#L93) — ` def render_share_card( `; [app/api/routers/share.py](../../../app/api/routers/share.py#L488) — ` def share_og_card( `

**Vorhandene relevante Prüfungen:**

- [ShareSeoEnhancementTests::test_og_card_route_and_meta](../../../tests/test_share_feature.py#L2459) — Große Unit-/Service-/Router-/SSR-Suite mit FakeDb und lokalen Cachethreads. Assertionstellen: [2466](../../../tests/test_share_feature.py#L2466), [2467](../../../tests/test_share_feature.py#L2467), [2468](../../../tests/test_share_feature.py#L2468), [2469](../../../tests/test_share_feature.py#L2469), [2470](../../../tests/test_share_feature.py#L2470).
- [ShareSeoEnhancementTests::test_og_card_404_for_private_pages](../../../tests/test_share_feature.py#L2472) — Große Unit-/Service-/Router-/SSR-Suite mit FakeDb und lokalen Cachethreads. Assertionstellen: [2476](../../../tests/test_share_feature.py#L2476).

**Suiteweite Gegenprüfung:** Probe M-02 ersetzt Renderer durch gültiges komplett weißes PNG gleicher Größe: beide OG-Tests bleiben grün. Status/MIME/PNG-Präfix sichern den zugesagten Karteninhalt nicht.

**Suchspur:** 224 versionierte Test-/Hilfsdateien durchsucht, 4 passende Zeilen. Regexe: ` og_image|og\.png|share_card|render_share_card `. Vollständige Treffer mit Pfad/Zeile in [search-evidence.json](search-evidence.json) unter ` G-020 `.

| Szenario | Erwartung |
|---|---|
| Given | Öffentlicher Snapshot mit markanter Frage, bekannten Modell-/Konfliktzahlen und Score; unscored/private/Renderingfehler separat. |
| When | Route und echten Renderer aufrufen, PNG dekodieren; semantische Renderinputs/Zeichenoperationen und stabile Bildinhalte prüfen. |
| Then | 1200×630 PNG enthält Frage/korrekte Kennzahlen, unscored erfindet keinen Score, private/inaktive Seite kein Bild. Deterministische Bildregionen oder toleranter Baselinevergleich statt bloß Bytepräfix. |

**Zielstellen:** ` tests/test_og_image.py ` (vorgeschlagen), [tests/test_share_feature.py](../../../tests/test_share_feature.py)

**Wiederverwenden:** [tests/test_share_feature.py](../../../tests/test_share_feature.py)

**Validierung nach Implementierung:** ` python -m pytest tests/test_og_image.py tests/test_share_feature.py -q `

**Gezielte Negativkontrolle:** Blank-PNG-Probe M-02 muss nach Ergänzung rot werden. Keine variable Font-Rasterisierung als exakter Plattformhash festschreiben.


<a id="g-021"></a>

## G-021 · Analytics-Opt-out ausführen statt Strings suchen

**P2 · assertion_gap** · Verträge: [UI-09](matrix.md#ui-09) · Paket: [WP-24](work-packages.md#wp-24)

**Produktbeleg:** [static/js/analytics-opt-out.js](../../../static/js/analytics-opt-out.js#L3) — ` const flag = `

**Vorhandene relevante Prüfungen:**

- [test_partial_ships_the_self_exclusion_switch](../../../tests/test_analytics_partial.py#L59) — Quelltextverträge. Assertionstellen: [67](../../../tests/test_analytics_partial.py#L67), [68](../../../tests/test_analytics_partial.py#L68), [69](../../../tests/test_analytics_partial.py#L69).

**Suiteweite Gegenprüfung:** Bestehender Test kontrolliert vorhandene Storage-Aufrufe und Scriptreihenfolge. Queryverzweigung oder ein nie ausgeführter Aufruf könnte falsch sein und dennoch bestehen.

**Suchspur:** 224 versionierte Test-/Hilfsdateien durchsucht, 7 passende Zeilen. Regexe: ` analytics-opt-out|notrack|umami.disabled `. Vollständige Treffer mit Pfad/Zeile in [search-evidence.json](search-evidence.json) unter ` G-021 `.

| Szenario | Erwartung |
|---|---|
| Given | notrack=1, 0, anderer/fehlender Wert und Storage mit get/set/remove-Fehlern. |
| When | Originalskript in isoliertem DOM vor einem instrumentierten Trackerstart ausführen. |
| Then | Flag korrekt gesetzt/entfernt/erhalten und vor Trackerbeobachtung wirksam; blockierter Storage bricht Seitenstart nicht ab. |

**Zielstellen:** ` tests/js/analytics-opt-out.test.mjs ` (vorgeschlagen)

**Wiederverwenden:** [tests/js/helpers/appWindow.mjs](../../../tests/js/helpers/appWindow.mjs), [tests/test_analytics_partial.py](../../../tests/test_analytics_partial.py)

**Validierung nach Implementierung:** ` npm test -- tests/js/analytics-opt-out.test.mjs; python -m pytest tests/test_analytics_partial.py -q `

**Gezielte Negativkontrolle:** Bedingungen 1/0 vertauschen oder in unerreichbaren Block stellen; Verhaltenstest muss rot werden.


<a id="g-022"></a>

## G-022 · Account-Reparaturskript ohne Produktionszugriff prüfen

**P1 · missing_case** · Verträge: [TOOLS-01](matrix.md#tools-01) · Paket: [WP-25](work-packages.md#wp-25)

**Produktbeleg:** [scripts/repair_agent_allowance.py](../../../scripts/repair_agent_allowance.py#L16) — ` def main(): `

**Vorhandene relevante Prüfungen:**

Kein direkter repräsentativer Testbeleg für diese Grenze; Suchtreffer und verwandte Verträge sind separat berücksichtigt.

**Suiteweite Gegenprüfung:** Keine Testreferenz und keine ausgeführte Zeile. Service-Recoverytests prüfen nicht --apply-/Projekt-/Umgebungsgrenzen dieses produktionswirksamen CLI.

**Suchspur:** 224 versionierte Test-/Hilfsdateien durchsucht, 0 passende Zeilen. Regexe: ` repair_agent_allowance|Production repair cannot|Configured Firebase project `. Vollständige Treffer mit Pfad/Zeile in [search-evidence.json](search-evidence.json) unter ` G-022 `.

| Szenario | Erwartung |
|---|---|
| Given | Komplett isolierter Subprozess mit Fake-Firebase-Modulen; unterschiedliche Projekt-ID, Test-/Emulatorflags, explizite E-Mail. |
| When | Inspect und --apply sowie ungültige Kombinationen aufrufen; Netzwerkoperationen verbieten. |
| Then | Inspect erzeugt keine Mutation/Providerarbeit; falsches Projekt/Emulator endet vor Kontoreparatur; Apply betrifft genau gewählten UID und ruft bestehende idempotente Recovery auf. |

**Zielstellen:** ` tests/test_repair_agent_allowance_script.py ` (vorgeschlagen)

**Wiederverwenden:** [tests/test_publisher_standalone.py](../../../tests/test_publisher_standalone.py), [tests/test_agent_quota_recovery.py](../../../tests/test_agent_quota_recovery.py)

**Validierung nach Implementierung:** ` python -m pytest tests/test_repair_agent_allowance_script.py tests/test_agent_quota_recovery.py -q `

**Gezielte Negativkontrolle:** --apply- oder Projektguard entfernen; isolierter Aufrufzähler muss unerlaubte Mutation entdecken.


<a id="g-023"></a>

## G-023 · Claim-Key-Backfill-Dry-run, Idempotenz und Datenerhalt

**P2 · missing_case** · Verträge: [TOOLS-01](matrix.md#tools-01) · Paket: [WP-25](work-packages.md#wp-25)

**Produktbeleg:** [scripts/backfill_claim_keys.py](../../../scripts/backfill_claim_keys.py#L41) — ` def backfill_topic( `; [scripts/backfill_claim_keys.py](../../../scripts/backfill_claim_keys.py#L76) — ` def main() `

**Vorhandene relevante Prüfungen:**

Kein direkter repräsentativer Testbeleg für diese Grenze; Suchtreffer und verwandte Verträge sind separat berücksichtigt.

**Suiteweite Gegenprüfung:** Kein Test oder dynamischer Aufruf. Das Script verändert gespeicherte opinion_map-Daten und ruft auch im Dry-run den Judge auf; Dry-run bedeutet laut CLI nur kein DB-Write, nicht kostenlos.

**Suchspur:** 224 versionierte Test-/Hilfsdateien durchsucht, 0 passende Zeilen. Regexe: ` backfill_claim_keys|backfill_topic|Would update `. Vollständige Treffer mit Pfad/Zeile in [search-evidence.json](search-evidence.json) unter ` G-023 `.

| Szenario | Erwartung |
|---|---|
| Given | Historische Runs mit/ohne/teilweisen Keys und fremden opinion_map-Feldern; Fake-Judge/DB. |
| When | Dry-run, normaler Lauf, zweiter Lauf und --force; außerdem MOCK_LLM und fehlende Selektion. |
| Then | Dry-run keine Writes, normal nur zulässige Keys ergänzt, sonstige Felder erhalten, fertige Runs übersprungen; erneuter Lauf idempotent. Kosten-/Scopeverhalten ausdrücklich dokumentiert. |

**Zielstellen:** ` tests/test_backfill_claim_keys.py ` (vorgeschlagen)

**Wiederverwenden:** [tests/test_topics_feature.py](../../../tests/test_topics_feature.py), [tests/test_claim_ledger.py](../../../tests/test_claim_ledger.py)

**Validierung nach Implementierung:** ` python -m pytest tests/test_backfill_claim_keys.py tests/test_claim_ledger.py -q `

**Gezielte Negativkontrolle:** dry_run-Guard entfernen oder gesamte Map durch Keys ersetzen; Write-/Datenerhaltsassertion muss scheitern.


<a id="g-024"></a>

## G-024 · Allgemeine Suite in CI absichern

**P1 · missing_automation** · Verträge: [BUILD-02](matrix.md#build-02), [BUILD-03](matrix.md#build-03) · Paket: [WP-05](work-packages.md#wp-05)

**Produktbeleg:** [.github/workflows/publisher-tests.yml](../../../.github/workflows/publisher-tests.yml#L1) — ` name: `; [package.json](../../../package.json#L9) — ` "test": `

**Vorhandene relevante Prüfungen:**

Kein direkter repräsentativer Testbeleg für diese Grenze; Suchtreffer und verwandte Verträge sind separat berücksichtigt.

**Suiteweite Gegenprüfung:** Die vorhandenen drei Workflows betreffen Publisherregressionen, Publisherjob und Renderrestart. Kein Workflow führt die gesamte reguläre Python-/JS-/Browser-/Emulatorsuite aus.

**Suchspur:** 224 versionierte Test-/Hilfsdateien durchsucht, 693 passende Zeilen. Regexe: ` publisher-tests|pytest|vitest `. Vollständige Treffer mit Pfad/Zeile in [search-evidence.json](search-evidence.json) unter ` G-024 `.

| Szenario | Erwartung |
|---|---|
| Given | Reproduzierbares Python/Node/Java/Chromium-Setup, dokumentierte fehlgeschlagene Tests vorher bearbeitet. |
| When | Allgemeinen CI-Workflow mit getrennten Jobs für Backend, JS, Browser/Emulator und Windows-Einstieg hinzufügen. |
| Then | Keine stillen Skips oder Fehlernormalisierung; JUnit/Reports bei Fehlern hochladen, Demo-Projekt strikt, kein Produktkey. Publisher-CI bleibt eigenständig und leichtgewichtig. |

**Zielstellen:** ` .github/workflows/tests.yml ` (vorgeschlagen), [docs/testing.md](../../testing.md)

**Wiederverwenden:** [dev.ps1](../../../dev.ps1), [tests/e2e/README.md](../../../tests/e2e/README.md), [.github/workflows/publisher-tests.yml](../../../.github/workflows/publisher-tests.yml)

**Validierung nach Implementierung:** ` Neue Jobs auf genau dem integrierten Commit prüfen; kein einzelner Publisher-Erfolg als Gesamtsuite-Erfolg werten. `

**Gezielte Negativkontrolle:** Absichtlich fehlschlagender Test in isoliertem CI-Probelauf muss den zugehörigen Job rot machen.


<a id="g-025"></a>

## G-025 · 267 vorhandene Browserfälle ausführen

**P1 · execution_gap** · Verträge: [BUILD-02](matrix.md#build-02), [UI-06](matrix.md#ui-06) · Paket: [WP-03](work-packages.md#wp-03)

**Produktbeleg:** [tests/e2e/conftest.py](../../../tests/e2e/conftest.py#L126) — ` browser = p.chromium.launch() `

**Vorhandene relevante Prüfungen:**

Kein direkter repräsentativer Testbeleg für diese Grenze; Suchtreffer und verwandte Verträge sind separat berücksichtigt.

**Suiteweite Gegenprüfung:** Alle 267 Browserfälle sind gesammelt und katalogisiert, aber Chromium-Download scheiterte im vorherigen Audit. Das ist ein fehlender Laufnachweis, kein Auftrag 267 Tests neu zu schreiben.

**Suchspur:** 224 versionierte Test-/Hilfsdateien durchsucht, 2 passende Zeilen. Regexe: ` chromium.launch|def browser\( `. Vollständige Treffer mit Pfad/Zeile in [search-evidence.json](search-evidence.json) unter ` G-025 `.

| Szenario | Erwartung |
|---|---|
| Given | Sauber installierter Chromium zur gepinnten Playwrightversion und sicherer Demo-Emulator, gleiche Testselektion. |
| When | Bestehende komplette Browserauswahl ausführen, tatsächliche Fehler klassifizieren und nur notwendige Korrekturen vornehmen. |
| Then | Jeder Fall erhält aktuellen Status; CSS/Focus/Overflow/SSE-Ergebnisse mit Versionen aufbewahren. Kein Ausweichen auf gemockte DOM-Geometrie als Browsernachweis. |

**Zielstellen:** [tests/e2e](../../../tests/e2e), [docs/test-coverage/execution.json](../execution.json)

**Wiederverwenden:** [tests/e2e/README.md](../../../tests/e2e/README.md), [docs/testing.md](../../testing.md)

**Validierung nach Implementierung:** ` python -m playwright install chromium; RUN_E2E=1 python -m pytest tests/e2e -q (sicheres vollständiges Emulatorprofil) `

**Gezielte Negativkontrolle:** Leere/übersprungene Auswahl darf nicht als erfolgreicher Gesamtlauf erscheinen.


<a id="g-026"></a>

## G-026 · Windows-Einstieg tatsächlich validieren

**P2 · execution_gap** · Verträge: [BUILD-02](matrix.md#build-02) · Paket: [WP-04](work-packages.md#wp-04)

**Produktbeleg:** [dev.ps1](../../../dev.ps1#L12) — ` param( `

**Vorhandene relevante Prüfungen:**

Kein direkter repräsentativer Testbeleg für diese Grenze; Suchtreffer und verwandte Verträge sind separat berücksichtigt.

**Suiteweite Gegenprüfung:** Zwölf test_dev_cli-Fälle werden unter Linux explizit übersprungen. Sourcechecks belegen nicht Prozessargumente/Exitcodes des Windows-Einstiegs.

**Suchspur:** 224 versionierte Test-/Hilfsdateien durchsucht, 1 passende Zeilen. Regexe: ` Windows PowerShell entry point|win32 `. Vollständige Treffer mit Pfad/Zeile in [search-evidence.json](search-evidence.json) unter ` G-026 `.

| Szenario | Erwartung |
|---|---|
| Given | Windowsrunner mit PowerShell und isolierten Tool-Doubles/Dependencies. |
| When | Alle vorhandenen test_dev_cli-Fälle und repräsentative dev.ps1 check-Aufrufe ausführen. |
| Then | Zwölf bislang übersprungene Fälle haben echten Pass/Fail-Status; Exitcodes und Pfad-/Argumentweitergabe funktionieren. |

**Zielstellen:** [tests/test_dev_cli.py](../../../tests/test_dev_cli.py), ` .github/workflows/tests.yml ` (vorgeschlagen)

**Wiederverwenden:** [docs/testing.md](../../testing.md), [dev.ps1](../../../dev.ps1)

**Validierung nach Implementierung:** ` Windows: python -m pytest tests/test_dev_cli.py -q `

**Gezielte Negativkontrolle:** Runner-Exitcode verschlucken; bestehender Fehlerpropagationstest muss rot werden.


<a id="g-027"></a>

## G-027 · Zwei veraltete Emulatorfixtures reparieren

**P1 · broken_test** · Verträge: [WATCH-01](matrix.md#watch-01), [SHARE-01](matrix.md#share-01) · Paket: [WP-01](work-packages.md#wp-01)

**Produktbeleg:** [tests/e2e/test_phase2_transactions.py](../../../tests/e2e/test_phase2_transactions.py#L56) — ` is_pro=False `; [tests/e2e/test_phase2_transactions.py](../../../tests/e2e/test_phase2_transactions.py#L98) — ` pending_ref.set({ `

**Vorhandene relevante Prüfungen:**

- [test_two_workers_cannot_exceed_owner_watch_limit](../../../tests/e2e/test_phase2_transactions.py#L24) — Firestore-Emulatorintegration mit echten SDK-Transaktionen und Threads. Assertionstellen: [66](../../../tests/e2e/test_phase2_transactions.py#L66), [73](../../../tests/e2e/test_phase2_transactions.py#L73), [78](../../../tests/e2e/test_phase2_transactions.py#L78).
- [test_two_workers_publish_one_pending_share_and_consume_one_quota](../../../tests/e2e/test_phase2_transactions.py#L92) — Firestore-Emulatorintegration mit echten SDK-Transaktionen und Threads. Assertionstellen: [115](../../../tests/e2e/test_phase2_transactions.py#L115), [116](../../../tests/e2e/test_phase2_transactions.py#L116), [121](../../../tests/e2e/test_phase2_transactions.py#L121).

**Suiteweite Gegenprüfung:** Vorbefunde F-02/F-03: nicht mehr vorhandenes is_pro-Argument statt tier; Pending-Result ohne expires_at. Beide scheitern vor dem intendierten Race.

**Suchspur:** 224 versionierte Test-/Hilfsdateien durchsucht, 7 passende Zeilen. Regexe: ` is_pro=False|test_two_workers_publish_one_pending_share|test_two_workers_cannot_exceed_owner_watch_limit `. Vollständige Treffer mit Pfad/Zeile in [search-evidence.json](search-evidence.json) unter ` G-027 `.

| Szenario | Erwartung |
|---|---|
| Given | Fixtures entsprechen aktuellem gültigem Watch-/Pending-Schema, Zeit deterministisch. |
| When | Bestehende zwei Rennen wieder ausführen, konkurrierende Starts mit Barriere absichern. |
| Then | Ein Watch bei Limit eins; eine Share-ID, ein created=True und ein Quota-Charge. Assertions bleiben fachlich gleich stark, Produktionsvalidierung nicht lockern. |

**Zielstellen:** [tests/e2e/test_phase2_transactions.py](../../../tests/e2e/test_phase2_transactions.py)

**Wiederverwenden:** [app/services/watch_service.py](../../../app/services/watch_service.py), [app/services/share_snapshots.py](../../../app/services/share_snapshots.py)

**Validierung nach Implementierung:** ` RUN_E2E=1 python -m pytest tests/e2e/test_phase2_transactions.py -q (Demo-Emulator) `

**Gezielte Negativkontrolle:** Quota-/Idempotenzschutz entfernen; korrigierte Fixtures müssen tatsächlich das Rennen erreichen.


<a id="g-028"></a>

## G-028 · Veralteten Footer-Stringvertrag korrigieren

**P2 · broken_test** · Verträge: [UI-04](matrix.md#ui-04) · Paket: [WP-01](work-packages.md#wp-01)

**Produktbeleg:** [tests/test_consensus_progress_ui.py](../../../tests/test_consensus_progress_ui.py#L335) — ` tab.className = `; [static/js/consensus-run.js](../../../static/js/consensus-run.js#L400) — ` consensus-tab consensus-evidence-action `

**Vorhandene relevante Prüfungen:**

- [test_archived_turns_use_the_same_drawer_row_as_the_live_answer](../../../tests/test_consensus_progress_ui.py#L322) — Quelltextverträge. Assertionstellen: [333](../../../tests/test_consensus_progress_ui.py#L333), [334](../../../tests/test_consensus_progress_ui.py#L334), [335](../../../tests/test_consensus_progress_ui.py#L335), [336](../../../tests/test_consensus_progress_ui.py#L336), [337](../../../tests/test_consensus_progress_ui.py#L337), [338](../../../tests/test_consensus_progress_ui.py#L338), [341](../../../tests/test_consensus_progress_ui.py#L341), [342](../../../tests/test_consensus_progress_ui.py#L342), [344](../../../tests/test_consensus_progress_ui.py#L344), [345](../../../tests/test_consensus_progress_ui.py#L345).

**Suiteweite Gegenprüfung:** F-01 reproduziert, auch im neuen Branchlauf. Erwarteter Klassenstring ist enger als aktueller zusätzlicher Evidence-Klasse. Kein Beweis eines UI-Produktfehlers.

**Suchspur:** 224 versionierte Test-/Hilfsdateien durchsucht, 4 passende Zeilen. Regexe: ` test_archived_turns_use_the_same_drawer_row|consensus-evidence-action `. Vollständige Treffer mit Pfad/Zeile in [search-evidence.json](search-evidence.json) unter ` G-028 `.

| Szenario | Erwartung |
|---|---|
| Given | Aktuelle Live-/Archivfooter mit identischen fachlichen Aktionen. |
| When | Vertrag auf relevante Klassen/Aktionen aktualisieren und gegebenenfalls vorhandenen DOM-/Browserfall erweitern. |
| Then | Zusätzliche harmlose Klasse erlaubt; fehlende Aktionen, falsche Turnzuordnung oder doppelte Footer bleiben erkennbar. Nicht nur alte Erwartung kommentarlos löschen. |

**Zielstellen:** [tests/test_consensus_progress_ui.py](../../../tests/test_consensus_progress_ui.py), [tests/js/stored-turn-markers.test.mjs](../../../tests/js/stored-turn-markers.test.mjs)

**Wiederverwenden:** [tests/e2e/test_reader_review_regressions.py](../../../tests/e2e/test_reader_review_regressions.py)

**Validierung nach Implementierung:** ` python -m pytest tests/test_consensus_progress_ui.py -q; npm test -- tests/js/stored-turn-markers.test.mjs `

**Gezielte Negativkontrolle:** Archivfooter-Aktion entfernen; neuer semantischer Vertrag muss weiterhin rot werden.


<a id="g-029"></a>

## G-029 · Report-Race-Instabilität isolieren

**P1 · unstable_test** · Verträge: [SHARE-03](matrix.md#share-03) · Paket: [WP-02](work-packages.md#wp-02)

**Produktbeleg:** [tests/e2e/test_phase2_transactions.py](../../../tests/e2e/test_phase2_transactions.py#L161) — ` def test_parallel_reports_never_lose_increments `

**Vorhandene relevante Prüfungen:**

- [test_parallel_reports_never_lose_increments_or_noindex_transition](../../../tests/e2e/test_phase2_transactions.py#L161) — Firestore-Emulatorintegration mit echten SDK-Transaktionen und Threads. Assertionstellen: [183](../../../tests/e2e/test_phase2_transactions.py#L183), [184](../../../tests/e2e/test_phase2_transactions.py#L184), [185](../../../tests/e2e/test_phase2_transactions.py#L185), [186](../../../tests/e2e/test_phase2_transactions.py#L186), [187](../../../tests/e2e/test_phase2_transactions.py#L187).

**Suiteweite Gegenprüfung:** F-04: Primärlauf Transaction-lock-timeout/12 Versuche, isolierter frischer Emulatorlauf bestanden. Ursache unbestimmt; nicht als sicherer Produktfehler oder sicherer Testflake etikettieren.

**Suchspur:** 224 versionierte Test-/Hilfsdateien durchsucht, 1 passende Zeilen. Regexe: ` test_parallel_reports_never_lose_increments `. Vollständige Treffer mit Pfad/Zeile in [search-evidence.json](search-evidence.json) unter ` G-029 `.

| Szenario | Erwartung |
|---|---|
| Given | Dokumentierte Java21-Umgebung, Emulatorversion, feste Racegröße/isolierte IDs, vollständiger und isolierter Lauf. |
| When | Rennen mit begrenzten Wiederholungen in beiden Kontexten ausführen, Retry-/Leasezeiten und Commitresultate erfassen. |
| Then | Ursache durch konkrete Beobachtung eingrenzen; keine fehlenden Reports oder falsche noindex-Schwelle, kein pauschales Retry-erhöhen/xfail zum Grünmachen. |

**Zielstellen:** [tests/e2e/test_phase2_transactions.py](../../../tests/e2e/test_phase2_transactions.py)

**Wiederverwenden:** [tests/e2e/README.md](../../../tests/e2e/README.md), [docs/test-coverage/findings.md](../findings.md)

**Validierung nach Implementierung:** ` RUN_E2E=1 python -m pytest tests/e2e/test_phase2_transactions.py -v (danach betroffenen Test isoliert) `

**Gezielte Negativkontrolle:** Inkrementverlust muss trotz erlaubter Transaktionsretries durch exakten Endstand/alle Resultwerte auffallen.


<a id="g-030"></a>

## G-030 · Wenige vollständige Browser→Backend→Persistenz-Flows

**P1 · missing_integration** · Verträge: [CONS-05](matrix.md#cons-05), [CHAT-04](matrix.md#chat-04), [AUTH-04](matrix.md#auth-04), [AGENT-04](matrix.md#agent-04) · Paket: [WP-29](work-packages.md#wp-29)

**Produktbeleg:** [tests/e2e/conftest.py](../../../tests/e2e/conftest.py#L140) — ` ctx.route("**/static/firebase.js*" `; [tests/e2e/test_phase4_frontend.py](../../../tests/e2e/test_phase4_frontend.py#L130) — ` def _real_firebase_page `

**Vorhandene relevante Prüfungen:**

Kein direkter repräsentativer Testbeleg für diese Grenze; Suchtreffer und verwandte Verträge sind separat berücksichtigt.

**Suiteweite Gegenprüfung:** Smoke verbindet Browser mit Mock-LLM-Backend, ersetzt jedoch komplettes AppFirebase. Phase4 führt AppFirebase aus, ersetzt Daten-APIs/SDK. Die bisherige Kombination prüft keine vollständige Persistenz-/Reload-/Auth-Recovery-Kette.

**Suchspur:** 224 versionierte Test-/Hilfsdateien durchsucht, 1167 passende Zeilen. Regexe: ` firebase_stub|_real_firebase_page|route\(|recover_only|bookmark `. Vollständige Treffer mit Pfad/Zeile in [search-evidence.json](search-evidence.json) unter ` G-030 `.

| Szenario | Erwartung |
|---|---|
| Given | Echter App-Bundle/Firebase-Appcode und Backend mit lokalem Demo-Firestore; nur externe Identitäts-/Providergrenzen kontrolliert ersetzt, keine Bookmark-/Chat-/Usage-Routen. |
| When | Consensus bis Bookmark speichern, Reload und Follow-up; zweiter paralleler Run/Viewwechsel; Stop/Verbindungsverlust; Konto A→B; analog Agent-Recover. |
| Then | DB-Endzustand und UI stimmen je Turn/Owner überein; ein Usage-Charge, kein zweiter Modellstart beim Recover, keine verlorene Zwischenantwort/fremde Projektion. Netzwerkreihenfolge gezielt kontrollieren. |

**Zielstellen:** ` tests/e2e/test_persisted_user_journeys.py ` (vorgeschlagen)

**Wiederverwenden:** [tests/e2e/conftest.py](../../../tests/e2e/conftest.py), [tests/e2e/test_phase4_frontend.py](../../../tests/e2e/test_phase4_frontend.py), [tests/test_consensus_chat_history.py](../../../tests/test_consensus_chat_history.py)

**Validierung nach Implementierung:** ` RUN_E2E=1 python -m pytest tests/e2e/test_persisted_user_journeys.py -q (Demo-Emulator) `

**Gezielte Negativkontrolle:** Bookmark-/Context-/Usage-ID an einer Grenze vertauschen; nur ein echter persistierter Endzustand darf den Test bestehen.


<a id="g-031"></a>

## G-031 · Due-Queries und Scheduler-Claims mit SDK-Formen

**P2 · missing_integration** · Verträge: [WATCH-02](matrix.md#watch-02), [TOPIC-01](matrix.md#topic-01), [SEO-04](matrix.md#seo-04) · Paket: [WP-19](work-packages.md#wp-19)

**Produktbeleg:** [app/services/watch_service.py](../../../app/services/watch_service.py#L1389) — ` def list_due_watch_ids( `; [app/services/topics.py](../../../app/services/topics.py#L977) — ` def claim_topic_run( `; [app/services/topics.py](../../../app/services/topics.py#L924) — ` def list_due_topic_ids( `; [app/services/seo_weekly_review.py](../../../app/services/seo_weekly_review.py#L1318) — ` async def seo_review_scheduler_loop `

**Vorhandene relevante Prüfungen:**

- [SchedulerSafetyTests::test_claim_transaction_prevents_double_run](../../../tests/test_watch_feature.py#L757) — Große Service-/Scheduler-/Router-/Mailformat-Suite mit DB-/LLM-/Versand-Doubles plus UI-Sourceverträge. Assertionstellen: [764](../../../tests/test_watch_feature.py#L764), [765](../../../tests/test_watch_feature.py#L765), [766](../../../tests/test_watch_feature.py#L766), [767](../../../tests/test_watch_feature.py#L767), [768](../../../tests/test_watch_feature.py#L768).
- [test_default_interval_is_seven_days_and_lease_is_persistent](../../../tests/test_seo_weekly_review.py#L81) — Review-Service mit Repository-/Judge-/Action-Doubles. Assertionstellen: [86](../../../tests/test_seo_weekly_review.py#L86), [87](../../../tests/test_seo_weekly_review.py#L87), [88](../../../tests/test_seo_weekly_review.py#L88), [89](../../../tests/test_seo_weekly_review.py#L89).

**Suiteweite Gegenprüfung:** Helperclaims/Zeitslots geprüft, Wrapper und Due-Queries im regulären Lauf vielfach unausgeführt oder ersetzt. Kein nativer Topic-/SEO-Leaserace im Emulatorbestand.

**Suchspur:** 224 versionierte Test-/Hilfsdateien durchsucht, 11 passende Zeilen. Regexe: ` list_due_watch_ids|list_due_topic_ids|claim_topic_run|acquire_worker_lease|seo_review_scheduler_loop `. Vollständige Treffer mit Pfad/Zeile in [search-evidence.json](search-evidence.json) unter ` G-031 `.

| Szenario | Erwartung |
|---|---|
| Given | Fällige/nichtfällige/pausierte Datensätze, gleiche Slotzeit, konkurrierende Worker, abgelaufene und erneuerte Lease. |
| When | Reale SDK-Queries/Claims und je einen Loop-Tick mit Fakepipeline/Benachrichtigung ausführen; Shutdown gezielt abbrechen. |
| Then | Nur fällige Arbeit, ein Slotgewinner, begrenzte Scans, keine stale Completion, kein weiterer Tick nach Shutdown. DST bleibt gesondert durch vorhandene Zeitfälle geschützt. |

**Zielstellen:** ` tests/e2e/test_scheduler_transactions.py ` (vorgeschlagen), [tests/test_background_task_supervision.py](../../../tests/test_background_task_supervision.py)

**Wiederverwenden:** [tests/test_watch_feature.py](../../../tests/test_watch_feature.py), [tests/test_topics_feature.py](../../../tests/test_topics_feature.py), [tests/test_seo_weekly_review.py](../../../tests/test_seo_weekly_review.py)

**Validierung nach Implementierung:** ` RUN_E2E=1 python -m pytest tests/e2e/test_scheduler_transactions.py -q; python -m pytest tests/test_background_task_supervision.py -q `

**Gezielte Negativkontrolle:** Fälligkeits-/Claim-Filter auslassen; Kontrollrows und doppelte Slots müssen entdeckt werden.


<a id="g-032"></a>

## G-032 · Lokale echte Transportgrenzen statt ausschließlich MockTransport

**P2 · missing_integration** · Verträge: [LLM-02](matrix.md#llm-02), [SRC-01](matrix.md#src-01) · Paket: [WP-26](work-packages.md#wp-26)

**Produktbeleg:** [app/services/llm/provider_runtime.py](../../../app/services/llm/provider_runtime.py#L170) — ` def managed_provider_resource `; [app/services/source_documents.py](../../../app/services/source_documents.py#L92) — ` async def _download( `

**Vorhandene relevante Prüfungen:**

Kein direkter repräsentativer Testbeleg für diese Grenze; Suchtreffer und verwandte Verträge sind separat berücksichtigt.

**Suiteweite Gegenprüfung:** Provider-/SSRFtests kontrollieren Fehler und Close über Transportdoubles. Der Testname real_provider_socket_stall bezeichnet ebenfalls MockTransport. Kein aktueller echter lokaler TCP/TLS-/Proxy-SSE-Nachweis.

**Suchspur:** 224 versionierte Test-/Hilfsdateien durchsucht, 8 passende Zeilen. Regexe: ` MockTransport|real_provider_socket_stall|http.server|ThreadingHTTPServer|TCPServer `. Vollständige Treffer mit Pfad/Zeile in [search-evidence.json](search-evidence.json) unter ` G-032 `.

| Szenario | Erwartung |
|---|---|
| Given | Ausschließlich lokaler Testserver mit deterministischem Streaming, Disconnect, Redirect, gzip-Budget und passenden Testzertifikaten. |
| When | Echten HTTP-Client durch dieselben Adapter gegen kontrollierte Transportfehler führen; keine öffentlichen Provider/Quellen anrufen. |
| Then | Deadlines/Close/Cancel auch am Socket wirksam; Redirectvalidierung und Host/SNI korrekt, kein unbegrenztes Lesen/Dekomprimieren oder versteckter Retry. |

**Zielstellen:** ` tests/test_provider_local_transport.py ` (vorgeschlagen), ` tests/test_source_documents_local_transport.py ` (vorgeschlagen)

**Wiederverwenden:** [tests/test_provider_timeouts.py](../../../tests/test_provider_timeouts.py), [tests/test_source_verification.py](../../../tests/test_source_verification.py)

**Validierung nach Implementierung:** ` python -m pytest tests/test_provider_local_transport.py tests/test_source_documents_local_transport.py -q `

**Gezielte Negativkontrolle:** Response-close oder Redirect-Neuvalidierung entfernen; Server-/Zielzähler müssen Leck erkennen.


<a id="g-033"></a>

## G-033 · Ungültige Body-Header und Konfigurationsgrenzen

**P2 · missing_case** · Verträge: [OPS-02](matrix.md#ops-02) · Paket: [WP-26](work-packages.md#wp-26)

**Produktbeleg:** [app/core/request_limits.py](../../../app/core/request_limits.py#L12) — ` def configured_max_request_body_bytes `; [app/core/request_limits.py](../../../app/core/request_limits.py#L58) — ` except ValueError: `

**Vorhandene relevante Prüfungen:**

- [test_exact_limit_body_is_replayed_once_to_the_application](../../../tests/test_request_body_limits.py#L61) — ASGI-Middleware mit kontrollierten Receive-/Send-Funktionen. Assertionstellen: [69](../../../tests/test_request_body_limits.py#L69), [70](../../../tests/test_request_body_limits.py#L70).

**Suiteweite Gegenprüfung:** Vier bestehende Tests prüfen Overlimit, Chunkzählung, exakt erlaubtes Replay und SSE-Disconnect. Negative/nichtnumerische Content-Length sowie Konfigurations-Min/Max/Invalid werden nicht als Fälle ausgeführt.

**Suchspur:** 224 versionierte Test-/Hilfsdateien durchsucht, 2 passende Zeilen. Regexe: ` MAX_REQUEST_BODY_BYTES|Invalid Content-Length|configured_max_request_body|content-length `. Vollständige Treffer mit Pfad/Zeile in [search-evidence.json](search-evidence.json) unter ` G-033 `.

| Szenario | Erwartung |
|---|---|
| Given | Header fehlt/negativ/nichtnumerisch, non-HTTP-Scope, frühzeitiger Disconnect sowie Envwerte unter/auf/über den Grenzen. |
| When | Middleware direkt über vorhandenen ASGI-Harness ausführen. |
| Then | Handler sieht keine abgelehnte Übergröße; Fehlerstatus ist bewusst festgelegt; gültige Grenzen passen, ungültige Konfiguration startet nicht. Protokollstatus 400 versus bestehendes 413 nicht unbegründet ändern. |

**Zielstellen:** [tests/test_request_body_limits.py](../../../tests/test_request_body_limits.py)

**Wiederverwenden:** [tests/test_request_body_limits.py](../../../tests/test_request_body_limits.py)

**Validierung nach Implementierung:** ` python -m pytest tests/test_request_body_limits.py -q `

**Gezielte Negativkontrolle:** Negative Content-Length passieren lassen; Nichtaufrufassertion muss rot werden.


<a id="g-034"></a>

## G-034 · Feedback-Adapter und Statistik-Persistenzwrapper

**P2 · missing_case** · Verträge: [DATA-01](matrix.md#data-01) · Paket: [WP-27](work-packages.md#wp-27)

**Produktbeleg:** [app/api/routers/pages.py](../../../app/api/routers/pages.py#L523) — ` def submit_feedback( `; [app/services/differences_stats.py](../../../app/services/differences_stats.py#L181) — ` def record_differences_stats( `

**Vorhandene relevante Prüfungen:**

- [test_feedback_cooldown_and_daily_limit_are_persistent](../../../tests/test_phase5_operations.py#L315) — Gemischt: Services mit DB-/HTTP-Doubles, Thread-/Async-Tests und Deployment-Quelltextverträge. Assertionstellen: [321](../../../tests/test_phase5_operations.py#L321), [327](../../../tests/test_phase5_operations.py#L327).

**Suiteweite Gegenprüfung:** Feedbackguard und Aggregationsform sind separat geprüft; echter Feedbackhandler und record_differences_stats sind im regulären Lauf unausgeführt. Browserprüfungen belegen keinen tatsächlichen Write.

**Suchspur:** 224 versionierte Test-/Hilfsdateien durchsucht, 5 passende Zeilen. Regexe: ` /feedback|submit_feedback|record_differences_stats `. Vollständige Treffer mit Pfad/Zeile in [search-evidence.json](search-evidence.json) unter ` G-034 `.

| Szenario | Erwartung |
|---|---|
| Given | Gültiger/ungültiger Login, Tages-/Cooldown-Grenze, Storefehler und sensible Modell-/Fragetexte. |
| When | POST /feedback und realen Statistikwrapper mit äußerem DB-/Notifierdouble ausführen. |
| Then | UID und erlaubte Felder korrekt, Limits vor Write, Fehler redigiert; Statistik zählt erwartete Kategorien ohne Prompt/Antwort/IDs. |

**Zielstellen:** ` tests/test_feedback.py ` (vorgeschlagen), [tests/test_differences_stats.py](../../../tests/test_differences_stats.py)

**Wiederverwenden:** [tests/test_phase5_operations.py](../../../tests/test_phase5_operations.py), [tests/test_differences_stats.py](../../../tests/test_differences_stats.py)

**Validierung nach Implementierung:** ` python -m pytest tests/test_feedback.py tests/test_differences_stats.py -q `

**Gezielte Negativkontrolle:** Rohfrage in Statistikrecord einfügen oder UID-Limit umgehen; Negativassertion muss rot werden.


<a id="g-035"></a>

## G-035 · Weitere ausführbare CLI-Einstiege

**P3 · missing_case** · Verträge: [BENCH-02](matrix.md#bench-02), [TOOLS-02](matrix.md#tools-02) · Paket: [WP-28](work-packages.md#wp-28)

**Produktbeleg:** [benchmark/run_sample.py](../../../benchmark/run_sample.py#L53) — ` def main( `; [benchmark/run_experiment.py](../../../benchmark/run_experiment.py#L62) — ` def main( `

**Vorhandene relevante Prüfungen:**

Kein direkter repräsentativer Testbeleg für diese Grenze; Suchtreffer und verwandte Verträge sind separat berücksichtigt.

**Suiteweite Gegenprüfung:** Haupt-Benchmark-CLI gut geprüft, alternative run_sample/run_experiment und Preview-/Probe-CLIs besitzen keinen vergleichbaren Ausführungsnachweis. Einige Evaluationhelper sind getestet, ihre CLI-Pfade nicht.

**Suchspur:** 224 versionierte Test-/Hilfsdateien durchsucht, 2 passende Zeilen. Regexe: ` run_sample|run_experiment|evaluate_agent_delegation|evaluate_source_verification|probe_agent_delegation|render_watch_preview `. Vollständige Treffer mit Pfad/Zeile in [search-evidence.json](search-evidence.json) unter ` G-035 `.

| Szenario | Erwartung |
|---|---|
| Given | Temporäre Ausgabeordner, Fakeprovider/-publisher/-renderer und fehlende/ungültige Argumente. |
| When | Jeden weiterhin unterstützten Einstieg direkt als Subprozess aufrufen; benötigte Toolgrenzen ersetzen. |
| Then | Keine unbeabsichtigten Provider-/DB-Aufrufe, korrekte Eingabe-/Budget-/Outputgrenzen und Exitcodes. Falls ein Einstieg veraltet ist, erst Supportstatus entscheiden statt alten Modus blind auszubauen. |

**Zielstellen:** ` tests/test_auxiliary_cli.py ` (vorgeschlagen)

**Wiederverwenden:** [tests/test_publisher_standalone.py](../../../tests/test_publisher_standalone.py), [tests/test_benchmark_cli.py](../../../tests/test_benchmark_cli.py)

**Validierung nach Implementierung:** ` python -m pytest tests/test_auxiliary_cli.py -q `

**Gezielte Negativkontrolle:** Ungültige CLI-Argumente in tatsächlichen Providerlauf weiterreichen; Netzwerkverbot muss Test stoppen.


<a id="g-036"></a>

## G-036 · Vendorhelper mit Version- und Check-only-Grenzen ausführen

**P2 · missing_case** · Verträge: [BUILD-01](matrix.md#build-01) · Paket: [WP-30](work-packages.md#wp-30)

**Produktbeleg:** [scripts/vendor_frontend.mjs](../../../scripts/vendor_frontend.mjs#L7) — ` export async function vendorFrontend( `; [scripts/vendor_frontend.mjs](../../../scripts/vendor_frontend.mjs#L18) — ` if (version !== pins[name]) `

**Vorhandene relevante Prüfungen:**

- [test_app_vendor_assets_are_local_versioned_and_include_fonts_and_licenses](../../../tests/test_frontend_build.py#L158) — Build-Artefakt-/Fingerprint-Verträge. Assertionstellen: [160](../../../tests/test_frontend_build.py#L160), [162](../../../tests/test_frontend_build.py#L162), [164](../../../tests/test_frontend_build.py#L164), [165](../../../tests/test_frontend_build.py#L165), [169](../../../tests/test_frontend_build.py#L169), [172](../../../tests/test_frontend_build.py#L172).

**Suiteweite Gegenprüfung:** Vorhandene Tests prüfen eingecheckte Vendorartefakte, Manifest und writeAtomicIfChanged; sie rufen vendorFrontend nicht auf. Exportierter Buildhelper, kein CLI: Versionabweichung, fehlende/stale Datei und schreibfreier checkOnly-Modus haben keinen Verhaltenstest.

**Suchspur:** 224 versionierte Test-/Hilfsdateien durchsucht, 1 passende Zeilen. Regexe: ` vendorFrontend|vendor_frontend|Unexpected .*version|checkOnly `, ` does not truncate or rewrite unchanged vendor `. Vollständige Treffer mit Pfad/Zeile in [search-evidence.json](search-evidence.json) unter ` G-036 `.

| Szenario | Erwartung |
|---|---|
| Given | Temporärer Projektbaum mit winzigen synthetischen package.json-/Library-/Font-/Lizenzdateien; keine npm-Downloads. |
| When | Realen vendorFrontend(root, checkOnly) in Build- und Prüfmodus mit richtiger/falscher Paketversion sowie fehlenden/geänderten Assets aufrufen. |
| Then | Gepinnte Version wird verlangt, Dateien/Fonts/Lizenzen vollständig und in stabiler Reihenfolge erfasst; Check-only verändert nichts und entdeckt fehlende/stale Bytes; unveränderte Builds schreiben nicht erneut. |

**Zielstellen:** ` tests/js/vendor-frontend.test.mjs ` (vorgeschlagen)

**Wiederverwenden:** [tests/js/frontend-output.test.mjs](../../../tests/js/frontend-output.test.mjs), [tests/test_frontend_build.py](../../../tests/test_frontend_build.py)

**Validierung nach Implementierung:** ` npm test -- tests/js/vendor-frontend.test.mjs tests/js/frontend-output.test.mjs; python -m pytest tests/test_frontend_build.py -q `

**Gezielte Negativkontrolle:** Versionsvergleich überspringen oder Check-only durch Write ersetzen; Fehler- und Dateisystemassertionen müssen scheitern.

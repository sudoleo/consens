# Verifizierte Befunde und ergänzende Tests

[Einstieg](README.md) · [Arbeitspakete](work-packages.md) · [Suchbelege](search-evidence.json)

46 Befunde im Verlauf, Stand 2026-10-02. Der aktuelle Status steht an jedem Befund: resolved = konkret behobener Befund, partially_addressed = Teilnachweis ergänzt, open = Restgrenze offen. Die ursprünglichen Mutations-/DOM-/Pythonproben vom 26.09.2026 bleiben historische Belege; sie werden nicht als aktuelle Messung ausgegeben. Der [Aktualisierungsbericht](current-review.md) trennt behobene Fehler, neue Teilbelege und erneut beobachtete Probleme.

P1/P2/P3 ordnen die Umsetzung nach möglichen Folgen und Voraussetzungen; sie sind keine Incident-Schweregrade. Suchtreffer allein beweisen weder Vorhandensein noch Abwesenheit eines Tests. Die Schlussfolgerung verbindet Suche, Testkörper, Mockgrenzen und gegebenenfalls Branchlauf/Probe. Suggested paths sind Vorschläge, vorhandene passende Dateien bevorzugen.

| ID | Priorität / Art | Befund | Status | Paket |
|---|---|---|---|---|
| [G-001](#g-001) | P1 / ` missing_integration ` | Deny-all-Regeln mit Clientidentitäten prüfen | open | [WP-06](work-packages.md#wp-06) |
| [G-002](#g-002) | P1 / ` missing_integration ` | Reguläre Usage mit echten Firestore-Transaktionen absichern | open | [WP-07](work-packages.md#wp-07) |
| [G-003](#g-003) | P1 / ` missing_integration ` | Chat-Löschen gegen Turn/Completion im Emulator | partially_addressed | [WP-08](work-packages.md#wp-08) |
| [G-004](#g-004) | P1 / ` missing_integration ` | Vollständige Kontokaskade und API-Cleanup prüfen | partially_addressed | [WP-09](work-packages.md#wp-09) |
| [G-005](#g-005) | P1 / ` missing_case ` | API-Neustart-Recovery und Retention tatsächlich ausführen | partially_addressed | [WP-11](work-packages.md#wp-11) |
| [G-006](#g-006) | P1 / ` missing_integration ` | Source-Queue-Leases und Result-Commits im Emulator | open | [WP-14](work-packages.md#wp-14) |
| [G-007](#g-007) | P1 / ` assertion_gap ` | Undo-Konflikt, Ablauf, Wiederholung und HTTP-Fehlergrenze | partially_addressed | [WP-10](work-packages.md#wp-10) |
| [G-008](#g-008) | P1 / ` missing_case ` | Memory-Patch gegen konkurrierenden Save und Kontolöschung | partially_addressed | [WP-10](work-packages.md#wp-10) |
| [G-009](#g-009) | P2 / ` missing_case ` | Konkurrierende Registrierung ohne Auskunfts-/Benachrichtigungsleck | open | [WP-12](work-packages.md#wp-12) |
| [G-010](#g-010) | P1 / ` missing_case ` | Historischer API-v1-Source-Check-Adapter | open | [WP-11](work-packages.md#wp-11) |
| [G-011](#g-011) | P1 / ` missing_case ` | App-POST-/api/share durch den echten Router prüfen | open | [WP-13](work-packages.md#wp-13) |
| [G-012](#g-012) | P1 / ` missing_case ` | user_status-Adapter einschließlich Free-Admin und Ausfällen | open | [WP-12](work-packages.md#wp-12) |
| [G-013](#g-013) | P2 / ` missing_case ` | Sieben Watch-/Telegram-/Unsubscribe-HTTP-Adapter | open | [WP-15](work-packages.md#wp-15) |
| [G-014](#g-014) | P1 / ` missing_case ` | Topic-PUT/List sowie öffentliche Hub-/Sitemap-/Follow-Adapter | open | [WP-16](work-packages.md#wp-16) |
| [G-015](#g-015) | P2 / ` missing_case ` | Admin-Benchmark-Routen und Reportviewer | open | [WP-22](work-packages.md#wp-22) |
| [G-016](#g-016) | P2 / ` missing_case ` | Claim-Identity-Judge selbst prüfen | open | [WP-17](work-packages.md#wp-17) |
| [G-017](#g-017) | P2 / ` missing_case ` | SEO-Readadapter hinter den Service-Fakes | open | [WP-18](work-packages.md#wp-18) |
| [G-018](#g-018) | P1 / ` observed_behavior_defect ` | Topic-Notizen werden erneut als HTML interpretiert | resolved | [WP-20](work-packages.md#wp-20) |
| [G-019](#g-019) | P2 / ` observed_behavior_defect ` | Strukturierte Adminfehler verlieren ihre Nachricht | open | [WP-21](work-packages.md#wp-21) |
| [G-020](#g-020) | P2 / ` assertion_gap ` | OG-Test akzeptiert leeres Bild | open | [WP-23](work-packages.md#wp-23) |
| [G-021](#g-021) | P2 / ` assertion_gap ` | Analytics-Opt-out ausführen statt Strings suchen | open | [WP-24](work-packages.md#wp-24) |
| [G-022](#g-022) | P1 / ` missing_case ` | Account-Reparaturskript ohne Produktionszugriff prüfen | open | [WP-25](work-packages.md#wp-25) |
| [G-023](#g-023) | P2 / ` missing_case ` | Claim-Key-Backfill-Dry-run, Idempotenz und Datenerhalt | open | [WP-25](work-packages.md#wp-25) |
| [G-024](#g-024) | P1 / ` missing_automation ` | Allgemeine Suite in CI absichern | open | [WP-05](work-packages.md#wp-05) |
| [G-025](#g-025) | P1 / ` execution_gap ` | Aktuelle Browserfälle ausführen und rote Fälle klären | partially_addressed | [WP-03](work-packages.md#wp-03) |
| [G-026](#g-026) | P2 / ` execution_gap ` | Windows-Einstieg tatsächlich validieren | partially_addressed | [WP-04](work-packages.md#wp-04) |
| [G-027](#g-027) | P1 / ` broken_test ` | Zwei veraltete Emulatorfixtures reparieren | open | [WP-01](work-packages.md#wp-01) |
| [G-028](#g-028) | P2 / ` broken_test ` | Veralteten Footer-Stringvertrag korrigieren | open | [WP-01](work-packages.md#wp-01) |
| [G-029](#g-029) | P1 / ` unstable_test ` | Report-Race-Instabilität isolieren | open | [WP-02](work-packages.md#wp-02) |
| [G-030](#g-030) | P1 / ` missing_integration ` | Wenige vollständige Browser→Backend→Persistenz-Flows | partially_addressed | [WP-29](work-packages.md#wp-29) |
| [G-031](#g-031) | P2 / ` missing_integration ` | Due-Queries und Scheduler-Claims mit SDK-Formen | partially_addressed | [WP-19](work-packages.md#wp-19) |
| [G-032](#g-032) | P2 / ` missing_integration ` | Lokale echte Transportgrenzen statt ausschließlich MockTransport | partially_addressed | [WP-26](work-packages.md#wp-26) |
| [G-033](#g-033) | P2 / ` missing_case ` | Ungültige Body-Header und Konfigurationsgrenzen | open | [WP-26](work-packages.md#wp-26) |
| [G-034](#g-034) | P2 / ` missing_case ` | Feedback-Adapter und Statistik-Persistenzwrapper | open | [WP-27](work-packages.md#wp-27) |
| [G-035](#g-035) | P3 / ` missing_case ` | Weitere ausführbare CLI-Einstiege | open | [WP-28](work-packages.md#wp-28) |
| [G-036](#g-036) | P2 / ` missing_case ` | Vendorhelper mit Version- und Check-only-Grenzen ausführen | open | [WP-30](work-packages.md#wp-30) |
| [G-037](#g-037) | P1 / ` observed_behavior_defect ` | main verwirft HTTPException-Header einschließlich Retry-After | resolved | [WP-31](work-packages.md#wp-31) |
| [G-038](#g-038) | P1 / ` observed_behavior_defect ` | Undo kürzt früheren Inhalt nach Absenkung des Memorylimits | open | [WP-10](work-packages.md#wp-10) |
| [G-039](#g-039) | P1 / ` missing_case ` | Erfolgreicher Agentdetail- und Stop-HTTP-Pfad fehlen | open | [WP-32](work-packages.md#wp-32) |
| [G-040](#g-040) | P1 / ` observed_behavior_defect ` | Modellrollback überschreibt einen zwischenzeitlichen Writer | partially_addressed | [WP-33](work-packages.md#wp-33) |
| [G-041](#g-041) | P1 / ` observed_behavior_defect ` | Topic-Admingrenze prüft Revocation nicht und verliert Rollen-503 | open | [WP-16](work-packages.md#wp-16) |
| [G-042](#g-042) | P1 / ` observed_behavior_defect ` | Benchmark zählt HTTP-200-Providerfehler als erfolgreiche Enthaltung | open | [WP-34](work-packages.md#wp-34) |
| [G-043](#g-043) | P1 / ` missing_integration ` | Google-Aktionsclaims mit nativen Transaktionen prüfen | open | [WP-35](work-packages.md#wp-35) |
| [G-044](#g-044) | P2 / ` missing_integration ` | Cloud-Dateiablage und verteilte Löschkaskade integrieren | open | [WP-36](work-packages.md#wp-36) |
| [G-045](#g-045) | P1 / ` missing_integration ` | Outbox-/Probeclaims mit nativer SDK-Konkurrenz absichern | open | [WP-37](work-packages.md#wp-37) |
| [G-046](#g-046) | P2 / ` broken_test ` | Aktuelle Testfehler und abweichenden Benchmark-Wiederholungslauf klären | open | [WP-38](work-packages.md#wp-38) |

<a id="g-001"></a>

## G-001 · Deny-all-Regeln mit Clientidentitäten prüfen

**P1 · missing_integration** · Verträge: [AUTH-05](matrix.md#auth-05) · Paket: [WP-06](work-packages.md#wp-06)

**Aktuelle Bewertung:** open — Die bestehende Testgrenze bleibt nach Abgleich der zugeordneten Tests und aktualisierter Suchspur offen. Frühere Lauf-/Mutationsangaben sind historische Belege vom 26.09.2026, keine neue Ausführung.

**Produktbeleg:** [firestore.rules](../../../firestore.rules#L31) — ` allow read, write: if false; `; [tests/e2e/test_agent_transactions.py](../../../tests/e2e/test_agent_transactions.py#L24) — ` db = firestore.Client `

**Vorhandene relevante Prüfungen:**

Kein direkter repräsentativer Testbeleg für diese Grenze; Suchtreffer und verwandte Verträge sind separat berücksichtigt.

**Suiteweite Gegenprüfung:** Die bestehende Testgrenze bleibt nach Abgleich der zugeordneten Tests und aktualisierter Suchspur offen. Frühere Lauf-/Mutationsangaben sind historische Belege vom 26.09.2026, keine neue Ausführung.

**Suchspur:** 263 versionierte Test-/Hilfsdateien durchsucht, 0 passende Zeilen. Regexe: ` firestore\.rules `, ` assertFails|assertSucceeds|initializeTestEnvironment|rules-unit-testing `. Vollständige Treffer mit Pfad/Zeile in [search-evidence.json](search-evidence.json) unter ` G-001 `.

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

**Aktuelle Bewertung:** open — Runzählquoten durch gemeinsames Tokenkonto ersetzt. Umfangreiche parallele Fake-Tests und Usage-Meter vorhanden; native Firestore-Admission/Buchung/Freigabe weiterhin offen.

**Produktbeleg:** [app/services/usage_repository.py](../../../app/services/usage_repository.py#L752) — ` def _transaction( `

**Vorhandene relevante Prüfungen:**

- [test_same_operation_race_has_exactly_one_authorization](../../../tests/test_usage_authorization.py#L78) — Atomare Autorisierungslogik mit FakeFirestore und Threads. Assertionstellen: [82](../../../tests/test_usage_authorization.py#L82), [83](../../../tests/test_usage_authorization.py#L83), [86](../../../tests/test_usage_authorization.py#L86), [87](../../../tests/test_usage_authorization.py#L87).
- [test_run_quotas_are_gone_from_the_limits_config](../../../tests/test_run_usage_repository.py#L55) — Repository-/Transaktionsverträge mit FakeFirestore und Threads. Assertionstellen: [58](../../../tests/test_run_usage_repository.py#L58), [59](../../../tests/test_run_usage_repository.py#L59), [60](../../../tests/test_run_usage_repository.py#L60), [62](../../../tests/test_run_usage_repository.py#L62).

**Suiteweite Gegenprüfung:** Runzählquoten durch gemeinsames Tokenkonto ersetzt. Umfangreiche parallele Fake-Tests und Usage-Meter vorhanden; native Firestore-Admission/Buchung/Freigabe weiterhin offen.

**Suchspur:** 263 versionierte Test-/Hilfsdateien durchsucht, 60 passende Zeilen. Regexe: ` usage_repository|FirestoreUsageRepository `, ` daily_token_admission|authorize_operation|parallel_unique_reservations `. Vollständige Treffer mit Pfad/Zeile in [search-evidence.json](search-evidence.json) unter ` G-002 `.

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

**Aktuelle Bewertung:** partially_addressed — Dauerhafte Löschjobs und spätes Turn-/Kontextfencing ergänzt (test_chat_history.py, test_chat_context.py). Ein nativer Emulatorrace mit Completion bleibt erforderlich.

**Produktbeleg:** [app/services/chat_store.py](../../../app/services/chat_store.py#L1270) — ` def delete_chat( `; [app/services/chat_store.py](../../../app/services/chat_store.py#L891) — ` def complete_turn( `

**Vorhandene relevante Prüfungen:**

- [test_deleting_chat_state_rejects_late_completion_and_failure_writes](../../../tests/test_chat_history.py#L1491) — Router und ChatStore mit speicherbasiertem Transaktionsmodell. Assertionstellen: [1500](../../../tests/test_chat_history.py#L1500), [1504](../../../tests/test_chat_history.py#L1504), [1512](../../../tests/test_chat_history.py#L1512), [1513](../../../tests/test_chat_history.py#L1513).
- [test_two_workers_cannot_exceed_owner_chat_limit](../../../tests/e2e/test_phase2_transactions.py#L134) — Firestore-Emulatorintegration mit echten SDK-Transaktionen und Threads. Assertionstellen: [149](../../../tests/e2e/test_phase2_transactions.py#L149), [153](../../../tests/e2e/test_phase2_transactions.py#L153).

**Suiteweite Gegenprüfung:** Dauerhafte Löschjobs und spätes Turn-/Kontextfencing ergänzt (test_chat_history.py, test_chat_context.py). Ein nativer Emulatorrace mit Completion bleibt erforderlich.

**Suchspur:** 263 versionierte Test-/Hilfsdateien durchsucht, 17 passende Zeilen. Regexe: ` delet.*complet|complet.*delet|deleting_chat|account_deletion_tombstone `, ` test_two_workers_cannot_exceed_owner_chat_limit `. Vollständige Treffer mit Pfad/Zeile in [search-evidence.json](search-evidence.json) unter ` G-003 `.

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

**Aktuelle Bewertung:** partially_addressed — Kaskade berücksichtigt Googlegrants, Aktionen, Dokumentversionen, Antwortreceipts und Outbox. Einzelne Fake-Nachweise sind vorhanden; komplette Kaskade samt Retrygrenzen noch nicht als eine integrierte Reise belegt.

**Produktbeleg:** [app/services/account_deletion.py](../../../app/services/account_deletion.py#L94) — ` areas = ( `; [app/services/api_account_cleanup.py](../../../app/services/api_account_cleanup.py#L85) — ` def cleanup_uid( `; [app/services/api_account_cleanup.py](../../../app/services/api_account_cleanup.py#L135) — ` def retry_pending( `

**Vorhandene relevante Prüfungen:**

- [test_failed_area_remains_pending_and_only_that_area_is_retried](../../../tests/test_account_deletion_retry.py#L69) — Service mit In-Memory-Datenbank. Assertionstellen: [163](../../../tests/test_account_deletion_retry.py#L163), [164](../../../tests/test_account_deletion_retry.py#L164), [165](../../../tests/test_account_deletion_retry.py#L165), [166](../../../tests/test_account_deletion_retry.py#L166), [167](../../../tests/test_account_deletion_retry.py#L167), [168](../../../tests/test_account_deletion_retry.py#L168), [169](../../../tests/test_account_deletion_retry.py#L169), [170](../../../tests/test_account_deletion_retry.py#L170), [172](../../../tests/test_account_deletion_retry.py#L172), [173](../../../tests/test_account_deletion_retry.py#L173), [174](../../../tests/test_account_deletion_retry.py#L174), [175](../../../tests/test_account_deletion_retry.py#L175), [176](../../../tests/test_account_deletion_retry.py#L176), [177](../../../tests/test_account_deletion_retry.py#L177), [179](../../../tests/test_account_deletion_retry.py#L179), [180](../../../tests/test_account_deletion_retry.py#L180), [181](../../../tests/test_account_deletion_retry.py#L181), [182](../../../tests/test_account_deletion_retry.py#L182).
- [test_delete_account_cascades_into_the_owner_chats](../../../tests/test_account_deletion_chats.py#L98) — API mit Service-Double. Assertionstellen: [102](../../../tests/test_account_deletion_chats.py#L102), [103](../../../tests/test_account_deletion_chats.py#L103), [104](../../../tests/test_account_deletion_chats.py#L104).

**Suiteweite Gegenprüfung:** Kaskade berücksichtigt Googlegrants, Aktionen, Dokumentversionen, Antwortreceipts und Outbox. Einzelne Fake-Nachweise sind vorhanden; komplette Kaskade samt Retrygrenzen noch nicht als eine integrierte Reise belegt.

**Suchspur:** 263 versionierte Test-/Hilfsdateien durchsucht, 29 passende Zeilen. Regexe: ` FirestoreAccountDeletion|FirestoreApiAccountCleanup|cleanup_uid|retry_pending `, ` completed_areas|_delete_api_access `. Vollständige Treffer mit Pfad/Zeile in [search-evidence.json](search-evidence.json) unter ` G-004 `.

| Szenario | Erwartung |
|---|---|
| Given | Eigene Daten in allen 14 Kaskadenbereichen plus Kontrollowner; Firebase Auth/Mail/Telegram-Transport bleiben externe Doubles. |
| When | Löschung mit einem gezielten Bereichs-/Checkpointfehler, anschließend neuer Serviceprozess/Instanz und Retry; parallel bereits authentifizierter Write. |
| Then | Persistiert quittierte Bereiche werden übersprungen; Operationen ohne dauerhaften Checkpoint dürfen idempotent wiederholt werden, auch wenn ihr Seiteneffekt bereits erfolgte. Zieldaten aller 14 Bereiche sind entfernt, fremde Daten erhalten und pending bleibt bis zum belegten Abschluss bestehen. Der erforderliche minimale UID-Sperrtombstone bleibt bis zum Aufbewahrungsende erhalten, die Cleanup-E-Mail wird entfernt; späte Writes dürfen nicht neu befüllen. |

**Zielstellen:** [tests/test_api_account_cleanup.py](../../../tests/test_api_account_cleanup.py), ` tests/e2e/test_account_deletion_transactions.py ` (vorgeschlagen)

**Wiederverwenden:** [tests/test_account_deletion_retry.py](../../../tests/test_account_deletion_retry.py), [tests/test_chat_history.py](../../../tests/test_chat_history.py)

**Validierung nach Implementierung:** ` python -m pytest tests/test_api_account_cleanup.py tests/test_account_deletion_retry.py -q; anschließend neuer Emulator-Kaskadentest `

**Gezielte Negativkontrolle:** Eine Kaskadenoperation durch No-op ersetzen oder die Sperre vorzeitig löschen; Residualdaten-/Sperrassertion muss rot werden. Den ausdrücklich erforderlichen UID-Tombstone nicht als unerlaubtes Residualdatum zählen.


<a id="g-005"></a>

## G-005 · API-Neustart-Recovery und Retention tatsächlich ausführen

**P1 · missing_case** · Verträge: [API-02](matrix.md#api-02) · Paket: [WP-11](work-packages.md#wp-11)

**Aktuelle Bewertung:** partially_addressed — test_api_run_billing_identity.py führt Recovery abgelaufener Reservierungen und Lösch-/Replaypfade aus. Vollständige Retention/Backfill-/Restartorchestrierung bleibt offen; die alte Behauptung keiner ausgeführten Recovery ist überholt.

**Produktbeleg:** [app/services/api_consensus_runner.py](../../../app/services/api_consensus_runner.py#L285) — ` def recover_persisted_runs( `; [app/services/api_consensus_runner.py](../../../app/services/api_consensus_runner.py#L255) — ` def cleanup_expired_runs( `; [app/services/api_run_repository.py](../../../app/services/api_run_repository.py#L307) — ` def backfill_retention( `

**Vorhandene relevante Prüfungen:**

- [test_runner_claim_prevents_duplicate_usage_and_provider_start](../../../tests/test_consensus_api.py#L493) — Main-App-API und Runner mit Repository-/LLM-/Scheduler-Doubles; einzelne Quelltextverträge. Assertionstellen: [542](../../../tests/test_consensus_api.py#L542), [543](../../../tests/test_consensus_api.py#L543), [544](../../../tests/test_consensus_api.py#L544).
- [test_expired_post_provider_worker_keeps_consumed_usage](../../../tests/test_consensus_api.py#L735) — Main-App-API und Runner mit Repository-/LLM-/Scheduler-Doubles; einzelne Quelltextverträge. Assertionstellen: [757](../../../tests/test_consensus_api.py#L757).

**Suiteweite Gegenprüfung:** test_api_run_billing_identity.py führt Recovery abgelaufener Reservierungen und Lösch-/Replaypfade aus. Vollständige Retention/Backfill-/Restartorchestrierung bleibt offen; die alte Behauptung keiner ausgeführten Recovery ist überholt.

**Suchspur:** 263 versionierte Test-/Hilfsdateien durchsucht, 6 passende Zeilen. Regexe: ` recover_persisted_runs|cleanup_expired_runs|backfill_retention `, ` fail_expired_run|expired_post_provider|expired_pre_provider `. Vollständige Treffer mit Pfad/Zeile in [search-evidence.json](search-evidence.json) unter ` G-005 `.

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

**Aktuelle Bewertung:** open — Die bestehende Testgrenze bleibt nach Abgleich der zugeordneten Tests und aktualisierter Suchspur offen. Frühere Lauf-/Mutationsangaben sind historische Belege vom 26.09.2026, keine neue Ausführung.

**Produktbeleg:** [app/services/source_check_repository.py](../../../app/services/source_check_repository.py#L358) — ` def claim( `; [app/services/source_check_repository.py](../../../app/services/source_check_repository.py#L406) — ` def finish_package( `

**Vorhandene relevante Prüfungen:**

- [test_expired_lease_reclaims_unfinished_package_and_rejects_stale_worker](../../../tests/test_source_check_repository.py#L214) — Repository mit lockbasiertem FakeDb und Threads. Assertionstellen: [219](../../../tests/test_source_check_repository.py#L219), [221](../../../tests/test_source_check_repository.py#L221), [222](../../../tests/test_source_check_repository.py#L222), [224](../../../tests/test_source_check_repository.py#L224), [225](../../../tests/test_source_check_repository.py#L225), [226](../../../tests/test_source_check_repository.py#L226), [227](../../../tests/test_source_check_repository.py#L227).

**Suiteweite Gegenprüfung:** Die bestehende Testgrenze bleibt nach Abgleich der zugeordneten Tests und aktualisierter Suchspur offen. Frühere Lauf-/Mutationsangaben sind historische Belege vom 26.09.2026, keine neue Ausführung.

**Suchspur:** 263 versionierte Test-/Hilfsdateien durchsucht, 75 passende Zeilen. Regexe: ` SourceCheckRepository|finish_package|lease_token `, ` transactional|run_transaction `. Vollständige Treffer mit Pfad/Zeile in [search-evidence.json](search-evidence.json) unter ` G-006 `.

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

## G-007 · Undo-Konflikt, Ablauf, Wiederholung und HTTP-Fehlergrenze

**P1 · assertion_gap** · Verträge: [MEM-02](matrix.md#mem-02) · Paket: [WP-10](work-packages.md#wp-10)

**Aktuelle Bewertung:** partially_addressed — Undo-Ablauf nach 30 Tagen ist nun im Repository getestet; Konflikt, fremder Owner, Repeat und echte Undo-HTTP-Fehlergrenze bleiben zusätzlich zu G-038 offen. Alte Mutationsprobe ist historisch, nicht erneut ausgeführt.

**Produktbeleg:** [app/services/memory_edit.py](../../../app/services/memory_edit.py#L701) — ` def undo( `; [app/services/memory_edit.py](../../../app/services/memory_edit.py#L735) — ` if current_revision != int(revision.get `; [app/api/routers/users.py](../../../app/api/routers/users.py#L320) — ` def _raise_memory_edit_error( `; [app/api/routers/users.py](../../../app/api/routers/users.py#L354) — ` def undo_user_memory( `

**Vorhandene relevante Prüfungen:**

- [test_replace_is_revision_checked_and_undo_restores_exact_content](../../../tests/test_memory_edit.py#L178) — Edit-Service/Repository und Router mit DB-/LLM-Doubles. Assertionstellen: [189](../../../tests/test_memory_edit.py#L189), [204](../../../tests/test_memory_edit.py#L204), [208](../../../tests/test_memory_edit.py#L208), [209](../../../tests/test_memory_edit.py#L209), [220](../../../tests/test_memory_edit.py#L220), [221](../../../tests/test_memory_edit.py#L221), [222](../../../tests/test_memory_edit.py#L222), [223](../../../tests/test_memory_edit.py#L223).

**Suiteweite Gegenprüfung:** Undo-Ablauf nach 30 Tagen ist nun im Repository getestet; Konflikt, fremder Owner, Repeat und echte Undo-HTTP-Fehlergrenze bleiben zusätzlich zu G-038 offen. Alte Mutationsprobe ist historisch, nicht erneut ausgeführt.

**Suchspur:** 263 versionierte Test-/Hilfsdateien durchsucht, 6 passende Zeilen. Regexe: ` undo\(|undo_expired|revision_not_found|invalid_revision `, ` revision_conflict `. Vollständige Treffer mit Pfad/Zeile in [search-evidence.json](search-evidence.json) unter ` G-007 `.

| Szenario | Erwartung |
|---|---|
| Given | Angewandter Patch Revision 4→5; danach expliziter unabhängiger Save auf Revision 6. Separate Fälle: fremder Owner, ungültige/fehlende ID, abgelaufenes Fenster, bereits undone. |
| When | Undo des alten Patches versuchen beziehungsweise identisches Undo wiederholen. Dieselben Fehler zusätzlich über POST /api/my/memory/undo in main.app prüfen; nur externe SDK-/LLM-/DB-Grenzen ersetzen. |
| Then | Neuere Daten bleiben byte-/feldgleich, Konflikt ist sichtbar und macht keine Writes; Ablauf/Ownerfehler bleiben fail-closed; legitimer Retry erhöht Revision nicht erneut. Authlos 401, Tierausfall 503, Tombstone 403 und strukturierte MemoryEditError-Codes mit dem tatsächlichen main-Umschlag; keine Writes oder bezahlten Calls bei Ablehnung. |

**Zielstellen:** [tests/test_memory_edit.py](../../../tests/test_memory_edit.py)

**Wiederverwenden:** [tests/test_memory_edit.py](../../../tests/test_memory_edit.py)

**Validierung nach Implementierung:** ` python -m pytest tests/test_memory_edit.py -q `

**Gezielte Negativkontrolle:** Probe M-01 (Guard current_revision != after_revision entfernt) muss nach Ergänzung rot werden.


<a id="g-008"></a>

## G-008 · Memory-Patch gegen konkurrierenden Save und Kontolöschung

**P1 · missing_case** · Verträge: [MEM-02](matrix.md#mem-02), [AUTH-03](matrix.md#auth-03) · Paket: [WP-10](work-packages.md#wp-10)

**Aktuelle Bewertung:** partially_addressed — Manuelles PUT benutzt Revision-CAS, KI-Edit nutzt Leasefencing; stale Save und Save nach KI-Patch werden geprüft. Direkter konkurrierender Patch/Save/Löschtombstone im nativen Speicher bleibt offen.

**Produktbeleg:** [app/services/memory_edit.py](../../../app/services/memory_edit.py#L610) — ` def apply_patch( `; [app/services/memory_edit.py](../../../app/services/memory_edit.py#L649) — ` if current_revision != int(request.get `

**Vorhandene relevante Prüfungen:**

- [test_replace_is_revision_checked_and_undo_restores_exact_content](../../../tests/test_memory_edit.py#L178) — Edit-Service/Repository und Router mit DB-/LLM-Doubles. Assertionstellen: [189](../../../tests/test_memory_edit.py#L189), [204](../../../tests/test_memory_edit.py#L204), [208](../../../tests/test_memory_edit.py#L208), [209](../../../tests/test_memory_edit.py#L209), [220](../../../tests/test_memory_edit.py#L220), [221](../../../tests/test_memory_edit.py#L221), [222](../../../tests/test_memory_edit.py#L222), [223](../../../tests/test_memory_edit.py#L223).

**Suiteweite Gegenprüfung:** Manuelles PUT benutzt Revision-CAS, KI-Edit nutzt Leasefencing; stale Save und Save nach KI-Patch werden geprüft. Direkter konkurrierender Patch/Save/Löschtombstone im nativen Speicher bleibt offen.

**Suchspur:** 263 versionierte Test-/Hilfsdateien durchsucht, 10 passende Zeilen. Regexe: ` memory_edit.*ensure_account|ensure_account_write_allowed `, ` baseline_revision|revision_conflict `. Vollständige Treffer mit Pfad/Zeile in [search-evidence.json](search-evidence.json) unter ` G-008 `.

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

**Aktuelle Bewertung:** open — Die bestehende Testgrenze bleibt nach Abgleich der zugeordneten Tests und aktualisierter Suchspur offen. Frühere Lauf-/Mutationsangaben sind historische Belege vom 26.09.2026, keine neue Ausführung.

**Produktbeleg:** [app/services/registration.py](../../../app/services/registration.py#L48) — ` except firebase_admin.auth.EmailAlreadyExistsError: `

**Vorhandene relevante Prüfungen:**

- [test_new_user_gets_an_unguessable_server_side_password](../../../tests/test_registration_security.py#L12) — Registrierungsservice mit Firebase-/HTTP-Doubles. Assertionstellen: [24](../../../tests/test_registration_security.py#L24), [25](../../../tests/test_registration_security.py#L25), [27](../../../tests/test_registration_security.py#L27), [28](../../../tests/test_registration_security.py#L28).
- [AuthSessionTests::test_new_and_existing_registration_responses_are_identical](../../../tests/test_auth_session.py#L110) — API mit Auth-/Mail-/Notifier-Doubles. Assertionstellen: [141](../../../tests/test_auth_session.py#L141), [142](../../../tests/test_auth_session.py#L142).

**Suiteweite Gegenprüfung:** Die bestehende Testgrenze bleibt nach Abgleich der zugeordneten Tests und aktualisierter Suchspur offen. Frühere Lauf-/Mutationsangaben sind historische Belege vom 26.09.2026, keine neue Ausführung.

**Suchspur:** 263 versionierte Test-/Hilfsdateien durchsucht, 8 passende Zeilen. Regexe: ` EmailAlreadyExists|find_or_provision_user|create.race `. Vollständige Treffer mit Pfad/Zeile in [search-evidence.json](search-evidence.json) unter ` G-009 `.

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

**Aktuelle Bewertung:** open — Die bestehende Testgrenze bleibt nach Abgleich der zugeordneten Tests und aktualisierter Suchspur offen. Frühere Lauf-/Mutationsangaben sind historische Belege vom 26.09.2026, keine neue Ausführung.

**Produktbeleg:** [app/api/routers/api_v1.py](../../../app/api/routers/api_v1.py#L400) — ` def get_run_source_check( `

**Vorhandene relevante Prüfungen:**

- [test_v4_public_share_rejects_wrong_job_version_on_every_page](../../../tests/test_source_check_api.py#L125) — Router mit SourceCheckRepository/FakeDb und Share-/Topic-Doubles. Assertionstellen: [138](../../../tests/test_source_check_api.py#L138), [140](../../../tests/test_source_check_api.py#L140).

**Suiteweite Gegenprüfung:** Die bestehende Testgrenze bleibt nach Abgleich der zugeordneten Tests und aktualisierter Suchspur offen. Frühere Lauf-/Mutationsangaben sind historische Belege vom 26.09.2026, keine neue Ausführung.

**Suchspur:** 263 versionierte Test-/Hilfsdateien durchsucht, 49 passende Zeilen. Regexe: ` /api/v1/consensus/runs/.{0,100}source-check `, ` get_run_source_check|expected_snapshot|answer_version `. Vollständige Treffer mit Pfad/Zeile in [search-evidence.json](search-evidence.json) unter ` G-010 `.

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

**Aktuelle Bewertung:** open — Die bestehende Testgrenze bleibt nach Abgleich der zugeordneten Tests und aktualisierter Suchspur offen. Frühere Lauf-/Mutationsangaben sind historische Belege vom 26.09.2026, keine neue Ausführung.

**Produktbeleg:** [app/api/routers/share.py](../../../app/api/routers/share.py#L357) — ` def create_share( `

**Vorhandene relevante Prüfungen:**

- [ShareFlowTests::test_create_share_is_idempotent](../../../tests/test_share_feature.py#L780) — Große Unit-/Service-/Router-/SSR-Suite mit FakeDb und lokalen Cachethreads. Assertionstellen: [790](../../../tests/test_share_feature.py#L790), [791](../../../tests/test_share_feature.py#L791), [792](../../../tests/test_share_feature.py#L792).

**Suiteweite Gegenprüfung:** Die bestehende Testgrenze bleibt nach Abgleich der zugeordneten Tests und aktualisierter Suchspur offen. Frühere Lauf-/Mutationsangaben sind historische Belege vom 26.09.2026, keine neue Ausführung.

**Suchspur:** 263 versionierte Test-/Hilfsdateien durchsucht, 26 passende Zeilen. Regexe: ` create_share\(|["\x27]/api/share["\x27] `, ` create_share_from_pending `. Vollständige Treffer mit Pfad/Zeile in [search-evidence.json](search-evidence.json) unter ` G-011 `.

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

**Aktuelle Bewertung:** open — Die bestehende Testgrenze bleibt nach Abgleich der zugeordneten Tests und aktualisierter Suchspur offen. Frühere Lauf-/Mutationsangaben sind historische Belege vom 26.09.2026, keine neue Ausführung.

**Produktbeleg:** [app/api/routers/users.py](../../../app/api/routers/users.py#L61) — ` def get_user_status( `

**Vorhandene relevante Prüfungen:**

Kein direkter repräsentativer Testbeleg für diese Grenze; Suchtreffer und verwandte Verträge sind separat berücksichtigt.

**Suiteweite Gegenprüfung:** Die bestehende Testgrenze bleibt nach Abgleich der zugeordneten Tests und aktualisierter Suchspur offen. Frühere Lauf-/Mutationsangaben sind historische Belege vom 26.09.2026, keine neue Ausführung.

**Suchspur:** 263 versionierte Test-/Hilfsdateien durchsucht, 33 passende Zeilen. Regexe: ` /user_status|get_user_status|checkUserStatusOnLoad `. Vollständige Treffer mit Pfad/Zeile in [search-evidence.json](search-evidence.json) unter ` G-012 `.

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

## G-013 · Sieben Watch-/Telegram-/Unsubscribe-HTTP-Adapter

**P2 · missing_case** · Verträge: [WATCH-01](matrix.md#watch-01), [WATCH-04](matrix.md#watch-04), [WATCH-03](matrix.md#watch-03) · Paket: [WP-15](work-packages.md#wp-15)

**Aktuelle Bewertung:** open — Die bestehende Testgrenze bleibt nach Abgleich der zugeordneten Tests und aktualisierter Suchspur offen. Frühere Lauf-/Mutationsangaben sind historische Belege vom 26.09.2026, keine neue Ausführung.

**Produktbeleg:** [app/api/routers/watch.py](../../../app/api/routers/watch.py#L129) — ` def patch_watch( `; [app/api/routers/watch.py](../../../app/api/routers/watch.py#L218) — ` def remove_watch( `; [app/api/routers/watch.py](../../../app/api/routers/watch.py#L157) — ` def create_telegram_link( `; [app/api/routers/watch.py](../../../app/api/routers/watch.py#L173) — ` def test_telegram( `; [app/api/routers/watch.py](../../../app/api/routers/watch.py#L187) — ` def disconnect_telegram( `; [app/api/routers/watch.py](../../../app/api/routers/watch.py#L332) — ` def follow_unsubscribe( `; [app/api/routers/watch.py](../../../app/api/routers/watch.py#L344) — ` def unsubscribe(request: `

**Vorhandene relevante Prüfungen:**

- [WatchCrudTests::test_free_create_list_update_pause_delete](../../../tests/test_watch_feature.py#L177) — Große Service-/Scheduler-/Router-/Mailformat-Suite mit DB-/LLM-/Versand-Doubles plus UI-Sourceverträge. Assertionstellen: [179](../../../tests/test_watch_feature.py#L179), [180](../../../tests/test_watch_feature.py#L180), [181](../../../tests/test_watch_feature.py#L181), [182](../../../tests/test_watch_feature.py#L182), [183](../../../tests/test_watch_feature.py#L183), [184](../../../tests/test_watch_feature.py#L184), [185](../../../tests/test_watch_feature.py#L185), [188](../../../tests/test_watch_feature.py#L188), [190](../../../tests/test_watch_feature.py#L190), [192](../../../tests/test_watch_feature.py#L192).
- [WatchRouteTests::test_telegram_connection_routes_and_webhook_secret](../../../tests/test_watch_feature.py#L2713) — Große Service-/Scheduler-/Router-/Mailformat-Suite mit DB-/LLM-/Versand-Doubles plus UI-Sourceverträge. Assertionstellen: [2721](../../../tests/test_watch_feature.py#L2721), [2722](../../../tests/test_watch_feature.py#L2722), [2726](../../../tests/test_watch_feature.py#L2726), [2734](../../../tests/test_watch_feature.py#L2734), [2735](../../../tests/test_watch_feature.py#L2735).

**Suiteweite Gegenprüfung:** Die bestehende Testgrenze bleibt nach Abgleich der zugeordneten Tests und aktualisierter Suchspur offen. Frühere Lauf-/Mutationsangaben sind historische Belege vom 26.09.2026, keine neue Ausführung.

**Suchspur:** 263 versionierte Test-/Hilfsdateien durchsucht, 11 passende Zeilen. Regexe: ` patch_watch|remove_watch|create_telegram_link|test_telegram\( `, ` /api/watch/|/api/my/telegram/(link|test) `, ` disconnect_telegram|follow_unsubscribe|/watch/unsubscribe|/telegram/disconnect `. Vollständige Treffer mit Pfad/Zeile in [search-evidence.json](search-evidence.json) unter ` G-013 `.

| Szenario | Erwartung |
|---|---|
| Given | Eigene/fremde Watch, verbundenes/unverbundenes Telegram, gültige/ungültige Felder, Servicefehler. Gültige, manipulierte und abgelaufene Watch-/Follower-Abmeldetokens; Tokens des jeweils anderen Typs. |
| When | Reale HTTP-Methoden mit Auth und strukturierten Fehlern durchlaufen. |
| Then | Ownerprüfung vor Mutation, Patchallowlist/Tier/Schedule unverändert durchgereicht, Delete beendet passend Brief/Watch, Link/Test führt nicht ohne autorisierten Owner aus. Disconnect betrifft nur die authentifizierte UID. Die beiden Abmeldeseiten setzen nur den zum Token gehörenden Zustand, liefern sichere HTML-Fehler und verändern bei ungültigem Token nichts. |

**Zielstellen:** [tests/test_watch_feature.py](../../../tests/test_watch_feature.py)

**Wiederverwenden:** [tests/test_watch_feature.py](../../../tests/test_watch_feature.py)

**Validierung nach Implementierung:** ` python -m pytest tests/test_watch_feature.py -q `

**Gezielte Negativkontrolle:** PATCH als falscher Owner oder Testnachricht ohne Verbindung zulassen; Fehler-/Nichtaufrufassertion muss scheitern.


<a id="g-014"></a>

## G-014 · Topic-PUT/List sowie öffentliche Hub-/Sitemap-/Follow-Adapter

**P1 · missing_case** · Verträge: [AUTH-02](matrix.md#auth-02), [TOPIC-01](matrix.md#topic-01), [TOPIC-04](matrix.md#topic-04) · Paket: [WP-16](work-packages.md#wp-16)

**Aktuelle Bewertung:** open — Die bestehende Testgrenze bleibt nach Abgleich der zugeordneten Tests und aktualisierter Suchspur offen. Frühere Lauf-/Mutationsangaben sind historische Belege vom 26.09.2026, keine neue Ausführung.

**Produktbeleg:** [app/api/routers/topics.py](../../../app/api/routers/topics.py#L138) — ` def _require_admin( `; [app/api/routers/topics.py](../../../app/api/routers/topics.py#L728) — ` async def admin_update_topic( `; [app/api/routers/topics.py](../../../app/api/routers/topics.py#L253) — ` async def topics_hub( `; [app/api/routers/topics.py](../../../app/api/routers/topics.py#L291) — ` async def sitemap_topics( `; [app/api/routers/topics.py](../../../app/api/routers/topics.py#L604) — ` async def follow_topic( `; [app/api/routers/admin.py](../../../app/api/routers/admin.py#L192) — ` uid = verify_user_token(id_token, check_revoked=True) `; [app/core/security.py](../../../app/core/security.py#L257) — ` check_revoked: bool = False `; [app/api/routers/topics.py](../../../app/api/routers/topics.py#L641) — ` def topic_follow_confirm( `; [app/api/routers/topics.py](../../../app/api/routers/topics.py#L658) — ` def topic_follow_unsubscribe( `; [app/api/routers/topics.py](../../../app/api/routers/topics.py#L683) — ` def admin_list_topics( `

**Vorhandene relevante Prüfungen:**

- [test_admin_topic_api_creates_updates_and_versions_without_share_data](../../../tests/test_topics_feature.py#L1137) — Große Service-/Router-/SSR-Suite mit FakeFirestore; einzelner echter SDK-Queryaufbau mit RPC-Mock. Assertionstellen: [1149](../../../tests/test_topics_feature.py#L1149), [1154](../../../tests/test_topics_feature.py#L1154), [1155](../../../tests/test_topics_feature.py#L1155), [1157](../../../tests/test_topics_feature.py#L1157), [1158](../../../tests/test_topics_feature.py#L1158), [1161](../../../tests/test_topics_feature.py#L1161), [1162](../../../tests/test_topics_feature.py#L1162), [1163](../../../tests/test_topics_feature.py#L1163).
- [test_admin_boundary_checks_revocation_and_maps_tier_outage_to_503](../../../tests/test_auth_revocation.py#L52) — Security-Funktionen mit Auth-/Datenbank-Doubles. Assertionstellen: [65](../../../tests/test_auth_revocation.py#L65), [68](../../../tests/test_auth_revocation.py#L68), [69](../../../tests/test_auth_revocation.py#L69).
- [test_noindex_and_unpublished_topics_are_not_in_topic_sitemap](../../../tests/test_topics_feature.py#L492) — Große Service-/Router-/SSR-Suite mit FakeFirestore; einzelner echter SDK-Queryaufbau mit RPC-Mock. Assertionstellen: [511](../../../tests/test_topics_feature.py#L511), [512](../../../tests/test_topics_feature.py#L512), [513](../../../tests/test_topics_feature.py#L513).

**Suiteweite Gegenprüfung:** Die bestehende Testgrenze bleibt nach Abgleich der zugeordneten Tests und aktualisierter Suchspur offen. Frühere Lauf-/Mutationsangaben sind historische Belege vom 26.09.2026, keine neue Ausführung.

**Suchspur:** 263 versionierte Test-/Hilfsdateien durchsucht, 33 passende Zeilen. Regexe: ` admin_update_topic|topics_hub|sitemap_topics|follow_topic|_require_admin `, ` /api/admin/topics|/sitemap-topics.xml `, ` confirm_topic_follow|unsubscribe_topic|admin_list_topics|/topics/follow `. Vollständige Treffer mit Pfad/Zeile in [search-evidence.json](search-evidence.json) unter ` G-014 `.

| Szenario | Erwartung |
|---|---|
| Given | Admin, normaler Nutzer, ungültiges/widerrufenes Token und Rollendienst-Ausfall; aktive/pausierte Topics mit/ohne veröffentlichten Run, noindex- und archivierte Topics sowie Follow-Challenges. |
| When | PUT /api/admin/topics/{id}, GET /topics, GET /sitemap-topics.xml und Follow-POST an echten Routern ausführen. Zusätzlich Adminlist sowie die Topic-Confirm-/Unsubscribe-GET-Routen mit gültigen, wiederverwendeten, abgelaufenen und falsch typisierten Tokens aufrufen. |
| Then | Adminprüfung vor Service, actor_uid und ID-Token-Allowlist korrekt. Revocation und 503 bei Rollendienst-Ausfall gemäß zentraler Adminpolicy an der echten Topicgrenze absichern. Hub enthält veröffentlichte aktive/pausierte Topics einschließlich noindex; Sitemap lässt noindex aus. Archive/unveröffentlichte Topics fehlen in beiden Listen; XML ist escaped, Follow neutral und ohne Doppelmail. Tokenfehler verändern keine Follower/Deliveries und werden als escaped HTML ausgegeben; erfolgreicher Confirm/Unsubscribe folgt der vorhandenen Service-Idempotenz statt einer erfundenen generellen 200-Garantie. |

**Zielstellen:** [tests/test_topics_feature.py](../../../tests/test_topics_feature.py)

**Wiederverwenden:** [tests/test_topics_feature.py](../../../tests/test_topics_feature.py), [tests/test_auth_revocation.py](../../../tests/test_auth_revocation.py)

**Validierung nach Implementierung:** ` python -m pytest tests/test_topics_feature.py tests/test_auth_revocation.py -q `

**Gezielte Negativkontrolle:** Admincheck aus PUT entfernen; Nonadmin-Test muss vor Mutation rot werden. Revocationflag weglassen oder 503-Abbildung entfernen; jeweilige Grenzassertion muss rot werden. noindex im Hub auszublenden muss ebenfalls auffallen.


<a id="g-015"></a>

## G-015 · Admin-Benchmark-Routen und Reportviewer

**P2 · missing_case** · Verträge: [BENCH-03](matrix.md#bench-03) · Paket: [WP-22](work-packages.md#wp-22)

**Aktuelle Bewertung:** open — Die bestehende Testgrenze bleibt nach Abgleich der zugeordneten Tests und aktualisierter Suchspur offen. Frühere Lauf-/Mutationsangaben sind historische Belege vom 26.09.2026, keine neue Ausführung.

**Produktbeleg:** [app/api/routers/admin.py](../../../app/api/routers/admin.py#L872) — ` def admin_list_benchmark_runs( `; [app/api/routers/admin.py](../../../app/api/routers/admin.py#L886) — ` def admin_get_benchmark_run( `; [static/js/admin-benchmark.js](../../../static/js/admin-benchmark.js#L26) — ` async function `

**Vorhandene relevante Prüfungen:**

- [test_publish_run_dir_stores_compact_report_only](../../../tests/test_benchmark_reports.py#L76) — Report-Publisher mit FakeCollection. Assertionstellen: [83](../../../tests/test_benchmark_reports.py#L83), [86](../../../tests/test_benchmark_reports.py#L86), [87](../../../tests/test_benchmark_reports.py#L87), [88](../../../tests/test_benchmark_reports.py#L88), [89](../../../tests/test_benchmark_reports.py#L89), [90](../../../tests/test_benchmark_reports.py#L90).

**Suiteweite Gegenprüfung:** Die bestehende Testgrenze bleibt nach Abgleich der zugeordneten Tests und aktualisierter Suchspur offen. Frühere Lauf-/Mutationsangaben sind historische Belege vom 26.09.2026, keine neue Ausführung.

**Suchspur:** 263 versionierte Test-/Hilfsdateien durchsucht, 3 passende Zeilen. Regexe: ` /api/admin/benchmark|admin_list_benchmark_runs|admin_get_benchmark_run|admin-benchmark.js `. Vollständige Treffer mit Pfad/Zeile in [search-evidence.json](search-evidence.json) unter ` G-015 `.

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

**Aktuelle Bewertung:** open — Die bestehende Testgrenze bleibt nach Abgleich der zugeordneten Tests und aktualisierter Suchspur offen. Frühere Lauf-/Mutationsangaben sind historische Belege vom 26.09.2026, keine neue Ausführung.

**Produktbeleg:** [app/services/llm/consensus_engine.py](../../../app/services/llm/consensus_engine.py#L2699) — ` def query_claim_identity( `

**Vorhandene relevante Prüfungen:**

- [test_claim_identity_result_maps_claims_onto_the_keys_they_continue](../../../tests/test_topics_feature.py#L1119) — Große Service-/Router-/SSR-Suite mit FakeFirestore; einzelner echter SDK-Queryaufbau mit RPC-Mock. Assertionstellen: [1134](../../../tests/test_topics_feature.py#L1134).
- [test_claim_identity_falls_back_to_fresh_keys_when_the_judge_is_unavailable](../../../tests/test_topics_feature.py#L1098) — Große Service-/Router-/SSR-Suite mit FakeFirestore; einzelner echter SDK-Queryaufbau mit RPC-Mock. Assertionstellen: [1116](../../../tests/test_topics_feature.py#L1116).

**Suiteweite Gegenprüfung:** Die bestehende Testgrenze bleibt nach Abgleich der zugeordneten Tests und aktualisierter Suchspur offen. Frühere Lauf-/Mutationsangaben sind historische Belege vom 26.09.2026, keine neue Ausführung.

**Suchspur:** 263 versionierte Test-/Hilfsdateien durchsucht, 3 passende Zeilen. Regexe: ` query_claim_identity|known_keys|claim_identity_result `. Vollständige Treffer mit Pfad/Zeile in [search-evidence.json](search-evidence.json) unter ` G-016 `.

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

**Aktuelle Bewertung:** open — Die bestehende Testgrenze bleibt nach Abgleich der zugeordneten Tests und aktualisierter Suchspur offen. Frühere Lauf-/Mutationsangaben sind historische Belege vom 26.09.2026, keine neue Ausführung.

**Produktbeleg:** [app/services/seo_repository.py](../../../app/services/seo_repository.py#L247) — ` def list_metrics_for_pages( `; [app/services/seo_repository.py](../../../app/services/seo_repository.py#L375) — ` def last_run( `; [app/services/seo_repository.py](../../../app/services/seo_repository.py#L426) — ` def list_judgments( `

**Vorhandene relevante Prüfungen:**

- [test_review_reuses_overview_context_without_second_metric_scan](../../../tests/test_seo_weekly_review.py#L300) — Review-Service mit Repository-/Judge-/Action-Doubles. Assertionstellen: [348](../../../tests/test_seo_weekly_review.py#L348), [349](../../../tests/test_seo_weekly_review.py#L349), [350](../../../tests/test_seo_weekly_review.py#L350).

**Suiteweite Gegenprüfung:** Die bestehende Testgrenze bleibt nach Abgleich der zugeordneten Tests und aktualisierter Suchspur offen. Frühere Lauf-/Mutationsangaben sind historische Belege vom 26.09.2026, keine neue Ausführung.

**Suchspur:** 263 versionierte Test-/Hilfsdateien durchsucht, 33 passende Zeilen. Regexe: ` list_metrics_for_pages|list_judgments|last_run|latest_review|recent_reviews `. Vollständige Treffer mit Pfad/Zeile in [search-evidence.json](search-evidence.json) unter ` G-017 `.

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

**Aktuelle Bewertung:** resolved — Behoben in 76e4873e: Checkstrip nutzt Text-/DOMknoten, Topicseite externe Skripte/strikte CSP. topic-page.test.mjs prüft inerte Notizen/Datumswerte, test_topics_feature.py CSP und aktuelle Quellenregeln. Beide Dateien im aktuellen Unitlauf grün.

**Produktbeleg:** [app/services/claim_ledger.py](../../../app/services/claim_ledger.py#L455) — ` note = str(run.get("change_summary") `; [templates/topic.html](../../../templates/topic.html#L231) — ` data-note="{{ cell.note }}" `

**Vorhandene relevante Prüfungen:**

- [test_topic_templates_expose_timeline_evidence_follow_and_admin_controls](../../../tests/test_topics_feature.py#L851) — Große Service-/Router-/SSR-Suite mit FakeFirestore; einzelner echter SDK-Queryaufbau mit RPC-Mock. Assertionstellen: [857](../../../tests/test_topics_feature.py#L857), [858](../../../tests/test_topics_feature.py#L858), [859](../../../tests/test_topics_feature.py#L859), [860](../../../tests/test_topics_feature.py#L860), [863](../../../tests/test_topics_feature.py#L863), [864](../../../tests/test_topics_feature.py#L864), [865](../../../tests/test_topics_feature.py#L865), [868](../../../tests/test_topics_feature.py#L868), [872](../../../tests/test_topics_feature.py#L872), [873](../../../tests/test_topics_feature.py#L873), [874](../../../tests/test_topics_feature.py#L874), [876](../../../tests/test_topics_feature.py#L876), [877](../../../tests/test_topics_feature.py#L877), [878](../../../tests/test_topics_feature.py#L878), [879](../../../tests/test_topics_feature.py#L879), [880](../../../tests/test_topics_feature.py#L880), [881](../../../tests/test_topics_feature.py#L881), [882](../../../tests/test_topics_feature.py#L882), [883](../../../tests/test_topics_feature.py#L883), [884](../../../tests/test_topics_feature.py#L884), [885](../../../tests/test_topics_feature.py#L885), [886](../../../tests/test_topics_feature.py#L886).

**Suiteweite Gegenprüfung:** Behoben in 76e4873e: Checkstrip nutzt Text-/DOMknoten, Topicseite externe Skripte/strikte CSP. topic-page.test.mjs prüft inerte Notizen/Datumswerte, test_topics_feature.py CSP und aktuelle Quellenregeln. Beide Dateien im aktuellen Unitlauf grün.

**Suchspur:** 263 versionierte Test-/Hilfsdateien durchsucht, 10 passende Zeilen. Regexe: ` topic-page|topicStripRead|topicReturn|topic-seen:|readStrip|returningReader `. Vollständige Treffer mit Pfad/Zeile in [search-evidence.json](search-evidence.json) unter ` G-018 `.

| Szenario | Erwartung |
|---|---|
| Given | SSR-escaped Notiz mit wörtlichem HTML, Quotes und Sonderzeichen; normaler/Touch-/historischer/Storage-blockierter Besuch. |
| When | Topicmodul laden und Zelle fokussieren/hovern/antippen; aktuellen und historischen Besuch wiederholen. |
| Then | Notiz bleibt Text, keine aus Notiz erzeugten Elemente/Handler. Touchvorschau, zweite Navigation, Unseen-Marker und historische Storageisolation funktionieren weiterhin. |

**Zielstellen:** [tests/js/topic-page.test.mjs](../../../tests/js/topic-page.test.mjs), ` tests/e2e/test_topic_frontend.py ` (vorgeschlagen)

**Wiederverwenden:** [tests/js/helpers/appWindow.mjs](../../../tests/js/helpers/appWindow.mjs), [tests/test_claim_ledger.py](../../../tests/test_claim_ledger.py)

**Validierung nach Implementierung:** ` npm test -- tests/js/topic-page.test.mjs; ergänzend gezielter Topic-Browserfall `

**Gezielte Negativkontrolle:** Aktuelles innerHTML-Verhalten muss am literalen Notiztest scheitern; kein Snapshot akzeptieren, der die Injection festschreibt.


<a id="g-019"></a>

## G-019 · Strukturierte Adminfehler verlieren ihre Nachricht

**P2 · observed_behavior_defect** · Verträge: [ADMIN-02](matrix.md#admin-02) · Paket: [WP-21](work-packages.md#wp-21)

**Aktuelle Bewertung:** open — Die bestehende Testgrenze bleibt nach Abgleich der zugeordneten Tests und aktualisierter Suchspur offen. Frühere Lauf-/Mutationsangaben sind historische Belege vom 26.09.2026, keine neue Ausführung.

**Produktbeleg:** [static/js/admin-api.js](../../../static/js/admin-api.js#L20) — ` const message = data.error `; [main.py](../../../main.py#L242) — ` content={"error": exc.detail} `; [app/api/routers/admin.py](../../../app/api/routers/admin.py#L642) — ` detail={"error_code": exc.code `

**Vorhandene relevante Prüfungen:**

- [test_configuration_tab_saves_reloads_and_preserves_conflicting_draft](../../../tests/e2e/test_admin_prompt_config.py#L15) — Chromium-Browserintegration mit simulierten Admin-APIs. Assertionstellen: [30](../../../tests/e2e/test_admin_prompt_config.py#L30), [46](../../../tests/e2e/test_admin_prompt_config.py#L46), [47](../../../tests/e2e/test_admin_prompt_config.py#L47), [49](../../../tests/e2e/test_admin_prompt_config.py#L49), [50](../../../tests/e2e/test_admin_prompt_config.py#L50), [51](../../../tests/e2e/test_admin_prompt_config.py#L51), [53](../../../tests/e2e/test_admin_prompt_config.py#L53), [55](../../../tests/e2e/test_admin_prompt_config.py#L55), [56](../../../tests/e2e/test_admin_prompt_config.py#L56), [57](../../../tests/e2e/test_admin_prompt_config.py#L57), [64](../../../tests/e2e/test_admin_prompt_config.py#L64), [65](../../../tests/e2e/test_admin_prompt_config.py#L65), [72](../../../tests/e2e/test_admin_prompt_config.py#L72), [73](../../../tests/e2e/test_admin_prompt_config.py#L73), [74](../../../tests/e2e/test_admin_prompt_config.py#L74), [76](../../../tests/e2e/test_admin_prompt_config.py#L76), [77](../../../tests/e2e/test_admin_prompt_config.py#L77), [78](../../../tests/e2e/test_admin_prompt_config.py#L78), [85](../../../tests/e2e/test_admin_prompt_config.py#L85), [86](../../../tests/e2e/test_admin_prompt_config.py#L86), [88](../../../tests/e2e/test_admin_prompt_config.py#L88), [90](../../../tests/e2e/test_admin_prompt_config.py#L90), [91](../../../tests/e2e/test_admin_prompt_config.py#L91), [92](../../../tests/e2e/test_admin_prompt_config.py#L92), [94](../../../tests/e2e/test_admin_prompt_config.py#L94), [95](../../../tests/e2e/test_admin_prompt_config.py#L95), [96](../../../tests/e2e/test_admin_prompt_config.py#L96), [101](../../../tests/e2e/test_admin_prompt_config.py#L101).

**Suiteweite Gegenprüfung:** Die bestehende Testgrenze bleibt nach Abgleich der zugeordneten Tests und aktualisierter Suchspur offen. Frühere Lauf-/Mutationsangaben sind historische Belege vom 26.09.2026, keine neue Ausführung.

**Suchspur:** 263 versionierte Test-/Hilfsdateien durchsucht, 4 passende Zeilen. Regexe: ` createAdminClient|admin-api.js|\[object Object\] `, ` Configuration changed in another session `. Vollständige Treffer mit Pfad/Zeile in [search-evidence.json](search-evidence.json) unter ` G-019 `.

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

**Aktuelle Bewertung:** open — Die bestehende Testgrenze bleibt nach Abgleich der zugeordneten Tests und aktualisierter Suchspur offen. Frühere Lauf-/Mutationsangaben sind historische Belege vom 26.09.2026, keine neue Ausführung.

**Produktbeleg:** [app/services/og_image.py](../../../app/services/og_image.py#L93) — ` def render_share_card( `; [app/api/routers/share.py](../../../app/api/routers/share.py#L550) — ` def share_og_card( `

**Vorhandene relevante Prüfungen:**

- [ShareSeoEnhancementTests::test_og_card_route_and_meta](../../../tests/test_share_feature.py#L2597) — Große Unit-/Service-/Router-/SSR-Suite mit FakeDb und lokalen Cachethreads. Assertionstellen: [2604](../../../tests/test_share_feature.py#L2604), [2605](../../../tests/test_share_feature.py#L2605), [2606](../../../tests/test_share_feature.py#L2606), [2607](../../../tests/test_share_feature.py#L2607), [2608](../../../tests/test_share_feature.py#L2608), [2609](../../../tests/test_share_feature.py#L2609).
- [ShareSeoEnhancementTests::test_og_card_404_for_private_pages](../../../tests/test_share_feature.py#L2611) — Große Unit-/Service-/Router-/SSR-Suite mit FakeDb und lokalen Cachethreads. Assertionstellen: [2615](../../../tests/test_share_feature.py#L2615).

**Suiteweite Gegenprüfung:** Die bestehende Testgrenze bleibt nach Abgleich der zugeordneten Tests und aktualisierter Suchspur offen. Frühere Lauf-/Mutationsangaben sind historische Belege vom 26.09.2026, keine neue Ausführung.

**Suchspur:** 263 versionierte Test-/Hilfsdateien durchsucht, 4 passende Zeilen. Regexe: ` og_image|og\.png|share_card|render_share_card `. Vollständige Treffer mit Pfad/Zeile in [search-evidence.json](search-evidence.json) unter ` G-020 `.

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

**Aktuelle Bewertung:** open — Die bestehende Testgrenze bleibt nach Abgleich der zugeordneten Tests und aktualisierter Suchspur offen. Frühere Lauf-/Mutationsangaben sind historische Belege vom 26.09.2026, keine neue Ausführung.

**Produktbeleg:** [static/js/analytics-opt-out.js](../../../static/js/analytics-opt-out.js#L3) — ` const flag = `

**Vorhandene relevante Prüfungen:**

- [test_partial_ships_the_self_exclusion_switch](../../../tests/test_analytics_partial.py#L59) — Quelltextverträge. Assertionstellen: [67](../../../tests/test_analytics_partial.py#L67), [68](../../../tests/test_analytics_partial.py#L68), [69](../../../tests/test_analytics_partial.py#L69).

**Suiteweite Gegenprüfung:** Die bestehende Testgrenze bleibt nach Abgleich der zugeordneten Tests und aktualisierter Suchspur offen. Frühere Lauf-/Mutationsangaben sind historische Belege vom 26.09.2026, keine neue Ausführung.

**Suchspur:** 263 versionierte Test-/Hilfsdateien durchsucht, 7 passende Zeilen. Regexe: ` analytics-opt-out|notrack|umami.disabled `. Vollständige Treffer mit Pfad/Zeile in [search-evidence.json](search-evidence.json) unter ` G-021 `.

| Szenario | Erwartung |
|---|---|
| Given | notrack=1, 0, anderer/fehlender Wert und Storage mit setItem-/removeItem-Fehlern. Das Skript liest Storage nicht über getItem. |
| When | Originalskript in isoliertem DOM vor einem instrumentierten Trackerstart ausführen. |
| Then | Flag korrekt gesetzt/entfernt/erhalten und vor Trackerbeobachtung wirksam; blockierter Storage bricht Seitenstart nicht ab. |

**Zielstellen:** ` tests/js/analytics-opt-out.test.mjs ` (vorgeschlagen)

**Wiederverwenden:** [tests/js/helpers/appWindow.mjs](../../../tests/js/helpers/appWindow.mjs), [tests/test_analytics_partial.py](../../../tests/test_analytics_partial.py)

**Validierung nach Implementierung:** ` npm test -- tests/js/analytics-opt-out.test.mjs; python -m pytest tests/test_analytics_partial.py -q `

**Gezielte Negativkontrolle:** Bedingungen 1/0 vertauschen oder in unerreichbaren Block stellen; Verhaltenstest muss rot werden.


<a id="g-022"></a>

## G-022 · Account-Reparaturskript ohne Produktionszugriff prüfen

**P1 · missing_case** · Verträge: [TOOLS-01](matrix.md#tools-01) · Paket: [WP-25](work-packages.md#wp-25)

**Aktuelle Bewertung:** open — Die bestehende Testgrenze bleibt nach Abgleich der zugeordneten Tests und aktualisierter Suchspur offen. Frühere Lauf-/Mutationsangaben sind historische Belege vom 26.09.2026, keine neue Ausführung.

**Produktbeleg:** [scripts/repair_agent_allowance.py](../../../scripts/repair_agent_allowance.py#L16) — ` def main(): `

**Vorhandene relevante Prüfungen:**

Kein direkter repräsentativer Testbeleg für diese Grenze; Suchtreffer und verwandte Verträge sind separat berücksichtigt.

**Suiteweite Gegenprüfung:** Die bestehende Testgrenze bleibt nach Abgleich der zugeordneten Tests und aktualisierter Suchspur offen. Frühere Lauf-/Mutationsangaben sind historische Belege vom 26.09.2026, keine neue Ausführung.

**Suchspur:** 263 versionierte Test-/Hilfsdateien durchsucht, 0 passende Zeilen. Regexe: ` repair_agent_allowance|Production repair cannot|Configured Firebase project `. Vollständige Treffer mit Pfad/Zeile in [search-evidence.json](search-evidence.json) unter ` G-022 `.

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

**Aktuelle Bewertung:** open — Die bestehende Testgrenze bleibt nach Abgleich der zugeordneten Tests und aktualisierter Suchspur offen. Frühere Lauf-/Mutationsangaben sind historische Belege vom 26.09.2026, keine neue Ausführung.

**Produktbeleg:** [scripts/backfill_claim_keys.py](../../../scripts/backfill_claim_keys.py#L41) — ` def backfill_topic( `; [scripts/backfill_claim_keys.py](../../../scripts/backfill_claim_keys.py#L76) — ` def main() `

**Vorhandene relevante Prüfungen:**

Kein direkter repräsentativer Testbeleg für diese Grenze; Suchtreffer und verwandte Verträge sind separat berücksichtigt.

**Suiteweite Gegenprüfung:** Die bestehende Testgrenze bleibt nach Abgleich der zugeordneten Tests und aktualisierter Suchspur offen. Frühere Lauf-/Mutationsangaben sind historische Belege vom 26.09.2026, keine neue Ausführung.

**Suchspur:** 263 versionierte Test-/Hilfsdateien durchsucht, 0 passende Zeilen. Regexe: ` backfill_claim_keys|backfill_topic|Would update `. Vollständige Treffer mit Pfad/Zeile in [search-evidence.json](search-evidence.json) unter ` G-023 `.

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

**Aktuelle Bewertung:** open — Die bestehende Testgrenze bleibt nach Abgleich der zugeordneten Tests und aktualisierter Suchspur offen. Frühere Lauf-/Mutationsangaben sind historische Belege vom 26.09.2026, keine neue Ausführung.

**Produktbeleg:** [.github/workflows/publisher-tests.yml](../../../.github/workflows/publisher-tests.yml#L1) — ` name: `; [package.json](../../../package.json#L9) — ` "test": `

**Vorhandene relevante Prüfungen:**

Kein direkter repräsentativer Testbeleg für diese Grenze; Suchtreffer und verwandte Verträge sind separat berücksichtigt.

**Suiteweite Gegenprüfung:** Die bestehende Testgrenze bleibt nach Abgleich der zugeordneten Tests und aktualisierter Suchspur offen. Frühere Lauf-/Mutationsangaben sind historische Belege vom 26.09.2026, keine neue Ausführung.

**Suchspur:** 263 versionierte Test-/Hilfsdateien durchsucht, 877 passende Zeilen. Regexe: ` publisher-tests|pytest|vitest `. Vollständige Treffer mit Pfad/Zeile in [search-evidence.json](search-evidence.json) unter ` G-024 `.

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

## G-025 · Aktuelle Browserfälle ausführen und rote Fälle klären

**P1 · execution_gap** · Verträge: [BUILD-02](matrix.md#build-02), [UI-06](matrix.md#ui-06) · Paket: [WP-03](work-packages.md#wp-03)

**Aktuelle Bewertung:** partially_addressed — Aktuell 308 E2E-Fälle gesammelt. Der writerfreie Chromiumlauf wird in execution.json dokumentiert; Transaktions-/Smoke-Fälle bleiben getrennt. Alte Zahl 267 ist ein historischer Laufumfang.

**Produktbeleg:** [tests/e2e/conftest.py](../../../tests/e2e/conftest.py#L126) — ` browser = p.chromium.launch() `

**Vorhandene relevante Prüfungen:**

Kein direkter repräsentativer Testbeleg für diese Grenze; Suchtreffer und verwandte Verträge sind separat berücksichtigt.

**Suiteweite Gegenprüfung:** Aktuell 308 E2E-Fälle gesammelt. Der writerfreie Chromiumlauf wird in execution.json dokumentiert; Transaktions-/Smoke-Fälle bleiben getrennt. Alte Zahl 267 ist ein historischer Laufumfang.

**Suchspur:** 263 versionierte Test-/Hilfsdateien durchsucht, 2 passende Zeilen. Regexe: ` chromium.launch|def browser\( `. Vollständige Treffer mit Pfad/Zeile in [search-evidence.json](search-evidence.json) unter ` G-025 `.

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

**Aktuelle Bewertung:** partially_addressed — Aktuelle Tests laufen unter Windows; test_dev_cli.py wird nicht mehr wegen fehlender PowerShell übersprungen. Tatsächlicher Gesamtstart mit Java/Firebase-Emulator über dev.ps1 bleibt gesondert.

**Produktbeleg:** [dev.ps1](../../../dev.ps1#L14) — ` param( `; [tests/test_dev_cli.py](../../../tests/test_dev_cli.py#L25) — ` @pytest.fixture(params=SHELLS or [None] `

**Vorhandene relevante Prüfungen:**

Kein direkter repräsentativer Testbeleg für diese Grenze; Suchtreffer und verwandte Verträge sind separat berücksichtigt.

**Suiteweite Gegenprüfung:** Aktuelle Tests laufen unter Windows; test_dev_cli.py wird nicht mehr wegen fehlender PowerShell übersprungen. Tatsächlicher Gesamtstart mit Java/Firebase-Emulator über dev.ps1 bleibt gesondert.

**Suchspur:** 263 versionierte Test-/Hilfsdateien durchsucht, 1 passende Zeilen. Regexe: ` Windows PowerShell entry point|win32 `. Vollständige Treffer mit Pfad/Zeile in [search-evidence.json](search-evidence.json) unter ` G-026 `.

| Szenario | Erwartung |
|---|---|
| Given | Windowsrunner mit PowerShell und isolierten Tool-Doubles/Dependencies. |
| When | Alle vorhandenen test_dev_cli-Fälle und repräsentative dev.ps1 check-Aufrufe ausführen. |
| Then | Alle 12 Varianten je verfügbarer Windows-Shell erhalten echten Pass/Fail-Status (derzeit 12 oder 24 Fälle bei einer oder zwei Shells); Shellversionen und gesammelte Fallzahl sind dokumentiert. Exitcodes und Pfad-/Argumentweitergabe funktionieren. |

**Zielstellen:** [tests/test_dev_cli.py](../../../tests/test_dev_cli.py), ` .github/workflows/tests.yml ` (vorgeschlagen)

**Wiederverwenden:** [docs/testing.md](../../testing.md), [dev.ps1](../../../dev.ps1)

**Validierung nach Implementierung:** ` Windows: python -m pytest tests/test_dev_cli.py -q `

**Gezielte Negativkontrolle:** Runner-Exitcode verschlucken; bestehender Fehlerpropagationstest muss rot werden.


<a id="g-027"></a>

## G-027 · Zwei veraltete Emulatorfixtures reparieren

**P1 · broken_test** · Verträge: [WATCH-01](matrix.md#watch-01), [SHARE-01](matrix.md#share-01) · Paket: [WP-01](work-packages.md#wp-01)

**Aktuelle Bewertung:** open — Die bestehende Testgrenze bleibt nach Abgleich der zugeordneten Tests und aktualisierter Suchspur offen. Frühere Lauf-/Mutationsangaben sind historische Belege vom 26.09.2026, keine neue Ausführung.

**Produktbeleg:** [tests/e2e/test_phase2_transactions.py](../../../tests/e2e/test_phase2_transactions.py#L56) — ` is_pro=False `; [tests/e2e/test_phase2_transactions.py](../../../tests/e2e/test_phase2_transactions.py#L98) — ` pending_ref.set({ `

**Vorhandene relevante Prüfungen:**

- [test_two_workers_cannot_exceed_owner_watch_limit](../../../tests/e2e/test_phase2_transactions.py#L24) — Firestore-Emulatorintegration mit echten SDK-Transaktionen und Threads. Assertionstellen: [66](../../../tests/e2e/test_phase2_transactions.py#L66), [73](../../../tests/e2e/test_phase2_transactions.py#L73), [78](../../../tests/e2e/test_phase2_transactions.py#L78).
- [test_two_workers_publish_one_pending_share_and_consume_one_quota](../../../tests/e2e/test_phase2_transactions.py#L92) — Firestore-Emulatorintegration mit echten SDK-Transaktionen und Threads. Assertionstellen: [115](../../../tests/e2e/test_phase2_transactions.py#L115), [116](../../../tests/e2e/test_phase2_transactions.py#L116), [121](../../../tests/e2e/test_phase2_transactions.py#L121).

**Suiteweite Gegenprüfung:** Die bestehende Testgrenze bleibt nach Abgleich der zugeordneten Tests und aktualisierter Suchspur offen. Frühere Lauf-/Mutationsangaben sind historische Belege vom 26.09.2026, keine neue Ausführung.

**Suchspur:** 263 versionierte Test-/Hilfsdateien durchsucht, 6 passende Zeilen. Regexe: ` is_pro=False|test_two_workers_publish_one_pending_share|test_two_workers_cannot_exceed_owner_watch_limit `. Vollständige Treffer mit Pfad/Zeile in [search-evidence.json](search-evidence.json) unter ` G-027 `.

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

**Aktuelle Bewertung:** open — Erneut fehlgeschlagen: test_archived_turns_use_the_same_drawer_row_as_the_live_answer erwartet weiterhin den exakten alten Klassenstring.

**Produktbeleg:** [tests/test_consensus_progress_ui.py](../../../tests/test_consensus_progress_ui.py#L339) — ` tab.className = `; [static/js/consensus-run.js](../../../static/js/consensus-run.js#L411) — ` consensus-tab consensus-evidence-action `

**Vorhandene relevante Prüfungen:**

- [test_archived_turns_use_the_same_drawer_row_as_the_live_answer](../../../tests/test_consensus_progress_ui.py#L326) — Quelltextverträge. Assertionstellen: [337](../../../tests/test_consensus_progress_ui.py#L337), [338](../../../tests/test_consensus_progress_ui.py#L338), [339](../../../tests/test_consensus_progress_ui.py#L339), [340](../../../tests/test_consensus_progress_ui.py#L340), [341](../../../tests/test_consensus_progress_ui.py#L341), [342](../../../tests/test_consensus_progress_ui.py#L342), [345](../../../tests/test_consensus_progress_ui.py#L345), [346](../../../tests/test_consensus_progress_ui.py#L346), [348](../../../tests/test_consensus_progress_ui.py#L348), [349](../../../tests/test_consensus_progress_ui.py#L349).

**Suiteweite Gegenprüfung:** Erneut fehlgeschlagen: test_archived_turns_use_the_same_drawer_row_as_the_live_answer erwartet weiterhin den exakten alten Klassenstring.

**Suchspur:** 263 versionierte Test-/Hilfsdateien durchsucht, 4 passende Zeilen. Regexe: ` test_archived_turns_use_the_same_drawer_row|consensus-evidence-action `. Vollständige Treffer mit Pfad/Zeile in [search-evidence.json](search-evidence.json) unter ` G-028 `.

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

**Aktuelle Bewertung:** open — Die bestehende Testgrenze bleibt nach Abgleich der zugeordneten Tests und aktualisierter Suchspur offen. Frühere Lauf-/Mutationsangaben sind historische Belege vom 26.09.2026, keine neue Ausführung.

**Produktbeleg:** [tests/e2e/test_phase2_transactions.py](../../../tests/e2e/test_phase2_transactions.py#L161) — ` def test_parallel_reports_never_lose_increments `

**Vorhandene relevante Prüfungen:**

- [test_parallel_reports_never_lose_increments_or_noindex_transition](../../../tests/e2e/test_phase2_transactions.py#L161) — Firestore-Emulatorintegration mit echten SDK-Transaktionen und Threads. Assertionstellen: [183](../../../tests/e2e/test_phase2_transactions.py#L183), [184](../../../tests/e2e/test_phase2_transactions.py#L184), [185](../../../tests/e2e/test_phase2_transactions.py#L185), [186](../../../tests/e2e/test_phase2_transactions.py#L186), [187](../../../tests/e2e/test_phase2_transactions.py#L187).

**Suiteweite Gegenprüfung:** Die bestehende Testgrenze bleibt nach Abgleich der zugeordneten Tests und aktualisierter Suchspur offen. Frühere Lauf-/Mutationsangaben sind historische Belege vom 26.09.2026, keine neue Ausführung.

**Suchspur:** 263 versionierte Test-/Hilfsdateien durchsucht, 1 passende Zeilen. Regexe: ` test_parallel_reports_never_lose_increments `. Vollständige Treffer mit Pfad/Zeile in [search-evidence.json](search-evidence.json) unter ` G-029 `.

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

**Aktuelle Bewertung:** partially_addressed — Ein neuer Agentloop verbindet Datei, Angebote, Vergleich, Dokument und Gmailentwurf; Browserfälle sind weiterhin an API-Doubles getrennt. Keine zusätzliche vollständige persistierte Browserreise belegt.

**Produktbeleg:** [tests/e2e/conftest.py](../../../tests/e2e/conftest.py#L140) — ` ctx.route("**/static/firebase.js*" `; [tests/e2e/test_phase4_frontend.py](../../../tests/e2e/test_phase4_frontend.py#L130) — ` def _real_firebase_page `

**Vorhandene relevante Prüfungen:**

Kein direkter repräsentativer Testbeleg für diese Grenze; Suchtreffer und verwandte Verträge sind separat berücksichtigt.

**Suiteweite Gegenprüfung:** Ein neuer Agentloop verbindet Datei, Angebote, Vergleich, Dokument und Gmailentwurf; Browserfälle sind weiterhin an API-Doubles getrennt. Keine zusätzliche vollständige persistierte Browserreise belegt.

**Suchspur:** 263 versionierte Test-/Hilfsdateien durchsucht, 1257 passende Zeilen. Regexe: ` firebase_stub|_real_firebase_page|route\(|recover_only|bookmark `. Vollständige Treffer mit Pfad/Zeile in [search-evidence.json](search-evidence.json) unter ` G-030 `.

| Szenario | Erwartung |
|---|---|
| Given | Echter App-Bundle/Firebase-Appcode und Backend mit lokalem Demo-Firestore; nur externe Identitäts-/Providergrenzen kontrolliert ersetzt, keine Bookmark-/Chat-/Usage-Routen. |
| When | Consensus bis Bookmark speichern, Reload und Follow-up; zweiter paralleler Run/Viewwechsel; Stop/Verbindungsverlust; Konto A→B; analog Agent-Recover. |
| Then | DB-Endzustand und UI stimmen je Turn/Owner überein, einschließlich erfolgreicher Antwort mit ausdrücklich gemeldetem Persistenzfehler. Regulärer Consensus belastet den Run einmal; Agent-Settlement berücksichtigt die tatsächlich angefallenen Providersteps laut Ledger ohne Doppelbuchung bei Recovery. Kein zweiter Modellstart bei zugesagtem Replay und keine verlorene Zwischenantwort/fremde Projektion. Netzwerkreihenfolge gezielt kontrollieren. |

**Zielstellen:** ` tests/e2e/test_persisted_user_journeys.py ` (vorgeschlagen)

**Wiederverwenden:** [tests/e2e/conftest.py](../../../tests/e2e/conftest.py), [tests/e2e/test_phase4_frontend.py](../../../tests/e2e/test_phase4_frontend.py), [tests/test_consensus_chat_history.py](../../../tests/test_consensus_chat_history.py)

**Validierung nach Implementierung:** ` RUN_E2E=1 python -m pytest tests/e2e/test_persisted_user_journeys.py -q (Demo-Emulator) `

**Gezielte Negativkontrolle:** Bookmark-/Context-/Usage-ID an einer Grenze vertauschen; nur ein echter persistierter Endzustand darf den Test bestehen.


<a id="g-031"></a>

## G-031 · Due-Queries und Scheduler-Claims mit SDK-Formen

**P2 · missing_integration** · Verträge: [WATCH-02](matrix.md#watch-02), [TOPIC-01](matrix.md#topic-01), [SEO-04](matrix.md#seo-04) · Paket: [WP-19](work-packages.md#wp-19)

**Aktuelle Bewertung:** partially_addressed — Workerleaseowner, verlorene Lease und stale Watchcompletion haben neue Fake-Nachweise. Native SDK-Queries/Transaktionskonflikte samt Probe-/Outboxclaims bleiben offen.

**Produktbeleg:** [app/services/watch_service.py](../../../app/services/watch_service.py#L1472) — ` def list_due_watch_ids( `; [app/services/topics.py](../../../app/services/topics.py#L1103) — ` def claim_topic_run( `; [app/services/topics.py](../../../app/services/topics.py#L1050) — ` def list_due_topic_ids( `; [app/services/seo_weekly_review.py](../../../app/services/seo_weekly_review.py#L1350) — ` async def seo_review_scheduler_loop `

**Vorhandene relevante Prüfungen:**

- [SchedulerSafetyTests::test_claim_transaction_prevents_double_run](../../../tests/test_watch_feature.py#L760) — Große Service-/Scheduler-/Router-/Mailformat-Suite mit DB-/LLM-/Versand-Doubles plus UI-Sourceverträge. Assertionstellen: [767](../../../tests/test_watch_feature.py#L767), [768](../../../tests/test_watch_feature.py#L768), [769](../../../tests/test_watch_feature.py#L769), [770](../../../tests/test_watch_feature.py#L770), [771](../../../tests/test_watch_feature.py#L771).
- [test_default_interval_is_seven_days_and_lease_is_persistent](../../../tests/test_seo_weekly_review.py#L81) — Review-Service mit Repository-/Judge-/Action-Doubles. Assertionstellen: [86](../../../tests/test_seo_weekly_review.py#L86), [87](../../../tests/test_seo_weekly_review.py#L87), [88](../../../tests/test_seo_weekly_review.py#L88), [89](../../../tests/test_seo_weekly_review.py#L89).

**Suiteweite Gegenprüfung:** Workerleaseowner, verlorene Lease und stale Watchcompletion haben neue Fake-Nachweise. Native SDK-Queries/Transaktionskonflikte samt Probe-/Outboxclaims bleiben offen.

**Suchspur:** 263 versionierte Test-/Hilfsdateien durchsucht, 19 passende Zeilen. Regexe: ` list_due_watch_ids|list_due_topic_ids|claim_topic_run|acquire_worker_lease|seo_review_scheduler_loop `. Vollständige Treffer mit Pfad/Zeile in [search-evidence.json](search-evidence.json) unter ` G-031 `.

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

**Aktuelle Bewertung:** partially_addressed — ASGI-Test für unveränderte SSE-Frames hinzugekommen. Das ersetzt keine echten Socket-/Proxytests für Disconnect, Chunking und Providergrenzen.

**Produktbeleg:** [app/services/llm/provider_runtime.py](../../../app/services/llm/provider_runtime.py#L170) — ` def managed_provider_resource `; [app/services/source_documents.py](../../../app/services/source_documents.py#L92) — ` async def _download( `

**Vorhandene relevante Prüfungen:**

Kein direkter repräsentativer Testbeleg für diese Grenze; Suchtreffer und verwandte Verträge sind separat berücksichtigt.

**Suiteweite Gegenprüfung:** ASGI-Test für unveränderte SSE-Frames hinzugekommen. Das ersetzt keine echten Socket-/Proxytests für Disconnect, Chunking und Providergrenzen.

**Suchspur:** 263 versionierte Test-/Hilfsdateien durchsucht, 10 passende Zeilen. Regexe: ` MockTransport|real_provider_socket_stall|http.server|ThreadingHTTPServer|TCPServer `. Vollständige Treffer mit Pfad/Zeile in [search-evidence.json](search-evidence.json) unter ` G-032 `.

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

**Aktuelle Bewertung:** open — Die bestehende Testgrenze bleibt nach Abgleich der zugeordneten Tests und aktualisierter Suchspur offen. Frühere Lauf-/Mutationsangaben sind historische Belege vom 26.09.2026, keine neue Ausführung.

**Produktbeleg:** [app/core/request_limits.py](../../../app/core/request_limits.py#L12) — ` def configured_max_request_body_bytes `; [app/core/request_limits.py](../../../app/core/request_limits.py#L58) — ` except ValueError: `

**Vorhandene relevante Prüfungen:**

- [test_exact_limit_body_is_replayed_once_to_the_application](../../../tests/test_request_body_limits.py#L61) — ASGI-Middleware mit kontrollierten Receive-/Send-Funktionen. Assertionstellen: [69](../../../tests/test_request_body_limits.py#L69), [70](../../../tests/test_request_body_limits.py#L70).

**Suiteweite Gegenprüfung:** Die bestehende Testgrenze bleibt nach Abgleich der zugeordneten Tests und aktualisierter Suchspur offen. Frühere Lauf-/Mutationsangaben sind historische Belege vom 26.09.2026, keine neue Ausführung.

**Suchspur:** 263 versionierte Test-/Hilfsdateien durchsucht, 2 passende Zeilen. Regexe: ` MAX_REQUEST_BODY_BYTES|Invalid Content-Length|configured_max_request_body|content-length `. Vollständige Treffer mit Pfad/Zeile in [search-evidence.json](search-evidence.json) unter ` G-033 `.

| Szenario | Erwartung |
|---|---|
| Given | Header fehlt/negativ/nichtnumerisch, non-HTTP-Scope, frühzeitiger Disconnect sowie Envwerte unter/auf/über den Grenzen. |
| When | Middleware direkt über vorhandenen ASGI-Harness ausführen. |
| Then | Handler sieht keine abgelehnte Übergröße; Fehlerstatus ist bewusst festgelegt; gültige Grenzen passen, configured_max_request_body_bytes bzw. die Middlewarekonstruktion lehnt ungültige Konfiguration ab (die Konstruktion kann erst beim ersten Request erfolgen). Protokollstatus 400 versus bestehendes 413 nicht unbegründet ändern. |

**Zielstellen:** [tests/test_request_body_limits.py](../../../tests/test_request_body_limits.py)

**Wiederverwenden:** [tests/test_request_body_limits.py](../../../tests/test_request_body_limits.py)

**Validierung nach Implementierung:** ` python -m pytest tests/test_request_body_limits.py -q `

**Gezielte Negativkontrolle:** Negative Content-Length passieren lassen; Nichtaufrufassertion muss rot werden.


<a id="g-034"></a>

## G-034 · Feedback-Adapter und Statistik-Persistenzwrapper

**P2 · missing_case** · Verträge: [DATA-01](matrix.md#data-01) · Paket: [WP-27](work-packages.md#wp-27)

**Aktuelle Bewertung:** open — Die bestehende Testgrenze bleibt nach Abgleich der zugeordneten Tests und aktualisierter Suchspur offen. Frühere Lauf-/Mutationsangaben sind historische Belege vom 26.09.2026, keine neue Ausführung.

**Produktbeleg:** [app/api/routers/pages.py](../../../app/api/routers/pages.py#L522) — ` def submit_feedback( `; [app/services/differences_stats.py](../../../app/services/differences_stats.py#L181) — ` def record_differences_stats( `

**Vorhandene relevante Prüfungen:**

- [test_feedback_cooldown_and_daily_limit_are_persistent](../../../tests/test_phase5_operations.py#L316) — Gemischt: Services mit DB-/HTTP-Doubles, Thread-/Async-Tests und Deployment-Quelltextverträge. Assertionstellen: [322](../../../tests/test_phase5_operations.py#L322), [328](../../../tests/test_phase5_operations.py#L328).

**Suiteweite Gegenprüfung:** Die bestehende Testgrenze bleibt nach Abgleich der zugeordneten Tests und aktualisierter Suchspur offen. Frühere Lauf-/Mutationsangaben sind historische Belege vom 26.09.2026, keine neue Ausführung.

**Suchspur:** 263 versionierte Test-/Hilfsdateien durchsucht, 6 passende Zeilen. Regexe: ` /feedback|submit_feedback|record_differences_stats `. Vollständige Treffer mit Pfad/Zeile in [search-evidence.json](search-evidence.json) unter ` G-034 `.

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

**Aktuelle Bewertung:** open — Die bestehende Testgrenze bleibt nach Abgleich der zugeordneten Tests und aktualisierter Suchspur offen. Frühere Lauf-/Mutationsangaben sind historische Belege vom 26.09.2026, keine neue Ausführung.

**Produktbeleg:** [benchmark/run_sample.py](../../../benchmark/run_sample.py#L53) — ` def main( `; [benchmark/run_experiment.py](../../../benchmark/run_experiment.py#L62) — ` def main( `

**Vorhandene relevante Prüfungen:**

Kein direkter repräsentativer Testbeleg für diese Grenze; Suchtreffer und verwandte Verträge sind separat berücksichtigt.

**Suiteweite Gegenprüfung:** Die bestehende Testgrenze bleibt nach Abgleich der zugeordneten Tests und aktualisierter Suchspur offen. Frühere Lauf-/Mutationsangaben sind historische Belege vom 26.09.2026, keine neue Ausführung.

**Suchspur:** 263 versionierte Test-/Hilfsdateien durchsucht, 2 passende Zeilen. Regexe: ` run_sample|run_experiment|evaluate_agent_delegation|evaluate_source_verification|probe_agent_delegation|render_watch_preview `. Vollständige Treffer mit Pfad/Zeile in [search-evidence.json](search-evidence.json) unter ` G-035 `.

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

**Aktuelle Bewertung:** open — DOMPurify-Pin und Sanitizerpayloads werden nun geprüft; das führt vendorFrontend mit temporärem Dateisystem/check-only noch nicht aus.

**Produktbeleg:** [scripts/vendor_frontend.mjs](../../../scripts/vendor_frontend.mjs#L7) — ` export async function vendorFrontend( `; [scripts/vendor_frontend.mjs](../../../scripts/vendor_frontend.mjs#L18) — ` if (version !== pins[name]) `

**Vorhandene relevante Prüfungen:**

- [test_app_vendor_assets_are_local_versioned_and_include_fonts_and_licenses](../../../tests/test_frontend_build.py#L158) — Build-Artefakt-/Fingerprint-Verträge. Assertionstellen: [160](../../../tests/test_frontend_build.py#L160), [162](../../../tests/test_frontend_build.py#L162), [164](../../../tests/test_frontend_build.py#L164), [165](../../../tests/test_frontend_build.py#L165), [169](../../../tests/test_frontend_build.py#L169), [172](../../../tests/test_frontend_build.py#L172).

**Suiteweite Gegenprüfung:** DOMPurify-Pin und Sanitizerpayloads werden nun geprüft; das führt vendorFrontend mit temporärem Dateisystem/check-only noch nicht aus.

**Suchspur:** 263 versionierte Test-/Hilfsdateien durchsucht, 1 passende Zeilen. Regexe: ` vendorFrontend|vendor_frontend|Unexpected .*version|checkOnly `, ` does not truncate or rewrite unchanged vendor `. Vollständige Treffer mit Pfad/Zeile in [search-evidence.json](search-evidence.json) unter ` G-036 `.

| Szenario | Erwartung |
|---|---|
| Given | Temporärer Projektbaum mit winzigen synthetischen package.json-/Library-/Font-/Lizenzdateien; keine npm-Downloads. |
| When | Realen vendorFrontend(root, checkOnly) in Build- und Prüfmodus mit richtiger/falscher Paketversion sowie fehlenden/geänderten Assets aufrufen. |
| Then | Gepinnte Version wird verlangt, Dateien/Fonts/Lizenzen vollständig und in stabiler Reihenfolge erfasst; Check-only verändert nichts und entdeckt fehlende/stale Bytes; unveränderte Builds schreiben nicht erneut. |

**Zielstellen:** ` tests/js/vendor-frontend.test.mjs ` (vorgeschlagen)

**Wiederverwenden:** [tests/js/frontend-output.test.mjs](../../../tests/js/frontend-output.test.mjs), [tests/test_frontend_build.py](../../../tests/test_frontend_build.py)

**Validierung nach Implementierung:** ` npm test -- tests/js/vendor-frontend.test.mjs tests/js/frontend-output.test.mjs; python -m pytest tests/test_frontend_build.py -q `

**Gezielte Negativkontrolle:** Versionsvergleich überspringen oder Check-only durch Write ersetzen; Fehler- und Dateisystemassertionen müssen scheitern.


<a id="g-037"></a>

## G-037 · main verwirft HTTPException-Header einschließlich Retry-After

**P1 · observed_behavior_defect** · Verträge: [OPS-02](matrix.md#ops-02), [API-01](matrix.md#api-01), [AGENT-01](matrix.md#agent-01) · Paket: [WP-31](work-packages.md#wp-31)

**Aktuelle Bewertung:** resolved — Behoben in c929e343: main übernimmt exc.headers. test_registered_http_exception_handler_preserves_headers prüft 429/503 Retry-After und 401 WWW-Authenticate durch den registrierten Handler; aktuelle Pythondatei grün. Echte Ablehnungspfade bleiben zusätzliche Integration.

**Produktbeleg:** [main.py](../../../main.py#L242) — ` content={"error": exc.detail} `; [app/api/routers/api_v1.py](../../../app/api/routers/api_v1.py#L173) — ` def enforce_uid_rate_limit( `; [app/api/routers/agent.py](../../../app/api/routers/agent.py#L164) — ` def run_agent( `

**Vorhandene relevante Prüfungen:**

- [test_local_capacity_rejects_before_creating_a_turn_and_preserves_replay](../../../tests/test_agent_capacity.py#L74) — Agent-Kapazität und API mit synchronisiertem Store-Fake. Assertionstellen: [83](../../../tests/test_agent_capacity.py#L83), [84](../../../tests/test_agent_capacity.py#L84), [85](../../../tests/test_agent_capacity.py#L85), [88](../../../tests/test_agent_capacity.py#L88), [91](../../../tests/test_agent_capacity.py#L91), [94](../../../tests/test_agent_capacity.py#L94).
- [ClientIpKeyTests::test_uid_limiter_cannot_be_bypassed_with_another_key](../../../tests/test_rate_limit.py#L74) — Rate-Key-/UID-Limiter-Funktionen. Assertionstellen: [77](../../../tests/test_rate_limit.py#L77).
- [test_rate_limit_blocks_immediate_resubmission_without_another_paid_claim](../../../tests/test_agent_search.py#L121) — Usage-/Cooldownlogik, Agent-API und geskripteter Transport. Assertionstellen: [137](../../../tests/test_agent_search.py#L137), [139](../../../tests/test_agent_search.py#L139), [140](../../../tests/test_agent_search.py#L140), [141](../../../tests/test_agent_search.py#L141).

**Suiteweite Gegenprüfung:** Behoben in c929e343: main übernimmt exc.headers. test_registered_http_exception_handler_preserves_headers prüft 429/503 Retry-After und 401 WWW-Authenticate durch den registrierten Handler; aktuelle Pythondatei grün. Echte Ablehnungspfade bleiben zusätzliche Integration.

**Suchspur:** 263 versionierte Test-/Hilfsdateien durchsucht, 40 passende Zeilen. Regexe: ` Retry.After|enforce_uid_rate_limit|handle_http_exception `, ` TestClient\(main\.app\) `. Vollständige Treffer mit Pfad/Zeile in [search-evidence.json](search-evidence.json) unter ` G-037 `.

| Szenario | Erwartung |
|---|---|
| Given | Reales main.app, eine ausgeschöpfte UID-Quote sowie Agent-Cooldown/volle Kapazität; gültige lokale Auth-/DB-Doubles, kein Provider. |
| When | Tatsächliche Consensus-/Agent-Routen bis zur Ablehnung aufrufen, erfolgreiche Kontrolle ergänzen. |
| Then | 429/503, sichere Fehlermeldung und vorgesehenes Retry-After bleiben gemeinsam erhalten; Ablehnung startet weder Provider noch unerlaubten Write. Vorgesehene Exceptionheader werden bewahrt, keine frei vom Request kopierten Header. |

**Zielstellen:** [tests/test_consensus_api.py](../../../tests/test_consensus_api.py), [tests/test_agent_capacity.py](../../../tests/test_agent_capacity.py), [tests/test_agent_search.py](../../../tests/test_agent_search.py)

**Wiederverwenden:** [tests/test_consensus_api.py](../../../tests/test_consensus_api.py), [tests/test_agent_capacity.py](../../../tests/test_agent_capacity.py)

**Validierung nach Implementierung:** ` python -m pytest tests/test_consensus_api.py tests/test_agent_capacity.py tests/test_agent_search.py -q `

**Gezielte Negativkontrolle:** headers-Weitergabe im main-Handler entfernen: neue main.app-Headerassertion muss scheitern, obwohl die bestehenden isolierten Routertests grün bleiben.


<a id="g-038"></a>

## G-038 · Undo kürzt früheren Inhalt nach Absenkung des Memorylimits

**P1 · observed_behavior_defect** · Verträge: [MEM-02](matrix.md#mem-02) · Paket: [WP-10](work-packages.md#wp-10)

**Aktuelle Bewertung:** open — Undo sanitisiert den Vorzustand weiterhin mit dem aktuellen memory_limit; nach Limitabsenkung bleibt stilles Kürzen möglich. Lease-/CAS-/Retentionkorrekturen lösen diese Grenze nicht.

**Produktbeleg:** [app/services/memory_edit.py](../../../app/services/memory_edit.py#L701) — ` def undo( `; [app/services/memory_edit.py](../../../app/services/memory_edit.py#L741) — ` revision.get("before") or {}, max_notes_chars=memory_limit `

**Vorhandene relevante Prüfungen:**

- [test_replace_is_revision_checked_and_undo_restores_exact_content](../../../tests/test_memory_edit.py#L178) — Edit-Service/Repository und Router mit DB-/LLM-Doubles. Assertionstellen: [189](../../../tests/test_memory_edit.py#L189), [204](../../../tests/test_memory_edit.py#L204), [208](../../../tests/test_memory_edit.py#L208), [209](../../../tests/test_memory_edit.py#L209), [220](../../../tests/test_memory_edit.py#L220), [221](../../../tests/test_memory_edit.py#L221), [222](../../../tests/test_memory_edit.py#L222), [223](../../../tests/test_memory_edit.py#L223).

**Suiteweite Gegenprüfung:** Undo sanitisiert den Vorzustand weiterhin mit dem aktuellen memory_limit; nach Limitabsenkung bleibt stilles Kürzen möglich. Lease-/CAS-/Retentionkorrekturen lösen diese Grenze nicht.

**Suchspur:** 263 versionierte Test-/Hilfsdateien durchsucht, 23 passende Zeilen. Regexe: ` \.undo\(|/memory/undo `, ` over.*limit|memory_limit `. Vollständige Treffer mit Pfad/Zeile in [search-evidence.json](search-evidence.json) unter ` G-038 `.

| Szenario | Erwartung |
|---|---|
| Given | Profil über dem inzwischen abgesenkten Limit, gültige Undo-ID ohne Zwischenwrite; unverändertes Limit und exakte Grenze als Kontrollen. |
| When | Rollenedit rückgängig machen, nachdem Tier oder Adminlimit abgesenkt wurde; HTTP-Pfad ebenso prüfen. |
| Then | Kein stilles Truncation-Save. Empfohlen: Undo mit strukturiertem memory_limit-Fehler ohne jeglichen Write ablehnen, wenn das alte Profil nicht mehr zulässig ist. Alternativ nur nach expliziter Produktentscheidung verlustfrei wiederherstellen. Erfolgsfall vergleicht alle Profilfelder, nicht nur die editierten. |

**Zielstellen:** [tests/test_memory_edit.py](../../../tests/test_memory_edit.py)

**Wiederverwenden:** [tests/test_memory_edit.py](../../../tests/test_memory_edit.py)

**Validierung nach Implementierung:** ` python -m pytest tests/test_memory_edit.py -q `

**Gezielte Negativkontrolle:** Aktuelles sanitize_profile(before, kleineres Limit) muss die neue Datenintegritätsassertion verletzen; nicht den abgeschnittenen Text als Sollwert übernehmen.


<a id="g-039"></a>

## G-039 · Erfolgreicher Agentdetail- und Stop-HTTP-Pfad fehlen

**P1 · missing_case** · Verträge: [AGENT-03](matrix.md#agent-03), [AGENT-04](matrix.md#agent-04) · Paket: [WP-32](work-packages.md#wp-32)

**Aktuelle Bewertung:** open — Die bestehende Testgrenze bleibt nach Abgleich der zugeordneten Tests und aktualisierter Suchspur offen. Frühere Lauf-/Mutationsangaben sind historische Belege vom 26.09.2026, keine neue Ausführung.

**Produktbeleg:** [app/api/routers/agent.py](../../../app/api/routers/agent.py#L410) — ` def agent_details( `; [app/api/routers/agent.py](../../../app/api/routers/agent.py#L430) — ` def stop_agent_run( `

**Vorhandene relevante Prüfungen:**

- [test_delegation_endpoints_are_owner_bound_and_read_only](../../../tests/test_agent_delegation.py#L265) — Echte Workerthreads/Mailboxen mit Store- und Provider-Doubles. Assertionstellen: [270](../../../tests/test_agent_delegation.py#L270), [271](../../../tests/test_agent_delegation.py#L271), [272](../../../tests/test_agent_delegation.py#L272), [273](../../../tests/test_agent_delegation.py#L273), [274](../../../tests/test_agent_delegation.py#L274), [275](../../../tests/test_agent_delegation.py#L275).

**Suiteweite Gegenprüfung:** Die bestehende Testgrenze bleibt nach Abgleich der zugeordneten Tests und aktualisierter Suchspur offen. Frühere Lauf-/Mutationsangaben sind historische Belege vom 26.09.2026, keine neue Ausführung.

**Suchspur:** 263 versionierte Test-/Hilfsdateien durchsucht, 12 passende Zeilen. Regexe: ` /agents|/stop `, ` agent_details|stop_agent_run|stop_turn `. Vollständige Treffer mit Pfad/Zeile in [search-evidence.json](search-evidence.json) unter ` G-039 `.

| Szenario | Erwartung |
|---|---|
| Given | Zwei Owner, verschiedene Chats/Turns/Agents; laufende und terminale Delegation, Authlosigkeit, Free/Plus/Pro/Admin sowie Tierausfall. |
| When | GET Detail mit gültiger Seite und Grenzcursors; POST Turn-Stop einschließlich Wiederholung und verspätetem Workerwrite. |
| Then | IDs und UID binden exakt dieselbe Ressource; fremde Daten bleiben verborgen. Pagination hat weder Lücken noch unbeschränkte Antwort; after<0, limit=0/51 werden abgewiesen. Stop wirkt nur auf den gebundenen Turn, ist bei Wiederholung sicher und beendet den Konsens nicht ungewollt. Tier-/Adminregel folgt require_agent_access; private Antwort no-store, kein bezahlter Call durch Detail/Stop. |

**Zielstellen:** [tests/test_agent_delegation.py](../../../tests/test_agent_delegation.py), [tests/test_agent_reliability.py](../../../tests/test_agent_reliability.py)

**Wiederverwenden:** [tests/test_agent_delegation.py](../../../tests/test_agent_delegation.py), [tests/test_agent_reliability.py](../../../tests/test_agent_reliability.py)

**Validierung nach Implementierung:** ` python -m pytest tests/test_agent_delegation.py tests/test_agent_reliability.py -q `

**Gezielte Negativkontrolle:** UID oder turn_id beim Store-Aufruf vertauschen beziehungsweise Stop weglassen: Ownership-/Zustandsassertionen müssen scheitern; ein reiner 422-Test genügt nicht.


<a id="g-040"></a>

## G-040 · Modellrollback überschreibt einen zwischenzeitlichen Writer

**P1 · observed_behavior_defect** · Verträge: [ADMIN-01](matrix.md#admin-01) · Paket: [WP-33](work-packages.md#wp-33)

**Aktuelle Bewertung:** partially_addressed — Behobenes Überschreiben in 6b80daa6: CAS und eigener Revisionsrollback bewahren simulierten fremden Writer. test_model_configuration.py grün; nativer konkurrierender Firestore-/Mehrprozesslauf noch offen.

**Produktbeleg:** [app/api/routers/admin.py](../../../app/api/routers/admin.py#L59) — ` def _persist_and_activate_models( `

**Vorhandene relevante Prüfungen:**

- [ModelConfigurationTests::test_admin_update_restores_persisted_document_on_activation_error](../../../tests/test_model_configuration.py#L147) — Konfigurations-/Payload-Unit-Tests, Admin-/DB-Doubles und UI-Sourceverträge. Assertionstellen: [160](../../../tests/test_model_configuration.py#L160), [164](../../../tests/test_model_configuration.py#L164), [165](../../../tests/test_model_configuration.py#L165), [169](../../../tests/test_model_configuration.py#L169), [170](../../../tests/test_model_configuration.py#L170).

**Suiteweite Gegenprüfung:** Behobenes Überschreiben in 6b80daa6: CAS und eigener Revisionsrollback bewahren simulierten fremden Writer. test_model_configuration.py grün; nativer konkurrierender Firestore-/Mehrprozesslauf noch offen.

**Suchspur:** 263 versionierte Test-/Hilfsdateien durchsucht, 13 passende Zeilen. Regexe: ` persist_and_activate_models|activation_error `, ` rollback|restores_persisted `. Vollständige Treffer mit Pfad/Zeile in [search-evidence.json](search-evidence.json) unter ` G-040 `.

| Szenario | Erwartung |
|---|---|
| Given | Zwei Konfigwriter; A liest initial und schreibt A, B schreibt B vor As Aktivierungsfehler. |
| When | As Rollback nach Bs erfolgreichem Write auslösen; zusätzlich initial fehlendes Dokument und Rollback-RPC-Ausfall. |
| Then | Rollback löscht/überschreibt nur die eigene unveränderte Version mit nativer Precondition/Transaktion. B bleibt erhalten, auch wenn initial nichts existierte. Lokale Runtime bleibt beim eigenen letzten gültigen Stand; Fehler/Recoveryzustand ist ehrlich sichtbar. Keine globale DB-/Runtime-Atomizität behaupten. |

**Zielstellen:** [tests/test_model_configuration.py](../../../tests/test_model_configuration.py), ` tests/e2e/test_model_configuration_transactions.py ` (vorgeschlagen)

**Wiederverwenden:** [tests/test_model_configuration.py](../../../tests/test_model_configuration.py), [tests/e2e/test_prompt_config_transactions.py](../../../tests/e2e/test_prompt_config_transactions.py)

**Validierung nach Implementierung:** ` python -m pytest tests/test_model_configuration.py tests/test_reasoning_policy.py tests/test_source_model_configuration.py -q; zusätzlich gezielter Firestore-Emulatorfall `

**Gezielte Negativkontrolle:** Bedingung aus Rollback entfernen: B-Erhalt muss rot werden; nur final==initial zu prüfen würde den Fehler festschreiben.


<a id="g-041"></a>

## G-041 · Topic-Admingrenze prüft Revocation nicht und verliert Rollen-503

**P1 · observed_behavior_defect** · Verträge: [AUTH-02](matrix.md#auth-02), [TOPIC-01](matrix.md#topic-01) · Paket: [WP-16](work-packages.md#wp-16)

**Aktuelle Bewertung:** open — Topichelper ruft verify_user_token weiterhin ohne check_revoked=True auf; Abweichung zum zentralen Adminhelper bleibt bestehen.

**Produktbeleg:** [app/api/routers/topics.py](../../../app/api/routers/topics.py#L138) — ` def _require_admin( `; [app/api/routers/admin.py](../../../app/api/routers/admin.py#L187) — ` def _require_admin( `; [app/core/security.py](../../../app/core/security.py#L257) — ` check_revoked: bool = False `

**Vorhandene relevante Prüfungen:**

- [test_admin_boundary_checks_revocation_and_maps_tier_outage_to_503](../../../tests/test_auth_revocation.py#L52) — Security-Funktionen mit Auth-/Datenbank-Doubles. Assertionstellen: [65](../../../tests/test_auth_revocation.py#L65), [68](../../../tests/test_auth_revocation.py#L68), [69](../../../tests/test_auth_revocation.py#L69).
- [test_admin_topic_api_creates_updates_and_versions_without_share_data](../../../tests/test_topics_feature.py#L1137) — Große Service-/Router-/SSR-Suite mit FakeFirestore; einzelner echter SDK-Queryaufbau mit RPC-Mock. Assertionstellen: [1149](../../../tests/test_topics_feature.py#L1149), [1154](../../../tests/test_topics_feature.py#L1154), [1155](../../../tests/test_topics_feature.py#L1155), [1157](../../../tests/test_topics_feature.py#L1157), [1158](../../../tests/test_topics_feature.py#L1158), [1161](../../../tests/test_topics_feature.py#L1161), [1162](../../../tests/test_topics_feature.py#L1162), [1163](../../../tests/test_topics_feature.py#L1163).

**Suiteweite Gegenprüfung:** Topichelper ruft verify_user_token weiterhin ohne check_revoked=True auf; Abweichung zum zentralen Adminhelper bleibt bestehen.

**Suchspur:** 263 versionierte Test-/Hilfsdateien durchsucht, 38 passende Zeilen. Regexe: ` _require_admin|check_revoked|TierStatusUnavailable `, ` /api/admin/topics `. Vollständige Treffer mit Pfad/Zeile in [search-evidence.json](search-evidence.json) unter ` G-041 `.

| Szenario | Erwartung |
|---|---|
| Given | Gültiger Admin, Nichtadmin, widerrufenes/ungültiges Token und Rollendienst-Ausfall; leere Write-/Read-/Paidcall-Zähler. |
| When | Alle Topic-Adminmethoden mit echter Adminpolicy aufrufen, nur externes SDK kontrollieren; zentrale Adminroute als Vergleich. |
| Then | Revocation=True wird angefordert; invalid/revoked 401, Nichtadmin 403, Rollenausfall 503 vor Service/Write. Gemeinsame Policy verwenden oder deren Gleichheit explizit sichern, erlaubten Rollencache nicht als Frischegarantie darstellen. |

**Zielstellen:** [tests/test_topics_feature.py](../../../tests/test_topics_feature.py), [tests/test_auth_revocation.py](../../../tests/test_auth_revocation.py)

**Wiederverwenden:** [tests/test_topics_feature.py](../../../tests/test_topics_feature.py), [tests/test_auth_revocation.py](../../../tests/test_auth_revocation.py)

**Validierung nach Implementierung:** ` python -m pytest tests/test_topics_feature.py tests/test_auth_revocation.py -q `

**Gezielte Negativkontrolle:** check_revoked=True entfernen oder TierStatusUnavailable-Abbildung weglassen: neue echte Topicgrenztests müssen scheitern.


<a id="g-042"></a>

## G-042 · Benchmark zählt HTTP-200-Providerfehler als erfolgreiche Enthaltung

**P1 · observed_behavior_defect** · Verträge: [BENCH-02](matrix.md#bench-02), [BENCH-03](matrix.md#bench-03) · Paket: [WP-34](work-packages.md#wp-34)

**Aktuelle Bewertung:** open — Budgetkorrekturen ändern nicht die HTTP-200-Protokollfehlerklassifikation; diesen Befund weiterhin gesondert prüfen.

**Produktbeleg:** [benchmark/transport.py](../../../benchmark/transport.py#L133) — ` def execute( `; [benchmark/runner.py](../../../benchmark/runner.py#L69) — ` def index_existing( `; [benchmark/runner.py](../../../benchmark/runner.py#L502) — ` def _make_cell_record( `

**Vorhandene relevante Prüfungen:**

- [test_malformed_response_is_structured](../../../tests/test_benchmark_transport.py#L111) — Transportfunktionen mit injiziertem POST. Assertionstellen: [114](../../../tests/test_benchmark_transport.py#L114), [115](../../../tests/test_benchmark_transport.py#L115), [116](../../../tests/test_benchmark_transport.py#L116).

**Suiteweite Gegenprüfung:** Budgetkorrekturen ändern nicht die HTTP-200-Protokollfehlerklassifikation; diesen Befund weiterhin gesondert prüfen.

**Suchspur:** 263 versionierte Test-/Hilfsdateien durchsucht, 25 passende Zeilen. Regexe: ` malformed_response|provider_http_error|response_parse_failed `, ` index_existing|retry_failed|abstain `. Vollständige Treffer mit Pfad/Zeile in [search-evidence.json](search-evidence.json) unter ` G-042 `.

| Szenario | Erwartung |
|---|---|
| Given | HTTP-200-Body mit provider error, leere/ungültige choices und gültige Textantwort ohne extrahierbaren FINAL_ANSWER; echte erfolgreiche Auswahl als Kontrolle. |
| When | Transport→Cellrecord→Resume/Retry und Resultstatistik durchlaufen. |
| Then | Provider-/Protokollfehler bleiben Fehler mit sicherem Code statt Enthaltung; sie werden nicht als Erfolg dedupliziert. Explizites retry_failed folgt der vorhandenen Policy. Gültiger Antworttext ohne auswertbaren Buchstaben bleibt Enthaltung. Keine Rohcredentials/privaten Providertexte persistieren; Counts/Kostenbehauptungen aus vorliegenden Feldern ableiten. |

**Zielstellen:** [tests/test_benchmark_transport.py](../../../tests/test_benchmark_transport.py), [tests/test_benchmark_runner.py](../../../tests/test_benchmark_runner.py), [tests/test_benchmark_results.py](../../../tests/test_benchmark_results.py)

**Wiederverwenden:** [tests/test_benchmark_transport.py](../../../tests/test_benchmark_transport.py), [tests/test_benchmark_runner.py](../../../tests/test_benchmark_runner.py)

**Validierung nach Implementierung:** ` python -m pytest tests/test_benchmark_transport.py tests/test_benchmark_runner.py tests/test_benchmark_results.py -q `

**Gezielte Negativkontrolle:** Bodyerror-Prüfung entfernen: HTTP-200-Fehler darf die kombinierte error-/abstain-/Resumeassertion nicht bestehen. Kontrolle mit gültigem Text ohne Buchstaben verhindert fälschliches Umdeuten jeder Enthaltung in einen Fehler.


<a id="g-043"></a>

## G-043 · Google-Aktionsclaims mit nativen Transaktionen prüfen

**P1 · missing_integration** · Verträge: [GOOGLE-02](matrix.md#google-02) · Paket: [WP-35](work-packages.md#wp-35)

**Aktuelle Bewertung:** open — Fake-Parallelität ist belegt; neue Aktionsclaims fehlen im bestehenden Transaktionsharness.

**Produktbeleg:** [app/services/agent_actions.py](../../../app/services/agent_actions.py#L142) — ` def confirm( `

**Vorhandene relevante Prüfungen:**

- [test_prepare_does_not_write_and_confirmation_is_exact_once](../../../tests/test_agent_calendar.py#L42) — Kalender-Service und HTTP-Adapter mit Fake-DB und Google-Transport. Assertionstellen: [45](../../../tests/test_agent_calendar.py#L45), [46](../../../tests/test_agent_calendar.py#L46), [48](../../../tests/test_agent_calendar.py#L48), [49](../../../tests/test_agent_calendar.py#L49), [51](../../../tests/test_agent_calendar.py#L51), [55](../../../tests/test_agent_calendar.py#L55), [56](../../../tests/test_agent_calendar.py#L56), [57](../../../tests/test_agent_calendar.py#L57), [58](../../../tests/test_agent_calendar.py#L58), [59](../../../tests/test_agent_calendar.py#L59).
- [test_separate_oauth_read_and_send_scopes_and_local_draft_before_send](../../../tests/test_agent_gmail.py#L50) — Gmail-/Aktionsdienste und echter Agentloop mit Transport-/DB-Doubles. Assertionstellen: [54](../../../tests/test_agent_gmail.py#L54), [55](../../../tests/test_agent_gmail.py#L55), [58](../../../tests/test_agent_gmail.py#L58), [59](../../../tests/test_agent_gmail.py#L59), [60](../../../tests/test_agent_gmail.py#L60), [61](../../../tests/test_agent_gmail.py#L61).

**Suiteweite Gegenprüfung:** Fake-Parallelität ist belegt; neue Aktionsclaims fehlen im bestehenden Transaktionsharness.

**Suchspur:** 263 versionierte Test-/Hilfsdateien durchsucht, 220 passende Zeilen. Regexe: ` confirm|reconcile|expected_hash|agent_actions `. Vollständige Treffer mit Pfad/Zeile in [search-evidence.json](search-evidence.json) unter ` G-043 `.

| Szenario | Erwartung |
|---|---|
| Given | Zwei Prozesse bestätigen denselben sichtbaren Aktionshash. |
| When | Bestätigen, Leaseablauf und unklaren Transportausgang im lokalen Emulator steuern. |
| Then | Höchstens ein Writeversuch pro gültiger Aktion; unknown bleibt gegen Wiederholung gesperrt, fremder Owner/alte Revision schreibt nichts. |

**Zielstellen:** [tests/test_agent_calendar.py](../../../tests/test_agent_calendar.py), [tests/test_agent_gmail.py](../../../tests/test_agent_gmail.py)

**Wiederverwenden:** [tests/test_agent_calendar.py](../../../tests/test_agent_calendar.py), [tests/test_agent_gmail.py](../../../tests/test_agent_gmail.py)

**Validierung nach Implementierung:** ` Gezielte Dateien, dann kombinierter Lauf; native Transaktionen nur mit demo-consensio-e2e. `

**Gezielte Negativkontrolle:** Entscheidenden Guard oder Fehlerpfad kontrolliert ausschalten: der neue Test muss gezielt scheitern.


<a id="g-044"></a>

## G-044 · Cloud-Dateiablage und verteilte Löschkaskade integrieren

**P2 · missing_integration** · Verträge: [AGENT-06](matrix.md#agent-06) · Paket: [WP-36](work-packages.md#wp-36)

**Aktuelle Bewertung:** open — Lokale Objektablage/Parser sind geprüft; daraus folgt kein produktiver Bucket-/IAM- oder verteilter Kaskadennachweis.

**Produktbeleg:** [app/services/agent_files.py](../../../app/services/agent_files.py#L136) — ` class AgentFiles `

**Vorhandene relevante Prüfungen:**

- [test_real_extraction_storage_download_and_owner_isolation](../../../tests/test_agent_files.py#L28) — Datei-Service, echte Extraktion und isolierte HTTP-Adapter. Assertionstellen: [32](../../../tests/test_agent_files.py#L32), [33](../../../tests/test_agent_files.py#L33), [34](../../../tests/test_agent_files.py#L34), [35](../../../tests/test_agent_files.py#L35), [38](../../../tests/test_agent_files.py#L38), [39](../../../tests/test_agent_files.py#L39).
- [test_real_docx_pdf_version_and_saved_provenance](../../../tests/test_agent_documents.py#L24) — Dokument-Service mit echten DOCX-/PDF-Renderern und temporärem Speicher. Assertionstellen: [30](../../../tests/test_agent_documents.py#L30), [33](../../../tests/test_agent_documents.py#L33), [37](../../../tests/test_agent_documents.py#L37), [40](../../../tests/test_agent_documents.py#L40), [42](../../../tests/test_agent_documents.py#L42), [43](../../../tests/test_agent_documents.py#L43), [45](../../../tests/test_agent_documents.py#L45), [48](../../../tests/test_agent_documents.py#L48), [51](../../../tests/test_agent_documents.py#L51), [52](../../../tests/test_agent_documents.py#L52), [53](../../../tests/test_agent_documents.py#L53), [54](../../../tests/test_agent_documents.py#L54), [55](../../../tests/test_agent_documents.py#L55).

**Suiteweite Gegenprüfung:** Lokale Objektablage/Parser sind geprüft; daraus folgt kein produktiver Bucket-/IAM- oder verteilter Kaskadennachweis.

**Suchspur:** 263 versionierte Test-/Hilfsdateien durchsucht, 14 passende Zeilen. Regexe: ` AgentFiles|ObjectStorage|AGENT_FILES_BUCKET|storage.Client `. Vollständige Treffer mit Pfad/Zeile in [search-evidence.json](search-evidence.json) unter ` G-044 `.

| Szenario | Erwartung |
|---|---|
| Given | Private Datei/Dokumentversion und Löschjob mit fehlgeschlagenem Objektzugriff. |
| When | Cloudadapter mit kontrolliertem Storage-Double und native Metadaten-/Quotatransaktionen samt Wiederaufnahme ausführen. |
| Then | Keine öffentliche Freigabe, kein fremder Download und keine verwaisten Quoten/Versionen nach erfolgreichem Retry; Originalfehler bleibt sichtbar. |

**Zielstellen:** [tests/test_agent_files.py](../../../tests/test_agent_files.py), [tests/test_agent_documents.py](../../../tests/test_agent_documents.py)

**Wiederverwenden:** [tests/test_agent_files.py](../../../tests/test_agent_files.py), [tests/test_agent_documents.py](../../../tests/test_agent_documents.py)

**Validierung nach Implementierung:** ` Gezielte Dateien, dann kombinierter Lauf; native Transaktionen nur mit demo-consensio-e2e. `

**Gezielte Negativkontrolle:** Entscheidenden Guard oder Fehlerpfad kontrolliert ausschalten: der neue Test muss gezielt scheitern.


<a id="g-045"></a>

## G-045 · Outbox-/Probeclaims mit nativer SDK-Konkurrenz absichern

**P1 · missing_integration** · Verträge: [WATCH-07](matrix.md#watch-07) · Paket: [WP-37](work-packages.md#wp-37)

**Aktuelle Bewertung:** open — Fake-Claims und Versanddoubles belegen Logik, keine echten SDK-Retries. Externe Exactly-once-Zustellung ist ausdrücklich nicht versprochen.

**Produktbeleg:** [app/services/notification_outbox.py](../../../app/services/notification_outbox.py#L379) — ` def claim( `

**Vorhandene relevante Prüfungen:**

- [test_pause_then_stale_failure_keeps_watch_paused_and_counter_consistent](../../../tests/test_watch_review_regressions.py#L86) — Scheduler-/Outbox-/Deliverydienste mit Fake-DB und Versand-Doubles. Assertionstellen: [88](../../../tests/test_watch_review_regressions.py#L88), [90](../../../tests/test_watch_review_regressions.py#L90), [91](../../../tests/test_watch_review_regressions.py#L91), [93](../../../tests/test_watch_review_regressions.py#L93), [96](../../../tests/test_watch_review_regressions.py#L96), [97](../../../tests/test_watch_review_regressions.py#L97).
- [test_new_evidence_must_cite_a_source_the_standing_answer_did_not_have](../../../tests/test_watch_evidence_model.py#L31) — Evidence-/Probe-/Ledgerdienste mit Fake-DB. Assertionstellen: [36](../../../tests/test_watch_evidence_model.py#L36), [37](../../../tests/test_watch_evidence_model.py#L37), [45](../../../tests/test_watch_evidence_model.py#L45), [46](../../../tests/test_watch_evidence_model.py#L46).

**Suiteweite Gegenprüfung:** Fake-Claims und Versanddoubles belegen Logik, keine echten SDK-Retries. Externe Exactly-once-Zustellung ist ausdrücklich nicht versprochen.

**Suchspur:** 263 versionierte Test-/Hilfsdateien durchsucht, 41 passende Zeilen. Regexe: ` notification_outbox|watch_probe|lease_owner `. Vollständige Treffer mit Pfad/Zeile in [search-evidence.json](search-evidence.json) unter ` G-045 `.

| Szenario | Erwartung |
|---|---|
| Given | Zwei Worker, ein Ergebnis/Outboxitem und eine fällige Probe. |
| When | Nativen Emulatorcommit, Crash nach Commit, Leaseübernahme und spätes Ack kontrollieren. |
| Then | Resultat und Zustellabsicht atomar; alter Worker kann neuen Claim nicht bestätigen; Probe respektiert Tagesbudget und aktuelle Watchkonfiguration. |

**Zielstellen:** [tests/test_watch_review_regressions.py](../../../tests/test_watch_review_regressions.py), [tests/test_watch_evidence_model.py](../../../tests/test_watch_evidence_model.py)

**Wiederverwenden:** [tests/test_watch_review_regressions.py](../../../tests/test_watch_review_regressions.py), [tests/test_watch_evidence_model.py](../../../tests/test_watch_evidence_model.py)

**Validierung nach Implementierung:** ` Gezielte Dateien, dann kombinierter Lauf; native Transaktionen nur mit demo-consensio-e2e. `

**Gezielte Negativkontrolle:** Entscheidenden Guard oder Fehlerpfad kontrolliert ausschalten: der neue Test muss gezielt scheitern.


<a id="g-046"></a>

## G-046 · Aktuelle Testfehler und abweichenden Benchmark-Wiederholungslauf klären

**P2 · broken_test** · Verträge: [BUILD-02](matrix.md#build-02) · Paket: [WP-38](work-packages.md#wp-38)

**Aktuelle Bewertung:** open — Benchmark-Resume scheitert im Primärlauf und besteht isoliert. Publisher-Ergebnisprüfung scheitert in beiden Läufen trotz Subprozessreturncode 0. Browserergebnisse werden im Laufbericht ergänzt.

**Produktbeleg:** [tests/test_benchmark_budget.py](../../../tests/test_benchmark_budget.py#L73) — ` def test_resume_of_a_finished_pilot_does_not_pay_for_audits_again `

**Vorhandene relevante Prüfungen:**

- [BenchmarkBudgetTests::test_tight_budget_stops_before_the_first_uncovered_audit_call](../../../tests/test_benchmark_budget.py#L53) — Benchmarkrunner mit deterministischem Transport und temporären Artefakten. Assertionstellen: [60](../../../tests/test_benchmark_budget.py#L60), [65](../../../tests/test_benchmark_budget.py#L65), [66](../../../tests/test_benchmark_budget.py#L66), [67](../../../tests/test_benchmark_budget.py#L67), [68](../../../tests/test_benchmark_budget.py#L68), [69](../../../tests/test_benchmark_budget.py#L69), [70](../../../tests/test_benchmark_budget.py#L70), [71](../../../tests/test_benchmark_budget.py#L71).
- [PublisherStandaloneTests::test_cli_reaches_configuration_validation_without_packages](../../../tests/test_publisher_standalone.py#L29) — Echte Python-Subprozesse ohne Site-Packages mit HTTP-Doubles. Assertionstellen: [38](../../../tests/test_publisher_standalone.py#L38), [39](../../../tests/test_publisher_standalone.py#L39), [40](../../../tests/test_publisher_standalone.py#L40).

**Suiteweite Gegenprüfung:** Benchmark-Resume scheitert im Primärlauf und besteht isoliert. Publisher-Ergebnisprüfung scheitert in beiden Läufen trotz Subprozessreturncode 0. Browserergebnisse werden im Laufbericht ergänzt.

**Suchspur:** 263 versionierte Test-/Hilfsdateien durchsucht, 2 passende Zeilen. Regexe: ` consensus_prompt_template|test_scheduled_flow_without_packages|test_resume_of_a_finished_pilot `. Vollständige Treffer mit Pfad/Zeile in [search-evidence.json](search-evidence.json) unter ` G-046 `.

| Szenario | Erwartung |
|---|---|
| Given | Gesamtlauf unter Windows und isolierter Wiederholungslauf. |
| When | Prompt-/Mockzustand sowie Publisher-Subprozessresultat kontrolliert reproduzieren; aktuelle Browserfehler laut Laufbericht zuordnen. |
| Then | Gleiche fachliche Assertions bestehen isoliert und gemeinsam; keine Tests abschwächen oder Fehler nachträglich aus dem Primärlauf entfernen. |

**Zielstellen:** [tests/test_benchmark_budget.py](../../../tests/test_benchmark_budget.py), [tests/test_publisher_standalone.py](../../../tests/test_publisher_standalone.py)

**Wiederverwenden:** [tests/test_benchmark_budget.py](../../../tests/test_benchmark_budget.py), [tests/test_publisher_standalone.py](../../../tests/test_publisher_standalone.py)

**Validierung nach Implementierung:** ` Gezielte Dateien, dann kombinierter Lauf; native Transaktionen nur mit demo-consensio-e2e. `

**Gezielte Negativkontrolle:** Entscheidenden Guard oder Fehlerpfad kontrolliert ausschalten: der neue Test muss gezielt scheitern.

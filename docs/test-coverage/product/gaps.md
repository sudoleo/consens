# Verifizierte Befunde und ergänzende Tests

[Einstieg](README.md) · [Arbeitspakete](work-packages.md) · [Suchbelege](search-evidence.json)

46 Befunde im Verlauf, Stand 2026-10-02. Der aktuelle Status steht an jedem Befund: resolved = konkret behobener Befund, partially_addressed = Teilnachweis ergänzt, open = Restgrenze offen. Die ursprünglichen Mutations-/DOM-/Pythonproben vom 26.09.2026 bleiben historische Belege; sie werden nicht als aktuelle Messung ausgegeben. Der [Aktualisierungsbericht](current-review.md) trennt behobene Fehler, neue Teilbelege und erneut beobachtete Probleme.

P1/P2/P3 ordnen die Umsetzung nach möglichen Folgen und Voraussetzungen; sie sind keine Incident-Schweregrade. Suchtreffer allein beweisen weder Vorhandensein noch Abwesenheit eines Tests. Die Schlussfolgerung verbindet Suche, Testkörper, Mockgrenzen und gegebenenfalls Branchlauf/Probe. Suggested paths sind Vorschläge, vorhandene passende Dateien bevorzugen.

| ID | Priorität / Art | Befund | Status | Paket |
|---|---|---|---|---|
| [G-001](#g-001) | P1 / ` missing_integration ` | Deny-all-Regeln mit Clientidentitäten prüfen | resolved | [WP-06](work-packages.md#wp-06) |
| [G-002](#g-002) | P1 / ` missing_integration ` | Reguläre Usage mit echten Firestore-Transaktionen absichern | resolved | [WP-07](work-packages.md#wp-07) |
| [G-003](#g-003) | P1 / ` missing_integration ` | Chat-Löschen gegen Turn/Completion im Emulator | resolved | [WP-08](work-packages.md#wp-08) |
| [G-004](#g-004) | P1 / ` missing_integration ` | Vollständige Kontokaskade und API-Cleanup prüfen | resolved | [WP-09](work-packages.md#wp-09) |
| [G-005](#g-005) | P1 / ` missing_case ` | API-Neustart-Recovery und Retention tatsächlich ausführen | resolved | [WP-11](work-packages.md#wp-11) |
| [G-006](#g-006) | P1 / ` missing_integration ` | Source-Queue-Leases und Result-Commits im Emulator | resolved | [WP-14](work-packages.md#wp-14) |
| [G-007](#g-007) | P1 / ` assertion_gap ` | Undo-Konflikt, Ablauf, Wiederholung und HTTP-Fehlergrenze | resolved | [WP-10](work-packages.md#wp-10) |
| [G-008](#g-008) | P1 / ` missing_case ` | Memory-Patch gegen konkurrierenden Save und Kontolöschung | resolved | [WP-10](work-packages.md#wp-10) |
| [G-009](#g-009) | P2 / ` missing_case ` | Konkurrierende Registrierung ohne Auskunfts-/Benachrichtigungsleck | resolved | [WP-12](work-packages.md#wp-12) |
| [G-010](#g-010) | P1 / ` missing_case ` | Historischer API-v1-Source-Check-Adapter | resolved | [WP-11](work-packages.md#wp-11) |
| [G-011](#g-011) | P1 / ` missing_case ` | App-POST-/api/share durch den echten Router prüfen | resolved | [WP-13](work-packages.md#wp-13) |
| [G-012](#g-012) | P1 / ` missing_case ` | user_status-Adapter einschließlich Free-Admin und Ausfällen | resolved | [WP-12](work-packages.md#wp-12) |
| [G-013](#g-013) | P2 / ` missing_case ` | Sieben Watch-/Telegram-/Unsubscribe-HTTP-Adapter | resolved | [WP-15](work-packages.md#wp-15) |
| [G-014](#g-014) | P1 / ` missing_case ` | Topic-PUT/List sowie öffentliche Hub-/Sitemap-/Follow-Adapter | resolved | [WP-16](work-packages.md#wp-16) |
| [G-015](#g-015) | P2 / ` missing_case ` | Admin-Benchmark-Routen und Reportviewer | resolved | [WP-22](work-packages.md#wp-22) |
| [G-016](#g-016) | P2 / ` missing_case ` | Claim-Identity-Judge selbst prüfen | resolved | [WP-17](work-packages.md#wp-17) |
| [G-017](#g-017) | P2 / ` missing_case ` | SEO-Readadapter hinter den Service-Fakes | resolved | [WP-18](work-packages.md#wp-18) |
| [G-018](#g-018) | P1 / ` observed_behavior_defect ` | Topic-Notizen werden erneut als HTML interpretiert | resolved | [WP-20](work-packages.md#wp-20) |
| [G-019](#g-019) | P2 / ` observed_behavior_defect ` | Strukturierte Adminfehler verlieren ihre Nachricht | resolved | [WP-21](work-packages.md#wp-21) |
| [G-020](#g-020) | P2 / ` assertion_gap ` | OG-Test akzeptiert leeres Bild | resolved | [WP-23](work-packages.md#wp-23) |
| [G-021](#g-021) | P2 / ` assertion_gap ` | Analytics-Opt-out ausführen statt Strings suchen | resolved | [WP-24](work-packages.md#wp-24) |
| [G-022](#g-022) | P1 / ` missing_case ` | Account-Reparaturskript ohne Produktionszugriff prüfen | resolved | [WP-25](work-packages.md#wp-25) |
| [G-023](#g-023) | P2 / ` missing_case ` | Claim-Key-Backfill-Dry-run, Idempotenz und Datenerhalt | resolved | [WP-25](work-packages.md#wp-25) |
| [G-024](#g-024) | P1 / ` missing_automation ` | Allgemeine Suite in CI absichern | resolved | [WP-05](work-packages.md#wp-05) |
| [G-025](#g-025) | P1 / ` execution_gap ` | Aktuelle Browserfälle ausführen und rote Fälle klären | resolved | [WP-03](work-packages.md#wp-03) |
| [G-026](#g-026) | P2 / ` execution_gap ` | Windows-Einstieg tatsächlich validieren | resolved | [WP-04](work-packages.md#wp-04) |
| [G-027](#g-027) | P1 / ` broken_test ` | Zwei veraltete Emulatorfixtures reparieren | resolved | [WP-01](work-packages.md#wp-01) |
| [G-028](#g-028) | P2 / ` broken_test ` | Veralteten Footer-Stringvertrag korrigieren | resolved | [WP-01](work-packages.md#wp-01) |
| [G-029](#g-029) | P1 / ` unstable_test ` | Report-Race-Instabilität isolieren | resolved | [WP-02](work-packages.md#wp-02) |
| [G-030](#g-030) | P1 / ` missing_integration ` | Wenige vollständige Browser→Backend→Persistenz-Flows | resolved | [WP-29](work-packages.md#wp-29) |
| [G-031](#g-031) | P2 / ` missing_integration ` | Due-Queries und Scheduler-Claims mit SDK-Formen | resolved | [WP-19](work-packages.md#wp-19) |
| [G-032](#g-032) | P2 / ` missing_integration ` | Lokale echte Transportgrenzen statt ausschließlich MockTransport | resolved | [WP-26](work-packages.md#wp-26) |
| [G-033](#g-033) | P2 / ` missing_case ` | Ungültige Body-Header und Konfigurationsgrenzen | resolved | [WP-26](work-packages.md#wp-26) |
| [G-034](#g-034) | P2 / ` missing_case ` | Feedback-Adapter und Statistik-Persistenzwrapper | resolved | [WP-27](work-packages.md#wp-27) |
| [G-035](#g-035) | P3 / ` missing_case ` | Weitere ausführbare CLI-Einstiege | resolved | [WP-28](work-packages.md#wp-28) |
| [G-036](#g-036) | P2 / ` missing_case ` | Vendorhelper mit Version- und Check-only-Grenzen ausführen | resolved | [WP-30](work-packages.md#wp-30) |
| [G-037](#g-037) | P1 / ` observed_behavior_defect ` | main verwirft HTTPException-Header einschließlich Retry-After | resolved | [WP-31](work-packages.md#wp-31) |
| [G-038](#g-038) | P1 / ` observed_behavior_defect ` | Undo kürzt früheren Inhalt nach Absenkung des Memorylimits | resolved | [WP-10](work-packages.md#wp-10) |
| [G-039](#g-039) | P1 / ` missing_case ` | Erfolgreicher Agentdetail- und Stop-HTTP-Pfad fehlen | resolved | [WP-32](work-packages.md#wp-32) |
| [G-040](#g-040) | P1 / ` observed_behavior_defect ` | Modellrollback überschreibt einen zwischenzeitlichen Writer | resolved | [WP-33](work-packages.md#wp-33) |
| [G-041](#g-041) | P1 / ` observed_behavior_defect ` | Topic-Admingrenze prüft Revocation nicht und verliert Rollen-503 | resolved | [WP-16](work-packages.md#wp-16) |
| [G-042](#g-042) | P1 / ` observed_behavior_defect ` | Benchmark zählt HTTP-200-Providerfehler als erfolgreiche Enthaltung | resolved | [WP-34](work-packages.md#wp-34) |
| [G-043](#g-043) | P1 / ` missing_integration ` | Google-Aktionsclaims mit nativen Transaktionen prüfen | resolved | [WP-35](work-packages.md#wp-35) |
| [G-044](#g-044) | P2 / ` missing_integration ` | Cloud-Dateiablage und verteilte Löschkaskade integrieren | resolved | [WP-36](work-packages.md#wp-36) |
| [G-045](#g-045) | P1 / ` missing_integration ` | Outbox-/Probeclaims mit nativer SDK-Konkurrenz absichern | resolved | [WP-37](work-packages.md#wp-37) |
| [G-046](#g-046) | P2 / ` broken_test ` | Aktuelle Testfehler und abweichenden Benchmark-Wiederholungslauf klären | resolved | [WP-38](work-packages.md#wp-38) |

<a id="g-001"></a>

## G-001 · Deny-all-Regeln mit Clientidentitäten prüfen

**P1 · missing_integration** · Verträge: [AUTH-05](matrix.md#auth-05) · Paket: [WP-06](work-packages.md#wp-06)

**Aktuelle Bewertung:** resolved — 49 echte Clientfälle: zwölf tatsächliche private Servicepfade mit vier Identitäten und Denial-Negativkontrolle. Emulator, keine produktive Rules-/IAMfreigabe.

**Produktbeleg:** [firestore.rules](../../../firestore.rules#L31) — ` allow read, write: if false; `; [tests/e2e/test_agent_transactions.py](../../../tests/e2e/test_agent_transactions.py#L24) — ` db = firestore.Client `

**Vorhandene relevante Prüfungen:**

- [`${identity}: no client read/write/query/delete of ${path.replace(owner, '{uid}').split('/').slice(0, -1).join('/')}`](../../../tests/rules/firestore.rules.test.mjs#L49) — Echte Firebase-Clientoperationen gegen Firestore-Emulator. Assertionstellen: [54](../../../tests/rules/firestore.rules.test.mjs#L54), [55](../../../tests/rules/firestore.rules.test.mjs#L55), [56](../../../tests/rules/firestore.rules.test.mjs#L56), [57](../../../tests/rules/firestore.rules.test.mjs#L57), [58](../../../tests/rules/firestore.rules.test.mjs#L58).

**Suiteweite Gegenprüfung:** 49 echte Clientfälle: zwölf tatsächliche private Servicepfade mit vier Identitäten und Denial-Negativkontrolle. Emulator, keine produktive Rules-/IAMfreigabe.

**Suchspur:** 304 versionierte Test-/Hilfsdateien durchsucht, 16 passende Zeilen. Regexe: ` firestore\.rules `, ` assertFails|assertSucceeds|initializeTestEnvironment|rules-unit-testing `. Vollständige Treffer mit Pfad/Zeile in [search-evidence.json](search-evidence.json) unter ` G-001 `.

| Szenario | Erwartung |
|---|---|
| Given | Geladene Repo-Regeln und getrennte anonyme, Owner- und fremde Clientidentität; Daten ausschließlich über Admin-Testsetup angelegt. |
| When | Jede Identität liest/schreibt users/{uid}, role/tier und repräsentative Untercollections über den regelgeprüften Client. |
| Then | Alle Clientoperationen scheitern; Admin-Testsetup bleibt funktionsfähig. Eine allow-true-Mutation muss scheitern. |

**Zielstellen:** [tests/rules/firestore.rules.test.mjs](../../../tests/rules/firestore.rules.test.mjs)

**Wiederverwenden:** [firebase.json](../../../firebase.json), [tests/e2e/README.md](../../../tests/e2e/README.md)

**Validierung nach Implementierung:** ` Separaten Rules-Runner mit dem lokalen Demo-Emulator einrichten; nicht den bestehenden Vitest-Glob oder Admin-SDK als Rules-Test verwenden. `

**Gezielte Negativkontrolle:** Temporär nur im Test-Ruletext write für users/{uid} erlauben; Owner-Schreibtest muss rot werden.


<a id="g-002"></a>

## G-002 · Reguläre Usage mit echten Firestore-Transaktionen absichern

**P1 · missing_integration** · Verträge: [QUOTA-01](matrix.md#quota-01) · Paket: [WP-07](work-packages.md#wp-07)

**Aktuelle Bewertung:** resolved — Admission, letzter Betrag, Buchung, Release/Consume, UTC-Tage und Kontrollowner nativ belegt. Lokaler Emulator mit anonymen Credentials; kein Produktkonto, keine produktive IAM-/Lastgarantie. Nur eigene Dokumentwurzeln werden aufgeräumt.

**Produktbeleg:** [app/services/usage_repository.py](../../../app/services/usage_repository.py#L752) — ` def _transaction( `

**Vorhandene relevante Prüfungen:**

- [test_same_operation_race_has_exactly_one_authorization](../../../tests/test_usage_authorization.py#L78) — Atomare Autorisierungslogik mit FakeFirestore und Threads. Assertionstellen: [82](../../../tests/test_usage_authorization.py#L82), [83](../../../tests/test_usage_authorization.py#L83), [86](../../../tests/test_usage_authorization.py#L86), [87](../../../tests/test_usage_authorization.py#L87).
- [test_run_quotas_are_gone_from_the_limits_config](../../../tests/test_run_usage_repository.py#L55) — Repository-/Transaktionsverträge mit FakeFirestore und Threads. Assertionstellen: [58](../../../tests/test_run_usage_repository.py#L58), [59](../../../tests/test_run_usage_repository.py#L59), [60](../../../tests/test_run_usage_repository.py#L60), [62](../../../tests/test_run_usage_repository.py#L62).
- [test_native_identical_key_and_booking_are_exactly_once](../../../tests/e2e/test_usage_transactions.py#L26) — Echte Firestore-SDK-Transaktionen gegen isolierten Demo-Emulator. Assertionstellen: [32](../../../tests/e2e/test_usage_transactions.py#L32), [39](../../../tests/e2e/test_usage_transactions.py#L39), [40](../../../tests/e2e/test_usage_transactions.py#L40).

**Suiteweite Gegenprüfung:** Admission, letzter Betrag, Buchung, Release/Consume, UTC-Tage und Kontrollowner nativ belegt. Lokaler Emulator mit anonymen Credentials; kein Produktkonto, keine produktive IAM-/Lastgarantie. Nur eigene Dokumentwurzeln werden aufgeräumt.

**Suchspur:** 304 versionierte Test-/Hilfsdateien durchsucht, 82 passende Zeilen. Regexe: ` usage_repository|FirestoreUsageRepository `, ` daily_token_admission|authorize_operation|parallel_unique_reservations `. Vollständige Treffer mit Pfad/Zeile in [search-evidence.json](search-evidence.json) unter ` G-002 `.

| Szenario | Erwartung |
|---|---|
| Given | Mehrere Repositoryinstanzen, gleicher UID/UTC-Tag, letzter freier Slot; zusätzlich zweiter Owner. |
| When | Gleiche Operation und verschiedene Run-Keys konkurrieren; Release/Consume/UTC-Wechsel werden kontrolliert verschachtelt. |
| Then | Ein Claimgewinner je Operation, keine Überbuchung, genau ein regulärer Charge, separate Deep-Zähler und unveränderte fremde Daten. Endzustand direkt aus Firestore lesen. |

**Zielstellen:** [tests/e2e/test_usage_transactions.py](../../../tests/e2e/test_usage_transactions.py)

**Wiederverwenden:** [tests/usage_test_support.py](../../../tests/usage_test_support.py), [tests/e2e/test_agent_transactions.py](../../../tests/e2e/test_agent_transactions.py), [app/core/e2e_profile.py](../../../app/core/e2e_profile.py)

**Validierung nach Implementierung:** ` RUN_E2E=1 python -m pytest tests/e2e/test_usage_transactions.py -q (mit sicherem Demo-Emulatorprofil) `

**Gezielte Negativkontrolle:** Claim oder Tagescounter außerhalb der Transaktion verschieben; barrier-gesteuertes Rennen muss dies entdecken.


<a id="g-003"></a>

## G-003 · Chat-Löschen gegen Turn/Completion im Emulator

**P1 · missing_integration** · Verträge: [CHAT-01](matrix.md#chat-01), [CHAT-02](matrix.md#chat-02) · Paket: [WP-08](work-packages.md#wp-08)

**Aktuelle Bewertung:** resolved — Echter Deleteprozess pausiert nach Tombstonecommit vor Purge; Completion/Create/Failure verändern weder vorhandene Nachfahren noch Löschjob. Beide finalen Commitreihenfolgen, Contextfence und vollständige Kaskade bleiben belegt. Lokaler Emulator mit anonymen Credentials; kein Produktkonto, keine produktive IAM-/Lastgarantie. Nur eigene Dokumentwurzeln werden aufgeräumt.

**Produktbeleg:** [app/services/chat_store.py](../../../app/services/chat_store.py#L1270) — ` def delete_chat( `; [app/services/chat_store.py](../../../app/services/chat_store.py#L891) — ` def complete_turn( `

**Vorhandene relevante Prüfungen:**

- [test_deleting_chat_state_rejects_late_completion_and_failure_writes](../../../tests/test_chat_history.py#L1491) — Router und ChatStore mit speicherbasiertem Transaktionsmodell. Assertionstellen: [1500](../../../tests/test_chat_history.py#L1500), [1504](../../../tests/test_chat_history.py#L1504), [1512](../../../tests/test_chat_history.py#L1512), [1513](../../../tests/test_chat_history.py#L1513).
- [test_two_workers_cannot_exceed_owner_chat_limit](../../../tests/e2e/test_phase2_transactions.py#L140) — Echte Firestore-SDK-Transaktionen gegen isolierten Demo-Emulator. Assertionstellen: [155](../../../tests/e2e/test_phase2_transactions.py#L155), [159](../../../tests/e2e/test_phase2_transactions.py#L159).
- [test_native_chat_completion_and_delete_never_resurrect_children](../../../tests/e2e/test_chat_lifecycle_transactions.py#L23) — Echte Firestore-SDK-Transaktionen gegen isolierten Demo-Emulator. Assertionstellen: [35](../../../tests/e2e/test_chat_lifecycle_transactions.py#L35), [41](../../../tests/e2e/test_chat_lifecycle_transactions.py#L41), [43](../../../tests/e2e/test_chat_lifecycle_transactions.py#L43), [46](../../../tests/e2e/test_chat_lifecycle_transactions.py#L46), [51](../../../tests/e2e/test_chat_lifecycle_transactions.py#L51), [53](../../../tests/e2e/test_chat_lifecycle_transactions.py#L53), [54](../../../tests/e2e/test_chat_lifecycle_transactions.py#L54).

**Suiteweite Gegenprüfung:** Echter Deleteprozess pausiert nach Tombstonecommit vor Purge; Completion/Create/Failure verändern weder vorhandene Nachfahren noch Löschjob. Beide finalen Commitreihenfolgen, Contextfence und vollständige Kaskade bleiben belegt. Lokaler Emulator mit anonymen Credentials; kein Produktkonto, keine produktive IAM-/Lastgarantie. Nur eigene Dokumentwurzeln werden aufgeräumt.

**Suchspur:** 304 versionierte Test-/Hilfsdateien durchsucht, 19 passende Zeilen. Regexe: ` delet.*complet|complet.*delet|deleting_chat|account_deletion_tombstone `, ` test_two_workers_cannot_exceed_owner_chat_limit `. Vollständige Treffer mit Pfad/Zeile in [search-evidence.json](search-evidence.json) unter ` G-003 `.

| Szenario | Erwartung |
|---|---|
| Given | Aktiver Chat mit pending Turn und separatem fremdem Owner. |
| When | Delete-Marker und Completion/Fail/Create-Turn konkurrieren mit kontrollierten Barrieren; beide zulässigen Commitreihenfolgen testen. |
| Then | Nach abgeschlossener Kaskade keine neuen Antwort-/Context-/Turn-Waisen; vor Delete vollständig committed Daten werden mitgelöscht; fremder Owner unverändert. |

**Zielstellen:** [tests/e2e/test_chat_lifecycle_transactions.py](../../../tests/e2e/test_chat_lifecycle_transactions.py)

**Wiederverwenden:** [tests/test_chat_history.py](../../../tests/test_chat_history.py), [tests/e2e/test_phase2_transactions.py](../../../tests/e2e/test_phase2_transactions.py)

**Validierung nach Implementierung:** ` RUN_E2E=1 python -m pytest tests/e2e/test_chat_lifecycle_transactions.py -q (Demo-Emulator) `

**Gezielte Negativkontrolle:** Den active/deleting-Read aus der Completion-Transaktion entfernen; Late-Write-Szenario muss rot werden.


<a id="g-004"></a>

## G-004 · Vollständige Kontokaskade und API-Cleanup prüfen

**P1 · missing_integration** · Verträge: [AUTH-03](matrix.md#auth-03) · Paket: [WP-09](work-packages.md#wp-09)

**Aktuelle Bewertung:** resolved — Alle16 aktuellen Bereiche mit expliziter Inventarassertion; Retry, fehlende Parentdokumente, verlorene Checkpoints, Kontrollowner und minimaler Tombstone belegt. Auth- und Cloudobjektgrenzen ersetzt; keine produktive Lösch-/IAMfreigabe.

**Produktbeleg:** [app/services/account_deletion.py](../../../app/services/account_deletion.py#L94) — ` areas = ( `; [app/services/api_account_cleanup.py](../../../app/services/api_account_cleanup.py#L85) — ` def cleanup_uid( `; [app/services/api_account_cleanup.py](../../../app/services/api_account_cleanup.py#L135) — ` def retry_pending( `

**Vorhandene relevante Prüfungen:**

- [test_failed_area_remains_pending_and_only_that_area_is_retried](../../../tests/test_account_deletion_retry.py#L69) — Service mit In-Memory-Datenbank. Assertionstellen: [163](../../../tests/test_account_deletion_retry.py#L163), [164](../../../tests/test_account_deletion_retry.py#L164), [165](../../../tests/test_account_deletion_retry.py#L165), [166](../../../tests/test_account_deletion_retry.py#L166), [167](../../../tests/test_account_deletion_retry.py#L167), [168](../../../tests/test_account_deletion_retry.py#L168), [169](../../../tests/test_account_deletion_retry.py#L169), [170](../../../tests/test_account_deletion_retry.py#L170), [172](../../../tests/test_account_deletion_retry.py#L172), [173](../../../tests/test_account_deletion_retry.py#L173), [174](../../../tests/test_account_deletion_retry.py#L174), [175](../../../tests/test_account_deletion_retry.py#L175), [176](../../../tests/test_account_deletion_retry.py#L176), [177](../../../tests/test_account_deletion_retry.py#L177), [179](../../../tests/test_account_deletion_retry.py#L179), [180](../../../tests/test_account_deletion_retry.py#L180), [181](../../../tests/test_account_deletion_retry.py#L181), [182](../../../tests/test_account_deletion_retry.py#L182).
- [test_delete_account_cascades_into_the_owner_chats](../../../tests/test_account_deletion_chats.py#L98) — API mit Service-Double. Assertionstellen: [102](../../../tests/test_account_deletion_chats.py#L102), [103](../../../tests/test_account_deletion_chats.py#L103), [104](../../../tests/test_account_deletion_chats.py#L104).
- [test_native_account_cascade_resumes_failed_objects_without_foreign_loss](../../../tests/e2e/test_account_deletion_transactions.py#L60) — Echte Firestore-SDK-Transaktionen gegen isolierten Demo-Emulator und echter Cloudadapter. Assertionstellen: [76](../../../tests/e2e/test_account_deletion_transactions.py#L76), [78](../../../tests/e2e/test_account_deletion_transactions.py#L78), [79](../../../tests/e2e/test_account_deletion_transactions.py#L79), [80](../../../tests/e2e/test_account_deletion_transactions.py#L80), [83](../../../tests/e2e/test_account_deletion_transactions.py#L83), [85](../../../tests/e2e/test_account_deletion_transactions.py#L85), [86](../../../tests/e2e/test_account_deletion_transactions.py#L86), [87](../../../tests/e2e/test_account_deletion_transactions.py#L87), [88](../../../tests/e2e/test_account_deletion_transactions.py#L88), [89](../../../tests/e2e/test_account_deletion_transactions.py#L89), [90](../../../tests/e2e/test_account_deletion_transactions.py#L90), [91](../../../tests/e2e/test_account_deletion_transactions.py#L91).

**Suiteweite Gegenprüfung:** Alle16 aktuellen Bereiche mit expliziter Inventarassertion; Retry, fehlende Parentdokumente, verlorene Checkpoints, Kontrollowner und minimaler Tombstone belegt. Auth- und Cloudobjektgrenzen ersetzt; keine produktive Lösch-/IAMfreigabe.

**Suchspur:** 304 versionierte Test-/Hilfsdateien durchsucht, 49 passende Zeilen. Regexe: ` FirestoreAccountDeletion|FirestoreApiAccountCleanup|cleanup_uid|retry_pending `, ` completed_areas|_delete_api_access `. Vollständige Treffer mit Pfad/Zeile in [search-evidence.json](search-evidence.json) unter ` G-004 `.

| Szenario | Erwartung |
|---|---|
| Given | Eigene Daten in allen 14 Kaskadenbereichen plus Kontrollowner; Firebase Auth/Mail/Telegram-Transport bleiben externe Doubles. |
| When | Löschung mit einem gezielten Bereichs-/Checkpointfehler, anschließend neuer Serviceprozess/Instanz und Retry; parallel bereits authentifizierter Write. |
| Then | Persistiert quittierte Bereiche werden übersprungen; Operationen ohne dauerhaften Checkpoint dürfen idempotent wiederholt werden, auch wenn ihr Seiteneffekt bereits erfolgte. Zieldaten aller 14 Bereiche sind entfernt, fremde Daten erhalten und pending bleibt bis zum belegten Abschluss bestehen. Der erforderliche minimale UID-Sperrtombstone bleibt bis zum Aufbewahrungsende erhalten, die Cleanup-E-Mail wird entfernt; späte Writes dürfen nicht neu befüllen. |

**Zielstellen:** [tests/test_api_account_cleanup.py](../../../tests/test_api_account_cleanup.py), [tests/e2e/test_account_deletion_transactions.py](../../../tests/e2e/test_account_deletion_transactions.py)

**Wiederverwenden:** [tests/test_account_deletion_retry.py](../../../tests/test_account_deletion_retry.py), [tests/test_chat_history.py](../../../tests/test_chat_history.py)

**Validierung nach Implementierung:** ` python -m pytest tests/test_api_account_cleanup.py tests/test_account_deletion_retry.py -q; anschließend neuer Emulator-Kaskadentest `

**Gezielte Negativkontrolle:** Eine Kaskadenoperation durch No-op ersetzen oder die Sperre vorzeitig löschen; Residualdaten-/Sperrassertion muss rot werden. Den ausdrücklich erforderlichen UID-Tombstone nicht als unerlaubtes Residualdatum zählen.


<a id="g-005"></a>

## G-005 · API-Neustart-Recovery und Retention tatsächlich ausführen

**P1 · missing_case** · Verträge: [API-02](matrix.md#api-02) · Paket: [WP-11](work-packages.md#wp-11)

**Aktuelle Bewertung:** resolved — Ausgeführte Recoveryaufträge, lebende/abgelaufene Leases, kein zweiter Providerstart/Verbrauch; historischer Sourceadapter bindet alle Identitäten/Versionen, Pagination und Pollrevision. Backfill liest Run und Mapping transaktional neu. Infrastruktur/Providergrenzen kontrolliert; keine produktive Restart-/Lastfreigabe.

**Produktbeleg:** [app/services/api_consensus_runner.py](../../../app/services/api_consensus_runner.py#L285) — ` def recover_persisted_runs( `; [app/services/api_consensus_runner.py](../../../app/services/api_consensus_runner.py#L255) — ` def cleanup_expired_runs( `; [app/services/api_run_repository.py](../../../app/services/api_run_repository.py#L307) — ` def backfill_retention( `

**Vorhandene relevante Prüfungen:**

- [test_runner_claim_prevents_duplicate_usage_and_provider_start](../../../tests/test_consensus_api.py#L493) — Main-App-API und Runner mit Repository-/LLM-/Scheduler-Doubles; einzelne Quelltextverträge. Assertionstellen: [542](../../../tests/test_consensus_api.py#L542), [543](../../../tests/test_consensus_api.py#L543), [544](../../../tests/test_consensus_api.py#L544).
- [test_expired_post_provider_worker_keeps_consumed_usage](../../../tests/test_consensus_api.py#L735) — Main-App-API und Runner mit Repository-/LLM-/Scheduler-Doubles; einzelne Quelltextverträge. Assertionstellen: [757](../../../tests/test_consensus_api.py#L757).
- [test_restart_requeues_only_pre_provider_work_and_deduplicates_schedule](../../../tests/test_api_run_recovery.py#L104) — Recoveryorchestrierung mit echten Run-/Quota-/Cleanup-Repositories. Assertionstellen: [118](../../../tests/test_api_run_recovery.py#L118), [119](../../../tests/test_api_run_recovery.py#L119), [122](../../../tests/test_api_run_recovery.py#L122), [123](../../../tests/test_api_run_recovery.py#L123), [124](../../../tests/test_api_run_recovery.py#L124), [125](../../../tests/test_api_run_recovery.py#L125), [126](../../../tests/test_api_run_recovery.py#L126), [130](../../../tests/test_api_run_recovery.py#L130), [133](../../../tests/test_api_run_recovery.py#L133), [136](../../../tests/test_api_run_recovery.py#L136), [141](../../../tests/test_api_run_recovery.py#L141), [145](../../../tests/test_api_run_recovery.py#L145).
- [test_historic_api_source_pages_owner_cursor_revision_and_cache](../../../tests/test_api_source_history.py#L43) — Registrierte main.app mit echten Middleware-, Auth-/Owner- und Serviceguards. Assertionstellen: [52](../../../tests/test_api_source_history.py#L52), [53](../../../tests/test_api_source_history.py#L53), [60](../../../tests/test_api_source_history.py#L60), [61](../../../tests/test_api_source_history.py#L61), [62](../../../tests/test_api_source_history.py#L62), [64](../../../tests/test_api_source_history.py#L64), [73](../../../tests/test_api_source_history.py#L73), [75](../../../tests/test_api_source_history.py#L75).
- [test_retention_backfill_is_atomic_and_does_not_renew_another_run](../../../tests/e2e/test_api_retention_transactions.py#L8) — Echte Firestore-SDK-Transaktionen gegen isolierten Demo-Emulator. Assertionstellen: [21](../../../tests/e2e/test_api_retention_transactions.py#L21), [22](../../../tests/e2e/test_api_retention_transactions.py#L22), [23](../../../tests/e2e/test_api_retention_transactions.py#L23), [27](../../../tests/e2e/test_api_retention_transactions.py#L27), [28](../../../tests/e2e/test_api_retention_transactions.py#L28).

**Suiteweite Gegenprüfung:** Ausgeführte Recoveryaufträge, lebende/abgelaufene Leases, kein zweiter Providerstart/Verbrauch; historischer Sourceadapter bindet alle Identitäten/Versionen, Pagination und Pollrevision. Backfill liest Run und Mapping transaktional neu. Infrastruktur/Providergrenzen kontrolliert; keine produktive Restart-/Lastfreigabe.

**Suchspur:** 304 versionierte Test-/Hilfsdateien durchsucht, 17 passende Zeilen. Regexe: ` recover_persisted_runs|cleanup_expired_runs|backfill_retention `, ` fail_expired_run|expired_post_provider|expired_pre_provider `. Vollständige Treffer mit Pfad/Zeile in [search-evidence.json](search-evidence.json) unter ` G-005 `.

| Szenario | Erwartung |
|---|---|
| Given | Persistierte accepted/reserved/running/terminal Runs, abgelaufene und frische Leases, alte Runs ohne expires_at. |
| When | Recovery zweimal und nach simuliertem Prozessneustart ausführen; Scan-/Reserve-/Schedulefehler pro Fall injizieren. |
| Then | Nur pre-provider Arbeit wird eingeplant; unklare laufende Arbeit niemals doppelt generiert; Reserven korrekt freigegeben/Verbrauch erhalten; Retention löscht Run und Mapping konsistent und erhält noch gültige Daten. |

**Zielstellen:** [tests/test_api_run_recovery.py](../../../tests/test_api_run_recovery.py), [tests/test_api_run_repository.py](../../../tests/test_api_run_repository.py)

**Wiederverwenden:** [tests/test_consensus_api.py](../../../tests/test_consensus_api.py), [tests/test_api_run_repository.py](../../../tests/test_api_run_repository.py), [tests/usage_test_support.py](../../../tests/usage_test_support.py)

**Validierung nach Implementierung:** ` python -m pytest tests/test_api_run_recovery.py tests/test_api_run_repository.py tests/test_consensus_api.py -q `

**Gezielte Negativkontrolle:** running in die Requeue-Menge aufnehmen; Provider-/Schedule-Zähler muss den Doppelstart erkennen.


<a id="g-006"></a>

## G-006 · Source-Queue-Leases und Result-Commits im Emulator

**P1 · missing_integration** · Verträge: [SRC-03](matrix.md#src-03) · Paket: [WP-14](work-packages.md#wp-14)

**Aktuelle Bewertung:** resolved — Native Claims/Takeover/Paketabschluss/Delete/Pagination/Revision plus tatsächlicher Own-Key-Workerpfad. Fremder Worker und Fremdowner bleiben gesperrt; nur gebundener Judge erhält flüchtigen Dummykey, kein Key in entpackter DB/Cache/Workerlogs, kein zweiter Providercall. Transiente SDK-Abbrüche werden explizit erfasst; externer Provider ist kein Testziel.

**Produktbeleg:** [app/services/source_check_repository.py](../../../app/services/source_check_repository.py#L358) — ` def claim( `; [app/services/source_check_repository.py](../../../app/services/source_check_repository.py#L406) — ` def finish_package( `

**Vorhandene relevante Prüfungen:**

- [test_expired_lease_reclaims_unfinished_package_and_rejects_stale_worker](../../../tests/test_source_check_repository.py#L214) — Repository mit lockbasiertem FakeDb und Threads. Assertionstellen: [219](../../../tests/test_source_check_repository.py#L219), [221](../../../tests/test_source_check_repository.py#L221), [222](../../../tests/test_source_check_repository.py#L222), [224](../../../tests/test_source_check_repository.py#L224), [225](../../../tests/test_source_check_repository.py#L225), [226](../../../tests/test_source_check_repository.py#L226), [227](../../../tests/test_source_check_repository.py#L227).
- [test_native_source_claim_takeover_and_exactly_once_package](../../../tests/e2e/test_source_check_transactions.py#L15) — Echte Firestore-SDK-Transaktionen gegen isolierten Demo-Emulator. Assertionstellen: [27](../../../tests/e2e/test_source_check_transactions.py#L27), [31](../../../tests/e2e/test_source_check_transactions.py#L31), [33](../../../tests/e2e/test_source_check_transactions.py#L33), [34](../../../tests/e2e/test_source_check_transactions.py#L34), [42](../../../tests/e2e/test_source_check_transactions.py#L42), [43](../../../tests/e2e/test_source_check_transactions.py#L43), [44](../../../tests/e2e/test_source_check_transactions.py#L44), [47](../../../tests/e2e/test_source_check_transactions.py#L47), [48](../../../tests/e2e/test_source_check_transactions.py#L48).

**Suiteweite Gegenprüfung:** Native Claims/Takeover/Paketabschluss/Delete/Pagination/Revision plus tatsächlicher Own-Key-Workerpfad. Fremder Worker und Fremdowner bleiben gesperrt; nur gebundener Judge erhält flüchtigen Dummykey, kein Key in entpackter DB/Cache/Workerlogs, kein zweiter Providercall. Transiente SDK-Abbrüche werden explizit erfasst; externer Provider ist kein Testziel.

**Suchspur:** 304 versionierte Test-/Hilfsdateien durchsucht, 97 passende Zeilen. Regexe: ` SourceCheckRepository|finish_package|lease_token `, ` transactional|run_transaction `. Vollständige Treffer mit Pfad/Zeile in [search-evidence.json](search-evidence.json) unter ` G-006 `.

| Szenario | Erwartung |
|---|---|
| Given | Ein Job mit zwei Paketen, zwei Workerinstanzen, eigene Key-Affinität und ownergebundener Snapshot. |
| When | Claim/Leaseablauf/Neubeanspruchung und verspäteten finish_package-Write kontrolliert verschachteln; parallel Owner-/Referenzlöschung. |
| Then | Nur aktueller Leaseholder committed, Pakete zählen einmal, keine wiederbelebten Jobs, Revision/Pagination konsistent; eigene Keys erscheinen in keinem Dokument. |

**Zielstellen:** [tests/e2e/test_source_check_transactions.py](../../../tests/e2e/test_source_check_transactions.py)

**Wiederverwenden:** [tests/test_source_check_repository.py](../../../tests/test_source_check_repository.py), [tests/test_source_check_jobs.py](../../../tests/test_source_check_jobs.py), [tests/e2e/test_prompt_config_transactions.py](../../../tests/e2e/test_prompt_config_transactions.py)

**Validierung nach Implementierung:** ` RUN_E2E=1 python -m pytest tests/e2e/test_source_check_transactions.py -q (Demo-Emulator) `

**Gezielte Negativkontrolle:** Leasevergleich beim Commit entfernen; verspätetes Ergebnis muss den Test scheitern lassen.


<a id="g-007"></a>

## G-007 · Undo-Konflikt, Ablauf, Wiederholung und HTTP-Fehlergrenze

**P1 · assertion_gap** · Verträge: [MEM-02](matrix.md#mem-02) · Paket: [WP-10](work-packages.md#wp-10)

**Aktuelle Bewertung:** resolved — Datenverlust bei Limitabsenkung behoben. Native Revision/Lease/Tombstone/Commitfehler und volle echte main-HTTP-Matrix mit Auth/Tier/Owner/Expiry/Konflikt/Repeat ohne Providerarbeit belegt. Synthetische Profile; keine Live-Modellqualität.

**Produktbeleg:** [app/services/memory_edit.py](../../../app/services/memory_edit.py#L710) — ` def undo( `; [app/services/memory_edit.py](../../../app/services/memory_edit.py#L744) — ` if current_revision != int(revision.get `; [app/api/routers/users.py](../../../app/api/routers/users.py#L320) — ` def _raise_memory_edit_error( `; [app/api/routers/users.py](../../../app/api/routers/users.py#L354) — ` def undo_user_memory( `

**Vorhandene relevante Prüfungen:**

- [test_replace_is_revision_checked_and_undo_restores_exact_content](../../../tests/test_memory_edit.py#L178) — Memory-Repository mit Transaktionsdouble. Assertionstellen: [189](../../../tests/test_memory_edit.py#L189), [204](../../../tests/test_memory_edit.py#L204), [208](../../../tests/test_memory_edit.py#L208), [209](../../../tests/test_memory_edit.py#L209), [220](../../../tests/test_memory_edit.py#L220), [221](../../../tests/test_memory_edit.py#L221), [222](../../../tests/test_memory_edit.py#L222), [223](../../../tests/test_memory_edit.py#L223).
- [test_native_patch_and_manual_save_have_one_revision_winner](../../../tests/e2e/test_memory_edit_transactions.py#L44) — Echte Firestore-SDK-Transaktionen gegen isolierten Demo-Emulator und echter main-HTTP-Adapter. Assertionstellen: [51](../../../tests/e2e/test_memory_edit_transactions.py#L51), [68](../../../tests/e2e/test_memory_edit_transactions.py#L68), [70](../../../tests/e2e/test_memory_edit_transactions.py#L70), [71](../../../tests/e2e/test_memory_edit_transactions.py#L71).
- [test_main_undo_errors_preserve_all_state_and_never_call_provider](../../../tests/test_memory_http_contract.py#L75) — Registrierte main.app mit echten Middleware-, Auth-/Owner- und Serviceguards. Assertionstellen: [109](../../../tests/test_memory_http_contract.py#L109), [110](../../../tests/test_memory_http_contract.py#L110), [112](../../../tests/test_memory_http_contract.py#L112), [113](../../../tests/test_memory_http_contract.py#L113), [114](../../../tests/test_memory_http_contract.py#L114), [115](../../../tests/test_memory_http_contract.py#L115), [116](../../../tests/test_memory_http_contract.py#L116).

**Suiteweite Gegenprüfung:** Datenverlust bei Limitabsenkung behoben. Native Revision/Lease/Tombstone/Commitfehler und volle echte main-HTTP-Matrix mit Auth/Tier/Owner/Expiry/Konflikt/Repeat ohne Providerarbeit belegt. Synthetische Profile; keine Live-Modellqualität.

**Suchspur:** 304 versionierte Test-/Hilfsdateien durchsucht, 22 passende Zeilen. Regexe: ` undo\(|undo_expired|revision_not_found|invalid_revision `, ` revision_conflict `. Vollständige Treffer mit Pfad/Zeile in [search-evidence.json](search-evidence.json) unter ` G-007 `.

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

**Aktuelle Bewertung:** resolved — Datenverlust bei Limitabsenkung behoben. Native Revision/Lease/Tombstone/Commitfehler und volle echte main-HTTP-Matrix mit Auth/Tier/Owner/Expiry/Konflikt/Repeat ohne Providerarbeit belegt. Synthetische Profile; keine Live-Modellqualität.

**Produktbeleg:** [app/services/memory_edit.py](../../../app/services/memory_edit.py#L621) — ` def apply_patch( `; [app/services/memory_edit.py](../../../app/services/memory_edit.py#L660) — ` if current_revision != int(request.get `

**Vorhandene relevante Prüfungen:**

- [test_replace_is_revision_checked_and_undo_restores_exact_content](../../../tests/test_memory_edit.py#L178) — Memory-Repository mit Transaktionsdouble. Assertionstellen: [189](../../../tests/test_memory_edit.py#L189), [204](../../../tests/test_memory_edit.py#L204), [208](../../../tests/test_memory_edit.py#L208), [209](../../../tests/test_memory_edit.py#L209), [220](../../../tests/test_memory_edit.py#L220), [221](../../../tests/test_memory_edit.py#L221), [222](../../../tests/test_memory_edit.py#L222), [223](../../../tests/test_memory_edit.py#L223).
- [test_native_patch_and_manual_save_have_one_revision_winner](../../../tests/e2e/test_memory_edit_transactions.py#L44) — Echte Firestore-SDK-Transaktionen gegen isolierten Demo-Emulator und echter main-HTTP-Adapter. Assertionstellen: [51](../../../tests/e2e/test_memory_edit_transactions.py#L51), [68](../../../tests/e2e/test_memory_edit_transactions.py#L68), [70](../../../tests/e2e/test_memory_edit_transactions.py#L70), [71](../../../tests/e2e/test_memory_edit_transactions.py#L71).
- [test_main_undo_errors_preserve_all_state_and_never_call_provider](../../../tests/test_memory_http_contract.py#L75) — Registrierte main.app mit echten Middleware-, Auth-/Owner- und Serviceguards. Assertionstellen: [109](../../../tests/test_memory_http_contract.py#L109), [110](../../../tests/test_memory_http_contract.py#L110), [112](../../../tests/test_memory_http_contract.py#L112), [113](../../../tests/test_memory_http_contract.py#L113), [114](../../../tests/test_memory_http_contract.py#L114), [115](../../../tests/test_memory_http_contract.py#L115), [116](../../../tests/test_memory_http_contract.py#L116).

**Suiteweite Gegenprüfung:** Datenverlust bei Limitabsenkung behoben. Native Revision/Lease/Tombstone/Commitfehler und volle echte main-HTTP-Matrix mit Auth/Tier/Owner/Expiry/Konflikt/Repeat ohne Providerarbeit belegt. Synthetische Profile; keine Live-Modellqualität.

**Suchspur:** 304 versionierte Test-/Hilfsdateien durchsucht, 14 passende Zeilen. Regexe: ` memory_edit.*ensure_account|ensure_account_write_allowed `, ` baseline_revision|revision_conflict `. Vollständige Treffer mit Pfad/Zeile in [search-evidence.json](search-evidence.json) unter ` G-008 `.

| Szenario | Erwartung |
|---|---|
| Given | Reservierter Edit, danach neuer manueller Save oder persistierter Account-Tombstone, anschließend verspätete Providerantwort. |
| When | apply_patch sowie reserve/undo mit realem Guard aufrufen; auch Commitfehler nach mehreren geplanten Writes injizieren. |
| Then | Kein Überschreiben neuerer Memory, keine Wiederanlage nach Löschung, keine partiellen Profile-/Request-/Revisionswrites. Bereits beanspruchte Kosten nicht still zurückerfinden. |

**Zielstellen:** [tests/test_memory_edit.py](../../../tests/test_memory_edit.py), [tests/e2e/test_memory_edit_transactions.py](../../../tests/e2e/test_memory_edit_transactions.py)

**Wiederverwenden:** [tests/test_memory_edit.py](../../../tests/test_memory_edit.py), [app/services/persistence_guard.py](../../../app/services/persistence_guard.py)

**Validierung nach Implementierung:** ` python -m pytest tests/test_memory_edit.py -q; ergänzend Memory-Emulatortest `

**Gezielte Negativkontrolle:** Guard entfernen oder Revisionsvergleich deaktivieren; neue Nichtänderungsassertions müssen scheitern.


<a id="g-009"></a>

## G-009 · Konkurrierende Registrierung ohne Auskunfts-/Benachrichtigungsleck

**P2 · missing_case** · Verträge: [AUTH-01](matrix.md#auth-01) · Paket: [WP-12](work-packages.md#wp-12)

**Aktuelle Bewertung:** resolved — Echter Registrierungsservice behandelt Lookup/Create-Race neutral ohne doppelte Neunutzerbenachrichtigung. user_status führt reale Rollen-/Tarifmatrix und Tierausfall aus. Firebase-SDK-Authentifizierung und DB ersetzt; externe Modell-, Mail- und Telegramgrenzen kontrolliert. Kein Live-OAuth oder produktiver Versand.

**Produktbeleg:** [app/services/registration.py](../../../app/services/registration.py#L48) — ` except firebase_admin.auth.EmailAlreadyExistsError: `

**Vorhandene relevante Prüfungen:**

- [test_new_user_gets_an_unguessable_server_side_password](../../../tests/test_registration_security.py#L12) — Registrierungsservice mit Firebase-/HTTP-Doubles. Assertionstellen: [24](../../../tests/test_registration_security.py#L24), [25](../../../tests/test_registration_security.py#L25), [27](../../../tests/test_registration_security.py#L27), [28](../../../tests/test_registration_security.py#L28).
- [AuthSessionTests::test_new_and_existing_registration_responses_are_identical](../../../tests/test_auth_session.py#L110) — API mit Auth-/Mail-/Notifier-Doubles. Assertionstellen: [141](../../../tests/test_auth_session.py#L141), [142](../../../tests/test_auth_session.py#L142).
- [test_every_topic_admin_method_enforces_real_policy_before_service](../../../tests/test_http_adapter_auth.py#L29) — Registrierte main.app mit echten Middleware-, Auth-/Owner- und Serviceguards. Assertionstellen: [43](../../../tests/test_http_adapter_auth.py#L43), [44](../../../tests/test_http_adapter_auth.py#L44), [45](../../../tests/test_http_adapter_auth.py#L45), [47](../../../tests/test_http_adapter_auth.py#L47).

**Suiteweite Gegenprüfung:** Echter Registrierungsservice behandelt Lookup/Create-Race neutral ohne doppelte Neunutzerbenachrichtigung. user_status führt reale Rollen-/Tarifmatrix und Tierausfall aus. Firebase-SDK-Authentifizierung und DB ersetzt; externe Modell-, Mail- und Telegramgrenzen kontrolliert. Kein Live-OAuth oder produktiver Versand.

**Suchspur:** 304 versionierte Test-/Hilfsdateien durchsucht, 10 passende Zeilen. Regexe: ` EmailAlreadyExists|find_or_provision_user|create.race `. Vollständige Treffer mit Pfad/Zeile in [search-evidence.json](search-evidence.json) unter ` G-009 `.

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

**Aktuelle Bewertung:** resolved — Ausgeführte Recoveryaufträge, lebende/abgelaufene Leases, kein zweiter Providerstart/Verbrauch; historischer Sourceadapter bindet alle Identitäten/Versionen, Pagination und Pollrevision. Backfill liest Run und Mapping transaktional neu. Infrastruktur/Providergrenzen kontrolliert; keine produktive Restart-/Lastfreigabe.

**Produktbeleg:** [app/api/routers/api_v1.py](../../../app/api/routers/api_v1.py#L400) — ` def get_run_source_check( `

**Vorhandene relevante Prüfungen:**

- [test_v4_public_share_rejects_wrong_job_version_on_every_page](../../../tests/test_source_check_api.py#L125) — Router mit SourceCheckRepository/FakeDb und Share-/Topic-Doubles. Assertionstellen: [138](../../../tests/test_source_check_api.py#L138), [140](../../../tests/test_source_check_api.py#L140).
- [test_restart_requeues_only_pre_provider_work_and_deduplicates_schedule](../../../tests/test_api_run_recovery.py#L104) — Recoveryorchestrierung mit echten Run-/Quota-/Cleanup-Repositories. Assertionstellen: [118](../../../tests/test_api_run_recovery.py#L118), [119](../../../tests/test_api_run_recovery.py#L119), [122](../../../tests/test_api_run_recovery.py#L122), [123](../../../tests/test_api_run_recovery.py#L123), [124](../../../tests/test_api_run_recovery.py#L124), [125](../../../tests/test_api_run_recovery.py#L125), [126](../../../tests/test_api_run_recovery.py#L126), [130](../../../tests/test_api_run_recovery.py#L130), [133](../../../tests/test_api_run_recovery.py#L133), [136](../../../tests/test_api_run_recovery.py#L136), [141](../../../tests/test_api_run_recovery.py#L141), [145](../../../tests/test_api_run_recovery.py#L145).
- [test_historic_api_source_pages_owner_cursor_revision_and_cache](../../../tests/test_api_source_history.py#L43) — Registrierte main.app mit echten Middleware-, Auth-/Owner- und Serviceguards. Assertionstellen: [52](../../../tests/test_api_source_history.py#L52), [53](../../../tests/test_api_source_history.py#L53), [60](../../../tests/test_api_source_history.py#L60), [61](../../../tests/test_api_source_history.py#L61), [62](../../../tests/test_api_source_history.py#L62), [64](../../../tests/test_api_source_history.py#L64), [73](../../../tests/test_api_source_history.py#L73), [75](../../../tests/test_api_source_history.py#L75).
- [test_retention_backfill_is_atomic_and_does_not_renew_another_run](../../../tests/e2e/test_api_retention_transactions.py#L8) — Echte Firestore-SDK-Transaktionen gegen isolierten Demo-Emulator. Assertionstellen: [21](../../../tests/e2e/test_api_retention_transactions.py#L21), [22](../../../tests/e2e/test_api_retention_transactions.py#L22), [23](../../../tests/e2e/test_api_retention_transactions.py#L23), [27](../../../tests/e2e/test_api_retention_transactions.py#L27), [28](../../../tests/e2e/test_api_retention_transactions.py#L28).

**Suiteweite Gegenprüfung:** Ausgeführte Recoveryaufträge, lebende/abgelaufene Leases, kein zweiter Providerstart/Verbrauch; historischer Sourceadapter bindet alle Identitäten/Versionen, Pagination und Pollrevision. Backfill liest Run und Mapping transaktional neu. Infrastruktur/Providergrenzen kontrolliert; keine produktive Restart-/Lastfreigabe.

**Suchspur:** 304 versionierte Test-/Hilfsdateien durchsucht, 56 passende Zeilen. Regexe: ` /api/v1/consensus/runs/.{0,100}source-check `, ` get_run_source_check|expected_snapshot|answer_version `. Vollständige Treffer mit Pfad/Zeile in [search-evidence.json](search-evidence.json) unter ` G-010 `.

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

**Aktuelle Bewertung:** resolved — App-POST schreibt das autoritative Pendingergebnis, verwirft gefälschte Inhalts-/Owner-/Visibilityfelder und prüft Quota/Ablauf/Retry. Antwort und persistierter Share stimmen überein. Firebase-SDK-Authentifizierung und DB ersetzt; externe Modell-, Mail- und Telegramgrenzen kontrolliert. Kein Live-OAuth oder produktiver Versand.

**Produktbeleg:** [app/api/routers/share.py](../../../app/api/routers/share.py#L357) — ` def create_share( `

**Vorhandene relevante Prüfungen:**

- [ShareFlowTests::test_create_share_is_idempotent](../../../tests/test_share_feature.py#L780) — Große Unit-/Service-/Router-/SSR-Suite mit FakeDb und lokalen Cachethreads. Assertionstellen: [790](../../../tests/test_share_feature.py#L790), [791](../../../tests/test_share_feature.py#L791), [792](../../../tests/test_share_feature.py#L792).
- [test_app_share_publishes_authoritative_content_and_retry_does_not_charge_twice](../../../tests/test_share_http_contract.py#L36) — Registrierte main.app mit echten Middleware-, Auth-/Owner- und Serviceguards. Assertionstellen: [48](../../../tests/test_share_http_contract.py#L48), [51](../../../tests/test_share_http_contract.py#L51), [52](../../../tests/test_share_http_contract.py#L52), [55](../../../tests/test_share_http_contract.py#L55), [56](../../../tests/test_share_http_contract.py#L56), [59](../../../tests/test_share_http_contract.py#L59), [60](../../../tests/test_share_http_contract.py#L60), [61](../../../tests/test_share_http_contract.py#L61).

**Suiteweite Gegenprüfung:** App-POST schreibt das autoritative Pendingergebnis, verwirft gefälschte Inhalts-/Owner-/Visibilityfelder und prüft Quota/Ablauf/Retry. Antwort und persistierter Share stimmen überein. Firebase-SDK-Authentifizierung und DB ersetzt; externe Modell-, Mail- und Telegramgrenzen kontrolliert. Kein Live-OAuth oder produktiver Versand.

**Suchspur:** 304 versionierte Test-/Hilfsdateien durchsucht, 34 passende Zeilen. Regexe: ` create_share\(|["\x27]/api/share["\x27] `, ` create_share_from_pending `. Vollständige Treffer mit Pfad/Zeile in [search-evidence.json](search-evidence.json) unter ` G-011 `.

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

**Aktuelle Bewertung:** resolved — Echter Registrierungsservice behandelt Lookup/Create-Race neutral ohne doppelte Neunutzerbenachrichtigung. user_status führt reale Rollen-/Tarifmatrix und Tierausfall aus. Firebase-SDK-Authentifizierung und DB ersetzt; externe Modell-, Mail- und Telegramgrenzen kontrolliert. Kein Live-OAuth oder produktiver Versand.

**Produktbeleg:** [app/api/routers/users.py](../../../app/api/routers/users.py#L61) — ` def get_user_status( `

**Vorhandene relevante Prüfungen:**

- [test_every_topic_admin_method_enforces_real_policy_before_service](../../../tests/test_http_adapter_auth.py#L29) — Registrierte main.app mit echten Middleware-, Auth-/Owner- und Serviceguards. Assertionstellen: [43](../../../tests/test_http_adapter_auth.py#L43), [44](../../../tests/test_http_adapter_auth.py#L44), [45](../../../tests/test_http_adapter_auth.py#L45), [47](../../../tests/test_http_adapter_auth.py#L47).

**Suiteweite Gegenprüfung:** Echter Registrierungsservice behandelt Lookup/Create-Race neutral ohne doppelte Neunutzerbenachrichtigung. user_status führt reale Rollen-/Tarifmatrix und Tierausfall aus. Firebase-SDK-Authentifizierung und DB ersetzt; externe Modell-, Mail- und Telegramgrenzen kontrolliert. Kein Live-OAuth oder produktiver Versand.

**Suchspur:** 304 versionierte Test-/Hilfsdateien durchsucht, 35 passende Zeilen. Regexe: ` /user_status|get_user_status|checkUserStatusOnLoad `. Vollständige Treffer mit Pfad/Zeile in [search-evidence.json](search-evidence.json) unter ` G-012 `.

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

**Aktuelle Bewertung:** resolved — Watch-/Telegramhandler und Abmelde-/Followeradapter prüfen UID/Owner/Tarif, Verbindung, Fehler und Tokenzustände vor Write; Disconnect ist UID-gebunden. Firebase-SDK-Authentifizierung und DB ersetzt; externe Modell-, Mail- und Telegramgrenzen kontrolliert. Kein Live-OAuth oder produktiver Versand.

**Produktbeleg:** [app/api/routers/watch.py](../../../app/api/routers/watch.py#L129) — ` def patch_watch( `; [app/api/routers/watch.py](../../../app/api/routers/watch.py#L218) — ` def remove_watch( `; [app/api/routers/watch.py](../../../app/api/routers/watch.py#L157) — ` def create_telegram_link( `; [app/api/routers/watch.py](../../../app/api/routers/watch.py#L173) — ` def test_telegram( `; [app/api/routers/watch.py](../../../app/api/routers/watch.py#L187) — ` def disconnect_telegram( `; [app/api/routers/watch.py](../../../app/api/routers/watch.py#L332) — ` def follow_unsubscribe( `; [app/api/routers/watch.py](../../../app/api/routers/watch.py#L344) — ` def unsubscribe(request: `

**Vorhandene relevante Prüfungen:**

- [WatchCrudTests::test_free_create_list_update_pause_delete](../../../tests/test_watch_feature.py#L177) — Große Service-/Scheduler-/Router-/Mailformat-Suite mit DB-/LLM-/Versand-Doubles plus UI-Sourceverträge. Assertionstellen: [179](../../../tests/test_watch_feature.py#L179), [180](../../../tests/test_watch_feature.py#L180), [181](../../../tests/test_watch_feature.py#L181), [182](../../../tests/test_watch_feature.py#L182), [183](../../../tests/test_watch_feature.py#L183), [184](../../../tests/test_watch_feature.py#L184), [185](../../../tests/test_watch_feature.py#L185), [188](../../../tests/test_watch_feature.py#L188), [190](../../../tests/test_watch_feature.py#L190), [192](../../../tests/test_watch_feature.py#L192).
- [WatchRouteTests::test_telegram_connection_routes_and_webhook_secret](../../../tests/test_watch_feature.py#L2713) — Große Service-/Scheduler-/Router-/Mailformat-Suite mit DB-/LLM-/Versand-Doubles plus UI-Sourceverträge. Assertionstellen: [2721](../../../tests/test_watch_feature.py#L2721), [2722](../../../tests/test_watch_feature.py#L2722), [2726](../../../tests/test_watch_feature.py#L2726), [2734](../../../tests/test_watch_feature.py#L2734), [2735](../../../tests/test_watch_feature.py#L2735).
- [test_watch_patch_delete_entitlement_owner_and_allowlist](../../../tests/test_watch_http_contract.py#L42) — Registrierte main.app mit echten Middleware-, Auth-/Owner- und Serviceguards. Assertionstellen: [52](../../../tests/test_watch_http_contract.py#L52), [53](../../../tests/test_watch_http_contract.py#L53), [60](../../../tests/test_watch_http_contract.py#L60), [62](../../../tests/test_watch_http_contract.py#L62), [63](../../../tests/test_watch_http_contract.py#L63), [64](../../../tests/test_watch_http_contract.py#L64), [65](../../../tests/test_watch_http_contract.py#L65), [66](../../../tests/test_watch_http_contract.py#L66), [67](../../../tests/test_watch_http_contract.py#L67), [68](../../../tests/test_watch_http_contract.py#L68).

**Suiteweite Gegenprüfung:** Watch-/Telegramhandler und Abmelde-/Followeradapter prüfen UID/Owner/Tarif, Verbindung, Fehler und Tokenzustände vor Write; Disconnect ist UID-gebunden. Firebase-SDK-Authentifizierung und DB ersetzt; externe Modell-, Mail- und Telegramgrenzen kontrolliert. Kein Live-OAuth oder produktiver Versand.

**Suchspur:** 304 versionierte Test-/Hilfsdateien durchsucht, 22 passende Zeilen. Regexe: ` patch_watch|remove_watch|create_telegram_link|test_telegram\( `, ` /api/watch/|/api/my/telegram/(link|test) `, ` disconnect_telegram|follow_unsubscribe|/watch/unsubscribe|/telegram/disconnect `. Vollständige Treffer mit Pfad/Zeile in [search-evidence.json](search-evidence.json) unter ` G-013 `.

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

**Aktuelle Bewertung:** resolved — Alle Topicadminmethoden prüfen Revocation und projizieren Tierausfall503. Hub/Sitemap unterscheiden Status/noindex korrekt. Neutraler Follow, tatsächlicher Confirm-/Unsubscribe-Link und Escaping ausgeführt. Firebase-SDK-Authentifizierung und DB ersetzt; externe Modell-, Mail- und Telegramgrenzen kontrolliert. Kein Live-OAuth oder produktiver Versand.

**Produktbeleg:** [app/api/routers/topics.py](../../../app/api/routers/topics.py#L138) — ` def _require_admin( `; [app/api/routers/topics.py](../../../app/api/routers/topics.py#L735) — ` async def admin_update_topic( `; [app/api/routers/topics.py](../../../app/api/routers/topics.py#L260) — ` async def topics_hub( `; [app/api/routers/topics.py](../../../app/api/routers/topics.py#L298) — ` async def sitemap_topics( `; [app/api/routers/topics.py](../../../app/api/routers/topics.py#L611) — ` async def follow_topic( `; [app/api/routers/admin.py](../../../app/api/routers/admin.py#L192) — ` uid = verify_user_token(id_token, check_revoked=True) `; [app/core/security.py](../../../app/core/security.py#L257) — ` check_revoked: bool = False `; [app/api/routers/topics.py](../../../app/api/routers/topics.py#L648) — ` def topic_follow_confirm( `; [app/api/routers/topics.py](../../../app/api/routers/topics.py#L665) — ` def topic_follow_unsubscribe( `; [app/api/routers/topics.py](../../../app/api/routers/topics.py#L690) — ` def admin_list_topics( `

**Vorhandene relevante Prüfungen:**

- [test_admin_topic_api_creates_updates_and_versions_without_share_data](../../../tests/test_topics_feature.py#L1137) — Große Service-/Router-/SSR-Suite mit FakeFirestore; einzelner echter SDK-Queryaufbau mit RPC-Mock. Assertionstellen: [1149](../../../tests/test_topics_feature.py#L1149), [1154](../../../tests/test_topics_feature.py#L1154), [1155](../../../tests/test_topics_feature.py#L1155), [1157](../../../tests/test_topics_feature.py#L1157), [1158](../../../tests/test_topics_feature.py#L1158), [1161](../../../tests/test_topics_feature.py#L1161), [1162](../../../tests/test_topics_feature.py#L1162), [1163](../../../tests/test_topics_feature.py#L1163).
- [test_admin_boundary_checks_revocation_and_maps_tier_outage_to_503](../../../tests/test_auth_revocation.py#L52) — Security-Funktionen mit Auth-/Datenbank-Doubles. Assertionstellen: [65](../../../tests/test_auth_revocation.py#L65), [68](../../../tests/test_auth_revocation.py#L68), [69](../../../tests/test_auth_revocation.py#L69).
- [test_noindex_and_unpublished_topics_are_not_in_topic_sitemap](../../../tests/test_topics_feature.py#L492) — Große Service-/Router-/SSR-Suite mit FakeFirestore; einzelner echter SDK-Queryaufbau mit RPC-Mock. Assertionstellen: [511](../../../tests/test_topics_feature.py#L511), [512](../../../tests/test_topics_feature.py#L512), [513](../../../tests/test_topics_feature.py#L513).
- [test_every_topic_admin_method_enforces_real_policy_before_service](../../../tests/test_http_adapter_auth.py#L29) — Registrierte main.app mit echten Middleware-, Auth-/Owner- und Serviceguards. Assertionstellen: [43](../../../tests/test_http_adapter_auth.py#L43), [44](../../../tests/test_http_adapter_auth.py#L44), [45](../../../tests/test_http_adapter_auth.py#L45), [47](../../../tests/test_http_adapter_auth.py#L47).
- [test_hub_and_sitemap_distinguish_noindex_from_archive_or_unpublished](../../../tests/test_topic_public_http.py#L34) — Registrierte main.app mit echten Middleware-, Auth-/Owner- und Serviceguards. Assertionstellen: [52](../../../tests/test_topic_public_http.py#L52), [54](../../../tests/test_topic_public_http.py#L54), [56](../../../tests/test_topic_public_http.py#L56), [58](../../../tests/test_topic_public_http.py#L58), [59](../../../tests/test_topic_public_http.py#L59), [61](../../../tests/test_topic_public_http.py#L61).

**Suiteweite Gegenprüfung:** Alle Topicadminmethoden prüfen Revocation und projizieren Tierausfall503. Hub/Sitemap unterscheiden Status/noindex korrekt. Neutraler Follow, tatsächlicher Confirm-/Unsubscribe-Link und Escaping ausgeführt. Firebase-SDK-Authentifizierung und DB ersetzt; externe Modell-, Mail- und Telegramgrenzen kontrolliert. Kein Live-OAuth oder produktiver Versand.

**Suchspur:** 304 versionierte Test-/Hilfsdateien durchsucht, 46 passende Zeilen. Regexe: ` admin_update_topic|topics_hub|sitemap_topics|follow_topic|_require_admin `, ` /api/admin/topics|/sitemap-topics.xml `, ` confirm_topic_follow|unsubscribe_topic|admin_list_topics|/topics/follow `. Vollständige Treffer mit Pfad/Zeile in [search-evidence.json](search-evidence.json) unter ` G-014 `.

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

**Aktuelle Bewertung:** resolved — Echter Adminrollen-/Reportadapter plus dynamischer Viewer: kompakte Daten, keine Rohprompts, passende Run-ID, stale Antwort/Fehler ignoriert und alte Daten bei Auswahlfehler entfernt. Reportdateien/Netzwerk lokal kontrolliert, kein Livebenchmark.

**Produktbeleg:** [app/api/routers/admin.py](../../../app/api/routers/admin.py#L872) — ` def admin_list_benchmark_runs( `; [app/api/routers/admin.py](../../../app/api/routers/admin.py#L886) — ` def admin_get_benchmark_run( `; [static/js/admin-benchmark.js](../../../static/js/admin-benchmark.js#L30) — ` async function `

**Vorhandene relevante Prüfungen:**

- [test_publish_run_dir_stores_compact_report_only](../../../tests/test_benchmark_reports.py#L76) — Report-Publisher mit FakeCollection. Assertionstellen: [83](../../../tests/test_benchmark_reports.py#L83), [86](../../../tests/test_benchmark_reports.py#L86), [87](../../../tests/test_benchmark_reports.py#L87), [88](../../../tests/test_benchmark_reports.py#L88), [89](../../../tests/test_benchmark_reports.py#L89), [90](../../../tests/test_benchmark_reports.py#L90).
- [test_every_topic_admin_method_enforces_real_policy_before_service](../../../tests/test_http_adapter_auth.py#L29) — Registrierte main.app mit echten Middleware-, Auth-/Owner- und Serviceguards. Assertionstellen: [43](../../../tests/test_http_adapter_auth.py#L43), [44](../../../tests/test_http_adapter_auth.py#L44), [45](../../../tests/test_http_adapter_auth.py#L45), [47](../../../tests/test_http_adapter_auth.py#L47).
- [renders compact data, safely quotes labels and excludes raw prompts/answers](../../../tests/js/admin-benchmark.test.mjs#L25) — Originaler Viewer und Adminclient im jsdom. Assertionstellen: [33](../../../tests/js/admin-benchmark.test.mjs#L33), [34](../../../tests/js/admin-benchmark.test.mjs#L34), [35](../../../tests/js/admin-benchmark.test.mjs#L35), [36](../../../tests/js/admin-benchmark.test.mjs#L36), [37](../../../tests/js/admin-benchmark.test.mjs#L37).

**Suiteweite Gegenprüfung:** Echter Adminrollen-/Reportadapter plus dynamischer Viewer: kompakte Daten, keine Rohprompts, passende Run-ID, stale Antwort/Fehler ignoriert und alte Daten bei Auswahlfehler entfernt. Reportdateien/Netzwerk lokal kontrolliert, kein Livebenchmark.

**Suchspur:** 304 versionierte Test-/Hilfsdateien durchsucht, 7 passende Zeilen. Regexe: ` /api/admin/benchmark|admin_list_benchmark_runs|admin_get_benchmark_run|admin-benchmark.js `. Vollständige Treffer mit Pfad/Zeile in [search-evidence.json](search-evidence.json) unter ` G-015 `.

| Szenario | Erwartung |
|---|---|
| Given | Ein kompakter Report, fehlende/traversierende ID, Backendfehler und Nonadmin. |
| When | Listen-/Detailroute und Viewerladung inklusive Auswahlwechsel/Fehlerantwort ausführen. |
| Then | Auth vor Read, kompakte Daten ohne Rohprompts, 404/Fehler korrekt und kein Stale-Report nach Auswahlwechsel. |

**Zielstellen:** [tests/test_benchmark_reports.py](../../../tests/test_benchmark_reports.py), [tests/js/admin-benchmark.test.mjs](../../../tests/js/admin-benchmark.test.mjs)

**Wiederverwenden:** [tests/test_benchmark_report_reader.py](../../../tests/test_benchmark_report_reader.py), [tests/test_benchmark_reports.py](../../../tests/test_benchmark_reports.py), [tests/js/helpers/appWindow.mjs](../../../tests/js/helpers/appWindow.mjs)

**Validierung nach Implementierung:** ` python -m pytest tests/test_benchmark_reports.py tests/test_benchmark_report_reader.py -q; npm test -- tests/js/admin-benchmark.test.mjs `

**Gezielte Negativkontrolle:** Adminprüfung überspringen oder verspätetes erstes Result rendern; negative Fälle müssen rot werden.


<a id="g-016"></a>

## G-016 · Claim-Identity-Judge selbst prüfen

**P2 · missing_case** · Verträge: [TOPIC-02](matrix.md#topic-02) · Paket: [WP-17](work-packages.md#wp-17)

**Aktuelle Bewertung:** resolved — Identityhelper/Parser/Retryplan prüft bekannte eindeutige Keys und ausschließlich echte JSON-Integer, begrenzte Inputs/Versuche, sichere Fehlerdiagnose. Fallback bewahrt schon reservierte Keys. Synthetische Modellantworten; neue Integerpräzisierung in D06/Implementierungsbericht dokumentiert.

**Produktbeleg:** [app/services/llm/consensus_engine.py](../../../app/services/llm/consensus_engine.py#L2699) — ` def query_claim_identity( `

**Vorhandene relevante Prüfungen:**

- [test_claim_identity_result_maps_claims_onto_the_keys_they_continue](../../../tests/test_topics_feature.py#L1119) — Große Service-/Router-/SSR-Suite mit FakeFirestore; einzelner echter SDK-Queryaufbau mit RPC-Mock. Assertionstellen: [1134](../../../tests/test_topics_feature.py#L1134).
- [test_claim_identity_falls_back_to_fresh_keys_when_the_judge_is_unavailable](../../../tests/test_topics_feature.py#L1098) — Große Service-/Router-/SSR-Suite mit FakeFirestore; einzelner echter SDK-Queryaufbau mit RPC-Mock. Assertionstellen: [1116](../../../tests/test_topics_feature.py#L1116).
- [test_known_unique_bindings_only](../../../tests/test_claim_identity_judge.py#L19) — Echter Identityhelper, Parser und Retryplan mit Transportdouble. Assertionstellen: [33](../../../tests/test_claim_identity_judge.py#L33), [34](../../../tests/test_claim_identity_judge.py#L34).
- [test_repair_inspect_does_not_apply_but_selected_account_recovery_does](../../../tests/test_maintenance_scripts.py#L114) — Echte Entry-Points in isolierten Subprozessen. Assertionstellen: [116](../../../tests/test_maintenance_scripts.py#L116), [117](../../../tests/test_maintenance_scripts.py#L117), [119](../../../tests/test_maintenance_scripts.py#L119), [120](../../../tests/test_maintenance_scripts.py#L120).

**Suiteweite Gegenprüfung:** Identityhelper/Parser/Retryplan prüft bekannte eindeutige Keys und ausschließlich echte JSON-Integer, begrenzte Inputs/Versuche, sichere Fehlerdiagnose. Fallback bewahrt schon reservierte Keys. Synthetische Modellantworten; neue Integerpräzisierung in D06/Implementierungsbericht dokumentiert.

**Suchspur:** 304 versionierte Test-/Hilfsdateien durchsucht, 10 passende Zeilen. Regexe: ` query_claim_identity|known_keys|claim_identity_result `. Vollständige Treffer mit Pfad/Zeile in [search-evidence.json](search-evidence.json) unter ` G-016 `.

| Szenario | Erwartung |
|---|---|
| Given | Bekannte Keys und neue Claims, synthetischer Transport mit gültigen/ungültigen matches und mehreren Versuchsergebnissen. |
| When | Realen Helper mit unbekannten/doppelten Keys, wiederholten/out-of-range/nichtnumerischen Indices, malformed JSON, leerem Input und Providerfehler aufrufen. |
| Then | Nur zulässige eindeutige Zuordnungen, begrenzte Inputs, definierter Fallback ohne Topicabbruch und redigierte Logs. Bool/Float-Indexsemantik vor Fix ausdrücklich entscheiden. |

**Zielstellen:** [tests/test_claim_identity_judge.py](../../../tests/test_claim_identity_judge.py)

**Wiederverwenden:** [tests/test_consensus_engine.py](../../../tests/test_consensus_engine.py), [tests/test_topics_feature.py](../../../tests/test_topics_feature.py)

**Validierung nach Implementierung:** ` python -m pytest tests/test_claim_identity_judge.py tests/test_topics_feature.py tests/test_claim_ledger.py -q `

**Gezielte Negativkontrolle:** known_keys-/used-Prüfung entfernen; erfundene/mehrfach vergebene IDs müssen erkannt werden.


<a id="g-017"></a>

## G-017 · SEO-Readadapter hinter den Service-Fakes

**P2 · missing_case** · Verträge: [SEO-02](matrix.md#seo-02), [SEO-04](matrix.md#seo-04) · Paket: [WP-18](work-packages.md#wp-18)

**Aktuelle Bewertung:** resolved — BatchGet ordnet anhand Dokumentidentität zu, begrenzt 615 Referenzen auf400/215; fehlende Snapshots/Messungen, Datumsformen und neueste Queries mit echten SDK-Fällen. Lokaler Emulator mit anonymen Credentials; kein Produktkonto, keine produktive IAM-/Lastgarantie. Nur eigene Dokumentwurzeln werden aufgeräumt.

**Produktbeleg:** [app/services/seo_repository.py](../../../app/services/seo_repository.py#L247) — ` def list_metrics_for_pages( `; [app/services/seo_repository.py](../../../app/services/seo_repository.py#L373) — ` def last_run( `; [app/services/seo_repository.py](../../../app/services/seo_repository.py#L424) — ` def list_judgments( `

**Vorhandene relevante Prüfungen:**

- [test_review_reuses_overview_context_without_second_metric_scan](../../../tests/test_seo_weekly_review.py#L300) — Review-Service mit Repository-/Judge-/Action-Doubles. Assertionstellen: [348](../../../tests/test_seo_weekly_review.py#L348), [349](../../../tests/test_seo_weekly_review.py#L349), [350](../../../tests/test_seo_weekly_review.py#L350).
- [test_batch_get_binds_document_identity_and_dates_not_position_or_payload](../../../tests/test_seo_repository.py#L9) — Echter Repositoryadapter mit kontrollierten SDK-Snapshots. Assertionstellen: [26](../../../tests/test_seo_repository.py#L26), [27](../../../tests/test_seo_repository.py#L27), [30](../../../tests/test_seo_repository.py#L30), [31](../../../tests/test_seo_repository.py#L31), [32](../../../tests/test_seo_repository.py#L32), [33](../../../tests/test_seo_repository.py#L33).
- [test_seo_native_latest_judgments_and_unordered_batch_identity](../../../tests/e2e/test_seo_repository_queries.py#L8) — Echte Firestore-SDK-Transaktionen gegen isolierten Demo-Emulator. Assertionstellen: [30](../../../tests/e2e/test_seo_repository_queries.py#L30), [35](../../../tests/e2e/test_seo_repository_queries.py#L35), [45](../../../tests/e2e/test_seo_repository_queries.py#L45), [46](../../../tests/e2e/test_seo_repository_queries.py#L46), [47](../../../tests/e2e/test_seo_repository_queries.py#L47).

**Suiteweite Gegenprüfung:** BatchGet ordnet anhand Dokumentidentität zu, begrenzt 615 Referenzen auf400/215; fehlende Snapshots/Messungen, Datumsformen und neueste Queries mit echten SDK-Fällen. Lokaler Emulator mit anonymen Credentials; kein Produktkonto, keine produktive IAM-/Lastgarantie. Nur eigene Dokumentwurzeln werden aufgeräumt.

**Suchspur:** 304 versionierte Test-/Hilfsdateien durchsucht, 45 passende Zeilen. Regexe: ` list_metrics_for_pages|list_judgments|last_run|latest_review|recent_reviews `. Vollständige Treffer mit Pfad/Zeile in [search-evidence.json](search-evidence.json) unter ` G-017 `.

| Szenario | Erwartung |
|---|---|
| Given | Mehrere Page-IDs, doppelte Inputs, über 400 Dokumentrefs, fehlende/ungeordnete Snapshots, leere und naive/aware Zeitstempel. |
| When | Reale Repositorymethoden mit SDK-kompatiblem Double, ergänzend Emulator für Queries, aufrufen. |
| Then | Exakte Seiten-/Datumszuordnung, keine Vermischung, bounded Batchgrößen, korrekt sortierte neueste Daten und deterministische leere Ergebnisse; Datenfehler nicht als Nulltraffic ausgeben. |

**Zielstellen:** [tests/test_seo_repository.py](../../../tests/test_seo_repository.py)

**Wiederverwenden:** [tests/test_seo_data.py](../../../tests/test_seo_data.py), [tests/test_seo_weekly_review.py](../../../tests/test_seo_weekly_review.py)

**Validierung nach Implementierung:** ` python -m pytest tests/test_seo_repository.py tests/test_seo_data.py tests/test_seo_weekly_review.py -q `

**Gezielte Negativkontrolle:** BatchGet-Snapshots nach Rückgabereihenfolge statt Dokumentpfad zuordnen; ungeordnete Fixture muss rot werden.


<a id="g-018"></a>

## G-018 · Topic-Notizen werden erneut als HTML interpretiert

**P1 · observed_behavior_defect** · Verträge: [TOPIC-05](matrix.md#topic-05) · Paket: [WP-20](work-packages.md#wp-20)

**Aktuelle Bewertung:** resolved — Originales Topicskript hält Notizen inert und Sonderzeichen lesbar; Focus/Enter, Touchpreview/Navigation, Seenmarker, historische Ansicht und blockierter Storage ausgeführt. Kontrollierte SSRfixture, kein vollständiger visueller Seitenaudit.

**Produktbeleg:** [app/services/claim_ledger.py](../../../app/services/claim_ledger.py#L455) — ` note = str(run.get("change_summary") `; [templates/topic.html](../../../templates/topic.html#L231) — ` data-note="{{ cell.note }}" `

**Vorhandene relevante Prüfungen:**

- [test_topic_templates_expose_timeline_evidence_follow_and_admin_controls](../../../tests/test_topics_feature.py#L851) — Große Service-/Router-/SSR-Suite mit FakeFirestore; einzelner echter SDK-Queryaufbau mit RPC-Mock. Assertionstellen: [857](../../../tests/test_topics_feature.py#L857), [858](../../../tests/test_topics_feature.py#L858), [859](../../../tests/test_topics_feature.py#L859), [860](../../../tests/test_topics_feature.py#L860), [863](../../../tests/test_topics_feature.py#L863), [864](../../../tests/test_topics_feature.py#L864), [865](../../../tests/test_topics_feature.py#L865), [868](../../../tests/test_topics_feature.py#L868), [872](../../../tests/test_topics_feature.py#L872), [873](../../../tests/test_topics_feature.py#L873), [874](../../../tests/test_topics_feature.py#L874), [876](../../../tests/test_topics_feature.py#L876), [877](../../../tests/test_topics_feature.py#L877), [878](../../../tests/test_topics_feature.py#L878), [879](../../../tests/test_topics_feature.py#L879), [880](../../../tests/test_topics_feature.py#L880), [881](../../../tests/test_topics_feature.py#L881), [882](../../../tests/test_topics_feature.py#L882), [883](../../../tests/test_topics_feature.py#L883), [884](../../../tests/test_topics_feature.py#L884), [885](../../../tests/test_topics_feature.py#L885), [886](../../../tests/test_topics_feature.py#L886).
- [test_topic_markup_stays_text_and_preview_preserves_navigation](../../../tests/e2e/test_topic_frontend.py#L33) — Chromium mit Originalskript und kontrollierter SSR-Minimalfixture. Assertionstellen: [39](../../../tests/e2e/test_topic_frontend.py#L39), [42](../../../tests/e2e/test_topic_frontend.py#L42), [43](../../../tests/e2e/test_topic_frontend.py#L43), [44](../../../tests/e2e/test_topic_frontend.py#L44), [45](../../../tests/e2e/test_topic_frontend.py#L45), [50](../../../tests/e2e/test_topic_frontend.py#L50), [51](../../../tests/e2e/test_topic_frontend.py#L51).
- [`shows HTML-like notes literally on ${label}`](../../../tests/js/topic-page.test.mjs#L57) — jsdom-Checkstrip und Returning-Reader-Band. Assertionstellen: [63](../../../tests/js/topic-page.test.mjs#L63), [64](../../../tests/js/topic-page.test.mjs#L64), [65](../../../tests/js/topic-page.test.mjs#L65), [66](../../../tests/js/topic-page.test.mjs#L66), [67](../../../tests/js/topic-page.test.mjs#L67), [68](../../../tests/js/topic-page.test.mjs#L68).

**Suiteweite Gegenprüfung:** Originales Topicskript hält Notizen inert und Sonderzeichen lesbar; Focus/Enter, Touchpreview/Navigation, Seenmarker, historische Ansicht und blockierter Storage ausgeführt. Kontrollierte SSRfixture, kein vollständiger visueller Seitenaudit.

**Suchspur:** 304 versionierte Test-/Hilfsdateien durchsucht, 20 passende Zeilen. Regexe: ` topic-page|topicStripRead|topicReturn|topic-seen:|readStrip|returningReader `. Vollständige Treffer mit Pfad/Zeile in [search-evidence.json](search-evidence.json) unter ` G-018 `.

| Szenario | Erwartung |
|---|---|
| Given | SSR-escaped Notiz mit wörtlichem HTML, Quotes und Sonderzeichen; normaler/Touch-/historischer/Storage-blockierter Besuch. |
| When | Topicmodul laden und Zelle fokussieren/hovern/antippen; aktuellen und historischen Besuch wiederholen. |
| Then | Notiz bleibt Text, keine aus Notiz erzeugten Elemente/Handler. Touchvorschau, zweite Navigation, Unseen-Marker und historische Storageisolation funktionieren weiterhin. |

**Zielstellen:** [tests/js/topic-page.test.mjs](../../../tests/js/topic-page.test.mjs), [tests/e2e/test_topic_frontend.py](../../../tests/e2e/test_topic_frontend.py)

**Wiederverwenden:** [tests/js/helpers/appWindow.mjs](../../../tests/js/helpers/appWindow.mjs), [tests/test_claim_ledger.py](../../../tests/test_claim_ledger.py)

**Validierung nach Implementierung:** ` npm test -- tests/js/topic-page.test.mjs; ergänzend gezielter Topic-Browserfall `

**Gezielte Negativkontrolle:** Aktuelles innerHTML-Verhalten muss am literalen Notiztest scheitern; kein Snapshot akzeptieren, der die Injection festschreibt.


<a id="g-019"></a>

## G-019 · Strukturierte Adminfehler verlieren ihre Nachricht

**P2 · observed_behavior_defect** · Verträge: [ADMIN-02](matrix.md#admin-02) · Paket: [WP-21](work-packages.md#wp-21)

**Aktuelle Bewertung:** resolved — Echter main-error-Umschlag ist serverseitig belegt und wird vom tatsächlichen Adminclient lesbar projiziert; unbekannte Objekte fallen sicher zurück,409 behält Draft ohne Retry. Fetch/Auth kontrolliert, keine gemeinsame Firestore-/Browsertransaktion.

**Produktbeleg:** [main.py](../../../main.py#L242) — ` content={"error": exc.detail} `; [app/api/routers/admin.py](../../../app/api/routers/admin.py#L642) — ` detail={"error_code": exc.code `

**Vorhandene relevante Prüfungen:**

- [test_configuration_tab_saves_reloads_and_preserves_conflicting_draft](../../../tests/e2e/test_admin_prompt_config.py#L15) — Chromium-Browserintegration mit simulierten Admin-APIs. Assertionstellen: [30](../../../tests/e2e/test_admin_prompt_config.py#L30), [46](../../../tests/e2e/test_admin_prompt_config.py#L46), [47](../../../tests/e2e/test_admin_prompt_config.py#L47), [49](../../../tests/e2e/test_admin_prompt_config.py#L49), [50](../../../tests/e2e/test_admin_prompt_config.py#L50), [51](../../../tests/e2e/test_admin_prompt_config.py#L51), [53](../../../tests/e2e/test_admin_prompt_config.py#L53), [55](../../../tests/e2e/test_admin_prompt_config.py#L55), [56](../../../tests/e2e/test_admin_prompt_config.py#L56), [57](../../../tests/e2e/test_admin_prompt_config.py#L57), [64](../../../tests/e2e/test_admin_prompt_config.py#L64), [65](../../../tests/e2e/test_admin_prompt_config.py#L65), [72](../../../tests/e2e/test_admin_prompt_config.py#L72), [73](../../../tests/e2e/test_admin_prompt_config.py#L73), [74](../../../tests/e2e/test_admin_prompt_config.py#L74), [76](../../../tests/e2e/test_admin_prompt_config.py#L76), [77](../../../tests/e2e/test_admin_prompt_config.py#L77), [78](../../../tests/e2e/test_admin_prompt_config.py#L78), [85](../../../tests/e2e/test_admin_prompt_config.py#L85), [86](../../../tests/e2e/test_admin_prompt_config.py#L86), [88](../../../tests/e2e/test_admin_prompt_config.py#L88), [90](../../../tests/e2e/test_admin_prompt_config.py#L90), [91](../../../tests/e2e/test_admin_prompt_config.py#L91), [92](../../../tests/e2e/test_admin_prompt_config.py#L92), [94](../../../tests/e2e/test_admin_prompt_config.py#L94), [95](../../../tests/e2e/test_admin_prompt_config.py#L95), [96](../../../tests/e2e/test_admin_prompt_config.py#L96), [101](../../../tests/e2e/test_admin_prompt_config.py#L101).
- [unpacks only allowed strings from %j](../../../tests/js/admin-api.test.mjs#L8) — Originaler Adminclient mit kontrolliertem Fetch. Assertionstellen: [20](../../../tests/js/admin-api.test.mjs#L20), [21](../../../tests/js/admin-api.test.mjs#L21), [22](../../../tests/js/admin-api.test.mjs#L22).
- [shows the real main error envelope while retaining a conflicting draft without a second write](../../../tests/js/admin-prompt-config.test.mjs#L31) — Prompteditor im jsdom mit echtem Adminclient. Assertionstellen: [40](../../../tests/js/admin-prompt-config.test.mjs#L40), [41](../../../tests/js/admin-prompt-config.test.mjs#L41), [42](../../../tests/js/admin-prompt-config.test.mjs#L42), [43](../../../tests/js/admin-prompt-config.test.mjs#L43), [44](../../../tests/js/admin-prompt-config.test.mjs#L44).
- [test_set_tier_writes_the_field_audits_it_and_drops_the_cache](../../../tests/test_account_tier_admin.py#L144) — Registrierte main.app mit echten Middleware-, Auth-/Owner- und Serviceguards. Assertionstellen: [149](../../../tests/test_account_tier_admin.py#L149), [150](../../../tests/test_account_tier_admin.py#L150), [151](../../../tests/test_account_tier_admin.py#L151), [152](../../../tests/test_account_tier_admin.py#L152), [155](../../../tests/test_account_tier_admin.py#L155), [156](../../../tests/test_account_tier_admin.py#L156), [157](../../../tests/test_account_tier_admin.py#L157), [158](../../../tests/test_account_tier_admin.py#L158), [161](../../../tests/test_account_tier_admin.py#L161), [162](../../../tests/test_account_tier_admin.py#L162), [163](../../../tests/test_account_tier_admin.py#L163), [164](../../../tests/test_account_tier_admin.py#L164), [165](../../../tests/test_account_tier_admin.py#L165), [166](../../../tests/test_account_tier_admin.py#L166).

**Suiteweite Gegenprüfung:** Echter main-error-Umschlag ist serverseitig belegt und wird vom tatsächlichen Adminclient lesbar projiziert; unbekannte Objekte fallen sicher zurück,409 behält Draft ohne Retry. Fetch/Auth kontrolliert, keine gemeinsame Firestore-/Browsertransaktion.

**Suchspur:** 304 versionierte Test-/Hilfsdateien durchsucht, 16 passende Zeilen. Regexe: ` createAdminClient|admin-api.js|\[object Object\] `, ` Configuration changed in another session `. Vollständige Treffer mit Pfad/Zeile in [search-evidence.json](search-evidence.json) unter ` G-019 `.

| Szenario | Erwartung |
|---|---|
| Given | createAdminClient mit Responseformen aus main.handle_http_exception, Standard-FastAPI, nicht-JSON und leerem Body. |
| When | Fehlerhafte Adminanfrage einschließlich AccountTierError ausführen. |
| Then | Verständliche erlaubte Nachricht/HTTP-Fallback statt Objektstring; Token-/Statusfehler propagieren, kein zweiter Write. Panelentwurf bleibt bei Konflikt erhalten. |

**Zielstellen:** [tests/js/admin-api.test.mjs](../../../tests/js/admin-api.test.mjs), [tests/test_account_tier_admin.py](../../../tests/test_account_tier_admin.py)

**Wiederverwenden:** [tests/e2e/test_admin_prompt_config.py](../../../tests/e2e/test_admin_prompt_config.py), [tests/js/admin-prompt-config.test.mjs](../../../tests/js/admin-prompt-config.test.mjs)

**Validierung nach Implementierung:** ` npm test -- tests/js/admin-api.test.mjs tests/js/admin-prompt-config.test.mjs; python -m pytest tests/test_account_tier_admin.py -q `

**Gezielte Negativkontrolle:** Unveränderter Client muss am main-error-Objektfall rot werden; echten Responseumschlag verwenden.


<a id="g-020"></a>

## G-020 · OG-Test akzeptiert leeres Bild

**P2 · assertion_gap** · Verträge: [SHARE-04](matrix.md#share-04) · Paket: [WP-23](work-packages.md#wp-23)

**Aktuelle Bewertung:** resolved — Echtes PNG mit gezeichneten Bildregionen, Fragepixel, Score/Modelle/Konflikte/unscored und privater Route. Cache berücksichtigt alle sichtbaren Inhalte und Renderfehlerretry. Keine pixelgenauen Hashes, keine neue historische OG-Versionsauswahl.

**Produktbeleg:** [app/services/og_image.py](../../../app/services/og_image.py#L93) — ` def render_share_card( `; [app/api/routers/share.py](../../../app/api/routers/share.py#L550) — ` def share_og_card( `

**Vorhandene relevante Prüfungen:**

- [ShareSeoEnhancementTests::test_og_card_route_and_meta](../../../tests/test_share_feature.py#L2597) — Große Unit-/Service-/Router-/SSR-Suite mit FakeDb und lokalen Cachethreads. Assertionstellen: [2604](../../../tests/test_share_feature.py#L2604), [2605](../../../tests/test_share_feature.py#L2605), [2606](../../../tests/test_share_feature.py#L2606), [2607](../../../tests/test_share_feature.py#L2607), [2608](../../../tests/test_share_feature.py#L2608), [2609](../../../tests/test_share_feature.py#L2609).
- [ShareSeoEnhancementTests::test_og_card_404_for_private_pages](../../../tests/test_share_feature.py#L2611) — Große Unit-/Service-/Router-/SSR-Suite mit FakeDb und lokalen Cachethreads. Assertionstellen: [2615](../../../tests/test_share_feature.py#L2615).
- [test_renderer_draws_question_score_and_model_facts](../../../tests/test_og_image.py#L31) — Echter Pillowrenderer und kontrollierter Imagecache. Assertionstellen: [41](../../../tests/test_og_image.py#L41), [42](../../../tests/test_og_image.py#L42), [43](../../../tests/test_og_image.py#L43), [44](../../../tests/test_og_image.py#L44), [47](../../../tests/test_og_image.py#L47), [53](../../../tests/test_og_image.py#L53).
- [test_app_share_publishes_authoritative_content_and_retry_does_not_charge_twice](../../../tests/test_share_http_contract.py#L36) — Registrierte main.app mit echten Middleware-, Auth-/Owner- und Serviceguards. Assertionstellen: [48](../../../tests/test_share_http_contract.py#L48), [51](../../../tests/test_share_http_contract.py#L51), [52](../../../tests/test_share_http_contract.py#L52), [55](../../../tests/test_share_http_contract.py#L55), [56](../../../tests/test_share_http_contract.py#L56), [59](../../../tests/test_share_http_contract.py#L59), [60](../../../tests/test_share_http_contract.py#L60), [61](../../../tests/test_share_http_contract.py#L61).

**Suiteweite Gegenprüfung:** Echtes PNG mit gezeichneten Bildregionen, Fragepixel, Score/Modelle/Konflikte/unscored und privater Route. Cache berücksichtigt alle sichtbaren Inhalte und Renderfehlerretry. Keine pixelgenauen Hashes, keine neue historische OG-Versionsauswahl.

**Suchspur:** 304 versionierte Test-/Hilfsdateien durchsucht, 22 passende Zeilen. Regexe: ` og_image|og\.png|share_card|render_share_card `. Vollständige Treffer mit Pfad/Zeile in [search-evidence.json](search-evidence.json) unter ` G-020 `.

| Szenario | Erwartung |
|---|---|
| Given | Öffentlicher Snapshot mit markanter Frage, bekannten Modell-/Konfliktzahlen und Score; unscored/private/Renderingfehler separat. |
| When | Route und echten Renderer aufrufen, PNG dekodieren; semantische Renderinputs/Zeichenoperationen und stabile Bildinhalte prüfen. |
| Then | 1200×630 PNG enthält Frage/korrekte Kennzahlen, unscored erfindet keinen Score, private/inaktive Seite kein Bild. Deterministische Bildregionen oder toleranter Baselinevergleich statt bloß Bytepräfix. |

**Zielstellen:** [tests/test_og_image.py](../../../tests/test_og_image.py), [tests/test_share_feature.py](../../../tests/test_share_feature.py)

**Wiederverwenden:** [tests/test_share_feature.py](../../../tests/test_share_feature.py)

**Validierung nach Implementierung:** ` python -m pytest tests/test_og_image.py tests/test_share_feature.py -q `

**Gezielte Negativkontrolle:** Blank-PNG-Probe M-02 muss nach Ergänzung rot werden. Keine variable Font-Rasterisierung als exakter Plattformhash festschreiben.


<a id="g-021"></a>

## G-021 · Analytics-Opt-out ausführen statt Strings suchen

**P2 · assertion_gap** · Verträge: [UI-09](matrix.md#ui-09) · Paket: [WP-24](work-packages.md#wp-24)

**Aktuelle Bewertung:** resolved — Originales Skript läuft vor instrumentiertem Seitenstart für1/0/fehlend/leer/anders und Storagefehler. Vorhandener Wert bleibt bei anderen Parametern erhalten. Kein echter Tracker oder Analyticseventversand.

**Produktbeleg:** [static/js/analytics-opt-out.js](../../../static/js/analytics-opt-out.js#L3) — ` const flag = `

**Vorhandene relevante Prüfungen:**

- [test_partial_ships_the_self_exclusion_switch](../../../tests/test_analytics_partial.py#L59) — Quelltextverträge. Assertionstellen: [67](../../../tests/test_analytics_partial.py#L67), [68](../../../tests/test_analytics_partial.py#L68), [69](../../../tests/test_analytics_partial.py#L69).
- [applies %s to %s before the next script runs](../../../tests/js/analytics-opt-out.test.mjs#L9) — Originales Skript in frischem jsdom vor instrumentiertem Trackerstart. Assertionstellen: [19](../../../tests/js/analytics-opt-out.test.mjs#L19), [20](../../../tests/js/analytics-opt-out.test.mjs#L20).

**Suiteweite Gegenprüfung:** Originales Skript läuft vor instrumentiertem Seitenstart für1/0/fehlend/leer/anders und Storagefehler. Vorhandener Wert bleibt bei anderen Parametern erhalten. Kein echter Tracker oder Analyticseventversand.

**Suchspur:** 304 versionierte Test-/Hilfsdateien durchsucht, 16 passende Zeilen. Regexe: ` analytics-opt-out|notrack|umami.disabled `. Vollständige Treffer mit Pfad/Zeile in [search-evidence.json](search-evidence.json) unter ` G-021 `.

| Szenario | Erwartung |
|---|---|
| Given | notrack=1, 0, anderer/fehlender Wert und Storage mit setItem-/removeItem-Fehlern. Das Skript liest Storage nicht über getItem. |
| When | Originalskript in isoliertem DOM vor einem instrumentierten Trackerstart ausführen. |
| Then | Flag korrekt gesetzt/entfernt/erhalten und vor Trackerbeobachtung wirksam; blockierter Storage bricht Seitenstart nicht ab. |

**Zielstellen:** [tests/js/analytics-opt-out.test.mjs](../../../tests/js/analytics-opt-out.test.mjs)

**Wiederverwenden:** [tests/js/helpers/appWindow.mjs](../../../tests/js/helpers/appWindow.mjs), [tests/test_analytics_partial.py](../../../tests/test_analytics_partial.py)

**Validierung nach Implementierung:** ` npm test -- tests/js/analytics-opt-out.test.mjs; python -m pytest tests/test_analytics_partial.py -q `

**Gezielte Negativkontrolle:** Bedingungen 1/0 vertauschen oder in unerreichbaren Block stellen; Verhaltenstest muss rot werden.


<a id="g-022"></a>

## G-022 · Account-Reparaturskript ohne Produktionszugriff prüfen

**P1 · missing_case** · Verträge: [TOOLS-01](matrix.md#tools-01) · Paket: [WP-25](work-packages.md#wp-25)

**Aktuelle Bewertung:** resolved — Wartungseinstiege in netzwerkgesperrten Subprozessen, Account-/Apply-/Projektguards, Dry-run und wiederholbarer Backfill. Bestehende Claimkeys werden reserviert; Fallbackkollisionen verhindert. Backfill-Dry-run kann in echter Umgebung einen Judgeaufruf kosten; Tests ersetzen ihn.

**Produktbeleg:** [scripts/repair_agent_allowance.py](../../../scripts/repair_agent_allowance.py#L16) — ` def main(): `

**Vorhandene relevante Prüfungen:**

- [test_repair_inspect_does_not_apply_but_selected_account_recovery_does](../../../tests/test_maintenance_scripts.py#L114) — Echte Entry-Points in isolierten Subprozessen. Assertionstellen: [116](../../../tests/test_maintenance_scripts.py#L116), [117](../../../tests/test_maintenance_scripts.py#L117), [119](../../../tests/test_maintenance_scripts.py#L119), [120](../../../tests/test_maintenance_scripts.py#L120).

**Suiteweite Gegenprüfung:** Wartungseinstiege in netzwerkgesperrten Subprozessen, Account-/Apply-/Projektguards, Dry-run und wiederholbarer Backfill. Bestehende Claimkeys werden reserviert; Fallbackkollisionen verhindert. Backfill-Dry-run kann in echter Umgebung einen Judgeaufruf kosten; Tests ersetzen ihn.

**Suchspur:** 304 versionierte Test-/Hilfsdateien durchsucht, 1 passende Zeilen. Regexe: ` repair_agent_allowance|Production repair cannot|Configured Firebase project `. Vollständige Treffer mit Pfad/Zeile in [search-evidence.json](search-evidence.json) unter ` G-022 `.

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

**Aktuelle Bewertung:** resolved — Wartungseinstiege in netzwerkgesperrten Subprozessen, Account-/Apply-/Projektguards, Dry-run und wiederholbarer Backfill. Bestehende Claimkeys werden reserviert; Fallbackkollisionen verhindert. Backfill-Dry-run kann in echter Umgebung einen Judgeaufruf kosten; Tests ersetzen ihn.

**Produktbeleg:** [scripts/backfill_claim_keys.py](../../../scripts/backfill_claim_keys.py#L41) — ` def backfill_topic( `; [scripts/backfill_claim_keys.py](../../../scripts/backfill_claim_keys.py#L99) — ` def main() `

**Vorhandene relevante Prüfungen:**

- [test_repair_inspect_does_not_apply_but_selected_account_recovery_does](../../../tests/test_maintenance_scripts.py#L114) — Echte Entry-Points in isolierten Subprozessen. Assertionstellen: [116](../../../tests/test_maintenance_scripts.py#L116), [117](../../../tests/test_maintenance_scripts.py#L117), [119](../../../tests/test_maintenance_scripts.py#L119), [120](../../../tests/test_maintenance_scripts.py#L120).

**Suiteweite Gegenprüfung:** Wartungseinstiege in netzwerkgesperrten Subprozessen, Account-/Apply-/Projektguards, Dry-run und wiederholbarer Backfill. Bestehende Claimkeys werden reserviert; Fallbackkollisionen verhindert. Backfill-Dry-run kann in echter Umgebung einen Judgeaufruf kosten; Tests ersetzen ihn.

**Suchspur:** 304 versionierte Test-/Hilfsdateien durchsucht, 2 passende Zeilen. Regexe: ` backfill_claim_keys|backfill_topic|Would update `. Vollständige Treffer mit Pfad/Zeile in [search-evidence.json](search-evidence.json) unter ` G-023 `.

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

**Aktuelle Bewertung:** resolved — Nutzerkonforme schnelle Auswahl und vollständige Auswahl sind belegt. ReadyForReview auf ffaca3df startete alle vier Jobs; Backend, Frontend/Build, Browser/Rules und Windows schlossen erfolgreich ab. Linux-Plattformskips bleiben separat sichtbar; der primäre lokale Windows-Backendlauf enthält sämtliche 3303 Fälle bestanden. Voll-CI https://github.com/sudoleo/consens/actions/runs/36995379657 auf ffaca3df erfolgreich. Gewöhnliche Push-/PR-Läufe bleiben nach ausdrücklicher Nutzerentscheidung schnell; reine Dokumentänderungen lösen keine weitere Vollsuite aus.

**Produktbeleg:** [.github/workflows/publisher-tests.yml](../../../.github/workflows/publisher-tests.yml#L1) — ` name: `; [package.json](../../../package.json#L9) — ` "test": `

**Vorhandene relevante Prüfungen:**

- [test_frontend_runs_tests_then_build_check_from_repository_root](../../../tests/test_dev_cli.py#L153) — Windows-PowerShell-/pwsh-Subprozesse mit instrumentierten Runnern. Assertionstellen: [156](../../../tests/test_dev_cli.py#L156), [157](../../../tests/test_dev_cli.py#L157), [160](../../../tests/test_dev_cli.py#L160).

**Suiteweite Gegenprüfung:** Nutzerkonforme schnelle Auswahl und vollständige Auswahl sind belegt. ReadyForReview auf ffaca3df startete alle vier Jobs; Backend, Frontend/Build, Browser/Rules und Windows schlossen erfolgreich ab. Linux-Plattformskips bleiben separat sichtbar; der primäre lokale Windows-Backendlauf enthält sämtliche 3303 Fälle bestanden. Voll-CI https://github.com/sudoleo/consens/actions/runs/36995379657 auf ffaca3df erfolgreich. Gewöhnliche Push-/PR-Läufe bleiben nach ausdrücklicher Nutzerentscheidung schnell; reine Dokumentänderungen lösen keine weitere Vollsuite aus.

**Suchspur:** 304 versionierte Test-/Hilfsdateien durchsucht, 1037 passende Zeilen. Regexe: ` publisher-tests|pytest|vitest `. Vollständige Treffer mit Pfad/Zeile in [search-evidence.json](search-evidence.json) unter ` G-024 `.

| Szenario | Erwartung |
|---|---|
| Given | Reproduzierbares Python/Node/Java/Chromium-Setup, dokumentierte fehlgeschlagene Tests vorher bearbeitet. |
| When | Workflow mit getrennter schneller und vollständiger Auswahl gemäß Nutzerentscheidung caa7bac6 ausführen. |
| Then | Schnelle Läufe starten Backend/Frontend; vollständige Auswahl startet zusätzlich Browser/Emulator/Rules und Windows. Bewusste Ereignisskips transparent von tatsächlichen Tests unterscheiden; keine Fehlernormalisierung, Reports bei Fehlern, ausschließlich Demo-Projekt ohne Produktkey. Publisher-CI bleibt eigenständig. |

**Zielstellen:** [.github/workflows/tests.yml](../../../.github/workflows/tests.yml), [docs/testing.md](../../testing.md)

**Wiederverwenden:** [dev.ps1](../../../dev.ps1), [tests/e2e/README.md](../../../tests/e2e/README.md), [.github/workflows/publisher-tests.yml](../../../.github/workflows/publisher-tests.yml)

**Validierung nach Implementierung:** ` Neue Jobs auf genau dem integrierten Commit prüfen; kein einzelner Publisher-Erfolg als Gesamtsuite-Erfolg werten. `

**Gezielte Negativkontrolle:** Absichtlich fehlschlagender Test in isoliertem CI-Probelauf muss den zugehörigen Job rot machen.


<a id="g-025"></a>

## G-025 · Aktuelle Browserfälle ausführen und rote Fälle klären

**P1 · execution_gap** · Verträge: [BUILD-02](matrix.md#build-02), [UI-06](matrix.md#ui-06) · Paket: [WP-03](work-packages.md#wp-03)

**Aktuelle Bewertung:** resolved — Der vollständige integrierte E2E-Lauf umfasst 368 bestandene Fälle ohne Fehler oder Skips: native SDK-Transaktionen, writerfreie Browserdetails, 43 aktuelle Smoke-Fälle und sechs persistierte Reisen. App-/Browserversion, ursprüngliche Runneridentitäten und neue/entfallene IDs gegenüber dem früheren Inventar sind archiviert. GitHubjob 110800783463 auf ffaca3df mit Chromium 148.0.7778.96/Playwright 1.60.0 bestanden; konkrete Mockgrenzen bleiben je Datei erhalten. Keine Behauptung einer flächigen visuellen oder Liveanbieter-Abnahme.

**Produktbeleg:** [tests/e2e/conftest.py](../../../tests/e2e/conftest.py#L126) — ` browser = p.chromium.launch() `

**Vorhandene relevante Prüfungen:**

- [test_phase4_server_reuses_its_child_and_rejects_an_unowned_listener](../../../tests/e2e/test_phase4_frontend.py#L143) — Chromium und ein gemeinsam gestarteter lokaler Testserver. Assertionstellen: [150](../../../tests/e2e/test_phase4_frontend.py#L150), [151](../../../tests/e2e/test_phase4_frontend.py#L151), [153](../../../tests/e2e/test_phase4_frontend.py#L153), [156](../../../tests/e2e/test_phase4_frontend.py#L156).
- [test_topic_markup_stays_text_and_preview_preserves_navigation](../../../tests/e2e/test_topic_frontend.py#L33) — Chromium mit Originalskript und kontrollierter SSR-Minimalfixture. Assertionstellen: [39](../../../tests/e2e/test_topic_frontend.py#L39), [42](../../../tests/e2e/test_topic_frontend.py#L42), [43](../../../tests/e2e/test_topic_frontend.py#L43), [44](../../../tests/e2e/test_topic_frontend.py#L44), [45](../../../tests/e2e/test_topic_frontend.py#L45), [50](../../../tests/e2e/test_topic_frontend.py#L50), [51](../../../tests/e2e/test_topic_frontend.py#L51).
- [test_app_loads_without_console_errors](../../../tests/e2e/test_smoke.py#L89) — Chromium gegen echte App-Routen und Demo-Firestore mit kontrollierter Identität/Modellen; ergänzend direkte Rendererfälle. Assertionstellen: [99](../../../tests/e2e/test_smoke.py#L99), [100](../../../tests/e2e/test_smoke.py#L100), [103](../../../tests/e2e/test_smoke.py#L103), [104](../../../tests/e2e/test_smoke.py#L104), [105](../../../tests/e2e/test_smoke.py#L105), [110](../../../tests/e2e/test_smoke.py#L110).

**Suiteweite Gegenprüfung:** Der vollständige integrierte E2E-Lauf umfasst 368 bestandene Fälle ohne Fehler oder Skips: native SDK-Transaktionen, writerfreie Browserdetails, 43 aktuelle Smoke-Fälle und sechs persistierte Reisen. App-/Browserversion, ursprüngliche Runneridentitäten und neue/entfallene IDs gegenüber dem früheren Inventar sind archiviert. GitHubjob 110800783463 auf ffaca3df mit Chromium 148.0.7778.96/Playwright 1.60.0 bestanden; konkrete Mockgrenzen bleiben je Datei erhalten. Keine Behauptung einer flächigen visuellen oder Liveanbieter-Abnahme.

**Suchspur:** 304 versionierte Test-/Hilfsdateien durchsucht, 2 passende Zeilen. Regexe: ` chromium.launch|def browser\( `. Vollständige Treffer mit Pfad/Zeile in [search-evidence.json](search-evidence.json) unter ` G-025 `.

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

**Aktuelle Bewertung:** resolved — Alle 28 CLI-Vertragsfälle in Windows PowerShell und pwsh sowie reale dev.ps1-Aufrufe für Backend, Frontend/Build, 49 Rulesfälle und vier native Phase2-Fälle liefen im Windows-CI-Job erfolgreich. Windows-GitHubjob 110800783247 auf integriertem Code ffaca3df erfolgreich: https://github.com/sudoleo/consens/actions/runs/36995379657/job/110800783247 . Native Windowsfälle ergänzen die ausdrücklich erhaltenen Linux-Plattformskips. Keine produktiven Credentials oder Cloudwrites.

**Produktbeleg:** [dev.ps1](../../../dev.ps1#L14) — ` param( `; [tests/test_dev_cli.py](../../../tests/test_dev_cli.py#L25) — ` @pytest.fixture(params=SHELLS or [None] `

**Vorhandene relevante Prüfungen:**

- [test_frontend_runs_tests_then_build_check_from_repository_root](../../../tests/test_dev_cli.py#L153) — Windows-PowerShell-/pwsh-Subprozesse mit instrumentierten Runnern. Assertionstellen: [156](../../../tests/test_dev_cli.py#L156), [157](../../../tests/test_dev_cli.py#L157), [160](../../../tests/test_dev_cli.py#L160).

**Suiteweite Gegenprüfung:** Alle 28 CLI-Vertragsfälle in Windows PowerShell und pwsh sowie reale dev.ps1-Aufrufe für Backend, Frontend/Build, 49 Rulesfälle und vier native Phase2-Fälle liefen im Windows-CI-Job erfolgreich. Windows-GitHubjob 110800783247 auf integriertem Code ffaca3df erfolgreich: https://github.com/sudoleo/consens/actions/runs/36995379657/job/110800783247 . Native Windowsfälle ergänzen die ausdrücklich erhaltenen Linux-Plattformskips. Keine produktiven Credentials oder Cloudwrites.

**Suchspur:** 304 versionierte Test-/Hilfsdateien durchsucht, 1 passende Zeilen. Regexe: ` Windows PowerShell entry point|win32 `. Vollständige Treffer mit Pfad/Zeile in [search-evidence.json](search-evidence.json) unter ` G-026 `.

| Szenario | Erwartung |
|---|---|
| Given | Windowsrunner mit PowerShell und isolierten Tool-Doubles/Dependencies. |
| When | Alle vorhandenen test_dev_cli-Fälle und repräsentative dev.ps1 check-Aufrufe ausführen. |
| Then | Alle 12 Varianten je verfügbarer Windows-Shell erhalten echten Pass/Fail-Status (derzeit 12 oder 24 Fälle bei einer oder zwei Shells); Shellversionen und gesammelte Fallzahl sind dokumentiert. Exitcodes und Pfad-/Argumentweitergabe funktionieren. |

**Zielstellen:** [tests/test_dev_cli.py](../../../tests/test_dev_cli.py), [.github/workflows/tests.yml](../../../.github/workflows/tests.yml)

**Wiederverwenden:** [docs/testing.md](../../testing.md), [dev.ps1](../../../dev.ps1)

**Validierung nach Implementierung:** ` Windows: python -m pytest tests/test_dev_cli.py -q `

**Gezielte Negativkontrolle:** Runner-Exitcode verschlucken; bestehender Fehlerpropagationstest muss rot werden.


<a id="g-027"></a>

## G-027 · Zwei veraltete Emulatorfixtures reparieren

**P1 · broken_test** · Verträge: [WATCH-01](matrix.md#watch-01), [SHARE-01](matrix.md#share-01) · Paket: [WP-01](work-packages.md#wp-01)

**Aktuelle Bewertung:** resolved — Veraltete Watch-/Pendingfixtures und Footerstring ersetzt; heutige Limits, Idempotenz und echte archivierte Drawerknoten geprüft. Keine pauschalen Snapshots oder gelockerten Produktguards.

**Produktbeleg:** [tests/e2e/test_phase2_transactions.py](../../../tests/e2e/test_phase2_transactions.py#L103) — ` pending_ref.set({ `

**Vorhandene relevante Prüfungen:**

- [test_two_workers_cannot_exceed_owner_watch_limit](../../../tests/e2e/test_phase2_transactions.py#L29) — Echte Firestore-SDK-Transaktionen gegen isolierten Demo-Emulator. Assertionstellen: [71](../../../tests/e2e/test_phase2_transactions.py#L71), [78](../../../tests/e2e/test_phase2_transactions.py#L78), [83](../../../tests/e2e/test_phase2_transactions.py#L83).
- [test_two_workers_publish_one_pending_share_and_consume_one_quota](../../../tests/e2e/test_phase2_transactions.py#L97) — Echte Firestore-SDK-Transaktionen gegen isolierten Demo-Emulator. Assertionstellen: [121](../../../tests/e2e/test_phase2_transactions.py#L121), [122](../../../tests/e2e/test_phase2_transactions.py#L122), [127](../../../tests/e2e/test_phase2_transactions.py#L127).
- [test_consensus_result_precedes_model_answers_and_run_block_is_loaded](../../../tests/test_consensus_progress_ui.py#L12) — Statische DOM-/CSS-/JS-Verträge. Assertionstellen: [15](../../../tests/test_consensus_progress_ui.py#L15), [18](../../../tests/test_consensus_progress_ui.py#L18), [19](../../../tests/test_consensus_progress_ui.py#L19), [20](../../../tests/test_consensus_progress_ui.py#L20), [21](../../../tests/test_consensus_progress_ui.py#L21).
- [keeps the contradiction line on the disputed sentence](../../../tests/js/stored-turn-markers.test.mjs#L92) — Echte DOMrenderfunktionen im jsdom. Assertionstellen: [95](../../../tests/js/stored-turn-markers.test.mjs#L95), [96](../../../tests/js/stored-turn-markers.test.mjs#L96).

**Suiteweite Gegenprüfung:** Veraltete Watch-/Pendingfixtures und Footerstring ersetzt; heutige Limits, Idempotenz und echte archivierte Drawerknoten geprüft. Keine pauschalen Snapshots oder gelockerten Produktguards.

**Suchspur:** 304 versionierte Test-/Hilfsdateien durchsucht, 6 passende Zeilen. Regexe: ` is_pro=False|test_two_workers_publish_one_pending_share|test_two_workers_cannot_exceed_owner_watch_limit `. Vollständige Treffer mit Pfad/Zeile in [search-evidence.json](search-evidence.json) unter ` G-027 `.

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

**Aktuelle Bewertung:** resolved — Veraltete Watch-/Pendingfixtures und Footerstring ersetzt; heutige Limits, Idempotenz und echte archivierte Drawerknoten geprüft. Keine pauschalen Snapshots oder gelockerten Produktguards.

**Produktbeleg:** [static/js/consensus-run.js](../../../static/js/consensus-run.js#L411) — ` consensus-tab consensus-evidence-action `

**Vorhandene relevante Prüfungen:**

- [test_archived_turns_use_the_same_drawer_row_as_the_live_answer](../../../tests/test_consensus_progress_ui.py#L326) — Statische DOM-/CSS-/JS-Verträge. Assertionstellen: [337](../../../tests/test_consensus_progress_ui.py#L337), [338](../../../tests/test_consensus_progress_ui.py#L338), [343](../../../tests/test_consensus_progress_ui.py#L343), [344](../../../tests/test_consensus_progress_ui.py#L344), [345](../../../tests/test_consensus_progress_ui.py#L345), [346](../../../tests/test_consensus_progress_ui.py#L346), [347](../../../tests/test_consensus_progress_ui.py#L347), [350](../../../tests/test_consensus_progress_ui.py#L350), [351](../../../tests/test_consensus_progress_ui.py#L351), [353](../../../tests/test_consensus_progress_ui.py#L353), [354](../../../tests/test_consensus_progress_ui.py#L354).
- [test_two_workers_cannot_exceed_owner_watch_limit](../../../tests/e2e/test_phase2_transactions.py#L29) — Echte Firestore-SDK-Transaktionen gegen isolierten Demo-Emulator. Assertionstellen: [71](../../../tests/e2e/test_phase2_transactions.py#L71), [78](../../../tests/e2e/test_phase2_transactions.py#L78), [83](../../../tests/e2e/test_phase2_transactions.py#L83).
- [keeps the contradiction line on the disputed sentence](../../../tests/js/stored-turn-markers.test.mjs#L92) — Echte DOMrenderfunktionen im jsdom. Assertionstellen: [95](../../../tests/js/stored-turn-markers.test.mjs#L95), [96](../../../tests/js/stored-turn-markers.test.mjs#L96).

**Suiteweite Gegenprüfung:** Veraltete Watch-/Pendingfixtures und Footerstring ersetzt; heutige Limits, Idempotenz und echte archivierte Drawerknoten geprüft. Keine pauschalen Snapshots oder gelockerten Produktguards.

**Suchspur:** 304 versionierte Test-/Hilfsdateien durchsucht, 6 passende Zeilen. Regexe: ` test_archived_turns_use_the_same_drawer_row|consensus-evidence-action `. Vollständige Treffer mit Pfad/Zeile in [search-evidence.json](search-evidence.json) unter ` G-028 `.

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

**Aktuelle Bewertung:** resolved — Reportzähler und Gründe verlieren keine erfolgreichen Inkremente. Indexstatus bleibt gemäß R19 unverändert; konkrete ABORTED-Fälle werden vor gesondertem Replay gezählt. SDK-Retryerschöpfung ist kein Erfolg; keine Ausfallfreiheit unter Last zugesagt.

**Produktbeleg:** [tests/e2e/test_phase2_transactions.py](../../../tests/e2e/test_phase2_transactions.py#L167) — ` def test_parallel_reports_never_lose_increments `

**Vorhandene relevante Prüfungen:**

- [test_two_workers_cannot_exceed_owner_watch_limit](../../../tests/e2e/test_phase2_transactions.py#L29) — Echte Firestore-SDK-Transaktionen gegen isolierten Demo-Emulator. Assertionstellen: [71](../../../tests/e2e/test_phase2_transactions.py#L71), [78](../../../tests/e2e/test_phase2_transactions.py#L78), [83](../../../tests/e2e/test_phase2_transactions.py#L83).

**Suiteweite Gegenprüfung:** Reportzähler und Gründe verlieren keine erfolgreichen Inkremente. Indexstatus bleibt gemäß R19 unverändert; konkrete ABORTED-Fälle werden vor gesondertem Replay gezählt. SDK-Retryerschöpfung ist kein Erfolg; keine Ausfallfreiheit unter Last zugesagt.

**Suchspur:** 304 versionierte Test-/Hilfsdateien durchsucht, 2 passende Zeilen. Regexe: ` test_parallel_reports_never_lose_increments `. Vollständige Treffer mit Pfad/Zeile in [search-evidence.json](search-evidence.json) unter ` G-029 `.

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

**Aktuelle Bewertung:** resolved — Sechs Chromiumreisen verbinden originales gebautes AppFirebase, echte HTTP-/Serviceguards und nativen Speicher für J01–J05 sowie echten Bookmark-Speicherfehler. J03 führt den echten Own-Key-Worker aus; J05 prüft Daten erst nach beobachtetem Producer-/Settlementabschluss. Identitäten, Context/Turns, Messbuchungen, Stop/Recover und Kontowechsel werden anhand gespeicherter Daten geprüft. Alle sechs Reisen bestanden auch im vollständigen integrierten CI-Lauf mit 368 Fällen. Externe Identität/Modelle/Mail kontrolliert; historischer V3-Import und gezielt getriebener ownergebundener Watchpfad sind ausdrücklich gekennzeichnet. J05 beobachtet echte Responsebeendigung und Leasefreigabe vor dem nativen Late-Write-Oracle.

**Produktbeleg:** [tests/e2e/conftest.py](../../../tests/e2e/conftest.py#L140) — ` ctx.route("**/static/firebase.js*" `; [tests/e2e/test_phase4_frontend.py](../../../tests/e2e/test_phase4_frontend.py#L160) — ` def _real_firebase_page `

**Vorhandene relevante Prüfungen:**

- [test_j01_saved_consensus_reload_followup_keeps_native_identity_and_context](../../../tests/e2e/test_persisted_journeys.py#L150) — Chromium → gebautes AppFirebase → echte main-Routen → nativer Firestore. Assertionstellen: [155](../../../tests/e2e/test_persisted_journeys.py#L155), [156](../../../tests/e2e/test_persisted_journeys.py#L156), [158](../../../tests/e2e/test_persisted_journeys.py#L158), [160](../../../tests/e2e/test_persisted_journeys.py#L160), [161](../../../tests/e2e/test_persisted_journeys.py#L161), [163](../../../tests/e2e/test_persisted_journeys.py#L163), [164](../../../tests/e2e/test_persisted_journeys.py#L164), [168](../../../tests/e2e/test_persisted_journeys.py#L168), [169](../../../tests/e2e/test_persisted_journeys.py#L169), [172](../../../tests/e2e/test_persisted_journeys.py#L172), [173](../../../tests/e2e/test_persisted_journeys.py#L173), [174](../../../tests/e2e/test_persisted_journeys.py#L174), [175](../../../tests/e2e/test_persisted_journeys.py#L175), [176](../../../tests/e2e/test_persisted_journeys.py#L176), [178](../../../tests/e2e/test_persisted_journeys.py#L178), [179](../../../tests/e2e/test_persisted_journeys.py#L179), [180](../../../tests/e2e/test_persisted_journeys.py#L180), [182](../../../tests/e2e/test_persisted_journeys.py#L182), [183](../../../tests/e2e/test_persisted_journeys.py#L183).
- [stays disabled until both the run and its persistence write finish](../../../tests/js/bookmark-pending-state.test.mjs#L45) — Originale Bookmarkhelfer und Markup im jsdom mit kontrolliertem Speichern. Assertionstellen: [54](../../../tests/js/bookmark-pending-state.test.mjs#L54), [55](../../../tests/js/bookmark-pending-state.test.mjs#L55), [59](../../../tests/js/bookmark-pending-state.test.mjs#L59), [60](../../../tests/js/bookmark-pending-state.test.mjs#L60), [61](../../../tests/js/bookmark-pending-state.test.mjs#L61).

**Suiteweite Gegenprüfung:** Sechs Chromiumreisen verbinden originales gebautes AppFirebase, echte HTTP-/Serviceguards und nativen Speicher für J01–J05 sowie echten Bookmark-Speicherfehler. J03 führt den echten Own-Key-Worker aus; J05 prüft Daten erst nach beobachtetem Producer-/Settlementabschluss. Identitäten, Context/Turns, Messbuchungen, Stop/Recover und Kontowechsel werden anhand gespeicherter Daten geprüft. Alle sechs Reisen bestanden auch im vollständigen integrierten CI-Lauf mit 368 Fällen. Externe Identität/Modelle/Mail kontrolliert; historischer V3-Import und gezielt getriebener ownergebundener Watchpfad sind ausdrücklich gekennzeichnet. J05 beobachtet echte Responsebeendigung und Leasefreigabe vor dem nativen Late-Write-Oracle.

**Suchspur:** 304 versionierte Test-/Hilfsdateien durchsucht, 1307 passende Zeilen. Regexe: ` firebase_stub|_real_firebase_page|route\(|recover_only|bookmark `. Vollständige Treffer mit Pfad/Zeile in [search-evidence.json](search-evidence.json) unter ` G-030 `.

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

**Aktuelle Bewertung:** resolved — Native Duequeries/Claims/Budget/Stale-Fences plus wirkliche Topic-/SEOloops: Erfolgs- und Fehlerabschluss, gespeicherter Benachrichtigungsstatus, Leasefreigabe und Cancellation ohne nächsten Dispatch. Erneuter Scheduler-Tick nach Infrastrukturfehler kann erforderlich sein.

**Produktbeleg:** [app/services/watch_service.py](../../../app/services/watch_service.py#L1478) — ` def list_due_watch_ids( `; [app/services/topics.py](../../../app/services/topics.py#L1103) — ` def claim_topic_run( `; [app/services/topics.py](../../../app/services/topics.py#L1050) — ` def list_due_topic_ids( `; [app/services/seo_weekly_review.py](../../../app/services/seo_weekly_review.py#L1361) — ` async def seo_review_scheduler_loop `

**Vorhandene relevante Prüfungen:**

- [SchedulerSafetyTests::test_claim_transaction_prevents_double_run](../../../tests/test_watch_feature.py#L760) — Große Service-/Scheduler-/Router-/Mailformat-Suite mit DB-/LLM-/Versand-Doubles plus UI-Sourceverträge. Assertionstellen: [767](../../../tests/test_watch_feature.py#L767), [768](../../../tests/test_watch_feature.py#L768), [769](../../../tests/test_watch_feature.py#L769), [770](../../../tests/test_watch_feature.py#L770), [771](../../../tests/test_watch_feature.py#L771).
- [test_default_interval_is_seven_days_and_lease_is_persistent](../../../tests/test_seo_weekly_review.py#L81) — Review-Service mit Repository-/Judge-/Action-Doubles. Assertionstellen: [86](../../../tests/test_seo_weekly_review.py#L86), [87](../../../tests/test_seo_weekly_review.py#L87), [88](../../../tests/test_seo_weekly_review.py#L88), [89](../../../tests/test_seo_weekly_review.py#L89).
- [test_native_due_queries_and_topic_claim_fence](../../../tests/e2e/test_scheduler_transactions.py#L21) — Echte Firestore-SDK-Transaktionen gegen isolierten Demo-Emulator. Assertionstellen: [33](../../../tests/e2e/test_scheduler_transactions.py#L33), [39](../../../tests/e2e/test_scheduler_transactions.py#L39), [42](../../../tests/e2e/test_scheduler_transactions.py#L42), [46](../../../tests/e2e/test_scheduler_transactions.py#L46), [47](../../../tests/e2e/test_scheduler_transactions.py#L47), [48](../../../tests/e2e/test_scheduler_transactions.py#L48).
- [test_supervisor_restarts_crashes_and_keeps_last_success_health](../../../tests/test_background_task_supervision.py#L12) — Async-Supervisor und Startupfunktionen mit Cleanup-Doubles. Assertionstellen: [43](../../../tests/test_background_task_supervision.py#L43), [44](../../../tests/test_background_task_supervision.py#L44), [45](../../../tests/test_background_task_supervision.py#L45), [46](../../../tests/test_background_task_supervision.py#L46), [47](../../../tests/test_background_task_supervision.py#L47).

**Suiteweite Gegenprüfung:** Native Duequeries/Claims/Budget/Stale-Fences plus wirkliche Topic-/SEOloops: Erfolgs- und Fehlerabschluss, gespeicherter Benachrichtigungsstatus, Leasefreigabe und Cancellation ohne nächsten Dispatch. Erneuter Scheduler-Tick nach Infrastrukturfehler kann erforderlich sein.

**Suchspur:** 304 versionierte Test-/Hilfsdateien durchsucht, 23 passende Zeilen. Regexe: ` list_due_watch_ids|list_due_topic_ids|claim_topic_run|acquire_worker_lease|seo_review_scheduler_loop `. Vollständige Treffer mit Pfad/Zeile in [search-evidence.json](search-evidence.json) unter ` G-031 `.

| Szenario | Erwartung |
|---|---|
| Given | Fällige/nichtfällige/pausierte Datensätze, gleiche Slotzeit, konkurrierende Worker, abgelaufene und erneuerte Lease. |
| When | Reale SDK-Queries/Claims und je einen Loop-Tick mit Fakepipeline/Benachrichtigung ausführen; Shutdown gezielt abbrechen. |
| Then | Nur fällige Arbeit, ein Slotgewinner, begrenzte Scans, keine stale Completion, kein weiterer Tick nach Shutdown. DST bleibt gesondert durch vorhandene Zeitfälle geschützt. |

**Zielstellen:** [tests/e2e/test_scheduler_transactions.py](../../../tests/e2e/test_scheduler_transactions.py), [tests/test_background_task_supervision.py](../../../tests/test_background_task_supervision.py)

**Wiederverwenden:** [tests/test_watch_feature.py](../../../tests/test_watch_feature.py), [tests/test_topics_feature.py](../../../tests/test_topics_feature.py), [tests/test_seo_weekly_review.py](../../../tests/test_seo_weekly_review.py)

**Validierung nach Implementierung:** ` RUN_E2E=1 python -m pytest tests/e2e/test_scheduler_transactions.py -q; python -m pytest tests/test_background_task_supervision.py -q `

**Gezielte Negativkontrolle:** Fälligkeits-/Claim-Filter auslassen; Kontrollrows und doppelte Slots müssen entdeckt werden.


<a id="g-032"></a>

## G-032 · Lokale echte Transportgrenzen statt ausschließlich MockTransport

**P2 · missing_integration** · Verträge: [LLM-02](matrix.md#llm-02), [SRC-01](matrix.md#src-01) · Paket: [WP-26](work-packages.md#wp-26)

**Aktuelle Bewertung:** resolved — Bodylimit und vorzeitiger Disconnect, reale TCP-/TLS-Sockets mit Abbruch/Deadline, Host/SNI, Redirectvalidierung und gzip-Budget belegt. Lokale Server, keine Deploymentproxy-/Internetmessung.

**Produktbeleg:** [app/services/llm/provider_runtime.py](../../../app/services/llm/provider_runtime.py#L170) — ` def managed_provider_resource `; [app/services/source_documents.py](../../../app/services/source_documents.py#L92) — ` async def _download( `

**Vorhandene relevante Prüfungen:**

- [test_cancellation_closes_real_idle_provider_socket_without_retry](../../../tests/test_local_transport.py#L64) — Echte lokale TCP-/TLS-Server durch HTTP-/SDK-Adapter. Assertionstellen: [85](../../../tests/test_local_transport.py#L85), [88](../../../tests/test_local_transport.py#L88), [89](../../../tests/test_local_transport.py#L89), [90](../../../tests/test_local_transport.py#L90), [91](../../../tests/test_local_transport.py#L91).
- [test_declared_oversized_body_is_rejected_without_reading_or_parsing](../../../tests/test_request_body_limits.py#L41) — Registrierte Bodylimit-Middleware mit ASGI-Ereignissen. Assertionstellen: [47](../../../tests/test_request_body_limits.py#L47), [48](../../../tests/test_request_body_limits.py#L48).

**Suiteweite Gegenprüfung:** Bodylimit und vorzeitiger Disconnect, reale TCP-/TLS-Sockets mit Abbruch/Deadline, Host/SNI, Redirectvalidierung und gzip-Budget belegt. Lokale Server, keine Deploymentproxy-/Internetmessung.

**Suchspur:** 304 versionierte Test-/Hilfsdateien durchsucht, 12 passende Zeilen. Regexe: ` MockTransport|real_provider_socket_stall|http.server|ThreadingHTTPServer|TCPServer `. Vollständige Treffer mit Pfad/Zeile in [search-evidence.json](search-evidence.json) unter ` G-032 `.

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

**Aktuelle Bewertung:** resolved — Bodylimit und vorzeitiger Disconnect, reale TCP-/TLS-Sockets mit Abbruch/Deadline, Host/SNI, Redirectvalidierung und gzip-Budget belegt. Lokale Server, keine Deploymentproxy-/Internetmessung.

**Produktbeleg:** [app/core/request_limits.py](../../../app/core/request_limits.py#L12) — ` def configured_max_request_body_bytes `; [app/core/request_limits.py](../../../app/core/request_limits.py#L58) — ` except ValueError: `

**Vorhandene relevante Prüfungen:**

- [test_exact_limit_body_is_replayed_once_to_the_application](../../../tests/test_request_body_limits.py#L63) — Registrierte Bodylimit-Middleware mit ASGI-Ereignissen. Assertionstellen: [71](../../../tests/test_request_body_limits.py#L71), [72](../../../tests/test_request_body_limits.py#L72).
- [test_cancellation_closes_real_idle_provider_socket_without_retry](../../../tests/test_local_transport.py#L64) — Echte lokale TCP-/TLS-Server durch HTTP-/SDK-Adapter. Assertionstellen: [85](../../../tests/test_local_transport.py#L85), [88](../../../tests/test_local_transport.py#L88), [89](../../../tests/test_local_transport.py#L89), [90](../../../tests/test_local_transport.py#L90), [91](../../../tests/test_local_transport.py#L91).

**Suiteweite Gegenprüfung:** Bodylimit und vorzeitiger Disconnect, reale TCP-/TLS-Sockets mit Abbruch/Deadline, Host/SNI, Redirectvalidierung und gzip-Budget belegt. Lokale Server, keine Deploymentproxy-/Internetmessung.

**Suchspur:** 304 versionierte Test-/Hilfsdateien durchsucht, 14 passende Zeilen. Regexe: ` MAX_REQUEST_BODY_BYTES|Invalid Content-Length|configured_max_request_body|content-length `. Vollständige Treffer mit Pfad/Zeile in [search-evidence.json](search-evidence.json) unter ` G-033 `.

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

**Aktuelle Bewertung:** resolved — Feedbackhandler/Persistenzguard prüft Auth, Allowlist, Cooldown, Tageslimit und Storefehler. Statistik speichert nur erlaubte Zähler/Metadaten, Fehler bleiben nichtfatal. Bewusst eingegebene Feedbacknachricht darf gespeichert werden; keine produktiven Accounts.

**Produktbeleg:** [app/api/routers/pages.py](../../../app/api/routers/pages.py#L522) — ` def submit_feedback( `; [app/services/differences_stats.py](../../../app/services/differences_stats.py#L181) — ` def record_differences_stats( `

**Vorhandene relevante Prüfungen:**

- [test_feedback_cooldown_and_daily_limit_are_persistent](../../../tests/test_phase5_operations.py#L316) — Gemischt: Services mit DB-/HTTP-Doubles, Thread-/Async-Tests und Deployment-Quelltextverträge. Assertionstellen: [322](../../../tests/test_phase5_operations.py#L322), [328](../../../tests/test_phase5_operations.py#L328).
- [test_feedback_auth_payload_and_persisted_cooldown](../../../tests/test_feedback.py#L23) — Registrierte main.app mit echten Middleware-, Auth-/Owner- und Serviceguards. Assertionstellen: [33](../../../tests/test_feedback.py#L33), [34](../../../tests/test_feedback.py#L34), [36](../../../tests/test_feedback.py#L36), [38](../../../tests/test_feedback.py#L38), [39](../../../tests/test_feedback.py#L39), [40](../../../tests/test_feedback.py#L40), [41](../../../tests/test_feedback.py#L41), [45](../../../tests/test_feedback.py#L45), [46](../../../tests/test_feedback.py#L46), [47](../../../tests/test_feedback.py#L47).

**Suiteweite Gegenprüfung:** Feedbackhandler/Persistenzguard prüft Auth, Allowlist, Cooldown, Tageslimit und Storefehler. Statistik speichert nur erlaubte Zähler/Metadaten, Fehler bleiben nichtfatal. Bewusst eingegebene Feedbacknachricht darf gespeichert werden; keine produktiven Accounts.

**Suchspur:** 304 versionierte Test-/Hilfsdateien durchsucht, 15 passende Zeilen. Regexe: ` /feedback|submit_feedback|record_differences_stats `. Vollständige Treffer mit Pfad/Zeile in [search-evidence.json](search-evidence.json) unter ` G-034 `.

| Szenario | Erwartung |
|---|---|
| Given | Gültiger/ungültiger Login, Tages-/Cooldown-Grenze, Storefehler und sensible Modell-/Fragetexte. |
| When | POST /feedback und realen Statistikwrapper mit äußerem DB-/Notifierdouble ausführen. |
| Then | UID und erlaubte Felder korrekt, Limits vor Write, Fehler redigiert; Statistik zählt erwartete Kategorien ohne Prompt/Antwort/IDs. |

**Zielstellen:** [tests/test_feedback.py](../../../tests/test_feedback.py), [tests/test_differences_stats.py](../../../tests/test_differences_stats.py)

**Wiederverwenden:** [tests/test_phase5_operations.py](../../../tests/test_phase5_operations.py), [tests/test_differences_stats.py](../../../tests/test_differences_stats.py)

**Validierung nach Implementierung:** ` python -m pytest tests/test_feedback.py tests/test_differences_stats.py -q `

**Gezielte Negativkontrolle:** Rohfrage in Statistikrecord einfügen oder UID-Limit umgehen; Negativassertion muss rot werden.


<a id="g-035"></a>

## G-035 · Weitere ausführbare CLI-Einstiege

**P3 · missing_case** · Verträge: [BENCH-02](matrix.md#bench-02), [TOOLS-02](matrix.md#tools-02) · Paket: [WP-28](work-packages.md#wp-28)

**Aktuelle Bewertung:** resolved — Unterstützte sample/experiment-Einstiege validieren Scope/Budget vor Arbeit und durchlaufen echte Runner-/Manifest-/Record-/Resume-/Resultpfade. Keine bezahlten Modelle, keine Livequalitätsmessung.

**Produktbeleg:** [benchmark/run_sample.py](../../../benchmark/run_sample.py#L51) — ` def main( `; [benchmark/run_experiment.py](../../../benchmark/run_experiment.py#L60) — ` def main( `

**Vorhandene relevante Prüfungen:**

- [test_invalid_execution_args_stop_before_dataset_or_provider](../../../tests/test_auxiliary_cli.py#L77) — Echte CLIs und Runner in netzwerkgesperrten Subprozessen. Assertionstellen: [79](../../../tests/test_auxiliary_cli.py#L79), [80](../../../tests/test_auxiliary_cli.py#L80).

**Suiteweite Gegenprüfung:** Unterstützte sample/experiment-Einstiege validieren Scope/Budget vor Arbeit und durchlaufen echte Runner-/Manifest-/Record-/Resume-/Resultpfade. Keine bezahlten Modelle, keine Livequalitätsmessung.

**Suchspur:** 304 versionierte Test-/Hilfsdateien durchsucht, 8 passende Zeilen. Regexe: ` run_sample|run_experiment|evaluate_agent_delegation|evaluate_source_verification|probe_agent_delegation|render_watch_preview `. Vollständige Treffer mit Pfad/Zeile in [search-evidence.json](search-evidence.json) unter ` G-035 `.

| Szenario | Erwartung |
|---|---|
| Given | Temporäre Ausgabeordner, Fakeprovider/-publisher/-renderer und fehlende/ungültige Argumente. |
| When | Jeden weiterhin unterstützten Einstieg direkt als Subprozess aufrufen; benötigte Toolgrenzen ersetzen. |
| Then | Keine unbeabsichtigten Provider-/DB-Aufrufe, korrekte Eingabe-/Budget-/Outputgrenzen und Exitcodes. Falls ein Einstieg veraltet ist, erst Supportstatus entscheiden statt alten Modus blind auszubauen. |

**Zielstellen:** [tests/test_auxiliary_cli.py](../../../tests/test_auxiliary_cli.py)

**Wiederverwenden:** [tests/test_publisher_standalone.py](../../../tests/test_publisher_standalone.py), [tests/test_benchmark_cli.py](../../../tests/test_benchmark_cli.py)

**Validierung nach Implementierung:** ` python -m pytest tests/test_auxiliary_cli.py -q `

**Gezielte Negativkontrolle:** Ungültige CLI-Argumente in tatsächlichen Providerlauf weiterreichen; Netzwerkverbot muss Test stoppen.


<a id="g-036"></a>

## G-036 · Vendorhelper mit Version- und Check-only-Grenzen ausführen

**P2 · missing_case** · Verträge: [BUILD-01](matrix.md#build-01) · Paket: [WP-30](work-packages.md#wp-30)

**Aktuelle Bewertung:** resolved — vendorFrontend auf echtem temporärem Dateisystem, Pins/Lizenzen/Fontbytes/Sortierung, stale Assets, Check-only und unveränderte Mtime belegt. Synthetische Pakete, kein Download oder Bibliotheksqualitätsbeweis.

**Produktbeleg:** [scripts/vendor_frontend.mjs](../../../scripts/vendor_frontend.mjs#L7) — ` export async function vendorFrontend( `; [scripts/vendor_frontend.mjs](../../../scripts/vendor_frontend.mjs#L18) — ` if (version !== pins[name]) `

**Vorhandene relevante Prüfungen:**

- [test_app_vendor_assets_are_local_versioned_and_include_fonts_and_licenses](../../../tests/test_frontend_build.py#L158) — Build-Artefakt-/Fingerprint-Verträge. Assertionstellen: [160](../../../tests/test_frontend_build.py#L160), [162](../../../tests/test_frontend_build.py#L162), [164](../../../tests/test_frontend_build.py#L164), [165](../../../tests/test_frontend_build.py#L165), [169](../../../tests/test_frontend_build.py#L169), [172](../../../tests/test_frontend_build.py#L172).
- [copies every pinned library, license and font byte and retains unrelated old versions](../../../tests/js/vendor-frontend.test.mjs#L25) — Echter Vendorhelper mit temporärem Dateisystem und synthetischen Paketen. Assertionstellen: [29](../../../tests/js/vendor-frontend.test.mjs#L29), [30](../../../tests/js/vendor-frontend.test.mjs#L30), [32](../../../tests/js/vendor-frontend.test.mjs#L32), [34](../../../tests/js/vendor-frontend.test.mjs#L34), [38](../../../tests/js/vendor-frontend.test.mjs#L38).

**Suiteweite Gegenprüfung:** vendorFrontend auf echtem temporärem Dateisystem, Pins/Lizenzen/Fontbytes/Sortierung, stale Assets, Check-only und unveränderte Mtime belegt. Synthetische Pakete, kein Download oder Bibliotheksqualitätsbeweis.

**Suchspur:** 304 versionierte Test-/Hilfsdateien durchsucht, 7 passende Zeilen. Regexe: ` vendorFrontend|vendor_frontend|Unexpected .*version|checkOnly `, ` does not truncate or rewrite unchanged vendor `. Vollständige Treffer mit Pfad/Zeile in [search-evidence.json](search-evidence.json) unter ` G-036 `.

| Szenario | Erwartung |
|---|---|
| Given | Temporärer Projektbaum mit winzigen synthetischen package.json-/Library-/Font-/Lizenzdateien; keine npm-Downloads. |
| When | Realen vendorFrontend(root, checkOnly) in Build- und Prüfmodus mit richtiger/falscher Paketversion sowie fehlenden/geänderten Assets aufrufen. |
| Then | Gepinnte Version wird verlangt, Dateien/Fonts/Lizenzen vollständig und in stabiler Reihenfolge erfasst; Check-only verändert nichts und entdeckt fehlende/stale Bytes; unveränderte Builds schreiben nicht erneut. |

**Zielstellen:** [tests/js/vendor-frontend.test.mjs](../../../tests/js/vendor-frontend.test.mjs)

**Wiederverwenden:** [tests/js/frontend-output.test.mjs](../../../tests/js/frontend-output.test.mjs), [tests/test_frontend_build.py](../../../tests/test_frontend_build.py)

**Validierung nach Implementierung:** ` npm test -- tests/js/vendor-frontend.test.mjs tests/js/frontend-output.test.mjs; python -m pytest tests/test_frontend_build.py -q `

**Gezielte Negativkontrolle:** Versionsvergleich überspringen oder Check-only durch Write ersetzen; Fehler- und Dateisystemassertionen müssen scheitern.


<a id="g-037"></a>

## G-037 · main verwirft HTTPException-Header einschließlich Retry-After

**P1 · observed_behavior_defect** · Verträge: [OPS-02](matrix.md#ops-02), [API-01](matrix.md#api-01), [AGENT-01](matrix.md#agent-01) · Paket: [WP-31](work-packages.md#wp-31)

**Aktuelle Bewertung:** resolved — Reale Agent503/API429 gehen durch main mit sicherem Body und serverseitigem Retry-After, ohne unerlaubte Arbeit; Requestheader werden nicht reflektiert. Firebase-SDK-Authentifizierung und DB ersetzt; externe Modell-, Mail- und Telegramgrenzen kontrolliert. Kein Live-OAuth oder produktiver Versand.

**Produktbeleg:** [main.py](../../../main.py#L242) — ` content={"error": exc.detail} `; [app/api/routers/api_v1.py](../../../app/api/routers/api_v1.py#L173) — ` def enforce_uid_rate_limit( `; [app/api/routers/agent.py](../../../app/api/routers/agent.py#L170) — ` def run_agent( `

**Vorhandene relevante Prüfungen:**

- [test_local_capacity_rejects_before_creating_a_turn_and_preserves_replay](../../../tests/test_agent_capacity.py#L104) — Agentkapazität, Routerstream und lokale Worker mit kontrolliertem Loop. Assertionstellen: [113](../../../tests/test_agent_capacity.py#L113), [114](../../../tests/test_agent_capacity.py#L114), [115](../../../tests/test_agent_capacity.py#L115), [118](../../../tests/test_agent_capacity.py#L118), [121](../../../tests/test_agent_capacity.py#L121), [124](../../../tests/test_agent_capacity.py#L124).
- [ClientIpKeyTests::test_uid_limiter_cannot_be_bypassed_with_another_key](../../../tests/test_rate_limit.py#L74) — Rate-Key-/UID-Limiter-Funktionen. Assertionstellen: [77](../../../tests/test_rate_limit.py#L77).
- [test_rate_limit_blocks_immediate_resubmission_without_another_paid_claim](../../../tests/test_agent_search.py#L121) — Usage-/Cooldownlogik, Agent-API und geskripteter Transport. Assertionstellen: [137](../../../tests/test_agent_search.py#L137), [139](../../../tests/test_agent_search.py#L139), [140](../../../tests/test_agent_search.py#L140), [141](../../../tests/test_agent_search.py#L141).
- [test_detail_pages_are_owner_bound_and_never_start_provider](../../../tests/test_agent_http_contract.py#L56) — Registrierte main.app mit echten Middleware-, Auth-/Owner- und Serviceguards. Assertionstellen: [67](../../../tests/test_agent_http_contract.py#L67), [68](../../../tests/test_agent_http_contract.py#L68), [70](../../../tests/test_agent_http_contract.py#L70), [71](../../../tests/test_agent_http_contract.py#L71), [72](../../../tests/test_agent_http_contract.py#L72), [77](../../../tests/test_agent_http_contract.py#L77), [83](../../../tests/test_agent_http_contract.py#L83), [88](../../../tests/test_agent_http_contract.py#L88), [94](../../../tests/test_agent_http_contract.py#L94).

**Suiteweite Gegenprüfung:** Reale Agent503/API429 gehen durch main mit sicherem Body und serverseitigem Retry-After, ohne unerlaubte Arbeit; Requestheader werden nicht reflektiert. Firebase-SDK-Authentifizierung und DB ersetzt; externe Modell-, Mail- und Telegramgrenzen kontrolliert. Kein Live-OAuth oder produktiver Versand.

**Suchspur:** 304 versionierte Test-/Hilfsdateien durchsucht, 44 passende Zeilen. Regexe: ` Retry.After|enforce_uid_rate_limit|handle_http_exception `, ` TestClient\(main\.app\) `. Vollständige Treffer mit Pfad/Zeile in [search-evidence.json](search-evidence.json) unter ` G-037 `.

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

**Aktuelle Bewertung:** resolved — Datenverlust bei Limitabsenkung behoben. Native Revision/Lease/Tombstone/Commitfehler und volle echte main-HTTP-Matrix mit Auth/Tier/Owner/Expiry/Konflikt/Repeat ohne Providerarbeit belegt. Synthetische Profile; keine Live-Modellqualität.

**Produktbeleg:** [app/services/memory_edit.py](../../../app/services/memory_edit.py#L710) — ` def undo( `

**Vorhandene relevante Prüfungen:**

- [test_replace_is_revision_checked_and_undo_restores_exact_content](../../../tests/test_memory_edit.py#L178) — Memory-Repository mit Transaktionsdouble. Assertionstellen: [189](../../../tests/test_memory_edit.py#L189), [204](../../../tests/test_memory_edit.py#L204), [208](../../../tests/test_memory_edit.py#L208), [209](../../../tests/test_memory_edit.py#L209), [220](../../../tests/test_memory_edit.py#L220), [221](../../../tests/test_memory_edit.py#L221), [222](../../../tests/test_memory_edit.py#L222), [223](../../../tests/test_memory_edit.py#L223).
- [test_native_patch_and_manual_save_have_one_revision_winner](../../../tests/e2e/test_memory_edit_transactions.py#L44) — Echte Firestore-SDK-Transaktionen gegen isolierten Demo-Emulator und echter main-HTTP-Adapter. Assertionstellen: [51](../../../tests/e2e/test_memory_edit_transactions.py#L51), [68](../../../tests/e2e/test_memory_edit_transactions.py#L68), [70](../../../tests/e2e/test_memory_edit_transactions.py#L70), [71](../../../tests/e2e/test_memory_edit_transactions.py#L71).
- [test_main_undo_errors_preserve_all_state_and_never_call_provider](../../../tests/test_memory_http_contract.py#L75) — Registrierte main.app mit echten Middleware-, Auth-/Owner- und Serviceguards. Assertionstellen: [109](../../../tests/test_memory_http_contract.py#L109), [110](../../../tests/test_memory_http_contract.py#L110), [112](../../../tests/test_memory_http_contract.py#L112), [113](../../../tests/test_memory_http_contract.py#L113), [114](../../../tests/test_memory_http_contract.py#L114), [115](../../../tests/test_memory_http_contract.py#L115), [116](../../../tests/test_memory_http_contract.py#L116).

**Suiteweite Gegenprüfung:** Datenverlust bei Limitabsenkung behoben. Native Revision/Lease/Tombstone/Commitfehler und volle echte main-HTTP-Matrix mit Auth/Tier/Owner/Expiry/Konflikt/Repeat ohne Providerarbeit belegt. Synthetische Profile; keine Live-Modellqualität.

**Suchspur:** 304 versionierte Test-/Hilfsdateien durchsucht, 46 passende Zeilen. Regexe: ` \.undo\(|/memory/undo `, ` over.*limit|memory_limit `. Vollständige Treffer mit Pfad/Zeile in [search-evidence.json](search-evidence.json) unter ` G-038 `.

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

**Aktuelle Bewertung:** resolved — Agentdetail/Stop binden UID, Chat und Turn, paginieren vollständig und prüfen Parameter/Pro-/Admin-/Tierausfall. Wiederholter Stop sperrt nur Zielturn und späten Publish; Antworten private/no-store. Firebase-SDK-Authentifizierung und DB ersetzt; externe Modell-, Mail- und Telegramgrenzen kontrolliert. Kein Live-OAuth oder produktiver Versand.

**Produktbeleg:** [app/api/routers/agent.py](../../../app/api/routers/agent.py#L428) — ` def agent_details( `; [app/api/routers/agent.py](../../../app/api/routers/agent.py#L448) — ` def stop_agent_run( `

**Vorhandene relevante Prüfungen:**

- [test_delegation_endpoints_are_owner_bound_and_read_only](../../../tests/test_agent_delegation.py#L265) — Echte Workerthreads/Mailboxen mit Store- und Provider-Doubles. Assertionstellen: [270](../../../tests/test_agent_delegation.py#L270), [271](../../../tests/test_agent_delegation.py#L271), [272](../../../tests/test_agent_delegation.py#L272), [273](../../../tests/test_agent_delegation.py#L273), [274](../../../tests/test_agent_delegation.py#L274), [275](../../../tests/test_agent_delegation.py#L275).
- [test_detail_pages_are_owner_bound_and_never_start_provider](../../../tests/test_agent_http_contract.py#L56) — Registrierte main.app mit echten Middleware-, Auth-/Owner- und Serviceguards. Assertionstellen: [67](../../../tests/test_agent_http_contract.py#L67), [68](../../../tests/test_agent_http_contract.py#L68), [70](../../../tests/test_agent_http_contract.py#L70), [71](../../../tests/test_agent_http_contract.py#L71), [72](../../../tests/test_agent_http_contract.py#L72), [77](../../../tests/test_agent_http_contract.py#L77), [83](../../../tests/test_agent_http_contract.py#L83), [88](../../../tests/test_agent_http_contract.py#L88), [94](../../../tests/test_agent_http_contract.py#L94).

**Suiteweite Gegenprüfung:** Agentdetail/Stop binden UID, Chat und Turn, paginieren vollständig und prüfen Parameter/Pro-/Admin-/Tierausfall. Wiederholter Stop sperrt nur Zielturn und späten Publish; Antworten private/no-store. Firebase-SDK-Authentifizierung und DB ersetzt; externe Modell-, Mail- und Telegramgrenzen kontrolliert. Kein Live-OAuth oder produktiver Versand.

**Suchspur:** 304 versionierte Test-/Hilfsdateien durchsucht, 23 passende Zeilen. Regexe: ` /agents|/stop `, ` agent_details|stop_agent_run|stop_turn `. Vollständige Treffer mit Pfad/Zeile in [search-evidence.json](search-evidence.json) unter ` G-039 `.

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

**Aktuelle Bewertung:** resolved — Unabhängiger nativer Writer B bleibt trotz Aktivierungsfehler/Rollback A erhalten, auch ohne Vorgänger. Zusätzlich abgewiesener nativer Rollback-RPC: ursprünglicher Fehler/Diagnose ehrlich sichtbar, DB nicht fälschlich restored, lokaler Snapshot bewahrt. Keine gemeinsame Atomizität zwischen Firestore und mehreren Serverruntimes.

**Produktbeleg:** [app/api/routers/admin.py](../../../app/api/routers/admin.py#L59) — ` def _persist_and_activate_models( `

**Vorhandene relevante Prüfungen:**

- [ModelConfigurationTests::test_admin_update_restores_persisted_document_on_activation_error](../../../tests/test_model_configuration.py#L147) — Modellkonfiguration mit Repository-/Aktivierungsdoubles und statischen UIverträgen. Assertionstellen: [160](../../../tests/test_model_configuration.py#L160), [164](../../../tests/test_model_configuration.py#L164), [165](../../../tests/test_model_configuration.py#L165), [169](../../../tests/test_model_configuration.py#L169), [170](../../../tests/test_model_configuration.py#L170).
- [test_native_failed_model_activation_preserves_other_writer](../../../tests/e2e/test_model_configuration_transactions.py#L11) — Echte Firestore-SDK-Transaktionen gegen isolierten Demo-Emulator mit zwei durch Events koordinierten Writern. Assertionstellen: [20](../../../tests/e2e/test_model_configuration_transactions.py#L20), [24](../../../tests/e2e/test_model_configuration_transactions.py#L24), [27](../../../tests/e2e/test_model_configuration_transactions.py#L27), [34](../../../tests/e2e/test_model_configuration_transactions.py#L34), [43](../../../tests/e2e/test_model_configuration_transactions.py#L43), [44](../../../tests/e2e/test_model_configuration_transactions.py#L44).

**Suiteweite Gegenprüfung:** Unabhängiger nativer Writer B bleibt trotz Aktivierungsfehler/Rollback A erhalten, auch ohne Vorgänger. Zusätzlich abgewiesener nativer Rollback-RPC: ursprünglicher Fehler/Diagnose ehrlich sichtbar, DB nicht fälschlich restored, lokaler Snapshot bewahrt. Keine gemeinsame Atomizität zwischen Firestore und mehreren Serverruntimes.

**Suchspur:** 304 versionierte Test-/Hilfsdateien durchsucht, 23 passende Zeilen. Regexe: ` persist_and_activate_models|activation_error `, ` rollback|restores_persisted `. Vollständige Treffer mit Pfad/Zeile in [search-evidence.json](search-evidence.json) unter ` G-040 `.

| Szenario | Erwartung |
|---|---|
| Given | Zwei Konfigwriter; A liest initial und schreibt A, B schreibt B vor As Aktivierungsfehler. |
| When | As Rollback nach Bs erfolgreichem Write auslösen; zusätzlich initial fehlendes Dokument und Rollback-RPC-Ausfall. |
| Then | Rollback löscht/überschreibt nur die eigene unveränderte Version mit nativer Precondition/Transaktion. B bleibt erhalten, auch wenn initial nichts existierte. Lokale Runtime bleibt beim eigenen letzten gültigen Stand; Fehler/Recoveryzustand ist ehrlich sichtbar. Keine globale DB-/Runtime-Atomizität behaupten. |

**Zielstellen:** [tests/test_model_configuration.py](../../../tests/test_model_configuration.py), [tests/e2e/test_model_configuration_transactions.py](../../../tests/e2e/test_model_configuration_transactions.py)

**Wiederverwenden:** [tests/test_model_configuration.py](../../../tests/test_model_configuration.py), [tests/e2e/test_prompt_config_transactions.py](../../../tests/e2e/test_prompt_config_transactions.py)

**Validierung nach Implementierung:** ` python -m pytest tests/test_model_configuration.py tests/test_reasoning_policy.py tests/test_source_model_configuration.py -q; zusätzlich gezielter Firestore-Emulatorfall `

**Gezielte Negativkontrolle:** Bedingung aus Rollback entfernen: B-Erhalt muss rot werden; nur final==initial zu prüfen würde den Fehler festschreiben.


<a id="g-041"></a>

## G-041 · Topic-Admingrenze prüft Revocation nicht und verliert Rollen-503

**P1 · observed_behavior_defect** · Verträge: [AUTH-02](matrix.md#auth-02), [TOPIC-01](matrix.md#topic-01) · Paket: [WP-16](work-packages.md#wp-16)

**Aktuelle Bewertung:** resolved — Alle Topicadminmethoden prüfen Revocation und projizieren Tierausfall503. Hub/Sitemap unterscheiden Status/noindex korrekt. Neutraler Follow, tatsächlicher Confirm-/Unsubscribe-Link und Escaping ausgeführt. Firebase-SDK-Authentifizierung und DB ersetzt; externe Modell-, Mail- und Telegramgrenzen kontrolliert. Kein Live-OAuth oder produktiver Versand.

**Produktbeleg:** [app/api/routers/topics.py](../../../app/api/routers/topics.py#L138) — ` def _require_admin( `; [app/api/routers/admin.py](../../../app/api/routers/admin.py#L187) — ` def _require_admin( `; [app/core/security.py](../../../app/core/security.py#L257) — ` check_revoked: bool = False `

**Vorhandene relevante Prüfungen:**

- [test_admin_boundary_checks_revocation_and_maps_tier_outage_to_503](../../../tests/test_auth_revocation.py#L52) — Security-Funktionen mit Auth-/Datenbank-Doubles. Assertionstellen: [65](../../../tests/test_auth_revocation.py#L65), [68](../../../tests/test_auth_revocation.py#L68), [69](../../../tests/test_auth_revocation.py#L69).
- [test_admin_topic_api_creates_updates_and_versions_without_share_data](../../../tests/test_topics_feature.py#L1137) — Große Service-/Router-/SSR-Suite mit FakeFirestore; einzelner echter SDK-Queryaufbau mit RPC-Mock. Assertionstellen: [1149](../../../tests/test_topics_feature.py#L1149), [1154](../../../tests/test_topics_feature.py#L1154), [1155](../../../tests/test_topics_feature.py#L1155), [1157](../../../tests/test_topics_feature.py#L1157), [1158](../../../tests/test_topics_feature.py#L1158), [1161](../../../tests/test_topics_feature.py#L1161), [1162](../../../tests/test_topics_feature.py#L1162), [1163](../../../tests/test_topics_feature.py#L1163).
- [test_every_topic_admin_method_enforces_real_policy_before_service](../../../tests/test_http_adapter_auth.py#L29) — Registrierte main.app mit echten Middleware-, Auth-/Owner- und Serviceguards. Assertionstellen: [43](../../../tests/test_http_adapter_auth.py#L43), [44](../../../tests/test_http_adapter_auth.py#L44), [45](../../../tests/test_http_adapter_auth.py#L45), [47](../../../tests/test_http_adapter_auth.py#L47).
- [test_hub_and_sitemap_distinguish_noindex_from_archive_or_unpublished](../../../tests/test_topic_public_http.py#L34) — Registrierte main.app mit echten Middleware-, Auth-/Owner- und Serviceguards. Assertionstellen: [52](../../../tests/test_topic_public_http.py#L52), [54](../../../tests/test_topic_public_http.py#L54), [56](../../../tests/test_topic_public_http.py#L56), [58](../../../tests/test_topic_public_http.py#L58), [59](../../../tests/test_topic_public_http.py#L59), [61](../../../tests/test_topic_public_http.py#L61).

**Suiteweite Gegenprüfung:** Alle Topicadminmethoden prüfen Revocation und projizieren Tierausfall503. Hub/Sitemap unterscheiden Status/noindex korrekt. Neutraler Follow, tatsächlicher Confirm-/Unsubscribe-Link und Escaping ausgeführt. Firebase-SDK-Authentifizierung und DB ersetzt; externe Modell-, Mail- und Telegramgrenzen kontrolliert. Kein Live-OAuth oder produktiver Versand.

**Suchspur:** 304 versionierte Test-/Hilfsdateien durchsucht, 51 passende Zeilen. Regexe: ` _require_admin|check_revoked|TierStatusUnavailable `, ` /api/admin/topics `. Vollständige Treffer mit Pfad/Zeile in [search-evidence.json](search-evidence.json) unter ` G-041 `.

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

**Aktuelle Bewertung:** resolved — HTTP200-Fehlerobjekte und ungültige Responseformen bleiben sichere Fehler bis Record/Resume/Statistik. Gültiger Text ohne Auswahl bleibt Enthaltung, private Fehlermeldungen werden entfernt. Keine Häufigkeitsmessung produktiver Providerfehler.

**Produktbeleg:** [benchmark/transport.py](../../../benchmark/transport.py#L151) — ` def execute( `; [benchmark/runner.py](../../../benchmark/runner.py#L70) — ` def index_existing( `; [benchmark/runner.py](../../../benchmark/runner.py#L503) — ` def _make_cell_record( `

**Vorhandene relevante Prüfungen:**

- [test_malformed_response_is_structured](../../../tests/test_benchmark_transport.py#L111) — Benchmarktransport mit HTTP-Doubles. Assertionstellen: [114](../../../tests/test_benchmark_transport.py#L114), [115](../../../tests/test_benchmark_transport.py#L115), [116](../../../tests/test_benchmark_transport.py#L116).
- [test_protocol_failures_are_not_successful_abstentions](../../../tests/test_benchmark_protocol.py#L46) — Transport-, Record-, Resume- und Statistikpipeline mit HTTP-Response-Double. Assertionstellen: [49](../../../tests/test_benchmark_protocol.py#L49), [50](../../../tests/test_benchmark_protocol.py#L50), [51](../../../tests/test_benchmark_protocol.py#L51), [52](../../../tests/test_benchmark_protocol.py#L52), [54](../../../tests/test_benchmark_protocol.py#L54), [55](../../../tests/test_benchmark_protocol.py#L55), [56](../../../tests/test_benchmark_protocol.py#L56), [59](../../../tests/test_benchmark_protocol.py#L59), [60](../../../tests/test_benchmark_protocol.py#L60), [61](../../../tests/test_benchmark_protocol.py#L61), [63](../../../tests/test_benchmark_protocol.py#L63), [64](../../../tests/test_benchmark_protocol.py#L64).

**Suiteweite Gegenprüfung:** HTTP200-Fehlerobjekte und ungültige Responseformen bleiben sichere Fehler bis Record/Resume/Statistik. Gültiger Text ohne Auswahl bleibt Enthaltung, private Fehlermeldungen werden entfernt. Keine Häufigkeitsmessung produktiver Providerfehler.

**Suchspur:** 304 versionierte Test-/Hilfsdateien durchsucht, 44 passende Zeilen. Regexe: ` malformed_response|provider_http_error|response_parse_failed `, ` index_existing|retry_failed|abstain `. Vollständige Treffer mit Pfad/Zeile in [search-evidence.json](search-evidence.json) unter ` G-042 `.

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

**Aktuelle Bewertung:** resolved — Gmail/Kalenderclaims nativ, maximal ein Writeversuch, Unknownreplay und Lese-Reconciliation sowie Owner/Revision/Approval/Hash/Supersession geprüft. Google-HTTP an Wiregrenze ersetzt; keine echte Zustellgarantie.

**Produktbeleg:** [app/services/agent_actions.py](../../../app/services/agent_actions.py#L142) — ` def confirm( `

**Vorhandene relevante Prüfungen:**

- [test_prepare_does_not_write_and_confirmation_is_exact_once](../../../tests/test_agent_calendar.py#L42) — Kalender-Service und HTTP-Adapter mit Fake-DB und Google-Transport. Assertionstellen: [45](../../../tests/test_agent_calendar.py#L45), [46](../../../tests/test_agent_calendar.py#L46), [48](../../../tests/test_agent_calendar.py#L48), [49](../../../tests/test_agent_calendar.py#L49), [51](../../../tests/test_agent_calendar.py#L51), [55](../../../tests/test_agent_calendar.py#L55), [56](../../../tests/test_agent_calendar.py#L56), [57](../../../tests/test_agent_calendar.py#L57), [58](../../../tests/test_agent_calendar.py#L58), [59](../../../tests/test_agent_calendar.py#L59).
- [test_separate_oauth_read_and_send_scopes_and_local_draft_before_send](../../../tests/test_agent_gmail.py#L50) — Gmail-/Aktionsdienste und echter Agentloop mit Transport-/DB-Doubles. Assertionstellen: [54](../../../tests/test_agent_gmail.py#L54), [55](../../../tests/test_agent_gmail.py#L55), [58](../../../tests/test_agent_gmail.py#L58), [59](../../../tests/test_agent_gmail.py#L59), [60](../../../tests/test_agent_gmail.py#L60), [61](../../../tests/test_agent_gmail.py#L61).
- [test_native_google_confirmation_one_attempt_and_unknown_never_retries](../../../tests/e2e/test_google_action_transactions.py#L13) — Echte Firestore-SDK-Transaktionen gegen isolierten Demo-Emulator mit echtem Aktions- und HTTP-Payloadpfad. Assertionstellen: [45](../../../tests/e2e/test_google_action_transactions.py#L45), [46](../../../tests/e2e/test_google_action_transactions.py#L46), [47](../../../tests/e2e/test_google_action_transactions.py#L47), [48](../../../tests/e2e/test_google_action_transactions.py#L48), [49](../../../tests/e2e/test_google_action_transactions.py#L49), [51](../../../tests/e2e/test_google_action_transactions.py#L51), [53](../../../tests/e2e/test_google_action_transactions.py#L53).

**Suiteweite Gegenprüfung:** Gmail/Kalenderclaims nativ, maximal ein Writeversuch, Unknownreplay und Lese-Reconciliation sowie Owner/Revision/Approval/Hash/Supersession geprüft. Google-HTTP an Wiregrenze ersetzt; keine echte Zustellgarantie.

**Suchspur:** 304 versionierte Test-/Hilfsdateien durchsucht, 244 passende Zeilen. Regexe: ` confirm|reconcile|expected_hash|agent_actions `. Vollständige Treffer mit Pfad/Zeile in [search-evidence.json](search-evidence.json) unter ` G-043 `.

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

**Aktuelle Bewertung:** resolved — Native Dateiquote, strenger privater Cloudadapter, Fehler-/Kaskadenretry und echter Dokumentrenderer mit immutable Vorversionen. Zusätzlich Firestore-Fehler 400 für Tabellen durch verlustfreien Codec behoben. Bucketdouble prüft Adaptervertrag, keine produktive IAM.

**Produktbeleg:** [app/services/agent_files.py](../../../app/services/agent_files.py#L136) — ` class AgentFiles `

**Vorhandene relevante Prüfungen:**

- [test_real_extraction_storage_download_and_owner_isolation](../../../tests/test_agent_files.py#L28) — Datei-Service, echte Extraktion und isolierte HTTP-Adapter. Assertionstellen: [32](../../../tests/test_agent_files.py#L32), [33](../../../tests/test_agent_files.py#L33), [34](../../../tests/test_agent_files.py#L34), [35](../../../tests/test_agent_files.py#L35), [38](../../../tests/test_agent_files.py#L38), [39](../../../tests/test_agent_files.py#L39).
- [test_real_docx_pdf_version_and_saved_provenance](../../../tests/test_agent_documents.py#L24) — Dokument-Service mit echten DOCX-/PDF-Renderern und temporärem Speicher. Assertionstellen: [30](../../../tests/test_agent_documents.py#L30), [33](../../../tests/test_agent_documents.py#L33), [37](../../../tests/test_agent_documents.py#L37), [40](../../../tests/test_agent_documents.py#L40), [42](../../../tests/test_agent_documents.py#L42), [43](../../../tests/test_agent_documents.py#L43), [45](../../../tests/test_agent_documents.py#L45), [48](../../../tests/test_agent_documents.py#L48), [51](../../../tests/test_agent_documents.py#L51), [52](../../../tests/test_agent_documents.py#L52), [53](../../../tests/test_agent_documents.py#L53), [54](../../../tests/test_agent_documents.py#L54), [55](../../../tests/test_agent_documents.py#L55).
- [test_native_cloud_upload_quota_foreign_download_and_delete_retry](../../../tests/e2e/test_file_storage_transactions.py#L50) — Echte Firestore-SDK-Transaktionen gegen isolierten Demo-Emulator, echter Cloudadapter und DOCX-/PDF-Renderer. Assertionstellen: [62](../../../tests/e2e/test_file_storage_transactions.py#L62), [63](../../../tests/e2e/test_file_storage_transactions.py#L63), [64](../../../tests/e2e/test_file_storage_transactions.py#L64), [66](../../../tests/e2e/test_file_storage_transactions.py#L66), [68](../../../tests/e2e/test_file_storage_transactions.py#L68), [70](../../../tests/e2e/test_file_storage_transactions.py#L70), [72](../../../tests/e2e/test_file_storage_transactions.py#L72), [73](../../../tests/e2e/test_file_storage_transactions.py#L73), [76](../../../tests/e2e/test_file_storage_transactions.py#L76), [77](../../../tests/e2e/test_file_storage_transactions.py#L77).

**Suiteweite Gegenprüfung:** Native Dateiquote, strenger privater Cloudadapter, Fehler-/Kaskadenretry und echter Dokumentrenderer mit immutable Vorversionen. Zusätzlich Firestore-Fehler 400 für Tabellen durch verlustfreien Codec behoben. Bucketdouble prüft Adaptervertrag, keine produktive IAM.

**Suchspur:** 304 versionierte Test-/Hilfsdateien durchsucht, 20 passende Zeilen. Regexe: ` AgentFiles|ObjectStorage|AGENT_FILES_BUCKET|storage.Client `. Vollständige Treffer mit Pfad/Zeile in [search-evidence.json](search-evidence.json) unter ` G-044 `.

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

**Aktuelle Bewertung:** resolved — Resultat/History/Outbox atomar; Vorcommitfehler, neuer Worker, stale Ack, Probe-Tagesbudget/Konfig/Einmalclaim und Tombstone belegt. Externe Benachrichtigungen bleiben at-least-once.

**Produktbeleg:** [app/services/notification_outbox.py](../../../app/services/notification_outbox.py#L379) — ` def claim( `

**Vorhandene relevante Prüfungen:**

- [test_pause_then_stale_failure_keeps_watch_paused_and_counter_consistent](../../../tests/test_watch_review_regressions.py#L86) — Scheduler-/Outbox-/Deliverydienste mit Fake-DB und Versand-Doubles. Assertionstellen: [88](../../../tests/test_watch_review_regressions.py#L88), [90](../../../tests/test_watch_review_regressions.py#L90), [91](../../../tests/test_watch_review_regressions.py#L91), [93](../../../tests/test_watch_review_regressions.py#L93), [96](../../../tests/test_watch_review_regressions.py#L96), [97](../../../tests/test_watch_review_regressions.py#L97).
- [test_new_evidence_must_cite_a_source_the_standing_answer_did_not_have](../../../tests/test_watch_evidence_model.py#L31) — Evidence-/Probe-/Ledgerdienste mit Fake-DB. Assertionstellen: [36](../../../tests/test_watch_evidence_model.py#L36), [37](../../../tests/test_watch_evidence_model.py#L37), [45](../../../tests/test_watch_evidence_model.py#L45), [46](../../../tests/test_watch_evidence_model.py#L46).
- [test_native_outbox_claim_takeover_rejects_stale_ack_and_terminal_replay](../../../tests/e2e/test_watch_delivery_transactions.py#L8) — Echte Firestore-SDK-Transaktionen gegen isolierten Demo-Emulator. Assertionstellen: [15](../../../tests/e2e/test_watch_delivery_transactions.py#L15), [20](../../../tests/e2e/test_watch_delivery_transactions.py#L20), [21](../../../tests/e2e/test_watch_delivery_transactions.py#L21), [22](../../../tests/e2e/test_watch_delivery_transactions.py#L22), [23](../../../tests/e2e/test_watch_delivery_transactions.py#L23), [24](../../../tests/e2e/test_watch_delivery_transactions.py#L24), [25](../../../tests/e2e/test_watch_delivery_transactions.py#L25).

**Suiteweite Gegenprüfung:** Resultat/History/Outbox atomar; Vorcommitfehler, neuer Worker, stale Ack, Probe-Tagesbudget/Konfig/Einmalclaim und Tombstone belegt. Externe Benachrichtigungen bleiben at-least-once.

**Suchspur:** 304 versionierte Test-/Hilfsdateien durchsucht, 61 passende Zeilen. Regexe: ` notification_outbox|watch_probe|lease_owner `. Vollständige Treffer mit Pfad/Zeile in [search-evidence.json](search-evidence.json) unter ` G-045 `.

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

**Aktuelle Bewertung:** resolved — Manifestzeit-/DST-Drift, UTF8-Subprozess, Fixture-/UI-Erwartungen, Resize-Scrollsprung und echter Composer-Autosizefehler nach CSS-Breitenanimation behoben. Playwright/native Scheduler teilen keinen Eventloop mehr; konkrete SDK-Aborted-Aufrufe werden vor einem gesonderten nächsten Tick als Fehlversuche dokumentiert. Vollständig integriert: 3303 Python-, 705 JavaScript-, 368 E2E- und 49 Rulesfälle bestanden. Grüne integrierte Runner gelten für ffaca3df. Keine neue Branch-Coverage oder flächige visuelle Prüfung; alte Fehlerbelege und alternative Plattformskips bleiben sichtbar.

**Produktbeleg:** [tests/test_benchmark_budget.py](../../../tests/test_benchmark_budget.py#L73) — ` def test_resume_of_a_finished_pilot_does_not_pay_for_audits_again `

**Vorhandene relevante Prüfungen:**

- [BenchmarkBudgetTests::test_tight_budget_stops_before_the_first_uncovered_audit_call](../../../tests/test_benchmark_budget.py#L53) — Benchmarkrunner mit deterministischem Transport und temporären Artefakten. Assertionstellen: [60](../../../tests/test_benchmark_budget.py#L60), [65](../../../tests/test_benchmark_budget.py#L65), [66](../../../tests/test_benchmark_budget.py#L66), [67](../../../tests/test_benchmark_budget.py#L67), [68](../../../tests/test_benchmark_budget.py#L68), [69](../../../tests/test_benchmark_budget.py#L69), [70](../../../tests/test_benchmark_budget.py#L70), [71](../../../tests/test_benchmark_budget.py#L71).
- [PublisherStandaloneTests::test_cli_reaches_configuration_validation_without_packages](../../../tests/test_publisher_standalone.py#L29) — Isolierter Python-Subprozess ohne optionale Pakete oder externe Services. Assertionstellen: [38](../../../tests/test_publisher_standalone.py#L38), [39](../../../tests/test_publisher_standalone.py#L39), [40](../../../tests/test_publisher_standalone.py#L40).
- [test_resume_across_seconds_days_and_dst_keeps_manifest](../../../tests/test_benchmark_manifest_clock.py#L15) — Echter Manifestvergleich mit kontrollierter Uhr. Assertionstellen: [22](../../../tests/test_benchmark_manifest_clock.py#L22).
- [shrinks a wrapped placeholder when the actual width finishes changing without another viewport event](../../../tests/js/composer-autosize.test.mjs#L31) — Originales Autosize-Modul in jsdom mit kontrollierter Geometrie und Frames. Assertionstellen: [34](../../../tests/js/composer-autosize.test.mjs#L34), [35](../../../tests/js/composer-autosize.test.mjs#L35), [37](../../../tests/js/composer-autosize.test.mjs#L37), [39](../../../tests/js/composer-autosize.test.mjs#L39), [40](../../../tests/js/composer-autosize.test.mjs#L40).
- [test_sidebar_navigation_is_self_contained_and_guest_login_is_top_only](../../../tests/test_navigation_settings_ui.py#L13) — Quelltextverträge. Assertionstellen: [21](../../../tests/test_navigation_settings_ui.py#L21), [22](../../../tests/test_navigation_settings_ui.py#L22), [23](../../../tests/test_navigation_settings_ui.py#L23), [24](../../../tests/test_navigation_settings_ui.py#L24), [25](../../../tests/test_navigation_settings_ui.py#L25), [26](../../../tests/test_navigation_settings_ui.py#L26), [27](../../../tests/test_navigation_settings_ui.py#L27), [28](../../../tests/test_navigation_settings_ui.py#L28), [29](../../../tests/test_navigation_settings_ui.py#L29), [30](../../../tests/test_navigation_settings_ui.py#L30), [31](../../../tests/test_navigation_settings_ui.py#L31), [32](../../../tests/test_navigation_settings_ui.py#L32), [33](../../../tests/test_navigation_settings_ui.py#L33), [34](../../../tests/test_navigation_settings_ui.py#L34), [35](../../../tests/test_navigation_settings_ui.py#L35), [36](../../../tests/test_navigation_settings_ui.py#L36), [37](../../../tests/test_navigation_settings_ui.py#L37), [38](../../../tests/test_navigation_settings_ui.py#L38), [39](../../../tests/test_navigation_settings_ui.py#L39), [40](../../../tests/test_navigation_settings_ui.py#L40), [41](../../../tests/test_navigation_settings_ui.py#L41), [42](../../../tests/test_navigation_settings_ui.py#L42), [43](../../../tests/test_navigation_settings_ui.py#L43), [44](../../../tests/test_navigation_settings_ui.py#L44), [45](../../../tests/test_navigation_settings_ui.py#L45), [46](../../../tests/test_navigation_settings_ui.py#L46), [47](../../../tests/test_navigation_settings_ui.py#L47), [48](../../../tests/test_navigation_settings_ui.py#L48), [49](../../../tests/test_navigation_settings_ui.py#L49), [50](../../../tests/test_navigation_settings_ui.py#L50), [52](../../../tests/test_navigation_settings_ui.py#L52), [53](../../../tests/test_navigation_settings_ui.py#L53), [54](../../../tests/test_navigation_settings_ui.py#L54), [56](../../../tests/test_navigation_settings_ui.py#L56), [57](../../../tests/test_navigation_settings_ui.py#L57), [58](../../../tests/test_navigation_settings_ui.py#L58), [59](../../../tests/test_navigation_settings_ui.py#L59), [60](../../../tests/test_navigation_settings_ui.py#L60), [61](../../../tests/test_navigation_settings_ui.py#L61), [62](../../../tests/test_navigation_settings_ui.py#L62), [63](../../../tests/test_navigation_settings_ui.py#L63), [64](../../../tests/test_navigation_settings_ui.py#L64), [67](../../../tests/test_navigation_settings_ui.py#L67), [68](../../../tests/test_navigation_settings_ui.py#L68), [69](../../../tests/test_navigation_settings_ui.py#L69), [70](../../../tests/test_navigation_settings_ui.py#L70), [71](../../../tests/test_navigation_settings_ui.py#L71).
- [test_app_loads_without_console_errors](../../../tests/e2e/test_smoke.py#L89) — Chromium gegen echte App-Routen und Demo-Firestore mit kontrollierter Identität/Modellen; ergänzend direkte Rendererfälle. Assertionstellen: [99](../../../tests/e2e/test_smoke.py#L99), [100](../../../tests/e2e/test_smoke.py#L100), [103](../../../tests/e2e/test_smoke.py#L103), [104](../../../tests/e2e/test_smoke.py#L104), [105](../../../tests/e2e/test_smoke.py#L105), [110](../../../tests/e2e/test_smoke.py#L110).
- [keeps the reading position when offscreen activity shrinks, including native anchoring](../../../tests/js/chat-scroll.test.mjs#L37) — Originale Scrollsteuerung mit kontrollierten DOMmaßen und Frames. Assertionstellen: [46](../../../tests/js/chat-scroll.test.mjs#L46), [52](../../../tests/js/chat-scroll.test.mjs#L52), [53](../../../tests/js/chat-scroll.test.mjs#L53), [55](../../../tests/js/chat-scroll.test.mjs#L55).
- [preserves manifest and content-hashed asset bytes in an autocrlf checkout](../../../tests/js/frontend-output.test.mjs#L31) — Echter Buildoutput und temporärer Gitcheckout. Assertionstellen: [60](../../../tests/js/frontend-output.test.mjs#L60).
- [test_native_due_queries_and_topic_claim_fence](../../../tests/e2e/test_scheduler_transactions.py#L21) — Echte Firestore-SDK-Transaktionen gegen isolierten Demo-Emulator. Assertionstellen: [33](../../../tests/e2e/test_scheduler_transactions.py#L33), [39](../../../tests/e2e/test_scheduler_transactions.py#L39), [42](../../../tests/e2e/test_scheduler_transactions.py#L42), [46](../../../tests/e2e/test_scheduler_transactions.py#L46), [47](../../../tests/e2e/test_scheduler_transactions.py#L47), [48](../../../tests/e2e/test_scheduler_transactions.py#L48).

**Suiteweite Gegenprüfung:** Manifestzeit-/DST-Drift, UTF8-Subprozess, Fixture-/UI-Erwartungen, Resize-Scrollsprung und echter Composer-Autosizefehler nach CSS-Breitenanimation behoben. Playwright/native Scheduler teilen keinen Eventloop mehr; konkrete SDK-Aborted-Aufrufe werden vor einem gesonderten nächsten Tick als Fehlversuche dokumentiert. Vollständig integriert: 3303 Python-, 705 JavaScript-, 368 E2E- und 49 Rulesfälle bestanden. Grüne integrierte Runner gelten für ffaca3df. Keine neue Branch-Coverage oder flächige visuelle Prüfung; alte Fehlerbelege und alternative Plattformskips bleiben sichtbar.

**Suchspur:** 304 versionierte Test-/Hilfsdateien durchsucht, 5 passende Zeilen. Regexe: ` consensus_prompt_template|test_scheduled_flow_without_packages|test_resume_of_a_finished_pilot `. Vollständige Treffer mit Pfad/Zeile in [search-evidence.json](search-evidence.json) unter ` G-046 `.

| Szenario | Erwartung |
|---|---|
| Given | Gesamtlauf unter Windows und isolierter Wiederholungslauf. |
| When | Prompt-/Mockzustand sowie Publisher-Subprozessresultat kontrolliert reproduzieren; aktuelle Browserfehler laut Laufbericht zuordnen. |
| Then | Gleiche fachliche Assertions bestehen isoliert und gemeinsam; keine Tests abschwächen oder Fehler nachträglich aus dem Primärlauf entfernen. |

**Zielstellen:** [tests/test_benchmark_budget.py](../../../tests/test_benchmark_budget.py), [tests/test_publisher_standalone.py](../../../tests/test_publisher_standalone.py)

**Wiederverwenden:** [tests/test_benchmark_budget.py](../../../tests/test_benchmark_budget.py), [tests/test_publisher_standalone.py](../../../tests/test_publisher_standalone.py)

**Validierung nach Implementierung:** ` Gezielte Dateien, dann kombinierter Lauf; native Transaktionen nur mit demo-consensio-e2e. `

**Gezielte Negativkontrolle:** Entscheidenden Guard oder Fehlerpfad kontrolliert ausschalten: der neue Test muss gezielt scheitern.

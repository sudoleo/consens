# Produktverhalten und Testbelege

[Einstieg](README.md) · [Dateikatalog](../backend.md) · [Lücken](gaps.md)

77 gruppierte Verhaltensverträge, alle 216 Testdateien verknüpft. Ein Abschnitt bündelt mehrere Teilverträge; die 83 ausgewählten Testdefinitionen sind konkrete **Teilbelege**. Sie beweisen nicht jede Klausel des Abschnitts. Der vollständige Testdateikatalog bleibt maßgeblich für die übrigen Assertions. Zuordnung, Testzahl und Zeilenausführung sind keine fachliche Coveragequote.

| Vertrag | Verhalten | Quellen | Testdateien | Befunde |
|---|---|---:|---:|---|
| [OPS-01](#ops-01) | Start, Shutdown und überwachte Jobs | 5 | 4 | — |
| [OPS-02](#ops-02) | Requestgrenzen und Sicherheitsheader | 3 | 4 | [G-033](gaps.md#g-033) |
| [OPS-03](#ops-03) | Inhaltsfreie Fehlerdiagnostik | 5 | 6 | — |
| [AUTH-01](#auth-01) | Registrierung ohne Kontoauskunft | 2 | 2 | [G-009](gaps.md#g-009) |
| [AUTH-02](#auth-02) | Token, Session und Rollen | 4 | 5 | [G-012](gaps.md#g-012) |
| [AUTH-03](#auth-03) | Kontolöschung mit Wiederaufnahme | 4 | 5 | [G-004](gaps.md#g-004), [G-008](gaps.md#g-008) |
| [AUTH-04](#auth-04) | Browser-Identität und Sitzungswechsel | 5 | 5 | [G-030](gaps.md#g-030) |
| [QUOTA-01](#quota-01) | Ein regulärer Lauf, eine Belastung | 3 | 3 | [G-002](gaps.md#g-002) |
| [QUOTA-02](#quota-02) | Rate-Limits und Kontostufen | 7 | 7 | [G-012](gaps.md#g-012) |
| [CHAT-01](#chat-01) | Chats, Turns und Cursor | 2 | 1 | [G-003](gaps.md#g-003) |
| [CHAT-02](#chat-02) | Abschluss und Löschsperre | 2 | 3 | [G-003](gaps.md#g-003) |
| [CHAT-03](#chat-03) | Kontext und Nutzergedächtnis im Lauf | 3 | 5 | — |
| [CHAT-04](#chat-04) | Bookmarks und vollständiger Verlauf | 3 | 7 | [G-030](gaps.md#g-030) |
| [MEM-01](#mem-01) | Memory lesen und manuell speichern | 3 | 3 | — |
| [MEM-02](#mem-02) | Expliziter KI-Patch und sicheres Undo | 3 | 2 | [G-007](gaps.md#g-007), [G-008](gaps.md#g-008) |
| [API-01](#api-01) | API-Schlüssel und Scopes | 4 | 3 | — |
| [API-02](#api-02) | Dauerhafte API-Runs | 3 | 2 | [G-005](gaps.md#g-005) |
| [API-03](#api-03) | Historische Source-Checks der API | 3 | 2 | [G-010](gaps.md#g-010) |
| [API-04](#api-04) | API-Publish und Publisher-Watch | 3 | 3 | — |
| [LLM-01](#llm-01) | Registry, Credentials und Payload | 9 | 7 | — |
| [LLM-02](#llm-02) | Providerstream, Fehler und Ressourcen | 4 | 5 | [G-032](gaps.md#g-032) |
| [CONS-01](#cons-01) | Neutrale Pipeline und Teilergebnisse | 3 | 5 | — |
| [CONS-02](#cons-02) | Strukturierte Differences und Agreement | 4 | 5 | — |
| [CONS-03](#cons-03) | Quellenkatalog und Zitatprovenienz | 4 | 5 | — |
| [CONS-04](#cons-04) | Resolve als eigener Lauf | 3 | 3 | — |
| [CONS-05](#cons-05) | Finalisierung, Replay und Browser-Recovery | 5 | 5 | [G-030](gaps.md#g-030) |
| [AGENT-01](#agent-01) | Admission und Token-/Kostenledger | 7 | 6 | — |
| [AGENT-02](#agent-02) | Chatpolicy und Legacy-Toolloop | 7 | 7 | — |
| [AGENT-03](#agent-03) | Delegierte Sitzungen und Kommunikation | 4 | 5 | — |
| [AGENT-04](#agent-04) | Agent-Recovery und Eigentümerbindung | 4 | 5 | [G-030](gaps.md#g-030) |
| [AGENT-05](#agent-05) | Agent-Ansicht und bestätigter Fortschritt | 6 | 9 | — |
| [SRC-01](#src-01) | Sicherer begrenzter Quellenabruf | 2 | 1 | [G-032](gaps.md#g-032) |
| [SRC-02](#src-02) | Prüfplan und konservative Urteile | 3 | 4 | — |
| [SRC-03](#src-03) | Dauerhafte Jobqueue und Credentials | 2 | 4 | [G-006](gaps.md#g-006) |
| [SRC-04](#src-04) | Private und öffentliche Jobseiten | 2 | 2 | [G-010](gaps.md#g-010) |
| [SRC-05](#src-05) | Sources-/Differences-UI und Nachladen | 3 | 10 | — |
| [SHARE-01](#share-01) | Autoritative Share-Erstellung | 3 | 3 | [G-011](gaps.md#g-011), [G-027](gaps.md#g-027) |
| [SHARE-02](#share-02) | Öffentliche und private Darstellung | 6 | 4 | — |
| [SHARE-03](#share-03) | Reports, Moderation und Kaskade | 3 | 2 | [G-029](gaps.md#g-029) |
| [SHARE-04](#share-04) | Open-Graph-Karte | 2 | 1 | [G-020](gaps.md#g-020) |
| [WATCH-01](#watch-01) | Watch-Erstellung und Planrechte | 2 | 3 | [G-013](gaps.md#g-013), [G-027](gaps.md#g-027) |
| [WATCH-02](#watch-02) | Zeitplan, Claim und Ausführung | 4 | 4 | [G-031](gaps.md#g-031) |
| [WATCH-03](#watch-03) | E-Mail-Follow mit Einwilligungsnachweis | 4 | 3 | — |
| [WATCH-04](#watch-04) | Telegram-Link und Zustellung | 3 | 1 | [G-013](gaps.md#g-013) |
| [WATCH-05](#watch-05) | Morning Brief | 4 | 2 | — |
| [WATCH-06](#watch-06) | Watch-Frontend | 3 | 6 | — |
| [TOPIC-01](#topic-01) | Topic-Administration und versionierte Runs | 2 | 1 | [G-014](gaps.md#g-014), [G-031](gaps.md#g-031) |
| [TOPIC-02](#topic-02) | Topic-Pipeline und Identitätsjudge | 3 | 2 | [G-016](gaps.md#g-016) |
| [TOPIC-03](#topic-03) | Zeitlicher Claim-/Quellenverlauf | 5 | 5 | — |
| [TOPIC-04](#topic-04) | Öffentliche Topic-Seiten und Follow | 5 | 3 | [G-014](gaps.md#g-014) |
| [TOPIC-05](#topic-05) | Interaktiver Check-Strip | 3 | 2 | [G-018](gaps.md#g-018) |
| [SEO-01](#seo-01) | Search-Console-Erfassung | 2 | 1 | — |
| [SEO-02](#seo-02) | SEO-Repository und Dossiers | 3 | 2 | [G-017](gaps.md#g-017) |
| [SEO-03](#seo-03) | Konservative Empfehlungen und Aktionen | 3 | 3 | — |
| [SEO-04](#seo-04) | Wöchentlicher Review und Publikationsdaten | 3 | 1 | [G-017](gaps.md#g-017), [G-031](gaps.md#g-031) |
| [SEO-05](#seo-05) | Öffentliche Navigation und Suchmetadaten | 27 | 5 | — |
| [ADMIN-01](#admin-01) | Revisionierte Konfiguration | 6 | 7 | — |
| [ADMIN-02](#admin-02) | Adminoberfläche und HTTP-Adapter | 9 | 8 | [G-019](gaps.md#g-019) |
| [UI-01](#ui-01) | Run-State und getrennte Ansichten | 4 | 6 | — |
| [UI-02](#ui-02) | Senden, Presets und Moduswechsel | 6 | 7 | — |
| [UI-03](#ui-03) | Streaming, Deadlines und Fortschritt | 4 | 6 | — |
| [UI-04](#ui-04) | Antworten, Markdown und zugängliche Details | 6 | 15 | [G-028](gaps.md#g-028) |
| [UI-05](#ui-05) | Anhänge und Composer | 4 | 8 | — |
| [UI-06](#ui-06) | Navigation, Scroll und Modals | 7 | 6 | [G-025](gaps.md#g-025) |
| [UI-07](#ui-07) | Bootstrap, Skript-Reihenfolge und Styles | 42 | 5 | — |
| [UI-08](#ui-08) | Demo und Landing-Interaktionen | 7 | 4 | — |
| [UI-09](#ui-09) | Analytics-Selbstausschluss | 2 | 1 | [G-021](gaps.md#g-021) |
| [DATA-01](#data-01) | Votes, Feedback und Modellstatistik | 3 | 4 | [G-034](gaps.md#g-034) |
| [BENCH-01](#bench-01) | Dataset, Budget und Closed-book-Vertrag | 7 | 6 | — |
| [BENCH-02](#bench-02) | Runner, Resume und Artefakte | 5 | 5 | [G-035](gaps.md#g-035) |
| [BENCH-03](#bench-03) | Ergebnisberechnung und Adminberichte | 4 | 3 | [G-015](gaps.md#g-015) |
| [BUILD-01](#build-01) | Reproduzierbare Frontendartefakte | 6 | 3 | [G-036](gaps.md#g-036) |
| [BUILD-02](#build-02) | Test- und Emulator-Einstieg | 4 | 3 | [G-024](gaps.md#g-024), [G-025](gaps.md#g-025), [G-026](gaps.md#g-026) |
| [BUILD-03](#build-03) | Scheduled Publisher und Workflows | 4 | 2 | [G-024](gaps.md#g-024) |
| [TOOLS-01](#tools-01) | Wartungs- und Reparaturwerkzeuge | 2 | 0 | [G-022](gaps.md#g-022), [G-023](gaps.md#g-023) |
| [TOOLS-02](#tools-02) | Evaluations-/Vorschauwerkzeuge | 4 | 2 | [G-035](gaps.md#g-035) |
| [AUTH-05](#auth-05) | Direkte Firestore-Clients bleiben gesperrt | 2 | 0 | [G-001](gaps.md#g-001) |

<a id="ops-01"></a>

## OPS-01 · Start, Shutdown und überwachte Jobs

Readiness wartet nur auf den begrenzten Konfigurationsread; Writer starten danach, werden überwacht und beim Shutdown beendet. E2E deaktiviert Writer und bindet Firebase an das Demo-Projekt.

**Anforderungsbasis:** [docs/codebase-map.md](../../codebase-map.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** Loops/Startup-Arbeit in Tests ersetzt; kein Deployment-Neustart. Browser-Harness überspringt die produktiven Writer.

**Befunde:** —. Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [app/core/background_tasks.py](../../../app/core/background_tasks.py)
- [app/core/concurrency.py](../../../app/core/concurrency.py)
- [app/core/e2e_profile.py](../../../app/core/e2e_profile.py)
- [app/services/retention_maintenance.py](../../../app/services/retention_maintenance.py)
- [main.py](../../../main.py)

**Testdateien:**

- [tests/test_background_task_supervision.py](../../../tests/test_background_task_supervision.py)
- [tests/test_e2e_safety.py](../../../tests/test_e2e_safety.py)
- [tests/test_router_event_loop_contract.py](../../../tests/test_router_event_loop_contract.py)
- [tests/test_worker_thread_budget.py](../../../tests/test_worker_thread_budget.py)

</details>

**Konkrete Teilbelege:**

- [test_supervisor_restarts_crashes_and_keeps_last_success_health](../../../tests/test_background_task_supervision.py#L12) — Async-Supervisor und Startupfunktionen mit Cleanup-Doubles. Historischer **Datei**status: passed=7.
  - [Zeile 43](../../../tests/test_background_task_supervision.py#L43): ` assert attempts == 3 `
  - [Zeile 44](../../../tests/test_background_task_supervision.py#L44): ` assert health["restart_count"] == 2 `
  - [Zeile 45](../../../tests/test_background_task_supervision.py#L45): ` assert health["consecutive_failures"] == 0 `
  - [Zeile 46](../../../tests/test_background_task_supervision.py#L46): ` assert health["last_success_at"] `
  - [Zeile 47](../../../tests/test_background_task_supervision.py#L47): ` assert health["state"] == "stopped" `
- [test_e2e_guard_rejects_missing_remote_or_unknown_targets](../../../tests/test_e2e_safety.py#L42) — Guard-Unit-Tests und Python-Subprozess-/Lifespan-Verträge. Historischer **Datei**status: passed=10.
  - [Zeile 43](../../../tests/test_e2e_safety.py#L43): ` with pytest.raises(RuntimeError, match=message): `
  - [Zeile 44](../../../tests/test_e2e_safety.py#L44): ` assert_safe_e2e_environment(safe_env(**overrides)) `

<a id="ops-02"></a>

## OPS-02 · Requestgrenzen und Sicherheitsheader

Übergrößen werden vor Parsing/Handler abgewiesen; Replay erhält den echten Disconnect. Private Datenantworten sind nicht öffentlich cachebar; App/Admin erzwingen externe Skripte.

**Anforderungsbasis:** [docs/codebase-map.md](../../codebase-map.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** ASGI- und Headerprüfungen, kein vorgeschalteter Proxy. Nicht jede ungültige Header-/Konfigurationskante wird ausgeführt.

**Befunde:** [G-033](gaps.md#g-033). Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [app/core/request_limits.py](../../../app/core/request_limits.py)
- [app/core/security.py](../../../app/core/security.py)
- [main.py](../../../main.py)

**Testdateien:**

- [tests/test_e2e_safety.py](../../../tests/test_e2e_safety.py)
- [tests/test_phase6_architecture.py](../../../tests/test_phase6_architecture.py)
- [tests/test_request_body_limits.py](../../../tests/test_request_body_limits.py)
- [tests/test_security_controls.py](../../../tests/test_security_controls.py)

</details>

**Konkrete Teilbelege:**

- [test_replayed_body_does_not_synthesize_disconnect_for_delayed_stream](../../../tests/test_request_body_limits.py#L75) — ASGI-Middleware mit kontrollierten Receive-/Send-Funktionen. Historischer **Datei**status: passed=4.
  - [Zeile 109](../../../tests/test_request_body_limits.py#L109): ` assert await inner_receive() == {                 "type": "http.request",                 "body": b"{}",                 "more_body": False,             } `
  - [Zeile 133](../../../tests/test_request_body_limits.py#L133): ` assert body_messages == [         {             "type": "http.response.body",             "body": b'event: final\ndata: {"response":"ok"}\n\n',             "more_body": True,         },         {"type": "http.response.body", "body": b"", "more_body": False},     ] `
- [test_app_and_all_admin_pages_receive_strict_script_csp](../../../tests/test_phase6_architecture.py#L184) — Gemischt: Pipeline-/CSP-Runtime und Quelltextarchitektur. Historischer **Datei**status: passed=8.
  - [Zeile 196](../../../tests/test_phase6_architecture.py#L196): ` assert "'unsafe-inline'" not in script_src `
  - [Zeile 201](../../../tests/test_phase6_architecture.py#L201): ` assert "'unsafe-inline'" in public_script_src `

<a id="ops-03"></a>

## OPS-03 · Inhaltsfreie Fehlerdiagnostik

Logs, Metriken und Browsermeldungen enthalten erlaubte Kategorien, keine Prompts, Antworten, Schlüssel oder Nutzerkennungen; Reporter dedupliziert und blockiert den Nutzerflow nicht.

**Anforderungsbasis:** [docs/codebase-map.md](../../codebase-map.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** Bekannte sensible Marker/Typen und Fake-Zustellung; keine universelle Freitext-Secret-Erkennung.

**Befunde:** —. Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [app/api/routers/client_errors.py](../../../app/api/routers/client_errors.py)
- [app/core/observability.py](../../../app/core/observability.py)
- [app/services/telegram_notifier.py](../../../app/services/telegram_notifier.py)
- [main.py](../../../main.py)
- [static/js/error-reporter.js](../../../static/js/error-reporter.js)

**Testdateien:**

- [tests/js/error-reporter.test.mjs](../../../tests/js/error-reporter.test.mjs)
- [tests/test_client_error_alerts.py](../../../tests/test_client_error_alerts.py)
- [tests/test_differences_stats.py](../../../tests/test_differences_stats.py)
- [tests/test_logging_redaction_contract.py](../../../tests/test_logging_redaction_contract.py)
- [tests/test_phase5_operations.py](../../../tests/test_phase5_operations.py)
- [tests/test_telegram_notifier.py](../../../tests/test_telegram_notifier.py)

</details>

**Konkrete Teilbelege:**

- [test_client_error_report_is_accepted_and_sanitized](../../../tests/test_client_error_alerts.py#L38) — Router mit Notification-Double und Bundle-Quelltextvertrag. Historischer **Datei**status: passed=34.
  - [Zeile 55](../../../tests/test_client_error_alerts.py#L55): ` assert response.status_code == 202 `
  - [Zeile 56](../../../tests/test_client_error_alerts.py#L56): ` assert response.json() == {"status": "accepted"} `
  - [Zeile 57](../../../tests/test_client_error_alerts.py#L57): ` assert captured == [{         "source": "browser",         "type": "run_failed",         "phase": "model_fanout",         "message": "A browser run failed.",         "path": "/s/{share_id}",     }] `

<a id="auth-01"></a>

## AUTH-01 · Registrierung ohne Kontoauskunft

Neue und vorhandene Adressen erhalten dieselbe öffentliche Antwort und den Mailbox-Setup-Pfad; fremdbestimmtes Passwort darf kein Konto übernehmen, ein Create-Race wird wie Bestand behandelt.

**Anforderungsbasis:** [docs/codebase-map.md](../../codebase-map.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** Firebase und Zustellung ersetzt. Der EmailAlreadyExists-Race-Zweig besitzt keinen ausgeführten Beleg.

**Befunde:** [G-009](gaps.md#g-009). Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [app/api/routers/auth.py](../../../app/api/routers/auth.py)
- [app/services/registration.py](../../../app/services/registration.py)

**Testdateien:**

- [tests/test_auth_session.py](../../../tests/test_auth_session.py)
- [tests/test_registration_security.py](../../../tests/test_registration_security.py)

</details>

**Konkrete Teilbelege:**

- [AuthSessionTests::test_new_and_existing_registration_responses_are_identical](../../../tests/test_auth_session.py#L110) — API mit Auth-/Mail-/Notifier-Doubles. Historischer **Datei**status: passed=8.
  - [Zeile 141](../../../tests/test_auth_session.py#L141): ` self.assertEqual(created.status_code, existing.status_code) `
  - [Zeile 142](../../../tests/test_auth_session.py#L142): ` self.assertEqual(created.content, existing.content) `

<a id="auth-02"></a>

## AUTH-02 · Token, Session und Rollen

Sensitive Aktionen prüfen Revocation, Account-Tombstone und aktuelle Rolle; Auth-/Tier-Ausfälle gewähren keine Rechte. Session-Cookie wird bei Login gesetzt und Logout gelöscht.

**Anforderungsbasis:** [docs/codebase-map.md](../../codebase-map.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** SDK-Rückgaben und Uhr kontrolliert; kein echter Firebase-Login oder verteilter Cache.

**Befunde:** [G-012](gaps.md#g-012). Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [app/api/routers/auth.py](../../../app/api/routers/auth.py)
- [app/core/entitlements.py](../../../app/core/entitlements.py)
- [app/core/security.py](../../../app/core/security.py)
- [app/services/account_tier.py](../../../app/services/account_tier.py)

**Testdateien:**

- [tests/test_account_tier_admin.py](../../../tests/test_account_tier_admin.py)
- [tests/test_auth_revocation.py](../../../tests/test_auth_revocation.py)
- [tests/test_auth_session.py](../../../tests/test_auth_session.py)
- [tests/test_plus_tier.py](../../../tests/test_plus_tier.py)
- [tests/test_tier_cache.py](../../../tests/test_tier_cache.py)

</details>

**Konkrete Teilbelege:**

- [test_admin_boundary_checks_revocation_and_maps_tier_outage_to_503](../../../tests/test_auth_revocation.py#L52) — Security-Funktionen mit Auth-/Datenbank-Doubles. Historischer **Datei**status: passed=4.
  - [Zeile 65](../../../tests/test_auth_revocation.py#L65): ` with pytest.raises(admin_router.HTTPException) as exc_info: `
  - [Zeile 68](../../../tests/test_auth_revocation.py#L68): ` assert verify.call_args.kwargs["check_revoked"] is True `
  - [Zeile 69](../../../tests/test_auth_revocation.py#L69): ` assert exc_info.value.status_code == 503 `

<a id="auth-03"></a>

## AUTH-03 · Kontolöschung mit Wiederaufnahme

Vor dem Löschen persistiert eine Sperre. Alle eigenen Datenbereiche werden idempotent entfernt, fremde Daten bleiben erhalten; Teilfehler bleiben 202/pending und quittierte Bereiche werden nicht neu erzeugt.

**Anforderungsbasis:** [docs/codebase-map.md](../../codebase-map.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** Löschorchestrierung und einzelne Kaskaden separat, Kernbereiche teilweise ersetzt. Keine komplette Kaskade mit gleichzeitig verspätetem Write im Emulator.

**Befunde:** [G-004](gaps.md#g-004), [G-008](gaps.md#g-008). Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [app/api/routers/users.py](../../../app/api/routers/users.py)
- [app/services/account_deletion.py](../../../app/services/account_deletion.py)
- [app/services/api_account_cleanup.py](../../../app/services/api_account_cleanup.py)
- [app/services/persistence_guard.py](../../../app/services/persistence_guard.py)

**Testdateien:**

- [tests/test_account_deletion_chats.py](../../../tests/test_account_deletion_chats.py)
- [tests/test_account_deletion_retry.py](../../../tests/test_account_deletion_retry.py)
- [tests/test_api_account_cleanup.py](../../../tests/test_api_account_cleanup.py)
- [tests/test_chat_history.py](../../../tests/test_chat_history.py)
- [tests/test_phase5_operations.py](../../../tests/test_phase5_operations.py)

</details>

**Konkrete Teilbelege:**

- [test_failed_area_remains_pending_and_only_that_area_is_retried](../../../tests/test_account_deletion_retry.py#L69) — Service mit In-Memory-Datenbank. Historischer **Datei**status: passed=1.
  - [Zeile 157](../../../tests/test_account_deletion_retry.py#L157): ` assert first_errors == ["owned_shares"] `
  - [Zeile 158](../../../tests/test_account_deletion_retry.py#L158): ` assert second_errors == [] `
  - [Zeile 159](../../../tests/test_account_deletion_retry.py#L159): ` assert calls["shares"] == 2 `
  - [Zeile 160](../../../tests/test_account_deletion_retry.py#L160): ` assert calls["source_checks"] == 1 `
  - [Zeile 161](../../../tests/test_account_deletion_retry.py#L161): ` assert calls["api"] == 1 `
  - [Zeile 162](../../../tests/test_account_deletion_retry.py#L162): ` assert calls["subcollections"] == 1 `
  - [Zeile 163](../../../tests/test_account_deletion_retry.py#L163): ` assert calls["chats"] == 1 `
  - [Zeile 164](../../../tests/test_account_deletion_retry.py#L164): ` assert calls["watches"] == 1 `
  - [Zeile 165](../../../tests/test_account_deletion_retry.py#L165): ` assert calls["watch_indexes"] == 1 `
  - [Zeile 166](../../../tests/test_account_deletion_retry.py#L166): ` assert calls["guards"] == 1 `
  - [Zeile 167](../../../tests/test_account_deletion_retry.py#L167): ` assert calls["follows"] == 1 `
  - [Zeile 168](../../../tests/test_account_deletion_retry.py#L168): ` assert calls["auth"] == 1 `
  - [Zeile 170](../../../tests/test_account_deletion_retry.py#L170): ` assert job["status"] == "completed" `
  - [Zeile 171](../../../tests/test_account_deletion_retry.py#L171): ` assert job["cleanup_pending"] is False `
  - [Zeile 172](../../../tests/test_account_deletion_retry.py#L172): ` assert "email" not in job `
  - [Zeile 173](../../../tests/test_account_deletion_retry.py#L173): ` assert all(job["completed_areas"].values()) `

<a id="auth-04"></a>

## AUTH-04 · Browser-Identität und Sitzungswechsel

Jeder asynchrone Read/Write und jede Ansicht gehört zur aktuellen UID und Auth-Generation. Logout/Kontowechsel verwerfen alte Projektionen und laufende Contexts.

**Anforderungsbasis:** [docs/codebase-map.md](../../codebase-map.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** Browserfälle nicht ausgeführt; JS-Fälle setzen Auth-State häufig selbst oder führen Firebase-Quellausschnitte aus. Kein Firebase-SDK-Emulatorvertrag.

**Befunde:** [G-030](gaps.md#g-030). Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [static/firebase.js](../../../static/firebase.js)
- [static/js/auth-bootstrap.js](../../../static/js/auth-bootstrap.js)
- [static/js/auth-session-state.js](../../../static/js/auth-session-state.js)
- [static/js/email-verify.js](../../../static/js/email-verify.js)
- [static/js/run-registry.js](../../../static/js/run-registry.js)

**Testdateien:**

- [tests/e2e/test_browser_failure_recovery.py](../../../tests/e2e/test_browser_failure_recovery.py)
- [tests/e2e/test_phase4_frontend.py](../../../tests/e2e/test_phase4_frontend.py)
- [tests/js/bookmark-write-queue.test.mjs](../../../tests/js/bookmark-write-queue.test.mjs)
- [tests/js/skeleton-lifecycle.test.mjs](../../../tests/js/skeleton-lifecycle.test.mjs)
- [tests/js/source-verification-watch.test.mjs](../../../tests/js/source-verification-watch.test.mjs)

</details>

**Konkrete Teilbelege:**

- [serializes the same account resource across rapid auth generations](../../../tests/js/bookmark-write-queue.test.mjs#L59) — Ausgeführter Firebase-Funktionsausschnitt in Node. Historischer **Datei**status: passed=3.
  - [Zeile 75](../../../tests/js/bookmark-write-queue.test.mjs#L75): ` expect(events).toEqual(["old:start"]); `
  - [Zeile 78](../../../tests/js/bookmark-write-queue.test.mjs#L78): ` expect(events).toEqual(["old:start", "old:end", "new"]); `

<a id="quota-01"></a>

## QUOTA-01 · Ein regulärer Lauf, eine Belastung

Prepare/Fan-out/Consensus teilen einen owner- und payloadgebundenen Run-Key; pro Provideroperation gewinnt genau ein Claim. Reserve/Consume/Release bleiben integerbasiert, UTC-gebunden und fail-closed.

**Anforderungsbasis:** [docs/codebase-map.md](../../codebase-map.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** Ausführliche konkurrierende Tests mit lokalen Locks; kein echter Firestore-Transaktionslauf für die reguläre Usage.

**Befunde:** [G-002](gaps.md#g-002). Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [app/api/routers/chat.py](../../../app/api/routers/chat.py)
- [app/api/routers/users.py](../../../app/api/routers/users.py)
- [app/services/usage_repository.py](../../../app/services/usage_repository.py)

**Testdateien:**

- [tests/test_run_usage_endpoints.py](../../../tests/test_run_usage_endpoints.py)
- [tests/test_run_usage_repository.py](../../../tests/test_run_usage_repository.py)
- [tests/test_usage_authorization.py](../../../tests/test_usage_authorization.py)

</details>

**Konkrete Teilbelege:**

- [test_prepare_and_parallel_models_consume_exactly_one_run](../../../tests/test_run_usage_endpoints.py#L88) — Router-Integration mit FakeFirestore und Provider-/Engine-Doubles. Historischer **Datei**status: passed=11.
  - [Zeile 93](../../../tests/test_run_usage_endpoints.py#L93): ` assert prepared.status_code == 200 `
  - [Zeile 97](../../../tests/test_run_usage_endpoints.py#L97): ` assert prepared.json()["usage_run_status"] == "consumed" `
  - [Zeile 98](../../../tests/test_run_usage_endpoints.py#L98): ` assert prepared.json()["free_usage_remaining"] == FREE_TOTAL - 1 `
  - [Zeile 111](../../../tests/test_run_usage_endpoints.py#L111): ` assert all(response.status_code == 200 for response in responses) `
  - [Zeile 112](../../../tests/test_run_usage_endpoints.py#L112): ` assert all(response.json()["usage_run_status"] == "consumed" for response in responses) `
  - [Zeile 114](../../../tests/test_run_usage_endpoints.py#L114): ` assert snapshot.total.reserved == 0 `
  - [Zeile 115](../../../tests/test_run_usage_endpoints.py#L115): ` assert snapshot.total.consumed == 1 `
  - [Zeile 116](../../../tests/test_run_usage_endpoints.py#L116): ` assert snapshot.total.remaining == FREE_TOTAL - 1 `
- [test_same_operation_race_has_exactly_one_authorization](../../../tests/test_usage_authorization.py#L68) — Atomare Autorisierungslogik mit FakeFirestore und Threads. Historischer **Datei**status: passed=19.
  - [Zeile 72](../../../tests/test_usage_authorization.py#L72): ` assert sum(not claim.idempotent for _, claim in results) == 1 `
  - [Zeile 73](../../../tests/test_usage_authorization.py#L73): ` assert repo.snapshot("owner", LIMITS, now=NOW).total.consumed == 1 `
  - [Zeile 76](../../../tests/test_usage_authorization.py#L76): ` assert repeated.idempotent `
  - [Zeile 77](../../../tests/test_usage_authorization.py#L77): ` assert db.documents == before `

<a id="quota-02"></a>

## QUOTA-02 · Rate-Limits und Kontostufen

Rechte und Kosten ergeben sich aus serverseitiger Stufe/Modellwahl; Own-Key umgeht keine Login-/Premiumrechte. UID-Limits bleiben beim Keywechsel erhalten; getrennte IP-/Key-Buckets schützen den Eingang.

**Anforderungsbasis:** [docs/codebase-map.md](../../codebase-map.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** Konfiguration und Sourceverträge ergänzen Endpointtests; echter Proxy-/Mehrinstanz-Limiter und user_status-Adapter bleiben gesondert zu prüfen.

**Befunde:** [G-012](gaps.md#g-012). Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [app/api/routers/users.py](../../../app/api/routers/users.py)
- [app/core/entitlements.py](../../../app/core/entitlements.py)
- [app/core/rate_limit.py](../../../app/core/rate_limit.py)
- [app/services/account_tier.py](../../../app/services/account_tier.py)
- [static/js/feature-access.js](../../../static/js/feature-access.js)
- [static/js/usage-limit.js](../../../static/js/usage-limit.js)
- [static/js/user-tier.js](../../../static/js/user-tier.js)

**Testdateien:**

- [tests/js/account-tier-mark.test.mjs](../../../tests/js/account-tier-mark.test.mjs)
- [tests/js/plus-tier-gates.test.mjs](../../../tests/js/plus-tier-gates.test.mjs)
- [tests/test_onboarding_gates.py](../../../tests/test_onboarding_gates.py)
- [tests/test_plus_tier.py](../../../tests/test_plus_tier.py)
- [tests/test_pro_beta_and_copy.py](../../../tests/test_pro_beta_and_copy.py)
- [tests/test_rate_limit.py](../../../tests/test_rate_limit.py)
- [tests/test_usage_limit_ui.py](../../../tests/test_usage_limit_ui.py)

</details>

**Konkrete Teilbelege:**

- [test_plus_gets_the_features_but_not_the_expensive_models](../../../tests/test_plus_tier.py#L67) — Entitlements-/Konfigurationslogik und Security mit DB-Double. Historischer **Datei**status: passed=34.
  - [Zeile 69](../../../tests/test_plus_tier.py#L69): ` assert plus.attachments is True `
  - [Zeile 70](../../../tests/test_plus_tier.py#L70): ` assert plus.resolve is True `
  - [Zeile 72](../../../tests/test_plus_tier.py#L72): ` assert plus.is_pro is False `
  - [Zeile 73](../../../tests/test_plus_tier.py#L73): ` assert plus.premium_models is False `
  - [Zeile 74](../../../tests/test_plus_tier.py#L74): ` assert plus.deep_think is False `

<a id="chat-01"></a>

## CHAT-01 · Chats, Turns und Cursor

Ownergebundene Chats/Turns verwenden stabile Request-IDs, monotone Positionen und begrenzte signierte Pagination; bewegte Seitengrenzen dürfen keine fremden oder doppelten Inhalte erzeugen.

**Anforderungsbasis:** [docs/codebase-map.md](../../codebase-map.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** FakeChatDatabase bildet Query/Transaktion nach; keine echte Create-Turn-/Pagination-Konkurrenz.

**Befunde:** [G-003](gaps.md#g-003). Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [app/api/routers/chat_history.py](../../../app/api/routers/chat_history.py)
- [app/services/chat_store.py](../../../app/services/chat_store.py)

**Testdateien:**

- [tests/test_chat_history.py](../../../tests/test_chat_history.py)

</details>

**Konkrete Teilbelege:**

- [test_chat_cursor_keeps_original_boundary_when_boundary_chat_moves](../../../tests/test_chat_history.py#L504) — Router und ChatStore mit speicherbasiertem Transaktionsmodell. Historischer **Datei**status: passed=72.
  - [Zeile 521](../../../tests/test_chat_history.py#L521): ` assert delivered_ids == [chats[3]["id"], chats[2]["id"]] `
  - [Zeile 522](../../../tests/test_chat_history.py#L522): ` assert second_ids == [chats[1]["id"], chats[0]["id"]] `
  - [Zeile 523](../../../tests/test_chat_history.py#L523): ` assert set(delivered_ids).isdisjoint(second_ids) `

<a id="chat-02"></a>

## CHAT-02 · Abschluss und Löschsperre

Completion persistiert erlaubte Turn-/Antwortdaten atomar, ist bei identischem Payload idempotent und lehnt Konflikte ab. Nach deleting/Tombstone sind verspätete Completion/Fail-Writes gesperrt.

**Anforderungsbasis:** [docs/codebase-map.md](../../codebase-map.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** Fake-Commit-Fehler und getrennte Endpoints; Atomizität gegenüber realem Delete/Complete-Race nicht belegt.

**Befunde:** [G-003](gaps.md#g-003). Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [app/api/routers/chat.py](../../../app/api/routers/chat.py)
- [app/services/chat_store.py](../../../app/services/chat_store.py)

**Testdateien:**

- [tests/test_agent_chat_integrity.py](../../../tests/test_agent_chat_integrity.py)
- [tests/test_chat_history.py](../../../tests/test_chat_history.py)
- [tests/test_consensus_chat_history.py](../../../tests/test_consensus_chat_history.py)

</details>

**Konkrete Teilbelege:**

- [test_complete_turn_atomically_persists_six_separate_answer_documents](../../../tests/test_chat_history.py#L824) — Router und ChatStore mit speicherbasiertem Transaktionsmodell. Historischer **Datei**status: passed=72.
  - [Zeile 838](../../../tests/test_chat_history.py#L838): ` assert completed["status"] == "completed" `
  - [Zeile 839](../../../tests/test_chat_history.py#L839): ` assert completed["answer_count"] == 6 `
  - [Zeile 840](../../../tests/test_chat_history.py#L840): ` assert completed["agreement_score"] == 83 `
  - [Zeile 841](../../../tests/test_chat_history.py#L841): ` assert completed["included_models"] == list(PROVIDERS) `
  - [Zeile 842](../../../tests/test_chat_history.py#L842): ` assert set(completed["model_answers"]) == set(PROVIDERS) `
  - [Zeile 843](../../../tests/test_chat_history.py#L843): ` assert set(stored_answers) == {         chat_store.PROVIDER_DOCUMENT_IDS[provider] for provider in PROVIDERS     } `
  - [Zeile 846](../../../tests/test_chat_history.py#L846): ` assert all(         set(answer) == {             "schema_version", "provider", "model_label", "answer", "sources",             "created_at", "updated_at",         }         for answer in stored_answers.values()     ) `
  - [Zeile 853](../../../tests/test_chat_history.py#L853): ` assert all("api_key" not in answer for answer in stored_answers.values()) `
  - [Zeile 854](../../../tests/test_chat_history.py#L854): ` assert all("raw_attachment" not in answer for answer in stored_answers.values()) `
  - [Zeile 855](../../../tests/test_chat_history.py#L855): ` assert "model_answers" not in stored_turn `
  - [Zeile 856](../../../tests/test_chat_history.py#L856): ` assert not any(provider in stored_turn for provider in PROVIDERS) `
  - [Zeile 857](../../../tests/test_chat_history.py#L857): ` assert stored_turn["completion_fingerprint"] `
  - [Zeile 858](../../../tests/test_chat_history.py#L858): ` assert stored_turn["result_id"] == "AbCdEf0123456789" `
  - [Zeile 859](../../../tests/test_chat_history.py#L859): ` assert stored_turn["sources"] == [{         "id": "S1", "title": "Turn source", "url": "https://example.test/turn",         "provider": "OpenAI",     }] `
  - [Zeile 863](../../../tests/test_chat_history.py#L863): ` assert "secret" not in stored_turn["differences_data"]["claims"][0] `
  - [Zeile 864](../../../tests/test_chat_history.py#L864): ` assert "api_key" not in stored_turn["differences_data"] `
  - [Zeile 865](../../../tests/test_chat_history.py#L865): ` assert stored_chat["turn_count"] == chat_before["turn_count"] == 1 `
  - [Zeile 866](../../../tests/test_chat_history.py#L866): ` assert stored_chat["latest_question"] == chat_before["latest_question"] `
  - [Zeile 867](../../../tests/test_chat_history.py#L867): ` assert stored_chat["updated_at"] > chat_before["updated_at"] `
  - [Zeile 869](../../../tests/test_chat_history.py#L869): ` assert len(committed_paths) == 8 `
  - [Zeile 870](../../../tests/test_chat_history.py#L870): ` assert committed_paths[-2:] == [         ("users", "owner-uid", "chats", chat["id"], "turns", turn["id"]),         ("users", "owner-uid", "chats", chat["id"]),     ] `
- [test_deleting_chat_state_rejects_late_completion_and_failure_writes](../../../tests/test_chat_history.py#L1484) — Router und ChatStore mit speicherbasiertem Transaktionsmodell. Historischer **Datei**status: passed=72.
  - [Zeile 1493](../../../tests/test_chat_history.py#L1493): ` with pytest.raises(chat_store.ChatNotFound): `
  - [Zeile 1497](../../../tests/test_chat_history.py#L1497): ` with pytest.raises(chat_store.ChatNotFound): `
  - [Zeile 1505](../../../tests/test_chat_history.py#L1505): ` assert database.documents == before `
  - [Zeile 1506](../../../tests/test_chat_history.py#L1506): ` assert database.model_answers("owner-uid", chat["id"], turn["id"]) == {} `

<a id="chat-03"></a>

## CHAT-03 · Kontext und Nutzergedächtnis im Lauf

Ein autoritativer Kontext ist an Owner/Turn/Frage/Version gebunden, einmalig gebaut und begrenzt. Jede Modellfamilie erhält nur ihre eigene vorherige Antwort; Gedächtnis bleibt Datenkontext ohne ungefragte Persistenz.

**Anforderungsbasis:** [docs/codebase-map.md](../../codebase-map.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** Compressor/Judge synthetisch; Signaltests beweisen keine semantische Gedächtnisqualität oder Prompt-Injection-Resistenz.

**Befunde:** —. Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [app/api/routers/chat_history.py](../../../app/api/routers/chat_history.py)
- [app/services/chat_context.py](../../../app/services/chat_context.py)
- [app/services/user_memory.py](../../../app/services/user_memory.py)

**Testdateien:**

- [tests/test_chat_context.py](../../../tests/test_chat_context.py)
- [tests/test_followup_context.py](../../../tests/test_followup_context.py)
- [tests/test_prompt_date_context.py](../../../tests/test_prompt_date_context.py)
- [tests/test_user_memory.py](../../../tests/test_user_memory.py)
- [tests/test_user_memory_run_cache.py](../../../tests/test_user_memory_run_cache.py)

</details>

**Konkrete Teilbelege:**

- [test_each_model_sees_only_its_own_previous_answer](../../../tests/test_chat_context.py#L1043) — Service/Repository/Router mit FakeChatDatabase und künstlichem Compressor. Historischer **Datei**status: passed=37.
  - [Zeile 1074](../../../tests/test_chat_context.py#L1074): ` assert "My earlier reading of the site." in claude `
  - [Zeile 1075](../../../tests/test_chat_context.py#L1075): ` assert "A different earlier reading." not in claude `
  - [Zeile 1076](../../../tests/test_chat_context.py#L1076): ` assert "A different earlier reading." in grok `
  - [Zeile 1077](../../../tests/test_chat_context.py#L1077): ` assert "My earlier reading of the site." not in grok `
  - [Zeile 1079](../../../tests/test_chat_context.py#L1079): ` assert "Anthropic" not in claude and "Grok" not in grok `
  - [Zeile 1081](../../../tests/test_chat_context.py#L1081): ` assert "the answer you yourself gave" not in mistral.casefold() `

<a id="chat-04"></a>

## CHAT-04 · Bookmarks und vollständiger Verlauf

Speichern materialisiert den autoritativen Run/Turn statt Clientkopien; stabile Bookmark-ID erhält alle Turns, Listen bleiben kompakt. Rehydration ist owner-/versionsgebunden, Quoten begrenzen Count/Bytes.

**Anforderungsbasis:** [docs/codebase-map.md](../../codebase-map.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** Browser-SDK/API ersetzt, viele JS-Tests Quellausschnitte; keine durchgehende Browser→Bookmark→Firestore-Kaskade.

**Befunde:** [G-030](gaps.md#g-030). Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [app/api/routers/bookmarks.py](../../../app/api/routers/bookmarks.py)
- [app/services/persistence_guard.py](../../../app/services/persistence_guard.py)
- [static/firebase.js](../../../static/firebase.js)

**Testdateien:**

- [tests/e2e/test_bookmark_lifecycle_frontend.py](../../../tests/e2e/test_bookmark_lifecycle_frontend.py)
- [tests/js/bookmark-attachments.test.mjs](../../../tests/js/bookmark-attachments.test.mjs)
- [tests/js/bookmark-pending-state.test.mjs](../../../tests/js/bookmark-pending-state.test.mjs)
- [tests/js/bookmark-source-check.test.mjs](../../../tests/js/bookmark-source-check.test.mjs)
- [tests/js/bookmark-write-queue.test.mjs](../../../tests/js/bookmark-write-queue.test.mjs)
- [tests/test_bookmarks.py](../../../tests/test_bookmarks.py)
- [tests/test_phase5_operations.py](../../../tests/test_phase5_operations.py)

</details>

**Konkrete Teilbelege:**

- [test_chat_bookmark_conversation_falls_back_without_losing_middle_turns](../../../tests/test_bookmarks.py#L881) — Router/Service mit Firestore-Doubles und Quelltextverträgen. Historischer **Datei**status: passed=38.
  - [Zeile 894](../../../tests/test_bookmarks.py#L894): ` assert (uid, requested_chat_id, cursor, limit) == (                 "uid-1", chat_id, "", 50,             ) `
  - [Zeile 931](../../../tests/test_bookmarks.py#L931): ` assert response.status_code == 200 `
  - [Zeile 932](../../../tests/test_bookmarks.py#L932): ` assert [turn["question"] for turn in response.json()["turns"]] == [         "Question 1", "Question 2", "Question 3", "Question 4",     ] `

<a id="mem-01"></a>

## MEM-01 · Memory lesen und manuell speichern

Auth und Feldallowlist begrenzen Memory; fehlende/pausierte Profile sind neutral, ein Legacy-Save erhält unübermittelte Notizen und Kontolöschung sperrt Writes.

**Anforderungsbasis:** [docs/codebase-map.md](../../codebase-map.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** Repos/Endpoints/DOM separat; reale Cross-Tab-Persistenz nicht durch diese Tests bewiesen.

**Befunde:** —. Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [app/api/routers/users.py](../../../app/api/routers/users.py)
- [app/services/user_memory.py](../../../app/services/user_memory.py)
- [static/js/user-memory.js](../../../static/js/user-memory.js)

**Testdateien:**

- [tests/js/user-memory.test.mjs](../../../tests/js/user-memory.test.mjs)
- [tests/test_user_memory.py](../../../tests/test_user_memory.py)
- [tests/test_user_memory_run_cache.py](../../../tests/test_user_memory_run_cache.py)

</details>

**Konkrete Teilbelege:**

- [test_legacy_save_without_notes_preserves_an_existing_long_note](../../../tests/test_user_memory.py#L234) — Sanitizer-/Repository-/Router-/Prompt-Integration mit Doubles und einem Sourcevertrag. Historischer **Datei**status: passed=29.
  - [Zeile 237](../../../tests/test_user_memory.py#L237): ` assert saved["role"] == "Senior doctor" `
  - [Zeile 238](../../../tests/test_user_memory.py#L238): ` assert saved["notes"] == "Keep this imported memory" `
  - [Zeile 241](../../../tests/test_user_memory.py#L241): ` assert cleared["notes"] == "" `

<a id="mem-02"></a>

## MEM-02 · Expliziter KI-Patch und sicheres Undo

KI-Edit wendet nur den kleinsten erlaubten Patch gegen die reservierte Revision an, belastet Request/Budget einmal und überschreibt keine fremde Zwischenänderung. Undo ist zeitlich/owner-/revisionsgebunden.

**Anforderungsbasis:** [docs/codebase-map.md](../../codebase-map.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** Guard im Repository-Test deaktiviert. Undo-Erfolg belegt nicht Konflikt, Ablauf, fremden Owner oder wiederholtes Undo.

**Befunde:** [G-007](gaps.md#g-007), [G-008](gaps.md#g-008). Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [app/api/routers/users.py](../../../app/api/routers/users.py)
- [app/services/memory_edit.py](../../../app/services/memory_edit.py)
- [static/js/memory-edit.js](../../../static/js/memory-edit.js)

**Testdateien:**

- [tests/e2e/test_reader_review_regressions.py](../../../tests/e2e/test_reader_review_regressions.py)
- [tests/test_memory_edit.py](../../../tests/test_memory_edit.py)

</details>

**Konkrete Teilbelege:**

- [test_replace_is_revision_checked_and_undo_restores_exact_content](../../../tests/test_memory_edit.py#L118) — Edit-Service/Repository und Router mit DB-/LLM-Doubles. Historischer **Datei**status: passed=14.
  - [Zeile 129](../../../tests/test_memory_edit.py#L129): ` assert reserved["baseline_revision"] == 4 `
  - [Zeile 143](../../../tests/test_memory_edit.py#L143): ` assert result["status"] == "applied" `
  - [Zeile 147](../../../tests/test_memory_edit.py#L147): ` assert profile["role"] == "Works at Firma Y." `
  - [Zeile 148](../../../tests/test_memory_edit.py#L148): ` assert revision == 5 `
  - [Zeile 159](../../../tests/test_memory_edit.py#L159): ` assert undone["status"] == "undone" `
  - [Zeile 160](../../../tests/test_memory_edit.py#L160): ` assert restored["role"] == "Works at Firma X." `
  - [Zeile 161](../../../tests/test_memory_edit.py#L161): ` assert restored["notes"] == "Prefers short answers." `
  - [Zeile 162](../../../tests/test_memory_edit.py#L162): ` assert restored_revision == 6 `

<a id="api-01"></a>

## API-01 · API-Schlüssel und Scopes

Nur aktive verifizierte Konten bekommen Schlüssel; Klartext wird einmal ausgegeben und nicht gespeichert. Ownerbindung, Widerruf und Scopes begrenzen Run/Share/Indexing.

**Anforderungsbasis:** [docs/consensus-api.md](../../consensus-api.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** Hash-/Scope-/Authvertrag lokal; API-Cleanup und Listenadapter teilweise durch Doubles ersetzt.

**Befunde:** —. Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [app/api/routers/admin.py](../../../app/api/routers/admin.py)
- [app/api/routers/api_v1.py](../../../app/api/routers/api_v1.py)
- [app/services/api_account_cleanup.py](../../../app/services/api_account_cleanup.py)
- [app/services/api_key_repository.py](../../../app/services/api_key_repository.py)

**Testdateien:**

- [tests/test_api_account_cleanup.py](../../../tests/test_api_account_cleanup.py)
- [tests/test_api_key_repository.py](../../../tests/test_api_key_repository.py)
- [tests/test_consensus_api.py](../../../tests/test_consensus_api.py)

</details>

**Konkrete Teilbelege:**

- [test_plaintext_key_is_returned_once_but_never_persisted](../../../tests/test_api_key_repository.py#L71) — Repository mit Firestore-Fake. Historischer **Datei**status: passed=5.
  - [Zeile 76](../../../tests/test_api_key_repository.py#L76): ` assert issued["api_key"].startswith("cns_live_") `
  - [Zeile 77](../../../tests/test_api_key_repository.py#L77): ` assert issued["key_id"] in db.documents `
  - [Zeile 78](../../../tests/test_api_key_repository.py#L78): ` assert issued["api_key"] not in repr(db.documents) `
  - [Zeile 79](../../../tests/test_api_key_repository.py#L79): ` assert "api_key" not in db.documents[issued["key_id"]] `
  - [Zeile 81](../../../tests/test_api_key_repository.py#L81): ` assert identity.uid == "user-1" `
  - [Zeile 82](../../../tests/test_api_key_repository.py#L82): ` assert identity.key_id == issued["key_id"] `
  - [Zeile 83](../../../tests/test_api_key_repository.py#L83): ` assert identity.scopes == tuple(sorted(DEFAULT_API_KEY_SCOPES)) `
  - [Zeile 86](../../../tests/test_api_key_repository.py#L86): ` assert db.documents[issued["key_id"]]["last_used_at"] == first_last_used `

<a id="api-02"></a>

## API-02 · Dauerhafte API-Runs

Idempotency-Key und Payload bestimmen einen Run. Nur ein Worker beginnt bezahlte Arbeit; accepted/reserved dürfen wieder aufgenommen werden, running nach unklarem Ausfall darf nicht blind erneut generieren.

**Anforderungsbasis:** [docs/consensus-api.md](../../consensus-api.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** Zustandsübergänge und execute-Pfad belegt; tatsächliche Recovery-/Retention-Orchestrierung in regulärer Suite nicht ausgeführt.

**Befunde:** [G-005](gaps.md#g-005). Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [app/api/routers/api_v1.py](../../../app/api/routers/api_v1.py)
- [app/services/api_consensus_runner.py](../../../app/services/api_consensus_runner.py)
- [app/services/api_run_repository.py](../../../app/services/api_run_repository.py)

**Testdateien:**

- [tests/test_api_run_repository.py](../../../tests/test_api_run_repository.py)
- [tests/test_consensus_api.py](../../../tests/test_consensus_api.py)

</details>

**Konkrete Teilbelege:**

- [test_expired_running_lease_fails_without_requeueing](../../../tests/test_api_run_repository.py#L199) — Repository mit synchronisiertem Firestore-Fake. Historischer **Datei**status: passed=8.
  - [Zeile 210](../../../tests/test_api_run_repository.py#L210): ` assert changed is True `
  - [Zeile 211](../../../tests/test_api_run_repository.py#L211): ` assert failed["status"] == "failed" `
  - [Zeile 212](../../../tests/test_api_run_repository.py#L212): ` assert failed["error"]["code"] == "worker_interrupted" `
  - [Zeile 213](../../../tests/test_api_run_repository.py#L213): ` assert repo.fail_if_lease_expired(run["run_id"]) is False `

<a id="api-03"></a>

## API-03 · Historische Source-Checks der API

Historische API-Prüfberichte bleiben owner-, run- und antwortversionsgebunden lesbar; neue Nicht-Chat-Runs starten keine Source-Check-Jobs.

**Anforderungsbasis:** [docs/codebase-map.md](../../codebase-map.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** Chat-/Share-/Topic-Adapter geprüft; historischer API-v1-source-check-Handler nicht ausgeführt. Alte API-Doku beschreibt noch aktive Job-Erzeugung.

**Befunde:** [G-010](gaps.md#g-010). Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [app/api/routers/api_v1.py](../../../app/api/routers/api_v1.py)
- [app/api/routers/source_checks.py](../../../app/api/routers/source_checks.py)
- [app/services/source_check_jobs.py](../../../app/services/source_check_jobs.py)

**Testdateien:**

- [tests/test_source_check_api.py](../../../tests/test_source_check_api.py)
- [tests/test_source_check_scope.py](../../../tests/test_source_check_scope.py)

</details>

**Konkrete Teilbelege:**

- [test_product_runs_keep_consensus_and_differences_without_source_work](../../../tests/test_source_check_scope.py#L20) — Produkt-Pipeline-Integration im Mock-LLM-Modus mit verbotenen Source-Hooks. Historischer **Datei**status: passed=12.
  - [Zeile 39](../../../tests/test_source_check_scope.py#L39): ` assert result.get('consensus') or result.get('consensus_response') `
  - [Zeile 40](../../../tests/test_source_check_scope.py#L40): ` assert isinstance(result['differences_data']['agreement']['score'], int) `
  - [Zeile 41](../../../tests/test_source_check_scope.py#L41): ` assert result.get('source_verification') is None `
  - [Zeile 43](../../../tests/test_source_check_scope.py#L43): ` assert len(result['included_models']) == 2 `
  - [Zeile 44](../../../tests/test_source_check_scope.py#L44): ` assert 'sources' in result `
  - [Zeile 45](../../../tests/test_source_check_scope.py#L45): ` assert 'opinion_map' in result `
  - [Zeile 46](../../../tests/test_source_check_scope.py#L46): ` assert 'changed' in result `

<a id="api-04"></a>

## API-04 · API-Publish und Publisher-Watch

Nur eigene erfolgreiche Runs werden publiziert; Indexing verlangt Scope und aktuelle Adminrolle. Publisher-Konfiguration und Watch-Capacity liefern stabile Skip-/Erfolgsverträge.

**Anforderungsbasis:** [docs/codebase-map.md](../../codebase-map.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** API/Repository/Dienst separat mit Fakes. Aktuelle Providerpläne den Tests/Config entnehmen; veraltete DeepSeek-Ausschlussbeschreibung nicht als Soll verwenden.

**Befunde:** —. Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [app/api/routers/api_v1.py](../../../app/api/routers/api_v1.py)
- [app/services/publisher_config.py](../../../app/services/publisher_config.py)
- [app/services/share_snapshots.py](../../../app/services/share_snapshots.py)

**Testdateien:**

- [tests/test_consensus_api.py](../../../tests/test_consensus_api.py)
- [tests/test_publisher_config.py](../../../tests/test_publisher_config.py)
- [tests/test_share_feature.py](../../../tests/test_share_feature.py)

</details>

**Konkrete Teilbelege:**

- [test_direct_indexing_requires_scope_admin_and_returns_indexed_state](../../../tests/test_consensus_api.py#L930) — Main-App-API und Runner mit Repository-/LLM-/Scheduler-Doubles; einzelne Quelltextverträge. Historischer **Datei**status: passed=27.
  - [Zeile 967](../../../tests/test_consensus_api.py#L967): ` assert response.status_code == 200 `
  - [Zeile 968](../../../tests/test_consensus_api.py#L968): ` assert response.json()["indexing_status"] == "indexed" `
  - [Zeile 969](../../../tests/test_consensus_api.py#L969): ` assert response.json()["robots"] == "index, follow" `
  - [Zeile 970](../../../tests/test_consensus_api.py#L970): ` assert response.json()["in_sitemap"] is True `
  - [Zeile 978](../../../tests/test_consensus_api.py#L978): ` assert denied_scope.status_code == 403 `
  - [Zeile 987](../../../tests/test_consensus_api.py#L987): ` assert denied_admin.status_code == 403 `

<a id="llm-01"></a>

## LLM-01 · Registry, Credentials und Payload

Angebotene Modelle, Fähigkeiten, Reasoning und Suchoptionen folgen der Registry; nur der passende OpenRouter-Key wird verwendet, Own-Key hat keinen Developer-Fallback.

**Anforderungsbasis:** [docs/codebase-map.md](../../codebase-map.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** Konfiguration/Payloads des Snapshots; keine Live-Verfügbarkeits-, Preis- oder Capability-Bestätigung.

**Befunde:** —. Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [app/core/config.py](../../../app/core/config.py)
- [app/core/openrouter_contract.py](../../../app/core/openrouter_contract.py)
- [app/services/llm/agent_model_catalog.json](../../../app/services/llm/agent_model_catalog.json)
- [app/services/llm/agent_model_metadata.py](../../../app/services/llm/agent_model_metadata.py)
- [app/services/llm/base.py](../../../app/services/llm/base.py)
- [app/services/llm/credentials.py](../../../app/services/llm/credentials.py)
- [app/services/llm/engines.py](../../../app/services/llm/engines.py)
- [app/services/llm/provider_transport.py](../../../app/services/llm/provider_transport.py)
- [app/services/llm/task_transport.py](../../../app/services/llm/task_transport.py)

**Testdateien:**

- [tests/test_agent_model_catalog.py](../../../tests/test_agent_model_catalog.py)
- [tests/test_ask_endpoints.py](../../../tests/test_ask_endpoints.py)
- [tests/test_deepseek_web_search.py](../../../tests/test_deepseek_web_search.py)
- [tests/test_model_configuration.py](../../../tests/test_model_configuration.py)
- [tests/test_model_configuration_regressions.py](../../../tests/test_model_configuration_regressions.py)
- [tests/test_provider_registry.py](../../../tests/test_provider_registry.py)
- [tests/test_reasoning_policy.py](../../../tests/test_reasoning_policy.py)

</details>

**Konkrete Teilbelege:**

- [test_own_keys_flag_without_openrouter_key_is_rejected](../../../tests/test_ask_endpoints.py#L78) — Router und Usage-Repository mit Auth-/Provider-Doubles. Historischer **Datei**status: passed=14.
  - [Zeile 91](../../../tests/test_ask_endpoints.py#L91): ` assert response.status_code == 400 `
  - [Zeile 92](../../../tests/test_ask_endpoints.py#L92): ` assert response.json()["detail"] == "Missing user OpenRouter API key." `

<a id="llm-02"></a>

## LLM-02 · Providerstream, Fehler und Ressourcen

Timeouts sind begrenzt, HTTP-200-Fehlerbodies werden als Fehler erkannt, Ressourcen schließen bei normalem Ende und Cancel. Kein versteckter kostenpflichtiger SDK-Retry.

**Anforderungsbasis:** [docs/codebase-map.md](../../codebase-map.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** HTTPX-/SSE-Doubles und lokale Tasks; kein realer TCP/TLS-Providerstall oder Proxy-Disconnect.

**Befunde:** [G-032](gaps.md#g-032). Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [app/services/llm/agent_client.py](../../../app/services/llm/agent_client.py)
- [app/services/llm/mock_llm.py](../../../app/services/llm/mock_llm.py)
- [app/services/llm/provider_runtime.py](../../../app/services/llm/provider_runtime.py)
- [app/services/llm/streaming.py](../../../app/services/llm/streaming.py)

**Testdateien:**

- [tests/test_agent_reliability.py](../../../tests/test_agent_reliability.py)
- [tests/test_provider_response_errors.py](../../../tests/test_provider_response_errors.py)
- [tests/test_provider_timeouts.py](../../../tests/test_provider_timeouts.py)
- [tests/test_stream_backpressure.py](../../../tests/test_stream_backpressure.py)
- [tests/test_streaming.py](../../../tests/test_streaming.py)

</details>

**Konkrete Teilbelege:**

- [test_body_error_preserves_status_without_content_or_retry](../../../tests/test_provider_response_errors.py#L55) — Adapter/Fan-out mit HTTP-Response-Doubles. Historischer **Datei**status: passed=38.
  - [Zeile 64](../../../tests/test_provider_response_errors.py#L64): ` assert result["error_code"] == expected `
  - [Zeile 65](../../../tests/test_provider_response_errors.py#L65): ` assert result["text"] == "" `
  - [Zeile 66](../../../tests/test_provider_response_errors.py#L66): ` assert result["sources"] == [] `
  - [Zeile 67](../../../tests/test_provider_response_errors.py#L67): ` assert f"_ProviderResponseError:{code}" in caplog.text `
  - [Zeile 68](../../../tests/test_provider_response_errors.py#L68): ` assert secret not in caplog.text + json.dumps(result) `

<a id="cons-01"></a>

## CONS-01 · Neutrale Pipeline und Teilergebnisse

Fan-out sammelt gültige Antworten, synthetisiert Consensus und analysiert Unterschiede; gescheiterte Einzelmodelle werden ehrlich behandelt. Watch/Topic/API verwenden denselben neutralen Kern.

**Anforderungsbasis:** [docs/codebase-map.md](../../codebase-map.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** Feste Engine-/Judge-Ergebnisse prüfen Orchestrierung, keine fachliche Überlegenheit der Synthese.

**Befunde:** —. Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [app/api/routers/chat.py](../../../app/api/routers/chat.py)
- [app/services/consensus_pipeline.py](../../../app/services/consensus_pipeline.py)
- [app/services/llm/consensus_engine.py](../../../app/services/llm/consensus_engine.py)

**Testdateien:**

- [tests/test_consensus_answer_contract.py](../../../tests/test_consensus_answer_contract.py)
- [tests/test_consensus_chat_history.py](../../../tests/test_consensus_chat_history.py)
- [tests/test_consensus_engine.py](../../../tests/test_consensus_engine.py)
- [tests/test_consensus_input_caps.py](../../../tests/test_consensus_input_caps.py)
- [tests/test_phase6_architecture.py](../../../tests/test_phase6_architecture.py)

</details>

**Konkrete Teilbelege:**

- [test_neutral_pipeline_can_select_the_first_successful_provider_as_engine](../../../tests/test_phase6_architecture.py#L76) — Gemischt: Pipeline-/CSP-Runtime und Quelltextarchitektur. Historischer **Datei**status: passed=8.
  - [Zeile 83](../../../tests/test_phase6_architecture.py#L83): ` assert args[3] == "Mistral" `
  - [Zeile 102](../../../tests/test_phase6_architecture.py#L102): ` assert [item["provider"] for item in result["model_answers"]] == ["Mistral", "Gemini"] `

<a id="cons-02"></a>

## CONS-02 · Strukturierte Differences und Agreement

Parser/Scorer akzeptieren nur zulässige Modelle, Claims, Anchors und bounded Werte; fehlende Analyse bleibt unbewertet statt Nullbeweis. Agreement und Claim-Coverage bleiben verschiedene Aussagen.

**Anforderungsbasis:** [docs/codebase-map.md](../../codebase-map.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** Synthetische JSON-/Textantworten; Validierung sichert Form/Provenienz, nicht Wahrheit oder Kalibrierung.

**Befunde:** —. Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [app/services/llm/consensus_engine.py](../../../app/services/llm/consensus_engine.py)
- [app/services/llm/consensus_parsing.py](../../../app/services/llm/consensus_parsing.py)
- [app/services/llm/consensus_scoring.py](../../../app/services/llm/consensus_scoring.py)
- [app/services/llm/coverage_judge.py](../../../app/services/llm/coverage_judge.py)

**Testdateien:**

- [tests/test_analysis_quality_budget.py](../../../tests/test_analysis_quality_budget.py)
- [tests/test_consensus_answer_contract.py](../../../tests/test_consensus_answer_contract.py)
- [tests/test_consensus_engine.py](../../../tests/test_consensus_engine.py)
- [tests/test_coverage_judge.py](../../../tests/test_coverage_judge.py)
- [tests/test_differences_schema.py](../../../tests/test_differences_schema.py)

</details>

**Konkrete Teilbelege:**

- [test_empty_or_sparse_evidence_does_not_create_a_numeric_score](../../../tests/test_analysis_quality_budget.py#L28) — Scoring-/Snapshot-/Budgetlogik und HTTPX-MockTransport. Historischer **Datei**status: passed=14.
  - [Zeile 31](../../../tests/test_analysis_quality_budget.py#L31): ` assert result["score"] is None `
  - [Zeile 32](../../../tests/test_analysis_quality_budget.py#L32): ` assert result["level"] == "insufficient" `
  - [Zeile 33](../../../tests/test_analysis_quality_budget.py#L33): ` assert result["coverage_status"] == "insufficient" `
  - [Zeile 34](../../../tests/test_analysis_quality_budget.py#L34): ` assert score([claim()] + [claim(()) for _ in range(19)])["coverage_percent"] == 5 `

<a id="cons-03"></a>

## CONS-03 · Quellenkatalog und Zitatprovenienz

Quellen werden normalisiert, nummeriert und an den richtigen Run/Antworttext gebunden; unbekannte IDs und falsche Zitatzuordnung werden nicht als verifiziert dargestellt.

**Anforderungsbasis:** [docs/codebase-map.md](../../codebase-map.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** Formaler Parser/DOM-Vertrag; keine externe Quellenwahrheit.

**Befunde:** —. Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [app/services/llm/citations.py](../../../app/services/llm/citations.py)
- [app/services/llm/consensus_citations.py](../../../app/services/llm/consensus_citations.py)
- [app/services/source_catalog.py](../../../app/services/source_catalog.py)
- [static/js/sources.js](../../../static/js/sources.js)

**Testdateien:**

- [tests/js/agent-citations.test.mjs](../../../tests/js/agent-citations.test.mjs)
- [tests/js/source-catalog-refs.test.mjs](../../../tests/js/source-catalog-refs.test.mjs)
- [tests/test_citations.py](../../../tests/test_citations.py)
- [tests/test_consensus_citations.py](../../../tests/test_consensus_citations.py)
- [tests/test_source_catalog.py](../../../tests/test_source_catalog.py)

</details>

**Konkrete Teilbelege:**

- [resolves sparse IDs by identity and leaves missing citations unresolved](../../../tests/js/source-catalog-refs.test.mjs#L14) — JavaScript-Modultest mit jsdom. Historischer **Datei**status: passed=4.
  - [Zeile 18](../../../tests/js/source-catalog-refs.test.mjs#L18): ` expect(refs.map(item => item.src?.url || null)).toEqual([null, 'https://two.example', 'https://seven.example']); `

<a id="cons-04"></a>

## CONS-04 · Resolve als eigener Lauf

Resolve verwendet vorhandene Konflikte/Kontext, bleibt tier-/ownergebunden und nutzt eigenen Usage-Key. Ein abgeschlossener Resolve wird korrekt gespeichert und angezeigt.

**Anforderungsbasis:** [docs/codebase-map.md](../../codebase-map.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** Backend lokal; Browseraktionen teils nur Fixture-UI. Durchgehender Resolve→Persistenz-Vertrag nicht ausgeführt.

**Befunde:** —. Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [app/api/routers/chat.py](../../../app/api/routers/chat.py)
- [app/services/llm/resolve_engine.py](../../../app/services/llm/resolve_engine.py)
- [static/js/consensus-actions.js](../../../static/js/consensus-actions.js)

**Testdateien:**

- [tests/e2e/test_inspector_polish.py](../../../tests/e2e/test_inspector_polish.py)
- [tests/e2e/test_smoke.py](../../../tests/e2e/test_smoke.py)
- [tests/test_resolve_round.py](../../../tests/test_resolve_round.py)

</details>

**Konkrete Teilbelege:**

- [test_resolve_does_not_persist_after_the_bookmark_revision_advanced](../../../tests/test_resolve_round.py#L400) — Resolve-Unit-/Routertests mit Engine-/DB-Doubles. Historischer **Datei**status: passed=23.
  - [Zeile 438](../../../tests/test_resolve_round.py#L438): ` assert persisted is False `
  - [Zeile 439](../../../tests/test_resolve_round.py#L439): ` assert "resolution" not in bookmark_ref.data["responses"]["differences_data"]["differences"][0] `

<a id="cons-05"></a>

## CONS-05 · Finalisierung, Replay und Browser-Recovery

Erfolgsevent folgt dem autoritativen Abschluss; completed Replay ruft weder Engine noch Usage erneut auf. Unklarer Streamabbruch wird am Turnstatus reconciliert, Analysefehler vernichtet keine bereits gelieferte Antwort.

**Anforderungsbasis:** [docs/codebase-map.md](../../codebase-map.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** SSE-Schnipsel/TestClient/Fake-Requests; keine durchgehende Socket→Server→DB→Reload-Prüfung.

**Befunde:** [G-030](gaps.md#g-030). Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [app/api/routers/chat.py](../../../app/api/routers/chat.py)
- [static/js/chat-session.js](../../../static/js/chat-session.js)
- [static/js/consensus-lifecycle.js](../../../static/js/consensus-lifecycle.js)
- [static/js/consensus-run.js](../../../static/js/consensus-run.js)
- [static/js/query-send.js](../../../static/js/query-send.js)

**Testdateien:**

- [tests/e2e/test_run_cancel_and_progress.py](../../../tests/e2e/test_run_cancel_and_progress.py)
- [tests/js/consensus-recovery.test.mjs](../../../tests/js/consensus-recovery.test.mjs)
- [tests/js/judge-stream-events.test.mjs](../../../tests/js/judge-stream-events.test.mjs)
- [tests/js/sse-completion.test.mjs](../../../tests/js/sse-completion.test.mjs)
- [tests/test_consensus_chat_history.py](../../../tests/test_consensus_chat_history.py)

</details>

**Konkrete Teilbelege:**

- [recovers a committed turn through GET without another generation, vote or save](../../../tests/js/consensus-recovery.test.mjs#L40) — JavaScript-Modulintegration mit Request-/Stream-Doubles. Historischer **Datei**status: passed=6.
  - [Zeile 43](../../../tests/js/consensus-recovery.test.mjs#L43): ` expect(context.status, context.consensus.error?.message).toBe('succeeded'); `
  - [Zeile 44](../../../tests/js/consensus-recovery.test.mjs#L44): ` expect(context.consensus.text).toBe('Stored answer'); `
  - [Zeile 45](../../../tests/js/consensus-recovery.test.mjs#L45): ` expect(context.consensus.resultId).toBe('stored-result'); `
  - [Zeile 46](../../../tests/js/consensus-recovery.test.mjs#L46): ` expect(context.chatSession.handleConsensusResult).toHaveBeenCalledWith(expect.objectContaining({ chatTurnState: 'completed' })); `
  - [Zeile 47](../../../tests/js/consensus-recovery.test.mjs#L47): ` expect(window.streamSSERequest).toHaveBeenCalledOnce(); `
  - [Zeile 48](../../../tests/js/consensus-recovery.test.mjs#L48): `` expect(window.fetch).toHaveBeenCalledWith(`/chats/${'a'.repeat(32)}/turns/${'b'.repeat(32)}`, expect.objectContaining({ cache: 'no-store', headers: { Authorization: 'Bearer token' } })); ``
  - [Zeile 49](../../../tests/js/consensus-recovery.test.mjs#L49): ` expect(window.recordModelVote).not.toHaveBeenCalled(); `
  - [Zeile 50](../../../tests/js/consensus-recovery.test.mjs#L50): ` expect(window.saveBookmarkConsensus).not.toHaveBeenCalled(); `
  - [Zeile 51](../../../tests/js/consensus-recovery.test.mjs#L51): ` expect(window.App.reportCriticalError).not.toHaveBeenCalled(); `
- [test_consensus_persists_requested_bookmark_before_successful_final_event](../../../tests/test_consensus_chat_history.py#L249) — Router/SSE-Verträge mit RecordingStore und Engine-Doubles. Historischer **Datei**status: passed=52.
  - [Zeile 304](../../../tests/test_consensus_chat_history.py#L304): ` assert response.status_code == 200 `
  - [Zeile 305](../../../tests/test_consensus_chat_history.py#L305): ` assert body["bookmark_persisted"] is True `
  - [Zeile 306](../../../tests/test_consensus_chat_history.py#L306): ` assert body["bookmark_meta"]["id"] == "stable_bookmark" `
  - [Zeile 307](../../../tests/test_consensus_chat_history.py#L307): ` assert len(writes) == 1 `
  - [Zeile 309](../../../tests/test_consensus_chat_history.py#L309): ` assert uid == UID `
  - [Zeile 310](../../../tests/test_consensus_chat_history.py#L310): ` assert data["chatId"] == CHAT_ID `
  - [Zeile 311](../../../tests/test_consensus_chat_history.py#L311): ` assert data["turnId"] == TURN_ID `
  - [Zeile 312](../../../tests/test_consensus_chat_history.py#L312): ` assert data["previousTurn"]["consensus"] == "Earlier consensus" `
  - [Zeile 313](../../../tests/test_consensus_chat_history.py#L313): ` assert authoritative["model_responses"] == {         "OpenAI": "OpenAI answer",         "Mistral": "Mistral answer",     } `
  - [Zeile 317](../../../tests/test_consensus_chat_history.py#L317): ` assert store.completions `

<a id="agent-01"></a>

## AGENT-01 · Admission und Token-/Kostenledger

Modellaufrufe benötigen atomare Admission; Tokens, Kosten, Reserven und unbekannte Messungen bleiben getrennt. Settlement pro tatsächlichem Schritt ist idempotent, UTC-/Reset-Versionen ordnen Budgetstände.

**Anforderungsbasis:** [docs/agent-accounting-audit.md](../../agent-accounting-audit.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** Reale Emulatorbelege für ausgewählte Rennen vorhanden; kein vollständiger produktiver Mehrprozess-/Providerablauf.

**Befunde:** —. Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [app/services/agent_budget_config.py](../../../app/services/agent_budget_config.py)
- [app/services/agent_costs.py](../../../app/services/agent_costs.py)
- [app/services/agent_provider_limits.py](../../../app/services/agent_provider_limits.py)
- [app/services/agent_quota.py](../../../app/services/agent_quota.py)
- [app/services/agent_runs.py](../../../app/services/agent_runs.py)
- [app/services/agent_sessions.py](../../../app/services/agent_sessions.py)
- [app/services/agent_tokens.py](../../../app/services/agent_tokens.py)

**Testdateien:**

- [tests/e2e/test_agent_transactions.py](../../../tests/e2e/test_agent_transactions.py)
- [tests/test_agent_accounting_audit.py](../../../tests/test_agent_accounting_audit.py)
- [tests/test_agent_admission.py](../../../tests/test_agent_admission.py)
- [tests/test_agent_budget_config.py](../../../tests/test_agent_budget_config.py)
- [tests/test_agent_capacity.py](../../../tests/test_agent_capacity.py)
- [tests/test_agent_quota_recovery.py](../../../tests/test_agent_quota_recovery.py)

</details>

**Konkrete Teilbelege:**

- [test_final_usage_replaces_cumulative_values_and_releases_reservation](../../../tests/test_agent_accounting_audit.py#L85) — Abrechnung über realen Agent-Loop und geskripteten Transport. Historischer **Datei**status: passed=58.
  - [Zeile 91](../../../tests/test_agent_accounting_audit.py#L91): ` assert budget['used'] == 130 and budget['reserved'] == budget['unknown'] == 0 `
  - [Zeile 92](../../../tests/test_agent_accounting_audit.py#L92): ` assert loop.completion.usage['complete'] `

<a id="agent-02"></a>

## AGENT-02 · Chatpolicy und Legacy-Toolloop

Agent-Chat erlaubt registrierte Tools/Modelle und verwendet das atomare Kontotokenbudget; aktive Chats haben keine alten Gesamtzeit-/Call-/Suchlimits. Parallelität, Nachrichtenformate, Provider-Kontext und Stillstandsfristen bleiben begrenzt. Legacy-AgentLoop behält seine separate begrenzte Policy.

**Anforderungsbasis:** [docs/codebase-map.md](../../codebase-map.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** Gesteuerte Tool-/Providerantworten; richtige Aufgabenverteilung/Urteilsqualität ist damit nicht gemessen.

**Befunde:** —. Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [app/api/routers/agent.py](../../../app/api/routers/agent.py)
- [app/services/agent_comparison.py](../../../app/services/agent_comparison.py)
- [app/services/agent_contradictions.py](../../../app/services/agent_contradictions.py)
- [app/services/agent_loop.py](../../../app/services/agent_loop.py)
- [app/services/agent_policy.py](../../../app/services/agent_policy.py)
- [app/services/agent_tools.py](../../../app/services/agent_tools.py)
- [app/services/llm/agent_client.py](../../../app/services/llm/agent_client.py)

**Testdateien:**

- [tests/test_agent_comparison.py](../../../tests/test_agent_comparison.py)
- [tests/test_agent_continuation.py](../../../tests/test_agent_continuation.py)
- [tests/test_agent_contradictions.py](../../../tests/test_agent_contradictions.py)
- [tests/test_agent_loop.py](../../../tests/test_agent_loop.py)
- [tests/test_agent_reliability.py](../../../tests/test_agent_reliability.py)
- [tests/test_agent_search.py](../../../tests/test_agent_search.py)
- [tests/test_agent_synthesis_context.py](../../../tests/test_agent_synthesis_context.py)

</details>

**Konkrete Teilbelege:**

- [test_more_than_one_hundred_steps_and_seventeen_minutes_complete_with_live_lease](../../../tests/test_agent_continuation.py#L46) — Langlauf-/Recovery-Verträge mit Fake-Uhr, Store und Providern. Historischer **Datei**status: passed=13.
  - [Zeile 66](../../../tests/test_agent_continuation.py#L66): ` assert loop.budget.deadline == float("inf") `
  - [Zeile 70](../../../tests/test_agent_continuation.py#L70): ` assert saved["status"] == "completed" and saved["consensus"] == "Finished after many rounds." `
  - [Zeile 71](../../../tests/test_agent_continuation.py#L71): ` assert timer.stamp - started == timedelta(minutes=17) `
  - [Zeile 72](../../../tests/test_agent_continuation.py#L72): ` assert root["step_states"]["completion:101"] == "succeeded" `
  - [Zeile 73](../../../tests/test_agent_continuation.py#L73): ` assert root["policy"]["seconds"] is None and root["policy"]["max_calls"] is None `
  - [Zeile 74](../../../tests/test_agent_continuation.py#L74): ` assert loop.tools_used == 101 and loop.budget.calls == 102 `
  - [Zeile 75](../../../tests/test_agent_continuation.py#L75): ` assert totals(store)["unsettled_calls"] == 0 `
  - [Zeile 76](../../../tests/test_agent_continuation.py#L76): ` assert all(searches) `
  - [Zeile 78](../../../tests/test_agent_continuation.py#L78): ` assert quota["used"] == 102 * 120 and quota["reserved"] == 0 `
- [test_consensus_and_legacy_analysis_budgets_remain_bounded](../../../tests/test_agent_continuation.py#L155) — Langlauf-/Recovery-Verträge mit Fake-Uhr, Store und Providern. Historischer **Datei**status: passed=13.
  - [Zeile 157](../../../tests/test_agent_continuation.py#L157): ` with pytest.raises(AnalysisBudgetExceeded, match="deadline"): `
  - [Zeile 159](../../../tests/test_agent_continuation.py#L159): ` assert not AgentPolicy.from_config(defaults()).account_budget_only `

<a id="agent-03"></a>

## AGENT-03 · Delegierte Sitzungen und Kommunikation

Orchestrator und Worker besitzen eigene Identitäten/Verläufe, geordnete deduplizierte Nachrichten und gemeinsames Budget. Stop und verspätete Workerergebnisse dürfen keine neuen bezahlten Schritte oder falschen Turnwrites verursachen.

**Anforderungsbasis:** [docs/codebase-map.md](../../codebase-map.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** Lokale Threads und Emulatorbudget, Browser-API ersetzt. Historische Delegation-Spezifikation ist teilweise überholt.

**Befunde:** —. Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [app/services/agent_delegation.py](../../../app/services/agent_delegation.py)
- [app/services/agent_delegation_config.py](../../../app/services/agent_delegation_config.py)
- [app/services/agent_sessions.py](../../../app/services/agent_sessions.py)
- [static/js/agent-delegation.js](../../../static/js/agent-delegation.js)

**Testdateien:**

- [tests/e2e/test_agent_delegation_frontend.py](../../../tests/e2e/test_agent_delegation_frontend.py)
- [tests/e2e/test_agent_transactions.py](../../../tests/e2e/test_agent_transactions.py)
- [tests/js/agent-delegation.test.mjs](../../../tests/js/agent-delegation.test.mjs)
- [tests/test_agent_delegation.py](../../../tests/test_agent_delegation.py)
- [tests/test_agent_reliability.py](../../../tests/test_agent_reliability.py)

</details>

**Konkrete Teilbelege:**

- [test_parallel_question_answer_rework_and_review_persist_same_session_and_total_costs](../../../tests/test_agent_delegation.py#L102) — Echte Workerthreads/Mailboxen mit Store- und Provider-Doubles. Historischer **Datei**status: passed=16.
  - [Zeile 106](../../../tests/test_agent_delegation.py#L106): ` assert loop.completion.text == "Product 6; sum 5." `
  - [Zeile 107](../../../tests/test_agent_delegation.py#L107): ` assert len(loop.workers) == 2 `
  - [Zeile 108](../../../tests/test_agent_delegation.py#L108): ` assert script.actions.count("start_agent") == 2 and script.actions.count("send_agent") == 2 `
  - [Zeile 109](../../../tests/test_agent_delegation.py#L109): ` assert all(w.reviewed and not w.thread.is_alive() for w in loop.workers.values()) `
  - [Zeile 113](../../../tests/test_agent_delegation.py#L113): ` assert [m["kind"] for m in messages] == ["question", "answer", "result", "rework", "result", "review"] `
  - [Zeile 114](../../../tests/test_agent_delegation.py#L114): ` assert [m["text"] for m in messages if m["kind"] == "result"] == ["5", "6"] `
  - [Zeile 115](../../../tests/test_agent_delegation.py#L115): ` assert detail["agent"]["assignment"]["goal"] == "multiply" `
  - [Zeile 116](../../../tests/test_agent_delegation.py#L116): ` assert any(e.get("agent", {}).get("status") == "question" for e in events) `
  - [Zeile 118](../../../tests/test_agent_delegation.py#L118): ` assert seqs == sorted(set(seqs)) `
  - [Zeile 119](../../../tests/test_agent_delegation.py#L119): ` assert totals(store)["calls"] == loop.costs.calls `
  - [Zeile 120](../../../tests/test_agent_delegation.py#L120): ` assert totals(store)["estimated_cost_nano_usd"] == loop.costs.calls * 200_000 `
  - [Zeile 121](../../../tests/test_agent_delegation.py#L121): ` assert loop.completion.usage["estimated_cost_nano_usd"] == totals(store)["estimated_cost_nano_usd"] `
  - [Zeile 122](../../../tests/test_agent_delegation.py#L122): ` assert detail["agent"]["usage"]["estimated_cost_nano_usd"] == 600_000 `
  - [Zeile 124](../../../tests/test_agent_delegation.py#L124): ` assert view["usage"] == loop.completion.usage `
  - [Zeile 126](../../../tests/test_agent_delegation.py#L126): ` assert page["has_more"] and len(page["messages"]) == 2 `
  - [Zeile 128](../../../tests/test_agent_delegation.py#L128): ` assert len(next_page["messages"]) == 4 `
  - [Zeile 129](../../../tests/test_agent_delegation.py#L129): ` with pytest.raises(ChatNotFound): `

<a id="agent-04"></a>

## AGENT-04 · Agent-Recovery und Eigentümerbindung

Run-/Turn-/Agentdetails sind ownergebunden; recover_only startet nie Modelle. Abgelaufene Leases werden ohne Doppelverbrauch beendet, bestätigte Antworten und Usage bleiben lesbar.

**Anforderungsbasis:** [docs/agent-reliability-audit-2026-09-20.md](../../agent-reliability-audit-2026-09-20.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** Prozesscrash durch Zustand/IDs/Uhr simuliert; Socket-Stall-Test nutzt MockTransport.

**Befunde:** [G-030](gaps.md#g-030). Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [app/api/routers/agent.py](../../../app/api/routers/agent.py)
- [app/services/agent_runs.py](../../../app/services/agent_runs.py)
- [app/services/agent_runtime.py](../../../app/services/agent_runtime.py)
- [app/services/agent_sessions.py](../../../app/services/agent_sessions.py)

**Testdateien:**

- [tests/test_agent_answer_lifecycle.py](../../../tests/test_agent_answer_lifecycle.py)
- [tests/test_agent_chat_integrity.py](../../../tests/test_agent_chat_integrity.py)
- [tests/test_agent_quota_recovery.py](../../../tests/test_agent_quota_recovery.py)
- [tests/test_agent_reliability.py](../../../tests/test_agent_reliability.py)
- [tests/test_agent_runs.py](../../../tests/test_agent_runs.py)

</details>

**Konkrete Teilbelege:**

- [test_recovery_never_starts_a_new_call](../../../tests/test_agent_runs.py#L275) — Store-/API-Verträge mit Auth-/Transport-Doubles. Historischer **Datei**status: passed=38.
  - [Zeile 280](../../../tests/test_agent_runs.py#L280): ` assert response.status_code == 404 `
  - [Zeile 281](../../../tests/test_agent_runs.py#L281): ` assert calls == [] `
  - [Zeile 282](../../../tests/test_agent_runs.py#L282): ` assert store.get_chat(UID, chat_id)["turn_count"] == 0 `

<a id="agent-05"></a>

## AGENT-05 · Agent-Ansicht und bestätigter Fortschritt

Sidebar/Antworten zeigen echte Ereignisse, Reasoning getrennt vom Antworttext, bekannte Kosten versus pending; historische Laufzeiten frieren ein. View-/Authwechsel unterdrücken verspätete Projektionen.

**Anforderungsbasis:** [docs/codebase-map.md](../../codebase-map.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** jsdom führt Logik aus, Geometrie/Fokusfälle ausschließlich im nicht ausgeführten Browserbestand.

**Befunde:** —. Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [app/services/agent_progress.py](../../../app/services/agent_progress.py)
- [static/js/agent-activity.js](../../../static/js/agent-activity.js)
- [static/js/agent-answer-actions.js](../../../static/js/agent-answer-actions.js)
- [static/js/agent-chat.js](../../../static/js/agent-chat.js)
- [static/js/agent-review.js](../../../static/js/agent-review.js)
- [static/js/sidebar-quota.js](../../../static/js/sidebar-quota.js)

**Testdateien:**

- [tests/e2e/test_agent_chat_frontend.py](../../../tests/e2e/test_agent_chat_frontend.py)
- [tests/e2e/test_agent_comparison_frontend.py](../../../tests/e2e/test_agent_comparison_frontend.py)
- [tests/e2e/test_agent_delegation_frontend.py](../../../tests/e2e/test_agent_delegation_frontend.py)
- [tests/e2e/test_agent_status_frontend.py](../../../tests/e2e/test_agent_status_frontend.py)
- [tests/js/agent-answer-actions.test.mjs](../../../tests/js/agent-answer-actions.test.mjs)
- [tests/js/agent-chat.test.mjs](../../../tests/js/agent-chat.test.mjs)
- [tests/js/agent-review.test.mjs](../../../tests/js/agent-review.test.mjs)
- [tests/js/sidebar-quota.test.mjs](../../../tests/js/sidebar-quota.test.mjs)
- [tests/test_agent_progress.py](../../../tests/test_agent_progress.py)

</details>

**Konkrete Teilbelege:**

- [test_short_highlights_update_at_boundaries_and_remain_bounded](../../../tests/test_agent_progress.py#L14) — Fortschrittsfunktionen und Loop mit kontrollierter Uhr/Providern. Historischer **Datei**status: passed=10.
  - [Zeile 16](../../../tests/test_agent_progress.py#L16): ` assert progress.update(event("Checking the ")) is None `
  - [Zeile 18](../../../tests/test_agent_progress.py#L18): ` assert first["text"] == "Checking the available evidence." `
  - [Zeile 19](../../../tests/test_agent_progress.py#L19): ` assert first["summary_source"] == "excerpt" and first["append"] is False `
  - [Zeile 20](../../../tests/test_agent_progress.py#L20): ` assert progress.update(event(" Next")) is None `
  - [Zeile 24](../../../tests/test_agent_progress.py#L24): ` assert len(value["text"]) <= 542 `
  - [Zeile 25](../../../tests/test_agent_progress.py#L25): ` assert len(value["text"].splitlines()) <= 3 `
  - [Zeile 26](../../../tests/test_agent_progress.py#L26): ` assert progress.updates <= 8 and len(progress.text) <= 8000 `

<a id="src-01"></a>

## SRC-01 · Sicherer begrenzter Quellenabruf

Abruf validiert URL, DNS, Redirects und Ziel-IP, erhält Host/SNI und begrenzt Bytes/Zeit; Fehler-/Singleflight-Caches dürfen Ownerdaten nicht vermischen.

**Anforderungsbasis:** [docs/source-verification.md](../../source-verification.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** DNS/HTTP/TLS ersetzt; reale Zertifikats-/Redirectverbindung und Streaming-Dekompression nicht als Integration ausgeführt.

**Befunde:** [G-032](gaps.md#g-032). Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [app/services/source_documents.py](../../../app/services/source_documents.py)
- [app/services/source_verification.py](../../../app/services/source_verification.py)

**Testdateien:**

- [tests/test_source_verification.py](../../../tests/test_source_verification.py)

</details>

**Konkrete Teilbelege:**

- [test_fetch_pins_ip_and_checks_redirect_again](../../../tests/test_source_verification.py#L436) — Verifikations-/Dokument-/Pipeline-Integration mit Fetch/Judge/HTTPX-Doubles und Threads. Historischer **Datei**status: passed=122.
  - [Zeile 443](../../../tests/test_source_verification.py#L443): ` assert request.url.host == '93.184.216.34' `
  - [Zeile 444](../../../tests/test_source_verification.py#L444): ` assert request.headers['host'] == 'example.com' `
  - [Zeile 445](../../../tests/test_source_verification.py#L445): ` assert request.extensions['sni_hostname'] == 'example.com' `
  - [Zeile 449](../../../tests/test_source_verification.py#L449): ` with pytest.raises(ValueError, match='unsafe_address'): `
  - [Zeile 451](../../../tests/test_source_verification.py#L451): ` assert len(calls) == 1 `

<a id="src-02"></a>

## SRC-02 · Prüfplan und konservative Urteile

Nur geeignete Widersprüche werden anhand vorhandener Quellen geprüft; beide Positionen, Originalzitate und Run-/Antwortbindung sind erforderlich. Disabled/skipped/unavailable/unresolved sind unterschiedliche Zustände.

**Anforderungsbasis:** [docs/source-judge-spec.md](../../source-judge-spec.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** Synthetische Belege und Judgeantworten; kein fachlicher Evaluationsnachweis.

**Befunde:** —. Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [app/services/contradiction_verification.py](../../../app/services/contradiction_verification.py)
- [app/services/llm/coverage_judge.py](../../../app/services/llm/coverage_judge.py)
- [app/services/source_verification.py](../../../app/services/source_verification.py)

**Testdateien:**

- [tests/test_analysis_quality_budget.py](../../../tests/test_analysis_quality_budget.py)
- [tests/test_contradiction_verification.py](../../../tests/test_contradiction_verification.py)
- [tests/test_source_judge_fallback.py](../../../tests/test_source_judge_fallback.py)
- [tests/test_source_verification.py](../../../tests/test_source_verification.py)

</details>

**Konkrete Teilbelege:**

- [test_original_evidence_validation_rejects_invented_or_incomplete_verdicts](../../../tests/test_contradiction_verification.py#L177) — Deterministische Planungs-/Validierungs- und Ausführungstests mit injizierten Fetch/Judge-Funktionen. Historischer **Datei**status: passed=64.
  - [Zeile 193](../../../tests/test_contradiction_verification.py#L193): ` assert not result['findings'][0]['checked'] `
  - [Zeile 194](../../../tests/test_contradiction_verification.py#L194): ` assert result['findings'][0]['reason_code'] in ('evidence_mismatch', 'invalid_output') `

<a id="src-03"></a>

## SRC-03 · Dauerhafte Jobqueue und Credentials

Claims/Resultwrites sind lease-/revisionsgebunden; eigene Keys bleiben im Prozessspeicher, kein Developer-Fallback. Stale Writes/Ownerlöschung/Versionswechsel dürfen alte Ergebnisse nicht an neue Antworten hängen.

**Anforderungsbasis:** [docs/codebase-map.md](../../codebase-map.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** Fake-Transaktionen und simulierte Worker; kein Firestore-Emulator-/Mehrprozessvertrag für diese Queue.

**Befunde:** [G-006](gaps.md#g-006). Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [app/services/source_check_jobs.py](../../../app/services/source_check_jobs.py)
- [app/services/source_check_repository.py](../../../app/services/source_check_repository.py)

**Testdateien:**

- [tests/test_contradiction_jobs.py](../../../tests/test_contradiction_jobs.py)
- [tests/test_source_check_jobs.py](../../../tests/test_source_check_jobs.py)
- [tests/test_source_check_repository.py](../../../tests/test_source_check_repository.py)
- [tests/test_source_check_scope.py](../../../tests/test_source_check_scope.py)

</details>

**Konkrete Teilbelege:**

- [test_expired_lease_reclaims_unfinished_package_and_rejects_stale_worker](../../../tests/test_source_check_repository.py#L214) — Repository mit lockbasiertem FakeDb und Threads. Historischer **Datei**status: passed=36.
  - [Zeile 219](../../../tests/test_source_check_repository.py#L219): ` assert repo.claim(job["job_id"], now=now + timedelta(seconds=LEASE_SECONDS - 1)) is None `
  - [Zeile 221](../../../tests/test_source_check_repository.py#L221): ` assert second["lease_token"] != first["lease_token"] `
  - [Zeile 222](../../../tests/test_source_check_repository.py#L222): ` assert second["completed_packages"] == 0 `
  - [Zeile 224](../../../tests/test_source_check_repository.py#L224): ` assert not repo.finish_package(first, result) `
  - [Zeile 225](../../../tests/test_source_check_repository.py#L225): ` assert not repo.retry(first) `
  - [Zeile 226](../../../tests/test_source_check_repository.py#L226): ` assert repo.finish_package(second, result) `
  - [Zeile 227](../../../tests/test_source_check_repository.py#L227): ` assert repo.get(job["job_id"])["completed_packages"] == 1 `
- [test_restart_pauses_own_key_work_without_developer_fallback_then_owner_resumes](../../../tests/test_source_check_jobs.py#L80) — Job-Worker mit FakeDb/Fetch/Judge und simulierten Workeridentitäten. Historischer **Datei**status: passed=23.
  - [Zeile 89](../../../tests/test_source_check_jobs.py#L89): ` assert jobs.process_one(repo) `
  - [Zeile 90](../../../tests/test_source_check_jobs.py#L90): ` assert repo.get(snapshot['job_id'])['status'] == 'awaiting_credentials' `
  - [Zeile 91](../../../tests/test_source_check_jobs.py#L91): ` assert used == [] `
  - [Zeile 93](../../../tests/test_source_check_jobs.py#L93): ` assert resumed['job_id'] == snapshot['job_id'] and resumed['status'] == 'queued' `
  - [Zeile 94](../../../tests/test_source_check_jobs.py#L94): ` assert jobs.process_one(repo) `
  - [Zeile 95](../../../tests/test_source_check_jobs.py#L95): ` assert used == [{'OpenRouter': 'replacement-secret'}] `

<a id="src-04"></a>

## SRC-04 · Private und öffentliche Jobseiten

Jede Seite prüft Owner oder aktive öffentliche Ressource sowie Run/Antwort/Revision; Pagination darf bei geändertem Stand nicht mischen, eigene Keys dürfen nicht persistieren.

**Anforderungsbasis:** [docs/codebase-map.md](../../codebase-map.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** Öffentliche Share-/Topicdaten und Auth ersetzt; API-v1-Adapter besitzt gesonderte Lücke.

**Befunde:** [G-010](gaps.md#g-010). Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [app/api/routers/api_v1.py](../../../app/api/routers/api_v1.py)
- [app/api/routers/source_checks.py](../../../app/api/routers/source_checks.py)

**Testdateien:**

- [tests/test_source_check_api.py](../../../tests/test_source_check_api.py)
- [tests/test_source_check_scope.py](../../../tests/test_source_check_scope.py)

</details>

**Konkrete Teilbelege:**

- [test_v4_public_share_rejects_wrong_job_version_on_every_page](../../../tests/test_source_check_api.py#L125) — Router mit SourceCheckRepository/FakeDb und Share-/Topic-Doubles. Historischer **Datei**status: passed=14.
  - [Zeile 138](../../../tests/test_source_check_api.py#L138): ` assert client.get(url, params=params).status_code == 200 `
  - [Zeile 140](../../../tests/test_source_check_api.py#L140): ` assert client.get(url, params=params).status_code == 404 `

<a id="src-05"></a>

## SRC-05 · Sources-/Differences-UI und Nachladen

UI unterscheidet alle Prüfzustände, zeigt Originalpassagen und bindet verspätete Seiten an Run/Ansicht/Auth. Legacyberichte bleiben lesbar; Filter entfernen unsichtbare Interaktionen ohne Befunde zu verlieren.

**Anforderungsbasis:** [docs/codebase-map.md](../../codebase-map.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** Fixture-Daten/DOM, Browser nicht ausgeführt; keine Qualitätsbehauptung über den Judge.

**Befunde:** —. Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [static/js/consensus-insights.js](../../../static/js/consensus-insights.js)
- [static/js/source-verification.js](../../../static/js/source-verification.js)
- [static/js/sources.js](../../../static/js/sources.js)

**Testdateien:**

- [tests/e2e/test_contradiction_source_ui.py](../../../tests/e2e/test_contradiction_source_ui.py)
- [tests/e2e/test_phase4_frontend.py](../../../tests/e2e/test_phase4_frontend.py)
- [tests/js/admin-source-model.test.mjs](../../../tests/js/admin-source-model.test.mjs)
- [tests/js/bookmark-source-check.test.mjs](../../../tests/js/bookmark-source-check.test.mjs)
- [tests/js/claim-coverage-states.test.mjs](../../../tests/js/claim-coverage-states.test.mjs)
- [tests/js/contradiction-source-verification.test.mjs](../../../tests/js/contradiction-source-verification.test.mjs)
- [tests/js/source-catalog-refs.test.mjs](../../../tests/js/source-catalog-refs.test.mjs)
- [tests/js/source-teaser-check.test.mjs](../../../tests/js/source-teaser-check.test.mjs)
- [tests/js/source-verification-watch.test.mjs](../../../tests/js/source-verification-watch.test.mjs)
- [tests/js/source-verification.test.mjs](../../../tests/js/source-verification.test.mjs)

</details>

**Konkrete Teilbelege:**

- [keeps the compact Sources verdict honest across result and run changes](../../../tests/js/source-verification.test.mjs#L16) — JavaScript-Modulintegration mit jsdom. Historischer **Datei**status: passed=21.
  - [Zeile 37](../../../tests/js/source-verification.test.mjs#L37): ` expect(tab.dataset.checkState).toBe(state); `
  - [Zeile 38](../../../tests/js/source-verification.test.mjs#L38): ` expect(tab.querySelectorAll('.consensus-source-check-icon')).toHaveLength(1); `
  - [Zeile 39](../../../tests/js/source-verification.test.mjs#L39): ` expect(tab.querySelector('.consensus-source-check-icon').textContent).toBe(icon); `
  - [Zeile 40](../../../tests/js/source-verification.test.mjs#L40): ` expect(tab.querySelector('.consensus-source-check-icon').getAttribute('aria-hidden')).toBe('true'); `
  - [Zeile 42](../../../tests/js/source-verification.test.mjs#L42): ` expect(tab.title).toBe('View sources'); `

<a id="share-01"></a>

## SHARE-01 · Autoritative Share-Erstellung

Ein gültiger eigener Pending-Run wird idempotent veröffentlicht; Sichtbarkeit, Quota und Snapshot werden gemeinsam entschieden. Clientinhalt darf kein fremdes oder erfundenes Resultat materialisieren.

**Anforderungsbasis:** [docs/codebase-map.md](../../codebase-map.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** Repository breit geprüft; der App-POST-/api/share-Adapter wird nicht ausgeführt. Emulator-Publish-Race scheitert bereits an veralteter Fixture.

**Befunde:** [G-011](gaps.md#g-011), [G-027](gaps.md#g-027). Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [app/api/routers/share.py](../../../app/api/routers/share.py)
- [app/services/share_snapshots.py](../../../app/services/share_snapshots.py)
- [static/js/share-dialog.js](../../../static/js/share-dialog.js)

**Testdateien:**

- [tests/e2e/test_phase2_transactions.py](../../../tests/e2e/test_phase2_transactions.py)
- [tests/test_consensus_api.py](../../../tests/test_consensus_api.py)
- [tests/test_share_feature.py](../../../tests/test_share_feature.py)

</details>

**Konkrete Teilbelege:**

- [ShareFlowTests::test_create_share_is_idempotent](../../../tests/test_share_feature.py#L780) — Große Unit-/Service-/Router-/SSR-Suite mit FakeDb und lokalen Cachethreads. Historischer **Datei**status: passed=151.
  - [Zeile 790](../../../tests/test_share_feature.py#L790): ` self.assertEqual(first["share_id"], second["share_id"]) `
  - [Zeile 791](../../../tests/test_share_feature.py#L791): ` self.assertFalse(second["created"]) `
  - [Zeile 792](../../../tests/test_share_feature.py#L792): ` self.assertEqual(len(quota_calls), 1) `

<a id="share-02"></a>

## SHARE-02 · Öffentliche und private Darstellung

Status/Sichtbarkeit und gewählte Version bestimmen Inhalt, Quellen, Canonical und noindex; Legacy-Citations und Markdown werden sicher dargestellt. Private Inhalte erscheinen nicht in öffentlichen Hubs/Sitemaps.

**Anforderungsbasis:** [docs/codebase-map.md](../../codebase-map.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** SSR mit Fake-Daten; nicht automatisch als Browser-Sanitizer-/CSP-Nachweis zu werten.

**Befunde:** —. Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [app/api/routers/share.py](../../../app/api/routers/share.py)
- [app/services/history_view.py](../../../app/services/history_view.py)
- [app/services/public_markdown.py](../../../app/services/public_markdown.py)
- [templates/questions.html](../../../templates/questions.html)
- [templates/share.html](../../../templates/share.html)
- [templates/share_unavailable.html](../../../templates/share_unavailable.html)

**Testdateien:**

- [tests/test_public_citation_cleanup.py](../../../tests/test_public_citation_cleanup.py)
- [tests/test_seo_basics.py](../../../tests/test_seo_basics.py)
- [tests/test_share_feature.py](../../../tests/test_share_feature.py)
- [tests/test_unscored_history.py](../../../tests/test_unscored_history.py)

</details>

**Konkrete Teilbelege:**

- [SharePageRouteTests::test_private_share_requires_owner_and_is_never_publicly_cached](../../../tests/test_share_feature.py#L1387) — Große Unit-/Service-/Router-/SSR-Suite mit FakeDb und lokalen Cachethreads. Historischer **Datei**status: passed=151.
  - [Zeile 1393](../../../tests/test_share_feature.py#L1393): ` self.assertEqual(denied.status_code, 403) `
  - [Zeile 1394](../../../tests/test_share_feature.py#L1394): ` self.assertNotIn("Photosynthese wandelt", denied.text) `
  - [Zeile 1400](../../../tests/test_share_feature.py#L1400): ` self.assertEqual(allowed.status_code, 200) `
  - [Zeile 1401](../../../tests/test_share_feature.py#L1401): ` self.assertEqual(allowed.headers["Cache-Control"], "private, no-store") `
  - [Zeile 1402](../../../tests/test_share_feature.py#L1402): ` self.assertIn("· Private", allowed.text) `
  - [Zeile 1403](../../../tests/test_share_feature.py#L1403): ` self.assertNotIn("Report this page", allowed.text) `
  - [Zeile 1404](../../../tests/test_share_feature.py#L1404): ` self.assertIn("noindex, nofollow", allowed.headers["X-Robots-Tag"]) `

<a id="share-03"></a>

## SHARE-03 · Reports, Moderation und Kaskade

Reports zählen ohne verlorene Inkremente; Schwellwerte und Adminentscheidungen steuern Index/Sichtbarkeit. Ownerlöschung entfernt abhängige Daten idempotent.

**Anforderungsbasis:** [docs/codebase-map.md](../../codebase-map.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** Report-Race im Primärlauf fehlgeschlagen, isoliert bestanden; Ursache offen. Fakes prüfen weitere Kaskaden.

**Befunde:** [G-029](gaps.md#g-029). Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [app/api/routers/admin.py](../../../app/api/routers/admin.py)
- [app/api/routers/share.py](../../../app/api/routers/share.py)
- [app/services/share_snapshots.py](../../../app/services/share_snapshots.py)

**Testdateien:**

- [tests/e2e/test_phase2_transactions.py](../../../tests/e2e/test_phase2_transactions.py)
- [tests/test_share_feature.py](../../../tests/test_share_feature.py)

</details>

**Konkrete Teilbelege:**

- [test_parallel_reports_never_lose_increments_or_noindex_transition](../../../tests/e2e/test_phase2_transactions.py#L161) — Firestore-Emulatorintegration mit echten SDK-Transaktionen und Threads. Historischer **Datei**status: failed=3, passed=1.
  - [Zeile 183](../../../tests/e2e/test_phase2_transactions.py#L183): ` assert sorted(counts) == list(range(1, 9)) `
  - [Zeile 184](../../../tests/e2e/test_phase2_transactions.py#L184): ` assert stored["reports_count"] == 8 `
  - [Zeile 185](../../../tests/e2e/test_phase2_transactions.py#L185): ` assert stored["report_reasons"] == {"spam": 8} `
  - [Zeile 186](../../../tests/e2e/test_phase2_transactions.py#L186): ` assert stored["needs_review"] is True `
  - [Zeile 187](../../../tests/e2e/test_phase2_transactions.py#L187): ` assert stored["indexed"] is False `

<a id="share-04"></a>

## SHARE-04 · Open-Graph-Karte

Aktive öffentliche Shares liefern eine PNG-Karte aus dem ausgewählten Antwortstand; private/inaktive Ressourcen bleiben verborgen, Frage und Kennzahlen müssen tatsächlich im Bild ankommen.

**Anforderungsbasis:** [docs/codebase-map.md](../../codebase-map.md) · ` documented_and_inferred_rendering_invariant `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** Bestehende OG-Assertions prüfen Meta/Status/MIME/PNG-Präfix. Eine gültige leere PNG kann sie erfüllen.

**Befunde:** [G-020](gaps.md#g-020). Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [app/api/routers/share.py](../../../app/api/routers/share.py)
- [app/services/og_image.py](../../../app/services/og_image.py)

**Testdateien:**

- [tests/test_share_feature.py](../../../tests/test_share_feature.py)

</details>

**Konkrete Teilbelege:**

- [ShareSeoEnhancementTests::test_og_card_route_and_meta](../../../tests/test_share_feature.py#L2459) — Große Unit-/Service-/Router-/SSR-Suite mit FakeDb und lokalen Cachethreads. Historischer **Datei**status: passed=151.
  - [Zeile 2466](../../../tests/test_share_feature.py#L2466): ` self.assertIn("/og.png", page.text) `
  - [Zeile 2467](../../../tests/test_share_feature.py#L2467): ` self.assertIn("summary_large_image", page.text) `
  - [Zeile 2468](../../../tests/test_share_feature.py#L2468): ` self.assertEqual(og.status_code, 200) `
  - [Zeile 2469](../../../tests/test_share_feature.py#L2469): ` self.assertEqual(og.headers["content-type"], "image/png") `
  - [Zeile 2470](../../../tests/test_share_feature.py#L2470): ` self.assertTrue(og.content.startswith(b"\x89PNG")) `

<a id="watch-01"></a>

## WATCH-01 · Watch-Erstellung und Planrechte

Watches sind ownergebunden, quota-/tierbegrenzt und verwenden konsistente Baseline-/Publisherlineage. Updates/Löschen dürfen fremde Watches und quittierte Löschbereiche nicht verändern.

**Anforderungsbasis:** [docs/codebase-map.md](../../codebase-map.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** Breite Fake-Tests; echtes Ownerlimit-Race scheitert vor der Konkurrenz an veraltetem is_pro-Aufruf.

**Befunde:** [G-013](gaps.md#g-013), [G-027](gaps.md#g-027). Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [app/api/routers/watch.py](../../../app/api/routers/watch.py)
- [app/services/watch_service.py](../../../app/services/watch_service.py)

**Testdateien:**

- [tests/e2e/test_phase2_transactions.py](../../../tests/e2e/test_phase2_transactions.py)
- [tests/test_plus_tier.py](../../../tests/test_plus_tier.py)
- [tests/test_watch_feature.py](../../../tests/test_watch_feature.py)

</details>

**Konkrete Teilbelege:**

- [WatchCrudTests::test_pause_delete_and_resume_keep_owner_counter_consistent](../../../tests/test_watch_feature.py#L410) — Große Service-/Scheduler-/Router-/Mailformat-Suite mit DB-/LLM-/Versand-Doubles plus UI-Sourceverträge. Historischer **Datei**status: passed=146.
  - [Zeile 420](../../../tests/test_watch_feature.py#L420): ` self.assertEqual(state_store["quota"]["active_count"], 2) `
  - [Zeile 425](../../../tests/test_watch_feature.py#L425): ` self.assertEqual(state_store["quota"]["active_count"], 1) `
  - [Zeile 429](../../../tests/test_watch_feature.py#L429): ` self.assertEqual(state_store["quota"]["active_count"], 2) `
  - [Zeile 431](../../../tests/test_watch_feature.py#L431): ` self.assertEqual(state_store["quota"]["active_count"], 1) `

<a id="watch-02"></a>

## WATCH-02 · Zeitplan, Claim und Ausführung

Lokale Zeit/DST, Lease und deterministische Run-ID erlauben einen Lauf je Slot. Aktueller Tarif/Modellplan, Budget und wiederholte Fehler bestimmen Ausführung/Pause; stale Worker dürfen keinen neuen Stand überschreiben.

**Anforderungsbasis:** [docs/codebase-map.md](../../codebase-map.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** Zeit/Fan-out/Claims überwiegend ersetzt; produktive Due-Query/Workerlease nicht vollständig mit echtem SDK ausgeführt.

**Befunde:** [G-031](gaps.md#g-031). Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [app/services/drift_signal.py](../../../app/services/drift_signal.py)
- [app/services/opinion_map.py](../../../app/services/opinion_map.py)
- [app/services/watch_scheduler.py](../../../app/services/watch_scheduler.py)
- [app/services/watch_service.py](../../../app/services/watch_service.py)

**Testdateien:**

- [tests/test_drift_signal.py](../../../tests/test_drift_signal.py)
- [tests/test_phase5_operations.py](../../../tests/test_phase5_operations.py)
- [tests/test_unscored_history.py](../../../tests/test_unscored_history.py)
- [tests/test_watch_feature.py](../../../tests/test_watch_feature.py)

</details>

**Konkrete Teilbelege:**

- [SchedulerSafetyTests::test_stale_run_cannot_complete_or_fail_newer_claim](../../../tests/test_watch_feature.py#L1065) — Große Service-/Scheduler-/Router-/Mailformat-Suite mit DB-/LLM-/Versand-Doubles plus UI-Sourceverträge. Historischer **Datei**status: passed=146.
  - [Zeile 1089](../../../tests/test_watch_feature.py#L1089): ` self.assertIsNone(             watch_service.complete_watch_run("w1", claimed, result, db=db)         ) `
  - [Zeile 1092](../../../tests/test_watch_feature.py#L1092): ` self.assertIsNone(watch_service.fail_watch_run("w1", claimed, db=db)) `
  - [Zeile 1093](../../../tests/test_watch_feature.py#L1093): ` self.assertEqual(db.stores["watches"]["w1"]["current_run_id"], "new-run") `
  - [Zeile 1094](../../../tests/test_watch_feature.py#L1094): ` self.assertEqual(db.stores[f"shares/{share_id}/watch_history"], {}) `

<a id="watch-03"></a>

## WATCH-03 · E-Mail-Follow mit Einwilligungsnachweis

Follow wird erst nach atomar konsumierter Challenge aktiv; Rate-/Resendlimits, Delivery-ID und signierte Unsubscribe verhindern Duplikate und fremde Abmeldung. Löschung invalidiert alte Challenges.

**Anforderungsbasis:** [docs/codebase-map.md](../../codebase-map.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** Mailtransport ersetzt, kein echter Zustellnachweis; Challenge- und Send-Effekt getrennt.

**Befunde:** —. Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [app/api/routers/watch.py](../../../app/api/routers/watch.py)
- [app/services/follow_challenges.py](../../../app/services/follow_challenges.py)
- [app/services/mailer.py](../../../app/services/mailer.py)
- [app/services/watch_followers.py](../../../app/services/watch_followers.py)

**Testdateien:**

- [tests/test_phase5_operations.py](../../../tests/test_phase5_operations.py)
- [tests/test_topics_feature.py](../../../tests/test_topics_feature.py)
- [tests/test_watch_feature.py](../../../tests/test_watch_feature.py)

</details>

**Konkrete Teilbelege:**

- [FollowerTests::test_cleanup_or_removed_watch_invalidates_outstanding_confirm_link](../../../tests/test_watch_feature.py#L2743) — Große Service-/Scheduler-/Router-/Mailformat-Suite mit DB-/LLM-/Versand-Doubles plus UI-Sourceverträge. Historischer **Datei**status: passed=146.
  - [Zeile 2746](../../../tests/test_watch_feature.py#L2746): ` self.assertTrue(pending["token"]) `
  - [Zeile 2751](../../../tests/test_watch_feature.py#L2751): ` with self.assertRaisesRegex(WatchError, "invalid or expired"): `
  - [Zeile 2753](../../../tests/test_watch_feature.py#L2753): ` self.assertEqual(self.db.stores[watch_followers.FOLLOWERS_COLLECTION], {}) `
  - [Zeile 2757](../../../tests/test_watch_feature.py#L2757): ` with self.assertRaisesRegex(WatchError, "no Consensus Watch"): `
  - [Zeile 2759](../../../tests/test_watch_feature.py#L2759): ` self.assertEqual(self.db.stores[watch_followers.FOLLOWERS_COLLECTION], {}) `

<a id="watch-04"></a>

## WATCH-04 · Telegram-Link und Zustellung

Secret-Webhook, einmaliger Linktoken und Ownerbindung schützen Verbindung/Aktionen; wiederholte Updates/Sendversuche erzeugen keine Doppelaktionen, Löschung entfernt Verknüpfungen.

**Anforderungsbasis:** [docs/codebase-map.md](../../codebase-map.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** Telegram-HTTP und Firestore ersetzt; User-Link-/Test-Endpoint und Cleanup-Schleifen teilweise nicht ausgeführt.

**Befunde:** [G-013](gaps.md#g-013). Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [app/api/routers/watch.py](../../../app/api/routers/watch.py)
- [app/services/mailer.py](../../../app/services/mailer.py)
- [app/services/telegram_watch.py](../../../app/services/telegram_watch.py)

**Testdateien:**

- [tests/test_watch_feature.py](../../../tests/test_watch_feature.py)

</details>

**Konkrete Teilbelege:**

- [TelegramWatchTests::test_watch_delivery_is_deduplicated_and_contains_actions](../../../tests/test_watch_feature.py#L1785) — Große Service-/Scheduler-/Router-/Mailformat-Suite mit DB-/LLM-/Versand-Doubles plus UI-Sourceverträge. Historischer **Datei**status: passed=146.
  - [Zeile 1799](../../../tests/test_watch_feature.py#L1799): ` self.assertTrue(telegram_watch.send_watch_notification(                 "w1", "run1", "change", watch, result, now=self.now, db=self.db,             )) `
  - [Zeile 1802](../../../tests/test_watch_feature.py#L1802): ` self.assertFalse(telegram_watch.send_watch_notification(                 "w1", "run1", "change", watch, result, now=self.now, db=self.db,             )) `
  - [Zeile 1805](../../../tests/test_watch_feature.py#L1805): ` send.assert_called_once() `
  - [Zeile 1808](../../../tests/test_watch_feature.py#L1808): ` self.assertIn("wm:w1", callbacks) `
  - [Zeile 1809](../../../tests/test_watch_feature.py#L1809): ` self.assertIn("wp:w1", callbacks) `
  - [Zeile 1810](../../../tests/test_watch_feature.py#L1810): ` self.assertEqual(len(self.db.stores[telegram_watch.DELIVERIES_COLLECTION]), 1) `

<a id="watch-05"></a>

## WATCH-05 · Morning Brief

Brief bündelt fällige Inhalte nach lokaler Zeit, hat einen persistenten Claim und deduplizierte Send-ID; Unsubscribe deaktiviert ausschließlich den passenden Brief.

**Anforderungsbasis:** [docs/codebase-map.md](../../codebase-map.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** Claim-/Mailerfakes, kein Mehrprozess-Sendnachweis oder definierter Crash-nach-Zustellung-Vertrag.

**Befunde:** —. Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [app/api/routers/watch.py](../../../app/api/routers/watch.py)
- [app/services/mailer.py](../../../app/services/mailer.py)
- [app/services/watch_brief.py](../../../app/services/watch_brief.py)
- [app/services/watch_scheduler.py](../../../app/services/watch_scheduler.py)

**Testdateien:**

- [tests/test_phase5_operations.py](../../../tests/test_phase5_operations.py)
- [tests/test_watch_feature.py](../../../tests/test_watch_feature.py)

</details>

**Konkrete Teilbelege:**

- [BriefClaimTests::test_claim_advances_before_sending_and_prevents_double_send](../../../tests/test_watch_feature.py#L2231) — Große Service-/Scheduler-/Router-/Mailformat-Suite mit DB-/LLM-/Versand-Doubles plus UI-Sourceverträge. Historischer **Datei**status: passed=146.
  - [Zeile 2233](../../../tests/test_watch_feature.py#L2233): ` self.assertIsNotNone(claimed) `
  - [Zeile 2234](../../../tests/test_watch_feature.py#L2234): ` self.assertEqual(claimed["baseline"], self.now - timedelta(days=3)) `
  - [Zeile 2235](../../../tests/test_watch_feature.py#L2235): ` self.assertGreater(self.store["u1"]["next_send_at"], self.now) `
  - [Zeile 2236](../../../tests/test_watch_feature.py#L2236): ` self.assertEqual(self.store["u1"]["last_evaluated_at"], self.now) `
  - [Zeile 2237](../../../tests/test_watch_feature.py#L2237): ` self.assertIsNone(watch_brief._claim_in_transaction(FakeTransaction(), self.ref, self.now)) `

<a id="watch-06"></a>

## WATCH-06 · Watch-Frontend

Dashboard lädt eigene Metadaten/History und autoritative Limitwerte, Modals erhalten Fokus/Scrollzustand, Konto-/Ansichtswechsel verwirft verspätete Daten. Driftanzeige folgt derselben Regel wie Backend.

**Anforderungsbasis:** [docs/codebase-map.md](../../codebase-map.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** JS teils ausgeschnittene Funktionen, Browser-APIs ersetzt; zentrale Create/Update/Delete-Verkabelung nicht Ende-zu-Ende belegt.

**Befunde:** —. Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [static/js/share-dialog.js](../../../static/js/share-dialog.js)
- [static/js/watch-state.js](../../../static/js/watch-state.js)
- [static/js/watch.js](../../../static/js/watch.js)

**Testdateien:**

- [tests/e2e/test_mobile_navigation.py](../../../tests/e2e/test_mobile_navigation.py)
- [tests/e2e/test_phase4_frontend.py](../../../tests/e2e/test_phase4_frontend.py)
- [tests/js/source-verification-watch.test.mjs](../../../tests/js/source-verification-watch.test.mjs)
- [tests/js/watch-drift-state.test.mjs](../../../tests/js/watch-drift-state.test.mjs)
- [tests/js/watch-feature-nudge.test.mjs](../../../tests/js/watch-feature-nudge.test.mjs)
- [tests/test_phase4_frontend.py](../../../tests/test_phase4_frontend.py)

</details>

**Konkrete Teilbelege:**

- [reads the server verdict instead of the raw changed flag](../../../tests/js/watch-drift-state.test.mjs#L31) — JavaScript-Modulintegration mit jsdom. Historischer **Datei**status: passed=2.
  - [Zeile 43](../../../tests/js/watch-drift-state.test.mjs#L43): ` expect(restated.key).toBe("stable"); `
  - [Zeile 44](../../../tests/js/watch-drift-state.test.mjs#L44): ` expect(restated.label).toBe("Stable"); `
  - [Zeile 45](../../../tests/js/watch-drift-state.test.mjs#L45): ` expect(restated.summary).toContain("Restated, not moved"); `

<a id="topic-01"></a>

## TOPIC-01 · Topic-Administration und versionierte Runs

Adminrechte, Slugreservierung, Archive/Indexing und unveränderliche Runversionen schützen Topics; atomare Pointerwrites akzeptieren nur den aktuellen Claim.

**Anforderungsbasis:** [docs/codebase-map.md](../../codebase-map.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** CRUD/Versionen mit Fake-DB; einzelne Routeradapter und der reale Scheduler-Claim werden ersetzt.

**Befunde:** [G-014](gaps.md#g-014), [G-031](gaps.md#g-031). Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [app/api/routers/topics.py](../../../app/api/routers/topics.py)
- [app/services/topics.py](../../../app/services/topics.py)

**Testdateien:**

- [tests/test_topics_feature.py](../../../tests/test_topics_feature.py)

</details>

**Konkrete Teilbelege:**

- [test_topic_run_and_latest_pointer_commit_or_fail_together](../../../tests/test_topics_feature.py#L414) — Große Service-/Router-/SSR-Suite mit FakeFirestore; einzelner echter SDK-Queryaufbau mit RPC-Mock. Historischer **Datei**status: passed=58.
  - [Zeile 420](../../../tests/test_topics_feature.py#L420): ` with pytest.raises(RuntimeError, match="injected transaction failure"): `
  - [Zeile 425](../../../tests/test_topics_feature.py#L425): ` assert db.documents[("topics", topic["id"])] == before `
  - [Zeile 426](../../../tests/test_topics_feature.py#L426): ` assert not any(         len(path) == 4 and path[:3] == ("topics", topic["id"], "runs")         for path in db.documents     ) `

<a id="topic-02"></a>

## TOPIC-02 · Topic-Pipeline und Identitätsjudge

Die neutrale Pipeline erzeugt neue Topicruns, vorhandene Claimidentitäten werden nur aus erlaubten Keys/Indices übernommen; ein fehlerhafter Identity-Judge darf den Run nicht verhindern.

**Anforderungsbasis:** [docs/codebase-map.md](../../codebase-map.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** Identity-Judge selbst vollständig ersetzt; echte Parser-/Fallback-/Bijectionsvalidierung dieses Helpers nicht ausgeführt.

**Befunde:** [G-016](gaps.md#g-016). Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [app/services/llm/consensus_engine.py](../../../app/services/llm/consensus_engine.py)
- [app/services/topic_pipeline.py](../../../app/services/topic_pipeline.py)
- [app/services/topic_runner.py](../../../app/services/topic_runner.py)

**Testdateien:**

- [tests/test_source_check_scope.py](../../../tests/test_source_check_scope.py)
- [tests/test_topics_feature.py](../../../tests/test_topics_feature.py)

</details>

**Konkrete Teilbelege:**

- [test_claim_identity_falls_back_to_fresh_keys_when_the_judge_is_unavailable](../../../tests/test_topics_feature.py#L998) — Große Service-/Router-/SSR-Suite mit FakeFirestore; einzelner echter SDK-Queryaufbau mit RPC-Mock. Historischer **Datei**status: passed=58.
  - [Zeile 1016](../../../tests/test_topics_feature.py#L1016): ` assert [item["key"] for item in position_map["dimensions"]] == ["run-7-0", "run-7-1"] `

<a id="topic-03"></a>

## TOPIC-03 · Zeitlicher Claim-/Quellenverlauf

Materialänderung, Formulierungswechsel, fehlende Messung und Claim-Retirement bleiben getrennt; historische Ansicht nutzt nur damals verfügbare Runs/Quellen und erfindet keine Nullscores.

**Anforderungsbasis:** [docs/codebase-map.md](../../codebase-map.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** Synthetische Identitäten und Claims; ein korrektes Ledger macht falsche LLM-Identitäten nicht fachlich richtig.

**Befunde:** —. Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [app/services/claim_ledger.py](../../../app/services/claim_ledger.py)
- [app/services/drift_signal.py](../../../app/services/drift_signal.py)
- [app/services/history_view.py](../../../app/services/history_view.py)
- [app/services/opinion_map.py](../../../app/services/opinion_map.py)
- [app/services/topic_finding.py](../../../app/services/topic_finding.py)

**Testdateien:**

- [tests/test_claim_ledger.py](../../../tests/test_claim_ledger.py)
- [tests/test_drift_signal.py](../../../tests/test_drift_signal.py)
- [tests/test_topic_finding.py](../../../tests/test_topic_finding.py)
- [tests/test_topics_feature.py](../../../tests/test_topics_feature.py)
- [tests/test_unscored_history.py](../../../tests/test_unscored_history.py)

</details>

**Konkrete Teilbelege:**

- [test_a_check_without_a_claim_list_is_a_gap_not_a_retirement](../../../tests/test_claim_ledger.py#L85) — Deterministische Unit-Tests. Historischer **Datei**status: passed=21.
  - [Zeile 98](../../../tests/test_claim_ledger.py#L98): ` assert ledger["thin"] == 1 `
  - [Zeile 99](../../../tests/test_claim_ledger.py#L99): ` assert ledger["enumerated"] == 2 `
  - [Zeile 101](../../../tests/test_claim_ledger.py#L101): ` assert claim["streak"] == 2, "the gap must not break the streak" `
  - [Zeile 102](../../../tests/test_claim_ledger.py#L102): ` assert claim["appearances"] == 2 `
  - [Zeile 103](../../../tests/test_claim_ledger.py#L103): ` assert [tick["state"] for tick in claim["lifeline"]] == ["on", "gap", "on"] `
  - [Zeile 104](../../../tests/test_claim_ledger.py#L104): ` assert ledger["retired"] == [] `

<a id="topic-04"></a>

## TOPIC-04 · Öffentliche Topic-Seiten und Follow

Hub, Sitemap, Versionseite und Evidenz-Links respektieren Archive/Indexing; Follow benötigt Double-opt-in, Faviconabruf ist begrenzt und ersetzt keine fremde Netzwerkressource ungeprüft.

**Anforderungsbasis:** [docs/codebase-map.md](../../codebase-map.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** SSR und Helper belegt; Hub/Sitemap/Follow-Adapter und echter Favicon-Transport haben Ausführungsgrenzen.

**Befunde:** [G-014](gaps.md#g-014). Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [app/api/routers/topics.py](../../../app/api/routers/topics.py)
- [app/services/favicons.py](../../../app/services/favicons.py)
- [app/services/topics.py](../../../app/services/topics.py)
- [templates/topic.html](../../../templates/topic.html)
- [templates/topics.html](../../../templates/topics.html)

**Testdateien:**

- [tests/test_phase5_operations.py](../../../tests/test_phase5_operations.py)
- [tests/test_seo_basics.py](../../../tests/test_seo_basics.py)
- [tests/test_topics_feature.py](../../../tests/test_topics_feature.py)

</details>

**Konkrete Teilbelege:**

- [test_public_topic_history_is_ssr_and_historical_version_is_noindex](../../../tests/test_topics_feature.py#L1246) — Große Service-/Router-/SSR-Suite mit FakeFirestore; einzelner echter SDK-Queryaufbau mit RPC-Mock. Historischer **Datei**status: passed=58.
  - [Zeile 1273](../../../tests/test_topics_feature.py#L1273): ` assert current.status_code == 200 `
  - [Zeile 1274](../../../tests/test_topics_feature.py#L1274): ` assert "The <strong>current</strong> consensus moved." in current.text `
  - [Zeile 1275](../../../tests/test_topics_feature.py#L1275): ` assert current.headers["x-robots-tag"] == "index, follow" `
  - [Zeile 1276](../../../tests/test_topics_feature.py#L1276): ` assert historical.status_code == 200 `
  - [Zeile 1277](../../../tests/test_topics_feature.py#L1277): ` assert "No confirmed release date exists." in historical.text `
  - [Zeile 1278](../../../tests/test_topics_feature.py#L1278): ` assert historical.headers["x-robots-tag"] == "noindex, follow" `
  - [Zeile 1279](../../../tests/test_topics_feature.py#L1279): ` assert "Return to the current consensus" in historical.text `

<a id="topic-05"></a>

## TOPIC-05 · Interaktiver Check-Strip

Hover/Fokus zeigt den gewählten historischen Check, Touch trennt Vorschau und Navigation. Wiederkehrende Leser sehen neue Checks; historische Versionen markieren neuere Checks nicht als gelesen. Notiztext bleibt Text.

**Anforderungsbasis:** [docs/codebase-map.md](../../codebase-map.md) · ` documented_and_inferred_rendering_invariant `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** Tests prüfen SSR-Marker und vorbereitete Daten; keine Ausführung des Topic-Frontendmoduls.

**Befunde:** [G-018](gaps.md#g-018). Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [app/services/claim_ledger.py](../../../app/services/claim_ledger.py)
- [static/js/topic-page.js](../../../static/js/topic-page.js)
- [templates/topic.html](../../../templates/topic.html)

**Testdateien:**

- [tests/test_claim_ledger.py](../../../tests/test_claim_ledger.py)
- [tests/test_topics_feature.py](../../../tests/test_topics_feature.py)

</details>

**Konkrete Teilbelege:**

- [test_the_check_strip_gives_every_check_one_cell_and_a_reason](../../../tests/test_claim_ledger.py#L395) — Deterministische Unit-Tests. Historischer **Datei**status: passed=21.
  - [Zeile 409](../../../tests/test_claim_ledger.py#L409): ` assert [cell["kind"] for cell in strip] == ["first", "stable", "material", "event"] `
  - [Zeile 410](../../../tests/test_claim_ledger.py#L410): ` assert strip[0]["note"] == "First check. The record starts here." `
  - [Zeile 411](../../../tests/test_claim_ledger.py#L411): ` assert strip[2]["note"] == "A rumoured window entered the answer." `
  - [Zeile 413](../../../tests/test_claim_ledger.py#L413): ` assert "entered" in strip[3]["note"] and "dropped out" in strip[3]["note"] `
  - [Zeile 414](../../../tests/test_claim_ledger.py#L414): ` assert strip[-1]["is_latest"] is True `
  - [Zeile 415](../../../tests/test_claim_ledger.py#L415): ` assert [cell["is_latest"] for cell in strip[:-1]] == [False, False, False] `
  - [Zeile 416](../../../tests/test_claim_ledger.py#L416): ` assert strip[2]["run_id"] == "run-2" `

<a id="seo-01"></a>

## SEO-01 · Search-Console-Erfassung

Read-only Credentials und begrenzte paginierte Erfassung liefern finale Zeiträume; Truncation/fehlende Daten werden nicht als echte Nullen gespeichert, wiederholte Tage bleiben idempotent.

**Anforderungsbasis:** [docs/codebase-map.md](../../codebase-map.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** Keine GSC-Integration; Erfassung gegen Repository-Double, Entdeckung der tatsächlich indexierbaren Ressourcen separat.

**Befunde:** —. Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [app/services/google_search_console.py](../../../app/services/google_search_console.py)
- [app/services/seo_data.py](../../../app/services/seo_data.py)

**Testdateien:**

- [tests/test_seo_data.py](../../../tests/test_seo_data.py)

</details>

**Konkrete Teilbelege:**

- [test_truncated_ranges_do_not_persist_omitted_rows_as_zeroes](../../../tests/test_seo_data.py#L251) — GSC-/Repository-/Recommendation-/Router-Integration mit Service-/HTTP-/DB-Doubles; UI-Sourceverträge. Historischer **Datei**status: passed=35.
  - [Zeile 269](../../../tests/test_seo_data.py#L269): ` assert result["status"] == "partial" `
  - [Zeile 270](../../../tests/test_seo_data.py#L270): ` assert result["days_requested"] == 90 `
  - [Zeile 271](../../../tests/test_seo_data.py#L271): ` assert result["days_collected"] == 0 `
  - [Zeile 273](../../../tests/test_seo_data.py#L273): ` assert len(metric_paths) == 1 `
  - [Zeile 274](../../../tests/test_seo_data.py#L274): ` assert metric_paths[0][-1] == "2026-07-17" `

<a id="seo-02"></a>

## SEO-02 · SEO-Repository und Dossiers

Seitengruppen, Zeiträume und neueste Läufe werden deterministisch, begrenzt und ohne sensible Querydetails gelesen; Dossiers trennen beobachtete Kennzahlen von Empfehlungen.

**Anforderungsbasis:** [docs/codebase-map.md](../../codebase-map.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** Viele Serviceprüfungen ersetzen Repository; Multi-page-Metrics, latest-run-Fallback und Judgmentlisten nicht ausgeführt.

**Befunde:** [G-017](gaps.md#g-017). Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [app/services/seo_data.py](../../../app/services/seo_data.py)
- [app/services/seo_dossier.py](../../../app/services/seo_dossier.py)
- [app/services/seo_repository.py](../../../app/services/seo_repository.py)

**Testdateien:**

- [tests/test_seo_data.py](../../../tests/test_seo_data.py)
- [tests/test_seo_weekly_review.py](../../../tests/test_seo_weekly_review.py)

</details>

**Konkrete Teilbelege:**

- [test_share_dossier_keeps_only_a_bounded_representation](../../../tests/test_seo_data.py#L677) — GSC-/Repository-/Recommendation-/Router-Integration mit Service-/HTTP-/DB-Doubles; UI-Sourceverträge. Historischer **Datei**status: passed=35.
  - [Zeile 701](../../../tests/test_seo_data.py#L701): ` assert len(dossier["content_representation"]) <= seo_dossier.MAX_SHARE_CONTENT_REPRESENTATION_CHARS `
  - [Zeile 702](../../../tests/test_seo_data.py#L702): ` assert dossier["source_freshness"]["source_count"] == 1 `
  - [Zeile 703](../../../tests/test_seo_data.py#L703): ` assert dossier["watch_freshness"]["last_checked_at"] == checked.isoformat() `
  - [Zeile 704](../../../tests/test_seo_data.py#L704): ` assert dossier["last_content_change_at"] == changed.isoformat() `
  - [Zeile 705](../../../tests/test_seo_data.py#L705): ` assert dossier["technical_uncertainties"] == [] `

<a id="seo-03"></a>

## SEO-03 · Konservative Empfehlungen und Aktionen

Deterministische Evidenzgates schützen Gewinner/Graceperiod; Content-Judge umgeht keine Regeln. Preview und Apply unterscheiden sich, Teilfehler bleiben sichtbar und Briefannahme prüft Konflikte.

**Anforderungsbasis:** [docs/codebase-map.md](../../codebase-map.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** LLM/Indexing/Watch-Aktionen ersetzt; reale SEO-Wirkung nicht messbar durch diese Suite.

**Befunde:** —. Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [app/api/routers/admin.py](../../../app/api/routers/admin.py)
- [app/services/seo_recommendation.py](../../../app/services/seo_recommendation.py)
- [app/services/seo_weekly_review.py](../../../app/services/seo_weekly_review.py)

**Testdateien:**

- [tests/js/seo-admin-alerts.test.mjs](../../../tests/js/seo-admin-alerts.test.mjs)
- [tests/test_seo_data.py](../../../tests/test_seo_data.py)
- [tests/test_seo_weekly_review.py](../../../tests/test_seo_weekly_review.py)

</details>

**Konkrete Teilbelege:**

- [test_apply_all_never_includes_delete_and_delete_requires_publisher_lineage](../../../tests/test_seo_weekly_review.py#L573) — Review-Service mit Repository-/Judge-/Action-Doubles. Historischer **Datei**status: passed=20.
  - [Zeile 576](../../../tests/test_seo_weekly_review.py#L576): ` assert service.apply(RUN_ID, admin_uid="admin", apply_all=True)["results"] == [] `
  - [Zeile 577](../../../tests/test_seo_weekly_review.py#L577): ` assert deleted == [] `
  - [Zeile 582](../../../tests/test_seo_weekly_review.py#L582): ` assert result["results"][0]["status"] == "error" `
  - [Zeile 583](../../../tests/test_seo_weekly_review.py#L583): ` assert deleted == [] `
  - [Zeile 587](../../../tests/test_seo_weekly_review.py#L587): ` assert result["results"][0]["status"] == "success" `
  - [Zeile 588](../../../tests/test_seo_weekly_review.py#L588): ` assert deleted == ["S" * 16] `

<a id="seo-04"></a>

## SEO-04 · Wöchentlicher Review und Publikationsdaten

Persistente Lease erlaubt einen Review je lokaler Woche, Datenportfolio und Prompt sind begrenzt; Benachrichtigung und manuelle Entscheidungen sind nachvollziehbar und wiederholbar.

**Anforderungsbasis:** [docs/codebase-map.md](../../codebase-map.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** Schedulerloop und einige Repository-Statusreads nicht ausgeführt; keine echte Mehrprozesslease.

**Befunde:** [G-017](gaps.md#g-017), [G-031](gaps.md#g-031). Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [app/services/publisher_config.py](../../../app/services/publisher_config.py)
- [app/services/seo_data.py](../../../app/services/seo_data.py)
- [app/services/seo_weekly_review.py](../../../app/services/seo_weekly_review.py)

**Testdateien:**

- [tests/test_seo_weekly_review.py](../../../tests/test_seo_weekly_review.py)

</details>

**Konkrete Teilbelege:**

- [test_review_uses_at_most_one_portfolio_judge_call](../../../tests/test_seo_weekly_review.py#L179) — Review-Service mit Repository-/Judge-/Action-Doubles. Historischer **Datei**status: passed=20.
  - [Zeile 182](../../../tests/test_seo_weekly_review.py#L182): ` assert result["status"] == "completed" `
  - [Zeile 183](../../../tests/test_seo_weekly_review.py#L183): ` assert judge.calls == 1 `
  - [Zeile 184](../../../tests/test_seo_weekly_review.py#L184): ` assert result["judge_called"] is True `

<a id="seo-05"></a>

## SEO-05 · Öffentliche Navigation und Suchmetadaten

SSR liefert Canonical, Robots/Sitemaps und konsistente Entität; App/Privat/Admin sind angemessen noindex. Model-Pulse zeigt dieselben Counts wie API und erhält letzten Stand bei Fehlern.

**Anforderungsbasis:** [docs/codebase-map.md](../../codebase-map.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** SSR-/String-/DOM-Belege; keine tatsächliche Google-Indexierung oder semantische Richtigkeit von Rechtstexten.

**Befunde:** —. Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [app/api/routers/pages.py](../../../app/api/routers/pages.py)
- [app/core/seo_entity.py](../../../app/core/seo_entity.py)
- [app/core/site.py](../../../app/core/site.py)
- [static/js/model-pulse.js](../../../static/js/model-pulse.js)
- [templates/about.html](../../../templates/about.html)
- [templates/admin.html](../../../templates/admin.html)
- [templates/admin_benchmark.html](../../../templates/admin_benchmark.html)
- [templates/ai-model-comparison.html](../../../templates/ai-model-comparison.html)
- [templates/benchmark.html](../../../templates/benchmark.html)
- [templates/consensus-engine.html](../../../templates/consensus-engine.html)
- [templates/imprint.html](../../../templates/imprint.html)
- [templates/index.html](../../../templates/index.html)
- [templates/landing.html](../../../templates/landing.html)
- [templates/model-pulse.html](../../../templates/model-pulse.html)
- [templates/partials/admin_prompt_config.html](../../../templates/partials/admin_prompt_config.html)
- [templates/partials/analytics.html](../../../templates/partials/analytics.html)
- [templates/partials/composer_toolbar_mockup.html](../../../templates/partials/composer_toolbar_mockup.html)
- [templates/partials/product_result_mockup.html](../../../templates/partials/product_result_mockup.html)
- [templates/partials/public_footer.html](../../../templates/partials/public_footer.html)
- [templates/partials/public_nav.html](../../../templates/partials/public_nav.html)
- [templates/privacy.html](../../../templates/privacy.html)
- [templates/questions.html](../../../templates/questions.html)
- [templates/share.html](../../../templates/share.html)
- [templates/share_unavailable.html](../../../templates/share_unavailable.html)
- [templates/terms.html](../../../templates/terms.html)
- [templates/topic.html](../../../templates/topic.html)
- [templates/topics.html](../../../templates/topics.html)

**Testdateien:**

- [tests/js/model-pulse.test.mjs](../../../tests/js/model-pulse.test.mjs)
- [tests/test_model_leaderboard.py](../../../tests/test_model_leaderboard.py)
- [tests/test_public_design_system.py](../../../tests/test_public_design_system.py)
- [tests/test_seo_basics.py](../../../tests/test_seo_basics.py)
- [tests/test_seo_entity.py](../../../tests/test_seo_entity.py)

</details>

**Konkrete Teilbelege:**

- [test_pulse_failure_is_retryable_not_a_fake_zero_ranking](../../../tests/test_model_leaderboard.py#L60) — Pages/API mit FakeDb und echten lokalen Threads. Historischer **Datei**status: passed=18.
  - [Zeile 68](../../../tests/test_model_leaderboard.py#L68): ` assert page.status_code == 503 `
  - [Zeile 69](../../../tests/test_model_leaderboard.py#L69): ` assert page.headers["cache-control"] == "no-store" `
  - [Zeile 70](../../../tests/test_model_leaderboard.py#L70): ` assert page.headers["retry-after"] == "60" `
  - [Zeile 71](../../../tests/test_model_leaderboard.py#L71): ` assert "temporarily unavailable" in page.text `
  - [Zeile 72](../../../tests/test_model_leaderboard.py#L72): ` assert 'role="listitem"' not in page.text `
  - [Zeile 73](../../../tests/test_model_leaderboard.py#L73): ` assert "0 judge selections" not in page.text `
  - [Zeile 74](../../../tests/test_model_leaderboard.py#L74): ` assert client.get("/model-pulse?period=invalid").status_code == 400 `

<a id="admin-01"></a>

## ADMIN-01 · Revisionierte Konfiguration

Adminsave validiert vor Mutation, speichert mit Revision/Audit und aktiviert konsistent; DB-/Aktivierungsfehler dürfen Runtime und Persistenz nicht auseinanderziehen. Alte Clients erhalten neue Felder.

**Anforderungsbasis:** [docs/codebase-map.md](../../codebase-map.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** Für Promptrevision echte Emulator-Konkurrenz; sonst Fakes und keine atomare Aktivierung über mehrere Prozesse.

**Befunde:** —. Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [app/api/routers/admin.py](../../../app/api/routers/admin.py)
- [app/core/config.py](../../../app/core/config.py)
- [app/services/agent_budget_config.py](../../../app/services/agent_budget_config.py)
- [app/services/prompt_config.py](../../../app/services/prompt_config.py)
- [app/services/prompt_defaults.py](../../../app/services/prompt_defaults.py)
- [app/services/publisher_config.py](../../../app/services/publisher_config.py)

**Testdateien:**

- [tests/e2e/test_prompt_config_transactions.py](../../../tests/e2e/test_prompt_config_transactions.py)
- [tests/test_agent_budget_config.py](../../../tests/test_agent_budget_config.py)
- [tests/test_model_configuration.py](../../../tests/test_model_configuration.py)
- [tests/test_model_configuration_regressions.py](../../../tests/test_model_configuration_regressions.py)
- [tests/test_prompt_config.py](../../../tests/test_prompt_config.py)
- [tests/test_publisher_config.py](../../../tests/test_publisher_config.py)
- [tests/test_source_model_configuration.py](../../../tests/test_source_model_configuration.py)

</details>

**Konkrete Teilbelege:**

- [test_admin_read_is_write_free_and_save_is_versioned_and_audited](../../../tests/test_prompt_config.py#L94) — Router/Store und Runtime-Prompt-Integration mit Fake-DB. Historischer **Datei**status: passed=19.
  - [Zeile 96](../../../tests/test_prompt_config.py#L96): ` assert response.status_code == 200 `
  - [Zeile 97](../../../tests/test_prompt_config.py#L97): ` assert response.json()["config"]["revision"] == 0 `
  - [Zeile 98](../../../tests/test_prompt_config.py#L98): ` assert response.json()["defaults"] == prompt_config.defaults() `
  - [Zeile 99](../../../tests/test_prompt_config.py#L99): ` assert config_store.db.documents == {} `
  - [Zeile 101](../../../tests/test_prompt_config.py#L101): ` assert response.status_code == 200 `
  - [Zeile 103](../../../tests/test_prompt_config.py#L103): ` assert saved["revision"] == 1 and saved["updated_by"] == "admin" `
  - [Zeile 104](../../../tests/test_prompt_config.py#L104): ` assert saved["prompts"] == changed()["prompts"] `
  - [Zeile 105](../../../tests/test_prompt_config.py#L105): ` assert config_store.db.documents[("app_config", "prompts")] == config_store.db.documents[("app_config", "prompts", "revisions", "000000000001")] `
  - [Zeile 106](../../../tests/test_prompt_config.py#L106): ` assert client.get("/api/admin/prompt-config", headers=AUTH).json()["config"] == saved `
  - [Zeile 108](../../../tests/test_prompt_config.py#L108): ` assert conflict.status_code == 409 `
  - [Zeile 109](../../../tests/test_prompt_config.py#L109): ` assert config_store.read()["revision"] == 1 `
  - [Zeile 111](../../../tests/test_prompt_config.py#L111): ` assert restored.status_code == 200 and restored.json()["config"]["revision"] == 2 `
  - [Zeile 112](../../../tests/test_prompt_config.py#L112): ` assert config_store.db.documents[("app_config", "prompts", "revisions", "000000000001")]["prompts"] == changed()["prompts"] `

<a id="admin-02"></a>

## ADMIN-02 · Adminoberfläche und HTTP-Adapter

Adminaktionen tragen den aktuellen Token, lesen/speichern die passende Ressource und zeigen verständliche Fehler; Revisionkonflikte erhalten lokale Eingaben und fordern Reload statt stiller Überschreibung.

**Anforderungsbasis:** [docs/codebase-map.md](../../codebase-map.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** JS meist Quellausschnitte; Browser prüft auch einen 409-detail-String, ersetzt aber /api/admin/** und ist nicht ausgeführt. Das error-Objekt des main-Handlers wird damit nicht geprüft.

**Befunde:** [G-019](gaps.md#g-019). Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [static/js/admin-agent-budget.js](../../../static/js/admin-agent-budget.js)
- [static/js/admin-api.js](../../../static/js/admin-api.js)
- [static/js/admin-benchmark.js](../../../static/js/admin-benchmark.js)
- [static/js/admin-config.js](../../../static/js/admin-config.js)
- [static/js/admin-prompt-config.js](../../../static/js/admin-prompt-config.js)
- [static/js/admin.js](../../../static/js/admin.js)
- [templates/admin.html](../../../templates/admin.html)
- [templates/admin_benchmark.html](../../../templates/admin_benchmark.html)
- [templates/partials/admin_prompt_config.html](../../../templates/partials/admin_prompt_config.html)

**Testdateien:**

- [tests/e2e/test_admin_agent_budget.py](../../../tests/e2e/test_admin_agent_budget.py)
- [tests/e2e/test_admin_prompt_config.py](../../../tests/e2e/test_admin_prompt_config.py)
- [tests/js/admin-agent-budget.test.mjs](../../../tests/js/admin-agent-budget.test.mjs)
- [tests/js/admin-prompt-config.test.mjs](../../../tests/js/admin-prompt-config.test.mjs)
- [tests/js/admin-reasoning-policy.test.mjs](../../../tests/js/admin-reasoning-policy.test.mjs)
- [tests/js/admin-source-model.test.mjs](../../../tests/js/admin-source-model.test.mjs)
- [tests/js/admin-watch-effective-run.test.mjs](../../../tests/js/admin-watch-effective-run.test.mjs)
- [tests/test_phase6_architecture.py](../../../tests/test_phase6_architecture.py)

</details>

**Konkrete Teilbelege:**

- [keeps the draft after conflict or failure and allows explicit reload](../../../tests/js/admin-prompt-config.test.mjs#L69) — JavaScript-Modultest und ausgeführte Quellcodeausschnitte mit jsdom. Historischer **Datei**status: passed=10.
  - [Zeile 75](../../../tests/js/admin-prompt-config.test.mjs#L75): ` await vi.waitFor(() => expect(doc.getElementById('promptConfigStatus').textContent).toContain('another session')); `
  - [Zeile 76](../../../tests/js/admin-prompt-config.test.mjs#L76): ` expect(doc.getElementById('prompt-agent').value).toBe('My unsaved draft'); `
  - [Zeile 77](../../../tests/js/admin-prompt-config.test.mjs#L77): ` expect(doc.getElementById('promptConfigDirty').hidden).toBe(false); `
  - [Zeile 79](../../../tests/js/admin-prompt-config.test.mjs#L79): ` await vi.waitFor(() => expect(doc.getElementById('prompt-agent').value).toBe(config.prompts.agent)); `
  - [Zeile 80](../../../tests/js/admin-prompt-config.test.mjs#L80): ` expect(doc.getElementById('promptConfigDirty').hidden).toBe(true); `

<a id="ui-01"></a>

## UI-01 · Run-State und getrennte Ansichten

RunRegistry besitzt Ausführung/Abbruch; visibleRunId bestimmt nur Rendering. Hintergrundruns speichern weiter, gespeicherte Ansichten und Authgeneration verhindern fremde Projektionen.

**Anforderungsbasis:** [docs/codebase-map.md](../../codebase-map.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** Reale Modulzustände mit Fake-Netzwerk; Browser nicht ausgeführt.

**Befunde:** —. Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [static/js/app-state.js](../../../static/js/app-state.js)
- [static/js/chat-session.js](../../../static/js/chat-session.js)
- [static/js/run-registry.js](../../../static/js/run-registry.js)
- [static/js/run-view.js](../../../static/js/run-view.js)

**Testdateien:**

- [tests/e2e/test_phase4_frontend.py](../../../tests/e2e/test_phase4_frontend.py)
- [tests/js/app-state.test.mjs](../../../tests/js/app-state.test.mjs)
- [tests/js/multi-run-view.test.mjs](../../../tests/js/multi-run-view.test.mjs)
- [tests/js/run-registry.test.mjs](../../../tests/js/run-registry.test.mjs)
- [tests/test_chat_session_ui.py](../../../tests/test_chat_session_ui.py)
- [tests/test_multi_run_architecture.py](../../../tests/test_multi_run_architecture.py)

</details>

**Konkrete Teilbelege:**

- [rejects a write from any other module and leaves the value alone](../../../tests/js/app-state.test.mjs#L36) — JavaScript-Modultest mit jsdom. Historischer **Datei**status: passed=8.
  - [Zeile 40](../../../tests/js/app-state.test.mjs#L40): ` expect(() => `
  - [Zeile 43](../../../tests/js/app-state.test.mjs#L43): ` expect(window.App.state.get("lastQuestion")).toBe("original"); `

<a id="ui-02"></a>

## UI-02 · Senden, Presets und Moduswechsel

Eingaben/Modelle/Quoten werden vor Runbeginn geprüft und pro Context eingefroren; Moduswechsel verändert nicht den laufenden Auftrag, Follow-up nutzt autoritative Chatbasis.

**Anforderungsbasis:** [docs/codebase-map.md](../../codebase-map.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** Statische und jsdom-Verträge; tatsächliche Provider-/Persistenzverkabelung gesondert.

**Befunde:** —. Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [static/js/agent-mode.js](../../../static/js/agent-mode.js)
- [static/js/app-core.js](../../../static/js/app-core.js)
- [static/js/app-init.js](../../../static/js/app-init.js)
- [static/js/feature-access.js](../../../static/js/feature-access.js)
- [static/js/model-picker.js](../../../static/js/model-picker.js)
- [static/js/query-send.js](../../../static/js/query-send.js)

**Testdateien:**

- [tests/e2e/test_direct_comparison_preview.py](../../../tests/e2e/test_direct_comparison_preview.py)
- [tests/js/agent-mode-projection.test.mjs](../../../tests/js/agent-mode-projection.test.mjs)
- [tests/js/model-attachment-capability.test.mjs](../../../tests/js/model-attachment-capability.test.mjs)
- [tests/js/model-family-cap.test.mjs](../../../tests/js/model-family-cap.test.mjs)
- [tests/js/plus-tier-gates.test.mjs](../../../tests/js/plus-tier-gates.test.mjs)
- [tests/test_agent_mode_ui.py](../../../tests/test_agent_mode_ui.py)
- [tests/test_usage_limit_ui.py](../../../tests/test_usage_limit_ui.py)

</details>

**Konkrete Teilbelege:**

- [persists source checks for agent runs and locks every control for direct comparisons](../../../tests/js/agent-mode-projection.test.mjs#L107) — JavaScript-Modultest mit jsdom. Historischer **Datei**status: passed=11.
  - [Zeile 111](../../../tests/js/agent-mode-projection.test.mjs#L111): ` expect(window.App.isSourceCheckEnabled()).toBe(true); `
  - [Zeile 112](../../../tests/js/agent-mode-projection.test.mjs#L112): ` expect(toggle.getAttribute('aria-checked')).toBe('true'); `
  - [Zeile 114](../../../tests/js/agent-mode-projection.test.mjs#L114): ` expect(window.App.isSourceCheckEnabled()).toBe(false); `
  - [Zeile 115](../../../tests/js/agent-mode-projection.test.mjs#L115): ` expect(window.localStorage.getItem('checkSources')).toBe('false'); `
  - [Zeile 116](../../../tests/js/agent-mode-projection.test.mjs#L116): ` expect(document.getElementById('sourceCheckMenuSwitch').checked).toBe(false); `
  - [Zeile 117](../../../tests/js/agent-mode-projection.test.mjs#L117): ` expect(document.getElementById('sourceCheckSwitch').checked).toBe(false); `
  - [Zeile 118](../../../tests/js/agent-mode-projection.test.mjs#L118): ` expect(document.getElementById('composerSourcesState').textContent).toBe('Off'); `
  - [Zeile 121](../../../tests/js/agent-mode-projection.test.mjs#L121): ` expect(toggle.getAttribute('aria-checked')).toBe('false'); `
  - [Zeile 124](../../../tests/js/agent-mode-projection.test.mjs#L124): ` expect(toggle.disabled).toBe(true); `
  - [Zeile 125](../../../tests/js/agent-mode-projection.test.mjs#L125): ` expect(document.getElementById('sourceCheckMenuSwitch').disabled).toBe(true); `
  - [Zeile 126](../../../tests/js/agent-mode-projection.test.mjs#L126): ` expect(document.getElementById('sourceCheckSwitch').disabled).toBe(true); `
  - [Zeile 128](../../../tests/js/agent-mode-projection.test.mjs#L128): ` expect(toggle.disabled).toBe(false); `
  - [Zeile 131](../../../tests/js/agent-mode-projection.test.mjs#L131): ` expect(window.localStorage.getItem('checkSources')).toBe('true'); `
  - [Zeile 133](../../../tests/js/agent-mode-projection.test.mjs#L133): ` expect(document.getElementById('sourceCheckSwitch').checked).toBe(true); `

<a id="ui-03"></a>

## UI-03 · Streaming, Deadlines und Fortschritt

Parser verarbeitet geteilte SSE-Chunks, genau ein finales Ergebnis und verständliche Fehler. Steueranfragen haben Fristen; Stream-Liveness und Provider-Fortschrittswatchdog bleiben von Gesamtlaufzeit getrennt. Progress zählt echte Daten und endet pro Run.

**Anforderungsbasis:** [docs/codebase-map.md](../../codebase-map.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** Fake-Uhr/Streams; Geometrie/Animation im Browserbestand noch nicht ausgeführt.

**Befunde:** —. Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [static/js/consensus-lifecycle.js](../../../static/js/consensus-lifecycle.js)
- [static/js/consensus-progress.js](../../../static/js/consensus-progress.js)
- [static/js/markdown-stream.js](../../../static/js/markdown-stream.js)
- [static/js/request-deadline.js](../../../static/js/request-deadline.js)

**Testdateien:**

- [tests/e2e/test_consensus_live_progress.py](../../../tests/e2e/test_consensus_live_progress.py)
- [tests/js/judge-stream-events.test.mjs](../../../tests/js/judge-stream-events.test.mjs)
- [tests/js/request-deadline.test.mjs](../../../tests/js/request-deadline.test.mjs)
- [tests/js/run-progress-animation.test.mjs](../../../tests/js/run-progress-animation.test.mjs)
- [tests/js/run-progress-scope.test.mjs](../../../tests/js/run-progress-scope.test.mjs)
- [tests/js/sse-completion.test.mjs](../../../tests/js/sse-completion.test.mjs)

</details>

**Konkrete Teilbelege:**

- [renews streaming liveness and removes timers after completion](../../../tests/js/request-deadline.test.mjs#L22) — JavaScript-Modultest mit jsdom. Historischer **Datei**status: passed=3.
  - [Zeile 29](../../../tests/js/request-deadline.test.mjs#L29): ` for (let i = 0; i < 10; i++) { progress(); expect(timers.size).toBe(1); } `
  - [Zeile 32](../../../tests/js/request-deadline.test.mjs#L32): ` expect(result).toBe('done'); expect(timers.size).toBe(0); `

<a id="ui-04"></a>

## UI-04 · Antworten, Markdown und zugängliche Details

Antworttext, Zitate, Mathematik, Marker und gespeicherte Turns rendern konsistent und sanitisiert; Filter entfernen keine Beweise, verborgene Elemente erzeugen keine unsichtbaren Tabstopps.

**Anforderungsbasis:** [docs/codebase-map.md](../../codebase-map.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** Konkrete DOM-/CSS-Verträge, kein flächiger Accessibility-/visueller Baseline-Audit. Ein statischer Footer-Vertrag ist rot.

**Befunde:** [G-028](gaps.md#g-028). Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [static/js/consensus-anchor.js](../../../static/js/consensus-anchor.js)
- [static/js/consensus-insights.js](../../../static/js/consensus-insights.js)
- [static/js/consensus-run.js](../../../static/js/consensus-run.js)
- [static/js/markdown-stream.js](../../../static/js/markdown-stream.js)
- [static/js/math-render.js](../../../static/js/math-render.js)
- [static/js/model-answer-reader.js](../../../static/js/model-answer-reader.js)

**Testdateien:**

- [tests/e2e/test_agreement_verdict.py](../../../tests/e2e/test_agreement_verdict.py)
- [tests/e2e/test_model_answer_reader.py](../../../tests/e2e/test_model_answer_reader.py)
- [tests/e2e/test_reader_density.py](../../../tests/e2e/test_reader_density.py)
- [tests/e2e/test_reader_review_regressions.py](../../../tests/e2e/test_reader_review_regressions.py)
- [tests/js/consensus-anchor.test.mjs](../../../tests/js/consensus-anchor.test.mjs)
- [tests/js/consensus-coverage-verdict.test.mjs](../../../tests/js/consensus-coverage-verdict.test.mjs)
- [tests/js/consensus-marker-visibility.test.mjs](../../../tests/js/consensus-marker-visibility.test.mjs)
- [tests/js/consensus-recovery.test.mjs](../../../tests/js/consensus-recovery.test.mjs)
- [tests/js/markdown-table.test.mjs](../../../tests/js/markdown-table.test.mjs)
- [tests/js/math-render.test.mjs](../../../tests/js/math-render.test.mjs)
- [tests/js/model-answer-reader.test.mjs](../../../tests/js/model-answer-reader.test.mjs)
- [tests/js/stored-turn-markers.test.mjs](../../../tests/js/stored-turn-markers.test.mjs)
- [tests/js/thread-question-disclosure.test.mjs](../../../tests/js/thread-question-disclosure.test.mjs)
- [tests/test_agreement_verdict_ui.py](../../../tests/test_agreement_verdict_ui.py)
- [tests/test_consensus_progress_ui.py](../../../tests/test_consensus_progress_ui.py)

</details>

**Konkrete Teilbelege:**

- [keeps measured agreement and coverage separate](../../../tests/js/consensus-coverage-verdict.test.mjs#L24) — JavaScript-Modulintegration mit jsdom. Historischer **Datei**status: passed=3.
  - [Zeile 26](../../../tests/js/consensus-coverage-verdict.test.mjs#L26): ` expect(verdict.querySelector(".verdict-score-num").textContent).toContain("64"); `
  - [Zeile 27](../../../tests/js/consensus-coverage-verdict.test.mjs#L27): ` expect(verdict.textContent).toContain("Coverage: 2/4 claims (50%)"); `
  - [Zeile 28](../../../tests/js/consensus-coverage-verdict.test.mjs#L28): ` expect(verdict.textContent).toContain("evidence incomplete"); `

<a id="ui-05"></a>

## UI-05 · Anhänge und Composer

Ab Plus akzeptierte Dateien werden validiert, komprimiert und pro Turn eingefroren; Vorschau/Entfernen und Moduswechsel erhalten korrekte Metadaten. Persistenz enthält keine Dateibytes.

**Anforderungsbasis:** [docs/codebase-map.md](../../codebase-map.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** Codec/Blob/Canvas teilweise ersetzt; kein umfassender Dateiformat-Fuzz-/realer Browsercodec-Nachweis.

**Befunde:** —. Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [app/services/llm/attachments.py](../../../app/services/llm/attachments.py)
- [static/js/attachments.js](../../../static/js/attachments.js)
- [static/js/composer-collapse.js](../../../static/js/composer-collapse.js)
- [static/js/composer-quote.js](../../../static/js/composer-quote.js)

**Testdateien:**

- [tests/e2e/test_composer_mode_bar.py](../../../tests/e2e/test_composer_mode_bar.py)
- [tests/js/attachment-compression.test.mjs](../../../tests/js/attachment-compression.test.mjs)
- [tests/js/bookmark-attachments.test.mjs](../../../tests/js/bookmark-attachments.test.mjs)
- [tests/js/composer-attachments.test.mjs](../../../tests/js/composer-attachments.test.mjs)
- [tests/js/composer-quote.test.mjs](../../../tests/js/composer-quote.test.mjs)
- [tests/js/model-attachment-capability.test.mjs](../../../tests/js/model-attachment-capability.test.mjs)
- [tests/test_attachments.py](../../../tests/test_attachments.py)
- [tests/test_chat_history.py](../../../tests/test_chat_history.py)

</details>

**Konkrete Teilbelege:**

- [shrinks an oversized photo before it is encoded](../../../tests/js/attachment-compression.test.mjs#L106) — JavaScript-Modulintegration mit simuliertem Bild-/Canvasverhalten. Historischer **Datei**status: passed=5.
  - [Zeile 114](../../../tests/js/attachment-compression.test.mjs#L114): ` expect(attachments).toHaveLength(1); `
  - [Zeile 115](../../../tests/js/attachment-compression.test.mjs#L115): ` expect(attachments[0].mime).toBe("image/jpeg"); `
  - [Zeile 117](../../../tests/js/attachment-compression.test.mjs#L117): ` expect(attachments[0].name).toBe("photo.jpg"); `
  - [Zeile 118](../../../tests/js/attachment-compression.test.mjs#L118): ` expect(attachments[0].size).toBe(ENCODED_BYTES); `
  - [Zeile 120](../../../tests/js/attachment-compression.test.mjs#L120): ` expect(harness.drawn).toEqual([[1568, 1045]]); `

<a id="ui-06"></a>

## UI-06 · Navigation, Scroll und Modals

Sidebar, Settings, Login und Shared-Modal sind erreichbar, geben Fokus zurück und erhalten korrekten Scroll-/Runzustand; mobile Größen und Reduced Motion folgen denselben Aktionen.

**Anforderungsbasis:** [docs/codebase-map.md](../../codebase-map.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** Abgedeckte Viewports/Flows begrenzt; Browser nicht ausgeführt, jsdom misst kein echtes Layout.

**Befunde:** [G-025](gaps.md#g-025). Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [static/app-ui.js](../../../static/app-ui.js)
- [static/js/app-dom-events.js](../../../static/js/app-dom-events.js)
- [static/js/app-init.js](../../../static/js/app-init.js)
- [static/js/chat-scroll.js](../../../static/js/chat-scroll.js)
- [static/js/composer-collapse.js](../../../static/js/composer-collapse.js)
- [static/js/mobile-header.js](../../../static/js/mobile-header.js)
- [static/js/share-dialog.js](../../../static/js/share-dialog.js)

**Testdateien:**

- [tests/e2e/test_browser_failure_recovery.py](../../../tests/e2e/test_browser_failure_recovery.py)
- [tests/e2e/test_chat_scroll_frontend.py](../../../tests/e2e/test_chat_scroll_frontend.py)
- [tests/e2e/test_mobile_navigation.py](../../../tests/e2e/test_mobile_navigation.py)
- [tests/js/chat-scroll.test.mjs](../../../tests/js/chat-scroll.test.mjs)
- [tests/js/mobile-header.test.mjs](../../../tests/js/mobile-header.test.mjs)
- [tests/test_navigation_settings_ui.py](../../../tests/test_navigation_settings_ui.py)

</details>

**Konkrete Teilbelege:**

- [moves the actual controls and restores their exact desktop slots without duplicates](../../../tests/js/mobile-header.test.mjs#L24) — JavaScript-Modultest mit jsdom. Historischer **Datei**status: passed=3.
  - [Zeile 30](../../../tests/js/mobile-header.test.mjs#L30): ` expect(actions.parentElement.id).toBe('mobileConversationActions'); `
  - [Zeile 31](../../../tests/js/mobile-header.test.mjs#L31): ` expect(views.parentElement.id).toBe('mobileSidebarViews'); `
  - [Zeile 32](../../../tests/js/mobile-header.test.mjs#L32): ` document.getElementById('action').click();expect(listener).toHaveBeenCalledOnce(); `
  - [Zeile 34](../../../tests/js/mobile-header.test.mjs#L34): ` expect(actions.previousElementSibling.id).toBe('before'); `
  - [Zeile 35](../../../tests/js/mobile-header.test.mjs#L35): ` expect(actions.nextElementSibling.id).toBe('after'); `
  - [Zeile 36](../../../tests/js/mobile-header.test.mjs#L36): ` expect(views.parentElement.tagName).toBe('HEADER'); `
  - [Zeile 37](../../../tests/js/mobile-header.test.mjs#L37): ` expect(document.querySelectorAll('#action')).toHaveLength(1); `
  - [Zeile 38](../../../tests/js/mobile-header.test.mjs#L38): ` expect(actions.hidden).toBe(false); `

<a id="ui-07"></a>

## UI-07 · Bootstrap, Skript-Reihenfolge und Styles

Serverkonfiguration wird escaped über Bootstrap-Daten übergeben; klassische Skripte laden in Vertragsreihenfolge, Globals haben eindeutige Owner und Styles konsistente Tokens.

**Anforderungsbasis:** [docs/codebase-map.md](../../codebase-map.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** Datei-/Source-Verträge sichern keine vollständige visuelle Darstellung.

**Befunde:** —. Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [static/app-ui.js](../../../static/app-ui.js)
- [static/css/admin-benchmark.css](../../../static/css/admin-benchmark.css)
- [static/css/admin.css](../../../static/css/admin.css)
- [static/css/agent-chat.css](../../../static/css/agent-chat.css)
- [static/css/base.css](../../../static/css/base.css)
- [static/css/benchmark.css](../../../static/css/benchmark.css)
- [static/css/chat-scroll.css](../../../static/css/chat-scroll.css)
- [static/css/components-attachment-viewer.css](../../../static/css/components-attachment-viewer.css)
- [static/css/components-consensus-insights.css](../../../static/css/components-consensus-insights.css)
- [static/css/components-consensus-visuals.css](../../../static/css/components-consensus-visuals.css)
- [static/css/components-consensus.css](../../../static/css/components-consensus.css)
- [static/css/components-controls.css](../../../static/css/components-controls.css)
- [static/css/components-feedback.css](../../../static/css/components-feedback.css)
- [static/css/components-input.css](../../../static/css/components-input.css)
- [static/css/components-memory-edit.css](../../../static/css/components-memory-edit.css)
- [static/css/components-misc.css](../../../static/css/components-misc.css)
- [static/css/components-modals.css](../../../static/css/components-modals.css)
- [static/css/components-model-picker.css](../../../static/css/components-model-picker.css)
- [static/css/components-watch.css](../../../static/css/components-watch.css)
- [static/css/composer-attachments.css](../../../static/css/composer-attachments.css)
- [static/css/consensus-engine.css](../../../static/css/consensus-engine.css)
- [static/css/demo-action.css](../../../static/css/demo-action.css)
- [static/css/landing.css](../../../static/css/landing.css)
- [static/css/layout.css](../../../static/css/layout.css)
- [static/css/model-answer-reader.css](../../../static/css/model-answer-reader.css)
- [static/css/model-pulse.css](../../../static/css/model-pulse.css)
- [static/css/public-pages.css](../../../static/css/public-pages.css)
- [static/css/public-shell.css](../../../static/css/public-shell.css)
- [static/css/public-tokens.css](../../../static/css/public-tokens.css)
- [static/css/shell.css](../../../static/css/shell.css)
- [static/css/skeleton.css](../../../static/css/skeleton.css)
- [static/css/source-verification.css](../../../static/css/source-verification.css)
- [static/css/status-palette.css](../../../static/css/status-palette.css)
- [static/css/topics.css](../../../static/css/topics.css)
- [static/css/typography.css](../../../static/css/typography.css)
- [static/css/variables.css](../../../static/css/variables.css)
- [static/js/app-bootstrap.js](../../../static/js/app-bootstrap.js)
- [static/js/app-core.js](../../../static/js/app-core.js)
- [static/js/app-dom-events.js](../../../static/js/app-dom-events.js)
- [static/js/bundles.json](../../../static/js/bundles.json)
- [static/style.css](../../../static/style.css)
- [templates/index.html](../../../templates/index.html)

**Testdateien:**

- [tests/test_frontend_assets.py](../../../tests/test_frontend_assets.py)
- [tests/test_frontend_build.py](../../../tests/test_frontend_build.py)
- [tests/test_frontend_resilience.py](../../../tests/test_frontend_resilience.py)
- [tests/test_phase6_architecture.py](../../../tests/test_phase6_architecture.py)
- [tests/test_public_design_system.py](../../../tests/test_public_design_system.py)

</details>

**Konkrete Teilbelege:**

- [test_source_mode_serves_every_file_in_declared_order](../../../tests/test_frontend_assets.py#L55) — Asset-Funktionen, Dateisystem und isolierte Pages-Routen. Historischer **Datei**status: passed=14.
  - [Zeile 67](../../../tests/test_frontend_assets.py#L67): ` assert served == expected `

<a id="ui-08"></a>

## UI-08 · Demo und Landing-Interaktionen

Demo bleibt lokal, startet auf bewusste Aktion, zeigt konsistente Beispielantworten und führt zum Login; Landing-Animationen dürfen Inhalt/Navigation nicht blockieren.

**Anforderungsbasis:** [docs/codebase-map.md](../../codebase-map.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** Demo-Teilfälle belegt; eigenständige Landing-Animationslogik hat keinen gezielten dynamischen Nachweis.

**Befunde:** —. Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [static/demo.js](../../../static/demo.js)
- [static/js/landing-insights.js](../../../static/js/landing-insights.js)
- [static/js/landing-scenes.js](../../../static/js/landing-scenes.js)
- [templates/consensus-engine.html](../../../templates/consensus-engine.html)
- [templates/landing.html](../../../templates/landing.html)
- [templates/partials/composer_toolbar_mockup.html](../../../templates/partials/composer_toolbar_mockup.html)
- [templates/partials/product_result_mockup.html](../../../templates/partials/product_result_mockup.html)

**Testdateien:**

- [tests/e2e/test_public_composer_mockups.py](../../../tests/e2e/test_public_composer_mockups.py)
- [tests/e2e/test_smoke.py](../../../tests/e2e/test_smoke.py)
- [tests/js/demo-claim-coverage.test.mjs](../../../tests/js/demo-claim-coverage.test.mjs)
- [tests/test_demo_login_prompt.py](../../../tests/test_demo_login_prompt.py)

</details>

**Konkrete Teilbelege:**

- [marks every checkable consensus passage with the current coverage contract](../../../tests/js/demo-claim-coverage.test.mjs#L33) — JavaScript-Daten-/Modulintegration mit VM und jsdom. Historischer **Datei**status: passed=2.
  - [Zeile 60](../../../tests/js/demo-claim-coverage.test.mjs#L60): ` expect(body.querySelectorAll(".cx-claim").length).toBe(19); `
  - [Zeile 61](../../../tests/js/demo-claim-coverage.test.mjs#L61): ` expect(fallback.hidden).toBe(true); `
  - [Zeile 71](../../../tests/js/demo-claim-coverage.test.mjs#L71): ` expect(unmarkedWords, passage.textContent).toBe(""); `

<a id="ui-09"></a>

## UI-09 · Analytics-Selbstausschluss

notrack=1 deaktiviert Tracking vor Trackerstart, notrack=0 hebt den Ausschluss auf; blockierter Storage darf Seitenstart nicht abbrechen. Adminseiten werden nicht getrackt.

**Anforderungsbasis:** [docs/codebase-map.md](../../codebase-map.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** Nur Source-/Template-Assertions; Queryparameter und Storageausfall nicht ausgeführt.

**Befunde:** [G-021](gaps.md#g-021). Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [static/js/analytics-opt-out.js](../../../static/js/analytics-opt-out.js)
- [templates/partials/analytics.html](../../../templates/partials/analytics.html)

**Testdateien:**

- [tests/test_analytics_partial.py](../../../tests/test_analytics_partial.py)

</details>

**Konkrete Teilbelege:**

- [test_partial_ships_the_self_exclusion_switch](../../../tests/test_analytics_partial.py#L59) — Quelltextverträge. Historischer **Datei**status: passed=5.
  - [Zeile 67](../../../tests/test_analytics_partial.py#L67): ` assert 'localStorage.setItem("umami.disabled", "1")' in opt_out `
  - [Zeile 68](../../../tests/test_analytics_partial.py#L68): ` assert 'localStorage.removeItem("umami.disabled")' in opt_out `
  - [Zeile 69](../../../tests/test_analytics_partial.py#L69): ` assert partial.index("analytics-opt-out.js") < partial.index("cloud.umami.is"), (         "Das Opt-out muss vor dem Tracker laufen, sonst geht der erste Pageview raus."     ) `

<a id="data-01"></a>

## DATA-01 · Votes, Feedback und Modellstatistik

Feedback ist UID-begrenzt, Votes sind owner-/resultgebunden und zählen einmal. Aggregierte Statistik enthält keine Inhalte; öffentliche Counts kommen aus konsistentem gecachtem Snapshot.

**Anforderungsbasis:** [docs/codebase-map.md](../../codebase-map.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** Guard/Aggregation gut lokal geprüft; Feedback-HTTP-Adapter und Stats-Persistenzwrapper nicht ausgeführt.

**Befunde:** [G-034](gaps.md#g-034). Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [app/api/routers/pages.py](../../../app/api/routers/pages.py)
- [app/services/differences_stats.py](../../../app/services/differences_stats.py)
- [app/services/persistence_guard.py](../../../app/services/persistence_guard.py)

**Testdateien:**

- [tests/test_differences_stats.py](../../../tests/test_differences_stats.py)
- [tests/test_firestore_read_contracts.py](../../../tests/test_firestore_read_contracts.py)
- [tests/test_model_leaderboard.py](../../../tests/test_model_leaderboard.py)
- [tests/test_phase5_operations.py](../../../tests/test_phase5_operations.py)

</details>

**Konkrete Teilbelege:**

- [BuildDifferencesStatsDocTests::test_no_content_leaks_into_doc](../../../tests/test_differences_stats.py#L134) — Unit-Tests für Statistikprojektion. Historischer **Datei**status: passed=4.
  - [Zeile 147](../../../tests/test_differences_stats.py#L147): ` self.assertNotIn(forbidden, flat) `

<a id="bench-01"></a>

## BENCH-01 · Dataset, Budget und Closed-book-Vertrag

Stichproben sind deterministisch und Pilot/Final disjunkt; Parser bewertet nur explizite Antwortmarker, Payloads haben keine Webtools, Budgetstop erfolgt vor weiteren Calls.

**Anforderungsbasis:** [docs/codebase-map.md](../../codebase-map.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** Kleine synthetische Daten und Provider-Doubles; keine Repräsentativität oder Live-Modellqualität.

**Befunde:** —. Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [benchmark/audit.py](../../../benchmark/audit.py)
- [benchmark/config.py](../../../benchmark/config.py)
- [benchmark/cost.py](../../../benchmark/cost.py)
- [benchmark/dataset.py](../../../benchmark/dataset.py)
- [benchmark/parse.py](../../../benchmark/parse.py)
- [benchmark/prompt.py](../../../benchmark/prompt.py)
- [benchmark/transport.py](../../../benchmark/transport.py)

**Testdateien:**

- [tests/test_benchmark_audits.py](../../../tests/test_benchmark_audits.py)
- [tests/test_benchmark_credentials.py](../../../tests/test_benchmark_credentials.py)
- [tests/test_benchmark_dataset.py](../../../tests/test_benchmark_dataset.py)
- [tests/test_benchmark_mode.py](../../../tests/test_benchmark_mode.py)
- [tests/test_benchmark_parse.py](../../../tests/test_benchmark_parse.py)
- [tests/test_benchmark_transport.py](../../../tests/test_benchmark_transport.py)

</details>

**Konkrete Teilbelege:**

- [ExtractLetterTests::test_final_answer_marker_on_last_line](../../../tests/test_benchmark_parse.py#L9) — Reine Parser-/Auswertungsfunktionen. Historischer **Datei**status: passed=12.
  - [Zeile 10](../../../tests/test_benchmark_parse.py#L10): ` self.assertEqual(             extract_letter("Brief reason first.\nFINAL_ANSWER: C"),             "C",         ) `
  - [Zeile 14](../../../tests/test_benchmark_parse.py#L14): ` self.assertEqual(             extract_letter("The supported calculation gives 2/3.\n\nFINAL_ANSWER: J"),             "J",         ) `

<a id="bench-02"></a>

## BENCH-02 · Runner, Resume und Artefakte

Runs speichern effektive Konfiguration und getrennte Modell-/Consensus-/Synthesezellen; Resume dedupliziert, Retry bleibt explizit, Rohkeys werden redigiert. Große Modi bleiben hinter Budget-/Freigabegates.

**Anforderungsbasis:** [docs/codebase-map.md](../../codebase-map.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** Haupt-CLI belegt; alternative run_sample/run_experiment-Einstiege nicht ausgeführt. Keine Livebenchmarks.

**Befunde:** [G-035](gaps.md#g-035). Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [benchmark/__init__.py](../../../benchmark/__init__.py)
- [benchmark/__main__.py](../../../benchmark/__main__.py)
- [benchmark/run_experiment.py](../../../benchmark/run_experiment.py)
- [benchmark/run_sample.py](../../../benchmark/run_sample.py)
- [benchmark/runner.py](../../../benchmark/runner.py)

**Testdateien:**

- [tests/test_benchmark_audits.py](../../../tests/test_benchmark_audits.py)
- [tests/test_benchmark_cli.py](../../../tests/test_benchmark_cli.py)
- [tests/test_benchmark_redaction.py](../../../tests/test_benchmark_redaction.py)
- [tests/test_benchmark_run.py](../../../tests/test_benchmark_run.py)
- [tests/test_benchmark_runner.py](../../../tests/test_benchmark_runner.py)

</details>

**Konkrete Teilbelege:**

- [test_dry_run_creates_run_dir_and_manifest_without_http](../../../tests/test_benchmark_cli.py#L54) — CLI-Funktionen mit Dataset-/Runner-/Publisher-Doubles. Historischer **Datei**status: passed=20.
  - [Zeile 56](../../../tests/test_benchmark_cli.py#L56): ` assert rc == 0 `
  - [Zeile 58](../../../tests/test_benchmark_cli.py#L58): ` assert (run_dir / "manifest.json").exists() `
  - [Zeile 59](../../../tests/test_benchmark_cli.py#L59): ` assert not (run_dir / "calls.jsonl").exists() `
  - [Zeile 60](../../../tests/test_benchmark_cli.py#L60): ` assert "Dry-Run" in capsys.readouterr().out `

<a id="bench-03"></a>

## BENCH-03 · Ergebnisberechnung und Adminberichte

Deduplizierte Zellen bestimmen Accuracy/Kosten/Fehler; Publish speichert kompakte Reports ohne Rohprompts, Reader verhindert Traversal und bevorzugt Firestore bei Duplikaten.

**Anforderungsbasis:** [docs/codebase-map.md](../../codebase-map.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** Datei-/Repositoryfakes; Admin-HTTP-Adapter und Frontendbericht nicht dynamisch geprüft. Adminrollen statt Eigentümerscope schützen diese Oberfläche.

**Befunde:** [G-015](gaps.md#g-015). Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [app/services/benchmark_reports.py](../../../app/services/benchmark_reports.py)
- [benchmark/report_reader.py](../../../benchmark/report_reader.py)
- [benchmark/results.py](../../../benchmark/results.py)
- [static/js/admin-benchmark.js](../../../static/js/admin-benchmark.js)

**Testdateien:**

- [tests/test_benchmark_report_reader.py](../../../tests/test_benchmark_report_reader.py)
- [tests/test_benchmark_reports.py](../../../tests/test_benchmark_reports.py)
- [tests/test_benchmark_results.py](../../../tests/test_benchmark_results.py)

</details>

**Konkrete Teilbelege:**

- [test_publish_run_dir_stores_compact_report_only](../../../tests/test_benchmark_reports.py#L76) — Report-Publisher mit FakeCollection. Historischer **Datei**status: passed=2.
  - [Zeile 83](../../../tests/test_benchmark_reports.py#L83): ` assert summary["run_id"] == "pilot_v1" `
  - [Zeile 86](../../../tests/test_benchmark_reports.py#L86): ` assert stored["storage_version"] == benchmark_reports.STORAGE_VERSION `
  - [Zeile 87](../../../tests/test_benchmark_reports.py#L87): ` assert stored["report"]["questions"][0]["models"]["openai"]["letter"] == "C" `
  - [Zeile 88](../../../tests/test_benchmark_reports.py#L88): ` assert "SECRET_RAW_ANSWER" not in stored_json `
  - [Zeile 89](../../../tests/test_benchmark_reports.py#L89): ` assert "SECRET_RAW_PROMPT" not in stored_json `
  - [Zeile 90](../../../tests/test_benchmark_reports.py#L90): ` assert "SECRET_RAW_PAYLOAD" not in stored_json `

<a id="build-01"></a>

## BUILD-01 · Reproduzierbare Frontendartefakte

Manifest/Fingerprint und Inhaltsnamen passen zu aktuellen Quellen; alter Output wird sicher bereinigt, öffentliche Assets haben konsistente Cachekeys und vendorte Libraries definierte Eingänge.

**Anforderungsbasis:** [docs/codebase-map.md](../../codebase-map.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** Build-/Dateisystembelege; Vendor-Kopierskript selbst und Browserausführung jedes erzeugten Bundles gesondert.

**Befunde:** [G-036](gaps.md#g-036). Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [app/core/assets.py](../../../app/core/assets.py)
- [app/core/version.py](../../../app/core/version.py)
- [package.json](../../../package.json)
- [scripts/build_frontend.mjs](../../../scripts/build_frontend.mjs)
- [scripts/frontend-output.mjs](../../../scripts/frontend-output.mjs)
- [scripts/vendor_frontend.mjs](../../../scripts/vendor_frontend.mjs)

**Testdateien:**

- [tests/js/frontend-output.test.mjs](../../../tests/js/frontend-output.test.mjs)
- [tests/test_frontend_assets.py](../../../tests/test_frontend_assets.py)
- [tests/test_frontend_build.py](../../../tests/test_frontend_build.py)

</details>

**Konkrete Teilbelege:**

- [leaves the old manifest and assets readable when publication fails](../../../tests/js/frontend-output.test.mjs#L56) — Node-Integration mit echtem temporärem Dateisystem. Historischer **Datei**status: passed=4.
  - [Zeile 59](../../../tests/js/frontend-output.test.mjs#L59): ` await expect(publishBuild(dir, new Map([["invalid.js", "bad"]]), {})).rejects.toThrow(); `
  - [Zeile 60](../../../tests/js/frontend-output.test.mjs#L60): ` expect(JSON.parse(await fs.readFile(path.join(dir, "manifest.json"), "utf8"))).toEqual(first.manifest); `
  - [Zeile 61](../../../tests/js/frontend-output.test.mjs#L61): ` expect(await fs.readFile(path.join(dir, first.name), "utf8")).toBe("/* version 1 */"); `

<a id="build-02"></a>

## BUILD-02 · Test- und Emulator-Einstieg

Backend/Frontend/Browser sind reproduzierbar auswählbar; Browser nutzt ausschließlich lokales Demo-Firestore, niemals produktive Credentials. Toolfehler müssen als Fehler sichtbar bleiben.

**Anforderungsbasis:** [docs/testing.md](../../testing.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** Zwölf Windowsfälle übersprungen; bestehende CI führt nur Publisherregressionen aus.

**Befunde:** [G-024](gaps.md#g-024), [G-025](gaps.md#g-025), [G-026](gaps.md#g-026). Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [dev.ps1](../../../dev.ps1)
- [firebase.json](../../../firebase.json)
- [firestore.indexes.json](../../../firestore.indexes.json)
- [vitest.config.mjs](../../../vitest.config.mjs)

**Testdateien:**

- [tests/test_dev_cli.py](../../../tests/test_dev_cli.py)
- [tests/test_e2e_safety.py](../../../tests/test_e2e_safety.py)
- [tests/test_phase5_operations.py](../../../tests/test_phase5_operations.py)

</details>

**Konkrete Teilbelege:**

- [test_frontend_preserves_failure_and_stops](../../../tests/test_dev_cli.py#L164) — Windows-Prozessintegration mit Fake-CLI-Werkzeugen. Historischer **Datei**status: skipped=12.
  - [Zeile 167](../../../tests/test_dev_cli.py#L167): ` assert result.returncode == 23, result.stdout + result.stderr `
  - [Zeile 168](../../../tests/test_dev_cli.py#L168): ` assert len(calls) == expected_calls `
  - [Zeile 169](../../../tests/test_dev_cli.py#L169): ` assert "[dev] OK" not in result.stdout `

<a id="build-03"></a>

## BUILD-03 · Scheduled Publisher und Workflows

Standalone-Publisher funktioniert ohne Backendabhängigkeiten, verwendet stabiles Idempotency-Key und behandelt Publish/Skip/Disabled nachvollziehbar; Konfiguration/Indexing/Watch sind explizite Schritte.

**Anforderungsbasis:** [docs/codebase-map.md](../../codebase-map.md) · ` documented_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** Subprozess mit Netzwerkverbot und HTTP-Doubles; kein realer Scheduler-/Render-/Publishlauf.

**Befunde:** [G-024](gaps.md#g-024). Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [.github/workflows/publish-consensus.yml](../../../.github/workflows/publish-consensus.yml)
- [.github/workflows/publisher-tests.yml](../../../.github/workflows/publisher-tests.yml)
- [.github/workflows/restart-render.yml](../../../.github/workflows/restart-render.yml)
- [scripts/publish_consensus.py](../../../scripts/publish_consensus.py)

**Testdateien:**

- [tests/test_publish_consensus_script.py](../../../tests/test_publish_consensus_script.py)
- [tests/test_publisher_standalone.py](../../../tests/test_publisher_standalone.py)

</details>

**Konkrete Teilbelege:**

- [PublisherStandaloneTests::test_scheduled_flow_without_packages_or_external_services](../../../tests/test_publisher_standalone.py#L98) — Echte Python-Subprozesse ohne Site-Packages mit HTTP-Doubles. Historischer **Datei**status: passed=3.
  - [Zeile 156](../../../tests/test_publisher_standalone.py#L156): ` self.assert_success(self.run_python(["-c", code], env={                     "TEST_MODE": mode,                     "CONSENSUS_API_BASE_URL": "https://consensus.invalid",                     "CONSENSUS_API_KEY": "test-consensus-key",                     "OPENROUTER_API_KEY": "test-topic-key",                     "CONSENSUS_IDEMPOTENCY_KEY": "scheduled-publisher-test",                     "GITHUB_STEP_SUMMARY": str(Path(temp) / "summary.md"),                 })) `

<a id="tools-01"></a>

## TOOLS-01 · Wartungs- und Reparaturwerkzeuge

Repair betrifft nur explizit gewähltes Konto/Projekt, Inspect schreibt nicht. Claim-Key-Backfill erhält fremde Felder, überspringt fertige Runs, Dry-run schreibt nicht und Force ist explizit.

**Anforderungsbasis:** [docs/codebase-map.md](../../codebase-map.md) · ` documented_cli_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Kein eigener Verhaltensbeleg in der Suite gefunden. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** Keine Testreferenz und keine ausgeführte Zeile in regulärer Messung; niemals als Produktionsprobe ausführen.

**Befunde:** [G-022](gaps.md#g-022), [G-023](gaps.md#g-023). Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [scripts/backfill_claim_keys.py](../../../scripts/backfill_claim_keys.py)
- [scripts/repair_agent_allowance.py](../../../scripts/repair_agent_allowance.py)

**Testdateien:**

Keine.

</details>

**Konkrete Teilbelege:**

Kein repräsentativer Verhaltenstest vorhanden.

<a id="tools-02"></a>

## TOOLS-02 · Evaluations-/Vorschauwerkzeuge

Evaluationen haben begrenzte Inputs/Modelle/Budgets und nachvollziehbare Ergebnisse; lokale Vorschauen schreiben ausschließlich gewünschte Artefakte, keine Produktdaten.

**Anforderungsbasis:** [docs/codebase-map.md](../../codebase-map.md) · ` documented_cli_contract `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Teilweise belegt. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** Fixtures/Helper teilweise geprüft, CLI-Livepfade nicht ausgeführt. Manuelle Artefakte sind kein aktueller Suite-Nachweis.

**Befunde:** [G-035](gaps.md#g-035). Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [scripts/evaluate_agent_delegation.py](../../../scripts/evaluate_agent_delegation.py)
- [scripts/evaluate_source_verification.py](../../../scripts/evaluate_source_verification.py)
- [scripts/probe_agent_delegation.py](../../../scripts/probe_agent_delegation.py)
- [scripts/render_watch_preview.py](../../../scripts/render_watch_preview.py)

**Testdateien:**

- [tests/test_agent_delegation.py](../../../tests/test_agent_delegation.py)
- [tests/test_source_verification.py](../../../tests/test_source_verification.py)

</details>

**Konkrete Teilbelege:**

- [test_evaluation_dataset_has_complete_v3_expected_verdicts](../../../tests/test_source_verification.py#L753) — Verifikations-/Dokument-/Pipeline-Integration mit Fetch/Judge/HTTPX-Doubles und Threads. Historischer **Datei**status: passed=122.
  - [Zeile 755](../../../tests/test_source_verification.py#L755): ` assert all(len(case) == 7 for case in CASES) `
  - [Zeile 757](../../../tests/test_source_verification.py#L757): ` assert expected['contradiction'] == expected['untrusted_instructions'] == 'contradicted' `
  - [Zeile 758](../../../tests/test_source_verification.py#L758): ` assert expected['missing_condition'] == 'partial' `
- [test_quality_gate_rejects_cheap_bad_unknown_unpaired_or_unused_delegation](../../../tests/test_agent_delegation.py#L296) — Echte Workerthreads/Mailboxen mit Store- und Provider-Doubles. Historischer **Datei**status: passed=16.
  - [Zeile 302](../../../tests/test_agent_delegation.py#L302): ` assert gate(rows)["approved"] is True `
  - [Zeile 307](../../../tests/test_agent_delegation.py#L307): ` assert gate(candidate)["approved"] is False `
  - [Zeile 308](../../../tests/test_agent_delegation.py#L308): ` assert not gate([r for r in rows if r["task"] == "parallel_ledgers"])["approved"] `
  - [Zeile 309](../../../tests/test_agent_delegation.py#L309): ` assert not gate([{**r, "agents": 0} for r in rows])["approved"] `

<a id="auth-05"></a>

## AUTH-05 · Direkte Firestore-Clients bleiben gesperrt

Browser-/REST-Clients dürfen weder fremde noch eigene Firestore-Dokumente lesen/schreiben; insbesondere dürfen Nutzer ihren tier/role nicht selbst ändern. Backend-Admin-SDK ist eine getrennte Autorisierungsgrenze.

**Anforderungsbasis:** [firestore.rules](../../../firestore.rules) · ` documented_security_invariant `. Die Basis ist eine Fundstelle, keine Behauptung, dass ältere Spezifikationen jede aktuelle Klausel wörtlich enthalten; [abweichende Oracles](decisions.md) beachten.

**Bewertung:** Kein eigener Verhaltensbeleg in der Suite gefunden. Dateien liefern Belege für die im Testkatalog beschriebenen Teilfälle. Die Zuordnung behauptet keine vollständige Assertion jeder Vertragskante.

**Testgrenze:** Kein Rules-Unit-Test gefunden. Die bestehenden Emulatorfälle verwenden Admin-SDK und umgehen diese Regeln.

**Befunde:** [G-001](gaps.md#g-001). Kein verknüpfter Befund bedeutet keine Vollständigkeitsfreigabe.

<details><summary>Produktdateien und zugeordnete Testdateien</summary>

**Produktdateien:**

- [firebase.json](../../../firebase.json)
- [firestore.rules](../../../firestore.rules)

**Testdateien:**

Keine.

</details>

**Konkrete Teilbelege:**

Kein repräsentativer Verhaltenstest vorhanden.

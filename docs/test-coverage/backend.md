# Reguläre Python-Suite: Abdeckung pro Testdatei

Stand: **2026-09-26**, Quellstand `145db25bfe029ff7f50cd77595bd6b9e043c1a2f`. [Methodik und Gesamtbefund](../test-coverage-map.md).

**133 Dateien · 2034 statische Testdefinitionen · 2730 Runner-Fälle.**

„Geprüftes Verhalten“ beschreibt die vorhandenen Assertions. Der Laufstatus steht separat: bei Fehlern ist der beschriebene Vertrag nicht als bestanden belegt. Prüfaufträge sind offene Fragen für den Folgeaudit, keine pauschal festgestellten Lücken der gesamten Suite.

Die Codeverweise sind direkte Imports oder wörtliche Pfade, keine gemessene Ausführungsabdeckung. Indirekte Abhängigkeiten über Fixtures/Helpers und dynamisch zusammengesetzte Pfade können fehlen. Das [JSON-Inventar](inventory.json) enthält jede Definition mit Zeilen, Assertion-Fundstellen und jeden expandierten Runner-Fall.

| Datei | Definitionen | Runner-Fälle | Primärlauf |
|---|---:|---:|---|
| [test_account_deletion_chats.py](#test-account-deletion-chats-py) | 3 | 3 | 3 bestanden |
| [test_account_deletion_retry.py](#test-account-deletion-retry-py) | 1 | 1 | 1 bestanden |
| [test_account_tier_admin.py](#test-account-tier-admin-py) | 12 | 12 | 12 bestanden |
| [test_agent_accounting_audit.py](#test-agent-accounting-audit-py) | 11 | 58 | 58 bestanden |
| [test_agent_admission.py](#test-agent-admission-py) | 11 | 15 | 15 bestanden |
| [test_agent_answer_lifecycle.py](#test-agent-answer-lifecycle-py) | 3 | 7 | 7 bestanden |
| [test_agent_budget_config.py](#test-agent-budget-config-py) | 3 | 3 | 3 bestanden |
| [test_agent_capacity.py](#test-agent-capacity-py) | 6 | 6 | 6 bestanden |
| [test_agent_chat_integrity.py](#test-agent-chat-integrity-py) | 8 | 15 | 15 bestanden |
| [test_agent_comparison.py](#test-agent-comparison-py) | 19 | 44 | 44 bestanden |
| [test_agent_continuation.py](#test-agent-continuation-py) | 11 | 13 | 13 bestanden |
| [test_agent_contradictions.py](#test-agent-contradictions-py) | 10 | 11 | 11 bestanden |
| [test_agent_delegation.py](#test-agent-delegation-py) | 16 | 16 | 16 bestanden |
| [test_agent_loop.py](#test-agent-loop-py) | 24 | 152 | 152 bestanden |
| [test_agent_mode_ui.py](#test-agent-mode-ui-py) | 9 | 9 | 9 bestanden |
| [test_agent_model_catalog.py](#test-agent-model-catalog-py) | 5 | 11 | 11 bestanden |
| [test_agent_progress.py](#test-agent-progress-py) | 9 | 10 | 10 bestanden |
| [test_agent_quota_recovery.py](#test-agent-quota-recovery-py) | 8 | 12 | 12 bestanden |
| [test_agent_reliability.py](#test-agent-reliability-py) | 13 | 17 | 17 bestanden |
| [test_agent_runs.py](#test-agent-runs-py) | 30 | 38 | 38 bestanden |
| [test_agent_search.py](#test-agent-search-py) | 11 | 61 | 61 bestanden |
| [test_agent_synthesis_context.py](#test-agent-synthesis-context-py) | 2 | 4 | 4 bestanden |
| [test_agreement_verdict_ui.py](#test-agreement-verdict-ui-py) | 6 | 6 | 6 bestanden |
| [test_analysis_quality_budget.py](#test-analysis-quality-budget-py) | 12 | 14 | 14 bestanden |
| [test_analytics_partial.py](#test-analytics-partial-py) | 5 | 5 | 5 bestanden |
| [test_api_account_cleanup.py](#test-api-account-cleanup-py) | 3 | 4 | 4 bestanden |
| [test_api_key_repository.py](#test-api-key-repository-py) | 5 | 5 | 5 bestanden |
| [test_api_run_repository.py](#test-api-run-repository-py) | 8 | 8 | 8 bestanden |
| [test_ask_endpoints.py](#test-ask-endpoints-py) | 14 | 14 | 14 bestanden |
| [test_attachments.py](#test-attachments-py) | 37 | 37 | 37 bestanden |
| [test_auth_revocation.py](#test-auth-revocation-py) | 4 | 4 | 4 bestanden |
| [test_auth_session.py](#test-auth-session-py) | 8 | 8 | 8 bestanden |
| [test_background_task_supervision.py](#test-background-task-supervision-py) | 7 | 7 | 7 bestanden |
| [test_benchmark_audits.py](#test-benchmark-audits-py) | 9 | 9 | 9 bestanden |
| [test_benchmark_cli.py](#test-benchmark-cli-py) | 20 | 20 | 20 bestanden |
| [test_benchmark_credentials.py](#test-benchmark-credentials-py) | 4 | 4 | 4 bestanden |
| [test_benchmark_dataset.py](#test-benchmark-dataset-py) | 7 | 7 | 7 bestanden |
| [test_benchmark_mode.py](#test-benchmark-mode-py) | 5 | 5 | 5 bestanden |
| [test_benchmark_parse.py](#test-benchmark-parse-py) | 12 | 12 | 12 bestanden |
| [test_benchmark_redaction.py](#test-benchmark-redaction-py) | 3 | 3 | 3 bestanden |
| [test_benchmark_report_reader.py](#test-benchmark-report-reader-py) | 4 | 4 | 4 bestanden |
| [test_benchmark_reports.py](#test-benchmark-reports-py) | 2 | 2 | 2 bestanden |
| [test_benchmark_results.py](#test-benchmark-results-py) | 8 | 8 | 8 bestanden |
| [test_benchmark_run.py](#test-benchmark-run-py) | 6 | 6 | 6 bestanden |
| [test_benchmark_runner.py](#test-benchmark-runner-py) | 9 | 9 | 9 bestanden |
| [test_benchmark_transport.py](#test-benchmark-transport-py) | 6 | 6 | 6 bestanden |
| [test_bookmarks.py](#test-bookmarks-py) | 35 | 38 | 38 bestanden |
| [test_chat_context.py](#test-chat-context-py) | 37 | 37 | 37 bestanden |
| [test_chat_history.py](#test-chat-history-py) | 61 | 72 | 72 bestanden |
| [test_chat_session_ui.py](#test-chat-session-ui-py) | 11 | 11 | 11 bestanden |
| [test_citations.py](#test-citations-py) | 7 | 7 | 7 bestanden |
| [test_claim_ledger.py](#test-claim-ledger-py) | 21 | 21 | 21 bestanden |
| [test_client_error_alerts.py](#test-client-error-alerts-py) | 12 | 34 | 34 bestanden |
| [test_consensus_answer_contract.py](#test-consensus-answer-contract-py) | 5 | 5 | 5 bestanden |
| [test_consensus_api.py](#test-consensus-api-py) | 27 | 27 | 27 bestanden |
| [test_consensus_chat_history.py](#test-consensus-chat-history-py) | 39 | 52 | 52 bestanden |
| [test_consensus_citations.py](#test-consensus-citations-py) | 15 | 44 | 44 bestanden |
| [test_consensus_engine.py](#test-consensus-engine-py) | 19 | 19 | 19 bestanden |
| [test_consensus_input_caps.py](#test-consensus-input-caps-py) | 8 | 8 | 8 bestanden |
| [test_consensus_progress_ui.py](#test-consensus-progress-ui-py) | 18 | 18 | 17 bestanden, 1 fehlgeschlagen |
| [test_contradiction_jobs.py](#test-contradiction-jobs-py) | 15 | 19 | 19 bestanden |
| [test_contradiction_verification.py](#test-contradiction-verification-py) | 29 | 64 | 64 bestanden |
| [test_coverage_judge.py](#test-coverage-judge-py) | 27 | 27 | 27 bestanden |
| [test_deepseek_web_search.py](#test-deepseek-web-search-py) | 3 | 3 | 3 bestanden |
| [test_demo_login_prompt.py](#test-demo-login-prompt-py) | 5 | 5 | 5 bestanden |
| [test_dev_cli.py](#test-dev-cli-py) | 8 | 12 | 12 übersprungen |
| [test_differences_schema.py](#test-differences-schema-py) | 75 | 75 | 75 bestanden |
| [test_differences_stats.py](#test-differences-stats-py) | 4 | 4 | 4 bestanden |
| [test_drift_signal.py](#test-drift-signal-py) | 7 | 7 | 7 bestanden |
| [test_e2e_safety.py](#test-e2e-safety-py) | 6 | 10 | 10 bestanden |
| [test_firestore_read_contracts.py](#test-firestore-read-contracts-py) | 1 | 2 | 2 bestanden |
| [test_followup_context.py](#test-followup-context-py) | 16 | 18 | 18 bestanden |
| [test_frontend_assets.py](#test-frontend-assets-py) | 13 | 14 | 14 bestanden |
| [test_frontend_build.py](#test-frontend-build-py) | 8 | 8 | 8 bestanden |
| [test_frontend_resilience.py](#test-frontend-resilience-py) | 4 | 4 | 4 bestanden |
| [test_logging_redaction_contract.py](#test-logging-redaction-contract-py) | 6 | 6 | 6 bestanden |
| [test_memory_edit.py](#test-memory-edit-py) | 14 | 14 | 14 bestanden |
| [test_model_configuration.py](#test-model-configuration-py) | 27 | 27 | 27 bestanden |
| [test_model_configuration_regressions.py](#test-model-configuration-regressions-py) | 33 | 33 | 33 bestanden |
| [test_model_leaderboard.py](#test-model-leaderboard-py) | 14 | 18 | 18 bestanden |
| [test_multi_run_architecture.py](#test-multi-run-architecture-py) | 3 | 3 | 3 bestanden |
| [test_navigation_settings_ui.py](#test-navigation-settings-ui-py) | 27 | 27 | 27 bestanden |
| [test_onboarding_gates.py](#test-onboarding-gates-py) | 7 | 7 | 7 bestanden |
| [test_phase4_frontend.py](#test-phase4-frontend-py) | 14 | 14 | 14 bestanden |
| [test_phase5_operations.py](#test-phase5-operations-py) | 25 | 32 | 32 bestanden |
| [test_phase6_architecture.py](#test-phase6-architecture-py) | 8 | 8 | 8 bestanden |
| [test_plus_tier.py](#test-plus-tier-py) | 18 | 34 | 34 bestanden |
| [test_pro_beta_and_copy.py](#test-pro-beta-and-copy-py) | 9 | 9 | 9 bestanden |
| [test_prompt_config.py](#test-prompt-config-py) | 7 | 19 | 19 bestanden |
| [test_prompt_date_context.py](#test-prompt-date-context-py) | 2 | 3 | 3 bestanden |
| [test_provider_registry.py](#test-provider-registry-py) | 16 | 16 | 16 bestanden |
| [test_provider_response_errors.py](#test-provider-response-errors-py) | 3 | 38 | 38 bestanden |
| [test_provider_timeouts.py](#test-provider-timeouts-py) | 8 | 58 | 58 bestanden |
| [test_public_citation_cleanup.py](#test-public-citation-cleanup-py) | 5 | 5 | 5 bestanden |
| [test_public_design_system.py](#test-public-design-system-py) | 7 | 7 | 7 bestanden |
| [test_publish_consensus_script.py](#test-publish-consensus-script-py) | 13 | 13 | 13 bestanden |
| [test_publisher_config.py](#test-publisher-config-py) | 4 | 4 | 4 bestanden |
| [test_publisher_standalone.py](#test-publisher-standalone-py) | 3 | 3 | 3 bestanden |
| [test_rate_limit.py](#test-rate-limit-py) | 8 | 8 | 8 bestanden |
| [test_reasoning_policy.py](#test-reasoning-policy-py) | 7 | 18 | 18 bestanden |
| [test_registration_security.py](#test-registration-security-py) | 4 | 4 | 4 bestanden |
| [test_request_body_limits.py](#test-request-body-limits-py) | 4 | 4 | 4 bestanden |
| [test_resolve_round.py](#test-resolve-round-py) | 23 | 23 | 23 bestanden |
| [test_router_event_loop_contract.py](#test-router-event-loop-contract-py) | 2 | 2 | 2 bestanden |
| [test_run_usage_endpoints.py](#test-run-usage-endpoints-py) | 9 | 11 | 11 bestanden |
| [test_run_usage_repository.py](#test-run-usage-repository-py) | 22 | 25 | 25 bestanden |
| [test_security_controls.py](#test-security-controls-py) | 4 | 4 | 4 bestanden |
| [test_seo_basics.py](#test-seo-basics-py) | 13 | 13 | 13 bestanden |
| [test_seo_data.py](#test-seo-data-py) | 35 | 35 | 35 bestanden |
| [test_seo_entity.py](#test-seo-entity-py) | 6 | 6 | 6 bestanden |
| [test_seo_weekly_review.py](#test-seo-weekly-review-py) | 20 | 20 | 20 bestanden |
| [test_share_feature.py](#test-share-feature-py) | 151 | 151 | 151 bestanden |
| [test_source_catalog.py](#test-source-catalog-py) | 19 | 19 | 19 bestanden |
| [test_source_check_api.py](#test-source-check-api-py) | 9 | 14 | 14 bestanden |
| [test_source_check_jobs.py](#test-source-check-jobs-py) | 22 | 23 | 23 bestanden |
| [test_source_check_repository.py](#test-source-check-repository-py) | 31 | 36 | 36 bestanden |
| [test_source_check_scope.py](#test-source-check-scope-py) | 5 | 12 | 12 bestanden |
| [test_source_judge_fallback.py](#test-source-judge-fallback-py) | 7 | 15 | 15 bestanden |
| [test_source_model_configuration.py](#test-source-model-configuration-py) | 13 | 28 | 28 bestanden |
| [test_source_verification.py](#test-source-verification-py) | 62 | 122 | 122 bestanden |
| [test_stream_backpressure.py](#test-stream-backpressure-py) | 3 | 3 | 3 bestanden |
| [test_streaming.py](#test-streaming-py) | 27 | 27 | 27 bestanden |
| [test_telegram_notifier.py](#test-telegram-notifier-py) | 9 | 9 | 9 bestanden |
| [test_tier_cache.py](#test-tier-cache-py) | 7 | 7 | 7 bestanden |
| [test_topic_finding.py](#test-topic-finding-py) | 14 | 14 | 14 bestanden |
| [test_topics_feature.py](#test-topics-feature-py) | 45 | 58 | 58 bestanden |
| [test_unscored_history.py](#test-unscored-history-py) | 3 | 3 | 3 bestanden |
| [test_usage_authorization.py](#test-usage-authorization-py) | 11 | 19 | 19 bestanden |
| [test_usage_limit_ui.py](#test-usage-limit-ui-py) | 10 | 10 | 10 bestanden |
| [test_user_memory.py](#test-user-memory-py) | 29 | 29 | 29 bestanden |
| [test_user_memory_run_cache.py](#test-user-memory-run-cache-py) | 11 | 15 | 15 bestanden |
| [test_watch_feature.py](#test-watch-feature-py) | 146 | 146 | 146 bestanden |
| [test_worker_thread_budget.py](#test-worker-thread-budget-py) | 5 | 9 | 9 bestanden |

<a id="test-account-deletion-chats-py"></a>

## test_account_deletion_chats.py

**Quelle:** [tests/test_account_deletion_chats.py](../../tests/test_account_deletion_chats.py) · **Bereiche:** Authentifizierung.

**Ebene:** API mit Service-Double.

**Lauf:** 3 bestanden.

**Geprüftes Verhalten:** POST /delete_account startet einen dauerhaften Löschauftrag mit UID/E-Mail und ruft die Bereinigung auf; vollständiger Erfolg liefert 200, gemeldete Teilfehler und eine sofortige Cleanup-Exception liefern 202 cleanup_pending.

**Grenzen und Doubles:** Der Name des ersten Tests suggeriert eine Chat-Kaskade; tatsächlich ist account_deletion ersetzt und nur Start-/Cleanup-Aufruf wird geprüft. Keine echte Chat-Löschung, Datenbank oder Firebase-Auth-Löschung.

**Prüfauftrag für den Folgeaudit:** Mit test_account_deletion_retry.py und ChatStore-Löschtests abgleichen, welche Kaskaden und verspäteten Writer tatsächlich ausgeführt werden.

**Direkte Codeverweise:** [app/api/routers/users.py](../../app/api/routers/users.py), [app/core/rate_limit.py](../../app/core/rate_limit.py).

<details>
<summary>3 Testdefinitionen und ihre Quellstellen</summary>

- [test_delete_account_cascades_into_the_owner_chats](../../tests/test_account_deletion_chats.py#L98) (Zeile 98)
- [test_delete_account_reports_a_failed_chat_cascade_instead_of_hiding_it](../../tests/test_account_deletion_chats.py#L107) (Zeile 107)
- [test_delete_account_reports_durable_job_when_immediate_cleanup_crashes](../../tests/test_account_deletion_chats.py#L119) (Zeile 119)

</details>

<a id="test-account-deletion-retry-py"></a>

## test_account_deletion_retry.py

**Quelle:** [tests/test_account_deletion_retry.py](../../tests/test_account_deletion_retry.py) · **Bereiche:** Authentifizierung, Persistenz.

**Ebene:** Service mit In-Memory-Datenbank.

**Lauf:** 1 bestanden.

**Geprüftes Verhalten:** Ein Fehler im Bereich owned_shares bleibt beim ersten Cleanup offen; der zweite Durchlauf wiederholt nur diesen Bereich. Andere quittierte Bereiche laufen genau einmal; der Auftrag endet completed, cleanup_pending=false und entfernt die E-Mail.

**Grenzen und Doubles:** Die eigentlichen Bereichslöschungen einschließlich ChatStore sind Doubles mit Aufrufzählern. Geprüft werden Orchestrierung und Checkpoints, keine reale Löschkaskade oder Firestore-Konflikte.

**Prüfauftrag für den Folgeaudit:** Weitere Fehlerpositionen, Prozessabbruch zwischen Bereichslöschung und Quittierung und konkurrierende Cleanup-Worker im späteren Audit abgleichen.

**Direkte Codeverweise:** [app/services/account_deletion.py](../../app/services/account_deletion.py).

<details>
<summary>1 Testdefinitionen und ihre Quellstellen</summary>

- [test_failed_area_remains_pending_and_only_that_area_is_retried](../../tests/test_account_deletion_retry.py#L69) (Zeile 69)

</details>

<a id="test-account-tier-admin-py"></a>

## test_account_tier_admin.py

**Quelle:** [tests/test_account_tier_admin.py](../../tests/test_account_tier_admin.py) · **Bereiche:** Admin, Authentifizierung.

**Ebene:** Service und API mit Datenbank-/Auth-Doubles.

**Lauf:** 12 bestanden.

**Geprüftes Verhalten:** Tier setzen inklusive Audit, Zeitstempel, Cache-Invalidierung, Featureflags und Erhalt anderer Profilfelder; ungültige Stufe und Kontolöschungs-Sperre; Prüfung der Sperre innerhalb der übergebenen Transaktion; E-Mail-Lookup, Legacy-premium, Änderungsverlauf sowie Admin-403, erfolgreicher PUT, Schema-422 und Lookup-404.

**Grenzen und Doubles:** Firebase-Nutzer, Adminentscheidung und Firestore sind ersetzt; die Transaktionsprüfung belegt die Übergabe des Transaktionsobjekts, keine echte Konfliktauflösung.

**Prüfauftrag für den Folgeaudit:** Atomarität von Profiländerung/Audit/Cache bei Teilfehlern und parallelem Tierwechsel gegen ergänzende Transaktionstests prüfen.

**Direkte Codeverweise:** [app/api/routers/admin.py](../../app/api/routers/admin.py), [app/core/rate_limit.py](../../app/core/rate_limit.py), [app/services/account_tier.py](../../app/services/account_tier.py).

<details>
<summary>12 Testdefinitionen und ihre Quellstellen</summary>

- [test_set_tier_writes_the_field_audits_it_and_drops_the_cache](../../tests/test_account_tier_admin.py#L143) (Zeile 143)
- [test_set_tier_keeps_unrelated_profile_fields](../../tests/test_account_tier_admin.py#L168) (Zeile 168)
- [test_set_tier_rejects_an_unknown_tier](../../tests/test_account_tier_admin.py#L176) (Zeile 176)
- [test_an_account_being_deleted_gets_no_tier](../../tests/test_account_tier_admin.py#L183) (Zeile 183)
- [test_set_tier_checks_deletion_fence_inside_profile_transaction](../../tests/test_account_tier_admin.py#L197) (Zeile 197)
- [test_lookup_accepts_an_email](../../tests/test_account_tier_admin.py#L220) (Zeile 220)
- [test_listing_covers_the_legacy_premium_tag](../../tests/test_account_tier_admin.py#L229) (Zeile 229)
- [test_recent_changes_are_readable](../../tests/test_account_tier_admin.py#L242) (Zeile 242)
- [test_endpoints_require_admin](../../tests/test_account_tier_admin.py#L255) (Zeile 255)
- [test_put_sets_the_tier](../../tests/test_account_tier_admin.py#L267) (Zeile 267)
- [test_put_rejects_a_tier_outside_the_three](../../tests/test_account_tier_admin.py#L278) (Zeile 278)
- [test_lookup_of_an_unknown_account_is_a_404](../../tests/test_account_tier_admin.py#L288) (Zeile 288)

</details>

<a id="test-agent-accounting-audit-py"></a>

## test_agent_accounting_audit.py

**Quelle:** [tests/test_agent_accounting_audit.py](../../tests/test_agent_accounting_audit.py) · **Bereiche:** Konten und Tarife.

**Ebene:** Abrechnung über realen Agent-Loop und geskripteten Transport.

**Lauf:** 58 bestanden.

**Geprüftes Verhalten:** Provider-Token-/Kostenübernahme für alle registrierten Modell-IDs; explizite HTTP-Ablehnungen geben Reservierungen genau einmal frei, mehrdeutige Ausfälle bleiben unbekannt; Stop vor Dispatch, Zwischen- gegenüber finaler Usage, getrennte Token-/Kosten-Vollständigkeit, separat eintreffende Tokenfelder, eingefrorene Laufzeit nach Reaping sowie Ledgerrevisionen.

**Grenzen und Doubles:** Die Modellmatrix prüft denselben synthetischen Transport für jede Konfiguration. Sie belegt keine realen Providerantworten; Datenbank ist der geteilte Agent-Fake.

**Prüfauftrag für den Folgeaudit:** Live-Provider-Protokollabweichungen und vollständige Verwendung der Unknown-Zähler im Produkt abgleichen.

**Direkte Codeverweise:** [app/core/config.py](../../app/core/config.py), [app/services/agent_costs.py](../../app/services/agent_costs.py), [app/services/agent_policy.py](../../app/services/agent_policy.py), [app/services/agent_provider_limits.py](../../app/services/agent_provider_limits.py), [app/services/agent_quota.py](../../app/services/agent_quota.py), [app/services/llm/agent_client.py](../../app/services/llm/agent_client.py), [app/services/llm/engines.py](../../app/services/llm/engines.py).

**Direkte Testhelfer:** [tests/test_agent_delegation.py](../../tests/test_agent_delegation.py), [tests/test_agent_loop.py](../../tests/test_agent_loop.py), [tests/test_agent_runs.py](../../tests/test_agent_runs.py).

<details>
<summary>11 Testdefinitionen und ihre Quellstellen</summary>

- [test_every_registered_chat_comparison_and_judge_model_uses_provider_totals](../../tests/test_agent_accounting_audit.py#L19) (Zeile 19)
- [test_explicit_http_rejection_releases_paid_claim_once](../../tests/test_agent_accounting_audit.py#L34) (Zeile 34)
- [test_ambiguous_errors_never_invent_free_usage](../../tests/test_agent_accounting_audit.py#L53) (Zeile 53)
- [test_stop_after_admission_but_before_provider_releases_all_tokens](../../tests/test_agent_accounting_audit.py#L59) (Zeile 59)
- [test_intermediate_usage_is_lower_bound_after_interrupted_generation](../../tests/test_agent_accounting_audit.py#L73) (Zeile 73)
- [test_final_usage_replaces_cumulative_values_and_releases_reservation](../../tests/test_agent_accounting_audit.py#L85) (Zeile 85)
- [test_token_receipt_is_complete_without_search_price](../../tests/test_agent_accounting_audit.py#L95) (Zeile 95)
- [test_final_cost_does_not_promote_intermediate_token_counts](../../tests/test_agent_accounting_audit.py#L106) (Zeile 106)
- [test_separately_reported_final_token_fields_complete_the_receipt](../../tests/test_agent_accounting_audit.py#L117) (Zeile 117)
- [test_reaped_session_preserves_confirmed_duration_without_growing_after_reload](../../tests/test_agent_accounting_audit.py#L126) (Zeile 126)
- [test_ledger_versions_cover_reservation_settlement_and_released_review_hold](../../tests/test_agent_accounting_audit.py#L143) (Zeile 143)

</details>

<a id="test-agent-admission-py"></a>

## test_agent_admission.py

**Quelle:** [tests/test_agent_admission.py](../../tests/test_agent_admission.py) · **Bereiche:** Konten und Tarife.

**Ebene:** Agent-Admission mit echten Tokenzählern und Provider-Doubles.

**Lauf:** 15 bestanden.

**Geprüftes Verhalten:** Realistischer großer Prompt bei 20.933 Resttokens; offline Unicode/Spezialtokens und Schema-Overhead; reduzierte Output-Caps in Request und Receipt; Suchreservierung erst bei Bedarf; paralleles Warten inklusive Stop ohne doppelte Calls; erschöpftes Budget ohne Dispatch; Teilantwort bei Outputlimit; Contextfenster und Reasoningminimum; Systemprompt/Workerfreigabe; Fortsetzung nach nativer Suche ohne doppelte Suche.

**Grenzen und Doubles:** Provideraufrufe sind geskriptet und Firestore ist ein Fake. Die lokale Tokenzählung ist keine Bestätigung der Tokenisierung jedes Providers.

**Prüfauftrag für den Folgeaudit:** Grenzen je tatsächlichem Modellkontext, reservierter Suchumfang und langlaufende Waiter im Emulator abgleichen.

**Direkte Codeverweise:** [app/services/agent_costs.py](../../app/services/agent_costs.py), [app/services/agent_policy.py](../../app/services/agent_policy.py), [app/services/agent_quota.py](../../app/services/agent_quota.py), [app/services/agent_tokens.py](../../app/services/agent_tokens.py), [app/services/agent_tools.py](../../app/services/agent_tools.py), [app/services/llm/agent_client.py](../../app/services/llm/agent_client.py), [app/services/llm/provider_runtime.py](../../app/services/llm/provider_runtime.py).

**Direkte Testhelfer:** [tests/test_agent_comparison.py](../../tests/test_agent_comparison.py), [tests/test_agent_continuation.py](../../tests/test_agent_continuation.py), [tests/test_agent_runs.py](../../tests/test_agent_runs.py).

<details>
<summary>11 Testdefinitionen und ihre Quellstellen</summary>

- [test_screenshot_sized_prompt_fits_20933_tokens_without_byte_reservation](../../tests/test_agent_admission.py#L51) (Zeile 51)
- [test_offline_counting_accepts_unicode_and_special_token_literals](../../tests/test_agent_admission.py#L70) (Zeile 70)
- [test_small_remaining_budget_sets_provider_and_receipt_output_cap](../../tests/test_agent_admission.py#L81) (Zeile 81)
- [test_bounded_search_does_not_reserve_its_results_before_the_search](../../tests/test_agent_admission.py#L100) (Zeile 100)
- [test_parallel_comparison_waits_for_receipt_instead_of_failing_or_shrinking](../../tests/test_agent_admission.py#L113) (Zeile 113)
- [test_truly_exhausted_budget_does_not_dispatch_or_leak_local_reservation](../../tests/test_agent_admission.py#L164) (Zeile 164)
- [test_output_limit_preserves_partial_answer_without_claiming_completion](../../tests/test_agent_admission.py#L173) (Zeile 173)
- [test_context_window_can_fit_reduced_output_without_losing_messages](../../tests/test_agent_admission.py#L186) (Zeile 186)
- [test_explicit_reasoning_budget_is_not_shrunk_below_provider_minimum](../../tests/test_agent_admission.py#L196) (Zeile 196)
- [test_consensus_default_overrides_legacy_prompt_and_disabled_workers_are_not_advertised](../../tests/test_agent_admission.py#L206) (Zeile 206)
- [test_server_search_final_answer_resumes_consensus_without_repeating_search](../../tests/test_agent_admission.py#L217) (Zeile 217)

</details>

<a id="test-agent-answer-lifecycle-py"></a>

## test_agent_answer_lifecycle.py

**Quelle:** [tests/test_agent_answer_lifecycle.py](../../tests/test_agent_answer_lifecycle.py) · **Bereiche:** Agent.

**Ebene:** Agent-Loop/Review mit geskripteten Providern.

**Lauf:** 7 bestanden.

**Geprüftes Verhalten:** Früher Judge-Aufruf oder Einleitung ersetzt keine vollständige Antwort; sichtbarer Stream, gespeicherter Wortlaut und Reviewhash stimmen überein. length/max_tokens/cancelled/timeout bewahren Teiltext ohne Judges; leere Antwort scheitert ohne abgeschlossenen Turn.

**Grenzen und Doubles:** Der Ablauf ist real, Antwortinhalt und Provider-Endzustände sind vorgegeben. Keine Bewertung der inhaltlichen Antwort- oder Judgequalität.

**Prüfauftrag für den Folgeaudit:** Zusammenspiel mit Frontend-Reprojektion, Unicode-/Chunkgrenzen und allen Provider-Finish-Reasons abgleichen.

**Direkte Codeverweise:** [app/services/agent_comparison.py](../../app/services/agent_comparison.py), [app/services/llm/agent_client.py](../../app/services/llm/agent_client.py), [app/services/llm/provider_runtime.py](../../app/services/llm/provider_runtime.py).

**Direkte Testhelfer:** [tests/test_agent_comparison.py](../../tests/test_agent_comparison.py), [tests/test_agent_runs.py](../../tests/test_agent_runs.py).

<details>
<summary>3 Testdefinitionen und ihre Quellstellen</summary>

- [test_early_judge_or_intro_cannot_replace_complete_streamed_answer](../../tests/test_agent_answer_lifecycle.py#L69) (Zeile 69)
- [test_incomplete_answer_is_saved_without_starting_judges](../../tests/test_agent_answer_lifecycle.py#L94) (Zeile 94)
- [test_empty_answer_cannot_start_judges_or_complete_the_turn](../../tests/test_agent_answer_lifecycle.py#L111) (Zeile 111)

</details>

<a id="test-agent-budget-config-py"></a>

## test_agent_budget_config.py

**Quelle:** [tests/test_agent_budget_config.py](../../tests/test_agent_budget_config.py) · **Bereiche:** Admin.

**Ebene:** Budgetstore und Admin-API mit Datenbank-Fake.

**Lauf:** 3 bestanden.

**Geprüftes Verhalten:** Cache begrenzt Reads; Limit speichern und Reset ohne Nutzer-Scan; Revision und Resetepoch; konkurrierender Reset lässt einen Gewinner zu; Schreibfehler verändern Cache nicht; Admin-401/403, Schema-422, Konflikt-409 und erfolgreicher Reset/Limit-PUT.

**Grenzen und Doubles:** Concurrency ist durch den Fake synchronisiert; keine echte Firestore-Transaktion oder laufender Browser.

**Prüfauftrag für den Folgeaudit:** Verteilte Cacheinvalidierung und Reset bei aktiven Calls mit test_agent_comparison.py und Emulator abgleichen.

**Direkte Codeverweise:** [app/api/routers/admin.py](../../app/api/routers/admin.py), [app/core/rate_limit.py](../../app/core/rate_limit.py), [app/services/agent_budget_config.py](../../app/services/agent_budget_config.py).

**Direkte Testhelfer:** [tests/test_prompt_config.py](../../tests/test_prompt_config.py).

<details>
<summary>3 Testdefinitionen und ihre Quellstellen</summary>

- [test_cached_configuration_and_atomic_reset_without_scanning_users](../../tests/test_agent_budget_config.py#L13) (Zeile 13)
- [test_reset_is_revision_guarded_and_write_errors_do_not_change_cached_budget](../../tests/test_agent_budget_config.py#L31) (Zeile 31)
- [test_admin_limit_and_reset_routes_require_role_and_revision](../../tests/test_agent_budget_config.py#L64) (Zeile 64)

</details>

<a id="test-agent-capacity-py"></a>

## test_agent_capacity.py

**Quelle:** [tests/test_agent_capacity.py](../../tests/test_agent_capacity.py) · **Bereiche:** Streaming und Wiederherstellung.

**Ebene:** Agent-Kapazität und API mit synchronisiertem Store-Fake.

**Lauf:** 6 bestanden.

**Geprüftes Verhalten:** Ownerlimit über verschiedene Chats und Ownerisolation; Leaseablauf ohne Wiederholung bezahlter Receipts; lokale Admission und idempotente Freigabe; 503/Retry-After vor Turnerstellung bei voller Kapazität bei weiter möglichem Replay; Ownerlimit entsperrt fehlgeschlagenen Turn; nie gestartete Response gibt Ressourcen frei und bewahrt Bookmark ohne Modellkosten.

**Grenzen und Doubles:** Threads laufen innerhalb eines Prozesses gegen gelockten Fake. Leases werden zeitlich manipuliert, kein echter Prozesscrash.

**Prüfauftrag für den Folgeaudit:** Echte Mehrprozesskonkurrenz, Server-Shutdown und Ressourcenfreigabe gegen Emulator-/Betriebstests abgleichen.

**Direkte Codeverweise:** [app/api/routers/agent.py](../../app/api/routers/agent.py), [app/services/agent_runtime.py](../../app/services/agent_runtime.py), [app/services/llm/agent_client.py](../../app/services/llm/agent_client.py).

**Direkte Testhelfer:** [tests/test_agent_runs.py](../../tests/test_agent_runs.py).

<details>
<summary>6 Testdefinitionen und ihre Quellstellen</summary>

- [test_owner_limit_is_atomic_across_different_chats](../../tests/test_agent_capacity.py#L15) (Zeile 15)
- [test_crashed_owner_lease_expires_without_retrying_the_paid_receipt](../../tests/test_agent_capacity.py#L45) (Zeile 45)
- [test_local_admission_is_bounded_and_release_is_idempotent](../../tests/test_agent_capacity.py#L60) (Zeile 60)
- [test_local_capacity_rejects_before_creating_a_turn_and_preserves_replay](../../tests/test_agent_capacity.py#L74) (Zeile 74)
- [test_owner_capacity_failure_unlocks_unclaimed_turn_and_does_not_call_model](../../tests/test_agent_capacity.py#L97) (Zeile 97)
- [test_response_never_entered_releases_pending_turn_without_a_paid_claim](../../tests/test_agent_capacity.py#L111) (Zeile 111)

</details>

<a id="test-agent-chat-integrity-py"></a>

## test_agent_chat_integrity.py

**Quelle:** [tests/test_agent_chat_integrity.py](../../tests/test_agent_chat_integrity.py) · **Bereiche:** Agent.

**Ebene:** Chatpolicy und Delegation mit kontrollierten Completion-Klassen.

**Lauf:** 15 bestanden.

**Geprüftes Verhalten:** Vergleiche im Toolbatch enden vor Judge/Synthese; direkte Antworten erst nach vollständigem toolfreiem Ergebnis; Fehlturns erhalten Frage und gegebenenfalls markierte Teilantwort im Folgekontext; legitime Error-Texte und 6.000/6.001 Zeichen bleiben erhalten; fehlender Judgecall wird ohne extra Routing ergänzt; wiederholt ungültige Tools stoppen nach drei Calls; akzeptierte, überarbeitete und geprüfte Fallback-Workerergebnisse erreichen Synthese ohne veraltete/private Daten.

**Grenzen und Doubles:** Die Entscheidungskette und Worker laufen mit geskripteten Modellentscheidungen; kein Nachweis, wie oft reale Modelle diese Pfade wählen. Datenbank-Fake.

**Prüfauftrag für den Folgeaudit:** Toolbatch-Reihenfolgen, zusätzliche ungültige Protokollvarianten und adversarielle Toolinhalte im späteren Audit abgleichen.

**Direkte Codeverweise:** [app/services/agent_comparison.py](../../app/services/agent_comparison.py), [app/services/agent_policy.py](../../app/services/agent_policy.py), [app/services/llm/agent_client.py](../../app/services/llm/agent_client.py), [app/services/llm/provider_runtime.py](../../app/services/llm/provider_runtime.py).

**Direkte Testhelfer:** [tests/test_agent_answer_lifecycle.py](../../tests/test_agent_answer_lifecycle.py), [tests/test_agent_comparison.py](../../tests/test_agent_comparison.py), [tests/test_agent_delegation.py](../../tests/test_agent_delegation.py), [tests/test_agent_runs.py](../../tests/test_agent_runs.py).

<details>
<summary>8 Testdefinitionen und ihre Quellstellen</summary>

- [test_comparisons_in_a_batch_finish_before_its_judge_and_synthesis](../../tests/test_agent_chat_integrity.py#L28) (Zeile 28)
- [test_direct_reply_is_published_once_after_complete_non_tool_response](../../tests/test_agent_chat_integrity.py#L59) (Zeile 59)
- [test_interrupted_visible_answer_is_in_next_turn_context_without_private_failure](../../tests/test_agent_chat_integrity.py#L83) (Zeile 83)
- [test_failed_turn_without_an_answer_keeps_the_users_request](../../tests/test_agent_chat_integrity.py#L97) (Zeile 97)
- [test_valid_comparison_text_is_retained_with_consistent_session_status](../../tests/test_agent_chat_integrity.py#L107) (Zeile 107)
- [test_missing_judge_call_starts_existing_judges_without_more_orchestrator_requests](../../tests/test_agent_chat_integrity.py#L130) (Zeile 130)
- [test_repeated_invalid_tools_stop_without_exhausting_daily_allowance](../../tests/test_agent_chat_integrity.py#L140) (Zeile 140)
- [test_late_worker_results_reach_synthesis_after_review_without_stale_or_private_data](../../tests/test_agent_chat_integrity.py#L162) (Zeile 162)

</details>

<a id="test-agent-comparison-py"></a>

## test_agent_comparison.py

**Quelle:** [tests/test_agent_comparison.py](../../tests/test_agent_comparison.py) · **Bereiche:** Agent.

**Ebene:** Gemeinsame Judge-/Comparison-Logik mit kontrollierten Modellen.

**Lauf:** 44 bestanden.

**Geprüftes Verhalten:** Exakte unveränderliche Antwortversion, Hashbindung und Quell-/Kontextübernahme; mehrere Vergleiche, fehlender Toolcall, Teilausfälle und Rate-Limits; vollständige Usage und Tagesquota, konkurrierende Claims/doppeltes Settlement; Reset während laufender Calls, Suchfallback, UTC-Wechsel und Reviewholds; konfigurierte familienabhängige Judge-Fallbacks inklusive 404/Timeout/leer/Cooldown; Disconnect, reine Recovery ohne Call sowie Settlementfehler vor/nach Commit ohne doppelte Generierung.

**Grenzen und Doubles:** „Real judges“ meint hier echte Parser/Orchestrierung mit synthetischen Judgeantworten. Die Transaktionsfehler werden im In-Memory-Store injiziert; keine reale Modellqualität/Firestore-Konkurrenz.

**Prüfauftrag für den Folgeaudit:** Fallbackkonfiguration bei neuen Modellfamilien, unterschiedliche Fehlerabfolgen und verteilte Commit-Ungewissheit abgleichen.

**Direkte Codeverweise:** [app/core/config.py](../../app/core/config.py), [app/services/agent_budget_config.py](../../app/services/agent_budget_config.py), [app/services/agent_comparison.py](../../app/services/agent_comparison.py), [app/services/agent_delegation.py](../../app/services/agent_delegation.py), [app/services/agent_delegation_config.py](../../app/services/agent_delegation_config.py), [app/services/agent_policy.py](../../app/services/agent_policy.py), [app/services/agent_provider_limits.py](../../app/services/agent_provider_limits.py), [app/services/agent_quota.py](../../app/services/agent_quota.py), [app/services/llm/agent_client.py](../../app/services/llm/agent_client.py), [app/services/llm/provider_runtime.py](../../app/services/llm/provider_runtime.py).

**Direkte Testhelfer:** [tests/test_agent_runs.py](../../tests/test_agent_runs.py).

<details>
<summary>19 Testdefinitionen und ihre Quellstellen</summary>

- [test_real_judges_exact_versions_context_sources_and_all_usage](../../tests/test_agent_comparison.py#L89) (Zeile 89)
- [test_fixed_answer_cannot_be_reopened_by_false_finalize_or_late_comparison](../../tests/test_agent_comparison.py#L122) (Zeile 122)
- [test_partial_or_failed_checks_never_certify_success](../../tests/test_agent_comparison.py#L144) (Zeile 144)
- [test_rate_limited_answer_is_distinct_from_successful_judges](../../tests/test_agent_comparison.py#L155) (Zeile 155)
- [test_review_binding_survives_saved_turn_projection_without_normalizing_text](../../tests/test_agent_comparison.py#L176) (Zeile 176)
- [test_review_issues_explain_each_missing_check](../../tests/test_agent_comparison.py#L207) (Zeile 207)
- [test_missing_tool_uses_existing_review_and_persists_checked_answer](../../tests/test_agent_comparison.py#L212) (Zeile 212)
- [test_atomic_daily_budget_and_duplicate_settlement](../../tests/test_agent_comparison.py#L223) (Zeile 223)
- [test_quota_rejection_distinguishes_empty_from_insufficient_reservation](../../tests/test_agent_comparison.py#L246) (Zeile 246)
- [test_admin_budget_is_enforced_and_reset_isolated_from_inflight_settlement](../../tests/test_agent_comparison.py#L257) (Zeile 257)
- [test_search_reservation_can_fall_back_without_extra_paid_claim](../../tests/test_agent_comparison.py#L284) (Zeile 284)
- [test_unknown_terminal_usage_releases_admission_and_utc_day_is_separate](../../tests/test_agent_comparison.py#L316) (Zeile 316)
- [test_configured_default_uses_cross_family_judges](../../tests/test_agent_comparison.py#L327) (Zeile 327)
- [test_gemini_chat_uses_standard_luna_then_flash_lite_for_both_judges](../../tests/test_agent_comparison.py#L338) (Zeile 338)
- [test_unavailable_chat_judges_stop_after_standard_fallback](../../tests/test_agent_comparison.py#L396) (Zeile 396)
- [test_midnight_moves_only_unspent_review_hold](../../tests/test_agent_comparison.py#L420) (Zeile 420)
- [test_disconnect_during_review_settles_every_paid_call_and_marks_stopped](../../tests/test_agent_comparison.py#L434) (Zeile 434)
- [test_failed_review_recovery_preserves_status_and_never_calls_provider](../../tests/test_agent_comparison.py#L450) (Zeile 450)
- [test_transient_settlement_failure_never_repeats_model_or_leaves_run_pending](../../tests/test_agent_comparison.py#L471) (Zeile 471)

</details>

<a id="test-agent-continuation-py"></a>

## test_agent_continuation.py

**Quelle:** [tests/test_agent_continuation.py](../../tests/test_agent_continuation.py) · **Bereiche:** Agent.

**Ebene:** Langlauf-/Recovery-Verträge mit Fake-Uhr, Store und Providern.

**Lauf:** 13 bestanden.

**Geprüftes Verhalten:** 102 Calls über simulierte 17 Minuten bei lebender Lease; Tagesbudget bleibt begrenzend; Leaseverlängerung synchronisiert Sperren, stop/expired/superseded werden nicht wiederbelebt; Timeout bewahrt Teiltext mit sicherem Fehler; mehrere Vergleiche ohne fixen Reviewhold, alte Analysebudgets bleiben begrenzt; finalisierte Antwort unveränderlich; kurzer DB-Ausfall wird toleriert; Routing-/Vorantwortfehler bleiben ehrlich gespeichert und Recovery räumt verwaiste Produzenten ohne bezahlten Retry auf.

**Grenzen und Doubles:** Die 17 Minuten sind eine kontrollierte Uhr, kein 17-minütiger Dauertest. DB-Ausfall/Timeout/Leaseablauf werden simuliert; Provider und Datenbank sind ersetzt.

**Prüfauftrag für den Folgeaudit:** Reale Prozessneustarts, anhaltende Datenbankausfälle und Langzeitressourcenverbrauch separat prüfen.

**Direkte Codeverweise:** [app/services/agent_comparison.py](../../app/services/agent_comparison.py), [app/services/agent_delegation.py](../../app/services/agent_delegation.py), [app/services/agent_delegation_config.py](../../app/services/agent_delegation_config.py), [app/services/agent_policy.py](../../app/services/agent_policy.py), [app/services/agent_provider_limits.py](../../app/services/agent_provider_limits.py), [app/services/agent_quota.py](../../app/services/agent_quota.py), [app/services/agent_sessions.py](../../app/services/agent_sessions.py), [app/services/llm/agent_client.py](../../app/services/llm/agent_client.py), [app/services/llm/provider_runtime.py](../../app/services/llm/provider_runtime.py).

**Direkte Testhelfer:** [tests/test_agent_comparison.py](../../tests/test_agent_comparison.py), [tests/test_agent_runs.py](../../tests/test_agent_runs.py).

<details>
<summary>11 Testdefinitionen und ihre Quellstellen</summary>

- [test_more_than_one_hundred_steps_and_seventeen_minutes_complete_with_live_lease](../../tests/test_agent_continuation.py#L46) (Zeile 46)
- [test_daily_budget_still_stops_before_any_additional_paid_step_and_saves_reason](../../tests/test_agent_continuation.py#L81) (Zeile 81)
- [test_lease_renewal_keeps_all_fences_in_sync_but_never_revives_a_stopped_run](../../tests/test_agent_continuation.py#L100) (Zeile 100)
- [test_mid_answer_provider_timeout_preserves_text_and_safe_reason_in_history](../../tests/test_agent_continuation.py#L126) (Zeile 126)
- [test_many_comparisons_use_actual_call_reservations_without_fixed_review_hold](../../tests/test_agent_continuation.py#L142) (Zeile 142)
- [test_consensus_and_legacy_analysis_budgets_remain_bounded](../../tests/test_agent_continuation.py#L155) (Zeile 155)
- [test_account_budget_does_not_allow_more_comparisons_or_revisions_after_review](../../tests/test_agent_continuation.py#L162) (Zeile 162)
- [test_brief_database_outage_does_not_cancel_a_healthy_producer](../../tests/test_agent_continuation.py#L196) (Zeile 196)
- [test_interrupted_routing_recovery_preserves_failure_without_publishing_unconfirmed_text](../../tests/test_agent_continuation.py#L215) (Zeile 215)
- [test_failure_before_answer_preserves_question_activity_and_bookmark](../../tests/test_agent_continuation.py#L246) (Zeile 246)
- [test_recovery_reaps_expired_producer_and_restores_checkpoint_without_paid_retry](../../tests/test_agent_continuation.py#L270) (Zeile 270)

</details>

<a id="test-agent-contradictions-py"></a>

## test_agent_contradictions.py

**Quelle:** [tests/test_agent_contradictions.py](../../tests/test_agent_contradictions.py) · **Bereiche:** Quellenprüfung.

**Ebene:** Agent-Quellenprüfung mit Fetch-/Judge-Doubles.

**Lauf:** 11 bestanden.

**Geprüftes Verhalten:** Toolfreigabe und eingefrorene Settings; Originalbelege, getrenntes Quellenurteil, genaue Hashbindung und sämtliche Callkosten; fehlender Toolcall wird automatisch ergänzt; ungültige Belege ergeben partial; keine Widersprüche überspringen Fetch/Judge; Fallback wird abgerechnet; weitere Modellrunden ändern die fixierte Antwort nicht; Cancellation beendet alle Findings ohne pending.

**Grenzen und Doubles:** Differences-Antworten, Quellenabruf und Modellantworten sind vorgegeben; kein Live-Belegabruf und keine echte Quellenwahrheit.

**Prüfauftrag für den Folgeaudit:** Ergänzung durch die eigenständigen Source-Verifikationstests und Browserprojektion prüfen.

**Direkte Codeverweise:** [app/services/agent_comparison.py](../../app/services/agent_comparison.py), [app/services/agent_contradictions.py](../../app/services/agent_contradictions.py), [app/services/agent_quota.py](../../app/services/agent_quota.py), [app/services/llm/agent_client.py](../../app/services/llm/agent_client.py), [app/services/llm/consensus_engine.py](../../app/services/llm/consensus_engine.py), [app/services/llm/provider_runtime.py](../../app/services/llm/provider_runtime.py), [app/services/source_verification.py](../../app/services/source_verification.py).

**Direkte Testhelfer:** [tests/test_agent_comparison.py](../../tests/test_agent_comparison.py), [tests/test_agent_runs.py](../../tests/test_agent_runs.py), [tests/test_contradiction_verification.py](../../tests/test_contradiction_verification.py).

<details>
<summary>10 Testdefinitionen und ihre Quellstellen</summary>

- [test_enabled_tool_persists_original_evidence_exact_binding_and_all_usage](../../tests/test_agent_contradictions.py#L86) (Zeile 86)
- [test_disabled_tool_never_fetches_and_keeps_model_agreement_review](../../tests/test_agent_contradictions.py#L112) (Zeile 112)
- [test_missing_enabled_tool_still_executes_existing_source_check](../../tests/test_agent_contradictions.py#L122) (Zeile 122)
- [test_invalid_original_evidence_is_not_a_successful_source_check](../../tests/test_agent_contradictions.py#L131) (Zeile 131)
- [test_no_contradictions_skips_fetch_and_paid_source_judge](../../tests/test_agent_contradictions.py#L140) (Zeile 140)
- [test_source_fallback_is_metered_and_not_a_new_comparison](../../tests/test_agent_contradictions.py#L151) (Zeile 151)
- [test_api_freezes_setting_and_recovery_rejects_different_tool_permission](../../tests/test_agent_contradictions.py#L163) (Zeile 163)
- [test_source_check_finishes_once_even_when_model_requests_more_rounds](../../tests/test_agent_contradictions.py#L179) (Zeile 179)
- [test_rewrite_during_source_tool_step_never_reaches_stream_or_saved_answer](../../tests/test_agent_contradictions.py#L191) (Zeile 191)
- [test_cancellation_during_retrieval_keeps_answer_and_terminal_check](../../tests/test_agent_contradictions.py#L205) (Zeile 205)

</details>

<a id="test-agent-delegation-py"></a>

## test_agent_delegation.py

**Quelle:** [tests/test_agent_delegation.py](../../tests/test_agent_delegation.py) · **Bereiche:** Agent.

**Ebene:** Echte Workerthreads/Mailboxen mit Store- und Provider-Doubles.

**Lauf:** 16 bestanden.

**Geprüftes Verhalten:** Zwei gleichzeitig laufende Worker mit Rückfrage, Antwort, Rework und Review; Persistenz, Sequenzdeduplizierung, Pagination/Ownerbindung und Kosten; einfache Antwort ohne Delegation/Replaycall; Workerfehler mit Unknown-Kosten; atomare lokale/persistente Budgetreservierung im Fake; Stop joint Worker; Crash-/Leaserecovery; signierte Reasoningblöcke bleiben privat; Toolbatch-Ergebnisse; eingefrorene Konfiguration; Evaluationsgate lehnt schlechte/unvollständige Vergleiche ab; Nachricht während Generierung, Remote-Stop und geprüfter 429-Fallback.

**Grenzen und Doubles:** Synchronisierte In-Memory-Transaktionen ersetzen Firestore. Evaluationsgate wird mit konstruierten Ergebniszeilen geprüft, nicht die Qualität echter Delegation.

**Prüfauftrag für den Folgeaudit:** Crash zwischen Mailbox-/Event-/Receiptwrites und echte Prozessgrenzen gegen Emulatorprüfungen abgleichen.

**Direkte Codeverweise:** [app/api/routers/agent.py](../../app/api/routers/agent.py), [app/services/agent_costs.py](../../app/services/agent_costs.py), [app/services/agent_delegation.py](../../app/services/agent_delegation.py), [app/services/agent_delegation_config.py](../../app/services/agent_delegation_config.py), [app/services/agent_policy.py](../../app/services/agent_policy.py), [app/services/agent_provider_limits.py](../../app/services/agent_provider_limits.py), [app/services/chat_store.py](../../app/services/chat_store.py), [app/services/llm/agent_client.py](../../app/services/llm/agent_client.py), [app/services/llm/engines.py](../../app/services/llm/engines.py), [app/services/llm/provider_runtime.py](../../app/services/llm/provider_runtime.py), [app/services/prompt_config.py](../../app/services/prompt_config.py), [scripts/evaluate_agent_delegation.py](../../scripts/evaluate_agent_delegation.py).

**Direkte Testhelfer:** [tests/test_agent_loop.py](../../tests/test_agent_loop.py), [tests/test_agent_runs.py](../../tests/test_agent_runs.py).

<details>
<summary>16 Testdefinitionen und ihre Quellstellen</summary>

- [test_parallel_question_answer_rework_and_review_persist_same_session_and_total_costs](../../tests/test_agent_delegation.py#L102) (Zeile 102)
- [test_simple_request_does_not_delegate_or_repeat_after_reload](../../tests/test_agent_delegation.py#L133) (Zeile 133)
- [test_worker_failure_reports_unknown_cost_and_orchestrator_can_finish_fallback](../../tests/test_agent_delegation.py#L144) (Zeile 144)
- [test_activity_view_reuses_the_receipt_read_for_lease_check](../../tests/test_agent_delegation.py#L156) (Zeile 156)
- [test_atomic_durable_and_memory_budget_reservations](../../tests/test_agent_delegation.py#L166) (Zeile 166)
- [test_stop_joins_all_workers_and_accounts_every_started_step](../../tests/test_agent_delegation.py#L194) (Zeile 194)
- [test_crashed_process_never_restarts_paid_steps_and_deduplicates_events](../../tests/test_agent_delegation.py#L209) (Zeile 209)
- [test_reasoning_continuation_preserves_signed_blocks_without_public_exposure](../../tests/test_agent_delegation.py#L234) (Zeile 234)
- [test_bounded_parallel_tool_batch_is_replayed_with_every_result](../../tests/test_agent_delegation.py#L251) (Zeile 251)
- [test_delegation_endpoints_are_owner_bound_and_read_only](../../tests/test_agent_delegation.py#L262) (Zeile 262)
- [test_admin_enabled_delegation_is_frozen_and_replay_does_not_consult_new_config](../../tests/test_agent_delegation.py#L275) (Zeile 275)
- [test_quality_gate_rejects_cheap_bad_unknown_unpaired_or_unused_delegation](../../tests/test_agent_delegation.py#L296) (Zeile 296)
- [test_confirmed_own_fallback_finishes_without_echo_rework](../../tests/test_agent_delegation.py#L312) (Zeile 312)
- [test_message_during_active_generation_is_delivered_at_next_boundary](../../tests/test_agent_delegation.py#L325) (Zeile 325)
- [test_remote_stop_cancels_a_worker_with_an_active_stream](../../tests/test_agent_delegation.py#L362) (Zeile 362)
- [test_worker_429_can_use_checked_fallback_without_retrying_worker](../../tests/test_agent_delegation.py#L389) (Zeile 389)

</details>

<a id="test-agent-loop-py"></a>

## test_agent_loop.py

**Quelle:** [tests/test_agent_loop.py](../../tests/test_agent_loop.py) · **Bereiche:** Agent.

**Ebene:** Providerprotokoll und Agentloop mit geskripteten SSE-Zeilen.

**Lauf:** 152 bestanden.

**Geprüftes Verhalten:** Native Suche und erlaubte Quellen; fragmentierte Tools validieren/ausführen/abrechnen; ungültige Argumente, doppelte Keys/IDs, unbekannte Tools und kaputte Toolfragmente scheitern; Call-/Tool-/Token-/Kosten-/Zeitlimits; Cancellation zwischen Schritten und Streamclose; korrekte Unknown-/Teilusage, getrennte Token-/Suchchunks; Suchfähigkeit aller angebotenen Modelle; Claimraces, Löschung zwischen Schritten und Replay; übergroße Toolresultate erreichen keinen nächsten Call; terminale Toolstatus.

**Grenzen und Doubles:** Transport liefert synthetische SSE-Zeilen, kein echter Provider oder Socket. Modellmatrix verwendet dieselben Fixtures. Store ist Fake.

**Prüfauftrag für den Folgeaudit:** Protokolländerungen echter Provider, zusätzliche Chunk-/Unicodegrenzen und Mehrprozessrennen separat abgleichen.

**Direkte Codeverweise:** [app/services/agent_loop.py](../../app/services/agent_loop.py), [app/services/agent_policy.py](../../app/services/agent_policy.py), [app/services/agent_tools.py](../../app/services/agent_tools.py), [app/services/chat_store.py](../../app/services/chat_store.py), [app/services/llm/agent_client.py](../../app/services/llm/agent_client.py), [app/services/llm/engines.py](../../app/services/llm/engines.py), [app/services/llm/provider_runtime.py](../../app/services/llm/provider_runtime.py).

**Direkte Testhelfer:** [tests/test_agent_runs.py](../../tests/test_agent_runs.py).

<details>
<summary>24 Testdefinitionen und ihre Quellstellen</summary>

- [test_native_search_stays_in_selected_model_request_with_real_citations](../../tests/test_agent_loop.py#L79) (Zeile 79)
- [test_explicit_tool_loop_validates_executes_and_settles_each_step_once](../../tests/test_agent_loop.py#L109) (Zeile 109)
- [test_invalid_or_unapproved_tool_never_executes_or_spawns_another_paid_call](../../tests/test_agent_loop.py#L134) (Zeile 134)
- [test_malformed_streamed_tool_calls_close_transport](../../tests/test_agent_loop.py#L147) (Zeile 147)
- [test_repeated_tool_identity_stops_without_reexecution](../../tests/test_agent_loop.py#L155) (Zeile 155)
- [test_limits_prevent_unapproved_work](../../tests/test_agent_loop.py#L167) (Zeile 167)
- [test_cancel_or_failure_in_second_step_keeps_first_usage_and_never_retries](../../tests/test_agent_loop.py#L178) (Zeile 178)
- [test_cancel_between_tool_and_model_prevents_next_claim](../../tests/test_agent_loop.py#L191) (Zeile 191)
- [test_close_during_provider_stream_settles_cancelled_and_closes_socket](../../tests/test_agent_loop.py#L204) (Zeile 204)
- [test_missing_search_cost_keeps_only_cost_reservation](../../tests/test_agent_loop.py#L218) (Zeile 218)
- [test_greetings_offer_optional_search_without_inventing_tool_activity](../../tests/test_agent_loop.py#L236) (Zeile 236)
- [test_interrupted_search_only_records_activity_if_use_is_confirmed](../../tests/test_agent_loop.py#L257) (Zeile 257)
- [test_every_offered_model_can_use_the_consensus_search_route](../../tests/test_agent_loop.py#L270) (Zeile 270)
- [test_crash_receipts_and_continuation_claim_races_remain_fenced](../../tests/test_agent_loop.py#L285) (Zeile 285)
- [test_deletion_between_steps_preserves_accounting_and_fences_next_call](../../tests/test_agent_loop.py#L301) (Zeile 301)
- [test_native_endpoint_replay_uses_receipt_and_does_not_search_again](../../tests/test_agent_loop.py#L316) (Zeile 316)
- [test_known_search_charge_survives_missing_tokens_without_inventing_zero_tokens](../../tests/test_agent_loop.py#L335) (Zeile 335)
- [test_reported_native_limit_violation_is_accounted_and_stops](../../tests/test_agent_loop.py#L348) (Zeile 348)
- [test_usage_beyond_total_budget_stops_after_accounting](../../tests/test_agent_loop.py#L357) (Zeile 357)
- [test_two_client_tools_then_final_answer_use_three_steps_and_one_owner_slot](../../tests/test_agent_loop.py#L367) (Zeile 367)
- [test_oversized_tool_result_never_reaches_next_model](../../tests/test_agent_loop.py#L383) (Zeile 383)
- [test_close_on_tool_started_persists_stopped_instead_of_working](../../tests/test_agent_loop.py#L393) (Zeile 393)
- [test_normalized_input_output_usage_aliases](../../tests/test_agent_loop.py#L407) (Zeile 407)
- [test_search_and_token_usage_in_separate_chunks_are_merged_once](../../tests/test_agent_loop.py#L413) (Zeile 413)

</details>

<a id="test-agent-mode-ui-py"></a>

## test_agent_mode_ui.py

**Quelle:** [tests/test_agent_mode_ui.py](../../tests/test_agent_mode_ui.py) · **Bereiche:** Agent, Frontend.

**Ebene:** Quelltextverträge.

**Lauf:** 9 bestanden.

**Geprüftes Verhalten:** Agent-spezifische Antwort-Disclosure, separater Direct-/Agent-Präferenzschalter, Free-Menü-Synchronisierung, Stacking, Sprung zu Antworten ohne Präferenzwechsel, explizite Footer-Beschriftung und Wiederherstellung bei manuellem Konsens/Bookmarks.

**Grenzen und Doubles:** Prüft Zeichenketten in JS, Templates und CSS; führt weder Interaktion noch Layout aus.

**Prüfauftrag für den Folgeaudit:** Mit ausführbaren Agent-Projektions- und Browserprüfungen abgleichen; Wechsel während laufender und wiederhergestellter Runs prüfen.

<details>
<summary>9 Testdefinitionen und ihre Quellstellen</summary>

- [test_answer_disclosure_is_agent_mode_only](../../tests/test_agent_mode_ui.py#L10) (Zeile 10)
- [test_disabled_agent_mode_is_a_direct_six_answer_flow](../../tests/test_agent_mode_ui.py#L30) (Zeile 30)
- [test_plus_menu_agent_mode_switch_is_free_and_synchronized](../../tests/test_agent_mode_ui.py#L62) (Zeile 62)
- [test_the_switch_shows_the_setting_not_the_run_on_screen](../../tests/test_agent_mode_ui.py#L79) (Zeile 79)
- [test_direct_comparison_keeps_compact_copy_and_an_accurate_placeholder](../../tests/test_agent_mode_ui.py#L96) (Zeile 96)
- [test_composer_and_its_plus_menu_stay_above_the_answer_boxes](../../tests/test_agent_mode_ui.py#L110) (Zeile 110)
- [test_consensus_jumps_reveal_answers_without_disabling_agent_mode](../../tests/test_agent_mode_ui.py#L126) (Zeile 126)
- [test_consensus_actions_are_explicit_and_hover_preview_has_no_native_duplicate](../../tests/test_agent_mode_ui.py#L141) (Zeile 141)
- [test_answer_disclosure_is_restored_for_manual_consensus_and_bookmarks](../../tests/test_agent_mode_ui.py#L155) (Zeile 155)

</details>

<a id="test-agent-model-catalog-py"></a>

## test_agent_model_catalog.py

**Quelle:** [tests/test_agent_model_catalog.py](../../tests/test_agent_model_catalog.py) · **Bereiche:** Modelle und Provider.

**Ebene:** Katalogcache und Agent-API mit Metadaten-/DB-Doubles.

**Lauf:** 11 bestanden.

**Geprüftes Verhalten:** Gebündelte Cache-Reads und letzte gute Werte bei Ausfall; fester unauthentifizierter Fetch mit Timeout und Bytegrenze; ungültige Preise/Kontext-/Reasoningmetadaten abweisen; Admin-DB steuert neue Modelle, Reihenfolge und Entfernung; unbekannte Metadaten bleiben unverfügbar; Replay verwendet gespeicherten Stand; DB-Ausfall liefert 503.

**Grenzen und Doubles:** Katalog und HTTP-Antwort sind Fixtures; die zugesicherten Grenzen werden an Aufrufargumenten geprüft. Keine aktuelle Live-Modellverfügbarkeit.

**Prüfauftrag für den Folgeaudit:** Cachealter, Fehlformate an der Bytegrenze und geänderte Adminmodelle während paralleler Starts abgleichen.

**Direkte Codeverweise:** [app/api/routers/agent.py](../../app/api/routers/agent.py), [app/core/config.py](../../app/core/config.py), [app/core/security.py](../../app/core/security.py), [app/services/llm/agent_client.py](../../app/services/llm/agent_client.py), [app/services/llm/agent_model_metadata.py](../../app/services/llm/agent_model_metadata.py).

**Direkte Testhelfer:** [tests/test_agent_runs.py](../../tests/test_agent_runs.py).

<details>
<summary>5 Testdefinitionen und ihre Quellstellen</summary>

- [test_public_metadata_cache_coalesces_reads_and_preserves_last_good_values](../../tests/test_agent_model_catalog.py#L21) (Zeile 21)
- [test_public_fetch_uses_one_fixed_unauthenticated_bounded_endpoint](../../tests/test_agent_model_catalog.py#L43) (Zeile 43)
- [test_invalid_metadata_never_becomes_an_admission_estimate](../../tests/test_agent_model_catalog.py#L63) (Zeile 63)
- [test_admin_db_additions_order_removals_and_replay_without_a_code_allowlist](../../tests/test_agent_model_catalog.py#L67) (Zeile 67)
- [test_unavailable_admin_db_is_reported_without_falling_back_to_code_defaults](../../tests/test_agent_model_catalog.py#L116) (Zeile 116)

</details>

<a id="test-agent-progress-py"></a>

## test_agent_progress.py

**Quelle:** [tests/test_agent_progress.py](../../tests/test_agent_progress.py) · **Bereiche:** Agent.

**Ebene:** Fortschrittsfunktionen und Loop mit kontrollierter Uhr/Providern.

**Lauf:** 10 bestanden.

**Geprüftes Verhalten:** Begrenzte Reasoningauszüge, Vorrang später Providerzusammenfassung und Ausschluss roher/verschlüsselter Details; Nutzerfortschritt mehrsprachig, validiert, vor Toolstart und unverändert gespeichert ohne Zusatzcalls; Unicode-Zeichenzähler und Drosselung; gemeldete Tokens ohne Schätzung; coalesced Live-Snapshots ohne zusätzliche Receipts/Transcript; Reworkusage zählt einmal bei voller Eventqueue.

**Grenzen und Doubles:** Reasoning-Auszüge in Worker-/Legacypfaden sind bewusst andere Verträge als der ausgeschlossene Orchestrator-Reasoningstrom. Keine Browserdarstellung oder reale Streaminglatenz.

**Prüfauftrag für den Folgeaudit:** Queue-/Drosselgrenzen und fehlende/falsch geordnete Statusereignisse gegen JS-/Browsertests abgleichen.

**Direkte Codeverweise:** [app/services/agent_delegation.py](../../app/services/agent_delegation.py), [app/services/agent_progress.py](../../app/services/agent_progress.py), [app/services/llm/agent_client.py](../../app/services/llm/agent_client.py).

**Direkte Testhelfer:** [tests/test_agent_comparison.py](../../tests/test_agent_comparison.py), [tests/test_agent_runs.py](../../tests/test_agent_runs.py).

<details>
<summary>9 Testdefinitionen und ihre Quellstellen</summary>

- [test_short_highlights_update_at_boundaries_and_remain_bounded](../../tests/test_agent_progress.py#L14) (Zeile 14)
- [test_provider_summary_replaces_excerpts_and_ignores_raw_reasoning](../../tests/test_agent_progress.py#L29) (Zeile 29)
- [test_late_provider_summary_without_punctuation_replaces_excerpts_at_limit](../../tests/test_agent_progress.py#L39) (Zeile 39)
- [test_live_and_saved_activity_never_contain_full_reasoning](../../tests/test_agent_progress.py#L49) (Zeile 49)
- [test_user_progress_is_ordered_persisted_and_does_not_add_model_calls](../../tests/test_agent_progress.py#L79) (Zeile 79)
- [test_progress_arguments_are_bounded_and_published_only_after_validation](../../tests/test_agent_progress.py#L115) (Zeile 115)
- [test_stream_progress_counts_received_unicode_and_throttles_without_guessing_tokens](../../tests/test_agent_progress.py#L130) (Zeile 130)
- [test_live_usage_replaces_step_snapshots_without_extra_receipts_or_transcript](../../tests/test_agent_progress.py#L150) (Zeile 150)
- [test_worker_rework_adds_settled_usage_once_and_coalesces_without_filling_event_queue](../../tests/test_agent_progress.py#L184) (Zeile 184)

</details>

<a id="test-agent-quota-recovery-py"></a>

## test_agent_quota_recovery.py

**Quelle:** [tests/test_agent_quota_recovery.py](../../tests/test_agent_quota_recovery.py) · **Bereiche:** Konten und Tarife.

**Ebene:** Quota-/Receiptrecovery mit Store-Fake.

**Lauf:** 12 bestanden.

**Geprüftes Verhalten:** Migration terminaler Unknown-Holds bei Erhalt lebender Reservierungen und idempotenter Revision; unbekannte Usage bleibt unbekannt; verlorene Leasemap räumt verwaiste Runs auf und übernimmt nur eindeutige gespeicherte Einzelcallusage; lebende/nachträglich erneuerte Lease bleibt aktiv; unvollständige/provisorische/aggregierte Mehrschrittwerte werden nicht geraten; gelöschter Chat und Tages-/Resetwechsel blockieren keine Quote dauerhaft.

**Grenzen und Doubles:** Leases, alte Dokumente und Renewalrace werden im synchronisierten Fake hergestellt; keine echte Transaktionskonkurrenz zwischen Prozessen.

**Prüfauftrag für den Folgeaudit:** Legacy-Formate und unterschiedliche Crashzeitpunkte mit Emulatorprüfungen vergleichen.

**Direkte Codeverweise:** [app/services/agent_costs.py](../../app/services/agent_costs.py), [app/services/agent_quota.py](../../app/services/agent_quota.py), [app/services/llm/agent_client.py](../../app/services/llm/agent_client.py).

**Direkte Testhelfer:** [tests/test_agent_delegation.py](../../tests/test_agent_delegation.py), [tests/test_agent_runs.py](../../tests/test_agent_runs.py).

<details>
<summary>8 Testdefinitionen und ihre Quellstellen</summary>

- [test_refresh_migrates_terminal_unknown_holds_but_preserves_live_reservations](../../tests/test_agent_quota_recovery.py#L14) (Zeile 14)
- [test_terminal_unknown_usage_releases_admission_without_inventing_zero_usage](../../tests/test_agent_quota_recovery.py#L32) (Zeile 32)
- [test_reload_reaps_lost_lease_map_and_recovers_exact_saved_single_call_usage](../../tests/test_agent_quota_recovery.py#L47) (Zeile 47)
- [test_live_lease_is_never_reaped_by_a_budget_refresh](../../tests/test_agent_quota_recovery.py#L78) (Zeile 78)
- [test_renewal_committed_after_recovery_read_cannot_be_cancelled](../../tests/test_agent_quota_recovery.py#L87) (Zeile 87)
- [test_recovery_never_guesses_an_individual_receipt_from_ambiguous_saved_usage](../../tests/test_agent_quota_recovery.py#L104) (Zeile 104)
- [test_deleted_chat_cannot_leave_an_expired_receipt_blocking_the_account](../../tests/test_agent_quota_recovery.py#L139) (Zeile 139)
- [test_unreported_reservation_cannot_leak_across_day_or_reset](../../tests/test_agent_quota_recovery.py#L151) (Zeile 151)

</details>

<a id="test-agent-reliability-py"></a>

## test_agent_reliability.py

**Quelle:** [tests/test_agent_reliability.py](../../tests/test_agent_reliability.py) · **Bereiche:** Streaming und Wiederherstellung.

**Ebene:** Agentintegration einschließlich HTTPX-MockTransport.

**Lauf:** 17 bestanden.

**Geprüftes Verhalten:** Alte Receipts verdecken keine reparierbaren Reservierungen; Familiencap und unmögliche Admission; Stop vor Claim und zwischen Status/Dispatch; Agentstatus beschädigt keinen Consensus-Turn; Pre-Admission-Lease, superseded Turn und Initialisierungsfehler; gespeicherte Teilsynthese; fertige Vergleichsantwort wird vor langsamem Peer checkpointed; Stillstand mit/ohne Heartbeats schließt Stream und sichert Teiltext; produktiver Stream darf Stallintervall überschreiten.

**Grenzen und Doubles:** Der Testname real_provider_socket_stall verwendet HTTPX MockTransport mit AsyncByteStream, keinen echten Netzwerksocket. Deadline künstlich verkürzt; DB-Fake.

**Prüfauftrag für den Folgeaudit:** Realer Netzabbruch/Proxybuffering und anhaltender Heartbeat ohne semantischen Fortschritt in Deploymentnähe prüfen.

**Direkte Codeverweise:** [app/api/routers/agent.py](../../app/api/routers/agent.py), [app/core/config.py](../../app/core/config.py), [app/services/agent_comparison.py](../../app/services/agent_comparison.py), [app/services/agent_provider_limits.py](../../app/services/agent_provider_limits.py), [app/services/agent_quota.py](../../app/services/agent_quota.py), [app/services/agent_runtime.py](../../app/services/agent_runtime.py), [app/services/agent_tools.py](../../app/services/agent_tools.py), [app/services/chat_store.py](../../app/services/chat_store.py), [app/services/llm/agent_client.py](../../app/services/llm/agent_client.py), [app/services/llm/provider_runtime.py](../../app/services/llm/provider_runtime.py).

**Direkte Testhelfer:** [tests/test_agent_admission.py](../../tests/test_agent_admission.py), [tests/test_agent_comparison.py](../../tests/test_agent_comparison.py), [tests/test_agent_continuation.py](../../tests/test_agent_continuation.py), [tests/test_agent_runs.py](../../tests/test_agent_runs.py).

<details>
<summary>13 Testdefinitionen und ihre Quellstellen</summary>

- [test_legacy_receipts_cannot_hide_recoverable_token_reservations](../../tests/test_agent_reliability.py#L26) (Zeile 26)
- [test_api_comparison_selection_uses_the_same_six_family_cap_as_the_picker](../../tests/test_agent_reliability.py#L40) (Zeile 40)
- [test_admission_cannot_wait_when_even_released_tokens_cannot_fit](../../tests/test_agent_reliability.py#L46) (Zeile 46)
- [test_stop_before_first_claim_fences_later_admission](../../tests/test_agent_reliability.py#L57) (Zeile 57)
- [test_agent_status_and_stop_cannot_fail_a_consensus_turn](../../tests/test_agent_reliability.py#L68) (Zeile 68)
- [test_expired_pre_admission_recovers_without_unlocking_a_new_turn](../../tests/test_agent_reliability.py#L78) (Zeile 78)
- [test_live_pre_admission_is_not_reaped_but_expired_producer_cannot_start](../../tests/test_agent_reliability.py#L91) (Zeile 91)
- [test_stop_between_status_event_and_provider_dispatch_is_known_zero](../../tests/test_agent_reliability.py#L100) (Zeile 100)
- [test_partial_synthesis_survives_after_comparisons](../../tests/test_agent_reliability.py#L114) (Zeile 114)
- [test_loop_initialization_failure_unlocks_chat_and_releases_capacity](../../tests/test_agent_reliability.py#L141) (Zeile 141)
- [test_comparison_checkpoints_finished_answer_while_peer_is_still_running](../../tests/test_agent_reliability.py#L158) (Zeile 158)
- [test_real_provider_socket_stall_releases_receipt_and_preserves_partial_text](../../tests/test_agent_reliability.py#L191) (Zeile 191)
- [test_productive_stream_can_outlive_the_stall_interval](../../tests/test_agent_reliability.py#L218) (Zeile 218)

</details>

<a id="test-agent-runs-py"></a>

## test_agent_runs.py

**Quelle:** [tests/test_agent_runs.py](../../tests/test_agent_runs.py) · **Bereiche:** Agent.

**Ebene:** Store-/API-Verträge mit Auth-/Transport-Doubles.

**Lauf:** 38 bestanden.

**Geprüftes Verhalten:** Token-/Kostenvalidierung ohne doppelte Reasoningtokens; genau einmalige parallele Claims/Settlements, vollständiger Folgekontext und Quellenerhalt; Chat-/Accountlöschsperren und Transaktionsretry; kein Pipelinewechsel; toolfreier SSE-Client; serverseitige Pro/Admin-/Owner-/Schema-Grenzen, reine Recovery, alter Replay überschreibt kein neues Bookmark; Kosten nach Providerfehler und aktuelle Quotafehler; Disconnectcleanup und Receiptlöschung; Katalog/Reasoning/Modellrouting, eingefrorene Auswahl und kleine Kontextfenster; keine unnötigen model_answers-Reads.

**Grenzen und Doubles:** Eigene FastAPI-App mit realen Routern, aber Auth/Tiers, Modellrefresh und Completion ersetzt. Threadkonkurrenz gegen gelockten Fake, kein Firestore-Emulator.

**Prüfauftrag für den Folgeaudit:** API-Middlewaregrenzen mit main.app und echte Transaktionsrennen gegen test_agent_transactions.py abgleichen.

**Direkte Codeverweise:** [app/api/routers/agent.py](../../app/api/routers/agent.py), [app/api/routers/chat_history.py](../../app/api/routers/chat_history.py), [app/core/config.py](../../app/core/config.py), [app/core/rate_limit.py](../../app/core/rate_limit.py), [app/services/account_deletion.py](../../app/services/account_deletion.py), [app/services/agent_quota.py](../../app/services/agent_quota.py), [app/services/agent_runs.py](../../app/services/agent_runs.py), [app/services/chat_store.py](../../app/services/chat_store.py), [app/services/llm/agent_client.py](../../app/services/llm/agent_client.py), [app/services/llm/provider_runtime.py](../../app/services/llm/provider_runtime.py), [app/services/llm/streaming.py](../../app/services/llm/streaming.py), [app/services/persistence_guard.py](../../app/services/persistence_guard.py).

**Direkte Testhelfer:** [tests/test_chat_history.py](../../tests/test_chat_history.py).

<details>
<summary>30 Testdefinitionen und ihre Quellstellen</summary>

- [test_usage_uses_reported_tokens_and_does_not_double_count_reasoning](../../tests/test_agent_runs.py#L65) (Zeile 65)
- [test_parallel_claims_and_settlement_are_exactly_once](../../tests/test_agent_runs.py#L78) (Zeile 78)
- [test_followups_use_all_completed_messages_without_compression](../../tests/test_agent_runs.py#L94) (Zeile 94)
- [test_final_turn_keeps_search_sources_from_previous_steps](../../tests/test_agent_runs.py#L104) (Zeile 104)
- [test_chat_lock_prevents_two_different_turns_running_together](../../tests/test_agent_runs.py#L116) (Zeile 116)
- [test_missing_usage_is_unknown_instead_of_zero](../../tests/test_agent_runs.py#L125) (Zeile 125)
- [test_chat_deletion_does_not_erase_cost_or_resurrect_turn](../../tests/test_agent_runs.py#L135) (Zeile 135)
- [test_account_tombstone_fences_settlement](../../tests/test_agent_runs.py#L145) (Zeile 145)
- [test_failed_transaction_can_settle_again_without_partial_accounting](../../tests/test_agent_runs.py#L154) (Zeile 154)
- [test_conversation_cannot_switch_pipeline](../../tests/test_agent_runs.py#L166) (Zeile 166)
- [test_client_makes_one_tool_free_request_and_reads_final_usage_chunk](../../tests/test_agent_runs.py#L175) (Zeile 175)
- [test_endpoint_single_call_replay_and_cumulative_costs](../../tests/test_agent_runs.py#L235) (Zeile 235)
- [test_access_is_enforced_on_server](../../tests/test_agent_runs.py#L253) (Zeile 253)
- [test_foreign_chat_and_client_supplied_models_or_usage_are_rejected](../../tests/test_agent_runs.py#L265) (Zeile 265)
- [test_recovery_never_starts_a_new_call](../../tests/test_agent_runs.py#L275) (Zeile 275)
- [test_old_replay_keeps_newest_bookmark_and_sums_both_calls](../../tests/test_agent_runs.py#L285) (Zeile 285)
- [test_provider_error_after_usage_still_records_cost](../../tests/test_agent_runs.py#L297) (Zeile 297)
- [test_quota_failure_returns_current_allowance_and_reservation_reason](../../tests/test_agent_runs.py#L334) (Zeile 334)
- [test_disconnect_closes_producer_and_settles_unknown_usage](../../tests/test_agent_runs.py#L358) (Zeile 358)
- [test_account_cleanup_removes_step_receipts](../../tests/test_agent_runs.py#L377) (Zeile 377)
- [test_catalog_reuses_allowlist_and_restricts_reasoning](../../tests/test_agent_runs.py#L385) (Zeile 385)
- [test_invalid_selections_do_not_start_or_lock_a_turn](../../tests/test_agent_runs.py#L422) (Zeile 422)
- [test_model_effort_snapshot_switch_and_recovery_identity](../../tests/test_agent_runs.py#L433) (Zeile 433)
- [test_reasoning_stream_formats_are_bounded_and_never_leak_encrypted_data](../../tests/test_agent_runs.py#L456) (Zeile 456)
- [test_selected_model_prices_and_mandatory_provider_routes](../../tests/test_agent_runs.py#L487) (Zeile 487)
- [test_context_check_precedes_paid_claim_for_small_model](../../tests/test_agent_runs.py#L498) (Zeile 498)
- [test_agent_history_never_queries_empty_model_answers](../../tests/test_agent_runs.py#L513) (Zeile 513)
- [test_configured_default_uses_its_own_prices_context_and_routing](../../tests/test_agent_runs.py#L521) (Zeile 521)
- [test_unknown_default_requires_catalog_instead_of_assuming_deepseek_limits](../../tests/test_agent_runs.py#L537) (Zeile 537)
- [test_bookmark_conflict_and_nonstream_request_are_rejected_before_model_call](../../tests/test_agent_runs.py#L543) (Zeile 543)

</details>

<a id="test-agent-search-py"></a>

## test_agent_search.py

**Quelle:** [tests/test_agent_search.py](../../tests/test_agent_search.py) · **Bereiche:** Modelle und Provider.

**Ebene:** Usage-/Cooldownlogik, Agent-API und geskripteter Transport.

**Lauf:** 61 bestanden.

**Geprüftes Verhalten:** Providerkosten haben Vorrang vor Katalog inkl. Cache/Reasoning/Suche; ungültige Kosten bleiben unbekannt, null ist gültig; Catalogfallback und geteilte Usagechunks; getrennte Token-/Kostenreservierung; sichere Retry-After-Auswertung; Cooldown pro Key/Modell und begrenzter Cache; HTTP-/SSE-429 verhindert sofortigen zweiten bezahlten Claim; 404 liefert handlungsfähigen Fehler und gibt Chatslot frei.

**Grenzen und Doubles:** Providerkosten sind vorgegebene Zahlen und Preise aus dem lokalen Katalog; keine Rechnungsprüfung oder Live-Ratelimits.

**Prüfauftrag für den Folgeaudit:** Weitere Retry-After-Formate, Cacheauslauf und parallele Requests über mehrere Prozesse gegen den Code prüfen.

**Direkte Codeverweise:** [app/api/routers/agent.py](../../app/api/routers/agent.py), [app/services/agent_costs.py](../../app/services/agent_costs.py), [app/services/agent_loop.py](../../app/services/agent_loop.py), [app/services/agent_policy.py](../../app/services/agent_policy.py), [app/services/agent_provider_limits.py](../../app/services/agent_provider_limits.py), [app/services/llm/agent_client.py](../../app/services/llm/agent_client.py), [app/services/llm/engines.py](../../app/services/llm/engines.py).

**Direkte Testhelfer:** [tests/test_agent_loop.py](../../tests/test_agent_loop.py), [tests/test_agent_runs.py](../../tests/test_agent_runs.py).

<details>
<summary>11 Testdefinitionen und ihre Quellstellen</summary>

- [test_provider_total_wins_over_catalog_including_search_cache_and_reasoning](../../tests/test_agent_search.py#L19) (Zeile 19)
- [test_invalid_provider_cost_never_becomes_a_known_zero](../../tests/test_agent_search.py#L36) (Zeile 36)
- [test_provider_zero_is_valid_and_cost_without_tokens_remains_partial](../../tests/test_agent_search.py#L40) (Zeile 40)
- [test_catalog_fallback_accounts_for_cache_writes_once_and_is_labeled](../../tests/test_agent_search.py#L49) (Zeile 49)
- [test_default_prices_match_catalog_instead_of_stale_dataclass_defaults](../../tests/test_agent_search.py#L56) (Zeile 56)
- [test_stream_merges_split_usage_and_records_actual_cost_idempotently](../../tests/test_agent_search.py#L65) (Zeile 65)
- [test_unknown_usage_does_not_release_a_reservation_with_known_cost_only](../../tests/test_agent_search.py#L83) (Zeile 83)
- [test_http_errors_preserve_only_retry_timing](../../tests/test_agent_search.py#L96) (Zeile 96)
- [test_cooldown_is_bounded_and_isolated_by_key_and_model](../../tests/test_agent_search.py#L103) (Zeile 103)
- [test_rate_limit_blocks_immediate_resubmission_without_another_paid_claim](../../tests/test_agent_search.py#L121) (Zeile 121)
- [test_provider_404_has_an_actionable_message_and_releases_the_chat](../../tests/test_agent_search.py#L144) (Zeile 144)

</details>

<a id="test-agent-synthesis-context-py"></a>

## test_agent_synthesis_context.py

**Quelle:** [tests/test_agent_synthesis_context.py](../../tests/test_agent_synthesis_context.py) · **Bereiche:** Agent.

**Ebene:** Synthesekontext und Providerpayload mit kontrolliertem Transport.

**Lauf:** 4 bestanden.

**Geprüftes Verhalten:** Originalgespräch, konfigurierter Stil, Vergleichs- und Worker-/Suchbelege erreichen die isolierte Synthese; interner Tool-/Reasoning-Kontext bleibt draußen, Rollen/Felder sind begrenzt; mehrere oder teilweise Vergleiche; Providerrequest setzt reasoning.exclude bei gleicher Effort-Einstellung und ohne Tools; sichtbarer/gespeicherter Text bleibt exakt reviewgebunden.

**Grenzen und Doubles:** Synthetische Kontexte/Antworten, keine inhaltliche Bewertung durch reale Modelle. Die expliziten Privatmarker decken die verwendeten Beispiele ab.

**Prüfauftrag für den Folgeaudit:** Weitere Protokoll-/Metadatenfelder und sensible Inhalte in legitimen Nutzer-/Tooltexten im späteren Audit unterscheiden.

**Direkte Codeverweise:** [app/services/agent_comparison.py](../../app/services/agent_comparison.py), [app/services/llm/agent_client.py](../../app/services/llm/agent_client.py), [app/services/prompt_config.py](../../app/services/prompt_config.py).

**Direkte Testhelfer:** [tests/test_agent_comparison.py](../../tests/test_agent_comparison.py), [tests/test_agent_loop.py](../../tests/test_agent_loop.py), [tests/test_agent_runs.py](../../tests/test_agent_runs.py).

<details>
<summary>2 Testdefinitionen und ihre Quellstellen</summary>

- [test_synthesis_receives_original_conversation_and_evidence_without_tool_protocol](../../tests/test_agent_synthesis_context.py#L16) (Zeile 16)
- [test_standalone_synthesis_excludes_provider_reasoning_without_changing_effort_or_visible_text](../../tests/test_agent_synthesis_context.py#L71) (Zeile 71)

</details>

<a id="test-agreement-verdict-ui-py"></a>

## test_agreement_verdict_ui.py

**Quelle:** [tests/test_agreement_verdict_ui.py](../../tests/test_agreement_verdict_ui.py) · **Bereiche:** Frontend, Konsens und Unterschiede.

**Ebene:** Quelltextverträge.

**Lauf:** 6 bestanden.

**Geprüftes Verhalten:** Score-Bänder/Beschriftungen, drei persistente Darstellungsmodi samt Legacy-Schlüssel, getrennte Status-/Tooltip-ARIA-Verknüpfung, persistente Highlight-Steuerung und öffentliche Mockup-Texte.

**Grenzen und Doubles:** Wortlaut- und Strukturprüfung; beweist weder numerische Grenzwerte zur Laufzeit noch tatsächliche Accessibility oder Darstellung.

**Prüfauftrag für den Folgeaudit:** Grenzwert-, Tastatur- und Wiederherstellungsfälle mit JS/E2E-Dateien abgleichen.

**Direkte Codeverweise:** [static/demo.js](../../static/demo.js).

<details>
<summary>6 Testdefinitionen und ihre Quellstellen</summary>

- [test_verdict_color_and_label_follow_the_agreement_score](../../tests/test_agreement_verdict_ui.py#L7) (Zeile 7)
- [test_settings_offer_three_agreement_display_levels_persistently](../../tests/test_agreement_verdict_ui.py#L25) (Zeile 25)
- [test_footer_status_is_separate_from_navigation_and_tools_follow_it](../../tests/test_agreement_verdict_ui.py#L42) (Zeile 42)
- [test_the_old_agreement_score_switch_choice_still_applies](../../tests/test_agreement_verdict_ui.py#L53) (Zeile 53)
- [test_sentence_checks_have_a_discreet_persistent_visibility_control](../../tests/test_agreement_verdict_ui.py#L60) (Zeile 60)
- [test_public_mockups_use_the_same_score_semantics](../../tests/test_agreement_verdict_ui.py#L78) (Zeile 78)

</details>

<a id="test-analysis-quality-budget-py"></a>

## test_analysis_quality_budget.py

**Quelle:** [tests/test_analysis_quality_budget.py](../../tests/test_analysis_quality_budget.py) · **Bereiche:** Konsens und Unterschiede.

**Ebene:** Scoring-/Snapshot-/Budgetlogik und HTTPX-MockTransport.

**Lauf:** 14 bestanden.

**Geprüftes Verhalten:** Leere/schwache Evidenz ergibt keinen erfundenen numerischen Score; begrenzte Evidenz deckelt Urteil, Widersprüche bleiben sichtbar; vollständige lange Antworten und gemeldetes Satzlimit; Persistenz von Nullscore/Coverage/Runtime; atomar geteiltes Callbudget und verschachtelte Scopes; Cancellation während Header-/Body-Warten beendet Task/Stream; keine Requests nach Erschöpfung; Coverageworker erbt Budget/Cancel; unbegrenztes Agentbudget wartet ohne Overflow.

**Grenzen und Doubles:** Kontrollierte Evidenz und MockTransport; Scoringkonsistenz wird geprüft, nicht empirische Kalibrierung oder reale LLM-Urteilsqualität.

**Prüfauftrag für den Folgeaudit:** Fehler-/Grenzfälle der Budgetvererbung und Coverage-Aggregation über alle Produzenten abgleichen.

**Direkte Codeverweise:** [app/services/chat_store.py](../../app/services/chat_store.py), [app/services/llm/consensus_engine.py](../../app/services/llm/consensus_engine.py), [app/services/llm/consensus_scoring.py](../../app/services/llm/consensus_scoring.py), [app/services/llm/provider_runtime.py](../../app/services/llm/provider_runtime.py), [app/services/llm/task_transport.py](../../app/services/llm/task_transport.py), [app/services/share_snapshots.py](../../app/services/share_snapshots.py).

<details>
<summary>12 Testdefinitionen und ihre Quellstellen</summary>

- [test_empty_or_sparse_evidence_does_not_create_a_numeric_score](../../tests/test_analysis_quality_budget.py#L28) (Zeile 28)
- [test_limited_coverage_caps_the_verdict_without_hiding_disagreement](../../tests/test_analysis_quality_budget.py#L37) (Zeile 37)
- [test_judges_and_synthesis_share_the_full_answer_including_late_caveats](../../tests/test_analysis_quality_budget.py#L46) (Zeile 46)
- [test_sentence_cap_is_reported_and_limits_overall_score](../../tests/test_analysis_quality_budget.py#L58) (Zeile 58)
- [test_snapshot_preserves_all_claims_null_score_coverage_and_runtime](../../tests/test_analysis_quality_budget.py#L69) (Zeile 69)
- [test_parallel_roles_share_one_atomic_call_budget](../../tests/test_analysis_quality_budget.py#L89) (Zeile 89)
- [test_nested_synthesis_and_judges_do_not_reset_budget](../../tests/test_analysis_quality_budget.py#L103) (Zeile 103)
- [test_nonstream_request_is_cancelled_while_waiting_for_headers](../../tests/test_analysis_quality_budget.py#L116) (Zeile 116)
- [test_paid_transport_is_not_called_after_budget_exhaustion](../../tests/test_analysis_quality_budget.py#L149) (Zeile 149)
- [test_stream_body_read_is_cancelled_and_connection_closed](../../tests/test_analysis_quality_budget.py#L158) (Zeile 158)
- [test_coverage_worker_inherits_budget_and_disconnect_signal](../../tests/test_analysis_quality_budget.py#L196) (Zeile 196)
- [test_unlimited_agent_budget_waits_for_pending_coverage_without_overflow](../../tests/test_analysis_quality_budget.py#L211) (Zeile 211)

</details>

<a id="test-analytics-partial-py"></a>

## test_analytics_partial.py

**Quelle:** [tests/test_analytics_partial.py](../../tests/test_analytics_partial.py) · **Bereiche:** Analytics, Öffentliche Seiten.

**Ebene:** Quelltextverträge.

**Lauf:** 5 bestanden.

**Geprüftes Verhalten:** Zentrales Analytics-Partial in vorgesehenen Templates, Tracking-URL nur dort, Admin ausgeschlossen, Domain-Allowlist und Opt-out-Anleitung/Ladereihenfolge.

**Grenzen und Doubles:** Kein Browser-/Netzwerknachweis, dass Opt-out tatsächlich Requests verhindert.

**Prüfauftrag für den Folgeaudit:** Echten Request-Unterdrückungstest und Domain-/Einwilligungszustände prüfen.

<details>
<summary>5 Testdefinitionen und ihre Quellstellen</summary>

- [test_tracked_pages_include_the_shared_partial](../../tests/test_analytics_partial.py#L28) (Zeile 28)
- [test_website_id_lives_only_in_the_partial](../../tests/test_analytics_partial.py#L34) (Zeile 34)
- [test_admin_pages_are_not_tracked](../../tests/test_analytics_partial.py#L41) (Zeile 41)
- [test_partial_restricts_tracking_to_the_live_domain](../../tests/test_analytics_partial.py#L48) (Zeile 48)
- [test_partial_ships_the_self_exclusion_switch](../../tests/test_analytics_partial.py#L59) (Zeile 59)

</details>

<a id="test-api-account-cleanup-py"></a>

## test_api_account_cleanup.py

**Quelle:** [tests/test_api_account_cleanup.py](../../tests/test_api_account_cleanup.py) · **Bereiche:** Authentifizierung, Öffentliche API.

**Ebene:** Service mit Firebase-Double.

**Lauf:** 4 bestanden.

**Geprüftes Verhalten:** Gesperrter Account wird vor Firebase abgewiesen; disabled und unverified sind zwei Parameterfälle für inaktive Konten; Firebase-Ausfall wird als ApiAccountStatusUnavailable fail-closed weitergegeben.

**Grenzen und Doubles:** is_blocked und auth.get_user werden ersetzt. Keine Prüfung der tatsächlichen Tombstone-Abfrage oder einer vollständigen Cleanup-Kaskade.

**Prüfauftrag für den Folgeaudit:** Erfolgsfall und Zuordnung der Servicefehler zu HTTP-Status in den API-Tests abgleichen.

**Direkte Codeverweise:** [app/services/api_account_cleanup.py](../../app/services/api_account_cleanup.py).

<details>
<summary>3 Testdefinitionen und ihre Quellstellen</summary>

- [test_blocked_account_fails_before_firebase](../../tests/test_api_account_cleanup.py#L13) (Zeile 13)
- [test_disabled_or_unverified_firebase_account_is_inactive](../../tests/test_api_account_cleanup.py#L33) (Zeile 33)
- [test_firebase_outage_fails_closed_as_unavailable](../../tests/test_api_account_cleanup.py#L42) (Zeile 42)

</details>

<a id="test-api-key-repository-py"></a>

## test_api_key_repository.py

**Quelle:** [tests/test_api_key_repository.py](../../tests/test_api_key_repository.py) · **Bereiche:** Authentifizierung, Öffentliche API.

**Ebene:** Repository mit Firestore-Fake.

**Lauf:** 5 bestanden.

**Geprüftes Verhalten:** Klartextschlüssel wird ausgegeben, aber nicht gespeichert; Authentifizierung liefert UID/Key-ID/Scopes und wiederholt last_used_at nicht sofort; Tombstone verhindert Ausgabe; Widerruf sperrt Authentifizierung; Scopes werden validiert und Legacy-Schlüssel bekommen eingeschränkte Defaults.

**Grenzen und Doubles:** In-Memory-Datenbank; kein echter Firestore-Zugriff. Der Textvergleich des gespeicherten Zustands belegt die Abwesenheit des ausgegebenen Schlüssels, keine umfassende kryptografische Sicherheitsanalyse.

**Prüfauftrag für den Folgeaudit:** Ungültige Schlüsselvarianten, Cache-/Zeitgrenzen und Scope-Durchsetzung an jedem Endpoint gegen andere Tests abgleichen.

**Direkte Codeverweise:** [app/services/api_key_repository.py](../../app/services/api_key_repository.py), [app/services/persistence_guard.py](../../app/services/persistence_guard.py).

<details>
<summary>5 Testdefinitionen und ihre Quellstellen</summary>

- [test_plaintext_key_is_returned_once_but_never_persisted](../../tests/test_api_key_repository.py#L71) (Zeile 71)
- [test_account_deletion_tombstone_fences_api_key_issue](../../tests/test_api_key_repository.py#L89) (Zeile 89)
- [test_revoked_key_cannot_authenticate](../../tests/test_api_key_repository.py#L102) (Zeile 102)
- [test_scopes_are_validated_persisted_and_authenticated](../../tests/test_api_key_repository.py#L112) (Zeile 112)
- [test_legacy_key_without_scopes_gets_safe_defaults](../../tests/test_api_key_repository.py#L128) (Zeile 128)

</details>

<a id="test-api-run-repository-py"></a>

## test_api_run_repository.py

**Quelle:** [tests/test_api_run_repository.py](../../tests/test_api_run_repository.py) · **Bereiche:** Persistenz, Öffentliche API.

**Ebene:** Repository mit synchronisiertem Firestore-Fake.

**Lauf:** 8 bestanden.

**Geprüftes Verhalten:** Idempotente Erstellung und Konflikt bei anderem Payload, gehashter Idempotenzschlüssel und Retention; Tombstone sperrt Erstellung und Workertransition; unter konkurrierenden Threads gewinnt ein Claim; accepted/reserved/running/succeeded und terminaler Replay; abgelaufene Lease führt ohne Requeue zu failed; nur Owner kann terminalen Run samt Mapping löschen und denselben Schlüssel neu verwenden.

**Grenzen und Doubles:** Nebenläufigkeit läuft gegen einen lokalen Fake mit Lock, nicht gegen verteilte Firestore-Transaktionen. Nicht jede theoretische Zustandskante wird allein durch den Erfolgssequenztest belegt.

**Prüfauftrag für den Folgeaudit:** Lease-Grenzzeitpunkte, Fehler vor/nach Commit und echte konkurrierende Worker gegen Emulator-/Agent-Tests abgleichen.

**Direkte Codeverweise:** [app/services/api_run_repository.py](../../app/services/api_run_repository.py), [app/services/persistence_guard.py](../../app/services/persistence_guard.py).

<details>
<summary>8 Testdefinitionen und ihre Quellstellen</summary>

- [test_create_is_idempotent_and_never_stores_plaintext_key](../../tests/test_api_run_repository.py#L118) (Zeile 118)
- [test_same_key_with_different_request_conflicts](../../tests/test_api_run_repository.py#L134) (Zeile 134)
- [test_pending_account_deletion_fences_api_run_creation](../../tests/test_api_run_repository.py#L141) (Zeile 141)
- [test_pending_account_deletion_fences_worker_transition](../../tests/test_api_run_repository.py#L154) (Zeile 154)
- [test_only_one_concurrent_worker_can_claim_running](../../tests/test_api_run_repository.py#L168) (Zeile 168)
- [test_full_state_sequence_and_terminal_idempotency](../../tests/test_api_run_repository.py#L185) (Zeile 185)
- [test_expired_running_lease_fails_without_requeueing](../../tests/test_api_run_repository.py#L199) (Zeile 199)
- [test_only_owner_can_delete_terminal_run_and_mapping](../../tests/test_api_run_repository.py#L216) (Zeile 216)

</details>

<a id="test-ask-endpoints-py"></a>

## test_ask_endpoints.py

**Quelle:** [tests/test_ask_endpoints.py](../../tests/test_ask_endpoints.py) · **Bereiche:** Modelle und Provider.

**Ebene:** Router und Usage-Repository mit Auth-/Provider-Doubles.

**Lauf:** 14 bestanden.

**Geprüftes Verhalten:** Einheitliche fehlende Auth über Familien, Own-Key-Anforderungen/Login, Pro-only Deep Search und Premiummodelle; Plus-Anhänge/Quote, modellabhängige GLM-Dateifähigkeit und Meta-/Muse-Routing; Zeichen-/UTF-8-Bytegrenzen vor Providerarbeit; Entwicklerkey verbraucht Quote und wird bei Erschöpfung gesperrt, eigener Key verbraucht keine Quote.

**Grenzen und Doubles:** _run_ask bzw. Providerarbeit sind ersetzt; eigene FastAPI-App ohne komplette Middleware. Usage-Repository nutzt synchronisierten Fake.

**Prüfauftrag für den Folgeaudit:** Kompletter Request bis Transport, Grenzwerte je Familie und Middlewarekombination mit weiteren Tests abgleichen.

**Direkte Codeverweise:** [app/api/routers/chat.py](../../app/api/routers/chat.py), [app/core/config.py](../../app/core/config.py), [app/core/rate_limit.py](../../app/core/rate_limit.py), [app/services/usage_repository.py](../../app/services/usage_repository.py).

**Direkte Testhelfer:** [tests/usage_test_support.py](../../tests/usage_test_support.py).

<details>
<summary>14 Testdefinitionen und ihre Quellstellen</summary>

- [test_no_auth_error_is_uniform_across_model_families](../../tests/test_ask_endpoints.py#L60) (Zeile 60)
- [test_own_keys_flag_without_openrouter_key_is_rejected](../../tests/test_ask_endpoints.py#L78) (Zeile 78)
- [test_deep_search_is_pro_only](../../tests/test_ask_endpoints.py#L95) (Zeile 95)
- [test_deep_search_is_refused_for_plus](../../tests/test_ask_endpoints.py#L112) (Zeile 112)
- [test_plus_cannot_ask_a_premium_model](../../tests/test_ask_endpoints.py#L130) (Zeile 130)
- [test_plus_may_attach_a_file_and_gets_the_plus_quota](../../tests/test_ask_endpoints.py#L145) (Zeile 145)
- [test_glm_attachment_support_depends_on_the_effective_model](../../tests/test_ask_endpoints.py#L170) (Zeile 170)
- [test_ask_muse_serves_the_meta_family_and_gates_its_pro_model](../../tests/test_ask_endpoints.py#L204) (Zeile 204)
- [test_megabyte_style_one_word_question_is_rejected_before_provider_work](../../tests/test_ask_endpoints.py#L233) (Zeile 233)
- [test_multibyte_question_and_system_prompt_obey_utf8_byte_caps](../../tests/test_ask_endpoints.py#L251) (Zeile 251)
- [test_usage_limit_blocks_developer_key_path](../../tests/test_ask_endpoints.py#L280) (Zeile 280)
- [test_gemini_developer_path_uses_openrouter_and_counts_usage](../../tests/test_ask_endpoints.py#L301) (Zeile 301)
- [test_own_key_path_bypasses_usage_counting](../../tests/test_ask_endpoints.py#L338) (Zeile 338)
- [test_own_key_without_login_is_rejected_for_every_provider](../../tests/test_ask_endpoints.py#L376) (Zeile 376)

</details>

<a id="test-attachments-py"></a>

## test_attachments.py

**Quelle:** [tests/test_attachments.py](../../tests/test_attachments.py) · **Bereiche:** Anhänge.

**Ebene:** Parser, reale Pillow-/ZIP-Verarbeitung und Payloadbuilder.

**Lauf:** 37 bestanden.

**Geprüftes Verhalten:** Allowlist nach Magic Bytes, Plus-Gate, ungültige Base64, Einzel-/Gesamt-/Anzahl-/Encoded-/Pixelgrenzen; generische ZIPs, DOCX-Bomben und Traversal; DOCX-Text; reale Bildverkleinerung, Byte/Base64-Konsistenz, JPEG-Dateiname, Transparenz und Erhalt kleiner/nicht dekodierbarer Bilder; große PDF Textfallback oder Nativefallback; Dateiblöcke je Provider; Bookmarkmetadaten ohne Dateidaten, MIME-Normalisierung und Listenlimit.

**Grenzen und Doubles:** PDF-Textextraktion der Routingtests ist ersetzt; Payloads werden nicht an Provider gesendet. unittest.subTest-/Schleifenfälle zählen nicht als separate pytest-Items.

**Prüfauftrag für den Folgeaudit:** Exakt-am-Limit-Fälle, zusätzliche defekte Archiv-/Bildformate und Upload-UI/Providerintegration abgleichen.

**Direkte Codeverweise:** [app/api/routers/bookmarks.py](../../app/api/routers/bookmarks.py), [app/services/llm/attachments.py](../../app/services/llm/attachments.py), [app/services/llm/engines.py](../../app/services/llm/engines.py).

<details>
<summary>37 Testdefinitionen und ihre Quellstellen</summary>

- [ParseAttachmentsTests::test_no_attachments_returns_empty_list](../../tests/test_attachments.py#L60) (Zeile 60)
- [ParseAttachmentsTests::test_attachments_are_refused_below_plus](../../tests/test_attachments.py#L64) (Zeile 64)
- [ParseAttachmentsTests::test_valid_types_are_sniffed_from_magic_bytes](../../tests/test_attachments.py#L70) (Zeile 70)
- [ParseAttachmentsTests::test_unsupported_type_is_rejected_even_with_image_extension](../../tests/test_attachments.py#L87) (Zeile 87)
- [ParseAttachmentsTests::test_generic_zip_is_not_accepted_as_docx](../../tests/test_attachments.py#L93) (Zeile 93)
- [ParseAttachmentsTests::test_docx_text_extraction_joins_paragraphs](../../tests/test_attachments.py#L102) (Zeile 102)
- [ParseAttachmentsTests::test_invalid_base64_is_rejected](../../tests/test_attachments.py#L108) (Zeile 108)
- [ParseAttachmentsTests::test_size_limit_is_enforced](../../tests/test_attachments.py#L114) (Zeile 114)
- [ParseAttachmentsTests::test_encoded_size_limit_is_checked_before_base64_decode](../../tests/test_attachments.py#L121) (Zeile 121)
- [ParseAttachmentsTests::test_docx_zip_bomb_ratio_is_rejected_during_parse](../../tests/test_attachments.py#L133) (Zeile 133)
- [ParseAttachmentsTests::test_docx_traversal_entry_is_rejected](../../tests/test_attachments.py#L145) (Zeile 145)
- [ParseAttachmentsTests::test_attachment_count_limit_is_enforced](../../tests/test_attachments.py#L157) (Zeile 157)
- [ParseAttachmentsTests::test_data_url_prefix_is_tolerated](../../tests/test_attachments.py#L163) (Zeile 163)
- [ImageShrinkTests::test_oversized_image_is_shrunk_to_provider_size](../../tests/test_attachments.py#L189) (Zeile 189)
- [ImageShrinkTests::test_shrunk_image_data_matches_its_bytes](../../tests/test_attachments.py#L199) (Zeile 199)
- [ImageShrinkTests::test_server_side_jpeg_conversion_updates_the_filename](../../tests/test_attachments.py#L203) (Zeile 203)
- [ImageShrinkTests::test_pixel_budget_is_checked_before_image_load](../../tests/test_attachments.py#L207) (Zeile 207)
- [ImageShrinkTests::test_small_image_is_left_untouched](../../tests/test_attachments.py#L222) (Zeile 222)
- [ImageShrinkTests::test_transparency_is_flattened_onto_white](../../tests/test_attachments.py#L228) (Zeile 228)
- [ImageShrinkTests::test_undecodable_image_stays_untouched](../../tests/test_attachments.py#L238) (Zeile 238)
- [ImageShrinkTests::test_total_size_limit_is_enforced](../../tests/test_attachments.py#L243) (Zeile 243)
- [LargePdfRoutingTests::test_large_pdf_goes_out_as_text_instead_of_file](../../tests/test_attachments.py#L274) (Zeile 274)
- [LargePdfRoutingTests::test_large_pdf_without_extractable_text_stays_native](../../tests/test_attachments.py#L283) (Zeile 283)
- [LargePdfRoutingTests::test_small_pdf_still_goes_out_natively](../../tests/test_attachments.py#L289) (Zeile 289)
- [AttachmentPayloadTests::test_openai_image_becomes_openrouter_image_url_block](../../tests/test_attachments.py#L301) (Zeile 301)
- [AttachmentPayloadTests::test_openai_pdf_becomes_input_file_block](../../tests/test_attachments.py#L313) (Zeile 313)
- [AttachmentPayloadTests::test_anthropic_gets_image_and_document_blocks](../../tests/test_attachments.py#L325) (Zeile 325)
- [AttachmentPayloadTests::test_gemini_gets_openrouter_file_block](../../tests/test_attachments.py#L337) (Zeile 337)
- [AttachmentPayloadTests::test_grok_image_native_but_pdf_falls_back_to_text](../../tests/test_attachments.py#L349) (Zeile 349)
- [AttachmentPayloadTests::test_text_only_providers_get_fallback_notes](../../tests/test_attachments.py#L364) (Zeile 364)
- [AttachmentPayloadTests::test_docx_and_text_fall_back_to_extracted_text_for_all_providers](../../tests/test_attachments.py#L378) (Zeile 378)
- [AttachmentPayloadTests::test_no_attachments_keeps_payload_shape_unchanged](../../tests/test_attachments.py#L392) (Zeile 392)
- [BookmarkAttachmentMetaTests::test_missing_field_returns_none_so_merge_keeps_existing](../../tests/test_attachments.py#L407) (Zeile 407)
- [BookmarkAttachmentMetaTests::test_file_data_is_never_stored](../../tests/test_attachments.py#L410) (Zeile 410)
- [BookmarkAttachmentMetaTests::test_invalid_entries_are_dropped](../../tests/test_attachments.py#L417) (Zeile 417)
- [BookmarkAttachmentMetaTests::test_list_is_capped_and_non_list_becomes_empty](../../tests/test_attachments.py#L426) (Zeile 426)
- [BookmarkAttachmentMetaTests::test_browser_type_variants_survive_as_their_canonical_type](../../tests/test_attachments.py#L431) (Zeile 431)

</details>

<a id="test-auth-revocation-py"></a>

## test_auth_revocation.py

**Quelle:** [tests/test_auth_revocation.py](../../tests/test_auth_revocation.py) · **Bereiche:** Authentifizierung.

**Ebene:** Security-Funktionen mit Auth-/Datenbank-Doubles.

**Lauf:** 4 bestanden.

**Geprüftes Verhalten:** Sensitive Tokenprüfung reicht check_revoked=True weiter; ansonsten gültiges Token scheitert am Tombstone; pending Löschung bleibt trotz altem expires_at gesperrt; Admin-Grenze verlangt Revocation und bildet Tier-Ausfall auf HTTP 503 ab.

**Grenzen und Doubles:** Kein reales widerrufenes Firebase-Token. Ein Test erwartet allgemein Exception mit Text statt eines engeren Exceptiontyps.

**Prüfauftrag für den Folgeaudit:** Revocation-Weitergabe an allen sensitiven Einstiegen sowie Cachewechsel von pending zu completed separat gegen den Produktionscode prüfen.

**Direkte Codeverweise:** [app/api/routers/admin.py](../../app/api/routers/admin.py), [app/core/security.py](../../app/core/security.py).

<details>
<summary>4 Testdefinitionen und ihre Quellstellen</summary>

- [test_live_revocation_flag_is_forwarded_for_sensitive_verification](../../tests/test_auth_revocation.py#L13) (Zeile 13)
- [test_account_deletion_tombstone_rejects_otherwise_valid_token](../../tests/test_auth_revocation.py#L24) (Zeile 24)
- [test_pending_deletion_never_expires_before_cleanup_completes](../../tests/test_auth_revocation.py#L34) (Zeile 34)
- [test_admin_boundary_checks_revocation_and_maps_tier_outage_to_503](../../tests/test_auth_revocation.py#L52) (Zeile 52)

</details>

<a id="test-auth-session-py"></a>

## test_auth_session.py

**Quelle:** [tests/test_auth_session.py](../../tests/test_auth_session.py) · **Bereiche:** Authentifizierung.

**Ebene:** API mit Auth-/Mail-/Notifier-Doubles.

**Lauf:** 8 bestanden.

**Geprüftes Verhalten:** Bestätigter Login setzt HttpOnly-/SameSite=lax-Session und no-store; neue Google-/E-Mail-Nutzer lösen die passende Benachrichtigung aus, vorhandene E-Mail-Nutzer nicht; Mailbox-Setup wird aufgerufen; Neu-/Bestandsantwort sind identisch; altes Clientpasswort wird ignoriert; Kontrollzeichen werden vor Provisionierung mit 422 abgelehnt; Logout löscht Session mit Max-Age=0.

**Grenzen und Doubles:** HTTP-Tests nutzen eine eigene FastAPI-App und ersetzen Auth, Provisionierung, Zustellung und Notifications. Die Cookieassertions prüfen nicht alle Cookieattribute oder einen echten Browser-Login.

**Prüfauftrag für den Folgeaudit:** Secure-/Domain-/Pfadattribute unter Deploymentbedingungen und vollständigen externen Auth-Flow gegen gesonderte Tests prüfen.

**Direkte Codeverweise:** [app/api/routers/auth.py](../../app/api/routers/auth.py), [app/core/rate_limit.py](../../app/core/rate_limit.py).

<details>
<summary>8 Testdefinitionen und ihre Quellstellen</summary>

- [AuthSessionTests::test_confirm_registration_sets_httponly_session_cookie](../../tests/test_auth_session.py#L23) (Zeile 23)
- [AuthSessionTests::test_confirm_registration_notifies_for_recent_google_account](../../tests/test_auth_session.py#L41) (Zeile 41)
- [AuthSessionTests::test_new_email_registration_schedules_telegram_notification](../../tests/test_auth_session.py#L62) (Zeile 62)
- [AuthSessionTests::test_existing_email_registration_does_not_notify](../../tests/test_auth_session.py#L86) (Zeile 86)
- [AuthSessionTests::test_new_and_existing_registration_responses_are_identical](../../tests/test_auth_session.py#L110) (Zeile 110)
- [AuthSessionTests::test_registration_ignores_cached_client_password](../../tests/test_auth_session.py#L144) (Zeile 144)
- [AuthSessionTests::test_registration_rejects_control_characters_before_firebase](../../tests/test_auth_session.py#L162) (Zeile 162)
- [AuthSessionTests::test_logout_clears_session_cookie](../../tests/test_auth_session.py#L172) (Zeile 172)

</details>

<a id="test-background-task-supervision-py"></a>

## test_background_task_supervision.py

**Quelle:** [tests/test_background_task_supervision.py](../../tests/test_background_task_supervision.py) · **Bereiche:** Sicherheit.

**Ebene:** Async-Supervisor und Startupfunktionen mit Cleanup-Doubles.

**Lauf:** 7 bestanden.

**Geprüftes Verhalten:** Neustart nach zwei Abstürzen mit erhaltenem Health-/Successzustand; Alarm nach wiederholtem Fehler und sofort bei einmaligem Task; Retention räumt vor erstem Sleep auf und meldet Counts; degraded/disabled-Health; Startup trennt bounded Konfigurationsread und strikten Backfill.

**Grenzen und Doubles:** Kurze asynchrone Szenarien innerhalb eines Prozesses; Cleanup-/Konfigurationsarbeiten sind ersetzt. Kein kompletter echter Serverneustart.

**Prüfauftrag für den Folgeaudit:** Backoffgrenzen, dauerhafter Alarmversand und reale Lifespan-/Shutdown-Reihenfolge gegen Betriebsprüfungen abgleichen.

**Direkte Codeverweise:** [app/core/background_tasks.py](../../app/core/background_tasks.py), [app/services/retention_maintenance.py](../../app/services/retention_maintenance.py), [app/services/source_check_jobs.py](../../app/services/source_check_jobs.py), [main.py](../../main.py).

<details>
<summary>7 Testdefinitionen und ihre Quellstellen</summary>

- [test_supervisor_restarts_crashes_and_keeps_last_success_health](../../tests/test_background_task_supervision.py#L12) (Zeile 12)
- [test_supervisor_alerts_after_repeated_failure](../../tests/test_background_task_supervision.py#L50) (Zeile 50)
- [test_failed_one_shot_task_alerts_immediately](../../tests/test_background_task_supervision.py#L81) (Zeile 81)
- [test_retention_loop_runs_cleanup_before_first_sleep](../../tests/test_background_task_supervision.py#L100) (Zeile 100)
- [test_maintenance_health_reports_degraded_task_state](../../tests/test_background_task_supervision.py#L139) (Zeile 139)
- [test_startup_readiness_only_loads_bounded_configuration](../../tests/test_background_task_supervision.py#L149) (Zeile 149)
- [test_startup_configuration_write_runs_through_one_shot_wrapper](../../tests/test_background_task_supervision.py#L162) (Zeile 162)

</details>

<a id="test-benchmark-audits-py"></a>

## test_benchmark_audits.py

**Quelle:** [tests/test_benchmark_audits.py](../../tests/test_benchmark_audits.py) · **Bereiche:** Benchmarks.

**Ebene:** Benchmarkrunner mit Fake-Transport und temporären Dateien.

**Lauf:** 9 bestanden.

**Geprüftes Verhalten:** Positions-/Optionspermutation konsistent, inkonsistent oder unentscheidbar; Consensus-Reihenfolge stabil/instabil; Pilot schreibt sämtliche Audit-/Ergebnisartefakte, Budgetstop überspringt Auswertung; Smoke schreibt acht Rollen-Zellen und ausdrücklich deaktivierte Audits, verlangt exakt eine Frage.

**Grenzen und Doubles:** Synthetische feste/positionsabhängige Antworten. Belegt Auditmechanik, keine reale Robustheit oder Benchmarkleistung.

**Prüfauftrag für den Folgeaudit:** Unvollständige/fehlerhafte Auditantworten und statistische Aussagekraft später prüfen.

**Direkte Codeverweise:** [benchmark/prompt.py](../../benchmark/prompt.py), [benchmark/runner.py](../../benchmark/runner.py).

<details>
<summary>9 Testdefinitionen und ihre Quellstellen</summary>

- [PermutationConsistencyUnitTests::test_position_invariant_answer_is_consistent](../../tests/test_benchmark_audits.py#L35) (Zeile 35)
- [PermutationConsistencyUnitTests::test_position_biased_answer_is_inconsistent](../../tests/test_benchmark_audits.py#L40) (Zeile 40)
- [PermutationConsistencyUnitTests::test_missing_letter_is_inconclusive](../../tests/test_benchmark_audits.py#L44) (Zeile 44)
- [ConsensusOrderAuditTests::test_order_invariant_consensus_is_stable](../../tests/test_benchmark_audits.py#L56) (Zeile 56)
- [ConsensusOrderAuditTests::test_order_sensitive_consensus_is_unstable](../../tests/test_benchmark_audits.py#L66) (Zeile 66)
- [RunPilotTests::test_run_pilot_writes_all_artifacts](../../tests/test_benchmark_audits.py#L84) (Zeile 84)
- [RunPilotTests::test_run_pilot_skips_audits_when_budget_stops](../../tests/test_benchmark_audits.py#L114) (Zeile 114)
- [RunSmokeTests::test_run_smoke_writes_base_artifacts_without_e4_audits](../../tests/test_benchmark_audits.py#L136) (Zeile 136)
- [RunSmokeTests::test_run_smoke_validates_exactly_one_question](../../tests/test_benchmark_audits.py#L170) (Zeile 170)

</details>

<a id="test-benchmark-cli-py"></a>

## test_benchmark_cli.py

**Quelle:** [tests/test_benchmark_cli.py](../../tests/test_benchmark_cli.py) · **Bereiche:** Benchmarks.

**Ebene:** CLI-Funktionen mit Dataset-/Runner-/Publisher-Doubles.

**Lauf:** 20 bestanden.

**Geprüftes Verhalten:** Argumente und Ausschlüsse, Run-ID-Priorität, Dry-Run ohne HTTP; Einzel-/Sammelpublikation nur fertiger Runs; Smoke/Pilot/Preview verlangen Budget; fehlende Credentials stoppen; große/finale Runs bleiben gated, freigegebene kleine Modi rufen passenden Runner auf; Konstanten für Gates/Previewcap.

**Grenzen und Doubles:** CLI main wird direkt aufgerufen, Live-Runs/Publikation sind ersetzt. Kein tatsächlicher bezahlter Benchmark oder Firestore-Publish.

**Prüfauftrag für den Folgeaudit:** Echte Shell-Exitcodes, fehlerhafte Manifestdateien und alle Gatekombinationen abgleichen.

**Direkte Codeverweise:** [app/services/benchmark_reports.py](../../app/services/benchmark_reports.py), [app/services/llm/credentials.py](../../app/services/llm/credentials.py), [benchmark/__init__.py](../../benchmark/__init__.py), [benchmark/__main__.py](../../benchmark/__main__.py), [benchmark/config.py](../../benchmark/config.py), [benchmark/report_reader.py](../../benchmark/report_reader.py), [benchmark/runner.py](../../benchmark/runner.py).

<details>
<summary>20 Testdefinitionen und ihre Quellstellen</summary>

- [test_parse_args_supports_new_flags](../../tests/test_benchmark_cli.py#L32) (Zeile 32)
- [test_sample_flags_are_mutually_exclusive](../../tests/test_benchmark_cli.py#L39) (Zeile 39)
- [test_resolve_run_id_precedence](../../tests/test_benchmark_cli.py#L46) (Zeile 46)
- [test_dry_run_creates_run_dir_and_manifest_without_http](../../tests/test_benchmark_cli.py#L54) (Zeile 54)
- [test_run_id_flag_controls_directory](../../tests/test_benchmark_cli.py#L63) (Zeile 63)
- [test_publish_run_publishes_existing_directory_without_pin_check](../../tests/test_benchmark_cli.py#L68) (Zeile 68)
- [test_publish_all_uses_finished_runs_only](../../tests/test_benchmark_cli.py#L90) (Zeile 90)
- [test_smoke_dry_run_uses_own_directory_and_manifest](../../tests/test_benchmark_cli.py#L118) (Zeile 118)
- [test_smoke_live_requires_budget](../../tests/test_benchmark_cli.py#L130) (Zeile 130)
- [test_pilot_live_requires_budget](../../tests/test_benchmark_cli.py#L136) (Zeile 136)
- [test_smoke_rejects_limit](../../tests/test_benchmark_cli.py#L142) (Zeile 142)
- [test_live_aborts_on_missing_credentials](../../tests/test_benchmark_cli.py#L148) (Zeile 148)
- [test_final_live_preflight_passes_but_is_gated_no_http](../../tests/test_benchmark_cli.py#L157) (Zeile 157)
- [test_pilot_live_executes_when_pilot_gate_enabled](../../tests/test_benchmark_cli.py#L171) (Zeile 171)
- [test_smoke_live_executes_when_smoke_gate_enabled](../../tests/test_benchmark_cli.py#L196) (Zeile 196)
- [test_final_preview_requires_budget](../../tests/test_benchmark_cli.py#L223) (Zeile 223)
- [test_final_limit_over_preview_cap_is_rejected](../../tests/test_benchmark_cli.py#L229) (Zeile 229)
- [test_full_final_without_limit_stays_gated](../../tests/test_benchmark_cli.py#L235) (Zeile 235)
- [test_final_preview_executes_when_preview_gate_enabled](../../tests/test_benchmark_cli.py#L245) (Zeile 245)
- [test_live_execution_stays_gated_constant](../../tests/test_benchmark_cli.py#L269) (Zeile 269)

</details>

<a id="test-benchmark-credentials-py"></a>

## test_benchmark_credentials.py

**Quelle:** [tests/test_benchmark_credentials.py](../../tests/test_benchmark_credentials.py) · **Bereiche:** Benchmarks.

**Ebene:** Credential-Hilfsfunktionen mit Envwerten.

**Lauf:** 4 bestanden.

**Geprüftes Verhalten:** Nur gemeinsamer OpenRouter-Key zählt; fremde Providervariablen werden ignoriert, Leerzeichen/blank normalisiert; fehlende Credentials einmalig als OpenRouter gemeldet; Legacy-Providerkeymapping nicht akzeptiert.

**Grenzen und Doubles:** Keine tatsächliche Schlüsselauthentifizierung oder Secretverwaltung außerhalb des Prozesses.

**Prüfauftrag für den Folgeaudit:** Weitere Aufrufer/Logpfade und Env-Vorrang im Betrieb abgleichen.

**Direkte Codeverweise:** [app/services/llm/credentials.py](../../app/services/llm/credentials.py).

<details>
<summary>4 Testdefinitionen und ihre Quellstellen</summary>

- [test_resolve_reads_only_openrouter_env](../../tests/test_benchmark_credentials.py#L6) (Zeile 6)
- [test_resolve_blank_is_none](../../tests/test_benchmark_credentials.py#L14) (Zeile 14)
- [test_missing_credentials_is_one_shared_key](../../tests/test_benchmark_credentials.py#L19) (Zeile 19)
- [test_openrouter_api_key_accepts_shared_mapping](../../tests/test_benchmark_credentials.py#L26) (Zeile 26)

</details>

<a id="test-benchmark-dataset-py"></a>

## test_benchmark_dataset.py

**Quelle:** [tests/test_benchmark_dataset.py](../../tests/test_benchmark_dataset.py) · **Bereiche:** Benchmarks.

**Ebene:** Sampling, DataFrame-Konvertierung und optional Parquet.

**Lauf:** 7 bestanden.

**Geprüftes Verhalten:** Deterministische sortierte Pilotstichprobe, Seedvariation; deterministische Finalstichprobe pro Kategorie, Pilot/Final disjunkt; zu kleine Kategorien scheitern; DataFrame-Felder/Optionen konvertieren; optionaler lokaler Parquet-Roundtrip.

**Grenzen und Doubles:** Parquet-Test ist abhängig von Engine/Fixture überspringbar. Kleine künstliche Datensätze belegen keine Repräsentativität des echten Benchmarks.

**Prüfauftrag für den Folgeaudit:** Skipstatus beachten; Datasetrevision, Duplikate und fehlende/korrupte Felder im späteren Audit prüfen.

**Direkte Codeverweise:** [benchmark/__init__.py](../../benchmark/__init__.py), [benchmark/config.py](../../benchmark/config.py), [benchmark/dataset.py](../../benchmark/dataset.py).

<details>
<summary>7 Testdefinitionen und ihre Quellstellen</summary>

- [SamplingTests::test_pilot_is_deterministic](../../tests/test_benchmark_dataset.py#L46) (Zeile 46)
- [SamplingTests::test_different_seed_changes_pilot](../../tests/test_benchmark_dataset.py#L53) (Zeile 53)
- [SamplingTests::test_final_is_per_category_and_deterministic](../../tests/test_benchmark_dataset.py#L58) (Zeile 58)
- [SamplingTests::test_pilot_and_final_are_disjoint](../../tests/test_benchmark_dataset.py#L71) (Zeile 71)
- [SamplingTests::test_category_shortfall_raises](../../tests/test_benchmark_dataset.py#L77) (Zeile 77)
- [SamplingTests::test_records_from_dataframe](../../tests/test_benchmark_dataset.py#L82) (Zeile 82)
- [SamplingTests::test_parquet_fixture_roundtrip](../../tests/test_benchmark_dataset.py#L105) (Zeile 105)

</details>

<a id="test-benchmark-mode-py"></a>

## test_benchmark_mode.py

**Quelle:** [tests/test_benchmark_mode.py](../../tests/test_benchmark_mode.py) · **Bereiche:** Benchmarks.

**Ebene:** Payloadbuilder und Auditfunktionen.

**Lauf:** 5 bestanden.

**Geprüftes Verhalten:** Closed-book entfernt Tools/tool_choice/include für geprüfte Familien; Normalmodus enthält Suche, Default entspricht Normalmodus; DeepSeek bleibt auf gemeinsamem OpenRouter-Chat-Completions-Payload.

**Grenzen und Doubles:** Keine Provideranfragen; Toolfreiheit im Payload ist kein empirischer Nachweis gegen Modellvorwissen oder versteckte externe Providerfunktionen.

**Prüfauftrag für den Folgeaudit:** Alle registrierten Familien und verschachtelte Webtoolvarianten gegen Registry prüfen.

**Direkte Codeverweise:** [app/services/llm/engines.py](../../app/services/llm/engines.py), [benchmark/audit.py](../../benchmark/audit.py).

<details>
<summary>5 Testdefinitionen und ihre Quellstellen</summary>

- [BenchmarkModeTests::test_benchmark_mode_removes_web_tools_for_all_providers](../../tests/test_benchmark_mode.py#L26) (Zeile 26)
- [BenchmarkModeTests::test_normal_mode_still_injects_web_tools](../../tests/test_benchmark_mode.py#L36) (Zeile 36)
- [BenchmarkModeTests::test_deepseek_benchmark_mode_keeps_openrouter_compatible_payload](../../tests/test_benchmark_mode.py#L45) (Zeile 45)
- [BenchmarkModeTests::test_deepseek_normal_mode_uses_shared_openrouter_search](../../tests/test_benchmark_mode.py#L59) (Zeile 59)
- [BenchmarkModeTests::test_default_matches_normal_mode](../../tests/test_benchmark_mode.py#L74) (Zeile 74)

</details>

<a id="test-benchmark-parse-py"></a>

## test_benchmark_parse.py

**Quelle:** [tests/test_benchmark_parse.py](../../tests/test_benchmark_parse.py) · **Bereiche:** Benchmarks.

**Ebene:** Reine Parser-/Auswertungsfunktionen.

**Lauf:** 12 bestanden.

**Geprüftes Verhalten:** Final-Answer-Marker nur auf letzter nichtleerer Zeile mit tolerierten Schreibweisen; kein semantischer Options-/Buchstabenfallback; Müll/leer/None; Mehrheit bei eindeutiger Höchstzahl, Gleichstand/Enthaltung und leere Stimmen; case-insensitive Grading, None/no_majority nie richtig.

**Grenzen und Doubles:** Explizite Stringbeispiele; keine Modellruns. majority_vote bezeichnet hier den getesteten Gewinner nach Stimmenzählung und verlangt nicht in jedem Beispiel eine absolute Mehrheit.

**Prüfauftrag für den Folgeaudit:** Gültiger Buchstabenbereich, Mehrfachmarker und zusätzliche Format-/Unicodevarianten prüfen.

**Direkte Codeverweise:** [benchmark/parse.py](../../benchmark/parse.py).

<details>
<summary>12 Testdefinitionen und ihre Quellstellen</summary>

- [ExtractLetterTests::test_final_answer_marker_on_last_line](../../tests/test_benchmark_parse.py#L9) (Zeile 9)
- [ExtractLetterTests::test_marker_must_be_last_non_empty_line](../../tests/test_benchmark_parse.py#L19) (Zeile 19)
- [ExtractLetterTests::test_marker_format_is_tolerant](../../tests/test_benchmark_parse.py#L23) (Zeile 23)
- [ExtractLetterTests::test_no_semantic_option_text_or_letter_fallback](../../tests/test_benchmark_parse.py#L36) (Zeile 36)
- [ExtractLetterTests::test_garbage_returns_none](../../tests/test_benchmark_parse.py#L46) (Zeile 46)
- [MajorityVoteTests::test_clear_majority](../../tests/test_benchmark_parse.py#L53) (Zeile 53)
- [MajorityVoteTests::test_tie_is_no_majority](../../tests/test_benchmark_parse.py#L56) (Zeile 56)
- [MajorityVoteTests::test_abstain_votes_ignored](../../tests/test_benchmark_parse.py#L60) (Zeile 60)
- [MajorityVoteTests::test_all_abstain_is_no_majority](../../tests/test_benchmark_parse.py#L63) (Zeile 63)
- [GradeTests::test_correct](../../tests/test_benchmark_parse.py#L69) (Zeile 69)
- [GradeTests::test_incorrect](../../tests/test_benchmark_parse.py#L73) (Zeile 73)
- [GradeTests::test_no_majority_and_none_never_correct](../../tests/test_benchmark_parse.py#L76) (Zeile 76)

</details>

<a id="test-benchmark-redaction-py"></a>

## test_benchmark_redaction.py

**Quelle:** [tests/test_benchmark_redaction.py](../../tests/test_benchmark_redaction.py) · **Bereiche:** Benchmarks.

**Ebene:** Rekursive Redaction und Cellserialisierung.

**Lauf:** 3 bestanden.

**Geprüftes Verhalten:** Sensible Felder verschachtelt entfernen, Headers vollständig redigieren, unkritische Felder behalten, Eingabepayload nicht mutieren; persistierbarer Cellrecord enthält den beispielhaften Schlüssel nicht.

**Grenzen und Doubles:** Schlüssel-/Markerbeispiele sind begrenzt; kein universeller Geheimnisdetektor in Freitext.

**Prüfauftrag für den Folgeaudit:** Response-/Exception-/Metadatenpfade und alternative sensible Feldnamen abgleichen.

**Direkte Codeverweise:** [benchmark/runner.py](../../benchmark/runner.py).

<details>
<summary>3 Testdefinitionen und ihre Quellstellen</summary>

- [RedactionTests::test_redacts_secret_fields_recursively](../../tests/test_benchmark_redaction.py#L20) (Zeile 20)
- [RedactionTests::test_original_payload_is_not_mutated](../../tests/test_benchmark_redaction.py#L38) (Zeile 38)
- [RedactionTests::test_cell_record_cannot_leak_secret](../../tests/test_benchmark_redaction.py#L43) (Zeile 43)

</details>

<a id="test-benchmark-report-reader-py"></a>

## test_benchmark_report_reader.py

**Quelle:** [tests/test_benchmark_report_reader.py](../../tests/test_benchmark_report_reader.py) · **Bereiche:** Benchmarks.

**Ebene:** Dateireader mit Tempdateien und separatem Python-Prozess.

**Lauf:** 4 bestanden.

**Geprüftes Verhalten:** Traversal/fehlende Run-ID wird abgewiesen; Runliste mit Kosten/Artefakten; Matrix, Groundtruth, Disagreement, Majority/Consensus und Retry-Deduplizierung; Readerimport zieht keine LLM-Engines nach.

**Grenzen und Doubles:** Kleine lokale Beispieldateien, keine Firestore-Livequelle oder gleichzeitigen Dateiwriter.

**Prüfauftrag für den Folgeaudit:** Defekte JSONL-/Manifestdaten, Symlinks und unvollständige Schreibvorgänge im späteren Audit prüfen.

**Direkte Codeverweise:** [benchmark/__init__.py](../../benchmark/__init__.py), [benchmark/report_reader.py](../../benchmark/report_reader.py).

<details>
<summary>4 Testdefinitionen und ihre Quellstellen</summary>

- [SafeRunDirTests::test_rejects_traversal_and_missing](../../tests/test_benchmark_report_reader.py#L12) (Zeile 12)
- [ReaderWithTempRunTests::test_list_runs](../../tests/test_benchmark_report_reader.py#L62) (Zeile 62)
- [ReaderWithTempRunTests::test_get_run_matrix_and_dedupe](../../tests/test_benchmark_report_reader.py#L71) (Zeile 71)
- [ReaderWithTempRunTests::test_reader_does_not_import_llm_engines](../../tests/test_benchmark_report_reader.py#L86) (Zeile 86)

</details>

<a id="test-benchmark-reports-py"></a>

## test_benchmark_reports.py

**Quelle:** [tests/test_benchmark_reports.py](../../tests/test_benchmark_reports.py) · **Bereiche:** Benchmarks.

**Ebene:** Report-Publisher mit FakeCollection.

**Lauf:** 2 bestanden.

**Geprüftes Verhalten:** Fertiger Run wird als kompakter versionierter Report gespeichert; rohe Prompt-/Antwort-/Payloadmarker fehlen; Firestorebericht gewinnt bei gleichnamigem lokalen Run.

**Grenzen und Doubles:** FakeCollection ersetzt Firestore; kein realer Upload oder umfassender Datenschutzbeweis.

**Prüfauftrag für den Folgeaudit:** Persistenzfehler, Schemalimits und Auswahl-/Fallbackverhalten bei Ausfällen abgleichen.

**Direkte Codeverweise:** [app/services/benchmark_reports.py](../../app/services/benchmark_reports.py), [benchmark/__init__.py](../../benchmark/__init__.py), [benchmark/report_reader.py](../../benchmark/report_reader.py).

<details>
<summary>2 Testdefinitionen und ihre Quellstellen</summary>

- [test_publish_run_dir_stores_compact_report_only](../../tests/test_benchmark_reports.py#L76) (Zeile 76)
- [test_firestore_runs_win_over_disk_duplicates](../../tests/test_benchmark_reports.py#L93) (Zeile 93)

</details>

<a id="test-benchmark-results-py"></a>

## test_benchmark_results.py

**Quelle:** [tests/test_benchmark_results.py](../../tests/test_benchmark_results.py) · **Bereiche:** Benchmarks.

**Ebene:** Aggregation und Ergebnisdateien.

**Lauf:** 8 bestanden.

**Geprüftes Verhalten:** Frage-/Disagreementcounts, Modell-/Consensus-/Synthesizer-/Majorityaccuracy; Fehler/Enthaltung/Parserraten, Kostensumme und Latenzfelder; no_majority wird falsch gewertet; Retryzeilen dedupliziert, erfolgreicher Retry ersetzt Fehler.

**Grenzen und Doubles:** Künstliche zwei-Fragen-Daten; manche Kosten-/Latenzassertions prüfen nur Existenz/positiven Wert. Keine empirische Modellbewertung.

**Prüfauftrag für den Folgeaudit:** Leere Kohorten, fehlende Systeme, NaN und vollständig gepaarte Nenner im späteren Audit prüfen.

**Direkte Codeverweise:** [benchmark/__init__.py](../../benchmark/__init__.py), [benchmark/results.py](../../benchmark/results.py), [benchmark/runner.py](../../benchmark/runner.py).

<details>
<summary>8 Testdefinitionen und ihre Quellstellen</summary>

- [AggregateTests::test_question_and_disagreement_counts](../../tests/test_benchmark_results.py#L52) (Zeile 52)
- [AggregateTests::test_single_model_accuracy_overall_and_disagreement](../../tests/test_benchmark_results.py#L57) (Zeile 57)
- [AggregateTests::test_error_abstain_and_parse_rate](../../tests/test_benchmark_results.py#L63) (Zeile 63)
- [AggregateTests::test_majority_vote](../../tests/test_benchmark_results.py#L75) (Zeile 75)
- [AggregateTests::test_consensus_and_synth](../../tests/test_benchmark_results.py#L81) (Zeile 81)
- [AggregateTests::test_totals_costs_and_latency](../../tests/test_benchmark_results.py#L88) (Zeile 88)
- [AggregateTests::test_no_majority_bucket](../../tests/test_benchmark_results.py#L95) (Zeile 95)
- [WriteResultsTests::test_write_results_dedupes_retry_rows](../../tests/test_benchmark_results.py#L109) (Zeile 109)

</details>

<a id="test-benchmark-run-py"></a>

## test_benchmark_run.py

**Quelle:** [tests/test_benchmark_run.py](../../tests/test_benchmark_run.py) · **Bereiche:** Benchmarks.

**Ebene:** Runnerintegration mit Fake-Transport und realen Tempdateien.

**Lauf:** 6 bestanden.

**Geprüftes Verhalten:** Acht Zellen je Frage (sechs Modelle/Consensus/Synth-alone), Usage/Labels/Manifest; Consensus erhält Antwortvertrag; Resume vermeidet Duplikate; Fehler bleiben nachvollziehbar und nur explizit retrybar; Budgetstop vor/zwischen Calls und spätere Fortsetzung.

**Grenzen und Doubles:** EndToEnd im Klassennamen meint Runner/Dateien mit synthetischem Provider, keine komplette App oder echte Modelle.

**Prüfauftrag für den Folgeaudit:** Abbruch zwischen Providerantwort und JSONL-Append, beschädigte letzte Zeile und veränderte Konfiguration bei Resume prüfen.

**Direkte Codeverweise:** [benchmark/runner.py](../../benchmark/runner.py).

<details>
<summary>6 Testdefinitionen und ihre Quellstellen</summary>

- [RunEndToEndTests::test_jsonl_append_one_cell_per_call](../../tests/test_benchmark_run.py#L65) (Zeile 65)
- [RunEndToEndTests::test_consensus_receives_benchmark_final_answer_contract](../../tests/test_benchmark_run.py#L94) (Zeile 94)
- [RunEndToEndTests::test_resume_skips_successful_cells_without_duplicates](../../tests/test_benchmark_run.py#L112) (Zeile 112)
- [RunEndToEndTests::test_errors_are_stored_and_controllably_retryable](../../tests/test_benchmark_run.py#L128) (Zeile 128)
- [RunEndToEndTests::test_budget_cap_stops_before_first_call](../../tests/test_benchmark_run.py#L164) (Zeile 164)
- [RunEndToEndTests::test_budget_cap_stops_midway_and_is_resumable](../../tests/test_benchmark_run.py#L177) (Zeile 177)

</details>

<a id="test-benchmark-runner-py"></a>

## test_benchmark_runner.py

**Quelle:** [tests/test_benchmark_runner.py](../../tests/test_benchmark_runner.py) · **Bereiche:** Benchmarks.

**Ebene:** Budget-/Resume-/Dry-Run-Funktionen.

**Lauf:** 9 bestanden.

**Geprüftes Verhalten:** Donekeys ignorieren Fehler/Leerzeilen und behandeln fehlende Datei; Budget ohne Cap, unter/über Cap; Dry-Run prüft sechs Payloads und Kosten; injiziertes Webtool wird erkannt; Manifest hält effektive Modellmatrix, Reasoning/Alias-/Consensus-/Synth-Einstellungen fest.

**Grenzen und Doubles:** Manifestassertions sind an bestimmte Modellkonfiguration gebunden; kein Live-Pin-/Preisnachweis.

**Prüfauftrag für den Folgeaudit:** Budgetgleichheit, fehlende Preise und neue Registryfamilien bei späterem Scan abgleichen.

**Direkte Codeverweise:** [benchmark/__init__.py](../../benchmark/__init__.py), [benchmark/audit.py](../../benchmark/audit.py), [benchmark/config.py](../../benchmark/config.py), [benchmark/runner.py](../../benchmark/runner.py).

<details>
<summary>9 Testdefinitionen und ihre Quellstellen</summary>

- [ResumeTests::test_load_done_keys_skips_errors_and_blank_lines](../../tests/test_benchmark_runner.py#L29) (Zeile 29)
- [ResumeTests::test_load_done_keys_missing_file](../../tests/test_benchmark_runner.py#L46) (Zeile 46)
- [BudgetTests::test_no_cap_never_stops](../../tests/test_benchmark_runner.py#L51) (Zeile 51)
- [BudgetTests::test_stops_when_next_cell_would_exceed](../../tests/test_benchmark_runner.py#L54) (Zeile 54)
- [BudgetTests::test_continues_when_within_cap](../../tests/test_benchmark_runner.py#L57) (Zeile 57)
- [DryRunTests::test_dry_run_audits_all_model_payloads_and_projects_cost](../../tests/test_benchmark_runner.py#L62) (Zeile 62)
- [DryRunTests::test_dry_run_audit_catches_injected_web_tool](../../tests/test_benchmark_runner.py#L70) (Zeile 70)
- [DryRunTests::test_assert_no_web_tools_passes_for_clean_payload](../../tests/test_benchmark_runner.py#L84) (Zeile 84)
- [ManifestModelConfigTests::test_manifest_records_regular_model_matrix_and_effective_settings](../../tests/test_benchmark_runner.py#L89) (Zeile 89)

</details>

<a id="test-benchmark-transport-py"></a>

## test_benchmark_transport.py

**Quelle:** [tests/test_benchmark_transport.py](../../tests/test_benchmark_transport.py) · **Bereiche:** Benchmarks.

**Ebene:** Transportfunktionen mit injiziertem POST.

**Lauf:** 6 bestanden.

**Geprüftes Verhalten:** Alle im Test verwendeten Familien teilen OpenRouter-URL, Headers, Payload, Text/Citations und Usage; gemeinsames Credentialmapping; keine alten provider-spezifischen Authfunktionen; HTTP-/Transportfehler strukturiert; Antwort ohne erwartete Felder ergibt leeren Text und Nullusage.

**Grenzen und Doubles:** POST ist Fake. Der Test malformed_response akzeptiert error=None bei leerer Antwort; dies dokumentiert bestehendes Verhalten, keine positive Fehlererkennung.

**Prüfauftrag für den Folgeaudit:** Prüfen, ob fehlende Usage künftig unknown statt null und malformed response als Fehler behandelt werden soll; zuerst Produktvertrag klären.

**Direkte Codeverweise:** [app/services/llm/engines.py](../../app/services/llm/engines.py), [benchmark/__init__.py](../../benchmark/__init__.py), [benchmark/transport.py](../../benchmark/transport.py).

<details>
<summary>6 Testdefinitionen und ihre Quellstellen</summary>

- [test_all_model_families_use_one_openrouter_transport](../../tests/test_benchmark_transport.py#L53) (Zeile 53)
- [test_shared_credential_mapping_is_accepted](../../tests/test_benchmark_transport.py#L74) (Zeile 74)
- [test_no_provider_specific_adc_or_auth_parameters_exist](../../tests/test_benchmark_transport.py#L84) (Zeile 84)
- [test_http_error_is_structured](../../tests/test_benchmark_transport.py#L94) (Zeile 94)
- [test_transport_exception_is_structured](../../tests/test_benchmark_transport.py#L102) (Zeile 102)
- [test_malformed_response_is_structured](../../tests/test_benchmark_transport.py#L111) (Zeile 111)

</details>

<a id="test-bookmarks-py"></a>

## test_bookmarks.py

**Quelle:** [tests/test_bookmarks.py](../../tests/test_bookmarks.py) · **Bereiche:** Bookmarks und Verlauf, Öffentliche Freigaben.

**Ebene:** Router/Service mit Firestore-Doubles und Quelltextverträgen.

**Lauf:** 38 bestanden.

**Geprüftes Verhalten:** UID-Schreibbudget/429, Modellantworten und historische Labels, autoritativer Konsens statt Browserkopie, Follow-up/NFKC, stabiler Titel und Bookmark-ID, Chat-Konversation inkl. Fallback, Share-Revision/Reuse, kompakte Pagination und Owner-Scope, Löschen mit Chat-Cascade sowie Cursor-400/503. JS-Quelltextverträge betreffen Replay, Retry, Provenienz und Direct-Ansicht.

**Grenzen und Doubles:** FakeBookmarkRef implementiert eigenes Merge-Verhalten; Chats/Share-Snapshots oft gestubbt. Cascade-Fehler darf Bookmark-Löschung nicht verhindern; Browserverträge sind statisch.

**Prüfauftrag für den Folgeaudit:** Firestore-Merge, gleichzeitige Saves/Löschung und durchgängigen Restore mit JS/E2E abgleichen.

**Direkte Codeverweise:** [app/api/routers/bookmarks.py](../../app/api/routers/bookmarks.py), [app/core/config.py](../../app/core/config.py), [app/core/rate_limit.py](../../app/core/rate_limit.py), [app/core/security.py](../../app/core/security.py), [app/services/chat_store.py](../../app/services/chat_store.py), [app/services/share_snapshots.py](../../app/services/share_snapshots.py).

<details>
<summary>35 Testdefinitionen und ihre Quellstellen</summary>

- [test_bookmark_write_budget_is_scoped_to_the_authenticated_uid](../../tests/test_bookmarks.py#L152) (Zeile 152)
- [test_bookmark_uid_throttle_remains_a_429](../../tests/test_bookmarks.py#L165) (Zeile 165)
- [test_last_grok_model_write_is_persisted_under_the_owner_budget](../../tests/test_bookmarks.py#L180) (Zeile 180)
- [test_consensus_save_returns_complete_merged_bookmark](../../tests/test_bookmarks.py#L214) (Zeile 214)
- [test_consensus_save_ignores_large_legacy_client_snapshot](../../tests/test_bookmarks.py#L280) (Zeile 280)
- [test_direct_comparison_model_save_accepts_full_evidence_budget](../../tests/test_bookmarks.py#L344) (Zeile 344)
- [test_direct_comparison_model_name_contract_follows_provider_registry](../../tests/test_bookmarks.py#L360) (Zeile 360)
- [test_direct_comparison_saves_model_version_with_answer](../../tests/test_bookmarks.py#L381) (Zeile 381)
- [test_followup_bookmark_keeps_complete_previous_turn_for_restore](../../tests/test_bookmarks.py#L408) (Zeile 408)
- [test_followup_consensus_updates_one_stable_chat_bookmark](../../tests/test_bookmarks.py#L470) (Zeile 470)
- [test_bookmark_name_stays_the_first_question_of_the_conversation](../../tests/test_bookmarks.py#L533) (Zeile 533)
- [test_a_legacy_bookmark_without_a_title_falls_back_to_its_question](../../tests/test_bookmarks.py#L608) (Zeile 608)
- [test_a_follow_up_saves_although_the_turn_stored_a_normalized_question](../../tests/test_bookmarks.py#L613) (Zeile 613)
- [test_a_follow_up_bookmark_may_rest_on_its_own_run_snapshot](../../tests/test_bookmarks.py#L674) (Zeile 674)
- [test_the_browser_sends_the_run_snapshot_with_every_consensus_bookmark](../../tests/test_bookmarks.py#L728) (Zeile 728)
- [test_a_consensus_bookmark_without_a_completed_run_is_rejected](../../tests/test_bookmarks.py#L736) (Zeile 736)
- [test_completed_turn_is_the_authoritative_source_for_model_provenance](../../tests/test_bookmarks.py#L766) (Zeile 766)
- [test_chat_bookmark_conversation_returns_complete_owner_bound_turns](../../tests/test_bookmarks.py#L804) (Zeile 804)
- [test_agent_bookmark_returns_failed_turn_without_synthesis](../../tests/test_bookmarks.py#L860) (Zeile 860)
- [test_chat_bookmark_conversation_falls_back_without_losing_middle_turns](../../tests/test_bookmarks.py#L881) (Zeile 881)
- [test_legacy_consensus_bookmark_gets_new_share_result](../../tests/test_bookmarks.py#L937) (Zeile 937)
- [test_consensus_bookmark_reuses_live_share_result](../../tests/test_bookmarks.py#L989) (Zeile 989)
- [test_bookmark_share_result_rejects_a_different_visible_revision](../../tests/test_bookmarks.py#L1027) (Zeile 1027)
- [test_bookmark_frontend_prepares_share_and_watch_result](../../tests/test_bookmarks.py#L1070) (Zeile 1070)
- [test_consensus_frontend_uses_primary_write_and_small_retry_payload](../../tests/test_bookmarks.py#L1081) (Zeile 1081)
- [test_bookmark_frontend_restores_every_turn_and_keeps_a_context_fallback](../../tests/test_bookmarks.py#L1100) (Zeile 1100)
- [test_bookmark_restore_uses_historical_model_labels_without_mutating_picker_state](../../tests/test_bookmarks.py#L1130) (Zeile 1130)
- [test_bookmark_restores_the_view_the_run_had_not_the_current_toggle](../../tests/test_bookmarks.py#L1155) (Zeile 1155)
- [test_bookmark_list_is_compact_and_cursor_paginated](../../tests/test_bookmarks.py#L1189) (Zeile 1189)
- [test_bookmark_detail_is_owner_scoped_and_frontend_loads_on_open](../../tests/test_bookmarks.py#L1220) (Zeile 1220)
- [test_deleting_a_chat_bookmark_also_deletes_its_chat](../../tests/test_bookmarks.py#L1290) (Zeile 1290)
- [test_deleting_a_legacy_bookmark_touches_no_chat](../../tests/test_bookmarks.py#L1302) (Zeile 1302)
- [test_a_failing_chat_cascade_does_not_fail_the_bookmark_deletion](../../tests/test_bookmarks.py#L1313) (Zeile 1313)
- [test_unavailable_cursor_signing_is_reported_as_a_server_error](../../tests/test_bookmarks.py#L1327) (Zeile 1327)
- [test_a_malformed_cursor_is_still_a_client_error](../../tests/test_bookmarks.py#L1356) (Zeile 1356)

</details>

<a id="test-chat-context-py"></a>

## test_chat_context.py

**Quelle:** [tests/test_chat_context.py](../../tests/test_chat_context.py) · **Bereiche:** Bookmarks und Verlauf, Kontext, Nutzergedächtnis.

**Ebene:** Service/Repository/Router mit FakeChatDatabase und künstlichem Compressor.

**Lauf:** 37 bestanden.

**Geprüftes Verhalten:** Deterministische erste Folgefrage, Frageauflösung vor Fan-out, inkrementelle Kompression/Version-Reuse/Lease, degradierte Fehler- und Langhistorienfälle, Provenienz, Owner-/Frage-/Provider-Bindung, NFKC und Caps, Prompt-/Secret-Allowlist, eigene versus Developer-Credentials und Usage-Claim. Entfernt Judge-Metadaten/fremde Antworten/alte Quellenmarker; Offline-Fixture prüft Signal-Erhalt. Cache-Tests prüfen Trennung, TTL, Begrenzung und nicht gecachte Fehler.

**Grenzen und Doubles:** Künstliche Compressor-/Query-Antworten; Offline-Evaluation misst Textsignale im deterministischen Kontext, keine Qualität eines echten LLM. Reentrantes Lease-Szenario ersetzt reale Mehrprozess-Konkurrenz.

**Prüfauftrag für den Folgeaudit:** Emulator-Kontexttransaktionen, semantische Kompressionsqualität und konkurrierende Cache-Misses gesondert abgleichen.

**Direkte Codeverweise:** [app/api/routers/chat.py](../../app/api/routers/chat.py), [app/api/routers/chat_history.py](../../app/api/routers/chat_history.py), [app/core/config.py](../../app/core/config.py), [app/core/rate_limit.py](../../app/core/rate_limit.py), [app/services/chat_context.py](../../app/services/chat_context.py), [app/services/chat_store.py](../../app/services/chat_store.py), [app/services/usage_repository.py](../../app/services/usage_repository.py).

**Direkte Testhelfer:** [tests/test_chat_history.py](../../tests/test_chat_history.py).

<details>
<summary>37 Testdefinitionen und ihre Quellstellen</summary>

- [test_turn_two_keeps_recent_completed_turn_without_compression](../../tests/test_chat_context.py#L139) (Zeile 139)
- [test_first_follow_up_resolves_the_question_before_the_fan_out](../../tests/test_chat_context.py#L160) (Zeile 160)
- [test_a_self_contained_question_renders_no_resolved_reading](../../tests/test_chat_context.py#L196) (Zeile 196)
- [test_a_failed_resolution_never_blocks_the_run](../../tests/test_chat_context.py#L222) (Zeile 222)
- [test_a_maxed_out_context_still_ends_with_its_instructions](../../tests/test_chat_context.py#L246) (Zeile 246)
- [test_the_resolver_also_sees_the_memory_of_older_turns](../../tests/test_chat_context.py#L282) (Zeile 282)
- [test_sanitize_resolved_question_drops_noise](../../tests/test_chat_context.py#L309) (Zeile 309)
- [test_turn_three_compresses_older_history_once_and_reuses_version](../../tests/test_chat_context.py#L329) (Zeile 329)
- [test_failed_and_pending_predecessors_never_enter_context](../../tests/test_chat_context.py#L388) (Zeile 388)
- [test_compression_failure_finishes_a_degraded_deterministic_version](../../tests/test_chat_context.py#L409) (Zeile 409)
- [test_reentrant_retry_observes_build_lease_and_cannot_start_second_call](../../tests/test_chat_context.py#L434) (Zeile 434)
- [test_long_history_is_bounded_and_explicitly_degraded_without_prior_memory](../../tests/test_chat_context.py#L468) (Zeile 468)
- [test_prior_memory_provenance_survives_outside_current_raw_turn_window](../../tests/test_chat_context.py#L499) (Zeile 499)
- [test_incremental_context_keeps_prior_provenance_beyond_read_window](../../tests/test_chat_context.py#L518) (Zeile 518)
- [test_context_is_owner_scoped_and_question_bound](../../tests/test_chat_context.py#L577) (Zeile 577)
- [test_question_binding_normalizes_like_create_turn](../../tests/test_chat_context.py#L596) (Zeile 596)
- [test_completed_turn_cannot_receive_new_context_but_linked_retry_is_read_only](../../tests/test_chat_context.py#L638) (Zeile 638)
- [test_memory_compressor_validates_categories_origins_and_source_refs](../../tests/test_chat_context.py#L665) (Zeile 665)
- [test_memory_input_is_valid_json_within_budget_and_fallback_keeps_newest_turns](../../tests/test_chat_context.py#L703) (Zeile 703)
- [test_own_key_memory_credentials_never_resolve_developer_keys](../../tests/test_chat_context.py#L748) (Zeile 748)
- [test_admin_chat_memory_model_replaces_the_turn_engine_within_its_family](../../tests/test_chat_context.py#L781) (Zeile 781)
- [test_without_a_configured_chat_memory_model_the_turn_engine_stays](../../tests/test_chat_context.py#L813) (Zeile 813)
- [test_developer_memory_credentials_only_read_consumed_usage](../../tests/test_chat_context.py#L842) (Zeile 842)
- [test_context_endpoint_is_additive_idempotent_and_never_persists_request_key](../../tests/test_chat_context.py#L895) (Zeile 895)
- [test_authoritative_context_ids_are_all_required_and_legacy_context_cannot_mix](../../tests/test_chat_context.py#L938) (Zeile 938)
- [test_no_derived_context_ever_carries_judge_metadata_or_model_names](../../tests/test_chat_context.py#L1007) (Zeile 1007)
- [test_each_model_sees_only_its_own_previous_answer](../../tests/test_chat_context.py#L1043) (Zeile 1043)
- [test_the_previous_answer_never_carries_its_source_markers_forward](../../tests/test_chat_context.py#L1084) (Zeile 1084)
- [test_the_previous_answer_is_offered_as_context_not_as_a_commitment](../../tests/test_chat_context.py#L1126) (Zeile 1126)
- [test_a_previous_answer_can_never_be_claimed_under_a_foreign_provider](../../tests/test_chat_context.py#L1140) (Zeile 1140)
- [test_offline_memory_evaluation_preserves_reference_numbers_negations_and_corrections](../../tests/test_chat_context.py#L1166) (Zeile 1166)
- [test_repeated_resolution_for_one_provider_reads_once](../../tests/test_chat_context.py#L1210) (Zeile 1210)
- [test_each_provider_gets_its_own_rendered_context](../../tests/test_chat_context.py#L1233) (Zeile 1233)
- [test_cached_context_never_crosses_owners_turns_or_questions](../../tests/test_chat_context.py#L1257) (Zeile 1257)
- [test_context_errors_are_never_cached](../../tests/test_chat_context.py#L1293) (Zeile 1293)
- [test_resolved_context_cache_expires_and_stays_bounded](../../tests/test_chat_context.py#L1316) (Zeile 1316)
- [test_resolved_context_cache_key_is_owner_first_and_bounded](../../tests/test_chat_context.py#L1339) (Zeile 1339)

</details>

<a id="test-chat-history-py"></a>

## test_chat_history.py

**Quelle:** [tests/test_chat_history.py](../../tests/test_chat_history.py) · **Bereiche:** Authentifizierung, Bookmarks und Verlauf, Persistenz.

**Ebene:** Router und ChatStore mit speicherbasiertem Transaktionsmodell.

**Lauf:** 72 bestanden.

**Geprüftes Verhalten:** Auth/Owner-Scope, signierte Cursor inkl. Nanosekunden und bewegter Grenze, monotone Turns, Request-ID-Idempotenz/NFKC, Eingabe-/Tier-/Quota-Gates. Completion schreibt separate Modellantworten, saniert Metadaten und Quellen, begrenzt Bytebudgets; Retry/Conflict/Failure ohne partielle Writes. Kompakte Listen und Lesebudget, rekursive Löschung inkl. fehlender Eltern, Tombstone-Fencing, Abandoned-Sweep, UID-Limits und persistente Anhangmetadaten.

**Grenzen und Doubles:** FakeChatDatabase stellt Transaktionen/Queries selbst nach; kein Firestore-Emulator in dieser Datei. Nachgewiesene Atomizität gilt für injizierte Fake-Commit-Fehler.

**Prüfauftrag für den Folgeaudit:** SDK-/Emulator-Verträge und echte parallele Erstellung/Completion/Löschung mit Transaktionsdateien abgleichen.

**Direkte Codeverweise:** [app/api/routers/chat_history.py](../../app/api/routers/chat_history.py), [app/core/config.py](../../app/core/config.py), [app/core/rate_limit.py](../../app/core/rate_limit.py), [app/core/security.py](../../app/core/security.py), [app/services/chat_store.py](../../app/services/chat_store.py).

<details>
<summary>61 Testdefinitionen und ihre Quellstellen</summary>

- [test_all_chat_endpoints_require_verified_authentication](../../tests/test_chat_history.py#L425) (Zeile 425)
- [test_chat_creation_uses_server_id_and_storage_allowlist](../../tests/test_chat_history.py#L439) (Zeile 439)
- [test_chat_detail_is_owner_scoped_and_list_is_compact](../../tests/test_chat_history.py#L463) (Zeile 463)
- [test_chat_list_enforces_limit_and_owner_bound_cursor](../../tests/test_chat_history.py#L483) (Zeile 483)
- [test_chat_cursor_keeps_original_boundary_when_boundary_chat_moves](../../tests/test_chat_history.py#L504) (Zeile 504)
- [test_chat_cursor_preserves_nanoseconds_and_rejects_invalid_timestamp](../../tests/test_chat_history.py#L526) (Zeile 526)
- [test_chat_cursor_signing_secret_is_required_for_followup_page](../../tests/test_chat_history.py#L569) (Zeile 569)
- [test_first_and_second_turn_are_monotone_and_update_chat](../../tests/test_chat_history.py#L581) (Zeile 581)
- [test_turn_client_request_id_returns_original_for_normalized_identical_retry](../../tests/test_chat_history.py#L618) (Zeile 618)
- [test_turn_client_request_id_rejects_changed_payload](../../tests/test_chat_history.py#L640) (Zeile 640)
- [test_latest_question_is_bounded_preview_but_turn_keeps_full_question](../../tests/test_chat_history.py#L663) (Zeile 663)
- [test_turn_list_is_sorted_bounded_and_cursor_paginated](../../tests/test_chat_history.py#L686) (Zeile 686)
- [test_invalid_or_secret_bearing_turn_payloads_are_not_stored](../../tests/test_chat_history.py#L727) (Zeile 727)
- [test_premium_engine_needs_pro_at_turn_creation_like_at_consensus](../../tests/test_chat_history.py#L738) (Zeile 738)
- [test_unknown_and_foreign_chat_are_indistinguishable_for_turn_creation](../../tests/test_chat_history.py#L774) (Zeile 774)
- [test_completion_preflight_is_owner_bound_read_only_and_skips_answers](../../tests/test_chat_history.py#L791) (Zeile 791)
- [test_complete_turn_atomically_persists_six_separate_answer_documents](../../tests/test_chat_history.py#L824) (Zeile 824)
- [test_complete_turn_skips_empty_answers_and_derives_count_server_side](../../tests/test_chat_history.py#L876) (Zeile 876)
- [test_complete_turn_rejects_unknown_or_too_many_providers_before_writes](../../tests/test_chat_history.py#L898) (Zeile 898)
- [test_completion_limits_text_metadata_but_preserves_all_sources](../../tests/test_chat_history.py#L927) (Zeile 927)
- [test_completion_rejects_oversized_source_documents_without_partial_writes](../../tests/test_chat_history.py#L963) (Zeile 963)
- [test_completion_retry_is_idempotent_but_changed_payload_conflicts](../../tests/test_chat_history.py#L981) (Zeile 981)
- [test_completion_rejects_question_mismatch_failed_turn_and_invalid_result_id](../../tests/test_chat_history.py#L1012) (Zeile 1012)
- [test_fail_turn_is_allowlisted_idempotent_and_terminal](../../tests/test_chat_history.py#L1048) (Zeile 1048)
- [test_completion_transaction_failure_leaves_no_partial_state](../../tests/test_chat_history.py#L1092) (Zeile 1092)
- [test_turn_detail_is_owner_scoped_whitelisted_and_reads_six_known_docs](../../tests/test_chat_history.py#L1109) (Zeile 1109)
- [test_turn_list_stays_compact_after_completion_and_failure](../../tests/test_chat_history.py#L1155) (Zeile 1155)
- [test_turn_question_limit_matches_the_consensus_cap](../../tests/test_chat_history.py#L1192) (Zeile 1192)
- [test_turn_rejects_a_question_the_consensus_cap_would_truncate](../../tests/test_chat_history.py#L1196) (Zeile 1196)
- [test_longest_accepted_question_still_validates_after_the_consensus_cap](../../tests/test_chat_history.py#L1208) (Zeile 1208)
- [test_get_turn_reads_model_answers_with_one_query](../../tests/test_chat_history.py#L1232) (Zeile 1232)
- [test_model_answer_under_a_foreign_document_id_is_ignored](../../tests/test_chat_history.py#L1253) (Zeile 1253)
- [test_list_turn_details_checks_the_chat_once_for_the_whole_page](../../tests/test_chat_history.py#L1274) (Zeile 1274)
- [test_list_turn_details_keeps_pagination_identical_to_list_turns](../../tests/test_chat_history.py#L1302) (Zeile 1302)
- [test_list_turn_details_rejects_a_foreign_owner](../../tests/test_chat_history.py#L1319) (Zeile 1319)
- [test_delete_all_chats_removes_every_nested_level](../../tests/test_chat_history.py#L1334) (Zeile 1334)
- [test_delete_all_chats_descends_into_missing_parent_documents](../../tests/test_chat_history.py#L1357) (Zeile 1357)
- [test_delete_all_chats_leaves_other_owners_untouched](../../tests/test_chat_history.py#L1377) (Zeile 1377)
- [test_delete_all_chats_is_idempotent](../../tests/test_chat_history.py#L1392) (Zeile 1392)
- [test_delete_chat_removes_the_whole_tree](../../tests/test_chat_history.py#L1411) (Zeile 1411)
- [test_delete_chat_is_owner_scoped_and_uniformly_404](../../tests/test_chat_history.py#L1432) (Zeile 1432)
- [test_delete_chat_requires_authentication](../../tests/test_chat_history.py#L1445) (Zeile 1445)
- [test_deleting_a_chat_twice_reports_404_and_changes_nothing](../../tests/test_chat_history.py#L1455) (Zeile 1455)
- [test_deleting_chat_state_rejects_a_late_turn_before_it_can_write](../../tests/test_chat_history.py#L1466) (Zeile 1466)
- [test_deleting_chat_state_rejects_late_completion_and_failure_writes](../../tests/test_chat_history.py#L1484) (Zeile 1484)
- [test_account_deletion_tombstone_fences_late_chat_completion](../../tests/test_chat_history.py#L1509) (Zeile 1509)
- [test_account_deletion_tombstone_fences_late_chat_and_turn_creation](../../tests/test_chat_history.py#L1527) (Zeile 1527)
- [test_account_deletion_fences_normal_chat_delete_but_cleanup_can_continue](../../tests/test_chat_history.py#L1549) (Zeile 1549)
- [test_stale_pending_turn_is_retired_as_abandoned](../../tests/test_chat_history.py#L1584) (Zeile 1584)
- [test_a_recent_pending_turn_is_never_retired](../../tests/test_chat_history.py#L1603) (Zeile 1603)
- [test_sweep_never_touches_completed_or_failed_turns](../../tests/test_chat_history.py#L1620) (Zeile 1620)
- [test_chat_count_is_capped_per_owner_and_scoped_to_that_owner](../../tests/test_chat_history.py#L1644) (Zeile 1644)
- [test_chat_count_falls_back_to_a_bounded_scan_without_aggregation](../../tests/test_chat_history.py#L1666) (Zeile 1666)
- [test_turns_per_chat_are_capped_without_corrupting_the_counter](../../tests/test_chat_history.py#L1683) (Zeile 1683)
- [test_write_endpoints_are_rate_limited_per_account_not_only_per_ip](../../tests/test_chat_history.py#L1706) (Zeile 1706)
- [test_context_uid_budget_is_charged_on_post_not_turn_get](../../tests/test_chat_history.py#L1730) (Zeile 1730)
- [test_creating_a_turn_retires_an_abandoned_predecessor](../../tests/test_chat_history.py#L1776) (Zeile 1776)
- [test_a_failing_sweep_never_blocks_turn_creation](../../tests/test_chat_history.py#L1794) (Zeile 1794)
- [test_turn_keeps_the_attachment_meta_of_its_own_question](../../tests/test_chat_history.py#L1807) (Zeile 1807)
- [test_turn_attachments_never_carry_file_data_or_unknown_types](../../tests/test_chat_history.py#L1851) (Zeile 1851)
- [test_turn_attachment_meta_survives_completion](../../tests/test_chat_history.py#L1881) (Zeile 1881)

</details>

<a id="test-chat-session-ui-py"></a>

## test_chat_session_ui.py

**Quelle:** [tests/test_chat_session_ui.py](../../tests/test_chat_session_ui.py) · **Bereiche:** Bookmarks und Verlauf, Frontend, Kontext.

**Ebene:** Gemischt: Node-VM mit Fake-Fetch und Quelltextverträge.

**Lauf:** 11 bestanden.

**Geprüftes Verhalten:** Drei eingebettete Node-Skripte führen chat-session.js aus: Pending/Completed/Failed, stabile Request-IDs und Retry bei 503, Folge-Turn-Bindung, 202→200 Kontext-Aufbau, Kontextversion/Usage-Key, eigener Schlüssel bei degradiertem Kontext, 409, Abort, Reset und verständliche 403-Limitmeldungen. Weitere Quelltextprüfungen sichern Bundle-Reihenfolge, SSE-/Bookmark-Bindung, Replay-Gating, Archivierung, Antwortboxen und Payload-Allowlist ohne Secrets/Antworten.

**Grenzen und Doubles:** Node läuft mit Fake-Fetch und ohne echten Browser/HTTP. Einige Verhaltensbehauptungen beruhen ausschließlich auf Quelltext. Das Skript zu permanenten Fehlern führt 403 und 503 aus; der Docstring erwähnt zusätzlich 429.

**Prüfauftrag für den Folgeaudit:** Runtime-Integration von Archiv/Replay und serverseitiger Idempotenz prüfen; erwähnten 429-Fall ausdrücklich gegen vorhandene Tests verifizieren.

**Direkte Testhelfer:** [tests/frontend_order.py](../../tests/frontend_order.py).

<details>
<summary>11 Testdefinitionen und ihre Quellstellen</summary>

- [test_chat_session_state_fresh_followup_retry_and_reset_contract](../../tests/test_chat_session_ui.py#L11) (Zeile 11)
- [test_chat_session_script_order_consensus_payload_and_legacy_bookmarks_remain](../../tests/test_chat_session_ui.py#L222) (Zeile 222)
- [test_chat_turn_payload_contains_no_key_or_answer_fields](../../tests/test_chat_session_ui.py#L269) (Zeile 269)
- [test_session6_frontend_replay_disposition_and_ui_ordering_contracts](../../tests/test_chat_session_ui.py#L282) (Zeile 282)
- [test_chat_context_version_retry_degraded_and_own_key_contract](../../tests/test_chat_session_ui.py#L330) (Zeile 330)
- [test_replay_repaints_model_boxes_from_the_stored_turn](../../tests/test_chat_session_ui.py#L483) (Zeile 483)
- [test_pending_turn_creation_does_not_rewrite_the_logical_run](../../tests/test_chat_session_ui.py#L511) (Zeile 511)
- [test_permanent_persistence_failures_are_reported_as_such](../../tests/test_chat_session_ui.py#L523) (Zeile 523)
- [test_query_send_shows_the_real_reason_instead_of_a_dead_end_retry](../../tests/test_chat_session_ui.py#L629) (Zeile 629)
- [test_archived_turns_render_the_same_difference_cards_as_the_live_run](../../tests/test_chat_session_ui.py#L637) (Zeile 637)
- [test_archived_difference_cards_carry_no_live_run_controls](../../tests/test_chat_session_ui.py#L665) (Zeile 665)

</details>

<a id="test-citations-py"></a>

## test_citations.py

**Quelle:** [tests/test_citations.py](../../tests/test_citations.py) · **Bereiche:** Quellenprüfung.

**Ebene:** Reiner OpenRouter-Antwortparser.

**Lauf:** 7 bestanden.

**Geprüftes Verhalten:** URL-Annotationen werden dedupliziert und mehrfach als S1 im Text markiert; ungültige Annotationen lassen Text unverändert; lange Snippets auf Teaser kürzen, kurze erhalten; Zero-Width-/Streamfallback-/ungültige Offsets setzen Marker an geeignete Textgrenzen.

**Grenzen und Doubles:** Synthetische Annotationen und Textoffsets; kein echter Provider oder DOMrendering.

**Prüfauftrag für den Folgeaudit:** Weitere Unicode-/Offseteinheiten und überlappende Annotationen gegen Streaming/Browserfälle abgleichen.

**Direkte Codeverweise:** [app/services/llm/citations.py](../../app/services/llm/citations.py).

<details>
<summary>7 Testdefinitionen und ihre Quellstellen</summary>

- [OpenRouterCitationParsingTests::test_url_annotations_become_deduplicated_tagged_sources](../../tests/test_citations.py#L12) (Zeile 12)
- [OpenRouterCitationParsingTests::test_invalid_annotations_are_ignored_and_text_is_preserved](../../tests/test_citations.py#L49) (Zeile 49)
- [OpenRouterCitationParsingTests::test_page_sized_annotation_content_is_clipped_to_a_teaser](../../tests/test_citations.py#L62) (Zeile 62)
- [OpenRouterCitationParsingTests::test_short_snippets_stay_untouched](../../tests/test_citations.py#L89) (Zeile 89)
- [OpenRouterCitationParsingTests::test_zero_width_annotation_never_precedes_the_answer](../../tests/test_citations.py#L103) (Zeile 103)
- [OpenRouterCitationParsingTests::test_stream_fallback_advances_to_the_next_sentence_boundary](../../tests/test_citations.py#L119) (Zeile 119)
- [OpenRouterCitationParsingTests::test_invalid_offset_does_not_split_a_word](../../tests/test_citations.py#L138) (Zeile 138)

</details>

<a id="test-claim-ledger-py"></a>

## test_claim_ledger.py

**Quelle:** [tests/test_claim_ledger.py](../../tests/test_claim_ledger.py) · **Bereiche:** Konsens und Unterschiede, Quellenprüfung, Topics.

**Ebene:** Deterministische Unit-Tests.

**Lauf:** 21 bestanden.

**Geprüftes Verhalten:** Claim-Identität über Umformulierungen/Schlüssel, Lücken statt falscher Retirement, Contested/Holding/Retired, materielle Änderungen statt Score-/Wortlautbewegung, gefaltete Timeline, Quellenchronik und rungebundene Zitatmarker, Check-Strip inkl. Limits und fehlender Position-Map.

**Grenzen und Doubles:** Synthetische Runs/Dimensionen und vorgegebene Identitätskeys; prüft keine Qualität des Identity-/Change-Judges.

**Prüfauftrag für den Folgeaudit:** Falsche Join-/Split-Keys sowie gemischte alte Datenformate mit Topic-Runner-Tests abgleichen.

**Direkte Codeverweise:** [app/services/claim_ledger.py](../../app/services/claim_ledger.py), [app/services/topic_runner.py](../../app/services/topic_runner.py).

<details>
<summary>21 Testdefinitionen und ihre Quellstellen</summary>

- [test_one_claim_stays_one_claim_through_rewording](../../tests/test_claim_ledger.py#L52) (Zeile 52)
- [test_a_check_without_a_claim_list_is_a_gap_not_a_retirement](../../tests/test_claim_ledger.py#L85) (Zeile 85)
- [test_half_sentences_from_the_differences_judge_never_become_claims](../../tests/test_claim_ledger.py#L107) (Zeile 107)
- [test_claim_keys_decide_identity_where_wording_would_mislead](../../tests/test_claim_ledger.py#L125) (Zeile 125)
- [test_a_claim_absent_from_the_newest_check_is_reported_as_dropped](../../tests/test_claim_ledger.py#L150) (Zeile 150)
- [test_contested_claims_are_separated_from_the_ones_all_models_state](../../tests/test_claim_ledger.py#L169) (Zeile 169)
- [test_record_summary_anchors_on_material_change_not_on_score_movement](../../tests/test_claim_ledger.py#L188) (Zeile 188)
- [test_a_minor_grade_restates_the_answer_and_does_not_anchor_the_record](../../tests/test_claim_ledger.py#L210) (Zeile 210)
- [test_record_summary_without_any_material_change_points_at_the_first_check](../../tests/test_claim_ledger.py#L229) (Zeile 229)
- [test_unchanged_checks_fold_into_one_timeline_entry](../../tests/test_claim_ledger.py#L240) (Zeile 240)
- [test_sources_are_dated_and_the_ones_that_left_the_record_are_listed](../../tests/test_claim_ledger.py#L267) (Zeile 267)
- [test_a_site_cited_in_a_single_check_is_not_called_part_of_the_record](../../tests/test_claim_ledger.py#L295) (Zeile 295)
- [test_the_first_snapshot_of_a_topic_flags_no_source_as_new](../../tests/test_claim_ledger.py#L316) (Zeile 316)
- [test_known_claims_carry_the_newest_wording_of_each_tracked_claim](../../tests/test_claim_ledger.py#L326) (Zeile 326)
- [test_a_topic_without_any_position_map_has_no_ledger](../../tests/test_claim_ledger.py#L343) (Zeile 343)
- [test_a_claim_clipped_mid_citation_does_not_keep_half_a_marker](../../tests/test_claim_ledger.py#L349) (Zeile 349)
- [test_a_claim_carries_the_sources_its_own_wording_cites](../../tests/test_claim_ledger.py#L364) (Zeile 364)
- [test_a_claim_without_markers_lists_no_sources_of_its_own](../../tests/test_claim_ledger.py#L385) (Zeile 385)
- [test_the_check_strip_gives_every_check_one_cell_and_a_reason](../../tests/test_claim_ledger.py#L395) (Zeile 395)
- [test_the_check_strip_stands_alone_without_a_ledger](../../tests/test_claim_ledger.py#L419) (Zeile 419)
- [test_the_check_strip_keeps_the_newest_checks_when_a_topic_runs_long](../../tests/test_claim_ledger.py#L428) (Zeile 428)

</details>

<a id="test-client-error-alerts-py"></a>

## test_client_error_alerts.py

**Quelle:** [tests/test_client_error_alerts.py](../../tests/test_client_error_alerts.py) · **Bereiche:** Datenschutz, Fehlerdiagnostik.

**Ebene:** Router mit Notification-Double und Bundle-Quelltextvertrag.

**Lauf:** 34 bestanden.

**Geprüftes Verhalten:** 202-Annahme mit strenger Allowlist für Fehlerart/-phase, normalisierte Pfade, Assetklassen/dateinamen, sichere Scriptpositionen; verwirft freie Metadaten, Query-Secrets und ungültige Koordinaten. Cross-Origin-403 und frühe Reporter-Ladereihenfolge.

**Grenzen und Doubles:** Notification wird gesammelt statt versendet; Browser-Erfassung und tatsächliche Egress-/Rate-Limit-Wirkung hier nicht ausgeführt.

**Prüfauftrag für den Folgeaudit:** Frontend-Reporter und Telegram-Tests auf vollständige Ende-zu-Ende-Redaktion und Deduplizierung abgleichen.

**Direkte Codeverweise:** [app/api/routers/client_errors.py](../../app/api/routers/client_errors.py), [app/core/rate_limit.py](../../app/core/rate_limit.py).

**Direkte Testhelfer:** [tests/frontend_order.py](../../tests/frontend_order.py).

<details>
<summary>12 Testdefinitionen und ihre Quellstellen</summary>

- [test_consensus_failure_kind_is_allowlisted](../../tests/test_client_error_alerts.py#L27) (Zeile 27)
- [test_client_error_report_is_accepted_and_sanitized](../../tests/test_client_error_alerts.py#L38) (Zeile 38)
- [test_resource_failure_keeps_only_allowlisted_resource_class](../../tests/test_client_error_alerts.py#L66) (Zeile 66)
- [test_resource_failure_drops_unknown_resource_class](../../tests/test_client_error_alerts.py#L94) (Zeile 94)
- [test_client_error_report_replaces_unknown_phase_and_route](../../tests/test_client_error_alerts.py#L112) (Zeile 112)
- [test_client_error_report_rejects_cross_origin](../../tests/test_client_error_alerts.py#L137) (Zeile 137)
- [test_client_error_report_rejects_foreign_origin_without_fetch_metadata](../../tests/test_client_error_alerts.py#L151) (Zeile 151)
- [test_error_reporter_loads_before_app_modules](../../tests/test_client_error_alerts.py#L167) (Zeile 167)
- [test_asset_report_keeps_only_known_file_names](../../tests/test_client_error_alerts.py#L185) (Zeile 185)
- [test_runtime_report_retains_only_safe_code_location](../../tests/test_client_error_alerts.py#L196) (Zeile 196)
- [test_runtime_report_rejects_free_form_metadata](../../tests/test_client_error_alerts.py#L215) (Zeile 215)
- [test_runtime_report_rejects_invalid_coordinates](../../tests/test_client_error_alerts.py#L226) (Zeile 226)

</details>

<a id="test-consensus-answer-contract-py"></a>

## test_consensus_answer_contract.py

**Quelle:** [tests/test_consensus_answer_contract.py](../../tests/test_consensus_answer_contract.py) · **Bereiche:** Konsens und Unterschiede.

**Ebene:** /consensus-API mit ersetzter Engine/Persistenz.

**Lauf:** 5 bestanden.

**Geprüftes Verhalten:** Antwortmapping über Familienkeys, Anzeigenamen und Legacyfelder; ausgeschlossene Familie fällt weg; genau konfigurierte Höchstzahl zulässig und zu viele Familien mit 400 abgelehnt.

**Grenzen und Doubles:** query_consensus/query_differences und Pending-Persistenz sind ersetzt; belegt Eingangsnormierung und Übergabe, keine Ergebnisqualität.

**Prüfauftrag für den Folgeaudit:** Konfligierende Legacy-/neue Felder, leere/unbekannte Familien und tatsächliche Modellanzahl im vollständigen Ablauf prüfen.

**Direkte Codeverweise:** [app/api/routers/chat.py](../../app/api/routers/chat.py), [app/core/config.py](../../app/core/config.py), [app/core/rate_limit.py](../../app/core/rate_limit.py).

<details>
<summary>5 Testdefinitionen und ihre Quellstellen</summary>

- [test_answers_field_keyed_by_family](../../tests/test_consensus_answer_contract.py#L63) (Zeile 63)
- [test_answers_field_keyed_by_display_name](../../tests/test_consensus_answer_contract.py#L74) (Zeile 74)
- [test_legacy_answer_fields_still_work](../../tests/test_consensus_answer_contract.py#L85) (Zeile 85)
- [test_excluded_family_is_dropped_from_the_run](../../tests/test_consensus_answer_contract.py#L97) (Zeile 97)
- [test_a_run_never_compares_more_than_the_configured_cap](../../tests/test_consensus_answer_contract.py#L109) (Zeile 109)

</details>

<a id="test-consensus-api-py"></a>

## test_consensus_api.py

**Quelle:** [tests/test_consensus_api.py](../../tests/test_consensus_api.py) · **Bereiche:** API, Konten und Tarife, Publisher, Öffentliche Freigaben.

**Ebene:** Main-App-API und Runner mit Repository-/LLM-/Scheduler-Doubles; einzelne Quelltextverträge.

**Lauf:** 27 bestanden.

**Geprüftes Verhalten:** OpenAPI-Key/Idempotency-Vertrag, Admin-Key-Management und Publisher-Konfiguration, accepted/duplicate Runs, serverseitiger Modellplan, Tier/Scope/Admin-/Account-Gates und Key-/IP-Throttling. Runner-Claim verhindert doppelte Starts/Usage, Scheduler begrenzt Arbeit, Expiry unterscheidet Reservierung/Verbrauch; Publish/List/Read/Revoke, Watch-Capacity-Skip und Direct-Index-Gates.

**Grenzen und Doubles:** Auth/Firestore/LLM/Executor meist ersetzt; API-202-Duplikattest erwartet sogar zwei schedule-Aufrufe, eigentliche Deduplizierung separat geprüft. UI nur Quelltext.

**Prüfauftrag für den Folgeaudit:** Realen Worker-Abbruch und wiederaufgenommene Runs mit Repository/Emulator abgleichen; Routenintegration ohne gestubbte Fachservices prüfen.

**Direkte Codeverweise:** [app/api/routers/admin.py](../../app/api/routers/admin.py), [app/api/routers/api_v1.py](../../app/api/routers/api_v1.py), [app/core/config.py](../../app/core/config.py), [app/services/api_account_cleanup.py](../../app/services/api_account_cleanup.py), [app/services/api_consensus_runner.py](../../app/services/api_consensus_runner.py), [app/services/api_key_repository.py](../../app/services/api_key_repository.py), [app/services/api_run_repository.py](../../app/services/api_run_repository.py), [app/services/usage_repository.py](../../app/services/usage_repository.py), [main.py](../../main.py), [static/js/admin.js](../../static/js/admin.js), [templates/admin.html](../../templates/admin.html).

<details>
<summary>27 Testdefinitionen und ihre Quellstellen</summary>

- [test_openapi_contract_declares_api_key_and_idempotency_header](../../tests/test_consensus_api.py#L97) (Zeile 97)
- [test_admin_dashboard_exposes_safe_api_key_management_section](../../tests/test_consensus_api.py#L132) (Zeile 132)
- [test_admin_can_load_and_save_publisher_configuration](../../tests/test_consensus_api.py#L153) (Zeile 153)
- [test_admin_can_issue_list_and_revoke_api_keys](../../tests/test_consensus_api.py#L183) (Zeile 183)
- [test_admin_cannot_issue_direct_index_scope_to_non_admin_uid](../../tests/test_consensus_api.py#L243) (Zeile 243)
- [test_post_returns_accepted_run_and_duplicate_run_id](../../tests/test_consensus_api.py#L271) (Zeile 271)
- [test_admin_publisher_run_keeps_every_provider_in_the_persisted_plan](../../tests/test_consensus_api.py#L293) (Zeile 293)
- [test_publisher_mode_requires_admin](../../tests/test_consensus_api.py#L323) (Zeile 323)
- [test_server_model_plan_uses_exactly_the_configured_preset_models](../../tests/test_consensus_api.py#L341) (Zeile 341)
- [test_terminal_run_can_be_deleted_early](../../tests/test_consensus_api.py#L350) (Zeile 350)
- [test_disabled_account_cannot_use_still_active_key](../../tests/test_consensus_api.py#L372) (Zeile 372)
- [test_locally_blocked_account_fails_before_firebase_lookup](../../tests/test_consensus_api.py#L393) (Zeile 393)
- [test_request_rejects_client_model_and_limit_fields](../../tests/test_consensus_api.py#L413) (Zeile 413)
- [test_deep_think_is_uid_tier_gated](../../tests/test_consensus_api.py#L424) (Zeile 424)
- [test_post_is_rate_limited_per_api_key](../../tests/test_consensus_api.py#L435) (Zeile 435)
- [test_random_invalid_keys_are_ip_limited_before_firestore_auth](../../tests/test_consensus_api.py#L461) (Zeile 461)
- [test_runner_claim_prevents_duplicate_usage_and_provider_start](../../tests/test_consensus_api.py#L493) (Zeile 493)
- [test_publisher_pipeline_runs_the_full_plan_including_deepseek](../../tests/test_consensus_api.py#L547) (Zeile 547)
- [test_queued_run_rechecks_account_before_provider_start](../../tests/test_consensus_api.py#L600) (Zeile 600)
- [test_deep_think_reservation_uses_separate_usage_kind](../../tests/test_consensus_api.py#L650) (Zeile 650)
- [test_scheduler_deduplicates_and_bounds_pending_work](../../tests/test_consensus_api.py#L679) (Zeile 679)
- [test_expired_pre_provider_worker_releases_reserved_usage](../../tests/test_consensus_api.py#L701) (Zeile 701)
- [test_expired_post_provider_worker_keeps_consumed_usage](../../tests/test_consensus_api.py#L728) (Zeile 728)
- [test_api_key_can_publish_list_read_and_revoke_own_share](../../tests/test_consensus_api.py#L753) (Zeile 753)
- [test_admin_api_configures_weekly_watch_with_free_provider_tier](../../tests/test_consensus_api.py#L829) (Zeile 829)
- [test_publisher_watch_capacity_returns_successful_skip](../../tests/test_consensus_api.py#L897) (Zeile 897)
- [test_direct_indexing_requires_scope_admin_and_returns_indexed_state](../../tests/test_consensus_api.py#L930) (Zeile 930)

</details>

<a id="test-consensus-chat-history-py"></a>

## test_consensus_chat_history.py

**Quelle:** [tests/test_consensus_chat_history.py](../../tests/test_consensus_chat_history.py) · **Bereiche:** Bookmarks und Verlauf, Konsens und Unterschiede, Quellenprüfung.

**Ebene:** Router/SSE-Verträge mit RecordingStore und Engine-Doubles.

**Lauf:** 52 bestanden.

**Geprüftes Verhalten:** Kanonische Chat-/Turn-/Kontextbindung vor Engine, serverseitig aufgelöste Folgefrage, Completion-Provenienz/Quellen und Bookmark vor finalem Erfolg. Stream/JSON-Parität, Source-Job-Reihenfolge/disabled/skipped, Analysefehler bewahrt Konsens; persistenter Fehler bleibt pending. Completed-Replay ohne Engine/Usage/Writes, Tier-/Own-Key-Gates und eindeutige terminale Fehler inkl. redigierter Logs.

**Grenzen und Doubles:** Store zeichnet Aufrufe auf; Engine und Job-Submission sind ersetzt. Persistenz-/Netzwerk-Atomizität wird hier nicht nachgewiesen; SSE wird über TestClient konsumiert.

**Prüfauftrag für den Folgeaudit:** Disconnect während Completion/Bookmark und echte Persistenzfehler mit Store-/Browsertests abgleichen.

**Direkte Codeverweise:** [app/api/routers/bookmarks.py](../../app/api/routers/bookmarks.py), [app/api/routers/chat.py](../../app/api/routers/chat.py), [app/core/rate_limit.py](../../app/core/rate_limit.py), [app/services/chat_store.py](../../app/services/chat_store.py), [app/services/consensus_pipeline.py](../../app/services/consensus_pipeline.py), [app/services/source_check_jobs.py](../../app/services/source_check_jobs.py), [app/services/source_verification.py](../../app/services/source_verification.py).

<details>
<summary>39 Testdefinitionen und ihre Quellstellen</summary>

- [test_source_verification_replays_from_completed_turn](../../tests/test_consensus_chat_history.py#L101) (Zeile 101)
- [test_durable_source_check_does_not_delay_consensus_completion](../../tests/test_consensus_chat_history.py#L141) (Zeile 141)
- [test_disabled_source_check_skips_third_judge_and_keeps_analysis](../../tests/test_consensus_chat_history.py#L173) (Zeile 173)
- [test_failed_differences_never_start_source_job](../../tests/test_consensus_chat_history.py#L198) (Zeile 198)
- [test_no_checkable_differences_skips_sources_without_job](../../tests/test_consensus_chat_history.py#L218) (Zeile 218)
- [test_consensus_without_chat_ids_remains_legacy_compatible](../../tests/test_consensus_chat_history.py#L233) (Zeile 233)
- [test_consensus_persists_requested_bookmark_before_successful_final_event](../../tests/test_consensus_chat_history.py#L249) (Zeile 249)
- [test_consensus_requires_chat_and_turn_ids_together](../../tests/test_consensus_chat_history.py#L321) (Zeile 321)
- [test_consensus_rejects_noncanonical_chat_ids](../../tests/test_consensus_chat_history.py#L337) (Zeile 337)
- [test_consensus_context_version_requires_ids_and_canonical_value](../../tests/test_consensus_chat_history.py#L348) (Zeile 348)
- [test_consensus_requires_exact_context_version_link_before_engine](../../tests/test_consensus_chat_history.py#L366) (Zeile 366)
- [test_consensus_accepts_exact_linked_context_version](../../tests/test_consensus_chat_history.py#L393) (Zeile 393)
- [test_resolved_follow_up_reading_reaches_consensus_and_judge](../../tests/test_consensus_chat_history.py#L408) (Zeile 408)
- [test_a_client_supplied_reading_is_ignored](../../tests/test_consensus_chat_history.py#L438) (Zeile 438)
- [test_a_single_turn_run_never_carries_a_resolved_reading](../../tests/test_consensus_chat_history.py#L463) (Zeile 463)
- [test_consensus_rejects_foreign_or_unknown_turn_before_engine](../../tests/test_consensus_chat_history.py#L482) (Zeile 482)
- [test_consensus_rejects_question_mismatch_before_engine](../../tests/test_consensus_chat_history.py#L502) (Zeile 502)
- [test_non_streaming_completion_maps_answers_labels_sources_and_result](../../tests/test_consensus_chat_history.py#L522) (Zeile 522)
- [test_excluded_and_empty_providers_are_not_completed](../../tests/test_consensus_chat_history.py#L563) (Zeile 563)
- [test_missing_turn_sources_falls_back_to_deduplicated_model_sources](../../tests/test_consensus_chat_history.py#L582) (Zeile 582)
- [test_streaming_success_completes_exactly_once](../../tests/test_consensus_chat_history.py#L600) (Zeile 600)
- [test_analysis_failure_keeps_the_answer_the_user_already_received](../../tests/test_consensus_chat_history.py#L627) (Zeile 627)
- [test_unexpected_consensus_stream_error_is_redacted_from_sse_and_logs](../../tests/test_consensus_chat_history.py#L669) (Zeile 669)
- [test_terminal_consensus_error_marks_pending_turn_failed_best_effort](../../tests/test_consensus_chat_history.py#L699) (Zeile 699)
- [test_server_side_insufficient_answers_fails_pending_turn](../../tests/test_consensus_chat_history.py#L731) (Zeile 731)
- [test_insufficient_answers_fail_before_own_key_or_engine_checks](../../tests/test_consensus_chat_history.py#L752) (Zeile 752)
- [test_insufficient_answers_disposition_precedes_current_model_and_tier_checks](../../tests/test_consensus_chat_history.py#L786) (Zeile 786)
- [test_completion_storage_failure_never_replaces_successful_consensus](../../tests/test_consensus_chat_history.py#L816) (Zeile 816)
- [test_completed_turn_replays_without_engine_writes_or_usage](../../tests/test_consensus_chat_history.py#L849) (Zeile 849)
- [test_completed_replay_precedes_current_model_tier_and_credentials](../../tests/test_consensus_chat_history.py#L915) (Zeile 915)
- [test_completed_turn_without_stored_consensus_fails_closed](../../tests/test_consensus_chat_history.py#L965) (Zeile 965)
- [test_correctable_missing_own_key_keeps_turn_retryable](../../tests/test_consensus_chat_history.py#L990) (Zeile 990)
- [test_premium_engine_stays_pro_only_even_with_own_keys](../../tests/test_consensus_chat_history.py#L1012) (Zeile 1012)
- [test_premium_engine_stays_pro_only_with_developer_keys](../../tests/test_consensus_chat_history.py#L1033) (Zeile 1033)
- [test_pro_user_may_use_a_premium_engine_with_own_keys](../../tests/test_consensus_chat_history.py#L1045) (Zeile 1045)
- [test_non_premium_engine_remains_available_to_free_users](../../tests/test_consensus_chat_history.py#L1060) (Zeile 1060)
- [test_empty_question_still_disposes_the_pending_turn](../../tests/test_consensus_chat_history.py#L1068) (Zeile 1068)
- [test_empty_question_with_too_few_answers_reports_insufficient_answers](../../tests/test_consensus_chat_history.py#L1084) (Zeile 1084)
- [test_empty_question_without_chat_ids_keeps_the_legacy_error](../../tests/test_consensus_chat_history.py#L1099) (Zeile 1099)

</details>

<a id="test-consensus-citations-py"></a>

## test_consensus_citations.py

**Quelle:** [tests/test_consensus_citations.py](../../tests/test_consensus_citations.py) · **Bereiche:** Quellenprüfung.

**Ebene:** Quote-/Markerparser plus Engine mit Transport-Doubles.

**Lauf:** 44 bestanden.

**Geprüftes Verhalten:** Unicode- und formattolerante Originalzitate/Anker bleiben korrekt; S-Markerfilter stimmt für vollständigen Text, Zeichenstream und alle Zweiteilungsgrenzen der Beispiele überein; Code/Mathe/Escapes bleiben erhalten; Teilmarker werden gepuffert; Query/Stream liefern identischen bereinigten Text; Quellen bleiben im Prompt; faktische Prüfbarkeit und Originalprovenienz separat, ungewisse Klassifikation fail-closed; Nichtprüfbarkeit entfernt weder Differences noch Claims.

**Grenzen und Doubles:** Beispielmatrix testet alle Chunkgrenzen nur ihrer festgelegten Texte. Promptassertions belegen Anweisungen, kein Modellbefolgen. Der Kommentar über einen historischen Liveversuch gehört nicht zur automatisierten Ausführung.

**Prüfauftrag für den Folgeaudit:** Weitere Markdown-/Unicodekombinationen und sehr lange unvollständige Marker im späteren Scan prüfen.

**Direkte Codeverweise:** [app/services/llm/consensus_citations.py](../../app/services/llm/consensus_citations.py), [app/services/llm/consensus_engine.py](../../app/services/llm/consensus_engine.py).

<details>
<summary>15 Testdefinitionen und ihre Quellstellen</summary>

- [test_unicode_quote_offsets_preserve_original_spans](../../tests/test_consensus_citations.py#L20) (Zeile 20)
- [test_formatted_unicode_quote_offsets_preserve_original_span](../../tests/test_consensus_citations.py#L24) (Zeile 24)
- [test_unicode_differences_payload_keeps_verified_anchors_and_quotes](../../tests/test_consensus_citations.py#L29) (Zeile 29)
- [test_complete_and_every_chunk_boundary_agree](../../tests/test_consensus_citations.py#L65) (Zeile 65)
- [test_synthesis_keeps_source_information_but_prohibits_tags](../../tests/test_consensus_citations.py#L75) (Zeile 75)
- [test_differences_prompt_keeps_source_eligibility_separate_from_detection](../../tests/test_consensus_citations.py#L85) (Zeile 85)
- [test_model_quote_matching_accepts_only_formatting_omissions_and_keeps_original_span](../../tests/test_consensus_citations.py#L100) (Zeile 100)
- [test_formatted_quote_fallback_never_ignores_literal_code_or_math](../../tests/test_consensus_citations.py#L118) (Zeile 118)
- [test_real_original_position_span_survives_markdown_and_interleaved_citations](../../tests/test_consensus_citations.py#L122) (Zeile 122)
- [test_prose_streams_immediately_and_partial_markers_never_leak](../../tests/test_consensus_citations.py#L143) (Zeile 143)
- [test_query_and_stream_remove_tags_before_final_or_delta](../../tests/test_consensus_citations.py#L153) (Zeile 153)
- [test_checkability_and_original_quote_provenance_are_preserved](../../tests/test_consensus_citations.py#L184) (Zeile 184)
- [test_legacy_or_uncertain_classification_fails_closed](../../tests/test_consensus_citations.py#L195) (Zeile 195)
- [test_unmatched_anchor_cannot_be_marked_validated](../../tests/test_consensus_citations.py#L199) (Zeile 199)
- [test_source_check_eligibility_never_filters_differences_or_claims](../../tests/test_consensus_citations.py#L207) (Zeile 207)

</details>

<a id="test-consensus-engine-py"></a>

## test_consensus_engine.py

**Quelle:** [tests/test_consensus_engine.py](../../tests/test_consensus_engine.py) · **Bereiche:** Konsens und Unterschiede.

**Ebene:** Prompt-/Modellkonfiguration und Fallbacksteuerung mit Engine-Doubles.

**Lauf:** 19 bestanden.

**Geprüftes Verhalten:** Follow-up-Lesart im Prompt als untrusted Daten; redaktionelle Instruktionen, Quellenprovenienz und Memory-Schreibgrenze; Expert-Anonymisierung/Reihenfolge/Shuffle und Filter leerer/ausgeschlossener Antworten; modellabhängige Temperatur/Reasoning/Routing; zwei Primärfehler oder leere Antworten lösen Fallback aus, fehlender Key/fehlgeschlagener Fallback ergibt Fehlertext; Streamingfallback liefert final.

**Grenzen und Doubles:** Engine-Text/Stream sind ersetzt; keine reale Synthese, empirische Anonymisierungswirkung oder Prompt-Injection-Resistenz.

**Prüfauftrag für den Folgeaudit:** Teilstream vor Fallback, sämtliche Modellfamilien und Konsistenz mit gemeinsamen Budget-/Canceltests abgleichen.

**Direkte Codeverweise:** [app/core/config.py](../../app/core/config.py), [app/services/llm/consensus_engine.py](../../app/services/llm/consensus_engine.py).

<details>
<summary>19 Testdefinitionen und ihre Quellstellen</summary>

- [ConsensusFollowUpQuestionTests::test_resolved_question_is_carried_into_the_prompt](../../tests/test_consensus_engine.py#L66) (Zeile 66)
- [ConsensusFollowUpQuestionTests::test_empty_followup_keeps_the_same_clock_prompt_unchanged](../../tests/test_consensus_engine.py#L74) (Zeile 74)
- [ConsensusFollowUpQuestionTests::test_the_reading_is_framed_as_data_not_as_an_instruction](../../tests/test_consensus_engine.py#L89) (Zeile 89)
- [ConsensusPromptAnonymizationTests::test_prompt_uses_journalistic_judgment_without_cutoff_veto](../../tests/test_consensus_engine.py#L105) (Zeile 105)
- [ConsensusPromptAnonymizationTests::test_prompt_preserves_current_source_provenance_without_limiting_reasoning](../../tests/test_consensus_engine.py#L113) (Zeile 113)
- [ConsensusPromptAnonymizationTests::test_prompt_forbids_false_memory_persistence_claims](../../tests/test_consensus_engine.py#L121) (Zeile 121)
- [ConsensusPromptAnonymizationTests::test_prompt_contains_no_real_model_names](../../tests/test_consensus_engine.py#L125) (Zeile 125)
- [ConsensusPromptAnonymizationTests::test_all_answers_appear_under_contiguous_expert_labels](../../tests/test_consensus_engine.py#L130) (Zeile 130)
- [ConsensusPromptAnonymizationTests::test_excluded_and_empty_answers_are_filtered](../../tests/test_consensus_engine.py#L137) (Zeile 137)
- [ConsensusPromptAnonymizationTests::test_shuffle_false_keeps_fixed_model_order](../../tests/test_consensus_engine.py#L144) (Zeile 144)
- [ConsensusPromptAnonymizationTests::test_shuffle_reorders_expert_labels](../../tests/test_consensus_engine.py#L152) (Zeile 152)
- [ConsensusPromptAnonymizationTests::test_sources_are_looked_up_by_real_name_but_stay_anonymous](../../tests/test_consensus_engine.py#L163) (Zeile 163)
- [OpenRouterTemperatureTests::test_temperature_is_only_suppressed_for_reasoning_models](../../tests/test_consensus_engine.py#L171) (Zeile 171)
- [OpenRouterTemperatureTests::test_engine_aliases_keep_model_specific_reasoning_policies](../../tests/test_consensus_engine.py#L177) (Zeile 177)
- [QueryConsensusFallbackTests::test_fallback_provider_rescues_run_after_two_failures](../../tests/test_consensus_engine.py#L205) (Zeile 205)
- [QueryConsensusFallbackTests::test_empty_results_also_trigger_fallback](../../tests/test_consensus_engine.py#L220) (Zeile 220)
- [QueryConsensusFallbackTests::test_without_the_common_key_there_is_no_fallback](../../tests/test_consensus_engine.py#L230) (Zeile 230)
- [QueryConsensusFallbackTests::test_failed_fallback_yields_error_text](../../tests/test_consensus_engine.py#L238) (Zeile 238)
- [StreamConsensusFallbackTests::test_fallback_engine_delivers_final_answer](../../tests/test_consensus_engine.py#L248) (Zeile 248)

</details>

<a id="test-consensus-input-caps-py"></a>

## test_consensus_input_caps.py

**Quelle:** [tests/test_consensus_input_caps.py](../../tests/test_consensus_input_caps.py) · **Bereiche:** Konsens und Unterschiede.

**Ebene:** Cap-Helfer und Konfigurationsgrenzen.

**Lauf:** 8 bestanden.

**Geprüftes Verhalten:** Kurze/leere Texte und Nichtstrings unverändert; lange Texte auf Länge beschränkt, abschließendes Leerzeichen erhält erkennbare Caplänge; großzügige Defaults, Adminoverride und modellierte Deep-Search-Antwortgröße.

**Grenzen und Doubles:** Die Annahme zur maximalen legitimen Antwort ist eine Größenrechnung, kein echter Deep-Search-Run. Keine Endpointintegration in dieser Datei.

**Prüfauftrag für den Folgeaudit:** Tatsächliche Trunkierung/Evidenzkennzeichnung und Byte-/Zeichengrenzen im Datenfluss prüfen.

**Direkte Codeverweise:** [app/api/routers/chat.py](../../app/api/routers/chat.py), [app/core/config.py](../../app/core/config.py).

<details>
<summary>8 Testdefinitionen und ihre Quellstellen</summary>

- [CapEngineTextTests::test_short_text_passes_unchanged](../../tests/test_consensus_input_caps.py#L8) (Zeile 8)
- [CapEngineTextTests::test_none_and_non_strings_pass_through](../../tests/test_consensus_input_caps.py#L11) (Zeile 11)
- [CapEngineTextTests::test_oversized_text_is_truncated](../../tests/test_consensus_input_caps.py#L16) (Zeile 16)
- [CapEngineTextTests::test_truncation_keeps_detectable_cap_even_at_whitespace](../../tests/test_consensus_input_caps.py#L20) (Zeile 20)
- [CapEngineTextTests::test_empty_string_stays_falsy](../../tests/test_consensus_input_caps.py#L26) (Zeile 26)
- [ConsensusInputLimitTests::test_default_limits_exist_and_are_generous](../../tests/test_consensus_input_caps.py#L33) (Zeile 33)
- [ConsensusInputLimitTests::test_limits_are_admin_overridable](../../tests/test_consensus_input_caps.py#L37) (Zeile 37)
- [ConsensusInputLimitTests::test_answer_limit_never_clips_legit_deep_search_answers](../../tests/test_consensus_input_caps.py#L49) (Zeile 49)

</details>

<a id="test-consensus-progress-ui-py"></a>

## test_consensus_progress_ui.py

**Quelle:** [tests/test_consensus_progress_ui.py](../../tests/test_consensus_progress_ui.py) · **Bereiche:** Frontend, Konsens und Unterschiede.

**Ebene:** Quelltextverträge.

**Lauf:** 17 bestanden, 1 fehlgeschlagen.

- `test_archived_turns_use_the_same_drawer_row_as_the_live_answer`: assert 'tab.className = "consensus-tab"' in 'turnData, liveBody = null, liveVerdict = null) {\n      const history = document.getElementById("threadHistory");\n  ...dabei zu reinen Anzeigeelementen;\n    // doppelte IDs oder tote Buttons duerfen nicht in den Live-DOM gelangen.\n

**Geprüftes Verhalten:** Einheitliche Fortschrittsanzeige, Direct-Modus, Modellzeiten, Phasen/Terminal-Hooks, Erhalt des Konsenses bei Differences-Fehler, reduzierte Bewegung, Provenienz/Replay, Thread-Archiv/Drawer, sofortiger Composer-Handoff sowie sichere Draft-/Quote-Restaurierung.

**Grenzen und Doubles:** Substring-/Reihenfolgeprüfungen ohne Browserausführung. Ein Archiv-Drawer-Quelltextvertrag schlägt im Auditlauf fehl.

**Prüfauftrag für den Folgeaudit:** Fehlgeschlagenen Drawer-Vertrag auf veraltete Syntaxannahme versus Verhaltensregression prüfen; Laufzeitbelege für Zeit-/Restore-Rennen abgleichen.

**Direkte Codeverweise:** [app/api/routers/chat.py](../../app/api/routers/chat.py), [static/css/components-consensus.css](../../static/css/components-consensus.css), [static/css/components-feedback.css](../../static/css/components-feedback.css), [static/css/shell.css](../../static/css/shell.css), [static/demo.js](../../static/demo.js), [static/js/app-core.js](../../static/js/app-core.js), [static/js/app-init.js](../../static/js/app-init.js), [static/js/consensus-insights.js](../../static/js/consensus-insights.js), [static/js/consensus-lifecycle.js](../../static/js/consensus-lifecycle.js), [static/js/consensus-progress.js](../../static/js/consensus-progress.js), [static/js/consensus-run.js](../../static/js/consensus-run.js), [static/js/query-send.js](../../static/js/query-send.js), [static/js/run-view.js](../../static/js/run-view.js), [templates/index.html](../../templates/index.html).

**Direkte Testhelfer:** [tests/frontend_order.py](../../tests/frontend_order.py).

<details>
<summary>18 Testdefinitionen und ihre Quellstellen</summary>

- [test_consensus_result_precedes_model_answers_and_run_block_is_loaded](../../tests/test_consensus_progress_ui.py#L12) (Zeile 12)
- [test_run_block_shows_one_step_at_a_time](../../tests/test_consensus_progress_ui.py#L24) (Zeile 24)
- [test_the_direct_comparison_has_no_run_block_at_all](../../tests/test_consensus_progress_ui.py#L39) (Zeile 39)
- [test_the_per_model_rows_show_live_progress_and_measured_time](../../tests/test_consensus_progress_ui.py#L65) (Zeile 65)
- [test_run_covers_every_phase_and_terminal_state](../../tests/test_consensus_progress_ui.py#L79) (Zeile 79)
- [test_completed_consensus_survives_differences_or_transport_failure](../../tests/test_consensus_progress_ui.py#L105) (Zeile 105)
- [test_run_is_compact_and_unknowable_phases_stay_indeterminate](../../tests/test_consensus_progress_ui.py#L115) (Zeile 115)
- [test_run_hands_over_to_a_provenance_line](../../tests/test_consensus_progress_ui.py#L129) (Zeile 129)
- [test_result_footer_has_one_boundary_before_the_composer](../../tests/test_consensus_progress_ui.py#L141) (Zeile 141)
- [test_the_composer_carries_no_followup_affordance_at_all](../../tests/test_consensus_progress_ui.py#L150) (Zeile 150)
- [test_followup_archives_the_previous_turn_before_rendering_the_next_one](../../tests/test_consensus_progress_ui.py#L173) (Zeile 173)
- [test_the_sent_message_leaves_the_field_before_prepare_runs](../../tests/test_consensus_progress_ui.py#L215) (Zeile 215)
- [test_a_run_that_never_happens_gives_the_message_back](../../tests/test_consensus_progress_ui.py#L269) (Zeile 269)
- [test_archived_questions_clamp_like_the_active_one](../../tests/test_consensus_progress_ui.py#L296) (Zeile 296)
- [test_archived_turns_use_the_same_drawer_row_as_the_live_answer](../../tests/test_consensus_progress_ui.py#L322) (Zeile 322)
- [test_composer_row_is_reduced_to_attach_run_switch_and_send](../../tests/test_consensus_progress_ui.py#L348) (Zeile 348)
- [test_sidebar_header_groups_brand_and_toggle_before_new_comparison](../../tests/test_consensus_progress_ui.py#L368) (Zeile 368)
- [test_consensus_loader_matches_the_run_visual_language](../../tests/test_consensus_progress_ui.py#L383) (Zeile 383)

</details>

<a id="test-contradiction-jobs-py"></a>

## test_contradiction_jobs.py

**Quelle:** [tests/test_contradiction_jobs.py](../../tests/test_contradiction_jobs.py) · **Bereiche:** Jobs, Konsens und Unterschiede, Quellenprüfung.

**Ebene:** Job-/Repository-Integration mit FakeDb, Fetch- und Judge-Doubles.

**Lauf:** 19 bestanden.

**Geprüftes Verhalten:** V4-Zulassung/Idempotenz bindet Run/Antwort/Positionen; beide Positionen samt Originalzitaten persistiert, Budget-Omissions und falsche Ergebnisbindung. Own-Key-Neustart ohne Credential-Persistenz, Legacy/V4-Cachetrennung, eingefrorener Fallback, Diagnostik, Cache erst nach Result-Commit und kein wiederholter bezahlter Aufruf nach ungewissem Write-/Workerfehler.

**Grenzen und Doubles:** Fetch/Judge und Firestore ersetzt; Restart wird durch Zustandsmanipulation nachgebildet. Kein echter Prozesscrash oder verteilter Lease-Konflikt.

**Prüfauftrag für den Folgeaudit:** Reale Worker-Unterbrechung, Credential-Lebensdauer und konkurrierende Jobs mit Emulator/Operations abgleichen.

**Direkte Codeverweise:** [app/services/contradiction_verification.py](../../app/services/contradiction_verification.py), [app/services/llm/provider_runtime.py](../../app/services/llm/provider_runtime.py), [app/services/share_snapshots.py](../../app/services/share_snapshots.py), [app/services/source_check_jobs.py](../../app/services/source_check_jobs.py), [app/services/source_check_repository.py](../../app/services/source_check_repository.py), [app/services/source_documents.py](../../app/services/source_documents.py), [app/services/source_verification.py](../../app/services/source_verification.py).

**Direkte Testhelfer:** [tests/test_contradiction_verification.py](../../tests/test_contradiction_verification.py), [tests/test_source_check_repository.py](../../tests/test_source_check_repository.py).

<details>
<summary>15 Testdefinitionen und ihre Quellstellen</summary>

- [test_admission_binding_and_positions_idempotency](../../tests/test_contradiction_jobs.py#L39) (Zeile 39)
- [test_worker_persists_both_positions_original_quotes_and_documents](../../tests/test_contradiction_jobs.py#L54) (Zeile 54)
- [test_repository_rejects_result_from_changed_binding](../../tests/test_contradiction_jobs.py#L73) (Zeile 73)
- [test_budget_omissions_survive_job_pages_and_completion](../../tests/test_contradiction_jobs.py#L88) (Zeile 88)
- [test_v4_own_key_restart_resumes_same_job_and_interruption_stays_v4](../../tests/test_contradiction_jobs.py#L104) (Zeile 104)
- [test_no_eligible_contradictions_and_persistence_errors_are_distinct](../../tests/test_contradiction_jobs.py#L117) (Zeile 117)
- [test_cached_judge_contract_separates_legacy_from_disputes](../../tests/test_contradiction_jobs.py#L127) (Zeile 127)
- [test_v4_cache_rpc_is_skipped_when_it_cannot_fit_remaining_budget](../../tests/test_contradiction_jobs.py#L137) (Zeile 137)
- [test_share_snapshot_preserves_factual_classification_and_position_provenance](../../tests/test_contradiction_jobs.py#L145) (Zeile 145)
- [test_validation_diagnostics_survive_job_storage_and_polling](../../tests/test_contradiction_jobs.py#L155) (Zeile 155)
- [test_queued_fallback_selection_is_frozen_and_legacy_jobs_remain_disabled](../../tests/test_contradiction_jobs.py#L173) (Zeile 173)
- [test_cache_transactions_run_only_after_the_result_is_committed](../../tests/test_contradiction_jobs.py#L193) (Zeile 193)
- [test_failed_result_commit_never_repeats_paid_v4_work](../../tests/test_contradiction_jobs.py#L208) (Zeile 208)
- [test_worker_failure_phase_survives_retry_without_repeating_uncertain_work](../../tests/test_contradiction_jobs.py#L234) (Zeile 234)
- [test_failure_from_another_package_does_not_mislabel_a_lost_lease](../../tests/test_contradiction_jobs.py#L260) (Zeile 260)

</details>

<a id="test-contradiction-verification-py"></a>

## test_contradiction_verification.py

**Quelle:** [tests/test_contradiction_verification.py](../../tests/test_contradiction_verification.py) · **Bereiche:** Konsens und Unterschiede, Quellenprüfung.

**Ebene:** Deterministische Planungs-/Validierungs- und Ausführungstests mit injizierten Fetch/Judge-Funktionen.

**Lauf:** 64 bestanden.

**Geprüftes Verhalten:** V4-Modus, Eligibility samt expliziter Exclusions, Version-/Run-/Positionsbindung, beide belegte Positionen, Quellenzuordnung und deduplizierter Fetch. Verwirft erfundene/unvollständige Evidenz, künstliche Textjoins, unzulässige Daten und falsche Provenienz; differenziert insufficient/unavailable/omitted. Globale URL-/Token-/Zeitbudgets, Legacy-V3 und begrenzte textfreie Validierungsdiagnostik.

**Grenzen und Doubles:** Vorgegebene Dokumente und Judge-JSON; beweist formale Belegtreue, keine tatsächliche Wahrheit oder semantische Zuverlässigkeit des LLM. Zeitbudget teils künstliche Uhr.

**Prüfauftrag für den Folgeaudit:** Adversariale reale Dokument-Fixtures, Datums-/Scope-Semantik und Retrieval-Ausfälle mit source_documents-Tests abgleichen.

**Direkte Codeverweise:** [app/services/contradiction_verification.py](../../app/services/contradiction_verification.py), [app/services/source_verification.py](../../app/services/source_verification.py).

<details>
<summary>29 Testdefinitionen und ihre Quellstellen</summary>

- [test_separate_mode_has_no_consensus_citations_and_preserves_inputs](../../tests/test_contradiction_verification.py#L53) (Zeile 53)
- [test_ineligible_differences_never_schedule](../../tests/test_contradiction_verification.py#L70) (Zeile 70)
- [test_unverified_model_position_never_drops_one_side_into_judge](../../tests/test_contradiction_verification.py#L79) (Zeile 79)
- [test_missing_original_quotes_are_explicit_exclusions_not_absent_contradictions](../../tests/test_contradiction_verification.py#L86) (Zeile 86)
- [test_mixed_checks_keep_excluded_dispute_and_all_exclusion_causes](../../tests/test_contradiction_verification.py#L104) (Zeile 104)
- [test_identity_binds_run_answer_positions_and_question](../../tests/test_contradiction_verification.py#L120) (Zeile 120)
- [test_direct_references_select_both_sides_and_ignore_unrelated_catalog](../../tests/test_contradiction_verification.py#L132) (Zeile 132)
- [test_reference_from_next_sentence_is_not_borrowed](../../tests/test_contradiction_verification.py#L141) (Zeile 141)
- [test_shared_url_fetched_once_preserves_both_passages](../../tests/test_contradiction_verification.py#L147) (Zeile 147)
- [test_original_evidence_validation_rejects_invented_or_incomplete_verdicts](../../tests/test_contradiction_verification.py#L177) (Zeile 177)
- [test_missing_evidence_can_only_be_insufficient_not_refutation](../../tests/test_contradiction_verification.py#L197) (Zeile 197)
- [test_fetch_errors_never_call_judge_or_refute](../../tests/test_contradiction_verification.py#L207) (Zeile 207)
- [test_global_contradiction_budget_records_omissions](../../tests/test_contradiction_verification.py#L217) (Zeile 217)
- [test_url_budget_never_picks_only_one_side](../../tests/test_contradiction_verification.py#L227) (Zeile 227)
- [test_input_token_budget_is_global_and_explicit](../../tests/test_contradiction_verification.py#L233) (Zeile 233)
- [test_runtime_budget_omits_unfinished_check](../../tests/test_contradiction_verification.py#L240) (Zeile 240)
- [test_merge_rejects_run_and_position_tampering](../../tests/test_contradiction_verification.py#L251) (Zeile 251)
- [test_legacy_citation_mode_keeps_schema_three](../../tests/test_contradiction_verification.py#L264) (Zeile 264)
- [test_large_v4_reference_preserves_mode_run_and_scope](../../tests/test_contradiction_verification.py#L270) (Zeile 270)
- [test_direct_background_start_uses_disputes_without_citations](../../tests/test_contradiction_verification.py#L281) (Zeile 281)
- [test_failed_background_start_keeps_v4_mode](../../tests/test_contradiction_verification.py#L290) (Zeile 290)
- [test_one_side_retrieval_failure_does_not_promote_surviving_side](../../tests/test_contradiction_verification.py#L298) (Zeile 298)
- [test_invented_applicability_date_is_rejected](../../tests/test_contradiction_verification.py#L314) (Zeile 314)
- [test_passage_selection_never_validates_an_artificial_join](../../tests/test_contradiction_verification.py#L323) (Zeile 323)
- [test_only_sources_for_metadata_within_budget_are_fetched](../../tests/test_contradiction_verification.py#L336) (Zeile 336)
- [test_every_rejection_has_precise_bounded_text_free_diagnostics](../../tests/test_contradiction_verification.py#L378) (Zeile 378)
- [test_multiple_bad_quotes_are_all_rejected_and_diagnostics_are_bounded](../../tests/test_contradiction_verification.py#L453) (Zeile 453)
- [test_cosmetic_quotes_still_validate_without_diagnostics](../../tests/test_contradiction_verification.py#L463) (Zeile 463)
- [test_unknown_extra_finding_does_not_spoil_complete_valid_results](../../tests/test_contradiction_verification.py#L474) (Zeile 474)

</details>

<a id="test-coverage-judge-py"></a>

## test_coverage_judge.py

**Quelle:** [tests/test_coverage_judge.py](../../tests/test_coverage_judge.py) · **Bereiche:** Konsens und Unterschiede.

**Ebene:** Schema-/Parser-/Scoring-Unit-Tests und Engine-Integration mit Mock-Antworten.

**Lauf:** 27 bestanden.

**Geprüftes Verhalten:** Striktes Satz-/Modell-Schema, konservative fehlende/unklare Stances, gebundene IDs und genau ein gezielter Repair-Aufruf, sichtbare thin-Lücken, exakte Konsensanker und Dissent-Zitate. Thin-Claims senken Abdeckung/Score, günstige unabhängige Judge-Familie, Cooldown-Fallback sowie getrennte Judge-Metadaten und angepasster Credibility-Text.

**Grenzen und Doubles:** Hier meint Coverage die inhaltliche Satzabdeckung der App, keine Test-Code-Coverage. LLM-Antworten sind konstruiert; Klassifikationsqualität wird nicht gemessen.

**Prüfauftrag für den Folgeaudit:** Goldstandard für Satz-/Stance-Zuordnung, Tokenabschneiden und Mehrsprachigkeit gesondert prüfen.

**Direkte Codeverweise:** [app/core/config.py](../../app/core/config.py), [app/services/agent_provider_limits.py](../../app/services/agent_provider_limits.py), [app/services/llm/consensus_engine.py](../../app/services/llm/consensus_engine.py), [app/services/llm/consensus_scoring.py](../../app/services/llm/consensus_scoring.py), [app/services/llm/coverage_judge.py](../../app/services/llm/coverage_judge.py).

<details>
<summary>27 Testdefinitionen und ihre Quellstellen</summary>

- [CoverageSchemaTests::test_schema_is_strict_mode_compatible](../../tests/test_coverage_judge.py#L64) (Zeile 64)
- [CoverageSchemaTests::test_every_model_is_a_required_property](../../tests/test_coverage_judge.py#L82) (Zeile 82)
- [CoverageSchemaTests::test_sentence_ids_are_an_enum](../../tests/test_coverage_judge.py#L92) (Zeile 92)
- [CoveragePromptTests::test_prompt_carries_the_binding_id_list](../../tests/test_coverage_judge.py#L99) (Zeile 99)
- [CoveragePromptTests::test_repair_prompt_asks_only_for_the_missing_ids](../../tests/test_coverage_judge.py#L113) (Zeile 113)
- [CoverageParsingTests::test_unmentioned_model_counts_as_not_addressed](../../tests/test_coverage_judge.py#L131) (Zeile 131)
- [CoverageParsingTests::test_unknown_stance_and_classification_are_coerced](../../tests/test_coverage_judge.py#L140) (Zeile 140)
- [CoverageParsingTests::test_ids_outside_the_binding_list_are_dropped](../../tests/test_coverage_judge.py#L152) (Zeile 152)
- [CoverageParsingTests::test_model_list_form_is_accepted](../../tests/test_coverage_judge.py#L159) (Zeile 159)
- [CoverageParsingTests::test_structurally_broken_output_is_none](../../tests/test_coverage_judge.py#L169) (Zeile 169)
- [CoverageParsingTests::test_missing_ids_are_reported](../../tests/test_coverage_judge.py#L173) (Zeile 173)
- [CoverageClaimTests::test_stances_become_agree_and_dissent](../../tests/test_coverage_judge.py#L185) (Zeile 185)
- [CoverageClaimTests::test_a_non_claim_sentence_is_skipped_on_purpose](../../tests/test_coverage_judge.py#L203) (Zeile 203)
- [CoverageClaimTests::test_an_id_the_judge_never_answered_stays_visible_as_thin](../../tests/test_coverage_judge.py#L214) (Zeile 214)
- [CoverageClaimTests::test_a_single_voice_is_thin_not_supported](../../tests/test_coverage_judge.py#L222) (Zeile 222)
- [CoverageClaimTests::test_anchor_is_an_exact_excerpt_of_the_consensus](../../tests/test_coverage_judge.py#L234) (Zeile 234)
- [CoverageScoringTests::test_thin_claims_do_not_lift_the_agreement_score](../../tests/test_coverage_judge.py#L241) (Zeile 241)
- [CoverageJudgePolicyTests::test_coverage_judge_stays_on_the_cheap_standard_tier](../../tests/test_coverage_judge.py#L263) (Zeile 263)
- [CoverageJudgePolicyTests::test_coverage_judge_avoids_the_consensus_family](../../tests/test_coverage_judge.py#L275) (Zeile 275)
- [CoverageJudgePolicyTests::test_invalid_engine_has_no_attempts](../../tests/test_coverage_judge.py#L279) (Zeile 279)
- [CoverageRunTests::test_missing_ids_trigger_exactly_one_targeted_repair_call](../../tests/test_coverage_judge.py#L288) (Zeile 288)
- [CoverageRunTests::test_an_unfixable_gap_is_reported_instead_of_hidden](../../tests/test_coverage_judge.py#L320) (Zeile 320)
- [CoverageRunTests::test_a_failing_coverage_judge_never_breaks_the_run](../../tests/test_coverage_judge.py#L335) (Zeile 335)
- [CoverageIntegrationTests::test_busy_openai_falls_back_for_both_judges](../../tests/test_coverage_judge.py#L398) (Zeile 398)
- [CoverageIntegrationTests::test_claims_come_from_the_coverage_judge](../../tests/test_coverage_judge.py#L407) (Zeile 407)
- [CoverageIntegrationTests::test_both_judges_are_reported_separately](../../tests/test_coverage_judge.py#L421) (Zeile 421)
- [CoverageIntegrationTests::test_the_credibility_sentence_follows_the_recomputed_score](../../tests/test_coverage_judge.py#L428) (Zeile 428)

</details>

<a id="test-deepseek-web-search-py"></a>

## test_deepseek_web_search.py

**Quelle:** [tests/test_deepseek_web_search.py](../../tests/test_deepseek_web_search.py) · **Bereiche:** Modelle und Provider, Quellenprüfung.

**Ebene:** Payload-/Parser-Tests mit requests.post-Double.

**Lauf:** 3 bestanden.

**Geprüftes Verhalten:** DeepSeek über OpenRouter-Websuche ohne Provider-Pinning, ZDR-Payload, logisches Providerlabel bei URL-Zitaten und Parsing einer erfolgreichen Query-Antwort.

**Grenzen und Doubles:** Kein tatsächlicher OpenRouter-/DeepSeek-Aufruf; nur eine synthetische Erfolgsantwort.

**Prüfauftrag für den Folgeaudit:** Fehler-/Timeout-/leere Citation-Fälle in gemeinsamen Provider-Dateien abgleichen.

**Direkte Codeverweise:** [app/core/config.py](../../app/core/config.py), [app/services/llm/citations.py](../../app/services/llm/citations.py), [app/services/llm/engines.py](../../app/services/llm/engines.py).

<details>
<summary>3 Testdefinitionen und ihre Quellstellen</summary>

- [test_deepseek_payload_uses_openrouter_search_without_provider_pinning](../../tests/test_deepseek_web_search.py#L9) (Zeile 9)
- [test_deepseek_url_citations_keep_the_logical_provider_label](../../tests/test_deepseek_web_search.py#L29) (Zeile 29)
- [test_successful_query_model_parses_openrouter_response](../../tests/test_deepseek_web_search.py#L53) (Zeile 53)

</details>

<a id="test-demo-login-prompt-py"></a>

## test_demo_login_prompt.py

**Quelle:** [tests/test_demo_login_prompt.py](../../tests/test_demo_login_prompt.py) · **Bereiche:** Demo, Frontend.

**Ebene:** Quelltextverträge.

**Lauf:** 5 bestanden.

**Geprüftes Verhalten:** Login-Prompt erst nach Demo ohne Auth, Login-Öffnung und Entfernung nach Auth, Reihenfolge Tippen→Leeren→Laden, Demo-Score 45 und vorgegebene Coverage-Ankeranzahl.

**Grenzen und Doubles:** Kein ausgeführter Demo-/Login-Ablauf; konstante Ankerzahlen beweisen keine inhaltlich richtige Claim-Zuordnung.

**Prüfauftrag für den Folgeaudit:** Browserfälle für Auth-Wechsel während der Demo und tatsächliche Marker-Zuordnung abgleichen.

<details>
<summary>5 Testdefinitionen und ihre Quellstellen</summary>

- [DemoLoginPromptContractTests::test_prompt_is_hidden_until_demo_finishes](../../tests/test_demo_login_prompt.py#L9) (Zeile 9)
- [DemoLoginPromptContractTests::test_prompt_opens_login_and_is_removed_after_auth](../../tests/test_demo_login_prompt.py#L23) (Zeile 23)
- [DemoLoginPromptContractTests::test_question_is_cleared_before_model_loading_starts](../../tests/test_demo_login_prompt.py#L32) (Zeile 32)
- [DemoLoginPromptContractTests::test_demo_result_has_an_agreement_score](../../tests/test_demo_login_prompt.py#L46) (Zeile 46)
- [DemoLoginPromptContractTests::test_every_checkable_demo_passage_has_a_coverage_claim](../../tests/test_demo_login_prompt.py#L52) (Zeile 52)

</details>

<a id="test-dev-cli-py"></a>

## test_dev_cli.py

**Quelle:** [tests/test_dev_cli.py](../../tests/test_dev_cli.py) · **Bereiche:** Testinfrastruktur.

**Ebene:** Windows-Prozessintegration mit Fake-CLI-Werkzeugen.

**Lauf:** 12 übersprungen.

**Geprüftes Verhalten:** Führt dev.ps1 im Pfad mit Leerzeichen aus; prüft Test-/Build-Reihenfolge, Exitcodes/Abbruch, Suite-Pfadvalidierung, Dependency-Hinweise, Isolation/Wiederherstellung von Umgebungsvariablen und Firebase-Lifecycle samt Loopback-Gate.

**Grenzen und Doubles:** Nur unter Windows mit PowerShell; im Linux-Audit alle 12 Fälle übersprungen. npm/pytest/Firebase/Java sind Wegwerf-Doubles, kein echter Emulatorstart.

**Prüfauftrag für den Folgeaudit:** Auf Windows beide verfügbaren PowerShell-Versionen ausführen und echten Browser-Einstieg separat prüfen.

**Direkte Codeverweise:** [app/core/e2e_profile.py](../../app/core/e2e_profile.py), [app/services/agent_tokens.py](../../app/services/agent_tokens.py).

<details>
<summary>8 Testdefinitionen und ihre Quellstellen</summary>

- [test_frontend_runs_tests_then_build_check_from_repository_root](../../tests/test_dev_cli.py#L153) (Zeile 153)
- [test_frontend_preserves_failure_and_stops](../../tests/test_dev_cli.py#L164) (Zeile 164)
- [test_backend_isolates_inherited_e2e_flags_and_restores_caller](../../tests/test_dev_cli.py#L173) (Zeile 173)
- [test_browser_delegates_lifecycle_and_failure_to_firebase](../../tests/test_dev_cli.py#L185) (Zeile 185)
- [test_browser_rejects_nonlocal_emulator_before_start](../../tests/test_dev_cli.py#L206) (Zeile 206)
- [test_browser_failure_restores_initially_absent_environment_entries](../../tests/test_dev_cli.py#L216) (Zeile 216)
- [test_rejects_tests_outside_selected_suite](../../tests/test_dev_cli.py#L224) (Zeile 224)
- [test_missing_dependencies_have_actionable_error](../../tests/test_dev_cli.py#L232) (Zeile 232)

</details>

<a id="test-differences-schema-py"></a>

## test_differences_schema.py

**Quelle:** [tests/test_differences_schema.py](../../tests/test_differences_schema.py) · **Bereiche:** Konsens und Unterschiede.

**Ebene:** Parser-/Scoring-/Prompt-Unit-Tests und Mock-Engine-Integration.

**Lauf:** 75 bestanden.

**Geprüftes Verhalten:** JSON/Fence/Truncation-Reparatur und konservative Shape-Ablehnung, anonymisierte Modelllabels, Dissent-Deduplizierung, Quote-/Anchor-Abgleich und Legacy-Text. Judge-Auswahl/Retry/Fallback/Metadaten/Schema, Score-Caps nach Modellanzahl und Contradictions. Satznummerierung berücksichtigt Abkürzungen/Zahlen, Quellen, Markdown/Listen/Tabellen/Code/Math, 80-Satz-Cap und gleiche sichtbare Vorkommen mit getrennten IDs.

**Grenzen und Doubles:** Feste Beispiele und gemockte LLM-Antworten; kein Qualitätsbenchmark. Nicht auffindbare Legacy-Claim-Anker bleiben bewusst für Fallback sichtbar, während falsche Difference-Anker geleert werden.

**Prüfauftrag für den Folgeaudit:** Property-/Fuzz-Fälle für Parser und mehrsprachige Segmentierung sowie semantische Quote-Zuordnung abgleichen.

**Direkte Codeverweise:** [app/core/config.py](../../app/core/config.py), [app/services/llm/consensus_engine.py](../../app/services/llm/consensus_engine.py), [app/services/llm/engines.py](../../app/services/llm/engines.py).

<details>
<summary>75 Testdefinitionen und ihre Quellstellen</summary>

- [ParseDifferencesPayloadTests::test_valid_json_is_parsed_and_translated](../../tests/test_differences_schema.py#L61) (Zeile 61)
- [ParseDifferencesPayloadTests::test_json_inside_markdown_fences](../../tests/test_differences_schema.py#L89) (Zeile 89)
- [ParseDifferencesPayloadTests::test_hallucinated_labels_are_dropped](../../tests/test_differences_schema.py#L95) (Zeile 95)
- [ParseDifferencesPayloadTests::test_unparsable_output_falls_back_to_raw_text](../../tests/test_differences_schema.py#L113) (Zeile 113)
- [ParseDifferencesPayloadTests::test_empty_string_returns_none](../../tests/test_differences_schema.py#L121) (Zeile 121)
- [ParseDifferencesPayloadTests::test_unknown_type_defaults_to_emphasis](../../tests/test_differences_schema.py#L126) (Zeile 126)
- [ParseDifferencesPayloadTests::test_dissent_wins_over_agree_for_same_model](../../tests/test_differences_schema.py#L132) (Zeile 132)
- [JsonRepairAndShapeTests::test_truncated_json_is_repaired](../../tests/test_differences_schema.py#L142) (Zeile 142)
- [JsonRepairAndShapeTests::test_incomplete_object_shape_is_rejected](../../tests/test_differences_schema.py#L156) (Zeile 156)
- [JsonRepairAndShapeTests::test_truncation_before_any_difference_is_not_reported_as_agreement](../../tests/test_differences_schema.py#L163) (Zeile 163)
- [JsonRepairAndShapeTests::test_truncation_after_a_difference_keeps_what_was_written](../../tests/test_differences_schema.py#L174) (Zeile 174)
- [JsonRepairAndShapeTests::test_json_garbage_never_leaks_raw_text](../../tests/test_differences_schema.py#L189) (Zeile 189)
- [QuoteVerificationTests::test_found_anchor_and_quotes_use_original_text](../../tests/test_differences_schema.py#L196) (Zeile 196)
- [QuoteVerificationTests::test_fuzzy_anchor_match](../../tests/test_differences_schema.py#L217) (Zeile 217)
- [QuoteVerificationTests::test_difference_consensus_anchor_is_verified_against_the_consensus](../../tests/test_differences_schema.py#L227) (Zeile 227)
- [QuoteVerificationTests::test_unfindable_difference_anchor_is_cleared](../../tests/test_differences_schema.py#L243) (Zeile 243)
- [QuoteVerificationTests::test_missing_difference_anchor_defaults_to_empty](../../tests/test_differences_schema.py#L255) (Zeile 255)
- [QuoteVerificationTests::test_unfindable_anchor_is_kept_for_fallback_box](../../tests/test_differences_schema.py#L263) (Zeile 263)
- [JudgePolicyTests::test_judge_family_differs_from_consensus_family](../../tests/test_differences_schema.py#L282) (Zeile 282)
- [JudgePolicyTests::test_pro_engine_gets_pro_judge_of_other_family](../../tests/test_differences_schema.py#L294) (Zeile 294)
- [JudgePolicyTests::test_missing_common_key_fails_open_to_own_standard_judge](../../tests/test_differences_schema.py#L305) (Zeile 305)
- [JudgePolicyTests::test_invalid_engine_returns_none](../../tests/test_differences_schema.py#L313) (Zeile 313)
- [JudgePolicyTests::test_attempts_are_primary_retry_fallback](../../tests/test_differences_schema.py#L317) (Zeile 317)
- [JudgePolicyTests::test_pro_attempts_fail_open_to_standard_judge](../../tests/test_differences_schema.py#L327) (Zeile 327)
- [JudgePolicyTests::test_attempts_without_any_cross_family_key](../../tests/test_differences_schema.py#L338) (Zeile 338)
- [JudgePolicyTests::test_differences_judge_uses_openrouter_json_schema](../../tests/test_differences_schema.py#L346) (Zeile 346)
- [JudgePolicyTests::test_differences_schema_is_strict_mode_compatible](../../tests/test_differences_schema.py#L367) (Zeile 367)
- [JudgePolicyTests::test_streaming_differences_judge_uses_same_json_schema](../../tests/test_differences_schema.py#L384) (Zeile 384)
- [JudgePolicyTests::test_one_openrouter_key_makes_every_judge_family_available](../../tests/test_differences_schema.py#L415) (Zeile 415)
- [JudgePolicyTests::test_mistral_judge_uses_supported_none_effort](../../tests/test_differences_schema.py#L419) (Zeile 419)
- [JudgePolicyTests::test_only_retryable_provider_errors_repeat_same_call](../../tests/test_differences_schema.py#L429) (Zeile 429)
- [JudgeMetadataTests::test_query_differences_reports_actual_judge](../../tests/test_differences_schema.py#L478) (Zeile 478)
- [JudgeMetadataTests::test_fallback_judge_is_reported](../../tests/test_differences_schema.py#L494) (Zeile 494)
- [JudgeMetadataTests::test_non_retryable_primary_error_skips_duplicate_call](../../tests/test_differences_schema.py#L508) (Zeile 508)
- [JudgeMetadataTests::test_stream_differences_reports_judge](../../tests/test_differences_schema.py#L527) (Zeile 527)
- [LegacyTextSynthesisTests::test_no_differences_is_very_credible](../../tests/test_differences_schema.py#L561) (Zeile 561)
- [LegacyTextSynthesisTests::test_nothing_measured_is_not_very_credible](../../tests/test_differences_schema.py#L571) (Zeile 571)
- [LegacyTextSynthesisTests::test_only_emphasis_is_largely_credible](../../tests/test_differences_schema.py#L581) (Zeile 581)
- [LegacyTextSynthesisTests::test_multiple_contradictions_are_hardly_credible](../../tests/test_differences_schema.py#L591) (Zeile 591)
- [AgreementScoreTests::test_clean_run_with_four_models_is_perfect](../../tests/test_differences_schema.py#L604) (Zeile 604)
- [AgreementScoreTests::test_two_models_cannot_reach_very](../../tests/test_differences_schema.py#L613) (Zeile 613)
- [AgreementScoreTests::test_minor_contradiction_hurts_less_than_major](../../tests/test_differences_schema.py#L622) (Zeile 622)
- [AgreementScoreTests::test_severity_minor_is_parsed_from_payload](../../tests/test_differences_schema.py#L644) (Zeile 644)
- [AgreementScoreTests::test_emphasis_has_no_severity](../../tests/test_differences_schema.py#L655) (Zeile 655)
- [DifferencesPromptTests::test_prompt_requests_json_and_anonymizes](../../tests/test_differences_schema.py#L664) (Zeile 664)
- [DifferencesPromptTests::test_follow_up_reading_reaches_the_judge_without_touching_single_runs](../../tests/test_differences_schema.py#L690) (Zeile 690)
- [DifferencesPromptTests::test_differences_judge_no_longer_asks_for_the_claim_list](../../tests/test_differences_schema.py#L714) (Zeile 714)
- [DifferencesPromptTests::test_long_consensus_is_numbered_sentence_by_sentence](../../tests/test_differences_schema.py#L734) (Zeile 734)
- [ConsensusSentenceSplitTests::test_plain_sentences_are_split](../../tests/test_differences_schema.py#L774) (Zeile 774)
- [ConsensusSentenceSplitTests::test_year_at_the_end_is_a_sentence_end](../../tests/test_differences_schema.py#L783) (Zeile 783)
- [ConsensusSentenceSplitTests::test_source_tag_neither_blocks_the_split_nor_enters_the_anchor](../../tests/test_differences_schema.py#L791) (Zeile 791)
- [ConsensusSentenceSplitTests::test_abbreviations_and_initials_do_not_split](../../tests/test_differences_schema.py#L800) (Zeile 800)
- [ConsensusSentenceSplitTests::test_currency_abbreviations_do_not_break_markdown_claims](../../tests/test_differences_schema.py#L806) (Zeile 806)
- [ConsensusSentenceSplitTests::test_quantity_abbreviation_can_still_end_a_sentence](../../tests/test_differences_schema.py#L822) (Zeile 822)
- [ConsensusSentenceSplitTests::test_display_math_blocks_are_not_numbered](../../tests/test_differences_schema.py#L832) (Zeile 832)
- [ConsensusSentenceSplitTests::test_single_line_display_math_does_not_swallow_the_next_paragraph](../../tests/test_differences_schema.py#L854) (Zeile 854)
- [ConsensusSentenceSplitTests::test_inline_math_stays_part_of_its_sentence](../../tests/test_differences_schema.py#L869) (Zeile 869)
- [ConsensusSentenceSplitTests::test_headings_table_headers_and_code_are_not_numbered](../../tests/test_differences_schema.py#L879) (Zeile 879)
- [ConsensusSentenceSplitTests::test_list_counter_stays_out_of_the_anchor](../../tests/test_differences_schema.py#L892) (Zeile 892)
- [ConsensusSentenceSplitTests::test_table_cells_include_short_values_and_preserve_context](../../tests/test_differences_schema.py#L902) (Zeile 902)
- [ConsensusSentenceSplitTests::test_table_without_outer_pipes_and_escaped_pipe](../../tests/test_differences_schema.py#L916) (Zeile 916)
- [ConsensusSentenceSplitTests::test_table_inside_code_is_not_numbered](../../tests/test_differences_schema.py#L923) (Zeile 923)
- [ConsensusSentenceSplitTests::test_sentence_count_is_capped](../../tests/test_differences_schema.py#L929) (Zeile 929)
- [ConsensusSentenceSplitTests::test_empty_answer_yields_no_sentences](../../tests/test_differences_schema.py#L934) (Zeile 934)
- [SentenceAnchorTests::test_sentence_numbers_resolve_to_the_exact_sentence](../../tests/test_differences_schema.py#L960) (Zeile 960)
- [SentenceAnchorTests::test_unknown_sentence_number_is_ignored](../../tests/test_differences_schema.py#L971) (Zeile 971)
- [SentenceAnchorTests::test_zero_means_the_consensus_does_not_state_it](../../tests/test_differences_schema.py#L987) (Zeile 987)
- [SentenceAnchorTests::test_verbatim_anchor_still_works_for_older_payloads](../../tests/test_differences_schema.py#L996) (Zeile 996)
- [SentenceAnchorTests::test_duplicate_sentence_keeps_the_more_conservative_claim](../../tests/test_differences_schema.py#L1004) (Zeile 1004)
- [SentenceAnchorTests::test_identical_sentence_occurrences_keep_distinct_ids](../../tests/test_differences_schema.py#L1019) (Zeile 1019)
- [SentenceAnchorTests::test_visibly_identical_sentences_ignore_citations_and_markdown](../../tests/test_differences_schema.py#L1037) (Zeile 1037)
- [ClaimSupportThresholdTests::test_single_voice_claim_is_dropped](../../tests/test_differences_schema.py#L1064) (Zeile 1064)
- [ClaimSupportThresholdTests::test_two_voices_are_kept](../../tests/test_differences_schema.py#L1072) (Zeile 1072)
- [ClaimSupportThresholdTests::test_single_dissent_alone_is_dropped](../../tests/test_differences_schema.py#L1078) (Zeile 1078)
- [ClaimSupportThresholdTests::test_duplicate_dissent_from_one_model_counts_once](../../tests/test_differences_schema.py#L1085) (Zeile 1085)

</details>

<a id="test-differences-stats-py"></a>

## test_differences_stats.py

**Quelle:** [tests/test_differences_stats.py](../../tests/test_differences_stats.py) · **Bereiche:** Datenschutz, Fehlerdiagnostik, Konsens und Unterschiede.

**Ebene:** Unit-Tests für Statistikprojektion.

**Lauf:** 4 bestanden.

**Geprüftes Verhalten:** Null-/Fehlformat, Modell-/Judge-/Agreement-Metadaten und Counts, Firestore-kompatible Struktur ohne direkt verschachtelte Arrays sowie Ausschluss von Frage-/Claim-/Quote-Inhalten.

**Grenzen und Doubles:** Kein tatsächlicher Statistik-Write/Firestore; sensible Inhalte werden anhand fester Testwerte gesucht.

**Prüfauftrag für den Folgeaudit:** Weitere Freitextfelder und Schreibfehler mit redaction-/pipeline-Tests abgleichen.

**Direkte Codeverweise:** [app/services/differences_stats.py](../../app/services/differences_stats.py).

<details>
<summary>4 Testdefinitionen und ihre Quellstellen</summary>

- [BuildDifferencesStatsDocTests::test_none_for_missing_data](../../tests/test_differences_stats.py#L63) (Zeile 63)
- [BuildDifferencesStatsDocTests::test_counts_and_metadata](../../tests/test_differences_stats.py#L67) (Zeile 67)
- [BuildDifferencesStatsDocTests::test_firestore_compatible_no_nested_arrays](../../tests/test_differences_stats.py#L117) (Zeile 117)
- [BuildDifferencesStatsDocTests::test_no_content_leaks_into_doc](../../tests/test_differences_stats.py#L134) (Zeile 134)

</details>

<a id="test-drift-signal-py"></a>

## test_drift_signal.py

**Quelle:** [tests/test_drift_signal.py](../../tests/test_drift_signal.py) · **Bereiche:** Topics, Watch.

**Ebene:** Deterministische Unit-Tests.

**Lauf:** 7 bestanden.

**Geprüftes Verhalten:** Minor als Restatement, materielle Major-Änderung und Score außerhalb jüngster Bandbreite; oszillierende/stabile Stufen melden nur erstes Ereignis, alte Trigger werden neu bewertet, erster Check und Steady-Zählung.

**Grenzen und Doubles:** Synthetische Scorefolgen/Judge-Grades; keine Messung der semantischen Change-Judge-Qualität.

**Prüfauftrag für den Folgeaudit:** Grenzwerte, fehlende Scores und lange/unregelmäßige Historien gegen Watch/Topic-Fixtures abgleichen.

**Direkte Codeverweise:** [app/services/drift_signal.py](../../app/services/drift_signal.py).

<details>
<summary>7 Testdefinitionen und ihre Quellstellen</summary>

- [test_a_minor_grade_is_a_restatement_not_a_change](../../tests/test_drift_signal.py#L15) (Zeile 15)
- [test_a_score_that_leaves_the_band_of_the_recent_checks_is_movement](../../tests/test_drift_signal.py#L24) (Zeile 24)
- [test_a_score_swinging_between_two_cap_steps_reports_the_first_step_only](../../tests/test_drift_signal.py#L29) (Zeile 29)
- [test_a_sustained_step_reports_once_and_then_settles](../../tests/test_drift_signal.py#L45) (Zeile 45)
- [test_a_stored_trigger_from_the_looser_rule_is_recomputed_not_trusted](../../tests/test_drift_signal.py#L59) (Zeile 59)
- [test_the_first_check_has_no_band_and_no_predecessor](../../tests/test_drift_signal.py#L72) (Zeile 72)
- [test_steady_checks_counts_back_to_the_last_material_check](../../tests/test_drift_signal.py#L82) (Zeile 82)

</details>

<a id="test-e2e-safety-py"></a>

## test_e2e_safety.py

**Quelle:** [tests/test_e2e_safety.py](../../tests/test_e2e_safety.py) · **Bereiche:** Sicherheit, Testinfrastruktur.

**Ebene:** Guard-Unit-Tests und Python-Subprozess-/Lifespan-Verträge.

**Lauf:** 10 bestanden.

**Geprüftes Verhalten:** Erlaubt E2E nur mit Loopback und festem Demo-Projekt; lehnt fehlende/entfernte/fremde Ziele ab. Echter Security-Import stoppt vor Firebase-Initialisierung, Unit-Import braucht keine Service-Account-Datei und E2E-Lifespan startet keine Maintenance-Tasks.

**Grenzen und Doubles:** Lifespan-Taskstart ist gemockt; lokale Positivprüfung beweist keinen tatsächlich laufenden Emulator.

**Prüfauftrag für den Folgeaudit:** Profilübergänge mit dev.ps1 und Emulator-Tests zusammen betrachten.

**Direkte Codeverweise:** [app/core/e2e_profile.py](../../app/core/e2e_profile.py), [main.py](../../main.py).

<details>
<summary>6 Testdefinitionen und ihre Quellstellen</summary>

- [test_e2e_guard_accepts_only_the_local_demo_project](../../tests/test_e2e_safety.py#L28) (Zeile 28)
- [test_e2e_guard_rejects_missing_remote_or_unknown_targets](../../tests/test_e2e_safety.py#L42) (Zeile 42)
- [test_e2e_guard_is_a_noop_outside_the_explicit_profile](../../tests/test_e2e_safety.py#L47) (Zeile 47)
- [test_real_security_import_refuses_a_production_project_before_firebase_init](../../tests/test_e2e_safety.py#L51) (Zeile 51)
- [test_unit_profile_import_needs_no_service_account_file](../../tests/test_e2e_safety.py#L65) (Zeile 65)
- [test_e2e_lifespan_starts_no_maintenance_or_background_tasks](../../tests/test_e2e_safety.py#L80) (Zeile 80)

</details>

<a id="test-firestore-read-contracts-py"></a>

## test_firestore_read_contracts.py

**Quelle:** [tests/test_firestore_read_contracts.py](../../tests/test_firestore_read_contracts.py) · **Bereiche:** Modellstatistik, Persistenz.

**Ebene:** Echter Firestore-SDK-Queryaufbau mit RPC-Mock.

**Lauf:** 2 bestanden.

**Geprüftes Verhalten:** Leaderboard liest Katalog einmal und neun Count-Aggregationen mit passendem deklarativem Index, Filter/IN-Grenzen/Zeitraum, Timeout und ohne Retry in einem Read-only-Snapshot; prüft leeres und nichtleeres Ergebnis.

**Grenzen und Doubles:** SDK serialisiert reale Protobufs; Backend-RPCs sind gemockt. Indexverfügbarkeit und Query-Ausführung im echten Dienst werden nicht bewiesen.

**Prüfauftrag für den Folgeaudit:** Emulator-/Deployment-Indexvalidierung und Skalierung der Provider-Aliase abgleichen.

**Direkte Codeverweise:** [app/api/routers/pages.py](../../app/api/routers/pages.py).

<details>
<summary>1 Testdefinitionen und ihre Quellstellen</summary>

- [test_leaderboard_sdk_uses_indexed_counts_and_one_read_only_snapshot](../../tests/test_firestore_read_contracts.py#L59) (Zeile 59)

</details>

<a id="test-followup-context-py"></a>

## test_followup_context.py

**Quelle:** [tests/test_followup_context.py](../../tests/test_followup_context.py) · **Bereiche:** Bookmarks und Verlauf.

**Ebene:** Legacy-Kontextnormalisierung, Promptbuilder und Router mit Doubles.

**Lauf:** 18 bestanden.

**Geprüftes Verhalten:** Ungültige/unvollständige Kontexte ignorieren, gültige trimmen, Übergrößen ablehnen, nur eine Legacyebene; Adminlimits; Promptreihenfolge; Free-Followups; versionierter Kontext wird owner-/provider-/fragegebunden aufgelöst; prepare validiert ohne Injektion; Admin-/Customprompt und maximale UTF-8-/Zeichenlimits über prepare→ask mit einmaligem Datum; Memory-Schreibgrenze bleibt erhalten.

**Grenzen und Doubles:** Kontextservice und _run_ask teilweise ersetzt; die autoritative Kontextspeicherung wird hier nicht selbst ausgeführt.

**Prüfauftrag für den Folgeaudit:** ChatStore/ContextService-Tests für Ownerbindung, Versionkonflikte und tatsächlich gespeicherte Inhalte ergänzend heranziehen.

**Direkte Codeverweise:** [app/api/routers/chat.py](../../app/api/routers/chat.py), [app/core/config.py](../../app/core/config.py), [app/core/rate_limit.py](../../app/core/rate_limit.py), [app/services/llm/base.py](../../app/services/llm/base.py), [app/services/prompt_config.py](../../app/services/prompt_config.py).

**Direkte Testhelfer:** [tests/usage_test_support.py](../../tests/usage_test_support.py).

<details>
<summary>16 Testdefinitionen und ihre Quellstellen</summary>

- [TestNormalizeFollowupContext::test_non_dict_payloads_are_ignored](../../tests/test_followup_context.py#L69) (Zeile 69)
- [TestNormalizeFollowupContext::test_missing_or_empty_fields_are_ignored](../../tests/test_followup_context.py#L75) (Zeile 75)
- [TestNormalizeFollowupContext::test_valid_context_is_stripped_and_passed_through](../../tests/test_followup_context.py#L90) (Zeile 90)
- [TestNormalizeFollowupContext::test_oversized_texts_are_rejected](../../tests/test_followup_context.py#L96) (Zeile 96)
- [TestNormalizeFollowupContext::test_exactly_one_context_level_no_history](../../tests/test_followup_context.py#L108) (Zeile 108)
- [TestNormalizeFollowupContext::test_limits_are_admin_overridable](../../tests/test_followup_context.py#L121) (Zeile 121)
- [TestBuildFollowupSystemPrompt::test_contains_context_and_base_prompt](../../tests/test_followup_context.py#L139) (Zeile 139)
- [TestBuildFollowupSystemPrompt::test_context_block_precedes_base_prompt](../../tests/test_followup_context.py#L146) (Zeile 146)
- [test_ask_with_context_works_for_free_users](../../tests/test_followup_context.py#L158) (Zeile 158)
- [test_ask_with_context_version_loads_authoritative_context_without_compressing](../../tests/test_followup_context.py#L185) (Zeile 185)
- [test_prepare_with_context_works_for_free_users](../../tests/test_followup_context.py#L233) (Zeile 233)
- [test_prepare_uses_admin_answer_default_unless_user_has_custom_instructions](../../tests/test_followup_context.py#L246) (Zeile 246)
- [test_maximum_admin_prompt_survives_prepare_to_ask_round_trip](../../tests/test_followup_context.py#L267) (Zeile 267)
- [test_ask_rejects_oversized_context_before_provider_call](../../tests/test_followup_context.py#L295) (Zeile 295)
- [test_ask_without_context_only_adds_the_memory_write_boundary](../../tests/test_followup_context.py#L327) (Zeile 327)
- [test_prepare_validates_but_does_not_inject_context](../../tests/test_followup_context.py#L357) (Zeile 357)

</details>

<a id="test-frontend-assets-py"></a>

## test_frontend_assets.py

**Quelle:** [tests/test_frontend_assets.py](../../tests/test_frontend_assets.py) · **Bereiche:** Build und Betrieb, Frontend.

**Ebene:** Asset-Funktionen, Dateisystem und isolierte Pages-Routen.

**Lauf:** 14 bestanden.

**Geprüftes Verhalten:** App-HTML no-store, Bundle-Manifest-Dateien/Reihenfolge/defer/module, inhaltsbasierte URLs samt CSS-Imports und Änderungen, Build-/Dev-Auswahl, unbekannte/externe Pfade und keine alten manuellen Cachekeys in App-Template/Imports.

**Grenzen und Doubles:** Kein Browser/CDN. Build-spezifische Fälle überspringen ohne Manifest; Auditausführung mit vorhandenem Build prüfen.

**Prüfauftrag für den Folgeaudit:** Tiefe Importketten, beschädigte Manifeste und tatsächliches Cacheverhalten separat abgleichen.

**Direkte Codeverweise:** [app/api/routers/pages.py](../../app/api/routers/pages.py), [app/core/assets.py](../../app/core/assets.py), [static/js/app-state.js](../../static/js/app-state.js).

<details>
<summary>13 Testdefinitionen und ihre Quellstellen</summary>

- [test_app_html_cannot_cache_obsolete_bundle_urls](../../tests/test_frontend_assets.py#L19) (Zeile 19)
- [test_bundles_json_lists_only_files_that_exist](../../tests/test_frontend_assets.py#L43) (Zeile 43)
- [test_source_mode_serves_every_file_in_declared_order](../../tests/test_frontend_assets.py#L55) (Zeile 55)
- [test_source_mode_marks_defer_and_module_per_group](../../tests/test_frontend_assets.py#L70) (Zeile 70)
- [test_every_source_url_carries_a_content_hash](../../tests/test_frontend_assets.py#L81) (Zeile 81)
- [test_editing_a_file_changes_its_url](../../tests/test_frontend_assets.py#L86) (Zeile 86)
- [test_style_url_changes_when_an_imported_sheet_changes](../../tests/test_frontend_assets.py#L100) (Zeile 100)
- [test_built_mode_is_used_when_a_manifest_exists](../../tests/test_frontend_assets.py#L115) (Zeile 115)
- [test_built_mode_keeps_the_head_group_first_and_blocking](../../tests/test_frontend_assets.py#L128) (Zeile 128)
- [test_dev_flag_overrides_an_existing_build](../../tests/test_frontend_assets.py#L146) (Zeile 146)
- [test_asset_url_leaves_unknown_and_external_paths_alone](../../tests/test_frontend_assets.py#L152) (Zeile 152)
- [test_no_manual_version_marks_are_left_in_the_app_template](../../tests/test_frontend_assets.py#L158) (Zeile 158)
- [test_no_manual_version_marks_hide_inside_app_javascript_imports](../../tests/test_frontend_assets.py#L166) (Zeile 166)

</details>

<a id="test-frontend-build-py"></a>

## test_frontend_build.py

**Quelle:** [tests/test_frontend_build.py](../../tests/test_frontend_build.py) · **Bereiche:** Build und Betrieb.

**Ebene:** Build-Artefakt-/Fingerprint-Verträge.

**Lauf:** 8 bestanden.

**Geprüftes Verhalten:** Windows/Linux-Newline-stabiler Source-Fingerprint mit Vendor-Byteprüfung, Staleness und vollständige Inputs, vorhandene Hash-Dateinamen, Request-/Byte-Reduktion, erhaltene globale Fensterverträge, inline CSS-Imports und auflösbare Font-/Vendor-/Lizenzdateien.

**Grenzen und Doubles:** Globalnamen als Text beweisen keine ausführbare Interoperabilität; mehrere Fälle benötigen generiertes Manifest. Kein Browser-Funktionstest des minifizierten Bundles.

**Prüfauftrag für den Folgeaudit:** Browser-Tests ausdrücklich gegen Build- und Source-Modus abgleichen.

**Direkte Codeverweise:** [app/core/assets.py](../../app/core/assets.py), [scripts/build_frontend.mjs](../../scripts/build_frontend.mjs), [scripts/frontend-output.mjs](../../scripts/frontend-output.mjs), [static/js/bundles.json](../../static/js/bundles.json), [templates/index.html](../../templates/index.html).

<details>
<summary>8 Testdefinitionen und ihre Quellstellen</summary>

- [test_build_fingerprint_survives_windows_linux_checkout_but_checks_vendor_bytes](../../tests/test_frontend_build.py#L32) (Zeile 32)
- [test_dist_is_not_stale](../../tests/test_frontend_build.py#L51) (Zeile 51)
- [test_manifest_records_every_input_needed_for_python_only_staleness_checks](../../tests/test_frontend_build.py#L61) (Zeile 61)
- [test_every_file_the_manifest_points_at_exists](../../tests/test_frontend_build.py#L83) (Zeile 83)
- [test_bundling_actually_reduced_the_request_count_and_bytes](../../tests/test_frontend_build.py#L95) (Zeile 95)
- [test_the_bundle_keeps_the_window_contracts_addressable](../../tests/test_frontend_build.py#L119) (Zeile 119)
- [test_css_bundle_keeps_relative_asset_paths_resolvable](../../tests/test_frontend_build.py#L144) (Zeile 144)
- [test_app_vendor_assets_are_local_versioned_and_include_fonts_and_licenses](../../tests/test_frontend_build.py#L158) (Zeile 158)

</details>

<a id="test-frontend-resilience-py"></a>

## test_frontend_resilience.py

**Quelle:** [tests/test_frontend_resilience.py](../../tests/test_frontend_resilience.py) · **Bereiche:** Build und Betrieb, Frontend.

**Ebene:** Quelltextverträge und Asset-Datei-/Git-Prüfung.

**Lauf:** 4 bestanden.

**Geprüftes Verhalten:** Markdown-Fallback-Signaturen, begrenzter usage_storage_busy-Retry vor Fan-out, mobiles Enter/IME-Gating sowie Existenz, Cache-Key und Datums-Konsistenz aller aktiven lokalen Assets.

**Grenzen und Doubles:** Interaktion/Retry überwiegend statisch. Assetprüfung verwendet echte Dateien und Git-Historie, aber keinen HTTP/CDN-Cache. Shallow-Clone kann Dateihistorie verfälschen.

**Prüfauftrag für den Folgeaudit:** Git-Historie für Cache-Key-Ergebnis sicherstellen; Markdown-/IME-/Retry-Verhalten gegen ausführbare JS/E2E-Prüfungen abgleichen.

**Direkte Codeverweise:** [static/js/app-init.js](../../static/js/app-init.js), [static/js/markdown-stream.js](../../static/js/markdown-stream.js), [static/js/query-send.js](../../static/js/query-send.js), [static/js/usage-limit.js](../../static/js/usage-limit.js).

<details>
<summary>4 Testdefinitionen und ihre Quellstellen</summary>

- [test_missing_markdown_dependencies_render_plaintext_instead_of_throwing](../../tests/test_frontend_resilience.py#L20) (Zeile 20)
- [test_usage_storage_busy_is_retried_and_stops_before_model_fanout](../../tests/test_frontend_resilience.py#L29) (Zeile 29)
- [test_all_active_local_assets_have_current_consistent_cache_keys](../../tests/test_frontend_resilience.py#L110) (Zeile 110)
- [test_mobile_enter_keeps_the_textarea_newline_behavior](../../tests/test_frontend_resilience.py#L136) (Zeile 136)

</details>

<a id="test-logging-redaction-contract-py"></a>

## test_logging_redaction_contract.py

**Quelle:** [tests/test_logging_redaction_contract.py](../../tests/test_logging_redaction_contract.py) · **Bereiche:** Datenschutz, Fehlerdiagnostik.

**Ebene:** AST-Vertrag und Runtime-Tests mit SMTP-/Notifier-Doubles.

**Lauf:** 6 bestanden.

**Geprüftes Verhalten:** AST-Scan verbietet rohe Exception-Logs; globaler Handler liefert generische 500-Meldung/Alert, safe_traceback enthält begrenzte lokale Koordinaten ohne Geheimnisse, safe_exception verwirft freie Errorcodes und Mailfehler redigieren Empfänger/Credentials/Providertext.

**Grenzen und Doubles:** AST erkennt definierte Logging-Muster, keine vollständige Informationsflussanalyse. SMTP/Alertversand ersetzt; Runtime nur exemplarische Fehler.

**Prüfauftrag für den Folgeaudit:** Strukturierte/nicht standardisierte Logs und weitere Secret-Felder gegen produktive Sink-Pfade abgleichen.

**Direkte Codeverweise:** [app/core/observability.py](../../app/core/observability.py), [app/services/mailer.py](../../app/services/mailer.py), [main.py](../../main.py).

<details>
<summary>6 Testdefinitionen und ihre Quellstellen</summary>

- [test_runtime_never_emits_raw_exception_tracebacks_or_messages](../../tests/test_logging_redaction_contract.py#L62) (Zeile 62)
- [test_global_exception_handler_logs_and_alerts_only_safe_categories](../../tests/test_logging_redaction_contract.py#L100) (Zeile 100)
- [test_safe_traceback_reports_where_not_what](../../tests/test_logging_redaction_contract.py#L133) (Zeile 133)
- [test_safe_traceback_is_bounded_and_survives_a_bare_exception](../../tests/test_logging_redaction_contract.py#L159) (Zeile 159)
- [test_safe_exception_never_projects_arbitrary_string_error_codes](../../tests/test_logging_redaction_contract.py#L175) (Zeile 175)
- [test_mail_delivery_error_log_redacts_recipient_credentials_and_provider_body](../../tests/test_logging_redaction_contract.py#L183) (Zeile 183)

</details>

<a id="test-memory-edit-py"></a>

## test_memory_edit.py

**Quelle:** [tests/test_memory_edit.py](../../tests/test_memory_edit.py) · **Bereiche:** Admin, Konten und Tarife, Nutzergedächtnis.

**Ebene:** Edit-Service/Repository und Router mit DB-/LLM-Doubles.

**Lauf:** 14 bestanden.

**Geprüftes Verhalten:** Strikter minimaler Patch, eindeutiges Replace, Append/Correct-Intent, keine Delete-Patches beim Remember, Revision/Undo, idempotenter Provideraufruf, persistente Tages-/Global-/In-flight-Limits und kein Truncation/Charge bei Übergröße. Adminfallback, schema-/tokengebundener LLM-Payload und direkter expliziter Edit-Endpunkt.

**Grenzen und Doubles:** Persistence-Guard in Fixture deaktiviert, DB/LLM ersetzt; Undo nach konkurrierender Fremdänderung wird nicht durch den einfachen Roundtrip bewiesen.

**Prüfauftrag für den Folgeaudit:** Tombstone-/Undo-Konflikt-/Crashfälle und echte parallele Edits im nächsten Audit abgleichen.

**Direkte Codeverweise:** [app/api/routers/users.py](../../app/api/routers/users.py), [app/core/config.py](../../app/core/config.py), [app/core/rate_limit.py](../../app/core/rate_limit.py), [app/services/memory_edit.py](../../app/services/memory_edit.py), [app/services/user_memory.py](../../app/services/user_memory.py).

<details>
<summary>14 Testdefinitionen und ihre Quellstellen</summary>

- [test_model_patch_schema_is_strict_and_passage_bounded](../../tests/test_memory_edit.py#L97) (Zeile 97)
- [test_replace_is_revision_checked_and_undo_restores_exact_content](../../tests/test_memory_edit.py#L118) (Zeile 118)
- [test_non_unique_target_is_never_overwritten](../../tests/test_memory_edit.py#L165) (Zeile 165)
- [test_same_client_request_never_calls_provider_twice](../../tests/test_memory_edit.py#L189) (Zeile 189)
- [test_remember_intent_appends_when_no_related_entry_exists](../../tests/test_memory_edit.py#L215) (Zeile 215)
- [test_remember_intent_replaces_one_unique_conflicting_passage](../../tests/test_memory_edit.py#L246) (Zeile 246)
- [test_remember_intent_rejects_delete_patch](../../tests/test_memory_edit.py#L273) (Zeile 273)
- [test_smallest_replace_preserves_unrelated_details](../../tests/test_memory_edit.py#L296) (Zeile 296)
- [test_persistent_daily_budget_is_shared_by_repository_instances](../../tests/test_memory_edit.py#L326) (Zeile 326)
- [test_over_plan_memory_is_not_truncated_or_charged_by_ai_edit](../../tests/test_memory_edit.py#L349) (Zeile 349)
- [test_invalid_admin_values_fall_back_to_safe_defaults](../../tests/test_memory_edit.py#L369) (Zeile 369)
- [test_provider_call_is_schema_bound_no_reasoning_and_output_capped](../../tests/test_memory_edit.py#L380) (Zeile 380)
- [test_one_in_flight_edit_and_global_budget_are_persistent](../../tests/test_memory_edit.py#L423) (Zeile 423)
- [test_edit_endpoint_applies_explicit_feedback_without_confirmation](../../tests/test_memory_edit.py#L456) (Zeile 456)

</details>

<a id="test-model-configuration-py"></a>

## test_model_configuration.py

**Quelle:** [tests/test_model_configuration.py](../../tests/test_model_configuration.py) · **Bereiche:** Admin, Modelle und Provider.

**Ebene:** Konfigurations-/Payload-Unit-Tests, Admin-/DB-Doubles und UI-Sourceverträge.

**Lauf:** 27 bestanden.

**Geprüftes Verhalten:** Ungültiger Adminsave ohne Runtime-Mutation, Aktivierungs-/DB-Rollback und read-only Readiness; Own-/Developer-Key-Trennung. Entfernte/kanonische IDs, Presets/Free-/Pro-Gates, Provider-spezifische Search-/Reasoning-/Attachment-Policies, Errorprojektion und Eingabehelper.

**Grenzen und Doubles:** Prüft gespeicherte Regeln/Payloads des Commitstands; keine Live-Verfügbarkeit oder Akzeptanz der Modell-APIs. UI-Auszüge nur statisch.

**Prüfauftrag für den Folgeaudit:** Aktualisierte Modelllisten, atomare konkurrierende Adminsaves und reale Providerverträge separat prüfen.

**Direkte Codeverweise:** [app/api/routers/admin.py](../../app/api/routers/admin.py), [app/api/routers/chat.py](../../app/api/routers/chat.py), [app/core/config.py](../../app/core/config.py), [app/services/llm/base.py](../../app/services/llm/base.py), [app/services/llm/citations.py](../../app/services/llm/citations.py), [app/services/llm/engines.py](../../app/services/llm/engines.py).

<details>
<summary>27 Testdefinitionen und ihre Quellstellen</summary>

- [ModelConfigurationTests::test_rejected_admin_document_cannot_mutate_runtime_limits](../../tests/test_model_configuration.py#L51) (Zeile 51)
- [ModelConfigurationTests::test_runtime_reload_rolls_back_all_mutations_on_activation_error](../../tests/test_model_configuration.py#L71) (Zeile 71)
- [ModelConfigurationTests::test_admin_update_restores_persisted_document_on_activation_error](../../tests/test_model_configuration.py#L97) (Zeile 97)
- [ModelConfigurationTests::test_readiness_config_load_never_creates_missing_document](../../tests/test_model_configuration.py#L129) (Zeile 129)
- [ModelConfigurationTests::test_engine_developer_keys_use_shared_credentials_source](../../tests/test_model_configuration.py#L143) (Zeile 143)
- [ModelConfigurationTests::test_engine_own_keys_are_stripped_and_never_use_developer_keys](../../tests/test_model_configuration.py#L153) (Zeile 153)
- [ModelConfigurationTests::test_admin_models_get_is_read_only_and_preserves_judge_family](../../tests/test_model_configuration.py#L166) (Zeile 166)
- [ModelConfigurationTests::test_removed_low_reasoning_aliases_are_not_runtime_models](../../tests/test_model_configuration.py#L221) (Zeile 221)
- [ModelConfigurationTests::test_missing_openrouter_legacy_ids_stay_removed](../../tests/test_model_configuration.py#L231) (Zeile 231)
- [ModelConfigurationTests::test_admin_drops_removed_aliases_everywhere](../../tests/test_model_configuration.py#L263) (Zeile 263)
- [ModelConfigurationTests::test_new_gemini_models_are_direct_and_temperature_free](../../tests/test_model_configuration.py#L281) (Zeile 281)
- [ModelConfigurationTests::test_web_search_budget_and_engine_per_family](../../tests/test_model_configuration.py#L299) (Zeile 299)
- [ModelConfigurationTests::test_deep_search_keeps_the_wider_search_budget](../../tests/test_model_configuration.py#L327) (Zeile 327)
- [ModelConfigurationTests::test_gemini_models_are_available_to_admin](../../tests/test_model_configuration.py#L334) (Zeile 334)
- [ModelConfigurationTests::test_admin_premium_is_limited_to_configured_provider_models](../../tests/test_model_configuration.py#L340) (Zeile 340)
- [ModelConfigurationTests::test_admin_dependencies_are_informative_not_server_enforced](../../tests/test_model_configuration.py#L360) (Zeile 360)
- [ModelConfigurationTests::test_retired_grok_aliases_are_canonicalized](../../tests/test_model_configuration.py#L375) (Zeile 375)
- [ModelConfigurationTests::test_grok_no_reasoning_and_high_reasoning_payloads](../../tests/test_model_configuration.py#L384) (Zeile 384)
- [ModelConfigurationTests::test_muse_reasoning_is_pinned_low_because_it_cannot_be_disabled](../../tests/test_model_configuration.py#L398) (Zeile 398)
- [ModelConfigurationTests::test_kimi_search_keeps_moonshot_zdr_route_and_model_reasoning](../../tests/test_model_configuration.py#L413) (Zeile 413)
- [ModelConfigurationTests::test_kimi_and_glm_payload_policies_are_applied](../../tests/test_model_configuration.py#L432) (Zeile 432)
- [ModelConfigurationTests::test_effective_reasoning_policy_matches_answer_payload_precedence](../../tests/test_model_configuration.py#L447) (Zeile 447)
- [ModelConfigurationTests::test_access_control_only_has_free_and_pro_models](../../tests/test_model_configuration.py#L467) (Zeile 467)
- [ModelConfigurationTests::test_presets_are_complete_and_free_presets_stay_free](../../tests/test_model_configuration.py#L487) (Zeile 487)
- [ModelConfigurationTests::test_admin_and_picker_have_no_early_contract](../../tests/test_model_configuration.py#L523) (Zeile 523)
- [ModelConfigurationTests::test_provider_errors_are_structured_without_fallback_response](../../tests/test_model_configuration.py#L537) (Zeile 537)
- [ModelConfigurationTests::test_input_helpers](../../tests/test_model_configuration.py#L548) (Zeile 548)

</details>

<a id="test-model-configuration-regressions-py"></a>

## test_model_configuration_regressions.py

**Quelle:** [tests/test_model_configuration_regressions.py](../../tests/test_model_configuration_regressions.py) · **Bereiche:** Admin, Frontend, Modelle und Provider.

**Ebene:** Konfigurations-/Metadaten-Runtime und UI-Quelltextverträge.

**Lauf:** 33 bestanden.

**Geprüftes Verhalten:** Kanonische API-IDs, Reasoning pro Familie, Deep-Think-/Preset-/Judge-/Memory-Modellauswahl und Fallbacks, Labels und kollisionsfreier Admin-Metadatenumschlag. Credential-Verfügbarkeit nur als Boolean, Watch-Tier-Config, Picker-/Admincontrols, bestehende Präferenzen und Fehler-/Inputhelper.

**Grenzen und Doubles:** Viele Picker-/Admin-Verträge sind reine Strings. Erwartete Modellwerte stammen aus Commit-Konfiguration, kein unabhängiger Live-API-Nachweis. Teilweise Überschneidung mit test_model_configuration.

**Prüfauftrag für den Folgeaudit:** Doppelte Assertions auf Nutzen prüfen und kritische Save-/Picker-Flows mit JS/E2E verbinden.

**Direkte Codeverweise:** [app/api/routers/admin.py](../../app/api/routers/admin.py), [app/api/routers/chat.py](../../app/api/routers/chat.py), [app/core/config.py](../../app/core/config.py), [app/services/llm/base.py](../../app/services/llm/base.py), [app/services/llm/citations.py](../../app/services/llm/citations.py), [app/services/llm/consensus_engine.py](../../app/services/llm/consensus_engine.py), [app/services/llm/engines.py](../../app/services/llm/engines.py), [static/js/model-picker.js](../../static/js/model-picker.js).

<details>
<summary>33 Testdefinitionen und ihre Quellstellen</summary>

- [ExistingModelFlowTests::test_normal_pro_models_keep_api_names_without_low_payloads](../../tests/test_model_configuration_regressions.py#L40) (Zeile 40)
- [ExistingModelFlowTests::test_all_allowed_model_configs_use_openrouter_ids_without_changing_keys](../../tests/test_model_configuration_regressions.py#L67) (Zeile 67)
- [ExistingModelFlowTests::test_grok_43_no_reasoning_uses_canonical_api_model_and_none_effort](../../tests/test_model_configuration_regressions.py#L96) (Zeile 96)
- [ExistingModelFlowTests::test_mistral_defaults_use_supported_reasoning_models](../../tests/test_model_configuration_regressions.py#L121) (Zeile 121)
- [ExistingModelFlowTests::test_deep_think_consensus_model_is_always_available_and_pro_gated](../../tests/test_model_configuration_regressions.py#L146) (Zeile 146)
- [ExistingModelFlowTests::test_consensus_presets_are_complete_model_sets](../../tests/test_model_configuration_regressions.py#L152) (Zeile 152)
- [ExistingModelFlowTests::test_admin_normalizes_preset_models_and_keeps_free_presets_free](../../tests/test_model_configuration_regressions.py#L170) (Zeile 170)
- [ExistingModelFlowTests::test_apply_deep_think_model_validates_and_falls_back](../../tests/test_model_configuration_regressions.py#L217) (Zeile 217)
- [ExistingModelFlowTests::test_normalize_models_document_validates_deep_think_model](../../tests/test_model_configuration_regressions.py#L233) (Zeile 233)
- [ExistingModelFlowTests::test_apply_judge_families_and_family_preference](../../tests/test_model_configuration_regressions.py#L258) (Zeile 258)
- [ExistingModelFlowTests::test_apply_chat_memory_models_keeps_a_valid_model_per_family](../../tests/test_model_configuration_regressions.py#L287) (Zeile 287)
- [ExistingModelFlowTests::test_admin_template_exposes_the_chat_memory_selection](../../tests/test_model_configuration_regressions.py#L341) (Zeile 341)
- [ExistingModelFlowTests::test_judge_engines_resolve_virtual_ids_to_their_api_model](../../tests/test_model_configuration_regressions.py#L349) (Zeile 349)
- [ExistingModelFlowTests::test_grok_reasoning_labels_are_consistent](../../tests/test_model_configuration_regressions.py#L383) (Zeile 383)
- [ExistingModelFlowTests::test_unknown_allowed_style_ids_get_public_product_labels](../../tests/test_model_configuration_regressions.py#L394) (Zeile 394)
- [ExistingModelFlowTests::test_admin_meta_envelope_cannot_shadow_a_provider_list](../../tests/test_model_configuration_regressions.py#L399) (Zeile 399)
- [ExistingModelFlowTests::test_admin_meta_exposes_virtual_api_models](../../tests/test_model_configuration_regressions.py#L412) (Zeile 412)
- [ExistingModelFlowTests::test_admin_meta_exposes_the_effective_reasoning_policy](../../tests/test_model_configuration_regressions.py#L419) (Zeile 419)
- [ExistingModelFlowTests::test_admin_meta_reports_provider_credentials_as_booleans_only](../../tests/test_model_configuration_regressions.py#L456) (Zeile 456)
- [ExistingModelFlowTests::test_admin_meta_stays_silent_when_the_credential_probe_fails](../../tests/test_model_configuration_regressions.py#L478) (Zeile 478)
- [ExistingModelFlowTests::test_admin_template_lists_premium_models_as_locked_instead_of_hiding](../../tests/test_model_configuration_regressions.py#L492) (Zeile 492)
- [ExistingModelFlowTests::test_admin_template_has_tabs_and_deep_think_control](../../tests/test_model_configuration_regressions.py#L503) (Zeile 503)
- [ExistingModelFlowTests::test_consensus_preset_picker_applies_answers_and_pro_gates_thorough](../../tests/test_model_configuration_regressions.py#L525) (Zeile 525)
- [ExistingModelFlowTests::test_empty_app_and_consensus_picker_css_prevent_overflow](../../tests/test_model_configuration_regressions.py#L538) (Zeile 538)
- [ExistingModelFlowTests::test_index_injects_deep_think_consensus_model](../../tests/test_model_configuration_regressions.py#L545) (Zeile 545)
- [ExistingModelFlowTests::test_saved_preferences_are_not_overwritten_when_present](../../tests/test_model_configuration_regressions.py#L553) (Zeile 553)
- [ExistingModelFlowTests::test_watch_models_are_separate_for_free_and_pro](../../tests/test_model_configuration_regressions.py#L561) (Zeile 561)
- [ExistingModelFlowTests::test_admin_model_rows_have_order_and_default_controls](../../tests/test_model_configuration_regressions.py#L608) (Zeile 608)
- [ExistingModelFlowTests::test_admin_model_rows_have_separate_premium_and_consensus_toggles](../../tests/test_model_configuration_regressions.py#L614) (Zeile 614)
- [ExistingModelFlowTests::test_admin_exposes_free_and_pro_watch_model_config](../../tests/test_model_configuration_regressions.py#L623) (Zeile 623)
- [ExistingModelFlowTests::test_provider_errors_are_structured_without_fallback_response](../../tests/test_model_configuration_regressions.py#L634) (Zeile 634)
- [ExistingModelFlowTests::test_question_validation_rejects_empty_input](../../tests/test_model_configuration_regressions.py#L646) (Zeile 646)
- [ExistingModelFlowTests::test_boolean_flag_parser_is_whitespace_tolerant](../../tests/test_model_configuration_regressions.py#L653) (Zeile 653)

</details>

<a id="test-model-leaderboard-py"></a>

## test_model_leaderboard.py

**Quelle:** [tests/test_model_leaderboard.py](../../tests/test_model_leaderboard.py) · **Bereiche:** Cache, Modellstatistik, Öffentliche Seiten.

**Ebene:** Pages/API mit FakeDb und echten lokalen Threads.

**Lauf:** 18 bestanden.

**Geprüftes Verhalten:** Serverseitiges Ranking ohne JS, Aliasaggregation/Verfügbarkeitsdaten/Zeitraum, Cacheheader und 503 statt Nullranking; Count-Queries in Chunks/einem Snapshot, leere Cachetreffer, TTL/DB-Isolation/Singleflight. Fehlender Index fällt einmal auf Scan zurück; andere/partielle Fehler aktivieren keinen Cache.

**Grenzen und Doubles:** Fake-Snapshot/Queryausführung, künstliche Uhr; SDK-Protobuf-Vertrag separat in test_firestore_read_contracts. Kein realer Index oder Browser.

**Prüfauftrag für den Folgeaudit:** Große Aliasbestände, tatsächliche Indexumstellung und SSR/JS-Datenparität abgleichen.

**Direkte Codeverweise:** [app/api/routers/pages.py](../../app/api/routers/pages.py), [app/core/rate_limit.py](../../app/core/rate_limit.py).

<details>
<summary>14 Testdefinitionen und ihre Quellstellen</summary>

- [test_pulse_renders_cached_ranking_without_javascript](../../tests/test_model_leaderboard.py#L42) (Zeile 42)
- [test_pulse_failure_is_retryable_not_a_fake_zero_ranking](../../tests/test_model_leaderboard.py#L60) (Zeile 60)
- [test_public_model_leaderboard_aggregates_aliases_and_sets_cache](../../tests/test_model_leaderboard.py#L168) (Zeile 168)
- [test_public_model_leaderboard_supports_shared_window](../../tests/test_model_leaderboard.py#L205) (Zeile 205)
- [test_public_model_leaderboard_rejects_unknown_period](../../tests/test_model_leaderboard.py#L226) (Zeile 226)
- [test_period_counts_preserve_historical_aliases_other_dates_and_deleted_votes](../../tests/test_model_leaderboard.py#L237) (Zeile 237)
- [test_period_alias_counts_chunk_above_firestore_in_limit](../../tests/test_model_leaderboard.py#L270) (Zeile 270)
- [test_server_cache_reuses_empty_totals_and_refreshes_at_expiry](../../tests/test_model_leaderboard.py#L288) (Zeile 288)
- [test_cache_entries_separate_periods_and_database_clients](../../tests/test_model_leaderboard.py#L306) (Zeile 306)
- [test_concurrent_period_misses_share_one_refresh](../../tests/test_model_leaderboard.py#L320) (Zeile 320)
- [test_counts_use_one_snapshot_despite_concurrent_vote_deletion](../../tests/test_model_leaderboard.py#L342) (Zeile 342)
- [test_missing_index_falls_back_once_then_upgrades_after_expiry](../../tests/test_model_leaderboard.py#L358) (Zeile 358)
- [test_failed_aggregation_is_not_cached_or_replaced_with_scan](../../tests/test_model_leaderboard.py#L378) (Zeile 378)
- [test_partial_refresh_does_not_publish_or_extend_expired_cache](../../tests/test_model_leaderboard.py#L395) (Zeile 395)

</details>

<a id="test-multi-run-architecture-py"></a>

## test_multi_run_architecture.py

**Quelle:** [tests/test_multi_run_architecture.py](../../tests/test_multi_run_architecture.py) · **Bereiche:** Frontend, Nebenläufigkeit.

**Ebene:** Quelltextverträge.

**Lauf:** 3 bestanden.

**Geprüftes Verhalten:** Registry als Session-Owner mit zwei aktiven Runs, Conversation-Locks und eingefrorener Config; gebundene Query-/Consensus-Callbacks, explizite Bookmark-/Logout-/Resolution-Ownership und Run-View-Projektion.

**Grenzen und Doubles:** Nur Strings/Ladereihenfolge; beweist keine korrekte Isolation bei wirklich überlappenden Antworten.

**Prüfauftrag für den Folgeaudit:** Mit run-registry-/ownership-/race-JS- und Browser-Dateien abgleichen.

**Direkte Codeverweise:** [static/firebase.js](../../static/firebase.js), [static/js/app-init.js](../../static/js/app-init.js), [static/js/bundles.json](../../static/js/bundles.json), [static/js/consensus-insights.js](../../static/js/consensus-insights.js), [static/js/consensus-run.js](../../static/js/consensus-run.js), [static/js/query-send.js](../../static/js/query-send.js), [static/js/run-registry.js](../../static/js/run-registry.js), [static/js/run-view.js](../../static/js/run-view.js), [static/js/sources.js](../../static/js/sources.js).

<details>
<summary>3 Testdefinitionen und ihre Quellstellen</summary>

- [test_registry_is_the_single_browser_session_owner_and_loads_before_consumers](../../tests/test_multi_run_architecture.py#L18) (Zeile 18)
- [test_query_and_consensus_callbacks_use_their_bound_context_not_visible_dom](../../tests/test_multi_run_architecture.py#L37) (Zeile 37)
- [test_bookmark_view_and_logout_keep_run_ownership_explicit](../../tests/test_multi_run_architecture.py#L70) (Zeile 70)

</details>

<a id="test-navigation-settings-ui-py"></a>

## test_navigation_settings_ui.py

**Quelle:** [tests/test_navigation_settings_ui.py](../../tests/test_navigation_settings_ui.py) · **Bereiche:** Einstellungen, Frontend, Nutzergedächtnis, Scrollen und Navigation.

**Ebene:** Quelltextverträge.

**Lauf:** 27 bestanden.

**Geprüftes Verhalten:** Sidebar/Bookmark-Suche/Modellpicker, öffentliche Navigation und Provider-Surfaces, Mindestmodellauswahl, Demo ohne Usage-Signale, responsive Composer-/Reading-Chrome-Regeln. Settings-Tabs und Memory zuerst, Lazy-Load, explizites Remember/Correct/Ask-about-this, Logout-Abbruch/Secret-Cleanup und Watch-Session-Fencing.

**Grenzen und Doubles:** 27 Tests prüfen Text/CSS/DOM-Strukturen im Source, keine tatsächlichen Klicks, Layouts oder Race-Ausführung.

**Prüfauftrag für den Folgeaudit:** Jede kritische Nutzeraktion gegen ausführbare JS-/Browserdateien abgleichen; harte Pixel-/Copy-Verträge auf unnötige Fragilität prüfen.

**Direkte Codeverweise:** [static/app-ui.js](../../static/app-ui.js), [static/css/components-input.css](../../static/css/components-input.css), [static/css/components-memory-edit.css](../../static/css/components-memory-edit.css), [static/css/components-misc.css](../../static/css/components-misc.css), [static/css/components-modals.css](../../static/css/components-modals.css), [static/css/components-watch.css](../../static/css/components-watch.css), [static/css/landing.css](../../static/css/landing.css), [static/css/layout.css](../../static/css/layout.css), [static/css/model-pulse.css](../../static/css/model-pulse.css), [static/css/shell.css](../../static/css/shell.css), [static/demo.js](../../static/demo.js), [static/firebase.js](../../static/firebase.js), [static/js/agent-chat.js](../../static/js/agent-chat.js), [static/js/app-init.js](../../static/js/app-init.js), [static/js/composer-quote.js](../../static/js/composer-quote.js), [static/js/memory-edit.js](../../static/js/memory-edit.js), [static/js/model-picker.js](../../static/js/model-picker.js), [static/js/model-pulse.js](../../static/js/model-pulse.js), [static/js/query-send.js](../../static/js/query-send.js), [static/js/user-memory.js](../../static/js/user-memory.js), [static/js/watch-state.js](../../static/js/watch-state.js), [static/js/watch.js](../../static/js/watch.js), [templates/about.html](../../templates/about.html), [templates/ai-model-comparison.html](../../templates/ai-model-comparison.html), [templates/consensus-engine.html](../../templates/consensus-engine.html), [templates/index.html](../../templates/index.html), [templates/landing.html](../../templates/landing.html), [templates/model-pulse.html](../../templates/model-pulse.html), [templates/partials/public_footer.html](../../templates/partials/public_footer.html), [templates/partials/public_nav.html](../../templates/partials/public_nav.html), [templates/share.html](../../templates/share.html).

**Direkte Testhelfer:** [tests/frontend_order.py](../../tests/frontend_order.py).

<details>
<summary>27 Testdefinitionen und ihre Quellstellen</summary>

- [test_sidebar_navigation_is_self_contained_and_guest_login_is_top_only](../../tests/test_navigation_settings_ui.py#L13) (Zeile 13)
- [test_public_navigation_is_compact_and_learning_links_live_in_footer](../../tests/test_navigation_settings_ui.py#L74) (Zeile 74)
- [test_demo_watch_nudge_and_dedicated_model_pulse_match_the_product_contract](../../tests/test_navigation_settings_ui.py#L86) (Zeile 86)
- [test_model_pulse_inverts_all_monochrome_provider_logos_in_dark_mode](../../tests/test_navigation_settings_ui.py#L127) (Zeile 127)
- [test_meta_muse_is_present_across_public_provider_surfaces](../../tests/test_navigation_settings_ui.py#L139) (Zeile 139)
- [test_kimi_and_glm_are_present_across_public_provider_surfaces](../../tests/test_navigation_settings_ui.py#L155) (Zeile 155)
- [test_consensus_run_requires_two_selected_models_before_starting](../../tests/test_navigation_settings_ui.py#L174) (Zeile 174)
- [test_cross_check_greeting_is_light_in_the_app_and_absent_from_the_landing_mock](../../tests/test_navigation_settings_ui.py#L189) (Zeile 189)
- [test_demo_never_writes_product_usage_signals](../../tests/test_navigation_settings_ui.py#L208) (Zeile 208)
- [test_mobile_brand_and_desktop_input_centering_contract](../../tests/test_navigation_settings_ui.py#L216) (Zeile 216)
- [test_fixed_navigation_yields_while_consensus_or_watch_content_is_read](../../tests/test_navigation_settings_ui.py#L228) (Zeile 228)
- [test_disclaimer_stays_attached_below_the_moving_input_section](../../tests/test_navigation_settings_ui.py#L244) (Zeile 244)
- [test_light_input_is_white_and_account_popup_uses_opaque_surfaces](../../tests/test_navigation_settings_ui.py#L257) (Zeile 257)
- [test_chat_textarea_does_not_keep_the_generic_inset_frame](../../tests/test_navigation_settings_ui.py#L272) (Zeile 272)
- [test_chat_textarea_grows_until_responsive_height_limit](../../tests/test_navigation_settings_ui.py#L280) (Zeile 280)
- [test_hero_greeting_requires_agent_mode_and_available_space](../../tests/test_navigation_settings_ui.py#L296) (Zeile 296)
- [test_settings_are_grouped_without_changing_control_ids](../../tests/test_navigation_settings_ui.py#L312) (Zeile 312)
- [test_every_settings_category_is_a_tab_panel_with_a_nav_item](../../tests/test_navigation_settings_ui.py#L339) (Zeile 339)
- [test_settings_tabs_read_as_navigation_not_as_buttons](../../tests/test_navigation_settings_ui.py#L368) (Zeile 368)
- [test_settings_visibility_is_owned_by_the_tab_controller](../../tests/test_navigation_settings_ui.py#L394) (Zeile 394)
- [test_memory_is_the_first_settings_category](../../tests/test_navigation_settings_ui.py#L409) (Zeile 409)
- [test_the_memory_profile_is_only_fetched_when_the_settings_open](../../tests/test_navigation_settings_ui.py#L471) (Zeile 471)
- [test_memory_selection_has_explicit_add_and_correct_flows](../../tests/test_navigation_settings_ui.py#L489) (Zeile 489)
- [test_selecting_answer_text_offers_asking_about_it](../../tests/test_navigation_settings_ui.py#L510) (Zeile 510)
- [test_logout_clears_the_loaded_run_and_aborts_active_streams](../../tests/test_navigation_settings_ui.py#L542) (Zeile 542)
- [test_watch_change_surfaces_use_tint_without_a_left_rail](../../tests/test_navigation_settings_ui.py#L581) (Zeile 581)
- [test_watch_requests_cannot_repopulate_account_state_after_logout](../../tests/test_navigation_settings_ui.py#L592) (Zeile 592)

</details>

<a id="test-onboarding-gates-py"></a>

## test_onboarding_gates.py

**Quelle:** [tests/test_onboarding_gates.py](../../tests/test_onboarding_gates.py) · **Bereiche:** Authentifizierung, Frontend, Onboarding.

**Ebene:** Quelltextverträge plus Konfigurationsassertion.

**Lauf:** 7 bestanden.

**Geprüftes Verhalten:** Unverifizierte Session mit Banner/Resend/Recheck, Draft-Wiederherstellung über Verify-Link, keine Account-Existenzprobe mit eingegebenem Passwort, Follow-ups ohne Pro-Gate, mindestens zehn Free-Runs und Watch-Nudge mit privaten wöchentlichen Changes-only-Defaults.

**Grenzen und Doubles:** Auth/Draft/Watch-Interaktion überwiegend nicht ausgeführt; Mindestkontingent ist direkte Config-Prüfung.

**Prüfauftrag für den Folgeaudit:** Resend-/Verify-Fehler und Konto-/Tabwechsel in Runtime-Dateien abgleichen.

**Direkte Codeverweise:** [app/api/routers/chat.py](../../app/api/routers/chat.py), [app/core/config.py](../../app/core/config.py), [static/css/components-input.css](../../static/css/components-input.css), [static/firebase.js](../../static/firebase.js), [static/js/app-init.js](../../static/js/app-init.js), [static/js/consensus-run.js](../../static/js/consensus-run.js), [static/js/email-verify.js](../../static/js/email-verify.js), [static/js/query-send.js](../../static/js/query-send.js), [static/js/watch.js](../../static/js/watch.js), [templates/index.html](../../templates/index.html).

<details>
<summary>7 Testdefinitionen und ihre Quellstellen</summary>

- [test_unverified_sessions_are_not_signed_out_anymore](../../tests/test_onboarding_gates.py#L30) (Zeile 30)
- [test_verification_banner_offers_resend_and_recheck](../../tests/test_onboarding_gates.py#L47) (Zeile 47)
- [test_verification_link_returns_to_the_app_with_the_typed_question](../../tests/test_onboarding_gates.py#L73) (Zeile 73)
- [test_registration_never_probes_account_existence_with_caller_credentials](../../tests/test_onboarding_gates.py#L99) (Zeile 99)
- [test_followups_are_no_longer_pro_gated](../../tests/test_onboarding_gates.py#L115) (Zeile 115)
- [test_free_daily_runs_allow_more_than_a_single_try](../../tests/test_onboarding_gates.py#L132) (Zeile 132)
- [test_watch_nudge_starts_a_watch_directly_and_says_when_it_writes](../../tests/test_onboarding_gates.py#L142) (Zeile 142)

</details>

<a id="test-phase4-frontend-py"></a>

## test_phase4_frontend.py

**Quelle:** [tests/test_phase4_frontend.py](../../tests/test_phase4_frontend.py) · **Bereiche:** Authentifizierung, Frontend, Nebenläufigkeit, Watch.

**Ebene:** Quelltextverträge.

**Lauf:** 14 bestanden.

**Geprüftes Verhalten:** UTC-Usage-Refresh, Auth-/View-Generationen, sichtbare/deduplizierte Bookmarkfehler und serielle Writes, Share-Abbruch/Epochs, Fan-out-Fehler/Mindestmodelle nach Attachmentfilter, Tier-Recovery, Auth-Watchdog und Watch-Rollback. Binder-Eindeutigkeit, Retry und Login-Dialog-ARIA/Fokus-Code.

**Grenzen und Doubles:** Statische Strukturprüfungen; keine Runtime-Rennen oder tatsächlich geprüfte Fokusfalle. Nicht mit gleichnamiger E2E-Datei verwechseln.

**Prüfauftrag für den Folgeaudit:** Gleiche Verträge mit JS-race- und E2E-Phase4-Tests abgleichen.

**Direkte Codeverweise:** [static/app-ui.js](../../static/app-ui.js), [static/firebase.js](../../static/firebase.js), [static/js/app-bootstrap.js](../../static/js/app-bootstrap.js), [static/js/app-init.js](../../static/js/app-init.js), [static/js/auth-bootstrap.js](../../static/js/auth-bootstrap.js), [static/js/query-send.js](../../static/js/query-send.js), [static/js/share-dialog.js](../../static/js/share-dialog.js), [static/js/watch.js](../../static/js/watch.js), [templates/index.html](../../templates/index.html), [templates/landing.html](../../templates/landing.html).

**Direkte Testhelfer:** [tests/frontend_order.py](../../tests/frontend_order.py).

<details>
<summary>14 Testdefinitionen und ihre Quellstellen</summary>

- [test_usage_countdown_tracks_utc_midnight_and_refreshes_server_state](../../tests/test_phase4_frontend.py#L27) (Zeile 27)
- [test_bookmark_writes_and_views_are_bound_to_auth_and_intent_generations](../../tests/test_phase4_frontend.py#L39) (Zeile 39)
- [test_bookmark_save_failures_are_visible_and_deduplicated](../../tests/test_phase4_frontend.py#L54) (Zeile 54)
- [test_bookmark_model_and_consensus_writes_are_serialized_per_saved_run](../../tests/test_phase4_frontend.py#L74) (Zeile 74)
- [test_share_requests_use_auth_snapshots_abort_controllers_and_view_epochs](../../tests/test_phase4_frontend.py#L93) (Zeile 93)
- [test_complete_model_failure_is_an_error_and_marker_legend_is_not_cleared](../../tests/test_phase4_frontend.py#L104) (Zeile 104)
- [test_minimum_model_count_is_rechecked_after_attachment_filter_before_usage](../../tests/test_phase4_frontend.py#L115) (Zeile 115)
- [test_usage_snapshot_can_recover_pro_tier_after_status_failure](../../tests/test_phase4_frontend.py#L127) (Zeile 127)
- [test_auth_bootstrap_watchdog_precedes_firebase_and_clears_stale_skeletons](../../tests/test_phase4_frontend.py#L142) (Zeile 142)
- [test_watch_modal_route_and_brief_state_have_deterministic_rollback_contracts](../../tests/test_phase4_frontend.py#L154) (Zeile 154)
- [test_bookmark_restore_uses_owned_run_state_and_token_wait_is_fenced](../../tests/test_phase4_frontend.py#L170) (Zeile 170)
- [test_bookmark_load_failure_has_a_visible_retry_state](../../tests/test_phase4_frontend.py#L185) (Zeile 185)
- [test_account_popup_and_settings_controls_have_exactly_one_binder](../../tests/test_phase4_frontend.py#L194) (Zeile 194)
- [test_login_dialog_accessibility_and_current_landing_marker_vocabulary](../../tests/test_phase4_frontend.py#L209) (Zeile 209)

</details>

<a id="test-phase5-operations-py"></a>

## test_phase5_operations.py

**Quelle:** [tests/test_phase5_operations.py](../../tests/test_phase5_operations.py) · **Bereiche:** Fehlerdiagnostik, Persistenz, Runtime, Watch.

**Ebene:** Gemischt: Services mit DB-/HTTP-Doubles, Thread-/Async-Tests und Deployment-Quelltextverträge.

**Lauf:** 32 bestanden.

**Geprüftes Verhalten:** Bookmark-Count/Bytes/Merge/Löschung/Transaktionsretry, Account-Tombstones, Feedback-/Follow-Resendbudgets und rungebundene Votes/Expiry. Favicon-Singleflight/LRU/Fehler/Capacity und aktiver Eventloop, Correlation/Metriken/Redaktion, Provider-Timeout und Disconnect als cancelled, begrenzte Due-Brief-Query und Index-/Dependency-Verträge.

**Grenzen und Doubles:** Threads/Async-Verhalten lokal real, externe DB/Fetch/Provider ersetzt. Kein Last-/Deploymenttest; Subprozess testet Routerimport nach asyncio.run.

**Prüfauftrag für den Folgeaudit:** Mehrprozess-Budgets, globale Cachegrenzen und tatsächliche Worker-/Transportabbrüche abgleichen.

**Direkte Codeverweise:** [app/api/routers/chat.py](../../app/api/routers/chat.py), [app/api/routers/pages.py](../../app/api/routers/pages.py), [app/api/routers/topics.py](../../app/api/routers/topics.py), [app/core/observability.py](../../app/core/observability.py), [app/core/rate_limit.py](../../app/core/rate_limit.py), [app/services/favicons.py](../../app/services/favicons.py), [app/services/follow_challenges.py](../../app/services/follow_challenges.py), [app/services/llm/consensus_engine.py](../../app/services/llm/consensus_engine.py), [app/services/llm/engines.py](../../app/services/llm/engines.py), [app/services/llm/provider_runtime.py](../../app/services/llm/provider_runtime.py), [app/services/llm/provider_transport.py](../../app/services/llm/provider_transport.py), [app/services/persistence_guard.py](../../app/services/persistence_guard.py), [app/services/watch_brief.py](../../app/services/watch_brief.py).

<details>
<summary>25 Testdefinitionen und ihre Quellstellen</summary>

- [test_bookmark_quota_counts_merges_and_rejects_oversize](../../tests/test_phase5_operations.py#L160) (Zeile 160)
- [test_persistence_transactions_have_a_contention_retry_budget](../../tests/test_phase5_operations.py#L193) (Zeile 193)
- [test_bookmark_quota_accepts_legacy_owner_above_the_old_cap](../../tests/test_phase5_operations.py#L215) (Zeile 215)
- [test_bookmark_delete_updates_quota_with_firestore_transaction_contract](../../tests/test_phase5_operations.py#L234) (Zeile 234)
- [test_account_deletion_tombstone_fences_normal_bookmark_delete](../../tests/test_phase5_operations.py#L253) (Zeile 253)
- [test_account_deletion_tombstone_fences_owner_persistence](../../tests/test_phase5_operations.py#L271) (Zeile 271)
- [test_feedback_cooldown_and_daily_limit_are_persistent](../../tests/test_phase5_operations.py#L315) (Zeile 315)
- [test_vote_is_run_bound_and_exactly_once](../../tests/test_phase5_operations.py#L334) (Zeile 334)
- [test_vote_expiry_is_fail_closed](../../tests/test_phase5_operations.py#L365) (Zeile 365)
- [test_follow_confirmation_has_persistent_resend_and_recipient_budgets](../../tests/test_phase5_operations.py#L393) (Zeile 393)
- [test_favicon_proxy_single_flights_and_uses_lru](../../tests/test_phase5_operations.py#L411) (Zeile 411)
- [test_favicon_exception_releases_followers_and_allows_retry](../../tests/test_phase5_operations.py#L438) (Zeile 438)
- [test_topics_router_imports_after_asyncio_run_and_uses_the_active_loop](../../tests/test_phase5_operations.py#L464) (Zeile 464)
- [test_favicon_capacity_fallback_is_never_cached](../../tests/test_phase5_operations.py#L493) (Zeile 493)
- [test_favicon_unexpected_failure_returns_private_fallback_without_raw_log](../../tests/test_phase5_operations.py#L517) (Zeile 517)
- [test_invalid_vote_model_never_reaches_logs](../../tests/test_phase5_operations.py#L539) (Zeile 539)
- [test_correlation_header_metrics_and_log_redaction](../../tests/test_phase5_operations.py#L566) (Zeile 566)
- [test_provider_pipeline_metrics_classify_normalized_results_without_secrets](../../tests/test_phase5_operations.py#L611) (Zeile 611)
- [test_upstream_http_timeout_status_is_normalized_without_response_body](../../tests/test_phase5_operations.py#L642) (Zeile 642)
- [test_ask_metrics_classify_normalized_openrouter_timeouts](../../tests/test_phase5_operations.py#L657) (Zeile 657)
- [test_ask_disconnect_records_cancellation_not_success](../../tests/test_phase5_operations.py#L703) (Zeile 703)
- [test_cancelled_provider_metric_has_a_dedicated_counter](../../tests/test_phase5_operations.py#L772) (Zeile 772)
- [test_due_brief_query_filters_and_limits_in_firestore](../../tests/test_phase5_operations.py#L780) (Zeile 780)
- [test_phase5_frontend_vote_binding_and_deployment_contracts](../../tests/test_phase5_operations.py#L791) (Zeile 791)
- [test_benchmark_only_dependencies_are_not_in_production_requirements](../../tests/test_phase5_operations.py#L807) (Zeile 807)

</details>

<a id="test-phase6-architecture-py"></a>

## test_phase6_architecture.py

**Quelle:** [tests/test_phase6_architecture.py](../../tests/test_phase6_architecture.py) · **Bereiche:** Architektur, Frontend, Konsens und Unterschiede, Sicherheit.

**Ebene:** Gemischt: Pipeline-/CSP-Runtime und Quelltextarchitektur.

**Lauf:** 8 bestanden.

**Geprüftes Verhalten:** Validierte öffentliche Origin; neutrale Pipeline führt injizierten Fan-out/Synthese/Analyse aus und wählt ersten erfolgreichen Provider. Source-Verträge erzwingen Delegation/Frontend-State-Owner, externe Admin-Skripte, gemeinsame Visuals und entfernte alte DOM-IDs. Middleware prüft striktes Script-CSP für App/Admin.

**Grenzen und Doubles:** Pipelinefunktionen injiziert; Architektur-Scans sind Syntaxmuster. CSP-Header alleine beweisen keinen XSS-Schutz im Browser.

**Prüfauftrag für den Folgeaudit:** Tatsächliche Frontend-State-Schreibverstöße und CSP-Verhalten der gebauten App abgleichen.

**Direkte Codeverweise:** [app/api/routers/chat.py](../../app/api/routers/chat.py), [app/core/security.py](../../app/core/security.py), [app/core/site.py](../../app/core/site.py), [app/services/api_consensus_runner.py](../../app/services/api_consensus_runner.py), [app/services/consensus_pipeline.py](../../app/services/consensus_pipeline.py), [app/services/llm/consensus_engine.py](../../app/services/llm/consensus_engine.py), [app/services/topic_pipeline.py](../../app/services/topic_pipeline.py), [app/services/topic_runner.py](../../app/services/topic_runner.py), [app/services/watch_scheduler.py](../../app/services/watch_scheduler.py), [static/css/admin-benchmark.css](../../static/css/admin-benchmark.css), [static/css/components-consensus-insights.css](../../static/css/components-consensus-insights.css), [static/css/components-consensus-visuals.css](../../static/css/components-consensus-visuals.css), [static/css/landing.css](../../static/css/landing.css), [static/js/admin-benchmark.js](../../static/js/admin-benchmark.js), [static/js/admin-config.js](../../static/js/admin-config.js), [static/js/admin.js](../../static/js/admin.js), [static/js/app-state.js](../../static/js/app-state.js), [templates/admin.html](../../templates/admin.html), [templates/admin_benchmark.html](../../templates/admin_benchmark.html), [templates/index.html](../../templates/index.html), [templates/partials/admin_prompt_config.html](../../templates/partials/admin_prompt_config.html).

**Direkte Testhelfer:** [tests/frontend_order.py](../../tests/frontend_order.py).

<details>
<summary>8 Testdefinitionen und ihre Quellstellen</summary>

- [test_public_site_origin_is_neutral_validated_core_configuration](../../tests/test_phase6_architecture.py#L27) (Zeile 27)
- [test_neutral_pipeline_owns_fanout_synthesis_parsing_and_scoring](../../tests/test_phase6_architecture.py#L40) (Zeile 40)
- [test_neutral_pipeline_can_select_the_first_successful_provider_as_engine](../../tests/test_phase6_architecture.py#L76) (Zeile 76)
- [test_all_server_product_paths_delegate_to_neutral_pipeline](../../tests/test_phase6_architecture.py#L105) (Zeile 105)
- [test_cross_module_frontend_state_has_enforced_owners_and_no_direct_writers](../../tests/test_phase6_architecture.py#L122) (Zeile 122)
- [test_privileged_app_and_admin_templates_are_external_script_surfaces](../../tests/test_phase6_architecture.py#L142) (Zeile 142)
- [test_app_and_all_admin_pages_receive_strict_script_csp](../../tests/test_phase6_architecture.py#L184) (Zeile 184)
- [test_consensus_visuals_are_shared_and_dead_dom_contracts_are_gone](../../tests/test_phase6_architecture.py#L204) (Zeile 204)

</details>

<a id="test-plus-tier-py"></a>

## test_plus_tier.py

**Quelle:** [tests/test_plus_tier.py](../../tests/test_plus_tier.py) · **Bereiche:** Authentifizierung.

**Ebene:** Entitlements-/Konfigurationslogik und Security mit DB-Double.

**Lauf:** 34 bestanden.

**Geprüftes Verhalten:** Normalisierung inkl. Legacy/Bool/Fremdwerten, Tierordnung und Featureflags; relative Quoten-/Memory-/Watchgrenzen, kein Plus-Deep-Think, freie Watchmodelle und Adminswitch; sichere Fallbacks fehlender Konfigurationswerte; konfigurierbare/clamped Limits, Premiummodellabwehr, Anhänge ab Plus und gecachte Flags für gespeicherte Tiers.

**Grenzen und Doubles:** Viele Assertions vergleichen Konfigurationswerte untereinander; sie beweisen keine tatsächliche Endpoint-Durchsetzung oder reale Quotenbelastung.

**Prüfauftrag für den Folgeaudit:** Jede Entitlement-Grenze serverseitig und im Frontend mit den entsprechenden Router-/JS-Tests abgleichen.

**Direkte Codeverweise:** [app/core/config.py](../../app/core/config.py), [app/core/entitlements.py](../../app/core/entitlements.py), [app/core/security.py](../../app/core/security.py), [app/services/llm/attachments.py](../../app/services/llm/attachments.py), [app/services/llm/base.py](../../app/services/llm/base.py).

<details>
<summary>18 Testdefinitionen und ihre Quellstellen</summary>

- [test_normalize_tier](../../tests/test_plus_tier.py#L49) (Zeile 49)
- [test_unknown_tier_never_becomes_plus_or_pro](../../tests/test_plus_tier.py#L53) (Zeile 53)
- [test_tier_ordering](../../tests/test_plus_tier.py#L58) (Zeile 58)
- [test_plus_gets_the_features_but_not_the_expensive_models](../../tests/test_plus_tier.py#L67) (Zeile 67)
- [test_free_gets_nothing_and_pro_gets_everything](../../tests/test_plus_tier.py#L77) (Zeile 77)
- [test_plus_has_the_largest_run_quota](../../tests/test_plus_tier.py#L86) (Zeile 86)
- [test_plus_has_no_deep_think_quota](../../tests/test_plus_tier.py#L92) (Zeile 92)
- [test_plus_deep_search_limits_fall_back_to_free](../../tests/test_plus_tier.py#L97) (Zeile 97)
- [test_plus_sits_between_free_and_pro_for_memory](../../tests/test_plus_tier.py#L102) (Zeile 102)
- [test_plus_watch_limit_sits_between_free_and_pro](../../tests/test_plus_tier.py#L110) (Zeile 110)
- [test_plus_watches_run_on_the_free_models](../../tests/test_plus_tier.py#L118) (Zeile 118)
- [test_plus_daily_watch_interval_follows_the_admin_switch](../../tests/test_plus_tier.py#L124) (Zeile 124)
- [test_a_plus_limit_missing_from_the_config_falls_back_to_free_not_pro](../../tests/test_plus_tier.py#L141) (Zeile 141)
- [test_plus_limits_are_admin_configurable](../../tests/test_plus_tier.py#L151) (Zeile 151)
- [test_memory_plus_chars_is_clamped_between_free_and_pro](../../tests/test_plus_tier.py#L159) (Zeile 159)
- [test_plus_cannot_pick_a_premium_model](../../tests/test_plus_tier.py#L170) (Zeile 170)
- [test_attachments_open_at_plus](../../tests/test_plus_tier.py#L183) (Zeile 183)
- [test_tier_lookup_derives_all_three_flags](../../tests/test_plus_tier.py#L214) (Zeile 214)

</details>

<a id="test-pro-beta-and-copy-py"></a>

## test_pro_beta_and_copy.py

**Quelle:** [tests/test_pro_beta_and_copy.py](../../tests/test_pro_beta_and_copy.py) · **Bereiche:** Konten und Tarife, Onboarding, Öffentliche Seiten.

**Ebene:** Waitlist-Router mit Transaktions-Double und Quelltextverträge.

**Lauf:** 9 bestanden.

**Geprüftes Verhalten:** Idempotenter Pro-Beta-Antrag, bestehendes Pro abgelehnt, Tombstone verhindert Write. Early-access-Texte ohne Kauf-CTA, dynamische Kontingente, konsistente öffentliche Copy und Commit-/Repo-Footer.

**Grenzen und Doubles:** Waitlist-Transaktion nachgebildet; UI-/Copy-Prüfungen textuell. Kein echter E-Mail-/Beta-Freischaltungsablauf.

**Prüfauftrag für den Folgeaudit:** Parallel doppelte Anträge und Admin-Freischaltung separat abgleichen.

**Direkte Codeverweise:** [app/api/routers/users.py](../../app/api/routers/users.py), [app/core/rate_limit.py](../../app/core/rate_limit.py), [app/core/version.py](../../app/core/version.py), [app/services/persistence_guard.py](../../app/services/persistence_guard.py).

<details>
<summary>9 Testdefinitionen und ihre Quellstellen</summary>

- [test_pro_beta_request_is_idempotent_and_active_pro_is_rejected](../../tests/test_pro_beta_and_copy.py#L101) (Zeile 101)
- [test_pro_beta_request_is_fenced_during_account_deletion](../../tests/test_pro_beta_and_copy.py#L125) (Zeile 125)
- [test_access_information_explains_availability_and_sells_nothing](../../tests/test_pro_beta_and_copy.py#L142) (Zeile 142)
- [test_sidebar_link_explains_limits_instead_of_offering_an_upgrade](../../tests/test_pro_beta_and_copy.py#L159) (Zeile 159)
- [test_access_copy_is_in_about_and_app_without_a_landing_cost_section](../../tests/test_pro_beta_and_copy.py#L170) (Zeile 170)
- [test_no_page_claims_that_nothing_will_ever_be_for_sale](../../tests/test_pro_beta_and_copy.py#L185) (Zeile 185)
- [test_no_purchase_call_to_action_survives_anywhere_in_the_ui](../../tests/test_pro_beta_and_copy.py#L197) (Zeile 197)
- [test_user_visible_plan_copy_has_no_stale_literal_plan_values](../../tests/test_pro_beta_and_copy.py#L208) (Zeile 208)
- [test_footer_shows_the_running_commit_and_links_to_the_repository](../../tests/test_pro_beta_and_copy.py#L225) (Zeile 225)

</details>

<a id="test-prompt-config-py"></a>

## test_prompt_config.py

**Quelle:** [tests/test_prompt_config.py](../../tests/test_prompt_config.py) · **Bereiche:** Admin, Prompts.

**Ebene:** Router/Store und Runtime-Prompt-Integration mit Fake-DB.

**Lauf:** 19 bestanden.

**Geprüftes Verhalten:** Read-only Defaultabruf, revisionierte/auditierte Saves und Restore, Auth vor DB, strukturelle/Text-/Byte-/Timezone-Validierung. Gespeicherte Prompts erreichen Runtime samt dynamischem Kontext; zwei Threads konkurrieren um Revision, Cache-Refresh und fehlgeschlagene Aktivierung/Writes, Delegation-Legacy-Erhalt.

**Grenzen und Doubles:** DB-Transaktion nutzt lokales Lock; echte Mehrprozess-/Firestore-Konflikte nicht hier. Promptassertions messen Textaufbau, keine LLM-Wirkung.

**Prüfauftrag für den Folgeaudit:** Emulator-Prompttransaktionen und Browser-Adminformular abgleichen.

**Direkte Codeverweise:** [app/api/routers/admin.py](../../app/api/routers/admin.py), [app/core/rate_limit.py](../../app/core/rate_limit.py), [app/services/agent_runs.py](../../app/services/agent_runs.py), [app/services/llm/agent_client.py](../../app/services/llm/agent_client.py), [app/services/llm/base.py](../../app/services/llm/base.py), [app/services/llm/consensus_engine.py](../../app/services/llm/consensus_engine.py), [app/services/prompt_config.py](../../app/services/prompt_config.py).

<details>
<summary>7 Testdefinitionen und ihre Quellstellen</summary>

- [test_admin_read_is_write_free_and_save_is_versioned_and_audited](../../tests/test_prompt_config.py#L94) (Zeile 94)
- [test_admin_access_is_checked_before_config_reads_or_writes](../../tests/test_prompt_config.py#L117) (Zeile 117)
- [test_invalid_config_is_rejected_without_writes](../../tests/test_prompt_config.py#L136) (Zeile 136)
- [test_runtime_uses_saved_prompts_and_keeps_dynamic_context](../../tests/test_prompt_config.py#L143) (Zeile 143)
- [test_two_workers_cannot_overwrite_the_same_revision](../../tests/test_prompt_config.py#L162) (Zeile 162)
- [test_cache_refreshes_other_workers_and_failed_writes_never_activate](../../tests/test_prompt_config.py#L177) (Zeile 177)
- [test_delegation_limits_are_validated_and_legacy_saves_preserve_them](../../tests/test_prompt_config.py#L197) (Zeile 197)

</details>

<a id="test-prompt-date-context-py"></a>

## test_prompt_date_context.py

**Quelle:** [tests/test_prompt_date_context.py](../../tests/test_prompt_date_context.py) · **Bereiche:** Agent, Kontext, Prompts.

**Ebene:** Prompt-/Agent-Store-Integration mit Fake-Uhr/Store.

**Lauf:** 3 bestanden.

**Geprüftes Verhalten:** Gemeinsames lokales Datum/Uhrzeit/Berlin-DST-Offset über Antwortstufen an zwei Zeitpunkten; Agent-Follow-up aktualisiert Modell/Datum und bewahrt historische Assistant-Antwort.

**Grenzen und Doubles:** Feste Uhrzeitpunkte; keine gesamte DST-Übergangsmatrix oder echte Provider-Ausführung.

**Prüfauftrag für den Folgeaudit:** Andere gespeicherte Zeitzonen und Requestdauer über Tageswechsel abgleichen.

**Direkte Codeverweise:** [app/services/agent_runs.py](../../app/services/agent_runs.py), [app/services/llm/agent_client.py](../../app/services/llm/agent_client.py), [app/services/llm/base.py](../../app/services/llm/base.py), [app/services/llm/consensus_engine.py](../../app/services/llm/consensus_engine.py), [app/services/llm/engines.py](../../app/services/llm/engines.py).

**Direkte Testhelfer:** [tests/test_agent_runs.py](../../tests/test_agent_runs.py).

<details>
<summary>2 Testdefinitionen und ihre Quellstellen</summary>

- [test_all_answer_stages_share_explicit_local_date_and_dst_offset](../../tests/test_prompt_date_context.py#L30) (Zeile 30)
- [test_agent_followup_refreshes_clock_and_model_without_rewriting_history](../../tests/test_prompt_date_context.py#L43) (Zeile 43)

</details>

<a id="test-provider-registry-py"></a>

## test_provider_registry.py

**Quelle:** [tests/test_provider_registry.py](../../tests/test_provider_registry.py) · **Bereiche:** Architektur, Modelle und Provider.

**Ebene:** Daten-/Consumer-/Prompt-Unit-Tests.

**Lauf:** 16 bestanden.

**Geprüftes Verhalten:** Alle Registry-Familien in abgeleiteten Maps/Sets/Aliasobjekten, Free-/Pro-/Attachment-Policies, Transport-/Share-/Chat-/Topic-/Watch-/Router-Konsumenten und Judge-Vokabular. Prompts variieren mit Antwortanzahl; IDs/Labels sowie leere/exkludierte Antworten normalisieren.

**Grenzen und Doubles:** Konsistenz überwiegend gegen dieselbe Registry; beweist Vollständigkeit relativ zur Registry, keine externe Vollständigkeit. Schleifen/subTests sind keine zusätzlichen Runnerfälle.

**Prüfauftrag für den Folgeaudit:** Neue Familie durch vollständigen Lauf/Persistenz/Frontend-Restore führen; unabhängige Produktanforderungen abgleichen.

**Direkte Codeverweise:** [app/api/routers/chat.py](../../app/api/routers/chat.py), [app/core/config.py](../../app/core/config.py), [app/services/chat_store.py](../../app/services/chat_store.py), [app/services/llm/consensus_engine.py](../../app/services/llm/consensus_engine.py), [app/services/llm/engines.py](../../app/services/llm/engines.py), [app/services/llm/provider_transport.py](../../app/services/llm/provider_transport.py), [app/services/llm/resolve_engine.py](../../app/services/llm/resolve_engine.py), [app/services/opinion_map.py](../../app/services/opinion_map.py), [app/services/share_snapshots.py](../../app/services/share_snapshots.py), [app/services/topics.py](../../app/services/topics.py), [app/services/watch_scheduler.py](../../app/services/watch_scheduler.py).

<details>
<summary>16 Testdefinitionen und ihre Quellstellen</summary>

- [RegistryCoverageTests::test_derived_model_maps_cover_every_family](../../tests/test_provider_registry.py#L25) (Zeile 25)
- [RegistryCoverageTests::test_allowed_model_aliases_are_the_registry_sets](../../tests/test_provider_registry.py#L41) (Zeile 41)
- [RegistryCoverageTests::test_every_family_has_both_consensus_aliases](../../tests/test_provider_registry.py#L58) (Zeile 58)
- [RegistryCoverageTests::test_base_model_is_free_and_pro_model_is_premium](../../tests/test_provider_registry.py#L72) (Zeile 72)
- [RegistryCoverageTests::test_model_configs_resolve_every_allowed_model](../../tests/test_provider_registry.py#L80) (Zeile 80)
- [RegistryCoverageTests::test_kimi_and_glm_request_and_attachment_policies_are_data](../../tests/test_provider_registry.py#L89) (Zeile 89)
- [RegistryCoverageTests::test_meta_is_the_ninth_family_with_muse_as_its_product_name](../../tests/test_provider_registry.py#L105) (Zeile 105)
- [ConsumerCoverageTests::test_transport_order_and_labels_come_from_the_registry](../../tests/test_provider_registry.py#L128) (Zeile 128)
- [ConsumerCoverageTests::test_engine_model_maps_cover_every_family](../../tests/test_provider_registry.py#L132) (Zeile 132)
- [ConsumerCoverageTests::test_product_surfaces_cover_every_family](../../tests/test_provider_registry.py#L136) (Zeile 136)
- [ConsumerCoverageTests::test_ask_endpoints_and_judge_vocabulary_cover_every_family](../../tests/test_provider_registry.py#L145) (Zeile 145)
- [ConsumerCoverageTests::test_preference_orders_stay_inside_the_registry](../../tests/test_provider_registry.py#L176) (Zeile 176)
- [PipelineIsFamilyCountAgnosticTests::test_consensus_prompt_grows_and_shrinks_with_the_answers](../../tests/test_provider_registry.py#L189) (Zeile 189)
- [PipelineIsFamilyCountAgnosticTests::test_differences_prompt_anonymizes_any_number_of_families](../../tests/test_provider_registry.py#L198) (Zeile 198)
- [PipelineIsFamilyCountAgnosticTests::test_answers_may_be_keyed_by_family_id_or_display_name](../../tests/test_provider_registry.py#L207) (Zeile 207)
- [PipelineIsFamilyCountAgnosticTests::test_empty_and_excluded_answers_drop_out](../../tests/test_provider_registry.py#L213) (Zeile 213)

</details>

<a id="test-provider-response-errors-py"></a>

## test_provider_response_errors.py

**Quelle:** [tests/test_provider_response_errors.py](../../tests/test_provider_response_errors.py) · **Bereiche:** Datenschutz, Modelle und Provider, Streaming und Wiederherstellung.

**Ebene:** Adapter/Fan-out mit HTTP-Response-Doubles.

**Lauf:** 38 bestanden.

**Geprüftes Verhalten:** Unterscheidet normale Texte über Fehler von tatsächlichen Transportfehlern; JSON und SSE mit HTTP-200-Fehlerbody klassifizieren numerische/ungültige Codes, entfernen Teiltext/Quellen und redigieren Upstream-Inhalt.

**Grenzen und Doubles:** HTTP-Antworten und Streams konstruiert, kein Netz. Assertions zum Ergebnis/Log belegen nicht automatisch alle Retry-/Requestanzahlen.

**Prüfauftrag für den Folgeaudit:** Gemischte fehlerhafte SSE-Pakete und Retry-Verhalten in streaming/runtime-Dateien abgleichen.

**Direkte Codeverweise:** [app/services/llm/engines.py](../../app/services/llm/engines.py), [app/services/llm/provider_transport.py](../../app/services/llm/provider_transport.py), [app/services/llm/streaming.py](../../app/services/llm/streaming.py).

<details>
<summary>3 Testdefinitionen und ihre Quellstellen</summary>

- [test_fanout_distinguishes_answer_text_from_transport_errors](../../tests/test_provider_response_errors.py#L19) (Zeile 19)
- [test_body_error_preserves_status_without_content_or_retry](../../tests/test_provider_response_errors.py#L55) (Zeile 55)
- [test_untrusted_status_is_not_logged_or_mistaken_for_http_status](../../tests/test_provider_response_errors.py#L73) (Zeile 73)

</details>

<a id="test-provider-timeouts-py"></a>

## test_provider_timeouts.py

**Quelle:** [tests/test_provider_timeouts.py](../../tests/test_provider_timeouts.py) · **Bereiche:** Modelle und Provider, Runtime, Streaming und Wiederherstellung.

**Ebene:** Echte Adapter mit requests-/SDK-Doubles plus AST-Verträge.

**Lauf:** 58 bestanden.

**Geprüftes Verhalten:** Providerübergreifend 408/504/ReadTimeout in JSON/Streaming als provider_timeout ohne Body-Leak; feste HTTP-/SDK-Timeouts, deaktivierte SDK-Retries und zentrale Clientfactory. AST sucht requests-Aufrufe ohne Timeout.

**Grenzen und Doubles:** Echt sind die Adapterfunktionen; Netzwerk und SDK-Konstruktion sind gemockt. Statische Timeout-Präsenz beweist keine tatsächliche Deadline unter Last.

**Prüfauftrag für den Folgeaudit:** Abbruch/Langläufer über cancellable transport und Agent-Reliability separat abgleichen.

**Direkte Codeverweise:** [app/core/config.py](../../app/core/config.py), [app/services/llm/engines.py](../../app/services/llm/engines.py), [app/services/llm/provider_runtime.py](../../app/services/llm/provider_runtime.py), [app/services/llm/streaming.py](../../app/services/llm/streaming.py).

<details>
<summary>8 Testdefinitionen und ihre Quellstellen</summary>

- [test_real_provider_adapters_classify_http_timeout_status_without_body_leak](../../tests/test_provider_timeouts.py#L42) (Zeile 42)
- [test_real_provider_adapters_preserve_read_timeout_type](../../tests/test_provider_timeouts.py#L60) (Zeile 60)
- [test_real_streaming_adapters_classify_http_timeout_status](../../tests/test_provider_timeouts.py#L76) (Zeile 76)
- [test_real_streaming_adapters_preserve_read_timeout_type](../../tests/test_provider_timeouts.py#L94) (Zeile 94)
- [test_query_model_sets_timeout](../../tests/test_provider_timeouts.py#L106) (Zeile 106)
- [test_openai_compatible_clients_disable_sdk_retries_and_set_timeout](../../tests/test_provider_timeouts.py#L118) (Zeile 118)
- [test_provider_modules_use_only_the_central_openai_client_factory](../../tests/test_provider_timeouts.py#L133) (Zeile 133)
- [test_all_requests_calls_set_timeout](../../tests/test_provider_timeouts.py#L209) (Zeile 209)

</details>

<a id="test-public-citation-cleanup-py"></a>

## test_public_citation_cleanup.py

**Quelle:** [tests/test_public_citation_cleanup.py](../../tests/test_public_citation_cleanup.py) · **Bereiche:** Quellenprüfung, Öffentliche Seiten.

**Ebene:** Renderer-/Citation-Unit-Tests.

**Lauf:** 5 bestanden.

**Geprüftes Verhalten:** Legacy-Referenzen nummerieren/deduplizieren, echte Wörter/deskriptive Links/unbekannte Referenzen/Code erhalten, kopierte Citation an exakte Share-Version binden und Redirecttokens auslassen; Plaintext-Snippet bereinigen.

**Grenzen und Doubles:** Feste Markdown-Beispiele; kein Browser oder externe Linkprüfung.

**Prüfauftrag für den Folgeaudit:** Verschachteltes/fehlerhaftes Markdown und XSS mit public_markdown-/Share-Tests abgleichen.

**Direkte Codeverweise:** [app/services/public_markdown.py](../../app/services/public_markdown.py), [app/services/share_snapshots.py](../../app/services/share_snapshots.py).

<details>
<summary>5 Testdefinitionen und ihre Quellstellen</summary>

- [test_legacy_citations_are_numbered_without_removing_actual_words](../../tests/test_public_citation_cleanup.py#L11) (Zeile 11)
- [test_duplicate_reference_ids_are_collapsed_but_distinct_sources_survive](../../tests/test_public_citation_cleanup.py#L25) (Zeile 25)
- [test_descriptive_links_unknown_references_and_code_are_preserved](../../tests/test_public_citation_cleanup.py#L31) (Zeile 31)
- [test_copied_citation_points_to_exact_version_without_redirect_tokens](../../tests/test_public_citation_cleanup.py#L43) (Zeile 43)
- [test_search_snippet_omits_known_citation_labels_but_keeps_real_mentions](../../tests/test_public_citation_cleanup.py#L55) (Zeile 55)

</details>

<a id="test-public-design-system-py"></a>

## test_public_design_system.py

**Quelle:** [tests/test_public_design_system.py](../../tests/test_public_design_system.py) · **Bereiche:** Build und Betrieb, Responsive UI, Öffentliche Seiten.

**Ebene:** Quelltext- und Dateiverträge.

**Lauf:** 7 bestanden.

**Geprüftes Verhalten:** Gemeinsame Navigation/Footer/Tokens/Mockup, selbstgehostete Fonts samt Mindestgröße/Lizenz und keine Google-Font-Abhängigkeiten, gemeinsamer Math-Renderer, Watch-Header und vierter Produkt-Schritt auf Landingpage.

**Grenzen und Doubles:** Keine visuelle Darstellung/Layout-/Fontladeprüfung; Dateigröße beweist keine korrekte Schriftdatei.

**Prüfauftrag für den Folgeaudit:** Responsive/Accessibility/Math-Rendering mit Browser-Dateien abgleichen.

**Direkte Codeverweise:** [app/core/security.py](../../app/core/security.py), [static/css/landing.css](../../static/css/landing.css), [static/css/public-pages.css](../../static/css/public-pages.css), [static/css/public-tokens.css](../../static/css/public-tokens.css), [static/css/typography.css](../../static/css/typography.css), [static/css/variables.css](../../static/css/variables.css), [templates/consensus-engine.html](../../templates/consensus-engine.html), [templates/landing.html](../../templates/landing.html), [templates/partials/public_nav.html](../../templates/partials/public_nav.html), [templates/share.html](../../templates/share.html).

<details>
<summary>7 Testdefinitionen und ihre Quellstellen</summary>

- [test_public_pages_share_navigation_and_footer_partials](../../tests/test_public_design_system.py#L27) (Zeile 27)
- [test_public_styles_share_the_app_aligned_token_layer](../../tests/test_public_design_system.py#L34) (Zeile 34)
- [test_typography_is_self_hosted_and_shared_by_every_surface](../../tests/test_public_design_system.py#L72) (Zeile 72)
- [test_product_result_mockup_is_reused](../../tests/test_public_design_system.py#L107) (Zeile 107)
- [test_share_page_loads_the_common_math_renderer](../../tests/test_public_design_system.py#L114) (Zeile 114)
- [test_watch_header_keeps_intro_left_aligned_and_dates_visible](../../tests/test_public_design_system.py#L123) (Zeile 123)
- [test_landing_explains_consensus_watch_as_fourth_product_step](../../tests/test_public_design_system.py#L133) (Zeile 133)

</details>

<a id="test-publish-consensus-script-py"></a>

## test_publish_consensus_script.py

**Quelle:** [tests/test_publish_consensus_script.py](../../tests/test_publish_consensus_script.py) · **Bereiche:** Benachrichtigungen, Publisher.

**Ebene:** Script-Unit-/Ablauf-Integration mit HTTP/Telegram-Doubles und Workflow-Sourcevertrag.

**Lauf:** 13 bestanden.

**Geprüftes Verhalten:** Question/Textnormalisierung, explizite Frage ohne Topiccall, Run→Share→Watch→Index und Header, Capacityskip bleibt erfolgreich. Telegram-Payload/nichtfataler redigierter Fehler, Topic-Websearch/History/Prompt, Disagreement-Schwellen/missing data, ungeeignete Fragen, Titelretry, Disabled-Exit und Workflowcron/Secretname.

**Grenzen und Doubles:** Kein echter Scheduler, Provider oder Publish/Telegram; Workflow wird als Text geprüft.

**Prüfauftrag für den Folgeaudit:** Polling-/Netzwerkfehler, wiederholte Schedules und idempotente Veröffentlichung mit API/Standalone abgleichen.

**Direkte Codeverweise:** [app/services/publisher_config.py](../../app/services/publisher_config.py).

<details>
<summary>13 Testdefinitionen und ihre Quellstellen</summary>

- [test_response_output_text_and_question_validation](../../tests/test_publish_consensus_script.py#L18) (Zeile 18)
- [test_main_runs_publish_and_index_flow_without_topic_call](../../tests/test_publish_consensus_script.py#L36) (Zeile 36)
- [test_watch_capacity_skip_keeps_publisher_run_successful](../../tests/test_publish_consensus_script.py#L114) (Zeile 114)
- [test_telegram_notification_posts_question_and_share_url](../../tests/test_publish_consensus_script.py#L143) (Zeile 143)
- [test_telegram_failure_is_non_fatal_and_does_not_log_token](../../tests/test_publish_consensus_script.py#L185) (Zeile 185)
- [test_topic_selection_uses_web_search_and_recent_question_history](../../tests/test_publish_consensus_script.py#L205) (Zeile 205)
- [test_search_opportunity_rules_match_backend_product_fact](../../tests/test_publish_consensus_script.py#L246) (Zeile 246)
- [test_evaluate_disagreement_publishes_only_contested_runs](../../tests/test_publish_consensus_script.py#L251) (Zeile 251)
- [test_unanimous_run_is_not_published_but_reported](../../tests/test_publish_consensus_script.py#L285) (Zeile 285)
- [test_generated_topic_rejects_government_policy_queries](../../tests/test_publish_consensus_script.py#L324) (Zeile 324)
- [test_scheduled_publisher_runs_three_times_per_week](../../tests/test_publish_consensus_script.py#L340) (Zeile 340)
- [test_topic_selection_retries_a_long_multi_clause_title](../../tests/test_publish_consensus_script.py#L350) (Zeile 350)
- [test_disabled_publisher_exits_without_starting_a_run](../../tests/test_publish_consensus_script.py#L375) (Zeile 375)

</details>

<a id="test-publisher-config-py"></a>

## test_publisher_config.py

**Quelle:** [tests/test_publisher_config.py](../../tests/test_publisher_config.py) · **Bereiche:** Admin, Publisher.

**Ebene:** Config-Service mit kleiner Fake-DB.

**Lauf:** 4 bestanden.

**Geprüftes Verhalten:** Defaultpersistenz, Free-Watch-Profil/Capacity, normalisierte Save-/Actorfelder, Migration überholter Standardbriefs zur Disagreement-Strategie und Erhalt manuell editierten Briefs.

**Grenzen und Doubles:** Keine echte DB/Cachekonkurrenz; nicht der vollständige Publisherlauf.

**Prüfauftrag für den Folgeaudit:** Ungültige Configtypen und parallele Migration/Saves abgleichen.

**Direkte Codeverweise:** [app/services/publisher_config.py](../../app/services/publisher_config.py).

<details>
<summary>4 Testdefinitionen und ihre Quellstellen</summary>

- [test_default_publisher_configuration_is_persisted_and_free_pinned](../../tests/test_publisher_config.py#L48) (Zeile 48)
- [test_saved_publisher_configuration_is_normalized](../../tests/test_publisher_config.py#L63) (Zeile 63)
- [test_superseded_default_topic_briefs_migrate_to_the_disagreement_strategy](../../tests/test_publisher_config.py#L80) (Zeile 80)
- [test_hand_edited_topic_brief_is_never_overwritten](../../tests/test_publisher_config.py#L95) (Zeile 95)

</details>

<a id="test-publisher-standalone-py"></a>

## test_publisher_standalone.py

**Quelle:** [tests/test_publisher_standalone.py](../../tests/test_publisher_standalone.py) · **Bereiche:** Publisher, Testinfrastruktur.

**Ebene:** Echte Python-Subprozesse ohne Site-Packages mit HTTP-Doubles.

**Lauf:** 3 bestanden.

**Geprüftes Verhalten:** CLI als relativer/absoluter Pfad und Modul erreicht Konfigvalidierung ohne Backendpakete. Eingebettete Skripte prüfen Modell-/Keynormalisierung, OpenRouter-Header/Search/Reasoning/ZDR und direkten Question-Bypass. Echter __main__ durchläuft publish/skip/disabled, HTTP-Serialisierung, Idempotency-Key, Watch/Index und Summarydatei.

**Grenzen und Doubles:** Socket.connect explizit verboten, urlopen/http_json ersetzt. Interne Schleifen/subTests expandieren nicht zu zusätzlichen Pytestfällen; kein veröffentlichter Share.

**Prüfauftrag für den Folgeaudit:** Workflow-Umgebung und Fehler-/Pollingvarianten mit Publish-Script-/API-Dateien abgleichen.

**Direkte Codeverweise:** [scripts/publish_consensus.py](../../scripts/publish_consensus.py).

<details>
<summary>3 Testdefinitionen und ihre Quellstellen</summary>

- [PublisherStandaloneTests::test_cli_reaches_configuration_validation_without_packages](../../tests/test_publisher_standalone.py#L29) (Zeile 29)
- [PublisherStandaloneTests::test_topic_models_credentials_and_request_contract_without_packages](../../tests/test_publisher_standalone.py#L42) (Zeile 42)
- [PublisherStandaloneTests::test_scheduled_flow_without_packages_or_external_services](../../tests/test_publisher_standalone.py#L98) (Zeile 98)

</details>

<a id="test-rate-limit-py"></a>

## test_rate_limit.py

**Quelle:** [tests/test_rate_limit.py](../../tests/test_rate_limit.py) · **Bereiche:** Sicherheit.

**Ebene:** Rate-Key-/UID-Limiter-Funktionen.

**Lauf:** 8 bestanden.

**Geprüftes Verhalten:** IP-Schlüssel aus Socket/Proxyheader/Kette, getrennte Besucher hinter Proxy und leerer Headerfallback; API-Schlüssel wird gehasht statt im Bucket offengelegt; ungültiger Key fällt auf IP zurück; UIDlimit bleibt beim Wechsel des Keys bestehen.

**Grenzen und Doubles:** Künstliche Request-Scopes; kein realer vertrauenswürdiger Reverse-Proxy und kein verteilter Limiter.

**Prüfauftrag für den Folgeaudit:** Proxy-Vertrauensgrenze, manipulierte Header und Mehrprozesslimitierung im Deploymentkontext prüfen.

**Direkte Codeverweise:** [app/core/rate_limit.py](../../app/core/rate_limit.py).

<details>
<summary>8 Testdefinitionen und ihre Quellstellen</summary>

- [ClientIpKeyTests::test_without_proxy_header_uses_socket_address](../../tests/test_rate_limit.py#L31) (Zeile 31)
- [ClientIpKeyTests::test_render_proxy_header_yields_client_ip](../../tests/test_rate_limit.py#L35) (Zeile 35)
- [ClientIpKeyTests::test_render_proxy_chain_uses_first_client_ip](../../tests/test_rate_limit.py#L40) (Zeile 40)
- [ClientIpKeyTests::test_visitors_behind_the_same_proxy_get_distinct_buckets](../../tests/test_rate_limit.py#L48) (Zeile 48)
- [ClientIpKeyTests::test_empty_header_falls_back](../../tests/test_rate_limit.py#L57) (Zeile 57)
- [ClientIpKeyTests::test_api_key_bucket_hashes_secret](../../tests/test_rate_limit.py#L62) (Zeile 62)
- [ClientIpKeyTests::test_invalid_api_key_bucket_falls_back_to_ip](../../tests/test_rate_limit.py#L68) (Zeile 68)
- [ClientIpKeyTests::test_uid_limiter_cannot_be_bypassed_with_another_key](../../tests/test_rate_limit.py#L74) (Zeile 74)

</details>

<a id="test-reasoning-policy-py"></a>

## test_reasoning_policy.py

**Quelle:** [tests/test_reasoning_policy.py](../../tests/test_reasoning_policy.py) · **Bereiche:** Admin, Modelle und Provider.

**Ebene:** Konfigurations-/Payload-/Admin-Verträge mit Transport-/DB-Mocks.

**Lauf:** 18 bestanden.

**Geprüftes Verhalten:** Sparprofil und modellspezifische Ausnahmen über Antworten/Deep/Synthese/Helpers, ZDR/Provider-Bindung, Preview=Runtime ohne Mutation, ungültiges Admin-Payload vor Write, Legacy-Save, Reload-/Aktivierungsrollback und identische JSON-/Stream-Policy.

**Grenzen und Doubles:** Keine providerseitige Akzeptanz/Wirkung der Reasoning-Parameter; persistente API und Transport ersetzt.

**Prüfauftrag für den Folgeaudit:** Neue Modellfamilien und tatsächlich akzeptierte Provider-Payloads gesondert abgleichen.

**Direkte Codeverweise:** [app/api/routers/admin.py](../../app/api/routers/admin.py), [app/core/config.py](../../app/core/config.py), [app/services/llm/consensus_engine.py](../../app/services/llm/consensus_engine.py), [app/services/llm/engines.py](../../app/services/llm/engines.py).

<details>
<summary>7 Testdefinitionen und ihre Quellstellen</summary>

- [test_savings_reaches_answers_and_engine_aliases_without_breaking_protection](../../tests/test_reasoning_policy.py#L46) (Zeile 46)
- [test_disabled_helpers_stay_disabled_and_exception_restores_flow_specific_behavior](../../tests/test_reasoning_policy.py#L61) (Zeile 61)
- [test_saved_preview_matches_runtime_for_every_model_and_flow](../../tests/test_reasoning_policy.py#L71) (Zeile 71)
- [test_invalid_admin_policy_fails_before_persistence](../../tests/test_reasoning_policy.py#L91) (Zeile 91)
- [test_save_roundtrip_and_old_client_preserve_active_policy](../../tests/test_reasoning_policy.py#L101) (Zeile 101)
- [test_reload_and_activation_rollback_include_reasoning_policy](../../tests/test_reasoning_policy.py#L110) (Zeile 110)
- [test_stream_and_json_engine_send_same_capped_policy](../../tests/test_reasoning_policy.py#L124) (Zeile 124)

</details>

<a id="test-registration-security-py"></a>

## test_registration_security.py

**Quelle:** [tests/test_registration_security.py](../../tests/test_registration_security.py) · **Bereiche:** Authentifizierung.

**Ebene:** Registrierungsservice mit Firebase-/HTTP-Doubles.

**Lauf:** 4 bestanden.

**Geprüftes Verhalten:** Neues Konto erhält ein serverseitiges Passwort mit mindestens 48 Zeichen und abweichend vom Vergleichswert; vorhandenes Konto wird nicht neu angelegt; Passwort-Setup hat Connect-/Read-Timeouts und loggt bei Timeout keine E-Mail/Upstreamdetails; fehlender API-Key verhindert Setup.

**Grenzen und Doubles:** Die Passwortassertions belegen Länge und einen Vergleich, keine gemessene Entropie oder Eindeutigkeit vieler erzeugter Passwörter. Echte E-Mail-Zustellung und Firebase fehlen.

**Prüfauftrag für den Folgeaudit:** Create-Race und zusätzliche HTTP-Fehlerantworten sowie die tatsächliche Zufallsquelle im späteren Audit abgleichen.

**Direkte Codeverweise:** [app/services/registration.py](../../app/services/registration.py).

<details>
<summary>4 Testdefinitionen und ihre Quellstellen</summary>

- [test_new_user_gets_an_unguessable_server_side_password](../../tests/test_registration_security.py#L12) (Zeile 12)
- [test_existing_user_uses_the_same_mailbox_setup_path](../../tests/test_registration_security.py#L31) (Zeile 31)
- [test_password_setup_request_is_bounded_and_does_not_log_email](../../tests/test_registration_security.py#L44) (Zeile 44)
- [test_password_setup_requires_operator_configuration](../../tests/test_registration_security.py#L62) (Zeile 62)

</details>

<a id="test-request-body-limits-py"></a>

## test_request_body_limits.py

**Quelle:** [tests/test_request_body_limits.py](../../tests/test_request_body_limits.py) · **Bereiche:** Sicherheit, Streaming und Wiederherstellung.

**Ebene:** ASGI-Middleware mit kontrollierten Receive-/Send-Funktionen.

**Lauf:** 4 bestanden.

**Geprüftes Verhalten:** Zu große deklarierte und chunked Requests werden mit 413 vor der inneren App abgewiesen; exakt erlaubte Bytes werden einmal gesammelt wiedergegeben; ein verzögertes StreamingResponse liefert sein finales SSE-Ereignis ohne künstlichen Disconnect.

**Grenzen und Doubles:** Direkter ASGI-Aufruf ohne echten HTTP-Server/Proxy. Die gesammelte received-Liste dokumentiert die innere App; nicht pauschal mit sämtlichen Transport-Reads gleichsetzen.

**Prüfauftrag für den Folgeaudit:** Fehlende/ungültige Content-Length, Clientabbruch während Upload und reale Proxy-/Servergrenzen gegen weitere Tests abgleichen.

**Direkte Codeverweise:** [app/core/request_limits.py](../../app/core/request_limits.py).

<details>
<summary>4 Testdefinitionen und ihre Quellstellen</summary>

- [test_declared_oversized_body_is_rejected_without_reading_or_parsing](../../tests/test_request_body_limits.py#L39) (Zeile 39)
- [test_chunked_body_is_counted_across_receive_messages](../../tests/test_request_body_limits.py#L49) (Zeile 49)
- [test_exact_limit_body_is_replayed_once_to_the_application](../../tests/test_request_body_limits.py#L61) (Zeile 61)
- [test_replayed_body_does_not_synthesize_disconnect_for_delayed_stream](../../tests/test_request_body_limits.py#L75) (Zeile 75)

</details>

<a id="test-resolve-round-py"></a>

## test_resolve_round.py

**Quelle:** [tests/test_resolve_round.py](../../tests/test_resolve_round.py) · **Bereiche:** Bookmarks und Verlauf, Konsens und Unterschiede, Konten und Tarife.

**Ebene:** Resolve-Unit-/Routertests mit Engine-/DB-Doubles.

**Lauf:** 23 bestanden.

**Geprüftes Verhalten:** Positionsnormalisierung/Modelle/Aliase/Gegenpositionen/Caps, maintain/revise/standoff/mutual_revision/error, fehlender Key ohne Call. Auth und Plus-Gate, Usage-Zählung/Limit/normaler Run-Konflikt; nur Serverresultat auf exakt gebundener Bookmarkrevision persistiert, spätere Revision bleibt unangetastet.

**Grenzen und Doubles:** LLM-Entscheidungen konstruiert; Bookmark-DB ersetzt. Kein Browser und keine gemessene Wahrheit der Auflösung.

**Prüfauftrag für den Folgeaudit:** In-flight Bookmarkwechsel/Logout mit Frontendtests sowie konkurrierende Persistenz abgleichen.

**Direkte Codeverweise:** [app/api/routers/bookmarks.py](../../app/api/routers/bookmarks.py), [app/api/routers/chat.py](../../app/api/routers/chat.py), [app/core/config.py](../../app/core/config.py), [app/core/rate_limit.py](../../app/core/rate_limit.py), [app/services/llm/resolve_engine.py](../../app/services/llm/resolve_engine.py), [app/services/usage_repository.py](../../app/services/usage_repository.py).

**Direkte Testhelfer:** [tests/usage_test_support.py](../../tests/usage_test_support.py).

<details>
<summary>23 Testdefinitionen und ihre Quellstellen</summary>

- [TestNormalizeResolvePositions::test_valid_payload_is_normalized](../../tests/test_resolve_round.py#L43) (Zeile 43)
- [TestNormalizeResolvePositions::test_model_aliases_are_canonicalized](../../tests/test_resolve_round.py#L48) (Zeile 48)
- [TestNormalizeResolvePositions::test_unknown_models_are_dropped](../../tests/test_resolve_round.py#L54) (Zeile 54)
- [TestNormalizeResolvePositions::test_missing_claim_is_rejected](../../tests/test_resolve_round.py#L60) (Zeile 60)
- [TestNormalizeResolvePositions::test_single_position_is_rejected](../../tests/test_resolve_round.py#L64) (Zeile 64)
- [TestNormalizeResolvePositions::test_same_model_on_both_sides_is_rejected](../../tests/test_resolve_round.py#L68) (Zeile 68)
- [TestNormalizeResolvePositions::test_oversized_texts_are_clipped](../../tests/test_resolve_round.py#L74) (Zeile 74)
- [TestRunResolveRound::test_all_maintain_is_standoff](../../tests/test_resolve_round.py#L91) (Zeile 91)
- [TestRunResolveRound::test_one_revision_is_resolved](../../tests/test_resolve_round.py#L99) (Zeile 99)
- [TestRunResolveRound::test_all_revise_is_mutual_revision](../../tests/test_resolve_round.py#L109) (Zeile 109)
- [TestRunResolveRound::test_provider_errors_do_not_break_the_round](../../tests/test_resolve_round.py#L115) (Zeile 115)
- [TestRunResolveRound::test_all_failures_yield_error_outcome](../../tests/test_resolve_round.py#L126) (Zeile 126)
- [TestRunResolveRound::test_invalid_decision_counts_as_error](../../tests/test_resolve_round.py#L132) (Zeile 132)
- [TestRunResolveRound::test_missing_shared_key_skips_all_engine_calls](../../tests/test_resolve_round.py#L138) (Zeile 138)
- [test_resolve_requires_auth](../../tests/test_resolve_round.py#L225) (Zeile 225)
- [test_resolve_is_refused_below_plus](../../tests/test_resolve_round.py#L231) (Zeile 231)
- [test_resolve_is_open_to_plus](../../tests/test_resolve_round.py#L241) (Zeile 241)
- [test_resolve_rejects_invalid_positions](../../tests/test_resolve_round.py#L257) (Zeile 257)
- [test_resolve_counts_usage_and_returns_result](../../tests/test_resolve_round.py#L268) (Zeile 268)
- [test_resolve_rejects_a_key_reserved_for_a_normal_consensus](../../tests/test_resolve_round.py#L293) (Zeile 293)
- [test_resolve_blocks_when_usage_limit_reached](../../tests/test_resolve_round.py#L326) (Zeile 326)
- [test_resolve_persists_only_the_server_result_on_the_bound_bookmark_revision](../../tests/test_resolve_round.py#L344) (Zeile 344)
- [test_resolve_does_not_persist_after_the_bookmark_revision_advanced](../../tests/test_resolve_round.py#L400) (Zeile 400)

</details>

<a id="test-router-event-loop-contract-py"></a>

## test_router_event_loop_contract.py

**Quelle:** [tests/test_router_event_loop_contract.py](../../tests/test_router_event_loop_contract.py) · **Bereiche:** Sicherheit.

**Ebene:** AST-Vertrag plus ASGI-Nebenläufigkeit.

**Lauf:** 2 bestanden.

**Geprüftes Verhalten:** AST scannt async Routerhandler auf asynchrone Arbeit; zwei /prepare-Requests mit blockierendem Tier-Double treffen gleichzeitig im Threadpool ein und liefern 200.

**Grenzen und Doubles:** Vorhandenes await beweist nicht die Abwesenheit sämtlicher blockierender Aufrufe. Der dynamische Test betrifft nur /prepare und nutzt ASGITransport ohne Server.

**Prüfauftrag für den Folgeaudit:** Weitere Router mit blockierenden SDK-Aufrufen und tatsächliche Belastung des Threadpools prüfen.

**Direkte Codeverweise:** [app/api/routers/chat.py](../../app/api/routers/chat.py), [main.py](../../main.py).

<details>
<summary>2 Testdefinitionen und ihre Quellstellen</summary>

- [test_async_route_handlers_have_real_async_work](../../tests/test_router_event_loop_contract.py#L28) (Zeile 28)
- [test_prepare_firestore_bundle_does_not_serialize_the_event_loop](../../tests/test_router_event_loop_contract.py#L47) (Zeile 47)

</details>

<a id="test-run-usage-endpoints-py"></a>

## test_run_usage_endpoints.py

**Quelle:** [tests/test_run_usage_endpoints.py](../../tests/test_run_usage_endpoints.py) · **Bereiche:** API, Konsens und Unterschiede, Konten und Tarife.

**Ebene:** Router-Integration mit FakeFirestore und Provider-/Engine-Doubles.

**Lauf:** 11 bestanden.

**Geprüftes Verhalten:** Prepare plus parallele Modelle verbrauchen einen Run; identische Operation hat einen Gewinner, Konsens keinen zweiten Charge. Usage-Snapshot/Release, fehlender Key vor Provider, strukturierte 503 bei Contention, Deep-/Total-Zähler, Payloadkonflikte ohne zweiten Start und zuvor vorbereiteter letzter Slot.

**Grenzen und Doubles:** Nebenläufige Requests lokal, Repository nutzt sperrenden Fake; Provider wird nicht kontaktiert.

**Prüfauftrag für den Folgeaudit:** Echte Firestore-Contention und Abbruch nach Autorisierung mit E2E-Transaktionen abgleichen.

**Direkte Codeverweise:** [app/api/routers/chat.py](../../app/api/routers/chat.py), [app/api/routers/users.py](../../app/api/routers/users.py), [app/core/config.py](../../app/core/config.py), [app/core/rate_limit.py](../../app/core/rate_limit.py), [app/services/usage_repository.py](../../app/services/usage_repository.py).

**Direkte Testhelfer:** [tests/usage_test_support.py](../../tests/usage_test_support.py).

<details>
<summary>9 Testdefinitionen und ihre Quellstellen</summary>

- [test_prepare_and_parallel_models_consume_exactly_one_run](../../tests/test_run_usage_endpoints.py#L88) (Zeile 88)
- [test_parallel_same_provider_operation_runs_only_once](../../tests/test_run_usage_endpoints.py#L119) (Zeile 119)
- [test_consensus_reuses_consumed_run_without_second_charge](../../tests/test_run_usage_endpoints.py#L142) (Zeile 142)
- [test_usage_endpoint_reads_persistent_snapshot_and_release_frees_reservation](../../tests/test_run_usage_endpoints.py#L173) (Zeile 173)
- [test_requests_without_run_key_are_rejected_before_provider_call](../../tests/test_run_usage_endpoints.py#L199) (Zeile 199)
- [test_exhausted_firestore_contention_returns_structured_503](../../tests/test_run_usage_endpoints.py#L214) (Zeile 214)
- [test_deep_think_counts_once_total_and_once_in_deep_quota](../../tests/test_run_usage_endpoints.py#L226) (Zeile 226)
- [test_authorization_rejections_never_start_a_second_provider](../../tests/test_run_usage_endpoints.py#L245) (Zeile 245)
- [test_prepared_run_can_finish_when_daily_limit_is_exhausted](../../tests/test_run_usage_endpoints.py#L267) (Zeile 267)

</details>

<a id="test-run-usage-repository-py"></a>

## test_run_usage_repository.py

**Quelle:** [tests/test_run_usage_repository.py](../../tests/test_run_usage_repository.py) · **Bereiche:** Konten und Tarife, Persistenz.

**Ebene:** Repository-/Transaktionsverträge mit FakeFirestore und Threads.

**Lauf:** 25 bestanden.

**Geprüftes Verhalten:** Reserve/Consume/Release/Read und integerbasierte Limits, parallele eindeutige/identische Keys, Owner/Kind/Fingerprint-Bindung, read-only Status, Kontextbindung, Tombstone-Fencing, Expiry/UTC-Tag und getrennte Deep-/Total-Zähler. Operation-Claims deduplizieren und binden Payload.

**Grenzen und Doubles:** Lockbasierter Fake; SDK-Decorator-Pfad nur instrumentiert. Tatsächliche Firestore-Retries und Mehrprozess-Atomizität hier nicht ausgeführt.

**Prüfauftrag für den Folgeaudit:** Emulator-Reservation-/Claim-Rennen und Counter-Recovery bei Prozessabbruch abgleichen.

**Direkte Codeverweise:** [app/core/config.py](../../app/core/config.py), [app/services/persistence_guard.py](../../app/services/persistence_guard.py), [app/services/usage_repository.py](../../app/services/usage_repository.py).

**Direkte Testhelfer:** [tests/usage_test_support.py](../../tests/usage_test_support.py).

<details>
<summary>22 Testdefinitionen und ihre Quellstellen</summary>

- [test_free_consensus_run_limit_allows_a_daily_habit](../../tests/test_run_usage_repository.py#L37) (Zeile 37)
- [test_production_path_wraps_reserve_in_firestore_transaction](../../tests/test_run_usage_repository.py#L45) (Zeile 45)
- [test_usage_limits_reject_floats_and_booleans](../../tests/test_run_usage_repository.py#L80) (Zeile 80)
- [test_regular_limit_reserves_exactly_three_integer_slots](../../tests/test_run_usage_repository.py#L87) (Zeile 87)
- [test_parallel_unique_reservations_cannot_oversubscribe_limit](../../tests/test_run_usage_repository.py#L112) (Zeile 112)
- [test_parallel_same_idempotency_key_reserves_only_once](../../tests/test_run_usage_repository.py#L137) (Zeile 137)
- [test_idempotency_is_scoped_by_uid_and_bound_to_run_kind](../../tests/test_run_usage_repository.py#L154) (Zeile 154)
- [test_consume_moves_one_slot_and_is_idempotent](../../tests/test_run_usage_repository.py#L167) (Zeile 167)
- [test_get_run_is_read_only_and_reports_consumed_status](../../tests/test_run_usage_repository.py#L186) (Zeile 186)
- [test_consumed_run_context_binding_is_idempotent_and_target_specific](../../tests/test_run_usage_repository.py#L199) (Zeile 199)
- [test_pending_account_deletion_fences_every_usage_mutation](../../tests/test_run_usage_repository.py#L226) (Zeile 226)
- [test_expired_run_cannot_be_read_or_bound_to_new_context](../../tests/test_run_usage_repository.py#L280) (Zeile 280)
- [test_release_frees_slot_and_is_idempotent](../../tests/test_run_usage_repository.py#L300) (Zeile 300)
- [test_deep_think_has_separate_limit_and_counters](../../tests/test_run_usage_repository.py#L319) (Zeile 319)
- [test_consuming_deep_think_moves_total_and_deep_counters](../../tests/test_run_usage_repository.py#L337) (Zeile 337)
- [test_total_limit_blocks_deep_think_even_when_deep_quota_remains](../../tests/test_run_usage_repository.py#L350) (Zeile 350)
- [test_reservation_is_charged_to_utc_day_of_reserve](../../tests/test_run_usage_repository.py#L363) (Zeile 363)
- [test_missing_reservation_cannot_be_consumed_or_released](../../tests/test_run_usage_repository.py#L378) (Zeile 378)
- [test_request_fingerprint_binds_reused_key](../../tests/test_run_usage_repository.py#L386) (Zeile 386)
- [test_parallel_operation_claim_allows_exactly_one_winner](../../tests/test_run_usage_repository.py#L410) (Zeile 410)
- [test_cross_operation_claims_are_independent_and_payload_bound](../../tests/test_run_usage_repository.py#L440) (Zeile 440)
- [test_cross_day_replay_cannot_claim_provider_work](../../tests/test_run_usage_repository.py#L471) (Zeile 471)

</details>

<a id="test-security-controls-py"></a>

## test_security_controls.py

**Quelle:** [tests/test_security_controls.py](../../tests/test_security_controls.py) · **Bereiche:** Authentifizierung, Sicherheit.

**Ebene:** API-Verträge; ein Test mit main.app.

**Lauf:** 4 bestanden.

**Geprüftes Verhalten:** /check_keys verlangt Login und mindestens einen OpenRouter-Key; Own-Key-Modellrequest ohne Login liefert 401; der echte globale Validation-Handler bleibt bei Pydantic-ValueError auf 422 und entfernt ctx sowie eingesendeten Wert, lässt nur loc/type/msg zu.

**Grenzen und Doubles:** Die ersten Routertests haben eine eigene App und deaktivierten Limiter. Nur der Validation-Test nutzt main.app, ohne vollständigen Deployment-Lifespan.

**Prüfauftrag für den Folgeaudit:** Weitere Fehler- und Loggingpfade für sensible Eingaben sowie positive Schlüsselprüfung separat abgleichen.

**Direkte Codeverweise:** [app/api/routers/chat.py](../../app/api/routers/chat.py), [app/api/routers/pages.py](../../app/api/routers/pages.py), [app/core/rate_limit.py](../../app/core/rate_limit.py), [main.py](../../main.py).

<details>
<summary>4 Testdefinitionen und ihre Quellstellen</summary>

- [test_check_keys_requires_verified_login](../../tests/test_security_controls.py#L18) (Zeile 18)
- [test_check_keys_requires_at_least_one_key_after_auth](../../tests/test_security_controls.py#L26) (Zeile 26)
- [test_user_api_key_requests_require_login](../../tests/test_security_controls.py#L40) (Zeile 40)
- [test_validation_errors_stay_422_and_never_echo_the_submitted_value](../../tests/test_security_controls.py#L57) (Zeile 57)

</details>

<a id="test-seo-basics-py"></a>

## test_seo_basics.py

**Quelle:** [tests/test_seo_basics.py](../../tests/test_seo_basics.py) · **Bereiche:** SEO, Öffentliche Seiten.

**Ebene:** Pages-Routen und Template-Quelltextverträge.

**Lauf:** 13 bestanden.

**Geprüftes Verhalten:** Landing trotz Session erreichbar, App-Home-Link/noindex, Robots und Sitemap-Index/-Pages mit vorgesehenen indexierbaren Routen, Canonical/OG/Twitter/JSON-LD/OG-Datei und Hub-/Footer-Verlinkung.

**Grenzen und Doubles:** Metadaten überwiegend Sourceprüfungen; kein Suchmaschinen-Crawl oder tatsächlicher Indexierungsnachweis.

**Prüfauftrag für den Folgeaudit:** Gerenderte dynamische Metadaten/Canonical-Konsistenz und Robotsheader über alle Seiten abgleichen.

**Direkte Codeverweise:** [app/api/routers/pages.py](../../app/api/routers/pages.py), [static/og-home-v2.png](../../static/og-home-v2.png).

<details>
<summary>13 Testdefinitionen und ihre Quellstellen</summary>

- [SeoBasicsTests::test_landing_remains_accessible_with_session_cookie](../../tests/test_seo_basics.py#L22) (Zeile 22)
- [SeoBasicsTests::test_app_logo_links_to_landing_page](../../tests/test_seo_basics.py#L28) (Zeile 28)
- [SeoBasicsTests::test_robots_txt_points_to_sitemap](../../tests/test_seo_basics.py#L33) (Zeile 33)
- [SeoBasicsTests::test_sitemap_is_index_of_pages_and_shares](../../tests/test_seo_basics.py#L40) (Zeile 40)
- [SeoBasicsTests::test_pages_sitemap_contains_public_indexable_pages](../../tests/test_seo_basics.py#L50) (Zeile 50)
- [SeoBasicsTests::test_landing_template_has_core_seo_metadata](../../tests/test_seo_basics.py#L66) (Zeile 66)
- [SeoBasicsTests::test_ai_model_comparison_page_has_seo_metadata](../../tests/test_seo_basics.py#L79) (Zeile 79)
- [SeoBasicsTests::test_consensus_engine_page_has_seo_metadata](../../tests/test_seo_basics.py#L86) (Zeile 86)
- [SeoBasicsTests::test_questions_hub_template_has_seo_metadata](../../tests/test_seo_basics.py#L93) (Zeile 93)
- [SeoBasicsTests::test_topics_hub_template_has_seo_metadata](../../tests/test_seo_basics.py#L101) (Zeile 101)
- [SeoBasicsTests::test_model_pulse_page_has_seo_metadata_and_public_route](../../tests/test_seo_basics.py#L109) (Zeile 109)
- [SeoBasicsTests::test_public_nav_and_footer_link_to_questions_hub](../../tests/test_seo_basics.py#L120) (Zeile 120)
- [SeoBasicsTests::test_app_template_is_noindex](../../tests/test_seo_basics.py#L132) (Zeile 132)

</details>

<a id="test-seo-data-py"></a>

## test_seo_data.py

**Quelle:** [tests/test_seo_data.py](../../tests/test_seo_data.py) · **Bereiche:** Admin, Datenschutz, SEO.

**Ebene:** GSC-/Repository-/Recommendation-/Router-Integration mit Service-/HTTP-/DB-Doubles; UI-Sourceverträge.

**Lauf:** 35 bestanden.

**Geprüftes Verhalten:** Sichere GSC-Konfig/Dateialias/Readonly-Credentials, finale paginierte 90-Tage-Erfassung mit Delay/Chunks/Idempotenz und Truncation ohne falsche Nullen. Statusklassifikation, Admingates, erreichbare Alerts/Controls, begrenzte Dossiers, konservative Noindex-Safeguards/Graceperiod, Query-Privacyfilter, append-only Journal, strikter optionaler Content-Judge ohne Guard-Bypass.

**Grenzen und Doubles:** Keine echte Search-Console-Abfrage oder LLM-Bewertung. Admin-UI überwiegend statisch; synthetische Kennzahlen ersetzen reale Portfolioqualität.

**Prüfauftrag für den Folgeaudit:** Datenlücken/Quota-/APIänderungen und gerenderte Admin-Aktionen mit JS-Alerts/Weeklyreview abgleichen.

**Direkte Codeverweise:** [app/api/routers/admin.py](../../app/api/routers/admin.py), [app/services/google_search_console.py](../../app/services/google_search_console.py), [app/services/seo_data.py](../../app/services/seo_data.py), [app/services/seo_dossier.py](../../app/services/seo_dossier.py), [app/services/seo_recommendation.py](../../app/services/seo_recommendation.py), [app/services/seo_repository.py](../../app/services/seo_repository.py).

<details>
<summary>35 Testdefinitionen und ihre Quellstellen</summary>

- [test_configuration_errors_are_safe](../../tests/test_seo_data.py#L118) (Zeile 118)
- [test_service_account_file_variable_is_accepted_as_an_alias](../../tests/test_seo_data.py#L145) (Zeile 145)
- [test_service_account_variable_is_a_relative_repository_root_path](../../tests/test_seo_data.py#L163) (Zeile 163)
- [test_client_builds_credentials_with_readonly_scope_only](../../tests/test_seo_data.py#L177) (Zeile 177)
- [test_successful_collection_persists_90_days_with_origin_and_source](../../tests/test_seo_data.py#L197) (Zeile 197)
- [test_collection_is_idempotent_and_skips_already_finalized_days](../../tests/test_seo_data.py#L226) (Zeile 226)
- [test_truncated_ranges_do_not_persist_omitted_rows_as_zeroes](../../tests/test_seo_data.py#L251) (Zeile 251)
- [test_date_boundaries_exclude_the_three_day_delay_and_chunk_requests](../../tests/test_seo_data.py#L277) (Zeile 277)
- [test_not_configured_collection_records_safe_result](../../tests/test_seo_data.py#L292) (Zeile 292)
- [test_search_console_http_pagination_and_final_data_state](../../tests/test_seo_data.py#L312) (Zeile 312)
- [test_connection_check_returns_only_sanitized_status](../../tests/test_seo_data.py#L345) (Zeile 345)
- [test_connection_failure_never_exposes_google_body_or_credential_path](../../tests/test_seo_data.py#L378) (Zeile 378)
- [test_status_classification_rules](../../tests/test_seo_data.py#L404) (Zeile 404)
- [test_insufficient_data_counts_rows_not_traffic](../../tests/test_seo_data.py#L418) (Zeile 418)
- [test_visibility_weights_one_click_as_twenty_impressions](../../tests/test_seo_data.py#L429) (Zeile 429)
- [test_small_portfolio_reaches_opportunity_on_impressions_alone](../../tests/test_seo_data.py#L441) (Zeile 441)
- [test_admin_endpoints_require_admin](../../tests/test_seo_data.py#L448) (Zeile 448)
- [test_admin_seo_collect_action_is_hidden_until_admin_request_succeeds](../../tests/test_seo_data.py#L543) (Zeile 543)
- [test_admin_seo_tab_keeps_every_control_reachable_after_the_layout_rework](../../tests/test_seo_data.py#L573) (Zeile 573)
- [test_admin_seo_alert_strip_covers_every_state_that_can_silence_the_pipeline](../../tests/test_seo_data.py#L615) (Zeile 615)
- [test_static_dossier_contains_bounded_content_and_freshness_fields](../../tests/test_seo_data.py#L665) (Zeile 665)
- [test_share_dossier_keeps_only_a_bounded_representation](../../tests/test_seo_data.py#L677) (Zeile 677)
- [test_noindex_candidate_requires_every_safeguard_not_just_invisible_status](../../tests/test_seo_data.py#L719) (Zeile 719)
- [test_noindex_candidate_rejects_missing_final_days_and_positive_development](../../tests/test_seo_data.py#L755) (Zeile 755)
- [test_deterministic_recommendation_maps_existing_status_classes](../../tests/test_seo_data.py#L777) (Zeile 777)
- [test_distinctive_pages_get_a_longer_grace_period_before_retirement](../../tests/test_seo_data.py#L809) (Zeile 809)
- [test_pages_without_a_consensus_signal_keep_the_plain_60_day_rule](../../tests/test_seo_data.py#L836) (Zeile 836)
- [test_share_dossier_reports_the_consensus_signal](../../tests/test_seo_data.py#L849) (Zeile 849)
- [test_query_snapshot_marks_privacy_filtered_rows_as_partial](../../tests/test_seo_data.py#L881) (Zeile 881)
- [test_search_console_query_request_is_final_bounded_and_page_filtered](../../tests/test_seo_data.py#L908) (Zeile 908)
- [test_journal_generation_is_idempotent_and_append_only](../../tests/test_seo_data.py#L942) (Zeile 942)
- [test_weekly_review_can_generate_for_historically_captured_inactive_pages](../../tests/test_seo_data.py#L966) (Zeile 966)
- [test_llm_json_validation_is_strict_and_cannot_bypass_noindex_safeguards](../../tests/test_seo_data.py#L986) (Zeile 986)
- [test_optional_content_judge_uses_bounded_prompt_and_structured_schema](../../tests/test_seo_data.py#L1019) (Zeile 1019)
- [test_content_judge_is_not_called_for_winner_status](../../tests/test_seo_data.py#L1058) (Zeile 1058)

</details>

<a id="test-seo-entity-py"></a>

## test_seo_entity.py

**Quelle:** [tests/test_seo_entity.py](../../tests/test_seo_entity.py) · **Bereiche:** SEO, Öffentliche Seiten.

**Ebene:** Gerenderte Pages-/JSON-LD-Verträge.

**Lauf:** 6 bestanden.

**Geprüftes Verhalten:** Ein konsistenter Organization-Knoten pro öffentlicher Seite, keine konkurrierende Organisation, dokumentintern auflösbare @id-Referenzen, HTTPS-sameAs, Founder ausgeschlossen und korrekte Pagegraph-Einbettung.

**Grenzen und Doubles:** Lokal gerendertes JSON-LD; kein externer Schema-/Crawlernachweis. subTest-Schleifen sind nicht separate Runnerfälle.

**Prüfauftrag für den Folgeaudit:** Neue dynamische Share-/Topic-Seiten und Schemaänderungen in dieselbe Entity-Matrix aufnehmen.

**Direkte Codeverweise:** [app/api/routers/pages.py](../../app/api/routers/pages.py), [app/core/seo_entity.py](../../app/core/seo_entity.py).

<details>
<summary>6 Testdefinitionen und ihre Quellstellen</summary>

- [SeoEntityTests::test_every_public_page_carries_the_same_organization](../../tests/test_seo_entity.py#L39) (Zeile 39)
- [SeoEntityTests::test_no_page_invents_a_second_organization_by_name](../../tests/test_seo_entity.py#L51) (Zeile 51)
- [SeoEntityTests::test_id_references_resolve_inside_the_same_document](../../tests/test_seo_entity.py#L61) (Zeile 61)
- [SeoEntityTests::test_same_as_holds_only_absolute_urls](../../tests/test_seo_entity.py#L74) (Zeile 74)
- [SeoEntityTests::test_founder_stays_out_of_structured_data](../../tests/test_seo_entity.py#L81) (Zeile 81)
- [SeoEntityTests::test_page_graph_embeds_the_entity_next_to_the_page_node](../../tests/test_seo_entity.py#L86) (Zeile 86)

</details>

<a id="test-seo-weekly-review-py"></a>

## test_seo_weekly_review.py

**Quelle:** [tests/test_seo_weekly_review.py](../../tests/test_seo_weekly_review.py) · **Bereiche:** Publisher, SEO, Watch.

**Ebene:** Review-Service mit Repository-/Judge-/Action-Doubles.

**Lauf:** 20 bestanden.

**Geprüftes Verhalten:** Persistente Lease/lokaler Wochenzeitplan, höchstens ein Portfolio-Judge, 100 Seiten im begrenzten Prompt und explizite Auslassung erst nach Detailreduktion. Terminale Notifications/Collection-Failure, keine doppelten Metricscans, Evidenzgate für Briefänderung, History/Statusdelta und deterministische Empfehlungen. Getrennte Watch-/Index-Aktionen mit Teilergebnissen, kein Delete bei apply-all, Publisherlineage, manuelle Entscheidung und konfliktgeprüfte Briefannahme.

**Grenzen und Doubles:** DB, GSC, Judge und Aktionen ersetzt; keine reale Index-/Watch-/Delete-Ausführung und kein Mehrprozesslease.

**Prüfauftrag für den Folgeaudit:** Konkurrierende Review-/Adminänderungen sowie Fehler nach Teilaktionen mit Persistenz-/APIfällen abgleichen.

**Direkte Codeverweise:** [app/services/seo_weekly_review.py](../../app/services/seo_weekly_review.py).

<details>
<summary>20 Testdefinitionen und ihre Quellstellen</summary>

- [test_default_interval_is_seven_days_and_lease_is_persistent](../../tests/test_seo_weekly_review.py#L81) (Zeile 81)
- [test_weekly_schedule_uses_configured_local_time](../../tests/test_seo_weekly_review.py#L92) (Zeile 92)
- [test_review_uses_at_most_one_portfolio_judge_call](../../tests/test_seo_weekly_review.py#L179) (Zeile 179)
- [test_a_growing_portfolio_still_fits_into_one_judge_prompt](../../tests/test_seo_weekly_review.py#L212) (Zeile 212)
- [test_judge_prompt_gives_up_detail_before_it_gives_up_pages](../../tests/test_seo_weekly_review.py#L223) (Zeile 223)
- [test_portfolio_judge_defaults_to_gpt_5_6_terra](../../tests/test_seo_weekly_review.py#L249) (Zeile 249)
- [test_portfolio_judge_sends_terra_with_medium_reasoning](../../tests/test_seo_weekly_review.py#L257) (Zeile 257)
- [test_every_terminal_review_attempts_telegram_notification](../../tests/test_seo_weekly_review.py#L282) (Zeile 282)
- [test_review_reuses_overview_context_without_second_metric_scan](../../tests/test_seo_weekly_review.py#L298) (Zeile 298)
- [test_failed_collection_never_calls_portfolio_judge](../../tests/test_seo_weekly_review.py#L351) (Zeile 351)
- [test_mature_portfolio_can_persist_optional_topic_brief_suggestion](../../tests/test_seo_weekly_review.py#L359) (Zeile 359)
- [test_young_portfolio_keeps_the_topic_brief_suggestion_but_cannot_apply_it](../../tests/test_seo_weekly_review.py#L383) (Zeile 383)
- [test_history_exposes_findings_judge_failure_and_status_delta](../../tests/test_seo_weekly_review.py#L408) (Zeile 408)
- [test_deterministic_recommendations_are_grouped_without_llm_override](../../tests/test_seo_weekly_review.py#L452) (Zeile 452)
- [test_manual_improvement_gets_snapshot_decision_template](../../tests/test_seo_weekly_review.py#L465) (Zeile 465)
- [test_pause_and_resume_watch_never_change_indexing](../../tests/test_seo_weekly_review.py#L532) (Zeile 532)
- [test_noindex_only_leaves_watch_and_combined_reports_both_steps](../../tests/test_seo_weekly_review.py#L546) (Zeile 546)
- [test_apply_all_never_includes_delete_and_delete_requires_publisher_lineage](../../tests/test_seo_weekly_review.py#L573) (Zeile 573)
- [test_topic_brief_accept_preserves_other_config_and_detects_manual_change](../../tests/test_seo_weekly_review.py#L591) (Zeile 591)
- [test_editorial_decision_and_topic_brief_rejection_are_persisted](../../tests/test_seo_weekly_review.py#L609) (Zeile 609)

</details>

<a id="test-share-feature-py"></a>

## test_share_feature.py

**Quelle:** [tests/test_share_feature.py](../../tests/test_share_feature.py) · **Bereiche:** Authentifizierung, Persistenz, SEO, Watch, Öffentliche Freigaben.

**Ebene:** Große Unit-/Service-/Router-/SSR-Suite mit FakeDb und lokalen Cachethreads.

**Lauf:** 151 bestanden.

**Geprüftes Verhalten:** 151 Definitionen: Slug/IDs, Allowlist/Caps/Quellen/Modelle/Judge/Resolution, Pending-Owner/TTL/Indexeligibility, sichere Markdown-/Math-/Citationausgabe. Idempotente public/private Veröffentlichung mit Backlink und Sourcejob-Retention, Quota/Tombstones, Revoke/Report/Moderation/Harddelete/Cleanup. Owner/Admin-API und Indexrequests, Related-/Sharecache, Canonical/Sitemap/Hub/OG; aktuelle/historische Watch-Snapshots samt Quellen/Labels/Zeit/fehlenden Scores bleiben getrennt.

**Grenzen und Doubles:** Transaktions- und Querverweise nutzen FakeDb; Router patchen teils ganze Services. SVG/HTML wird textuell geprüft, OG nur PNG-Signatur/Status. ID-Stichprobe mit 500 Werten beweist keine kryptographische Entropie. Hubfehler wird aktuell als leere 200-Seite dargestellt.

**Prüfauftrag für den Folgeaudit:** Atomizität/Retention unter echter Konkurrenz, öffentliche Cacheinvalidierung nach Revoke und Browser-XSS/Rendering separat abgleichen.

**Direkte Codeverweise:** [app/api/routers/admin.py](../../app/api/routers/admin.py), [app/api/routers/share.py](../../app/api/routers/share.py), [app/core/config.py](../../app/core/config.py), [app/core/rate_limit.py](../../app/core/rate_limit.py), [app/services/public_markdown.py](../../app/services/public_markdown.py), [app/services/share_snapshots.py](../../app/services/share_snapshots.py).

<details>
<summary>151 Testdefinitionen und ihre Quellstellen</summary>

- [SlugAndIdTests::test_slugify_handles_umlauts_and_punctuation](../../tests/test_share_feature.py#L209) (Zeile 209)
- [SlugAndIdTests::test_slugify_truncates_at_word_boundary](../../tests/test_share_feature.py#L216) (Zeile 216)
- [SlugAndIdTests::test_slugify_fallback_for_empty_input](../../tests/test_share_feature.py#L221) (Zeile 221)
- [SlugAndIdTests::test_generate_share_id_charset_and_uniqueness](../../tests/test_share_feature.py#L225) (Zeile 225)
- [SlugAndIdTests::test_is_valid_share_id_rejects_bad_input](../../tests/test_share_feature.py#L232) (Zeile 232)
- [SlugAndIdTests::test_split_slug_id](../../tests/test_share_feature.py#L238) (Zeile 238)
- [SlugAndIdTests::test_question_hash_normalizes](../../tests/test_share_feature.py#L242) (Zeile 242)
- [SanitizerTests::test_sources_drop_non_http_and_dedupe](../../tests/test_share_feature.py#L250) (Zeile 250)
- [SanitizerTests::test_sources_preserve_all_entries_beyond_legacy_count_cap](../../tests/test_share_feature.py#L262) (Zeile 262)
- [SanitizerTests::test_differences_whitelist](../../tests/test_share_feature.py#L266) (Zeile 266)
- [SanitizerTests::test_judges_are_whitelisted](../../tests/test_share_feature.py#L298) (Zeile 298)
- [SanitizerTests::test_resolution_is_whitelisted](../../tests/test_share_feature.py#L317) (Zeile 317)
- [SanitizerTests::test_invalid_resolution_is_dropped](../../tests/test_share_feature.py#L344) (Zeile 344)
- [SanitizerTests::test_agreement_score_is_clamped](../../tests/test_share_feature.py#L358) (Zeile 358)
- [SanitizerTests::test_included_models_order_and_labels](../../tests/test_share_feature.py#L370) (Zeile 370)
- [SanitizerTests::test_model_labels_only_for_included_providers](../../tests/test_share_feature.py#L377) (Zeile 377)
- [SanitizerTests::test_model_labels_charset_and_length_fallback](../../tests/test_share_feature.py#L385) (Zeile 385)
- [SanitizerTests::test_model_labels_strip_badge_suffix](../../tests/test_share_feature.py#L397) (Zeile 397)
- [SanitizerTests::test_consulted_models_view_maps_icon_and_model](../../tests/test_share_feature.py#L414) (Zeile 414)
- [SanitizerTests::test_consensus_model_view_resolves_provider_and_pro](../../tests/test_share_feature.py#L437) (Zeile 437)
- [PendingResultTests::test_requires_uid_question_and_consensus](../../tests/test_share_feature.py#L463) (Zeile 463)
- [PendingResultTests::test_account_deletion_tombstone_fences_pending_result_write](../../tests/test_share_feature.py#L468) (Zeile 468)
- [PendingResultTests::test_caps_applied](../../tests/test_share_feature.py#L480) (Zeile 480)
- [PendingResultTests::test_index_eligible](../../tests/test_share_feature.py#L493) (Zeile 493)
- [PendingResultTests::test_index_eligible_uses_limits_config](../../tests/test_share_feature.py#L503) (Zeile 503)
- [PublicPayloadTests::test_whitelist_excludes_internal_fields](../../tests/test_share_feature.py#L518) (Zeile 518)
- [PublicPayloadTests::test_citation_contains_canonical_url](../../tests/test_share_feature.py#L538) (Zeile 538)
- [PublicPayloadTests::test_citation_empty_without_models](../../tests/test_share_feature.py#L548) (Zeile 548)
- [PublicMarkdownTests::test_script_and_raw_html_neutralized](../../tests/test_share_feature.py#L556) (Zeile 556)
- [PublicMarkdownTests::test_javascript_links_stripped](../../tests/test_share_feature.py#L564) (Zeile 564)
- [PublicMarkdownTests::test_http_links_get_rel](../../tests/test_share_feature.py#L569) (Zeile 569)
- [PublicMarkdownTests::test_source_tags_become_anchor_links](../../tests/test_share_feature.py#L574) (Zeile 574)
- [PublicMarkdownTests::test_sentence_end_source_tags_follow_punctuation](../../tests/test_share_feature.py#L582) (Zeile 582)
- [PublicMarkdownTests::test_source_tags_without_url_fall_back_to_id](../../tests/test_share_feature.py#L591) (Zeile 591)
- [PublicMarkdownTests::test_unknown_source_tags_untouched](../../tests/test_share_feature.py#L596) (Zeile 596)
- [PublicMarkdownTests::test_source_tags_in_code_untouched](../../tests/test_share_feature.py#L601) (Zeile 601)
- [PublicMarkdownTests::test_tables_render](../../tests/test_share_feature.py#L605) (Zeile 605)
- [PublicMarkdownTests::test_latex_delimiters_survive_markdown_for_katex](../../tests/test_share_feature.py#L609) (Zeile 609)
- [PublicMarkdownTests::test_latex_delimiters_in_code_stay_literal](../../tests/test_share_feature.py#L616) (Zeile 616)
- [PublicMarkdownTests::test_multiline_equations_do_not_become_markdown_headings](../../tests/test_share_feature.py#L621) (Zeile 621)
- [PublicMarkdownTests::test_formula_markup_and_tex_escapes_survive_public_markdown](../../tests/test_share_feature.py#L636) (Zeile 636)
- [PublicMarkdownTests::test_plaintext_strips_and_clips](../../tests/test_share_feature.py#L643) (Zeile 643)
- [PublicMarkdownTests::test_plaintext_strips_source_tags](../../tests/test_share_feature.py#L649) (Zeile 649)
- [PublicMarkdownTests::test_grounding_redirects_show_the_site_they_point_at](../../tests/test_share_feature.py#L655) (Zeile 655)
- [ShareFlowTests::test_publication_retains_source_check_atomically](../../tests/test_share_feature.py#L681) (Zeile 681)
- [ShareFlowTests::test_publication_rejects_missing_foreign_or_deleting_source_check_before_quota](../../tests/test_share_feature.py#L698) (Zeile 698)
- [ShareFlowTests::test_unknown_result_id_raises_not_found](../../tests/test_share_feature.py#L713) (Zeile 713)
- [ShareFlowTests::test_invalid_result_id_raises_not_found](../../tests/test_share_feature.py#L719) (Zeile 719)
- [ShareFlowTests::test_foreign_result_raises_forbidden](../../tests/test_share_feature.py#L725) (Zeile 725)
- [ShareFlowTests::test_expired_result_is_deleted_and_not_found](../../tests/test_share_feature.py#L732) (Zeile 732)
- [ShareFlowTests::test_quota_exceeded](../../tests/test_share_feature.py#L741) (Zeile 741)
- [ShareFlowTests::test_create_share_snapshot](../../tests/test_share_feature.py#L748) (Zeile 748)
- [ShareFlowTests::test_account_deletion_tombstone_fences_share_publication](../../tests/test_share_feature.py#L764) (Zeile 764)
- [ShareFlowTests::test_create_share_is_idempotent](../../tests/test_share_feature.py#L780) (Zeile 780)
- [ShareFlowTests::test_publication_failure_cannot_leave_share_without_backlink](../../tests/test_share_feature.py#L794) (Zeile 794)
- [ShareFlowTests::test_private_and_public_snapshots_are_distinct_and_idempotent](../../tests/test_share_feature.py#L811) (Zeile 811)
- [ShareFlowTests::test_pending_result_reuse_requires_owner_and_unexpired_ttl](../../tests/test_share_feature.py#L836) (Zeile 836)
- [ShareFlowTests::test_pending_result_provenance_fails_closed_without_aware_expiry](../../tests/test_share_feature.py#L847) (Zeile 847)
- [ShareFlowTests::test_private_share_cannot_be_reported](../../tests/test_share_feature.py#L865) (Zeile 865)
- [ShareFlowTests::test_revoke_by_owner](../../tests/test_share_feature.py#L874) (Zeile 874)
- [ShareFlowTests::test_revoke_foreign_share_forbidden_unless_admin](../../tests/test_share_feature.py#L882) (Zeile 882)
- [ShareFlowTests::test_revoke_is_fenced_during_account_deletion](../../tests/test_share_feature.py#L892) (Zeile 892)
- [ShareFlowTests::test_report_share_increments_and_aggregates](../../tests/test_share_feature.py#L906) (Zeile 906)
- [ShareFlowTests::test_report_share_rejects_inactive_or_unknown](../../tests/test_share_feature.py#L918) (Zeile 918)
- [ShareFlowTests::test_report_fields_stay_out_of_public_payload](../../tests/test_share_feature.py#L928) (Zeile 928)
- [ShareFlowTests::test_list_shares_for_owner_is_whitelisted](../../tests/test_share_feature.py#L935) (Zeile 935)
- [ModerationAndCleanupTests::test_block_sets_status_and_clears_indexed](../../tests/test_share_feature.py#L973) (Zeile 973)
- [ModerationAndCleanupTests::test_unblock_requires_blocked_status](../../tests/test_share_feature.py#L982) (Zeile 982)
- [ModerationAndCleanupTests::test_indexed_only_for_active_shares](../../tests/test_share_feature.py#L989) (Zeile 989)
- [ModerationAndCleanupTests::test_moderation_is_fenced_during_account_deletion](../../tests/test_share_feature.py#L1002) (Zeile 1002)
- [ModerationAndCleanupTests::test_moderate_validates_input](../../tests/test_share_feature.py#L1011) (Zeile 1011)
- [ModerationAndCleanupTests::test_revoke_cannot_be_blocked](../../tests/test_share_feature.py#L1020) (Zeile 1020)
- [ModerationAndCleanupTests::test_admin_hard_delete_removes_share_watch_and_followers](../../tests/test_share_feature.py#L1025) (Zeile 1025)
- [ModerationAndCleanupTests::test_admin_hard_delete_rejects_missing_share](../../tests/test_share_feature.py#L1044) (Zeile 1044)
- [ModerationAndCleanupTests::test_auto_noindex_after_report_threshold](../../tests/test_share_feature.py#L1048) (Zeile 1048)
- [ModerationAndCleanupTests::test_reports_below_threshold_keep_indexed](../../tests/test_share_feature.py#L1057) (Zeile 1057)
- [ModerationAndCleanupTests::test_admin_list_prioritizes_review_and_reports](../../tests/test_share_feature.py#L1064) (Zeile 1064)
- [ModerationAndCleanupTests::test_cleanup_revoked_shares_after_30_days](../../tests/test_share_feature.py#L1078) (Zeile 1078)
- [ModerationAndCleanupTests::test_cleanup_revoked_shares_drains_more_than_one_page](../../tests/test_share_feature.py#L1092) (Zeile 1092)
- [ModerationAndCleanupTests::test_find_canonical_share_prefers_oldest_indexed](../../tests/test_share_feature.py#L1112) (Zeile 1112)
- [ModerationAndCleanupTests::test_list_indexed_share_urls_filters](../../tests/test_share_feature.py#L1128) (Zeile 1128)
- [ModerationAndCleanupTests::test_list_hub_shares_filters_and_enriches](../../tests/test_share_feature.py#L1138) (Zeile 1138)
- [ModerationAndCleanupTests::test_list_related_shares_only_indexed_active_and_excludes_self](../../tests/test_share_feature.py#L1169) (Zeile 1169)
- [ModerationAndCleanupTests::test_list_related_shares_ranks_by_token_overlap](../../tests/test_share_feature.py#L1186) (Zeile 1186)
- [ModerationAndCleanupTests::test_related_candidate_pool_serves_different_pages_and_arguments](../../tests/test_share_feature.py#L1203) (Zeile 1203)
- [ModerationAndCleanupTests::test_related_pool_expiry_and_explicit_database_bypass](../../tests/test_share_feature.py#L1225) (Zeile 1225)
- [ModerationAndCleanupTests::test_related_pool_coalesces_concurrent_misses](../../tests/test_share_feature.py#L1241) (Zeile 1241)
- [ModerationAndCleanupTests::test_related_invalidation_during_fill_cannot_leave_stale_pool](../../tests/test_share_feature.py#L1250) (Zeile 1250)
- [ModerationAndCleanupTests::test_share_cache_returns_cached_until_invalidated](../../tests/test_share_feature.py#L1280) (Zeile 1280)
- [ModerationAndCleanupTests::test_revoke_invalidates_cache](../../tests/test_share_feature.py#L1295) (Zeile 1295)
- [SharePageRouteTests::test_invalid_id_renders_404_with_noindex](../../tests/test_share_feature.py#L1336) (Zeile 1336)
- [SharePageRouteTests::test_unknown_id_renders_404](../../tests/test_share_feature.py#L1341) (Zeile 1341)
- [SharePageRouteTests::test_revoked_share_renders_410](../../tests/test_share_feature.py#L1346) (Zeile 1346)
- [SharePageRouteTests::test_wrong_slug_redirects_to_canonical](../../tests/test_share_feature.py#L1353) (Zeile 1353)
- [SharePageRouteTests::test_active_share_renders_content_with_noindex](../../tests/test_share_feature.py#L1360) (Zeile 1360)
- [SharePageRouteTests::test_active_share_preserves_latex_and_loads_katex_renderer](../../tests/test_share_feature.py#L1373) (Zeile 1373)
- [SharePageRouteTests::test_private_share_requires_owner_and_is_never_publicly_cached](../../tests/test_share_feature.py#L1387) (Zeile 1387)
- [SharePageRouteTests::test_differences_cards_and_toggle_rendered](../../tests/test_share_feature.py#L1406) (Zeile 1406)
- [SharePageRouteTests::test_differences_fallback_text_rendered](../../tests/test_share_feature.py#L1432) (Zeile 1432)
- [SharePageRouteTests::test_structured_empty_differences_do_not_render_legacy_credibility_text](../../tests/test_share_feature.py#L1440) (Zeile 1440)
- [SharePageRouteTests::test_related_questions_section_rendered](../../tests/test_share_feature.py#L1465) (Zeile 1465)
- [SharePageRouteTests::test_related_questions_section_hidden_when_empty](../../tests/test_share_feature.py#L1479) (Zeile 1479)
- [SharePageRouteTests::test_watch_history_renders_inline_svg_and_events](../../tests/test_share_feature.py#L1486) (Zeile 1486)
- [SharePageRouteTests::test_watch_history_renders_position_map_and_direction_shift](../../tests/test_share_feature.py#L1512) (Zeile 1512)
- [SharePageRouteTests::test_active_watch_page_shows_run_metadata_before_history_exists](../../tests/test_share_feature.py#L1550) (Zeile 1550)
- [SharePageRouteTests::test_a_rephrased_check_reads_as_stable_on_the_watch_page](../../tests/test_share_feature.py#L1569) (Zeile 1569)
- [SharePageRouteTests::test_watch_page_renders_latest_version_without_mutating_shared_baseline](../../tests/test_share_feature.py#L1612) (Zeile 1612)
- [SharePageRouteTests::test_watch_historical_version_uses_only_its_full_snapshot_metadata](../../tests/test_share_feature.py#L1672) (Zeile 1672)
- [SharePageRouteTests::test_missing_current_full_version_falls_back_consistently_to_original](../../tests/test_share_feature.py#L1713) (Zeile 1713)
- [SharePageRouteTests::test_legacy_compact_history_without_version_pointer_keeps_original_snapshot](../../tests/test_share_feature.py#L1739) (Zeile 1739)
- [SharePageRouteTests::test_watch_page_shows_selected_local_run_time](../../tests/test_share_feature.py#L1761) (Zeile 1761)
- [SharePageRouteTests::test_rendered_citation_contains_canonical_url](../../tests/test_share_feature.py#L1774) (Zeile 1774)
- [SharePageRouteTests::test_noindex_page_has_seo_tags_and_cache_control](../../tests/test_share_feature.py#L1784) (Zeile 1784)
- [SharePageRouteTests::test_indexed_page_gets_index_follow](../../tests/test_share_feature.py#L1802) (Zeile 1802)
- [SharePageRouteTests::test_noindex_duplicate_points_canonical_to_indexed_share](../../tests/test_share_feature.py#L1812) (Zeile 1812)
- [SharePageRouteTests::test_sitemap_shares_lists_only_indexed](../../tests/test_share_feature.py#L1828) (Zeile 1828)
- [SharePageRouteTests::test_questions_hub_lists_indexed_shares](../../tests/test_share_feature.py#L1838) (Zeile 1838)
- [SharePageRouteTests::test_questions_hub_survives_backend_failure](../../tests/test_share_feature.py#L1860) (Zeile 1860)
- [SharePageRouteTests::test_report_endpoint_maps_share_errors](../../tests/test_share_feature.py#L1867) (Zeile 1867)
- [ShareApiRouteTests::test_my_shares_requires_auth](../../tests/test_share_feature.py#L1898) (Zeile 1898)
- [ShareApiRouteTests::test_my_shares_returns_owner_list](../../tests/test_share_feature.py#L1903) (Zeile 1903)
- [ShareApiRouteTests::test_delete_share_revokes_for_owner](../../tests/test_share_feature.py#L1917) (Zeile 1917)
- [ShareApiRouteTests::test_delete_share_maps_share_errors](../../tests/test_share_feature.py#L1926) (Zeile 1926)
- [AdminShareRouteTests::test_list_requires_admin](../../tests/test_share_feature.py#L1952) (Zeile 1952)
- [AdminShareRouteTests::test_list_passes_filter](../../tests/test_share_feature.py#L1958) (Zeile 1958)
- [AdminShareRouteTests::test_moderate_forwards_action_and_indexed](../../tests/test_share_feature.py#L1972) (Zeile 1972)
- [AdminShareRouteTests::test_moderate_validates_indexed_type_and_maps_errors](../../tests/test_share_feature.py#L1991) (Zeile 1991)
- [AdminShareRouteTests::test_delete_requires_admin_and_hard_deletes](../../tests/test_share_feature.py#L2006) (Zeile 2006)
- [AdminShareRouteTests::test_delete_maps_missing_share](../../tests/test_share_feature.py#L2027) (Zeile 2027)
- [IndexingRequestTests::test_owner_can_request_and_withdraw](../../tests/test_share_feature.py#L2051) (Zeile 2051)
- [IndexingRequestTests::test_indexing_request_is_fenced_during_account_deletion](../../tests/test_share_feature.py#L2065) (Zeile 2065)
- [IndexingRequestTests::test_only_owner_public_active_can_request](../../tests/test_share_feature.py#L2075) (Zeile 2075)
- [IndexingRequestTests::test_already_indexed_returns_state_without_new_request](../../tests/test_share_feature.py#L2086) (Zeile 2086)
- [IndexingRequestTests::test_moderation_clears_open_request](../../tests/test_share_feature.py#L2093) (Zeile 2093)
- [IndexingRequestTests::test_indexing_request_route_requires_auth_and_owner](../../tests/test_share_feature.py#L2100) (Zeile 2100)
- [IndexingRequestTests::test_sitemap_lastmod_prefers_last_watch_run](../../tests/test_share_feature.py#L2116) (Zeile 2116)
- [ApiRunPublishingServiceTests::test_api_run_publication_is_idempotent_and_skips_pending_results](../../tests/test_share_feature.py#L2164) (Zeile 2164)
- [ApiRunPublishingServiceTests::test_account_deletion_tombstone_fences_api_run_publication](../../tests/test_share_feature.py#L2183) (Zeile 2183)
- [ApiRunPublishingServiceTests::test_only_publisher_mode_api_runs_receive_publisher_lineage](../../tests/test_share_feature.py#L2198) (Zeile 2198)
- [ApiRunPublishingServiceTests::test_api_run_requires_ownership_and_success](../../tests/test_share_feature.py#L2213) (Zeile 2213)
- [ApiRunPublishingServiceTests::test_api_indexing_enforces_quality_dedup_and_audit](../../tests/test_share_feature.py#L2226) (Zeile 2226)
- [ApiRunPublishingServiceTests::test_api_indexing_is_fenced_during_account_deletion](../../tests/test_share_feature.py#L2280) (Zeile 2280)
- [ShareSeoEnhancementTests::test_scoreboard_teaser_and_data_led_description](../../tests/test_share_feature.py#L2354) (Zeile 2354)
- [ShareSeoEnhancementTests::test_date_modified_uses_authoritative_display_version](../../tests/test_share_feature.py#L2368) (Zeile 2368)
- [ShareSeoEnhancementTests::test_citations_skip_redirect_urls_that_point_nowhere_readable](../../tests/test_share_feature.py#L2377) (Zeile 2377)
- [ShareSeoEnhancementTests::test_tracked_page_shows_its_history_as_a_fact_not_only_as_a_chart](../../tests/test_share_feature.py#L2391) (Zeile 2391)
- [ShareSeoEnhancementTests::test_unscored_watch_check_keeps_its_change_and_version_link](../../tests/test_share_feature.py#L2401) (Zeile 2401)
- [ShareSeoEnhancementTests::test_historical_version_does_not_claim_the_full_tracking_record](../../tests/test_share_feature.py#L2425) (Zeile 2425)
- [ShareSeoEnhancementTests::test_follow_form_only_on_active_public_watch_pages](../../tests/test_share_feature.py#L2443) (Zeile 2443)
- [ShareSeoEnhancementTests::test_og_card_route_and_meta](../../tests/test_share_feature.py#L2459) (Zeile 2459)
- [ShareSeoEnhancementTests::test_og_card_404_for_private_pages](../../tests/test_share_feature.py#L2472) (Zeile 2472)

</details>

<a id="test-source-catalog-py"></a>

## test_source_catalog.py

**Quelle:** [tests/test_source_catalog.py](../../tests/test_source_catalog.py) · **Bereiche:** Konsens und Unterschiede, Persistenz, Quellenprüfung.

**Ebene:** Normalizer-/Transport-/Renderer-/Storage-Unit-Integration.

**Lauf:** 19 bestanden.

**Geprüftes Verhalten:** Providerlokale ID-Kollisionen vor Synthese umnummerieren, deterministisch/idempotent/ohne Mutation; URL-Deduplizierung mit Provenienz und case-sensitiven Pfaden, explizite/fehlende/mehrdeutige IDs. Code/Fences nicht umschreiben, 100 Quellen erhalten, Chat-/Share-/Public-Markdown-Roundtrip und Source-Check-Provenienz.

**Grenzen und Doubles:** Fan-out verwendet injizierte Antworten; Sanitizer-Roundtrip ist kein DB-Write. Kein Abruf der referenzierten Webseiten.

**Prüfauftrag für den Folgeaudit:** Gemischte Legacy-/neue ID-Namensräume und stark beschädigtes Markdown mit Citation-Dateien abgleichen.

**Direkte Codeverweise:** [app/services/chat_store.py](../../app/services/chat_store.py), [app/services/llm/provider_transport.py](../../app/services/llm/provider_transport.py), [app/services/public_markdown.py](../../app/services/public_markdown.py), [app/services/share_snapshots.py](../../app/services/share_snapshots.py), [app/services/source_catalog.py](../../app/services/source_catalog.py), [app/services/source_verification.py](../../app/services/source_verification.py).

<details>
<summary>19 Testdefinitionen und ihre Quellstellen</summary>

- [test_colliding_provider_local_ids_are_rewritten_before_synthesis](../../tests/test_source_catalog.py#L20) (Zeile 20)
- [test_deterministic_registry_order_and_input_immutability](../../tests/test_source_catalog.py#L32) (Zeile 32)
- [test_duplicate_documents_deduplicate_and_retain_all_provider_provenance](../../tests/test_source_catalog.py#L42) (Zeile 42)
- [test_path_and_query_case_are_significant](../../tests/test_source_catalog.py#L53) (Zeile 53)
- [test_browser_global_numbering_and_explicit_turn_sources_stay_stable](../../tests/test_source_catalog.py#L63) (Zeile 63)
- [test_explicit_turn_catalog_cannot_override_provider_local_mapping](../../tests/test_source_catalog.py#L74) (Zeile 74)
- [test_ambiguous_local_ids_never_acquire_a_link_and_neither_document_is_lost](../../tests/test_source_catalog.py#L83) (Zeile 83)
- [test_missing_references_are_reserved_in_other_provider_namespaces](../../tests/test_source_catalog.py#L94) (Zeile 94)
- [test_missing_ids_fall_back_to_position_but_do_not_override_explicit_ids](../../tests/test_source_catalog.py#L104) (Zeile 104)
- [test_only_real_citation_tags_are_rewritten](../../tests/test_source_catalog.py#L113) (Zeile 113)
- [test_normalization_is_idempotent](../../tests/test_source_catalog.py#L120) (Zeile 120)
- [test_explicit_catalog_fills_sources_for_string_answers_and_accepts_aliases](../../tests/test_source_catalog.py#L128) (Zeile 128)
- [test_fan_out_normalizes_real_transport_results](../../tests/test_source_catalog.py#L138) (Zeile 138)
- [test_catalog_does_not_drop_sources_above_old_fifty_source_limit](../../tests/test_source_catalog.py#L147) (Zeile 147)
- [test_malformed_explicit_id_does_not_alias_position_and_dicts_keep_text_field](../../tests/test_source_catalog.py#L154) (Zeile 154)
- [test_unclosed_and_longer_fences_preserve_all_literal_citations](../../tests/test_source_catalog.py#L163) (Zeile 163)
- [test_persistence_sanitizer_retains_case_sensitive_paths_aliases_and_all_citations](../../tests/test_source_catalog.py#L168) (Zeile 168)
- [test_chat_model_and_turn_normalization_roundtrip_entire_source_catalog](../../tests/test_source_catalog.py#L185) (Zeile 185)
- [test_source_check_plan_preserves_validated_shared_provider_provenance](../../tests/test_source_catalog.py#L198) (Zeile 198)

</details>

<a id="test-source-check-api-py"></a>

## test_source_check_api.py

**Quelle:** [tests/test_source_check_api.py](../../tests/test_source_check_api.py) · **Bereiche:** Authentifizierung, Jobs, Quellenprüfung, Öffentliche Seiten.

**Ebene:** Router mit SourceCheckRepository/FakeDb und Share-/Topic-Doubles.

**Lauf:** 14 bestanden.

**Geprüftes Verhalten:** Owner-Pagination/Revision/no-store, fremde Jobs verborgen, aktive passende öffentliche/private Share-/Historybindung. Resume-Key nur für richtigen Owner/Job/Workerumgebung; Cursorgrenzen und unverändertes Poll ohne große Planreads. V4 bindet Run-/Answer-/Prompt-Version auch auf unchanged-Pages; identische Topicantwort erlaubt keinen falschen Run.

**Grenzen und Doubles:** Auth-Tokenprüfung und Share-/Topiczugriffe ersetzt; kein vollständiger Firebase-/Share-Serverablauf.

**Prüfauftrag für den Folgeaudit:** Revocation während Pagination/Resume und tatsächliche Browserpoller gegen API abgleichen.

**Direkte Codeverweise:** [app/api/routers/source_checks.py](../../app/api/routers/source_checks.py), [app/services/share_snapshots.py](../../app/services/share_snapshots.py), [app/services/source_check_jobs.py](../../app/services/source_check_jobs.py), [app/services/source_check_repository.py](../../app/services/source_check_repository.py), [app/services/source_verification.py](../../app/services/source_verification.py), [app/services/topics.py](../../app/services/topics.py).

**Direkte Testhelfer:** [tests/test_contradiction_verification.py](../../tests/test_contradiction_verification.py), [tests/test_source_check_repository.py](../../tests/test_source_check_repository.py).

<details>
<summary>9 Testdefinitionen und ihre Quellstellen</summary>

- [test_owner_reads_all_pages_and_other_owner_cannot_read](../../tests/test_source_check_api.py#L26) (Zeile 26)
- [test_public_access_requires_active_matching_share_and_correct_answer](../../tests/test_source_check_api.py#L45) (Zeile 45)
- [test_private_share_and_history_cannot_leak_other_jobs](../../tests/test_source_check_api.py#L60) (Zeile 60)
- [test_resume_does_not_accept_key_for_another_owner_or_server_job](../../tests/test_source_check_api.py#L77) (Zeile 77)
- [test_invalid_cursor_has_no_unbounded_or_cross_job_access](../../tests/test_source_check_api.py#L86) (Zeile 86)
- [test_other_environment_is_readable_but_cannot_take_an_own_key](../../tests/test_source_check_api.py#L93) (Zeile 93)
- [test_unchanged_poll_does_not_read_large_plan_or_package_documents](../../tests/test_source_check_api.py#L112) (Zeile 112)
- [test_v4_public_share_rejects_wrong_job_version_on_every_page](../../tests/test_source_check_api.py#L125) (Zeile 125)
- [test_v4_topic_binds_requested_run_even_when_answer_is_identical](../../tests/test_source_check_api.py#L143) (Zeile 143)

</details>

<a id="test-source-check-jobs-py"></a>

## test_source_check_jobs.py

**Quelle:** [tests/test_source_check_jobs.py](../../tests/test_source_check_jobs.py) · **Bereiche:** Authentifizierung, Jobs, Quellenprüfung.

**Ebene:** Job-Worker mit FakeDb/Fetch/Judge und simulierten Workeridentitäten.

**Lauf:** 23 bestanden.

**Geprüftes Verhalten:** Serialisierter Plan, eigene Keys nur im Speicher, Fertigstellung ohne Replay, Restart/Expiry/Owner-Resume ohne Developerfallback. Dreimalige transiente Fetch-Retry versus permanente/bezahlt fehlgeschlagene Calls, ownergebundener Verdictcache und eingefrorenes Modell. Worker-Affinität/Heartbeat/Queue-Rotation/Fairness, Nodewechsel bei queued aber nicht running und keine Starvation.

**Grenzen und Doubles:** Prozess-/Nodewechsel werden durch Worker-ID/Keymap-Änderung simuliert; kein echter Mehrprozess-/Netzausfall.

**Prüfauftrag für den Folgeaudit:** Reale Prozessabbrüche und nodeübergreifender Credential-Resume mit Emulator/Operations abgleichen.

**Direkte Codeverweise:** [app/services/source_check_jobs.py](../../app/services/source_check_jobs.py), [app/services/source_check_repository.py](../../app/services/source_check_repository.py), [app/services/source_documents.py](../../app/services/source_documents.py), [app/services/source_verification.py](../../app/services/source_verification.py).

**Direkte Testhelfer:** [tests/test_source_check_repository.py](../../tests/test_source_check_repository.py).

<details>
<summary>22 Testdefinitionen und ihre Quellstellen</summary>

- [test_admission_persists_complete_plan_and_only_memory_contains_own_credentials](../../tests/test_source_check_jobs.py#L58) (Zeile 58)
- [test_worker_completes_job_then_never_replays_and_forgets_key](../../tests/test_source_check_jobs.py#L69) (Zeile 69)
- [test_restart_pauses_own_key_work_without_developer_fallback_then_owner_resumes](../../tests/test_source_check_jobs.py#L80) (Zeile 80)
- [test_expired_or_wrong_owner_memory_key_never_used](../../tests/test_source_check_jobs.py#L98) (Zeile 98)
- [test_heartbeat_removes_expired_key_without_new_submission_or_paid_call](../../tests/test_source_check_jobs.py#L106) (Zeile 106)
- [test_transient_fetch_retries_only_three_times_and_leaves_explicit_result](../../tests/test_source_check_jobs.py#L124) (Zeile 124)
- [test_permanent_fetch_failure_does_not_retry](../../tests/test_source_check_jobs.py#L147) (Zeile 147)
- [test_paid_judge_failure_is_never_automatically_retried](../../tests/test_source_check_jobs.py#L156) (Zeile 156)
- [test_shared_verdict_cache_skips_paid_call_and_separates_owner_question_and_model](../../tests/test_source_check_jobs.py#L169) (Zeile 169)
- [test_owner_busy_does_not_prevent_another_owner_progress](../../tests/test_source_check_jobs.py#L194) (Zeile 194)
- [test_queued_job_keeps_admitted_model_after_admin_change](../../tests/test_source_check_jobs.py#L206) (Zeile 206)
- [test_repeatedly_interrupted_package_gets_complete_terminal_shape](../../tests/test_source_check_jobs.py#L234) (Zeile 234)
- [test_cache_write_failure_preserves_successful_checked_result](../../tests/test_source_check_jobs.py#L248) (Zeile 248)
- [test_context_restores_prior_owner_and_no_uncited_job_is_created](../../tests/test_source_check_jobs.py#L256) (Zeile 256)
- [test_different_live_process_cannot_claim_or_pause_own_key_job](../../tests/test_source_check_jobs.py#L269) (Zeile 269)
- [test_dead_process_affinity_pauses_without_attempt_or_credential_fallback](../../tests/test_source_check_jobs.py#L289) (Zeile 289)
- [test_resume_on_another_http_node_transfers_queued_work_without_sticky_routing](../../tests/test_source_check_jobs.py#L307) (Zeile 307)
- [test_resume_on_other_node_does_not_transfer_running_package](../../tests/test_source_check_jobs.py#L331) (Zeile 331)
- [test_expired_affinity_cannot_steal_unexpired_running_package](../../tests/test_source_check_jobs.py#L345) (Zeile 345)
- [test_rotating_queue_scan_reaches_job_after_more_than_24_foreign_live_jobs](../../tests/test_source_check_jobs.py#L357) (Zeile 357)
- [test_queue_scan_retains_unconsumed_ready_batch_for_other_workers](../../tests/test_source_check_jobs.py#L380) (Zeile 380)
- [test_queue_scan_wraps_to_previously_busy_owner_without_starvation](../../tests/test_source_check_jobs.py#L388) (Zeile 388)

</details>

<a id="test-source-check-repository-py"></a>

## test_source_check_repository.py

**Quelle:** [tests/test_source_check_repository.py](../../tests/test_source_check_repository.py) · **Bereiche:** Jobs, Persistenz, Quellenprüfung.

**Ebene:** Repository mit lockbasiertem FakeDb und Threads.

**Lauf:** 36 bestanden.

**Geprüftes Verhalten:** Atomare/idempotente Planablage, genau ein Claimwinner, Expiry/Stale-Lease-Fencing, Owner/Tombstones, vollständige Pending-/Result-Pagination mit Revisionkontrolle und korrekten Counts. Credential-Pause, Referenz-Retention/Cascade/Cleanup, ungültige Ergebnisidentität, Queue-/Workerprotokoll-/Environmenttrennung, Legacy-Lesbarkeit und bereinigte Retrydiagnostik.

**Grenzen und Doubles:** Fake-Queries/Locks bilden SDK und Transaktionen nach; keine tatsächlichen Firestore-RPCs. Cleanup-/Retention-Rennen sind gezielt simuliert.

**Prüfauftrag für den Folgeaudit:** Real-SDK-Transaktionen, Queryindexes und verteilter Cleanup/Retain-Konflikt gesondert abgleichen.

**Direkte Codeverweise:** [app/services/persistence_guard.py](../../app/services/persistence_guard.py), [app/services/source_check_repository.py](../../app/services/source_check_repository.py).

<details>
<summary>31 Testdefinitionen und ihre Quellstellen</summary>

- [test_create_is_atomic_idempotent_and_persists_every_package_without_credentials](../../tests/test_source_check_repository.py#L181) (Zeile 181)
- [test_only_one_parallel_worker_claims_and_terminal_packages_are_not_replayed](../../tests/test_source_check_repository.py#L200) (Zeile 200)
- [test_expired_lease_reclaims_unfinished_package_and_rejects_stale_worker](../../tests/test_source_check_repository.py#L214) (Zeile 214)
- [test_owner_scope_and_invalid_job_ids_are_not_disclosed](../../tests/test_source_check_repository.py#L230) (Zeile 230)
- [test_account_tombstone_fences_creation_claim_finish_and_cache](../../tests/test_source_check_repository.py#L242) (Zeile 242)
- [test_pagination_covers_every_pending_pair_and_rejects_revision_changes](../../tests/test_source_check_repository.py#L256) (Zeile 256)
- [test_progress_counts_sources_only_after_all_their_packages_finish](../../tests/test_source_check_repository.py#L277) (Zeile 277)
- [test_credentials_pause_preserves_work_and_only_owner_can_resume](../../tests/test_source_check_repository.py#L302) (Zeile 302)
- [test_due_excludes_terminal_null_timestamps_before_limit](../../tests/test_source_check_repository.py#L315) (Zeile 315)
- [test_owner_deletion_cascades_plans_results_and_cache_and_stale_workers_cannot_resurrect](../../tests/test_source_check_repository.py#L323) (Zeile 323)
- [test_page_detects_commit_during_assembly](../../tests/test_source_check_repository.py#L341) (Zeile 341)
- [test_cache_is_owner_partitioned_and_expired_items_are_ignored](../../tests/test_source_check_repository.py#L356) (Zeile 356)
- [test_deleted_chat_parent_fences_inflight_results_but_retained_bookmark_can_continue](../../tests/test_source_check_repository.py#L366) (Zeile 366)
- [test_cleanup_retains_live_references_and_deletes_unreferenced_results](../../tests/test_source_check_repository.py#L383) (Zeile 383)
- [test_claim_exposes_running_status_and_advances_snapshot_revision](../../tests/test_source_check_repository.py#L399) (Zeile 399)
- [test_repeated_missing_credentials_do_not_consume_worker_crash_attempts](../../tests/test_source_check_repository.py#L408) (Zeile 408)
- [test_incomplete_duplicate_or_wrong_package_results_never_lose_planned_pairs](../../tests/test_source_check_repository.py#L419) (Zeile 419)
- [test_mismatched_result_identity_cannot_validate_a_source](../../tests/test_source_check_repository.py#L440) (Zeile 440)
- [test_checked_statement_waits_for_all_its_source_pairs_and_content_version_ignores_fetch_time](../../tests/test_source_check_repository.py#L452) (Zeile 452)
- [test_retained_private_share_allows_work_after_chat_deletion_but_revoked_share_does_not](../../tests/test_source_check_repository.py#L472) (Zeile 472)
- [test_legacy_bookmark_does_not_need_to_exist_at_enqueue](../../tests/test_source_check_repository.py#L487) (Zeile 487)
- [test_retain_refuses_deleting_job_and_deleted_resource_and_nested_turn_cannot_bypass_parent](../../tests/test_source_check_repository.py#L493) (Zeile 493)
- [test_cleanup_deletion_rechecks_concurrent_retention_and_revoked_references](../../tests/test_source_check_repository.py#L512) (Zeile 512)
- [test_due_snapshot_cursor_covers_ties_after_cursor_document_deleted](../../tests/test_source_check_repository.py#L527) (Zeile 527)
- [test_old_global_worker_cannot_see_new_jobs_and_environments_cannot_claim_each_other](../../tests/test_source_check_repository.py#L557) (Zeile 557)
- [test_legacy_and_foreign_polling_retention_and_owner_deletion_remain_available](../../tests/test_source_check_repository.py#L580) (Zeile 580)
- [test_cleanup_covers_expired_jobs_in_both_environments_and_legacy](../../tests/test_source_check_repository.py#L606) (Zeile 606)
- [test_own_key_resume_rejects_foreign_and_legacy_queue_without_retargeting](../../tests/test_source_check_repository.py#L619) (Zeile 619)
- [test_retry_diagnosis_is_allowlisted_lease_bound_and_cleared_on_finish](../../tests/test_source_check_repository.py#L634) (Zeile 634)
- [test_retry_rejects_untrusted_failure_fields](../../tests/test_source_check_repository.py#L655) (Zeile 655)
- [test_queue_environment_follows_existing_production_detection](../../tests/test_source_check_repository.py#L664) (Zeile 664)

</details>

<a id="test-source-check-scope-py"></a>

## test_source_check_scope.py

**Quelle:** [tests/test_source_check_scope.py](../../tests/test_source_check_scope.py) · **Bereiche:** API, Quellenprüfung, Topics, Watch.

**Ebene:** Produkt-Pipeline-Integration im Mock-LLM-Modus mit verbotenen Source-Hooks.

**Lauf:** 12 bestanden.

**Geprüftes Verhalten:** Watch/Topic/API behalten Konsens/Differences/Quellen, starten aber keine Sourceprüfung. Nicht-Chat-Admission stoppt vor Plan/Write; alte Hintergrundjobs werden ohne Credentials/paid work cancelled; historische Watchreads entfernen Sourceprüfstatus ohne restliche Daten zu verlieren.

**Grenzen und Doubles:** Mock-LLM, FakeDb und verbotene Funktionsdoubles; kein tatsächlicher Schedulerstart.

**Prüfauftrag für den Folgeaudit:** Alle später hinzukommenden Produktpfade auf dieselbe Chat-only-Regel prüfen.

**Direkte Codeverweise:** [app/services/api_consensus_runner.py](../../app/services/api_consensus_runner.py), [app/services/consensus_pipeline.py](../../app/services/consensus_pipeline.py), [app/services/share_snapshots.py](../../app/services/share_snapshots.py), [app/services/source_check_jobs.py](../../app/services/source_check_jobs.py), [app/services/source_check_repository.py](../../app/services/source_check_repository.py), [app/services/source_documents.py](../../app/services/source_documents.py), [app/services/source_verification.py](../../app/services/source_verification.py), [app/services/topic_pipeline.py](../../app/services/topic_pipeline.py), [app/services/watch_scheduler.py](../../app/services/watch_scheduler.py).

**Direkte Testhelfer:** [tests/test_source_check_repository.py](../../tests/test_source_check_repository.py).

<details>
<summary>5 Testdefinitionen und ihre Quellstellen</summary>

- [test_product_runs_keep_consensus_and_differences_without_source_work](../../tests/test_source_check_scope.py#L20) (Zeile 20)
- [test_neutral_analysis_does_not_emit_disabled_or_failed_chat_status](../../tests/test_source_check_scope.py#L50) (Zeile 50)
- [test_non_chat_admission_stops_before_planning_or_persistence](../../tests/test_source_check_scope.py#L65) (Zeile 65)
- [test_preexisting_background_jobs_are_cancelled_without_plan_or_paid_work](../../tests/test_source_check_scope.py#L73) (Zeile 73)
- [test_historical_watch_read_preserves_answer_sources_and_stored_data](../../tests/test_source_check_scope.py#L89) (Zeile 89)

</details>

<a id="test-source-judge-fallback-py"></a>

## test_source_judge_fallback.py

**Quelle:** [tests/test_source_judge_fallback.py](../../tests/test_source_judge_fallback.py) · **Bereiche:** Konten und Tarife, Modelle und Provider, Quellenprüfung.

**Ebene:** Judge-Fallback-/Cache-Unit-Integration mit Transport-Double.

**Lauf:** 15 bestanden.

**Geprüftes Verhalten:** Ein Fallback für definierte Verfügbarkeitsfehler mit gleichem Key/ZDR/Deadline; Credential-/Inhaltsfehler nicht wiederholen. Primärtimeout versus globale Expiry, Gesamtinputbudget, ungültige Evidenz ohne Retry und erhaltener Fallback-Cache-/Attempt-Provenienz ohne Exceptiontext.

**Grenzen und Doubles:** HTTPX-/HTTP-Fehler injiziert, keine echten Timeouts/Provider. Budgetverbrauch wird am lokalen Objekt beobachtet.

**Prüfauftrag für den Folgeaudit:** Reale Cancel-/Transportdeadlines und Änderungen der Cache-/Modellkonfiguration abgleichen.

**Direkte Codeverweise:** [app/services/contradiction_verification.py](../../app/services/contradiction_verification.py), [app/services/llm/engines.py](../../app/services/llm/engines.py), [app/services/llm/provider_runtime.py](../../app/services/llm/provider_runtime.py), [app/services/source_check_jobs.py](../../app/services/source_check_jobs.py), [app/services/source_check_repository.py](../../app/services/source_check_repository.py), [app/services/source_verification.py](../../app/services/source_verification.py).

**Direkte Testhelfer:** [tests/test_contradiction_verification.py](../../tests/test_contradiction_verification.py), [tests/test_source_check_repository.py](../../tests/test_source_check_repository.py).

<details>
<summary>7 Testdefinitionen und ihre Quellstellen</summary>

- [test_unavailable_primary_uses_one_fallback_same_key_and_bound_budget](../../tests/test_source_judge_fallback.py#L28) (Zeile 28)
- [test_credentials_and_invalid_content_do_not_trigger_fallback](../../tests/test_source_judge_fallback.py#L50) (Zeile 50)
- [test_primary_attempt_timeout_can_fallback_but_global_expiry_cannot](../../tests/test_source_judge_fallback.py#L61) (Zeile 61)
- [test_second_input_must_fit_total_budget](../../tests/test_source_judge_fallback.py#L79) (Zeile 79)
- [test_invalid_evidence_is_diagnosed_and_never_retried](../../tests/test_source_judge_fallback.py#L94) (Zeile 94)
- [test_successful_fallback_provenance_survives_cache_and_model_selection_change](../../tests/test_source_judge_fallback.py#L110) (Zeile 110)
- [test_both_attempt_failures_are_preserved_without_exception_text](../../tests/test_source_judge_fallback.py#L131) (Zeile 131)

</details>

<a id="test-source-model-configuration-py"></a>

## test_source_model_configuration.py

**Quelle:** [tests/test_source_model_configuration.py](../../tests/test_source_model_configuration.py) · **Bereiche:** Admin, Quellenprüfung.

**Ebene:** Admin-/Konfigurations-Runtime mit DB-Doubles.

**Lauf:** 28 bestanden.

**Geprüftes Verhalten:** Registrierte OpenRouter-IDs für Primärmodell/opt-in Fallback, Metadaten/Dependencies und keine ENV-Übersteuerung; ungültige/doppelte Wahl vor Write, Legacy-Saves erhalten aktive Wahl, Backfill/Read-only-GET und gemeinsamer Rollback nach Aktivierungsfehler.

**Grenzen und Doubles:** Persistenz gemockt; keine UI-Interaktion oder externe Modellverfügbarkeit.

**Prüfauftrag für den Folgeaudit:** Admin-Frontend-Roundtrip und konkurrierende Saves mit Konfigurationsdateien abgleichen.

**Direkte Codeverweise:** [app/api/routers/admin.py](../../app/api/routers/admin.py), [app/core/config.py](../../app/core/config.py), [app/services/source_verification.py](../../app/services/source_verification.py).

<details>
<summary>13 Testdefinitionen und ihre Quellstellen</summary>

- [test_default_is_gemini_and_env_does_not_override_admin](../../tests/test_source_model_configuration.py#L29) (Zeile 29)
- [test_metadata_and_dependencies_use_real_openrouter_ids](../../tests/test_source_model_configuration.py#L37) (Zeile 37)
- [test_invalid_explicit_admin_choice_is_rejected_before_write](../../tests/test_source_model_configuration.py#L48) (Zeile 48)
- [test_admin_save_persists_choice_and_legacy_tab_preserves_active_choice](../../tests/test_source_model_configuration.py#L60) (Zeile 60)
- [test_database_load_defaults_and_backfills_missing_or_invalid_choice](../../tests/test_source_model_configuration.py#L76) (Zeile 76)
- [test_read_only_get_defaults_without_writing](../../tests/test_source_model_configuration.py#L95) (Zeile 95)
- [test_runtime_reload_rolls_back_source_choice_when_later_activation_fails](../../tests/test_source_model_configuration.py#L106) (Zeile 106)
- [test_fallback_is_opt_in_and_uses_registered_ids_without_environment_override](../../tests/test_source_model_configuration.py#L121) (Zeile 121)
- [test_invalid_or_duplicate_fallback_is_rejected_without_write](../../tests/test_source_model_configuration.py#L133) (Zeile 133)
- [test_fallback_save_and_legacy_admin_tab_preservation](../../tests/test_source_model_configuration.py#L145) (Zeile 145)
- [test_fallback_database_load_migration_and_duplicate_normalization](../../tests/test_source_model_configuration.py#L162) (Zeile 162)
- [test_failed_reload_restores_both_primary_and_fallback](../../tests/test_source_model_configuration.py#L180) (Zeile 180)
- [test_fallback_dependency_and_read_only_get_metadata](../../tests/test_source_model_configuration.py#L198) (Zeile 198)

</details>

<a id="test-source-verification-py"></a>

## test_source_verification.py

**Quelle:** [tests/test_source_verification.py](../../tests/test_source_verification.py) · **Bereiche:** Konsens und Unterschiede, Quellenprüfung, Sicherheit.

**Ebene:** Verifikations-/Dokument-/Pipeline-Integration mit Fetch/Judge/HTTPX-Doubles und Threads.

**Lauf:** 122 bestanden.

**Geprüftes Verhalten:** V3-Beleg-/Topic-/Zeitstatus, strikte Originalzitate/IDs/Hardlimits und konservative Cutoff-/Fehlerzustände; sichtbare Citation-Paare, paketierte große Kataloge, deduplizierter Fetch, Input-/Zeitreserve und incremental merge. Snapshot-Version/Legacy/Rehydration, Passageauswahl/Qualifikationen und HTML-Extraktion. SSRF-Adress/DNS/Redirect/IP/Host/SNI-Regeln, Portgates, komprimierte Ausgabe, Singleflight/defensive/negative Caches.

**Grenzen und Doubles:** Judgeergebnisse synthetisch; Datasettest prüft Schema/erwartete Labels, führt keinen LLM-Evaluationslauf aus. DNS/HTTP sind ersetzt; keine echte TLS-Verbindung. Begrenzte Ausgabe belegt nicht alle Speicher-/Dekompressionsgrenzen.

**Prüfauftrag für den Folgeaudit:** Adversariale Dokumente, echte TLS-/Redirectpfade und semantische Source-Goldstandard-Evaluation gesondert abgleichen.

**Direkte Codeverweise:** [app/services/consensus_pipeline.py](../../app/services/consensus_pipeline.py), [app/services/share_snapshots.py](../../app/services/share_snapshots.py), [app/services/source_documents.py](../../app/services/source_documents.py), [app/services/source_verification.py](../../app/services/source_verification.py), [scripts/evaluate_source_verification.py](../../scripts/evaluate_source_verification.py).

<details>
<summary>62 Testdefinitionen und ihre Quellstellen</summary>

- [test_relevant_and_immutable_input](../../tests/test_source_verification.py#L35) (Zeile 35)
- [test_separate_topical_and_time_results](../../tests/test_source_verification.py#L56) (Zeile 56)
- [test_copyright_and_retrieval_date_cannot_establish_currency](../../tests/test_source_verification.py#L63) (Zeile 63)
- [test_multiple_sources_keep_individual_outcomes_and_deduplicate_fetches](../../tests/test_source_verification.py#L70) (Zeile 70)
- [test_ambiguous_provider_local_source_ids_stay_unchecked](../../tests/test_source_verification.py#L84) (Zeile 84)
- [test_invalid_judge_output_stays_unchecked](../../tests/test_source_verification.py#L95) (Zeile 95)
- [test_reason_soft_prompt_target_does_not_discard_valid_evidence](../../tests/test_source_verification.py#L107) (Zeile 107)
- [test_cosmetic_quote_wrapper_preserves_only_exact_original_span](../../tests/test_source_verification.py#L119) (Zeile 119)
- [test_quote_wrapper_cannot_repair_nonverbatim_evidence](../../tests/test_source_verification.py#L128) (Zeile 128)
- [test_wrapped_quote_has_bounded_formatting_tolerance](../../tests/test_source_verification.py#L134) (Zeile 134)
- [test_extra_exact_quotes_preserve_all_evidence_within_hard_limits](../../tests/test_source_verification.py#L144) (Zeile 144)
- [test_combined_quote_budget_accepts_exact_boundary](../../tests/test_source_verification.py#L158) (Zeile 158)
- [test_quote_structure_and_total_budget_remain_hard_limits](../../tests/test_source_verification.py#L170) (Zeile 170)
- [test_nonverbatim_evidence_is_explicitly_unverified_without_partial_acceptance](../../tests/test_source_verification.py#L179) (Zeile 179)
- [test_exact_evidence_must_also_exist_in_original_document](../../tests/test_source_verification.py#L194) (Zeile 194)
- [test_duplicate_invalid_evidence_remains_schema_failure](../../tests/test_source_verification.py#L205) (Zeile 205)
- [test_duplicate_output_is_not_last_write_wins](../../tests/test_source_verification.py#L215) (Zeile 215)
- [test_topic_only_judgment_without_evidence_cannot_establish_support](../../tests/test_source_verification.py#L223) (Zeile 223)
- [test_truncated_provider_response_retains_only_complete_validated_pairs](../../tests/test_source_verification.py#L236) (Zeile 236)
- [test_invalid_or_empty_cutoff_response_is_not_repaired](../../tests/test_source_verification.py#L257) (Zeile 257)
- [test_slow_fetches_reserve_time_for_the_judge](../../tests/test_source_verification.py#L264) (Zeile 264)
- [test_timeout_is_reported_without_leaking_provider_details](../../tests/test_source_verification.py#L282) (Zeile 282)
- [test_negative_fit_requires_short_verifiable_evidence](../../tests/test_source_verification.py#L291) (Zeile 291)
- [test_only_visible_consensus_citations_reach_fetch_judge_and_snapshot](../../tests/test_source_verification.py#L296) (Zeile 296)
- [test_uncited_available_sources_never_trigger_a_check](../../tests/test_source_verification.py#L313) (Zeile 313)
- [test_cost_budget_sends_each_excerpt_and_claim_once_without_context_or_offsets](../../tests/test_source_verification.py#L321) (Zeile 321)
- [test_fetch_error_and_limits_do_not_call_judge_without_text](../../tests/test_source_verification.py#L344) (Zeile 344)
- [test_missing_output_and_failure_are_advisory](../../tests/test_source_verification.py#L357) (Zeile 357)
- [test_setup_failure_cannot_escape_into_consensus](../../tests/test_source_verification.py#L366) (Zeile 366)
- [test_hard_input_limit_is_explicit_and_claim_target_does_not_skip_sources](../../tests/test_source_verification.py#L374) (Zeile 374)
- [test_sentence_ids_repeated_text_tables_and_uncited_scope](../../tests/test_source_verification.py#L382) (Zeile 382)
- [test_pipeline_starts_verification_after_successful_differences](../../tests/test_source_verification.py#L393) (Zeile 393)
- [test_private_addresses_blocked](../../tests/test_source_verification.py#L425) (Zeile 425)
- [test_dns_mixed_answers_fail_closed](../../tests/test_source_verification.py#L429) (Zeile 429)
- [test_fetch_pins_ip_and_checks_redirect_again](../../tests/test_source_verification.py#L436) (Zeile 436)
- [test_pinned_target_preserves_canonical_host_and_tls_name](../../tests/test_source_verification.py#L463) (Zeile 463)
- [test_pinned_target_rejects_nonstandard_ports_before_dns](../../tests/test_source_verification.py#L477) (Zeile 477)
- [test_fetch_follows_canonical_redirect_without_default_port_loop](../../tests/test_source_verification.py#L483) (Zeile 483)
- [test_compressed_body_is_bounded_before_expansion_and_cached](../../tests/test_source_verification.py#L507) (Zeile 507)
- [test_metadata_provenance_context_and_no_invented_date](../../tests/test_source_verification.py#L524) (Zeile 524)
- [test_source_result_arrives_while_differences_are_blocked](../../tests/test_source_verification.py#L533) (Zeile 533)
- [test_pending_share_and_bookmark_rehydration_preserve_snapshot](../../tests/test_source_verification.py#L547) (Zeile 547)
- [test_evidence_verdicts_are_distinct_and_quoted](../../tests/test_source_verification.py#L564) (Zeile 564)
- [test_each_evidence_judgment_requires_original_passages](../../tests/test_source_verification.py#L573) (Zeile 573)
- [test_all_cited_sources_and_pairs_survive_many_bounded_packages](../../tests/test_source_verification.py#L579) (Zeile 579)
- [test_same_source_many_statements_fetches_once_and_splits_output_budget](../../tests/test_source_verification.py#L595) (Zeile 595)
- [test_serializable_plan_and_idempotent_incremental_merge](../../tests/test_source_verification.py#L608) (Zeile 608)
- [test_content_version_ignores_retrieval_time_but_changes_with_document](../../tests/test_source_verification.py#L625) (Zeile 625)
- [test_transient_and_permanent_fetch_failures_keep_explicit_records](../../tests/test_source_verification.py#L633) (Zeile 633)
- [test_relevance_selection_finds_late_evidence_and_adjacent_qualification](../../tests/test_source_verification.py#L647) (Zeile 647)
- [test_artificial_excerpt_join_cannot_become_an_original_quote](../../tests/test_source_verification.py#L661) (Zeile 661)
- [test_main_content_extraction_retains_tables_and_removes_navigation](../../tests/test_source_verification.py#L669) (Zeile 669)
- [test_document_singleflight_and_defensive_cache_copies](../../tests/test_source_verification.py#L676) (Zeile 676)
- [test_short_negative_cache_prevents_failure_storm](../../tests/test_source_verification.py#L696) (Zeile 696)
- [test_legacy_v2_snapshot_remains_readable_without_new_evidence_claim](../../tests/test_source_verification.py#L709) (Zeile 709)
- [test_large_durable_snapshot_preserves_bounded_reference_and_summary](../../tests/test_source_verification.py#L717) (Zeile 717)
- [test_large_snapshot_without_valid_durable_identity_is_rejected](../../tests/test_source_verification.py#L739) (Zeile 739)
- [test_supported_without_applicable_time_cannot_reassure](../../tests/test_source_verification.py#L747) (Zeile 747)
- [test_evaluation_dataset_has_complete_v3_expected_verdicts](../../tests/test_source_verification.py#L753) (Zeile 753)
- [test_long_original_claim_is_judged_without_soft_target_truncation](../../tests/test_source_verification.py#L762) (Zeile 762)
- [test_even_unjudgeably_large_claim_attempts_its_cited_document](../../tests/test_source_verification.py#L773) (Zeile 773)
- [test_cached_judge_verdict_is_revalidated_and_does_not_count_a_paid_call](../../tests/test_source_verification.py#L783) (Zeile 783)

</details>

<a id="test-stream-backpressure-py"></a>

## test_stream_backpressure.py

**Quelle:** [tests/test_stream_backpressure.py](../../tests/test_stream_backpressure.py) · **Bereiche:** Runtime, Streaming und Wiederherstellung.

**Ebene:** Lokale Producer-/Consumer-Threadtests.

**Lauf:** 3 bestanden.

**Geprüftes Verhalten:** Begrenzter Puffer bei langsamem Client, Disconnect schließt Producer, festhängender Consumer löst Backpressuretimeout aus und bereits gepufferte Daten bleiben vor terminalem Fehler erhalten.

**Grenzen und Doubles:** Consumer ist lokaler Iterator; kein Socket/Proxy/Browser und kein Lasttest.

**Prüfauftrag für den Folgeaudit:** ASGI-/Proxy-Disconnects und viele parallele langsame Clients mit Streaming/E2E abgleichen.

**Direkte Codeverweise:** [app/services/llm/provider_runtime.py](../../app/services/llm/provider_runtime.py), [app/services/llm/streaming.py](../../app/services/llm/streaming.py).

<details>
<summary>3 Testdefinitionen und ihre Quellstellen</summary>

- [test_slow_client_has_a_bounded_buffer_and_disconnect_releases_producer](../../tests/test_stream_backpressure.py#L9) (Zeile 9)
- [test_stalled_client_times_out_instead_of_holding_a_worker_forever](../../tests/test_stream_backpressure.py#L33) (Zeile 33)
- [test_bounded_buffer_preserves_data_before_terminal_errors](../../tests/test_stream_backpressure.py#L52) (Zeile 52)

</details>

<a id="test-streaming-py"></a>

## test_streaming.py

**Quelle:** [tests/test_streaming.py](../../tests/test_streaming.py) · **Bereiche:** Konsens und Unterschiede, Modelle und Provider, Streaming und Wiederherstellung.

**Ebene:** SSE-/ASGI-/Cancellation-Integration mit Provider-Response-Doubles.

**Lauf:** 27 bestanden.

**Geprüftes Verhalten:** Disconnect schließt Providerressource und stoppt nachfolgende Arbeit; parallele Streams behalten eigene Cancellation. SSE-Roundtrip/Firestorezeit, Delta/Final/Fehler/Contentblocks, OpenRouter-URLs und zero-width Citation-Deduplizierung, Reasoning-only Cutoff, ungültige Engines und begrenzte Konsens-Retries/Leerantwortfehler.

**Grenzen und Doubles:** ASGI-Response wird lokal ausgeführt; Upstream-HTTP gemockt. Kein echter Socket oder Reverseproxy; Keepalive-Timing nicht aus Namen/Importen ableiten.

**Prüfauftrag für den Folgeaudit:** Transportfragmentierung/Browser-Disconnect und Teilantwort-Retrypolitik gegen JS/Provider-Runtime abgleichen.

**Direkte Codeverweise:** [app/services/llm/citations.py](../../app/services/llm/citations.py), [app/services/llm/consensus_engine.py](../../app/services/llm/consensus_engine.py), [app/services/llm/provider_runtime.py](../../app/services/llm/provider_runtime.py), [app/services/llm/streaming.py](../../app/services/llm/streaming.py).

<details>
<summary>27 Testdefinitionen und ihre Quellstellen</summary>

- [ProviderCancellationTests::test_disconnect_closes_active_provider_resource](../../tests/test_streaming.py#L87) (Zeile 87)
- [ProviderCancellationTests::test_sse_response_is_closed_after_normal_exhaustion](../../tests/test_streaming.py#L110) (Zeile 110)
- [ProviderCancellationTests::test_real_asgi_disconnect_closes_model_provider_resource](../../tests/test_streaming.py#L118) (Zeile 118)
- [ProviderCancellationTests::test_real_asgi_disconnect_stops_consensus_before_followup_work](../../tests/test_streaming.py#L144) (Zeile 144)
- [ProviderCancellationTests::test_parallel_streams_keep_their_own_cancellation](../../tests/test_streaming.py#L173) (Zeile 173)
- [ProviderCancellationTests::test_cancelled_provider_wrapper_does_not_emit_a_failure_result](../../tests/test_streaming.py#L220) (Zeile 220)
- [SSEPackTests::test_pack_roundtrip](../../tests/test_streaming.py#L230) (Zeile 230)
- [SSEPackTests::test_pack_normalizes_firestore_timestamp_in_final_metadata](../../tests/test_streaming.py#L237) (Zeile 237)
- [SSEPackTests::test_iter_sse_events_multiple](../../tests/test_streaming.py#L256) (Zeile 256)
- [StreamingModelResponseTests::test_delta_and_final_events](../../tests/test_streaming.py#L269) (Zeile 269)
- [StreamingModelResponseTests::test_error_result_final_event](../../tests/test_streaming.py#L289) (Zeile 289)
- [StreamingModelResponseTests::test_structured_content_blocks_never_serialize_as_object_object](../../tests/test_streaming.py#L304) (Zeile 304)
- [StreamingModelResponseTests::test_generator_exception_yields_error_final](../../tests/test_streaming.py#L326) (Zeile 326)
- [OpenRouterStreamTests::test_delta_final_and_url_citation_use_the_common_contract](../../tests/test_streaming.py#L374) (Zeile 374)
- [OpenRouterStreamTests::test_zero_width_citation_uses_its_stream_position](../../tests/test_streaming.py#L397) (Zeile 397)
- [OpenRouterStreamTests::test_repeated_zero_width_snapshot_does_not_duplicate_a_citation](../../tests/test_streaming.py#L420) (Zeile 420)
- [OpenRouterStreamTests::test_reasoning_only_length_cutoff_is_a_structured_error](../../tests/test_streaming.py#L436) (Zeile 436)
- [OpenRouterStreamTests::test_low_level_parser_accepts_content_blocks_and_done](../../tests/test_streaming.py#L445) (Zeile 445)
- [ConsensusStreamTests::test_invalid_consensus_engine](../../tests/test_streaming.py#L455) (Zeile 455)
- [ConsensusStreamTests::test_differences_without_answers](../../tests/test_streaming.py#L465) (Zeile 465)
- [ConsensusStreamTests::test_invalid_differences_engine](../../tests/test_streaming.py#L475) (Zeile 475)
- [ConsensusStreamTests::test_invalid_engine_final_is_flagged_as_error](../../tests/test_streaming.py#L486) (Zeile 486)
- [ConsensusRetryTests::test_transient_failure_is_retried](../../tests/test_streaming.py#L510) (Zeile 510)
- [ConsensusRetryTests::test_persistent_failure_yields_error_final](../../tests/test_streaming.py#L526) (Zeile 526)
- [ConsensusRetryTests::test_empty_stream_counts_as_failure](../../tests/test_streaming.py#L536) (Zeile 536)
- [ConsensusErrorTextTests::test_error_and_empty_texts_are_detected](../../tests/test_streaming.py#L547) (Zeile 547)
- [ConsensusErrorTextTests::test_normal_answers_are_not_errors](../../tests/test_streaming.py#L554) (Zeile 554)

</details>

<a id="test-telegram-notifier-py"></a>

## test_telegram_notifier.py

**Quelle:** [tests/test_telegram_notifier.py](../../tests/test_telegram_notifier.py) · **Bereiche:** Benachrichtigungen, Datenschutz, Fehlerdiagnostik.

**Ebene:** Notifier-Unit-Tests mit urlopen/send_bot_message-Doubles.

**Lauf:** 9 bestanden.

**Geprüftes Verhalten:** SEO-Review auch ohne Entscheidungen, Judgefehler/Findings, fehlende Konfiguration als skipped. Kritische Fehler redigieren/deduplizieren, sichere Asset-/Codepositionen unterscheiden und Registrierungsalert ohne PII.

**Grenzen und Doubles:** Es werden keine Telegramnachrichten gesendet; HTTP-/Versandfunktion ersetzt. Nur ausgewählte Secretmuster und Dedupe-Situationen.

**Prüfauftrag für den Folgeaudit:** Netzwerkfehler/Timeout/Rate-Limit und Dedupe-TTL/Mehrprozessverhalten separat abgleichen.

**Direkte Codeverweise:** [app/services/telegram_notifier.py](../../app/services/telegram_notifier.py).

<details>
<summary>9 Testdefinitionen und ihre Quellstellen</summary>

- [test_seo_review_notification_is_sent_even_without_open_decisions](../../tests/test_telegram_notifier.py#L17) (Zeile 17)
- [test_seo_review_notification_names_the_judge_failure_and_findings](../../tests/test_telegram_notifier.py#L46) (Zeile 46)
- [test_seo_review_notification_is_recorded_as_skipped_without_config](../../tests/test_telegram_notifier.py#L80) (Zeile 80)
- [test_critical_error_notification_redacts_and_deduplicates](../../tests/test_telegram_notifier.py#L88) (Zeile 88)
- [test_critical_error_message_includes_safe_resource_class](../../tests/test_telegram_notifier.py#L122) (Zeile 122)
- [test_runtime_locations_are_visible_and_deduplicated_separately](../../tests/test_telegram_notifier.py#L137) (Zeile 137)
- [test_asset_names_are_visible_and_deduplicated_separately](../../tests/test_telegram_notifier.py#L157) (Zeile 157)
- [test_new_user_registration_notification_is_pii_free](../../tests/test_telegram_notifier.py#L176) (Zeile 176)
- [test_new_user_registration_notification_is_skipped_without_config](../../tests/test_telegram_notifier.py#L206) (Zeile 206)

</details>

<a id="test-tier-cache-py"></a>

## test_tier_cache.py

**Quelle:** [tests/test_tier_cache.py](../../tests/test_tier_cache.py) · **Bereiche:** Authentifizierung.

**Ebene:** Securitycache mit Fake-Uhr und DB-Mock.

**Lauf:** 7 bestanden.

**Geprüftes Verhalten:** Pro/Admin teilen einen Firestore-Read; Legacy-/fehlende Profile ergeben passende Flags; TTL-Auslauf und explizite Invalidierung laden neu; DB-Fehler werden nicht gecacht; E2E-Mockuser bypassed Datenbank ohne Pro/Adminrechte.

**Grenzen und Doubles:** Kontrollierte TTLCache-Uhr und einfache Firestore-Mocks; keine parallelen Cachemisses oder verteilte Invalidation.

**Prüfauftrag für den Folgeaudit:** Mehrprozess-Tierwechsel und gleichzeitige Fehler-/Erfolgsreads mit account_tier-Tests abgleichen.

**Direkte Codeverweise:** [app/core/security.py](../../app/core/security.py).

<details>
<summary>7 Testdefinitionen und ihre Quellstellen</summary>

- [test_tier_checks_share_one_firestore_read](../../tests/test_tier_cache.py#L38) (Zeile 38)
- [test_flags_derived_like_before](../../tests/test_tier_cache.py#L46) (Zeile 46)
- [test_missing_document_is_not_pro](../../tests/test_tier_cache.py#L63) (Zeile 63)
- [test_cache_expires_after_ttl](../../tests/test_tier_cache.py#L70) (Zeile 70)
- [test_invalidate_tier_cache_forces_fresh_read](../../tests/test_tier_cache.py#L89) (Zeile 89)
- [test_firestore_errors_are_not_cached](../../tests/test_tier_cache.py#L99) (Zeile 99)
- [test_mock_auth_hook_bypasses_firestore](../../tests/test_tier_cache.py#L112) (Zeile 112)

</details>

<a id="test-topic-finding-py"></a>

## test_topic_finding.py

**Quelle:** [tests/test_topic_finding.py](../../tests/test_topic_finding.py) · **Bereiche:** Konsens und Unterschiede, Topics.

**Ebene:** Deterministische View-Unit-Tests.

**Lauf:** 14 bestanden.

**Geprüftes Verhalten:** Längst gehaltener Claim als Finding, Widerspruch/Materialchange-Zustand, Teilmodell-Support, kurze deduplizierte Nebenzeilen, redaktioneller Vorrang und Konsenssatzfallback. Ganze statt abgeschnittener Sätze, Langmarkierung, keine Fragmente und forming statt settled bei dünner Historie.

**Grenzen und Doubles:** Synthetischer Ledger/Record; keine echte Claimextraktion, Judgequalität oder Browserdarstellung.

**Prüfauftrag für den Folgeaudit:** Mehrsprachige Satzenden, redaktionelle Konflikte und reale lange Topic-Historien abgleichen.

**Direkte Codeverweise:** [app/services/topic_finding.py](../../app/services/topic_finding.py).

<details>
<summary>14 Testdefinitionen und ihre Quellstellen</summary>

- [test_the_finding_is_the_claim_the_record_puts_first](../../tests/test_topic_finding.py#L40) (Zeile 40)
- [test_a_contested_claim_never_becomes_the_finding](../../tests/test_topic_finding.py#L60) (Zeile 60)
- [test_a_check_that_moved_the_answer_outranks_every_other_state](../../tests/test_topic_finding.py#L78) (Zeile 78)
- [test_a_claim_only_some_models_state_says_so_in_the_finding](../../tests/test_topic_finding.py#L88) (Zeile 88)
- [test_supporting_lines_never_repeat_the_finding_or_run_long](../../tests/test_topic_finding.py#L98) (Zeile 98)
- [test_an_editorial_headline_wins_over_the_derived_one](../../tests/test_topic_finding.py#L119) (Zeile 119)
- [test_a_topic_without_a_position_map_still_states_an_answer](../../tests/test_topic_finding.py#L130) (Zeile 130)
- [test_a_run_with_nothing_to_state_produces_no_finding](../../tests/test_topic_finding.py#L147) (Zeile 147)
- [test_a_long_claim_stays_one_sentence_and_is_marked_as_long](../../tests/test_topic_finding.py#L152) (Zeile 152)
- [test_a_clipped_claim_is_restated_from_the_consensus_it_came_from](../../tests/test_topic_finding.py#L166) (Zeile 166)
- [test_a_clipped_claim_with_no_match_falls_back_to_a_whole_sentence](../../tests/test_topic_finding.py#L190) (Zeile 190)
- [test_a_mid_sentence_fragment_is_never_the_finding_or_a_supporting_line](../../tests/test_topic_finding.py#L203) (Zeile 203)
- [test_a_claim_that_held_through_a_fraction_of_the_record_is_not_settled](../../tests/test_topic_finding.py#L218) (Zeile 218)
- [test_a_statement_that_ends_inside_a_quotation_keeps_one_full_stop](../../tests/test_topic_finding.py#L238) (Zeile 238)

</details>

<a id="test-topics-feature-py"></a>

## test_topics_feature.py

**Quelle:** [tests/test_topics_feature.py](../../tests/test_topics_feature.py) · **Bereiche:** Benachrichtigungen, Persistenz, Quellenprüfung, SEO, Topics.

**Ebene:** Große Service-/Router-/SSR-Suite mit FakeFirestore; einzelner echter SDK-Queryaufbau mit RPC-Mock.

**Lauf:** 58 bestanden.

**Geprüftes Verhalten:** Begrenzte historische Reads inkl. Legacy-/Timestamp-/Count-Snapshot, unveränderliche Runversionen und Pointer-Atomizität/Stale-Claim. Archiv/Index/Slug-Rename/Reservierung, Quellenrollen/Canonicalisierung/100 Quellen/ID-Erhalt. Double-opt-in, Challenge-Atomizität, Delivery-Dedupe/Cleanup/Tombstones, Mockmodus ohne Publish; automatische Pipeline/Claimidentity-Fallback. Admin-CRUD, öffentliche Historie/Finding/Claimledger/Positionmap und unscored/historische noindex-Seiten.

**Grenzen und Doubles:** Fachlogik/SSR real, DB/LLM/Mail ersetzt. SDKfall prüft RPC-Aufbau, nicht Dienstverhalten; Quellrollen sind URLheuristiken, keine inhaltliche Qualitätsprüfung.

**Prüfauftrag für den Folgeaudit:** Echte konkurrierende Slug-/Run-/Followertransaktionen und Browser-Historiennavigation abgleichen.

**Direkte Codeverweise:** [app/api/routers/pages.py](../../app/api/routers/pages.py), [app/api/routers/topics.py](../../app/api/routers/topics.py), [app/core/rate_limit.py](../../app/core/rate_limit.py), [app/services/account_deletion.py](../../app/services/account_deletion.py), [app/services/follow_challenges.py](../../app/services/follow_challenges.py), [app/services/mailer.py](../../app/services/mailer.py), [app/services/topic_pipeline.py](../../app/services/topic_pipeline.py), [app/services/topic_runner.py](../../app/services/topic_runner.py), [app/services/topics.py](../../app/services/topics.py).

<details>
<summary>45 Testdefinitionen und ihre Quellstellen</summary>

- [test_list_runs_bounds_long_histories_and_preserves_ascending_chronology](../../tests/test_topics_feature.py#L186) (Zeile 186)
- [test_list_runs_keeps_legacy_missing_dates_and_versions](../../tests/test_topics_feature.py#L197) (Zeile 197)
- [test_list_runs_short_complete_history_uses_count_instead_of_document_rescan](../../tests/test_topics_feature.py#L209) (Zeile 209)
- [test_list_runs_count_proof_uses_same_snapshot_during_deletion](../../tests/test_topics_feature.py#L219) (Zeile 219)
- [test_list_runs_rejects_invalid_counts_without_expensive_fallback](../../tests/test_topics_feature.py#L237) (Zeile 237)
- [test_list_runs_count_failure_does_not_fall_back_to_a_full_scan](../../tests/test_topics_feature.py#L245) (Zeile 245)
- [test_list_runs_sdk_count_is_unfiltered_and_shares_read_only_transaction](../../tests/test_topics_feature.py#L253) (Zeile 253)
- [test_list_runs_resolves_timestamp_boundary_by_version_and_document_id](../../tests/test_topics_feature.py#L285) (Zeile 285)
- [test_list_runs_ignores_missing_dates_when_newer_window_is_full](../../tests/test_topics_feature.py#L293) (Zeile 293)
- [test_list_runs_query_failure_is_not_hidden_by_a_full_scan](../../tests/test_topics_feature.py#L302) (Zeile 302)
- [test_list_runs_invalid_legacy_timestamp_uses_original_sorting](../../tests/test_topics_feature.py#L310) (Zeile 310)
- [test_topic_runs_are_immutable_and_keep_historical_editorial_state](../../tests/test_topics_feature.py#L368) (Zeile 368)
- [test_topic_run_and_latest_pointer_commit_or_fail_together](../../tests/test_topics_feature.py#L414) (Zeile 414)
- [test_stale_topic_claim_cannot_publish_or_mark_newer_claim_failed](../../tests/test_topics_feature.py#L432) (Zeile 432)
- [test_archived_topics_leave_public_discovery_and_reject_new_runs](../../tests/test_topics_feature.py#L462) (Zeile 462)
- [test_noindex_and_unpublished_topics_are_not_in_topic_sitemap](../../tests/test_topics_feature.py#L485) (Zeile 485)
- [test_slug_uniqueness_and_evidence_url_validation](../../tests/test_topics_feature.py#L509) (Zeile 509)
- [test_renamed_topic_keeps_its_runs_and_redirects_the_old_url](../../tests/test_topics_feature.py#L536) (Zeile 536)
- [test_a_retired_slug_cannot_be_claimed_and_can_be_taken_back](../../tests/test_topics_feature.py#L576) (Zeile 576)
- [test_evidence_sources_receive_specific_public_roles](../../tests/test_topics_feature.py#L610) (Zeile 610)
- [test_google_redirects_are_unwrapped_or_flagged_as_indirect](../../tests/test_topics_feature.py#L614) (Zeile 614)
- [test_automatic_evidence_orders_direct_sources_before_rumors](../../tests/test_topics_feature.py#L625) (Zeile 625)
- [test_topic_evidence_keeps_citation_ids_when_quality_sort_changes_order](../../tests/test_topics_feature.py#L634) (Zeile 634)
- [test_topic_evidence_preserves_more_than_eighty_sources_and_case_sensitive_paths](../../tests/test_topics_feature.py#L646) (Zeile 646)
- [test_topic_evidence_legacy_ids_skip_explicit_ids_and_conflicts_fail_explicitly](../../tests/test_topics_feature.py#L656) (Zeile 656)
- [test_topic_followers_use_separate_collection_and_double_opt_in](../../tests/test_topics_feature.py#L665) (Zeile 665)
- [test_topic_account_cleanup_invalidates_outstanding_confirm_link](../../tests/test_topics_feature.py#L695) (Zeile 695)
- [test_topic_confirm_consumes_challenge_atomically_with_follower_write](../../tests/test_topics_feature.py#L709) (Zeile 709)
- [test_topic_notification_delivery_is_deduplicated_and_multipart](../../tests/test_topics_feature.py#L738) (Zeile 738)
- [test_topic_delivery_claim_requires_a_live_topic_bound_follower](../../tests/test_topics_feature.py#L774) (Zeile 774)
- [test_topic_delivery_finish_does_not_recreate_a_cleaned_claim](../../tests/test_topics_feature.py#L789) (Zeile 789)
- [test_account_deletion_fences_claims_before_topic_delivery_cleanup](../../tests/test_topics_feature.py#L808) (Zeile 808)
- [test_topic_templates_expose_timeline_evidence_follow_and_admin_controls](../../tests/test_topics_feature.py#L825) (Zeile 825)
- [test_legacy_topic_admin_url_redirects_into_main_admin](../../tests/test_topics_feature.py#L863) (Zeile 863)
- [test_mock_llm_instances_never_publish_topic_runs](../../tests/test_topics_feature.py#L875) (Zeile 875)
- [test_automatic_topic_run_researches_sources_and_builds_timeline_point](../../tests/test_topics_feature.py#L898) (Zeile 898)
- [test_topic_run_carries_the_tracked_claims_into_the_identity_judge](../../tests/test_topics_feature.py#L942) (Zeile 942)
- [test_claim_identity_falls_back_to_fresh_keys_when_the_judge_is_unavailable](../../tests/test_topics_feature.py#L998) (Zeile 998)
- [test_claim_identity_result_maps_claims_onto_the_keys_they_continue](../../tests/test_topics_feature.py#L1019) (Zeile 1019)
- [test_admin_topic_api_creates_updates_and_versions_without_share_data](../../tests/test_topics_feature.py#L1037) (Zeile 1037)
- [test_topic_page_shows_the_position_map_and_agreement_history](../../tests/test_topics_feature.py#L1087) (Zeile 1087)
- [test_topic_page_keeps_unscored_latest_run_and_its_position_map](../../tests/test_topics_feature.py#L1134) (Zeile 1134)
- [test_topic_page_leads_with_the_finding_and_folds_unchanged_checks](../../tests/test_topics_feature.py#L1156) (Zeile 1156)
- [test_public_topic_history_is_ssr_and_historical_version_is_noindex](../../tests/test_topics_feature.py#L1246) (Zeile 1246)
- [test_disagreement_leads_the_statement_list_and_is_labelled_as_its_own_kind](../../tests/test_topics_feature.py#L1282) (Zeile 1282)

</details>

<a id="test-unscored-history-py"></a>

## test_unscored_history.py

**Quelle:** [tests/test_unscored_history.py](../../tests/test_unscored_history.py) · **Bereiche:** Bookmarks und Verlauf, Topics, Watch.

**Ebene:** Service-/View-Unit-Integration mit FakeDb.

**Lauf:** 3 bestanden.

**Geprüftes Verhalten:** Unbewerteter abgeschlossener Watch bleibt als Changed-Ereignis sichtbar; Historie/Position-Map bleibt erhalten, Chartlinie bricht an null statt erfundenem Score. Topic-Version begrenzt Historie vor künftigen Runs.

**Grenzen und Doubles:** Künstliche Historypunkte/DB, keine tatsächliche Browser-Chartdarstellung.

**Prüfauftrag für den Folgeaudit:** Mehrere aufeinanderfolgende unscored Runs und Versionsnavigation im Browser abgleichen.

**Direkte Codeverweise:** [app/api/routers/share.py](../../app/api/routers/share.py), [app/api/routers/topics.py](../../app/api/routers/topics.py), [app/services/history_view.py](../../app/services/history_view.py), [app/services/share_snapshots.py](../../app/services/share_snapshots.py), [app/services/watch_service.py](../../app/services/watch_service.py).

**Direkte Testhelfer:** [tests/test_watch_feature.py](../../tests/test_watch_feature.py).

<details>
<summary>3 Testdefinitionen und ihre Quellstellen</summary>

- [test_completed_unscored_watch_remains_visible_and_changed](../../tests/test_unscored_history.py#L18) (Zeile 18)
- [test_history_keeps_unscored_events_and_maps_but_breaks_the_chart_line](../../tests/test_unscored_history.py#L47) (Zeile 47)
- [test_topic_history_retains_unscored_selected_version_without_future_runs](../../tests/test_unscored_history.py#L64) (Zeile 64)

</details>

<a id="test-usage-authorization-py"></a>

## test_usage_authorization.py

**Quelle:** [tests/test_usage_authorization.py](../../tests/test_usage_authorization.py) · **Bereiche:** Konten und Tarife, Persistenz.

**Ebene:** Atomare Autorisierungslogik mit FakeFirestore und Threads.

**Lauf:** 19 bestanden.

**Geprüftes Verhalten:** Drei Reads pro Autorisierung, 18 für sechs Provider/ein Charge; genau ein Gewinner derselben Operation, tägliches Limit bei konkurrierenden Runs, Konflikt/Expiry/Release ohne Writes, Deep-Limit, reservierte Limits bei Konfigwechsel, Owner-/UTC-Isolation, Tombstone zuerst und korrupte Counter fail-closed.

**Grenzen und Doubles:** Lesebudget stammt aus instrumentiertem Fake, nicht aus echten RPC-/Abrechnungsdaten. Lokale Serialisierung ersetzt Firestore.

**Prüfauftrag für den Folgeaudit:** SDK-/Emulator-Transaktionsread-Vertrag und Limits unter Mehrprozesslast prüfen.

**Direkte Codeverweise:** [app/services/persistence_guard.py](../../app/services/persistence_guard.py), [app/services/usage_repository.py](../../app/services/usage_repository.py).

**Direkte Testhelfer:** [tests/usage_test_support.py](../../tests/usage_test_support.py).

<details>
<summary>11 Testdefinitionen und ihre Quellstellen</summary>

- [test_three_reads_for_direct_reserved_and_prepared_runs](../../tests/test_usage_authorization.py#L35) (Zeile 35)
- [test_six_provider_fanout_uses_18_reads_and_one_charge](../../tests/test_usage_authorization.py#L54) (Zeile 54)
- [test_same_operation_race_has_exactly_one_authorization](../../tests/test_usage_authorization.py#L68) (Zeile 68)
- [test_distinct_run_race_cannot_exceed_daily_limit](../../tests/test_usage_authorization.py#L80) (Zeile 80)
- [test_conflicts_and_expiry_leave_all_documents_unchanged](../../tests/test_usage_authorization.py#L100) (Zeile 100)
- [test_released_reservation_cannot_authorize_work](../../tests/test_usage_authorization.py#L109) (Zeile 109)
- [test_deep_quota_failure_does_not_consume_total_or_claim](../../tests/test_usage_authorization.py#L119) (Zeile 119)
- [test_changed_limits_preserve_previously_reserved_limits_and_fresh_counters](../../tests/test_usage_authorization.py#L129) (Zeile 129)
- [test_owner_isolation_and_utc_rollover](../../tests/test_usage_authorization.py#L139) (Zeile 139)
- [test_account_deletion_fence_blocks_even_a_prepared_run](../../tests/test_usage_authorization.py#L149) (Zeile 149)
- [test_corrupt_reserved_counter_fails_without_claim](../../tests/test_usage_authorization.py#L161) (Zeile 161)

</details>

<a id="test-usage-limit-ui-py"></a>

## test_usage_limit_ui.py

**Quelle:** [tests/test_usage_limit_ui.py](../../tests/test_usage_limit_ui.py) · **Bereiche:** Frontend, Konten und Tarife.

**Ebene:** Überwiegend Quelltextverträge; ein Asset-Fingerprint-Runtimefall.

**Lauf:** 10 bestanden.

**Geprüftes Verhalten:** Blocked-Karte und Ladereihenfolge/Position, echte Server-Errorcode-Vokabeln, Preflight vor Run-Zulassung, Wiederherstellung des Follow-up-Basiszustands, konservatives Own-Key/Unknown-Budget-Verhalten, gemeinsame Quotadaten, UTC-Reset und Wechsel ohne Deep Think. CSS-Änderung ändert Asset-URL.

**Grenzen und Doubles:** UI-Zustandsübergänge werden überwiegend als Sourcefragmente geprüft, nicht ausgeführt.

**Prüfauftrag für den Folgeaudit:** Preflight gegen serverseitige Rennen und tatsächlich erhaltene Draft-/Quote-Zustände mit JS/E2E abgleichen.

**Direkte Codeverweise:** [app/api/routers/chat.py](../../app/api/routers/chat.py), [app/core/assets.py](../../app/core/assets.py), [static/css/components-input.css](../../static/css/components-input.css), [static/css/shell.css](../../static/css/shell.css), [static/js/consensus-run.js](../../static/js/consensus-run.js), [static/js/query-send.js](../../static/js/query-send.js), [static/js/run-registry.js](../../static/js/run-registry.js), [static/js/run-view.js](../../static/js/run-view.js), [static/js/sidebar-quota.js](../../static/js/sidebar-quota.js), [static/js/usage-limit.js](../../static/js/usage-limit.js), [templates/index.html](../../templates/index.html).

**Direkte Testhelfer:** [tests/frontend_order.py](../../tests/frontend_order.py).

<details>
<summary>10 Testdefinitionen und ihre Quellstellen</summary>

- [test_blocked_card_exists_and_is_loaded_before_its_callers](../../tests/test_usage_limit_ui.py#L26) (Zeile 26)
- [test_blocked_card_sits_where_the_answer_would_be](../../tests/test_usage_limit_ui.py#L49) (Zeile 49)
- [test_server_error_codes_are_actually_matched](../../tests/test_usage_limit_ui.py#L66) (Zeile 66)
- [test_run_is_blocked_before_it_appears_to_start](../../tests/test_usage_limit_ui.py#L85) (Zeile 85)
- [test_blocked_follow_up_gets_its_context_back](../../tests/test_usage_limit_ui.py#L106) (Zeile 106)
- [test_preflight_stays_conservative](../../tests/test_usage_limit_ui.py#L128) (Zeile 128)
- [test_quota_numbers_have_a_single_source](../../tests/test_usage_limit_ui.py#L139) (Zeile 139)
- [test_card_names_the_reset_and_never_sells_anything](../../tests/test_usage_limit_ui.py#L152) (Zeile 152)
- [test_deep_think_exhaustion_offers_the_cheaper_run](../../tests/test_usage_limit_ui.py#L164) (Zeile 164)
- [test_css_cache_busting_needs_no_manual_bump](../../tests/test_usage_limit_ui.py#L180) (Zeile 180)

</details>

<a id="test-user-memory-py"></a>

## test_user_memory.py

**Quelle:** [tests/test_user_memory.py](../../tests/test_user_memory.py) · **Bereiche:** Authentifizierung, Kontext, Nutzergedächtnis.

**Ebene:** Sanitizer-/Repository-/Router-/Prompt-Integration mit Doubles und einem Sourcevertrag.

**Lauf:** 29 bestanden.

**Geprüftes Verhalten:** Feld-/Notizlimits, Whitespace/Controls/Frame-Marker, Enabled/Empty, Profile-Unterordnung unter Evidenz und einmalige Nicht-Persistenzinstruktion. Normalisiertes Save/Legacy-Notizerhalt, Guard-Aufruf, fail-open Reads, Auth/Schema, Clientprompt/Folgekontext/Memory-Opt-out und anonym ohne Read.

**Grenzen und Doubles:** Router-/Provider-/DB-Doubles; Account-Deletion-Unterkollektion wird nur mit inspect.getsource geprüft. Prompttext beweist keine Widerstandsfähigkeit des LLM gegen Injection.

**Prüfauftrag für den Folgeaudit:** Tatsächliche Cascade/Owner-Isolation und Prompt-Injection-Evaluation separat abgleichen.

**Direkte Codeverweise:** [app/api/routers/chat.py](../../app/api/routers/chat.py), [app/api/routers/users.py](../../app/api/routers/users.py), [app/core/config.py](../../app/core/config.py), [app/core/rate_limit.py](../../app/core/rate_limit.py), [app/services/account_deletion.py](../../app/services/account_deletion.py), [app/services/user_memory.py](../../app/services/user_memory.py).

**Direkte Testhelfer:** [tests/usage_test_support.py](../../tests/usage_test_support.py).

<details>
<summary>29 Testdefinitionen und ihre Quellstellen</summary>

- [test_sanitize_collapses_whitespace_and_keeps_line_structure](../../tests/test_user_memory.py#L46) (Zeile 46)
- [test_sanitize_clips_each_field_to_the_documented_limit](../../tests/test_user_memory.py#L55) (Zeile 55)
- [test_sanitize_keeps_the_long_note_structure_and_clips_it_separately](../../tests/test_user_memory.py#L60) (Zeile 60)
- [test_sanitize_strips_prompt_frame_markers](../../tests/test_user_memory.py#L69) (Zeile 69)
- [test_sanitize_drops_control_characters_and_non_strings](../../tests/test_user_memory.py#L79) (Zeile 79)
- [test_enabled_defaults_to_true_and_only_false_turns_it_off](../../tests/test_user_memory.py#L86) (Zeile 86)
- [test_empty_or_paused_profile_renders_nothing](../../tests/test_user_memory.py#L95) (Zeile 95)
- [test_rendered_profile_names_the_fields_and_subordinates_itself_to_evidence](../../tests/test_user_memory.py#L103) (Zeile 103)
- [test_rendered_profile_includes_the_manual_note_without_an_llm_rewrite](../../tests/test_user_memory.py#L111) (Zeile 111)
- [test_a_multiline_field_stays_one_line_in_the_prompt](../../tests/test_user_memory.py#L118) (Zeile 118)
- [test_rendered_content_respects_the_profile_budget](../../tests/test_user_memory.py#L123) (Zeile 123)
- [test_memory_is_appended_to_the_instruction_not_prepended](../../tests/test_user_memory.py#L132) (Zeile 132)
- [test_interactive_memory_boundary_forbids_false_persistence_claims_once](../../tests/test_user_memory.py#L142) (Zeile 142)
- [test_repository_round_trip_normalizes_on_the_way_in](../../tests/test_user_memory.py#L226) (Zeile 226)
- [test_legacy_save_without_notes_preserves_an_existing_long_note](../../tests/test_user_memory.py#L234) (Zeile 234)
- [test_repository_write_is_fenced_by_the_account_tombstone](../../tests/test_user_memory.py#L244) (Zeile 244)
- [test_load_profile_text_fails_open](../../tests/test_user_memory.py#L260) (Zeile 260)
- [test_memory_endpoints_require_authentication](../../tests/test_user_memory.py#L301) (Zeile 301)
- [test_put_normalizes_and_returns_the_stored_profile](../../tests/test_user_memory.py#L307) (Zeile 307)
- [test_put_rejects_unknown_fields](../../tests/test_user_memory.py#L323) (Zeile 323)
- [test_get_returns_the_stored_profile](../../tests/test_user_memory.py#L331) (Zeile 331)
- [test_profile_reaches_the_provider_behind_the_base_instruction](../../tests/test_user_memory.py#L388) (Zeile 388)
- [test_long_manual_note_reaches_the_provider_verbatim](../../tests/test_user_memory.py#L397) (Zeile 397)
- [test_a_client_system_prompt_keeps_precedence_and_still_gets_the_profile](../../tests/test_user_memory.py#L403) (Zeile 403)
- [test_paused_or_empty_profile_still_gets_the_non_persistence_boundary](../../tests/test_user_memory.py#L413) (Zeile 413)
- [test_conversation_context_wraps_around_the_profile](../../tests/test_user_memory.py#L422) (Zeile 422)
- [test_use_memory_false_skips_the_profile_for_a_single_run](../../tests/test_user_memory.py#L440) (Zeile 440)
- [test_anonymous_runs_never_read_a_profile](../../tests/test_user_memory.py#L446) (Zeile 446)
- [test_account_deletion_covers_the_memory_subcollection](../../tests/test_user_memory.py#L463) (Zeile 463)

</details>

<a id="test-user-memory-run-cache-py"></a>

## test_user_memory_run_cache.py

**Quelle:** [tests/test_user_memory_run_cache.py](../../tests/test_user_memory_run_cache.py) · **Bereiche:** Cache, Nutzergedächtnis, Runtime.

**Ebene:** Cache-Unit-Tests mit Repository-Double und echten Threads.

**Lauf:** 15 bestanden.

**Geprüftes Verhalten:** Stabiler Snapshot je Run, frische Standalone-/Folgeruns, Owner/Repository/Tier-Isolation, ungültige Schlüssel, TTL und Fehler nicht cachen. Sechs parallele Requests teilen Read; Invalidation während Read verwirft Privattext, wartende Leser fail-open, Owner-selektives Löschen und begrenzte Pending-/Cache-Einträge.

**Grenzen und Doubles:** Lokale Threads und künstliche Uhr; Repository ist Double. Keine Mehrprozess-Kohärenz oder echter Firestore-Timeout.

**Prüfauftrag für den Folgeaudit:** Cacheinvalidierung bei Accountwechsel/Memory-Edit mit Router-/Frontendfällen abgleichen.

**Direkte Codeverweise:** [app/services/user_memory.py](../../app/services/user_memory.py).

<details>
<summary>11 Testdefinitionen und ihre Quellstellen</summary>

- [test_run_snapshot_is_stable_but_new_run_and_standalone_reads_are_fresh](../../tests/test_user_memory_run_cache.py#L30) (Zeile 30)
- [test_no_usable_run_key_never_caches](../../tests/test_user_memory_run_cache.py#L41) (Zeile 41)
- [test_owners_repositories_and_tier_budgets_never_share_snapshots](../../tests/test_user_memory_run_cache.py#L48) (Zeile 48)
- [test_expired_snapshot_reads_again](../../tests/test_user_memory_run_cache.py#L60) (Zeile 60)
- [test_read_failures_are_not_cached](../../tests/test_user_memory_run_cache.py#L71) (Zeile 71)
- [test_six_parallel_model_requests_share_one_read](../../tests/test_user_memory_run_cache.py#L85) (Zeile 85)
- [test_invalidation_during_read_discards_personal_text](../../tests/test_user_memory_run_cache.py#L113) (Zeile 113)
- [test_waiting_model_fails_open_when_another_profile_read_is_stuck](../../tests/test_user_memory_run_cache.py#L134) (Zeile 134)
- [test_invalidation_only_removes_target_owner](../../tests/test_user_memory_run_cache.py#L157) (Zeile 157)
- [test_cache_storage_is_bounded](../../tests/test_user_memory_run_cache.py#L167) (Zeile 167)
- [test_pending_entries_are_bounded_and_overflow_reads_without_caching](../../tests/test_user_memory_run_cache.py#L179) (Zeile 179)

</details>

<a id="test-watch-feature-py"></a>

## test_watch_feature.py

**Quelle:** [tests/test_watch_feature.py](../../tests/test_watch_feature.py) · **Bereiche:** Benachrichtigungen, Frontend, Konten und Tarife, Persistenz, Watch.

**Ebene:** Große Service-/Scheduler-/Router-/Mailformat-Suite mit DB-/LLM-/Versand-Doubles plus UI-Sourceverträge.

**Lauf:** 146 bestanden.

**Geprüftes Verhalten:** 146 Definitionen: Watch-CRUD/Owner/Quota/Counter/Tombstones, Query-first/private Baseline, Free/Plus/Pro und Publisherlineage, lokale Zeit/Wochentag/DST, signierte Unsubscribe. Claim/Lease/Run-ID-Fencing, Tagesbudget/3-Fehler-Pause, Version-/Baseline-/Drift-/Conditionlogik und aktuelle Tier-/Providerwahl. Mail/Telegram/Webhook/Actions/Dedupe/Cleanup, Morningbrief-Claims/Schedules/Tokens, Follower-Double-opt-in, Admin-/Userrouten, Historie/Positionmap und Watch-UI-Verträge.

**Grenzen und Doubles:** Meist lokale Fake-Transaktionen und gemockte Schedulerabhängigkeiten; keine realen Mails/Telegram/LLM. Mehrere Claims werden sequenziell getestet, nicht als echte verteilte Rennen. UI nur Source.

**Prüfauftrag für den Folgeaudit:** Emulator-Watch-/Followertransaktionen, Schedulercrash zwischen Claim/Versand, DST-Sonderfälle und Browsermodals abgleichen.

**Direkte Codeverweise:** [app/api/routers/admin.py](../../app/api/routers/admin.py), [app/api/routers/pages.py](../../app/api/routers/pages.py), [app/api/routers/share.py](../../app/api/routers/share.py), [app/api/routers/watch.py](../../app/api/routers/watch.py), [app/core/config.py](../../app/core/config.py), [app/core/rate_limit.py](../../app/core/rate_limit.py), [app/services/follow_challenges.py](../../app/services/follow_challenges.py), [app/services/mailer.py](../../app/services/mailer.py), [app/services/opinion_map.py](../../app/services/opinion_map.py), [app/services/persistence_guard.py](../../app/services/persistence_guard.py), [app/services/share_snapshots.py](../../app/services/share_snapshots.py), [app/services/telegram_watch.py](../../app/services/telegram_watch.py), [app/services/watch_brief.py](../../app/services/watch_brief.py), [app/services/watch_followers.py](../../app/services/watch_followers.py), [app/services/watch_scheduler.py](../../app/services/watch_scheduler.py), [app/services/watch_service.py](../../app/services/watch_service.py), [static/css/components-input.css](../../static/css/components-input.css), [static/css/components-modals.css](../../static/css/components-modals.css), [static/css/components-watch.css](../../static/css/components-watch.css), [static/css/public-pages.css](../../static/css/public-pages.css), [static/firebase.js](../../static/firebase.js), [static/js/share-dialog.js](../../static/js/share-dialog.js), [static/js/watch.js](../../static/js/watch.js), [templates/index.html](../../templates/index.html), [templates/share.html](../../templates/share.html).

<details>
<summary>146 Testdefinitionen und ihre Quellstellen</summary>

- [WatchCrudTests::test_free_create_list_update_pause_delete](../../tests/test_watch_feature.py#L174) (Zeile 174)
- [WatchCrudTests::test_account_deletion_fences_watch_mutations_but_cleanup_delete_continues](../../tests/test_watch_feature.py#L191) (Zeile 191)
- [WatchCrudTests::test_account_deletion_retry_does_not_recreate_deleted_watch_indexes](../../tests/test_watch_feature.py#L231) (Zeile 231)
- [WatchCrudTests::test_owned_share_cleanup_does_not_recreate_deleted_watch_indexes](../../tests/test_watch_feature.py#L264) (Zeile 264)
- [WatchCrudTests::test_normal_delete_reseeds_missing_watch_indexes_for_counter_updates](../../tests/test_watch_feature.py#L293) (Zeile 293)
- [WatchCrudTests::test_watch_requires_one_notification_channel](../../tests/test_watch_feature.py#L319) (Zeile 319)
- [WatchCrudTests::test_every_run_email_mode_can_be_created_and_changed](../../tests/test_watch_feature.py#L336) (Zeile 336)
- [WatchCrudTests::test_condition_mode_requires_condition_and_resets_state_when_edited](../../tests/test_watch_feature.py#L351) (Zeile 351)
- [WatchCrudTests::test_free_daily_requires_a_higher_tier](../../tests/test_watch_feature.py#L370) (Zeile 370)
- [WatchCrudTests::test_plus_may_watch_daily_but_keeps_a_smaller_slot_count](../../tests/test_watch_feature.py#L376) (Zeile 376)
- [WatchCrudTests::test_plus_daily_can_be_switched_off_by_the_admin](../../tests/test_watch_feature.py#L386) (Zeile 386)
- [WatchCrudTests::test_daily_gate_follows_admin_limit](../../tests/test_watch_feature.py#L393) (Zeile 393)
- [WatchCrudTests::test_free_and_pro_active_limits](../../tests/test_watch_feature.py#L400) (Zeile 400)
- [WatchCrudTests::test_pause_delete_and_resume_keep_owner_counter_consistent](../../tests/test_watch_feature.py#L410) (Zeile 410)
- [WatchCrudTests::test_cannot_watch_foreign_or_duplicate_share](../../tests/test_watch_feature.py#L433) (Zeile 433)
- [WatchCrudTests::test_publisher_watch_is_free_pinned_and_idempotent](../../tests/test_watch_feature.py#L442) (Zeile 442)
- [WatchCrudTests::test_publisher_watch_resume_bypasses_owner_limit_but_keeps_counter](../../tests/test_watch_feature.py#L471) (Zeile 471)
- [WatchCrudTests::test_legacy_free_watch_counts_and_verified_lineage_is_backfilled](../../tests/test_watch_feature.py#L493) (Zeile 493)
- [WatchCrudTests::test_admin_can_list_and_queue_active_watch](../../tests/test_watch_feature.py#L517) (Zeile 517)
- [WatchCrudTests::test_admin_queue_rejects_paused_or_claimed_watch](../../tests/test_watch_feature.py#L530) (Zeile 530)
- [WatchCrudTests::test_update_rejects_unknown_fields_and_owner](../../tests/test_watch_feature.py#L545) (Zeile 545)
- [WatchCrudTests::test_result_id_uses_existing_share_flow](../../tests/test_watch_feature.py#L552) (Zeile 552)
- [WatchCrudTests::test_query_first_watch_creates_an_empty_scheduled_baseline](../../tests/test_watch_feature.py#L563) (Zeile 563)
- [WatchCrudTests::test_query_first_watch_rejects_duplicate_question](../../tests/test_watch_feature.py#L584) (Zeile 584)
- [WatchCrudTests::test_query_first_watch_requires_a_complete_text_question](../../tests/test_watch_feature.py#L595) (Zeile 595)
- [WatchCrudTests::test_deleting_query_first_watch_revokes_its_empty_page](../../tests/test_watch_feature.py#L606) (Zeile 606)
- [WatchCrudTests::test_private_watch_keeps_visibility_private](../../tests/test_watch_feature.py#L617) (Zeile 617)
- [WatchCrudTests::test_watch_can_schedule_local_run_time](../../tests/test_watch_feature.py#L626) (Zeile 626)
- [WatchCrudTests::test_free_weekly_watch_uses_selected_local_weekday](../../tests/test_watch_feature.py#L641) (Zeile 641)
- [WatchCrudTests::test_weekly_run_day_can_be_updated_and_rejects_invalid_values](../../tests/test_watch_feature.py#L656) (Zeile 656)
- [WatchCrudTests::test_manual_run_keeps_the_selected_weekday](../../tests/test_watch_feature.py#L677) (Zeile 677)
- [WatchCrudTests::test_run_time_update_reschedules_and_rejects_invalid_values](../../tests/test_watch_feature.py#L685) (Zeile 685)
- [UnsubscribeTokenTests::test_valid_token_pauses_without_login](../../tests/test_watch_feature.py#L720) (Zeile 720)
- [UnsubscribeTokenTests::test_invalid_and_expired_tokens](../../tests/test_watch_feature.py#L733) (Zeile 733)
- [UnsubscribeTokenTests::test_tampered_token_is_invalid](../../tests/test_watch_feature.py#L740) (Zeile 740)
- [SchedulerSafetyTests::test_claim_transaction_prevents_double_run](../../tests/test_watch_feature.py#L757) (Zeile 757)
- [SchedulerSafetyTests::test_daily_budget_leaves_watch_due](../../tests/test_watch_feature.py#L770) (Zeile 770)
- [SchedulerSafetyTests::test_auto_pause_only_on_third_failure](../../tests/test_watch_feature.py#L780) (Zeile 780)
- [SchedulerSafetyTests::test_notification_threshold](../../tests/test_watch_feature.py#L794) (Zeile 794)
- [SchedulerSafetyTests::test_mock_llm_scheduler_ticks_never_touch_the_shared_database](../../tests/test_watch_feature.py#L842) (Zeile 842)
- [SchedulerSafetyTests::test_mock_llm_watch_pipeline](../../tests/test_watch_feature.py#L853) (Zeile 853)
- [SchedulerSafetyTests::test_watch_pipeline_tracks_previous_and_original_baseline_separately](../../tests/test_watch_feature.py#L864) (Zeile 864)
- [SchedulerSafetyTests::test_query_first_pipeline_establishes_baseline_without_change_alert](../../tests/test_watch_feature.py#L887) (Zeile 887)
- [SchedulerSafetyTests::test_query_first_condition_is_evaluated_against_first_consensus](../../tests/test_watch_feature.py#L897) (Zeile 897)
- [SchedulerSafetyTests::test_complete_run_persists_full_version_and_simple_event_type](../../tests/test_watch_feature.py#L916) (Zeile 916)
- [SchedulerSafetyTests::test_a_restated_answer_is_recorded_as_a_check_not_as_a_change](../../tests/test_watch_feature.py#L953) (Zeile 953)
- [SchedulerSafetyTests::test_a_score_bouncing_between_cap_steps_reports_one_event](../../tests/test_watch_feature.py#L988) (Zeile 988)
- [SchedulerSafetyTests::test_first_query_watch_run_promotes_result_to_share_baseline](../../tests/test_watch_feature.py#L1031) (Zeile 1031)
- [SchedulerSafetyTests::test_stale_run_cannot_complete_or_fail_newer_claim](../../tests/test_watch_feature.py#L1065) (Zeile 1065)
- [SchedulerSafetyTests::test_watch_lease_renewal_is_fenced_by_run_id](../../tests/test_watch_feature.py#L1096) (Zeile 1096)
- [SchedulerSafetyTests::test_watch_uses_all_configured_models_for_the_selected_tier](../../tests/test_watch_feature.py#L1117) (Zeile 1117)
- [SchedulerSafetyTests::test_watch_preserves_its_provider_and_fallback_engine_order](../../tests/test_watch_feature.py#L1130) (Zeile 1130)
- [SchedulerSafetyTests::test_watch_uses_configured_consensus_engine_independent_of_answer_models](../../tests/test_watch_feature.py#L1187) (Zeile 1187)
- [SchedulerSafetyTests::test_watch_falls_back_when_configured_consensus_provider_is_unavailable](../../tests/test_watch_feature.py#L1225) (Zeile 1225)
- [SchedulerSafetyTests::test_free_tier_watch_runs_every_configured_provider](../../tests/test_watch_feature.py#L1236) (Zeile 1236)
- [SchedulerSafetyTests::test_missing_shared_credential_drops_every_configured_model](../../tests/test_watch_feature.py#L1248) (Zeile 1248)
- [MailerTests::test_change_mail_is_multipart_with_unsubscribe](../../tests/test_watch_feature.py#L1262) (Zeile 1262)
- [MailerTests::test_every_run_mail_contains_new_consensus](../../tests/test_watch_feature.py#L1273) (Zeile 1273)
- [MailerTests::test_condition_mail_explains_trigger](../../tests/test_watch_feature.py#L1285) (Zeile 1285)
- [MailerTests::test_change_mail_leads_with_the_change_not_with_prose](../../tests/test_watch_feature.py#L1298) (Zeile 1298)
- [MailerTests::test_long_question_is_collapsed_and_links_to_the_page](../../tests/test_watch_feature.py#L1321) (Zeile 1321)
- [MailerTests::test_short_question_stays_whole_and_without_a_link](../../tests/test_watch_feature.py#L1337) (Zeile 1337)
- [MailerTests::test_brief_puts_changed_watches_first](../../tests/test_watch_feature.py#L1348) (Zeile 1348)
- [MailerTests::test_admin_test_mail_is_multipart_and_does_not_claim_a_watch](../../tests/test_watch_feature.py#L1365) (Zeile 1365)
- [MailerTests::test_public_watch_meta_contains_run_schedule_but_no_owner](../../tests/test_watch_feature.py#L1371) (Zeile 1371)
- [HistoryViewTests::test_watch_page_schedule_includes_weekday](../../tests/test_watch_feature.py#L1389) (Zeile 1389)
- [HistoryViewTests::test_svg_view_coordinates_and_change_events](../../tests/test_watch_feature.py#L1396) (Zeile 1396)
- [HistoryViewTests::test_position_map_labels_lose_the_markdown_of_the_answer_text](../../tests/test_watch_feature.py#L1409) (Zeile 1409)
- [OpinionMapTests::test_multidimensional_map_tracks_provider_cluster_movement](../../tests/test_watch_feature.py#L1446) (Zeile 1446)
- [OpinionMapTests::test_stable_judge_prevents_synthetic_full_shift](../../tests/test_watch_feature.py#L1457) (Zeile 1457)
- [OpinionMapTests::test_reframed_dimensions_are_unscored_instead_of_full_shift](../../tests/test_watch_feature.py#L1471) (Zeile 1471)
- [OpinionMapTests::test_legacy_full_shift_is_recalculated_against_predecessor](../../tests/test_watch_feature.py#L1489) (Zeile 1489)
- [OpinionMapTests::test_map_is_compact_and_contains_no_raw_answers](../../tests/test_watch_feature.py#L1502) (Zeile 1502)
- [OpinionMapTests::test_unanimous_claims_still_produce_a_direction_baseline](../../tests/test_watch_feature.py#L1507) (Zeile 1507)
- [SchedulerLoopTests::test_scheduler_wake_triggers_an_immediate_second_tick](../../tests/test_watch_feature.py#L1524) (Zeile 1524)
- [SchedulerLoopTests::test_every_run_mail_targets_verified_watch_owner](../../tests/test_watch_feature.py#L1543) (Zeile 1543)
- [SchedulerLoopTests::test_pause_mail_emitted_exactly_on_third_failure](../../tests/test_watch_feature.py#L1564) (Zeile 1564)
- [SchedulerLoopTests::test_every_run_mode_sends_full_result_mail_without_change](../../tests/test_watch_feature.py#L1588) (Zeile 1588)
- [SchedulerLoopTests::test_telegram_only_watch_reuses_notification_rule_without_mail](../../tests/test_watch_feature.py#L1617) (Zeile 1617)
- [SchedulerLoopTests::test_each_watch_run_uses_the_owners_current_tier](../../tests/test_watch_feature.py#L1649) (Zeile 1649)
- [SchedulerLoopTests::test_publisher_watch_stays_on_free_tier_for_pro_owner](../../tests/test_watch_feature.py#L1677) (Zeile 1677)
- [TelegramWatchTests::test_one_time_deep_link_connects_and_disconnects_private_chat](../../tests/test_watch_feature.py#L1721) (Zeile 1721)
- [TelegramWatchTests::test_account_deletion_fences_link_creation_consumption_and_delivery_claim](../../tests/test_watch_feature.py#L1741) (Zeile 1741)
- [TelegramWatchTests::test_startup_registers_secret_header_webhook](../../tests/test_watch_feature.py#L1773) (Zeile 1773)
- [TelegramWatchTests::test_watch_delivery_is_deduplicated_and_contains_actions](../../tests/test_watch_feature.py#L1785) (Zeile 1785)
- [TelegramWatchTests::test_notification_text_leads_with_the_change_and_folds_the_question](../../tests/test_watch_feature.py#L1812) (Zeile 1812)
- [TelegramWatchTests::test_html_rejection_falls_back_to_plain_text](../../tests/test_watch_feature.py#L1837) (Zeile 1837)
- [TelegramWatchTests::test_mute_and_confirmed_pause_actions_are_owner_scoped](../../tests/test_watch_feature.py#L1860) (Zeile 1860)
- [TelegramWatchTests::test_account_cleanup_removes_connection_links_and_deliveries](../../tests/test_watch_feature.py#L1891) (Zeile 1891)
- [WatchFrontendContractTests::test_user_menu_places_watched_after_shared_links](../../tests/test_watch_feature.py#L1909) (Zeile 1909)
- [WatchFrontendContractTests::test_watch_ui_exposes_every_run_email_mode](../../tests/test_watch_feature.py#L1914) (Zeile 1914)
- [WatchFrontendContractTests::test_watch_dashboard_supports_query_first_creation](../../tests/test_watch_feature.py#L1928) (Zeile 1928)
- [WatchFrontendContractTests::test_watch_empty_state_and_mobile_create_button_alignment](../../tests/test_watch_feature.py#L1938) (Zeile 1938)
- [WatchFrontendContractTests::test_watch_setup_offers_editing_next_to_the_defaults_it_describes](../../tests/test_watch_feature.py#L1947) (Zeile 1947)
- [WatchFrontendContractTests::test_watch_dialog_ignores_backdrop_click_and_view_switch_hint_is_finite](../../tests/test_watch_feature.py#L1971) (Zeile 1971)
- [WatchFrontendContractTests::test_watch_limits_are_visible_before_creation_and_on_dashboard](../../tests/test_watch_feature.py#L1981) (Zeile 1981)
- [WatchFrontendContractTests::test_watch_modal_has_one_scroll_area_and_locks_background](../../tests/test_watch_feature.py#L1991) (Zeile 1991)
- [WatchFrontendContractTests::test_watch_dashboard_is_a_page_with_segmented_view_switch](../../tests/test_watch_feature.py#L2012) (Zeile 2012)
- [WatchFrontendContractTests::test_long_questions_collapse_on_the_page_like_in_the_app](../../tests/test_watch_feature.py#L2034) (Zeile 2034)
- [WatchFrontendContractTests::test_collapsed_watch_cards_keep_a_centered_themed_toggle_and_summary](../../tests/test_watch_feature.py#L2054) (Zeile 2054)
- [WatchPageRouteTests::test_watch_page_serves_app_shell_noindex](../../tests/test_watch_feature.py#L2078) (Zeile 2078)
- [WatchHistorySerializationTests::test_list_watches_can_attach_compact_history](../../tests/test_watch_feature.py#L2086) (Zeile 2086)
- [WatchHistorySerializationTests::test_history_lookup_failure_degrades_to_empty_list](../../tests/test_watch_feature.py#L2109) (Zeile 2109)
- [WatchHistorySerializationTests::test_serialize_history_points_caps_at_newest](../../tests/test_watch_feature.py#L2118) (Zeile 2118)
- [BriefSettingsTests::test_defaults_when_no_document_exists](../../tests/test_watch_feature.py#L2134) (Zeile 2134)
- [BriefSettingsTests::test_account_deletion_tombstone_fences_brief_upsert](../../tests/test_watch_feature.py#L2141) (Zeile 2141)
- [BriefSettingsTests::test_enabling_without_a_watch_is_rejected](../../tests/test_watch_feature.py#L2153) (Zeile 2153)
- [BriefSettingsTests::test_final_watch_removal_disables_an_active_brief](../../tests/test_watch_feature.py#L2161) (Zeile 2161)
- [BriefSettingsTests::test_enabling_requires_timezone_and_schedules_dst_safe](../../tests/test_watch_feature.py#L2171) (Zeile 2171)
- [BriefSettingsTests::test_time_change_while_enabled_reschedules](../../tests/test_watch_feature.py#L2188) (Zeile 2188)
- [BriefSettingsTests::test_mode_and_field_validation](../../tests/test_watch_feature.py#L2201) (Zeile 2201)
- [BriefSettingsTests::test_disable_keeps_settings](../../tests/test_watch_feature.py#L2210) (Zeile 2210)
- [BriefClaimTests::test_claim_advances_before_sending_and_prevents_double_send](../../tests/test_watch_feature.py#L2231) (Zeile 2231)
- [BriefClaimTests::test_disabled_or_not_due_is_not_claimed](../../tests/test_watch_feature.py#L2239) (Zeile 2239)
- [BriefClaimTests::test_unschedulable_settings_disable_instead_of_hot_looping](../../tests/test_watch_feature.py#L2245) (Zeile 2245)
- [BriefClaimTests::test_baseline_falls_back_to_first_brief_window](../../tests/test_watch_feature.py#L2250) (Zeile 2250)
- [BriefClaimTests::test_due_scan_lists_only_enabled_due_briefs](../../tests/test_watch_feature.py#L2255) (Zeile 2255)
- [BriefCollectTests::test_notable_changes_are_counted_since_baseline](../../tests/test_watch_feature.py#L2266) (Zeile 2266)
- [BriefMailTests::test_brief_mail_is_multipart_with_summary_and_unsubscribe](../../tests/test_watch_feature.py#L2304) (Zeile 2304)
- [BriefMailTests::test_brief_mail_without_changes_uses_calm_subject](../../tests/test_watch_feature.py#L2318) (Zeile 2318)
- [BriefTokenTests::test_valid_token_disables_brief](../../tests/test_watch_feature.py#L2339) (Zeile 2339)
- [BriefTokenTests::test_watch_token_is_not_accepted_for_brief](../../tests/test_watch_feature.py#L2347) (Zeile 2347)
- [BriefTokenTests::test_expired_brief_token](../../tests/test_watch_feature.py#L2352) (Zeile 2352)
- [BriefTickTests::test_due_brief_is_sent_and_marked](../../tests/test_watch_feature.py#L2365) (Zeile 2365)
- [BriefTickTests::test_changes_only_brief_is_skipped_without_changes](../../tests/test_watch_feature.py#L2388) (Zeile 2388)
- [BriefTickTests::test_unverified_owner_never_receives_a_brief](../../tests/test_watch_feature.py#L2406) (Zeile 2406)
- [WatchRouteTests::test_create_forwards_weekday_schedule](../../tests/test_watch_feature.py#L2428) (Zeile 2428)
- [WatchRouteTests::test_create_forwards_query_without_result_id](../../tests/test_watch_feature.py#L2444) (Zeile 2444)
- [WatchRouteTests::test_my_watches_exposes_authoritative_active_limit](../../tests/test_watch_feature.py#L2464) (Zeile 2464)
- [WatchRouteTests::test_telegram_must_be_connected_before_enabling_watch_channel](../../tests/test_watch_feature.py#L2487) (Zeile 2487)
- [WatchRouteTests::test_telegram_connection_routes_and_webhook_secret](../../tests/test_watch_feature.py#L2501) (Zeile 2501)
- [BriefRouteTests::test_get_and_patch_brief_settings](../../tests/test_watch_feature.py#L2540) (Zeile 2540)
- [BriefRouteTests::test_patch_brief_maps_watch_errors_to_http_400](../../tests/test_watch_feature.py#L2562) (Zeile 2562)
- [BriefRouteTests::test_brief_unsubscribe_page](../../tests/test_watch_feature.py#L2570) (Zeile 2570)
- [AdminWatchRouteTests::test_watch_diagnostics_requires_admin](../../tests/test_watch_feature.py#L2596) (Zeile 2596)
- [AdminWatchRouteTests::test_watch_diagnostics_lists_and_starts_run](../../tests/test_watch_feature.py#L2602) (Zeile 2602)
- [AdminWatchRouteTests::test_admin_test_email_uses_verified_admin_address](../../tests/test_watch_feature.py#L2626) (Zeile 2626)
- [FollowerTests::test_request_confirm_and_unsubscribe_roundtrip](../../tests/test_watch_feature.py#L2657) (Zeile 2657)
- [FollowerTests::test_confirm_and_unsubscribe_tokens_are_not_interchangeable](../../tests/test_watch_feature.py#L2679) (Zeile 2679)
- [FollowerTests::test_invalid_email_and_unfollowable_pages_rejected](../../tests/test_watch_feature.py#L2687) (Zeile 2687)
- [FollowerTests::test_delete_followers_for_share](../../tests/test_watch_feature.py#L2699) (Zeile 2699)
- [FollowerTests::test_follower_mails_only_on_material_change](../../tests/test_watch_feature.py#L2706) (Zeile 2706)
- [FollowerTests::test_cleanup_or_removed_watch_invalidates_outstanding_confirm_link](../../tests/test_watch_feature.py#L2743) (Zeile 2743)
- [FollowRouteTests::test_follow_route_sends_confirmation_mail](../../tests/test_watch_feature.py#L2770) (Zeile 2770)
- [FollowRouteTests::test_follow_route_is_generic_for_existing_followers](../../tests/test_watch_feature.py#L2780) (Zeile 2780)
- [FollowRouteTests::test_follow_confirm_route_renders_page](../../tests/test_watch_feature.py#L2789) (Zeile 2789)

</details>

<a id="test-worker-thread-budget-py"></a>

## test_worker_thread_budget.py

**Quelle:** [tests/test_worker_thread_budget.py](../../tests/test_worker_thread_budget.py) · **Bereiche:** Sicherheit.

**Ebene:** Konfiguration und echter AnyIO-Limiter.

**Lauf:** 9 bestanden.

**Geprüftes Verhalten:** Defaultbudget, Unter-/Obergrenzen und ungültige Envwerte; aktiver Limiter wird auf 144 erhöht und vorhandene 300 werden nicht gesenkt; Lifespan wendet Budget vor E2E-Early-Return an.

**Grenzen und Doubles:** Die Division des Defaults durch sechs ist eine Kapazitätsannahme, kein Lasttest mit zwanzig vollständigen Runs. Lifespan-E2E-Bedingung ist ersetzt.

**Prüfauftrag für den Folgeaudit:** Tatsächlichen Threadbedarf, Speicher-/CPU-Verhalten und Plattformdefaults unter realistischer Last prüfen.

**Direkte Codeverweise:** [app/core/concurrency.py](../../app/core/concurrency.py), [main.py](../../main.py).

<details>
<summary>5 Testdefinitionen und ihre Quellstellen</summary>

- [test_default_budget_carries_more_than_six_concurrent_runs](../../tests/test_worker_thread_budget.py#L18) (Zeile 18)
- [test_budget_is_bounded_and_survives_garbage](../../tests/test_worker_thread_budget.py#L38) (Zeile 38)
- [test_apply_raises_the_running_loops_limiter](../../tests/test_worker_thread_budget.py#L44) (Zeile 44)
- [test_apply_never_lowers_an_already_larger_budget](../../tests/test_worker_thread_budget.py#L60) (Zeile 60)
- [test_lifespan_applies_the_budget_before_the_e2e_early_return](../../tests/test_worker_thread_budget.py#L71) (Zeile 71)

</details>

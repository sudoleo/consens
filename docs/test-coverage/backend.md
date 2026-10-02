# Reguläre Python-Suite: Abdeckung pro Testdatei

Stand: **2026-10-02**, Quellstand `ffaca3df7c8bbb02d850fb8f31d90107f26e9293`. [Methodik und Gesamtbefund](../test-coverage-map.md).

**169 Dateien · 2445 statische Testdefinitionen · 3303 Runner-Fälle.**

„Geprüftes Verhalten“ beschreibt die vorhandenen Assertions. Der Laufstatus steht separat: bei Fehlern ist der beschriebene Vertrag nicht als bestanden belegt. Prüfaufträge sind offene Fragen, keine pauschal festgestellten Lücken der gesamten Suite. Aktuelle Befundbewertungen stehen im [Produktabgleich](product/README.md).

Die Codeverweise sind direkte Imports oder wörtliche Pfade, keine gemessene Ausführungsabdeckung. Indirekte Abhängigkeiten über Fixtures/Helpers und dynamisch zusammengesetzte Pfade können fehlen. Das [JSON-Inventar](inventory.json) enthält jede Definition mit Zeilen, Assertion-Fundstellen und jeden expandierten Runner-Fall. Datum, Umgebung und Grenzen stehen im [Laufbericht](findings.md).

| Datei | Definitionen | Runner-Fälle | Primärlauf 2026-10-02 |
|---|---:|---:|---|
| [test_account_deletion_chats.py](#test-account-deletion-chats-py) | 3 | 3 | 3 bestanden |
| [test_account_deletion_retry.py](#test-account-deletion-retry-py) | 1 | 1 | 1 bestanden |
| [test_account_tier_admin.py](#test-account-tier-admin-py) | 13 | 13 | 13 bestanden |
| [test_agent_accounting_audit.py](#test-agent-accounting-audit-py) | 11 | 58 | 58 bestanden |
| [test_agent_admission.py](#test-agent-admission-py) | 12 | 16 | 16 bestanden |
| [test_agent_answer_lifecycle.py](#test-agent-answer-lifecycle-py) | 3 | 7 | 7 bestanden |
| [test_agent_budget_config.py](#test-agent-budget-config-py) | 5 | 5 | 5 bestanden |
| [test_agent_calendar.py](#test-agent-calendar-py) | 9 | 9 | 9 bestanden |
| [test_agent_capacity.py](#test-agent-capacity-py) | 7 | 7 | 7 bestanden |
| [test_agent_chat_integrity.py](#test-agent-chat-integrity-py) | 8 | 15 | 15 bestanden |
| [test_agent_comparison.py](#test-agent-comparison-py) | 40 | 69 | 69 bestanden |
| [test_agent_continuation.py](#test-agent-continuation-py) | 11 | 13 | 13 bestanden |
| [test_agent_contradictions.py](#test-agent-contradictions-py) | 10 | 11 | 11 bestanden |
| [test_agent_delegation.py](#test-agent-delegation-py) | 16 | 16 | 16 bestanden |
| [test_agent_documents.py](#test-agent-documents-py) | 12 | 12 | 12 bestanden |
| [test_agent_files.py](#test-agent-files-py) | 23 | 24 | 24 bestanden |
| [test_agent_gmail.py](#test-agent-gmail-py) | 18 | 21 | 21 bestanden |
| [test_agent_http_contract.py](#test-agent-http-contract-py) | 6 | 9 | 9 bestanden |
| [test_agent_loop.py](#test-agent-loop-py) | 24 | 152 | 152 bestanden |
| [test_agent_mode_ui.py](#test-agent-mode-ui-py) | 9 | 9 | 9 bestanden |
| [test_agent_model_catalog.py](#test-agent-model-catalog-py) | 5 | 11 | 11 bestanden |
| [test_agent_progress.py](#test-agent-progress-py) | 9 | 10 | 10 bestanden |
| [test_agent_quota_recovery.py](#test-agent-quota-recovery-py) | 8 | 12 | 12 bestanden |
| [test_agent_reasoning_continuation.py](#test-agent-reasoning-continuation-py) | 8 | 8 | 8 bestanden |
| [test_agent_reliability.py](#test-agent-reliability-py) | 14 | 19 | 19 bestanden |
| [test_agent_root_compaction.py](#test-agent-root-compaction-py) | 7 | 7 | 7 bestanden |
| [test_agent_runs.py](#test-agent-runs-py) | 30 | 38 | 38 bestanden |
| [test_agent_search.py](#test-agent-search-py) | 11 | 61 | 61 bestanden |
| [test_agent_synthesis_context.py](#test-agent-synthesis-context-py) | 2 | 4 | 4 bestanden |
| [test_agent_usage_reconciliation.py](#test-agent-usage-reconciliation-py) | 11 | 11 | 11 bestanden |
| [test_agreement_verdict_ui.py](#test-agreement-verdict-ui-py) | 6 | 6 | 6 bestanden |
| [test_analysis_quality_budget.py](#test-analysis-quality-budget-py) | 12 | 14 | 14 bestanden |
| [test_analytics_partial.py](#test-analytics-partial-py) | 5 | 5 | 5 bestanden |
| [test_api_account_cleanup.py](#test-api-account-cleanup-py) | 3 | 4 | 4 bestanden |
| [test_api_key_repository.py](#test-api-key-repository-py) | 5 | 5 | 5 bestanden |
| [test_api_run_billing_identity.py](#test-api-run-billing-identity-py) | 11 | 11 | 11 bestanden |
| [test_api_run_recovery.py](#test-api-run-recovery-py) | 4 | 4 | 4 bestanden |
| [test_api_run_repository.py](#test-api-run-repository-py) | 8 | 8 | 8 bestanden |
| [test_api_source_history.py](#test-api-source-history-py) | 2 | 9 | 9 bestanden |
| [test_ask_endpoints.py](#test-ask-endpoints-py) | 14 | 14 | 14 bestanden |
| [test_attachment_meta.py](#test-attachment-meta-py) | 2 | 2 | 2 bestanden |
| [test_attachments.py](#test-attachments-py) | 37 | 37 | 37 bestanden |
| [test_auth_revocation.py](#test-auth-revocation-py) | 4 | 4 | 4 bestanden |
| [test_auth_session.py](#test-auth-session-py) | 8 | 8 | 8 bestanden |
| [test_auxiliary_cli.py](#test-auxiliary-cli-py) | 5 | 21 | 21 bestanden |
| [test_background_task_supervision.py](#test-background-task-supervision-py) | 8 | 8 | 8 bestanden |
| [test_benchmark_audits.py](#test-benchmark-audits-py) | 9 | 9 | 9 bestanden |
| [test_benchmark_budget.py](#test-benchmark-budget-py) | 4 | 4 | 4 bestanden |
| [test_benchmark_cli.py](#test-benchmark-cli-py) | 20 | 20 | 20 bestanden |
| [test_benchmark_credentials.py](#test-benchmark-credentials-py) | 4 | 4 | 4 bestanden |
| [test_benchmark_dataset.py](#test-benchmark-dataset-py) | 7 | 7 | 7 bestanden |
| [test_benchmark_manifest_clock.py](#test-benchmark-manifest-clock-py) | 3 | 5 | 5 bestanden |
| [test_benchmark_mode.py](#test-benchmark-mode-py) | 5 | 5 | 5 bestanden |
| [test_benchmark_parse.py](#test-benchmark-parse-py) | 12 | 12 | 12 bestanden |
| [test_benchmark_protocol.py](#test-benchmark-protocol-py) | 4 | 15 | 15 bestanden |
| [test_benchmark_redaction.py](#test-benchmark-redaction-py) | 3 | 3 | 3 bestanden |
| [test_benchmark_report_reader.py](#test-benchmark-report-reader-py) | 4 | 4 | 4 bestanden |
| [test_benchmark_reports.py](#test-benchmark-reports-py) | 2 | 2 | 2 bestanden |
| [test_benchmark_results.py](#test-benchmark-results-py) | 8 | 8 | 8 bestanden |
| [test_benchmark_run.py](#test-benchmark-run-py) | 6 | 6 | 6 bestanden |
| [test_benchmark_runner.py](#test-benchmark-runner-py) | 9 | 9 | 9 bestanden |
| [test_benchmark_transport.py](#test-benchmark-transport-py) | 6 | 6 | 6 bestanden |
| [test_bookmarks.py](#test-bookmarks-py) | 37 | 40 | 40 bestanden |
| [test_chat_context.py](#test-chat-context-py) | 41 | 41 | 41 bestanden |
| [test_chat_history.py](#test-chat-history-py) | 66 | 77 | 77 bestanden |
| [test_chat_session_ui.py](#test-chat-session-ui-py) | 11 | 11 | 11 bestanden |
| [test_citations.py](#test-citations-py) | 7 | 7 | 7 bestanden |
| [test_claim_identity_judge.py](#test-claim-identity-judge-py) | 5 | 14 | 14 bestanden |
| [test_claim_ledger.py](#test-claim-ledger-py) | 21 | 21 | 21 bestanden |
| [test_client_error_alerts.py](#test-client-error-alerts-py) | 12 | 34 | 34 bestanden |
| [test_consensus_answer_contract.py](#test-consensus-answer-contract-py) | 5 | 5 | 5 bestanden |
| [test_consensus_api.py](#test-consensus-api-py) | 27 | 27 | 27 bestanden |
| [test_consensus_chat_history.py](#test-consensus-chat-history-py) | 39 | 52 | 52 bestanden |
| [test_consensus_citations.py](#test-consensus-citations-py) | 17 | 46 | 46 bestanden |
| [test_consensus_engine.py](#test-consensus-engine-py) | 19 | 19 | 19 bestanden |
| [test_consensus_input_caps.py](#test-consensus-input-caps-py) | 8 | 8 | 8 bestanden |
| [test_consensus_progress_ui.py](#test-consensus-progress-ui-py) | 18 | 18 | 18 bestanden |
| [test_contradiction_jobs.py](#test-contradiction-jobs-py) | 15 | 19 | 19 bestanden |
| [test_contradiction_verification.py](#test-contradiction-verification-py) | 31 | 67 | 67 bestanden |
| [test_coverage_judge.py](#test-coverage-judge-py) | 30 | 30 | 30 bestanden |
| [test_deepseek_web_search.py](#test-deepseek-web-search-py) | 3 | 3 | 3 bestanden |
| [test_demo_login_prompt.py](#test-demo-login-prompt-py) | 5 | 5 | 5 bestanden |
| [test_dev_cli.py](#test-dev-cli-py) | 9 | 28 | 28 bestanden |
| [test_differences_schema.py](#test-differences-schema-py) | 83 | 83 | 83 bestanden |
| [test_differences_stats.py](#test-differences-stats-py) | 4 | 4 | 4 bestanden |
| [test_drift_signal.py](#test-drift-signal-py) | 15 | 15 | 15 bestanden |
| [test_e2e_safety.py](#test-e2e-safety-py) | 6 | 10 | 10 bestanden |
| [test_feedback.py](#test-feedback-py) | 5 | 8 | 8 bestanden |
| [test_firestore_read_contracts.py](#test-firestore-read-contracts-py) | 1 | 2 | 2 bestanden |
| [test_followup_context.py](#test-followup-context-py) | 16 | 18 | 18 bestanden |
| [test_frontend_assets.py](#test-frontend-assets-py) | 13 | 14 | 14 bestanden |
| [test_frontend_build.py](#test-frontend-build-py) | 8 | 8 | 8 bestanden |
| [test_frontend_resilience.py](#test-frontend-resilience-py) | 4 | 4 | 4 bestanden |
| [test_google_connections.py](#test-google-connections-py) | 15 | 15 | 15 bestanden |
| [test_http_adapter_auth.py](#test-http-adapter-auth-py) | 7 | 38 | 38 bestanden |
| [test_local_transport.py](#test-local-transport-py) | 6 | 10 | 10 bestanden |
| [test_logging_redaction_contract.py](#test-logging-redaction-contract-py) | 8 | 8 | 8 bestanden |
| [test_maintenance_scripts.py](#test-maintenance-scripts-py) | 10 | 13 | 13 bestanden |
| [test_memory_edit.py](#test-memory-edit-py) | 21 | 22 | 22 bestanden |
| [test_memory_http_contract.py](#test-memory-http-contract-py) | 3 | 12 | 12 bestanden |
| [test_model_configuration.py](#test-model-configuration-py) | 31 | 31 | 31 bestanden |
| [test_model_configuration_regressions.py](#test-model-configuration-regressions-py) | 33 | 33 | 33 bestanden |
| [test_model_leaderboard.py](#test-model-leaderboard-py) | 14 | 18 | 18 bestanden |
| [test_multi_run_architecture.py](#test-multi-run-architecture-py) | 3 | 3 | 3 bestanden |
| [test_navigation_settings_ui.py](#test-navigation-settings-ui-py) | 27 | 27 | 27 bestanden |
| [test_og_image.py](#test-og-image-py) | 4 | 4 | 4 bestanden |
| [test_onboarding_gates.py](#test-onboarding-gates-py) | 7 | 7 | 7 bestanden |
| [test_pdf_extraction_isolation.py](#test-pdf-extraction-isolation-py) | 9 | 10 | 10 bestanden |
| [test_phase4_frontend.py](#test-phase4-frontend-py) | 14 | 14 | 14 bestanden |
| [test_phase5_operations.py](#test-phase5-operations-py) | 26 | 34 | 34 bestanden |
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
| [test_public_markdown.py](#test-public-markdown-py) | 1 | 1 | 1 bestanden |
| [test_publish_consensus_script.py](#test-publish-consensus-script-py) | 13 | 13 | 13 bestanden |
| [test_publisher_config.py](#test-publisher-config-py) | 6 | 6 | 6 bestanden |
| [test_publisher_standalone.py](#test-publisher-standalone-py) | 3 | 3 | 3 bestanden |
| [test_rate_limit.py](#test-rate-limit-py) | 8 | 8 | 8 bestanden |
| [test_reasoning_policy.py](#test-reasoning-policy-py) | 7 | 18 | 18 bestanden |
| [test_registration_security.py](#test-registration-security-py) | 4 | 4 | 4 bestanden |
| [test_request_body_limits.py](#test-request-body-limits-py) | 9 | 22 | 22 bestanden |
| [test_resolve_round.py](#test-resolve-round-py) | 23 | 23 | 23 bestanden |
| [test_result_integrity.py](#test-result-integrity-py) | 19 | 27 | 27 bestanden |
| [test_router_event_loop_contract.py](#test-router-event-loop-contract-py) | 2 | 2 | 2 bestanden |
| [test_run_usage_endpoints.py](#test-run-usage-endpoints-py) | 12 | 14 | 14 bestanden |
| [test_run_usage_repository.py](#test-run-usage-repository-py) | 25 | 29 | 29 bestanden |
| [test_security_controls.py](#test-security-controls-py) | 5 | 5 | 5 bestanden |
| [test_seo_basics.py](#test-seo-basics-py) | 13 | 13 | 13 bestanden |
| [test_seo_data.py](#test-seo-data-py) | 39 | 39 | 39 bestanden |
| [test_seo_entity.py](#test-seo-entity-py) | 6 | 6 | 6 bestanden |
| [test_seo_repository.py](#test-seo-repository-py) | 3 | 3 | 3 bestanden |
| [test_seo_weekly_review.py](#test-seo-weekly-review-py) | 20 | 20 | 20 bestanden |
| [test_share_feature.py](#test-share-feature-py) | 156 | 156 | 156 bestanden |
| [test_share_http_contract.py](#test-share-http-contract-py) | 4 | 7 | 7 bestanden |
| [test_source_catalog.py](#test-source-catalog-py) | 19 | 19 | 19 bestanden |
| [test_source_check_api.py](#test-source-check-api-py) | 9 | 14 | 14 bestanden |
| [test_source_check_jobs.py](#test-source-check-jobs-py) | 22 | 23 | 23 bestanden |
| [test_source_check_repository.py](#test-source-check-repository-py) | 31 | 36 | 36 bestanden |
| [test_source_check_scope.py](#test-source-check-scope-py) | 5 | 12 | 12 bestanden |
| [test_source_judge_fallback.py](#test-source-judge-fallback-py) | 7 | 15 | 15 bestanden |
| [test_source_model_configuration.py](#test-source-model-configuration-py) | 13 | 28 | 28 bestanden |
| [test_source_pills_ui.py](#test-source-pills-ui-py) | 3 | 3 | 3 bestanden |
| [test_source_verification.py](#test-source-verification-py) | 62 | 122 | 122 bestanden |
| [test_static_delivery.py](#test-static-delivery-py) | 8 | 8 | 8 bestanden |
| [test_stream_backpressure.py](#test-stream-backpressure-py) | 3 | 3 | 3 bestanden |
| [test_streaming.py](#test-streaming-py) | 31 | 31 | 31 bestanden |
| [test_telegram_notifier.py](#test-telegram-notifier-py) | 9 | 9 | 9 bestanden |
| [test_tier_cache.py](#test-tier-cache-py) | 7 | 7 | 7 bestanden |
| [test_topic_finding.py](#test-topic-finding-py) | 14 | 14 | 14 bestanden |
| [test_topic_public_http.py](#test-topic-public-http-py) | 3 | 10 | 10 bestanden |
| [test_topics_feature.py](#test-topics-feature-py) | 52 | 65 | 65 bestanden |
| [test_unscored_history.py](#test-unscored-history-py) | 3 | 3 | 3 bestanden |
| [test_usage_authorization.py](#test-usage-authorization-py) | 10 | 15 | 15 bestanden |
| [test_usage_limit_ui.py](#test-usage-limit-ui-py) | 10 | 10 | 10 bestanden |
| [test_usage_meter.py](#test-usage-meter-py) | 8 | 8 | 8 bestanden |
| [test_user_memory.py](#test-user-memory-py) | 34 | 34 | 34 bestanden |
| [test_user_memory_run_cache.py](#test-user-memory-run-cache-py) | 11 | 15 | 15 bestanden |
| [test_watch_evidence_model.py](#test-watch-evidence-model-py) | 13 | 13 | 13 bestanden |
| [test_watch_feature.py](#test-watch-feature-py) | 157 | 157 | 157 bestanden |
| [test_watch_http_contract.py](#test-watch-http-contract-py) | 6 | 13 | 13 bestanden |
| [test_watch_review_regressions.py](#test-watch-review-regressions-py) | 24 | 24 | 24 bestanden |
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

**Geprüftes Verhalten:** Ein Fehler im Bereich owned_shares bleibt beim ersten Cleanup offen; der zweite Durchlauf wiederholt nur diesen Bereich. Andere quittierte Bereiche laufen genau einmal; der Auftrag endet completed, cleanup_pending=false und entfernt die E-Mail. Aktualisierung 02.10.2026: Kaskade umfasst jetzt Antwortreceipts und Benachrichtigungs-Outbox.

**Grenzen und Doubles:** Die eigentlichen Bereichslöschungen einschließlich ChatStore sind Doubles mit Aufrufzählern. Geprüft werden Orchestrierung und Checkpoints, keine reale Löschkaskade oder Firestore-Konflikte.

**Prüfauftrag für den Folgeaudit:** Weitere Fehlerpositionen, Prozessabbruch zwischen Bereichslöschung und Quittierung und konkurrierende Cleanup-Worker im späteren Audit abgleichen.

**Direkte Codeverweise:** [app/services/account_deletion.py](../../app/services/account_deletion.py).

<details>
<summary>1 Testdefinitionen und ihre Quellstellen</summary>

- [test_failed_area_remains_pending_and_only_that_area_is_retried](../../tests/test_account_deletion_retry.py#L69) (Zeile 69)

</details>

<a id="test-account-tier-admin-py"></a>

## test_account_tier_admin.py

**Quelle:** [tests/test_account_tier_admin.py](../../tests/test_account_tier_admin.py) · **Bereiche:** Authentifizierung, Admin.

**Ebene:** Registrierte main.app mit echten Middleware-, Auth-/Owner- und Serviceguards.

**Lauf:** 13 bestanden.

**Geprüftes Verhalten:** Tarif-/Adminänderungen und Cacheinvalidierung; unbekanntes Konto liefert im echten main-Handler404 mit error.error_code=not_found und lesbarer error.message ohne SDK-Diagnose.

**Grenzen und Doubles:** Firebase-SDK-Authentifizierung und DB ersetzt; externe Modell-, Mail- und Telegramgrenzen kontrolliert. Kein Live-OAuth oder produktiver Versand.

**Prüfauftrag für den Folgeaudit:** Die benannten Betriebs- und Testgrenzen bei künftigen Änderungen erneut prüfen; konkrete Paketnachweise stehen im Produktabgleich.

**Direkte Codeverweise:** [app/api/routers/admin.py](../../app/api/routers/admin.py), [app/core/rate_limit.py](../../app/core/rate_limit.py), [app/services/account_tier.py](../../app/services/account_tier.py).

<details>
<summary>13 Testdefinitionen und ihre Quellstellen</summary>

- [test_set_tier_writes_the_field_audits_it_and_drops_the_cache](../../tests/test_account_tier_admin.py#L144) (Zeile 144)
- [test_set_tier_keeps_unrelated_profile_fields](../../tests/test_account_tier_admin.py#L169) (Zeile 169)
- [test_set_tier_rejects_an_unknown_tier](../../tests/test_account_tier_admin.py#L177) (Zeile 177)
- [test_an_account_being_deleted_gets_no_tier](../../tests/test_account_tier_admin.py#L184) (Zeile 184)
- [test_set_tier_checks_deletion_fence_inside_profile_transaction](../../tests/test_account_tier_admin.py#L198) (Zeile 198)
- [test_lookup_accepts_an_email](../../tests/test_account_tier_admin.py#L221) (Zeile 221)
- [test_listing_covers_the_legacy_premium_tag](../../tests/test_account_tier_admin.py#L230) (Zeile 230)
- [test_recent_changes_are_readable](../../tests/test_account_tier_admin.py#L243) (Zeile 243)
- [test_endpoints_require_admin](../../tests/test_account_tier_admin.py#L256) (Zeile 256)
- [test_put_sets_the_tier](../../tests/test_account_tier_admin.py#L268) (Zeile 268)
- [test_put_rejects_a_tier_outside_the_three](../../tests/test_account_tier_admin.py#L279) (Zeile 279)
- [test_lookup_of_an_unknown_account_is_a_404](../../tests/test_account_tier_admin.py#L289) (Zeile 289)
- [test_unknown_account_has_structured_error_in_real_main_app](../../tests/test_account_tier_admin.py#L300) (Zeile 300)

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

**Lauf:** 16 bestanden.

**Geprüftes Verhalten:** Realistischer großer Prompt bei 20.933 Resttokens; offline Unicode/Spezialtokens und Schema-Overhead; reduzierte Output-Caps in Request und Receipt; Suchreservierung erst bei Bedarf; paralleles Warten inklusive Stop ohne doppelte Calls; erschöpftes Budget ohne Dispatch; Teilantwort bei Outputlimit; Contextfenster und Reasoningminimum; Systemprompt/Workerfreigabe; Fortsetzung nach nativer Suche ohne doppelte Suche. Aktualisierung 02.10.2026: Suche reserviert Resultate erst bei Bedarf; parallele Vergleiche reduzieren Suchumfang statt auf unnötige Reserve zu warten.

**Grenzen und Doubles:** Provideraufrufe sind geskriptet und Firestore ist ein Fake. Die lokale Tokenzählung ist keine Bestätigung der Tokenisierung jedes Providers.

**Prüfauftrag für den Folgeaudit:** Grenzen je tatsächlichem Modellkontext, reservierter Suchumfang und langlaufende Waiter im Emulator abgleichen.

**Direkte Codeverweise:** [app/services/agent_costs.py](../../app/services/agent_costs.py), [app/services/agent_policy.py](../../app/services/agent_policy.py), [app/services/agent_quota.py](../../app/services/agent_quota.py), [app/services/agent_tokens.py](../../app/services/agent_tokens.py), [app/services/agent_tools.py](../../app/services/agent_tools.py), [app/services/llm/agent_client.py](../../app/services/llm/agent_client.py), [app/services/llm/provider_runtime.py](../../app/services/llm/provider_runtime.py).

**Direkte Testhelfer:** [tests/test_agent_comparison.py](../../tests/test_agent_comparison.py), [tests/test_agent_continuation.py](../../tests/test_agent_continuation.py), [tests/test_agent_runs.py](../../tests/test_agent_runs.py).

<details>
<summary>12 Testdefinitionen und ihre Quellstellen</summary>

- [test_screenshot_sized_prompt_fits_20933_tokens_without_byte_reservation](../../tests/test_agent_admission.py#L51) (Zeile 51)
- [test_offline_counting_accepts_unicode_and_special_token_literals](../../tests/test_agent_admission.py#L70) (Zeile 70)
- [test_small_remaining_budget_sets_provider_and_receipt_output_cap](../../tests/test_agent_admission.py#L81) (Zeile 81)
- [test_search_does_not_reserve_its_results_before_the_search](../../tests/test_agent_admission.py#L100) (Zeile 100)
- [test_parallel_comparison_waits_for_receipt_instead_of_failing_or_shrinking](../../tests/test_agent_admission.py#L113) (Zeile 113)
- [test_truly_exhausted_budget_does_not_dispatch_or_leak_local_reservation](../../tests/test_agent_admission.py#L164) (Zeile 164)
- [test_output_limit_preserves_partial_answer_without_claiming_completion](../../tests/test_agent_admission.py#L173) (Zeile 173)
- [test_context_window_can_fit_reduced_output_without_losing_messages](../../tests/test_agent_admission.py#L186) (Zeile 186)
- [test_explicit_reasoning_budget_is_not_shrunk_below_provider_minimum](../../tests/test_agent_admission.py#L196) (Zeile 196)
- [test_consensus_default_overrides_legacy_prompt_and_disabled_workers_are_not_advertised](../../tests/test_agent_admission.py#L206) (Zeile 206)
- [test_server_search_final_answer_resumes_consensus_without_repeating_search](../../tests/test_agent_admission.py#L217) (Zeile 217)
- [test_parallel_comparison_takes_a_smaller_search_instead_of_waiting](../../tests/test_agent_admission.py#L253) (Zeile 253)

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

**Lauf:** 5 bestanden.

**Geprüftes Verhalten:** Gemeinsames Tokenkonto für Free/Plus/Pro/Admin mit separaten Schätzungen für Compare/Consensus/Deep Think; alte daily_token_limit-Konfiguration entfällt, Normalisierung und revisioniertes Speichern/Reset bleiben geprüft.

**Grenzen und Doubles:** Concurrency ist durch den Fake synchronisiert; keine echte Firestore-Transaktion oder laufender Browser.

**Prüfauftrag für den Folgeaudit:** Verteilte Cacheinvalidierung und Reset bei aktiven Calls mit test_agent_comparison.py und Emulator abgleichen.

**Direkte Codeverweise:** [app/api/routers/admin.py](../../app/api/routers/admin.py), [app/core/rate_limit.py](../../app/core/rate_limit.py), [app/services/agent_budget_config.py](../../app/services/agent_budget_config.py).

**Direkte Testhelfer:** [tests/test_prompt_config.py](../../tests/test_prompt_config.py).

<details>
<summary>5 Testdefinitionen und ihre Quellstellen</summary>

- [test_defaults_cover_every_tier_and_mode_and_ignore_the_legacy_agent_limit](../../tests/test_agent_budget_config.py#L13) (Zeile 13)
- [test_tier_keys_and_modes](../../tests/test_agent_budget_config.py#L34) (Zeile 34)
- [test_cached_configuration_and_atomic_reset_without_scanning_users](../../tests/test_agent_budget_config.py#L43) (Zeile 43)
- [test_reset_is_revision_guarded_and_write_errors_do_not_change_cached_budget](../../tests/test_agent_budget_config.py#L65) (Zeile 65)
- [test_admin_limit_and_reset_routes_require_role_and_revision](../../tests/test_agent_budget_config.py#L98) (Zeile 98)

</details>

<a id="test-agent-calendar-py"></a>

## test_agent_calendar.py

**Quelle:** [tests/test_agent_calendar.py](../../tests/test_agent_calendar.py) · **Bereiche:** Google, Agent.

**Ebene:** Kalender-Service und HTTP-Adapter mit Fake-DB und Google-Transport.

**Lauf:** 9 bestanden.

**Geprüftes Verhalten:** Kalenderauswahl, Pagination, Zeitfenster, DST/Zeitzone, ganztägige Termine und Serien; Prepare schreibt nicht, Bestätigung bindet Hash und ETag, parallele Bestätigungen schreiben einmal. Unklarer Ausgang wird nur gelesen/reconciled; Erneuern erzeugt einen neuen prüfpflichtigen Vorschlag, Ownership und Widerruf sperren alte Aktionen.

**Grenzen und Doubles:** Google-Antworten, Auth und DB ersetzt; kein echtes OAuth, keine Einladungszustellung und kein nativer Firestore-Konkurrenzlauf.

**Prüfauftrag für den Folgeaudit:** Die benannten Mock-/Integrationsgrenzen am realen Adapter prüfen; Zuordnung und offene Aufgaben stehen in der Produktmatrix.

**Direkte Codeverweise:** [app/api/routers/agent_google.py](../../app/api/routers/agent_google.py), [app/core/rate_limit.py](../../app/core/rate_limit.py), [app/services/agent_actions.py](../../app/services/agent_actions.py), [app/services/agent_calendar.py](../../app/services/agent_calendar.py), [app/services/agent_files.py](../../app/services/agent_files.py), [app/services/chat_store.py](../../app/services/chat_store.py), [app/services/google_connections.py](../../app/services/google_connections.py), [app/services/llm/provider_runtime.py](../../app/services/llm/provider_runtime.py).

<details>
<summary>9 Testdefinitionen und ihre Quellstellen</summary>

- [test_prepare_does_not_write_and_confirmation_is_exact_once](../../tests/test_agent_calendar.py#L42) (Zeile 42)
- [test_unreliable_result_and_process_crash_are_never_resent](../../tests/test_agent_calendar.py#L62) (Zeile 62)
- [test_stale_revised_and_foreign_actions_cannot_execute](../../tests/test_agent_calendar.py#L85) (Zeile 85)
- [test_update_etag_series_instance_and_invitation_preview](../../tests/test_agent_calendar.py#L100) (Zeile 100)
- [test_read_selection_pagination_bounds_and_untrusted_events](../../tests/test_agent_calendar.py#L116) (Zeile 116)
- [test_dst_all_day_and_recurrence_validation](../../tests/test_agent_calendar.py#L131) (Zeile 131)
- [test_action_api_requires_owner_hash_and_displays_saved_result](../../tests/test_agent_calendar.py#L150) (Zeile 150)
- [test_actions_are_ordered_carry_google_data_and_calendar_name](../../tests/test_agent_calendar.py#L170) (Zeile 170)
- [test_renew_reprepares_stored_payload_without_model_or_write](../../tests/test_agent_calendar.py#L196) (Zeile 196)

</details>

<a id="test-agent-capacity-py"></a>

## test_agent_capacity.py

**Quelle:** [tests/test_agent_capacity.py](../../tests/test_agent_capacity.py) · **Bereiche:** Agent, Konten und Tarife.

**Ebene:** Agentkapazität, Routerstream und lokale Worker mit kontrolliertem Loop.

**Lauf:** 7 bestanden.

**Geprüftes Verhalten:** Prozess-/Ownerkapazität und Freigabe bei Fehler/Disconnect. Verweigert ein Kontotombstone Cleanup während Producerclose, bleibt GeneratorExit erhalten, kein Fehlerframe wird danach ausgegeben, Diagnose bleibt inhaltsfrei und Kapazität wird freigegeben.

**Grenzen und Doubles:** Loop-/Providergrenzen kontrolliert; native Browserreise ergänzt die tatsächliche Kontolöschung während Stream.

**Prüfauftrag für den Folgeaudit:** Die benannten Betriebs- und Testgrenzen bei künftigen Änderungen erneut prüfen; konkrete Paketnachweise stehen im Produktabgleich.

**Direkte Codeverweise:** [app/api/routers/agent.py](../../app/api/routers/agent.py), [app/services/agent_runtime.py](../../app/services/agent_runtime.py), [app/services/llm/agent_client.py](../../app/services/llm/agent_client.py), [app/services/persistence_guard.py](../../app/services/persistence_guard.py).

**Direkte Testhelfer:** [tests/test_agent_runs.py](../../tests/test_agent_runs.py).

<details>
<summary>7 Testdefinitionen und ihre Quellstellen</summary>

- [test_disconnect_preserves_generator_exit_when_deleted_account_blocks_cleanup](../../tests/test_agent_capacity.py#L16) (Zeile 16)
- [test_owner_limit_is_atomic_across_different_chats](../../tests/test_agent_capacity.py#L45) (Zeile 45)
- [test_crashed_owner_lease_expires_without_retrying_the_paid_receipt](../../tests/test_agent_capacity.py#L75) (Zeile 75)
- [test_local_admission_is_bounded_and_release_is_idempotent](../../tests/test_agent_capacity.py#L90) (Zeile 90)
- [test_local_capacity_rejects_before_creating_a_turn_and_preserves_replay](../../tests/test_agent_capacity.py#L104) (Zeile 104)
- [test_owner_capacity_failure_unlocks_unclaimed_turn_and_does_not_call_model](../../tests/test_agent_capacity.py#L127) (Zeile 127)
- [test_response_never_entered_releases_pending_turn_without_a_paid_claim](../../tests/test_agent_capacity.py#L141) (Zeile 141)

</details>

<a id="test-agent-chat-integrity-py"></a>

## test_agent_chat_integrity.py

**Quelle:** [tests/test_agent_chat_integrity.py](../../tests/test_agent_chat_integrity.py) · **Bereiche:** Agent.

**Ebene:** Chatpolicy und Delegation mit kontrollierten Completion-Klassen.

**Lauf:** 15 bestanden.

**Geprüftes Verhalten:** Vergleiche im Toolbatch enden vor Judge/Synthese; direkte Antworten erst nach vollständigem toolfreiem Ergebnis; Fehlturns erhalten Frage und gegebenenfalls markierte Teilantwort im Folgekontext; legitime Error-Texte und 6.000/6.001 Zeichen bleiben erhalten; fehlender Judgecall wird ohne extra Routing ergänzt; wiederholt ungültige Tools stoppen nach drei Calls; akzeptierte, überarbeitete und geprüfte Fallback-Workerergebnisse erreichen Synthese ohne veraltete/private Daten. Der aktuelle Diff passt Fixtures, Payloads oder Bezeichnungen an; die unten neu extrahierten Definitionen und Assertionstellen sind maßgeblich.

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

**Lauf:** 69 bestanden.

**Geprüftes Verhalten:** Exakte unveränderliche Antwortversion, Hashbindung und Quell-/Kontextübernahme; mehrere Vergleiche, fehlender Toolcall, Teilausfälle und Rate-Limits; vollständige Usage und Tagesquota, konkurrierende Claims/doppeltes Settlement; Reset während laufender Calls, Suchfallback, UTC-Wechsel und Reviewholds; konfigurierte familienabhängige Judge-Fallbacks inklusive 404/Timeout/leer/Cooldown; Disconnect, reine Recovery ohne Call sowie Settlementfehler vor/nach Commit ohne doppelte Generierung. Aktualisierung 02.10.2026: Parallele Vergleichsmodelle, Quorum/all-Modus und direkter Antwortschritt; späte Antworten fließen nur rechtzeitig in die Prüfung ein. Abgebrochene Teiltexte bleiben als incomplete lesbar, Outputlimits werden markiert. Tiefe, Datum und eine Suchkonfiguration gelten für alle Modelle; Judges suchen nicht, gespeicherte Reviewgröße begrenzt Antworten.

**Grenzen und Doubles:** „Real judges“ meint hier echte Parser/Orchestrierung mit synthetischen Judgeantworten. Die Transaktionsfehler werden im In-Memory-Store injiziert; keine reale Modellqualität/Firestore-Konkurrenz.

**Prüfauftrag für den Folgeaudit:** Fallbackkonfiguration bei neuen Modellfamilien, unterschiedliche Fehlerabfolgen und verteilte Commit-Ungewissheit abgleichen.

**Direkte Codeverweise:** [app/core/config.py](../../app/core/config.py), [app/services/agent_budget_config.py](../../app/services/agent_budget_config.py), [app/services/agent_comparison.py](../../app/services/agent_comparison.py), [app/services/agent_costs.py](../../app/services/agent_costs.py), [app/services/agent_delegation.py](../../app/services/agent_delegation.py), [app/services/agent_delegation_config.py](../../app/services/agent_delegation_config.py), [app/services/agent_policy.py](../../app/services/agent_policy.py), [app/services/agent_provider_limits.py](../../app/services/agent_provider_limits.py), [app/services/agent_quota.py](../../app/services/agent_quota.py), [app/services/llm/agent_client.py](../../app/services/llm/agent_client.py), [app/services/llm/engines.py](../../app/services/llm/engines.py), [app/services/llm/provider_runtime.py](../../app/services/llm/provider_runtime.py).

**Direkte Testhelfer:** [tests/test_agent_runs.py](../../tests/test_agent_runs.py).

<details>
<summary>40 Testdefinitionen und ihre Quellstellen</summary>

- [test_real_judges_exact_versions_context_sources_and_all_usage](../../tests/test_agent_comparison.py#L102) (Zeile 102)
- [test_fixed_answer_cannot_be_reopened_by_false_finalize_or_late_comparison](../../tests/test_agent_comparison.py#L135) (Zeile 135)
- [test_partial_or_failed_checks_never_certify_success](../../tests/test_agent_comparison.py#L158) (Zeile 158)
- [test_rate_limited_answer_is_distinct_from_successful_judges](../../tests/test_agent_comparison.py#L169) (Zeile 169)
- [test_review_binding_survives_saved_turn_projection_without_normalizing_text](../../tests/test_agent_comparison.py#L190) (Zeile 190)
- [test_review_issues_explain_each_missing_check](../../tests/test_agent_comparison.py#L221) (Zeile 221)
- [test_missing_tool_uses_existing_review_and_persists_checked_answer](../../tests/test_agent_comparison.py#L226) (Zeile 226)
- [test_atomic_daily_budget_and_duplicate_settlement](../../tests/test_agent_comparison.py#L237) (Zeile 237)
- [test_quota_rejection_distinguishes_empty_from_insufficient_reservation](../../tests/test_agent_comparison.py#L260) (Zeile 260)
- [test_admin_budget_is_enforced_and_reset_isolated_from_inflight_settlement](../../tests/test_agent_comparison.py#L271) (Zeile 271)
- [test_every_model_searches_with_one_configuration_and_judges_never_search](../../tests/test_agent_comparison.py#L302) (Zeile 302)
- [test_search_steps_down_by_rounds_and_reserves_one_bound_per_round](../../tests/test_agent_comparison.py#L345) (Zeile 345)
- [test_search_reservation_can_fall_back_without_extra_paid_claim](../../tests/test_agent_comparison.py#L366) (Zeile 366)
- [test_unknown_terminal_usage_releases_admission_and_utc_day_is_separate](../../tests/test_agent_comparison.py#L397) (Zeile 397)
- [test_configured_default_uses_cross_family_judges](../../tests/test_agent_comparison.py#L408) (Zeile 408)
- [test_gemini_chat_uses_standard_luna_then_flash_lite_for_both_judges](../../tests/test_agent_comparison.py#L419) (Zeile 419)
- [test_unavailable_chat_judges_stop_after_standard_fallback](../../tests/test_agent_comparison.py#L477) (Zeile 477)
- [test_midnight_moves_only_unspent_review_hold](../../tests/test_agent_comparison.py#L501) (Zeile 501)
- [test_disconnect_during_review_settles_every_paid_call_and_marks_stopped](../../tests/test_agent_comparison.py#L515) (Zeile 515)
- [test_later_run_failure_keeps_finished_review_result](../../tests/test_agent_comparison.py#L535) (Zeile 535)
- [test_failed_review_recovery_preserves_status_and_never_calls_provider](../../tests/test_agent_comparison.py#L551) (Zeile 551)
- [test_transient_settlement_failure_never_repeats_model_or_leaves_run_pending](../../tests/test_agent_comparison.py#L576) (Zeile 576)
- [test_comparison_models_get_their_own_completion_limit](../../tests/test_agent_comparison.py#L602) (Zeile 602)
- [test_answer_cut_off_at_the_output_limit_is_kept_as_marked_evidence](../../tests/test_agent_comparison.py#L614) (Zeile 614)
- [test_output_limit_without_text_names_the_cause_without_retry_advice](../../tests/test_agent_comparison.py#L627) (Zeile 627)
- [test_last_comparison_goes_straight_to_the_checked_answer](../../tests/test_agent_comparison.py#L652) (Zeile 652)
- [test_comparison_models_answer_at_the_same_time](../../tests/test_agent_comparison.py#L665) (Zeile 665)
- [test_answer_starts_at_quorum_and_a_late_answer_still_feeds_the_check](../../tests/test_agent_comparison.py#L739) (Zeile 739)
- [test_a_model_still_writing_at_the_check_is_stopped_and_reported](../../tests/test_agent_comparison.py#L755) (Zeile 755)
- [test_text_of_a_model_stopped_mid_answer_is_kept_as_incomplete_but_never_checked](../../tests/test_agent_comparison.py#L770) (Zeile 770)
- [test_partial_text_gives_way_before_the_review_exceeds_its_storage](../../tests/test_agent_comparison.py#L791) (Zeile 791)
- [test_quorum_sizes](../../tests/test_agent_comparison.py#L809) (Zeile 809)
- [test_depth_sets_the_answer_models_length_guidance](../../tests/test_agent_comparison.py#L817) (Zeile 817)
- [test_next_step_is_a_required_decision](../../tests/test_agent_comparison.py#L827) (Zeile 827)
- [test_a_failed_run_does_not_leave_a_model_shown_as_still_answering](../../tests/test_agent_comparison.py#L834) (Zeile 834)
- [test_answer_allowance_respects_the_saved_review_size](../../tests/test_agent_comparison.py#L855) (Zeile 855)
- [test_only_an_accepted_last_comparison_skips_the_routing_round](../../tests/test_agent_comparison.py#L862) (Zeile 862)
- [test_a_depth_fixed_in_settings_overrides_the_orchestrator](../../tests/test_agent_comparison.py#L874) (Zeile 874)
- [test_waiting_for_every_model_puts_a_slow_answer_into_the_text](../../tests/test_agent_comparison.py#L884) (Zeile 884)
- [test_quorum_modes](../../tests/test_agent_comparison.py#L897) (Zeile 897)

</details>

<a id="test-agent-continuation-py"></a>

## test_agent_continuation.py

**Quelle:** [tests/test_agent_continuation.py](../../tests/test_agent_continuation.py) · **Bereiche:** Agent.

**Ebene:** Langlauf-/Recovery-Verträge mit Fake-Uhr, Store und Providern.

**Lauf:** 13 bestanden.

**Geprüftes Verhalten:** 102 Calls über simulierte 17 Minuten bei lebender Lease; Tagesbudget bleibt begrenzend; Leaseverlängerung synchronisiert Sperren, stop/expired/superseded werden nicht wiederbelebt; Timeout bewahrt Teiltext mit sicherem Fehler; mehrere Vergleiche ohne fixen Reviewhold, alte Analysebudgets bleiben begrenzt; finalisierte Antwort unveränderlich; kurzer DB-Ausfall wird toleriert; Routing-/Vorantwortfehler bleiben ehrlich gespeichert und Recovery räumt verwaiste Produzenten ohne bezahlten Retry auf. Der aktuelle Diff passt Fixtures, Payloads oder Bezeichnungen an; die unten neu extrahierten Definitionen und Assertionstellen sind maßgeblich.

**Grenzen und Doubles:** Die 17 Minuten sind eine kontrollierte Uhr, kein 17-minütiger Dauertest. DB-Ausfall/Timeout/Leaseablauf werden simuliert; Provider und Datenbank sind ersetzt.

**Prüfauftrag für den Folgeaudit:** Reale Prozessneustarts, anhaltende Datenbankausfälle und Langzeitressourcenverbrauch separat prüfen.

**Direkte Codeverweise:** [app/services/agent_comparison.py](../../app/services/agent_comparison.py), [app/services/agent_delegation.py](../../app/services/agent_delegation.py), [app/services/agent_delegation_config.py](../../app/services/agent_delegation_config.py), [app/services/agent_policy.py](../../app/services/agent_policy.py), [app/services/agent_provider_limits.py](../../app/services/agent_provider_limits.py), [app/services/agent_quota.py](../../app/services/agent_quota.py), [app/services/agent_sessions.py](../../app/services/agent_sessions.py), [app/services/llm/agent_client.py](../../app/services/llm/agent_client.py), [app/services/llm/provider_runtime.py](../../app/services/llm/provider_runtime.py).

**Direkte Testhelfer:** [tests/test_agent_comparison.py](../../tests/test_agent_comparison.py), [tests/test_agent_runs.py](../../tests/test_agent_runs.py).

<details>
<summary>11 Testdefinitionen und ihre Quellstellen</summary>

- [test_more_than_one_hundred_steps_and_seventeen_minutes_complete_with_live_lease](../../tests/test_agent_continuation.py#L45) (Zeile 45)
- [test_daily_budget_still_stops_before_any_additional_paid_step_and_saves_reason](../../tests/test_agent_continuation.py#L80) (Zeile 80)
- [test_lease_renewal_keeps_all_fences_in_sync_but_never_revives_a_stopped_run](../../tests/test_agent_continuation.py#L99) (Zeile 99)
- [test_mid_answer_provider_timeout_preserves_text_and_safe_reason_in_history](../../tests/test_agent_continuation.py#L125) (Zeile 125)
- [test_many_comparisons_use_actual_call_reservations_without_fixed_review_hold](../../tests/test_agent_continuation.py#L141) (Zeile 141)
- [test_consensus_and_legacy_analysis_budgets_remain_bounded](../../tests/test_agent_continuation.py#L154) (Zeile 154)
- [test_account_budget_does_not_allow_more_comparisons_or_revisions_after_review](../../tests/test_agent_continuation.py#L161) (Zeile 161)
- [test_brief_database_outage_does_not_cancel_a_healthy_producer](../../tests/test_agent_continuation.py#L195) (Zeile 195)
- [test_interrupted_routing_recovery_preserves_failure_without_publishing_unconfirmed_text](../../tests/test_agent_continuation.py#L214) (Zeile 214)
- [test_failure_before_answer_preserves_question_activity_and_bookmark](../../tests/test_agent_continuation.py#L245) (Zeile 245)
- [test_recovery_reaps_expired_producer_and_restores_checkpoint_without_paid_retry](../../tests/test_agent_continuation.py#L269) (Zeile 269)

</details>

<a id="test-agent-contradictions-py"></a>

## test_agent_contradictions.py

**Quelle:** [tests/test_agent_contradictions.py](../../tests/test_agent_contradictions.py) · **Bereiche:** Quellenprüfung.

**Ebene:** Agent-Quellenprüfung mit Fetch-/Judge-Doubles.

**Lauf:** 11 bestanden.

**Geprüftes Verhalten:** Toolfreigabe und eingefrorene Settings; Originalbelege, getrenntes Quellenurteil, genaue Hashbindung und sämtliche Callkosten; fehlender Toolcall wird automatisch ergänzt; ungültige Belege ergeben partial; keine Widersprüche überspringen Fetch/Judge; Fallback wird abgerechnet; weitere Modellrunden ändern die fixierte Antwort nicht; Cancellation beendet alle Findings ohne pending. Der aktuelle Diff passt Fixtures, Payloads oder Bezeichnungen an; die unten neu extrahierten Definitionen und Assertionstellen sind maßgeblich.

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

**Geprüftes Verhalten:** Zwei gleichzeitig laufende Worker mit Rückfrage, Antwort, Rework und Review; Persistenz, Sequenzdeduplizierung, Pagination/Ownerbindung und Kosten; einfache Antwort ohne Delegation/Replaycall; Workerfehler mit Unknown-Kosten; atomare lokale/persistente Budgetreservierung im Fake; Stop joint Worker; Crash-/Leaserecovery; signierte Reasoningblöcke bleiben privat; Toolbatch-Ergebnisse; eingefrorene Konfiguration; Evaluationsgate lehnt schlechte/unvollständige Vergleiche ab; Nachricht während Generierung, Remote-Stop und geprüfter 429-Fallback. Aktualisierung 02.10.2026: Verschlüsselte Reasoningdetails werden als getrennte Fortsetzungsblöcke erhalten.

**Grenzen und Doubles:** Synchronisierte In-Memory-Transaktionen ersetzen Firestore. Evaluationsgate wird mit konstruierten Ergebniszeilen geprüft, nicht die Qualität echter Delegation. Der HTTP-Fall prüft Liste/Auth/fremden Chat und Detail-limit=51 (422), keinen erfolgreichen Detailbody und keinen Stop-HTTP-Handler (G-039).

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
- [test_bounded_parallel_tool_batch_is_replayed_with_every_result](../../tests/test_agent_delegation.py#L254) (Zeile 254)
- [test_delegation_endpoints_are_owner_bound_and_read_only](../../tests/test_agent_delegation.py#L265) (Zeile 265)
- [test_admin_enabled_delegation_is_frozen_and_replay_does_not_consult_new_config](../../tests/test_agent_delegation.py#L278) (Zeile 278)
- [test_quality_gate_rejects_cheap_bad_unknown_unpaired_or_unused_delegation](../../tests/test_agent_delegation.py#L299) (Zeile 299)
- [test_confirmed_own_fallback_finishes_without_echo_rework](../../tests/test_agent_delegation.py#L315) (Zeile 315)
- [test_message_during_active_generation_is_delivered_at_next_boundary](../../tests/test_agent_delegation.py#L328) (Zeile 328)
- [test_remote_stop_cancels_a_worker_with_an_active_stream](../../tests/test_agent_delegation.py#L365) (Zeile 365)
- [test_worker_429_can_use_checked_fallback_without_retrying_worker](../../tests/test_agent_delegation.py#L392) (Zeile 392)

</details>

<a id="test-agent-documents-py"></a>

## test_agent_documents.py

**Quelle:** [tests/test_agent_documents.py](../../tests/test_agent_documents.py) · **Bereiche:** Agent, Dateien und Dokumente.

**Ebene:** Dokument-Service mit echten DOCX-/PDF-Renderern und temporärem Speicher.

**Lauf:** 12 bestanden.

**Geprüftes Verhalten:** Erzeugte DOCX/PDF-Inhalte, Tabellen, Unicode, Quellenhashes und Vergleichsbelege; idempotente Erstellung, unveränderte alte Version, Revisionskonflikt, Parser-/Glyph-/Kontrollzeichenlimits, Abbruch, partieller Speicherfehler und Chatkaskade. Dateiliste zeigt chronologische Dokumenttitel und Versionen.

**Grenzen und Doubles:** DB und Objektablage lokal; Text-/Tabellenprüfung ersetzt keine vollständige visuelle Seitenkontrolle oder Cloud-Bucket-Integration.

**Prüfauftrag für den Folgeaudit:** Die benannten Mock-/Integrationsgrenzen am realen Adapter prüfen; Zuordnung und offene Aufgaben stehen in der Produktmatrix.

**Direkte Codeverweise:** [app/services/agent_documents.py](../../app/services/agent_documents.py), [app/services/agent_files.py](../../app/services/agent_files.py), [app/services/agent_runs.py](../../app/services/agent_runs.py), [app/services/agent_tools.py](../../app/services/agent_tools.py), [app/services/chat_store.py](../../app/services/chat_store.py), [app/services/llm/provider_runtime.py](../../app/services/llm/provider_runtime.py).

<details>
<summary>12 Testdefinitionen und ihre Quellstellen</summary>

- [test_real_docx_pdf_version_and_saved_provenance](../../tests/test_agent_documents.py#L24) (Zeile 24)
- [test_ownership_invalid_sources_and_storage_failure](../../tests/test_agent_documents.py#L60) (Zeile 60)
- [test_limits_unsupported_glyphs_and_cancellation](../../tests/test_agent_documents.py#L88) (Zeile 88)
- [test_synthesis_keeps_actual_document_results](../../tests/test_agent_documents.py#L105) (Zeile 105)
- [test_chat_deletion_removes_document_versions_and_manifest](../../tests/test_agent_documents.py#L115) (Zeile 115)
- [test_render_subprocess_does_not_import_firebase](../../tests/test_agent_documents.py#L127) (Zeile 127)
- [test_common_symbols_and_central_european_text_render](../../tests/test_agent_documents.py#L135) (Zeile 135)
- [test_unsupported_characters_are_named_in_the_error](../../tests/test_agent_documents.py#L145) (Zeile 145)
- [test_control_characters_are_rejected_before_rendering](../../tests/test_agent_documents.py#L154) (Zeile 154)
- [test_document_tools_get_a_larger_argument_limit_than_other_tools](../../tests/test_agent_documents.py#L162) (Zeile 162)
- [test_failed_revision_keeps_the_manifest_title](../../tests/test_agent_documents.py#L177) (Zeile 177)
- [test_file_list_is_chronological_and_carries_document_titles](../../tests/test_agent_documents.py#L190) (Zeile 190)

</details>

<a id="test-agent-files-py"></a>

## test_agent_files.py

**Quelle:** [tests/test_agent_files.py](../../tests/test_agent_files.py) · **Bereiche:** Agent, Dateien und Dokumente.

**Ebene:** Datei-Service, echte Extraktion und isolierte HTTP-Adapter.

**Lauf:** 24 bestanden.

**Geprüftes Verhalten:** Private Uploads/Downloads, Owner-/Chatbindung, Ablauf, Auswahl ohne erneute Extraktion, Quoten, Löschfences, Parserlimits, bild-/PDFfähige Modelle und ZDR-/native-PDF-Payload. Lokaler Entwicklungsspeicher, expliziter Bucket-Vorrang und kein stiller Disk-Fallback im Deployment; Retention paginiert trotz Fehlern.

**Grenzen und Doubles:** Fake-DB, lokaler Objektspeicher und ersetzte Provider/Auth; keine Cloud-IAM-/Bucket- oder echte Transaktionsprüfung.

**Prüfauftrag für den Folgeaudit:** Die benannten Mock-/Integrationsgrenzen am realen Adapter prüfen; Zuordnung und offene Aufgaben stehen in der Produktmatrix.

**Direkte Codeverweise:** [app/api/routers/agent_files.py](../../app/api/routers/agent_files.py), [app/core/rate_limit.py](../../app/core/rate_limit.py), [app/services/agent_files.py](../../app/services/agent_files.py), [app/services/agent_runs.py](../../app/services/agent_runs.py), [app/services/agent_tokens.py](../../app/services/agent_tokens.py), [app/services/chat_store.py](../../app/services/chat_store.py), [app/services/llm/agent_client.py](../../app/services/llm/agent_client.py), [app/services/llm/provider_runtime.py](../../app/services/llm/provider_runtime.py), [app/services/persistence_guard.py](../../app/services/persistence_guard.py).

<details>
<summary>23 Testdefinitionen und ihre Quellstellen</summary>

- [test_real_extraction_storage_download_and_owner_isolation](../../tests/test_agent_files.py#L28) (Zeile 28)
- [test_followup_reads_saved_excerpts_without_reextracting](../../tests/test_agent_files.py#L42) (Zeile 42)
- [test_wrong_chat_expiration_deletion_and_quota](../../tests/test_agent_files.py#L53) (Zeile 53)
- [test_chat_deletion_removes_objects_and_account_fence_blocks_upload](../../tests/test_agent_files.py#L68) (Zeile 68)
- [test_malformed_and_scanned_pdf_limits](../../tests/test_agent_files.py#L77) (Zeile 77)
- [test_images_are_capability_aware_and_private](../../tests/test_agent_files.py#L89) (Zeile 89)
- [test_cancelled_upload_and_concurrent_delete_do_not_leave_bytes](../../tests/test_agent_files.py#L103) (Zeile 103)
- [test_file_endpoints_validate_auth_and_return_private_download](../../tests/test_agent_files.py#L118) (Zeile 118)
- [test_storage_quota_is_atomic_and_parser_times_out](../../tests/test_agent_files.py#L145) (Zeile 145)
- [test_docx_tables_preserve_cell_boundaries_and_paragraph_locators](../../tests/test_agent_files.py#L157) (Zeile 157)
- [test_visual_admission_does_not_tokenize_base64_as_prose](../../tests/test_agent_files.py#L166) (Zeile 166)
- [test_real_comparison_loop_receives_same_saved_file_evidence](../../tests/test_agent_files.py#L172) (Zeile 172)
- [test_account_tombstone_prevents_recreation_during_upload](../../tests/test_agent_files.py#L191) (Zeile 191)
- [test_native_pdf_transport_never_selects_paid_ocr](../../tests/test_agent_files.py#L199) (Zeile 199)
- [test_missing_storage_fails_before_metadata_and_chat_deletion_still_works](../../tests/test_agent_files.py#L216) (Zeile 216)
- [test_missing_storage_returns_503](../../tests/test_agent_files.py#L233) (Zeile 233)
- [test_failed_upload_cleanup_surfaces_original_error](../../tests/test_agent_files.py#L250) (Zeile 250)
- [test_retention_pages_past_failures](../../tests/test_agent_files.py#L289) (Zeile 289)
- [test_native_pdf_only_when_it_fits_the_model_window](../../tests/test_agent_files.py#L306) (Zeile 306)
- [test_model_reads_never_evict_the_user_selection](../../tests/test_agent_files.py#L323) (Zeile 323)
- [test_local_checkout_gets_private_storage_without_setup](../../tests/test_agent_files.py#L342) (Zeile 342)
- [test_hosted_deploy_never_falls_back_to_local_disk](../../tests/test_agent_files.py#L353) (Zeile 353)
- [test_configured_bucket_wins_over_automatic_local_storage](../../tests/test_agent_files.py#L363) (Zeile 363)

</details>

<a id="test-agent-gmail-py"></a>

## test_agent_gmail.py

**Quelle:** [tests/test_agent_gmail.py](../../tests/test_agent_gmail.py) · **Bereiche:** Google, Agent, Dateien und Dokumente.

**Ebene:** Gmail-/Aktionsdienste und echter Agentloop mit Transport-/DB-Doubles.

**Lauf:** 21 bestanden.

**Geprüftes Verhalten:** Getrennte Lese-/Sendescopes, begrenzte Thread-/Bodypagination, MIME/Charset/HTML, private Anhangimporte und Dokumentversionen; Entwurf ohne Write, exakte Empfänger-/Reply-/Anhangbindung, erneute Prüfung nach Revision, unklarer Versand ohne automatisches Wiederholen, Reconciliation, Widerruf und Löschfences. Ein integrierter Loop verbindet Angebote, Vergleich, Dokument und Mailentwurf.

**Grenzen und Doubles:** Keine echte Google-Mailbox, Zustellung oder verteilter Transaktionslauf. Auth-/Providerantworten und Speicher sind Doubles; bestätigtes MIME ist kein produktiver Sendenachweis.

**Prüfauftrag für den Folgeaudit:** Die benannten Mock-/Integrationsgrenzen am realen Adapter prüfen; Zuordnung und offene Aufgaben stehen in der Produktmatrix.

**Direkte Codeverweise:** [app/services/agent_actions.py](../../app/services/agent_actions.py), [app/services/agent_calendar.py](../../app/services/agent_calendar.py), [app/services/agent_comparison.py](../../app/services/agent_comparison.py), [app/services/agent_delegation.py](../../app/services/agent_delegation.py), [app/services/agent_delegation_config.py](../../app/services/agent_delegation_config.py), [app/services/agent_documents.py](../../app/services/agent_documents.py), [app/services/agent_files.py](../../app/services/agent_files.py), [app/services/agent_gmail.py](../../app/services/agent_gmail.py), [app/services/agent_policy.py](../../app/services/agent_policy.py), [app/services/agent_runs.py](../../app/services/agent_runs.py), [app/services/chat_store.py](../../app/services/chat_store.py), [app/services/google_connections.py](../../app/services/google_connections.py), [app/services/llm/agent_client.py](../../app/services/llm/agent_client.py), [app/services/llm/provider_runtime.py](../../app/services/llm/provider_runtime.py), [app/services/persistence_guard.py](../../app/services/persistence_guard.py).

<details>
<summary>18 Testdefinitionen und ihre Quellstellen</summary>

- [test_separate_oauth_read_and_send_scopes_and_local_draft_before_send](../../tests/test_agent_gmail.py#L50) (Zeile 50)
- [test_search_and_complete_thread_pagination_keep_context_bounded](../../tests/test_agent_gmail.py#L64) (Zeile 64)
- [test_mime_external_body_html_charset_and_malformed_content](../../tests/test_agent_gmail.py#L91) (Zeile 91)
- [test_import_attachment_reuses_private_processing_and_respects_cancel_and_owner](../../tests/test_agent_gmail.py#L107) (Zeile 107)
- [test_draft_revision_exact_recipients_and_original_reply_metadata](../../tests/test_agent_gmail.py#L128) (Zeile 128)
- [test_confirm_sends_one_real_mime_with_exact_reply_and_saved_attachment](../../tests/test_agent_gmail.py#L142) (Zeile 142)
- [test_unknown_send_is_only_reconciled_and_blocks_duplicate_in_other_chat](../../tests/test_agent_gmail.py#L164) (Zeile 164)
- [test_deleted_foreign_or_changed_attachments_and_revoked_grants_fail_closed](../../tests/test_agent_gmail.py#L189) (Zeile 189)
- [test_offers_comparison_documents_and_gmail_draft_through_real_agent_loop](../../tests/test_agent_gmail.py#L204) (Zeile 204)
- [test_provider_limit_errors_never_retry_or_expose_response_content](../../tests/test_agent_gmail.py#L273) (Zeile 273)
- [test_action_expiry_and_account_deletion_cannot_restore_a_send](../../tests/test_agent_gmail.py#L290) (Zeile 290)
- [test_saved_calendar_only_turn_replays_after_gmail_schema_extension](../../tests/test_agent_gmail.py#L314) (Zeile 314)
- [test_unicode_line_breaks_in_subject_are_rejected_before_approval](../../tests/test_agent_gmail.py#L333) (Zeile 333)
- [test_local_build_failure_is_failed_not_unknown_and_does_not_fence](../../tests/test_agent_gmail.py#L338) (Zeile 338)
- [test_recipients_not_named_by_user_or_thread_are_flagged](../../tests/test_agent_gmail.py#L355) (Zeile 355)
- [test_chat_deletion_removes_actions_and_gmail_evidence](../../tests/test_agent_gmail.py#L363) (Zeile 363)
- [test_oversized_thread_page_records_no_evidence](../../tests/test_agent_gmail.py#L374) (Zeile 374)
- [test_renew_after_send_grant_and_recipient_removal_needs_fresh_review](../../tests/test_agent_gmail.py#L392) (Zeile 392)

</details>

<a id="test-agent-http-contract-py"></a>

## test_agent_http_contract.py

**Quelle:** [tests/test_agent_http_contract.py](../../tests/test_agent_http_contract.py) · **Bereiche:** Agent, Authentifizierung, Konten und Tarife.

**Ebene:** Registrierte main.app mit echten Middleware-, Auth-/Owner- und Serviceguards.

**Lauf:** 9 bestanden.

**Geprüftes Verhalten:** Reale Kapazitätsablehnung503 und API-UID-Limit429 bewahren serverseitiges Retry-After, sicheren Body und Nichtwrite. Agentdetails paginieren vollständig und binden UID/Chat/Turn; Pro-/Admin-/Tierausfallregeln und Parametergrenzen. Wiederholter Stop sperrt nur Zielturn, später Publish scheitert, private Antworten no-store.

**Grenzen und Doubles:** Firebase-SDK-Authentifizierung und DB ersetzt; externe Modell-, Mail- und Telegramgrenzen kontrolliert. Kein Live-OAuth oder produktiver Versand.

**Prüfauftrag für den Folgeaudit:** Die benannten Betriebs- und Testgrenzen bei künftigen Änderungen erneut prüfen; konkrete Paketnachweise stehen im Produktabgleich.

**Direkte Codeverweise:** [app/api/routers/agent.py](../../app/api/routers/agent.py), [app/api/routers/chat_history.py](../../app/api/routers/chat_history.py), [app/core/rate_limit.py](../../app/core/rate_limit.py), [app/core/security.py](../../app/core/security.py), [app/services/agent_policy.py](../../app/services/agent_policy.py), [app/services/agent_runs.py](../../app/services/agent_runs.py), [app/services/agent_runtime.py](../../app/services/agent_runtime.py), [app/services/llm/agent_client.py](../../app/services/llm/agent_client.py), [app/services/llm/provider_runtime.py](../../app/services/llm/provider_runtime.py).

<details>
<summary>6 Testdefinitionen und ihre Quellstellen</summary>

- [test_detail_pages_are_owner_bound_and_never_start_provider](../../tests/test_agent_http_contract.py#L56) (Zeile 56)
- [test_stop_fences_only_bound_turn_repeatedly_and_rejects_late_worker](../../tests/test_agent_http_contract.py#L97) (Zeile 97)
- [test_detail_and_stop_use_real_tier_policy](../../tests/test_agent_http_contract.py#L154) (Zeile 154)
- [test_agent_role_outage_is_retryable_without_private_data_or_write](../../tests/test_agent_http_contract.py#L172) (Zeile 172)
- [test_actual_agent_capacity_through_main_preserves_retry_header](../../tests/test_agent_http_contract.py#L187) (Zeile 187)
- [test_actual_api_uid_limit_through_main_preserves_only_server_retry_header](../../tests/test_agent_http_contract.py#L232) (Zeile 232)

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

**Geprüftes Verhalten:** Agent-spezifische Antwort-Disclosure, separater Direct-/Agent-Präferenzschalter, Free-Menü-Synchronisierung, Stacking, Sprung zu Antworten ohne Präferenzwechsel, explizite Footer-Beschriftung und Wiederherstellung bei manuellem Konsens/Bookmarks. Der aktuelle Diff passt Fixtures, Payloads oder Bezeichnungen an; die unten neu extrahierten Definitionen und Assertionstellen sind maßgeblich.

**Grenzen und Doubles:** Prüft Zeichenketten in JS, Templates und CSS; führt weder Interaktion noch Layout aus.

**Prüfauftrag für den Folgeaudit:** Mit ausführbaren Agent-Projektions- und Browserprüfungen abgleichen; Wechsel während laufender und wiederhergestellter Runs prüfen.

**Direkte Codeverweise:** [static/js/app-bootstrap.js](../../static/js/app-bootstrap.js), [static/js/run-mode.js](../../static/js/run-mode.js).

<details>
<summary>9 Testdefinitionen und ihre Quellstellen</summary>

- [test_answer_disclosure_is_agent_mode_only](../../tests/test_agent_mode_ui.py#L11) (Zeile 11)
- [test_compare_mode_is_a_direct_six_answer_flow](../../tests/test_agent_mode_ui.py#L31) (Zeile 31)
- [test_one_mode_selector_replaces_every_old_switch](../../tests/test_agent_mode_ui.py#L66) (Zeile 66)
- [test_the_switch_shows_the_setting_not_the_run_on_screen](../../tests/test_agent_mode_ui.py#L90) (Zeile 90)
- [test_direct_comparison_keeps_compact_copy_and_an_accurate_placeholder](../../tests/test_agent_mode_ui.py#L108) (Zeile 108)
- [test_composer_and_its_plus_menu_stay_above_the_answer_boxes](../../tests/test_agent_mode_ui.py#L123) (Zeile 123)
- [test_consensus_jumps_reveal_answers_without_disabling_agent_mode](../../tests/test_agent_mode_ui.py#L139) (Zeile 139)
- [test_consensus_actions_are_explicit_and_hover_preview_has_no_native_duplicate](../../tests/test_agent_mode_ui.py#L154) (Zeile 154)
- [test_answer_disclosure_is_restored_for_manual_consensus_and_bookmarks](../../tests/test_agent_mode_ui.py#L168) (Zeile 168)

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

**Geprüftes Verhalten:** Begrenzte Reasoningauszüge, Vorrang später Providerzusammenfassung und Ausschluss roher/verschlüsselter Details; Nutzerfortschritt mehrsprachig, validiert, vor Toolstart und unverändert gespeichert ohne Zusatzcalls; Unicode-Zeichenzähler und Drosselung; gemeldete Tokens ohne Schätzung; coalesced Live-Snapshots ohne zusätzliche Receipts/Transcript; Reworkusage zählt einmal bei voller Eventqueue. Der aktuelle Diff passt Fixtures, Payloads oder Bezeichnungen an; die unten neu extrahierten Definitionen und Assertionstellen sind maßgeblich.

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

**Geprüftes Verhalten:** Migration terminaler Unknown-Holds bei Erhalt lebender Reservierungen und idempotenter Revision; unbekannte Usage bleibt unbekannt; verlorene Leasemap räumt verwaiste Runs auf und übernimmt nur eindeutige gespeicherte Einzelcallusage; lebende/nachträglich erneuerte Lease bleibt aktiv; unvollständige/provisorische/aggregierte Mehrschrittwerte werden nicht geraten; gelöschter Chat und Tages-/Resetwechsel blockieren keine Quote dauerhaft. Aktualisierung 02.10.2026: Unbekannte Usage belastet begrenzte estimated Tokens; remaining zieht die Schätzung ab statt das volle Budget wieder freizugeben.

**Grenzen und Doubles:** Leases, alte Dokumente und Renewalrace werden im synchronisierten Fake hergestellt; keine echte Transaktionskonkurrenz zwischen Prozessen.

**Prüfauftrag für den Folgeaudit:** Legacy-Formate und unterschiedliche Crashzeitpunkte mit Emulatorprüfungen vergleichen.

**Direkte Codeverweise:** [app/services/agent_costs.py](../../app/services/agent_costs.py), [app/services/agent_quota.py](../../app/services/agent_quota.py), [app/services/llm/agent_client.py](../../app/services/llm/agent_client.py).

**Direkte Testhelfer:** [tests/test_agent_delegation.py](../../tests/test_agent_delegation.py), [tests/test_agent_runs.py](../../tests/test_agent_runs.py).

<details>
<summary>8 Testdefinitionen und ihre Quellstellen</summary>

- [test_refresh_migrates_terminal_unknown_holds_but_preserves_live_reservations](../../tests/test_agent_quota_recovery.py#L14) (Zeile 14)
- [test_terminal_unknown_usage_releases_admission_without_inventing_zero_usage](../../tests/test_agent_quota_recovery.py#L32) (Zeile 32)
- [test_reload_reaps_lost_lease_map_and_recovers_exact_saved_single_call_usage](../../tests/test_agent_quota_recovery.py#L50) (Zeile 50)
- [test_live_lease_is_never_reaped_by_a_budget_refresh](../../tests/test_agent_quota_recovery.py#L83) (Zeile 83)
- [test_renewal_committed_after_recovery_read_cannot_be_cancelled](../../tests/test_agent_quota_recovery.py#L92) (Zeile 92)
- [test_recovery_never_guesses_an_individual_receipt_from_ambiguous_saved_usage](../../tests/test_agent_quota_recovery.py#L109) (Zeile 109)
- [test_deleted_chat_cannot_leave_an_expired_receipt_blocking_the_account](../../tests/test_agent_quota_recovery.py#L144) (Zeile 144)
- [test_unreported_reservation_cannot_leak_across_day_or_reset](../../tests/test_agent_quota_recovery.py#L158) (Zeile 158)

</details>

<a id="test-agent-reasoning-continuation-py"></a>

## test_agent_reasoning_continuation.py

**Quelle:** [tests/test_agent_reasoning_continuation.py](../../tests/test_agent_reasoning_continuation.py) · **Bereiche:** Agent, Provider.

**Ebene:** Gestreamte Providerfragmente und Fortsetzungsnachrichten mit Doubles.

**Lauf:** 8 bestanden.

**Geprüftes Verhalten:** Gemini-Signatur am selben Index, getrennte verschlüsselte Blöcke, Typwechsel, Anthropic-Signaturen und fehlerhafte Fragmente; Signaturen bleiben aus sichtbarer Aktivität heraus und große Fortsetzungen bleiben begrenzt.

**Grenzen und Doubles:** Synthetische Providerereignisse; keine aktuelle Live-Kompatibilitätsmessung.

**Prüfauftrag für den Folgeaudit:** Die benannten Mock-/Integrationsgrenzen am realen Adapter prüfen; Zuordnung und offene Aufgaben stehen in der Produktmatrix.

**Direkte Codeverweise:** [app/services/llm/agent_client.py](../../app/services/llm/agent_client.py).

<details>
<summary>8 Testdefinitionen und ihre Quellstellen</summary>

- [test_gemini_text_then_signature_at_same_index_continues_the_tool_loop](../../tests/test_agent_reasoning_continuation.py#L42) (Zeile 42)
- [test_consecutive_encrypted_blocks_are_never_glued_together](../../tests/test_agent_reasoning_continuation.py#L65) (Zeile 65)
- [test_type_change_at_same_index_starts_a_new_block_instead_of_failing](../../tests/test_agent_reasoning_continuation.py#L75) (Zeile 75)
- [test_signed_anthropic_thinking_is_merged_and_replayed_with_one_signature](../../tests/test_agent_reasoning_continuation.py#L91) (Zeile 91)
- [test_unsigned_anthropic_thinking_is_not_replayed](../../tests/test_agent_reasoning_continuation.py#L103) (Zeile 103)
- [test_distinct_indices_and_ids_stay_separate_blocks](../../tests/test_agent_reasoning_continuation.py#L112) (Zeile 112)
- [test_malformed_reasoning_fragments_do_not_end_the_run](../../tests/test_agent_reasoning_continuation.py#L124) (Zeile 124)
- [test_oversized_reasoning_continuation_is_still_bounded](../../tests/test_agent_reasoning_continuation.py#L133) (Zeile 133)

</details>

<a id="test-agent-reliability-py"></a>

## test_agent_reliability.py

**Quelle:** [tests/test_agent_reliability.py](../../tests/test_agent_reliability.py) · **Bereiche:** Streaming und Wiederherstellung.

**Ebene:** Agentintegration einschließlich HTTPX-MockTransport.

**Lauf:** 19 bestanden.

**Geprüftes Verhalten:** Alte Receipts verdecken keine reparierbaren Reservierungen; Familiencap und unmögliche Admission; Stop vor Claim und zwischen Status/Dispatch; Agentstatus beschädigt keinen Consensus-Turn; Pre-Admission-Lease, superseded Turn und Initialisierungsfehler; gespeicherte Teilsynthese; fertige Vergleichsantwort wird vor langsamem Peer checkpointed; Stillstand mit/ohne Heartbeats schließt Stream und sichert Teiltext; produktiver Stream darf Stallintervall überschreiten. Aktualisierung 02.10.2026: Antwortschritt reduziert sein Tokenallowance vor unnötigem Queueing.

**Grenzen und Doubles:** Der Testname real_provider_socket_stall verwendet HTTPX MockTransport mit AsyncByteStream, keinen echten Netzwerksocket. Deadline künstlich verkürzt; DB-Fake.

**Prüfauftrag für den Folgeaudit:** Realer Netzabbruch/Proxybuffering und anhaltender Heartbeat ohne semantischen Fortschritt in Deploymentnähe prüfen.

**Direkte Codeverweise:** [app/api/routers/agent.py](../../app/api/routers/agent.py), [app/core/config.py](../../app/core/config.py), [app/services/agent_comparison.py](../../app/services/agent_comparison.py), [app/services/agent_provider_limits.py](../../app/services/agent_provider_limits.py), [app/services/agent_quota.py](../../app/services/agent_quota.py), [app/services/agent_runtime.py](../../app/services/agent_runtime.py), [app/services/agent_tools.py](../../app/services/agent_tools.py), [app/services/chat_store.py](../../app/services/chat_store.py), [app/services/llm/agent_client.py](../../app/services/llm/agent_client.py), [app/services/llm/provider_runtime.py](../../app/services/llm/provider_runtime.py).

**Direkte Testhelfer:** [tests/test_agent_admission.py](../../tests/test_agent_admission.py), [tests/test_agent_comparison.py](../../tests/test_agent_comparison.py), [tests/test_agent_continuation.py](../../tests/test_agent_continuation.py), [tests/test_agent_runs.py](../../tests/test_agent_runs.py).

<details>
<summary>14 Testdefinitionen und ihre Quellstellen</summary>

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
- [test_answer_step_starts_with_a_smaller_allowance_instead_of_queueing](../../tests/test_agent_reliability.py#L237) (Zeile 237)

</details>

<a id="test-agent-root-compaction-py"></a>

## test_agent_root_compaction.py

**Quelle:** [tests/test_agent_root_compaction.py](../../tests/test_agent_root_compaction.py) · **Bereiche:** Agent, Konten und Tarife.

**Ebene:** Session-/Usage-Repositories mit Fake-Transaktionen.

**Lauf:** 7 bestanden.

**Geprüftes Verhalten:** Hunderte Schritte halten das Rootdokument unter dem Größenlimit; kompaktierte Receipts verhindern Replay, bewahren Token-/Callsummen und laufende Reservierungen. Parallelabschluss, Recovery/Reaping und kontrollierter Stop vor übergroßem Write.

**Grenzen und Doubles:** Die Fake-DB beweist keine Firestore-Dokumentgrößen-/Retrygarantie im Mehrinstanzbetrieb.

**Prüfauftrag für den Folgeaudit:** Die benannten Mock-/Integrationsgrenzen am realen Adapter prüfen; Zuordnung und offene Aufgaben stehen in der Produktmatrix.

**Direkte Codeverweise:** [app/services/agent_costs.py](../../app/services/agent_costs.py), [app/services/agent_provider_limits.py](../../app/services/agent_provider_limits.py), [app/services/agent_quota.py](../../app/services/agent_quota.py), [app/services/agent_sessions.py](../../app/services/agent_sessions.py), [app/services/llm/agent_client.py](../../app/services/llm/agent_client.py), [app/services/llm/provider_runtime.py](../../app/services/llm/provider_runtime.py).

<details>
<summary>7 Testdefinitionen und ihre Quellstellen</summary>

- [test_hundreds_of_sequential_steps_keep_the_root_bounded_without_losing_usage](../../tests/test_agent_root_compaction.py#L36) (Zeile 36)
- [test_compacted_previous_step_still_authorizes_the_next_step_and_replays_are_refused](../../tests/test_agent_root_compaction.py#L69) (Zeile 69)
- [test_parallel_worker_settlements_keep_running_leases_and_exact_usage](../../tests/test_agent_root_compaction.py#L87) (Zeile 87)
- [test_oversized_root_is_a_saved_resumable_stop_not_a_write_failure](../../tests/test_agent_root_compaction.py#L121) (Zeile 121)
- [test_aggregates_compose_with_earlier_aggregates_and_unknown_calls](../../tests/test_agent_root_compaction.py#L140) (Zeile 140)
- [test_reaping_after_compaction_keeps_every_worker_step_usage](../../tests/test_agent_root_compaction.py#L150) (Zeile 150)
- [test_unmetered_first_fold_keeps_its_call_count](../../tests/test_agent_root_compaction.py#L178) (Zeile 178)

</details>

<a id="test-agent-runs-py"></a>

## test_agent_runs.py

**Quelle:** [tests/test_agent_runs.py](../../tests/test_agent_runs.py) · **Bereiche:** Agent.

**Ebene:** Store-/API-Verträge mit Auth-/Transport-Doubles.

**Lauf:** 38 bestanden.

**Geprüftes Verhalten:** Token-/Kostenvalidierung ohne doppelte Reasoningtokens; genau einmalige parallele Claims/Settlements, vollständiger Folgekontext und Quellenerhalt; Chat-/Accountlöschsperren und Transaktionsretry; kein Pipelinewechsel; toolfreier SSE-Client; serverseitige Pro/Admin-/Owner-/Schema-Grenzen, reine Recovery, alter Replay überschreibt kein neues Bookmark; Kosten nach Providerfehler und aktuelle Quotafehler; Disconnectcleanup und Receiptlöschung; Katalog/Reasoning/Modellrouting, eingefrorene Auswahl und kleine Kontextfenster; keine unnötigen model_answers-Reads. Aktualisierung 02.10.2026: Finalereignisse enthalten zusätzlich den Google-Datenstatus.

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
- [test_access_is_enforced_on_server](../../tests/test_agent_runs.py#L256) (Zeile 256)
- [test_foreign_chat_and_client_supplied_models_or_usage_are_rejected](../../tests/test_agent_runs.py#L268) (Zeile 268)
- [test_recovery_never_starts_a_new_call](../../tests/test_agent_runs.py#L278) (Zeile 278)
- [test_old_replay_keeps_newest_bookmark_and_sums_both_calls](../../tests/test_agent_runs.py#L288) (Zeile 288)
- [test_provider_error_after_usage_still_records_cost](../../tests/test_agent_runs.py#L300) (Zeile 300)
- [test_quota_failure_returns_current_allowance_and_reservation_reason](../../tests/test_agent_runs.py#L337) (Zeile 337)
- [test_disconnect_closes_producer_and_settles_unknown_usage](../../tests/test_agent_runs.py#L361) (Zeile 361)
- [test_account_cleanup_removes_step_receipts](../../tests/test_agent_runs.py#L380) (Zeile 380)
- [test_catalog_reuses_allowlist_and_restricts_reasoning](../../tests/test_agent_runs.py#L388) (Zeile 388)
- [test_invalid_selections_do_not_start_or_lock_a_turn](../../tests/test_agent_runs.py#L425) (Zeile 425)
- [test_model_effort_snapshot_switch_and_recovery_identity](../../tests/test_agent_runs.py#L436) (Zeile 436)
- [test_reasoning_stream_formats_are_bounded_and_never_leak_encrypted_data](../../tests/test_agent_runs.py#L459) (Zeile 459)
- [test_selected_model_prices_and_mandatory_provider_routes](../../tests/test_agent_runs.py#L490) (Zeile 490)
- [test_context_check_precedes_paid_claim_for_small_model](../../tests/test_agent_runs.py#L501) (Zeile 501)
- [test_agent_history_never_queries_empty_model_answers](../../tests/test_agent_runs.py#L516) (Zeile 516)
- [test_configured_default_uses_its_own_prices_context_and_routing](../../tests/test_agent_runs.py#L524) (Zeile 524)
- [test_unknown_default_requires_catalog_instead_of_assuming_deepseek_limits](../../tests/test_agent_runs.py#L540) (Zeile 540)
- [test_bookmark_conflict_and_nonstream_request_are_rejected_before_model_call](../../tests/test_agent_runs.py#L546) (Zeile 546)

</details>

<a id="test-agent-search-py"></a>

## test_agent_search.py

**Quelle:** [tests/test_agent_search.py](../../tests/test_agent_search.py) · **Bereiche:** Modelle und Provider.

**Ebene:** Usage-/Cooldownlogik, Agent-API und geskripteter Transport.

**Lauf:** 61 bestanden.

**Geprüftes Verhalten:** Providerkosten haben Vorrang vor Katalog inkl. Cache/Reasoning/Suche; ungültige Kosten bleiben unbekannt, null ist gültig; Catalogfallback und geteilte Usagechunks; getrennte Token-/Kostenreservierung; sichere Retry-After-Auswertung; Cooldown pro Key/Modell und begrenzter Cache; HTTP-/SSE-429 verhindert sofortigen zweiten bezahlten Claim; 404 liefert handlungsfähigen Fehler und gibt Chatslot frei.

**Grenzen und Doubles:** Providerkosten sind vorgegebene Zahlen und Preise aus dem lokalen Katalog; keine Rechnungsprüfung oder Live-Ratelimits. HTTP-Assertions laufen in eigener FastAPI-App; main.handle_http_exception fehlt. Retry-After dort beweist deshalb nicht dessen Erhalt in main.app (G-037).

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

**Geprüftes Verhalten:** Originalgespräch, konfigurierter Stil, Vergleichs- und Worker-/Suchbelege erreichen die isolierte Synthese; interner Tool-/Reasoning-Kontext bleibt draußen, Rollen/Felder sind begrenzt; mehrere oder teilweise Vergleiche; Providerrequest setzt reasoning.exclude bei gleicher Effort-Einstellung und ohne Tools; sichtbarer/gespeicherter Text bleibt exakt reviewgebunden. Der aktuelle Diff passt Fixtures, Payloads oder Bezeichnungen an; die unten neu extrahierten Definitionen und Assertionstellen sind maßgeblich.

**Grenzen und Doubles:** Synthetische Kontexte/Antworten, keine inhaltliche Bewertung durch reale Modelle. Die expliziten Privatmarker decken die verwendeten Beispiele ab.

**Prüfauftrag für den Folgeaudit:** Weitere Protokoll-/Metadatenfelder und sensible Inhalte in legitimen Nutzer-/Tooltexten im späteren Audit unterscheiden.

**Direkte Codeverweise:** [app/services/agent_comparison.py](../../app/services/agent_comparison.py), [app/services/llm/agent_client.py](../../app/services/llm/agent_client.py), [app/services/prompt_config.py](../../app/services/prompt_config.py).

**Direkte Testhelfer:** [tests/test_agent_comparison.py](../../tests/test_agent_comparison.py), [tests/test_agent_loop.py](../../tests/test_agent_loop.py), [tests/test_agent_runs.py](../../tests/test_agent_runs.py).

<details>
<summary>2 Testdefinitionen und ihre Quellstellen</summary>

- [test_synthesis_receives_original_conversation_and_evidence_without_tool_protocol](../../tests/test_agent_synthesis_context.py#L16) (Zeile 16)
- [test_standalone_synthesis_excludes_provider_reasoning_without_changing_effort_or_visible_text](../../tests/test_agent_synthesis_context.py#L71) (Zeile 71)

</details>

<a id="test-agent-usage-reconciliation-py"></a>

## test_agent_usage_reconciliation.py

**Quelle:** [tests/test_agent_usage_reconciliation.py](../../tests/test_agent_usage_reconciliation.py) · **Bereiche:** Agent, Konten und Tarife.

**Ebene:** Quota-/Receipt-Reconciliation mit In-Memory-Speicher.

**Lauf:** 11 bestanden.

**Geprüftes Verhalten:** Unbekannter Verbrauch belastet eine begrenzte Schätzung, ungestartete Aufrufe bleiben frei. Nachmessung ersetzt die Schätzung genau einmal, auch bei parallelen Versuchen; begrenzte Retries, fehlende Generation-ID, Vortagsbelege und ungültige Statistikdaten.

**Grenzen und Doubles:** Messdienst und Datenbank ersetzt; keine echten OpenRouter-Statistiken oder native Firestore-Transaktion.

**Prüfauftrag für den Folgeaudit:** Die benannten Mock-/Integrationsgrenzen am realen Adapter prüfen; Zuordnung und offene Aufgaben stehen in der Produktmatrix.

**Direkte Codeverweise:** [app/services/agent_quota.py](../../app/services/agent_quota.py), [app/services/agent_usage_reconciliation.py](../../app/services/agent_usage_reconciliation.py), [app/services/llm/agent_client.py](../../app/services/llm/agent_client.py).

<details>
<summary>11 Testdefinitionen und ihre Quellstellen</summary>

- [test_unknown_usage_is_charged_a_bounded_estimate_not_released_or_fully_charged](../../tests/test_agent_usage_reconciliation.py#L29) (Zeile 29)
- [test_repeated_unknown_calls_are_bounded_but_measured_calls_do_not_lock](../../tests/test_agent_usage_reconciliation.py#L40) (Zeile 40)
- [test_provably_unstarted_calls_are_still_released_completely](../../tests/test_agent_usage_reconciliation.py#L53) (Zeile 53)
- [test_reconciliation_replaces_the_estimate_exactly_once](../../tests/test_agent_usage_reconciliation.py#L66) (Zeile 66)
- [test_parallel_reconciliation_passes_apply_the_measurement_once](../../tests/test_agent_usage_reconciliation.py#L91) (Zeile 91)
- [test_unavailable_measurement_keeps_the_estimate_and_stops_after_bounded_attempts](../../tests/test_agent_usage_reconciliation.py#L101) (Zeile 101)
- [test_lookup_errors_count_as_attempts_and_old_receipts_are_finalized](../../tests/test_agent_usage_reconciliation.py#L113) (Zeile 113)
- [test_receipts_without_generation_id_keep_their_estimate_as_final](../../tests/test_agent_usage_reconciliation.py#L125) (Zeile 125)
- [test_generation_stats_prefer_native_counts_and_reject_garbage](../../tests/test_agent_usage_reconciliation.py#L132) (Zeile 132)
- [test_background_scheduling_is_disabled_in_unit_test_mode](../../tests/test_agent_usage_reconciliation.py#L141) (Zeile 141)
- [test_snapshot_schedules_reconciliation_for_yesterdays_estimates](../../tests/test_agent_usage_reconciliation.py#L145) (Zeile 145)

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

<a id="test-api-run-billing-identity-py"></a>

## test_api_run_billing_identity.py

**Quelle:** [tests/test_api_run_billing_identity.py](../../tests/test_api_run_billing_identity.py) · **Bereiche:** API, Konten und Tarife.

**Ebene:** Runrepository, Runner und isolierter API-Router mit Fakes.

**Lauf:** 11 bestanden.

**Geprüftes Verhalten:** Gelöschter Idempotenzschlüssel startet keine bezahlte Arbeit neu, HTTP liefert 410; neuer Schlüssel wird neu belastet. Paralleler Replay, begrenzter Tombstone, Legacy-Usage-Key, Mitternacht sowie Crash zwischen Reservierung und Statuscommit werden geprüft.

**Grenzen und Doubles:** Pipeline/Authentifizierung und DB ersetzt; keine echte Restart-/Mehrprozess-/Retention-Deploymentprüfung.

**Prüfauftrag für den Folgeaudit:** Die benannten Mock-/Integrationsgrenzen am realen Adapter prüfen; Zuordnung und offene Aufgaben stehen in der Produktmatrix.

**Direkte Codeverweise:** [app/api/routers/api_v1.py](../../app/api/routers/api_v1.py), [app/services/agent_budget_config.py](../../app/services/agent_budget_config.py), [app/services/api_consensus_runner.py](../../app/services/api_consensus_runner.py), [app/services/api_run_repository.py](../../app/services/api_run_repository.py), [app/services/usage_repository.py](../../app/services/usage_repository.py), [main.py](../../main.py).

<details>
<summary>11 Testdefinitionen und ihre Quellstellen</summary>

- [test_deleted_run_cannot_start_paid_work_again_under_the_same_key](../../tests/test_api_run_billing_identity.py#L106) (Zeile 106)
- [test_parallel_retries_after_deletion_never_start_a_pipeline](../../tests/test_api_run_billing_identity.py#L122) (Zeile 122)
- [test_new_key_after_deletion_starts_exactly_one_newly_charged_run](../../tests/test_api_run_billing_identity.py#L141) (Zeile 141)
- [test_retry_of_the_same_live_run_stays_idempotent](../../tests/test_api_run_billing_identity.py#L152) (Zeile 152)
- [test_deletion_removes_content_and_keeps_only_a_bounded_tombstone](../../tests/test_api_run_billing_identity.py#L165) (Zeile 165)
- [test_legacy_runs_without_own_receipt_keep_their_historic_usage_key](../../tests/test_api_run_billing_identity.py#L188) (Zeile 188)
- [test_route_returns_stable_410_for_a_deleted_key](../../tests/test_api_run_billing_identity.py#L196) (Zeile 196)
- [test_run_charged_before_midnight_finishes_after_midnight_without_second_charge](../../tests/test_api_run_billing_identity.py#L233) (Zeile 233)
- [test_execution_validity_stays_bounded](../../tests/test_api_run_billing_identity.py#L265) (Zeile 265)
- [test_crash_between_reserve_and_mark_reserved_is_terminalized_once](../../tests/test_api_run_billing_identity.py#L292) (Zeile 292)
- [test_route_terminalizes_an_accepted_run_whose_reservation_expired](../../tests/test_api_run_billing_identity.py#L318) (Zeile 318)

</details>

<a id="test-api-run-recovery-py"></a>

## test_api_run_recovery.py

**Quelle:** [tests/test_api_run_recovery.py](../../tests/test_api_run_recovery.py) · **Bereiche:** API, Konten und Tarife.

**Ebene:** Recoveryorchestrierung mit echten Run-/Quota-/Cleanup-Repositories.

**Lauf:** 4 bestanden.

**Geprüftes Verhalten:** Accepted/reserved Recovery, lebende/abgelaufene Leases und ausgeführte Backgroundaufträge; kein zweiter Providerstart oder Verbrauch. Retention/Backfill respektiert andere Runbindungen und lässt sich nach Fehler wiederholen.

**Grenzen und Doubles:** Transaktionsfähige DB-Doubles; Providerantwort und Executoraufnahme kontrolliert, gespeicherte Funktionen tatsächlich ausgeführt.

**Prüfauftrag für den Folgeaudit:** Die benannten Betriebs- und Testgrenzen bei künftigen Änderungen erneut prüfen; konkrete Paketnachweise stehen im Produktabgleich.

**Direkte Codeverweise:** [app/core/security.py](../../app/core/security.py), [app/services/api_account_cleanup.py](../../app/services/api_account_cleanup.py), [app/services/api_consensus_runner.py](../../app/services/api_consensus_runner.py), [app/services/api_run_repository.py](../../app/services/api_run_repository.py), [app/services/llm/provider_transport.py](../../app/services/llm/provider_transport.py), [app/services/usage_repository.py](../../app/services/usage_repository.py).

<details>
<summary>4 Testdefinitionen und ihre Quellstellen</summary>

- [test_restart_requeues_only_pre_provider_work_and_deduplicates_schedule](../../tests/test_api_run_recovery.py#L104) (Zeile 104)
- [test_retention_rechecks_expiry_and_preserves_rebound_idempotency](../../tests/test_api_run_recovery.py#L148) (Zeile 148)
- [test_backfill_preserves_existing_expiry_and_rebound_mapping](../../tests/test_api_run_recovery.py#L173) (Zeile 173)
- [test_recovery_backfill_failure_is_retryable_and_queue_submission_unwinds](../../tests/test_api_run_recovery.py#L198) (Zeile 198)

</details>

<a id="test-api-run-repository-py"></a>

## test_api_run_repository.py

**Quelle:** [tests/test_api_run_repository.py](../../tests/test_api_run_repository.py) · **Bereiche:** Persistenz, Öffentliche API.

**Ebene:** Repository mit synchronisiertem Firestore-Fake.

**Lauf:** 8 bestanden.

**Geprüftes Verhalten:** Idempotente Erstellung und Konflikt bei anderem Payload, gehashter Idempotenzschlüssel und Retention; Tombstone sperrt Erstellung und Workertransition; unter konkurrierenden Threads gewinnt ein Claim; accepted/reserved/running/succeeded und terminaler Replay; abgelaufene Lease führt ohne Requeue zu failed; nur Owner kann terminalen Run samt Mapping löschen und denselben Schlüssel neu verwenden. Der aktuelle Diff passt Fixtures, Payloads oder Bezeichnungen an; die unten neu extrahierten Definitionen und Assertionstellen sind maßgeblich.

**Grenzen und Doubles:** Nebenläufigkeit läuft gegen einen lokalen Fake mit Lock, nicht gegen verteilte Firestore-Transaktionen. Nicht jede theoretische Zustandskante wird allein durch den Erfolgssequenztest belegt.

**Prüfauftrag für den Folgeaudit:** Lease-Grenzzeitpunkte, Fehler vor/nach Commit und echte konkurrierende Worker gegen Emulator-/Agent-Tests abgleichen.

**Direkte Codeverweise:** [app/services/api_run_repository.py](../../app/services/api_run_repository.py), [app/services/persistence_guard.py](../../app/services/persistence_guard.py).

<details>
<summary>8 Testdefinitionen und ihre Quellstellen</summary>

- [test_create_is_idempotent_and_never_stores_plaintext_key](../../tests/test_api_run_repository.py#L119) (Zeile 119)
- [test_same_key_with_different_request_conflicts](../../tests/test_api_run_repository.py#L135) (Zeile 135)
- [test_pending_account_deletion_fences_api_run_creation](../../tests/test_api_run_repository.py#L142) (Zeile 142)
- [test_pending_account_deletion_fences_worker_transition](../../tests/test_api_run_repository.py#L155) (Zeile 155)
- [test_only_one_concurrent_worker_can_claim_running](../../tests/test_api_run_repository.py#L169) (Zeile 169)
- [test_full_state_sequence_and_terminal_idempotency](../../tests/test_api_run_repository.py#L186) (Zeile 186)
- [test_expired_running_lease_fails_without_requeueing](../../tests/test_api_run_repository.py#L200) (Zeile 200)
- [test_only_owner_can_delete_terminal_run_and_mapping](../../tests/test_api_run_repository.py#L217) (Zeile 217)

</details>

<a id="test-api-source-history-py"></a>

## test_api_source_history.py

**Quelle:** [tests/test_api_source_history.py](../../tests/test_api_source_history.py) · **Bereiche:** API, Quellen.

**Ebene:** Registrierte main.app mit echten Middleware-, Auth-/Owner- und Serviceguards.

**Lauf:** 9 bestanden.

**Geprüftes Verhalten:** Historischer Source-GET bindet UID, Run, Job, Antwort und Promptversion. Alle Seiten, negative Cursor, Revisionskonflikt und unveränderte Polls werden geprüft, ohne neue Sourcearbeit zu starten.

**Grenzen und Doubles:** Firebase-SDK-Authentifizierung und DB ersetzt; externe Modell-, Mail- und Telegramgrenzen kontrolliert. Kein Live-OAuth oder produktiver Versand.

**Prüfauftrag für den Folgeaudit:** Die benannten Betriebs- und Testgrenzen bei künftigen Änderungen erneut prüfen; konkrete Paketnachweise stehen im Produktabgleich.

**Direkte Codeverweise:** [app/services/api_run_repository.py](../../app/services/api_run_repository.py), [app/services/source_check_jobs.py](../../app/services/source_check_jobs.py), [app/services/source_check_repository.py](../../app/services/source_check_repository.py).

<details>
<summary>2 Testdefinitionen und ihre Quellstellen</summary>

- [test_historic_api_source_pages_owner_cursor_revision_and_cache](../../tests/test_api_source_history.py#L43) (Zeile 43)
- [test_historic_api_rejects_mismatched_snapshot_on_full_and_unchanged_polls](../../tests/test_api_source_history.py#L87) (Zeile 87)

</details>

<a id="test-ask-endpoints-py"></a>

## test_ask_endpoints.py

**Quelle:** [tests/test_ask_endpoints.py](../../tests/test_ask_endpoints.py) · **Bereiche:** Modelle und Provider.

**Ebene:** Router und Usage-Repository mit Auth-/Provider-Doubles.

**Lauf:** 14 bestanden.

**Geprüftes Verhalten:** Einheitliche fehlende Auth über Familien, Own-Key-Anforderungen/Login, Pro-only Deep Search und Premiummodelle; Plus-Anhänge/Quote, modellabhängige GLM-Dateifähigkeit und Meta-/Muse-Routing; Zeichen-/UTF-8-Bytegrenzen vor Providerarbeit; Entwicklerkey verbraucht Quote und wird bei Erschöpfung gesperrt, eigener Key verbraucht keine Quote. Aktualisierung 02.10.2026: Tokenkonto statt Runzählquote: Entwicklerkeys belasten metered operations, BYOK erzeugt kein Kontobudget; token_budget_exhausted meldet das aktuelle Konto.

**Grenzen und Doubles:** _run_ask bzw. Providerarbeit sind ersetzt; eigene FastAPI-App ohne komplette Middleware. Usage-Repository nutzt synchronisierten Fake.

**Prüfauftrag für den Folgeaudit:** Kompletter Request bis Transport, Grenzwerte je Familie und Middlewarekombination mit weiteren Tests abgleichen.

**Direkte Codeverweise:** [app/api/routers/chat.py](../../app/api/routers/chat.py), [app/core/config.py](../../app/core/config.py), [app/core/rate_limit.py](../../app/core/rate_limit.py), [app/services/agent_budget_config.py](../../app/services/agent_budget_config.py), [app/services/agent_quota.py](../../app/services/agent_quota.py), [app/services/usage_repository.py](../../app/services/usage_repository.py).

**Direkte Testhelfer:** [tests/usage_test_support.py](../../tests/usage_test_support.py).

<details>
<summary>14 Testdefinitionen und ihre Quellstellen</summary>

- [test_no_auth_error_is_uniform_across_model_families](../../tests/test_ask_endpoints.py#L61) (Zeile 61)
- [test_own_keys_flag_without_openrouter_key_is_rejected](../../tests/test_ask_endpoints.py#L79) (Zeile 79)
- [test_deep_search_is_pro_only](../../tests/test_ask_endpoints.py#L96) (Zeile 96)
- [test_deep_search_is_refused_for_plus](../../tests/test_ask_endpoints.py#L113) (Zeile 113)
- [test_plus_cannot_ask_a_premium_model](../../tests/test_ask_endpoints.py#L131) (Zeile 131)
- [test_plus_may_attach_a_file_and_gets_the_plus_quota](../../tests/test_ask_endpoints.py#L146) (Zeile 146)
- [test_glm_attachment_support_depends_on_the_effective_model](../../tests/test_ask_endpoints.py#L171) (Zeile 171)
- [test_ask_muse_serves_the_meta_family_and_gates_its_pro_model](../../tests/test_ask_endpoints.py#L205) (Zeile 205)
- [test_megabyte_style_one_word_question_is_rejected_before_provider_work](../../tests/test_ask_endpoints.py#L234) (Zeile 234)
- [test_multibyte_question_and_system_prompt_obey_utf8_byte_caps](../../tests/test_ask_endpoints.py#L252) (Zeile 252)
- [test_usage_limit_blocks_developer_key_path](../../tests/test_ask_endpoints.py#L287) (Zeile 287)
- [test_gemini_developer_path_uses_openrouter_and_counts_usage](../../tests/test_ask_endpoints.py#L308) (Zeile 308)
- [test_own_key_path_bypasses_usage_counting](../../tests/test_ask_endpoints.py#L340) (Zeile 340)
- [test_own_key_without_login_is_rejected_for_every_provider](../../tests/test_ask_endpoints.py#L373) (Zeile 373)

</details>

<a id="test-attachment-meta-py"></a>

## test_attachment_meta.py

**Quelle:** [tests/test_attachment_meta.py](../../tests/test_attachment_meta.py) · **Bereiche:** Anhänge, Agent.

**Ebene:** Reine Metadaten-Normalisierung.

**Lauf:** 2 bestanden.

**Geprüftes Verhalten:** Datei-ID und Lesewarnungen bleiben an der Agent-Nachricht; ungültige IDs werden verworfen und bisherige Consensus-Metadaten bleiben erhalten.

**Grenzen und Doubles:** Keine tatsächlichen Dateioperationen oder Browseransicht.

**Prüfauftrag für den Folgeaudit:** Die benannten Mock-/Integrationsgrenzen am realen Adapter prüfen; Zuordnung und offene Aufgaben stehen in der Produktmatrix.

**Direkte Codeverweise:** [app/services/llm/attachments.py](../../app/services/llm/attachments.py).

<details>
<summary>2 Testdefinitionen und ihre Quellstellen</summary>

- [test_agent_file_id_and_warnings_stay_with_the_message](../../tests/test_attachment_meta.py#L4) (Zeile 4)
- [test_foreign_ids_are_dropped_and_consensus_meta_is_unchanged](../../tests/test_attachment_meta.py#L13) (Zeile 13)

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

<a id="test-auxiliary-cli-py"></a>

## test_auxiliary_cli.py

**Quelle:** [tests/test_auxiliary_cli.py](../../tests/test_auxiliary_cli.py) · **Bereiche:** Benchmark, Werkzeuge.

**Ebene:** Echte CLIs und Runner in netzwerkgesperrten Subprozessen.

**Lauf:** 21 bestanden.

**Geprüftes Verhalten:** run_sample/run_experiment validieren Argumente vor Daten-/Providerarbeit, begrenzen Run-ID und endliches Budget; Dry-run, Live mit synthetischem Transport und Resume schreiben reale Manifest-/Record-/Resultdateien ohne Doppelcalls. Fehlende Credentials und entfernte Budgetguard als Negativkontrolle.

**Grenzen und Doubles:** Dataset und Providerantworten kontrolliert; keine kostenpflichtigen Modelle oder Livequalitätsmessung.

**Prüfauftrag für den Folgeaudit:** Die benannten Betriebs- und Testgrenzen bei künftigen Änderungen erneut prüfen; konkrete Paketnachweise stehen im Produktabgleich.

<details>
<summary>5 Testdefinitionen und ihre Quellstellen</summary>

- [test_invalid_execution_args_stop_before_dataset_or_provider](../../tests/test_auxiliary_cli.py#L77) (Zeile 77)
- [test_sample_run_id_cannot_escape_output_root](../../tests/test_auxiliary_cli.py#L84) (Zeile 84)
- [test_dry_run_then_live_then_resume_uses_real_runner_without_duplicate_calls](../../tests/test_auxiliary_cli.py#L90) (Zeile 90)
- [test_missing_credential_never_starts_provider](../../tests/test_auxiliary_cli.py#L105) (Zeile 105)
- [test_argument_boundary_oracle_detects_removed_finite_budget_guard](../../tests/test_auxiliary_cli.py#L111) (Zeile 111)

</details>

<a id="test-background-task-supervision-py"></a>

## test_background_task_supervision.py

**Quelle:** [tests/test_background_task_supervision.py](../../tests/test_background_task_supervision.py) · **Bereiche:** Sicherheit.

**Ebene:** Async-Supervisor und Startupfunktionen mit Cleanup-Doubles.

**Lauf:** 8 bestanden.

**Geprüftes Verhalten:** Neustart nach zwei Abstürzen mit erhaltenem Health-/Successzustand; Alarm nach wiederholtem Fehler und sofort bei einmaligem Task; Retention räumt vor erstem Sleep auf und meldet Counts; degraded/disabled-Health; Startup trennt bounded Konfigurationsread und strikten Backfill. Aktualisierung 02.10.2026: Retention enthält Receipts, Chatlöschjobs, Memory und Outbox; ein fehlerhafter Schritt verhindert spätere Schritte nicht.

**Grenzen und Doubles:** Kurze asynchrone Szenarien innerhalb eines Prozesses; Cleanup-/Konfigurationsarbeiten sind ersetzt. Kein kompletter echter Serverneustart.

**Prüfauftrag für den Folgeaudit:** Backoffgrenzen, dauerhafter Alarmversand und reale Lifespan-/Shutdown-Reihenfolge gegen Betriebsprüfungen abgleichen.

**Direkte Codeverweise:** [app/core/background_tasks.py](../../app/core/background_tasks.py), [app/services/answer_receipts.py](../../app/services/answer_receipts.py), [app/services/chat_store.py](../../app/services/chat_store.py), [app/services/memory_edit.py](../../app/services/memory_edit.py), [app/services/notification_outbox.py](../../app/services/notification_outbox.py), [app/services/retention_maintenance.py](../../app/services/retention_maintenance.py), [app/services/source_check_jobs.py](../../app/services/source_check_jobs.py), [main.py](../../main.py).

<details>
<summary>8 Testdefinitionen und ihre Quellstellen</summary>

- [test_supervisor_restarts_crashes_and_keeps_last_success_health](../../tests/test_background_task_supervision.py#L12) (Zeile 12)
- [test_supervisor_alerts_after_repeated_failure](../../tests/test_background_task_supervision.py#L50) (Zeile 50)
- [test_failed_one_shot_task_alerts_immediately](../../tests/test_background_task_supervision.py#L81) (Zeile 81)
- [test_retention_loop_runs_cleanup_before_first_sleep](../../tests/test_background_task_supervision.py#L100) (Zeile 100)
- [test_maintenance_health_reports_degraded_task_state](../../tests/test_background_task_supervision.py#L158) (Zeile 158)
- [test_startup_readiness_only_loads_bounded_configuration](../../tests/test_background_task_supervision.py#L168) (Zeile 168)
- [test_startup_configuration_write_runs_through_one_shot_wrapper](../../tests/test_background_task_supervision.py#L181) (Zeile 181)
- [test_retention_step_failure_does_not_stop_later_steps](../../tests/test_background_task_supervision.py#L194) (Zeile 194)

</details>

<a id="test-benchmark-audits-py"></a>

## test_benchmark_audits.py

**Quelle:** [tests/test_benchmark_audits.py](../../tests/test_benchmark_audits.py) · **Bereiche:** Benchmarks.

**Ebene:** Benchmarkrunner mit Fake-Transport und temporären Dateien.

**Lauf:** 9 bestanden.

**Geprüftes Verhalten:** Positions-/Optionspermutation konsistent, inkonsistent oder unentscheidbar; Consensus-Reihenfolge stabil/instabil; Pilot schreibt sämtliche Audit-/Ergebnisartefakte, Budgetstop überspringt Auswertung; Smoke schreibt acht Rollen-Zellen und ausdrücklich deaktivierte Audits, verlangt exakt eine Frage. Aktualisierung 02.10.2026: Gespeicherte Auditkosten werden ausdrücklich mitgeprüft.

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
- [RunPilotTests::test_run_pilot_skips_audits_when_budget_stops](../../tests/test_benchmark_audits.py#L115) (Zeile 115)
- [RunSmokeTests::test_run_smoke_writes_base_artifacts_without_e4_audits](../../tests/test_benchmark_audits.py#L137) (Zeile 137)
- [RunSmokeTests::test_run_smoke_validates_exactly_one_question](../../tests/test_benchmark_audits.py#L171) (Zeile 171)

</details>

<a id="test-benchmark-budget-py"></a>

## test_benchmark_budget.py

**Quelle:** [tests/test_benchmark_budget.py](../../tests/test_benchmark_budget.py) · **Bereiche:** Benchmark.

**Ebene:** Benchmarkrunner mit deterministischem Transport und temporären Artefakten.

**Lauf:** 4 bestanden.

**Geprüftes Verhalten:** Auditaufrufe und bereits bezahlte Fehler zählen zum Budget; enges Budget stoppt vor dem nächsten Audit. Resume fertiger Piloten bezahlt fertige Audits nicht erneut; fehlende Usage wird konservativ geschätzt. Der zuvor beobachtete zeitabhängige Manifestfehler ist durch die getrennte Clockkorrektur behoben.

**Grenzen und Doubles:** Keine bezahlten Modelle; aktuelle Runnerergebnisse gelten für die integrierte Konfiguration, nicht für Livepreise/-qualität.

**Prüfauftrag für den Folgeaudit:** Die benannten Betriebs- und Testgrenzen bei künftigen Änderungen erneut prüfen; konkrete Paketnachweise stehen im Produktabgleich.

**Direkte Codeverweise:** [benchmark/runner.py](../../benchmark/runner.py).

<details>
<summary>4 Testdefinitionen und ihre Quellstellen</summary>

- [BenchmarkBudgetTests::test_tight_budget_stops_before_the_first_uncovered_audit_call](../../tests/test_benchmark_budget.py#L53) (Zeile 53)
- [BenchmarkBudgetTests::test_resume_of_a_finished_pilot_does_not_pay_for_audits_again](../../tests/test_benchmark_budget.py#L73) (Zeile 73)
- [BenchmarkBudgetTests::test_failed_paid_attempts_count_toward_the_resumed_budget](../../tests/test_benchmark_budget.py#L93) (Zeile 93)
- [BenchmarkBudgetTests::test_audit_costs_without_usage_are_estimated_conservatively](../../tests/test_benchmark_budget.py#L113) (Zeile 113)

</details>

<a id="test-benchmark-cli-py"></a>

## test_benchmark_cli.py

**Quelle:** [tests/test_benchmark_cli.py](../../tests/test_benchmark_cli.py) · **Bereiche:** Benchmarks.

**Ebene:** CLI-Funktionen mit Dataset-/Runner-/Publisher-Doubles.

**Lauf:** 20 bestanden.

**Geprüftes Verhalten:** Argumente und Ausschlüsse, Run-ID-Priorität, Dry-Run ohne HTTP; Einzel-/Sammelpublikation nur fertiger Runs; Smoke/Pilot/Preview verlangen Budget; fehlende Credentials stoppen; große/finale Runs bleiben gated, freigegebene kleine Modi rufen passenden Runner auf; Konstanten für Gates/Previewcap.

**Grenzen und Doubles:** CLI main wird direkt aufgerufen, Live-Runs/Publikation sind ersetzt. Kein tatsächlicher bezahlter Benchmark oder Firestore-Publish.

**Prüfauftrag für den Folgeaudit:** Echte Shell-Exitcodes, fehlerhafte Manifestdateien und alle Gatekombinationen abgleichen.

**Direkte Codeverweise:** [app/services/benchmark_reports.py](../../app/services/benchmark_reports.py), [app/services/llm/credentials.py](../../app/services/llm/credentials.py), [benchmark/__main__.py](../../benchmark/__main__.py), [benchmark/config.py](../../benchmark/config.py), [benchmark/report_reader.py](../../benchmark/report_reader.py), [benchmark/runner.py](../../benchmark/runner.py).

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

**Direkte Codeverweise:** [benchmark/config.py](../../benchmark/config.py), [benchmark/dataset.py](../../benchmark/dataset.py).

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

<a id="test-benchmark-manifest-clock-py"></a>

## test_benchmark_manifest_clock.py

**Quelle:** [tests/test_benchmark_manifest_clock.py](../../tests/test_benchmark_manifest_clock.py) · **Bereiche:** Benchmark.

**Ebene:** Echter Manifestvergleich mit kontrollierter Uhr.

**Lauf:** 5 bestanden.

**Geprüftes Verhalten:** Sekunden, Tageswechsel und DST dürfen Resume nicht als Promptdrift ablehnen. Zeitzone, Instruktion und Modell-/Tokenkonfiguration bleiben bindend; alte Timestamp-Manifeste werden unverändert akzeptiert.

**Grenzen und Doubles:** Lokale Dateien und kontrollierte Zeitkontexte; kein Provideraufruf.

**Prüfauftrag für den Folgeaudit:** Die benannten Betriebs- und Testgrenzen bei künftigen Änderungen erneut prüfen; konkrete Paketnachweise stehen im Produktabgleich.

**Direkte Codeverweise:** [app/services/llm/consensus_engine.py](../../app/services/llm/consensus_engine.py), [benchmark/runner.py](../../benchmark/runner.py).

<details>
<summary>3 Testdefinitionen und ihre Quellstellen</summary>

- [test_resume_across_seconds_days_and_dst_keeps_manifest](../../tests/test_benchmark_manifest_clock.py#L15) (Zeile 15)
- [test_actual_configuration_drift_still_rejects_resume](../../tests/test_benchmark_manifest_clock.py#L26) (Zeile 26)
- [test_timestamped_legacy_manifest_resumes_without_rewriting_it](../../tests/test_benchmark_manifest_clock.py#L40) (Zeile 40)

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

<a id="test-benchmark-protocol-py"></a>

## test_benchmark_protocol.py

**Quelle:** [tests/test_benchmark_protocol.py](../../tests/test_benchmark_protocol.py) · **Bereiche:** Benchmark, Provider.

**Ebene:** Transport-, Record-, Resume- und Statistikpipeline mit HTTP-Response-Double.

**Lauf:** 15 bestanden.

**Geprüftes Verhalten:** HTTP-200-Fehlerobjekte und ungültige Responseformen bleiben Fehler, werden nicht als Enthaltung/Erfolg dedupliziert und folgen retry_failed. Gültiger Text ohne Buchstaben bleibt Enthaltung; private Fehlertexte/Credentials gelangen nicht in Records, auch bei Consensusfehlern.

**Grenzen und Doubles:** Synthetische HTTP-Antworten; keine Häufigkeitsmessung realer Providerfehler.

**Prüfauftrag für den Folgeaudit:** Die benannten Betriebs- und Testgrenzen bei künftigen Änderungen erneut prüfen; konkrete Paketnachweise stehen im Produktabgleich.

**Direkte Codeverweise:** [benchmark/results.py](../../benchmark/results.py), [benchmark/runner.py](../../benchmark/runner.py), [benchmark/transport.py](../../benchmark/transport.py).

<details>
<summary>4 Testdefinitionen und ihre Quellstellen</summary>

- [test_protocol_failures_are_not_successful_abstentions](../../tests/test_benchmark_protocol.py#L46) (Zeile 46)
- [test_valid_text_preserves_selection_and_abstention](../../tests/test_benchmark_protocol.py#L71) (Zeile 71)
- [test_exception_messages_cannot_leak_credentials_into_records](../../tests/test_benchmark_protocol.py#L84) (Zeile 84)
- [test_consensus_error_projection_never_persists_private_provider_details](../../tests/test_benchmark_protocol.py#L93) (Zeile 93)

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

**Direkte Codeverweise:** [benchmark/report_reader.py](../../benchmark/report_reader.py).

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

**Direkte Codeverweise:** [app/services/benchmark_reports.py](../../app/services/benchmark_reports.py), [benchmark/report_reader.py](../../benchmark/report_reader.py).

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

**Direkte Codeverweise:** [benchmark/results.py](../../benchmark/results.py), [benchmark/runner.py](../../benchmark/runner.py).

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

**Direkte Codeverweise:** [benchmark/audit.py](../../benchmark/audit.py), [benchmark/config.py](../../benchmark/config.py), [benchmark/runner.py](../../benchmark/runner.py).

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

**Quelle:** [tests/test_benchmark_transport.py](../../tests/test_benchmark_transport.py) · **Bereiche:** Benchmark, Provider.

**Ebene:** Benchmarktransport mit HTTP-Doubles.

**Lauf:** 6 bestanden.

**Geprüftes Verhalten:** Payload/Timeout, Fehler und Usage werden normalisiert. Provider-/Protokollfehler tragen sichere Fehlercodes; private Transporttexte werden nicht ungefiltert weitergegeben.

**Grenzen und Doubles:** Kein Liveprovider; Record-/Resume-/Abstentionvertrag separat in test_benchmark_protocol.py.

**Prüfauftrag für den Folgeaudit:** Die benannten Betriebs- und Testgrenzen bei künftigen Änderungen erneut prüfen; konkrete Paketnachweise stehen im Produktabgleich.

**Direkte Codeverweise:** [app/services/llm/engines.py](../../app/services/llm/engines.py), [benchmark/transport.py](../../benchmark/transport.py).

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

**Lauf:** 40 bestanden.

**Geprüftes Verhalten:** UID-Schreibbudget/429, Modellantworten und historische Labels, autoritativer Konsens statt Browserkopie, Follow-up/NFKC, stabiler Titel und Bookmark-ID, Chat-Konversation inkl. Fallback, Share-Revision/Reuse, kompakte Pagination und Owner-Scope, Löschen mit Chat-Cascade sowie Cursor-400/503. JS-Quelltextverträge betreffen Replay, Retry, Provenienz und Direct-Ansicht. Aktualisierung 02.10.2026: Dauerhafter Chatlöschjob wird vor Entfernen des Bookmarkhandles committed; scheitert die Jobanlage, bleibt der Handle erhalten.

**Grenzen und Doubles:** FakeBookmarkRef implementiert eigenes Merge-Verhalten; Chats/Share-Snapshots oft gestubbt. Cascade-Fehler darf Bookmark-Löschung nicht verhindern; Browserverträge sind statisch.

**Prüfauftrag für den Folgeaudit:** Firestore-Merge, gleichzeitige Saves/Löschung und durchgängigen Restore mit JS/E2E abgleichen.

**Direkte Codeverweise:** [app/api/routers/bookmarks.py](../../app/api/routers/bookmarks.py), [app/core/config.py](../../app/core/config.py), [app/core/rate_limit.py](../../app/core/rate_limit.py), [app/core/security.py](../../app/core/security.py), [app/services/chat_store.py](../../app/services/chat_store.py), [app/services/share_snapshots.py](../../app/services/share_snapshots.py).

<details>
<summary>37 Testdefinitionen und ihre Quellstellen</summary>

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
- [test_deleting_a_chat_bookmark_also_deletes_its_chat](../../tests/test_bookmarks.py#L1307) (Zeile 1307)
- [test_deleting_a_legacy_bookmark_touches_no_chat](../../tests/test_bookmarks.py#L1319) (Zeile 1319)
- [test_a_failing_chat_cascade_does_not_fail_the_bookmark_deletion](../../tests/test_bookmarks.py#L1330) (Zeile 1330)
- [test_chat_deletion_job_is_committed_before_the_bookmark_handle_is_removed](../../tests/test_bookmarks.py#L1345) (Zeile 1345)
- [test_bookmark_is_kept_when_the_chat_deletion_job_cannot_be_queued](../../tests/test_bookmarks.py#L1359) (Zeile 1359)
- [test_unavailable_cursor_signing_is_reported_as_a_server_error](../../tests/test_bookmarks.py#L1373) (Zeile 1373)
- [test_a_malformed_cursor_is_still_a_client_error](../../tests/test_bookmarks.py#L1402) (Zeile 1402)

</details>

<a id="test-chat-context-py"></a>

## test_chat_context.py

**Quelle:** [tests/test_chat_context.py](../../tests/test_chat_context.py) · **Bereiche:** Bookmarks und Verlauf, Kontext, Nutzergedächtnis.

**Ebene:** Service/Repository/Router mit FakeChatDatabase und künstlichem Compressor.

**Lauf:** 41 bestanden.

**Geprüftes Verhalten:** Deterministische erste Folgefrage, Frageauflösung vor Fan-out, inkrementelle Kompression/Version-Reuse/Lease, degradierte Fehler- und Langhistorienfälle, Provenienz, Owner-/Frage-/Provider-Bindung, NFKC und Caps, Prompt-/Secret-Allowlist, eigene versus Developer-Credentials und Usage-Claim. Entfernt Judge-Metadaten/fremde Antworten/alte Quellenmarker; Offline-Fixture prüft Signal-Erhalt. Cache-Tests prüfen Trennung, TTL, Begrenzung und nicht gecachte Fehler. Aktualisierung 02.10.2026: Späte Kontextbuilds ändern weder abgeschlossene Turns noch gelöschte Chats; konkurrierende Builds und wiederverwendete Bindung bleiben getrennt.

**Grenzen und Doubles:** Künstliche Compressor-/Query-Antworten; Offline-Evaluation misst Textsignale im deterministischen Kontext, keine Qualität eines echten LLM. Reentrantes Lease-Szenario ersetzt reale Mehrprozess-Konkurrenz.

**Prüfauftrag für den Folgeaudit:** Emulator-Kontexttransaktionen, semantische Kompressionsqualität und konkurrierende Cache-Misses gesondert abgleichen.

**Direkte Codeverweise:** [app/api/routers/chat.py](../../app/api/routers/chat.py), [app/api/routers/chat_history.py](../../app/api/routers/chat_history.py), [app/core/config.py](../../app/core/config.py), [app/core/rate_limit.py](../../app/core/rate_limit.py), [app/services/chat_context.py](../../app/services/chat_context.py), [app/services/chat_store.py](../../app/services/chat_store.py), [app/services/usage_repository.py](../../app/services/usage_repository.py).

**Direkte Testhelfer:** [tests/test_chat_history.py](../../tests/test_chat_history.py).

<details>
<summary>41 Testdefinitionen und ihre Quellstellen</summary>

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
- [test_late_context_build_never_rewrites_a_turn_completed_meanwhile](../../tests/test_chat_context.py#L1366) (Zeile 1366)
- [test_late_context_build_never_revives_a_deleted_chat](../../tests/test_chat_context.py#L1385) (Zeile 1385)
- [test_two_builds_cannot_overwrite_each_others_turn_binding](../../tests/test_chat_context.py#L1398) (Zeile 1398)
- [test_bound_pending_turn_rebuild_reads_its_existing_binding](../../tests/test_chat_context.py#L1416) (Zeile 1416)

</details>

<a id="test-chat-history-py"></a>

## test_chat_history.py

**Quelle:** [tests/test_chat_history.py](../../tests/test_chat_history.py) · **Bereiche:** Authentifizierung, Bookmarks und Verlauf, Persistenz.

**Ebene:** Router und ChatStore mit speicherbasiertem Transaktionsmodell.

**Lauf:** 77 bestanden.

**Geprüftes Verhalten:** Auth/Owner-Scope, signierte Cursor inkl. Nanosekunden und bewegter Grenze, monotone Turns, Request-ID-Idempotenz/NFKC, Eingabe-/Tier-/Quota-Gates. Completion schreibt separate Modellantworten, saniert Metadaten und Quellen, begrenzt Bytebudgets; Retry/Conflict/Failure ohne partielle Writes. Kompakte Listen und Lesebudget, rekursive Löschung inkl. fehlender Eltern, Tombstone-Fencing, Abandoned-Sweep, UID-Limits und persistente Anhangmetadaten. Aktualisierung 02.10.2026: Wiederaufnehmbare Chatkaskade überlebt Teilfehler und Crash nach Tombstone, blockiert späte Writes und korrigiert den Zähler einmal; verwaiste deleting-Chats werden übernommen, Kontolöschung entfernt Jobs.

**Grenzen und Doubles:** FakeChatDatabase stellt Transaktionen/Queries selbst nach; kein Firestore-Emulator in dieser Datei. Nachgewiesene Atomizität gilt für injizierte Fake-Commit-Fehler.

**Prüfauftrag für den Folgeaudit:** SDK-/Emulator-Verträge und echte parallele Erstellung/Completion/Löschung mit Transaktionsdateien abgleichen.

**Direkte Codeverweise:** [app/api/routers/chat_history.py](../../app/api/routers/chat_history.py), [app/core/config.py](../../app/core/config.py), [app/core/rate_limit.py](../../app/core/rate_limit.py), [app/core/security.py](../../app/core/security.py), [app/services/chat_context.py](../../app/services/chat_context.py), [app/services/chat_store.py](../../app/services/chat_store.py).

<details>
<summary>66 Testdefinitionen und ihre Quellstellen</summary>

- [test_all_chat_endpoints_require_verified_authentication](../../tests/test_chat_history.py#L432) (Zeile 432)
- [test_chat_creation_uses_server_id_and_storage_allowlist](../../tests/test_chat_history.py#L446) (Zeile 446)
- [test_chat_detail_is_owner_scoped_and_list_is_compact](../../tests/test_chat_history.py#L470) (Zeile 470)
- [test_chat_list_enforces_limit_and_owner_bound_cursor](../../tests/test_chat_history.py#L490) (Zeile 490)
- [test_chat_cursor_keeps_original_boundary_when_boundary_chat_moves](../../tests/test_chat_history.py#L511) (Zeile 511)
- [test_chat_cursor_preserves_nanoseconds_and_rejects_invalid_timestamp](../../tests/test_chat_history.py#L533) (Zeile 533)
- [test_chat_cursor_signing_secret_is_required_for_followup_page](../../tests/test_chat_history.py#L576) (Zeile 576)
- [test_first_and_second_turn_are_monotone_and_update_chat](../../tests/test_chat_history.py#L588) (Zeile 588)
- [test_turn_client_request_id_returns_original_for_normalized_identical_retry](../../tests/test_chat_history.py#L625) (Zeile 625)
- [test_turn_client_request_id_rejects_changed_payload](../../tests/test_chat_history.py#L647) (Zeile 647)
- [test_latest_question_is_bounded_preview_but_turn_keeps_full_question](../../tests/test_chat_history.py#L670) (Zeile 670)
- [test_turn_list_is_sorted_bounded_and_cursor_paginated](../../tests/test_chat_history.py#L693) (Zeile 693)
- [test_invalid_or_secret_bearing_turn_payloads_are_not_stored](../../tests/test_chat_history.py#L734) (Zeile 734)
- [test_premium_engine_needs_pro_at_turn_creation_like_at_consensus](../../tests/test_chat_history.py#L745) (Zeile 745)
- [test_unknown_and_foreign_chat_are_indistinguishable_for_turn_creation](../../tests/test_chat_history.py#L781) (Zeile 781)
- [test_completion_preflight_is_owner_bound_read_only_and_skips_answers](../../tests/test_chat_history.py#L798) (Zeile 798)
- [test_complete_turn_atomically_persists_six_separate_answer_documents](../../tests/test_chat_history.py#L831) (Zeile 831)
- [test_complete_turn_skips_empty_answers_and_derives_count_server_side](../../tests/test_chat_history.py#L883) (Zeile 883)
- [test_complete_turn_rejects_unknown_or_too_many_providers_before_writes](../../tests/test_chat_history.py#L905) (Zeile 905)
- [test_completion_limits_text_metadata_but_preserves_all_sources](../../tests/test_chat_history.py#L934) (Zeile 934)
- [test_completion_rejects_oversized_source_documents_without_partial_writes](../../tests/test_chat_history.py#L970) (Zeile 970)
- [test_completion_retry_is_idempotent_but_changed_payload_conflicts](../../tests/test_chat_history.py#L988) (Zeile 988)
- [test_completion_rejects_question_mismatch_failed_turn_and_invalid_result_id](../../tests/test_chat_history.py#L1019) (Zeile 1019)
- [test_fail_turn_is_allowlisted_idempotent_and_terminal](../../tests/test_chat_history.py#L1055) (Zeile 1055)
- [test_completion_transaction_failure_leaves_no_partial_state](../../tests/test_chat_history.py#L1099) (Zeile 1099)
- [test_turn_detail_is_owner_scoped_whitelisted_and_reads_six_known_docs](../../tests/test_chat_history.py#L1116) (Zeile 1116)
- [test_turn_list_stays_compact_after_completion_and_failure](../../tests/test_chat_history.py#L1162) (Zeile 1162)
- [test_turn_question_limit_matches_the_consensus_cap](../../tests/test_chat_history.py#L1199) (Zeile 1199)
- [test_turn_rejects_a_question_the_consensus_cap_would_truncate](../../tests/test_chat_history.py#L1203) (Zeile 1203)
- [test_longest_accepted_question_still_validates_after_the_consensus_cap](../../tests/test_chat_history.py#L1215) (Zeile 1215)
- [test_get_turn_reads_model_answers_with_one_query](../../tests/test_chat_history.py#L1239) (Zeile 1239)
- [test_model_answer_under_a_foreign_document_id_is_ignored](../../tests/test_chat_history.py#L1260) (Zeile 1260)
- [test_list_turn_details_checks_the_chat_once_for_the_whole_page](../../tests/test_chat_history.py#L1281) (Zeile 1281)
- [test_list_turn_details_keeps_pagination_identical_to_list_turns](../../tests/test_chat_history.py#L1309) (Zeile 1309)
- [test_list_turn_details_rejects_a_foreign_owner](../../tests/test_chat_history.py#L1326) (Zeile 1326)
- [test_delete_all_chats_removes_every_nested_level](../../tests/test_chat_history.py#L1341) (Zeile 1341)
- [test_delete_all_chats_descends_into_missing_parent_documents](../../tests/test_chat_history.py#L1364) (Zeile 1364)
- [test_delete_all_chats_leaves_other_owners_untouched](../../tests/test_chat_history.py#L1384) (Zeile 1384)
- [test_delete_all_chats_is_idempotent](../../tests/test_chat_history.py#L1399) (Zeile 1399)
- [test_delete_chat_removes_the_whole_tree](../../tests/test_chat_history.py#L1418) (Zeile 1418)
- [test_delete_chat_is_owner_scoped_and_uniformly_404](../../tests/test_chat_history.py#L1439) (Zeile 1439)
- [test_delete_chat_requires_authentication](../../tests/test_chat_history.py#L1452) (Zeile 1452)
- [test_deleting_a_chat_twice_reports_404_and_changes_nothing](../../tests/test_chat_history.py#L1462) (Zeile 1462)
- [test_deleting_chat_state_rejects_a_late_turn_before_it_can_write](../../tests/test_chat_history.py#L1473) (Zeile 1473)
- [test_deleting_chat_state_rejects_late_completion_and_failure_writes](../../tests/test_chat_history.py#L1491) (Zeile 1491)
- [test_account_deletion_tombstone_fences_late_chat_completion](../../tests/test_chat_history.py#L1516) (Zeile 1516)
- [test_account_deletion_tombstone_fences_late_chat_and_turn_creation](../../tests/test_chat_history.py#L1534) (Zeile 1534)
- [test_account_deletion_fences_normal_chat_delete_but_cleanup_can_continue](../../tests/test_chat_history.py#L1556) (Zeile 1556)
- [test_interrupted_chat_cascade_is_resumed_by_retention_and_counts_once](../../tests/test_chat_history.py#L1625) (Zeile 1625)
- [test_chat_deletion_survives_a_crash_right_after_the_tombstone](../../tests/test_chat_history.py#L1667) (Zeile 1667)
- [test_queued_chat_deletion_cannot_be_revived_by_late_writes](../../tests/test_chat_history.py#L1685) (Zeile 1685)
- [test_adopts_a_chat_stranded_in_deleting_without_a_job](../../tests/test_chat_history.py#L1707) (Zeile 1707)
- [test_account_deletion_removes_pending_chat_deletion_jobs](../../tests/test_chat_history.py#L1723) (Zeile 1723)
- [test_stale_pending_turn_is_retired_as_abandoned](../../tests/test_chat_history.py#L1749) (Zeile 1749)
- [test_a_recent_pending_turn_is_never_retired](../../tests/test_chat_history.py#L1768) (Zeile 1768)
- [test_sweep_never_touches_completed_or_failed_turns](../../tests/test_chat_history.py#L1785) (Zeile 1785)
- [test_chat_count_is_capped_per_owner_and_scoped_to_that_owner](../../tests/test_chat_history.py#L1809) (Zeile 1809)
- [test_chat_count_falls_back_to_a_bounded_scan_without_aggregation](../../tests/test_chat_history.py#L1831) (Zeile 1831)
- [test_turns_per_chat_are_capped_without_corrupting_the_counter](../../tests/test_chat_history.py#L1848) (Zeile 1848)
- [test_write_endpoints_are_rate_limited_per_account_not_only_per_ip](../../tests/test_chat_history.py#L1871) (Zeile 1871)
- [test_context_uid_budget_is_charged_on_post_not_turn_get](../../tests/test_chat_history.py#L1895) (Zeile 1895)
- [test_creating_a_turn_retires_an_abandoned_predecessor](../../tests/test_chat_history.py#L1941) (Zeile 1941)
- [test_a_failing_sweep_never_blocks_turn_creation](../../tests/test_chat_history.py#L1959) (Zeile 1959)
- [test_turn_keeps_the_attachment_meta_of_its_own_question](../../tests/test_chat_history.py#L1972) (Zeile 1972)
- [test_turn_attachments_never_carry_file_data_or_unknown_types](../../tests/test_chat_history.py#L2016) (Zeile 2016)
- [test_turn_attachment_meta_survives_completion](../../tests/test_chat_history.py#L2046) (Zeile 2046)

</details>

<a id="test-chat-session-ui-py"></a>

## test_chat_session_ui.py

**Quelle:** [tests/test_chat_session_ui.py](../../tests/test_chat_session_ui.py) · **Bereiche:** Bookmarks und Verlauf, Frontend, Kontext.

**Ebene:** Gemischt: Node-VM mit Fake-Fetch und Quelltextverträge.

**Lauf:** 11 bestanden.

**Geprüftes Verhalten:** Drei eingebettete Node-Skripte führen chat-session.js aus: Pending/Completed/Failed, stabile Request-IDs und Retry bei 503, Folge-Turn-Bindung, 202→200 Kontext-Aufbau, Kontextversion/Usage-Key, eigener Schlüssel bei degradiertem Kontext, 409, Abort, Reset und verständliche 403-Limitmeldungen. Weitere Quelltextprüfungen sichern Bundle-Reihenfolge, SSE-/Bookmark-Bindung, Replay-Gating, Archivierung, Antwortboxen und Payload-Allowlist ohne Secrets/Antworten. Aktualisierung 02.10.2026: Modellantwortnavigation über gemeinsame Reader-Schnittstelle; sichere Textlabels statt HTML.

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

<a id="test-claim-identity-judge-py"></a>

## test_claim_identity_judge.py

**Quelle:** [tests/test_claim_identity_judge.py](../../tests/test_claim_identity_judge.py) · **Bereiche:** Topics, Quellen.

**Ebene:** Echter Identityhelper, Parser und Retryplan mit Transportdouble.

**Lauf:** 14 bestanden.

**Geprüftes Verhalten:** Nur bekannte eindeutige Keys und echte JSON-Integer dürfen binden; unbekannt, doppelt, Bool, Float, String und Bereichsfehler werden verworfen. Promptfenster/Text/Tokens begrenzt, Modell-/Transport-/JSONfehler sicher behandelt, Logs ohne Modellinhalte.

**Grenzen und Doubles:** Synthetische Modellantworten; keine semantische Qualitätsmessung echter Claims.

**Prüfauftrag für den Folgeaudit:** Die benannten Betriebs- und Testgrenzen bei künftigen Änderungen erneut prüfen; konkrete Paketnachweise stehen im Produktabgleich.

**Direkte Codeverweise:** [app/services/llm/consensus_engine.py](../../app/services/llm/consensus_engine.py).

<details>
<summary>5 Testdefinitionen und ihre Quellstellen</summary>

- [test_known_unique_bindings_only](../../tests/test_claim_identity_judge.py#L19) (Zeile 19)
- [test_only_json_integer_indices_are_accepted](../../tests/test_claim_identity_judge.py#L38) (Zeile 38)
- [test_bounded_prompt_and_unmapped_outside_window](../../tests/test_claim_identity_judge.py#L42) (Zeile 42)
- [test_retry_fallback_is_bounded_and_logs_no_provider_content](../../tests/test_claim_identity_judge.py#L66) (Zeile 66)
- [test_empty_or_invalid_engine_returns_unmapped_without_transport](../../tests/test_claim_identity_judge.py#L93) (Zeile 93)

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

**Geprüftes Verhalten:** Antwortmapping über Familienkeys, Anzeigenamen und Legacyfelder; ausgeschlossene Familie fällt weg; genau konfigurierte Höchstzahl zulässig und zu viele Familien mit 400 abgelehnt. Der aktuelle Diff passt Fixtures, Payloads oder Bezeichnungen an; die unten neu extrahierten Definitionen und Assertionstellen sind maßgeblich.

**Grenzen und Doubles:** query_consensus/query_differences und Pending-Persistenz sind ersetzt; belegt Eingangsnormierung und Übergabe, keine Ergebnisqualität.

**Prüfauftrag für den Folgeaudit:** Konfligierende Legacy-/neue Felder, leere/unbekannte Familien und tatsächliche Modellanzahl im vollständigen Ablauf prüfen.

**Direkte Codeverweise:** [app/api/routers/chat.py](../../app/api/routers/chat.py), [app/core/config.py](../../app/core/config.py), [app/core/rate_limit.py](../../app/core/rate_limit.py).

<details>
<summary>5 Testdefinitionen und ihre Quellstellen</summary>

- [test_answers_field_keyed_by_family](../../tests/test_consensus_answer_contract.py#L65) (Zeile 65)
- [test_answers_field_keyed_by_display_name](../../tests/test_consensus_answer_contract.py#L76) (Zeile 76)
- [test_legacy_answer_fields_still_work](../../tests/test_consensus_answer_contract.py#L87) (Zeile 87)
- [test_excluded_family_is_dropped_from_the_run](../../tests/test_consensus_answer_contract.py#L99) (Zeile 99)
- [test_a_run_never_compares_more_than_the_configured_cap](../../tests/test_consensus_answer_contract.py#L111) (Zeile 111)

</details>

<a id="test-consensus-api-py"></a>

## test_consensus_api.py

**Quelle:** [tests/test_consensus_api.py](../../tests/test_consensus_api.py) · **Bereiche:** API, Konten und Tarife, Publisher, Öffentliche Freigaben.

**Ebene:** Main-App-API und Runner mit Repository-/LLM-/Scheduler-Doubles; einzelne Quelltextverträge.

**Lauf:** 27 bestanden.

**Geprüftes Verhalten:** OpenAPI-Key/Idempotency-Vertrag, Admin-Key-Management und Publisher-Konfiguration, accepted/duplicate Runs, serverseitiger Modellplan, Tier/Scope/Admin-/Account-Gates und Key-/IP-Throttling. Runner-Claim verhindert doppelte Starts/Usage, Scheduler begrenzt Arbeit, Expiry unterscheidet Reservierung/Verbrauch; Publish/List/Read/Revoke, Watch-Capacity-Skip und Direct-Index-Gates. Aktualisierung 02.10.2026: Deep Think verwendet die passende Tokenadmission; Publisher zeigt den aktuellen Providerplan ohne pauschalen Ausschluss.

**Grenzen und Doubles:** Auth/Firestore/LLM/Executor meist ersetzt; API-202-Duplikattest erwartet sogar zwei schedule-Aufrufe, eigentliche Deduplizierung separat geprüft. UI nur Quelltext. setup_api ersetzt enforce_uid_rate_limit; reale Key-/IP-Limitfälle sind vorhanden, aber kein UID-Reject durch main.app einschließlich Retry-After (G-037).

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
- [test_scheduler_deduplicates_and_bounds_pending_work](../../tests/test_consensus_api.py#L686) (Zeile 686)
- [test_expired_pre_provider_worker_releases_reserved_usage](../../tests/test_consensus_api.py#L708) (Zeile 708)
- [test_expired_post_provider_worker_keeps_consumed_usage](../../tests/test_consensus_api.py#L735) (Zeile 735)
- [test_api_key_can_publish_list_read_and_revoke_own_share](../../tests/test_consensus_api.py#L760) (Zeile 760)
- [test_admin_api_configures_weekly_watch_with_free_provider_tier](../../tests/test_consensus_api.py#L836) (Zeile 836)
- [test_publisher_watch_capacity_returns_successful_skip](../../tests/test_consensus_api.py#L904) (Zeile 904)
- [test_direct_indexing_requires_scope_admin_and_returns_indexed_state](../../tests/test_consensus_api.py#L937) (Zeile 937)

</details>

<a id="test-consensus-chat-history-py"></a>

## test_consensus_chat_history.py

**Quelle:** [tests/test_consensus_chat_history.py](../../tests/test_consensus_chat_history.py) · **Bereiche:** Bookmarks und Verlauf, Konsens und Unterschiede, Quellenprüfung.

**Ebene:** Router/SSE-Verträge mit RecordingStore und Engine-Doubles.

**Lauf:** 52 bestanden.

**Geprüftes Verhalten:** Kanonische Chat-/Turn-/Kontextbindung vor Engine, serverseitig aufgelöste Folgefrage, Completion-Provenienz/Quellen und Bookmark vor finalem Erfolg. Stream/JSON-Parität, Source-Job-Reihenfolge/disabled/skipped, Analysefehler bewahrt Konsens; Persistenzfehler erhält die Antwort und meldet chat_persisted=false/pending. Completed-Replay ohne Engine/Usage/Writes, Tier-/Own-Key-Gates und eindeutige terminale Fehler inkl. redigierter Logs. Aktualisierung 02.10.2026: Gespeicherte Modelllabels werden aus autoritativen Receipts gelesen.

**Grenzen und Doubles:** Store zeichnet Aufrufe auf; Engine und Job-Submission sind ersetzt. Persistenz-/Netzwerk-Atomizität wird hier nicht nachgewiesen; SSE wird über TestClient konsumiert.

**Prüfauftrag für den Folgeaudit:** Disconnect während Completion/Bookmark und echte Persistenzfehler mit Store-/Browsertests abgleichen.

**Direkte Codeverweise:** [app/api/routers/bookmarks.py](../../app/api/routers/bookmarks.py), [app/api/routers/chat.py](../../app/api/routers/chat.py), [app/core/rate_limit.py](../../app/core/rate_limit.py), [app/services/chat_store.py](../../app/services/chat_store.py), [app/services/consensus_pipeline.py](../../app/services/consensus_pipeline.py), [app/services/source_check_jobs.py](../../app/services/source_check_jobs.py), [app/services/source_verification.py](../../app/services/source_verification.py).

<details>
<summary>39 Testdefinitionen und ihre Quellstellen</summary>

- [test_source_verification_replays_from_completed_turn](../../tests/test_consensus_chat_history.py#L102) (Zeile 102)
- [test_durable_source_check_does_not_delay_consensus_completion](../../tests/test_consensus_chat_history.py#L143) (Zeile 143)
- [test_disabled_source_check_skips_third_judge_and_keeps_analysis](../../tests/test_consensus_chat_history.py#L175) (Zeile 175)
- [test_failed_differences_never_start_source_job](../../tests/test_consensus_chat_history.py#L200) (Zeile 200)
- [test_no_checkable_differences_skips_sources_without_job](../../tests/test_consensus_chat_history.py#L220) (Zeile 220)
- [test_consensus_without_chat_ids_remains_legacy_compatible](../../tests/test_consensus_chat_history.py#L235) (Zeile 235)
- [test_consensus_persists_requested_bookmark_before_successful_final_event](../../tests/test_consensus_chat_history.py#L251) (Zeile 251)
- [test_consensus_requires_chat_and_turn_ids_together](../../tests/test_consensus_chat_history.py#L323) (Zeile 323)
- [test_consensus_rejects_noncanonical_chat_ids](../../tests/test_consensus_chat_history.py#L339) (Zeile 339)
- [test_consensus_context_version_requires_ids_and_canonical_value](../../tests/test_consensus_chat_history.py#L350) (Zeile 350)
- [test_consensus_requires_exact_context_version_link_before_engine](../../tests/test_consensus_chat_history.py#L368) (Zeile 368)
- [test_consensus_accepts_exact_linked_context_version](../../tests/test_consensus_chat_history.py#L395) (Zeile 395)
- [test_resolved_follow_up_reading_reaches_consensus_and_judge](../../tests/test_consensus_chat_history.py#L410) (Zeile 410)
- [test_a_client_supplied_reading_is_ignored](../../tests/test_consensus_chat_history.py#L440) (Zeile 440)
- [test_a_single_turn_run_never_carries_a_resolved_reading](../../tests/test_consensus_chat_history.py#L465) (Zeile 465)
- [test_consensus_rejects_foreign_or_unknown_turn_before_engine](../../tests/test_consensus_chat_history.py#L484) (Zeile 484)
- [test_consensus_rejects_question_mismatch_before_engine](../../tests/test_consensus_chat_history.py#L504) (Zeile 504)
- [test_non_streaming_completion_maps_answers_labels_sources_and_result](../../tests/test_consensus_chat_history.py#L524) (Zeile 524)
- [test_excluded_and_empty_providers_are_not_completed](../../tests/test_consensus_chat_history.py#L568) (Zeile 568)
- [test_missing_turn_sources_falls_back_to_deduplicated_model_sources](../../tests/test_consensus_chat_history.py#L587) (Zeile 587)
- [test_streaming_success_completes_exactly_once](../../tests/test_consensus_chat_history.py#L605) (Zeile 605)
- [test_analysis_failure_keeps_the_answer_the_user_already_received](../../tests/test_consensus_chat_history.py#L632) (Zeile 632)
- [test_unexpected_consensus_stream_error_is_redacted_from_sse_and_logs](../../tests/test_consensus_chat_history.py#L674) (Zeile 674)
- [test_terminal_consensus_error_marks_pending_turn_failed_best_effort](../../tests/test_consensus_chat_history.py#L704) (Zeile 704)
- [test_server_side_insufficient_answers_fails_pending_turn](../../tests/test_consensus_chat_history.py#L736) (Zeile 736)
- [test_insufficient_answers_fail_before_own_key_or_engine_checks](../../tests/test_consensus_chat_history.py#L757) (Zeile 757)
- [test_insufficient_answers_disposition_precedes_current_model_and_tier_checks](../../tests/test_consensus_chat_history.py#L791) (Zeile 791)
- [test_completion_storage_failure_never_replaces_successful_consensus](../../tests/test_consensus_chat_history.py#L821) (Zeile 821)
- [test_completed_turn_replays_without_engine_writes_or_usage](../../tests/test_consensus_chat_history.py#L854) (Zeile 854)
- [test_completed_replay_precedes_current_model_tier_and_credentials](../../tests/test_consensus_chat_history.py#L921) (Zeile 921)
- [test_completed_turn_without_stored_consensus_fails_closed](../../tests/test_consensus_chat_history.py#L971) (Zeile 971)
- [test_correctable_missing_own_key_keeps_turn_retryable](../../tests/test_consensus_chat_history.py#L996) (Zeile 996)
- [test_premium_engine_stays_pro_only_even_with_own_keys](../../tests/test_consensus_chat_history.py#L1018) (Zeile 1018)
- [test_premium_engine_stays_pro_only_with_developer_keys](../../tests/test_consensus_chat_history.py#L1039) (Zeile 1039)
- [test_pro_user_may_use_a_premium_engine_with_own_keys](../../tests/test_consensus_chat_history.py#L1051) (Zeile 1051)
- [test_non_premium_engine_remains_available_to_free_users](../../tests/test_consensus_chat_history.py#L1066) (Zeile 1066)
- [test_empty_question_still_disposes_the_pending_turn](../../tests/test_consensus_chat_history.py#L1074) (Zeile 1074)
- [test_empty_question_with_too_few_answers_reports_insufficient_answers](../../tests/test_consensus_chat_history.py#L1090) (Zeile 1090)
- [test_empty_question_without_chat_ids_keeps_the_legacy_error](../../tests/test_consensus_chat_history.py#L1105) (Zeile 1105)

</details>

<a id="test-consensus-citations-py"></a>

## test_consensus_citations.py

**Quelle:** [tests/test_consensus_citations.py](../../tests/test_consensus_citations.py) · **Bereiche:** Quellenprüfung.

**Ebene:** Quote-/Markerparser plus Engine mit Transport-Doubles.

**Lauf:** 46 bestanden.

**Geprüftes Verhalten:** Unicode- und formattolerante Originalzitate/Anker bleiben korrekt; S-Markerfilter stimmt für vollständigen Text, Zeichenstream und alle Zweiteilungsgrenzen der Beispiele überein; Code/Mathe/Escapes bleiben erhalten; Teilmarker werden gepuffert; Query/Stream liefern identischen bereinigten Text; Quellen bleiben im Prompt; faktische Prüfbarkeit und Originalprovenienz separat, ungewisse Klassifikation fail-closed; Nichtprüfbarkeit entfernt weder Differences noch Claims. Aktualisierung 02.10.2026: Fuzzy Navigation gilt nicht als Zitatbeleg; harmlose Markdownvarianten dürfen passen, geänderte Zahlen nicht.

**Grenzen und Doubles:** Beispielmatrix testet alle Chunkgrenzen nur ihrer festgelegten Texte. Promptassertions belegen Anweisungen, kein Modellbefolgen. Der Kommentar über einen historischen Liveversuch gehört nicht zur automatisierten Ausführung.

**Prüfauftrag für den Folgeaudit:** Weitere Markdown-/Unicodekombinationen und sehr lange unvollständige Marker im späteren Scan prüfen.

**Direkte Codeverweise:** [app/services/llm/consensus_citations.py](../../app/services/llm/consensus_citations.py), [app/services/llm/consensus_engine.py](../../app/services/llm/consensus_engine.py).

<details>
<summary>17 Testdefinitionen und ihre Quellstellen</summary>

- [test_unicode_quote_offsets_preserve_original_spans](../../tests/test_consensus_citations.py#L20) (Zeile 20)
- [test_fuzzy_unicode_match_is_not_evidence](../../tests/test_consensus_citations.py#L25) (Zeile 25)
- [test_formatted_unicode_quote_offsets_preserve_original_span](../../tests/test_consensus_citations.py#L30) (Zeile 30)
- [test_unicode_differences_payload_keeps_verified_anchors_and_quotes](../../tests/test_consensus_citations.py#L35) (Zeile 35)
- [test_complete_and_every_chunk_boundary_agree](../../tests/test_consensus_citations.py#L71) (Zeile 71)
- [test_synthesis_keeps_source_information_but_prohibits_tags](../../tests/test_consensus_citations.py#L81) (Zeile 81)
- [test_differences_prompt_keeps_source_eligibility_separate_from_detection](../../tests/test_consensus_citations.py#L91) (Zeile 91)
- [test_model_quote_matching_accepts_only_formatting_omissions_and_keeps_original_span](../../tests/test_consensus_citations.py#L106) (Zeile 106)
- [test_formatted_quote_fallback_never_ignores_literal_code_or_math](../../tests/test_consensus_citations.py#L124) (Zeile 124)
- [test_real_original_position_span_survives_markdown_and_interleaved_citations](../../tests/test_consensus_citations.py#L128) (Zeile 128)
- [test_prose_streams_immediately_and_partial_markers_never_leak](../../tests/test_consensus_citations.py#L149) (Zeile 149)
- [test_query_and_stream_remove_tags_before_final_or_delta](../../tests/test_consensus_citations.py#L159) (Zeile 159)
- [test_checkability_and_original_quote_provenance_are_preserved](../../tests/test_consensus_citations.py#L190) (Zeile 190)
- [test_legacy_or_uncertain_classification_fails_closed](../../tests/test_consensus_citations.py#L201) (Zeile 201)
- [test_unmatched_anchor_cannot_be_marked_validated](../../tests/test_consensus_citations.py#L205) (Zeile 205)
- [test_source_check_eligibility_never_filters_differences_or_claims](../../tests/test_consensus_citations.py#L213) (Zeile 213)
- [test_dissent_quotes_tolerate_dropped_markdown_but_not_changed_numbers](../../tests/test_consensus_citations.py#L252) (Zeile 252)

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

**Quelle:** [tests/test_consensus_progress_ui.py](../../tests/test_consensus_progress_ui.py) · **Bereiche:** Consensus, Frontend.

**Ebene:** Statische DOM-/CSS-/JS-Verträge.

**Lauf:** 18 bestanden.

**Geprüftes Verhalten:** Consensusfortschritt, Footer- und Drawerstruktur einschließlich Archivturns. Klassenmitgliedschaft ersetzt veralteten exakten String; dynamisches Zielturn-/ARIA-Verhalten separat im DOMtest.

**Grenzen und Doubles:** Quelltextpräsenz allein beweist weder Layout noch Klick-/Fokuswirkung.

**Prüfauftrag für den Folgeaudit:** Die benannten Betriebs- und Testgrenzen bei künftigen Änderungen erneut prüfen; konkrete Paketnachweise stehen im Produktabgleich.

**Direkte Codeverweise:** [app/api/routers/chat.py](../../app/api/routers/chat.py), [static/css/components-consensus.css](../../static/css/components-consensus.css), [static/css/components-feedback.css](../../static/css/components-feedback.css), [static/css/shell.css](../../static/css/shell.css), [static/demo.js](../../static/demo.js), [static/js/app-core.js](../../static/js/app-core.js), [static/js/app-init.js](../../static/js/app-init.js), [static/js/consensus-insights.js](../../static/js/consensus-insights.js), [static/js/consensus-lifecycle.js](../../static/js/consensus-lifecycle.js), [static/js/consensus-progress.js](../../static/js/consensus-progress.js), [static/js/consensus-run.js](../../static/js/consensus-run.js), [static/js/query-send.js](../../static/js/query-send.js), [static/js/run-view.js](../../static/js/run-view.js), [templates/index.html](../../templates/index.html).

**Direkte Testhelfer:** [tests/frontend_order.py](../../tests/frontend_order.py).

<details>
<summary>18 Testdefinitionen und ihre Quellstellen</summary>

- [test_consensus_result_precedes_model_answers_and_run_block_is_loaded](../../tests/test_consensus_progress_ui.py#L12) (Zeile 12)
- [test_run_block_shows_one_step_at_a_time](../../tests/test_consensus_progress_ui.py#L24) (Zeile 24)
- [test_the_direct_comparison_has_no_run_block_at_all](../../tests/test_consensus_progress_ui.py#L42) (Zeile 42)
- [test_the_per_model_rows_show_live_progress_and_measured_time](../../tests/test_consensus_progress_ui.py#L68) (Zeile 68)
- [test_run_covers_every_phase_and_terminal_state](../../tests/test_consensus_progress_ui.py#L82) (Zeile 82)
- [test_completed_consensus_survives_differences_or_transport_failure](../../tests/test_consensus_progress_ui.py#L108) (Zeile 108)
- [test_run_is_compact_and_unknowable_phases_stay_indeterminate](../../tests/test_consensus_progress_ui.py#L118) (Zeile 118)
- [test_run_hands_over_to_a_provenance_line](../../tests/test_consensus_progress_ui.py#L132) (Zeile 132)
- [test_result_footer_has_one_boundary_before_the_composer](../../tests/test_consensus_progress_ui.py#L144) (Zeile 144)
- [test_the_composer_carries_no_followup_affordance_at_all](../../tests/test_consensus_progress_ui.py#L153) (Zeile 153)
- [test_followup_archives_the_previous_turn_before_rendering_the_next_one](../../tests/test_consensus_progress_ui.py#L177) (Zeile 177)
- [test_the_sent_message_leaves_the_field_before_prepare_runs](../../tests/test_consensus_progress_ui.py#L219) (Zeile 219)
- [test_a_run_that_never_happens_gives_the_message_back](../../tests/test_consensus_progress_ui.py#L273) (Zeile 273)
- [test_archived_questions_clamp_like_the_active_one](../../tests/test_consensus_progress_ui.py#L300) (Zeile 300)
- [test_archived_turns_use_the_same_drawer_row_as_the_live_answer](../../tests/test_consensus_progress_ui.py#L326) (Zeile 326)
- [test_composer_row_is_reduced_to_attach_run_switch_and_send](../../tests/test_consensus_progress_ui.py#L357) (Zeile 357)
- [test_sidebar_header_groups_brand_and_toggle_before_new_comparison](../../tests/test_consensus_progress_ui.py#L377) (Zeile 377)
- [test_consensus_loader_matches_the_run_visual_language](../../tests/test_consensus_progress_ui.py#L392) (Zeile 392)

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

**Lauf:** 67 bestanden.

**Geprüftes Verhalten:** V4-Modus, Eligibility samt expliziter Exclusions, Version-/Run-/Positionsbindung, beide belegte Positionen, Quellenzuordnung und deduplizierter Fetch. Verwirft erfundene/unvollständige Evidenz, künstliche Textjoins, unzulässige Daten und falsche Provenienz; differenziert insufficient/unavailable/omitted. Globale URL-/Token-/Zeitbudgets, Legacy-V3 und begrenzte textfreie Validierungsdiagnostik. Aktualisierung 02.10.2026: Nicht exakt lokalisierte Zitate behalten beide sachlichen Positionen mit stance-Fallback; unbrauchbare Seiten sind explizite Ausschlüsse.

**Grenzen und Doubles:** Vorgegebene Dokumente und Judge-JSON; beweist formale Belegtreue, keine tatsächliche Wahrheit oder semantische Zuverlässigkeit des LLM. Zeitbudget teils künstliche Uhr.

**Prüfauftrag für den Folgeaudit:** Adversariale reale Dokument-Fixtures, Datums-/Scope-Semantik und Retrieval-Ausfälle mit source_documents-Tests abgleichen.

**Direkte Codeverweise:** [app/services/contradiction_verification.py](../../app/services/contradiction_verification.py), [app/services/source_verification.py](../../app/services/source_verification.py).

<details>
<summary>31 Testdefinitionen und ihre Quellstellen</summary>

- [test_separate_mode_has_no_consensus_citations_and_preserves_inputs](../../tests/test_contradiction_verification.py#L53) (Zeile 53)
- [test_ineligible_differences_never_schedule](../../tests/test_contradiction_verification.py#L70) (Zeile 70)
- [test_unmatched_quote_keeps_both_sides_and_locates_by_stance](../../tests/test_contradiction_verification.py#L79) (Zeile 79)
- [test_stance_located_side_is_checked_end_to_end](../../tests/test_contradiction_verification.py#L96) (Zeile 96)
- [test_side_without_stance_or_answering_model_never_drops_into_judge](../../tests/test_contradiction_verification.py#L111) (Zeile 111)
- [test_unusable_sides_are_explicit_exclusions_not_absent_contradictions](../../tests/test_contradiction_verification.py#L117) (Zeile 117)
- [test_mixed_checks_keep_excluded_dispute_and_all_exclusion_causes](../../tests/test_contradiction_verification.py#L135) (Zeile 135)
- [test_identity_binds_run_answer_positions_and_question](../../tests/test_contradiction_verification.py#L151) (Zeile 151)
- [test_direct_references_select_both_sides_and_ignore_unrelated_catalog](../../tests/test_contradiction_verification.py#L163) (Zeile 163)
- [test_reference_from_next_sentence_is_not_borrowed](../../tests/test_contradiction_verification.py#L172) (Zeile 172)
- [test_shared_url_fetched_once_preserves_both_passages](../../tests/test_contradiction_verification.py#L178) (Zeile 178)
- [test_original_evidence_validation_rejects_invented_or_incomplete_verdicts](../../tests/test_contradiction_verification.py#L208) (Zeile 208)
- [test_missing_evidence_can_only_be_insufficient_not_refutation](../../tests/test_contradiction_verification.py#L228) (Zeile 228)
- [test_fetch_errors_never_call_judge_or_refute](../../tests/test_contradiction_verification.py#L238) (Zeile 238)
- [test_global_contradiction_budget_records_omissions](../../tests/test_contradiction_verification.py#L248) (Zeile 248)
- [test_url_budget_never_picks_only_one_side](../../tests/test_contradiction_verification.py#L258) (Zeile 258)
- [test_input_token_budget_is_global_and_explicit](../../tests/test_contradiction_verification.py#L264) (Zeile 264)
- [test_runtime_budget_omits_unfinished_check](../../tests/test_contradiction_verification.py#L271) (Zeile 271)
- [test_merge_rejects_run_and_position_tampering](../../tests/test_contradiction_verification.py#L282) (Zeile 282)
- [test_legacy_citation_mode_keeps_schema_three](../../tests/test_contradiction_verification.py#L295) (Zeile 295)
- [test_large_v4_reference_preserves_mode_run_and_scope](../../tests/test_contradiction_verification.py#L301) (Zeile 301)
- [test_direct_background_start_uses_disputes_without_citations](../../tests/test_contradiction_verification.py#L312) (Zeile 312)
- [test_failed_background_start_keeps_v4_mode](../../tests/test_contradiction_verification.py#L321) (Zeile 321)
- [test_one_side_retrieval_failure_does_not_promote_surviving_side](../../tests/test_contradiction_verification.py#L329) (Zeile 329)
- [test_invented_applicability_date_is_rejected](../../tests/test_contradiction_verification.py#L345) (Zeile 345)
- [test_passage_selection_never_validates_an_artificial_join](../../tests/test_contradiction_verification.py#L354) (Zeile 354)
- [test_only_sources_for_metadata_within_budget_are_fetched](../../tests/test_contradiction_verification.py#L367) (Zeile 367)
- [test_every_rejection_has_precise_bounded_text_free_diagnostics](../../tests/test_contradiction_verification.py#L409) (Zeile 409)
- [test_multiple_bad_quotes_are_all_rejected_and_diagnostics_are_bounded](../../tests/test_contradiction_verification.py#L484) (Zeile 484)
- [test_cosmetic_quotes_still_validate_without_diagnostics](../../tests/test_contradiction_verification.py#L494) (Zeile 494)
- [test_unknown_extra_finding_does_not_spoil_complete_valid_results](../../tests/test_contradiction_verification.py#L505) (Zeile 505)

</details>

<a id="test-coverage-judge-py"></a>

## test_coverage_judge.py

**Quelle:** [tests/test_coverage_judge.py](../../tests/test_coverage_judge.py) · **Bereiche:** Konsens und Unterschiede.

**Ebene:** Schema-/Parser-/Scoring-Unit-Tests und Engine-Integration mit Mock-Antworten.

**Lauf:** 30 bestanden.

**Geprüftes Verhalten:** Striktes Satz-/Modell-Schema, konservative fehlende/unklare Stances, gebundene IDs und genau ein gezielter Repair-Aufruf, sichtbare thin-Lücken, exakte Konsensanker und Dissent-Zitate. Thin-Claims senken Abdeckung/Score, günstige unabhängige Judge-Familie, Cooldown-Fallback sowie getrennte Judge-Metadaten und angepasster Credibility-Text. Aktualisierung 02.10.2026: Lange Antworten werden in parallele Satzfenster geteilt; ein fehlgeschlagenes Fenster lässt nur seine Sätze ungeprüft, Consensus behält Satzindizes.

**Grenzen und Doubles:** Hier meint Coverage die inhaltliche Satzabdeckung der App, keine Test-Code-Coverage. LLM-Antworten sind konstruiert; Klassifikationsqualität wird nicht gemessen.

**Prüfauftrag für den Folgeaudit:** Goldstandard für Satz-/Stance-Zuordnung, Tokenabschneiden und Mehrsprachigkeit gesondert prüfen.

**Direkte Codeverweise:** [app/core/config.py](../../app/core/config.py), [app/services/agent_provider_limits.py](../../app/services/agent_provider_limits.py), [app/services/llm/consensus_engine.py](../../app/services/llm/consensus_engine.py), [app/services/llm/consensus_scoring.py](../../app/services/llm/consensus_scoring.py), [app/services/llm/coverage_judge.py](../../app/services/llm/coverage_judge.py).

<details>
<summary>30 Testdefinitionen und ihre Quellstellen</summary>

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
- [CoverageWindowTests::test_long_answer_is_covered_in_parallel_windows](../../tests/test_coverage_judge.py#L452) (Zeile 452)
- [CoverageWindowTests::test_a_failed_window_leaves_only_its_sentences_unchecked](../../tests/test_coverage_judge.py#L478) (Zeile 478)
- [CoverageWindowTests::test_consensus_runs_keep_their_sentence_index](../../tests/test_coverage_judge.py#L495) (Zeile 495)

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

**Quelle:** [tests/test_dev_cli.py](../../tests/test_dev_cli.py) · **Bereiche:** Betrieb, Frontend-Build.

**Ebene:** Windows-PowerShell-/pwsh-Subprozesse mit instrumentierten Runnern.

**Lauf:** 28 bestanden.

**Geprüftes Verhalten:** Backend-, Frontend-, Browser-/Emulator-, Rules- und Buildauswahl, Fehlercodes, Argumente, Arbeitsverzeichnis und vollständige Envwiederherstellung einschließlich UTF-8. Tatsächliche Shellverfügbarkeit bestimmt die expandierte Fallzahl.

**Grenzen und Doubles:** Runnerinstrumentierung prüft Orchestrierung; reale Python/JS/Emulatorausführung ist zusätzlich im integrierten Lauf dokumentiert.

**Prüfauftrag für den Folgeaudit:** Die benannten Betriebs- und Testgrenzen bei künftigen Änderungen erneut prüfen; konkrete Paketnachweise stehen im Produktabgleich.

**Direkte Codeverweise:** [app/core/e2e_profile.py](../../app/core/e2e_profile.py), [app/services/agent_tokens.py](../../app/services/agent_tokens.py), [dev.ps1](../../dev.ps1), [firebase.json](../../firebase.json), [firestore.rules](../../firestore.rules), [package.json](../../package.json).

<details>
<summary>9 Testdefinitionen und ihre Quellstellen</summary>

- [test_frontend_runs_tests_then_build_check_from_repository_root](../../tests/test_dev_cli.py#L153) (Zeile 153)
- [test_frontend_preserves_failure_and_stops](../../tests/test_dev_cli.py#L164) (Zeile 164)
- [test_backend_isolates_inherited_e2e_flags_and_restores_caller](../../tests/test_dev_cli.py#L173) (Zeile 173)
- [test_browser_delegates_lifecycle_and_failure_to_firebase](../../tests/test_dev_cli.py#L185) (Zeile 185)
- [test_rules_uses_client_runner_with_emulator_lifecycle_and_restores_environment](../../tests/test_dev_cli.py#L208) (Zeile 208)
- [test_browser_rejects_nonlocal_emulator_before_start](../../tests/test_dev_cli.py#L219) (Zeile 219)
- [test_browser_failure_restores_initially_absent_environment_entries](../../tests/test_dev_cli.py#L229) (Zeile 229)
- [test_rejects_tests_outside_selected_suite](../../tests/test_dev_cli.py#L237) (Zeile 237)
- [test_missing_dependencies_have_actionable_error](../../tests/test_dev_cli.py#L245) (Zeile 245)

</details>

<a id="test-differences-schema-py"></a>

## test_differences_schema.py

**Quelle:** [tests/test_differences_schema.py](../../tests/test_differences_schema.py) · **Bereiche:** Konsens und Unterschiede.

**Ebene:** Parser-/Scoring-/Prompt-Unit-Tests und Mock-Engine-Integration.

**Lauf:** 83 bestanden.

**Geprüftes Verhalten:** JSON/Fence/Truncation-Reparatur und konservative Shape-Ablehnung, anonymisierte Modelllabels, Dissent-Deduplizierung, Quote-/Anchor-Abgleich und Legacy-Text. Judge-Auswahl/Retry/Fallback/Metadaten/Schema, Score-Caps nach Modellanzahl und Contradictions. Satznummerierung berücksichtigt Abkürzungen/Zahlen, Quellen, Markdown/Listen/Tabellen/Code/Math, 80-Satz-Cap und gleiche sichtbare Vorkommen mit getrennten IDs. Aktualisierung 02.10.2026: Zitatbeleg verlangt vollständige normalisierte Deckung: Zahlen, Einheiten, Negation und Bedingung bleiben strikt; Typografie/Markdown sind toleriert. Ablehnungsgründe enthalten keinen Inhalt.

**Grenzen und Doubles:** Feste Beispiele und gemockte LLM-Antworten; kein Qualitätsbenchmark. Nicht auffindbare Legacy-Claim-Anker bleiben bewusst für Fallback sichtbar, während falsche Difference-Anker geleert werden.

**Prüfauftrag für den Folgeaudit:** Property-/Fuzz-Fälle für Parser und mehrsprachige Segmentierung sowie semantische Quote-Zuordnung abgleichen.

**Direkte Codeverweise:** [app/core/config.py](../../app/core/config.py), [app/services/llm/consensus_engine.py](../../app/services/llm/consensus_engine.py), [app/services/llm/engines.py](../../app/services/llm/engines.py).

<details>
<summary>83 Testdefinitionen und ihre Quellstellen</summary>

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
- [QuoteVerificationTests::test_changed_number_unit_negation_or_condition_is_never_a_verified_quote](../../tests/test_differences_schema.py#L233) (Zeile 233)
- [QuoteVerificationTests::test_typographic_variants_of_a_full_quote_stay_verified](../../tests/test_differences_schema.py#L248) (Zeile 248)
- [QuoteVerificationTests::test_harmless_formatting_keeps_a_full_quote_verified](../../tests/test_differences_schema.py#L254) (Zeile 254)
- [QuoteVerificationTests::test_formatting_tolerance_keeps_words_and_identifiers_strict](../../tests/test_differences_schema.py#L274) (Zeile 274)
- [QuoteVerificationTests::test_rejected_quote_records_a_content_free_reason](../../tests/test_differences_schema.py#L283) (Zeile 283)
- [QuoteVerificationTests::test_fuzzy_consensus_anchor_navigates_but_is_not_validated](../../tests/test_differences_schema.py#L302) (Zeile 302)
- [QuoteVerificationTests::test_difference_consensus_anchor_is_verified_against_the_consensus](../../tests/test_differences_schema.py#L314) (Zeile 314)
- [QuoteVerificationTests::test_unfindable_difference_anchor_is_cleared](../../tests/test_differences_schema.py#L330) (Zeile 330)
- [QuoteVerificationTests::test_missing_difference_anchor_defaults_to_empty](../../tests/test_differences_schema.py#L342) (Zeile 342)
- [QuoteVerificationTests::test_unfindable_anchor_is_kept_for_fallback_box](../../tests/test_differences_schema.py#L350) (Zeile 350)
- [JudgePolicyTests::test_judge_family_differs_from_consensus_family](../../tests/test_differences_schema.py#L369) (Zeile 369)
- [JudgePolicyTests::test_pro_engine_gets_pro_judge_of_other_family](../../tests/test_differences_schema.py#L381) (Zeile 381)
- [JudgePolicyTests::test_missing_common_key_fails_open_to_own_standard_judge](../../tests/test_differences_schema.py#L392) (Zeile 392)
- [JudgePolicyTests::test_invalid_engine_returns_none](../../tests/test_differences_schema.py#L400) (Zeile 400)
- [JudgePolicyTests::test_attempts_are_primary_retry_fallback](../../tests/test_differences_schema.py#L404) (Zeile 404)
- [JudgePolicyTests::test_pro_attempts_fail_open_to_standard_judge](../../tests/test_differences_schema.py#L414) (Zeile 414)
- [JudgePolicyTests::test_attempts_without_any_cross_family_key](../../tests/test_differences_schema.py#L425) (Zeile 425)
- [JudgePolicyTests::test_differences_judge_uses_openrouter_json_schema](../../tests/test_differences_schema.py#L433) (Zeile 433)
- [JudgePolicyTests::test_differences_schema_is_strict_mode_compatible](../../tests/test_differences_schema.py#L454) (Zeile 454)
- [JudgePolicyTests::test_streaming_differences_judge_uses_same_json_schema](../../tests/test_differences_schema.py#L471) (Zeile 471)
- [JudgePolicyTests::test_one_openrouter_key_makes_every_judge_family_available](../../tests/test_differences_schema.py#L502) (Zeile 502)
- [JudgePolicyTests::test_mistral_judge_uses_supported_none_effort](../../tests/test_differences_schema.py#L506) (Zeile 506)
- [JudgePolicyTests::test_only_retryable_provider_errors_repeat_same_call](../../tests/test_differences_schema.py#L516) (Zeile 516)
- [JudgeMetadataTests::test_query_differences_reports_actual_judge](../../tests/test_differences_schema.py#L565) (Zeile 565)
- [JudgeMetadataTests::test_fallback_judge_is_reported](../../tests/test_differences_schema.py#L581) (Zeile 581)
- [JudgeMetadataTests::test_non_retryable_primary_error_skips_duplicate_call](../../tests/test_differences_schema.py#L595) (Zeile 595)
- [JudgeMetadataTests::test_stream_differences_reports_judge](../../tests/test_differences_schema.py#L614) (Zeile 614)
- [LegacyTextSynthesisTests::test_no_differences_is_very_credible](../../tests/test_differences_schema.py#L648) (Zeile 648)
- [LegacyTextSynthesisTests::test_nothing_measured_is_not_very_credible](../../tests/test_differences_schema.py#L658) (Zeile 658)
- [LegacyTextSynthesisTests::test_only_emphasis_is_largely_credible](../../tests/test_differences_schema.py#L668) (Zeile 668)
- [LegacyTextSynthesisTests::test_multiple_contradictions_are_hardly_credible](../../tests/test_differences_schema.py#L678) (Zeile 678)
- [AgreementScoreTests::test_clean_run_with_four_models_is_perfect](../../tests/test_differences_schema.py#L691) (Zeile 691)
- [AgreementScoreTests::test_two_models_cannot_reach_very](../../tests/test_differences_schema.py#L700) (Zeile 700)
- [AgreementScoreTests::test_minor_contradiction_hurts_less_than_major](../../tests/test_differences_schema.py#L709) (Zeile 709)
- [AgreementScoreTests::test_severity_minor_is_parsed_from_payload](../../tests/test_differences_schema.py#L731) (Zeile 731)
- [AgreementScoreTests::test_emphasis_has_no_severity](../../tests/test_differences_schema.py#L742) (Zeile 742)
- [DifferencesPromptTests::test_prompt_requests_json_and_anonymizes](../../tests/test_differences_schema.py#L751) (Zeile 751)
- [DifferencesPromptTests::test_follow_up_reading_reaches_the_judge_without_touching_single_runs](../../tests/test_differences_schema.py#L777) (Zeile 777)
- [DifferencesPromptTests::test_differences_judge_no_longer_asks_for_the_claim_list](../../tests/test_differences_schema.py#L801) (Zeile 801)
- [DifferencesPromptTests::test_long_consensus_is_numbered_sentence_by_sentence](../../tests/test_differences_schema.py#L821) (Zeile 821)
- [ConsensusSentenceSplitTests::test_plain_sentences_are_split](../../tests/test_differences_schema.py#L861) (Zeile 861)
- [ConsensusSentenceSplitTests::test_year_at_the_end_is_a_sentence_end](../../tests/test_differences_schema.py#L870) (Zeile 870)
- [ConsensusSentenceSplitTests::test_source_tag_neither_blocks_the_split_nor_enters_the_anchor](../../tests/test_differences_schema.py#L878) (Zeile 878)
- [ConsensusSentenceSplitTests::test_german_ordinal_dates_do_not_split](../../tests/test_differences_schema.py#L887) (Zeile 887)
- [ConsensusSentenceSplitTests::test_number_before_a_capitalized_sentence_still_splits](../../tests/test_differences_schema.py#L897) (Zeile 897)
- [ConsensusSentenceSplitTests::test_abbreviations_and_initials_do_not_split](../../tests/test_differences_schema.py#L903) (Zeile 903)
- [ConsensusSentenceSplitTests::test_currency_abbreviations_do_not_break_markdown_claims](../../tests/test_differences_schema.py#L909) (Zeile 909)
- [ConsensusSentenceSplitTests::test_quantity_abbreviation_can_still_end_a_sentence](../../tests/test_differences_schema.py#L925) (Zeile 925)
- [ConsensusSentenceSplitTests::test_display_math_blocks_are_not_numbered](../../tests/test_differences_schema.py#L935) (Zeile 935)
- [ConsensusSentenceSplitTests::test_single_line_display_math_does_not_swallow_the_next_paragraph](../../tests/test_differences_schema.py#L957) (Zeile 957)
- [ConsensusSentenceSplitTests::test_inline_math_stays_part_of_its_sentence](../../tests/test_differences_schema.py#L972) (Zeile 972)
- [ConsensusSentenceSplitTests::test_headings_table_headers_and_code_are_not_numbered](../../tests/test_differences_schema.py#L982) (Zeile 982)
- [ConsensusSentenceSplitTests::test_list_counter_stays_out_of_the_anchor](../../tests/test_differences_schema.py#L995) (Zeile 995)
- [ConsensusSentenceSplitTests::test_table_cells_include_short_values_and_preserve_context](../../tests/test_differences_schema.py#L1005) (Zeile 1005)
- [ConsensusSentenceSplitTests::test_table_without_outer_pipes_and_escaped_pipe](../../tests/test_differences_schema.py#L1019) (Zeile 1019)
- [ConsensusSentenceSplitTests::test_table_inside_code_is_not_numbered](../../tests/test_differences_schema.py#L1026) (Zeile 1026)
- [ConsensusSentenceSplitTests::test_sentence_count_is_capped](../../tests/test_differences_schema.py#L1032) (Zeile 1032)
- [ConsensusSentenceSplitTests::test_empty_answer_yields_no_sentences](../../tests/test_differences_schema.py#L1037) (Zeile 1037)
- [SentenceAnchorTests::test_sentence_numbers_resolve_to_the_exact_sentence](../../tests/test_differences_schema.py#L1063) (Zeile 1063)
- [SentenceAnchorTests::test_unknown_sentence_number_is_ignored](../../tests/test_differences_schema.py#L1074) (Zeile 1074)
- [SentenceAnchorTests::test_zero_means_the_consensus_does_not_state_it](../../tests/test_differences_schema.py#L1090) (Zeile 1090)
- [SentenceAnchorTests::test_verbatim_anchor_still_works_for_older_payloads](../../tests/test_differences_schema.py#L1099) (Zeile 1099)
- [SentenceAnchorTests::test_duplicate_sentence_keeps_the_more_conservative_claim](../../tests/test_differences_schema.py#L1107) (Zeile 1107)
- [SentenceAnchorTests::test_identical_sentence_occurrences_keep_distinct_ids](../../tests/test_differences_schema.py#L1122) (Zeile 1122)
- [SentenceAnchorTests::test_visibly_identical_sentences_ignore_citations_and_markdown](../../tests/test_differences_schema.py#L1140) (Zeile 1140)
- [ClaimSupportThresholdTests::test_single_voice_claim_is_dropped](../../tests/test_differences_schema.py#L1167) (Zeile 1167)
- [ClaimSupportThresholdTests::test_two_voices_are_kept](../../tests/test_differences_schema.py#L1175) (Zeile 1175)
- [ClaimSupportThresholdTests::test_single_dissent_alone_is_dropped](../../tests/test_differences_schema.py#L1181) (Zeile 1181)
- [ClaimSupportThresholdTests::test_duplicate_dissent_from_one_model_counts_once](../../tests/test_differences_schema.py#L1188) (Zeile 1188)

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

**Lauf:** 15 bestanden.

**Geprüftes Verhalten:** Änderungsursachen unterscheiden neue Belege, Wiederbewertung und Modellwechsel; bloße Scorebewegung ist kein fachlicher Wandel.

**Grenzen und Doubles:** Synthetische Scorefolgen/Judge-Grades; keine Messung der semantischen Change-Judge-Qualität.

**Prüfauftrag für den Folgeaudit:** Grenzwerte, fehlende Scores und lange/unregelmäßige Historien gegen Watch/Topic-Fixtures abgleichen.

**Direkte Codeverweise:** [app/services/drift_signal.py](../../app/services/drift_signal.py).

<details>
<summary>15 Testdefinitionen und ihre Quellstellen</summary>

- [test_the_gpt6_record_holds_the_release_instead_of_flip_flopping](../../tests/test_drift_signal.py#L26) (Zeile 26)
- [test_a_reassessment_waits_for_the_recheck_before_it_counts](../../tests/test_drift_signal.py#L44) (Zeile 44)
- [test_a_repeated_reassessment_is_movement_on_the_recheck](../../tests/test_drift_signal.py#L51) (Zeile 51)
- [test_a_reassessment_the_recheck_does_not_repeat_is_reverted](../../tests/test_drift_signal.py#L65) (Zeile 65)
- [test_a_recheck_that_only_misses_evidence_does_not_confirm](../../tests/test_drift_signal.py#L71) (Zeile 71)
- [test_new_evidence_confirms_a_pending_reassessment](../../tests/test_drift_signal.py#L77) (Zeile 77)
- [test_a_major_grade_without_a_cause_is_treated_as_a_reassessment](../../tests/test_drift_signal.py#L83) (Zeile 83)
- [test_the_score_alone_no_longer_raises_an_event](../../tests/test_drift_signal.py#L88) (Zeile 88)
- [test_classify_latest_reads_the_new_check_in_the_context_of_its_history](../../tests/test_drift_signal.py#L97) (Zeile 97)
- [test_legacy_minor_grade_is_a_restatement_not_a_change](../../tests/test_drift_signal.py#L113) (Zeile 113)
- [test_legacy_score_leaving_the_band_is_still_movement](../../tests/test_drift_signal.py#L118) (Zeile 118)
- [test_legacy_score_swinging_between_two_cap_steps_reports_the_first_step_only](../../tests/test_drift_signal.py#L124) (Zeile 124)
- [test_a_stored_trigger_from_the_looser_rule_is_recomputed_not_trusted](../../tests/test_drift_signal.py#L132) (Zeile 132)
- [test_the_first_check_has_no_band_and_no_predecessor](../../tests/test_drift_signal.py#L145) (Zeile 145)
- [test_steady_checks_counts_back_to_the_last_material_check](../../tests/test_drift_signal.py#L153) (Zeile 153)

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

<a id="test-feedback-py"></a>

## test_feedback.py

**Quelle:** [tests/test_feedback.py](../../tests/test_feedback.py) · **Bereiche:** Feedback, Statistiken.

**Ebene:** Registrierte main.app mit echten Middleware-, Auth-/Owner- und Serviceguards.

**Lauf:** 8 bestanden.

**Geprüftes Verhalten:** Feedback prüft UID, Allowlist, persistierten Cooldown trotz lokalem Limiterreset, Tageslimit und Storefehler. Statistik schreibt Zähler/Modellmetadaten ohne Frage, Antwort, UID oder Run-ID; Fehler bleiben nichtfatal.

**Grenzen und Doubles:** Firebase-SDK-Authentifizierung und DB ersetzt; externe Modell-, Mail- und Telegramgrenzen kontrolliert. Kein Live-OAuth oder produktiver Versand. Absichtlich eingegebene Feedbacknachricht darf gespeichert werden.

**Prüfauftrag für den Folgeaudit:** Die benannten Betriebs- und Testgrenzen bei künftigen Änderungen erneut prüfen; konkrete Paketnachweise stehen im Produktabgleich.

**Direkte Codeverweise:** [app/api/routers/pages.py](../../app/api/routers/pages.py), [app/core/rate_limit.py](../../app/core/rate_limit.py), [app/services/differences_stats.py](../../app/services/differences_stats.py), [app/services/persistence_guard.py](../../app/services/persistence_guard.py).

<details>
<summary>5 Testdefinitionen und ihre Quellstellen</summary>

- [test_feedback_auth_payload_and_persisted_cooldown](../../tests/test_feedback.py#L23) (Zeile 23)
- [test_feedback_daily_limit_and_storage_failure_are_safe](../../tests/test_feedback.py#L53) (Zeile 53)
- [test_feedback_rejects_invalid_fields_before_storage](../../tests/test_feedback.py#L93) (Zeile 93)
- [test_stats_wrapper_persists_only_counts_and_safe_model_metadata](../../tests/test_feedback.py#L102) (Zeile 102)
- [test_stats_failure_never_aborts_answer_or_logs_content](../../tests/test_feedback.py#L133) (Zeile 133)

</details>

<a id="test-firestore-read-contracts-py"></a>

## test_firestore_read_contracts.py

**Quelle:** [tests/test_firestore_read_contracts.py](../../tests/test_firestore_read_contracts.py) · **Bereiche:** Modellstatistik, Persistenz.

**Ebene:** Echter Firestore-SDK-Queryaufbau mit RPC-Mock.

**Lauf:** 2 bestanden.

**Geprüftes Verhalten:** Leaderboard liest Katalog einmal und neun Count-Aggregationen mit passendem deklarativem Index, Filter/IN-Grenzen/Zeitraum, Timeout und ohne Retry in einem Read-only-Snapshot; prüft leeres und nichtleeres Ergebnis.

**Grenzen und Doubles:** SDK serialisiert reale Protobufs; Backend-RPCs sind gemockt. Indexverfügbarkeit und Query-Ausführung im echten Dienst werden nicht bewiesen.

**Prüfauftrag für den Folgeaudit:** Emulator-/Deployment-Indexvalidierung und Skalierung der Provider-Aliase abgleichen.

**Direkte Codeverweise:** [app/api/routers/pages.py](../../app/api/routers/pages.py), [firestore.indexes.json](../../firestore.indexes.json).

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

**Direkte Codeverweise:** [app/core/assets.py](../../app/core/assets.py), [package.json](../../package.json), [scripts/build_frontend.mjs](../../scripts/build_frontend.mjs), [scripts/frontend-output.mjs](../../scripts/frontend-output.mjs), [templates/index.html](../../templates/index.html).

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

<a id="test-google-connections-py"></a>

## test_google_connections.py

**Quelle:** [tests/test_google_connections.py](../../tests/test_google_connections.py) · **Bereiche:** Google, Authentifizierung.

**Ebene:** OAuth-/Connectiondienste, signierte Testidentität und HTTP-Adapter.

**Lauf:** 15 bestanden.

**Geprüftes Verhalten:** PKCE, State-/Browser-/Ownerbindung, inkrementelle Scopes, verschlüsselte Credentials, Refresh/Widerruf/Disconnect-Races, Kontolöschung, Quoten und Logredaktion. Google-Daten pinnen erlaubte Modelle/Hosts einschließlich Vergleich, Synthese und Judges; Free-Nutzer dürfen trennen, aber nicht verbinden.

**Grenzen und Doubles:** Signierte lokale Tokens und Transport-/DB-/Auth-Doubles; kein Live-OAuth und keine Überprüfung der Google-Konfiguration im Deployment.

**Prüfauftrag für den Folgeaudit:** Die benannten Mock-/Integrationsgrenzen am realen Adapter prüfen; Zuordnung und offene Aufgaben stehen in der Produktmatrix.

**Direkte Codeverweise:** [app/api/routers/agent_google.py](../../app/api/routers/agent_google.py), [app/core/observability.py](../../app/core/observability.py), [app/core/rate_limit.py](../../app/core/rate_limit.py), [app/services/account_deletion.py](../../app/services/account_deletion.py), [app/services/agent_runs.py](../../app/services/agent_runs.py), [app/services/google_connections.py](../../app/services/google_connections.py), [app/services/llm/agent_client.py](../../app/services/llm/agent_client.py), [app/services/persistence_guard.py](../../app/services/persistence_guard.py).

<details>
<summary>15 Testdefinitionen und ihre Quellstellen</summary>

- [test_oauth_state_pkce_browser_owner_and_incremental_scopes](../../tests/test_google_connections.py#L35) (Zeile 35)
- [test_refresh_preserves_refresh_token_and_hides_credentials](../../tests/test_google_connections.py#L55) (Zeile 55)
- [test_revoked_refresh_and_api_credentials_require_reauthorization](../../tests/test_google_connections.py#L68) (Zeile 68)
- [test_disconnect_during_refresh_never_restores_access](../../tests/test_google_connections.py#L79) (Zeile 79)
- [test_disconnect_invalidates_pending_oauth_and_account_fence](../../tests/test_google_connections.py#L89) (Zeile 89)
- [test_real_signed_identity_rejects_wrong_nonce_and_audience](../../tests/test_google_connections.py#L103) (Zeile 103)
- [test_api_daily_quota_and_oauth_access_log_redaction](../../tests/test_google_connections.py#L120) (Zeile 120)
- [test_model_routing_fails_closed_and_pins_approved_hosting](../../tests/test_google_connections.py#L133) (Zeile 133)
- [test_google_routing_reaches_comparison_synthesis_and_judges](../../tests/test_google_connections.py#L144) (Zeile 144)
- [test_api_401_keeps_sealed_grant_so_disconnect_can_revoke](../../tests/test_google_connections.py#L169) (Zeile 169)
- [test_account_deletion_revokes_google_grants_before_deleting_them](../../tests/test_google_connections.py#L182) (Zeile 182)
- [test_chat_deletion_removes_proposed_actions](../../tests/test_google_connections.py#L193) (Zeile 193)
- [test_non_agent_users_can_list_and_disconnect_but_not_connect](../../tests/test_google_connections.py#L201) (Zeile 201)
- [test_failed_finish_still_clears_the_oauth_cookie](../../tests/test_google_connections.py#L221) (Zeile 221)
- [test_httpx_request_urls_are_not_logged_at_info](../../tests/test_google_connections.py#L238) (Zeile 238)

</details>

<a id="test-http-adapter-auth-py"></a>

## test_http_adapter_auth.py

**Quelle:** [tests/test_http_adapter_auth.py](../../tests/test_http_adapter_auth.py) · **Bereiche:** Authentifizierung, Topics, Admin, Benchmark.

**Ebene:** Registrierte main.app mit echten Middleware-, Auth-/Owner- und Serviceguards.

**Lauf:** 38 bestanden.

**Geprüftes Verhalten:** Registrierung liefert neutral dieselbe Antwort bei neu/bestehend/Lookup-Create-Race und benachrichtigt einmal. user_status führt die echte Free-/Plus-/Pro-/Adminmatrix aus. Alle Topicadminmethoden prüfen widerrufene Tokens und Tierausfall; Benchmarkliste/-detail lehnen Nichtadmin vor Reportread ab, liefern nur kompakte Reports und korrekte 404.

**Grenzen und Doubles:** Firebase-SDK-Authentifizierung und DB ersetzt; externe Modell-, Mail- und Telegramgrenzen kontrolliert. Kein Live-OAuth oder produktiver Versand.

**Prüfauftrag für den Folgeaudit:** Die benannten Betriebs- und Testgrenzen bei künftigen Änderungen erneut prüfen; konkrete Paketnachweise stehen im Produktabgleich.

**Direkte Codeverweise:** [app/api/routers/auth.py](../../app/api/routers/auth.py), [app/api/routers/users.py](../../app/api/routers/users.py), [app/services/benchmark_reports.py](../../app/services/benchmark_reports.py), [app/services/registration.py](../../app/services/registration.py), [app/services/topics.py](../../app/services/topics.py), [app/services/usage_repository.py](../../app/services/usage_repository.py), [benchmark/report_reader.py](../../benchmark/report_reader.py).

<details>
<summary>7 Testdefinitionen und ihre Quellstellen</summary>

- [test_every_topic_admin_method_enforces_real_policy_before_service](../../tests/test_http_adapter_auth.py#L29) (Zeile 29)
- [test_real_topic_admin_put_list_and_version_have_persisted_results](../../tests/test_http_adapter_auth.py#L50) (Zeile 50)
- [test_user_status_uses_real_tier_and_role_payload](../../tests/test_http_adapter_auth.py#L90) (Zeile 90)
- [test_user_status_rejects_auth_and_tier_outage](../../tests/test_http_adapter_auth.py#L112) (Zeile 112)
- [test_registration_create_race_has_same_public_response_and_no_duplicate_notification](../../tests/test_http_adapter_auth.py#L120) (Zeile 120)
- [test_benchmark_admin_denies_before_read](../../tests/test_http_adapter_auth.py#L159) (Zeile 159)
- [test_benchmark_admin_reads_compact_report_and_handles_missing_ids](../../tests/test_http_adapter_auth.py#L172) (Zeile 172)

</details>

<a id="test-local-transport-py"></a>

## test_local_transport.py

**Quelle:** [tests/test_local_transport.py](../../tests/test_local_transport.py) · **Bereiche:** Provider, Quellen, Betrieb.

**Ebene:** Echte lokale TCP-/TLS-Server durch HTTP-/SDK-Adapter.

**Lauf:** 10 bestanden.

**Geprüftes Verhalten:** Abbruch vor Headern und im SSE-Body schließt echte Sockets; SDK-Deadline und 503 verursachen keinen zweiten Request. Host/SNI bleiben korrekt, Redirect wird neu validiert, gzip-Ausgabe begrenzt. Aktivierte SDK-Retries werden über zwei Serverrequests erkannt.

**Grenzen und Doubles:** Ausschließlich Loopbackserver und eigene Zertifikate; Zielpinning wird für den Testserver ersetzt, echte Host-/Redirectpolicy separat geprüft. Keine Proxy-/CDN-/Internetmessung.

**Prüfauftrag für den Folgeaudit:** Die benannten Betriebs- und Testgrenzen bei künftigen Änderungen erneut prüfen; konkrete Paketnachweise stehen im Produktabgleich.

**Direkte Codeverweise:** [app/services/llm/provider_runtime.py](../../app/services/llm/provider_runtime.py), [app/services/source_documents.py](../../app/services/source_documents.py).

<details>
<summary>6 Testdefinitionen und ihre Quellstellen</summary>

- [test_cancellation_closes_real_idle_provider_socket_without_retry](../../tests/test_local_transport.py#L64) (Zeile 64)
- [test_sdk_read_deadline_closes_real_socket_and_does_not_retry](../../tests/test_local_transport.py#L97) (Zeile 97)
- [test_http_failure_has_one_attempt_and_oracle_detects_enabled_sdk_retry](../../tests/test_local_transport.py#L114) (Zeile 114)
- [test_source_tls_preserves_host_sni_redirect_and_bounds_gzip](../../tests/test_local_transport.py#L162) (Zeile 162)
- [test_source_revalidates_redirect_before_connecting_private_target](../../tests/test_local_transport.py#L178) (Zeile 178)
- [test_real_source_policy_keeps_loopback_and_credentials_forbidden](../../tests/test_local_transport.py#L189) (Zeile 189)

</details>

<a id="test-logging-redaction-contract-py"></a>

## test_logging_redaction_contract.py

**Quelle:** [tests/test_logging_redaction_contract.py](../../tests/test_logging_redaction_contract.py) · **Bereiche:** Datenschutz, Fehlerdiagnostik.

**Ebene:** AST-Vertrag und Runtime-Tests mit SMTP-/Notifier-Doubles.

**Lauf:** 8 bestanden.

**Geprüftes Verhalten:** AST-Scan verbietet rohe Exception-Logs; globaler Handler liefert generische 500-Meldung/Alert, safe_traceback enthält begrenzte lokale Koordinaten ohne Geheimnisse, safe_exception verwirft freie Errorcodes und Mailfehler redigieren Empfänger/Credentials/Providertext. Aktualisierung 02.10.2026: OAuth-/Google-Request- und weitere Fehlerpfade werden in die inhaltsfreie Logprüfung einbezogen.

**Grenzen und Doubles:** AST erkennt definierte Logging-Muster, keine vollständige Informationsflussanalyse. SMTP/Alertversand ersetzt; Runtime nur exemplarische Fehler.

**Prüfauftrag für den Folgeaudit:** Strukturierte/nicht standardisierte Logs und weitere Secret-Felder gegen produktive Sink-Pfade abgleichen.

**Direkte Codeverweise:** [app/core/observability.py](../../app/core/observability.py), [app/services/llm/engines.py](../../app/services/llm/engines.py), [app/services/llm/provider_runtime.py](../../app/services/llm/provider_runtime.py), [app/services/mailer.py](../../app/services/mailer.py), [main.py](../../main.py).

<details>
<summary>8 Testdefinitionen und ihre Quellstellen</summary>

- [test_runtime_never_emits_raw_exception_tracebacks_or_messages](../../tests/test_logging_redaction_contract.py#L64) (Zeile 64)
- [test_global_exception_handler_logs_and_alerts_only_safe_categories](../../tests/test_logging_redaction_contract.py#L102) (Zeile 102)
- [test_safe_traceback_reports_where_not_what](../../tests/test_logging_redaction_contract.py#L135) (Zeile 135)
- [test_safe_traceback_is_bounded_and_survives_a_bare_exception](../../tests/test_logging_redaction_contract.py#L161) (Zeile 161)
- [test_safe_exception_never_projects_arbitrary_string_error_codes](../../tests/test_logging_redaction_contract.py#L177) (Zeile 177)
- [test_mail_delivery_error_log_redacts_recipient_credentials_and_provider_body](../../tests/test_logging_redaction_contract.py#L185) (Zeile 185)
- [test_provider_diagnostic_classifies_upstream_errors_without_copying_text](../../tests/test_logging_redaction_contract.py#L229) (Zeile 229)
- [test_streaming_http_error_carries_diagnostic_but_no_body](../../tests/test_logging_redaction_contract.py#L254) (Zeile 254)

</details>

<a id="test-maintenance-scripts-py"></a>

## test_maintenance_scripts.py

**Quelle:** [tests/test_maintenance_scripts.py](../../tests/test_maintenance_scripts.py) · **Bereiche:** Wartung, Werkzeuge.

**Ebene:** Echte Entry-Points in isolierten Subprozessen.

**Lauf:** 13 bestanden.

**Geprüftes Verhalten:** Inspect/Dry-run ohne Writes, Projekt-/Apply-/Emulatorguards, gezielter Account und Idempotenz. Claim-Backfill bewahrt vorhandene Teilkeys und Reservierungen, verhindert Fallbackkollisionen und zählt Vorschauänderungen korrekt. Entfernte Applyguard wird entdeckt.

**Grenzen und Doubles:** SDK-, Judge- und Recoverygrenzen kontrolliert, Netzwerk gesperrt. Ein echter Backfill-Dry-run kann den kostenpflichtigen Judge aufrufen.

**Prüfauftrag für den Folgeaudit:** Die benannten Betriebs- und Testgrenzen bei künftigen Änderungen erneut prüfen; konkrete Paketnachweise stehen im Produktabgleich.

**Direkte Codeverweise:** [scripts/backfill_claim_keys.py](../../scripts/backfill_claim_keys.py), [scripts/repair_agent_allowance.py](../../scripts/repair_agent_allowance.py).

<details>
<summary>10 Testdefinitionen und ihre Quellstellen</summary>

- [test_repair_inspect_does_not_apply_but_selected_account_recovery_does](../../tests/test_maintenance_scripts.py#L114) (Zeile 114)
- [test_repair_refuses_test_or_emulator_before_lookup_or_write](../../tests/test_maintenance_scripts.py#L124) (Zeile 124)
- [test_repair_refuses_project_mismatch_before_account_lookup](../../tests/test_maintenance_scripts.py#L130) (Zeile 130)
- [test_repair_inspection_oracle_detects_removed_apply_guard](../../tests/test_maintenance_scripts.py#L136) (Zeile 136)
- [test_backfill_dry_run_counts_changes_without_writes_but_runs_judge](../../tests/test_maintenance_scripts.py#L154) (Zeile 154)
- [test_backfill_preserves_partial_keys_and_other_fields_and_is_idempotent](../../tests/test_maintenance_scripts.py#L163) (Zeile 163)
- [test_force_can_rekey_existing_dimensions_explicitly](../../tests/test_maintenance_scripts.py#L176) (Zeile 176)
- [test_backfill_reserves_retained_keys_and_avoids_fallback_collisions](../../tests/test_maintenance_scripts.py#L182) (Zeile 182)
- [test_force_assigns_valid_judge_keys_before_generating_fallbacks](../../tests/test_maintenance_scripts.py#L203) (Zeile 203)
- [test_backfill_requires_selection_and_refuses_fixture_identity_mode](../../tests/test_maintenance_scripts.py#L220) (Zeile 220)

</details>

<a id="test-memory-edit-py"></a>

## test_memory_edit.py

**Quelle:** [tests/test_memory_edit.py](../../tests/test_memory_edit.py) · **Bereiche:** Memory.

**Ebene:** Memory-Repository mit Transaktionsdouble.

**Lauf:** 22 bestanden.

**Geprüftes Verhalten:** Patch/Undo, Idempotenz, Quoten, Lease-Recovery und sichere Revisionen. Bei abgesenktem Notizlimit lehnen Patch und Undo den verlustbehafteten Vorzustand ab; sämtliche Profil-/Request-/Quotenwerte bleiben unverändert.

**Grenzen und Doubles:** DB-Double; nativer Wettbewerb und echter main-Fehlerumschlag sind separat belegt.

**Prüfauftrag für den Folgeaudit:** Die benannten Betriebs- und Testgrenzen bei künftigen Änderungen erneut prüfen; konkrete Paketnachweise stehen im Produktabgleich.

**Direkte Codeverweise:** [app/api/routers/users.py](../../app/api/routers/users.py), [app/core/config.py](../../app/core/config.py), [app/core/rate_limit.py](../../app/core/rate_limit.py), [app/services/memory_edit.py](../../app/services/memory_edit.py), [app/services/user_memory.py](../../app/services/user_memory.py).

<details>
<summary>21 Testdefinitionen und ihre Quellstellen</summary>

- [test_model_patch_schema_is_strict_and_passage_bounded](../../tests/test_memory_edit.py#L157) (Zeile 157)
- [test_replace_is_revision_checked_and_undo_restores_exact_content](../../tests/test_memory_edit.py#L178) (Zeile 178)
- [test_non_unique_target_is_never_overwritten](../../tests/test_memory_edit.py#L226) (Zeile 226)
- [test_lowered_limit_never_truncates_existing_memory](../../tests/test_memory_edit.py#L252) (Zeile 252)
- [test_same_client_request_never_calls_provider_twice](../../tests/test_memory_edit.py#L281) (Zeile 281)
- [test_remember_intent_appends_when_no_related_entry_exists](../../tests/test_memory_edit.py#L307) (Zeile 307)
- [test_remember_intent_replaces_one_unique_conflicting_passage](../../tests/test_memory_edit.py#L338) (Zeile 338)
- [test_remember_intent_rejects_delete_patch](../../tests/test_memory_edit.py#L365) (Zeile 365)
- [test_smallest_replace_preserves_unrelated_details](../../tests/test_memory_edit.py#L388) (Zeile 388)
- [test_persistent_daily_budget_is_shared_by_repository_instances](../../tests/test_memory_edit.py#L419) (Zeile 419)
- [test_over_plan_memory_is_not_truncated_or_charged_by_ai_edit](../../tests/test_memory_edit.py#L442) (Zeile 442)
- [test_invalid_admin_values_fall_back_to_safe_defaults](../../tests/test_memory_edit.py#L462) (Zeile 462)
- [test_provider_call_is_schema_bound_no_reasoning_and_output_capped](../../tests/test_memory_edit.py#L473) (Zeile 473)
- [test_one_in_flight_edit_and_global_budget_are_persistent](../../tests/test_memory_edit.py#L516) (Zeile 516)
- [test_edit_endpoint_applies_explicit_feedback_without_confirmation](../../tests/test_memory_edit.py#L549) (Zeile 549)
- [test_same_request_is_recovered_under_a_new_lease_after_a_crash](../../tests/test_memory_edit.py#L621) (Zeile 621)
- [test_a_second_crash_ends_the_request_as_interrupted](../../tests/test_memory_edit.py#L667) (Zeile 667)
- [test_crash_after_provider_answer_is_recovered_through_the_service](../../tests/test_memory_edit.py#L678) (Zeile 678)
- [test_retention_moves_abandoned_reservations_to_a_terminal_state](../../tests/test_memory_edit.py#L711) (Zeile 711)
- [test_interrupted_edit_endpoint_answers_with_a_retryable_409](../../tests/test_memory_edit.py#L732) (Zeile 732)
- [test_undo_snapshots_expire_after_thirty_days_but_idempotency_remains](../../tests/test_memory_edit.py#L764) (Zeile 764)

</details>

<a id="test-memory-http-contract-py"></a>

## test_memory_http_contract.py

**Quelle:** [tests/test_memory_http_contract.py](../../tests/test_memory_http_contract.py) · **Bereiche:** Memory, Authentifizierung.

**Ebene:** Registrierte main.app mit echten Middleware-, Auth-/Owner- und Serviceguards.

**Lauf:** 12 bestanden.

**Geprüftes Verhalten:** Echtes Undo durch main mit fehlendem/ungültigem Token, Tierausfall, fremder/fehlender/ungültiger Revision, Ablauf, Konflikt und Limitabsenkung: exakter Status/Body, vollständige Nichtmutation und kein Providercall. Vorher authentifizierter Edit/Undo bleibt hinter Tombstone gesperrt; erfolgreicher Repeat stellt jedes Profilfeld ohne neue Revision/Buchung wieder her.

**Grenzen und Doubles:** SDKidentität und Datenbankzugang ersetzt; Auth-/Tier-/Owner-/Revision-/Löschguards und main-Fehlerprojektion bleiben echt.

**Prüfauftrag für den Folgeaudit:** Die benannten Betriebs- und Testgrenzen bei künftigen Änderungen erneut prüfen; konkrete Paketnachweise stehen im Produktabgleich.

**Direkte Codeverweise:** [app/api/routers/users.py](../../app/api/routers/users.py), [app/core/config.py](../../app/core/config.py), [app/core/security.py](../../app/core/security.py), [app/services/memory_edit.py](../../app/services/memory_edit.py), [app/services/persistence_guard.py](../../app/services/persistence_guard.py), [app/services/user_memory.py](../../app/services/user_memory.py).

<details>
<summary>3 Testdefinitionen und ihre Quellstellen</summary>

- [test_main_undo_errors_preserve_all_state_and_never_call_provider](../../tests/test_memory_http_contract.py#L75) (Zeile 75)
- [test_main_previously_authenticated_memory_write_is_fenced_by_tombstone](../../tests/test_memory_http_contract.py#L120) (Zeile 120)
- [test_main_undo_retry_restores_every_profile_field_without_second_revision_or_charge](../../tests/test_memory_http_contract.py#L151) (Zeile 151)

</details>

<a id="test-model-configuration-py"></a>

## test_model_configuration.py

**Quelle:** [tests/test_model_configuration.py](../../tests/test_model_configuration.py) · **Bereiche:** Admin, Modelle.

**Ebene:** Modellkonfiguration mit Repository-/Aktivierungsdoubles und statischen UIverträgen.

**Lauf:** 31 bestanden.

**Geprüftes Verhalten:** Gespeicherte Regeln/Payloads, CAS-Revisionskonflikt, eigener Rollback und Übernahme neuer Revisionen; konkurrierender Write im Double bleibt erhalten, Runtimeaktivierungsfehler sind sichtbar. Native Writer-/Rollback-RPCfälle stehen separat im E2E-Katalog.

**Grenzen und Doubles:** Keine Liveverfügbarkeit/Akzeptanz der Modell-APIs; UIauszüge statisch und lokale DBkonkurrenz simuliert.

**Prüfauftrag für den Folgeaudit:** Die benannten Betriebs- und Testgrenzen bei künftigen Änderungen erneut prüfen; konkrete Paketnachweise stehen im Produktabgleich.

**Direkte Codeverweise:** [app/api/routers/admin.py](../../app/api/routers/admin.py), [app/api/routers/chat.py](../../app/api/routers/chat.py), [app/core/config.py](../../app/core/config.py), [app/services/llm/base.py](../../app/services/llm/base.py), [app/services/llm/citations.py](../../app/services/llm/citations.py), [app/services/llm/engines.py](../../app/services/llm/engines.py).

<details>
<summary>31 Testdefinitionen und ihre Quellstellen</summary>

- [ModelConfigurationTests::test_rejected_admin_document_cannot_mutate_runtime_limits](../../tests/test_model_configuration.py#L101) (Zeile 101)
- [ModelConfigurationTests::test_runtime_reload_rolls_back_all_mutations_on_activation_error](../../tests/test_model_configuration.py#L121) (Zeile 121)
- [ModelConfigurationTests::test_admin_update_restores_persisted_document_on_activation_error](../../tests/test_model_configuration.py#L147) (Zeile 147)
- [ModelConfigurationTests::test_failed_activation_never_rolls_back_a_newer_foreign_revision](../../tests/test_model_configuration.py#L172) (Zeile 172)
- [ModelConfigurationTests::test_stale_admin_save_is_refused_with_409_and_nothing_is_written](../../tests/test_model_configuration.py#L189) (Zeile 189)
- [ModelConfigurationTests::test_successful_save_increments_revision_and_get_exposes_it](../../tests/test_model_configuration.py#L203) (Zeile 203)
- [ModelConfigurationTests::test_every_process_adopts_a_newer_published_revision](../../tests/test_model_configuration.py#L216) (Zeile 216)
- [ModelConfigurationTests::test_readiness_config_load_never_creates_missing_document](../../tests/test_model_configuration.py#L231) (Zeile 231)
- [ModelConfigurationTests::test_engine_developer_keys_use_shared_credentials_source](../../tests/test_model_configuration.py#L245) (Zeile 245)
- [ModelConfigurationTests::test_engine_own_keys_are_stripped_and_never_use_developer_keys](../../tests/test_model_configuration.py#L255) (Zeile 255)
- [ModelConfigurationTests::test_admin_models_get_is_read_only_and_preserves_judge_family](../../tests/test_model_configuration.py#L268) (Zeile 268)
- [ModelConfigurationTests::test_removed_low_reasoning_aliases_are_not_runtime_models](../../tests/test_model_configuration.py#L323) (Zeile 323)
- [ModelConfigurationTests::test_missing_openrouter_legacy_ids_stay_removed](../../tests/test_model_configuration.py#L333) (Zeile 333)
- [ModelConfigurationTests::test_admin_drops_removed_aliases_everywhere](../../tests/test_model_configuration.py#L365) (Zeile 365)
- [ModelConfigurationTests::test_new_gemini_models_are_direct_and_temperature_free](../../tests/test_model_configuration.py#L383) (Zeile 383)
- [ModelConfigurationTests::test_web_search_budget_and_engine_per_family](../../tests/test_model_configuration.py#L401) (Zeile 401)
- [ModelConfigurationTests::test_deep_search_keeps_the_wider_search_budget](../../tests/test_model_configuration.py#L429) (Zeile 429)
- [ModelConfigurationTests::test_gemini_models_are_available_to_admin](../../tests/test_model_configuration.py#L436) (Zeile 436)
- [ModelConfigurationTests::test_admin_premium_is_limited_to_configured_provider_models](../../tests/test_model_configuration.py#L442) (Zeile 442)
- [ModelConfigurationTests::test_admin_dependencies_are_informative_not_server_enforced](../../tests/test_model_configuration.py#L462) (Zeile 462)
- [ModelConfigurationTests::test_retired_grok_aliases_are_canonicalized](../../tests/test_model_configuration.py#L477) (Zeile 477)
- [ModelConfigurationTests::test_grok_no_reasoning_and_high_reasoning_payloads](../../tests/test_model_configuration.py#L486) (Zeile 486)
- [ModelConfigurationTests::test_muse_reasoning_is_pinned_low_because_it_cannot_be_disabled](../../tests/test_model_configuration.py#L500) (Zeile 500)
- [ModelConfigurationTests::test_kimi_search_keeps_moonshot_zdr_route_and_model_reasoning](../../tests/test_model_configuration.py#L515) (Zeile 515)
- [ModelConfigurationTests::test_kimi_and_glm_payload_policies_are_applied](../../tests/test_model_configuration.py#L534) (Zeile 534)
- [ModelConfigurationTests::test_effective_reasoning_policy_matches_answer_payload_precedence](../../tests/test_model_configuration.py#L549) (Zeile 549)
- [ModelConfigurationTests::test_access_control_only_has_free_and_pro_models](../../tests/test_model_configuration.py#L569) (Zeile 569)
- [ModelConfigurationTests::test_presets_are_complete_and_free_presets_stay_free](../../tests/test_model_configuration.py#L589) (Zeile 589)
- [ModelConfigurationTests::test_admin_and_picker_have_no_early_contract](../../tests/test_model_configuration.py#L625) (Zeile 625)
- [ModelConfigurationTests::test_provider_errors_are_structured_without_fallback_response](../../tests/test_model_configuration.py#L639) (Zeile 639)
- [ModelConfigurationTests::test_input_helpers](../../tests/test_model_configuration.py#L650) (Zeile 650)

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

**Geprüftes Verhalten:** Registry als Session-Owner mit zwei aktiven Runs, Conversation-Locks und eingefrorener Config; gebundene Query-/Consensus-Callbacks, explizite Bookmark-/Logout-/Resolution-Ownership und Run-View-Projektion. Aktualisierung 02.10.2026: Consensuspayload trägt answer_receipts statt Clientantworttexte.

**Grenzen und Doubles:** Nur Strings/Ladereihenfolge; beweist keine korrekte Isolation bei wirklich überlappenden Antworten.

**Prüfauftrag für den Folgeaudit:** Mit run-registry-/ownership-/race-JS- und Browser-Dateien abgleichen.

**Direkte Codeverweise:** [static/firebase.js](../../static/firebase.js), [static/js/app-init.js](../../static/js/app-init.js), [static/js/consensus-insights.js](../../static/js/consensus-insights.js), [static/js/consensus-run.js](../../static/js/consensus-run.js), [static/js/query-send.js](../../static/js/query-send.js), [static/js/run-registry.js](../../static/js/run-registry.js), [static/js/run-view.js](../../static/js/run-view.js), [static/js/sources.js](../../static/js/sources.js).

<details>
<summary>3 Testdefinitionen und ihre Quellstellen</summary>

- [test_registry_is_the_single_browser_session_owner_and_loads_before_consumers](../../tests/test_multi_run_architecture.py#L18) (Zeile 18)
- [test_query_and_consensus_callbacks_use_their_bound_context_not_visible_dom](../../tests/test_multi_run_architecture.py#L37) (Zeile 37)
- [test_bookmark_view_and_logout_keep_run_ownership_explicit](../../tests/test_multi_run_architecture.py#L71) (Zeile 71)

</details>

<a id="test-navigation-settings-ui-py"></a>

## test_navigation_settings_ui.py

**Quelle:** [tests/test_navigation_settings_ui.py](../../tests/test_navigation_settings_ui.py) · **Bereiche:** Einstellungen, Frontend, Nutzergedächtnis, Scrollen und Navigation.

**Ebene:** Quelltextverträge.

**Lauf:** 27 bestanden.

**Geprüftes Verhalten:** Sidebar/Bookmarksuche/Modellpicker, öffentliche Navigation und Providerflächen, Mindestmodellauswahl, Demo ohne Usage-Signale sowie responsive Composer-/Leseregeln. Settings-Tabs, Memory zuerst, Lazy-Load, explizites Remember/Correct/Ask-about-this, Logout-Abbruch/Secret-Cleanup und Watch-Session-Fencing. Gemeinsames Tokenkonto und heutige Dashboardverträge. Das Autosize-Modul wird vor app-init geladen; App.initComposerAutosize und der öffentliche Resize-Trigger bleiben korrekt verbunden.

**Grenzen und Doubles:** Text-/CSS-/DOM-Strukturen im Source; tatsächliche Klicks, Geometrie und Raceausführung werden in eigenen DOM-/Chromiumfällen geprüft.

**Prüfauftrag für den Folgeaudit:** Die benannten Betriebs- und Testgrenzen bei künftigen Änderungen erneut prüfen; konkrete Paketnachweise stehen im Produktabgleich.

**Direkte Codeverweise:** [static/app-ui.js](../../static/app-ui.js), [static/css/components-input.css](../../static/css/components-input.css), [static/css/components-memory-edit.css](../../static/css/components-memory-edit.css), [static/css/components-misc.css](../../static/css/components-misc.css), [static/css/components-modals.css](../../static/css/components-modals.css), [static/css/components-watch.css](../../static/css/components-watch.css), [static/css/landing.css](../../static/css/landing.css), [static/css/layout.css](../../static/css/layout.css), [static/css/model-pulse.css](../../static/css/model-pulse.css), [static/css/shell.css](../../static/css/shell.css), [static/demo.js](../../static/demo.js), [static/firebase.js](../../static/firebase.js), [static/js/agent-chat.js](../../static/js/agent-chat.js), [static/js/app-init.js](../../static/js/app-init.js), [static/js/composer-autosize.js](../../static/js/composer-autosize.js), [static/js/composer-quote.js](../../static/js/composer-quote.js), [static/js/memory-edit.js](../../static/js/memory-edit.js), [static/js/model-picker.js](../../static/js/model-picker.js), [static/js/model-pulse.js](../../static/js/model-pulse.js), [static/js/query-send.js](../../static/js/query-send.js), [static/js/user-memory.js](../../static/js/user-memory.js), [static/js/watch-state.js](../../static/js/watch-state.js), [static/js/watch.js](../../static/js/watch.js), [templates/about.html](../../templates/about.html), [templates/ai-model-comparison.html](../../templates/ai-model-comparison.html), [templates/consensus-engine.html](../../templates/consensus-engine.html), [templates/index.html](../../templates/index.html), [templates/landing.html](../../templates/landing.html), [templates/model-pulse.html](../../templates/model-pulse.html), [templates/partials/public_footer.html](../../templates/partials/public_footer.html), [templates/partials/public_nav.html](../../templates/partials/public_nav.html), [templates/share.html](../../templates/share.html).

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
- [test_hero_greeting_requires_agent_mode_and_available_space](../../tests/test_navigation_settings_ui.py#L298) (Zeile 298)
- [test_settings_are_grouped_without_changing_control_ids](../../tests/test_navigation_settings_ui.py#L314) (Zeile 314)
- [test_every_settings_category_is_a_tab_panel_with_a_nav_item](../../tests/test_navigation_settings_ui.py#L340) (Zeile 340)
- [test_settings_tabs_read_as_navigation_not_as_buttons](../../tests/test_navigation_settings_ui.py#L369) (Zeile 369)
- [test_settings_visibility_is_owned_by_the_tab_controller](../../tests/test_navigation_settings_ui.py#L395) (Zeile 395)
- [test_memory_is_the_first_settings_category](../../tests/test_navigation_settings_ui.py#L410) (Zeile 410)
- [test_the_memory_profile_is_only_fetched_when_the_settings_open](../../tests/test_navigation_settings_ui.py#L472) (Zeile 472)
- [test_memory_selection_has_explicit_add_and_correct_flows](../../tests/test_navigation_settings_ui.py#L490) (Zeile 490)
- [test_selecting_answer_text_offers_asking_about_it](../../tests/test_navigation_settings_ui.py#L514) (Zeile 514)
- [test_logout_clears_the_loaded_run_and_aborts_active_streams](../../tests/test_navigation_settings_ui.py#L546) (Zeile 546)
- [test_watch_change_surfaces_use_tint_without_a_left_rail](../../tests/test_navigation_settings_ui.py#L587) (Zeile 587)
- [test_watch_requests_cannot_repopulate_account_state_after_logout](../../tests/test_navigation_settings_ui.py#L601) (Zeile 601)

</details>

<a id="test-og-image-py"></a>

## test_og_image.py

**Quelle:** [tests/test_og_image.py](../../tests/test_og_image.py) · **Bereiche:** Shares, Frontend.

**Ebene:** Echter Pillowrenderer und kontrollierter Imagecache.

**Lauf:** 4 bestanden.

**Geprüftes Verhalten:** Dekodierbare Karte mit mehreren gezeichneten Bildregionen, Fragepixeländerung, Score, Modelle/Konflikte und unscored. Weißes gültiges PNG wird erkannt. Alle sichtbaren Inputs/Historienwerte beeinflussen Cache, Renderfehler kann erneut versucht werden.

**Grenzen und Doubles:** Keine pixelgenauen plattformabhängigen Hashes; Route bietet weiterhin nur neuesten öffentlichen Stand, keine neue historische Auswahl.

**Prüfauftrag für den Folgeaudit:** Die benannten Betriebs- und Testgrenzen bei künftigen Änderungen erneut prüfen; konkrete Paketnachweise stehen im Produktabgleich.

**Direkte Codeverweise:** [app/services/og_image.py](../../app/services/og_image.py).

<details>
<summary>4 Testdefinitionen und ihre Quellstellen</summary>

- [test_renderer_draws_question_score_and_model_facts](../../tests/test_og_image.py#L31) (Zeile 31)
- [test_unscored_card_keeps_conflicts_without_inventing_agreement](../../tests/test_og_image.py#L58) (Zeile 58)
- [test_cache_tracks_all_rendered_content](../../tests/test_og_image.py#L72) (Zeile 72)
- [test_render_failure_is_safe_and_not_cached](../../tests/test_og_image.py#L89) (Zeile 89)

</details>

<a id="test-onboarding-gates-py"></a>

## test_onboarding_gates.py

**Quelle:** [tests/test_onboarding_gates.py](../../tests/test_onboarding_gates.py) · **Bereiche:** Authentifizierung, Frontend, Onboarding.

**Ebene:** Quelltextverträge plus Konfigurationsassertion.

**Lauf:** 7 bestanden.

**Geprüftes Verhalten:** Unverifizierte Session mit Banner/Resend/Recheck, Draft-Wiederherstellung über Verify-Link, keine Account-Existenzprobe mit eingegebenem Passwort, Follow-ups ohne Pro-Gate, mindestens zehn Free-Runs und Watch-Nudge mit privaten wöchentlichen Changes-only-Defaults. Aktualisierung 02.10.2026: Tarifgrenzen folgen dem Tokenkonto; Watch-Einstieg erklärt Änderungen anhand von Belegen.

**Grenzen und Doubles:** Auth/Draft/Watch-Interaktion überwiegend nicht ausgeführt; Mindestkontingent ist direkte Config-Prüfung.

**Prüfauftrag für den Folgeaudit:** Resend-/Verify-Fehler und Konto-/Tabwechsel in Runtime-Dateien abgleichen.

**Direkte Codeverweise:** [app/api/routers/chat.py](../../app/api/routers/chat.py), [app/core/config.py](../../app/core/config.py), [app/services/agent_budget_config.py](../../app/services/agent_budget_config.py), [static/css/components-input.css](../../static/css/components-input.css), [static/firebase.js](../../static/firebase.js), [static/js/app-init.js](../../static/js/app-init.js), [static/js/consensus-run.js](../../static/js/consensus-run.js), [static/js/email-verify.js](../../static/js/email-verify.js), [static/js/query-send.js](../../static/js/query-send.js), [static/js/watch.js](../../static/js/watch.js), [templates/index.html](../../templates/index.html).

<details>
<summary>7 Testdefinitionen und ihre Quellstellen</summary>

- [test_unverified_sessions_are_not_signed_out_anymore](../../tests/test_onboarding_gates.py#L30) (Zeile 30)
- [test_verification_banner_offers_resend_and_recheck](../../tests/test_onboarding_gates.py#L47) (Zeile 47)
- [test_verification_link_returns_to_the_app_with_the_typed_question](../../tests/test_onboarding_gates.py#L73) (Zeile 73)
- [test_registration_never_probes_account_existence_with_caller_credentials](../../tests/test_onboarding_gates.py#L99) (Zeile 99)
- [test_followups_are_no_longer_pro_gated](../../tests/test_onboarding_gates.py#L115) (Zeile 115)
- [test_free_daily_runs_allow_more_than_a_single_try](../../tests/test_onboarding_gates.py#L132) (Zeile 132)
- [test_watch_nudge_starts_a_watch_directly_and_says_when_it_writes](../../tests/test_onboarding_gates.py#L145) (Zeile 145)

</details>

<a id="test-pdf-extraction-isolation-py"></a>

## test_pdf_extraction_isolation.py

**Quelle:** [tests/test_pdf_extraction_isolation.py](../../tests/test_pdf_extraction_isolation.py) · **Bereiche:** Anhänge, Dateien und Dokumente.

**Ebene:** Echte PDF-Extraktion im Subprozess plus Timeout-/Output-Doubles.

**Lauf:** 10 bestanden.

**Geprüftes Verhalten:** PDF-Text, leere/gescannte/defekte Dateien, Zeichen-/Seiten-/Ausgabelimit, UTF-8 und hartes Zeitbudget. Eine parallel laufende normale Extraktion bleibt erreichbar, während der langsame Prozess beendet wird.

**Grenzen und Doubles:** Keine allgemeine Parser-Fuzzing-/OS-Sandbox-/Speicherlastprüfung.

**Prüfauftrag für den Folgeaudit:** Die benannten Mock-/Integrationsgrenzen am realen Adapter prüfen; Zuordnung und offene Aufgaben stehen in der Produktmatrix.

**Direkte Codeverweise:** [app/services/agent_file_extract.py](../../app/services/agent_file_extract.py), [app/services/llm/attachments.py](../../app/services/llm/attachments.py).

<details>
<summary>9 Testdefinitionen und ihre Quellstellen</summary>

- [test_normal_pdf_text_is_extracted_in_a_subprocess](../../tests/test_pdf_extraction_isolation.py#L41) (Zeile 41)
- [test_blank_or_scanned_pdf_reports_no_text](../../tests/test_pdf_extraction_isolation.py#L59) (Zeile 59)
- [test_malformed_pdf_fails_safely](../../tests/test_pdf_extraction_isolation.py#L69) (Zeile 69)
- [test_char_budget_stops_the_page_loop](../../tests/test_pdf_extraction_isolation.py#L73) (Zeile 73)
- [test_page_cap_bounds_work_for_many_page_documents](../../tests/test_pdf_extraction_isolation.py#L80) (Zeile 80)
- [test_slow_extraction_is_stopped_at_the_wall_clock_budget_and_others_stay_served](../../tests/test_pdf_extraction_isolation.py#L88) (Zeile 88)
- [test_oversized_child_response_is_rejected](../../tests/test_pdf_extraction_isolation.py#L118) (Zeile 118)
- [test_attachment_fallback_explains_unreadable_pdfs](../../tests/test_pdf_extraction_isolation.py#L130) (Zeile 130)
- [test_extractor_output_is_utf8_even_with_a_legacy_console_encoding](../../tests/test_pdf_extraction_isolation.py#L137) (Zeile 137)

</details>

<a id="test-phase4-frontend-py"></a>

## test_phase4_frontend.py

**Quelle:** [tests/test_phase4_frontend.py](../../tests/test_phase4_frontend.py) · **Bereiche:** Authentifizierung, Frontend, Nebenläufigkeit, Watch.

**Ebene:** Quelltextverträge.

**Lauf:** 14 bestanden.

**Geprüftes Verhalten:** UTC-Usage-Refresh, Auth-/View-Generationen, sichtbare/deduplizierte Bookmarkfehler und serielle Writes, Share-Abbruch/Epochs, Fan-out-Fehler/Mindestmodelle nach Attachmentfilter, Tier-Recovery, Auth-Watchdog und Watch-Rollback. Binder-Eindeutigkeit, Retry und Login-Dialog-ARIA/Fokus-Code. Aktualisierung 02.10.2026: Autoritatives Tokenbudget ist UID-gebunden; gespeicherte Einstellungen des Watch-Dashboards bleiben erhalten. Statische Quelltextverträge.

**Grenzen und Doubles:** Statische Strukturprüfungen; keine Runtime-Rennen oder tatsächlich geprüfte Fokusfalle. Nicht mit gleichnamiger E2E-Datei verwechseln.

**Prüfauftrag für den Folgeaudit:** Gleiche Verträge mit JS-race- und E2E-Phase4-Tests abgleichen.

**Direkte Codeverweise:** [static/app-ui.js](../../static/app-ui.js), [static/firebase.js](../../static/firebase.js), [static/js/app-bootstrap.js](../../static/js/app-bootstrap.js), [static/js/app-init.js](../../static/js/app-init.js), [static/js/auth-bootstrap.js](../../static/js/auth-bootstrap.js), [static/js/query-send.js](../../static/js/query-send.js), [static/js/share-dialog.js](../../static/js/share-dialog.js), [static/js/watch-dashboard.js](../../static/js/watch-dashboard.js), [static/js/watch.js](../../static/js/watch.js), [templates/index.html](../../templates/index.html), [templates/landing.html](../../templates/landing.html).

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
- [test_auth_bootstrap_watchdog_precedes_firebase_and_clears_stale_skeletons](../../tests/test_phase4_frontend.py#L143) (Zeile 143)
- [test_watch_modal_route_and_brief_state_have_deterministic_rollback_contracts](../../tests/test_phase4_frontend.py#L155) (Zeile 155)
- [test_bookmark_restore_uses_owned_run_state_and_token_wait_is_fenced](../../tests/test_phase4_frontend.py#L172) (Zeile 172)
- [test_bookmark_load_failure_has_a_visible_retry_state](../../tests/test_phase4_frontend.py#L187) (Zeile 187)
- [test_account_popup_and_settings_controls_have_exactly_one_binder](../../tests/test_phase4_frontend.py#L196) (Zeile 196)
- [test_login_dialog_accessibility_and_current_landing_marker_vocabulary](../../tests/test_phase4_frontend.py#L211) (Zeile 211)

</details>

<a id="test-phase5-operations-py"></a>

## test_phase5_operations.py

**Quelle:** [tests/test_phase5_operations.py](../../tests/test_phase5_operations.py) · **Bereiche:** Fehlerdiagnostik, Persistenz, Runtime, Watch.

**Ebene:** Gemischt: Services mit DB-/HTTP-Doubles, Thread-/Async-Tests und Deployment-Quelltextverträge.

**Lauf:** 34 bestanden.

**Geprüftes Verhalten:** Bookmark-Count/Bytes/Merge/Löschung/Transaktionsretry, Account-Tombstones, Feedback-/Follow-Resendbudgets und rungebundene Votes/Expiry. Favicon-Singleflight/LRU/Fehler/Capacity und aktiver Eventloop, Correlation/Metriken/Redaktion, Provider-Timeout und Disconnect als cancelled, begrenzte Due-Brief-Query und Index-/Dependency-Verträge. Aktualisierung 02.10.2026: BYOK und unverifizierte Ergebnisse bleiben von Modellrankings ausgeschlossen.

**Grenzen und Doubles:** Threads/Async-Verhalten lokal real, externe DB/Fetch/Provider ersetzt. Kein Last-/Deploymenttest; Subprozess testet Routerimport nach asyncio.run.

**Prüfauftrag für den Folgeaudit:** Mehrprozess-Budgets, globale Cachegrenzen und tatsächliche Worker-/Transportabbrüche abgleichen.

**Direkte Codeverweise:** [app/api/routers/chat.py](../../app/api/routers/chat.py), [app/api/routers/pages.py](../../app/api/routers/pages.py), [app/api/routers/topics.py](../../app/api/routers/topics.py), [app/core/observability.py](../../app/core/observability.py), [app/core/rate_limit.py](../../app/core/rate_limit.py), [app/services/favicons.py](../../app/services/favicons.py), [app/services/follow_challenges.py](../../app/services/follow_challenges.py), [app/services/llm/consensus_engine.py](../../app/services/llm/consensus_engine.py), [app/services/llm/engines.py](../../app/services/llm/engines.py), [app/services/llm/provider_runtime.py](../../app/services/llm/provider_runtime.py), [app/services/llm/provider_transport.py](../../app/services/llm/provider_transport.py), [app/services/persistence_guard.py](../../app/services/persistence_guard.py), [app/services/watch_brief.py](../../app/services/watch_brief.py), [firebase.json](../../firebase.json), [firestore.indexes.json](../../firestore.indexes.json).

<details>
<summary>26 Testdefinitionen und ihre Quellstellen</summary>

- [test_bookmark_quota_counts_merges_and_rejects_oversize](../../tests/test_phase5_operations.py#L160) (Zeile 160)
- [test_persistence_transactions_have_a_contention_retry_budget](../../tests/test_phase5_operations.py#L193) (Zeile 193)
- [test_bookmark_quota_accepts_legacy_owner_above_the_old_cap](../../tests/test_phase5_operations.py#L215) (Zeile 215)
- [test_bookmark_delete_updates_quota_with_firestore_transaction_contract](../../tests/test_phase5_operations.py#L234) (Zeile 234)
- [test_account_deletion_tombstone_fences_normal_bookmark_delete](../../tests/test_phase5_operations.py#L253) (Zeile 253)
- [test_account_deletion_tombstone_fences_owner_persistence](../../tests/test_phase5_operations.py#L271) (Zeile 271)
- [test_feedback_cooldown_and_daily_limit_are_persistent](../../tests/test_phase5_operations.py#L316) (Zeile 316)
- [test_vote_is_run_bound_and_exactly_once](../../tests/test_phase5_operations.py#L335) (Zeile 335)
- [test_byok_and_unverified_results_never_count_for_model_rankings](../../tests/test_phase5_operations.py#L359) (Zeile 359)
- [test_vote_expiry_is_fail_closed](../../tests/test_phase5_operations.py#L389) (Zeile 389)
- [test_follow_confirmation_has_persistent_resend_and_recipient_budgets](../../tests/test_phase5_operations.py#L417) (Zeile 417)
- [test_favicon_proxy_single_flights_and_uses_lru](../../tests/test_phase5_operations.py#L435) (Zeile 435)
- [test_favicon_exception_releases_followers_and_allows_retry](../../tests/test_phase5_operations.py#L462) (Zeile 462)
- [test_topics_router_imports_after_asyncio_run_and_uses_the_active_loop](../../tests/test_phase5_operations.py#L488) (Zeile 488)
- [test_favicon_capacity_fallback_is_never_cached](../../tests/test_phase5_operations.py#L517) (Zeile 517)
- [test_favicon_unexpected_failure_returns_private_fallback_without_raw_log](../../tests/test_phase5_operations.py#L541) (Zeile 541)
- [test_invalid_vote_model_never_reaches_logs](../../tests/test_phase5_operations.py#L563) (Zeile 563)
- [test_correlation_header_metrics_and_log_redaction](../../tests/test_phase5_operations.py#L590) (Zeile 590)
- [test_provider_pipeline_metrics_classify_normalized_results_without_secrets](../../tests/test_phase5_operations.py#L635) (Zeile 635)
- [test_upstream_http_timeout_status_is_normalized_without_response_body](../../tests/test_phase5_operations.py#L666) (Zeile 666)
- [test_ask_metrics_classify_normalized_openrouter_timeouts](../../tests/test_phase5_operations.py#L681) (Zeile 681)
- [test_ask_disconnect_records_cancellation_not_success](../../tests/test_phase5_operations.py#L727) (Zeile 727)
- [test_cancelled_provider_metric_has_a_dedicated_counter](../../tests/test_phase5_operations.py#L796) (Zeile 796)
- [test_due_brief_query_filters_and_limits_in_firestore](../../tests/test_phase5_operations.py#L804) (Zeile 804)
- [test_phase5_frontend_vote_binding_and_deployment_contracts](../../tests/test_phase5_operations.py#L815) (Zeile 815)
- [test_benchmark_only_dependencies_are_not_in_production_requirements](../../tests/test_phase5_operations.py#L831) (Zeile 831)

</details>

<a id="test-phase6-architecture-py"></a>

## test_phase6_architecture.py

**Quelle:** [tests/test_phase6_architecture.py](../../tests/test_phase6_architecture.py) · **Bereiche:** Betrieb, Frontend-Build.

**Ebene:** Statische Architektur-, Routing- und Assetverträge.

**Lauf:** 8 bestanden.

**Geprüftes Verhalten:** Modulgrenzen, Endpointregistrierung, Template-/Skriptstruktur und versioniertes Assetformat. Kein fest verdrahteter alter Cache-Key; Resilienzsuite prüft Aktualität/Konsistenz gegen Git separat.

**Grenzen und Doubles:** Quelltextverträge beweisen keine tatsächliche Ausführung aller Routen oder Bundles.

**Prüfauftrag für den Folgeaudit:** Die benannten Betriebs- und Testgrenzen bei künftigen Änderungen erneut prüfen; konkrete Paketnachweise stehen im Produktabgleich.

**Direkte Codeverweise:** [app/api/routers/chat.py](../../app/api/routers/chat.py), [app/core/security.py](../../app/core/security.py), [app/core/site.py](../../app/core/site.py), [app/services/api_consensus_runner.py](../../app/services/api_consensus_runner.py), [app/services/consensus_pipeline.py](../../app/services/consensus_pipeline.py), [app/services/llm/consensus_engine.py](../../app/services/llm/consensus_engine.py), [app/services/topic_pipeline.py](../../app/services/topic_pipeline.py), [app/services/topic_runner.py](../../app/services/topic_runner.py), [app/services/watch_scheduler.py](../../app/services/watch_scheduler.py), [static/css/components-consensus-insights.css](../../static/css/components-consensus-insights.css), [static/css/components-consensus-visuals.css](../../static/css/components-consensus-visuals.css), [static/css/landing.css](../../static/css/landing.css), [static/js/admin-benchmark.js](../../static/js/admin-benchmark.js), [static/js/admin-config.js](../../static/js/admin-config.js), [static/js/admin.js](../../static/js/admin.js), [static/js/app-state.js](../../static/js/app-state.js), [templates/admin.html](../../templates/admin.html), [templates/admin_benchmark.html](../../templates/admin_benchmark.html), [templates/index.html](../../templates/index.html), [templates/partials/admin_prompt_config.html](../../templates/partials/admin_prompt_config.html).

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
- [test_consensus_visuals_are_shared_and_dead_dom_contracts_are_gone](../../tests/test_phase6_architecture.py#L207) (Zeile 207)

</details>

<a id="test-plus-tier-py"></a>

## test_plus_tier.py

**Quelle:** [tests/test_plus_tier.py](../../tests/test_plus_tier.py) · **Bereiche:** Authentifizierung.

**Ebene:** Entitlements-/Konfigurationslogik und Security mit DB-Double.

**Lauf:** 34 bestanden.

**Geprüftes Verhalten:** Plus besitzt mehr Tokens als Free, aber kein Deep Think; Output-/Wortlimits werden separat vom Tokenkonto behandelt.

**Grenzen und Doubles:** Viele Assertions vergleichen Konfigurationswerte untereinander; sie beweisen keine tatsächliche Endpoint-Durchsetzung oder reale Quotenbelastung.

**Prüfauftrag für den Folgeaudit:** Jede Entitlement-Grenze serverseitig und im Frontend mit den entsprechenden Router-/JS-Tests abgleichen.

**Direkte Codeverweise:** [app/core/config.py](../../app/core/config.py), [app/core/entitlements.py](../../app/core/entitlements.py), [app/core/security.py](../../app/core/security.py), [app/services/agent_budget_config.py](../../app/services/agent_budget_config.py), [app/services/llm/attachments.py](../../app/services/llm/attachments.py), [app/services/llm/base.py](../../app/services/llm/base.py).

<details>
<summary>18 Testdefinitionen und ihre Quellstellen</summary>

- [test_normalize_tier](../../tests/test_plus_tier.py#L49) (Zeile 49)
- [test_unknown_tier_never_becomes_plus_or_pro](../../tests/test_plus_tier.py#L53) (Zeile 53)
- [test_tier_ordering](../../tests/test_plus_tier.py#L58) (Zeile 58)
- [test_plus_gets_the_features_but_not_the_expensive_models](../../tests/test_plus_tier.py#L67) (Zeile 67)
- [test_free_gets_nothing_and_pro_gets_everything](../../tests/test_plus_tier.py#L77) (Zeile 77)
- [test_plus_has_a_larger_token_allowance_than_free](../../tests/test_plus_tier.py#L86) (Zeile 86)
- [test_plus_has_no_deep_think_entitlement](../../tests/test_plus_tier.py#L95) (Zeile 95)
- [test_plus_deep_search_limits_fall_back_to_free](../../tests/test_plus_tier.py#L101) (Zeile 101)
- [test_plus_sits_between_free_and_pro_for_memory](../../tests/test_plus_tier.py#L106) (Zeile 106)
- [test_plus_watch_limit_sits_between_free_and_pro](../../tests/test_plus_tier.py#L114) (Zeile 114)
- [test_plus_watches_run_on_the_free_models](../../tests/test_plus_tier.py#L122) (Zeile 122)
- [test_plus_daily_watch_interval_follows_the_admin_switch](../../tests/test_plus_tier.py#L128) (Zeile 128)
- [test_a_plus_limit_missing_from_the_config_falls_back_to_free_not_pro](../../tests/test_plus_tier.py#L145) (Zeile 145)
- [test_plus_limits_are_admin_configurable](../../tests/test_plus_tier.py#L155) (Zeile 155)
- [test_memory_plus_chars_is_clamped_between_free_and_pro](../../tests/test_plus_tier.py#L166) (Zeile 166)
- [test_plus_cannot_pick_a_premium_model](../../tests/test_plus_tier.py#L177) (Zeile 177)
- [test_attachments_open_at_plus](../../tests/test_plus_tier.py#L190) (Zeile 190)
- [test_tier_lookup_derives_all_three_flags](../../tests/test_plus_tier.py#L221) (Zeile 221)

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

<a id="test-public-markdown-py"></a>

## test_public_markdown.py

**Quelle:** [tests/test_public_markdown.py](../../tests/test_public_markdown.py) · **Bereiche:** Topics, Quellen.

**Ebene:** Öffentlicher Markdownrenderer.

**Lauf:** 1 bestanden.

**Geprüftes Verhalten:** Zitate ausgeschlossener Quellen verschwinden statt als rohe Marker stehenzubleiben; erlaubte Quellen behalten ihre Anker.

**Grenzen und Doubles:** Ein gezielter Renderingfall; keine vollständige Sanitizer-/Browserprüfung.

**Prüfauftrag für den Folgeaudit:** Die benannten Mock-/Integrationsgrenzen am realen Adapter prüfen; Zuordnung und offene Aufgaben stehen in der Produktmatrix.

**Direkte Codeverweise:** [app/services/public_markdown.py](../../app/services/public_markdown.py).

<details>
<summary>1 Testdefinitionen und ihre Quellstellen</summary>

- [test_citations_to_excluded_sources_are_dropped_not_shown_raw](../../tests/test_public_markdown.py#L3) (Zeile 3)

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

**Lauf:** 6 bestanden.

**Geprüftes Verhalten:** Defaultpersistenz, Free-Watch-Profil/Capacity, normalisierte Save-/Actorfelder, Migration überholter Standardbriefs zur Disagreement-Strategie und Erhalt manuell editierten Briefs. Aktualisierung 02.10.2026: Öffentliche Konfiguration und Adminanzeige nennen reale Initial-/Watchprovider statt statischem DeepSeek-Ausschluss.

**Grenzen und Doubles:** Keine echte DB/Cachekonkurrenz; nicht der vollständige Publisherlauf.

**Prüfauftrag für den Folgeaudit:** Ungültige Configtypen und parallele Migration/Saves abgleichen.

**Direkte Codeverweise:** [app/core/config.py](../../app/core/config.py), [app/services/api_consensus_runner.py](../../app/services/api_consensus_runner.py), [app/services/publisher_config.py](../../app/services/publisher_config.py).

<details>
<summary>6 Testdefinitionen und ihre Quellstellen</summary>

- [test_default_publisher_configuration_is_persisted_and_free_pinned](../../tests/test_publisher_config.py#L48) (Zeile 48)
- [test_public_config_reports_the_real_provider_plan_instead_of_an_exclusion](../../tests/test_publisher_config.py#L63) (Zeile 63)
- [test_admin_publisher_ui_makes_no_static_provider_exclusion_promise](../../tests/test_publisher_config.py#L89) (Zeile 89)
- [test_saved_publisher_configuration_is_normalized](../../tests/test_publisher_config.py#L102) (Zeile 102)
- [test_superseded_default_topic_briefs_migrate_to_the_disagreement_strategy](../../tests/test_publisher_config.py#L119) (Zeile 119)
- [test_hand_edited_topic_brief_is_never_overwritten](../../tests/test_publisher_config.py#L134) (Zeile 134)

</details>

<a id="test-publisher-standalone-py"></a>

## test_publisher_standalone.py

**Quelle:** [tests/test_publisher_standalone.py](../../tests/test_publisher_standalone.py) · **Bereiche:** Publisher, Betrieb.

**Ebene:** Isolierter Python-Subprozess ohne optionale Pakete oder externe Services.

**Lauf:** 3 bestanden.

**Geprüftes Verhalten:** Scheduled Publisher läuft mit kontrollierten Diensten und unverändertem fachlichem Ergebnis auch unter Windows; explizites UTF-8 verhindert fehlerhafte Ergebnisdekodierung im -E/-S-Prozess.

**Grenzen und Doubles:** Provider/DB kontrolliert; kein geplanter Produktivlauf.

**Prüfauftrag für den Folgeaudit:** Die benannten Betriebs- und Testgrenzen bei künftigen Änderungen erneut prüfen; konkrete Paketnachweise stehen im Produktabgleich.

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

**Geprüftes Verhalten:** IP-Schlüssel aus Socket/Proxyheader/Kette, getrennte Besucher hinter Proxy und leerer Headerfallback; API-Schlüssel mit cns_-Präfix wird gehasht. Fehlender oder falsch präfixierter Key fällt auf IP zurück. Zwei Aufrufe derselben UID überschreiten deren Limit; ein wirklicher Keywechsel wird nicht ausgeführt.

**Grenzen und Doubles:** Künstliche Request-Scopes; kein vertrauenswürdiger Reverse-Proxy oder verteilter Limiter. Präfixgültige, aber nicht authentifizierbare Keys werden hier nicht geprüft. Der separate IP-Guard der Consensus-API ist in test_consensus_api abgedeckt; daraus folgt kein vollständiger Limiter-Bypass.

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

**Quelle:** [tests/test_request_body_limits.py](../../tests/test_request_body_limits.py) · **Bereiche:** Betrieb, Sicherheit.

**Ebene:** Registrierte Bodylimit-Middleware mit ASGI-Ereignissen.

**Lauf:** 22 bestanden.

**Geprüftes Verhalten:** Deklarierte und tatsächliche Bodygrößen werden begrenzt, gültige Größen akzeptiert. Früher Disconnect wird nicht als vollständiger Request weitergereicht, auch wenn das Präfix gültiges JSON enthält; kein unbegrenztes Lesen.

**Grenzen und Doubles:** Lokaler ASGI-Transport; reale Socketgrenzen werden separat geprüft.

**Prüfauftrag für den Folgeaudit:** Die benannten Betriebs- und Testgrenzen bei künftigen Änderungen erneut prüfen; konkrete Paketnachweise stehen im Produktabgleich.

**Direkte Codeverweise:** [app/core/request_limits.py](../../app/core/request_limits.py).

<details>
<summary>9 Testdefinitionen und ihre Quellstellen</summary>

- [test_declared_oversized_body_is_rejected_without_reading_or_parsing](../../tests/test_request_body_limits.py#L41) (Zeile 41)
- [test_chunked_body_is_counted_across_receive_messages](../../tests/test_request_body_limits.py#L51) (Zeile 51)
- [test_exact_limit_body_is_replayed_once_to_the_application](../../tests/test_request_body_limits.py#L63) (Zeile 63)
- [test_invalid_or_oversized_length_never_reaches_handler](../../tests/test_request_body_limits.py#L78) (Zeile 78)
- [test_request_limit_configuration_boundaries](../../tests/test_request_body_limits.py#L86) (Zeile 86)
- [test_invalid_configuration_fails_before_serving](../../tests/test_request_body_limits.py#L96) (Zeile 96)
- [test_early_disconnect_does_not_replay_partial_body_as_complete](../../tests/test_request_body_limits.py#L103) (Zeile 103)
- [test_non_http_scope_passes_through_without_reading_body](../../tests/test_request_body_limits.py#L109) (Zeile 109)
- [test_replayed_body_does_not_synthesize_disconnect_for_delayed_stream](../../tests/test_request_body_limits.py#L122) (Zeile 122)

</details>

<a id="test-resolve-round-py"></a>

## test_resolve_round.py

**Quelle:** [tests/test_resolve_round.py](../../tests/test_resolve_round.py) · **Bereiche:** Bookmarks und Verlauf, Konsens und Unterschiede, Konten und Tarife.

**Ebene:** Resolve-Unit-/Routertests mit Engine-/DB-Doubles.

**Lauf:** 23 bestanden.

**Geprüftes Verhalten:** Positionsnormalisierung/Modelle/Aliase/Gegenpositionen/Caps, maintain/revise/standoff/mutual_revision/error, fehlender Key ohne Call. Auth und Plus-Gate, Usage-Zählung/Limit/normaler Run-Konflikt; nur Serverresultat auf exakt gebundener Bookmarkrevision persistiert, spätere Revision bleibt unangetastet. Aktualisierung 02.10.2026: Resolve verwendet Tokenadmission, gibt Restreservierung frei und meldet erschöpftes Konto ohne Doppelbuchung.

**Grenzen und Doubles:** LLM-Entscheidungen konstruiert; Bookmark-DB ersetzt. Kein Browser und keine gemessene Wahrheit der Auflösung.

**Prüfauftrag für den Folgeaudit:** In-flight Bookmarkwechsel/Logout mit Frontendtests sowie konkurrierende Persistenz abgleichen.

**Direkte Codeverweise:** [app/api/routers/bookmarks.py](../../app/api/routers/bookmarks.py), [app/api/routers/chat.py](../../app/api/routers/chat.py), [app/core/config.py](../../app/core/config.py), [app/core/rate_limit.py](../../app/core/rate_limit.py), [app/services/agent_budget_config.py](../../app/services/agent_budget_config.py), [app/services/agent_quota.py](../../app/services/agent_quota.py), [app/services/llm/resolve_engine.py](../../app/services/llm/resolve_engine.py), [app/services/usage_repository.py](../../app/services/usage_repository.py), [main.py](../../main.py).

**Direkte Testhelfer:** [tests/usage_test_support.py](../../tests/usage_test_support.py).

<details>
<summary>23 Testdefinitionen und ihre Quellstellen</summary>

- [TestNormalizeResolvePositions::test_valid_payload_is_normalized](../../tests/test_resolve_round.py#L49) (Zeile 49)
- [TestNormalizeResolvePositions::test_model_aliases_are_canonicalized](../../tests/test_resolve_round.py#L54) (Zeile 54)
- [TestNormalizeResolvePositions::test_unknown_models_are_dropped](../../tests/test_resolve_round.py#L60) (Zeile 60)
- [TestNormalizeResolvePositions::test_missing_claim_is_rejected](../../tests/test_resolve_round.py#L66) (Zeile 66)
- [TestNormalizeResolvePositions::test_single_position_is_rejected](../../tests/test_resolve_round.py#L70) (Zeile 70)
- [TestNormalizeResolvePositions::test_same_model_on_both_sides_is_rejected](../../tests/test_resolve_round.py#L74) (Zeile 74)
- [TestNormalizeResolvePositions::test_oversized_texts_are_clipped](../../tests/test_resolve_round.py#L80) (Zeile 80)
- [TestRunResolveRound::test_all_maintain_is_standoff](../../tests/test_resolve_round.py#L97) (Zeile 97)
- [TestRunResolveRound::test_one_revision_is_resolved](../../tests/test_resolve_round.py#L105) (Zeile 105)
- [TestRunResolveRound::test_all_revise_is_mutual_revision](../../tests/test_resolve_round.py#L115) (Zeile 115)
- [TestRunResolveRound::test_provider_errors_do_not_break_the_round](../../tests/test_resolve_round.py#L121) (Zeile 121)
- [TestRunResolveRound::test_all_failures_yield_error_outcome](../../tests/test_resolve_round.py#L132) (Zeile 132)
- [TestRunResolveRound::test_invalid_decision_counts_as_error](../../tests/test_resolve_round.py#L138) (Zeile 138)
- [TestRunResolveRound::test_missing_shared_key_skips_all_engine_calls](../../tests/test_resolve_round.py#L144) (Zeile 144)
- [test_resolve_requires_auth](../../tests/test_resolve_round.py#L231) (Zeile 231)
- [test_resolve_is_refused_below_plus](../../tests/test_resolve_round.py#L237) (Zeile 237)
- [test_resolve_is_open_to_plus](../../tests/test_resolve_round.py#L247) (Zeile 247)
- [test_resolve_rejects_invalid_positions](../../tests/test_resolve_round.py#L263) (Zeile 263)
- [test_resolve_counts_usage_and_returns_result](../../tests/test_resolve_round.py#L274) (Zeile 274)
- [test_resolve_rejects_a_key_reserved_for_a_normal_consensus](../../tests/test_resolve_round.py#L295) (Zeile 295)
- [test_resolve_blocks_when_usage_limit_reached](../../tests/test_resolve_round.py#L324) (Zeile 324)
- [test_resolve_persists_only_the_server_result_on_the_bound_bookmark_revision](../../tests/test_resolve_round.py#L338) (Zeile 338)
- [test_resolve_does_not_persist_after_the_bookmark_revision_advanced](../../tests/test_resolve_round.py#L394) (Zeile 394)

</details>

<a id="test-result-integrity-py"></a>

## test_result_integrity.py

**Quelle:** [tests/test_result_integrity.py](../../tests/test_result_integrity.py) · **Bereiche:** Consensus, API, Provider.

**Ebene:** Echte Chatrouter-/Receiptfunktionen mit ersetzter Synthese und Persistenz.

**Lauf:** 27 bestanden.

**Geprüftes Verhalten:** Consensus erhält ausschließlich gespeicherte, Owner/Run/Frage/Modell-gebundene Antwortreceipts; manipulierte oder fremde Belege werden abgelehnt. BYOK nimmt nicht am Ranking teil; unterbrochene Antworten entfallen, Tokenlimitantworten bleiben markiert; unvollständige Synthese endet fehlgeschlagen ohne Ergebnis-ID.

**Grenzen und Doubles:** Auth, Provider und DB ersetzt; Browserpayload zusätzlich als Quelltext geprüft. Kein kompletter Browser→DB-Nachweis.

**Prüfauftrag für den Folgeaudit:** Die benannten Mock-/Integrationsgrenzen am realen Adapter prüfen; Zuordnung und offene Aufgaben stehen in der Produktmatrix.

**Direkte Codeverweise:** [app/api/routers/chat.py](../../app/api/routers/chat.py), [app/core/config.py](../../app/core/config.py), [app/core/rate_limit.py](../../app/core/rate_limit.py), [app/services/answer_receipts.py](../../app/services/answer_receipts.py), [app/services/llm/completion.py](../../app/services/llm/completion.py), [app/services/llm/consensus_engine.py](../../app/services/llm/consensus_engine.py), [app/services/llm/engines.py](../../app/services/llm/engines.py), [app/services/llm/provider_transport.py](../../app/services/llm/provider_transport.py), [app/services/run_metering.py](../../app/services/run_metering.py), [app/services/usage_repository.py](../../app/services/usage_repository.py).

<details>
<summary>19 Testdefinitionen und ihre Quellstellen</summary>

- [test_consensus_uses_exactly_the_stored_answers](../../tests/test_result_integrity.py#L98) (Zeile 98)
- [test_client_answer_text_is_never_a_model_answer](../../tests/test_result_integrity.py#L107) (Zeile 107)
- [test_forged_or_foreign_receipts_are_rejected](../../tests/test_result_integrity.py#L120) (Zeile 120)
- [test_model_names_come_from_the_receipt_not_the_client](../../tests/test_result_integrity.py#L146) (Zeile 146)
- [test_byok_results_are_flagged_and_excluded_from_rankings](../../tests/test_result_integrity.py#L158) (Zeile 158)
- [test_own_key_synthesis_of_developer_answers_is_flagged](../../tests/test_result_integrity.py#L167) (Zeile 167)
- [test_developer_results_keep_rankings](../../tests/test_result_integrity.py#L176) (Zeile 176)
- [test_browser_retry_of_the_same_receipts_is_accepted](../../tests/test_result_integrity.py#L200) (Zeile 200)
- [test_ask_issues_a_receipt_bound_to_owner_run_question_and_model](../../tests/test_result_integrity.py#L209) (Zeile 209)
- [test_interrupted_answers_never_enter_the_synthesis](../../tests/test_result_integrity.py#L235) (Zeile 235)
- [test_token_limit_answers_enter_the_synthesis_marked_as_truncated](../../tests/test_result_integrity.py#L244) (Zeile 244)
- [test_truncated_streaming_synthesis_is_never_a_completed_result](../../tests/test_result_integrity.py#L259) (Zeile 259)
- [test_complete_streaming_synthesis_reports_complete](../../tests/test_result_integrity.py#L280) (Zeile 280)
- [test_stream_consensus_marks_truncation_and_does_not_mix_retries](../../tests/test_result_integrity.py#L293) (Zeile 293)
- [test_query_consensus_rejects_a_token_limited_synthesis](../../tests/test_result_integrity.py#L321) (Zeile 321)
- [test_non_streaming_query_model_reports_token_limit](../../tests/test_result_integrity.py#L329) (Zeile 329)
- [test_provider_fan_out_drops_interrupted_and_marks_truncated_answers](../../tests/test_result_integrity.py#L346) (Zeile 346)
- [test_browser_flow_carries_receipts_and_completion_state](../../tests/test_result_integrity.py#L361) (Zeile 361)
- [test_rejected_answer_sets_fail_the_pending_turn](../../tests/test_result_integrity.py#L377) (Zeile 377)

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

**Lauf:** 14 bestanden.

**Geprüftes Verhalten:** Prepare reserviert eine tier-/modusabhängige Kostenschätzung einmal; parallele Ask-Aufrufe und Judges buchen gemessene Tokens einmal. Release/Final löst Holds, Admin benutzt Adminkonto, angenommene Arbeit darf das Restkonto überziehen.

**Grenzen und Doubles:** Nebenläufige Requests lokal, Repository nutzt sperrenden Fake; Provider wird nicht kontaktiert.

**Prüfauftrag für den Folgeaudit:** Echte Firestore-Contention und Abbruch nach Autorisierung mit E2E-Transaktionen abgleichen.

**Direkte Codeverweise:** [app/api/routers/chat.py](../../app/api/routers/chat.py), [app/api/routers/users.py](../../app/api/routers/users.py), [app/core/config.py](../../app/core/config.py), [app/core/rate_limit.py](../../app/core/rate_limit.py), [app/services/agent_budget_config.py](../../app/services/agent_budget_config.py), [app/services/agent_quota.py](../../app/services/agent_quota.py), [app/services/llm/usage_meter.py](../../app/services/llm/usage_meter.py), [app/services/usage_repository.py](../../app/services/usage_repository.py).

**Direkte Testhelfer:** [tests/usage_test_support.py](../../tests/usage_test_support.py).

<details>
<summary>12 Testdefinitionen und ihre Quellstellen</summary>

- [test_prepare_admits_once_and_answers_book_their_measured_tokens](../../tests/test_run_usage_endpoints.py#L100) (Zeile 100)
- [test_compare_runs_are_admitted_against_the_compare_estimate](../../tests/test_run_usage_endpoints.py#L127) (Zeile 127)
- [test_prepare_is_refused_when_the_account_does_not_cover_a_run](../../tests/test_run_usage_endpoints.py#L134) (Zeile 134)
- [test_parallel_same_provider_operation_runs_only_once](../../tests/test_run_usage_endpoints.py#L150) (Zeile 150)
- [test_consensus_books_its_judges_once_and_drops_the_hold](../../tests/test_run_usage_endpoints.py#L165) (Zeile 165)
- [test_usage_endpoint_reads_the_account_and_release_drops_the_hold](../../tests/test_run_usage_endpoints.py#L210) (Zeile 210)
- [test_requests_without_run_key_are_rejected_before_provider_call](../../tests/test_run_usage_endpoints.py#L229) (Zeile 229)
- [test_exhausted_firestore_contention_returns_structured_503](../../tests/test_run_usage_endpoints.py#L241) (Zeile 241)
- [test_deep_think_is_admitted_against_the_deep_think_estimate](../../tests/test_run_usage_endpoints.py#L254) (Zeile 254)
- [test_admin_role_uses_the_admin_tier](../../tests/test_run_usage_endpoints.py#L268) (Zeile 268)
- [test_authorization_rejections_never_start_a_second_provider](../../tests/test_run_usage_endpoints.py#L281) (Zeile 281)
- [test_admitted_run_finishes_and_may_overdraw_the_account](../../tests/test_run_usage_endpoints.py#L304) (Zeile 304)

</details>

<a id="test-run-usage-repository-py"></a>

## test_run_usage_repository.py

**Quelle:** [tests/test_run_usage_repository.py](../../tests/test_run_usage_repository.py) · **Bereiche:** Konten und Tarife, Persistenz.

**Ebene:** Repository-/Transaktionsverträge mit FakeFirestore und Threads.

**Lauf:** 29 bestanden.

**Geprüftes Verhalten:** Runzählquoten entfallen. Compare/Consensus/Deep Think teilen mit Agent ein UTC-Tageskonto; parallele Admission/Idempotenz, einzelne Messbuchungen, schrumpfende Holds, Ablauf/Freigabe und Bindung an den Admissiontag werden im Fake geprüft.

**Grenzen und Doubles:** Lockbasierter Fake; SDK-Decorator-Pfad nur instrumentiert. Tatsächliche Firestore-Retries und Mehrprozess-Atomizität hier nicht ausgeführt.

**Prüfauftrag für den Folgeaudit:** Emulator-Reservation-/Claim-Rennen und Counter-Recovery bei Prozessabbruch abgleichen.

**Direkte Codeverweise:** [app/core/config.py](../../app/core/config.py), [app/services/agent_budget_config.py](../../app/services/agent_budget_config.py), [app/services/agent_quota.py](../../app/services/agent_quota.py), [app/services/persistence_guard.py](../../app/services/persistence_guard.py), [app/services/usage_repository.py](../../app/services/usage_repository.py).

**Direkte Testhelfer:** [tests/usage_test_support.py](../../tests/usage_test_support.py).

<details>
<summary>25 Testdefinitionen und ihre Quellstellen</summary>

- [test_run_quotas_are_gone_from_the_limits_config](../../tests/test_run_usage_repository.py#L55) (Zeile 55)
- [test_token_admission_follows_tier_and_mode](../../tests/test_run_usage_repository.py#L65) (Zeile 65)
- [test_production_path_wraps_reserve_in_firestore_transaction](../../tests/test_run_usage_repository.py#L82) (Zeile 82)
- [test_admission_needs_the_expected_run_cost_and_holds_it](../../tests/test_run_usage_repository.py#L118) (Zeile 118)
- [test_parallel_admissions_cannot_oversubscribe_the_account](../../tests/test_run_usage_repository.py#L135) (Zeile 135)
- [test_parallel_same_idempotency_key_admits_only_once](../../tests/test_run_usage_repository.py#L152) (Zeile 152)
- [test_idempotency_is_scoped_by_uid_and_bound_to_run_kind](../../tests/test_run_usage_repository.py#L166) (Zeile 166)
- [test_consume_is_idempotent_and_changes_no_tokens](../../tests/test_run_usage_repository.py#L179) (Zeile 179)
- [test_booking_debits_measured_tokens_once_and_may_overdraw](../../tests/test_run_usage_repository.py#L194) (Zeile 194)
- [test_bookings_shrink_the_hold_and_final_drops_the_rest](../../tests/test_run_usage_repository.py#L219) (Zeile 219)
- [test_expired_holds_stop_blocking_admissions](../../tests/test_run_usage_repository.py#L231) (Zeile 231)
- [test_booking_requires_a_consumed_run](../../tests/test_run_usage_repository.py#L239) (Zeile 239)
- [test_release_drops_the_hold_and_is_idempotent](../../tests/test_run_usage_repository.py#L250) (Zeile 250)
- [test_agent_and_pipeline_share_one_account](../../tests/test_run_usage_repository.py#L264) (Zeile 264)
- [test_get_run_is_read_only_and_reports_consumed_status](../../tests/test_run_usage_repository.py#L282) (Zeile 282)
- [test_consumed_run_context_binding_is_idempotent_and_target_specific](../../tests/test_run_usage_repository.py#L294) (Zeile 294)
- [test_pending_account_deletion_fences_every_usage_mutation](../../tests/test_run_usage_repository.py#L310) (Zeile 310)
- [test_expired_run_cannot_be_read_or_bound_to_new_context](../../tests/test_run_usage_repository.py#L339) (Zeile 339)
- [test_run_records_its_admission_day_and_account_period](../../tests/test_run_usage_repository.py#L353) (Zeile 353)
- [test_missing_reservation_cannot_be_consumed_or_released](../../tests/test_run_usage_repository.py#L366) (Zeile 366)
- [test_request_fingerprint_binds_reused_key](../../tests/test_run_usage_repository.py#L374) (Zeile 374)
- [test_authorize_admits_a_legacy_run_and_reads_no_account_for_prepared_runs](../../tests/test_run_usage_repository.py#L384) (Zeile 384)
- [test_parallel_operation_claim_allows_exactly_one_winner](../../tests/test_run_usage_repository.py#L403) (Zeile 403)
- [test_cross_operation_claims_are_independent_and_payload_bound](../../tests/test_run_usage_repository.py#L420) (Zeile 420)
- [test_cross_day_replay_cannot_claim_provider_work](../../tests/test_run_usage_repository.py#L436) (Zeile 436)

</details>

<a id="test-security-controls-py"></a>

## test_security_controls.py

**Quelle:** [tests/test_security_controls.py](../../tests/test_security_controls.py) · **Bereiche:** Authentifizierung, Sicherheit.

**Ebene:** API-Verträge; ein Test mit main.app.

**Lauf:** 5 bestanden.

**Geprüftes Verhalten:** /check_keys verlangt Login und mindestens einen OpenRouter-Key; Own-Key-Modellrequest ohne Login liefert 401; der echte globale Validation-Handler bleibt bei Pydantic-ValueError auf 422 und entfernt ctx sowie eingesendeten Wert, lässt nur loc/type/msg zu. Aktualisierung 02.10.2026: Der registrierte main-HTTPException-Handler bewahrt Retry-After bei 429/503 und WWW-Authenticate bei 401 samt Fehlerbody; synthetische Routen, keine volle Auth-/Limiterkette.

**Grenzen und Doubles:** Eigene FastAPI-App mit Router und Limiterzustand in den ersten drei Tests; der Limiter wird dort nicht deaktiviert. Der letzte Test verwendet main.app für den Validation-Error-Umschlag. Keine vollständige Prüfung von main-Middleware/HTTPException-Headern oder Firebase-Authentifizierung.

**Prüfauftrag für den Folgeaudit:** Weitere Fehler- und Loggingpfade für sensible Eingaben sowie positive Schlüsselprüfung separat abgleichen.

**Direkte Codeverweise:** [app/api/routers/chat.py](../../app/api/routers/chat.py), [app/api/routers/pages.py](../../app/api/routers/pages.py), [app/core/rate_limit.py](../../app/core/rate_limit.py), [main.py](../../main.py).

<details>
<summary>5 Testdefinitionen und ihre Quellstellen</summary>

- [test_check_keys_requires_verified_login](../../tests/test_security_controls.py#L18) (Zeile 18)
- [test_check_keys_requires_at_least_one_key_after_auth](../../tests/test_security_controls.py#L26) (Zeile 26)
- [test_user_api_key_requests_require_login](../../tests/test_security_controls.py#L40) (Zeile 40)
- [test_validation_errors_stay_422_and_never_echo_the_submitted_value](../../tests/test_security_controls.py#L57) (Zeile 57)
- [test_registered_http_exception_handler_preserves_headers](../../tests/test_security_controls.py#L123) (Zeile 123)

</details>

<a id="test-seo-basics-py"></a>

## test_seo_basics.py

**Quelle:** [tests/test_seo_basics.py](../../tests/test_seo_basics.py) · **Bereiche:** SEO, Öffentliche Seiten.

**Ebene:** Pages-Routen und Template-Quelltextverträge.

**Lauf:** 13 bestanden.

**Geprüftes Verhalten:** Landing trotz Session erreichbar, App-Home-Link/noindex, Robots und Sitemap-Index/-Pages mit vorgesehenen indexierbaren Routen, Canonical/OG/Twitter/JSON-LD/OG-Datei und Hub-/Footer-Verlinkung.

**Grenzen und Doubles:** Metadaten überwiegend Sourceprüfungen; kein Suchmaschinen-Crawl oder tatsächlicher Indexierungsnachweis.

**Prüfauftrag für den Folgeaudit:** Gerenderte dynamische Metadaten/Canonical-Konsistenz und Robotsheader über alle Seiten abgleichen.

**Direkte Codeverweise:** [app/api/routers/pages.py](../../app/api/routers/pages.py).

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

**Lauf:** 39 bestanden.

**Geprüftes Verhalten:** Sichere GSC-Konfig/Dateialias/Readonly-Credentials, finale paginierte 90-Tage-Erfassung mit Delay/Chunks/Idempotenz und Truncation ohne falsche Nullen. Statusklassifikation, Admingates, erreichbare Alerts/Controls, begrenzte Dossiers, konservative Noindex-Safeguards/Graceperiod, Query-Privacyfilter, append-only Journal, strikter optionaler Content-Judge ohne Guard-Bypass. Aktualisierung 02.10.2026: Collectorlock wird auch nach frühem Init-/Clockfehler freigegeben; über aufeinanderfolgende Reviews werden alle Seiten rotiert.

**Grenzen und Doubles:** Keine echte Search-Console-Abfrage oder LLM-Bewertung. Admin-UI überwiegend statisch; synthetische Kennzahlen ersetzen reale Portfolioqualität.

**Prüfauftrag für den Folgeaudit:** Datenlücken/Quota-/APIänderungen und gerenderte Admin-Aktionen mit JS-Alerts/Weeklyreview abgleichen.

**Direkte Codeverweise:** [app/api/routers/admin.py](../../app/api/routers/admin.py), [app/services/google_search_console.py](../../app/services/google_search_console.py), [app/services/seo_data.py](../../app/services/seo_data.py), [app/services/seo_dossier.py](../../app/services/seo_dossier.py), [app/services/seo_recommendation.py](../../app/services/seo_recommendation.py), [app/services/seo_repository.py](../../app/services/seo_repository.py), [app/services/seo_weekly_review.py](../../app/services/seo_weekly_review.py), [main.py](../../main.py).

<details>
<summary>39 Testdefinitionen und ihre Quellstellen</summary>

- [test_configuration_errors_are_safe](../../tests/test_seo_data.py#L118) (Zeile 118)
- [test_service_account_file_variable_is_accepted_as_an_alias](../../tests/test_seo_data.py#L145) (Zeile 145)
- [test_service_account_variable_is_a_relative_repository_root_path](../../tests/test_seo_data.py#L163) (Zeile 163)
- [test_client_builds_credentials_with_readonly_scope_only](../../tests/test_seo_data.py#L177) (Zeile 177)
- [test_successful_collection_persists_90_days_with_origin_and_source](../../tests/test_seo_data.py#L197) (Zeile 197)
- [test_collection_is_idempotent_and_skips_already_finalized_days](../../tests/test_seo_data.py#L226) (Zeile 226)
- [test_truncated_ranges_do_not_persist_omitted_rows_as_zeroes](../../tests/test_seo_data.py#L251) (Zeile 251)
- [test_date_boundaries_exclude_the_three_day_delay_and_chunk_requests](../../tests/test_seo_data.py#L277) (Zeile 277)
- [test_not_configured_collection_records_safe_result](../../tests/test_seo_data.py#L292) (Zeile 292)
- [test_collector_lock_is_released_when_run_creation_fails](../../tests/test_seo_data.py#L322) (Zeile 322)
- [test_collector_lock_is_released_when_clock_or_window_fails](../../tests/test_seo_data.py#L348) (Zeile 348)
- [test_running_collector_still_blocks_a_second_one_and_recovers_afterwards](../../tests/test_seo_data.py#L372) (Zeile 372)
- [test_search_console_http_pagination_and_final_data_state](../../tests/test_seo_data.py#L409) (Zeile 409)
- [test_connection_check_returns_only_sanitized_status](../../tests/test_seo_data.py#L442) (Zeile 442)
- [test_connection_failure_never_exposes_google_body_or_credential_path](../../tests/test_seo_data.py#L475) (Zeile 475)
- [test_status_classification_rules](../../tests/test_seo_data.py#L501) (Zeile 501)
- [test_insufficient_data_counts_rows_not_traffic](../../tests/test_seo_data.py#L515) (Zeile 515)
- [test_visibility_weights_one_click_as_twenty_impressions](../../tests/test_seo_data.py#L526) (Zeile 526)
- [test_small_portfolio_reaches_opportunity_on_impressions_alone](../../tests/test_seo_data.py#L538) (Zeile 538)
- [test_admin_endpoints_require_admin](../../tests/test_seo_data.py#L545) (Zeile 545)
- [test_admin_seo_collect_action_is_hidden_until_admin_request_succeeds](../../tests/test_seo_data.py#L640) (Zeile 640)
- [test_admin_seo_tab_keeps_every_control_reachable_after_the_layout_rework](../../tests/test_seo_data.py#L670) (Zeile 670)
- [test_admin_seo_alert_strip_covers_every_state_that_can_silence_the_pipeline](../../tests/test_seo_data.py#L712) (Zeile 712)
- [test_static_dossier_contains_bounded_content_and_freshness_fields](../../tests/test_seo_data.py#L762) (Zeile 762)
- [test_share_dossier_keeps_only_a_bounded_representation](../../tests/test_seo_data.py#L774) (Zeile 774)
- [test_noindex_candidate_requires_every_safeguard_not_just_invisible_status](../../tests/test_seo_data.py#L816) (Zeile 816)
- [test_noindex_candidate_rejects_missing_final_days_and_positive_development](../../tests/test_seo_data.py#L852) (Zeile 852)
- [test_deterministic_recommendation_maps_existing_status_classes](../../tests/test_seo_data.py#L874) (Zeile 874)
- [test_distinctive_pages_get_a_longer_grace_period_before_retirement](../../tests/test_seo_data.py#L906) (Zeile 906)
- [test_pages_without_a_consensus_signal_keep_the_plain_60_day_rule](../../tests/test_seo_data.py#L933) (Zeile 933)
- [test_share_dossier_reports_the_consensus_signal](../../tests/test_seo_data.py#L946) (Zeile 946)
- [test_query_snapshot_marks_privacy_filtered_rows_as_partial](../../tests/test_seo_data.py#L978) (Zeile 978)
- [test_search_console_query_request_is_final_bounded_and_page_filtered](../../tests/test_seo_data.py#L1005) (Zeile 1005)
- [test_journal_generation_is_idempotent_and_append_only](../../tests/test_seo_data.py#L1039) (Zeile 1039)
- [test_weekly_review_can_generate_for_historically_captured_inactive_pages](../../tests/test_seo_data.py#L1063) (Zeile 1063)
- [test_llm_json_validation_is_strict_and_cannot_bypass_noindex_safeguards](../../tests/test_seo_data.py#L1083) (Zeile 1083)
- [test_optional_content_judge_uses_bounded_prompt_and_structured_schema](../../tests/test_seo_data.py#L1116) (Zeile 1116)
- [test_content_judge_is_not_called_for_winner_status](../../tests/test_seo_data.py#L1155) (Zeile 1155)
- [test_weekly_review_rotation_covers_every_page_over_consecutive_runs](../../tests/test_seo_data.py#L1181) (Zeile 1181)

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

<a id="test-seo-repository-py"></a>

## test_seo_repository.py

**Quelle:** [tests/test_seo_repository.py](../../tests/test_seo_repository.py) · **Bereiche:** SEO.

**Ebene:** Echter Repositoryadapter mit kontrollierten SDK-Snapshots.

**Lauf:** 3 bestanden.

**Geprüftes Verhalten:** 615 Referenzen werden in 400/215 gelesen; ungeordnete/fehlende Snapshots und falsche Payloadidentität werden anhand des Dokumentpfads zugeordnet. Latest-/Judgmentquery und Datumsformen begrenzt, fehlende Messung bleibt fehlend.

**Grenzen und Doubles:** SDK-Double; ergänzende native BatchGet-/Queryfälle separat.

**Prüfauftrag für den Folgeaudit:** Die benannten Betriebs- und Testgrenzen bei künftigen Änderungen erneut prüfen; konkrete Paketnachweise stehen im Produktabgleich.

**Direkte Codeverweise:** [app/services/seo_repository.py](../../app/services/seo_repository.py).

<details>
<summary>3 Testdefinitionen und ihre Quellstellen</summary>

- [test_batch_get_binds_document_identity_and_dates_not_position_or_payload](../../tests/test_seo_repository.py#L9) (Zeile 9)
- [test_latest_and_judgment_query_shapes_bound_reads_and_return_document_ids](../../tests/test_seo_repository.py#L36) (Zeile 36)
- [test_fallback_dates_are_ordered_with_naive_aware_and_missing_values](../../tests/test_seo_repository.py#L84) (Zeile 84)

</details>

<a id="test-seo-weekly-review-py"></a>

## test_seo_weekly_review.py

**Quelle:** [tests/test_seo_weekly_review.py](../../tests/test_seo_weekly_review.py) · **Bereiche:** Publisher, SEO, Watch.

**Ebene:** Review-Service mit Repository-/Judge-/Action-Doubles.

**Lauf:** 20 bestanden.

**Geprüftes Verhalten:** Persistente Lease, 7-Tage-Default und konfigurierte lokale Uhrzeit, höchstens ein Portfolio-Judge, 100 Seiten im begrenzten Prompt und explizite Auslassung erst nach Detailreduktion. Terminale Notifications/Collection-Failure, keine doppelten Metricscans, Evidenzgate für Briefänderung, History/Statusdelta und deterministische Empfehlungen. Getrennte Watch-/Index-Aktionen mit Teilergebnissen, kein Delete bei apply-all, Publisherlineage, manuelle Entscheidung und konfliktgeprüfte Briefannahme. Der aktuelle Diff passt Fixtures, Payloads oder Bezeichnungen an; die unten neu extrahierten Definitionen und Assertionstellen sind maßgeblich.

**Grenzen und Doubles:** DB, GSC, Judge und Aktionen ersetzt; keine reale Index-/Watch-/Delete-Ausführung und kein Mehrprozesslease.

**Prüfauftrag für den Folgeaudit:** Konkurrierende Review-/Adminänderungen sowie Fehler nach Teilaktionen mit Persistenz-/APIfällen abgleichen.

**Direkte Codeverweise:** [app/services/seo_weekly_review.py](../../app/services/seo_weekly_review.py).

<details>
<summary>20 Testdefinitionen und ihre Quellstellen</summary>

- [test_default_interval_is_seven_days_and_lease_is_persistent](../../tests/test_seo_weekly_review.py#L81) (Zeile 81)
- [test_weekly_schedule_uses_configured_local_time](../../tests/test_seo_weekly_review.py#L92) (Zeile 92)
- [test_review_uses_at_most_one_portfolio_judge_call](../../tests/test_seo_weekly_review.py#L181) (Zeile 181)
- [test_a_growing_portfolio_still_fits_into_one_judge_prompt](../../tests/test_seo_weekly_review.py#L214) (Zeile 214)
- [test_judge_prompt_gives_up_detail_before_it_gives_up_pages](../../tests/test_seo_weekly_review.py#L225) (Zeile 225)
- [test_portfolio_judge_defaults_to_gpt_5_6_terra](../../tests/test_seo_weekly_review.py#L251) (Zeile 251)
- [test_portfolio_judge_sends_terra_with_medium_reasoning](../../tests/test_seo_weekly_review.py#L259) (Zeile 259)
- [test_every_terminal_review_attempts_telegram_notification](../../tests/test_seo_weekly_review.py#L284) (Zeile 284)
- [test_review_reuses_overview_context_without_second_metric_scan](../../tests/test_seo_weekly_review.py#L300) (Zeile 300)
- [test_failed_collection_never_calls_portfolio_judge](../../tests/test_seo_weekly_review.py#L353) (Zeile 353)
- [test_mature_portfolio_can_persist_optional_topic_brief_suggestion](../../tests/test_seo_weekly_review.py#L361) (Zeile 361)
- [test_young_portfolio_keeps_the_topic_brief_suggestion_but_cannot_apply_it](../../tests/test_seo_weekly_review.py#L385) (Zeile 385)
- [test_history_exposes_findings_judge_failure_and_status_delta](../../tests/test_seo_weekly_review.py#L410) (Zeile 410)
- [test_deterministic_recommendations_are_grouped_without_llm_override](../../tests/test_seo_weekly_review.py#L454) (Zeile 454)
- [test_manual_improvement_gets_snapshot_decision_template](../../tests/test_seo_weekly_review.py#L467) (Zeile 467)
- [test_pause_and_resume_watch_never_change_indexing](../../tests/test_seo_weekly_review.py#L534) (Zeile 534)
- [test_noindex_only_leaves_watch_and_combined_reports_both_steps](../../tests/test_seo_weekly_review.py#L548) (Zeile 548)
- [test_apply_all_never_includes_delete_and_delete_requires_publisher_lineage](../../tests/test_seo_weekly_review.py#L575) (Zeile 575)
- [test_topic_brief_accept_preserves_other_config_and_detects_manual_change](../../tests/test_seo_weekly_review.py#L593) (Zeile 593)
- [test_editorial_decision_and_topic_brief_rejection_are_persisted](../../tests/test_seo_weekly_review.py#L611) (Zeile 611)

</details>

<a id="test-share-feature-py"></a>

## test_share_feature.py

**Quelle:** [tests/test_share_feature.py](../../tests/test_share_feature.py) · **Bereiche:** Authentifizierung, Persistenz, SEO, Watch, Öffentliche Freigaben.

**Ebene:** Große Unit-/Service-/Router-/SSR-Suite mit FakeDb und lokalen Cachethreads.

**Lauf:** 156 bestanden.

**Geprüftes Verhalten:** 151 Definitionen: Slug/IDs, Allowlist/Caps/Quellen/Modelle/Judge/Resolution, Pending-Owner/TTL/Indexeligibility, sichere Markdown-/Math-/Citationausgabe. Idempotente public/private Veröffentlichung mit Backlink und Sourcejob-Retention, Quota/Tombstones, Revoke/Report/Moderation/Harddelete/Cleanup. Owner/Admin-API und Indexrequests, Related-/Sharecache, Canonical/Sitemap/Hub/OG; aktuelle/historische Watch-Snapshots samt Quellen/Labels/Zeit/fehlenden Scores bleiben getrennt. Aktualisierung 02.10.2026: Anonyme Reports markieren Review statt selbst noindex zu setzen. Listen filtern/ordnen vor Limit und paginieren; Indexaufbau besitzt Fallback. Revocation wird in einem zweiten Worker innerhalb des Cachevertrags sichtbar.

**Grenzen und Doubles:** Transaktions- und Querverweise nutzen FakeDb; Router patchen teils ganze Services. SVG/HTML wird textuell geprüft, OG nur PNG-Signatur/Status. ID-Stichprobe mit 500 Werten beweist keine kryptographische Entropie. Hubfehler wird aktuell als leere 200-Seite dargestellt.

**Prüfauftrag für den Folgeaudit:** Atomizität/Retention unter echter Konkurrenz, öffentliche Cacheinvalidierung nach Revoke und Browser-XSS/Rendering separat abgleichen.

**Direkte Codeverweise:** [app/api/routers/admin.py](../../app/api/routers/admin.py), [app/api/routers/share.py](../../app/api/routers/share.py), [app/core/config.py](../../app/core/config.py), [app/core/rate_limit.py](../../app/core/rate_limit.py), [app/services/public_markdown.py](../../app/services/public_markdown.py), [app/services/share_snapshots.py](../../app/services/share_snapshots.py).

<details>
<summary>156 Testdefinitionen und ihre Quellstellen</summary>

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
- [ModerationAndCleanupTests::test_repeated_anonymous_reports_flag_review_but_never_deindex](../../tests/test_share_feature.py#L1048) (Zeile 1048)
- [ModerationAndCleanupTests::test_reports_below_threshold_keep_indexed](../../tests/test_share_feature.py#L1068) (Zeile 1068)
- [ModerationAndCleanupTests::test_admin_list_prioritizes_review_and_reports](../../tests/test_share_feature.py#L1075) (Zeile 1075)
- [ModerationAndCleanupTests::test_reported_share_beyond_the_first_window_is_found_by_paging](../../tests/test_share_feature.py#L1089) (Zeile 1089)
- [ModerationAndCleanupTests::test_bounded_share_lists_make_truncation_visible_in_the_ui](../../tests/test_share_feature.py#L1121) (Zeile 1121)
- [ModerationAndCleanupTests::test_owner_list_falls_back_to_in_memory_order_while_the_index_builds](../../tests/test_share_feature.py#L1134) (Zeile 1134)
- [ModerationAndCleanupTests::test_owner_list_is_newest_first_with_a_continuation_contract](../../tests/test_share_feature.py#L1158) (Zeile 1158)
- [ModerationAndCleanupTests::test_cleanup_revoked_shares_after_30_days](../../tests/test_share_feature.py#L1174) (Zeile 1174)
- [ModerationAndCleanupTests::test_cleanup_revoked_shares_drains_more_than_one_page](../../tests/test_share_feature.py#L1188) (Zeile 1188)
- [ModerationAndCleanupTests::test_find_canonical_share_prefers_oldest_indexed](../../tests/test_share_feature.py#L1208) (Zeile 1208)
- [ModerationAndCleanupTests::test_list_indexed_share_urls_filters](../../tests/test_share_feature.py#L1224) (Zeile 1224)
- [ModerationAndCleanupTests::test_list_hub_shares_filters_and_enriches](../../tests/test_share_feature.py#L1234) (Zeile 1234)
- [ModerationAndCleanupTests::test_list_related_shares_only_indexed_active_and_excludes_self](../../tests/test_share_feature.py#L1265) (Zeile 1265)
- [ModerationAndCleanupTests::test_list_related_shares_ranks_by_token_overlap](../../tests/test_share_feature.py#L1282) (Zeile 1282)
- [ModerationAndCleanupTests::test_related_candidate_pool_serves_different_pages_and_arguments](../../tests/test_share_feature.py#L1299) (Zeile 1299)
- [ModerationAndCleanupTests::test_related_pool_expiry_and_explicit_database_bypass](../../tests/test_share_feature.py#L1321) (Zeile 1321)
- [ModerationAndCleanupTests::test_related_pool_coalesces_concurrent_misses](../../tests/test_share_feature.py#L1337) (Zeile 1337)
- [ModerationAndCleanupTests::test_related_invalidation_during_fill_cannot_leave_stale_pool](../../tests/test_share_feature.py#L1346) (Zeile 1346)
- [ModerationAndCleanupTests::test_revocation_reaches_a_second_worker_within_the_promised_delay](../../tests/test_share_feature.py#L1376) (Zeile 1376)
- [ModerationAndCleanupTests::test_share_cache_returns_cached_until_invalidated](../../tests/test_share_feature.py#L1408) (Zeile 1408)
- [ModerationAndCleanupTests::test_revoke_invalidates_cache](../../tests/test_share_feature.py#L1423) (Zeile 1423)
- [SharePageRouteTests::test_invalid_id_renders_404_with_noindex](../../tests/test_share_feature.py#L1464) (Zeile 1464)
- [SharePageRouteTests::test_unknown_id_renders_404](../../tests/test_share_feature.py#L1469) (Zeile 1469)
- [SharePageRouteTests::test_revoked_share_renders_410](../../tests/test_share_feature.py#L1474) (Zeile 1474)
- [SharePageRouteTests::test_wrong_slug_redirects_to_canonical](../../tests/test_share_feature.py#L1481) (Zeile 1481)
- [SharePageRouteTests::test_active_share_renders_content_with_noindex](../../tests/test_share_feature.py#L1488) (Zeile 1488)
- [SharePageRouteTests::test_active_share_preserves_latex_and_loads_katex_renderer](../../tests/test_share_feature.py#L1501) (Zeile 1501)
- [SharePageRouteTests::test_private_share_requires_owner_and_is_never_publicly_cached](../../tests/test_share_feature.py#L1515) (Zeile 1515)
- [SharePageRouteTests::test_differences_cards_and_toggle_rendered](../../tests/test_share_feature.py#L1534) (Zeile 1534)
- [SharePageRouteTests::test_differences_fallback_text_rendered](../../tests/test_share_feature.py#L1560) (Zeile 1560)
- [SharePageRouteTests::test_structured_empty_differences_do_not_render_legacy_credibility_text](../../tests/test_share_feature.py#L1568) (Zeile 1568)
- [SharePageRouteTests::test_related_questions_section_rendered](../../tests/test_share_feature.py#L1593) (Zeile 1593)
- [SharePageRouteTests::test_related_questions_section_hidden_when_empty](../../tests/test_share_feature.py#L1607) (Zeile 1607)
- [SharePageRouteTests::test_watch_history_renders_inline_svg_and_events](../../tests/test_share_feature.py#L1614) (Zeile 1614)
- [SharePageRouteTests::test_watch_history_renders_position_map_and_direction_shift](../../tests/test_share_feature.py#L1640) (Zeile 1640)
- [SharePageRouteTests::test_active_watch_page_shows_run_metadata_before_history_exists](../../tests/test_share_feature.py#L1678) (Zeile 1678)
- [SharePageRouteTests::test_a_rephrased_check_reads_as_stable_on_the_watch_page](../../tests/test_share_feature.py#L1697) (Zeile 1697)
- [SharePageRouteTests::test_watch_page_renders_latest_version_without_mutating_shared_baseline](../../tests/test_share_feature.py#L1740) (Zeile 1740)
- [SharePageRouteTests::test_watch_historical_version_uses_only_its_full_snapshot_metadata](../../tests/test_share_feature.py#L1805) (Zeile 1805)
- [SharePageRouteTests::test_missing_current_full_version_falls_back_consistently_to_original](../../tests/test_share_feature.py#L1846) (Zeile 1846)
- [SharePageRouteTests::test_legacy_compact_history_without_version_pointer_keeps_original_snapshot](../../tests/test_share_feature.py#L1872) (Zeile 1872)
- [SharePageRouteTests::test_watch_page_shows_selected_local_run_time](../../tests/test_share_feature.py#L1894) (Zeile 1894)
- [SharePageRouteTests::test_rendered_citation_contains_canonical_url](../../tests/test_share_feature.py#L1907) (Zeile 1907)
- [SharePageRouteTests::test_noindex_page_has_seo_tags_and_cache_control](../../tests/test_share_feature.py#L1917) (Zeile 1917)
- [SharePageRouteTests::test_indexed_page_gets_index_follow](../../tests/test_share_feature.py#L1935) (Zeile 1935)
- [SharePageRouteTests::test_noindex_duplicate_points_canonical_to_indexed_share](../../tests/test_share_feature.py#L1945) (Zeile 1945)
- [SharePageRouteTests::test_sitemap_shares_lists_only_indexed](../../tests/test_share_feature.py#L1961) (Zeile 1961)
- [SharePageRouteTests::test_questions_hub_lists_indexed_shares](../../tests/test_share_feature.py#L1971) (Zeile 1971)
- [SharePageRouteTests::test_questions_hub_survives_backend_failure](../../tests/test_share_feature.py#L1993) (Zeile 1993)
- [SharePageRouteTests::test_report_endpoint_maps_share_errors](../../tests/test_share_feature.py#L2000) (Zeile 2000)
- [ShareApiRouteTests::test_my_shares_requires_auth](../../tests/test_share_feature.py#L2031) (Zeile 2031)
- [ShareApiRouteTests::test_my_shares_returns_owner_list](../../tests/test_share_feature.py#L2036) (Zeile 2036)
- [ShareApiRouteTests::test_delete_share_revokes_for_owner](../../tests/test_share_feature.py#L2053) (Zeile 2053)
- [ShareApiRouteTests::test_delete_share_maps_share_errors](../../tests/test_share_feature.py#L2062) (Zeile 2062)
- [AdminShareRouteTests::test_list_requires_admin](../../tests/test_share_feature.py#L2088) (Zeile 2088)
- [AdminShareRouteTests::test_list_passes_filter](../../tests/test_share_feature.py#L2094) (Zeile 2094)
- [AdminShareRouteTests::test_moderate_forwards_action_and_indexed](../../tests/test_share_feature.py#L2110) (Zeile 2110)
- [AdminShareRouteTests::test_moderate_validates_indexed_type_and_maps_errors](../../tests/test_share_feature.py#L2129) (Zeile 2129)
- [AdminShareRouteTests::test_delete_requires_admin_and_hard_deletes](../../tests/test_share_feature.py#L2144) (Zeile 2144)
- [AdminShareRouteTests::test_delete_maps_missing_share](../../tests/test_share_feature.py#L2165) (Zeile 2165)
- [IndexingRequestTests::test_owner_can_request_and_withdraw](../../tests/test_share_feature.py#L2189) (Zeile 2189)
- [IndexingRequestTests::test_indexing_request_is_fenced_during_account_deletion](../../tests/test_share_feature.py#L2203) (Zeile 2203)
- [IndexingRequestTests::test_only_owner_public_active_can_request](../../tests/test_share_feature.py#L2213) (Zeile 2213)
- [IndexingRequestTests::test_already_indexed_returns_state_without_new_request](../../tests/test_share_feature.py#L2224) (Zeile 2224)
- [IndexingRequestTests::test_moderation_clears_open_request](../../tests/test_share_feature.py#L2231) (Zeile 2231)
- [IndexingRequestTests::test_indexing_request_route_requires_auth_and_owner](../../tests/test_share_feature.py#L2238) (Zeile 2238)
- [IndexingRequestTests::test_sitemap_lastmod_prefers_last_watch_run](../../tests/test_share_feature.py#L2254) (Zeile 2254)
- [ApiRunPublishingServiceTests::test_api_run_publication_is_idempotent_and_skips_pending_results](../../tests/test_share_feature.py#L2302) (Zeile 2302)
- [ApiRunPublishingServiceTests::test_account_deletion_tombstone_fences_api_run_publication](../../tests/test_share_feature.py#L2321) (Zeile 2321)
- [ApiRunPublishingServiceTests::test_only_publisher_mode_api_runs_receive_publisher_lineage](../../tests/test_share_feature.py#L2336) (Zeile 2336)
- [ApiRunPublishingServiceTests::test_api_run_requires_ownership_and_success](../../tests/test_share_feature.py#L2351) (Zeile 2351)
- [ApiRunPublishingServiceTests::test_api_indexing_enforces_quality_dedup_and_audit](../../tests/test_share_feature.py#L2364) (Zeile 2364)
- [ApiRunPublishingServiceTests::test_api_indexing_is_fenced_during_account_deletion](../../tests/test_share_feature.py#L2418) (Zeile 2418)
- [ShareSeoEnhancementTests::test_scoreboard_teaser_and_data_led_description](../../tests/test_share_feature.py#L2492) (Zeile 2492)
- [ShareSeoEnhancementTests::test_date_modified_uses_authoritative_display_version](../../tests/test_share_feature.py#L2506) (Zeile 2506)
- [ShareSeoEnhancementTests::test_citations_skip_redirect_urls_that_point_nowhere_readable](../../tests/test_share_feature.py#L2515) (Zeile 2515)
- [ShareSeoEnhancementTests::test_tracked_page_shows_its_history_as_a_fact_not_only_as_a_chart](../../tests/test_share_feature.py#L2529) (Zeile 2529)
- [ShareSeoEnhancementTests::test_unscored_watch_check_keeps_its_change_and_version_link](../../tests/test_share_feature.py#L2539) (Zeile 2539)
- [ShareSeoEnhancementTests::test_historical_version_does_not_claim_the_full_tracking_record](../../tests/test_share_feature.py#L2563) (Zeile 2563)
- [ShareSeoEnhancementTests::test_follow_form_only_on_active_public_watch_pages](../../tests/test_share_feature.py#L2581) (Zeile 2581)
- [ShareSeoEnhancementTests::test_og_card_route_and_meta](../../tests/test_share_feature.py#L2597) (Zeile 2597)
- [ShareSeoEnhancementTests::test_og_card_404_for_private_pages](../../tests/test_share_feature.py#L2611) (Zeile 2611)

</details>

<a id="test-share-http-contract-py"></a>

## test_share_http_contract.py

**Quelle:** [tests/test_share_http_contract.py](../../tests/test_share_http_contract.py) · **Bereiche:** Shares.

**Ebene:** Registrierte main.app mit echten Middleware-, Auth-/Owner- und Serviceguards.

**Lauf:** 7 bestanden.

**Geprüftes Verhalten:** App-Share-POST nutzt autoritatives Pendingergebnis statt gefälschter Inhalte/Owner/Visibility, prüft Quote/Ablauf und Transaktionsfehler, bleibt idempotent. Antwort und DB stimmen überein. OG-Route nutzt gespeicherte Werte; private/widerrufene Shares bleiben verborgen.

**Grenzen und Doubles:** Firebase-SDK-Authentifizierung und DB ersetzt; externe Modell-, Mail- und Telegramgrenzen kontrolliert. Kein Live-OAuth oder produktiver Versand.

**Prüfauftrag für den Folgeaudit:** Die benannten Betriebs- und Testgrenzen bei künftigen Änderungen erneut prüfen; konkrete Paketnachweise stehen im Produktabgleich.

**Direkte Codeverweise:** [app/services/og_image.py](../../app/services/og_image.py), [app/services/share_snapshots.py](../../app/services/share_snapshots.py), [app/services/watch_service.py](../../app/services/watch_service.py).

<details>
<summary>4 Testdefinitionen und ihre Quellstellen</summary>

- [test_app_share_publishes_authoritative_content_and_retry_does_not_charge_twice](../../tests/test_share_http_contract.py#L36) (Zeile 36)
- [test_app_share_rejects_unauthorized_or_missing_result](../../tests/test_share_http_contract.py#L73) (Zeile 73)
- [test_app_share_expiry_quota_and_transaction_failure_never_publish](../../tests/test_share_http_contract.py#L91) (Zeile 91)
- [test_og_http_route_renders_stored_question_score_and_private_revocation](../../tests/test_share_http_contract.py#L123) (Zeile 123)

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

**Geprüftes Verhalten:** Watch/Topic/API behalten Konsens/Differences/Quellen, starten aber keine Sourceprüfung. Nicht-Chat-Admission stoppt vor Plan/Write; alte Hintergrundjobs werden ohne Credentials/paid work cancelled; historische Watchreads entfernen Sourceprüfstatus ohne restliche Daten zu verlieren. Der aktuelle Diff passt Fixtures, Payloads oder Bezeichnungen an; die unten neu extrahierten Definitionen und Assertionstellen sind maßgeblich.

**Grenzen und Doubles:** Mock-LLM, FakeDb und verbotene Funktionsdoubles; kein tatsächlicher Schedulerstart.

**Prüfauftrag für den Folgeaudit:** Alle später hinzukommenden Produktpfade auf dieselbe Chat-only-Regel prüfen.

**Direkte Codeverweise:** [app/services/api_consensus_runner.py](../../app/services/api_consensus_runner.py), [app/services/consensus_pipeline.py](../../app/services/consensus_pipeline.py), [app/services/share_snapshots.py](../../app/services/share_snapshots.py), [app/services/source_check_jobs.py](../../app/services/source_check_jobs.py), [app/services/source_check_repository.py](../../app/services/source_check_repository.py), [app/services/source_documents.py](../../app/services/source_documents.py), [app/services/source_verification.py](../../app/services/source_verification.py), [app/services/topic_pipeline.py](../../app/services/topic_pipeline.py), [app/services/watch_scheduler.py](../../app/services/watch_scheduler.py).

**Direkte Testhelfer:** [tests/test_source_check_repository.py](../../tests/test_source_check_repository.py).

<details>
<summary>5 Testdefinitionen und ihre Quellstellen</summary>

- [test_product_runs_keep_consensus_and_differences_without_source_work](../../tests/test_source_check_scope.py#L20) (Zeile 20)
- [test_neutral_analysis_does_not_emit_disabled_or_failed_chat_status](../../tests/test_source_check_scope.py#L52) (Zeile 52)
- [test_non_chat_admission_stops_before_planning_or_persistence](../../tests/test_source_check_scope.py#L67) (Zeile 67)
- [test_preexisting_background_jobs_are_cancelled_without_plan_or_paid_work](../../tests/test_source_check_scope.py#L75) (Zeile 75)
- [test_historical_watch_read_preserves_answer_sources_and_stored_data](../../tests/test_source_check_scope.py#L91) (Zeile 91)

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

<a id="test-source-pills-ui-py"></a>

## test_source_pills_ui.py

**Quelle:** [tests/test_source_pills_ui.py](../../tests/test_source_pills_ui.py) · **Bereiche:** Quellen, Frontend.

**Ebene:** Statische JS-/CSS-Verträge.

**Lauf:** 3 bestanden.

**Geprüftes Verhalten:** Quellenpillen auf der Grundlinie, Ellipse, eigener Faviconproxy und gemeinsame Plaintext-/URL-Helfer für Copy.

**Grenzen und Doubles:** Stringprüfungen belegen weder tatsächliches Layout noch Fokus oder Netzwerkverhalten.

**Prüfauftrag für den Folgeaudit:** Die benannten Mock-/Integrationsgrenzen am realen Adapter prüfen; Zuordnung und offene Aufgaben stehen in der Produktmatrix.

**Direkte Codeverweise:** [static/css/shell.css](../../static/css/shell.css), [static/js/consensus-actions.js](../../static/js/consensus-actions.js), [static/js/sources.js](../../static/js/sources.js).

<details>
<summary>3 Testdefinitionen und ihre Quellstellen</summary>

- [test_source_pill_sits_on_the_baseline_not_raised](../../tests/test_source_pills_ui.py#L24) (Zeile 24)
- [test_source_pill_favicons_only_use_the_own_proxy](../../tests/test_source_pills_ui.py#L38) (Zeile 38)
- [test_copy_paths_read_pills_through_the_shared_helper](../../tests/test_source_pills_ui.py#L46) (Zeile 46)

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

<a id="test-static-delivery-py"></a>

## test_static_delivery.py

**Quelle:** [tests/test_static_delivery.py](../../tests/test_static_delivery.py) · **Bereiche:** Betrieb, Frontend-Build.

**Ebene:** ASGI-/TestClient-Middleware und echte lokale Assets.

**Lauf:** 8 bestanden.

**Geprüftes Verhalten:** Gehashtes dist ist immutable/gzip, ungehashte Assets revalidieren; HTML wird komprimiert, API-JSON und SSE nicht. SSE-Frames werden einzeln weitergereicht; main registriert die Middleware.

**Grenzen und Doubles:** Lokaler ASGI-Transport, keine Proxy-/CDN-/echte Socket-Pufferungsprüfung.

**Prüfauftrag für den Folgeaudit:** Die benannten Mock-/Integrationsgrenzen am realen Adapter prüfen; Zuordnung und offene Aufgaben stehen in der Produktmatrix.

**Direkte Codeverweise:** [app/core/static_delivery.py](../../app/core/static_delivery.py), [main.py](../../main.py), [static/js/agent-chat.js](../../static/js/agent-chat.js), [static/style.css](../../static/style.css).

<details>
<summary>8 Testdefinitionen und ihre Quellstellen</summary>

- [test_event_stream_is_never_gzip_encoded](../../tests/test_static_delivery.py#L39) (Zeile 39)
- [test_event_stream_frames_are_forwarded_one_by_one](../../tests/test_static_delivery.py#L49) (Zeile 49)
- [test_main_app_serves_dist_immutable_and_keeps_json_errors_uncompressed](../../tests/test_static_delivery.py#L74) (Zeile 74)
- [test_hashed_dist_file_is_immutable_and_gzip_encoded](../../tests/test_static_delivery.py#L89) (Zeile 89)
- [test_unhashed_static_file_keeps_revalidation](../../tests/test_static_delivery.py#L106) (Zeile 106)
- [test_html_is_compressed_but_api_json_is_not](../../tests/test_static_delivery.py#L114) (Zeile 114)
- [test_gzip_payload_round_trips](../../tests/test_static_delivery.py#L123) (Zeile 123)
- [test_hashed_dist_pattern](../../tests/test_static_delivery.py#L130) (Zeile 130)

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

**Lauf:** 31 bestanden.

**Geprüftes Verhalten:** Disconnect schließt Providerressource und stoppt nachfolgende Arbeit; parallele Streams behalten eigene Cancellation. SSE-Roundtrip/Firestorezeit, Delta/Final/Fehler/Contentblocks, OpenRouter-URLs und zero-width Citation-Deduplizierung, Reasoning-only Cutoff, ungültige Engines und begrenzte Konsens-Retries/Leerantwortfehler. Aktualisierung 02.10.2026: EOF nach Text bleibt interrupted, length wird token_limit, stop/done wird complete; Textstream gibt den Abschlusszustand gesondert weiter.

**Grenzen und Doubles:** ASGI-Response wird lokal ausgeführt; Upstream-HTTP gemockt. Kein echter Socket oder Reverseproxy; Keepalive-Timing nicht aus Namen/Importen ableiten.

**Prüfauftrag für den Folgeaudit:** Transportfragmentierung/Browser-Disconnect und Teilantwort-Retrypolitik gegen JS/Provider-Runtime abgleichen.

**Direkte Codeverweise:** [app/services/llm/citations.py](../../app/services/llm/citations.py), [app/services/llm/consensus_engine.py](../../app/services/llm/consensus_engine.py), [app/services/llm/provider_runtime.py](../../app/services/llm/provider_runtime.py), [app/services/llm/streaming.py](../../app/services/llm/streaming.py).

<details>
<summary>31 Testdefinitionen und ihre Quellstellen</summary>

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
- [OpenRouterStreamTests::test_delta_then_eof_is_interrupted_not_complete](../../tests/test_streaming.py#L463) (Zeile 463)
- [OpenRouterStreamTests::test_delta_then_length_is_token_limit_not_complete](../../tests/test_streaming.py#L470) (Zeile 470)
- [OpenRouterStreamTests::test_stop_and_done_are_complete](../../tests/test_streaming.py#L480) (Zeile 480)
- [OpenRouterStreamTests::test_text_stream_reports_its_completion_state](../../tests/test_streaming.py#L489) (Zeile 489)
- [ConsensusStreamTests::test_invalid_consensus_engine](../../tests/test_streaming.py#L503) (Zeile 503)
- [ConsensusStreamTests::test_differences_without_answers](../../tests/test_streaming.py#L513) (Zeile 513)
- [ConsensusStreamTests::test_invalid_differences_engine](../../tests/test_streaming.py#L523) (Zeile 523)
- [ConsensusStreamTests::test_invalid_engine_final_is_flagged_as_error](../../tests/test_streaming.py#L534) (Zeile 534)
- [ConsensusRetryTests::test_transient_failure_is_retried](../../tests/test_streaming.py#L558) (Zeile 558)
- [ConsensusRetryTests::test_persistent_failure_yields_error_final](../../tests/test_streaming.py#L574) (Zeile 574)
- [ConsensusRetryTests::test_empty_stream_counts_as_failure](../../tests/test_streaming.py#L584) (Zeile 584)
- [ConsensusErrorTextTests::test_error_and_empty_texts_are_detected](../../tests/test_streaming.py#L595) (Zeile 595)
- [ConsensusErrorTextTests::test_normal_answers_are_not_errors](../../tests/test_streaming.py#L602) (Zeile 602)

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

<a id="test-topic-public-http-py"></a>

## test_topic_public_http.py

**Quelle:** [tests/test_topic_public_http.py](../../tests/test_topic_public_http.py) · **Bereiche:** Topics.

**Ebene:** Registrierte main.app mit echten Middleware-, Auth-/Owner- und Serviceguards.

**Lauf:** 10 bestanden.

**Geprüftes Verhalten:** Hub/Sitemap unterscheiden aktiv, pausiert, noindex, archiviert und unveröffentlicht. Neutraler wiederholter Follow und tatsächlicher erzeugter E-Mail-Link führen durch Confirm/Unsubscribe; ungültige Tokens schreiben nicht, Titel bleibt escaped.

**Grenzen und Doubles:** Firebase-SDK-Authentifizierung und DB ersetzt; externe Modell-, Mail- und Telegramgrenzen kontrolliert. Kein Live-OAuth oder produktiver Versand.

**Prüfauftrag für den Folgeaudit:** Die benannten Betriebs- und Testgrenzen bei künftigen Änderungen erneut prüfen; konkrete Paketnachweise stehen im Produktabgleich.

**Direkte Codeverweise:** [app/services/mailer.py](../../app/services/mailer.py), [app/services/topics.py](../../app/services/topics.py), [app/services/watch_service.py](../../app/services/watch_service.py).

<details>
<summary>3 Testdefinitionen und ihre Quellstellen</summary>

- [test_hub_and_sitemap_distinguish_noindex_from_archive_or_unpublished](../../tests/test_topic_public_http.py#L34) (Zeile 34)
- [test_follow_neutral_response_confirmation_escaping_and_unsubscribe](../../tests/test_topic_public_http.py#L64) (Zeile 64)
- [test_topic_tokens_reject_without_writes](../../tests/test_topic_public_http.py#L109) (Zeile 109)

</details>

<a id="test-topics-feature-py"></a>

## test_topics_feature.py

**Quelle:** [tests/test_topics_feature.py](../../tests/test_topics_feature.py) · **Bereiche:** Benachrichtigungen, Persistenz, Quellenprüfung, SEO, Topics.

**Ebene:** Große Service-/Router-/SSR-Suite mit FakeFirestore; einzelner echter SDK-Queryaufbau mit RPC-Mock.

**Lauf:** 65 bestanden.

**Geprüftes Verhalten:** Begrenzte historische Reads inkl. Legacy-/Timestamp-/Count-Snapshot, unveränderliche Runversionen und Pointer-Atomizität/Stale-Claim. Archiv/Index/Slug-Rename/Reservierung, Quellenrollen/Canonicalisierung/100 Quellen/ID-Erhalt. Double-opt-in, Challenge-Atomizität, Delivery-Dedupe/Cleanup/Tombstones, Mockmodus ohne Publish; automatische Pipeline/Claimidentity-Fallback. Service-CRUD sowie Admin-Create/Run/Detail, öffentliche Historie/Finding/Claimledger/Positionmap und unscored/historische noindex-Seiten. Aktualisierung 02.10.2026: Strict-CSP ohne Inlinecode, ausgeschlossene Quellen werden entfernt statt umetikettiert, Primärquellenregeln und leere Evidenz. Alte Versionslinks bleiben jenseits von 100 Runs erreichbar; begrenzte Historie wird nicht als vollständig ausgegeben.

**Grenzen und Doubles:** Fachlogik/SSR real, DB/LLM/Mail ersetzt. SDKfall prüft RPC-Aufbau, nicht Dienstverhalten; Quellrollen sind URLheuristiken, keine inhaltliche Qualitätsprüfung. Adminauth im HTTP-Erfolgstest ersetzt; trotz Testnamen kein PUT, Adminlist/öffentliche Hub-/Sitemap-/Follow-/Confirm-/Unsubscribe-Adapter hier nicht ausgeführt (G-014/G-041).

**Prüfauftrag für den Folgeaudit:** Echte konkurrierende Slug-/Run-/Followertransaktionen und Browser-Historiennavigation abgleichen.

**Direkte Codeverweise:** [app/api/routers/pages.py](../../app/api/routers/pages.py), [app/api/routers/topics.py](../../app/api/routers/topics.py), [app/core/rate_limit.py](../../app/core/rate_limit.py), [app/services/account_deletion.py](../../app/services/account_deletion.py), [app/services/follow_challenges.py](../../app/services/follow_challenges.py), [app/services/mailer.py](../../app/services/mailer.py), [app/services/topic_pipeline.py](../../app/services/topic_pipeline.py), [app/services/topic_runner.py](../../app/services/topic_runner.py), [app/services/topics.py](../../app/services/topics.py), [static/js/public-theme.js](../../static/js/public-theme.js), [static/js/topic-page.js](../../static/js/topic-page.js).

<details>
<summary>52 Testdefinitionen und ihre Quellstellen</summary>

- [test_list_runs_bounds_long_histories_and_preserves_ascending_chronology](../../tests/test_topics_feature.py#L193) (Zeile 193)
- [test_list_runs_keeps_legacy_missing_dates_and_versions](../../tests/test_topics_feature.py#L204) (Zeile 204)
- [test_list_runs_short_complete_history_uses_count_instead_of_document_rescan](../../tests/test_topics_feature.py#L216) (Zeile 216)
- [test_list_runs_count_proof_uses_same_snapshot_during_deletion](../../tests/test_topics_feature.py#L226) (Zeile 226)
- [test_list_runs_rejects_invalid_counts_without_expensive_fallback](../../tests/test_topics_feature.py#L244) (Zeile 244)
- [test_list_runs_count_failure_does_not_fall_back_to_a_full_scan](../../tests/test_topics_feature.py#L252) (Zeile 252)
- [test_list_runs_sdk_count_is_unfiltered_and_shares_read_only_transaction](../../tests/test_topics_feature.py#L260) (Zeile 260)
- [test_list_runs_resolves_timestamp_boundary_by_version_and_document_id](../../tests/test_topics_feature.py#L292) (Zeile 292)
- [test_list_runs_ignores_missing_dates_when_newer_window_is_full](../../tests/test_topics_feature.py#L300) (Zeile 300)
- [test_list_runs_query_failure_is_not_hidden_by_a_full_scan](../../tests/test_topics_feature.py#L309) (Zeile 309)
- [test_list_runs_invalid_legacy_timestamp_uses_original_sorting](../../tests/test_topics_feature.py#L317) (Zeile 317)
- [test_topic_runs_are_immutable_and_keep_historical_editorial_state](../../tests/test_topics_feature.py#L375) (Zeile 375)
- [test_topic_run_and_latest_pointer_commit_or_fail_together](../../tests/test_topics_feature.py#L421) (Zeile 421)
- [test_stale_topic_claim_cannot_publish_or_mark_newer_claim_failed](../../tests/test_topics_feature.py#L439) (Zeile 439)
- [test_archived_topics_leave_public_discovery_and_reject_new_runs](../../tests/test_topics_feature.py#L469) (Zeile 469)
- [test_noindex_and_unpublished_topics_are_not_in_topic_sitemap](../../tests/test_topics_feature.py#L492) (Zeile 492)
- [test_slug_uniqueness_and_evidence_url_validation](../../tests/test_topics_feature.py#L516) (Zeile 516)
- [test_renamed_topic_keeps_its_runs_and_redirects_the_old_url](../../tests/test_topics_feature.py#L543) (Zeile 543)
- [test_a_retired_slug_cannot_be_claimed_and_can_be_taken_back](../../tests/test_topics_feature.py#L583) (Zeile 583)
- [test_evidence_sources_receive_specific_public_roles](../../tests/test_topics_feature.py#L617) (Zeile 617)
- [test_google_redirects_are_unwrapped_or_flagged_as_indirect](../../tests/test_topics_feature.py#L621) (Zeile 621)
- [test_automatic_evidence_orders_direct_sources_before_rumors](../../tests/test_topics_feature.py#L632) (Zeile 632)
- [test_topic_evidence_keeps_citation_ids_when_quality_sort_changes_order](../../tests/test_topics_feature.py#L641) (Zeile 641)
- [test_topic_evidence_preserves_more_than_eighty_sources_and_case_sensitive_paths](../../tests/test_topics_feature.py#L653) (Zeile 653)
- [test_topic_evidence_legacy_ids_skip_explicit_ids_and_conflicts_fail_explicitly](../../tests/test_topics_feature.py#L663) (Zeile 663)
- [test_topic_followers_use_separate_collection_and_double_opt_in](../../tests/test_topics_feature.py#L672) (Zeile 672)
- [test_topic_account_cleanup_invalidates_outstanding_confirm_link](../../tests/test_topics_feature.py#L702) (Zeile 702)
- [test_topic_confirm_consumes_challenge_atomically_with_follower_write](../../tests/test_topics_feature.py#L716) (Zeile 716)
- [test_topic_notification_delivery_is_deduplicated_and_multipart](../../tests/test_topics_feature.py#L745) (Zeile 745)
- [test_topic_delivery_claim_requires_a_live_topic_bound_follower](../../tests/test_topics_feature.py#L783) (Zeile 783)
- [test_topic_delivery_finish_does_not_recreate_a_cleaned_claim](../../tests/test_topics_feature.py#L798) (Zeile 798)
- [test_account_deletion_fences_claims_before_topic_delivery_cleanup](../../tests/test_topics_feature.py#L817) (Zeile 817)
- [test_topic_detail_page_carries_no_inline_script_for_its_strict_csp](../../tests/test_topics_feature.py#L834) (Zeile 834)
- [test_topic_templates_expose_timeline_evidence_follow_and_admin_controls](../../tests/test_topics_feature.py#L851) (Zeile 851)
- [test_legacy_topic_admin_url_redirects_into_main_admin](../../tests/test_topics_feature.py#L889) (Zeile 889)
- [test_mock_llm_instances_never_publish_topic_runs](../../tests/test_topics_feature.py#L901) (Zeile 901)
- [test_automatic_topic_run_researches_sources_and_builds_timeline_point](../../tests/test_topics_feature.py#L924) (Zeile 924)
- [test_primary_only_rules_exclude_reporting_instead_of_relabeling_it](../../tests/test_topics_feature.py#L968) (Zeile 968)
- [test_preferred_domain_orders_sources_without_making_them_primary](../../tests/test_topics_feature.py#L989) (Zeile 989)
- [test_topic_page_says_insufficient_eligible_evidence_when_all_sources_are_excluded](../../tests/test_topics_feature.py#L1005) (Zeile 1005)
- [test_topic_run_carries_the_tracked_claims_into_the_identity_judge](../../tests/test_topics_feature.py#L1042) (Zeile 1042)
- [test_claim_identity_falls_back_to_fresh_keys_when_the_judge_is_unavailable](../../tests/test_topics_feature.py#L1098) (Zeile 1098)
- [test_claim_identity_result_maps_claims_onto_the_keys_they_continue](../../tests/test_topics_feature.py#L1119) (Zeile 1119)
- [test_admin_topic_api_creates_updates_and_versions_without_share_data](../../tests/test_topics_feature.py#L1137) (Zeile 1137)
- [test_topic_page_shows_the_position_map_and_agreement_history](../../tests/test_topics_feature.py#L1187) (Zeile 1187)
- [test_old_topic_version_links_survive_more_than_one_page_of_runs](../../tests/test_topics_feature.py#L1253) (Zeile 1253)
- [test_topic_page_counts_do_not_claim_a_complete_history_beyond_the_window](../../tests/test_topics_feature.py#L1286) (Zeile 1286)
- [test_list_runs_until_reads_a_bounded_window_ending_at_the_run](../../tests/test_topics_feature.py#L1314) (Zeile 1314)
- [test_topic_page_keeps_unscored_latest_run_and_its_position_map](../../tests/test_topics_feature.py#L1328) (Zeile 1328)
- [test_topic_page_leads_with_the_finding_and_folds_unchanged_checks](../../tests/test_topics_feature.py#L1350) (Zeile 1350)
- [test_public_topic_history_is_ssr_and_historical_version_is_noindex](../../tests/test_topics_feature.py#L1440) (Zeile 1440)
- [test_disagreement_leads_the_statement_list_and_is_labelled_as_its_own_kind](../../tests/test_topics_feature.py#L1476) (Zeile 1476)

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

**Lauf:** 15 bestanden.

**Geprüftes Verhalten:** Tokenadmission liest Löschguard/Run/Konto begrenzt; vorbereitete Runs lesen das Konto nicht erneut. Fanout admittiert einmal, konkurrierende Runs überbuchen Holds nicht, Ablehnung schreibt nichts.

**Grenzen und Doubles:** Lesebudget stammt aus instrumentiertem Fake, nicht aus echten RPC-/Abrechnungsdaten. Lokale Serialisierung ersetzt Firestore.

**Prüfauftrag für den Folgeaudit:** SDK-/Emulator-Transaktionsread-Vertrag und Limits unter Mehrprozesslast prüfen.

**Direkte Codeverweise:** [app/services/agent_budget_config.py](../../app/services/agent_budget_config.py), [app/services/agent_quota.py](../../app/services/agent_quota.py), [app/services/persistence_guard.py](../../app/services/persistence_guard.py), [app/services/usage_repository.py](../../app/services/usage_repository.py).

**Direkte Testhelfer:** [tests/usage_test_support.py](../../tests/usage_test_support.py).

<details>
<summary>10 Testdefinitionen und ihre Quellstellen</summary>

- [test_direct_run_is_admitted_in_three_reads](../../tests/test_usage_authorization.py#L36) (Zeile 36)
- [test_prepared_runs_authorize_in_two_reads_without_the_account](../../tests/test_usage_authorization.py#L48) (Zeile 48)
- [test_six_provider_fanout_admits_once](../../tests/test_usage_authorization.py#L64) (Zeile 64)
- [test_same_operation_race_has_exactly_one_authorization](../../tests/test_usage_authorization.py#L78) (Zeile 78)
- [test_distinct_run_race_cannot_exceed_the_account](../../tests/test_usage_authorization.py#L90) (Zeile 90)
- [test_conflicts_and_expiry_leave_all_documents_unchanged](../../tests/test_usage_authorization.py#L111) (Zeile 111)
- [test_released_reservation_cannot_authorize_work](../../tests/test_usage_authorization.py#L120) (Zeile 120)
- [test_refused_admission_writes_nothing](../../tests/test_usage_authorization.py#L130) (Zeile 130)
- [test_owner_isolation_and_utc_rollover](../../tests/test_usage_authorization.py#L140) (Zeile 140)
- [test_account_deletion_fence_blocks_even_a_prepared_run](../../tests/test_usage_authorization.py#L152) (Zeile 152)

</details>

<a id="test-usage-limit-ui-py"></a>

## test_usage_limit_ui.py

**Quelle:** [tests/test_usage_limit_ui.py](../../tests/test_usage_limit_ui.py) · **Bereiche:** Frontend, Konten und Tarife.

**Ebene:** Überwiegend Quelltextverträge; ein Asset-Fingerprint-Runtimefall.

**Lauf:** 10 bestanden.

**Geprüftes Verhalten:** Statische Verträge für token_budget_exhausted, zentrale Kontoansicht, Ladereihenfolge und UTC-Reset statt separater Run-/Deep-Thinkzähler.

**Grenzen und Doubles:** UI-Zustandsübergänge werden überwiegend als Sourcefragmente geprüft, nicht ausgeführt.

**Prüfauftrag für den Folgeaudit:** Preflight gegen serverseitige Rennen und tatsächlich erhaltene Draft-/Quote-Zustände mit JS/E2E abgleichen.

**Direkte Codeverweise:** [app/api/routers/chat.py](../../app/api/routers/chat.py), [app/core/assets.py](../../app/core/assets.py), [static/css/components-input.css](../../static/css/components-input.css), [static/css/shell.css](../../static/css/shell.css), [static/js/agent-chat.js](../../static/js/agent-chat.js), [static/js/consensus-run.js](../../static/js/consensus-run.js), [static/js/query-send.js](../../static/js/query-send.js), [static/js/run-registry.js](../../static/js/run-registry.js), [static/js/run-view.js](../../static/js/run-view.js), [static/js/sidebar-quota.js](../../static/js/sidebar-quota.js), [static/js/token-budget.js](../../static/js/token-budget.js), [static/js/usage-limit.js](../../static/js/usage-limit.js), [templates/index.html](../../templates/index.html).

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
- [test_card_names_the_reset_and_never_sells_anything](../../tests/test_usage_limit_ui.py#L154) (Zeile 154)
- [test_deep_think_exhaustion_offers_the_cheaper_run](../../tests/test_usage_limit_ui.py#L167) (Zeile 167)
- [test_css_cache_busting_needs_no_manual_bump](../../tests/test_usage_limit_ui.py#L183) (Zeile 183)

</details>

<a id="test-usage-meter-py"></a>

## test_usage_meter.py

**Quelle:** [tests/test_usage_meter.py](../../tests/test_usage_meter.py) · **Bereiche:** Konten und Tarife, Provider.

**Ebene:** Usage-Meter, Providerseams und Buchungswrapper.

**Lauf:** 8 bestanden.

**Geprüftes Verhalten:** Streaming-/Nichtstreaming-Usage, Reasoningtokens, Abbruchschätzung, kostenlose Ablehnung, Thread-Fanout sowie idempotente Buchung. Finalereignis trägt das Konto, Streamclose bucht und löst die Meterbindung.

**Grenzen und Doubles:** Providerfragmente und Repository ersetzt; keine belastbare Live-Abrechnungsmessung.

**Prüfauftrag für den Folgeaudit:** Die benannten Mock-/Integrationsgrenzen am realen Adapter prüfen; Zuordnung und offene Aufgaben stehen in der Produktmatrix.

**Direkte Codeverweise:** [app/services/llm/engines.py](../../app/services/llm/engines.py), [app/services/llm/provider_runtime.py](../../app/services/llm/provider_runtime.py), [app/services/llm/provider_transport.py](../../app/services/llm/provider_transport.py), [app/services/llm/streaming.py](../../app/services/llm/streaming.py), [app/services/llm/usage_meter.py](../../app/services/llm/usage_meter.py), [app/services/run_metering.py](../../app/services/run_metering.py).

<details>
<summary>8 Testdefinitionen und ihre Quellstellen</summary>

- [test_streamed_request_reports_provider_usage](../../tests/test_usage_meter.py#L23) (Zeile 23)
- [test_cut_stream_is_estimated_and_rejection_is_free](../../tests/test_usage_meter.py#L44) (Zeile 44)
- [test_without_a_bound_meter_nothing_is_metered](../../tests/test_usage_meter.py#L68) (Zeile 68)
- [test_non_streaming_judge_call_reports_usage](../../tests/test_usage_meter.py#L75) (Zeile 75)
- [test_non_streaming_answer_reports_usage](../../tests/test_usage_meter.py#L89) (Zeile 89)
- [test_parallel_fan_out_reports_into_the_callers_meter](../../tests/test_usage_meter.py#L108) (Zeile 108)
- [test_operation_booking_books_once_and_survives_storage_errors](../../tests/test_usage_meter.py#L131) (Zeile 131)
- [test_metered_events_put_the_booked_account_on_the_final_event_and_book_on_close](../../tests/test_usage_meter.py#L147) (Zeile 147)

</details>

<a id="test-user-memory-py"></a>

## test_user_memory.py

**Quelle:** [tests/test_user_memory.py](../../tests/test_user_memory.py) · **Bereiche:** Authentifizierung, Kontext, Nutzergedächtnis.

**Ebene:** Sanitizer-/Repository-/Router-/Prompt-Integration mit Doubles und einem Sourcevertrag.

**Lauf:** 34 bestanden.

**Geprüftes Verhalten:** Feld-/Notizlimits, Whitespace/Controls/Frame-Marker, Enabled/Empty, Profile-Unterordnung unter Evidenz und einmalige Nicht-Persistenzinstruktion. Normalisiertes Save/Legacy-Notizerhalt, Guard-Aufruf, fail-open Reads, Auth/Schema, Clientprompt/Folgekontext/Memory-Opt-out und anonym ohne Read. Aktualisierung 02.10.2026: Manuelles Speichern benötigt erwartete Revision; stale PUT liefert 409 ohne Write, fehlende Revision wird verweigert und absichtliches Leeren mit aktueller Revision bleibt möglich.

**Grenzen und Doubles:** Router-/Provider-/DB-Doubles; Account-Deletion-Unterkollektion wird nur mit inspect.getsource geprüft. Prompttext beweist keine Widerstandsfähigkeit des LLM gegen Injection.

**Prüfauftrag für den Folgeaudit:** Tatsächliche Cascade/Owner-Isolation und Prompt-Injection-Evaluation separat abgleichen.

**Direkte Codeverweise:** [app/api/routers/chat.py](../../app/api/routers/chat.py), [app/api/routers/users.py](../../app/api/routers/users.py), [app/core/config.py](../../app/core/config.py), [app/core/rate_limit.py](../../app/core/rate_limit.py), [app/services/account_deletion.py](../../app/services/account_deletion.py), [app/services/user_memory.py](../../app/services/user_memory.py).

**Direkte Testhelfer:** [tests/usage_test_support.py](../../tests/usage_test_support.py).

<details>
<summary>34 Testdefinitionen und ihre Quellstellen</summary>

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
- [test_stale_manual_save_cannot_restore_older_memory](../../tests/test_user_memory.py#L244) (Zeile 244)
- [test_manual_save_after_an_ai_patch_needs_the_patched_revision](../../tests/test_user_memory.py#L264) (Zeile 264)
- [test_deliberate_clear_with_current_revision_still_works](../../tests/test_user_memory.py#L280) (Zeile 280)
- [test_repository_write_is_fenced_by_the_account_tombstone](../../tests/test_user_memory.py#L288) (Zeile 288)
- [test_load_profile_text_fails_open](../../tests/test_user_memory.py#L304) (Zeile 304)
- [test_memory_endpoints_require_authentication](../../tests/test_user_memory.py#L352) (Zeile 352)
- [test_put_normalizes_and_returns_the_stored_profile](../../tests/test_user_memory.py#L360) (Zeile 360)
- [test_put_rejects_unknown_fields](../../tests/test_user_memory.py#L377) (Zeile 377)
- [test_get_returns_the_stored_profile](../../tests/test_user_memory.py#L385) (Zeile 385)
- [test_stale_put_gets_409_with_the_current_revision_and_writes_nothing](../../tests/test_user_memory.py#L399) (Zeile 399)
- [test_put_without_a_revision_from_an_old_tab_is_refused_not_merged](../../tests/test_user_memory.py#L420) (Zeile 420)
- [test_profile_reaches_the_provider_behind_the_base_instruction](../../tests/test_user_memory.py#L477) (Zeile 477)
- [test_long_manual_note_reaches_the_provider_verbatim](../../tests/test_user_memory.py#L486) (Zeile 486)
- [test_a_client_system_prompt_keeps_precedence_and_still_gets_the_profile](../../tests/test_user_memory.py#L492) (Zeile 492)
- [test_paused_or_empty_profile_still_gets_the_non_persistence_boundary](../../tests/test_user_memory.py#L502) (Zeile 502)
- [test_conversation_context_wraps_around_the_profile](../../tests/test_user_memory.py#L511) (Zeile 511)
- [test_use_memory_false_skips_the_profile_for_a_single_run](../../tests/test_user_memory.py#L529) (Zeile 529)
- [test_anonymous_runs_never_read_a_profile](../../tests/test_user_memory.py#L535) (Zeile 535)
- [test_account_deletion_covers_the_memory_subcollection](../../tests/test_user_memory.py#L552) (Zeile 552)

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

<a id="test-watch-evidence-model-py"></a>

## test_watch_evidence_model.py

**Quelle:** [tests/test_watch_evidence_model.py](../../tests/test_watch_evidence_model.py) · **Bereiche:** Watches, Topics, Quellen.

**Ebene:** Evidence-/Probe-/Ledgerdienste mit Fake-DB.

**Lauf:** 13 bestanden.

**Geprüftes Verhalten:** Gültige neue Quellen, Wiederbewertung/Modellwechsel, Held-Runs, Rechecks und Zielabschluss. Probeclaims beachten Tagesbudget und Terminabstand; geändertes Ziel oder neuer Claimtoken macht das alte Resultat ohne Writes ungültig.

**Grenzen und Doubles:** Synthetische Quellen/Judgeergebnisse; keine fachliche Bewertung echter Neuigkeiten.

**Prüfauftrag für den Folgeaudit:** Die benannten Betriebs- und Testgrenzen bei künftigen Änderungen erneut prüfen; konkrete Paketnachweise stehen im Produktabgleich.

**Direkte Codeverweise:** [app/services/claim_ledger.py](../../app/services/claim_ledger.py), [app/services/evidence_change.py](../../app/services/evidence_change.py), [app/services/topic_runner.py](../../app/services/topic_runner.py), [app/services/watch_probe.py](../../app/services/watch_probe.py), [app/services/watch_service.py](../../app/services/watch_service.py).

<details>
<summary>13 Testdefinitionen und ihre Quellstellen</summary>

- [test_new_evidence_must_cite_a_source_the_standing_answer_did_not_have](../../tests/test_watch_evidence_model.py#L31) (Zeile 31)
- [test_invented_source_ids_are_dropped](../../tests/test_watch_evidence_model.py#L49) (Zeile 49)
- [test_a_reassessment_after_a_line_up_change_is_a_model_change](../../tests/test_watch_evidence_model.py#L57) (Zeile 57)
- [test_an_unchanged_answer_has_no_cause_and_a_goal_needs_a_cited_source](../../tests/test_watch_evidence_model.py#L66) (Zeile 66)
- [test_the_judge_sees_which_new_sources_it_has_seen_before](../../tests/test_watch_evidence_model.py#L84) (Zeile 84)
- [test_a_held_topic_run_is_a_gap_in_the_claim_record_not_a_retraction](../../tests/test_watch_evidence_model.py#L93) (Zeile 93)
- [test_a_topic_run_outcome_asks_for_a_recheck_on_a_reassessment](../../tests/test_watch_evidence_model.py#L120) (Zeile 120)
- [test_a_resolved_watch_only_reopens_with_a_new_or_empty_goal](../../tests/test_watch_evidence_model.py#L143) (Zeile 143)
- [test_a_probe_only_counts_a_yes_with_a_source_the_answer_did_not_cite](../../tests/test_watch_evidence_model.py#L164) (Zeile 164)
- [test_probe_claim_advances_first_and_respects_the_daily_cap](../../tests/test_watch_evidence_model.py#L188) (Zeile 188)
- [test_probe_is_skipped_when_the_full_check_is_close_or_the_watch_is_daily](../../tests/test_watch_evidence_model.py#L199) (Zeile 199)
- [test_new_evidence_pulls_the_full_check_forward](../../tests/test_watch_evidence_model.py#L208) (Zeile 208)
- [test_claimed_probe_cannot_record_for_changed_goal_or_superseded_claim](../../tests/test_watch_evidence_model.py#L223) (Zeile 223)

</details>

<a id="test-watch-feature-py"></a>

## test_watch_feature.py

**Quelle:** [tests/test_watch_feature.py](../../tests/test_watch_feature.py) · **Bereiche:** Benachrichtigungen, Frontend, Konten und Tarife, Persistenz, Watch.

**Ebene:** Große Service-/Scheduler-/Router-/Mailformat-Suite mit DB-/LLM-/Versand-Doubles plus UI-Sourceverträge.

**Lauf:** 157 bestanden.

**Geprüftes Verhalten:** Watches halten die stehende Antwort bei fehlenden neuen Belegen, bestätigen Wiederbewertung erneut und lösen erreichte Ziele samt Slotfreigabe auf. Outbox wird mit Ergebnis/Briefclaim gespeichert; Mailtexte nennen Änderung/Belege statt Score, Quellenbewegung und Modellposition bleiben getrennt.

**Grenzen und Doubles:** Meist lokale Fake-Transaktionen und gemockte Schedulerabhängigkeiten; keine realen Mails/Telegram/LLM. Mehrere Claims werden sequenziell getestet, nicht als echte verteilte Rennen. UI nur Source.

**Prüfauftrag für den Folgeaudit:** Emulator-Watch-/Followertransaktionen, Schedulercrash zwischen Claim/Versand, DST-Sonderfälle und Browsermodals abgleichen.

**Direkte Codeverweise:** [app/api/routers/admin.py](../../app/api/routers/admin.py), [app/api/routers/pages.py](../../app/api/routers/pages.py), [app/api/routers/share.py](../../app/api/routers/share.py), [app/api/routers/watch.py](../../app/api/routers/watch.py), [app/core/config.py](../../app/core/config.py), [app/core/rate_limit.py](../../app/core/rate_limit.py), [app/services/drift_signal.py](../../app/services/drift_signal.py), [app/services/follow_challenges.py](../../app/services/follow_challenges.py), [app/services/llm/consensus_engine.py](../../app/services/llm/consensus_engine.py), [app/services/mailer.py](../../app/services/mailer.py), [app/services/opinion_map.py](../../app/services/opinion_map.py), [app/services/persistence_guard.py](../../app/services/persistence_guard.py), [app/services/share_snapshots.py](../../app/services/share_snapshots.py), [app/services/telegram_watch.py](../../app/services/telegram_watch.py), [app/services/watch_brief.py](../../app/services/watch_brief.py), [app/services/watch_followers.py](../../app/services/watch_followers.py), [app/services/watch_scheduler.py](../../app/services/watch_scheduler.py), [app/services/watch_service.py](../../app/services/watch_service.py), [static/css/components-input.css](../../static/css/components-input.css), [static/css/components-modals.css](../../static/css/components-modals.css), [static/css/components-watch.css](../../static/css/components-watch.css), [static/css/public-pages.css](../../static/css/public-pages.css), [static/firebase.js](../../static/firebase.js), [static/js/share-dialog.js](../../static/js/share-dialog.js), [static/js/watch-dashboard.js](../../static/js/watch-dashboard.js), [static/js/watch.js](../../static/js/watch.js), [templates/index.html](../../templates/index.html), [templates/share.html](../../templates/share.html).

<details>
<summary>157 Testdefinitionen und ihre Quellstellen</summary>

- [WatchCrudTests::test_free_create_list_update_pause_delete](../../tests/test_watch_feature.py#L177) (Zeile 177)
- [WatchCrudTests::test_account_deletion_fences_watch_mutations_but_cleanup_delete_continues](../../tests/test_watch_feature.py#L194) (Zeile 194)
- [WatchCrudTests::test_account_deletion_retry_does_not_recreate_deleted_watch_indexes](../../tests/test_watch_feature.py#L234) (Zeile 234)
- [WatchCrudTests::test_owned_share_cleanup_does_not_recreate_deleted_watch_indexes](../../tests/test_watch_feature.py#L267) (Zeile 267)
- [WatchCrudTests::test_normal_delete_reseeds_missing_watch_indexes_for_counter_updates](../../tests/test_watch_feature.py#L296) (Zeile 296)
- [WatchCrudTests::test_watch_requires_one_notification_channel](../../tests/test_watch_feature.py#L322) (Zeile 322)
- [WatchCrudTests::test_every_run_email_mode_can_be_created_and_changed](../../tests/test_watch_feature.py#L339) (Zeile 339)
- [WatchCrudTests::test_condition_mode_requires_condition_and_resets_state_when_edited](../../tests/test_watch_feature.py#L354) (Zeile 354)
- [WatchCrudTests::test_free_daily_requires_a_higher_tier](../../tests/test_watch_feature.py#L373) (Zeile 373)
- [WatchCrudTests::test_plus_may_watch_daily_but_keeps_a_smaller_slot_count](../../tests/test_watch_feature.py#L379) (Zeile 379)
- [WatchCrudTests::test_plus_daily_can_be_switched_off_by_the_admin](../../tests/test_watch_feature.py#L389) (Zeile 389)
- [WatchCrudTests::test_daily_gate_follows_admin_limit](../../tests/test_watch_feature.py#L396) (Zeile 396)
- [WatchCrudTests::test_free_and_pro_active_limits](../../tests/test_watch_feature.py#L403) (Zeile 403)
- [WatchCrudTests::test_pause_delete_and_resume_keep_owner_counter_consistent](../../tests/test_watch_feature.py#L413) (Zeile 413)
- [WatchCrudTests::test_cannot_watch_foreign_or_duplicate_share](../../tests/test_watch_feature.py#L436) (Zeile 436)
- [WatchCrudTests::test_publisher_watch_is_free_pinned_and_idempotent](../../tests/test_watch_feature.py#L445) (Zeile 445)
- [WatchCrudTests::test_publisher_watch_resume_bypasses_owner_limit_but_keeps_counter](../../tests/test_watch_feature.py#L474) (Zeile 474)
- [WatchCrudTests::test_legacy_free_watch_counts_and_verified_lineage_is_backfilled](../../tests/test_watch_feature.py#L496) (Zeile 496)
- [WatchCrudTests::test_admin_can_list_and_queue_active_watch](../../tests/test_watch_feature.py#L520) (Zeile 520)
- [WatchCrudTests::test_admin_queue_rejects_paused_or_claimed_watch](../../tests/test_watch_feature.py#L533) (Zeile 533)
- [WatchCrudTests::test_update_rejects_unknown_fields_and_owner](../../tests/test_watch_feature.py#L548) (Zeile 548)
- [WatchCrudTests::test_result_id_uses_existing_share_flow](../../tests/test_watch_feature.py#L555) (Zeile 555)
- [WatchCrudTests::test_query_first_watch_creates_an_empty_scheduled_baseline](../../tests/test_watch_feature.py#L566) (Zeile 566)
- [WatchCrudTests::test_query_first_watch_rejects_duplicate_question](../../tests/test_watch_feature.py#L587) (Zeile 587)
- [WatchCrudTests::test_query_first_watch_requires_a_complete_text_question](../../tests/test_watch_feature.py#L598) (Zeile 598)
- [WatchCrudTests::test_deleting_query_first_watch_revokes_its_empty_page](../../tests/test_watch_feature.py#L609) (Zeile 609)
- [WatchCrudTests::test_private_watch_keeps_visibility_private](../../tests/test_watch_feature.py#L620) (Zeile 620)
- [WatchCrudTests::test_watch_can_schedule_local_run_time](../../tests/test_watch_feature.py#L629) (Zeile 629)
- [WatchCrudTests::test_free_weekly_watch_uses_selected_local_weekday](../../tests/test_watch_feature.py#L644) (Zeile 644)
- [WatchCrudTests::test_weekly_run_day_can_be_updated_and_rejects_invalid_values](../../tests/test_watch_feature.py#L659) (Zeile 659)
- [WatchCrudTests::test_manual_run_keeps_the_selected_weekday](../../tests/test_watch_feature.py#L680) (Zeile 680)
- [WatchCrudTests::test_run_time_update_reschedules_and_rejects_invalid_values](../../tests/test_watch_feature.py#L688) (Zeile 688)
- [UnsubscribeTokenTests::test_valid_token_pauses_without_login](../../tests/test_watch_feature.py#L723) (Zeile 723)
- [UnsubscribeTokenTests::test_invalid_and_expired_tokens](../../tests/test_watch_feature.py#L736) (Zeile 736)
- [UnsubscribeTokenTests::test_tampered_token_is_invalid](../../tests/test_watch_feature.py#L743) (Zeile 743)
- [SchedulerSafetyTests::test_claim_transaction_prevents_double_run](../../tests/test_watch_feature.py#L760) (Zeile 760)
- [SchedulerSafetyTests::test_daily_budget_leaves_watch_due](../../tests/test_watch_feature.py#L773) (Zeile 773)
- [SchedulerSafetyTests::test_auto_pause_only_on_third_failure](../../tests/test_watch_feature.py#L783) (Zeile 783)
- [SchedulerSafetyTests::test_notification_threshold](../../tests/test_watch_feature.py#L797) (Zeile 797)
- [SchedulerSafetyTests::test_mock_llm_scheduler_ticks_never_touch_the_shared_database](../../tests/test_watch_feature.py#L814) (Zeile 814)
- [SchedulerSafetyTests::test_mock_llm_watch_pipeline](../../tests/test_watch_feature.py#L825) (Zeile 825)
- [SchedulerSafetyTests::test_watch_pipeline_tracks_previous_and_original_baseline_separately](../../tests/test_watch_feature.py#L838) (Zeile 838)
- [SchedulerSafetyTests::test_query_first_pipeline_establishes_baseline_without_change_alert](../../tests/test_watch_feature.py#L868) (Zeile 868)
- [SchedulerSafetyTests::test_query_first_condition_is_evaluated_against_first_consensus](../../tests/test_watch_feature.py#L879) (Zeile 879)
- [SchedulerSafetyTests::test_complete_run_persists_full_version_and_simple_event_type](../../tests/test_watch_feature.py#L902) (Zeile 902)
- [SchedulerSafetyTests::test_a_restated_answer_is_recorded_as_a_check_not_as_a_change](../../tests/test_watch_feature.py#L951) (Zeile 951)
- [SchedulerSafetyTests::test_a_held_answer_keeps_the_standing_version_and_its_schedule](../../tests/test_watch_feature.py#L1008) (Zeile 1008)
- [SchedulerSafetyTests::test_a_reassessment_is_rechecked_before_it_counts](../../tests/test_watch_feature.py#L1022) (Zeile 1022)
- [SchedulerSafetyTests::test_a_score_drop_alone_is_no_longer_movement](../../tests/test_watch_feature.py#L1043) (Zeile 1043)
- [SchedulerSafetyTests::test_a_goal_met_with_a_source_resolves_the_watch_and_frees_its_slot](../../tests/test_watch_feature.py#L1052) (Zeile 1052)
- [SchedulerSafetyTests::test_an_unsourced_goal_needs_a_second_met_check](../../tests/test_watch_feature.py#L1072) (Zeile 1072)
- [SchedulerSafetyTests::test_first_query_watch_run_promotes_result_to_share_baseline](../../tests/test_watch_feature.py#L1090) (Zeile 1090)
- [SchedulerSafetyTests::test_stale_run_cannot_complete_or_fail_newer_claim](../../tests/test_watch_feature.py#L1124) (Zeile 1124)
- [SchedulerSafetyTests::test_watch_lease_renewal_is_fenced_by_run_id](../../tests/test_watch_feature.py#L1155) (Zeile 1155)
- [SchedulerSafetyTests::test_watch_uses_all_configured_models_for_the_selected_tier](../../tests/test_watch_feature.py#L1176) (Zeile 1176)
- [SchedulerSafetyTests::test_watch_preserves_its_provider_and_fallback_engine_order](../../tests/test_watch_feature.py#L1189) (Zeile 1189)
- [SchedulerSafetyTests::test_watch_uses_configured_consensus_engine_independent_of_answer_models](../../tests/test_watch_feature.py#L1246) (Zeile 1246)
- [SchedulerSafetyTests::test_watch_falls_back_when_configured_consensus_provider_is_unavailable](../../tests/test_watch_feature.py#L1284) (Zeile 1284)
- [SchedulerSafetyTests::test_free_tier_watch_runs_every_configured_provider](../../tests/test_watch_feature.py#L1295) (Zeile 1295)
- [SchedulerSafetyTests::test_missing_shared_credential_drops_every_configured_model](../../tests/test_watch_feature.py#L1307) (Zeile 1307)
- [MailerTests::test_change_mail_is_multipart_with_unsubscribe](../../tests/test_watch_feature.py#L1338) (Zeile 1338)
- [MailerTests::test_change_mail_is_a_change_log_without_a_score](../../tests/test_watch_feature.py#L1346) (Zeile 1346)
- [MailerTests::test_every_run_mail_contains_the_answer](../../tests/test_watch_feature.py#L1365) (Zeile 1365)
- [MailerTests::test_condition_mail_says_the_watch_is_complete](../../tests/test_watch_feature.py#L1377) (Zeile 1377)
- [MailerTests::test_long_question_is_collapsed_and_links_to_the_page](../../tests/test_watch_feature.py#L1393) (Zeile 1393)
- [MailerTests::test_short_question_stays_whole_and_without_a_link](../../tests/test_watch_feature.py#L1404) (Zeile 1404)
- [MailerTests::test_brief_puts_changed_watches_first](../../tests/test_watch_feature.py#L1410) (Zeile 1410)
- [MailerTests::test_admin_test_mail_is_multipart_and_does_not_claim_a_watch](../../tests/test_watch_feature.py#L1428) (Zeile 1428)
- [MailerTests::test_public_watch_meta_contains_run_schedule_but_no_owner](../../tests/test_watch_feature.py#L1434) (Zeile 1434)
- [HistoryViewTests::test_watch_page_schedule_includes_weekday](../../tests/test_watch_feature.py#L1452) (Zeile 1452)
- [HistoryViewTests::test_svg_view_coordinates_and_change_events](../../tests/test_watch_feature.py#L1459) (Zeile 1459)
- [HistoryViewTests::test_position_map_labels_lose_the_markdown_of_the_answer_text](../../tests/test_watch_feature.py#L1472) (Zeile 1472)
- [OpinionMapTests::test_modal_may_and_number_formatting_are_not_movement](../../tests/test_watch_feature.py#L1495) (Zeile 1495)
- [OpinionMapTests::test_multidimensional_map_tracks_provider_cluster_movement](../../tests/test_watch_feature.py#L1518) (Zeile 1518)
- [OpinionMapTests::test_stable_judge_prevents_synthetic_full_shift](../../tests/test_watch_feature.py#L1529) (Zeile 1529)
- [OpinionMapTests::test_reframed_dimensions_are_unscored_instead_of_full_shift](../../tests/test_watch_feature.py#L1543) (Zeile 1543)
- [OpinionMapTests::test_legacy_full_shift_is_recalculated_against_predecessor](../../tests/test_watch_feature.py#L1561) (Zeile 1561)
- [OpinionMapTests::test_numbers_units_signs_negations_and_conditions_register_as_movement](../../tests/test_watch_feature.py#L1588) (Zeile 1588)
- [OpinionMapTests::test_pure_paraphrase_is_not_movement](../../tests/test_watch_feature.py#L1607) (Zeile 1607)
- [OpinionMapTests::test_single_model_change_stays_visible_when_consensus_is_stable](../../tests/test_watch_feature.py#L1616) (Zeile 1616)
- [OpinionMapTests::test_missing_comparison_is_not_scored_as_stable](../../tests/test_watch_feature.py#L1637) (Zeile 1637)
- [OpinionMapTests::test_sanitized_map_keeps_unknown_movement_unknown](../../tests/test_watch_feature.py#L1653) (Zeile 1653)
- [OpinionMapTests::test_map_is_compact_and_contains_no_raw_answers](../../tests/test_watch_feature.py#L1662) (Zeile 1662)
- [OpinionMapTests::test_unanimous_claims_still_produce_a_direction_baseline](../../tests/test_watch_feature.py#L1667) (Zeile 1667)
- [SchedulerLoopTests::test_scheduler_wake_triggers_an_immediate_second_tick](../../tests/test_watch_feature.py#L1684) (Zeile 1684)
- [SchedulerLoopTests::test_pause_notification_is_queued_exactly_on_third_failure](../../tests/test_watch_feature.py#L1731) (Zeile 1731)
- [SchedulerLoopTests::test_successful_run_commits_result_and_outbox_items_together](../../tests/test_watch_feature.py#L1760) (Zeile 1760)
- [SchedulerLoopTests::test_telegram_only_watch_reuses_notification_rule_without_mail](../../tests/test_watch_feature.py#L1804) (Zeile 1804)
- [SchedulerLoopTests::test_each_watch_run_uses_the_owners_current_tier](../../tests/test_watch_feature.py#L1835) (Zeile 1835)
- [SchedulerLoopTests::test_publisher_watch_stays_on_free_tier_for_pro_owner](../../tests/test_watch_feature.py#L1864) (Zeile 1864)
- [TelegramWatchTests::test_one_time_deep_link_connects_and_disconnects_private_chat](../../tests/test_watch_feature.py#L1909) (Zeile 1909)
- [TelegramWatchTests::test_account_deletion_fences_link_creation_consumption_and_delivery_claim](../../tests/test_watch_feature.py#L1929) (Zeile 1929)
- [TelegramWatchTests::test_startup_registers_secret_header_webhook](../../tests/test_watch_feature.py#L1954) (Zeile 1954)
- [TelegramWatchTests::test_watch_message_contains_actions](../../tests/test_watch_feature.py#L1966) (Zeile 1966)
- [TelegramWatchTests::test_notification_text_leads_with_the_change_and_folds_the_question](../../tests/test_watch_feature.py#L1985) (Zeile 1985)
- [TelegramWatchTests::test_resolved_text_names_the_goal](../../tests/test_watch_feature.py#L2014) (Zeile 2014)
- [TelegramWatchTests::test_html_rejection_falls_back_to_plain_text](../../tests/test_watch_feature.py#L2024) (Zeile 2024)
- [TelegramWatchTests::test_mute_and_confirmed_pause_actions_are_owner_scoped](../../tests/test_watch_feature.py#L2048) (Zeile 2048)
- [TelegramWatchTests::test_account_cleanup_removes_connection_links_and_deliveries](../../tests/test_watch_feature.py#L2079) (Zeile 2079)
- [WatchFrontendContractTests::test_user_menu_places_watched_after_shared_links](../../tests/test_watch_feature.py#L2097) (Zeile 2097)
- [WatchFrontendContractTests::test_watch_ui_exposes_every_run_email_mode](../../tests/test_watch_feature.py#L2102) (Zeile 2102)
- [WatchFrontendContractTests::test_watch_dashboard_supports_query_first_creation](../../tests/test_watch_feature.py#L2119) (Zeile 2119)
- [WatchFrontendContractTests::test_watch_empty_state_explains_the_difference_to_a_scheduled_prompt](../../tests/test_watch_feature.py#L2129) (Zeile 2129)
- [WatchFrontendContractTests::test_watch_setup_offers_editing_next_to_the_defaults_it_describes](../../tests/test_watch_feature.py#L2142) (Zeile 2142)
- [WatchFrontendContractTests::test_watch_dialog_ignores_backdrop_click_and_view_switch_hint_is_finite](../../tests/test_watch_feature.py#L2172) (Zeile 2172)
- [WatchFrontendContractTests::test_watch_limits_are_visible_before_creation_and_on_dashboard](../../tests/test_watch_feature.py#L2182) (Zeile 2182)
- [WatchFrontendContractTests::test_watch_modal_has_one_scroll_area_and_locks_background](../../tests/test_watch_feature.py#L2192) (Zeile 2192)
- [WatchFrontendContractTests::test_watch_dashboard_is_a_page_with_segmented_view_switch](../../tests/test_watch_feature.py#L2213) (Zeile 2213)
- [WatchFrontendContractTests::test_long_questions_collapse_on_the_page_like_in_the_app](../../tests/test_watch_feature.py#L2240) (Zeile 2240)
- [WatchFrontendContractTests::test_watch_cards_open_their_settings_in_place_and_keep_their_styles](../../tests/test_watch_feature.py#L2261) (Zeile 2261)
- [WatchPageRouteTests::test_watch_page_serves_app_shell_noindex](../../tests/test_watch_feature.py#L2280) (Zeile 2280)
- [WatchHistorySerializationTests::test_list_watches_can_attach_compact_history](../../tests/test_watch_feature.py#L2288) (Zeile 2288)
- [WatchHistorySerializationTests::test_history_lookup_failure_degrades_to_empty_list](../../tests/test_watch_feature.py#L2311) (Zeile 2311)
- [WatchHistorySerializationTests::test_serialize_history_points_caps_at_newest](../../tests/test_watch_feature.py#L2320) (Zeile 2320)
- [BriefSettingsTests::test_defaults_when_no_document_exists](../../tests/test_watch_feature.py#L2336) (Zeile 2336)
- [BriefSettingsTests::test_account_deletion_tombstone_fences_brief_upsert](../../tests/test_watch_feature.py#L2343) (Zeile 2343)
- [BriefSettingsTests::test_enabling_without_a_watch_is_rejected](../../tests/test_watch_feature.py#L2355) (Zeile 2355)
- [BriefSettingsTests::test_final_watch_removal_disables_an_active_brief](../../tests/test_watch_feature.py#L2363) (Zeile 2363)
- [BriefSettingsTests::test_enabling_requires_timezone_and_schedules_dst_safe](../../tests/test_watch_feature.py#L2373) (Zeile 2373)
- [BriefSettingsTests::test_time_change_while_enabled_reschedules](../../tests/test_watch_feature.py#L2390) (Zeile 2390)
- [BriefSettingsTests::test_mode_and_field_validation](../../tests/test_watch_feature.py#L2403) (Zeile 2403)
- [BriefSettingsTests::test_disable_keeps_settings](../../tests/test_watch_feature.py#L2412) (Zeile 2412)
- [BriefClaimTests::test_claim_advances_before_sending_and_prevents_double_send](../../tests/test_watch_feature.py#L2433) (Zeile 2433)
- [BriefClaimTests::test_claim_stages_one_outbox_item_in_the_same_transaction](../../tests/test_watch_feature.py#L2441) (Zeile 2441)
- [BriefClaimTests::test_disabled_or_not_due_is_not_claimed](../../tests/test_watch_feature.py#L2453) (Zeile 2453)
- [BriefClaimTests::test_unschedulable_settings_disable_instead_of_hot_looping](../../tests/test_watch_feature.py#L2459) (Zeile 2459)
- [BriefClaimTests::test_baseline_falls_back_to_first_brief_window](../../tests/test_watch_feature.py#L2464) (Zeile 2464)
- [BriefClaimTests::test_due_scan_lists_only_enabled_due_briefs](../../tests/test_watch_feature.py#L2469) (Zeile 2469)
- [BriefCollectTests::test_notable_changes_are_counted_since_baseline](../../tests/test_watch_feature.py#L2480) (Zeile 2480)
- [BriefMailTests::test_brief_mail_is_multipart_with_summary_and_unsubscribe](../../tests/test_watch_feature.py#L2519) (Zeile 2519)
- [BriefMailTests::test_brief_mail_without_changes_uses_calm_subject](../../tests/test_watch_feature.py#L2534) (Zeile 2534)
- [BriefTokenTests::test_valid_token_disables_brief](../../tests/test_watch_feature.py#L2555) (Zeile 2555)
- [BriefTokenTests::test_watch_token_is_not_accepted_for_brief](../../tests/test_watch_feature.py#L2563) (Zeile 2563)
- [BriefTokenTests::test_expired_brief_token](../../tests/test_watch_feature.py#L2568) (Zeile 2568)
- [BriefTickTests::test_due_brief_is_claimed_and_delivered_through_the_outbox](../../tests/test_watch_feature.py#L2575) (Zeile 2575)
- [BriefTickTests::test_unclaimed_brief_is_not_delivered](../../tests/test_watch_feature.py#L2592) (Zeile 2592)
- [WatchRouteTests::test_create_forwards_weekday_schedule](../../tests/test_watch_feature.py#L2614) (Zeile 2614)
- [WatchRouteTests::test_create_forwards_query_without_result_id](../../tests/test_watch_feature.py#L2630) (Zeile 2630)
- [WatchRouteTests::test_my_watches_exposes_authoritative_active_limit](../../tests/test_watch_feature.py#L2650) (Zeile 2650)
- [WatchRouteTests::test_goal_suggestions_are_offered_and_never_block_the_dialog](../../tests/test_watch_feature.py#L2674) (Zeile 2674)
- [WatchRouteTests::test_telegram_must_be_connected_before_enabling_watch_channel](../../tests/test_watch_feature.py#L2699) (Zeile 2699)
- [WatchRouteTests::test_telegram_connection_routes_and_webhook_secret](../../tests/test_watch_feature.py#L2713) (Zeile 2713)
- [BriefRouteTests::test_get_and_patch_brief_settings](../../tests/test_watch_feature.py#L2752) (Zeile 2752)
- [BriefRouteTests::test_patch_brief_maps_watch_errors_to_http_400](../../tests/test_watch_feature.py#L2774) (Zeile 2774)
- [BriefRouteTests::test_brief_unsubscribe_page](../../tests/test_watch_feature.py#L2782) (Zeile 2782)
- [AdminWatchRouteTests::test_watch_diagnostics_requires_admin](../../tests/test_watch_feature.py#L2808) (Zeile 2808)
- [AdminWatchRouteTests::test_watch_diagnostics_lists_and_starts_run](../../tests/test_watch_feature.py#L2814) (Zeile 2814)
- [AdminWatchRouteTests::test_admin_test_email_uses_verified_admin_address](../../tests/test_watch_feature.py#L2838) (Zeile 2838)
- [FollowerTests::test_request_confirm_and_unsubscribe_roundtrip](../../tests/test_watch_feature.py#L2869) (Zeile 2869)
- [FollowerTests::test_confirm_and_unsubscribe_tokens_are_not_interchangeable](../../tests/test_watch_feature.py#L2891) (Zeile 2891)
- [FollowerTests::test_invalid_email_and_unfollowable_pages_rejected](../../tests/test_watch_feature.py#L2899) (Zeile 2899)
- [FollowerTests::test_delete_followers_for_share](../../tests/test_watch_feature.py#L2911) (Zeile 2911)
- [FollowerTests::test_follower_items_only_on_material_change](../../tests/test_watch_feature.py#L2918) (Zeile 2918)
- [FollowerTests::test_cleanup_or_removed_watch_invalidates_outstanding_confirm_link](../../tests/test_watch_feature.py#L2967) (Zeile 2967)
- [FollowRouteTests::test_follow_route_sends_confirmation_mail](../../tests/test_watch_feature.py#L2994) (Zeile 2994)
- [FollowRouteTests::test_follow_route_is_generic_for_existing_followers](../../tests/test_watch_feature.py#L3004) (Zeile 3004)
- [FollowRouteTests::test_follow_confirm_route_renders_page](../../tests/test_watch_feature.py#L3013) (Zeile 3013)

</details>

<a id="test-watch-http-contract-py"></a>

## test_watch_http_contract.py

**Quelle:** [tests/test_watch_http_contract.py](../../tests/test_watch_http_contract.py) · **Bereiche:** Watches, Authentifizierung.

**Ebene:** Registrierte main.app mit echten Middleware-, Auth-/Owner- und Serviceguards.

**Lauf:** 13 bestanden.

**Geprüftes Verhalten:** Watch PATCH/DELETE und Telegram Link/Test/Disconnect prüfen Owner, Allowlist, Tarif, Verbindung und Store-/Providerfehler. Gültige, ungültige, abgelaufene und falsche Tokentypen bewirken nur die erlaubte Änderung; Bestätigungs-HTML escaped Nutztext.

**Grenzen und Doubles:** Firebase-SDK-Authentifizierung und DB ersetzt; externe Modell-, Mail- und Telegramgrenzen kontrolliert. Kein Live-OAuth oder produktiver Versand.

**Prüfauftrag für den Folgeaudit:** Die benannten Betriebs- und Testgrenzen bei künftigen Änderungen erneut prüfen; konkrete Paketnachweise stehen im Produktabgleich.

**Direkte Codeverweise:** [app/core/rate_limit.py](../../app/core/rate_limit.py), [app/services/share_snapshots.py](../../app/services/share_snapshots.py), [app/services/telegram_watch.py](../../app/services/telegram_watch.py), [app/services/watch_brief.py](../../app/services/watch_brief.py), [app/services/watch_followers.py](../../app/services/watch_followers.py), [app/services/watch_service.py](../../app/services/watch_service.py).

<details>
<summary>6 Testdefinitionen und ihre Quellstellen</summary>

- [test_watch_patch_delete_entitlement_owner_and_allowlist](../../tests/test_watch_http_contract.py#L42) (Zeile 42)
- [test_telegram_link_test_disconnect_are_bound_to_authenticated_owner](../../tests/test_watch_http_contract.py#L71) (Zeile 71)
- [test_unsubscribe_invalid_expired_and_wrong_type_never_mutate](../../tests/test_watch_http_contract.py#L129) (Zeile 129)
- [test_watch_and_follower_unsubscribe_change_only_the_bound_resource](../../tests/test_watch_http_contract.py#L157) (Zeile 157)
- [test_follower_confirmation_escapes_stored_question](../../tests/test_watch_http_contract.py#L183) (Zeile 183)
- [test_watch_adapters_project_storage_failure_safely](../../tests/test_watch_http_contract.py#L199) (Zeile 199)

</details>

<a id="test-watch-review-regressions-py"></a>

## test_watch_review_regressions.py

**Quelle:** [tests/test_watch_review_regressions.py](../../tests/test_watch_review_regressions.py) · **Bereiche:** Watches, Topics, Betrieb.

**Ebene:** Scheduler-/Outbox-/Deliverydienste mit Fake-DB und Versand-Doubles.

**Lauf:** 24 bestanden.

**Geprüftes Verhalten:** Pause/Resume/Termin-/Zielwechsel sperren späte Worker; Leaseowner verhindert fremdes Freigeben. Resultat und Outbox werden gemeinsam gespeichert, Crash/Retry/Backoff/Ablauf, Unsubscribe/Löschtombstone, Telegrammute/403 und Morning-Brief-/Topiczustellung werden geprüft.

**Grenzen und Doubles:** Fake-Transaktionen und SMTP/Telegram-Doubles; kein genau-einmaliger externer Versand oder nativer verteilter Lease-Nachweis.

**Prüfauftrag für den Folgeaudit:** Die benannten Mock-/Integrationsgrenzen am realen Adapter prüfen; Zuordnung und offene Aufgaben stehen in der Produktmatrix.

**Direkte Codeverweise:** [app/core/observability.py](../../app/core/observability.py), [app/services/notification_delivery.py](../../app/services/notification_delivery.py), [app/services/notification_outbox.py](../../app/services/notification_outbox.py), [app/services/persistence_guard.py](../../app/services/persistence_guard.py), [app/services/topic_runner.py](../../app/services/topic_runner.py), [app/services/topics.py](../../app/services/topics.py), [app/services/watch_brief.py](../../app/services/watch_brief.py), [app/services/watch_followers.py](../../app/services/watch_followers.py), [app/services/watch_scheduler.py](../../app/services/watch_scheduler.py), [app/services/watch_service.py](../../app/services/watch_service.py).

<details>
<summary>24 Testdefinitionen und ihre Quellstellen</summary>

- [test_pause_then_stale_failure_keeps_watch_paused_and_counter_consistent](../../tests/test_watch_review_regressions.py#L86) (Zeile 86)
- [test_pause_then_stale_success_does_not_reactivate_or_reschedule](../../tests/test_watch_review_regressions.py#L100) (Zeile 100)
- [test_resume_revokes_the_old_claim_so_no_second_worker_shares_a_generation](../../tests/test_watch_review_regressions.py#L112) (Zeile 112)
- [test_resending_the_current_status_keeps_a_running_claim](../../tests/test_watch_review_regressions.py#L125) (Zeile 125)
- [test_schedule_change_during_run_survives_completion_and_failure](../../tests/test_watch_review_regressions.py#L133) (Zeile 133)
- [test_third_failure_only_pauses_an_active_watch](../../tests/test_watch_review_regressions.py#L162) (Zeile 162)
- [test_alert_rule_changed_during_run_is_applied_at_commit](../../tests/test_watch_review_regressions.py#L169) (Zeile 169)
- [test_condition_edited_during_run_neither_alerts_nor_records_the_old_state](../../tests/test_watch_review_regressions.py#L189) (Zeile 189)
- [test_expired_worker_cannot_release_the_new_owners_lease](../../tests/test_watch_review_regressions.py#L215) (Zeile 215)
- [test_owner_release_frees_the_lease_immediately](../../tests/test_watch_review_regressions.py#L241) (Zeile 241)
- [test_legacy_ownerless_lease_simply_expires](../../tests/test_watch_review_regressions.py#L248) (Zeile 248)
- [test_scheduler_stops_when_its_worker_lease_was_taken_over](../../tests/test_watch_review_regressions.py#L258) (Zeile 258)
- [test_delivery_ids_are_stable_per_resource_run_channel_and_recipient](../../tests/test_watch_review_regressions.py#L294) (Zeile 294)
- [test_crash_after_result_commit_leaves_a_retryable_item](../../tests/test_watch_review_regressions.py#L302) (Zeile 302)
- [test_crash_mid_attempt_is_retried_after_the_lease](../../tests/test_watch_review_regressions.py#L333) (Zeile 333)
- [test_failures_back_off_and_turn_terminal_with_a_metric](../../tests/test_watch_review_regressions.py#L351) (Zeile 351)
- [test_expired_items_fail_instead_of_sending_stale_news](../../tests/test_watch_review_regressions.py#L375) (Zeile 375)
- [test_paused_watch_skips_a_queued_alert_before_the_attempt](../../tests/test_watch_review_regressions.py#L386) (Zeile 386)
- [test_unsubscribed_follower_receives_no_late_retry_and_others_still_do](../../tests/test_watch_review_regressions.py#L403) (Zeile 403)
- [test_account_deletion_tombstone_skips_items_before_any_attempt](../../tests/test_watch_review_regressions.py#L448) (Zeile 448)
- [test_telegram_attempt_rechecks_mute_and_connection_and_disables_on_403](../../tests/test_watch_review_regressions.py#L459) (Zeile 459)
- [test_brief_is_retried_after_a_crash_following_the_claim_and_honours_unsubscribe](../../tests/test_watch_review_regressions.py#L484) (Zeile 484)
- [test_topic_run_stages_follower_items_in_the_run_transaction](../../tests/test_watch_review_regressions.py#L523) (Zeile 523)
- [test_outbox_retry_scan_survives_a_missing_composite_index](../../tests/test_watch_review_regressions.py#L548) (Zeile 548)

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

# Inventar der Produkt- und Betriebsdateien

[Einstieg und Scope](README.md) · [Maschinenlesbar mit Hashes und Python-Symbolen](sources.json)

269 Dateien, 128.351 physische Quellzeilen. Jede Datei ist mindestens einem Verhaltensbereich zugeordnet. Das ist ein Vollständigkeitscheck der Auswahl, kein Beweis für jede Funktion/Stylesheetregel. Direkte Testreferenzen sind ausschließlich Suchkandidaten aus dem vorherigen Testinventar. Null direkte Referenzen können trotzdem indirekte Tests bedeuten. Alle positiven Testbelege stehen in der Matrix/dem Dateikatalog.

Pythonspalte: ausgeführte Statements/Statements und ausgeführte Branches/Branches des regulären Branchlaufs; bei null Branches „—“, bei nicht instrumentierter Datei „nicht gemessen“. Vorhandene ausgeführte Statements können Moduldefinitionen/Imports sein.

| Datei | Zeilen | Verträge | Direkte Testreferenzen | Python-Ausführung |
|---|---:|---|---:|---|
| [.github/workflows/publish-consensus.yml](../../../.github/workflows/publish-consensus.yml) | 48 | [BUILD-03](matrix.md#build-03) | 0 | nicht gemessen |
| [.github/workflows/publisher-tests.yml](../../../.github/workflows/publisher-tests.yml) | 22 | [BUILD-03](matrix.md#build-03) | 0 | nicht gemessen |
| [.github/workflows/restart-render.yml](../../../.github/workflows/restart-render.yml) | 20 | [BUILD-03](matrix.md#build-03) | 0 | nicht gemessen |
| [app/api/routers/admin.py](../../../app/api/routers/admin.py) | 1696 | [API-01](matrix.md#api-01), [SHARE-03](matrix.md#share-03), [SEO-03](matrix.md#seo-03), [ADMIN-01](matrix.md#admin-01) | 12 | 673/884 Statements; 195/256 Branches |
| [app/api/routers/agent.py](../../../app/api/routers/agent.py) | 377 | [AGENT-02](matrix.md#agent-02), [AGENT-04](matrix.md#agent-04) | 6 | 249/287 Statements; 55/70 Branches |
| [app/api/routers/api_v1.py](../../../app/api/routers/api_v1.py) | 783 | [API-01](matrix.md#api-01), [API-02](matrix.md#api-02), [API-03](matrix.md#api-03), [API-04](matrix.md#api-04), [SRC-04](matrix.md#src-04) | 1 | 261/356 Statements; 32/56 Branches |
| [app/api/routers/auth.py](../../../app/api/routers/auth.py) | 166 | [AUTH-01](matrix.md#auth-01), [AUTH-02](matrix.md#auth-02) | 1 | 79/95 Statements; 13/22 Branches |
| [app/api/routers/bookmarks.py](../../../app/api/routers/bookmarks.py) | 927 | [CHAT-04](matrix.md#chat-04) | 4 | 397/473 Statements; 79/116 Branches |
| [app/api/routers/chat.py](../../../app/api/routers/chat.py) | 2084 | [QUOTA-01](matrix.md#quota-01), [CHAT-02](matrix.md#chat-02), [CONS-01](matrix.md#cons-01), [CONS-04](matrix.md#cons-04), [CONS-05](matrix.md#cons-05) | 19 | 671/809 Statements; 222/284 Branches |
| [app/api/routers/chat_history.py](../../../app/api/routers/chat_history.py) | 461 | [CHAT-01](matrix.md#chat-01), [CHAT-03](matrix.md#chat-03) | 3 | 211/243 Statements; 37/52 Branches |
| [app/api/routers/client_errors.py](../../../app/api/routers/client_errors.py) | 168 | [OPS-03](matrix.md#ops-03) | 1 | 81/89 Statements; 36/44 Branches |
| [app/api/routers/pages.py](../../../app/api/routers/pages.py) | 632 | [SEO-05](matrix.md#seo-05), [DATA-01](matrix.md#data-01) | 9 | 258/325 Statements; 57/70 Branches |
| [app/api/routers/share.py](../../../app/api/routers/share.py) | 943 | [SHARE-01](matrix.md#share-01), [SHARE-02](matrix.md#share-02), [SHARE-03](matrix.md#share-03), [SHARE-04](matrix.md#share-04) | 3 | 334/415 Statements; 96/118 Branches |
| [app/api/routers/source_checks.py](../../../app/api/routers/source_checks.py) | 150 | [API-03](matrix.md#api-03), [SRC-04](matrix.md#src-04) | 1 | 101/115 Statements; 30/38 Branches |
| [app/api/routers/topics.py](../../../app/api/routers/topics.py) | 722 | [TOPIC-01](matrix.md#topic-01), [TOPIC-04](matrix.md#topic-04) | 3 | 229/355 Statements; 34/62 Branches |
| [app/api/routers/users.py](../../../app/api/routers/users.py) | 485 | [AUTH-03](matrix.md#auth-03), [QUOTA-01](matrix.md#quota-01), [QUOTA-02](matrix.md#quota-02), [MEM-01](matrix.md#mem-01), [MEM-02](matrix.md#mem-02) | 5 | 168/234 Statements; 17/26 Branches |
| [app/api/routers/watch.py](../../../app/api/routers/watch.py) | 337 | [WATCH-01](matrix.md#watch-01), [WATCH-03](matrix.md#watch-03), [WATCH-04](matrix.md#watch-04), [WATCH-05](matrix.md#watch-05) | 1 | 124/215 Statements; 10/16 Branches |
| [app/core/assets.py](../../../app/core/assets.py) | 252 | [BUILD-01](matrix.md#build-01) | 3 | 111/128 Statements; 26/36 Branches |
| [app/core/background_tasks.py](../../../app/core/background_tasks.py) | 138 | [OPS-01](matrix.md#ops-01) | 1 | 60/68 Statements; 8/12 Branches |
| [app/core/concurrency.py](../../../app/core/concurrency.py) | 75 | [OPS-01](matrix.md#ops-01) | 1 | 23/23 Statements; 2/2 Branches |
| [app/core/config.py](../../../app/core/config.py) | 2086 | [LLM-01](matrix.md#llm-01), [ADMIN-01](matrix.md#admin-01) | 33 | 775/808 Statements; 206/234 Branches |
| [app/core/e2e_profile.py](../../../app/core/e2e_profile.py) | 84 | [OPS-01](matrix.md#ops-01) | 5 | 28/37 Statements; 7/12 Branches |
| [app/core/entitlements.py](../../../app/core/entitlements.py) | 107 | [AUTH-02](matrix.md#auth-02), [QUOTA-02](matrix.md#quota-02) | 1 | 43/45 Statements; 3/4 Branches |
| [app/core/observability.py](../../../app/core/observability.py) | 162 | [OPS-03](matrix.md#ops-03) | 2 | 83/85 Statements; 9/10 Branches |
| [app/core/openrouter_contract.py](../../../app/core/openrouter_contract.py) | 29 | [LLM-01](matrix.md#llm-01) | 0 | 12/12 Statements; — Branches |
| [app/core/rate_limit.py](../../../app/core/rate_limit.py) | 93 | [QUOTA-02](matrix.md#quota-02) | 26 | 45/52 Statements; 11/20 Branches |
| [app/core/request_limits.py](../../../app/core/request_limits.py) | 128 | [OPS-02](matrix.md#ops-02) | 1 | 51/74 Statements; 20/30 Branches |
| [app/core/security.py](../../../app/core/security.py) | 389 | [OPS-02](matrix.md#ops-02), [AUTH-02](matrix.md#auth-02) | 8 | 160/185 Statements; 35/50 Branches |
| [app/core/seo_entity.py](../../../app/core/seo_entity.py) | 108 | [SEO-05](matrix.md#seo-05) | 1 | 25/25 Statements; 1/2 Branches |
| [app/core/site.py](../../../app/core/site.py) | 25 | [SEO-05](matrix.md#seo-05) | 1 | 15/15 Statements; 6/6 Branches |
| [app/core/version.py](../../../app/core/version.py) | 107 | [BUILD-01](matrix.md#build-01) | 1 | 37/53 Statements; 7/20 Branches |
| [app/services/account_deletion.py](../../../app/services/account_deletion.py) | 299 | [AUTH-03](matrix.md#auth-03) | 5 | 108/174 Statements; 19/48 Branches |
| [app/services/account_tier.py](../../../app/services/account_tier.py) | 224 | [AUTH-02](matrix.md#auth-02), [QUOTA-02](matrix.md#quota-02) | 1 | 101/117 Statements; 14/16 Branches |
| [app/services/agent_budget_config.py](../../../app/services/agent_budget_config.py) | 100 | [AGENT-01](matrix.md#agent-01), [ADMIN-01](matrix.md#admin-01) | 2 | 70/75 Statements; 15/20 Branches |
| [app/services/agent_comparison.py](../../../app/services/agent_comparison.py) | 436 | [AGENT-02](matrix.md#agent-02) | 7 | 231/243 Statements; 64/76 Branches |
| [app/services/agent_contradictions.py](../../../app/services/agent_contradictions.py) | 111 | [AGENT-02](matrix.md#agent-02) | 1 | 55/62 Statements; 11/16 Branches |
| [app/services/agent_costs.py](../../../app/services/agent_costs.py) | 152 | [AGENT-01](matrix.md#agent-01) | 6 | 94/96 Statements; 26/28 Branches |
| [app/services/agent_delegation.py](../../../app/services/agent_delegation.py) | 915 | [AGENT-03](matrix.md#agent-03) | 5 | 667/721 Statements; 221/264 Branches |
| [app/services/agent_delegation_config.py](../../../app/services/agent_delegation_config.py) | 76 | [AGENT-03](matrix.md#agent-03) | 4 | 18/22 Statements; 10/14 Branches |
| [app/services/agent_loop.py](../../../app/services/agent_loop.py) | 193 | [AGENT-02](matrix.md#agent-02) | 2 | 148/158 Statements; 35/44 Branches |
| [app/services/agent_policy.py](../../../app/services/agent_policy.py) | 67 | [AGENT-02](matrix.md#agent-02) | 9 | 41/41 Statements; 4/4 Branches |
| [app/services/agent_progress.py](../../../app/services/agent_progress.py) | 88 | [AGENT-05](matrix.md#agent-05) | 1 | 68/69 Statements; 29/30 Branches |
| [app/services/agent_provider_limits.py](../../../app/services/agent_provider_limits.py) | 90 | [AGENT-01](matrix.md#agent-01) | 7 | 64/64 Statements; 24/24 Branches |
| [app/services/agent_quota.py](../../../app/services/agent_quota.py) | 117 | [AGENT-01](matrix.md#agent-01) | 9 | 69/69 Statements; 10/10 Branches |
| [app/services/agent_runs.py](../../../app/services/agent_runs.py) | 367 | [AGENT-01](matrix.md#agent-01), [AGENT-04](matrix.md#agent-04) | 4 | 263/274 Statements; 103/120 Branches |
| [app/services/agent_runtime.py](../../../app/services/agent_runtime.py) | 73 | [AGENT-04](matrix.md#agent-04) | 3 | 49/50 Statements; 9/10 Branches |
| [app/services/agent_sessions.py](../../../app/services/agent_sessions.py) | 401 | [AGENT-01](matrix.md#agent-01), [AGENT-03](matrix.md#agent-03), [AGENT-04](matrix.md#agent-04) | 1 | 290/313 Statements; 96/122 Branches |
| [app/services/agent_tokens.py](../../../app/services/agent_tokens.py) | 39 | [AGENT-01](matrix.md#agent-01) | 2 | 21/22 Statements; 1/2 Branches |
| [app/services/agent_tools.py](../../../app/services/agent_tools.py) | 91 | [AGENT-02](matrix.md#agent-02) | 4 | 55/57 Statements; 12/14 Branches |
| [app/services/api_account_cleanup.py](../../../app/services/api_account_cleanup.py) | 208 | [AUTH-03](matrix.md#auth-03), [API-01](matrix.md#api-01) | 2 | 54/119 Statements; 5/24 Branches |
| [app/services/api_consensus_runner.py](../../../app/services/api_consensus_runner.py) | 398 | [API-02](matrix.md#api-02) | 3 | 120/224 Statements; 15/60 Branches |
| [app/services/api_key_repository.py](../../../app/services/api_key_repository.py) | 200 | [API-01](matrix.md#api-01) | 2 | 98/122 Statements; 20/30 Branches |
| [app/services/api_run_repository.py](../../../app/services/api_run_repository.py) | 403 | [API-02](matrix.md#api-02) | 2 | 165/225 Statements; 33/70 Branches |
| [app/services/benchmark_reports.py](../../../app/services/benchmark_reports.py) | 128 | [BENCH-03](matrix.md#bench-03) | 2 | 55/71 Statements; 13/24 Branches |
| [app/services/chat_context.py](../../../app/services/chat_context.py) | 1222 | [CHAT-03](matrix.md#chat-03) | 1 | 469/535 Statements; 154/214 Branches |
| [app/services/chat_store.py](../../../app/services/chat_store.py) | 1587 | [CHAT-01](matrix.md#chat-01), [CHAT-02](matrix.md#chat-02) | 14 | 733/808 Statements; 292/350 Branches |
| [app/services/claim_ledger.py](../../../app/services/claim_ledger.py) | 620 | [TOPIC-03](matrix.md#topic-03), [TOPIC-05](matrix.md#topic-05) | 1 | 273/283 Statements; 117/130 Branches |
| [app/services/consensus_pipeline.py](../../../app/services/consensus_pipeline.py) | 222 | [CONS-01](matrix.md#cons-01) | 4 | 56/60 Statements; 12/16 Branches |
| [app/services/contradiction_verification.py](../../../app/services/contradiction_verification.py) | 543 | [SRC-02](matrix.md#src-02) | 3 | 397/411 Statements; 180/198 Branches |
| [app/services/differences_stats.py](../../../app/services/differences_stats.py) | 202 | [DATA-01](matrix.md#data-01) | 1 | 39/59 Statements; 17/26 Branches |
| [app/services/drift_signal.py](../../../app/services/drift_signal.py) | 130 | [WATCH-02](matrix.md#watch-02), [TOPIC-03](matrix.md#topic-03) | 1 | 53/53 Statements; 17/18 Branches |
| [app/services/favicons.py](../../../app/services/favicons.py) | 113 | [TOPIC-04](matrix.md#topic-04) | 1 | 60/75 Statements; 12/20 Branches |
| [app/services/follow_challenges.py](../../../app/services/follow_challenges.py) | 201 | [WATCH-03](matrix.md#watch-03) | 3 | 81/97 Statements; 16/24 Branches |
| [app/services/google_search_console.py](../../../app/services/google_search_console.py) | 335 | [SEO-01](matrix.md#seo-01) | 1 | 115/149 Statements; 19/28 Branches |
| [app/services/history_view.py](../../../app/services/history_view.py) | 129 | [SHARE-02](matrix.md#share-02), [TOPIC-03](matrix.md#topic-03) | 1 | 58/60 Statements; 26/28 Branches |
| [app/services/llm/agent_client.py](../../../app/services/llm/agent_client.py) | 531 | [LLM-02](matrix.md#llm-02), [AGENT-02](matrix.md#agent-02) | 21 | 350/378 Statements; 160/186 Branches |
| [app/services/llm/agent_model_catalog.json](../../../app/services/llm/agent_model_catalog.json) | 1054 | [LLM-01](matrix.md#llm-01) | 0 | nicht gemessen |
| [app/services/llm/agent_model_metadata.py](../../../app/services/llm/agent_model_metadata.py) | 90 | [LLM-01](matrix.md#llm-01) | 1 | 69/75 Statements; 20/26 Branches |
| [app/services/llm/attachments.py](../../../app/services/llm/attachments.py) | 618 | [UI-05](matrix.md#ui-05) | 2 | 299/362 Statements; 121/158 Branches |
| [app/services/llm/base.py](../../../app/services/llm/base.py) | 71 | [LLM-01](matrix.md#llm-01) | 6 | 26/27 Statements; 3/4 Branches |
| [app/services/llm/citations.py](../../../app/services/llm/citations.py) | 336 | [CONS-03](matrix.md#cons-03) | 5 | 146/182 Statements; 55/76 Branches |
| [app/services/llm/consensus_citations.py](../../../app/services/llm/consensus_citations.py) | 161 | [CONS-03](matrix.md#cons-03) | 1 | 130/132 Statements; 61/62 Branches |
| [app/services/llm/consensus_engine.py](../../../app/services/llm/consensus_engine.py) | 2657 | [CONS-01](matrix.md#cons-01), [CONS-02](matrix.md#cons-02), [TOPIC-02](matrix.md#topic-02) | 14 | 1078/1244 Statements; 406/518 Branches |
| [app/services/llm/consensus_parsing.py](../../../app/services/llm/consensus_parsing.py) | 94 | [CONS-02](matrix.md#cons-02) | 0 | 73/82 Statements; 39/50 Branches |
| [app/services/llm/consensus_scoring.py](../../../app/services/llm/consensus_scoring.py) | 88 | [CONS-02](matrix.md#cons-02) | 2 | 50/50 Statements; 22/22 Branches |
| [app/services/llm/coverage_judge.py](../../../app/services/llm/coverage_judge.py) | 335 | [CONS-02](matrix.md#cons-02), [SRC-02](matrix.md#src-02) | 1 | 80/90 Statements; 31/40 Branches |
| [app/services/llm/credentials.py](../../../app/services/llm/credentials.py) | 24 | [LLM-01](matrix.md#llm-01) | 2 | 11/11 Statements; — Branches |
| [app/services/llm/engines.py](../../../app/services/llm/engines.py) | 300 | [LLM-01](matrix.md#llm-01) | 18 | 116/119 Statements; 30/32 Branches |
| [app/services/llm/mock_llm.py](../../../app/services/llm/mock_llm.py) | 215 | [LLM-02](matrix.md#llm-02) | 1 | 60/83 Statements; 16/30 Branches |
| [app/services/llm/provider_runtime.py](../../../app/services/llm/provider_runtime.py) | 369 | [LLM-02](matrix.md#llm-02) | 18 | 224/236 Statements; 41/50 Branches |
| [app/services/llm/provider_transport.py](../../../app/services/llm/provider_transport.py) | 158 | [LLM-01](matrix.md#llm-01) | 4 | 62/64 Statements; 9/10 Branches |
| [app/services/llm/resolve_engine.py](../../../app/services/llm/resolve_engine.py) | 211 | [CONS-04](matrix.md#cons-04) | 2 | 88/90 Statements; 29/32 Branches |
| [app/services/llm/streaming.py](../../../app/services/llm/streaming.py) | 473 | [LLM-02](matrix.md#llm-02) | 5 | 233/270 Statements; 73/102 Branches |
| [app/services/llm/task_transport.py](../../../app/services/llm/task_transport.py) | 18 | [LLM-01](matrix.md#llm-01) | 1 | 9/9 Statements; — Branches |
| [app/services/mailer.py](../../../app/services/mailer.py) | 720 | [WATCH-03](matrix.md#watch-03), [WATCH-04](matrix.md#watch-04), [WATCH-05](matrix.md#watch-05) | 3 | 239/277 Statements; 37/52 Branches |
| [app/services/memory_edit.py](../../../app/services/memory_edit.py) | 753 | [MEM-02](matrix.md#mem-02) | 1 | 289/340 Statements; 69/108 Branches |
| [app/services/og_image.py](../../../app/services/og_image.py) | 178 | [SHARE-04](matrix.md#share-04) | 0 | 92/117 Statements; 17/28 Branches |
| [app/services/opinion_map.py](../../../app/services/opinion_map.py) | 342 | [WATCH-02](matrix.md#watch-02), [TOPIC-03](matrix.md#topic-03) | 2 | 181/209 Statements; 90/122 Branches |
| [app/services/persistence_guard.py](../../../app/services/persistence_guard.py) | 388 | [AUTH-03](matrix.md#auth-03), [CHAT-04](matrix.md#chat-04), [DATA-01](matrix.md#data-01) | 9 | 196/230 Statements; 44/68 Branches |
| [app/services/prompt_config.py](../../../app/services/prompt_config.py) | 161 | [ADMIN-01](matrix.md#admin-01) | 6 | 112/119 Statements; 25/32 Branches |
| [app/services/prompt_defaults.py](../../../app/services/prompt_defaults.py) | 95 | [ADMIN-01](matrix.md#admin-01) | 0 | 4/4 Statements; — Branches |
| [app/services/public_markdown.py](../../../app/services/public_markdown.py) | 225 | [SHARE-02](matrix.md#share-02) | 3 | 121/126 Statements; 39/42 Branches |
| [app/services/publisher_config.py](../../../app/services/publisher_config.py) | 235 | [API-04](matrix.md#api-04), [SEO-04](matrix.md#seo-04), [ADMIN-01](matrix.md#admin-01) | 2 | 60/69 Statements; 10/16 Branches |
| [app/services/registration.py](../../../app/services/registration.py) | 85 | [AUTH-01](matrix.md#auth-01) | 1 | 35/40 Statements; 2/2 Branches |
| [app/services/retention_maintenance.py](../../../app/services/retention_maintenance.py) | 36 | [OPS-01](matrix.md#ops-01) | 1 | 19/21 Statements; — Branches |
| [app/services/seo_data.py](../../../app/services/seo_data.py) | 577 | [SEO-01](matrix.md#seo-01), [SEO-02](matrix.md#seo-02), [SEO-04](matrix.md#seo-04) | 1 | 235/295 Statements; 65/88 Branches |
| [app/services/seo_dossier.py](../../../app/services/seo_dossier.py) | 312 | [SEO-02](matrix.md#seo-02) | 1 | 106/129 Statements; 25/40 Branches |
| [app/services/seo_recommendation.py](../../../app/services/seo_recommendation.py) | 578 | [SEO-03](matrix.md#seo-03) | 1 | 199/244 Statements; 55/76 Branches |
| [app/services/seo_repository.py](../../../app/services/seo_repository.py) | 459 | [SEO-02](matrix.md#seo-02) | 1 | 141/289 Statements; 51/142 Branches |
| [app/services/seo_weekly_review.py](../../../app/services/seo_weekly_review.py) | 1340 | [SEO-03](matrix.md#seo-03), [SEO-04](matrix.md#seo-04) | 1 | 495/689 Statements; 126/214 Branches |
| [app/services/share_snapshots.py](../../../app/services/share_snapshots.py) | 1973 | [API-04](matrix.md#api-04), [SHARE-01](matrix.md#share-01), [SHARE-03](matrix.md#share-03) | 13 | 882/1023 Statements; 335/430 Branches |
| [app/services/source_catalog.py](../../../app/services/source_catalog.py) | 226 | [CONS-03](matrix.md#cons-03) | 1 | 165/169 Statements; 72/76 Branches |
| [app/services/source_check_jobs.py](../../../app/services/source_check_jobs.py) | 443 | [API-03](matrix.md#api-03), [SRC-03](matrix.md#src-03) | 7 | 265/316 Statements; 76/96 Branches |
| [app/services/source_check_repository.py](../../../app/services/source_check_repository.py) | 711 | [SRC-03](matrix.md#src-03) | 6 | 490/520 Statements; 175/204 Branches |
| [app/services/source_documents.py](../../../app/services/source_documents.py) | 274 | [SRC-01](matrix.md#src-01) | 4 | 182/219 Statements; 61/92 Branches |
| [app/services/source_verification.py](../../../app/services/source_verification.py) | 815 | [SRC-01](matrix.md#src-01), [SRC-02](matrix.md#src-02) | 11 | 552/595 Statements; 193/220 Branches |
| [app/services/telegram_notifier.py](../../../app/services/telegram_notifier.py) | 398 | [OPS-03](matrix.md#ops-03) | 1 | 202/235 Statements; 61/82 Branches |
| [app/services/telegram_watch.py](../../../app/services/telegram_watch.py) | 559 | [WATCH-04](matrix.md#watch-04) | 1 | 251/347 Statements; 52/102 Branches |
| [app/services/topic_finding.py](../../../app/services/topic_finding.py) | 254 | [TOPIC-03](matrix.md#topic-03) | 1 | 116/121 Statements; 53/58 Branches |
| [app/services/topic_pipeline.py](../../../app/services/topic_pipeline.py) | 123 | [TOPIC-02](matrix.md#topic-02) | 3 | 44/47 Statements; 10/14 Branches |
| [app/services/topic_runner.py](../../../app/services/topic_runner.py) | 322 | [TOPIC-02](matrix.md#topic-02) | 3 | 84/147 Statements; 18/48 Branches |
| [app/services/topics.py](../../../app/services/topics.py) | 1334 | [TOPIC-01](matrix.md#topic-01), [TOPIC-04](matrix.md#topic-04) | 3 | 530/679 Statements; 170/262 Branches |
| [app/services/usage_repository.py](../../../app/services/usage_repository.py) | 995 | [QUOTA-01](matrix.md#quota-01) | 7 | 416/460 Statements; 111/142 Branches |
| [app/services/user_memory.py](../../../app/services/user_memory.py) | 470 | [CHAT-03](matrix.md#chat-03), [MEM-01](matrix.md#mem-01) | 3 | 222/239 Statements; 65/76 Branches |
| [app/services/watch_brief.py](../../../app/services/watch_brief.py) | 325 | [WATCH-05](matrix.md#watch-05) | 2 | 181/206 Statements; 43/52 Branches |
| [app/services/watch_followers.py](../../../app/services/watch_followers.py) | 212 | [WATCH-03](matrix.md#watch-03) | 1 | 104/109 Statements; 25/30 Branches |
| [app/services/watch_scheduler.py](../../../app/services/watch_scheduler.py) | 680 | [WATCH-02](matrix.md#watch-02), [WATCH-05](matrix.md#watch-05) | 4 | 243/323 Statements; 69/104 Branches |
| [app/services/watch_service.py](../../../app/services/watch_service.py) | 1686 | [WATCH-01](matrix.md#watch-01), [WATCH-02](matrix.md#watch-02) | 3 | 745/894 Statements; 216/298 Branches |
| [benchmark/__init__.py](../../../benchmark/__init__.py) | 7 | [BENCH-02](matrix.md#bench-02) | 7 | 0/0 Statements; — Branches |
| [benchmark/__main__.py](../../../benchmark/__main__.py) | 345 | [BENCH-02](matrix.md#bench-02) | 1 | 151/183 Statements; 50/66 Branches |
| [benchmark/audit.py](../../../benchmark/audit.py) | 120 | [BENCH-01](matrix.md#bench-01) | 2 | 45/46 Statements; 17/18 Branches |
| [benchmark/config.py](../../../benchmark/config.py) | 159 | [BENCH-01](matrix.md#bench-01) | 3 | 46/48 Statements; 3/4 Branches |
| [benchmark/cost.py](../../../benchmark/cost.py) | 29 | [BENCH-01](matrix.md#bench-01) | 0 | 13/13 Statements; 2/2 Branches |
| [benchmark/dataset.py](../../../benchmark/dataset.py) | 189 | [BENCH-01](matrix.md#bench-01) | 1 | 53/83 Statements; 14/30 Branches |
| [benchmark/parse.py](../../../benchmark/parse.py) | 74 | [BENCH-01](matrix.md#bench-01) | 1 | 30/31 Statements; 11/12 Branches |
| [benchmark/prompt.py](../../../benchmark/prompt.py) | 73 | [BENCH-01](matrix.md#bench-01) | 1 | 21/26 Statements; 6/10 Branches |
| [benchmark/report_reader.py](../../../benchmark/report_reader.py) | 191 | [BENCH-03](matrix.md#bench-03) | 3 | 85/100 Statements; 27/36 Branches |
| [benchmark/results.py](../../../benchmark/results.py) | 222 | [BENCH-03](matrix.md#bench-03) | 1 | 116/116 Statements; 52/54 Branches |
| [benchmark/run_experiment.py](../../../benchmark/run_experiment.py) | 124 | [BENCH-02](matrix.md#bench-02) | 0 | 0/55 Statements; 0/10 Branches |
| [benchmark/run_sample.py](../../../benchmark/run_sample.py) | 118 | [BENCH-02](matrix.md#bench-02) | 0 | 0/58 Statements; 0/10 Branches |
| [benchmark/runner.py](../../../benchmark/runner.py) | 1084 | [BENCH-02](matrix.md#bench-02) | 6 | 407/437 Statements; 97/120 Branches |
| [benchmark/transport.py](../../../benchmark/transport.py) | 206 | [BENCH-01](matrix.md#bench-01) | 1 | 69/74 Statements; 7/10 Branches |
| [dev.ps1](../../../dev.ps1) | 180 | [BUILD-02](matrix.md#build-02) | 0 | nicht gemessen |
| [firebase.json](../../../firebase.json) | 16 | [BUILD-02](matrix.md#build-02), [AUTH-05](matrix.md#auth-05) | 0 | nicht gemessen |
| [firestore.indexes.json](../../../firestore.indexes.json) | 63 | [BUILD-02](matrix.md#build-02) | 0 | nicht gemessen |
| [firestore.rules](../../../firestore.rules) | 34 | [AUTH-05](matrix.md#auth-05) | 0 | nicht gemessen |
| [main.py](../../../main.py) | 299 | [OPS-01](matrix.md#ops-01), [OPS-02](matrix.md#ops-02), [OPS-03](matrix.md#ops-03) | 7 | 83/116 Statements; 5/10 Branches |
| [package.json](../../../package.json) | 20 | [BUILD-01](matrix.md#build-01) | 0 | nicht gemessen |
| [scripts/backfill_claim_keys.py](../../../scripts/backfill_claim_keys.py) | 110 | [TOOLS-01](matrix.md#tools-01) | 0 | 0/61 Statements; 0/24 Branches |
| [scripts/build_frontend.mjs](../../../scripts/build_frontend.mjs) | 303 | [BUILD-01](matrix.md#build-01) | 1 | nicht gemessen |
| [scripts/evaluate_agent_delegation.py](../../../scripts/evaluate_agent_delegation.py) | 186 | [TOOLS-02](matrix.md#tools-02) | 1 | 50/124 Statements; 1/22 Branches |
| [scripts/evaluate_source_verification.py](../../../scripts/evaluate_source_verification.py) | 102 | [TOOLS-02](matrix.md#tools-02) | 1 | 12/43 Statements; 1/8 Branches |
| [scripts/frontend-output.mjs](../../../scripts/frontend-output.mjs) | 69 | [BUILD-01](matrix.md#build-01) | 2 | nicht gemessen |
| [scripts/probe_agent_delegation.py](../../../scripts/probe_agent_delegation.py) | 80 | [TOOLS-02](matrix.md#tools-02) | 0 | 0/65 Statements; 0/16 Branches |
| [scripts/publish_consensus.py](../../../scripts/publish_consensus.py) | 585 | [BUILD-03](matrix.md#build-03) | 1 | 211/271 Statements; 62/88 Branches |
| [scripts/render_watch_preview.py](../../../scripts/render_watch_preview.py) | 201 | [TOOLS-02](matrix.md#tools-02) | 0 | 0/51 Statements; 0/4 Branches |
| [scripts/repair_agent_allowance.py](../../../scripts/repair_agent_allowance.py) | 47 | [TOOLS-01](matrix.md#tools-01) | 0 | 0/37 Statements; 0/8 Branches |
| [scripts/vendor_frontend.mjs](../../../scripts/vendor_frontend.mjs) | 36 | [BUILD-01](matrix.md#build-01) | 0 | nicht gemessen |
| [static/app-ui.js](../../../static/app-ui.js) | 355 | [UI-06](matrix.md#ui-06), [UI-07](matrix.md#ui-07) | 3 | nicht gemessen |
| [static/css/admin-benchmark.css](../../../static/css/admin-benchmark.css) | 277 | [UI-07](matrix.md#ui-07) | 1 | nicht gemessen |
| [static/css/admin.css](../../../static/css/admin.css) | 793 | [UI-07](matrix.md#ui-07) | 0 | nicht gemessen |
| [static/css/agent-chat.css](../../../static/css/agent-chat.css) | 380 | [UI-07](matrix.md#ui-07) | 0 | nicht gemessen |
| [static/css/base.css](../../../static/css/base.css) | 145 | [UI-07](matrix.md#ui-07) | 0 | nicht gemessen |
| [static/css/benchmark.css](../../../static/css/benchmark.css) | 526 | [UI-07](matrix.md#ui-07) | 0 | nicht gemessen |
| [static/css/chat-scroll.css](../../../static/css/chat-scroll.css) | 25 | [UI-07](matrix.md#ui-07) | 0 | nicht gemessen |
| [static/css/components-attachment-viewer.css](../../../static/css/components-attachment-viewer.css) | 401 | [UI-07](matrix.md#ui-07) | 0 | nicht gemessen |
| [static/css/components-consensus-insights.css](../../../static/css/components-consensus-insights.css) | 907 | [UI-07](matrix.md#ui-07) | 1 | nicht gemessen |
| [static/css/components-consensus-visuals.css](../../../static/css/components-consensus-visuals.css) | 394 | [UI-07](matrix.md#ui-07) | 1 | nicht gemessen |
| [static/css/components-consensus.css](../../../static/css/components-consensus.css) | 1841 | [UI-07](matrix.md#ui-07) | 1 | nicht gemessen |
| [static/css/components-controls.css](../../../static/css/components-controls.css) | 274 | [UI-07](matrix.md#ui-07) | 0 | nicht gemessen |
| [static/css/components-feedback.css](../../../static/css/components-feedback.css) | 246 | [UI-07](matrix.md#ui-07) | 1 | nicht gemessen |
| [static/css/components-input.css](../../../static/css/components-input.css) | 1260 | [UI-07](matrix.md#ui-07) | 4 | nicht gemessen |
| [static/css/components-memory-edit.css](../../../static/css/components-memory-edit.css) | 436 | [UI-07](matrix.md#ui-07) | 1 | nicht gemessen |
| [static/css/components-misc.css](../../../static/css/components-misc.css) | 385 | [UI-07](matrix.md#ui-07) | 1 | nicht gemessen |
| [static/css/components-modals.css](../../../static/css/components-modals.css) | 2027 | [UI-07](matrix.md#ui-07) | 2 | nicht gemessen |
| [static/css/components-model-picker.css](../../../static/css/components-model-picker.css) | 1189 | [UI-07](matrix.md#ui-07) | 0 | nicht gemessen |
| [static/css/components-watch.css](../../../static/css/components-watch.css) | 744 | [UI-07](matrix.md#ui-07) | 2 | nicht gemessen |
| [static/css/composer-attachments.css](../../../static/css/composer-attachments.css) | 102 | [UI-07](matrix.md#ui-07) | 0 | nicht gemessen |
| [static/css/consensus-engine.css](../../../static/css/consensus-engine.css) | 1055 | [UI-07](matrix.md#ui-07) | 0 | nicht gemessen |
| [static/css/demo-action.css](../../../static/css/demo-action.css) | 75 | [UI-07](matrix.md#ui-07) | 0 | nicht gemessen |
| [static/css/landing.css](../../../static/css/landing.css) | 3025 | [UI-07](matrix.md#ui-07) | 3 | nicht gemessen |
| [static/css/layout.css](../../../static/css/layout.css) | 1370 | [UI-07](matrix.md#ui-07) | 1 | nicht gemessen |
| [static/css/model-answer-reader.css](../../../static/css/model-answer-reader.css) | 691 | [UI-07](matrix.md#ui-07) | 0 | nicht gemessen |
| [static/css/model-pulse.css](../../../static/css/model-pulse.css) | 302 | [UI-07](matrix.md#ui-07) | 1 | nicht gemessen |
| [static/css/public-pages.css](../../../static/css/public-pages.css) | 3627 | [UI-07](matrix.md#ui-07) | 2 | nicht gemessen |
| [static/css/public-shell.css](../../../static/css/public-shell.css) | 506 | [UI-07](matrix.md#ui-07) | 0 | nicht gemessen |
| [static/css/public-tokens.css](../../../static/css/public-tokens.css) | 190 | [UI-07](matrix.md#ui-07) | 1 | nicht gemessen |
| [static/css/shell.css](../../../static/css/shell.css) | 4239 | [UI-07](matrix.md#ui-07) | 3 | nicht gemessen |
| [static/css/skeleton.css](../../../static/css/skeleton.css) | 84 | [UI-07](matrix.md#ui-07) | 0 | nicht gemessen |
| [static/css/source-verification.css](../../../static/css/source-verification.css) | 182 | [UI-07](matrix.md#ui-07) | 0 | nicht gemessen |
| [static/css/status-palette.css](../../../static/css/status-palette.css) | 31 | [UI-07](matrix.md#ui-07) | 0 | nicht gemessen |
| [static/css/topics.css](../../../static/css/topics.css) | 2350 | [UI-07](matrix.md#ui-07) | 0 | nicht gemessen |
| [static/css/typography.css](../../../static/css/typography.css) | 70 | [UI-07](matrix.md#ui-07) | 1 | nicht gemessen |
| [static/css/variables.css](../../../static/css/variables.css) | 228 | [UI-07](matrix.md#ui-07) | 1 | nicht gemessen |
| [static/demo.js](../../../static/demo.js) | 915 | [UI-08](matrix.md#ui-08) | 4 | nicht gemessen |
| [static/firebase.js](../../../static/firebase.js) | 2887 | [AUTH-04](matrix.md#auth-04), [CHAT-04](matrix.md#chat-04) | 12 | nicht gemessen |
| [static/js/admin-agent-budget.js](../../../static/js/admin-agent-budget.js) | 56 | [ADMIN-02](matrix.md#admin-02) | 1 | nicht gemessen |
| [static/js/admin-api.js](../../../static/js/admin-api.js) | 31 | [ADMIN-02](matrix.md#admin-02) | 0 | nicht gemessen |
| [static/js/admin-benchmark.js](../../../static/js/admin-benchmark.js) | 406 | [ADMIN-02](matrix.md#admin-02), [BENCH-03](matrix.md#bench-03) | 1 | nicht gemessen |
| [static/js/admin-config.js](../../../static/js/admin-config.js) | 12 | [ADMIN-02](matrix.md#admin-02) | 1 | nicht gemessen |
| [static/js/admin-prompt-config.js](../../../static/js/admin-prompt-config.js) | 143 | [ADMIN-02](matrix.md#admin-02) | 1 | nicht gemessen |
| [static/js/admin.js](../../../static/js/admin.js) | 3555 | [ADMIN-02](matrix.md#admin-02) | 6 | nicht gemessen |
| [static/js/agent-activity.js](../../../static/js/agent-activity.js) | 404 | [AGENT-05](matrix.md#agent-05) | 1 | nicht gemessen |
| [static/js/agent-answer-actions.js](../../../static/js/agent-answer-actions.js) | 87 | [AGENT-05](matrix.md#agent-05) | 1 | nicht gemessen |
| [static/js/agent-chat.js](../../../static/js/agent-chat.js) | 703 | [AGENT-05](matrix.md#agent-05) | 2 | nicht gemessen |
| [static/js/agent-delegation.js](../../../static/js/agent-delegation.js) | 477 | [AGENT-03](matrix.md#agent-03) | 1 | nicht gemessen |
| [static/js/agent-mode.js](../../../static/js/agent-mode.js) | 840 | [UI-02](matrix.md#ui-02) | 2 | nicht gemessen |
| [static/js/agent-review.js](../../../static/js/agent-review.js) | 368 | [AGENT-05](matrix.md#agent-05) | 2 | nicht gemessen |
| [static/js/analytics-opt-out.js](../../../static/js/analytics-opt-out.js) | 8 | [UI-09](matrix.md#ui-09) | 0 | nicht gemessen |
| [static/js/app-bootstrap.js](../../../static/js/app-bootstrap.js) | 84 | [UI-07](matrix.md#ui-07) | 2 | nicht gemessen |
| [static/js/app-core.js](../../../static/js/app-core.js) | 441 | [UI-02](matrix.md#ui-02), [UI-07](matrix.md#ui-07) | 7 | nicht gemessen |
| [static/js/app-dom-events.js](../../../static/js/app-dom-events.js) | 18 | [UI-06](matrix.md#ui-06), [UI-07](matrix.md#ui-07) | 0 | nicht gemessen |
| [static/js/app-init.js](../../../static/js/app-init.js) | 1906 | [UI-02](matrix.md#ui-02), [UI-06](matrix.md#ui-06) | 6 | nicht gemessen |
| [static/js/app-state.js](../../../static/js/app-state.js) | 91 | [UI-01](matrix.md#ui-01) | 6 | nicht gemessen |
| [static/js/attachments.js](../../../static/js/attachments.js) | 782 | [UI-05](matrix.md#ui-05) | 4 | nicht gemessen |
| [static/js/auth-bootstrap.js](../../../static/js/auth-bootstrap.js) | 75 | [AUTH-04](matrix.md#auth-04) | 1 | nicht gemessen |
| [static/js/auth-session-state.js](../../../static/js/auth-session-state.js) | 54 | [AUTH-04](matrix.md#auth-04) | 0 | nicht gemessen |
| [static/js/bundles.json](../../../static/js/bundles.json) | 141 | [UI-07](matrix.md#ui-07) | 2 | nicht gemessen |
| [static/js/chat-scroll.js](../../../static/js/chat-scroll.js) | 209 | [UI-06](matrix.md#ui-06) | 1 | nicht gemessen |
| [static/js/chat-session.js](../../../static/js/chat-session.js) | 595 | [CONS-05](matrix.md#cons-05), [UI-01](matrix.md#ui-01) | 1 | nicht gemessen |
| [static/js/composer-collapse.js](../../../static/js/composer-collapse.js) | 344 | [UI-05](matrix.md#ui-05), [UI-06](matrix.md#ui-06) | 0 | nicht gemessen |
| [static/js/composer-quote.js](../../../static/js/composer-quote.js) | 124 | [UI-05](matrix.md#ui-05) | 2 | nicht gemessen |
| [static/js/consensus-actions.js](../../../static/js/consensus-actions.js) | 360 | [CONS-04](matrix.md#cons-04) | 0 | nicht gemessen |
| [static/js/consensus-anchor.js](../../../static/js/consensus-anchor.js) | 310 | [UI-04](matrix.md#ui-04) | 8 | nicht gemessen |
| [static/js/consensus-insights.js](../../../static/js/consensus-insights.js) | 2637 | [SRC-05](matrix.md#src-05), [UI-04](matrix.md#ui-04) | 7 | nicht gemessen |
| [static/js/consensus-lifecycle.js](../../../static/js/consensus-lifecycle.js) | 257 | [CONS-05](matrix.md#cons-05), [UI-03](matrix.md#ui-03) | 1 | nicht gemessen |
| [static/js/consensus-progress.js](../../../static/js/consensus-progress.js) | 945 | [UI-03](matrix.md#ui-03) | 5 | nicht gemessen |
| [static/js/consensus-run.js](../../../static/js/consensus-run.js) | 1916 | [CONS-05](matrix.md#cons-05), [UI-04](matrix.md#ui-04) | 6 | nicht gemessen |
| [static/js/email-verify.js](../../../static/js/email-verify.js) | 163 | [AUTH-04](matrix.md#auth-04) | 1 | nicht gemessen |
| [static/js/error-reporter.js](../../../static/js/error-reporter.js) | 226 | [OPS-03](matrix.md#ops-03) | 1 | nicht gemessen |
| [static/js/feature-access.js](../../../static/js/feature-access.js) | 96 | [QUOTA-02](matrix.md#quota-02), [UI-02](matrix.md#ui-02) | 0 | nicht gemessen |
| [static/js/landing-insights.js](../../../static/js/landing-insights.js) | 429 | [UI-08](matrix.md#ui-08) | 0 | nicht gemessen |
| [static/js/landing-scenes.js](../../../static/js/landing-scenes.js) | 469 | [UI-08](matrix.md#ui-08) | 0 | nicht gemessen |
| [static/js/markdown-stream.js](../../../static/js/markdown-stream.js) | 341 | [UI-03](matrix.md#ui-03), [UI-04](matrix.md#ui-04) | 6 | nicht gemessen |
| [static/js/math-render.js](../../../static/js/math-render.js) | 175 | [UI-04](matrix.md#ui-04) | 2 | nicht gemessen |
| [static/js/memory-edit.js](../../../static/js/memory-edit.js) | 443 | [MEM-02](matrix.md#mem-02) | 1 | nicht gemessen |
| [static/js/mobile-header.js](../../../static/js/mobile-header.js) | 60 | [UI-06](matrix.md#ui-06) | 1 | nicht gemessen |
| [static/js/model-answer-reader.js](../../../static/js/model-answer-reader.js) | 977 | [UI-04](matrix.md#ui-04) | 2 | nicht gemessen |
| [static/js/model-picker.js](../../../static/js/model-picker.js) | 1171 | [UI-02](matrix.md#ui-02) | 4 | nicht gemessen |
| [static/js/model-pulse.js](../../../static/js/model-pulse.js) | 150 | [SEO-05](matrix.md#seo-05) | 2 | nicht gemessen |
| [static/js/query-send.js](../../../static/js/query-send.js) | 845 | [CONS-05](matrix.md#cons-05), [UI-02](matrix.md#ui-02) | 8 | nicht gemessen |
| [static/js/request-deadline.js](../../../static/js/request-deadline.js) | 36 | [UI-03](matrix.md#ui-03) | 3 | nicht gemessen |
| [static/js/run-registry.js](../../../static/js/run-registry.js) | 659 | [AUTH-04](matrix.md#auth-04), [UI-01](matrix.md#ui-01) | 7 | nicht gemessen |
| [static/js/run-view.js](../../../static/js/run-view.js) | 476 | [UI-01](matrix.md#ui-01) | 5 | nicht gemessen |
| [static/js/share-dialog.js](../../../static/js/share-dialog.js) | 380 | [SHARE-01](matrix.md#share-01), [WATCH-06](matrix.md#watch-06), [UI-06](matrix.md#ui-06) | 2 | nicht gemessen |
| [static/js/sidebar-quota.js](../../../static/js/sidebar-quota.js) | 245 | [AGENT-05](matrix.md#agent-05) | 2 | nicht gemessen |
| [static/js/source-verification.js](../../../static/js/source-verification.js) | 1245 | [SRC-05](matrix.md#src-05) | 4 | nicht gemessen |
| [static/js/sources.js](../../../static/js/sources.js) | 779 | [CONS-03](matrix.md#cons-03), [SRC-05](matrix.md#src-05) | 5 | nicht gemessen |
| [static/js/topic-page.js](../../../static/js/topic-page.js) | 120 | [TOPIC-05](matrix.md#topic-05) | 0 | nicht gemessen |
| [static/js/usage-limit.js](../../../static/js/usage-limit.js) | 388 | [QUOTA-02](matrix.md#quota-02) | 2 | nicht gemessen |
| [static/js/user-memory.js](../../../static/js/user-memory.js) | 347 | [MEM-01](matrix.md#mem-01) | 2 | nicht gemessen |
| [static/js/user-tier.js](../../../static/js/user-tier.js) | 218 | [QUOTA-02](matrix.md#quota-02) | 2 | nicht gemessen |
| [static/js/watch-state.js](../../../static/js/watch-state.js) | 41 | [WATCH-06](matrix.md#watch-06) | 3 | nicht gemessen |
| [static/js/watch.js](../../../static/js/watch.js) | 2113 | [WATCH-06](matrix.md#watch-06) | 6 | nicht gemessen |
| [static/style.css](../../../static/style.css) | 45 | [UI-07](matrix.md#ui-07) | 0 | nicht gemessen |
| [templates/about.html](../../../templates/about.html) | 241 | [SEO-05](matrix.md#seo-05) | 1 | nicht gemessen |
| [templates/admin.html](../../../templates/admin.html) | 679 | [SEO-05](matrix.md#seo-05), [ADMIN-02](matrix.md#admin-02) | 8 | nicht gemessen |
| [templates/admin_benchmark.html](../../../templates/admin_benchmark.html) | 41 | [SEO-05](matrix.md#seo-05), [ADMIN-02](matrix.md#admin-02) | 1 | nicht gemessen |
| [templates/ai-model-comparison.html](../../../templates/ai-model-comparison.html) | 180 | [SEO-05](matrix.md#seo-05) | 1 | nicht gemessen |
| [templates/benchmark.html](../../../templates/benchmark.html) | 405 | [SEO-05](matrix.md#seo-05) | 0 | nicht gemessen |
| [templates/consensus-engine.html](../../../templates/consensus-engine.html) | 540 | [SEO-05](matrix.md#seo-05), [UI-08](matrix.md#ui-08) | 2 | nicht gemessen |
| [templates/imprint.html](../../../templates/imprint.html) | 91 | [SEO-05](matrix.md#seo-05) | 0 | nicht gemessen |
| [templates/index.html](../../../templates/index.html) | 1490 | [SEO-05](matrix.md#seo-05), [UI-07](matrix.md#ui-07) | 10 | nicht gemessen |
| [templates/landing.html](../../../templates/landing.html) | 742 | [SEO-05](matrix.md#seo-05), [UI-08](matrix.md#ui-08) | 3 | nicht gemessen |
| [templates/model-pulse.html](../../../templates/model-pulse.html) | 147 | [SEO-05](matrix.md#seo-05) | 1 | nicht gemessen |
| [templates/partials/admin_prompt_config.html](../../../templates/partials/admin_prompt_config.html) | 48 | [SEO-05](matrix.md#seo-05), [ADMIN-02](matrix.md#admin-02) | 2 | nicht gemessen |
| [templates/partials/analytics.html](../../../templates/partials/analytics.html) | 19 | [SEO-05](matrix.md#seo-05), [UI-09](matrix.md#ui-09) | 0 | nicht gemessen |
| [templates/partials/composer_toolbar_mockup.html](../../../templates/partials/composer_toolbar_mockup.html) | 24 | [SEO-05](matrix.md#seo-05), [UI-08](matrix.md#ui-08) | 0 | nicht gemessen |
| [templates/partials/product_result_mockup.html](../../../templates/partials/product_result_mockup.html) | 60 | [SEO-05](matrix.md#seo-05), [UI-08](matrix.md#ui-08) | 0 | nicht gemessen |
| [templates/partials/public_footer.html](../../../templates/partials/public_footer.html) | 18 | [SEO-05](matrix.md#seo-05) | 1 | nicht gemessen |
| [templates/partials/public_nav.html](../../../templates/partials/public_nav.html) | 16 | [SEO-05](matrix.md#seo-05) | 2 | nicht gemessen |
| [templates/privacy.html](../../../templates/privacy.html) | 334 | [SEO-05](matrix.md#seo-05) | 0 | nicht gemessen |
| [templates/questions.html](../../../templates/questions.html) | 167 | [SHARE-02](matrix.md#share-02), [SEO-05](matrix.md#seo-05) | 0 | nicht gemessen |
| [templates/share.html](../../../templates/share.html) | 773 | [SHARE-02](matrix.md#share-02), [SEO-05](matrix.md#seo-05) | 3 | nicht gemessen |
| [templates/share_unavailable.html](../../../templates/share_unavailable.html) | 50 | [SHARE-02](matrix.md#share-02), [SEO-05](matrix.md#seo-05) | 0 | nicht gemessen |
| [templates/terms.html](../../../templates/terms.html) | 194 | [SEO-05](matrix.md#seo-05) | 0 | nicht gemessen |
| [templates/topic.html](../../../templates/topic.html) | 734 | [TOPIC-04](matrix.md#topic-04), [TOPIC-05](matrix.md#topic-05), [SEO-05](matrix.md#seo-05) | 0 | nicht gemessen |
| [templates/topics.html](../../../templates/topics.html) | 152 | [TOPIC-04](matrix.md#topic-04), [SEO-05](matrix.md#seo-05) | 0 | nicht gemessen |
| [vitest.config.mjs](../../../vitest.config.mjs) | 13 | [BUILD-02](matrix.md#build-02) | 0 | nicht gemessen |

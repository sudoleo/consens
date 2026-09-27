# Abdeckung und Abschnittsprotokoll

Referenz: `4d7c061036936b06bb98b2b306b2987a5844cde4`. Dieser Anhang dokumentiert die Prüftiefe, nicht Fehlerfreiheit. Der Hauptbericht ist [README.md](README.md), die isolierten Ausführungsbelege stehen in [BELEGE.md](BELEGE.md).

Die [Gegenprüfung vom 27. September 2026](GEGENPRUEFUNG.md) prüft alle 33 Befunde erneut gegen den unveränderten Produktcode. Sie ist eine befundbezogene zweite Lesung mit zusätzlichen Zustandsproben, kein behaupteter zweiter vollständiger Zeile-für-Zeile-Durchlauf aller hier aufgelisteten Dateien. Pfade, Bestandszahlen und Zeilenzahlen wurden erneut maschinell abgeglichen.

## Vorgehen und Grenzen

Die Produktlogik wurde modulweise in zusammenhängenden Abschnitten gelesen; Aufrufer, Persistenz, Fehlerpfade und Darstellung wurden anschließend über Modulgrenzen hinweg verbunden. Einzelne Suchtreffer dienten der Navigation und Gegenprüfung, nicht als Ersatz für die Prüfung ganzer Produktmodule. Längere Python-Kommentare/Docstrings und reine HTML-Kommentare wurden teilweise für die Lesedarstellung ausgeblendet; relevante Verträge wurden am Original gegengeprüft.

Der Umfang umfasst 115 Backend-Pythondateien einschließlich `main.py`, 60 eigene JavaScript-Dateien, 23 Templates, 24 Python-/JavaScript-Dateien unter `scripts/` und `benchmark/`, drei Workflows sowie den PowerShell-Einstieg. Leere Initialisierungsdateien zählen als Dateien, nicht als komplexe geprüfte Funktionen. Die unten angegebenen Zeilenzahlen sind Dateigrößen einschließlich Leerzeilen und Kommentare, keine Behauptung unabhängig getesteter Codezeilen.

**Bewusste Begrenzung:** Die 36 eigenen Stylesheets wurden strukturell auf Imports, responsive Bereiche sowie Sichtbarkeits-, Fokus- und Bewegungsregeln betrachtet; es gab weder eine vollständige manuelle Prüfung jeder CSS-Deklaration noch einen visuellen Durchlauf aller Ansichten. Generierte Bundles, vendorte Bibliotheksimplementierungen, Bilder, Fonts, komprimierte Tokenizerdaten und historische Artefakte wurden nicht wie eigener Produktcode Zeile für Zeile auditiert. Build-Eingänge, Sanitizer-Versionen und Ladereihenfolge wurden hingegen geprüft. `package-lock.json` dient als Auflösungsartefakt; kein vollständiges CVE-Audit aller Transitiven. Testdateien und Dokumente des parallelen Testaudits wurden nicht als Befundquelle verwendet. Die Architekturkarte wurde zur Orientierung gelesen; das übrige Dokumentationsarchiv war kein separater Reviewgegenstand.

## Fachliche Abschnitte

| Abschnitt | Verbundene Prüfung | Ergebnis / weiter zu |
|---|---|---|
| Einstieg, Auth, Rollen, Requestgrenzen | Lifespan → Middleware → Auth → Router; Mock-/Emulatorgrenzen, Fehlerantworten | R04; Deny-all-Firestore-Regeln und serverseitige Besitzerprüfung sind wichtige vorhandene Grenzen |
| API und Quoten | API-Key → Annahme/Idempotenz → Usage → Claim → Provider → Ergebnis → Löschung/Recovery | R03, R05; getrennte Lebenszyklen verursachen das Hauptproblem |
| Chats, Kontext, Bookmarks | Turn-Reserve → Kontextversion → Completion → Sidebar → Gesprächslöschung | R09–R11; Account-Lösch-Tombstones positiv, Einzelchat-Retry unvollständig |
| Memory | Profilread/-save → KI-Reserve → Apply/Undo → Kontolöschung | R12, R13, R23, R28; CAS im KI-Apply vorhanden, manueller Save ohne Baseline |
| Provider und Consensus | Credentials → Payload → Timeouts/Cancel → Streaming → Synthese → Judge/Scoring | R06, R08; gemeinsame Providertransporte und Budgets als gute Grundlage |
| Quellen und Attachments | MIME/Dateigröße → Extraktion → Quellenabruf → Belege → Zitat-ID → Rendering | R14, R21, R26, R31; Quellen-Netzwerkgrenzen und DOCX-/Bildschutz nicht mit PDF-Budget verwechseln |
| Agent und Delegation | Admission → Session/Run-Token → Reservation → Tool/Worker → Settlement → Recovery | R07, R29; vorhandene Fences erhalten, unbekannte Usage gesondert behandeln |
| Shares, Votes und Moderation | Pending-Result → Snapshot → Public HTML → Report/Indexierung → Widerruf | R01, R02, R09, R18, R19, R24 |
| Watches und Topics | Claim/Schedule → Pipeline → Änderungssignal → Speicherung → Versand → Versionen | R14–R17, R30, R33; lokale Einzelrun-Fences lösen globale Lease-/Outboxprobleme nicht |
| Frontend-Lebenszyklus | Auth → RunRegistry → Query → Stream → Ansichtwechsel → gespeicherter Chat | R20, R21, R23, R31; moderne Run-/Auth-Generationen als Vorbild für ältere Module |
| Admin, Konfiguration und SEO | Editorzustand → Admin-API → Runtime-Aktivierung → Collector → Weekly Review | R20, R22, R24, R25, R32 |
| Build, Betrieb und Benchmark | Bundlemanifest → Build/Publish → Scheduler-Workflows; Benchmark-Resume/Budget/Reports | R02, R27; atomare Build-Dateien und feste Modellmanifeste positiv, Auditkosten außerhalb Budget |
| Produkttexte und Styles | öffentliche Leistungs-/Datenaussagen mit Codepfaden verglichen; CSS strukturell | R18, R28, R32; keine juristische Konformitäts- oder vollständige Accessibility-Zertifizierung |

## Dateiweise Prüfliste

Alle Pfade sind relativ zum Repo-Root. Ein Eintrag bedeutet die jeweils ausgewiesene Prüftiefe; „keinen zusätzlichen Befund“ bedeutet ausdrücklich nicht „nachgewiesen fehlerfrei“.

### Backend — Einstieg, Core und alle Services

Abschnittsweise Quelltext-/Kontrollflussprüfung.

| Datei | Zeilen |
|---|---:|
| [main.py](../../main.py) | 299 |
| [app/api/routers/admin.py](../../app/api/routers/admin.py) | 1696 |
| [app/api/routers/agent.py](../../app/api/routers/agent.py) | 377 |
| [app/api/routers/api_v1.py](../../app/api/routers/api_v1.py) | 783 |
| [app/api/routers/auth.py](../../app/api/routers/auth.py) | 166 |
| [app/api/routers/bookmarks.py](../../app/api/routers/bookmarks.py) | 927 |
| [app/api/routers/chat.py](../../app/api/routers/chat.py) | 2084 |
| [app/api/routers/chat_history.py](../../app/api/routers/chat_history.py) | 461 |
| [app/api/routers/client_errors.py](../../app/api/routers/client_errors.py) | 168 |
| [app/api/routers/pages.py](../../app/api/routers/pages.py) | 632 |
| [app/api/routers/share.py](../../app/api/routers/share.py) | 943 |
| [app/api/routers/source_checks.py](../../app/api/routers/source_checks.py) | 150 |
| [app/api/routers/topics.py](../../app/api/routers/topics.py) | 722 |
| [app/api/routers/users.py](../../app/api/routers/users.py) | 485 |
| [app/api/routers/watch.py](../../app/api/routers/watch.py) | 337 |
| [app/core/assets.py](../../app/core/assets.py) | 252 |
| [app/core/background_tasks.py](../../app/core/background_tasks.py) | 138 |
| [app/core/concurrency.py](../../app/core/concurrency.py) | 75 |
| [app/core/config.py](../../app/core/config.py) | 2086 |
| [app/core/e2e_profile.py](../../app/core/e2e_profile.py) | 84 |
| [app/core/entitlements.py](../../app/core/entitlements.py) | 107 |
| [app/core/observability.py](../../app/core/observability.py) | 162 |
| [app/core/openrouter_contract.py](../../app/core/openrouter_contract.py) | 29 |
| [app/core/rate_limit.py](../../app/core/rate_limit.py) | 93 |
| [app/core/request_limits.py](../../app/core/request_limits.py) | 128 |
| [app/core/security.py](../../app/core/security.py) | 389 |
| [app/core/seo_entity.py](../../app/core/seo_entity.py) | 108 |
| [app/core/site.py](../../app/core/site.py) | 25 |
| [app/core/version.py](../../app/core/version.py) | 107 |
| [app/services/account_deletion.py](../../app/services/account_deletion.py) | 299 |
| [app/services/account_tier.py](../../app/services/account_tier.py) | 224 |
| [app/services/agent_budget_config.py](../../app/services/agent_budget_config.py) | 100 |
| [app/services/agent_comparison.py](../../app/services/agent_comparison.py) | 436 |
| [app/services/agent_contradictions.py](../../app/services/agent_contradictions.py) | 111 |
| [app/services/agent_costs.py](../../app/services/agent_costs.py) | 152 |
| [app/services/agent_delegation.py](../../app/services/agent_delegation.py) | 915 |
| [app/services/agent_delegation_config.py](../../app/services/agent_delegation_config.py) | 76 |
| [app/services/agent_loop.py](../../app/services/agent_loop.py) | 193 |
| [app/services/agent_policy.py](../../app/services/agent_policy.py) | 67 |
| [app/services/agent_progress.py](../../app/services/agent_progress.py) | 88 |
| [app/services/agent_provider_limits.py](../../app/services/agent_provider_limits.py) | 90 |
| [app/services/agent_quota.py](../../app/services/agent_quota.py) | 117 |
| [app/services/agent_runs.py](../../app/services/agent_runs.py) | 367 |
| [app/services/agent_runtime.py](../../app/services/agent_runtime.py) | 73 |
| [app/services/agent_sessions.py](../../app/services/agent_sessions.py) | 401 |
| [app/services/agent_tokens.py](../../app/services/agent_tokens.py) | 39 |
| [app/services/agent_tools.py](../../app/services/agent_tools.py) | 91 |
| [app/services/api_account_cleanup.py](../../app/services/api_account_cleanup.py) | 208 |
| [app/services/api_consensus_runner.py](../../app/services/api_consensus_runner.py) | 398 |
| [app/services/api_key_repository.py](../../app/services/api_key_repository.py) | 200 |
| [app/services/api_run_repository.py](../../app/services/api_run_repository.py) | 403 |
| [app/services/benchmark_reports.py](../../app/services/benchmark_reports.py) | 128 |
| [app/services/chat_context.py](../../app/services/chat_context.py) | 1222 |
| [app/services/chat_store.py](../../app/services/chat_store.py) | 1587 |
| [app/services/claim_ledger.py](../../app/services/claim_ledger.py) | 620 |
| [app/services/consensus_pipeline.py](../../app/services/consensus_pipeline.py) | 222 |
| [app/services/contradiction_verification.py](../../app/services/contradiction_verification.py) | 543 |
| [app/services/differences_stats.py](../../app/services/differences_stats.py) | 202 |
| [app/services/drift_signal.py](../../app/services/drift_signal.py) | 130 |
| [app/services/favicons.py](../../app/services/favicons.py) | 113 |
| [app/services/follow_challenges.py](../../app/services/follow_challenges.py) | 201 |
| [app/services/google_search_console.py](../../app/services/google_search_console.py) | 335 |
| [app/services/history_view.py](../../app/services/history_view.py) | 129 |
| [app/services/llm/agent_client.py](../../app/services/llm/agent_client.py) | 531 |
| [app/services/llm/agent_model_metadata.py](../../app/services/llm/agent_model_metadata.py) | 90 |
| [app/services/llm/attachments.py](../../app/services/llm/attachments.py) | 618 |
| [app/services/llm/base.py](../../app/services/llm/base.py) | 71 |
| [app/services/llm/citations.py](../../app/services/llm/citations.py) | 336 |
| [app/services/llm/consensus_citations.py](../../app/services/llm/consensus_citations.py) | 161 |
| [app/services/llm/consensus_engine.py](../../app/services/llm/consensus_engine.py) | 2657 |
| [app/services/llm/consensus_parsing.py](../../app/services/llm/consensus_parsing.py) | 94 |
| [app/services/llm/consensus_scoring.py](../../app/services/llm/consensus_scoring.py) | 88 |
| [app/services/llm/coverage_judge.py](../../app/services/llm/coverage_judge.py) | 335 |
| [app/services/llm/credentials.py](../../app/services/llm/credentials.py) | 24 |
| [app/services/llm/engines.py](../../app/services/llm/engines.py) | 300 |
| [app/services/llm/mock_llm.py](../../app/services/llm/mock_llm.py) | 215 |
| [app/services/llm/provider_runtime.py](../../app/services/llm/provider_runtime.py) | 369 |
| [app/services/llm/provider_transport.py](../../app/services/llm/provider_transport.py) | 158 |
| [app/services/llm/resolve_engine.py](../../app/services/llm/resolve_engine.py) | 211 |
| [app/services/llm/streaming.py](../../app/services/llm/streaming.py) | 473 |
| [app/services/llm/task_transport.py](../../app/services/llm/task_transport.py) | 18 |
| [app/services/mailer.py](../../app/services/mailer.py) | 720 |
| [app/services/memory_edit.py](../../app/services/memory_edit.py) | 753 |
| [app/services/og_image.py](../../app/services/og_image.py) | 178 |
| [app/services/opinion_map.py](../../app/services/opinion_map.py) | 342 |
| [app/services/persistence_guard.py](../../app/services/persistence_guard.py) | 388 |
| [app/services/prompt_config.py](../../app/services/prompt_config.py) | 161 |
| [app/services/prompt_defaults.py](../../app/services/prompt_defaults.py) | 95 |
| [app/services/public_markdown.py](../../app/services/public_markdown.py) | 225 |
| [app/services/publisher_config.py](../../app/services/publisher_config.py) | 235 |
| [app/services/registration.py](../../app/services/registration.py) | 85 |
| [app/services/retention_maintenance.py](../../app/services/retention_maintenance.py) | 36 |
| [app/services/seo_data.py](../../app/services/seo_data.py) | 577 |
| [app/services/seo_dossier.py](../../app/services/seo_dossier.py) | 312 |
| [app/services/seo_recommendation.py](../../app/services/seo_recommendation.py) | 578 |
| [app/services/seo_repository.py](../../app/services/seo_repository.py) | 459 |
| [app/services/seo_weekly_review.py](../../app/services/seo_weekly_review.py) | 1340 |
| [app/services/share_snapshots.py](../../app/services/share_snapshots.py) | 1973 |
| [app/services/source_catalog.py](../../app/services/source_catalog.py) | 226 |
| [app/services/source_check_jobs.py](../../app/services/source_check_jobs.py) | 443 |
| [app/services/source_check_repository.py](../../app/services/source_check_repository.py) | 711 |
| [app/services/source_documents.py](../../app/services/source_documents.py) | 274 |
| [app/services/source_verification.py](../../app/services/source_verification.py) | 815 |
| [app/services/telegram_notifier.py](../../app/services/telegram_notifier.py) | 398 |
| [app/services/telegram_watch.py](../../app/services/telegram_watch.py) | 559 |
| [app/services/topic_finding.py](../../app/services/topic_finding.py) | 254 |
| [app/services/topic_pipeline.py](../../app/services/topic_pipeline.py) | 123 |
| [app/services/topic_runner.py](../../app/services/topic_runner.py) | 322 |
| [app/services/topics.py](../../app/services/topics.py) | 1334 |
| [app/services/usage_repository.py](../../app/services/usage_repository.py) | 995 |
| [app/services/user_memory.py](../../app/services/user_memory.py) | 470 |
| [app/services/watch_brief.py](../../app/services/watch_brief.py) | 325 |
| [app/services/watch_followers.py](../../app/services/watch_followers.py) | 212 |
| [app/services/watch_scheduler.py](../../app/services/watch_scheduler.py) | 680 |
| [app/services/watch_service.py](../../app/services/watch_service.py) | 1686 |

### Frontend — eigene JavaScript-Module

Abschnittsweise Quelltext-/DOM-/Zustandsprüfung.

| Datei | Zeilen |
|---|---:|
| [static/app-ui.js](../../static/app-ui.js) | 355 |
| [static/demo.js](../../static/demo.js) | 915 |
| [static/firebase.js](../../static/firebase.js) | 2887 |
| [static/js/admin-agent-budget.js](../../static/js/admin-agent-budget.js) | 56 |
| [static/js/admin-api.js](../../static/js/admin-api.js) | 31 |
| [static/js/admin-benchmark.js](../../static/js/admin-benchmark.js) | 406 |
| [static/js/admin-config.js](../../static/js/admin-config.js) | 12 |
| [static/js/admin-prompt-config.js](../../static/js/admin-prompt-config.js) | 143 |
| [static/js/admin.js](../../static/js/admin.js) | 3555 |
| [static/js/agent-activity.js](../../static/js/agent-activity.js) | 404 |
| [static/js/agent-answer-actions.js](../../static/js/agent-answer-actions.js) | 87 |
| [static/js/agent-chat.js](../../static/js/agent-chat.js) | 703 |
| [static/js/agent-delegation.js](../../static/js/agent-delegation.js) | 477 |
| [static/js/agent-mode.js](../../static/js/agent-mode.js) | 840 |
| [static/js/agent-review.js](../../static/js/agent-review.js) | 368 |
| [static/js/analytics-opt-out.js](../../static/js/analytics-opt-out.js) | 8 |
| [static/js/app-bootstrap.js](../../static/js/app-bootstrap.js) | 84 |
| [static/js/app-core.js](../../static/js/app-core.js) | 441 |
| [static/js/app-dom-events.js](../../static/js/app-dom-events.js) | 18 |
| [static/js/app-init.js](../../static/js/app-init.js) | 1906 |
| [static/js/app-state.js](../../static/js/app-state.js) | 91 |
| [static/js/attachments.js](../../static/js/attachments.js) | 782 |
| [static/js/auth-bootstrap.js](../../static/js/auth-bootstrap.js) | 75 |
| [static/js/auth-session-state.js](../../static/js/auth-session-state.js) | 54 |
| [static/js/chat-scroll.js](../../static/js/chat-scroll.js) | 209 |
| [static/js/chat-session.js](../../static/js/chat-session.js) | 595 |
| [static/js/composer-collapse.js](../../static/js/composer-collapse.js) | 344 |
| [static/js/composer-quote.js](../../static/js/composer-quote.js) | 124 |
| [static/js/consensus-actions.js](../../static/js/consensus-actions.js) | 360 |
| [static/js/consensus-anchor.js](../../static/js/consensus-anchor.js) | 310 |
| [static/js/consensus-insights.js](../../static/js/consensus-insights.js) | 2637 |
| [static/js/consensus-lifecycle.js](../../static/js/consensus-lifecycle.js) | 257 |
| [static/js/consensus-progress.js](../../static/js/consensus-progress.js) | 945 |
| [static/js/consensus-run.js](../../static/js/consensus-run.js) | 1916 |
| [static/js/email-verify.js](../../static/js/email-verify.js) | 163 |
| [static/js/error-reporter.js](../../static/js/error-reporter.js) | 226 |
| [static/js/feature-access.js](../../static/js/feature-access.js) | 96 |
| [static/js/landing-insights.js](../../static/js/landing-insights.js) | 429 |
| [static/js/landing-scenes.js](../../static/js/landing-scenes.js) | 469 |
| [static/js/markdown-stream.js](../../static/js/markdown-stream.js) | 341 |
| [static/js/math-render.js](../../static/js/math-render.js) | 175 |
| [static/js/memory-edit.js](../../static/js/memory-edit.js) | 443 |
| [static/js/mobile-header.js](../../static/js/mobile-header.js) | 60 |
| [static/js/model-answer-reader.js](../../static/js/model-answer-reader.js) | 977 |
| [static/js/model-picker.js](../../static/js/model-picker.js) | 1171 |
| [static/js/model-pulse.js](../../static/js/model-pulse.js) | 150 |
| [static/js/query-send.js](../../static/js/query-send.js) | 845 |
| [static/js/request-deadline.js](../../static/js/request-deadline.js) | 36 |
| [static/js/run-registry.js](../../static/js/run-registry.js) | 659 |
| [static/js/run-view.js](../../static/js/run-view.js) | 476 |
| [static/js/share-dialog.js](../../static/js/share-dialog.js) | 380 |
| [static/js/sidebar-quota.js](../../static/js/sidebar-quota.js) | 245 |
| [static/js/source-verification.js](../../static/js/source-verification.js) | 1245 |
| [static/js/sources.js](../../static/js/sources.js) | 779 |
| [static/js/topic-page.js](../../static/js/topic-page.js) | 120 |
| [static/js/usage-limit.js](../../static/js/usage-limit.js) | 388 |
| [static/js/user-memory.js](../../static/js/user-memory.js) | 347 |
| [static/js/user-tier.js](../../static/js/user-tier.js) | 218 |
| [static/js/watch-state.js](../../static/js/watch-state.js) | 41 |
| [static/js/watch.js](../../static/js/watch.js) | 2113 |

### Templates — App, Admin und öffentliche Seiten

Markup, Datenübergaben, Script-Reihenfolge und Produkttexte gelesen.

| Datei | Zeilen |
|---|---:|
| [templates/about.html](../../templates/about.html) | 241 |
| [templates/admin.html](../../templates/admin.html) | 679 |
| [templates/admin_benchmark.html](../../templates/admin_benchmark.html) | 41 |
| [templates/ai-model-comparison.html](../../templates/ai-model-comparison.html) | 180 |
| [templates/benchmark.html](../../templates/benchmark.html) | 405 |
| [templates/consensus-engine.html](../../templates/consensus-engine.html) | 540 |
| [templates/imprint.html](../../templates/imprint.html) | 91 |
| [templates/index.html](../../templates/index.html) | 1490 |
| [templates/landing.html](../../templates/landing.html) | 742 |
| [templates/model-pulse.html](../../templates/model-pulse.html) | 147 |
| [templates/partials/admin_prompt_config.html](../../templates/partials/admin_prompt_config.html) | 48 |
| [templates/partials/analytics.html](../../templates/partials/analytics.html) | 19 |
| [templates/partials/composer_toolbar_mockup.html](../../templates/partials/composer_toolbar_mockup.html) | 24 |
| [templates/partials/product_result_mockup.html](../../templates/partials/product_result_mockup.html) | 60 |
| [templates/partials/public_footer.html](../../templates/partials/public_footer.html) | 18 |
| [templates/partials/public_nav.html](../../templates/partials/public_nav.html) | 16 |
| [templates/privacy.html](../../templates/privacy.html) | 334 |
| [templates/questions.html](../../templates/questions.html) | 167 |
| [templates/share.html](../../templates/share.html) | 773 |
| [templates/share_unavailable.html](../../templates/share_unavailable.html) | 50 |
| [templates/terms.html](../../templates/terms.html) | 194 |
| [templates/topic.html](../../templates/topic.html) | 734 |
| [templates/topics.html](../../templates/topics.html) | 152 |

### Build-, Betriebs- und Benchmarkcode

Abschnittsweise Quelltext-/Ablaufprüfung.

| Datei | Zeilen |
|---|---:|
| [scripts/backfill_claim_keys.py](../../scripts/backfill_claim_keys.py) | 110 |
| [scripts/evaluate_agent_delegation.py](../../scripts/evaluate_agent_delegation.py) | 186 |
| [scripts/evaluate_source_verification.py](../../scripts/evaluate_source_verification.py) | 102 |
| [scripts/probe_agent_delegation.py](../../scripts/probe_agent_delegation.py) | 80 |
| [scripts/publish_consensus.py](../../scripts/publish_consensus.py) | 585 |
| [scripts/render_watch_preview.py](../../scripts/render_watch_preview.py) | 201 |
| [scripts/repair_agent_allowance.py](../../scripts/repair_agent_allowance.py) | 47 |
| [scripts/build_frontend.mjs](../../scripts/build_frontend.mjs) | 303 |
| [scripts/frontend-output.mjs](../../scripts/frontend-output.mjs) | 69 |
| [scripts/vendor_frontend.mjs](../../scripts/vendor_frontend.mjs) | 36 |
| [benchmark/__init__.py](../../benchmark/__init__.py) | 7 |
| [benchmark/__main__.py](../../benchmark/__main__.py) | 345 |
| [benchmark/audit.py](../../benchmark/audit.py) | 120 |
| [benchmark/config.py](../../benchmark/config.py) | 159 |
| [benchmark/cost.py](../../benchmark/cost.py) | 29 |
| [benchmark/dataset.py](../../benchmark/dataset.py) | 189 |
| [benchmark/parse.py](../../benchmark/parse.py) | 74 |
| [benchmark/prompt.py](../../benchmark/prompt.py) | 73 |
| [benchmark/report_reader.py](../../benchmark/report_reader.py) | 191 |
| [benchmark/results.py](../../benchmark/results.py) | 222 |
| [benchmark/run_experiment.py](../../benchmark/run_experiment.py) | 124 |
| [benchmark/run_sample.py](../../benchmark/run_sample.py) | 118 |
| [benchmark/runner.py](../../benchmark/runner.py) | 1084 |
| [benchmark/transport.py](../../benchmark/transport.py) | 206 |
| [.github/workflows/publish-consensus.yml](../../.github/workflows/publish-consensus.yml) | 48 |
| [.github/workflows/publisher-tests.yml](../../.github/workflows/publisher-tests.yml) | 22 |
| [.github/workflows/restart-render.yml](../../.github/workflows/restart-render.yml) | 20 |
| [dev.ps1](../../dev.ps1) | 180 |

### Styles — begrenzte strukturelle Prüfung

Import-/Layoutstruktur und Zustandsregeln; keine vollständige Deklarations-/Pixelprüfung.

| Datei | Zeilen |
|---|---:|
| [static/style.css](../../static/style.css) | 45 |
| [static/css/admin-benchmark.css](../../static/css/admin-benchmark.css) | 277 |
| [static/css/admin.css](../../static/css/admin.css) | 793 |
| [static/css/agent-chat.css](../../static/css/agent-chat.css) | 380 |
| [static/css/base.css](../../static/css/base.css) | 145 |
| [static/css/benchmark.css](../../static/css/benchmark.css) | 526 |
| [static/css/chat-scroll.css](../../static/css/chat-scroll.css) | 25 |
| [static/css/components-attachment-viewer.css](../../static/css/components-attachment-viewer.css) | 401 |
| [static/css/components-consensus-insights.css](../../static/css/components-consensus-insights.css) | 907 |
| [static/css/components-consensus-visuals.css](../../static/css/components-consensus-visuals.css) | 394 |
| [static/css/components-consensus.css](../../static/css/components-consensus.css) | 1841 |
| [static/css/components-controls.css](../../static/css/components-controls.css) | 274 |
| [static/css/components-feedback.css](../../static/css/components-feedback.css) | 246 |
| [static/css/components-input.css](../../static/css/components-input.css) | 1260 |
| [static/css/components-memory-edit.css](../../static/css/components-memory-edit.css) | 436 |
| [static/css/components-misc.css](../../static/css/components-misc.css) | 385 |
| [static/css/components-modals.css](../../static/css/components-modals.css) | 2027 |
| [static/css/components-model-picker.css](../../static/css/components-model-picker.css) | 1189 |
| [static/css/components-watch.css](../../static/css/components-watch.css) | 744 |
| [static/css/composer-attachments.css](../../static/css/composer-attachments.css) | 102 |
| [static/css/consensus-engine.css](../../static/css/consensus-engine.css) | 1055 |
| [static/css/demo-action.css](../../static/css/demo-action.css) | 75 |
| [static/css/landing.css](../../static/css/landing.css) | 3025 |
| [static/css/layout.css](../../static/css/layout.css) | 1370 |
| [static/css/model-answer-reader.css](../../static/css/model-answer-reader.css) | 691 |
| [static/css/model-pulse.css](../../static/css/model-pulse.css) | 302 |
| [static/css/public-pages.css](../../static/css/public-pages.css) | 3627 |
| [static/css/public-shell.css](../../static/css/public-shell.css) | 506 |
| [static/css/public-tokens.css](../../static/css/public-tokens.css) | 190 |
| [static/css/shell.css](../../static/css/shell.css) | 4239 |
| [static/css/skeleton.css](../../static/css/skeleton.css) | 84 |
| [static/css/source-verification.css](../../static/css/source-verification.css) | 182 |
| [static/css/status-palette.css](../../static/css/status-palette.css) | 31 |
| [static/css/topics.css](../../static/css/topics.css) | 2350 |
| [static/css/typography.css](../../static/css/typography.css) | 70 |
| [static/css/variables.css](../../static/css/variables.css) | 228 |

### Konfiguration und Datenverträge

Konfiguration gelesen; Modellkatalog statisch, keine Live-Verfügbarkeits-/Preisprüfung.

| Datei | Zeilen |
|---|---:|
| [.env.example](../../.env.example) | 86 |
| [.gitignore](../../.gitignore) | 63 |
| [.gitattributes](../../.gitattributes) | 2 |
| [package.json](../../package.json) | 20 |
| [requirements.txt](../../requirements.txt) | 88 |
| [firebase.json](../../firebase.json) | 16 |
| [firestore.rules](../../firestore.rules) | 34 |
| [firestore.indexes.json](../../firestore.indexes.json) | 63 |
| [static/js/bundles.json](../../static/js/bundles.json) | 141 |
| [app/services/llm/agent_model_catalog.json](../../app/services/llm/agent_model_catalog.json) | 1054 |
| [benchmark/requirements-benchmark.txt](../../benchmark/requirements-benchmark.txt) | 10 |

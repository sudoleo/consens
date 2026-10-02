# Separat gestartete E2E-Suite: Abdeckung pro Testdatei

Stand: **2026-10-02**, Quellstand `ffaca3df7c8bbb02d850fb8f31d90107f26e9293`. [Methodik und Gesamtbefund](../test-coverage-map.md).

**44 Dateien · 205 statische Testdefinitionen · 368 Runner-Fälle.**

„Geprüftes Verhalten“ beschreibt die vorhandenen Assertions. Der Laufstatus steht separat: bei Fehlern ist der beschriebene Vertrag nicht als bestanden belegt. Prüfaufträge sind offene Fragen, keine pauschal festgestellten Lücken der gesamten Suite. Aktuelle Befundbewertungen stehen im [Produktabgleich](product/README.md).

Die Codeverweise sind direkte Imports oder wörtliche Pfade, keine gemessene Ausführungsabdeckung. Indirekte Abhängigkeiten über Fixtures/Helpers und dynamisch zusammengesetzte Pfade können fehlen. Das [JSON-Inventar](inventory.json) enthält jede Definition mit Zeilen, Assertion-Fundstellen und jeden expandierten Runner-Fall. Datum, Umgebung und Grenzen stehen im [Laufbericht](findings.md).

| Datei | Definitionen | Runner-Fälle | Primärlauf 2026-10-02 |
|---|---:|---:|---|
| [test_account_deletion_transactions.py](#test-account-deletion-transactions-py) | 2 | 2 | 2 bestanden |
| [test_admin_agent_budget.py](#test-admin-agent-budget-py) | 1 | 3 | 3 bestanden |
| [test_admin_prompt_config.py](#test-admin-prompt-config-py) | 1 | 3 | 3 bestanden |
| [test_agent_chat_frontend.py](#test-agent-chat-frontend-py) | 12 | 31 | 31 bestanden |
| [test_agent_comparison_frontend.py](#test-agent-comparison-frontend-py) | 6 | 15 | 15 bestanden |
| [test_agent_delegation_frontend.py](#test-agent-delegation-frontend-py) | 2 | 8 | 8 bestanden |
| [test_agent_gmail_frontend.py](#test-agent-gmail-frontend-py) | 1 | 3 | 3 bestanden |
| [test_agent_google_frontend.py](#test-agent-google-frontend-py) | 2 | 4 | 4 bestanden |
| [test_agent_status_frontend.py](#test-agent-status-frontend-py) | 1 | 6 | 6 bestanden |
| [test_agent_transactions.py](#test-agent-transactions-py) | 7 | 7 | 7 bestanden |
| [test_agent_workspace_frontend.py](#test-agent-workspace-frontend-py) | 2 | 5 | 5 bestanden |
| [test_agreement_verdict.py](#test-agreement-verdict-py) | 1 | 1 | 1 bestanden |
| [test_api_retention_transactions.py](#test-api-retention-transactions-py) | 2 | 2 | 2 bestanden |
| [test_bookmark_lifecycle_frontend.py](#test-bookmark-lifecycle-frontend-py) | 2 | 6 | 6 bestanden |
| [test_browser_failure_recovery.py](#test-browser-failure-recovery-py) | 3 | 3 | 3 bestanden |
| [test_chat_lifecycle_transactions.py](#test-chat-lifecycle-transactions-py) | 4 | 5 | 5 bestanden |
| [test_chat_scroll_frontend.py](#test-chat-scroll-frontend-py) | 3 | 11 | 11 bestanden |
| [test_composer_mode_bar.py](#test-composer-mode-bar-py) | 2 | 7 | 7 bestanden |
| [test_consensus_live_progress.py](#test-consensus-live-progress-py) | 5 | 14 | 14 bestanden |
| [test_contradiction_source_ui.py](#test-contradiction-source-ui-py) | 3 | 7 | 7 bestanden |
| [test_direct_comparison_preview.py](#test-direct-comparison-preview-py) | 2 | 8 | 8 bestanden |
| [test_file_storage_transactions.py](#test-file-storage-transactions-py) | 3 | 3 | 3 bestanden |
| [test_google_action_transactions.py](#test-google-action-transactions-py) | 2 | 6 | 6 bestanden |
| [test_inspector_polish.py](#test-inspector-polish-py) | 1 | 2 | 2 bestanden |
| [test_memory_edit_transactions.py](#test-memory-edit-transactions-py) | 6 | 7 | 7 bestanden |
| [test_mobile_navigation.py](#test-mobile-navigation-py) | 5 | 12 | 12 bestanden |
| [test_model_answer_reader.py](#test-model-answer-reader-py) | 12 | 51 | 51 bestanden |
| [test_model_configuration_transactions.py](#test-model-configuration-transactions-py) | 2 | 4 | 4 bestanden |
| [test_persisted_journeys.py](#test-persisted-journeys-py) | 6 | 6 | 6 bestanden |
| [test_phase2_transactions.py](#test-phase2-transactions-py) | 4 | 4 | 4 bestanden |
| [test_phase4_frontend.py](#test-phase4-frontend-py) | 24 | 29 | 29 bestanden |
| [test_prompt_config_transactions.py](#test-prompt-config-transactions-py) | 1 | 1 | 1 bestanden |
| [test_public_composer_mockups.py](#test-public-composer-mockups-py) | 1 | 5 | 5 bestanden |
| [test_reader_density.py](#test-reader-density-py) | 1 | 2 | 2 bestanden |
| [test_reader_review_regressions.py](#test-reader-review-regressions-py) | 2 | 5 | 5 bestanden |
| [test_run_cancel_and_progress.py](#test-run-cancel-and-progress-py) | 3 | 3 | 3 bestanden |
| [test_run_mode_selector.py](#test-run-mode-selector-py) | 6 | 11 | 11 bestanden |
| [test_scheduler_transactions.py](#test-scheduler-transactions-py) | 5 | 6 | 6 bestanden |
| [test_seo_repository_queries.py](#test-seo-repository-queries-py) | 1 | 1 | 1 bestanden |
| [test_smoke.py](#test-smoke-py) | 43 | 43 | 43 bestanden |
| [test_source_check_transactions.py](#test-source-check-transactions-py) | 3 | 3 | 3 bestanden |
| [test_topic_frontend.py](#test-topic-frontend-py) | 2 | 5 | 5 bestanden |
| [test_usage_transactions.py](#test-usage-transactions-py) | 4 | 4 | 4 bestanden |
| [test_watch_delivery_transactions.py](#test-watch-delivery-transactions-py) | 4 | 4 | 4 bestanden |

<a id="test-account-deletion-transactions-py"></a>

## test_account_deletion_transactions.py

**Quelle:** [tests/e2e/test_account_deletion_transactions.py](../../tests/e2e/test_account_deletion_transactions.py) · **Bereiche:** Authentifizierung, Konten und Tarife, Dateien und Dokumente.

**Ebene:** Echte Firestore-SDK-Transaktionen gegen isolierten Demo-Emulator und echter Cloudadapter.

**Lauf:** 2 bestanden.

**Geprüftes Verhalten:** Alle 16 aktuellen Cleanupbereiche, Google-/API-Metadaten, Dokumentversionen, Shares, Watches, Receipts und Outbox. Objektfehler lassen nur den betroffenen Bereich pending; frische Serviceinstanz setzt fort. Verlorene Checkpoints führen zu idempotenter Wiederholung. Fremder Owner bleibt unverändert; minimaler Tombstone bleibt, Cleanup-E-Mail verschwindet.

**Grenzen und Doubles:** Lokaler Emulator mit anonymen Credentials; kein Produktkonto, keine produktive IAM-/Lastgarantie. Nur eigene Dokumentwurzeln werden aufgeräumt. Authlöschung und Objekttransport sind äußere Doubles; die Bereichsliste ist explizit als Reviewguard fixiert.

**Prüfauftrag für den Folgeaudit:** Die benannten Betriebs- und Testgrenzen bei künftigen Änderungen erneut prüfen; konkrete Paketnachweise stehen im Produktabgleich.

**Direkte Codeverweise:** [app/services/account_deletion.py](../../app/services/account_deletion.py), [app/services/agent_files.py](../../app/services/agent_files.py), [app/services/chat_store.py](../../app/services/chat_store.py), [app/services/persistence_guard.py](../../app/services/persistence_guard.py), [app/services/share_snapshots.py](../../app/services/share_snapshots.py), [app/services/source_check_repository.py](../../app/services/source_check_repository.py).

<details>
<summary>2 Testdefinitionen und ihre Quellstellen</summary>

- [test_native_account_cascade_resumes_failed_objects_without_foreign_loss](../../tests/e2e/test_account_deletion_transactions.py#L60) (Zeile 60)
- [test_native_account_repeats_success_after_lost_checkpoint](../../tests/e2e/test_account_deletion_transactions.py#L94) (Zeile 94)

</details>

<a id="test-admin-agent-budget-py"></a>

## test_admin_agent_budget.py

**Quelle:** [tests/e2e/test_admin_agent_budget.py](../../tests/e2e/test_admin_agent_budget.py) · **Bereiche:** Admin, Agent, Konten und Tarife.

**Ebene:** Chromium-Browserintegration mit simulierten Admin-APIs.

**Lauf:** 3 bestanden.

**Geprüftes Verhalten:** Bei 1280/390/320 px Budgetfeld laden, unabhängig von allgemeiner Savebar speichern, danach global resetten; Authorization und erwartete Revision/Methoden/Payloads, erhaltener Limitwert, kein horizontaler Überlauf und keine erfassten JSfehler. Aktualisierung 02.10.2026: Gemeinsame Tariflimits und Compare/Consensus/Deep-Think-Schätzungen speichern und alle Konten resetten.

**Grenzen und Doubles:** Echte Adminseite/Modul, Firebase-App/Auth-SDK und Budgetendpoints über Routes ersetzt; Reset wirkt nur auf Testzustand.

**Prüfauftrag für den Folgeaudit:** UIrequests mit tatsächlicher Adminautorisierung und atomarem Reset im Backend verbinden.

**Direkte Testhelfer:** [tests/e2e/test_phase4_frontend.py](../../tests/e2e/test_phase4_frontend.py).

<details>
<summary>1 Testdefinitionen und ihre Quellstellen</summary>

- [test_admin_agent_budget_save_and_reset](../../tests/e2e/test_admin_agent_budget.py#L11) (Zeile 11)

</details>

<a id="test-admin-prompt-config-py"></a>

## test_admin_prompt_config.py

**Quelle:** [tests/e2e/test_admin_prompt_config.py](../../tests/e2e/test_admin_prompt_config.py) · **Bereiche:** Admin, Prompts.

**Ebene:** Chromium-Browserintegration mit simulierten Admin-APIs.

**Lauf:** 3 bestanden.

**Geprüftes Verhalten:** Konfigurationstab bei 1280/390/320 px: Defaults/aktive Felder, Legacydelegation verborgen, Bearbeitung ohne Autosave, revisionsgebundenes Speichern/Reload und UTC; fremder Edit erzeugt Konflikt ohne Draftverlust, Reload übernimmt Fremdstand, Restore speichert neue Revision; Authheader, unveränderte Legacywerte und kein Überlauf/JSfehler.

**Grenzen und Doubles:** Echte Seite und Promptschema-Defaults; APIzustand in Routehandlern, Auth-SDK ersetzt. Keine tatsächliche Datenbank oder zentrale Promptverwendung.

**Prüfauftrag für den Folgeaudit:** Browservertrag mit PromptConfigStore-/Endpointtests zuordnen.

**Direkte Codeverweise:** [app/services/prompt_config.py](../../app/services/prompt_config.py).

**Direkte Testhelfer:** [tests/e2e/test_phase4_frontend.py](../../tests/e2e/test_phase4_frontend.py).

<details>
<summary>1 Testdefinitionen und ihre Quellstellen</summary>

- [test_configuration_tab_saves_reloads_and_preserves_conflicting_draft](../../tests/e2e/test_admin_prompt_config.py#L15) (Zeile 15)

</details>

<a id="test-agent-chat-frontend-py"></a>

## test_agent_chat_frontend.py

**Quelle:** [tests/e2e/test_agent_chat_frontend.py](../../tests/e2e/test_agent_chat_frontend.py) · **Bereiche:** Agent, Frontend.

**Ebene:** Chromium mit echtem App-Frontend und kontrollierten Agent-APIantworten.

**Lauf:** 31 bestanden.

**Geprüftes Verhalten:** Agentlauf, Replay/Recovery, gespeicherte Antworten, Datei-/Ressourcenbindung und Fehleransicht. Fixtures verwenden heutige Dokument-Turn-IDs und verbindliche Antwortzustände; unvollständige Antworten bleiben sichtbar markiert.

**Grenzen und Doubles:** API/Auth/DB ersetzt; persistierte interne Ende-zu-Ende-Reisen werden separat geprüft.

**Prüfauftrag für den Folgeaudit:** Die benannten Betriebs- und Testgrenzen bei künftigen Änderungen erneut prüfen; konkrete Paketnachweise stehen im Produktabgleich.

**Direkte Codeverweise:** [app/core/config.py](../../app/core/config.py), [app/services/llm/agent_client.py](../../app/services/llm/agent_client.py).

**Direkte Testhelfer:** [tests/e2e/test_phase4_frontend.py](../../tests/e2e/test_phase4_frontend.py).

<details>
<summary>12 Testdefinitionen und ihre Quellstellen</summary>

- [test_all_pro_chat_models_are_grouped_by_provider](../../tests/e2e/test_agent_chat_frontend.py#L71) (Zeile 71)
- [test_saved_interruption_keeps_reason_and_partial_answer_visible](../../tests/e2e/test_agent_chat_frontend.py#L126) (Zeile 126)
- [test_failed_stream_adopts_saved_bookmark_and_survives_reload](../../tests/e2e/test_agent_chat_frontend.py#L164) (Zeile 164)
- [test_single_agent_send_followup_restore_and_layout](../../tests/e2e/test_agent_chat_frontend.py#L245) (Zeile 245)
- [test_live_reasoning_disclosure_and_stop](../../tests/e2e/test_agent_chat_frontend.py#L411) (Zeile 411)
- [test_small_viewport_long_model_and_missing_reasoning](../../tests/e2e/test_agent_chat_frontend.py#L521) (Zeile 521)
- [test_model_catalog_retry_and_failed_stream](../../tests/e2e/test_agent_chat_frontend.py#L569) (Zeile 569)
- [test_model_loading_and_unsent_draft_recovery](../../tests/e2e/test_agent_chat_frontend.py#L629) (Zeile 629)
- [test_quota_stream_and_failure_update_existing_percentage](../../tests/e2e/test_agent_chat_frontend.py#L676) (Zeile 676)
- [test_shared_consensus_picker_still_navigates_submenus](../../tests/e2e/test_agent_chat_frontend.py#L720) (Zeile 720)
- [test_native_search_sources_in_chat_and_saved_activity](../../tests/e2e/test_agent_chat_frontend.py#L746) (Zeile 746)
- [test_removed_preference_and_legacy_phantom_search](../../tests/e2e/test_agent_chat_frontend.py#L810) (Zeile 810)

</details>

<a id="test-agent-comparison-frontend-py"></a>

## test_agent_comparison_frontend.py

**Quelle:** [tests/e2e/test_agent_comparison_frontend.py](../../tests/e2e/test_agent_comparison_frontend.py) · **Bereiche:** Agent, Frontend.

**Ebene:** Chromium mit echten Vergleichs-/Drawerkomponenten.

**Lauf:** 15 bestanden.

**Geprüftes Verhalten:** Vergleichsantworten, Sources/Differences, aktive und gespeicherte Turns sowie Mobilbedienung. Ownergebundene Antwortreceipts bilden gültige Consensusgrundlage; fehlende Receipts dürfen sichtbar bleiben, starten aber keinen Consensus.

**Grenzen und Doubles:** Provider/APIantworten kontrolliert; keine native Ergebnis-/Quotenpersistenz in diesen Detailfällen.

**Prüfauftrag für den Folgeaudit:** Die benannten Betriebs- und Testgrenzen bei künftigen Änderungen erneut prüfen; konkrete Paketnachweise stehen im Produktabgleich.

**Direkte Codeverweise:** [app/services/chat_store.py](../../app/services/chat_store.py).

**Direkte Testhelfer:** [tests/e2e/test_agent_chat_frontend.py](../../tests/e2e/test_agent_chat_frontend.py), [tests/e2e/test_phase4_frontend.py](../../tests/e2e/test_phase4_frontend.py).

<details>
<summary>6 Testdefinitionen und ihre Quellstellen</summary>

- [test_comparison_selection_blocks_send_before_losing_draft](../../tests/e2e/test_agent_comparison_frontend.py#L13) (Zeile 13)
- [test_mobile_agent_plus_menu_opens_tools_from_single_line_composer](../../tests/e2e/test_agent_comparison_frontend.py#L67) (Zeile 67)
- [test_comparison_review_and_saved_projection](../../tests/e2e/test_agent_comparison_frontend.py#L179) (Zeile 179)
- [test_saved_agent_paper_urls_become_source_pills](../../tests/e2e/test_agent_comparison_frontend.py#L419) (Zeile 419)
- [test_differences_reader_stays_calm_with_missing_models](../../tests/e2e/test_agent_comparison_frontend.py#L465) (Zeile 465)
- [test_green_agent_passages_hover_after_scrolling_and_reprojection](../../tests/e2e/test_agent_comparison_frontend.py#L568) (Zeile 568)

</details>

<a id="test-agent-delegation-frontend-py"></a>

## test_agent_delegation_frontend.py

**Quelle:** [tests/e2e/test_agent_delegation_frontend.py](../../tests/e2e/test_agent_delegation_frontend.py) · **Bereiche:** Agent, Responsive UI, Streaming und Wiederherstellung.

**Ebene:** Chromium-Browserintegration mit künstlichem SSE-Stream und APIantworten.

**Lauf:** 8 bestanden.

**Geprüftes Verhalten:** Livecounter wechselt Tokens pending→Zeichen→Tokens, Dauer aus Serverwert, Animationen enden bei Abschluss/Reduced Motion; echte SSEparser-Laufkette über offenem Browser-ReadableStream. Sidebar mit vielen Delegationen, stabilem Header/Usage beim Scrollen, eigenem Scrollbereich, Detail-Skeleton/Laden/Cache und Judgeinfos; gespeicherte Ansicht, Escape/Fokus und mobile Grenzen in hell/dunkel. Aktualisierung 02.10.2026: Aktivitätsansicht öffnet mobil nur auf Wunsch mit Scrim und korrektem aria-expanded.

**Grenzen und Doubles:** App-eigene UI echt, Fetch für /agent durch lokalen ReadableStream ersetzt, Poll-/Detail-/Bookmarkantworten und Auth simuliert. Kein Netzwerkstream, Delegationsworker oder Datenbank.

**Prüfauftrag für den Folgeaudit:** Delegationsereignisse/Sequenzen, Pollfallback und Persistenz mit Backendtests verbinden.

**Direkte Testhelfer:** [tests/e2e/test_agent_chat_frontend.py](../../tests/e2e/test_agent_chat_frontend.py), [tests/e2e/test_phase4_frontend.py](../../tests/e2e/test_phase4_frontend.py).

<details>
<summary>2 Testdefinitionen und ihre Quellstellen</summary>

- [test_agent_live_counter_uses_streamed_progress_and_stops_animation](../../tests/e2e/test_agent_delegation_frontend.py#L14) (Zeile 14)
- [test_agent_sidebar_real_app_and_saved_view](../../tests/e2e/test_agent_delegation_frontend.py#L110) (Zeile 110)

</details>

<a id="test-agent-gmail-frontend-py"></a>

## test_agent_gmail_frontend.py

**Quelle:** [tests/e2e/test_agent_gmail_frontend.py](../../tests/e2e/test_agent_gmail_frontend.py) · **Bereiche:** Google, Agent, Frontend.

**Ebene:** Chromium mit kontrollierten Verbindungen und Gmailaktionsantworten.

**Lauf:** 3 bestanden.

**Geprüftes Verhalten:** Freigabe und Entwurfskarte binden Empfänger/Anhänge/Dokumentversion an den richtigen Turn; heutige Dokument-ID-Fixtures, Bestätigung und Fehler/Unknownanzeige bleiben nutzbar.

**Grenzen und Doubles:** Google/Agentendpoints ersetzt; native Aktionsclaims separat, keine echte Mailzustellung.

**Prüfauftrag für den Folgeaudit:** Die benannten Betriebs- und Testgrenzen bei künftigen Änderungen erneut prüfen; konkrete Paketnachweise stehen im Produktabgleich.

<details>
<summary>1 Testdefinitionen und ihre Quellstellen</summary>

- [test_gmail_draft_revision_document_download_and_restoration](../../tests/e2e/test_agent_gmail_frontend.py#L12) (Zeile 12)

</details>

<a id="test-agent-google-frontend-py"></a>

## test_agent_google_frontend.py

**Quelle:** [tests/e2e/test_agent_google_frontend.py](../../tests/e2e/test_agent_google_frontend.py) · **Bereiche:** Google, Agent.

**Ebene:** Chromium mit writerfreiem Server und gemockten APIs.

**Lauf:** 4 bestanden.

**Geprüftes Verhalten:** Kalender-/Accountchips, Zustimmung pro Nachricht, Sendenblocker, exakter Aktionshash, Ergebnisanzeige und Kontowechsel; OAuth-Popup nutzt echte Callback-CSP und authentifizierten gemockten Finish.

**Grenzen und Doubles:** Google- und Persistenzendpoints ersetzt; kein Live-OAuth oder echter Terminwrite.

**Prüfauftrag für den Folgeaudit:** Die benannten Mock-/Integrationsgrenzen am realen Adapter prüfen; Zuordnung und offene Aufgaben stehen in der Produktmatrix.

<details>
<summary>2 Testdefinitionen und ihre Quellstellen</summary>

- [test_selected_calendar_and_exact_confirmation](../../tests/e2e/test_agent_google_frontend.py#L22) (Zeile 22)
- [test_oauth_callback_popup_uses_real_csp_and_authenticated_finish](../../tests/e2e/test_agent_google_frontend.py#L94) (Zeile 94)

</details>

<a id="test-agent-status-frontend-py"></a>

## test_agent_status_frontend.py

**Quelle:** [tests/e2e/test_agent_status_frontend.py](../../tests/e2e/test_agent_status_frontend.py) · **Bereiche:** Agent, Frontend.

**Ebene:** Chromium mit kontrollierten gestreamten Fortschrittsereignissen.

**Lauf:** 6 bestanden.

**Geprüftes Verhalten:** Agentstatus/Verlauf, mobile Details, Quellenpills und sichtbare abgeschlossene/unvollständige Antworten folgen aktuellen Produktzuständen. Gerundete CSS-Pixel vermeiden Subpixelartefakte ohne Layoutgrenzen aufzugeben.

**Grenzen und Doubles:** Synthetische Ereignisse; ausgewählte Viewports und keine vollständige Accessibilitybaseline.

**Prüfauftrag für den Folgeaudit:** Die benannten Betriebs- und Testgrenzen bei künftigen Änderungen erneut prüfen; konkrete Paketnachweise stehen im Produktabgleich.

**Direkte Testhelfer:** [tests/e2e/test_agent_chat_frontend.py](../../tests/e2e/test_agent_chat_frontend.py), [tests/e2e/test_phase4_frontend.py](../../tests/e2e/test_phase4_frontend.py).

<details>
<summary>1 Testdefinitionen und ihre Quellstellen</summary>

- [test_progress_paragraphs_collapse_at_final_and_reopen_with_keyboard](../../tests/e2e/test_agent_status_frontend.py#L11) (Zeile 11)

</details>

<a id="test-agent-transactions-py"></a>

## test_agent_transactions.py

**Quelle:** [tests/e2e/test_agent_transactions.py](../../tests/e2e/test_agent_transactions.py) · **Bereiche:** Agent, Konten und Tarife, Nebenläufigkeit, Persistenz.

**Ebene:** Firestore-Emulatorintegration mit echten SDK-Transaktionen und Threads.

**Lauf:** 7 bestanden.

**Geprüftes Verhalten:** Stop gegen erste Zulassung ohne normalen Prozesslock; wartender zweiter Agent nutzt freiwerdendes Tokenbudget. Parallele Legacyhold-Reparatur und Orphanreceipt-/Savedusage-Recovery nur einmal; tägliche Reservierung und idempotentes Settlement. Delegationsjournal/Sequenzen, Budget/Receipts und Detailnachrichten atomar; parallele Worker teilen Kapazität, erneutes Claim/Settlement/Finish nur einmal, unbekannte und gemessene Kosten getrennt, Leasefreigabe sowie Chat-/Agentsubcollections-Löschung. Der aktuelle Diff passt Fixtures, Payloads oder Bezeichnungen an; die unten neu extrahierten Definitionen und Assertionstellen sind maßgeblich.

**Grenzen und Doubles:** Echter lokaler Emulator, mehrere Storeinstanzen/Threads und Barrieren; Completion künstlich, stellenweise Policy/Limits oder Prozesslock gezielt ersetzt. Kein produktiver Firestorecluster, Mehrprozessdeployment oder echter Provider.

**Prüfauftrag für den Folgeaudit:** Produktionsretry-/Latenz-/Mehrprozessverhalten und übrige Transaktionsgrenzen gegen diese Szenarien abgleichen.

**Direkte Codeverweise:** [app/core/e2e_profile.py](../../app/core/e2e_profile.py), [app/services/account_deletion.py](../../app/services/account_deletion.py), [app/services/agent_budget_config.py](../../app/services/agent_budget_config.py), [app/services/agent_costs.py](../../app/services/agent_costs.py), [app/services/agent_delegation.py](../../app/services/agent_delegation.py), [app/services/agent_delegation_config.py](../../app/services/agent_delegation_config.py), [app/services/agent_policy.py](../../app/services/agent_policy.py), [app/services/agent_quota.py](../../app/services/agent_quota.py), [app/services/agent_runs.py](../../app/services/agent_runs.py), [app/services/agent_runtime.py](../../app/services/agent_runtime.py), [app/services/agent_tools.py](../../app/services/agent_tools.py), [app/services/chat_store.py](../../app/services/chat_store.py), [app/services/llm/agent_client.py](../../app/services/llm/agent_client.py), [app/services/llm/provider_runtime.py](../../app/services/llm/provider_runtime.py).

<details>
<summary>7 Testdefinitionen und ihre Quellstellen</summary>

- [test_stop_and_first_admission_are_atomic_without_process_lock](../../tests/e2e/test_agent_transactions.py#L22) (Zeile 22)
- [test_chat_admission_waits_across_runs_then_uses_released_allowance](../../tests/e2e/test_agent_transactions.py#L69) (Zeile 69)
- [test_parallel_legacy_hold_repair_preserves_measured_usage_and_live_reservations](../../tests/e2e/test_agent_transactions.py#L129) (Zeile 129)
- [test_concurrent_budget_refresh_recovers_orphaned_receipt_and_saved_usage_once](../../tests/e2e/test_agent_transactions.py#L153) (Zeile 153)
- [test_daily_token_admission_and_idempotent_settlement_in_firestore](../../tests/e2e/test_agent_transactions.py#L194) (Zeile 194)
- [test_delegation_budget_journal_and_receipts_are_atomic_in_firestore](../../tests/e2e/test_agent_transactions.py#L237) (Zeile 237)
- [test_parallel_workers_share_admission_and_settle_each_receipt_once](../../tests/e2e/test_agent_transactions.py#L292) (Zeile 292)

</details>

<a id="test-agent-workspace-frontend-py"></a>

## test_agent_workspace_frontend.py

**Quelle:** [tests/e2e/test_agent_workspace_frontend.py](../../tests/e2e/test_agent_workspace_frontend.py) · **Bereiche:** Agent, Dateien und Dokumente.

**Ebene:** Chromium mit writerfreiem Server und gemockten APIs.

**Lauf:** 5 bestanden.

**Geprüftes Verhalten:** Upload, Restore, Dateivorschau und privater Download; Dokumentkarten folgen der Antwort, Versionen bleiben zugeordnet, Löschung braucht Bestätigung, Mailherkunft/Lesewarnung und Hell/Dunkel/Viewportgrenzen.

**Grenzen und Doubles:** Gemockte Datei-/Chatendpoints; kein echter Parser, Bucket oder DB.

**Prüfauftrag für den Folgeaudit:** Die benannten Mock-/Integrationsgrenzen am realen Adapter prüfen; Zuordnung und offene Aufgaben stehen in der Produktmatrix.

<details>
<summary>2 Testdefinitionen und ihre Quellstellen</summary>

- [test_upload_restoration_and_private_download](../../tests/e2e/test_agent_workspace_frontend.py#L30) (Zeile 30)
- [test_saved_document_versions_follow_the_answer_and_remove_needs_confirmation](../../tests/e2e/test_agent_workspace_frontend.py#L96) (Zeile 96)

</details>

<a id="test-agreement-verdict-py"></a>

## test_agreement_verdict.py

**Quelle:** [tests/e2e/test_agreement_verdict.py](../../tests/e2e/test_agreement_verdict.py) · **Bereiche:** Consensus, Frontend.

**Ebene:** Chromium mit echtem App-Frontend und direkt aufgerufenem Verdict-Renderer.

**Lauf:** 1 bestanden.

**Geprüftes Verhalten:** Ein synthetischer niedriger Agreementwert ohne Widersprüche ergibt eine Warnanzeige mit korrektem Text und berechnetem CSS-Token --dispute; keine veraltete feste Hexfarbe als Oracle.

**Grenzen und Doubles:** Der Fall übergibt kontrollierte Daten direkt an renderConsensusInsights. Die app_page-Umgebung nutzt echte App-Routen und Emulator, aber dieser Fall beweist keinen eigenen Modell-/Persistenzlauf.

**Prüfauftrag für den Folgeaudit:** Die benannten Betriebs- und Testgrenzen bei künftigen Änderungen erneut prüfen; konkrete Paketnachweise stehen im Produktabgleich.

<details>
<summary>1 Testdefinitionen und ihre Quellstellen</summary>

- [test_low_score_without_contradictions_is_not_green_or_high](../../tests/e2e/test_agreement_verdict.py#L4) (Zeile 4)

</details>

<a id="test-api-retention-transactions-py"></a>

## test_api_retention_transactions.py

**Quelle:** [tests/e2e/test_api_retention_transactions.py](../../tests/e2e/test_api_retention_transactions.py) · **Bereiche:** API.

**Ebene:** Echte Firestore-SDK-Transaktionen gegen isolierten Demo-Emulator.

**Lauf:** 2 bestanden.

**Geprüftes Verhalten:** Retention-Backfill bindet aktualisierte Idempotenzabläufe an denselben Run; native konkurrierende Migration kann fremd neu gebundenes Mapping nicht überschreiben.

**Grenzen und Doubles:** Lokaler Emulator mit anonymen Credentials; kein Produktkonto, keine produktive IAM-/Lastgarantie. Nur eigene Dokumentwurzeln werden aufgeräumt.

**Prüfauftrag für den Folgeaudit:** Die benannten Betriebs- und Testgrenzen bei künftigen Änderungen erneut prüfen; konkrete Paketnachweise stehen im Produktabgleich.

**Direkte Codeverweise:** [app/services/api_run_repository.py](../../app/services/api_run_repository.py).

<details>
<summary>2 Testdefinitionen und ihre Quellstellen</summary>

- [test_retention_backfill_is_atomic_and_does_not_renew_another_run](../../tests/e2e/test_api_retention_transactions.py#L8) (Zeile 8)
- [test_backfill_rechecks_document_after_scan_before_commit](../../tests/e2e/test_api_retention_transactions.py#L31) (Zeile 31)

</details>

<a id="test-bookmark-lifecycle-frontend-py"></a>

## test_bookmark_lifecycle_frontend.py

**Quelle:** [tests/e2e/test_bookmark_lifecycle_frontend.py](../../tests/e2e/test_bookmark_lifecycle_frontend.py) · **Bereiche:** Bookmarks und Verlauf, Scrollen und Navigation.

**Ebene:** Chromium-Browserintegration mit verzögerten HTTP-Doubles.

**Lauf:** 6 bestanden.

**Geprüftes Verhalten:** Optimistisches Löschen vor Serverantwort, keine doppelte Löschanfrage; Erfolg entfernt dauerhaft, 403/500 stellt Zeile wieder her und erlaubt Retry. Gespeicherter Agent-/Standardchat scrollt nach Layout zum Ende; mehrere Zwischenpositionen bei Animation und Reduced-Motionvariante.

**Grenzen und Doubles:** Bookmarks/Chats/Delete vollständig durch Routeantworten simuliert, echtes Firebase-UI-Modul; keine tatsächliche Löschung oder Speichertransaktion.

**Prüfauftrag für den Folgeaudit:** Fehler-/Authwechsel und realen Reload nach Serverlöschung zuordnen.

**Direkte Testhelfer:** [tests/e2e/test_agent_chat_frontend.py](../../tests/e2e/test_agent_chat_frontend.py), [tests/e2e/test_phase4_frontend.py](../../tests/e2e/test_phase4_frontend.py).

<details>
<summary>2 Testdefinitionen und ihre Quellstellen</summary>

- [test_delete_disappears_before_server_reply_and_restores_on_failure](../../tests/e2e/test_bookmark_lifecycle_frontend.py#L9) (Zeile 9)
- [test_open_bookmark_scrolls_smoothly_to_end_after_layout](../../tests/e2e/test_bookmark_lifecycle_frontend.py#L51) (Zeile 51)

</details>

<a id="test-browser-failure-recovery-py"></a>

## test_browser_failure_recovery.py

**Quelle:** [tests/e2e/test_browser_failure_recovery.py](../../tests/e2e/test_browser_failure_recovery.py) · **Bereiche:** Authentifizierung, Build und Betrieb, Markdown und Darstellung.

**Ebene:** Chromium-Browserintegration mit injizierten Ausfällen.

**Lauf:** 3 bestanden.

**Geprüftes Verhalten:** Markdown, Sanitization und KaTeX samt Font funktionieren bei blockiertem jsDelivr ohne CDNrequests; abgelehntes Vote-/Logintoken erzeugt abgefangenen Fehler statt pageerror; Authrefreshfehler zeigt Reloadhinweis und entfernt Skeletons.

**Grenzen und Doubles:** Netzwerk-/Tokenfehler gezielt simuliert, kein Firebase-Login; kleine Renderprobe, kein umfassender XSSaudit.

**Prüfauftrag für den Folgeaudit:** Bundle-/Authfehlerklassen und Recovery über Browserneustart zuordnen.

**Direkte Testhelfer:** [tests/e2e/test_phase4_frontend.py](../../tests/e2e/test_phase4_frontend.py).

<details>
<summary>3 Testdefinitionen und ihre Quellstellen</summary>

- [test_app_renders_markdown_and_math_without_jsdelivr](../../tests/e2e/test_browser_failure_recovery.py#L11) (Zeile 11)
- [test_rejected_vote_and_login_tokens_are_handled](../../tests/e2e/test_browser_failure_recovery.py#L41) (Zeile 41)
- [test_auth_refresh_failure_shows_recovery_message](../../tests/e2e/test_browser_failure_recovery.py#L59) (Zeile 59)

</details>

<a id="test-chat-lifecycle-transactions-py"></a>

## test_chat_lifecycle_transactions.py

**Quelle:** [tests/e2e/test_chat_lifecycle_transactions.py](../../tests/e2e/test_chat_lifecycle_transactions.py) · **Bereiche:** Chats, Memory.

**Ebene:** Echte Firestore-SDK-Transaktionen gegen isolierten Demo-Emulator.

**Lauf:** 5 bestanden.

**Geprüftes Verhalten:** Kontrollierte Commitreihenfolgen Delete/Completion, späte Create-/Complete-Aufrufe, terminaler Failure und Contextfinalisierung. Eigene Nachfahren verschwinden vollständig; fremder Owner bleibt unverändert. Eine echte Löschung pausiert nach committed deleting vor physischem Purge; Completion/Create/Failure müssen den vollständigen Zwischenzustand und Löschjob unverändert lassen.

**Grenzen und Doubles:** Lokaler Emulator mit anonymen Credentials; kein Produktkonto, keine produktive IAM-/Lastgarantie. Nur eigene Dokumentwurzeln werden aufgeräumt.

**Prüfauftrag für den Folgeaudit:** Die benannten Betriebs- und Testgrenzen bei künftigen Änderungen erneut prüfen; konkrete Paketnachweise stehen im Produktabgleich.

**Direkte Codeverweise:** [app/services/chat_context.py](../../app/services/chat_context.py), [app/services/chat_store.py](../../app/services/chat_store.py).

<details>
<summary>4 Testdefinitionen und ihre Quellstellen</summary>

- [test_native_chat_completion_and_delete_never_resurrect_children](../../tests/e2e/test_chat_lifecycle_transactions.py#L23) (Zeile 23)
- [test_native_terminal_failure_rejects_completion_and_remains_failed](../../tests/e2e/test_chat_lifecycle_transactions.py#L57) (Zeile 57)
- [test_native_deleting_tombstone_fences_writes_before_physical_purge](../../tests/e2e/test_chat_lifecycle_transactions.py#L69) (Zeile 69)
- [test_native_context_finalization_cannot_write_after_chat_tombstone](../../tests/e2e/test_chat_lifecycle_transactions.py#L116) (Zeile 116)

</details>

<a id="test-chat-scroll-frontend-py"></a>

## test_chat_scroll_frontend.py

**Quelle:** [tests/e2e/test_chat_scroll_frontend.py](../../tests/e2e/test_chat_scroll_frontend.py) · **Bereiche:** Frontend, Chats.

**Ebene:** Chromium mit echten Appskripten und kontrollierten Antworten.

**Lauf:** 11 bestanden.

**Geprüftes Verhalten:** Anchoring bei langem Follow-up, Streaming, Abschluss, freiwilligem Scrollen und Nachrichtentrennung. Absatzinhalt wird nach finalem Markdown-Neurender neu lokalisiert, um echte Sprünge statt entfernte DOMknoten zu messen.

**Grenzen und Doubles:** Auth/APIantworten kontrolliert; Auswahl an Viewports, keine globale visuelle Baseline.

**Prüfauftrag für den Folgeaudit:** Die benannten Betriebs- und Testgrenzen bei künftigen Änderungen erneut prüfen; konkrete Paketnachweise stehen im Produktabgleich.

**Direkte Testhelfer:** [tests/e2e/test_agent_chat_frontend.py](../../tests/e2e/test_agent_chat_frontend.py), [tests/e2e/test_phase4_frontend.py](../../tests/e2e/test_phase4_frontend.py).

<details>
<summary>3 Testdefinitionen und ihre Quellstellen</summary>

- [test_agent_review_and_completion_keep_visible_answer_still](../../tests/e2e/test_chat_scroll_frontend.py#L13) (Zeile 13)
- [test_consensus_stream_stays_still_and_latest_only_jumps_once](../../tests/e2e/test_chat_scroll_frontend.py#L96) (Zeile 96)
- [test_agent_chat_follows_new_messages_without_stealing_the_readers_position](../../tests/e2e/test_chat_scroll_frontend.py#L157) (Zeile 157)

</details>

<a id="test-composer-mode-bar-py"></a>

## test_composer_mode_bar.py

**Quelle:** [tests/e2e/test_composer_mode_bar.py](../../tests/e2e/test_composer_mode_bar.py) · **Bereiche:** Anhänge, Composer, Konten und Tarife, Responsive UI.

**Ebene:** Chromium-Browserintegration mit vorgegebenem Frontendzustand.

**Lauf:** 7 bestanden.

**Geprüftes Verhalten:** Modebar mit sechs Modellicons, Agent-/Directumschaltung und Quellgates; eingefrorener Directlauf bleibt bei nächster Moduswahl sichtbar, New Run bereinigt. Ausrichtung/Höhe und Reveal-/Reduced-Motionanimation. Deep-/Uploadplanhinweise, Modalnavigation/Fokus/Escape und alternierende Hinweise; Plusfunktionen, Dateiupload und wiederverwendete Anhangsleiste beim Moduswechsel. Aktualisierung 02.10.2026: Eine Toolbaranatomie für Compare/Consensus/Agent; Quellenoptionen folgen dem Modus.

**Grenzen und Doubles:** Echte App-UI auf writerfreiem Server, Auth/Status simuliert und Runzustände teilweise direkt gesetzt; keine Backendtarifautorisierung oder tatsächliche Modellanfrage.

**Prüfauftrag für den Folgeaudit:** Tarif-/Modus-/Anhangszustände über den Versandvertrag zusammenführen.

**Direkte Testhelfer:** [tests/e2e/test_phase4_frontend.py](../../tests/e2e/test_phase4_frontend.py).

<details>
<summary>2 Testdefinitionen und ihre Quellstellen</summary>

- [test_composer_mode_bar](../../tests/e2e/test_composer_mode_bar.py#L12) (Zeile 12)
- [test_toolbar_deep_think_and_upload_reuse_plan_gates](../../tests/e2e/test_composer_mode_bar.py#L109) (Zeile 109)

</details>

<a id="test-consensus-live-progress-py"></a>

## test_consensus_live_progress.py

**Quelle:** [tests/e2e/test_consensus_live_progress.py](../../tests/e2e/test_consensus_live_progress.py) · **Bereiche:** Antwortdarstellung, Barrierefreiheit, Konsens und Unterschiede.

**Ebene:** Isolierter Chromium-Komponententest mit lokal gerouteten Assets.

**Lauf:** 14 bestanden.

**Geprüftes Verhalten:** Modellstatus und Phasenübergang bei 320/390/768/1280 px hell/dunkel, große Zeichenzähler, Reasoning/Waiting/Done und abgeschlossene Phase. Reduced Motion statisch lesbar; nur Phasensummary live; Skip per Tastatur und Touch mit mindestens 44×44-Ziel ohne Layoutsprung oder Overflow. Aktualisierung 02.10.2026: Stepper zeigt Schreiben/Denken/Zeit, ausgefallenes Modell sinkt ab und wird einmal erklärt.

**Grenzen und Doubles:** Eigenes minimales HTML mit echten CSS-/Progressassets, Modelle/Zeitstatus künstlich; kein kompletter Appbootstrap, Backend oder tatsächliches Modellskip.

**Prüfauftrag für den Folgeaudit:** Full-App-Phasenanbindung, echte Streamdauer und Assistenztechnik zuordnen.

**Direkte Codeverweise:** [static/js/consensus-progress.js](../../static/js/consensus-progress.js), [templates/index.html](../../templates/index.html).

<details>
<summary>5 Testdefinitionen und ihre Quellstellen</summary>

- [test_model_status_layout_and_phase_handoff](../../tests/e2e/test_consensus_live_progress.py#L86) (Zeile 86)
- [test_reduced_motion_keeps_status_readable_and_static](../../tests/e2e/test_consensus_live_progress.py#L153) (Zeile 153)
- [test_a_dropped_model_sinks_and_is_explained_once](../../tests/e2e/test_consensus_live_progress.py#L169) (Zeile 169)
- [test_only_phase_summary_is_live_and_skip_is_keyboard_accessible](../../tests/e2e/test_consensus_live_progress.py#L187) (Zeile 187)
- [test_skip_has_a_full_touch_target_without_overflow](../../tests/e2e/test_consensus_live_progress.py#L219) (Zeile 219)

</details>

<a id="test-contradiction-source-ui-py"></a>

## test_contradiction_source_ui.py

**Quelle:** [tests/e2e/test_contradiction_source_ui.py](../../tests/e2e/test_contradiction_source_ui.py) · **Bereiche:** Barrierefreiheit, Konsens und Unterschiede, Quellenprüfung.

**Ebene:** Chromium-UIintegration mit eingespeisten Run-/Quellenzuständen.

**Lauf:** 7 bestanden.

**Geprüftes Verhalten:** Widerspruchsbelege im Reader mit Fokus, temporärer Markierung, Originalzitaten/Links und Auslassungshinweis; verworfenes Ergebnis ohne positive Belege, auch bei schmaler Breite. Neue Konsensprojektion erhält Claims/Karten, numerische Notation bleibt wörtlich, nur Hauptwiderspruch erhält Quellencheck; deaktivierter Check klar benannt. Ausgeschlossener roter Widerspruch erklärt technische/klassifikatorische Gründe ohne Snapshotmutation, Reduced Motion und Forced Colors bleiben fokussierbar.

**Grenzen und Doubles:** seed_insights und page.evaluate erzeugen Run-/Analysedaten direkt; keine tatsächliche Quellenprüfung oder Serverstream trotz eines Stream-Testnamens. Echte Renderer und Browsergeometrie.

**Prüfauftrag für den Folgeaudit:** Aussage-/Positionsbindung und Quellenzustände mit Backendvalidierung sowie echter Streamanbindung abgleichen.

**Direkte Testhelfer:** [tests/e2e/test_model_answer_reader.py](../../tests/e2e/test_model_answer_reader.py), [tests/e2e/test_phase4_frontend.py](../../tests/e2e/test_phase4_frontend.py).

<details>
<summary>3 Testdefinitionen und ihre Quellstellen</summary>

- [test_contradiction_evidence_reader](../../tests/e2e/test_contradiction_source_ui.py#L25) (Zeile 25)
- [test_new_consensus_stream_preserves_claims_and_checks_only_major_contradiction](../../tests/e2e/test_contradiction_source_ui.py#L107) (Zeile 107)
- [test_excluded_red_contradiction_is_explained_in_reader](../../tests/e2e/test_contradiction_source_ui.py#L180) (Zeile 180)

</details>

<a id="test-direct-comparison-preview-py"></a>

## test_direct_comparison_preview.py

**Quelle:** [tests/e2e/test_direct_comparison_preview.py](../../tests/e2e/test_direct_comparison_preview.py) · **Bereiche:** Antwortdarstellung, Composer, Responsive UI.

**Ebene:** Chromium-UIintegration mit direkt erzeugten Runs.

**Lauf:** 8 bestanden.

**Geprüftes Verhalten:** Directvorschau ohne Run, Requests oder Ladezustand; sechs Karten, Draft bleibt bei Umschaltung; Raster/Composer bei Desktop, Tablet, schmaler und Querformatansicht hell/dunkel im Viewport. Reduced Motion, injizierter fertiger Lauf ersetzt Vorschau und bleibt bei Moduswechsel; gespeicherter Offzustand, Modellabwahl und New Comparison erhalten Auswahl. Aktualisierung 02.10.2026: Compare wird über den neuen Modusselektor gewählt.

**Grenzen und Doubles:** Vorschauinteraktion echt; vermeintlich realer Ergebnislauf über seed_reader künstlich erzeugt, kein Backendmodellaufruf.

**Prüfauftrag für den Folgeaudit:** Übergang von Vorschau zu tatsächlichem Senden und Fehlern gemeinsam mit anderen Browserfällen zuordnen.

**Direkte Testhelfer:** [tests/e2e/test_model_answer_reader.py](../../tests/e2e/test_model_answer_reader.py), [tests/e2e/test_phase4_frontend.py](../../tests/e2e/test_phase4_frontend.py).

<details>
<summary>2 Testdefinitionen und ihre Quellstellen</summary>

- [test_preview_toggle_layout_and_real_result](../../tests/e2e/test_direct_comparison_preview.py#L22) (Zeile 22)
- [test_persisted_off_new_comparison_and_model_selection](../../tests/e2e/test_direct_comparison_preview.py#L89) (Zeile 89)

</details>

<a id="test-file-storage-transactions-py"></a>

## test_file_storage_transactions.py

**Quelle:** [tests/e2e/test_file_storage_transactions.py](../../tests/e2e/test_file_storage_transactions.py) · **Bereiche:** Dateien und Dokumente, Agent.

**Ebene:** Echte Firestore-SDK-Transaktionen gegen isolierten Demo-Emulator, echter Cloudadapter und DOCX-/PDF-Renderer.

**Lauf:** 3 bestanden.

**Geprüftes Verhalten:** Konkurrierende Dateiquote, private Objektpfade, Fremddownload ohne Objektread, Originalfehler und wiederaufgenommene Löschung. Dokumenttabellen durchlaufen den nativen Schema-2-Codec; alte Versionen bleiben unverändert. Partielle Chatkaskade behält Versionen bis erfolgreichem Objektretry und bereinigt Quote.

**Grenzen und Doubles:** Lokaler Emulator mit anonymen Credentials; kein Produktkonto, keine produktive IAM-/Lastgarantie. Nur eigene Dokumentwurzeln werden aufgeräumt. Strenges Bucket-Double ohne ACL/public_url; keine produktive Bucket-IAM oder vollständige visuelle Renderprüfung.

**Prüfauftrag für den Folgeaudit:** Die benannten Betriebs- und Testgrenzen bei künftigen Änderungen erneut prüfen; konkrete Paketnachweise stehen im Produktabgleich.

**Direkte Codeverweise:** [app/services/agent_documents.py](../../app/services/agent_documents.py), [app/services/agent_files.py](../../app/services/agent_files.py), [app/services/chat_store.py](../../app/services/chat_store.py), [app/services/llm/provider_runtime.py](../../app/services/llm/provider_runtime.py).

<details>
<summary>3 Testdefinitionen und ihre Quellstellen</summary>

- [test_native_cloud_upload_quota_foreign_download_and_delete_retry](../../tests/e2e/test_file_storage_transactions.py#L50) (Zeile 50)
- [test_native_failed_cloud_upload_preserves_original_error_and_retry_cleans](../../tests/e2e/test_file_storage_transactions.py#L80) (Zeile 80)
- [test_native_cloud_document_versions_are_immutable_and_cascade_retries](../../tests/e2e/test_file_storage_transactions.py#L95) (Zeile 95)

</details>

<a id="test-google-action-transactions-py"></a>

## test_google_action_transactions.py

**Quelle:** [tests/e2e/test_google_action_transactions.py](../../tests/e2e/test_google_action_transactions.py) · **Bereiche:** Google, Agent.

**Ebene:** Echte Firestore-SDK-Transaktionen gegen isolierten Demo-Emulator mit echtem Aktions- und HTTP-Payloadpfad.

**Lauf:** 6 bestanden.

**Geprüftes Verhalten:** Gmail/Kalender: parallele Bestätigung erzeugt höchstens einen externen Writeversuch. Verschlüsselte Dummygrants, Capability-, Revision-, Quota-, Hash-, Ablauf- und Supersessionguards bleiben aktiv. Unknown ist gegen erneuten Write gesperrt, Reconciliation liest nur, fremder Owner verändert nichts.

**Grenzen und Doubles:** Lokaler Emulator mit anonymen Credentials; kein Produktkonto, keine produktive IAM-/Lastgarantie. Nur eigene Dokumentwurzeln werden aufgeräumt. Ausschließlich Google Wire.request ist ersetzt; keine echte Mailzustellung, Einladung oder Provider-Exactly-once-Garantie.

**Prüfauftrag für den Folgeaudit:** Die benannten Betriebs- und Testgrenzen bei künftigen Änderungen erneut prüfen; konkrete Paketnachweise stehen im Produktabgleich.

**Direkte Codeverweise:** [app/services/agent_actions.py](../../app/services/agent_actions.py), [app/services/chat_store.py](../../app/services/chat_store.py), [app/services/google_connections.py](../../app/services/google_connections.py).

<details>
<summary>2 Testdefinitionen und ihre Quellstellen</summary>

- [test_native_google_confirmation_one_attempt_and_unknown_never_retries](../../tests/e2e/test_google_action_transactions.py#L13) (Zeile 13)
- [test_native_google_changed_authority_or_content_performs_no_write](../../tests/e2e/test_google_action_transactions.py#L57) (Zeile 57)

</details>

<a id="test-inspector-polish-py"></a>

## test_inspector_polish.py

**Quelle:** [tests/e2e/test_inspector_polish.py](../../tests/e2e/test_inspector_polish.py) · **Bereiche:** Antwortdarstellung, Barrierefreiheit, Quellenprüfung, Responsive UI.

**Ebene:** Chromium-UIintegration mit vorbereiteten Insights.

**Lauf:** 2 bestanden.

**Geprüftes Verhalten:** Kompakte Unterschiedskarten und Quellenzeilen, je Disclosure nur ein Chevron; vollständige Claimtexte, Diagnosedetails und zusätzlicher Quellenlistenschalter. Footerstatussymbole, Provenienz, kurze Mobilbeschriftung, gleich große erreichbare Aktionen ohne Überlauf; Displaysettings über Reader, richtige Ebene/Tab und Rückkehr; hell/dunkel.

**Grenzen und Doubles:** Daten über seed_insights/page.evaluate injiziert; echte CSS-/Geometriemessung, kein API-/Persistenzablauf oder vollständiger visueller Bildvergleich.

**Prüfauftrag für den Folgeaudit:** Inhaltliche Extremfälle und Assistenztechnik mit tatsächlichen langen Antworten abgleichen.

**Direkte Testhelfer:** [tests/e2e/test_model_answer_reader.py](../../tests/e2e/test_model_answer_reader.py), [tests/e2e/test_phase4_frontend.py](../../tests/e2e/test_phase4_frontend.py).

<details>
<summary>1 Testdefinitionen und ihre Quellstellen</summary>

- [test_inspector_density_disclosures_and_footer](../../tests/e2e/test_inspector_polish.py#L10) (Zeile 10)

</details>

<a id="test-memory-edit-transactions-py"></a>

## test_memory_edit_transactions.py

**Quelle:** [tests/e2e/test_memory_edit_transactions.py](../../tests/e2e/test_memory_edit_transactions.py) · **Bereiche:** Memory, Authentifizierung.

**Ebene:** Echte Firestore-SDK-Transaktionen gegen isolierten Demo-Emulator und echter main-HTTP-Adapter.

**Lauf:** 7 bestanden.

**Geprüftes Verhalten:** Patch/Save-CAS mit einem Gewinner, Leaseübernahme, veralteter Worker und Kontotombstone. Undo bindet Owner, Ablauf und Revision, Repeat ist idempotent. Abgesenktes Limit verändert keine Daten; main liefert Auth-, Tier- und strukturierte Memoryfehler. Fehler am echten SDKcommit nach vier geplanten Applywrites bzw. zwei Undowrites hinterlässt Profil/Request/Revision/Quota unverändert; Reserve und Undo beachten den Tombstone ebenfalls.

**Grenzen und Doubles:** Lokaler Emulator mit anonymen Credentials; kein Produktkonto, keine produktive IAM-/Lastgarantie. Nur eigene Dokumentwurzeln werden aufgeräumt. main verwendet echte Auth-/Tierguards; lediglich Firebase-SDKidentität und ein gezielter Read-/Committransportfehler sind kontrolliert.

**Prüfauftrag für den Folgeaudit:** Die benannten Betriebs- und Testgrenzen bei künftigen Änderungen erneut prüfen; konkrete Paketnachweise stehen im Produktabgleich.

**Direkte Codeverweise:** [app/api/routers/users.py](../../app/api/routers/users.py), [app/core/config.py](../../app/core/config.py), [app/core/security.py](../../app/core/security.py), [app/services/memory_edit.py](../../app/services/memory_edit.py), [app/services/persistence_guard.py](../../app/services/persistence_guard.py), [app/services/user_memory.py](../../app/services/user_memory.py).

<details>
<summary>6 Testdefinitionen und ihre Quellstellen</summary>

- [test_native_patch_and_manual_save_have_one_revision_winner](../../tests/e2e/test_memory_edit_transactions.py#L44) (Zeile 44)
- [test_native_undo_is_lossless_owner_bound_idempotent_and_revision_checked](../../tests/e2e/test_memory_edit_transactions.py#L77) (Zeile 77)
- [test_native_lost_lease_and_account_tombstone_never_write_memory](../../tests/e2e/test_memory_edit_transactions.py#L98) (Zeile 98)
- [test_native_memory_undo_through_main_preserves_error_status_and_body](../../tests/e2e/test_memory_edit_transactions.py#L137) (Zeile 137)
- [test_native_memory_commit_failure_has_no_partial_profile_request_revision_or_quota](../../tests/e2e/test_memory_edit_transactions.py#L182) (Zeile 182)
- [test_native_undo_rejects_a_later_manual_revision_without_any_write](../../tests/e2e/test_memory_edit_transactions.py#L215) (Zeile 215)

</details>

<a id="test-mobile-navigation-py"></a>

## test_mobile_navigation.py

**Quelle:** [tests/e2e/test_mobile_navigation.py](../../tests/e2e/test_mobile_navigation.py) · **Bereiche:** Authentifizierung, Barrierefreiheit, Responsive UI, Watch.

**Ebene:** Chromium-Browserintegration mit simuliertem Auth und vorbereiteten Antworten.

**Lauf:** 12 bestanden.

**Geprüftes Verhalten:** Mobiler opaker 56-px-Header mit mindestens 44-px-Zielen, Aktionen/Sidebarmenü erreichbar, Header weicht beim Lesen, Fokus/inert und Reduced Motion. Gastheader passt, Login-/Registrierungsdialoge und Authwechsel; Watchdashboard/New Chat über gleiche Navigation. Desktoppositionen nach Wechsel erhalten; Share-/Watch-/Cite-Dialoge mit Fokusrückgabe, identische Controls bei Resize, New Chat leert und fokussiert Eingabe.

**Grenzen und Doubles:** Auth-SDK/APIzustände simuliert, lange Antworten/Insights eingespeist; tatsächliche CSS-/Hit-Test-/Scrollprüfung, aber kein realer Login oder Watch-CRUD.

**Prüfauftrag für den Folgeaudit:** Gerätekeyboard, Browserzoom und vollständige Tastaturnavigation zuordnen.

**Direkte Testhelfer:** [tests/e2e/test_model_answer_reader.py](../../tests/e2e/test_model_answer_reader.py), [tests/e2e/test_phase4_frontend.py](../../tests/e2e/test_phase4_frontend.py).

<details>
<summary>5 Testdefinitionen und ihre Quellstellen</summary>

- [test_mobile_menu_has_opaque_header_and_yields_while_reading](../../tests/e2e/test_mobile_navigation.py#L26) (Zeile 26)
- [test_guest_navigation_fits_and_auth_dialogs_open](../../tests/e2e/test_mobile_navigation.py#L85) (Zeile 85)
- [test_watch_navigation_uses_the_same_mobile_surface](../../tests/e2e/test_mobile_navigation.py#L139) (Zeile 139)
- [test_desktop_sidebar_controls_keep_their_original_layout](../../tests/e2e/test_mobile_navigation.py#L172) (Zeile 172)
- [test_mobile_actions_keep_dialogs_focus_and_new_chat_behavior](../../tests/e2e/test_mobile_navigation.py#L189) (Zeile 189)

</details>

<a id="test-model-answer-reader-py"></a>

## test_model_answer_reader.py

**Quelle:** [tests/e2e/test_model_answer_reader.py](../../tests/e2e/test_model_answer_reader.py) · **Bereiche:** Antwortdarstellung, Bookmarks und Verlauf, Demo, Responsive UI.

**Ebene:** Chromium-UIintegration auf echter Apphülle mit Fixture-Runs.

**Lauf:** 51 bestanden.

**Geprüftes Verhalten:** Breiter Reader und Chat zentriert mit/ohne Sidebar; Quellenkarten/Faviconfallback. Resize/kurze Viewports, Modal-/Dockedwechsel, gemeinsames Inhaltsraster und große Scrollfläche; Unterschiede/Quellen/Antworten turngebunden, historische Ansicht bleibt bei Projektion. Directantworten inline inkl. Modellfehler, sechs Karten und gespeicherte Directantwort trotz aktueller Agentpräferenz. Eigene Picker, verschiedene Vergleichsmodelle, mobile Seitenwahl, Escape/Fokusrückgabe, lange Frage. Demo verwendet sechs Balancedmodelle, richtige Labels, Skeleton bis Abschluss und echtes Markdown statt Spinnermarkup. Viele Breiten bis 2560 px und hell/dunkel. Aktualisierung 02.10.2026: Leser und Settings verwenden runMode statt Legacy-Agent-Schalter.

**Grenzen und Doubles:** seed_reader/seed_insights erzeugen Runs ohne LLM-/Firestoreanfragen; einzelne Bookmark-APIs simuliert, Demo lokal. Echte Browserdarstellung, optionale Screenshots ohne automatischen Pixelvergleich.

**Prüfauftrag für den Folgeaudit:** UIzustände mit tatsächlich gespeicherten Turns und Streamingfehlern verbinden.

**Direkte Testhelfer:** [tests/e2e/test_phase4_frontend.py](../../tests/e2e/test_phase4_frontend.py).

<details>
<summary>12 Testdefinitionen und ihre Quellstellen</summary>

- [test_wide_reader_centering_and_source_cards](../../tests/e2e/test_model_answer_reader.py#L74) (Zeile 74)
- [test_single_difference_and_missing_favicon](../../tests/e2e/test_model_answer_reader.py#L116) (Zeile 116)
- [test_detail_panel_survives_resize_and_short_viewports](../../tests/e2e/test_model_answer_reader.py#L140) (Zeile 140)
- [test_expanded_reader_uses_one_content_grid](../../tests/e2e/test_model_answer_reader.py#L195) (Zeile 195)
- [test_differences_and_sources_share_turn_scoped_sidebar](../../tests/e2e/test_model_answer_reader.py#L241) (Zeile 241)
- [test_reader_responsive_comparison_and_return](../../tests/e2e/test_model_answer_reader.py#L294) (Zeile 294)
- [test_archived_reader_keeps_turn_sources_during_projection](../../tests/e2e/test_model_answer_reader.py#L332) (Zeile 332)
- [test_direct_reader_remains_inline_and_lists_failed_models](../../tests/e2e/test_model_answer_reader.py#L353) (Zeile 353)
- [test_reader_custom_pickers_and_dismissal](../../tests/e2e/test_model_answer_reader.py#L391) (Zeile 391)
- [test_direct_comparison_shares_chat_shell_and_fits_picker](../../tests/e2e/test_model_answer_reader.py#L442) (Zeile 442)
- [test_fresh_agent_mode_session_opens_saved_direct_answers](../../tests/e2e/test_model_answer_reader.py#L508) (Zeile 508)
- [test_demo_uses_all_balanced_models_and_never_displays_spinner_markup](../../tests/e2e/test_model_answer_reader.py#L552) (Zeile 552)

</details>

<a id="test-model-configuration-transactions-py"></a>

## test_model_configuration_transactions.py

**Quelle:** [tests/e2e/test_model_configuration_transactions.py](../../tests/e2e/test_model_configuration_transactions.py) · **Bereiche:** Admin, Modelle.

**Ebene:** Echte Firestore-SDK-Transaktionen gegen isolierten Demo-Emulator mit zwei durch Events koordinierten Writern.

**Lauf:** 4 bestanden.

**Geprüftes Verhalten:** Writer A scheitert bei Runtimeaktivierung, nachdem unabhängige SDK-Transaktion B eine neuere Revision gespeichert hat. B bleibt bei vorhandener und fehlender Ausgangskonfiguration erhalten; stale Save wird abgewiesen. Zusätzlich wird nach echter Aktivierungsfehlfunktion der native Rollback-RPC abgewiesen: ursprünglicher Fehler bleibt sichtbar, kritische inhaltsfreie Diagnose kennzeichnet fehlende Wiederherstellung der Datenbank, Runtime behält ihren Snapshot.

**Grenzen und Doubles:** Lokaler Emulator mit anonymen Credentials; kein Produktkonto, keine produktive IAM-/Lastgarantie. Nur eigene Dokumentwurzeln werden aufgeräumt. Runtimeaktivierungsfehler wird injiziert; keine globale Atomizität zwischen DB und mehreren Serverruntimes.

**Prüfauftrag für den Folgeaudit:** Die benannten Betriebs- und Testgrenzen bei künftigen Änderungen erneut prüfen; konkrete Paketnachweise stehen im Produktabgleich.

**Direkte Codeverweise:** [app/api/routers/admin.py](../../app/api/routers/admin.py), [app/core/config.py](../../app/core/config.py), [app/core/security.py](../../app/core/security.py).

<details>
<summary>2 Testdefinitionen und ihre Quellstellen</summary>

- [test_native_failed_model_activation_preserves_other_writer](../../tests/e2e/test_model_configuration_transactions.py#L11) (Zeile 11)
- [test_native_activation_and_rollback_rpc_failure_is_not_reported_as_restored](../../tests/e2e/test_model_configuration_transactions.py#L49) (Zeile 49)

</details>

<a id="test-persisted-journeys-py"></a>

## test_persisted_journeys.py

**Quelle:** [tests/e2e/test_persisted_journeys.py](../../tests/e2e/test_persisted_journeys.py) · **Bereiche:** Chats, Agent, Quellen, Shares, Watches, Authentifizierung, Konten und Tarife.

**Ebene:** Chromium → gebautes AppFirebase → echte main-Routen → nativer Firestore.

**Lauf:** 6 bestanden.

**Geprüftes Verhalten:** J01 speichert zwei Consensusläufe mit getrennten Turn-IDs und korrekt gebundener Follow-up-Kontextversion; erster Turn ohne Kontext, Reload und exakte reguläre Buchung. J02 stoppt Agentarbeit, erhält Teilantwort und gemessene Providerstepkosten, Recover startet/bucht nichts erneut. J03 importiert ausdrücklich historische V3-Daten und prüft echtes Own-Key-Resume, native Packagecommits, mehrseitiges Nachladen/Revisionswechsel/Reload. J04 nutzt echten Saved-Pending-/Shareadapter, Follow/Double-Opt-in und native Watchversion. J05 löscht während Agentarbeit, sperrt späte Writes und erhält fremden Owner nach Wechsel/Reload. Echte erschöpfte Bookmarkquote trennt sichtbaren Antworterfolg von fehlgeschlagener Speicherung.

**Grenzen und Doubles:** Firebaseidentität, Modelle und Mail sind äußere Doubles; direkte Browser-Firestorezugriffe verboten, App-APIs nicht abgefangen. E2E-Lifespan unterdrückt globale Scheduler; ownergebundener Watchpfad gezielt getrieben. Historischer V3-Job wird ausdrücklich importiert, neue V4-Runs erhalten keinen künstlichen Altjob. J03 führt den wirklichen Worker samt Judge-Request/-Parser, Quotevalidierung, Cache und nativen Paketcommits aus; nur Dokumentfetch und Judge-HTTP sind kontrolliert. J05 wartet vor dem Datenprüfung auf echtes Responseende und Capacityfreigabe nach Producer-/Settlementabschluss.

**Prüfauftrag für den Folgeaudit:** Die benannten Betriebs- und Testgrenzen bei künftigen Änderungen erneut prüfen; konkrete Paketnachweise stehen im Produktabgleich.

**Direkte Codeverweise:** [app/core/e2e_profile.py](../../app/core/e2e_profile.py).

<details>
<summary>6 Testdefinitionen und ihre Quellstellen</summary>

- [test_j01_saved_consensus_reload_followup_keeps_native_identity_and_context](../../tests/e2e/test_persisted_journeys.py#L150) (Zeile 150)
- [test_j02_stop_reload_recover_preserves_partial_and_charges_only_started_step](../../tests/e2e/test_persisted_journeys.py#L186) (Zeile 186)
- [test_j03_historical_source_job_resumes_and_pages_a_native_revision](../../tests/e2e/test_persisted_journeys.py#L227) (Zeile 227)
- [test_j04_app_share_follow_watch_versions_bind_to_saved_native_result](../../tests/e2e/test_persisted_journeys.py#L261) (Zeile 261)
- [test_j05_delete_during_agent_work_fences_late_writes_and_owner_switch](../../tests/e2e/test_persisted_journeys.py#L308) (Zeile 308)
- [test_persistence_quota_failure_keeps_answer_visible_and_never_claims_saved](../../tests/e2e/test_persisted_journeys.py#L352) (Zeile 352)

</details>

<a id="test-phase2-transactions-py"></a>

## test_phase2_transactions.py

**Quelle:** [tests/e2e/test_phase2_transactions.py](../../tests/e2e/test_phase2_transactions.py) · **Bereiche:** Chats, Watches, Shares.

**Ebene:** Echte Firestore-SDK-Transaktionen gegen isolierten Demo-Emulator.

**Lauf:** 4 bestanden.

**Geprüftes Verhalten:** Native Chat-/Watchlimits, Shareidempotenz und parallele Reportinkremente mit gültigen heutigen Fixtures. Reports setzen Reviewflag und Gründe, ändern den Indexstatus gemäß aktuellem Vertrag nicht. Erschöpfte SDK-Retries werden vor getrenntem Replay gegen Zahl erfolgreicher Aufrufe und gespeicherten Zähler abgeglichen.

**Grenzen und Doubles:** Lokaler Emulator mit anonymen Credentials; kein Produktkonto, keine produktive IAM-/Lastgarantie. Nur eigene Dokumentwurzeln werden aufgeräumt. Keine erfolgreiche Reportannahme für abgebrochene Aufrufe behauptet.

**Prüfauftrag für den Folgeaudit:** Die benannten Betriebs- und Testgrenzen bei künftigen Änderungen erneut prüfen; konkrete Paketnachweise stehen im Produktabgleich.

**Direkte Codeverweise:** [app/core/e2e_profile.py](../../app/core/e2e_profile.py), [app/services/chat_store.py](../../app/services/chat_store.py), [app/services/share_snapshots.py](../../app/services/share_snapshots.py), [app/services/watch_service.py](../../app/services/watch_service.py).

<details>
<summary>4 Testdefinitionen und ihre Quellstellen</summary>

- [test_two_workers_cannot_exceed_owner_watch_limit](../../tests/e2e/test_phase2_transactions.py#L29) (Zeile 29)
- [test_two_workers_publish_one_pending_share_and_consume_one_quota](../../tests/e2e/test_phase2_transactions.py#L97) (Zeile 97)
- [test_two_workers_cannot_exceed_owner_chat_limit](../../tests/e2e/test_phase2_transactions.py#L140) (Zeile 140)
- [test_parallel_reports_never_lose_increments_or_change_indexing](../../tests/e2e/test_phase2_transactions.py#L167) (Zeile 167)

</details>

<a id="test-phase4-frontend-py"></a>

## test_phase4_frontend.py

**Quelle:** [tests/e2e/test_phase4_frontend.py](../../tests/e2e/test_phase4_frontend.py) · **Bereiche:** Frontend, Authentifizierung, Chats.

**Ebene:** Chromium und ein gemeinsam gestarteter lokaler Testserver.

**Lauf:** 29 bestanden.

**Geprüftes Verhalten:** Composer, Modus, Memory, Einstellungen, Account-/Turnbindungen und Sourceansicht mit aktuellen autoritativen Antwortreceipts. Belegter Serverport wird abgelehnt; alle importierten Fixtures nutzen denselben Serverprozess.

**Grenzen und Doubles:** API/Auth kontrolliert; Serverport- und Fixtureisolation ist kein produktiver Deploynachweis.

**Prüfauftrag für den Folgeaudit:** Die benannten Betriebs- und Testgrenzen bei künftigen Änderungen erneut prüfen; konkrete Paketnachweise stehen im Produktabgleich.

**Direkte Codeverweise:** [static/firebase.js](../../static/firebase.js).

<details>
<summary>24 Testdefinitionen und ihre Quellstellen</summary>

- [test_phase4_server_reuses_its_child_and_rejects_an_unowned_listener](../../tests/e2e/test_phase4_frontend.py#L143) (Zeile 143)
- [test_source_verification_display_and_restore](../../tests/e2e/test_phase4_frontend.py#L215) (Zeile 215)
- [test_composer_source_check_toggle_persists_and_freezes_run_payload](../../tests/e2e/test_phase4_frontend.py#L349) (Zeile 349)
- [test_followup_stream_preserves_history_and_model_loading_nodes](../../tests/e2e/test_phase4_frontend.py#L404) (Zeile 404)
- [test_source_judge_stream_keeps_completed_claims_and_differences](../../tests/e2e/test_phase4_frontend.py#L445) (Zeile 445)
- [test_auth_module_failure_exposes_usable_login_dialog](../../tests/e2e/test_phase4_frontend.py#L643) (Zeile 643)
- [test_watch_feature_nudge_never_raises_answer_over_fixed_composer](../../tests/e2e/test_phase4_frontend.py#L678) (Zeile 678)
- [test_account_a_late_bookmark_save_cannot_mutate_account_b](../../tests/e2e/test_phase4_frontend.py#L756) (Zeile 756)
- [test_account_a_share_response_cannot_overwrite_account_b_view](../../tests/e2e/test_phase4_frontend.py#L796) (Zeile 796)
- [test_last_bookmark_click_wins_when_detail_responses_arrive_out_of_order](../../tests/e2e/test_phase4_frontend.py#L841) (Zeile 841)
- [test_logged_out_watch_deep_link_survives_and_late_login_renders](../../tests/e2e/test_phase4_frontend.py#L883) (Zeile 883)
- [test_all_model_failures_end_in_error_without_consensus](../../tests/e2e/test_phase4_frontend.py#L909) (Zeile 909)
- [test_two_runs_keep_payloads_views_and_cancel_controllers_isolated](../../tests/e2e/test_phase4_frontend.py#L937) (Zeile 937)
- [test_two_runs_finish_reverse_order_behind_a_saved_bookmark](../../tests/e2e/test_phase4_frontend.py#L1256) (Zeile 1256)
- [test_missing_answer_receipts_remain_visible_but_never_start_consensus](../../tests/e2e/test_phase4_frontend.py#L1795) (Zeile 1795)
- [test_disabled_agent_mode_is_six_answers_only](../../tests/e2e/test_phase4_frontend.py#L1816) (Zeile 1816)
- [test_attachment_filter_blocks_one_model_run_before_prepare](../../tests/e2e/test_phase4_frontend.py#L1936) (Zeile 1936)
- [test_watched_navigation_closes_the_shared_modal](../../tests/e2e/test_phase4_frontend.py#L1976) (Zeile 1976)
- [test_cancel_during_token_resolution_keeps_followup_and_creates_no_usage_run](../../tests/e2e/test_phase4_frontend.py#L2002) (Zeile 2002)
- [test_late_watch_create_cannot_overwrite_newer_share_modal](../../tests/e2e/test_phase4_frontend.py#L2056) (Zeile 2056)
- [test_watch_create_is_not_sent_after_modal_changes_during_token_wait](../../tests/e2e/test_phase4_frontend.py#L2112) (Zeile 2112)
- [test_failed_utc_usage_refresh_retries_until_authoritative_success](../../tests/e2e/test_phase4_frontend.py#L2160) (Zeile 2160)
- [test_template_visibility_classes_remain_overridable_by_ui_controls](../../tests/e2e/test_phase4_frontend.py#L2215) (Zeile 2215)
- [test_key_claim_fallback_cleans_orphan_markdown_and_renders_math](../../tests/e2e/test_phase4_frontend.py#L2246) (Zeile 2246)

</details>

<a id="test-prompt-config-transactions-py"></a>

## test_prompt_config_transactions.py

**Quelle:** [tests/e2e/test_prompt_config_transactions.py](../../tests/e2e/test_prompt_config_transactions.py) · **Bereiche:** Admin, Nebenläufigkeit, Persistenz, Prompts.

**Ebene:** Firestore-Emulatorintegration mit echten SDK-Transaktionen und Threads.

**Lauf:** 1 bestanden.

**Geprüftes Verhalten:** Zwei Editoren mit Revision null: genau ein Gewinner, gespeicherter Inhalt und Editor passen zusammen, genau ein unveränderter Historieneintrag; anderer Store sieht Ergebnis; Defaultsrestore erzeugt Revision zwei und erhält beide Historien.

**Grenzen und Doubles:** Isoliertes Konfigurationsdokument durch Storeunterklasse, zwei Threads; kein HTTP-/Adminbrowserpfad.

**Prüfauftrag für den Folgeaudit:** API-Konfliktstatus, Cacheinvalidierung und weitere Revisions-/Restoregrenzen zuordnen.

**Direkte Codeverweise:** [app/core/e2e_profile.py](../../app/core/e2e_profile.py), [app/services/prompt_config.py](../../app/services/prompt_config.py).

<details>
<summary>1 Testdefinitionen und ihre Quellstellen</summary>

- [test_prompt_configuration_conflict_and_history_are_atomic](../../tests/e2e/test_prompt_config_transactions.py#L12) (Zeile 12)

</details>

<a id="test-public-composer-mockups-py"></a>

## test_public_composer_mockups.py

**Quelle:** [tests/e2e/test_public_composer_mockups.py](../../tests/e2e/test_public_composer_mockups.py) · **Bereiche:** Responsive UI, Öffentliche Seiten.

**Ebene:** Chromium-Browserintegration öffentlicher lokaler Seiten.

**Lauf:** 5 bestanden.

**Geprüftes Verhalten:** Startseite enthält zwei ausgerichtete Composerpreviews, sechs geladene Modellicons, zugänglichen Quellenstatus und Demolink; Scrollszene blendet Toolbar phasenabhängig ein/aus, Reduced Motion statisch. /consensus-engine zeigt Ergebnisdarstellung und Quellencheck-FAQ ohne Composerpreview; mehrere Breiten/Themes ohne Overflow/JSfehler.

**Grenzen und Doubles:** Keine Anmeldung oder Modellabfrage; Screenshots werden als Artefakt gespeichert, nicht gegen Baseline verglichen.

**Prüfauftrag für den Folgeaudit:** Weitere öffentliche Seitentemplates, Browser und tatsächlich ausgelieferte Assets abgleichen.

**Direkte Testhelfer:** [tests/e2e/test_phase4_frontend.py](../../tests/e2e/test_phase4_frontend.py).

<details>
<summary>1 Testdefinitionen und ihre Quellstellen</summary>

- [test_public_composer_mockups](../../tests/e2e/test_public_composer_mockups.py#L30) (Zeile 30)

</details>

<a id="test-reader-density-py"></a>

## test_reader_density.py

**Quelle:** [tests/e2e/test_reader_density.py](../../tests/e2e/test_reader_density.py) · **Bereiche:** Frontend, Chats.

**Ebene:** Chromium mit echten Readerkomponenten und gemessener Geometrie.

**Lauf:** 2 bestanden.

**Geprüftes Verhalten:** Lesedichte/Abstände und Quellen-/Textdarstellung folgen aktueller Sekundärfarbe und gruppierten Quellenpills; CSS-Pixelgrenzen berücksichtigen Rundung.

**Grenzen und Doubles:** Ausgewählte Desktop-/Mobilviewports, kontrollierte Inhalte; kein flächiger visueller oder Accessibilityaudit.

**Prüfauftrag für den Folgeaudit:** Die benannten Betriebs- und Testgrenzen bei künftigen Änderungen erneut prüfen; konkrete Paketnachweise stehen im Produktabgleich.

**Direkte Testhelfer:** [tests/e2e/test_model_answer_reader.py](../../tests/e2e/test_model_answer_reader.py), [tests/e2e/test_phase4_frontend.py](../../tests/e2e/test_phase4_frontend.py).

<details>
<summary>1 Testdefinitionen und ihre Quellstellen</summary>

- [test_six_answers_leave_room_to_read_and_keep_touch_targets](../../tests/e2e/test_reader_density.py#L10) (Zeile 10)

</details>

<a id="test-reader-review-regressions-py"></a>

## test_reader_review_regressions.py

**Quelle:** [tests/e2e/test_reader_review_regressions.py](../../tests/e2e/test_reader_review_regressions.py) · **Bereiche:** Antwortdarstellung, Bookmarks und Verlauf, Composer, Nutzergedächtnis.

**Ebene:** Chromium-UIintegration mit Fixture-Runs.

**Lauf:** 5 bestanden.

**Geprüftes Verhalten:** Liveinspektor gibt verschobene Quellen-/Unterschiedscontainer beim Followup zurück und vermischt neue Frage nicht mit alten Belegen. Textauswahl im Direct-, Docked- und Mobilreader führt zu Composerzitat oder Gedächtniseditor; Markierungsstil, Fokus, Schließen und Quellenlabel.

**Grenzen und Doubles:** Runs/Insights direkt eingespeist, Auswahl programmgesteuert; Editoröffnung geprüft, kein tatsächlicher Memorysave oder Promptwirkung.

**Prüfauftrag für den Folgeaudit:** Auswahlaktionen mit realen Markdownstrukturen und Persistenz zuordnen.

**Direkte Testhelfer:** [tests/e2e/test_model_answer_reader.py](../../tests/e2e/test_model_answer_reader.py), [tests/e2e/test_phase4_frontend.py](../../tests/e2e/test_phase4_frontend.py).

<details>
<summary>2 Testdefinitionen und ihre Quellstellen</summary>

- [test_live_inspector_releases_shared_targets_on_followup](../../tests/e2e/test_reader_review_regressions.py#L9) (Zeile 9)
- [test_reader_selection_actions_reach_composer_and_memory](../../tests/e2e/test_reader_review_regressions.py#L64) (Zeile 64)

</details>

<a id="test-run-cancel-and-progress-py"></a>

## test_run_cancel_and_progress.py

**Quelle:** [tests/e2e/test_run_cancel_and_progress.py](../../tests/e2e/test_run_cancel_and_progress.py) · **Bereiche:** Consensus, Agent, Frontend.

**Ebene:** Chromium mit echten Registry- und DOMereignissen.

**Lauf:** 3 bestanden.

**Geprüftes Verhalten:** Pending, Streaming und Differences bleiben vollständig abbrechbar. Der Abbruch folgt dem tatsächlichen aktuellen Lauf, räumt UIstatus auf und entfernt nach Abschluss das einzelne Zustandsklassentoken; kein unbenutzter Legacy-startRun-Hook.

**Grenzen und Doubles:** Echte App-HTTP-Routen und Firestore im app_page-Lauf; Firebase-Frontendstub/MOCK_AUTH und externe Modelle kontrolliert. Persistierter Agentstop und Settlement zusätzlich in J02.

**Prüfauftrag für den Folgeaudit:** Die benannten Betriebs- und Testgrenzen bei künftigen Änderungen erneut prüfen; konkrete Paketnachweise stehen im Produktabgleich.

**Direkte Testhelfer:** [tests/e2e/test_smoke.py](../../tests/e2e/test_smoke.py).

<details>
<summary>3 Testdefinitionen und ihre Quellstellen</summary>

- [test_send_button_stays_cancelable_until_consensus_is_done](../../tests/e2e/test_run_cancel_and_progress.py#L47) (Zeile 47)
- [test_send_button_cancels_a_running_consensus](../../tests/e2e/test_run_cancel_and_progress.py#L94) (Zeile 94)
- [test_model_rows_restart_empty_on_a_second_run](../../tests/e2e/test_run_cancel_and_progress.py#L109) (Zeile 109)

</details>

<a id="test-run-mode-selector-py"></a>

## test_run_mode_selector.py

**Quelle:** [tests/e2e/test_run_mode_selector.py](../../tests/e2e/test_run_mode_selector.py) · **Bereiche:** Frontend, Agent, Einstellungen.

**Ebene:** Chromium mit writerfreiem Server und gemockten APIs.

**Lauf:** 11 bestanden.

**Geprüftes Verhalten:** Legacy-Migration, ein Modusselektor für Toolbar/Settings, Compare ohne automatische Synthese, Agentzugriff und Chatfamilienbindung, Wartezustand bei ausstehendem Accountstatus und Fallback bei Fehler; Tastatur-/Mobil-/Hell-Dunkelansicht.

**Grenzen und Doubles:** Auth-/Model-/Usageantworten simuliert; kein echter Modelllauf.

**Prüfauftrag für den Folgeaudit:** Die benannten Mock-/Integrationsgrenzen am realen Adapter prüfen; Zuordnung und offene Aufgaben stehen in der Produktmatrix.

<details>
<summary>6 Testdefinitionen und ihre Quellstellen</summary>

- [test_legacy_agent_mode_switch_migrates_once](../../tests/e2e/test_run_mode_selector.py#L41) (Zeile 41)
- [test_one_selector_drives_mode_tools_and_settings](../../tests/e2e/test_run_mode_selector.py#L60) (Zeile 60)
- [test_without_agent_access_agent_is_not_offered_and_falls_back](../../tests/e2e/test_run_mode_selector.py#L150) (Zeile 150)
- [test_open_chat_keeps_its_family](../../tests/e2e/test_run_mode_selector.py#L166) (Zeile 166)
- [test_stored_agent_choice_waits_for_access_instead_of_sending_consensus](../../tests/e2e/test_run_mode_selector.py#L194) (Zeile 194)
- [test_failed_status_check_releases_the_agent_wait](../../tests/e2e/test_run_mode_selector.py#L209) (Zeile 209)

</details>

<a id="test-scheduler-transactions-py"></a>

## test_scheduler_transactions.py

**Quelle:** [tests/e2e/test_scheduler_transactions.py](../../tests/e2e/test_scheduler_transactions.py) · **Bereiche:** Watches, Topics, SEO, Betrieb.

**Ebene:** Echte Firestore-SDK-Transaktionen gegen isolierten Demo-Emulator.

**Lauf:** 6 bestanden.

**Geprüftes Verhalten:** Echte fällige Watch-/Topicqueries, Claimkonkurrenz und Tagesbudget, Leaseübernahme und stale Watch-/Topic-/SEO-Owner. SEO-Abschluss erfolgt atomar und einmalig. Abgebrochene Topic-/SEO-Claims werden sichtbar erfasst und genau einmal nach Beruhigung erneut aufgerufen. Der wirkliche Topicloop führt Duequery, Claim und Erfolgs-/Fehlerabschluss nativ aus. Der wirkliche SEOloop persistiert Collectionfehler/Benachrichtigungsstatus und löst die Lease; beide Loops enden an Cancellation ohne weiteren Dispatch.

**Grenzen und Doubles:** Lokaler Emulator mit anonymen Credentials; kein Produktkonto, keine produktive IAM-/Lastgarantie. Nur eigene Dokumentwurzeln werden aufgeräumt. Schedulerfehler können einen nächsten Tick erfordern; keine Ausfallfreiheit unter Last. Die tatsächlichen Asyncscheduler laufen in eigenem Thread/Loop, damit eine bestehende synchrone Playwright-Session nicht asyncio.run blockiert. Nur direktes SDK-Aborted oder ValueError mit genau dieser Ursache erlaubt den sichtbar gemeldeten einzelnen nächsten Tick; andere Fehler und erneuter Abbruch bleiben Fehler.

**Prüfauftrag für den Folgeaudit:** Die benannten Betriebs- und Testgrenzen bei künftigen Änderungen erneut prüfen; konkrete Paketnachweise stehen im Produktabgleich.

**Direkte Codeverweise:** [app/services/seo_weekly_review.py](../../app/services/seo_weekly_review.py), [app/services/topic_runner.py](../../app/services/topic_runner.py), [app/services/topics.py](../../app/services/topics.py), [app/services/watch_service.py](../../app/services/watch_service.py).

<details>
<summary>5 Testdefinitionen und ihre Quellstellen</summary>

- [test_native_due_queries_and_topic_claim_fence](../../tests/e2e/test_scheduler_transactions.py#L21) (Zeile 21)
- [test_native_seo_claim_and_finish_require_current_owner](../../tests/e2e/test_scheduler_transactions.py#L51) (Zeile 51)
- [test_native_watch_claim_budget_and_stale_renewal](../../tests/e2e/test_scheduler_transactions.py#L74) (Zeile 74)
- [test_native_topic_loop_commits_due_tick_and_stops_on_cancel](../../tests/e2e/test_scheduler_transactions.py#L94) (Zeile 94)
- [test_native_seo_loop_persists_failure_releases_lease_and_cancels](../../tests/e2e/test_scheduler_transactions.py#L149) (Zeile 149)

</details>

<a id="test-seo-repository-queries-py"></a>

## test_seo_repository_queries.py

**Quelle:** [tests/e2e/test_seo_repository_queries.py](../../tests/e2e/test_seo_repository_queries.py) · **Bereiche:** SEO.

**Ebene:** Echte Firestore-SDK-Transaktionen gegen isolierten Demo-Emulator.

**Lauf:** 1 bestanden.

**Geprüftes Verhalten:** Native Query-/BatchGet-Rückgaben für last_run, list_judgments und latest_query_snapshot; neueste Daten und Dokumentidentität werden korrekt zugeordnet.

**Grenzen und Doubles:** Lokaler Emulator mit anonymen Credentials; kein Produktkonto, keine produktive IAM-/Lastgarantie. Nur eigene Dokumentwurzeln werden aufgeräumt.

**Prüfauftrag für den Folgeaudit:** Die benannten Betriebs- und Testgrenzen bei künftigen Änderungen erneut prüfen; konkrete Paketnachweise stehen im Produktabgleich.

**Direkte Codeverweise:** [app/services/seo_repository.py](../../app/services/seo_repository.py).

<details>
<summary>1 Testdefinitionen und ihre Quellstellen</summary>

- [test_seo_native_latest_judgments_and_unordered_batch_identity](../../tests/e2e/test_seo_repository_queries.py#L8) (Zeile 8)

</details>

<a id="test-smoke-py"></a>

## test_smoke.py

**Quelle:** [tests/e2e/test_smoke.py](../../tests/e2e/test_smoke.py) · **Bereiche:** Anhänge, Composer, Konsens und Unterschiede, Markdown und Darstellung, Responsive UI, Watch.

**Ebene:** Chromium gegen echte App-Routen und Demo-Firestore mit kontrollierter Identität/Modellen; ergänzend direkte Rendererfälle.

**Lauf:** 43 bestanden.

**Geprüftes Verhalten:** Bootstrap und Konsole, Sidebar/Search/Picker, responsive Textareahöhe auch nach abgeschlossener Breitenanimation, stabile Ein-/Mehrzeilenform, Fokus/Caret und Anhänge. Streaming von sechs ausgewählten Modellantworten, Direct-/Consensusablauf, Score/Claims/Differences und archivierte Antworten im laufenden Chat und explizite Restorefixture. Markdown/KaTeX/Quellenmarker, Markerprioritäten, stille Modelle, neutrale Dissentzählung und berechnete Farbverträge. Watchdialog, sichere Defaults, Goal/Telegram/Limit, Theme/Preset/Tarifwechsel, explizite Modellpräferenz, Anhangsfilter/Restore und blockierte stale DeepSeekauswahl.

**Grenzen und Doubles:** Firebase-Frontendstub/MOCK_AUTH und externe Modelle kontrolliert; viele Detailfälle rufen Renderer direkt auf oder ersetzen einzelne Antworten. Sechs ausgewählte Provider sind keine vollständige Registryprüfung. Konkrete Viewports statt flächiger visueller Baseline; keine echte Google-/Mailzustellung oder allgemeine vollständige Watch-CRUD-Reise.

**Prüfauftrag für den Folgeaudit:** Die benannten Betriebs- und Testgrenzen bei künftigen Änderungen erneut prüfen; konkrete Paketnachweise stehen im Produktabgleich.

**Direkte Codeverweise:** [app/services/llm/mock_llm.py](../../app/services/llm/mock_llm.py).

<details>
<summary>43 Testdefinitionen und ihre Quellstellen</summary>

- [test_app_loads_without_console_errors](../../tests/e2e/test_smoke.py#L89) (Zeile 89)
- [test_sidebar_header_hover_search_and_provider_picker](../../tests/e2e/test_smoke.py#L113) (Zeile 113)
- [test_question_input_grows_and_caps_on_desktop_and_mobile](../../tests/e2e/test_smoke.py#L176) (Zeile 176)
- [test_restored_context_keeps_the_composer_open_and_continuable](../../tests/e2e/test_smoke.py#L230) (Zeile 230)
- [test_mobile_composer_collapses_after_a_question_and_opens_on_tap](../../tests/e2e/test_smoke.py#L289) (Zeile 289)
- [test_desktop_composer_is_one_row_without_a_collapsed_state](../../tests/e2e/test_smoke.py#L358) (Zeile 358)
- [test_desktop_long_question_takes_the_full_width_and_drops_the_buttons](../../tests/e2e/test_smoke.py#L406) (Zeile 406)
- [test_desktop_composer_does_not_flip_forms_while_editing](../../tests/e2e/test_smoke.py#L447) (Zeile 447)
- [test_desktop_one_row_keeps_the_run_switch_and_attachments_usable](../../tests/e2e/test_smoke.py#L483) (Zeile 483)
- [test_mobile_composer_stays_small_when_scrolling_back_up](../../tests/e2e/test_smoke.py#L532) (Zeile 532)
- [test_typing_into_the_collapsed_composer_keeps_the_cursor_in_the_field](../../tests/e2e/test_smoke.py#L565) (Zeile 565)
- [test_latex_is_typeset_after_markdown_rendering](../../tests/e2e/test_smoke.py#L622) (Zeile 622)
- [test_dollar_math_is_typeset_without_losing_the_result](../../tests/e2e/test_smoke.py#L647) (Zeile 647)
- [test_consensus_citations_follow_terminal_punctuation](../../tests/e2e/test_smoke.py#L680) (Zeile 680)
- [test_usage_display_is_stable_and_updates_visible_quota_panel](../../tests/e2e/test_smoke.py#L704) (Zeile 704)
- [test_empty_app_and_consensus_picker_do_not_scroll_unnecessarily](../../tests/e2e/test_smoke.py#L726) (Zeile 726)
- [test_send_question_streams_all_models](../../tests/e2e/test_smoke.py#L789) (Zeile 789)
- [test_disabled_agent_mode_stays_in_direct_six_answer_comparison](../../tests/e2e/test_smoke.py#L809) (Zeile 809)
- [test_consensus_renders_differences_and_agreement_score](../../tests/e2e/test_smoke.py#L852) (Zeile 852)
- [test_followup_keeps_the_previous_answer_and_appends_the_new_question](../../tests/e2e/test_smoke.py#L1181) (Zeile 1181)
- [test_split_claim_uses_visible_dissent_palette_and_neutral_count](../../tests/e2e/test_smoke.py#L1306) (Zeile 1306)
- [test_claim_hover_keeps_silent_models_available_on_demand](../../tests/e2e/test_smoke.py#L1357) (Zeile 1357)
- [test_repeated_sentence_claim_marks_the_requested_occurrence](../../tests/e2e/test_smoke.py#L1392) (Zeile 1392)
- [test_claim_anchor_with_markdown_syntax_marks_the_rendered_sentence](../../tests/e2e/test_smoke.py#L1417) (Zeile 1417)
- [test_key_claim_fallback_renders_source_tags_as_citations](../../tests/e2e/test_smoke.py#L1479) (Zeile 1479)
- [test_two_claims_in_one_paragraph_mark_their_own_sentence](../../tests/e2e/test_smoke.py#L1516) (Zeile 1516)
- [test_contradiction_keeps_the_visible_control_on_a_shared_sentence](../../tests/e2e/test_smoke.py#L1546) (Zeile 1546)
- [test_emphasis_marker_still_yields_to_the_claim_badge](../../tests/e2e/test_smoke.py#L1608) (Zeile 1608)
- [test_claim_anchor_with_source_tag_still_marks_its_sentence](../../tests/e2e/test_smoke.py#L1652) (Zeile 1652)
- [test_agent_mode_can_reveal_hidden_model_answers_on_mobile](../../tests/e2e/test_smoke.py#L1679) (Zeile 1679)
- [test_watch_dialog_uses_safe_defaults_keeps_telegram_visible_and_asks_for_a_goal](../../tests/e2e/test_smoke.py#L1714) (Zeile 1714)
- [test_query_first_watch_guides_question_then_configuration](../../tests/e2e/test_smoke.py#L1820) (Zeile 1820)
- [test_watch_limit_is_explained_before_creation](../../tests/e2e/test_smoke.py#L1903) (Zeile 1903)
- [test_exclude_model_toggles_excluded_class](../../tests/e2e/test_smoke.py#L1938) (Zeile 1938)
- [test_theme_toggle](../../tests/e2e/test_smoke.py#L1956) (Zeile 1956)
- [test_deep_think_temporarily_selects_configured_engine](../../tests/e2e/test_smoke.py#L1995) (Zeile 1995)
- [test_consensus_presets_apply_full_model_sets_and_gate_thorough](../../tests/e2e/test_smoke.py#L2028) (Zeile 2028)
- [test_attachment_pauses_deepseek_and_restores_previous_selection](../../tests/e2e/test_smoke.py#L2099) (Zeile 2099)
- [test_attachment_block_survives_the_whole_run](../../tests/e2e/test_smoke.py#L2208) (Zeile 2208)
- [test_pdf_drop_uses_full_attachment_whitelist](../../tests/e2e/test_smoke.py#L2288) (Zeile 2288)
- [test_attachment_send_hard_blocks_stale_deepseek_selection](../../tests/e2e/test_smoke.py#L2342) (Zeile 2342)
- [test_tier_upgrade_applies_pro_defaults_but_keeps_explicit_picker_choice](../../tests/e2e/test_smoke.py#L2393) (Zeile 2393)
- [test_model_selection_persists_across_reload](../../tests/e2e/test_smoke.py#L2436) (Zeile 2436)

</details>

<a id="test-source-check-transactions-py"></a>

## test_source_check_transactions.py

**Quelle:** [tests/e2e/test_source_check_transactions.py](../../tests/e2e/test_source_check_transactions.py) · **Bereiche:** Quellen.

**Ebene:** Echte Firestore-SDK-Transaktionen gegen isolierten Demo-Emulator.

**Lauf:** 3 bestanden.

**Geprüftes Verhalten:** Getrennte Repositories claimen/reclaimen denselben Job; nur aktuelle Lease committet ein Paket genau einmal. Delete verhindert Wiederanlage, alle Seiten und Revisionsbindung stimmen, keine Providerkeys werden gespeichert. Ausschließlich ABORTED nach SDK-Retrylimit wird als fehlgeschlagener Aufruf erfasst und separat wiederholt. Vollständiger Own-Key-Workerpfad: fremder Worker claimt nicht, nur gebundener Worker übergibt zufälligen Dummykey an den Judge, Replay ruft kein Modell erneut. Entpackte Jobs/Pakete/Cache, Workerdokumente und Logs bleiben keyfrei; Keyregister wird nach Abschluss geleert.

**Grenzen und Doubles:** Lokaler Emulator mit anonymen Credentials; kein Produktkonto, keine produktive IAM-/Lastgarantie. Nur eigene Dokumentwurzeln werden aufgeräumt. Fetch und Judge sind äußere Doubles; ein Fallback auf Entwicklercredentials führt unmittelbar zum Testfehler.

**Prüfauftrag für den Folgeaudit:** Die benannten Betriebs- und Testgrenzen bei künftigen Änderungen erneut prüfen; konkrete Paketnachweise stehen im Produktabgleich.

**Direkte Codeverweise:** [app/services/source_check_jobs.py](../../app/services/source_check_jobs.py), [app/services/source_check_repository.py](../../app/services/source_check_repository.py), [app/services/source_documents.py](../../app/services/source_documents.py), [app/services/source_verification.py](../../app/services/source_verification.py).

<details>
<summary>3 Testdefinitionen und ihre Quellstellen</summary>

- [test_native_source_claim_takeover_and_exactly_once_package](../../tests/e2e/test_source_check_transactions.py#L15) (Zeile 15)
- [test_native_source_pagination_pins_revision_and_never_persists_credentials](../../tests/e2e/test_source_check_transactions.py#L51) (Zeile 51)
- [test_native_own_key_affinity_uses_only_the_bound_workers_memory](../../tests/e2e/test_source_check_transactions.py#L78) (Zeile 78)

</details>

<a id="test-topic-frontend-py"></a>

## test_topic_frontend.py

**Quelle:** [tests/e2e/test_topic_frontend.py](../../tests/e2e/test_topic_frontend.py) · **Bereiche:** Topics, Frontend.

**Ebene:** Chromium mit Originalskript und kontrollierter SSR-Minimalfixture.

**Lauf:** 5 bestanden.

**Geprüftes Verhalten:** Focus/Enter und Touchpreview mit anschließender Navigation, inerte HTML-Notizen, neue Checks, historischer Besuch und gesperrter Storage. Erster Touch navigiert nicht, historische Ansicht schreibt keinen Seenmarker.

**Grenzen und Doubles:** SSR/Netzwerk kontrolliert; kein echter Topicrouter oder vollständiges Produktionslayout in dieser Fixture.

**Prüfauftrag für den Folgeaudit:** Die benannten Betriebs- und Testgrenzen bei künftigen Änderungen erneut prüfen; konkrete Paketnachweise stehen im Produktabgleich.

**Direkte Codeverweise:** [static/js/topic-page.js](../../static/js/topic-page.js).

<details>
<summary>2 Testdefinitionen und ihre Quellstellen</summary>

- [test_topic_markup_stays_text_and_preview_preserves_navigation](../../tests/e2e/test_topic_frontend.py#L33) (Zeile 33)
- [test_topic_returning_reader_respects_historical_and_blocked_storage](../../tests/e2e/test_topic_frontend.py#L57) (Zeile 57)

</details>

<a id="test-usage-transactions-py"></a>

## test_usage_transactions.py

**Quelle:** [tests/e2e/test_usage_transactions.py](../../tests/e2e/test_usage_transactions.py) · **Bereiche:** Konten und Tarife, Agent.

**Ebene:** Echte Firestore-SDK-Transaktionen gegen isolierten Demo-Emulator.

**Lauf:** 4 bestanden.

**Geprüftes Verhalten:** Gleicher Admissionkey, letzter freier Betrag, Release/Consume und Buchungsdeduplizierung; gemessene plus geschätzte Tokens, alter/neuer UTC-Tag und unveränderter Kontrollowner. Lokaler Accountlock wird entfernt, um getrennte Prozesse nachzubilden. Getrennte gleichzeitige Buchungen bewahren beide Receipts und deren gemeinsame Summe. Mutationen echter Reads/Writes außerhalb der Transaktion müssen doppelte Admission oder verlorene Buchung aufdecken.

**Grenzen und Doubles:** Lokaler Emulator mit anonymen Credentials; kein Produktkonto, keine produktive IAM-/Lastgarantie. Nur eigene Dokumentwurzeln werden aufgeräumt.

**Prüfauftrag für den Folgeaudit:** Die benannten Betriebs- und Testgrenzen bei künftigen Änderungen erneut prüfen; konkrete Paketnachweise stehen im Produktabgleich.

**Direkte Codeverweise:** [app/services/agent_budget_config.py](../../app/services/agent_budget_config.py), [app/services/agent_quota.py](../../app/services/agent_quota.py), [app/services/usage_repository.py](../../app/services/usage_repository.py).

<details>
<summary>4 Testdefinitionen und ihre Quellstellen</summary>

- [test_native_identical_key_and_booking_are_exactly_once](../../tests/e2e/test_usage_transactions.py#L26) (Zeile 26)
- [test_native_last_allowance_release_and_utc_period](../../tests/e2e/test_usage_transactions.py#L43) (Zeile 43)
- [test_native_distinct_bookings_preserve_both_charges](../../tests/e2e/test_usage_transactions.py#L66) (Zeile 66)
- [test_native_release_consume_have_one_terminal_winner](../../tests/e2e/test_usage_transactions.py#L83) (Zeile 83)

</details>

<a id="test-watch-delivery-transactions-py"></a>

## test_watch_delivery_transactions.py

**Quelle:** [tests/e2e/test_watch_delivery_transactions.py](../../tests/e2e/test_watch_delivery_transactions.py) · **Bereiche:** Watches.

**Ebene:** Echte Firestore-SDK-Transaktionen gegen isolierten Demo-Emulator.

**Lauf:** 4 bestanden.

**Geprüftes Verhalten:** Resultat, History und Outbox committen gemeinsam; Abbruch vorher hinterlässt keine Teilwrites, neuer Worker liest nach Commit dieselbe Absicht. Leaseübernahme sperrt stale Ack, Completion-Replay bleibt einmalig. Probe-Tagesbudget, Konfigdrift, einmaliger Claimtoken und Kontotombstone verhindern späte Writes.

**Grenzen und Doubles:** Lokaler Emulator mit anonymen Credentials; kein Produktkonto, keine produktive IAM-/Lastgarantie. Nur eigene Dokumentwurzeln werden aufgeräumt. E-Mail/Telegram bleiben at-least-once; keine externe Zustellgarantie.

**Prüfauftrag für den Folgeaudit:** Die benannten Betriebs- und Testgrenzen bei künftigen Änderungen erneut prüfen; konkrete Paketnachweise stehen im Produktabgleich.

**Direkte Codeverweise:** [app/services/notification_outbox.py](../../app/services/notification_outbox.py), [app/services/persistence_guard.py](../../app/services/persistence_guard.py), [app/services/watch_probe.py](../../app/services/watch_probe.py), [app/services/watch_service.py](../../app/services/watch_service.py).

<details>
<summary>4 Testdefinitionen und ihre Quellstellen</summary>

- [test_native_outbox_claim_takeover_rejects_stale_ack_and_terminal_replay](../../tests/e2e/test_watch_delivery_transactions.py#L8) (Zeile 8)
- [test_native_probe_budget_is_atomic_and_old_configuration_cannot_schedule](../../tests/e2e/test_watch_delivery_transactions.py#L28) (Zeile 28)
- [test_native_watch_result_and_outbox_commit_atomically_and_survive_worker_loss](../../tests/e2e/test_watch_delivery_transactions.py#L57) (Zeile 57)
- [test_native_owner_tombstone_fences_watch_and_probe_late_results](../../tests/e2e/test_watch_delivery_transactions.py#L86) (Zeile 86)

</details>

# Separat gestartete E2E-Suite: Abdeckung pro Testdatei

Stand: **2026-09-26**, Quellstand `145db25bfe029ff7f50cd77595bd6b9e043c1a2f`. [Methodik und Gesamtbefund](../test-coverage-map.md).

**26 Dateien · 144 statische Testdefinitionen · 279 Runner-Fälle.**

„Geprüftes Verhalten“ beschreibt die vorhandenen Assertions. Der Laufstatus steht separat: bei Fehlern ist der beschriebene Vertrag nicht als bestanden belegt. Prüfaufträge sind offene Fragen für den Folgeaudit, keine pauschal festgestellten Lücken der gesamten Suite.

Die Codeverweise sind direkte Imports oder wörtliche Pfade, keine gemessene Ausführungsabdeckung. Indirekte Abhängigkeiten über Fixtures/Helpers und dynamisch zusammengesetzte Pfade können fehlen. Das [JSON-Inventar](inventory.json) enthält jede Definition mit Zeilen, Assertion-Fundstellen und jeden expandierten Runner-Fall.

| Datei | Definitionen | Runner-Fälle | Primärlauf |
|---|---:|---:|---|
| [test_admin_agent_budget.py](#test-admin-agent-budget-py) | 1 | 3 | 3 nicht ausgeführt |
| [test_admin_prompt_config.py](#test-admin-prompt-config-py) | 1 | 3 | 3 nicht ausgeführt |
| [test_agent_chat_frontend.py](#test-agent-chat-frontend-py) | 12 | 31 | 31 nicht ausgeführt |
| [test_agent_comparison_frontend.py](#test-agent-comparison-frontend-py) | 5 | 11 | 11 nicht ausgeführt |
| [test_agent_delegation_frontend.py](#test-agent-delegation-frontend-py) | 2 | 8 | 8 nicht ausgeführt |
| [test_agent_status_frontend.py](#test-agent-status-frontend-py) | 1 | 6 | 6 nicht ausgeführt |
| [test_agent_transactions.py](#test-agent-transactions-py) | 7 | 7 | 7 bestanden |
| [test_agreement_verdict.py](#test-agreement-verdict-py) | 1 | 1 | 1 nicht ausgeführt |
| [test_bookmark_lifecycle_frontend.py](#test-bookmark-lifecycle-frontend-py) | 2 | 6 | 6 nicht ausgeführt |
| [test_browser_failure_recovery.py](#test-browser-failure-recovery-py) | 3 | 3 | 3 nicht ausgeführt |
| [test_chat_scroll_frontend.py](#test-chat-scroll-frontend-py) | 3 | 11 | 11 nicht ausgeführt |
| [test_composer_mode_bar.py](#test-composer-mode-bar-py) | 2 | 7 | 7 nicht ausgeführt |
| [test_consensus_live_progress.py](#test-consensus-live-progress-py) | 4 | 12 | 12 nicht ausgeführt |
| [test_contradiction_source_ui.py](#test-contradiction-source-ui-py) | 3 | 7 | 7 nicht ausgeführt |
| [test_direct_comparison_preview.py](#test-direct-comparison-preview-py) | 2 | 8 | 8 nicht ausgeführt |
| [test_inspector_polish.py](#test-inspector-polish-py) | 1 | 2 | 2 nicht ausgeführt |
| [test_mobile_navigation.py](#test-mobile-navigation-py) | 5 | 12 | 12 nicht ausgeführt |
| [test_model_answer_reader.py](#test-model-answer-reader-py) | 12 | 51 | 51 nicht ausgeführt |
| [test_phase2_transactions.py](#test-phase2-transactions-py) | 4 | 4 | 3 fehlgeschlagen, 1 bestanden |
| [test_phase4_frontend.py](#test-phase4-frontend-py) | 22 | 27 | 27 nicht ausgeführt |
| [test_prompt_config_transactions.py](#test-prompt-config-transactions-py) | 1 | 1 | 1 bestanden |
| [test_public_composer_mockups.py](#test-public-composer-mockups-py) | 1 | 5 | 5 nicht ausgeführt |
| [test_reader_density.py](#test-reader-density-py) | 1 | 2 | 2 nicht ausgeführt |
| [test_reader_review_regressions.py](#test-reader-review-regressions-py) | 2 | 5 | 5 nicht ausgeführt |
| [test_run_cancel_and_progress.py](#test-run-cancel-and-progress-py) | 3 | 3 | 3 nicht ausgeführt |
| [test_smoke.py](#test-smoke-py) | 43 | 43 | 43 nicht ausgeführt |

<a id="test-admin-agent-budget-py"></a>

## test_admin_agent_budget.py

**Quelle:** [tests/e2e/test_admin_agent_budget.py](../../tests/e2e/test_admin_agent_budget.py) · **Bereiche:** Admin, Agent, Konten und Tarife.

**Ebene:** Chromium-Browserintegration mit simulierten Admin-APIs.

**Lauf:** 3 nicht ausgeführt.

**Geprüftes Verhalten:** Bei 1280/390/320 px Budgetfeld laden, unabhängig von allgemeiner Savebar speichern, danach global resetten; Authorization und erwartete Revision/Methoden/Payloads, erhaltener Limitwert, kein horizontaler Überlauf und keine erfassten JSfehler.

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

**Lauf:** 3 nicht ausgeführt.

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

**Quelle:** [tests/e2e/test_agent_chat_frontend.py](../../tests/e2e/test_agent_chat_frontend.py) · **Bereiche:** Agent, Bookmarks und Verlauf, Composer, Responsive UI, Streaming und Wiederherstellung.

**Ebene:** Chromium-Browserintegration mit echten App-/Firebase-UI-Modulen und simuliertem Auth/HTTP.

**Lauf:** 31 nicht ausgeführt.

**Geprüftes Verhalten:** Providergruppierter Prokatalog inkl. Verfügbarkeit/Reasoning, mobile Menügrenzen und Hit-Targets. Gespeicherte Unterbrechung/Teilantwort, Streamfehler mit Bookmarkübernahme und Reload für Teil-/Vergleichs-/leeren Inhalt. Senden/Followup mit gleichem Chat, Modellwechsel, echte Clipboardaktionen, Historie und Restore; nur Agentroute. Laufendes Reasoning/Warten/Toolstatus, Stop, fehlende Detail-/Usagedaten, langer Modellname; Katalogretry/Recovery mit stabiler Request-ID und recover_only. Unversandter mehrzeiliger Draft/Zitat erhalten; Quote nach Streamfehler, gemeinsamer Picker, bestätigte native Suchquellen und Legacy-Phantomsuche unterdrückt. Mehrere schmale/breite, helle/dunkle Varianten prüfen Overflow, Fokus und Controls.

**Grenzen und Doubles:** Writerfreier phase4_server; App-eigenes Firebase-Modul echt, Firebase-SDK/Auth und Daten-APIs ersetzt. SSE teils als Routebody, teils künstlicher Browserstream. Katalog standardmäßig aus Backendregistry, optional externe Fixture. Keine echte Persistenz, Modellgenerierung oder Sicherheitsprüfung des Tokens; optionale Screenshots ohne Bildvergleich.

**Prüfauftrag für den Folgeaudit:** Browser-/API-/Storeverträge für Unterbrechung und Followup zusammenführen, spätere echte Transport-/Persistenzlücken markieren.

**Direkte Codeverweise:** [app/core/config.py](../../app/core/config.py), [app/services/llm/agent_client.py](../../app/services/llm/agent_client.py).

**Direkte Testhelfer:** [tests/e2e/test_phase4_frontend.py](../../tests/e2e/test_phase4_frontend.py).

<details>
<summary>12 Testdefinitionen und ihre Quellstellen</summary>

- [test_all_pro_chat_models_are_grouped_by_provider](../../tests/e2e/test_agent_chat_frontend.py#L52) (Zeile 52)
- [test_saved_interruption_keeps_reason_and_partial_answer_visible](../../tests/e2e/test_agent_chat_frontend.py#L107) (Zeile 107)
- [test_failed_stream_adopts_saved_bookmark_and_survives_reload](../../tests/e2e/test_agent_chat_frontend.py#L145) (Zeile 145)
- [test_single_agent_send_followup_restore_and_layout](../../tests/e2e/test_agent_chat_frontend.py#L226) (Zeile 226)
- [test_live_reasoning_disclosure_and_stop](../../tests/e2e/test_agent_chat_frontend.py#L392) (Zeile 392)
- [test_small_viewport_long_model_and_missing_reasoning](../../tests/e2e/test_agent_chat_frontend.py#L491) (Zeile 491)
- [test_model_catalog_retry_and_failed_stream](../../tests/e2e/test_agent_chat_frontend.py#L536) (Zeile 536)
- [test_model_loading_and_unsent_draft_recovery](../../tests/e2e/test_agent_chat_frontend.py#L594) (Zeile 594)
- [test_quota_stream_and_failure_update_existing_percentage](../../tests/e2e/test_agent_chat_frontend.py#L641) (Zeile 641)
- [test_shared_consensus_picker_still_navigates_submenus](../../tests/e2e/test_agent_chat_frontend.py#L681) (Zeile 681)
- [test_native_search_sources_in_chat_and_saved_activity](../../tests/e2e/test_agent_chat_frontend.py#L707) (Zeile 707)
- [test_removed_preference_and_legacy_phantom_search](../../tests/e2e/test_agent_chat_frontend.py#L771) (Zeile 771)

</details>

<a id="test-agent-comparison-frontend-py"></a>

## test_agent_comparison_frontend.py

**Quelle:** [tests/e2e/test_agent_comparison_frontend.py](../../tests/e2e/test_agent_comparison_frontend.py) · **Bereiche:** Agent, Konsens und Unterschiede, Quellenprüfung, Responsive UI.

**Ebene:** Chromium-Browserintegration mit simuliertem HTTP und gespeicherten Turns.

**Lauf:** 11 nicht ausgeführt.

**Geprüftes Verhalten:** Ungültige Vergleichsauswahl blockiert ohne Draftverlust/Requests; mobiles Plusmenü, kompakter Composer, Reasoning-/Quellschalter und erreichbare Menüs. Vergleichsreview mit mehreren Familien, eingefrorenen Requestoptionen, Tokenquote, Marker, Quellen, Reader-/Unterschieds-/Belegdetails, Tastaturfokusrückgabe und Restore/Historie. Gespeicherte Paper-URLs nummeriert, Tooltip und Readerkatalog; grüner Passagehover nach Scrollen/Projektion. Geometrie, Touchhöhen und Überlauf in schmalen/breiten und dunklen Varianten.

**Grenzen und Doubles:** Künstliche Agent-/Bookmark-/Reviewdaten; echte Frontendmodule und Browserparser, Auth/Backend durch Routes. Geprüfte Belege werden vorgegeben, keine tatsächliche Vergleichs-/Quellenbewertung; optionale Screenshots keine Regressionbaseline.

**Prüfauftrag für den Folgeaudit:** Reviewbasis, Antwortversion und persistierte Belege mit Backendvalidierung abgleichen.

**Direkte Codeverweise:** [app/services/chat_store.py](../../app/services/chat_store.py).

**Direkte Testhelfer:** [tests/e2e/test_agent_chat_frontend.py](../../tests/e2e/test_agent_chat_frontend.py), [tests/e2e/test_phase4_frontend.py](../../tests/e2e/test_phase4_frontend.py).

<details>
<summary>5 Testdefinitionen und ihre Quellstellen</summary>

- [test_comparison_selection_blocks_send_before_losing_draft](../../tests/e2e/test_agent_comparison_frontend.py#L12) (Zeile 12)
- [test_mobile_agent_plus_menu_opens_tools_from_single_line_composer](../../tests/e2e/test_agent_comparison_frontend.py#L64) (Zeile 64)
- [test_comparison_review_and_saved_projection](../../tests/e2e/test_agent_comparison_frontend.py#L164) (Zeile 164)
- [test_saved_agent_paper_urls_are_numbered_citations](../../tests/e2e/test_agent_comparison_frontend.py#L402) (Zeile 402)
- [test_green_agent_passages_hover_after_scrolling_and_reprojection](../../tests/e2e/test_agent_comparison_frontend.py#L445) (Zeile 445)

</details>

<a id="test-agent-delegation-frontend-py"></a>

## test_agent_delegation_frontend.py

**Quelle:** [tests/e2e/test_agent_delegation_frontend.py](../../tests/e2e/test_agent_delegation_frontend.py) · **Bereiche:** Agent, Responsive UI, Streaming und Wiederherstellung.

**Ebene:** Chromium-Browserintegration mit künstlichem SSE-Stream und APIantworten.

**Lauf:** 8 nicht ausgeführt.

**Geprüftes Verhalten:** Livecounter wechselt Tokens pending→Zeichen→Tokens, Dauer aus Serverwert, Animationen enden bei Abschluss/Reduced Motion; echte SSEparser-Laufkette über offenem Browser-ReadableStream. Sidebar mit vielen Delegationen, stabilem Header/Usage beim Scrollen, eigenem Scrollbereich, Detail-Skeleton/Laden/Cache und Judgeinfos; gespeicherte Ansicht, Escape/Fokus und mobile Grenzen in hell/dunkel.

**Grenzen und Doubles:** App-eigene UI echt, Fetch für /agent durch lokalen ReadableStream ersetzt, Poll-/Detail-/Bookmarkantworten und Auth simuliert. Kein Netzwerkstream, Delegationsworker oder Datenbank.

**Prüfauftrag für den Folgeaudit:** Delegationsereignisse/Sequenzen, Pollfallback und Persistenz mit Backendtests verbinden.

**Direkte Testhelfer:** [tests/e2e/test_agent_chat_frontend.py](../../tests/e2e/test_agent_chat_frontend.py), [tests/e2e/test_phase4_frontend.py](../../tests/e2e/test_phase4_frontend.py).

<details>
<summary>2 Testdefinitionen und ihre Quellstellen</summary>

- [test_agent_live_counter_uses_streamed_progress_and_stops_animation](../../tests/e2e/test_agent_delegation_frontend.py#L14) (Zeile 14)
- [test_agent_sidebar_real_app_and_saved_view](../../tests/e2e/test_agent_delegation_frontend.py#L104) (Zeile 104)

</details>

<a id="test-agent-status-frontend-py"></a>

## test_agent_status_frontend.py

**Quelle:** [tests/e2e/test_agent_status_frontend.py](../../tests/e2e/test_agent_status_frontend.py) · **Bereiche:** Agent, Antwortdarstellung, Barrierefreiheit.

**Ebene:** Chromium-Browserintegration mit kontrolliertem SSE-Stream.

**Lauf:** 6 nicht ausgeführt.

**Geprüftes Verhalten:** Fortschrittsabsätze/Toolereignisse in richtiger Reihenfolge, Details mit Modell/Reasoning, Antwort erst bei Delta; Abschluss klappt Vorschau ein, räumt Timer auf, friert Serverdauer ein; Tastatur öffnet Historie erneut. Layoutabstände, Farben und Motionevents in 1280/390/320 px, dunkel/hell, Reduced Motion und Forced Colors.

**Grenzen und Doubles:** Stream aus überschriebenem Fetch, Events manuell eingespeist; Element.animate instrumentiert, echte Animation weiter aufgerufen. Keine reale Modellaktivität oder Assistenztechnik.

**Prüfauftrag für den Folgeaudit:** Progressdaten aus Backend und sparsamer Persistenz gegen UIverträge abgleichen.

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

**Geprüftes Verhalten:** Stop gegen erste Zulassung ohne normalen Prozesslock; wartender zweiter Agent nutzt freiwerdendes Tokenbudget. Parallele Legacyhold-Reparatur und Orphanreceipt-/Savedusage-Recovery nur einmal; tägliche Reservierung und idempotentes Settlement. Delegationsjournal/Sequenzen, Budget/Receipts und Detailnachrichten atomar; parallele Worker teilen Kapazität, erneutes Claim/Settlement/Finish nur einmal, unbekannte und gemessene Kosten getrennt, Leasefreigabe sowie Chat-/Agentsubcollections-Löschung.

**Grenzen und Doubles:** Echter lokaler Emulator, mehrere Storeinstanzen/Threads und Barrieren; Completion künstlich, stellenweise Policy/Limits oder Prozesslock gezielt ersetzt. Kein produktiver Firestorecluster, Mehrprozessdeployment oder echter Provider.

**Prüfauftrag für den Folgeaudit:** Produktionsretry-/Latenz-/Mehrprozessverhalten und übrige Transaktionsgrenzen gegen diese Szenarien abgleichen.

**Direkte Codeverweise:** [app/core/e2e_profile.py](../../app/core/e2e_profile.py), [app/services/account_deletion.py](../../app/services/account_deletion.py), [app/services/agent_costs.py](../../app/services/agent_costs.py), [app/services/agent_delegation.py](../../app/services/agent_delegation.py), [app/services/agent_delegation_config.py](../../app/services/agent_delegation_config.py), [app/services/agent_policy.py](../../app/services/agent_policy.py), [app/services/agent_quota.py](../../app/services/agent_quota.py), [app/services/agent_runs.py](../../app/services/agent_runs.py), [app/services/agent_runtime.py](../../app/services/agent_runtime.py), [app/services/agent_tools.py](../../app/services/agent_tools.py), [app/services/chat_store.py](../../app/services/chat_store.py), [app/services/llm/agent_client.py](../../app/services/llm/agent_client.py), [app/services/llm/provider_runtime.py](../../app/services/llm/provider_runtime.py).

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

<a id="test-agreement-verdict-py"></a>

## test_agreement_verdict.py

**Quelle:** [tests/e2e/test_agreement_verdict.py](../../tests/e2e/test_agreement_verdict.py) · **Bereiche:** Antwortdarstellung, Konsens und Unterschiede.

**Ebene:** Chromium-UItest auf lokaler Appseite.

**Lauf:** 1 nicht ausgeführt.

**Geprüftes Verhalten:** Niedriger Score ohne Widerspruchskarten wird als Low agreement mit Alarmklasse/rotem Ring und Hinweis auf fehlende Widersprüche dargestellt.

**Grenzen und Doubles:** Analysedaten per page.evaluate direkt gerendert; app_page nutzt Mock-Auth/-LLM und Emulator. Keine Berechnung der Übereinstimmung geprüft.

**Prüfauftrag für den Folgeaudit:** Backendscore und Evidenzabdeckung gemeinsam gegen Darstellungsfälle prüfen.

<details>
<summary>1 Testdefinitionen und ihre Quellstellen</summary>

- [test_low_score_without_contradictions_is_not_green_or_high](../../tests/e2e/test_agreement_verdict.py#L4) (Zeile 4)

</details>

<a id="test-bookmark-lifecycle-frontend-py"></a>

## test_bookmark_lifecycle_frontend.py

**Quelle:** [tests/e2e/test_bookmark_lifecycle_frontend.py](../../tests/e2e/test_bookmark_lifecycle_frontend.py) · **Bereiche:** Bookmarks und Verlauf, Scrollen und Navigation.

**Ebene:** Chromium-Browserintegration mit verzögerten HTTP-Doubles.

**Lauf:** 6 nicht ausgeführt.

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

**Lauf:** 3 nicht ausgeführt.

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

<a id="test-chat-scroll-frontend-py"></a>

## test_chat_scroll_frontend.py

**Quelle:** [tests/e2e/test_chat_scroll_frontend.py](../../tests/e2e/test_chat_scroll_frontend.py) · **Bereiche:** Agent, Konsens und Unterschiede, Scrollen und Navigation.

**Ebene:** Chromium-Browserintegration mit kontrollierten Run-/Streamzuständen.

**Lauf:** 11 nicht ausgeführt.

**Geprüftes Verhalten:** Offscreen-Agentaktivität kollabiert bei Review/Abschluss ohne sichtbare Antwort zu verschieben; Konsensstream bleibt am Leseort, Latest springt einmal. Agent folgt neuen Nachrichten, Nutzerunterbrechung bewahrt Position, Rückkehrcontrol und Fokusrückgabe; enge Scrolltoleranzen, lange Antworten, offene Historie, End-/Mittelposition, Mobile und Reduced Motion.

**Grenzen und Doubles:** Echte Browsergeometrie/Scrollen, aber Antworten/Ereignisse und APIs gezielt vorgegeben; kein realer Provider oder Gerät mit Bildschirmtastatur.

**Prüfauftrag für den Folgeaudit:** Reale Touch-/Keyboard-Viewportwechsel und verzögerte Medienlayouts abgleichen.

**Direkte Testhelfer:** [tests/e2e/test_agent_chat_frontend.py](../../tests/e2e/test_agent_chat_frontend.py), [tests/e2e/test_phase4_frontend.py](../../tests/e2e/test_phase4_frontend.py).

<details>
<summary>3 Testdefinitionen und ihre Quellstellen</summary>

- [test_agent_review_and_completion_keep_visible_answer_still](../../tests/e2e/test_chat_scroll_frontend.py#L13) (Zeile 13)
- [test_consensus_stream_stays_still_and_latest_only_jumps_once](../../tests/e2e/test_chat_scroll_frontend.py#L90) (Zeile 90)
- [test_agent_chat_follows_new_messages_without_stealing_the_readers_position](../../tests/e2e/test_chat_scroll_frontend.py#L151) (Zeile 151)

</details>

<a id="test-composer-mode-bar-py"></a>

## test_composer_mode_bar.py

**Quelle:** [tests/e2e/test_composer_mode_bar.py](../../tests/e2e/test_composer_mode_bar.py) · **Bereiche:** Anhänge, Composer, Konten und Tarife, Responsive UI.

**Ebene:** Chromium-Browserintegration mit vorgegebenem Frontendzustand.

**Lauf:** 7 nicht ausgeführt.

**Geprüftes Verhalten:** Modebar mit sechs Modellicons, Agent-/Directumschaltung und Quellgates; eingefrorener Directlauf bleibt bei nächster Moduswahl sichtbar, New Run bereinigt. Ausrichtung/Höhe und Reveal-/Reduced-Motionanimation. Deep-/Uploadplanhinweise, Modalnavigation/Fokus/Escape und alternierende Hinweise; Plusfunktionen, Dateiupload und wiederverwendete Anhangsleiste beim Moduswechsel.

**Grenzen und Doubles:** Echte App-UI auf writerfreiem Server, Auth/Status simuliert und Runzustände teilweise direkt gesetzt; keine Backendtarifautorisierung oder tatsächliche Modellanfrage.

**Prüfauftrag für den Folgeaudit:** Tarif-/Modus-/Anhangszustände über den Versandvertrag zusammenführen.

**Direkte Testhelfer:** [tests/e2e/test_phase4_frontend.py](../../tests/e2e/test_phase4_frontend.py).

<details>
<summary>2 Testdefinitionen und ihre Quellstellen</summary>

- [test_composer_mode_bar](../../tests/e2e/test_composer_mode_bar.py#L11) (Zeile 11)
- [test_toolbar_deep_think_and_upload_reuse_plan_gates](../../tests/e2e/test_composer_mode_bar.py#L101) (Zeile 101)

</details>

<a id="test-consensus-live-progress-py"></a>

## test_consensus_live_progress.py

**Quelle:** [tests/e2e/test_consensus_live_progress.py](../../tests/e2e/test_consensus_live_progress.py) · **Bereiche:** Antwortdarstellung, Barrierefreiheit, Konsens und Unterschiede.

**Ebene:** Isolierter Chromium-Komponententest mit lokal gerouteten Assets.

**Lauf:** 12 nicht ausgeführt.

**Geprüftes Verhalten:** Modellstatus und Phasenübergang bei 320/390/768/1280 px hell/dunkel, große Zeichenzähler, Reasoning/Waiting/Done und abgeschlossene Phase. Reduced Motion statisch lesbar; nur Phasensummary live; Skip per Tastatur und Touch mit mindestens 44×44-Ziel ohne Layoutsprung oder Overflow.

**Grenzen und Doubles:** Eigenes minimales HTML mit echten CSS-/Progressassets, Modelle/Zeitstatus künstlich; kein kompletter Appbootstrap, Backend oder tatsächliches Modellskip.

**Prüfauftrag für den Folgeaudit:** Full-App-Phasenanbindung, echte Streamdauer und Assistenztechnik zuordnen.

**Direkte Codeverweise:** [static/dist/manifest.json](../../static/dist/manifest.json), [static/js/consensus-progress.js](../../static/js/consensus-progress.js), [templates/index.html](../../templates/index.html).

<details>
<summary>4 Testdefinitionen und ihre Quellstellen</summary>

- [test_model_status_layout_and_phase_handoff](../../tests/e2e/test_consensus_live_progress.py#L85) (Zeile 85)
- [test_reduced_motion_keeps_status_readable_and_static](../../tests/e2e/test_consensus_live_progress.py#L135) (Zeile 135)
- [test_only_phase_summary_is_live_and_skip_is_keyboard_accessible](../../tests/e2e/test_consensus_live_progress.py#L149) (Zeile 149)
- [test_skip_has_a_full_touch_target_without_overflow](../../tests/e2e/test_consensus_live_progress.py#L181) (Zeile 181)

</details>

<a id="test-contradiction-source-ui-py"></a>

## test_contradiction_source_ui.py

**Quelle:** [tests/e2e/test_contradiction_source_ui.py](../../tests/e2e/test_contradiction_source_ui.py) · **Bereiche:** Barrierefreiheit, Konsens und Unterschiede, Quellenprüfung.

**Ebene:** Chromium-UIintegration mit eingespeisten Run-/Quellenzuständen.

**Lauf:** 7 nicht ausgeführt.

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

**Lauf:** 8 nicht ausgeführt.

**Geprüftes Verhalten:** Directvorschau ohne Run, Requests oder Ladezustand; sechs Karten, Draft bleibt bei Umschaltung; Raster/Composer bei Desktop, Tablet, schmaler und Querformatansicht hell/dunkel im Viewport. Reduced Motion, injizierter fertiger Lauf ersetzt Vorschau und bleibt bei Moduswechsel; gespeicherter Offzustand, Modellabwahl und New Comparison erhalten Auswahl.

**Grenzen und Doubles:** Vorschauinteraktion echt; vermeintlich realer Ergebnislauf über seed_reader künstlich erzeugt, kein Backendmodellaufruf.

**Prüfauftrag für den Folgeaudit:** Übergang von Vorschau zu tatsächlichem Senden und Fehlern gemeinsam mit anderen Browserfällen zuordnen.

**Direkte Testhelfer:** [tests/e2e/test_model_answer_reader.py](../../tests/e2e/test_model_answer_reader.py), [tests/e2e/test_phase4_frontend.py](../../tests/e2e/test_phase4_frontend.py).

<details>
<summary>2 Testdefinitionen und ihre Quellstellen</summary>

- [test_preview_toggle_layout_and_real_result](../../tests/e2e/test_direct_comparison_preview.py#L21) (Zeile 21)
- [test_persisted_off_new_comparison_and_model_selection](../../tests/e2e/test_direct_comparison_preview.py#L86) (Zeile 86)

</details>

<a id="test-inspector-polish-py"></a>

## test_inspector_polish.py

**Quelle:** [tests/e2e/test_inspector_polish.py](../../tests/e2e/test_inspector_polish.py) · **Bereiche:** Antwortdarstellung, Barrierefreiheit, Quellenprüfung, Responsive UI.

**Ebene:** Chromium-UIintegration mit vorbereiteten Insights.

**Lauf:** 2 nicht ausgeführt.

**Geprüftes Verhalten:** Kompakte Unterschiedskarten und Quellenzeilen, je Disclosure nur ein Chevron; vollständige Claimtexte, Diagnosedetails und zusätzlicher Quellenlistenschalter. Footerstatussymbole, Provenienz, kurze Mobilbeschriftung, gleich große erreichbare Aktionen ohne Überlauf; Displaysettings über Reader, richtige Ebene/Tab und Rückkehr; hell/dunkel.

**Grenzen und Doubles:** Daten über seed_insights/page.evaluate injiziert; echte CSS-/Geometriemessung, kein API-/Persistenzablauf oder vollständiger visueller Bildvergleich.

**Prüfauftrag für den Folgeaudit:** Inhaltliche Extremfälle und Assistenztechnik mit tatsächlichen langen Antworten abgleichen.

**Direkte Testhelfer:** [tests/e2e/test_model_answer_reader.py](../../tests/e2e/test_model_answer_reader.py), [tests/e2e/test_phase4_frontend.py](../../tests/e2e/test_phase4_frontend.py).

<details>
<summary>1 Testdefinitionen und ihre Quellstellen</summary>

- [test_inspector_density_disclosures_and_footer](../../tests/e2e/test_inspector_polish.py#L10) (Zeile 10)

</details>

<a id="test-mobile-navigation-py"></a>

## test_mobile_navigation.py

**Quelle:** [tests/e2e/test_mobile_navigation.py](../../tests/e2e/test_mobile_navigation.py) · **Bereiche:** Authentifizierung, Barrierefreiheit, Responsive UI, Watch.

**Ebene:** Chromium-Browserintegration mit simuliertem Auth und vorbereiteten Antworten.

**Lauf:** 12 nicht ausgeführt.

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

**Lauf:** 51 nicht ausgeführt.

**Geprüftes Verhalten:** Breiter Reader und Chat zentriert mit/ohne Sidebar; Quellenkarten/Faviconfallback. Resize/kurze Viewports, Modal-/Dockedwechsel, gemeinsames Inhaltsraster und große Scrollfläche; Unterschiede/Quellen/Antworten turngebunden, historische Ansicht bleibt bei Projektion. Directantworten inline inkl. Modellfehler, sechs Karten und gespeicherte Directantwort trotz aktueller Agentpräferenz. Eigene Picker, verschiedene Vergleichsmodelle, mobile Seitenwahl, Escape/Fokusrückgabe, lange Frage. Demo verwendet sechs Balancedmodelle, richtige Labels, Skeleton bis Abschluss und echtes Markdown statt Spinnermarkup. Viele Breiten bis 2560 px und hell/dunkel.

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
- [test_demo_uses_all_balanced_models_and_never_displays_spinner_markup](../../tests/e2e/test_model_answer_reader.py#L551) (Zeile 551)

</details>

<a id="test-phase2-transactions-py"></a>

## test_phase2_transactions.py

**Quelle:** [tests/e2e/test_phase2_transactions.py](../../tests/e2e/test_phase2_transactions.py) · **Bereiche:** Bookmarks und Verlauf, Nebenläufigkeit, Persistenz, Watch, Öffentliche Freigaben.

**Ebene:** Firestore-Emulatorintegration mit echten SDK-Transaktionen und Threads.

**Lauf:** 3 fehlgeschlagen, 1 bestanden.

- `test_two_workers_cannot_exceed_owner_watch_limit`: TypeError: create_watch() got an unexpected keyword argument 'is_pro'

- `test_two_workers_publish_one_pending_share_and_consume_one_quota`: app.services.share_snapshots.ShareError: Result not found or expired.

- `test_parallel_reports_never_lose_increments_or_noindex_transition`: ValueError: Failed to commit transaction in 12 attempts. Im isolierten Wiederholungslauf bestanden; Ursache der Abweichung noch offen.

**Geprüftes Verhalten:** Zwei Worker überschreiten weder Watch- noch Chatlimit; paralleles Publizieren derselben Anfrage erzeugt eine Pendingfreigabe und verbraucht eine Quote. Acht parallele Meldungen behalten alle Inkremente/Spamzähler und setzen Review/noindex.

**Grenzen und Doubles:** Limitwerte auf eins reduziert, unabhängige Threads statt getrennter Serverprozesse; isolierte Testdokumente und echte Emulatortransaktionen, keine UI oder produktive Firestoreinfrastruktur.

**Prüfauftrag für den Folgeaudit:** Weitere konkurrierende Create/Delete-/Retrykombinationen anhand der Produktionsinvarianten prüfen.

**Direkte Codeverweise:** [app/core/e2e_profile.py](../../app/core/e2e_profile.py), [app/services/chat_store.py](../../app/services/chat_store.py), [app/services/share_snapshots.py](../../app/services/share_snapshots.py), [app/services/watch_service.py](../../app/services/watch_service.py).

<details>
<summary>4 Testdefinitionen und ihre Quellstellen</summary>

- [test_two_workers_cannot_exceed_owner_watch_limit](../../tests/e2e/test_phase2_transactions.py#L24) (Zeile 24)
- [test_two_workers_publish_one_pending_share_and_consume_one_quota](../../tests/e2e/test_phase2_transactions.py#L92) (Zeile 92)
- [test_two_workers_cannot_exceed_owner_chat_limit](../../tests/e2e/test_phase2_transactions.py#L134) (Zeile 134)
- [test_parallel_reports_never_lose_increments_or_noindex_transition](../../tests/e2e/test_phase2_transactions.py#L161) (Zeile 161)

</details>

<a id="test-phase4-frontend-py"></a>

## test_phase4_frontend.py

**Quelle:** [tests/e2e/test_phase4_frontend.py](../../tests/e2e/test_phase4_frontend.py) · **Bereiche:** Authentifizierung, Bookmarks und Verlauf, Frontend-Zustand, Nebenläufigkeit, Quellenprüfung, Watch.

**Ebene:** Chromium-Browserintegration mit echten App-/Firebase-UI-Modulen und simuliertem SDK/HTTP.

**Lauf:** 27 nicht ausgeführt.

**Geprüftes Verhalten:** Quellenstatus/Animation/Reduced Motion, sichere Markdownclaims/Tabellen, partielle Prüfung und Restore ohne DOMverlust; Quellschalter persistiert, Payload pro Lauf eingefroren. Followup erhält Historie/Spinner; spätere Quellenjobupdates erhalten abgeschlossene Claims/Karten, Fokus, Tooltip und Navigation. Authmodulausfall bietet nutzbaren Login; Watchhinweis überdeckt Composer nicht. Späte Bookmark-/Shareantwort von Konto A erreicht Konto B nicht; letzter Bookmarkklick gewinnt; Watchdeeplink über Login. Alle Modellfehler ohne Konsens. Zwei parallele Läufe mit isolierten Payloads/Controllern, gezieltem Cancel und umgekehrtem Abschluss hinter gespeicherter Ansicht ohne Basis-/Quellenvermischung. Directmodus speichert sechs Antworten ohne Konsens; Anhangsfilter blockiert zu wenige kompatible Modelle vor Prepare. Watchnavigation schließt Modal, verspätete Erstellung/Tokenauflösung respektiert neuere Ansicht; Cancel während Tokenauflösung erhält Followup ohne Usagerun. UTCusage-Refresh retry bis autoritativer Erfolg; Sichtbarkeitsklassen überschreibbar; Legacy-Claimfallback säubert Markdown und rendert Mathematik.

**Grenzen und Doubles:** Writerfreier eigener Server, Firebase-App/Auth/Firestore-SDK durch Module ersetzt; App-eigenes Firebase-Modul bleibt echt. API-/SSEantworten oder Runzustände gezielt simuliert, also keine echte DBpersistenz, Loginprüfung oder Providerarbeit. Nicht alle Szenarien parametrisieren dieselben Breiten.

**Prüfauftrag für den Folgeaudit:** Verträge aus Browserraces mit Backendtransaktionen und echten HTTPstream-/Persistenztests verbinden; versionierte Sourcechecks von Legacyanzeigen trennen.

**Direkte Codeverweise:** [static/firebase.js](../../static/firebase.js).

<details>
<summary>22 Testdefinitionen und ihre Quellstellen</summary>

- [test_source_verification_display_and_restore](../../tests/e2e/test_phase4_frontend.py#L185) (Zeile 185)
- [test_composer_source_check_toggle_persists_and_freezes_run_payload](../../tests/e2e/test_phase4_frontend.py#L315) (Zeile 315)
- [test_followup_stream_preserves_history_and_model_loading_nodes](../../tests/e2e/test_phase4_frontend.py#L370) (Zeile 370)
- [test_source_judge_stream_keeps_completed_claims_and_differences](../../tests/e2e/test_phase4_frontend.py#L411) (Zeile 411)
- [test_auth_module_failure_exposes_usable_login_dialog](../../tests/e2e/test_phase4_frontend.py#L596) (Zeile 596)
- [test_watch_feature_nudge_never_raises_answer_over_fixed_composer](../../tests/e2e/test_phase4_frontend.py#L631) (Zeile 631)
- [test_account_a_late_bookmark_save_cannot_mutate_account_b](../../tests/e2e/test_phase4_frontend.py#L709) (Zeile 709)
- [test_account_a_share_response_cannot_overwrite_account_b_view](../../tests/e2e/test_phase4_frontend.py#L749) (Zeile 749)
- [test_last_bookmark_click_wins_when_detail_responses_arrive_out_of_order](../../tests/e2e/test_phase4_frontend.py#L794) (Zeile 794)
- [test_logged_out_watch_deep_link_survives_and_late_login_renders](../../tests/e2e/test_phase4_frontend.py#L836) (Zeile 836)
- [test_all_model_failures_end_in_error_without_consensus](../../tests/e2e/test_phase4_frontend.py#L862) (Zeile 862)
- [test_two_runs_keep_payloads_views_and_cancel_controllers_isolated](../../tests/e2e/test_phase4_frontend.py#L890) (Zeile 890)
- [test_two_runs_finish_reverse_order_behind_a_saved_bookmark](../../tests/e2e/test_phase4_frontend.py#L1210) (Zeile 1210)
- [test_disabled_agent_mode_is_six_answers_only](../../tests/e2e/test_phase4_frontend.py#L1748) (Zeile 1748)
- [test_attachment_filter_blocks_one_model_run_before_prepare](../../tests/e2e/test_phase4_frontend.py#L1872) (Zeile 1872)
- [test_watched_navigation_closes_the_shared_modal](../../tests/e2e/test_phase4_frontend.py#L1912) (Zeile 1912)
- [test_cancel_during_token_resolution_keeps_followup_and_creates_no_usage_run](../../tests/e2e/test_phase4_frontend.py#L1938) (Zeile 1938)
- [test_late_watch_create_cannot_overwrite_newer_share_modal](../../tests/e2e/test_phase4_frontend.py#L1992) (Zeile 1992)
- [test_watch_create_is_not_sent_after_modal_changes_during_token_wait](../../tests/e2e/test_phase4_frontend.py#L2048) (Zeile 2048)
- [test_failed_utc_usage_refresh_retries_until_authoritative_success](../../tests/e2e/test_phase4_frontend.py#L2096) (Zeile 2096)
- [test_template_visibility_classes_remain_overridable_by_ui_controls](../../tests/e2e/test_phase4_frontend.py#L2151) (Zeile 2151)
- [test_key_claim_fallback_cleans_orphan_markdown_and_renders_math](../../tests/e2e/test_phase4_frontend.py#L2182) (Zeile 2182)

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

**Lauf:** 5 nicht ausgeführt.

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

**Quelle:** [tests/e2e/test_reader_density.py](../../tests/e2e/test_reader_density.py) · **Bereiche:** Antwortdarstellung, Barrierefreiheit, Responsive UI.

**Ebene:** Chromium-UIintegration mit sechs künstlichen Modellantworten.

**Lauf:** 2 nicht ausgeführt.

**Geprüftes Verhalten:** Lesefläche, begrenzte Readerbreite/Headerhöhe und ausreichende Chatbreite; sechs Modellbuttons, 14-px-Antworttext, mindestens 44-px-Bedienziele. Mobile Einzelauswahl und Vergleichsseiten, kein Überlauf, Fokusrückgabe; hell/dunkel.

**Grenzen und Doubles:** Vorgegebene Antworten/DOMzustände und echte CSSmessungen; keine universelle Lesbarkeits-/Kontrastbewertung.

**Prüfauftrag für den Folgeaudit:** Extremtext, Zoom, Sprachen und assistive Nutzung separat bewerten.

**Direkte Testhelfer:** [tests/e2e/test_model_answer_reader.py](../../tests/e2e/test_model_answer_reader.py), [tests/e2e/test_phase4_frontend.py](../../tests/e2e/test_phase4_frontend.py).

<details>
<summary>1 Testdefinitionen und ihre Quellstellen</summary>

- [test_six_answers_leave_room_to_read_and_keep_touch_targets](../../tests/e2e/test_reader_density.py#L10) (Zeile 10)

</details>

<a id="test-reader-review-regressions-py"></a>

## test_reader_review_regressions.py

**Quelle:** [tests/e2e/test_reader_review_regressions.py](../../tests/e2e/test_reader_review_regressions.py) · **Bereiche:** Antwortdarstellung, Bookmarks und Verlauf, Composer, Nutzergedächtnis.

**Ebene:** Chromium-UIintegration mit Fixture-Runs.

**Lauf:** 5 nicht ausgeführt.

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

**Quelle:** [tests/e2e/test_run_cancel_and_progress.py](../../tests/e2e/test_run_cancel_and_progress.py) · **Bereiche:** Konsens und Unterschiede, Streaming und Wiederherstellung.

**Ebene:** Chromium-Integration gegen lokalen Mock-LLM-Server und Firestore-Emulator.

**Lauf:** 3 nicht ausgeführt.

**Geprüftes Verhalten:** Sendbutton bleibt beim Konsensstart abbrechbar und wird erst nach Lifecycleende normal; erneutes sendQuestion bricht laufenden Konsens auf Clientseite ab. Zweiter frischer Vergleich zeigt zwischenzeitlich null fertige Modellzeilen und danach neue Abschlüsse.

**Grenzen und Doubles:** Reale lokale HTTP-/SSEkette mit Mock-LLM, Mock-Auth und Firebase-UIstub; eigener Dummykey umgeht reguläre Quote. Cancelassertions belegen Clientzustand, nicht Ende eines realen Providerprozesses; Zähler prüft Reset/Abschluss, keine exakten Laufzeiten.

**Prüfauftrag für den Folgeaudit:** Clientcancel gegen Backendabbau, Persistenz und Tokenabrechnung abgleichen.

**Direkte Testhelfer:** [tests/e2e/test_smoke.py](../../tests/e2e/test_smoke.py).

<details>
<summary>3 Testdefinitionen und ihre Quellstellen</summary>

- [test_send_button_stays_cancelable_until_consensus_is_done](../../tests/e2e/test_run_cancel_and_progress.py#L45) (Zeile 45)
- [test_send_button_cancels_a_running_consensus](../../tests/e2e/test_run_cancel_and_progress.py#L77) (Zeile 77)
- [test_model_rows_restart_empty_on_a_second_run](../../tests/e2e/test_run_cancel_and_progress.py#L90) (Zeile 90)

</details>

<a id="test-smoke-py"></a>

## test_smoke.py

**Quelle:** [tests/e2e/test_smoke.py](../../tests/e2e/test_smoke.py) · **Bereiche:** Anhänge, Composer, Konsens und Unterschiede, Markdown und Darstellung, Responsive UI, Watch.

**Ebene:** Gemischte Chromium-Integration gegen Mockserver sowie direkte UIzustandsprüfungen.

**Lauf:** 43 nicht ausgeführt.

**Geprüftes Verhalten:** Appbootstrap/window-Verträge und Konsole; Sidebar/Search/Picker, mobile/desktop Composerhöhe, Einzeilen-/Mehrzeilenform ohne Flackern, Fokus/Caret, Scrollverhalten und Anhangsanordnung. Markdown/KaTeX/Währungen und Quelleninterpunktion; stabile Usageanzeige. Sechs ausgewählte Mockmodelle streamen, Directmodus ohne Konsens; Autokonsens mit Score, Claims/Widerspruch, Reader-/Quellnavigation, zugänglichen Popovern, sauberem Copytext und Run-again. Drei Gesprächsschritte erhalten historische Antworten/Score/Marker. Anchorfälle für Markdown, wiederholte Sätze, mehrere Sätze, Quellentags, Fallback, Split-/Widerspruchs-/Emphasispriorität und stille Modelle. Watchdialog mit privaten Defaults, Termin/Telegram/Conditionvalidierung, Query-first-Rücknavigation und Limitanzeige. Modellabwahl/Reload, Theme, Deep-Engine ohne dauerhafte Präferenzänderung, Presets/Prohinweis und Upgrade mit expliziter Auswahl. Anhangsfilter/Restore über Tarifrefresh und Lauf, PDFdrop, stale DeepSeekauswahl vor Versand blockiert.

**Grenzen und Doubles:** app_page nutzt lokalen Server/Emulator mit Mock-LLM/Auth; Firebase-UI wird komplett durch firebase_stub.js ersetzt, Dummy-Eigenkey entkoppelt Quoten. Viele Einzelfälle rufen Renderer direkt auf oder routen Antworten. Harte Liste aus sechs Providern, keine vollständige aktuelle Registry. Einleitender Altkommentar behauptet fehlende Anhänge/Followups, die inzwischen tatsächlich geprüft werden; Inhaltsbeschreibung folgt Assertions. Kein produktiver Login, Provider oder umfassender Share-/Watch-CRUD.

**Prüfauftrag für den Folgeaudit:** Breite Smokeabdeckung in einzelne Produktverträge auflösen, echte Backend-/Persistenzanteile je Fall abgleichen und veraltete Erwartungen gegen aktuelle UI prüfen.

**Direkte Codeverweise:** [app/services/llm/mock_llm.py](../../app/services/llm/mock_llm.py).

<details>
<summary>43 Testdefinitionen und ihre Quellstellen</summary>

- [test_app_loads_without_console_errors](../../tests/e2e/test_smoke.py#L69) (Zeile 69)
- [test_sidebar_header_hover_search_and_provider_picker](../../tests/e2e/test_smoke.py#L89) (Zeile 89)
- [test_question_input_grows_and_caps_on_desktop_and_mobile](../../tests/e2e/test_smoke.py#L152) (Zeile 152)
- [test_restored_context_keeps_the_composer_open_and_continuable](../../tests/e2e/test_smoke.py#L201) (Zeile 201)
- [test_mobile_composer_collapses_after_a_question_and_opens_on_tap](../../tests/e2e/test_smoke.py#L260) (Zeile 260)
- [test_desktop_composer_is_one_row_without_a_collapsed_state](../../tests/e2e/test_smoke.py#L328) (Zeile 328)
- [test_desktop_long_question_takes_the_full_width_and_drops_the_buttons](../../tests/e2e/test_smoke.py#L376) (Zeile 376)
- [test_desktop_composer_does_not_flip_forms_while_editing](../../tests/e2e/test_smoke.py#L417) (Zeile 417)
- [test_desktop_one_row_keeps_the_run_switch_and_attachments_usable](../../tests/e2e/test_smoke.py#L453) (Zeile 453)
- [test_mobile_composer_stays_small_when_scrolling_back_up](../../tests/e2e/test_smoke.py#L502) (Zeile 502)
- [test_typing_into_the_collapsed_composer_keeps_the_cursor_in_the_field](../../tests/e2e/test_smoke.py#L535) (Zeile 535)
- [test_latex_is_typeset_after_markdown_rendering](../../tests/e2e/test_smoke.py#L592) (Zeile 592)
- [test_dollar_math_is_typeset_without_losing_the_result](../../tests/e2e/test_smoke.py#L617) (Zeile 617)
- [test_consensus_citations_follow_terminal_punctuation](../../tests/e2e/test_smoke.py#L650) (Zeile 650)
- [test_usage_display_is_stable_and_updates_visible_quota_panel](../../tests/e2e/test_smoke.py#L674) (Zeile 674)
- [test_empty_app_and_consensus_picker_do_not_scroll_unnecessarily](../../tests/e2e/test_smoke.py#L709) (Zeile 709)
- [test_send_question_streams_all_models](../../tests/e2e/test_smoke.py#L769) (Zeile 769)
- [test_disabled_agent_mode_stays_in_direct_six_answer_comparison](../../tests/e2e/test_smoke.py#L789) (Zeile 789)
- [test_consensus_renders_differences_and_agreement_score](../../tests/e2e/test_smoke.py#L843) (Zeile 843)
- [test_followup_keeps_the_previous_answer_and_appends_the_new_question](../../tests/e2e/test_smoke.py#L1225) (Zeile 1225)
- [test_split_claim_is_marked_in_the_colour_of_its_badge](../../tests/e2e/test_smoke.py#L1341) (Zeile 1341)
- [test_claim_hover_keeps_silent_models_available_on_demand](../../tests/e2e/test_smoke.py#L1384) (Zeile 1384)
- [test_repeated_sentence_claim_marks_the_requested_occurrence](../../tests/e2e/test_smoke.py#L1422) (Zeile 1422)
- [test_claim_anchor_with_markdown_syntax_marks_the_rendered_sentence](../../tests/e2e/test_smoke.py#L1447) (Zeile 1447)
- [test_key_claim_fallback_renders_source_tags_as_citations](../../tests/e2e/test_smoke.py#L1509) (Zeile 1509)
- [test_two_claims_in_one_paragraph_mark_their_own_sentence](../../tests/e2e/test_smoke.py#L1545) (Zeile 1545)
- [test_contradiction_keeps_the_visible_control_on_a_shared_sentence](../../tests/e2e/test_smoke.py#L1575) (Zeile 1575)
- [test_emphasis_marker_still_yields_to_the_claim_badge](../../tests/e2e/test_smoke.py#L1635) (Zeile 1635)
- [test_claim_anchor_with_source_tag_still_marks_its_sentence](../../tests/e2e/test_smoke.py#L1675) (Zeile 1675)
- [test_agent_mode_can_reveal_hidden_model_answers_on_mobile](../../tests/e2e/test_smoke.py#L1702) (Zeile 1702)
- [test_watch_dialog_uses_safe_defaults_keeps_telegram_visible_and_reveals_condition](../../tests/e2e/test_smoke.py#L1733) (Zeile 1733)
- [test_query_first_watch_guides_question_then_configuration](../../tests/e2e/test_smoke.py#L1828) (Zeile 1828)
- [test_watch_limit_is_explained_before_creation](../../tests/e2e/test_smoke.py#L1911) (Zeile 1911)
- [test_exclude_model_toggles_excluded_class](../../tests/e2e/test_smoke.py#L1946) (Zeile 1946)
- [test_theme_toggle](../../tests/e2e/test_smoke.py#L1964) (Zeile 1964)
- [test_deep_think_temporarily_selects_configured_engine](../../tests/e2e/test_smoke.py#L2002) (Zeile 2002)
- [test_consensus_presets_apply_full_model_sets_and_gate_thorough](../../tests/e2e/test_smoke.py#L2035) (Zeile 2035)
- [test_attachment_pauses_deepseek_and_restores_previous_selection](../../tests/e2e/test_smoke.py#L2106) (Zeile 2106)
- [test_attachment_block_survives_the_whole_run](../../tests/e2e/test_smoke.py#L2215) (Zeile 2215)
- [test_pdf_drop_uses_full_attachment_whitelist](../../tests/e2e/test_smoke.py#L2295) (Zeile 2295)
- [test_attachment_send_hard_blocks_stale_deepseek_selection](../../tests/e2e/test_smoke.py#L2349) (Zeile 2349)
- [test_tier_upgrade_applies_pro_defaults_but_keeps_explicit_picker_choice](../../tests/e2e/test_smoke.py#L2399) (Zeile 2399)
- [test_model_selection_persists_across_reload](../../tests/e2e/test_smoke.py#L2440) (Zeile 2440)

</details>

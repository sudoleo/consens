# JavaScript-Suite: Abdeckung pro Testdatei

Stand: **2026-10-02**, Quellstand `2860844af9dcba2087551af1697408e87e5fe928`. [Methodik und Gesamtbefund](../test-coverage-map.md).

**72 Dateien · 556 statische Testdefinitionen · 664 Runner-Fälle.**

„Geprüftes Verhalten“ beschreibt die vorhandenen Assertions. Der Laufstatus steht separat: bei Fehlern ist der beschriebene Vertrag nicht als bestanden belegt. Prüfaufträge sind offene Fragen, keine pauschal festgestellten Lücken der gesamten Suite. Aktuelle Befundbewertungen stehen im [Produktabgleich](product/README.md).

Die Codeverweise sind direkte Imports oder wörtliche Pfade, keine gemessene Ausführungsabdeckung. Indirekte Abhängigkeiten über Fixtures/Helpers und dynamisch zusammengesetzte Pfade können fehlen. Das [JSON-Inventar](inventory.json) enthält jede Definition mit Zeilen, Assertion-Fundstellen und jeden expandierten Runner-Fall. Datum, Umgebung und Grenzen stehen im [Laufbericht](findings.md).

| Datei | Definitionen | Runner-Fälle | Primärlauf 2026-10-02 |
|---|---:|---:|---|
| [account-tier-mark.test.mjs](#account-tier-mark-test-mjs) | 5 | 5 | 5 bestanden |
| [admin-agent-budget.test.mjs](#admin-agent-budget-test-mjs) | 2 | 2 | 2 bestanden |
| [admin-prompt-config.test.mjs](#admin-prompt-config-test-mjs) | 7 | 10 | 10 bestanden |
| [admin-reasoning-policy.test.mjs](#admin-reasoning-policy-test-mjs) | 2 | 2 | 2 bestanden |
| [admin-source-model.test.mjs](#admin-source-model-test-mjs) | 5 | 5 | 5 bestanden |
| [admin-topic-editor.test.mjs](#admin-topic-editor-test-mjs) | 4 | 4 | 4 bestanden |
| [admin-watch-effective-run.test.mjs](#admin-watch-effective-run-test-mjs) | 4 | 4 | 4 bestanden |
| [agent-answer-actions.test.mjs](#agent-answer-actions-test-mjs) | 4 | 4 | 4 bestanden |
| [agent-chat.test.mjs](#agent-chat-test-mjs) | 64 | 74 | 74 bestanden |
| [agent-citations.test.mjs](#agent-citations-test-mjs) | 9 | 9 | 9 bestanden |
| [agent-delegation.test.mjs](#agent-delegation-test-mjs) | 24 | 24 | 24 bestanden |
| [agent-google.test.mjs](#agent-google-test-mjs) | 10 | 10 | 10 bestanden |
| [agent-mode-projection.test.mjs](#agent-mode-projection-test-mjs) | 9 | 10 | 10 bestanden |
| [agent-preferences.test.mjs](#agent-preferences-test-mjs) | 2 | 2 | 2 bestanden |
| [agent-review.test.mjs](#agent-review-test-mjs) | 19 | 23 | 23 bestanden |
| [agent-workspace.test.mjs](#agent-workspace-test-mjs) | 11 | 11 | 11 bestanden |
| [app-state.test.mjs](#app-state-test-mjs) | 8 | 8 | 8 bestanden |
| [attachment-compression.test.mjs](#attachment-compression-test-mjs) | 5 | 5 | 5 bestanden |
| [attachment-draft-generation.test.mjs](#attachment-draft-generation-test-mjs) | 5 | 5 | 5 bestanden |
| [bookmark-attachments.test.mjs](#bookmark-attachments-test-mjs) | 6 | 6 | 6 bestanden |
| [bookmark-pending-state.test.mjs](#bookmark-pending-state-test-mjs) | 4 | 4 | 4 bestanden |
| [bookmark-source-check.test.mjs](#bookmark-source-check-test-mjs) | 2 | 2 | 2 bestanden |
| [bookmark-write-queue.test.mjs](#bookmark-write-queue-test-mjs) | 3 | 3 | 3 bestanden |
| [chat-scroll.test.mjs](#chat-scroll-test-mjs) | 10 | 12 | 12 bestanden |
| [claim-coverage-states.test.mjs](#claim-coverage-states-test-mjs) | 9 | 9 | 9 bestanden |
| [claim-mark-joins.test.mjs](#claim-mark-joins-test-mjs) | 1 | 1 | 1 bestanden |
| [composer-attachments.test.mjs](#composer-attachments-test-mjs) | 7 | 7 | 7 bestanden |
| [composer-quote.test.mjs](#composer-quote-test-mjs) | 11 | 11 | 11 bestanden |
| [consensus-anchor.test.mjs](#consensus-anchor-test-mjs) | 21 | 25 | 25 bestanden |
| [consensus-coverage-verdict.test.mjs](#consensus-coverage-verdict-test-mjs) | 3 | 3 | 3 bestanden |
| [consensus-marker-visibility.test.mjs](#consensus-marker-visibility-test-mjs) | 10 | 14 | 14 bestanden |
| [consensus-recovery.test.mjs](#consensus-recovery-test-mjs) | 6 | 6 | 6 bestanden |
| [contradiction-source-verification.test.mjs](#contradiction-source-verification-test-mjs) | 33 | 53 | 53 bestanden |
| [demo-claim-coverage.test.mjs](#demo-claim-coverage-test-mjs) | 2 | 2 | 2 bestanden |
| [dompurify-vendor.test.mjs](#dompurify-vendor-test-mjs) | 4 | 26 | 26 bestanden |
| [error-reporter.test.mjs](#error-reporter-test-mjs) | 13 | 15 | 15 bestanden |
| [frontend-output.test.mjs](#frontend-output-test-mjs) | 4 | 4 | 4 bestanden |
| [judge-stream-events.test.mjs](#judge-stream-events-test-mjs) | 1 | 1 | 1 bestanden |
| [markdown-remote-media.test.mjs](#markdown-remote-media-test-mjs) | 3 | 3 | 3 bestanden |
| [markdown-stream-incremental.test.mjs](#markdown-stream-incremental-test-mjs) | 4 | 7 | 7 bestanden |
| [markdown-table.test.mjs](#markdown-table-test-mjs) | 2 | 2 | 2 bestanden |
| [math-render.test.mjs](#math-render-test-mjs) | 19 | 26 | 26 bestanden |
| [memory-edit-auth.test.mjs](#memory-edit-auth-test-mjs) | 5 | 5 | 5 bestanden |
| [memory-edit-sources.test.mjs](#memory-edit-sources-test-mjs) | 1 | 2 | 2 bestanden |
| [mobile-header.test.mjs](#mobile-header-test-mjs) | 3 | 3 | 3 bestanden |
| [model-answer-reader.test.mjs](#model-answer-reader-test-mjs) | 21 | 24 | 24 bestanden |
| [model-attachment-capability.test.mjs](#model-attachment-capability-test-mjs) | 2 | 2 | 2 bestanden |
| [model-family-cap.test.mjs](#model-family-cap-test-mjs) | 4 | 4 | 4 bestanden |
| [model-pulse.test.mjs](#model-pulse-test-mjs) | 3 | 3 | 3 bestanden |
| [multi-run-view.test.mjs](#multi-run-view-test-mjs) | 10 | 10 | 10 bestanden |
| [plus-tier-gates.test.mjs](#plus-tier-gates-test-mjs) | 7 | 7 | 7 bestanden |
| [request-deadline.test.mjs](#request-deadline-test-mjs) | 3 | 3 | 3 bestanden |
| [result-integrity.test.mjs](#result-integrity-test-mjs) | 2 | 2 | 2 bestanden |
| [run-mode.test.mjs](#run-mode-test-mjs) | 4 | 8 | 8 bestanden |
| [run-progress-scope.test.mjs](#run-progress-scope-test-mjs) | 9 | 11 | 11 bestanden |
| [run-registry.test.mjs](#run-registry-test-mjs) | 9 | 9 | 9 bestanden |
| [send-button.test.mjs](#send-button-test-mjs) | 1 | 1 | 1 bestanden |
| [seo-admin-alerts.test.mjs](#seo-admin-alerts-test-mjs) | 10 | 10 | 10 bestanden |
| [sidebar-quota.test.mjs](#sidebar-quota-test-mjs) | 4 | 4 | 4 bestanden |
| [skeleton-lifecycle.test.mjs](#skeleton-lifecycle-test-mjs) | 3 | 5 | 5 bestanden |
| [source-catalog-refs.test.mjs](#source-catalog-refs-test-mjs) | 4 | 4 | 4 bestanden |
| [source-teaser-check.test.mjs](#source-teaser-check-test-mjs) | 5 | 10 | 10 bestanden |
| [source-url-identity.test.mjs](#source-url-identity-test-mjs) | 3 | 3 | 3 bestanden |
| [source-verification-watch.test.mjs](#source-verification-watch-test-mjs) | 12 | 13 | 13 bestanden |
| [source-verification.test.mjs](#source-verification-test-mjs) | 21 | 21 | 21 bestanden |
| [sse-completion.test.mjs](#sse-completion-test-mjs) | 5 | 11 | 11 bestanden |
| [stored-turn-markers.test.mjs](#stored-turn-markers-test-mjs) | 7 | 7 | 7 bestanden |
| [thread-question-disclosure.test.mjs](#thread-question-disclosure-test-mjs) | 2 | 2 | 2 bestanden |
| [topic-page.test.mjs](#topic-page-test-mjs) | 5 | 7 | 7 bestanden |
| [user-memory.test.mjs](#user-memory-test-mjs) | 6 | 6 | 6 bestanden |
| [watch-dashboard-state.test.mjs](#watch-dashboard-state-test-mjs) | 5 | 5 | 5 bestanden |
| [watch-feature-nudge.test.mjs](#watch-feature-nudge-test-mjs) | 3 | 3 | 3 bestanden |

<a id="account-tier-mark-test-mjs"></a>

## account-tier-mark.test.mjs

**Quelle:** [tests/js/account-tier-mark.test.mjs](../../tests/js/account-tier-mark.test.mjs) · **Bereiche:** Konten und Tarife.

**Ebene:** JavaScript-Modultest mit jsdom.

**Lauf:** 5 bestanden.

**Geprüftes Verhalten:** Pro-/Plus-Klassen und Beschriftung, Free ohne Markierung; Kontotarif bleibt bei abweichendem Lauftarif erhalten; Markierung nach Austausch des Footer-DOM.

**Grenzen und Doubles:** Echte app-state-/user-tier-Skripte, nachgebautes DOM; prüft Klassen, keine tatsächliche Goldfarbe oder Browserdarstellung.

**Prüfauftrag für den Folgeaudit:** Tarifwechsel im vollständigen Auth- und DOM-Lebenszyklus abgleichen.

**Direkte Codeverweise:** [static/js/app-state.js](../../static/js/app-state.js), [static/js/user-tier.js](../../static/js/user-tier.js).

**Direkte Testhelfer:** [tests/js/helpers/appWindow.mjs](../../tests/js/helpers/appWindow.mjs).

<details>
<summary>5 Testdefinitionen und ihre Quellstellen</summary>

- [marks Pro in gold and names it in the popup](../../tests/js/account-tier-mark.test.mjs#L52) (Zeile 52)
- [marks Plus without gold and names it too](../../tests/js/account-tier-mark.test.mjs#L63) (Zeile 63)
- [leaves Free unmarked](../../tests/js/account-tier-mark.test.mjs#L76) (Zeile 76)
- [keeps the mark when a Free run is opened](../../tests/js/account-tier-mark.test.mjs#L87) (Zeile 87)
- [re-applies the mark after the account footer is re-rendered](../../tests/js/account-tier-mark.test.mjs#L97) (Zeile 97)

</details>

<a id="admin-agent-budget-test-mjs"></a>

## admin-agent-budget.test.mjs

**Quelle:** [tests/js/admin-agent-budget.test.mjs](../../tests/js/admin-agent-budget.test.mjs) · **Bereiche:** Admin, Agent, Konten und Tarife.

**Ebene:** JavaScript-Modultest mit jsdom und HTTP-Doubles.

**Lauf:** 2 bestanden.

**Geprüftes Verhalten:** Eine Tabellenzeile je Tarif; Tageslimits und Modusschätzungen getrennt vom globalen Reset speichern.

**Grenzen und Doubles:** Echtes Admin-Template und admin-agent-budget-Modul mit entfernter Export-Syntax; Request und Bestätigung simuliert.

**Prüfauftrag für den Folgeaudit:** Serverseitige Berechtigung, Transaktion und UI-Anbindung in anderen Tests zuordnen.

**Direkte Codeverweise:** [static/js/admin-agent-budget.js](../../static/js/admin-agent-budget.js), [templates/admin.html](../../templates/admin.html).

**Direkte Testhelfer:** [tests/js/helpers/appWindow.mjs](../../tests/js/helpers/appWindow.mjs).

<details>
<summary>2 Testdefinitionen und ihre Quellstellen</summary>

- [renders one row per tier and saves limits and run estimates apart from the global reset](../../tests/js/admin-agent-budget.test.mjs#L22) (Zeile 22)
- [preserves the draft on failure and ignores an old account response](../../tests/js/admin-agent-budget.test.mjs#L54) (Zeile 54)

</details>

<a id="admin-prompt-config-test-mjs"></a>

## admin-prompt-config.test.mjs

**Quelle:** [tests/js/admin-prompt-config.test.mjs](../../tests/js/admin-prompt-config.test.mjs) · **Bereiche:** Admin, Prompts.

**Ebene:** JavaScript-Modultest und ausgeführte Quellcodeausschnitte mit jsdom.

**Lauf:** 10 bestanden.

**Geprüftes Verhalten:** Laden, Bearbeiten, revisionsgebundenes Speichern, Sperre während Requests; Prompttext als Text statt HTML; Standard wiederherstellen als Entwurf; versteckte Legacy-Felder erhalten; Konflikt, Ladefehler, verspätete fremde Antwort und leeres Pflichtfeld. Standard-/Legacy-Nutzerprompts überlassen die Wahl dem Server, individuelle Prompts bleiben gespeichert und erhalten Datum.

**Grenzen und Doubles:** Admin-Modul mit entfernter Export-Syntax und gemocktem Request; persönliche Promptwahl aus Ausschnitten von app-ui.js und query-send.js. Keine vollständige Admin-/Sendekette.

**Prüfauftrag für den Folgeaudit:** Gemeinsamen Vertrag zwischen gespeicherter Konfiguration, Promptauflösung und Provideraufruf abgleichen.

**Direkte Codeverweise:** [static/app-ui.js](../../static/app-ui.js), [static/js/admin-prompt-config.js](../../static/js/admin-prompt-config.js), [static/js/query-send.js](../../static/js/query-send.js), [templates/admin.html](../../templates/admin.html), [templates/partials/admin_prompt_config.html](../../templates/partials/admin_prompt_config.html).

**Direkte Testhelfer:** [tests/js/helpers/appWindow.mjs](../../tests/js/helpers/appWindow.mjs).

<details>
<summary>7 Testdefinitionen und ihre Quellstellen</summary>

- [hides retired chat caps while preserving legacy values when saving current settings](../../tests/js/admin-prompt-config.test.mjs#L30) (Zeile 30)
- [loads, edits, saves exactly one config with its revision, and restores defaults as a draft](../../tests/js/admin-prompt-config.test.mjs#L47) (Zeile 47)
- [keeps the draft after conflict or failure and allows explicit reload](../../tests/js/admin-prompt-config.test.mjs#L69) (Zeile 69)
- [does not enable saving after a failed load or apply a stale login response](../../tests/js/admin-prompt-config.test.mjs#L84) (Zeile 84)
- [opens a collapsed editor when its required prompt is empty](../../tests/js/admin-prompt-config.test.mjs#L100) (Zeile 100)
- [lets the server choose the central default for %s](../../tests/js/admin-prompt-config.test.mjs#L118) (Zeile 118)
- [preserves an explicitly customized personal prompt](../../tests/js/admin-prompt-config.test.mjs#L128) (Zeile 128)

</details>

<a id="admin-reasoning-policy-test-mjs"></a>

## admin-reasoning-policy.test.mjs

**Quelle:** [tests/js/admin-reasoning-policy.test.mjs](../../tests/js/admin-reasoning-policy.test.mjs) · **Bereiche:** Admin, Modelle und Provider.

**Ebene:** Ausgeführter admin.js-Ausschnitt mit jsdom.

**Lauf:** 2 bestanden.

**Geprüftes Verhalten:** Economy-/Quality-Vorschau, geschützte Modelle ohne unzulässige Auswahl, Ausnahme wird serialisiert; unsichere Modellnamen bleiben Text; Wechsel der Vorschau verändert keinen gespeicherten Entwurf.

**Grenzen und Doubles:** Ausschnitt von meta bis currentPresetModels, künstliche Modelldaten und Dirty-Callback; kein vollständiges Admin-Modul oder HTTP-Speichern.

**Prüfauftrag für den Folgeaudit:** Effektive Policy im nächsten Backendlauf sowie Modellfähigkeiten abgleichen.

**Direkte Codeverweise:** [static/js/admin.js](../../static/js/admin.js), [templates/admin.html](../../templates/admin.html).

**Direkte Testhelfer:** [tests/js/helpers/appWindow.mjs](../../tests/js/helpers/appWindow.mjs).

<details>
<summary>2 Testdefinitionen und ihre Quellstellen</summary>

- [previews savings, preserves protected models and serializes a quality exception](../../tests/js/admin-reasoning-policy.test.mjs#L37) (Zeile 37)
- [changing the preview scope does not dirty the saved configuration](../../tests/js/admin-reasoning-policy.test.mjs#L60) (Zeile 60)

</details>

<a id="admin-source-model-test-mjs"></a>

## admin-source-model.test.mjs

**Quelle:** [tests/js/admin-source-model.test.mjs](../../tests/js/admin-source-model.test.mjs) · **Bereiche:** Admin, Quellenprüfung.

**Ebene:** Ausgeführte admin.js-Ausschnitte mit jsdom.

**Lauf:** 5 bestanden.

**Geprüftes Verhalten:** Standardmodell, sichere Modellnamen, Erhalt des Entwurfs bei Neurendern und Reset bei Laden; Fallback deaktivierbar und verschieden vom Primärmodell; deaktivierter Entwurf bleibt erhalten; primärer und Fallback-Wert gelangen in den Speicherrequest.

**Grenzen und Doubles:** Quellcodeausschnitte für Quellmodell-Konfiguration und saveModels; Auth, Fetch und andere Konfigurationshelfer ersetzt.

**Prüfauftrag für den Folgeaudit:** Vollständigen Speichern-/Neuladen-Ablauf und serverseitige Zulässigkeit zuordnen.

**Direkte Codeverweise:** [static/js/admin.js](../../static/js/admin.js), [templates/admin.html](../../templates/admin.html).

**Direkte Testhelfer:** [tests/js/helpers/appWindow.mjs](../../tests/js/helpers/appWindow.mjs).

<details>
<summary>5 Testdefinitionen und ihre Quellstellen</summary>

- [shows the Gemini default and renders model labels as text](../../tests/js/admin-source-model.test.mjs#L33) (Zeile 33)
- [keeps a draft choice during rerenders and discards it when saved data reloads](../../tests/js/admin-source-model.test.mjs#L43) (Zeile 43)
- [defaults fallback to Disabled and prevents selecting the primary model twice](../../tests/js/admin-source-model.test.mjs#L54) (Zeile 54)
- [preserves a Disabled draft instead of restoring a previously saved fallback](../../tests/js/admin-source-model.test.mjs#L65) (Zeile 65)
- [sends the chosen source model through the existing admin save request](../../tests/js/admin-source-model.test.mjs#L78) (Zeile 78)

</details>

<a id="admin-topic-editor-test-mjs"></a>

## admin-topic-editor.test.mjs

**Quelle:** [tests/js/admin-topic-editor.test.mjs](../../tests/js/admin-topic-editor.test.mjs) · **Bereiche:** Admin, Topics.

**Ebene:** jsdom-Editor mit kontrollierten Fetchantworten.

**Lauf:** 4 bestanden.

**Geprüftes Verhalten:** Langsame/falsch zugeordnete Topicantworten dürfen nicht unter neuer ID gespeichert werden; fehlgeschlagener Load sperrt Save, Wechsel invalidiert alten Formularzustand.

**Grenzen und Doubles:** Kein echter Adminrouter oder Browserlayout.

**Prüfauftrag für den Folgeaudit:** Die benannten Mock-/Integrationsgrenzen am realen Adapter prüfen; Zuordnung und offene Aufgaben stehen in der Produktmatrix.

**Direkte Codeverweise:** [static/js/admin.js](../../static/js/admin.js), [templates/admin.html](../../templates/admin.html).

<details>
<summary>4 Testdefinitionen und ihre Quellstellen</summary>

- [never saves the A form under B after B failed to load](../../tests/js/admin-topic-editor.test.mjs#L98) (Zeile 98)
- [drops a slow A answer that arrives after B was selected](../../tests/js/admin-topic-editor.test.mjs#L114) (Zeile 114)
- [an account change invalidates the editor and any open request](../../tests/js/admin-topic-editor.test.mjs#L133) (Zeile 133)
- [keeps saving a new Topic and a loaded Topic working](../../tests/js/admin-topic-editor.test.mjs#L146) (Zeile 146)

</details>

<a id="admin-watch-effective-run-test-mjs"></a>

## admin-watch-effective-run.test.mjs

**Quelle:** [tests/js/admin-watch-effective-run.test.mjs](../../tests/js/admin-watch-effective-run.test.mjs) · **Bereiche:** Admin, Modelle und Provider, Watch.

**Ebene:** Ausgeführter admin.js-Ausschnitt mit jsdom.

**Lauf:** 4 bestanden.

**Geprüftes Verhalten:** Effektive Providerzahl, Ausschluss fehlender Zugangsdaten, Premium-Ausschluss bei Free und Warnung unter zwei Modellen; Pro gültig; unbekannter Credentialstatus wird nicht als bestätigt dargestellt.

**Grenzen und Doubles:** Künstliche Liste aus sechs Providern, Modell- und Dirty-Doubles, kleines Watch-DOM; keine vollständige Registry oder tatsächliche Watchausführung.

**Prüfauftrag für den Folgeaudit:** Angezeigte Vorschau gegen die reale Backend-Auswahl einschließlich weiterer Provider abgleichen.

**Direkte Codeverweise:** [static/js/admin.js](../../static/js/admin.js), [templates/admin.html](../../templates/admin.html).

**Direkte Testhelfer:** [tests/js/helpers/appWindow.mjs](../../tests/js/helpers/appWindow.mjs).

<details>
<summary>4 Testdefinitionen und ihre Quellstellen</summary>

- [names every provider the next run will really use](../../tests/js/admin-watch-effective-run.test.mjs#L76) (Zeile 76)
- [names the skipped provider when the server has no credential for it](../../tests/js/admin-watch-effective-run.test.mjs#L93) (Zeile 93)
- [flags a Free tier pick that is locked to Pro instead of dropping it silently](../../tests/js/admin-watch-effective-run.test.mjs#L111) (Zeile 111)
- [claims nothing while the server reports no credential state at all](../../tests/js/admin-watch-effective-run.test.mjs#L129) (Zeile 129)

</details>

<a id="agent-answer-actions-test-mjs"></a>

## agent-answer-actions.test.mjs

**Quelle:** [tests/js/agent-answer-actions.test.mjs](../../tests/js/agent-answer-actions.test.mjs) · **Bereiche:** Agent, Antwortdarstellung.

**Ebene:** JavaScript-Modultest mit jsdom.

**Lauf:** 4 bestanden.

**Geprüftes Verhalten:** Kopiert kanonischen Antworttext; stabile Bedienelemente und Fokus bei Projektion; Aktionen für vollständige bzw. gestoppte Teilantwort, getrennte archivierte Antworten; verspätete Clipboardantwort verworfen, Ablehnung erneut versuchbar; execCommand-Fallback wertet Erfolg aus, entfernt Hilfsfeld und stellt Fokus wieder her.

**Grenzen und Doubles:** Clipboard-/execCommand-Doubles; keine realen Browserberechtigungen.

**Prüfauftrag für den Folgeaudit:** Browserpfade für Kopieren und Tastaturzugang zuordnen.

**Direkte Codeverweise:** [static/js/agent-answer-actions.js](../../static/js/agent-answer-actions.js).

**Direkte Testhelfer:** [tests/js/helpers/appWindow.mjs](../../tests/js/helpers/appWindow.mjs).

<details>
<summary>4 Testdefinitionen und ihre Quellstellen</summary>

- [copies only the canonical answer and keeps controls stable across projections](../../tests/js/agent-answer-actions.test.mjs#L14) (Zeile 14)
- [hides incomplete streams, preserves partial answers after stop and separates archived turns](../../tests/js/agent-answer-actions.test.mjs#L32) (Zeile 32)
- [does not apply late clipboard feedback to a different answer and allows retry after denial](../../tests/js/agent-answer-actions.test.mjs#L45) (Zeile 45)
- [checks fallback clipboard success and returns keyboard focus](../../tests/js/agent-answer-actions.test.mjs#L67) (Zeile 67)

</details>

<a id="agent-chat-test-mjs"></a>

## agent-chat.test.mjs

**Quelle:** [tests/js/agent-chat.test.mjs](../../tests/js/agent-chat.test.mjs) · **Bereiche:** Agent, Composer, Konten und Tarife, Streaming und Wiederherstellung.

**Ebene:** JavaScript-Modulintegration mit jsdom und Transport-Doubles.

**Lauf:** 74 bestanden.

**Geprüftes Verhalten:** Katalogladen/-fehler, Verfügbarkeit und zwei bis sechs Vergleichsmodelle vor Versand validiert; Modellpicker, Tastatur, entfernte gespeicherte Modelle und kontogebundene Einstellungen. Unversandten Entwurf/Zitat nur bei gleichem Eigentümer und leerem Composer wiederherstellen; Abbruch während Chatanlage. Kontingent nach Resetepoche/Tag/Revision, Fokusrefresh, Hänger und alte/fremde Antworten; Verbindungsstille erhält Teilantwort und Turn. Recovery mit stabiler Request-ID, ohne neuen Lauf, mit Duplikatschutz, Statusprüfung und Übernahme gespeicherter Teilantwort/fehlgeschlagenem Review. Quellenpräferenz pro Lauf eingefroren; Aktivität, Reasoning und Antwort getrennt; Toolstatus, begrenzte Statushistorie, Serverdauer und geschätzte/gemessene Kosten. Hintergrundabschluss verändert sichtbare Gesprächsbasis nicht; Konten-/Logoutgrenzen, Bookmarkrestore, Agentendpoint, Anhangsperre, sichere bestätigte Quellen, unbekannte Usage und Bereinigung von Zwischenantworten. Aktualisierung 02.10.2026: Uploads vor Start, IDs für Recovery, resources-Events gezielt verteilen, inkrementelles Rendern ohne Composer-Neuaufbau, Sendeblocker für Google und Reviewhinweise. Ein Modellpicker verbindet Chat-/Vergleichsmodelle; vollständige geprüfte Antwort bleibt trotz späterem Runfehler vollständig.

**Grenzen und Doubles:** Echte Registry-, Picker-, Deadline-, Aktivitäts- und Chatmodule; Fetch/Auth/SSE-Anbindung sowie Markdown-/Followup-/Bookmarkhelfer simuliert. Keine echte Modellantwort, HTTP-Verbindung oder Persistenz.

**Prüfauftrag für den Folgeaudit:** Dieselben Abbruch-/Recovery- und Kontenwechselverträge über Backend, Bookmarkpersistenz und Browser zusammenführen.

**Direkte Codeverweise:** [static/js/agent-activity.js](../../static/js/agent-activity.js), [static/js/agent-chat.js](../../static/js/agent-chat.js), [static/js/model-picker.js](../../static/js/model-picker.js), [static/js/request-deadline.js](../../static/js/request-deadline.js), [static/js/run-mode.js](../../static/js/run-mode.js), [static/js/run-registry.js](../../static/js/run-registry.js), [static/js/token-budget.js](../../static/js/token-budget.js).

**Direkte Testhelfer:** [tests/js/helpers/appWindow.mjs](../../tests/js/helpers/appWindow.mjs).

<details>
<summary>64 Testdefinitionen und ihre Quellstellen</summary>

- [blocks sending during catalog loading/failure and when every model is unavailable](../../tests/js/agent-chat.test.mjs#L54) (Zeile 54)
- [restores an unsent draft without replacing newer composer ownership: %s](../../tests/js/agent-chat.test.mjs#L73) (Zeile 73)
- [does not restore an already dispatched request as an unsent draft](../../tests/js/agent-chat.test.mjs#L96) (Zeile 96)
- [validates %i comparison models before clearing the draft or creating a chat](../../tests/js/agent-chat.test.mjs#L107) (Zeile 107)
- [keeps unresolved admin models visible and disabled, and repairs a saved unavailable selection](../../tests/js/agent-chat.test.mjs#L131) (Zeile 131)
- [groups chat models by provider, supports keyboard navigation and keeps reasoning tied to the chosen model](../../tests/js/agent-chat.test.mjs#L151) (Zeile 151)
- [orders allowance snapshots by reset, UTC day and ledger revision despite server clock skew](../../tests/js/agent-chat.test.mjs#L194) (Zeile 194)
- [refreshes idle allowance on focus and marks failed refreshes as stale](../../tests/js/agent-chat.test.mjs#L213) (Zeile 213)
- [recovers the model picker and budget refresh after hung control requests](../../tests/js/agent-chat.test.mjs#L228) (Zeile 228)
- [ends a silent Agent connection with recoverable partial text and a known turn identity](../../tests/js/agent-chat.test.mjs#L252) (Zeile 252)
- [explains allowance waiting outside the collapsed activity details](../../tests/js/agent-chat.test.mjs#L276) (Zeile 276)
- [keeps the newest status and usage after long runs exceed the activity window](../../tests/js/agent-chat.test.mjs#L286) (Zeile 286)
- [freezes source-check permission for sending and recovery while the next-message preference changes](../../tests/js/agent-chat.test.mjs#L298) (Zeile 298)
- [updates the allowance on terminal errors and ignores older or foreign snapshots](../../tests/js/agent-chat.test.mjs#L319) (Zeile 319)
- [refreshes the allowance after a disconnected stream](../../tests/js/agent-chat.test.mjs#L340) (Zeile 340)
- [leaves tool mentions plain and highlights only confirmed running calls](../../tests/js/agent-chat.test.mjs#L353) (Zeile 353)
- [keeps a review stage in one live row when tool events arrive](../../tests/js/agent-chat.test.mjs#L377) (Zeile 377)
- [commits a draft model before an input-triggered projection can restore the old model](../../tests/js/agent-chat.test.mjs#L393) (Zeile 393)
- [keeps a running chat's model independent of an earlier draft selection](../../tests/js/agent-chat.test.mjs#L410) (Zeile 410)
- [shows provider costs separately from estimates and removes status dashes](../../tests/js/agent-chat.test.mjs#L423) (Zeile 423)
- [keeps the selected conversation when a background follow-up ends: %s](../../tests/js/agent-chat.test.mjs#L436) (Zeile 436)
- [recovers a first message without borrowing another conversation's history](../../tests/js/agent-chat.test.mjs#L461) (Zeile 461)
- [does not start a model request after cancellation during chat creation](../../tests/js/agent-chat.test.mjs#L479) (Zeile 479)
- [reconciles a removed saved model with the displayed choice before sending](../../tests/js/agent-chat.test.mjs#L495) (Zeile 495)
- [uses the same keyboard picker for effort and returns focus after choosing](../../tests/js/agent-chat.test.mjs#L516) (Zeile 516)
- [interleaves confirmed steps with complete localized updates and preserves the finished history](../../tests/js/agent-chat.test.mjs#L541) (Zeile 541)
- [reads a complete, checked answer as done even when the run failed afterwards](../../tests/js/agent-chat.test.mjs#L581) (Zeile 581)
- [names the sources a web search found instead of the bare verb](../../tests/js/agent-chat.test.mjs#L593) (Zeile 593)
- [does not claim to write the answer while a preamble led into a tool step](../../tests/js/agent-chat.test.mjs#L607) (Zeile 607)
- [shows useful run details when opened during thinking, before any progress or tool event](../../tests/js/agent-chat.test.mjs#L620) (Zeile 620)
- [ticks runtime through waiting, freezes at stop, and disposes the live timer](../../tests/js/agent-chat.test.mjs#L635) (Zeile 635)
- [restores saved runtime from terminal timestamps rather than the time since creation](../../tests/js/agent-chat.test.mjs#L666) (Zeile 666)
- [retains live insights across a partial final snapshot and uses saved tool outcomes](../../tests/js/agent-chat.test.mjs#L680) (Zeile 680)
- [retains progress paragraphs and confirmed steps when the auxiliary status window rotates](../../tests/js/agent-chat.test.mjs#L704) (Zeile 704)
- [collapses finished reasoning, preserves explicit disclosure, and restores stopped status](../../tests/js/agent-chat.test.mjs#L719) (Zeile 719)
- [requires the current account's entitlement and retains no cross-account access](../../tests/js/agent-chat.test.mjs#L743) (Zeile 743)
- [calls only the agent endpoint and continues the same persisted chat](../../tests/js/agent-chat.test.mjs#L758) (Zeile 758)
- [uploads attachments before starting the agent and freezes IDs for recovery](../../tests/js/agent-chat.test.mjs#L786) (Zeile 786)
- [restores an agent bookmark independently of the global consensus preference](../../tests/js/agent-chat.test.mjs#L802) (Zeile 802)
- [ignores late completion after logout](../../tests/js/agent-chat.test.mjs#L818) (Zeile 818)
- [recovers with the same identity and an explicit no-new-call flag](../../tests/js/agent-chat.test.mjs#L835) (Zeile 835)
- [adopts a server-saved partial answer and bookmark while preserving its failed review](../../tests/js/agent-chat.test.mjs#L854) (Zeile 854)
- [offers a status check rather than claiming an unfinished server run is already saved](../../tests/js/agent-chat.test.mjs#L874) (Zeile 874)
- [does not offer recovery without a saved answer and deduplicates concurrent recovery clicks](../../tests/js/agent-chat.test.mjs#L888) (Zeile 888)
- [keeps a new budget generation when an older worker sends a later snapshot](../../tests/js/agent-chat.test.mjs#L915) (Zeile 915)
- [rebuilds its history after displaying another conversation](../../tests/js/agent-chat.test.mjs#L924) (Zeile 924)
- [reuses the picker, sends supported effort, and leaves consensus preferences alone](../../tests/js/agent-chat.test.mjs#L943) (Zeile 943)
- [streams reasoning separately, preserves disclosure, and ignores deltas after stop](../../tests/js/agent-chat.test.mjs#L965) (Zeile 965)
- [restores reasoning and settings from a saved turn without treating reasoning as HTML](../../tests/js/agent-chat.test.mjs#L1007) (Zeile 1007)
- [repairs a removed history model for the next message without changing its saved label](../../tests/js/agent-chat.test.mjs#L1023) (Zeile 1023)
- [keeps the actual failure reason visible when reopening an incomplete answer](../../tests/js/agent-chat.test.mjs#L1041) (Zeile 1041)
- [hides legacy unconfirmed searches (%s) while preserving reasoning and measured costs](../../tests/js/agent-chat.test.mjs#L1055) (Zeile 1055)
- [renders confirmed native sources, partial usage and safe links from history](../../tests/js/agent-chat.test.mjs#L1078) (Zeile 1078)
- [keeps tool states honest and clears intermediate answer text for a new step](../../tests/js/agent-chat.test.mjs#L1101) (Zeile 1101)
- [routes resources events to the list they name and refreshes both when unsure](../../tests/js/agent-chat.test.mjs#L1136) (Zeile 1136)
- [never re-renders the composer shell or the full answer for a streamed chunk](../../tests/js/agent-chat.test.mjs#L1167) (Zeile 1167)
- [lets the fixed answer shimmer while it is checked and shows its marks as soon as the check ends](../../tests/js/agent-chat.test.mjs#L1208) (Zeile 1208)
- [restores the draft without a recovery or failed row when the server refuses before starting](../../tests/js/agent-chat.test.mjs#L1246) (Zeile 1246)
- [explains a token reservation refusal in plain words with next steps](../../tests/js/agent-chat.test.mjs#L1265) (Zeile 1265)
- [blocks Send with the Google blocker and runs its action](../../tests/js/agent-chat.test.mjs#L1288) (Zeile 1288)
- [shows a pending-review notice, bookmark dot and tab count after a run](../../tests/js/agent-chat.test.mjs#L1307) (Zeile 1307)
- [carries both choices in one menu and gives the comparison chip back outside Agent](../../tests/js/agent-chat.test.mjs#L1357) (Zeile 1357)
- [opens the named level from shortcuts and keeps the comparisons open while the chat model is locked](../../tests/js/agent-chat.test.mjs#L1417) (Zeile 1417)
- [links once the comparison picker exists, whichever picker comes first](../../tests/js/agent-chat.test.mjs#L1454) (Zeile 1454)

</details>

<a id="agent-citations-test-mjs"></a>

## agent-citations.test.mjs

**Quelle:** [tests/js/agent-citations.test.mjs](../../tests/js/agent-citations.test.mjs) · **Bereiche:** Agent, Markdown und Darstellung, Quellenprüfung.

**Ebene:** JavaScript-Modulintegration mit jsdom.

**Lauf:** 9 bestanden.

**Geprüftes Verhalten:** URL- und nummerierte Quellenverweise mit Titel, sicheren Linkattributen und ARIA; Deduplizierung, explizite IDs und unveränderte mehrdeutige/fehlende Verweise; Code-/Mathematiknotation bleibt korrekt; nachträgliche Metadaten erhalten Fokus und Turnbindung; Reviewmarker ändern geprüften Markdown-/Versionsstand nicht. Aktualisierung 02.10.2026: Quellen als Faviconpillen: Paper-URLs, Domainlabels, Gruppen mit +N, zugängliche Vorschau und neutraler Fallback bei fehlerhaftem Favicon.

**Grenzen und Doubles:** Echte sources-, markdown-stream- und agent-review-Skripte sowie marked/DOMPurify; Reviewmarkerhelfer teilweise ersetzt.

**Prüfauftrag für den Folgeaudit:** Provider-Metadaten und persistierte Quellen im vollständigen Ablauf abgleichen.

**Direkte Codeverweise:** [static/js/agent-review.js](../../static/js/agent-review.js), [static/js/markdown-stream.js](../../static/js/markdown-stream.js), [static/js/sources.js](../../static/js/sources.js).

**Direkte Testhelfer:** [tests/js/helpers/appWindow.mjs](../../tests/js/helpers/appWindow.mjs).

<details>
<summary>9 Testdefinitionen und ihre Quellstellen</summary>

- [turns parenthesized paper URLs into source pills with their original titles](../../tests/js/agent-citations.test.mjs#L27) (Zeile 27)
- [deduplicates repeated URLs and preserves named link formatting, code, math notation and unsafe links](../../tests/js/agent-citations.test.mjs#L46) (Zeile 46)
- [maps explicit source IDs by identity without turning numeric notation or ambiguous IDs into citations](../../tests/js/agent-citations.test.mjs#L60) (Zeile 60)
- [reformats streamed text and updates metadata without borrowing another turn or replacing focused references](../../tests/js/agent-citations.test.mjs#L71) (Zeile 71)
- [applies citations after review markers without changing the checked answer or its version binding](../../tests/js/agent-citations.test.mjs#L88) (Zeile 88)
- [lets a pill stand in for a link label that only repeats its domain](../../tests/js/agent-citations.test.mjs#L108) (Zeile 108)
- [collapses adjacent citations into one pill and lists every source in the teaser](../../tests/js/agent-citations.test.mjs#L125) (Zeile 125)
- [shows only the favicon when the domain is already written before the citation](../../tests/js/agent-citations.test.mjs#L151) (Zeile 151)
- [replaces a failed favicon with a neutral monogram instead of a broken image](../../tests/js/agent-citations.test.mjs#L164) (Zeile 164)

</details>

<a id="agent-delegation-test-mjs"></a>

## agent-delegation.test.mjs

**Quelle:** [tests/js/agent-delegation.test.mjs](../../tests/js/agent-delegation.test.mjs) · **Bereiche:** Agent, Streaming und Wiederherstellung.

**Ebene:** JavaScript-Modulintegration mit jsdom und Request-Doubles.

**Lauf:** 24 bestanden.

**Geprüftes Verhalten:** Stabile Symbole/Fokus und getrennte gleichnamige Delegationen; monotone, nach Abschluss eingefrorene Dauer; verspätete Konten-/Chatantworten und veraltete Summen verworfen. Zeichen-/Token-/unbekannte Usagezustände; Liveevents reduzieren Polling, Stille aktiviert Fallback, abgeschlossene Delegation startet nicht neu. Judge-Details aus Snapshot, Skeleton/Laden/Cache und sicherer Fehlertext; Kontingent aus Aktivitätsrequest; automatisches erstes Öffnen respektiert späteres Schließen; Wiederherstellung startet keine Modelle. Aktualisierung 02.10.2026: Timer endet bei Inaktivität, kein Timer für gespeicherte Turns; mobiles Sheet mit Scrim/Fokusfalle, eine Prüfreihe für Retries/Judges, lesbare unvollständige Modellantworten und stabile Details in einem Scrollbereich.

**Grenzen und Doubles:** Echte Deadline-/Delegationslogik, simulierte Fetch-, Auth- und RunRegistry-Grenzen; kein Provider oder Netzwerk.

**Prüfauftrag für den Folgeaudit:** Polling-/SSE-Konkurrenz und Sidebar-Anbindung im echten Browser zuordnen.

**Direkte Codeverweise:** [static/js/agent-delegation.js](../../static/js/agent-delegation.js), [static/js/request-deadline.js](../../static/js/request-deadline.js).

**Direkte Testhelfer:** [tests/js/helpers/appWindow.mjs](../../tests/js/helpers/appWindow.mjs).

<details>
<summary>24 Testdefinitionen und ihre Quellstellen</summary>

- [stops its 2.5 s tick once nothing runs and never starts one for a saved turn](../../tests/js/agent-delegation.test.mjs#L29) (Zeile 29)
- [opens as a sheet only on request under 1200 px, with a scrim and a focus trap](../../tests/js/agent-delegation.test.mjs#L44) (Zeile 44)
- [does not rewrite row titles or status text when nothing changed](../../tests/js/agent-delegation.test.mjs#L66) (Zeile 66)
- [keeps model icons and keyboard focus stable as statuses and same-model calls change](../../tests/js/agent-delegation.test.mjs#L80) (Zeile 80)
- [uses elapsed server durations with a monotonic clock and freezes terminal or recovered sessions](../../tests/js/agent-delegation.test.mjs#L100) (Zeile 100)
- [does not replace a newer polled total with a stale run projection](../../tests/js/agent-delegation.test.mjs#L123) (Zeile 123)
- [discards a pending old session response after the same user signs in again](../../tests/js/agent-delegation.test.mjs#L132) (Zeile 132)
- [shows live received characters, switches to provider tokens and stops shimmer on completion](../../tests/js/agent-delegation.test.mjs#L146) (Zeile 146)
- [clears transient counters on stop and turn switches and never animates saved active snapshots](../../tests/js/agent-delegation.test.mjs#L174) (Zeile 174)
- [shows loading independently for each model and hides it for terminal or paused sessions](../../tests/js/agent-delegation.test.mjs#L190) (Zeile 190)
- [uses SSE updates without polling, repairs quiet streams, and never revives a completed run](../../tests/js/agent-delegation.test.mjs#L202) (Zeile 202)
- [shows measured input plus output tokens, with no invented zero or double-counted details](../../tests/js/agent-delegation.test.mjs#L230) (Zeile 230)
- [opens judge details immediately from live snapshots without detail reads](../../tests/js/agent-delegation.test.mjs#L244) (Zeile 244)
- [shows a skeleton immediately and reuses cached messages on reopening](../../tests/js/agent-delegation.test.mjs#L260) (Zeile 260)
- [updates the account allowance from the existing activity request](../../tests/js/agent-delegation.test.mjs#L279) (Zeile 279)
- [opens on first start, shares state with inline icons and respects manual close and duplicate events](../../tests/js/agent-delegation.test.mjs#L287) (Zeile 287)
- [distinguishes same-model agents and restores saved state without starting any model request](../../tests/js/agent-delegation.test.mjs#L313) (Zeile 313)
- [ignores delayed responses and events after account or conversation switch](../../tests/js/agent-delegation.test.mjs#L325) (Zeile 325)
- [folds judge attempts, retries and backups into one quiet Answer check row](../../tests/js/agent-delegation.test.mjs#L341) (Zeile 341)
- [names a check that no model could run, once, in the Answer check row](../../tests/js/agent-delegation.test.mjs#L368) (Zeile 368)
- [shows a failed comparison model's reason as a plain note without routing labels](../../tests/js/agent-delegation.test.mjs#L381) (Zeile 381)
- [keeps the text of a comparison model stopped mid-answer, marked as incomplete](../../tests/js/agent-delegation.test.mjs#L398) (Zeile 398)
- [renders untrusted text safely, labels unknown totals and retries details only on demand](../../tests/js/agent-delegation.test.mjs#L416) (Zeile 416)
- [sums the run up in one overview and keeps opened details in the single scrolling list](../../tests/js/agent-delegation.test.mjs#L430) (Zeile 430)

</details>

<a id="agent-google-test-mjs"></a>

## agent-google.test.mjs

**Quelle:** [tests/js/agent-google.test.mjs](../../tests/js/agent-google.test.mjs) · **Bereiche:** Google, Agent.

**Ebene:** jsdom-Auswahl und Aktionskarten mit Fetch-Doubles.

**Lauf:** 10 bestanden.

**Geprüftes Verhalten:** Lazy Connections, vollständige Kalenderauswahl und Zustimmung pro Nachricht; Kontowechsel leert Auswahl. Untrusted Text bleibt inert, bestätigter Hash stimmt, unklare Aktionen bieten kein Wiederholen; abgelaufene/ersetzte Vorschläge, Empfängerentfernung und Authwechsel.

**Grenzen und Doubles:** Google-/Aktionsendpoints simuliert, keine echte Zustimmungspersistenz oder Browsergeometrie.

**Prüfauftrag für den Folgeaudit:** Die benannten Mock-/Integrationsgrenzen am realen Adapter prüfen; Zuordnung und offene Aufgaben stehen in der Produktmatrix.

**Direkte Codeverweise:** [static/js/agent-google.js](../../static/js/agent-google.js).

<details>
<summary>10 Testdefinitionen und ihre Quellstellen</summary>

- [loads connections only on first use and never sends a partial selection](../../tests/js/agent-google.test.mjs#L33) (Zeile 33)
- [requires consent on every message in a chat that already holds Google data](../../tests/js/agent-google.test.mjs#L59) (Zeile 59)
- [removing a source chip turns it off](../../tests/js/agent-google.test.mjs#L70) (Zeile 70)
- [renders untrusted text safely and submits the exact displayed hash only after review](../../tests/js/agent-google.test.mjs#L82) (Zeile 82)
- [does not offer repeat execution for ambiguous results](../../tests/js/agent-google.test.mjs#L104) (Zeile 104)
- [shows expired approvals as expired and prepares them again without a model call](../../tests/js/agent-google.test.mjs#L110) (Zeile 110)
- [requires a per-address acknowledgement for flagged recipients and offers a send grant for unauthorized drafts](../../tests/js/agent-google.test.mjs#L123) (Zeile 123)
- [coalesces refreshes and discards late reads after an account change](../../tests/js/agent-google.test.mjs#L155) (Zeile 155)
- [projects the current chat on its own, skips a new chat while it starts and reloads when the run finishes](../../tests/js/agent-google.test.mjs#L166) (Zeile 166)
- [stays hidden when actions fail in a chat without Google data](../../tests/js/agent-google.test.mjs#L182) (Zeile 182)

</details>

<a id="agent-mode-projection-test-mjs"></a>

## agent-mode-projection.test.mjs

**Quelle:** [tests/js/agent-mode-projection.test.mjs](../../tests/js/agent-mode-projection.test.mjs) · **Bereiche:** Agent, Composer, Responsive UI.

**Ebene:** JavaScript-Modultest mit jsdom.

**Lauf:** 10 bestanden.

**Geprüftes Verhalten:** Toolbar-/Menüprojektion bei Agent, Direct und neuem Lauf; sichtbarer Lauf getrennt von Präferenz für nächste Nachricht; synchronisierte und gesperrte Schalter; Quellenpräferenz bleibt bei Direct/Reload erhalten; Anhänge im Agentmodus gesperrt; Reasoning-/Modellpicker-Routing, abgelehnte Umschaltung, Bereinigung veralteter Modellstatus und nullsicherer Fallback. Aktualisierung 02.10.2026: Einheitlicher Composer und Modusselektor: Tools wechseln in das Plusmenü, Chats behalten Familie, neue Ansicht stellt Toolbar wieder her; Settings synchronisiert.

**Grenzen und Doubles:** matchMedia und minimales DOM simuliert; Assertions prüfen Zustand/Attribute, keine tatsächliche Position oder CSS-Geometrie.

**Prüfauftrag für den Folgeaudit:** Responsive Darstellung und Moduswechsel während laufender Antworten browserseitig abgleichen.

**Direkte Codeverweise:** [static/js/agent-mode.js](../../static/js/agent-mode.js), [static/js/run-mode.js](../../static/js/run-mode.js).

**Direkte Testhelfer:** [tests/js/helpers/appWindow.mjs](../../tests/js/helpers/appWindow.mjs).

<details>
<summary>9 Testdefinitionen und ihre Quellstellen</summary>

- [moves Beta tools into the plus menu after chat start](../../tests/js/agent-mode-projection.test.mjs#L62) (Zeile 62)
- [persists source checks for agent runs and locks every control for direct comparisons](../../tests/js/agent-mode-projection.test.mjs#L114) (Zeile 114)
- [gates the saved source preference %s on reload without changing it](../../tests/js/agent-mode-projection.test.mjs#L147) (Zeile 147)
- [uses one toolbar rule for every mode: tools on the start screen, a docked status line in a chat](../../tests/js/agent-mode-projection.test.mjs#L166) (Zeile 166)
- [shows the starting toolbar, hides it in a chat in every mode and restores it on the start screen](../../tests/js/agent-mode-projection.test.mjs#L196) (Zeile 196)
- [routes toolbar actions through the original controls and respects a rejected deep toggle](../../tests/js/agent-mode-projection.test.mjs#L214) (Zeile 214)
- [keeps the mode choice independent of a frozen run and synchronizes selector and settings](../../tests/js/agent-mode-projection.test.mjs#L231) (Zeile 231)
- [updates selected model marks and clears stale direct-result summaries](../../tests/js/agent-mode-projection.test.mjs#L253) (Zeile 253)
- [falls back to the controls when no run is selected](../../tests/js/agent-mode-projection.test.mjs#L266) (Zeile 266)

</details>

<a id="agent-preferences-test-mjs"></a>

## agent-preferences.test.mjs

**Quelle:** [tests/js/agent-preferences.test.mjs](../../tests/js/agent-preferences.test.mjs) · **Bereiche:** Agent, Einstellungen.

**Ebene:** jsdom-Präferenzen.

**Lauf:** 2 bestanden.

**Geprüftes Verhalten:** Tiefe und Quorummodus speichern und wiederherstellen, unbekannte Werte normalisieren; der Settings-Tab erscheint nur für Konten mit Agentzugriff.

**Grenzen und Doubles:** Lokaler Storage; keine serverseitige Policy-/Modellprüfung.

**Prüfauftrag für den Folgeaudit:** Die benannten Mock-/Integrationsgrenzen am realen Adapter prüfen; Zuordnung und offene Aufgaben stehen in der Produktmatrix.

**Direkte Codeverweise:** [static/js/agent-preferences.js](../../static/js/agent-preferences.js).

<details>
<summary>2 Testdefinitionen und ihre Quellstellen</summary>

- [saves both choices, restores them and ignores unknown stored values](../../tests/js/agent-preferences.test.mjs#L20) (Zeile 20)
- [offers the settings tab only to accounts with Agent Beta](../../tests/js/agent-preferences.test.mjs#L35) (Zeile 35)

</details>

<a id="agent-review-test-mjs"></a>

## agent-review.test.mjs

**Quelle:** [tests/js/agent-review.test.mjs](../../tests/js/agent-review.test.mjs) · **Bereiche:** Agent, Antwortdarstellung, Quellenprüfung.

**Ebene:** JavaScript-Modultest mit jsdom.

**Lauf:** 23 bestanden.

**Geprüftes Verhalten:** Vergleichszweck, Fragen/Antworten, Unterschiede, Quellenchecks und Dauer im Detailbereich; laufend/teilweise/veraltet korrekt beschriftet, Turnwechsel bereinigt. Marker nur bei passender Antwortversion und Basis; gebundene Quellenevidenz nur bei passenden Daten. Quellen aus Suche, Antwort und Vergleich zusammengeführt, Legacy-Suchquellen unterstützt; fehlendes Modell, unvollständige Prüfung und Satz-/Quellenabdeckung unterschieden; unsicherer Text entschärft. Aktualisierung 02.10.2026: Reviewstatus bleibt knapp, unvollständige/Tokenlimitantworten bleiben markiert lesbar; Copy bleibt in einer Belegzeile. Marken erscheinen einmal in Lesereihenfolge, gespeicherte/Reduced-Motion-/gefilterte Marken beachten ihre Grenzen.

**Grenzen und Doubles:** Markdown-, Marker-, Quellen- und Reader-Helfer überwiegend Doubles; einzelne Kontexte mit echtem marked/DOMPurify.

**Prüfauftrag für den Folgeaudit:** Marker- und Quellenintegration mit echten Nachbarmodulen sowie semantische Judge-Gültigkeit separat abgleichen.

**Direkte Codeverweise:** [static/js/agent-answer-actions.js](../../static/js/agent-answer-actions.js), [static/js/agent-review.js](../../static/js/agent-review.js).

**Direkte Testhelfer:** [tests/js/helpers/appWindow.mjs](../../tests/js/helpers/appWindow.mjs).

<details>
<summary>19 Testdefinitionen und ihre Quellstellen</summary>

- [explains the recorded comparison in the duration disclosure and opens its original evidence](../../tests/js/agent-review.test.mjs#L21) (Zeile 21)
- [shows the live comparison purpose while its answers and checks are still pending](../../tests/js/agent-review.test.mjs#L51) (Zeile 51)
- [keeps partial and stale reviews honest in activity insights and clears them for another turn](../../tests/js/agent-review.test.mjs#L63) (Zeile 63)
- [uses the shared markers only for the exact answer and selected comparison basis](../../tests/js/agent-review.test.mjs#L84) (Zeile 84)
- [renders bound source evidence with the shared contradiction cards and rejects stale evidence](../../tests/js/agent-review.test.mjs#L107) (Zeile 107)
- [collects chat search, answer links and comparison citations into one source view](../../tests/js/agent-review.test.mjs#L129) (Zeile 129)
- [makes search sources available without a comparison, including saved legacy activities](../../tests/js/agent-review.test.mjs#L143) (Zeile 143)
- [rejects stale comparison bindings and distinguishes incomplete results](../../tests/js/agent-review.test.mjs#L157) (Zeile 157)
- [explains a missing model without reporting a failed check, including older saved reviews](../../tests/js/agent-review.test.mjs#L187) (Zeile 187)
- [keeps %s failures distinct from unavailable comparison models](../../tests/js/agent-review.test.mjs#L217) (Zeile 217)
- [keeps a fully answered check to one line and the source report below the findings](../../tests/js/agent-review.test.mjs#L248) (Zeile 248)
- [adds no note under a checked answer and one calm sentence otherwise](../../tests/js/agent-review.test.mjs#L268) (Zeile 268)
- [speaks under the answer only when the check itself is limited (%j)](../../tests/js/agent-review.test.mjs#L280) (Zeile 280)
- [names an output limit as the reason a comparison model gave no answer](../../tests/js/agent-review.test.mjs#L295) (Zeile 295)
- [shows a model stopped mid-answer as a marked, readable incomplete answer, and a cut-off one as marked](../../tests/js/agent-review.test.mjs#L307) (Zeile 307)
- [keeps Copy in the evidence row across re-renders and hands it back when the row goes away](../../tests/js/agent-review.test.mjs#L326) (Zeile 326)
- [strokes the marks on once, in reading order, when a live answer is first checked](../../tests/js/agent-review.test.mjs#L349) (Zeile 349)
- [shows marks without animation for saved answers and reduced motion](../../tests/js/agent-review.test.mjs#L388) (Zeile 388)
- [leaves marks hidden by the highlight setting out of the reveal](../../tests/js/agent-review.test.mjs#L403) (Zeile 403)

</details>

<a id="agent-workspace-test-mjs"></a>

## agent-workspace.test.mjs

**Quelle:** [tests/js/agent-workspace.test.mjs](../../tests/js/agent-workspace.test.mjs) · **Bereiche:** Agent, Dateien und Dokumente.

**Ebene:** jsdom-Ressourcenansicht mit Fetch-/Download-Doubles.

**Lauf:** 11 bestanden.

**Geprüftes Verhalten:** Upload vor Runstart, Fehlermarkierung, Dokumentversionen am richtigen Turn, Ressourcenhook ohne Template, Konto-/Chatwechsel gegen späte Antworten, private Dateivorschau und bestätigtes Entfernen.

**Grenzen und Doubles:** API/Dateiinhalte simuliert; kein Cloudspeicher oder echter Browserdownload.

**Prüfauftrag für den Folgeaudit:** Die benannten Mock-/Integrationsgrenzen am realen Adapter prüfen; Zuordnung und offene Aufgaben stehen in der Produktmatrix.

**Direkte Codeverweise:** [static/js/agent-workspace.js](../../static/js/agent-workspace.js).

<details>
<summary>11 Testdefinitionen und ihre Quellstellen</summary>

- [renders one document card per document after the answer, grouped by version and without raw IDs](../../tests/js/agent-workspace.test.mjs#L35) (Zeile 35)
- [shows only the documents of the displayed turn under the answer](../../tests/js/agent-workspace.test.mjs#L61) (Zeile 61)
- [removes only after an explicit confirmation from the overflow menu](../../tests/js/agent-workspace.test.mjs#L76) (Zeile 76)
- [marks partly readable files and never renders file names as markup](../../tests/js/agent-workspace.test.mjs#L101) (Zeile 101)
- [describes Gmail imports of the turn by subject and sender instead of message IDs](../../tests/js/agent-workspace.test.mjs#L115) (Zeile 115)
- [coalesces refreshes to one request per 300 ms and never refreshes Google actions](../../tests/js/agent-workspace.test.mjs#L128) (Zeile 128)
- [keeps the list while uploading and shows a progress row per file](../../tests/js/agent-workspace.test.mjs#L151) (Zeile 151)
- [keeps a failed upload in the composer with its reason](../../tests/js/agent-workspace.test.mjs#L171) (Zeile 171)
- [creates the answer resources hook when the template lacks it and discards an old account response](../../tests/js/agent-workspace.test.mjs#L185) (Zeile 185)
- [keeps each archived turn's documents with its own answer](../../tests/js/agent-workspace.test.mjs#L199) (Zeile 199)
- [opens and removes a message attachment in the chat on screen](../../tests/js/agent-workspace.test.mjs#L218) (Zeile 218)

</details>

<a id="app-state-test-mjs"></a>

## app-state.test.mjs

**Quelle:** [tests/js/app-state.test.mjs](../../tests/js/app-state.test.mjs) · **Bereiche:** Frontend-Zustand.

**Ebene:** JavaScript-Modultest mit jsdom.

**Lauf:** 8 bestanden.

**Geprüftes Verhalten:** Deklarationen und Initialwerte, nur zuständiger Owner darf schreiben, unbekannte Schlüssel abgewiesen; schreibgeschützte window-Brücken; Änderungsevent mit Werten, Übernahme vorhandener Zustände und eingefrorene Definitionsliste.

**Grenzen und Doubles:** Prüft State-API und Top-Level-Brücken; kein Beleg für tiefe Unveränderlichkeit aller gespeicherten Objekte.

**Prüfauftrag für den Folgeaudit:** Direkte Mutationen verschachtelter Zustände und Konsumenten außerhalb der State-API prüfen.

**Direkte Codeverweise:** [static/js/app-state.js](../../static/js/app-state.js).

**Direkte Testhelfer:** [tests/js/helpers/appWindow.mjs](../../tests/js/helpers/appWindow.mjs).

<details>
<summary>8 Testdefinitionen und ihre Quellstellen</summary>

- [exposes every declared key with its initial value](../../tests/js/app-state.test.mjs#L18) (Zeile 18)
- [accepts a write from the owning module](../../tests/js/app-state.test.mjs#L27) (Zeile 27)
- [rejects a write from any other module and leaves the value alone](../../tests/js/app-state.test.mjs#L36) (Zeile 36)
- [rejects unknown keys on both read and write](../../tests/js/app-state.test.mjs#L46) (Zeile 46)
- [makes the window view read-only](../../tests/js/app-state.test.mjs#L55) (Zeile 55)
- [announces each change with key, owner and value](../../tests/js/app-state.test.mjs#L64) (Zeile 64)
- [adopts a value a previous script already put on window](../../tests/js/app-state.test.mjs#L76) (Zeile 76)
- [keeps the definitions frozen against tampering](../../tests/js/app-state.test.mjs#L86) (Zeile 86)

</details>

<a id="attachment-compression-test-mjs"></a>

## attachment-compression.test.mjs

**Quelle:** [tests/js/attachment-compression.test.mjs](../../tests/js/attachment-compression.test.mjs) · **Bereiche:** Anhänge, Composer.

**Ebene:** JavaScript-Modulintegration mit simuliertem Bild-/Canvasverhalten.

**Lauf:** 5 bestanden.

**Geprüftes Verhalten:** Großes Foto vor Base64-Kodierung proportional auf 1568 × 1045 und JPEG verkleinert; kleines PNG unverändert; Fallback ohne Canvas-Encoding; 15-MB-Eingangsgrenze für Bilder und 5-MB-Grenze für nicht ausreichend verkleinerbare Dateien.

**Grenzen und Doubles:** Echte Dateifeld-/Attachmentlogik, aber Bildmaße, Canvas-Ausgabe und Dateigrößen künstlich. Keine echte Bilddekodierung, Codecqualität oder Speicherlast.

**Prüfauftrag für den Folgeaudit:** Reale Fotos, Orientierung, Transparenz und Browser-Encoding gesondert zuordnen.

**Direkte Codeverweise:** [static/js/app-core.js](../../static/js/app-core.js), [static/js/app-state.js](../../static/js/app-state.js), [static/js/attachments.js](../../static/js/attachments.js).

**Direkte Testhelfer:** [tests/js/helpers/appWindow.mjs](../../tests/js/helpers/appWindow.mjs).

<details>
<summary>5 Testdefinitionen und ihre Quellstellen</summary>

- [shrinks an oversized photo before it is encoded](../../tests/js/attachment-compression.test.mjs#L106) (Zeile 106)
- [leaves a small screenshot untouched](../../tests/js/attachment-compression.test.mjs#L123) (Zeile 123)
- [still attaches the file when the browser has no canvas](../../tests/js/attachment-compression.test.mjs#L137) (Zeile 137)
- [refuses an image far above the input limit](../../tests/js/attachment-compression.test.mjs#L150) (Zeile 150)
- [keeps the tighter limit for files that cannot be shrunk](../../tests/js/attachment-compression.test.mjs#L162) (Zeile 162)

</details>

<a id="attachment-draft-generation-test-mjs"></a>

## attachment-draft-generation.test.mjs

**Quelle:** [tests/js/attachment-draft-generation.test.mjs](../../tests/js/attachment-draft-generation.test.mjs) · **Bereiche:** Anhänge, Frontend.

**Ebene:** jsdom-Dateiimport mit kontrolliertem FileReader.

**Lauf:** 5 bestanden.

**Geprüftes Verhalten:** Verspätete Imports nach Senden, Chatreset oder Kontowechsel werden verworfen; alter Import blockiert nicht das nächste Limit, normale Mehrfachimporte behalten die Reihenfolge.

**Grenzen und Doubles:** Simulierter FileReader; keine echten Dateidialoge.

**Prüfauftrag für den Folgeaudit:** Die benannten Mock-/Integrationsgrenzen am realen Adapter prüfen; Zuordnung und offene Aufgaben stehen in der Produktmatrix.

**Direkte Codeverweise:** [static/js/attachments.js](../../static/js/attachments.js).

<details>
<summary>5 Testdefinitionen und ihre Quellstellen</summary>

- [drops a late import after the saved-chat reset](../../tests/js/attachment-draft-generation.test.mjs#L59) (Zeile 59)
- [drops a late import after the draft was handed to a sent message](../../tests/js/attachment-draft-generation.test.mjs#L71) (Zeile 71)
- [drops a late import after an account change](../../tests/js/attachment-draft-generation.test.mjs#L79) (Zeile 79)
- [a stale import neither blocks nor leaks into the next draft's limit](../../tests/js/attachment-draft-generation.test.mjs#L87) (Zeile 87)
- [keeps order and completes a normal multi-file import](../../tests/js/attachment-draft-generation.test.mjs#L106) (Zeile 106)

</details>

<a id="bookmark-attachments-test-mjs"></a>

## bookmark-attachments.test.mjs

**Quelle:** [tests/js/bookmark-attachments.test.mjs](../../tests/js/bookmark-attachments.test.mjs) · **Bereiche:** Anhänge, Bookmarks und Verlauf.

**Ebene:** Ausgeführter Firebase-Ausschnitt und JavaScript-Modultests mit jsdom.

**Lauf:** 6 bestanden.

**Geprüftes Verhalten:** Aktueller Turn gewinnt gegenüber Dokumentanhängen, frühere Turnanhänge bleiben in Historie, Legacy-Dokument als Fallback; gespeicherte Chips nur lesbar, CSV als Text, neue Frage bereinigt alte Anhänge.

**Grenzen und Doubles:** materializeConversationBookmark aus Firebase-Quellcode ausgeschnitten; echte app-core-/attachments-Skripte, kein Firebase-SDK oder Backend.

**Prüfauftrag für den Folgeaudit:** Persistenzvertrag für mehrere Turns und Legacy-Migration mit API-Tests abgleichen.

**Direkte Codeverweise:** [static/firebase.js](../../static/firebase.js), [static/js/app-core.js](../../static/js/app-core.js), [static/js/attachments.js](../../static/js/attachments.js).

**Direkte Testhelfer:** [tests/js/helpers/appWindow.mjs](../../tests/js/helpers/appWindow.mjs).

<details>
<summary>6 Testdefinitionen und ihre Quellstellen</summary>

- [keeps the current turn's files instead of the document's](../../tests/js/bookmark-attachments.test.mjs#L83) (Zeile 83)
- [shows the files of the last question when that is the one with files](../../tests/js/bookmark-attachments.test.mjs#L101) (Zeile 101)
- [still reads the document for chats saved before turns carried files](../../tests/js/bookmark-attachments.test.mjs#L112) (Zeile 112)
- [renders a read-only chip for the restored question](../../tests/js/bookmark-attachments.test.mjs#L123) (Zeile 123)
- [gives a .csv the type the server also knows](../../tests/js/bookmark-attachments.test.mjs#L139) (Zeile 139)
- [does not carry the files into the next question](../../tests/js/bookmark-attachments.test.mjs#L156) (Zeile 156)

</details>

<a id="bookmark-pending-state-test-mjs"></a>

## bookmark-pending-state.test.mjs

**Quelle:** [tests/js/bookmark-pending-state.test.mjs](../../tests/js/bookmark-pending-state.test.mjs) · **Bereiche:** Bookmarks und Verlauf, Frontend-Zustand.

**Ebene:** Ausgeführte Firebase-Ausschnitte mit Funktions-Doubles/jsdom.

**Lauf:** 4 bestanden.

**Geprüftes Verhalten:** Bookmark bleibt bis Laufende und Abschluss aller Writes gesperrt; kein kurzzeitiger Readyzustand zwischen Modellfanout und Autokonsens; vorhandener Bookmark nach Followup ohne neue Speicherung wiederhergestellt; Pendingzeile mit aria-disabled, Spinner und ohne Löschaktion.

**Grenzen und Doubles:** Session- und DOM-Funktionen ausgeschnitten; Auth, Schreiben und Renderübergänge simuliert, keine vollständige Firebase-Modulinitialisierung.

**Prüfauftrag für den Folgeaudit:** Netzwerkfehler und Kontenwechsel zusammen mit realer Schreibqueue prüfen.

**Direkte Codeverweise:** [static/firebase.js](../../static/firebase.js).

**Direkte Testhelfer:** [tests/js/helpers/appWindow.mjs](../../tests/js/helpers/appWindow.mjs).

<details>
<summary>4 Testdefinitionen und ihre Quellstellen</summary>

- [stays disabled until both the run and its persistence write finish](../../tests/js/bookmark-pending-state.test.mjs#L45) (Zeile 45)
- [does not flash ready between model fan-out and auto-consensus](../../tests/js/bookmark-pending-state.test.mjs#L64) (Zeile 64)
- [restores an existing conversation bookmark if a follow-up saves nothing](../../tests/js/bookmark-pending-state.test.mjs#L82) (Zeile 82)
- [renders an inaccessible loading row with a bookmark-frame spinner](../../tests/js/bookmark-pending-state.test.mjs#L95) (Zeile 95)

</details>

<a id="bookmark-source-check-test-mjs"></a>

## bookmark-source-check.test.mjs

**Quelle:** [tests/js/bookmark-source-check.test.mjs](../../tests/js/bookmark-source-check.test.mjs) · **Bereiche:** Bookmarks und Verlauf, Quellenprüfung.

**Ebene:** Ausgeführter Firebase-Ausschnitt mit jsdom.

**Lauf:** 2 bestanden.

**Geprüftes Verhalten:** Auch terminaler leerer Quellenstub wird beobachtet und hydratisiert; Update betrifft gespeicherten Turn, Quellbookmark und selektierte Basis; Authgeneration gebunden; Wechsel der Bookmarkansicht invalidiert alten Observer.

**Grenzen und Doubles:** sourceVerification und Registry ersetzt; observeBookmarkSourceCheck als Quellcodeausschnitt, kein echter Pollrequest oder Datenbankzugriff.

**Prüfauftrag für den Folgeaudit:** Vollständiges Öffnen, Nachladen und Ansichtswechsel mit tatsächlichem Observer abgleichen.

**Direkte Codeverweise:** [static/firebase.js](../../static/firebase.js).

**Direkte Testhelfer:** [tests/js/helpers/appWindow.mjs](../../tests/js/helpers/appWindow.mjs).

<details>
<summary>2 Testdefinitionen und ihre Quellstellen</summary>

- [hydrates even a terminal empty stub and updates only its saved turn and basis](../../tests/js/bookmark-source-check.test.mjs#L20) (Zeile 20)
- [invalidates the old observer when another bookmark or live run replaces its view](../../tests/js/bookmark-source-check.test.mjs#L39) (Zeile 39)

</details>

<a id="bookmark-write-queue-test-mjs"></a>

## bookmark-write-queue.test.mjs

**Quelle:** [tests/js/bookmark-write-queue.test.mjs](../../tests/js/bookmark-write-queue.test.mjs) · **Bereiche:** Bookmarks und Verlauf, Nebenläufigkeit.

**Ebene:** Ausgeführter Firebase-Funktionsausschnitt in Node.

**Lauf:** 3 bestanden.

**Geprüftes Verhalten:** Writes desselben Bookmarks laufen in Aufrufreihenfolge, Konsenswrite folgt auch nach fehlgeschlagenem Modellwrite; dieselbe Kontenressource bleibt über rasche Authgenerationswechsel serialisiert.

**Grenzen und Doubles:** Promisegates statt Netzwerk; Authgültigkeit immer positiv simuliert; kein SDK oder persistierter Inhalt geprüft.

**Prüfauftrag für den Folgeaudit:** Abgewiesene alte Authgeneration, unterschiedliche Ressourcen und Backend-Idempotenz zusammenführen.

**Direkte Codeverweise:** [static/firebase.js](../../static/firebase.js).

**Direkte Testhelfer:** [tests/js/helpers/appWindow.mjs](../../tests/js/helpers/appWindow.mjs).

<details>
<summary>3 Testdefinitionen und ihre Quellstellen</summary>

- [runs model and consensus writes for one bookmark in invocation order](../../tests/js/bookmark-write-queue.test.mjs#L21) (Zeile 21)
- [still runs the authoritative consensus write after a failed model write](../../tests/js/bookmark-write-queue.test.mjs#L43) (Zeile 43)
- [serializes the same account resource across rapid auth generations](../../tests/js/bookmark-write-queue.test.mjs#L59) (Zeile 59)

</details>

<a id="chat-scroll-test-mjs"></a>

## chat-scroll.test.mjs

**Quelle:** [tests/js/chat-scroll.test.mjs](../../tests/js/chat-scroll.test.mjs) · **Bereiche:** Scrollen und Navigation, Streaming und Wiederherstellung.

**Ebene:** JavaScript-Modulintegration mit simulierten Scrollmaßen und jsdom.

**Lauf:** 12 bestanden.

**Geprüftes Verhalten:** Leseposition bei schrumpfender Aktivität erhalten; Follow endet mit Antwort; gespeicherte Agent-/Konsensgespräche mit abbrechbarem Sprung; Agent folgt Wachstum, Konsens bleibt nach einmaligem Sprung stehen. Leserinteraktion, Tastaturrückkehr, Touchgeste, Run-/Ansichts-/Kontenwechsel, Textauswahl/Dialog/Vergleich stoppen Automatik; Reduced Motion und Viewport-/Composeränderungen.

**Grenzen und Doubles:** scrollTo, Scrollposition, Geometrie und Frames im Harness simuliert; kein Nachweis nativen Scrollanchorings oder tatsächlicher Mobilgeometrie.

**Prüfauftrag für den Folgeaudit:** Dieselben Verträge mit realen Layoutänderungen, Touch und langen Antworten abgleichen.

**Direkte Codeverweise:** [static/js/app-core.js](../../static/js/app-core.js), [static/js/chat-scroll.js](../../static/js/chat-scroll.js).

**Direkte Testhelfer:** [tests/js/helpers/appWindow.mjs](../../tests/js/helpers/appWindow.mjs).

<details>
<summary>10 Testdefinitionen und ihre Quellstellen</summary>

- [keeps the reading position when offscreen activity shrinks, including native anchoring](../../tests/js/chat-scroll.test.mjs#L36) (Zeile 36)
- [ends automatic following when the response finishes](../../tests/js/chat-scroll.test.mjs#L58) (Zeile 58)
- [opens a saved %s conversation with one cancellable smooth jump](../../tests/js/chat-scroll.test.mjs#L67) (Zeile 67)
- [smoothly reaches the end and follows growing agent output despite a hidden pending bubble](../../tests/js/chat-scroll.test.mjs#L85) (Zeile 85)
- [keeps consensus still after a single jump, including fast deltas and reduced motion: %s](../../tests/js/chat-scroll.test.mjs#L99) (Zeile 99)
- [gives the reader control even before the first frame, then offers a keyboard usable return](../../tests/js/chat-scroll.test.mjs#L123) (Zeile 123)
- [never resumes from layout scrolls and cancels on a different run, saved view or account](../../tests/js/chat-scroll.test.mjs#L142) (Zeile 142)
- [interrupts a finger gesture and resumes only when swiping back to the end](../../tests/js/chat-scroll.test.mjs#L159) (Zeile 159)
- [respects reduced motion and viewport/composer changes without scrolling upwards](../../tests/js/chat-scroll.test.mjs#L176) (Zeile 176)
- [stops for text selection, dialogs and direct comparison](../../tests/js/chat-scroll.test.mjs#L189) (Zeile 189)

</details>

<a id="claim-coverage-states-test-mjs"></a>

## claim-coverage-states.test.mjs

**Quelle:** [tests/js/claim-coverage-states.test.mjs](../../tests/js/claim-coverage-states.test.mjs) · **Bereiche:** Antwortdarstellung, Konsens und Unterschiede.

**Ebene:** JavaScript-Modulintegration mit jsdom.

**Lauf:** 9 bestanden.

**Geprüftes Verhalten:** Claims in Tabellenzellen ohne Header-Markierung; einstimmig, geteilt und dünn unterschiedlich; dünne Evidenz mit Strich statt irreführender Quote, unterstützte mit Verhältnis. Zähler standardmäßig aus, Tastaturdetail und gespeicherte Präferenz; Legacyzustand aus Zählwerten; Widerspruch überschreibt dünne Markierung; Zustimmung als kein Wahrheitsbeweis erklärt.

**Grenzen und Doubles:** Echte Anchor-/Insightsmodule mit vorgegebenen Analysedaten und DOM; keine fachliche Richtigkeit der zugrunde liegenden Claims.

**Prüfauftrag für den Folgeaudit:** Vollständigkeit und Semantik der vom Backend gelieferten Claims getrennt bewerten.

**Direkte Codeverweise:** [static/js/consensus-anchor.js](../../static/js/consensus-anchor.js), [static/js/consensus-insights.js](../../static/js/consensus-insights.js).

**Direkte Testhelfer:** [tests/js/helpers/appWindow.mjs](../../tests/js/helpers/appWindow.mjs).

<details>
<summary>9 Testdefinitionen und ihre Quellstellen</summary>

- [renders claims and contradictions inside separate table cells](../../tests/js/claim-coverage-states.test.mjs#L71) (Zeile 71)
- [marks a supported, a split and a thin sentence differently](../../tests/js/claim-coverage-states.test.mjs#L94) (Zeile 94)
- [shows a dash instead of a ratio when too few models addressed it](../../tests/js/claim-coverage-states.test.mjs#L112) (Zeile 112)
- [keeps the ratio on a supported sentence](../../tests/js/claim-coverage-states.test.mjs#L126) (Zeile 126)
- [defaults counts off and keeps claim details accessible by keyboard](../../tests/js/claim-coverage-states.test.mjs#L137) (Zeile 137)
- [restores an explicit opt-in](../../tests/js/claim-coverage-states.test.mjs#L159) (Zeile 159)
- [derives the state from the counts for snapshots without the field](../../tests/js/claim-coverage-states.test.mjs#L165) (Zeile 165)
- [lets a contradiction override the thin mark on the same sentence](../../tests/js/claim-coverage-states.test.mjs#L177) (Zeile 177)
- [says in the detail card that agreement is not proof](../../tests/js/claim-coverage-states.test.mjs#L198) (Zeile 198)

</details>

<a id="claim-mark-joins-test-mjs"></a>

## claim-mark-joins.test.mjs

**Quelle:** [tests/js/claim-mark-joins.test.mjs](../../tests/js/claim-mark-joins.test.mjs) · **Bereiche:** Consensus, Frontend.

**Ebene:** jsdom-Claim-Markierung.

**Lauf:** 1 bestanden.

**Geprüftes Verhalten:** Geteilte Satzmarkierungen bewahren Text und innere Verbindungen; nur äußere Enden erhalten Kantenklassen.

**Grenzen und Doubles:** DOM-Klassen statt Pixel-/Browserlayout.

**Prüfauftrag für den Folgeaudit:** Die benannten Mock-/Integrationsgrenzen am realen Adapter prüfen; Zuordnung und offene Aufgaben stehen in der Produktmatrix.

**Direkte Codeverweise:** [static/js/consensus-anchor.js](../../static/js/consensus-anchor.js), [static/js/consensus-insights.js](../../static/js/consensus-insights.js).

<details>
<summary>1 Testdefinitionen und ihre Quellstellen</summary>

- [keeps inner joins of a split sentence flush and pads only its outer ends](../../tests/js/claim-mark-joins.test.mjs#L11) (Zeile 11)

</details>

<a id="composer-attachments-test-mjs"></a>

## composer-attachments.test.mjs

**Quelle:** [tests/js/composer-attachments.test.mjs](../../tests/js/composer-attachments.test.mjs) · **Bereiche:** Anhänge, Composer.

**Ebene:** JavaScript-Modulintegration mit jsdom.

**Lauf:** 7 bestanden.

**Geprüftes Verhalten:** Dasselbe Anhangstableau wechselt zwischen Toolbar, Agentcomposer und neuem Vergleich ohne Duplikate oder Fokusverlust; gesendete Dateien werden schreibgeschützte Nachrichtenanhänge, Draft geleert und bei Fehler sichtbar wiederhergestellt; Vorschau und Entfernen getrennt, Fokus folgt verfügbarer Aktion. Aktualisierung 02.10.2026: Dasselbe Tray erhält Fokus bei Moduswechsel; Upload-/Lesefehler am Chip, gespeicherte Datei öffnen/downloaden und nur bestätigt entfernen.

**Grenzen und Doubles:** Echte attachments-/agent-mode-Skripte mit Composer-/Umgebungsdoubles und vorgegebenen Dateien; kein Upload oder Browserlayout.

**Prüfauftrag für den Folgeaudit:** Fehler nach echter Anfrage und Responsivität des vollständigen Composers abgleichen.

**Direkte Codeverweise:** [static/js/agent-mode.js](../../static/js/agent-mode.js), [static/js/attachments.js](../../static/js/attachments.js), [static/js/run-mode.js](../../static/js/run-mode.js).

**Direkte Testhelfer:** [tests/js/helpers/appWindow.mjs](../../tests/js/helpers/appWindow.mjs).

<details>
<summary>7 Testdefinitionen und ihre Quellstellen</summary>

- [moves the same tray and focused control between the start toolbar, a chat in any mode and a new comparison](../../tests/js/composer-attachments.test.mjs#L43) (Zeile 43)
- [hands sent files to the message, clears the draft and restores failed drafts in the visible composer](../../tests/js/composer-attachments.test.mjs#L68) (Zeile 68)
- [separates preview from removal and returns focus to the next available action](../../tests/js/composer-attachments.test.mjs#L86) (Zeile 86)
- [shows an Agent upload failure on the pending chip and clears it again](../../tests/js/composer-attachments.test.mjs#L105) (Zeile 105)
- [marks sent Agent files that were only partly readable](../../tests/js/composer-attachments.test.mjs#L116) (Zeile 116)
- [opens a stored Agent file from its sent message with download and a confirmed removal](../../tests/js/composer-attachments.test.mjs#L126) (Zeile 126)
- [shows why a stored file could not be opened](../../tests/js/composer-attachments.test.mjs#L154) (Zeile 154)

</details>

<a id="composer-quote-test-mjs"></a>

## composer-quote.test.mjs

**Quelle:** [tests/js/composer-quote.test.mjs](../../tests/js/composer-quote.test.mjs) · **Bereiche:** Composer.

**Ebene:** JavaScript-Modultest mit jsdom.

**Lauf:** 11 bestanden.

**Geprüftes Verhalten:** Leerzustand, Setzen, Whitespace-/CRLF-Normalisierung und 1200-Zeichen-Kappung mit Ellipse; Frage vor Zitat, Ersatzfrage bei leerer Eingabe, unveränderte Frage ohne Zitat; Leeren, Entfernen mit Fokus und fehlendes Composer-DOM.

**Grenzen und Doubles:** Isoliertes composer-quote-Modul; Versand und Konten-/Turnbindung nicht in dieser Datei.

**Prüfauftrag für den Folgeaudit:** Zitate in Agent-/Konsens-Versand, Abbruch und Draftwiederherstellung zuordnen.

**Direkte Codeverweise:** [static/js/composer-quote.js](../../static/js/composer-quote.js).

**Direkte Testhelfer:** [tests/js/helpers/appWindow.mjs](../../tests/js/helpers/appWindow.mjs).

<details>
<summary>11 Testdefinitionen und ihre Quellstellen</summary>

- [starts empty and hidden](../../tests/js/composer-quote.test.mjs#L35) (Zeile 35)
- [shows the passage in the composer once set](../../tests/js/composer-quote.test.mjs#L41) (Zeile 41)
- [collapses runs of spaces and caps blank lines at one](../../tests/js/composer-quote.test.mjs#L51) (Zeile 51)
- [normalizes CRLF so a pasted passage does not carry \r into the run](../../tests/js/composer-quote.test.mjs#L60) (Zeile 60)
- [truncates beyond the cap with an ellipsis](../../tests/js/composer-quote.test.mjs#L66) (Zeile 66)
- [puts the typed question first and the passage below it](../../tests/js/composer-quote.test.mjs#L74) (Zeile 74)
- [asks for a comment when the user typed nothing](../../tests/js/composer-quote.test.mjs#L82) (Zeile 82)
- [returns the question untouched when there is no quote](../../tests/js/composer-quote.test.mjs#L90) (Zeile 90)
- [hides the box again on clear](../../tests/js/composer-quote.test.mjs#L95) (Zeile 95)
- [clears through the remove button and hands focus back to the field](../../tests/js/composer-quote.test.mjs#L103) (Zeile 103)
- [survives a page that has no composer markup at all](../../tests/js/composer-quote.test.mjs#L112) (Zeile 112)

</details>

<a id="consensus-anchor-test-mjs"></a>

## consensus-anchor.test.mjs

**Quelle:** [tests/js/consensus-anchor.test.mjs](../../tests/js/consensus-anchor.test.mjs) · **Bereiche:** Konsens und Unterschiede, Markdown und Darstellung.

**Ebene:** JavaScript-Modultest mit jsdom.

**Lauf:** 25 bestanden.

**Geprüftes Verhalten:** Normalisierung von Groß-/Kleinschreibung, Anführungszeichen und Leerraum; rohe Offsets auch bei Unicode-Erweiterung; Mehrfachtreffer, leere/fehlende Passage und Zeilenumbrüche. Quellen-Tags entfernen, Interpunktion, priorisierte Vollpassage vor Kurzfallback, Ellipsen und Deduplizierung; DOM-Verankerung ohne Quellenchips und mit Mathematikmarkup; Satzgrenzen bei Währungs-/Mengenabkürzungen. Aktualisierung 02.10.2026: Deutsches Ordinaldatum bleibt innerhalb seines Satzes.

**Grenzen und Doubles:** Vorgegebene Texte/DOM inklusive vorbereiteter Mathematikdarstellung; keine Garantie für jede Sprache oder mehrdeutige reale Antwort.

**Prüfauftrag für den Folgeaudit:** Mehrdeutige Passagen, internationale Satzgrenzen und reale Renderer-Integration abgleichen.

**Direkte Codeverweise:** [static/js/consensus-anchor.js](../../static/js/consensus-anchor.js), [static/js/math-render.js](../../static/js/math-render.js).

**Direkte Testhelfer:** [tests/js/helpers/appWindow.mjs](../../tests/js/helpers/appWindow.mjs).

<details>
<summary>21 Testdefinitionen und ihre Quellstellen</summary>

- [folds case, curly quotes and runs of whitespace](../../tests/js/consensus-anchor.test.mjs#L34) (Zeile 34)
- [treats every quote flavour as the same character](../../tests/js/consensus-anchor.test.mjs#L40) (Zeile 40)
- [survives null and undefined](../../tests/js/consensus-anchor.test.mjs#L47) (Zeile 47)
- [maps a normalized needle back onto the raw offsets](../../tests/js/consensus-anchor.test.mjs#L59) (Zeile 59)
- [keeps valid DOM offsets after Unicode case expansion: %s](../../tests/js/consensus-anchor.test.mjs#L68) (Zeile 68)
- [finds every non-overlapping occurrence](../../tests/js/consensus-anchor.test.mjs#L85) (Zeile 85)
- [returns nothing for an empty needle instead of matching everywhere](../../tests/js/consensus-anchor.test.mjs#L98) (Zeile 98)
- [returns null when the passage is not there](../../tests/js/consensus-anchor.test.mjs#L103) (Zeile 103)
- [matches across a line break, because the source wrapped mid-sentence](../../tests/js/consensus-anchor.test.mjs#L107) (Zeile 107)
- [offers a tag-free variant, because the rendered DOM has no \[S1\]](../../tests/js/consensus-anchor.test.mjs#L123) (Zeile 123)
- [pulls the punctuation back to the word when the tag is dropped](../../tests/js/consensus-anchor.test.mjs#L130) (Zeile 130)
- [ranks full passages ahead of the eight-word fallbacks](../../tests/js/consensus-anchor.test.mjs#L138) (Zeile 138)
- [does not shorten a passage that is already short](../../tests/js/consensus-anchor.test.mjs#L149) (Zeile 149)
- [strips leading and trailing ellipses from a clipped quote](../../tests/js/consensus-anchor.test.mjs#L153) (Zeile 153)
- [emits no duplicates when markup makes the variants identical](../../tests/js/consensus-anchor.test.mjs#L159) (Zeile 159)
- [finds the passage inside a rendered answer and skips the source chips](../../tests/js/consensus-anchor.test.mjs#L167) (Zeile 167)
- [finds a sentence whose formula is already rendered by KaTeX](../../tests/js/consensus-anchor.test.mjs#L188) (Zeile 188)
- [returns null rather than guessing when the passage is absent](../../tests/js/consensus-anchor.test.mjs#L210) (Zeile 210)
- [does not treat currency abbreviations as sentence endings](../../tests/js/consensus-anchor.test.mjs#L221) (Zeile 221)
- [keeps a German ordinal date inside its sentence](../../tests/js/consensus-anchor.test.mjs#L235) (Zeile 235)
- [still recognizes a quantity abbreviation at a real sentence end](../../tests/js/consensus-anchor.test.mjs#L243) (Zeile 243)

</details>

<a id="consensus-coverage-verdict-test-mjs"></a>

## consensus-coverage-verdict.test.mjs

**Quelle:** [tests/js/consensus-coverage-verdict.test.mjs](../../tests/js/consensus-coverage-verdict.test.mjs) · **Bereiche:** Antwortdarstellung, Konsens und Unterschiede.

**Ebene:** JavaScript-Modulintegration mit jsdom.

**Lauf:** 3 bestanden.

**Geprüftes Verhalten:** Unzureichende Evidenz zeigt keinen beruhigenden Score/Gauge; gemessene Übereinstimmung und Claimabdeckung getrennt; Legacy-Snapshots ohne Abdeckungsmetadaten behalten alte Darstellung.

**Grenzen und Doubles:** Vorgegebene Score-/Coveragemetadaten; keine Prüfung ihrer Berechnung.

**Prüfauftrag für den Folgeaudit:** Backend-Schwellenwerte und unvollständige Analysedaten als gemeinsamen Vertrag zuordnen.

**Direkte Codeverweise:** [static/js/consensus-anchor.js](../../static/js/consensus-anchor.js), [static/js/consensus-insights.js](../../static/js/consensus-insights.js).

**Direkte Testhelfer:** [tests/js/helpers/appWindow.mjs](../../tests/js/helpers/appWindow.mjs).

<details>
<summary>3 Testdefinitionen und ihre Quellstellen</summary>

- [shows an explicit unavailable verdict instead of a reassuring score](../../tests/js/consensus-coverage-verdict.test.mjs#L17) (Zeile 17)
- [keeps measured agreement and coverage separate](../../tests/js/consensus-coverage-verdict.test.mjs#L24) (Zeile 24)
- [retains the legacy verdict for snapshots without coverage metadata](../../tests/js/consensus-coverage-verdict.test.mjs#L30) (Zeile 30)

</details>

<a id="consensus-marker-visibility-test-mjs"></a>

## consensus-marker-visibility.test.mjs

**Quelle:** [tests/js/consensus-marker-visibility.test.mjs](../../tests/js/consensus-marker-visibility.test.mjs) · **Bereiche:** Barrierefreiheit, Konsens und Unterschiede.

**Ebene:** JavaScript-Modulintegration mit jsdom.

**Lauf:** 14 bestanden.

**Geprüftes Verhalten:** Maus nach Rendering aktiviert Hover, Touch bleibt ruhig; Fehler optionaler Quellenhooks zerstören Unterschiede nicht. Persistente Filter all/contradictions/concerns/critical/none für aktuelle und historische Marker/Fallbacks; versteckte Marker verlieren interaktive Rollen und Tastaturzugang, Analyse bleibt erhalten. Minder-/Hauptwidersprüche getrennt; Zähler-, Settings- und Ansichtswechsel, Legacypräferenz, ungültige Werte und Storagefehler; neuer Browser startet mit concerns, explizites all bleibt.

**Grenzen und Doubles:** Echte Anchor-/Insightslogik, simuliertes DOM und Pointer-/Storagezustände; Sichtbarkeit über Klassen/Attribute statt tatsächlicher CSS- oder Assistenztechnikprüfung.

**Prüfauftrag für den Folgeaudit:** Browserdarstellung, Tastaturreihenfolge und Screenreaderwirkung den vorhandenen E2E-Fällen zuordnen.

**Direkte Codeverweise:** [static/js/consensus-anchor.js](../../static/js/consensus-anchor.js), [static/js/consensus-insights.js](../../static/js/consensus-insights.js).

**Direkte Testhelfer:** [tests/js/helpers/appWindow.mjs](../../tests/js/helpers/appWindow.mjs).

<details>
<summary>10 Testdefinitionen und ihre Quellstellen</summary>

- [enables passage hover for a mouse attached after rendering, while touch stays quiet](../../tests/js/consensus-marker-visibility.test.mjs#L57) (Zeile 57)
- [keeps contradiction cards and sentence marks when advisory source hooks fail](../../tests/js/consensus-marker-visibility.test.mjs#L75) (Zeile 75)
- [uses the persistent settings selection without removing the analysis](../../tests/js/consensus-marker-visibility.test.mjs#L83) (Zeile 83)
- [restores the hidden preference before a new answer is rendered](../../tests/js/consensus-marker-visibility.test.mjs#L105) (Zeile 105)
- [applies %s before a previous answer enters the conversation](../../tests/js/consensus-marker-visibility.test.mjs#L156) (Zeile 156)
- [distinguishes minor contradictions from grey emphasis and restores keyboard access](../../tests/js/consensus-marker-visibility.test.mjs#L200) (Zeile 200)
- [keeps filters across settings changes, counts changes and later stored answers](../../tests/js/consensus-marker-visibility.test.mjs#L222) (Zeile 222)
- [restores saved filters and the existing hidden preference](../../tests/js/consensus-marker-visibility.test.mjs#L238) (Zeile 238)
- [falls back for invalid values and retains the session choice when writes fail](../../tests/js/consensus-marker-visibility.test.mjs#L248) (Zeile 248)
- [defaults new browsers to disagreements and concerns while preserving explicit all](../../tests/js/consensus-marker-visibility.test.mjs#L263) (Zeile 263)

</details>

<a id="consensus-recovery-test-mjs"></a>

## consensus-recovery.test.mjs

**Quelle:** [tests/js/consensus-recovery.test.mjs](../../tests/js/consensus-recovery.test.mjs) · **Bereiche:** Konsens und Unterschiede, Streaming und Wiederherstellung.

**Ebene:** JavaScript-Modulintegration mit Request-/Stream-Doubles.

**Lauf:** 6 bestanden.

**Geprüftes Verhalten:** Nach Transportfehler gespeicherten fertigen Turn per authentifiziertem GET übernehmen, ohne neue Generierung, Vote oder Save; bei gespeichertem Fehlschlag Teiltext und Gesprächssperre erhalten. Renderfehler lösen keine Transportrecovery aus; Pendingpolling auf drei Requests begrenzt; Benutzerabbruch pollt nicht; Antwort nach Logout verworfen.

**Grenzen und Doubles:** Echte Registry-/Konsensmodule, aber SSE wirft vorgegebenen Fehler und Fetch liefert künstliche Turnzustände; keine reale Verbindung oder Datenbank.

**Prüfauftrag für den Folgeaudit:** Persistenzzeitpunkt, Disconnect und Wiederholung mit Backend-Turnvertrag abgleichen.

**Direkte Codeverweise:** [static/js/consensus-run.js](../../static/js/consensus-run.js), [static/js/run-registry.js](../../static/js/run-registry.js).

**Direkte Testhelfer:** [tests/js/helpers/appWindow.mjs](../../tests/js/helpers/appWindow.mjs).

<details>
<summary>6 Testdefinitionen und ihre Quellstellen</summary>

- [recovers a committed turn through GET without another generation, vote or save](../../tests/js/consensus-recovery.test.mjs#L40) (Zeile 40)
- [keeps partial text and the conversation fence when the stored turn failed](../../tests/js/consensus-recovery.test.mjs#L55) (Zeile 55)
- [does not hide rendering defects with transport recovery](../../tests/js/consensus-recovery.test.mjs#L66) (Zeile 66)
- [bounds pending-turn polling and never treats a partial stream as complete](../../tests/js/consensus-recovery.test.mjs#L74) (Zeile 74)
- [does not poll when the user cancels](../../tests/js/consensus-recovery.test.mjs#L85) (Zeile 85)
- [discards a recovery response after logout](../../tests/js/consensus-recovery.test.mjs#L97) (Zeile 97)

</details>

<a id="contradiction-source-verification-test-mjs"></a>

## contradiction-source-verification.test.mjs

**Quelle:** [tests/js/contradiction-source-verification.test.mjs](../../tests/js/contradiction-source-verification.test.mjs) · **Bereiche:** Barrierefreiheit, Konsens und Unterschiede, Quellenprüfung.

**Ebene:** JavaScript-Modultest mit jsdom; teilweise Navigation mit echten Nachbarmodulen.

**Lauf:** 53 bestanden.

**Geprüftes Verhalten:** Ergebnisnavigation öffnet passendes Unterschiedsdetail, fokussiert und markiert zeitlich begrenzt; Fallbackreport/Reader, Reduced Motion und Priorität ausgeschlossener Checks. Attribuierte Originalbelege, sichere Links, unveränderter Konsens und Snapshot; Ergebnis nur bei passender Antwort, Position, Frage und Anchor. Stream-/historische Container, paginierte Deduplizierung und Versionsschutz. Disabled, fehlgeschlagen, Budgetauslassung, technisch ausgeschlossen, abgelehnter Schluss, unerreichbare Quelle und laufend unterschieden; Legacyanzeigen. Ablehnungsdiagnosen mit sicherer Quellen-/Modellzuordnung, unbekannte/unsichere Daten unterdrückt, Liste auf zwölf begrenzt, Fallbackherkunft; keine verworfenen Zitate trotz widersprüchlichem checked-Flag. Arbeits-/Persistenz-/Interruptfehler und positive, unklare sowie unvollständige Zustände. Aktualisierung 02.10.2026: Stance-Fallback bindet an passende Karte, geänderte Positionen übernehmen keinen alten Befund.

**Grenzen und Doubles:** Echte source-verification-Logik, optional progress/reader; künstliche Snapshots und Fetch/Timer/Scroll-Doubles. Prüft Darstellung und Bindung, nicht Abruf oder Wahrheit des Belegs.

**Prüfauftrag für den Folgeaudit:** Alle Backendzustände und Versionen mit UIrepräsentation sowie realem Nachladen abgleichen.

**Direkte Codeverweise:** [static/js/consensus-progress.js](../../static/js/consensus-progress.js), [static/js/model-answer-reader.js](../../static/js/model-answer-reader.js), [static/js/source-verification.js](../../static/js/source-verification.js).

**Direkte Testhelfer:** [tests/js/helpers/appWindow.mjs](../../tests/js/helpers/appWindow.mjs).

<details>
<summary>33 Testdefinitionen und ihre Quellstellen</summary>

- [opens the checked explanation in Differences with only the result highlighted and focused](../../tests/js/contradiction-source-verification.test.mjs#L34) (Zeile 34)
- [prioritizes an excluded check among several cards and leaves other cards collapsed](../../tests/js/contradiction-source-verification.test.mjs#L50) (Zeile 50)
- [keeps the cue through polling, expires it, retriggers it and clears it on a different answer](../../tests/js/contradiction-source-verification.test.mjs#L65) (Zeile 65)
- [opens the report when no per-contradiction result exists (schema %s)](../../tests/js/contradiction-source-verification.test.mjs#L88) (Zeile 88)
- [opens the relevant disclosure when the reader is unavailable](../../tests/js/contradiction-source-verification.test.mjs#L103) (Zeile 103)
- [shows attributed verbatim evidence inside the contradiction, never a verified-answer badge](../../tests/js/contradiction-source-verification.test.mjs#L115) (Zeile 115)
- [distinguishes empty, disabled, failed and budget omissions](../../tests/js/contradiction-source-verification.test.mjs#L132) (Zeile 132)
- [does not show a substantive verdict without attributed evidence or for a different answer](../../tests/js/contradiction-source-verification.test.mjs#L143) (Zeile 143)
- [rejects changed positions, anchor or factual question in restored Differences](../../tests/js/contradiction-source-verification.test.mjs#L151) (Zeile 151)
- [binds a side located by its stance to its card, but never a changed stance](../../tests/js/contradiction-source-verification.test.mjs#L162) (Zeile 162)
- [reattaches after streamed Differences rendering, and clears old results on run changes](../../tests/js/contradiction-source-verification.test.mjs#L173) (Zeile 173)
- [keeps evidence on a historical card when the reader moves its container](../../tests/js/contradiction-source-verification.test.mjs#L184) (Zeile 184)
- [deduplicates paginated findings by contradiction identity and rejects mismatched versions](../../tests/js/contradiction-source-verification.test.mjs#L194) (Zeile 194)
- [shows a technical exclusion on the red card and never claims no contradictions exist](../../tests/js/contradiction-source-verification.test.mjs#L218) (Zeile 218)
- [counts excluded contradictions in the displayed total for a mixed result](../../tests/js/contradiction-source-verification.test.mjs#L229) (Zeile 229)
- [shows classification and technical reasons together without turning them into a source verdict](../../tests/js/contradiction-source-verification.test.mjs#L235) (Zeile 235)
- [derives only display explanations for old terminal v4 snapshots with missing quote matches](../../tests/js/contradiction-source-verification.test.mjs#L246) (Zeile 246)
- [does not attach exclusions to different raw positions, question, anchor, or answer](../../tests/js/contradiction-source-verification.test.mjs#L258) (Zeile 258)
- [explains an excluded contradiction in the public fallback when no Differences panel exists](../../tests/js/contradiction-source-verification.test.mjs#L268) (Zeile 268)
- [describes the rejected source check as unresolved in the footer, report and detail](../../tests/js/contradiction-source-verification.test.mjs#L280) (Zeile 280)
- [counts multiple rejected checks without implying no source comparison was attempted](../../tests/js/contradiction-source-verification.test.mjs#L294) (Zeile 294)
- [separates rejected conclusions, unavailable sources and omitted checks in a mixed result](../../tests/js/contradiction-source-verification.test.mjs#L301) (Zeile 301)
- [keeps running checks and inaccessible sources distinct from rejected conclusions](../../tests/js/contradiction-source-verification.test.mjs#L310) (Zeile 310)
- [shows the exact safe rejection reason with its known source and model position](../../tests/js/contradiction-source-verification.test.mjs#L320) (Zeile 320)
- [never displays rejected quotes, explanations or a positive verdict even with contradictory checked metadata](../../tests/js/contradiction-source-verification.test.mjs#L333) (Zeile 333)
- [explains %s without inventing quote content](../../tests/js/contradiction-source-verification.test.mjs#L343) (Zeile 343)
- [does not create links for unknown, ambiguous or unsafe source identities and ignores raw diagnostics](../../tests/js/contradiction-source-verification.test.mjs#L357) (Zeile 357)
- [keeps legacy evidence_mismatch honest when no detailed rejection was saved](../../tests/js/contradiction-source-verification.test.mjs#L371) (Zeile 371)
- [bounds rejection diagnostics and reports fallback provenance without claiming successful verification](../../tests/js/contradiction-source-verification.test.mjs#L379) (Zeile 379)
- [gives an honest status and useful context for incomplete checks](../../tests/js/contradiction-source-verification.test.mjs#L395) (Zeile 395)
- [does not present rejected evidence as reviewed when a saved checked flag contradicts the rejection (%s)](../../tests/js/contradiction-source-verification.test.mjs#L411) (Zeile 411)
- [reserves the positive status for a supported outcome without adding a failure hint](../../tests/js/contradiction-source-verification.test.mjs#L421) (Zeile 421)
- [explains %s in the contradiction and source summary](../../tests/js/contradiction-source-verification.test.mjs#L429) (Zeile 429)

</details>

<a id="demo-claim-coverage-test-mjs"></a>

## demo-claim-coverage.test.mjs

**Quelle:** [tests/js/demo-claim-coverage.test.mjs](../../tests/js/demo-claim-coverage.test.mjs) · **Bereiche:** Demo, Konsens und Unterschiede.

**Ebene:** JavaScript-Daten-/Modulintegration mit VM und jsdom.

**Lauf:** 2 bestanden.

**Geprüftes Verhalten:** Demodaten enthalten sechs aktuelle Balanced-Familien mit längeren Antworten, konsistente models_compared und drei Unterschiede; 19 Claims markieren alle als prüfbar vorgesehenen Demopassagen ohne sichtbaren Fallback oder unmarkierte Wörter.

**Grenzen und Doubles:** Feste Demo und Text-/DOMassertions; weder reale Modellqualität noch Vollständigkeit beliebiger Antworten.

**Prüfauftrag für den Folgeaudit:** Demoänderungen gegen Registry und aktuelle Claimschemata synchron halten.

**Direkte Codeverweise:** [static/demo.js](../../static/demo.js), [static/js/consensus-anchor.js](../../static/js/consensus-anchor.js), [static/js/consensus-insights.js](../../static/js/consensus-insights.js).

**Direkte Testhelfer:** [tests/js/helpers/appWindow.mjs](../../tests/js/helpers/appWindow.mjs).

<details>
<summary>2 Testdefinitionen und ihre Quellstellen</summary>

- [provides six complete viewpoints and consistent claims for updated Balanced families](../../tests/js/demo-claim-coverage.test.mjs#L22) (Zeile 22)
- [marks every checkable consensus passage with the current coverage contract](../../tests/js/demo-claim-coverage.test.mjs#L33) (Zeile 33)

</details>

<a id="dompurify-vendor-test-mjs"></a>

## dompurify-vendor.test.mjs

**Quelle:** [tests/js/dompurify-vendor.test.mjs](../../tests/js/dompurify-vendor.test.mjs) · **Bereiche:** Sicherheit, Frontend.

**Ebene:** Echter gepinnter Sanitizer im jsdom.

**Lauf:** 26 bestanden.

**Geprüftes Verhalten:** Version und Angriffspayloads entfernen ausführbare Elemente, Eventhandler und javascript-URLs; Markdown, Mathematik und Quellenanker bleiben nutzbar.

**Grenzen und Doubles:** Endlicher Payloadkorpus, keine vollständige Sicherheitsfreigabe oder Live-Advisory-Prüfung.

**Prüfauftrag für den Folgeaudit:** Die benannten Mock-/Integrationsgrenzen am realen Adapter prüfen; Zuordnung und offene Aufgaben stehen in der Produktmatrix.

**Direkte Codeverweise:** [static/js/markdown-stream.js](../../static/js/markdown-stream.js), [static/js/math-render.js](../../static/js/math-render.js), [static/js/sources.js](../../static/js/sources.js), [static/vendor/marked/12.0.2/marked.min.js](../../static/vendor/marked/12.0.2/marked.min.js).

<details>
<summary>4 Testdefinitionen und ihre Quellstellen</summary>

- [is the pinned, maintained release and not an advisory-affected one](../../tests/js/dompurify-vendor.test.mjs#L68) (Zeile 68)
- [neutralizes %s with the default config](../../tests/js/dompurify-vendor.test.mjs#L75) (Zeile 75)
- [neutralizes %s through the model-answer renderer](../../tests/js/dompurify-vendor.test.mjs#L80) (Zeile 80)
- [still renders Markdown, formulas and numbered source anchors](../../tests/js/dompurify-vendor.test.mjs#L87) (Zeile 87)

</details>

<a id="error-reporter-test-mjs"></a>

## error-reporter.test.mjs

**Quelle:** [tests/js/error-reporter.test.mjs](../../tests/js/error-reporter.test.mjs) · **Bereiche:** Datenschutz, Fehlerdiagnostik.

**Ebene:** JavaScript-Modultest mit jsdom und Fetch-Double.

**Lauf:** 15 bestanden.

**Geprüftes Verhalten:** Nichtleere Meldung auch ohne Rejectiongrund, synchroner Transportfehler abgefangen und Reportgröße begrenzt; freigegebene Asset-/Runtimeorte erkannt, Querydaten und nicht erlaubte Metadaten entfernt. Unterschiedliche Runtimepositionen und Streamfehlerklassen bleiben getrennt; Favicons ignoriert; Appbundle- und CDN-Stylesheetfehler klassifiziert.

**Grenzen und Doubles:** Reports nur an Fetch-Double; keine tatsächliche keepalive-Zustellung, Backendannahme oder umfassende Geheimnisprüfung beliebiger Meldungen.

**Prüfauftrag für den Folgeaudit:** Client-/Serverredaktion und Deduplizierung als zusammenhängenden Vertrag prüfen.

**Direkte Codeverweise:** [static/js/error-reporter.js](../../static/js/error-reporter.js), [static/vendor/katex/0.17.0/dist/contrib/auto-render.min.js](../../static/vendor/katex/0.17.0/dist/contrib/auto-render.min.js), [static/vendor/katex/0.17.0/dist/katex.min.js](../../static/vendor/katex/0.17.0/dist/katex.min.js).

**Direkte Testhelfer:** [tests/js/helpers/appWindow.mjs](../../tests/js/helpers/appWindow.mjs).

<details>
<summary>13 Testdefinitionen und ihre Quellstellen</summary>

- [sends a nonempty message even for a rejection without a reason](../../tests/js/error-reporter.test.mjs#L24) (Zeile 24)
- [does not throw when the reporting transport throws synchronously](../../tests/js/error-reporter.test.mjs#L32) (Zeile 32)
- [bounds the report before the keepalive request](../../tests/js/error-reporter.test.mjs#L39) (Zeile 39)
- [identifies separate failed app assets without query strings](../../tests/js/error-reporter.test.mjs#L45) (Zeile 45)
- [does not send unapproved resource names](../../tests/js/error-reporter.test.mjs#L65) (Zeile 65)
- [keeps distinct runtime locations and strips query data from the script field](../../tests/js/error-reporter.test.mjs#L74) (Zeile 74)
- [extracts an app location from a rejected promise stack](../../tests/js/error-reporter.test.mjs#L90) (Zeile 90)
- [does not include unapproved runtime metadata: %s](../../tests/js/error-reporter.test.mjs#L100) (Zeile 100)
- [preserves distinct stream failure categories during deduplication](../../tests/js/error-reporter.test.mjs#L115) (Zeile 115)
- [ignores optional source favicons](../../tests/js/error-reporter.test.mjs#L124) (Zeile 124)
- [ignores document favicons](../../tests/js/error-reporter.test.mjs#L134) (Zeile 134)
- [reports a failed app script without sending its URL](../../tests/js/error-reporter.test.mjs#L145) (Zeile 145)
- [classifies a failed CDN stylesheet](../../tests/js/error-reporter.test.mjs#L162) (Zeile 162)

</details>

<a id="frontend-output-test-mjs"></a>

## frontend-output.test.mjs

**Quelle:** [tests/js/frontend-output.test.mjs](../../tests/js/frontend-output.test.mjs) · **Bereiche:** Build und Betrieb.

**Ebene:** Node-Integration mit echtem temporärem Dateisystem.

**Lauf:** 4 bestanden.

**Geprüftes Verhalten:** Behält zwei vorherige Assetversionen, identische Builds altern sie nicht; unveränderte Dateien behalten mtime, Änderungen atomar ersetzt ohne Restdateien. Fehlgeschlagene Veröffentlichung lässt altes Manifest/Assets lesbar; fremde Dateien bleiben, unsichere Retentionspfade ignoriert.

**Grenzen und Doubles:** Direkte Hilfsfunktionen mit kleinen künstlichen Assets; kein vollständiger Bundler, laufender Webserver oder Prozessabsturz während Veröffentlichung.

**Prüfauftrag für den Folgeaudit:** Deployment-/Cachevertrag und Leser während Veröffentlichung abgleichen.

**Direkte Codeverweise:** [scripts/frontend-output.mjs](../../scripts/frontend-output.mjs).

<details>
<summary>4 Testdefinitionen und ihre Quellstellen</summary>

- [preserves two previous versions and does not age them out on identical rebuilds](../../tests/js/frontend-output.test.mjs#L27) (Zeile 27)
- [does not truncate or rewrite unchanged vendor and bundle files](../../tests/js/frontend-output.test.mjs#L43) (Zeile 43)
- [leaves the old manifest and assets readable when publication fails](../../tests/js/frontend-output.test.mjs#L56) (Zeile 56)
- [never prunes unrelated files and ignores untrusted retention paths](../../tests/js/frontend-output.test.mjs#L64) (Zeile 64)

</details>

<a id="judge-stream-events-test-mjs"></a>

## judge-stream-events.test.mjs

**Quelle:** [tests/js/judge-stream-events.test.mjs](../../tests/js/judge-stream-events.test.mjs) · **Bereiche:** Konsens und Unterschiede, Quellenprüfung, Streaming und Wiederherstellung.

**Ebene:** JavaScript-Streamparser mit simuliertem ReadableStream.

**Lauf:** 1 bestanden.

**Geprüftes Verhalten:** Strukturierte ursprüngliche Unterschiede werden vor spätem Quellencheck ausgeliefert; finales Ergebnis enthält beide; nur Textempfänger erhält stop, strukturierte Empfänger nicht.

**Grenzen und Doubles:** Echtes markdown-stream-Modul, vorgegebene SSE-Bytes über Fetch-/Reader-Double; kein tatsächlicher dritter Judge oder Netzwerkstream.

**Prüfauftrag für den Folgeaudit:** Backendeventreihenfolge und tatsächliche Quelljoblatenz abgleichen.

**Direkte Codeverweise:** [static/js/markdown-stream.js](../../static/js/markdown-stream.js).

**Direkte Testhelfer:** [tests/js/helpers/appWindow.mjs](../../tests/js/helpers/appWindow.mjs).

<details>
<summary>1 Testdefinitionen und ihre Quellstellen</summary>

- [delivers original results before the third judge finishes and completes without calling stop on structured receivers](../../tests/js/judge-stream-events.test.mjs#L5) (Zeile 5)

</details>

<a id="markdown-remote-media-test-mjs"></a>

## markdown-remote-media.test.mjs

**Quelle:** [tests/js/markdown-remote-media.test.mjs](../../tests/js/markdown-remote-media.test.mjs) · **Bereiche:** Sicherheit, Frontend.

**Ebene:** jsdom-Markdownrenderer.

**Lauf:** 3 bestanden.

**Geprüftes Verhalten:** Remote-Markdownbilder werden durch Hinweise ersetzt, HTML-Medien/srcset/styles entfernt; sichere lokale Data-Bilder und normale Links bleiben.

**Grenzen und Doubles:** DOM-Ausgabe statt tatsächlicher Browser-Netzwerkbeobachtung.

**Prüfauftrag für den Folgeaudit:** Die benannten Mock-/Integrationsgrenzen am realen Adapter prüfen; Zuordnung und offene Aufgaben stehen in der Produktmatrix.

**Direkte Codeverweise:** [static/js/markdown-stream.js](../../static/js/markdown-stream.js), [static/vendor/dompurify/3.4.16/dist/purify.min.js](../../static/vendor/dompurify/3.4.16/dist/purify.min.js), [static/vendor/marked/12.0.2/marked.min.js](../../static/vendor/marked/12.0.2/marked.min.js).

<details>
<summary>3 Testdefinitionen und ihre Quellstellen</summary>

- [replaces remote markdown images with a visible note](../../tests/js/markdown-remote-media.test.mjs#L21) (Zeile 21)
- [strips raw HTML images, srcset, media and style blocks](../../tests/js/markdown-remote-media.test.mjs#L28) (Zeile 28)
- [keeps ordinary links clickable](../../tests/js/markdown-remote-media.test.mjs#L41) (Zeile 41)

</details>

<a id="markdown-stream-incremental-test-mjs"></a>

## markdown-stream-incremental.test.mjs

**Quelle:** [tests/js/markdown-stream-incremental.test.mjs](../../tests/js/markdown-stream-incremental.test.mjs) · **Bereiche:** Frontend, Agent.

**Ebene:** jsdom-Streamingrenderer mit Parserinstrumentierung.

**Lauf:** 7 bestanden.

**Geprüftes Verhalten:** Vollständige und inkrementelle Ausgabe stimmen überein, fertige Blöcke bleiben stabil; Parserarbeit ist begrenzt, Textwechsel setzt zurück und Streaming sanitisiert wie Vollrendering.

**Grenzen und Doubles:** Instrumentierte Zeichenmenge statt Produktions-Performancebenchmark.

**Prüfauftrag für den Folgeaudit:** Die benannten Mock-/Integrationsgrenzen am realen Adapter prüfen; Zuordnung und offene Aufgaben stehen in der Produktmatrix.

**Direkte Codeverweise:** [static/js/markdown-stream.js](../../static/js/markdown-stream.js), [static/vendor/dompurify/3.4.16/dist/purify.min.js](../../static/vendor/dompurify/3.4.16/dist/purify.min.js), [static/vendor/marked/12.0.2/marked.min.js](../../static/vendor/marked/12.0.2/marked.min.js).

<details>
<summary>4 Testdefinitionen und ihre Quellstellen</summary>

- [ends identical to a full render when chunks are %i chars](../../tests/js/markdown-stream-incremental.test.mjs#L30) (Zeile 30)
- [parses each finished block once, so work stays linear in the answer length](../../tests/js/markdown-stream-incremental.test.mjs#L38) (Zeile 38)
- [keeps finished nodes stable and starts over when the text does not just grow](../../tests/js/markdown-stream-incremental.test.mjs#L46) (Zeile 46)
- [sanitizes streamed blocks like a full render](../../tests/js/markdown-stream-incremental.test.mjs#L62) (Zeile 62)

</details>

<a id="markdown-table-test-mjs"></a>

## markdown-table.test.mjs

**Quelle:** [tests/js/markdown-table.test.mjs](../../tests/js/markdown-table.test.mjs) · **Bereiche:** Barrierefreiheit, Markdown und Darstellung.

**Ebene:** JavaScript-Modultest mit jsdom und Renderer-Doubles.

**Lauf:** 2 bestanden.

**Geprüftes Verhalten:** Semantische Tabelle bleibt in fokussierbarer Scrollregion mit aus Überschriften abgeleitetem ARIA-Label; überwiegend numerische Spalten erhalten Ausrichtung, Text und Summenbeschriftung bleiben Text.

**Grenzen und Doubles:** marked liefert immer vorbereitetes HTML, DOMPurify gibt unverändert zurück; keine Markdownparsing- oder XSS-Abdeckung durch diese Datei.

**Prüfauftrag für den Folgeaudit:** Reale Parser-/Sanitizerintegration und horizontales Scrollen browserseitig zuordnen.

**Direkte Codeverweise:** [static/js/markdown-stream.js](../../static/js/markdown-stream.js).

**Direkte Testhelfer:** [tests/js/helpers/appWindow.mjs](../../tests/js/helpers/appWindow.mjs).

<details>
<summary>2 Testdefinitionen und ihre Quellstellen</summary>

- [keeps the semantic table inside an accessible scroll region](../../tests/js/markdown-table.test.mjs#L32) (Zeile 32)
- [aligns predominantly numeric columns without changing text columns](../../tests/js/markdown-table.test.mjs#L46) (Zeile 46)

</details>

<a id="math-render-test-mjs"></a>

## math-render.test.mjs

**Quelle:** [tests/js/math-render.test.mjs](../../tests/js/math-render.test.mjs) · **Bereiche:** Markdown und Darstellung.

**Ebene:** JavaScript-Modulintegration mit jsdom und echten marked/DOMPurify/KaTeX-Bibliotheken; zusätzliche isolierte Helfertests.

**Lauf:** 26 bestanden.

**Geprüftes Verhalten:** Vollständige Formelbeispiele und vervollständigte Streamingdelimiter werden gesetzt; Displayvarianten, Zeilenumbrüche und Formelinterpunktion beschädigen Markdown nicht. Code und Geldbeträge bleiben wörtlich; Escapes/Indizes, Dollar-Inlineformeln und unvollständige Delimiter; Formeln aus Anchortext entfernen, nacktes Legacy-LaTeX erkennen, gewöhnlichen Text nicht umdeuten.

**Grenzen und Doubles:** DOM-/KaTeX-Assertions inklusive Annotationen, keine Screenshotvergleichsprüfung trotz Testnamen; einige vorbereitende Helfertests verwenden eigene Markdown-/Renderdoubles.

**Prüfauftrag für den Folgeaudit:** Breitere LaTeX-/Sprach-/Währungsfälle und visuelle Überläufe bei realer Browserbreite abgleichen.

**Direkte Codeverweise:** [static/js/markdown-stream.js](../../static/js/markdown-stream.js), [static/js/math-render.js](../../static/js/math-render.js), [templates/index.html](../../templates/index.html).

**Direkte Testhelfer:** [tests/js/helpers/appWindow.mjs](../../tests/js/helpers/appWindow.mjs).

<details>
<summary>19 Testdefinitionen und ihre Quellstellen</summary>

- [typesets the complete screenshot formula: %s](../../tests/js/math-render.test.mjs#L50) (Zeile 50)
- [recovers a formula once its streaming delimiter is complete](../../tests/js/math-render.test.mjs#L62) (Zeile 62)
- [preserves other display delimiters and formula punctuation: %s](../../tests/js/math-render.test.mjs#L76) (Zeile 76)
- [keeps code literal and renders ordinary Markdown and currency as before](../../tests/js/math-render.test.mjs#L94) (Zeile 94)
- [laesst die Escapes einer Formel den Markdown-Pass ueberleben](../../tests/js/math-render.test.mjs#L123) (Zeile 123)
- [macht aus $...$ die von KaTeX erkannte Form](../../tests/js/math-render.test.mjs#L128) (Zeile 128)
- [laesst Betraege in Ruhe, auch wenn zwei davon nebeneinander stehen](../../tests/js/math-render.test.mjs#L135) (Zeile 135)
- [haelt einen Preisvergleich fuer Text, keine Formel](../../tests/js/math-render.test.mjs#L140) (Zeile 140)
- [schuetzt Indizes vor der Kursivschrift](../../tests/js/math-render.test.mjs#L145) (Zeile 145)
- [fasst Code nicht an](../../tests/js/math-render.test.mjs#L155) (Zeile 155)
- [laesst $$-Bloecke unveraendert durch](../../tests/js/math-render.test.mjs#L160) (Zeile 160)
- [behaelt ein einzelnes \( ausserhalb einer Formel sichtbar](../../tests/js/math-render.test.mjs#L165) (Zeile 165)
- [liefert den Satz ohne Formel - so, wie ihn das DOM zeigt](../../tests/js/math-render.test.mjs#L178) (Zeile 178)
- [erkennt auch die Dollar-Schreibweise](../../tests/js/math-render.test.mjs#L184) (Zeile 184)
- [meldet mit "", dass gar keine Formel drin war](../../tests/js/math-render.test.mjs#L190) (Zeile 190)
- [erkennt den Anker einer abgesetzten Formel aus einem alten Lauf](../../tests/js/math-render.test.mjs#L201) (Zeile 201)
- [laesst jeden Anker mit gewoehnlichem Text in Ruhe](../../tests/js/math-render.test.mjs#L207) (Zeile 207)
- [uebergibt auch $...$ als echten KaTeX-Ausdruck](../../tests/js/math-render.test.mjs#L220) (Zeile 220)
- [fasst Betraege im fertigen DOM nicht an](../../tests/js/math-render.test.mjs#L235) (Zeile 235)

</details>

<a id="memory-edit-auth-test-mjs"></a>

## memory-edit-auth.test.mjs

**Quelle:** [tests/js/memory-edit-auth.test.mjs](../../tests/js/memory-edit-auth.test.mjs) · **Bereiche:** Nutzergedächtnis, Authentifizierung.

**Ebene:** jsdom-Memorydialog mit gesteuerten Auth-/Fetchwechseln.

**Lauf:** 5 bestanden.

**Geprüftes Verhalten:** Kontowechsel entfernt Auswahl und Undo, verhindert falsche Übermittlung und verspätetes Reload; Tokenrefresh desselben Kontos bleibt zulässig.

**Grenzen und Doubles:** Serverautorisierung und Persistenz werden nicht ausgeführt.

**Prüfauftrag für den Folgeaudit:** Die benannten Mock-/Integrationsgrenzen am realen Adapter prüfen; Zuordnung und offene Aufgaben stehen in der Produktmatrix.

**Direkte Codeverweise:** [static/js/auth-session-state.js](../../static/js/auth-session-state.js), [static/js/memory-edit.js](../../static/js/memory-edit.js).

<details>
<summary>5 Testdefinitionen und ihre Quellstellen</summary>

- [closes and forgets A's selection when the account changes to B](../../tests/js/memory-edit-auth.test.mjs#L59) (Zeile 59)
- [refuses to submit A's selection even if no auth event was seen](../../tests/js/memory-edit-auth.test.mjs#L72) (Zeile 72)
- [a late answer for A neither reloads nor shows Undo in B's session](../../tests/js/memory-edit-auth.test.mjs#L85) (Zeile 85)
- [hides A's Undo toast when the account changes](../../tests/js/memory-edit-auth.test.mjs#L104) (Zeile 104)
- [keeps working through a token refresh of the same account](../../tests/js/memory-edit-auth.test.mjs#L123) (Zeile 123)

</details>

<a id="memory-edit-sources-test-mjs"></a>

## memory-edit-sources.test.mjs

**Quelle:** [tests/js/memory-edit-sources.test.mjs](../../tests/js/memory-edit-sources.test.mjs) · **Bereiche:** Nutzergedächtnis, Quellen.

**Ebene:** jsdom-Auswahlmenü.

**Lauf:** 2 bestanden.

**Geprüftes Verhalten:** Ausgewählter Antworttext mit Quellenmarkierung öffnet das Ask-/Memory-Auswahlmenü.

**Grenzen und Doubles:** Keine tatsächliche KI-Patch-/Undo-Anfrage.

**Prüfauftrag für den Folgeaudit:** Die benannten Mock-/Integrationsgrenzen am realen Adapter prüfen; Zuordnung und offene Aufgaben stehen in der Produktmatrix.

**Direkte Codeverweise:** [static/js/memory-edit.js](../../static/js/memory-edit.js).

<details>
<summary>1 Testdefinitionen und ihre Quellstellen</summary>

- [offers Ask about this for %s](../../tests/js/memory-edit-sources.test.mjs#L32) (Zeile 32)

</details>

<a id="mobile-header-test-mjs"></a>

## mobile-header.test.mjs

**Quelle:** [tests/js/mobile-header.test.mjs](../../tests/js/mobile-header.test.mjs) · **Bereiche:** Responsive UI, Scrollen und Navigation.

**Ebene:** JavaScript-Modultest mit jsdom.

**Lauf:** 3 bestanden.

**Geprüftes Verhalten:** Verschiebt vorhandene Aktions-/Ansichtscontrols und stellt exakte Desktopposition wieder her, ohne Duplikat oder verlorenen Listener; Aktionen bei unvollständigem, geleertem oder Watchview verborgen; vorhandene New-Comparison-Aktion und Sidebarschließen nach Ansichtswechsel.

**Grenzen und Doubles:** Viewport/DOM und Aktionen simuliert; keine CSS-Geometrie oder echter Touchbrowser.

**Prüfauftrag für den Folgeaudit:** Breakpointwechsel, Fokus und Layout mit E2E abgleichen.

**Direkte Codeverweise:** [static/js/mobile-header.js](../../static/js/mobile-header.js).

**Direkte Testhelfer:** [tests/js/helpers/appWindow.mjs](../../tests/js/helpers/appWindow.mjs).

<details>
<summary>3 Testdefinitionen und ihre Quellstellen</summary>

- [moves the actual controls and restores their exact desktop slots without duplicates](../../tests/js/mobile-header.test.mjs#L24) (Zeile 24)
- [hides actions for incomplete, cleared and Watch views and restores them for the answer](../../tests/js/mobile-header.test.mjs#L40) (Zeile 40)
- [uses the existing new-comparison action and closes the sidebar after switching views](../../tests/js/mobile-header.test.mjs#L57) (Zeile 57)

</details>

<a id="model-answer-reader-test-mjs"></a>

## model-answer-reader.test.mjs

**Quelle:** [tests/js/model-answer-reader.test.mjs](../../tests/js/model-answer-reader.test.mjs) · **Bereiche:** Antwortdarstellung, Barrierefreiheit, Bookmarks und Verlauf, Responsive UI.

**Ebene:** JavaScript-Modultest mit jsdom.

**Lauf:** 24 bestanden.

**Geprüftes Verhalten:** Toolbelege pro Panel/Basis, Refresh und Reset isoliert; Modellvorschau erzeugt keine Antwort oder Ladeanzeige, echter Lauf ersetzt sie. Skeleton bis erster Text/Terminalzustand; Directbereitschaft im Composer, eingefrorene Modellversionen mit ehrlichem Legacyfallback. Auswahl und Scrollposition bei Streamupdate erhalten; archivierter Turn mit eigenen Quellen bleibt während Followup gewählt; fertiger Live-Turn geht in Historie über. Fremder Lauf/Logout schließt; unveränderte Antwort-DOM bleibt; Fehler im Directvergleich, zwei verschiedene Vergleichsmodelle und schmale/mobile Picker. Claimlink öffnet richtigen historischen Provider mit Fokusrückgabe; unsichere Namen/Links blockiert. Aktualisierung 02.10.2026: Nur ein Finding offen; keine redundanten Kontextlabels, unvollständige und abgeschnittene Antworten behalten Text und sichtbare Begründung.

**Grenzen und Doubles:** Echter Reader, vorbereitete Run-/Turndaten, Markdown- und Geometrie-/Dialogumgebung teilweise simuliert. Keine tatsächliche Bildschirmbreite oder Screenreaderwirkung.

**Prüfauftrag für den Folgeaudit:** Zusammenspiel mit echten Renderern, Liveprojektion und Browserdialog abgleichen.

**Direkte Codeverweise:** [static/js/model-answer-reader.js](../../static/js/model-answer-reader.js).

**Direkte Testhelfer:** [tests/js/helpers/appWindow.mjs](../../tests/js/helpers/appWindow.mjs).

<details>
<summary>21 Testdefinitionen und ihre Quellstellen</summary>

- [keeps explicit tool evidence isolated across panels, bases, refresh and reset](../../tests/js/model-answer-reader.test.mjs#L53) (Zeile 53)
- [keeps the differences panel to one open finding, without subtitle or question label](../../tests/js/model-answer-reader.test.mjs#L89) (Zeile 89)
- [previews selected models without creating an answer or a loading state](../../tests/js/model-answer-reader.test.mjs#L118) (Zeile 118)
- [replaces the preview with a real run and protects its frozen answers from mode changes](../../tests/js/model-answer-reader.test.mjs#L137) (Zeile 137)
- [replaces waiting skeletons on first text and terminal states (agent=%s)](../../tests/js/model-answer-reader.test.mjs#L150) (Zeile 150)
- [moves direct readiness to the composer and retains the normal reader heading](../../tests/js/model-answer-reader.test.mjs#L170) (Zeile 170)
- [keeps saved model versions independent of current model choices](../../tests/js/model-answer-reader.test.mjs#L185) (Zeile 185)
- [omits unknown legacy version %s without inventing one](../../tests/js/model-answer-reader.test.mjs#L193) (Zeile 193)
- [uses the frozen model ID if a live run has no display label](../../tests/js/model-answer-reader.test.mjs#L203) (Zeile 203)
- [shows only the selected original and updates streaming text without changing selection or scroll](../../tests/js/model-answer-reader.test.mjs#L210) (Zeile 210)
- [keeps an archived question and its own sources selected when a later turn streams](../../tests/js/model-answer-reader.test.mjs#L225) (Zeile 225)
- [keeps a completed live answer pinned when it moves into the conversation history](../../tests/js/model-answer-reader.test.mjs#L235) (Zeile 235)
- [closes when switching to an unrelated run and on logout/reset](../../tests/js/model-answer-reader.test.mjs#L245) (Zeile 245)
- [preserves an untouched direct answer while another model streams](../../tests/js/model-answer-reader.test.mjs#L253) (Zeile 253)
- [shows every direct answer inline including failed models](../../tests/js/model-answer-reader.test.mjs#L263) (Zeile 263)
- [compares two distinct models and switches between them on phones](../../tests/js/model-answer-reader.test.mjs#L273) (Zeile 273)
- [uses actual reader width for tablets with a sidebar](../../tests/js/model-answer-reader.test.mjs#L286) (Zeile 286)
- [uses one compact model picker on phones instead of a tall stack of model tabs](../../tests/js/model-answer-reader.test.mjs#L294) (Zeile 294)
- [opens claim links in the correct archived model and restores focus on close](../../tests/js/model-answer-reader.test.mjs#L303) (Zeile 303)
- [shows partial and cut-off answers with their text, a small mark and one visible reason](../../tests/js/model-answer-reader.test.mjs#L313) (Zeile 313)
- [renders model names as text and never creates unsafe source links](../../tests/js/model-answer-reader.test.mjs#L331) (Zeile 331)

</details>

<a id="model-attachment-capability-test-mjs"></a>

## model-attachment-capability.test.mjs

**Quelle:** [tests/js/model-attachment-capability.test.mjs](../../tests/js/model-attachment-capability.test.mjs) · **Bereiche:** Anhänge, Modelle und Provider.

**Ebene:** JavaScript-Modultest mit jsdom.

**Lauf:** 2 bestanden.

**Geprüftes Verhalten:** GLM Flash mit Anhängen, GLM Pro textbasiert und Thinkingausschluss unterschieden; Legacy-Providerboolean als Fallback für gecachte Clients.

**Grenzen und Doubles:** Zwei künstliche Familykonfigurationen; kein Nachweis aller Registrymodelle oder tatsächlicher Providerannahme.

**Prüfauftrag für den Folgeaudit:** Frontendfähigkeiten gegen serverseitige Registry und ausgewählte Modelle abgleichen.

**Direkte Codeverweise:** [static/js/app-core.js](../../static/js/app-core.js).

**Direkte Testhelfer:** [tests/js/helpers/appWindow.mjs](../../tests/js/helpers/appWindow.mjs).

<details>
<summary>2 Testdefinitionen und ihre Quellstellen</summary>

- [distinguishes GLM Flash from the text-only Pro model](../../tests/js/model-attachment-capability.test.mjs#L16) (Zeile 16)
- [keeps the legacy provider boolean as a cached-client fallback](../../tests/js/model-attachment-capability.test.mjs#L30) (Zeile 30)

</details>

<a id="model-family-cap-test-mjs"></a>

## model-family-cap.test.mjs

**Quelle:** [tests/js/model-family-cap.test.mjs](../../tests/js/model-family-cap.test.mjs) · **Bereiche:** Composer, Modelle und Provider.

**Ebene:** JavaScript-Modultest mit jsdom.

**Lauf:** 4 bestanden.

**Geprüftes Verhalten:** Modellfamilie innerhalb Limit auswählbar; Überschreitung abgewiesen, bestehende Auswahl nicht still ersetzt; gespeicherte Überauswahl ohne Popup reduziert; Abwahl gibt Platz frei.

**Grenzen und Doubles:** Künstliche vier Familien und konfiguriertes Limit drei; keine reale Katalog-/Backendvalidierung.

**Prüfauftrag für den Folgeaudit:** Gemeinsame Ober-/Untergrenzen bei Restore, Tarifen und Versand zuordnen.

**Direkte Codeverweise:** [static/js/model-picker.js](../../static/js/model-picker.js).

**Direkte Testhelfer:** [tests/js/helpers/appWindow.mjs](../../tests/js/helpers/appWindow.mjs).

<details>
<summary>4 Testdefinitionen und ihre Quellstellen</summary>

- [includes a family while the run still has room](../../tests/js/model-family-cap.test.mjs#L57) (Zeile 57)
- [refuses the family beyond the cap instead of dropping another one](../../tests/js/model-family-cap.test.mjs#L66) (Zeile 66)
- [applies the cap to restored selections without shouting at the user](../../tests/js/model-family-cap.test.mjs#L77) (Zeile 77)
- [frees a slot again when a family is left out](../../tests/js/model-family-cap.test.mjs#L86) (Zeile 86)

</details>

<a id="model-pulse-test-mjs"></a>

## model-pulse.test.mjs

**Quelle:** [tests/js/model-pulse.test.mjs](../../tests/js/model-pulse.test.mjs) · **Bereiche:** Modellstatistik, Öffentliche Seiten.

**Ebene:** JavaScript-Modultest mit jsdom und Fetch-Double.

**Lauf:** 3 bestanden.

**Geprüftes Verhalten:** Serverseitiges Initialranking ohne Doppelrequest; Periodenwechsel rendert alle gelieferten Familien, individuelle Startdaten und Gesamtsumme; fehlgeschlagener Refresh behält Ranking, restauriert Auswahl und entsperrt Controls.

**Grenzen und Doubles:** Vorbereitetes HTML und APIantworten; keine Statistikberechnung, echte Serverrenderingkette oder Netzwerkverfügbarkeit.

**Prüfauftrag für den Folgeaudit:** SSR-/APIvertrag, Periodenfilter und fehlende Statistikdaten zusammenführen.

**Direkte Codeverweise:** [static/js/model-pulse.js](../../static/js/model-pulse.js).

**Direkte Testhelfer:** [tests/js/helpers/appWindow.mjs](../../tests/js/helpers/appWindow.mjs).

<details>
<summary>3 Testdefinitionen und ihre Quellstellen</summary>

- [keeps the initial server ranking without a duplicate request](../../tests/js/model-pulse.test.mjs#L22) (Zeile 22)
- [switches period and renders individual start dates and every returned family](../../tests/js/model-pulse.test.mjs#L30) (Zeile 30)
- [preserves the last ranking and restores its period when refresh fails](../../tests/js/model-pulse.test.mjs#L47) (Zeile 47)

</details>

<a id="multi-run-view-test-mjs"></a>

## multi-run-view.test.mjs

**Quelle:** [tests/js/multi-run-view.test.mjs](../../tests/js/multi-run-view.test.mjs) · **Bereiche:** Bookmarks und Verlauf, Frontend-Zustand, Nebenläufigkeit, Quellenprüfung.

**Ebene:** JavaScript-Modulintegration mit jsdom und Render-/Observer-Doubles.

**Lauf:** 10 bestanden.

**Geprüftes Verhalten:** Quellenhydration nach Konsensabschluss ohne versteckten Lauf zu projizieren; historische Stubs nur solange ihr DOM existiert. Followup erhält Historien-DOM, offene Details, Fokus und wartende Animationen; Modellquellen/Terminalfehler aktualisieren auch ohne Textänderung. Insights erscheinen vor Quellenabschluss und bleiben als DOM erhalten; Hintergrundupdates bleiben beim Owner, Laufzeilen wechseln gezielt. Rückkopplung durch Projektion begrenzt; Quellnummern lauflokal ohne sichtbare Globals zu ändern; Legacy-Quellenblock hinter erste Aussage. Aktualisierung 02.10.2026: Archivierter Agentturn besitzt eine Belegzeile mit Copy ohne doppelten Quellenfooter.

**Grenzen und Doubles:** Echte Registry-/View- und teilweise Konsens-/Sourcesmodule, viele Rendering-/Auth-/Quellobservergrenzen ersetzt; kein tatsächliches paralleles Backend.

**Prüfauftrag für den Folgeaudit:** Reale Renderer, Persistenz und mehrere Streams mit Browserläufen abgleichen.

**Direkte Codeverweise:** [static/js/agent-answer-actions.js](../../static/js/agent-answer-actions.js), [static/js/agent-review.js](../../static/js/agent-review.js), [static/js/consensus-run.js](../../static/js/consensus-run.js), [static/js/run-registry.js](../../static/js/run-registry.js), [static/js/run-view.js](../../static/js/run-view.js), [static/js/sources.js](../../static/js/sources.js).

**Direkte Testhelfer:** [tests/js/helpers/appWindow.mjs](../../tests/js/helpers/appWindow.mjs).

<details>
<summary>10 Testdefinitionen und ihre Quellstellen</summary>

- [continues source hydration after consensus succeeds without projecting a hidden run](../../tests/js/multi-run-view.test.mjs#L133) (Zeile 133)
- [hydrates a saved terminal source stub for a historical turn only while its body exists](../../tests/js/multi-run-view.test.mjs#L164) (Zeile 164)
- [gives an archived Agent turn one evidence row with Copy inside and no second Sources footer](../../tests/js/multi-run-view.test.mjs#L183) (Zeile 183)
- [preserves completed history, open drawers and waiting model animations during follow-up streaming](../../tests/js/multi-run-view.test.mjs#L205) (Zeile 205)
- [refreshes model source mappings and terminal errors without text changes](../../tests/js/multi-run-view.test.mjs#L266) (Zeile 266)
- [publishes insights while sources are pending and preserves their DOM through source and final events](../../tests/js/multi-run-view.test.mjs#L285) (Zeile 285)
- [keeps late background updates out of the visible DOM and restores either run from its row](../../tests/js/multi-run-view.test.mjs#L321) (Zeile 321)
- [survives a surface that renders the visible run back at it](../../tests/js/multi-run-view.test.mjs#L356) (Zeile 356)
- [rewrites source numbers against the supplied run without touching the visible global](../../tests/js/multi-run-view.test.mjs#L386) (Zeile 386)
- [moves a legacy leading source block behind the first model claim](../../tests/js/multi-run-view.test.mjs#L431) (Zeile 431)

</details>

<a id="plus-tier-gates-test-mjs"></a>

## plus-tier-gates.test.mjs

**Quelle:** [tests/js/plus-tier-gates.test.mjs](../../tests/js/plus-tier-gates.test.mjs) · **Bereiche:** Anhänge, Konten und Tarife.

**Ebene:** Gemischte JavaScript-Modulintegration und statische Quelltextverträge.

**Lauf:** 7 bestanden.

**Geprüftes Verhalten:** Plus darf Dateiauswahl, Free wird gesperrt; Badge/Upgradelink für Free/Plus/Pro; falsches is_pro-Signal überschreibt Plus nicht, expliziter Downgrade und Prosignal gültig. Quelltextprüfungen für Tarifsinks verbieten is_pro als direkte Übergabe und fordern data.tier mit Fallback. Der aktuelle Diff passt Fixtures, Payloads oder Bezeichnungen an; die unten neu extrahierten Definitionen und Assertionstellen sind maßgeblich.

**Grenzen und Doubles:** DOMlogik mit echten State/Core/Attachments/Tiermodulen; ausgewählte Tierauflösung und Aufrufstellen zusätzlich aus Quelltext geprüft. Keine serverseitige Autorisierung oder vollständige Authintegration.

**Prüfauftrag für den Folgeaudit:** APIpayloads und sämtliche Tarifkonsumenten einschließlich Altclients gemeinsam abgleichen.

**Direkte Codeverweise:** [static/firebase.js](../../static/firebase.js), [static/js/app-core.js](../../static/js/app-core.js), [static/js/app-state.js](../../static/js/app-state.js), [static/js/attachments.js](../../static/js/attachments.js), [static/js/user-tier.js](../../static/js/user-tier.js).

**Direkte Testhelfer:** [tests/js/helpers/appWindow.mjs](../../tests/js/helpers/appWindow.mjs).

<details>
<summary>7 Testdefinitionen und ihre Quellstellen</summary>

- [lets a Plus account open the file picker](../../tests/js/plus-tier-gates.test.mjs#L72) (Zeile 72)
- [still refuses a Free account](../../tests/js/plus-tier-gates.test.mjs#L85) (Zeile 85)
- [names the tier on the badge and drops the Free-only upgrade link](../../tests/js/plus-tier-gates.test.mjs#L94) (Zeile 94)
- [keeps Plus when a run reports only is_pro_user: false](../../tests/js/plus-tier-gates.test.mjs#L109) (Zeile 109)
- [still accepts an explicit downgrade and a bare Pro signal](../../tests/js/plus-tier-gates.test.mjs#L123) (Zeile 123)
- [never passes an is_pro flag to %s](../../tests/js/plus-tier-gates.test.mjs#L171) (Zeile 171)
- [reads data.tier with the pro flag only as a fallback](../../tests/js/plus-tier-gates.test.mjs#L177) (Zeile 177)

</details>

<a id="request-deadline-test-mjs"></a>

## request-deadline.test.mjs

**Quelle:** [tests/js/request-deadline.test.mjs](../../tests/js/request-deadline.test.mjs) · **Bereiche:** Streaming und Wiederherstellung.

**Ebene:** JavaScript-Modultest mit jsdom.

**Lauf:** 3 bestanden.

**Geprüftes Verhalten:** Hängende Operation wird abgebrochen und erneuter Versuch möglich; bereits abgebrochenes Signal verhindert Dispatch; Streamaktivität erneuert Deadline und räumt Timer bei Abschluss auf.

**Grenzen und Doubles:** Promises und Timer teilweise kontrolliert; kein echter TCP-/HTTP-Timeout.

**Prüfauftrag für den Folgeaudit:** Abbruchsignale und Body-/Headerhänger in allen Requestkonsumenten zuordnen.

**Direkte Codeverweise:** [static/js/request-deadline.js](../../static/js/request-deadline.js).

**Direkte Testhelfer:** [tests/js/helpers/appWindow.mjs](../../tests/js/helpers/appWindow.mjs).

<details>
<summary>3 Testdefinitionen und ihre Quellstellen</summary>

- [aborts a stalled request and allows another attempt](../../tests/js/request-deadline.test.mjs#L5) (Zeile 5)
- [preserves cancellation and never dispatches an already cancelled operation](../../tests/js/request-deadline.test.mjs#L14) (Zeile 14)
- [renews streaming liveness and removes timers after completion](../../tests/js/request-deadline.test.mjs#L22) (Zeile 22)

</details>

<a id="result-integrity-test-mjs"></a>

## result-integrity.test.mjs

**Quelle:** [tests/js/result-integrity.test.mjs](../../tests/js/result-integrity.test.mjs) · **Bereiche:** Consensus, Frontend.

**Ebene:** jsdom-Consensusablauf mit simuliertem Transport.

**Lauf:** 2 bestanden.

**Geprüftes Verhalten:** Nur Receipts vollständiger/verwendbarer Antworten werden gesendet, keine Clientantworttexte/-quellen. Abgeschnittene Synthese bleibt sichtbar, aber fehlgeschlagen, ohne Vote oder Bookmarksave.

**Grenzen und Doubles:** SSE/API simuliert; Serverreceipt-Prüfung liegt separat in Python.

**Prüfauftrag für den Folgeaudit:** Die benannten Mock-/Integrationsgrenzen am realen Adapter prüfen; Zuordnung und offene Aufgaben stehen in der Produktmatrix.

**Direkte Codeverweise:** [static/js/consensus-run.js](../../static/js/consensus-run.js), [static/js/run-registry.js](../../static/js/run-registry.js).

<details>
<summary>2 Testdefinitionen und ihre Quellstellen</summary>

- [sends only receipts of complete answers, never answer text or sources](../../tests/js/result-integrity.test.mjs#L41) (Zeile 41)
- [keeps a truncated synthesis visible but marks it incomplete and failed](../../tests/js/result-integrity.test.mjs#L53) (Zeile 53)

</details>

<a id="run-mode-test-mjs"></a>

## run-mode.test.mjs

**Quelle:** [tests/js/run-mode.test.mjs](../../tests/js/run-mode.test.mjs) · **Bereiche:** Frontend, Einstellungen.

**Ebene:** jsdom-Moduszustand und Storage.

**Lauf:** 8 bestanden.

**Geprüftes Verhalten:** Legacy-Schalter migrieren einmalig; Compare/Consensus/Agent werden anhand von Chatfamilie und Zugriff aufgelöst. Ungültige Werte, Eventdeduplizierung und anderer Tab sind geprüft.

**Grenzen und Doubles:** Keine vollständige UI-/Routerintegration.

**Prüfauftrag für den Folgeaudit:** Die benannten Mock-/Integrationsgrenzen am realen Adapter prüfen; Zuordnung und offene Aufgaben stehen in der Produktmatrix.

**Direkte Codeverweise:** [static/js/run-mode.js](../../static/js/run-mode.js).

<details>
<summary>4 Testdefinitionen und ihre Quellstellen</summary>

- [migrates %o once to %s and removes the legacy keys](../../tests/js/run-mode.test.mjs#L15) (Zeile 15)
- [changes only to known modes, announces changes once and tracks the source](../../tests/js/run-mode.test.mjs#L32) (Zeile 32)
- [resolves the effective mode from the open chat and the account](../../tests/js/run-mode.test.mjs#L45) (Zeile 45)
- [follows a change made in another tab](../../tests/js/run-mode.test.mjs#L71) (Zeile 71)

</details>

<a id="run-progress-scope-test-mjs"></a>

## run-progress-scope.test.mjs

**Quelle:** [tests/js/run-progress-scope.test.mjs](../../tests/js/run-progress-scope.test.mjs) · **Bereiche:** Antwortdarstellung, Frontend-Zustand, Streaming und Wiederherstellung.

**Ebene:** JavaScript-Modulintegration mit jsdom.

**Lauf:** 11 bestanden.

**Geprüftes Verhalten:** Aktueller Stepper statt entfernter animierter Fortschrittsleiste; Modellstatus gehört zum sichtbaren Lauf.

**Grenzen und Doubles:** Echte Registry/Progress/Viewmodule mit Auth-/Umgebungsdoubles und unmittelbaren Zählern; keine realen Zeit-/Screenreader-/Layoutmessungen.

**Prüfauftrag für den Folgeaudit:** Zusammenspiel mit Animationssuite und echten Hintergrundstreams abgleichen.

**Direkte Codeverweise:** [static/js/consensus-progress.js](../../static/js/consensus-progress.js), [static/js/run-registry.js](../../static/js/run-registry.js), [static/js/run-view.js](../../static/js/run-view.js).

**Direkte Testhelfer:** [tests/js/helpers/appWindow.mjs](../../tests/js/helpers/appWindow.mjs).

<details>
<summary>9 Testdefinitionen und ihre Quellstellen</summary>

- [leaves the view when a saved bookmark is opened and comes back with the run](../../tests/js/run-progress-scope.test.mjs#L130) (Zeile 130)
- [keeps counting from the real start when a running run is reopened](../../tests/js/run-progress-scope.test.mjs#L164) (Zeile 164)
- [shows a live per-model bar and completes it with the answer](../../tests/js/run-progress-scope.test.mjs#L176) (Zeile 176)
- [never shows one run's facts under another view](../../tests/js/run-progress-scope.test.mjs#L201) (Zeile 201)
- [counts raw streamed characters without Markdown UI or surrogate duplication](../../tests/js/run-progress-scope.test.mjs#L226) (Zeile 226)
- [does not count waiting or reasoning placeholders](../../tests/js/run-progress-scope.test.mjs#L252) (Zeile 252)
- [shows %s as a terminal outcome, never a successful answer or character count](../../tests/js/run-progress-scope.test.mjs#L266) (Zeile 266)
- [freezes completion time and restores only the selected run's characters](../../tests/js/run-progress-scope.test.mjs#L282) (Zeile 282)
- [does not repeatedly announce each timer tick or streamed character](../../tests/js/run-progress-scope.test.mjs#L309) (Zeile 309)

</details>

<a id="run-registry-test-mjs"></a>

## run-registry.test.mjs

**Quelle:** [tests/js/run-registry.test.mjs](../../tests/js/run-registry.test.mjs) · **Bereiche:** Frontend-Zustand, Nebenläufigkeit, Streaming und Wiederherstellung.

**Ebene:** JavaScript-Modultest mit jsdom und Auth-Doubles.

**Lauf:** 9 bestanden.

**Geprüftes Verhalten:** Gespeicherte Agentsnapshots begrenzt ohne ungespeicherte/fremde Pipelineergebnisse zu verlieren; Startsnapshots eingefroren und höchstens zwei aktive Läufe. Sichtbare Projektion, Ausführung und Followupbasis getrennt; gezielter Cancel und clearAll brechen Ownercontroller ab. Followups pro Gespräch serialisiert, unsicherer Turn/Löschung gesperrt; fehlgeschlagenes Followup verdrängt letzten erfolgreichen Bookmark nicht. Usageupdates nach Reihenfolge, autoritativer Refresh; teure Folgeaktionen teilen Zulassung/Logoutgrenze; ChatSessioninstanzen teilen keine Identität. Aktualisierung 02.10.2026: Entfernte Fortschrittsanimation wird nicht mehr als Registryvertrag erwartet; Run-/Chatbindung bleibt.

**Grenzen und Doubles:** In-Memory-Registry und simulierte Auth-/Operationen; kein serverübergreifendes Lock oder tatsächliche Quota-Transaktion.

**Prüfauftrag für den Folgeaudit:** Clientzulassung gegen Backendconcurrency, Kontenwechsel und persistierte Gesprächsidentität prüfen.

**Direkte Codeverweise:** [static/js/chat-session.js](../../static/js/chat-session.js), [static/js/run-registry.js](../../static/js/run-registry.js).

**Direkte Testhelfer:** [tests/js/helpers/appWindow.mjs](../../tests/js/helpers/appWindow.mjs).

<details>
<summary>9 Testdefinitionen und ihre Quellstellen</summary>

- [bounds saved Agent snapshots without dropping unsaved or other pipeline results](../../tests/js/run-registry.test.mjs#L39) (Zeile 39)
- [freezes each start snapshot and admits at most two executing runs](../../tests/js/run-registry.test.mjs#L64) (Zeile 64)
- [projects only the selected run while background callbacks keep updating their owner](../../tests/js/run-registry.test.mjs#L86) (Zeile 86)
- [keeps execution, visible view, and selected follow-up basis independent](../../tests/js/run-registry.test.mjs#L107) (Zeile 107)
- [cancels exactly the addressed run and clearAll aborts the rest](../../tests/js/run-registry.test.mjs#L129) (Zeile 129)
- [serializes follow-ups per conversation and retains an uncertain-turn fence](../../tests/js/run-registry.test.mjs#L165) (Zeile 165)
- [does not let a failed follow-up shadow the last successful bookmark snapshot](../../tests/js/run-registry.test.mjs#L196) (Zeile 196)
- [owns costly post-actions under the same admission and logout boundary](../../tests/js/run-registry.test.mjs#L208) (Zeile 208)
- [does not share completed or pending conversation identity](../../tests/js/run-registry.test.mjs#L242) (Zeile 242)

</details>

<a id="send-button-test-mjs"></a>

## send-button.test.mjs

**Quelle:** [tests/js/send-button.test.mjs](../../tests/js/send-button.test.mjs) · **Bereiche:** Frontend.

**Ebene:** jsdom-Sende-/Stopzustand.

**Lauf:** 1 bestanden.

**Geprüftes Verhalten:** SVG bleibt über wiederholte Syncs stabil; Startanimation erfolgt einmal, Stop und Ende stellen die richtigen Icons/Klassen her.

**Grenzen und Doubles:** Kein visueller Nachweis von Lichtanimation/Reduced Motion.

**Prüfauftrag für den Folgeaudit:** Die benannten Mock-/Integrationsgrenzen am realen Adapter prüfen; Zuordnung und offene Aufgaben stehen in der Produktmatrix.

**Direkte Codeverweise:** [static/js/query-send.js](../../static/js/query-send.js).

<details>
<summary>1 Testdefinitionen und ihre Quellstellen</summary>

- [keeps its icon across repeated syncs and launches once per run](../../tests/js/send-button.test.mjs#L13) (Zeile 13)

</details>

<a id="seo-admin-alerts-test-mjs"></a>

## seo-admin-alerts.test.mjs

**Quelle:** [tests/js/seo-admin-alerts.test.mjs](../../tests/js/seo-admin-alerts.test.mjs) · **Bereiche:** Admin, SEO.

**Ebene:** Ausgeführter admin.js-Ausschnitt mit jsdom.

**Lauf:** 10 bestanden.

**Geprüftes Verhalten:** Unverifizierte Verbindung als Hinweis, nur vollständig bestätigter gesunder Zustand still; fehlende Credentials/fehlgeschlagene Verbindung, fehlerhafte oder nie erfolgte Collection, laufender Job, fehlgeschlagener Wochenreview/Judge und Portfolio ohne gespeicherte Daten sichtbar. Success/Partial passend behandelt; mehrere Fehler stapeln sich statt gegenseitig verborgen zu werden.

**Grenzen und Doubles:** SEO-Ausschnitt aus admin.js und Ausschnitt des echten Admin-Templates, künstliche Overviewdaten und Request-Doubles; kein Search-Consolezugriff, Scheduler oder vollständiges Admin-Modul.

**Prüfauftrag für den Folgeaudit:** Alle Serverstatus und dauerhaft ausbleibende Jobs mit tatsächlichem Monitoring abgleichen.

**Direkte Codeverweise:** [static/js/admin.js](../../static/js/admin.js), [templates/admin.html](../../templates/admin.html).

**Direkte Testhelfer:** [tests/js/helpers/appWindow.mjs](../../tests/js/helpers/appWindow.mjs).

<details>
<summary>10 Testdefinitionen und ihre Quellstellen</summary>

- [stays silent only when everything is verified healthy](../../tests/js/seo-admin-alerts.test.mjs#L102) (Zeile 102)
- [catches credentials that are not configured](../../tests/js/seo-admin-alerts.test.mjs#L114) (Zeile 114)
- [catches a failed connection check and drops the unverified notice](../../tests/js/seo-admin-alerts.test.mjs#L128) (Zeile 128)
- [catches every collection run that is neither success nor partial](../../tests/js/seo-admin-alerts.test.mjs#L143) (Zeile 143)
- [keeps partial and success quiet, and calls a running collection out as a notice](../../tests/js/seo-admin-alerts.test.mjs#L161) (Zeile 161)
- [catches a portfolio that has never been collected at all](../../tests/js/seo-admin-alerts.test.mjs#L178) (Zeile 178)
- [catches a weekly review that ended as collection_failed or error](../../tests/js/seo-admin-alerts.test.mjs#L185) (Zeile 185)
- [catches a judge that did not answer](../../tests/js/seo-admin-alerts.test.mjs#L202) (Zeile 202)
- [catches a portfolio where no page has any stored data](../../tests/js/seo-admin-alerts.test.mjs#L216) (Zeile 216)
- [reproduces the five silent weeks: several failures stack instead of hiding](../../tests/js/seo-admin-alerts.test.mjs#L225) (Zeile 225)

</details>

<a id="sidebar-quota-test-mjs"></a>

## sidebar-quota.test.mjs

**Quelle:** [tests/js/sidebar-quota.test.mjs](../../tests/js/sidebar-quota.test.mjs) · **Bereiche:** Agent, Konten und Tarife.

**Ebene:** JavaScript-Modultest mit jsdom.

**Lauf:** 4 bestanden.

**Geprüftes Verhalten:** Ein Kontoring und Panel für alle Modi; Holds/Schätzungen, Schwellfarben, geordnete konkurrierende Snapshots, UID-Fencing und Startprüfung gegen Modusschätzung.

**Grenzen und Doubles:** Ein Test mit mehreren aufeinanderfolgenden künstlichen Budgets; keine Backendberechnung, tatsächliche Reservierung oder visuelle Ringprüfung.

**Prüfauftrag für den Folgeaudit:** Reset, konkurrierende Reservierungen und kontenbezogene UIupdates zuordnen.

**Direkte Codeverweise:** [static/js/sidebar-quota.js](../../static/js/sidebar-quota.js), [static/js/token-budget.js](../../static/js/token-budget.js).

**Direkte Testhelfer:** [tests/js/helpers/appWindow.mjs](../../tests/js/helpers/appWindow.mjs).

<details>
<summary>4 Testdefinitionen und ihre Quellstellen</summary>

- [shows one quiet ring for the shared account, the value only in label and panel](../../tests/js/sidebar-quota.test.mjs#L30) (Zeile 30)
- [turns only the arc and the bar amber or red, and explains holds and estimates](../../tests/js/sidebar-quota.test.mjs#L55) (Zeile 55)
- [orders concurrent snapshots and fences other accounts](../../tests/js/sidebar-quota.test.mjs#L75) (Zeile 75)
- [admits a run like the server: available tokens against the mode estimate](../../tests/js/sidebar-quota.test.mjs#L93) (Zeile 93)

</details>

<a id="skeleton-lifecycle-test-mjs"></a>

## skeleton-lifecycle.test.mjs

**Quelle:** [tests/js/skeleton-lifecycle.test.mjs](../../tests/js/skeleton-lifecycle.test.mjs) · **Bereiche:** Authentifizierung, Barrierefreiheit, Bookmarks und Verlauf.

**Ebene:** JavaScript-Modultest und ausgeführter Firebase-Ausschnitt mit jsdom.

**Lauf:** 5 bestanden.

**Geprüftes Verhalten:** Bekannte eingeloggte/ausgeloggte Session wird durch gecachtes Token nicht in Skeletonzustand versetzt; benannter Chatladestatus, dekorative Zeilen versteckt. Bookmarkplaceholder bleibt bis Requestabschluss und verschwindet bei leerem oder gefülltem Erfolg.

**Grenzen und Doubles:** Echtes app-bootstrap; loadBookmarks aus Firebase ausgeschnitten, Auth/Fetch und Zeilenrendering ersetzt. Kein tatsächlicher Firebase-Login oder Ladefehlerpfad in dieser Datei.

**Prüfauftrag für den Folgeaudit:** Loginrace, fehlgeschlagene/abgebrochene Bookmarkrequests und vollständige Bootstrapfolge abgleichen.

**Direkte Codeverweise:** [static/firebase.js](../../static/firebase.js), [static/js/app-bootstrap.js](../../static/js/app-bootstrap.js).

**Direkte Testhelfer:** [tests/js/helpers/appWindow.mjs](../../tests/js/helpers/appWindow.mjs).

<details>
<summary>3 Testdefinitionen und ihre Quellstellen</summary>

- [does not overwrite an already resolved session with cached-token placeholders: %o](../../tests/js/skeleton-lifecycle.test.mjs#L21) (Zeile 21)
- [exposes one named chat loading status and hides its decorative lines](../../tests/js/skeleton-lifecycle.test.mjs#L27) (Zeile 27)
- [keeps chat placeholders through the request and removes them on success: %o](../../tests/js/skeleton-lifecycle.test.mjs#L34) (Zeile 34)

</details>

<a id="source-catalog-refs-test-mjs"></a>

## source-catalog-refs.test.mjs

**Quelle:** [tests/js/source-catalog-refs.test.mjs](../../tests/js/source-catalog-refs.test.mjs) · **Bereiche:** Markdown und Darstellung, Quellenprüfung.

**Ebene:** JavaScript-Modultest mit jsdom.

**Lauf:** 4 bestanden.

**Geprüftes Verhalten:** Neue Konsensantwort mit source-references=none lässt numerische Notation wörtlich; Modellantworten und Legacyantworten behalten Links. Dünn besetzte Quellen-IDs per Identität, numerische Normalisierung, mehrdeutige Duplikate unaufgelöst; Positionsfallback nur für Legacyquellen ohne ID.

**Grenzen und Doubles:** Vorgegebene Quellenkataloge und Textstücke; kein Metadatenabruf oder semantischer Belegnachweis.

**Prüfauftrag für den Folgeaudit:** IDs über Backend, Speicherung und Rendering konsistent zuordnen.

**Direkte Codeverweise:** [static/js/sources.js](../../static/js/sources.js).

**Direkte Testhelfer:** [tests/js/helpers/appWindow.mjs](../../tests/js/helpers/appWindow.mjs).

<details>
<summary>4 Testdefinitionen und ihre Quellstellen</summary>

- [keeps numerical notation literal in new consensus while model answers and legacy citations remain linked](../../tests/js/source-catalog-refs.test.mjs#L5) (Zeile 5)
- [resolves sparse IDs by identity and leaves missing citations unresolved](../../tests/js/source-catalog-refs.test.mjs#L14) (Zeile 14)
- [normalizes numeric IDs without resolving ambiguous duplicate IDs](../../tests/js/source-catalog-refs.test.mjs#L20) (Zeile 20)
- [keeps positional lookup solely for legacy entries without an ID](../../tests/js/source-catalog-refs.test.mjs#L27) (Zeile 27)

</details>

<a id="source-teaser-check-test-mjs"></a>

## source-teaser-check.test.mjs

**Quelle:** [tests/js/source-teaser-check.test.mjs](../../tests/js/source-teaser-check.test.mjs) · **Bereiche:** Barrierefreiheit, Quellenprüfung.

**Ebene:** JavaScript-Modulintegration mit jsdom.

**Lauf:** 10 bestanden.

**Geprüftes Verhalten:** Popup zeigt gebundenes Support-/Teil-/Widerspruchs-/Unklar-/Zeit-/Nichtprüfbar-Ergebnis und sicheren Begründungstext; offenes Popup bleibt über Pending, Update, Neurendern und Reset aktuell. Ergebnis nicht von anderer Aussage oder anderem Turn mit derselben ID übernehmen; Tastaturfokus öffnet, Escape schließt ohne Fokusverlust und erhält bestehendes aria-describedby. Aktualisierung 02.10.2026: Gruppenpillen behalten einen Befund pro Quelle und zeigen die stärkste Warnung.

**Grenzen und Doubles:** Echte Sources/Anchor/Verificationmodule, künstliche Findings und DOMevents; keine Mausgeometrie oder Screenreaderprüfung im echten Browser.

**Prüfauftrag für den Folgeaudit:** Quellenbindung und Tooltipzugänglichkeit mit tatsächlichen Antworten prüfen.

**Direkte Codeverweise:** [static/js/consensus-anchor.js](../../static/js/consensus-anchor.js), [static/js/source-verification.js](../../static/js/source-verification.js), [static/js/sources.js](../../static/js/sources.js).

**Direkte Testhelfer:** [tests/js/helpers/appWindow.mjs](../../tests/js/helpers/appWindow.mjs).

<details>
<summary>5 Testdefinitionen und ihre Quellstellen</summary>

- [shows the bound result and safe reason for %j](../../tests/js/source-teaser-check.test.mjs#L25) (Zeile 25)
- [keeps a hovered popup current through pending, checked, rerender and clearing without native titles](../../tests/js/source-teaser-check.test.mjs#L45) (Zeile 45)
- [binds one verdict per source to a grouped pill and shows the most severe one](../../tests/js/source-teaser-check.test.mjs#L65) (Zeile 65)
- [does not borrow the verdict of another statement or turn using the same source ID](../../tests/js/source-teaser-check.test.mjs#L96) (Zeile 96)
- [opens the same tooltip on keyboard focus and dismisses with Escape without stealing focus](../../tests/js/source-teaser-check.test.mjs#L115) (Zeile 115)

</details>

<a id="source-url-identity-test-mjs"></a>

## source-url-identity.test.mjs

**Quelle:** [tests/js/source-url-identity.test.mjs](../../tests/js/source-url-identity.test.mjs) · **Bereiche:** Quellen.

**Ebene:** Quellenmerge und Zitatzählung im jsdom.

**Lauf:** 3 bestanden.

**Geprüftes Verhalten:** Pfad-/Query-Großschreibung und trailing slash unterscheiden Ressourcen; Scheme-/Hostschreibung und Fragment dürfen zusammenfallen, Zitatnummern bleiben zugeordnet.

**Grenzen und Doubles:** Keine reale URL-Auflösung oder Redirectprüfung.

**Prüfauftrag für den Folgeaudit:** Die benannten Mock-/Integrationsgrenzen am realen Adapter prüfen; Zuordnung und offene Aufgaben stehen in der Produktmatrix.

**Direkte Codeverweise:** [app/services/source_catalog.py](../../app/services/source_catalog.py), [static/js/sources.js](../../static/js/sources.js).

<details>
<summary>3 Testdefinitionen und ihre Quellstellen</summary>

- [keeps sources apart that differ only in path or query case](../../tests/js/source-url-identity.test.mjs#L24) (Zeile 24)
- [keeps a trailing slash as part of the resource, like the backend](../../tests/js/source-url-identity.test.mjs#L48) (Zeile 48)
- [still merges URLs that differ only in scheme/host case or fragment](../../tests/js/source-url-identity.test.mjs#L62) (Zeile 62)

</details>

<a id="source-verification-watch-test-mjs"></a>

## source-verification-watch.test.mjs

**Quelle:** [tests/js/source-verification-watch.test.mjs](../../tests/js/source-verification-watch.test.mjs) · **Bereiche:** Authentifizierung, Quellenprüfung, Streaming und Wiederherstellung.

**Ebene:** JavaScript-Modultest mit jsdom, Fetch- und Timer-Doubles.

**Lauf:** 13 bestanden.

**Geprüftes Verhalten:** 403/404 stoppen Updates mit ehrlichem Hinweis und erhalten letzten Snapshot; transiente Fehler erst nach mehreren Versuchen sichtbar, Recovery entfernt Hinweis. Terminale Stubs hydratisieren; Authwechsel/Stop brechen ab und verwerfen Spätantwort. Own-key-Job einmalig mit Schlüssel fortsetzen ohne Schlüssel in Snapshots, Server-key-Job fragt keinen eigenen Schlüssel ab. Alle Seiten vor Veröffentlichung, Auth/Revision gebunden, unveränderte Revision mit Backoff ohne Seitenreload; inkonsistente Pagination neu beginnen, Pending erhält Belege, verstecktes Dokument pausiert. Öffentliche Same-Origin-URLs ohne Credentials, fremde URLs abgewiesen.

**Grenzen und Doubles:** Observer heißt watch, ist hier Quellenjob-Polling, nicht das Watch-Produkt; alle HTTPantworten/Zeitabläufe simuliert.

**Prüfauftrag für den Folgeaudit:** Serverpagination, Revisionswechsel, Hintergrundtab und Own-key-Recovery im Gesamtablauf abgleichen.

**Direkte Codeverweise:** [static/js/source-verification.js](../../static/js/source-verification.js).

**Direkte Testhelfer:** [tests/js/helpers/appWindow.mjs](../../tests/js/helpers/appWindow.mjs).

<details>
<summary>12 Testdefinitionen und ihre Quellstellen</summary>

- [explains a terminal %s refresh failure without changing the saved verdict](../../tests/js/source-verification-watch.test.mjs#L22) (Zeile 22)
- [keeps results during transient failures, explains the third failure and clears its notice on recovery](../../tests/js/source-verification-watch.test.mjs#L42) (Zeile 42)
- [hydrates completed stubs and stops a private observer as soon as auth changes](../../tests/js/source-verification-watch.test.mjs#L66) (Zeile 66)
- [resumes an original own-key job once without adding the key to its snapshots](../../tests/js/source-verification-watch.test.mjs#L84) (Zeile 84)
- [does not automatically supply an own key to a server-key job](../../tests/js/source-verification-watch.test.mjs#L103) (Zeile 103)
- [loads every page before publishing and includes auth and stable revision](../../tests/js/source-verification-watch.test.mjs#L115) (Zeile 115)
- [backs off an unchanged revision and avoids fetching its finding pages again](../../tests/js/source-verification-watch.test.mjs#L130) (Zeile 130)
- [aborts on stop and never publishes a late response into another run](../../tests/js/source-verification-watch.test.mjs#L149) (Zeile 149)
- [restarts inconsistent pagination without publishing mixed versions](../../tests/js/source-verification-watch.test.mjs#L162) (Zeile 162)
- [preserves evidence on pending refresh and pauses when hidden](../../tests/js/source-verification-watch.test.mjs#L175) (Zeile 175)
- [supports public same-origin snapshots without credentials and rejects remote URLs](../../tests/js/source-verification-watch.test.mjs#L192) (Zeile 192)
- [backs off transient failures and stops after denied access](../../tests/js/source-verification-watch.test.mjs#L200) (Zeile 200)

</details>

<a id="source-verification-test-mjs"></a>

## source-verification.test.mjs

**Quelle:** [tests/js/source-verification.test.mjs](../../tests/js/source-verification.test.mjs) · **Bereiche:** Antwortdarstellung, Barrierefreiheit, Quellenprüfung.

**Ebene:** JavaScript-Modulintegration mit jsdom.

**Lauf:** 21 bestanden.

**Geprüftes Verhalten:** Kompakter Quellenstatus und Details über Run-/Ergebniswechsel ehrlich; vollständige Aussagen, klappbare Quellen-/Diagnosedetails und Fokus erhalten. Support getrennt von Themen-/Zeitproblemen; exakte Zitatnavigation mit temporärem Highlight, Originalpassage/Zeit/gebundenen Modellzahlen. Quelljob-Ladezustand, Teilabdeckung, nicht geprüfte Findings und Fehlergründe; sichere Texte/URLs und malformed Findings ohne Zerstören bestehender Claims. Satzbezogene Verweise unabhängig dekoriert, aggregierte Quelle bleibt bei Pending/gemischter Evidenz neutral; spätere Listen, Reset, öffentliche sparse IDs und historische Turns isoliert. Unzitierte Katalogquellen, ausstehende Checks und kompakte Stubs unterschieden.

**Grenzen und Doubles:** Echte Anchor-/Verificationlogik mit vorgegebenen Snapshots; Timer/Scroll teilweise simuliert. Prüft Darstellung/Identitätsbindung, keine Belegwahrheit oder tatsächlichen Quellenabruf.

**Prüfauftrag für den Folgeaudit:** Metadataversionen, Bindungsfehler und alle Backendzustände mit dem Darstellungsvertrag zusammenführen.

**Direkte Codeverweise:** [static/js/consensus-anchor.js](../../static/js/consensus-anchor.js), [static/js/source-verification.js](../../static/js/source-verification.js).

**Direkte Testhelfer:** [tests/js/helpers/appWindow.mjs](../../tests/js/helpers/appWindow.mjs).

<details>
<summary>21 Testdefinitionen und ihre Quellstellen</summary>

- [keeps the compact Sources verdict honest across result and run changes](../../tests/js/source-verification.test.mjs#L16) (Zeile 16)
- [shows full statements directly while source details remain collapsible across updates](../../tests/js/source-verification.test.mjs#L44) (Zeile 44)
- [never presents a single green verdict when topic or time has a problem](../../tests/js/source-verification.test.mjs#L70) (Zeile 70)
- [highlights the exact citation destination, survives updates, retriggers and clears without leaking to another run](../../tests/js/source-verification.test.mjs#L78) (Zeile 78)
- [shows real support, original passages, checked time and bound model evidence without a success tick](../../tests/js/source-verification.test.mjs#L109) (Zeile 109)
- [identifies a document cited by multiple providers as shared evidence](../../tests/js/source-verification.test.mjs#L121) (Zeile 121)
- [keeps completed evidence visible during processing and separates pending from failed work](../../tests/js/source-verification.test.mjs#L128) (Zeile 128)
- [does not combine matching text from a different sentence with model evidence](../../tests/js/source-verification.test.mjs#L140) (Zeile 140)
- [preserves expanded passages and keyboard focus during progressive updates](../../tests/js/source-verification.test.mjs#L146) (Zeile 146)
- [never relabels an old support verdict as thematic fit or repeats its opinion](../../tests/js/source-verification.test.mjs#L155) (Zeile 155)
- [only decorates the relevant S reference, preserving claim and difference nodes and handlers](../../tests/js/source-verification.test.mjs#L164) (Zeile 164)
- [renders unknowns neutrally and restores without accumulating marks](../../tests/js/source-verification.test.mjs#L190) (Zeile 190)
- [communicates pending and clean assessments under Verify sources, including a moved reader panel](../../tests/js/source-verification.test.mjs#L199) (Zeile 199)
- [keeps partial coverage explicit and never gives an unchecked report a checkmark](../../tests/js/source-verification.test.mjs#L217) (Zeile 217)
- [does not turn provider text into HTML or link to unsafe URLs, and contains malformed results](../../tests/js/source-verification.test.mjs#L231) (Zeile 231)
- [marks supported citations immediately but keeps a source with pending claims neutral](../../tests/js/source-verification.test.mjs#L243) (Zeile 243)
- [keeps mixed or unclear source evidence out of green while preserving independent citation verdicts](../../tests/js/source-verification.test.mjs#L262) (Zeile 262)
- [applies results to a late source list and removes green marks on reset without leaking into history](../../tests/js/source-verification.test.mjs#L276) (Zeile 276)
- [summarizes unavailable checks with concrete reasons and counts](../../tests/js/source-verification.test.mjs#L296) (Zeile 296)
- [decorates sparse public source IDs and keeps separate historical turns isolated](../../tests/js/source-verification.test.mjs#L304) (Zeile 304)
- [distinguishes uncited catalogue references from pending checks and compact job stubs](../../tests/js/source-verification.test.mjs#L329) (Zeile 329)

</details>

<a id="sse-completion-test-mjs"></a>

## sse-completion.test.mjs

**Quelle:** [tests/js/sse-completion.test.mjs](../../tests/js/sse-completion.test.mjs) · **Bereiche:** Streaming und Wiederherstellung.

**Ebene:** JavaScript-Streamparser mit simulierten Readern.

**Lauf:** 11 bestanden.

**Geprüftes Verhalten:** Finalframes bei CRLF/CR/LF über einzelne Bytes einschließlich UTF-8 erkannt; final/error beendet vor späterem Lesefehler und räumt Reader auf. consensus.final/Keepalive noch nicht endgültig, terminales event: final erforderlich. Request-, Read-, unvollständiger Stream- und Handlerfehler getrennt, Renderer gestoppt; bewusster Abbruch bleibt AbortError.

**Grenzen und Doubles:** Echtes markdown-stream-Modul, Bytechunks und Reader-/Fetch-/Cleanupfehler vorgegeben; kein Netzwerkproxy oder reale Verbindung. Der Parser verlangt kein Persistenzflag; ein final-Frame belegt keinen DB-Commit.

**Prüfauftrag für den Folgeaudit:** ASGI-/Proxy-Framing und Commit-vor-final-Vertrag serverseitig zuordnen.

**Direkte Codeverweise:** [static/js/markdown-stream.js](../../static/js/markdown-stream.js).

**Direkte Testhelfer:** [tests/js/helpers/appWindow.mjs](../../tests/js/helpers/appWindow.mjs).

<details>
<summary>5 Testdefinitionen und ihre Quellstellen</summary>

- [recognizes final frames with %j line endings across byte boundaries](../../tests/js/sse-completion.test.mjs#L17) (Zeile 17)
- [accepts %s without waiting for a later failing read](../../tests/js/sse-completion.test.mjs#L29) (Zeile 29)
- [keeps reading after consensus.final and keepalives until the persisted final](../../tests/js/sse-completion.test.mjs#L43) (Zeile 43)
- [distinguishes %s and stops renderers](../../tests/js/sse-completion.test.mjs#L56) (Zeile 56)
- [preserves deliberate cancellation as AbortError](../../tests/js/sse-completion.test.mjs#L71) (Zeile 71)

</details>

<a id="stored-turn-markers-test-mjs"></a>

## stored-turn-markers.test.mjs

**Quelle:** [tests/js/stored-turn-markers.test.mjs](../../tests/js/stored-turn-markers.test.mjs) · **Bereiche:** Bookmarks und Verlauf, Konsens und Unterschiede.

**Ebene:** JavaScript-Modulintegration mit jsdom.

**Lauf:** 7 bestanden.

**Geprüftes Verhalten:** Widerspruch bleibt an richtiger historischer Aussage und wird nicht zur bloßen Supportquote; Aktivierung öffnet Unterschiedskarte desselben Turns, nicht aktuellen Footer. Bloß geteilter Claim behält Verhältnis und zugängliches Label. Aktualisierung 02.10.2026: Schweregrad zuerst, einwortige Labels und stabile Differenceindizes; Modelllinks nur bei erreichbarer Antwort, Markerklick öffnet über Datenindex.

**Grenzen und Doubles:** Vorgegebener historischer DOM und Analysedaten; keine Bookmarkpersistenz oder tatsächlicher Reload.

**Prüfauftrag für den Folgeaudit:** Mehrere gespeicherte Turns und echte Quellen-/Readerintegration abgleichen.

**Direkte Codeverweise:** [static/js/consensus-anchor.js](../../static/js/consensus-anchor.js), [static/js/consensus-insights.js](../../static/js/consensus-insights.js).

**Direkte Testhelfer:** [tests/js/helpers/appWindow.mjs](../../tests/js/helpers/appWindow.mjs).

<details>
<summary>7 Testdefinitionen und ihre Quellstellen</summary>

- [keeps the contradiction line on the disputed sentence](../../tests/js/stored-turn-markers.test.mjs#L92) (Zeile 92)
- [does not downgrade the contradiction to a support ratio](../../tests/js/stored-turn-markers.test.mjs#L99) (Zeile 99)
- [opens the difference card of its own turn, not the live footer](../../tests/js/stored-turn-markers.test.mjs#L106) (Zeile 106)
- [still shows the support ratio for a merely split claim](../../tests/js/stored-turn-markers.test.mjs#L121) (Zeile 121)
- [orders critical first, names severity in one word and keeps the data index](../../tests/js/stored-turn-markers.test.mjs#L152) (Zeile 152)
- [puts each position's models on one line, as jump links only when an answer is reachable](../../tests/js/stored-turn-markers.test.mjs#L166) (Zeile 166)
- [opens the card of the clicked marker by data index, not by card position](../../tests/js/stored-turn-markers.test.mjs#L190) (Zeile 190)

</details>

<a id="thread-question-disclosure-test-mjs"></a>

## thread-question-disclosure.test.mjs

**Quelle:** [tests/js/thread-question-disclosure.test.mjs](../../tests/js/thread-question-disclosure.test.mjs) · **Bereiche:** Antwortdarstellung, Composer.

**Ebene:** JavaScript-Modultest mit jsdom.

**Lauf:** 2 bestanden.

**Geprüftes Verhalten:** Wiederholte Projektion derselben langen Frage erhält geöffneten Zustand, Beschriftung und aria-expanded; tatsächlich neue Frage setzt Disclosure/Langmarkierung zurück.

**Grenzen und Doubles:** DOMhöhe/Umgebung simuliert; keine tatsächliche Textumbruchmessung oder vollständige Runprojektion.

**Prüfauftrag für den Folgeaudit:** Lange Fragen, Responsivewechsel und Bookmarks im echten Layout zuordnen.

**Direkte Codeverweise:** [static/js/app-core.js](../../static/js/app-core.js).

**Direkte Testhelfer:** [tests/js/helpers/appWindow.mjs](../../tests/js/helpers/appWindow.mjs).

<details>
<summary>2 Testdefinitionen und ihre Quellstellen</summary>

- [stays open when a running context projects the same question again](../../tests/js/thread-question-disclosure.test.mjs#L34) (Zeile 34)
- [resets the disclosure when the projected question actually changes](../../tests/js/thread-question-disclosure.test.mjs#L58) (Zeile 58)

</details>

<a id="topic-page-test-mjs"></a>

## topic-page.test.mjs

**Quelle:** [tests/js/topic-page.test.mjs](../../tests/js/topic-page.test.mjs) · **Bereiche:** Topics, Sicherheit.

**Ebene:** jsdom-Checkstrip und Returning-Reader-Band.

**Lauf:** 7 bestanden.

**Geprüftes Verhalten:** HTMLartige Notizen/Datumswerte werden als Text angezeigt; kein eingeschleustes Bild/Eventhandler, korrekte Score-/Unscoredanzeige und Rückkehr zur Serverzeile.

**Grenzen und Doubles:** Keine echte CSP-/Browserangriffskette; öffentliche Route separat als Quelltext/HTTP geprüft.

**Prüfauftrag für den Folgeaudit:** Die benannten Mock-/Integrationsgrenzen am realen Adapter prüfen; Zuordnung und offene Aufgaben stehen in der Produktmatrix.

**Direkte Codeverweise:** [static/js/topic-page.js](../../static/js/topic-page.js).

<details>
<summary>5 Testdefinitionen und ihre Quellstellen</summary>

- [`shows HTML-like notes literally on ${label}`](../../tests/js/topic-page.test.mjs#L57) (Zeile 57)
- [keeps the bold date and the score formatting](../../tests/js/topic-page.test.mjs#L72) (Zeile 72)
- [omits the score for an unscored cell](../../tests/js/topic-page.test.mjs#L83) (Zeile 83)
- [restores the server-rendered resting line after leaving the strip](../../tests/js/topic-page.test.mjs#L89) (Zeile 89)
- [builds the returning-reader band from text, including hostile dates](../../tests/js/topic-page.test.mjs#L99) (Zeile 99)

</details>

<a id="user-memory-test-mjs"></a>

## user-memory.test.mjs

**Quelle:** [tests/js/user-memory.test.mjs](../../tests/js/user-memory.test.mjs) · **Bereiche:** Einstellungen, Nutzergedächtnis.

**Ebene:** JavaScript-Modultest mit jsdom und Auth-/Fetch-Doubles.

**Lauf:** 6 bestanden.

**Geprüftes Verhalten:** Gespeichertes Profil in Formular geladen; Ausschalten sendet enabled=false mit vollständigen sechs Profilfeldern und bleibt ausgeschaltet; reiner Schalterwrite erhält gespeicherte Rolle/Notizen. Aktualisierung 02.10.2026: 409 bewahrt lokalen Entwurf und bietet Reload; bewusstes Überschreiben benötigt neueste Revision, KI-Reload löscht ungespeicherten Entwurf nicht.

**Grenzen und Doubles:** Künstliche GET-/PUTantworten, keine Datenbank, Servervalidierung oder Promptinjektion.

**Prüfauftrag für den Folgeaudit:** Kontenwechsel, Speicherkonflikte/-fehler und tatsächliche Promptverwendung abgleichen.

**Direkte Codeverweise:** [static/js/user-memory.js](../../static/js/user-memory.js).

**Direkte Testhelfer:** [tests/js/helpers/appWindow.mjs](../../tests/js/helpers/appWindow.mjs).

<details>
<summary>6 Testdefinitionen und ihre Quellstellen</summary>

- [loads the stored profile into the form](../../tests/js/user-memory.test.mjs#L99) (Zeile 99)
- [turns memory off and stays off](../../tests/js/user-memory.test.mjs#L104) (Zeile 104)
- [keeps the saved text when only the switch is written](../../tests/js/user-memory.test.mjs#L121) (Zeile 121)
- [keeps the draft and offers reload when another writer won](../../tests/js/user-memory.test.mjs#L187) (Zeile 187)
- [can deliberately overwrite the newer Memory with the kept draft](../../tests/js/user-memory.test.mjs#L210) (Zeile 210)
- [an AI edit reload does not wipe an unsaved settings draft](../../tests/js/user-memory.test.mjs#L226) (Zeile 226)

</details>

<a id="watch-dashboard-state-test-mjs"></a>

## watch-dashboard-state.test.mjs

**Quelle:** [tests/js/watch-dashboard-state.test.mjs](../../tests/js/watch-dashboard-state.test.mjs) · **Bereiche:** Watches, Frontend.

**Ebene:** jsdom-Dashboard mit Serverzustandsfixtures.

**Lauf:** 5 bestanden.

**Geprüftes Verhalten:** Moved ausschließlich aus Serverurteil samt Belegen, Held bleibt stehende Antwort, Recheck/Resolved/Ziel und letzter Move werden richtig dargestellt; Gruppen Watching/Resolved/Delivery ohne Score.

**Grenzen und Doubles:** Keine echte Watch-API, Zustellung oder Browsergeometrie.

**Prüfauftrag für den Folgeaudit:** Die benannten Mock-/Integrationsgrenzen am realen Adapter prüfen; Zuordnung und offene Aufgaben stehen in der Produktmatrix.

**Direkte Codeverweise:** [static/js/watch-dashboard.js](../../static/js/watch-dashboard.js), [static/js/watch-state.js](../../static/js/watch-state.js), [static/js/watch.js](../../static/js/watch.js).

<details>
<summary>5 Testdefinitionen und ihre Quellstellen</summary>

- [reads moved only from the server verdict, with the sources that carry it](../../tests/js/watch-dashboard-state.test.mjs#L36) (Zeile 36)
- [never presents a held answer as a change](../../tests/js/watch-dashboard-state.test.mjs#L50) (Zeile 50)
- [names a pending re-check and a resolved goal](../../tests/js/watch-dashboard-state.test.mjs#L63) (Zeile 63)
- [falls back to the last move while the answer is steady](../../tests/js/watch-dashboard-state.test.mjs#L76) (Zeile 76)
- [groups watches and shows the goal with its status](../../tests/js/watch-dashboard-state.test.mjs#L95) (Zeile 95)

</details>

<a id="watch-feature-nudge-test-mjs"></a>

## watch-feature-nudge.test.mjs

**Quelle:** [tests/js/watch-feature-nudge.test.mjs](../../tests/js/watch-feature-nudge.test.mjs) · **Bereiche:** Composer, Watch.

**Ebene:** JavaScript-Modulintegration mit jsdom.

**Lauf:** 3 bestanden.

**Geprüftes Verhalten:** Hinweis erst bei dritter Frage; nur Hinweis wird an body über Composer angehängt, Antwort erhält keine entsprechende Hochstufung; Positionswerte gesetzt, Schließen entfernt Hinweis und Ankermarkierung.

**Grenzen und Doubles:** Timer manuell ausgelöst, künstlicher DOM/Geometrie und Fetchdouble; keine tatsächliche Überlagerungs- oder Sichtbarkeitsmessung.

**Prüfauftrag für den Folgeaudit:** Mobile Überdeckung, Wiederholungs-/Kontenpräferenz und Tastaturbedienung zuordnen.

**Direkte Codeverweise:** [static/js/watch-state.js](../../static/js/watch-state.js), [static/js/watch.js](../../static/js/watch.js).

**Direkte Testhelfer:** [tests/js/helpers/appWindow.mjs](../../tests/js/helpers/appWindow.mjs).

<details>
<summary>3 Testdefinitionen und ihre Quellstellen</summary>

- [haelt sich bis zur dritten Frage zurueck](../../tests/js/watch-feature-nudge.test.mjs#L73) (Zeile 73)
- [portaliert nur den Hinweis ueber den Composer, nie die Antwort](../../tests/js/watch-feature-nudge.test.mjs#L84) (Zeile 84)
- [nimmt die Markierung beim Schliessen wieder zurueck](../../tests/js/watch-feature-nudge.test.mjs#L98) (Zeile 98)

</details>

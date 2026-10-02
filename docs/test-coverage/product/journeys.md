# Nutzerreisen über die Testgrenzen hinweg

[Einstieg](README.md) · [WP-29](work-packages.md#wp-29)

Die Tabelle beschreibt interne Datenketten und fehlende gemeinsame Nachweise.
Sie behauptet nicht, dass jede genannte Teilfunktion ungetestet ist.
Der vorhandene Dateikatalog dokumentiert die umfangreichen Detailtests.
Stand 02.10.2026: Laufstatus und Fehler der einzelnen Teilbelege stehen im
[Laufbericht](../findings.md); diese Tabelle behauptet keinen bestandenen
Gesamtlauf jeder Reise.
Für vollständige Integrationsfälle externe Identitäts-/Modell-/Nachrichtendienste
deterministisch ersetzen, Appcode, interne HTTP-Routen und lokale Persistenz
dagegen tatsächlich ausführen.

| ID / Ablauf | Interne Kette | Bereits vorhandener Teilbeleg | Noch getrennte Grenze / nächster Nachweis |
|---|---|---|---|
| J-01 Consensus speichern und fortsetzen | Querysend → Chat/Turn/Context → prepare/ask → consensus → Turnabschluss/Bookmark → Reload/Follow-up | [Chat-/Consensus-Integration](../../../tests/test_consensus_chat_history.py), [Kontext](../../../tests/test_chat_context.py), [Bookmarks](../../../tests/test_bookmarks.py), [Phase4](../../../tests/e2e/test_phase4_frontend.py) | Backend mit Fake-DB beziehungsweise Browser mit ersetzten APIs; vollständige gespeicherte Daten nach Reload in echtem AppFirebase lesen |
| J-02 Agent stoppen und wiederherstellen | Agentansicht → Auth/Admission → Receipts/Provider → Teilantwort/Settlement → Stop/Status → Reload | [Reliability](../../../tests/test_agent_reliability.py), [Continuation](../../../tests/test_agent_continuation.py), [native Transaktionen](../../../tests/e2e/test_agent_transactions.py), [Agentbrowser](../../../tests/e2e/test_agent_chat_frontend.py) | Native Ledgerfälle und Browserpayloads noch getrennt; gleiche Run-/Turn-/Owner-ID und kein zweiter Modellstart beim Recover gemeinsam nachweisen |
| J-03 Quellen später nachladen | Consensusabschluss → Job/Packagelease → Quellenfetch/Judge → Resultrevision → UI-GET/Resume → historischer Snapshot | [Jobs](../../../tests/test_source_check_jobs.py), [Repository](../../../tests/test_source_check_repository.py), [API](../../../tests/test_source_check_api.py), [Scope](../../../tests/test_source_check_scope.py) | Native Queuekonkurrenz und UI-Pagination bei realen Revisionswechseln fehlen als gemeinsamer Nachweis; WP-14 und WP-29 |
| J-04 Ergebnis teilen und beobachten | eigener Pending-Result → App-Share-POST → versionierte öffentliche Seite → Follow/Watch → neuer Run → Versionsansicht | [Shares](../../../tests/test_share_feature.py), [Watches](../../../tests/test_watch_feature.py), [Share-/Followbrowser](../e2e.md) | App-Share-HTTP-Adapter und native Pending-/Watchfixtures schließen; anschließend UI und gespeicherte Sichtbarkeit/Version verbinden |
| J-05 Konto wechseln/löschen während Arbeit läuft | Session A → laufender Turn/Memoryedit → Tombstone/Kaskade → späte Antwort → Session B/Reload | [Löschretry](../../../tests/test_account_deletion_retry.py), [Session/Ownerbrowser](../../../tests/e2e/test_phase4_frontend.py), [Memoryedit](../../../tests/test_memory_edit.py) | Aktuelle Kontokaskade und konkrete Late-Writes real ausführen; fremden Kontrollowner und UI-Projektion gemeinsam prüfen |
| J-06 Adminrevision beeinflusst nächsten Lauf | Admin laden → zwei lokale Entwürfe → versionierter Save → Konflikt/Reload → nächster Run nutzt neuen Snapshot | [Promptconfig](../../../tests/test_prompt_config.py), [native Revision](../../../tests/e2e/test_prompt_config_transactions.py), [Promptbrowser](../../../tests/e2e/test_admin_prompt_config.py) | Browserpayload nutzt vereinfachten Fehlerumschlag; tatsächliche main-Fehlerform und Runtimekonfiguration an gemeinsamer Grenze prüfen |
| J-07 Publisher überlebt Wiederaufnahme | Config/Keyscope → API-Run → Poll/Restart → Publish → Publisherwatch → Indexierungsstatus | [API](../../../tests/test_consensus_api.py), [Repository](../../../tests/test_api_run_repository.py), [Standalonepublisher](../../../tests/test_publisher_standalone.py) | Runner-Recovery/Retention und API-Cleanup direkt ausführen; historische Sourcejobs von neuen sourcefreien Produktruns unterscheiden |
| J-08 Topiccheck aktualisiert öffentliche Historie | Admin/Zeitslot → native Claim → Topicpipeline/Identity → versionierter Run/Ledger → SSR → Check-Strip/Follow | [Topics](../../../tests/test_topics_feature.py), [Claimledger](../../../tests/test_claim_ledger.py), [Historydarstellung](../../../tests/test_unscored_history.py) | Echte Admin-/Due-/Identityadapter und Topic-JS ausführen; wörtliche Notiz, Version/Seen-Marker und Followzustand gemeinsam prüfen |

## Neu ergänzte Reisen

| ID / Ablauf | Interne Kette | Vorhandener Teilbeleg | Noch getrennte Grenze |
|---|---|---|---|
| J-09 Datei zu versioniertem Dokument | Upload → private Ablage/Extraktion → Modellkontext/Vergleich → DOCX/PDF → Version → Nachricht/Download/Löschung | `test_agent_files.py`, `test_agent_documents.py`, Workspace-DOM/Browser | Echter Cloudadapter, atomare Metadaten-/Objektkaskade und visuelle Dokumentseiten; G-044 |
| J-10 Google lesen und Aktion bestätigen | OAuth/PKCE → Scope → Zustimmung → Kalender/Gmail → Vorschlag → exakter Hash → Write/unknown → Reconcile | Google-/Calendar-/Gmail-Services, Aktions-DOM/Browser; Gmail-Agentloop verbindet Angebote und Dokumententwurf | Browser/HTTP/DB gemeinsam, native Claims und echte OAuth-Konfiguration; G-043 |
| J-11 Gemeinsames Tokenkonto | Tier/Modus → Admission/Hold → parallele Operationen → Meter/Schätzung → Final/Release → Nachmessung/UTC-Tag → UI | Usage-Meter/-Repository/-Endpoints, Agent-Reconciliation, Sidebar-DOM | Native gemeinsame Transaktion und Live-Abrechnungsdaten; G-002 |
| J-12 Watch vom Beleg zur Zustellung | Probe → Vollcheck → Evidenceverifikation/Recheck → stehende oder neue Antwort/Zielabschluss → Outboxcommit → Retry/Unsubscribe | Watch-Evidence-/Review-Regressionen und Dashboard-DOM | Echte SDK-Claims/Retry und integrierte Browser-/Zustellreise; G-045 |

J-05: Die aktuelle
Kaskade umfasst zusätzlich unter anderem Googlegrants/Aktionen, Dokumente,
Antwortreceipts und Outbox. J-07 besitzt neue Recovery-/Billing-Identity-Tests;
vollständiger Restart/Retention bleibt offen. J-08 besitzt inzwischen einen
Topic-JS-Nachweis für wörtliche Notizen und Seen-Marker; native Admin-/Due-/
Identityintegration bleibt davon getrennt.

## Gemeinsame Assertions für die neuen Integrationsfälle

- UI-Ergebnis nach Reload aus gespeicherten Daten ableiten; keine erwartete
  Komplettpayload direkt in die App injizieren.
- Exakte Owner-, Chat-, Turn-, Kontext-, Run-, Job- und Antwortversionsbindung
  an jeder relevanten Grenze prüfen. Zweiten Owner und zweiten Run mit
  unterscheidbaren Daten vorhalten.
- Persistierte Antwort, Fortschritt, Status und sichtbare Fehlermeldung
  müssen zusammenpassen. „Erfolgreiche Antwort, Persistenzfehler“ ist ein
  eigener Zustand; keine erfolgreiche Antwort durch generischen Fehler verlieren.
- Nach Stop/Reload/Retry keinen zusätzlichen Providerdispatch oder Usage-Charge
  erlauben, wo Replay zugesagt ist. Gleichzeitig bereits angefallene reale
  Kosten nicht aus der Ledgererwartung löschen.
  Die einmalige reguläre Runbelastung von der Agent-Abrechnung tatsächlich
  angefallener Providersteps unterscheiden; nicht einen pauschalen Charge
  für jede Agentausführung erwarten.
- Reihenfolge/Verzögerung am Testserver kontrollieren; keine beliebigen Sleeps.
  Bei Fehlern Status-/ID-Abfolge, relevanten DB-Endzustand und Browsertrace
  sichern, ohne Credentials oder reale Nutzerdaten.

## Auswahl und Zuständigkeit

WP-29 beginnt mit J-01/J-02. J-03/J-04/J-05 folgen auf die jeweils benötigten
Queue-, Share- und Löschpakete; J-05 setzt WP-09 zusätzlich voraus.
J-06 ergänzt WP-21, J-07 WP-11 und J-08 WP-16/WP-17/WP-19/WP-20.
Diese Abhängigkeiten sind keine Forderung, jeden Detailfall als langsamen
Browsertest zu duplizieren. Die neuen durchgängigen Fälle konzentrieren sich
auf tatsächlich bislang getrennte Datenübergänge; Detailvarianten bleiben
auf ihrer geeigneten Unit-/Service-/Routerebene.

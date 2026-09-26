# Codex-Arbeitspakete

[Einstieg](README.md) · [Befunde](gaps.md) · [Nutzerreisen](journeys.md) · [Oracles](decisions.md)

Alle **30 Pakete sind geplant**, keines in diesem Dokumentationsauftrag implementiert. Die IDs sind stabil; sie geben keine zwingende lineare Reihenfolge vor. Abhängigkeiten sind fachliche/technische Voraussetzungen. Vorarbeit ist früher möglich. WP-01 bis WP-04 klären den Ausgangsstand; WP-05 macht die allgemeine CI verbindlich. WP-06 bis WP-14 sowie WP-20 schützen besonders folgenreiche Grenzen. WP-29 folgt auf tragfähige Adapter-/Persistenztests. Die restlichen Pakete bleiben im Gesamtumfang.

## Gemeinsamer Auftrag und Abnahme

Ein Paket anhand seiner ID auswählen. Zuerst `check_product_audit.py` und den bisherigen Inventarcheck ausführen. Bei Drift betroffene Code-/Testkörper erneut lesen; Hashes nicht blind aktualisieren. Produktvertrag, Given/When/Then und vorhandene Testhelfer lesen. Den kleinsten geeigneten Test ergänzen, der das reale Verhalten an der benannten Grenze ausführt. Nur äußere Abhängigkeiten ersetzen; den zu prüfenden Guard/Adapter nicht mocken. Bei beobachtetem Produktfehler zuerst roten Regressionstest festhalten und dann begründet korrigieren.

Jedes Paket verlangt die verknüpften Then-Bedingungen, mindestens eine fachliche Negativkontrolle (temporäre Mutation nur lokal/in isoliertem Prozess), passende fokussierte Regressionen und erforderliche Repo-Gates. Ein Statuscode/Mockaufruf ersetzt keinen benötigten DB-/UI-Endzustand. Konkurrenz mit Barrieren/Fakeuhr steuern; keine Sleeps als Erfolgsbedingung. Unabhängige Owner-/Run-/Versionskontrollwerte verwenden. Testdoubles an realer SDK-/HTTP-Form ausrichten.

Bei neuen Tests die Runner-Discovery kontrollieren. Nach Änderungen unter `static/` Build und öffentliche Cachebuster nach AGENTS.md pflegen; bei Änderungen von Architektur/Flows `docs/codebase-map.md` im selben Auftrag aktualisieren. Keine echten Provider-/Produktdatenzugriffe in Regressionen. Fehlende Umgebung als offen dokumentieren, nicht als Erfolg umetikettieren.

Abschluss pro Paket in `audit.json`: Status `completed`, Implementierungscommit und konkrete Validierungsevidenz (Befehle, Umgebung, Pass/Fail/Skip, Negativkontrolle, Restgrenze). Bei Teilabschluss `in_progress` oder `blocked` mit Grund. Originale Audit-/Laufhistorie erhalten; fachliche Matrix, neuer Testkatalog und aktuelle Nachweise bewusst fortschreiben.

| Paket | Ziel | Priorität | Vorher | Befunde | Status |
|---|---|---|---|---|---|
| [WP-01](#wp-01) | Bekannte Fixture- und Stringfehler bereinigen | P1 | — | [G-027](gaps.md#g-027), [G-028](gaps.md#g-028) | planned |
| [WP-02](#wp-02) | Report-Race unter kontrollierter Emulatorumgebung klären | P1 | [WP-01](work-packages.md#wp-01) | [G-029](gaps.md#g-029) | planned |
| [WP-03](#wp-03) | Bestehende Browserfälle tatsächlich ausführen | P1 | [WP-01](work-packages.md#wp-01) | [G-025](gaps.md#g-025) | planned |
| [WP-04](#wp-04) | Windows-Einstieg verifizieren | P2 | — | [G-026](gaps.md#g-026) | planned |
| [WP-05](#wp-05) | Allgemeine Regression-CI einrichten | P1 | [WP-01](work-packages.md#wp-01), [WP-02](work-packages.md#wp-02), [WP-03](work-packages.md#wp-03), [WP-04](work-packages.md#wp-04) | [G-024](gaps.md#g-024) | planned |
| [WP-06](#wp-06) | Firestore-Regeln durch echte Clientoperationen schützen | P1 | [WP-01](work-packages.md#wp-01) | [G-001](gaps.md#g-001) | planned |
| [WP-07](#wp-07) | Reguläre Usage nativ atomar prüfen | P1 | [WP-01](work-packages.md#wp-01) | [G-002](gaps.md#g-002) | planned |
| [WP-08](#wp-08) | Chat-Lebenszyklus gegen späte Writes absichern | P1 | [WP-01](work-packages.md#wp-01) | [G-003](gaps.md#g-003) | planned |
| [WP-09](#wp-09) | Kontokaskade und API-Cleanup integrieren | P1 | [WP-08](work-packages.md#wp-08), [WP-11](work-packages.md#wp-11) | [G-004](gaps.md#g-004) | planned |
| [WP-10](#wp-10) | Memory-Revision, Undo und Löschsperre stärken | P1 | [WP-01](work-packages.md#wp-01) | [G-007](gaps.md#g-007), [G-008](gaps.md#g-008) | planned |
| [WP-11](#wp-11) | API-Recovery und historischen Source-Adapter prüfen | P1 | — | [G-005](gaps.md#g-005), [G-010](gaps.md#g-010) | planned |
| [WP-12](#wp-12) | Registrierungsrace und user_status verbinden | P1 | — | [G-009](gaps.md#g-009), [G-012](gaps.md#g-012) | planned |
| [WP-13](#wp-13) | App-Share-POST integrieren | P1 | [WP-01](work-packages.md#wp-01) | [G-011](gaps.md#g-011) | planned |
| [WP-14](#wp-14) | Source-Queue mit nativen Leases prüfen | P1 | [WP-01](work-packages.md#wp-01) | [G-006](gaps.md#g-006) | planned |
| [WP-15](#wp-15) | Watch- und Telegramadapter schließen | P2 | — | [G-013](gaps.md#g-013) | planned |
| [WP-16](#wp-16) | Topic-Administration und öffentliche Adapter schließen | P1 | — | [G-014](gaps.md#g-014) | planned |
| [WP-17](#wp-17) | Claim-Identity-Judge validieren | P2 | — | [G-016](gaps.md#g-016) | planned |
| [WP-18](#wp-18) | SEO-Repositoryadapter ausführen | P2 | — | [G-017](gaps.md#g-017) | planned |
| [WP-19](#wp-19) | Schedulerqueries und persistente Claims prüfen | P2 | [WP-01](work-packages.md#wp-01) | [G-031](gaps.md#g-031) | planned |
| [WP-20](#wp-20) | Topic-Notizen als Text absichern | P1 | — | [G-018](gaps.md#g-018) | planned |
| [WP-21](#wp-21) | Adminfehler aus dem echten Appumschlag anzeigen | P2 | — | [G-019](gaps.md#g-019) | planned |
| [WP-22](#wp-22) | Benchmark-Adminadapter und Viewer prüfen | P2 | — | [G-015](gaps.md#g-015) | planned |
| [WP-23](#wp-23) | Inhalt der OG-Karte wirksam prüfen | P2 | — | [G-020](gaps.md#g-020) | planned |
| [WP-24](#wp-24) | Analytics-Opt-out dynamisch prüfen | P2 | — | [G-021](gaps.md#g-021) | planned |
| [WP-25](#wp-25) | Wartungsskripte isoliert absichern | P1 | — | [G-022](gaps.md#g-022), [G-023](gaps.md#g-023) | planned |
| [WP-26](#wp-26) | HTTP-Body- und lokale Transportgrenzen ergänzen | P2 | — | [G-032](gaps.md#g-032), [G-033](gaps.md#g-033) | planned |
| [WP-27](#wp-27) | Feedback und Statistikwrites verbinden | P2 | — | [G-034](gaps.md#g-034) | planned |
| [WP-28](#wp-28) | Unterstützte Hilfs-CLIs prüfen | P3 | — | [G-035](gaps.md#g-035) | planned |
| [WP-29](#wp-29) | Persistierte Nutzerreisen durch alle internen Schichten prüfen | P1 | [WP-03](work-packages.md#wp-03), [WP-07](work-packages.md#wp-07), [WP-08](work-packages.md#wp-08), [WP-09](work-packages.md#wp-09), [WP-10](work-packages.md#wp-10), [WP-12](work-packages.md#wp-12), [WP-13](work-packages.md#wp-13), [WP-14](work-packages.md#wp-14) | [G-030](gaps.md#g-030) | planned |
| [WP-30](#wp-30) | Vendorhelper mit echtem temporärem Dateisystem prüfen | P2 | — | [G-036](gaps.md#g-036) | planned |

<a id="wp-01"></a>

## WP-01 · Bekannte Fixture- und Stringfehler bereinigen

**Ziel:** F-01/F-02/F-03 erreichen wieder ihren eigentlichen Prüfvertrag.

**Befunde:** [G-027](gaps.md#g-027), [G-028](gaps.md#g-028) · **Vorher:** —

**Vorgehen:** Aktuelle Produktionsvalidierung lesen; gültige Pending-/Watchdaten herstellen, Footer fachlich statt über exakten Klassenstring prüfen. Erst fehlschlagende Ausgangsläufe festhalten.

**Abnahme zusätzlich zu den verknüpften Then-/Negativkontrollen:** Alle drei Altfehler erklärt und gezielt grün; Race-/Aktionsassertions mindestens gleich stark; keine gelockerten Produktguards, Skips oder pauschalen Snapshots.

**Produktstellen:** [static/js/consensus-run.js](../../../static/js/consensus-run.js), [tests/e2e/test_phase2_transactions.py](../../../tests/e2e/test_phase2_transactions.py), [tests/test_consensus_progress_ui.py](../../../tests/test_consensus_progress_ui.py)

**Test-/Dokumentziele:** [tests/e2e/test_phase2_transactions.py](../../../tests/e2e/test_phase2_transactions.py), [tests/js/stored-turn-markers.test.mjs](../../../tests/js/stored-turn-markers.test.mjs), [tests/test_consensus_progress_ui.py](../../../tests/test_consensus_progress_ui.py)

**Vorhandene Hilfen:** [app/services/share_snapshots.py](../../../app/services/share_snapshots.py), [app/services/watch_service.py](../../../app/services/watch_service.py), [tests/e2e/test_reader_review_regressions.py](../../../tests/e2e/test_reader_review_regressions.py)

**Befehle/Prüfauftrag nach Implementierung:**

- ` RUN_E2E=1 python -m pytest tests/e2e/test_phase2_transactions.py -q (Demo-Emulator) `
- ` python -m pytest tests/test_consensus_progress_ui.py -q; npm test -- tests/js/stored-turn-markers.test.mjs `

**Zu beachten:** —


<a id="wp-02"></a>

## WP-02 · Report-Race unter kontrollierter Emulatorumgebung klären

**Ziel:** Ursache des abweichenden Parallelreport-Laufs ermitteln.

**Befunde:** [G-029](gaps.md#g-029) · **Vorher:** [WP-01](work-packages.md#wp-01)

**Vorgehen:** Java21/Emulator dokumentieren, Kontamination zwischen Fällen ausschließen; isolierten und vollständigen Transaktionslauf mit gleichen IDs-/Zeitregeln vergleichen. Nur gezielte begrenzte Wiederholungen.

**Abnahme zusätzlich zu den verknüpften Then-/Negativkontrollen:** Root-Cause oder eng belegter verbleibender Umgebungsblocker, Result-/Counter-/noindex-Assertions, nachvollziehbarer Wiederholungslauf. Kein unbegründetes Retry-Tuning.

**Produktstellen:** [tests/e2e/test_phase2_transactions.py](../../../tests/e2e/test_phase2_transactions.py)

**Test-/Dokumentziele:** [tests/e2e/test_phase2_transactions.py](../../../tests/e2e/test_phase2_transactions.py)

**Vorhandene Hilfen:** [docs/test-coverage/findings.md](../findings.md), [tests/e2e/README.md](../../../tests/e2e/README.md)

**Befehle/Prüfauftrag nach Implementierung:**

- ` RUN_E2E=1 python -m pytest tests/e2e/test_phase2_transactions.py -v (danach betroffenen Test isoliert) `

**Zu beachten:** —


<a id="wp-03"></a>

## WP-03 · Bestehende Browserfälle tatsächlich ausführen

**Ziel:** Aktuellen Status der 267 bestehenden Browserfälle gewinnen.

**Befunde:** [G-025](gaps.md#g-025) · **Vorher:** [WP-01](work-packages.md#wp-01)

**Vorgehen:** Chromium passend zu Playwright installieren, Build und sichere E2E-Voraussetzungen prüfen. Vollständige Suite ausführen, echte Produkt-/Fixture-/Infrastrukturfehler getrennt bearbeiten.

**Abnahme zusätzlich zu den verknüpften Then-/Negativkontrollen:** 267 Fälle zugeordnet, kein unbemerkter Collect-/Skipverlust; Browser- und Appversion, JUnit und gezielte Fehlerscreenshots/Traces vorhanden. Neue Fälle separat zählen.

**Produktstellen:** [tests/e2e/conftest.py](../../../tests/e2e/conftest.py)

**Test-/Dokumentziele:** [docs/test-coverage/execution.json](../execution.json), [tests/e2e](../../../tests/e2e)

**Vorhandene Hilfen:** [docs/testing.md](../../testing.md), [tests/e2e/README.md](../../../tests/e2e/README.md)

**Befehle/Prüfauftrag nach Implementierung:**

- ` python -m playwright install chromium; RUN_E2E=1 python -m pytest tests/e2e -q (sicheres vollständiges Emulatorprofil) `

**Zu beachten:** [D-05](decisions.md#d-05)


<a id="wp-04"></a>

## WP-04 · Windows-Einstieg verifizieren

**Ziel:** Die zwölf Linux-Skips durch Windows-Evidenz ergänzen.

**Befunde:** [G-026](gaps.md#g-026) · **Vorher:** —

**Vorgehen:** Vorhandene CLI-Doubles auf unterstütztem Windows/PowerShell ausführen; echte repräsentative dev.ps1-Aufrufe ergänzen, ohne eine zweite Suiteauswahl zu pflegen.

**Abnahme zusätzlich zu den verknüpften Then-/Negativkontrollen:** Zwölf Fälle wirklich ausgeführt; Fehlercodes, Argumente, Arbeitsverzeichnis und Envwiederherstellung belegt; konkrete PowerShellversion dokumentiert.

**Produktstellen:** [dev.ps1](../../../dev.ps1)

**Test-/Dokumentziele:** ` .github/workflows/tests.yml ` (vorgeschlagen), [tests/test_dev_cli.py](../../../tests/test_dev_cli.py)

**Vorhandene Hilfen:** [dev.ps1](../../../dev.ps1), [docs/testing.md](../../testing.md)

**Befehle/Prüfauftrag nach Implementierung:**

- ` Windows: python -m pytest tests/test_dev_cli.py -q `

**Zu beachten:** —


<a id="wp-05"></a>

## WP-05 · Allgemeine Regression-CI einrichten

**Ziel:** Neue Tests zuverlässig bei Änderungen ausführen.

**Befunde:** [G-024](gaps.md#g-024) · **Vorher:** [WP-01](work-packages.md#wp-01), [WP-02](work-packages.md#wp-02), [WP-03](work-packages.md#wp-03), [WP-04](work-packages.md#wp-04)

**Vorgehen:** Vorbereitungen können früher erfolgen; verpflichtende Jobs erst nach geklärter Ausgangsbasis aktivieren. Python, JS/Build, Emulator/Browser und Windows unterscheiden; bestehende Publisher-CI behalten.

**Abnahme zusätzlich zu den verknüpften Then-/Negativkontrollen:** Jobs auf integriertem SHA grün, keine versteckten Skips/continue-on-error; Fehlerartefakte und leere Auswahl erkennbar. Branchpflichten nur entsprechend Repo-Regeln setzen.

**Produktstellen:** [.github/workflows/publisher-tests.yml](../../../.github/workflows/publisher-tests.yml), [package.json](../../../package.json)

**Test-/Dokumentziele:** ` .github/workflows/tests.yml ` (vorgeschlagen), [docs/testing.md](../../testing.md)

**Vorhandene Hilfen:** [.github/workflows/publisher-tests.yml](../../../.github/workflows/publisher-tests.yml), [dev.ps1](../../../dev.ps1), [tests/e2e/README.md](../../../tests/e2e/README.md)

**Befehle/Prüfauftrag nach Implementierung:**

- ` Neue Jobs auf genau dem integrierten Commit prüfen; kein einzelner Publisher-Erfolg als Gesamtsuite-Erfolg werten. `

**Zu beachten:** —


<a id="wp-06"></a>

## WP-06 · Firestore-Regeln durch echte Clientoperationen schützen

**Ziel:** Direkte Clientrechte dürfen nie Admin-SDK-Rechte erben.

**Befunde:** [G-001](gaps.md#g-001) · **Vorher:** [WP-01](work-packages.md#wp-01)

**Vorgehen:** Isolierten Rules-Testharness verwenden, Regeln aus Repository laden, Admin nur fürs Seed/Teardown. Anonym/Owner/Fremdidentität und Untercollections prüfen.

**Abnahme zusätzlich zu den verknüpften Then-/Negativkontrollen:** Reale permission-denied-Nachweise und allow-true-Negativkontrolle. Test wird durch den vorgesehenen Runner/CI tatsächlich entdeckt.

**Produktstellen:** [firestore.rules](../../../firestore.rules), [tests/e2e/test_agent_transactions.py](../../../tests/e2e/test_agent_transactions.py)

**Test-/Dokumentziele:** ` tests/rules/firestore.rules.test.mjs ` (vorgeschlagen)

**Vorhandene Hilfen:** [firebase.json](../../../firebase.json), [tests/e2e/README.md](../../../tests/e2e/README.md)

**Befehle/Prüfauftrag nach Implementierung:**

- ` Separaten Rules-Runner mit dem lokalen Demo-Emulator einrichten; nicht den bestehenden Vitest-Glob oder Admin-SDK als Rules-Test verwenden. `

**Zu beachten:** —


<a id="wp-07"></a>

## WP-07 · Reguläre Usage nativ atomar prüfen

**Ziel:** Claims, Slots und Belastungen mit mehreren Repositoryinstanzen.

**Befunde:** [G-002](gaps.md#g-002) · **Vorher:** [WP-01](work-packages.md#wp-01)

**Vorgehen:** Bestehende Usage-Regeln als Oracle verwenden; Firestoreemulator und explizite Barrieren statt Thread-Lock-Fake für die entscheidende Transaktion.

**Abnahme zusätzlich zu den verknüpften Then-/Negativkontrollen:** Endzustände für gleicher Key, verschiedene Keys, letzter Slot, Release/Consume und UTC-Wechsel; getrennte Owner; Negativkontrolle entdeckt fehlende Atomarität.

**Produktstellen:** [app/services/usage_repository.py](../../../app/services/usage_repository.py)

**Test-/Dokumentziele:** ` tests/e2e/test_usage_transactions.py ` (vorgeschlagen)

**Vorhandene Hilfen:** [app/core/e2e_profile.py](../../../app/core/e2e_profile.py), [tests/e2e/test_agent_transactions.py](../../../tests/e2e/test_agent_transactions.py), [tests/usage_test_support.py](../../../tests/usage_test_support.py)

**Befehle/Prüfauftrag nach Implementierung:**

- ` RUN_E2E=1 python -m pytest tests/e2e/test_usage_transactions.py -q (mit sicherem Demo-Emulatorprofil) `

**Zu beachten:** —


<a id="wp-08"></a>

## WP-08 · Chat-Lebenszyklus gegen späte Writes absichern

**Ziel:** Delete/Turn/Completion-Konkurrenz ohne wiederbelebte Daten.

**Befunde:** [G-003](gaps.md#g-003) · **Vorher:** [WP-01](work-packages.md#wp-01)

**Vorgehen:** Beide zulässigen Commitreihenfolgen deterministisch herstellen, Antwort-/Context-/Turn-Dokumente direkt prüfen; bestehendes Create-Chat-Limit weiterlaufen lassen.

**Abnahme zusätzlich zu den verknüpften Then-/Negativkontrollen:** Keine eigenen Waisen nach abgeschlossenem Delete, Kontrollowner unverändert, Stop/Failure/Completion präzise klassifiziert; kein Mock des entscheidenden Guards.

**Produktstellen:** [app/services/chat_store.py](../../../app/services/chat_store.py)

**Test-/Dokumentziele:** ` tests/e2e/test_chat_lifecycle_transactions.py ` (vorgeschlagen)

**Vorhandene Hilfen:** [tests/e2e/test_phase2_transactions.py](../../../tests/e2e/test_phase2_transactions.py), [tests/test_chat_history.py](../../../tests/test_chat_history.py)

**Befehle/Prüfauftrag nach Implementierung:**

- ` RUN_E2E=1 python -m pytest tests/e2e/test_chat_lifecycle_transactions.py -q (Demo-Emulator) `

**Zu beachten:** —


<a id="wp-09"></a>

## WP-09 · Kontokaskade und API-Cleanup integrieren

**Ziel:** Alle Datenbereiche inklusive Resume nach Teilfehler.

**Befunde:** [G-004](gaps.md#g-004) · **Vorher:** [WP-08](work-packages.md#wp-08), [WP-11](work-packages.md#wp-11)

**Vorgehen:** Aus tatsächlichem areas-Tupel vollständiges Seedinventar bauen, Services ausführen und nur externe Firebase-Auth/Mail/Telegram-Grenzen ersetzen; Teilfehler und neue Instanz injizieren.

**Abnahme zusätzlich zu den verknüpften Then-/Negativkontrollen:** Alle 14 aktuellen Bereiche mit explizitem Endzustand, kein Fremddatenverlust; pending/Retry und bereits authentifizierte Late-Writes geprüft. Änderungen des Bereichsinventars erzwingen Review.

**Produktstellen:** [app/services/account_deletion.py](../../../app/services/account_deletion.py), [app/services/api_account_cleanup.py](../../../app/services/api_account_cleanup.py)

**Test-/Dokumentziele:** ` tests/e2e/test_account_deletion_transactions.py ` (vorgeschlagen), [tests/test_api_account_cleanup.py](../../../tests/test_api_account_cleanup.py)

**Vorhandene Hilfen:** [tests/test_account_deletion_retry.py](../../../tests/test_account_deletion_retry.py), [tests/test_chat_history.py](../../../tests/test_chat_history.py)

**Befehle/Prüfauftrag nach Implementierung:**

- ` python -m pytest tests/test_api_account_cleanup.py tests/test_account_deletion_retry.py -q; anschließend neuer Emulator-Kaskadentest `

**Zu beachten:** —


<a id="wp-10"></a>

## WP-10 · Memory-Revision, Undo und Löschsperre stärken

**Ziel:** Vorhandene Erfolgsroundtrips um konkurrierende Zustände ergänzen.

**Befunde:** [G-007](gaps.md#g-007), [G-008](gaps.md#g-008) · **Vorher:** [WP-01](work-packages.md#wp-01)

**Vorgehen:** Unit-/Routerfälle auf echten Revisions-/Ownerguard ausrichten; nativer Commitfall für partielle Writes. Patch/Undo-Fehler müssen gespeicherten Inhalt unverändert lassen.

**Abnahme zusätzlich zu den verknüpften Then-/Negativkontrollen:** M-01 überlebt die neuen Tests nicht; Konflikt, expiry, Fremd-ID, Retry, manueller Save und Tombstone belegt. Kostenverhalten folgt aktueller Abrechnung.

**Produktstellen:** [app/services/memory_edit.py](../../../app/services/memory_edit.py)

**Test-/Dokumentziele:** ` tests/e2e/test_memory_edit_transactions.py ` (vorgeschlagen), [tests/test_memory_edit.py](../../../tests/test_memory_edit.py)

**Vorhandene Hilfen:** [app/services/persistence_guard.py](../../../app/services/persistence_guard.py), [tests/test_memory_edit.py](../../../tests/test_memory_edit.py)

**Befehle/Prüfauftrag nach Implementierung:**

- ` python -m pytest tests/test_memory_edit.py -q `
- ` python -m pytest tests/test_memory_edit.py -q; ergänzend Memory-Emulatortest `

**Zu beachten:** —


<a id="wp-11"></a>

## WP-11 · API-Recovery und historischen Source-Adapter prüfen

**Ziel:** Durable Runs und ihre historischen Quellen nach Restart.

**Befunde:** [G-005](gaps.md#g-005), [G-010](gaps.md#g-010) · **Vorher:** —

**Vorgehen:** Recovery/Retention mit Fakeuhr und echtem Runner-/Repositorypfad, Source-GET über echten API-Key-/Run-Adapter; Snapshotversion und No-new-job-Regel prüfen.

**Abnahme zusätzlich zu den verknüpften Then-/Negativkontrollen:** Kein doppelter Providerstart, keine Löschung lebender Daten oder falsche historische Bindung; Cursor/revision/Ownership/Leases/Backfill-Grenzen belegt.

**Produktstellen:** [app/api/routers/api_v1.py](../../../app/api/routers/api_v1.py), [app/services/api_consensus_runner.py](../../../app/services/api_consensus_runner.py), [app/services/api_run_repository.py](../../../app/services/api_run_repository.py)

**Test-/Dokumentziele:** ` tests/test_api_run_recovery.py ` (vorgeschlagen), [tests/test_api_run_repository.py](../../../tests/test_api_run_repository.py), [tests/test_consensus_api.py](../../../tests/test_consensus_api.py), [tests/test_source_check_api.py](../../../tests/test_source_check_api.py)

**Vorhandene Hilfen:** [tests/test_api_run_repository.py](../../../tests/test_api_run_repository.py), [tests/test_consensus_api.py](../../../tests/test_consensus_api.py), [tests/test_source_check_repository.py](../../../tests/test_source_check_repository.py), [tests/usage_test_support.py](../../../tests/usage_test_support.py)

**Befehle/Prüfauftrag nach Implementierung:**

- ` python -m pytest tests/test_api_run_recovery.py tests/test_api_run_repository.py tests/test_consensus_api.py -q `
- ` python -m pytest tests/test_consensus_api.py tests/test_source_check_api.py tests/test_source_check_scope.py -q `

**Zu beachten:** [D-01](decisions.md#d-01)


<a id="wp-12"></a>

## WP-12 · Registrierungsrace und user_status verbinden

**Ziel:** Tatsächliche Auth-/Tarifpayloads an der HTTP-Grenze.

**Befunde:** [G-009](gaps.md#g-009), [G-012](gaps.md#g-012) · **Vorher:** —

**Vorgehen:** Lookup/Create-Race gezielt vom Firebase-SDK-Double auslösen; echten Provisioner/Statushandler verwenden. Free-Admin separat von Pro modellieren.

**Abnahme zusätzlich zu den verknüpften Then-/Negativkontrollen:** Gleiche öffentliche Registrierungsantwort, keine Doppelbenachrichtigung; Tarif-/Rollenmatrix und Tierausfall mit fail-closed Verhalten.

**Produktstellen:** [app/api/routers/users.py](../../../app/api/routers/users.py), [app/services/registration.py](../../../app/services/registration.py)

**Test-/Dokumentziele:** [tests/test_auth_session.py](../../../tests/test_auth_session.py), [tests/test_registration_security.py](../../../tests/test_registration_security.py), ` tests/test_user_status.py ` (vorgeschlagen)

**Vorhandene Hilfen:** [tests/js/plus-tier-gates.test.mjs](../../../tests/js/plus-tier-gates.test.mjs), [tests/test_account_tier_admin.py](../../../tests/test_account_tier_admin.py), [tests/test_auth_session.py](../../../tests/test_auth_session.py), [tests/test_tier_cache.py](../../../tests/test_tier_cache.py)

**Befehle/Prüfauftrag nach Implementierung:**

- ` python -m pytest tests/test_registration_security.py tests/test_auth_session.py -q `
- ` python -m pytest tests/test_user_status.py tests/test_tier_cache.py tests/test_plus_tier.py -q `

**Zu beachten:** —


<a id="wp-13"></a>

## WP-13 · App-Share-POST integrieren

**Ziel:** Der Appadapter publiziert ausschließlich autoritative eigene Ergebnisse.

**Befunde:** [G-011](gaps.md#g-011) · **Vorher:** [WP-01](work-packages.md#wp-01)

**Vorgehen:** Route plus Snapshotservice ausführen, gültigen Pending-Datensatz nutzen; main-Fehlerumschlag und Owner/Visibility/Quota/Retry prüfen.

**Abnahme zusätzlich zu den verknüpften Then-/Negativkontrollen:** Response und gespeicherte Ressource stimmen überein; fremde/abgelaufene/gefälschte Payload abgelehnt. API-v1-Test wird nicht als Ersatz gezählt.

**Produktstellen:** [app/api/routers/share.py](../../../app/api/routers/share.py)

**Test-/Dokumentziele:** [tests/test_share_feature.py](../../../tests/test_share_feature.py)

**Vorhandene Hilfen:** [tests/test_bookmarks.py](../../../tests/test_bookmarks.py), [tests/test_share_feature.py](../../../tests/test_share_feature.py)

**Befehle/Prüfauftrag nach Implementierung:**

- ` python -m pytest tests/test_share_feature.py -q `

**Zu beachten:** —


<a id="wp-14"></a>

## WP-14 · Source-Queue mit nativen Leases prüfen

**Ziel:** Alte Worker dürfen nach Reclaim nichts committen.

**Befunde:** [G-006](gaps.md#g-006) · **Vorher:** [WP-01](work-packages.md#wp-01)

**Vorgehen:** Claim-/Finish-/Delete-Reihenfolgen im Emulator mit getrennten Repositoryinstanzen; Credentialprovider bleibt außerhalb der DB.

**Abnahme zusätzlich zu den verknüpften Then-/Negativkontrollen:** Nur aktuelle Lease, genau einmal Paketabschluss, keine Wiederanlage, korrekte Version/Pagination; keine eigenen Keys in Dokumenten oder Logs.

**Produktstellen:** [app/services/source_check_repository.py](../../../app/services/source_check_repository.py)

**Test-/Dokumentziele:** ` tests/e2e/test_source_check_transactions.py ` (vorgeschlagen)

**Vorhandene Hilfen:** [tests/e2e/test_prompt_config_transactions.py](../../../tests/e2e/test_prompt_config_transactions.py), [tests/test_source_check_jobs.py](../../../tests/test_source_check_jobs.py), [tests/test_source_check_repository.py](../../../tests/test_source_check_repository.py)

**Befehle/Prüfauftrag nach Implementierung:**

- ` RUN_E2E=1 python -m pytest tests/e2e/test_source_check_transactions.py -q (Demo-Emulator) `

**Zu beachten:** —


<a id="wp-15"></a>

## WP-15 · Watch- und Telegramadapter schließen

**Ziel:** HTTP-Methoden und Servicegrenzen tatsächlich ausführen.

**Befunde:** [G-013](gaps.md#g-013) · **Vorher:** —

**Vorgehen:** PATCH/DELETE/Link/Test durch echten Router; UID/Allowlist/Entitlements/Servicefehler mit gespeicherten Kontrollzuständen und Notifierdouble prüfen.

**Abnahme zusätzlich zu den verknüpften Then-/Negativkontrollen:** Alle vier bisher unausgeführten Handler verhaltensbasiert geprüft; falscher Owner und nicht verbundener Versand haben keine Nebenwirkung.

**Produktstellen:** [app/api/routers/watch.py](../../../app/api/routers/watch.py)

**Test-/Dokumentziele:** [tests/test_watch_feature.py](../../../tests/test_watch_feature.py)

**Vorhandene Hilfen:** [tests/test_watch_feature.py](../../../tests/test_watch_feature.py)

**Befehle/Prüfauftrag nach Implementierung:**

- ` python -m pytest tests/test_watch_feature.py -q `

**Zu beachten:** [D-03](decisions.md#d-03)


<a id="wp-16"></a>

## WP-16 · Topic-Administration und öffentliche Adapter schließen

**Ziel:** Echte Adminberechtigung und vollständige Routenauswahl.

**Befunde:** [G-014](gaps.md#g-014) · **Vorher:** —

**Vorgehen:** PUT ausdrücklich aufrufen, Adminprüfung nicht ersetzen; Hub/Sitemap/Follow mit verschiedenen Publikationszuständen und Escapingfällen.

**Abnahme zusätzlich zu den verknüpften Then-/Negativkontrollen:** Nonadmin scheitert vor Mutation, Hub/Sitemap zeigen nur zulässige Daten, Follow bleibt neutral/idempotent. Testnamen entsprechen ausgeführten Methoden.

**Produktstellen:** [app/api/routers/topics.py](../../../app/api/routers/topics.py)

**Test-/Dokumentziele:** [tests/test_topics_feature.py](../../../tests/test_topics_feature.py)

**Vorhandene Hilfen:** [tests/test_auth_revocation.py](../../../tests/test_auth_revocation.py), [tests/test_topics_feature.py](../../../tests/test_topics_feature.py)

**Befehle/Prüfauftrag nach Implementierung:**

- ` python -m pytest tests/test_topics_feature.py tests/test_auth_revocation.py -q `

**Zu beachten:** —


<a id="wp-17"></a>

## WP-17 · Claim-Identity-Judge validieren

**Ziel:** Parser, Schlüsselbindung und Fallback des echten Helpers.

**Befunde:** [G-016](gaps.md#g-016) · **Vorher:** —

**Vorgehen:** Transportantworten einspeisen, query_claim_identity ausführen. Bekannte/neue/duplizierte Keys und Indexformen systematisch kombinieren.

**Abnahme zusätzlich zu den verknüpften Then-/Negativkontrollen:** Unbekannte/mehrfach verwendete Zuordnungen werden verworfen, Inputs/Versuche begrenzt und Fehler nachvollziehbar. Grenzsemantik vor Änderung dokumentiert.

**Produktstellen:** [app/services/llm/consensus_engine.py](../../../app/services/llm/consensus_engine.py)

**Test-/Dokumentziele:** ` tests/test_claim_identity_judge.py ` (vorgeschlagen)

**Vorhandene Hilfen:** [tests/test_consensus_engine.py](../../../tests/test_consensus_engine.py), [tests/test_topics_feature.py](../../../tests/test_topics_feature.py)

**Befehle/Prüfauftrag nach Implementierung:**

- ` python -m pytest tests/test_claim_identity_judge.py tests/test_topics_feature.py tests/test_claim_ledger.py -q `

**Zu beachten:** [D-06](decisions.md#d-06)


<a id="wp-18"></a>

## WP-18 · SEO-Repositoryadapter ausführen

**Ziel:** SDK-Rückgabeformen hinter vorhandenen Service-Fakes.

**Befunde:** [G-017](gaps.md#g-017) · **Vorher:** —

**Vorgehen:** Ungeordnete/missing BatchGet-Snapshots und Grenzgrößen, Datumsmischung und Latest-/Judgmentqueries prüfen; kleiner Emulatorfall für reale Queryform.

**Abnahme zusätzlich zu den verknüpften Then-/Negativkontrollen:** Zuordnung über Dokumentidentität, bounded Reads und korrekt neueste Daten; fehlende Daten werden nicht als gemessener Nulltraffic ausgegeben.

**Produktstellen:** [app/services/seo_repository.py](../../../app/services/seo_repository.py)

**Test-/Dokumentziele:** ` tests/test_seo_repository.py ` (vorgeschlagen)

**Vorhandene Hilfen:** [tests/test_seo_data.py](../../../tests/test_seo_data.py), [tests/test_seo_weekly_review.py](../../../tests/test_seo_weekly_review.py)

**Befehle/Prüfauftrag nach Implementierung:**

- ` python -m pytest tests/test_seo_repository.py tests/test_seo_data.py tests/test_seo_weekly_review.py -q `

**Zu beachten:** —


<a id="wp-19"></a>

## WP-19 · Schedulerqueries und persistente Claims prüfen

**Ziel:** Watch-, Topic- und SEO-Slots über echte SDK-Grenzen.

**Befunde:** [G-031](gaps.md#g-031) · **Vorher:** [WP-01](work-packages.md#wp-01)

**Vorgehen:** Einzelnen Tick mit kontrollierter Uhr/Pipeline ausführen, native Claimkonkurrenz und Shutdown. Vorhandene DST-/Supervisortests wiederverwenden.

**Abnahme zusätzlich zu den verknüpften Then-/Negativkontrollen:** Nur fällige Daten, ein Gewinner, keine stale Completion und kein weiterer Tick nach Shutdown; reale Query-/Leaseform statt nur Fakefilter.

**Produktstellen:** [app/services/seo_weekly_review.py](../../../app/services/seo_weekly_review.py), [app/services/topics.py](../../../app/services/topics.py), [app/services/watch_service.py](../../../app/services/watch_service.py)

**Test-/Dokumentziele:** ` tests/e2e/test_scheduler_transactions.py ` (vorgeschlagen), [tests/test_background_task_supervision.py](../../../tests/test_background_task_supervision.py)

**Vorhandene Hilfen:** [tests/test_seo_weekly_review.py](../../../tests/test_seo_weekly_review.py), [tests/test_topics_feature.py](../../../tests/test_topics_feature.py), [tests/test_watch_feature.py](../../../tests/test_watch_feature.py)

**Befehle/Prüfauftrag nach Implementierung:**

- ` RUN_E2E=1 python -m pytest tests/e2e/test_scheduler_transactions.py -q; python -m pytest tests/test_background_task_supervision.py -q `

**Zu beachten:** [D-03](decisions.md#d-03)


<a id="wp-20"></a>

## WP-20 · Topic-Notizen als Text absichern

**Ziel:** Reproduzierten Text→HTML-Fehler zunächst rot festhalten.

**Befunde:** [G-018](gaps.md#g-018) · **Vorher:** —

**Vorgehen:** DOM-Test mit inertem Markup und Interaktionen; gezielten Browserfall für Touch/Focus/Navigation ergänzen. Textknoten und konstante UI-Struktur getrennt aufbauen.

**Abnahme zusätzlich zu den verknüpften Then-/Negativkontrollen:** D-01 erzeugt kein Element mehr aus Nutztext; Sonderzeichen bleiben lesbar. Unseen-/historischer Besuch und blockierter Storage funktionieren. Frontendbuild/öffentlichen Cachebuster nach Repo-Regel pflegen.

**Produktstellen:** [app/services/claim_ledger.py](../../../app/services/claim_ledger.py), [static/js/topic-page.js](../../../static/js/topic-page.js), [templates/topic.html](../../../templates/topic.html)

**Test-/Dokumentziele:** ` tests/e2e/test_topic_frontend.py ` (vorgeschlagen), ` tests/js/topic-page.test.mjs ` (vorgeschlagen)

**Vorhandene Hilfen:** [tests/js/helpers/appWindow.mjs](../../../tests/js/helpers/appWindow.mjs), [tests/test_claim_ledger.py](../../../tests/test_claim_ledger.py)

**Befehle/Prüfauftrag nach Implementierung:**

- ` npm test -- tests/js/topic-page.test.mjs; ergänzend gezielter Topic-Browserfall `

**Zu beachten:** —


<a id="wp-21"></a>

## WP-21 · Adminfehler aus dem echten Appumschlag anzeigen

**Ziel:** Fehlerobjekte dürfen nicht als [object Object] erscheinen.

**Befunde:** [G-019](gaps.md#g-019) · **Vorher:** —

**Vorgehen:** createAdminClient mit tatsächlichen error-/detail-Objekten, Strings, Listen und nicht-JSON testen; AccountTier-HTTP-Response als Vertragsfixture nutzen.

**Abnahme zusätzlich zu den verknüpften Then-/Negativkontrollen:** D-02 main-handler-Fall zeigt erlaubte Nachricht/Fallback; kein zweiter Write; Konfliktdraft bleibt erhalten. Frontendbuild/Cachebuster nach Repo-Regel pflegen.

**Produktstellen:** [app/api/routers/admin.py](../../../app/api/routers/admin.py), [main.py](../../../main.py), [static/js/admin-api.js](../../../static/js/admin-api.js)

**Test-/Dokumentziele:** ` tests/js/admin-api.test.mjs ` (vorgeschlagen), [tests/test_account_tier_admin.py](../../../tests/test_account_tier_admin.py)

**Vorhandene Hilfen:** [tests/e2e/test_admin_prompt_config.py](../../../tests/e2e/test_admin_prompt_config.py), [tests/js/admin-prompt-config.test.mjs](../../../tests/js/admin-prompt-config.test.mjs)

**Befehle/Prüfauftrag nach Implementierung:**

- ` npm test -- tests/js/admin-api.test.mjs tests/js/admin-prompt-config.test.mjs; python -m pytest tests/test_account_tier_admin.py -q `

**Zu beachten:** —


<a id="wp-22"></a>

## WP-22 · Benchmark-Adminadapter und Viewer prüfen

**Ziel:** Vom kompakten Report bis zum echten Auswahl-/Fehlerzustand.

**Befunde:** [G-015](gaps.md#g-015) · **Vorher:** —

**Vorgehen:** Admin-Listen/Detailroute mit Auth, danach Viewer mit kontrolliert verspäteten Antworten. Kein Rohreport mit Prompts/Antworten als Fixture im Adminvertrag.

**Abnahme zusätzlich zu den verknüpften Then-/Negativkontrollen:** Nonadmin vor Read abgelehnt; 404, falsche IDs und Auswahlwechsel korrekt; keine Staledaten oder Rohprompts.

**Produktstellen:** [app/api/routers/admin.py](../../../app/api/routers/admin.py), [static/js/admin-benchmark.js](../../../static/js/admin-benchmark.js)

**Test-/Dokumentziele:** ` tests/js/admin-benchmark.test.mjs ` (vorgeschlagen), [tests/test_benchmark_reports.py](../../../tests/test_benchmark_reports.py)

**Vorhandene Hilfen:** [tests/js/helpers/appWindow.mjs](../../../tests/js/helpers/appWindow.mjs), [tests/test_benchmark_report_reader.py](../../../tests/test_benchmark_report_reader.py), [tests/test_benchmark_reports.py](../../../tests/test_benchmark_reports.py)

**Befehle/Prüfauftrag nach Implementierung:**

- ` python -m pytest tests/test_benchmark_reports.py tests/test_benchmark_report_reader.py -q; npm test -- tests/js/admin-benchmark.test.mjs `

**Zu beachten:** —


<a id="wp-23"></a>

## WP-23 · Inhalt der OG-Karte wirksam prüfen

**Ziel:** Gültige PNG-Bytes reichen als Inhaltstest nicht aus.

**Befunde:** [G-020](gaps.md#g-020) · **Vorher:** —

**Vorgehen:** Realen Renderer mit deterministischen Fonts/Inputs prüfen; Dekodierung, stabile Bildregionen und semantische Renderinputs kombinieren. Route muss richtige Inputs liefern.

**Abnahme zusätzlich zu den verknüpften Then-/Negativkontrollen:** M-02 wird von neuem Test entdeckt; Frage/Kennzahlen/unscored und private Seiten geprüft. Kein pixelgenauer plattformabhängiger Hash.

**Produktstellen:** [app/api/routers/share.py](../../../app/api/routers/share.py), [app/services/og_image.py](../../../app/services/og_image.py)

**Test-/Dokumentziele:** ` tests/test_og_image.py ` (vorgeschlagen), [tests/test_share_feature.py](../../../tests/test_share_feature.py)

**Vorhandene Hilfen:** [tests/test_share_feature.py](../../../tests/test_share_feature.py)

**Befehle/Prüfauftrag nach Implementierung:**

- ` python -m pytest tests/test_og_image.py tests/test_share_feature.py -q `

**Zu beachten:** [D-06](decisions.md#d-06)


<a id="wp-24"></a>

## WP-24 · Analytics-Opt-out dynamisch prüfen

**Ziel:** Query-/Storageverhalten vor dem Trackerstart.

**Befunde:** [G-021](gaps.md#g-021) · **Vorher:** —

**Vorgehen:** Originalskript in frischem jsdom ausführen, Trackerstart instrumentieren und Storageausfälle injizieren.

**Abnahme zusätzlich zu den verknüpften Then-/Negativkontrollen:** 1/0/fehlend/sonstige Parameter und get/set/remove-Fehler führen zum erwarteten Flag/Seitenstart; reine Stringpräsenz genügt nicht.

**Produktstellen:** [static/js/analytics-opt-out.js](../../../static/js/analytics-opt-out.js)

**Test-/Dokumentziele:** ` tests/js/analytics-opt-out.test.mjs ` (vorgeschlagen)

**Vorhandene Hilfen:** [tests/js/helpers/appWindow.mjs](../../../tests/js/helpers/appWindow.mjs), [tests/test_analytics_partial.py](../../../tests/test_analytics_partial.py)

**Befehle/Prüfauftrag nach Implementierung:**

- ` npm test -- tests/js/analytics-opt-out.test.mjs; python -m pytest tests/test_analytics_partial.py -q `

**Zu beachten:** —


<a id="wp-25"></a>

## WP-25 · Wartungsskripte isoliert absichern

**Ziel:** Projekt-/Apply-/Dry-run-Grenzen ohne Produktzugriff.

**Befunde:** [G-022](gaps.md#g-022), [G-023](gaps.md#g-023) · **Vorher:** —

**Vorgehen:** Subprozesse mit synthetischen Modulen/DB/Provider und explizitem Netzwerkverbot. Reparatur-Projektguard nicht für Tests deaktivieren; Fakeumgebung muss kontrollierten Vertrag abbilden.

**Abnahme zusätzlich zu den verknüpften Then-/Negativkontrollen:** Inspect/dry-run schreiben nicht; Apply nur gewählten Account/Keys, Idempotenz und Datenerhalt. Dry-run-Kosten des Backfills klar dokumentiert.

**Produktstellen:** [scripts/backfill_claim_keys.py](../../../scripts/backfill_claim_keys.py), [scripts/repair_agent_allowance.py](../../../scripts/repair_agent_allowance.py)

**Test-/Dokumentziele:** ` tests/test_backfill_claim_keys.py ` (vorgeschlagen), ` tests/test_repair_agent_allowance_script.py ` (vorgeschlagen)

**Vorhandene Hilfen:** [tests/test_agent_quota_recovery.py](../../../tests/test_agent_quota_recovery.py), [tests/test_claim_ledger.py](../../../tests/test_claim_ledger.py), [tests/test_publisher_standalone.py](../../../tests/test_publisher_standalone.py), [tests/test_topics_feature.py](../../../tests/test_topics_feature.py)

**Befehle/Prüfauftrag nach Implementierung:**

- ` python -m pytest tests/test_repair_agent_allowance_script.py tests/test_agent_quota_recovery.py -q `
- ` python -m pytest tests/test_backfill_claim_keys.py tests/test_claim_ledger.py -q `

**Zu beachten:** [D-07](decisions.md#d-07)


<a id="wp-26"></a>

## WP-26 · HTTP-Body- und lokale Transportgrenzen ergänzen

**Ziel:** ASGI-Randfälle und wirkliche Socket-Lebenszyklen.

**Befunde:** [G-032](gaps.md#g-032), [G-033](gaps.md#g-033) · **Vorher:** —

**Vorgehen:** Header/Env-Grenzen im vorhandenen ASGI-Harness; lokaler HTTP/TLS-Server für Stream/Cancel/Close/gzip. Testziel explizit einspeisen; SSRF-Policy separat real prüfen, keine Produktionsallowlist erweitern.

**Abnahme zusätzlich zu den verknüpften Then-/Negativkontrollen:** Kein Leak/zweiter Retry/unbegrenztes Lesen; Host/SNI/Redirect-Neuvalidierung belegt. Fehlerstatus bewusst gewählt, keine Internetabhängigkeit.

**Produktstellen:** [app/core/request_limits.py](../../../app/core/request_limits.py), [app/services/llm/provider_runtime.py](../../../app/services/llm/provider_runtime.py), [app/services/source_documents.py](../../../app/services/source_documents.py)

**Test-/Dokumentziele:** ` tests/test_provider_local_transport.py ` (vorgeschlagen), [tests/test_request_body_limits.py](../../../tests/test_request_body_limits.py), ` tests/test_source_documents_local_transport.py ` (vorgeschlagen)

**Vorhandene Hilfen:** [tests/test_provider_timeouts.py](../../../tests/test_provider_timeouts.py), [tests/test_request_body_limits.py](../../../tests/test_request_body_limits.py), [tests/test_source_verification.py](../../../tests/test_source_verification.py)

**Befehle/Prüfauftrag nach Implementierung:**

- ` python -m pytest tests/test_provider_local_transport.py tests/test_source_documents_local_transport.py -q `
- ` python -m pytest tests/test_request_body_limits.py -q `

**Zu beachten:** [D-06](decisions.md#d-06)


<a id="wp-27"></a>

## WP-27 · Feedback und Statistikwrites verbinden

**Ziel:** Echte Router-/Persistenzwrapper hinter vorhandenen Guardtests.

**Befunde:** [G-034](gaps.md#g-034) · **Vorher:** —

**Vorgehen:** Auth, Tages-/Cooldown-Limits und Storefehler durch realen Handler; Statistikwrapper mit inhaltshaltigen Eingaben ausführen und gespeicherte Felder prüfen.

**Abnahme zusätzlich zu den verknüpften Then-/Negativkontrollen:** UID vor Write geprüft, Limits unverändert, Statistik ohne Prompt/Antwort/IDs. Feedback selbst darf die bewusst eingegebene Nachricht enthalten.

**Produktstellen:** [app/api/routers/pages.py](../../../app/api/routers/pages.py), [app/services/differences_stats.py](../../../app/services/differences_stats.py)

**Test-/Dokumentziele:** [tests/test_differences_stats.py](../../../tests/test_differences_stats.py), ` tests/test_feedback.py ` (vorgeschlagen)

**Vorhandene Hilfen:** [tests/test_differences_stats.py](../../../tests/test_differences_stats.py), [tests/test_phase5_operations.py](../../../tests/test_phase5_operations.py)

**Befehle/Prüfauftrag nach Implementierung:**

- ` python -m pytest tests/test_feedback.py tests/test_differences_stats.py -q `

**Zu beachten:** —


<a id="wp-28"></a>

## WP-28 · Unterstützte Hilfs-CLIs prüfen

**Ziel:** Alternative Benchmark-/Evaluations-/Preview-Einstiege.

**Befunde:** [G-035](gaps.md#g-035) · **Vorher:** —

**Vorgehen:** Aktuelle Supportentscheidung je Einstieg festhalten; unterstützte CLIs per Subprozess mit temporären Outputs und Fakeprovider prüfen. Veraltete Modi nicht als neue Produktanforderung behandeln.

**Abnahme zusätzlich zu den verknüpften Then-/Negativkontrollen:** Argumente, Exitcodes, Budget/Scope und Outputgrenzen pro unterstütztem Einstieg belegt; Live-Modellqualität ausdrücklich separat.

**Produktstellen:** [benchmark/run_experiment.py](../../../benchmark/run_experiment.py), [benchmark/run_sample.py](../../../benchmark/run_sample.py)

**Test-/Dokumentziele:** ` tests/test_auxiliary_cli.py ` (vorgeschlagen)

**Vorhandene Hilfen:** [tests/test_benchmark_cli.py](../../../tests/test_benchmark_cli.py), [tests/test_publisher_standalone.py](../../../tests/test_publisher_standalone.py)

**Befehle/Prüfauftrag nach Implementierung:**

- ` python -m pytest tests/test_auxiliary_cli.py -q `

**Zu beachten:** [D-04](decisions.md#d-04), [D-07](decisions.md#d-07)


<a id="wp-29"></a>

## WP-29 · Persistierte Nutzerreisen durch alle internen Schichten prüfen

**Ziel:** Wenige gezielte Integrationsfälle schließen die Mocklücken.

**Befunde:** [G-030](gaps.md#g-030) · **Vorher:** [WP-03](work-packages.md#wp-03), [WP-07](work-packages.md#wp-07), [WP-08](work-packages.md#wp-08), [WP-09](work-packages.md#wp-09), [WP-10](work-packages.md#wp-10), [WP-12](work-packages.md#wp-12), [WP-13](work-packages.md#wp-13), [WP-14](work-packages.md#wp-14)

**Vorgehen:** J-01/J-02 zuerst, dann J-03/J-04/J-05 gemäß journeys.md. Echtes AppFirebase, App-Routen und lokales Firestore; nur Identitäts-/Provider-/Nachrichtengrenzen ersetzen.

**Abnahme zusätzlich zu den verknüpften Then-/Negativkontrollen:** UI und DB stimmen nach Reload/Ownerwechsel/Stop überein, kein zweiter Modellstart beim Recover, keine vermischten Turns/Charges. Bestehende Modul-/Browsertests bleiben schnelle Detailnachweise.

**Produktstellen:** [tests/e2e/conftest.py](../../../tests/e2e/conftest.py), [tests/e2e/test_phase4_frontend.py](../../../tests/e2e/test_phase4_frontend.py)

**Test-/Dokumentziele:** ` tests/e2e/test_persisted_user_journeys.py ` (vorgeschlagen)

**Vorhandene Hilfen:** [tests/e2e/conftest.py](../../../tests/e2e/conftest.py), [tests/e2e/test_phase4_frontend.py](../../../tests/e2e/test_phase4_frontend.py), [tests/test_consensus_chat_history.py](../../../tests/test_consensus_chat_history.py)

**Befehle/Prüfauftrag nach Implementierung:**

- ` RUN_E2E=1 python -m pytest tests/e2e/test_persisted_user_journeys.py -q (Demo-Emulator) `

**Zu beachten:** [D-02](decisions.md#d-02)


<a id="wp-30"></a>

## WP-30 · Vendorhelper mit echtem temporärem Dateisystem prüfen

**Ziel:** Versionpins, Font-/Lizenzumfang und checkOnly.

**Befunde:** [G-036](gaps.md#g-036) · **Vorher:** —

**Vorgehen:** Winzige synthetische Pakete statt realer Paketdownloads verwenden; helper direkt aufrufen, alte Assets und Mtime kontrollieren.

**Abnahme zusätzlich zu den verknüpften Then-/Negativkontrollen:** Versionabweichung und stale/fehlende Bytes erkannt, Check-only ohne Writes, unveränderte Inputs ohne Rewrite; bestehende Artefakt-/Buildtests bleiben grün.

**Produktstellen:** [scripts/vendor_frontend.mjs](../../../scripts/vendor_frontend.mjs)

**Test-/Dokumentziele:** ` tests/js/vendor-frontend.test.mjs ` (vorgeschlagen)

**Vorhandene Hilfen:** [tests/js/frontend-output.test.mjs](../../../tests/js/frontend-output.test.mjs), [tests/test_frontend_build.py](../../../tests/test_frontend_build.py)

**Befehle/Prüfauftrag nach Implementierung:**

- ` npm test -- tests/js/vendor-frontend.test.mjs tests/js/frontend-output.test.mjs; python -m pytest tests/test_frontend_build.py -q `

**Zu beachten:** —

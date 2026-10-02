# Codex-Arbeitspakete

[Einstieg](README.md) · [Befunde](gaps.md) · [Nutzerreisen](journeys.md) · [Oracles](decisions.md)

**38 Arbeitspakete · 38 abgeschlossen.** Im ursprünglichen Dokumentationsauftrag wurde keines implementiert; der aktuelle Status steht in audit.json. Die IDs sind stabil; sie geben keine zwingende lineare Reihenfolge vor. Abhängigkeiten sind fachliche/technische Voraussetzungen. Vorarbeit ist früher möglich. WP-01 bis WP-04 klären den Ausgangsstand; WP-05 macht die allgemeine CI verbindlich. WP-06 bis WP-14 sowie WP-20 schützen besonders folgenreiche Grenzen. WP-29 folgt auf tragfähige Adapter-/Persistenztests. Die restlichen Pakete bleiben im Gesamtumfang.

## Gemeinsamer Auftrag und Abnahme

Ein Paket anhand seiner ID auswählen. Zuerst `check_product_audit.py` und den bisherigen Inventarcheck ausführen. Bei Drift betroffene Code-/Testkörper erneut lesen; Hashes nicht blind aktualisieren. Produktvertrag, Given/When/Then und vorhandene Testhelfer lesen. Den kleinsten geeigneten Test ergänzen, der das reale Verhalten an der benannten Grenze ausführt. Nur äußere Abhängigkeiten ersetzen; den zu prüfenden Guard/Adapter nicht mocken. Bei beobachtetem Produktfehler zuerst roten Regressionstest festhalten und dann begründet korrigieren.

Jedes Paket verlangt die verknüpften Then-Bedingungen, mindestens eine fachliche Negativkontrolle (temporäre Mutation nur lokal/in isoliertem Prozess), passende fokussierte Regressionen und erforderliche Repo-Gates. Ein Statuscode/Mockaufruf ersetzt keinen benötigten DB-/UI-Endzustand. Konkurrenz mit Barrieren/Fakeuhr steuern; keine Sleeps als Erfolgsbedingung. Unabhängige Owner-/Run-/Versionskontrollwerte verwenden. Testdoubles an realer SDK-/HTTP-Form ausrichten.

Bei neuen Tests die Runner-Discovery kontrollieren. Nach Änderungen unter `static/` Build und öffentliche Cachebuster nach AGENTS.md pflegen; bei Änderungen von Architektur/Flows `docs/codebase-map.md` im selben Auftrag aktualisieren. Keine echten Provider-/Produktdatenzugriffe in Regressionen. Fehlende Umgebung als offen dokumentieren, nicht als Erfolg umetikettieren.

Abschluss pro Paket in `audit.json`: Status `completed`, Implementierungscommit und konkrete Validierungsevidenz (Befehle, Umgebung, Pass/Fail/Skip, Negativkontrolle, Restgrenze). Bei Teilabschluss `in_progress` oder `blocked` mit Grund. Originale Audit-/Laufhistorie erhalten; fachliche Matrix, neuer Testkatalog und aktuelle Nachweise bewusst fortschreiben.

| Paket | Ziel | Priorität | Vorher | Befunde | Status |
|---|---|---|---|---|---|
| [WP-01](#wp-01) | Bekannte Fixture- und Stringfehler bereinigen | P1 | — | [G-027](gaps.md#g-027), [G-028](gaps.md#g-028) | completed |
| [WP-02](#wp-02) | Report-Race unter kontrollierter Emulatorumgebung klären | P1 | [WP-01](work-packages.md#wp-01) | [G-029](gaps.md#g-029) | completed |
| [WP-03](#wp-03) | Aktuelle Browserfälle ausführen und Fehler einordnen | P1 | [WP-01](work-packages.md#wp-01) | [G-025](gaps.md#g-025) | completed |
| [WP-04](#wp-04) | Windows-Einstieg verifizieren | P2 | — | [G-026](gaps.md#g-026) | completed |
| [WP-05](#wp-05) | Allgemeine Regression-CI einrichten | P1 | [WP-01](work-packages.md#wp-01), [WP-02](work-packages.md#wp-02), [WP-03](work-packages.md#wp-03), [WP-04](work-packages.md#wp-04) | [G-024](gaps.md#g-024) | completed |
| [WP-06](#wp-06) | Firestore-Regeln durch echte Clientoperationen schützen | P1 | [WP-01](work-packages.md#wp-01) | [G-001](gaps.md#g-001) | completed |
| [WP-07](#wp-07) | Reguläre Usage nativ atomar prüfen | P1 | [WP-01](work-packages.md#wp-01) | [G-002](gaps.md#g-002) | completed |
| [WP-08](#wp-08) | Chat-Lebenszyklus gegen späte Writes absichern | P1 | [WP-01](work-packages.md#wp-01) | [G-003](gaps.md#g-003) | completed |
| [WP-09](#wp-09) | Kontokaskade und API-Cleanup integrieren | P1 | [WP-08](work-packages.md#wp-08), [WP-11](work-packages.md#wp-11) | [G-004](gaps.md#g-004) | completed |
| [WP-10](#wp-10) | Memory-Revision, Undo und Löschsperre stärken | P1 | [WP-01](work-packages.md#wp-01) | [G-007](gaps.md#g-007), [G-008](gaps.md#g-008), [G-038](gaps.md#g-038) | completed |
| [WP-11](#wp-11) | API-Recovery und historischen Source-Adapter prüfen | P1 | — | [G-005](gaps.md#g-005), [G-010](gaps.md#g-010) | completed |
| [WP-12](#wp-12) | Registrierungsrace und user_status verbinden | P1 | — | [G-009](gaps.md#g-009), [G-012](gaps.md#g-012) | completed |
| [WP-13](#wp-13) | App-Share-POST integrieren | P1 | [WP-01](work-packages.md#wp-01) | [G-011](gaps.md#g-011) | completed |
| [WP-14](#wp-14) | Source-Queue mit nativen Leases prüfen | P1 | [WP-01](work-packages.md#wp-01) | [G-006](gaps.md#g-006) | completed |
| [WP-15](#wp-15) | Watch- und Telegramadapter schließen | P2 | — | [G-013](gaps.md#g-013) | completed |
| [WP-16](#wp-16) | Topic-Administration und öffentliche Adapter schließen | P1 | — | [G-014](gaps.md#g-014), [G-041](gaps.md#g-041) | completed |
| [WP-17](#wp-17) | Claim-Identity-Judge validieren | P2 | — | [G-016](gaps.md#g-016) | completed |
| [WP-18](#wp-18) | SEO-Repositoryadapter ausführen | P2 | — | [G-017](gaps.md#g-017) | completed |
| [WP-19](#wp-19) | Schedulerqueries und persistente Claims prüfen | P2 | [WP-01](work-packages.md#wp-01) | [G-031](gaps.md#g-031) | completed |
| [WP-20](#wp-20) | Topic-Notizen als Text absichern | P1 | — | [G-018](gaps.md#g-018) | completed |
| [WP-21](#wp-21) | Adminfehler aus dem echten Appumschlag anzeigen | P2 | — | [G-019](gaps.md#g-019) | completed |
| [WP-22](#wp-22) | Benchmark-Adminadapter und Viewer prüfen | P2 | — | [G-015](gaps.md#g-015) | completed |
| [WP-23](#wp-23) | Inhalt der OG-Karte wirksam prüfen | P2 | — | [G-020](gaps.md#g-020) | completed |
| [WP-24](#wp-24) | Analytics-Opt-out dynamisch prüfen | P2 | — | [G-021](gaps.md#g-021) | completed |
| [WP-25](#wp-25) | Wartungsskripte isoliert absichern | P1 | — | [G-022](gaps.md#g-022), [G-023](gaps.md#g-023) | completed |
| [WP-26](#wp-26) | HTTP-Body- und lokale Transportgrenzen ergänzen | P2 | — | [G-032](gaps.md#g-032), [G-033](gaps.md#g-033) | completed |
| [WP-27](#wp-27) | Feedback und Statistikwrites verbinden | P2 | — | [G-034](gaps.md#g-034) | completed |
| [WP-28](#wp-28) | Unterstützte Hilfs-CLIs prüfen | P3 | — | [G-035](gaps.md#g-035) | completed |
| [WP-29](#wp-29) | Persistierte Nutzerreisen durch alle internen Schichten prüfen | P1 | [WP-03](work-packages.md#wp-03), [WP-07](work-packages.md#wp-07), [WP-08](work-packages.md#wp-08), [WP-09](work-packages.md#wp-09), [WP-10](work-packages.md#wp-10), [WP-12](work-packages.md#wp-12), [WP-13](work-packages.md#wp-13), [WP-14](work-packages.md#wp-14) | [G-030](gaps.md#g-030) | completed |
| [WP-30](#wp-30) | Vendorhelper mit echtem temporärem Dateisystem prüfen | P2 | — | [G-036](gaps.md#g-036) | completed |
| [WP-31](#wp-31) | HTTPException-Header durch main bewahren | P1 | — | [G-037](gaps.md#g-037) | completed |
| [WP-32](#wp-32) | Agentdetail und Turn-Stop durch HTTP absichern | P1 | — | [G-039](gaps.md#g-039) | completed |
| [WP-33](#wp-33) | Modellrollback gegen fremde Writes absichern | P1 | — | [G-040](gaps.md#g-040) | completed |
| [WP-34](#wp-34) | Benchmarkfehler von Enthaltung trennen | P1 | — | [G-042](gaps.md#g-042) | completed |
| [WP-35](#wp-35) | Google-Aktionsclaims mit nativen Transaktionen prüfen | P1 | — | [G-043](gaps.md#g-043) | completed |
| [WP-36](#wp-36) | Cloud-Dateiablage und verteilte Löschkaskade integrieren | P2 | — | [G-044](gaps.md#g-044) | completed |
| [WP-37](#wp-37) | Outbox-/Probeclaims mit nativer SDK-Konkurrenz absichern | P1 | — | [G-045](gaps.md#g-045) | completed |
| [WP-38](#wp-38) | Aktuelle Testfehler und abweichenden Benchmark-Wiederholungslauf klären | P2 | — | [G-046](gaps.md#g-046) | completed |

<a id="wp-01"></a>

## WP-01 · Bekannte Fixture- und Stringfehler bereinigen

**Ziel:** F-01/F-02/F-03 erreichen wieder ihren eigentlichen Prüfvertrag.

**Befunde:** [G-027](gaps.md#g-027), [G-028](gaps.md#g-028) · **Vorher:** —

**Stand:** completed. Veraltete Watch-/Pendingfixtures und Footerstring ersetzt; heutige Limits, Idempotenz und echte archivierte Drawerknoten geprüft.

**Vorgehen:** Aktuelle Produktionsvalidierung lesen; gültige Pending-/Watchdaten herstellen, Footer fachlich statt über exakten Klassenstring prüfen. Erst fehlschlagende Ausgangsläufe festhalten.

**Abnahme zusätzlich zu den verknüpften Then-/Negativkontrollen:** Alle drei Altfehler erklärt und gezielt grün; Race-/Aktionsassertions mindestens gleich stark; keine gelockerten Produktguards, Skips oder pauschalen Snapshots.

**Produktstellen:** [static/js/consensus-run.js](../../../static/js/consensus-run.js), [tests/e2e/test_phase2_transactions.py](../../../tests/e2e/test_phase2_transactions.py), [tests/test_consensus_progress_ui.py](../../../tests/test_consensus_progress_ui.py)

**Test-/Dokumentziele:** [tests/e2e/test_phase2_transactions.py](../../../tests/e2e/test_phase2_transactions.py), [tests/js/stored-turn-markers.test.mjs](../../../tests/js/stored-turn-markers.test.mjs), [tests/test_consensus_progress_ui.py](../../../tests/test_consensus_progress_ui.py)

**Vorhandene Hilfen:** [app/services/share_snapshots.py](../../../app/services/share_snapshots.py), [app/services/watch_service.py](../../../app/services/watch_service.py), [tests/e2e/test_reader_review_regressions.py](../../../tests/e2e/test_reader_review_regressions.py)

**Befehle/Prüfauftrag nach Implementierung:**

- ` RUN_E2E=1 python -m pytest tests/e2e/test_phase2_transactions.py -q (Demo-Emulator) `
- ` python -m pytest tests/test_consensus_progress_ui.py -q; npm test -- tests/js/stored-turn-markers.test.mjs `

**Zu beachten:** —

**Implementierungsnachweis:** ` acdadb91 ` · [docs/test-coverage/product/implementation-persistence.md](implementation-persistence.md) · [docs/test-coverage/execution.json](../execution.json)

**Ausgeführte Testbereiche:** [tests/e2e/test_phase2_transactions.py](../../../tests/e2e/test_phase2_transactions.py), [tests/test_consensus_progress_ui.py](../../../tests/test_consensus_progress_ui.py), [tests/js/stored-turn-markers.test.mjs](../../../tests/js/stored-turn-markers.test.mjs)

**Beobachtete Negativkontrolle:** Watchquotaguard entfernt; DOM prüft Zielturn und unveränderten Fremdturn.

**Verbleibende Grenze:** Keine pauschalen Snapshots oder gelockerten Produktguards.


<a id="wp-02"></a>

## WP-02 · Report-Race unter kontrollierter Emulatorumgebung klären

**Ziel:** Ursache des abweichenden Parallelreport-Laufs ermitteln.

**Befunde:** [G-029](gaps.md#g-029) · **Vorher:** [WP-01](work-packages.md#wp-01)

**Stand:** completed. Reportzähler und Gründe verlieren keine erfolgreichen Inkremente. Indexstatus bleibt gemäß R19 unverändert; konkrete ABORTED-Fälle werden vor gesondertem Replay gezählt.

**Vorgehen:** Java21/Emulator dokumentieren, Kontamination zwischen Fällen ausschließen; isolierten und vollständigen Transaktionslauf mit gleichen IDs-/Zeitregeln vergleichen. Nur gezielte begrenzte Wiederholungen.

**Abnahme zusätzlich zu den verknüpften Then-/Negativkontrollen:** Root-Cause oder eng belegter verbleibender Umgebungsblocker, Result-/Counter-/noindex-Assertions, nachvollziehbarer Wiederholungslauf. Kein unbegründetes Retry-Tuning.

**Produktstellen:** [tests/e2e/test_phase2_transactions.py](../../../tests/e2e/test_phase2_transactions.py)

**Test-/Dokumentziele:** [tests/e2e/test_phase2_transactions.py](../../../tests/e2e/test_phase2_transactions.py)

**Vorhandene Hilfen:** [docs/test-coverage/findings.md](../findings.md), [tests/e2e/README.md](../../../tests/e2e/README.md)

**Befehle/Prüfauftrag nach Implementierung:**

- ` RUN_E2E=1 python -m pytest tests/e2e/test_phase2_transactions.py -v (danach betroffenen Test isoliert) `

**Zu beachten:** —

**Implementierungsnachweis:** ` acdadb91 ` · [docs/test-coverage/product/implementation-persistence.md](implementation-persistence.md) · [docs/test-coverage/execution.json](../execution.json)

**Ausgeführte Testbereiche:** [tests/e2e/test_phase2_transactions.py](../../../tests/e2e/test_phase2_transactions.py)

**Beobachtete Negativkontrolle:** Konstanter Zähler1 statt Inkrement wird erkannt.

**Verbleibende Grenze:** SDK-Retryerschöpfung ist kein Erfolg; keine Ausfallfreiheit unter Last zugesagt.


<a id="wp-03"></a>

## WP-03 · Aktuelle Browserfälle ausführen und Fehler einordnen

**Ziel:** Alle 368 aktuellen E2E-Fälle mit Browser-/Native-/Smoke-Grenzen und tatsächlichen Runnerresultaten belegen.

**Befunde:** [G-025](gaps.md#g-025) · **Vorher:** [WP-01](work-packages.md#wp-01)

**Stand:** completed. Der vollständige integrierte E2E-Lauf umfasst 368 bestandene Fälle ohne Fehler oder Skips: native SDK-Transaktionen, writerfreie Browserdetails, 43 aktuelle Smoke-Fälle und sechs persistierte Reisen. App-/Browserversion, ursprüngliche Runneridentitäten und neue/entfallene IDs gegenüber dem früheren Inventar sind archiviert.

**Vorgehen:** Chromium passend zu Playwright installieren, Build und sichere E2E-Voraussetzungen prüfen. Vollständige Suite ausführen, echte Produkt-/Fixture-/Infrastrukturfehler getrennt bearbeiten.

**Abnahme zusätzlich zu den verknüpften Then-/Negativkontrollen:** Alle 368 aktuellen E2E-Fälle zugeordnet, kein unbemerkter Collect-/Skipverlust; Browser- und Appversion, JUnit und gezielte Fehlerscreenshots/Traces vorhanden. Neue Fälle separat zählen.

**Produktstellen:** [tests/e2e/conftest.py](../../../tests/e2e/conftest.py)

**Test-/Dokumentziele:** [docs/test-coverage/execution.json](../execution.json), [tests/e2e](../../../tests/e2e), [tests/e2e/test_phase4_frontend.py](../../../tests/e2e/test_phase4_frontend.py), [tests/e2e/test_smoke.py](../../../tests/e2e/test_smoke.py), [tests/e2e/test_topic_frontend.py](../../../tests/e2e/test_topic_frontend.py)

**Vorhandene Hilfen:** [docs/testing.md](../../testing.md), [tests/e2e/README.md](../../../tests/e2e/README.md)

**Befehle/Prüfauftrag nach Implementierung:**

- ` python -m playwright install chromium; RUN_E2E=1 python -m pytest tests/e2e -q (sicheres vollständiges Emulatorprofil) `

**Zu beachten:** [D-05](decisions.md#d-05)

**Implementierungsnachweis:** ` ffaca3df ` · [docs/test-coverage/product/implementation-browser.md](implementation-browser.md) · [docs/test-coverage/execution.json](../execution.json)

**Ausgeführte Testbereiche:** [tests/e2e/test_phase4_frontend.py](../../../tests/e2e/test_phase4_frontend.py), [tests/e2e/test_topic_frontend.py](../../../tests/e2e/test_topic_frontend.py), [tests/e2e/test_smoke.py](../../../tests/e2e/test_smoke.py)

**Beobachtete Negativkontrolle:** Alte Admin-/Scrollquellen gegen neue Tests liefern gezielte Fehler, belegter Port wird abgewiesen.

**Verbleibende Grenze:** GitHubjob 110800783463 auf ffaca3df mit Chromium 148.0.7778.96/Playwright 1.60.0 bestanden; konkrete Mockgrenzen bleiben je Datei erhalten. Keine Behauptung einer flächigen visuellen oder Liveanbieter-Abnahme.


<a id="wp-04"></a>

## WP-04 · Windows-Einstieg verifizieren

**Ziel:** Die zwölf Linux-Skips durch Windows-Evidenz ergänzen.

**Befunde:** [G-026](gaps.md#g-026) · **Vorher:** —

**Stand:** completed. Alle 28 CLI-Vertragsfälle in Windows PowerShell und pwsh sowie reale dev.ps1-Aufrufe für Backend, Frontend/Build, 49 Rulesfälle und vier native Phase2-Fälle liefen im Windows-CI-Job erfolgreich.

**Vorgehen:** Vorhandene CLI-Doubles auf unterstütztem Windows/PowerShell ausführen; echte repräsentative dev.ps1-Aufrufe ergänzen, ohne eine zweite Suiteauswahl zu pflegen.

**Abnahme zusätzlich zu den verknüpften Then-/Negativkontrollen:** Alle 14 Varianten je verfügbarer Windows-Shell wirklich ausgeführt; Shellversionen und tatsächliche Fallzahl (derzeit 14 oder 28) dokumentiert. Fehlercodes, Argumente, Arbeitsverzeichnis und Envwiederherstellung belegt.

**Produktstellen:** [dev.ps1](../../../dev.ps1)

**Test-/Dokumentziele:** [.github/workflows/tests.yml](../../../.github/workflows/tests.yml), [tests/test_dev_cli.py](../../../tests/test_dev_cli.py)

**Vorhandene Hilfen:** [dev.ps1](../../../dev.ps1), [docs/testing.md](../../testing.md)

**Befehle/Prüfauftrag nach Implementierung:**

- ` Windows: python -m pytest tests/test_dev_cli.py -q `

**Zu beachten:** —

**Implementierungsnachweis:** ` ffaca3df ` · [docs/test-coverage/product/implementation-runtime.md](implementation-runtime.md) · [docs/test-coverage/execution.json](../execution.json)

**Ausgeführte Testbereiche:** [tests/test_dev_cli.py](../../../tests/test_dev_cli.py)

**Beobachtete Negativkontrolle:** Fehlercode/Env/Emulatorteardown und fehlende Auswahl werden beobachtet.

**Verbleibende Grenze:** Windows-GitHubjob 110800783247 auf integriertem Code ffaca3df erfolgreich: https://github.com/sudoleo/consens/actions/runs/36995379657/job/110800783247 . Native Windowsfälle ergänzen die ausdrücklich erhaltenen Linux-Plattformskips. Keine produktiven Credentials oder Cloudwrites.


<a id="wp-05"></a>

## WP-05 · Allgemeine Regression-CI einrichten

**Ziel:** Neue Tests zuverlässig bei Änderungen ausführen.

**Befunde:** [G-024](gaps.md#g-024) · **Vorher:** [WP-01](work-packages.md#wp-01), [WP-02](work-packages.md#wp-02), [WP-03](work-packages.md#wp-03), [WP-04](work-packages.md#wp-04)

**Stand:** completed. Nutzerkonforme schnelle Auswahl und vollständige Auswahl sind belegt. ReadyForReview auf ffaca3df startete alle vier Jobs; Backend, Frontend/Build, Browser/Rules und Windows schlossen erfolgreich ab. Linux-Plattformskips bleiben separat sichtbar; der primäre lokale Windows-Backendlauf enthält sämtliche 3303 Fälle bestanden.

**Vorgehen:** Vier getrennte Jobs mit unveränderter Fehlerpropagation. Nutzerentscheidung caa7bac6: normale Push-/PR-Ereignisse starten Backend und Frontend; ReadyForReview oder manuelles full startet zusätzlich Browser/Rules und Windows. Dokumentänderungen allein lösen den Workflow nicht aus; Publisher-CI bleibt eigenständig.

**Abnahme zusätzlich zu den verknüpften Then-/Negativkontrollen:** Schnelle und ausdrücklich vollständige Auswahl auf dem integrierten Code belegen. Bewusste ereignisabhängige Skips sind transparent, kein Nachweis einer gelaufenen Vollsuite. Kein continue-on-error; echte Assertionfehler müssen den jeweiligen Job rot machen, Fehlerartefakte und leere Auswahl erkennbar. Branchpflichten nur nach Repo-Regeln.

**Produktstellen:** [.github/workflows/publisher-tests.yml](../../../.github/workflows/publisher-tests.yml), [.github/workflows/tests.yml](../../../.github/workflows/tests.yml), [dev.ps1](../../../dev.ps1), [package.json](../../../package.json)

**Test-/Dokumentziele:** [.github/workflows/tests.yml](../../../.github/workflows/tests.yml), [docs/testing.md](../../testing.md), [tests/test_dev_cli.py](../../../tests/test_dev_cli.py)

**Vorhandene Hilfen:** [.github/workflows/publisher-tests.yml](../../../.github/workflows/publisher-tests.yml), [dev.ps1](../../../dev.ps1), [tests/e2e/README.md](../../../tests/e2e/README.md)

**Befehle/Prüfauftrag nach Implementierung:**

- ` Neue Jobs auf genau dem integrierten Commit prüfen; kein einzelner Publisher-Erfolg als Gesamtsuite-Erfolg werten. `

**Zu beachten:** —

**Implementierungsnachweis:** ` ffaca3df ` · [docs/test-coverage/product/implementation-runtime.md](implementation-runtime.md) · [docs/test-coverage/execution.json](../execution.json)

**Ausgeführte Testbereiche:** [tests/test_dev_cli.py](../../../tests/test_dev_cli.py)

**Beobachtete Negativkontrolle:** Realer CI-Lauf auf 2afe0cf1: 25 fehlgeschlagene Fälle, 343 bestanden; Exit 1 führt zum roten Job110781068840 und trotzdem archiviertem Artefakt11218892950. Tatsächlicher Fehlerpropagationsbeleg, kein absichtlich injizierter Mutant.

**Verbleibende Grenze:** Voll-CI https://github.com/sudoleo/consens/actions/runs/36995379657 auf ffaca3df erfolgreich. Gewöhnliche Push-/PR-Läufe bleiben nach ausdrücklicher Nutzerentscheidung schnell; reine Dokumentänderungen lösen keine weitere Vollsuite aus.


<a id="wp-06"></a>

## WP-06 · Firestore-Regeln durch echte Clientoperationen schützen

**Ziel:** Direkte Clientrechte dürfen nie Admin-SDK-Rechte erben.

**Befunde:** [G-001](gaps.md#g-001) · **Vorher:** [WP-01](work-packages.md#wp-01)

**Stand:** completed. 49 echte Clientfälle: zwölf tatsächliche private Servicepfade mit vier Identitäten und Denial-Negativkontrolle.

**Vorgehen:** Isolierten Rules-Testharness verwenden, Regeln aus Repository laden, Admin nur fürs Seed/Teardown. Anonym/Owner/Fremdidentität und Untercollections prüfen.

**Abnahme zusätzlich zu den verknüpften Then-/Negativkontrollen:** Reale permission-denied-Nachweise und allow-true-Negativkontrolle. Test wird durch den vorgesehenen Runner/CI tatsächlich entdeckt.

**Produktstellen:** [firestore.rules](../../../firestore.rules), [tests/e2e/test_agent_transactions.py](../../../tests/e2e/test_agent_transactions.py)

**Test-/Dokumentziele:** [tests/rules/firestore.rules.test.mjs](../../../tests/rules/firestore.rules.test.mjs)

**Vorhandene Hilfen:** [firebase.json](../../../firebase.json), [tests/e2e/README.md](../../../tests/e2e/README.md)

**Befehle/Prüfauftrag nach Implementierung:**

- ` Separaten Rules-Runner mit dem lokalen Demo-Emulator einrichten; nicht den bestehenden Vitest-Glob oder Admin-SDK als Rules-Test verwenden. `

**Zu beachten:** —

**Implementierungsnachweis:** ` c4710a97 ` · [docs/test-coverage/product/implementation-runtime.md](implementation-runtime.md) · [docs/test-coverage/execution.json](../execution.json)

**Ausgeführte Testbereiche:** [tests/rules/firestore.rules.test.mjs](../../../tests/rules/firestore.rules.test.mjs)

**Beobachtete Negativkontrolle:** Temporärer erlaubter Ownerwrite lässt dieselbe Denialassertion scheitern; Regeln im finally wiederhergestellt.

**Verbleibende Grenze:** Emulator, keine produktive Rules-/IAMfreigabe.


<a id="wp-07"></a>

## WP-07 · Reguläre Usage nativ atomar prüfen

**Ziel:** Gemeinsames Tokenkonto mit nativer Firestore-Admission, Buchung und Freigabe absichern.

**Befunde:** [G-002](gaps.md#g-002) · **Vorher:** [WP-01](work-packages.md#wp-01)

**Stand:** completed. Admission, letzter Betrag, Buchung, Release/Consume, UTC-Tage und Kontrollowner nativ belegt.

**Vorgehen:** Bestehende Usage-Regeln als Oracle verwenden; Firestoreemulator und explizite Barrieren statt Thread-Lock-Fake für die entscheidende Transaktion.

**Abnahme zusätzlich zu den verknüpften Then-/Negativkontrollen:** Endzustände für gleicher Key, verschiedene Keys, letzter Slot, Release/Consume und UTC-Wechsel; getrennte Owner; Negativkontrolle entdeckt fehlende Atomarität.

**Produktstellen:** [app/services/usage_repository.py](../../../app/services/usage_repository.py)

**Test-/Dokumentziele:** [tests/e2e/test_usage_transactions.py](../../../tests/e2e/test_usage_transactions.py)

**Vorhandene Hilfen:** [app/core/e2e_profile.py](../../../app/core/e2e_profile.py), [tests/e2e/test_agent_transactions.py](../../../tests/e2e/test_agent_transactions.py), [tests/usage_test_support.py](../../../tests/usage_test_support.py)

**Befehle/Prüfauftrag nach Implementierung:**

- ` RUN_E2E=1 python -m pytest tests/e2e/test_usage_transactions.py -q (mit sicherem Demo-Emulatorprofil) `

**Zu beachten:** —

**Implementierungsnachweis:** ` 1d574233 ` · [docs/test-coverage/product/implementation-persistence.md](implementation-persistence.md) · [docs/test-coverage/execution.json](../execution.json)

**Ausgeführte Testbereiche:** [tests/e2e/test_usage_transactions.py](../../../tests/e2e/test_usage_transactions.py)

**Beobachtete Negativkontrolle:** Dedupguard entfernt: Doppelabbuchung; zusätzlich echte SDK-Reads/Writes aus Transaktion verlagert: zwei Admissions bzw. verlorene unabhängige Buchung erkannt.

**Verbleibende Grenze:** Lokaler Emulator mit anonymen Credentials; kein Produktkonto, keine produktive IAM-/Lastgarantie. Nur eigene Dokumentwurzeln werden aufgeräumt.


<a id="wp-08"></a>

## WP-08 · Chat-Lebenszyklus gegen späte Writes absichern

**Ziel:** Delete/Turn/Completion-Konkurrenz ohne wiederbelebte Daten.

**Befunde:** [G-003](gaps.md#g-003) · **Vorher:** [WP-01](work-packages.md#wp-01)

**Stand:** completed. Echter Deleteprozess pausiert nach Tombstonecommit vor Purge; Completion/Create/Failure verändern weder vorhandene Nachfahren noch Löschjob. Beide finalen Commitreihenfolgen, Contextfence und vollständige Kaskade bleiben belegt.

**Vorgehen:** Beide zulässigen Commitreihenfolgen deterministisch herstellen, Antwort-/Context-/Turn-Dokumente direkt prüfen; bestehendes Create-Chat-Limit weiterlaufen lassen.

**Abnahme zusätzlich zu den verknüpften Then-/Negativkontrollen:** Keine eigenen Waisen nach abgeschlossenem Delete, Kontrollowner unverändert, Stop/Failure/Completion präzise klassifiziert; kein Mock des entscheidenden Guards.

**Produktstellen:** [app/services/chat_store.py](../../../app/services/chat_store.py)

**Test-/Dokumentziele:** [tests/e2e/test_chat_lifecycle_transactions.py](../../../tests/e2e/test_chat_lifecycle_transactions.py)

**Vorhandene Hilfen:** [tests/e2e/test_phase2_transactions.py](../../../tests/e2e/test_phase2_transactions.py), [tests/test_chat_history.py](../../../tests/test_chat_history.py)

**Befehle/Prüfauftrag nach Implementierung:**

- ` RUN_E2E=1 python -m pytest tests/e2e/test_chat_lifecycle_transactions.py -q (Demo-Emulator) `

**Zu beachten:** —

**Implementierungsnachweis:** ` 1d574233 ` · [docs/test-coverage/product/implementation-persistence.md](implementation-persistence.md) · [docs/test-coverage/execution.json](../execution.json)

**Ausgeführte Testbereiche:** [tests/e2e/test_chat_lifecycle_transactions.py](../../../tests/e2e/test_chat_lifecycle_transactions.py)

**Beobachtete Negativkontrolle:** Exakter Active-/Deleting-Guard entfernt: unerlaubter Write im Zwischenzustand erkannt; terminaler Statusguard zusätzlich separat mutiert.

**Verbleibende Grenze:** Lokaler Emulator mit anonymen Credentials; kein Produktkonto, keine produktive IAM-/Lastgarantie. Nur eigene Dokumentwurzeln werden aufgeräumt.


<a id="wp-09"></a>

## WP-09 · Kontokaskade und API-Cleanup integrieren

**Ziel:** Alle Datenbereiche inklusive Resume nach Teilfehler.

**Befunde:** [G-004](gaps.md#g-004) · **Vorher:** [WP-08](work-packages.md#wp-08), [WP-11](work-packages.md#wp-11)

**Stand:** completed. Alle16 aktuellen Bereiche mit expliziter Inventarassertion; Retry, fehlende Parentdokumente, verlorene Checkpoints, Kontrollowner und minimaler Tombstone belegt.

**Vorgehen:** Aus tatsächlichem areas-Tupel vollständiges Seedinventar bauen, Services ausführen und nur externe Firebase-Auth/Mail/Telegram-Grenzen ersetzen; Teilfehler und neue Instanz injizieren. Bereichserfolg mit anschließendem Checkpointverlust separat vom eigentlichen Löschfehler prüfen; Wiederaufnahme aus dauerhaft gespeichertem Zustand lesen.

**Abnahme zusätzlich zu den verknüpften Then-/Negativkontrollen:** Alle 16 aktuellen Bereiche mit explizitem Endzustand, kein Fremddatenverlust; pending/Retry und bereits authentifizierte Late-Writes geprüft. Änderungen des Bereichsinventars erzwingen Review. Persistiert bestätigte Bereiche überspringen, unbestätigte Operationen idempotent wiederholen. Minimalen UID-Sperrtombstone bis zum Aufbewahrungsende erhalten und Cleanup-E-Mail bei Abschluss entfernen.

**Produktstellen:** [app/services/account_deletion.py](../../../app/services/account_deletion.py), [app/services/api_account_cleanup.py](../../../app/services/api_account_cleanup.py)

**Test-/Dokumentziele:** [tests/e2e/test_account_deletion_transactions.py](../../../tests/e2e/test_account_deletion_transactions.py), [tests/test_api_account_cleanup.py](../../../tests/test_api_account_cleanup.py)

**Vorhandene Hilfen:** [tests/test_account_deletion_retry.py](../../../tests/test_account_deletion_retry.py), [tests/test_chat_history.py](../../../tests/test_chat_history.py)

**Befehle/Prüfauftrag nach Implementierung:**

- ` python -m pytest tests/test_api_account_cleanup.py tests/test_account_deletion_retry.py -q; anschließend neuer Emulator-Kaskadentest `

**Zu beachten:** —

**Implementierungsnachweis:** ` acdadb91 ` · [docs/test-coverage/product/implementation-persistence.md](implementation-persistence.md) · [docs/test-coverage/execution.json](../execution.json)

**Ausgeführte Testbereiche:** [tests/e2e/test_account_deletion_transactions.py](../../../tests/e2e/test_account_deletion_transactions.py)

**Beobachtete Negativkontrolle:** Receiptcleanup ausgelassen: verbleibende persönliche Daten erkannt.

**Verbleibende Grenze:** Auth- und Cloudobjektgrenzen ersetzt; keine produktive Lösch-/IAMfreigabe.


<a id="wp-10"></a>

## WP-10 · Memory-Revision, Undo und Löschsperre stärken

**Ziel:** Vorhandene Erfolgsroundtrips um konkurrierende Zustände ergänzen.

**Befunde:** [G-007](gaps.md#g-007), [G-008](gaps.md#g-008), [G-038](gaps.md#g-038) · **Vorher:** [WP-01](work-packages.md#wp-01)

**Stand:** completed. Datenverlust bei Limitabsenkung behoben. Native Revision/Lease/Tombstone/Commitfehler und volle echte main-HTTP-Matrix mit Auth/Tier/Owner/Expiry/Konflikt/Repeat ohne Providerarbeit belegt.

**Vorgehen:** Unit-/Routerfälle auf echten Revisions-/Ownerguard ausrichten; nativer Commitfall für partielle Writes. Patch/Undo-Fehler müssen gespeicherten Inhalt unverändert lassen. Undo auch als echte HTTP-Anfrage ausführen. Bei kleinerem Tier-/Adminlimit den kompletten Vorzustand vergleichen; die derzeitige stille Kürzung aus P-02 nicht als Sollverhalten übernehmen.

**Abnahme zusätzlich zu den verknüpften Then-/Negativkontrollen:** M-01 überlebt die neuen Tests nicht; Konflikt, expiry, Fremd-ID, Retry, manueller Save und Tombstone belegt. Kostenverhalten folgt aktueller Abrechnung. P-02 muss regressionswirksam abgesichert werden: bei unzulässigem Vorprofil strukturierte Ablehnung ohne Writes (empfohlen), andernfalls explizit entschiedene verlustfreie Rücknahme. Kein undone bei Datenverlust. main-Status/Body für Auth, Tierausfall und MemoryEditError geprüft.

**Produktstellen:** [app/services/memory_edit.py](../../../app/services/memory_edit.py), [app/api/routers/users.py](../../../app/api/routers/users.py)

**Test-/Dokumentziele:** [tests/e2e/test_memory_edit_transactions.py](../../../tests/e2e/test_memory_edit_transactions.py), [tests/test_memory_edit.py](../../../tests/test_memory_edit.py), [tests/test_memory_http_contract.py](../../../tests/test_memory_http_contract.py)

**Vorhandene Hilfen:** [app/services/persistence_guard.py](../../../app/services/persistence_guard.py), [tests/test_memory_edit.py](../../../tests/test_memory_edit.py)

**Befehle/Prüfauftrag nach Implementierung:**

- ` python -m pytest tests/test_memory_edit.py -q `
- ` python -m pytest tests/test_memory_edit.py -q; ergänzend Memory-Emulatortest `

**Zu beachten:** —

**Implementierungsnachweis:** ` b517b3f5 ` · [docs/test-coverage/product/implementation-persistence.md](implementation-persistence.md) · [docs/test-coverage/execution.json](../execution.json)

**Ausgeführte Testbereiche:** [tests/test_memory_edit.py](../../../tests/test_memory_edit.py), [tests/e2e/test_memory_edit_transactions.py](../../../tests/e2e/test_memory_edit_transactions.py), [tests/test_memory_http_contract.py](../../../tests/test_memory_http_contract.py)

**Beobachtete Negativkontrolle:** Verlustschutz entfernt: Undo kürzt; zusätzlich Undo-Revisionsguard im isolierten Prozess entfernt: echter HTTPfall liefert200 statt409.

**Verbleibende Grenze:** Synthetische Profile; keine Live-Modellqualität.


<a id="wp-11"></a>

## WP-11 · API-Recovery und historischen Source-Adapter prüfen

**Ziel:** Durable Runs und ihre historischen Quellen nach Restart.

**Befunde:** [G-005](gaps.md#g-005), [G-010](gaps.md#g-010) · **Vorher:** —

**Stand:** completed. Ausgeführte Recoveryaufträge, lebende/abgelaufene Leases, kein zweiter Providerstart/Verbrauch; historischer Sourceadapter bindet alle Identitäten/Versionen, Pagination und Pollrevision. Backfill liest Run und Mapping transaktional neu.

**Vorgehen:** Vorhandene Recovery-/Billing-Identity-Tests anerkennen; fehlende Retention-/Backfill-/Restartfälle und historischen Source-Adapter ergänzen.

**Abnahme zusätzlich zu den verknüpften Then-/Negativkontrollen:** Kein doppelter Providerstart, keine Löschung lebender Daten oder falsche historische Bindung; Cursor/revision/Ownership/Leases/Backfill-Grenzen belegt.

**Produktstellen:** [app/api/routers/api_v1.py](../../../app/api/routers/api_v1.py), [app/services/api_consensus_runner.py](../../../app/services/api_consensus_runner.py), [app/services/api_run_repository.py](../../../app/services/api_run_repository.py)

**Test-/Dokumentziele:** [tests/e2e/test_api_retention_transactions.py](../../../tests/e2e/test_api_retention_transactions.py), [tests/test_api_run_recovery.py](../../../tests/test_api_run_recovery.py), [tests/test_api_run_repository.py](../../../tests/test_api_run_repository.py), [tests/test_api_source_history.py](../../../tests/test_api_source_history.py), [tests/test_consensus_api.py](../../../tests/test_consensus_api.py), [tests/test_source_check_api.py](../../../tests/test_source_check_api.py)

**Vorhandene Hilfen:** [tests/test_api_run_repository.py](../../../tests/test_api_run_repository.py), [tests/test_consensus_api.py](../../../tests/test_consensus_api.py), [tests/test_source_check_repository.py](../../../tests/test_source_check_repository.py), [tests/usage_test_support.py](../../../tests/usage_test_support.py)

**Befehle/Prüfauftrag nach Implementierung:**

- ` python -m pytest tests/test_api_run_recovery.py tests/test_api_run_repository.py tests/test_consensus_api.py -q `
- ` python -m pytest tests/test_consensus_api.py tests/test_source_check_api.py tests/test_source_check_scope.py -q `

**Zu beachten:** [D-01](decisions.md#d-01)

**Implementierungsnachweis:** ` c723e42b ` · [docs/test-coverage/product/implementation-adapters.md](implementation-adapters.md) · [docs/test-coverage/execution.json](../execution.json)

**Ausgeführte Testbereiche:** [tests/test_api_run_recovery.py](../../../tests/test_api_run_recovery.py), [tests/test_api_source_history.py](../../../tests/test_api_source_history.py), [tests/e2e/test_api_retention_transactions.py](../../../tests/e2e/test_api_retention_transactions.py)

**Beobachtete Negativkontrolle:** Run-ID-Bindung vor Mappingupdate entfernt: fremde Ablaufdaten ändern sich.

**Verbleibende Grenze:** Infrastruktur/Providergrenzen kontrolliert; keine produktive Restart-/Lastfreigabe.


<a id="wp-12"></a>

## WP-12 · Registrierungsrace und user_status verbinden

**Ziel:** Tatsächliche Auth-/Tarifpayloads an der HTTP-Grenze.

**Befunde:** [G-009](gaps.md#g-009), [G-012](gaps.md#g-012) · **Vorher:** —

**Stand:** completed. Echter Registrierungsservice behandelt Lookup/Create-Race neutral ohne doppelte Neunutzerbenachrichtigung. user_status führt reale Rollen-/Tarifmatrix und Tierausfall aus.

**Vorgehen:** Lookup/Create-Race gezielt vom Firebase-SDK-Double auslösen; echten Provisioner/Statushandler verwenden. Free-Admin separat von Pro modellieren.

**Abnahme zusätzlich zu den verknüpften Then-/Negativkontrollen:** Gleiche öffentliche Registrierungsantwort, keine Doppelbenachrichtigung; Tarif-/Rollenmatrix und Tierausfall mit fail-closed Verhalten.

**Produktstellen:** [app/api/routers/users.py](../../../app/api/routers/users.py), [app/services/registration.py](../../../app/services/registration.py)

**Test-/Dokumentziele:** [tests/test_auth_session.py](../../../tests/test_auth_session.py), [tests/test_http_adapter_auth.py](../../../tests/test_http_adapter_auth.py), [tests/test_registration_security.py](../../../tests/test_registration_security.py), ` tests/test_user_status.py ` (vorgeschlagen)

**Vorhandene Hilfen:** [tests/js/plus-tier-gates.test.mjs](../../../tests/js/plus-tier-gates.test.mjs), [tests/test_account_tier_admin.py](../../../tests/test_account_tier_admin.py), [tests/test_auth_session.py](../../../tests/test_auth_session.py), [tests/test_tier_cache.py](../../../tests/test_tier_cache.py)

**Befehle/Prüfauftrag nach Implementierung:**

- ` python -m pytest tests/test_registration_security.py tests/test_auth_session.py -q `
- ` python -m pytest tests/test_user_status.py tests/test_tier_cache.py tests/test_plus_tier.py -q `

**Zu beachten:** —

**Implementierungsnachweis:** ` c723e42b ` · [docs/test-coverage/product/implementation-adapters.md](implementation-adapters.md) · [docs/test-coverage/execution.json](../execution.json)

**Ausgeführte Testbereiche:** [tests/test_http_adapter_auth.py](../../../tests/test_http_adapter_auth.py)

**Beobachtete Negativkontrolle:** Create-Racebehandlung entfernt: neutrale Antworten stimmen nicht mehr überein.

**Verbleibende Grenze:** Firebase-SDK-Authentifizierung und DB ersetzt; externe Modell-, Mail- und Telegramgrenzen kontrolliert. Kein Live-OAuth oder produktiver Versand.


<a id="wp-13"></a>

## WP-13 · App-Share-POST integrieren

**Ziel:** Der Appadapter publiziert ausschließlich autoritative eigene Ergebnisse.

**Befunde:** [G-011](gaps.md#g-011) · **Vorher:** [WP-01](work-packages.md#wp-01)

**Stand:** completed. App-POST schreibt das autoritative Pendingergebnis, verwirft gefälschte Inhalts-/Owner-/Visibilityfelder und prüft Quota/Ablauf/Retry. Antwort und persistierter Share stimmen überein.

**Vorgehen:** Route plus Snapshotservice ausführen, gültigen Pending-Datensatz nutzen; main-Fehlerumschlag und Owner/Visibility/Quota/Retry prüfen.

**Abnahme zusätzlich zu den verknüpften Then-/Negativkontrollen:** Response und gespeicherte Ressource stimmen überein; fremde/abgelaufene/gefälschte Payload abgelehnt. API-v1-Test wird nicht als Ersatz gezählt.

**Produktstellen:** [app/api/routers/share.py](../../../app/api/routers/share.py)

**Test-/Dokumentziele:** [tests/test_share_feature.py](../../../tests/test_share_feature.py), [tests/test_share_http_contract.py](../../../tests/test_share_http_contract.py)

**Vorhandene Hilfen:** [tests/test_bookmarks.py](../../../tests/test_bookmarks.py), [tests/test_share_feature.py](../../../tests/test_share_feature.py)

**Befehle/Prüfauftrag nach Implementierung:**

- ` python -m pytest tests/test_share_feature.py -q `

**Zu beachten:** —

**Implementierungsnachweis:** ` c723e42b ` · [docs/test-coverage/product/implementation-adapters.md](implementation-adapters.md) · [docs/test-coverage/execution.json](../execution.json)

**Ausgeführte Testbereiche:** [tests/test_share_http_contract.py](../../../tests/test_share_http_contract.py)

**Beobachtete Negativkontrolle:** Private statt autoritativer public-Visibility geschrieben: Storeassertion wird rot.

**Verbleibende Grenze:** Firebase-SDK-Authentifizierung und DB ersetzt; externe Modell-, Mail- und Telegramgrenzen kontrolliert. Kein Live-OAuth oder produktiver Versand.


<a id="wp-14"></a>

## WP-14 · Source-Queue mit nativen Leases prüfen

**Ziel:** Alte Worker dürfen nach Reclaim nichts committen.

**Befunde:** [G-006](gaps.md#g-006) · **Vorher:** [WP-01](work-packages.md#wp-01)

**Stand:** completed. Native Claims/Takeover/Paketabschluss/Delete/Pagination/Revision plus tatsächlicher Own-Key-Workerpfad. Fremder Worker und Fremdowner bleiben gesperrt; nur gebundener Judge erhält flüchtigen Dummykey, kein Key in entpackter DB/Cache/Workerlogs, kein zweiter Providercall.

**Vorgehen:** Claim-/Finish-/Delete-Reihenfolgen im Emulator mit getrennten Repositoryinstanzen; Credentialprovider bleibt außerhalb der DB.

**Abnahme zusätzlich zu den verknüpften Then-/Negativkontrollen:** Nur aktuelle Lease, genau einmal Paketabschluss, keine Wiederanlage, korrekte Version/Pagination; keine eigenen Keys in Dokumenten oder Logs.

**Produktstellen:** [app/services/source_check_repository.py](../../../app/services/source_check_repository.py)

**Test-/Dokumentziele:** [tests/e2e/test_source_check_transactions.py](../../../tests/e2e/test_source_check_transactions.py)

**Vorhandene Hilfen:** [tests/e2e/test_prompt_config_transactions.py](../../../tests/e2e/test_prompt_config_transactions.py), [tests/test_source_check_jobs.py](../../../tests/test_source_check_jobs.py), [tests/test_source_check_repository.py](../../../tests/test_source_check_repository.py)

**Befehle/Prüfauftrag nach Implementierung:**

- ` RUN_E2E=1 python -m pytest tests/e2e/test_source_check_transactions.py -q (Demo-Emulator) `

**Zu beachten:** —

**Implementierungsnachweis:** ` b517b3f5 ` · [docs/test-coverage/product/implementation-persistence.md](implementation-persistence.md) · [docs/test-coverage/execution.json](../execution.json)

**Ausgeführte Testbereiche:** [tests/e2e/test_source_check_transactions.py](../../../tests/e2e/test_source_check_transactions.py)

**Beobachtete Negativkontrolle:** Leasevergleich entfernt: alter Commit; Own-Key-Affinitätsguard separat entfernt: fremder Worker verarbeitet das native Jobdokument.

**Verbleibende Grenze:** Transiente SDK-Abbrüche werden explizit erfasst; externer Provider ist kein Testziel.


<a id="wp-15"></a>

## WP-15 · Watch- und Telegramadapter schließen

**Ziel:** HTTP-Methoden und Servicegrenzen tatsächlich ausführen.

**Befunde:** [G-013](gaps.md#g-013) · **Vorher:** —

**Stand:** completed. Watch-/Telegramhandler und Abmelde-/Followeradapter prüfen UID/Owner/Tarif, Verbindung, Fehler und Tokenzustände vor Write; Disconnect ist UID-gebunden.

**Vorgehen:** PATCH/DELETE/Link/Test durch echten Router; UID/Allowlist/Entitlements/Servicefehler mit gespeicherten Kontrollzuständen und Notifierdouble prüfen. Telegram-Disconnect und beide Watch-/Follower-Unsubscribe-Routen einschließlich Tokenfehlern und escaped HTML ergänzen.

**Abnahme zusätzlich zu den verknüpften Then-/Negativkontrollen:** Alle sieben bisher unausgeführten Handler verhaltensbasiert geprüft; falscher Owner und nicht verbundener Versand haben keine Nebenwirkung. Ungültige/abgelaufene/falsch typisierte Abmeldetokens ändern keine Daten; Disconnect bleibt UID-gebunden.

**Produktstellen:** [app/api/routers/watch.py](../../../app/api/routers/watch.py)

**Test-/Dokumentziele:** [tests/test_watch_feature.py](../../../tests/test_watch_feature.py), [tests/test_watch_http_contract.py](../../../tests/test_watch_http_contract.py)

**Vorhandene Hilfen:** [tests/test_watch_feature.py](../../../tests/test_watch_feature.py)

**Befehle/Prüfauftrag nach Implementierung:**

- ` python -m pytest tests/test_watch_feature.py -q `

**Zu beachten:** [D-03](decisions.md#d-03)

**Implementierungsnachweis:** ` c723e42b ` · [docs/test-coverage/product/implementation-adapters.md](implementation-adapters.md) · [docs/test-coverage/execution.json](../execution.json)

**Ausgeführte Testbereiche:** [tests/test_watch_http_contract.py](../../../tests/test_watch_http_contract.py)

**Beobachtete Negativkontrolle:** WatchPATCH verwendet fremde UID: Fremdrequest/Nichtmutation schlägt fehl.

**Verbleibende Grenze:** Firebase-SDK-Authentifizierung und DB ersetzt; externe Modell-, Mail- und Telegramgrenzen kontrolliert. Kein Live-OAuth oder produktiver Versand.


<a id="wp-16"></a>

## WP-16 · Topic-Administration und öffentliche Adapter schließen

**Ziel:** Echte Adminberechtigung und vollständige Routenauswahl.

**Befunde:** [G-014](gaps.md#g-014), [G-041](gaps.md#g-041) · **Vorher:** —

**Stand:** completed. Alle Topicadminmethoden prüfen Revocation und projizieren Tierausfall503. Hub/Sitemap unterscheiden Status/noindex korrekt. Neutraler Follow, tatsächlicher Confirm-/Unsubscribe-Link und Escaping ausgeführt.

**Vorgehen:** PUT ausdrücklich aufrufen, Adminprüfung nicht ersetzen; Hub/Sitemap/Follow mit verschiedenen Publikationszuständen und Escapingfällen. Separate Topic-Adminprüfung gegen die zentrale Revocation-/503-Policy prüfen; nur das externe Auth-SDK ersetzen. noindex ausdrücklich von Zugriffs- und Archivzustand unterscheiden. P-04 als roten Grenztest übernehmen; gemeinsame Adminpolicy korrigieren. Adminlist/Confirm/Unsubscribe ebenso ausführen, SDK-Flags und HTTP-Umschlag getrennt prüfen.

**Abnahme zusätzlich zu den verknüpften Then-/Negativkontrollen:** Nonadmin/widerrufenes Token scheitern vor Mutation, Rollendienst-Ausfall liefert 503 gemäß zentraler Adminpolicy. Hub zeigt veröffentlichte aktive/pausierte Topics auch bei noindex; Sitemap schließt noindex aus, beide schließen Archive/unveröffentlichte Topics aus. Follow bleibt neutral/idempotent; Testnamen entsprechen ausgeführten Methoden. G-041 ist ein beobachteter Defekt, kein bloß fehlender Laufnachweis. Für Confirm/Unsubscribe gültige und ungültige Tokenzustände samt Nichtmutation und Escaping prüfen.

**Produktstellen:** [app/api/routers/topics.py](../../../app/api/routers/topics.py), [app/api/routers/admin.py](../../../app/api/routers/admin.py), [app/core/security.py](../../../app/core/security.py)

**Test-/Dokumentziele:** [tests/test_http_adapter_auth.py](../../../tests/test_http_adapter_auth.py), [tests/test_topic_public_http.py](../../../tests/test_topic_public_http.py), [tests/test_topics_feature.py](../../../tests/test_topics_feature.py)

**Vorhandene Hilfen:** [tests/test_auth_revocation.py](../../../tests/test_auth_revocation.py), [tests/test_topics_feature.py](../../../tests/test_topics_feature.py)

**Befehle/Prüfauftrag nach Implementierung:**

- ` python -m pytest tests/test_topics_feature.py tests/test_auth_revocation.py -q `

**Zu beachten:** —

**Implementierungsnachweis:** ` c723e42b ` · [docs/test-coverage/product/implementation-adapters.md](implementation-adapters.md) · [docs/test-coverage/execution.json](../execution.json)

**Ausgeführte Testbereiche:** [tests/test_http_adapter_auth.py](../../../tests/test_http_adapter_auth.py), [tests/test_topic_public_http.py](../../../tests/test_topic_public_http.py)

**Beobachtete Negativkontrolle:** check_revoked entfernt: widerrufener Request/SDK-Flag wird erkannt.

**Verbleibende Grenze:** Firebase-SDK-Authentifizierung und DB ersetzt; externe Modell-, Mail- und Telegramgrenzen kontrolliert. Kein Live-OAuth oder produktiver Versand.


<a id="wp-17"></a>

## WP-17 · Claim-Identity-Judge validieren

**Ziel:** Parser, Schlüsselbindung und Fallback des echten Helpers.

**Befunde:** [G-016](gaps.md#g-016) · **Vorher:** —

**Stand:** completed. Identityhelper/Parser/Retryplan prüft bekannte eindeutige Keys und ausschließlich echte JSON-Integer, begrenzte Inputs/Versuche, sichere Fehlerdiagnose. Fallback bewahrt schon reservierte Keys.

**Vorgehen:** Transportantworten einspeisen, query_claim_identity ausführen. Bekannte/neue/duplizierte Keys und Indexformen systematisch kombinieren.

**Abnahme zusätzlich zu den verknüpften Then-/Negativkontrollen:** Unbekannte/mehrfach verwendete Zuordnungen werden verworfen, Inputs/Versuche begrenzt und Fehler nachvollziehbar. Grenzsemantik vor Änderung dokumentiert.

**Produktstellen:** [app/services/llm/consensus_engine.py](../../../app/services/llm/consensus_engine.py)

**Test-/Dokumentziele:** [tests/test_claim_identity_judge.py](../../../tests/test_claim_identity_judge.py), [tests/test_maintenance_scripts.py](../../../tests/test_maintenance_scripts.py)

**Vorhandene Hilfen:** [tests/test_consensus_engine.py](../../../tests/test_consensus_engine.py), [tests/test_topics_feature.py](../../../tests/test_topics_feature.py)

**Befehle/Prüfauftrag nach Implementierung:**

- ` python -m pytest tests/test_claim_identity_judge.py tests/test_topics_feature.py tests/test_claim_ledger.py -q `

**Zu beachten:** [D-06](decisions.md#d-06)

**Implementierungsnachweis:** ` d3500c0c ` · [docs/test-coverage/product/implementation-adapters.md](implementation-adapters.md) · [docs/test-coverage/execution.json](../execution.json)

**Ausgeführte Testbereiche:** [tests/test_claim_identity_judge.py](../../../tests/test_claim_identity_judge.py), [tests/test_maintenance_scripts.py](../../../tests/test_maintenance_scripts.py)

**Beobachtete Negativkontrolle:** Key-/Eindeutigkeitsguard entfernt: unerlaubte Zuordnung erkannt.

**Verbleibende Grenze:** Synthetische Modellantworten; neue Integerpräzisierung in D06/Implementierungsbericht dokumentiert.


<a id="wp-18"></a>

## WP-18 · SEO-Repositoryadapter ausführen

**Ziel:** SDK-Rückgabeformen hinter vorhandenen Service-Fakes.

**Befunde:** [G-017](gaps.md#g-017) · **Vorher:** —

**Stand:** completed. BatchGet ordnet anhand Dokumentidentität zu, begrenzt 615 Referenzen auf400/215; fehlende Snapshots/Messungen, Datumsformen und neueste Queries mit echten SDK-Fällen.

**Vorgehen:** Ungeordnete/missing BatchGet-Snapshots und Grenzgrößen, Datumsmischung und Latest-/Judgmentqueries prüfen; kleiner Emulatorfall für reale Queryform.

**Abnahme zusätzlich zu den verknüpften Then-/Negativkontrollen:** Zuordnung über Dokumentidentität, bounded Reads und korrekt neueste Daten; fehlende Daten werden nicht als gemessener Nulltraffic ausgegeben.

**Produktstellen:** [app/services/seo_repository.py](../../../app/services/seo_repository.py)

**Test-/Dokumentziele:** [tests/e2e/test_seo_repository_queries.py](../../../tests/e2e/test_seo_repository_queries.py), [tests/test_seo_repository.py](../../../tests/test_seo_repository.py)

**Vorhandene Hilfen:** [tests/test_seo_data.py](../../../tests/test_seo_data.py), [tests/test_seo_weekly_review.py](../../../tests/test_seo_weekly_review.py)

**Befehle/Prüfauftrag nach Implementierung:**

- ` python -m pytest tests/test_seo_repository.py tests/test_seo_data.py tests/test_seo_weekly_review.py -q `

**Zu beachten:** —

**Implementierungsnachweis:** ` c723e42b ` · [docs/test-coverage/product/implementation-adapters.md](implementation-adapters.md) · [docs/test-coverage/execution.json](../execution.json)

**Ausgeführte Testbereiche:** [tests/test_seo_repository.py](../../../tests/test_seo_repository.py), [tests/e2e/test_seo_repository_queries.py](../../../tests/e2e/test_seo_repository_queries.py)

**Beobachtete Negativkontrolle:** Payload-page_id bevorzugt: falsche Zuordnung erkannt.

**Verbleibende Grenze:** Lokaler Emulator mit anonymen Credentials; kein Produktkonto, keine produktive IAM-/Lastgarantie. Nur eigene Dokumentwurzeln werden aufgeräumt.


<a id="wp-19"></a>

## WP-19 · Schedulerqueries und persistente Claims prüfen

**Ziel:** Watch-, Topic- und SEO-Slots über echte SDK-Grenzen.

**Befunde:** [G-031](gaps.md#g-031) · **Vorher:** [WP-01](work-packages.md#wp-01)

**Stand:** completed. Native Duequeries/Claims/Budget/Stale-Fences plus wirkliche Topic-/SEOloops: Erfolgs- und Fehlerabschluss, gespeicherter Benachrichtigungsstatus, Leasefreigabe und Cancellation ohne nächsten Dispatch.

**Vorgehen:** Einzelnen Tick mit kontrollierter Uhr/Pipeline ausführen, native Claimkonkurrenz und Shutdown. Vorhandene DST-/Supervisortests wiederverwenden.

**Abnahme zusätzlich zu den verknüpften Then-/Negativkontrollen:** Nur fällige Daten, ein Gewinner, keine stale Completion und kein weiterer Tick nach Shutdown; reale Query-/Leaseform statt nur Fakefilter.

**Produktstellen:** [app/services/seo_weekly_review.py](../../../app/services/seo_weekly_review.py), [app/services/topics.py](../../../app/services/topics.py), [app/services/watch_service.py](../../../app/services/watch_service.py)

**Test-/Dokumentziele:** [tests/e2e/test_scheduler_transactions.py](../../../tests/e2e/test_scheduler_transactions.py), [tests/test_background_task_supervision.py](../../../tests/test_background_task_supervision.py)

**Vorhandene Hilfen:** [tests/test_seo_weekly_review.py](../../../tests/test_seo_weekly_review.py), [tests/test_topics_feature.py](../../../tests/test_topics_feature.py), [tests/test_watch_feature.py](../../../tests/test_watch_feature.py)

**Befehle/Prüfauftrag nach Implementierung:**

- ` RUN_E2E=1 python -m pytest tests/e2e/test_scheduler_transactions.py -q; python -m pytest tests/test_background_task_supervision.py -q `

**Zu beachten:** [D-03](decisions.md#d-03)

**Implementierungsnachweis:** ` a19134b0 ` · [docs/test-coverage/product/implementation-persistence.md](implementation-persistence.md) · [docs/test-coverage/execution.json](../execution.json)

**Ausgeführte Testbereiche:** [tests/e2e/test_scheduler_transactions.py](../../../tests/e2e/test_scheduler_transactions.py), [tests/test_background_task_supervision.py](../../../tests/test_background_task_supervision.py)

**Beobachtete Negativkontrolle:** SEO-Ownerguard entfernt: Nachfolgerzustand wird überschrieben.

**Verbleibende Grenze:** Erneuter Scheduler-Tick nach Infrastrukturfehler kann erforderlich sein.


<a id="wp-20"></a>

## WP-20 · Topic-Notizen als Text absichern

**Ziel:** Reproduzierten Text→HTML-Fehler zunächst rot festhalten.

**Befunde:** [G-018](gaps.md#g-018) · **Vorher:** —

**Stand:** completed. Originales Topicskript hält Notizen inert und Sonderzeichen lesbar; Focus/Enter, Touchpreview/Navigation, Seenmarker, historische Ansicht und blockierter Storage ausgeführt.

**Vorgehen:** DOM-Test mit inertem Markup und Interaktionen; gezielten Browserfall für Touch/Focus/Navigation ergänzen. Textknoten und konstante UI-Struktur getrennt aufbauen.

**Abnahme zusätzlich zu den verknüpften Then-/Negativkontrollen:** D-01 erzeugt kein Element mehr aus Nutztext; Sonderzeichen bleiben lesbar. Unseen-/historischer Besuch und blockierter Storage funktionieren. Frontendbuild/öffentlichen Cachebuster nach Repo-Regel pflegen.

**Produktstellen:** [app/services/claim_ledger.py](../../../app/services/claim_ledger.py), [static/js/topic-page.js](../../../static/js/topic-page.js), [templates/topic.html](../../../templates/topic.html)

**Test-/Dokumentziele:** [tests/e2e/test_topic_frontend.py](../../../tests/e2e/test_topic_frontend.py), [tests/js/topic-page.test.mjs](../../../tests/js/topic-page.test.mjs)

**Vorhandene Hilfen:** [tests/js/helpers/appWindow.mjs](../../../tests/js/helpers/appWindow.mjs), [tests/test_claim_ledger.py](../../../tests/test_claim_ledger.py)

**Befehle/Prüfauftrag nach Implementierung:**

- ` npm test -- tests/js/topic-page.test.mjs; ergänzend gezielter Topic-Browserfall `

**Zu beachten:** —

**Implementierungsnachweis:** ` 0cd497d9 ` · [docs/test-coverage/product/implementation-browser.md](implementation-browser.md) · [docs/test-coverage/execution.json](../execution.json)

**Ausgeführte Testbereiche:** [tests/e2e/test_topic_frontend.py](../../../tests/e2e/test_topic_frontend.py), [tests/js/topic-page.test.mjs](../../../tests/js/topic-page.test.mjs)

**Beobachtete Negativkontrolle:** Feindlicher Text erzeugt kein Element/Handler; erster Touch navigiert nicht, historischer Besuch schreibt keinen Seenmarker.

**Verbleibende Grenze:** Kontrollierte SSRfixture, kein vollständiger visueller Seitenaudit.


<a id="wp-21"></a>

## WP-21 · Adminfehler aus dem echten Appumschlag anzeigen

**Ziel:** Fehlerobjekte dürfen nicht als [object Object] erscheinen.

**Befunde:** [G-019](gaps.md#g-019) · **Vorher:** —

**Stand:** completed. Echter main-error-Umschlag ist serverseitig belegt und wird vom tatsächlichen Adminclient lesbar projiziert; unbekannte Objekte fallen sicher zurück,409 behält Draft ohne Retry.

**Vorgehen:** createAdminClient mit tatsächlichen error-/detail-Objekten, Strings, Listen und nicht-JSON testen; AccountTier-HTTP-Response als Vertragsfixture nutzen.

**Abnahme zusätzlich zu den verknüpften Then-/Negativkontrollen:** D-02 main-handler-Fall zeigt erlaubte Nachricht/Fallback; kein zweiter Write; Konfliktdraft bleibt erhalten. Frontendbuild/Cachebuster nach Repo-Regel pflegen.

**Produktstellen:** [app/api/routers/admin.py](../../../app/api/routers/admin.py), [main.py](../../../main.py), [static/js/admin-api.js](../../../static/js/admin-api.js)

**Test-/Dokumentziele:** [tests/js/admin-api.test.mjs](../../../tests/js/admin-api.test.mjs), [tests/js/admin-prompt-config.test.mjs](../../../tests/js/admin-prompt-config.test.mjs), [tests/test_account_tier_admin.py](../../../tests/test_account_tier_admin.py)

**Vorhandene Hilfen:** [tests/e2e/test_admin_prompt_config.py](../../../tests/e2e/test_admin_prompt_config.py), [tests/js/admin-prompt-config.test.mjs](../../../tests/js/admin-prompt-config.test.mjs)

**Befehle/Prüfauftrag nach Implementierung:**

- ` npm test -- tests/js/admin-api.test.mjs tests/js/admin-prompt-config.test.mjs; python -m pytest tests/test_account_tier_admin.py -q `

**Zu beachten:** —

**Implementierungsnachweis:** ` 0cd497d9 ` · [docs/test-coverage/product/implementation-browser.md](implementation-browser.md) · [docs/test-coverage/execution.json](../execution.json)

**Ausgeführte Testbereiche:** [tests/js/admin-api.test.mjs](../../../tests/js/admin-api.test.mjs), [tests/js/admin-prompt-config.test.mjs](../../../tests/js/admin-prompt-config.test.mjs), [tests/test_account_tier_admin.py](../../../tests/test_account_tier_admin.py)

**Beobachtete Negativkontrolle:** Alte Adminclientquelle gegen neuen Test erzeugt Fehler; Writezähler bleibt1.

**Verbleibende Grenze:** Fetch/Auth kontrolliert, keine gemeinsame Firestore-/Browsertransaktion.


<a id="wp-22"></a>

## WP-22 · Benchmark-Adminadapter und Viewer prüfen

**Ziel:** Vom kompakten Report bis zum echten Auswahl-/Fehlerzustand.

**Befunde:** [G-015](gaps.md#g-015) · **Vorher:** —

**Stand:** completed. Echter Adminrollen-/Reportadapter plus dynamischer Viewer: kompakte Daten, keine Rohprompts, passende Run-ID, stale Antwort/Fehler ignoriert und alte Daten bei Auswahlfehler entfernt.

**Vorgehen:** Admin-Listen/Detailroute mit Auth, danach Viewer mit kontrolliert verspäteten Antworten. Kein Rohreport mit Prompts/Antworten als Fixture im Adminvertrag.

**Abnahme zusätzlich zu den verknüpften Then-/Negativkontrollen:** Nonadmin vor Read abgelehnt; 404, falsche IDs und Auswahlwechsel korrekt; keine Staledaten oder Rohprompts.

**Produktstellen:** [app/api/routers/admin.py](../../../app/api/routers/admin.py), [static/js/admin-benchmark.js](../../../static/js/admin-benchmark.js)

**Test-/Dokumentziele:** [tests/js/admin-benchmark.test.mjs](../../../tests/js/admin-benchmark.test.mjs), [tests/test_benchmark_reports.py](../../../tests/test_benchmark_reports.py), [tests/test_http_adapter_auth.py](../../../tests/test_http_adapter_auth.py)

**Vorhandene Hilfen:** [tests/js/helpers/appWindow.mjs](../../../tests/js/helpers/appWindow.mjs), [tests/test_benchmark_report_reader.py](../../../tests/test_benchmark_report_reader.py), [tests/test_benchmark_reports.py](../../../tests/test_benchmark_reports.py)

**Befehle/Prüfauftrag nach Implementierung:**

- ` python -m pytest tests/test_benchmark_reports.py tests/test_benchmark_report_reader.py -q; npm test -- tests/js/admin-benchmark.test.mjs `

**Zu beachten:** —

**Implementierungsnachweis:** ` 0cd497d9 ` · [docs/test-coverage/product/implementation-browser.md](implementation-browser.md) · [docs/test-coverage/execution.json](../execution.json)

**Ausgeführte Testbereiche:** [tests/test_http_adapter_auth.py](../../../tests/test_http_adapter_auth.py), [tests/js/admin-benchmark.test.mjs](../../../tests/js/admin-benchmark.test.mjs)

**Beobachtete Negativkontrolle:** Adminguard entfernt: unerlaubter Read; alte Viewerquelle: Race-/Staleassertionen schlagen fehl.

**Verbleibende Grenze:** Reportdateien/Netzwerk lokal kontrolliert, kein Livebenchmark.


<a id="wp-23"></a>

## WP-23 · Inhalt der OG-Karte wirksam prüfen

**Ziel:** Gültige PNG-Bytes reichen als Inhaltstest nicht aus.

**Befunde:** [G-020](gaps.md#g-020) · **Vorher:** —

**Stand:** completed. Echtes PNG mit gezeichneten Bildregionen, Fragepixel, Score/Modelle/Konflikte/unscored und privater Route. Cache berücksichtigt alle sichtbaren Inhalte und Renderfehlerretry.

**Vorgehen:** Realen Renderer mit deterministischen Fonts/Inputs prüfen; Dekodierung, stabile Bildregionen und semantische Renderinputs kombinieren. Route muss richtige Inputs liefern.

**Abnahme zusätzlich zu den verknüpften Then-/Negativkontrollen:** M-02 wird von neuem Test entdeckt; Frage/Kennzahlen/unscored und private Seiten geprüft. Kein pixelgenauer plattformabhängiger Hash.

**Produktstellen:** [app/api/routers/share.py](../../../app/api/routers/share.py), [app/services/og_image.py](../../../app/services/og_image.py)

**Test-/Dokumentziele:** [tests/test_og_image.py](../../../tests/test_og_image.py), [tests/test_share_feature.py](../../../tests/test_share_feature.py), [tests/test_share_http_contract.py](../../../tests/test_share_http_contract.py)

**Vorhandene Hilfen:** [tests/test_share_feature.py](../../../tests/test_share_feature.py)

**Befehle/Prüfauftrag nach Implementierung:**

- ` python -m pytest tests/test_og_image.py tests/test_share_feature.py -q `

**Zu beachten:** [D-06](decisions.md#d-06)

**Implementierungsnachweis:** ` c723e42b ` · [docs/test-coverage/product/implementation-adapters.md](implementation-adapters.md) · [docs/test-coverage/execution.json](../execution.json)

**Ausgeführte Testbereiche:** [tests/test_og_image.py](../../../tests/test_og_image.py), [tests/test_share_http_contract.py](../../../tests/test_share_http_contract.py)

**Beobachtete Negativkontrolle:** Gültiges weißes PNG statt Renderer: Inhaltsassertionen werden rot.

**Verbleibende Grenze:** Keine pixelgenauen Hashes, keine neue historische OG-Versionsauswahl.


<a id="wp-24"></a>

## WP-24 · Analytics-Opt-out dynamisch prüfen

**Ziel:** Query-/Storageverhalten vor dem Trackerstart.

**Befunde:** [G-021](gaps.md#g-021) · **Vorher:** —

**Stand:** completed. Originales Skript läuft vor instrumentiertem Seitenstart für1/0/fehlend/leer/anders und Storagefehler. Vorhandener Wert bleibt bei anderen Parametern erhalten.

**Vorgehen:** Originalskript in frischem jsdom ausführen, Trackerstart instrumentieren und Storageausfälle injizieren.

**Abnahme zusätzlich zu den verknüpften Then-/Negativkontrollen:** 1/0/fehlend/sonstige Parameter sowie setItem-/removeItem-Fehler führen zum erwarteten Flag/Seitenstart; fehlender/anderer Parameter erhält den vorhandenen Wert. Keine getItem-Verzweigung erfinden; reine Stringpräsenz genügt nicht.

**Produktstellen:** [static/js/analytics-opt-out.js](../../../static/js/analytics-opt-out.js)

**Test-/Dokumentziele:** [tests/js/analytics-opt-out.test.mjs](../../../tests/js/analytics-opt-out.test.mjs)

**Vorhandene Hilfen:** [tests/js/helpers/appWindow.mjs](../../../tests/js/helpers/appWindow.mjs), [tests/test_analytics_partial.py](../../../tests/test_analytics_partial.py)

**Befehle/Prüfauftrag nach Implementierung:**

- ` npm test -- tests/js/analytics-opt-out.test.mjs; python -m pytest tests/test_analytics_partial.py -q `

**Zu beachten:** —

**Implementierungsnachweis:** ` 0cd497d9 ` · [docs/test-coverage/product/implementation-browser.md](implementation-browser.md) · [docs/test-coverage/execution.json](../execution.json)

**Ausgeführte Testbereiche:** [tests/js/analytics-opt-out.test.mjs](../../../tests/js/analytics-opt-out.test.mjs)

**Beobachtete Negativkontrolle:** Unzulässige Storageoperation würde exakte Aufruf-/Flagausgabe verändern; Fehler darf Seitenstart nicht stoppen.

**Verbleibende Grenze:** Kein echter Tracker oder Analyticseventversand.


<a id="wp-25"></a>

## WP-25 · Wartungsskripte isoliert absichern

**Ziel:** Projekt-/Apply-/Dry-run-Grenzen ohne Produktzugriff.

**Befunde:** [G-022](gaps.md#g-022), [G-023](gaps.md#g-023) · **Vorher:** —

**Stand:** completed. Wartungseinstiege in netzwerkgesperrten Subprozessen, Account-/Apply-/Projektguards, Dry-run und wiederholbarer Backfill. Bestehende Claimkeys werden reserviert; Fallbackkollisionen verhindert.

**Vorgehen:** Subprozesse mit synthetischen Modulen/DB/Provider und explizitem Netzwerkverbot. Reparatur-Projektguard nicht für Tests deaktivieren; Fakeumgebung muss kontrollierten Vertrag abbilden.

**Abnahme zusätzlich zu den verknüpften Then-/Negativkontrollen:** Inspect/dry-run schreiben nicht; Apply nur gewählten Account/Keys, Idempotenz und Datenerhalt. Dry-run-Kosten des Backfills klar dokumentiert.

**Produktstellen:** [scripts/backfill_claim_keys.py](../../../scripts/backfill_claim_keys.py), [scripts/repair_agent_allowance.py](../../../scripts/repair_agent_allowance.py)

**Test-/Dokumentziele:** ` tests/test_backfill_claim_keys.py ` (vorgeschlagen), [tests/test_maintenance_scripts.py](../../../tests/test_maintenance_scripts.py), ` tests/test_repair_agent_allowance_script.py ` (vorgeschlagen)

**Vorhandene Hilfen:** [tests/test_agent_quota_recovery.py](../../../tests/test_agent_quota_recovery.py), [tests/test_claim_ledger.py](../../../tests/test_claim_ledger.py), [tests/test_publisher_standalone.py](../../../tests/test_publisher_standalone.py), [tests/test_topics_feature.py](../../../tests/test_topics_feature.py)

**Befehle/Prüfauftrag nach Implementierung:**

- ` python -m pytest tests/test_repair_agent_allowance_script.py tests/test_agent_quota_recovery.py -q `
- ` python -m pytest tests/test_backfill_claim_keys.py tests/test_claim_ledger.py -q `

**Zu beachten:** [D-07](decisions.md#d-07)

**Implementierungsnachweis:** ` d3500c0c ` · [docs/test-coverage/product/implementation-runtime.md](implementation-runtime.md) · [docs/test-coverage/execution.json](../execution.json)

**Ausgeführte Testbereiche:** [tests/test_maintenance_scripts.py](../../../tests/test_maintenance_scripts.py)

**Beobachtete Negativkontrolle:** Entfernte Applyguard bewirkt unerlaubten Recoveryaufruf; rote Regressionen für Keyverlust, Vorschauzählung und Kollision.

**Verbleibende Grenze:** Backfill-Dry-run kann in echter Umgebung einen Judgeaufruf kosten; Tests ersetzen ihn.


<a id="wp-26"></a>

## WP-26 · HTTP-Body- und lokale Transportgrenzen ergänzen

**Ziel:** ASGI-Randfälle und wirkliche Socket-Lebenszyklen.

**Befunde:** [G-032](gaps.md#g-032), [G-033](gaps.md#g-033) · **Vorher:** —

**Stand:** completed. Bodylimit und vorzeitiger Disconnect, reale TCP-/TLS-Sockets mit Abbruch/Deadline, Host/SNI, Redirectvalidierung und gzip-Budget belegt.

**Vorgehen:** Header/Env-Grenzen im vorhandenen ASGI-Harness; lokaler HTTP/TLS-Server für Stream/Cancel/Close/gzip. Testziel explizit einspeisen; SSRF-Policy separat real prüfen, keine Produktionsallowlist erweitern.

**Abnahme zusätzlich zu den verknüpften Then-/Negativkontrollen:** Kein Leak/zweiter Retry/unbegrenztes Lesen; Host/SNI/Redirect-Neuvalidierung belegt. Fehlerstatus bewusst gewählt, keine Internetabhängigkeit.

**Produktstellen:** [app/core/request_limits.py](../../../app/core/request_limits.py), [app/services/llm/provider_runtime.py](../../../app/services/llm/provider_runtime.py), [app/services/source_documents.py](../../../app/services/source_documents.py)

**Test-/Dokumentziele:** [tests/test_local_transport.py](../../../tests/test_local_transport.py), ` tests/test_provider_local_transport.py ` (vorgeschlagen), [tests/test_request_body_limits.py](../../../tests/test_request_body_limits.py), ` tests/test_source_documents_local_transport.py ` (vorgeschlagen)

**Vorhandene Hilfen:** [tests/test_provider_timeouts.py](../../../tests/test_provider_timeouts.py), [tests/test_request_body_limits.py](../../../tests/test_request_body_limits.py), [tests/test_source_verification.py](../../../tests/test_source_verification.py)

**Befehle/Prüfauftrag nach Implementierung:**

- ` python -m pytest tests/test_provider_local_transport.py tests/test_source_documents_local_transport.py -q `
- ` python -m pytest tests/test_request_body_limits.py -q `

**Zu beachten:** [D-06](decisions.md#d-06)

**Implementierungsnachweis:** ` bad07367 ` · [docs/test-coverage/product/implementation-runtime.md](implementation-runtime.md) · [docs/test-coverage/execution.json](../execution.json)

**Ausgeführte Testbereiche:** [tests/test_local_transport.py](../../../tests/test_local_transport.py), [tests/test_request_body_limits.py](../../../tests/test_request_body_limits.py)

**Beobachtete Negativkontrolle:** Aktivierte SDK-Retries führen nachweislich zu zwei Requests; Disconnect-Regression vor Fix rot.

**Verbleibende Grenze:** Lokale Server, keine Deploymentproxy-/Internetmessung.


<a id="wp-27"></a>

## WP-27 · Feedback und Statistikwrites verbinden

**Ziel:** Echte Router-/Persistenzwrapper hinter vorhandenen Guardtests.

**Befunde:** [G-034](gaps.md#g-034) · **Vorher:** —

**Stand:** completed. Feedbackhandler/Persistenzguard prüft Auth, Allowlist, Cooldown, Tageslimit und Storefehler. Statistik speichert nur erlaubte Zähler/Metadaten, Fehler bleiben nichtfatal.

**Vorgehen:** Auth, Tages-/Cooldown-Limits und Storefehler durch realen Handler; Statistikwrapper mit inhaltshaltigen Eingaben ausführen und gespeicherte Felder prüfen.

**Abnahme zusätzlich zu den verknüpften Then-/Negativkontrollen:** UID vor Write geprüft, Limits unverändert, Statistik ohne Prompt/Antwort/IDs. Feedback selbst darf die bewusst eingegebene Nachricht enthalten.

**Produktstellen:** [app/api/routers/pages.py](../../../app/api/routers/pages.py), [app/services/differences_stats.py](../../../app/services/differences_stats.py)

**Test-/Dokumentziele:** [tests/test_differences_stats.py](../../../tests/test_differences_stats.py), [tests/test_feedback.py](../../../tests/test_feedback.py)

**Vorhandene Hilfen:** [tests/test_differences_stats.py](../../../tests/test_differences_stats.py), [tests/test_phase5_operations.py](../../../tests/test_phase5_operations.py)

**Befehle/Prüfauftrag nach Implementierung:**

- ` python -m pytest tests/test_feedback.py tests/test_differences_stats.py -q `

**Zu beachten:** —

**Implementierungsnachweis:** ` c723e42b ` · [docs/test-coverage/product/implementation-adapters.md](implementation-adapters.md) · [docs/test-coverage/execution.json](../execution.json)

**Ausgeführte Testbereiche:** [tests/test_feedback.py](../../../tests/test_feedback.py)

**Beobachtete Negativkontrolle:** Unbearbeitete Statistikinputs schreiben: private Inhalts-/ID-Marker werden erkannt.

**Verbleibende Grenze:** Bewusst eingegebene Feedbacknachricht darf gespeichert werden; keine produktiven Accounts.


<a id="wp-28"></a>

## WP-28 · Unterstützte Hilfs-CLIs prüfen

**Ziel:** Alternative Benchmark-/Evaluations-/Preview-Einstiege.

**Befunde:** [G-035](gaps.md#g-035) · **Vorher:** —

**Stand:** completed. Unterstützte sample/experiment-Einstiege validieren Scope/Budget vor Arbeit und durchlaufen echte Runner-/Manifest-/Record-/Resume-/Resultpfade.

**Vorgehen:** Aktuelle Supportentscheidung je Einstieg festhalten; unterstützte CLIs per Subprozess mit temporären Outputs und Fakeprovider prüfen. Veraltete Modi nicht als neue Produktanforderung behandeln.

**Abnahme zusätzlich zu den verknüpften Then-/Negativkontrollen:** Argumente, Exitcodes, Budget/Scope und Outputgrenzen pro unterstütztem Einstieg belegt; Live-Modellqualität ausdrücklich separat.

**Produktstellen:** [benchmark/run_experiment.py](../../../benchmark/run_experiment.py), [benchmark/run_sample.py](../../../benchmark/run_sample.py)

**Test-/Dokumentziele:** [tests/test_auxiliary_cli.py](../../../tests/test_auxiliary_cli.py)

**Vorhandene Hilfen:** [tests/test_benchmark_cli.py](../../../tests/test_benchmark_cli.py), [tests/test_publisher_standalone.py](../../../tests/test_publisher_standalone.py)

**Befehle/Prüfauftrag nach Implementierung:**

- ` python -m pytest tests/test_auxiliary_cli.py -q `

**Zu beachten:** [D-04](decisions.md#d-04), [D-07](decisions.md#d-07)

**Implementierungsnachweis:** ` bad07367 ` · [docs/test-coverage/product/implementation-runtime.md](implementation-runtime.md) · [docs/test-coverage/execution.json](../execution.json)

**Ausgeführte Testbereiche:** [tests/test_auxiliary_cli.py](../../../tests/test_auxiliary_cli.py)

**Beobachtete Negativkontrolle:** Entfernte endliche Budgetvalidierung startet unerlaubte synthetische Providerarbeit.

**Verbleibende Grenze:** Keine bezahlten Modelle, keine Livequalitätsmessung.


<a id="wp-29"></a>

## WP-29 · Persistierte Nutzerreisen durch alle internen Schichten prüfen

**Ziel:** Wenige gezielte Integrationsfälle schließen die Mocklücken.

**Befunde:** [G-030](gaps.md#g-030) · **Vorher:** [WP-03](work-packages.md#wp-03), [WP-07](work-packages.md#wp-07), [WP-08](work-packages.md#wp-08), [WP-09](work-packages.md#wp-09), [WP-10](work-packages.md#wp-10), [WP-12](work-packages.md#wp-12), [WP-13](work-packages.md#wp-13), [WP-14](work-packages.md#wp-14)

**Stand:** completed. Sechs Chromiumreisen verbinden originales gebautes AppFirebase, echte HTTP-/Serviceguards und nativen Speicher für J01–J05 sowie echten Bookmark-Speicherfehler. J03 führt den echten Own-Key-Worker aus; J05 prüft Daten erst nach beobachtetem Producer-/Settlementabschluss. Identitäten, Context/Turns, Messbuchungen, Stop/Recover und Kontowechsel werden anhand gespeicherter Daten geprüft. Alle sechs Reisen bestanden auch im vollständigen integrierten CI-Lauf mit 368 Fällen.

**Vorgehen:** J-01/J-02 zuerst, dann J-03/J-04/J-05 gemäß journeys.md. Echtes AppFirebase, App-Routen und lokales Firestore; nur Identitäts-/Provider-/Nachrichtengrenzen ersetzen.

**Abnahme zusätzlich zu den verknüpften Then-/Negativkontrollen:** UI und DB stimmen nach Reload/Ownerwechsel/Stop überein, kein zweiter Modellstart beim Recover, keine vermischten Turns/Charges. Bestehende Modul-/Browsertests bleiben schnelle Detailnachweise. Antworterfolg und Persistenzstatus getrennt prüfen. Einmalige reguläre Runbelastung von der Agent-Abrechnung tatsächlicher Providersteps unterscheiden; Recovery darf keine Buchung duplizieren.

**Produktstellen:** [tests/e2e/conftest.py](../../../tests/e2e/conftest.py), [tests/e2e/test_phase4_frontend.py](../../../tests/e2e/test_phase4_frontend.py)

**Test-/Dokumentziele:** [tests/e2e/test_persisted_journeys.py](../../../tests/e2e/test_persisted_journeys.py), ` tests/e2e/test_persisted_user_journeys.py ` (vorgeschlagen), [tests/js/bookmark-pending-state.test.mjs](../../../tests/js/bookmark-pending-state.test.mjs)

**Vorhandene Hilfen:** [tests/e2e/conftest.py](../../../tests/e2e/conftest.py), [tests/e2e/test_phase4_frontend.py](../../../tests/e2e/test_phase4_frontend.py), [tests/test_consensus_chat_history.py](../../../tests/test_consensus_chat_history.py)

**Befehle/Prüfauftrag nach Implementierung:**

- ` RUN_E2E=1 python -m pytest tests/e2e/test_persisted_user_journeys.py -q (Demo-Emulator) `

**Zu beachten:** [D-02](decisions.md#d-02)

**Implementierungsnachweis:** ` ffaca3df ` · [docs/test-coverage/product/implementation-browser.md](implementation-browser.md) · [docs/test-coverage/execution.json](../execution.json)

**Ausgeführte Testbereiche:** [tests/e2e/test_persisted_journeys.py](../../../tests/e2e/test_persisted_journeys.py), [tests/js/bookmark-pending-state.test.mjs](../../../tests/js/bookmark-pending-state.test.mjs)

**Beobachtete Negativkontrolle:** Fremdowner/Revisionskonflikt, neun stale Packagecommits ohne Revisionsänderung, Fremdworker ohne Claim, kein zweiter Modellstart/Buchung beim Recover, tatsächlicher Speicherquotafehler ohne erfundenen Savedstatus; Bookmarkmetadatenregression vor Fix rot.

**Verbleibende Grenze:** Externe Identität/Modelle/Mail kontrolliert; historischer V3-Import und gezielt getriebener ownergebundener Watchpfad sind ausdrücklich gekennzeichnet. J05 beobachtet echte Responsebeendigung und Leasefreigabe vor dem nativen Late-Write-Oracle.


<a id="wp-30"></a>

## WP-30 · Vendorhelper mit echtem temporärem Dateisystem prüfen

**Ziel:** Versionpins, Font-/Lizenzumfang und checkOnly.

**Befunde:** [G-036](gaps.md#g-036) · **Vorher:** —

**Stand:** completed. vendorFrontend auf echtem temporärem Dateisystem, Pins/Lizenzen/Fontbytes/Sortierung, stale Assets, Check-only und unveränderte Mtime belegt.

**Vorgehen:** Winzige synthetische Pakete statt realer Paketdownloads verwenden; helper direkt aufrufen, alte Assets und Mtime kontrollieren.

**Abnahme zusätzlich zu den verknüpften Then-/Negativkontrollen:** Versionabweichung und stale/fehlende Bytes erkannt, Check-only ohne Writes, unveränderte Inputs ohne Rewrite; bestehende Artefakt-/Buildtests bleiben grün.

**Produktstellen:** [scripts/vendor_frontend.mjs](../../../scripts/vendor_frontend.mjs)

**Test-/Dokumentziele:** [tests/js/vendor-frontend.test.mjs](../../../tests/js/vendor-frontend.test.mjs)

**Vorhandene Hilfen:** [tests/js/frontend-output.test.mjs](../../../tests/js/frontend-output.test.mjs), [tests/test_frontend_build.py](../../../tests/test_frontend_build.py)

**Befehle/Prüfauftrag nach Implementierung:**

- ` npm test -- tests/js/vendor-frontend.test.mjs tests/js/frontend-output.test.mjs; python -m pytest tests/test_frontend_build.py -q `

**Zu beachten:** —

**Implementierungsnachweis:** ` 0cd497d9 ` · [docs/test-coverage/product/implementation-browser.md](implementation-browser.md) · [docs/test-coverage/execution.json](../execution.json)

**Ausgeführte Testbereiche:** [tests/js/vendor-frontend.test.mjs](../../../tests/js/vendor-frontend.test.mjs)

**Beobachtete Negativkontrolle:** Abweichender Pin oder stale/fehlende Bytes müssen erkannt werden; Check-onlybytes bleiben identisch.

**Verbleibende Grenze:** Synthetische Pakete, kein Download oder Bibliotheksqualitätsbeweis.


<a id="wp-31"></a>

## WP-31 · HTTPException-Header durch main bewahren

**Ziel:** Fehlerstatus, Body und Retry-After als zusammenhängender HTTP-Vertrag.

**Befunde:** [G-037](gaps.md#g-037) · **Vorher:** —

**Stand:** completed. Reale Agent503/API429 gehen durch main mit sicherem Body und serverseitigem Retry-After, ohne unerlaubte Arbeit; Requestheader werden nicht reflektiert.

**Vorgehen:** Zuerst P-01 als roten Integrationstest an echten Routen konkretisieren; gemeinsame Fehlerbehandlung korrigieren und bestehende isolierte Routerkontrollen behalten.

**Abnahme zusätzlich zu den verknüpften Then-/Negativkontrollen:** 429/503, sichere Fehlermeldung und vorgesehenes Retry-After bleiben gemeinsam erhalten; Ablehnung startet weder Provider noch unerlaubten Write. Vorgesehene Exceptionheader werden bewahrt, keine frei vom Request kopierten Header. headers-Weitergabe im main-Handler entfernen: neue main.app-Headerassertion muss scheitern, obwohl die bestehenden isolierten Routertests grün bleiben.

**Produktstellen:** [main.py](../../../main.py), [app/api/routers/api_v1.py](../../../app/api/routers/api_v1.py), [app/api/routers/agent.py](../../../app/api/routers/agent.py)

**Test-/Dokumentziele:** [tests/test_agent_capacity.py](../../../tests/test_agent_capacity.py), [tests/test_agent_http_contract.py](../../../tests/test_agent_http_contract.py), [tests/test_agent_search.py](../../../tests/test_agent_search.py), [tests/test_consensus_api.py](../../../tests/test_consensus_api.py)

**Vorhandene Hilfen:** [tests/test_consensus_api.py](../../../tests/test_consensus_api.py), [tests/test_agent_capacity.py](../../../tests/test_agent_capacity.py)

**Befehle/Prüfauftrag nach Implementierung:**

- ` python -m pytest tests/test_consensus_api.py tests/test_agent_capacity.py tests/test_agent_search.py -q `

**Zu beachten:** —

**Implementierungsnachweis:** ` c723e42b ` · [docs/test-coverage/product/implementation-adapters.md](implementation-adapters.md) · [docs/test-coverage/execution.json](../execution.json)

**Ausgeführte Testbereiche:** [tests/test_agent_http_contract.py](../../../tests/test_agent_http_contract.py)

**Beobachtete Negativkontrolle:** Exceptionheader im main-Handler verworfen: Retry-After60-Assertion schlägt fehl.

**Verbleibende Grenze:** Firebase-SDK-Authentifizierung und DB ersetzt; externe Modell-, Mail- und Telegramgrenzen kontrolliert. Kein Live-OAuth oder produktiver Versand.


<a id="wp-32"></a>

## WP-32 · Agentdetail und Turn-Stop durch HTTP absichern

**Ziel:** Servicebelege bis zur tatsächlichen HTTP-Grenze erweitern.

**Befunde:** [G-039](gaps.md#g-039) · **Vorher:** —

**Stand:** completed. Agentdetail/Stop binden UID, Chat und Turn, paginieren vollständig und prüfen Parameter/Pro-/Admin-/Tierausfall. Wiederholter Stop sperrt nur Zielturn und späten Publish; Antworten private/no-store.

**Vorgehen:** Vorhandene echte Stores/Fakes wiederverwenden; main.app, echte Auth-/Tierpolicy mit externen SDK-Doubles, keine pauschale _agent_details- oder require_agent_access-Ersetzung.

**Abnahme zusätzlich zu den verknüpften Then-/Negativkontrollen:** IDs und UID binden exakt dieselbe Ressource; fremde Daten bleiben verborgen. Pagination hat weder Lücken noch unbeschränkte Antwort; after<0, limit=0/51 werden abgewiesen. Stop wirkt nur auf den gebundenen Turn, ist bei Wiederholung sicher und beendet den Konsens nicht ungewollt. Tier-/Adminregel folgt require_agent_access; private Antwort no-store, kein bezahlter Call durch Detail/Stop. UID oder turn_id beim Store-Aufruf vertauschen beziehungsweise Stop weglassen: Ownership-/Zustandsassertionen müssen scheitern; ein reiner 422-Test genügt nicht.

**Produktstellen:** [app/api/routers/agent.py](../../../app/api/routers/agent.py), [app/services/agent_sessions.py](../../../app/services/agent_sessions.py)

**Test-/Dokumentziele:** [tests/test_agent_delegation.py](../../../tests/test_agent_delegation.py), [tests/test_agent_http_contract.py](../../../tests/test_agent_http_contract.py), [tests/test_agent_reliability.py](../../../tests/test_agent_reliability.py)

**Vorhandene Hilfen:** [tests/test_agent_delegation.py](../../../tests/test_agent_delegation.py), [tests/test_agent_reliability.py](../../../tests/test_agent_reliability.py)

**Befehle/Prüfauftrag nach Implementierung:**

- ` python -m pytest tests/test_agent_delegation.py tests/test_agent_reliability.py -q `

**Zu beachten:** —

**Implementierungsnachweis:** ` c723e42b ` · [docs/test-coverage/product/implementation-adapters.md](implementation-adapters.md) · [docs/test-coverage/execution.json](../execution.json)

**Ausgeführte Testbereiche:** [tests/test_agent_http_contract.py](../../../tests/test_agent_http_contract.py)

**Beobachtete Negativkontrolle:** Stopaufruf am Store entfernt: Zielturn bleibt ungesperrt.

**Verbleibende Grenze:** Firebase-SDK-Authentifizierung und DB ersetzt; externe Modell-, Mail- und Telegramgrenzen kontrolliert. Kein Live-OAuth oder produktiver Versand.


<a id="wp-33"></a>

## WP-33 · Modellrollback gegen fremde Writes absichern

**Ziel:** Kein Datenverlust durch den Fehlerpfad eines konkurrierenden Konfigwriters.

**Befunde:** [G-040](gaps.md#g-040) · **Vorher:** —

**Stand:** completed. Unabhängiger nativer Writer B bleibt trotz Aktivierungsfehler/Rollback A erhalten, auch ohne Vorgänger. Zusätzlich abgewiesener nativer Rollback-RPC: ursprünglicher Fehler/Diagnose ehrlich sichtbar, DB nicht fälschlich restored, lokaler Snapshot bewahrt.

**Vorgehen:** P-03 zunächst als deterministische Regression übernehmen. Native Firestore-Versionsbedingung wählen; zwei unabhängige Writerinstanzen unter Barrieren im Emulator einschließlich fehlendem Vorgängerdokument und Rollbackausfall prüfen.

**Abnahme zusätzlich zu den verknüpften Then-/Negativkontrollen:** Rollback löscht/überschreibt nur die eigene unveränderte Version mit nativer Precondition/Transaktion. B bleibt erhalten, auch wenn initial nichts existierte. Lokale Runtime bleibt beim eigenen letzten gültigen Stand; Fehler/Recoveryzustand ist ehrlich sichtbar. Keine globale DB-/Runtime-Atomizität behaupten. Bedingung aus Rollback entfernen: B-Erhalt muss rot werden; nur final==initial zu prüfen würde den Fehler festschreiben.

**Produktstellen:** [app/api/routers/admin.py](../../../app/api/routers/admin.py), [app/core/config.py](../../../app/core/config.py)

**Test-/Dokumentziele:** [tests/e2e/test_model_configuration_transactions.py](../../../tests/e2e/test_model_configuration_transactions.py), [tests/test_model_configuration.py](../../../tests/test_model_configuration.py)

**Vorhandene Hilfen:** [tests/test_model_configuration.py](../../../tests/test_model_configuration.py), [tests/e2e/test_prompt_config_transactions.py](../../../tests/e2e/test_prompt_config_transactions.py)

**Befehle/Prüfauftrag nach Implementierung:**

- ` python -m pytest tests/test_model_configuration.py tests/test_reasoning_policy.py tests/test_source_model_configuration.py -q; zusätzlich gezielter Firestore-Emulatorfall `

**Zu beachten:** —

**Implementierungsnachweis:** ` a19134b0 ` · [docs/test-coverage/product/implementation-persistence.md](implementation-persistence.md) · [docs/test-coverage/execution.json](../execution.json)

**Ausgeführte Testbereiche:** [tests/e2e/test_model_configuration_transactions.py](../../../tests/e2e/test_model_configuration_transactions.py), [tests/test_model_configuration.py](../../../tests/test_model_configuration.py)

**Beobachtete Negativkontrolle:** Rollbackrevision entfernt: B-Erhalt wird rot.

**Verbleibende Grenze:** Keine gemeinsame Atomizität zwischen Firestore und mehreren Serverruntimes.


<a id="wp-34"></a>

## WP-34 · Benchmarkfehler von Enthaltung trennen

**Ziel:** Fehlerklassifikation bis zu Resume und Statistik erhalten.

**Befunde:** [G-042](gaps.md#g-042) · **Vorher:** —

**Stand:** completed. HTTP200-Fehlerobjekte und ungültige Responseformen bleiben sichere Fehler bis Record/Resume/Statistik. Gültiger Text ohne Auswahl bleibt Enthaltung, private Fehlermeldungen werden entfernt.

**Vorgehen:** P-05 mit echten Record-/Resume-/Statsfunktionen in die bestehende Suite übertragen; HTTP-200-Body validieren, alte malformed-response-Sollvorgabe differenzieren und sichere Errorprojektion prüfen.

**Abnahme zusätzlich zu den verknüpften Then-/Negativkontrollen:** Provider-/Protokollfehler bleiben Fehler mit sicherem Code statt Enthaltung; sie werden nicht als Erfolg dedupliziert. Explizites retry_failed folgt der vorhandenen Policy. Gültiger Antworttext ohne auswertbaren Buchstaben bleibt Enthaltung. Keine Rohcredentials/privaten Providertexte persistieren; Counts/Kostenbehauptungen aus vorliegenden Feldern ableiten. Bodyerror-Prüfung entfernen: HTTP-200-Fehler darf die kombinierte error-/abstain-/Resumeassertion nicht bestehen. Kontrolle mit gültigem Text ohne Buchstaben verhindert fälschliches Umdeuten jeder Enthaltung in einen Fehler.

**Produktstellen:** [benchmark/transport.py](../../../benchmark/transport.py), [benchmark/runner.py](../../../benchmark/runner.py)

**Test-/Dokumentziele:** [tests/test_benchmark_protocol.py](../../../tests/test_benchmark_protocol.py), [tests/test_benchmark_results.py](../../../tests/test_benchmark_results.py), [tests/test_benchmark_runner.py](../../../tests/test_benchmark_runner.py), [tests/test_benchmark_transport.py](../../../tests/test_benchmark_transport.py)

**Vorhandene Hilfen:** [tests/test_benchmark_transport.py](../../../tests/test_benchmark_transport.py), [tests/test_benchmark_runner.py](../../../tests/test_benchmark_runner.py)

**Befehle/Prüfauftrag nach Implementierung:**

- ` python -m pytest tests/test_benchmark_transport.py tests/test_benchmark_runner.py tests/test_benchmark_results.py -q `

**Zu beachten:** —

**Implementierungsnachweis:** ` bad07367 ` · [docs/test-coverage/product/implementation-runtime.md](implementation-runtime.md) · [docs/test-coverage/execution.json](../execution.json)

**Ausgeführte Testbereiche:** [tests/test_benchmark_protocol.py](../../../tests/test_benchmark_protocol.py), [tests/test_benchmark_transport.py](../../../tests/test_benchmark_transport.py)

**Beobachtete Negativkontrolle:** Neun Regressionen vor Fix rot, Auswahl/echte Enthaltung als Gegenkontrollen.

**Verbleibende Grenze:** Keine Häufigkeitsmessung produktiver Providerfehler.


<a id="wp-35"></a>

## WP-35 · Google-Aktionsclaims mit nativen Transaktionen prüfen

**Ziel:** Höchstens ein Writeversuch pro gültiger Aktion; unknown bleibt gegen Wiederholung gesperrt, fremder Owner/alte Revision schreibt nichts.

**Befunde:** [G-043](gaps.md#g-043) · **Vorher:** —

**Stand:** completed. Gmail/Kalenderclaims nativ, maximal ein Writeversuch, Unknownreplay und Lese-Reconciliation sowie Owner/Revision/Approval/Hash/Supersession geprüft.

**Vorgehen:** Bestätigen, Leaseablauf und unklaren Transportausgang im lokalen Emulator steuern.

**Abnahme zusätzlich zu den verknüpften Then-/Negativkontrollen:** Höchstens ein Writeversuch pro gültiger Aktion; unknown bleibt gegen Wiederholung gesperrt, fremder Owner/alte Revision schreibt nichts.

**Produktstellen:** [app/services/agent_actions.py](../../../app/services/agent_actions.py)

**Test-/Dokumentziele:** [tests/e2e/test_google_action_transactions.py](../../../tests/e2e/test_google_action_transactions.py), [tests/test_agent_calendar.py](../../../tests/test_agent_calendar.py), [tests/test_agent_gmail.py](../../../tests/test_agent_gmail.py)

**Vorhandene Hilfen:** [tests/test_agent_calendar.py](../../../tests/test_agent_calendar.py), [tests/test_agent_gmail.py](../../../tests/test_agent_gmail.py)

**Befehle/Prüfauftrag nach Implementierung:**

- ` Gezielte Dateien, dann kombinierter Lauf; native Transaktionen nur mit demo-consensio-e2e. `

**Zu beachten:** —

**Implementierungsnachweis:** ` acdadb91 ` · [docs/test-coverage/product/implementation-persistence.md](implementation-persistence.md) · [docs/test-coverage/execution.json](../execution.json)

**Ausgeführte Testbereiche:** [tests/e2e/test_google_action_transactions.py](../../../tests/e2e/test_google_action_transactions.py)

**Beobachtete Negativkontrolle:** Replay-/Statusguards entfernt: zweiter externer Writeversuch erkannt.

**Verbleibende Grenze:** Google-HTTP an Wiregrenze ersetzt; keine echte Zustellgarantie.


<a id="wp-36"></a>

## WP-36 · Cloud-Dateiablage und verteilte Löschkaskade integrieren

**Ziel:** Keine öffentliche Freigabe, kein fremder Download und keine verwaisten Quoten/Versionen nach erfolgreichem Retry; Originalfehler bleibt sichtbar.

**Befunde:** [G-044](gaps.md#g-044) · **Vorher:** —

**Stand:** completed. Native Dateiquote, strenger privater Cloudadapter, Fehler-/Kaskadenretry und echter Dokumentrenderer mit immutable Vorversionen. Zusätzlich Firestore-Fehler 400 für Tabellen durch verlustfreien Codec behoben.

**Vorgehen:** Cloudadapter mit kontrolliertem Storage-Double und native Metadaten-/Quotatransaktionen samt Wiederaufnahme ausführen.

**Abnahme zusätzlich zu den verknüpften Then-/Negativkontrollen:** Keine öffentliche Freigabe, kein fremder Download und keine verwaisten Quoten/Versionen nach erfolgreichem Retry; Originalfehler bleibt sichtbar.

**Produktstellen:** [app/services/agent_files.py](../../../app/services/agent_files.py)

**Test-/Dokumentziele:** [tests/e2e/test_file_storage_transactions.py](../../../tests/e2e/test_file_storage_transactions.py), [tests/test_agent_documents.py](../../../tests/test_agent_documents.py), [tests/test_agent_files.py](../../../tests/test_agent_files.py)

**Vorhandene Hilfen:** [tests/test_agent_files.py](../../../tests/test_agent_files.py), [tests/test_agent_documents.py](../../../tests/test_agent_documents.py)

**Befehle/Prüfauftrag nach Implementierung:**

- ` Gezielte Dateien, dann kombinierter Lauf; native Transaktionen nur mit demo-consensio-e2e. `

**Zu beachten:** —

**Implementierungsnachweis:** ` acdadb91 ` · [docs/test-coverage/product/implementation-persistence.md](implementation-persistence.md) · [docs/test-coverage/execution.json](../execution.json)

**Ausgeführte Testbereiche:** [tests/e2e/test_file_storage_transactions.py](../../../tests/e2e/test_file_storage_transactions.py)

**Beobachtete Negativkontrolle:** Dateiquotaguard entfernt: zweiter Upload bei Limit1 erkannt.

**Verbleibende Grenze:** Bucketdouble prüft Adaptervertrag, keine produktive IAM.


<a id="wp-37"></a>

## WP-37 · Outbox-/Probeclaims mit nativer SDK-Konkurrenz absichern

**Ziel:** Resultat und Zustellabsicht atomar; alter Worker kann neuen Claim nicht bestätigen; Probe respektiert Tagesbudget und aktuelle Watchkonfiguration.

**Befunde:** [G-045](gaps.md#g-045) · **Vorher:** —

**Stand:** completed. Resultat/History/Outbox atomar; Vorcommitfehler, neuer Worker, stale Ack, Probe-Tagesbudget/Konfig/Einmalclaim und Tombstone belegt.

**Vorgehen:** Nativen Emulatorcommit, Crash nach Commit, Leaseübernahme und spätes Ack kontrollieren.

**Abnahme zusätzlich zu den verknüpften Then-/Negativkontrollen:** Resultat und Zustellabsicht atomar; alter Worker kann neuen Claim nicht bestätigen; Probe respektiert Tagesbudget und aktuelle Watchkonfiguration.

**Produktstellen:** [app/services/notification_outbox.py](../../../app/services/notification_outbox.py)

**Test-/Dokumentziele:** [tests/e2e/test_watch_delivery_transactions.py](../../../tests/e2e/test_watch_delivery_transactions.py), [tests/test_watch_evidence_model.py](../../../tests/test_watch_evidence_model.py), [tests/test_watch_review_regressions.py](../../../tests/test_watch_review_regressions.py)

**Vorhandene Hilfen:** [tests/test_watch_review_regressions.py](../../../tests/test_watch_review_regressions.py), [tests/test_watch_evidence_model.py](../../../tests/test_watch_evidence_model.py)

**Befehle/Prüfauftrag nach Implementierung:**

- ` Gezielte Dateien, dann kombinierter Lauf; native Transaktionen nur mit demo-consensio-e2e. `

**Zu beachten:** —

**Implementierungsnachweis:** ` acdadb91 ` · [docs/test-coverage/product/implementation-persistence.md](implementation-persistence.md) · [docs/test-coverage/execution.json](../execution.json)

**Ausgeführte Testbereiche:** [tests/e2e/test_watch_delivery_transactions.py](../../../tests/e2e/test_watch_delivery_transactions.py)

**Beobachtete Negativkontrolle:** Outboxownerguard und Probekonfigvergleich getrennt entfernt, unerlaubte Writes erkannt.

**Verbleibende Grenze:** Externe Benachrichtigungen bleiben at-least-once.


<a id="wp-38"></a>

## WP-38 · Aktuelle Testfehler und abweichenden Benchmark-Wiederholungslauf klären

**Ziel:** Gleiche fachliche Assertions bestehen isoliert und gemeinsam; keine Tests abschwächen oder Fehler nachträglich aus dem Primärlauf entfernen.

**Befunde:** [G-046](gaps.md#g-046) · **Vorher:** —

**Stand:** completed. Manifestzeit-/DST-Drift, UTF8-Subprozess, Fixture-/UI-Erwartungen, Resize-Scrollsprung und echter Composer-Autosizefehler nach CSS-Breitenanimation behoben. Playwright/native Scheduler teilen keinen Eventloop mehr; konkrete SDK-Aborted-Aufrufe werden vor einem gesonderten nächsten Tick als Fehlversuche dokumentiert. Vollständig integriert: 3303 Python-, 705 JavaScript-, 368 E2E- und 49 Rulesfälle bestanden.

**Vorgehen:** Prompt-/Mockzustand sowie Publisher-Subprozessresultat kontrolliert reproduzieren; aktuelle Browserfehler laut Laufbericht zuordnen.

**Abnahme zusätzlich zu den verknüpften Then-/Negativkontrollen:** Gleiche fachliche Assertions bestehen isoliert und gemeinsam; keine Tests abschwächen oder Fehler nachträglich aus dem Primärlauf entfernen.

**Produktstellen:** [tests/test_benchmark_budget.py](../../../tests/test_benchmark_budget.py)

**Test-/Dokumentziele:** [tests/e2e/test_scheduler_transactions.py](../../../tests/e2e/test_scheduler_transactions.py), [tests/e2e/test_smoke.py](../../../tests/e2e/test_smoke.py), [tests/js/chat-scroll.test.mjs](../../../tests/js/chat-scroll.test.mjs), [tests/js/composer-autosize.test.mjs](../../../tests/js/composer-autosize.test.mjs), [tests/js/frontend-output.test.mjs](../../../tests/js/frontend-output.test.mjs), [tests/test_benchmark_budget.py](../../../tests/test_benchmark_budget.py), [tests/test_benchmark_manifest_clock.py](../../../tests/test_benchmark_manifest_clock.py), [tests/test_navigation_settings_ui.py](../../../tests/test_navigation_settings_ui.py), [tests/test_publisher_standalone.py](../../../tests/test_publisher_standalone.py)

**Vorhandene Hilfen:** [tests/test_benchmark_budget.py](../../../tests/test_benchmark_budget.py), [tests/test_publisher_standalone.py](../../../tests/test_publisher_standalone.py)

**Befehle/Prüfauftrag nach Implementierung:**

- ` Gezielte Dateien, dann kombinierter Lauf; native Transaktionen nur mit demo-consensio-e2e. `

**Zu beachten:** —

**Implementierungsnachweis:** ` ffaca3df ` · [docs/test-coverage/product/implementation-runtime.md](implementation-runtime.md) · [docs/test-coverage/execution.json](../execution.json)

**Ausgeführte Testbereiche:** [tests/test_benchmark_manifest_clock.py](../../../tests/test_benchmark_manifest_clock.py), [tests/test_benchmark_budget.py](../../../tests/test_benchmark_budget.py), [tests/test_publisher_standalone.py](../../../tests/test_publisher_standalone.py), [tests/js/composer-autosize.test.mjs](../../../tests/js/composer-autosize.test.mjs), [tests/test_navigation_settings_ui.py](../../../tests/test_navigation_settings_ui.py), [tests/e2e/test_smoke.py](../../../tests/e2e/test_smoke.py), [tests/js/chat-scroll.test.mjs](../../../tests/js/chat-scroll.test.mjs), [tests/js/frontend-output.test.mjs](../../../tests/js/frontend-output.test.mjs), [tests/e2e/test_scheduler_transactions.py](../../../tests/e2e/test_scheduler_transactions.py)

**Beobachtete Negativkontrolle:** Clockregressionen, alter Scrollcontroller und Composer ohne Breitenbeobachtung liefern echte rote Assertions. Der alte Composer bleibt nach real beendeter CSS-Transition 180 px statt 52 px hoch. Historischer roter CI-Lauf bleibt erhalten; ursprünglicher unvollständiger Phase2-Verdacht wird nicht als nachgewiesene Flakebehebung ausgegeben.

**Verbleibende Grenze:** Grüne integrierte Runner gelten für ffaca3df. Keine neue Branch-Coverage oder flächige visuelle Prüfung; alte Fehlerbelege und alternative Plattformskips bleiben sichtbar.

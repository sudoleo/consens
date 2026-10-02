# Laufbefunde und Grenzen

**Stand: 02.10.2026 · Quellstand `2860844a` · Windows, lokaler Checkout**

[Katalog](../test-coverage-map.md) · [Laufmetadaten](execution.json) ·
[Alle roten Fall-IDs und Meldungen](evidence/failures-2026-10-02.md) ·
[Historischer Bericht](findings-2026-09-26.md)

## Aktuelle Ergebnisse

| Lauf | Ergebnis |
|---|---|
| Reguläres Pytest | 3.078 bestanden, 3 fehlgeschlagen; 179,59 s |
| Vitest | 72 Dateien, 664 Fälle bestanden; verschachtelte describe-Blöcke zählen nicht als Dateien |
| E2E-Collection | 308 Fälle in 30 Dateien |
| E2E-Auswahl | 219 bestanden, 30 fehlgeschlagen, 4 Setupfehler; 874,06 s |
| E2E nicht ausgewählt | 55 Fälle: 43 Smoke- und 12 Transaktionsfälle |
| Buildcheck | `static/dist is up to date` |
| Isolierte Wiederholung | Benchmark-Resume bestanden, Publisher-Ergebnisprüfung erneut fehlgeschlagen |

Primärlaufzahlen wurden durch Wiederholungen nicht geändert. Normalisierte
JUnit-/Vitestbelege behalten Originalidentitäten, Status und Fehlermeldungen;
Capturelogs/Tracebackkörper wurden für kompakte versionierte Nachweise entfernt.
Befehle, Versionen und Hashes stehen in [execution.json](execution.json).

## Pythonfehler

| Fall | Beobachtung / nächste Prüfung |
|---|---|
| `test_consensus_progress_ui.py::test_archived_turns_use_the_same_drawer_row_as_the_live_answer` | Alter exakter Klassenstring `consensus-tab` passt weiterhin nicht zu `consensus-tab consensus-evidence-action`. Historischer F-01/G-028 erneut bestätigt; kein automatisch bewiesener Layoutfehler. |
| `test_benchmark_budget.py::BenchmarkBudgetTests::test_resume_of_a_finished_pilot_does_not_pay_for_audits_again` | Gesamtlauf meldet Drift von `consensus_prompt_template`; isoliert bestanden. Reihenfolge-/Konfigurationszustand als Ursache untersuchen, nicht aus dem Primärlauf herausrechnen. |
| `test_publisher_standalone.py::PublisherStandaloneTests::test_scheduled_flow_without_packages_or_external_services` | Subprozessreturncode 0, aber Ergebnisprüfung addiert `None + str`. Begleitender Readerthread meldet UTF-8-Decodierfehler bei Byte 0x97. Kindprozess startet mit `-E -S` und bereinigter Umgebung; Encodingvertrag im Test prüfen. Auch isoliert rot. |

24 parametrische `test_dev_cli.py`-Fälle bestanden unter pwsh und Windows
PowerShell; dies sind Skripttests mit Tool-Doubles. Ein echter vollständiger
Emulatorstart über `dev.ps1 check browser` ist damit nicht nachgewiesen.

## Browserfehler nach Gruppe

| Datei/Gruppe | Anzahl | Beobachtete Grenze |
|---|---:|---|
| Agentchat | 7 | Abweichende Unterbrechungs-/Stoptexte und mobil nicht sichtbares Bedienelement |
| Agentvergleich | 1 | Geometrieabweichung von ca. 1,016 px gegenüber 1-px-Assertion |
| Gmail | 3 | Erwartete Dokumentversion 2 fehlt im Ressourcencontainer |
| Agentstatus | 4 | Erwartete Farben stimmen nicht mit aktuellen Styles überein |
| Chatscroll | 5 | Position des sichtbaren Antworttexts ändert sich beim Abschluss |
| Phase 4 | 8 | Quellenstatus/Locator, gruppierte Quellenpille bleibt pending, drei Run-/Modus-Timeouts |
| Readerdichte | 2 | Grenzwertabweichungen kleiner als 0,001 px |
| Agreement-/Cancel-Setup | 4 | `app_page` benötigt den nicht gestarteten Firestore-Emulator |

Das sind beobachtete **Testfehler**, keine pauschale Liste bestätigter
Produktdefekte. Besonders Text-/Farb-/Pixelassertions können veraltete
Erwartungen enthalten. Gmailressourcen, Scrollsprung und Runzustände verlangen
einen gezielten Abgleich von Produktverhalten, Fixture und Erwartung.
Vollständige Identitäten/Meldungen stehen im [Fehlerkatalog](evidence/failures-2026-10-02.md).

Die Auswahl schloss `test_smoke.py` und die drei Transaktionsdateien aus.
`test_agreement_verdict.py` und `test_run_cancel_and_progress.py` hängen
ebenfalls an `app_page`; ihre vier Fehler sind fehlende Voraussetzungen.
Für einen gezielten Lauf ohne Emulator zusätzlich diese beiden Dateien
ausschließen; für eine vollständige Freigabe alle integrierten Fälle mit
dem Demo-Emulator ausführen.

## Umgebung und verbleibende Grenzen

Reguläre Tests: `UNIT_TEST_MODE=1`, kein `RUN_E2E`, nicht geheimer
OpenRouter-Dummykey. Browser: `RUN_E2E=1`, `UNIT_TEST_MODE=1`, Chromium und
writerfreier Phase-4-Server/API-Doubles, soweit die jeweilige Fixture das
unterstützt. Git-safe.directory wurde nur pro Prozess gesetzt.

Ein erster npm-Aufruf scheiterte an der Windows-Sandbox mit EPERM; der
wiederholte Lauf außerhalb der Sandbox bestand. Keine daraus erfundene
Produktregression. Die vorhandenen dist-Änderungen wurden erhalten und
durch den Buildcheck geprüft.

Kein neuer Branch-Coveragelauf, keine neuen Mutationen, kein Live-OAuth,
keine produktiven Modelle/Mail-/Telegram-/Cloudtests. Die historischen
Emulatorfehler F-02/F-03 und instabilen Reports F-04 wurden nicht neu ausgeführt.
Die historischen Coveragewerte dürfen nicht auf den heutigen Code übertragen
werden. Neue Defizite und Umsetzungsaufträge stehen in
[product/gaps.md](product/gaps.md), insbesondere G-043–G-046.

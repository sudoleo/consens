# Produktabdeckung und Umsetzungsstand

**Stand: 02.10.2026 · integrierter Quellstand `ffaca3df`**

Der Abgleich verbindet **304 Produktdateien, 87
Vertragsgruppen, 291 Testdateien und 174
App-Routen plus 4 Frameworkrouten**. Die offenen Auditaufträge wurden
implementiert und unabhängig gegen ihre Abnahmekriterien geprüft.

38 der 38 Arbeitspakete sind vollständig abgenommen. Die in den Berichten benannten Betriebsgrenzen bleiben ausdrücklich bestehen.

| Dokument | Zweck |
|---|---|
| [Aktualisierungsbericht](current-review.md) | Produktkorrekturen und nachgeschärfte Nachweise |
| [Verhaltensmatrix](matrix.md) | Vertragsgruppen und konkrete Assertionstellen |
| [Quelleninventar](sources.md) / [Routen](routes.md) | Aktuelle Dateien, Hashes und Runtimezuordnung |
| [Befunde](gaps.md) | 46 Befunde mit aktueller Bewertung und historischer Spur |
| [Arbeitspakete](work-packages.md) | 38 Pakete mit Commit, Tests, Negativkontrolle und Restgrenze |
| [Nutzerreisen](journeys.md) / [Testvorgaben](decisions.md) | Schichtenketten und begründete Oracles |
| [Laufbericht](../findings.md) / [Laufdaten](../execution.json) | Tatsächliche finale Runnerbelege |
| [Persistenz](implementation-persistence.md), [Adapter](implementation-adapters.md), [Browser](implementation-browser.md), [Runtime](implementation-runtime.md) | Konkrete Umsetzung und fokussierte Prüfungen |
| [Messungen](measurements.md) | Historische Coverage/Proben mit damaligem Quellstand |
| [Kanonische Bewertung](audit.json) / [Suchspuren](search-evidence.json) | Maschinenlesbare Bewertung, kein automatischer Vollständigkeitsbeweis |

| Suite | Dateien | Definitionen | Runnerfälle | Ergebnis |
|---|---:|---:|---:|---|
| Python | 169 | 2445 | 3303 | 3.303 bestanden |
| JavaScript | 77 | 579 | 705 | 705 bestanden |
| Chromium / native SDK / Smoke | 44 | 205 | 368 | 368 bestanden |
| Firestore-Clientregeln | 1 | 2 | 49 | 49 bestanden |

Die alten Branchwerte **83,37 % Statements / 74,58 % Branches** gehören zum
26.09.2026 und Gitstand `145db25b`. Die aktuelle Abnahme ist uninstrumentiert;
Quellenänderungen erhalten keine erfundene neue Coveragezahl. Gezielt
ausgeschaltete Guards belegen die Wirksamkeit konkreter neuer Assertions.

Produktions-IAM, Live-Modellqualität, externe Exactly-once-Zustellung und eine
vollständige visuelle/Accessibility-Baseline sind keine Zusage dieser Tests.
Ein abgeschlossener Auditauftrag bleibt durch seine konkrete Testgrenze definiert.

```powershell
venv/Scripts/python.exe docs/test-coverage/check_inventory.py
venv/Scripts/python.exe docs/test-coverage/product/render_product_audit.py --check
venv/Scripts/python.exe docs/test-coverage/product/check_product_audit.py
```

Alte Bewertungen bleiben in `review_history`, `historical_verification` und Git.
[Historische Produktläufe](execution.json), [Coverage](python-coverage.json),
[Review](review.md) und [Gegenprüfung](independent-review.md) behalten ihren
damaligen Stand. Neue Läufe färben alte Primärergebnisse nicht nachträglich grün.

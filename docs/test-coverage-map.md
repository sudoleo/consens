# Testabdeckung: aktueller Bestand und geprüfte Grenzen

**Stand: 02.10.2026 · integrierter Quellstand `ffaca3df`**

Der Katalog enthält **291 Testdateien, 3,231 statische Definitionen und 4,425 Runnerfälle**.
Geänderte Testkörper, Assertions, Fixtures und Produktverträge wurden abgeglichen.
Das Inventar verbindet diese Beschreibungen mit tatsächlichen Runneridentitäten;
Testzahlen sind keine fachliche Coveragequote.

| Dokument | Inhalt |
|---|---|
| [Python-Katalog](test-coverage/backend.md) | Router, Dienste, Infrastruktur und statische Verträge |
| [JavaScript-Katalog](test-coverage/frontend.md) | jsdom, Module und Dateisystem-/Buildtests |
| [E2E-Katalog](test-coverage/e2e.md) | Chromium, persistierte Reisen und native SDK-Transaktionen |
| [Clientregeln](test-coverage/rules.md) | Echte permission-denied-Fälle mit Firebase-Client |
| [Produktbereiche](test-coverage/areas.md) | Fachlicher Einstieg über alle Suiten |
| [Produktabgleich](test-coverage/product/README.md) | 304 Produktdateien, 87 Vertragsgruppen und aktuelle Befunde |
| [Umsetzungsbericht](test-coverage/product/current-review.md) | Behobene Fehler, stärkere Nachweise und verbleibende Grenzen |
| [Laufbericht](test-coverage/findings.md) | Tatsächliche Ergebnisse, Umgebung und historische Abgrenzung |
| [Testanleitung](testing.md) | Einrichtung und sichere Runnerbefehle |
| [Inventar](test-coverage/inventory.json) / [Laufmetadaten](test-coverage/execution.json) | Definitionen, Assertionstellen, Fälle, Befehle und Artefakthashes |
| [Auditverfahren](test-coverage/next-audit.md) | Anforderungen, Negativkontrollen und Pflege |

| Suite | Dateien | Definitionen | Runnerfälle | Ergebnis |
|---|---:|---:|---:|---|
| Python | 169 | 2445 | 3303 | 3.303 bestanden |
| JavaScript | 77 | 579 | 705 | 705 bestanden |
| Chromium / native SDK / Smoke | 44 | 205 | 368 | 368 bestanden |
| Firestore-Clientregeln | 1 | 2 | 49 | 49 bestanden |

38 der 38 Arbeitspakete sind vollständig abgenommen. Die in den Berichten benannten Betriebsgrenzen bleiben ausdrücklich bestehen.

Native Tests verwenden ausschließlich den lokalen Demo-Firestore mit anonymen
Credentials. Browserreisen führen interne HTTP-/Service-/Persistenzschichten
aus; Detailtests verwenden teils bewusst API-/SDK-Doubles. Die genaue Grenze
steht je Datei. Google/SMTP/Telegram und kostenpflichtige Provider bleiben
kontrollierte äußere Testgrenzen. Kein Lauf bestätigt produktive IAM,
Live-Modellqualität oder vollständige visuelle/Accessibility-Abdeckung.

Die historischen Branchwerte vom 26.09.2026 bleiben unverändert und gelten
für ihren damaligen Gitstand. Neue Mutationsergebnisse sind gezielte
Wirksamkeitskontrollen, keine neue flächige Coverage-Messung.
[Läufe vor der Umsetzung](test-coverage/execution-pre-implementation-2026-10-02.json)
und [historischer Lauf](test-coverage/execution-2026-09-26.json) bleiben erhalten.

```powershell
venv/Scripts/python.exe docs/test-coverage/check_inventory.py
venv/Scripts/python.exe docs/test-coverage/product/check_product_audit.py
```

Die Checker benötigen Node und installierte Repoabhängigkeiten für den
AST-Abgleich. Sie validieren Hashes, Definitionen, Assertionstellen, Zuordnung
und Runnerbelege; sie führen keine Tests aus und ersetzen keine semantische
Gegenprüfung. Generiertes dist wird durch `npm run build:check` geprüft.

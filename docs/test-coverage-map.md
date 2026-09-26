# Testabdeckung: Bestandsaufnahme für den Folgeaudit

**Stand: 26.09.2026 · geprüfter Quellstand: `145db25bfe029ff7f50cd77595bd6b9e043c1a2f`**

Dieser Katalog beschreibt **jede der 216 Testdateien** anhand ihrer Testkörper,
Assertions, Fixtures und ersetzten Abhängigkeiten. Er dient als Ausgangspunkt,
um anschließend die Produktanforderungen und den Produktionscode systematisch
gegen die vorhandenen Tests abzugleichen und belegte Lücken zu schließen.

Die Dokumentation erfasst vorhandene Prüfungen. Sie ist **keine gemessene
Zeilen-/Branch-Coverage und kein Nachweis vollständiger fachlicher Abdeckung**.
Ein passender Testname, ein Import oder ausgeführter Code allein beweist noch
keine wirksame Absicherung des Verhaltens.

Der anschließende **[Produktcode-Abgleich und Codex-Umsetzungsplan](test-coverage/product/README.md)**
liegt inzwischen vor: 269 Produkt-/Betriebsdateien, 77 Verhaltensverträge,
36 gegengeprüfte Befunde und 30 geplante Arbeitspakete. Er ergänzt diesen
historischen Testdateikatalog um tatsächliche Python-Branchmessung und gezielte
Wirksamkeitsproben; die hier gespeicherten Laufstatus bleiben unverändert.

## Einstieg

| Dokument | Inhalt |
|---|---|
| [Reguläre Python-Suite](test-coverage/backend.md) | 133 Dateien, einschließlich API-, Service-, Infrastruktur- und statischer Frontendverträge |
| [JavaScript-Suite](test-coverage/frontend.md) | 57 Dateien, überwiegend Modul-/DOMtests, zusätzlich Build-Dateisystemtests |
| [Separate E2E-Suite](test-coverage/e2e.md) | 26 Dateien: Browserflows, isolierte Browserkomponenten und Emulatortransaktionen |
| [Produktbereiche](test-coverage/areas.md) | Rückverweise über die drei Suiten hinweg |
| [Produktabgleich und Arbeitspakete](test-coverage/product/README.md) | Code → Verhalten → Assertions → Lücken → konkrete Implementierungsaufträge |
| [Befunde und Laufbedingungen](test-coverage/findings.md) | Reproduzierte Fehler, abweichender Wiederholungslauf und Ausführungsgrenzen |
| [Vorgehen für den Folgeaudit](test-coverage/next-audit.md) | Anforderungen, Gegenprüfung, Lückenbelege und Implementierungsregeln |
| [Maschinenlesbares Inventar](test-coverage/inventory.json) | Alle Dateien, Beschreibungen, Definitionen, Assertion-Fundstellen, expandierten Testfälle und Laufstatus |
| [Laufprotokoll in JSON](test-coverage/execution.json) | Befehle, Umgebung, Ergebnisse und Herkunft der Laufdaten |

## Verifizierter Umfang

| Suite | Dateien | Statische Definitionen | Runner-Fälle | Primärlauf |
|---|---:|---:|---:|---|
| Reguläres Pytest | 133 | 2.034 | 2.730 | 2.717 bestanden, 1 fehlgeschlagen, 12 übersprungen |
| Vitest | 57 | 439 | 515 | 515 bestanden |
| Separates Pytest-E2E | 26 | 144 | 279 | 12 Emulatorfälle ausgeführt: 9 bestanden, 3 fehlgeschlagen; 267 Browserfälle nicht ausgeführt |
| **Gesamt** | **216** | **2.617** | **3.524** | **3.241 bestanden, 4 fehlgeschlagen, 12 übersprungen, 267 nicht ausgeführt** |

Die Testdateien enthalten zusammen 63.422 Quellzeilen. Das ist eine Bestandsgröße,
keine Qualitätsmetrik. Parametrisierungen erzeugen mehr Runner-Fälle als statische
Definitionen. Schleifen und `unittest.subTest` können mehrere Varianten innerhalb
eines Runner-Falls prüfen. Verschachtelte Vitest-Suites sind keine zusätzlichen
Testdateien.

Alle 2.178 Python-Definitionen sind einem gesammelten Pytest-Testnamen zugeordnet;
es gibt beim Abgleich keine fehlende Definition und keinen unbekannten
gesammelten Python-Test. Die 57 Vitest-Ergebnisdateien stimmen mit dem Dateiinventar
überein. Die Testdateimenge wurde zusätzlich gegen das Repository geprüft.

Ein fehlgeschlagener Emulatorfall bestand im **isolierten Wiederholungslauf**.
Die Tabelle bewahrt den ursprünglichen Gesamtlauf; sie rechnet den Fehler nicht
nachträglich heraus. Die Ursache dieser Abweichung ist offen. Details stehen in
[findings.md](test-coverage/findings.md).

## Was ein Dateieintrag bedeutet

Jede Datei hat dieselben Felder:

- **Ebene:** Was tatsächlich ausgeführt wird: etwa Python-Service mit Fake-DB,
  ASGI-Endpoint mit ersetzten Providern, Quelltextvertrag, jsdom-Modul,
  Browserflow mit API-Doubles oder echte Emulatortransaktion.
- **Geprüftes Verhalten:** Zusammenfassung der tatsächlichen Assertions und
  relevanten Zustandsübergänge. Bei einem fehlgeschlagenen Test ist dies der
  formulierte Prüfvertrag, kein bestandener Nachweis.
- **Grenzen und Doubles:** Welche Teile vorgegeben, ersetzt, ausgeschnitten oder
  nur als Text kontrolliert werden. Insbesondere sind DOM-Klassenprüfungen,
  Browsergeometrie, echte HTTPstreams und Providerqualität verschiedene Nachweise.
- **Prüfauftrag:** Konkrete offene Frage für den nächsten Audit. „Nicht in dieser
  Datei geprüft“ bedeutet nicht „nirgendwo in der Suite geprüft“.
- **Code-/Helferverweise:** Direkt erkennbare Imports und wörtliche Pfade.
  Dynamische Pfade, transitiv aufgerufener Code und gemeinsame Fixtures sind
  damit nicht vollständig abgebildet; die Verweise sind keine Coverage-Messung.
- **Testdefinitionen:** Aufklappbare Namensliste mit Quellzeilen. Im JSON stehen
  zusätzlich Parametrisierungsdeklarationen, Argumente, Assertion-Fundstellen
  und die vom Runner gemeldeten Fälle.

`cases[].id` bewahrt den vom Runner gelieferten Namen. Vitest meldet bei zwei
parametrisierten Prüfungen in `contradiction-source-verification.test.mjs`
denselben Namen für mehrere Varianten. Diese Fälle bleiben einzeln erhalten;
Dateipfad plus `report_ordinal` identifiziert sie innerhalb dieses Snapshots.
Die Ordinalzahl ist kein stabiler Schlüssel zwischen unterschiedlichen Läufen.

Die `assertion_evidence` im JSON ist eine syntaktische Suchhilfe. Assertionhelfer
können weitere Prüfungen enthalten; Aufrufe mit „assert“ im Namen sind nicht
automatisch wirksame Assertions. Playwright-`expect` und `wait_for_function`
werden ebenfalls erfasst. Die qualitative Beschreibung beruht auf der Prüfung
des Testkontexts, nicht auf einer Addition dieser Fundstellen.

## Gemeinsame Testgrenzen

| Grundlage | Wirkung auf die Aussagekraft |
|---|---|
| [`tests/conftest.py`](../tests/conftest.py) | Ohne `RUN_E2E=1` wird E2E ausgeschlossen. Autouse-Fixtures setzen leere zentrale Promptkonfiguration, neutrales Nutzergedächtnis und bereinigen den Kontextcache. Einzelne Tests überschreiben diese Defaults. |
| [`tests/js/helpers/appWindow.mjs`](../tests/js/helpers/appWindow.mjs) | Frisches jsdom mit echten geladenen Skripten; Browserlayout, Medienabfragen und andere APIs werden bei Bedarf simuliert. |
| [`tests/e2e/conftest.py`](../tests/e2e/conftest.py) | Chromium; lokaler Appserver mit Mock-LLM, Mock-Auth, deaktiviertem Rate-Limit und sicherem Emulatorprojekt. Im `app_page`-Pfad ersetzt ein Stub das gesamte App-Firebase-Modul. |
| [`tests/e2e/firebase_stub.js`](../tests/e2e/firebase_stub.js) | Vereinfacht Login-/Bookmarkanbindung für die Smoke-Suite. Dadurch wird kein produktiver Firebase-Login oder vollständiger Bookmarkclient geprüft. |
| [`test_phase4_frontend.py`](../tests/e2e/test_phase4_frontend.py) | Eigener writerfreier Server. App-eigenes Firebase-Modul läuft, dessen SDKs und Daten-APIs werden ersetzt. Viele andere Browserdateien importieren diesen Harness. |
| [`tests/frontend_order.py`](../tests/frontend_order.py) | Löst Frontendquellen entsprechend dem Bundle-/Ladereihenfolgevertrag auf. |
| [`tests/usage_test_support.py`](../tests/usage_test_support.py) | Gemeinsame Usage-Fakes; ersetzen keinen Firestore-Transaktionsnachweis. |

Die drei Dateien `test_agent_transactions.py`, `test_phase2_transactions.py`
und `test_prompt_config_transactions.py` brauchen keinen Browser. Sie prüfen
echte SDK-Transaktionen gegen den lokalen Firestore-Emulator. Mehrere
Storeinstanzen und Threads entsprechen dennoch nicht einem produktiven
Mehrprozess-/Mehrinstanzdeployment.

Die Browserdateien verwenden ausschließlich Chromium. Größen-, Fokus-,
Reduced-Motion- und Forced-Colors-Assertions gelten jeweils nur für die konkret
parametrisierten Szenarien. Gespeicherte Screenshots ohne Baselinevergleich sind
keine automatischen visuellen Regressionstests. Kein Lauf dieses Audits ruft
bezahlte Modelle auf oder bewertet deren fachliche Antwortqualität.

## Aktualität und Pflege

Aus dem Repositoryverzeichnis:

```bash
python docs/test-coverage/check_inventory.py
```

Die Prüfung kontrolliert Dateimenge, Hashes, Zählwerte und Quellstellen. Sie
markiert auch Änderungen an erfassten Grundlagen und am Produktionscode seit
dem geprüften Commit. Sie führt keine Tests aus und kann Beschreibungen nicht
semantisch neu bewerten.

Bei Test- oder Produktänderungen betroffene Einträge erneut inhaltlich lesen,
Runner-Fälle neu sammeln, Laufstatus mit Datum aktualisieren und danach JSON
und Markdown gemeinsam pflegen. Die Dateibeschreibungen im JSON sind die
Grundlage der erzeugten Katalogseiten. Nach einer inhaltlichen Aktualisierung:

```bash
python docs/test-coverage/render_catalog.py
python docs/test-coverage/check_inventory.py
```

Die Übersicht, Befunde und Laufmetadaten bei Bedarf ebenfalls aktualisieren.
Hashes allein zu ersetzen genügt nicht. Der
gespeicherte Laufstatus ist historisch und wird durch neue grüne Läufe nicht
automatisch aktuell.

Setup und normale Befehle stehen in [testing.md](testing.md), der sichere
Browser-/Emulatorstart in [tests/e2e/README.md](../tests/e2e/README.md).
Für den geprüften Stand existiert eine Publisher-Regression-CI, aber kein
allgemeiner Workflow für alle drei Suiten; siehe den Quellenabgleich in
[findings.md](test-coverage/findings.md).

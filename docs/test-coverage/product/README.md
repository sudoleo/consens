# Produktabdeckung und Umsetzungsstand

**Stand: 02.10.2026 · Quellstand `2860844a` · lokaler Windows-Checkout**

Der Abgleich verbindet **301 Produktdateien, 87 Vertragsgruppen, 254 Testdateien
und 174 App-Routen plus vier Frameworkrouten**. Dieser Auftrag aktualisiert
Dokumentation und Auditwerkzeuge; erwähnte Produktkorrekturen waren bereits vorhanden.

| Dokument | Zweck |
|---|---|
| [Aktualisierungsbericht](current-review.md) | Neue Funktionen und aktuelle Befundbewertung |
| [Verhaltensmatrix](matrix.md) | Alle Vertragsgruppen und konkrete Assertionstellen |
| [Quelleninventar](sources.md) | Dateien, aktuelle Hashes und Vertragszuordnung |
| [Routen](routes.md) | Runtime-Inventar einschließlich Datei-/Google-/Aktionsadapter |
| [Befunde](gaps.md) | 46 Befunde im Verlauf, mit aktuellem Status |
| [Arbeitspakete](work-packages.md) | 38 Pakete mit Abhängigkeiten und Restabnahme |
| [Nutzerreisen](journeys.md) | Schichtenübergreifende Abläufe |
| [Testvorgaben](decisions.md) | Aktuelle Erwartungen und vermiedene Fehlbefunde |
| [Laufbericht](../findings.md) | Aktuelle Ergebnisse und sämtliche roten Fall-IDs |
| [Messungen](measurements.md) | Historische Coverage und Proben |
| [Kanonische Bewertung](audit.json) | Status und Belege |
| [Suchspuren](search-evidence.json) | Neu erfasste Treffer; allein kein Lückenbeweis |
| [Quelldaten](sources.json), [Routendaten](routes.json) | Maschinenlesbarer Bestand |

Python: **3.078 bestanden, drei fehlgeschlagen**. JavaScript: **664 bestanden**.
E2E: **219 bestanden, 30 fehlgeschlagen, vier Setupfehler, 55 nicht ausgeführt**.
Buildcheck bestanden. Nachweise: [aktuelle Laufmetadaten](../execution.json).

G-018 (Topic-HTML) und G-037 (HTTP-Header) sind durch Implementierung und aktuelle
Regressionen adressiert. G-040 ist im simulierten Konkurrenzfall korrigiert;
nativer Mehrprozessnachweis fehlt. G-041 (Topic-Adminauth) und G-042
(Benchmark-Protokollfehler) wurden erneut isoliert beobachtet.
Ein behobener Befund kann zu einem noch `in_progress` geführten Paket gehören,
wenn dessen vollständige Integration/Negativkontrolle nicht abgenommen wurde.

## Messung und Umfang

**83,37 % Statements und 74,58 % Branches** stammen vom 26.09.2026, Quellstand
`145db25b`; **keine aktuellen Coveragewerte**. Der neue Lauf war uninstrumentiert.
Die Quellentabelle zeigt alte Messwerte nur für unveränderte Quellen; historische
Positionen werden gegen den alten Gitstand validiert.

Ausgewählt werden die im Checker definierten Produkt-/Betriebspfade mit
`.py/.js/.mjs/.html/.css/.json/.yml/.ps1/.rules`. Bundles, Vendorbibliotheken,
Fonts und binäre Assets sind keine separat bewerteten Quellmodule.
Build-/Lade-/Renderverträge sind über Tests verknüpft. Keine Live-Provider-,
Deployment- oder Cloudprüfung. Vertragsgruppen zählen nicht jede mögliche
Eingabe auf; Teilbelege beweisen nicht jede Klausel.

## Pflege

```powershell
venv/Scripts/python.exe docs/test-coverage/check_inventory.py
venv/Scripts/python.exe docs/test-coverage/product/render_product_audit.py --check
venv/Scripts/python.exe docs/test-coverage/product/check_product_audit.py
```

Vor Umsetzung Paket, Befund, tatsächliche Testkörper und aktuelle Produktvorgabe
lesen. Alte Bewertungen bleiben in `historical_verification` sowie Git.
[Historische Läufe](execution.json), [Coverage](python-coverage.json),
[Review](review.md) und [Gegenprüfung](independent-review.md) behalten ihren
damaligen Stand. Neue Läufe färben alte Primärresultate nicht nachträglich grün.

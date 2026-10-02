# Native Firestore-Client-Regeln: Abdeckung pro Testdatei

Stand: **2026-10-02**, Quellstand `ffaca3df7c8bbb02d850fb8f31d90107f26e9293`. [Methodik und Gesamtbefund](../test-coverage-map.md).

**1 Dateien · 2 statische Testdefinitionen · 49 Runner-Fälle.**

„Geprüftes Verhalten“ beschreibt die vorhandenen Assertions. Der Laufstatus steht separat: bei Fehlern ist der beschriebene Vertrag nicht als bestanden belegt. Prüfaufträge sind offene Fragen, keine pauschal festgestellten Lücken der gesamten Suite. Aktuelle Befundbewertungen stehen im [Produktabgleich](product/README.md).

Die Codeverweise sind direkte Imports oder wörtliche Pfade, keine gemessene Ausführungsabdeckung. Indirekte Abhängigkeiten über Fixtures/Helpers und dynamisch zusammengesetzte Pfade können fehlen. Das [JSON-Inventar](inventory.json) enthält jede Definition mit Zeilen, Assertion-Fundstellen und jeden expandierten Runner-Fall. Datum, Umgebung und Grenzen stehen im [Laufbericht](findings.md).

| Datei | Definitionen | Runner-Fälle | Primärlauf 2026-10-02 |
|---|---:|---:|---|
| [firestore.rules.test.mjs](#firestore-rules-test-mjs) | 2 | 49 | 49 bestanden |

<a id="firestore-rules-test-mjs"></a>

## firestore.rules.test.mjs

**Quelle:** [tests/rules/firestore.rules.test.mjs](../../tests/rules/firestore.rules.test.mjs) · **Bereiche:** Sicherheit, Authentifizierung.

**Ebene:** Echte Firebase-Clientoperationen gegen Firestore-Emulator.

**Lauf:** 49 bestanden.

**Geprüftes Verhalten:** Anonyme, eigene, fremde und Admin-Claim-Identität dürfen repräsentative tatsächliche Servicepfade nicht lesen, queryen, schreiben, ändern oder löschen. Enthält aktive und Legacyquellenjobs, API-/Datei-/Usagepfade und llm_calls. Temporär erlaubter Ownerwrite lässt dieselbe Denialassertion scheitern, danach Regeln wiederhergestellt.

**Grenzen und Doubles:** Emulatorregeln; Admin-SDK ausschließlich für eigene Seeds/Cleanup. Keine produktive IAM-/Deploymentfreigabe.

**Prüfauftrag für den Folgeaudit:** Die benannten Betriebs- und Testgrenzen bei künftigen Änderungen erneut prüfen; konkrete Paketnachweise stehen im Produktabgleich.

**Direkte Codeverweise:** [firebase.json](../../firebase.json), [firestore.rules](../../firestore.rules).

<details>
<summary>2 Testdefinitionen und ihre Quellstellen</summary>

- [`${identity}: no client read/write/query/delete of ${path.replace(owner, '{uid}').split('/').slice(0, -1).join('/')}`](../../tests/rules/firestore.rules.test.mjs#L49) (Zeile 49)
- [the same denial oracle detects an accidentally permitted owner write](../../tests/rules/firestore.rules.test.mjs#L63) (Zeile 63)

</details>

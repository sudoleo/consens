# Unabhängige Gegenprüfung von c88629ee

[Einstieg](README.md) · [Befunde](gaps.md) · [Arbeitspakete](work-packages.md)

**Reviewdatum: 26.09.2026 UTC.** Eingang: `c88629eed4466de1b0944dd20eb441880833a89b`.
Der initial per Git und GitHub bestätigte Remote-Stand war
`4d7c061036936b06bb98b2b306b2987a5844cde4`. Der lokale Commit war sauber und
enthielt die bisher nicht hochgeladenen Korrekturen. Vor Änderungen wurden
ein Sicherungsref `audit-safety/c88629ee-20260926` und ein erfolgreich geprüftes
vollständiges Gitbundle angelegt. Ein erneuter normaler Push scheiterte hier
an fehlenden HTTPS-Anmeldedaten; ein Timeout wurde dabei nicht beobachtet.
Der abschließende GitHub-Integrationsstatus wird beim Abschluss berichtet.

Die Gegenprüfung erweitert die kanonische Matrix auf **42 Befunde und 34
geplante Arbeitspakete**. **77 Vertragsgruppen, 216 Testdateien, 2.617 statische
Definitionen und 3.524 historisch gesammelte Runnerfälle** bleiben unverändert.
Produkt- und Testcode entsprechen weiterhin
`145db25bfe029ff7f50cd77595bd6b9e043c1a2f`. Kein Paket ist implementiert oder
als erledigt markiert. Geändert sind Auditdaten, Erläuterungen und Auditwerkzeuge.

## Neue Befunde und genaue Beleggrenzen

| Befund | Beobachtung | Grenze / Auftrag |
|---|---|---|
| [G-037](gaps.md#g-037), P-01 | UID-Limiter erzeugt 429 mit `Retry-After: 60`; der echte main-Fehlerhandler verliert den Header. Standard-FastAPI erhält ihn. | Synthetische Route durch main, keine vollständige Auth-/Agentintegration. WP-31 muss echte Ablehnungspfade samt Body, Header und Nichtaufrufen prüfen. |
| [G-038](gaps.md#g-038), P-02 | Undo nach Limitabsenkung meldet `undone`, obwohl eine unverändert gebliebene Notiz von 12.050 auf 12.000 Zeichen gekürzt wird. Gleiches Limit erhält alle Zeichen. | Reale Repositoryfunktionen und echter Persistenceguard, Fake-DB. WP-10 verlangt verlustfreie Semantik oder Ablehnung ohne Writes. |
| [G-039](gaps.md#g-039) | Detail mit gültiger Pagination und Turn-Stop werden nicht durch HTTP geprüft. Vorhandener Detailaufruf prüft nur `limit=51` → 422. | Fehlender Test, kein nachgewiesener Produktfehler. Store-/Servicebelege bleiben anerkannt. WP-32 ergänzt Ownership, Status, Pagination und Stop. |
| [G-040](gaps.md#g-040), P-03 | A schreibt, ein simulierter anderer Prozess schreibt B, As Aktivierung scheitert: Rollback überschreibt B mit initial. | Kontrollierte Reihenfolge im Dokument-Double, kein verteilter Firestorelauf. WP-33 verlangt bedingten Rollback und einen nativen Konkurrenznachweis. |
| [G-041](gaps.md#g-041), P-04 | Topic-Adminhelper fordert beim echten Tokenwrapper `check_revoked=False` an und akzeptiert das synthetisch widerrufene Token; zentraler Helper fordert True und lehnt ab. Rollenausfall wird nur zentral zu 503. | Firebase-SDK/Role/Tombstone-Doubles; kein echter widerrufener Firebase-Token. WP-16 korrigiert und prüft die tatsächliche Topicgrenze. |
| [G-042](gaps.md#g-042), P-05 | Ein HTTP-200-Providerfehlerbody wird zu `error=None`, `abstain=True` und einem erfolgreichen Resumeeintrag. Derselbe Body mit HTTP 429 bleibt Fehler. | Echter Transport/Record/Index, synthetische HTTP-Antwort. WP-34 trennt Protokollfehler von gültiger Antwort ohne auswertbaren Buchstaben. |

Die fünf Gegenproben sind als [Programm](probes/independent-probes.py) und
[unverändertes Beobachtungsergebnis](evidence/independent-probes.json) enthalten.
Sie ändern keine Produktdateien, starten keinen App-Lifespan und verbieten
Socketzugriffe. Externe Datenbanken, Provider, Mail und produktive Konten wurden
nicht verwendet. **Exitcode 0 bedeutet, dass die Beobachtung durchgeführt wurde;
die beobachteten Fehlverhalten sind damit nicht behoben.**

```bash
UNIT_TEST_MODE=1 python docs/test-coverage/product/probes/independent-probes.py
```

## Korrigierte Aussagen und Testaufträge

| Stelle | Korrektur |
|---|---|
| ADMIN-01/02 | Revision/Audit gelten nicht pauschal für alle Konfigurationen. Prompt/Budget sind revisioniert; Modellrollback und Publisherkonfiguration haben andere Garantien. Einzelwriter-Rollback ist kein Mehrprozessschutz. |
| UI-08 | Dynamische Landing-Scroll-/Animations-/Reduced-Motion-Tests existieren in `test_public_composer_mockups.py`; es fehlt ihr Laufnachweis. Die separate `landing-insights.js`-Lücke wird nicht auf den gesamten Landingbereich verallgemeinert. |
| AGENT-05 | jsdom prüft auch logischen Fokus, beispielsweise `activeElement` und Clipboard-Fallback. Browsergeometrie und native Selektion bleiben getrennte Grenzen. |
| G-007 / WP-10 | Neben Undo-Konflikt/Expiry/Owner/Retry fehlt die tatsächliche Undo-HTTP-Grenze einschließlich Error-Mapping. Der vorhandene kleine Erfolgsroundtrip verdeckt zusätzlich den Limitwechsel aus G-038. |
| G-013 / WP-15 | Sieben statt vier fehlende Adapter: Watch-PATCH/-DELETE, Telegram-Link/-Test/-Disconnect sowie Follower- und Watch-Unsubscribe. Die letzten drei fehlten im Auftrag. |
| G-014 / WP-16 | Adminlist, Topic-Confirm und Topic-Unsubscribe zusätzlich zu PUT/Hub/Sitemap/Follow. Beobachtete Authabweichung separat G-041; fehlende Adapter bleiben `missing_case`. |
| Rate-Limiter-Dateikatalog | Fallback auf IP ist nur für fehlende/falsch präfixierte Keys belegt. UIDtest ruft dieselbe UID zweimal auf, führt keinen echten Keywechsel aus. Separater API-IP-Guard existiert; kein pauschaler Bypassbefund. |
| Topic-Dateikatalog | `creates_updates` prüft Create/Run/Detail, keinen PUT. Service-CRUD darf nicht als HTTP-CRUD beschrieben werden. |
| Security-/Agent-/API-Dateikatalog | Eigene FastAPI-App und main.app unterscheiden. Der Limiter ist in den ersten Security-Routerfällen nicht deaktiviert. Consensus-API-Fixture ersetzt den UID-Guard, trotz echter separater Key-/IP-Limitfälle. |
| BENCH-02/03 | Providerfehler, Protokollfehler und Antwort-Enthaltung getrennt behandeln. Die vorhandene `choices=[]`-Assertion `error=None` ist kein unabhängiger Beleg korrekter Fehlerklassifikation. |

Alle neuen Pakete enthalten konkrete Produktquellen, bestehende Testbelege,
Given/When/Then, wiederverwendbare Helfer und Negativkontrollen. Die empfohlenen
Sollvorgaben werden von beobachtetem Istverhalten getrennt. Beispielsweise wird
für übergroßes Undo eine Ablehnung ohne Writes empfohlen; eine automatische
Überschreitung von Tierlimits wird nicht als bestehendes Recht vorausgesetzt.

## Katalog- und Prüferfehler

Die erneute syntaktische Extraktion aus den Testkörpern fand **128 fehlende
JavaScript-Assertionstellen in 74 Definitionen aus 26 Dateien**. Es handelt sich
um im selben Test wiederholte Prüfungen, häufig nach einem weiteren
Zustandswechsel. Ihre identischen Textfragmente hatten die spätere Fundstelle
nicht im Inventar erhalten. Die betroffenen Quellzeilen wurden inhaltlich
gegengeprüft und ergänzt; dies sind **keine neuen Tests oder neuen Laufnachweise**.

Der Inventarchecker rekonstruiert nun Pythondefinitionen und Assertionanker aus
dem AST sowie JavaScript-Registrierungen/`expect`-Anker über Acorn. Er vergleicht
Name, Anfang, Ende und vollständige Ankerliste mit dem JSON. Dafür werden Node
und die Repoabhängigkeiten (`npm ci`) benötigt; Acorn ist bereits im Lockfile.
Der Produktchecker prüft zusätzlich das tatsächliche Definitionsende sowie
Hashes/IDs der neuen Beobachtungsartefakte und die neuen JUnit-Ergebniszahlen.

Die [Werkzeug-Gegenkontrollen](probes/checker-self-check.py) manipulieren nur
In-Memory-Daten: erfundene Definition, verkürzter Testkörper, verschobene oder
ausgelassene Assertion sowie widersprüchliche Ausführungszahlen müssen abgelehnt
werden. Syntaktische Konsistenz bewertet weiterhin weder eine fachliche
Beschreibung noch die Wirksamkeit einer Assertion automatisch. Helper,
eingebettete Subprozessprogramme, Parametrisierungen und Mockwirkungen verlangen
inhaltliche Prüfung; die Ankerliste ist kein vollständiger Kontrollflussbeweis.

## Tatsächliche neue Ausführung

**374 vorhandene Pythonfälle bestanden, 0 fehlgeschlagen, 0 Fehler, 0 Skips,
6,520 Sekunden.** [JUnit](evidence/independent-focused.xml), genaue Auswahl und
Befehl in [execution.json](execution.json). Die Auswahl umfasst Memory-Edit,
Modellkonfiguration, Auth-Revocation, Agent-Capacity/Search/Delegation,
Consensus-API, Benchmark-Transport/-Runner, Topics und Watch. Sie bleibt grün,
während die neuen Gegenproben Fehlverhalten beobachten; daraus folgt gerade
keine Vollständigkeit. JUnit verwendet lokale Logzeit `+03:00`; der Lauf gehört
zum 26.09.2026 UTC.

Keine neue Vollsuite oder Coveragequote, kein Browser-, Windows-, Emulator-
oder Liveproviderlauf. Historische Ergebnisse bleiben erhalten:

- Python: 2.717 bestanden, ein bekannter Fehler, zwölf Windows-Skips.
- Vitest: 515 bestanden aus 57 Dateien.
- Emulator: neun bestanden, drei fehlgeschlagen; der isolierte Report-Race
  bestand, ohne den roten gemeinsamen Lauf zu erklären.
- 267 Browserfälle gesammelt, nicht ausgeführt. Windows: zwölf Varianten je
  verfügbarer Shell, kein neuer Nachweis.

Der breite Code-/Testabgleich hinterfragt die Beschreibungen aller 216 Dateien,
die 77 gruppierten Verträge und die bisherigen 36 Befunde einschließlich ihrer
Mockgrenzen. Produktpfade und behauptete Lücken wurden anhand ihrer konkreten
Implementierung, Testkörper/Assertions und benachbarter Tests geprüft; die
Suchspuren bleiben reproduzierbar. Er beansprucht keine formale Prüfung jeder
denkbaren Anforderung, keine Wahrheit der LLM-Antworten und keine Aussage über
aktuelle produktive Provider-/Datenbankzustände. Die 269-Dateien-Auswahl und ihre
ausgeschlossenen Artefakt-/Deploymentbereiche bleiben wie im Einstieg benannt.

## Abschlussprüfungen

Aus dem Repositoryverzeichnis mit den installierten Repoabhängigkeiten:

```bash
python docs/test-coverage/render_catalog.py
python docs/test-coverage/check_inventory.py
python docs/test-coverage/product/render_product_audit.py
python docs/test-coverage/product/render_product_audit.py --check
python docs/test-coverage/product/check_product_audit.py
python docs/test-coverage/product/probes/checker-self-check.py
git diff --check
```

Hashes von Produkt-/Testquellen wurden nicht erneuert. Nur der inhaltlich
korrigierte Inventarverweis und neue Beobachtungsartefakte erhalten neue Hashes.
Ausgeführt und bestanden: Inventarchecker, Produktchecker, Renderer-Abgleich und `git diff --check`. Die Werkzeug-Selbstprüfung lehnt zehn absichtlich verfälschte Datensätze ab; die zusätzliche Renderer-Gegenkontrolle bildet 33 geplante und ein blockiertes Paket korrekt ab. Diese Ergebnisse sind Konsistenz-/Werkzeugnachweise, keine zusätzlichen Produktfälle.

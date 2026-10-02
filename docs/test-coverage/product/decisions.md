# Testoracles, offene Entscheidungen und Fehlbefunde

[Einstieg](README.md) · [Arbeitspakete](work-packages.md)

Ein Testoracle beschreibt das beabsichtigte Ergebnis. Aktueller Code erklärt
den Istzustand, ist aber nicht automatisch die richtige Erwartung für jeden
Regressionstest. Explizite aktuelle Produktentscheidungen, konsistente
Dokumentation und begründete Invarianten verwenden. Bei Widerspruch den
Konflikt dokumentieren; weder alte Pläne noch den beobachteten Fehler blind
festschreiben. Routinefragen lassen sich anhand des Codes/Vertrags klären.
Nur eine tatsächlich offene Produktentscheidung benötigt eine Entscheidung
des Produktverantwortlichen.

<a id="d-01"></a>

## D-01 · API-Source-Checks und Publisherkonfiguration

Stand 02.10.2026: Die API-Dokumentation und Publisheranzeige wurden inzwischen
an den aktuellen Providerplan angepasst; `test_publisher_config.py` prüft ihn.
Die folgenden Hinweise erklären den früheren Widerspruch, nicht eine weiterhin
unverändert falsche API-Dokumentation.

[docs/consensus-api.md](../../consensus-api.md) und die neuen HTTP-/Recovery-
Nachweise bilden inzwischen den aktuellen Vertrag ab. Neue API-Läufe erzeugen
Consensus/Differences, aber keine neue Source-Check-Arbeit. Der historische
Source-GET bleibt für gespeicherte Jobs lesbar. Die aktuelle konfigurationsgestützte
Providerliste ersetzt den früheren pauschalen DeepSeek-Ausschluss.

[Scopeprüfung](../../../tests/test_source_check_scope.py),
[API-Routen](../../../app/api/routers/api_v1.py) und
[Publisherkonfiguration](../../../app/services/publisher_config.py) bleiben
gemeinsam zu lesen; historische Fixtures dürfen neue Jobs nicht wiederbeleben.

<a id="d-02"></a>

## D-02 · Agentlauf, Stop und Recovery

[AgentPolicy.for_chat](../../../app/services/agent_policy.py) verwendet
`account_budget_only`. Aktive Agentchats haben keine alten fixen Gesamtzeit-,
Call- oder Suchgrenzen. Kontotokenbudget, Parallelität, Providerkontext und
Stillstandsfristen gelten weiterhin. Der Legacy-AgentLoop bleibt separat
begrenzt. [test_agent_continuation.py](../../../tests/test_agent_continuation.py)
prüft ausdrücklich mehr als hundert Schritte und siebzehn Minuten.

Das ältere [Delegationskonzept](../../agent-delegation-spec.md) ist deshalb
kein Oracle für pauschale Drei-Call-/Gesamtlaufzeitgrenzen aktiver Chats.
Ein lebender Heartbeat ohne produktive Daten und ein produktiver langer
Stream sind verschiedene Fälle. Requestdeadline, Stream-Liveness und
Fortschrittswatchdog nicht als einen unveränderlichen Gesamttimer testen.

Persistierte Teilantworten/Receipts, expliziter Stop und gespeicherte Recovery
sind aktuelle Verträge. Dauerhafte Fortsetzung der Modellarbeit unabhängig
von jeder Browserverbindung wäre eine gesonderte Architekturentscheidung;
WP-29 darf dieses Verhalten nicht beiläufig als erforderliche Regression
einführen. Nachweise im [Agent-Zuverlässigkeitsaudit](../../agent-reliability-audit-2026-09-20.md)
beachten.

<a id="d-03"></a>

## D-03 · Versand ist keine verteilte Exactly-once-Transaktion

Der [Morning-Brief-Claim](../../../app/services/watch_brief.py) rückt den
Zeitplan vor und legt nun im selben Commit eine Zustellabsicht in der
[Outbox](../../../app/services/notification_outbox.py) mit deterministischer
Versand-ID an. Crash, Leaseübernahme, Retry, Ablauf und Unsubscribe haben
lokale und native Regressionsbelege. Ein Crash nach externer Zustellung vor dem Ack kann
weiterhin Doppelzustellung erlauben: die Outbox ist keine atomare Transaktion
mit SMTP/Telegram. Native Claims, stale Acks und atomare Resultat-/Outboxcommits sind nun belegt; die externe Zustellgrenze bleibt bestehen.

Tests sollen die konkrete aktuelle Claim-/Deduplizierungsgrenze absichern,
einschließlich Sendefehler. Sie dürfen keine atomare Exactly-once-Garantie
über Firestore und E-Mail/Telegram behaupten. Wenn das Produkt stärkere
Zustellung verlangt, Auslassung versus Duplikat sowie Outbox-/Provider-
Idempotenz bewusst entscheiden und erst danach Implementierung und Tests
erweitern. Das blockiert die bestehenden Adapter-/Slotprüfungen nicht.

<a id="d-04"></a>

## D-04 · Modellqualität benötigt eine eigene Evaluation

Provider-Doubles belegen Parser, Budget, Promptzusammenstellung, Attribution
und Orchestrierung. Sie belegen nicht, dass Consensus, Quellenurteil,
Claim-Identität oder Agentdelegation inhaltlich gut sind.
Die bestehenden Benchmark-/Evaluationswerkzeuge und gespeicherten Artefakte
sind Ausgangspunkte; historische Ergebnisse sind kein aktueller Suite-Lauf.

Nach den deterministischen Regressionen einen eigenen Qualitätsauftrag mit
folgenden überprüfbaren Ergebnissen durchführen:

1. Repräsentative Fälle nach Produktaufgaben zusammenstellen: belegbarer
   Konsens, Widerspruch, fehlende Bedingung, schwache/unzugängliche Quelle,
   Zahlen/Zeiten, deutsch/englisch, Quellen mit nicht vertrauenswürdigen
   Anweisungen, mehrteilige Agentaufgaben und sinnvolle Abstention.
2. Erwartungskriterien unabhängig vom zu bewertenden Output festlegen;
   Quellenprovenienz und zeitliche Gültigkeit speichern. Kein Modell darf
   ungeprüft seine eigenen Antworten als Goldstandard festlegen.
3. Entwicklungs- und zurückgehaltenen Evaluationssatz trennen. Keine
   nachträgliche Promptoptimierung auf dem endgültigen Testsatz. Fachliche
   Stichproben durch unabhängige menschliche Prüfung oder ausdrücklich
   begründete unabhängige Referenzen absichern.
4. Baseline und neue Variante auf denselben Fällen vergleichen. Modell-/Prompt-/
   Konfigurationsversion, Kosten, Latenz und Fehlerarten speichern; Qualität
   nach Fehlerklasse statt nur als aggregierten Score auswerten.
5. Für stochastische Fälle begründete Wiederholungen und Unsicherheit berichten.
   Äquivalente Formulierungen nicht über exakte Strings bestrafen; erfundene
   Belege, falsche Attribution und unberechtigte Sicherheit explizit werten.
6. Erst daraus Qualitätsgates ableiten. Live-Evaluation bleibt von schnellen
   Offline-Regressionen und Provider-Verfügbarkeitsproben getrennt.

In diesem Audit wurden keine bezahlten Providerläufe gestartet. Verfügbares
ChatGPT-Kontingent ist keine eingerichtete API-Abrechnung oder Freigabe eines
beliebigen externen Evaluationsbudgets. Das Offline-Dataset und die Rubrics
können vor einer solchen Betriebsentscheidung vorbereitet werden.

<a id="d-05"></a>

## D-05 · Browserziel und visuelle Abnahme

Zuerst die vorhandenen Chromiumfälle ausführen. Das Produktziel für
Safari/WebKit, Firefox, mobile Browser und assistive Bedienung anschließend
explizit festhalten. Zusätzliche Browser sind sinnvoll, wenn sie tatsächlich
unterstützte Nutzerpfade repräsentieren. Ihre Zahl ist kein Qualitätsmaß.

Fokusreihenfolge, Tastatur, Dialogrückkehr, Reduced Motion, Forced Colors,
Zoom/Reflow und lesbare Fehler an realen Nutzerreisen prüfen. jsdom-Klassen
belegen keine Geometrie. Ein gespeicherter Screenshot ohne bewertete Baseline
ist kein visueller Regressionstest. Visuelle Baselines nach inhaltlicher
Prüfung freigeben; nicht jede neue Ausgabe automatisch akzeptieren.

<a id="d-06"></a>

## D-06 · Kleine Grenzentscheidungen vor dem Testfix

| Grenze | Aktueller Hinweis | Vorgehen |
|---|---|---|
| Ungültige `Content-Length` | Middleware verwendet auch hier 413 | Ablehnung/Nichtaufruf zuerst schützen; Änderung zu 400 bewusst begründen |
| Bool-/Float-Indices im Identity-Judge | Der Modellvertrag fordert JSON-Integer: ausschließlich `type(index) is int` | Bool, Float, numerische Strings, null, negative/zu große Indices verwerfen; bekannte eindeutige Keys und reservierte Fallbackkeys prüfen |
| OG-Historie/Cache | Aktuelle OG-Route wählt den neuesten gültigen öffentlichen Antwortstand und übergibt leere `history_scores`; der Renderer besitzt zusätzliche Fähigkeiten | Keine beliebige historische Versionsauswahl oder Sparkline als aktuell garantierte Routenfunktion erfinden; Cachefrische an tatsächliche öffentliche Version binden |
| Topic `noindex` | Veröffentlichte aktive/pausierte Topics bleiben öffentlich im Hub; nur die Sitemap schließt `noindex` zusätzlich aus | Indexierung nicht mit Zugriffsschutz verwechseln; keinen erfundenen privaten Topicstatus testen |
| Erfolgreiche Antwort bei Speicherfehler | Chatabschluss kann die Antwort mit `chat_persisted=false` und `chat_turn_state=pending` liefern | Terminales `final` nicht als DB-Commit behandeln; Antwort und Persistenzstatus getrennt prüfen |
| Konto-Cleanup nach Checkpointverlust | Eine erfolgreiche Operation kann vor dauerhafter Quittierung abbrechen; der minimale UID-Tombstone bleibt nach Abschluss erhalten | Idempotente Wiederholung zulassen, dauerhaft quittierte Bereiche überspringen und Tombstone nicht als unerlaubten Datenrest werten |
| Lokaler Source-Transport | Produktionspolicy lehnt Loopback/andere Ports ab | Kontrolliertes Testziel nur im Testadapter einspeisen; echte SSRF-Ablehnung separat belegen, keinen Produktguard lockern |

Diese Punkte machen die klaren Konflikt-/Ownership-/Textinvarianten nicht
unsicher und erfordern keine pauschale Arbeitsunterbrechung.

<a id="d-07"></a>

## D-07 · Hilfsprogramme und Dry-run

`benchmark/run_sample.py` und `benchmark/run_experiment.py` bleiben unterstützt
und besitzen nun echte isolierte CLI-/Runner-/Manifest-/Resumebelege. Die
Probe-/Preview-Einstiege bleiben Qualitäts-/Diagnosewerkzeuge; ein Liveergebnis
ist keine automatische Modellqualitätsfreigabe. `vendorFrontend` ist ein exportierter Buildhelper, **kein CLI**; WP-30
ruft ihn direkt auf.

`backfill_claim_keys.py --dry-run` unterdrückt Datenbankwrites, ruft aber den
Identity-Judge auf. Dry-run deshalb nicht mit „kostenlos/netzwerkfrei“
gleichsetzen. Reparaturskript-Tests laufen ausschließlich mit isolierten
synthetischen Modulen und müssen den bestehenden Projekt-/Applyguard prüfen.
Ein echter Reparaturlauf ist kein Regressionstest.

## Bewusst verworfene Fehlbefunde

| Naheliegender Fehlschluss | Gegenbeleg / korrekte Grenze |
|---|---|
| Kein direkter Testimport bedeutet ungetestet | OG-Renderer wird indirekt über den Share-Router erreicht; neue Bildinhaltsassertions erkennen eine gültige weiße PNG |
| Kein direktes Parsing-/Defaultmodul im Testnamen bedeutet keine Coverage | Konsensparser und Promptdefaults werden über Pipeline-/Konfigurationstests erreicht; Imports sind nur Suchhilfe |
| Keine Real-Firestore-Chatprüfung vorhanden | `test_two_workers_cannot_exceed_owner_chat_limit` existiert; G-003 betrifft Delete/Completion |
| Agent-Abrechnung ausschließlich Fake | Native Agent- und inzwischen reguläre Usage-Transaktionen existieren; ihre konkreten Oracles stehen getrennt im Katalog |
| `creates_updates` im Topic-Test beweist PUT | Der Test ruft Create/Run/Detail auf und ersetzt Adminauth; G-014 |
| Endpoint-Kaskadentest beweist alle Datenbereiche | Dort ist der Löschservice ersetzt; G-004 ergänzt die konkrete Kaskade |
| `real_provider_socket_stall` verwendet echte Sockets | Der Test nutzt MockTransport; G-032 ergänzt die Transportgrenze |
| Ein grüner isolierter Report-Race widerlegt den roten Gesamtlauf | Primärlauf und Wiederholung bleiben beide Evidenz; konkrete SDK-Abbrüche und erfolgreiche Inkremente werden nun getrennt erfasst |
| Browserdatei vorhanden bedeutet Browservertrag grün | Tatsächliche aktuelle Fälle/Status in execution.json nachlesen; Dateivorhandensein allein beweist weiterhin keinen Lauf |
| Hohe Zeilenabdeckung sichert Undo/OG-Inhalt | Historische M-01/M-02 blieben grün; neue Revisions-/Bildinhaltsassertions erkennen die gezielten Mutationen |

## Zusätzliche Oracle-Korrekturen der unabhängigen Prüfung

- **Memory:** Erfolgreiches Undo darf keine unverändert gebliebene Notiz nach Limitabsenkung still kürzen. Implementiert ist eine strukturierte Ablehnung ohne Write; eine andere verlustfreie Wiederherstellung über dem aktuellen Limit wäre eine neue Produktentscheidung (G-038/WP-10).
- **Admin:** Modellkonfiguration besitzt jetzt eigene CAS-/Rollbackrevisionen; sie nicht mit Prompt-/Budget- oder Publishergarantien gleichsetzen. Ein Rollback darf nur den eigenen Write zurücknehmen (G-040/WP-33, native Konkurrenz und Rollback-RPCfehler geprüft).
- **Benchmark:** HTTP-200-Providerfehler sind keine Modell-Enthaltung. Gültiger Antworttext ohne extrahierbare Auswahl bleibt hingegen eine Enthaltung; diese Kontrolle muss die Fehlerkorrektur begleiten (G-042/WP-34).
- **HTTP:** Retry-After im isolierten Router ist kein Beleg für dessen Erhalt durch main.app. Ebenso beweist Pydantic-422 keinen ausgeführten Detailhandler (G-037/G-039).
- **UI:** Logischer Fokus ist in jsdom teilweise geprüft; aktuelle Chromiumläufe einschließlich Landing/Reduced Motion stehen im Dateikatalog. Rote Tests, fehlende Tests und fehlende Laufnachweise bleiben getrennt.

## Abschluss des späteren Gesamtvorhabens

Nach den Paketen erneut vom Produkt zur Suite prüfen: offene Vertragsklauseln,
neue Quellen/Routes, echte Testgrenzen, Fehlerpfade und unerreichte Branches.
Gezielte Mutationen an Owner-, Revisions-, Quota-, Idempotenz- und
Persistenzgrenzen einsetzen; äquivalente und unklare Mutationen getrennt
klassifizieren. Redundante Tests nur entfernen, wenn ihre einzigartige
Aussage erhalten bleibt. Aktuelle Gesamtstatus und verbleibende fachliche,
visuelle und externe Grenzen berichten. Weder Testzahl noch ein Coveragewert
allein kann diesen Abschluss ersetzen.

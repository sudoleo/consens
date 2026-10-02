# Zweite Gegenprüfung des Testaudits

**Historischer Bericht vom 26.09.2026.** Aktueller Quellstand und Befundstatus:
[Aktualisierung 02.10.2026](current-review.md). Die folgenden Laufzahlen und
Beobachtungen werden als damalige Nachweise erhalten.

[Einstieg](README.md) · [Verträge](matrix.md) · [Befunde](gaps.md)

**Aktuell:** Die [unabhängige Gegenprüfung von `c88629ee`](independent-review.md)
ergänzt sechs Befunde und vier Pakete: jetzt 42 Befunde und 34 geplante Pakete
bei unverändert 77 Vertragsgruppen. P-04 hat die unten noch statisch beschriebene
Topic-Adminabweichung mit SDK-Doubles reproduziert (G-041).
Der folgende Bericht bleibt als historische zweite Gegenprüfung erhalten;
seine Zahlen und Laufnachweise beziehen sich auf den damals geprüften Stand.

**Datum: 26.09.2026 · geprüfter Dokumentationscommit:
`4d7c061036936b06bb98b2b306b2987a5844cde4`**

Die zweite Prüfung gleicht die Auditdokumentation erneut mit Produktcode,
Testkörpern, gespeicherten Messdaten und gezielten Wiederholungen ab.
Produkt- und Testquellen entsprechen weiterhin
`145db25bfe029ff7f50cd77595bd6b9e043c1a2f`; geändert wurden ausschließlich
Auditbeschreibungen, abgeleitete Seiten und deren Prüf-/Erzeugungswerkzeuge.
Die 77 Vertragsgruppen, 36 Befunde und 30 geplanten Arbeitspakete bleiben
erhalten. Es wurden keine Arbeitspakete als implementiert verbucht.

## Inhaltliche Korrekturen

| Stelle | Fehler oder zu starke Aussage | Korrigierte Vorgabe und Beleg |
|---|---|---|
| CONS-05 / SSE-Dateikatalog | Erfolgreiches `final` wurde mit erfolgreicher Persistenz gleichgesetzt | Eine erfolgreiche Antwort bleibt bei Speicherfehler erhalten; Persistenzflags und Turnstatus melden den Unterschied. Der SSE-Parser selbst prüft keinen DB-Commit. [JSON-/SSE-Speicherfehlertest](../../../tests/test_consensus_chat_history.py#L815), [Parserfälle](../../../tests/js/sse-completion.test.mjs) |
| WATCH-05 | Zusätzliche deduplizierte Versand-ID behauptet | Morning Brief nutzt einen persistenten Vorabclaim; Crash danach kann einen Brief auslassen. Keine separate Versand-ID in diesem Pfad. [Claim](../../../app/services/watch_brief.py#L195), [Versand](../../../app/services/watch_scheduler.py#L585) |
| SEO-04 / Dateikatalog | Genau ein Review pro lokaler Woche behauptet | Konfigurierbares Intervall 1–90 Tage, Default 7, lokale Uhrzeit/Zeitzone; erzwungener Lauf und Lease getrennt behandeln. [Konfiguration](../../../app/services/seo_weekly_review.py#L413) |
| AUTH-03 / G-004 / WP-09 | Nur fehlgeschlagene Operationen wiederholen; alle Daten restlos entfernen | Dauerhafte Checkpoints entscheiden über Wiederholung. Bereits ausgeführte, unbestätigte Operationen müssen idempotent wiederholbar sein. Minimalen UID-Sperrtombstone erhalten, Cleanup-E-Mail entfernen. [Orchestrierung](../../../app/services/account_deletion.py#L93) |
| TOPIC-04 / G-014 / WP-16 | Indexierung mit Sichtbarkeit vermischt, privaten Topiczustand vorausgesetzt | Hub enthält veröffentlichte aktive/pausierte Topics einschließlich `noindex`; Sitemap schließt `noindex` zusätzlich aus. Archive/unveröffentlichte Topics fehlen in beiden Listen. [Vorhandener Gegenbeleg](../../../tests/test_topics_feature.py#L485) |
| AUTH-02 / G-014 / WP-16 | Zentrale Revocation-/Rollenprüfung auf alle sensitiven Router übertragen | [Topichelfer](../../../app/api/routers/topics.py#L133) fordert keine Revocationprüfung an und besitzt keine eigene 503-Abbildung bei Rollendienst-Ausfall; [zentraler Adminhelfer](../../../app/api/routers/admin.py#L151) tut beides. G-014 verlangt jetzt explizite Grenztests. Rollenwerte können aus dem vorgesehenen Cache stammen. Session-Cookie wird bei Registrierungsbestätigung gesetzt. |
| G-021 / WP-24 | Storage-`getItem`-Fehler als ausgeführte Verzweigung gefordert | Das [Skript](../../../static/js/analytics-opt-out.js) verwendet `setItem`/`removeItem`. Abwesende/andere Querywerte erhalten den vorhandenen Wert. |
| G-026 / WP-04 | Windows-Gesamtzahl unveränderlich auf zwölf festgelegt | Zwölf Varianten **je verfügbarer Shell**, derzeit zwölf oder 24 bei einer oder zwei Shells. Die historischen zwölf Linux-Skips bleiben korrekt. [Fixture](../../../tests/test_dev_cli.py#L25) |
| G-030 / WP-29 / Nutzerreisen | Ein pauschaler Usage-Charge auch für Agentläufe | Reguläre einmalige Runbelastung und Abrechnung tatsächlicher Agent-Providersteps unterscheiden; Recovery darf keine Buchung duplizieren. [Agentabrechnung](../../agent-accounting-audit.md) |
| G-033 | Ungültige Konfiguration verhindere zwingend den Appstart | Parser/Middlewarekonstruktion lehnt ungültige Werte ab; Konstruktion kann erst beim ersten Request stattfinden. [Konfigurationsparser](../../../app/core/request_limits.py#L12) |
| SHARE-04 / D-06 | OG-Karte aus beliebig ausgewähltem Antwortstand nahegelegt | Aktuelle OG-Route wählt den neuesten gültigen öffentlichen Antwortstand, übergibt leere `history_scores`. Keine historische Auswahl oder Sparkline als vorhandenen Vertrag erfinden. [Share-Router](../../../app/api/routers/share.py) |
| G-018-Darstellung | Rohes, nicht geschlossenes HTML-Tag in Markdown | Das inerte HTML-Beispiel ist jetzt als Code ausgezeichnet und wird nicht als Formatierung interpretiert. |

Die Adminabweichung ist ein **statischer Codebefund**. Es wurde kein echter
widerrufener Firebase-Token eingesetzt und kein produktiver Angriff geprüft.
Die ergänzten Fälle sollen die zentrale Adminpolicy an der Topicgrenze
absichern; sie behaupten keine bereits bestehende Gleichheit der Helfer.

## Korrekturen an den Auditwerkzeugen

- Der Renderer leitet Paketstatus und Übersichtszahlen aus den kanonischen
  Daten ab. Die bisher fest eingebaute Aussage „alle geplant“ wäre nach einem
  späteren Statuswechsel falsch geblieben.
- Der Checker vergleicht zusätzlich Coverage-Detailarrays mit ihren Zählern,
  prüft doppelte/überlappende Positionen, gültige Quellzeilen, eindeutige
  Routen-IDs und den tatsächlichen Anfang einer Assertion an ihrer Fundstelle.
- Gespeicherte Mutationsproben werden nach Fallidentität und Ergebnis gegen
  ihre JUnitdateien geprüft. Ein grüner Konsistenzcheck bleibt ausdrücklich
  kein automatisch erneuerter fachlicher Review oder Testlauf.

## Erneute Validierung

| Prüfung | Ergebnis / Aussagegrenze |
|---|---|
| Inventar- und Produktchecker, deterministisch erzeugte Seiten, lokale Links und Git-Diff | Konsistent; Quellen-/Testhashes unverändert |
| Runtime-Routen gegen Snapshot | Alle 162 Einträge nach Methoden, Pfad, Handler, Quelle, Zeile und Schemaflag identisch; keine HTTP-Verhaltensprüfung |
| Kompakter Coveragebericht gegen ursprünglichen Rohbericht | SHA-256 des Rohberichts stimmt; Metadaten, Summen und Detaildaten aller 136 Dateien einschließlich unausgeführter Funktionen identisch |
| Ursprüngliche Python-JUnitdaten gegen Laufmetadaten | 2.717 bestanden, 1 fehlgeschlagen, 12 übersprungen bestätigt; kein neuer Gesamtlauf |
| Elf gezielte vorhandene Tests | 11 bestanden: Speicherfehler JSON/SSE, Topic-noindex, Briefclaim, SEO-Default/Zeitplan, Kontolöschretry und zentrale Auth-/Revocationfälle; [JUnit](evidence/recheck-focused.xml) |
| M-01 wiederholt | 14 bestanden trotz entfernter Undo-Revisionsprüfung; Assertionslücke weiter reproduzierbar; [JUnit](evidence/recheck-memory.xml) |
| M-02 wiederholt | 2 bestanden, 149 nicht ausgewählt trotz weißer OG-Karte; Inhaltslücke weiter reproduzierbar; [JUnit](evidence/recheck-og.xml) |
| D-01/D-02 wiederholt | Inerte Notiz wird wieder als Element interpretiert; strukturierter Appfehler wird weiterhin als `[object Object]` angezeigt |
| Auditwerkzeuge mit absichtlichen In-Memory-Fehlern | Falscher Coverage-Detailzähler, abweichendes Probe-Ergebnis, doppelte Routen-ID und verschobene Assertionstelle werden abgelehnt; Paketübersicht folgt geändertem Status |

Die Gegenbeispiele für die Werkzeuge sind als explizite, dateischreibfreie
[Selbstprüfung](probes/checker-self-check.py) reproduzierbar:

```bash
python docs/test-coverage/product/probes/checker-self-check.py
```

Die gezielte Testauswahl lässt sich mit den üblichen Repoabhängigkeiten so
wiederholen (Python 3.12.14, pytest 8.4.2):

```bash
env -u RUN_E2E UNIT_TEST_MODE=1 \
  OPENROUTER_API_KEY=audit-placeholder-not-a-real-key \
  python -m pytest -q \
  tests/test_consensus_chat_history.py::test_completion_storage_failure_never_replaces_successful_consensus \
  tests/test_topics_feature.py::test_noindex_and_unpublished_topics_are_not_in_topic_sitemap \
  tests/test_watch_feature.py::BriefClaimTests::test_claim_advances_before_sending_and_prevents_double_send \
  tests/test_seo_weekly_review.py::test_default_interval_is_seven_days_and_lease_is_persistent \
  tests/test_seo_weekly_review.py::test_weekly_schedule_uses_configured_local_time \
  tests/test_account_deletion_retry.py tests/test_auth_revocation.py
```

Die vier Auditproben verwenden die unveränderten Befehle aus
[measurements.md](measurements.md). Ihre grünen Mutationsläufe sind gerade
**kein** Nachweis korrekter Schutz-/Bildinhaltsassertions.

## Verbleibende Grenzen

Die bekannten roten regulären/Emulatortests, die 267 Browserfälle ohne
Laufnachweis und die fehlende Windowsausführung bleiben offen. In dieser
Gegenprüfung wurden keine Browser-, Windows-, Emulator- oder bezahlten
Providerläufe gestartet und keine produktiven Daten verwendet.
Die Korrekturen verbessern die Grundlage für spätere Implementierungen;
sie machen weder die gesamte Suite grün noch alle Produktverträge vollständig
getestet. Historische Laufdaten wurden nicht als neue Ergebnisse ausgegeben.

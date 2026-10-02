# Umsetzung der Persistenzpakete – 2. Oktober 2026

Diese Nachweise ergänzen das historische Audit. Sie verwenden den lokalen
Firestore-Emulator 1.19.8, Firebase CLI 13.35.1 und Java 21.0.12,
Python 3.9.7/google-cloud-firestore aus der Projekt-venv. Ausschließlich
`demo-consensio-e2e` auf `127.0.0.1:8085`, anonyme SDK-Credentials und explizites
`E2E_TEST_MODE=1`; der Helper lehnt andere Umgebungen vor dem Clientbau ab.
Unique Owner-/Ressourcen-IDs und rekursives Aufräumen verhindern globale Clears.
Kein Test sendet echte Google-, SMTP-, Telegram- oder Cloud-Storage-Schreibaufrufe.

## Behobene Produktfehler

- **G-038, Memory:** Patch und Undo lehnen einen Vorzustand über dem aktuellen
  Notizlimit mit `memory_limit` ab. Profil, Revision, Request und Quoten bleiben
  bei der Ablehnung unverändert. Die neue Regression war vor dem Fix für beide
  Operationen rot; HTTP durch `main` liefert strukturiert 422.
- **SEO-Lease:** Abschluss prüft den aktuellen Owner und schreibt den nächsten
  Termin atomar. Ein abgelaufener oder erneut ausgeführter Abschluss kann keinen
  fremden Lease und keinen neueren Zeitplan überschreiben.
- **Watch-Probe:** Ein einmaliger Claim-Token und Vergleich von
  `config_generation`, Ziel, Zeitplan, Modellstufe und letztem Vollcheck verhindern
  veraltete Ergebnisse. Claim/Resultat beachten die Kontolöschsperre. Auch normale
  Watch-Claims, Completion und Fehlerabschluss lesen jetzt den Kontotombstone in
  ihrer Transaktion.
- **Dokumenttabellen:** Der native Test mit echtem DOCX-/PDF-Renderer entdeckte
  einen Firestore-400 beim Speichern von Tabellen: verschachtelte Zeilenarrays
  sind dort nicht zulässig. Storage-Schema 2 speichert Zeilen als Maps mit `cells`.
  Der verlustfreie Lesecodec stellt die gleiche DocumentSpec wieder her; API,
  Inhaltshash und unveränderliche Vorversionen behalten ihre Bedeutung.

## Pakete und konkrete Grenzen

| Paket | Nachweis | Negativkontrolle |
|---|---|---|
| WP-01 (Persistenzanteil) | `test_phase2_transactions.py`: aktueller `tier`-Parameter und gültiges Pending-Expiry; Watch-/Chatlimit und Share-Idempotenz nativ | Watch-Quotaguard entfernt: zwei Gewinner werden erkannt |
| WP-02 | Report-Zähler, Gründe und Reviewflag ohne verlorene Inkremente; Indexstatus bleibt gemäß aktuellem R19-Vertrag unverändert | Zähler immer 1: Oracle wird rot |
| WP-07 | `test_usage_transactions.py`: gleicher Key, letzter freier Betrag, gemessene/geschätzte und getrennte konkurrierende Buchungen, Release/Consume, alter/neuer UTC-Tag, Kontrollowner | Buchungsdeduplizierung entfernt: Doppelabbuchung erkannt; echte SDK-Reads/Writes aus der Transaktion verlagert: doppelte Admission bzw. verlorene Buchung erkannt |
| WP-08 | `test_chat_lifecycle_transactions.py`: beide Commitreihenfolgen Delete/Completion sowie tatsächlicher Zwischenzustand nach Tombstonecommit vor physischem Purge; Completion/Create/Failure ändern weder Chatnachfahren noch Löschjob, danach vollständige Kaskade; Context-Finalisierung, terminales Failure und Kontrollowner | Active-Guard entfernt: Completion schreibt während `deleting`; zusätzlich terminalen Statusguard entfernt: fehlgeschlagener Turn wird unzulässig completed |
| WP-09 | `test_account_deletion_transactions.py`: alle **16 aktuellen** Bereiche, Google-/API-Metadaten, Dokumentversionen, fremde Daten; Objektfehler, fehlender Parent, neue Serviceinstanz, verlorene Checkpoints, Tombstone/E-Mail | Receipt-Bereich übersprungen: verbleibende persönliche Daten erkannt |
| WP-10 | `test_memory_edit_transactions.py` + `test_memory_edit.py`: native Patch/Save-CAS, verlorene Lease, Undo-Owner/Expiry/Retry/Konflikt, Limitabsenkung ohne Writes; echtes `main` mit Auth-, Tier- und Undo-Fehlern | Verlustschutz entfernt: Undo kürzt und Regression wird rot |
| WP-14 | `test_source_check_transactions.py`: getrennte Repositoryinstanzen, Claimübernahme, alter Lease, genau ein Paketcommit, Delete ohne Wiederanlage, vollständige Pagination und Revisionsbindung | Leasevergleich entfernt: alter Worker committet, Oracle wird rot |
| WP-19 | `test_scheduler_transactions.py`: echte fällige Watch-/Topicqueries, Claim-/Budgetkonkurrenz, alte Topic-/Watch-/SEO-Owner; bestehende Supervisor-/Shutdownfälle bleiben im fokussierten Lauf | SEO-Ownerguard entfernt: Nachfolgerzustand wird überschrieben |
| WP-33 | `test_model_configuration_transactions.py`: aktivierender Writer A gegen unabhängige SDK-Transaktion B unter Events, mit/ohne Vorgängerdokument, stale Revision; lokale Runtime-Fehler zusätzlich bestehende Unitfälle | Rollbackrevision entfernt: B geht verloren |
| WP-35 | `test_google_action_transactions.py`: Gmail und Kalender mit nativer Approval-/Intenttransaktion; echte Payloads, verschlüsselte Dummygrants, Capability-/Revision-/Quotaprüfung; ausschließlich HTTP-Wire ersetzt; unknown, Fremdowner, alte Revision/Preview/Approval/Supersession | Status-/Replayguard entfernt: zweiter externer Writeversuch erkannt |
| WP-36 | `test_file_storage_transactions.py`: echter Cloudadapter an strengem Bucket-Double, native Quote, privater Pfad, Fremddownload, Originalfehler, Löschretry sowie echter Renderer und immutable Dokumentversionen | Dateiquotaguard entfernt: zwei Uploads bei Limit 1 erkannt |
| WP-37 | `test_watch_delivery_transactions.py`: Ergebnis/History/Outbox gemeinsam, Abbruch vor Commit ohne Teilwrite, neuer Worker nach Commit, Claimübernahme/stales Ack, Probe-Tagesbudget, Konfigdrift, wiederholte Completion, Kontotombstone | Outbox-Ownerguard bzw. Probe-Konfigvergleich entfernt: unerlaubter Write erkannt |

## Befehle und Ergebnisse

Abschlussprüfung: **38 native Tests bestanden in 97,96 s**, dazu **346 fokussierte
Unit-Tests in 16,83 s** und **36 Datei-/Dokument-Unit-Tests in 26,94 s**.
Alle **13 Negativkontrollen** wurden durch fachliche Assertions abgewiesen.
Im nativen Abschlusslauf waren die getrennten Wiederholungsaufrufe bei Source
(zwei abgebrochene Worker) und Topic (ein Worker) erforderlich und als Warnungen
sichtbar; ihre genaue Bedeutung steht unten.

Die unabhängige Abnahme ergänzte anschließend zwei stärkere Nativefälle:
Eine echte Löschung pausiert nach dem committed `deleting`-Tombstone und
Löschjob vor dem physischen Purge, während ein anderer Worker Completion,
Create und Failure versucht. Der vollständige Zustand wird vor Fortsetzung
der Kaskade auf Nichtmutation geprüft. Getrennte gleichzeitige Buchungen
prüfen außerdem sowohl den gemeinsamen Kontostand als auch beide Receipts.
Die zusätzlichen Mutationen entfernen ausdrücklich den Active-/Deleting-Guard
bzw. verlagern echte SDK-Reads und Writes aus der Transaktion. Eine Barriere
in diesen beiden absichtlich ungeschützten Mutanten erzwingt denselben
Ledger-Vorzustand; sie befindet sich nie in einem echten SDK-Callback.
Alle fachlichen Quota-/Dedupguards bleiben für die Atomaritätskontrolle aktiv.
Der fokussierte Abschluss dieser Ergänzung bestand mit **9 Tests in 14,68 s**;
alle drei zusätzlichen Negativkontrollen scheiterten an den vorgesehenen
fachlichen Assertions. Damit sind **16 unterschiedliche Mutationen** erkannt.
JUnit: `test-results/persistence-acceptance.xml`; Mutationen:
`python tests/e2e/native_mutations.py WP-07-atomicity WP-07-atomicity-charge WP-08`.

Die Native-Tests benötigen diese Umgebungswerte, zusätzlich zu `UNIT_TEST_MODE=1`
und `RUN_E2E=1`: `E2E_TEST_MODE=1`,
`FIRESTORE_EMULATOR_HOST=127.0.0.1:8085`,
`GOOGLE_CLOUD_PROJECT=GCLOUD_PROJECT=FIREBASE_PROJECT_ID=demo-consensio-e2e`.
`GOOGLE_APPLICATION_CREDENTIALS` ist entfernt. Der Emulator wird separat
gestartet; die Testprozesse starten keinen Server und führen kein globales Reset aus.

```powershell
python -m pytest tests/e2e/test_usage_transactions.py tests/e2e/test_memory_edit_transactions.py tests/e2e/test_source_check_transactions.py tests/e2e/test_chat_lifecycle_transactions.py tests/e2e/test_google_action_transactions.py tests/e2e/test_file_storage_transactions.py tests/e2e/test_scheduler_transactions.py tests/e2e/test_model_configuration_transactions.py tests/e2e/test_account_deletion_transactions.py tests/e2e/test_watch_delivery_transactions.py tests/e2e/test_phase2_transactions.py -q
python tests/e2e/native_mutations.py
python -m pytest tests/test_memory_edit.py tests/test_watch_evidence_model.py tests/test_watch_review_regressions.py tests/test_seo_weekly_review.py tests/test_watch_feature.py tests/test_account_deletion_retry.py tests/test_api_account_cleanup.py tests/test_model_configuration.py tests/test_source_check_repository.py tests/test_background_task_supervision.py tests/test_agent_calendar.py tests/test_agent_gmail.py -q
```

`native_mutations.py` verändert nur Funktionen im jeweiligen isolierten
pytest-Kindprozess. Keine Mutation schreibt Produktionsdateien. Der Harness
verlangt einen fachlichen Assertionfehler und akzeptiert keinen Import-/Setupfehler.
Logs liegen lokal unter `test-results/native-mutations`; JUnit-Läufe unter
`test-results/persistence-native.xml` und `test-results/persistence-unit.xml`.

## Bedeutung der Konkurrenznachweise

Barrieren starten konkurrierende öffentliche Operationen; sie befinden sich nie
im SDK-Callback oder zwischen dessen Reads/Writes. Der optionale lokale
Accountlock wird allein im Usage-Test entfernt, damit echte SDK-Transaktionen
wie bei verschiedenen Serverprozessen konkurrieren. Produktguards bleiben aktiv.

Sowohl Emulator 1.15.1 als auch 1.19.8 lieferten bei gleichzeitigem Lock-Upgrade
teilweise `ABORTED: Transaction lock timeout`, bis das unveränderte SDK-Limit
(Source 3, Topic/SEO 5, Share 12) erschöpft war. Das ist kein erfolgreicher Aufruf.
Die Tests erfassen ausschließlich dieses konkrete Fehlerbild. Wenn alle
Versuche abbrechen, muss der vollständige gespeicherte Zustand unverändert sein.
Danach erfolgt genau ein expliziter Wiederholungsaufruf je abgebrochenem Worker;
andere Fehler und erneute Fehler im Wiederholungsaufruf bleiben rot.

Source-Worker behandeln Infrastrukturfehler in `process_one` und lesen die
persistente Queue im nächsten Tick erneut; ein bereits geclaimter Fehler erhält
seinen gespeicherten Retryzustand. `topic_runner.run_due_topic_tick` protokolliert
den Claimfehler und lässt den Topic für den nächsten Tick fällig. Die Repository-
Tests prüfen daneben ausdrücklich Replays eines bereits gespeicherten Pakets;
sie behaupten keine kostenlose Wiederholung einer externen Provideroperation.
Der Report-Test vergleicht vor seinem getrennten Wiederholungsaufruf die Zahl
erfolgreicher Aufrufe exakt mit DB-Zähler und Rückgabewerten. Damit bleiben
Abbrüche sichtbar, statt sie als erfolgreiche Reports mitzuzählen.

## Verbleibende Betriebsgrenzen

Der Emulator belegt SDK-Transaktions- und Queryverhalten, keine produktive
Bucket-IAM-Konfiguration, GCS-Verfügbarkeit oder Ausfallfreiheit unter Last.
Das Storage-Double stellt weder ACL- noch Public-URL-Funktionen bereit; Download
und Löschkaskade laufen durch den echten Service. Auth-Löschung und Google-HTTP
werden ausschließlich an der externen Grenze ersetzt. Outbox-Zustellung bleibt
at-least-once; es gibt weiterhin keine Exactly-once-Zusage für E-Mail/Telegram
und keine globale Atomizität zwischen Modellkonfiguration und mehreren lokalen
Serverruntimes. Die historischen Coverage-Prozente werden durch diese Läufe nicht
zu einer neuen Coverage-Messung.

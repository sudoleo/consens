# Nutzerreisen über die Testgrenzen hinweg

[Einstieg](README.md) · [WP-29](work-packages.md#wp-29) ·
[Konkrete Befehle und Grenzen](implementation-browser.md) ·
[Stand vor der Umsetzung](journeys-pre-implementation-2026-10-02.md)

Stand 02.10.2026: **Alle sechs Fälle in
`tests/e2e/test_persisted_journeys.py` sind im integrierten Lauf bestanden.**
J01–J05 laufen vom Chromium über das originale gebaute AppFirebase und echte
main-Routen bis zum nativen Demo-Firestore. Der sechste Fall prüft eine echte
Speicherquotaverletzung. Externe Identität, Modellantworten und Mailtransport
sind deterministisch ersetzt. Interne HTTP-APIs werden im Browser nicht
abgefangen; direkte Firestore-Datenoperationen aus dem Browser werfen absichtlich Fehler.

| Reise | Gemeinsam ausgeführte Kette | Konkrete Assertions und Grenze |
|---|---|---|
| J-01 Consensus speichern und fortsetzen | Query → Chat/Turn/Context → prepare/ask → consensus → Turn/Bookmark → Reload/Follow-up | Zwei unterscheidbare Läufe im selben Chat haben getrennte Turn-IDs. Der erste Turn besitzt keine Kontextversion; die fertige Follow-up-Version bindet recent an den ersten und target an den zweiten Turn. Genau zwei konsumierte reguläre Receipts und exakt eine Consensusbuchung je Lauf. Fremdowner erhält 404; Ledger stimmt mit der Summe gemessener und geschätzter Schritte überein. |
| J-02 Agent stoppen und wiederherstellen | Agentansicht → Auth/Admission → Providersteps → Stop → Teilantwort/Settlement → Reload/Recover | Acht tatsächlich gestartete synthetische Providersteps kosten 1200 Tokens; Reservierung wird freigegeben. Teilantwort und failed/cancelled bleiben gespeichert. Recover liest denselben Snapshot ohne weiteren Dispatch oder erneute Buchung. |
| J-03 Quellen später nachladen | Importierter historischer V3-Job → Own-Key-Resume → echter Queueworker → Fetch/Judge/Cache → native Packagecommits → UI-Pagination/Reload | Neun Judgecalls, ein Fetch dank echtem Cache, neun Findings über mehrere Seiten. Echte Requestbildung, Parser und Quotevalidierung; nur externe Fetch-/Judgeantworten sind Fixtures. Alte Revision 409, Fremdowner 404, Fremdworker ohne Claim und neun stale Commits ohne Revisionsänderung. Terminaler Worker startet nichts erneut, vergisst den Key und hinterlässt ihn weder in entpacktem Plan noch Paketen/Cache. UI liest nach Reload 9/9. Neue V4-Läufe erhalten keinen künstlichen historischen Job. |
| J-04 Ergebnis teilen und beobachten | Saved-Bookmark-Pending → Share-Dialog/POST → öffentliche Seite → Follow/Double-Opt-in → Watchclaim/Pipeline → native Version | Autoritativ gespeicherter Inhalt statt UI-Komplettfixture. Mail wird am Transport abgefangen; Watchanlage erfolgt über echtes HTTP. Gezielter Ownerclaim und echte Pipeline mit externem Modellmock erzeugen eine unterscheidbare neue Version, ohne Baselineänderung. Fremde Sharelöschung wird verweigert. Globale Scheduler bleiben im E2E-Lifespan ausgeschaltet. |
| J-05 Konto löschen und wechseln während Arbeit läuft | Memory-CAS → laufende Synthese → Tombstone/Kaskade → Sessionwechsel → spätes Providerende/Settlement → Reload | Passive Callthrough-Beobachtung belegt den laufenden Producer. Der Test wartet auf tatsächliches Responseende und Capacityfreigabe nach Producer-/Settlement-/Cleanupabschluss. Erst danach prüft er fehlende Wiederbelebung, gesperrte alte Identität, unveränderten Kontrollowner samt Ledger, dessen geöffneten Kontrollbookmark nach Reload und die verborgene alte Agentansicht. Eine vollständige Abwesenheitsprüfung sämtlicher alter DOM-/Sidebareinträge ist das nicht. |
| Speicherfehler als eigener UIzustand | Erschöpfte native Bookmarkquote → erfolgreicher Consensus → fehlgeschlagener Save | Antwort bleibt sichtbar und Turn completed; persistence.error und Hinweis nennen fehlgeschlagenes Speichern. Es gibt keinen erfundenen Bookmark oder Saved-Erfolg. |

Der J03-Harness verweigert seinen Tick, falls die gemeinsame Emulatorqueue
fremde fällige Arbeit enthält. So führt der echte Worker keine Jobs anderer
Tests aus. Zufallsowner und gezieltes Cleanup ersetzen globale Datenbankresets.

## Weitere Ketten mit gezielten Schichtnachweisen

Diese Reisen sind keine zusätzlich behaupteten vollständigen Browserläufe.
Die ursprünglichen Lücken wurden auf der jeweils geeigneten Adapter-, Service-,
DOM- oder nativen Ebene geschlossen. Produktive externe Dienste bleiben Grenzen.

| Reise | Nachweis nach Umsetzung | Weiterhin getrennte Grenze |
|---|---|---|
| J-06 Adminrevision beeinflusst nächsten Lauf | Echte main-Fehlerumschläge und originaler Adminclient/Prompteditor bei 409; native CAS und Modellaktivierung/Rollback mit Writerkonkurrenz und gesondertem RPCfehler | Keine neue gemeinsame Chromiumreise vom Adminentwurf bis zum nächsten bezahlten Modellaufruf. |
| J-07 Publisher überlebt Wiederaufnahme | Echte Recovery-/Retention-/Cleanupadapter, Rebound-Idempotency-Schutz, Billing-Identity und historischer Source-GET; isolierter Standalonepublisher | Kein Neustart einer produktiven Publisherinstallation oder Liveindexierungsnachweis. Historische Sourcejobs bleiben von neuen sourcefreien Läufen getrennt. |
| J-08 Topiccheck aktualisiert öffentliche Historie | Echte Admin-/Revocationguards, strikter Claim-Identityparser, native Duequery/Claim und tatsächlicher Schedulerloop, echte Topic-DOM-/Chromiuminteraktion mit inertem Text und Seenmarkern | Kein neuer kompletter Browserlauf vom Administrationsklick über Scheduler bis SSR. Externe Pipelineantworten sind synthetisch. |
| J-09 Datei zu versioniertem Dokument | Nativer Quoten-/Metadatenwettlauf, echter Cloudadapter am strengen Bucketdouble, Fehlercleanup und wiederholbare Kontokaskade; verlustfreie Dokumenttabellen im echten Firestore | Keine produktive Bucket-IAM oder globale Objekt-/DBtransaktion, keine flächige visuelle Kontrolle aller DOCX/PDFseiten. |
| J-10 Google lesen und Aktion bestätigen | Native konkurrierende Claims, echte Hash-/Payload-/Guardpfade und Unknown-Replayverbot, externer HTTPwire kontrolliert; passende Detailbrowser-/DOMfälle | Keine echte Googlezustellung oder zusammenhängende Live-OAuthreise. |
| J-11 Gemeinsames Tokenkonto | Native letzte Admission, identische und verschiedene Operationen, Holds/Final/Release/UTC; Entfernung der echten Transaktionsatomarität wird erkannt. J01/J02 verbinden gespeichertes Ledger und UI | Keine Abgleichmessung realer Providerrechnungen oder produktiver Lastverfügbarkeit. |
| J-12 Watch vom Beleg zur Zustellung | Native Probeclaims mit Konfigurationsfence, echter Watch-Runcommit samt atomarer History/Outbox, Leaseübernahme und stale Ack; J04 verbindet Teilen/Follow mit nativer Watchversion | Kein vollständiger Browserlauf bis realer SMTP-/Telegramzustellung. Externe Zustellung bleibt at-least-once und wird kontrolliert ersetzt. |

## Gemeinsame Assertions und Pflege

- UI nach Reload aus gespeicherten Daten ableiten und unterscheidbare Owner,
  Chats, Turns, Contexts, Runs, Jobs und Versionen prüfen.
- Antworterfolg, unvollständige Teilantwort und Persistenzfehler getrennt und
  wahrheitsgemäß anzeigen; fehlgeschlagenes Speichern ist kein erfolgreicher Save.
- Stop/Retry/Recover darf zugesagtes Replay nicht erneut dispatchen oder buchen.
  Bereits gestartete Providersteps bleiben kostenpflichtig; reguläre Runbelastung
  und Agent-Meterbuchungen haben unterschiedliche Oracles.
- Nebenläufige Grenzen über beobachtbare Phasen/Barrieren kontrollieren und
  nach tatsächlichem Abschluss Daten prüfen. Keine zufälligen Sleeps als Beweis.
- Detailvarianten auf ihrer geeigneten Ebene halten. Zusätzliche Browserläufe
  brauchen einen bisher getrennten Datenübergang oder eine konkrete Regression.

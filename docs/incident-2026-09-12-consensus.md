# Consensus-Alert am 12.09.2026, 03:15 Uhr MESZ

Die vom Betreiber bereitgestellten Access-/Anwendungslogs und der Telegram-
Screenshot zeigen denselben Browserlauf. Personenbezogene Requestdaten werden
hier nicht wiederholt. Alle folgenden Zeiten sind MESZ (UTC + 2).

- 03:12:23: `/prepare` und sechs Modellrequests wurden mit HTTP 200 angenommen.
- Anschließend: Chat und Turn angelegt (201), `/consensus` angenommen (200).
  Der Access-Log-Zeitpunkt dafür ist nicht enthalten. Ein Streaming-200 belegt
  nur den Response-Start, keinen erfolgreichen Abschluss.
- 03:13:58: OpenRouter antwortet auf einen Chat-Completions-Request mit 200.
- 03:15:05: Browser meldet `consensus_failed`, Phase `consensus_connection`.
- 03:16:56: `Analysis completed attempts=1 duration_ms=180132`.
  Diese Logzeile entsteht im `finally` des Analysebudgets, auch bei Abbruch;
  sie beweist keine erfolgreiche Antwort. Die Dauer entspricht dem regulären
  180-Sekunden-Analysebudget. Mangels Correlation-ID (`corr=-`) ist die Zuordnung
  zum Browserlauf plausibel, aber nicht sicher.

Die Ursache des konkreten Vorfalls bleibt unbewiesen. Der Browser-Catch umfasst
auch Rendering-/Verarbeitungsfehler; die alte Meldung unterscheidet diese nicht
von einem Netzwerkfehler. Keepalives existieren bereits (15 Sekunden), der
Browser setzt für diesen Request keinen eigenen festen Timeout. Weder ein
bestimmter Providerfehler noch ein Proxytimeout oder Gerätewechsel ist belegt.

Bei der Untersuchung wurde unabhängig davon ein reproduzierbarer Fehler im
SSE-Reader gefunden: Nach einem vollständigen `final` wartete er weiter auf EOF.
Ein danach geworfener Read-Fehler ließ das bereits bestätigte Ergebnis scheitern.
Der Reader beendet sich jetzt beim autoritativen Abschlussereignis und räumt
seinen Reader auf. Zwischenereignisse bleiben unverändert. Regressionstests
prüfen den späten Read-Fehler, die Phasengrenze und unterschiedliche Fehlerarten.

Neue Alerts unterscheiden feste Fehlerkategorien für Request, Stream-Read,
Eventhandler, EOF ohne Abschluss und übrige Consensus-Verarbeitung. Die
serverseitige Allowlist erhält die bisherigen Grenzen gegen Nutzdaten in Alerts.
Dies ist eine Absicherung und Diagnoseverbesserung, kein Beweis, dass der
EOF-Fehler den beobachteten Vorfall ausgelöst hat.

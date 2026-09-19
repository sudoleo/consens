# Agent-Budget und Tool-Hinweise

19.09.2026. Lokale App mit isolierten HTTP-/SSE-Fixtures; keine bezahlten
Provider-Aufrufe oder Änderungen an produktiven Kontingenten.

Behoben:

- Die bisher nur bei Erfolg aktualisierte Prozentanzeige verarbeitet jetzt
  Live-Quota-Ereignisse, den bestehenden Activity-Poll und terminale Fehler.
  Nach Disconnect wird erneut gelesen; ältere oder fremde Snapshots gelten nicht.
- Die Tagesquote unterscheidet leeres verfügbares Budget und eine zu große
  Reservierung. Fehlermeldungen enthalten die Werte zum Ablehnungszeitpunkt;
  das Panel zeigt verbleibende Reserven nach Settlement.
- Eine abgelehnte Zulassung mit optionaler Websuche kann vor dem Provideraufruf
  ohne Suche erneut geprüft werden. Kontext-, Kosten- und Tokenlimits bleiben
  aktiv; kein doppelter Call/Beleg. Das Modell wird über die Einschränkung
  informiert und muss mit vorhandener Evidenz arbeiten.
- Tool-Nennungen im Reasoning erhalten Inline-Labels. Bestätigte, validierte
  Orchestrator-Aufrufe senden Start-/Endereignisse und zeigen separat „Active“.

Validierung:

- 441 JavaScript-Tests bestanden.
- 162 Agent-Backendtests und 23 Build-/Frontend-Vertragstests bestanden.
- 20 verschiedene Browserfälle bestanden. Sechs Budget-/Live-/Fehlerfälle
  nach finaler Darstellungskorrektur erneut geprüft. Der Scrolltest enthält
  ausreichend Inhalt, um bewusstes Hochscrollen außerhalb der Folgetoleranz
  tatsächlich zu testen.
- Desktop, 390px dunkel und 320px hell visuell geprüft; Labels bleiben bei
  Zeilenumbrüchen zusammen. Budget-Test: 75% → 32% während des Calls → 16%
  nach einem Reservierungsfehler, ohne neue Modellanfrage.
- Frontend neu gebaut, Build-Abgleich und Diff-Whitespace geprüft.

Das Nutzerlog enthält Providerfehler (429 und RuntimeError), aber keinen
terminalen SSE-Fehlertext. Die konkrete Ursache dieses historischen Laufs ist
damit nicht eindeutig nachweisbar; die beschriebenen Fehler sind im Code
nachgewiesen und durch Regressionstests abgedeckt.

[Tool-Nennung](agent-tool-mentioned-1280-light.png) ·
[Aktives Tool, mobil](agent-tool-active-390-dark.png) ·
[Budgetfehler](agent-budget-failure-1280.png)

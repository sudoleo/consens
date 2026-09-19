# Agent-Chat: Kontingent, Fortschritt und Quellen

19.09.2026 — gebaute App mit isolierten HTTP-/SSE-Fixtures, keine bezahlten
Provider-Aufrufe.

- Verbleibendes Tokenbudget im bestehenden Sidebar-Ring: 188878/250000 → 75%,
  nach Abschluss 140057/250000 → 56%. Exakte Zahlen und UTC-Reset im Panel.
- Composer ohne Tokenzeile, separaten Auto-Schalter und gesperrten Modusschalter.
  Reasoning bleibt im Chatmodellmenü per Maus und Tastatur erreichbar.
- Thinking startet geschlossen. Kurze Fortschrittsabsätze bleiben darunter
  sichtbar und verschwinden nach Ende/Stop; Details werden nur manuell geöffnet.
- Modell-Icons auf 15px verkleinert. Keine vertikalen Linien im Denkfortschritt.
- Quellen aus Chat-Recherche, Antworten und Vergleichen werden zusammengeführt.
  Provider-/Suchquellen bleiben auf gespeicherten Turns erhalten; alte Aktivitäten
  funktionieren ebenfalls. Sources ist auch ohne Vergleich verfügbar.

Prüfungen:

- **437 JavaScript-Tests** vollständig bestanden; zuletzt die vier Quellen-Tests
  nach einem zusätzlichen Schutz gegen veraltete Gesprächskontexte erneut geprüft.
- **126 Agent-Backendtests** einschließlich persistierter Quellen, Vergleich,
  Delegation, Reasoning, Budgets und Abbruch bestanden.
- **53 weitere Tests** für Suche, Frontend-Build, Cachemarken und Chat-UI-Verträge
  bestanden.
- **26 verschiedene Browserfälle** bestanden: 18 Agent-Fälle sowie acht
  Consensus-Picker-Regressionen. Sechs Quellen-/Vergleichsfälle zusätzlich nachgeprüft.
- Desktop, 390px dunkel und 320px hell visuell geprüft; alle Modell-Icons laden.
- Finaler Build-Abgleich und `git diff --check` ohne Befund.

[Desktop](comparison-review-1440.png) · [Mobil](comparison-review-390.png) ·
[Thinking](agent-live-1280-light.png) · [Reasoning-Menü](agent-effort-thread-1280-light.png)

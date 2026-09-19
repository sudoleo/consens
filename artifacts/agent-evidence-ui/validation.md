# Agent · Beta: Evidenzansicht und Denkfortschritt

Stand: 19.09.2026. Screenshots aus dem gebauten `/app` mit deterministischen
HTTP-/SSE-Fixtures; keine kostenpflichtigen Modellaufrufe.

## Ergebnis

- Zentrale Anbieter-Icons im überlappenden Modellstapel; wiederholte Aufrufe
  bleiben in der bestehenden Aktivitätsseitenleiste einzeln erreichbar.
- Kompakter Prüfstatus und Footer-Links. Rote Textstellen öffnen die passende
  Widerspruchskarte; Modelllinks öffnen formatierte Originalantworten.
- Gemeinsamer Consensus-Leser für Antworten, Unterschiede und Quellen,
  mit isolierten Vergleichsgrundlagen, Fokus-Rückkehr und gespeichertem Verlauf.
- Kurze Provider-Zusammenfassungen oder gekennzeichnete Satzauszüge. Neue Runs
  speichern begrenzte Kurztexte statt vollständiger sichtbarer Reasoning-Traces.
  Keine zusätzliche Zusammenfassung durch einen weiteren Modellaufruf.

## Validierung

- Vollständige Frontend-Suite: **434 Tests bestanden**, Build-Abgleich erfolgreich.
  Nach der letzten Fokus-/Refresh-Korrektur: **22 Leser-Tests erneut bestanden**.
- Backend-Gesamtlauf: **2400 bestanden**, zwei Befunde. Der alte Vertrag für
  archivierte Modelllinks wurde auf explizite Kontextnavigation aktualisiert;
  die CSS-Cachemarke wurde nachgezogen. Git-Verzeichnisvertrauen wurde nur für
  den Prüfprozess gesetzt. Anschließend **27 betroffene Tests bestanden**, inklusive
  Fortschritt, Cachemarken und Frontend-Build.
- Browser-Gesamtlauf über Agent, Delegation und Consensus-Leser: **71 bestanden**,
  acht Fälle mit veraltetem, mehrdeutigem Picker-Selektor. Nach dessen Korrektur
  **16 Tests bestanden**: alle acht betroffenen Fälle, die drei Agent-
  Vergleichsansichten und fünf Leser-Regressionen. Damit sind alle **79 Fälle**
  erfolgreich geprüft.
- Visuell geprüft: Desktop 1440px, Mobil 390px dunkel und 320px hell;
  Widerspruchskarten, Markdown-Antworten, Denkfortschritt und Aktivitätsleiste.
- Tastatur, Quellenlinks, Account-Reset, gespeicherte/archivierte Turns und
  kollisionsfreies Desktop-Docking automatisiert geprüft.
- `git diff --check` ohne Befund. Firestore-Emulator und reale Provider waren
  für diese UI-/Fortschrittsprüfungen nicht beteiligt.

## Ansichten

- [Chat/Desktop](comparison-review-1440.png)
- [Widersprüche/Desktop](comparison-contradictions-1440.png)
- [Chat/Mobil dunkel](comparison-review-390.png)
- [Originalantwort/320px](comparison-answer-320.png)
- [Denkfortschritt](agent-live-1280-light.png)
- [Live-Aktivitätsleiste](delegation-1440-light.png)

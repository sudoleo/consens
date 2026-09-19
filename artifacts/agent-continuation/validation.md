# Agent Chat: lange Läufe und nachvollziehbare Unterbrechungen

Stand: 19.09.2026. Ausschließlich deterministische Provider und isolierte lokale
Browser-Fixtures; keine bezahlten Modellaufrufe oder Produktions-DB-Schreibvorgänge.

- 2426 Backend-Tests geprüft: im Gesamtlauf 2425 erfolgreich, anschließend die
  Build-Freshness-Prüfung nach dem abschließenden Build erfolgreich. Der letzte
  gezielte Lauf umfasst 93 erfolgreiche Tests für Build, Fortsetzung, Agent-API
  und Bookmarks.
- 452 Frontend-Tests erfolgreich. Nach der abschließenden Anpassung des
  Bookmark-Ladepfads nochmals 52 betroffene Tests erfolgreich.
- Sechs Browserfälle erfolgreich: gespeicherte Unterbrechung auf Desktop/Mobil,
  Recovery ohne neuen Run und Admin-Konfiguration bei 1280/390/320 px. Die zwei
  Unterbrechungsfälle zuletzt nochmals über `openBookmark` mit dem gebauten
  Firebase-Modul geprüft und visuell kontrolliert.
- `npm run build` erstellt `app.bba4e19f2eed.js`, `firebase.5cc9d6fa1098.js` und
  die bestehende `app.f537fd43293a.css`.

Der Langlauftest führt 102 Modellaufrufe und 101 Tools über simulierte 17 Minuten
aus, einschließlich fortlaufender Suchzulassung und Lease-Erneuerung. Weitere
Tests prüfen fünf Vergleiche, mindestens 20 Judge-Aufrufe, zusätzliche Vergleiche
nach einem Review und vier Antwortversionen mit korrekt gebundener Abschlussprüfung.
Das Tagesbudget stoppt weiterhin vor einem weiteren bezahlten Aufruf. Gestoppte,
abgelaufene oder ersetzte Producer erhalten keine neue Lease. Kurze temporäre
DB-Ausfälle lösen keinen sofortigen Nutzerabbruch aus.

Ein Provider-Timeout erhält den Teiltext und einen sicheren Fehlergrund; zweimalige
Recovery erzeugt keinen neuen Provideraufruf. Desktop-/Mobilbelege:

- [Desktop](agent-saved-interruption-1280.png)
- [Mobil, dunkel](agent-saved-interruption-390.png)

Technische Modellfenster, begrenzte Provider-Nachrichten, Output-/Speichergrößen,
Parallelität und echte Verbindungsfehler bleiben relevant. Der Agent-Chat hat
keine zusätzliche feste Laufzeit, Rundenzahl, Suchanzahl oder Dollargrenze.

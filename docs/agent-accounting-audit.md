# Agent-Chat: Kontingent und Laufzeiten

Prüfung vom 19. September 2026. Umfang: Chatmodell, delegierte Worker,
Vergleichsmodelle, Coverage-/Differences-Judges und Quellenprüfung. Alle verwenden
denselben metered Provider-Adapter und den transaktionalen Receipt-/Tagesledger.

## Gefundene und behobene Fehler

- Fehlende Suchkostendetails machten auch bekannte Input-/Output-Zähler
  unvollständig. Token- und Kostenvollständigkeit werden getrennt behandelt.
- Vor Beginn abgelehnte HTTP-Anfragen konnten das Nutzerkontingent bis zum
  Tageswechsel reserviert halten. Eindeutige Ablehnungen erhalten einen
  Nullverbrauchsbeleg; bereits angenommene, unklare Aufrufe behalten die Reserve.
  Auch ein sofortiger Abbruch nach Admission, aber vor Start des Provider-Adapters,
  gibt die ungenutzte Reserve mit einem eigenen `not_started`-Beleg frei.
- Kumulative Zwischenstände konnten nach Streamabbruch als finale Usage gelten.
  Sie werden jetzt als Untergrenze markiert; nur endgültige Messungen lösen die
  Reservierung ab. Cache-/Reasoning-Details werden niemals zusätzlich gezählt.
  Ein finaler Kostenwert allein macht frühere Tokenzwischenstände nicht final.
- Verspätete Kontingentantworten konnten bei verschiedenen Serveruhren einen
  neueren Stand überschreiben. Ledger-Version, UTC-Tag und Reset-Version ordnen
  Antworten unabhängig von der Uhrzeit. Ein offener Tab aktualisiert das Budget
  auch ohne neuen Run; ein fehlgeschlagener Abruf ist sichtbar.
- Die Sidebar berechnete Laufzeiten aus Browser-Uhrzeit und Serverdatum und
  konnte gespeicherte aktive Sitzungen weiterzählen. Live-Dauern basieren nun auf
  monotonen Uhren und frieren bei Abschluss ein. Prozessabbrüche zeigen die
  letzte bestätigte Dauer als Untergrenze statt einer erfundenen exakten Dauer.
- Requests und Ansichten werden auch bei erneuter Anmeldung desselben Nutzers
  gegen die aktuelle Auth-Sitzung geprüft.
- Nach lokalem Stop wird weiter auf den terminalen Serverstatus abgeglichen,
  damit verzögert abgeschlossene Calls und deren Usage noch sichtbar werden.
  Verspätete Projektionen können weder den Lauf reaktivieren noch eine neuere
  Gesamtsumme durch einen früheren Zwischenstand ersetzen.

## Regressionen

`tests/test_agent_accounting_audit.py` prüft den realen SSE-Parser und die
Abrechnungsinvarianten für jede Modellvariante in `MODEL_CONFIGS`, einschließlich
Vergleichs-/Judge-Modellen. Zusätzliche Fälle prüfen kumulative/finale Usage,
eindeutige Ablehnungen gegenüber unklaren Abbrüchen, idempotente Belege,
fehlende Suchpreise, Ledger-Versionen und abgelaufene Prozess-Leases.

Die vorhandenen Agent-Tests prüfen außerdem Tageswechsel, globale Resets,
parallele Claims, fehlende Usage, Nullverbrauch, Abbruch, Fehler, Wiederherstellung,
Kontolöschung, Modell-/Kontextgrenzen und lange Chatläufe. Die Frontendtests
prüfen fehlerhafte Uhrzeiten, eingefrorene Ansichten, verspätete Budgets,
Tageswechsel und fehlgeschlagene Aktualisierungen. Firestore-Emulatortests prüfen
atomare Admission und genau einmalige Abrechnung unter konkurrierenden Requests.

Erfolgreiche Validierung: vollständige Backend-Suite (2.501 Tests), danach die
gesamte Agent-Suite nach den letzten Adapterkorrekturen (269 Tests, darunter
58 Auditfälle); vollständige Frontend-Suite (469 Tests) und erneuter Lauf der
betroffenen Chat-/Sidebar-Tests einschließlich neuer Fälle (51 Tests).
38 Desktop-/Mobil-Browserfälle und drei Tests gegen den isolierten echten
Firestore-Emulator bestanden; nach dem letzten Sidebar-Abgleich wurden deren
acht Browserfälle nochmals erfolgreich geprüft. Produktionsbundles wurden mit `npm run build`
erneuert. Veraltete Text-/UI-Verträge aus den vorangegangenen Bookmark- und
Bottom-Bar-Änderungen wurden an das aktuelle Verhalten angepasst; öffentliche
Share-/Topic-Seiten laden die aktuelle Quellenprüfungsdatei mit erneuertem
Cache-Key. Es wurden keine bezahlten Live-Modellaufrufe gestartet.

## Grenzen der Aussage

Die Tests verwenden deterministische Provider-Antworten; sie sind keine bezahlte
Live-Prüfung aller aktuell von OpenRouter gerouteten Endpunkte. Ein Provider muss
korrekte Usage liefern. Ohne finale Usage bleibt ein bereits gestarteter Aufruf
konservativ reserviert und ausdrücklich unbekannt bis zum UTC-Tageswechsel bzw.
Admin-Reset. Es wird weder eine Schätzung als Messung angezeigt noch ein
möglicherweise bezahlter Aufruf automatisch wiederholt. Die tatsächliche
Enddauer eines abgestürzten Prozesses kann nachträglich nicht exakt rekonstruiert
werden. Admin-Limitänderungen haben weiterhin den dokumentierten Config-Cache
von maximal 30 Sekunden; der Server entscheidet jede neue Admission atomar.

Provider-Vertrag: [Usage accounting](https://openrouter.ai/docs/cookbook/administration/usage-accounting),
[Streaming](https://openrouter.ai/docs/api_reference/streaming) und
[Credit-/Rate-Limits](https://openrouter.ai/docs/api_reference/limits).
Input-/Output-Tokens stammen aus Provider-Usage; `usage.cost` hat Vorrang vor
Katalogschätzungen. Streamfehler nach Annahme sind von HTTP-Ablehnungen vor der
Generierung zu unterscheiden.

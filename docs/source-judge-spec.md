# Historische Spezifikation: dritter Judge zur Quellenprüfung

Historischer Entwurf vom 9. September 2026. Dieser Text dokumentiert eine frühere
Planung und ist **kein aktueller Implementierungsvertrag**. Die inzwischen
implementierte v3-Belegprüfung mit vollständiger Paketplanung, dauerhafter Queue,
revidierbaren Statusseiten und geänderten Ergebniswerten ist in
[source-verification.md](source-verification.md) beschrieben. Insbesondere der
hier genannte Wert `mismatch` und die Begrenzung auf einen gemeinsamen Judge-Call
gelten für v3 nicht. Der folgende Entwurf bleibt als historische Referenz erhalten.

## 1. Aufgabe und Grenzen

Der Quellen-Judge prüft Aussagen im fertigen Consensus, die einen Quellenverweis besitzen:

- **Beleg:** Stützt die zugeordnete Quelle die Aussage einschließlich Zahlen, Bedingungen und Einschränkungen?
- **Zeitliche Passung:** Ist der belegte Stand für die Frage und die Aussage geeignet?

Er erzeugt ausschließlich Quellenhinweise. Consensus-Text, Modellantworten, Differences und Agreement bleiben unverändert. Keine Neubewertung, keine Suche nach neueren Quellen und keine Faktenprüfung von Aussagen ohne Quellenverweis. Diese Grenzen erzwingt der Anwendungscode.

## 2. Wann läuft er?

Sobald der vollständige Consensus-Text vorliegt, startet die Quellenprüfung parallel zu den bestehenden Judges. Sie wartet nicht auf deren Ergebnisse. Der Nutzer kann den Consensus bereits lesen.

Im Browser bleibt `consensus.final` der Abschluss des Antworttexts. Quellenstatus und Quellenhinweise werden separat nachgeliefert. Ohne Quellenverweise entfällt der Judge-Aufruf. Ein Fehler der Quellenprüfung darf die übrigen Ergebnisse weder verhindern noch verwerfen.

## 3. Welche Informationen bekommt er?

Der Server ordnet zitierte Aussagen ihren Quellen zu und lädt die referenzierten öffentlichen Dokumente. Identische Quellen werden nur einmal abgerufen. Übergeben werden:

- Nutzerfrage, gegebenenfalls aufgelöste Folgefrage und aktuelles Datum;
- exakte Antwortstellen mit stabilen Satz-IDs und zugeordneten Quellen-IDs;
- tatsächliche Quellenpassagen mit Überschrift und ausreichendem Nachbarkontext;
- URL, Abrufzeit sowie erkennbare Veröffentlichungs-, Änderungs-, Versions- oder Gültigkeitsangaben mit Herkunft.

URL und Titel allein reichen nicht. Fehlende Datumsangaben werden nicht ergänzt oder erraten. Quelleninhalte werden als Daten behandelt, niemals als Anweisungen. Der Abruf blockiert interne Netzwerkadressen, auch nach Weiterleitungen.

## 4. Was liefert er zurück?

Pro Aussage und zugeordneter Quelle liefert er zwei getrennte Bewertungen:

| Prüfung | Mögliche Ergebnisse |
|---|---|
| Beleg | `supported` – gestützt; `mismatch` – konkrete Abweichung; `unknown` – nicht feststellbar |
| Zeitliche Passung | `suitable` – für den Fragezeitraum geeignet; `outdated` – unpassender Stand belegt; `unknown` – nicht feststellbar; `not_relevant` – Alter unerheblich |

Dazu gehören Satz-ID, exakter Aussageausschnitt, Quellen-ID, kurze Begründung und vorhandene Belegpassagen. Der Server prüft IDs und Zitate gegen den gespeicherten Text. Ungültige oder fehlende Ergebnisse gelten als ungeprüft.

**Wichtige Regeln:**

- Fehlende Belege in einem begrenzten Ausschnitt beweisen keine Abweichung. Bei unzureichendem Kontext gilt `unknown`.
- Eine alte Quelle kann eine historische Frage korrekt beantworten. Eine alte Preisankündigung belegt dagegen nicht automatisch heutige Preise.
- Abrufdatum und Copyright-Jahr beweisen keine Aktualität. Ohne ausreichende Anhaltspunkte gilt `unknown`.
- Bei mehreren Quellen bleibt erkennbar, welche Quelle trägt und welche nicht. Eine ungeeignete Einzelquelle macht nicht automatisch die gesamte Aussage unbelegt.

## 5. Darstellung und Speicherung

Während der Prüfung erscheint dezent „Quellen werden geprüft“. Auffälligkeiten werden über **„2 Quellenhinweise“** in der Consensus-Kopfzeile zugänglich und an den betroffenen Aussagen markiert. Gezählt werden betroffene Aussagen, nicht einzelne Prüffelder.

Ein Klick zeigt Quelle, Originalpassage und verständlichen Grund, beispielsweise „Aussage von dieser Quelle nicht gedeckt“, „Veralteter Stand“ oder „Aktualität nicht feststellbar“. Unklarheit erhält eine neutrale Darstellung statt einer Fehlermarkierung. Unauffällige Prüfungen benötigen keine Satzmarkierung und keinen zusätzlichen Score.

Ein separates `source_verification`-Objekt speichert Status, geprüften Umfang und Befunde, gebunden an Antwortversion und Quellenstand. Wiederöffnen, Bookmarks und Shares verwenden diese gespeicherte Prüfung. Teilprüfungen werden ausdrücklich kenntlich gemacht.

## 6. Aufwand und Abnahme

Die vorhandenen Satz- und Quellenverweise werden ohne zusätzlichen Planungs-LLM-Aufruf gesammelt. Ein gebündelter Judge-Aufruf prüft die vorbereiteten Aussagen und Quellen. Quellenabrufe werden gecacht; Abrufanzahl, Textmenge, Laufzeit und Ausgabe erhalten konfigurierbare harte Grenzen. Nicht bearbeitete Aussagen bleiben ungeprüft; es gibt keine unbegrenzten Wiederholungen.

Die gemeinsame Prüflogik wird im Browser-Streaming und in der serverseitigen Consensus-Pipeline eingebunden. Modell und Limits sind serverseitig konfigurierbar.

Vor Freigabe prüfen Tests: korrekter Beleg, fehlende Einschränkung, konkrete Abweichung, mehrere Quellen, veralteter Stand, passende historische Quelle, unbekanntes Datum, Abruffehler, Teilprüfung und ungültige Judge-Ausgabe. Zusätzlich muss nachgewiesen sein: unveränderter Consensus/Agreement, paralleler Start und korrekte Wiederanzeige gespeicherter Hinweise. Ein manuell bewerteter Beispielsatz misst Fehlalarme, übersehene Probleme, Kosten und Laufzeit.

# Video: ausgewählte Bewegungsreferenzen

Stand: 09.09.2026. Dies ist die abgestimmte Stilrichtung und der ursprüngliche
Übertragungsvorschlag. Die anschließend beauftragte Umsetzung als v11 ist in
`docs/linkedin-launch-kinetic.md` dokumentiert. Ausgangspunkt war
`docs/linkedin-launch-focus.md` und der 70-Sekunden-Film.

## Auswahl des Eigentümers

- Hauptreferenz: Magnific, besonders die ersten 16 Sekunden mit Kacheln,
  schnellen cinematischen Übergängen und Schnitt auf dem Beat. Trotz Bewegung
  wenig gleichzeitiger Informationsinput. Der Mittel-/Spätteil gefällt weniger.
- Magnific-Outro übernehmen als Prinzip: Logo fliegt ein, anschließend baut
  sich der Name auf. Für consens.io ist ausdrücklich der Name unter dem Logo
  gewünscht.
- Ergänzend Higgsfield: gezielte Kamerafahrten und Zooms, besonders der Schritt
  „Pulling competitor ads“.
- Agentic Product Demo und ccvideo sind abgelehnt. Ihre Stile oder Vorschläge
  sind keine Grundlage für die nächste Videofassung.
- Ton des Magnific-Videos nach Möglichkeit ebenfalls verwenden.

## Geprüfte Quellen

Magnific: https://github.com/naveen-annam/creativly.ai-magnific-video-remotion

Film: https://www.youtube.com/watch?v=WM0SEHVh-j4

Geprüfter Commit: `f0ce11dddacf14a306c0c1f122dd06509e1873f8`.
Die Videobeschreibung bestätigt Claude Code für den Remotion-Nachbau und
Gemini 3.1 Pro für den Vergleich mit dem Original. Das Original erscheint
als kleines Vergleichsbild; die große Darstellung ist der Nachbau.

- `src/scenes/Scene01_Cascade.tsx`: zwei gegenläufige Kachelspalten,
  Auffächern in räumlich gestaffelte Positionen, beschleunigte Durchfahrt.
- `src/scenes/Scene02_Expand.tsx`: Kacheln entstehen zwischen zwei Textzeilen,
  verdrängen diese und gehen in eine Streuung mit anschließender Wischblende
  über. Einzelne Objekte und Typografie tragen den Übergang gemeinsam.
- `src/scenes/Scene03_MenuPolygon.tsx`: vertikales Durchlaufen mit kurzen
  Haltepunkten; aus einem kleinen grafischen Element entsteht die nächste
  Szenenfläche. Für consens.io ist die Formkontinuität interessant, keine
  zusätzliche Feature-Liste.
- `src/scenes/Scene06_Transforms.tsx` und `Scene07_MagnificLockup.tsx`:
  Übergang zum Signet und maskierte Enthüllung des Namens. Im Repo entsteht
  der Name rechts neben dem Signet; die Anordnung darunter ist die gewünschte
  consens.io-Adaption und keine Behauptung über den Repo-Code.
- `src/tokens.ts`: gemeinsame Bewegungskurven und sieben Abschnitte à fünf
  Sekunden. Diese Abschnittsgrenzen allein sind keine Audio-Beat-Erkennung.

Higgsfield: https://github.com/naveen-annam/creativly.ai-higgsfield-video-remotion

Film: https://www.youtube.com/watch?v=9APVoE65qfs

Geprüfter Commit: `409a4893c5b597ae456eb54f31994e5e9fe32d98`.

- `src/scenes/Scene02_Seg001.tsx`, Phase A: Cursor zum Sendeknopf, Klick
  bei lokalem Frame 30; Zoom beginnt bei Frame 24 und erreicht bei Frame 60
  Maßstab 3.0. Der Sendeknopf bestimmt den Transformationsursprung. Weißer
  Übergang zur nächsten Arbeitsphase. Bei 30 fps dauert die Zoomstrecke
  1,2 Sekunden. Die Szene beginnt im Repo nach 182 Frames, also bei ca. 6,07 s.
- Das übertragbare Prinzip ist ein inhaltlich begründetes Ziel der Kamera:
  erst Handlung zeigen, dann zum Ergebnis führen und dort lesbar ankommen.
  Stärke und Bildausschnitt müssen an unsere 4:5-Komposition angepasst werden.

Die Text-/Codequellen beider Repos einschließlich LICENSE und Commit-Nachweis
liegen lokal unter `artifacts/video-references/2026-09-09/`. Keine Installation
und keine Einbindung dieser Dateien in den aktuellen Renderer wurden vorgenommen.

## Konkreter Vorschlag für consens.io

Die folgenden Zeitfenster sind ein Entwurf für unsere ersten 16 Sekunden,
keine vermessenen Beats des Referenztons. Die endgültigen Schnittpunkte folgen
dem gewählten Musikstück. Die bisherige Gesamtlänge ist damit nicht geändert.

| Zeitentwurf | Bild und Information | Bewegung / Tonakzent |
| --- | --- | --- |
| 0–4 s | Echte Ausschnitte der Modellantworten als Kacheln; zentral nur „One question.“ | Gegenläufige Kacheln öffnen eine freie Mitte. Kurze Akzente beim Einrasten; Text bleibt während des Lesemoments stabil. |
| 4–8 s | „More than one AI.“; Kacheln fächern sich zu mehreren Perspektiven auf. | Kurze räumliche Auffächerung mit einer gemeinsamen Bewegungsrichtung; Schnitt auf einen markanten Beat. |
| 8–12 s | Eine Kachel übernimmt das Bild und wird zur echten Frage im Composer. | Durchfahrt bzw. Größenübergang in den Composer; gezielter Zoom zum Sendeknopf nach dem Higgsfield-Prinzip. |
| 12–16 s | Sendeklick löst die unabhängigen Antworten aus. | Klick und musikalischer Akzent fallen zusammen. Kamera öffnet sich zur Antwortanordnung; anschließend klarer Haltepunkt. |

Die Kacheln am Anfang dienen als visuelle Vorschau auf unterschiedliche
Perspektiven. Längere Antworten werden erst im eigentlichen Erklärteil gelesen.
Pro Bild gibt es eine Hauptaussage; Bewegung erhöht nicht die Textmenge.

Für den weiteren Film: den Übergang mehrerer Antworten zur Synthese über
kontinuierliche Kachelbewegung gestalten. Beide Judge-Rollen bleiben verständlich
erklärt. Beim Widerspruch auf die konkrete Passage fahren, die Detailansicht
aus derselben Position öffnen und zum Lesen abbremsen.

Outro: Das echte consens.io-Signet fliegt ein und bremst präzise auf dem
Schlussakzent ab. Der Name erscheint anschließend über eine Maske darunter.
Danach ein ruhiges, gut lesbares Schlussbild. Die Mechanik des maskierten
Namensaufbaus kann aus der Referenz abgeleitet werden; Logo und Typografie
kommen aus consens.io.

## Ton: bisheriges Ergebnis

Der rekursiv geprüfte Magnific-Repo-Baum enthält keine separate MP3-, WAV-,
M4A- oder OGG-Musik-/Effektdatei. Die Hauptkomposition enthält keine
Audio-Komponente. Drei MP4-Dateien sind Bildassets späterer Szenen; sie belegen
keine verfügbare vollständige Musikspur. Auch die vollständig geöffnete
YouTube-Beschreibung nennt keine Musikquelle oder Audio-Nutzungserlaubnis.

Der Originalton ist damit noch nicht als wiederverwendbare Quelle geklärt.
Es wurde kein Ton extrahiert und keine eigene Hör-/Beatmessung durchgeführt.
Die vorhandene Code-Lizenz ist kein Nachweis für die Rechte am YouTube-Ton.
Für eine Umsetzung zunächst Musik und ihre markanten Akzente festlegen,
anschließend Kachellandungen, Schnitte, Zoomziele und Logoankunft daran ausrichten.
Bewegungsgeräusche und kurze Impacts können dieses Timing zusätzlich betonen.

# Marke

Wie consens.io aussieht, wo die Marke herkommt und was sich daran nicht ändert.
Gilt für die Website, die App, Link-Vorschauen und alles, was nach außen geht
(Profilbilder, Banner, Posts, Filme).

## Bildmarke

Die Bildmarke ist ein Kreis und ein Keil, der ihn an vier Punkten schneidet.
Ihre eine Zeichnung liegt in `static/brand/mark.svg` (Zeichenfläche 279 × 200,
Kreis mit Radius 100 um 178,58 / 100, Keil aus fünf Kurven). Sie ist aus dem
ursprünglichen PNG nachgezeichnet und deckt sich zu 99,4 % mit ihm. **Die Form
wird nicht verändert, gedreht, gespiegelt oder ergänzt.**

- Immer einfarbig. Keine Kontur, kein Verlauf, kein Schatten, kein Glanz.
- Kleinste Breite 16 Pixel. Darunter laufen Keil und Kreis zusammen.
- Schutzraum: ringsum ein Viertel der Markenhöhe, auch zum Bildrand.

### Dateien

Jede Datei entsteht aus der Zeichnung. Nach einer Änderung an `mark.svg`:

    venv/Scripts/python.exe scripts/render_brand_assets.py

| Datei | Wofür |
|---|---|
| `static/favicon.svg` | Tab-Icon; Tinte oder Kreide je nach System-Thema |
| `static/brand/icon-192.png` | Kachel für Browser ohne SVG-Icons und für Suchergebnisse |
| `static/brand/apple-touch-icon.png` | Kachel für den iOS-Homescreen |
| `static/brand/logo-512.png` | Kachel als Organization-Logo im JSON-LD |
| `static/favicon.png` | helle Marke ohne Grund, für Icon-Reihen (CSS invertiert sie auf hellem Grund) |
| `static/favicon-dark.png` | dunkle Marke ohne Grund; Alphamaske der Link-Karten |

Die drei `<link>`-Zeilen für Icons stehen einmal in
`templates/partials/head_icons.html`; jede Seite bindet dieses Partial ein.

### Im Template

Neben der Wortmarke steht die Bildmarke immer als Zeichnung im HTML, über das
Makro `brand_mark` aus `templates/partials/brand.html`. Sie nimmt die Farbe des
Wortes daneben an (`currentColor`), kein Thema färbt sie um.

    {% from "partials/brand.html" import brand_mark %}
    <a class="brand">{{ brand_mark(width=24, height=17) }}<span>consens.io</span></a>

Nur in Reihen aus Anbieter-Icons (Benchmark-Achsen, Mockups) bleibt sie ein
`<img>` wie ihre Nachbarn.

`tests/test_brand_assets.py` hält Zeichnung, Makro und erzeugte Dateien gleich.

## Wortmarke und Lockup

„consens.io“ in Inter, Gewicht 600, Laufweite −0,02 em, klein geschrieben.

- Die Bildmarke ist 1,5 Schriftgrößen breit (24 px bei 16 px Schrift).
- Der Abstand zum Wort ist 9/16 der Schriftgröße (9 px bei 16 px).
- Eine Zeile, die Marke links, mittig zur Zeile. Gestapelt gibt es sie nicht.
- Bild- und Wortmarke haben denselben Ton. Kein Akzent auf „.io“.
- Ohne Wort steht die Bildmarke nur dort, wo der Name daneben steht:
  Profilbild, App-Icon, Favicon.

Im Code: `.brand` in `static/css/public-pages.css` und `static/css/landing.css`,
für Link-Karten `og_image._lockup` (dort ohne die enge Laufweite, die Pillow
nicht setzen kann).

## Töne

| Ton | Wert | Wo |
|---|---|---|
| Tinte | `#0A0A0A` | Marke und Text auf hellem Grund (`--ink` hell) |
| Papier | `#FAFAF7` | Fläche zum Lesen: Link-Karten, LinkedIn (`og_image.BG`) |
| Bühne | `#050505` | Fläche für den Auftritt: X, Film (`--ground` dunkel) |
| Kreide | `#F5F5F5` | Marke und Text auf dunklem Grund (`--ink` dunkel) |
| Grau | `#5E5E5E` / `#A1A1A1` | zweite Zeile, Beschriftung (`--ink-3`) |

Kein Blau. Grün (`--agree`) steht im Produkt für Übereinstimmung und kommt in
Logo, Banner und Film nicht vor.

## Schrift und Satz

Inter, keine zweite Schrift. Der Satz der Marke spricht in zwei Zeilen, die
zweite einen Ton leiser, wie die Überschrift der Startseite: Gewicht 600,
Laufweite −0,034 em, Zeilenhöhe 1,05, mit Punkt am Ende, nie in Versalien.

    The risk of              One AI does the work.
    one perspective.         Several check it.

## Profilbild und Banner

Ein Profilbild für alle Plattformen: die Kachel aus `render_brand_assets.py`
(Tinte, Marke in Kreide, zwei Drittel der Breite, 3,6 % unter der Mitte, weil
ihr Gewicht oben liegt).

Banner tragen nur den Satz der Marke, kein zweites kleines Logo; die Bildmarke
liegt groß und Ton in Ton im Hintergrund. X bekommt die Bühne, LinkedIn das
Papier. Der Satz steht dort, wo die Plattform nichts darüberlegt:

- X (1500 × 500): Das Profilbild verdeckt unten links etwa 27 % der Breite.
- LinkedIn (1128 × 191): Das Logo verdeckt unten links; die kleine Seitenkarte
  zeigt nur etwa die mittleren zwei Drittel.

## Bewegung

Erst die Linie, dann die Fläche: Ein Stift zieht den Kreis, dann den Keil, die
Fläche füllt sich, das Wort kommt dazu. Text erscheint Wort für Wort (75 ms
versetzt), ein Satz pro Bild. Eine Kurve für alles
(`cubic-bezier(.22, 1, .36, 1)`), nichts federt, nichts leuchtet. Der Keil darf
einmal um die Kugel wandern; am Ende steht immer die unveränderte Marke.

### Ident

Der Ident ist diese Regel als Film. Er beginnt auf leerem Grund und endet auf
dem stehenden Lockup in der Bildmitte, weil das letzte Bild in jedem Player
stehen bleibt. Es gibt ihn in zwei Fassungen:

| Fassung | Länge | Ablauf |
|---|---|---|
| Ident | 6 s | Kreis 0,2–1,25 s, Keil 1,1–2,2 s, Fläche 2,1–2,8 s, Lockup 3,1–4,3 s |
| Ident mit Satz | 11 s | dieselbe Zeichnung; darunter der Satz der Marke, eine Hälfte pro Bild (0,5–3,7 s und 4–7,2 s), Lockup 7,4–8,6 s |

- Solange das Wort fehlt, steht die Bildmarke allein und 2,3-mal so groß wie im
  Lockup. Zum Lockup rückt sie nach links und wird kleiner. Das Wort hat dabei
  ihr Maß und wird erst 0,3 s später sichtbar, weil es am Anfang im schmalen
  Bild über den Rand ragt.
- Der Satz steht zweizeilig unter der Marke, 0,72 Schriftgrößen des Lockups
  groß, damit er im Feed am Handy lesbar bleibt. Marke und Satz sind zusammen
  mittig; ist der Satz weg, setzt sich die Marke mit dem Lockup in die Mitte.
  Die Wörter kommen nacheinander und gehen zusammen, bevor sich die Marke bewegt.
- Die Schriftgröße des Lockups ist 6,8 % der Bildbreite. Im Querformat zählt
  als Breite höchstens das 1,25-Fache der Bildhöhe, sonst wird die Marke dort
  zu groß.
- Der Grund ist die Bühne. Papier nur dort, wo der Ident an einen hellen Film
  anschließt.
- 60 Bilder pro Sekunde, H.264, ohne Ton; 1920 × 1080, 1080 × 1350 und
  1080 × 1080. Die Filme liegen nicht im Repo.

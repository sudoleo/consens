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

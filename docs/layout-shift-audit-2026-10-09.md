# Layout-Shift-Audit /app (2026-10-09)

Ziel: In /app verschiebt sich nichts, was der Nutzer schon sieht (Maßstab:
ChatGPT/Claude). Grundlage: vier parallele Code-Analysen (Antwortinhalt,
Lauf-Chrome, Laden/Navigation, globales CSS/Scroll) plus eine Browser-Messung
(Playwright, Agent-Lauf mit getaktetem Stream, Review mit drei Claims, Final;
gemessen per Layout-Instability-API, Wortpositionen und Scrollposition pro
Frame, 1400/1100/390 px).

Wichtig für künftige Messungen: Die Layout-Instability-API sieht Verschiebungen
durch ersetzte DOM-Knoten (`innerHTML`) und durch programmatisches Scrollen
nicht. Beides ist hier die Hauptursache; gemessen wird daher über Wortpositionen
relativ zum Viewport.

## P1 — „Markierungen erscheinen → Text springt“

Alles feuert in einem synchronen Aufruf: `agent-chat.js` (~576–586) →
`agentReview.render` → `context.mark()` (`agent-review.js` ~525–546), sobald die
Live-Prüfung `checked` ist oder der Lauf endet.

1. **Claim-Marken haben Box-Geometrie.** `components-consensus-visuals.css`
   ~372–385: `padding: .1em .14em; margin: 0 -.02em` → netto ~4 px Breite pro
   markiertem Satz, Zeilen brechen neu um. Gemessen: Wörter in markierten
   Sätzen rücken 2 px, Folgezeilen brechen um. Fix: Padding/Margin 0, Überstand
   per `box-shadow: 0 0 0 .12em var(--cx-mark)` (mit `box-decoration-break:
   clone`), Reveal-Keyframes (`agent-chat.css` ~470–484) angleichen. Optionale
   `.claim-badge` (nur mit `claim-counts-visible`) fügen 20–28 px inline ein.
2. **Quellen werden erst beim Markieren zu Pills.** Stream rendert ohne
   `linkifyAgentSources` (`markdown-stream.js`, `renderAnswer` mit leerer
   Quellenliste); bei `mark()` werden `[Label](url)`/`[S1]` zu `.src-ref`-Pills
   (`shell.css` ~3523–3553, Favicon + Domain + Margins) → jeder zitierende Absatz
   bricht um, oft ±1–3 Zeilen. Fix: Pills schon pro fertigem Stream-Block
   erzeugen (Geometrie hängt nur an Host/Gruppenzahl, `fillSourceRef` füllt
   später in place).
3. **Evidenzzeile erscheint, während Auto-Follow läuft.** `.agent-review`
   (~62 px) wird per `body.after(host)` eingefügt; der Lauf ist noch `running`,
   `chat-scroll.js` folgt und scrollt die ganze Antwort weich ~62 px hoch
   (gemessen: 184→246 über ~300 ms). Fix: Folgen beenden, sobald der Text fest
   ist, oder die Zeile ab `checking` mit fester Höhe reservieren.
4. **Kompletter DOM-Tausch.** `mark()` ruft immer `injectMarkdown` (innerHTML);
   der Scroll-Anker des Browsers geht verloren, Umbrüche oberhalb des Viewports
   werden nicht kompensiert. Fix: nicht neu injizieren, wenn der Body schon
   `raw` zeigt; Marken/Pills in place wrappen.
5. **Zweiter Markierungsdurchgang am Laufende.** Live-Pass sendet `sources:
   undefined`, am Ende die echten Quellen → andere `markSignature` → erneuter
   Tausch + Linkify. Fix: gleiche Eingaben live wie am Ende, Signatur nur aus
   geometrierelevanten Eingaben.

## P2 — Während/nach dem Stream

6. **Lead-Absatz wächst nachträglich.** `markAnswerLead`
   (`markdown-stream.js` ~149–155) setzt `.has-lead`, sobald der zweite Block
   kommt → der schon gelesene erste Absatz springt 17→20 px, medium,
   `text-wrap: balance` (`shell.css` ~3249–3256). Fix: Lead ohne Größen-/
   Gewichtswechsel (höchstens Abstand/Farbe).
7. **Fortschrittslog über der Antwort kollabiert.** `agent-activity.js`
   `hidePreview` (~128–147) animiert die Schrittliste auf 0; jeder neue Schritt
   schiebt die Antwort vorher nach unten. Gemessen: 105→36 px am Laufende.
   `preserveAbove` (`chat-scroll.js` ~61–77) korrigiert nur, wenn der Block ganz
   oberhalb des Viewports liegt. Fix: eine Statuszeile fester Höhe, die am Ende
   zu „Thought for Xs“ wird; Verlauf in `<details>`/Panel.
8. **Consensus-Modus: `#consensusRun` verschwindet über der Antwort.**
   `consensus-progress.js` `vanish(700)` (~474–488), `shell.css` ~1095–1110;
   dazu `#runDetail` (~200 px Modellzeilen) beim Consensus-Start. Fix: Karte
   behält ihre Höhe und wird in place zur Provenienzzeile.
9. **Auto-Scroll beim Consensus-Reveal.** `consensus-lifecycle.js` ~43–46
   (`scrollIntoView` smooth ohne Nutzeraktion, auch beim Bookmark-Öffnen). Fix:
   entfernen, `chatScroll` besitzt das Scrollen.
10. **Spät nachgeladene Ressourcenliste.** Gemessen ~1,5 s nach Laufende:
    `#agentAnswerResources` +56 px, Antwort springt 15 px. Fix: Platz
    reservieren oder nur bei vorhandenen Dateien und ohne Scrollkorrektur
    einfügen.
11. **`text-wrap: pretty`** auf streamenden Absätzen (`shell.css` ~3245):
    Wörter hüpfen bei jedem Delta zwischen den letzten Zeilen. Fix: im
    Antwort-Body weglassen.
12. **Folgefrage baut den vorigen Turn neu** (`consensus-run.js`
    `renderStoredTurns`, andere Abstände in `.thread-history-turn`). Fix: nur
    neuen Turn anhängen, Live-Knoten in die History verschieben.

## P3 — Scroll-Modell

13. **Agent-Ausgabe scrollt die Seite die ganze Zeit mit.** `chat-scroll.js`
    ~173–186: `oneShot` prüft `context.bookmarkId`, Run-Kontexte haben aber nur
    `bookmark.id` → bei Läufen immer Follow; `step()` scrollt jeden Frame.
    ChatGPT/Claude: beim Senden die Frage einmal nach oben, der aktive Turn hat
    `min-height` ≈ Viewport minus Composer, die Antwort wächst in reservierten
    Raum, kein Mitscrollen. Entschärft auch 3, 7, 10.

## P4 — Laden/Reload

Wurzel: fast alle Seeds laufen bei `DOMContentLoaded`, nach dem ersten Paint
(das `firebase`-Modul vor der `app`-Gruppe wartet auf gstatic). CSP verbietet
Inline-Skripte; Fix: Pre-Paint-Hook im Head-Bundle (MutationObserver auf
`documentElement`, setzt Klassen, sobald `<body>`/`#appSidebar` geparst sind).

14. Eingeklappte Sidebar fährt bei jedem Reload aus und wieder ein
    (`app-init.js` ~676–684 `checkWindowSize`), Spalte gleitet ~130 px.
15. Compare-Nutzer: Composer springt von der Mitte nach unten
    (`model-answer-reader.js` `syncPreview`).
16. Angemeldete sehen 0,5–2 s „Log in / Sign up“ (`app-bootstrap.js` ~58–61
    blendet ohne Auth-Wissen ein, versteckt erst `firebase.js` ~577).
17. Zentrierter Composer rutscht ~13 px hoch, weil `#composerModeBar` erst
    nachträglich sichtbar wird (`agent-mode.js` ~364); strukturell: auf das
    Feld zentrieren statt auf die halbe `.input-section`.
18. Agent-Nutzer: Texte/Größen wechseln nach `/user_status` (Greeting, View-
    Switch-Label, „New comparison“→„New chat“, Placeholder, Modell-Chip), weil
    `selectedMode()` bis dahin „consensus“ liefert. Fix: `agentShellExpected`
    als Agent behandeln, letztes Modell-Label cachen.
19. Webfont-Tausch: Inter unter ungehashter URL mit `no-cache`, `font-display:
    swap`, kein Preload, keine metrikangepasste Fallback-Schrift
    (`typography.css` ~9–23). Gemessen: Texte überall 3–30 px breiter bei
    ~450–650 ms. Fix: gehashte URL, Preload, Fallback-`@font-face` mit
    `size-adjust`/`ascent-override`.
20. Sidebar-Liste ohne `scrollbar-gutter` (`layout.css` ~497–504): Windows-
    Scrollbar verengt die Liste um ~15 px, sobald sie überläuft.
21. Native Modell-Select vor Enhancement als breite Box gestylt
    (`components-consensus.css` ~1186 vs. `composer.css` ~104).
22. Mobil: View-Switch erscheint im Header, bevor `mobile-header.js` ihn
    verschiebt.

## P5 — Klein

23. Aktivitätsleiste ≥1200 px öffnet live selbst und zentriert die Spalte neu
    (`agent-delegation.js` ~137, `agent-chat.css` ~160–178): gemessen ~150 px
    Gleiten. Fix: Overlay ohne Spaltenbewegung oder nie automatisch öffnen.
24. Kopfzeile „Working for 9s“→„10s“→„1m 0s“ ändert die Breite, Icons rücken;
    auf 375 px droht Umbruch. Fix: Icons zuerst oder `min-width: 9ch`, nowrap.
25. `#agentReviewNotice` lässt den Sticky-Composer ~50 px wachsen.
26. Font-weight-Wechsel auf Zuständen (`shell.css` ~1158, ~2233 u. a.).
27. Modell-Zeile vor History-Antworten nachträglich eingefügt
    (`agent-review.js` ~590–605, ~40 px).
28. Horizontale Scrollbars in Tabellen/KaTeX während des Streams.

## Bereits in Ordnung

`html { scrollbar-gutter: stable }`, kein globales `scroll-behavior: smooth`,
Timer/Zähler mit `tabular-nums`, Hover auf Marken/Pills nur Farbe/Schatten,
Checking-Schimmer und Reveal-Strich ohne Geometrie, Favicons mit fester Größe,
Skeleton→Bookmark-Übergabe sauber, Account-Fuß mit `min-height`.
